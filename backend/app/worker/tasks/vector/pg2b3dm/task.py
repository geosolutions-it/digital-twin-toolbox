import os
import json
import shutil
import time
from concurrent.futures import ThreadPoolExecutor

from sqlmodel import Session, select, text, Table, MetaData, Column, insert, Integer
from app.core.db import engine_tasks, engine
from app.models.task import Asset
from app.worker.main import celery, PipelineDatabaseTask, AssetDatabaseTask
from app.worker.common.utils import (
    get_asset_upload_path, get_asset_table_name, get_pipeline_table_name, setup_output_directory
)
from app.worker.common.processes import (
    identify_projection, import_vector_to_postgres, export_geojson_from_postgres
)
from app.worker.common.expression import parse_expression
from app.worker.common.types import GeometryType, JSONEncoder
from app.worker.tasks.vector.pg2b3dm.processes import pg2b3dm
from app.worker.tasks.vector.pg2b3dm.polyhedron import geometry_to_polyhedral_surface, polyhedral_to_wkt
from osgeo import gdal, ogr
from pyproj import CRS


def _empty_payload():
    return {'metadata': False, 'stats': False, 'sample': False, 'epsg': None, 'horizontal_epsg': None, 'vertical_epsg': None}


@celery.task(name="inspect_vector", base=AssetDatabaseTask)
def inspect_vector(options):
    asset = options['asset']
    asset_id = asset['id']
    extension = asset['extension']
    to_ellipsoidal_height = options.get('to_ellipsoidal_height', False)

    asset_file_path = get_asset_upload_path(f"{asset_id}/index{extension}")

    ds = ogr.Open(asset_file_path)
    if ds is None:
        raise Exception(f"Cannot open {asset_file_path}")

    layers_info = []
    for i in range(ds.GetLayerCount()):
        layer = ds.GetLayer(i)
        layer_defn = layer.GetLayerDefn()
        geom_fields = []
        for j in range(layer_defn.GetGeomFieldCount()):
            gfd = layer_defn.GetGeomFieldDefn(j)
            srs = gfd.GetSpatialRef()
            geom_fields.append({
                'type': ogr.GeometryTypeToName(gfd.GetType()),
                'coordinateSystem': {'wkt': srs.ExportToWkt()} if srs else None,
            })
        layers_info.append({
            'name': layer.GetName(),
            'featureCount': layer.GetFeatureCount(),
            'geometryFields': geom_fields,
        })

    info = {
        'driverShortName': ds.GetDriver().GetName(),
        'layers': layers_info,
    }

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

    table_name = f'asset_{asset_id}'.replace('-', '_')
    geometry_column_name = 'geom'
    fid_column_name = 'gid'
    size_kb = asset['content_size'] / 1024
    feature_count = layers[0]['featureCount']
    limit = None
    if size_kb > 1000:
        limit = (feature_count * 1000) / size_kb

    import_vector_to_postgres(asset_file_path, table_name, geometry_column_name, fid_column_name, epsg, to_ellipsoidal_height)
    export_geojson_from_postgres(get_asset_upload_path(f"{asset_id}/sample.json"), table_name, limit)

    return {
        'asset_type': asset_type,
        'geometry_type': geometry_type,
        'payload': {**_empty_payload(), 'metadata': True, 'sample': True, 'epsg': epsg}
    }


@celery.task(name="inspect_raster", base=AssetDatabaseTask)
def inspect_raster(options):
    asset = options['asset']
    asset_id = asset['id']
    extension = asset['extension']

    asset_file_path = get_asset_upload_path(f"{asset_id}/index{extension}")

    try:
        info = gdal.Info(f'{asset_file_path}', format='json')
    except Exception as e:
        raise e

    epsg = CRS(info['coordinateSystem']['wkt']).to_epsg()

    with open(get_asset_upload_path(f"{asset_id}/metadata.json"), 'w') as f:
        json.dump(info, f)

    return {
        'asset_type': None,
        'geometry_type': None,
        'payload': {**_empty_payload(), 'metadata': True, 'epsg': epsg}
    }



def _polygons_to_polyhedrons(table, table_tasks, offset, chunk_size, geometry_column_name, fid_column_name, config, default_config, lod_column_name):
    with Session(engine_tasks) as session:
        try:
            rows = session.execute(select(table).offset(offset).limit(chunk_size)).all()
            print(f"Start polyhedrons conversion - offset {offset}")
            start = time.time()

            lod = 2 if config.get('add_lod') else 1
            meters_in_degrees = 111194.87428468118
            lod_max_simplify_tolerance = parse_expression('number', config['lod_max_simplify_tolerance'], {}, default_config['lod_max_simplify_tolerance'])

            for row in rows:
                for level in range(lod):
                    row_obj = row._asdict()
                    row_geometry = row_obj[geometry_column_name]

                    if level == (lod - 1):
                        as_geojson = session.exec(text(f"SELECT ST_AsGeoJSON('{row_geometry}')"))
                    else:
                        tolerance = (lod_max_simplify_tolerance / pow(2, level) / meters_in_degrees)
                        as_geojson = session.exec(text(f"SELECT ST_AsGeoJSON(ST_SimplifyPreserveTopology('{row_geometry}', {tolerance}))"))

                    properties = []
                    feature_properties = {}
                    for key in row_obj:
                        if key not in [geometry_column_name, fid_column_name]:
                            properties.append({key: row_obj[key]})
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
                    geometry_options = {
                        'lower_limit': lower_limit,
                        'upper_limit': upper_limit,
                        'translate_z': translate_z,
                        'remove_bottom_surface': config['remove_bottom_surface']
                    }

                    polyhedron_wkt = polyhedral_to_wkt(geometry_to_polyhedral_surface(geometry, geometry_options))
                    if polyhedron_wkt != 'POLYHEDRALSURFACE Z()':
                        feature_properties[geometry_column_name] = polyhedron_wkt
                        feature_properties[lod_column_name] = level
                        session.exec(insert(table_tasks).values(feature_properties))
                    else:
                        print(f'Error creating polyhedron:', feature_properties)

            session.commit()
            print(f"End polyhedrons conversion - offset {offset} elapsed time {time.time() - start}")
        except Exception as e:
            print(e)
            raise Exception


@celery.task(name="create_polygon_3dtiles", base=PipelineDatabaseTask)
def create_polygon_3dtiles(pipeline_extended):
    asset = pipeline_extended['asset']
    asset_id = asset['id']
    pipeline_id = pipeline_extended['id']
    table_name = get_asset_table_name(asset_id)
    geometry_column_name = 'geom'
    fid_column_name = 'gid'
    lod_column_name = 'lod'

    pipeline_config = pipeline_extended.get('data') or {}

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

    config = {**default_config, **pipeline_config}

    table = Table(table_name, MetaData(), autoload_with=engine_tasks)
    table_task_name = get_pipeline_table_name(pipeline_id)

    columns = [Column('id', Integer, primary_key=True)]
    for c in table.c:
        if c.name not in [geometry_column_name, fid_column_name]:
            columns.append(Column(c.name, c.type, primary_key=False, autoincrement=c.autoincrement))
    columns.append(Column(geometry_column_name, GeometryType))
    columns.append(Column(lod_column_name, Integer))

    table_tasks = Table(table_task_name, MetaData(), *columns)

    with Session(engine_tasks) as session:
        session.exec(text(f"DROP TABLE IF EXISTS {table_task_name};"))
        session.commit()
        table_tasks.create(session.connection())
        session.exec(text(f"CREATE INDEX ON {table_task_name} USING gist(st_centroid(st_envelope({geometry_column_name})));"))
        session.commit()
        total_rows = session.exec(text(f"SELECT COUNT(*) FROM {table}")).first()[0]

    chunks = list(range(0, total_rows, 1000))
    with ThreadPoolExecutor(max_workers=8) as executor:
        for offset in chunks:
            executor.submit(_polygons_to_polyhedrons, table, table_tasks, offset, 1000, geometry_column_name, fid_column_name, config, default_config, lod_column_name)

    output_paths = setup_output_directory(pipeline_id)

    geometric_error_factor = parse_expression('number', config['geometric_error_factor'], {}, default_config['geometric_error_factor'])
    max_geometric_error = parse_expression('number', config['max_geometric_error'], {}, default_config['max_geometric_error'])
    max_features_per_tile = parse_expression('number', config['max_features_per_tile'], {}, default_config['max_features_per_tile'])

    double_sided = 'true' if config['double_sided'] else 'false'

    attributes = [c.name for c in columns if c.name not in [geometry_column_name, fid_column_name, lod_column_name]]

    active_lod_column = lod_column_name if config.get('add_lod') else None

    pg2b3dm(
        table_task_name, output_paths['output_path_3dtiles'], attributes,
        geometric_error_factor, max_geometric_error, geometry_column_name,
        max_features_per_tile, double_sided, fid_column_name, table,
        active_lod_column, config['add_outline']
    )

    with Session(engine_tasks) as session:
        session.exec(text(f"DROP TABLE IF EXISTS {table_task_name};"))
        session.commit()

    shutil.make_archive(output_paths['output_path_3dtiles_zip'], 'zip', output_paths['output_path_3dtiles'])

    return {
        'output': output_paths['output_path'],
        'tileset': output_paths['output_tileset'],
        'download': output_paths['output_tileset_zip']
    }


@celery.task(name="complete_asset_remove_process")
def complete_asset_remove_process(options):
    asset = options['asset']
    table_name = get_asset_table_name(asset['id'])

    with Session(engine_tasks) as session:
        session.exec(text(f"DROP TABLE IF EXISTS {table_name};"))
        session.commit()

    try:
        upload_dir = os.path.dirname(get_asset_upload_path(f"{asset['id']}/index{asset['extension']}"))
        shutil.rmtree(upload_dir)
    except Exception:
        pass

    return {}


@celery.task(name="complete_pipeline_remove_process")
def complete_pipeline_remove_process(options):
    pipeline = options['pipeline']
    table_name = get_pipeline_table_name(pipeline['id'])

    with Session(engine_tasks) as session:
        session.exec(text(f"DROP TABLE IF EXISTS {table_name};"))
        session.commit()

    output_paths = setup_output_directory(pipeline['id'])
    try:
        shutil.rmtree(output_paths['output_path'])
    except Exception:
        pass

    return {}
