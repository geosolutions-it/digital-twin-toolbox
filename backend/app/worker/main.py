import os
import uuid
from sqlmodel import Session, select, update
from celery import Celery, Task
from celery.exceptions import Ignore
from app.core.db import engine
from app.core.config import settings
from app.models.task import Pipeline
from app.models.user import User  # noqa - registers user table for FK resolution
from app.worker.tasks import TASK_QUEUES
from celery.states import SUCCESS, FAILURE, REVOKED, STARTED

celery = Celery(__name__)
celery.conf.broker_url = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379")
celery.conf.result_backend = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379")

CELERY_VISIBILITY_TIMOUT = int(os.environ.get("CELERY_VISIBILITY_TIMOUT", 3600))
celery.conf.broker_transport_options = {'visibility_timeout': CELERY_VISIBILITY_TIMOUT}
celery.conf.result_backend_transport_options = {'visibility_timeout': CELERY_VISIBILITY_TIMOUT}
celery.conf.visibility_timeout = CELERY_VISIBILITY_TIMOUT

celery.conf.task_routes = {name: {'queue': queue} for name, queue in TASK_QUEUES.items()}
celery.conf.task_track_started = True


def _owned_update(pipeline_id, task_id, values):
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


def _claim_row(pipeline_id, task_id) -> bool:
    """Mark the row STARTED if this task still owns it. False when cancelled, replaced or deleted."""
    with Session(engine) as session:
        result = session.exec(_owned_update(pipeline_id, task_id, {"task_status": STARTED}))
        session.commit()
        return result.rowcount == 1


def _write_result(pipeline_id, task_id, values) -> None:
    """Store the outcome if this task still owns the row, then check batch completion."""
    with Session(engine) as session:
        result = session.exec(_owned_update(pipeline_id, task_id, values))
        session.commit()
        if result.rowcount != 1:
            return
        pipeline = session.get(Pipeline, uuid.UUID(str(pipeline_id)))
        if pipeline is not None:
            _maybe_finalize_batch(session, pipeline)


class PipelineDatabaseTask(Task):
    """The pipeline row is the source of truth: a task acts on it only while row.task_id is its own id."""
    abstract = True

    def __call__(self, *args, **kwargs):
        pipeline_extended = kwargs.get('pipeline_extended')
        if pipeline_extended is not None:
            # id read before super().__call__ (its request has none); Ignore skips run and after_return
            if not _claim_row(pipeline_extended['id'], self.request.id):
                raise Ignore()
        return super().__call__(*args, **kwargs)

    def after_return(self, status, retval, task_id, args, kwargs, einfo):
        pipeline_extended = kwargs.get('pipeline_extended')
        if pipeline_extended is None:
            return
        values = {"task_status": status}
        if status == SUCCESS:
            values['task_result'] = retval
        # a stale or cancelled run never overwrites the row
        _write_result(pipeline_extended['id'], task_id, values)


def _maybe_finalize_batch(session, pipeline):
    """When the last sibling of a batch reaches a terminal state, stitch the combined tileset."""
    if not pipeline.batch_id:
        return
    prefix = (pipeline.source or {}).get('batch_output_prefix')
    if not prefix:
        return
    siblings = session.exec(select(Pipeline).where(Pipeline.batch_id == pipeline.batch_id)).all()
    if not all(s.task_status in (SUCCESS, FAILURE, REVOKED) for s in siblings):
        return
    celery.send_task(
        'finalize_tileset_batch',
        kwargs={'output_prefix': prefix, 'base': settings.API_V1_STR},
    )
