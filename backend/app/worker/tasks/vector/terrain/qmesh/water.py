"""Rasterize a supplied water layer to a per-tile mask for the quantized-mesh
water extension; None when no water source is set."""
import numpy as np
from osgeo import gdal

gdal.UseExceptions()

SIZE = 256


def tile_water_mask(water_path, bounds, size=SIZE):
    """(size, size) uint8, 255=water 0=land, or None."""
    if not water_path:
        return None
    west, south, east, north = bounds
    mem = gdal.Warp('', water_path, format='MEM', outputBounds=(west, south, east, north),
                    width=size, height=size)
    if mem is None:
        return None
    arr = mem.GetRasterBand(1).ReadAsArray()
    return (arr > 0).astype(np.uint8) * 255
