import shutil

from app.worker.main import celery
from app.worker.common.utils import setup_output_directory
import app.worker.tasks.common.tiles3d  # noqa - registers finalize_tileset_batch


@celery.task(name="complete_pipeline_remove_process")
def complete_pipeline_remove_process(options):
    pipeline = options['pipeline']

    output_paths = setup_output_directory(pipeline['id'])
    try:
        shutil.rmtree(output_paths['output_path'])
    except Exception:
        pass

    return {}
