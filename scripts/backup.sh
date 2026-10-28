#!/usr/bin/env bash
set -euo pipefail

# PART 07 §86-§95 — PostgreSQL backup helpers (logical + base + verify + restore drill).
export PGHOST="${PGHOST:-localhost}"
export PGPORT="${PGPORT:-5432}"
export PGUSER="${PGUSER:-growth}"
export PGPASSWORD="${PGPASSWORD:-growth}"
DB="${PGDATABASE:-growth}"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
STAMP="$(date +%Y%m%d-%H%M%S)"

mkdir -p "${BACKUP_DIR}"

case "${1:-}" in
  logical)
    pg_dump -Fc -d "${DB}" -f "${BACKUP_DIR}/growth-${STAMP}.dump"
    echo "logical backup: ${BACKUP_DIR}/growth-${STAMP}.dump"
    ;;
  base)
    pg_basebackup -D "${BACKUP_DIR}/base-${STAMP}" -Ft -z -P
    echo "base backup: ${BACKUP_DIR}/base-${STAMP}.tar.gz"
    ;;
  verify)
    LATEST="$(ls -1t "${BACKUP_DIR}"/growth-*.dump | head -1)"
    pg_restore --list "${LATEST}" > /dev/null
    echo "verified: ${LATEST}"
    ;;
  restore-drill)
    LATEST="$(ls -1t "${BACKUP_DIR}"/growth-*.dump | head -1)"
    DRILL_DB="growth_restore_drill"
    dropdb --if-exists "${DRILL_DB}"
    createdb "${DRILL_DB}"
    pg_restore -d "${DRILL_DB}" --no-owner "${LATEST}" > /dev/null
    psql -d "${DRILL_DB}" -c "SELECT count(*) FROM alembic_version;"
    echo "restore drill OK: ${DRILL_DB}"
    ;;
  *)
    echo "usage: $0 {logical|base|verify|restore-drill}"
    exit 2
    ;;
esac
