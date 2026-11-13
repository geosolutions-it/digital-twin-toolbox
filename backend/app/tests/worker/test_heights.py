import pytest

pytest.importorskip("numpy")
pytest.importorskip("osgeo.osr")

from pyproj import CRS  # noqa: E402

from app.worker.lib.geo.crs import (  # noqa: E402
    HeightTransformError,
    check_height_shift,
    height_crs_pair,
)
from app.worker.lib.geo.ogr import height_transform  # noqa: E402

# Trieste, EPSG:25833
X, Y = 404000.0, 5054000.0


@pytest.mark.parametrize(
    ("source", "reference", "vertical", "src_name", "dst_name", "shifts"),
    [
        ("EPSG:25833", "source", None, "UTM zone 33N", "WGS 84", False),
        ("EPSG:25833", "ellipsoidal", None, "EGM2008", "WGS 84", True),
        ("EPSG:25833", "ellipsoidal", 5783, "DHHN92", "WGS 84", True),
        ("EPSG:25833+5783", "ellipsoidal", 3855, "DHHN92", "WGS 84", True),
        ("EPSG:4937", "ellipsoidal", None, "ETRS89", "WGS 84", False),
        ("EPSG:25833", "orthometric", None, "UTM zone 33N", "EGM2008", True),
        ("EPSG:25833+3855", "orthometric", None, "EGM2008", "EGM2008", False),
        ("EPSG:25833+5783", "orthometric", None, "DHHN92", "EGM2008", True),
    ],
)
def test_height_crs_pair(source, reference, vertical, src_name, dst_name, shifts):
    src, dst, moves = height_crs_pair(CRS(source), reference, vertical)
    assert src_name in src.name and dst_name in dst.name
    assert moves is shifts
    if reference == "source":
        assert len(dst.axis_info) == 2
    elif reference == "ellipsoidal":
        assert len(dst.axis_info) == 3 and not dst.is_compound
    else:
        assert dst.is_compound
    if reference == "orthometric" and not CRS(source).is_compound:
        assert len(src.axis_info) == 3


def test_projected_target_keeps_the_horizontal_crs():
    utm = CRS("EPSG:25833")
    _, dst, _ = height_crs_pair(utm, "ellipsoidal", target=utm)
    assert dst.to_2d() == utm and len(dst.axis_info) == 3


def test_unknown_reference_raises():
    with pytest.raises(ValueError):
        height_crs_pair(CRS("EPSG:25833"), "geoid")


def test_check_height_shift():
    check_height_shift([100.0, 50.0], [145.3, 95.3], CRS("EPSG:25833"))
    with pytest.raises(HeightTransformError, match="missing PROJ geoid grid"):
        check_height_shift([100.0, 50.0], [100.0, 50.0], CRS("EPSG:25833"))


def test_a_geoid_proj_cannot_apply_fails_instead_of_keeping_heights():
    # no transformation exists for Genova 1942 heights, so PROJ keeps them as they are
    with pytest.raises(HeightTransformError):
        height_transform(CRS("EPSG:25833+5214"), X, Y, "ellipsoidal")


def test_source_heights_are_not_probed():
    transform, _, _ = height_transform(CRS("EPSG:25833+5214"), X, Y, "source")
    assert transform.TransformPoint(X, Y, 100.0)[2] == pytest.approx(100.0)


def test_egm2008_round_trip_when_the_grid_is_available():
    try:
        to_ellipsoid, _, _ = height_transform(CRS("EPSG:25833"), X, Y, "ellipsoidal")
        to_geoid, _, _ = height_transform(
            CRS("EPSG:25833").to_3d(), X, Y, "orthometric"
        )
    except HeightTransformError:
        pytest.skip("EGM2008 grid not available")
    ellipsoidal = to_ellipsoid.TransformPoint(X, Y, 100.0)[2]
    assert ellipsoidal == pytest.approx(145.3, abs=1.0)
    assert to_geoid.TransformPoint(X, Y, ellipsoidal)[2] == pytest.approx(
        100.0, abs=0.01
    )
