import subprocess
import json
import os
import math
from pyproj import CRS
from app.worker.tasks.pointcloud.crs import resolve_epsg_codes_from_pdal_metadata
from app.worker.common.utils import run_subprocess


def pdal_metadata(file_path):
    result = run_subprocess(
        ['pdal', 'info', file_path, '--metadata'],
        capture_output=True,
    )
    return json.loads(result.stdout.decode("utf-8"))


def pdal_stats(file_path):
    result = run_subprocess(
        ['pdal', 'info', file_path, '--stats'],
        capture_output=True,
    )
    return json.loads(result.stdout.decode("utf-8"))


def detect_point_attributes(file_path):
    """Return (has_classification, has_intensity): include an attribute only when the
    cloud actually carries it with useful variation, not just a zeroed dimension."""
    try:
        stats = pdal_stats(file_path)
    except Exception:
        return False, False
    by_name = {s.get('name'): s for s in (stats.get('stats') or {}).get('statistic', [])}

    def varied(name):
        s = by_name.get(name)
        if not s:
            return False
        mn, mx = s.get('minimum'), s.get('maximum')
        return mn is not None and mx is not None and mn != mx

    cls = by_name.get('Classification') or {}
    # classified if values vary, or a single non-trivial class (not 0/1 = unclassified)
    has_classification = varied('Classification') or cls.get('minimum') not in (None, 0, 1)
    has_intensity = varied('Intensity')
    return has_classification, has_intensity


def point_cloud_preview(input_file_path, output_file_path, metadata, stats):
    pipeline = [{"filename": input_file_path, "type": 'readers.las'}]

    count = metadata['metadata']['count']
    if count > 500000:
        step = int(math.ceil(count / 500000))
        pipeline += [{"type": 'filters.decimation', "step": step}]

    statistic = stats['stats']['statistic']
    x = y = z = red = None
    for value in statistic:
        if value['name'] == 'X':
            x = value
        if value['name'] == 'Y':
            y = value
        if value['name'] == 'Z':
            z = value
        if value['name'] == 'Red':
            red = value

    size = [x['maximum'] - x['minimum'], y['maximum'] - y['minimum'], z['maximum'] - z['minimum']]
    center = [x['minimum'] + (size[0] / 2), y['minimum'] + (size[1] / 2), z['minimum'] + (size[2] / 2)]

    pipeline += [{"type": "filters.transformation", "matrix": f"1  0  0  {-center[0]}  0  1  0  {-center[1]}  0  0  1  {-center[2]}  0  0  0  1"}]

    if red:
        pipeline += [{"type": 'writers.text', "format": 'csv', "order": 'X,Y,Z,Red:0,Green:0,Blue:0', "keep_unspecified": False, "filename": output_file_path}]
    else:
        pipeline += [{"type": 'writers.text', "format": 'csv', "order": 'X,Y,Z', "keep_unspecified": False, "filename": output_file_path}]

    pipeline_sample_path = os.path.join(os.path.dirname(output_file_path), 'sample-pipeline.json')
    with open(pipeline_sample_path, "w") as f:
        json.dump(pipeline, f)

    res = run_subprocess(['pdal', 'pipeline', pipeline_sample_path], capture_output=True, text=True)

    if not os.path.isfile(output_file_path):
        print(res.stderr)
        raise Exception("Sample not created")


def resolve_asset_crs(asset):
    upload_result = asset.get('upload_result') or {}
    horizontal_epsg = upload_result.get('horizontal_epsg') or upload_result.get('epsg')
    vertical_epsg = upload_result.get('vertical_epsg')
    return horizontal_epsg, vertical_epsg


def resolve_crs_from_file(input_path):
    """Read horizontal/vertical EPSG straight from the point cloud, so a job can
    run from a bucket key with no pre-inspected Asset."""
    try:
        metadata_json = pdal_metadata(input_path)
        codes = resolve_epsg_codes_from_pdal_metadata(metadata_json['metadata'])
        return (codes.get('horizontal_epsg') or codes.get('epsg')), codes.get('vertical_epsg')
    except Exception:
        return None, None


def process_las(work_dir, input_path, sample_radius=None, to_ellipsoidal_height=False, horizontal_epsg=None, vertical_epsg=None, colorization_image=None, ground_classification=False):
    pipeline = []

    if sample_radius:
        pipeline += [{"type": 'filters.sample', "radius": sample_radius}]

    if to_ellipsoidal_height:
        if not horizontal_epsg:
            raise Exception('Not recognized Point Cloud horizontal CRS (required for ellipsoidal height conversion)')
        vepsg = vertical_epsg or 3855
        geodetic_crs = CRS(horizontal_epsg).geodetic_crs.to_epsg()
        pipeline += [{"type": 'filters.reprojection', "in_srs": f"EPSG:{horizontal_epsg}+{vepsg}", "out_srs": f"EPSG:{horizontal_epsg}+{geodetic_crs}", "error_on_failure": True}]

    if colorization_image:
        pipeline += [{"type": 'filters.colorization', "raster": colorization_image}]

    if ground_classification:
        pipeline += [
            {"type": "filters.assign", "assignment": "Classification[:]=0"},
            {"type": "filters.elm"},
            {"type": "filters.outlier"},
            {"type": "filters.smrf", "ignore": "Classification[7:7]"}
        ]

    if len(pipeline) == 0:
        return input_path

    output_processed_laz_path = os.path.join(work_dir, 'processed.laz')
    pipeline_process_path = os.path.join(work_dir, 'process.pipeline.json')

    pipeline = [{"filename": input_path, "type": 'readers.las'}] + pipeline + [{"type": 'writers.las', "filename": output_processed_laz_path, "compression": True}]

    with open(pipeline_process_path, "w") as f:
        json.dump(pipeline, f)

    res = run_subprocess(['pdal', 'pipeline', pipeline_process_path], capture_output=True, text=True)

    if not os.path.isfile(output_processed_laz_path):
        print(res.stderr)
        raise Exception("Processed LAS not created")

    return output_processed_laz_path
