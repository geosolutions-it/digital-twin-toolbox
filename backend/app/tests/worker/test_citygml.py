import io
import zipfile

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("mapbox_earcut")

from app.worker.tasks.vector.citygml.crs import (  # noqa: E402
    resolve_crs,
    wgs84_transformer,
)
from app.worker.tasks.vector.citygml.reader import (  # noqa: E402
    iter_objects,
    iter_streams,
)
from app.worker.tasks.vector.citygml.triangulate import triangulate  # noqa: E402


def _poly(gid, coords):
    pos = " ".join(f"{x} {y} {z}" for x, y, z in coords + coords[:1])
    ident = f' gml:id="{gid}"' if gid else ""
    return (
        f'<gml:Polygon{ident}><gml:exterior><gml:LinearRing><gml:posList srsDimension="3">{pos}'
        "</gml:posList></gml:LinearRing></gml:exterior></gml:Polygon>"
    )


ROOF = [(0, 0, 10), (10, 0, 10), (10, 10, 10), (0, 10, 10)]
WALL = [(0, 0, 0), (10, 0, 0), (10, 0, 10), (0, 0, 10)]
PART = [(20, 0, 0), (30, 0, 0), (30, 0, 5), (20, 0, 5)]
BALCONY = [(0, -1, 3), (10, -1, 3), (10, 0, 3), (0, 0, 3)]

CITYGML = f"""<?xml version="1.0" encoding="UTF-8"?>
<core:CityModel xmlns:core="http://www.opengis.net/citygml/2.0" xmlns:bldg="http://www.opengis.net/citygml/building/2.0"
 xmlns:gml="http://www.opengis.net/gml" xmlns:gen="http://www.opengis.net/citygml/generics/2.0"
 xmlns:dem="http://www.opengis.net/citygml/relief/2.0" xmlns:xlink="http://www.w3.org/1999/xlink">
<gml:boundedBy><gml:Envelope srsName="urn:ogc:def:crs:EPSG:2056, crs:EPSG:5728" srsDimension="3"/></gml:boundedBy>
<core:cityObjectMember><bldg:Building gml:id="B1">
 <gen:stringAttribute name="usage"><gen:value>residential</gen:value></gen:stringAttribute>
 <gen:intAttribute name="year"><gen:value>2010</gen:value></gen:intAttribute>
 <gen:stringAttribute name="empty"><gen:value/></gen:stringAttribute>
 <bldg:measuredHeight uom="m">10.5</bldg:measuredHeight>
 <bldg:lod2Solid><gml:Solid><gml:exterior><gml:CompositeSurface>
  <gml:surfaceMember xlink:href="#R1"/><gml:surfaceMember xlink:href="#W1"/>
 </gml:CompositeSurface></gml:exterior></gml:Solid></bldg:lod2Solid>
 <bldg:boundedBy><bldg:RoofSurface><bldg:lod2MultiSurface><gml:MultiSurface><gml:surfaceMember>{_poly("R1", ROOF)}</gml:surfaceMember></gml:MultiSurface></bldg:lod2MultiSurface></bldg:RoofSurface></bldg:boundedBy>
 <bldg:boundedBy><bldg:WallSurface><bldg:lod2MultiSurface><gml:MultiSurface><gml:surfaceMember>{_poly("W1", WALL)}</gml:surfaceMember></gml:MultiSurface></bldg:lod2MultiSurface></bldg:WallSurface></bldg:boundedBy>
 <bldg:outerBuildingInstallation><bldg:BuildingInstallation>
  <bldg:lod2Geometry><gml:MultiSurface><gml:surfaceMember>{_poly(None, BALCONY)}</gml:surfaceMember></gml:MultiSurface></bldg:lod2Geometry>
  <bldg:lod3Geometry><gml:MultiSurface><gml:surfaceMember>{_poly(None, BALCONY)}</gml:surfaceMember><gml:surfaceMember>{_poly(None, BALCONY)}</gml:surfaceMember></gml:MultiSurface></bldg:lod3Geometry>
 </bldg:BuildingInstallation></bldg:outerBuildingInstallation>
 <bldg:consistsOfBuildingPart><bldg:BuildingPart>
  <bldg:lod2Solid><gml:Solid><gml:exterior><gml:CompositeSurface><gml:surfaceMember>{_poly(None, PART)}</gml:surfaceMember></gml:CompositeSurface></gml:exterior></gml:Solid></bldg:lod2Solid>
 </bldg:BuildingPart></bldg:consistsOfBuildingPart>
</bldg:Building></core:cityObjectMember>
<core:cityObjectMember><bldg:Building gml:id="B2">
 <bldg:lod1Solid><gml:Solid><gml:exterior><gml:CompositeSurface><gml:surfaceMember>{_poly(None, WALL)}</gml:surfaceMember></gml:CompositeSurface></gml:exterior></gml:Solid></bldg:lod1Solid>
</bldg:Building></core:cityObjectMember>
<core:cityObjectMember><dem:ReliefFeature gml:id="T1"/></core:cityObjectMember>
</core:CityModel>
"""


def _objects(max_lod=None):
    return list(iter_objects(io.BytesIO(CITYGML.encode()), max_lod))


def test_surfaces_lod_and_xlinks():
    (srs, props, polys), (_, props2, polys2) = _objects()
    assert srs == "urn:ogc:def:crs:EPSG:2056, crs:EPSG:5728"
    # roof + wall once (solid xlinks skipped), building part, installation at lod2 not lod3
    assert len(polys) == 4
    assert all(len(rings[0]) == 4 for rings in polys)
    assert props2["gml_id"] == "B2" and len(polys2) == 1


def test_max_lod_drops_objects_without_it():
    objects = _objects(max_lod=1)
    assert [p["gml_id"] for _, p, _ in objects] == ["B2"]


def test_attributes():
    props = _objects()[0][1]
    assert props == {
        "citygml_type": "Building",
        "gml_id": "B1",
        "usage": "residential",
        "year": 2010,
        "measuredHeight": 10.5,
    }


def test_zip_streams_every_gml(tmp_path):
    path = tmp_path / "city.zip"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("a/one.gml", CITYGML)
        zf.writestr("two.gml", CITYGML)
        zf.writestr("__MACOSX/a/._one.gml", "junk")
        zf.writestr("readme.txt", "x")
    count = sum(len(list(iter_objects(s))) for s in iter_streams(str(path)))
    assert count == 4


@pytest.mark.parametrize(
    "srs, name, swap",
    [
        (
            "urn:ogc:def:crs:EPSG:2056, crs:EPSG:5728",
            "CH1903+ / LV95 + LN02 height",
            False,
        ),
        (
            "urn:ogc:def:crs,crs:EPSG::25832,crs:EPSG::7837",
            "ETRS89 / UTM zone 32N + DHHN2016 height",
            False,
        ),
        (
            "urn:adv:crs:ETRS89_UTM32*DE_DHHN2016_NH",
            "ETRS89 / UTM zone 32N + DHHN2016 height",
            False,
        ),
        (
            "http://www.opengis.net/def/crs/EPSG/0/6697",
            "JGD2011 + JGD2011 (vertical) height",
            True,
        ),
        ("urn:ogc:def:crs:EPSG:6.12:4326", "WGS 84", True),
        ("EPSG:4326", "WGS 84", False),
    ],
)
def test_resolve_crs(srs, name, swap):
    crs, swapped = resolve_crs(srs)
    assert crs.name == name and swapped == swap


def test_resolve_crs_fallback():
    assert resolve_crs(None, 25832)[0].to_epsg() == 25832
    with pytest.raises(Exception, match="Missing spatial reference"):
        resolve_crs(None)


def test_horizontal_only_gets_vertical_datum():
    crs, _ = resolve_crs("EPSG:25832")
    crs, _ = wgs84_transformer(crs, True, 7837)
    assert crs.is_compound and "DHHN2016" in crs.name
    crs2, _ = wgs84_transformer(resolve_crs("EPSG:25832")[0], False)
    assert not crs2.is_compound


def _area(soup):
    t = soup.reshape(-1, 3, 3)
    return float(
        np.linalg.norm(np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]), axis=1).sum() / 2
    )


def test_triangulate_vertical_and_concave():
    wall = np.array(WALL, dtype=float)
    assert _area(triangulate([wall])) == pytest.approx(100)
    # concave quad (dart): the 0-2 diagonal lies outside
    dart = np.array([(0, 0, 0), (2, 1, 0), (4, 0, 0), (2, 3, 0)], dtype=float)
    assert _area(triangulate([dart])) == pytest.approx(4)


def test_triangulate_with_hole_on_tilted_plane():
    outer = np.array(
        [(0, 0, 0), (10, 0, 5), (10, 10, 5), (0, 10, 0), (-1, 5, -0.5)], dtype=float
    )
    hole = np.array([(2, 2, 1), (2, 4, 1), (4, 4, 2), (4, 2, 2)], dtype=float)
    full = _area(triangulate([outer]))
    holed = _area(triangulate([outer, hole]))
    assert full - holed == pytest.approx(4 * np.sqrt(1.25))


def test_triangulate_degenerate():
    assert (
        triangulate(
            [np.array([(0, 0, 0), (1, 1, 1), (2, 2, 2), (3, 3, 3)], dtype=float)]
        )
        is None
    )
