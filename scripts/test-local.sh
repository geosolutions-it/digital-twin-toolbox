#! /usr/bin/env bash

# Exit in case of error
set -e

docker compose down -v --remove-orphans # Remove possibly previous broken stacks left hanging after an error

if [ $(uname -s) = "Linux" ]; then
    echo "Remove __pycache__ files"
    sudo find . -type d -name __pycache__ -exec rm -r {} \+
fi

docker compose -f docker-compose.yml -f docker-compose.override.yml -f docker-compose.build.yml build
docker compose up -d
docker compose exec -T backend bash /app/tests-start.sh "$@"
