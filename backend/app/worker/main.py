import logging
import os
import re
import shutil
import tempfile
import threading

from celery.signals import worker_init, worker_ready

from app.core.celery_app import celery
from app.models.user import User
from app.services.pipeline_lifecycle import fail_orphaned_rows

# celery: workers load -A app.worker.main.celery; User: registers the user table for FK resolution
__all__ = ["User", "celery"]

logger = logging.getLogger(__name__)


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
