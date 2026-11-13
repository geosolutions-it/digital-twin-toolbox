import importlib

import pytest

from app.core.celery_app import TASK_QUEUES

# the task modules need the worker image packages
pytest.importorskip("numpy")

# queue -> the module its worker service loads with --include (docker-compose*.yml)
QUEUE_MODULES = {
    "vector": "app.worker.queues.vector",
    "point-cloud": "app.worker.queues.pointcloud",
    "mesh": "app.worker.queues.mesh",
    "common": "app.worker.queues.batch",
}


@pytest.mark.parametrize("queue", sorted(QUEUE_MODULES))
def test_queue_module_lists_exactly_its_queue_tasks(queue):
    module = importlib.import_module(QUEUE_MODULES[queue])
    expected = {name for name, q in TASK_QUEUES.items() if q == queue}
    assert {task.name for task in module.TASKS} == expected


def test_every_routed_task_has_a_queue_module():
    assert set(TASK_QUEUES.values()) == set(QUEUE_MODULES)
