import subprocess
import json
import os
import math
from pyproj import CRS
from app.worker.tasks.pointcloud.crs import resolve_epsg_codes_from_pdal_metadata
from app.worker.common.utils import get_asset_upload_path, run_subprocess


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

    if horizontal_epsg is None or vertical_epsg is None:
        metadata_path = get_asset_upload_path(f"{asset['id']}/metadata.json")
        if os.path.isfile(metadata_path):
            with open(metadata_path) as f:
                metadata_json = json.load(f)
            metadata = metadata_json.get('metadata', metadata_json)
            crs_codes = resolve_epsg_codes_from_pdal_metadata(metadata)
            if horizontal_epsg is None:
                horizontal_epsg = crs_codes['horizontal_epsg'] or crs_codes['epsg']
            if vertical_epsg is None:
                vertical_epsg = crs_codes['vertical_epsg']

    return horizontal_epsg, vertical_epsg


def process_las(pipeline_id, asset, sample_radius=None, to_ellipsoidal_height=False, colorization_image='', ground_classification=False):
    asset_upload_path = get_asset_upload_path(f"{asset['id']}/index{asset['extension']}")
    pipeline = []

    if sample_radius:
        pipeline += [{"type": 'filters.sample', "radius": sample_radius}]

    if to_ellipsoidal_height:
        horizontal_epsg, vertical_epsg = resolve_asset_crs(asset)
        if not horizontal_epsg:
            raise Exception('Not recognized Point Cloud horizontal CRS (required for ellipsoidal height conversion)')
        vertical_epsg = vertical_epsg or 3855
        geodetic_crs = CRS(horizontal_epsg).geodetic_crs.to_epsg()
        pipeline += [{"type": 'filters.reprojection', "in_srs": f"EPSG:{horizontal_epsg}+{vertical_epsg}", "out_srs": f"EPSG:{horizontal_epsg}+{geodetic_crs}", "error_on_failure": True}]

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
        return asset_upload_path

    output_processed_laz_path = get_asset_upload_path(f"{asset['id']}/{pipeline_id}.laz")
    pipeline_process_path = get_asset_upload_path(f"{asset['id']}/{pipeline_id}.pipeline.json")

    pipeline = [{"filename": asset_upload_path, "type": 'readers.las'}] + pipeline + [{"type": 'writers.las', "filename": output_processed_laz_path, "compression": True}]

    with open(pipeline_process_path, "w") as f:
        json.dump(pipeline, f)

    res = run_subprocess(['pdal', 'pipeline', pipeline_process_path], capture_output=True, text=True)

    if not os.path.isfile(output_processed_laz_path):
        print(res.stderr)
        raise Exception("Processed LAS not created")

    return output_processed_laz_path
