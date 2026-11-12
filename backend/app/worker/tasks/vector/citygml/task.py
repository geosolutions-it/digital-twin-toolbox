import os
import tempfile

import numpy as np

from app.core.storage import get_storage, output_key
from app.models.config import CityGMLConfig
from app.worker.common.geo import LocalFrame
from app.worker.common.output import publish_tiles
from app.worker.main import PipelineDatabaseTask, celery
from app.worker.tasks.vector.citygml.crs import (
    is_ellipsoidal,
    resolve_crs,
    wgs84_transformer,
)
from app.worker.tasks.vector.citygml.reader import iter_city_objects
from app.worker.tasks.vector.citygml.triangulate import triangulate
from app.worker.tasks.vector.ortho import OrthoTexturer
from app.worker.tasks.vector.polygon.tiler import build_tileset

_INPUT_EXTENSIONS = (".zip", ".gml", ".json", ".jsonl")


class Projector:

    def __init__(self, horizontal_epsg=None, to_ellipsoidal=False, vertical_epsg=None):
        self.horizontal_epsg = horizontal_epsg
        self.to_ellipsoidal = to_ellipsoidal
        self.vertical_epsg = vertical_epsg
        self.cache = {}

    def __call__(self, srs_name, pts):
        if srs_name not in self.cache:
            crs, swap = resolve_crs(srs_name, self.horizontal_epsg)
            crs, transformer = wgs84_transformer(crs, self.to_ellipsoidal, self.vertical_epsg)
            check = self.to_ellipsoidal and not is_ellipsoidal(crs)
            self.cache[srs_name] = [transformer, swap, check, crs.name]
        entry = self.cache[srs_name]
        transformer, swap, check, name = entry
        x, y = (pts[:, 1], pts[:, 0]) if swap else (pts[:, 0], pts[:, 1])
        lon, lat, h = transformer.transform(x, y, pts[:, 2])
        # PROJ silently keeps heights when it has no grid for the datum
        if check:
            if np.allclose(h, pts[:, 2], atol=1e-4):
                raise Exception(f"No vertical transformation from {name} to ellipsoidal heights (missing PROJ grid?)")
            entry[2] = False
        return np.column_stack([lon, lat, h])


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
        features.append({
            'mesh': np.concatenate(soups),
            'centroid': (xy.min(axis=0) + xy.max(axis=0)) / 2.0,
            'properties': props,
        })
    return features, frame


def tile_city_objects(objects, project, tiles_dir, max_tile_size_kb=400, orthophoto=None, texture_resolution=None):
    features, frame = _features(objects, project)
    if not features:
        raise Exception("No city object surfaces to tile")
    texturer = None
    if orthophoto:
        texturer = OrthoTexturer(orthophoto, frame, texture_resolution)
        colors = texturer.roof_colors([f['mesh'].reshape(-1, 3, 3) for f in features])
        for f, color in zip(features, colors, strict=True):
            f['properties']['roof_color'] = color
    build_tileset(features, tiles_dir, frame.transform(), max_tile_bytes=max_tile_size_kb * 1024,
                  texturer=texturer, max_leaf_extent=texturer.max_extent if texturer else None)
    return len(features)


@celery.task(name="create_citygml_3dtiles", base=PipelineDatabaseTask)
def create_citygml_3dtiles(pipeline_extended):
    pipeline_id = pipeline_extended['id']
    source = pipeline_extended.get('source') or {}
    key = source.get('key')
    if not key:
        raise Exception("City model pipeline requires a bucket source")
    config = CityGMLConfig(**(pipeline_extended.get('data') or {}))
    storage = get_storage()
    out_base = source.get('output_base') or output_key(pipeline_id)

    with tempfile.TemporaryDirectory() as scratch:
        ext = os.path.splitext(key)[1].lower()
        local = os.path.join(scratch, 'index' + (ext if ext in _INPUT_EXTENSIONS else '.gml'))
        storage.download_file(key, local)
        orthophoto = None
        if config.orthophoto:
            orthophoto = os.path.join(scratch, 'orthophoto' + os.path.splitext(config.orthophoto)[1].lower())
            storage.download_file(config.orthophoto, orthophoto)
        project = Projector(config.horizontal_epsg, config.to_ellipsoidal_height, config.vertical_epsg)
        tiles_dir = os.path.join(scratch, 'tiles')
        tile_city_objects(iter_city_objects(local, config.lod), project, tiles_dir, config.max_tile_size_kb,
                          orthophoto, config.texture_resolution)
        return publish_tiles(storage, tiles_dir, out_base, 'tileset.json')
