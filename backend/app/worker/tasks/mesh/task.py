import json
import os
import sys
import tempfile

from app.core.storage import get_storage
from app.models.config import MeshConfig
from app.worker.common.logs import log_stage
from app.worker.common.output import publish_tiles
from app.worker.common.task_input import task_output_base, task_source
from app.worker.common.utils import run_subprocess
from app.worker.main import PipelineDatabaseTask, celery
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
    return mesh_bbox_from_key(get_storage(), options["key"])


def _extension(key):
    return ".zip" if key.lower().endswith(".zip") else os.path.splitext(key)[1]


@celery.task(name="create_mesh_3dtiles", base=PipelineDatabaseTask)
def create_mesh_3dtiles(pipeline_extended):
    config = MeshConfig(**(pipeline_extended.get("data") or {}))
    storage = get_storage()
    source = task_source(pipeline_extended, "Mesh")
    input_key, extension = source.key, _extension(source.key)
    out_base = task_output_base(pipeline_extended, source)

    with tempfile.TemporaryDirectory() as scratch:
        log_stage("Downloading mesh")
        local = _materialize(storage, input_key, scratch, f"index{extension}")
        tiles_dir = os.path.join(scratch, "tiles")
        params = {
            **config.model_dump(),
            "input_file": resolve_obj(local, scratch),
            "output_dir": tiles_dir,
            "workers": _tiling_workers(),
        }
        log_stage("Tiling mesh")
        run_subprocess(
            [sys.executable, "-m", "app.worker.tasks.mesh.tiler", json.dumps(params)],
            check=True,
        )
        return publish_tiles(storage, tiles_dir, out_base, "tileset.json")
