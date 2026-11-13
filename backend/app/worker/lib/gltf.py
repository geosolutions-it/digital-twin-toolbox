"""Shared glTF/GLB building blocks: constants, ENU axis swap, quantization, binary blob, metadata, packing."""

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


def unique_rows(*cols):
    """Row-wise dedupe of equal-length arrays -> (first index per unique row, inverse)."""
    packed = np.concatenate(
        [np.ascontiguousarray(c).view(np.uint8).reshape(len(c), -1) for c in cols],
        axis=1,
    )
    packed = (
        np.ascontiguousarray(packed).view(np.dtype((np.void, packed.shape[1]))).ravel()
    )
    _, first, inverse = np.unique(packed, return_index=True, return_inverse=True)
    return first, inverse.ravel()


def pad_rows(arr, width):
    """(N,k) small ints -> (N,width) bytes so each vertex element stays 4-byte aligned."""
    raw = np.ascontiguousarray(arr).view(np.uint8).reshape(len(arr), -1)
    out = np.zeros((len(arr), width), dtype=np.uint8)
    out[:, : raw.shape[1]] = raw
    return out


def quantize_positions(pos, max_step=0.01):
    """(N,3) glTF positions -> (values, step, origin): uint16 grid when the step stays under
    max_step (KHR_mesh_quantization, undone by node translation/scale), else float32 and step None."""
    pos = np.asarray(pos, dtype=np.float64)
    mn = pos.min(axis=0)
    step = max(float((pos.max(axis=0) - mn).max()) / 65535.0, 1e-9)
    if step > max_step:
        return pos.astype(np.float32), None, mn
    return np.round((pos - mn) / step).astype(np.uint16), step, mn


def dequantize_node(step, origin):
    """Node translation/scale that maps quantized positions back to metres ({} when unquantized)."""
    if step is None:
        return {}
    return {
        "translation": np.asarray(origin, dtype=np.float64).tolist(),
        "scale": [step, step, step],
    }


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


def schema_json(schema):
    """Metadata schema shared by the glb property tables and tileset.json."""
    props = {
        p["name"]: {"type": "SCALAR", "componentType": "FLOAT32"}
        if p["kind"] == "number"
        else {"type": "STRING"}
        for p in schema
    }
    return {"id": "dtt", "classes": {"feature": {"properties": props}}}


def tileset_metadata(features, schema):
    """Top-level tileset.json keys: legacy properties ({} for text), 1.1 schema and statistics."""
    properties, stats = {}, {}
    for prop in schema:
        name = prop["name"]
        values = [
            float(f[name]) for f in features if isinstance(f.get(name), (int, float))
        ]
        if prop["kind"] == "number" and values:
            properties[name] = {"minimum": min(values), "maximum": max(values)}
            stats[name] = {"min": min(values), "max": max(values)}
        else:
            properties[name] = {}
    return {
        "properties": properties,
        "schema": schema_json(schema),
        "statistics": {
            "classes": {"feature": {"count": len(features), "properties": stats}}
        },
    }


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
    table_props = {}
    for prop in schema:
        name, kind = prop["name"], prop["kind"]
        if kind == "number":
            arr = np.array(
                [float(f.get(name) or 0) for f in features], dtype=np.float32
            )
            table_props[name] = {"values": blob.add(arr.tobytes())}
        else:
            strings = [
                "" if f.get(name) is None else str(f.get(name)) for f in features
            ]
            encoded = [s.encode("utf-8") for s in strings]
            offsets = np.zeros(len(encoded) + 1, dtype=np.uint32)
            offsets[1:] = np.cumsum([len(e) for e in encoded])
            table_props[name] = {
                "values": blob.add(b"".join(encoded)),
                "stringOffsets": blob.add(offsets.tobytes()),
            }

    return {
        "schema": schema_json(schema),
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


_SAMPLER = {"magFilter": 9729, "minFilter": 9987, "wrapS": 33071, "wrapT": 33071}


class GltfBuilder:
    """One buffer and its glTF JSON; each method declares the extensions it needs."""

    def __init__(self, generator):
        self.generator = generator
        self.blob = Blob()
        self.accessors, self.materials, self.meshes, self.nodes = [], [], [], []
        self.samplers, self.images, self.textures = [], [], []
        self.extensions = {}
        self.used, self.required = [], []

    def use(self, name, required=False):
        if name not in self.used:
            self.used.append(name)
        if required and name not in self.required:
            self.required.append(name)

    def accessor(
        self,
        data,
        component,
        kind,
        target=None,
        normalized=False,
        stride=None,
        minmax=None,
    ):
        """data: (count, n) array already in the component type; stride pads each row to that many bytes."""
        rows = np.ascontiguousarray(data).reshape(len(data), -1)
        raw = pad_rows(rows, stride) if stride else rows
        view = self.blob.add(raw.tobytes(), target)
        if stride:
            self.blob.views[view]["byteStride"] = stride
        acc = {
            "bufferView": view,
            "componentType": component,
            "count": int(len(rows)),
            "type": kind,
        }
        if normalized:
            acc["normalized"] = True
        if minmax is not None:
            acc["min"], acc["max"] = minmax
        self.accessors.append(acc)
        return len(self.accessors) - 1

    def positions(self, qpos, step):
        """POSITION from quantize_positions output: uint16 rows padded to 8 bytes, or float32."""
        minmax = (qpos.min(axis=0).tolist(), qpos.max(axis=0).tolist())
        if step is None:
            return self.accessor(qpos, FLOAT, "VEC3", ARRAY_BUFFER, minmax=minmax)
        self.use("KHR_mesh_quantization", required=True)
        return self.accessor(
            qpos, UNSIGNED_SHORT, "VEC3", ARRAY_BUFFER, stride=8, minmax=minmax
        )

    def indices(self, indices, vertex_count):
        small = vertex_count <= 65535
        values = np.ascontiguousarray(indices, dtype=np.uint16 if small else np.uint32)
        return self.accessor(
            values.ravel(),
            UNSIGNED_SHORT if small else UNSIGNED_INT,
            "SCALAR",
            ELEMENT_ARRAY_BUFFER,
        )

    def texture(self, image, mime="image/webp"):
        if not self.samplers:
            self.samplers.append(dict(_SAMPLER))
        self.images.append({"bufferView": self.blob.add(image), "mimeType": mime})
        source = len(self.images) - 1
        if mime == "image/webp":
            # WebP is not a core glTF image type
            self.use("EXT_texture_webp", required=True)
            self.textures.append(
                {"sampler": 0, "extensions": {"EXT_texture_webp": {"source": source}}}
            )
        else:
            self.textures.append({"sampler": 0, "source": source})
        return len(self.textures) - 1

    def material(self, base_color=None, texture=None, name=None):
        pbr = {"metallicFactor": 0.0, "roughnessFactor": 1.0}
        if base_color is not None:
            pbr["baseColorFactor"] = list(base_color)
        if texture is not None:
            pbr["baseColorTexture"] = {"index": texture}
        material = {"doubleSided": True, "pbrMetallicRoughness": pbr}
        if name:
            material["name"] = name
        self.materials.append(material)
        return len(self.materials) - 1

    def mesh(self, primitives):
        self.meshes.append({"primitives": primitives})
        return len(self.meshes) - 1

    def node(self, **fields):
        self.nodes.append(fields)
        return len(self.nodes) - 1

    def metadata(self, features, schema):
        self.use("EXT_structural_metadata")
        self.extensions["EXT_structural_metadata"] = metadata(
            self.blob, features, schema
        )

    def glb(self):
        gltf = {
            "asset": {"version": "2.0", "generator": self.generator},
            "scene": 0,
            "scenes": [{"nodes": list(range(len(self.nodes)))}],
            "nodes": self.nodes,
            "meshes": self.meshes,
            "materials": self.materials,
            "accessors": self.accessors,
        }
        for key in ("samplers", "images", "textures", "extensions"):
            if getattr(self, key):
                gltf[key] = getattr(self, key)
        if self.used:
            gltf["extensionsUsed"] = list(self.used)
        if self.required:
            gltf["extensionsRequired"] = list(self.required)
        return pack_glb(gltf, self.blob)


def primitive(attributes, indices, material, extensions=None):
    out = {
        "attributes": attributes,
        "indices": indices,
        "mode": 4,
        "material": material,
    }
    if extensions:
        out["extensions"] = extensions
    return out
