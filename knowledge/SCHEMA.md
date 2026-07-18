---
type: schema
title: RallyAI Knowledge Schema
description: Rules for maintaining the tennis technique wiki (LLM Wiki + OKF-lite).
tags: [schema, meta]
status: reviewed
timestamp: 2026-07-17T00:00:00Z
---

# SCHEMA — как вести semantic layer

Этот файл — контракт для агента (Cursor / Codex). Человек курирует источники и задаёт вопросы; агент делает bookkeeping.

## Типы страниц (`type` в frontmatter)

| type | Папка | Пример |
|------|--------|--------|
| `source` | `wiki/sources/` | summary одной статьи / клипа |
| `stroke` | `wiki/strokes/` | forehand, serve |
| `concept` | `wiki/concepts/` | contact-point, split-step |
| `error` | `wiki/errors/` | late-contact |
| `drill` | `wiki/drills/` | упражнение (позже + video id) |
| `moc` | корень / `wiki/` | карта содержания |
| `meta` | корень | index, log, schema |

## Обязательный frontmatter (OKF-lite)

```yaml
---
type: concept
title: Human-readable title
description: One-line summary for index/agents.
tags: [forehand, contact]
status: unverified   # unverified | reviewed | disputed
sources: []          # links to wiki/sources/* or raw/*
timestamp: ISO-8601
---
```

- `status: unverified` — нельзя цитировать в промпте бота как «эталон», пока не `reviewed`.
- Сырьё в `raw/` **immutable**. Правки только через новые файлы / версии в `wiki/`.

## Ingest (новый источник)

1. Положить оригинал или markdown в `raw/inbox/` (или `raw/<topic>/`).
2. Создать `wiki/sources/<slug>.md` — summary + ключевые claims + ссылка на raw.
3. Обновить связанные `stroke` / `concept` / `error` (дописать, не затирать без пометки).
4. При противоречии со старым — секция `## Contradictions` + `status: disputed` или заметка в [[open-questions]].
5. Обновить [[index]] и append в [[log]].

Один источник может тронуть 5–15 страниц. Лучше ingest **по одному** с ревью человека.

## Query

1. Читать [[index]] → выбрать страницы.
2. Отвечать со ссылками `[[wikilinks]]` и `status`.
3. Ценный синтез (сравнение, чеклист) можно сохранить как новую wiki-страницу **только если** опирается на sources; иначе — в chat / `scratch/` (не в wiki).

## Lint (периодически)

- orphans (нет inbound links);
- `unverified` старше N дней;
- contradictions между pages;
- concepts упомянуты, но без своей страницы;
- drills без связи с error/stroke.

## Связь с ботом RallyAI

Промпт анализа (фаза RAG): подмешивать **reviewed** страницы по удару из intake (`forehand` → [[forehand]] + связанные concepts/errors).  
Не подмешивать сырой `raw/` целиком.  
Drills library позже: `type: drill` + `telegram_file_id` в frontmatter.

## Именование файлов

- kebab-case: `contact-point.md`, `late-contact.md`
- Один concept = один файл
- Wikilinks: `[[contact-point]]`, `[[forehand]]`
