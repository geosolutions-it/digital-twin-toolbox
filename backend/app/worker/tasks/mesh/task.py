import io
import json
import os
import sys
import zipfile

from app.core.celery_app import celery
from app.core.storage import get_storage, open_range
from app.models.config import MeshConfig
from app.worker.runtime.logs import log_stage
from app.worker.runtime.subprocess import run_subprocess
from app.worker.runtime.task import PipelineDatabaseTask, TaskContext
from app.worker.tasks.mesh.reader import bbox_from_lines, is_obj_candidate, resolve_obj


def _tiling_workers():
    """Tiles built in parallel inside one task; keep the service concurrency low instead."""
    value = os.environ.get("MESH_TILING_WORKERS")
    return int(value) if value else min(os.cpu_count() or 1, 4)


def mesh_bbox_from_key(storage, key):
    """Bbox of a bucket .obj or zipped .obj; a zip is read in place, textures untouched."""
    with open_range(storage, key) as raw:
        if not key.lower().endswith(".zip"):
            return bbox_from_lines(raw)
        with zipfile.ZipFile(raw) as archive:
            names = [n for n in archive.namelist() if is_obj_candidate(n)]
            if not names:
                raise FileNotFoundError("No .obj file found in the mesh archive")
            names.sort(key=lambda n: (n.count("/"), n))
            with archive.open(names[0]) as member:
                return bbox_from_lines(io.BufferedReader(member, buffer_size=4 << 20))


@celery.task(name="read_mesh_bbox")
def read_mesh_bbox(options):
    return mesh_bbox_from_key(get_storage(), options["key"])


@celery.task(name="create_mesh_3dtiles", base=PipelineDatabaseTask)
def create_mesh_3dtiles(pipeline_extended):
    with TaskContext(pipeline_extended, "Mesh", MeshConfig) as ctx:
        log_stage("Downloading mesh")
        local = ctx.download(ctx.source.key, "index")
        tiles_dir = ctx.path("tiles")
        params = {
            **ctx.config.model_dump(),
            "input_file": resolve_obj(local, ctx.scratch),
            "output_dir": tiles_dir,
            "workers": _tiling_workers(),
        }
        log_stage("Tiling mesh")
        run_subprocess(
            [sys.executable, "-m", "app.worker.tasks.mesh.tiler", json.dumps(params)],
            check=True,
        )
        return ctx.publish(tiles_dir, "tileset.json")
