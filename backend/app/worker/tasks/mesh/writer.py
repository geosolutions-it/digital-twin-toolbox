import numpy as np

from app.worker.lib.gltf import (
    ARRAY_BUFFER,
    UNSIGNED_SHORT,
    GltfBuilder,
    dequantize_node,
    enu_to_gltf,
    primitive,
    quantize_positions,
)

# white: 3D Tiles styles multiply it
UNTEXTURED_COLOR = [1.0, 1.0, 1.0, 1.0]


def glb_bytes(
    enu_positions, faces, uvs=None, image=None, mime="image/webp", max_step=float("inf")
):
    """ENU positions and faces -> .glb; uvs have the origin top-left, no image means plain white."""
    qpos, step, origin = quantize_positions(enu_to_gltf(enu_positions), max_step)
    b = GltfBuilder("dtt-mesh")
    attributes = {"POSITION": b.positions(qpos, step)}
    if image is not None:
        quv = np.round(np.clip(uvs, 0.0, 1.0) * 65535).astype(np.uint16)
        attributes["TEXCOORD_0"] = b.accessor(
            quv, UNSIGNED_SHORT, "VEC2", ARRAY_BUFFER, normalized=True
        )
    indices = b.indices(faces, len(qpos))
    if image is not None:
        material = b.material(texture=b.texture(image, mime))
    else:
        material = b.material(UNTEXTURED_COLOR)
    b.node(
        mesh=b.mesh([primitive(attributes, indices, material)]),
        **dequantize_node(step, origin),
    )
    return b.glb()
