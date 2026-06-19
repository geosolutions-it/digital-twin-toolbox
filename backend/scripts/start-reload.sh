#!/usr/bin/env bash
set -e
bash /app/prestart.sh
# fastapi dev enables auto-reload; --host 0.0.0.0 so it is reachable from outside
# the container (same port 8000 as the production `fastapi run`).
fastapi dev --host 0.0.0.0 app/main.py
