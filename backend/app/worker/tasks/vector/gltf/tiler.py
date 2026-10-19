"""Quadtree tiler: ENU meshes -> 3D Tiles 1.1 tileset + one .glb per leaf.

ADD refinement (leaves carry geometry); geometricError halves with depth.
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


def _node(items, depth, max_features, max_depth, max_ge, schema, out_dir, counter):
    mn = np.min([it["min"] for it in items], axis=0)
    mx = np.max([it["max"] for it in items], axis=0)
    node = {
        "boundingVolume": {"box": _box(mn, mx)},
        "geometricError": float(max_ge / (2 ** depth)),
    }

    if len(items) <= max_features or depth >= max_depth:
        tile_id = counter["n"]
        counter["n"] += 1
        enu = np.concatenate([it["enu"] for it in items], axis=0)
        counts = [len(it["enu"]) for it in items]
        props = [it["properties"] for it in items]
        write_glb(os.path.join(out_dir, f"{tile_id}.glb"), enu, counts, props, schema)
        node["content"] = {"uri": f"{tile_id}.glb"}
        node["geometricError"] = 0.0
        return node

    cx = (mn[0] + mx[0]) / 2.0
    cy = (mn[1] + mx[1]) / 2.0
    quads = [[], [], [], []]
    for it in items:
        qx = 0 if it["c"][0] < cx else 1
        qy = 0 if it["c"][1] < cy else 1
        quads[qy * 2 + qx].append(it)

    node["children"] = [
        _node(q, depth + 1, max_features, max_depth, max_ge, schema, out_dir, counter)
        for q in quads if q
    ]
    return node


def build_tileset(features, output_dir, transform, max_features_per_tile=1000,
                  max_geometric_error=500.0, max_depth=16):
    """features: [{enu: (N,3) array, properties: dict}]. Writes tileset + glbs."""
    os.makedirs(output_dir, exist_ok=True)
    if not features:
        raise ValueError("No features to tile")

    schema = infer_schema([f["properties"] for f in features])
    items = []
    for f in features:
        enu = f["enu"]
        mn = enu.min(axis=0)
        mx = enu.max(axis=0)
        items.append({
            "enu": enu, "properties": f.get("properties") or {},
            "min": mn, "max": mx, "c": (mn[:2] + mx[:2]) / 2.0,
        })

    counter = {"n": 0}
    root = _node(items, 0, max_features_per_tile, max_depth,
                 float(max_geometric_error), schema, output_dir, counter)
    root["refine"] = "ADD"
    root["transform"] = transform

    tileset = {
        "asset": {"version": "1.1"},
        "geometricError": float(max_geometric_error),
        "root": root,
    }
    with open(os.path.join(output_dir, "tileset.json"), "w") as f:
        json.dump(tileset, f, separators=(",", ":"))
    return tileset
