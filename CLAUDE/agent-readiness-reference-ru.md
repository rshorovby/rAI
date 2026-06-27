# Agent Readiness: Reference Extract

Reference extract публичного материала по модели Agent Readiness. Wording близок к оригиналу.

**Disclaimer.** Несколько разделов оригинального источника находятся внутри interactive accordions: описания pillars и описания levels. В статической версии страницы expanded только **Style & Validation** (pillar) и **Level 3: Standardized** (level). Остальные pillars (Build System, Testing, Documentation, Dev Environment, Code Quality, Observability, Security & Governance) и остальные levels (1, 2, 4, 5) упоминаются по имени, но их полные descriptions недоступны в публично достижимом HTML. Где описаний нет, помечено как `[collapsed in source]`. Список pillars немного отличается между ранним announcement (8 pillars) и расширенными docs (9 pillars); показаны оба.

---

## Part A. Framework Introduction

### Introducing Agent Readiness

> A framework for measuring and improving how well your codebase supports autonomous development. Evaluate repositories across eight technical pillars and five maturity levels.

> Run `/readiness-report` to see where you stand across eight technical pillars and five maturity levels, with specific recommendations for what to fix first.

### The invisible bottleneck

> Teams deploying AI coding agents often see uneven results. They blame the model, try a different agent, get the same thing. The real problem is usually the codebase itself.

> The agent is not broken. The environment is. Missing pre-commit hooks mean the agent waits ten minutes for CI feedback instead of five seconds. Undocumented environment variables mean the agent guesses, fails, and guesses again. Build processes requiring tribal knowledge from Slack threads mean the agent has no idea how to verify its own work.

> These are environment problems, not agent problems. And they compound. A codebase with poor feedback loops will defeat any agent you throw at it. A codebase with fast feedback and clear instructions will make any agent dramatically more effective.

### What we measure (Eight Technical Pillars)

> Agent Readiness evaluates repositories across eight technical pillars. Each one addresses a specific failure mode we have observed in production deployments.

#### Style & Validation (expanded)

> Linters, type checkers, formatters. Automated tools that catch bugs instantly. Without them, agents waste cycles on syntax errors and style drift that could be caught in seconds.

Examples:
- ESLint / Biome
- TypeScript strict mode
- Prettier / Black

**Without this:** Agent submits code with formatting issues, waits for CI, fixes blindly, repeats.

#### Build System

`[collapsed in source; в announcement только имя pillar. См. Part B для docs description.]`

#### Testing

`[collapsed in source]`

#### Documentation

`[collapsed in source]`

#### Dev Environment

`[collapsed in source]`

#### Code Quality

`[collapsed in source. Этот pillar есть в announcement, но НЕТ в docs overview, где в той же полосе перечислены "Debugging & Observability" и "Task Discovery".]`

#### Observability

`[collapsed in source]`

#### Security & Governance

`[collapsed in source]`

### Five Maturity Levels

> Repositories progress through five levels. Each level represents a qualitative shift in what autonomous agents can accomplish.

#### Level 1: Functional

`[collapsed in source. См. Part B для docs definition.]`

#### Level 2: Documented

`[collapsed in source]`

#### Level 3: Standardized (expanded)

> Production-ready for agents. Clear processes defined and enforced. Minimum bar for production-grade autonomous operation.

**Key Signals:**

- E2E tests exist
- Docs maintained
- Security scanning
- Observability

**Agent Capability:** Routine maintenance: bug fixes, tests, docs, dependency upgrades.

**Examples:** FastAPI, GitHub CLI, pytest.

> Level 3 is the target. Most teams should aim here first.

#### Level 4: Optimized

`[collapsed in source]`

#### Level 5: Autonomous

`[collapsed in source]`

### See it in action

> Agent Readiness reports have been published for popular open source projects:

| Проект        | Язык        | Level | Score |
| ------------- | ----------- | ----- | ----- |
| CockroachDB   | Go          | L4    | 74%   |
| FastAPI       | Python      | L3    | 53%   |
| Express       | TypeScript  | L2    | 28%   |

> The contrast is instructive. CockroachDB at Level 4 has extensive CI, comprehensive testing, clear documentation, and security scanning. Express at Level 2 lacks several foundational signals. Both are successful, widely-used projects. But an agent will have a much easier time contributing to CockroachDB.

### How to use it

**CLI: `/readiness-report`**

> Run `/readiness-report` in the CLI to evaluate any repository. The report shows your current level, which criteria pass and fail, and prioritized suggestions for what to fix first.

**Dashboard: Organization view**

> View your organization's readiness scores in the dashboard. Track progress over time, see the distribution of repositories across maturity levels, and identify which active repositories need attention.

> The dashboard surfaces your lowest-scoring active repositories (those with commits in the last 90 days) with specific remediation suggestions.

**API: Programmatic access**

> Access reports via the Readiness Reports API to integrate with existing tooling. Run readiness checks in CI/CD, build custom dashboards, or set up alerting when scores drop below thresholds.

### Consistent evaluations

> Agent Readiness evaluates 60+ criteria using LLMs, which introduces a challenge: non-determinism. Before the fix, variance averaged 7% with spikes to 14.5%. After grounding, "variance dropped to 0.6% and has stayed there for six weeks across 9 benchmark repositories spanning low, medium, and high readiness tiers."

### How scoring works

> Each criterion is binary: pass or fail. Most signals are file existence checks or configuration parsing.

> To unlock a level, you must pass 80% of criteria from that level and all previous levels.

> At the organization level, the metric tracked is the percentage of active repositories that reach Level 3 or higher.

### Automated remediation

> When you run a readiness report, you can kick off automated remediation from the CLI or dashboard. This spins up an agent that opens a pull request to fix failing criteria: adding missing files like AGENTS.md, configuring linters, setting up pre-commit hooks.

> After fixes are applied, re-run the readiness check to validate and refresh your score.

### The compounding effect

> The work compounds. Better environments make agents more productive. More productive agents handle more work. That frees up time to improve environments further.

> "Teams that measure this and systematically improve will pull ahead of teams that do not. The gap will widen."

> A more agent-ready codebase improves the performance of all software development agents.

---

## Part B. Overview

### Description

> The Agent Readiness Model helps organizations measure their progress toward autonomous software development.

### Пять уровней (формулировки docs)

| Level | Name         | Description                                                                                |
| ----- | ------------ | ------------------------------------------------------------------------------------------ |
| 1     | Functional   | Код запускается, но setup ручной, automated validation отсутствует.                        |
| 2     | Documented   | Базовая документация и процессы есть. Workflow зафиксирован письменно.                     |
| 3     | Standardized | Чёткие процессы определены, документированы, и enforced через автоматизацию.               |
| 4     | Optimized    | Быстрые feedback loops и data-driven improvement. Системы спроектированы для productivity. |
| 5     | Autonomous   | Системы самоулучшающиеся со sophisticated orchestration.                                   |

### Scoring Mechanism

> To unlock a level, you must pass **80% of the criteria** from the previous level.

### Девять technical pillars (формулировки docs)

Expanded docs перечисляют **девять** pillars (на один больше чем в раннем announcement). Mapping ниже: имя pillar, one-line description, и примеры criteria. "Code Quality" из announcement в docs отсутствует; docs добавляют "Task Discovery" и "Product & Experimentation".

#### 1. Style & Validation

> Linters, type checkers, and formatters.

Примеры criteria:
- Linter configuration
- Type checker
- Code formatter
- Pre-commit hooks

#### 2. Build System

> Deterministic compilation and verification.

Примеры criteria:
- Build command documented
- Dependencies pinned
- VCS CLI tools

#### 3. Testing

> Unit and integration test feedback loops.

Примеры criteria:
- Unit tests exist
- Integration tests exist
- Tests runnable locally

#### 4. Documentation

> AGENTS.md, README, setup instructions.

Примеры criteria:
- AGENTS.md
- README
- Documentation freshness

#### 5. Development Environment

> Reproducible, consistent setups.

Примеры criteria:
- Devcontainer
- Environment template
- Local services setup

#### 6. Debugging & Observability

> Structured logging and tracing.

Примеры criteria:
- Structured logging
- Distributed tracing
- Metrics collection

#### 7. Security

> Branch protection, secret scanning, code owners.

Примеры criteria:
- Branch protection
- Secret scanning
- CODEOWNERS

#### 8. Task Discovery

> Issue templates and structured workflows.

Примеры criteria:
- Issue templates
- Issue labeling system
- PR templates

#### 9. Product & Experimentation

> Analytics and measurement infrastructure.

Примеры criteria:
- Product analytics instrumentation
- Experiment infrastructure

### Evaluation Scopes

* **Repository scope.** Одна оценка на репозиторий (пример: branch protection enabled).
* **Application scope.** Per-application оценка в monorepos (пример: "3 / 4 apps pass linting").

### Access Methods

В docs перечислено четыре способа взаимодействия:

1. CLI (`/readiness-report` slash command)
2. Web Dashboard (Agent Readiness dashboard view)
3. API (Readiness Reports API)
4. Remediation (automated fixes, marked "coming soon")

---

## Part C. CLI Reference

### Command Syntax

```text
> /readiness-report
```

### Prerequisites

> Включить feature в `/settings` → `Experimental` → `Readiness Report`.

### Evaluation Process

Команда выполняет следующие шаги:

1. **Language Detection.** Определяет языки репозитория (JavaScript/TypeScript, Python, Rust, Go, Java, Ruby) по configuration files и source code.
2. **Sub-application Discovery.** Определяет monorepo vs single service; идентифицирует независимо deployable applications.
3. **Criteria Evaluation.** Проверяет criteria по всем пяти maturity levels.
4. **Report Storage.** Сохраняет evaluation results для dashboard visualization.
5. **Summary Output.** Печатает human-readable отчёт с результатами.
6. **Remediation.** Coming soon; опция автоматического fix для failing criteria.

### Output Structure

**Level Achieved (1-5)**

- **Level 1: Functional.** Базовый tooling на месте.
- **Level 2: Documented.** Процесс и документация установлены.
- **Level 3: Standardized.** Security и observability сконфигурированы.
- **Level 4: Optimized.** Быстрый feedback и continuous measurement.
- **Level 5: Autonomous.** Self-improving systems.

**Applications Discovered.** Перечисляет каждое application с описанием (только monorepos).

**Criteria Results Format.** Формат score: `numerator/denominator`:

- Numerator: sub-applications прошедшие criterion.
- Denominator: sub-applications оценённые.

Пример criterion output:

```text
**Style & Validation**
- Linter Configuration: 2/2 - ESLint configured in both applications
- Type Checker: 2/2 - TypeScript strict mode enabled
- Pre-commit Hooks: 0/1 - No husky or lint-staged configuration found
```

**Action Items.** "2-3 highest-impact recommendations to reach the next level."

### Additional Features

- Историю отчётов можно просмотреть в web dashboard.
- Track progression, compare across repos, share with the team.
- Рекомендация: запускать периодически после крупных infrastructure changes.

---

## Part D. Dashboard Reference

### Page Description

> The Agent Readiness dashboard provides a centralized view of your organization's readiness scores across all repositories, with historical trends and detailed breakdowns.

### Navigation Path

> Settings → Analytics → Agent Readiness.

### Summary Cards

Три top-level метрики:

| Метрика                 | Определение                                                                           |
| ----------------------- | ------------------------------------------------------------------------------------- |
| Organization Score      | Average readiness level across all measured repositories (rounded down).              |
| Repositories Tracked    | Number of repositories with readiness reports vs. total enabled repositories.         |
| Last Updated            | Time since the most recent readiness evaluation.                                      |

### Progress Graph

> A time-series chart showing your organization's readiness level over time.

Filters: `7d`, `1m`, `6m`, `1y`, `all`.

### Repositories Table

> A searchable, paginated table of all repositories.

Колонки:

- Repository name (кликабельно для деталей).
- Level (1-5 readiness scale).
- Progress (percentage toward next level).
- Last Update (evaluation timestamp).

### Repository Detail Page

**Header.** Показывает имя репо, текущий level, время последней evaluation, и refresh.

**Level Accordions.** Каждый readiness level (Functional через Autonomous) имеет expandable accordion.

**Criterion Rows.** Каждая строка показывает:

- Name (оценённый criterion).
- Score в формате `[X/Y]`.
- Status (pass/fail индикатор).
- Rationale (expandable объяснение).

**Coming feature.** "Soon, failing criteria will display a Fix button that triggers automated remediation."

### Refresh Methods

- **Web dashboard.** Перейти на repository detail page и кликнуть **Refresh**.
- **CLI.** Запустить `/readiness-report` slash command в директории репозитория.

### Metrics Calculations

- **Organization Level.** Среднее всех repository levels, rounded down.
- **Repository Level.** 80% threshold system, где каждый следующий level разблокируется при выполнении этого критерия.

### Best Practices (по docs)

- Проводить evaluations после infrastructure changes.
- Закрывать failures текущего level до перехода на следующий.
- Мониторить тренды через progress graph.
- Приоритизировать high-impact improvements из CLI reports.

---

## Part E. API Reference

### Authentication

> Все запросы требуют: `Authorization: Bearer <api-key>`.

> API keys генерируются в settings (раздел API keys).

### Endpoint: List Readiness Reports

**GET** `/api/organization/maturity-level-reports`

#### Query parameters

| Параметр       | Type    | Required | Description                                                  |
| -------------- | ------- | -------- | ------------------------------------------------------------ |
| `repoId`       | string  | No       | Фильтр reports по repository ID.                             |
| `limit`        | integer | No       | Максимум reports на возврат (должен быть positive).          |
| `startAfter`   | string  | No       | Report ID как pagination cursor.                             |

#### Response schema

```json
{
  "reports": [
    {
      "reportId": "string (UUID)",
      "createdAt": "number (Unix ms)",
      "repoUrl": "string",
      "apps": { "path": { "description": "string" } },
      "report": {
        "criterionId": {
          "numerator": "number",
          "denominator": "number",
          "rationale": "string"
        }
      },
      "commitHash": "string?",
      "branch": "string?",
      "hasLocalChanges": "boolean?",
      "hasNonRemoteCommits": "boolean?",
      "modelUsed": {
        "id": "string",
        "reasoningEffort": "string (low|medium|high|off)"
      },
      "agentVersion": "string?"
    }
  ]
}
```

#### Example request

```bash
curl -X GET "<host>/api/organization/maturity-level-reports?limit=10" \
  -H "Authorization: Bearer <api-key>"
```

### Error responses

| Status | Meaning                              |
| ------ | ------------------------------------ |
| 400    | Invalid request parameters.          |
| 401    | Missing or invalid API key.          |
| 500    | Internal server error.               |

**Rate limits.** В публичной документации не упомянуты.

---

## Reconciliation Notes

### Pillar count mismatch (8 vs 9)

Initial announcement говорит **восемь technical pillars**, перечисляя эти восемь имён:

1. Style & Validation
2. Build System
3. Testing
4. Documentation
5. Dev Environment
6. Code Quality
7. Observability
8. Security & Governance

Expanded docs перечисляют **девять pillars** со слегка другими именами:

1. Style & Validation
2. Build System
3. Testing
4. Documentation
5. Development Environment
6. Debugging & Observability
7. Security
8. Task Discovery
9. Product & Experimentation

Различия:

- **Code Quality** только в announcement; в docs его нет.
- **Task Discovery** и **Product & Experimentation** только в docs.
- **Observability** в announcement в docs стало **Debugging & Observability**.
- **Security & Governance** в announcement в docs стало **Security**.

Наиболее вероятное объяснение: announcement это раннее framing фреймворка; docs это live, расширенная версия. Docs это authoritative current model.

### Scoring rule consistency

Оба источника говорят: **binary pass/fail per criterion**, **80% criteria для unlock уровня**. Organization-level metric описан в двух разных видах: "the percentage of active repositories that reach Level 3 or higher" и "average of all repository levels, rounded down". Это два разных aggregations в разных views; оба валидны в своём контексте.

### Counting criteria

Модель оценивает **60+ criteria using LLMs**. Docs их не перечисляют. Они surface в CLI output и в dashboard repository-detail accordions, где каждый строка с `[X/Y]` score и rationale.

---

## Что источник НЕ покрывает

Для полноты: следующее не описано ни в одной из публичных страниц и требует либо доступа к продукту, либо дополнительной internal documentation:

- Полный список всех 60+ criteria с точными определениями.
- Точное распределение criterion по уровням (какой принадлежит L1 vs L2 vs L3 и т.д.).
- Точный LLM grounding подход, снизивший variance с 7% до 0.6%.
- Per-language подстройки criteria (CLI определяет JS/TS, Python, Rust, Go, Java, Ruby).
- Как application-scope (monorepo) thresholds композируются в repo-level score в edge cases.

---

## Как этот документ соотносится с `agent-readiness-ru.md`

Companion файл `agent-readiness-ru.md` в этой директории берёт модель выше и расширяет:

- Явный десятый pillar ("Agent Tooling & Interfaces") покрывающий CLAUDE.md, AGENTS.md, MCP, hooks, skills и subagents, которые source модель трактует implicitly внутри Documentation.
- Явный одиннадцатый pillar ("Multi-Agent Coordination") для subagents, worktrees и agent teams readiness.
- Явные per-level чек-листы для каждого pillar (source не публикует полный criteria-to-level mapping).
- Опциональный organizational layer ("5 Shifts"), которого нет в source.
- Capability-gating таблица, mapping типов задач агента к минимальному readiness level.

Этот документ это unmodified source content для reference. Другой файл это extended working framework.
