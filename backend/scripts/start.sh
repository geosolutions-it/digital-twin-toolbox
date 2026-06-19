#!/usr/bin/env bash
set -e
bash /app/prestart.sh
fastapi run --workers 4 app/main.py
