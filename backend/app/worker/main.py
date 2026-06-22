import os
import uuid
from sqlmodel import Session
from celery import Celery, Task
from app.core.db import engine
from app.models.task import Pipeline, Asset
from app.models.user_db import User  # noqa - registers user table for FK resolution
from app.worker.tasks import TASK_QUEUES
from celery.states import SUCCESS

celery = Celery(__name__)
celery.conf.broker_url = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379")
celery.conf.result_backend = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379")

CELERY_VISIBILITY_TIMOUT = int(os.environ.get("CELERY_VISIBILITY_TIMOUT", 3600))
celery.conf.broker_transport_options = {'visibility_timeout': CELERY_VISIBILITY_TIMOUT}
celery.conf.result_backend_transport_options = {'visibility_timeout': CELERY_VISIBILITY_TIMOUT}
celery.conf.visibility_timeout = CELERY_VISIBILITY_TIMOUT

celery.conf.task_routes = {name: {'queue': queue} for name, queue in TASK_QUEUES.items()}
celery.conf.task_track_started = True


class PipelineDatabaseTask(Task):
    abstract = True

    def after_return(self, status, retval, task_id, args, kwargs, einfo):
        with Session(engine) as session:
            pipeline_extended = kwargs.get('pipeline_extended')
            pipeline = session.get(Pipeline, pipeline_extended['id'])
            pipeline_in = {"task_id": task_id, "task_status": status}
            if status == SUCCESS:
                pipeline_in['task_result'] = retval
            pipeline.sqlmodel_update(pipeline_in)
            session.add(pipeline)
            session.commit()
            session.refresh(pipeline)


class AssetDatabaseTask(Task):
    abstract = True

    def after_return(self, status, retval, task_id, args, kwargs, einfo):
        with Session(engine) as session:
            options = kwargs.get('options')
            asset_obj = options['asset']
            asset_id = asset_obj['id']
            if isinstance(asset_id, str):
                asset_id = uuid.UUID(asset_id)
            asset = session.get(Asset, asset_id)
            if asset is None:
                return
            asset_in = {"upload_id": task_id, "upload_status": status}
            if status == SUCCESS:
                asset_in['asset_type'] = retval['asset_type']
                asset_in['geometry_type'] = retval['geometry_type']
                asset_in['upload_result'] = retval['payload']
            elif einfo is not None:
                asset_in['upload_result'] = {
                    'error': str(einfo.exception),
                    'traceback': einfo.traceback,
                }
            asset.sqlmodel_update(asset_in)
            session.add(asset)
            session.commit()
            session.refresh(asset)
