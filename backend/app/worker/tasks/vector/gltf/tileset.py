"""Shared 3D Tiles 1.1 helpers: bounding box and tileset.json writing."""
import json
import os

import numpy as np


def box(mn, mx, min_half=0.01):
    """Axis-aligned bounds -> 3D Tiles box; min_half avoids zero-thickness boxes."""
    c = (mn + mx) / 2.0
    h = np.maximum((mx - mn) / 2.0, min_half)
    return [
        float(c[0]), float(c[1]), float(c[2]),
        float(h[0]), 0.0, 0.0,
        0.0, float(h[1]), 0.0,
        0.0, 0.0, float(h[2]),
    ]


def write_tileset(output_dir, root, transform, geometric_error):
    """Attach the root transform and write tileset.json; returns the tileset dict."""
    root["transform"] = transform
    tileset = {
        "asset": {"version": "1.1"},
        "geometricError": float(geometric_error),
        "root": root,
    }
    with open(os.path.join(output_dir, "tileset.json"), "w") as f:
        json.dump(tileset, f, separators=(",", ":"))
    return tileset
