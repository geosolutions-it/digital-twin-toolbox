#!/usr/bin/env bash
# Same checks as CI, with the ruff version locked in uv.lock

set -e
set -x

cd "$(dirname "$0")/.."
uv run --frozen --only-group dev ruff check app
uv run --frozen --only-group dev ruff format --check app
