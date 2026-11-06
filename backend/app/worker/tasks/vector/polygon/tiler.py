"""Size-bounded 3D Tiles 1.1 tileset (REPLACE): full-detail leaves, parents keep the larger
features simplified, never fused, with geometricError measured from the simplification."""
import os

import numpy as np

from app.worker.tasks.vector.gltf.glb import infer_schema, tileset_metadata
from app.worker.tasks.common.tiles3d import box, write_tileset
from app.worker.tasks.vector.polygon.writer import glb_bytes

_EST_BYTES_PER_VERTEX = 12
_MIN_EXTENT = 2.0
_CELL_STEP = 2 ** 0.5
_CELL_DIVISOR = 4.0


def cluster(soup, d, vertex_fid):
    """Per-feature vertex clustering on a grid of size d.
    -> (soup, feature id per vertex, max displacement of surviving vertices, vanished feature ids)"""
    keys = np.column_stack([vertex_fid, np.floor(soup / d).astype(np.int64)])
    _, inv = np.unique(keys, axis=0, return_inverse=True)
    inv = inv.ravel()
    n = int(inv.max()) + 1
    rep = np.zeros((n, 3))
    np.add.at(rep, inv, soup)
    rep /= np.bincount(inv, minlength=n)[:, None]
    cell_fid = np.zeros(n, dtype=np.int64)
    cell_fid[inv] = vertex_fid
    tri = inv.reshape(-1, 3)
    tri = tri[(tri[:, 0] != tri[:, 1]) & (tri[:, 1] != tri[:, 2]) & (tri[:, 0] != tri[:, 2])]
    if len(tri):
        _, keep = np.unique(np.sort(tri, axis=1), axis=0, return_index=True)
        tri = tri[np.sort(keep)]
    out_fid = cell_fid[tri].ravel()
    alive = np.isin(vertex_fid, out_fid)
    moved = np.linalg.norm(soup - rep[inv], axis=1)
    error = float(moved[alive].max()) if alive.any() else 0.0
    vanished = np.setdiff1d(np.unique(vertex_fid), out_fid)
    return rep[tri].reshape(-1, 3), out_fid, error, vanished


def _generalize(items, e):
    """Keep features with extent >= e, clustered on a grid of e/4 (full detail if they would collapse)."""
    kept = [i for i, it in enumerate(items) if it["extent"] >= e]
    dropped = max((it["extent"] for it in items if it["extent"] < e), default=0.0)
    if not kept:
        return np.empty((0, 3)), np.empty(0, dtype=np.int64), dropped
    soup = np.concatenate([items[i]["mesh"] for i in kept], axis=0)
    fid = np.concatenate([np.full(len(items[i]["mesh"]), i) for i in kept])
    coarse, out_fid, moved, vanished = cluster(soup, e / _CELL_DIVISOR, fid)
    if len(vanished):
        coarse = np.concatenate([coarse] + [items[i]["mesh"] for i in vanished], axis=0)
        out_fid = np.concatenate([out_fid] + [np.full(len(items[i]["mesh"]), i) for i in vanished])
        # glb_bytes wants vertices grouped by feature
        order = np.argsort(out_fid.reshape(-1, 3)[:, 0], kind="stable")
        coarse = coarse.reshape(-1, 3, 3)[order].reshape(-1, 3)
        out_fid = out_fid.reshape(-1, 3)[order].ravel()
    return coarse, out_fid, max(moved, dropped)


def _split(items):
    """Four children of balanced size: median split on x, then on y within each half."""
    by_x = sorted(items, key=lambda it: it["centroid"][0])
    half = len(by_x) // 2
    out = []
    for part in (by_x[:half], by_x[half:]):
        by_y = sorted(part, key=lambda it: it["centroid"][1])
        q = len(by_y) // 2
        out += [by_y[:q], by_y[q:]]
    return [q for q in out if q]


class _Builder:
    def __init__(self, out_dir, schema, max_bytes, max_depth):
        self.out_dir = out_dir
        self.schema = schema
        self.max_bytes = max_bytes
        self.max_depth = max_depth
        self.n = 0
        self.stats = []

    def _write(self, data):
        tile_id = self.n
        self.n += 1
        with open(os.path.join(self.out_dir, f"{tile_id}.glb"), "wb") as f:
            f.write(data)
        self.stats.append(len(data))
        return f"{tile_id}.glb"

    def _leaf_bytes(self, items):
        soup = np.concatenate([it["mesh"] for it in items], axis=0)
        counts = [len(it["mesh"]) for it in items]
        props = [it["properties"] for it in items]
        return soup, glb_bytes(soup, counts, props, self.schema)

    def node(self, items, depth):
        """-> (tile json, geometric error, aabb min, aabb max, size threshold e)"""
        est = sum(len(it["mesh"]) for it in items) * _EST_BYTES_PER_VERTEX + sum(it["meta_bytes"] for it in items)
        can_split = len(items) > 1 and depth < self.max_depth
        if est <= self.max_bytes * 1.5 or not can_split:
            soup, data = self._leaf_bytes(items)
            if len(data) <= self.max_bytes or not can_split:
                mn, mx = soup.min(axis=0), soup.max(axis=0)
                tile = {"boundingVolume": {"box": box(mn, mx)}, "geometricError": 0.0,
                        "content": {"uri": self._write(data)}}
                return tile, 0.0, mn, mx, 0.0

        children = [self.node(part, depth + 1) for part in _split(items)]
        mn = np.min([c[2] for c in children], axis=0)
        mx = np.max([c[3] for c in children], axis=0)
        e = max(max(c[4] for c in children), _MIN_EXTENT)
        while True:
            coarse, out_fid, error = _generalize(items, e)
            data = None
            if len(coarse):
                alive, counts = np.unique(out_fid, return_counts=True)
                props = [items[i]["properties"] for i in alive]
                data = glb_bytes(coarse, counts.tolist(), props, self.schema, max_step=e / 40.0)
            if data is None or len(data) <= self.max_bytes:
                break
            e *= _CELL_STEP
        error = max(error, max(c[1] for c in children))
        tile = {"boundingVolume": {"box": box(mn, mx)}, "geometricError": error,
                "children": [c[0] for c in children]}
        if data is not None:
            tile["content"] = {"uri": self._write(data)}
        return tile, error, mn, mx, e


def _meta_bytes(props):
    return sum(len(str(v).encode("utf-8")) + 4 for v in (props or {}).values())


def build_tileset(features, output_dir, transform, max_tile_bytes=400 * 1024, max_depth=16):
    """features: dicts with mesh ((N,3) ENU triangle soup), 2D centroid and properties."""
    os.makedirs(output_dir, exist_ok=True)
    items = [{**f, "meta_bytes": _meta_bytes(f["properties"]),
              "extent": float(np.linalg.norm(f["mesh"].max(axis=0) - f["mesh"].min(axis=0)))}
             for f in features if len(f["mesh"])]
    if not items:
        raise ValueError("No features to tile")

    schema = infer_schema([it["properties"] for it in items])
    builder = _Builder(output_dir, schema, int(max_tile_bytes), max_depth)
    root = builder.node(items, 0)[0]
    root["refine"] = "REPLACE"
    metadata = tileset_metadata([it["properties"] for it in items], schema)
    tileset = write_tileset(output_dir, root, transform, float(root["geometricError"]) * 2.0 or 1.0, metadata)
    return tileset, builder.stats
