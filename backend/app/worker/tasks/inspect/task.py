"""Attribute schema and preview sample of bucket vectors."""

import tempfile

from osgeo import ogr

from app.core.celery_app import celery
from app.core.storage import get_storage
from app.worker.lib.geo.ogr import (
    coerce,
    iter_features,
    open_layer,
    resolve_input,
    wgs84_transform,
)


@celery.task(name="read_vector_fields")
def read_vector_fields(options):
    """Attribute schema + a first-feature sample for a bucket vector, for the
    expression editor. Reads one feature; no reprojection or extrusion."""
    key = options["key"]
    storage = get_storage()
    with tempfile.TemporaryDirectory() as scratch:
        path = resolve_input(key, storage, scratch)
        ds, layer = open_layer(path)
        defn = layer.GetLayerDefn()
        fields = [
            {
                "name": defn.GetFieldDefn(i).GetName(),
                "type": defn.GetFieldDefn(i).GetTypeName(),
            }
            for i in range(defn.GetFieldCount())
        ]
        feat = layer.GetNextFeature()
        properties = {}
        if feat is not None:
            for f in fields:
                properties[f["name"]] = coerce(feat.GetField(f["name"]))
        name = ogr.GeometryTypeToName(layer.GetGeomType())
        if "Unknown" in name and feat is not None and feat.GetGeometryRef() is not None:
            name = feat.GetGeometryRef().GetGeometryName()
        geometry_type = (
            "Point" if "Point" in name else "Polygon" if "Polygon" in name else name
        )
        return {
            "count": layer.GetFeatureCount(),
            "fields": fields,
            "properties": properties,
            "geometry_type": geometry_type,
        }


def _count_upto(layer, n):
    """Filtered feature count capped at n (a full count scans every record)."""
    layer.ResetReading()
    count = 0
    while count < n and layer.GetNextFeature() is not None:
        count += 1
    return count


def _sample_window(layer, limit):
    """Source-CRS rect around the first feature holding about `limit` features, or None."""
    total = layer.GetFeatureCount()
    first = layer.GetNextFeature()
    if total <= limit or first is None or first.GetGeometryRef() is None:
        return None
    min_x, max_x, min_y, max_y = layer.GetExtent()
    centre = first.GetGeometryRef().Centroid()
    cx, cy = centre.GetX(), centre.GetY()
    half = max(((max_x - min_x) * (max_y - min_y) * limit / total) ** 0.5 / 2, 1.0)
    for _ in range(8):
        layer.SetSpatialFilterRect(cx - half, cy - half, cx + half, cy + half)
        enough = _count_upto(layer, limit // 2) >= limit // 2
        layer.SetSpatialFilter(None)
        if enough:
            break
        half *= 2
    return [cx - half, cy - half, cx + half, cy + half]


@celery.task(name="read_vector_sample")
def read_vector_sample(options):
    """Up to `limit` neighbouring features as WGS84 GeoJSON, heights as the workers produce them."""
    key = options["key"]
    ellipsoidal = bool(options.get("ellipsoidal"))
    limit = int(options.get("limit") or 200)
    storage = get_storage()
    with tempfile.TemporaryDirectory() as scratch:
        path = resolve_input(key, storage, scratch)
        ds, layer = open_layer(path)
        transform = wgs84_transform(layer, ellipsoidal)
        window = _sample_window(layer, limit)
        if window:
            layer.SetSpatialFilterRect(*window)
        features = []
        for geometry, properties in iter_features(layer, transform, ellipsoidal):
            features.append(
                {"type": "Feature", "geometry": geometry, "properties": properties}
            )
            if len(features) >= limit:
                break
        return {"type": "FeatureCollection", "features": features}
