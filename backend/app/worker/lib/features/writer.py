import numpy as np

from app.worker.lib.gltf import (
    ARRAY_BUFFER,
    BYTE,
    FLOAT,
    UNSIGNED_SHORT,
    GltfBuilder,
    dequantize_node,
    enu_to_gltf,
    primitive,
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
    """ENU triangle soup -> .glb, feature ids and metadata when schema is given; None over size_limit.
    texturer: .classify(tris) -> roof mask, and texturer(tris, detail_m) -> (uv top-left, WebP) or None."""
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

    b = GltfBuilder("dtt-vector")
    attributes = {"POSITION": b.positions(vpos, step)}
    # int8 normals need KHR_mesh_quantization even with float positions
    b.use("KHR_mesh_quantization", required=True)
    attributes["NORMAL"] = b.accessor(
        vnrm, BYTE, "VEC3", ARRAY_BUFFER, normalized=True, stride=4
    )
    indices = b.indices(inverse, nverts)
    material = b.material(base_color or [1.0, 1.0, 1.0, 1.0], name="surface")
    extensions = None
    if use_meta:
        vfid = fids[first]
        if fid_dtype == np.uint16:
            fid = b.accessor(vfid, UNSIGNED_SHORT, "SCALAR", ARRAY_BUFFER, stride=4)
        else:
            fid = b.accessor(vfid, FLOAT, "SCALAR", ARRAY_BUFFER)
        attributes["_FEATURE_ID_0"] = fid
        extensions = {
            "EXT_mesh_features": {
                "featureIds": [
                    {"featureCount": nfeat, "attribute": 0, "propertyTable": 0}
                ]
            }
        }
        b.use("EXT_mesh_features")
        b.metadata(features, schema)
    b.node(
        mesh=b.mesh([primitive(attributes, indices, material, extensions)]),
        **dequantize_node(step, mn),
    )

    data = b.glb()
    if size_limit is not None and len(data) > size_limit:
        return None
    texture = texturer(enu_tris, detail) if texturer else None
    if not texture:
        return data

    quv = np.round(np.clip(texture[0], 0.0, 1.0) * 65535).astype(np.uint16)
    attributes["TEXCOORD_0"] = b.accessor(
        quv[first], UNSIGNED_SHORT, "VEC2", ARRAY_BUFFER, normalized=True
    )
    b.materials[material]["pbrMetallicRoughness"].update(
        baseColorFactor=[1.0, 1.0, 1.0, 1.0],
        baseColorTexture={"index": b.texture(texture[1])},
    )
    return b.glb()
