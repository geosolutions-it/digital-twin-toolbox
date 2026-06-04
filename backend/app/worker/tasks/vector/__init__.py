QUEUE = 'vector'

CELERY_INCLUDES = [
    'app.worker.tasks.vector.pg2b3dm.task',
    'app.worker.tasks.vector.i3dm.task',
]
