import os
import struct

import numpy as np
from osgeo import osr

from app.core.celery_app import celery
from app.models.config import BuildingConfig
from app.worker.lib.features.city import tile_city_objects
from app.worker.lib.geo.ogr import open_layer, resolve_input, wgs84_transform
from app.worker.runtime.logs import log_stage
from app.worker.runtime.task import PipelineDatabaseTask, TaskContext
from app.worker.tasks.building.dtm import sink_to_dtm
from app.worker.tasks.building.roofer import read_roofer, run_roofer

_POINT_CLOUD_EXT = (".las", ".laz")
# keeps ground points around edge buildings
_TILE_MARGIN = 20.0
_LAS_HEADER = 227


def _las_bounds(storage, key):
    """(minx, miny, maxx, maxy) from the header, None if unreadable."""
    try:
        head = storage.read_range(key, 0, _LAS_HEADER)
    except Exception:
        return None
    if len(head) < _LAS_HEADER or head[:4] != b"LASF":
        return None
    maxx, minx, maxy, miny = struct.unpack_from("<4d", head, 179)
    return minx, miny, maxx, maxy


def _download_point_cloud(storage, key, scratch, extent):
    """extent is in the point cloud's CRS."""
    keys = (
        [k for k in storage.list(key) if k.lower().endswith(_POINT_CLOUD_EXT)]
        if key.endswith("/")
        else [key]
    )
    if not keys or not all(k.lower().endswith(_POINT_CLOUD_EXT) for k in keys):
        raise Exception(f"No LAS/LAZ point cloud at {key!r}")
    if len(keys) > 1:
        x0, y0, x1, y1 = (
            extent[0] - _TILE_MARGIN,
            extent[1] - _TILE_MARGIN,
            extent[2] + _TILE_MARGIN,
            extent[3] + _TILE_MARGIN,
        )
        bounds = {k: _las_bounds(storage, k) for k in keys}
        keys = [
            k
            for k, b in bounds.items()
            if b is None or (b[0] <= x1 and b[2] >= x0 and b[1] <= y1 and b[3] >= y0)
        ]
        if not keys:
            raise Exception(
                "No point cloud tile overlaps the footprints: check that both use the same CRS"
            )
    folder = os.path.join(scratch, "pointcloud")
    os.makedirs(folder, exist_ok=True)
    paths = []
    for i, k in enumerate(keys):
        dest = os.path.join(folder, f"{i}{os.path.splitext(k)[1].lower()}")
        storage.download_file(k, dest)
        paths.append(dest)
    return paths


@celery.task(name="create_building_3dtiles", base=PipelineDatabaseTask)
def create_building_3dtiles(pipeline_extended):
    with TaskContext(pipeline_extended, "Building", BuildingConfig) as ctx:
        config, storage, scratch = ctx.config, ctx.storage, ctx.scratch
        log_stage("Reading footprints")
        footprints = resolve_input(ctx.source.key, storage, scratch)
        ds, layer = open_layer(footprints)
        if layer.GetSpatialRef() is None:
            raise Exception("The footprints have no CRS: include the .prj file")
        srs = layer.GetSpatialRef().Clone()  # outlives the datasource
        srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        transform = wgs84_transform(layer, config.to_ellipsoidal_height)
        minx, maxx, miny, maxy = layer.GetExtent()
        del ds, layer

        log_stage("Downloading point cloud")
        clouds = _download_point_cloud(
            storage, config.point_cloud, scratch, (minx, miny, maxx, maxy)
        )
        log_stage(f"Roofer: starting on {len(clouds)} point cloud file(s)")
        jsonl = run_roofer(footprints, clouds, srs, config, scratch)
        log_stage("Reading buildings")
        objects = read_roofer(jsonl, config.lod)
        if not objects:
            raise Exception(f"No building reconstructed at LoD {config.lod}")
        if config.dtm:
            log_stage("Fitting walls to the DTM")
            sink_to_dtm(
                objects,
                ctx.download(config.dtm, "dtm"),
                srs.ExportToWkt(),
            )

        # Roofer's CityJSON cannot name a CRS given as WKT
        def project(_srs_name, pts):
            return np.array(transform.TransformPoints(pts))

        orthophoto = None
        if config.orthophoto:
            log_stage("Downloading orthophoto")
            orthophoto = ctx.download(config.orthophoto, "orthophoto")
        tiles_dir = ctx.path("tiles")
        log_stage(f"Tiling {len(objects)} buildings")
        tile_city_objects(
            objects,
            project,
            tiles_dir,
            config.max_tile_size_kb,
            orthophoto,
            config.texture_resolution,
        )
        artifacts = {
            f"buildings{'' if len(jsonl) == 1 else f'-{i}'}.city.jsonl": path
            for i, path in enumerate(jsonl)
        }
        return ctx.publish(tiles_dir, "tileset.json", artifacts)
