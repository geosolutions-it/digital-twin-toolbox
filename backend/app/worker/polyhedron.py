from app.worker.cartesian import convert_to_cartesian
from app.worker.processes import earcut_js

def parse_coords(coords, z, translate_z):
    height = coords[2]
    if not height:
        height = 0
    if z:
        height = z

    _translate_z = translate_z
    if not _translate_z:
        _translate_z = 0
    return [coords[0], coords[1], height + _translate_z]

def parse_ring(ring, z, translate_z):
    parsed_ring = []
    for coords in ring:
        parsed_ring.append(parse_coords(coords, z, translate_z))
    return parsed_ring

def sum_until_index(arr, index):
    filtered_arr = []
    for idx, value in enumerate(arr):
        if idx < index:
            filtered_arr.append(value)
    sum = 0
    for value in filtered_arr:
        sum += value
    return sum

def triangulate(coordinates, reverse):

    indices = earcut_js(coordinates)

    vertices = []

    for rings in coordinates:
        for ring in rings:
            vertices.append(ring)

    polyhedron = []

    for i in range(len(indices)):
        if i % 3 == 0:
            if reverse:
                polyhedron.append([
                    convert_to_cartesian(vertices[indices[i]]),
                    convert_to_cartesian(vertices[indices[i + 2]]),
                    convert_to_cartesian(vertices[indices[i + 1]]),
                    convert_to_cartesian(vertices[indices[i]])
                ])
            else:
                polyhedron.append([
                    convert_to_cartesian(vertices[indices[i]]),
                    convert_to_cartesian(vertices[indices[i + 1]]),
                    convert_to_cartesian(vertices[indices[i + 2]]),
                    convert_to_cartesian(vertices[indices[i]])
                ])
    return polyhedron

def plane_to_wall(lower_ring, upper_ring):
    polyhedron = []

    for i in range(len(lower_ring) - 1):
        if lower_ring[i + 1]:
            bl = convert_to_cartesian(lower_ring[i])
            br = convert_to_cartesian(lower_ring[i + 1])
            tl = convert_to_cartesian(upper_ring[i])
            tr = convert_to_cartesian(upper_ring[i + 1])
            polyhedron.append([bl, tl, br, bl])
            polyhedron.append([br, tl, tr, br])

    return polyhedron

def generate_walls(lower, upper):
    walls = []
    for idx in range(len(lower)):
        walls += plane_to_wall(lower[idx], upper[idx])
    return walls

def to_polyhedral_surface(lower, upper, remove_bottom_surface):
    if not upper:
        return triangulate(lower, False)

    polyhedral_surface = []
    polyhedral_surface += triangulate(upper, False)
    polyhedral_surface += generate_walls(lower, upper)

    if not remove_bottom_surface:
        polyhedral_surface += triangulate(lower, True)

    return polyhedral_surface

def polygon_to_polyhedral_surface(geometry, options):
    lower_limit = options['lower_limit']
    upper_limit = options['upper_limit']
    translate_z = options['translate_z']
    remove_bottom_surface = options['remove_bottom_surface']
    lower = []
    for ring in geometry['coordinates']:
        lower.append(parse_ring(ring, lower_limit, translate_z))

    if lower_limit == None and upper_limit == None:
        return to_polyhedral_surface(lower, None, remove_bottom_surface)

    upper = []
    for ring in geometry['coordinates']:
        upper.append(parse_ring(ring, upper_limit, translate_z))

    average_z_lower = 0
    for coords in lower[0]:
        average_z_lower += coords[2]

    average_z_lower /= len(lower[0])

    average_z_upper = 0
    for coords in upper[0]:
        average_z_upper += coords[2]

    average_z_upper /= len(upper[0])

    if average_z_lower > average_z_upper:
        return to_polyhedral_surface(upper, lower, remove_bottom_surface)

    return to_polyhedral_surface(lower, upper, remove_bottom_surface)

def geometry_to_polyhedral_surface(geometry, options):
    if geometry['type'] == 'Polygon':
        return polygon_to_polyhedral_surface(geometry, options)
    return []

def polyhedral_to_wkt(polyhedron):
    triangles = []
    for triangle in polyhedron:
        vertices = []
        for vertex in triangle:
            vertex_string = " ".join(map(str, vertex))
            vertices.append(vertex_string)
        vertices_string = ", ".join(vertices)
        triangles.append(f"(({vertices_string}))")
    wkt = ",".join(triangles)
    return f"POLYHEDRALSURFACE Z({wkt})"
