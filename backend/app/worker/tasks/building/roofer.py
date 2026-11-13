import glob
import os
import re

from pyproj import CRS

from app.worker.lib.cityjson import iter_cityjson
from app.worker.runtime.subprocess import run_subprocess

_SKIP = {"rf_t_run", "rf_ridgelines", "rf_pc_select", "rf_pc_source", "rf_pc_year"}
# "[time] [stdout] [info] [cropper] Tile 0: cropped 20 buildings"
_ROOFER_STEP = re.compile(
    r"^(?:\[[^\]]*\] ){3}(?:\[(?:cropper|reconstructor|sorter|serializer)\] (Tile .*)|(Cropping|Analysing) pointcloud)"
)


def _srs_argument(srs):
    epsg = srs.GetAuthorityCode(None) or CRS(srs.ExportToWkt()).to_epsg()
    return f"EPSG:{epsg}" if epsg else srs.ExportToWkt()


def _roofer_stage(line):
    match = _ROOFER_STEP.match(line)
    if not match:
        return None
    return f"Roofer: {match.group(1) or match.group(2).lower() + ' point cloud'}"


def run_roofer(footprints, clouds, srs, config, scratch):
    out = os.path.join(scratch, "roofer")
    cmd = [
        "roofer",
        f"--lod{config.lod.replace('.', '')}",
        "--srs",
        _srs_argument(srs),
        "--bld-class",
        str(config.building_class),
        "--grnd-class",
        str(config.ground_class),
        *clouds,
        footprints,
        out,
    ]
    # roofer writes roofer.log.json to its cwd
    result = run_subprocess(cmd, cwd=scratch, stage_of=_roofer_stage)
    if result.returncode != 0:
        raise Exception(
            f"Roofer failed with exit code {result.returncode}, see the job log"
        )
    paths = sorted(glob.glob(os.path.join(out, "*.city.jsonl")))
    if not paths:
        raise Exception(
            "Roofer wrote no buildings: check that the point cloud covers the footprints "
            "and has building and ground classes"
        )
    return paths


def read_roofer(paths, lod):
    """Buildings Roofer could not model have LoD 0 only and are left out."""
    objects = []
    for path in paths:
        for srs, props, polys in iter_cityjson(path, lod=float(lod)):
            objects.append(
                (srs, {k: v for k, v in props.items() if k not in _SKIP}, polys)
            )
    return objects
