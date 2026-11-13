import json
import struct
from io import BytesIO

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("xatlas")
pytest.importorskip("embreex")
pytest.importorskip("fast_simplification")

from PIL import Image  # noqa: E402

from app.worker.common.geo import LocalFrame  # noqa: E402
from app.worker.tasks.mesh import tiler  # noqa: E402
from app.worker.tasks.mesh.bake import rasterize_atlas  # noqa: E402
from app.worker.tasks.mesh.reader import axis_matrix, parse_obj  # noqa: E402

SIZE_X, SIZE_Y = 60.0, 40.0
TEXTURE = 256


def _write_textured_obj(folder, n=80):
    """Wavy grid, UVs spanning the extent; texture R encodes u and G encodes v, so the
    expected colour of any surface point is known from its position."""
    xs = np.linspace(0, SIZE_X, n)
    ys = np.linspace(0, SIZE_Y, n)
    gx, gy = np.meshgrid(xs, ys)
    gz = 2.0 * np.sin(gx / 7.0) * np.cos(gy / 5.0)
    lines = ["mtllib grid.mtl"]
    lines += [f"v {x:.4f} {y:.4f} {z:.4f}" for x, y, z in zip(gx.ravel(), gy.ravel(), gz.ravel(), strict=True)]
    lines += [f"vt {x / SIZE_X:.6f} {y / SIZE_Y:.6f}" for x, y in zip(gx.ravel(), gy.ravel(), strict=True)]
    lines.append("usemtl grid")
    for j in range(n - 1):
        for i in range(n - 1):
            a = j * n + i + 1
            b, c, d = a + 1, a + n + 1, a + n
            if (i + j) % 7 == 0:
                lines.append(f"f {a}/{a}/1 {b}/{b}/1 {c}/{c}/1 {d}/{d}/1")
            else:
                lines.append(f"f {a}/{a}/1 {b}/{b}/1 {c}/{c}/1")
                lines.append(f"f {a}/{a}/1 {c}/{c}/1 {d}/{d}/1")
    (folder / "grid.obj").write_text("\n".join(lines) + "\n")
    (folder / "grid.mtl").write_text("newmtl grid\nmap_Kd grid.png\n")

    # OBJ uv origin is bottom-left
    u = (np.arange(TEXTURE) + 0.5) / TEXTURE
    v = 1.0 - (np.arange(TEXTURE) + 0.5) / TEXTURE
    img = np.zeros((TEXTURE, TEXTURE, 3), np.uint8)
    img[..., 0] = (u[None, :] * 255).astype(np.uint8)
    img[..., 1] = (v[:, None] * 255).astype(np.uint8)
    Image.fromarray(img).save(folder / "grid.png")
    return folder / "grid.obj"


def _read_glb(path):
    data = path.read_bytes()
    json_len = struct.unpack_from("<I", data, 12)[0]
    gltf = json.loads(data[20:20 + json_len])
    binary = data[20 + json_len + 8:]

    def accessor(i):
        acc = gltf["accessors"][i]
        view = gltf["bufferViews"][acc["bufferView"]]
        dtype = {5123: np.uint16, 5125: np.uint32, 5126: np.float32}[acc["componentType"]]
        width = {"SCALAR": 1, "VEC2": 2, "VEC3": 3}[acc["type"]]
        item = np.dtype(dtype).itemsize
        stride = view.get("byteStride", item * width)
        raw = np.frombuffer(binary, np.uint8, count=view["byteLength"], offset=view["byteOffset"])
        rows = np.lib.stride_tricks.as_strided(raw, (acc["count"], width * item), (stride, 1))
        out = np.ascontiguousarray(rows).view(dtype).reshape(acc["count"], width).astype(np.float64)
        if acc.get("normalized"):
            out /= np.iinfo(dtype).max
        return out

    prim = gltf["meshes"][0]["primitives"][0]
    node = gltf["nodes"][0]
    pos = accessor(prim["attributes"]["POSITION"])
    pos = pos * np.array(node.get("scale", [1, 1, 1])) + np.array(node.get("translation", [0, 0, 0]))
    enu = np.stack([pos[:, 0], -pos[:, 2], pos[:, 1]], axis=1)
    faces = accessor(prim["indices"]).astype(np.int64).reshape(-1, 3)
    uv = image = None
    if "TEXCOORD_0" in prim["attributes"]:
        uv = accessor(prim["attributes"]["TEXCOORD_0"])
        img = gltf["images"][0]
        view = gltf["bufferViews"][img["bufferView"]]
        image = np.asarray(Image.open(BytesIO(binary[view["byteOffset"]:view["byteOffset"] + view["byteLength"]])).convert("RGB"))
    return gltf, enu, faces, uv, image


@pytest.fixture(scope="module")
def tiled(tmp_path_factory):
    folder = tmp_path_factory.mktemp("mesh")
    obj = _write_textured_obj(folder)
    out = folder / "tiles"
    tiler.run({
        "input_file": str(obj), "output_dir": str(out), "latitude": 45.8, "longitude": 13.5,
        "altitude": 10.0, "depth": 1, "tile_faces_target": 2000, "texture_image_size": TEXTURE,
        "max_geometric_error": 64, "decimate_last_depth_level": True, "workers": 2,
    })
    return out, json.loads((out / "tileset.json").read_text())


def _nodes(node):
    yield node
    for child in node.get("children", []):
        yield from _nodes(child)


def test_tileset_structure(tiled):
    out, tileset = tiled
    uris = sorted(n["content"]["uri"] for n in _nodes(tileset["root"]) if "content" in n)
    assert uris == ["0_0_0.glb", "1_0_0.glb", "1_0_1.glb", "1_1_0.glb", "1_1_1.glb"]
    assert tileset["root"]["transform"] == LocalFrame(13.5, 45.8, 10.0).transform()
    leaves = [n for n in _nodes(tileset["root"]) if "content" in n and "children" not in n]
    assert all(n["geometricError"] == 0 for n in leaves)
    for uri in uris:
        gltf = _read_glb(out / uri)[0]
        assert "EXT_texture_webp" in gltf["extensionsRequired"]
        assert gltf["textures"][0]["extensions"]["EXT_texture_webp"]["source"] == 0


def test_vertices_inside_their_bounding_volume(tiled):
    out, tileset = tiled
    for node in _nodes(tileset["root"]):
        if "content" not in node:
            continue
        enu = _read_glb(out / node["content"]["uri"])[1]
        b = node["boundingVolume"]["box"]
        centre, half = np.array(b[:3]), np.array([b[3], b[7], b[11]])
        assert np.all(np.abs(enu - centre) <= half + 1e-3), node["content"]["uri"]
    b = tileset["root"]["boundingVolume"]["box"]
    assert np.allclose(b[:2], [SIZE_X / 2, SIZE_Y / 2], atol=0.5)
    assert np.allclose([2 * b[3], 2 * b[7]], [SIZE_X, SIZE_Y], atol=1.0)


def test_texture_orientation(tiled):
    """Sample the baked atlas at each triangle centroid under both UV conventions: the glTF
    one (origin top-left) must match the colour expected at that position, the flipped not."""
    out, _ = tiled
    for uri in ("0_0_0.glb", "1_1_0.glb"):
        _, enu, faces, uv, image = _read_glb(out / uri)
        centroid = enu[faces].mean(axis=1)
        cuv = uv[faces].mean(axis=1)
        expected = np.stack([centroid[:, 0] / SIZE_X, centroid[:, 1] / SIZE_Y], axis=1) * 255
        size = image.shape[0]
        col = np.clip((cuv[:, 0] * size).astype(int), 0, size - 1)
        errors = [
            np.abs(image[np.clip(rows, 0, size - 1), col][:, :2] - expected).mean()
            for rows in ((cuv[:, 1] * size).astype(int), ((1 - cuv[:, 1]) * size).astype(int))
        ]
        correct, flipped = errors
        assert correct < 6, (uri, correct)
        assert flipped > 3 * correct, (uri, correct, flipped)


def test_untextured_mesh_is_grey_not_black(tmp_path):
    (tmp_path / "plain.obj").write_text("v 0 0 0\nv 10 0 0\nv 10 10 0\nv 0 10 1\nf 1 2 3\nf 1//1 3//1 4//1\n")
    tiler.run({"input_file": str(tmp_path / "plain.obj"), "output_dir": str(tmp_path / "t"),
               "depth": 0, "workers": 1})
    gltf, enu, faces, uv, image = _read_glb(tmp_path / "t" / "0_0_0.glb")
    assert uv is None and image is None and len(faces) == 2
    assert gltf["materials"][0]["pbrMetallicRoughness"]["baseColorFactor"][0] > 0


def test_vertex_colors_are_baked(tmp_path):
    (tmp_path / "vc.obj").write_text(
        "v 0 0 0 1 0 0\nv 10 0 0 1 0 0\nv 10 10 0 1 0 0\nv 0 10 0 1 0 0\nf 1 2 3\nf 1 3 4\n")
    tiler.run({"input_file": str(tmp_path / "vc.obj"), "output_dir": str(tmp_path / "t"),
               "depth": 0, "workers": 1, "texture_image_size": 64})
    _, _, faces, uv, image = _read_glb(tmp_path / "t" / "0_0_0.glb")
    texels = image[(uv[faces].mean(axis=1)[:, 1] * 64).astype(int), (uv[faces].mean(axis=1)[:, 0] * 64).astype(int)]
    assert np.all(texels[:, 0] > 200) and np.all(texels[:, 1:] < 40)


def test_axis_matrix_matches_blender_importer():
    m = axis_matrix("NEGATIVE_Z", "Y")
    assert np.allclose(m @ [1, 2, 3], [1, -3, 2])
    assert np.allclose(axis_matrix("Y", "Z"), np.eye(3))
    with pytest.raises(ValueError):
        axis_matrix("Z", "NEGATIVE_Z")


def test_parse_obj_face_forms(tmp_path):
    (tmp_path / "m.obj").write_text(
        "v 0 0 0\nv 1 0 0\nv 1 1 0\nv 0 1 0\nv 2 0 0\nvt 0 0\nvt 1 0\nvt 1 1\nvt 0 1\n"
        "f 1/1/1 2/2/1 3/3/1\nf 1/1 3/3 4/4\nf 1 2 5\nf 1//1 2//1 3//1 4//1\n")
    mesh = parse_obj(str(tmp_path / "m.obj"))
    assert len(mesh.face_v) == 1 + 1 + 1 + 2
    assert (mesh.face_vt[2] == -1).all() and (mesh.face_vt[1] >= 0).all()


def _rasterize_reference(atlas_uv, faces, size, tolerance=0.003):
    """Per-triangle loop (the original POC implementation)."""
    px, py = atlas_uv[:, 0] * size - 0.5, atlas_uv[:, 1] * size - 0.5
    texels = set()
    for f, tri in enumerate(faces):
        x0, x1, x2 = px[tri]
        y0, y1, y2 = py[tri]
        min_x, max_x = max(int(np.floor(min(x0, x1, x2))), 0), min(int(np.ceil(max(x0, x1, x2))), size - 1)
        min_y, max_y = max(int(np.floor(min(y0, y1, y2))), 0), min(int(np.ceil(max(y0, y1, y2))), size - 1)
        denom = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        if min_x > max_x or min_y > max_y or abs(denom) < 1e-12:
            continue
        gx, gy = np.meshgrid(np.arange(min_x, max_x + 1), np.arange(min_y, max_y + 1))
        w0 = ((y1 - y2) * (gx - x2) + (x2 - x1) * (gy - y2)) / denom
        w1 = ((y2 - y0) * (gx - x2) + (x0 - x2) * (gy - y2)) / denom
        inside = (w0 >= -tolerance) & (w1 >= -tolerance) & (1 - w0 - w1 >= -tolerance)
        texels.update(zip(gy[inside].tolist(), gx[inside].tolist(), [f] * int(inside.sum()), strict=True))
    return texels


def test_rasterize_matches_reference():
    rng = np.random.default_rng(0)
    uv = rng.random((300, 2))
    faces = rng.integers(0, 300, (200, 3))
    rows, cols, face_ids, bary = rasterize_atlas(uv, faces, 64, chunk=500)
    assert set(zip(rows.tolist(), cols.tolist(), face_ids.tolist(), strict=True)) == _rasterize_reference(uv, faces, 64)
    assert np.allclose(bary.sum(axis=1), 1.0)
