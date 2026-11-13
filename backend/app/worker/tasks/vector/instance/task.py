"""Bucket-first point instances: a point vector + uploaded model glbs -> 3D Tiles
1.1 with EXT_mesh_gpu_instancing. No PostGIS, no i3dm.export binary."""

import os
import tempfile

from app.core.storage import get_storage
from app.models.config import InstanceConfig
from app.worker.common.expression import parse_expression
from app.worker.common.geo import LocalFrame
from app.worker.common.gltf import infer_schema
from app.worker.common.logs import log_stage
from app.worker.common.output import publish_tiles
from app.worker.common.task_input import task_output_base, task_source
from app.worker.main import PipelineDatabaseTask, celery
from app.worker.tasks.vector.instance import reader
from app.worker.tasks.vector.instance.tiler import build_instance_tileset
from app.worker.tasks.vector.source import resolve_input

# per-feature fallback when an expression cannot be evaluated
_DEFAULTS = {name: field.default for name, field in InstanceConfig.model_fields.items()}


def _load_model(storage, name, config, scratch, cache):
    """Download a model glb from the bucket once and parse it; cached by name, None if missing."""
    if name in cache:
        return cache[name]
    key = config.models_prefix + str(name)
    if not storage.exists(key):
        return None
    dest = os.path.join(scratch, "model_" + os.path.basename(str(name)))
    storage.download_file(key, dest)
    mesh = reader.read_model_glb(dest)
    cache[name] = mesh
    return mesh


@celery.task(name="create_point_instance_3dtiles", base=PipelineDatabaseTask)
def create_point_instance_3dtiles(pipeline_extended):
    source = task_source(pipeline_extended, "Instance")

    config = InstanceConfig(**(pipeline_extended.get("data") or {}))

    storage = get_storage()
    out_base = task_output_base(pipeline_extended, source)

    with tempfile.TemporaryDirectory() as scratch:
        log_stage("Downloading input")
        input_path = resolve_input(source.key, storage, scratch)
        log_stage("Reading points")
        features, (lo, hi) = reader.read_points(
            input_path, config.to_ellipsoidal_height
        )
        if not features:
            raise Exception("No point features to tile")
        log_stage(f"Placing models on {len(features)} points")

        frame = LocalFrame.from_bounds(lo, hi)
        model_cache = {}
        records = []
        for feat in features:
            props = feat["properties"]
            fe = {
                "type": "Feature",
                "properties": props,
                "geometry": {"type": "Point", "coordinates": list(feat["lonlath"])},
            }
            model = parse_expression("string", config.model, fe, _DEFAULTS["model"])
            scale = parse_expression("number", config.scale, fe, _DEFAULTS["scale"])
            rotation = parse_expression(
                "number", config.rotation, fe, _DEFAULTS["rotation"]
            )
            elevation = parse_expression(
                "number", config.elevation, fe, _DEFAULTS["elevation"]
            )

            if (
                not model
                or _load_model(storage, model, config, scratch, model_cache) is None
            ):
                continue
            if scale is None:
                scale = _DEFAULTS["scale"]
            if rotation is None:
                rotation = _DEFAULTS["rotation"]
            lon, lat, h = feat["lonlath"]
            enu = frame.to_enu([[lon, lat, h if elevation is None else elevation]])[0]
            records.append(
                {
                    "enu": enu,
                    "heading": rotation,
                    "scale": scale,
                    "model": model,
                    "properties": props,
                }
            )

        if not records:
            raise Exception("No features with a valid model to tile")
        schema = infer_schema([r["properties"] for r in records])

        tiles_dir = os.path.join(scratch, "tiles")
        log_stage(f"Tiling {len(records)} instances")
        build_instance_tileset(
            records,
            tiles_dir,
            frame.transform(),
            model_cache,
            schema,
            max_tile_bytes=config.max_tile_size_kb * 1024,
            max_geometric_error=config.max_geometric_error,
        )

        return publish_tiles(storage, tiles_dir, out_base, "tileset.json")
