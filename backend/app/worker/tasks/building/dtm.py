import numpy as np
from osgeo import gdal, osr

gdal.UseExceptions()


def sink_to_dtm(objects, dtm_path, src_wkt, sink=0.3):
    """Roofer bases are flat, so downhill walls float; the DTM must share the point cloud's datum."""
    ds = gdal.Open(dtm_path)
    band = ds.GetRasterBand(1)
    nodata = band.GetNoDataValue()
    src = osr.SpatialReference()
    src.ImportFromWkt(src_wkt)
    dst = osr.SpatialReference()
    dst.ImportFromWkt(ds.GetProjection())
    for s in (src, dst):
        s.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    to_dtm = osr.CoordinateTransformation(src, dst)
    inv = gdal.InvGeoTransform(ds.GetGeoTransform())
    bases = []
    for _, _, polys in objects:
        rings = [r for poly in polys for r in poly]
        zmin = min(float(r[:, 2].min()) for r in rings)
        base = [r[:, 2] < zmin + 0.05 for r in rings]
        pts = np.array(
            to_dtm.TransformPoints(
                np.concatenate([r[m, :2] for r, m in zip(rings, base, strict=True)])
            )
        )
        col = np.floor(inv[0] + inv[1] * pts[:, 0] + inv[2] * pts[:, 1]).astype(int)
        row = np.floor(inv[3] + inv[4] * pts[:, 0] + inv[5] * pts[:, 1]).astype(int)
        bases.append((rings, base, zmin, col, row))
    if not bases:
        return
    # only the window under the buildings: a city-wide DTM does not fit in memory
    c0 = max(min(b[3].min() for b in bases), 0)
    r0 = max(min(b[4].min() for b in bases), 0)
    c1 = min(max(b[3].max() for b in bases) + 1, ds.RasterXSize)
    r1 = min(max(b[4].max() for b in bases) + 1, ds.RasterYSize)
    if c1 <= c0 or r1 <= r0:
        return
    data = band.ReadAsArray(int(c0), int(r0), int(c1 - c0), int(r1 - r0)).astype(
        np.float64
    )
    for rings, base, zmin, col, row in bases:
        inside = (col >= c0) & (col < c1) & (row >= r0) & (row < r1)
        z = data[row[inside] - r0, col[inside] - c0]
        keep = np.isfinite(z)
        if nodata is not None:
            keep &= z != nodata
        z = z[keep]
        if not len(z):
            continue
        ground = min(float(z.min()), zmin) - sink
        for r, m in zip(rings, base, strict=True):
            r[m, 2] = ground
