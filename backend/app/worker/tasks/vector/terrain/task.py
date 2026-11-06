"""Bucket-first terrain: a .tif or .vrt -> quantized-mesh pyramid uploaded as a
Cesium terrain layer. No external binary, no PostGIS."""
import os
import tempfile

from app.core.storage import get_storage, output_key
from app.worker.main import celery, PipelineDatabaseTask
from app.worker.tasks.vector.terrain import preprocess
from app.worker.tasks.vector.terrain.qmesh.tiler import build_terrain
from app.worker.tasks.vector.output import publish_tiles


@celery.task(name="create_terrain_tiles", base=PipelineDatabaseTask)
def create_terrain_tiles(pipeline_extended):
    pipeline_id = pipeline_extended['id']
    source = pipeline_extended.get('source') or {}
    if not source.get('key'):
        raise Exception("Terrain pipeline requires a bucket source")

    pipeline_config = pipeline_extended.get('data') or {}
    default_config = {
        'to_ellipsoidal_height': False,
        'source_vertical_epsg': 3855,
        'min_zoom': 0,
        'max_zoom': None,
        'vertex_normals': True,
        'water_key': None,
    }
    config = {**default_config, **pipeline_config}

    storage = get_storage()
    out_base = source.get('output_base') or output_key(pipeline_id)

    with tempfile.TemporaryDirectory() as scratch:
        src = preprocess.resolve_input(source, storage, scratch)
        dem = preprocess.warp_to_wgs84(
            src, scratch, bool(config['to_ellipsoidal_height']),
            int(config['source_vertical_epsg']))

        if config.get('water_key'):
            water = os.path.join(scratch, 'water' + os.path.splitext(config['water_key'])[1])
            storage.download_file(config['water_key'], water)
            config['water_path'] = water

        tiles_dir = os.path.join(scratch, 'tiles')
        info = build_terrain(dem, tiles_dir, config)

        result = publish_tiles(storage, tiles_dir, out_base, 'layer.json')

    return {**result, **info}
