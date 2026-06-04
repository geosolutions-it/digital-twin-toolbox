import os
import shutil

from app.worker.main import celery, PipelineDatabaseTask, AssetDatabaseTask
from app.worker.common.utils import get_asset_upload_path, setup_output_directory
import app.worker.tasks.mesh.mesh_tiling as mesh_tiling


@celery.task(name="inspect_glb", base=AssetDatabaseTask)
def inspect_glb(options):
    return {
        'asset_type': None,
        'geometry_type': None,
        'payload': {'metadata': False, 'stats': False, 'sample': False, 'epsg': None, 'horizontal_epsg': None, 'vertical_epsg': None}
    }


@celery.task(name="inspect_mesh", base=AssetDatabaseTask)
def inspect_mesh(options):
    return {
        'asset_type': 'Mesh',
        'geometry_type': None,
        'payload': {
            'metadata': False,
            'stats': False,
            'sample': False,
            'epsg': None,
            'horizontal_epsg': None,
            'vertical_epsg': None,
        }
    }


@celery.task(name="create_mesh_3dtiles", base=PipelineDatabaseTask)
def create_mesh_3dtiles(pipeline_extended):
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

    input_file = get_asset_upload_path(f"{asset_id}/index{asset_extension}")
    output_paths = setup_output_directory(pipeline_id)
    os.makedirs(output_paths['output_path_3dtiles'], exist_ok=True)

    mesh_tiling.run({
        'input_file': input_file,
        'output_dir': output_paths['output_path_3dtiles'],
        'latitude': config['latitude'],
        'longitude': config['longitude'],
        'altitude': config['altitude'],
        'depth': config['depth'],
        'tile_faces_target': config['tile_faces_target'],
        'texture_image_size': config['texture_image_size'],
        'max_geometric_error': config['max_geometric_error'],
        'apply_transform': True,
        'decimate_last_depth_level': config['decimate_last_depth_level'],
        'create_tileset_json': True,
        'start_x': 0,
        'start_y': 0,
        'start_z': 0,
    })

    shutil.make_archive(output_paths['output_path_3dtiles_zip'], 'zip', output_paths['output_path_3dtiles'])

    return {
        'output': output_paths['output_path'],
        'tileset': output_paths['output_tileset'],
        'download': output_paths['output_tileset_zip'],
    }
