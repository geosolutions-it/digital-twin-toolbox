"""Each model mesh is stored once and placed with EXT_mesh_gpu_instancing; properties per instance."""

import numpy as np

from app.worker.lib.gltf import (
    ARRAY_BUFFER,
    ELEMENT_ARRAY_BUFFER,
    FLOAT,
    UNSIGNED_INT,
    GltfBuilder,
    enu_to_gltf,
    primitive,
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
    b = GltfBuilder("dtt-instance")
    b.use("EXT_mesh_gpu_instancing")
    b.use("EXT_instance_features")

    def floats(arr, kind, target=None, minmax=False):
        arr = arr.astype(np.float32)
        bounds = (
            (arr.min(axis=0).tolist(), arr.max(axis=0).tolist()) if minmax else None
        )
        return b.accessor(arr, FLOAT, kind, target, minmax=bounds)

    offset = 0
    for g in groups:
        primitives = []
        for prim in g["mesh"]["primitives"]:
            attributes = {
                "POSITION": floats(
                    prim["positions"], "VEC3", ARRAY_BUFFER, minmax=True
                ),
                "NORMAL": floats(prim["normals"], "VEC3", ARRAY_BUFFER),
            }
            indices = b.accessor(
                prim["indices"].astype(np.uint32),
                UNSIGNED_INT,
                "SCALAR",
                ELEMENT_ARRAY_BUFFER,
            )
            material = b.material(prim.get("base_color", [1.0, 1.0, 1.0, 1.0]))
            primitives.append(primitive(attributes, indices, material))
        mesh = b.mesh(primitives)

        k = g["translations"].shape[0]
        scales = np.repeat(
            np.asarray(g["scales"], dtype=np.float32)[:, None], 3, axis=1
        )
        instancing = {
            "TRANSLATION": floats(enu_to_gltf(g["translations"]), "VEC3", minmax=True),
            "ROTATION": floats(heading_to_quat(g["headings"]), "VEC4"),
            "SCALE": floats(scales, "VEC3"),
            "_FEATURE_ID_0": floats(
                np.arange(offset, offset + k).reshape(-1, 1), "SCALAR"
            ),
        }
        b.node(
            mesh=mesh,
            extensions={
                "EXT_mesh_gpu_instancing": {"attributes": instancing},
                "EXT_instance_features": {
                    "featureIds": [
                        {"featureCount": k, "attribute": 0, "propertyTable": 0}
                    ]
                },
            },
        )
        offset += k

    if schema and features:
        b.metadata(features, schema)
    with open(path, "wb") as f:
        f.write(b.glb())
