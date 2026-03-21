#!/bin/bash
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/backups}"
DATABASE_URL="${DATABASE_URL:?DATABASE_URL environment variable is required}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
FILENAME="cryptomind_${TIMESTAMP}.sql.gz"

mkdir -p "${BACKUP_DIR}"

pg_dump "${DATABASE_URL}" | gzip > "${BACKUP_DIR}/${FILENAME}"

find "${BACKUP_DIR}" -name "*.sql.gz" -mtime +7 -delete

echo "Backup created: ${BACKUP_DIR}/${FILENAME}"
