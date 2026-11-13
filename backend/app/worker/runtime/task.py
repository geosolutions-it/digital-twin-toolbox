import logging
import time

from celery import Task
from celery.exceptions import Ignore, TaskPredicate
from celery.states import SUCCESS

from app.core.storage import output_key
from app.models.pipeline import PipelineSource
from app.services.pipeline_lifecycle import claim_row, write_result
from app.worker.runtime.logs import capture_pipeline_log

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
