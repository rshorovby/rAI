# Развёртывание RallyAI на DigitalOcean

Пошаговая инструкция для запуска бота **24/7** на виртуальном сервере (Droplet) в Европе.  
[Google Gemini API](https://aistudio.google.com) с EU-сервера работает **без VPN**.

Провайдер: [DigitalOcean](https://www.digitalocean.com) — раздел **Droplets** (это обычный VPS).

---

## Что понадобится от вас

| Что | Где взять |
|-----|-----------|
| Аккаунт DigitalOcean | [digitalocean.com](https://www.digitalocean.com) → **Sign up** |
| Банковская карта | привязка в аккаунте (списание ~$6–12/мес) |
| Токен Telegram-бота | [@BotFather](https://t.me/BotFather) |
| Ключ Gemini API | [Google AI Studio](https://aistudio.google.com/apikey) |
| Репозиторий на GitHub | публичный URL или Deploy key (см. ниже) |
| 30–40 минут | один раз на настройку |

**Бюджет:** ~**$6–12/мес** за Droplet (см. размер ниже).

> У новых аккаунтов DigitalOcean иногда дают промо-кредит. Проверьте в панели после регистрации — это не обязательно, но может покрыть первые месяцы.

---

## Часть 1. Регистрация в DigitalOcean

1. Откройте [digitalocean.com](https://www.digitalocean.com) → **Sign up**.
2. Подтвердите email.
3. В панели [cloud.digitalocean.com](https://cloud.digitalocean.com) добавьте способ оплаты:  
   **Account → Billing** (или мастер настройки при первом входе).

Дальше работаем в [cloud.digitalocean.com](https://cloud.digitalocean.com).

---

## Часть 2. SSH-ключ (на Mac)

Откройте **Терминал**:

```bash
ssh-keygen -t ed25519 -C "rallyai-digitalocean" -f ~/.ssh/digitalocean_rallyai -N ""
cat ~/.ssh/digitalocean_rallyai.pub
```

Скопируйте **всю строку** (начинается с `ssh-ed25519 ...`).

В DigitalOcean:

1. **Account** (правый верхний угол) → **Settings**
2. Слева **Security** → **SSH Keys**
3. **Add SSH Key** → вставьте ключ → имя, например `MacBook`

Без SSH-ключа придётся входить по паролю из email — это менее удобно и менее безопасно.

---

## Часть 3. Создать Droplet (сервер)

1. В панели нажмите зелёную кнопку **Create** → **Droplets**.

2. Заполните поля:

| Параметр | Что выбрать |
|----------|-------------|
| **Region** | **Amsterdam** или **Frankfurt** (EU — для Gemini) |
| **Image** | **Ubuntu 24.04 (LTS) x64** |
| **Size** | **Basic** → **Regular** |
| | Минимум для теста: **$6/mo** (1 GB RAM, 1 vCPU) |
| | Комфортнее: **$12/mo** (2 GB RAM, 1 vCPU) — рекомендуем |
| **Authentication** | **SSH Key** → выберите ключ из части 2 |
| **Hostname** | `rallyai` (любое имя) |

3. Остальное можно не трогать (без доп. опций).
4. **Create Droplet**.

Через 1–2 минуты на странице Droplet появится **публичный IP** (например `164.xxx.xxx.xxx`). Запишите его.

---

## Часть 4. Первый вход по SSH

На Mac:

```bash
ssh -i ~/.ssh/digitalocean_rallyai root@ВАШ_IP
```

При вопросе `Are you sure...` → `yes`.  
Должно появиться: `root@rallyai:~#`

**Если SSH не подключается:** в панели DigitalOcean откройте Droplet → **Access** → **Launch Droplet Console** — веб-терминал в браузере.

---

## Часть 5. Установить бота (автоматически)

На сервере (вы под `root`) — подставьте URL вашего GitHub-репозитория:

```bash
apt update && apt install -y git
git clone https://github.com/ВАШ_ЛОГИН/rAI.git /tmp/rAI
bash /tmp/rAI/deploy/install.sh https://github.com/ВАШ_ЛОГИН/rAI.git
```

Скрипт:
- создаст пользователя `rallyai`
- установит Python и зависимости
- склонирует код в `/home/rallyai/rAI`
- создаст `.env` из шаблона
- настроит автозапуск через **systemd**

---

## Часть 6. Заполнить секреты

```bash
nano /home/rallyai/rAI/.env
```

Вставьте (те же значения, что в локальном `.env` на Mac):

```env
TELEGRAM_BOT_TOKEN=123456789:AAH...
GEMINI_API_KEY=AIzaSy...
GEMINI_MODEL_PRO=gemini-3.1-pro-preview
```

Модель одна для всех тарифов (качество не режется). Тарифы Free/Pro ограничивают
только число разборов и длину видео. `GEMINI_MODEL_PRO` можно не указывать —
есть дефолт в `config.py`. Старая `GEMINI_MODEL` тоже работает как fallback.

`GEMINI_MODEL_FREE` больше не используется для маршрутизации (можно удалить из `.env`).

Сохранить: `Ctrl+O`, Enter. Выход: `Ctrl+X`.

---

## Часть 7. Запустить бота

**Сначала остановите бота на Mac** (`Ctrl+C` в терминале, где он запущен).  
С одним токеном Telegram может работать только **один** процесс polling.

На сервере:

```bash
systemctl start rallyai
systemctl status rallyai
```

Ожидаем: `Active: active (running)` зелёным.

Проверка в Telegram: откройте бота → `/start` → отправьте короткое видео.

### Логи

```bash
journalctl -u rallyai -f
```

Выход: `Ctrl+C`.

---

## Часть 8. После перезагрузки Droplet

Ничего делать не нужно — бот стартует сам (`systemctl enable` уже настроен скриптом установки).

---

## Обновление бота (после правок в git)

На Mac: `git push` в GitHub.

На сервере:

```bash
ssh -i ~/.ssh/digitalocean_rallyai root@ВАШ_IP
sudo bash /home/rallyai/rAI/deploy/update.sh
```

---

## Полезные команды

| Действие | Команда |
|----------|---------|
| Статус | `systemctl status rallyai` |
| Перезапуск | `systemctl restart rallyai` |
| Остановить | `systemctl stop rallyai` |
| Логи в реальном времени | `journalctl -u rallyai -f` |
| Последние 100 строк | `journalctl -u rallyai -n 100` |

### Управление Droplet в панели DigitalOcean

| Действие | Где |
|----------|-----|
| Перезагрузить сервер | Droplet → **Power** → **Reboot** |
| Выключить (экономия) | **Power** → **Power off** — бот не будет работать |
| Удалить сервер | **Destroy** — все данные пропадут |
| Посмотреть IP | Страница Droplet → **Public IPv4** |

---

## Если репозиторий приватный

**Вариант A — Deploy key (рекомендуется):**

```bash
sudo -u rallyai ssh-keygen -t ed25519 -f /home/rallyai/.ssh/id_ed25519 -N ""
sudo -u rallyai cat /home/rallyai/.ssh/id_ed25519.pub
```

GitHub → репозиторий → **Settings → Deploy keys → Add deploy key** → вставьте ключ.

Установка вручную (вместо `install.sh` с HTTPS):

```bash
adduser --disabled-password --gecos "" rallyai
apt install -y git python3 python3-venv
sudo -u rallyai git clone git@github.com:ВАШ_ЛОГИН/rAI.git /home/rallyai/rAI
bash /home/rallyai/rAI/deploy/install.sh git@github.com:ВАШ_ЛОГИН/rAI.git
```

> Для `git@github.com` скрипт `install.sh` должен клонировать по SSH — если `install.sh` ожидает HTTPS, клонируйте вручную как выше, затем выполните только части скрипта (venv, systemd) или адаптируйте URL.

Проще: на время теста сделать репо **публичным** — секреты всё равно только в `.env` на сервере.

---

## Резервная копия истории игроков

Файл на сервере:

```
/home/rallyai/rAI/data/rally.db
```

Ежедневный бэкап с ротацией 14 дней (cron от root):

```bash
# crontab -e
15 3 * * * root bash /home/rallyai/rAI/deploy/backup_db.sh
```

Бэкапы: `/home/rallyai/rAI/data/backups/rally_YYYYMMDD_HHMMSS.db`

Скачать на Mac:

```bash
scp -i ~/.ssh/digitalocean_rallyai root@ВАШ_IP:/home/rallyai/rAI/data/rally.db ./rally-backup.db
```

Истечение Pro и напоминания о продлении:

```bash
30 9 * * * root bash /home/rallyai/rAI/deploy/expire_subscriptions.sh
```

Выдать Pro вручную (нужен `ADMIN_USER_IDS` в `.env`):

```text
/grant <telegram_user_id> [months]
```

Или с сервера:

```bash
sudo -u rallyai /home/rallyai/rAI/.venv/bin/python /home/rallyai/rAI/grant_pro.py 123456789 1
```

Practice pre/post (каждый час; окна 09:00 / 20:00 МСК внутри кода) + 7-дневный remind:

```bash
sudo bash /home/rallyai/rAI/deploy/install_practice_cron.sh
```

После установки: `sudo -u rallyai crontab -l` и ручной прогон
`sudo -u rallyai /home/rallyai/rAI/deploy/remind.sh practice`
(лог: `data/practice.log`). Pre уходит в **день** тренировки после 09:00 МСК, post — после 20:00.

Недельный дайджест:

```bash
0 10 * * 1 root sudo -u rallyai /home/rallyai/rAI/.venv/bin/python /home/rallyai/rAI/remind.py digest
```

---

## Частые проблемы

| Симптом | Решение |
|---------|---------|
| Бот не отвечает | `systemctl status rallyai` → смотрите `journalctl -u rallyai -n 50` |
| Два бота конфликтуют | Остановите локальный бот на Mac |
| `Permission denied (publickey)` | SSH-ключ не добавлен в DigitalOcean или неверный путь `-i` |
| `location is not supported` | Droplet не в EU — пересоздайте в Amsterdam/Frankfurt |
| `503 UNAVAILABLE` | Временная перегрузка Gemini — подождите, отправьте видео снова |
| `Не заданы переменные окружения` | Проверьте `/home/rallyai/rAI/.env` |
| Нет денег на аккаунте | **Billing** в DigitalOcean — пополните баланс |
| После рестарта «забыл» диалог | Активный диалог теперь в `active_sessions` (TTL 7 дней); история — в `player_sessions` |
| Нет уведомления о тренировке | Cron: `install_practice_cron.sh`; лог `data/practice.log`; дата должна быть **сегодня** МСК; pre ≥09:00, post ≥20:00 |

---

## Вариант через Docker (опционально)

```bash
apt install -y docker.io docker-compose-v2
cd /home/rallyai/rAI
cp .env.example .env && nano .env
docker compose up -d --build
docker compose logs -f
```

Основной путь — **systemd** (проще для первого раза).

---

## Чеклист «готов к тесту в окружении»

- [ ] Droplet в **Amsterdam** или **Frankfurt**
- [ ] `.env` заполнен на сервере
- [ ] `systemctl status rallyai` → `active (running)`
- [ ] Локальный бот на Mac **выключен**
- [ ] `/start` и видео работают в Telegram
- [ ] Друзьям отправлена ссылка: `t.me/ИМЯ_ВАШЕГО_БОТА`

---

## Альтернатива

Та же инструкция подойдёт для любого Ubuntu VPS. Если позже захотите дешевле — [Hetzner Cloud](https://www.hetzner.com/cloud) (EU, ~€4/мес): шаги 5–7 идентичны, меняется только создание сервера в их панели.
