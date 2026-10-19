import mapbox_earcut


def earcut_flatten(data):
    vertices = []
    altitudes = []
    dimensions = len(data[0][0])
    rings = []
    ring_index = 0

    for ring in data:
        for p in ring:
            vertices.append([p[0], p[1]])
            altitudes.append(p[2])
        prev_len = 0
        if ring_index > 0:
            prev_len = rings[ring_index - 1]
        rings.append(prev_len + len(ring))
        ring_index += 1

    return {
        'vertices': vertices,
        'rings': rings,
        'dimensions': dimensions,
        'altitudes': altitudes
    }


def earcut(coordinates):
    try:
        data = earcut_flatten(coordinates)
        return mapbox_earcut.triangulate_float32(data.get('vertices'), data.get('rings'))
    except Exception as e:
        print('Earcut error', e)
        return []
