#!/bin/bash
# Первичная установка RallyAI на VPS (Ubuntu/Debian).
# Запуск: bash deploy/install.sh https://github.com/ВАШ_ЛОГИН/rAI.git
set -euo pipefail

REPO_URL="${1:-}"
APP_USER="${APP_USER:-rallyai}"
APP_DIR="/home/${APP_USER}/rAI"
SERVICE_NAME="rallyai"

if [[ -z "${REPO_URL}" ]]; then
  echo "Использование: bash deploy/install.sh https://github.com/USER/rAI.git"
  exit 1
fi

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Запустите скрипт от root: sudo bash deploy/install.sh URL"
  exit 1
fi

echo "==> Создаю пользователя ${APP_USER} (если ещё нет)..."
if ! id "${APP_USER}" &>/dev/null; then
  adduser --disabled-password --gecos "" "${APP_USER}"
fi

echo "==> Устанавливаю системные пакеты..."
apt-get update -qq
apt-get install -y -qq git python3 python3-venv python3-pip

echo "==> Клонирую репозиторий..."
if [[ -d "${APP_DIR}/.git" ]]; then
  echo "    Репозиторий уже есть: ${APP_DIR}"
  sudo -u "${APP_USER}" git -C "${APP_DIR}" pull
else
  sudo -u "${APP_USER}" git clone "${REPO_URL}" "${APP_DIR}"
fi

echo "==> Создаю venv и ставлю зависимости..."
sudo -u "${APP_USER}" python3 -m venv "${APP_DIR}/.venv"
sudo -u "${APP_USER}" "${APP_DIR}/.venv/bin/pip" install -q -r "${APP_DIR}/requirements.txt"

echo "==> Создаю каталог для базы данных..."
sudo -u "${APP_USER}" mkdir -p "${APP_DIR}/data"

if [[ ! -f "${APP_DIR}/.env" ]]; then
  echo "==> Создаю .env из шаблона — ЗАПОЛНИТЕ ЕГО перед запуском!"
  sudo -u "${APP_USER}" cp "${APP_DIR}/.env.example" "${APP_DIR}/.env"
  chmod 600 "${APP_DIR}/.env"
  chown "${APP_USER}:${APP_USER}" "${APP_DIR}/.env"
fi

echo "==> Устанавливаю systemd-сервис..."
cp "${APP_DIR}/deploy/rallyai.service" "/etc/systemd/system/${SERVICE_NAME}.service"
systemctl daemon-reload
systemctl enable "${SERVICE_NAME}"

echo ""
echo "Готово. Дальше:"
echo "  1. nano ${APP_DIR}/.env   # вставьте TELEGRAM_BOT_TOKEN и GEMINI_API_KEY"
echo "  2. systemctl start ${SERVICE_NAME}"
echo "  3. systemctl status ${SERVICE_NAME}"
echo "  4. journalctl -u ${SERVICE_NAME} -f   # логи"
