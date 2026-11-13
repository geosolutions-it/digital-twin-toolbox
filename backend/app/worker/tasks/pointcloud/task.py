import logging
import os

from app.core.celery_app import celery
from app.models.config import PointCloudConfig
from app.worker.runtime.logs import log_stage
from app.worker.runtime.task import PipelineDatabaseTask, TaskContext
from app.worker.tasks.pointcloud.pdal_processes import (
    compute_auto_sample_radius,
    detect_point_attributes,
    process_las,
    resolve_crs_from_file,
)
from app.worker.tasks.pointcloud.py3dtiles_processes import py3dtiles_convert

logger = logging.getLogger(__name__)


@celery.task(name="create_point_cloud_3dtiles", base=PipelineDatabaseTask)
def create_point_cloud_3dtiles(pipeline_extended):
    with TaskContext(pipeline_extended, "Point cloud", PointCloudConfig) as ctx:
        config, scratch = ctx.config, ctx.scratch
        log_stage("Downloading point cloud")
        input_file = ctx.download(
            ctx.source.key, "index" + (ctx.source.extension or "")
        )

        horizontal_epsg, vertical_epsg = resolve_crs_from_file(input_file)
        # some clouds ship without a CRS in the header: fall back to the one set in the config
        if not horizontal_epsg and config.horizontal_epsg:
            horizontal_epsg = config.horizontal_epsg
            vertical_epsg = vertical_epsg or config.vertical_epsg
        if not horizontal_epsg:
            raise Exception(
                "Point cloud has no CRS. Set its EPSG code in the config and re-run."
            )

        colorization_image_path = None
        if config.colorization_image:
            log_stage("Downloading colorization raster")
            key = config.colorization_image
            if not ctx.storage.exists(key):
                raise Exception(f"Colorization raster not found: {key!r}")
            ext = os.path.splitext(key)[1].lower() or ".tif"
            colorization_image_path = ctx.download(key, "colorization" + ext)

        # no radius given: auto-pick one from the cloud's spacing to drop redundant points
        sample_radius = config.sample_radius
        if sample_radius is None:
            log_stage("Measuring point spacing")
            sample_radius = compute_auto_sample_radius(scratch, input_file)
            logger.info("Auto sample radius: %s", sample_radius)

        log_stage("Processing with PDAL")
        processed_file = process_las(
            scratch,
            input_file,
            sample_radius=sample_radius,
            to_ellipsoidal_height=config.to_ellipsoidal_height,
            horizontal_epsg=horizontal_epsg,
            vertical_epsg=vertical_epsg,
            colorization_image=colorization_image_path,
            ground_classification=config.ground_classification,
        )

        attributes = detect_point_attributes(
            processed_file, force_classification=config.ground_classification
        )

        tiles_dir = ctx.path("tiles")
        log_stage("Tiling with py3dtiles")
        py3dtiles_convert(
            processed_file, tiles_dir, f"{horizontal_epsg}", attributes=attributes
        )

        return {
            **ctx.publish(tiles_dir, "tileset.json"),
            "sample_radius": sample_radius,
            "sample_radius_auto": config.sample_radius is None,
        }
