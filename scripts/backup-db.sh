#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# LitMatch Database Backup Script
# Backs up both bookdb and dagster databases using pg_dump custom format.
# Designed to run via cron or manually.
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Source .env early so BACKUP_DIR / LOG_FILE overrides take effect
if [[ -f "${PROJECT_DIR}/.env" ]]; then
    set -a
    # shellcheck source=/dev/null
    source "${PROJECT_DIR}/.env"
    set +a
fi

BACKUP_DIR="${BACKUP_DIR:-/var/backups/litmatch}"
LOG_FILE="${LOG_FILE:-/var/log/litmatch-backup.log}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
COMPOSE="podman compose --env-file ${PROJECT_DIR}/.env -f ${PROJECT_DIR}/compose.yaml"

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
Usage: $(basename "$0") [OPTIONS]

Back up LitMatch PostgreSQL databases (bookdb + dagster).

Options:
  --verify    Verify the latest backup by restoring to a temporary database
  --help, -h  Show this help message

Environment variables:
  BACKUP_DIR             Backup directory (default: /var/backups/litmatch)
  BACKUP_RETENTION_DAYS  Days to keep backups (default: 14)
  LOG_FILE               Log file path (default: /var/log/litmatch-backup.log)

Examples:
  $(basename "$0")           # Run backup
  $(basename "$0") --verify  # Verify latest backup
EOF
    exit 0
}

ensure_dirs() {
    mkdir -p "$BACKUP_DIR"
    mkdir -p "$(dirname "$LOG_FILE")"
}

# ----------------------------------------------------------------------------
# Backup
# ----------------------------------------------------------------------------

backup_database() {
    local db_name="$1"
    local dump_file="${BACKUP_DIR}/${db_name}_${TIMESTAMP}.dump"

    log "Backing up database '${db_name}' to ${dump_file} ..."

    if ! $COMPOSE exec -T db pg_dump -Fc -U "$POSTGRES_USER" -d "$db_name" > "$dump_file" 2>>"$LOG_FILE"; then
        rm -f "$dump_file"
        die "pg_dump failed for database '${db_name}'"
    fi

    local size
    size="$(du -h "$dump_file" | cut -f1)"
    log "Backup complete: ${dump_file} (${size})"
}

run_backup() {
    log "=== Starting LitMatch backup ==="

    # Source env vars
    if [[ ! -f "${PROJECT_DIR}/.env" ]]; then
        die ".env file not found at ${PROJECT_DIR}/.env"
    fi
    set -a
    # shellcheck source=/dev/null
    source "${PROJECT_DIR}/.env"
    set +a

    if [[ -z "${POSTGRES_USER:-}" ]]; then
        die "POSTGRES_USER not set in .env"
    fi

    # Check that db container is running
    if ! $COMPOSE exec -T db pg_isready -U "$POSTGRES_USER" > /dev/null 2>&1; then
        die "Database container is not running or not ready"
    fi

    backup_database "${POSTGRES_DB:-bookdb}"
    backup_database "dagster"

    # Enforce retention policy
    local deleted
    deleted=$(find "$BACKUP_DIR" -name "*.dump" -type f -mtime +"$RETENTION_DAYS" -print -delete | wc -l)
    if [[ "$deleted" -gt 0 ]]; then
        log "Retention: removed ${deleted} backup(s) older than ${RETENTION_DAYS} days"
    fi

    log "=== Backup finished successfully ==="
}

# ----------------------------------------------------------------------------
# Verify
# ----------------------------------------------------------------------------

verify_backup() {
    log "=== Starting backup verification ==="

    if [[ ! -f "${PROJECT_DIR}/.env" ]]; then
        die ".env file not found at ${PROJECT_DIR}/.env"
    fi
    set -a
    # shellcheck source=/dev/null
    source "${PROJECT_DIR}/.env"
    set +a

    local latest
    latest="$(ls -t "${BACKUP_DIR}/${POSTGRES_DB:-bookdb}"_*.dump 2>/dev/null | head -1)"
    if [[ -z "$latest" ]]; then
        die "No backup found for '${POSTGRES_DB:-bookdb}' in ${BACKUP_DIR}"
    fi

    log "Verifying backup: ${latest}"

    local temp_db="_backup_verify_$$"

    # Create temp database
    $COMPOSE exec -T db psql -U "$POSTGRES_USER" -d "${POSTGRES_DB:-bookdb}" \
        -c "CREATE DATABASE ${temp_db};" > /dev/null 2>>"$LOG_FILE" \
        || die "Failed to create temp database ${temp_db}"

    # Ensure pgvector extension in temp db
    $COMPOSE exec -T db psql -U "$POSTGRES_USER" -d "$temp_db" \
        -c "CREATE EXTENSION IF NOT EXISTS vector;" > /dev/null 2>>"$LOG_FILE"

    # Restore into temp database
    local restore_ok=true
    if ! cat "$latest" | $COMPOSE exec -T db pg_restore -U "$POSTGRES_USER" -d "$temp_db" --no-owner --no-privileges 2>>"$LOG_FILE"; then
        log "WARNING: pg_restore reported warnings (non-fatal)"
    fi

    # Count tables and rows
    local table_count
    table_count=$($COMPOSE exec -T db psql -U "$POSTGRES_USER" -d "$temp_db" -t -A \
        -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE';") \
        || restore_ok=false

    if [[ "$restore_ok" == true && "$table_count" -gt 0 ]]; then
        log "Verification PASSED: restored ${table_count} tables into temp database"

        # Show row counts per table
        $COMPOSE exec -T db psql -U "$POSTGRES_USER" -d "$temp_db" -t -A \
            -c "SELECT tablename, n_live_tup FROM pg_stat_user_tables ORDER BY tablename;" \
            2>/dev/null | while IFS='|' read -r tbl rows; do
            log "  ${tbl}: ${rows} rows"
        done
    else
        log "Verification FAILED: could not restore or no tables found"
    fi

    # Drop temp database
    $COMPOSE exec -T db psql -U "$POSTGRES_USER" -d "${POSTGRES_DB:-bookdb}" \
        -c "DROP DATABASE IF EXISTS ${temp_db};" > /dev/null 2>>"$LOG_FILE"

    log "=== Verification finished ==="

    if [[ "$restore_ok" != true || "$table_count" -eq 0 ]]; then
        exit 1
    fi
}

# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------

ensure_dirs

case "${1:-}" in
    --verify)
        verify_backup
        ;;
    --help|-h)
        usage
        ;;
    "")
        run_backup
        ;;
    *)
        echo "Unknown option: $1" >&2
        usage
        ;;
esac
