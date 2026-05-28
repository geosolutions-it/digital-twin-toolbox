#! /usr/bin/env sh

# Usage: ./scripts/up.sh [OPTIONS] [-- DOCKER COMPOSE ARGS]
#
# Options:
#   --prod              Exclude docker-compose.override.yml (production mode)
#   --workers LIST      Comma-separated list of workers to include:
#                         vector, point-cloud, blender, opensfm
#
# Examples:
#   ./scripts/up.sh -- up -d
#   ./scripts/up.sh --prod -- up -d
#   ./scripts/up.sh --workers vector,point-cloud -- up -d
#   ./scripts/up.sh --prod --workers vector,point-cloud,blender -- up -d
#   ./scripts/up.sh -- down

set -e

PROD=false
WORKERS=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --prod)
      PROD=true
      shift
      ;;
    --workers)
      WORKERS="$2"
      shift 2
      ;;
    --)
      shift
      break
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
done

FILES="-f docker-compose.yml"

if [ "$PROD" = false ]; then
  FILES="$FILES -f docker-compose.override.yml"
fi

if [ -n "$WORKERS" ]; then
  for worker in $(echo "$WORKERS" | tr ',' ' '); do
    file="docker-compose.worker.$worker.yml"
    if [ ! -f "$file" ]; then
      echo "Worker compose file not found: $file" >&2
      exit 1
    fi
    FILES="$FILES -f $file"
  done
fi

docker compose $FILES "$@"
