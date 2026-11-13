#!/usr/bin/env bash
set -e
bash /app/prestart.sh
# fastapi dev enables auto-reload; --host 0.0.0.0 so it is reachable from outside
# the container (same port 8000 as the production `fastapi run`).
# debugpy listens on 5678 for the VS Code "Attach to backend container" config and follows reloads.
exec python -m debugpy --listen 0.0.0.0:5678 -m fastapi dev --host 0.0.0.0 app/main.py
