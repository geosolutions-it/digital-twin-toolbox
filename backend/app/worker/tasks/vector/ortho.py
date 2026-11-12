"""An orthographic projection at the frame origin matches ENU east/north within cm over a city,
so a roof vertex's UV is its east/north and survives the tiler's vertex clustering."""
import io

import numpy as np
from osgeo import gdal
from PIL import Image, ImageDraw

gdal.UseExceptions()

# white: 3D Tiles styles multiply it
WALL_RGB = (255, 255, 255)
_STRIP = 8  # wall colour column, wide enough for mipmaps
_ROOF_MIN_NZ = 0.25
_WEBP_QUALITY = 80


def _grow(mask, r):
    """Binary dilation by a (2r+1)^2 square, separable; Pillow's MaxFilter is far slower."""
    out = mask.copy()
    for axis in (0, 1):
        src = out.copy()
        for d in range(1, r + 1):
            lo = [slice(None)] * 2
            hi = [slice(None)] * 2
            lo[axis], hi[axis] = slice(d, None), slice(None, -d)
            out[tuple(lo)] |= src[tuple(hi)]
            out[tuple(hi)] |= src[tuple(lo)]
    return out


def roof_mask(tris):
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    length = np.linalg.norm(n, axis=1)
    return n[:, 2] > _ROOF_MIN_NZ * np.maximum(length, 1e-12)


class OrthoTexturer:
    def __init__(self, path, frame, resolution=None, max_px=4096, wall_rgb=WALL_RGB):
        self.src = gdal.Open(path)
        if self.src.RasterCount < 3:
            raise Exception("The orthophoto needs 3 bands (RGB)")
        if not self.src.GetProjection():
            raise Exception("The orthophoto has no CRS")
        self.dst_srs = (f"+proj=ortho +lat_0={frame.origin_lat} +lon_0={frame.origin_lon} "
                        "+x_0=0 +y_0=0 +ellps=WGS84 +units=m +no_defs")
        self.resolution = resolution or self._native_resolution()
        self.max_px = max_px
        self.wall_rgb = np.array(wall_rgb, dtype=np.uint8)
        self.max_extent = (max_px - _STRIP - 4) * self.resolution
        self.ranges = None
        if self.src.GetRasterBand(1).DataType != gdal.GDT_Byte:
            # one stretch for the whole raster keeps colours consistent across tiles
            self.ranges = [self.src.GetRasterBand(b).ComputeRasterMinMax(True) for b in (1, 2, 3)]

    def _native_resolution(self):
        # measured in the local frame, so geographic rasters work too
        ds = gdal.Warp("", self.src, format="VRT", dstSRS=self.dst_srs)
        return float(abs(ds.GetGeoTransform()[1]))

    def _read(self, x0, y0, x1, y1, width, height):
        ds = gdal.Warp("", self.src, format="MEM", dstSRS=self.dst_srs, outputBounds=(x0, y0, x1, y1),
                       width=width, height=height, resampleAlg="average")
        rgb = np.moveaxis(ds.ReadAsArray()[:3], 0, -1)
        if self.ranges is None:
            return rgb
        lo = np.array([r[0] for r in self.ranges])
        span = np.maximum(np.array([r[1] for r in self.ranges]) - lo, 1e-9)
        return np.clip((rgb - lo) / span * 255.0, 0, 255).astype(np.uint8)

    def classify(self, tris):
        return roof_mask(tris)

    def _grid(self, xy, detail):
        """-> (x0, y0, x1, y1, metres per pixel) of the roofs' texture."""
        res = max(self.resolution, detail / 4.0)
        x0, y0 = xy.reshape(-1, 2).min(axis=0) - res
        x1, y1 = xy.reshape(-1, 2).max(axis=0) + res
        return x0, y0, x1, y1, max(res, (x1 - x0) / self.max_px, (y1 - y0) / self.max_px)

    def texel(self, tris, detail=0.0):
        """Metres per pixel __call__ would use; None without roofs."""
        roof = roof_mask(tris)
        return self._grid(tris[roof][:, :, :2], detail)[4] if roof.any() else None

    def __call__(self, tris, detail=0.0):
        roof = roof_mask(tris)
        if not roof.any():
            return None
        xy = tris[roof][:, :, :2]
        x0, y0, x1, y1, res = self._grid(xy, detail)
        width, height = max(int(np.ceil((x1 - x0) / res)), 1), max(int(np.ceil((y1 - y0) / res)), 1)
        x1, y1 = x0 + width * res, y0 + height * res
        rgb = self._read(x0, y0, x1, y1, width, height)

        # grown 2 px so linear filtering never samples the flat colour
        mask = Image.new("L", (width, height), 0)
        draw = ImageDraw.Draw(mask)
        px = np.empty_like(xy)
        px[..., 0] = (xy[..., 0] - x0) / res
        px[..., 1] = (y1 - xy[..., 1]) / res
        for t in px:
            draw.polygon([tuple(p) for p in t], fill=255)
        keep = _grow(np.asarray(mask) > 0, 2)

        image = np.empty((height, width + _STRIP, 3), dtype=np.uint8)
        image[:] = self.wall_rgb
        image[:, :width][keep] = rgb[keep]
        buf = io.BytesIO()
        Image.fromarray(image).save(buf, "WEBP", quality=_WEBP_QUALITY)

        uv = np.empty((len(tris), 3, 2))
        uv[:] = ((width + _STRIP / 2) / (width + _STRIP), 0.5)
        uv[roof, :, 0] = (xy[..., 0] - x0) / res / (width + _STRIP)
        uv[roof, :, 1] = (y1 - xy[..., 1]) / res / height
        return uv.reshape(-1, 2), buf.getvalue()

    def roof_colors(self, meshes, resolution=0.5, max_px=6000):
        """One orthophoto read for all roofs, coarsened to stay under max_px a side."""
        roofs = [m[roof_mask(m)][:, :, :2] for m in meshes]
        pts = [r.reshape(-1, 2) for r in roofs if len(r)]
        if not pts:
            return [None] * len(meshes)
        x0, y0 = np.min([p.min(axis=0) for p in pts], axis=0)
        x1, y1 = np.max([p.max(axis=0) for p in pts], axis=0)
        res = max(resolution, self.resolution, (x1 - x0) / max_px, (y1 - y0) / max_px)
        width, height = max(int(np.ceil((x1 - x0) / res)), 1), max(int(np.ceil((y1 - y0) / res)), 1)
        top = y0 + height * res
        rgb = self._read(x0, y0, x0 + width * res, top, width, height)

        colors = []
        for xy in roofs:
            if not len(xy):
                colors.append(None)
                continue
            px = np.empty_like(xy)
            px[..., 0] = (xy[..., 0] - x0) / res
            px[..., 1] = (top - xy[..., 1]) / res
            c0, r0 = np.floor(px.reshape(-1, 2).min(axis=0)).astype(int)
            c1, r1 = np.ceil(px.reshape(-1, 2).max(axis=0)).astype(int)
            mask = Image.new("L", (max(c1 - c0, 1), max(r1 - r0, 1)), 0)
            draw = ImageDraw.Draw(mask)
            for t in px:
                draw.polygon([(c - c0, r - r0) for c, r in t], fill=255)
            window = rgb[r0:r0 + mask.height, c0:c0 + mask.width]
            pixels = window[np.asarray(mask)[:window.shape[0], :window.shape[1]] > 0]
            if not len(pixels):
                c, r = np.clip(px.reshape(-1, 2).mean(axis=0).astype(int), 0, [width - 1, height - 1])
                pixels = rgb[r:r + 1, c:c + 1].reshape(-1, 3)
            pixels = pixels[pixels.sum(axis=1) > 0]  # outside the raster reads black
            if not len(pixels):
                colors.append(None)
                continue
            r, g, b = np.median(pixels, axis=0).astype(int)
            colors.append(f"#{r:02x}{g:02x}{b:02x}")
        return colors
