import json
import os
import sys
import tempfile

from app.core.storage import get_storage, output_key, upload_key
from app.models.config import MeshConfig
from app.worker.common.output import publish_tiles
from app.worker.common.utils import run_subprocess
from app.worker.main import celery, PipelineDatabaseTask, AssetDatabaseTask
from app.worker.tasks.mesh.reader import estimate_mesh_bbox_from_obj, mesh_bbox_from_key, resolve_obj


def _tiling_workers():
    """Tiles built in parallel inside one task; keep the service concurrency low instead."""
    value = os.environ.get("MESH_TILING_WORKERS")
    return int(value) if value else min(os.cpu_count() or 1, 4)


def _materialize(storage, key, scratch, name):
    dest = os.path.join(scratch, name)
    storage.download_file(key, dest)
    return dest


@celery.task(name="inspect_mesh", base=AssetDatabaseTask)
def inspect_mesh(options):
    asset = options['asset']
    extension = asset['extension']
    storage = get_storage()

    with tempfile.TemporaryDirectory() as scratch:
        local = _materialize(storage, upload_key(f"{asset['id']}/index{extension}"), scratch, f"index{extension}")
        mesh_bbox = estimate_mesh_bbox_from_obj(resolve_obj(local, scratch))

    payload = {
        'metadata': False,
        'stats': False,
        'sample': False,
        'epsg': None,
        'horizontal_epsg': None,
        'vertical_epsg': None,
    }
    if mesh_bbox:
        payload['size'] = mesh_bbox['size']
        payload['offset'] = mesh_bbox['offset']

    return {'asset_type': 'Mesh', 'geometry_type': None, 'payload': payload}


@celery.task(name="read_mesh_bbox")
def read_mesh_bbox(options):
    return mesh_bbox_from_key(get_storage(), options['key'])


def _resolve_input(pipeline_extended):
    """Input is a direct bucket key (by-reference) or an uploaded asset."""
    source = pipeline_extended.get('source')
    if source and source.get('key'):
        key = source['key']
        return key, '.zip' if key.lower().endswith('.zip') else os.path.splitext(key)[1]
    asset = pipeline_extended['asset']
    return upload_key(f"{asset['id']}/index{asset['extension']}"), asset['extension']


@celery.task(name="create_mesh_3dtiles", base=PipelineDatabaseTask)
def create_mesh_3dtiles(pipeline_extended):
    config = MeshConfig(**(pipeline_extended.get('data') or {}))
    storage = get_storage()
    input_key, extension = _resolve_input(pipeline_extended)
    source = pipeline_extended.get('source') or {}
    out_base = source.get('output_base') or output_key(pipeline_extended['id'])

    with tempfile.TemporaryDirectory() as scratch:
        local = _materialize(storage, input_key, scratch, f"index{extension}")
        tiles_dir = os.path.join(scratch, 'tiles')
        params = {
            **config.model_dump(),
            'input_file': resolve_obj(local, scratch),
            'output_dir': tiles_dir,
            'workers': _tiling_workers(),
        }
        run_subprocess([sys.executable, '-m', 'app.worker.tasks.mesh.tiler', json.dumps(params)], check=True)
        return publish_tiles(storage, tiles_dir, out_base, 'tileset.json')
