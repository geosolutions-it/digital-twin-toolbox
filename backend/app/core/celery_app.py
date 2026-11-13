import os

from celery import Celery

from app.models.pipeline_types import PIPELINES

TASK_QUEUES = {spec.task: spec.queue for spec in PIPELINES.values()} | {
    "read_vector_fields": "vector",
    "read_vector_sample": "vector",
    "read_mesh_bbox": "mesh",
    "finalize_tileset_batch": "common",
}

# named after the module workers load (-A app.worker.main.celery), as before the move
celery = Celery("app.worker.main")
celery.conf.broker_url = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379")
celery.conf.result_backend = os.environ.get(
    "CELERY_RESULT_BACKEND", "redis://localhost:6379"
)

CELERY_VISIBILITY_TIMOUT = int(os.environ.get("CELERY_VISIBILITY_TIMOUT", 3600))
celery.conf.broker_transport_options = {"visibility_timeout": CELERY_VISIBILITY_TIMOUT}
celery.conf.result_backend_transport_options = {
    "visibility_timeout": CELERY_VISIBILITY_TIMOUT
}
celery.conf.visibility_timeout = CELERY_VISIBILITY_TIMOUT

celery.conf.task_routes = {
    name: {"queue": queue} for name, queue in TASK_QUEUES.items()
}
celery.conf.task_track_started = True
