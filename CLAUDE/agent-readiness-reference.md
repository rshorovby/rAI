# Agent Readiness: Reference Extract

A verbatim-leaning extraction of published material on the Agent Readiness model. Wording follows the source closely; sections, headings, lists, tables, and examples are preserved in their original structure.

**Disclaimer.** Several sections of the original source sit inside interactive accordions: pillar descriptions and level descriptions. Only **Style & Validation** (pillar) and **Level 3: Standardized** (level) appear expanded in the static page. The rest of the pillars (Build System, Testing, Documentation, Dev Environment, Code Quality, Observability, Security & Governance) and the rest of the levels (1, 2, 4, 5) are referenced by name but their full descriptive bodies are not present in the publicly fetchable HTML. Where descriptions are missing below, that is marked with `[collapsed in source]`. Pillar lists are also slightly different between the initial framework announcement (8 pillars) and the expanded docs (9 pillars); both are shown.

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

`[collapsed in source; only the pillar name appears in the announcement. See Part B for the docs description.]`

#### Testing

`[collapsed in source]`

#### Documentation

`[collapsed in source]`

#### Dev Environment

`[collapsed in source]`

#### Code Quality

`[collapsed in source. This pillar appears in the announcement but does NOT appear in the docs overview, which lists "Debugging & Observability" and "Task Discovery" in roughly the same band.]`

#### Observability

`[collapsed in source]`

#### Security & Governance

`[collapsed in source]`

### Five Maturity Levels

> Repositories progress through five levels. Each level represents a qualitative shift in what autonomous agents can accomplish.

#### Level 1: Functional

`[collapsed in source. See Part B for the docs definition.]`

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

| Project       | Language    | Level | Score |
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

### The Five Levels (docs wording)

| Level | Name         | Description                                                                                |
| ----- | ------------ | ------------------------------------------------------------------------------------------ |
| 1     | Functional   | Code runs, but requires manual setup and lacks automated validation.                       |
| 2     | Documented   | Basic documentation and process exist. Workflows are written down.                         |
| 3     | Standardized | Clear processes are defined, documented, and enforced through automation.                  |
| 4     | Optimized    | Fast feedback loops and data-driven improvement. Systems designed for productivity.        |
| 5     | Autonomous   | Systems are self-improving with sophisticated orchestration.                               |

### Scoring Mechanism

> To unlock a level, you must pass **80% of the criteria** from the previous level.

### The Nine Technical Pillars (docs wording)

The expanded docs list **nine** pillars (one more than the initial announcement). The mapping below shows pillar name, one-line description, and the example criteria each surfaces. "Code Quality" from the announcement is not present in the docs; the docs add "Task Discovery" and "Product & Experimentation".

#### 1. Style & Validation

> Linters, type checkers, and formatters.

Example criteria:
- Linter configuration
- Type checker
- Code formatter
- Pre-commit hooks

#### 2. Build System

> Deterministic compilation and verification.

Example criteria:
- Build command documented
- Dependencies pinned
- VCS CLI tools

#### 3. Testing

> Unit and integration test feedback loops.

Example criteria:
- Unit tests exist
- Integration tests exist
- Tests runnable locally

#### 4. Documentation

> AGENTS.md, README, setup instructions.

Example criteria:
- AGENTS.md
- README
- Documentation freshness

#### 5. Development Environment

> Reproducible, consistent setups.

Example criteria:
- Devcontainer
- Environment template
- Local services setup

#### 6. Debugging & Observability

> Structured logging and tracing.

Example criteria:
- Structured logging
- Distributed tracing
- Metrics collection

#### 7. Security

> Branch protection, secret scanning, code owners.

Example criteria:
- Branch protection
- Secret scanning
- CODEOWNERS

#### 8. Task Discovery

> Issue templates and structured workflows.

Example criteria:
- Issue templates
- Issue labeling system
- PR templates

#### 9. Product & Experimentation

> Analytics and measurement infrastructure.

Example criteria:
- Product analytics instrumentation
- Experiment infrastructure

### Evaluation Scopes

* **Repository scope.** A single evaluation per repository (example: branch protection enabled).
* **Application scope.** Per-application evaluation in monorepos (example: "3 / 4 apps pass linting").

### Access Methods

Four interaction approaches are listed by the docs:

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

> Enable feature in `/settings` → `Experimental` → `Readiness Report`.

### Evaluation Process

The command performs these steps:

1. **Language Detection.** Identifies repository languages (JavaScript/TypeScript, Python, Rust, Go, Java, Ruby) based on configuration files and source code.
2. **Sub-application Discovery.** Determines mono-repo vs. single service; identifies independently deployable applications.
3. **Criteria Evaluation.** Checks criteria across all five maturity levels.
4. **Report Storage.** Persists evaluation results for dashboard visualization.
5. **Summary Output.** Prints human-readable report with evaluation results.
6. **Remediation.** Coming soon; option to automatically fix failing criteria.

### Output Structure

**Level Achieved (1-5)**

- **Level 1: Functional.** Basic tooling in place.
- **Level 2: Documented.** Process and documentation established.
- **Level 3: Standardized.** Security and observability configured.
- **Level 4: Optimized.** Fast feedback and continuous measurement.
- **Level 5: Autonomous.** Self-improving systems.

**Applications Discovered.** Lists each application with description (monorepos only).

**Criteria Results Format.** Score format is `numerator/denominator`:

- Numerator: sub-applications passing the criterion.
- Denominator: sub-applications evaluated.

Example criterion output:

```text
**Style & Validation**
- Linter Configuration: 2/2 - ESLint configured in both applications
- Type Checker: 2/2 - TypeScript strict mode enabled
- Pre-commit Hooks: 0/1 - No husky or lint-staged configuration found
```

**Action Items.** "2-3 highest-impact recommendations to reach the next level."

### Additional Features

- Historical reports viewable in the web dashboard.
- Track progression, compare across repos, share with the team.
- Recommendation: Run periodically after major infrastructure changes.

---

## Part D. Dashboard Reference

### Page Description

> The Agent Readiness dashboard provides a centralized view of your organization's readiness scores across all repositories, with historical trends and detailed breakdowns.

### Navigation Path

> Settings → Analytics → Agent Readiness.

### Summary Cards

Three top-level metrics:

| Metric                  | Definition                                                                            |
| ----------------------- | ------------------------------------------------------------------------------------- |
| Organization Score      | Average readiness level across all measured repositories (rounded down).              |
| Repositories Tracked    | Number of repositories with readiness reports vs. total enabled repositories.         |
| Last Updated            | Time since the most recent readiness evaluation.                                      |

### Progress Graph

> A time-series chart showing your organization's readiness level over time.

Filters: `7d`, `1m`, `6m`, `1y`, `all`.

### Repositories Table

> A searchable, paginated table of all repositories.

Columns:

- Repository name (clickable for details).
- Level (1-5 readiness scale).
- Progress (percentage toward next level).
- Last Update (evaluation timestamp).

### Repository Detail Page

**Header.** Shows repository name, current level, last evaluation time, and refresh functionality.

**Level Accordions.** Each readiness level (Functional through Autonomous) has an expandable accordion section.

**Criterion Rows.** Each row displays:

- Name (criterion evaluated).
- Score in `[X/Y]` format.
- Status (pass/fail indicator).
- Rationale (expandable explanation).

**Coming feature.** "Soon, failing criteria will display a Fix button that triggers automated remediation."

### Refresh Methods

- **Web dashboard.** Navigate to the repository detail page and click the **Refresh** button.
- **CLI.** Run the `/readiness-report` slash command while in the repository directory.

### Metrics Calculations

- **Organization Level.** Average of all repository levels, rounded down.
- **Repository Level.** 80% threshold system where each successive level unlocks upon meeting that criterion.

### Best Practices (per docs)

- Conduct evaluations after infrastructure changes.
- Address current-level failures before advancing.
- Monitor trends via the progress graph.
- Prioritize high-impact improvements from CLI reports.

---

## Part E. API Reference

### Authentication

> All requests require: `Authorization: Bearer <api-key>`.

> API keys generated in the app's settings page (API keys section).

### Endpoint: List Readiness Reports

**GET** `/api/organization/maturity-level-reports`

#### Query parameters

| Parameter      | Type    | Required | Description                                                  |
| -------------- | ------- | -------- | ------------------------------------------------------------ |
| `repoId`       | string  | No       | Filter reports by repository ID.                             |
| `limit`        | integer | No       | Maximum number of reports to return (must be positive).      |
| `startAfter`   | string  | No       | Report ID for pagination cursor.                             |

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

**Rate limits.** Not mentioned in the public documentation.

---

## Reconciliation Notes

### Pillar count mismatch (8 vs 9)

The initial announcement says **eight technical pillars**, and lists these eight names:

1. Style & Validation
2. Build System
3. Testing
4. Documentation
5. Dev Environment
6. Code Quality
7. Observability
8. Security & Governance

The expanded docs list **nine pillars** with slightly different names:

1. Style & Validation
2. Build System
3. Testing
4. Documentation
5. Development Environment
6. Debugging & Observability
7. Security
8. Task Discovery
9. Product & Experimentation

Differences:

- **Code Quality** appears only in the announcement; not in the docs.
- **Task Discovery** and **Product & Experimentation** appear only in the docs.
- **Observability** in the announcement is **Debugging & Observability** in the docs.
- **Security & Governance** in the announcement is **Security** in the docs.

Most likely explanation: the announcement is an early framing of the framework; the docs are the live, expanded version. The docs are the authoritative current model.

### Scoring rule consistency

Both sources state: **binary pass/fail per criterion**, **80% of the criteria required to unlock a level**. The organization-level metric is described two ways across the sources: "the percentage of active repositories that reach Level 3 or higher" and "average of all repository levels, rounded down". These are two different aggregations exposed in different views; both are valid in their respective contexts.

### Counting criteria

The model evaluates **60+ criteria using LLMs**. The docs do not enumerate them. They are surfaced in the CLI output and in the dashboard repository-detail accordions, where each is a row with `[X/Y]` score and a rationale.

---

## What the source does not cover

For completeness, the following are not addressed in any of the public material and would require either the live product or further internal documentation:

- The complete list of all 60+ criteria with their precise definitions.
- The exact level assignment for each criterion (which criterion belongs to L1 vs. L2 vs. L3 etc.).
- The exact LLM grounding approach that reduced variance from 7% to 0.6%.
- Per-language adjustments to the criteria (the CLI detects JS/TS, Python, Rust, Go, Java, Ruby).
- How application-scope (monorepo) thresholds compose into the repo-level score in edge cases.

---

## How this document maps to `agent-readiness.md`

The companion file `agent-readiness.md` in this directory takes the model above and extends it with:

- An explicit tenth pillar ("Agent Tooling & Interfaces") covering CLAUDE.md, AGENTS.md, MCP, hooks, skills, and subagents, which the source model treats implicitly inside Documentation.
- An explicit eleventh pillar ("Multi-Agent Coordination") for subagents, worktrees, and agent teams readiness.
- Explicit per-level checklists for each pillar (the source does not publish the full criteria-to-level mapping).
- An optional organizational layer (the "5 Shifts") that the source does not include.
- A capability-gating table that maps agent task types to the minimum readiness level.

This document is the unmodified source content for reference. The other file is the extended working framework.
