#!/bin/sh -e
set -x

cd "$(dirname "$0")/.."
uv run --frozen --only-group dev ruff check app --fix
uv run --frozen --only-group dev ruff format app
