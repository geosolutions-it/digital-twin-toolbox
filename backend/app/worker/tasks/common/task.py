import os
import shutil

from sqlmodel import Session, text
from app.core.db import engine_tasks
from app.worker.main import celery, AssetDatabaseTask
from app.worker.common.utils import (
    get_asset_upload_path, get_asset_table_name, get_pipeline_table_name, setup_output_directory
)


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
    table_name = get_asset_table_name(asset['id'])

    with Session(engine_tasks) as session:
        session.exec(text(f"DROP TABLE IF EXISTS {table_name};"))
        session.commit()

    try:
        upload_dir = os.path.dirname(get_asset_upload_path(f"{asset['id']}/index{asset['extension']}"))
        shutil.rmtree(upload_dir)
    except Exception:
        pass

    return {}


@celery.task(name="complete_pipeline_remove_process")
def complete_pipeline_remove_process(options):
    pipeline = options['pipeline']
    table_name = get_pipeline_table_name(pipeline['id'])

    with Session(engine_tasks) as session:
        session.exec(text(f"DROP TABLE IF EXISTS {table_name};"))
        session.commit()

    output_paths = setup_output_directory(pipeline['id'])
    try:
        shutil.rmtree(output_paths['output_path'])
    except Exception:
        pass

    return {}
