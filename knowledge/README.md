# RallyAI Knowledge Vault (Obsidian + LLM Wiki + OKF-lite)

Открой эту папку в Obsidian: **File → Open folder as vault** → выбери `knowledge/`.

## Слои

| Путь | Роль |
|------|------|
| `raw/` | Неизменяемые источники (статьи, PDF→md, клипы). LLM **не** правит. |
| `wiki/` | Скомпилированное знание: удары, концепции, ошибки, drills. Пишет LLM (+ вы курируете). |
| `SCHEMA.md` | Правила ingest / query / lint для агента. |
| `index.md` | Каталог всех страниц (обновлять при ingest). |
| `log.md` | Хронология операций (append-only). |

Паттерн: [Karpathy LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f).  
Формат страниц: OKF-lite (YAML frontmatter: `type`, `title`, `description`, `tags`, `status`, `timestamp`).

## Быстрый старт

1. Кидайте ссылки/файлы в `raw/inbox/` (или скажите агенту ingest).
2. Агент читает `SCHEMA.md` → пишет summary в `wiki/sources/` → обновляет entity/concept pages → `index.md` + `log.md`.
3. В боте позже: подмешивать релевантные `wiki/**` страницы в промпт (не сырой PDF).

Векторный RAG — следующий шаг, когда страниц станет много; сначала копим wiki.
