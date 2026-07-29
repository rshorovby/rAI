#!/bin/bash
# Ежедневный бэкап SQLite. Cron на VPS от root:
#   15 3 * * * root bash /home/rallyai/rAI/deploy/backup_db.sh
set -euo pipefail

APP_USER="${APP_USER:-rallyai}"
APP_DIR="/home/${APP_USER}/rAI"
DB_PATH="${APP_DIR}/data/rally.db"
BACKUP_DIR="${BACKUP_DIR:-${APP_DIR}/data/backups}"
KEEP_DAYS="${KEEP_DAYS:-14}"

mkdir -p "${BACKUP_DIR}"
ts="$(date -u +%Y%m%d_%H%M%S)"
out="${BACKUP_DIR}/rally_${ts}.db"

if [[ ! -f "${DB_PATH}" ]]; then
  echo "Нет БД: ${DB_PATH}"
  exit 1
fi

sudo -u "${APP_USER}" env RALLY_DB="${DB_PATH}" RALLY_BACKUP="${out}" \
  "${APP_DIR}/.venv/bin/python" - <<'PY'
import os
import sqlite3
from pathlib import Path

src = Path(os.environ["RALLY_DB"])
dst = Path(os.environ["RALLY_BACKUP"])
src_conn = sqlite3.connect(str(src))
dst_conn = sqlite3.connect(str(dst))
with dst_conn:
    src_conn.backup(dst_conn)
dst_conn.close()
src_conn.close()
check = sqlite3.connect(str(dst))
row = check.execute("PRAGMA integrity_check").fetchone()
check.close()
assert row and row[0] == "ok", row
print("OK", dst, "integrity", row[0])
PY

find "${BACKUP_DIR}" -name 'rally_*.db' -mtime "+${KEEP_DAYS}" -delete
chown -R "${APP_USER}:${APP_USER}" "${BACKUP_DIR}"
