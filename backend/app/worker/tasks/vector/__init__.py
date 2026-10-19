QUEUE = 'vector'

CELERY_INCLUDES = [
    'app.worker.tasks.vector.polygon.task',
    'app.worker.tasks.vector.i3dm.task',
]
