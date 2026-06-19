QUEUE = 'photogrammetry'

CELERY_INCLUDES = [
    'app.worker.tasks.photogrammetry.task',
]
