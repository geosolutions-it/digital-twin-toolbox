import json

import pytest

pytest.importorskip("osgeo.ogr")

from app.worker.lib.geo.ogr import (  # noqa: E402
    iter_features,
    open_layer,
    wgs84_transform,
)


def _write(tmp_path, features):
    path = tmp_path / "in.geojson"
    path.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
                "features": features,
            }
        )
    )
    return str(path)


def _feature(geometry, **properties):
    return {"type": "Feature", "geometry": geometry, "properties": properties}


def test_skips_null_geometries_and_keeps_properties(tmp_path):
    path = _write(
        tmp_path,
        [
            _feature({"type": "Point", "coordinates": [13.7, 45.6]}, name="a", h=1.5),
            _feature(None, name="b", h=2.0),
        ],
    )
    ds, layer = open_layer(path)
    rows = list(iter_features(layer, wgs84_transform(layer)))
    assert len(rows) == 1
    geometry, properties = rows[0]
    assert geometry["type"] == "Point"
    assert geometry["coordinates"][:2] == pytest.approx([13.7, 45.6])
    assert properties == {"name": "a", "h": 1.5}


def test_force_3d_adds_a_height(tmp_path):
    path = _write(tmp_path, [_feature({"type": "Point", "coordinates": [13.7, 45.6]})])
    ds, layer = open_layer(path)
    [(flat, _)] = iter_features(layer, wgs84_transform(layer))
    [(solid, _)] = iter_features(layer, wgs84_transform(layer), force_3d=True)
    assert len(flat["coordinates"]) == 2
    assert len(solid["coordinates"]) == 3


def test_respects_the_spatial_filter(tmp_path):
    path = _write(
        tmp_path,
        [
            _feature({"type": "Point", "coordinates": [10.0, 40.0]}, id=1),
            _feature({"type": "Point", "coordinates": [20.0, 50.0]}, id=2),
        ],
    )
    ds, layer = open_layer(path)
    layer.SetSpatialFilterRect(19.0, 49.0, 21.0, 51.0)
    assert [p["id"] for _, p in iter_features(layer, wgs84_transform(layer))] == [2]
