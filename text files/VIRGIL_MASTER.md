# Virgil — Master System Reference

**Status:** Post-mandate-ship (D&D), post-Tier-1-cleanup, post-direction-lock. Substrate-level reframe.
**Last reconciled:** May 14, 2026 (S70 — fold of S45/S47/S49/S50/S51 deltas + substrate-level reframe per operator clarification + Oracle §2/§3 corrections applied).

This document is the canonical system reference for Virgil-the-substrate and the workloads operating on it. SESSIONS.md chronicles per-session work (predominantly D&D since S52); FAILURES.md catalogs load-bearing failure modes; DOCTRINE.md anchors numbered doctrinal rules; this doc integrates the whole.

---

## 1. What Virgil is

Virgil is a personal-AI substrate running on Jordan's server. The substrate combines deterministic engine state (SQLite, single-writer discipline, doctrinal invariants) with LLM-narrated surfaces (Discord, Telegram, web) into a unified architecture where stochastic generation is bounded by controlled canon.

The substrate's architectural premise: **controlled canonization of stochastic generation.** Stochastic LLM output is creative-bounded; deterministic engine state is structurally-bounded; the boundary between them is the load-bearing surface every workload protects.

### Current workloads

**Telegram butler** — original Virgil workload, transitioned from OpenClaw on shared web hosting to the Virgil server. Personal assistant / life-management surface. Conversational-by-nature; substrate's first instance of LLM-mediated personal data.

**virgildm.com** — onboarding site for Discord D&D bot users. Live. Web surface for substrate's largest workload.

**Discord D&D bot** — started as side project, became the magnum opus. 70+ sessions of architectural work; load-bearing-but-not-only workload. Stress-tested substrate doctrine across multi-turn narrative + structured state + operator + multiple users + six-month-campaign timescale.

### Long-arc direction

The substrate is heading toward a personal database that learns operator's life — Telegram butler is the proto-instance, D&D bot built the doctrinal foundation, future workloads inherit both. Substrate doctrine (§1a, §17, §76, §1b) generalizes across workloads by design.

---

## 2. Substrate architecture (workload-independent)

These invariants and principles apply to every workload running on Virgil.

### 2.1 Substrate invariants

- **SQLite is authoritative structured state.** All durable canon (across workloads) lives in SQLite. Chroma is non-canon retrieval surface where used.
- **Cloud router is the only path for LLM calls.** No local LLM, no direct OpenAI/Anthropic API outside the router. All LLM access centralized for cost tracking, model swapping, and rate management.
- **LLMs never directly mutate structural state** (§1a). Operator-driven gates + deterministic parsers + external-system events (Avrae for D&D, calendar/email API for butler) are the binding-decision surfaces. LLM output is content, not state.
- **Single write paths per field** (§17). One writer per field; helpers can have multiple disjoint trigger surfaces; writers enforce invariants at the helper layer.
- **Hard-delete commands require two independent gates** — archive (structural state) + typed phrase (human confirmation). Belt-and-suspenders on data loss.
- **Bot does not directly send commands to external mechanical systems.** D&D bot doesn't emit Avrae commands directly (§F-59); butler doesn't auto-execute calendar mutations without operator approval (same shape generalized). Suggestions go to operator approval surface; bot proposes, operator commits.
- **Validated-suggester pattern** (§1b) is the canonical interaction shape across workloads. Six anchored project instances post-N-10; the pattern is substrate-level, not D&D-specific.

### 2.2 Conversational-Runtime Inversion (substrate-level direction-lock)

Three-way external review (planner + GPT + Gemini) locked next architectural arc post-S68. Largest doctrinal direction-lock since "controlled canonization of stochastic generation." The principle is substrate-level — applies to every Virgil workload, with workload-specific application landing as each earns architectural review.

**Load-bearing framing:**
- **Commands are BIOS** — session-zero/structural slashes stay
- **Engine is OS** — deterministic state machinery; substrate invariants from §2.1 hold
- **Conversation is UI** — narration-detection feeds engine via deterministic parsers

**Litmus test:** *"Would a good human DM stop the session to operate software for this?"* — generalizes:
- Butler: *"Would a good personal assistant make you type slash commands?"*
- Web: *"Would a good onboarding flow make you type explicit form-field names?"*
- Future workloads inherit the same litmus shape.

**§1a survives via inverted surface.** Narration-detection IS the deterministic gate (parser + structured signals + engine writer). Doctrinal extension shape is §11.2 candidate at Inversion spec review (lean iii §1a.x sub-numbering; operator + Oracle territory).

**Workload-specific application is filed at each workload's review session.** D&D is first; D&D-specific Inversion v0 details live in §3. Butler-specific application earns its own architectural arc when butler review opens. Substrate principle stays workload-agnostic.

---

## 3. The D&D workload — architectural specifics

The Discord D&D bot is the substrate's largest and most-developed workload. Architecture below is D&D-specific; substrate doctrine in §2 governs.

### The motion-system stack (mandate piece 1, 2, 3 + N-10)

Four architectural primitives shipped between S52-S68 + N-10 post-S68.

**Scene Lifecycle v1 (S52, S53 patch, S63 patch)** — scene-level cadence primitive. Stale-turn counter; soft/hard tier compression directives; climactic-hold suppression. §1.F activity-signal set restricted to operator-driven and Avrae-driven signals (LLM-extracted signals dropped per F-64 candidate framing).

**Quest Layer v0 + v0.1 (S54-S57)** — campaign-level commitment spine. `dnd_quests` 5-status state machine; audit log; NPC-voiced offer cards via `#dm-aside`. §1b third-instance anchored. Cosine-similarity paste-detection dropped at v0.1 — crystallized "no calibration-bound auxiliary" as substrate discipline.

**Composition Layer v0 + v0.x (S58-S62)** — where-are-we anchoring. `dnd_quest_acts` table; `current_act_id`; engine-deterministic act transitions; pressure directive renders current act. §1b fourth-instance anchored via Reading-2-direct.

**Canon Bootstrap Bot v0 + v0.1 (N-10, post-S68)** — authored-canon-volume primitive. `/bootstrap premise:"..."` with per-element `#dm-aside` cards. §1b sixth-instance anchored. Operator confirmed option-3 authoring (premise-only); bot writes skeleton.md as side effect of operator-approved cards.

### D&D-specific invariants

- **Avrae owns mechanics; Virgil owns narrative.** Mechanical resolution (rolls, HP, spell slots, rests, currency, inventory) is Avrae's domain. Narrative resolution is Virgil's. Crossings require explicit doctrinal walk.
- **`skeleton_origin=1` rows are authored canon** — parsers cannot overwrite. Bootstrap flow writes via operator-slash approval, not parser side-effect.
- **Avrae uses message edits as state transitions** — always wire `on_message` AND `on_message_edit`. Roll results land via edit, not initial post.
- **Discord transport is a thin shell** — no gameplay logic in `discord_dnd_bot.py` except routing. Orchestration owns rules-engine logic; engine owns SQLite.

### Tier 1 cleanup arc (S65-S67) — CLOSED

Eleven fixes shipped across four sessions (S65, S65.1, S66, S67). Front-door bugs, world-state-responds layer, durability + §76 audit. Standing practices adopted: pre-ship snapshot, per-fix rollback notes, sequential commits with atomic test verify, feature-disable switches.

§76 audit at S67 surfaced 3 NEW 4/4 surfaces (consequences.summary, npcs.description fold, chroma DM-stores). Initial classification ("mitigated by promotion gates / distance cutoffs") was insufficient — Phase C HALTED, filed for S67.1. S72.1 audit re-classified under proposed 6-property test: S1+S2 mitigated (4/6 + 4-5/6), S3 6/6-full surface. **S72.2 closure shipped**: Path B-structural on chroma DM-stores (read-side filter `role='user'` only at `chroma_search`); §76 main entry promoted to formal 6-property framing; §76.1 (rate-unlimited write) + §76.2 (verbatim re-injection) anchored as formal sub-clauses. ROADMAP item 6 retired.

### D&D-specific Inversion v0 application

Substrate principle in §2.2; D&D-specific application below.

**Slash sprawl correction.** D&D workload accumulated 47 slash commands (per S70 Inversion Phase 1 recon, R2: 47 slashes / 7 groups). Inversion v0 first-migration set: transaction + quest-acceptance + loot-drop. Subsequent migrations in observed-friction order. Tier 1 BIOS slashes remain.

Inversion v0 Phase 1 dispatched at S70; Phase 2 review pass at S71; Phase 3 implementation dispatches after operator lock.

---

## 4. Doctrinal foundation (cross-references to DOCTRINE.md)

The doctrine numbers are stable for cross-reference. Load-bearing across workloads:

- **§1a** — LLM never decides binding state. Substrate-level invariant; surface varies per workload (slash + Avrae for D&D; slash + calendar/email API for butler; slash + form-submit for web).
- **§1a.x** — Deterministic-gate authority via narration-detection (sub-numbered under §1a per §14.1 precedent). Closed-vocab parser producing high-confidence structured signal from narration is equivalent to operator-typed slash for §1a's binding-decision restriction. ANCHORED at S73 Inversion v0 Phase 3a (quest-acceptance narration-detection parser). Four prerequisites per DOCTRINE.md §1a.x.
- **§1b** — Validated-suggester pattern. Substrate-level. Six anchored project instances post-S73 per DOCTRINE.md §1b running-list (Track 6 #5.1 → NPC State-Sync → Quest Layer v0.1 → Composition Layer v0 → N-10 Canon Bootstrap → Inversion v0 Phase 3a quest-acceptance narration-detection). The pattern generalizes to butler reminder/task proposals.
- **§1b.1** — Clarification handshake via `#dm-aside`. Sub-clause anchored at S77. M-DELAYED in-fiction primary + Layer A multi-paste + Layer B `bot.wait_for` handshake. Decentralized parser-output aggregator; future parsers register against aggregator at their respective ships.
- **§17** — Single write paths per field. Substrate-level.
- **§59** — Pure-function sibling pattern. Each `compute_*_directive` / `compute_*_suggester` / `render_*` / `build_*_context` / `compute_setup_plan` is a separable pure function. 23 instances at S72.1 audit (21 in `dnd_orchestration.py`, 1 in `dnd_engine.py` (`build_dm_context`), 1 in `discord_dnd_bot.py` (`compute_setup_plan` — S23 #3 first non-orchestration sibling)); D&D-specific application of substrate's pure-function discipline. Naming-convention drift surfaced at audit: `compute_*_directive` and `compute_*_suggester` dominate (directive emits prompt-block text + signal dict; suggester emits proposal candidate or None + signal dict); `render_*` siblings emit text + structural metadata (state-footer, resolution-block); `build_*_context` siblings assemble full prompt context from multiple inputs.
- **§76** — Recursive-hallucination memory loop / 4-property contamination test (LLM-writable + persisted + retrieved + narratively-inferential) PLUS 6-property urgency test (§76.1 rate-unlimited write + §76.2 verbatim re-injection) for closure-shape classification. Substrate-level; applies anywhere LLM output writes to persisted retrievable state. **6-property test mandatory** for all 4/4 surface audits post-S72.2 (running 4-property test alone risks misclassifying 6/6 surfaces as mitigated). Four anchored project instances (S22/S32/S36/S39 → S67.1 cluster of three → S72.2 chroma closure).
- **§77** — Atmospheric continuity (instruction-side enforcement). D&D-specific.
- **§78** — Four-layer enforcement composition. D&D-specific to combat boundary handling.
- **§F-59** — Bot→Avrae prohibition. D&D-specific; substrate-level generalization: bot doesn't auto-execute external-system mutations without operator approval.
- **§F-64 (CANDIDATE)** — Narration-commit gap as systemic contamination surface. 5 anchored instances; sixth pending N-3.1 ship. Substrate-level (any LLM-mediated workload risks narration-claims-without-engine-enforce).

---

## 5. Operational discipline (substrate-level)

Operator-facing rules earned doctrinal weight across the project arc.

1. **The system evolves from observed friction, not anticipated friction.**
2. **One problem fixed at a time, confirmed working, then move on.**
3. **Diagnostic before treatment.** Smallest log line that answers the question, then decide.
4. **Inventory before patch; evidence before speculation.**
5. **When operator states a design preference, that's a constraint not a suggestion.**
6. **Two independent gates before destruction.**
7. **Doc updates land same-turn as Code handoff** (filed S70 post-Inversion-sketch).

---

## 6. Build hygiene (the load-bearing walls)

The architecture stays clean because patches are scoped to single concepts. Watch for:

- Giant branching conditionals where there used to be one decision
- Hidden side effects (functions that secretly mutate DB state)
- Duplicated state logic across workloads (two functions deciding the same thing slightly differently)
- Prompt logic leaking into orchestration (rules engine starting to "know" tone)
- Orchestration leaking into transport (slash commands doing logic instead of routing)
- "Temporary" exceptions becoming permanent

Substrate boundaries are the load-bearing walls — don't drill through them, even temporarily.

The pattern that protects this: **incremental, single-responsibility patches. One step at a time. Live-verify each one. Refuse to batch "while we're here" changes into a step that wasn't designed for them.**

---

## 7. State persistence and durability (post-S67, substrate-level)

- WAL mode enabled at `db_init` (per workload's DB)
- Nightly systemd timer (`virgil-backup.timer` @ 03:30 PDT) → `virgil_backup.sh` (sqlite3 .backup + integrity_check + 30d retention + PC push)
- Restore drill procedure documented at `planner-scratch/restore_drill.md`
- PRAGMA foreign_keys=ON enforced at engine init (D&D bot per S61; substrate pattern for other workloads at their architectural ships)

---

## 8. Multiplayer architecture (D&D-specific)

Multiplayer is NOT deferred for D&D. Solo and multiplayer are equally-weighted.

Ships 1-A-2-3 complete (S33-S36). Listener verification + dumb combat + combat-boundary hardening shipped across S43-S45. Combat session structurally isolated per guild; turn-batcher handles cross-talk with ⏳ reaction for off-turn input.

Filed-not-sequenced: F-006 multiplayer turn-gating two-tier banter buffer (v1.x when friends join). F-046 prompt injection guard (pre-non-friend-multiplayer ship).

---

## 9. Cross-workload future state (filed direction, not committed architecture)

The substrate is heading toward unified personal-data canon across workloads. Speculative shapes worth surfacing now so future architecture inherits substrate doctrine cleanly:

- **Shared identity surface.** Operator authentication once at substrate level; D&D / butler / web all consume.
- **Shared event ledger.** Calendar events, D&D session schedules, life-pattern observations land in single substrate event surface. Each workload reads what's relevant.
- **Shared LLM router config.** Cost tracking, model selection, rate management already substrate-level; future workloads inherit without rebuilding.
- **Cross-workload context.** Butler learns operator prefers asynchronous communication post-9pm; D&D bot inherits the constraint when scheduling session reminders. Substrate-level personal-canon read.

None of this is committed architecture. Filing reflects the substrate's intended trajectory; observed friction drives when each ships.

---

## 10. Current state snapshot

- Telegram butler operational (transitioned from OpenClaw)
- virgildm.com operational (D&D bot onboarding)
- Discord D&D bot operational with full F-54 motion-system stack
- 24 §59 sibling instances (D&D workload; 22 in `dnd_orchestration.py` + 1 in `dnd_engine.py` + 1 in `discord_dnd_bot.py` — post-S77 `compute_pending_clarification_directive` addition; quest-acceptance parser at S73 is closed-vocab parser, NOT §59 sibling shape)
- 6 §1b anchored instances + §1b.1 sub-clause anchored at S77 (substrate-level pattern, D&D applications; sixth §1b instance = S73 Inversion v0 Phase 3a quest-acceptance narration-detection; §1b.1 = clarification-handshake primitive)
- §1a.x anchored at S73 (deterministic-gate authority via narration-detection; sub-numbered extension per §14.1 precedent)
- Inversion v0 Phase 3a shipped at S73: closed-vocab quest-acceptance parser + `#dm-aside` suggester card + `dnd_npc_commitments` schema (N-3.1 fold-in skeleton) + per-fire JSONL telemetry + feature-disable switch + 141 closed-loop tests green
- Inversion v0 §1b.1 Clarification Handshake Primitive shipped at S77: `clarification_handshake.py` module + `pending_clarification` column on `dnd_scene_state` + decentralized parser-output aggregator at pre-LLM hook + M-DELAYED in-fiction primary path + Layer A multi-paste fallback + Layer B `bot.wait_for` listener + 12 new telemetry event types + 8 new test files (112 new assertions green)
- Inversion v0 Phase 3b shipped at S78: `transaction_completion_parser.py` + `loot_drop_parser.py` (5 narration-detection parser surfaces total post-S78 — quest_accept pre-LLM, transaction_completion pre/post LLM, loot_drop player + LLM); NEW post-LLM aggregator hook at `_dm_respond_and_post:4251`; 3 new test files (86 new assertions green). N-1 (`mechanical_hints`) unchanged per R3 (c) surface-separated lock. §1b.1 M-DELAYED primary path empirically activated
- **§F-64 ANCHORED at S81** post-S79 walk + S80 council pressure-test (three reviewer overrides applied: Gemini Q1 framing reword, Gemini Q3 placement change, GPT+Oracle Q5 deferral). 7-instance cluster; full architectural-relationship map; §1a.x is the architectural closure
- **§82 CANDIDATE filed at S81** — Instruction-Side Compliance doctrine candidate (2 instances; deferred until 3 across distinct directive surfaces). Compliance-failure telemetry instrumented via generic `directive_compliance_failure` event (S77 prototype refactored; central_thread detector NEW at S81). Two detector surfaces operating: `pending_clarification`, `central_thread`. Filed-forward detectors: combat_narration MUST/MUST-NOT, commitment_directive, pacing_directive, HARD STOP RULES 1-7
- **Doctrine-graph-proliferation-watch** landed in WWC at S81 per GPT S80 closing macro-observation (76+ anchored doctrines; sub-clause-vs-top-level discipline + anchor-threshold reinforcement + cross-doctrine relationship-map maintenance)
- 8 new tables shipped post-mandate (D&D)
- 47 slash commands per S70 Inversion Phase 1 recon (D&D; Inversion arc trimming this materially)
- Tier 1 cleanup closed at S67
- N-10 + S68 N-4 shipped
- Inversion v0 spec DRAFT awaiting Session 2 lock
- S69 Causality Engine spec LOCKED, Phase 3 paused pending Inversion ship
- Substrate doctrine generalized to non-D&D workloads as filed direction