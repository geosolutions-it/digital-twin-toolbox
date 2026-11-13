import importlib

import pytest

from app.core.celery_app import TASK_QUEUES, celery

# the modules each worker service loads with --include (docker-compose*.yml)
WORKER_INCLUDES = {
    "vector": "app.worker.tasks.vector.task",
    "point-cloud": "app.worker.tasks.pointcloud.task",
    "mesh": "app.worker.tasks.mesh.task",
    "common": "app.worker.tasks.common.task",
}


@pytest.mark.parametrize("queue", sorted(WORKER_INCLUDES))
def test_worker_include_registers_its_queue_tasks(queue):
    importlib.import_module(WORKER_INCLUDES[queue])
    expected = {name for name, q in TASK_QUEUES.items() if q == queue}
    assert expected <= set(celery.tasks)
