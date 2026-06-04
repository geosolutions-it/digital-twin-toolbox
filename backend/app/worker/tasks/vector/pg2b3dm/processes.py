import subprocess
import json
import os
import sqlalchemy.types as types
import mapbox_earcut
from app.core.config import settings


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


def pg2b3dm(table_task_name, output_3dtiles_path, attributes, geometric_error_factor, max_geometric_error, geometry_column_name, max_features_per_tile, double_sided, fid_column_name, table, lod_column_name, add_outline):
    options = []
    if add_outline:
        options = options + ['--add_outlines', 'true']
    if lod_column_name:
        options = options + ['--lodcolumn', lod_column_name, '--refinement', 'REPLACE']

    subprocess.run([
        'pg2b3dm',
        '-h', settings.POSTGRES_SERVER,
        '-p', f"{settings.POSTGRES_PORT}",
        '-d', settings.POSTGRES_TASKS_DB,
        '-U', settings.POSTGRES_USER,
        '-o', output_3dtiles_path,
        '-c', geometry_column_name,
        '-t', table_task_name,
        '-a', ",".join(attributes),
        '--geometricerror', f"{max_geometric_error}",
        '--double_sided', double_sided,
        '--use_implicit_tiling', "false",
        '--max_features_per_tile', f"{int(max_features_per_tile)}",
        '--geometricerrorfactor', f"{int(geometric_error_factor)}",
    ] + options)

    try:
        tileset_json_path = os.path.join(output_3dtiles_path, 'tileset.json')
        with open(tileset_json_path, "r") as f:
            data = json.load(f)

        property_keys = {}
        for c in table.c:
            if c.name not in [geometry_column_name, fid_column_name]:
                if type(c.type) is types.VARCHAR:
                    property_keys[c.name] = {}
                else:
                    property_keys[c.name] = {'minimum': 1, 'maximum': 1}

        data["properties"] = property_keys
        with open(tileset_json_path, "w") as f:
            json.dump(data, f)
    except Exception as e:
        raise e
