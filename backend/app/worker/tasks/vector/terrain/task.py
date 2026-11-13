"""Bucket-first terrain: a GeoTIFF -> quantized-mesh pyramid uploaded as a
Cesium terrain layer. No external binary, no PostGIS."""

import os
import tempfile

from app.core.storage import get_storage
from app.models.config import TerrainConfig
from app.worker.common.logs import log_stage
from app.worker.common.output import publish_tiles
from app.worker.common.task_input import task_output_base, task_source
from app.worker.main import PipelineDatabaseTask, celery
from app.worker.tasks.vector.terrain import preprocess
from app.worker.tasks.vector.terrain.qmesh.tiler import build_terrain


@celery.task(name="create_terrain_tiles", base=PipelineDatabaseTask)
def create_terrain_tiles(pipeline_extended):
    source = task_source(pipeline_extended, "Terrain")

    config = TerrainConfig(**(pipeline_extended.get("data") or {}))
    params = config.model_dump()

    storage = get_storage()
    out_base = task_output_base(pipeline_extended, source)

    with tempfile.TemporaryDirectory() as scratch:
        log_stage("Downloading DEM")
        src = preprocess.resolve_input(source.key, storage, scratch)
        log_stage("Reprojecting DEM")
        dem = preprocess.warp_to_wgs84(
            src, scratch, config.to_ellipsoidal_height, config.source_vertical_epsg
        )

        if config.water_key:
            log_stage("Downloading water mask")
            water = os.path.join(
                scratch, "water" + os.path.splitext(config.water_key)[1]
            )
            storage.download_file(config.water_key, water)
            params["water_path"] = water

        tiles_dir = os.path.join(scratch, "tiles")
        log_stage("Building terrain tiles")
        info = build_terrain(dem, tiles_dir, params)

        result = publish_tiles(storage, tiles_dir, out_base, "layer.json")

    return {**result, **info}
