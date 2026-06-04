from app.worker.main import celery


def run(pipeline_extended):
    return celery.send_task('create_polygon_3dtiles', kwargs={'pipeline_extended': pipeline_extended})
