"""Instanced .glb writer: embeds each model mesh once and replicates it with
EXT_mesh_gpu_instancing; per-instance properties ride along via EXT_instance_features
+ EXT_structural_metadata for picking.
"""
import numpy as np

from app.worker.tasks.vector.gltf.glb import (
    ARRAY_BUFFER, ELEMENT_ARRAY_BUFFER, FLOAT, UNSIGNED_INT, Blob, enu_to_gltf, metadata, pack_glb,
)


def heading_to_quat(deg):
    """(K,) heading degrees about local up -> (K,4) glTF quaternion about Y (up)."""
    half = np.radians(np.asarray(deg, dtype=np.float64)) / 2.0
    q = np.zeros((half.shape[0], 4), dtype=np.float32)
    q[:, 1] = np.sin(half)  # TODO: confirm sign/axis against a north-aligned model
    q[:, 3] = np.cos(half)
    return q


def write_instanced_glb(path, groups, features, schema):
    """groups: list of {mesh, translations(K,3 enu), headings(K), scales(K)}; one gpu
    instanced node per group. features/schema build a single tile-wide property table."""
    blob = Blob()
    accessors, materials, meshes, nodes = [], [], [], []

    def accessor(arr, comp, atype, target=None, minmax=False):
        view = blob.add(arr.tobytes(), target)
        acc = {"bufferView": view, "componentType": comp, "count": int(arr.shape[0]), "type": atype}
        if minmax:
            acc["min"] = arr.min(axis=0).tolist()
            acc["max"] = arr.max(axis=0).tolist()
        accessors.append(acc)
        return len(accessors) - 1

    offset = 0
    for g in groups:
        primitives = []
        for prim in g["mesh"]["primitives"]:
            pa = accessor(prim["positions"].astype(np.float32), FLOAT, "VEC3", ARRAY_BUFFER, minmax=True)
            na = accessor(prim["normals"].astype(np.float32), FLOAT, "VEC3", ARRAY_BUFFER)
            ia = accessor(prim["indices"].astype(np.uint32), UNSIGNED_INT, "SCALAR", ELEMENT_ARRAY_BUFFER)
            materials.append({
                "doubleSided": True,
                "pbrMetallicRoughness": {
                    "baseColorFactor": prim.get("base_color", [1.0, 1.0, 1.0, 1.0]),
                    "metallicFactor": 0.0,
                    "roughnessFactor": 1.0,
                },
            })
            primitives.append({"attributes": {"POSITION": pa, "NORMAL": na},
                               "indices": ia, "material": len(materials) - 1, "mode": 4})
        meshes.append({"primitives": primitives})

        k = g["translations"].shape[0]
        tr = enu_to_gltf(g["translations"])
        rot = heading_to_quat(g["headings"])
        sc = np.repeat(np.asarray(g["scales"], dtype=np.float32)[:, None], 3, axis=1)
        fid = np.arange(offset, offset + k, dtype=np.float32).reshape(-1, 1)
        ta = accessor(tr, FLOAT, "VEC3", minmax=True)
        ra = accessor(rot, FLOAT, "VEC4")
        sa = accessor(sc, FLOAT, "VEC3")
        fa = accessor(fid, FLOAT, "SCALAR")
        nodes.append({
            "mesh": len(meshes) - 1,
            "extensions": {
                "EXT_mesh_gpu_instancing": {
                    "attributes": {"TRANSLATION": ta, "ROTATION": ra, "SCALE": sa, "_FEATURE_ID_0": fa}
                },
                "EXT_instance_features": {
                    "featureIds": [{"featureCount": k, "attribute": 0, "propertyTable": 0}]
                },
            },
        })
        offset += k

    ext_used = ["EXT_mesh_gpu_instancing", "EXT_instance_features"]
    gltf = {
        "asset": {"version": "2.0", "generator": "dtt-instance"},
        "scene": 0,
        "scenes": [{"nodes": list(range(len(nodes)))}],
        "nodes": nodes,
        "meshes": meshes,
        "materials": materials,
        "accessors": accessors,
    }
    if schema and features:
        gltf["extensions"] = {"EXT_structural_metadata": metadata(blob, features, schema)}
        ext_used.append("EXT_structural_metadata")
    gltf["extensionsUsed"] = ext_used

    with open(path, "wb") as f:
        f.write(pack_glb(gltf, blob))
