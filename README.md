# RallyAI 🎾

Telegram-бот для разбора техники тенниса по видео. Пользователь отправляет короткий ролик, бот анализирует его через Google Gemini и возвращает структурированный отчёт на русском с градацией ошибок по критичности. После разбора можно задавать уточняющие вопросы в чате.

## Возможности

- Анализ видео (до 20 МБ, 10–30 сек) с разбором техники, работы ног и баланса
- Подпись к видео учитывается при разборе (например, «это бэкхенд, болит локоть»)
- Диалог после разбора: уточняющие вопросы текстом
- Меню команд внизу чата
- История прошлых разборов (`/history`)
- Форматированные отчёты (Telegram HTML)

## Требования

- Python 3.9+
- Токен Telegram-бота — от [@BotFather](https://t.me/BotFather)
- Ключ Google Gemini API — из [Google AI Studio](https://aistudio.google.com/apikey)

## Установка

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Настройка

Скопируйте шаблон и заполните значения:

```bash
cp .env.example .env
```

| Переменная | Обязательна | Назначение |
|------------|-------------|------------|
| `TELEGRAM_BOT_TOKEN` | да | Токен бота от BotFather |
| `GEMINI_API_KEY` | да | Ключ Google Gemini |
| `GEMINI_MODEL` | нет | Модель (по умолчанию `gemini-2.0-flash`) |

## Запуск

```bash
.venv/bin/python main.py
```

Остановка — `Ctrl+C`.

Проверить ключ Gemini без Telegram:

```bash
.venv/bin/python test_gemini.py
```

## Тесты и проверки

```bash
.venv/bin/pytest          # тесты
.venv/bin/ruff check .    # линтер
.venv/bin/black --check . # форматирование
```

## Структура

| Файл | Роль |
|------|------|
| `main.py` | Точка входа: логирование, запуск polling |
| `bot.py` | Telegram-логика: команды, меню, приём видео, диалог |
| `analyzer.py` | Загрузка видео в Gemini, разбор и follow-up диалог |
| `prompts.py` | Системные и пользовательские промпты |
| `formatting.py` | Конвертация markdown отчёта в Telegram HTML |
| `config.py` | Загрузка настроек из `.env` |
| `errors.py` | Человекочитаемые сообщения об ошибках API |

## Развёртывание на VPS (24/7)

Подробная инструкция для Hetzner и systemd: **[DEPLOY.md](DEPLOY.md)**.

Кратко: сервер в EU → `sudo bash deploy/install.sh URL_РЕПО` → заполнить `.env` → `systemctl start rallyai`.

## Лицензия

Учебный/личный проект.
