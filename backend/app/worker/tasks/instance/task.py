"""Bucket-first point instances: a point vector + uploaded model glbs -> 3D Tiles
1.1 with EXT_mesh_gpu_instancing. No PostGIS, no i3dm.export binary."""

import os

from app.core.celery_app import celery
from app.models.config import InstanceConfig
from app.worker.lib.expression import parse_expression
from app.worker.lib.geo.frame import LocalFrame
from app.worker.lib.geo.ogr import resolve_input
from app.worker.lib.gltf import infer_schema
from app.worker.runtime.logs import log_stage
from app.worker.runtime.task import PipelineDatabaseTask, TaskContext
from app.worker.tasks.instance import reader
from app.worker.tasks.instance.tiler import build_instance_tileset

# per-feature fallback when an expression cannot be evaluated
_DEFAULTS = {name: field.default for name, field in InstanceConfig.model_fields.items()}


def _load_model(ctx, name, cache):
    """Download a model glb from the bucket once and parse it; cached by name, None if missing."""
    if name not in cache:
        key = ctx.config.models_prefix + str(name)
        cache[name] = (
            reader.read_model_glb(
                ctx.download(key, "model_" + os.path.basename(str(name)))
            )
            if ctx.storage.exists(key)
            else None
        )
    return cache[name]


@celery.task(name="create_point_instance_3dtiles", base=PipelineDatabaseTask)
def create_point_instance_3dtiles(pipeline_extended):
    with TaskContext(pipeline_extended, "Instance", InstanceConfig) as ctx:
        config = ctx.config
        log_stage("Downloading input")
        input_path = resolve_input(ctx.source.key, ctx.storage, ctx.scratch)
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

            if not model or _load_model(ctx, model, model_cache) is None:
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

        tiles_dir = ctx.path("tiles")
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

        return ctx.publish(tiles_dir, "tileset.json")
