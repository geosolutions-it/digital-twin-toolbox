import logging
import os
import re
import shutil
import tempfile
import threading
import uuid
from sqlmodel import Session, select, update
from celery import Celery, Task
from celery.exceptions import Ignore
from celery.signals import worker_init, worker_ready
from app.core.db import engine
from app.core.config import settings
from app.models.task import Pipeline
from app.models.user import User  # noqa - registers user table for FK resolution
from app.worker.tasks import TASK_QUEUES
from celery.states import SUCCESS, FAILURE, REVOKED, STARTED

logger = logging.getLogger(__name__)

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


def _write_result(pipeline_id, task_id, values, status=None) -> bool:
    """Store the outcome if this task still owns the row (and it is in `status` when given), then check batch completion."""
    statement = _owned_update(pipeline_id, task_id, values)
    if status is not None:
        statement = statement.where(Pipeline.task_status == status)
    with Session(engine) as session:
        result = session.exec(statement)
        session.commit()
        if result.rowcount != 1:
            return False
        pipeline = session.get(Pipeline, uuid.UUID(str(pipeline_id)))
        if pipeline is not None:
            _maybe_finalize_batch(session, pipeline)
        return True


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


_SCRATCH_NAME = re.compile(r"^tmp[a-z0-9_]{8}$")
ORPHAN_INSPECT_TIMEOUT = float(os.environ.get("ORPHAN_INSPECT_TIMEOUT", 2.0))


def _clear_scratch(root=None) -> list[str]:
    root = root or tempfile.gettempdir()
    removed = []
    for entry in os.scandir(root):
        if _SCRATCH_NAME.match(entry.name) and entry.is_dir(follow_symlinks=False):
            shutil.rmtree(entry.path, ignore_errors=True)
            removed.append(entry.name)
    return removed


def _started_rows():
    with Session(engine) as session:
        return session.exec(
            select(Pipeline.id, Pipeline.task_id).where(Pipeline.task_status == STARTED, Pipeline.task_id.is_not(None))
        ).all()


def _active_task_ids():
    replies = celery.control.inspect(timeout=ORPHAN_INSPECT_TIMEOUT).active()
    if not replies:
        return None
    return {task["id"] for tasks in replies.values() for task in tasks or ()}


def _fail_orphaned_rows() -> int:
    # rows read before the broadcast: a task that claims its row later is not in them
    rows = _started_rows()
    if not rows:
        return 0
    active = _active_task_ids()
    if active is None:
        return 0
    failed = 0
    for pipeline_id, task_id in rows:
        if task_id in active:
            continue
        if _write_result(pipeline_id, task_id, {"task_status": FAILURE, "task_result": None}, status=STARTED):
            failed += 1
    return failed


@worker_init.connect
def _on_worker_init(**_kwargs):
    # before any task starts, so no live scratch folder is removed
    removed = _clear_scratch()
    if removed:
        logger.warning("Removed %d scratch folders left by killed runs", len(removed))


def _fail_orphaned_rows_logged():
    try:
        failed = _fail_orphaned_rows()
    except Exception:
        logger.exception("Could not check for orphaned pipeline rows")
        return
    if failed:
        logger.warning("Marked %d pipelines FAILURE: their run was killed", failed)


@worker_ready.connect
def _on_worker_ready(**_kwargs):
    # in a thread: the broadcast needs this worker's own loop free to answer it
    threading.Thread(target=_fail_orphaned_rows_logged, daemon=True).start()
