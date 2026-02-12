#!/bin/bash
# Creates a separate 'dagster' database for Dagster internal storage
# (run history, event logs, schedule/sensor state). This keeps Dagster
# tables isolated from the application schema in $POSTGRES_DB.
#
# Mounted into the db container at /docker-entrypoint-initdb.d/ so it
# runs automatically on first initialization of the data volume.
# Idempotent: safe to run even if the database already exists.
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    SELECT 'CREATE DATABASE dagster'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'dagster')\gexec
    GRANT ALL PRIVILEGES ON DATABASE dagster TO "$POSTGRES_USER";
EOSQL
