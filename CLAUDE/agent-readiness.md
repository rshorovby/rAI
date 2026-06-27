# AI Agent Readiness Assessment

A maturity model and self-assessment checklist for evaluating whether a repository is ready for autonomous AI coding agents (Claude Code, Codex, Gemini CLI, Cursor, Aider, Devin, Factory Droid, Copilot, and similar).

This document is both:

1. A **model**: the dimensions on which agent-readiness is judged.
2. A **tool**: pass/fail criteria you can walk through to score a repo.

It is built on Anthropic's Claude Code best practices and multi-agent guidance, supplemented by OpenAI Codex and Google Gemini documentation, the open AGENTS.md standard, organizational guidance from Scaled Agile, and the published Factory.ai Agent Readiness model. Sources are linked in the appendix.

---

## Why this matters

Agents do not fail randomly. They fail in predictable places: when there is no way to verify their work, when context lives only in someone's head, when feedback loops are slow, when the environment is not reproducible, when an action is destructive and irreversible.

A ready repository has tight feedback loops, explicit context, and safe defaults. Agents in those repositories close issues, ship tests, upgrade dependencies, and handle routine maintenance without supervision. Agents in unready repositories burn cycles on tribal knowledge, get blocked on environment setup, and ship plausible-looking code that does not actually work.

The model below is calibrated so that **Level 3 ("Standardized")** is the minimum bar for letting an agent merge code unsupervised on routine tasks. Most teams should aim there first, then climb.

---

## Part 1. Maturity Model

Five levels. A repository progresses through them in order. Each level represents a qualitative shift in what agents can be trusted to do.

| Level | Name           | Posture                                                                                                                                  | What an agent can do here                                                                                                   |
| ----- | -------------- | ---------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| **1** | Functional     | Code compiles and runs, but setup is manual, validation is ad hoc, and context lives in people's heads.                                  | Generate snippets and answer questions. Every change needs a human to verify and merge.                                     |
| **2** | Documented     | Basic docs and scripts exist. An agent can find the build command and run the tests, but coverage is patchy and there is no enforcement. | Make scoped, single-file changes under human review. Pair-programming style.                                                |
| **3** | Standardized   | Processes are defined, documented, and enforced through automation. Tests, linters, and security checks run on every change.             | **Routine autonomous work**: bug fixes, refactors, dependency upgrades, doc updates, test additions. PRs ready for review.  |
| **4** | Optimized      | Fast feedback loops, structured observability, measurable performance. Agents get high-quality signal in seconds, not minutes.           | Multi-file features, performance-aware changes, on-call triage with telemetry context.                                      |
| **5** | Autonomous     | Self-improving systems. Agents have orchestration, evaluation harnesses, experimentation infrastructure, and clear safety boundaries.    | End-to-end feature delivery, A/B experiments, incident response, fleet-wide upgrades. Human reviews policy, not every diff. |

**Target for most teams: Level 3.** Going from L1 to L3 unlocks most of the value. L4 and L5 are optimizations that compound over time.

### Capability gating

These rules of thumb pair an agent task with the minimum readiness level it should be attempted at:

| Task                                                            | Min level |
| --------------------------------------------------------------- | --------- |
| Ask questions, explain code, propose changes                    | L1        |
| Make a single-file change reviewed by a human                   | L2        |
| Fix a bug, add a test, upgrade a dependency, write docs         | L3        |
| Land a multi-file feature, refactor a module                    | L4        |
| Run an open-ended initiative, multi-day work, autonomous triage | L5        |

---

## Part 2. Scoring Method

The model is intentionally simple so a team can run an assessment in one sitting.

### Per-pillar score

Each pillar has a checklist grouped by level. You award the pillar the **highest level for which at least 80% of items pass**.

* Each item is binary: pass or fail. Partial credit is not awarded.
* If fewer than 80% of L*N* items pass, the pillar is at L*N-1*.
* L1 is the floor. If L1 items fail, fix those first; the pillar is "Pre-Functional".

### Repository score

The repository's overall level is the **minimum across pillars**. One weak pillar caps the repo.

Use the **average** as a secondary signal to see where you are heading, but the minimum is what gates agent autonomy: agents will fail on the weakest dimension first.

### Repository vs application scope

Some criteria are repo-wide (branch protection, README). Others apply per-application in a monorepo (linter config, test command, devcontainer). Score per-application criteria as "**N of M** apps pass" and require 80% to count.

### How to run the assessment

Three options, from least to most automated:

1. **Manual pass.** Walk through Part 3 with a tech lead. Mark each item. One hour for a small repo, half a day for a complex monorepo.
2. **Agent-driven pass.** Drop this document into the repo and run `claude -p "Score this repo against agent-readiness.md and produce a filled checklist with evidence (file paths, command outputs)"`. Review and adjust.
3. **CI-integrated pass.** Convert the binary criteria into shell/CI checks that run on every PR. Track the score over time. Tools that do this natively include Factory.ai's `/readiness-report`; equivalent custom tooling is straightforward.

**Re-assess quarterly**, and whenever there is a major architectural change.

---

## Part 3. Pillars

Eleven pillars in total. The first nine cover the codebase environment (style, build, testing, docs, dev env, observability, security, task discovery, product). The last two ("Agent Tooling & Interfaces" and "Multi-Agent Coordination") capture the agent-specific surface area that most published maturity models treat implicitly.

### Pillar map

| #  | Pillar                                                  | What it measures                                                |
| -- | ------------------------------------------------------- | --------------------------------------------------------------- |
| 1  | [Style & Validation](#1-style--validation)              | Static signal: linting, types, formatting.                      |
| 2  | [Build System](#2-build-system)                         | Reproducible, deterministic builds.                             |
| 3  | [Testing](#3-testing)                                   | Automated verification at multiple layers.                      |
| 4  | [Documentation & Agent Context](#4-documentation--agent-context) | Written context an agent can actually load.                     |
| 5  | [Development Environment](#5-development-environment)   | Reproducible local and CI environments.                         |
| 6  | [Debugging & Observability](#6-debugging--observability) | Runtime visibility into what the code actually did.             |
| 7  | [Security & Governance](#7-security--governance)        | Guardrails for unsafe changes.                                  |
| 8  | [Task Discovery](#8-task-discovery)                     | Machine-readable backlog: agents can pick up work.              |
| 9  | [Product & Experimentation](#9-product--experimentation) | Feature impact measurement and safe rollout.                    |
| 10 | [Agent Tooling & Interfaces](#10-agent-tooling--interfaces) | Agent-facing surface: CLAUDE.md, AGENTS.md, MCP, hooks, skills. |
| 11 | [Multi-Agent Coordination](#11-multi-agent-coordination) | Readiness for subagents, worktrees, and agent teams.            |

---

### 1. Style & Validation

**What it measures.** Automated static checks that catch syntax errors, style drift, and type mismatches in seconds. Agents waste a lot of cycles on these if they have to find them by running tests; a good linter and type checker give instant feedback.

| Level | Posture                                                          |
| ----- | ---------------------------------------------------------------- |
| L1    | No linter or formatter; style is enforced informally in review.  |
| L2    | Linter and formatter configured; documented but not enforced.    |
| L3    | Linter, formatter, type checker enforced in CI on every PR.      |
| L4    | Pre-commit hooks block bad changes locally; type coverage > 90%. |
| L5    | Project-specific rules (custom lints, project-aware codemods).   |

**Checklist:**

* [ ] **L1** A linter exists for each primary language (ESLint, Ruff, golangci-lint, etc.).
* [ ] **L1** A formatter exists for each primary language (Prettier, Black, gofmt, rustfmt, etc.).
* [ ] **L2** Linter and formatter configs are committed to the repo.
* [ ] **L2** Documentation tells an agent how to run them (`make lint`, `pnpm lint`, etc.).
* [ ] **L3** Linter and formatter run in CI and fail the build on violations.
* [ ] **L3** A type checker is configured if the language supports it (TypeScript, mypy, Pyright).
* [ ] **L3** Type checker runs in CI and fails the build on violations.
* [ ] **L4** Pre-commit hook runs the linter and formatter locally.
* [ ] **L4** Type strictness is high (TS `strict: true`, mypy `strict`, no broad `any`).
* [ ] **L5** Repo-specific lint rules encode architectural constraints (layering, imports, naming).

---

### 2. Build System

**What it measures.** Whether a fresh checkout can be built deterministically with a documented command, and whether dependencies are pinned. Without this, agents cannot verify their changes locally.

| Level | Posture                                                                                 |
| ----- | --------------------------------------------------------------------------------------- |
| L1    | Build works on the original author's machine; setup is folklore.                        |
| L2    | A documented build command exists. Dependency versions are pinned.                      |
| L3    | One-command build from a clean checkout; lockfile committed; build runs in CI.          |
| L4    | Incremental and cached builds; build time under 5 minutes for typical changes.          |
| L5    | Hermetic, reproducible builds (Bazel, Nix, or equivalent).                              |

**Checklist:**

* [ ] **L1** Build can be reproduced on a second developer's machine.
* [ ] **L2** A single documented command builds the project (`make build`, `pnpm build`, etc.).
* [ ] **L2** A lockfile is committed (`package-lock.json`, `pnpm-lock.yaml`, `poetry.lock`, `Cargo.lock`, `go.sum`, etc.).
* [ ] **L2** Direct dependencies have version constraints, not floating tags.
* [ ] **L3** Build runs in CI on every PR.
* [ ] **L3** Build artifacts are deterministic given the same lockfile and source.
* [ ] **L3** Failure messages from the build are actionable (not just "exit 1").
* [ ] **L4** Build cache (Turborepo, Nx, sccache, Bazel remote cache, etc.) is configured.
* [ ] **L4** Typical incremental build is under 5 minutes.
* [ ] **L5** Hermetic, fully reproducible builds with pinned toolchain.

---

### 3. Testing

**What it measures.** Whether an agent can verify that its change works without asking a human. This is the single highest-leverage pillar: agents perform dramatically better when they can run tests and read the output.

| Level | Posture                                                                                     |
| ----- | ------------------------------------------------------------------------------------------- |
| L1    | Some tests exist but are hard to run; no consistent runner.                                 |
| L2    | A documented test command runs the suite; unit tests cover the most-changed code.           |
| L3    | Unit and integration tests run in CI on every PR. Tests are easy to run locally.            |
| L4    | End-to-end and snapshot tests exist for critical paths. Coverage is tracked.                |
| L5    | Mutation testing, property-based tests, or formal verification for the most critical logic. |

**Checklist:**

* [ ] **L1** At least one test exists and demonstrably catches a real regression.
* [ ] **L2** A single command runs all tests (`make test`, `pnpm test`, `pytest`, etc.).
* [ ] **L2** Running a single test or a single file is documented.
* [ ] **L3** Unit tests cover the modules that change most often.
* [ ] **L3** Integration tests cover the boundaries (API, DB, external service).
* [ ] **L3** Tests run in CI on every PR and gate merge.
* [ ] **L3** Test failures produce useful diagnostic output, not just "assertion failed".
* [ ] **L4** End-to-end tests cover the top user journeys.
* [ ] **L4** Test coverage is reported in CI; trend is visible to the team.
* [ ] **L4** Flaky tests are tracked and quarantined, not ignored.
* [ ] **L5** Mutation testing or property-based testing covers the highest-risk modules.

---

### 4. Documentation & Agent Context

**What it measures.** Whether the context an agent needs to be effective is written down, discoverable, and current. This pillar has the strongest leverage for agents because it converts tribal knowledge into something they can read.

| Level | Posture                                                                                                                                |
| ----- | -------------------------------------------------------------------------------------------------------------------------------------- |
| L1    | A README exists; everything else is in heads, Slack, or Notion.                                                                        |
| L2    | README covers setup and basic usage. Some operational runbooks exist.                                                                  |
| L3    | `AGENTS.md` or `CLAUDE.md` at repo root with build, test, style, and gotchas. Architecture docs current.                               |
| L4    | Per-directory context files for monorepo modules. Common workflows captured as skills or slash commands.                               |
| L5    | Living documentation: docs link to code, code links to docs, agents update both as part of changes.                                    |

**Checklist:**

* [ ] **L1** `README.md` exists and describes what the project does.
* [ ] **L2** `README.md` documents prerequisites, install, build, test, and run.
* [ ] **L2** Operational runbooks exist for at least the deploy and on-call paths.
* [ ] **L3** An agent-facing context file exists at repo root (`AGENTS.md`, `CLAUDE.md`, or both). See [Agent context file](#agent-context-file-cheatsheet) below.
* [ ] **L3** The context file documents: build command, test command, lint command, code style notes, branch/PR conventions, and at least three project-specific gotchas.
* [ ] **L3** Architecture overview exists (one diagram or one page is enough) and is current.
* [ ] **L3** Public APIs have docstrings or interface comments.
* [ ] **L4** Monorepo modules have their own per-directory `AGENTS.md` / `CLAUDE.md`.
* [ ] **L4** Common multi-step workflows are captured as reusable artifacts: Claude Code skills, custom slash commands, or scripts.
* [ ] **L4** Documentation freshness is checked: stale docs surface in review.
* [ ] **L5** Documentation is treated as code: PRs that change behavior must update docs in the same change.

#### Agent context file cheatsheet

A repo at L3 has at least one agent-facing context file at the repo root. Which one depends on which agents the team uses:

* **`CLAUDE.md`**: Anthropic's Claude Code reads it on every session. Project root or user home (`~/.claude/CLAUDE.md`).
* **`AGENTS.md`**: open standard supported by OpenAI Codex, Gemini CLI, Cursor, Aider, GitHub Copilot, Windsurf, Factory, Devin, RooCode, and 25+ others. Stewarded by the Agentic AI Foundation under the Linux Foundation. Format is plain Markdown.
* **`GEMINI.md`**: Google's Gemini CLI looks for this in the project root and treats it as durable instructions for every session in that directory. Gemini CLI also reads `AGENTS.md`.

Many teams write **one** file and symlink the others, or keep one canonical file and let each tool fall back. Most modern agents (Claude Code, Codex, Gemini CLI) read `AGENTS.md` if their own file is absent, so `AGENTS.md` is the most portable single choice.

Keep it short: under 200 lines. If it exceeds 200 lines, split into per-directory files. A bloated file gets ignored. Codex reads at most one file per directory and concatenates from repo root down to the current directory; files closer to the current directory override earlier guidance.

Recommended sections:

```markdown
# Project name

## What this is
One paragraph for an agent that has never seen this repo.

## Setup
Exact commands. Prerequisites. Environment variables required.

## Build, test, lint
The exact commands. Single-test invocation. Type-check command.

## Code style
Conventions an agent cannot infer from the code: import order, naming,
preferred patterns, things to avoid.

## Architecture
Where the layers live. What depends on what. One diagram or one paragraph.

## Project-specific gotchas
Non-obvious behaviors. Recent incidents that shaped a rule. Anti-patterns
that look reasonable but break things here.

## How to commit and open a PR
Branch naming. Commit message style. Required checks.
```

Anti-bloat checks: for every line ask "would removing this cause an agent to make a mistake?". If not, cut it.

---

### 5. Development Environment

**What it measures.** Whether a fresh agent (or human) can get a working environment in minutes, not hours. Reproducible environments eliminate an entire class of failures.

| Level | Posture                                                                                       |
| ----- | --------------------------------------------------------------------------------------------- |
| L1    | Setup is manual and order-dependent; documented partially.                                    |
| L2    | A bootstrap script exists. Required env vars are listed.                                      |
| L3    | One-command bootstrap. Devcontainer or equivalent works out of the box.                       |
| L4    | Identical dev / CI / preview environments. Ephemeral preview environments per PR.             |
| L5    | Cloud development environments (Codespaces, Coder, etc.) are first-class.                     |

**Checklist:**

* [ ] **L1** A new developer can describe how to set up the project, even if it takes a day.
* [ ] **L2** A `.env.example` or equivalent template lists every required env var.
* [ ] **L2** A bootstrap script (`./scripts/setup.sh`, `make bootstrap`, etc.) exists.
* [ ] **L3** Devcontainer config (`.devcontainer/devcontainer.json`), Nix flake, or equivalent reproducible env is committed.
* [ ] **L3** One command starts the project end-to-end locally (`docker compose up`, `make dev`, etc.).
* [ ] **L3** Local services (DB, cache, queue) are containerized or scripted, not manual.
* [ ] **L4** CI runs in the same container or environment as local dev.
* [ ] **L4** Per-PR preview environments are automatically provisioned.
* [ ] **L5** Cloud dev environments (Codespaces, Coder, Gitpod) work without manual setup.

---

### 6. Debugging & Observability

**What it measures.** Whether an agent can find out what the code actually did at runtime. Structured logs, traces, and metrics turn "it failed" into a specific diagnosis.

| Level | Posture                                                                                |
| ----- | -------------------------------------------------------------------------------------- |
| L1    | Unstructured prints; logs are not aggregated.                                          |
| L2    | Structured logging exists in some services. Errors are surfaced somewhere.             |
| L3    | Structured logging everywhere; logs are aggregated; error tracking is wired up.        |
| L4    | Distributed tracing covers critical paths. Metrics dashboard exists. SLOs are defined. |
| L5    | Agents can query telemetry programmatically (MCP, CLI, or API).                        |

**Checklist:**

* [ ] **L1** Errors are written to stderr or a log, not silently swallowed.
* [ ] **L2** Logs are structured (JSON, logfmt, or equivalent) in the main services.
* [ ] **L2** An error tracker (Sentry, Rollbar, etc.) or aggregator (Datadog, Loki, etc.) ingests errors.
* [ ] **L3** Every request/job has a correlation id that flows through logs.
* [ ] **L3** Error messages are actionable: what failed, what was the input, what to try next.
* [ ] **L3** A documented way exists to fetch the last N error logs for a given module.
* [ ] **L4** Distributed tracing (OpenTelemetry, Datadog APM, Honeycomb) is wired through critical paths.
* [ ] **L4** A metrics dashboard surfaces request volume, error rate, and latency.
* [ ] **L4** SLOs and alerts exist for the most important user-visible journeys.
* [ ] **L5** Agents have a tool (MCP server, CLI, or API) to query logs, traces, and metrics directly.

---

### 7. Security & Governance

**What it measures.** Guardrails that prevent an agent (or human) from doing something unsafe without realising it: pushing secrets, bypassing review, merging without checks.

| Level | Posture                                                                                  |
| ----- | ---------------------------------------------------------------------------------------- |
| L1    | No enforced branch policy; secrets land in git occasionally.                             |
| L2    | Branch protection on the main branch. Secrets are scrubbed reactively.                   |
| L3    | Branch protection + required reviews + status checks. Secret scanning blocks pushes.     |
| L4    | CODEOWNERS for sensitive areas. SCA on dependencies. Permission boundaries for agents.   |
| L5    | Policy-as-code (OPA, Sentinel, etc.). SBOM published. Supply-chain attestations (SLSA).  |

**Checklist:**

* [ ] **L1** No live credentials are committed to the repository.
* [ ] **L2** Branch protection prevents direct pushes to the main branch.
* [ ] **L2** A documented secret-rotation procedure exists.
* [ ] **L3** Required status checks (lint, test, type, security scan) gate merge.
* [ ] **L3** Required review (at least 1 approver) before merge.
* [ ] **L3** Secret scanning blocks pushes that include credentials (Gitleaks, GitHub secret scanning, etc.).
* [ ] **L3** Dependency vulnerability scanning runs on every PR (Dependabot, Snyk, etc.).
* [ ] **L3** Agent permissions are scoped: an allowlist of safe commands (lint, test, build, git read) and an explicit denylist for destructive ones (`rm -rf`, `git push --force`, `DROP TABLE`).
* [ ] **L4** `CODEOWNERS` maps sensitive paths to required reviewers.
* [ ] **L4** Audit trail for agent actions: every commit, push, and PR is attributable.
* [ ] **L4** A pre-merge sandbox is used for agent-authored changes that touch sensitive paths.
* [ ] **L5** Supply-chain attestations (SLSA, Sigstore, in-toto) cover build artifacts.
* [ ] **L5** Policy-as-code enforces architectural and security invariants.

---

### 8. Task Discovery

**What it measures.** Whether the backlog is machine-readable. An agent that can read issue titles, labels, and acceptance criteria can pick up routine work on its own.

| Level | Posture                                                                                 |
| ----- | --------------------------------------------------------------------------------------- |
| L1    | Issues live in someone's head or a Slack thread.                                        |
| L2    | Issues are tracked in a system. Most have a title and a description.                    |
| L3    | Issue and PR templates enforce structure. Labels classify type, priority, and area.     |
| L4    | Issues carry acceptance criteria and reproduction steps. Agent-pickable issues labeled. |
| L5    | Issues are programmatically queryable; agents triage and pick work via an API.          |

**Checklist:**

* [ ] **L1** A backlog exists outside someone's memory.
* [ ] **L2** Issues have a title and a description.
* [ ] **L2** A PR description template exists.
* [ ] **L3** Issue templates exist for bug reports and feature requests.
* [ ] **L3** Labels classify by type (bug, feature, chore, docs), priority, and area/module.
* [ ] **L3** Acceptance criteria or a clear definition of done is captured for most issues.
* [ ] **L4** Bug reports include reproduction steps and expected vs. actual behavior.
* [ ] **L4** Issues that are safe for an agent to attempt are labeled (`good-first-issue`, `agent-ok`, etc.).
* [ ] **L5** A documented query (CLI, MCP, or API) returns the current agent-eligible backlog.
* [ ] **L5** Agents post status updates back to the issue tracker as work progresses.

---

### 9. Product & Experimentation

**What it measures.** Whether feature impact is measurable and rollout is safe. This is what lets an agent (or anyone) ship changes confidently and verify they helped.

| Level | Posture                                                                                  |
| ----- | ---------------------------------------------------------------------------------------- |
| L1    | No product analytics. Releases are all-or-nothing.                                       |
| L2    | Basic analytics on page views or top events. Manual rollout.                             |
| L3    | Event analytics cover key user journeys. Feature flags exist.                            |
| L4    | A/B testing infrastructure exists. Rollouts are staged. Kill switches work.              |
| L5    | Agents can run experiments end-to-end, with statistical guardrails.                      |

**Checklist:**

* [ ] **L1** Releases are recorded somewhere (changelog, release notes, deploys log).
* [ ] **L2** Page views or top events are instrumented (PostHog, Amplitude, GA, Mixpanel, etc.).
* [ ] **L2** A rollback procedure is documented and has been used at least once.
* [ ] **L3** Event analytics cover the top user journeys end-to-end.
* [ ] **L3** Feature flags exist for risky changes; flag toggles are documented.
* [ ] **L3** Releases can be rolled back in under 15 minutes.
* [ ] **L4** Experimentation framework supports A/B tests with proper sample size and stat checks.
* [ ] **L4** Staged rollouts (canary, percentage, region-based) are routine.
* [ ] **L4** Kill switches are tested at least quarterly.
* [ ] **L5** Agents can read experiment results and propose follow-up actions.

---

### 10. Agent Tooling & Interfaces

**What it measures.** The agent-facing surface area: how the agent receives context, what tools it can call, what guardrails it has, and how it composes work. This pillar is the difference between "an agent can read this repo" and "an agent can work effectively in this repo".

| Level | Posture                                                                                                                |
| ----- | ---------------------------------------------------------------------------------------------------------------------- |
| L1    | Default agent settings; nothing project-specific.                                                                      |
| L2    | Permission allowlist exists. At least one context file written by hand.                                                |
| L3    | `AGENTS.md` / `CLAUDE.md` is tuned. MCP servers connected for the repo's primary external systems. Hooks enforce style.|
| L4    | Skills or slash commands capture recurring workflows. Subagents handle research / review separately.                   |
| L5    | An evaluation harness measures agent performance on this repo over time. Tool descriptions are tuned, not boilerplate. |

**Checklist:**

* [ ] **L1** The repo has been opened with at least one coding agent (Claude Code, Codex, Gemini CLI, Cursor, etc.) and someone has watched it work.
* [ ] **L2** A permission allowlist permits safe commands (`make test`, `pnpm lint`, `git status`) without prompting. Mechanism is tool-specific: `.claude/settings.json` for Claude Code, `~/.codex/config.toml` for Codex, equivalent config for other tools.
* [ ] **L2** A denylist or sandbox blocks destructive commands (`rm -rf`, `git push --force`, raw DB writes).
* [ ] **L3** An agent context file (`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, or a combination) has been edited by the team based on observed agent failures, not generic boilerplate.
* [ ] **L3** MCP servers are configured for the repo's primary external systems: issue tracker, observability, design tool, deployment platform. MCP is supported natively by Claude Code, Gemini CLI, and Codex.
* [ ] **L3** Pre-commit hooks deterministically enforce the things that must always happen (lint, format, type-check). Documentation says so.
* [ ] **L3** At least one project-specific slash command or skill captures a recurring workflow (e.g. `/fix-issue`, `/release-notes`, `/triage`). Skills format: `.claude/skills/<name>/SKILL.md` for Claude Code, `~/.agents/skills/<name>/SKILL.md` for Codex (skills launched for Codex in December 2025), equivalent in Gemini API Skills.
* [ ] **L3** The agent context file documents a plan-mode triggering policy: when the agent must plan before acting (non-trivial tasks, architectural decisions, multi-step changes). See `agent-readiness-workflow.md` Rule 1.
* [ ] **L3** A lessons-capture convention is documented: after a user correction, the agent updates a persistent lessons file (`tasks/lessons.md`, `memory/lessons_*.md`, or equivalent) with the pattern and a rule preventing recurrence. See `agent-readiness-workflow.md` Rule 3.
* [ ] **L4** Specialized subagents handle isolated tasks (code review, security review, research) without polluting the main context.
* [ ] **L4** Tool descriptions on custom MCP servers are written for agent consumption, not human reference: clear contract, examples, when not to call.
* [ ] **L4** A documented "agent-runs" channel (Slack, log file, or dashboard) lets the team see what agents are doing. For async or long-running agents, PR descriptions and commit messages serve this role; review cost becomes the limiting factor.
* [ ] **L4** An explicit autonomous-fix policy is documented: what classes of change the agent may fix without human approval (lint, format, dependency bumps, failing tests, etc.) and what always requires approval (schema migrations, customer-facing copy, anything destructive). See `agent-readiness-workflow.md` Rule 6.
* [ ] **L4** A plan stress-testing skill is available for non-trivial decisions (interview about each branch of the decision tree with recommended answers). Example: the `grill-me` skill in `agent-readiness-skills/`. Use before committing to architectural choices or multi-step plans.
* [ ] **L5** An evaluation harness runs a fixed set of representative tasks against the agent periodically and tracks pass rate over time.
* [ ] **L5** Inter-agent protocols (MCP, A2A, ACP, AG-UI) are used deliberately, with awareness of what each layer does.

#### Anti-patterns to avoid in this pillar

* **Bloated context file.** Over 200 lines and the agent ignores half. If you keep adding rules and the agent still misbehaves, the file is too long, not too short.
* **Boilerplate tool descriptions.** "TODO: describe this tool" in an MCP server's tool description is a runtime cost on every call. Write tool descriptions like API docs: input contract, output contract, when to call, when not to.
* **No verification path.** Giving an agent the ability to merge without a way to verify is the most common cause of "the agent shipped something that looks right but does not work". Always pair autonomy with verification.
* **Silent fallbacks.** Tools that "do something sensible" when their precondition fails hide the root cause. Fail loudly with an actionable error.

---

### 11. Multi-Agent Coordination

**What it measures.** Whether the repository is ready to host multi-agent workflows: subagents that delegate isolated tasks, worktrees that isolate parallel edits, and Agent Teams (or equivalent multi-agent coordination) for tasks that need workers to discuss findings and converge.

This is a qualitatively different dimension from Pillar 10. Pillar 10 is "can a single agent work effectively here?". Pillar 11 is "can multiple agents work together here without stepping on each other?". A repo can be Level 5 on Pillar 10 and Level 1 on Pillar 11, and that is fine: multi-agent is opt-in, not a default.

**Important caveat from Anthropic's own research.** Multi-agent systems use roughly **15x more tokens than a chat session** (single-agent research is about 4x). For most coding tasks, single-agent plus subagents covers 90% of work; teams are for review, research, and debugging where parallel exploration of independent hypotheses adds real value. Score this pillar honestly: a repo where nobody actually runs multi-agent workloads does not need to be Level 5 here.

| Level | Posture                                                                                                                                              |
| ----- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| L1    | A single agent has been opened in the repo and observed at least once. No custom subagents.                                                          |
| L2    | One or two custom subagents defined for recurring work (e.g. `research`, `security-reviewer`). Tool allowlist scoped per subagent.                   |
| L3    | A catalogue of specialized subagents covers the common parallelizable tasks. Worktrees configured; `.worktreeinclude` if needed. Permission policy explicit per subagent. |
| L4    | Agent Teams playbooks documented for review / research / debug. Hooks enforce quality gates on team task lifecycle. Token-budget guidance written.   |
| L5    | Evaluation harness measures multi-agent performance on this repo over time. Custom orchestrator patterns documented. Failure modes are detected and remediated automatically. |

**Checklist:**

* [ ] **L1** A coding agent has been run in this repo at least once, and someone has watched a session end-to-end.
* [ ] **L1** Either Anthropic's CLAUDE.md or open AGENTS.md is present at the repo root (also enforced by Pillar 4; counted here as the prerequisite an agent loads on start).
* [ ] **L2** At least one custom subagent is defined in `.claude/agents/` (or the equivalent for other tools) with a clear `description` field.
* [ ] **L2** Each subagent has a `tools:` allowlist that restricts its capability to the safe surface for its role.
* [ ] **L2** At least one subagent is invoked routinely (research, review, test-runner, or similar), not just present.
* [ ] **L3** Specialized subagents cover the common parallelizable tasks for this repo: research, code-review, security-review, test-running, doc-generation, or domain-specific equivalents.
* [ ] **L3** Git worktrees are documented as the way to run parallel sessions; `.worktreeinclude` is configured if `.env.local` or equivalent untracked files are required for a fresh worktree.
* [ ] **L3** Subagents that edit files use worktree isolation (`isolation: worktree` in frontmatter) so parallel edits do not collide.
* [ ] **L3** Permission policy is explicit per subagent role: which are read-only, which can write, which can run shell commands, which can hit external services.
* [ ] **L3** A short decision aid is published (in `AGENTS.md`, a skill, or a runbook) for "single agent vs subagent vs team" given a task.
* [ ] **L4** At least one Agent Team playbook is documented in the repo. The playbook says: when to spawn a team, what teammates to spawn, how to size the team (3-5 typical), and what file-conflict avoidance rules apply.
* [ ] **L4** Hooks (`TeammateIdle`, `TaskCreated`, `TaskCompleted` for Claude Code; equivalents for other tools) enforce quality gates on the team task lifecycle.
* [ ] **L4** Token-budget guidance is documented: multi-agent is reserved for tasks where the 15x token cost is justified by parallel exploration value. Routine work uses single-agent.
* [ ] **L4** A failure-mode rubric exists for spotting common multi-agent failure modes (see anti-patterns below) and the team's response to each.
* [ ] **L4** Subagent definitions are reused as Agent Teams teammate types (define once, use as both delegated subagent and team member).
* [ ] **L5** An evaluation harness runs a representative set of multi-agent tasks against the repo on a schedule, and pass rate is tracked over time.
* [ ] **L5** Multi-agent traces (which subagent did what, what tools it called, what tokens it spent) are observable and analyzable for debugging non-determinism.
* [ ] **L5** Custom orchestrator patterns specific to this repo are documented (which roles, what tools they call, how findings are synthesized).
* [ ] **L5** Token spend per multi-agent run is tracked; budget thresholds trigger alerts.

#### Capability-gating for multi-agent work

A separate capability table for this pillar. The base capability table in Part 1 covers single-agent autonomy; this one covers when to involve multiple agents.

| Task                                                                                | Min level here |
| ----------------------------------------------------------------------------------- | -------------- |
| Spawn a one-off research subagent to read many files without polluting main context | L2             |
| Routine PR review by a specialized subagent                                         | L2             |
| Parallel feature work in separate worktrees, no coordination needed                 | L3             |
| Multi-perspective code review (security + perf + tests) as an Agent Team            | L4             |
| Adversarial debug team with competing hypotheses                                    | L4             |
| Long-horizon multi-day autonomous initiative across multiple subagents and tools    | L5             |

#### When NOT to invest in this pillar

Multi-agent is the wrong investment when:

* The repo's typical task is a single-file edit. The 15x token cost is not paid back by parallel exploration on small scoped changes.
* Tasks have heavy interdependencies. If agent A's output feeds directly into agent B which feeds into agent C, that is a pipeline, not a team. Use prompt chaining, not Agent Teams.
* All agents need the same context. Multi-agent shines when workers can explore independent directions. Identical-context work should stay single-agent.
* The repo does not yet hit Level 3 on Pillars 1-7. Multi-agent on a repo without tests, lint, or branch protection multiplies the blast radius of bad output. Fix the basics first.

#### Anti-patterns to avoid in this pillar

These come directly from Anthropic's documented failure modes on their multi-agent research system, plus operational lessons from running Agent Teams in practice:

* **Excessive spawning.** Lead agent spawns 50 teammates for a simple question. Mitigation: explicit scaling rules in the orchestrator prompt (simple = 1 worker, comparison = 2-4, complex = up to 10).
* **Vague task descriptions cause duplicate work.** "Investigate the bug" gives all teammates the same starting point and they repeat each other's searches. Mitigation: each spawn prompt includes objective, output format, tool scope, and explicit task boundaries.
* **Source bias.** Workers gravitate to SEO-optimized content over authoritative primary sources. Mitigation: source quality heuristics in the system prompt.
* **Continuation bias.** Workers keep searching past the point of sufficiency. Mitigation: explicit "enough" criteria.
* **Mutual distraction.** Teammates flood each other with status updates and stop making progress. Mitigation: messaging discipline, fewer required check-ins.
* **Tool misuse.** Worker searches the web for context that exists in the repo or in Slack. Mitigation: tool selection guidance in the orchestrator prompt and tool descriptions.
* **File-conflict overwrites.** Two teammates edit the same file in parallel and one overwrites the other. Mitigation: file-ownership rules in the spawn instructions, worktree isolation for write-heavy roles.
* **Multi-agent for routine work.** Spawning a 5-teammate review on a trivial PR pays 15x in tokens for no gain. Mitigation: token-budget guidance and decision aid in the repo.
* **No human in the loop on long runs.** Teams that run unattended for hours accumulate wasted effort. Mitigation: scheduled check-ins, hooks that pause on long idle, monitoring channel.

#### Reference patterns from Anthropic

Five workflow patterns from Anthropic's "Building Effective Agents" map onto this pillar:

| Pattern                   | What it is                                                              | Where it lives in Claude Code                           |
| ------------------------- | ----------------------------------------------------------------------- | ------------------------------------------------------- |
| **Prompt Chaining**       | Sequential decomposition with gates between steps.                      | Slash commands, skills, scripted multi-step workflows.  |
| **Routing**               | Classify input, dispatch to a specialist.                               | Subagent `description` field; Claude routes by intent.  |
| **Parallelization**       | Independent workers operate simultaneously (sectioning) or vote.        | Multiple subagents spawned in one turn; Agent Teams.    |
| **Orchestrator-Workers**  | Lead decomposes dynamically, spawns specialists, synthesizes results.   | Agent Teams (team lead is the orchestrator).            |
| **Evaluator-Optimizer**   | One generates, another critiques, iterate.                              | Writer/reviewer subagent pair; Agent Teams debate mode. |

---

## Part 4. Organizational Readiness (Optional Layer 0)

The pillars above measure the repository. They do not measure whether the team and the organization around it are ready to operate AI-native.

A repository can score Level 4 across every technical pillar and still see no agent adoption, because the people are not set up to use agents. This optional layer flags the most common organizational gaps. It is not part of the numeric score. Treat it as a context check before investing in repo-level remediation.

Based on Scaled Agile's "5 Shifts to Build an AI-Native Workforce".

### Shift 1. Ownership: IT alone is not enough

* [ ] AI transformation has a named owner triad: CIO (infrastructure, tooling, security), CHRO (literacy, role design, change management), COO (workflow redesign, KPIs).
* [ ] AI budget is not 100% in the tooling line; there is a corresponding line for workforce capability.
* [ ] In regulated environments, workforce preparation runs **in parallel** with infrastructure work, not after.

### Shift 2. Workflow redesign over tool training

* [ ] At least two high-value workflows have been redesigned end-to-end with AI integrated, not bolted on.
* [ ] Success is measured by "do people work differently?", not by training completion rate.
* [ ] AI literacy training is anchored to a real workflow, not a generic curriculum.

### Shift 3. Incentives that reward change, not status quo

* [ ] Performance reviews account for time spent experimenting with new workflows.
* [ ] Slowing down to integrate AI is not a career penalty.
* [ ] Recognition exists for shared learnings and reusable workflows, not just shipped features.

### Shift 4. Continuous experimentation, not single-point training

* [ ] Time is explicitly allocated for experimentation, separate from delivery.
* [ ] Team-level rituals exist for sharing what is working with AI (demos, brown bags, slack channels).
* [ ] Certifications are treated as a foundation, not a finish line.

### Shift 5. Specialist hires plus collective capability

* [ ] AI specialists are hired where needed, but the capability strategy does not end there.
* [ ] Judgment, governance, oversight, applied AI usage, and data literacy are built across the workforce.
* [ ] AI is treated as something every role uses, not a centralized function others request work from.

---

## Part 5. Remediation Playbook

Where to invest depending on the current level.

### L1 to L2: get a baseline

1. Add a `README.md` that covers what the project is, how to install, how to build, how to test, how to run.
2. Add a linter and a formatter with committed configs.
3. Document a single command to run all tests.
4. Commit a lockfile.
5. Enable branch protection on the main branch.
6. Remove any live credentials from history.

These are mechanical changes. A small team can do them in a week.

### L2 to L3: cross the agent-readiness bar

This is the most valuable jump. Until you reach L3, agents will produce code that needs heavy human review.

1. Wire CI: lint, format, type-check, build, test, security scan all gate merge.
2. Add a devcontainer or equivalent reproducible environment.
3. Write `AGENTS.md` and/or `CLAUDE.md` at the repo root, based on the cheatsheet in Pillar 4.
4. Add issue and PR templates with required structure.
5. Add structured logging and wire up an error tracker.
6. Configure agent permissions: allowlist safe commands, denylist destructive ones.
7. Connect MCP servers for the repo's primary external systems (issue tracker, deployment).
8. Add at least one pre-commit hook for must-always-happen checks.
9. Add a plan-mode triggering policy and a lessons-capture convention to `AGENTS.md` / `CLAUDE.md`. The off-the-shelf default is in `agent-readiness-workflow.md`.

After L3, an agent should be able to handle bug fixes, dependency upgrades, and test additions without supervision.

### L3 to L4: optimize the loop

1. Add distributed tracing and a metrics dashboard for the top user journeys.
2. Per-PR preview environments.
3. Coverage tracking; track and quarantine flaky tests.
4. Per-directory `AGENTS.md` / `CLAUDE.md` for monorepo modules.
5. Capture recurring workflows as skills or slash commands.
6. Specialized subagents for code review, security review, research.
7. Tune tool descriptions on custom MCP servers based on observed agent behavior.
8. **If multi-agent is in scope:** document at least one Agent Teams playbook (parallel review or competing-hypothesis debug), wire quality-gate hooks, publish token-budget guidance, and write a single-vs-multi decision aid.

### L4 to L5: invest in agent infrastructure

1. Evaluation harness for agent performance over time.
2. Policy-as-code for architectural and security invariants.
3. Supply-chain attestations (SLSA, Sigstore).
4. Programmatic backlog query: agents can pick up agent-eligible work without human routing.
5. Experimentation infrastructure with statistical guardrails that agents can use directly.
6. **If multi-agent is in scope:** stand up an evaluation harness for multi-agent tasks on this repo, observe per-run token spend, and document custom orchestrator patterns for the repo's typical multi-agent workloads.

---

## Part 6. Scoring Worksheet

Reproduce this table when running an assessment. The minimum across pillars is the repository level.

| #  | Pillar                       | L1 items pass | L2 items pass | L3 items pass | L4 items pass | L5 items pass | Awarded level |
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

**Repository level: \_\_\_** (minimum across pillars, with 80% threshold inside each level).

**Pillar to invest in next: \_\_\_** (the one capping the minimum).

**Pillar 11 caveat.** Multi-agent readiness is opt-in. If the team does not run multi-agent workloads, score Pillar 11 honestly and exclude it from the minimum-across-pillars calculation by marking it "Not pursued". Including it inflates pressure to invest in a dimension the team may not need.

---

## Appendix: References

### Anthropic guidance (primary)

* [Claude Code best practices](https://code.claude.com/docs/en/best-practices): CLAUDE.md structure, `/init`, plan-then-code workflow, permissions, hooks, skills, subagents, MCP, verification, parallel sessions.
* [Building effective AI agents](https://www.anthropic.com/research/building-effective-agents): workflow patterns (prompt chaining, routing, parallelization, orchestrator-workers, evaluator-optimizer), when to use agents vs workflows, tool design principles.
* [Writing tools for agents](https://www.anthropic.com/engineering/writing-tools-for-agents): tool description as contract, namespacing, context efficiency, response design, error patterns, iterative improvement.
* [Anthropic multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system): production lessons on orchestrator-worker architecture, 15x token cost, +90.2% over single-agent on research evals, failure modes, prompt engineering for orchestrators.
* [Claude Code subagents](https://code.claude.com/docs/en/sub-agents): `.claude/agents/` definitions, frontmatter (`name`, `description`, `tools`, `model`), context isolation, scope.
* [Claude Code agent teams](https://code.claude.com/docs/en/agent-teams): experimental multi-session coordination, shared task list, mailbox, display modes, hooks, limitations.
* [Claude Code worktrees](https://code.claude.com/docs/en/worktrees): `--worktree` flag, `.worktreeinclude`, subagent isolation, non-git VCS hooks.
* [2026 Agentic Coding Trends Report](https://resources.anthropic.com/hubfs/2026%20Agentic%20Coding%20Trends%20Report.pdf): empirical trends from Anthropic's customer base.

### OpenAI Codex

* [Codex - Best practices](https://developers.openai.com/codex/learn/best-practices): start with the right task context, use AGENTS.md for durable guidance, configure Codex to match the workflow, connect external systems with MCP, turn repeated work into skills, automate stable workflows.
* [Codex - Custom instructions with AGENTS.md](https://developers.openai.com/codex/guides/agents-md): how Codex reads AGENTS.md, the file hierarchy (concatenated root-down, closer files override), examples of effective sections.
* [Codex - Agent Skills](https://developers.openai.com/codex/skills): SKILL.md files in `~/.agents/skills/`, autoloaded when the task matches. Launched December 2025.
* [Codex CLI - Reference](https://developers.openai.com/codex/cli/reference): command-line options, configuration, sandbox modes.
* [openai/codex on GitHub](https://github.com/openai/codex): the lightweight terminal coding agent.
* [Introducing Codex](https://openai.com/index/introducing-codex/): product overview and positioning.

### Google Gemini

* [Set up your coding assistant with Gemini MCP and Skills](https://ai.google.dev/gemini-api/docs/coding-agents): how to keep an agent current with the evolving Gemini API, set up the Gemini Docs MCP, and enhance the environment with Gemini API Skills.
* [Gemini CLI documentation](https://developers.google.com/gemini-code-assist/docs/gemini-cli): ReAct loop, MCP-native design, output formats (`json`, `stream-json`), context window advantages, GEMINI.md durable instructions.
* [google-gemini/gemini-cli on GitHub](https://github.com/google-gemini/gemini-cli): the open-source Gemini terminal agent.

### Open standards

* [AGENTS.md specification](https://agents.md/): open Markdown standard for agent context files. Supported by Claude, Codex, Cursor, Aider, GitHub Copilot, Gemini CLI, Windsurf, Factory, Devin, RooCode, and 25+ others. Stewarded by the Agentic AI Foundation under the Linux Foundation.
* Agentic protocols (MCP, A2A, ACP, AG-UI): the inter-agent and agent-tool protocol layers referenced in Pillar 10. MCP is the most mature; the others are useful when designing multi-agent systems.

### Organizational layer

* [Scaled Agile - 5 Shifts to Build an AI-Native Workforce](https://ai-native.scaledagile.com/): the five organizational shifts referenced in Part 4. Source for ownership triad, workflow-redesign-over-tool-training, and incentive-system framing.

### Workflow orchestration

* [`agent-readiness-workflow.md`](agent-readiness-workflow.md): six in-session workflow rules (plan-mode default, subagent strategy, self-improvement loop, verification before done, demand elegance, autonomous bug fixing) extracted from Boris Cherny's published CLAUDE.md. Drop-in template for `AGENTS.md` / `CLAUDE.md`. Connects to Pillar 10 (and partly Pillars 3, 4, 7, 11).
* [`agent-readiness-skills/`](agent-readiness-skills/): three installable Claude Code skills used together with this framework. Source of truth lives here; symlink each into `~/.claude/skills/<name>` to install.
  * `cherny-workflow`: in-session workflow rules from `agent-readiness-workflow.md` as an installable skill.
  * `grill-me`: stress-test a plan via relentless interview down the decision tree, English triggers.
  * `grill-me-ru`: same skill, Russian triggers and Russian body.

### Further reading

* [Augment - How to Build Your AGENTS.md (2026)](https://www.augmentcode.com/guides/how-to-build-agents-md): practical guidance on sizing AGENTS.md files; the 150-200 line rule of thumb.
* [Hivetrail - AGENTS.md vs CLAUDE.md](https://hivetrail.com/blog/agents-md-vs-claude-md-cross-tool-standard): comparison of the two file conventions and their interaction.

### Factory.ai Agent Readiness (source for pillar count and scoring)

* [Factory.ai - Introducing Agent Readiness](https://factory.ai/news/agent-readiness): the 8-pillar / 5-level model that informed Pillars 1-9 and the binary-criteria-plus-80%-threshold scoring rule. Slash command `/readiness-report` and dashboard at `app.factory.ai/analytics/readiness`.
* [Factory.ai docs - Agent Readiness overview](https://docs.factory.ai/web/agent-readiness/overview): expanded pillar list (9 pillars including Task Discovery and Product & Experimentation), scoring rules, evaluation scopes.
