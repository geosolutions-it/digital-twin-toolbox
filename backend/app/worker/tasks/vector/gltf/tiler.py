"""Quadtree tiler: features -> 3D Tiles 1.1 tileset + one .glb per node.

Multi-resolution LOD with REPLACE refinement: every node (not just leaves) holds
geometry for all features beneath it, so there are no empty tiles and no holes at
any distance. Leaves are full resolution; parents re-extrude the same features with
footprints simplified by a tolerance that grows toward the root. geometricError
equals that tolerance, so a viewer loads coarse-first and refines as it approaches.

The tiler is geometry-agnostic: it owns the tree and calls `extrude(items, tolerance)`,
which returns (enu positions (M,3), per-feature vertex counts, per-feature properties)
or None. Each feature item carries 2D 'min'/'max'/'centroid' (east,north) for splitting
and 'properties' for the metadata schema.
"""
import json
import os

import numpy as np

from app.worker.tasks.vector.gltf.writer import infer_schema, write_glb


def _box(mn, mx):
    c = (mn + mx) / 2.0
    h = (mx - mn) / 2.0
    return [
        float(c[0]), float(c[1]), float(c[2]),
        float(h[0]), 0.0, 0.0,
        0.0, float(h[1]), 0.0,
        0.0, 0.0, float(h[2]),
    ]


def _node(items, depth, max_features, max_depth, max_ge, schema, extrude, out_dir, counter):
    is_leaf = len(items) <= max_features or depth >= max_depth
    tolerance = 0.0 if is_leaf else float(max_ge) / (2 ** depth)

    mesh = extrude(items, tolerance) or extrude(items, 0.0)
    enu, counts, props = mesh
    tile_id = counter["n"]
    counter["n"] += 1
    write_glb(os.path.join(out_dir, f"{tile_id}.glb"), enu, counts, props, schema)

    node = {
        "boundingVolume": {"box": _box(enu.min(axis=0), enu.max(axis=0))},
        "geometricError": float(tolerance),
        "content": {"uri": f"{tile_id}.glb"},
    }
    if is_leaf:
        return node

    mn = np.min([it["min"] for it in items], axis=0)
    mx = np.max([it["max"] for it in items], axis=0)
    cx = (mn[0] + mx[0]) / 2.0
    cy = (mn[1] + mx[1]) / 2.0
    quads = [[], [], [], []]
    for it in items:
        qx = 0 if it["centroid"][0] < cx else 1
        qy = 0 if it["centroid"][1] < cy else 1
        quads[qy * 2 + qx].append(it)

    node["children"] = [
        _node(q, depth + 1, max_features, max_depth, max_ge, schema, extrude, out_dir, counter)
        for q in quads if q
    ]
    return node


def build_tileset(features, output_dir, transform, extrude, max_features_per_tile=1000,
                  max_geometric_error=500.0, max_depth=16):
    """features: dicts with 2D min/max/centroid + properties + opaque extrude payload."""
    os.makedirs(output_dir, exist_ok=True)
    if not features:
        raise ValueError("No features to tile")

    schema = infer_schema([f["properties"] for f in features])
    counter = {"n": 0}
    root = _node(features, 0, max_features_per_tile, max_depth,
                 float(max_geometric_error), schema, extrude, output_dir, counter)
    root["refine"] = "REPLACE"
    root["transform"] = transform

    tileset = {
        "asset": {"version": "1.1"},
        "geometricError": float(max_geometric_error),
        "root": root,
    }
    with open(os.path.join(output_dir, "tileset.json"), "w") as f:
        json.dump(tileset, f, separators=(",", ":"))
    return tileset
