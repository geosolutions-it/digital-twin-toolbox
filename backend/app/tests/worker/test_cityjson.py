import io
import json
import zipfile

import pytest

np = pytest.importorskip("numpy")

from app.services.file_classify import classify_bucket_file  # noqa: E402
from app.worker.tasks.vector.citygml.cityjson import iter_cityjson  # noqa: E402
from app.worker.tasks.vector.citygml.crs import resolve_crs  # noqa: E402
from app.worker.tasks.vector.citygml.reader import iter_city_objects  # noqa: E402

SQUARE = [[0, 1, 2, 3]]


def _doc(**extra):
    """CityJSON 1.1 document: a building with LoD 1 and 2 parts, a road surface, a terrain."""
    return {
        "type": "CityJSON",
        "version": "1.1",
        "metadata": {"referenceSystem": "https://www.opengis.net/def/crs/EPSG/0/7415"},
        "transform": {
            "scale": [0.01, 0.01, 0.01],
            "translate": [85000.0, 446000.0, 0.0],
        },
        "vertices": [
            [0, 0, 0],
            [1000, 0, 0],
            [1000, 1000, 0],
            [0, 1000, 0],
            [0, 0, 900],
            [1000, 0, 900],
            [1000, 1000, 900],
            [0, 1000, 900],
        ],
        "CityObjects": {
            "B1": {
                "type": "Building",
                "children": ["B1-p"],
                "attributes": {"yearOfConstruction": 1930, "address": {"street": "x"}},
                "geometry": [
                    {
                        "type": "Solid",
                        "lod": "1",
                        "boundaries": [[[[0, 3, 2, 1]], [[4, 5, 6, 7]]]],
                    }
                ],
            },
            "B1-p": {
                "type": "BuildingPart",
                "parents": ["B1"],
                "geometry": [
                    {
                        "type": "MultiSurface",
                        "lod": "2.2",
                        "boundaries": [[[4, 5, 6, 7]]],
                    },
                    {"type": "MultiSurface", "lod": "2.0", "boundaries": [SQUARE]},
                ],
            },
            "R1": {
                "type": "Road",
                "geometry": [
                    {"type": "CompositeSurface", "lod": 2, "boundaries": [SQUARE]}
                ],
            },
            "T1": {
                "type": "TINRelief",
                "geometry": [
                    {"type": "CompositeSurface", "lod": "1", "boundaries": [SQUARE]}
                ],
            },
            "I1": {
                "type": "SolitaryVegetationObject",
                "geometry": [
                    {"type": "GeometryInstance", "template": 0, "boundaries": [0]}
                ],
            },
        },
        **extra,
    }


def test_cityjson_document_objects_lod_and_attributes():
    objs = {
        p["gml_id"]: (srs, p, polys)
        for srs, p, polys in iter_cityjson(io.BytesIO(json.dumps(_doc()).encode()))
    }
    assert set(objs) == {"B1", "R1"}  # no terrain, templates or parts
    srs, props, polys = objs["B1"]
    assert srs == "EPSG:7415"
    assert props == {
        "gml_id": "B1",
        "citygml_type": "Building",
        "yearOfConstruction": 1930,
    }  # nested dropped
    # LoD 2.2, from the child part
    assert len(polys) == 1
    np.testing.assert_allclose(
        polys[0][0],
        [
            [85000, 446000, 9],
            [85010, 446000, 9],
            [85010, 446010, 9],
            [85000, 446010, 9],
        ],
    )


def test_cityjson_lod_caps():
    data = json.dumps(_doc()).encode()
    b1 = {
        p["gml_id"]: polys for _, p, polys in iter_cityjson(io.BytesIO(data), max_lod=1)
    }["B1"]
    assert len(b1) == 2  # the LoD 1 solid
    assert [p["gml_id"] for _, p, _ in iter_cityjson(io.BytesIO(data), lod=2.2)] == [
        "B1"
    ]
    assert [len(polys) for _, _, polys in iter_cityjson(io.BytesIO(data), lod=1)] == [
        2
    ]  # not 2.2


def test_cityjson_formatted_v1_without_transform_and_urn():
    doc = _doc(
        version="1.0", metadata={"referenceSystem": "urn:ogc:def:crs:EPSG::28992"}
    )
    doc.pop("transform")
    doc["vertices"] = (np.array(doc["vertices"]) / 100.0 + [85000, 446000, 0]).tolist()
    data = json.dumps(doc, indent=2).encode()  # multi-line
    srs, props, polys = next(
        o for o in iter_cityjson(io.BytesIO(data)) if o[1]["gml_id"] == "B1"
    )
    assert srs == "EPSG:28992"
    assert polys[0][0][0].tolist() == [85000.0, 446000.0, 9.0]


def test_short_epsg_keeps_xy_order_for_geographic_crs():
    assert resolve_crs("EPSG:4326")[1] is False
    assert resolve_crs("EPSG:4326+EPSG:5773")[1] is False
    assert resolve_crs("urn:ogc:def:crs:EPSG::4326")[1] is True


def test_iter_city_objects_reads_cityjson_and_gml_in_one_zip(tmp_path):
    gml = (
        '<?xml version="1.0"?><core:CityModel xmlns:core="http://www.opengis.net/citygml/2.0" '
        'xmlns:bldg="http://www.opengis.net/citygml/building/2.0" xmlns:gml="http://www.opengis.net/gml">'
        '<core:cityObjectMember><bldg:Building gml:id="G1"><bldg:lod1MultiSurface><gml:MultiSurface>'
        '<gml:surfaceMember><gml:Polygon srsName="EPSG:25832"><gml:exterior><gml:LinearRing>'
        "<gml:posList>0 0 0 1 0 0 1 1 0 0 0 0</gml:posList></gml:LinearRing></gml:exterior></gml:Polygon>"
        "</gml:surfaceMember></gml:MultiSurface></bldg:lod1MultiSurface></bldg:Building>"
        "</core:cityObjectMember></core:CityModel>"
    )
    path = tmp_path / "city.zip"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("a.gml", gml)
        zf.writestr("b.city.json", json.dumps(_doc()))
        zf.writestr("readme.txt", "ignored")
        zf.writestr("metadata.json", '{"title": "a sidecar, not CityJSON"}')
    ids = [p["gml_id"] for _, p, _ in iter_city_objects(str(path))]
    assert ids == ["G1", "B1", "R1"]
    single = tmp_path / "b.city.json"
    single.write_text(json.dumps(_doc()))
    assert [p["gml_id"] for _, p, _ in iter_city_objects(str(single))] == ["B1", "R1"]


class _BytesStorage:
    def __init__(self, data):
        self.data = data

    def size(self, key):
        return len(self.data)

    def read_range(self, key, start, length):
        return self.data[start : start + length]


def test_classify_cityjson():
    assert (
        classify_bucket_file(_BytesStorage(json.dumps(_doc()).encode()), "a.json")
        == "CityGML"
    )
    seq = b'{"type": "CityJSON", "version": "2.0", "CityObjects": {}}\n{"type": "CityJSONFeature"}\n'
    assert classify_bucket_file(_BytesStorage(seq), "a.city.jsonl") == "CityGML"
    assert (
        classify_bucket_file(_BytesStorage(b'{"type": "FeatureCollection"}'), "a.json")
        is None
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("tiles/x.city.jsonl", seq)
    assert classify_bucket_file(_BytesStorage(buf.getvalue()), "c.zip") == "CityGML"
