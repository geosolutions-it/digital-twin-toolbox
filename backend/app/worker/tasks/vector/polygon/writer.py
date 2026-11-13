"""Mesh .glb writer: ENU triangle soup -> indexed, quantized glTF with optional per-feature metadata."""

import numpy as np

from app.worker.common.gltf import (
    ARRAY_BUFFER,
    BYTE,
    ELEMENT_ARRAY_BUFFER,
    FLOAT,
    UNSIGNED_INT,
    UNSIGNED_SHORT,
    Blob,
    add_positions,
    dequantize_node,
    enu_to_gltf,
    metadata,
    pack_glb,
    pad_rows,
    quantize_positions,
    unique_rows,
)


def glb_bytes(
    enu_positions,
    feature_vertex_counts=None,
    features=None,
    schema=None,
    max_step=0.01,
    texturer=None,
    detail=0.0,
    base_color=None,
    size_limit=None,
):
    """Indexed .glb (KHR_mesh_quantization): uint16 positions unless the step exceeds max_step,
    int8 normals, uint16 feature ids; metadata only when schema is given. None when the untextured
    tile exceeds size_limit. texturer: .classify(enu_tris) -> bool per triangle, and
    texturer(enu_tris, detail_m) -> (uv top-left origin, WebP bytes) or None."""
    use_meta = bool(schema) and feature_vertex_counts is not None and features
    nfeat = len(feature_vertex_counts) if use_meta else 0
    fid_dtype = np.uint16 if nfeat <= 65535 else np.float32
    fids = (
        np.repeat(np.arange(nfeat, dtype=fid_dtype), feature_vertex_counts)
        if use_meta
        else None
    )

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

    enu_tris = (
        np.asarray(enu_positions, dtype=np.float64).reshape(-1, 3, 3)[keep]
        if texturer
        else None
    )
    # vertices merge as they will once UVs, which follow the triangle class, are added
    cls = (
        np.repeat(texturer.classify(enu_tris).astype(np.uint8), 3) if texturer else None
    )

    qpos, step, mn = quantize_positions(pos, max_step)

    first, inverse = unique_rows(*(c for c in (qpos, nrm, cls, fids) if c is not None))
    vpos, vnrm = qpos[first], nrm[first]
    nverts = len(first)
    indices = inverse.astype(np.uint16 if nverts <= 65535 else np.uint32)

    blob = Blob()
    pos_acc = add_positions(blob, vpos, step)
    nrm_view = blob.add(pad_rows(vnrm, 4).tobytes(), ARRAY_BUFFER)
    blob.views[nrm_view]["byteStride"] = 4
    idx_view = blob.add(indices.tobytes(), ELEMENT_ARRAY_BUFFER)

    accessors = [
        pos_acc,
        {
            "bufferView": nrm_view,
            "componentType": BYTE,
            "normalized": True,
            "count": nverts,
            "type": "VEC3",
        },
        {
            "bufferView": idx_view,
            "componentType": UNSIGNED_SHORT
            if indices.dtype == np.uint16
            else UNSIGNED_INT,
            "count": count,
            "type": "SCALAR",
        },
    ]
    attributes = {"POSITION": 0, "NORMAL": 1}
    primitive = {"attributes": attributes, "indices": 2, "mode": 4, "material": 0}
    pbr = {
        "baseColorFactor": list(base_color or [1.0, 1.0, 1.0, 1.0]),
        "metallicFactor": 0.0,
        "roughnessFactor": 1.0,
    }
    node = {"mesh": 0, **dequantize_node(step, mn)}
    gltf = {
        "asset": {"version": "2.0", "generator": "dtt-vector"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [node],
        "meshes": [{"primitives": [primitive]}],
        "materials": [
            {"name": "surface", "doubleSided": True, "pbrMetallicRoughness": pbr}
        ],
    }
    used = ["KHR_mesh_quantization"]
    required = ["KHR_mesh_quantization"]  # int8 normals need it too

    if use_meta:
        vfid = fids[first]
        if fid_dtype == np.uint16:
            fid_view = blob.add(pad_rows(vfid[:, None], 4).tobytes(), ARRAY_BUFFER)
            blob.views[fid_view]["byteStride"] = 4
            fid_type = UNSIGNED_SHORT
        else:
            fid_view = blob.add(vfid.tobytes(), ARRAY_BUFFER)
            fid_type = FLOAT
        accessors.append(
            {
                "bufferView": fid_view,
                "componentType": fid_type,
                "count": nverts,
                "type": "SCALAR",
            }
        )
        attributes["_FEATURE_ID_0"] = len(accessors) - 1
        primitive["extensions"] = {
            "EXT_mesh_features": {
                "featureIds": [
                    {"featureCount": nfeat, "attribute": 0, "propertyTable": 0}
                ]
            }
        }
        used += ["EXT_mesh_features", "EXT_structural_metadata"]
        gltf["extensions"] = {
            "EXT_structural_metadata": metadata(blob, features, schema)
        }

    gltf["extensionsUsed"] = used
    gltf["extensionsRequired"] = required
    gltf["accessors"] = accessors
    data = pack_glb(gltf, blob)
    if size_limit is not None and len(data) > size_limit:
        return None
    texture = texturer(enu_tris, detail) if texturer else None
    if not texture:
        return data

    quv = np.round(np.clip(texture[0], 0.0, 1.0) * 65535).astype(np.uint16)
    uv_view = blob.add(quv[first].tobytes(), ARRAY_BUFFER)
    accessors.append(
        {
            "bufferView": uv_view,
            "componentType": UNSIGNED_SHORT,
            "normalized": True,
            "count": nverts,
            "type": "VEC2",
        }
    )
    attributes["TEXCOORD_0"] = len(accessors) - 1
    pbr["baseColorFactor"] = [1.0, 1.0, 1.0, 1.0]
    pbr["baseColorTexture"] = {"index": 0}
    gltf["samplers"] = [
        {"magFilter": 9729, "minFilter": 9987, "wrapS": 33071, "wrapT": 33071}
    ]
    gltf["images"] = [{"bufferView": blob.add(texture[1]), "mimeType": "image/webp"}]
    # WebP is not a core glTF image type
    gltf["textures"] = [
        {"sampler": 0, "extensions": {"EXT_texture_webp": {"source": 0}}}
    ]
    used.append("EXT_texture_webp")
    required.append("EXT_texture_webp")
    return pack_glb(gltf, blob)
