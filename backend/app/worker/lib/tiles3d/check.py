"""Structural checks of a written tileset and its GLB content; returns problems, never raises."""

import json
import os
import struct

import numpy as np

from app.worker.lib.gltf import BIN_CHUNK, GLB_MAGIC, JSON_CHUNK
from app.worker.lib.tiles3d.tileset import region_corners

_COMPONENT_BYTES = {5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4}
_INDEX_DTYPE = {5121: np.uint8, 5123: np.uint16, 5125: np.uint32}
_COMPONENTS = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}
_VOLUME_SIZE = {"box": 12, "region": 6, "sphere": 4}
_TOLERANCE = 1e-3


def check_tileset(folder, entry="tileset.json"):
    problems = []
    _check_tileset_file(os.path.join(folder, entry), problems)
    return problems


def _check_tileset_file(path, problems):
    name = os.path.basename(path)
    try:
        with open(path) as f:
            tileset = json.load(f)
    except (OSError, ValueError) as error:
        problems.append(f"{name}: unreadable ({error})")
        return
    if tileset.get("asset", {}).get("version") not in ("1.0", "1.1"):
        problems.append(f"{name}: asset.version must be 1.0 or 1.1")
    _check_extensions(tileset, name, problems)
    root = tileset.get("root")
    if not isinstance(root, dict):
        problems.append(f"{name}: no root")
        return
    if root.get("refine") not in ("ADD", "REPLACE"):
        problems.append(f"{name}: root needs refine ADD or REPLACE")
    if tileset.get("geometricError", -1) < root.get("geometricError", 0):
        problems.append(f"{name}: tileset geometricError below the root's")
    _check_node(root, None, os.path.dirname(path), f"{name}:root", problems)


def _check_extensions(doc, where, problems):
    missing = set(doc.get("extensionsRequired") or []) - set(
        doc.get("extensionsUsed") or []
    )
    if missing:
        problems.append(f"{where}: extensionsRequired not in extensionsUsed: {missing}")


def _check_node(node, parent, folder, where, problems, transformed=False):
    error = node.get("geometricError")
    if not isinstance(error, (int, float)) or error < 0:
        problems.append(f"{where}: geometricError must be a number >= 0")
        error = 0.0
    elif parent is not None and error > parent["geometricError"] + 1e-9:
        problems.append(
            f"{where}: geometricError {error} above its parent's {parent['geometricError']}"
        )
    if node.get("refine") not in (None, "ADD", "REPLACE"):
        problems.append(f"{where}: refine must be ADD or REPLACE")
    if "transform" in node and not _valid_transform(node["transform"]):
        problems.append(f"{where}: transform must be 16 numbers of an affine matrix")

    volume = node.get("boundingVolume") or {}
    kinds = [k for k in _VOLUME_SIZE if k in volume]
    if len(kinds) != 1 or len(volume[kinds[0]]) != _VOLUME_SIZE[kinds[0]]:
        problems.append(f"{where}: boundingVolume needs one box, region or sphere")
        volume = None
    transformed = transformed or "transform" in node
    # a node transform moves its own volume to a new frame; a region stays in world space
    comparable = "transform" not in node and not (
        volume and "region" in volume and transformed
    )
    if volume and parent is not None and parent.get("volume") and comparable:
        outside = _outside(_volume_points(volume), parent["volume"])
        if outside > _TOLERANCE:
            problems.append(
                f"{where}: boundingVolume outside its parent's by {outside:.3f}"
            )

    uri = (node.get("content") or {}).get("uri")
    if uri:
        path = os.path.join(folder, uri)
        if not os.path.isfile(path):
            problems.append(f"{where}: content {uri} missing")
        elif uri.endswith(".json"):
            _check_tileset_file(path, problems)
        elif uri.endswith(".glb"):
            points = _check_glb(path, problems)
            if volume and "box" in volume and points is not None and len(points):
                outside = _outside(points, volume)
                # uint16 positions snap to 1/65535 of the tile extent
                extent = 2 * np.linalg.norm(
                    np.reshape(volume["box"][3:], (3, 3)), axis=1
                )
                if outside > _TOLERANCE + extent.max() / 65535:
                    problems.append(
                        f"{where}: content {uri} outside its boundingVolume by {outside:.3f}"
                    )

    here = {"geometricError": error, "volume": volume}
    for i, child in enumerate(node.get("children") or []):
        _check_node(child, here, folder, f"{where}/{i}", problems, transformed)


def _valid_transform(m):
    return (
        isinstance(m, list)
        and len(m) == 16
        and all(isinstance(v, (int, float)) for v in m)
        and m[3] == m[7] == m[11] == 0
        and m[15] == 1
    )


def _volume_points(volume):
    if "region" in volume:
        return np.array(region_corners(volume["region"]))
    if "sphere" in volume:
        x, y, z, r = volume["sphere"]
        return np.array([x, y, z]) + r * np.vstack([np.eye(3), -np.eye(3)])
    b = np.array(volume["box"], dtype=float)
    signs = np.array([[i, j, k] for i in (-1, 1) for j in (-1, 1) for k in (-1, 1)])
    return b[:3] + signs @ b[3:].reshape(3, 3)


def _outside(points, volume):
    """Largest distance in metres by which points leave the volume; 0 when inside."""
    if "box" in volume:
        b = np.array(volume["box"], dtype=float)
        axes = b[3:].reshape(3, 3)
        half = np.linalg.norm(axes, axis=1)
        units = axes / np.where(half > 0, half, 1)[:, None]
        local = (np.asarray(points) - b[:3]) @ units.T
        return float(np.max(np.abs(local) - half, initial=0.0))
    if "sphere" in volume:
        x, y, z, r = volume["sphere"]
        d = np.linalg.norm(np.asarray(points) - [x, y, z], axis=1)
        return float(np.max(d - r, initial=0.0))
    # a region in world space cannot be compared with points of another frame
    return 0.0


def _check_glb(path, problems):
    """-> content points in the tile frame (glTF Y-up mapped back to ENU), or None."""
    name = os.path.basename(path)
    with open(path, "rb") as f:
        data = f.read()
    if len(data) < 20:
        problems.append(f"{name}: too short for a GLB")
        return None
    magic, version, total = struct.unpack_from("<III", data)
    if magic != GLB_MAGIC or version != 2 or total != len(data):
        problems.append(f"{name}: bad GLB header")
        return None
    json_length, json_type = struct.unpack_from("<II", data, 12)
    if json_type != JSON_CHUNK:
        problems.append(f"{name}: first chunk is not JSON")
        return None
    try:
        gltf = json.loads(data[20 : 20 + json_length])
    except ValueError:
        problems.append(f"{name}: JSON chunk does not parse")
        return None
    binary = b""
    start = 20 + json_length
    if start < len(data):
        bin_length, bin_type = struct.unpack_from("<II", data, start)
        if bin_type != BIN_CHUNK:
            problems.append(f"{name}: second chunk is not BIN")
        binary = data[start + 8 : start + 8 + bin_length]

    _check_extensions(gltf, name, problems)
    buffers = gltf.get("buffers") or []
    if buffers and buffers[0].get("byteLength", 0) > len(binary):
        problems.append(f"{name}: buffer longer than the BIN chunk")
    views = gltf.get("bufferViews") or []
    for i, view in enumerate(views):
        if view.get("byteOffset", 0) + view.get("byteLength", 0) > len(binary):
            problems.append(f"{name}: bufferView {i} outside the buffer")
    accessors = gltf.get("accessors") or []
    for i, acc in enumerate(accessors):
        if acc.get("bufferView") is None or acc["bufferView"] >= len(views):
            problems.append(f"{name}: accessor {i} has no bufferView")
            continue
        element = _COMPONENT_BYTES.get(acc.get("componentType"), 0) * _COMPONENTS.get(
            acc.get("type"), 0
        )
        if not element:
            problems.append(f"{name}: accessor {i} has an unknown type")
            continue
        view = views[acc["bufferView"]]
        stride = view.get("byteStride", element)
        count = acc.get("count", 0)
        end = acc.get("byteOffset", 0) + (
            stride * (count - 1) + element if count else 0
        )
        if end > view.get("byteLength", 0):
            problems.append(f"{name}: accessor {i} reads past its bufferView")
    for i, image in enumerate(gltf.get("images") or []):
        if image.get("bufferView", len(views)) >= len(views):
            problems.append(f"{name}: image {i} has no bufferView")

    points = []
    for m, mesh in enumerate(gltf.get("meshes") or []):
        for primitive in mesh.get("primitives") or []:
            counts = {
                accessors[a].get("count")
                for a in primitive.get("attributes", {}).values()
                if a < len(accessors)
            }
            if len(counts) > 1:
                problems.append(f"{name}: mesh {m} attributes differ in count")
            index = primitive.get("indices")
            if index is not None and counts:
                top = _max_index(accessors[index], views, binary)
                if top is not None and top >= min(counts):
                    problems.append(f"{name}: mesh {m} index {top} past its vertices")
    scene = (gltf.get("scenes") or [{}])[gltf.get("scene", 0)]
    for root in scene.get("nodes") or []:
        _node_points(gltf, root, np.eye(4), points)
    if not points:
        return None
    yup = np.vstack(points)
    return np.column_stack([yup[:, 0], -yup[:, 2], yup[:, 1]])


def _max_index(acc, views, binary):
    dtype = _INDEX_DTYPE.get(acc.get("componentType"))
    if dtype is None or not acc.get("count"):
        return None
    view = views[acc["bufferView"]]
    offset = view.get("byteOffset", 0) + acc.get("byteOffset", 0)
    if offset + acc["count"] * np.dtype(dtype).itemsize > len(binary):
        return None
    values = np.frombuffer(binary, dtype=dtype, count=acc["count"], offset=offset)
    return int(values.max())


def _node_points(gltf, index, parent, points):
    node = gltf["nodes"][index]
    world = parent @ _node_matrix(node)
    instancing = (node.get("extensions") or {}).get("EXT_mesh_gpu_instancing")
    if instancing:
        acc = gltf["accessors"][instancing["attributes"]["TRANSLATION"]]
        if "min" in acc and "max" in acc:
            points.append(_apply(world, [acc["min"], acc["max"]]))
    elif "mesh" in node:
        for primitive in gltf["meshes"][node["mesh"]]["primitives"]:
            acc = gltf["accessors"][primitive["attributes"]["POSITION"]]
            if "min" in acc and "max" in acc:
                lo, hi = acc["min"], acc["max"]
                corners = [
                    [x, y, z]
                    for x in (lo[0], hi[0])
                    for y in (lo[1], hi[1])
                    for z in (lo[2], hi[2])
                ]
                points.append(_apply(world, corners))
    for child in node.get("children") or []:
        _node_points(gltf, child, world, points)


def _node_matrix(node):
    if "matrix" in node:
        return np.array(node["matrix"], dtype=float).reshape(4, 4).T
    m = np.eye(4)
    x, y, z, w = node.get("rotation", [0, 0, 0, 1])
    m[:3, :3] = [
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ]
    m[:3, :3] *= node.get("scale", [1, 1, 1])
    m[:3, 3] = node.get("translation", [0, 0, 0])
    return m


def _apply(matrix, points):
    p = np.asarray(points, dtype=float)
    return p @ matrix[:3, :3].T + matrix[:3, 3]
