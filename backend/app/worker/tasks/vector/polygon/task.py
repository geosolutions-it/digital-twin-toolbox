import json
import os
import shutil
import tempfile
from decimal import Decimal

import numpy as np
from osgeo import gdal, ogr, osr
from pyproj import CRS

from app.core.config import settings
from app.core.storage import get_storage, output_key
from app.worker.common.expression import parse_expression
from app.worker.common.processes import (
    export_geojson_from_postgres, import_vector_to_postgres,
)
from app.worker.common.utils import get_asset_upload_path
from app.worker.main import celery, AssetDatabaseTask, PipelineDatabaseTask
from app.worker.tasks.vector.gltf.geo import LocalFrame
from app.worker.tasks.vector.gltf.tiler import build_tileset
from app.worker.tasks.vector.polygon.polyhedron import geometry_to_polyhedral_surface


def _empty_payload():
    return {'metadata': False, 'stats': False, 'sample': False, 'epsg': None, 'horizontal_epsg': None, 'vertical_epsg': None}


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

    table_name = f'asset_{asset_id}'.replace('-', '_')
    geometry_column_name = 'geom'
    fid_column_name = 'gid'
    size_kb = asset['content_size'] / 1024
    feature_count = layers[0]['featureCount']
    limit = None
    if size_kb > 1000:
        limit = (feature_count * 1000) / size_kb

    import_vector_to_postgres(asset_file_path, table_name, geometry_column_name, fid_column_name, epsg, to_ellipsoidal_height)
    export_geojson_from_postgres(get_asset_upload_path(f"{asset_id}/sample.json"), table_name, limit)

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


def _coerce(value):
    return float(value) if isinstance(value, Decimal) else value


def _materialize(storage, key, scratch, name):
    dest = os.path.join(scratch, name)
    storage.download_file(key, dest)
    return dest


def _resolve_input(source, storage, scratch):
    """Download the bucket vector to scratch; a .zip is opened via /vsizip so GDAL
    finds the shapefile inside, no .shp.zip naming required."""
    key = source['key']
    if key.lower().endswith('.zip'):
        local = _materialize(storage, key, scratch, 'index.zip')
        return f"/vsizip/{local}"
    ext = os.path.splitext(key)[1] or '.geojson'
    return _materialize(storage, key, scratch, f"index{ext}")


def _ensure_z(coords):
    if coords and isinstance(coords[0], (int, float)):
        return [coords[0], coords[1], coords[2] if len(coords) > 2 else 0.0]
    return [_ensure_z(c) for c in coords]


def _read_raw_features(path, config, default_config):
    """Open the vector with OGR, reproject to WGS84 (optionally ellipsoidal), and
    collect per-feature footprints + resolved heights. Returns (features, (lo, hi))."""
    ds = ogr.Open(path)
    if ds is None:
        raise Exception(f"Cannot open vector source {path}")
    layer = ds.GetLayer(0)
    src_srs = layer.GetSpatialRef()
    if src_srs is None:
        raise Exception("Missing spatial reference system")

    to_ellipsoidal = config.get('to_ellipsoidal_height', False)
    dst_srs = osr.SpatialReference()
    if to_ellipsoidal:
        # assume orthometric heights on EGM2008 (3855); convert to WGS84 ellipsoidal (4979)
        epsg = src_srs.GetAuthorityCode(None) or CRS(src_srs.ExportToWkt()).to_epsg()
        if not epsg:
            raise Exception("Source CRS EPSG is required for ellipsoidal height conversion")
        src_for_transform = osr.SpatialReference()
        src_for_transform.SetFromUserInput(f"EPSG:{epsg}+3855")
        dst_srs.SetFromUserInput("EPSG:4326+4979")
    else:
        src_for_transform = src_srs
        dst_srs.ImportFromEPSG(4326)
    src_for_transform.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    dst_srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    transform = osr.CoordinateTransformation(src_for_transform, dst_srs)

    defn = layer.GetLayerDefn()
    field_names = [defn.GetFieldDefn(i).GetName() for i in range(defn.GetFieldCount())]

    lo = np.array([np.inf, np.inf, np.inf])
    hi = np.array([-np.inf, -np.inf, -np.inf])
    features = []
    for feat in layer:
        geom = feat.GetGeometryRef()
        if geom is None:
            continue
        geom = geom.Clone()
        if to_ellipsoidal:
            geom.Set3D(True)
        geom.Transform(transform)
        geometry = json.loads(geom.ExportToJson())
        gtype = geometry.get('type')
        if gtype == 'Polygon':
            parts = [geometry['coordinates']]
        elif gtype == 'MultiPolygon':
            parts = geometry['coordinates']
        else:
            continue

        properties = {name: _coerce(feat.GetField(name)) for name in field_names}
        feature_for_expr = {'type': 'Feature', 'properties': properties, 'geometry': geometry}
        lower = parse_expression('number', config['lower_limit_height'], feature_for_expr, default_config['lower_limit_height'])
        upper = parse_expression('number', config['upper_limit_height'], feature_for_expr, default_config['upper_limit_height'])

        parts = [_ensure_z(p) for p in parts]
        for poly in parts:
            for ring in poly:
                arr = np.asarray(ring, dtype=np.float64)
                lo = np.minimum(lo, arr.min(axis=0))
                hi = np.maximum(hi, arr.max(axis=0))

        features.append({
            'parts': parts,
            'lower': lower,
            'upper': upper,
            'remove_bottom': config['remove_bottom_surface'],
            'properties': properties,
        })

    return features, (lo, hi)


def _simplify_rings(rings, tolerance):
    """OGR SimplifyPreserveTopology on a footprint's ENU rings; never empties it."""
    poly = ogr.Geometry(ogr.wkbPolygon)
    for ring in rings:
        linear = ogr.Geometry(ogr.wkbLinearRing)
        for x, y in ring:
            linear.AddPoint_2D(float(x), float(y))
        poly.AddGeometry(linear)
    simplified = poly.SimplifyPreserveTopology(tolerance)
    if simplified is None or simplified.IsEmpty() or simplified.GetGeometryName() != 'POLYGON':
        return rings
    out = [
        [(r.GetX(j), r.GetY(j)) for j in range(r.GetPointCount())]
        for r in (simplified.GetGeometryRef(i) for i in range(simplified.GetGeometryCount()))
    ]
    return out or rings


def _rings_to_coords(rings, ground_z):
    return [[[float(x), float(y), ground_z] for x, y in ring] for ring in rings]


def _extrude_items(items, tolerance):
    """Tiler callback: extrude a set of features at a footprint-simplification tolerance."""
    all_verts = []
    counts = []
    props = []
    for it in items:
        payload = it['extrude']
        parts_tris = []
        for part in payload['parts']:
            rings = part['rings']
            if tolerance > 0:
                rings = _simplify_rings(rings, tolerance)
            geom = {'type': 'Polygon', 'coordinates': _rings_to_coords(rings, part['ground_z'])}
            options = {
                'lower_limit': payload['lower'],
                'upper_limit': payload['upper'],
                'translate_z': 0,
                'remove_bottom_surface': payload['remove_bottom'],
            }
            surface = geometry_to_polyhedral_surface(geom, options)
            if not surface:
                continue
            tris = np.asarray(surface, dtype=np.float64)
            parts_tris.append(tris[:, :3, :].reshape(-1, 3))
        if not parts_tris:
            continue
        verts = np.concatenate(parts_tris, axis=0)
        all_verts.append(verts)
        counts.append(len(verts))
        props.append(it['properties'])
    if not all_verts:
        return None
    return np.concatenate(all_verts, axis=0), counts, props


@celery.task(name="create_polygon_3dtiles", base=PipelineDatabaseTask)
def create_polygon_3dtiles(pipeline_extended):
    pipeline_id = pipeline_extended['id']
    source = pipeline_extended.get('source') or {}
    if not source.get('key'):
        raise Exception("Polygon pipeline requires a bucket source")

    pipeline_config = pipeline_extended.get('data') or {}
    default_config = {
        'lower_limit_height': None,
        'upper_limit_height': None,
        'translate_z': 0,
        'to_ellipsoidal_height': False,
        'remove_bottom_surface': True,
        'max_features_per_tile': 1000,
        'max_geometric_error': 500,
    }
    config = {**default_config, **pipeline_config}

    storage = get_storage()
    out_base = source.get('output_base') or output_key(pipeline_id)

    with tempfile.TemporaryDirectory() as scratch:
        input_path = _resolve_input(source, storage, scratch)
        raw, (lo, hi) = _read_raw_features(input_path, config, default_config)
        if not raw:
            raise Exception("No polygon features to tile")

        frame = LocalFrame((lo[0] + hi[0]) / 2.0, (lo[1] + hi[1]) / 2.0, (lo[2] + hi[2]) / 2.0)

        features = []
        for r in raw:
            part_payloads = []
            fmin = np.array([np.inf, np.inf])
            fmax = np.array([-np.inf, -np.inf])
            for poly in r['parts']:
                rings_enu = []
                ground_z = 0.0
                for idx, ring in enumerate(poly):
                    enu = frame.to_enu(np.asarray(ring, dtype=np.float64))
                    rings_enu.append(enu[:, :2])
                    if idx == 0:
                        ground_z = float(enu[:, 2].mean())
                        fmin = np.minimum(fmin, enu[:, :2].min(axis=0))
                        fmax = np.maximum(fmax, enu[:, :2].max(axis=0))
                part_payloads.append({'rings': rings_enu, 'ground_z': ground_z})
            features.append({
                'min': fmin,
                'max': fmax,
                'centroid': (fmin + fmax) / 2.0,
                'properties': r['properties'],
                'extrude': {
                    'parts': part_payloads,
                    'lower': r['lower'],
                    'upper': r['upper'],
                    'remove_bottom': r['remove_bottom'],
                },
            })

        tiles_dir = os.path.join(scratch, 'tiles')
        max_features = int(parse_expression('number', config['max_features_per_tile'], {}, default_config['max_features_per_tile']))
        max_ge = float(parse_expression('number', config['max_geometric_error'], {}, default_config['max_geometric_error']))
        build_tileset(features, tiles_dir, frame.transform(), _extrude_items,
                      max_features_per_tile=max_features, max_geometric_error=max_ge)

        zip_base = os.path.join(scratch, 'download')
        shutil.make_archive(zip_base, 'zip', tiles_dir)

        storage.delete_prefix(f"{out_base}/tiles")
        storage.upload_dir(tiles_dir, f"{out_base}/tiles")
        storage.upload_file(zip_base + '.zip', f"{out_base}/download.zip")

    base = settings.API_V1_STR
    return {
        'output': out_base,
        'tileset': f"{base}/{out_base}/tiles/tileset.json",
        'download': f"{base}/{out_base}/download.zip",
    }


@celery.task(name="read_vector_fields")
def read_vector_fields(options):
    """Attribute schema + a first-feature sample for a bucket vector, for the
    expression editor. Reads one feature; no reprojection or extrusion."""
    key = options['key']
    storage = get_storage()
    with tempfile.TemporaryDirectory() as scratch:
        path = _resolve_input({'key': key}, storage, scratch)
        ds = ogr.Open(path)
        if ds is None:
            raise Exception(f"Cannot open vector source {key}")
        layer = ds.GetLayer(0)
        defn = layer.GetLayerDefn()
        fields = [
            {'name': defn.GetFieldDefn(i).GetName(), 'type': defn.GetFieldDefn(i).GetTypeName()}
            for i in range(defn.GetFieldCount())
        ]
        feat = layer.GetNextFeature()
        properties = {}
        if feat is not None:
            for f in fields:
                properties[f['name']] = _coerce(feat.GetField(f['name']))
        return {'count': layer.GetFeatureCount(), 'fields': fields, 'properties': properties}
