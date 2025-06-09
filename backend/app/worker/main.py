import os
import time
from sqlmodel import Session
from app.core.db import engine

from celery import Celery, Task
from app.models import Pipeline, Asset
from celery.states import SUCCESS
import app.worker.tasks as tasks

celery = Celery(__name__)
celery.conf.broker_url = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379")
celery.conf.result_backend = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379")

class PipelineDatabaseTask(Task):
    abstract = True
    def after_return(self, status, retval, task_id, args, kwargs, einfo):
        with Session(engine) as session:
            pipeline_extended = kwargs.get('pipeline_extended')
            pipeline = session.get(Pipeline, pipeline_extended['id'])
            pipeline_in = {
                "task_id": task_id,
                "task_status": status
            }
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
            asset = session.get(Asset, asset_obj['id'])
            asset_in = {
                "upload_id": task_id,
                "upload_status": status
            }
            if status == SUCCESS:
                asset_in['asset_type'] = retval['asset_type']
                asset_in['geometry_type'] = retval['geometry_type']
                asset_in['upload_result'] = retval['payload']

            asset.sqlmodel_update(asset_in)
            session.add(asset)
            session.commit()
            session.refresh(asset)

@celery.task(name="create_point_instance_3dtiles", base=PipelineDatabaseTask)
def create_point_instance_3dtiles(pipeline_extended):
    return tasks.create_point_instance_3dtiles(pipeline_extended)

@celery.task(name="create_mesh_3dtiles", base=PipelineDatabaseTask)
def create_mesh_3dtiles(pipeline_extended):
    return tasks.create_mesh_3dtiles(pipeline_extended)

@celery.task(name="create_point_cloud_3dtiles", base=PipelineDatabaseTask)
def create_point_cloud_3dtiles(pipeline_extended):
    return tasks.create_point_cloud_3dtiles(pipeline_extended)

@celery.task(name="create_reconstructed_mesh", base=PipelineDatabaseTask)
def create_reconstructed_mesh(pipeline_extended):
    return tasks.create_reconstructed_mesh(pipeline_extended)

@celery.task(name="complete_upload_process", base=AssetDatabaseTask)
def complete_upload_process(options):
    return tasks.complete_upload_process(options)

@celery.task(name="complete_asset_remove_process")
def complete_asset_remove_process(options):
    return tasks.complete_asset_remove_process(options)

@celery.task(name="complete_pipeline_remove_process")
def complete_pipeline_remove_process(options):
    return tasks.complete_pipeline_remove_process(options)
