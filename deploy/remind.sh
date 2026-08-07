#!/bin/bash
# Напоминания RallyAI (cron). Можно из user crontab (rallyai) или от root:
#   /home/rallyai/rAI/deploy/remind.sh practice
#   sudo bash /home/rallyai/rAI/deploy/remind.sh practice
set -euo pipefail

APP_USER="${APP_USER:-rallyai}"
APP_DIR="/home/${APP_USER}/rAI"
PYTHON="${APP_DIR}/.venv/bin/python"
SCRIPT="${APP_DIR}/remind.py"

run_as_app() {
  if [[ "$(id -u)" -eq 0 ]]; then
    sudo -u "${APP_USER}" "${PYTHON}" "${SCRIPT}" "$@"
  elif [[ "$(id -un)" == "${APP_USER}" ]]; then
    "${PYTHON}" "${SCRIPT}" "$@"
  else
    echo "Запустите от ${APP_USER} или root: bash deploy/remind.sh"
    exit 1
  fi
}

run_as_app "$@"
