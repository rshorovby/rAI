# RallyAI

## Что это

Telegram-бот для разбора техники тенниса по видео. Принимает ролик, отправляет его в Google Gemini, возвращает структурированный отчёт на русском и ведёт диалог с уточняющими вопросами. Стек: Python + `python-telegram-bot` (async) + `google-genai`.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env   # заполнить TELEGRAM_BOT_TOKEN и GEMINI_API_KEY
```

Обязательные переменные окружения: `TELEGRAM_BOT_TOKEN`, `GEMINI_API_KEY`. Опционально: `GEMINI_MODEL`.

## Build, test, lint

```bash
.venv/bin/python main.py        # запуск бота
.venv/bin/pytest                # тесты
.venv/bin/pytest tests/test_formatting.py::test_bold   # один тест
.venv/bin/ruff check .          # линтер
.venv/bin/black --check .       # проверка форматирования
```

Команды `python`/`pip` без префикса в этой системе НЕ работают — используй `.venv/bin/python` или активируй venv (`source .venv/bin/activate`).

## Code style

- Форматтер — `black` (длина строки 88), линтер — `ruff`. Запускай перед завершением.
- Хэндлеры Telegram — async; тяжёлые вызовы Gemini оборачивай в `asyncio.to_thread` (см. `bot.py`).
- Пользовательские строки — на русском.
- Не добавляй комментарии, пересказывающие код.

## Architecture

```
main.py → bot.py (хэндлеры) → analyzer.py (VideoAnalyzer) → Gemini API
                                   ↑ prompts.py, formatting.py
config.py (.env), errors.py (сообщения об ошибках)
```

Сессия диалога хранится в `context.user_data[SESSION_KEY]` (в памяти процесса, теряется при перезапуске): `{"analysis": str, "history": [{"user", "assistant"}]}`.

## Project-specific gotchas

- **Python 3.9.** Синтаксис `str | None` не работает — используй `Optional[str]` из `typing`. Это уже ломало запуск.
- **Telegram не поддерживает markdown `##`.** Отчёты модели конвертируются в HTML через `formatting.markdown_to_html`; отправка идёт с `ParseMode.HTML` и fallback на plain text при `BadRequest`. Не переключай обратно на `ParseMode.MARKDOWN` для отчётов.
- **venv привязан к абсолютному пути.** При переносе/переименовании папки пересоздавай `.venv`.
- **Секреты.** `.env` с живыми токенами не коммить (он в `.gitignore`). Не выводи значения токенов.
- Видео скачивается во временный файл и удаляется в `finally` — сохраняй этот паттерн.

## Поведение агента (Karpathy + workflow)

1. **Думать до кода.** Проговаривай допущения, спрашивай при неоднозначности, показывай trade-off'ы.
2. **Простота.** Минимум кода под задачу, без спекулятивных абстракций.
3. **Хирургические правки.** Меняй только то, что требует задача; держи существующий стиль; не рефактори рабочее.
4. **Цель → верификация.** Перед «готово» докажи: прогон `pytest`/`ruff`, компиляция, вывод. Не помечай задачу выполненной без доказательства.
5. **План для нетривиального** (3+ шага или архитектура): сначала план, потом код; при отклонении — перепланируй.
6. **Багфикс автономно** в рамках L3-инфраструктуры (тесты + CI). Деструктивное и смену секретов — только с подтверждением.

## Commit / PR

- Коммить только по явной просьбе пользователя.
- Не коммить `.env`, `.venv/`, временные видео.
- Сообщения коммитов — кратко по сути изменения.
