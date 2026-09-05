#!/bin/bash
# Публичный HTTPS для iOS API на том же Droplet (lock #35).
# Запуск от root:
#   sudo bash /home/rallyai/rAI/deploy/enable_http.sh
set -euo pipefail

APP_USER="${APP_USER:-rallyai}"
APP_DIR="/home/${APP_USER}/rAI"
ENV_FILE="${APP_DIR}/.env"
DOMAIN="${API_DOMAIN:-rallymind.64.227.74.21.sslip.io}"
BUNDLE_ID="${APPLE_BUNDLE_ID:-com.rakets.rallymind}"
CERTBOT_EMAIL="${CERTBOT_EMAIL:-rustam.shorov.by@gmail.by}"
SITE_SRC="${APP_DIR}/deploy/nginx-api.conf"
SITE_DST="/etc/nginx/sites-available/rallyai-api"
LINK_DST="/etc/nginx/sites-enabled/rallyai-api"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Запустите от root: sudo bash deploy/enable_http.sh"
  exit 1
fi

echo "==> nginx + certbot..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq nginx certbot python3-certbot-nginx

echo "==> HTTP_PORT в .env (если ещё нет)..."
touch "${ENV_FILE}"
chown "${APP_USER}:${APP_USER}" "${ENV_FILE}"
python3 - "${ENV_FILE}" "${BUNDLE_ID}" <<'PY'
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
bundle = sys.argv[2]
text = path.read_text() if path.exists() else ""
lines = text.splitlines()
keys = {
    "HTTP_HOST": "127.0.0.1",
    "HTTP_PORT": "8080",
    "APPLE_BUNDLE_ID": bundle,
}
existing = {
    line.split("=", 1)[0].strip()
    for line in lines
    if line.strip() and not line.lstrip().startswith("#") and "=" in line
}
out = list(lines)
for key, value in keys.items():
    if key not in existing:
        out.append(f"{key}={value}")
path.write_text("\n".join(out).rstrip() + "\n")
PY
chmod 600 "${ENV_FILE}"
chown "${APP_USER}:${APP_USER}" "${ENV_FILE}"

echo "==> nginx site ${DOMAIN}..."
sed "s/DOMAIN/${DOMAIN}/g" "${SITE_SRC}" > "${SITE_DST}"
ln -sfn "${SITE_DST}" "${LINK_DST}"
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl enable nginx
systemctl reload nginx || systemctl start nginx

echo "==> перезапуск бота с HTTP..."
systemctl restart rallyai
sleep 4
if ! systemctl is-active --quiet rallyai; then
  echo "rallyai не стартовал, смотрите journalctl -u rallyai"
  journalctl -u rallyai -n 40 --no-pager
  exit 1
fi
if ! curl -sS -o /dev/null -w "%{http_code}" --max-time 8 http://127.0.0.1:8080/v1/me | grep -q 401; then
  echo "HTTP на 127.0.0.1:8080 не отвечает 401 на /v1/me"
  journalctl -u rallyai -n 40 --no-pager
  exit 1
fi

echo "==> Let's Encrypt..."
certbot --nginx -d "${DOMAIN}" --non-interactive --agree-tos -m "${CERTBOT_EMAIL}" --redirect

echo "==> проверка HTTPS..."
code="$(curl -sS -o /dev/null -w "%{http_code}" --max-time 15 "https://${DOMAIN}/v1/me")"
echo "GET https://${DOMAIN}/v1/me -> ${code}"
if [[ "${code}" != "401" ]]; then
  echo "Ожидал 401 без токена"
  exit 1
fi

echo "Готово. API: https://${DOMAIN}"
systemctl status rallyai --no-pager
systemctl status nginx --no-pager
