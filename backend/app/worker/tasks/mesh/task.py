import json
import os
import shutil
import subprocess
import sys

from app.worker.main import celery, PipelineDatabaseTask, AssetDatabaseTask
from app.worker.common.utils import setup_output_directory, run_subprocess


@celery.task(name="inspect_mesh", base=AssetDatabaseTask)
def inspect_mesh(options):
    from app.worker.tasks.mesh.utils import (
        estimate_mesh_bbox_from_obj,
        resolve_mesh_input_file,
    )

    asset = options['asset']
    asset_id = asset['id']
    extension = asset['extension']

    input_file = resolve_mesh_input_file(asset_id, extension)
    if not os.path.isfile(input_file):
        raise FileNotFoundError(f"Mesh file not found: {input_file}")

    # OBJ bbox from a cheap vertex scan (no Blender). PLY is not sized at inspect time.
    mesh_bbox = None
    if input_file.lower().endswith(".obj"):
        mesh_bbox = estimate_mesh_bbox_from_obj(input_file)

    payload = {
        'metadata': False,
        'stats': False,
        'sample': False,
        'epsg': None,
        'horizontal_epsg': None,
        'vertical_epsg': None,
    }
    if mesh_bbox:
        payload['size'] = mesh_bbox['size']
        payload['offset'] = mesh_bbox['offset']

    return {
        'asset_type': 'Mesh',
        'geometry_type': None,
        'payload': payload,
    }


MESH_TILING_DEFAULTS = {
    'latitude': 0,
    'longitude': 0,
    'altitude': 0,
    'depth': 4,
    'tile_faces_target': 10000,
    'texture_image_size': 512,
    'max_geometric_error': 256,
    'decimate_last_depth_level': False,
    'forward_axis': 'Y',
    'up_axis': 'Z',
}


def _tile_obj_core(input_file, pipeline_id, config):
    """OBJ -> 3D Tiles: subprocess tiling, build tileset.json, zip. Generic over input_file."""
    output_paths = setup_output_directory(pipeline_id)
    tiles_dir = output_paths['output_path_3dtiles']
    os.makedirs(tiles_dir, exist_ok=True)

    tiling_params = {
        'input_file': input_file,
        'output_dir': tiles_dir,
        'latitude': config['latitude'],
        'longitude': config['longitude'],
        'altitude': config['altitude'],
        'depth': config['depth'],
        'tile_faces_target': config['tile_faces_target'],
        'texture_image_size': config['texture_image_size'],
        'apply_transform': True,
        'decimate_last_depth_level': config['decimate_last_depth_level'],
        'forward_axis': config['forward_axis'],
        'up_axis': config['up_axis'],
        'start_x': 0,
        'start_y': 0,
        'start_z': 0,
    }

    run_subprocess(
        [sys.executable, '-m', 'app.worker.tasks.mesh.run_tiling', json.dumps(tiling_params)],
        check=True,
    )

    from app.worker.tasks.mesh.finalize import finalize_mesh_3dtiles_output
    finalize_mesh_3dtiles_output(tiles_dir, config['depth'], config['max_geometric_error'])

    shutil.make_archive(output_paths['output_path_3dtiles_zip'], 'zip', tiles_dir)

    return {
        'output': output_paths['output_path'],
        'tileset': output_paths['output_tileset'],
        'download': output_paths['output_tileset_zip'],
    }


@celery.task(name="resolve_mesh_input")
def resolve_mesh_input(pipeline_extended):
    """Resolve the uploaded mesh asset to an OBJ path (extracts .obj.zip) and build the tile payload."""
    from app.worker.tasks.mesh.utils import resolve_mesh_input_file

    asset = pipeline_extended['asset']
    input_file = resolve_mesh_input_file(asset['id'], asset.get('extension', '.obj'))
    config = {**MESH_TILING_DEFAULTS, **(pipeline_extended.get('data') or {})}
    return {'pipeline_extended': pipeline_extended, 'input_file': input_file, 'config': config}


@celery.task(name="crop_obj")
def crop_obj(payload):
    """Generic mesh crop. Crops input_file to payload['bbox'] in place; no-op when bbox is absent."""
    from app.worker.tasks.mesh.mesh_tiling import crop_mesh
    crop_mesh(payload['input_file'], payload.get('bbox'))
    return payload


@celery.task(name="tile_obj_3dtiles", base=PipelineDatabaseTask)
def tile_obj_3dtiles(payload):
    """Generic terminal tiling step. Consumes {pipeline_extended, input_file, config} from the previous step."""
    return _tile_obj_core(
        payload['input_file'],
        payload['pipeline_extended']['id'],
        {**MESH_TILING_DEFAULTS, **payload['config']},
    )
