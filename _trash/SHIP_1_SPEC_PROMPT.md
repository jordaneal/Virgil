# Ship 1 Spec-Drafting Prompt — Resolution Binding (S33)

**Model selection:** Opus medium (architectural synthesis with clear precedent — extends existing `dnd_pending_roll_directives` infrastructure, follows §59 pure-function pattern, mirrors Track 7 #2 verifier-class extension shape).

**Session shape:** Spec drafting against partial precedent. You are templating against three existing patterns (§59 pure-function-in-orchestration, Track 7 #2's locked-violation-class architecture, Track 7 #1's AUTHORITATIVE-CANON prompt-block rendering) but synthesizing the resolution-binding shape itself for the first time.

**Output:** `/home/jordaneal/virgil-docs/RESOLUTION_BINDING_SPEC.md` v1. Spec doc with §1–§10 proposed decisions and §11 decision points needing Jordan's call. NO code ships this session. NO doc-update pass except writing the spec itself.

---

## Required reading before drafting

Read these in order. They establish the architectural priors this spec inherits.

1. **`text files/MULTIPLAYER_FIXES.md` v2** — particularly §1 diagnosis, §2 north-star principles, §4 Ship 1 Resolution Binding (this is the planner-locked architectural shape; do not re-litigate the fix shape, only fill in implementation detail), §9 doctrine work, §12 decision points (decisions 1, 2, 6, 7 are relevant to Ship 1).

2. **`text files/S32_MULTIPLAYER_PLAYTEST_FINDINGS.md`** — Finding L is Ship 1's primary closure target. Read it carefully; the spec's §1 problem statement should reference Finding L's evidence directly (specific player-rolls-6-says-passed scenario, F-45 regression context).

3. **Server-side: `BUG_1_SPEC.md`** (`/home/jordaneal/virgil-docs/BUG_1_SPEC.md`). **§L (Phase 2 trigger criteria) is load-bearing for this spec** — see "Bug 1 Phase 2 lineage" section below.

4. **Existing engine surfaces:**
   - `dnd_engine.py` — `dnd_pending_roll_directives` schema (Phase 1 ship; needs `dc INTEGER` column added per Ship 1), `pending_directive_*` CRUD helpers, `pending_directive_consume`
   - `dnd_orchestration.py` — `compute_persistence_directive` and siblings as the §59 pure-function template; this is the shape `resolve_directive` follows
   - `narration_verifier.py` — Track 7 #2's locked four-violation-class structure (`FABRICATED_COMBATANT`, `VERDICT_CONTRADICTION`, `STATE_MUTATION_CLAIM`, `ACTOR_OMISSION`); Ship 1 adds a fifth class
   - `discord_dnd_bot.py` — `_handle_dm_roll_arrival` (Phase 1's matcher branch — emits `directive_would_fire_dm_respond:` log; Ship 1 replaces this with `_dm_respond_and_post` invocation), `_dm_respond_and_post` itself (the auto-narration target)
   - `adjudicator.py` — Track 7 #1's CHECK_ACTION binding; Ship 1's resolution binding composes cleanly with this on a different surface (Phase 1 + Ship 1 cover DM-typed-directive flow; Track 7 #1 covers player-narrated-action flow)

5. **Doctrine context:**
   - §1a (LLM never decides mechanical outcomes) — Ship 1's controlling invariant
   - §17 (single write paths per field) — `dnd_pending_roll_directives.dc` is a new single-writer field
   - §59 (pure-function-in-orchestration) — `resolve_directive` is the eighth instance
   - Doctrine candidate from MULTIPLAYER_FIXES.md §9: "renderer not ruler" framing (do not anchor in Ship 1; spec language can use it freely)

---

## What this ship closes

- **Finding L** — Roll resolution unbound from rolled value. Player rolls 6 vs DC 10, says "I passed," bot narrates success. Ship 1 makes this structurally impossible.
- **F-45 regression** — Track 7 #1's CHECK_ACTION binding doesn't cover the DM-typed-directive flow. Ship 1 covers it.
- **Bug 1 Phase 2** — ships as a side effect (see lineage section below). The Phase 2 trigger criteria locked in BUG_1_SPEC.md §L are satisfied by Ship 1's implementation, not by waiting for accumulated Phase 1 telemetry.

---

## Bug 1 Phase 2 lineage (load-bearing — do not skip)

Phase 2's locked trigger criteria from BUG_1_SPEC.md §L gate the binary "should auto-narration fire at all?" question. Ship 1 answers that question affirmatively *and* adds a stronger constraint: when auto-narration fires, it fires with resolution binding so the LLM cannot drift on the outcome.

Spec must include a dedicated section (recommend §3 or §4) titled **"Bug 1 Phase 2 absorption"** that:

1. Lists each Phase 2 trigger criterion verbatim from BUG_1_SPEC.md §L
2. Explains how Ship 1's implementation satisfies each criterion structurally (not via Phase 1 telemetry accumulation)
3. Adds a fifth criterion (narrated outcome matches roll-vs-DC verdict in 100% of consumed directives) and names how it is measured (recommend: `ROLL_OUTCOME_DRIFT` violation count = 0 across one play session)
4. Explicitly marks Bug 1 Phase 2 as "shipped via Ship 1, S34" — when Ship 1 promotes ✅, the ROADMAP entry for Bug 1 Phase 2 flips ✅ in the same doc-update pass

This section preserves Bug 1's spec lineage. Without it, Phase 2 becomes a ghost item that disappears silently when Ship 1 lands.

---

## Architectural shape (planner-locked, do not re-litigate)

The fix shape is locked in MULTIPLAYER_FIXES.md §4. Spec fills in implementation detail; spec does NOT propose alternative fix shapes.

**Locked elements:**

- New pure function `resolve_directive(directive_row, avrae_event) → ResolutionResult` lives in `dnd_orchestration.py` (sibling to `compute_persistence_directive` etc per §59). No DB writes; pure compute.
- `ResolutionResult` is an immutable frozen dataclass with fields: `actor`, `check_kind` (`'check' | 'save'` — cast deferred per §4.4 decision 5), `skill_or_save`, `dc`, `roll_total`, `passed`, `rolled_at`, `directive_id`.
- New `dnd_pending_roll_directives.dc INTEGER` column (idempotent migration). DC parsed from directive emit text per §4.4 decision 1.
- Phase 2 wiring: matcher consumes directive → calls `resolve_directive` → auto-fires `_dm_respond_and_post` with `ResolutionResult` rendered as AUTHORITATIVE-CANON prompt block at top-of-prompt + bottom-of-prompt repeat per §48 (concrete-in-prompt narrows drift).
- New verifier class `ROLL_OUTCOME_DRIFT` in `narration_verifier.py` per Track 7 #2's locked-class pattern. Detection: keyword scan for success/failure terms cross-referenced against `passed`. 1-retry loop per existing verifier escalation.

**AUTHORITATIVE-CANON block shape** (locked in MULTIPLAYER_FIXES.md §4.1; spec confirms exact wording):

```
═══ AUTHORITATIVE ROLL RESOLUTION ═══
{Actor} attempted a {Skill/Save} {check/save} (DC {dc}).
Roll total: {roll_total}.
Outcome: {PASSED/FAILED}.

You MUST narrate this as a {success/failure}. {Actor} does {NOT} {achieve the intended outcome}.
Do NOT narrate {opposite outcome}. Do NOT invent an alternative interpretation.
═══
```

Bottom-of-prompt repeat: `Outcome: {PASSED/FAILED}.` (single line, no decoration — §48 concrete repetition pattern).

---

## Decisions to lock in §11

These are the seven decisions named in MULTIPLAYER_FIXES.md §4.4. Spec must walk each with trade-offs, recommended default, confidence level, and surfaced additions. **The recommendations in MULTIPLAYER_FIXES.md are planner leans, not locks** — spec author's job is to either confirm or push back with reasoning.

1. **DC source.** Two options: (a) parse DC from the directive emit text and store on `dnd_pending_roll_directives.dc`; (b) DM types DC explicitly in directive (`!check perception 10`) and matcher parses. Planner lean: (a). Spec must propose the parser regex, edge cases (multi-digit DC, missing DC, DC at different positions in the text), and graceful-degrade behavior when parsing fails.

2. **No-DC directives.** When DM types `!check perception` without a DC, what's the resolution shape? (a) default DC 10 always; (b) skip resolution binding, fall through to existing free-narration flow; (c) prompt DM via #dm-aside to set a DC before resolution fires. Planner lean: (b). Spec must define the fall-through path explicitly — does Phase 1 telemetry still fire? Does the directive still get consumed on roll arrival?

3. **Crit handling.** Nat 20 / nat 1 — D&D 5e RAW: only attack rolls and death saves auto-succeed/fail. Skill checks: nat 20 is just a high roll, nat 1 is just a low roll. Planner lean: RAW for v1. Spec must address: does Avrae's embed surface nat-20/nat-1 distinctly, or just `roll_total`? If distinctly, does ResolutionResult capture that for future table-rule customization (v1.x)?

4. **Multi-actor mismatch path.** Phase 1 logs `directive_actor_mismatch:` and posts wrong-actor aside; row stays alive. Confirm Ship 1 does not change this. Spec must address the multi-actor batched-turn evidence from S32 (Ship 4.5 candidate) — does Ship 1's verify checkpoint surface ambiguity rate, and how is "ambiguity" measured?

5. **Save and cast directive resolution.** Saves: same shape as check (DC vs roll_total). Cast: subtler — spell-cast directives don't have a DC at emit time; resolution happens at target's save. Planner lean: Ship 1 covers check + save only; cast directives stay in Phase 1 telemetry-only behavior. Spec must define the cast-skip path explicitly (matcher recognizes cast, skips resolution binding, leaves directive consumed) and file cast-resolution as v1.x.

6. **Phase 2 trigger criterion 5.** Add to BUG_1_SPEC.md §L: "narrated outcome matches roll-vs-DC verdict in 100% of consumed directives." Measured via `ROLL_OUTCOME_DRIFT` verifier (zero violations across one session = pass). Spec must define what counts as a "session" for this measurement and whether multi-session calibration is needed before promotion.

7. **Backward compatibility — manual-trigger flow.** When Ship 1 wires resolution binding to Phase 2's auto-narration path, what happens to the manual-trigger flow that exists today (DM types narration himself)? Three options: (a) manual-trigger bypasses resolution binding entirely; (b) manual-trigger also runs resolution binding; (c) deprecate manual-trigger flow. Planner lean: (a). Spec must address: how is "manual-trigger" detected? Does the directive still get consumed when DM narrates manually before Avrae rolls?

**Surface any additional decisions** the recon pass exposes. Track 7 #2's spec surfaced 18 §11 decisions; Ship 1 may surface more than 7. Don't artificially constrain the count.

---

## Recon questions (answer before §11 lock)

These are not §11 decisions — they're prerequisite reconnaissance. Spec drafts assume answers; if recon contradicts assumption, escalate via HALT (per Bug 1 spec's Q3 precedent).

1. **Avrae embed shape for `!check`/`!save` results.** Does the embed include `roll_total` as an integer in a parseable field, or does it require regex extraction from text? Recon `parse_avrae_embed` and the embed samples in journal logs from S30+ (post-Track 7 #2 ship).

2. **Nat-20 / nat-1 surface.** Does the embed surface "natural 20" or "natural 1" distinctly, or just the final total? If distinct, where in the embed structure?

3. **`_dm_respond_and_post` invocation surface for the resolution case.** Phase 1's matcher branch logs `directive_would_fire_dm_respond:` but does NOT call `_dm_respond_and_post`. Ship 1 needs to call it. Recon: what arguments does `_dm_respond_and_post` need? Does it expect player input? If yes, what's the synthesized "input" for an auto-fired resolution narration? (The directive's actor name? A synthesized "ROLL_RESOLUTION" sentinel? Empty string?)

4. **AUTHORITATIVE-CANON block insertion point.** Where in `build_dm_context`'s prompt assembly does the resolution block insert? Top-of-prompt is locked; recon must confirm this means "before retrieval block" or "before persistence directive" or some other anchor. Mirror the Track 7 #1 CHECK_ACTION rendering position if applicable.

5. **`narration_verifier` retry loop integration.** Does the existing 1-retry escalation pattern need extension for `ROLL_OUTCOME_DRIFT`, or does the new violation class slot in cleanly? Recon `verify_narration` and the four existing classes' retry behavior.

If any recon finding breaks the locked architectural shape (per the Q3 precedent in BUG_1_SPEC.md), HALT before drafting §1–§10 and surface the finding.

---

## Spec structure (use this skeleton)

```
§1 — Problem statement (Finding L evidence + F-45 regression context)
§2 — Architectural shape (locked elements; do NOT re-litigate)
§3 — Bug 1 Phase 2 absorption (lineage preservation)
§4 — Resolution binding pure function (resolve_directive)
§5 — ResolutionResult dataclass
§6 — DC parsing + dnd_pending_roll_directives.dc column
§7 — AUTHORITATIVE-CANON prompt block (top + bottom rendering)
§8 — narration_verifier ROLL_OUTCOME_DRIFT class
§9 — Phase 2 wiring (matcher → resolve_directive → _dm_respond_and_post)
§10 — Telemetry (new log lines, extension to existing log lines)
§11 — Decision points (7 named + any surfaced additions)
§12 — Test plan (~40 assertions across 2 new test files + extensions)
§13 — Live-verify scenario (Discord steps + grep patterns; populates tests-to-run-post-session.md after lock)
§14 — Doctrine candidates filed (do NOT anchor — file per §59 pattern-watch)
§15 — Out-of-scope (cast resolution, player-typed !check, combat-mode rolls, F-58)
```

---

## What this spec session does NOT do

- Does NOT ship code. Spec only.
- Does NOT modify ROADMAP.md, DOCTRINE.md, FAILURES.md, VIRGIL_MASTER.md, WHY.md. Doc-update pass happens after Ship 1 implementation lands.
- Does NOT propose alternative architectural shapes. The shape is locked in MULTIPLAYER_FIXES.md §4. Spec fills in implementation detail.
- Does NOT extend scope to cast resolution, player-typed !check flow, combat-mode rolls, or F-58. Each has explicit out-of-scope language in MULTIPLAYER_FIXES.md §4.7; honor those boundaries.

---

## Output expectations

- Spec at `/home/jordaneal/virgil-docs/RESOLUTION_BINDING_SPEC.md` v1
- Length comparable to TRACK_7_2_SPEC.md (architectural-synthesis precedent)
- §11 decisions each get: trade-offs, recommended default, confidence level, surfaced additions, related-decisions cross-references
- §13 live-verify scenario specific enough to walk in Discord against test campaign
- Tabular handoff at end of session: file path, decision count, recon findings, any HALT escalations, ready-for-review status

Companion review doc (`RESOLUTION_BINDING_REVIEW.md`) drafts in S33 part 2 after Jordan reads this spec. Don't draft the review doc this session.
