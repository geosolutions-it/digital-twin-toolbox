"""Bucket-first point instances: a point vector + uploaded model glbs -> 3D Tiles
1.1 with EXT_mesh_gpu_instancing. No PostGIS, no i3dm.export binary."""
import os
import shutil
import tempfile

import numpy as np

from app.core.config import settings
from app.core.storage import get_storage, output_key
from app.worker.common.expression import parse_expression
from app.worker.main import celery, PipelineDatabaseTask
from app.worker.tasks.vector.gltf.geo import LocalFrame
from app.worker.tasks.vector.gltf.writer import infer_schema
from app.worker.tasks.vector.instance import reader
from app.worker.tasks.vector.instance.tiler import build_instance_tileset


def _load_model(storage, name, config, scratch, cache):
    """Download a model glb from the bucket once and parse it; cached by name."""
    if name in cache:
        return cache[name]
    key = (config.get('models_prefix') or '') + name  # TODO: confirm model source (bucket vs asset store)
    dest = os.path.join(scratch, 'model_' + os.path.basename(name))
    storage.download_file(key, dest)
    mesh = reader.read_model_glb(dest)
    cache[name] = mesh
    return mesh


@celery.task(name="create_point_instance_3dtiles", base=PipelineDatabaseTask)
def create_point_instance_3dtiles(pipeline_extended):
    pipeline_id = pipeline_extended['id']
    source = pipeline_extended.get('source') or {}
    if not source.get('key'):
        raise Exception("Instance pipeline requires a bucket source")

    pipeline_config = pipeline_extended.get('data') or {}
    default_config = {
        'model': "model.glb",
        'models_prefix': '',
        'rotation': 0,
        'scale': 1,
        'translate_z': 0,
        'to_ellipsoidal_height': False,
        'max_features_per_tile': 25000,
        'max_geometric_error': 500,
    }
    config = {**default_config, **pipeline_config}

    storage = get_storage()
    out_base = source.get('output_base') or output_key(pipeline_id)

    with tempfile.TemporaryDirectory() as scratch:
        input_path = reader.resolve_input(source, storage, scratch)
        features, (lo, hi) = reader.read_points(input_path, bool(config['to_ellipsoidal_height']))
        if not features:
            raise Exception("No point features to tile")

        frame = LocalFrame((lo[0] + hi[0]) / 2.0, (lo[1] + hi[1]) / 2.0, (lo[2] + hi[2]) / 2.0)
        model_cache = {}
        records = []
        for feat in features:
            props = feat['properties']
            fe = {'type': 'Feature', 'properties': props, 'geometry': {'type': 'Point'}}
            model = parse_expression('string', config['model'], fe, default_config['model'])
            scale = parse_expression('number', config['scale'], fe, default_config['scale'])
            rotation = parse_expression('number', config['rotation'], fe, default_config['rotation'])
            translate_z = parse_expression('number', config['translate_z'], fe, default_config['translate_z'])

            _load_model(storage, model, config, scratch, model_cache)
            lon, lat, h = feat['lonlath']
            enu = frame.to_enu([[lon, lat, h + translate_z]])[0]
            records.append({'enu': enu, 'heading': rotation, 'scale': scale,
                            'model': model, 'properties': props})

        schema = infer_schema([r['properties'] for r in records])
        max_features = int(parse_expression('number', config['max_features_per_tile'], {}, default_config['max_features_per_tile']))
        max_ge = float(parse_expression('number', config['max_geometric_error'], {}, default_config['max_geometric_error']))

        tiles_dir = os.path.join(scratch, 'tiles')
        build_instance_tileset(records, tiles_dir, frame.transform(), model_cache, schema,
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
