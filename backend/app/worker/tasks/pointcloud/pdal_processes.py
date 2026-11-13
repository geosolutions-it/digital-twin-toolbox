import json
import math
import os

import laspy
from pyproj import CRS

from app.worker.runtime.subprocess import run_subprocess
from app.worker.tasks.pointcloud.crs import resolve_epsg_codes_from_pdal_metadata

# With no radius given, auto-pick this percentile of per-point nearest-neighbor distance,
# thinning only the densest excess (near-duplicate points) down to the typical spacing.
AUTO_SAMPLE_PERCENTILE = 90


def pdal_metadata(file_path):
    result = run_subprocess(
        ["pdal", "info", file_path, "--metadata"],
        capture_output=True,
        log_stdout=False,
    )
    return json.loads(result.stdout.decode("utf-8"))


def pdal_stats(file_path):
    result = run_subprocess(
        ["pdal", "info", file_path, "--stats"],
        capture_output=True,
        log_stdout=False,
    )
    return json.loads(result.stdout.decode("utf-8"))


def detect_point_attributes(file_path, force_classification=False):
    """Return {laspy name: {"minimum", "maximum"}} for the attributes worth exporting:
    only when the cloud carries them with useful variation, not just a zeroed dimension."""
    try:
        stats = pdal_stats(file_path)
    except Exception:
        stats = {}
    by_name = {
        s.get("name"): s for s in (stats.get("stats") or {}).get("statistic", [])
    }

    def value_range(name):
        s = by_name.get(name) or {}
        mn, mx = s.get("minimum"), s.get("maximum")
        return None if mn is None or mx is None else {"minimum": mn, "maximum": mx}

    attributes = {}
    cls = value_range("Classification")
    if force_classification or (
        cls and (cls["minimum"] != cls["maximum"] or cls["minimum"] not in (0, 1))
    ):
        attributes["classification"] = cls or {"minimum": 0, "maximum": 255}
    intensity = value_range("Intensity")
    if intensity and intensity["minimum"] != intensity["maximum"]:
        attributes["intensity"] = intensity
    return attributes


def resolve_crs_from_file(input_path):
    """Horizontal/vertical EPSG read from the point cloud header."""
    try:
        metadata_json = pdal_metadata(input_path)
        codes = resolve_epsg_codes_from_pdal_metadata(metadata_json["metadata"])
        return (codes.get("horizontal_epsg") or codes.get("epsg")), codes.get(
            "vertical_epsg"
        )
    except Exception:
        return None, None


def _las_point_format(file_path):
    with laspy.open(file_path) as f:
        return f.header.point_format.id


def process_las(
    work_dir,
    input_path,
    sample_radius=None,
    to_ellipsoidal_height=False,
    horizontal_epsg=None,
    vertical_epsg=None,
    colorization_image=None,
    ground_classification=False,
):
    pipeline = []

    if sample_radius:
        pipeline += [{"type": "filters.sample", "radius": sample_radius}]

    if to_ellipsoidal_height:
        if not horizontal_epsg:
            raise Exception(
                "Not recognized Point Cloud horizontal CRS (required for ellipsoidal height conversion)"
            )
        vepsg = vertical_epsg or 3855
        geodetic_crs = CRS(horizontal_epsg).geodetic_crs.to_epsg()
        pipeline += [
            {
                "type": "filters.reprojection",
                "in_srs": f"EPSG:{horizontal_epsg}+{vepsg}",
                "out_srs": f"EPSG:{horizontal_epsg}+{geodetic_crs}",
                "error_on_failure": True,
            }
        ]

    if colorization_image:
        pipeline += [{"type": "filters.colorization", "raster": colorization_image}]

    if ground_classification:
        pipeline += [
            {"type": "filters.assign", "assignment": "Classification[:]=0"},
            {"type": "filters.elm"},
            {"type": "filters.outlier"},
            {"type": "filters.smrf", "ignore": "Classification[7:7]"},
        ]

    if len(pipeline) == 0 and _las_point_format(input_path) >= 6:
        return input_path

    output_processed_laz_path = os.path.join(work_dir, "processed.laz")
    pipeline_process_path = os.path.join(work_dir, "process.pipeline.json")

    # LAS 1.4 format 7 (RGB): full-byte classification, which py3dtiles exports as "classification"
    writer = {
        "type": "writers.las",
        "filename": output_processed_laz_path,
        "compression": True,
        "minor_version": 4,
        "dataformat_id": 7,
    }
    pipeline = [{"filename": input_path, "type": "readers.las"}] + pipeline + [writer]

    with open(pipeline_process_path, "w") as f:
        json.dump(pipeline, f)

    run_subprocess(["pdal", "pipeline", pipeline_process_path])

    if not os.path.isfile(output_processed_laz_path):
        raise Exception("Processed LAS not created")

    return output_processed_laz_path


def compute_auto_sample_radius(work_dir, input_path):
    """Estimate a sample radius from the cloud's nearest-neighbor spacing (computed on the
    full cloud, output decimated for the percentile). Returns a radius in CRS units or None."""
    nn_csv = os.path.join(work_dir, "nndistance.csv")
    pipeline = [
        {"filename": input_path, "type": "readers.las"},
        {"type": "filters.nndistance", "mode": "kth", "k": 1},
        {"type": "filters.decimation", "step": 25},
        {
            "type": "writers.text",
            "format": "csv",
            "order": "NNDistance",
            "keep_unspecified": False,
            "filename": nn_csv,
        },
    ]
    pipeline_path = os.path.join(work_dir, "nndistance.pipeline.json")
    with open(pipeline_path, "w") as f:
        json.dump(pipeline, f)

    run_subprocess(["pdal", "pipeline", pipeline_path])
    if not os.path.isfile(nn_csv):
        return None

    values = []
    with open(nn_csv) as f:
        next(f, None)
        for line in f:
            try:
                v = float(line.strip())
            except ValueError:
                continue
            if v > 0 and math.isfinite(v):
                values.append(v)
    if not values:
        return None

    values.sort()
    rank = int(round((AUTO_SAMPLE_PERCENTILE / 100.0) * (len(values) - 1)))
    rank = max(0, min(len(values) - 1, rank))
    return values[rank]
