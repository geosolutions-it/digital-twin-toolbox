"""Dependency-free 3D Tiles helpers: bounding box and tileset.json writing."""

import json
import math
import os


def box(mn, mx, min_half=0.01):
    """Axis-aligned bounds -> 3D Tiles box; min_half avoids zero-thickness boxes."""
    c = [(float(mn[i]) + float(mx[i])) / 2.0 for i in range(3)]
    h = [max((float(mx[i]) - float(mn[i])) / 2.0, min_half) for i in range(3)]
    return [
        c[0],
        c[1],
        c[2],
        h[0],
        0.0,
        0.0,
        0.0,
        h[1],
        0.0,
        0.0,
        0.0,
        h[2],
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


def region_corners(region, samples=3):
    """ECEF points bounding a 3D Tiles region (radians, metres), edges sampled for curvature."""
    west, south, east, north, low, high = region
    a, e2 = 6378137.0, 6.69437999014e-3
    points = []
    for i in range(samples):
        lon = west + (east - west) * i / (samples - 1)
        for j in range(samples):
            lat = south + (north - south) * j / (samples - 1)
            n = a / math.sqrt(1 - e2 * math.sin(lat) ** 2)
            for h in (low, high):
                points.append(
                    (
                        (n + h) * math.cos(lat) * math.cos(lon),
                        (n + h) * math.cos(lat) * math.sin(lon),
                        (n * (1 - e2) + h) * math.sin(lat),
                    )
                )
    return points
