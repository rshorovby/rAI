# HTTP-контракт канала iOS

Источник: `PRODUCT_IOS.md`, lock rallyiOS 18–35. IAP/проверка чеков **не входят**.

База: `/v1`. Авторизация: `Authorization: Bearer <opaque token>` (кроме `POST /v1/auth/apple`).  
Процесс: тот же, что бот. Снаружи: nginx + TLS на том же Droplet.

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
| GET | `/v1/jobs` | `?open=1` — незакрытые; иначе доставленные. |
| GET | `/v1/jobs/{id}` | Заявка + `markdown` / `scores` / `focus` / `drills` / `stroke`. |
| GET | `/v1/progress` | Ряды scores, как `/progress`. |
| POST | `/v1/device-tokens` | Тело: `token`. APNs. |

## Правила

- Пустой iOS = нет `review_jobs` и нет `player_sessions`. Иначе Telegram→iOS — 409.
- Cancel открытых заявок при новом видео из бота — только `source_channel=telegram`.
- Отчёт в JSON: markdown + разобранные поля, не HTML.
