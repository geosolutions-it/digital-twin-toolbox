import os
import json
import shutil

from sqlmodel import Session, select, text, Table, MetaData
from app.core.db import engine_tasks, engine
from app.models.task import Asset
from app.worker.main import celery, PipelineDatabaseTask
from app.worker.common.utils import (
    get_asset_table_name, get_pipeline_table_name, setup_output_directory, get_asset_upload_path
)
from app.worker.common.expression import parse_expression
from app.worker.common.types import JSONEncoder
from app.worker.tasks.vector.i3dm.processes import i3dm_export


@celery.task(name="create_point_instance_3dtiles", base=PipelineDatabaseTask)
def create_point_instance_3dtiles(pipeline_extended):
    asset = pipeline_extended['asset']
    asset_id = asset['id']
    pipeline_id = pipeline_extended['id']
    table_name = get_asset_table_name(asset_id)
    geometry_column_name = 'geom'
    fid_column_name = 'gid'

    pipeline_config = pipeline_extended.get('data') or {}

    default_config = {
        'model': "model.glb",
        'rotation': 0,
        'scale': 1,
        'translate_z': 0,
        'max_features_per_tile': 5000,
        'max_geometric_error': 1000,
    }

    config = {**default_config, **pipeline_config}

    table = Table(table_name, MetaData(), autoload_with=engine_tasks)
    table_task_name = get_pipeline_table_name(pipeline_id)
    models = []

    with Session(engine_tasks) as session:
        session.exec(text(f"DROP TABLE IF EXISTS {table_task_name};"))
        session.exec(text(f"CREATE TABLE {table_task_name}(id serial PRIMARY KEY,{geometry_column_name} geometry(POINTZ, 4326),scale double precision,scale_non_uniform double precision[3],rotation double precision,model varchar,tags json);"))
        session.exec(text(f"CREATE INDEX {table_task_name}_geom_idx ON {table_task_name} USING GIST ({geometry_column_name});"))
        session.commit()

        statement = select(table).execution_options(yield_per=1000)
        for partition in session.execute(statement).partitions():
            for row in partition:
                row_obj = row._asdict()
                row_geometry = row_obj[geometry_column_name]
                as_geojson = session.exec(text(f"SELECT ST_AsGeoJSON('{row_geometry}')"))

                properties = []
                feature_properties = {}
                for key in row_obj:
                    if key not in [geometry_column_name, fid_column_name]:
                        properties.append({key: row_obj[key]})
                        feature_properties[key] = row_obj[key]

                geojson_string = as_geojson.first()[0]
                geometry = json.loads(geojson_string)
                coordinates = geometry['coordinates']
                z = coordinates[2] if coordinates[2] else 0

                feature = {'type': 'Feature', 'properties': feature_properties, 'geometry': geometry}
                translate_z = parse_expression('number', config['translate_z'], feature, default_config['translate_z'])

                coordinates = [coordinates[0], coordinates[1], z + translate_z]
                updated_geometry = {**geometry, 'coordinates': coordinates}
                updated_geometry_string = json.dumps(updated_geometry)
                properties_string = json.dumps(properties, cls=JSONEncoder)

                feature = {'type': 'Feature', 'properties': feature_properties, 'geometry': updated_geometry}
                model_scale = parse_expression('number', config['scale'], feature, default_config['scale'])
                model_rotation = parse_expression('number', config['rotation'], feature, default_config['rotation'])
                model_name = parse_expression('string', config['model'], feature, default_config['model'])

                if model_name not in models:
                    models.append(model_name)

                values = ",".join([f"ST_GeomFromGeoJSON('{updated_geometry_string}')", f"{model_scale}", f"{model_rotation}", f"'{model_name}'", f"'{properties_string}'"])
                session.exec(text(f"INSERT INTO {table_task_name}({geometry_column_name}, scale, rotation, model, tags) VALUES ({values});"))

        session.commit()

    output_paths = setup_output_directory(pipeline_id)

    max_geometric_error = parse_expression('number', config['max_geometric_error'], {}, default_config['max_geometric_error'])
    max_features_per_tile = parse_expression('number', config['max_features_per_tile'], {}, default_config['max_features_per_tile'])

    i3dm_export(table_task_name, output_paths['output_path_3dtiles'], max_geometric_error, geometry_column_name, max_features_per_tile, fid_column_name, table)

    with Session(engine_tasks) as session:
        session.exec(text(f"DROP TABLE IF EXISTS {table_task_name};"))
        session.commit()

    with Session(engine) as session:
        for model in models:
            statement = select(Asset).where(Asset.filename == model).limit(1)
            model_asset = session.exec(statement).first()
            model_asset_path = get_asset_upload_path(f"{model_asset.id}/index{model_asset.extension}")
            shutil.copy(model_asset_path, os.path.join(output_paths['output_path_3dtiles'], 'content', model))

    shutil.make_archive(output_paths['output_path_3dtiles_zip'], 'zip', output_paths['output_path_3dtiles'])

    return {
        'output': output_paths['output_path'],
        'tileset': output_paths['output_tileset'],
        'download': output_paths['output_tileset_zip']
    }
