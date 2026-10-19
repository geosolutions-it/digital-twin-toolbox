"""Bucket-first terrain: a .tif or .vrt -> quantized-mesh pyramid uploaded as a
Cesium terrain layer. No external binary, no PostGIS."""
import os
import shutil
import tempfile

from app.core.config import settings
from app.core.storage import get_storage, output_key
from app.worker.main import celery, PipelineDatabaseTask
from app.worker.tasks.vector.terrain import preprocess
from app.worker.tasks.vector.terrain.qmesh.tiler import build_terrain


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

        zip_base = os.path.join(scratch, 'download')
        shutil.make_archive(zip_base, 'zip', tiles_dir)

        storage.delete_prefix(f"{out_base}/tiles")
        storage.upload_dir(tiles_dir, f"{out_base}/tiles")
        storage.upload_file(zip_base + '.zip', f"{out_base}/download.zip")

    base = settings.API_V1_STR
    return {
        'output': out_base,
        'tileset': f"{base}/{out_base}/tiles/layer.json",
        'download': f"{base}/{out_base}/download.zip",
        **info,
    }
