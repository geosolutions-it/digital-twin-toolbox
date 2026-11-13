import mapbox_earcut
import numpy as np


def _cross2(a, b):
    return a[0] * b[1] - a[1] * b[0]


def triangulate(rings):
    """rings: open (n,3) arrays, outer first."""
    outer = rings[0]
    if len(rings) == 1 and len(outer) == 3:
        return outer.copy()
    d = outer - outer.mean(axis=0)
    normal = np.cross(d, np.roll(d, -1, axis=0)).sum(axis=0)
    if np.linalg.norm(normal) < 1e-12:
        return None
    keep = [i for i in range(3) if i != int(np.argmax(np.abs(normal)))]
    if len(rings) == 1 and len(outer) == 4:
        p = outer[:, keep]
        diag = p[2] - p[0]
        # diagonal 0-2 is inside when 1 and 3 lie on opposite sides of it
        idx = (
            [0, 1, 2, 0, 2, 3]
            if _cross2(diag, p[1] - p[0]) * _cross2(diag, p[3] - p[0]) < 0
            else [1, 2, 3, 1, 3, 0]
        )
        return outer[idx]
    pts = np.concatenate(rings)
    ends = np.cumsum([len(r) for r in rings]).astype(np.uint32)
    try:
        tri = np.asarray(
            mapbox_earcut.triangulate_float64(pts[:, keep], ends), dtype=np.int64
        )
    except Exception:
        return None
    return pts[tri] if len(tri) else None
