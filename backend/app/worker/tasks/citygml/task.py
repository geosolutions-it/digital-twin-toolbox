import os

import numpy as np

from app.core.celery_app import celery
from app.models.config import CityGMLConfig
from app.worker.lib.features.city import tile_city_objects
from app.worker.lib.geo.crs import (
    is_ellipsoidal,
    resolve_crs,
    wgs84_transformer,
)
from app.worker.runtime.logs import log_stage
from app.worker.runtime.task import PipelineDatabaseTask, TaskContext
from app.worker.tasks.citygml.reader import iter_city_objects

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
            crs, transformer = wgs84_transformer(
                crs, self.to_ellipsoidal, self.vertical_epsg
            )
            check = self.to_ellipsoidal and not is_ellipsoidal(crs)
            self.cache[srs_name] = [transformer, swap, check, crs.name]
        entry = self.cache[srs_name]
        transformer, swap, check, name = entry
        x, y = (pts[:, 1], pts[:, 0]) if swap else (pts[:, 0], pts[:, 1])
        lon, lat, h = transformer.transform(x, y, pts[:, 2])
        # PROJ silently keeps heights when it has no grid for the datum
        if check:
            if np.allclose(h, pts[:, 2], atol=1e-4):
                raise Exception(
                    f"No vertical transformation from {name} to ellipsoidal heights (missing PROJ grid?)"
                )
            entry[2] = False
        return np.column_stack([lon, lat, h])


@celery.task(name="create_citygml_3dtiles", base=PipelineDatabaseTask)
def create_citygml_3dtiles(pipeline_extended):
    with TaskContext(pipeline_extended, "City model", CityGMLConfig) as ctx:
        config = ctx.config
        key = ctx.source.key
        ext = os.path.splitext(key)[1].lower()
        log_stage("Downloading city model")
        local = ctx.download(
            key, "index" + (ext if ext in _INPUT_EXTENSIONS else ".gml")
        )
        orthophoto = None
        if config.orthophoto:
            log_stage("Downloading orthophoto")
            orthophoto = ctx.download(config.orthophoto, "orthophoto")
        project = Projector(
            config.horizontal_epsg, config.to_ellipsoidal_height, config.vertical_epsg
        )
        tiles_dir = ctx.path("tiles")
        log_stage("Reading and tiling city objects")
        tile_city_objects(
            iter_city_objects(local, config.lod),
            project,
            tiles_dir,
            config.max_tile_size_kb,
            orthophoto,
            config.texture_resolution,
        )
        return ctx.publish(tiles_dir, "tileset.json")
