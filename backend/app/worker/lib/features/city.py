"""City objects (srs name, properties, polygons of rings) -> feature meshes -> 3D Tiles."""

import numpy as np

from app.worker.lib.features.ortho import OrthoTexturer
from app.worker.lib.features.tiler import build_tileset
from app.worker.lib.features.triangulate import triangulate
from app.worker.lib.geo.frame import LocalFrame


def _features(objects, project):
    frame = None
    features = []
    for srs_name, props, polys in objects:
        rings = [r for poly in polys for r in poly]
        lonlath = project(srs_name, np.concatenate(rings))
        if frame is None:
            frame = LocalFrame(*lonlath.mean(axis=0))
        enu = frame.to_enu(lonlath)
        parts = iter(np.split(enu, np.cumsum([len(r) for r in rings])[:-1]))
        soups = [triangulate([next(parts) for _ in poly]) for poly in polys]
        soups = [s for s in soups if s is not None]
        if not soups:
            continue
        xy = enu[:, :2]
        features.append(
            {
                "mesh": np.concatenate(soups),
                "centroid": (xy.min(axis=0) + xy.max(axis=0)) / 2.0,
                "properties": props,
            }
        )
    return features, frame


def tile_city_objects(
    objects,
    project,
    tiles_dir,
    max_tile_size_kb=400,
    orthophoto=None,
    texture_resolution=None,
):
    features, frame = _features(objects, project)
    if not features:
        raise Exception("No city object surfaces to tile")
    texturer = None
    if orthophoto:
        texturer = OrthoTexturer(orthophoto, frame, texture_resolution)
        colors = texturer.roof_colors([f["mesh"].reshape(-1, 3, 3) for f in features])
        for f, color in zip(features, colors, strict=True):
            f["properties"]["roof_color"] = color
    build_tileset(
        features,
        tiles_dir,
        frame.transform(),
        max_tile_bytes=max_tile_size_kb * 1024,
        texturer=texturer,
        max_leaf_extent=texturer.max_extent if texturer else None,
    )
    return len(features)
