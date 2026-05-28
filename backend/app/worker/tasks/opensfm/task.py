import os
import json
import shutil
import errno

from celery.exceptions import Reject
from app.worker.main import celery, PipelineDatabaseTask, AssetDatabaseTask
from app.worker.common.utils import get_asset_upload_path, setup_output_directory
import app.worker.tasks.opensfm.images_to_sparse_reconstruction as images_to_sparse_reconstruction
import app.worker.tasks.opensfm.sparse_reconstruction_to_dense_point_cloud as sparse_reconstruction_to_dense_point_cloud
import app.worker.tasks.opensfm.point_cloud_to_mesh as point_cloud_to_mesh
import app.worker.tasks.blender.mesh_tiling as mesh_tiling
import zipfile


@celery.task(name="inspect_photogrammetry", base=AssetDatabaseTask)
def inspect_photogrammetry(options):
    return {
        'asset_type': 'Photogrammetry',
        'geometry_type': None,
        'payload': {'metadata': False, 'stats': False, 'sample': False, 'epsg': None, 'horizontal_epsg': None, 'vertical_epsg': None}
    }


@celery.task(name="create_reconstructed_mesh", bind=True, base=PipelineDatabaseTask, acks_late=True, max_retries=1)
def create_reconstructed_mesh(self, pipeline_extended):
    try:
        return _run_reconstructed_mesh(pipeline_extended)
    except MemoryError as exc:
        raise Reject(exc, requeue=False)
    except OSError as exc:
        if exc.errno == errno.ENOMEM:
            raise Reject(exc, requeue=False)
    except Exception as exc:
        raise self.retry(exc, countdown=10)


def _run_reconstructed_mesh(pipeline_extended):
    asset = pipeline_extended.get('asset')
    asset_id = asset.get('id')
    pipeline_id = pipeline_extended.get('id')
    asset_extension = asset.get('extension')
    asset_file_path = get_asset_upload_path(f"{asset_id}/index{asset_extension}")

    output_paths = setup_output_directory(pipeline_id)

    pipeline_config = pipeline_extended.get('data') or {}

    default_config = {
        "stage": 'all',
        "force_delete": False,
        "feature_process_size": 2048,
        "depthmap_resolution": 2048,
        "auto_resolutions_computation": False,
        "processes": 1,
        "read_processes": 4,
        "depthmap_processes": 1,
        'texture_image_resolution': 4096,
        'texture_image_processes': 1,
    }

    config = {**default_config, **pipeline_config}
    stage = config.get('stage')
    process_dir = f"{output_paths['output_path']}/process"

    if stage == 'all' and config.get('force_delete'):
        shutil.rmtree(process_dir)

    if not os.path.exists(process_dir):
        images_dir = f"{process_dir}/images"
        os.makedirs(images_dir, exist_ok=True)
        with zipfile.ZipFile(asset_file_path, 'r') as zip_ref:
            zip_ref.extractall(images_dir)
        with open(os.path.join(images_dir, "asset_info.txt"), "w") as f:
            f.write(f"{asset.get('filename')}")

    if stage in ('all', 'images_to_sparse_reconstruction'):
        images_to_sparse_reconstruction.run(process_dir, {**config})

    if stage in ('all', 'sparse_reconstruction_to_dense_point_cloud'):
        sparse_reconstruction_to_dense_point_cloud.run(process_dir, {**config})

    if stage in ('all', 'point_cloud_to_mesh'):
        point_cloud_to_mesh.run(process_dir, {**config})

    if stage in ('all', 'mesh_to_3dtile'):
        os.makedirs(output_paths['output_path_3dtiles'], exist_ok=True)
        input_file = os.path.join(process_dir, 'textured', 'mesh.obj')
        reference_lla_path = os.path.join(process_dir, 'reference_lla.json')
        with open(reference_lla_path, 'r') as f:
            reference_lla = json.load(f)

        mesh_tiling.run({
            'input_file': input_file,
            'texture_image_size': 512,
            'tile_faces_target': 10000,
            'depth': 4,
            'output_dir': output_paths['output_path_3dtiles'],
            'latitude': reference_lla.get('latitude', 0),
            'longitude': reference_lla.get('longitude', 0),
            'altitude': reference_lla.get('altitude', 0),
            'max_geometric_error': 256,
            'apply_transform': True,
            'decimate_last_depth_level': True,
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
