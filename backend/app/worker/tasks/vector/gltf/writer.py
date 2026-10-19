"""Binary glTF (.glb) writer for triangle soups, numpy-packed, no gltf lib.

Input is ENU (Z-up), swapped to glTF Y-up; per-feature properties ride along as
EXT_mesh_features + EXT_structural_metadata for picking.
"""
import json
import struct

import numpy as np

_GLB_MAGIC = 0x46546C67
_JSON_CHUNK = 0x4E4F534A
_BIN_CHUNK = 0x004E4942
_FLOAT = 5126
_ARRAY_BUFFER = 34962


def _flat_normals(positions):
    tris = positions.reshape(-1, 3, 3)
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    length = np.linalg.norm(n, axis=1, keepdims=True)
    length[length == 0] = 1.0
    return np.repeat(n / length, 3, axis=0).astype(np.float32)


def enu_to_gltf(enu):
    """(N,3) east,north,up -> glTF Y-up (east, up, -north) float32."""
    enu = np.asarray(enu, dtype=np.float64)
    out = np.empty_like(enu, dtype=np.float32)
    out[:, 0] = enu[:, 0]
    out[:, 1] = enu[:, 2]
    out[:, 2] = -enu[:, 1]
    return out


def infer_schema(features):
    """Ordered [{name, kind}] over the union of property keys; string wins on conflict."""
    kinds = {}
    for f in features:
        for k, v in (f or {}).items():
            if isinstance(v, str):
                kinds[k] = "string"
            elif kinds.get(k) != "string" and isinstance(v, (int, float, bool)):
                kinds.setdefault(k, "number")
            else:
                kinds.setdefault(k, "string")
    return [{"name": k, "kind": kinds[k]} for k in sorted(kinds)]


class _Blob:
    def __init__(self):
        self.buf = bytearray()
        self.views = []

    def add(self, data, target=None):
        pad = (4 - len(self.buf) % 4) % 4
        self.buf.extend(b"\x00" * pad)
        view = {"buffer": 0, "byteOffset": len(self.buf), "byteLength": len(data)}
        if target:
            view["target"] = target
        self.buf.extend(data)
        self.views.append(view)
        return len(self.views) - 1


def _metadata(blob, features, schema):
    """Build EXT_structural_metadata schema + a single property table."""
    classes_props = {}
    table_props = {}
    for prop in schema:
        name, kind = prop["name"], prop["kind"]
        if kind == "number":
            arr = np.array(
                [float(f.get(name) or 0) for f in features], dtype=np.float32
            )
            classes_props[name] = {"type": "SCALAR", "componentType": "FLOAT32"}
            table_props[name] = {"values": blob.add(arr.tobytes())}
        else:
            strings = [
                "" if f.get(name) is None else str(f.get(name)) for f in features
            ]
            encoded = [s.encode("utf-8") for s in strings]
            offsets = np.zeros(len(encoded) + 1, dtype=np.uint32)
            offsets[1:] = np.cumsum([len(e) for e in encoded])
            classes_props[name] = {"type": "STRING"}
            table_props[name] = {
                "values": blob.add(b"".join(encoded)),
                "stringOffsets": blob.add(offsets.tobytes()),
            }

    return {
        "schema": {"id": "dtt", "classes": {"feature": {"properties": classes_props}}},
        "propertyTables": [
            {"class": "feature", "count": len(features), "properties": table_props}
        ],
    }


def glb_bytes(enu_positions, feature_vertex_counts=None, features=None, schema=None):
    """.glb bytes from an ENU triangle soup; optional per-feature metadata."""
    positions = enu_to_gltf(enu_positions)
    normals = _flat_normals(positions)
    count = positions.shape[0]

    blob = _Blob()
    pos_view = blob.add(positions.tobytes(), _ARRAY_BUFFER)
    nrm_view = blob.add(normals.tobytes(), _ARRAY_BUFFER)

    accessors = [
        {"bufferView": pos_view, "componentType": _FLOAT, "count": count, "type": "VEC3",
         "min": positions.min(axis=0).tolist(), "max": positions.max(axis=0).tolist()},
        {"bufferView": nrm_view, "componentType": _FLOAT, "count": count, "type": "VEC3"},
    ]
    attributes = {"POSITION": 0, "NORMAL": 1}
    primitive = {"attributes": attributes, "mode": 4, "material": 0}
    gltf = {
        "asset": {"version": "2.0", "generator": "dtt-vector"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0}],
        "meshes": [{"primitives": [primitive]}],
        "materials": [{
            "name": "white",
            "doubleSided": True,
            "pbrMetallicRoughness": {
                "baseColorFactor": [1.0, 1.0, 1.0, 1.0],
                "metallicFactor": 0.0,
                "roughnessFactor": 1.0,
            },
        }],
    }

    use_meta = bool(schema) and feature_vertex_counts is not None and features
    if use_meta:
        fids = np.repeat(
            np.arange(len(feature_vertex_counts), dtype=np.float32), feature_vertex_counts
        )
        fid_view = blob.add(fids.tobytes(), _ARRAY_BUFFER)
        accessors.append(
            {"bufferView": fid_view, "componentType": _FLOAT, "count": count, "type": "SCALAR"}
        )
        attributes["_FEATURE_ID_0"] = len(accessors) - 1
        primitive["extensions"] = {
            "EXT_mesh_features": {
                "featureIds": [
                    {"featureCount": len(feature_vertex_counts), "attribute": 0,
                     "propertyTable": 0}
                ]
            }
        }
        gltf["extensionsUsed"] = ["EXT_mesh_features", "EXT_structural_metadata"]
        gltf["extensions"] = {"EXT_structural_metadata": _metadata(blob, features, schema)}

    bin_chunk = bytes(blob.buf)
    pad = (4 - len(bin_chunk) % 4) % 4
    bin_chunk += b"\x00" * pad

    gltf["accessors"] = accessors
    gltf["bufferViews"] = blob.views
    gltf["buffers"] = [{"byteLength": len(bin_chunk)}]

    json_chunk = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    jpad = (4 - len(json_chunk) % 4) % 4
    json_chunk += b" " * jpad

    total = 12 + 8 + len(json_chunk) + 8 + len(bin_chunk)
    out = bytearray()
    out += struct.pack("<III", _GLB_MAGIC, 2, total)
    out += struct.pack("<II", len(json_chunk), _JSON_CHUNK) + json_chunk
    out += struct.pack("<II", len(bin_chunk), _BIN_CHUNK) + bin_chunk
    return bytes(out)


def write_glb(path, enu_positions, feature_vertex_counts=None, features=None, schema=None):
    with open(path, "wb") as f:
        f.write(glb_bytes(enu_positions, feature_vertex_counts, features, schema))
