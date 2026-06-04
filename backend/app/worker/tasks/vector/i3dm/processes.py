import subprocess
import json
import os
import sqlalchemy.types as types
from app.core.config import settings

i3dm_db = f"Host={settings.POSTGRES_SERVER};Username={settings.POSTGRES_USER};password={settings.POSTGRES_PASSWORD};Port={settings.POSTGRES_PORT};Database={settings.POSTGRES_TASKS_DB}"


def i3dm_export(table_task_name, output_3dtiles_path, max_geometric_error, geometry_column_name, max_features_per_tile, fid_column_name, table):
    subprocess.run([
        'i3dm.export',
        '-c', i3dm_db,
        '-t', table_task_name,
        '-o', output_3dtiles_path,
        '-g', f"{int(max_geometric_error)}",
        '--use_external_model', "true",
        '--use_scale_non_uniform', "false",
        '--geometrycolumn', geometry_column_name,
        '--max_features_per_tile', f"{int(max_features_per_tile)}",
        '--use_gpu_instancing', "false",
        '--boundingvolume_heights', '0,10'
    ])

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
