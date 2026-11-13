import json
import os
import tempfile

import numpy as np

from app.core.storage import get_storage, output_key
from app.models.config import PolygonConfig
from app.worker.common.expression import parse_expression
from app.worker.common.geo import LocalFrame
from app.worker.common.logs import log_stage
from app.worker.common.output import publish_tiles
from app.worker.main import PipelineDatabaseTask, celery
from app.worker.tasks.vector.polygon.extrude import extrude
from app.worker.tasks.vector.polygon.tiler import build_tileset
from app.worker.tasks.vector.source import (
    coerce,
    field_names,
    open_layer,
    resolve_input,
    wgs84_transform,
)


def _ensure_z(coords):
    if coords and isinstance(coords[0], (int, float)):
        return [coords[0], coords[1], coords[2] if len(coords) > 2 else 0.0]
    return [_ensure_z(c) for c in coords]


def _read_raw_features(path, config):
    """Open the vector with OGR, reproject to WGS84 (optionally ellipsoidal), and
    collect per-feature footprints + resolved heights. Returns (features, (lo, hi))."""
    ds, layer = open_layer(path)
    to_ellipsoidal = config.to_ellipsoidal_height
    transform = wgs84_transform(layer, to_ellipsoidal)
    names = field_names(layer)

    lo = np.array([np.inf, np.inf, np.inf])
    hi = np.array([-np.inf, -np.inf, -np.inf])
    features = []
    for feat in layer:
        geom = feat.GetGeometryRef()
        if geom is None:
            continue
        geom = geom.Clone()
        if to_ellipsoidal:
            geom.Set3D(True)
        geom.Transform(transform)
        geometry = json.loads(geom.ExportToJson())
        gtype = geometry.get("type")
        if gtype == "Polygon":
            parts = [geometry["coordinates"]]
        elif gtype == "MultiPolygon":
            parts = geometry["coordinates"]
        else:
            continue

        properties = {name: coerce(feat.GetField(name)) for name in names}
        feature_for_expr = {
            "type": "Feature",
            "properties": properties,
            "geometry": geometry,
        }
        lower = parse_expression("number", config.lower_limit_height, feature_for_expr)
        upper = parse_expression("number", config.upper_limit_height, feature_for_expr)

        parts = [_ensure_z(p) for p in parts]
        for poly in parts:
            for ring in poly:
                arr = np.asarray(ring, dtype=np.float64)
                lo = np.minimum(lo, arr.min(axis=0))
                hi = np.maximum(hi, arr.max(axis=0))

        features.append(
            {
                "parts": parts,
                "lower": lower,
                "upper": upper,
                "remove_bottom": config.remove_bottom_surface,
                "properties": properties,
            }
        )

    return features, (lo, hi)


def _height_to_enu(h, part):
    # absolute height -> ENU up, relative to the footprint so origin and curvature cancel
    if h is None:
        return None
    return part["ground_z"] + (h - part["ground_h"])


def _extrude_feature(payload):
    """Full-detail extrusion of one feature -> (N,3) ENU triangle soup, or None."""
    meshes = [
        extrude(
            part["rings"],
            part["ground_z"],
            lower=_height_to_enu(payload["lower"], part),
            upper=_height_to_enu(payload["upper"], part),
            remove_bottom=payload["remove_bottom"],
        )
        for part in payload["parts"]
    ]
    meshes = [m for m in meshes if m is not None]
    return np.concatenate(meshes, axis=0) if meshes else None


def _build_meshes(raw, frame):
    """Raw features -> [{mesh, centroid, properties}] in the local ENU frame; empty extrusions dropped."""
    features = []
    for r in raw:
        parts = []
        fmin = np.array([np.inf, np.inf])
        fmax = np.array([-np.inf, -np.inf])
        for poly in r["parts"]:
            rings_enu = []
            ground_z = ground_h = 0.0
            for idx, ring in enumerate(poly):
                arr = np.asarray(ring, dtype=np.float64)
                enu = frame.to_enu(arr)
                rings_enu.append(enu[:, :2])
                if idx == 0:
                    ground_z = float(enu[:, 2].mean())
                    ground_h = float(arr[:, 2].mean())
                    fmin = np.minimum(fmin, enu[:, :2].min(axis=0))
                    fmax = np.maximum(fmax, enu[:, :2].max(axis=0))
            parts.append(
                {"rings": rings_enu, "ground_z": ground_z, "ground_h": ground_h}
            )
        mesh = _extrude_feature({**r, "parts": parts})
        if mesh is not None:
            features.append(
                {
                    "mesh": mesh,
                    "centroid": (fmin + fmax) / 2.0,
                    "properties": r["properties"],
                }
            )
    return features


@celery.task(name="create_polygon_3dtiles", base=PipelineDatabaseTask)
def create_polygon_3dtiles(pipeline_extended):
    pipeline_id = pipeline_extended["id"]
    source = pipeline_extended.get("source") or {}
    if not source.get("key"):
        raise Exception("Polygon pipeline requires a bucket source")

    config = PolygonConfig(**(pipeline_extended.get("data") or {}))

    storage = get_storage()
    out_base = source.get("output_base") or output_key(pipeline_id)

    with tempfile.TemporaryDirectory() as scratch:
        log_stage("Downloading input")
        input_path = resolve_input(source, storage, scratch)
        log_stage("Reading features")
        raw, (lo, hi) = _read_raw_features(input_path, config)
        if not raw:
            raise Exception("No polygon features to tile")

        frame = LocalFrame.from_bounds(lo, hi)

        log_stage(f"Building meshes for {len(raw)} features")
        features = _build_meshes(raw, frame)

        tiles_dir = os.path.join(scratch, "tiles")
        log_stage(f"Tiling {len(features)} features")
        build_tileset(
            features,
            tiles_dir,
            frame.transform(),
            max_tile_bytes=config.max_tile_size_kb * 1024,
        )

        return publish_tiles(storage, tiles_dir, out_base, "tileset.json")
