"""DEM -> quantized-mesh pyramid + layer.json. Samples each tile and meshes it
as a regular grid so flat tiles still follow the ellipsoid. Cesium geographic/TMS."""
import json
import os

import numpy as np
from osgeo import gdal
from quantized_mesh_tile.global_geodetic import GlobalGeodetic

from app.worker.tasks.vector.terrain.qmesh.writer import encode_tile
from app.worker.tasks.vector.terrain.qmesh.water import tile_water_mask

gdal.UseExceptions()

GRID = 257  # DEM sampling grid per tile
MESH_N = 33  # regular mesh vertices per tile side; enough to follow the ellipsoid
FULL_COVER_LEVEL = 2  # cover the whole world at these coarse levels so the globe is never half-missing


def _max_zoom(geodetic, pixel_deg, cap=18):
    """Shallowest level whose sampling matches the source pixel size; deeper oversamples."""
    for z in range(cap + 1):
        if geodetic.Resolution(z) <= pixel_deg:
            return z
    return cap


def _sample_tile(dem, bounds):
    """(GRID, GRID) float32 elevation over the tile bbox; flat 0 where no data."""
    west, south, east, north = bounds
    try:
        mem = gdal.Warp('', dem, format='MEM', outputBounds=(west, south, east, north),
                        width=GRID, height=GRID, resampleAlg='bilinear')
    except RuntimeError:
        return np.zeros((GRID, GRID), dtype=np.float32)
    if mem is None:
        return np.zeros((GRID, GRID), dtype=np.float32)
    band = mem.GetRasterBand(1)
    arr = band.ReadAsArray()
    if arr is None:
        return np.zeros((GRID, GRID), dtype=np.float32)
    arr = arr.astype(np.float32)
    nodata = band.GetNoDataValue()
    if nodata is not None:
        arr[arr == nodata] = 0.0
    return arr


def _grid_mesh(terrain, bounds):
    """Regular MESH_N x MESH_N mesh over the tile: positions (lon, lat, height) and
    triangle indices, wound so face normals point up."""
    west, south, east, north = bounds
    g = np.linspace(0, GRID - 1, MESH_N).round().astype(int)
    lon = west + (east - west) * (g / (GRID - 1))
    lat = north - (north - south) * (g / (GRID - 1))  # row 0 = north
    h = terrain[np.ix_(g, g)].astype(np.float64)
    lons = np.repeat(lon[None, :], MESH_N, axis=0)
    lats = np.repeat(lat[:, None], MESH_N, axis=1)
    positions = np.stack([lons.ravel(), lats.ravel(), h.ravel()], axis=1)

    idx = np.arange(MESH_N * MESH_N).reshape(MESH_N, MESH_N)
    v00, v01 = idx[:-1, :-1].ravel(), idx[:-1, 1:].ravel()
    v10, v11 = idx[1:, :-1].ravel(), idx[1:, 1:].ravel()
    tris = np.empty((v00.size * 2, 3), dtype=np.int64)
    tris[0::2] = np.stack([v00, v10, v11], axis=1)
    tris[1::2] = np.stack([v00, v11, v01], axis=1)
    return positions, tris


def _layer_json(output_dir, available, min_zoom, max_zoom, config):
    extensions = []
    if config.get('vertex_normals'):
        extensions.append('octvertexnormals')
    if config.get('water_path'):
        extensions.append('watermask')
    layer = {
        'tilejson': '2.1.0',
        'format': 'quantized-mesh-1.0',
        'scheme': 'tms',
        'tiles': ['{z}/{x}/{y}.terrain'],
        'projection': 'EPSG:4326',
        'bounds': [-180, -90, 180, 90],
        'available': available,
        'minzoom': min_zoom,
        'maxzoom': max_zoom,
    }
    if extensions:
        layer['extensions'] = extensions
    with open(os.path.join(output_dir, 'layer.json'), 'w') as f:
        json.dump(layer, f, separators=(',', ':'))


def build_terrain(dem_path, output_dir, config):
    os.makedirs(output_dir, exist_ok=True)
    dem = gdal.Open(dem_path)
    gt = dem.GetGeoTransform()
    pixel_deg = abs(gt[1])
    west = gt[0]
    east = gt[0] + gt[1] * dem.RasterXSize
    north = gt[3]
    south = gt[3] + gt[5] * dem.RasterYSize

    geodetic = GlobalGeodetic(True)
    min_zoom = int(config['min_zoom'])
    max_zoom = int(config['max_zoom']) if config.get('max_zoom') else _max_zoom(geodetic, pixel_deg)
    water_path = config.get('water_path')

    available = []
    for z in range(min_zoom, max_zoom + 1):
        if z <= FULL_COVER_LEVEL:
            # whole world: 2*2^z columns, 2^z rows (geographic, 2 tiles at level 0)
            x0, y0, x1, y1 = 0, 0, (1 << (z + 1)) - 1, (1 << z) - 1
        else:
            x0, y0 = geodetic.LonLatToTile(west, south, z)
            x1, y1 = geodetic.LonLatToTile(east, north, z)
        available.append([{'startX': x0, 'startY': y0, 'endX': x1, 'endY': y1}])
        for tx in range(x0, x1 + 1):
            for ty in range(y0, y1 + 1):
                bounds = geodetic.TileBounds(tx, ty, z)
                terrain = _sample_tile(dem, bounds)
                positions, triangles = _grid_mesh(terrain, bounds)
                mask = tile_water_mask(water_path, bounds) if water_path else None
                out = os.path.join(output_dir, str(z), str(tx))
                os.makedirs(out, exist_ok=True)
                encode_tile(os.path.join(out, f"{ty}.terrain"),
                            positions, triangles, bounds, config, water=mask)

    _layer_json(output_dir, available, min_zoom, max_zoom, config)
    return {
        'min_zoom': min_zoom,
        'max_zoom': max_zoom,
        'extent': [west, south, east, north],
    }
