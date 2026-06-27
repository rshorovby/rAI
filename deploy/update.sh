#!/bin/bash
# Обновление бота после git push. Запуск на VPS от root:
#   sudo bash /home/rallyai/rAI/deploy/update.sh
set -euo pipefail

APP_USER="${APP_USER:-rallyai}"
APP_DIR="/home/${APP_USER}/rAI"
SERVICE_NAME="rallyai"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Запустите от root: sudo bash deploy/update.sh"
  exit 1
fi

echo "==> git pull..."
sudo -u "${APP_USER}" git -C "${APP_DIR}" pull

echo "==> Обновляю зависимости..."
sudo -u "${APP_USER}" "${APP_DIR}/.venv/bin/pip" install -q -r "${APP_DIR}/requirements.txt"

echo "==> Перезапускаю бота..."
systemctl restart "${SERVICE_NAME}"
systemctl status "${SERVICE_NAME}" --no-pager
