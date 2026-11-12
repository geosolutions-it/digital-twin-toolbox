import json
import shutil
import struct

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("mapbox_earcut")
gdal = pytest.importorskip("osgeo.gdal")
pytest.importorskip("PIL")

from osgeo import osr  # noqa: E402

from app.models.config import BuildingConfig  # noqa: E402
from app.worker.common.geo import LocalFrame  # noqa: E402
from app.worker.tasks.vector.building.task import (  # noqa: E402
    read_roofer,
    sink_to_dtm,
)
from app.worker.tasks.vector.ortho import OrthoTexturer, roof_mask  # noqa: E402
from app.worker.tasks.vector.polygon.writer import glb_bytes  # noqa: E402

# a 10 m box building at (1000, 2000) in EPSG:25833, base at 50 m, flat roof at 60 m
X0, Y0 = 1000.0, 2000.0
BOX = [(0, 0), (10, 0), (10, 10), (0, 10)]


def _cityjsonseq(path):
    verts = [[int(x * 1000), int(y * 1000), 50000] for x, y in BOX] + \
            [[int(x * 1000), int(y * 1000), 60000] for x, y in BOX]
    walls = [[[i, (i + 1) % 4, 4 + (i + 1) % 4, 4 + i]] for i in range(4)]
    solid = {
        "type": "Solid", "lod": "2.2",
        "boundaries": [[[[3, 2, 1, 0]]] + walls + [[[4, 5, 6, 7]]]],
        "semantics": {"surfaces": [{"type": "GroundSurface"}, {"type": "WallSurface"}, {"type": "RoofSurface"}],
                      "values": [[0, 1, 1, 1, 1, 2]]},
    }
    footprint = {"type": "MultiSurface", "lod": "0", "boundaries": [[[0, 1, 2, 3]]]}
    header = {"type": "CityJSON", "version": "2.0", "CityObjects": {}, "vertices": [],
              "metadata": {"referenceSystem": "https://www.opengis.net/def/crs/EPSG/0/25833"},
              "transform": {"scale": [0.001, 0.001, 0.001], "translate": [X0, Y0, 0.0]}}
    feature = {"type": "CityJSONFeature", "id": "b1", "vertices": verts, "CityObjects": {
        "b1": {"type": "Building", "children": ["b1-0"], "geometry": [footprint],
               "attributes": {"name": "box", "rf_h_ground": 50.0, "rf_t_run": 0.1, "rf_ridgelines": [[0, 1]]}},
        "b1-0": {"type": "BuildingPart", "parents": ["b1"], "geometry": [solid]},
    }}
    with open(path, "w") as f:
        f.write(json.dumps(header) + "\n" + json.dumps(feature) + "\n")


def _raster(path, array, x0, y0, res, epsg=25833):
    bands = array.shape[0] if array.ndim == 3 else 1
    dtype = {np.uint8: gdal.GDT_Byte, np.uint16: gdal.GDT_UInt16}.get(array.dtype.type, gdal.GDT_Float32)
    ds = gdal.GetDriverByName("GTiff").Create(str(path), array.shape[-1], array.shape[-2], bands, dtype)
    ds.SetGeoTransform((x0, res, 0, y0, 0, -res))
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(epsg)
    ds.SetProjection(srs.ExportToWkt())
    for b in range(bands):
        ds.GetRasterBand(b + 1).WriteArray(array[b] if bands > 1 else array)
    ds = None


def _wkt(epsg=25833):
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(epsg)
    return srs.ExportToWkt()


def test_config_defaults_and_validation():
    c = BuildingConfig(point_cloud="lidar/", orthophoto="", lod="2.2")
    assert c.orthophoto is None and c.lod == "2.2" and c.building_class == 6
    with pytest.raises(ValueError):
        BuildingConfig(point_cloud="")
    with pytest.raises(ValueError):
        BuildingConfig(point_cloud="a.laz", lod="2")


def test_read_roofer_keeps_attributes_and_the_requested_lod(tmp_path):
    _cityjsonseq(tmp_path / "a.city.jsonl")
    [(srs, props, polys)] = read_roofer([str(tmp_path / "a.city.jsonl")], "2.2")
    assert srs == "EPSG:25833"
    assert props == {"gml_id": "b1", "citygml_type": "Building", "name": "box", "rf_h_ground": 50.0}
    assert len(polys) == 6  # the solid, not the LoD 0 footprint
    np.testing.assert_allclose(polys[-1][0][0], [X0, Y0, 60.0])
    assert read_roofer([str(tmp_path / "a.city.jsonl")], "1.2") == []


def test_sink_to_dtm_lowers_the_base_only(tmp_path):
    _cityjsonseq(tmp_path / "a.city.jsonl")
    objects = read_roofer([str(tmp_path / "a.city.jsonl")], "2.2")
    # terrain slopes from 50 m down to 46 m across the building
    dtm = np.tile(np.linspace(50, 46, 40, dtype=np.float32), (40, 1))
    _raster(tmp_path / "dtm.tif", dtm, X0 - 5, Y0 + 15, 0.5)
    sink_to_dtm(objects, str(tmp_path / "dtm.tif"), _wkt(), sink=0.3)
    zs = np.concatenate([r[:, 2] for poly in objects[0][2] for r in poly])
    assert zs.max() == pytest.approx(60.0)
    base = zs[zs < 59]
    # DTM column 30 is under x = 10 m
    expected = float(np.linspace(50, 46, 40, dtype=np.float32)[30]) - 0.3
    assert np.allclose(base, expected, atol=1e-4)


def _enu_box(frame_lonlat, transform):
    pts = [(X0 + x, Y0 + y, z) for z in (50.0, 60.0) for x, y in BOX]
    lonlath = np.array(transform.TransformPoints(pts))
    frame = LocalFrame(*frame_lonlat)
    return frame, frame.to_enu(lonlath)


def test_texturer_maps_roofs_into_the_orthophoto(tmp_path):
    src = osr.SpatialReference()
    src.ImportFromEPSG(25833)
    dst = osr.SpatialReference()
    dst.ImportFromEPSG(4326)
    for s in (src, dst):
        s.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    transform = osr.CoordinateTransformation(src, dst)
    centre = transform.TransformPoint(X0 + 5, Y0 + 5, 0)
    frame, enu = _enu_box(centre[:2], transform)
    # red roof inside a blue surround, 0.5 m pixels
    rgb = np.zeros((3, 60, 60), dtype=np.uint8)
    rgb[2] = 255
    rgb[:, 10:30, 10:30] = np.array([255, 0, 0], dtype=np.uint8)[:, None, None]
    _raster(tmp_path / "ortho.tif", rgb, X0 - 5, Y0 + 15, 0.5)

    roof = enu[[4, 5, 6, 4, 6, 7]].reshape(2, 3, 3)
    wall = enu[[0, 1, 5, 0, 5, 4]].reshape(2, 3, 3)
    tris = np.concatenate([roof, wall])
    assert roof_mask(tris).tolist() == [True, True, False, False]

    texturer = OrthoTexturer(str(tmp_path / "ortho.tif"), frame)
    assert texturer.resolution == pytest.approx(0.5, rel=0.05)
    assert texturer.texel(tris) == texturer.resolution
    assert texturer.texel(tris, detail=40.0) == 10.0
    assert texturer.texel(wall) is None
    uv, webp = texturer(tris)
    assert webp[:4] == b"RIFF" and webp[8:12] == b"WEBP"
    assert uv.shape == (12, 2) and (uv >= 0).all() and (uv <= 1).all()
    assert np.allclose(uv[6:], uv[6])  # walls share the flat strip
    assert uv[6, 0] > uv[:6, 0].max()
    assert texturer.roof_colors([tris, wall]) == ["#ff0000", None]


def test_glb_carries_uvs_and_webp_when_textured():
    tris = np.array([[0, 0, 10], [10, 0, 10], [10, 10, 10], [0, 0, 0], [10, 0, 0], [10, 0, 10]], dtype=float)

    class Texturer:
        calls = 0

        def classify(self, t):
            return roof_mask(t)

        def __call__(self, t, _detail):
            self.calls += 1
            assert t.shape == (2, 3, 3)
            return np.full((6, 2), 0.5), b"RIFF\x00\x00\x00\x00WEBPVP8 "

    texturer = Texturer()
    schema = [{"name": "a", "kind": "number"}]
    assert glb_bytes(tris, [6], [{"a": 1}], schema, texturer=texturer, size_limit=100) is None
    assert texturer.calls == 0  # an oversized tile never builds its texture
    data = glb_bytes(tris, [6], [{"a": 1}], schema, texturer=texturer, base_color=[0.7, 0.7, 0.7, 1.0])
    length = struct.unpack("<I", data[12:16])[0]
    gltf = json.loads(data[20:20 + length])
    assert "TEXCOORD_0" in gltf["meshes"][0]["primitives"][0]["attributes"]
    assert "EXT_texture_webp" in gltf["extensionsRequired"]
    assert gltf["materials"][0]["pbrMetallicRoughness"]["baseColorTexture"] == {"index": 0}

    plain = glb_bytes(tris, [6], [{"a": 1}], [{"name": "a", "kind": "number"}], base_color=[0.7, 0.7, 0.7, 1.0])
    gltf = json.loads(plain[20:20 + struct.unpack("<I", plain[12:16])[0]])
    assert "TEXCOORD_0" not in gltf["meshes"][0]["primitives"][0]["attributes"]
    assert gltf["materials"][0]["pbrMetallicRoughness"]["baseColorFactor"] == [0.7, 0.7, 0.7, 1.0]


@pytest.mark.skipif(shutil.which("roofer") is None, reason="roofer not installed")
def test_roofer_is_runnable():
    import subprocess

    out = subprocess.run(["roofer", "--version"], capture_output=True, text=True, check=True)
    assert "roofer" in out.stdout


class _TileStorage:
    """LAS headers only; downloads write the key name."""

    def __init__(self, tiles):
        self.tiles = tiles  # key -> (minx, miny, maxx, maxy) or None for a broken header

    def list(self, prefix):
        return [k for k in self.tiles if k.startswith(prefix)]

    def read_range(self, key, start, length):
        b = self.tiles[key]
        if b is None:
            return b"junk"
        head = bytearray(227)
        head[:4] = b"LASF"
        struct.pack_into("<6d", head, 179, b[2], b[0], b[3], b[1], 10.0, 0.0)
        return bytes(head[start:start + length])

    def download_file(self, key, dest):
        with open(dest, "w") as f:
            f.write(key)


def test_point_cloud_folder_keeps_only_tiles_near_the_footprints(tmp_path):
    from app.worker.tasks.vector.building.task import _download_point_cloud

    storage = _TileStorage({
        "las/a.laz": (0, 0, 500, 500),          # under the footprints
        "las/b.laz": (510, 0, 1000, 500),       # 10 m away: inside the margin
        "las/c.laz": (5000, 5000, 5500, 5500),  # far away
        "las/d.laz": None,                      # unreadable header: kept
        "las/readme.txt": (0, 0, 1, 1),
    })
    paths = _download_point_cloud(storage, "las/", str(tmp_path), (100, 100, 500, 400))
    assert sorted(open(p).read() for p in paths) == ["las/a.laz", "las/b.laz", "las/d.laz"]
    with pytest.raises(Exception, match="same CRS"):
        _download_point_cloud(_TileStorage({"las/c.laz": (5000, 5000, 5500, 5500), "las/e.laz": (9000, 0, 9100, 1)}),
                              "las/", str(tmp_path), (100, 100, 500, 400))


def test_tiler_splits_leaves_wider_than_the_texture_reach(tmp_path):
    from app.worker.tasks.vector.polygon.tiler import build_tileset

    # two buildings 1 km apart
    def box(x):
        return np.array([[x, 0, 0], [x + 10, 0, 0], [x + 10, 10, 0]], dtype=float)
    feats = [{"mesh": box(x), "centroid": np.array([x + 5.0, 5.0]), "properties": {"i": i}}
             for i, x in enumerate((0.0, 1000.0))]
    identity = [1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0]
    _, stats = build_tileset(feats, str(tmp_path / "a"), identity)
    assert len(stats) == 1
    _, stats = build_tileset(feats, str(tmp_path / "b"), identity, max_leaf_extent=500.0)
    leaves = json.load(open(tmp_path / "b" / "tileset.json"))["root"]["children"]
    assert len(leaves) == 2 and all(not c.get("children") for c in leaves)


def test_tiler_parent_error_covers_its_texture(tmp_path):
    from app.worker.tasks.vector.polygon.tiler import build_tileset

    class Texturer:
        def classify(self, t):
            return np.ones(len(t), dtype=bool)

        def __call__(self, t, _detail):
            return None

        def texel(self, t, _detail):
            return 3.0

    def box(x):
        return np.array([[x, 0, 0], [x + 10, 0, 0], [x + 10, 10, 0]], dtype=float)
    feats = [{"mesh": box(x), "centroid": np.array([x + 5.0, 5.0]), "properties": {"i": i}}
             for i, x in enumerate((0.0, 1000.0))]
    identity = [1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0]
    build_tileset(feats, str(tmp_path), identity, texturer=Texturer(), max_leaf_extent=500.0)
    root = json.load(open(tmp_path / "tileset.json"))["root"]
    assert "content" in root and root["geometricError"] == 3.0 * 8
    assert all(c["geometricError"] == 0.0 for c in root["children"])


def test_sink_to_dtm_skips_nan_cells(tmp_path):
    _cityjsonseq(tmp_path / "a.city.jsonl")
    objects = read_roofer([str(tmp_path / "a.city.jsonl")], "2.2")
    dtm = np.full((40, 40), 48.0, dtype=np.float32)
    dtm[:, 20:] = np.nan  # gap under half of the building
    _raster(tmp_path / "dtm.tif", dtm, X0 - 5, Y0 + 15, 0.5)
    sink_to_dtm(objects, str(tmp_path / "dtm.tif"), _wkt(), sink=0.3)
    zs = np.concatenate([r[:, 2] for poly in objects[0][2] for r in poly])
    assert np.isfinite(zs).all() and zs.min() == pytest.approx(47.7)


def test_texturer_stretches_16_bit_orthophotos(tmp_path):
    src = osr.SpatialReference()
    src.ImportFromEPSG(25833)
    dst = osr.SpatialReference()
    dst.ImportFromEPSG(4326)
    for s in (src, dst):
        s.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    transform = osr.CoordinateTransformation(src, dst)
    frame, enu = _enu_box(transform.TransformPoint(X0 + 5, Y0 + 5, 0)[:2], transform)
    rgb = np.zeros((3, 60, 60), dtype=np.uint16)
    rgb[0, 10:30, 10:30] = 4000  # 12-bit red roof, would wrap to 160 if cast
    rgb[:, 0, 0] = 4000  # full range in every band
    _raster(tmp_path / "ortho.tif", rgb, X0 - 5, Y0 + 15, 0.5)
    roof = enu[[4, 5, 6, 4, 6, 7]].reshape(2, 3, 3)
    assert OrthoTexturer(str(tmp_path / "ortho.tif"), frame).roof_colors([roof]) == ["#ff0000"]


def test_grow_is_a_square_dilation():
    from app.worker.tasks.vector.ortho import _grow

    m = np.zeros((9, 9), dtype=bool)
    m[5, 4] = True
    m[0, 8] = True
    out = _grow(m, 2)
    assert out[3:8, 2:7].all() and out.sum() == 25 + 9  # the corner pixel grows inside the image only
