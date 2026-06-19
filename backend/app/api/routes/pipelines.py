from app.api.deps import CurrentUser, SessionDep
from fastapi import APIRouter, HTTPException
from typing import Any
from sqlmodel import func, select
import uuid
from app.models.task import Pipeline, PipelinePublic, PipelinesPublic, PipelinePublicExtended, PipelineCreate, Message, Asset, PipelinesActionTypes, PipelineUpdate

from app.worker.pipelines import run as run_pipeline
from app.worker.main import celery
from celery.result import AsyncResult
from celery.states import PENDING, REVOKED, STARTED

router = APIRouter()

@router.get("/", response_model=PipelinesPublic)
def read_pipelines(
    session: SessionDep, current_user: CurrentUser, skip: int = 0, limit: int = 100
) -> Any:
    """
    Retrieve pipelines.
    """
    if current_user.is_superuser:
        count_statement = select(func.count()).select_from(Pipeline)
        count = session.exec(count_statement).one()
        statement = select(Pipeline).offset(skip).limit(limit)
        pipelines = session.exec(statement.order_by(Pipeline.title.asc())).all()
    else:
        count_statement = (
            select(func.count())
            .select_from(Pipeline)
            .where(Pipeline.owner_id == current_user.id)
        )
        count = session.exec(count_statement).one()
        statement = (
            select(Pipeline)
            .where(Pipeline.owner_id == current_user.id)
            .offset(skip)
            .limit(limit)
        )
        pipelines = session.exec(statement.order_by(Pipeline.title.asc())).all()

    return PipelinesPublic(data=pipelines, count=count)

@router.post("/", response_model=PipelinePublic)
def create_pipeline(
    *, session: SessionDep, current_user: CurrentUser, pipeline_in: PipelineCreate
) -> Any:
    """
    Create new pipeline.
    """
    pipeline = Pipeline.model_validate(pipeline_in, update={"owner_id": current_user.id})
    session.add(pipeline)
    session.commit()
    session.refresh(pipeline)
    return pipeline

@router.post("/{id}/task/{action_type}", response_model=Any)
async def process_pipeline_task(
    *, session: SessionDep, current_user: CurrentUser, id: uuid.UUID, action_type: PipelinesActionTypes
) -> Any:
    """
    Run/cancel the pipeline task.
    """
    pipeline = session.get(Pipeline, id)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    if not current_user.is_superuser and (pipeline.owner_id != current_user.id):
        raise HTTPException(status_code=400, detail="Not enough permissions")
    asset = session.get(Asset, pipeline.asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="There is not asset associated with this pipeline")
    if not current_user.is_superuser and (asset.owner_id != current_user.id):
        raise HTTPException(status_code=400, detail="Not enough permissions for linked asset")
    pipeline_in = pipeline.model_dump()
    pipeline_extended = PipelinePublicExtended.model_validate({ **pipeline_in, 'asset': asset }, update={ "owner_id": pipeline.owner_id })

    pipeline_out = {}
    try:
        if action_type == 'run' and pipeline_extended.task_status not in (PENDING, STARTED):
            pipeline_extended_dict = pipeline_extended.model_dump()
            task = run_pipeline(pipeline_extended_dict)
            pipeline_out = {
                "task_id": task.id,
                "task_status": PENDING,
                "task_result": None,
            }
            pipeline.sqlmodel_update(pipeline_out)
            session.add(pipeline)
            session.commit()
            session.refresh(pipeline)

        if action_type == 'cancel' and pipeline.task_id and pipeline_extended.task_status in (PENDING, STARTED):
            task = AsyncResult(pipeline.task_id)
            task.revoke(terminate=True)
            pipeline_out = {
                "task_id": task.id,
                "task_status": REVOKED,
                "task_result": None
            }
            pipeline.sqlmodel_update(pipeline_out)
            session.add(pipeline)
            session.commit()
            session.refresh(pipeline)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"Unsupported asset for this pipeline: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail="It was not possible to initialize the requested task")
    return {
        **pipeline_out,
        'action_type': action_type
    }

@router.put("/{id}", response_model=PipelinePublic)
def update_pipeline(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    pipeline_in: PipelineUpdate,
) -> Any:
    """
    Update a pipeline.
    """
    pipeline = session.get(Pipeline, id)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    if not current_user.is_superuser and (pipeline.owner_id != current_user.id):
        raise HTTPException(status_code=400, detail="Not enough permissions")
    update_dict = pipeline_in.model_dump(exclude_unset=True)
    pipeline.sqlmodel_update(update_dict)
    session.add(pipeline)
    session.commit()
    session.refresh(pipeline)
    return pipeline

@router.get("/{id}", response_model=PipelinePublicExtended)
def read_pipeline(session: SessionDep, current_user: CurrentUser, id: uuid.UUID) -> Any:
    """
    Get pipeline by ID.
    """
    pipeline = session.get(Pipeline, id)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    if not current_user.is_superuser and (pipeline.owner_id != current_user.id):
        raise HTTPException(status_code=400, detail="Not enough permissions")
    asset = session.get(Asset, pipeline.asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="There is not asset associated with this pipeline")
    if not current_user.is_superuser and (asset.owner_id != current_user.id):
        raise HTTPException(status_code=400, detail="Not enough permissions for linked asset")
    pipeline_in = pipeline.model_dump()
    pipeline_extended = PipelinePublicExtended.model_validate({ **pipeline_in, 'asset': asset }, update={ "owner_id": pipeline.owner_id })
    return pipeline_extended

@router.delete("/{id}")
def delete_pipeline(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> Message:
    """
    Delete an pipeline.
    """
    pipeline = session.get(Pipeline, id)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    if not current_user.is_superuser and (pipeline.owner_id != current_user.id):
        raise HTTPException(status_code=400, detail="Not enough permissions")

    session.delete(pipeline)
    session.commit()

    celery.send_task('complete_pipeline_remove_process', args=[{'pipeline': pipeline.model_dump()}])

    return Message(message="Pipeline deleted successfully")
