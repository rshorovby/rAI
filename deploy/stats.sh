#!/bin/bash
# Отчёт аналитики RallyAI. Запуск на VPS от root:
#   sudo bash /home/rallyai/rAI/deploy/stats.sh
set -euo pipefail

APP_USER="${APP_USER:-rallyai}"
APP_DIR="/home/${APP_USER}/rAI"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Запустите от root: sudo bash deploy/stats.sh"
  exit 1
fi

sudo -u "${APP_USER}" "${APP_DIR}/.venv/bin/python" "${APP_DIR}/stats_report.py"
