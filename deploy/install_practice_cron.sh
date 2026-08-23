#!/bin/bash
# Установка cron для practice pre/post (каждый час) и 7-дневных remind.
# Запуск на VPS от root один раз:
#   sudo bash /home/rallyai/rAI/deploy/install_practice_cron.sh
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
# убрать старые строки/комменты remind/practice, переустановить
FILTERED=$(
  echo "${EXISTING}" | grep -v "deploy/remind.sh" | grep -v "RallyAI: practice" | grep -v "RallyAI: напоминание через 7 дней" | grep -v "RallyAI: опрос" || true
)

{
  if [[ -n "${FILTERED}" ]]; then
    echo "${FILTERED}"
  fi
  echo "# RallyAI: practice pre/post (окна 09:00 и 20:00 МСК проверяются в коде)"
  echo "5 * * * * ${APP_DIR}/deploy/remind.sh practice >> ${APP_DIR}/data/practice.log 2>&1"
  echo "# RallyAI: review fallback 24ч (Product V2)"
  echo "10 * * * * ${APP_DIR}/deploy/remind.sh review >> ${APP_DIR}/data/review_fallback.log 2>&1"
  echo "# RallyAI: опросы через 24ч (нет видео / не прошёл онбординг)"
  echo "20 * * * * ${APP_DIR}/deploy/remind.sh survey >> ${APP_DIR}/data/survey.log 2>&1"
  echo "# RallyAI: напоминание через 7 дней (10:00 МСК)"
  echo "0 7 * * * ${APP_DIR}/deploy/remind.sh >> ${APP_DIR}/data/remind.log 2>&1"
} | sudo -u "${APP_USER}" crontab -

echo "Cron practice+remind установлен для пользователя ${APP_USER}"
sudo -u "${APP_USER}" crontab -l
echo "Проверка: sudo -u ${APP_USER} ${APP_DIR}/deploy/remind.sh practice"
