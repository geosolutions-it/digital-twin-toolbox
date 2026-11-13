import logging
import os
import re
import shutil
import tempfile
import threading
import time

from celery import Task
from celery.exceptions import Ignore, TaskPredicate
from celery.signals import worker_init, worker_ready
from celery.states import SUCCESS

from app.core.celery_app import celery  # noqa: F401 - workers load -A app.worker.main.celery
from app.models.user import User  # noqa: F401 - registers user table for FK resolution
from app.services.pipeline_lifecycle import claim_row, fail_orphaned_rows, write_result
from app.worker.common.logs import capture_pipeline_log

logger = logging.getLogger(__name__)


def _duration(seconds):
    minutes, seconds = divmod(round(seconds), 60)
    return f"{minutes} min {seconds:02d} s" if minutes else f"{seconds} s"


class PipelineDatabaseTask(Task):
    """Claims the pipeline row before running and writes the outcome after; see services.pipeline_lifecycle."""

    abstract = True

    def __call__(self, *args, **kwargs):
        pipeline_extended = kwargs.get("pipeline_extended")
        if pipeline_extended is not None:
            # id read before super().__call__ (its request has none); Ignore skips run and after_return
            if not claim_row(pipeline_extended["id"], self.request.id):
                raise Ignore()
            with capture_pipeline_log(pipeline_extended["id"]):
                started = time.monotonic()
                logger.info("Started %s", self.name)
                try:
                    result = super().__call__(*args, **kwargs)
                except TaskPredicate:
                    raise
                except Exception:
                    # Celery logs the failure after this returns, outside the job log
                    logger.exception(
                        "Failed after %s", _duration(time.monotonic() - started)
                    )
                    raise
                logger.info("Finished in %s", _duration(time.monotonic() - started))
                return result
        return super().__call__(*args, **kwargs)

    def after_return(self, status, retval, task_id, args, kwargs, einfo):
        pipeline_extended = kwargs.get("pipeline_extended")
        if pipeline_extended is None:
            return
        values = {"task_status": status}
        if status == SUCCESS:
            values["task_result"] = retval
        # a stale or cancelled run never overwrites the row
        write_result(pipeline_extended["id"], task_id, values)


_SCRATCH_NAME = re.compile(r"^tmp[a-z0-9_]{8}$")


def _clear_scratch(root=None) -> list[str]:
    root = root or tempfile.gettempdir()
    removed = []
    for entry in os.scandir(root):
        if _SCRATCH_NAME.match(entry.name) and entry.is_dir(follow_symlinks=False):
            shutil.rmtree(entry.path, ignore_errors=True)
            removed.append(entry.name)
    return removed


@worker_init.connect
def _on_worker_init(**_kwargs):
    # before any task starts, so no live scratch folder is removed
    removed = _clear_scratch()
    if removed:
        logger.warning("Removed %d scratch folders left by killed runs", len(removed))


def _fail_orphaned_rows_logged():
    try:
        failed = fail_orphaned_rows()
    except Exception:
        logger.exception("Could not check for orphaned pipeline rows")
        return
    if failed:
        logger.warning("Marked %d pipelines FAILURE: their run was killed", failed)


@worker_ready.connect
def _on_worker_ready(**_kwargs):
    # in a thread: the broadcast needs this worker's own loop free to answer it
    threading.Thread(target=_fail_orphaned_rows_logged, daemon=True).start()
