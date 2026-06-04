QUEUE = 'point-cloud'

CELERY_INCLUDES = [
    'app.worker.tasks.pointcloud.py3dtiles.task',
]
