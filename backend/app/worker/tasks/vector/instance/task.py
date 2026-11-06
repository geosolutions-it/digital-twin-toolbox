"""Bucket-first point instances: a point vector + uploaded model glbs -> 3D Tiles
1.1 with EXT_mesh_gpu_instancing. No PostGIS, no i3dm.export binary."""
import os
import tempfile

from app.core.storage import get_storage, output_key
from app.worker.common.expression import parse_expression
from app.worker.main import celery, PipelineDatabaseTask
from app.worker.common.geo import LocalFrame
from app.worker.common.gltf import infer_schema
from app.worker.tasks.vector.instance import reader
from app.worker.tasks.vector.instance.tiler import build_instance_tileset
from app.worker.tasks.vector.source import resolve_input
from app.worker.common.output import publish_tiles


def _load_model(storage, name, config, scratch, cache):
    """Download a model glb from the bucket once and parse it; cached by name, None if missing."""
    if name in cache:
        return cache[name]
    key = (config.get('models_prefix') or '') + str(name)
    if not storage.exists(key):
        return None
    dest = os.path.join(scratch, 'model_' + os.path.basename(str(name)))
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
        'elevation': None,
        'to_ellipsoidal_height': False,
        'max_tile_size_kb': 1024,
        'max_geometric_error': 500,
    }
    config = {**default_config, **pipeline_config}

    storage = get_storage()
    out_base = source.get('output_base') or output_key(pipeline_id)

    with tempfile.TemporaryDirectory() as scratch:
        input_path = resolve_input(source, storage, scratch)
        features, (lo, hi) = reader.read_points(input_path, bool(config['to_ellipsoidal_height']))
        if not features:
            raise Exception("No point features to tile")

        frame = LocalFrame.from_bounds(lo, hi)
        model_cache = {}
        records = []
        for feat in features:
            props = feat['properties']
            fe = {'type': 'Feature', 'properties': props,
                  'geometry': {'type': 'Point', 'coordinates': list(feat['lonlath'])}}
            model = parse_expression('string', config['model'], fe, default_config['model'])
            scale = parse_expression('number', config['scale'], fe, default_config['scale'])
            rotation = parse_expression('number', config['rotation'], fe, default_config['rotation'])
            elevation = parse_expression('number', config['elevation'], fe, default_config['elevation'])

            if not model or _load_model(storage, model, config, scratch, model_cache) is None:
                continue
            if scale is None:
                scale = default_config['scale']
            if rotation is None:
                rotation = default_config['rotation']
            lon, lat, h = feat['lonlath']
            enu = frame.to_enu([[lon, lat, h if elevation is None else elevation]])[0]
            records.append({'enu': enu, 'heading': rotation, 'scale': scale,
                            'model': model, 'properties': props})

        if not records:
            raise Exception("No features with a valid model to tile")
        schema = infer_schema([r['properties'] for r in records])
        max_kb = float(parse_expression('number', config['max_tile_size_kb'], {}, default_config['max_tile_size_kb']))
        max_ge = float(parse_expression('number', config['max_geometric_error'], {}, default_config['max_geometric_error']))

        tiles_dir = os.path.join(scratch, 'tiles')
        build_instance_tileset(records, tiles_dir, frame.transform(), model_cache, schema,
                               max_tile_bytes=max_kb * 1024, max_geometric_error=max_ge)

        return publish_tiles(storage, tiles_dir, out_base, 'tileset.json')
