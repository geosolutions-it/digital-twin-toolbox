QUEUE = 'cleanup'

CELERY_INCLUDES = [
    'app.worker.tasks.cleanup.task',
]
