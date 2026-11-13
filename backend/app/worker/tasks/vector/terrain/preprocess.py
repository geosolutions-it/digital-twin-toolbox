"""Prepare a DEM for tiling: resolve the bucket input, warp to WGS84, optionally
shift geoid heights to ellipsoidal."""

import os

from osgeo import gdal, osr

gdal.UseExceptions()


def resolve_input(key, storage, scratch):
    """Local DEM path, a single GeoTIFF."""
    dest = os.path.join(scratch, os.path.basename(key))
    storage.download_file(key, dest)
    return dest


def _horizontal_epsg(path):
    srs = osr.SpatialReference()
    srs.ImportFromWkt(gdal.Open(path).GetProjection())
    return srs.GetAuthorityCode(None)


def warp_to_wgs84(src_path, scratch, to_ellipsoidal=False, source_vertical_epsg=3855):
    """gdalwarp to EPSG:4326; optional geoid->ellipsoid via a compound vertical CRS.
    Needs the PROJ geoid grid present (PROJ_NETWORK=ON)."""
    dst = os.path.join(scratch, "dem_4326.tif")
    if to_ellipsoidal:
        epsg = _horizontal_epsg(src_path)
        src_srs = f"EPSG:{epsg}+{source_vertical_epsg}" if epsg else None
        gdal.Warp(
            dst,
            src_path,
            srcSRS=src_srs,
            dstSRS="EPSG:4326+4979",
            resampleAlg="bilinear",
        )
    else:
        gdal.Warp(dst, src_path, dstSRS="EPSG:4326", resampleAlg="bilinear")
    return dst
