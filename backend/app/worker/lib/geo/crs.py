import re

import numpy as np
from pyproj import CRS, Transformer
from pyproj.crs import CompoundCRS

# EPSG:2056, urn:...:EPSG::25832, urn:...:EPSG:6.12:25832, .../EPSG/0/6697
_EPSG = re.compile(r"EPSG(?:/0/|:+(?:[\d.]+:)?)(\d+)", re.I)
# short EPSG:n forms keep x/y order, as in GDAL
_SHORT_EPSG = re.compile(r"\s*EPSG:\d+(\+EPSG:\d+)?\s*$", re.I)
_ADV = {
    "ETRS89_UTM32": 25832,
    "ETRS89_UTM33": 25833,
    "DE_DHDN_3GK2": 31466,
    "DE_DHDN_3GK3": 31467,
    "DE_DHDN_3GK4": 31468,
    "DE_DHHN92_NH": 5783,
    "DE_DHHN2016_NH": 7837,
}
# EGM2008
DEFAULT_VERTICAL_EPSG = 3855


def epsg_codes(name):
    return [int(c) for c in _EPSG.findall(name or "")]


def resolve_crs(srs_name, horizontal_epsg=None):
    """Geographic axes are lat/lon unless srsName is the short EPSG:n form, as in GDAL."""
    codes = []
    if srs_name:
        codes = [int(c) for c in _EPSG.findall(srs_name)]
        if not codes:
            codes = [
                _ADV[p] for p in srs_name.rsplit(":", 1)[-1].split("*") if p in _ADV
            ]
    if codes:
        crs = CRS.from_user_input("+".join(f"EPSG:{c}" for c in codes[:2]))
    elif srs_name and not horizontal_epsg:
        crs = CRS.from_user_input(srs_name)
    elif horizontal_epsg:
        crs = CRS.from_epsg(int(horizontal_epsg))
    else:
        raise Exception(
            "Missing spatial reference system: no srsName in the file and no horizontal EPSG set"
        )
    swap = crs.is_geographic and not _SHORT_EPSG.match(srs_name or "")
    return crs, swap


WGS84 = CRS.from_epsg(4326)


class HeightTransformError(Exception):
    pass


def is_ellipsoidal(crs):
    """3D geographic or projected CRS: heights above the ellipsoid."""
    return not crs.is_compound and not crs.is_geocentric and len(crs.axis_info) == 3


def _horizontal(crs):
    if crs.is_compound:
        return crs.sub_crs_list[0]
    return crs.to_2d() if is_ellipsoidal(crs) else crs


def _vertical(crs):
    if crs.is_compound:
        return next((c for c in crs.sub_crs_list if c.is_vertical), None)
    return None


def _compound(horizontal, vertical):
    return CompoundCRS(f"{horizontal.name} + {vertical.name}", [horizontal, vertical])


def height_crs_pair(source, height_reference, vertical_epsg=None, target=WGS84):
    """-> (source CRS, target CRS, whether heights must change).
    vertical_epsg is the geoid on the orthometric side; a vertical CRS declared by the source wins."""
    horizontal = _horizontal(source)
    declared = _vertical(source)
    geoid = CRS.from_epsg(int(vertical_epsg or DEFAULT_VERTICAL_EPSG))
    if height_reference == "source":
        return horizontal, target, False
    if height_reference == "ellipsoidal":
        if is_ellipsoidal(source):
            return source, target.to_3d(), False
        return _compound(horizontal, declared or geoid), target.to_3d(), True
    if height_reference == "orthometric":
        if declared is not None:
            return source, _compound(target, geoid), declared != geoid
        return horizontal.to_3d(), _compound(target, geoid), True
    raise ValueError(f"Unknown height reference {height_reference!r}")


def check_height_shift(before, after, source):
    """PROJ keeps the heights instead of failing when it lacks the geoid grid."""
    if np.allclose(np.asarray(before), np.asarray(after), atol=1e-4):
        raise HeightTransformError(
            f"No vertical transformation from {source.name} (missing PROJ geoid grid? "
            "set PROJ_NETWORK=ON or install the grid)"
        )


def wgs84_transformer(crs, height_reference="source", vertical_epsg=None):
    """-> (source CRS, pyproj Transformer to WGS84, whether heights must change)."""
    src, dst, shifts = height_crs_pair(crs, height_reference, vertical_epsg)
    return src, Transformer.from_crs(src, dst, always_xy=True, only_best=True), shifts
