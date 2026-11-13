"""Bucket-first terrain: a GeoTIFF -> quantized-mesh pyramid uploaded as a
Cesium terrain layer. No external binary, no PostGIS."""

from app.core.celery_app import celery
from app.models.config import TerrainConfig
from app.worker.runtime.logs import log_stage
from app.worker.runtime.task import PipelineDatabaseTask, TaskContext
from app.worker.tasks.terrain import dem
from app.worker.tasks.terrain.qmesh.tiler import build_terrain


@celery.task(name="create_terrain_tiles", base=PipelineDatabaseTask)
def create_terrain_tiles(pipeline_extended):
    with TaskContext(pipeline_extended, "Terrain", TerrainConfig) as ctx:
        config = ctx.config
        params = config.model_dump()
        log_stage("Downloading DEM")
        src = ctx.download(ctx.source.key, "dem")
        log_stage("Reprojecting DEM")
        warped = dem.warp_to_wgs84(
            src, ctx.scratch, config.height_reference, config.vertical_epsg
        )

        if config.water_key:
            log_stage("Downloading water mask")
            params["water_path"] = ctx.download(config.water_key, "water")

        tiles_dir = ctx.path("tiles")
        log_stage("Building terrain tiles")
        info = build_terrain(warped, tiles_dir, params)

        return {**ctx.publish(tiles_dir, "layer.json"), **info}
