#!/bin/bash
# Apply database migration to add timezone support to timestamp columns

set -e

# Check if DATABASE_URL is set
if [ -z "$DATABASE_URL" ]; then
    echo "ERROR: DATABASE_URL environment variable must be set"
    exit 1
fi

echo "Applying migration: 001_add_timezone_to_timestamps.sql"
psql "$DATABASE_URL" -f "$(dirname "$0")/001_add_timezone_to_timestamps.sql"
echo "Migration applied successfully!"
