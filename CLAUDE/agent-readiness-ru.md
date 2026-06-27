# AI Agent Readiness Assessment (RU)

Модель зрелости и self-assessment чек-лист для оценки готовности репозитория к работе с автономными AI coding agents (Claude Code, Codex, Gemini CLI, Cursor, Aider, Devin, Factory Droid, Copilot и аналогичные).

Этот документ одновременно:

1. **Модель**: измерения по которым судят agent-readiness.
2. **Инструмент**: pass/fail criteria по которым можно скорить репу.

Основано на Claude Code best practices от Anthropic и multi-agent guidance, дополнено документацией OpenAI Codex и Google Gemini, открытым стандартом AGENTS.md, organizational guidance от Scaled Agile, и опубликованной моделью Factory.ai Agent Readiness. Все источники в appendix.

---

## Почему это важно

Агенты ломаются не случайно. Они ломаются предсказуемо: когда нет способа верифицировать работу, когда контекст живёт только в голове, когда feedback loops медленные, когда environment не reproducible, когда действие destructive и необратимое.

Готовая репа имеет tight feedback loops, явный контекст, и safe defaults. Агенты в таких репозиториях закрывают issue, пишут тесты, апгрейдят dependencies, обрабатывают routine maintenance без supervision. Агенты в неготовых репах жгут циклы на tribal knowledge, блокируются на environment setup, и shipпят plausible-looking код, который реально не работает.

Модель калибрована так что **Level 3 ("Standardized")** это минимальная планка для того чтобы агент мог merge-ить код без надзора на routine задачах. Большинство команд должны целиться сюда сначала, потом подниматься.

---

## Part 1. Maturity Model

Пять уровней. Репозиторий проходит их по порядку. Каждый уровень это качественный сдвиг в том, что агенту можно доверить.

| Level | Name           | Постура                                                                                                                                  | Что агент может делать здесь                                                                                                |
| ----- | -------------- | ---------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| **1** | Functional     | Код компилируется и работает, но setup ручной, валидация ad hoc, контекст в головах.                                                     | Генерировать сниппеты и отвечать на вопросы. Каждое изменение нужно человеку верифицировать и мержить.                       |
| **2** | Documented     | Базовая документация и скрипты есть. Агент может найти build command и прогнать тесты, но покрытие patchy, enforcement отсутствует.       | Делать ограниченные single-file изменения под review человека. Стиль pair-programming.                                       |
| **3** | Standardized   | Процессы определены, документированы, и enforced через автоматизацию. Тесты, linters и security checks бегут на каждом изменении.        | **Routine autonomous work**: bug fixes, refactor, dependency upgrade, doc updates, добавление тестов. PR готовы к review.   |
| **4** | Optimized      | Быстрые feedback loops, structured observability, measurable performance. Агенты получают качественный сигнал за секунды, не минуты.     | Multi-file features, performance-aware changes, on-call triage с telemetry context.                                          |
| **5** | Autonomous     | Самоулучшающиеся системы. У агентов orchestration, evaluation harnesses, experimentation infrastructure и clear safety boundaries.        | End-to-end feature delivery, A/B experiments, incident response, fleet-wide upgrades. Человек ревьюит policy, а не каждый diff. |

**Цель для большинства команд: Level 3.** Переход с L1 на L3 разблокирует большую часть value. L4 и L5 это оптимизации с убывающей отдачей.

### Capability gating

Эти rules of thumb связывают задачу для агента с минимальным уровнем зрелости, на котором её стоит пробовать:

| Задача                                                                | Min level |
| --------------------------------------------------------------------- | --------- |
| Задавать вопросы, объяснять код, предлагать изменения                 | L1        |
| Делать single-file change под review человека                         | L2        |
| Исправить баг, добавить тест, апгрейд dependency, написать docs       | L3        |
| Залендить multi-file feature, отрефакторить модуль                    | L4        |
| Вести open-ended инициативу, multi-day работа, autonomous triage     | L5        |

---

## Part 2. Scoring Method

Модель намеренно простая чтобы команда могла прогнать assessment за один заход.

### Per-pillar score

Каждый pillar имеет чек-лист, сгруппированный по уровням. Pillar получает **высший уровень, для которого минимум 80% пунктов прошли**.

* Каждый item бинарный: pass или fail. Частичный кредит не даётся.
* Если меньше 80% items уровня L*N* прошли, pillar остаётся на L*N-1*.
* L1 это пол. Если L1 items проваливаются, чинить надо это первым; pillar в "Pre-Functional".

### Repository score

Общий уровень репозитория это **минимум по всем pillars**. Один слабый pillar капает всю репу.

Используй **среднее** как secondary signal чтобы видеть куда движешься, но **минимум** это то, что gating'ует автономность агента: агенты ломаются на самом слабом измерении первыми.

### Repository vs application scope

Некоторые criteria repo-wide (branch protection, README). Другие применяются per-application в monorepo (linter config, test command, devcontainer). Скорь per-application criteria как "**N из M** apps прошли" и требуй 80% чтобы засчиталось.

### Как запускать assessment

Три варианта от менее к более автоматизированному:

1. **Manual pass.** Пройти Part 3 с tech lead. Отметить каждый пункт. Час на маленькую репу, полдня на сложный monorepo.
2. **Agent-driven pass.** Положить этот документ в репу и запустить `claude -p "Score this repo against agent-readiness-ru.md and produce a filled checklist with evidence (file paths, command outputs)"`. Просмотреть и скорректировать.
3. **CI-integrated pass.** Конвертировать бинарные criteria в shell/CI checks бегущие на каждом PR. Трекать score через время. Инструменты, делающие это нативно: Factory.ai `/readiness-report`; эквивалентный custom tooling прост.

**Re-assess раз в квартал**, и каждый раз при крупном architectural change.

---

## Part 3. Pillars

Одиннадцать pillars всего. Первые девять покрывают codebase environment (style, build, testing, docs, dev env, observability, security, task discovery, product). Последние два ("Agent Tooling & Interfaces" и "Multi-Agent Coordination") покрывают agent-specific surface area, которую большинство опубликованных maturity models трактуют implicitly.

### Pillar map

| #  | Pillar                                                  | Что измеряет                                                |
| -- | ------------------------------------------------------- | ----------------------------------------------------------- |
| 1  | [Style & Validation](#1-style--validation)              | Static signal: linting, types, formatting.                  |
| 2  | [Build System](#2-build-system)                         | Reproducible, deterministic builds.                         |
| 3  | [Testing](#3-testing)                                   | Automated verification на нескольких уровнях.              |
| 4  | [Documentation & Agent Context](#4-documentation--agent-context) | Written context, который агент может реально загрузить.    |
| 5  | [Development Environment](#5-development-environment)   | Reproducible local и CI environments.                      |
| 6  | [Debugging & Observability](#6-debugging--observability) | Runtime visibility в то, что код реально сделал.           |
| 7  | [Security & Governance](#7-security--governance)        | Guardrails против опасных изменений.                       |
| 8  | [Task Discovery](#8-task-discovery)                     | Machine-readable backlog: агенты могут брать работу.       |
| 9  | [Product & Experimentation](#9-product--experimentation) | Измерение влияния feature и safe rollout.                  |
| 10 | [Agent Tooling & Interfaces](#10-agent-tooling--interfaces) | Agent-facing surface: CLAUDE.md, AGENTS.md, MCP, hooks, skills. |
| 11 | [Multi-Agent Coordination](#11-multi-agent-coordination) | Готовность к subagents, worktrees и agent teams.           |

---

### 1. Style & Validation

**Что измеряет.** Автоматизированные static checks ловящие syntax errors, style drift, и type mismatches за секунды. Агенты тратят много циклов на это если приходится находить через прогон тестов; нормальный linter и type checker дают instant feedback.

| Level | Постура                                                          |
| ----- | ---------------------------------------------------------------- |
| L1    | Linter и formatter не настроены; стиль enforced informally в review. |
| L2    | Linter и formatter сконфигурированы; задокументированы но не enforced. |
| L3    | Linter, formatter, type checker enforced в CI на каждом PR.      |
| L4    | Pre-commit hooks блокируют плохие изменения локально; type coverage > 90%. |
| L5    | Project-specific rules (custom lints, project-aware codemods).   |

**Чек-лист:**

* [ ] **L1** Linter существует для каждого primary языка (ESLint, Ruff, golangci-lint и т.д.).
* [ ] **L1** Formatter существует для каждого primary языка (Prettier, Black, gofmt, rustfmt и т.д.).
* [ ] **L2** Linter и formatter configs закоммичены.
* [ ] **L2** Документация говорит агенту как их запускать (`make lint`, `pnpm lint` и т.д.).
* [ ] **L3** Linter и formatter бегут в CI и ломают build на нарушениях.
* [ ] **L3** Type checker настроен если язык поддерживает (TypeScript, mypy, Pyright).
* [ ] **L3** Type checker бежит в CI и ломает build на нарушениях.
* [ ] **L4** Pre-commit hook гоняет linter и formatter локально.
* [ ] **L4** Type strictness высокая (TS `strict: true`, mypy `strict`, no broad `any`).
* [ ] **L5** Repo-specific lint rules кодируют architectural constraints (layering, imports, naming).

---

### 2. Build System

**Что измеряет.** Можно ли свежий checkout детерминированно собрать одной задокументированной командой, и pin'нуты ли dependencies. Без этого агент не может верифицировать свои изменения локально.

| Level | Постура                                                                                 |
| ----- | --------------------------------------------------------------------------------------- |
| L1    | Build работает на машине автора; setup это folklore.                                    |
| L2    | Задокументированная build команда существует. Версии dependencies pin'нуты.             |
| L3    | One-command build от clean checkout; lockfile закоммичен; build бежит в CI.             |
| L4    | Incremental и cached builds; build time под 5 минут на typical changes.                 |
| L5    | Hermetic, reproducible builds (Bazel, Nix или эквивалент).                              |

**Чек-лист:**

* [ ] **L1** Build воспроизводится на машине второго разработчика.
* [ ] **L2** Один задокументированный command собирает проект (`make build`, `pnpm build` и т.д.).
* [ ] **L2** Lockfile закоммичен (`package-lock.json`, `pnpm-lock.yaml`, `poetry.lock`, `Cargo.lock`, `go.sum` и т.д.).
* [ ] **L2** Direct dependencies имеют version constraints, не floating tags.
* [ ] **L3** Build бежит в CI на каждом PR.
* [ ] **L3** Build artifacts детерминированы при том же lockfile и source.
* [ ] **L3** Failure messages от build actionable (не просто "exit 1").
* [ ] **L4** Build cache (Turborepo, Nx, sccache, Bazel remote cache и т.д.) настроен.
* [ ] **L4** Типичный incremental build под 5 минут.
* [ ] **L5** Hermetic, fully reproducible builds с pinned toolchain.

---

### 3. Testing

**Что измеряет.** Может ли агент верифицировать что его изменение работает не спрашивая человека. Самый leverage'овый pillar: агенты работают радикально лучше когда могут прогнать тесты и прочитать output.

| Level | Постура                                                                                     |
| ----- | ------------------------------------------------------------------------------------------- |
| L1    | Какие-то тесты есть но запустить сложно; нет consistent runner.                             |
| L2    | Задокументированная test команда гоняет suite; unit tests покрывают самый меняющийся код.   |
| L3    | Unit и integration tests бегут в CI на каждом PR. Тесты легко запускать локально.           |
| L4    | E2E и snapshot tests для critical paths. Coverage трекается.                                |
| L5    | Mutation testing, property-based tests или formal verification для самой критичной логики. |

**Чек-лист:**

* [ ] **L1** Хотя бы один тест существует и доказательно ловит реальную регрессию.
* [ ] **L2** Один command гоняет все тесты (`make test`, `pnpm test`, `pytest` и т.д.).
* [ ] **L2** Запуск одного теста или одного файла задокументирован.
* [ ] **L3** Unit tests покрывают модули, меняющиеся чаще всего.
* [ ] **L3** Integration tests покрывают границы (API, DB, external service).
* [ ] **L3** Тесты бегут в CI на каждом PR и gating'уют merge.
* [ ] **L3** Test failures выдают полезный diagnostic output, не просто "assertion failed".
* [ ] **L4** E2E tests покрывают top user journeys.
* [ ] **L4** Test coverage репортится в CI; тренд виден команде.
* [ ] **L4** Flaky tests трекаются и quarantine'нуты, не игнорируются.
* [ ] **L5** Mutation testing или property-based testing покрывают highest-risk модули.

---

### 4. Documentation & Agent Context

**Что измеряет.** Записан ли контекст нужный агенту чтобы быть эффективным, discoverable ли он, актуальный ли. Этот pillar самый leverage'овый для агентов, потому что превращает tribal knowledge в то, что они могут прочитать.

| Level | Постура                                                                                                                                |
| ----- | -------------------------------------------------------------------------------------------------------------------------------------- |
| L1    | README существует; всё остальное в головах, Slack, или Notion.                                                                         |
| L2    | README покрывает setup и базовое использование. Какие-то operational runbooks есть.                                                    |
| L3    | `AGENTS.md` или `CLAUDE.md` в корне репо с build, test, style и gotchas. Architecture docs актуальные.                                |
| L4    | Per-directory context файлы для monorepo модулей. Common workflows captured как skills или slash commands.                            |
| L5    | Living documentation: docs ссылаются на код, код ссылается на docs, агенты обновляют оба как часть изменений.                          |

**Чек-лист:**

* [ ] **L1** `README.md` существует и описывает что проект делает.
* [ ] **L2** `README.md` документирует prerequisites, install, build, test, run.
* [ ] **L2** Operational runbooks существуют как минимум для deploy и on-call paths.
* [ ] **L3** Agent-facing context file есть в корне репо (`AGENTS.md`, `CLAUDE.md`, или оба). См. [Agent context file](#agent-context-file-cheatsheet) ниже.
* [ ] **L3** Context файл документирует: build command, test command, lint command, code style notes, branch/PR conventions, и хотя бы три project-specific gotchas.
* [ ] **L3** Architecture overview существует (одна диаграмма или одна страница достаточно) и актуальна.
* [ ] **L3** Public APIs имеют docstrings или interface comments.
* [ ] **L4** Monorepo модули имеют свои per-directory `AGENTS.md` / `CLAUDE.md`.
* [ ] **L4** Частые multi-step workflows captured как reusable artifacts: Claude Code skills, custom slash commands или скрипты.
* [ ] **L4** Documentation freshness проверяется: stale docs всплывают в review.
* [ ] **L5** Documentation треатится как код: PR'ы меняющие behavior обязаны обновлять docs в том же изменении.

#### Agent context file cheatsheet

Репа на L3 имеет хотя бы один agent-facing context file в корне. Какой именно зависит от того, какими агентами пользуется команда:

* **`CLAUDE.md`**: Claude Code от Anthropic читает это на каждой сессии. Project root или user home (`~/.claude/CLAUDE.md`).
* **`AGENTS.md`**: открытый стандарт. Поддерживается OpenAI Codex, Gemini CLI, Cursor, Aider, GitHub Copilot, Windsurf, Factory, Devin, RooCode и 25+ другими. Стюардится Agentic AI Foundation под Linux Foundation. Формат plain Markdown.
* **`GEMINI.md`**: Gemini CLI от Google смотрит на этот файл в корне проекта и треатит как durable instructions для каждой сессии в этой директории. Gemini CLI также читает `AGENTS.md`.

Многие команды пишут **один** файл и symlink остальные, или держат один канонический файл и пускают каждый tool fallback'аться. Большинство современных агентов (Claude Code, Codex, Gemini CLI) читают `AGENTS.md` если их собственного файла нет, поэтому `AGENTS.md` это самый портативный single choice.

Держи коротко: под 200 строк. Если превысил 200 строк, разбивай на per-directory файлы. Раздутый файл игнорируется. Codex читает максимум один файл на директорию и конкатенирует от repo root вниз до текущей директории; файлы ближе к текущей переопределяют более ранние.

Рекомендуемые секции:

```markdown
# Имя проекта

## Что это
Один абзац для агента который никогда не видел эту репу.

## Setup
Точные commands. Prerequisites. Environment variables.

## Build, test, lint
Точные commands. Запуск одного теста. Type-check command.

## Code style
Конвенции, которые агент не может вывести из кода: import order, naming,
предпочитаемые паттерны, чего избегать.

## Architecture
Где слои живут. Что от чего зависит. Одна диаграмма или один абзац.

## Project-specific gotchas
Неочевидные поведения. Недавние инциденты сформировавшие правило.
Anti-patterns которые выглядят разумно но ломают вещи здесь.

## Как коммитить и открывать PR
Branch naming. Стиль commit message. Required checks.
```

Anti-bloat проверка: для каждой строки спроси "удаление этого приведёт к ошибке агента?". Если нет, режь.

---

### 5. Development Environment

**Что измеряет.** Может ли свежий агент (или человек) получить рабочее окружение за минуты, не за часы. Reproducible environments элиминируют целый класс failures.

| Level | Постура                                                                                       |
| ----- | --------------------------------------------------------------------------------------------- |
| L1    | Setup ручной и order-dependent; задокументирован частично.                                    |
| L2    | Bootstrap скрипт существует. Required env vars перечислены.                                   |
| L3    | One-command bootstrap. Devcontainer или эквивалент работает out-of-the-box.                  |
| L4    | Identical dev / CI / preview environments. Ephemeral preview environments per PR.            |
| L5    | Cloud dev environments (Codespaces, Coder и т.д.) first-class.                                |

**Чек-лист:**

* [ ] **L1** Новый разработчик может описать как поставить проект, даже если это займёт день.
* [ ] **L2** `.env.example` или эквивалентный template перечисляет каждый required env var.
* [ ] **L2** Bootstrap скрипт (`./scripts/setup.sh`, `make bootstrap` и т.д.) существует.
* [ ] **L3** Devcontainer config (`.devcontainer/devcontainer.json`), Nix flake или эквивалент reproducible env закоммичен.
* [ ] **L3** Один command стартует проект end-to-end локально (`docker compose up`, `make dev` и т.д.).
* [ ] **L3** Local services (DB, cache, queue) контейнеризованы или скриптованы, не ручные.
* [ ] **L4** CI бежит в том же контейнере или environment как local dev.
* [ ] **L4** Per-PR preview environments автоматически provisioned.
* [ ] **L5** Cloud dev environments (Codespaces, Coder, Gitpod) работают без ручного setup.

---

### 6. Debugging & Observability

**Что измеряет.** Может ли агент узнать что код реально сделал на runtime. Structured logs, traces и metrics превращают "it failed" в конкретный diagnosis.

| Level | Постура                                                                                |
| ----- | -------------------------------------------------------------------------------------- |
| L1    | Unstructured prints; логи не aggregated.                                               |
| L2    | Structured logging в некоторых сервисах. Errors surface'ятся где-то.                   |
| L3    | Structured logging везде; логи aggregated; error tracking подключён.                   |
| L4    | Distributed tracing покрывает critical paths. Metrics dashboard. SLOs определены.      |
| L5    | Агенты могут запрашивать telemetry программно (MCP, CLI или API).                     |

**Чек-лист:**

* [ ] **L1** Errors пишутся в stderr или log, не silently глотаются.
* [ ] **L2** Логи structured (JSON, logfmt или эквивалент) в основных сервисах.
* [ ] **L2** Error tracker (Sentry, Rollbar и т.д.) или aggregator (Datadog, Loki и т.д.) ingest'ит ошибки.
* [ ] **L3** У каждого request/job есть correlation id, идущий через логи.
* [ ] **L3** Error messages actionable: что упало, какой input, что попробовать дальше.
* [ ] **L3** Задокументированный способ получить последние N error logs для модуля.
* [ ] **L4** Distributed tracing (OpenTelemetry, Datadog APM, Honeycomb) разведён по critical paths.
* [ ] **L4** Metrics dashboard показывает request volume, error rate, latency.
* [ ] **L4** SLOs и alerts существуют для самых важных user-visible journeys.
* [ ] **L5** У агентов есть tool (MCP server, CLI или API) для прямого запроса логов, traces и metrics.

---

### 7. Security & Governance

**Что измеряет.** Guardrails предотвращающие unsafe действия от агента (или человека) без его понимания: запушить secrets, обойти review, мержить без checks.

| Level | Постура                                                                                  |
| ----- | ---------------------------------------------------------------------------------------- |
| L1    | Нет enforced branch policy; secrets попадают в git иногда.                               |
| L2    | Branch protection на main. Secrets чистятся реактивно.                                   |
| L3    | Branch protection + required reviews + status checks. Secret scanning блокирует push.    |
| L4    | CODEOWNERS для sensitive областей. SCA на dependencies. Permission boundaries для агентов. |
| L5    | Policy-as-code (OPA, Sentinel и т.д.). SBOM публикуется. Supply-chain attestations (SLSA). |

**Чек-лист:**

* [ ] **L1** Никакие live credentials не закоммичены в репозиторий.
* [ ] **L2** Branch protection блокирует direct push в main.
* [ ] **L2** Задокументированная процедура secret rotation существует.
* [ ] **L3** Required status checks (lint, test, type, security scan) gating'уют merge.
* [ ] **L3** Required review (хотя бы 1 approver) до merge.
* [ ] **L3** Secret scanning блокирует push'и с credentials (Gitleaks, GitHub secret scanning и т.д.).
* [ ] **L3** Dependency vulnerability scanning бежит на каждом PR (Dependabot, Snyk и т.д.).
* [ ] **L3** Agent permissions scoped: allowlist safe commands (lint, test, build, git read) и явный denylist destructive (`rm -rf`, `git push --force`, `DROP TABLE`).
* [ ] **L4** `CODEOWNERS` маппит sensitive paths к required reviewers.
* [ ] **L4** Audit trail на agent actions: каждый commit, push, PR атрибутируется.
* [ ] **L4** Pre-merge sandbox используется для agent-authored изменений в sensitive paths.
* [ ] **L5** Supply-chain attestations (SLSA, Sigstore, in-toto) покрывают build artifacts.
* [ ] **L5** Policy-as-code enforce'ит architectural и security invariants.

---

### 8. Task Discovery

**Что измеряет.** Machine-readable ли backlog. Агент который читает заголовки issues, labels и acceptance criteria может брать routine работу сам.

| Level | Постура                                                                                 |
| ----- | --------------------------------------------------------------------------------------- |
| L1    | Issues живут в голове или Slack thread.                                                 |
| L2    | Issues трекаются в системе. У большинства есть title и description.                     |
| L3    | Issue и PR templates форсят структуру. Labels классифицируют type, priority, area.      |
| L4    | Issues несут acceptance criteria и repro steps. Agent-pickable issues помечены.        |
| L5    | Issues программно queryable; агенты triage'ят и берут работу через API.                 |

**Чек-лист:**

* [ ] **L1** Backlog существует вне чьей-то памяти.
* [ ] **L2** У issues есть title и description.
* [ ] **L2** PR description template существует.
* [ ] **L3** Issue templates существуют для bug reports и feature requests.
* [ ] **L3** Labels классифицируют по type (bug, feature, chore, docs), priority и area/module.
* [ ] **L3** Acceptance criteria или ясное definition of done зафиксированы для большинства issues.
* [ ] **L4** Bug reports включают repro steps и expected vs actual behavior.
* [ ] **L4** Issues безопасные для агента помечены (`good-first-issue`, `agent-ok` и т.д.).
* [ ] **L5** Задокументированный query (CLI, MCP или API) возвращает текущий agent-eligible backlog.
* [ ] **L5** Агенты постят status updates обратно в issue tracker по ходу работы.

---

### 9. Product & Experimentation

**Что измеряет.** Измеряется ли влияние feature и safe ли rollout. Это то что позволяет агенту (или кому-то) шипить изменения уверенно и верифицировать что они помогли.

| Level | Постура                                                                                  |
| ----- | ---------------------------------------------------------------------------------------- |
| L1    | Нет product analytics. Релизы all-or-nothing.                                            |
| L2    | Базовая analytics на page views или top events. Ручной rollout.                          |
| L3    | Event analytics покрывают key user journeys. Feature flags существуют.                   |
| L4    | A/B testing infrastructure. Staged rollouts. Kill switches работают.                     |
| L5    | Агенты могут гонять experiments end-to-end со statistical guardrails.                    |

**Чек-лист:**

* [ ] **L1** Релизы записываются (changelog, release notes, deploys log).
* [ ] **L2** Page views или top events instrumented (PostHog, Amplitude, GA, Mixpanel и т.д.).
* [ ] **L2** Rollback procedure задокументирована и использовалась хотя бы раз.
* [ ] **L3** Event analytics покрывают top user journeys end-to-end.
* [ ] **L3** Feature flags существуют для рискованных изменений; flag toggles задокументированы.
* [ ] **L3** Релизы откатываются меньше чем за 15 минут.
* [ ] **L4** Experimentation framework поддерживает A/B tests с proper sample size и stat checks.
* [ ] **L4** Staged rollouts (canary, percentage, region-based) routine.
* [ ] **L4** Kill switches тестируются хотя бы раз в квартал.
* [ ] **L5** Агенты могут читать experiment results и предлагать follow-up actions.

---

### 10. Agent Tooling & Interfaces

**Что измеряет.** Agent-facing surface area: как агент получает контекст, какие tools может вызвать, какие guardrails есть, и как он композирует работу. Этот pillar это разница между "агент может прочитать эту репу" и "агент может эффективно работать в этой репе".

| Level | Постура                                                                                                                |
| ----- | ---------------------------------------------------------------------------------------------------------------------- |
| L1    | Default agent settings; ничего project-specific.                                                                       |
| L2    | Permission allowlist существует. Хотя бы один context файл написан вручную.                                            |
| L3    | `AGENTS.md` / `CLAUDE.md` tuned. MCP servers подключены к primary external systems репы. Hooks enforce'ят style.       |
| L4    | Skills или slash commands ловят recurring workflows. Subagents обрабатывают research / review отдельно.                |
| L5    | Evaluation harness измеряет agent performance на репе через время. Tool descriptions tuned, не boilerplate.            |

**Чек-лист:**

* [ ] **L1** Репа была открыта хотя бы одним coding agent (Claude Code, Codex, Gemini CLI, Cursor и т.д.) и кто-то наблюдал её работу.
* [ ] **L2** Permission allowlist разрешает safe commands (`make test`, `pnpm lint`, `git status`) без prompt. Механизм tool-specific: `.claude/settings.json` для Claude Code, `~/.codex/config.toml` для Codex, эквивалент для других tools.
* [ ] **L2** Denylist или sandbox блокирует destructive commands (`rm -rf`, `git push --force`, raw DB writes).
* [ ] **L3** Agent context файл (`CLAUDE.md`, `AGENTS.md`, `GEMINI.md` или комбинация) был отредактирован командой на основе observed agent failures, не generic boilerplate.
* [ ] **L3** MCP servers настроены для primary external systems репы: issue tracker, observability, design tool, deployment platform. MCP поддерживается нативно Claude Code, Gemini CLI и Codex.
* [ ] **L3** Pre-commit hooks детерминированно enforce'ят обязательные действия (lint, format, type-check). Документация это говорит.
* [ ] **L3** Хотя бы один project-specific slash command или skill ловит recurring workflow (например `/fix-issue`, `/release-notes`, `/triage`). Skills format: `.claude/skills/<name>/SKILL.md` для Claude Code, `~/.agents/skills/<name>/SKILL.md` для Codex (skills запущены для Codex в декабре 2025), эквивалент в Gemini API Skills.
* [ ] **L3** Agent context файл документирует policy запуска plan-mode: когда агент обязан планировать до действий (нетривиальные задачи, architectural решения, multi-step изменения). См. `agent-readiness-workflow-ru.md` Правило 1.
* [ ] **L3** Lessons-capture convention документирована: после коррекции от user'а агент обновляет persistent lessons файл (`tasks/lessons.md`, `memory/lessons_*.md` или эквивалент) с pattern и правилом которое предотвращает recurrence. См. `agent-readiness-workflow-ru.md` Правило 3.
* [ ] **L4** Specialized subagents обрабатывают isolated tasks (code review, security review, research) без замусоривания main context.
* [ ] **L4** Tool descriptions на custom MCP servers написаны для agent consumption, не human reference: ясный contract, examples, когда не вызывать.
* [ ] **L4** Задокументированный "agent-runs" канал (Slack, log file или dashboard) позволяет команде видеть что агенты делают. Для async или long-running agents эту роль играют PR descriptions и commit messages; review cost становится лимитирующим фактором.
* [ ] **L4** Явная autonomous-fix policy задокументирована: какие классы изменений агент может фиксить без human approval (lint, format, dependency bumps, failing tests и т.д.) и что всегда требует approval (schema migrations, customer-facing copy, anything destructive). См. `agent-readiness-workflow-ru.md` Правило 6.
* [ ] **L4** Skill для stress-test плана доступен на нетривиальные решения (допрос по каждой ветке дерева решений с рекомендованными ответами). Пример: skill `grill-me` / `grill-me-ru` в `agent-readiness-skills/`. Использовать перед коммитом к architectural выбору или multi-step плану.
* [ ] **L5** Evaluation harness гоняет фиксированный набор representative tasks против агента периодически и трекает pass rate через время.
* [ ] **L5** Inter-agent protocols (MCP, A2A, ACP, AG-UI) используются осознанно, с пониманием того что делает каждый слой.

#### Anti-patterns в этом pillar

* **Раздутый context файл.** Более 200 строк и агент игнорирует половину. Если продолжаешь добавлять правила а агент всё равно misbehave'ит, файл слишком длинный, не слишком короткий.
* **Boilerplate tool descriptions.** "TODO: describe this tool" в tool description MCP server'а это runtime cost на каждый вызов. Пиши tool descriptions как API docs: input contract, output contract, когда вызывать, когда не.
* **Нет verification path.** Дать агенту возможность мержить без способа верификации это самая частая причина "the agent shipped something that looks right but does not work". Всегда сочетай autonomy с verification.
* **Silent fallbacks.** Tools которые "делают что-то разумное" когда precondition fails скрывают root cause. Падай громко с actionable error.

---

### 11. Multi-Agent Coordination

**Что измеряет.** Готова ли репа к multi-agent workflows: subagents делегирующие изолированные задачи, worktrees изолирующие parallel edits, и Agent Teams (или эквивалентная multi-agent координация) для задач где работникам нужно обсуждать findings и сходиться.

Это качественно другое измерение чем Pillar 10. Pillar 10 это "может ли один агент эффективно работать здесь?". Pillar 11 это "могут ли несколько агентов работать вместе здесь не наступая друг на друга?". Репа может быть Level 5 на Pillar 10 и Level 1 на Pillar 11, и это нормально: multi-agent это opt-in, не default.

**Важный caveat из собственных исследований Anthropic.** Multi-agent системы используют примерно **15x больше токенов чем chat сессия** (single-agent research около 4x). Для большинства coding tasks single-agent плюс subagents покрывает 90% работы; teams нужны для review, research и debugging где parallel exploration независимых гипотез добавляет реальную ценность. Скорь этот pillar честно: репа где никто реально не гоняет multi-agent workload не нуждается быть Level 5 здесь.

| Level | Постура                                                                                                                                              |
| ----- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| L1    | Один агент был открыт в репе и наблюдался хотя бы один раз. Custom subagents нет.                                                                    |
| L2    | Один-два custom subagents определены для recurring работы (например `research`, `security-reviewer`). Tool allowlist scoped per-subagent.            |
| L3    | Каталог specialized subagents покрывает common parallelizable tasks. Worktrees настроены; `.worktreeinclude` если нужно. Permission policy явная per subagent. |
| L4    | Agent Teams playbooks задокументированы для review / research / debug. Hooks enforce'ят quality gates на team task lifecycle. Token-budget guidance написан. |
| L5    | Evaluation harness измеряет multi-agent performance на репе через время. Custom orchestrator patterns задокументированы. Failure modes детектируются и remediated автоматически. |

**Чек-лист:**

* [ ] **L1** Coding agent был запущен в этой репе хотя бы раз, и кто-то прошёл сессию end-to-end.
* [ ] **L1** Либо CLAUDE.md от Anthropic либо open AGENTS.md присутствует в корне (также enforced Pillar 4; здесь засчитывается как prerequisite который агент грузит на старте).
* [ ] **L2** Хотя бы один custom subagent определён в `.claude/agents/` (или эквивалент для других tools) с ясным `description` полем.
* [ ] **L2** У каждого subagent есть `tools:` allowlist, ограничивающий capability до safe surface для его роли.
* [ ] **L2** Хотя бы один subagent invoke'ится регулярно (research, review, test-runner или подобный), не просто existing.
* [ ] **L3** Specialized subagents покрывают common parallelizable tasks: research, code-review, security-review, test-running, doc-generation, или domain-specific эквиваленты.
* [ ] **L3** Git worktrees задокументированы как способ запуска parallel sessions; `.worktreeinclude` настроен если нужны `.env.local` или эквивалентные untracked файлы для свежего worktree.
* [ ] **L3** Subagents которые редактируют файлы используют worktree isolation (`isolation: worktree` в frontmatter) чтобы parallel edits не сталкивались.
* [ ] **L3** Permission policy явная per subagent role: какие read-only, какие могут писать, какие могут запускать shell, какие могут идти в external services.
* [ ] **L3** Короткое decision aid опубликовано (в `AGENTS.md`, skill или runbook) для "single agent vs subagent vs team" на задачу.
* [ ] **L4** Хотя бы один Agent Team playbook задокументирован в репе. Playbook говорит: когда спавнить команду, каких teammates спавнить, как размерить команду (3-5 typical), и какие правила избегания file-conflict применяются.
* [ ] **L4** Hooks (`TeammateIdle`, `TaskCreated`, `TaskCompleted` для Claude Code; эквиваленты для других tools) enforce'ят quality gates на team task lifecycle.
* [ ] **L4** Token-budget guidance задокументирован: multi-agent зарезервирован для задач где 15x token cost оправдан value от parallel exploration. Routine работа на single-agent.
* [ ] **L4** Failure-mode rubric существует для отлова common multi-agent failure modes (см. anti-patterns ниже) и реакция команды на каждый.
* [ ] **L4** Subagent definitions переиспользуются как Agent Teams teammate types (определить раз, использовать и как delegated subagent и как team member).
* [ ] **L5** Evaluation harness гоняет representative набор multi-agent tasks против репы по расписанию, и pass rate трекается через время.
* [ ] **L5** Multi-agent traces (какой subagent что сделал, какие tools вызывал, сколько tokens потратил) observable и analyzable для debugging non-determinism.
* [ ] **L5** Custom orchestrator patterns специфичные для этой репы задокументированы (какие роли, какие tools они вызывают, как findings синтезируются).
* [ ] **L5** Token spend per multi-agent run трекается; budget thresholds триггерят alerts.

#### Capability-gating для multi-agent работы

Отдельная capability table для этого pillar. Base capability table в Part 1 покрывает single-agent autonomy; эта покрывает когда привлекать несколько агентов.

| Задача                                                                              | Min level здесь |
| ----------------------------------------------------------------------------------- | ---------------- |
| Спавнить one-off research subagent читать много файлов не замусоривая main context  | L2               |
| Routine PR review specialized subagent'ом                                           | L2               |
| Parallel feature работа в отдельных worktrees, координации не нужно                 | L3               |
| Multi-perspective code review (security + perf + tests) как Agent Team              | L4               |
| Adversarial debug team с competing hypotheses                                       | L4               |
| Long-horizon multi-day autonomous инициатива через несколько subagents и tools      | L5               |

#### Когда НЕ инвестировать в этот pillar

Multi-agent это неверная инвестиция когда:

* Типичная задача репы single-file edit. 15x token cost не окупается parallel exploration на маленьких scoped изменениях.
* Задачи имеют heavy interdependencies. Если output агента A напрямую feed'ит в B feed'ящий в C, это pipeline, не команда. Используй prompt chaining, не Agent Teams.
* Все агенты должны видеть один и тот же контекст. Multi-agent блестит когда workers могут exploring независимые направления. Identical-context работа должна оставаться single-agent.
* Репа ещё не дошла до Level 3 по Pillars 1-7. Multi-agent на репе без тестов, lint, branch protection умножает blast radius плохого output. Сначала базис.

#### Anti-patterns в этом pillar

Эти приходят напрямую из задокументированных failure modes multi-agent research системы Anthropic, плюс operational уроки от запуска Agent Teams в практике:

* **Excessive spawning.** Lead agent спавнит 50 teammates для простого вопроса. Mitigation: явные scaling правила в orchestrator prompt (simple = 1 worker, comparison = 2-4, complex = до 10).
* **Vague task descriptions создают дубли.** "Investigate the bug" даёт всем teammates ту же стартовую точку и они повторяют друг друга. Mitigation: каждый spawn prompt включает objective, output format, tool scope и явные task boundaries.
* **Source bias.** Workers гравитируют к SEO-optimized content над authoritative primary sources. Mitigation: source quality heuristics в system prompt.
* **Continuation bias.** Workers продолжают искать после точки достаточности. Mitigation: явные "достаточно" criteria.
* **Mutual distraction.** Teammates флудят друг друга status updates и перестают двигаться. Mitigation: messaging discipline, меньше required check-ins.
* **Tool misuse.** Worker ищет в вебе контекст который существует в репе или в Slack. Mitigation: tool selection guidance в orchestrator prompt и tool descriptions.
* **File-conflict overwrites.** Двое teammates редактируют тот же файл параллельно и один перезаписывает другого. Mitigation: правила file ownership в spawn instructions, worktree isolation для write-heavy ролей.
* **Multi-agent для routine work.** Спавн 5-teammate review на тривиальный PR платит 15x в токенах без выигрыша. Mitigation: token-budget guidance и decision aid в репе.
* **Нет человека в петле на длинных run.** Команды бегущие без надзора часами накапливают wasted effort. Mitigation: scheduled check-ins, hooks которые pause'ят на long idle, monitoring канал.

#### Reference patterns от Anthropic

Пять workflow patterns из "Building Effective Agents" от Anthropic маппятся на этот pillar:

| Pattern                   | Что это                                                                 | Где живёт в Claude Code                                  |
| ------------------------- | ----------------------------------------------------------------------- | -------------------------------------------------------- |
| **Prompt Chaining**       | Sequential decomposition с gates между шагами.                          | Slash commands, skills, скриптованные multi-step workflows. |
| **Routing**               | Классифицировать input, dispatch к specialist.                          | Subagent `description` поле; Claude роутит по intent.    |
| **Parallelization**       | Independent workers работают одновременно (sectioning) или голосуют.    | Несколько subagents спавнятся в одном turn; Agent Teams. |
| **Orchestrator-Workers**  | Lead декомпозирует динамически, спавнит specialists, синтезирует.       | Agent Teams (team lead это orchestrator).                |
| **Evaluator-Optimizer**   | Один генерирует, другой критикует, итерируем.                           | Writer/reviewer subagent пара; Agent Teams debate mode.  |

---

## Part 4. Organizational Readiness (Optional Layer 0)

Pillars выше измеряют репозиторий. Они не измеряют готова ли команда и организация вокруг неё работать AI-native.

Репа может скорить Level 4 по каждому техническому pillar и всё равно не видеть adoption агентов, потому что люди не настроены их использовать. Этот опциональный слой флагает самые частые organizational gaps. Не часть numeric score. Используй как context check перед инвестицией в repo-level remediation.

На основе "5 Shifts to Build an AI-Native Workforce" от Scaled Agile.

### Shift 1. Ownership: только IT недостаточно

* [ ] AI трансформация имеет именованную ownership triad: CIO (инфраструктура, tooling, security), CHRO (literacy, role design, change management), COO (workflow redesign, KPIs).
* [ ] AI budget не 100% в tooling line; есть соответствующая line на workforce capability.
* [ ] В regulated environments workforce preparation идёт **параллельно** с infrastructure work, не после.

### Shift 2. Workflow redesign над tool training

* [ ] Хотя бы два high-value workflows были переработаны end-to-end с AI integrated, не bolt-on.
* [ ] Успех измеряется "работают ли люди иначе?", не training completion rate.
* [ ] AI literacy training заякорена на реальный workflow, не generic curriculum.

### Shift 3. Incentives которые поощряют изменение, не статус-кво

* [ ] Performance reviews учитывают время на эксперименты с новыми workflows.
* [ ] Замедление чтобы интегрировать AI не career penalty.
* [ ] Recognition существует для shared learnings и reusable workflows, не только shipped features.

### Shift 4. Continuous experimentation, не single-point training

* [ ] Время явно выделено на эксперименты, отдельно от delivery.
* [ ] Team-level ритуалы существуют для шеринга что работает с AI (demos, brown bags, slack channels).
* [ ] Certifications треатятся как foundation, не finish line.

### Shift 5. Specialist hires плюс collective capability

* [ ] AI specialists нанимаются где нужны, но capability strategy не заканчивается там.
* [ ] Judgment, governance, oversight, applied AI usage, и data literacy строятся across workforce.
* [ ] AI треатится как то что каждая роль использует, не centralized function у которой другие просят работу.

---

## Part 5. Remediation Playbook

Куда инвестировать в зависимости от текущего уровня.

### L1 -> L2: получить baseline

1. Добавить `README.md` который покрывает что проект, как install, как build, как test, как run.
2. Добавить linter и formatter с закоммиченными configs.
3. Задокументировать один command для прогонки всех тестов.
4. Закоммитить lockfile.
5. Включить branch protection на main.
6. Удалить все live credentials из history.

Это механические изменения. Маленькая команда делает за неделю.

### L2 -> L3: пройти agent-readiness планку

Самый ценный скачок. Пока не дошёл до L3, агенты выдают код требующий тяжёлого human review.

1. Подключить CI: lint, format, type-check, build, test, security scan все gating'уют merge.
2. Добавить devcontainer или эквивалентный reproducible environment.
3. Написать `AGENTS.md` и/или `CLAUDE.md` в корне репо, на основе cheatsheet в Pillar 4.
4. Добавить issue и PR templates с required структурой.
5. Добавить structured logging и подключить error tracker.
6. Настроить agent permissions: allowlist safe commands, denylist destructive.
7. Подключить MCP servers для primary external systems (issue tracker, deployment).
8. Добавить хотя бы один pre-commit hook для must-always-happen checks.
9. Добавить plan-mode triggering policy и lessons-capture convention в `AGENTS.md` / `CLAUDE.md`. Off-the-shelf default в `agent-readiness-workflow-ru.md`.

После L3 агент должен мочь делать bug fixes, dependency upgrades и добавление тестов без надзора.

### L3 -> L4: оптимизировать loop

1. Добавить distributed tracing и metrics dashboard для top user journeys.
2. Per-PR preview environments.
3. Coverage tracking; track and quarantine flaky tests.
4. Per-directory `AGENTS.md` / `CLAUDE.md` для monorepo модулей.
5. Ловить recurring workflows как skills или slash commands.
6. Specialized subagents для code review, security review, research.
7. Tune tool descriptions на custom MCP servers на основе observed agent behavior.
8. **Если multi-agent в scope:** задокументировать хотя бы один Agent Teams playbook (parallel review или competing-hypothesis debug), подключить quality-gate hooks, опубликовать token-budget guidance, написать single-vs-multi decision aid.

### L4 -> L5: инвестировать в agent infrastructure

1. Evaluation harness для performance агентов через время.
2. Policy-as-code для architectural и security invariants.
3. Supply-chain attestations (SLSA, Sigstore).
4. Programmatic backlog query: агенты могут брать agent-eligible работу без human routing.
5. Experimentation infrastructure со statistical guardrails которую агенты могут использовать напрямую.
6. **Если multi-agent в scope:** поднять evaluation harness для multi-agent tasks на этой репе, наблюдать per-run token spend, задокументировать custom orchestrator patterns для типичных multi-agent workloads репы.

---

## Part 6. Scoring Worksheet

Воспроизведи эту таблицу при assessment. Минимум по всем pillars это repo level.

| #  | Pillar                       | L1 пройдено   | L2 пройдено   | L3 пройдено   | L4 пройдено   | L5 пройдено   | Awarded level |
| -- | ---------------------------- | ------------- | ------------- | ------------- | ------------- | ------------- | ------------- |
| 1  | Style & Validation           |  / 2          |  / 2          |  / 3          |  / 2          |  / 1          |               |
| 2  | Build System                 |  / 1          |  / 3          |  / 3          |  / 2          |  / 1          |               |
| 3  | Testing                      |  / 1          |  / 2          |  / 4          |  / 3          |  / 1          |               |
| 4  | Documentation & Agent Context |  / 1          |  / 2          |  / 4          |  / 3          |  / 1          |               |
| 5  | Development Environment      |  / 1          |  / 2          |  / 3          |  / 2          |  / 1          |               |
| 6  | Debugging & Observability    |  / 1          |  / 2          |  / 3          |  / 3          |  / 1          |               |
| 7  | Security & Governance        |  / 1          |  / 2          |  / 5          |  / 3          |  / 2          |               |
| 8  | Task Discovery               |  / 1          |  / 2          |  / 3          |  / 2          |  / 2          |               |
| 9  | Product & Experimentation    |  / 1          |  / 2          |  / 3          |  / 3          |  / 1          |               |
| 10 | Agent Tooling & Interfaces   |  / 1          |  / 2          |  / 6          |  / 5          |  / 2          |               |
| 11 | Multi-Agent Coordination     |  / 2          |  / 3          |  / 5          |  / 5          |  / 4          |               |

**Repository level: \_\_\_** (минимум по pillars, с 80% threshold внутри каждого уровня).

**Pillar для инвестиции дальше: \_\_\_** (тот, который капает минимум).

**Caveat Pillar 11.** Multi-agent готовность opt-in. Если команда не гоняет multi-agent workloads, скорь Pillar 11 честно и исключи из minimum-across-pillars расчёта пометив "Not pursued". Включение раздувает давление инвестировать в измерение которое команде может быть не нужно.

---

## Appendix: References

### Anthropic guidance (primary)

* [Claude Code best practices](https://code.claude.com/docs/en/best-practices): структура CLAUDE.md, `/init`, plan-then-code workflow, permissions, hooks, skills, subagents, MCP, verification, parallel sessions.
* [Building effective AI agents](https://www.anthropic.com/research/building-effective-agents): workflow patterns (prompt chaining, routing, parallelization, orchestrator-workers, evaluator-optimizer), когда использовать агентов vs workflows, tool design principles.
* [Writing tools for agents](https://www.anthropic.com/engineering/writing-tools-for-agents): tool description как контракт, namespacing, context efficiency, response design, error patterns, iterative improvement.
* [Anthropic multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system): production уроки на orchestrator-worker архитектуре, 15x token cost, +90.2% над single-agent на research evals, failure modes, prompt engineering для orchestrators.
* [Claude Code subagents](https://code.claude.com/docs/en/sub-agents): `.claude/agents/` definitions, frontmatter (`name`, `description`, `tools`, `model`), context isolation, scope.
* [Claude Code agent teams](https://code.claude.com/docs/en/agent-teams): экспериментальная multi-session координация, shared task list, mailbox, display modes, hooks, limitations.
* [Claude Code worktrees](https://code.claude.com/docs/en/worktrees): `--worktree` flag, `.worktreeinclude`, subagent isolation, non-git VCS hooks.
* [2026 Agentic Coding Trends Report](https://resources.anthropic.com/hubfs/2026%20Agentic%20Coding%20Trends%20Report.pdf): empirical тренды из customer base Anthropic.

### OpenAI Codex

* [Codex - Best practices](https://developers.openai.com/codex/learn/best-practices): начни с правильного task context, используй AGENTS.md для durable guidance, настрой Codex под workflow, подключи external systems через MCP, превращай повторяющуюся работу в skills, автоматизируй стабильные workflows.
* [Codex - Custom instructions with AGENTS.md](https://developers.openai.com/codex/guides/agents-md): как Codex читает AGENTS.md, file hierarchy (concatenated root-down, ближе override), примеры эффективных секций.
* [Codex - Agent Skills](https://developers.openai.com/codex/skills): SKILL.md файлы в `~/.agents/skills/`, autoload когда task matches. Запущено декабрь 2025.
* [Codex CLI - Reference](https://developers.openai.com/codex/cli/reference): command-line опции, конфигурация, sandbox modes.
* [openai/codex on GitHub](https://github.com/openai/codex): легковесный terminal coding agent.
* [Introducing Codex](https://openai.com/index/introducing-codex/): обзор продукта и позиционирование.

### Google Gemini

* [Set up your coding assistant with Gemini MCP and Skills](https://ai.google.dev/gemini-api/docs/coding-agents): как держать агента актуальным с evolving Gemini API, настроить Gemini Docs MCP, и обогатить окружение Gemini API Skills.
* [Gemini CLI documentation](https://developers.google.com/gemini-code-assist/docs/gemini-cli): ReAct loop, MCP-native design, output formats (`json`, `stream-json`), context window преимущества, GEMINI.md durable instructions.
* [google-gemini/gemini-cli on GitHub](https://github.com/google-gemini/gemini-cli): open-source Gemini terminal agent.

### Open standards

* [AGENTS.md specification](https://agents.md/): открытый Markdown стандарт для agent context файлов. Поддерживается Claude, Codex, Cursor, Aider, GitHub Copilot, Gemini CLI, Windsurf, Factory, Devin, RooCode и 25+ другими. Стюардится Agentic AI Foundation под Linux Foundation.
* Agentic protocols (MCP, A2A, ACP, AG-UI): inter-agent и agent-tool protocol слои в Pillar 10. MCP самый зрелый; остальные полезны при дизайне multi-agent систем.

### Organizational layer

* [Scaled Agile - 5 Shifts to Build an AI-Native Workforce](https://ai-native.scaledagile.com/): пять organizational shifts в Part 4. Источник для ownership triad, workflow-redesign-over-tool-training, и incentive-system framing.

### Workflow orchestration

* [`agent-readiness-workflow-ru.md`](agent-readiness-workflow-ru.md): шесть in-session workflow правил (plan-mode default, subagent strategy, self-improvement loop, verification before done, demand elegance, autonomous bug fixing) извлечённых из опубликованного CLAUDE.md Boris Cherny. Drop-in template для `AGENTS.md` / `CLAUDE.md`. Связан с Pillar 10 (и частично Pillars 3, 4, 7, 11).
* [`agent-readiness-skills/`](agent-readiness-skills/): три устанавливаемых Claude Code skills используемых вместе с этим framework. Source of truth здесь; symlink в `~/.claude/skills/<name>` для установки.
  * `cherny-workflow`: in-session workflow rules из `agent-readiness-workflow.md` как installable skill.
  * `grill-me`: stress-test плана через безжалостный допрос по дереву решений, английские triggers.
  * `grill-me-ru`: тот же skill, русские triggers и русский body.

### Further reading

* [Augment - How to Build Your AGENTS.md (2026)](https://www.augmentcode.com/guides/how-to-build-agents-md): практическое guidance на размер AGENTS.md файлов; правило 150-200 строк.
* [Hivetrail - AGENTS.md vs CLAUDE.md](https://hivetrail.com/blog/agents-md-vs-claude-md-cross-tool-standard): сравнение двух file конвенций и их взаимодействие.

### Factory.ai Agent Readiness (источник pillar count и scoring)

* [Factory.ai - Introducing Agent Readiness](https://factory.ai/news/agent-readiness): 8-pillar / 5-level модель которая informed Pillars 1-9 и binary-criteria-plus-80%-threshold scoring правило. Slash command `/readiness-report` и dashboard `app.factory.ai/analytics/readiness`.
* [Factory.ai docs - Agent Readiness overview](https://docs.factory.ai/web/agent-readiness/overview): расширенный pillar list (9 pillars включая Task Discovery и Product & Experimentation), scoring правила, evaluation scopes.
