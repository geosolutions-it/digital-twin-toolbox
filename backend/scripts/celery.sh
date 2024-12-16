#!/usr/bin/env bash

celery -A app.worker.main.celery worker --loglevel=info
