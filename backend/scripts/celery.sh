#!/usr/bin/env bash

celery -A app.worker.main.celery worker --loglevel=info --concurrency=$CELERY_WORKER_CONCURRENCY
