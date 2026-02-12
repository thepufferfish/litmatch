#!/bin/bash
# Entrypoint script for dagster-webserver and dagster-daemon.
# Waits for the dagster-code gRPC server to be fully ready before
# starting the main process.  This prevents
# DagsterCodeLocationNotFoundError caused by the webserver or daemon
# starting before the code server has finished loading.

set -e

DAGSTER_CODE_HOST="${DAGSTER_CODE_HOST:-dagster-code}"
DAGSTER_CODE_PORT="${DAGSTER_CODE_PORT:-4000}"
MAX_RETRIES="${DAGSTER_CODE_MAX_RETRIES:-20}"
RETRY_INTERVAL="${DAGSTER_CODE_RETRY_INTERVAL:-5}"

echo "Waiting for dagster-code gRPC server at ${DAGSTER_CODE_HOST}:${DAGSTER_CODE_PORT}..."

retries=0
until uv run dagster api grpc-health-check \
        --host "$DAGSTER_CODE_HOST" \
        --port "$DAGSTER_CODE_PORT" 2>&1; do
    retries=$((retries + 1))
    if [ "$retries" -ge "$MAX_RETRIES" ]; then
        echo "ERROR: dagster-code gRPC server not ready after ${MAX_RETRIES} attempts" >&2
        echo "Last health check output:" >&2
        uv run dagster api grpc-health-check \
            --host "$DAGSTER_CODE_HOST" \
            --port "$DAGSTER_CODE_PORT" 2>&1 || true
        exit 1
    fi
    echo "dagster-code not ready (attempt ${retries}/${MAX_RETRIES}), retrying in ${RETRY_INTERVAL}s..."
    sleep "$RETRY_INTERVAL"
done

echo "dagster-code gRPC server is ready."
exec "$@"
