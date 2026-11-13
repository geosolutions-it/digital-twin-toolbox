"""Tasks of the "common" queue, consumed by every worker service."""

from app.worker.tasks.batch.task import finalize_tileset_batch

TASKS = (finalize_tileset_batch,)
