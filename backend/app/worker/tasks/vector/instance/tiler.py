"""Instance 3D Tiles 1.1 tileset: one glb per node, additive refinement.

Below max_features_per_tile the whole set is a single tile. Above it, an additive
quadtree: each node keeps a stride sample as its own content and pushes the rest to
quadrant children, so every instance renders exactly once and coarse levels thin
out (no replacement, no holes).
"""
import json
import os

import numpy as np

from app.worker.tasks.vector.instance.glb import write_instanced_glb


def _box(enu):
    mn, mx = enu.min(axis=0), enu.max(axis=0)
    c = (mn + mx) / 2.0
    h = np.maximum((mx - mn) / 2.0, 1.0)  # avoid a zero-thickness box for one point
    return [float(c[0]), float(c[1]), float(c[2]),
            float(h[0]), 0.0, 0.0, 0.0, float(h[1]), 0.0, 0.0, 0.0, float(h[2])]


def _write_node(records, models, schema, out_dir, tile_id):
    """Group a node's records by model, emit one instanced glb, return its box."""
    enu = np.array([r["enu"] for r in records], dtype=np.float64)
    order = sorted(range(len(records)), key=lambda i: records[i]["model"])
    records = [records[i] for i in order]
    groups, features = [], []
    i = 0
    while i < len(records):
        name = records[i]["model"]
        chunk = [r for r in records if r["model"] == name]
        groups.append({
            "mesh": models[name],
            "translations": np.array([r["enu"] for r in chunk], dtype=np.float64),
            "headings": np.array([r["heading"] for r in chunk], dtype=np.float64),
            "scales": np.array([r["scale"] for r in chunk], dtype=np.float64),
        })
        features.extend(r["properties"] for r in chunk)
        i += len(chunk)
    write_instanced_glb(os.path.join(out_dir, f"{tile_id}.glb"), groups, features, schema)
    return _box(enu)


def _subdivide(records, depth, max_features, max_depth, max_ge, models, schema, out_dir, counter):
    tile_id = counter["n"]
    counter["n"] += 1
    is_leaf = len(records) <= max_features or depth >= max_depth

    if is_leaf:
        content, remainder = records, []
    else:
        stride = max(1, len(records) // max_features)
        content = records[::stride]
        taken = set(id(r) for r in content)
        remainder = [r for r in records if id(r) not in taken]

    box = _write_node(content, models, schema, out_dir, tile_id)
    node = {
        "boundingVolume": {"box": box},
        "geometricError": float(max_ge) / (2 ** depth) if not is_leaf else 0.0,
        "content": {"uri": f"{tile_id}.glb"},
        "refine": "ADD",
    }
    if remainder:
        enu = np.array([r["enu"] for r in remainder])
        cx, cy = enu[:, 0].mean(), enu[:, 1].mean()
        quads = [[], [], [], []]
        for r in remainder:
            qx = 0 if r["enu"][0] < cx else 1
            qy = 0 if r["enu"][1] < cy else 1
            quads[qy * 2 + qx].append(r)
        node["children"] = [
            _subdivide(q, depth + 1, max_features, max_depth, max_ge, models, schema, out_dir, counter)
            for q in quads if q
        ]
    return node


def build_instance_tileset(records, output_dir, transform, models, schema,
                           max_features_per_tile=25000, max_geometric_error=500.0, max_depth=16):
    """records: dicts with enu(3), heading, scale, model, properties. models: name->mesh."""
    os.makedirs(output_dir, exist_ok=True)
    if not records:
        raise ValueError("No instances to tile")

    counter = {"n": 0}
    root = _subdivide(records, 0, max_features_per_tile, max_depth,
                      float(max_geometric_error), models, schema, output_dir, counter)
    root["transform"] = transform
    if root["geometricError"] == 0.0:
        root["geometricError"] = float(max_geometric_error)
    tileset = {
        "asset": {"version": "1.1"},
        "geometricError": float(root["geometricError"]),
        "root": root,
    }
    with open(os.path.join(output_dir, "tileset.json"), "w") as f:
        json.dump(tileset, f, separators=(",", ":"))
    return tileset
