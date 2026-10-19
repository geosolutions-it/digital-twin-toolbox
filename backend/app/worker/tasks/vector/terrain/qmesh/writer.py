"""Encode one quantized-mesh tile via quantized-mesh-tile; drop zero-area
triangles so lighting normals never NaN, retry without lighting on failure."""
import os

import numpy as np
from quantized_mesh_tile import encode


def _triangles(positions, indices):
    """Mesh -> non-degenerate [lon,lat,h] triangles (zero-area dropped)."""
    p = np.asarray(positions, dtype=np.float64)
    idx = np.asarray(indices).reshape(-1, 3)
    a, b, c = p[idx[:, 0]], p[idx[:, 1]], p[idx[:, 2]]
    cross = np.cross(b - a, c - a)
    keep = np.einsum("ij,ij->i", cross, cross) > 0.0
    idx = idx[keep]
    return [[p[i].tolist(), p[j].tolist(), p[k].tolist()] for i, j, k in idx]


def _write(geometries, bounds, lighting, water, path):
    kwargs = {"bounds": list(bounds), "hasLighting": lighting}
    if water is not None:
        kwargs["watermask"] = water.flatten().tolist()
    if os.path.exists(path):
        os.remove(path)
    encode(geometries, **kwargs).toFile(path)


def encode_tile(path, positions, indices, bounds, config, water=None):
    """Write one .terrain tile. bounds = (west, south, east, north) degrees."""
    geometries = _triangles(positions, indices)
    lighting = bool(config.get("vertex_normals"))
    try:
        _write(geometries, bounds, lighting, water, path)
    except ValueError:
        if not lighting:
            raise
        _write(geometries, bounds, False, water, path)
