import os
from app.core.config import settings
from app.core.db import engine_tasks, engine
from sqlmodel import Session, select, text, Table, MetaData, Column, insert, Integer
import json
from app.worker.expression import parse_expression
from app.worker.polyhedron import geometry_to_polyhedral_surface, polyhedral_to_wkt
from app.worker.utils import get_asset_upload_path, get_asset_table_name, get_pipeline_table_name
from app.worker.processes import (
    import_vector_to_postgres,
    i3dm_export,
    pg2b3dm,
    export_geojson_from_postgres,
    identify_projection,
    pdal_stats,
    pdal_metadata,
    point_cloud_preview,
    py3dtiles_convert,
    process_las
)
import shutil
from app.models import Asset
from app.worker.types import GeometryType, JSONEncoder
from osgeo import gdal
from pyproj import CRS
import time
from concurrent.futures import ThreadPoolExecutor
import zipfile
import app.worker.photogrammetry.images_to_point_cloud as images_to_point_cloud
import app.worker.photogrammetry.point_cloud_to_mesh as point_cloud_to_mesh
import app.worker.photogrammetry.mesh_to_3dtile as mesh_to_3dtile

def complete_upload_process(options):
    asset = options['asset']
    asset_id = asset['id']
    extension = asset['extension']
    vector_data_extensions = options['vector_data_extensions']
    point_cloud_data_extensions = options['point_cloud_data_extensions']
    photogrammetry_formats = options['photogrammetry_formats']
    raster_formats = options['raster_formats']
    asset_type = None
    geometry_type = None
    metadata = False
    stats = False
    sample = False
    epsg = None
    horizontal_epsg = None
    vertical_epsg = None
    to_ellipsoidal_height = options['to_ellipsoidal_height']

    asset_file_path = get_asset_upload_path(f"{asset_id}/index{extension}")

    if extension in vector_data_extensions:
        try:
            info = gdal.VectorInfo(f'{asset_file_path}', format='json')
        except Exception as e:
            raise e

        layers = info['layers']
        if len(layers) > 1:
            raise Exception("Multiple layers not supported")

        geometry_fields = layers[0]['geometryFields']
        if len(geometry_fields) > 1:
            raise Exception("Multiple geometry types not supported")

        geometry_type = geometry_fields[0]['type']

        if 'Multi' in geometry_type:
            raise Exception("Multi geometry is not supported")

        coordinate_system = geometry_fields[0].get('coordinateSystem')

        if coordinate_system:
            epsg = CRS(coordinate_system['wkt']).to_epsg()
        else:
            raise Exception("Missing spatial reference system")

        supported_geometry = 'Polygon' in geometry_type or 'Point' in geometry_type
        if not supported_geometry:
            raise Exception(f"{geometry_type} type is not supported")

        asset_type = info['driverShortName']

        if 'Point' in geometry_type:
            geometry_type = 'Point'
        if 'Polygon' in geometry_type:
            geometry_type = 'Polygon'

        with open(get_asset_upload_path(f"{asset_id}/metadata.json"), 'w') as f:
            json.dump(info, f)

        metadata = True
        id = f"{asset_id}".replace('-', '_')
        table_name = f'asset_{id}'
        geometry_column_name = 'geom'
        fid_column_name = 'gid'
        limit = None
        size_kb = asset['content_size'] / 1024
        feature_count = layers[0]['featureCount']
        if size_kb > 1000:
            limit = (feature_count * 1000) / size_kb

        import_vector_to_postgres(asset_file_path, table_name, geometry_column_name, fid_column_name, epsg, to_ellipsoidal_height)
        export_geojson_from_postgres(get_asset_upload_path(f"{asset_id}/sample.json"), table_name, limit)
        sample = True

    if extension in point_cloud_data_extensions:

        metadata_json = pdal_metadata(asset_file_path)
        with open(get_asset_upload_path(f"{asset_id}/metadata.json"), 'w') as f:
            json.dump(metadata_json, f)

        metadata = True

        stats_json = pdal_stats(asset_file_path)
        with open(get_asset_upload_path(f"{asset_id}/stats.json"), 'w') as f:
            json.dump(stats_json, f)

        stats = True

        epsg = identify_projection(metadata_json['metadata']['comp_spatialreference'])
        horizontal_epsg = identify_projection(metadata_json['metadata']['srs']['horizontal'])
        vertical_epsg = identify_projection(metadata_json['metadata']['srs']['vertical'])

        point_cloud_preview(asset_file_path, get_asset_upload_path(f"{asset_id}/sample.xyz"), metadata_json, stats_json)
        sample = True

        asset_type = 'LAS'
        geometry_type = 'PointCloud'

    if extension in raster_formats:
        try:
            info = gdal.Info(f'{asset_file_path}', format='json')
        except Exception as e:
            raise e

        epsg = CRS(info['coordinateSystem']['wkt']).to_epsg()

        with open(get_asset_upload_path(f"{asset_id}/metadata.json"), 'w') as f:
            json.dump(info, f)

        metadata = True

    if extension in photogrammetry_formats:
        asset_type = 'Photogrammetry'
        unzip_directory = get_asset_upload_path(f"{asset_id}/process/images/")
        os.makedirs(unzip_directory, exist_ok=True)
        with zipfile.ZipFile(asset_file_path, 'r') as zip_ref:
           zip_ref.extractall(unzip_directory)

    return {
        'asset_type': asset_type,
        'geometry_type': geometry_type,
        'payload': {
            'metadata': metadata,
            'stats': stats,
            'sample': sample,
            'epsg': epsg,
            'horizontal_epsg': horizontal_epsg,
            'vertical_epsg': vertical_epsg
        }
    }

def setup_output_directory(pipeline_id):
    relative_output_path = os.path.join("output", f"{pipeline_id}")
    output_path = os.path.join(settings.ASSETS_DATA, relative_output_path)

    try:
        shutil.rmtree(output_path)
    except Exception:
        pass

    os.makedirs(output_path, exist_ok=True)

    return {
        'relative_output_path': relative_output_path,
        'output_path': output_path,
        'output_path_3dtiles': os.path.join(output_path, 'tiles'),
        'output_path_3dtiles_zip': os.path.join(output_path, 'download'),
        'output_tileset': os.path.join(settings.API_V1_STR, relative_output_path, 'tiles', 'tileset.json'),
        'output_tileset_zip': os.path.join(settings.API_V1_STR, relative_output_path, 'download.zip'),
    }

def create_point_instance_3dtiles(pipeline_extended):

    asset = pipeline_extended['asset']
    asset_id = asset['id']
    pipeline_id = pipeline_extended['id']
    table_name = get_asset_table_name(asset_id)
    geometry_column_name = 'geom'
    fid_column_name = 'gid'

    pipeline_config = {}
    if pipeline_extended['data']:
        pipeline_config = pipeline_extended['data']

    default_config = {
        'model': "model.glb",
        'rotation': 0,
        'scale': 1,
        'translate_z': 0,
        'max_features_per_tile': 5000,
        'max_geometric_error': 1000,
    }

    config = {
        **default_config,
        **pipeline_config
    }

    table = Table(table_name, MetaData(), autoload_with=engine_tasks)

    table_task_name = get_pipeline_table_name(pipeline_id)

    models = []

    with Session(engine_tasks) as session:

        session.exec(text(f"DROP TABLE IF EXISTS {table_task_name};"))
        session.exec(text(f"CREATE TABLE {table_task_name}(id serial PRIMARY KEY,{geometry_column_name} geometry(POINTZ, 4326),scale double precision,scale_non_uniform double precision[3],rotation double precision,model varchar,tags json);"))
        session.exec(text(f"CREATE INDEX {table_task_name}_geom_idx ON {table_task_name} USING GIST ({geometry_column_name});"))
        session.commit()
        
        statement = select(table).execution_options(yield_per=1000)
        # need to use execute to return rows instead of scalar
        for partition in session.execute(statement).partitions():
            for row in partition:
                row_obj = row._asdict()
                row_geometry = row_obj[geometry_column_name]
                as_geojson = session.exec(text(f"SELECT ST_AsGeoJSON('{row_geometry}')"))
                properties = []
                feature_properties = {}
                for key in row_obj:
                    if not key in [geometry_column_name, fid_column_name]:
                        pair = {}
                        pair[key] = row_obj[key]
                        properties.append(pair)
                        feature_properties[key] = row_obj[key]

                geojson_string = as_geojson.first()[0]
                geometry = json.loads(geojson_string)
                coordinates = geometry['coordinates']
                z = 0
                if coordinates[2]:
                    z = coordinates[2]

                feature = {
                    'type': 'Feature',
                    'properties': feature_properties,
                    'geometry': geometry
                }
                translate_z = parse_expression('number', config['translate_z'], feature, default_config['translate_z'])

                coordinates = [
                    coordinates[0],
                    coordinates[1],
                    z + translate_z
                ]
                updated_geometry = {
                    **geometry,
                    'coordinates': coordinates
                }
                updated_geometry_string = json.dumps(updated_geometry)
                properties_string = json.dumps(properties, cls=JSONEncoder)
                feature = {
                    'type': 'Feature',
                    'properties': feature_properties,
                    'geometry': updated_geometry
                }
                model_scale = parse_expression('number', config['scale'], feature, default_config['scale'])
                model_rotation = parse_expression('number', config['rotation'], feature, default_config['rotation'])
                model_name = parse_expression('string', config['model'], feature, default_config['model'])

                if not model_name in models:
                    models.append(model_name)

                values = ",".join([f"ST_GeomFromGeoJSON('{updated_geometry_string}')", f"{model_scale}", f"{model_rotation}", f"'{model_name}'", f"'{properties_string}'" ])
                session.exec(text(f"INSERT INTO {table_task_name}({geometry_column_name}, scale, rotation, model, tags) VALUES ({values});"))

        session.commit()


    output_paths = setup_output_directory(pipeline_id)

    max_geometric_error = parse_expression('number', config['max_geometric_error'], {}, default_config['max_geometric_error'])
    max_features_per_tile = parse_expression('number', config['max_features_per_tile'], {}, default_config['max_features_per_tile'])

    i3dm_export(
        table_task_name,
        output_paths['output_path_3dtiles'],
        max_geometric_error,
        geometry_column_name,
        max_features_per_tile,
        fid_column_name,
        table
    )

    with Session(engine_tasks) as session:
        session.exec(text(f"DROP TABLE IF EXISTS {table_task_name};"))
        session.commit()
    
    with Session(engine) as session:
        for model in models:
            statement = select(Asset).where(Asset.filename == model).limit(1)
            results = session.exec(statement)
            model_asset = results.first()
            model_asset_path = get_asset_upload_path(f"{model_asset.id}/index{model_asset.extension}")
            shutil.copy(model_asset_path, os.path.join(output_paths['output_path_3dtiles'], 'content', model))

    try:
        shutil.make_archive(output_paths['output_path_3dtiles_zip'], 'zip', output_paths['output_path_3dtiles'])
    except Exception as e:
        raise e

    return {
        'output': output_paths['output_path'],
        'tileset': output_paths['output_tileset'],
        'download': output_paths['output_tileset_zip']
    }

def polygons_to_polyhedrons(table, table_tasks, offset, chunk_size, geometry_column_name, fid_column_name, config, default_config, lod_column_name):
    with Session(engine_tasks) as session:

        try:

            rows = session.execute(select(table).offset(offset).limit(chunk_size)).all()
            print(f"Start polyhedrons conversion - offset {offset}")
            start = time.time()

            lod = 1

            if config.get('add_lod'):
                lod = 2

            meters_in_degrees = 111194.87428468118

            lod_max_simplify_tolerance =  parse_expression('number', config['lod_max_simplify_tolerance'], {}, default_config['lod_max_simplify_tolerance'])

            for row in rows:
                for level in range(lod):
                    row_obj = row._asdict()
                    row_geometry = row_obj[geometry_column_name]
                    as_geojson = None
                    if level == (lod - 1):
                        as_geojson = session.exec(text(f"SELECT ST_AsGeoJSON('{row_geometry}')"))
                    else:
                        tolerance = (lod_max_simplify_tolerance / pow(2, level) / meters_in_degrees)
                        as_geojson = session.exec(text(f"SELECT ST_AsGeoJSON(ST_SimplifyPreserveTopology('{row_geometry}', {tolerance}))"))

                    properties = []
                    feature_properties = {}
                    for key in row_obj:
                        if not key in [geometry_column_name, fid_column_name]:
                            pair = {}
                            pair[key] = row_obj[key]
                            properties.append(pair)
                            feature_properties[key] = row_obj[key]

                    geojson_string = as_geojson.first()[0]
                    geometry = json.loads(geojson_string)

                    feature = {
                        'type': 'Feature',
                        'properties': json.loads(json.dumps(feature_properties, cls=JSONEncoder)),
                        'geometry': geometry
                    }

                    lower_limit = parse_expression('number', config['lower_limit_height'], feature, default_config['lower_limit_height'])
                    upper_limit = parse_expression('number', config['upper_limit_height'], feature, default_config['upper_limit_height'])
                    translate_z = parse_expression('number', config['translate_z'], feature, default_config['translate_z'])
                    remove_bottom_surface = config['remove_bottom_surface']
                    geometry_options = {
                        'lower_limit': lower_limit,
                        'upper_limit': upper_limit,
                        'translate_z': translate_z,
                        'remove_bottom_surface': remove_bottom_surface
                    }

                    polyhedron_wkt = polyhedral_to_wkt(geometry_to_polyhedral_surface(geometry, geometry_options))
                    if polyhedron_wkt != 'POLYHEDRALSURFACE Z()':
                        feature_properties[geometry_column_name] = polyhedron_wkt
                        feature_properties[lod_column_name] = level
                        session.exec(insert(table_tasks).values(feature_properties))
                    else:
                        print(f'Error creating polyhedron:', feature_properties)

            session.commit()
            end = time.time()
            print(f"End polyhedrons conversion - offset {offset} elapsed time {end - start}")
        except Exception as e:
            print(e)
            raise Exception

def create_mesh_3dtiles(pipeline_extended):

    asset = pipeline_extended['asset']
    asset_id = asset['id']
    pipeline_id = pipeline_extended['id']
    table_name = get_asset_table_name(asset_id)
    geometry_column_name = 'geom'
    fid_column_name = 'gid'
    lod_column_name = 'lod'

    pipeline_config = {}
    if pipeline_extended['data']:
        pipeline_config = pipeline_extended['data']

    default_config = {
        'lower_limit_height': None,
        'upper_limit_height': None,
        'translate_z': 0,
        'max_features_per_tile': 1000,
        'double_sided': False,
        'geometric_error_factor': 1,
        'max_geometric_error': 500,
        'remove_bottom_surface': True,
        'add_lod': False,
        'lod_max_simplify_tolerance': 5,
        'add_outline': False
    }

    config = {
        **default_config,
        **pipeline_config
    }

    table = Table(table_name, MetaData(), autoload_with=engine_tasks)

    table_task_name = get_pipeline_table_name(pipeline_id)

    columns = []
    columns.append(Column('id', Integer, primary_key=True))
    for c in table.c:
        if not c.name in [geometry_column_name, fid_column_name]:
            columns.append(Column(c.name, c.type, primary_key=False, autoincrement=c.autoincrement))

    columns.append(Column(geometry_column_name, GeometryType))
    columns.append(Column(lod_column_name, Integer))

    table_tasks = Table(table_task_name, MetaData(), *columns)

    total_rows = 0
    chunk_size = 1000
    max_workers = 8

    with Session(engine_tasks) as session:

        session.exec(text(f"DROP TABLE IF EXISTS {table_task_name};"))
        session.commit()

        table_tasks.create(session.connection())

        session.exec(text(f"CREATE INDEX ON {table_task_name} USING gist(st_centroid(st_envelope({geometry_column_name})));"))
        session.commit()

        total_rows = session.exec(text(f"SELECT COUNT(*) FROM {table}")).first()[0]

    chunks = [i for i in range(0, total_rows, chunk_size)]

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for offset in chunks:
            executor.submit(polygons_to_polyhedrons, table, table_tasks, offset, chunk_size, geometry_column_name, fid_column_name, config, default_config, lod_column_name)

    output_paths = setup_output_directory(pipeline_id)

    geometric_error_factor = parse_expression('number', config['geometric_error_factor'], {}, default_config['geometric_error_factor'])
    max_geometric_error = parse_expression('number', config['max_geometric_error'], {}, default_config['max_geometric_error'])
    max_features_per_tile = parse_expression('number', config['max_features_per_tile'], {}, default_config['max_features_per_tile'])
 
    double_sided = 'false'
    if config['double_sided']:
        double_sided = 'true'

    attributes = []

    for column in columns:
        if not column.name in [geometry_column_name, fid_column_name, lod_column_name]:
            attributes.append(column.name)

    if not config.get('add_lod'):
        lod_column_name = None

    pg2b3dm(
        table_task_name,
        output_paths['output_path_3dtiles'],
        attributes,
        geometric_error_factor,
        max_geometric_error,
        geometry_column_name,
        max_features_per_tile,
        double_sided,
        fid_column_name,
        table,
        lod_column_name,
        config['add_outline']
    )

    with Session(engine_tasks) as session:
        session.exec(text(f"DROP TABLE IF EXISTS {table_task_name};"))
        session.commit()

    try:
        shutil.make_archive(output_paths['output_path_3dtiles_zip'], 'zip', output_paths['output_path_3dtiles'])
    except Exception as e:
        raise e

    return {
        'output': output_paths['output_path'],
        'tileset': output_paths['output_tileset'],
        'download': output_paths['output_tileset_zip']
    }

def create_point_cloud_3dtiles(pipeline_extended):

    pipeline_config = {}
    if pipeline_extended['data']:
        pipeline_config = pipeline_extended['data']

    default_config = {
        "colorization_image": '',
        "sample_radius": None,
        "to_ellipsoidal_height": False,
        "ground_classification": False,
        "geometric_error_scale_factor": 1,
    }

    config = {
        **default_config,
        **pipeline_config
    }

    asset = pipeline_extended['asset']
    pipeline_id = pipeline_extended['id']

    output_paths = setup_output_directory(pipeline_id)

    sample_radius = parse_expression('number', config['sample_radius'], {}, default_config['sample_radius'])
    colorization_image = parse_expression('string', config['colorization_image'], {}, default_config['colorization_image'])
    to_ellipsoidal_height = config['to_ellipsoidal_height']
    ground_classification = config['ground_classification']

    colorization_image_path = None
    if colorization_image:
        with Session(engine) as session:
            statement = select(Asset).where(Asset.filename == colorization_image).limit(1)
            results = session.exec(statement)
            image_asset = results.first()
            colorization_image_path = get_asset_upload_path(f"{image_asset.id}/index{image_asset.extension}")

    input_file = process_las(
        pipeline_id,
        asset,
        sample_radius=sample_radius,
        to_ellipsoidal_height=to_ellipsoidal_height,
        colorization_image=colorization_image_path,
        ground_classification=ground_classification
    )

    crs_in = None

    if asset['upload_result']:
        if asset['upload_result']['horizontal_epsg']:
            crs_in = asset['upload_result']['horizontal_epsg']
        elif asset['upload_result']['epsg']:
            crs_in = asset['upload_result']['epsg']

    if not crs_in:
        raise Exception('Not recognized Point Cloud CRS')

    geometric_error_scale_factor = parse_expression('number', config['geometric_error_scale_factor'], {}, default_config['geometric_error_scale_factor'])

    py3dtiles_convert(
        input_file,
        output_paths['output_path_3dtiles'],
        f'{crs_in}',
        geometric_error_scale_factor
    )

    try:
        shutil.make_archive(output_paths['output_path_3dtiles_zip'], 'zip', output_paths['output_path_3dtiles'])
    except Exception as e:
        raise e

    return {
        'output': output_paths['output_path'],
        'tileset': output_paths['output_tileset'],
        'download': output_paths['output_tileset_zip']
    }

def create_reconstructed_mesh(pipeline_extended):

    asset = pipeline_extended.get('asset')
    asset_id = asset.get('id')
    pipeline_id = pipeline_extended.get('id')

    pipeline_config = {}
    if pipeline_extended['data']:
        pipeline_config = pipeline_extended['data']

    default_config = {
        "stage": 'all',
        "feature_process_size": 2048,
        "depthmap_resolution": 2048
    }

    config = {
        **default_config,
        **pipeline_config
    }

    output_paths = setup_output_directory(pipeline_id)

    process_dir = get_asset_upload_path(f"{asset_id}/process/")

    stage = config.get('stage')

    if stage == 'all' or stage == 'images_to_point_cloud':

        feature_process_size = parse_expression('number', config['feature_process_size'], {}, default_config['feature_process_size'])
        depthmap_resolution = parse_expression('number', config['depthmap_resolution'], {}, default_config['depthmap_resolution'])

        config_overrides = {
            'processes': 4,
            'read_processes': 4,
            'feature_process_size': int(feature_process_size),
            'depthmap_resolution': int(depthmap_resolution),
        }
        images_to_point_cloud.run(process_dir, config_overrides)

    if stage == 'all' or stage == 'point_cloud_to_mesh':
        point_cloud_to_mesh.run(process_dir)

    if stage == 'all' or stage == 'mesh_to_3dtile':
        os.makedirs(output_paths.get('output_path_3dtiles'), exist_ok=True)
        mesh_to_3dtile.run(process_dir, output_paths.get('output_path_3dtiles'))
        try:
            shutil.make_archive(output_paths['output_path_3dtiles_zip'], 'zip', output_paths['output_path_3dtiles'])
        except Exception as e:
            raise e

    return {
        'output': output_paths['output_path'],
        'tileset': output_paths['output_tileset'],
        'download': output_paths['output_tileset_zip']
    }

def complete_pipeline_remove_process(options):

    pipeline = options['pipeline']

    table_name = get_pipeline_table_name(pipeline['id'])

    with Session(engine_tasks) as session:
        session.exec(text(f"DROP TABLE IF EXISTS {table_name};"))
        session.commit()

    output_paths = setup_output_directory(pipeline['id'])

    try:
        # remove uploaded file
        shutil.rmtree(output_paths['output_path'])
    except Exception:
        pass

    return {}

def complete_asset_remove_process(options):

    asset = options['asset']
    table_name = get_asset_table_name(asset['id'])

    with Session(engine_tasks) as session:
        session.exec(text(f"DROP TABLE IF EXISTS {table_name};"))
        session.commit()

    try:
        # remove uploaded file
        upload_file_directory = os.path.dirname(get_asset_upload_path(f"{asset['id']}/index{asset['extension']}"))
        shutil.rmtree(upload_file_directory)
    except Exception:
        pass

    return {}
