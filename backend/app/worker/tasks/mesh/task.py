import json
import os
import shutil
import subprocess
import sys

from app.worker.main import celery, PipelineDatabaseTask, AssetDatabaseTask
from app.worker.common.utils import setup_output_directory


@celery.task(name="inspect_mesh", base=AssetDatabaseTask)
def inspect_mesh(options):
    from app.worker.tasks.mesh.utils import (
        estimate_mesh_size_from_obj,
        resolve_mesh_input_file,
    )

    asset = options['asset']
    asset_id = asset['id']
    extension = asset['extension']

    input_file = resolve_mesh_input_file(asset_id, extension)
    if not os.path.isfile(input_file):
        raise FileNotFoundError(f"Mesh file not found: {input_file}")

    # OBJ size from a cheap vertex scan (no Blender). PLY is not sized at inspect time.
    mesh_size = None
    if input_file.lower().endswith(".obj"):
        mesh_size = estimate_mesh_size_from_obj(input_file)

    payload = {
        'metadata': False,
        'stats': False,
        'sample': False,
        'epsg': None,
        'horizontal_epsg': None,
        'vertical_epsg': None,
    }
    if mesh_size:
        payload['size'] = mesh_size

    return {
        'asset_type': 'Mesh',
        'geometry_type': None,
        'payload': payload,
    }


@celery.task(name="create_obj_mesh_3dtiles", base=PipelineDatabaseTask)
def create_obj_mesh_3dtiles(pipeline_extended):
    asset = pipeline_extended['asset']
    asset_id = asset['id']
    pipeline_id = pipeline_extended['id']
    asset_extension = asset.get('extension', '.obj')

    pipeline_config = pipeline_extended.get('data') or {}

    default_config = {
        'latitude': 0,
        'longitude': 0,
        'altitude': 0,
        'depth': 4,
        'tile_faces_target': 10000,
        'texture_image_size': 512,
        'max_geometric_error': 256,
        'decimate_last_depth_level': False,
    }

    config = {**default_config, **pipeline_config}

    from app.worker.tasks.mesh.utils import resolve_mesh_input_file

    input_file = resolve_mesh_input_file(asset_id, asset_extension)
    output_paths = setup_output_directory(pipeline_id)
    os.makedirs(output_paths['output_path_3dtiles'], exist_ok=True)

    tiles_dir = output_paths['output_path_3dtiles']

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
        'start_x': 0,
        'start_y': 0,
        'start_z': 0,
    }

    subprocess.run(
        [sys.executable, '-m', 'app.worker.tasks.mesh.run_tiling', json.dumps(tiling_params)],
        check=True,
    )

    from app.worker.tasks.mesh.finalize import finalize_mesh_3dtiles_output

    finalize_mesh_3dtiles_output(
        tiles_dir,
        config['depth'],
        config['max_geometric_error'],
    )

    shutil.make_archive(output_paths['output_path_3dtiles_zip'], 'zip', tiles_dir)

    return {
        'output': output_paths['output_path'],
        'tileset': output_paths['output_tileset'],
        'download': output_paths['output_tileset_zip'],
    }
