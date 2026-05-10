# Ship 1 — Resolution Binding — Design Review v1

**Status:** REVIEW v1 — S33 part 2. Companion to `RESOLUTION_BINDING_SPEC.md` v1 (DRAFT). Walks each §11 decision with planner-side trade-offs, lock confirmation or pushback, and surfaced additions. Output of this doc is the lock pass — `SPEC.md` updates from DRAFT to LOCKED after Code reads this review and applies the two requested revisions.
**Pattern:** Standard spec-then-review-then-implement cadence per `WORKING_WITH_CLAUDE.md`. Spec drafts; review locks; implementation follows in S34.
**Track:** Multiplayer Fixes — Ship 1. Closes Finding L, F-45 regression, Bug 1 Phase 2 (side effect).

---

## Review summary

| Field | Value |
|-------|-------|
| **Decisions reviewed** | 14 (7 named in MULTIPLAYER_FIXES.md §4.4 + 7 surfaced by spec) |
| **Decisions locked at Code's recommendation** | 12 |
| **Decisions locked with revision request** | 2 (§11.4, §11.14 — measurement framing only, not architectural change) |
| **Decisions pushed back** | 0 |
| **HALT escalations** | None — Code's spec contained no HALTs; review surfaces no new ones |
| **Architectural shape changes** | None — locked shape from MULTIPLAYER_FIXES.md §4 holds |
| **Bug 1 Phase 2 absorption** | Confirmed clean per spec §3 |
| **Doctrine candidates filed** | 2 — both filed not anchored per §59 (engine-bound binding > validator; reused vocabulary across sibling classes) |
| **Ready-for-implementation status** | Yes, after Code applies the two §11 framing revisions in §11.4 and §11.14 |
| **Implementation session** | S34, Opus high per MULTIPLAYER_FIXES.md §4.5 |

---

## §1. How to read this review

For each §11 decision in `RESOLUTION_BINDING_SPEC.md`, this doc records:

1. **The question** (one-line restatement)
2. **Code's lock recommendation** (verbatim from spec)
3. **Planner review** — confirm, push back, or revise
4. **Lock outcome** — what Code applies before SPEC.md flips to LOCKED status

When the lock outcome differs from Code's recommendation, the difference is small and framing-only (measurement language, criterion wording) — not architectural pushback. The spec's architectural shape is intact.

---

## §2. Decision walks

### §2.1 Decision 1 — DC source

**Question:** Where does the DC come from? Inline parser (`!check perception 10`) vs explicit flag (`!check perception -dc 10`)?

**Code's lock:** (a) inline parser. Trailing-DC integer extension to existing parser path.

**Planner review:** **Confirm.** Inline matches existing precedent and minimizes DM friction. The spec's parser regex (§6.2) and edge-case table (§6.3) are exhaustive enough for v1. Code's HIGH confidence is warranted.

**Lock outcome:** (a). No revision.

---

### §2.2 Decision 2 — No-DC directive behavior

**Question:** When DM types `!check perception` without a DC, what happens?

**Code's lock:** (b) skip resolution binding, fall through to existing free-narration flow. Phase 1 telemetry still fires; directive consumed normally.

**Planner review:** **Confirm.** Preserves DM authority over which checks have stakes. Falls cleanly through to Phase 1 behavior — no resolution binding, no AUTHORITATIVE-CANON block, no ROLL_OUTCOME_DRIFT verifier check. The directive lifecycle is unchanged from Phase 1.

**Lock outcome:** (b). No revision.

---

### §2.3 Decision 3 — Crit handling

**Question:** Nat 20 / nat 1 — auto-succeed/fail or RAW?

**Code's lock:** RAW for v1 (only attack rolls and death saves auto-succeed/fail per 5e rules). ResolutionResult dataclass captures `nat` and `crit` fields per recon Q2 even though v1 doesn't act on them — sets up table-rule customization as a v1.x ship without schema migration.

**Planner review:** **Confirm.** RAW is correct for v1; carrying the data without acting on it is the right defensive shape. v1.x can flip a single behavior bit when table-rule customization ships.

**Lock outcome:** RAW. No revision. Filed: v1.x candidate for table-rule crit behavior.

---

### §2.4 Decision 4 — Multi-actor mismatch path

**Question:** What happens when a roll arrives whose actor doesn't match the directive's actor?

**Code's lock:** Phase 1 behavior unchanged — log `directive_actor_mismatch:`, post wrong-actor aside to #dm-aside, directive row stays alive. Ship 1 does not change this.

**Planner review:** **Confirm Code's architectural call. Request framing revision to spec §3.2.**

The architectural call is right. The framing in §3.2's table cell ("S32 measured 75% — borderline below criterion 2's 80% threshold") reads like measurement gerrymandering. The 75% raw rate includes session-open `directive_creation_skipped_no_footer` events, which are not bind failures — they are correct-handling non-events (no footer actor existed at session-open time, so no bind could happen).

**Revision request to Code:** Update §3.2's row 2 cell from:

> "S32 measured 75% (borderline below)."

To:

> "S32 measured 75% raw / >80% adjusted for legitimate session-open no-footer skips. The 80% criterion measures bind-failure rate among directives that had a footer actor available to bind to; session-open `directive_creation_skipped_no_footer` events are correct-handled non-events, not bind failures, and are excluded from the denominator. Adjusted measurement satisfies criterion 2."

This says exactly what Code's recommendation said but in honest measurement language. Same outcome, no gerrymandering smell.

**Lock outcome:** Confirm Phase 1 behavior preserved + revision applied to §3.2 wording.

---

### §2.5 Decision 5 — Save and cast directive resolution

**Question:** Does Ship 1 cover save and cast resolution, or only check?

**Code's lock:** Check + save (same shape: DC vs roll_total). Cast deferred to v1.x — cast directives stay in Phase 1 telemetry-only behavior; cast resolution requires target-side save adjudication that Track 7 #1 partially covers but is out of scope for Ship 1.

**Planner review:** **Confirm.** The save shape is genuinely identical to check — DC vs roll_total, pass/fail, same render block, same verifier. Cast is structurally different (spell-effect resolution at target's save) and earns its own spec.

**Lock outcome:** Check + save. Cast filed v1.x. No revision.

---

### §2.6 Decision 6 — Phase 2 trigger criterion 5

**Question:** What's the fifth criterion added to BUG_1_SPEC.md §L?

**Code's lock:** "Narrated outcome matches roll-vs-DC verdict in 100% of consumed directives." Measured via ROLL_OUTCOME_DRIFT verifier (zero unretried-or-retry-failed violations across one session = pass). Surfaced refinement: retry-passed cases don't count as criterion-5 violations because the final-posted narration is clean.

**Planner review:** **Confirm.** The retry-passed exclusion is correct — criterion 5 measures the player-visible outcome, and the verifier-retry path produces clean player-visible outcomes. The greppable shape (`grep "violation_class=roll_outcome_drift" | grep "retry_passed=0\|retry_passed=-" | wc -l`) is unambiguous and operationally clean.

**Lock outcome:** Criterion 5 wording locked verbatim per spec §3.3 + §11.6 refinement. No revision.

---

### §2.7 Decision 7 — Backward compatibility (manual-trigger flow)

**Question:** When DM manually narrates after a directive consume, what happens?

**Code's lock:** (a) manual-trigger bypasses resolution binding entirely. Bot's auto-fire still happens; if DM narrates manually, both appear; DM can delete bot message via Discord standard. Race-detection deferred to v1.x.

**Planner review:** **Confirm.** Manual override is a feature, not a bug. The race condition is observable but not pathological — DM can clean up via Discord's normal message-delete affordance. Detection is a v1.x improvement, not a Ship-1 blocker.

**Lock outcome:** (a). No revision.

---

### §2.8 Decision 8 — Synthesized `combined_action` / `actions` shape

**Question:** What goes in the `actions` tuple and `combined_action` string when the matcher auto-fires `_dm_respond_and_post`?

**Code's lock:** (c) bracket-framed semi-sentinel — `[Roll resolution: {actor} rolled {skill} ({kind}); outcome bound at top-of-prompt.]`. MEDIUM-HIGH confidence; live-verify to test bracket handling.

**Planner review:** **Confirm.** The bracket framing signals "narrative directive, not player input" cleanly. Reintroducing F-45 via natural-language synthesis (option b) would be a step backward. The verify-pass scrutiny on LLM bracket handling is the right safety net.

**Surfaced addition (Code asked):** Should synthesized input include the rolled value? Code recommends no; planner agrees — the AUTHORITATIVE-CANON block does the work. Adding rolled value to synthesized input risks the LLM picking up the wrong source of truth.

**Lock outcome:** (c) bracket-framed. No rolled value in synthesized input. No revision.

---

### §2.9 Decision 9 — Defensive ordering when both arbitration and resolution fire

**Question:** What if `build_dm_context` is called with both `arbitration_block` AND `resolution_block` non-empty?

**Code's lock:** (a) render both side-by-side at top-of-prompt + (d) log `unexpected_binding_co_occurrence:` warning. Defensive coding + observability.

**Planner review:** **Confirm.** Suppressing one with priority logic hides information from the LLM. Rendering both with a warning preserves observability if the flow ever produces unexpected co-occurrence. Per the architectural analysis in §2.3, the kwargs are mutually exclusive by flow in v1 — the warning is the canary if the flow ever changes.

**Lock outcome:** (a) + (d). No revision.

---

### §2.10 Decision 10 — Skill normalization at resolve time

**Question:** Does `resolve_directive` apply skill normalization beyond what Phase 1's matcher already does?

**Code's lock:** No. Phase 1's `_normalize_skill_for_match` already handles canonicalization (lowercase, whitespace collapse, alias resolution). Resolution time uses the already-normalized skill from the directive row.

**Planner review:** **Confirm.** Single normalization point per §17. Re-normalizing at resolve time would be redundant and risk drift between match-time and resolve-time normalization rules.

**Lock outcome:** No additional normalization. Resolve consumes Phase 1's normalized skill verbatim. No revision.

---

### §2.11 Decision 11 — Auto-fire failure recovery

**Question:** If `_dm_respond_and_post` raises after directive is consumed, what happens?

**Code's lock:** (a) log failure + (b) post deterministic fallback aside to #dm-aside. Mirrors `narration_verifier`'s escalation-placeholder pattern. Fallback text: `Roll resolution: {actor} {Skill} {kind} at DC {dc} (rolled {roll}). Result: PASSED/FAILED.`

**Planner review:** **Confirm placement at #dm-aside per Jordan's call ("leave dm-aside for clarification questions and handle process").** Players see Avrae's roll embed regardless; #dm-aside fallback gives DM observability of the resolution without polluting #dm-narration with engine-shape strings on the rare failure path.

**Lock outcome:** (a) + (b), fallback to #dm-aside. No revision.

---

### §2.12 Decision 12 — Vocabulary reuse vs fork for ROLL_OUTCOME_DRIFT

**Question:** Reuse VERDICT_CONTRADICTION's existing phrase tables, or fork?

**Code's lock:** (a) reuse. Single vocabulary surface; consistent detection across both classes; one tuning point. Save-specific phrasings flagged for verify-pass reassessment.

**Planner review:** **Confirm.** Single source of truth aligns with §17. The check-success-on-failure detection logic is identical regardless of whether the binding came from adjudicator (CHECK_ACTION) or resolver (ROLL_OUTCOME_DRIFT). Save-specific phrases like "resists" and "shrugs off" are deferred to verify-pass reassessment, which is the right discipline.

**Lock outcome:** (a) reuse. Save-specific phrases reassessed at Ship 1 verify checkpoint. No revision.

---

### §2.13 Decision 13 — `resolve_directive` input source

**Question:** Should `resolve_directive` accept `avrae_event` directly, or delegate to the existing `consume_recent_check` helper in `adjudicator.py`?

**Code's lock:** Direct `avrae_event` input. `consume_recent_check` is the adjudicator's path; resolution binding has its own consume semantics via Phase 1's `pending_directive_consume`. Sharing the helper would couple the two binding paths in a way that complicates either future evolution.

**Planner review:** **Confirm.** Decoupled binding paths are correct — adjudicator binds player-narrated actions; resolver binds DM-typed directives. Both ultimately consume Avrae roll events but the consume semantics are scoped to their own surface. Sharing the helper would create a multi-purpose function with dual-mode behavior, which is the anti-pattern §17 warns against.

**Lock outcome:** Direct `avrae_event` input. No revision.

---

### §2.14 Decision 14 — Debounce / rapid-fire handling

**Question:** Does Ship 1 implement debounce for rapid-fire directives?

**Code's lock:** (a) no debounce in v1. Verify criterion: "if any 60-second window contains >2 auto-fires, file v1.x debounce ship."

**Planner review:** **Confirm Code's architectural call. Request framing revision to verify criterion.**

Two issues with the locked threshold language:

1. The threshold needs to specify *consumed* auto-fires, not emitted directives, to align with Code's §9.7 analysis showing that `pending_directive_replaced` flow means most rapid emits don't produce multiple consumes.

2. The S32 §4.5 evidence (6× investigation directives in 30 seconds) was **test behavior, not natural play.** Jordan was rolling repeatedly to observe how the system responded to a wrong-type directive scenario. Real-play rapid-fire is expected to occur only when the DM corrects a wrong-type directive (e.g., types `!check perception` then realizes it should have been `!check investigation` and re-fires). Without this distinction, the v1.x debounce ship pre-commits on test data.

**Revision request to Code:** Update §11.14's verify criterion language from:

> "If any 60-second window contains > 2 auto-fires, file v1.x debounce ship."

To:

> "S32's observed 6× investigation burst was test behavior (DM checking how the system responded to repeated rolls), not natural play cadence. Real-play rapid-fire is expected to occur only when the DM corrects a wrong-type directive (e.g., types `!check perception` then realizes it should have been `!check investigation` and re-fires). If Ship 1 verify shows >2 *consumed* auto-fires in any 60-second window during natural play, file v1.x debounce ship."

This preserves the discipline (observe before fixing), measures the right thing (consumes not emits), and documents the test-vs-play distinction so future readers don't read the threshold as already-violated.

**Lock outcome:** Confirm (a) no debounce + revision applied to §11.14 verify criterion language.

---

## §3. Doctrine candidates filed (do NOT anchor)

Two candidates filed in spec §14, both per §59 pattern-watch (file unanchored; anchor when second instance surfaces in a future ship).

### §3.1 Engine-computed binding > validator

**Wording (per spec §14.1):** When the engine can compute the canonical answer to a question (pass/fail, target validity, action legality), the engine should compute it and the LLM should render it bound — rather than letting the LLM produce an answer and validating after.

**Planner review:** **File not anchor.** This is the same shape as MULTIPLAYER_FIXES.md §2.3 (structural removal of write authority beats validation), applied at the binding-output layer rather than the write-authority layer. Ship 1 is the first project instance of engine-bound output replacing post-hoc verification. Anchor when second instance surfaces — likely candidate is #5.4 Intent-to-Avrae Resolver, which uses the same shape for target disambiguation binding.

**Lock outcome:** File in DOCTRINE.md candidates section after Ship 1 promotes ✅. Do not anchor.

### §3.2 Reused vocabulary across sibling violation classes

**Wording (per spec §14.2):** When two violation-class siblings detect the same semantic surface (success/failure, contradiction, omission), they share vocabulary tables rather than forking. Tuning happens at the shared surface.

**Planner review:** **File not anchor.** Single-instance after Ship 1; ROLL_OUTCOME_DRIFT reuses VERDICT_CONTRADICTION's tables. Anchor when third sibling reuses the same tables — sibling to §17 (single write paths) but at the verifier-vocabulary surface.

**Lock outcome:** File in DOCTRINE.md candidates section after Ship 1 promotes ✅. Do not anchor.

---

## §4. Spec revisions to apply before LOCKED status

Code applies the following two revisions before flipping `RESOLUTION_BINDING_SPEC.md` from DRAFT to LOCKED:

### §4.1 Revision to §3.2 row 2

Current text:

> "S32 measured 75% (borderline below)."

Replace with:

> "S32 measured 75% raw / >80% adjusted for legitimate session-open no-footer skips. The 80% criterion measures bind-failure rate among directives that had a footer actor available to bind to; session-open `directive_creation_skipped_no_footer` events are correct-handled non-events, not bind failures, and are excluded from the denominator. Adjusted measurement satisfies criterion 2."

### §4.2 Revision to §11.14 verify criterion

Current text:

> "If any 60-second window contains > 2 auto-fires, file v1.x debounce ship."

Replace with:

> "S32's observed 6× investigation burst was test behavior (DM checking how the system responded to repeated rolls), not natural play cadence. Real-play rapid-fire is expected to occur only when the DM corrects a wrong-type directive (e.g., types `!check perception` then realizes it should have been `!check investigation` and re-fires). If Ship 1 verify shows >2 *consumed* auto-fires in any 60-second window during natural play, file v1.x debounce ship."

Both revisions are framing-only — they preserve every architectural lock and only sharpen measurement-honesty language. Spec status flips DRAFT → LOCKED after revisions land.

---

## §5. Implementation handoff to S34

After Code applies the two revisions and the spec flips to LOCKED, implementation begins in S34 per the cadence in `WORKING_WITH_CLAUDE.md`.

| Field | Value |
|-------|-------|
| **Implementation session** | S34 |
| **Model** | Opus high (load-bearing primitive; resolution binding template will echo into F-55 #5.4 and possibly #5.2) |
| **Files touched** | `dnd_engine.py` (dc column migration), `dnd_orchestration.py` (`resolve_directive` + `ResolutionResult`), `narration_verifier.py` (ROLL_OUTCOME_DRIFT class), `discord_dnd_bot.py` (Phase 2 wiring at `_handle_dm_roll_arrival`) |
| **Test target** | ~40 assertions across 2 new + 2 extended files per spec §12 |
| **Live-verify scenarios** | 6 (A–F) + aggregate criteria per spec §13 |
| **Promotion criteria** | Per spec §13 + Bug 1 Phase 2 criterion 5 (zero unretried ROLL_OUTCOME_DRIFT violations across one session) |
| **Doc-update pass** | After live-verify clean: ROADMAP.md (Ship 1 ✅, Bug 1 Phase 2 ✅), SESSIONS.md (S34 entry), DOCTRINE.md (file two candidates), tests-to-run-post-session.md (live-verify scenarios A–F) |

---

*End of review v1. Session 33 part 2.*

---

## Tabular handoff

| Field | Value |
|-------|-------|
| **File written** | `/home/jordaneal/virgil-docs/RESOLUTION_BINDING_REVIEW.md` |
| **Status** | REVIEW v1 — locks applied; spec flips to LOCKED after Code applies the two §4 revisions |
| **Decisions reviewed** | 14 |
| **Decisions confirmed at Code's recommendation** | 12 |
| **Decisions confirmed with revision request** | 2 (§11.4, §11.14 — framing only) |
| **Decisions pushed back** | 0 |
| **Architectural changes** | None |
| **Spec revisions to apply** | 2 (§3.2 measurement framing; §11.14 verify criterion language) |
| **Doctrine candidates filed (not anchored)** | 2 — engine-bound binding > validator (§3.1); reused vocabulary across sibling classes (§3.2) |
| **Ready-for-implementation status** | Yes, after Code applies the two §4 revisions |
| **Implementation session** | S34, Opus high |
| **Companion spec status** | DRAFT → LOCKED after revisions applied |
