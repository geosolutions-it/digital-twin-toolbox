import json
import os
import shutil
import tempfile

from sqlmodel import Session, select
from app.core.db import engine
from app.core.config import settings
from app.core.storage import get_storage, upload_key, output_key
from app.models.task import Asset
from app.models.config import PointCloudConfig
from app.worker.main import celery, PipelineDatabaseTask, AssetDatabaseTask
from app.worker.tasks.pointcloud.crs import resolve_epsg_codes_from_pdal_metadata
from app.worker.tasks.pointcloud.pdal.processes import (
    pdal_metadata, pdal_stats, point_cloud_preview, process_las, resolve_asset_crs,
    detect_point_attributes, resolve_crs_from_file,
)
from app.worker.tasks.pointcloud.py3dtiles.processes import py3dtiles_convert


def _materialize(storage, key, scratch, name):
    """Download a stored object to local scratch and return its path."""
    dest = os.path.join(scratch, name)
    storage.download_file(key, dest)
    return dest


@celery.task(name="inspect_pointcloud", base=AssetDatabaseTask)
def inspect_pointcloud(options):
    asset = options['asset']
    asset_id = asset['id']
    extension = asset['extension']

    storage = get_storage()

    with tempfile.TemporaryDirectory() as scratch:
        asset_file_path = _materialize(
            storage, upload_key(f"{asset_id}/index{extension}"), scratch, f"index{extension}"
        )

        metadata_json = pdal_metadata(asset_file_path)
        metadata_path = os.path.join(scratch, 'metadata.json')
        with open(metadata_path, 'w') as f:
            json.dump(metadata_json, f)
        storage.upload_file(metadata_path, upload_key(f"{asset_id}/metadata.json"))

        stats_json = pdal_stats(asset_file_path)
        stats_path = os.path.join(scratch, 'stats.json')
        with open(stats_path, 'w') as f:
            json.dump(stats_json, f)
        storage.upload_file(stats_path, upload_key(f"{asset_id}/stats.json"))

        crs_codes = resolve_epsg_codes_from_pdal_metadata(metadata_json['metadata'])
        epsg = crs_codes['epsg']
        horizontal_epsg = crs_codes['horizontal_epsg']
        vertical_epsg = crs_codes['vertical_epsg']

        sample_path = os.path.join(scratch, 'sample.xyz')
        point_cloud_preview(asset_file_path, sample_path, metadata_json, stats_json)
        storage.upload_file(sample_path, upload_key(f"{asset_id}/sample.xyz"))

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


def _resolve_colorization_path(storage, filename, scratch):
    with Session(engine) as session:
        statement = select(Asset).where(Asset.filename == filename).limit(1)
        image_asset = session.exec(statement).first()
    if not image_asset:
        return None
    return _materialize(
        storage,
        upload_key(f"{image_asset.id}/index{image_asset.extension}"),
        scratch,
        f"colorization{image_asset.extension}",
    )


def _resolve_input(pipeline_extended):
    """Input is a direct bucket key (batch/by-reference) or an uploaded asset."""
    source = pipeline_extended.get('source')
    if source and source.get('key'):
        key = source['key']
        return key, source.get('extension') or os.path.splitext(key)[1]
    asset = pipeline_extended.get('asset') or {}
    ext = asset['extension']
    return upload_key(f"{asset['id']}/index{ext}"), ext


def _resolve_crs(pipeline_extended, input_file):
    """CRS from a pre-inspected asset, an explicit source hint, or read in-job from the file."""
    asset = pipeline_extended.get('asset')
    if asset:
        h, v = resolve_asset_crs(asset)
        if h:
            return h, v
    source = pipeline_extended.get('source') or {}
    if source.get('crs'):
        return source['crs'], source.get('vertical_crs')
    return resolve_crs_from_file(input_file)


@celery.task(name="create_point_cloud_3dtiles", base=PipelineDatabaseTask)
def create_point_cloud_3dtiles(pipeline_extended):
    config = PointCloudConfig(**(pipeline_extended.get('data') or {}))
    pipeline_id = pipeline_extended['id']
    storage = get_storage()
    input_key, extension = _resolve_input(pipeline_extended)

    with tempfile.TemporaryDirectory() as scratch:
        input_file = _materialize(storage, input_key, scratch, f"index{extension}")

        horizontal_epsg, vertical_epsg = _resolve_crs(pipeline_extended, input_file)
        if not horizontal_epsg:
            raise Exception('Not recognized Point Cloud CRS')

        colorization_image_path = None
        if config.colorization_image:
            colorization_image_path = _resolve_colorization_path(
                storage, config.colorization_image, scratch
            )

        processed_file = process_las(
            scratch, input_file,
            sample_radius=config.sample_radius,
            to_ellipsoidal_height=config.to_ellipsoidal_height,
            horizontal_epsg=horizontal_epsg, vertical_epsg=vertical_epsg,
            colorization_image=colorization_image_path,
            ground_classification=config.ground_classification,
        )

        has_classification, has_intensity = detect_point_attributes(processed_file)
        if config.ground_classification:
            has_classification = True

        tiles_dir = os.path.join(scratch, 'tiles')
        py3dtiles_convert(
            processed_file, tiles_dir, f'{horizontal_epsg}',
            include_classification=has_classification, include_intensity=has_intensity,
        )

        zip_base = os.path.join(scratch, 'download')
        shutil.make_archive(zip_base, 'zip', tiles_dir)

        storage.delete_prefix(output_key(pipeline_id, 'tiles'))
        storage.upload_dir(tiles_dir, output_key(pipeline_id, 'tiles'))
        storage.upload_file(zip_base + '.zip', output_key(pipeline_id, 'download.zip'))

    base = settings.API_V1_STR
    return {
        'output': output_key(pipeline_id),
        'tileset': f"{base}/output/{pipeline_id}/tiles/tileset.json",
        'download': f"{base}/output/{pipeline_id}/download.zip",
    }
