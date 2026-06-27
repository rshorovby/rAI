# Развёртывание RallyAI на VPS (Hetzner)

Пошаговая инструкция для запуска бота **24/7** на сервере в Европе.  
Gemini API с такого сервера работает **без VPN**.

Рекомендуемый провайдер: [Hetzner Cloud](https://www.hetzner.com/cloud) (~€4/мес).  
Альтернативы: DigitalOcean, Vultr (регион EU/US).

---

## Что понадобится от вас

| Что | Где взять |
|-----|-----------|
| Аккаунт Hetzner | [hetzner.com/cloud](https://www.hetzner.com/cloud) — карта для оплаты |
| Токен Telegram-бота | [@BotFather](https://t.me/BotFather) |
| Ключ Gemini API | [Google AI Studio](https://aistudio.google.com/apikey) |
| Репозиторий на GitHub | уже есть — понадобится **публичный** URL или доступ по SSH |
| 30–40 минут | один раз на настройку |

**Бюджет:** ~€4–5 в месяц (сервер CX22 или аналог).

---

## Часть 1. Создать сервер в Hetzner

### 1.1 Регистрация

1. Зайдите на [console.hetzner.cloud](https://console.hetzner.cloud).
2. Создайте проект (например, `rallyai`).
3. Добавьте способ оплаты.

### 1.2 SSH-ключ (с Mac)

Откройте **Терминал** на Mac и выполните:

```bash
ssh-keygen -t ed25519 -C "rallyai" -f ~/.ssh/hetzner_rallyai -N ""
cat ~/.ssh/hetzner_rallyai.pub
```

Скопируйте **всю строку** из вывода `cat` (начинается с `ssh-ed25519 ...`).

В Hetzner: **Security → SSH keys → Add SSH key** → вставьте скопированное.

### 1.3 Создать сервер

**Add Server:**

| Параметр | Значение |
|----------|----------|
| Location | **Helsinki** или **Nuremberg** (EU) |
| Image | **Ubuntu 24.04** |
| Type | **CX22** (2 vCPU, 4 GB) — с запасом; можно CX11 для теста |
| SSH key | выберите ключ из шага 1.2 |
| Name | `rallyai` |

Нажмите **Create**. Через минуту появится **IP-адрес** (например `95.xxx.xxx.xxx`).

### 1.4 Первый вход по SSH

```bash
ssh -i ~/.ssh/hetzner_rallyai root@ВАШ_IP
```

При первом входе ответьте `yes`. Вы должны увидеть приглашение `root@rallyai:~#`.

---

## Часть 2. Установить бота (автоматически)

На сервере (под root) выполните **одну команду** — подставьте URL вашего репозитория:

```bash
apt update && apt install -y git
git clone https://github.com/ВАШ_ЛОГИН/rAI.git /tmp/rAI
bash /tmp/rAI/deploy/install.sh https://github.com/ВАШ_ЛОГИН/rAI.git
```

Скрипт:
- создаст пользователя `rallyai`
- установит Python и зависимости
- склонирует репозиторий в `/home/rallyai/rAI`
- создаст `.env` из шаблона
- настроит автозапуск через systemd

---

## Часть 3. Заполнить секреты

```bash
nano /home/rallyai/rAI/.env
```

Вставьте (без кавычек, без пробелов вокруг `=`):

```env
TELEGRAM_BOT_TOKEN=123456789:AAH...
GEMINI_API_KEY=AIzaSy...
GEMINI_MODEL=gemini-2.0-flash
```

Сохранить: `Ctrl+O`, Enter, выход: `Ctrl+X`.

---

## Часть 4. Запустить бота

**Сначала остановите бота на Mac**, если он ещё запущен локально (`Ctrl+C` в терминале).  
С одним токеном может работать только **один** процесс.

На сервере:

```bash
systemctl start rallyai
systemctl status rallyai
```

Должно быть: `Active: active (running)`.

Проверка в Telegram: откройте бота → `/start` → отправьте тестовое видео.

### Логи (если что-то не так)

```bash
journalctl -u rallyai -f
```

Выход из логов: `Ctrl+C`.

---

## Часть 5. После перезагрузки сервера

Ничего делать не нужно — бот поднимется сам (`systemctl enable` уже настроен).

---

## Обновление бота (после ваших правок в git)

На Mac: закоммитьте и запушьте изменения в GitHub.

На сервере:

```bash
ssh -i ~/.ssh/hetzner_rallyai root@ВАШ_IP
sudo bash /home/rallyai/rAI/deploy/update.sh
```

---

## Полезные команды

| Действие | Команда |
|----------|---------|
| Статус | `systemctl status rallyai` |
| Перезапуск | `systemctl restart rallyai` |
| Остановить | `systemctl stop rallyai` |
| Логи | `journalctl -u rallyai -f` |
| Последние 100 строк логов | `journalctl -u rallyai -n 100` |

---

## Если репозиторий приватный

Вариант A — **Deploy key** на GitHub (рекомендуется):

```bash
sudo -u rallyai ssh-keygen -t ed25519 -f /home/rallyai/.ssh/id_ed25519 -N ""
sudo -u rallyai cat /home/rallyai/.ssh/id_ed25519.pub
```

Добавьте ключ в GitHub: репозиторий → **Settings → Deploy keys → Add**.

Клонирование:

```bash
sudo -u rallyai git clone git@github.com:ВАШ_ЛОГИН/rAI.git /home/rallyai/rAI
```

Дальше — шаги 3–4 (`.env` и `systemctl`).

Вариант B — сделать репозиторий **публичным** на время теста (секреты всё равно только в `.env` на сервере, не в git).

---

## Резервная копия истории игроков

История хранится в файле:

```
/home/rallyai/rAI/data/rally.db
```

Скачать на Mac:

```bash
scp -i ~/.ssh/hetzner_rallyai root@ВАШ_IP:/home/rallyai/rAI/data/rally.db ./rally-backup.db
```

---

## Частые проблемы

| Симптом | Решение |
|---------|---------|
| Бот не отвечает | `systemctl status rallyai` — упал? Смотрите `journalctl -u rallyai -n 50` |
| Два бота конфликтуют | Остановите локальный на Mac |
| `location is not supported` | Сервер не в EU — пересоздайте в Helsinki/Nuremberg |
| `503 UNAVAILABLE` | Временная перегрузка Gemini — подождите и отправьте видео снова |
| `Не заданы переменные окружения` | Проверьте `.env` на сервере |
| После рестарта бота «забыл» диалог | Нормально: активный чат в памяти; история разборов в SQLite сохраняется |

---

## Вариант через Docker (опционально)

Если удобнее контейнер:

```bash
cd /home/rallyai/rAI
cp .env.example .env && nano .env   # заполнить
docker compose up -d --build
docker compose logs -f
```

Для Docker сначала установите: `apt install -y docker.io docker-compose-v2`.

Основной путь в этой инструкции — **systemd** (проще для первого раза).

---

## Чеклист «готов к тесту в окружении»

- [ ] Сервер в EU (Helsinki / Nuremberg)
- [ ] `.env` заполнен на сервере
- [ ] `systemctl status rallyai` → `active (running)`
- [ ] Локальный бот на Mac **выключен**
- [ ] `/start` и видео работают в Telegram
- [ ] Друзьям отправлена ссылка на бота: `t.me/ИМЯ_ВАШЕГО_БОТА`
