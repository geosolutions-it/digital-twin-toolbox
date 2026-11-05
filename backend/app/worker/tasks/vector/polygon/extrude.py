"""Polygon extrusion: footprint rings -> prism triangle soup (top cap, walls, optional bottom cap)."""
import mapbox_earcut
import numpy as np


def _earcut(rings):
    """Triangle vertex indices (M,3) into the concatenated rings; empty when earcut fails."""
    xy = np.concatenate(rings).astype(np.float32)
    ends = np.cumsum([len(r) for r in rings]).astype(np.uint32)
    try:
        return np.asarray(mapbox_earcut.triangulate_float32(xy, ends), dtype=np.int64).reshape(-1, 3)
    except Exception:
        return np.empty((0, 3), dtype=np.int64)


def _cap(xy, tri, z):
    pts = np.column_stack([xy, np.full(len(xy), z, dtype=np.float64)])
    return pts[tri].reshape(-1, 3)


def _walls(rings, z_low, z_high):
    out = []
    for ring in rings:
        if len(ring) < 2:
            continue
        a, b = ring[:-1], ring[1:]
        lo, hi = np.full(len(a), z_low, dtype=np.float64), np.full(len(a), z_high, dtype=np.float64)
        bl, br = np.column_stack([a, lo]), np.column_stack([b, lo])
        tl, tr = np.column_stack([a, hi]), np.column_stack([b, hi])
        out.append(np.stack([bl, tl, br, br, tl, tr], axis=1).reshape(-1, 3))
    return out


def extrude(rings, base_z, lower=None, upper=None, translate_z=0, remove_bottom=True):
    """rings: closed (n,2) arrays, outer first. lower/upper replace base_z for the bottom/top;
    with neither, only the flat footprint is returned. -> (N,3) soup or None."""
    xy = np.concatenate(rings).astype(np.float64)
    tri = _earcut(rings)
    shift = translate_z or 0
    z_low = (lower if lower is not None else base_z or 0) + shift
    if lower is None and upper is None:
        parts = [_cap(xy, tri, z_low)]
    else:
        z_high = (upper if upper is not None else base_z or 0) + shift
        if z_low > z_high:
            z_low, z_high = z_high, z_low
        parts = [_cap(xy, tri, z_high)] + _walls(rings, z_low, z_high)
        if not remove_bottom:
            parts.append(_cap(xy, tri[:, [0, 2, 1]], z_low))
    soup = np.concatenate(parts)
    return soup if len(soup) else None
