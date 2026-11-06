"""Asset inspection on upload; attribute schema and preview sample of bucket vectors."""
import json
import os
import tempfile

from osgeo import gdal, ogr
from pyproj import CRS

from app.core.storage import get_storage
from app.worker.common.utils import get_asset_upload_path
from app.worker.main import celery, AssetDatabaseTask
from app.worker.tasks.vector.source import coerce, field_names, open_layer, resolve_input, wgs84_transform


def _empty_payload():
    return {'metadata': False, 'stats': False, 'sample': False, 'epsg': None, 'horizontal_epsg': None, 'vertical_epsg': None}


def _write_vector_sample(source_path, output_path, epsg, to_ellipsoidal_height, limit):
    kwargs = dict(format='GeoJSON', dstSRS='EPSG:4326', dim='XYZ')
    if to_ellipsoidal_height:
        kwargs['srcSRS'] = f'EPSG:{epsg}+3855'
        kwargs['dstSRS'] = 'EPSG:4326+4979'
    if limit is not None:
        kwargs['limit'] = limit

    if os.path.isfile(output_path):
        os.remove(output_path)

    gdal.VectorTranslate(
        output_path,
        source_path,
        options=gdal.VectorTranslateOptions(**kwargs),
    )

    if not os.path.isfile(output_path):
        raise Exception("Sample not created")


@celery.task(name="inspect_vector", base=AssetDatabaseTask)
def inspect_vector(options):
    asset = options['asset']
    asset_id = asset['id']
    extension = asset['extension']
    to_ellipsoidal_height = options.get('to_ellipsoidal_height', False)

    asset_file_path = get_asset_upload_path(f"{asset_id}/index{extension}")

    ds = ogr.Open(asset_file_path)
    if ds is None:
        raise Exception(f"Cannot open {asset_file_path}")

    layers_info = []
    for i in range(ds.GetLayerCount()):
        layer = ds.GetLayer(i)
        layer_defn = layer.GetLayerDefn()
        geom_fields = []
        for j in range(layer_defn.GetGeomFieldCount()):
            gfd = layer_defn.GetGeomFieldDefn(j)
            srs = gfd.GetSpatialRef()
            geom_fields.append({
                'type': ogr.GeometryTypeToName(gfd.GetType()),
                'coordinateSystem': {'wkt': srs.ExportToWkt()} if srs else None,
            })
        layers_info.append({
            'name': layer.GetName(),
            'featureCount': layer.GetFeatureCount(),
            'geometryFields': geom_fields,
        })

    info = {
        'driverShortName': ds.GetDriver().GetName(),
        'layers': layers_info,
    }

    layers = info['layers']
    if len(layers) > 1:
        raise Exception("Multiple layers not supported")

    geometry_fields = layers[0]['geometryFields']
    if len(geometry_fields) > 1:
        raise Exception("Multiple geometry types not supported")

    geometry_type = geometry_fields[0]['type']

    if 'Multi' in geometry_type:
        raise Exception("Multi geometry is not supported")

    coordinate_system = geometry_fields[0].get('coordinateSystem')
    if coordinate_system:
        epsg = CRS(coordinate_system['wkt']).to_epsg()
    else:
        raise Exception("Missing spatial reference system")

    supported_geometry = 'Polygon' in geometry_type or 'Point' in geometry_type
    if not supported_geometry:
        raise Exception(f"{geometry_type} type is not supported")

    asset_type = info['driverShortName']

    if 'Point' in geometry_type:
        geometry_type = 'Point'
    if 'Polygon' in geometry_type:
        geometry_type = 'Polygon'

    with open(get_asset_upload_path(f"{asset_id}/metadata.json"), 'w') as f:
        json.dump(info, f)

    size_kb = asset['content_size'] / 1024
    feature_count = layers[0]['featureCount']
    limit = None
    if size_kb > 1000:
        limit = round((feature_count * 1000) / size_kb)

    _write_vector_sample(asset_file_path, get_asset_upload_path(f"{asset_id}/sample.json"), epsg, to_ellipsoidal_height, limit)

    return {
        'asset_type': asset_type,
        'geometry_type': geometry_type,
        'payload': {**_empty_payload(), 'metadata': True, 'sample': True, 'epsg': epsg}
    }


@celery.task(name="inspect_raster", base=AssetDatabaseTask)
def inspect_raster(options):
    asset = options['asset']
    asset_id = asset['id']
    extension = asset['extension']

    asset_file_path = get_asset_upload_path(f"{asset_id}/index{extension}")

    info = gdal.Info(f'{asset_file_path}', format='json')

    epsg = CRS(info['coordinateSystem']['wkt']).to_epsg()

    with open(get_asset_upload_path(f"{asset_id}/metadata.json"), 'w') as f:
        json.dump(info, f)

    return {
        'asset_type': None,
        'geometry_type': None,
        'payload': {**_empty_payload(), 'metadata': True, 'epsg': epsg}
    }


@celery.task(name="read_vector_fields")
def read_vector_fields(options):
    """Attribute schema + a first-feature sample for a bucket vector, for the
    expression editor. Reads one feature; no reprojection or extrusion."""
    key = options['key']
    storage = get_storage()
    with tempfile.TemporaryDirectory() as scratch:
        path = resolve_input({'key': key}, storage, scratch)
        ds, layer = open_layer(path)
        defn = layer.GetLayerDefn()
        fields = [
            {'name': defn.GetFieldDefn(i).GetName(), 'type': defn.GetFieldDefn(i).GetTypeName()}
            for i in range(defn.GetFieldCount())
        ]
        feat = layer.GetNextFeature()
        properties = {}
        if feat is not None:
            for f in fields:
                properties[f['name']] = coerce(feat.GetField(f['name']))
        name = ogr.GeometryTypeToName(layer.GetGeomType())
        if 'Unknown' in name and feat is not None and feat.GetGeometryRef() is not None:
            name = feat.GetGeometryRef().GetGeometryName()
        geometry_type = 'Point' if 'Point' in name else 'Polygon' if 'Polygon' in name else name
        return {'count': layer.GetFeatureCount(), 'fields': fields,
                'properties': properties, 'geometry_type': geometry_type}

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
    """Up to `limit` neighbouring features as WGS84 GeoJSON."""
    key = options['key']
    limit = int(options.get('limit') or 200)
    storage = get_storage()
    with tempfile.TemporaryDirectory() as scratch:
        path = resolve_input({'key': key}, storage, scratch)
        ds, layer = open_layer(path)
        transform = wgs84_transform(layer)
        names = field_names(layer)
        window = _sample_window(layer, limit)
        if window:
            layer.SetSpatialFilterRect(*window)
        layer.ResetReading()
        features = []
        for feat in layer:
            geom = feat.GetGeometryRef()
            if geom is None:
                continue
            geom = geom.Clone()
            geom.Transform(transform)
            features.append({
                'type': 'Feature',
                'geometry': json.loads(geom.ExportToJson()),
                'properties': {name: coerce(feat.GetField(name)) for name in names},
            })
            if len(features) >= limit:
                break
        ds = None
        return {'type': 'FeatureCollection', 'features': features}
