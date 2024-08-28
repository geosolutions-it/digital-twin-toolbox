#!/usr/bin/env bash

# using nodemon to be able to detect changes in the mounted volumes
# the --legacy-watch is needed
# other python solutions were not working properly
nodemon -e py --legacy-watch --exec ./scripts/celery.sh
