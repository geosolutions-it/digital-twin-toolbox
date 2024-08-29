#!/bin/bash

set -e

# Perform all actions as $POSTGRES_USER
export PGUSER="$POSTGRES_USER"

psql -c "CREATE DATABASE $POSTGRES_TASKS_DB"

echo "Loading PostGIS extensions into $POSTGRES_TASKS_DB"
psql --dbname="$POSTGRES_TASKS_DB" <<-'EOSQL'
    CREATE EXTENSION IF NOT EXISTS postgis;
    CREATE EXTENSION IF NOT EXISTS postgis_topology;
    -- Reconnect to update pg_setting.resetval
    -- See https://github.com/postgis/docker-postgis/issues/288
    \c
    CREATE EXTENSION IF NOT EXISTS fuzzystrmatch;
    CREATE EXTENSION IF NOT EXISTS postgis_tiger_geocoder;
EOSQL
