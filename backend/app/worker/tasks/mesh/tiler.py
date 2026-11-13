"""OBJ -> textured 3D Tiles quadtree: per tile decimate, unwrap (xatlas), bake, write .glb.
Vertices are metres east/north/up of lat/lon/alt; the tileset root transform places them."""

import json
import logging
import os
import time
from io import BytesIO

import numpy as np
from PIL import Image

from app.worker.lib.geo.frame import LocalFrame
from app.worker.lib.tiles3d.tileset import box, write_tileset
from app.worker.tasks.mesh.bake import (
    TextureCache,
    dilate,
    paint_texture,
    paint_vertex_color,
    rasterize_atlas,
    raycast,
)
from app.worker.tasks.mesh.reader import axis_matrix, mtl_paths, parse_mtl, parse_obj
from app.worker.tasks.mesh.writer import glb_bytes

logger = logging.getLogger(__name__)

TILE_MARGIN = 4.0  # m of overlap, hides cracks between independently decimated tiles
CAGE = 20.0  # m at level 0, halved per level
TEXTURE_QUALITY = 75


def _decimate(points, faces, target):
    import fast_simplification

    if target <= 0 or len(faces) <= target:
        return points, faces
    try:
        dec_points, dec_faces = fast_simplification.simplify(
            points, faces, 1.0 - target / len(faces)
        )
    except Exception as error:  # degenerate slice: keep full resolution
        logger.warning(f"decimation failed ({error}); keeping {len(faces)} faces")
        return points, faces
    return dec_points.astype(np.float32), dec_faces.astype(np.int32)


def _encode(rgb):
    out = BytesIO()
    Image.fromarray(rgb).save(out, format="WEBP", quality=TEXTURE_QUALITY, method=4)
    return out.getvalue()


def build_tile(mesh, cache, selected, shift, decimate_to, texture_size, cage):
    """One tile -> (glb bytes, ENU min, ENU max, stats) or None when nothing is left.
    shift recentres coordinates before the float32 steps (decimation, xatlas, Embree)."""
    import xatlas

    sub_v = mesh.face_v[selected]
    sub_vt = mesh.face_vt[selected]
    sub_mat = mesh.face_mat[selected]

    used, remapped = np.unique(sub_v.ravel(), return_inverse=True)
    points = (mesh.positions[used] - shift).astype(np.float32)
    faces = remapped.reshape(-1, 3).astype(np.int32)
    points, faces = _decimate(points, faces, decimate_to)
    if len(faces) == 0:
        return None

    vmapping, atlas_faces, atlas_uv = xatlas.parametrize(points, faces)
    if len(atlas_faces) == 0:
        return None
    atlas_points = points[vmapping]

    has_uv = len(mesh.uvs) > 0 and bool((sub_vt >= 0).all())
    if has_uv and any(cache.path(int(m)) for m in np.unique(sub_mat)):
        source = "texture"
    elif mesh.colors is not None:
        source = "vertex_color"
    else:
        source = "none"

    image, coverage = None, 0.0
    raster = (
        rasterize_atlas(atlas_uv, atlas_faces, texture_size)
        if source != "none"
        else None
    )
    if raster is not None:
        src_tri = (mesh.positions[sub_v] - shift).astype(np.float32)
        hits = raycast(src_tri, atlas_points, atlas_faces, raster, cage)
        if source == "texture":
            rgb, filled = paint_texture(
                texture_size, raster, hits, mesh.uvs[sub_vt], sub_mat, cache
            )
        else:
            rgb, filled = paint_vertex_color(
                texture_size, raster, hits, mesh.colors[sub_v]
            )
        coverage = float(filled[raster[0], raster[1]].mean())
        image = _encode(dilate(rgb, filled))
    elif source != "none":
        source = "none"

    enu = atlas_points.astype(np.float64) + shift
    glb = glb_bytes(enu, atlas_faces, atlas_uv if image else None, image)
    stats = {
        "faces": int(len(atlas_faces)),
        "source_faces": int(len(selected)),
        "color_source": source,
        "coverage": round(coverage, 3),
    }
    return glb, enu.min(axis=0), enu.max(axis=0), stats


def tile_grid(lo, hi, depth, margin=TILE_MARGIN):
    """(level, y, x, (min_x, max_x, min_y, max_y)) per quadtree cell; y counts down from the top."""
    size = hi - lo
    for level in range(depth + 1):
        n = 2**level
        w, h = size[0] / n, size[1] / n
        # small meshes: cap the overlap at a quarter tile
        m = min(margin, 0.25 * max(min(w, h), 1e-6))
        for y in range(n):
            for x in range(n):
                yield (
                    level,
                    y,
                    x,
                    (
                        lo[0] + x * w - m,
                        lo[0] + (x + 1) * w + m,
                        hi[1] - (y + 1) * h - m,
                        hi[1] - y * h + m,
                    ),
                )


def geometric_errors(max_geometric_error, depth):
    """Per level GE halves from max/2; the deepest level refines to 0."""
    return [max_geometric_error / 2 ** (level + 1) for level in range(depth + 1)] + [
        0.0
    ]


def build_tileset(tiles, depth, max_geometric_error):
    """tiles: {(level, y, x): (min, max)} -> REPLACE quadtree root (children only where written)."""
    ge = geometric_errors(max_geometric_error, depth)

    def node(level, y, x):
        """-> (tile, min, max); the box also encloses the children, whose faces can reach past the parent's."""
        lo, hi = tiles[(level, y, x)]
        children = [
            node(level + 1, cy, cx)
            for cy in (2 * y, 2 * y + 1)
            for cx in (2 * x, 2 * x + 1)
            if (level + 1, cy, cx) in tiles
        ]
        lo = np.min([lo, *(c[1] for c in children)], axis=0)
        hi = np.max([hi, *(c[2] for c in children)], axis=0)
        out = {
            "boundingVolume": {"box": box(lo, hi)},
            "geometricError": ge[level + 1],
            "refine": "REPLACE",
            "content": {"uri": f"{level}_{y}_{x}.glb"},
        }
        if children:
            out["children"] = [c[0] for c in children]
        return out, lo, hi

    top, _, _ = node(0, 0, 0)
    # contentless root, so 0_0_0 loads on refinement
    return {
        "boundingVolume": top["boundingVolume"],
        "geometricError": ge[0],
        "refine": "REPLACE",
        "children": [top],
    }, ge[0]


_SHARED = {}  # filled before the fork, read copy-on-write by pool workers


def _run_job(job):
    level, y, x, bounds, decimate_to, cage = job
    s = _SHARED
    c = s["centroids"]
    selected = np.nonzero(
        (c[:, 0] >= bounds[0])
        & (c[:, 0] <= bounds[1])
        & (c[:, 1] >= bounds[2])
        & (c[:, 1] <= bounds[3])
    )[0]
    if len(selected) == 0:
        return None
    started = time.time()
    result = build_tile(
        s["mesh"],
        s["cache"],
        selected,
        s["shift"],
        decimate_to,
        s["texture_size"],
        cage,
    )
    if result is None:
        return None
    glb, lo, hi, stats = result
    with open(os.path.join(s["output_dir"], f"{level}_{y}_{x}.glb"), "wb") as f:
        f.write(glb)
    stats.update(bytes=len(glb), seconds=round(time.time() - started, 1))
    return (level, y, x), lo, hi, stats


def run(params):
    """params: input_file, output_dir, latitude, longitude, altitude, depth, tile_faces_target,
    texture_image_size, max_geometric_error, decimate_last_depth_level, forward_axis, up_axis, workers."""
    started = time.time()
    input_file = params["input_file"]
    output_dir = params["output_dir"]
    depth = int(params.get("depth", 4))
    workers = max(int(params.get("workers") or 1), 1)
    os.makedirs(output_dir, exist_ok=True)

    mesh = parse_obj(input_file)
    if len(mesh.face_v) == 0:
        raise ValueError("The OBJ has no faces")
    rotation = axis_matrix(params.get("forward_axis", "Y"), params.get("up_axis", "Z"))
    mesh.positions = mesh.positions @ rotation.T
    textures = parse_mtl(mtl_paths(input_file, mesh))
    logger.info(
        f"mesh: {len(mesh.positions):,} vertices, {len(mesh.face_v):,} faces, "
        f"{len(mesh.mat_names)} materials, {len(textures)} textures"
    )

    lo = mesh.positions[mesh.face_v.ravel()].min(axis=0)
    hi = mesh.positions[mesh.face_v.ravel()].max(axis=0)
    shift = (lo + hi) / 2.0

    target = int(params.get("tile_faces_target", 10000))
    decimate_last = bool(params.get("decimate_last_depth_level", True))
    jobs = [
        (
            level,
            y,
            x,
            bounds,
            target if (level < depth or decimate_last) else 0,
            max(CAGE / 2**level, 0.05),
        )
        for level, y, x, bounds in tile_grid(lo, hi, depth)
    ]

    _SHARED.clear()
    _SHARED.update(
        mesh=mesh,
        shift=shift,
        output_dir=output_dir,
        centroids=mesh.positions[mesh.face_v].mean(axis=1),
        texture_size=int(params.get("texture_image_size", 512)),
        cache=TextureCache(textures, mesh.mat_names, limit=max(1, 6 // workers)),
    )

    logger.info(f"{len(jobs)} candidate tiles, depth {depth}, {workers} worker(s)")
    if workers == 1:
        results = map(_run_job, jobs)
        pool = None
    else:
        import multiprocessing

        pool = multiprocessing.get_context("fork").Pool(workers)
        results = pool.imap(_run_job, jobs)
    tiles = {}
    try:
        for result in results:
            if result is None:
                continue
            key, tile_lo, tile_hi, stats = result
            tiles[key] = (tile_lo, tile_hi)
            logger.info(
                f"tile {key[0]}_{key[1]}_{key[2]}: {stats['source_faces']:,} -> {stats['faces']:,} faces, "
                f"{stats['bytes'] / 1024:.0f} KB, {stats['color_source']} "
                f"{stats['coverage']:.0%}, {stats['seconds']}s"
            )
    finally:
        if pool is not None:
            pool.close()
            pool.join()
        _SHARED.clear()

    if (0, 0, 0) not in tiles:
        raise ValueError("No tiles were produced from the mesh")

    max_ge = params.get("max_geometric_error")
    if not max_ge:
        max_ge = float(np.linalg.norm(hi - lo)) / 3.0
    root, top_ge = build_tileset(tiles, depth, float(max_ge))
    frame = LocalFrame(
        params.get("longitude", 0), params.get("latitude", 0), params.get("altitude", 0)
    )
    write_tileset(output_dir, root, frame.transform(), top_ge)

    total = sum(
        os.path.getsize(os.path.join(output_dir, f"{level}_{y}_{x}.glb"))
        for level, y, x in tiles
    )
    logger.info(
        f"done: {len(tiles)} tiles, {total / 1e6:.1f} MB, {time.time() - started:.0f}s"
    )
    return {"tiles": len(tiles), "bytes": total, "size": (hi - lo).tolist()}


if __name__ == "__main__":
    # subprocess: Celery prefork children cannot fork a pool, and an OOM kill fails only the task
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    run(json.loads(sys.argv[1]))
