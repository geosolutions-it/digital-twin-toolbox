from app.api.deps import CurrentUser, SessionDep
from fastapi import APIRouter, HTTPException
from typing import Any
from sqlmodel import func, select
import os
import uuid
from app.models.task import Pipeline, PipelinePublic, PipelinesPublic, PipelinePublicExtended, PipelineCreate, PipelineBatchCreate, Message, Asset, PipelinesActionTypes, PipelineUpdate

from app.worker.pipelines import run as run_pipeline
from app.worker.pipelines import pointcloud as _pc
from app.services.pipeline_config import validate_pipeline_config
from app.core.storage import get_storage
from app.worker.main import celery
from celery.result import AsyncResult
from celery.states import REVOKED, PENDING, SUCCESS, FAILURE, STARTED

router = APIRouter()

def _collect_task_ids(result):
    """All task ids in the chain (walks result.parent); one id for single-task pipelines."""
    ids = []
    node = result
    while node is not None:
        if getattr(node, 'id', None):
            ids.append(node.id)
        node = getattr(node, 'parent', None)
    return ids

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

_SOURCE_DISPATCH = {"PointCloud": _pc.run}
_SOURCE_EXTENSIONS = {"PointCloud": (".laz", ".las")}


@router.post("/batch", response_model=Any)
def create_pipeline_batch(
    *, session: SessionDep, current_user: CurrentUser, batch_in: PipelineBatchCreate
) -> Any:
    """
    Create and dispatch one pipeline per matching file under a bucket prefix.
    """
    dispatch = _SOURCE_DISPATCH.get(batch_in.pipeline)
    if dispatch is None:
        raise HTTPException(status_code=422, detail=f"Unsupported batch pipeline: {batch_in.pipeline}")

    try:
        data = validate_pipeline_config(batch_in.pipeline, None, batch_in.data)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"Invalid config: {e}")

    exts = _SOURCE_EXTENSIONS[batch_in.pipeline]
    keys = [k for k in get_storage().list(batch_in.prefix) if k.lower().endswith(exts)]
    if not keys:
        raise HTTPException(status_code=404, detail=f"No matching files under prefix {batch_in.prefix!r}")

    batch_id = uuid.uuid4()
    created = []
    for key in keys:
        name = os.path.basename(key)
        pipeline = Pipeline(
            title=f"{batch_in.title} / {name}" if batch_in.title else name,
            asset_id=None,
            data=data,
            task_id=None,
            task_status=None,
            task_result=None,
            source={"key": key, "extension": os.path.splitext(key)[1]},
            batch_id=batch_id,
            owner_id=current_user.id,
        )
        session.add(pipeline)
        session.commit()
        session.refresh(pipeline)

        task = dispatch(pipeline.model_dump())
        pipeline.sqlmodel_update({"task_id": task.id, "task_status": PENDING})
        session.add(pipeline)
        session.commit()
        created.append(str(pipeline.id))

    return {"batch_id": str(batch_id), "count": len(created), "pipeline_ids": created}


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
            pipeline_extended_dict['data'] = validate_pipeline_config(
                asset.geometry_type, asset.asset_type, pipeline_extended_dict.get('data')
            )
            task = run_pipeline(pipeline_extended_dict)
            task_ids = _collect_task_ids(task)
            pipeline_out = {
                "task_id": task.id,
                "task_status": PENDING,
                # store all chain ids so cancel can revoke the running step, not just the tail
                "task_result": {"task_ids": task_ids} if len(task_ids) > 1 else None,
            }
            pipeline.sqlmodel_update(pipeline_out)
            session.add(pipeline)
            session.commit()
            session.refresh(pipeline)

        if action_type == 'cancel' and pipeline.task_id and pipeline_extended.task_status in (PENDING, STARTED):
            # revoke every chain task (running one terminated); single id for non-chains
            task_ids = []
            if isinstance(pipeline.task_result, dict):
                task_ids = pipeline.task_result.get('task_ids') or []
            if not task_ids:
                task_ids = [pipeline.task_id]
            for tid in task_ids:
                AsyncResult(tid, app=celery).revoke(terminate=True)
            pipeline_out = {
                "task_id": pipeline.task_id,
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
    pipeline_extended = PipelinePublicExtended.model_validate(
        {**pipeline_in, "asset": asset},
        update={"owner_id": pipeline.owner_id},
    )

    if pipeline.task_id and pipeline.task_status == PENDING:
        async_result = AsyncResult(pipeline.task_id, app=celery)
        celery_status = async_result.state
        if celery_status in (STARTED, 'PROGRESS'):
            pipeline_extended = pipeline_extended.model_copy(
                update={'task_status': STARTED},
            )
        elif celery_status == SUCCESS and async_result.ready():
            result = async_result.result
            if isinstance(result, dict):
                pipeline_extended = pipeline_extended.model_copy(
                    update={'task_status': SUCCESS, 'task_result': result},
                )
        elif celery_status == FAILURE and async_result.ready():
            pipeline_extended = pipeline_extended.model_copy(
                update={'task_status': FAILURE},
            )

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
