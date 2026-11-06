import json
import os
import sys
import tempfile

from app.core.storage import get_storage, output_key
from app.models.config import MeshConfig
from app.worker.common.output import publish_tiles
from app.worker.common.utils import run_subprocess
from app.worker.main import celery, PipelineDatabaseTask
from app.worker.tasks.mesh.reader import mesh_bbox_from_key, resolve_obj


def _tiling_workers():
    """Tiles built in parallel inside one task; keep the service concurrency low instead."""
    value = os.environ.get("MESH_TILING_WORKERS")
    return int(value) if value else min(os.cpu_count() or 1, 4)


def _materialize(storage, key, scratch, name):
    dest = os.path.join(scratch, name)
    storage.download_file(key, dest)
    return dest


@celery.task(name="read_mesh_bbox")
def read_mesh_bbox(options):
    return mesh_bbox_from_key(get_storage(), options['key'])


def _resolve_input(pipeline_extended):
    key = (pipeline_extended.get('source') or {}).get('key')
    if not key:
        raise Exception("Mesh pipeline requires a bucket source")
    return key, '.zip' if key.lower().endswith('.zip') else os.path.splitext(key)[1]


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
