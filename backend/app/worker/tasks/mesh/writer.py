"""Textured tile .glb: local ENU positions (quantized), atlas UVs and a WebP base colour."""
import numpy as np

from app.worker.common.gltf import (
    ARRAY_BUFFER, ELEMENT_ARRAY_BUFFER, UNSIGNED_INT, UNSIGNED_SHORT,
    Blob, add_positions, dequantize_node, enu_to_gltf, pack_glb, quantize_positions,
)

# white: 3D Tiles styles multiply it
UNTEXTURED_COLOR = [1.0, 1.0, 1.0, 1.0]


def glb_bytes(enu_positions, faces, uvs=None, image=None, mime="image/webp", max_step=float("inf")):
    """ENU positions and faces -> .glb; uvs have the origin top-left, no image means flat grey.
    Positions are always uint16 (1/65535 of the tile extent beats Blender's 14-bit Draco)."""
    qpos, step, origin = quantize_positions(enu_to_gltf(enu_positions), max_step)
    blob = Blob()
    accessors = [add_positions(blob, qpos, step)]
    attributes = {"POSITION": 0}

    if image is not None:
        quv = np.round(np.clip(uvs, 0.0, 1.0) * 65535).astype(np.uint16)
        view = blob.add(quv.tobytes(), ARRAY_BUFFER)
        accessors.append({"bufferView": view, "componentType": UNSIGNED_SHORT, "normalized": True,
                          "count": int(len(quv)), "type": "VEC2"})
        attributes["TEXCOORD_0"] = 1

    small = len(qpos) <= 65535
    indices = np.ascontiguousarray(faces, dtype=np.uint16 if small else np.uint32).ravel()
    view = blob.add(indices.tobytes(), ELEMENT_ARRAY_BUFFER)
    accessors.append({"bufferView": view, "componentType": UNSIGNED_SHORT if small else UNSIGNED_INT,
                      "count": int(len(indices)), "type": "SCALAR"})

    pbr = {"metallicFactor": 0.0, "roughnessFactor": 1.0}
    used, required = ["KHR_mesh_quantization"], ["KHR_mesh_quantization"]
    gltf = {
        "asset": {"version": "2.0", "generator": "dtt-mesh"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0, **dequantize_node(step, origin)}],
        "meshes": [{"primitives": [{
            "attributes": attributes, "indices": len(accessors) - 1, "material": 0, "mode": 4,
        }]}],
        "materials": [{"pbrMetallicRoughness": pbr, "doubleSided": True}],
        "accessors": accessors,
    }
    if image is not None:
        pbr["baseColorTexture"] = {"index": 0}
        gltf["samplers"] = [{"magFilter": 9729, "minFilter": 9987, "wrapS": 33071, "wrapT": 33071}]
        gltf["images"] = [{"bufferView": blob.add(image), "mimeType": mime}]
        if mime == "image/webp":
            # WebP is not a core glTF image type
            gltf["textures"] = [{"sampler": 0, "extensions": {"EXT_texture_webp": {"source": 0}}}]
            used.append("EXT_texture_webp")
            required.append("EXT_texture_webp")
        else:
            gltf["textures"] = [{"sampler": 0, "source": 0}]
    else:
        pbr["baseColorFactor"] = UNTEXTURED_COLOR
    gltf["extensionsUsed"] = used
    gltf["extensionsRequired"] = required
    return pack_glb(gltf, blob)
