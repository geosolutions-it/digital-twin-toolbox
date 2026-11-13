import os

from osgeo import gdal
from pyproj import CRS

from app.worker.lib.geo.ogr import height_transform

gdal.UseExceptions()


def warp_to_wgs84(src_path, scratch, height_reference="source", vertical_epsg=None):
    dst = os.path.join(scratch, "dem_4326.tif")
    ds = gdal.Open(src_path)
    srs = ds.GetSpatialRef()
    if srs is None:
        raise Exception("The DEM has no CRS")
    gt = ds.GetGeoTransform()
    _, src, target = height_transform(
        CRS(srs.ExportToWkt(["FORMAT=WKT2_2019"])),
        gt[0] + gt[1] * ds.RasterXSize / 2,
        gt[3] + gt[5] * ds.RasterYSize / 2,
        height_reference,
        vertical_epsg,
    )
    gdal.Warp(
        dst,
        ds,
        srcSRS=src.to_wkt(),
        dstSRS=target.to_wkt(),
        resampleAlg="bilinear",
    )
    return dst
