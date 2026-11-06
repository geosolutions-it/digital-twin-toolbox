"""Dependency-free 3D Tiles helpers: bounding box and tileset.json writing."""
import json
import os


def box(mn, mx, min_half=0.01):
    """Axis-aligned bounds -> 3D Tiles box; min_half avoids zero-thickness boxes."""
    c = [(float(mn[i]) + float(mx[i])) / 2.0 for i in range(3)]
    h = [max((float(mx[i]) - float(mn[i])) / 2.0, min_half) for i in range(3)]
    return [
        c[0], c[1], c[2],
        h[0], 0.0, 0.0,
        0.0, h[1], 0.0,
        0.0, 0.0, h[2],
    ]


def write_tileset(output_dir, root, transform, geometric_error, metadata=None):
    """Attach the root transform and write tileset.json; metadata adds top-level keys."""
    root["transform"] = transform
    tileset = {
        "asset": {"version": "1.1"},
        "geometricError": float(geometric_error),
        "root": root,
    }
    tileset.update(metadata or {})
    with open(os.path.join(output_dir, "tileset.json"), "w") as f:
        json.dump(tileset, f, separators=(",", ":"))
    return tileset
