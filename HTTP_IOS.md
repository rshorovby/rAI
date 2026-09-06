# HTTP-контракт канала iOS

Источник: `PRODUCT_IOS.md`, lock rallyiOS 18–35. IAP/проверка чеков **не входят**.

База: `/v1`. Авторизация: `Authorization: Bearer <opaque token>` (кроме `POST /v1/auth/apple`).  
Процесс: тот же, что бот. Снаружи: nginx + TLS на том же Droplet.

Публичный хост (пока нет своего домена): `https://rallymind.64.227.74.21.sslip.io`  
Включить на VPS: `sudo bash /home/rallyai/rAI/deploy/enable_http.sh`  
`APPLE_BUNDLE_ID` должен совпадать с bundle приложения (`com.rakets.rallymind`).

## Эндпоинты

| Метод | Путь | Назначение |
|-------|------|------------|
| POST | `/v1/auth/apple` | Sign in with Apple. Тело: `identity_token`, опционально `language_code`. Ответ: `token`, `player_id`, `telegram_linked`. |
| GET | `/v1/me` | Профиль канала: `player_id`, `telegram_linked`, `language_code`. |
| POST | `/v1/me/logout` | Удалить текущий токен. |
| DELETE | `/v1/me` | Удалить аккаунт (`player_id` и привязки). |
| POST | `/v1/link/telegram` | Код из бота (`/link`) → привязка к пустому iOS. Тело: `code`. |
| POST | `/v1/link/app-code` | Код из приложения для пустого Telegram. Ответ: `code`, `expires_in`. |
| POST | `/v1/jobs` | multipart: `video` + `stroke` + `look` + `comment` + `language_code`. `source_channel=ios`. Не cancel других iOS-заявок. |
| GET | `/v1/jobs` | `?open=1` — `queued` / `in_review` / `ai_sent`. Иначе `ai_sent` / `sent_coach` / `sent_fallback`. |
| GET | `/v1/jobs/{id}` | Заявка + `markdown` / `scores` / `focus` / `drills` / `stroke`. |
| GET | `/v1/dossier` | Покрытие игрока и 6 сегментов: pending / committed, слоты, `next_to_film`, `goals_unlocked`. |
| GET | `/v1/progress` | Ряды scores, как `/progress`. |
| POST | `/v1/device-tokens` | Тело: `token`. APNs. |

## Правила

- Пустой iOS = нет `review_jobs` и нет `player_sessions`. Иначе Telegram→iOS — 409.
- Cancel открытых заявок при новом видео из бота — только `source_channel=telegram`.
- Отчёт в JSON: markdown + разобранные поля, не HTML. `markdown` = `final_text` или `draft_text` (AI игроку сразу, lock rallyiOS #40/#53).
- `ai_sent` — разбор уже у игрока, супервизия в Forum ещё не канон. В обоих списках, пока нет `sent_coach` / `sent_fallback`.
- Заявка содержит `coverage.contributions` (слоты этого job). Покрытие пишется в `enqueue_review` с любого канала; `bot.py` не меняется.
