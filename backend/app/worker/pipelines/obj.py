from app.worker.main import celery


def run(pipeline_extended):
    return celery.send_task('tile_mesh', kwargs={'pipeline_extended': pipeline_extended})
