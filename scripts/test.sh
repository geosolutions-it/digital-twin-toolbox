#! /usr/bin/env sh
set -e

COMPOSE="docker compose -p dtt-test -f docker-compose.yml -f docker-compose.test.yml"

docker network create traefik-public 2>/dev/null || true

trap '$COMPOSE down -v --remove-orphans' EXIT

$COMPOSE build backend worker-vector

$COMPOSE run --rm backend bash /app/tests-start.sh app/tests --ignore=app/tests/worker "$@"

$COMPOSE run --rm --no-deps worker-vector "bash /app/test.sh app/tests --ignore=app/tests/api $*"
