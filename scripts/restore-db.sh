#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# LitMatch Database Restore Script
# Restores a PostgreSQL backup created by backup-db.sh.
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Source .env early so LOG_FILE override takes effect
if [[ -f "${PROJECT_DIR}/.env" ]]; then
    set -a
    # shellcheck source=/dev/null
    source "${PROJECT_DIR}/.env"
    set +a
fi

LOG_FILE="${LOG_FILE:-/var/log/litmatch-backup.log}"
COMPOSE="podman compose --env-file ${PROJECT_DIR}/.env -f ${PROJECT_DIR}/compose.yaml"

DRY_RUN=false
FORCE=false
BACKUP_FILE=""

# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------

log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $*"
    echo "$msg" | tee -a "$LOG_FILE"
}

die() {
    log "ERROR: $*"
    exit 1
}

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS] <backup-file>

Restore a LitMatch PostgreSQL backup.

Arguments:
  backup-file  Path to a .dump file created by backup-db.sh

Options:
  --dry-run    Show backup contents without restoring
  --force      Skip confirmation prompt
  --help, -h   Show this help message

The target database is detected from the filename:
  bookdb_*.dump  → restores to bookdb
  dagster_*.dump → restores to dagster

Examples:
  $(basename "$0") /var/backups/litmatch/bookdb_20260214_020000.dump
  $(basename "$0") --dry-run /var/backups/litmatch/bookdb_20260214_020000.dump
  $(basename "$0") --force /var/backups/litmatch/dagster_20260214_020000.dump
EOF
    exit 0
}

# ----------------------------------------------------------------------------
# Parse args
# ----------------------------------------------------------------------------

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)  DRY_RUN=true; shift ;;
        --force)    FORCE=true; shift ;;
        --help|-h)  usage ;;
        -*)         die "Unknown option: $1" ;;
        *)          BACKUP_FILE="$1"; shift ;;
    esac
done

if [[ -z "$BACKUP_FILE" ]]; then
    echo "Error: backup file path required" >&2
    usage
fi

if [[ ! -f "$BACKUP_FILE" ]]; then
    die "Backup file not found: ${BACKUP_FILE}"
fi

# Source env vars
if [[ ! -f "${PROJECT_DIR}/.env" ]]; then
    die ".env file not found at ${PROJECT_DIR}/.env"
fi
set -a
# shellcheck source=/dev/null
source "${PROJECT_DIR}/.env"
set +a

# Detect target database from filename
FILENAME="$(basename "$BACKUP_FILE")"
if [[ "$FILENAME" == bookdb_* ]] || [[ "$FILENAME" == "${POSTGRES_DB:-bookdb}"_* ]]; then
    TARGET_DB="${POSTGRES_DB:-bookdb}"
elif [[ "$FILENAME" == dagster_* ]]; then
    TARGET_DB="dagster"
else
    die "Cannot detect target database from filename '${FILENAME}'. Expected bookdb_*.dump or dagster_*.dump"
fi

# ----------------------------------------------------------------------------
# Dry run
# ----------------------------------------------------------------------------

if [[ "$DRY_RUN" == true ]]; then
    log "Dry run: listing contents of ${BACKUP_FILE} (target: ${TARGET_DB})"
    cat "$BACKUP_FILE" | $COMPOSE exec -T db pg_restore -l 2>/dev/null || true
    exit 0
fi

# ----------------------------------------------------------------------------
# Confirm
# ----------------------------------------------------------------------------

if [[ "$FORCE" != true ]]; then
    echo ""
    echo "WARNING: This will restore '${BACKUP_FILE}'"
    echo "         into database '${TARGET_DB}', replacing existing data."
    echo ""
    read -rp "Are you sure? [y/N] " confirm
    if [[ "${confirm,,}" != "y" ]]; then
        echo "Aborted."
        exit 0
    fi
fi

# ----------------------------------------------------------------------------
# Restore
# ----------------------------------------------------------------------------

log "=== Starting restore of '${TARGET_DB}' from ${BACKUP_FILE} ==="

# Check db container is running
if ! $COMPOSE exec -T db pg_isready -U "$POSTGRES_USER" > /dev/null 2>&1; then
    die "Database container is not running or not ready"
fi

# For bookdb, ensure pgvector extension
if [[ "$TARGET_DB" != "dagster" ]]; then
    $COMPOSE exec -T db psql -U "$POSTGRES_USER" -d "$TARGET_DB" \
        -c "CREATE EXTENSION IF NOT EXISTS vector;" > /dev/null 2>>"$LOG_FILE"
fi

if cat "$BACKUP_FILE" | $COMPOSE exec -T db pg_restore -U "$POSTGRES_USER" -d "$TARGET_DB" \
    --clean --if-exists --no-owner --no-privileges 2>>"$LOG_FILE"; then
    log "Restore completed successfully"
else
    log "WARNING: pg_restore completed with warnings (this is often normal for --clean on first restore)"
fi

log "=== Restore finished ==="
