# Agent Workflow Orchestration: Reference Extract

A reference extract of in-session workflow patterns for coding agents. Focus is on **how the agent operates turn-by-turn**, distinct from how the repository is configured (`agent-readiness.md`) and how the agent thinks (`agent-readiness-behavior.md`).

**Source:** Boris Cherny's published CLAUDE.md. Boris is a core engineer on Claude Code at Anthropic. Material is extended with related published guidance from Claude Code docs so the file works as a drop-in template.

**Tradeoff note.** These rules bias toward planning, verification, and autonomy. They cost some session latency in exchange for fewer surprises, fewer rollbacks, and compounding learning across sessions. For one-shot trivial tasks, use judgment.

---

## Three layers recap

This document sits in a three-layer model:

| Layer           | File                                | What it tunes                                                       |
| --------------- | ----------------------------------- | ------------------------------------------------------------------- |
| Environment     | `agent-readiness.md`                | What the repository gives the agent (configs, tests, docs, MCP).    |
| Behavior        | `agent-readiness-behavior.md`       | How the agent thinks (assumptions, simplicity, surgical edits).     |
| **Workflow**    | **`agent-readiness-workflow.md`**   | **How the agent operates in-session (planning, subagents, lessons).** |

All three are needed. A Level 5 environment with no behavior or workflow tuning still produces uneven results.

---

## The Six Workflow Rules

### 1. Plan Mode Default

**Plan before non-trivial work. Re-plan on deviation.**

* Enter plan mode for ANY non-trivial task (3+ steps or architectural decisions).
* If something goes sideways, STOP and re-plan immediately.
* Use plan mode for verification steps, not just building.
* Write detailed specs upfront to reduce ambiguity.

**Claude Code mechanics:** plan mode is built in. Cycle into it with `Shift+Tab`, or set `defaultMode: "plan"` in `~/.claude/settings.json`. In plan mode the agent has read-only tools and produces a plan; you approve before any write happens.

### 2. Subagent Strategy

**Spawn subagents liberally to keep main context clean.**

* Use subagents liberally to keep the main context window clean.
* Offload research, exploration, and parallel analysis to subagents.
* For complex problems, throw more compute via subagents.
* One task per subagent for focused execution.

**Claude Code mechanics:** subagents live in `.claude/agents/<name>.md` (project scope) or `~/.claude/agents/<name>.md` (user scope). Each has its own context window. Define a `description` field clearly so Claude routes to the right subagent automatically. Restrict `tools:` per subagent to the minimum surface. See Pillar 11 in `agent-readiness.md` for the full subagent readiness checklist.

### 3. Self-Improvement Loop

**Capture lessons after every correction. Read them at session start.**

* After ANY correction from the user, update `tasks/lessons.md` with the pattern.
* Write rules for yourself that prevent the same mistake.
* Ruthlessly iterate on these lessons until mistake rate drops.
* Review lessons at session start for the relevant project.

**The point:** the agent's instructions improve over time as the team uses it. A correction is data; capture it. The opposite (forgetting the same correction and getting it again) is the most expensive failure mode for autonomous agents.

### 4. Verification Before Done

**Never mark a task complete without proving it works.**

* Never mark a task complete without proving it works.
* Diff behavior between main and your changes when relevant.
* Ask yourself: "Would a staff engineer approve this?"
* Run tests, check logs, demonstrate correctness.

**The mental check:** "Would a staff engineer approve this?" If yes, ship. If no, do another pass. If unsure, verify with evidence (test output, log line, diff).

### 5. Demand Elegance (Balanced)

**Pause on non-trivial changes. Ask if there is a more elegant way.**

* For non-trivial changes, pause and ask "is there a more elegant way?"
* If a fix feels hacky, ask: "Knowing everything I know now, implement the elegant solution."
* Skip this for simple, obvious fixes. Do not over-engineer.
* Challenge your own work before presenting it.

**The trigger phrase:** "Knowing everything I know now, implement the elegant solution." It forces a post-hoc rethink after the first working version. The first version often reveals the right shape; rebuild on that knowledge.

### 6. Autonomous Bug Fixing

**Given a bug report, just fix it.**

* When given a bug report, just fix it. Do not ask for hand-holding.
* Point at logs, errors, failing tests. Then resolve them.
* Zero context switching required from the user.
* Go fix failing CI tests without being told how.

**Boundary:** this assumes a Level 3+ environment (tests gate merge, CI fails loud, branch protection prevents catastrophe). On a Level 1 repo, autonomous fixing is unsafe.

---

## Task Management Convention

Two files in the repo at `tasks/`:

### `tasks/todo.md`

Checkable items for the current task. Workflow:

1. **Plan First.** Write the plan to `tasks/todo.md` with checkable items.
2. **Verify Plan.** Check in with the user before starting implementation.
3. **Track Progress.** Mark items complete as you go.
4. **Explain Changes.** High-level summary at each step.
5. **Document Results.** Add a review section to `tasks/todo.md` at the end.

### `tasks/lessons.md`

Persistent learning across tasks. Workflow:

6. **Capture Lessons.** Update `tasks/lessons.md` after corrections, with the pattern and a rule that prevents recurrence.

**Why two files:** `todo.md` is per-task and short-lived. `lessons.md` is the compounding knowledge base that grows with the team. The first is execution; the second is memory.

---

## Core Principles

Three principles that underpin all six workflow rules:

* **Simplicity First.** Make every change as simple as possible. Impact minimal code.
* **No Laziness.** Find root causes. No temporary fixes. Senior developer standards.
* **Minimal Impact.** Only touch what is necessary. No side effects, no new bugs.

These overlap with the Karpathy principles in `agent-readiness-behavior.md` (`Simplicity First` is shared verbatim; `Minimal Impact` is the same as Karpathy's `Surgical Changes`; `No Laziness` extends Karpathy's `Goal-Driven Execution` with a root-cause stance). The two documents reinforce each other.

---

## How to Apply

Three options, from cleanest to most adapted:

### Option A. Drop in verbatim

Copy the entire `## Workflow Orchestration`, `## Task Management`, and `## Core Principles` sections directly into the project's `CLAUDE.md` or `AGENTS.md`. The agent will read them on every session.

Cost: ~50 lines added to the context file on every session. Worth it if the team values consistency and the agent is the main contributor.

### Option B. Merge with existing context file

If the project already has `CLAUDE.md` / `AGENTS.md` with project-specific rules, append the workflow rules under a clearly named section:

```markdown
## Workflow Orchestration

(Six rules from this document.)

## Task Management

(Convention from this document. Adapt file paths if needed.)

## Core Principles

(Three principles.)
```

Keep project-specific rules in their own section so workflow conventions stay portable.

### Option C. Adapt to the team's reality

Some of these rules will already be in place under different names:

* "Plan First, confirm, then act" rules from your team's playbook map to **Plan Mode Default**.
* A `memory/lessons_*.md` directory or equivalent maps to **Self-Improvement Loop**.
* A pre-commit / pre-merge hook that fails on uncovered code maps to **Verification Before Done**.
* An explicit policy on what an agent can autonomously fix (formatter changes, dependency bumps) vs. what needs human review maps to a **bounded** version of **Autonomous Bug Fixing**.

For these, keep what you have. Add only the parts that are not already covered. Trim the parts that conflict with stronger team norms (for example, "Autonomous Bug Fixing" should not override a "no agent commits on customer-facing repos" rule).

---

## Related Anthropic Guidance

The six rules above lean on these Claude Code primitives. Read these once if the rules are unfamiliar:

* [Plan mode in Claude Code](https://code.claude.com/docs/en/plan-mode): read-only thinking before any write, approval gate before execution, `Shift+Tab` to cycle.
* [Subagents](https://code.claude.com/docs/en/sub-agents): `.claude/agents/<name>.md` definitions, tool allowlists, model selection per agent, automatic routing by `description`.
* [Hooks](https://code.claude.com/docs/en/hooks): enforce verification deterministically (`PreToolUse`, `PostToolUse`, `SessionEnd`, `Stop`).
* [Slash commands and skills](https://code.claude.com/docs/en/slash-commands): capture recurring workflows so the same prompt fires every time.
* [Settings reference](https://code.claude.com/docs/en/settings): `defaultMode: "plan"`, `permissions`, `env`, `teammateMode`.

---

## How this maps to `agent-readiness.md`

| Boris Cherny rule         | Pillar in `agent-readiness.md`                       | What changes in the checklist                                         |
| ------------------------- | ---------------------------------------------------- | --------------------------------------------------------------------- |
| Plan Mode Default         | Pillar 10 (Agent Tooling & Interfaces)               | L3: context file documents plan-mode triggering policy.               |
| Subagent Strategy         | Pillar 11 (Multi-Agent Coordination)                 | L2-L3: subagents defined, tool allowlists scoped, dispatch documented. |
| Self-Improvement Loop     | Pillar 4 (Documentation & Agent Context) + Pillar 10 | L3: lessons capture convention documented in context file.            |
| Verification Before Done  | Pillar 3 (Testing) + Pillar 10                       | L3: agent expected to demonstrate correctness with evidence.          |
| Demand Elegance           | Pillar 10                                            | L4: post-hoc rethink rule documented for non-trivial changes.         |
| Autonomous Bug Fixing     | Pillar 7 (Security & Governance) + Pillar 10         | L4: explicit policy on what the agent may fix autonomously.           |

The framework treats these as `AGENTS.md` / `CLAUDE.md` content under Pillar 10 (and partly Pillars 4, 11, 3, 7). This document is the off-the-shelf default for that content.

---

## Attribution

Original CLAUDE.md by Boris Cherny (Anthropic). Extended here with related guidance from Claude Code docs. Use under the same spirit as any public engineering writeup: take what works, adapt the rest, credit the source.
