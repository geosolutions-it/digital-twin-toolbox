"""Shared glTF/GLB building blocks: constants, ENU axis swap, binary blob, metadata, packing."""
import json
import struct

import numpy as np

GLB_MAGIC = 0x46546C67
JSON_CHUNK = 0x4E4F534A
BIN_CHUNK = 0x004E4942
BYTE = 5120
UNSIGNED_SHORT = 5123
UNSIGNED_INT = 5125
FLOAT = 5126
ARRAY_BUFFER = 34962
ELEMENT_ARRAY_BUFFER = 34963


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


class Blob:
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


def metadata(blob, features, schema):
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


def pack_glb(gltf, blob):
    """Attach the blob as buffer 0 and pack glTF JSON + binary into .glb bytes."""
    bin_chunk = bytes(blob.buf)
    bin_chunk += b"\x00" * ((4 - len(bin_chunk) % 4) % 4)
    gltf["bufferViews"] = blob.views
    gltf["buffers"] = [{"byteLength": len(bin_chunk)}]
    json_chunk = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    json_chunk += b" " * ((4 - len(json_chunk) % 4) % 4)
    total = 12 + 8 + len(json_chunk) + 8 + len(bin_chunk)
    out = bytearray()
    out += struct.pack("<III", GLB_MAGIC, 2, total)
    out += struct.pack("<II", len(json_chunk), JSON_CHUNK) + json_chunk
    out += struct.pack("<II", len(bin_chunk), BIN_CHUNK) + bin_chunk
    return bytes(out)
