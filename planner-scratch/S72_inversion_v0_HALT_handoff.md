# S72 — Inversion v0 Phase 3 HALT Handoff

**Status:** HALT-and-redispatch. No code shipped. Recon completed; architectural impedance surfaced. Pre-ship DB snapshot landed.
**Date:** 2026-05-15
**Session:** S72 (Phase 3 implementation, attempted)
**Source dispatch:** Conversational-Runtime Inversion v0 Path A Phase 3.

---

## §1. Recon outputs

### §1.1 §59 instance count

Grep over `dnd_orchestration.py` for `^def compute_.*_directive\|^def render_` returned **18 sibling functions**:

```
compute_pacing_directive            (:1540)
compute_central_thread_directive    (:1626)
compute_consequence_directive       (:1675)
compute_commitment_directive        (:1954)  ← LOAD-BEARING; see §2
compute_init_directive              (:2140)
compute_persistence_directive       (:2338)
compute_loot_directive              (:2533)
render_state_footer                 (:2683)
compute_combat_redirect_directive   (:2889)
compute_time_directive              (:3016)
render_resolution_block             (:3815)
render_resolution_hardstop_echo     (:3889)
compute_combat_narration_directive  (:4054)
compute_scene_lifecycle_directive   (:4237)
compute_active_quest_directive      (:4486)
compute_composition_directive       (:4744)
compute_bootstrap_sequence_directive (:5046)
compute_bootstrap_card_directive    (:5347)
```

`dnd_engine.py` grep returned zero hits — confirms orchestration-layer is the §59 sibling home.

**Resolved count: 18 in `dnd_orchestration.py`.** VIRGIL_MASTER's "17" was stale (pre-S60 composition or pre-N-10 bootstrap-card additions). Phase 3 ship would add 2-4 new siblings (per-domain detection parsers + anti-gaslight directive), landing at 20-22.

### §1.2 §1b instance lineage

DOCTRINE.md line 7 (current): "five anchored project instances."

Audit of cross-spec citations:
- §1b 1st: Track 6 #5.1 SRD suggester (S26)
- §1b 2nd: NPC State-Sync (S41)
- §1b 3rd: Quest Layer v0.1 (per QUEST_LAYER §1.E + §11.12)
- §1b 4th: Composition Layer v0 (per CANON_BOOTSTRAP precedent list)
- §1b 5th: *unstamped* — likely Scene Lifecycle v1 §11.M-adjacent or a Track-5 v0.x patch; need explicit audit
- §1b 6th: N-10 CANON_BOOTSTRAP_BOT (per its §1.K self-stamp)

**Resolved: DOCTRINE.md is stale by one.** Likely sequence: at S67 DOCTRINE.md audit (line 7 stamp), 5 instances existed; CANON_BOOTSTRAP §1.K landed N-10 as #6 in a subsequent ship without DOCTRINE.md line 7 update. Phase 3 ship of Inversion v0 would anchor narration-detection-as-gate as **§1b 7th instance** AND update DOCTRINE.md line 7 to read "seven anchored project instances."

DOCTRINE.md line 21's wording ("Inversion v0's narration-detection-as-deterministic-gate may be that sixth instance") was written when DOCTRINE.md line 7 still read 5 — it predicted Inversion would be 6th. Since N-10 took 6th in the interim, line 21 also needs amendment to "seventh instance, potentially the formal sub-anchor candidate per validator-shape distinction."

**Spec citation count (5) was correct at spec-time** (referenced DOCTRINE.md's then-current stamp). Implementation-time count is 6+Inversion=7.

### §1.3 Detection insertion points hold

- `discord_dnd_bot.py:2664` — `action = message.content.strip()` in `on_message()` at line 2481. Confirmed pre-LLM-narration hook still operative.
- `discord_dnd_bot.py:2789` — `_extract_and_persist_world()` call site (S68 N-4 pattern) still operative.
- `_dm_respond_and_post()` at `discord_dnd_bot.py:3366` — LLM narration production. Unchanged.

Phase 3 insertion shape per R3 still architecturally clean.

### §1.4 N-1 hint extractor pattern operative

`mechanical_hints.py` confirmed unchanged at the pattern level (recon line numbers in `_COIN_TRANSACTION_VERBS:106`, `_narration_has_transaction_verb:136`, `_RECENT_HINTS_PER_CAMPAIGN:159`, `parse_mechanical_hints:284`). Generalization template holds: closed verb frozenset + structured-signal cooccurrence + whole-word tokenization + cross-turn LRU dedup + per-fire telemetry.

### §1.5 Prompt budget

R5 confirmed at spec time (~22k chars baseline; pre-detection parsers do not render to prompt; suggester cards render to operator channel only). No re-audit needed at Phase 3 — pre-LLM detection writes to engine state pre-prompt-construction; LLM prompt picks up post-write state at no per-fire delta.

---

## §2. Architectural impedance — namespace collision

**The blocker.** `compute_commitment_directive` (`dnd_orchestration.py:1954`, S19-era, locked §11.1-§11.D) already occupies the `commitment` semantic namespace in-tree. It is a **player-action-honor escape directive** — fires when player commits COMBAT-intent action and then attempts a scene-shift before Avrae drains the prior commitment. Five-gate function with full §59 sibling discipline; load-bearing across multiple call sites (5 cross-references).

**Spec §7.3's `dnd_commitments` table + commitment-utterance schema** uses the same `commitment` semantic for a fundamentally different concept: **NPC-utterance-commitment-tracking** for anti-gaslight rails.

The semantics are orthogonal:
- S19 `commitment_directive`: *player* committed an *action*; LLM must honor or acknowledge in next turn
- N-3.1 fold-in: *NPC* uttered a *commitment* (promise/pledge/deliverable); engine writes to table; reads back on subsequent turns for anti-gaslight

Both are valid. Both are "commitment-tracking" in plain English. Implementing both under unqualified `commitment` namespace would create cross-reading-burden indefinitely.

**Proposed amendment (for spec patch or next-session dispatch lock):**

| Spec name (current) | Proposed rename | Rationale |
|---|---|---|
| `dnd_commitments` table | `dnd_npc_commitments` | Disambiguates from S19 player-action surface |
| commitment-utterance parser | `parse_npc_commitment_utterances` (or `npc_commitment_extractor.py` matching `consequence_extractor` / `npc_extractor` / `mechanical_hints` precedent) | Names the subject (NPC); names the source (utterance) |
| anti-gaslight directive | `compute_npc_commitment_anti_gaslight_directive` | Reads from `dnd_npc_commitments`; sibling to S19's `compute_commitment_directive`, not replacement |
| F-64 doctrine anchoring | "narration-commit-gap (NPC utterance edition)" | Explicitly scopes the new doctrine to NPC-utterance surface |

This is a small, additive rename. No locked architectural shape changes. Spec §7.3 schema columns hold byte-for-byte; only the table-name and parser-name shift.

**Why HALT and not implement-with-rename:**

The Oracle §11.6 qualifier reads: *"in-place amendment applies when the upstream architectural direction-lock changes what the downstream spec depends on; not a general license for retroactive locked-spec amendment."*

This rename is *neither* of those cases — it's a discovery during implementation that the spec did not foresee. Implementing the rename silently and surfacing in handoff would:
- Set a precedent for "implementation discretion overrides locked names" (worse precedent than locked-spec amendment)
- Leave the locked spec stale relative to shipped code
- Risk future spec sessions citing `dnd_commitments` and discovering the actual table is `dnd_npc_commitments`

Cleaner pattern: HALT, surface, get operator + Oracle review on the amendment shape, then ship under amended spec.

---

## §3. Scope vs single-restart-cycle calibration

**Honest scope read on Inversion v0 v0 full ship:**

| Component | Estimated LOC | Risk |
|---|---|---|
| Schema (`dnd_npc_commitments`) | ~70 | Low — additive |
| Shared infra (telemetry helpers, suggester-card writer, three-tier router) | ~250 | Medium — new patterns |
| 4 closed-vocab parsers (txn / quest-accept / loot-drop / NPC-commitment-utterance) | ~600 (4 × ~150) | Medium per-parser; cumulative high |
| Detection insertion in `on_message` (pre-LLM at :2664) | ~150 | **HIGH** — touches load-bearing hot path |
| Post-LLM detection hook in `_extract_and_persist_world` | ~100 | Medium |
| Anti-gaslight directive injection (read-back from new table) | ~120 | Medium |
| DOCTRINE.md amendments (§1a.x sub-numbering + §1b 7th-instance + line-7 count fix) | ~80 | Low — doc |
| Closed-loop tests (per-parser + per-suggester + per-telemetry + schema-integrity + read-back roundtrip) | ~700 | Low individually; aggregated review burden |
| **Total** | **~2070 LOC** | |

Plus restart + 4 live-verify scenarios (A txn, B quest-accept, C loot-drop, D commitment+anti-gaslight).

**The §11.12-lock language:** "(b) gradual per-ship migration in observed-friction order. Big-bang multiplies blast radius; gradual preserves the per-ship sequential-commit discipline standing since S65."

§11.12 was about migrating *prior ships* under inverted discipline. But its underlying principle — *big-bang multiplies blast radius* — applies equally to shipping all four parsers + schema + anti-gaslight directive + amendments in a single restart cycle.

**Proposed sequencing (for next-session dispatch lock):**

**S73 — Inversion v0 Phase 3a (infrastructure + first domain).** Ships:
- `dnd_npc_commitments` schema (additive)
- Shared infrastructure (telemetry helpers, suggester-card writer per R4 format, three-tier confidence router)
- **One** parser: quest-acceptance (lowest cascade risk per R2; cleanest signal; aligns with §11.5 first-migration set's primary intuition)
- Detection insertion at `on_message:2664` for player-narration channel
- DOCTRINE.md §1a.x sub-numbering amendment (anchors the new doctrine before the second domain ships under it)
- Closed-loop tests for above
- Restart + live-verify Scenario B (quest-acceptance)

**S74 — Inversion v0 Phase 3b (second + third domain).** Ships:
- Transaction-completion parser (interacts with N-1 hint extractor — careful integration)
- Loot-drop parser
- Live-verify Scenarios A + C

**S75 — Inversion v0 Phase 3c (N-3.1 fold-in).** Ships:
- `parse_npc_commitment_utterances` (closed-vocab extractor, operator-narration channel post-LLM hook at `_extract_and_persist_world:2789`)
- `compute_npc_commitment_anti_gaslight_directive` (§59 sibling reading from `dnd_npc_commitments`)
- Directive injection at prompt-build site
- F-64 sixth-instance doctrine anchoring walk
- Live-verify Scenario D
- DOCTRINE.md §1b 7th-instance anchoring (lands after all four §1b-relevant surfaces ship)

This sequencing:
- Honors §11.12's gradual principle (one domain per restart cycle)
- Honors §11.5 lock (txn + quest-accept + loot-drop all ship within Inversion v0 scope — just across 3 sessions instead of 1)
- Defers N-3.1 fold-in to last (most schema-touching; depends on infrastructure being battle-tested)
- DOCTRINE.md amendments land at appropriate checkpoints (§1a.x at S73 with first surface; §1b 7th-instance at S75 after all surfaces shipped)

---

## §4. Pre-ship state

- **DB snapshot:** `/mnt/virgil_storage/virgil.db.pre-inversion-v0-20260515-164744` (20MB). Rollback target if any S73-S75 ship goes sideways.
- **Code:** no changes in flight. `dnd_orchestration.py`, `discord_dnd_bot.py`, `dnd_engine.py`, `mechanical_hints.py` at S71 lock state.
- **Specs:** `CONVERSATIONAL_RUNTIME_INVERSION_V0_SPEC.md` LOCKED + `CONVERSATIONAL_RUNTIME_INVERSION_V0_REVIEW.md` LOCKED unchanged.
- **Bot:** virgil-discord service unrestarted; running at S71 lock state.

---

## §5. Decisions needing operator + Oracle review

1. **Namespace rename (§2).** Operator + Oracle confirm proposed rename shape. Spec patch lands as `CONVERSATIONAL_RUNTIME_INVERSION_V0_SPEC_PATCH_NPC_COMMITMENT_NAMING.md` (additive patch, not amendment to locked spec body) — names the rename as implementation-discovered clarification with operator + Oracle sign-off.

2. **Sequencing (§3).** Operator confirms S73 / S74 / S75 sequencing OR proposes alternative (e.g., S73 = infrastructure + quest-accept + txn; S74 = loot-drop + commitment-fold). Code's lean: single-domain-per-restart is safer; operator may prefer two-domain-per-restart for cadence.

3. **DOCTRINE.md line 7 update.** Confirm Phase 3a ship lands the line-7 count fix (5 → 6 with N-10 anchored; bumps to 7 at Phase 3c when Inversion narration-detection anchors). Or defer DOCTRINE.md edits to a single batched amendment at Phase 3c lock.

---

## §6. Handoff tabular (WWC standard)

| Item | Value |
|---|---|
| **Session** | S72 — Inversion v0 Phase 3 (HALT) |
| **Code shipped** | None |
| **Recon outputs** | §59 = 18 (orchestration); §1b lineage 6 anchored (DOCTRINE stale by one); insertion points hold (:2664 + :2789); N-1 pattern operative; prompt budget unchanged |
| **Architectural impedance** | Namespace collision — `commitment` semantic already shipped (S19 player-action-honor); spec §7.3's `dnd_commitments` needs rename to `dnd_npc_commitments` + extractor/directive rename. Surfaced for operator + Oracle review. |
| **DB snapshot** | `/mnt/virgil_storage/virgil.db.pre-inversion-v0-20260515-164744` (20MB) |
| **HALT reason** | (1) Namespace collision not addressable in implementation discretion under Oracle §11.6 qualifier; (2) full-scope single-restart ship violates §11.12 gradual-migration principle |
| **Proposed next session** | **S73 — Phase 3a (infrastructure + quest-acceptance + DOCTRINE §1a.x amendment).** Sonnet medium per WWC cadence. Single domain ship; restart + live-verify Scenario B only. |
| **Files filed for next dispatch** | Spec patch (`*_PATCH_NPC_COMMITMENT_NAMING.md` if operator + Oracle approve rename) + S73 dispatch with single-domain scope |
| **PC push target** | This file (`planner-scratch/S72_inversion_v0_HALT_handoff.md`) |

---

## §7. Why this HALT is the correct move

Per memory feedback ("Compounding leverage > current-session output — value tests/refactors/docs/memory above ship count"):

- Half-shipping a 2000-LOC change touching `on_message` mid-context would leave the bot in a state harder to roll back than this clean HALT.
- The namespace collision discovery is genuinely useful information that the spec session missed; surfacing it cleanly produces a better spec patch than shipping silently around it.
- Single-domain-per-restart cadence honors S65's sequential-commit discipline and gives observed-friction data to feed back into per-domain threshold tuning (which §11.7 filed as v0.1 candidate).
- The compounding leverage of "S73 dispatches with corrected namespace + tight scope" exceeds the leverage of "S72 ships partial infrastructure + one parser under uncorrected namespace."

This is the work-quality move per project discipline. S73 ships clean.
