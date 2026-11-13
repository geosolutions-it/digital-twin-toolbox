import glob
import os
import re
import struct
import tempfile

import numpy as np
from osgeo import gdal, osr
from pyproj import CRS

from app.core.storage import get_storage, output_key
from app.models.config import BuildingConfig
from app.worker.common.logs import log_stage
from app.worker.common.output import publish_tiles
from app.worker.common.utils import run_subprocess
from app.worker.main import PipelineDatabaseTask, celery
from app.worker.tasks.vector.citygml.cityjson import iter_cityjson
from app.worker.tasks.vector.citygml.task import tile_city_objects
from app.worker.tasks.vector.source import open_layer, resolve_input, wgs84_transform

gdal.UseExceptions()

_POINT_CLOUD_EXT = (".las", ".laz")
# keeps ground points around edge buildings
_TILE_MARGIN = 20.0
_LAS_HEADER = 227
_SKIP = {"rf_t_run", "rf_ridgelines", "rf_pc_select", "rf_pc_source", "rf_pc_year"}
# "[time] [stdout] [info] [cropper] Tile 0: cropped 20 buildings"
_ROOFER_STEP = re.compile(
    r"^(?:\[[^\]]*\] ){3}(?:\[(?:cropper|reconstructor|sorter|serializer)\] (Tile .*)|(Cropping|Analysing) pointcloud)"
)


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
    keys = [k for k in storage.list(key) if k.lower().endswith(_POINT_CLOUD_EXT)] if key.endswith("/") else [key]
    if not keys or not all(k.lower().endswith(_POINT_CLOUD_EXT) for k in keys):
        raise Exception(f"No LAS/LAZ point cloud at {key!r}")
    if len(keys) > 1:
        x0, y0, x1, y1 = extent[0] - _TILE_MARGIN, extent[1] - _TILE_MARGIN, extent[2] + _TILE_MARGIN, extent[3] + _TILE_MARGIN
        bounds = {k: _las_bounds(storage, k) for k in keys}
        keys = [k for k, b in bounds.items() if b is None or (b[0] <= x1 and b[2] >= x0 and b[1] <= y1 and b[3] >= y0)]
        if not keys:
            raise Exception("No point cloud tile overlaps the footprints: check that both use the same CRS")
    folder = os.path.join(scratch, "pointcloud")
    os.makedirs(folder, exist_ok=True)
    paths = []
    for i, k in enumerate(keys):
        dest = os.path.join(folder, f"{i}{os.path.splitext(k)[1].lower()}")
        storage.download_file(k, dest)
        paths.append(dest)
    return paths


def _download(storage, key, scratch, name):
    dest = os.path.join(scratch, name + os.path.splitext(key)[1].lower())
    storage.download_file(key, dest)
    return dest


def _srs_argument(srs):
    epsg = srs.GetAuthorityCode(None) or CRS(srs.ExportToWkt()).to_epsg()
    return f"EPSG:{epsg}" if epsg else srs.ExportToWkt()


def _roofer_stage(line):
    match = _ROOFER_STEP.match(line)
    if not match:
        return None
    return f"Roofer: {match.group(1) or match.group(2).lower() + ' point cloud'}"


def _run_roofer(footprints, clouds, srs, config, scratch):
    out = os.path.join(scratch, "roofer")
    cmd = ["roofer", f"--lod{config.lod.replace('.', '')}", "--srs", _srs_argument(srs),
           "--bld-class", str(config.building_class), "--grnd-class", str(config.ground_class),
           *clouds, footprints, out]
    # roofer writes roofer.log.json to its cwd
    result = run_subprocess(cmd, cwd=scratch, stage_of=_roofer_stage)
    if result.returncode != 0:
        raise Exception(f"Roofer failed with exit code {result.returncode}, see the job log")
    paths = sorted(glob.glob(os.path.join(out, "*.city.jsonl")))
    if not paths:
        raise Exception("Roofer wrote no buildings: check that the point cloud covers the footprints "
                        "and has building and ground classes")
    return paths


def sink_to_dtm(objects, dtm_path, src_wkt, sink=0.3):
    """Roofer bases are flat, so downhill walls float; the DTM must share the point cloud's datum."""
    ds = gdal.Open(dtm_path)
    band = ds.GetRasterBand(1)
    nodata = band.GetNoDataValue()
    src = osr.SpatialReference()
    src.ImportFromWkt(src_wkt)
    dst = osr.SpatialReference()
    dst.ImportFromWkt(ds.GetProjection())
    for s in (src, dst):
        s.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    to_dtm = osr.CoordinateTransformation(src, dst)
    inv = gdal.InvGeoTransform(ds.GetGeoTransform())
    bases = []
    for _, _, polys in objects:
        rings = [r for poly in polys for r in poly]
        zmin = min(float(r[:, 2].min()) for r in rings)
        base = [r[:, 2] < zmin + 0.05 for r in rings]
        pts = np.array(to_dtm.TransformPoints(np.concatenate([r[m, :2] for r, m in zip(rings, base, strict=True)])))
        col = np.floor(inv[0] + inv[1] * pts[:, 0] + inv[2] * pts[:, 1]).astype(int)
        row = np.floor(inv[3] + inv[4] * pts[:, 0] + inv[5] * pts[:, 1]).astype(int)
        bases.append((rings, base, zmin, col, row))
    if not bases:
        return
    # only the window under the buildings: a city-wide DTM does not fit in memory
    c0 = max(min(b[3].min() for b in bases), 0)
    r0 = max(min(b[4].min() for b in bases), 0)
    c1 = min(max(b[3].max() for b in bases) + 1, ds.RasterXSize)
    r1 = min(max(b[4].max() for b in bases) + 1, ds.RasterYSize)
    if c1 <= c0 or r1 <= r0:
        return
    data = band.ReadAsArray(int(c0), int(r0), int(c1 - c0), int(r1 - r0)).astype(np.float64)
    for rings, base, zmin, col, row in bases:
        inside = (col >= c0) & (col < c1) & (row >= r0) & (row < r1)
        z = data[row[inside] - r0, col[inside] - c0]
        keep = np.isfinite(z)
        if nodata is not None:
            keep &= z != nodata
        z = z[keep]
        if not len(z):
            continue
        ground = min(float(z.min()), zmin) - sink
        for r, m in zip(rings, base, strict=True):
            r[m, 2] = ground


def read_roofer(paths, lod):
    """Buildings Roofer could not model have LoD 0 only and are left out."""
    objects = []
    for path in paths:
        for srs, props, polys in iter_cityjson(path, lod=float(lod)):
            objects.append((srs, {k: v for k, v in props.items() if k not in _SKIP}, polys))
    return objects


@celery.task(name="create_building_3dtiles", base=PipelineDatabaseTask)
def create_building_3dtiles(pipeline_extended):
    source = pipeline_extended.get("source") or {}
    if not source.get("key"):
        raise Exception("Building pipeline requires a footprint file as source")
    config = BuildingConfig(**(pipeline_extended.get("data") or {}))
    storage = get_storage()
    out_base = source.get("output_base") or output_key(pipeline_extended["id"])

    with tempfile.TemporaryDirectory() as scratch:
        log_stage("Reading footprints")
        footprints = resolve_input(source, storage, scratch)
        ds, layer = open_layer(footprints)
        if layer.GetSpatialRef() is None:
            raise Exception("The footprints have no CRS: include the .prj file")
        srs = layer.GetSpatialRef().Clone()  # outlives the datasource
        srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        transform = wgs84_transform(layer, config.to_ellipsoidal_height)
        minx, maxx, miny, maxy = layer.GetExtent()
        del ds, layer

        log_stage("Downloading point cloud")
        clouds = _download_point_cloud(storage, config.point_cloud, scratch, (minx, miny, maxx, maxy))
        log_stage(f"Roofer: starting on {len(clouds)} point cloud file(s)")
        jsonl = _run_roofer(footprints, clouds, srs, config, scratch)
        log_stage("Reading buildings")
        objects = read_roofer(jsonl, config.lod)
        if not objects:
            raise Exception(f"No building reconstructed at LoD {config.lod}")
        if config.dtm:
            log_stage("Fitting walls to the DTM")
            sink_to_dtm(objects, _download(storage, config.dtm, scratch, "dtm"), srs.ExportToWkt())

        # Roofer's CityJSON cannot name a CRS given as WKT
        def project(_srs_name, pts):
            return np.array(transform.TransformPoints(pts))

        if config.orthophoto:
            log_stage("Downloading orthophoto")
        orthophoto = _download(storage, config.orthophoto, scratch, "orthophoto") if config.orthophoto else None
        tiles_dir = os.path.join(scratch, "tiles")
        log_stage(f"Tiling {len(objects)} buildings")
        tile_city_objects(objects, project, tiles_dir, config.max_tile_size_kb, orthophoto,
                          config.texture_resolution)
        artifacts = {f"buildings{'' if len(jsonl) == 1 else f'-{i}'}.city.jsonl": path for i, path in enumerate(jsonl)}
        return publish_tiles(storage, tiles_dir, out_base, "tileset.json", artifacts)
