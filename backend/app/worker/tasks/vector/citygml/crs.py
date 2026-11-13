import re

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


def is_ellipsoidal(crs):
    return crs.is_geographic and not crs.is_compound and len(crs.axis_info) == 3


def wgs84_transformer(crs, to_ellipsoidal=False, vertical_epsg=None):
    if not to_ellipsoidal:
        return crs, Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    if not crs.is_compound and not is_ellipsoidal(crs):
        vertical = CRS.from_epsg(int(vertical_epsg or DEFAULT_VERTICAL_EPSG))
        crs = CompoundCRS(f"{crs.name} + {vertical.name}", [crs, vertical])
    return crs, Transformer.from_crs(crs, "EPSG:4979", always_xy=True, only_best=True)
