"""Prepare a DEM for tiling: resolve the bucket input, warp to WGS84, optionally
shift geoid heights to ellipsoidal."""
import os

from osgeo import gdal, osr

gdal.UseExceptions()


def resolve_input(source, storage, scratch):
    """Local DEM path. A .vrt pulls its sibling rasters too (flat folder assumed)
    so relative refs resolve; a single .tif is downloaded alone."""
    key = source['key']
    if key.lower().endswith('.vrt'):
        prefix = key.rsplit('/', 1)[0] + '/' if '/' in key else ''
        local_vrt = None
        for k in storage.list(prefix):
            dest = os.path.join(scratch, os.path.basename(k))
            storage.download_file(k, dest)
            if k.lower().endswith('.vrt'):
                local_vrt = dest
        if not local_vrt:
            raise Exception(f"No .vrt found next to {key!r}")
        return local_vrt
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
    dst = os.path.join(scratch, 'dem_4326.tif')
    if to_ellipsoidal:
        epsg = _horizontal_epsg(src_path)
        src_srs = f"EPSG:{epsg}+{source_vertical_epsg}" if epsg else None
        gdal.Warp(dst, src_path, srcSRS=src_srs, dstSRS="EPSG:4326+4979",
                  resampleAlg="bilinear")
    else:
        gdal.Warp(dst, src_path, dstSRS="EPSG:4326", resampleAlg="bilinear")
    return dst
