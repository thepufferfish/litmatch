#!/bin/sh
set -e

echo "Running database initialization..."
python -m backend.database
echo "Database initialization complete."

exec "$@"
