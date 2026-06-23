import os
import json
import errno
import shutil
import zipfile

from celery.exceptions import Reject
from app.worker.main import celery, AssetDatabaseTask
from app.worker.common.utils import get_asset_upload_path, setup_output_directory
import app.worker.tasks.photogrammetry.images_to_sparse_reconstruction as images_to_sparse_reconstruction
import app.worker.tasks.photogrammetry.sparse_reconstruction_to_dense_point_cloud as sparse_reconstruction_to_dense_point_cloud
import app.worker.tasks.photogrammetry.create_mesh as create_mesh
import app.worker.tasks.photogrammetry.create_texture as create_texture
from app.worker.tasks.photogrammetry.utils import build_params
from app.worker.tasks.photogrammetry.geo import transform_extent_to_local
# Tiling (bpy) and denoise (pdal) run on their own workers; chained in pipelines/photogrammetry.py.


DEFAULT_CONFIG = {
    "stage": 'all',
    "force_delete": False,
    "feature_process_size": 2048,
    "depthmap_resolution": 2048,
    "auto_resolutions_computation": False,
    "processes": 1,
    "read_processes": 4,
    "depthmap_processes": 1,
    'texture_image_resolution': 4096,
    'texture_image_processes': 1,
}


@celery.task(name="inspect_photogrammetry", base=AssetDatabaseTask)
def inspect_photogrammetry(options):
    return {
        'asset_type': 'Photogrammetry',
        'geometry_type': None,
        'payload': {'metadata': False, 'stats': False, 'sample': False, 'epsg': None, 'horizontal_epsg': None, 'vertical_epsg': None}
    }


def _prepare_process_dir(pipeline_extended):
    """Extract uploaded images into the shared process dir (idempotent)."""
    asset = pipeline_extended.get('asset')
    asset_id = asset.get('id')
    asset_extension = asset.get('extension')
    asset_file_path = get_asset_upload_path(f"{asset_id}/index{asset_extension}")

    output_paths = setup_output_directory(pipeline_extended.get('id'))
    process_dir = f"{output_paths['output_path']}/process"
    config = {**DEFAULT_CONFIG, **(pipeline_extended.get('data') or {})}

    if config.get('force_delete'):
        shutil.rmtree(process_dir, ignore_errors=True)

    if not os.path.exists(process_dir):
        images_dir = f"{process_dir}/images"
        os.makedirs(images_dir, exist_ok=True)
        with zipfile.ZipFile(asset_file_path, 'r') as zip_ref:
            zip_ref.extractall(images_dir)
        with open(os.path.join(images_dir, "asset_info.txt"), "w") as f:
            f.write(f"{asset.get('filename')}")

    return process_dir, config


def _ensure_context(payload):
    """Normalize input to a context (head gets pipeline_extended, mid-chain gets the context)."""
    if isinstance(payload, dict) and 'process_dir' in payload:
        return payload
    process_dir, config = _prepare_process_dir(payload)
    return {'pipeline_extended': payload, 'process_dir': process_dir, 'config': config}


def _run_stage(self, payload, stage_run):
    """Run one OpenSfM stage with the shared OOM handling, forwarding the context."""
    try:
        ctx = _ensure_context(payload)
        stage_run(ctx['process_dir'], {**ctx['config']})
        return ctx
    except MemoryError as exc:
        raise Reject(exc, requeue=False)
    except OSError as exc:
        if exc.errno == errno.ENOMEM:
            raise Reject(exc, requeue=False)
        raise self.retry(exc=exc, countdown=10)
    except Exception as exc:
        raise self.retry(exc=exc, countdown=10)


# One OpenSfM stage per task; stage selection lives in pipelines/photogrammetry.py.
@celery.task(name="photogrammetry_images_to_sparse", bind=True, acks_late=True, max_retries=1)
def photogrammetry_images_to_sparse(self, payload):
    return _run_stage(self, payload, images_to_sparse_reconstruction.run)


@celery.task(name="photogrammetry_sparse_to_dense", bind=True, acks_late=True, max_retries=1)
def photogrammetry_sparse_to_dense(self, payload):
    return _run_stage(self, payload, sparse_reconstruction_to_dense_point_cloud.run)


@celery.task(name="photogrammetry_create_mesh", bind=True, acks_late=True, max_retries=1)
def photogrammetry_create_mesh(self, payload):
    def run(process_dir, config):
        create_mesh.run(build_params(process_dir, config))
    return _run_stage(self, payload, run)


def _build_tile_payload(ctx):
    """Build the generic tile payload: origin from reference_lla + optional crop bbox."""
    process_dir = ctx['process_dir']
    config = ctx['config']
    # no GPS -> no reference_lla.json: default origin to 0,0,0 instead of crashing
    reference_lla = {}
    reference_lla_path = os.path.join(process_dir, 'reference_lla.json')
    if os.path.exists(reference_lla_path):
        with open(reference_lla_path, 'r') as f:
            reference_lla = json.load(f)

    tile_config = {
        'latitude': reference_lla.get('latitude', 0),
        'longitude': reference_lla.get('longitude', 0),
        'altitude': reference_lla.get('altitude', 0),
        'decimate_last_depth_level': True,
    }
    for key in ('depth', 'tile_faces_target', 'texture_image_size', 'max_geometric_error', 'decimate_last_depth_level'):
        if key in config:
            tile_config[key] = config[key]

    bbox = None
    if reference_lla and config.get('extent_mesh'):
        bbox = transform_extent_to_local(reference_lla, config.get('extent_mesh'), config.get('projection'))

    return {
        'pipeline_extended': ctx['pipeline_extended'],
        'input_file': os.path.join(process_dir, 'textured', 'mesh.obj'),
        'config': tile_config,
        'bbox': bbox,
    }


@celery.task(name="photogrammetry_create_texture", bind=True, acks_late=True, max_retries=1)
def photogrammetry_create_texture(self, payload):
    try:
        ctx = _ensure_context(payload)
        create_texture.run(build_params(ctx['process_dir'], {**ctx['config']}))
        return _build_tile_payload(ctx)
    except MemoryError as exc:
        raise Reject(exc, requeue=False)
    except OSError as exc:
        if exc.errno == errno.ENOMEM:
            raise Reject(exc, requeue=False)
        raise self.retry(exc=exc, countdown=10)
    except Exception as exc:
        raise self.retry(exc=exc, countdown=10)


@celery.task(name="photogrammetry_resolve_tile_input")
def photogrammetry_resolve_tile_input(payload):
    """Head for a tiling-only resume: rebuild the tile payload without re-texturing."""
    return _build_tile_payload(_ensure_context(payload))
