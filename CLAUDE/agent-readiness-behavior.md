# Karpathy-Inspired Agent Behavior Guidelines: Reference Extract

A reference extract of public guidelines designed to reduce common LLM coding mistakes when working with coding agents. Wording follows the source closely.

**Source:** [github.com/forrestchang/andrej-karpathy-skills](https://github.com/forrestchang/andrej-karpathy-skills) (MIT License). Derived from [Andrej Karpathy's public observations](https://x.com/karpathy/status/2015883857489522876) on LLM coding pitfalls.

**Tradeoff note (from source):** These guidelines bias toward caution over speed. For trivial tasks (simple typo fixes, obvious one-liners), use judgment. The goal is reducing costly mistakes on non-trivial work, not slowing down simple tasks.

---

## The Problems

Quoted from the original post:

> The models make wrong assumptions on your behalf and just run along with them without checking. They don't manage their confusion, don't seek clarifications, don't surface inconsistencies, don't present tradeoffs, don't push back when they should.

> They really like to overcomplicate code and APIs, bloat abstractions, don't clean up dead code... implement a bloated construction over 1000 lines when 100 would do.

> They still sometimes change/remove comments and code they don't sufficiently understand as side effects, even if orthogonal to the task.

---

## The Solution: Four Principles

| Principle                  | Addresses                                                       |
| -------------------------- | --------------------------------------------------------------- |
| **Think Before Coding**    | Wrong assumptions, hidden confusion, missing tradeoffs          |
| **Simplicity First**       | Overcomplication, bloated abstractions                          |
| **Surgical Changes**       | Orthogonal edits, touching code you shouldn't                   |
| **Goal-Driven Execution**  | Leverage through tests-first, verifiable success criteria       |

---

## Principle 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

LLMs often pick an interpretation silently and run with it. This principle forces explicit reasoning.

Before implementing:

* **State your assumptions explicitly.** If uncertain, ask.
* **If multiple interpretations exist, present them.** Don't pick silently.
* **Push back when warranted.** If a simpler approach exists, say so.
* **Stop when confused.** Name what's unclear. Ask.

---

## Principle 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

Combat the tendency toward overengineering:

* No features beyond what was asked.
* No abstractions for single-use code.
* No "flexibility" or "configurability" that wasn't requested.
* No error handling for impossible scenarios.
* If you write 200 lines and it could be 50, rewrite it.

**The test:** Would a senior engineer say this is overcomplicated? If yes, simplify.

---

## Principle 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:

* Don't "improve" adjacent code, comments, or formatting.
* Don't refactor things that aren't broken.
* Match existing style, even if you'd do it differently.
* If you notice unrelated dead code, mention it. Don't delete it.

When your changes create orphans:

* Remove imports/variables/functions that YOUR changes made unused.
* Don't remove pre-existing dead code unless asked.

**The test:** Every changed line should trace directly to the user's request.

---

## Principle 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform imperative tasks into verifiable goals:

| Instead of...      | Transform to...                                                  |
| ------------------ | ---------------------------------------------------------------- |
| "Add validation"   | "Write tests for invalid inputs, then make them pass"            |
| "Fix the bug"      | "Write a test that reproduces it, then make it pass"             |
| "Refactor X"       | "Ensure tests pass before and after"                             |

For multi-step tasks, state a brief plan:

```text
1. [Step] -> verify: [check]
2. [Step] -> verify: [check]
3. [Step] -> verify: [check]
```

Strong success criteria let the agent loop independently. Weak criteria ("make it work") require constant clarification.

### The key insight (Karpathy)

> LLMs are exceptionally good at looping until they meet specific goals... Don't tell it what to do, give it success criteria and watch it go.

---

## Worked Examples

Concrete scenarios from the source's EXAMPLES.md.

### Example 1: Think Before Coding

A user requests "export user data". A naive agent silently assumes: all users should be exported, in a specific file format, with particular fields, to a specific location. The better behavior: list uncertainties.

* "Export all users, or a filtered subset?"
* "Which format: file download, email attachment, or API endpoint?"
* "Which fields: full profile, or a sanitized subset?"

### Example 2: Simplicity First

A user asks to calculate a discount. A naive agent builds a Strategy pattern with a configuration class and pluggable discount types. The simpler version that fits the actual request:

```python
def apply_discount(amount, percent):
    return amount * (percent / 100)
```

Introduce complexity only when actual requirements demand it.

### Example 3: Surgical Changes

A user reports that empty-string email validation lets bad input through. The fix: handle the empty-string case. A naive agent also adds username validation, improves the email regex while there, and reformats the file. The surgical version: change only the empty-string check.

### Example 4: Goal-Driven Execution

Instead of "I will review and improve":

1. Write a failing test that reproduces the issue.
2. Implement the fix.
3. Verify the test passes.
4. Run the full suite to check for regressions.

The principle behind all four examples:

> Good code is code that solves today's problem simply, not tomorrow's problem prematurely.

---

## How to Apply These Guidelines

Three options, from most-integrated to most-portable:

### Option A. Plugin (Claude Code)

From within Claude Code:

```text
/plugin marketplace add forrestchang/andrej-karpathy-skills
/plugin install andrej-karpathy-skills@karpathy-skills
```

Installs the guidelines as a Claude Code skill, available across all projects.

### Option B. Per-Project CLAUDE.md

New project:

```bash
curl -o CLAUDE.md https://raw.githubusercontent.com/forrestchang/andrej-karpathy-skills/main/CLAUDE.md
```

Existing project (append):

```bash
echo "" >> CLAUDE.md
curl https://raw.githubusercontent.com/forrestchang/andrej-karpathy-skills/main/CLAUDE.md >> CLAUDE.md
```

### Option C. Merge into AGENTS.md / CLAUDE.md by hand

Copy the four principles into the agent context file at repo root. Pair with project-specific guidance.

```markdown
## Behavioral Guidelines (Karpathy-inspired)

1. Think before coding: surface assumptions, ask when ambiguous, present tradeoffs.
2. Simplicity first: minimum code that solves the problem, no speculative abstractions.
3. Surgical changes: touch only what the task requires, match existing style.
4. Goal-driven execution: define success criteria, loop until verified.

## Project-Specific Guidelines

- Use TypeScript strict mode
- All API endpoints must have tests
- Follow the existing error handling patterns in `src/utils/errors.ts`
```

The source explicitly designs the guidelines to be merged with project-specific rules; they do not replace them.

---

## Working Test (per source)

These guidelines are working if you see:

* **Fewer unnecessary changes in diffs.** Only the requested changes appear.
* **Fewer rewrites due to overcomplication.** Code is simple the first time.
* **Clarifying questions come before implementation,** not after mistakes.
* **Clean, minimal PRs.** No drive-by refactoring or "improvements".

---

## How this document maps to `agent-readiness.md`

These guidelines complement the readiness model rather than overlap with it. The readiness model evaluates the **environment** (does the repo make agents effective?). These guidelines tune the **agent's behavior** (does the agent act sensibly?). A repo can be Level 5 on readiness but agents still misbehave if no behavioral guidelines are loaded.

The natural fit is:

* **Pillar 4 (Documentation & Agent Context).** The agent context file cheatsheet recommends a `Behavioral Guidelines` section; the four principles above are the off-the-shelf default to put there.
* **Pillar 10 (Agent Tooling & Interfaces).** At L3 the checklist requires the `AGENTS.md` / `CLAUDE.md` to be tuned. Including the four principles is the minimum bar for behavioral tuning.

---

## License

The source repository is published under the MIT License. The summary, quotes, and worked examples above are reproduced under that license. Attribution: original guidelines by Forrest Chang (`forrestchang/andrej-karpathy-skills`), based on Andrej Karpathy's public observations.
