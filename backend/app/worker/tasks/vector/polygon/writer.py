"""Mesh .glb writer: ENU triangle soup -> indexed, quantized glTF with optional per-feature metadata."""
import numpy as np

from app.worker.tasks.vector.gltf.glb import (
    ARRAY_BUFFER, BYTE, ELEMENT_ARRAY_BUFFER, FLOAT, UNSIGNED_INT, UNSIGNED_SHORT,
    Blob, enu_to_gltf, metadata, pack_glb,
)


def _unique_rows(*cols):
    """Row-wise dedupe of equal-length arrays -> (first index per unique row, inverse)."""
    packed = np.concatenate([np.ascontiguousarray(c).view(np.uint8).reshape(len(c), -1) for c in cols], axis=1)
    packed = np.ascontiguousarray(packed).view(np.dtype((np.void, packed.shape[1]))).ravel()
    _, first, inverse = np.unique(packed, return_index=True, return_inverse=True)
    return first, inverse.ravel()


def _pad_rows(arr, width):
    """(N,k) small ints -> (N,width) bytes so each vertex element stays 4-byte aligned."""
    raw = np.ascontiguousarray(arr).view(np.uint8).reshape(len(arr), -1)
    out = np.zeros((len(arr), width), dtype=np.uint8)
    out[:, :raw.shape[1]] = raw
    return out


def glb_bytes(enu_positions, feature_vertex_counts=None, features=None, schema=None, max_step=0.01):
    """Indexed .glb (KHR_mesh_quantization): uint16 positions unless the step exceeds max_step,
    int8 normals, uint16 feature ids; metadata only when schema is given."""
    use_meta = bool(schema) and feature_vertex_counts is not None and features
    nfeat = len(feature_vertex_counts) if use_meta else 0
    fid_dtype = np.uint16 if nfeat <= 65535 else np.float32
    fids = np.repeat(np.arange(nfeat, dtype=fid_dtype), feature_vertex_counts) if use_meta else None

    pos = enu_to_gltf(enu_positions).astype(np.float64)
    tris = pos.reshape(-1, 3, 3)
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    length = np.linalg.norm(n, axis=1, keepdims=True)
    keep = length[:, 0] > 1e-9  # zero-area triangles have no normal
    tris, n, length = tris[keep], n[keep], length[keep]
    pos = tris.reshape(-1, 3)
    if fids is not None:
        fids = fids.reshape(-1, 3)[keep].ravel()
    count = pos.shape[0]
    nrm = np.repeat(np.round(n / length * 127), 3, axis=0).astype(np.int8)

    mn = pos.min(axis=0)
    step = max(float((pos.max(axis=0) - mn).max()) / 65535.0, 1e-9)
    quantize = step <= max_step
    qpos = np.round((pos - mn) / step).astype(np.uint16) if quantize else pos.astype(np.float32)

    first, inverse = _unique_rows(*(c for c in (qpos, nrm, fids) if c is not None))
    vpos, vnrm = qpos[first], nrm[first]
    nverts = len(first)
    indices = inverse.astype(np.uint16 if nverts <= 65535 else np.uint32)

    blob = Blob()
    if quantize:
        pos_view = blob.add(_pad_rows(vpos, 8).tobytes(), ARRAY_BUFFER)
        blob.views[pos_view]["byteStride"] = 8
        pos_acc = {"componentType": UNSIGNED_SHORT,
                   "min": vpos.min(axis=0).tolist(), "max": vpos.max(axis=0).tolist()}
    else:
        pos_view = blob.add(vpos.tobytes(), ARRAY_BUFFER)
        pos_acc = {"componentType": FLOAT,
                   "min": vpos.min(axis=0).tolist(), "max": vpos.max(axis=0).tolist()}
    nrm_view = blob.add(_pad_rows(vnrm, 4).tobytes(), ARRAY_BUFFER)
    blob.views[nrm_view]["byteStride"] = 4
    idx_view = blob.add(indices.tobytes(), ELEMENT_ARRAY_BUFFER)

    accessors = [
        {"bufferView": pos_view, "count": nverts, "type": "VEC3", **pos_acc},
        {"bufferView": nrm_view, "componentType": BYTE, "normalized": True, "count": nverts, "type": "VEC3"},
        {"bufferView": idx_view, "componentType": UNSIGNED_SHORT if indices.dtype == np.uint16 else UNSIGNED_INT,
         "count": count, "type": "SCALAR"},
    ]
    attributes = {"POSITION": 0, "NORMAL": 1}
    primitive = {"attributes": attributes, "indices": 2, "mode": 4, "material": 0}
    node = {"mesh": 0}
    if quantize:
        node["translation"] = mn.tolist()
        node["scale"] = [step, step, step]
    gltf = {
        "asset": {"version": "2.0", "generator": "dtt-vector"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [node],
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
    used = ["KHR_mesh_quantization"]

    if use_meta:
        vfid = fids[first]
        if fid_dtype == np.uint16:
            fid_view = blob.add(_pad_rows(vfid[:, None], 4).tobytes(), ARRAY_BUFFER)
            blob.views[fid_view]["byteStride"] = 4
            fid_type = UNSIGNED_SHORT
        else:
            fid_view = blob.add(vfid.tobytes(), ARRAY_BUFFER)
            fid_type = FLOAT
        accessors.append({"bufferView": fid_view, "componentType": fid_type, "count": nverts, "type": "SCALAR"})
        attributes["_FEATURE_ID_0"] = len(accessors) - 1
        primitive["extensions"] = {
            "EXT_mesh_features": {
                "featureIds": [{"featureCount": nfeat, "attribute": 0, "propertyTable": 0}]
            }
        }
        used += ["EXT_mesh_features", "EXT_structural_metadata"]
        gltf["extensions"] = {"EXT_structural_metadata": metadata(blob, features, schema)}

    gltf["extensionsUsed"] = used
    gltf["extensionsRequired"] = ["KHR_mesh_quantization"]  # int8 normals need it too

    gltf["accessors"] = accessors
    return pack_glb(gltf, blob)
