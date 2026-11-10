#!/usr/bin/env bash
# Runs inside a test image, arguments go to pytest (paths, --ignore, -k ...)

set -e
set -x

coverage run --source=app -m pytest "$@"
coverage report --show-missing
