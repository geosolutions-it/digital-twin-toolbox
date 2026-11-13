import logging
import os
import tempfile
import time

from celery import Task
from celery.exceptions import Ignore, TaskPredicate
from celery.states import SUCCESS

from app.core.storage import get_storage, output_key
from app.models.pipeline import PipelineSource
from app.services.pipeline_lifecycle import claim_row, write_result
from app.worker.runtime.logs import capture_pipeline_log
from app.worker.runtime.output import publish_tiles

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


def task_source(pipeline_extended: dict, label: str) -> PipelineSource:
    source = PipelineSource.model_validate(pipeline_extended.get("source") or {})
    if not source.key:
        raise Exception(f"{label} pipeline requires a bucket source")
    return source


def task_output_base(pipeline_extended: dict, source: PipelineSource) -> str:
    return source.output_base or output_key(pipeline_extended["id"])


class TaskContext:
    """One pipeline run: validated source and config, storage, output prefix and a scratch folder."""

    def __init__(self, pipeline_extended, label, config_class, storage=None):
        self.source = task_source(pipeline_extended, label)
        self.config = config_class(**(pipeline_extended.get("data") or {}))
        self.storage = storage or get_storage()
        self.out_base = task_output_base(pipeline_extended, self.source)
        self.scratch = None
        self._tmp = None

    def __enter__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.scratch = self._tmp.name
        return self

    def __exit__(self, *_exc):
        self._tmp.cleanup()
        return False

    def path(self, *parts):
        return os.path.join(self.scratch, *parts)

    def download(self, key, name):
        """Bucket key -> scratch/name; a name without extension takes the key's, lowercased."""
        if not os.path.splitext(name)[1]:
            name += os.path.splitext(key)[1].lower()
        dest = self.path(name)
        self.storage.download_file(key, dest)
        return dest

    def publish(self, tiles_dir, entry, artifacts=None):
        return publish_tiles(self.storage, tiles_dir, self.out_base, entry, artifacts)
