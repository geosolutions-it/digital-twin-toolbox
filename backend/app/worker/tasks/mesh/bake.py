import os

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None  # 8k-16k photogrammetry textures trip the bomb check


class TextureCache:
    """Keeps a few decoded source textures resident; large meshes reference hundreds."""

    def __init__(self, textures, mat_names, limit=6):
        self.textures = textures
        self.mat_names = mat_names
        self.limit = limit
        self.cache = {}

    def path(self, mat_id):
        name = self.mat_names[mat_id] if 0 <= mat_id < len(self.mat_names) else None
        path = self.textures.get(name)
        return path if path and os.path.isfile(path) else None

    def get(self, mat_id):
        if mat_id in self.cache:
            return self.cache[mat_id]
        if len(self.cache) >= self.limit:
            self.cache.pop(next(iter(self.cache)))
        path = self.path(mat_id)
        image = np.asarray(Image.open(path).convert("RGB")) if path else None
        self.cache[mat_id] = image
        return image


def sample(image, uv):
    """Nearest-neighbour sample; uv is OBJ convention (origin bottom-left)."""
    height, width = image.shape[:2]
    col = np.clip((np.clip(uv[:, 0], 0, 1) * width).astype(np.int32), 0, width - 1)
    row = np.clip(
        ((1.0 - np.clip(uv[:, 1], 0, 1)) * height).astype(np.int32), 0, height - 1
    )
    return image[row, col]


def rasterize_atlas(atlas_uv, faces, size, chunk=2_000_000, tolerance=0.003):
    """Covered texels of a UV atlas -> (rows, cols, face ids, barycentric weights), or None.
    Row is v * size: glTF UVs start top-left, painting at 1 - v mirrors the render."""
    px = atlas_uv[:, 0].astype(np.float64) * size - 0.5
    py = atlas_uv[:, 1].astype(np.float64) * size - 0.5
    x, y = px[faces], py[faces]
    x0, x1, x2 = x[:, 0], x[:, 1], x[:, 2]
    y0, y1, y2 = y[:, 0], y[:, 1], y[:, 2]

    min_x = np.maximum(np.floor(x.min(axis=1)), 0).astype(np.int64)
    max_x = np.minimum(np.ceil(x.max(axis=1)), size - 1).astype(np.int64)
    min_y = np.maximum(np.floor(y.min(axis=1)), 0).astype(np.int64)
    max_y = np.minimum(np.ceil(y.max(axis=1)), size - 1).astype(np.int64)
    denom = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
    width = max_x - min_x + 1
    height = max_y - min_y + 1
    valid = np.nonzero((width > 0) & (height > 0) & (np.abs(denom) >= 1e-12))[0]
    if len(valid) == 0:
        return None

    a0 = (y1 - y2) / np.where(denom == 0, 1, denom)
    b0 = (x2 - x1) / np.where(denom == 0, 1, denom)
    a1 = (y2 - y0) / np.where(denom == 0, 1, denom)
    b1 = (x0 - x2) / np.where(denom == 0, 1, denom)

    counts = (width * height)[valid]
    bounds = np.cumsum(counts)
    out = ([], [], [], [])
    start = 0
    while start < len(valid):
        base = bounds[start - 1] if start else 0
        stop = max(int(np.searchsorted(bounds, base + chunk, side="right")), start + 1)
        sel = valid[start:stop]
        cnt = counts[start:stop]
        face = np.repeat(sel, cnt)
        offset = np.arange(int(cnt.sum())) - np.repeat(np.cumsum(cnt) - cnt, cnt)
        w = width[face]
        gx = min_x[face] + offset % w
        gy = min_y[face] + offset // w
        dx = gx - x2[face]
        dy = gy - y2[face]
        w0 = a0[face] * dx + b0[face] * dy
        w1 = a1[face] * dx + b1[face] * dy
        w2 = 1.0 - w0 - w1
        inside = (w0 >= -tolerance) & (w1 >= -tolerance) & (w2 >= -tolerance)
        out[0].append(gy[inside])
        out[1].append(gx[inside])
        out[2].append(face[inside].astype(np.int32))
        out[3].append(np.stack([w0[inside], w1[inside], w2[inside]], axis=1))
        start = stop

    rows = np.concatenate(out[0])
    if len(rows) == 0:
        return None
    return rows, np.concatenate(out[1]), np.concatenate(out[2]), np.concatenate(out[3])


def raycast(source_triangles, atlas_positions, atlas_faces, raster, cage):
    """Cast a short ray from each texel along the tile normal back at the source surface.
    source_triangles is (F,3,3) float32. Returns (hit face, barycentric weights, found)."""
    from embreex import rtcore_scene
    from embreex.mesh_construction import TriangleMesh

    scene = rtcore_scene.EmbreeScene()
    TriangleMesh(scene, source_triangles)

    _, _, face_ids, bary = raster
    tri = atlas_positions[atlas_faces[face_ids]]
    position = np.einsum("ij,ijk->ik", bary, tri)
    normal = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    length = np.linalg.norm(normal, axis=1, keepdims=True)
    length[length == 0] = 1.0
    normal = (normal / length).astype(np.float32)
    position = position.astype(np.float32)

    hit_prim = np.full(len(position), -1, dtype=np.int64)
    hit_u = np.zeros(len(position))
    hit_v = np.zeros(len(position))
    for sign in (1.0, -1.0):
        todo = hit_prim < 0
        if not todo.any():
            break
        origins = position[todo] + normal[todo] * (cage * sign)
        result = scene.run(origins, (-normal[todo] * sign).astype(np.float32), output=1)
        prim = result["primID"].astype(np.int64)
        ok = prim >= 0
        index = np.nonzero(todo)[0][ok]
        hit_prim[index] = prim[ok]
        hit_u[index] = result["u"][ok]
        hit_v[index] = result["v"][ok]

    found = hit_prim >= 0
    weights = np.stack([1.0 - hit_u - hit_v, hit_u, hit_v], axis=1)
    return hit_prim, weights, found


def paint_texture(size, raster, hits, src_uv_tri, src_mat, cache):
    """Texels coloured from the source textures, grouped by material -> (rgb, filled)."""
    rows, cols = raster[0], raster[1]
    hit_prim, weights, found = hits
    rgb = np.zeros((size, size, 3), dtype=np.uint8)
    filled = np.zeros((size, size), dtype=bool)
    if not found.any():
        return rgb, filled
    prim = hit_prim[found]
    uv = np.einsum("ij,ijk->ik", weights[found], src_uv_tri[prim])
    mats = src_mat[prim]
    r, c = rows[found], cols[found]
    for mat_id in np.unique(mats):
        image = cache.get(int(mat_id))
        if image is None:
            continue
        pick = mats == mat_id
        rgb[r[pick], c[pick]] = sample(image, uv[pick])
        filled[r[pick], c[pick]] = True
    return rgb, filled


def paint_vertex_color(size, raster, hits, src_color_tri):
    """Texels coloured from interpolated source vertex colours -> (rgb, filled)."""
    rows, cols = raster[0], raster[1]
    hit_prim, weights, found = hits
    rgb = np.zeros((size, size, 3), dtype=np.uint8)
    filled = np.zeros((size, size), dtype=bool)
    if found.any():
        prim = hit_prim[found]
        interp = np.einsum(
            "ij,ijk->ik", weights[found], src_color_tri[prim].astype(np.float64)
        )
        rgb[rows[found], cols[found]] = np.clip(interp, 0, 255).astype(np.uint8)
        filled[rows[found], cols[found]] = True
    return rgb, filled


def dilate(rgb, filled, iterations=4):
    """Bleed colour into unfilled texels so bilinear filtering cannot pull in black."""
    out = rgb.copy()
    mask = filled.copy()
    for _ in range(iterations):
        if mask.all():
            break
        accum = np.zeros(rgb.shape, dtype=np.uint32)
        count = np.zeros(mask.shape, dtype=np.uint32)
        for axis, shift in ((0, 1), (0, -1), (1, 1), (1, -1)):
            accum += (
                np.roll(out, shift, axis=axis)
                * np.roll(mask, shift, axis=axis)[..., None]
            )
            count += np.roll(mask, shift, axis=axis)
        usable = ~mask & (count > 0)
        out[usable] = (accum // np.maximum(count, 1)[..., None])[usable].astype(
            np.uint8
        )
        mask |= usable
    return out
