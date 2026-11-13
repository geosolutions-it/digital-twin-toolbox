"""Bucket point vector + model glb readers for the instance worker.

Points are read with OGR and reprojected to WGS84 (optionally ellipsoidal). Model
glbs are parsed by hand (single-buffer, non-Draco, non-interleaved) into primitives
so the mesh writer can embed and gpu-instance them. No gltf library.
"""

import json
import struct

import numpy as np

from app.worker.lib.geo.ogr import iter_features, open_layer, wgs84_transform
from app.worker.lib.gltf import BIN_CHUNK, GLB_MAGIC, JSON_CHUNK

_DTYPE = {
    5120: np.int8,
    5121: np.uint8,
    5122: np.int16,
    5123: np.uint16,
    5125: np.uint32,
    5126: np.float32,
}
_NCOMP = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


# ---- point vector ---------------------------------------------------------


def read_points(path, to_ellipsoidal=False):
    """(features, (lo, hi)) where each feature is {lonlath, properties}; bounds are
    lon/lat/h min/max for the local frame origin. Non-point geometries are skipped."""
    ds, layer = open_layer(path)
    transform = wgs84_transform(layer, to_ellipsoidal)

    lo = np.array([np.inf, np.inf, np.inf])
    hi = np.array([-np.inf, -np.inf, -np.inf])
    features = []
    for g, props in iter_features(layer, transform, force_3d=True):
        if g.get("type") != "Point":
            continue  # TODO: MultiPoint -> one instance per point
        c = g["coordinates"]
        lonlath = [c[0], c[1], c[2] if len(c) > 2 and c[2] is not None else 0.0]
        arr = np.asarray(lonlath, dtype=np.float64)
        lo = np.minimum(lo, arr)
        hi = np.maximum(hi, arr)
        features.append({"lonlath": lonlath, "properties": props})

    return features, (lo, hi)


# ---- model glb ------------------------------------------------------------


def _parse_glb(path):
    with open(path, "rb") as f:
        data = f.read()
    magic, version, _ = struct.unpack_from("<III", data, 0)
    if magic != GLB_MAGIC:
        raise ValueError(f"{path!r} is not a binary glTF")
    off = 12
    gltf = None
    bin_data = b""
    while off < len(data):
        clen, ctype = struct.unpack_from("<II", data, off)
        off += 8
        chunk = data[off : off + clen]
        if ctype == JSON_CHUNK:
            gltf = json.loads(chunk)
        elif ctype == BIN_CHUNK:
            bin_data = chunk
        off += clen
    if gltf is None:
        raise ValueError(f"{path!r} has no glTF JSON chunk")
    if any("uri" in b for b in gltf.get("buffers", [])):
        raise ValueError(
            "external/base64 buffers unsupported; embed the model in the glb"
        )
    return gltf, bin_data


def _accessor(gltf, bin_data, index):
    acc = gltf["accessors"][index]
    view = gltf["bufferViews"][acc["bufferView"]]
    dtype = np.dtype(_DTYPE[acc["componentType"]])
    ncomp = _NCOMP[acc["type"]]
    stride = view.get("byteStride")
    if stride and stride != ncomp * dtype.itemsize:
        raise ValueError("interleaved accessors unsupported")
    start = view.get("byteOffset", 0) + acc.get("byteOffset", 0)
    length = acc["count"] * ncomp * dtype.itemsize
    arr = np.frombuffer(bin_data[start : start + length], dtype=dtype)
    return arr.reshape(acc["count"], ncomp)


def _quat_to_mat(q):
    x, y, z, w = q
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ],
        dtype=np.float64,
    )


def _node_matrix(node):
    if "matrix" in node:
        return (
            np.array(node["matrix"], dtype=np.float64).reshape(4, 4).T
        )  # glTF is column-major
    t = np.array(node.get("translation", [0, 0, 0]), dtype=np.float64)
    s = np.array(node.get("scale", [1, 1, 1]), dtype=np.float64)
    r = _quat_to_mat(node.get("rotation", [0, 0, 0, 1]))
    m = np.eye(4)
    m[:3, :3] = r * s
    m[:3, 3] = t
    return m


def _primitive(gltf, bin_data, prim, world):
    pos = _accessor(gltf, bin_data, prim["attributes"]["POSITION"]).astype(np.float64)
    pos = (world[:3, :3] @ pos.T).T + world[:3, 3]
    if "NORMAL" in prim["attributes"]:
        nrm = _accessor(gltf, bin_data, prim["attributes"]["NORMAL"]).astype(np.float64)
        nmat = np.linalg.inv(world[:3, :3]).T
        nrm = (nmat @ nrm.T).T
        norms = np.linalg.norm(nrm, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        nrm = nrm / norms
    else:
        nrm = np.zeros_like(pos)  # TODO: derive flat normals when the model omits them
    if "indices" in prim:
        idx = _accessor(gltf, bin_data, prim["indices"]).reshape(-1).astype(np.uint32)
    else:
        idx = np.arange(pos.shape[0], dtype=np.uint32)
    base_color = [1.0, 1.0, 1.0, 1.0]
    mat_idx = prim.get("material")
    if mat_idx is not None:
        pbr = gltf.get("materials", [])[mat_idx].get("pbrMetallicRoughness", {})
        base_color = pbr.get("baseColorFactor", base_color)  # textures ignored
    return {
        "positions": pos.astype(np.float32),
        "normals": nrm.astype(np.float32),
        "indices": idx,
        "base_color": base_color,
    }


def read_model_glb(path):
    """Flatten a model glb to a list of primitives in its own glTF Y-up space,
    node transforms baked. base_color only, textures ignored."""
    gltf, bin_data = _parse_glb(path)
    scene = gltf.get("scene", 0)
    roots = gltf["scenes"][scene].get("nodes", [])
    out = []

    def walk(node_idx, parent):
        node = gltf["nodes"][node_idx]
        world = parent @ _node_matrix(node)
        if "mesh" in node:
            for prim in gltf["meshes"][node["mesh"]]["primitives"]:
                out.append(_primitive(gltf, bin_data, prim, world))
        for child in node.get("children", []):
            walk(child, world)

    for r in roots:
        walk(r, np.eye(4))
    if not out:
        raise ValueError(f"{path!r} has no mesh primitives")
    return {"primitives": out}
