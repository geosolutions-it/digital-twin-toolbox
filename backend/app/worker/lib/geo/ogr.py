"""Shared bucket vector reading: download, open the layer, reproject to WGS84 with the requested heights."""

import json
import os
from decimal import Decimal

from osgeo import ogr, osr
from pyproj import CRS

from app.worker.lib.geo.crs import WGS84, check_height_shift, height_crs_pair


def resolve_input(key, storage, scratch):
    """Download the bucket vector to scratch; a .zip opens via /vsizip."""
    if key.lower().endswith(".zip"):
        dest = os.path.join(scratch, "index.zip")
        storage.download_file(key, dest)
        return f"/vsizip/{dest}"
    base, ext = os.path.splitext(key)
    dest = os.path.join(scratch, "index" + (ext or ".geojson"))
    storage.download_file(key, dest)
    if ext.lower() == ".shp":
        for side in (".shx", ".dbf", ".prj", ".cpg"):
            for candidate in (base + side, base + side.upper()):
                if storage.exists(candidate):
                    storage.download_file(
                        candidate, os.path.join(scratch, "index" + side)
                    )
                    break
    return dest


def coerce(value):
    return float(value) if isinstance(value, Decimal) else value


def open_layer(path):
    """-> (datasource, first layer); keep the datasource referenced while using the layer."""
    ds = ogr.Open(path)
    if ds is None:
        raise Exception(f"Cannot open vector source {path}")
    return ds, ds.GetLayer(0)


def field_names(layer):
    defn = layer.GetLayerDefn()
    return [defn.GetFieldDefn(i).GetName() for i in range(defn.GetFieldCount())]


def osr_srs(crs):
    srs = osr.SpatialReference()
    srs.ImportFromWkt(crs.to_wkt())
    srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    return srs


def height_transform(
    source, x, y, height_reference="source", vertical_epsg=None, target=WGS84
):
    """-> (GDAL transformation, source CRS, target CRS), probed at x, y in the source CRS."""
    src, dst, shifts = height_crs_pair(source, height_reference, vertical_epsg, target)
    transform = osr.CoordinateTransformation(osr_srs(src), osr_srs(dst))
    if shifts:
        check_height_shift(0.0, transform.TransformPoint(x, y, 0.0)[2], src)
    return transform, src, dst


def wgs84_transform(layer, height_reference="source", vertical_epsg=None):
    srs = layer.GetSpatialRef()
    if srs is None:
        raise Exception("Missing spatial reference system")
    minx, maxx, miny, maxy = layer.GetExtent()
    transform, _, _ = height_transform(
        CRS(srs.ExportToWkt(["FORMAT=WKT2_2019"])),
        (minx + maxx) / 2,
        (miny + maxy) / 2,
        height_reference,
        vertical_epsg,
    )
    return transform


def iter_features(layer, transform, force_3d=False):
    """-> (WGS84 GeoJSON geometry, properties) per feature with a geometry, within any spatial filter."""
    names = field_names(layer)
    for feat in layer:
        geom = feat.GetGeometryRef()
        if geom is None:
            continue
        geom = geom.Clone()
        if force_3d:
            geom.Set3D(True)
        geom.Transform(transform)
        properties = {name: coerce(feat.GetField(name)) for name in names}
        yield json.loads(geom.ExportToJson()), properties
