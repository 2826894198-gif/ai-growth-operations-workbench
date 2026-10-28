#!/usr/bin/env bash
set -euo pipefail

# PART 07 §206-§207 — explicit restore helper. Production restores require
# explicit APP_ENV=production confirmation and a known restore point.
export PGHOST="${PGHOST:-localhost}"
export PGPORT="${PGPORT:-5432}"
export PGUSER="${PGUSER:-growth}"
export PGPASSWORD="${PGPASSWORD:-growth}"
DB="${PGDATABASE:-growth}"
DUMP="${1:-}"

if [[ -z "${DUMP}" || ! -f "${DUMP}" ]]; then
  echo "usage: $0 path/to/backup.dump"
  exit 2
fi

if [[ "${APP_ENV:-local}" == "production" ]]; then
  read -r -p "This will REPLACE production database ${DB}. Type the database name to confirm: " CONFIRM
  if [[ "${CONFIRM}" != "${DB}" ]]; then
    echo "aborted"
    exit 1
  fi
fi

dropdb --if-exists "${DB}"
createdb "${DB}"
pg_restore -d "${DB}" --no-owner "${DUMP}"
echo "restore complete: ${DUMP}"
