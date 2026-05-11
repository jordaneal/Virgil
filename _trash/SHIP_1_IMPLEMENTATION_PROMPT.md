# Ship 1 Implementation Prompt — Resolution Binding (S34)

**Model selection:** Opus high. Load-bearing primitive (`ResolutionResult` template and AUTHORITATIVE-CANON binding shape echo into F-55 #5.4 and possibly #5.2). Multi-surface implementation: engine schema migration, new pure function in orchestration layer, new verifier class, Phase 2 wiring at the Discord matcher branch.

**Session shape:** Implementation against a LOCKED spec. The spec is exhaustive — your job is to implement what `RESOLUTION_BINDING_SPEC.md` §1–§10 specify, run the §12 test plan, walk the §13 live-verify scenarios, and produce the doc-update pass per §5 of the review doc.

**Output:** Working code, ~40 test assertions across 2 new + 2 extended test files, ✅ on all six §13 live-verify scenarios, doc-update pass touching ROADMAP / SESSIONS / DOCTRINE / tests-to-run-post-session.

---

## Required reading before implementation

1. **`/home/jordaneal/virgil-docs/specs/RESOLUTION_BINDING_SPEC.md`** — LOCKED v1. This is the implementation contract. Every architectural choice is locked; if you find yourself wanting to deviate, HALT and surface to planner first.

2. **`/home/jordaneal/virgil-docs/RESOLUTION_BINDING_REVIEW.md`** — planner-side lock pass. Documents which spec sections were confirmed and which had framing revisions applied. §5 (implementation handoff to S34) lists files touched, test target, promotion criteria, and doc-update plan.

3. **`/home/jordaneal/virgil-docs/specs/BUG_1_SPEC.md`** — Phase 1 spec. Phase 2 absorption is documented in `RESOLUTION_BINDING_SPEC.md` §3; do NOT modify `BUG_1_SPEC.md` itself. Read §L (Phase 2 trigger criteria) to understand what Ship 1 satisfies structurally.

4. **`text files/MULTIPLAYER_FIXES.md`** §4 (Ship 1) and §4.5 (work breakdown) — confirms the calendar (S33–S34) and the Opus-high model choice. §4.4 lists the seven named §11 decisions Code surfaced in the spec; spec §11 has the full 14.

5. **Existing engine surfaces (read as anchors, don't modify beyond Ship 1 scope):**
   - `dnd_engine.py` — `dnd_pending_roll_directives` schema (Phase 1; add `dc INTEGER` column), `pending_directive_*` CRUD, prompt assembly at line 5189 (AUTHORITATIVE-CANON anchor), HARD STOP RULES at line 5081/5327 (bottom-of-prompt echo)
   - `dnd_orchestration.py` — `compute_persistence_directive` and siblings as the §59 pure-function template; `resolve_directive` is sibling #8
   - `narration_verifier.py` — Track 7 #2's four locked classes; ROLL_OUTCOME_DRIFT is class #5
   - `discord_dnd_bot.py` — `_handle_dm_roll_arrival` (Phase 1's matcher branch; Ship 1 replaces the `directive_would_fire_dm_respond:` log emission with `_dm_respond_and_post` invocation), `_dm_respond_and_post` itself, `_post_dm_aside`
   - `adjudicator.py` — Track 7 #1's CHECK_ACTION binding; do NOT couple resolve_directive to `consume_recent_check` (decision §11.13 locked direct `avrae_event` input)

---

## What this ship closes

- **Finding L** (S32 §3.10) — Roll resolution unbound from rolled value
- **F-45 regression** (S25 #3 multiplayer test) — Track 7 #1's CHECK_ACTION binding doesn't cover DM-typed-directive flow
- **Bug 1 Phase 2** — ships as a side effect; ROADMAP entry flips ✅ in the same doc-update pass as Ship 1

---

## Implementation order (recommended)

The spec's §4–§9 sequence is the natural order. Suggested implementation walk:

1. **Schema migration** (spec §6) — add `dc INTEGER` column to `dnd_pending_roll_directives`. Idempotent migration. Test: re-running migration on existing schema is a no-op.

2. **`ResolutionResult` dataclass** (spec §5) — immutable frozen dataclass in `dnd_orchestration.py`. Fields per §5.1. Test: instantiation, immutability, field types.

3. **DC parsing** (spec §6.2) — parser regex extending Phase 1's directive emit path. Edge-case table per §6.3. Test: every edge case in §6.3.

4. **`resolve_directive` pure function** (spec §4) — sibling to `compute_persistence_directive`. Pure compute, no DB writes. Test: pass/fail logic, save shape, cast-skip path (decision §11.5), no-DC fall-through (decision §11.2).

5. **AUTHORITATIVE-CANON rendering** (spec §7) — `render_resolution_block` (top-of-prompt at line 5189 anchor) + `render_resolution_hardstop_echo` (bottom-of-prompt at line 5081/5327 anchor). Test: block shape, hardstop echo shape, empty-when-no-resolution behavior.

6. **`ROLL_OUTCOME_DRIFT` verifier class** (spec §8) — fifth violation class in `narration_verifier.py`. Vocabulary reuse per decision §11.12 (no fork from VERDICT_CONTRADICTION). Test: detection on success-on-failure phrasing, detection on failure-on-success phrasing, no-fire on aligned narration, 1-retry escalation path.

7. **Phase 2 wiring** (spec §9) — replace `directive_would_fire_dm_respond:` log emission in `_handle_dm_roll_arrival` with full call: `resolve_directive` → `_dm_respond_and_post` with `resolution_result` kwarg → fallback aside on raise (decision §11.11). Synthesized `combined_action` per decision §11.8 (bracket-frame). Defensive co-occurrence logging per decision §11.9.

8. **Telemetry** (spec §10) — new log lines + extensions to existing log lines per §10.1–§10.6.

Test files (per spec §12):

- **NEW:** `test_resolve_directive.py` — ~18 engine-layer assertions
- **NEW:** `test_roll_outcome_drift.py` — ~15 verifier assertions
- **EXTEND:** `test_pending_roll_directives.py` — schema migration + dc column assertions (~4 new)
- **EXTEND:** `test_narration_verifier.py` — ROLL_OUTCOME_DRIFT class integration assertions (~3 new)

Target: ~40 assertions total.

---

## Live-verify scenarios (spec §13)

Walk all six scenarios in one Discord session with Jordan present:

- **Scenario A** — Successful check resolution (PASSED) — happy path
- **Scenario B** — Failed check resolution (FAILED) — F-45 surface test, includes the "I passed the check" player-self-report attempt
- **Scenario C** — No-DC directive fall-through (decision §11.2 lock)
- **Scenario D** — Multi-actor mismatch (Phase 1 behavior preserved per decision §11.4)
- **Scenario E** — Save resolution (decision §11.5 — check + save covered, cast skipped)
- **Scenario F** — Manual-trigger backward compat (decision §11.7 — DM types narration before/after auto-fire)

For each scenario: run the Discord steps, capture the grep outputs per spec §13.x, confirm expected behavior.

**Promotion criteria (cumulative across all six scenarios):**
- All grep patterns match expected output
- Zero unretried `ROLL_OUTCOME_DRIFT` violations across the session (criterion 5 per spec §3.3)
- All ~40 test assertions pass
- `unexpected_binding_co_occurrence:` log line fires zero times (defensive co-occurrence didn't trigger)

If any scenario fails or the violation count is non-zero, HALT live-verify and surface to planner before doc-update pass.

---

## Doc-update pass (only after live-verify clean)

Per `WORKING_WITH_CLAUDE.md` discipline, doc updates earn their place after empirical validation. If live-verify is clean, doc-update happens in the same S34 session. If live-verify surfaces issues, doc-update waits for S35 cleanup.

Files to touch on clean live-verify:

1. **`text files/ROADMAP.md`** — flip Ship 1 row to ✅ in Status snapshot; flip Bug 1 Phase 2 row to ✅ (same pass); update FOOTINGS queue paragraph to reflect Ship 2 (S35–S37) as next active

2. **`text files/SESSIONS.md`** — S34 entry. Standard shape: "What surfaced," "What shipped," doctrine candidates filed (do NOT anchor yet — both candidates from review §3 await second instance), cross-references. Index entry inserted in chronological position.

3. **`text files/DOCTRINE.md`** — append both unanchored candidates to candidates section per review §3:
   - Engine-bound binding > validator (review §3.1)
   - Reused vocabulary across sibling violation classes (review §3.2)

4. **`text files/tests-to-run-post-session.md`** — append the six §13 live-verify scenarios as documented post-session verify steps, in case future regressions need re-verification.

5. **`text files/MULTIPLAYER_FIXES.md`** — update §10 calendar to reflect S34 ship; update §4 Ship 1 row to ✅. Plan stays active (Ships 2–5 still pending).

**Do NOT touch:**
- `VIRGIL_MASTER.md` — wait for Ship 5 cluster completion or until architectural framing has earned the update
- `WHY.md` — wait for plan completion
- `FAILURES.md` — F-NN entries for Findings A/B/H file when Ships 2/3/4 land (Finding L was the trigger but L doesn't get a separate F-NN since it's a regression of F-45)
- `BUG_1_SPEC.md` — server-only doc; Ship 1 satisfies §L criteria structurally per spec §3, no spec edit needed

---

## HALT conditions

HALT and surface to planner before proceeding if any of:

- Recon during implementation reveals the locked architectural anchors are different than spec §2 / §4 / §7 assume (e.g., `dnd_engine.py:5189` is no longer the right insertion point; `_dm_respond_and_post` signature changed since recon)
- Any spec §11 decision feels wrong during implementation (e.g., bracket-frame synthesized input produces garbled narration in dry-run testing — surface before live-verify)
- A test assertion fails in a way that suggests the spec is wrong, not the implementation
- Live-verify Scenario B (the F-45 surface) doesn't behave as expected — the "I passed" self-report still drifts the bot narration somehow
- ROLL_OUTCOME_DRIFT violations non-zero during live-verify
- `unexpected_binding_co_occurrence:` fires during live-verify

HALT means: stop work, write a brief surfacing note (what was expected, what was observed, hypothesis), do NOT continue past the HALT condition.

---

## Tabular handoff at end of session

End the session with a structured handoff table. Standard fields:

| Field | Value |
|-------|-------|
| Code shipped | (file paths + line counts) |
| Tests added | (file counts + assertion counts) |
| Tests passing | (X / Y) |
| Live-verify scenarios run | (A–F status, one line each) |
| Promotion criteria met | (yes / no / partial) |
| Doc-update pass | (files touched or "deferred to S35") |
| HALT escalations | (count + brief description, or "none") |
| Ship 1 status | (✅ promoted / ⏳ pending / 🔴 blocked) |
| Bug 1 Phase 2 status | (✅ shipped as side effect / ⏳ pending / 🔴 blocked) |
| Next session recommendation | (S35 Ship 2 spec drafting / S35 cleanup / other) |

---

## What this session does NOT do

- Does NOT modify `BUG_1_SPEC.md` (server-only; Phase 2 absorption is documented in Ship 1's spec §3, not in Bug 1's spec)
- Does NOT touch Ship 2/3/4/5 work (each is a separate ship per `MULTIPLAYER_FIXES.md`)
- Does NOT anchor doctrine candidates (both filed unanchored per review §3; anchor when second instance surfaces in a future ship)
- Does NOT extend scope to cast resolution, player-typed `!check`, or combat-mode rolls (decisions §11.5 and spec §15 explicit out-of-scope)
- Does NOT begin #5.1 Combat Entry Assist live-verify (separate session; can fit between S34 and S35 if Ship 1 is clean)
