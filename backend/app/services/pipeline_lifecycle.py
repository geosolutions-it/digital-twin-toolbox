"""Every change to a pipeline row's task state, made by the API or by the worker.

The row is the source of truth: a task may only update it while row.task_id is its own id.
"""

import os
import uuid

from celery.result import AsyncResult
from celery.states import FAILURE, PENDING, REVOKED, STARTED, SUCCESS
from sqlmodel import Session, delete, select, update

from app.core.celery_app import celery
from app.core.config import settings
from app.core.db import engine
from app.models.pipeline import (
    Pipeline,
    PipelineBatch,
    PipelineLog,
    PipelinesActionTypes,
)
from app.models.pipeline_types import (
    PIPELINES,
    pipeline_type_of,
    validate_pipeline_config,
)

# mirrors the frontend's isCeleryTaskInProgress
IN_PROGRESS = (PENDING, STARTED)
FINISHED = (SUCCESS, FAILURE, REVOKED)

ORPHAN_INSPECT_TIMEOUT = float(os.environ.get("ORPHAN_INSPECT_TIMEOUT", 2.0))


def _dispatch(pipeline: Pipeline, payload: dict) -> None:
    celery.send_task(
        PIPELINES[pipeline_type_of(pipeline.source)].task,
        kwargs={"pipeline_extended": payload},
        task_id=pipeline.task_id,
    )


def create_and_dispatch(
    session: Session,
    *,
    title: str,
    data: dict | None,
    source: dict,
    owner_id: uuid.UUID,
    batch_id: uuid.UUID | None = None,
) -> Pipeline:
    pipeline = Pipeline(
        title=title,
        data=data,
        task_id=str(uuid.uuid4()),
        task_status=PENDING,
        task_result=None,
        source=source,
        batch_id=batch_id,
        owner_id=owner_id,
    )
    session.add(pipeline)
    session.commit()
    session.refresh(pipeline)
    # row is PENDING before the task exists, so a fast failure is never overwritten
    _dispatch(pipeline, pipeline.model_dump())
    return pipeline


def revoke_running(pipeline: Pipeline) -> None:
    if pipeline.task_id and pipeline.task_status in IN_PROGRESS:
        try:
            AsyncResult(pipeline.task_id, app=celery).revoke(terminate=True)
        except Exception:
            # a revoked or deleted row rejects the task's claim and its result anyway
            pass


def _run(session: Session, pipeline: Pipeline) -> dict:
    if pipeline.task_status in IN_PROGRESS:
        return {}
    data = validate_pipeline_config(pipeline_type_of(pipeline.source), pipeline.data)
    applied = {
        "task_id": str(uuid.uuid4()),
        "task_status": PENDING,
        "task_result": None,
    }
    pipeline.sqlmodel_update(applied)
    session.add(pipeline)
    session.commit()
    session.refresh(pipeline)
    _dispatch(pipeline, {**pipeline.model_dump(), "data": data})
    return applied


def _cancel(session: Session, pipeline: Pipeline) -> dict:
    if not pipeline.task_id or pipeline.task_status not in IN_PROGRESS:
        return {}
    revoke_running(pipeline)
    applied = {"task_id": pipeline.task_id, "task_status": REVOKED, "task_result": None}
    pipeline.sqlmodel_update(applied)
    session.add(pipeline)
    session.commit()
    session.refresh(pipeline)
    return applied


def apply_action(
    session: Session, pipeline: Pipeline, action_type: PipelinesActionTypes
) -> dict:
    """Run or cancel; returns the fields applied, empty when the action did not apply.
    Raises ValueError for an invalid stored config."""
    if action_type == PipelinesActionTypes.run:
        return _run(session, pipeline)
    return _cancel(session, pipeline)


def queue_batch_finalize(output_prefix: str) -> None:
    celery.send_task(
        "finalize_tileset_batch",
        kwargs={"output_prefix": output_prefix, "base": settings.API_V1_STR},
    )


def maybe_finalize_batch(session: Session, pipeline: Pipeline) -> None:
    """When the last member of a batch finishes, stitch the combined tileset."""
    if not pipeline.batch_id:
        return
    batch = session.get(PipelineBatch, pipeline.batch_id)
    if batch is None or not batch.output_prefix:
        return
    statuses = session.exec(
        select(Pipeline.task_status).where(Pipeline.batch_id == batch.id)
    ).all()
    if all(status in FINISHED for status in statuses):
        queue_batch_finalize(batch.output_prefix)


def sync_lost_tasks(session: Session) -> None:
    """Mark rows whose task died without reporting back (OOM, time limit) from the result backend."""
    rows = session.exec(
        select(Pipeline).where(
            Pipeline.task_status.in_(IN_PROGRESS), Pipeline.task_id.is_not(None)
        )
    ).all()
    changed = []
    for pipeline in rows:
        try:
            state = AsyncResult(pipeline.task_id, app=celery).state
        except Exception:
            continue
        if state in (FAILURE, REVOKED):
            pipeline.sqlmodel_update({"task_status": state, "task_result": None})
            session.add(pipeline)
            changed.append(pipeline)
    if not changed:
        return
    session.commit()
    finalized = set()
    for pipeline in changed:
        if pipeline.batch_id and pipeline.batch_id not in finalized:
            finalized.add(pipeline.batch_id)
            maybe_finalize_batch(session, pipeline)


def owned_update(pipeline_id, task_id, values):
    """UPDATE the row only while it still belongs to task_id and was not cancelled (single atomic statement)."""
    return (
        update(Pipeline)
        .where(
            Pipeline.id == uuid.UUID(str(pipeline_id)),
            Pipeline.task_id == task_id,
            Pipeline.task_status.is_distinct_from(REVOKED),
        )
        .values(**values)
    )


def claim_row(pipeline_id, task_id) -> bool:
    """Mark the row STARTED and drop the previous run's log if this task still owns it. False when cancelled,
    replaced or deleted."""
    with Session(engine) as session:
        result = session.exec(
            owned_update(pipeline_id, task_id, {"task_status": STARTED})
        )
        claimed = result.rowcount == 1
        if claimed:
            session.exec(
                delete(PipelineLog).where(
                    PipelineLog.pipeline_id == uuid.UUID(str(pipeline_id))
                )
            )
        session.commit()
        return claimed


def write_result(pipeline_id, task_id, values, status=None) -> bool:
    """Store the outcome if this task still owns the row (and it is in `status` when given), then check batch completion."""
    statement = owned_update(pipeline_id, task_id, values)
    if status is not None:
        statement = statement.where(Pipeline.task_status == status)
    with Session(engine) as session:
        result = session.exec(statement)
        session.commit()
        if result.rowcount != 1:
            return False
        pipeline = session.get(Pipeline, uuid.UUID(str(pipeline_id)))
        if pipeline is not None:
            maybe_finalize_batch(session, pipeline)
        return True


def started_rows():
    with Session(engine) as session:
        return session.exec(
            select(Pipeline.id, Pipeline.task_id).where(
                Pipeline.task_status == STARTED, Pipeline.task_id.is_not(None)
            )
        ).all()


def active_task_ids():
    replies = celery.control.inspect(timeout=ORPHAN_INSPECT_TIMEOUT).active()
    if not replies:
        return None
    return {task["id"] for tasks in replies.values() for task in tasks or ()}


def fail_orphaned_rows() -> int:
    # rows read before the broadcast: a task that claims its row later is not in them
    rows = started_rows()
    if not rows:
        return 0
    active = active_task_ids()
    if active is None:
        return 0
    failed = 0
    for pipeline_id, task_id in rows:
        if task_id in active:
            continue
        if write_result(
            pipeline_id,
            task_id,
            {"task_status": FAILURE, "task_result": None},
            status=STARTED,
        ):
            failed += 1
    return failed
