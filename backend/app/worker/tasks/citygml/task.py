import json
import os
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed

from pyproj import Transformer

from app.worker.common.utils import get_asset_upload_path, setup_output_directory
from app.worker.main import AssetDatabaseTask, PipelineDatabaseTask, celery
from app.worker.tasks.citygml.crs import (
    resolve_epsg_code,
    resolve_layer_extent,
    select_primary_layer,
)
from app.worker.tasks.citygml.processes import (
    run_citygml_tools_subset,
    run_mago_3d_tiler,
    run_ogrinfo_json,
)
from app.worker.tasks.citygml.tileset import build_parent_tileset
from app.worker.tasks.citygml.utils import resolve_citygml_input_file


def _empty_payload():
    return {
        "metadata": False,
        "stats": False,
        "sample": False,
        "epsg": None,
        "horizontal_epsg": None,
    }


def _get_total_feature_count(layers: list[dict]) -> int:
    """Sum feature counts across all OGR layers in the CityGML file."""
    return sum(int(layer.get("featureCount") or 0) for layer in layers)


def _extent_to_wgs84_bbox(extent: list[float], epsg: int) -> list[float]:
    if len(extent) < 4:
        raise ValueError("Invalid layer extent")

    minx, miny, maxx, maxy = extent[:4]
    transformer = Transformer.from_crs(epsg, 4326, always_xy=True)

    corners = [
        transformer.transform(minx, miny),
        transformer.transform(maxx, miny),
        transformer.transform(maxx, maxy),
        transformer.transform(minx, maxy),
    ]
    lons = [corner[0] for corner in corners]
    lats = [corner[1] for corner in corners]
    return [min(lons), min(lats), max(lons), max(lats)]


def _convert_chunk(
    chunk_index: int,
    chunk_path: str,
    tiles_dir: str,
    crs: int,
) -> str:
    chunk_name = f"chunk_{chunk_index:04d}"
    chunk_output_dir = os.path.join(tiles_dir, chunk_name)
    run_mago_3d_tiler(chunk_path, chunk_output_dir, crs)
    return chunk_name


@celery.task(name="inspect_citygml", base=AssetDatabaseTask)
def inspect_citygml(options):
    asset = options["asset"]
    asset_id = asset["id"]
    extension = asset["extension"]

    input_path = resolve_citygml_input_file(asset_id, extension)
    info = run_ogrinfo_json(input_path)

    layers = info.get("layers") or []
    primary_layer = select_primary_layer(layers)
    total_feature_count = _get_total_feature_count(layers)
    epsg = resolve_epsg_code(input_path, info, primary_layer)

    extent = resolve_layer_extent(primary_layer, input_path)
    bbox_wgs84 = None
    if extent is not None:
        bbox_wgs84 = _extent_to_wgs84_bbox(extent, epsg)

    metadata_path = get_asset_upload_path(f"{asset_id}/metadata.json")
    with open(metadata_path, "w") as handle:
        json.dump(info, handle)

    payload = {
        **_empty_payload(),
        "metadata": True,
        "epsg": epsg,
        "horizontal_epsg": epsg,
        "feature_count": total_feature_count,
    }
    if bbox_wgs84 is not None:
        payload["bbox"] = bbox_wgs84

    return {
        "asset_type": "CityGML",
        "geometry_type": "Polygon",
        "payload": payload,
    }


@celery.task(name="create_citygml_3dtiles", base=PipelineDatabaseTask)
def create_citygml_3dtiles(pipeline_extended):
    asset = pipeline_extended["asset"]
    asset_id = asset["id"]
    pipeline_id = pipeline_extended["id"]
    extension = asset.get("extension", ".gml")
    upload_result = asset.get("upload_result") or {}

    default_config = {
        "crs": upload_result.get("epsg"),
        "feature_count_target": 2000,
        "max_workers": 4,
    }
    pipeline_config = pipeline_extended.get("data") or {}
    config = {**default_config, **pipeline_config}

    crs = config.get("crs")
    if crs is None:
        raise ValueError("Missing CRS configuration")
    if int(crs) <= 0:
        raise ValueError("Invalid CRS configuration: horizontal EPSG code is required")

    feature_count_target = int(config["feature_count_target"])
    max_workers = max(1, int(config["max_workers"]))

    input_path = resolve_citygml_input_file(asset_id, extension)
    info = run_ogrinfo_json(input_path)
    total_feature_count = _get_total_feature_count(info.get("layers") or [])

    feature_count = int(upload_result.get("feature_count") or 0)
    if feature_count <= 0 or feature_count < total_feature_count:
        feature_count = total_feature_count

    output_paths = setup_output_directory(pipeline_id)
    tiles_dir = output_paths["output_path_3dtiles"]
    process_dir = os.path.join(output_paths["output_path"], "process")
    os.makedirs(tiles_dir, exist_ok=True)
    os.makedirs(process_dir, exist_ok=True)

    if feature_count <= feature_count_target:
        run_mago_3d_tiler(input_path, tiles_dir, int(crs))
    else:
        chunk_jobs = []
        chunk_index = 0
        while True:
            start_index = chunk_index * feature_count_target
            if total_feature_count > 0 and start_index >= total_feature_count:
                break

            chunk_dir = os.path.join(process_dir, f"chunk_{chunk_index:04d}")
            try:
                chunk_path = run_citygml_tools_subset(
                    input_path,
                    chunk_dir,
                    start_index,
                    feature_count_target,
                )
            except Exception:
                break

            if not chunk_path or not os.path.exists(chunk_path):
                break

            # Verify chunk contains top-level features
            chunk_info = run_ogrinfo_json(chunk_path)
            chunk_features = _get_total_feature_count(chunk_info.get("layers") or [])
            if chunk_features == 0:
                break

            chunk_jobs.append((chunk_index, chunk_path))
            chunk_index += 1

            if total_feature_count > 0 and start_index + feature_count_target >= total_feature_count:
                break

        child_names = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    _convert_chunk, chunk_idx, chunk_path, tiles_dir, int(crs)
                ): chunk_idx
                for chunk_idx, chunk_path in chunk_jobs
            }
            for future in as_completed(futures):
                child_names.append(future.result())

        child_names.sort()
        build_parent_tileset(tiles_dir, child_names)

    shutil.make_archive(output_paths["output_path_3dtiles_zip"], "zip", tiles_dir)

    return {
        "output": output_paths["output_path"],
        "tileset": output_paths["output_tileset"],
        "download": output_paths["output_tileset_zip"],
    }