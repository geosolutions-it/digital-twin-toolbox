from app.worker.main import celery


def run(pipeline_extended):
    return celery.send_task('create_obj_mesh_3dtiles', kwargs={'pipeline_extended': pipeline_extended})
