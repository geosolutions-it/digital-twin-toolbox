import logging
import os
import tempfile

from app.core.storage import get_storage, output_key, output_url
from app.models.config import PointCloudConfig
from app.worker.common.logs import log_stage
from app.worker.main import PipelineDatabaseTask, celery
from app.worker.tasks.pointcloud.pdal.processes import (
    compute_auto_sample_radius,
    detect_point_attributes,
    process_las,
    resolve_crs_from_file,
)
from app.worker.tasks.pointcloud.py3dtiles.processes import py3dtiles_convert

logger = logging.getLogger(__name__)


def _materialize(storage, key, scratch, name):
    """Download a stored object to local scratch and return its path."""
    dest = os.path.join(scratch, name)
    storage.download_file(key, dest)
    return dest


def _resolve_colorization_path(storage, filename, scratch):
    if not filename or not storage.exists(filename):
        return None
    ext = os.path.splitext(filename)[1] or ".tif"
    return _materialize(storage, filename, scratch, f"colorization{ext}")


def _resolve_input(pipeline_extended):
    source = pipeline_extended.get("source") or {}
    key = source.get("key")
    if not key:
        raise Exception("Point cloud pipeline requires a bucket source")
    return key, source.get("extension") or os.path.splitext(key)[1]


def _resolve_crs(pipeline_extended, input_file):
    """CRS from an explicit source hint, else read from the file."""
    source = pipeline_extended.get("source") or {}
    if source.get("crs"):
        return source["crs"], source.get("vertical_crs")
    return resolve_crs_from_file(input_file)


@celery.task(name="create_point_cloud_3dtiles", base=PipelineDatabaseTask)
def create_point_cloud_3dtiles(pipeline_extended):
    config = PointCloudConfig(**(pipeline_extended.get("data") or {}))
    pipeline_id = pipeline_extended["id"]
    storage = get_storage()
    input_key, extension = _resolve_input(pipeline_extended)
    source = pipeline_extended.get("source") or {}
    out_base = source.get("output_base") or output_key(pipeline_id)

    with tempfile.TemporaryDirectory() as scratch:
        log_stage("Downloading point cloud")
        input_file = _materialize(storage, input_key, scratch, f"index{extension}")

        horizontal_epsg, vertical_epsg = _resolve_crs(pipeline_extended, input_file)
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
            colorization_image_path = _resolve_colorization_path(
                storage, config.colorization_image, scratch
            )
            if not colorization_image_path:
                raise Exception(
                    f"Colorization raster not found: {config.colorization_image!r}"
                )

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

        tiles_dir = os.path.join(scratch, "tiles")
        log_stage("Tiling with py3dtiles")
        py3dtiles_convert(
            processed_file, tiles_dir, f"{horizontal_epsg}", attributes=attributes
        )

        log_stage("Uploading tiles")
        storage.delete_prefix(f"{out_base}/tiles/")
        storage.upload_dir(tiles_dir, f"{out_base}/tiles")

    return {
        "output": out_base,
        "tileset": output_url(f"{out_base}/tiles/tileset.json"),
        "download": output_url(f"{out_base}/tiles/download.zip"),
        "sample_radius": sample_radius,
        "sample_radius_auto": config.sample_radius is None,
    }
