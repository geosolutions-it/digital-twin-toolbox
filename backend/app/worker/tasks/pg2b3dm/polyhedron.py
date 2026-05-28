from app.worker.tasks.pg2b3dm.processes import earcut


def parse_coords(coords, z, translate_z):
    height = coords[2] if coords[2] else 0
    if z:
        height = z
    _translate_z = translate_z if translate_z else 0
    return [coords[0], coords[1], height + _translate_z]


def parse_ring(ring, z, translate_z):
    return [parse_coords(coords, z, translate_z) for coords in ring]


def sum_until_index(arr, index):
    return sum(arr[:index])


def triangulate(coordinates, reverse):
    indices = earcut(coordinates)

    vertices = []
    for rings in coordinates:
        for ring in rings:
            vertices.append(ring)

    polyhedron = []
    for i in range(len(indices)):
        if i % 3 == 0:
            if reverse:
                polyhedron.append([
                    vertices[indices[i]],
                    vertices[indices[i + 2]],
                    vertices[indices[i + 1]],
                    vertices[indices[i]]
                ])
            else:
                polyhedron.append([
                    vertices[indices[i]],
                    vertices[indices[i + 1]],
                    vertices[indices[i + 2]],
                    vertices[indices[i]]
                ])
    return polyhedron


def plane_to_wall(lower_ring, upper_ring):
    polyhedron = []
    for i in range(len(lower_ring) - 1):
        if lower_ring[i + 1]:
            bl = lower_ring[i]
            br = lower_ring[i + 1]
            tl = upper_ring[i]
            tr = upper_ring[i + 1]
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

    lower = [parse_ring(ring, lower_limit, translate_z) for ring in geometry['coordinates']]

    if lower_limit is None and upper_limit is None:
        return to_polyhedral_surface(lower, None, remove_bottom_surface)

    upper = [parse_ring(ring, upper_limit, translate_z) for ring in geometry['coordinates']]

    average_z_lower = sum(c[2] for c in lower[0]) / len(lower[0])
    average_z_upper = sum(c[2] for c in upper[0]) / len(upper[0])

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
            vertices.append(" ".join(map(str, vertex)))
        triangles.append(f"(({', '.join(vertices)}))")
    return f"POLYHEDRALSURFACE Z({','.join(triangles)})"
