#! /usr/bin/env bash
set -e
set -x

python /app/app/tests_pre_start.py
alembic upgrade head

bash ./test.sh "$@"
