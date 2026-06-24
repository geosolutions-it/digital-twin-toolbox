#! /usr/bin/env sh

# Thin wrapper around `docker compose` that selects the right set of compose
# files (production toggle + optional component workers) and forwards every
# argument after `--` to `docker compose`.

set -e

usage() {
  cat <<'EOF'
Usage: ./scripts/compose.sh [OPTIONS] -- DOCKER COMPOSE ARGS

Options:
  --prod              Exclude docker-compose.override.yml (production mode)
  --dev               Hot reload (mounted source) for the backend and the
                        selected --workers
  --workers LIST      Comma-separated list of workers to include:
                        vector, point-cloud, mesh, photogrammetry
  -h, --help          Show this help and exit

Examples:
  ./scripts/compose.sh -- up -d
  ./scripts/compose.sh --prod -- up -d
  ./scripts/compose.sh --workers vector,point-cloud -- up -d
  ./scripts/compose.sh --dev --workers vector,point-cloud -- up
  ./scripts/compose.sh --prod --workers vector,point-cloud,mesh -- up -d
  ./scripts/compose.sh -- down
EOF
}

PROD=false
DEV=false
WORKERS=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --prod)
      PROD=true
      shift
      ;;
    --dev)
      DEV=true
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
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      echo >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [ "$#" -eq 0 ]; then
  echo "Error: no docker compose arguments given (expected something after '--')." >&2
  echo >&2
  usage >&2
  exit 1
fi

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

# Dev overrides must be applied AFTER the worker base files so they win.
if [ "$DEV" = true ]; then
  FILES="$FILES -f docker-compose.dev.yml"
fi

docker compose $FILES "$@"
