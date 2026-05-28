import json
import shutil

from sqlmodel import Session, select
from app.core.db import engine
from app.models.task import Asset
from app.worker.main import celery, PipelineDatabaseTask, AssetDatabaseTask
from app.worker.common.utils import get_asset_upload_path, setup_output_directory
from app.worker.common.processes import identify_projection
from app.worker.tasks.pdal.processes import (
    pdal_metadata, pdal_stats, point_cloud_preview, process_las
)
from app.worker.tasks.py3dtiles.processes import py3dtiles_convert


@celery.task(name="inspect_pointcloud", base=AssetDatabaseTask)
def inspect_pointcloud(options):
    asset = options['asset']
    asset_id = asset['id']
    extension = asset['extension']

    asset_file_path = get_asset_upload_path(f"{asset_id}/index{extension}")

    metadata_json = pdal_metadata(asset_file_path)
    with open(get_asset_upload_path(f"{asset_id}/metadata.json"), 'w') as f:
        json.dump(metadata_json, f)

    stats_json = pdal_stats(asset_file_path)
    with open(get_asset_upload_path(f"{asset_id}/stats.json"), 'w') as f:
        json.dump(stats_json, f)

    epsg = identify_projection(metadata_json['metadata']['comp_spatialreference'])
    horizontal_epsg = identify_projection(metadata_json['metadata']['srs']['horizontal'])
    vertical_epsg = identify_projection(metadata_json['metadata']['srs']['vertical'])

    point_cloud_preview(asset_file_path, get_asset_upload_path(f"{asset_id}/sample.xyz"), metadata_json, stats_json)

    return {
        'asset_type': 'LAS',
        'geometry_type': 'PointCloud',
        'payload': {
            'metadata': True,
            'stats': True,
            'sample': True,
            'epsg': epsg,
            'horizontal_epsg': horizontal_epsg,
            'vertical_epsg': vertical_epsg,
        }
    }


@celery.task(name="create_point_cloud_3dtiles", base=PipelineDatabaseTask)
def create_point_cloud_3dtiles(pipeline_extended):
    pipeline_config = pipeline_extended.get('data') or {}

    default_config = {
        "colorization_image": '',
        "sample_radius": None,
        "to_ellipsoidal_height": False,
        "ground_classification": False,
        "geometric_error_scale_factor": 1,
    }

    config = {**default_config, **pipeline_config}

    asset = pipeline_extended['asset']
    pipeline_id = pipeline_extended['id']

    output_paths = setup_output_directory(pipeline_id)

    colorization_image = config['colorization_image'] or ''
    colorization_image_path = None
    if colorization_image:
        with Session(engine) as session:
            statement = select(Asset).where(Asset.filename == colorization_image).limit(1)
            image_asset = session.exec(statement).first()
            colorization_image_path = get_asset_upload_path(f"{image_asset.id}/index{image_asset.extension}")

    input_file = process_las(
        pipeline_id, asset,
        sample_radius=config['sample_radius'],
        to_ellipsoidal_height=config['to_ellipsoidal_height'],
        colorization_image=colorization_image_path,
        ground_classification=config['ground_classification']
    )

    crs_in = None
    if asset.get('upload_result'):
        crs_in = asset['upload_result'].get('horizontal_epsg') or asset['upload_result'].get('epsg')

    if not crs_in:
        raise Exception('Not recognized Point Cloud CRS')

    py3dtiles_convert(input_file, output_paths['output_path_3dtiles'], f'{crs_in}', config['geometric_error_scale_factor'])

    shutil.make_archive(output_paths['output_path_3dtiles_zip'], 'zip', output_paths['output_path_3dtiles'])

    return {
        'output': output_paths['output_path'],
        'tileset': output_paths['output_tileset'],
        'download': output_paths['output_tileset_zip']
    }
