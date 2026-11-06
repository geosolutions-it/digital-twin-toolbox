"""Shared bucket vector reading: download, open the layer, reproject to WGS84 (optionally ellipsoidal)."""
import os
from decimal import Decimal

from osgeo import ogr, osr
from pyproj import CRS


def resolve_input(source, storage, scratch):
    """Download the bucket vector to scratch; a .zip opens via /vsizip."""
    key = source['key']
    if key.lower().endswith('.zip'):
        dest = os.path.join(scratch, 'index.zip')
        storage.download_file(key, dest)
        return f"/vsizip/{dest}"
    base, ext = os.path.splitext(key)
    dest = os.path.join(scratch, 'index' + (ext or '.geojson'))
    storage.download_file(key, dest)
    if ext.lower() == '.shp':
        for side in ('.shx', '.dbf', '.prj', '.cpg'):
            for candidate in (base + side, base + side.upper()):
                if storage.exists(candidate):
                    storage.download_file(candidate, os.path.join(scratch, 'index' + side))
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


def wgs84_transform(layer, to_ellipsoidal=False):
    """Layer CRS -> EPSG:4326; with to_ellipsoidal, EGM2008 heights (3855) -> ellipsoidal (4979)."""
    src_srs = layer.GetSpatialRef()
    if src_srs is None:
        raise Exception("Missing spatial reference system")
    dst_srs = osr.SpatialReference()
    if to_ellipsoidal:
        epsg = src_srs.GetAuthorityCode(None) or CRS(src_srs.ExportToWkt()).to_epsg()
        if not epsg:
            raise Exception("Source CRS EPSG is required for ellipsoidal height conversion")
        src_srs = osr.SpatialReference()
        src_srs.SetFromUserInput(f"EPSG:{epsg}+3855")
        dst_srs.SetFromUserInput("EPSG:4326+4979")
    else:
        dst_srs.ImportFromEPSG(4326)
    src_srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    dst_srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    return osr.CoordinateTransformation(src_srs, dst_srs)
