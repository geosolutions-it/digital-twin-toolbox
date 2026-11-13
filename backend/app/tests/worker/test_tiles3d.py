import json
import os

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("mapbox_earcut")

from app.worker.lib.features.tiler import build_tileset  # noqa: E402
from app.worker.lib.geo.frame import LocalFrame  # noqa: E402
from app.worker.lib.gltf import infer_schema  # noqa: E402
from app.worker.lib.tiles3d.check import check_tileset  # noqa: E402
from app.worker.lib.tiles3d.parent import build_parent_tileset  # noqa: E402
from app.worker.lib.tiles3d.tileset import region_corners  # noqa: E402
from app.worker.tasks.instance.tiler import build_instance_tileset  # noqa: E402
from app.worker.tasks.polygon.extrude import extrude  # noqa: E402

FRAME = LocalFrame(13.77, 45.65, 0.0)


def _prisms(n=400, seed=1):
    rng = np.random.default_rng(seed)
    features = []
    for i in range(n):
        x, y = rng.uniform(0, 2000, 2)
        w, d = rng.uniform(5, 30, 2)
        ring = np.array([[x, y], [x + w, y], [x + w, y + d], [x, y + d], [x, y]])
        mesh = extrude([ring], 0.0, upper=float(rng.uniform(3, 40)))
        features.append(
            {
                "mesh": mesh,
                "centroid": np.array([x + w / 2, y + d / 2]),
                "properties": {"id": i, "kind": "abc"[i % 3]},
            }
        )
    return features


class _Texturer:
    max_extent = 300.0

    def classify(self, tris):
        return np.ones(len(tris), dtype=bool)

    def __call__(self, tris, _detail):
        return np.full((len(tris) * 3, 2), 0.5), b"RIFF\x00\x00\x00\x00WEBPVP8 "

    def texel(self, _tris, _detail):
        return 0.5


@pytest.fixture(scope="module")
def polygon_tiles(tmp_path_factory):
    out = tmp_path_factory.mktemp("polygon")
    _, stats = build_tileset(
        _prisms(), str(out), FRAME.transform(), max_tile_bytes=20 * 1024
    )
    assert len(stats) > 5
    return out


def _box_model(size=2.0):
    s = size / 2
    corners = np.array(
        [[x, y, z] for x in (-s, s) for y in (0, size) for z in (-s, s)],
        dtype=np.float32,
    )
    faces = [
        [0, 1, 3], [0, 3, 2], [4, 6, 7], [4, 7, 5], [0, 4, 5], [0, 5, 1],
        [2, 3, 7], [2, 7, 6], [0, 2, 6], [0, 6, 4], [1, 5, 7], [1, 7, 3],
    ]  # fmt: skip
    return {
        "primitives": [
            {
                "positions": corners,
                "normals": corners / np.linalg.norm(corners, axis=1)[:, None],
                "indices": np.array(faces, dtype=np.uint32).ravel(),
            }
        ]
    }


@pytest.fixture(scope="module")
def instance_tiles(tmp_path_factory):
    out = tmp_path_factory.mktemp("instance")
    rng = np.random.default_rng(2)
    records = [
        {
            "enu": np.array([*rng.uniform(0, 3000, 2), rng.uniform(0, 20)]),
            "heading": float(rng.uniform(0, 360)),
            "scale": float(rng.uniform(0.5, 2)),
            "model": ("a.glb", "b.glb")[i % 2],
            "properties": {"id": i},
        }
        for i in range(3000)
    ]
    models = {"a.glb": _box_model(), "b.glb": _box_model(4.0)}
    schema = infer_schema([r["properties"] for r in records])
    tileset = build_instance_tileset(
        records, str(out), FRAME.transform(), models, schema, max_tile_bytes=16 * 1024
    )
    assert tileset["root"].get("children")
    return out


def test_polygon_tileset_passes(polygon_tiles):
    assert check_tileset(polygon_tiles) == []


def test_textured_polygon_tileset_passes(tmp_path):
    build_tileset(
        _prisms(150),
        str(tmp_path),
        FRAME.transform(),
        max_tile_bytes=20 * 1024,
        texturer=_Texturer(),
        max_leaf_extent=_Texturer.max_extent,
    )
    assert check_tileset(tmp_path) == []


def test_instance_tileset_passes(instance_tiles):
    assert check_tileset(instance_tiles) == []


def test_batch_parent_passes(tmp_path, polygon_tiles, instance_tiles):
    children = []
    for name, folder in (("a", polygon_tiles), ("b", instance_tiles)):
        os.symlink(folder, tmp_path / name)
        with open(folder / "tileset.json") as f:
            children.append({"uri": f"{name}/tileset.json", "tileset": json.load(f)})
    (tmp_path / "tileset.json").write_text(json.dumps(build_parent_tileset(children)))
    assert check_tileset(tmp_path) == []


def _region_tileset(region):
    return {
        "asset": {"version": "1.1"},
        "geometricError": 10,
        "root": {
            "boundingVolume": {"region": region},
            "geometricError": 10,
            "refine": "ADD",
        },
    }


def test_batch_parent_with_mixed_volumes_encloses_every_child(polygon_tiles):
    with open(polygon_tiles / "tileset.json") as f:
        boxed = json.load(f)
    region = [0.20, 0.79, 0.21, 0.80, 0.0, 50.0]
    parent = build_parent_tileset(
        [
            {"uri": "a/tileset.json", "tileset": boxed},
            {"uri": "b/tileset.json", "tileset": _region_tileset(region)},
        ]
    )
    volume = parent["root"]["boundingVolume"]
    assert "box" in volume
    b = np.array(volume["box"])
    half = np.abs(b[3:].reshape(3, 3)).sum(axis=0)
    corners = np.array(region_corners(region))
    assert np.all(np.abs(corners - b[:3]) <= half + 1e-3)


def test_region_children_get_boxes(tmp_path):
    regions = [[0, 0, 0.1, 0.1, 0, 5], [0.1, 0, 0.2, 0.1, -5, 1]]
    parent = build_parent_tileset(
        [
            {"uri": f"{i}.json", "tileset": _region_tileset(r)}
            for i, r in enumerate(regions)
        ]
    )
    root = parent["root"]
    assert "box" in root["boundingVolume"]
    assert all("box" in c["boundingVolume"] for c in root["children"])
    for i, r in enumerate(regions):
        (tmp_path / f"{i}.json").write_text(json.dumps(_region_tileset(r)))
    (tmp_path / "tileset.json").write_text(json.dumps(parent))
    assert check_tileset(tmp_path) == []


def _copy(src, dst):
    os.makedirs(dst)
    for name in os.listdir(src):
        with open(src / name, "rb") as f:
            (dst / name).write_bytes(f.read())
    return dst


def _edit(folder, change):
    path = folder / "tileset.json"
    tileset = json.loads(path.read_text())
    change(tileset)
    path.write_text(json.dumps(tileset))


def test_checker_flags_broken_tilesets(tmp_path, polygon_tiles):
    def child_error_above_parent(t):
        t["root"]["children"][0]["geometricError"] = t["root"]["geometricError"] + 1

    def child_outside_parent(t):
        t["root"]["children"][0]["boundingVolume"]["box"][0] += 1e4

    def shrunk_box(t):
        node = t["root"]
        while node.get("children"):
            node = node["children"][0]
        node["boundingVolume"]["box"][3] /= 4

    def missing_content(t):
        t["root"]["children"][0]["content"] = {"uri": "nope.glb"}

    def unknown_refine(t):
        t["root"]["refine"] = "MERGE"

    cases = {
        "above its parent": child_error_above_parent,
        "outside its parent": child_outside_parent,
        "outside its boundingVolume": shrunk_box,
        "missing": missing_content,
        "refine": unknown_refine,
    }
    for expected, change in cases.items():
        folder = _copy(polygon_tiles, tmp_path / expected.replace(" ", "_"))
        _edit(folder, change)
        problems = check_tileset(folder)
        assert any(expected in p for p in problems), (expected, problems)


def test_checker_flags_broken_glb(tmp_path, polygon_tiles):
    folder = _copy(polygon_tiles, tmp_path / "glb")
    glb = sorted(n for n in os.listdir(folder) if n.endswith(".glb"))[0]
    data = bytearray((folder / glb).read_bytes())
    (folder / glb).write_bytes(bytes(data[:-8]))
    assert any("bad GLB header" in p for p in check_tileset(folder))
