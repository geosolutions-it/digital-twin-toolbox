import os
import shutil

from app.worker.main import celery, AssetDatabaseTask
from app.worker.common.utils import get_asset_upload_path, setup_output_directory
import app.worker.tasks.common.tiles3d  # noqa - registers finalize_tileset_batch


@celery.task(name="inspect_glb", base=AssetDatabaseTask)
def inspect_glb(options):
    return {
        'asset_type': None,
        'geometry_type': None,
        'payload': {'metadata': False, 'stats': False, 'sample': False, 'epsg': None, 'horizontal_epsg': None, 'vertical_epsg': None}
    }


@celery.task(name="complete_asset_remove_process")
def complete_asset_remove_process(options):
    asset = options['asset']

    try:
        upload_dir = os.path.dirname(get_asset_upload_path(f"{asset['id']}/index{asset['extension']}"))
        shutil.rmtree(upload_dir)
    except Exception:
        pass

    return {}


@celery.task(name="complete_pipeline_remove_process")
def complete_pipeline_remove_process(options):
    pipeline = options['pipeline']

    output_paths = setup_output_directory(pipeline['id'])
    try:
        shutil.rmtree(output_paths['output_path'])
    except Exception:
        pass

    return {}
