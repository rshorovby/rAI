---
type: meta
title: Log
description: Append-only chronology of ingest, query, lint.
tags: [log, meta]
status: reviewed
timestamp: 2026-07-17T17:00:00Z
---

# Log

Формат записи: `## [YYYY-MM-DD] <op> | <title>`

## [2026-07-17] init | Knowledge vault scaffold

- Создан Obsidian vault `knowledge/` (LLM Wiki + OKF-lite).
- Seed: strokes, concepts, errors stubs.
- Источники: Karpathy LLM Wiki + Google OKF conventions (frontmatter only).

## [2026-07-17] ingest | Feel Tennis series (Parts 1–3)

- Sources: [[feeltennis-part1-intention]], [[feeltennis-part2-biomechanics]], [[feeltennis-part3-biomechanics-first]]
- New concepts: [[clear-intention]], [[biomechanics-first]], [[repeatable-swing]], [[effortless-power]]
- Status: **unverified**

## [2026-07-17] ingest | Feel Tennis stroke guides + myth

- Sources: [[feeltennis-technique-myth]], [[feeltennis-serve-7steps]], [[feeltennis-modern-forehand]], [[feeltennis-one-handed-backhand]], [[feeltennis-forehand-volley]], [[feeltennis-backhand-volley]]
- New concept: [[form-vs-technique]]
- Updated strokes: [[forehand]], [[backhand]], [[serve]], [[volley]]
- Updated: [[split-step]], [[contact-point]], [[clear-intention]], [[late-contact]], [[index]], [[home]]
- Status: **unverified** (по решению куратора)
- Gaps: 2HBH dedicated guide; grip concept page; drills library
- URLs:
  - https://www.feeltennis.net/tennis-technique-myth/
  - https://www.feeltennis.net/serve-technique/
  - https://www.feeltennis.net/modern-forehand-technique/
  - https://www.feeltennis.net/one-handed-backhand-technique/
  - https://www.feeltennis.net/forehand-volley-technique/
  - https://www.feeltennis.net/backhand-volley-technique/

## [2026-07-17] ingest | Feel Tennis tips batch (21)

- Classification map: [[feeltennis-map]]
- New concepts: [[topspin-roll]], [[ball-feel]], [[racquet-path]], [[aim-calibration]], [[gradual-acceleration]], [[ground-force]], [[balance]]
- New stroke: [[backhand-slice]]
- New drills: [[mini-tennis-contact]], [[racquet-path-two-hand]], [[slice-cut-the-net]]
- 21 sources `feeltennis-*.md` in wiki/sources/
- Updated: [[effortless-power]], [[contact-point]], [[late-contact]], [[footwork]], [[forehand]], [[backhand]], [[clear-intention]], [[index]], [[home]]
- Status: **unverified**
- Gap: 2HBH still thin; relaxed-play drills not fully transcribed from video

## [2026-07-17] ingest | Feel Tennis batch 3 (15+1 skip)

- 15 new sources; skip duplicate [[feeltennis-modern-forehand]]
- New concepts: [[grip]], [[strike-zone]], [[universal-swing]], [[still-head]], [[free-hitting]]
- New drill: [[racket-on-hip]]
- Updated: [[unit-turn]], [[late-contact]], [[gradual-acceleration]], [[topspin-roll]], [[racquet-path]], [[feeltennis-map]], [[index]], [[home]]
- Status: **unverified**

## [2026-07-17] ingest | Feel Tennis batch 4 (14)

- Sources: weight-transfer pelvis, visual illusions, shoulder/hip rotation, ball-machine progressions, Slinger review (low-pri), time perception, power-vs-risk, 1HBH grip, hold racket, balance drills, graze topspin, racket-as-weight, short-ball footwork
- New concepts: [[hip-rotation]], [[shoulder-rotation]], [[visual-illusions]], [[time-perception]], [[racket-as-weight]]
- New drill: [[count-for-more-time]]
- Updated: [[weight-transfer]], [[balance]], [[grip]], [[topspin-roll]], [[footwork]], [[feeltennis-map]], [[index]], [[home]]
- Status: **unverified**

## [2026-07-18] ingest | Николаев, Степанова 2012 (MPGU textbook)

- Overview: [[nikolaev-stepanova-2012]]
- Chapters: [[nikolaev-2012-serve]], [[nikolaev-2012-footwork]], [[nikolaev-2012-groundstrokes]], [[nikolaev-2012-net]]
- New concept: [[mezhdudarnoe-vremya]]
- Updated: [[serve]], [[footwork]], [[forehand]], [[backhand]], [[backhand-slice]], [[volley]], [[contact-point]], [[gradual-acceleration]], [[index]], [[home]]
- Raw: pointer only (`raw/inbox/2026-07-18-nikolaev-stepanova-2012.md`) — PDF не в git
- Status: **unverified**
- Note: first non–Feel Tennis source; contradictions on acceleration/firmness documented

## [2026-07-18] ingest | Джумок А.А. 2020 (РГУФКСМиТ)

- Overview: [[dzhumok-2020]]
- Chapters: [[dzhumok-2020-fundamentals]], [[dzhumok-2020-movement-cycle]], [[dzhumok-2020-serve]], [[dzhumok-2020-return]], [[dzhumok-2020-groundstrokes]], [[dzhumok-2020-net]]
- New strokes: [[return]], [[overhead]]
- Updated: [[grip]], [[footwork]], [[split-step]], [[racquet-path]], [[ground-force]], [[gradual-acceleration]], [[serve]], [[forehand]], [[backhand]], [[backhand-slice]], [[volley]], [[index]], [[home]]
- Raw: pointer only (`raw/inbox/2026-07-18-dzhumok-2020.md`) — PDF не в git
- Status: **unverified**
- Note: third voice; teaching closed-first + energy-fusion vs FT relax/open documented

## [2026-07-18] ingest | 2HBH batch

- New stroke: [[backhand-2h]]
- Sources: [[feeltennis-verdasco-2hbh]], [[feeltennis-2hbh-power-errors]], [[feeltennis-backhand-illusions]], [[mouratoglou-2hbh]], [[petrovici-tiuca-2025-2hbh]]
- Updated: [[backhand]], [[grip]], [[unit-turn]], [[hip-rotation]], [[weight-transfer]], [[visual-illusions]], [[ground-force]], [[index]], [[home]], [[feeltennis-map]]
- Raw: `raw/inbox/2026-07-18-2hbh-batch.md`
- Status: **unverified**
- Soft tension: non-dom Eastern-only (FT) vs Eastern/SW (Mouratoglou/Petrovici)

## [2026-07-18] policy | modern defaults for hard contradictions

- New: [[policy-modern-defaults]]
  - P1 accel/wrist → FT gradual + ground-force; not Nikolaev jerk/firm wrist
  - P2 teaching stances → open/semi/neutral OK early
  - P3 power stances → open/semi are attacking, not defense-only
- Updated: [[gradual-acceleration]], [[footwork]], [[ground-force]], [[forehand]], nikolaev/dzhumok contradiction sections, [[home]], [[index]], [[open-questions]]

## [2026-07-18] policy | keep P1 modern; reopen P2/P3 stances

- [[policy-modern-defaults]]: P1 remains modern; P2 teaching stances + P3 power stances back to OPEN
- Restored Dzhumok stance claims on [[footwork]]; contradiction notes on dzhumok fundamentals/groundstrokes
- [[open-questions]] / [[home]] updated

## [2026-07-18] review | bulk approve all wiki pages

- Flipped frontmatter `status: unverified` → `reviewed` on **120** pages (concepts, strokes, errors, drills, sources, …)
- Remaining open policy: P2/P3 stances + soft 2HBH grip (do not block RAG; see [[policy-modern-defaults]] / [[open-questions]])
- Next: wire reviewed wiki into `prompts.py`

## [2026-07-18] policy+wiring | P2/P3 situational, 2HBH grip, wiki→prompts

- [[policy-modern-defaults]]: P2/P3 RESOLVED situational; 2HBH grip Eastern default / SW ok
- Code: `wiki_context.py` loads reviewed pages by intake stroke into system/follow-up prompts
- `analyzer.py` / `bot.py`: pass stroke; session stores stroke for follow-up
- Tests: `tests/test_wiki_context.py`
