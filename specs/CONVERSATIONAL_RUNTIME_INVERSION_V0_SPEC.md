# Conversational-Runtime Inversion v0 — Spec (DRAFT)

**Status:** DRAFT — Phase 1 / Session 1 output. §11 decision points surfaced for Phase 2 walk-through; locks deferred to operator + Oracle review.
**Date:** 2026-05-15
**Authorized:** Three-way convergent review (Claude planner + GPT + Gemini) locked direction post-S69-pause. Doctrinal direction-lock — largest since the original "controlled canonization of stochastic generation" framing.
**Source sketch:** `planner-scratch/conversational_runtime_inversion_v0_sketch.md` (corrected 2026-05-15 — S69 framing recast from "resumption from shipped state" to "locked-spec-pre-implementation amend-in-place").

---

## §1. Proposed decisions

Code's recommendations from sketch synthesis + Phase 1 recon. **These are not locks.** Operator + Oracle walk each §11 candidate in Session 2.

1. **Detection vocabulary at v0 — closed-vocabulary verb-and-signal parsers per domain.** Sketch §5 lean (a). N-1 hint extractor pattern (`mechanical_hints.py`) generalizes cleanly per R1; LLM classifier (b) and hybrid (c) file v1.x.

2. **§1a doctrinal extension shape — file decision to Oracle.** Sketch §7. No confident code-side lean among (i) §1a in-place amendment, (ii) §1c new doctrine, (iii) §1a.x sub-numbering. Operator + Oracle territory; affects downstream citation in future specs.

3. **§1b validated-suggester interaction — parallel surfaces.** Sketch §8 lean (a). Existing §1b anchored-instances (Quest Layer v0.1, Composition Layer v0, NPC State-Sync, Track 6 #5.1, N-10) hold unchanged; narration-detection sits parallel as a high-confidence shortcut. (b) extension is the likely v1.x position after observed friction.

4. **N-3.1 commitment-tracking — folds into Inversion v0.** Sketch §9 lean (a). Same parser; same architectural problem viewed from two angles. Inversion ships narration-detection; commitment-tracking writes detected commitments to structured table; engine reads back for anti-gaslight rails.

5. **First-migration set at v0 — three Tier 3 surfaces.** Sketch §11.5 lean.
   - Transaction-completion (player-side narration "I'll buy the bread") — already partially landed via N-1 hint extractor; Inversion completes the writer path
   - Quest acceptance (player-side "I'll take the job")
   - Loot drop (player-side "we leave it behind")
   
   Travel-intent and compression-intent file v0.1.

6. **S69 implementation-spec shape — amend-in-place at Inversion ship time.** Per operator §11.6 dispatch update (supersedes sketch §11.6 stated lean (b)). Locked Causality Engine v0 spec amends a §6.1 (or sibling) clause naming inversion-aware slash discipline; locked architecture (atmospheric/hard-progression split, predicate evaluation, §76 disciplines) holds unchanged. Surface-layer slashes amend per §6 tier framework.

7. **Detection-confidence-tier routing — three tiers.** Sketch §11.7 lean.
   - High-confidence (verb + matching structured signal both present) → engine writer
   - Medium-confidence (verb only, no structured signal) → `#dm-aside` suggester card for operator approval
   - Low-confidence (neither) → silent (no fire)

8. **Telemetry — per-detection-fire.** Sketch §11.8 lean. `narration_intent_detected:`, `narration_intent_routed:`, `narration_intent_suppressed:`. Standard project pattern.

9. **Operator manual override — existing slashes hold.** Sketch §11.9 lean. No new abort surface. High-confidence detection that operator wants to refuse: operator types the existing slash (which remains operational) to overwrite engine state, or files `#dm-aside` correction.

10. **§F-59 bot→Avrae prohibition — unchanged.** Sketch §11.10 lean. Confirmed at R6. Detection-suggester pattern routes operator-pasteable Avrae commands to `#dm-aside`; no bot-emit changes. S41 NPC state-sync precedent generalizes.

11. **No v0.x emergent-surface pre-coupling.** Sketch §11.11. LLM classifier introduction, hybrid detection, advanced override flows, multi-character party detection, operator-vs-player disambiguation all file v1.x.

12. **Migration sequencing — gradual per-ship.** Sketch §11.12 lean (b). Inversion v0 introduces detection infrastructure + ships first three migrations (decision 5). Subsequent Tier 3 migrations follow observed-friction order, per-ship sequential-commit discipline standing since S65.

---

## §2. Problem statement

### 2.1 The architectural framing

The project has been accumulating slash commands across every architectural ship — 47 distinct slashes across 7 groups in `discord_dnd_bot.py` at recon time (R2). Each ship has added more: Quest Layer v0 (8 slashes), Composition Layer v0 (5+), Bootstrap Bot N-10 (7+), Clock surfaces (4+), S69-paused factions (~8 specified).

The convergent review (planner + GPT + Gemini, three-way independent) surfaced that this slash sprawl is **not the architecture's problem**. It is a *symptom of an inverted framing*. The project has been treating operator surface as primary deterministic control because §1a says LLM does not decide binding state. The implication appeared to be: every state mutation needs a slash for operator-deterministic invocation.

**The inverted framing keeps §1a intact via a different mechanism.** Detection from narration is itself a deterministic gate — *when* the parser is closed-vocabulary or structured-signal, *when* the writer remains engine-side and §17-disciplined, *when* low-confidence routes to suggester for operator approval. The engine reads operator narration and player narration through the same deterministic parsers; verbs and structured signals route to engine writers; LLM is still excluded from binding state writes.

This is doctrinal direction-lock, not feature work. The slash surfaces that the project has accumulated since the original mandate are *mostly not load-bearing* — most can invert to narration-detected with the §1a deterministic gate intact via parser + structured signals + engine writer.

### 2.2 The BIOS / OS / UI metaphor

Load-bearing framing principle. Carry forward across this spec and all downstream architectural work.

- **Commands are BIOS.** System-level structural primitives. Boot, configure, reset, escape hatch. Operator types these when the system needs structural mutation that has no narrative path. `/newcampaign`, `/setcampaign`, `/bindchar`, `/setup`, debug surfaces. Present but rare and structural; not the everyday operating surface.

- **Engine is OS.** Deterministic state machinery underneath everything. §1a, §17, §76, §59 patterns all still operate. Engine remains the canonical write surface; LLM still never decides binding outcomes.

- **Conversation is UI.** Operator and player both interact with the world through narration. The system *detects* intent from narration via deterministic parsers (closed-vocabulary at v0; hybrid filed v1.x) and routes to the deterministic gate. Slash exists as escape hatch and BIOS-tier control.

### 2.3 The litmus test

> **"Would a good human DM stop the session to operate software for this?"**

If yes, the surface stays as command. If no, the surface inverts to narration-detected.

Applied:
- `/newcampaign` — yes, session-zero setup. Stays BIOS.
- `/bindchar` — yes, character-sheet binding is session-zero work. Stays BIOS.
- `/quest accept <id>` — no, a player just says "I'll take the job" and the DM continues. Inverts.
- `/faction stage edit <id> <stage> <description>` — emphatically no. Inverts or migrates to bootstrap/aside flow.
- `/travel destination:"X" duration:"1 hour"` — borderline. DM might say "we travel three hours to the Old Mill" naturally. Inverts as primary surface; slash stays as deterministic escape hatch.

### 2.4 DM-burden co-equal with player-burden

Convergent-review insight: the slash-burden problem is *not* just player UX. It is *equally* a DM-burden problem.

**Current state.** When player narrates "I'll buy the sourdough," the operator (Jordan, in DM role) must mentally translate to `!game coin -5cp`, type it, watch Avrae respond, then narrate. The DM is operating software to render a transaction the player described in plain language.

**Inverted state.** Player narrates "I'll buy the sourdough." Engine narration parser detects transaction intent (closed verb vocabulary + price context per N-1 hint extractor precedent). Deterministic suggester proposes `!game coin -5cp` in `#dm-aside`. DM approves implicitly via continuing narration, or explicitly by pasting the suggested command.

The litmus test applies symmetrically. A good human DM does not stop the session to type software commands either. The inversion serves both roles.

This also reframes what gets built first. Inverting player-side surfaces (quest acceptance, loot drop, transactions) AND DM-side surfaces (compression intent, faction tick decisions, NPC commitment authoring) happen in the same architectural arc, not separate ships.

---

## §3. Architecture: narration-detection layer

### 3.1 Layer placement

New layer in `dnd_orchestration.py` — sits between `discord_dnd_bot.on_message()` (R3 integration point: `discord_dnd_bot.py:2664` — `action = message.content.strip()`) and `_dm_respond_and_post()` (`discord_dnd_bot.py:3366`).

For operator narration (DM-side surfaces — compression-intent, etc.), parallel post-LLM-narration hook at `_extract_and_persist_world()` site (`discord_dnd_bot.py:2789`, the S68 N-4 pattern). Operator narration in `#dm-aside`/operator-channel is parsed for operator-side intent signals.

### 3.2 Per-domain parsers (§59 sibling family)

One §59 sibling per detection domain. Pure `(body, signals) → (matched_intent | None, confidence_tier, structured_payload)` function. Soft-fail at call site (matches §59 #11+ pattern).

Domains at v0:

| Domain                  | Verb vocabulary (closed set)                      | Required structured signal               |
|-------------------------|---------------------------------------------------|------------------------------------------|
| Transaction-completion  | `buy`, `purchase`, `pay`, `pay for`, `I'll take`  | Price context in narration OR active shop scene; matches N-1 extractor pattern |
| Quest-acceptance        | `accept`, `take`, `agree to`, `do it`, `I'll do`, `count me in`, `I'll take` (disambiguated against transaction verb via signal) | Active `dnd_quests WHERE status='offered'` row matching player text via canonical-name OR first-name match |
| Loot-drop               | `leave behind`, `drop`, `discard`, `we won't take`, `not worth` | Active loot card OR recent loot directive in current scene |

### 3.3 Detection-confidence-tier routing

Three tiers, per §1 decision 7:

- **High** (verb + matching structured signal): Route directly to engine writer (transaction → write coin txn proposal; quest → `dnd_quests.status='accepted'` write; loot → `dnd_loot_drops` insert).
- **Medium** (verb only, no structured signal): Route to `#dm-aside` suggester card with operator-pasteable approval action (e.g., paste `/quest accept id:abc` OR the suggested Avrae command).
- **Low** (neither): Silent. No fire, no telemetry-emit beyond aggregate counter.

### 3.4 New telemetry primitives

- `narration_intent_detected:` — emitted on every high-or-medium-confidence fire. Fields: `domain`, `confidence_tier`, `verb_matched`, `signal_matched`, `campaign_id`, `actor_kind` (player/operator).
- `narration_intent_routed:` — emitted on detection→action transition. Fields: `domain`, `route` (engine_writer|suggester_card|silent), `success` (bool), `error_kind` (if failed).
- `narration_intent_suppressed:` — emitted when high-confidence fire is suppressed by cross-turn dedup (per N-1 `_RECENT_HINTS_PER_CAMPAIGN` precedent generalized to per-domain LRU).

### 3.5 Cross-turn dedup

Per N-1 precedent (`_RECENT_HINTS_PER_CAMPAIGN` at `mechanical_hints.py:159`). Process-local LRU deque per campaign per domain; suppresses same-intent re-fire within N turns. N=3 at v0, tunable per domain.

### 3.6 §17 single-writer-per-field discipline holds

No change to existing engine writers (`npc_upsert`, `quest_upsert`, `quest_act_upsert`, `faction_upsert`, `dnd_loot_drops` insert, etc.). What changes is what *fires* them — narration-detection rather than slash handler. Each field still has exactly one writer; the call site is what shifts.

### 3.7 No new ChromaDB collection, no bot→Avrae writes

Detection layer is structured-signal-only. ChromaDB unaffected. §F-59 prohibition holds — bot does not auto-emit `!`-prefixed Avrae commands; suggester cards render operator-pasteable text in `#dm-aside` (R6 confirmation).

---

## §4. Doctrinal framing

### 4.1 §1a doctrinal extension — three candidate shapes

Sketch §7. No confident code-side lean. Operator + Oracle territory.

**(i) §1a amendment (in-place extension).** Add a clause to §1a explicitly naming narration-detection-with-deterministic-parser as equivalent to operator-slash for the binding-decision restriction. Strict-literal precedent (§14.1 sub-numbering pattern) applies.

**(ii) §1c new doctrine.** File a new top-level doctrine number codifying *"Detection-from-narration is a deterministic gate when (a) parser is closed-vocabulary or structured-signal, (b) writer remains engine-side and §17-disciplined, (c) low-confidence routes to suggester for operator approval."* Parallels §1a + §1b as a third-of-three companion doctrines.

**(iii) §1a.x sub-numbering.** Like §14.1 pattern — anchored extension under §1a's number. Acknowledges the extension is doctrinally derived from §1a's intent, not a new separable rule.

**Trade-offs surface:**
- (i) keeps §1a as the load-bearing index but risks bloating its statement.
- (ii) gives the inversion its own anchor (useful for downstream citation) but breaks the §1a/§1b two-doctrine pairing.
- (iii) preserves §1a as the anchor and gives the extension its own citation point; mirrors §14.1's established pattern.

Code's weak lean: (iii). Matches §14.1 precedent and preserves citation clarity without breaking the §1a/§1b pairing. **Filed §11.2 for Phase 2 walk.**

### 4.2 §1b validated-suggester interaction — three candidate shapes

Sketch §8. Lean (a) parallel surfaces at v0.

**(a) Parallel surfaces (lean at v0).** §1b slash-approval remains the canonical pattern. Narration-detection sits parallel as a high-confidence shortcut — when detection confidence is high, route directly to engine writer; when medium, fall through to §1b-shaped suggester (`#dm-aside` card + operator-pasteable approval). §1b doctrine unchanged.

**(b) Extension — narration-detection IS the §1b gate.** §1b doctrine extends: "validated-suggester pattern" now includes both slash-approval and narration-detection as canonical gate forms.

**(c) Replacement — narration-detection supersedes §1b.** §1b deprecates. All validated-suggester flows route through narration-detection at v0.x.

**Lean (a).** Replacement is too aggressive; extension blurs the §1b anchor that just hardened across five instances. Parallel preserves §1b intact while opening the new surface. (b) is the likely v1.x position after observed friction shows narration-detection is reliably operating as the deterministic gate.

### 4.3 §17 single-writer holds, §59 sibling pattern continues, §76 four-property audit applies

- §17: per §3.6.
- §59: each per-domain parser is a §59 sibling — pure function returning `(matched_intent | None, confidence_tier, structured_payload)`; soft-fail at call site.
- §76: new field surfaces (detected-intent state in-memory; commitment records if N-3.1 folds in per §1 decision 4) audit at §10 below.

### 4.4 §65 / §F-59 bot→Avrae prohibition — confirmed unchanged

R6 evidence: `DOCTRINE.md:560-564`. Bot does not emit `!`-prefixed commands. Empirically validated via S41 Avrae bot-filter finding (bot-typed `!` commands silently filtered by Avrae). Inversion v0's high-confidence transaction detection routes to `#dm-aside` as operator-pasteable Avrae command (per S41 NPC State-Sync suggester precedent); not direct bot-emit.

---

## §5. Detection vocabulary

Per §1 decision 1: closed-vocabulary verb-and-signal parsers at v0.

### 5.1 Architectural template — N-1 hint extractor (R1 evidence)

`mechanical_hints.py` is the load-bearing precedent. Inspected components:

- **`_COIN_TRANSACTION_VERBS` frozenset (`mechanical_hints.py:106`).** Closed vocabulary. Constructed with noun-overlap traps excluded (e.g., `buy` is in; `sell` is in; ambiguous nouns like `change`/`cost` are excluded — they double as nouns in non-transaction contexts).
- **`_narration_has_transaction_verb()` (`mechanical_hints.py:136`).** Whole-word match via `re.findall(r"[a-zA-Z]+", text.lower())` — *not substring match*. Prevents `bought` from matching `bough` or similar phonetic overlaps.
- **`_RECENT_HINTS_PER_CAMPAIGN` LRU deque (`mechanical_hints.py:159`).** Process-local cross-turn dedup. Per-campaign deque suppresses same-hint re-fire within N recent turns.
- **`parse_mechanical_hints()` (`mechanical_hints.py:284`).** Two-stage gate: (1) verb-presence check, (2) structured-signal co-occurrence (price context). Per-fire telemetry emitted via standard project pattern.

**Generalization shape (confirmed at R1):** Closed verb set + structured-signal co-occurrence + whole-word tokenization + cross-turn dedup + per-fire telemetry. Applies cleanly to quest-acceptance and loot-drop domains. No HALT triggered.

### 5.2 Per-domain vocabulary at v0

Per §3.2 table. Each parser is a §59 sibling owning its verb frozenset + signal-check function.

### 5.3 Vocabulary maintenance discipline

Verb sets are *closed* — new verbs land via spec amendment, not silent additions. Per-fire telemetry surfaces friction (e.g., player phrases that should have detected but didn't) for periodic vocabulary review. Misses are operator-bridged via existing slash (which remains operational).

### 5.4 Why not LLM classifier (b) or hybrid (c) at v0

- (b) re-introduces LLM as decider — §1a tension. Calibration drift risk.
- (c) two systems to maintain; "ambiguous" threshold needs observed-friction data before it can be calibrated.

Both file v1.x and ship only after (a) operates at scale and friction shape becomes visible.

---

## §6. First-migration set at v0

Per §1 decision 5: three Tier 3 surfaces ship at v0. Selected by friction-visibility + clean detection signal + minimal cascade risk.

### 6.1 Transaction-completion (player-side)

**Current surface.** None — player types `!game coin -5cp` after narration, or DM types it post-narration. N-1 hint extractor emits hint to player narration prompt but does not write engine state.

**Inverted surface.** Player narrates "I'll buy the sourdough." Engine detects transaction intent. High-confidence (verb + price context) → engine writes proposal to suggester for Avrae paste (§F-59 compliant). Medium-confidence → `#dm-aside` suggester card.

**Cascade audit:** Cleanly absorbs into existing transaction-suggester flow. No new schema. Builds on N-1 hint extractor.

### 6.2 Quest-acceptance (player-side)

**Current surface.** `/quest accept id:<quest_id>` — Tier 3 surface from Quest Layer v0.1.

**Inverted surface.** Player narrates "I'll take the job" or "we accept." Engine detects quest-acceptance + matches against `dnd_quests WHERE status='offered'`. High-confidence (verb + single matching offered quest) → engine writes `status='accepted'` directly via `quest_upsert`. Medium-confidence (verb only, or multiple offered quests, or no clear match) → `#dm-aside` suggester card listing offered quests with pasteable `/quest accept` per row.

**Cascade audit:** `quest_upsert` is the §17 single-writer; cascade is limited to `dnd_quests.status` and any quest-acceptance-listener telemetry. No NPC mutation, no faction mutation. Clean.

**Existing slash holds as escape hatch.** Operator can still type `/quest accept id:<id>` to override detection or accept when narration is ambiguous.

### 6.3 Loot-drop (player-side)

**Current surface.** `/loot drop` — Tier 3 Quest Layer surface (R2 inventory).

**Inverted surface.** Player narrates "we leave the silver dagger behind" or "discard the broken sword." Engine detects loot-drop intent + matches against active loot card or recent loot directive. High-confidence → engine writes `dnd_loot_drops` insert. Medium-confidence → `#dm-aside` suggester card with pasteable confirmation.

**Cascade audit:** `dnd_loot_drops` is a leaf table; no downstream cascades at v0. Clean.

### 6.4 What files to v0.1

- **Travel-intent.** Player or operator narration "we travel to X" / "three hours to the Old Mill." Detection cleaner than quest-accept but more cascade surface (encounter rolls, faction ticks per S69 spec, scene compression coupling). v0.1 after S69 amends.
- **Compression-intent.** Operator narration "time passes" / "we wind down." Cleanly detectable but touches Scene Lifecycle v1's compression discipline — wants explicit operator-confirm at v0 phase. v0.1 candidate.
- **Mode transitions.** Combat-mode entry via "rolls for initiative" detection. Couples to Avrae init events — wants Combat-track-1 audit before inverting.

### 6.5 What stays slash at v0 (and likely beyond)

- All Tier 1 BIOS surfaces (per §6 sketch framework): `/newcampaign`, `/setcampaign`, `/bindchar`, `/setup`, `/refresh`, `/dmhelp`, `/inventory`, `*list`, `*status`.
- Tier 2 authoring surfaces: `/quest add`, `/quest_act add`, `/bootstrap.*`, `/skeleton.load`, `/companion.*`, `/clock.create/delete`, `/hydrate`, `/encounter`. Bootstrap-flow already absorbing partial authoring inversion via N-10.
- Tier 3 surfaces NOT in v0 first-migration set: `/quest complete`, `/quest fail`, `/quest abandon`, `/quest_act advance`, `/compress`, `/giveitem`, `/travel`, `/advance`, `/clock.tick/untick/reset`, `/nudge`. All remain operational; invert per observed-friction order in v0.1+.

---

## §7. N-3.1 commitment-tracking interaction

Per §1 decision 4: N-3.1 folds into Inversion v0.

### 7.1 The same architectural problem

N-3.1 (commitment-tracking layer; HALTed at S68 with N-3 escalation for schema work) is the load-bearing instance of the narration-commit-gap doctrine candidate. NPC says "I'll have the cart ready by noon Threeday"; engine has no structured record; anti-gaslight rails can't enforce.

Inversion v0 ships narration-detection infrastructure that is *exactly the parser N-3.1 needs*. The convergent review framing — "slash sprawl is a symptom of deeper architectural framing" — applies equally here: N-3.1 needs detection to write commitments to a structured table; Inversion v0 needs detection to fire engine writers. Same parser; same load-bearing problem viewed from two angles.

### 7.2 Fold-in shape

- Inversion v0 ships per-domain parsers including a **commitment-utterance** domain.
- Detected NPC commitments write to a new `dnd_commitments` table (schema sketch in §7.3).
- Engine reads back from `dnd_commitments` in subsequent turn prompts for anti-gaslight rail surfacing (per N-3.1 original problem statement).
- Player-side commitment detection (player narration "I'll meet you at the inn at dusk") is a v0.x candidate; v0 ships NPC-commitment-utterance detection from operator-narration channel only.

### 7.3 `dnd_commitments` schema sketch (filed for §11 walk)

| Column | Type | Notes |
|---|---|---|
| `commitment_id` | TEXT PK | UUID |
| `campaign_id` | TEXT FK | |
| `npc_id` | TEXT FK | `dnd_npcs.npc_id`; nullable if NPC unidentified at detection time |
| `npc_name_raw` | TEXT | What the narration said (resolves on next hydrate if `npc_id` nullable) |
| `commitment_text` | TEXT | Detected commitment verbatim |
| `commitment_kind` | TEXT | `deliverable` / `meeting` / `payment` / `task` (closed vocab) |
| `target_when_text` | TEXT | Detected time phrase ("noon Threeday", "before the harvest") |
| `target_when_iso` | TEXT NULL | Resolved if calendar context allows |
| `detected_at_turn_id` | INTEGER FK | `dnd_turns.turn_id` |
| `status` | TEXT | `open` / `fulfilled` / `broken` / `superseded` |
| `confidence_tier` | TEXT | `high` / `medium` (low never writes) |
| `created_at` | TEXT | |

Schema lock deferred to spec session; sketch surfaces shape for Phase 2 walk.

### 7.4 Where it doesn't fold

- Commitment-fulfillment detection (engine reads back from `dnd_commitments`, fires anti-gaslight prompt-rails) is a v0.x candidate. v0 ships detection-and-write only; fulfillment-tracking ships at v0.1 or v1.
- Commitment-cascade (NPC breaks commitment → faction trust shift) couples to S69 factions; ships post-S69-resume.

---

## §8. S69 implementation-spec shape

Per §1 decision 6 + operator §11.6 dispatch update.

### 8.1 Current state

`specs/CAUSALITY_ENGINE_V0_SPEC.md` is LOCKED. `specs/CAUSALITY_ENGINE_V0_REVIEW.md` is LOCKED. Phase 3 implementation was paused pre-dispatch pending Inversion v0 calibration. S69 is **locked-spec-pre-implementation**, not shipped-and-resuming.

### 8.2 Amend-in-place at Inversion ship time (operator override)

**Operator dispatch §11.6 update supersedes sketch §11.6 stated lean (b).**

When Inversion v0 ships, the locked Causality Engine v0 spec receives a §6.1 (or sibling) amendment naming:
- Inversion-aware slash discipline applies to faction surfaces per §6 tier framework
- Three slashes survive (Tier 1 BIOS): `/faction seed` (skeleton.md migration; structural), `/faction tick <id>` (escape-hatch deterministic; rare operator-deliberate), `/faction list` (folds into future `/status`).
- Tier 2/3 surfaces (`/faction stage edit`, `/faction set kind:`, `/faction hold`, `/faction reset`, `/faction delete`) invert per §6 framework. Operator authoring routes through bootstrap-flow + `#dm-aside` suggester.
- Detection adds a new fire path for faction-engagement signals (per S69 spec §5 predicate evaluation): operator narration "the cartel grows bolder" / "word of the cartel reaches the council" detects via faction-engagement parser, feeds predicate evaluation alongside engine-recognized events (travel, rest, scene compression).

### 8.3 What does not change in S69 spec

- §3 atmospheric vs hard-progression split
- §4 `dnd_factions` schema
- §5 tick mechanics (including the predicate evaluation pipeline)
- §6 pressure directive shape (§59 sibling #21)
- §7 solo-bard calibration
- §10 §76 four-property latent-canon audit

These are doctrine-layer locks. The amendment is *surface-layer only*.

### 8.4 §11 candidate note

Sketch §11.6 stated lean (b) — open S69 v0.1 spec session at resume. Operator dispatch overrides to (a) — amend-in-place. **Surfaced as discrepancy for Phase 2 walk operator confirmation.**

The operator-override lean (a) trade-off:
- (+) Preserves S69's spec session work (Session 2 review was significant)
- (+) Cleaner ship cadence (Inversion v0 lands → S69 amendment + implementation immediately follows)
- (–) Locked-spec edits carry doctrinal weight; amendment requires Oracle confirmation that surface-layer change does not implicitly mutate doctrine layer

Code's read: amendment is safe if §3-§7 and §10 hold byte-for-byte and amendment lands as a clearly-marked §6.1 (or §15 "Surface inversion delta") clause. Phase 2 confirms.

---

## §9. Recon findings

Six items per Phase 1 dispatch. Evidence and HALT-trigger status per item.

### R1 — N-1 hint extractor implementation audit

**Target:** `dnd_orchestration.py` and `mechanical_hints.py`.

**Findings:**
- `_COIN_TRANSACTION_VERBS` frozenset at `mechanical_hints.py:106`. Closed vocabulary with noun-overlap traps excluded.
- `_narration_has_transaction_verb()` at `mechanical_hints.py:136`. Whole-word match via `re.findall(r"[a-zA-Z]+", text.lower())`. Not substring.
- `_RECENT_HINTS_PER_CAMPAIGN` dict at `mechanical_hints.py:159`. Process-local LRU deque, per-campaign.
- `parse_mechanical_hints()` at `mechanical_hints.py:284`. Two-stage gate (verb-presence + price-signal-cooccurrence) + cross-turn dedup + per-fire telemetry.

**Generalization shape:** Closed verb set + structured-signal co-occurrence + whole-word tokenization + cross-turn dedup + per-fire telemetry. Generalizes cleanly to quest-acceptance and loot-drop domains.

**HALT trigger:** None. Pattern generalizes. Sketch §5 lean (a) architecturally supportable.

### R2 — Existing slash handler inventory + tier classification

**Target:** `discord_dnd_bot.py`.

**Findings:** 47 distinct slashes across 7 groups (`bootstrap`, `clock`, `companion`, `consequence`, `quest`, `quest_act`, `skeleton`). Tier classification per §6 sketch framework:

| Tier | Count | Surfaces |
|---|---|---|
| Tier 1 BIOS | ~18 | `newcampaign`, `setcampaign`, `archived`, `campaigns`, `deletecampaign`, `purgecampaign`, `purgeallcampaigns`, `bindchar`, `setup`, `refresh`, `dmhelp`, `inventory`, `*list`, `*status` |
| Tier 2 Authoring | ~14 | `quest.add/delete`, `quest_act.add`, `bootstrap.*` (7), `skeleton.load`, `companion.*`, `clock.create/delete`, `hydrate`, `encounter`, `mode` |
| Tier 3 Pacing/Play | ~13 | `quest.accept/complete/fail/abandon`, `quest_act.advance`, `compress`, `loot`, `giveitem`, `travel`, `advance`, `clock.tick/untick/reset`, `nudge` |

**Cascade audit:** `/quest accept` cascades to `dnd_quests.status` write only — no NPC or faction mutation. Clean inversion candidate. `/travel` cascades broadly (encounter rolls, faction ticks per S69 spec, compression coupling) — defers to v0.1 post-S69-amend.

**HALT trigger:** None. Tier-classification clean; first-migration set (§6) supportable.

### R3 — Detection-routing integration point

**Target:** `discord_dnd_bot.py` turn-processing pipeline.

**Findings:**
- `on_message()` entry at `discord_dnd_bot.py:2481`. Player narration arrives here.
- `action = message.content.strip()` at `discord_dnd_bot.py:2664` — clean detection-insertion candidate. Pre-LLM-narration. Detection fires before `_dm_respond_and_post()`.
- `_dm_respond_and_post()` at `discord_dnd_bot.py:3366` — LLM narration production.
- `_extract_and_persist_world()` at `discord_dnd_bot.py:2789` — post-narration background task (S68 N-4 pattern). Operator-narration parallel detection hook fits here.

**Integration shape:**
- Player narration → pre-LLM-narration detection at `discord_dnd_bot.py:2664`. High-confidence fires engine writer before LLM narrates (so LLM context already reflects engine state); medium-confidence fires `#dm-aside` suggester in parallel; low-confidence silent.
- Operator narration → post-LLM-narration detection at `_extract_and_persist_world()` hook. Same three-tier routing.

**HALT trigger:** None. Clean integration points; no turn-processing-pipeline impedance.

### R4 — `#dm-aside` suggester card format catalog

**Target:** existing card formats in `discord_dnd_bot.py`.

**Findings:** Five existing card-format precedents:
- `discord_dnd_bot.py:548` — QUEST OFFER card
- `discord_dnd_bot.py:684` — QUEST ACT TRANSITION card
- `discord_dnd_bot.py:5917` — REWARD READY card
- `discord_dnd_bot.py:6440` — BOOTSTRAP card
- `discord_dnd_bot.py:6512` — BOOTSTRAP COMPLETE card

Plain Discord send via `_post_dm_aside(guild, text)`. Format pattern: header line + body block + optional pasteable-command suffix.

**Format precedent for Inversion suggester cards:**
```
[INVERSION SUGGEST · <domain>]
Detected: <verbatim narration fragment>
Confidence: <medium|high>
Action: <pasteable slash or Avrae command>
```

Inherits S41 NPC State-Sync precedent: bot proposes via `#dm-aside`, deterministic gate confirms safe-to-suggest, DM approves by paste.

**HALT trigger:** None. Format precedent established.

### R5 — Prompt-size impact estimation at v0 fire-volume

**Target:** prompt-size baseline + projected delta.

**Findings:**
- Baseline ~22k chars post-S67.
- Pre-detection parsers do NOT render to prompt (fire pre-LLM-narration; engine writes happen before prompt construction).
- `#dm-aside` suggester cards render to operator channel, NOT player narration prompt. Zero delta on player prompt.
- Operator-channel prompt context (if applicable for DM-side parsing) takes minimal hit at v0 fire volumes — estimated <500 chars per suggester card; expected fire rate <5/session at v0 conservative estimate.

**HALT trigger:** None. Budget impact negligible at v0.

### R6 — §F-59 / §65 bot→Avrae prohibition confirmation

**Target:** `DOCTRINE.md` §65 + `discord_dnd_bot.py` for current-state bot-emit audit.

**Findings:**
- `DOCTRINE.md:560-564` §65 text: *"Avrae is the sole authority for mechanics. Virgil is the mechanics-consumer, not a mechanics-mirror. The bot does NOT emit `!`-prefixed commands. LLMs can emit them (in narration responses, for the player to copy or as suggestions); the bot side never does."*
- S41 NPC State-Sync precedent at `DOCTRINE.md:108-112`: Bot proposes via `#dm-aside`, deterministic gate confirms safe-to-suggest, DM approves by pasting, Avrae executes. Empirically validated — Avrae bot-filter silently filters bot-typed `!` commands.
- No current `channel.send(.*!)` violations found in `discord_dnd_bot.py`.

**Synthesis:** Inversion v0's high-confidence detection-suggester pattern routes operator-pasteable Avrae commands to `#dm-aside`. NOT direct bot-emit. §65/§F-59 holds unchanged. S41 suggester pattern generalizes to Inversion v0 transaction-domain.

**HALT trigger:** None. Doctrinal prohibition holds and inversion respects it.

---

## §10. §76 four-property latent-canon audit on new fields

§76 audit applies to: (a) detected-intent in-memory state (transient), (b) `dnd_commitments` records if N-3.1 fold-in per §1 decision 4 ships at v0.

### 10.1 Detected-intent in-memory state

In-memory; not latent-canon. Fires within a turn, either writes to engine (becomes canonical via existing writer's §76 properties) or routes to suggester card (operator-visible, not engine state). No §76 audit applies — transient by design.

### 10.2 `dnd_commitments` records (§7 fold-in)

Four §76 properties audit:

**Property 1: Single source of truth.** `dnd_commitments` is the sole repository for detected commitments. No parallel store. ✓

**Property 2: Engine-only writes.** Writes happen via `commitment_upsert` (new §17 single-writer; §59 sibling family). LLM never writes. Detection parser is engine-side; §17 holds. ✓

**Property 3: Read-back surface clarity.** Engine reads `dnd_commitments WHERE status='open'` in turn-prompt construction (anti-gaslight rails) and in NPC-state-rendering. Read paths are documented (filed §7.4 deferred to spec session for fulfillment-tracking, but read-for-rails ships at v0). ✓

**Property 4: Closed-loop test surface.** Test plan (filed §13 below) includes commitment-write + commitment-read roundtrip via test-database fixture. Existing test infrastructure (per N-1 hint extractor's test pattern) applies. ✓

**Audit result:** §76 four properties hold at v0 architectural intent. Schema lock + test plan flesh-out in Phase 2 walk + Phase 3 implementation.

### 10.3 No other new latent-canon surfaces

No new ChromaDB collection. No new schema beyond `dnd_commitments` (and that one is contingent on §11.4 lock). Existing tables (`dnd_quests`, `dnd_loot_drops`, etc.) unaffected at field-shape — only what *fires* writes changes.

---

## §11. Decision points — operator's call required

Twelve §11 candidates per sketch §11. Code's leans named; locks deferred to Phase 2 walk-through with operator + Oracle.

**1. Detection vocabulary at v0.** (a) closed-vocabulary verb-and-signal parsers, (b) LLM classifier, (c) hybrid. **Code lean: (a)** per §1 decision 1. §1a clean. N-1 / S66 precedent operates.

**2. §1a doctrinal extension shape.** (i) §1a amendment in-place, (ii) §1c new doctrine, (iii) §1a.x sub-numbering. **Code weak lean: (iii)** per §4.1 trade-off analysis. Operator + Oracle territory.

**3. §1b validated-suggester interaction.** (a) parallel surfaces, (b) extension, (c) replacement. **Code lean: (a) at v0** per §1 decision 3. Preserves §1b anchor.

**4. N-3.1 commitment-tracking fold-in.** (a) folds into Inversion v0 as same architectural ship, (b) stays separate. **Code lean: (a)** per §1 decision 4. Same parser; same load-bearing problem viewed from two angles.

**5. First-migration set at v0.** Which Tier 3 surfaces invert as primary v0 ship? **Code lean: transaction-completion + quest-acceptance + loot-drop** per §1 decision 5 / §6 detail. Smallest viable set; highest friction-visible cases first.

**6. S69 implementation-spec shape.** (a) amend locked S69 spec at Inversion v0 ship time, (b) open S69 v0.1 spec session at resume. **Operator dispatch override: (a)** supersedes sketch's stated lean (b). Code recommends operator-Oracle confirmation that surface-layer amendment is doctrinally safe — see §8.4.

**7. Detection-confidence tier routing.** High-confidence auto-route to writer; medium-confidence to `#dm-aside` suggester for operator approval; low-confidence silent. **Code lean: three-tier per §3.3.** Per-domain threshold tuning is filed §11 candidate for v0.1 calibration.

**8. Telemetry verbosity.** Per-detection-fire vs aggregated per-turn. **Code lean: per-detection-fire at v0** per §1 decision 8. Standard project pattern.

**9. Operator manual override surface.** Single-character abort (`/no`), slash that mirrors what was detected, or `#dm-aside` rejection card. **Code lean: existing slash as override + `#dm-aside` rejection card** per §1 decision 9. No new abort surface.

**10. Bot→Avrae auto-execution.** §F-59 anchored bot→Avrae writes as prohibited. **Code lean: §F-59 holds; confirmed unchanged** per §1 decision 10 / R6.

**11. Composition forward-compat — silent.** v0 does not pre-couple v0.x emergent surfaces. **Code lean: hold discipline.**

**12. Migration sequencing for prior ships.** (a) Big-bang Inversion v0 migrates all Tier 3 surfaces at once, (b) gradual per-ship migration in observed-friction order. **Code lean: (b)** per §1 decision 12. Big-bang multiplies blast radius.

---

## §12. Open questions filed forward — out of v0 scope

- **LLM classifier introduction** (§5 candidate (b)) — v1.x if v0 closed-vocabulary surfaces unmitigated friction.
- **Hybrid detection** (§5 candidate (c)) — v1.x after (a) operates at scale.
- **Multi-character party detection.** Player narration in multiplayer routing (whose intent did "we accept" represent?). v0 ships single-character assumption; multi-character routing files v0.x.
- **Operator-vs-player text disambiguation.** Channel-source disambiguates at v0; if surfaces friction (e.g., operator types in player channel for color), file as v0.1 surface.
- **Commitment-fulfillment detection.** Engine reads `dnd_commitments` and detects fulfillment in subsequent narration. v0 ships write-only; fulfillment ships v0.1 / v1.
- **Commitment-cascade to factions.** NPC breaks commitment → faction trust shift. Couples to S69 factions; ships post-S69-resume.
- **Travel-intent inversion.** Per §6.4. v0.1 after S69 amends.
- **Compression-intent inversion.** Per §6.4. v0.1 candidate.
- **Mode-transition inversion.** Per §6.4. Wants Combat-track-1 audit first.
- **Advanced override surfaces.** `/no`-style single-character abort if `#dm-aside`-rejection-card friction surfaces. Filed §11 candidate; v0.x if observed.
- **Vocabulary-expansion governance.** Process for adding verbs to closed sets as friction surfaces. v0 ships with operator-bridged-via-slash escape; v0.x candidate for governance pattern.

---

## §13. Out of scope — v0 explicitly does not

- Remove any existing slash command. All 47 slashes remain operational; inversion adds detection surface alongside.
- Modify any existing engine writer (`npc_upsert`, `quest_upsert`, `faction_upsert`, etc.). §17 holds; call sites shift, writers don't.
- Introduce a new ChromaDB collection.
- Modify `dnd_*` schemas except for the new `dnd_commitments` table (contingent on §11.4 lock).
- Auto-emit `!`-prefixed Avrae commands from bot. §F-59 holds.
- Resolve §F-59 N-6 surface (bot→Avrae auto-execution question). Inversion sharpens the question's visibility but does not resolve it.
- Ship LLM classifier or hybrid detection.
- Migrate all Tier 3 surfaces at once.
- Pre-couple v0.x emergent surfaces (silent forward-compat per §11.11).
- Address multi-character party detection.
- Address operator-vs-player text disambiguation (channel-source disambiguates at v0).
- Ship commitment-fulfillment detection.
- Ship faction-engagement detection (defers to S69 amendment).
- Modify §1b doctrine (parallel surfaces at v0 per §11.3).
- Modify §65 / §F-59 (confirmed unchanged at R6).

---

## §14. Handoff

**Spec doc:** `/home/jordaneal/virgil-docs/specs/CONVERSATIONAL_RUNTIME_INVERSION_V0_SPEC.md` (DRAFT — this file).

**Source sketch:** `planner-scratch/conversational_runtime_inversion_v0_sketch.md` (corrected 2026-05-15).

**Phase 1 recon:** Complete. R1-R6 evidence in §9. No HALT triggered.

**Phase 2 (next session):** Review pass. Operator + Oracle walk §11.1 through §11.12 in order. Locked output: amended spec with §11 candidates resolved into §1 decisions.

**Recommended Session 2 cadence:** Opus medium. Three §11 walks expected to require deeper synthesis:
- §11.2 §1a doctrinal extension shape — Oracle territory
- §11.3 §1b interaction — anchored-instance impact analysis
- §11.5 first-migration set — friction-visibility vs cascade-risk trade-off

**Phase 3 (after Session 2 lock):** Implementation ship. First-migration set per §11.5 lock. Per-domain parsers + integration at `discord_dnd_bot.py:2664` + suggester card format per R4 precedent + telemetry per §3.4. Test plan flesh-out (§10.2 commitment table closed-loop, §6 per-domain detection roundtrips).

**Discrepancy flag for Phase 2:** Sketch §11.6 stated lean (b) vs operator dispatch §11.6 lean (a). Spec drafted per operator override (a) — amend-in-place at Inversion ship time. Phase 2 walk confirms.

**Doctrinal weight:** This is the project's largest doctrinal direction-lock since "controlled canonization of stochastic generation." Carry the BIOS/OS/UI metaphor, the litmus test, the DM-burden co-equal framing as load-bearing reference points in downstream architectural work.
