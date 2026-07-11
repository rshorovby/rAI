#!/bin/bash
# Установка cron для напоминаний RallyAI (10:00 MSK = 07:00 UTC).
# Запуск на VPS от root один раз:
#   sudo bash /home/rallyai/rAI/deploy/install_reminder_cron.sh
set -euo pipefail

APP_USER="${APP_USER:-rallyai}"
APP_DIR="/home/${APP_USER}/rAI"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Запустите от root"
  exit 1
fi

chmod +x "${APP_DIR}/deploy/remind.sh"
mkdir -p "${APP_DIR}/data"
chown "${APP_USER}:${APP_USER}" "${APP_DIR}/data"

EXISTING=$(sudo -u "${APP_USER}" crontab -l 2>/dev/null || true)
if echo "${EXISTING}" | grep -q "deploy/remind.sh"; then
  echo "Cron для remind.sh уже установлен"
  exit 0
fi

{
  echo "${EXISTING}"
  echo "# RallyAI: напоминание через 7 дней после разбора (10:00 MSK)"
  echo "0 7 * * * ${APP_DIR}/deploy/remind.sh >> ${APP_DIR}/data/remind.log 2>&1"
} | sudo -u "${APP_USER}" crontab -

echo "Cron установлен для пользователя ${APP_USER}"
