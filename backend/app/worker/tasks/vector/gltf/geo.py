"""lon/lat/height -> local ENU metres and the ENU->ECEF tileset root transform."""
import numpy as np
from pyproj import Transformer

# always_xy: lon,lat order. 4978 = ECEF.
_to_ecef = Transformer.from_crs(4326, 4978, always_xy=True)


def lonlath_to_ecef(lon, lat, h):
    x, y, z = _to_ecef.transform(lon, lat, h)
    return np.array([x, y, z], dtype=np.float64)


def enu_basis(lon_deg, lat_deg):
    """East, north, up unit vectors (in ECEF) at a geodetic origin."""
    lon = np.radians(lon_deg)
    lat = np.radians(lat_deg)
    sl, cl = np.sin(lon), np.cos(lon)
    sp, cp = np.sin(lat), np.cos(lat)
    east = np.array([-sl, cl, 0.0])
    north = np.array([-sp * cl, -sp * sl, cp])
    up = np.array([cp * cl, cp * sl, sp])
    return east, north, up


def root_transform(origin_ecef, east, north, up):
    """Column-major 4x4 mapping local ENU (Z-up) metres to ECEF, for tileset root."""
    return [
        float(east[0]), float(east[1]), float(east[2]), 0.0,
        float(north[0]), float(north[1]), float(north[2]), 0.0,
        float(up[0]), float(up[1]), float(up[2]), 0.0,
        float(origin_ecef[0]), float(origin_ecef[1]), float(origin_ecef[2]), 1.0,
    ]


class LocalFrame:
    """Reusable projection from lon/lat/h to ENU metres at a fixed origin."""

    def __init__(self, origin_lon, origin_lat, origin_h=0.0):
        self.origin_lon = origin_lon
        self.origin_lat = origin_lat
        self.origin_ecef = lonlath_to_ecef(origin_lon, origin_lat, origin_h)
        self.east, self.north, self.up = enu_basis(origin_lon, origin_lat)

    def to_enu(self, lonlath):
        """(N,3) lon,lat,h -> (N,3) float64 east,north,up metres."""
        lonlath = np.asarray(lonlath, dtype=np.float64)
        xs, ys, zs = _to_ecef.transform(lonlath[:, 0], lonlath[:, 1], lonlath[:, 2])
        d = np.stack([xs, ys, zs], axis=1) - self.origin_ecef
        e = d @ self.east
        n = d @ self.north
        u = d @ self.up
        return np.stack([e, n, u], axis=1)

    def transform(self):
        return root_transform(self.origin_ecef, self.east, self.north, self.up)
