# Agent Workflow Orchestration: Reference Extract (RU)

Reference extract in-session workflow паттернов для coding agents. Фокус на **как агент работает turn-by-turn**, отдельно от того как репозиторий сконфигурирован (`agent-readiness-ru.md`) и как агент думает (`agent-readiness-behavior-ru.md`).

**Источник:** опубликованный CLAUDE.md Boris Cherny. Boris это core engineer на Claude Code в Anthropic. Материал дополнен related published guidance из Claude Code docs чтобы файл работал self-contained как drop-in template.

**Trade-off note.** Правила склоняют к planning, verification и autonomy. Платят session latency взамен на меньше surprises, меньше rollback и compounding learning across sessions. Для one-shot тривиальных задач используй здравый смысл.

---

## Три слоя - recap

Этот документ это часть three-layer модели:

| Слой            | Файл                                | Что настраивает                                                  |
| --------------- | ----------------------------------- | ---------------------------------------------------------------- |
| Environment     | `agent-readiness-ru.md`             | Что репозиторий даёт агенту (configs, tests, docs, MCP).         |
| Behavior        | `agent-readiness-behavior-ru.md`    | Как агент думает (assumptions, simplicity, surgical edits).      |
| **Workflow**    | **`agent-readiness-workflow-ru.md`** | **Как агент работает в сессии (planning, subagents, lessons).** |

Нужны все три. Level 5 environment без behavior и workflow tuning всё равно даёт неровные результаты.

---

## Шесть workflow правил

### 1. Plan Mode Default

**Планируй до нетривиальной работы. Re-plan при отклонении.**

* Заходи в plan mode для ЛЮБОЙ нетривиальной задачи (3+ шага или architectural решения).
* Если что-то пошло не так, СТОП и re-plan немедленно.
* Используй plan mode и для шагов верификации, не только для построения.
* Пиши детальные specs upfront чтобы снизить ambiguity.

**Claude Code mechanics:** plan mode встроен. Цикл через `Shift+Tab`, или установи `defaultMode: "plan"` в `~/.claude/settings.json`. В plan mode у агента read-only tools и он создаёт план; ты approve до любого write.

### 2. Subagent Strategy

**Спавни subagents либерально чтобы main context был чистым.**

* Используй subagents либерально чтобы main context window был чистым.
* Offload research, exploration и parallel analysis на subagents.
* Для сложных проблем кидай больше compute через subagents.
* Один task на subagent для focused execution.

**Claude Code mechanics:** subagents живут в `.claude/agents/<name>.md` (project scope) или `~/.claude/agents/<name>.md` (user scope). У каждого свой context window. Опиши `description` чётко чтобы Claude роутил к правильному subagent автоматически. Restrict `tools:` per subagent до минимально нужной surface. См. Pillar 11 в `agent-readiness-ru.md` для полного subagent readiness чек-листа.

### 3. Self-Improvement Loop

**Захвати lessons после каждой коррекции. Читай их на старте сессии.**

* После ЛЮБОЙ коррекции от user обнови `tasks/lessons.md` с pattern.
* Напиши правила для себя которые предотвратят ту же ошибку.
* Безжалостно итерируй на этих lessons пока mistake rate не упадёт.
* Просматривай lessons на старте сессии для relevant проекта.

**Смысл:** инструкции агента улучшаются со временем по мере того как команда им пользуется. Коррекция это data; захвати её. Противоположность (забыть ту же коррекцию и получить её снова) самый дорогой failure mode для autonomous agents.

### 4. Verification Before Done

**Никогда не помечай задачу complete без доказательства что работает.**

* Никогда не помечай задачу complete без доказательства что работает.
* Diff поведение между main и твоими изменениями когда relevant.
* Спроси себя: "Would a staff engineer approve this?".
* Прогони тесты, проверь логи, продемонстрируй correctness.

**Mental check:** "Would a staff engineer approve this?". Если да, шипи. Если нет, ещё один проход. Если не уверен, верифицируй с evidence (test output, log line, diff).

### 5. Demand Elegance (Balanced)

**На нетривиальных изменениях паузу. Спроси есть ли более элегантный способ.**

* Для нетривиальных изменений пауза и вопрос "is there a more elegant way?".
* Если фикс feels hacky: "Knowing everything I know now, implement the elegant solution".
* Skip это для simple, obvious fixes. Не over-engineer.
* Challenge свою работу до представления.

**Trigger phrase:** "Knowing everything I know now, implement the elegant solution". Форсирует post-hoc rethink после первой working version. Первая версия часто раскрывает правильную форму; перестрой опираясь на это знание.

### 6. Autonomous Bug Fixing

**Дали bug report - просто фикси.**

* Когда дали bug report, просто фикси. Не проси hand-holding.
* Указывай на логи, ошибки, failing tests. Затем resolve их.
* Zero context switching от user'а.
* Иди фикси failing CI tests без указаний как.

**Boundary:** это предполагает Level 3+ environment (тесты gate'ят merge, CI падает громко, branch protection защищает от катастрофы). На Level 1 репо autonomous fixing небезопасен.

---

## Конвенция Task Management

Два файла в репе в `tasks/`:

### `tasks/todo.md`

Checkable items для текущей задачи. Workflow:

1. **Plan First.** Запиши план в `tasks/todo.md` с checkable items.
2. **Verify Plan.** Check-in с user'ом до начала имплементации.
3. **Track Progress.** Помечай items complete по мере работы.
4. **Explain Changes.** High-level summary на каждом шаге.
5. **Document Results.** Добавь review секцию в `tasks/todo.md` в конце.

### `tasks/lessons.md`

Persistent learning across tasks. Workflow:

6. **Capture Lessons.** Обнови `tasks/lessons.md` после corrections, с pattern и правилом которое предотвращает recurrence.

**Почему два файла:** `todo.md` per-task и short-lived. `lessons.md` это compounding knowledge base который растёт с командой. Первое это execution; второе это память.

---

## Core Principles

Три принципа под всеми шестью workflow правилами:

* **Simplicity First.** Делай каждое изменение настолько простым насколько возможно. Влияй на минимум кода.
* **No Laziness.** Находи root causes. Никаких temporary fixes. Стандарты senior developer.
* **Minimal Impact.** Трогай только то что необходимо. Никаких side effects, никаких новых багов.

Пересекаются с принципами Karpathy в `agent-readiness-behavior-ru.md` (`Simplicity First` shared verbatim; `Minimal Impact` это то же что Karpathy `Surgical Changes`; `No Laziness` расширяет Karpathy `Goal-Driven Execution` с позицией root-cause). Документы усиливают друг друга.

---

## Как применять

Три варианта от чистого к более адаптированному:

### Вариант A. Дроп verbatim

Скопировать целиком секции `## Workflow Orchestration`, `## Task Management` и `## Core Principles` в `CLAUDE.md` или `AGENTS.md` проекта. Агент будет читать их на каждой сессии.

Цена: ~50 строк в context файле на каждой сессии. Стоит если команда ценит консистентность и агент это main contributor.

### Вариант B. Слить с существующим context файлом

Если у проекта уже есть `CLAUDE.md` / `AGENTS.md` с project-specific правилами, append workflow rules под clearly-named секцией:

```markdown
## Workflow Orchestration

(Шесть правил из этого документа.)

## Task Management

(Convention из этого документа. Адаптируй пути файлов если нужно.)

## Core Principles

(Три принципа.)
```

Держи project-specific правила в их собственной секции чтобы workflow конвенции оставались портативными.

### Вариант C. Адаптировать под реальность команды

Часть этих правил уже могут существовать под другими именами:

* "Plan first, confirm, then act" правила из playbook команды маппят на **Plan Mode Default**.
* Директория `memory/lessons_*.md` или эквивалент маппит на **Self-Improvement Loop**.
* Pre-commit / pre-merge hook который падает на uncovered code маппит на **Verification Before Done**.
* Явная policy на что агент может автономно фиксить (formatter changes, dependency bumps) vs что требует human review это **bounded** версия **Autonomous Bug Fixing**.

Для этих вариантов держи что есть. Добавь только части которые не покрыты. Trim части которые конфликтуют с более сильными team norms (например "Autonomous Bug Fixing" не должно override'ить "no agent commits on customer-facing repos" правило).

---

## Related Anthropic Guidance

Шесть правил выше опираются на эти Claude Code primitives. Прочитай один раз если правила незнакомы:

* [Plan mode in Claude Code](https://code.claude.com/docs/en/plan-mode): read-only thinking до любого write, approval gate перед execution, `Shift+Tab` чтобы цикл.
* [Subagents](https://code.claude.com/docs/en/sub-agents): `.claude/agents/<name>.md` definitions, tool allowlists, model selection per agent, automatic routing по `description`.
* [Hooks](https://code.claude.com/docs/en/hooks): enforce verification детерминированно (`PreToolUse`, `PostToolUse`, `SessionEnd`, `Stop`).
* [Slash commands и skills](https://code.claude.com/docs/en/slash-commands): захвати recurring workflows чтобы тот же prompt firing каждый раз.
* [Settings reference](https://code.claude.com/docs/en/settings): `defaultMode: "plan"`, `permissions`, `env`, `teammateMode`.

---

## Как это маппит на `agent-readiness-ru.md`

| Правило Boris Cherny      | Pillar в `agent-readiness-ru.md`                     | Что добавляется в чек-лист                                            |
| ------------------------- | ---------------------------------------------------- | --------------------------------------------------------------------- |
| Plan Mode Default         | Pillar 10 (Agent Tooling & Interfaces)               | L3: context файл документирует policy запуска plan-mode.              |
| Subagent Strategy         | Pillar 11 (Multi-Agent Coordination)                 | L2-L3: subagents определены, tool allowlists scoped, dispatch документирован. |
| Self-Improvement Loop     | Pillar 4 (Documentation & Agent Context) + Pillar 10 | L3: lessons capture convention документирована в context файле.       |
| Verification Before Done  | Pillar 3 (Testing) + Pillar 10                       | L3: агент должен демонстрировать correctness с evidence.              |
| Demand Elegance           | Pillar 10                                            | L4: правило post-hoc rethink документировано для нетривиальных изменений. |
| Autonomous Bug Fixing     | Pillar 7 (Security & Governance) + Pillar 10        | L4: явная policy что агент может фиксить автономно.                   |

Framework треатит эти как `AGENTS.md` / `CLAUDE.md` контент под Pillar 10 (и частично Pillars 4, 11, 3, 7). Этот документ это off-the-shelf default для того контента.

---

## Attribution

Оригинальный CLAUDE.md от Boris Cherny (Anthropic). Расширен здесь related guidance из Claude Code docs. Использовать в том же духе что и любой public engineering writeup: бери что работает, адаптируй остальное, ссылайся на источник.
