# S74 — Inversion v0 Phase 3b Recon-First Dispatch

**Session shape:** Conversational-Runtime Inversion v0 Path A Phase 3b recon-first — second of three implementation ships per S72 sequencing. Recon-only at this session; implementation gated on findings. Targets transaction-completion + loot-drop closed-vocab parsers at pre-LLM hook (same surface as S73.1's quest-accept). Sonnet medium for recon. Conditional model-tier bump to Opus medium for implementation IF vocabulary integration with N-1 hint extractor requires synthesis (per Oracle's S74 lock).

**SEQUENCING CONFIRMED:** Phase 3a structurally complete (S73 + S73.1 + S73.2 shipped, §1a.x firing in production per S73.1 verify). S72.2 §76 Path B operating in production. Cleanup arc fully closed. Phase 3b dispatches against fully-closed §76 surface + verified Phase 3a infrastructure.

---

## Required reading (in order)

1. S73 + S73.1 + S73.2 handoffs (in conversation context) — Phase 3a state + the architectural correction (pre-LLM hook is the structurally-correct surface for player-intent surfaces)
2. `specs/CONVERSATIONAL_RUNTIME_INVERSION_V0_SPEC.md` LOCKED — primary architectural authority
3. `specs/CONVERSATIONAL_RUNTIME_INVERSION_V0_REVIEW.md` — 12 §11 decisions walked at S71
4. `quest_acceptance_parser.py` — Phase 3a parser template (closed-vocab + LRU dedup + three-tier confidence + feature-disable switch)
5. `inversion_telemetry.py` — shared telemetry primitive (reused at Phase 3b)
6. `discord_dnd_bot.py:2664` — pre-LLM hook (S73.1 wired `_run_quest_acceptance_detection` here; new parsers fire alongside)
7. `discord_dnd_bot.py` — search for `_COIN_TRANSACTION_VERBS` (N-1 hint extractor anchor; primary recon target)
8. `text files/DOCTRINE.md` — §1a, §1a.x (anchored S73, firing S73.1), §1b (6 anchored), §17, §59, §76 (6-property formal), §F-59, §F-64-candidate
9. `text files/WORKING_WITH_CLAUDE.md` — cadence + recon-first + S65 standing practices
10. `text files/VIRGIL_MASTER.md` §3 + §10 — D&D-specific Inversion v0 application + current state snapshot

---

## Recon scope (5 items — output structured findings, no implementation)

### Recon Item 1 — N-1 hint extractor vocabulary inventory

Target: `discord_dnd_bot.py` `_COIN_TRANSACTION_VERBS` (and any sibling structures like `_COIN_HINT_PATTERNS`, `_RECEIVE_VERBS`, etc.). Inventory:

- Full verb list (frozenset contents)
- Trigger patterns (regex / phrase / structured-signal co-occurrence)
- Detection insertion point (line number)
- Output target (where N-1 hints flow — `#dm-aside`, suggester card, telemetry?)
- Firing surface (pre-LLM vs post-LLM)
- Existing telemetry shape

Surface in handoff: tabular inventory of N-1's full vocabulary surface.

### Recon Item 2 — Phase 3b parser proposed vocabularies

Two parsers proposed at Phase 3b:

**Transaction-completion parser.** Detects narration of a completed purchase / sale / trade.

Closed-vocab proposal (Code expands or refines per recon):
- Buy verbs: `buy`, `buys`, `bought`, `purchase`, `purchases`, `purchased`, `pay`, `pays`, `paid`
- Sell verbs: `sell`, `sells`, `sold`, `trade`, `trades`, `traded`
- Phrasal: `i'll take it`, `it's a deal`, `here's the coin`, `we'll buy`, etc.
- Structured-signal co-occurrence: currency-mention regex (`\d+\s*(?:cp|sp|ep|gp|pp|coin|coins|silver|gold|copper)`) or item-mention against active campaign vocabulary

**Loot-drop parser.** Detects narration of party picking up / claiming an item from environment.

Closed-vocab proposal:
- Take verbs: `take`, `takes`, `takes`, `grab`, `grabs`, `pocket`, `pockets`, `pick up`, `picks up`
- Claim phrasal: `i'll keep this`, `we take the`, `pocketing the`, etc.
- Structured-signal co-occurrence: against `dnd_loot_pending` table for surfaced-but-unclaimed items

Surface in handoff: tabular vocabulary proposal for each parser.

### Recon Item 3 — Overlap analysis

Cross-reference N-1 vocabulary (Item 1) against Phase 3b proposed vocabularies (Item 2).

For each of N-1's verbs / patterns:
- Does it appear in transaction-completion proposed vocab?
- Does it appear in loot-drop proposed vocab?
- If overlap exists: what triggers N-1 vs what triggers Phase 3b parser on the same utterance?
- Classify overlap shape: same-verb-different-intent / same-verb-same-intent / different-verb-overlapping-trigger / clean-separation

Surface in handoff: overlap matrix + classification per overlapping verb.

### Recon Item 4 — Coexistence pattern proposal

Per overlap findings from Item 3, propose coexistence pattern. Three candidates:

- **(a) Separate vocabularies + discipline rule.** Vocabularies stay distinct; planner-discipline rule ("transaction-completion parser does NOT include `!game coin` keywords because N-1 owns that surface"). Cheapest; relies on discipline maintenance.

- **(b) Shared vocabulary + dispatch routing.** Single shared verb set; routing layer decides which downstream (N-1 mechanical-hint vs Phase 3b structured-state-write) fires based on structured-signal context. Bigger refactor; one source of truth for vocabulary.

- **(c) Merged single-parser with dual outputs.** N-1 + Phase 3b parser become one detection pass with two output streams (mechanical-hint to #dm-aside, structured-state to `dnd_npc_commitments` or scene-state). Largest refactor; cleanest architectural surface.

Code surfaces lean based on Item 3 overlap findings:
- Clean separation → (a)
- Material overlap with semantically-distinct intents → (b)
- Material overlap with semantically-aligned intents → (c)

Surface in handoff: recommendation + reasoning, NOT implementation.

### Recon Item 5 — Standard F-60 environmental check

Confirm Phase 3a's pre-LLM hook infrastructure clean post-S73.1 + S73.2:

- `on_message` pre-LLM hook insertion point still at line ~2664 (or document new line if S73.1 + S73.2 + S72.2 + any intervening ship moved it)
- `_run_quest_acceptance_detection` async-task pattern coexists with adding parallel calls for transaction-completion + loot-drop (any race-condition risk? telemetry ordering?)
- `inversion_telemetry.py` schema extends cleanly to new domains (or needs amendment for transaction/loot-drop signal fields)
- `dnd_npc_commitments` schema reachable from pre-LLM hook (already verified live at S73; sanity check)
- `dnd_loot_pending` table reachable from loot-drop parser surface (read accessor confirmed)
- Prompt budget unchanged (Phase 3a + 3a.1 + 3a.2 shipped; verify no surface bloat)
- Pre-LLM hook is async-task-fire-and-forget per S73.1 — does that pattern extend cleanly to two new domains, or does adding parallel async tasks introduce ordering / batching concerns?

Surface in handoff: clean / impedance findings per item. HALT-and-rediscuss if any item surfaces architectural impedance.

---

## Three locks resolved at operator + Oracle level (do not relitigate)

- **§11.2** §1a doctrinal extension → (iii) §1a.x sub-numbering. Anchored at S73, firing in production at S73.1. New parsers at Phase 3b cite §1a.x as settled doctrine.
- **§11.4** N-3.1 commitment-tracking → folded into Inversion v0. Schema shipped at S73; extractor + anti-gaslight directive land at S75 (Phase 3c).
- **§11.6** S69 amend-in-place → (a) with Oracle qualifier ("upstream architectural direction-lock changes downstream spec dependency; not a general license"). S69 Phase 3 dispatches post-S75 ship.

---

## Conditional model-tier bump per Oracle S74 lock

Sonnet medium for this recon dispatch.

**If recon Item 4 surfaces coexistence pattern (a) — clean separation:** Phase 3b implementation dispatches at Sonnet medium per Phase 3a precedent.

**If recon Item 4 surfaces coexistence pattern (b) or (c) — material vocabulary integration:** HALT-and-redispatch Phase 3b implementation at Opus medium for the architectural synthesis. Vocabulary integration affecting N-1's shipped surface is doctrinal-pattern-shaping work, not pure implementation.

---

## Recon dispatch discipline (per F-60 + S72 + S72.1 + S73.1 precedents)

- No code changes at recon
- No DB writes
- No restart
- Standard recon output: tabular inventories + classification + recommendation
- HALT-and-rediscuss if any recon item surfaces architectural impedance not anticipated by dispatch (filings are starting points, not specs)
- S73.1 added recon-discipline refinement worth folding here: "empirical-sample-the-target-surface" — for post-LLM-hook ships, sample actual LLM output to verify closed vocab is reachable. Phase 3b is pre-LLM-hook, so the symmetric question is: sample actual operator-input phrasings (from journal or memory) to verify proposed closed vocab covers operator-natural language. If recon Item 2's proposed vocabularies don't match how operator actually narrates transactions/loot-drops, surface vocabulary gaps as part of Item 2 findings.

---

## End-of-recon handoff shape (WWC tabular)

Per Phase 3a + S73.1 handoff precedent:

| Item | Value |
|---|---|
| **Session** | S74 Inversion v0 Phase 3b recon-first |
| **Files touched** | None (recon-only) |
| **Recon Item 1** | N-1 hint extractor vocabulary inventory: ... |
| **Recon Item 2** | Phase 3b parser proposed vocabularies: ... |
| **Recon Item 3** | Overlap analysis: ... |
| **Recon Item 4** | Coexistence pattern recommendation: (a)/(b)/(c) — reasoning |
| **Recon Item 5** | F-60 environmental check: clean / impedance items |
| **Model-tier recommendation for implementation dispatch** | Sonnet medium / Opus medium — per Item 4 lean |
| **HALT escalations** | None / list |
| **Next session** | S74 implementation OR S74 redispatch-at-Opus-medium per recon Item 4 lean |

---

## Filed discipline for future closure-ship + parser-coordination dispatches

S72.2 surfaced: dispatch language should name **structural requirement** (retrieval surface, write surface) + **structural property** (asymmetric break, gated rate); leave **implementation surface choice** to Code. The S72.2 dispatch said "filter applies at retrieval time" with example Python code; Code shipped `$and` clause at chromadb collection layer — same fix shape, cleaner implementation surface.

S73.1 surfaced: recon F-60 for hook-insertion ships must include **surface-vocabulary-compatibility check**, not just **insertion-point-correctness check**. Post-LLM hook ships need empirical LLM-output sample to verify closed vocab reachable. Pre-LLM hook ships (this one) need empirical operator-input sample to verify closed vocab covers natural phrasing.

Both filed forward for Phase 3b/3c dispatch language refinement.

---

## Compounding leverage at successful Phase 3b recon

(1) N-1's vocabulary surface gets documented for the first time as a doctrinal recon artifact — future planners read against canonical state rather than greppable code state.

(2) Coexistence pattern decision (a/b/c) sets precedent for Phase 3c NPC-commitment-utterance extractor's relationship to existing extractors (npc_extractor, consequence_extractor, etc.). The architectural shape locked at Phase 3b informs Phase 3c without re-litigation.

(3) Filed empirical-vocabulary-sample-the-target-surface refinement gets exercised on Phase 3b's pre-LLM surface — generalizable F-60 refinement, not Inversion-specific.

(4) Per GPT's S72.2 observation, this is the project entering "runtime architecture" phase — recon at Phase 3b is where parser-hierarchy / runtime-intent-bus architectural question earns its first concrete decision surface (not as theoretical doctrine, but as "do these two parsers share vocabulary or not, structurally").

---

Standing by post-recon for findings review + implementation dispatch (or HALT-and-redispatch at Opus medium if recon Item 4 leans toward material integration).
