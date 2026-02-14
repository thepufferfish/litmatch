#!/bin/sh
set -e

echo "Running database migrations..."
python -m backend.database
echo "Database migrations complete."

exec "$@"
