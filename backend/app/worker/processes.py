import subprocess
import json
import re
import os
from app.core.config import settings
import sqlalchemy.types as types
import math
from pyproj import CRS
from app.worker.utils import get_asset_upload_path

ogr2ogr_db = f"dbname='{settings.POSTGRES_TASKS_DB}' host='{settings.POSTGRES_SERVER}' port='{settings.POSTGRES_PORT}' user='{settings.POSTGRES_USER}' password='{settings.POSTGRES_PASSWORD}'"
i3dm_db = f"Host={settings.POSTGRES_SERVER};Username={settings.POSTGRES_USER};password={settings.POSTGRES_PASSWORD};Port={settings.POSTGRES_PORT};Database={settings.POSTGRES_TASKS_DB}"

def earcut_js(coordinates):
    coordinates_str = json.dumps(coordinates)
    result = subprocess.run([
        'node',
        '/app/node/earcut.js',
        coordinates_str
    ], stdout=subprocess.PIPE)
    output = list(map(int, result.stdout.decode("utf-8").split(',')))
    return output

def identify_projection(projection):
    try:
        crs = CRS(projection).to_epsg()
        if crs:
            return crs
        # fallback on projinfo
        result = subprocess.run(
            [ 'projinfo', f"{projection}", '-o', '-PROJ', '--identify' ],
            stdout=subprocess.PIPE
        )
        lines = str(result.stdout.decode("utf-8")).splitlines()
        epsg = []
        for line in lines:
            if 'EPSG' in line:
                search = re.search(r'EPSG\:(.*)\:', line)
                if search:
                    epsg.append(search.group(1))
        if len(epsg) > 0:
            return epsg[0]
        return None
    except Exception:
        return None

def import_vector_to_postgres(asset_upload_path, table_name, geometry_column_name, fid_column_name):
    subprocess.run([
        'ogr2ogr', '-f', 'PostgreSQL', f'PG:{ogr2ogr_db}',
        f'{asset_upload_path}',
        '-t_srs', 'EPSG:4979',
        '-lco', f'GEOMETRY_NAME={geometry_column_name}',
        '-lco', f'FID={fid_column_name}',
        '-lco', 'SPATIAL_INDEX=GIST',
        # '-lco', 'OVERWRITE=YES',
        '-nln', table_name,
        '-dim', "3"
        ],
        capture_output = True,
        text = True
    )

def export_geojson_from_postgres(output_path, table_name, limit):
    options = []
    if limit != None:
        options + ['-limit', f"{limit}"]

    subprocess.run(['ogr2ogr', '-f', 'GeoJSON', output_path, f'PG:{ogr2ogr_db}', table_name] + options,
        capture_output = True,
        text = True
    )

    if not os.path.isfile(output_path):
        raise Exception("Sample not created")

def i3dm_export(table_task_name, output_3dtiles_path, max_geometric_error, geometry_column_name, max_features_per_tile, fid_column_name, table):
    subprocess.run(
        [
            'i3dm.export',
            '-c', i3dm_db,
            '-t', table_task_name,
            '-o', output_3dtiles_path,
            '-f', 'cesium',
            '-g', f"{int(max_geometric_error)}",
            '--use_external_model', "true",
            '--use_scale_non_uniform', "false",
            '--geometrycolumn', geometry_column_name,
            '--max_features_per_tile', f"{int(max_features_per_tile)}",
            '--use_gpu_instancing', "false",
            '--boundingvolume_heights', '0,10' # TODO: verify the usage of this parameter
        ],
        capture_output = True,
        text = True
    )
    try:
        tileset_json_path = os.path.join(output_3dtiles_path, 'tileset.json')
        with open(tileset_json_path, "r") as jsonFile:
            data = json.load(jsonFile)

        property_keys = {}

        for c in table.c:
            if not c.name in [geometry_column_name, fid_column_name]:
                if type(c.type) is types.VARCHAR:
                    property_keys[c.name] = {}
                else:
                    property_keys[c.name] = {
                        'minimum': 1,
                        'maximum': 1
                    }

        data["properties"] = property_keys

        with open(tileset_json_path, "w") as jsonFile:
            json.dump(data, jsonFile)

    except Exception as e:
        raise e

def pg2b3dm(table_task_name, output_3dtiles_path, attributes, min_geometric_error, max_geometric_error, geometry_column_name, max_features_per_tile, double_sided, fid_column_name, table):
    subprocess.run(
        [
            'pg2b3dm',
            '-h', settings.POSTGRES_SERVER,
            '-p', f"{settings.POSTGRES_PORT}",
            '-d', settings.POSTGRES_TASKS_DB,
            '-U', settings.POSTGRES_USER,
            '-o', output_3dtiles_path,
            '-c', geometry_column_name,
            '-t', table_task_name,
            '-a', ",".join(attributes),
            '-g', f"{max_geometric_error},{min_geometric_error}",
            '--double_sided', double_sided,
            '--use_implicit_tiling', "false",
            '--max_features_per_tile', f"{int(max_features_per_tile)}"
        ],
        capture_output = True,
        text = True
    )

    try:
        tileset_json_path = os.path.join(output_3dtiles_path, 'tileset.json')
        with open(tileset_json_path, "r") as jsonFile:
            data = json.load(jsonFile)

        property_keys = {}

        for c in table.c:
            if not c.name in [geometry_column_name, fid_column_name]:
                if type(c.type) is types.VARCHAR:
                    property_keys[c.name] = {}
                else:
                    property_keys[c.name] = {
                        'minimum': 1,
                        'maximum': 1
                    }

        data["properties"] = property_keys

        with open(tileset_json_path, "w") as jsonFile:
            json.dump(data, jsonFile)

    except Exception as e:
        raise e

def pdal_metadata(output_file_path):
    try:
        result = subprocess.run(
            [ 'pdal', 'info', f'{output_file_path}', '--metadata' ],
            stdout=subprocess.PIPE
        )
        return json.loads(result.stdout.decode("utf-8"))
    except Exception as e:
        raise e

def pdal_stats(output_file_path):
    try:
        result = subprocess.run(
            [ 'pdal', 'info', f'{output_file_path}', '--stats' ],
            stdout=subprocess.PIPE
        )
        return json.loads(result.stdout.decode("utf-8"))
    except Exception as e:
        raise e

def point_cloud_preview(input_file_path, output_file_path, metadata, stats):

    pipeline = [
        {
            "filename": input_file_path,
            "type": 'readers.las'
        }
    ]

    count = metadata['metadata']['count']

    if count > 500000:
        step = int(math.ceil(count / 500000))
        pipeline += [
            {
                "type": 'filters.decimation',
                "step": step
            }
        ]

    statistic = stats['stats']['statistic']
    x = None
    y = None
    z = None
    red = None

    for value in statistic:
        if value['name'] == 'X':
            x = value
        if value['name'] == 'Y':
            y = value
        if value['name'] == 'Z':
            z = value
        if value['name'] == 'Red':
            red = value


    size = [
        x['maximum'] - x['minimum'],
        y['maximum'] - y['minimum'],
        z['maximum'] - z['minimum'],
    ]

    center = [
        x['minimum'] + (size[0] / 2),
        y['minimum'] + (size[1] / 2),
        z['minimum'] + (size[2] / 2),
    ]

    pipeline += [
        {
            "type": "filters.transformation",
            "matrix": f"1  0  0  {-center[0]}  0  1  0  {-center[1]}  0  0  1  {-center[2]}  0  0  0  1"
        }
    ]

    if red:
        pipeline += [
            {
                "type": 'writers.text',
                "format": 'csv',
                "order": 'X,Y,Z,Red:0,Green:0,Blue:0',
                "keep_unspecified": False,
                "filename": output_file_path
            }
        ]
    else:
        pipeline += [
            {
                "type": 'writers.text',
                "format": 'csv',
                "order": 'X,Y,Z',
                "keep_unspecified": False,
                "filename": output_file_path
            }
        ]
    
    pipeline_sample_dir = os.path.dirname(output_file_path)
    pipeline_sample_path = os.path.join(pipeline_sample_dir, 'sample-pipeline.json')

    with open(pipeline_sample_path, "w") as jsonFile:
        json.dump(pipeline, jsonFile)

    res = subprocess.run(
        [
            'pdal',
            'pipeline',
            pipeline_sample_path
        ],
        capture_output = True,
        text = True
    )

    if not os.path.isfile(output_file_path):
        print(res.stderr)
        raise Exception("Sample not created")
    
def scale_geometric_error(leaf, scale = 1):

    scaled_leaf = {
        **leaf,
        'geometricError': leaf['geometricError'] * scale
    }

    if "children" in leaf:

        children = []
        for child_leaf in leaf['children']:
            children.append(scale_geometric_error(child_leaf, scale))

        return {
            **scaled_leaf,
            'children': children
        }

    return scaled_leaf


def py3dtiles_convert(input, output, srs_in, geometric_error_scale_factor = 1):
    res = subprocess.run(
        [
            'py3dtiles',
            'convert',
            input,
            '--overwrite',
            '--classification',
            '--force-srs-in',
            # // see https://gitlab.com/py3dtiles/py3dtiles/-/issues/201
            '--color_scale', "255",
            '--out', output,
            '--srs_in', srs_in,
            '--srs_out', '4978',
            '--intensity'
        ],
        capture_output = True,
        text = True
    )

    try:
        tileset_json_path = os.path.join(output, 'tileset.json')
        with open(tileset_json_path, "r") as jsonFile:
            data = json.load(jsonFile)

        updated_tileset = {
            **data,
            "properties": {
                "Classification": { "minimum": 0, "maximum": 255 }
            },
            "geometricError": data["geometricError"] * geometric_error_scale_factor,
            "root": scale_geometric_error(data['root'], geometric_error_scale_factor)
        }

        with open(tileset_json_path, "w") as jsonFile:
            json.dump(updated_tileset, jsonFile)

    except Exception as e:
        print(res.stderr)
        raise e

def process_las(
    pipeline_id,
    asset,
    sample_radius=None,
    to_ellipsoidal_height=False,
    colorization_image='',
    ground_classification=False
):

    asset_upload_path = get_asset_upload_path(asset['id'], asset['extension'])
    pipeline = []
    if sample_radius:
        pipeline += [
            {
                "type": 'filters.sample',
                "radius": sample_radius
            }
        ]
    
    if to_ellipsoidal_height:
        if 'upload_result' in asset:
            upload_result = asset['upload_result']
            horizontal_epsg = None
            if 'horizontal_epsg' in upload_result and upload_result['horizontal_epsg']:
                horizontal_epsg = upload_result['horizontal_epsg']

            # EGM2008
            vertical_epsg = 3855
            if vertical_epsg in upload_result and upload_result['vertical_epsg']:
                vertical_epsg = upload_result['vertical_epsg']

            geodetic_crs = CRS(horizontal_epsg).geodetic_crs.to_epsg()

            pipeline += [
                {
                    "type": 'filters.reprojection',
                    "in_srs": f"EPSG:{horizontal_epsg}+{vertical_epsg}",
                    "out_srs": f"EPSG:{horizontal_epsg}+{geodetic_crs}",
                    "error_on_failure": True
                }
            ]

    if colorization_image:
        pipeline += [
            {
                "type": 'filters.colorization',
                "raster": colorization_image
            }
        ]

    if ground_classification:
        pipeline += [
            {
                "type": "filters.assign",
                "assignment": "Classification[:]=0"
            },
            {
                "type": "filters.elm"
            },
            {
                "type": "filters.outlier"
            },
            {
                "type": "filters.smrf",
                "ignore": "Classification[7:7]"
            }
        ]

    if len(pipeline) == 0:
        return asset_upload_path

    output_processed_laz_path = get_asset_upload_path(asset['id'], '.laz', pipeline_id)
    pipeline_process_path = get_asset_upload_path(asset['id'], '.json', f"{pipeline_id}.pipeline")

    pipeline = [{
        "filename": asset_upload_path,
        "type": 'readers.las'
    }] + pipeline + [{
        "type": 'writers.las',
        "filename": output_processed_laz_path,
        "compression": True
    }]

    with open(pipeline_process_path, "w") as jsonFile:
        json.dump(pipeline, jsonFile)

    res = subprocess.run(
        [
            'pdal',
            'pipeline',
            pipeline_process_path
        ],
        capture_output = True,
        text = True
    )

    if not os.path.isfile(output_processed_laz_path):
        print(res.stderr)
        raise Exception("Sample not created")

    return output_processed_laz_path
