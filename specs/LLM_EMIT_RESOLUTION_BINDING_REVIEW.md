# Ship A — LLM-Emitted-Directive Resolution Binding — Design Review v1

**Status:** REVIEW v1 — S35b planner-side review. Companion to `LLM_EMIT_RESOLUTION_BINDING_SPEC.md` v1 DRAFT. Walks each §11 decision (12 pre-locked from v3 §12, 6 surfaced during S35 drafting) with planner-side trade-offs, lock confirmation or pushback, and surfaced spec revisions. Output of this doc is the lock pass — spec flips DRAFT → LOCKED after Code applies the framing revisions in §4 below.
**Pattern:** Standard spec-then-review-then-implement cadence per `WORKING_WITH_CLAUDE.md`. Spec drafts; review locks; implementation follows in S36. Same shape as Ship 1's S33 part 1 + part 2 cadence (`RESOLUTION_BINDING_SPEC.md` + `RESOLUTION_BINDING_REVIEW.md` precedent).
**Track:** Multiplayer Fixes — Ship A. Closes Finding L on the primary play loop (LLM-emitted-directive surface) per `MULTIPLAYER_FIXES.md` v3 §4.

---

## Review summary

| Field | Value |
|---|---|
| **Decisions reviewed** | 18 (12 pre-locked from v3 §12, 6 surfaced in spec §11.B.1–B.6) |
| **Decisions locked at Code's recommendation** | 16 |
| **Decisions locked with revision request** | 2 (§11.B.2 texture-computation surface, §11.B.6 spec-location convention — both framing-only, not architectural) |
| **Decisions pushed back** | 0 |
| **HALT escalations** | None — Code's spec contained no HALTs; review surfaces no new ones |
| **Architectural shape changes** | None — locked shape from v3 §4 holds |
| **Doctrine candidate disposition** | C1 wait per locked decision 11 (unchanged). C2 stays at one instance (unchanged). New candidate §16.3 reframed as §17-amendment-candidate (review framing revision). |
| **Spec revisions surfaced** | 6 framing/clarification revisions (§4 below). Each is line-level wording, not section-level rewrite. |
| **Ready-for-implementation status** | Yes, after Code applies the six §4 revisions. |
| **Implementation session** | S36, Opus high per v3 §4.6 |

---

## §1. How to read this review

For each §11 decision in `LLM_EMIT_RESOLUTION_BINDING_SPEC.md`, this doc records:

1. **The question** (one-line restatement)
2. **Code's lock recommendation** (verbatim from spec or paraphrase for length)
3. **Planner review** — confirm, push back, or revise
4. **Lock outcome** — what Code applies before SPEC.md flips to LOCKED status

When the lock outcome differs from Code's recommendation, the difference is small and framing-only (wording precision, edge-case clarification) — not architectural pushback. The spec's architectural shape is intact.

12 of the 18 decisions are pre-locked from `MULTIPLAYER_FIXES.md` v3 §12 (operator review May 11). Review confirms these as already-decided; no re-litigation. The 6 spec-drafting-surfaced decisions (§11.B.1–B.6) get full review treatment.

---

## §2. Pre-locked decisions (v3 §12 — confirmation pass)

These 12 decisions were operator-reviewed and locked before spec drafting. Review confirms each survives spec implementation without architectural drift.

| # | v3 §12 lock | Spec implementation | Review outcome |
|---|---|---|---|
| 1 | v3 supersedes v2 | (no spec implementation — planning lock) | ✅ confirm |
| 2 | A.1 inline `!check skill DC` | §7.1 regex, §12 prompt-side change | ✅ confirm; recon Test 1 evidence holds (Avrae silently ignores trailing integer, parse_skill_and_dc splits cleanly) |
| 3 | A.2 Avrae recon — form (a) clean | §2.1 locked; §7.3 edge cases | ✅ confirm; logs at 08:33:14–20 prove the format end-to-end on shipped Ship 1's writer surface |
| 4 | A.4 `compute_stakes_tier` as §59 9th sibling | §5 in full | ✅ confirm; sibling shape matches `compute_persistence_directive` et al. precedent |
| 5 | A.5 Separate `ResolutionTexture` | §4 in full | ✅ confirm with framing revision (see §3.B.2 below — `dataclasses.replace` ambiguity in spec wording needs clarification) |
| 6 | A.6 Accept stale + TTL=300s | §3.4 | ✅ confirm; phantom-binding three-condition compound argument holds |
| 7 | A.8 Two-embed UX | (operationally unchanged) | ✅ confirm |
| 8 | Ship 4.5 criterion shifts to Ship A verify | §15.10 | ✅ confirm |
| 9 | Ship 5 5a (Finding J) retired | (Ship 5 spec inherits) | ✅ confirm |
| 10 | Corpus discipline — defer to observation | §15 mentions; no parallel corpus | ✅ confirm; §8.3 / §9.2 / §10.2 phrasing "locked v1, tunable at verify checkpoint" honors the discipline |
| 11 | C1 doctrine timing — wait for Ship A verify | §16.1 | ✅ confirm; no pre-anchoring |
| 12 | Wrong-skill behavior — option (b) aside + row stays alive | §13 in full | ✅ confirm; aside copy template + `_wrong_skill_aside` analog to Ship 1's `_wrong_actor_aside` cleanly mirrors the existing pattern |

**Lock outcome for pre-locked decisions: all 12 confirmed at v3 §12 outcome. Three (5, 6, 12) get cross-referenced revisions for spec wording elsewhere — see §3 + §4 below.**

---

## §3. Surfaced decisions (spec §11.B.1–B.6 — full review)

### §3.B.1 — Multi-emit parser behavior (last-match vs first-match)

**Question:** If LLM emits >1 directive in a response, which one binds?

**Code's lock:** (b) last-match. HIGH confidence. `_LLM_EMIT_DIRECTIVE_RX.finditer` → take `matches[-1]`. Log `llm_emit_multi_directive_count:` when `len(matches) > 1` for empirical-baseline observability.

**Planner review:** **Confirm.** Multi-emit is rare under HARD STOP RULE 5 enforcement; last-match matches the prompt-side framing ("your reply MUST end with the roll request"). The observability log is the right shape — if the multi-emit rate is meaningful (>1% of responses), it surfaces as a calibration item without changing the behavior.

**Surfaced addition (Code asked):** None additional. Spec covers cleanly.

**Lock outcome:** (b) last-match. No revision.

---

### §3.B.2 — Texture computation surface (matcher vs resolve_directive)

**Question:** Where does `compute_resolution_texture` get called?

**Code's lock:** (a) inside `resolve_directive`, new optional kwargs. HIGH confidence. Texture at consume time matches engine-bound discipline.

**Planner review:** **Confirm architectural call. Request framing revision to spec §11.B.2 wording.**

Spec §11.B.2 says (verbatim):

> "With `dataclasses.replace` if frozen-immutability needs preservation OR via direct construction with texture-as-final-kwarg."

This is ambiguous and wrong. ResolutionResult is `frozen=True`; `dataclasses.replace` is for replacing a frozen-instance with a new one bearing modified fields, NOT for in-place mutation. The spec's two options aren't equivalent — they're construction-time vs reconstruct-with-replace. For Ship A, the clean path is **direct construction with `texture` as a kwarg at instantiation time inside `resolve_directive`**. No `replace()` shenanigans.

**Revision request to Code:** Update §11.B.2 paragraph to drop the `dataclasses.replace` mention. Replace with:

> "Texture is constructed at ResolutionResult instantiation time inside `resolve_directive`. ResolutionResult stays `frozen=True`; `dataclasses.replace` is unnecessary and rejected — texture is computed before the instance is created, not patched after."

Same-section §4.2 also benefits from clarification — the "Field invariant: Ship A's writer path produces non-None `texture`. Ship 1's writer path produces `texture=None`." line is correct but reads as if surface determines texture. The actual mechanism is: `resolve_directive` produces non-None texture WHEN scene_state kwarg is supplied. Both writer surfaces (Ship 1 and Ship A) can supply scene_state if they want texture rendering. In practice, Ship 1's surface (DM-typed-directive matcher) gets scene_state in S36 implementation as a side benefit, so Ship 1's resolutions also get texture. This matches spec §17.10's beneficial-side-effect framing.

**Lock outcome:** Confirm Code's (a) inside resolve_directive + revision applied to §11.B.2 wording.

**Related:** §4.2 ResolutionResult extension; §17.10 beneficial side effect.

---

### §3.B.3 — DC band reference table location

**Question:** Where does the LLM see DC band guidance?

**Code's lock:** (a) ROLL DIRECTIVE block via `RollDecision.to_prompt_directive` extension; no recommended-DC pre-computation. HIGH confidence.

**Planner review:** **Confirm.** Co-located guidance is the natural placement. The ROLL DIRECTIVE block is where the LLM looks for the directive shape; adding the DC band table there means the guidance is one read away from the template.

**Surfaced sub-decision (review notes, not new §11 item):** The DC GUIDANCE block adds ~300 chars to every roll-required prompt. Per Ship 1 §24 prompt size telemetry, current prompts run 14–20k chars; +300 is negligible (<2%). No concern.

**Lock outcome:** (a) ROLL DIRECTIVE block. No revision.

---

### §3.B.4 — Stakes-tier inputs scope

**Question:** Which scene_state fields does `compute_stakes_tier` read?

**Code's lock:** (b) recommended scope per §5.2 — five-axis scoring (mode + tension + urgent_clocks + recent_commitment + combat_active). HIGH confidence.

**Planner review:** **Confirm architectural call. Request framing revision to §5.2 scoring shape.**

The "recent_commitment_unresolved" axis in §5.2 says:

> "if recent_commitment_unresolved:       score += 1   # last_player_action contains commitment grammar"

Reading raw `last_player_action` text and running commitment-grammar detection inline duplicates work that `compute_commitment_directive` (the existing §59 sibling, called every turn in `dm_respond`) already does. The cleaner signal is `commitment_signals['fired']` — the boolean output from `compute_commitment_directive`.

But `compute_stakes_tier` is called from the matcher path, which doesn't have `commitment_signals` available — `dm_respond` computes it, but the matcher reads scene state independently. So either:

- (a) The matcher invokes `compute_commitment_directive` again to get `commitment_signals['fired']` (wasted work — commitment directive runs twice per turn)
- (b) Stakes reads `last_player_action` text directly with its own grammar detection (duplicates parser logic — minor risk of drift between detectors)
- (c) Stakes is approximated: skip the commitment axis OR replace with a simpler signal (`scene_state.last_player_action` non-empty AND contains imperative verbs)
- (d) Defer commitment-aware stakes to S36 implementation — drop the axis from §5.2 v1, see if four axes give enough resolution

**Revision request to Code:** Update §5.2 to use **(c) simpler signal** — replace "recent_commitment_unresolved" with "recent_player_action_strong_intent" derived from `scene_state.last_player_action` being non-empty AND matching a simple verb-class regex (`\b(?:attack|threaten|demand|refuse|accept|commit|leave|enter|attempt)\b`). This is purely engine-bound (player text + regex), avoids re-running commitment-directive computation, and produces approximately the same signal.

If the operator prefers exact-commitment signal, surface as a v1.x ticket: "pass `commitment_signals['fired']` through `_dm_respond_and_post` → matcher path for stakes consumption."

**Lock outcome:** Confirm Code's (b) scope + revision: replace commitment-axis with simpler intent-grammar regex per (c). Spec §5.2 + §5.4 stakes_signals dict updated to reflect.

**Related:** §5.2 scoring shape; §5.5 stakes_tier_log_summary signal name change (`recent_commitment` → `strong_intent`).

---

### §3.B.5 — Mixed-DC multi-emit

**Question:** Behavior when LLM emits multiple directives with mixed DC presence?

**Code's lock:** Last-match per §11.B.1 applies. HIGH confidence.

**Planner review:** **Confirm.** Last-match is consistent regardless of DC presence in the discarded emissions. Spec covers cleanly.

**Lock outcome:** Confirm. No revision.

---

### §3.B.6 — Spec-location convention

**Question:** Where on the server does this spec live?

**Code's lock:** `/home/jordaneal/virgil-docs/specs/LLM_EMIT_RESOLUTION_BINDING_SPEC.md` per dominant convention. HIGH confidence. Surfaces v1.x housekeeping to move flat-located specs (RESOLUTION_BINDING_SPEC.md, BUG_1_SPEC.md) into specs/ for consistency.

**Planner review:** **Confirm location. Request framing revision to v1.x housekeeping framing.**

The recommendation to move RESOLUTION_BINDING_SPEC.md + BUG_1_SPEC.md into specs/ is sound but adds doc-mechanics work without architectural payoff. Per `feedback_compounding_leverage` discipline, the move earns its keep only if cross-references actually break (they don't — SESSIONS / ROADMAP cite filenames, not paths).

**Revision request to Code:** Update §11.B.6 surfaced addition to:

> "v1.x housekeeping candidate (low priority): move `RESOLUTION_BINDING_SPEC.md` + `BUG_1_SPEC.md` from flat `/home/jordaneal/virgil-docs/` to `/home/jordaneal/virgil-docs/specs/` per dominant convention. **Defer indefinitely** unless a future ship requires consistent spec path discovery (e.g., a `/spec-load` slash command or a doc-search tool that assumes specs/ as root). Cosmetic-only; not a v1.x ticket worth scheduling."

This downgrades the recommendation from "v1.x ticket" to "candidate; defer indefinitely."

**Lock outcome:** Confirm specs/ for the new spec + revision to housekeeping framing.

---

## §4. Spec revisions to apply before LOCKED status

Code applies the following six revisions before flipping `LLM_EMIT_RESOLUTION_BINDING_SPEC.md` from DRAFT to LOCKED. All are line-level wording, no section-level rewrites.

### §4.1 Revision to §11.B.2 (texture computation surface)

Current text:

> "(a) inside `resolve_directive`, new optional kwargs. With `dataclasses.replace` if frozen-immutability needs preservation OR via direct construction with texture-as-final-kwarg."

Replace with:

> "(a) inside `resolve_directive`, new optional kwargs. Texture is constructed at ResolutionResult instantiation time inside `resolve_directive`. ResolutionResult stays `frozen=True`; `dataclasses.replace` is unnecessary and rejected — texture is computed before the instance is created, not patched after."

### §4.2 Clarify §4.2 ResolutionResult extension field invariant

Current text:

> "Field invariant: Ship A's writer path produces non-None `texture`. Ship 1's writer path produces `texture=None`."

Replace with:

> "Field invariant: `resolve_directive` produces non-None `texture` when scene_state kwarg is supplied; None otherwise. Both writer surfaces (Ship 1 DM-typed and Ship A LLM-emitted) can supply scene_state if they want texture rendering. In S36 implementation, BOTH surfaces' matcher invocations pass scene_state — so Ship 1's resolutions also get textured rendering as a beneficial side effect (per §17.10). The pre-Ship-A behavior (Ship 1's pass-through `resolve_directive(directive_row, avrae_event)` call without scene_state) continues to work and produces `texture=None`."

### §4.3 Revision to §5.2 stakes-tier scoring shape

Current text (in §5.2 scoring shape pseudocode):

```
if recent_commitment_unresolved:       score += 1   # last_player_action contains commitment grammar
```

Replace with:

```
if strong_intent_in_last_action:       score += 1   # last_player_action matches imperative-verb regex
```

And add to §5.2 prose:

> "**`strong_intent_in_last_action` derivation:** matches `\b(?:attack|threaten|demand|refuse|accept|commit|leave|enter|attempt|charge|cast|strike|defy|swear|insist|interrupt)\b` (case-insensitive) against `scene_state.last_player_action`. Purely engine-bound (player text + regex); no LLM-touched field reads, no re-invocation of `compute_commitment_directive`. The regex list is locked v1; tunable v1.x if logs show false-positive or miss patterns."

§5.4 signals_dict key `recent_commitment` → `strong_intent`. §5.5 `stakes_tier_log_summary` field `recent_commitment={N}` → `strong_intent={N}`.

### §4.4 Revision to §10.2 crit-tier vocabulary (nat-1 + FAILED mode mapping)

Current text:

> "Scene mode dictates whether the memorable beat is funny (downtime/exploration), grim (combat/social), or both (transition)."

`transition` is not a scene mode in the codebase. Replace with:

> "Scene mode dictates whether the memorable beat is funny (downtime/travel — low-stakes contexts where comedy fits), grim (combat/social — high-stakes contexts where comedy breaks immersion), or either (exploration — LLM judges based on scene tone)."

### §4.5 Revision to §15.9 aggregate verify criteria (count threshold)

Current text:

> "1. `llm_emit_directive_bound:` count ≥ 4 (per Ship A gate criteria, v3 §4.7 \"≥3 LLM-emitted resolutions across a session, mixed pass/fail\")"

Replace with:

> "1. `llm_emit_directive_bound:` count ≥ 3 (per Ship A gate criteria, v3 §4.7)"

The bump from 3 → 4 in the spec draft was unintentional; align to v3 §4.7's locked threshold.

### §4.6 Revision to §11.B.6 housekeeping framing

Current text in §11.B.6 surfaced addition:

> "v1.x housekeeping ticket — move `RESOLUTION_BINDING_SPEC.md` + `BUG_1_SPEC.md` from flat to specs/ for convention consistency. Not Ship A's job."

Replace with:

> "v1.x housekeeping candidate (low priority): move `RESOLUTION_BINDING_SPEC.md` + `BUG_1_SPEC.md` from flat `/home/jordaneal/virgil-docs/` to `/home/jordaneal/virgil-docs/specs/` per dominant convention. **Defer indefinitely** unless a future ship requires consistent spec path discovery (e.g., a `/spec-load` slash command or a doc-search tool that assumes specs/ as root). Cosmetic-only; not a v1.x ticket worth scheduling."

---

## §5. Doctrine candidates filed (do NOT anchor mid-flight)

Per Doctrine §59 + locked decision 11, candidates surface during ship work but anchor only after the proving ship lands cleanly.

### §5.1 C1 — Engine-computed binding > validator-on-LLM-output (third instance pending)

**Pre-locked per decision 11.** Wait for Ship A verify to confirm the shape holds. If post-verify the three instances (Track 7 #1 + Ship 1 + Ship A) all hold cleanly, C1 promotes from candidate to numbered §-entry (likely §77).

**Planner review:** Confirm timing. No change.

### §5.2 C2 — Reused vocabulary across sibling verifier classes (stays at one instance)

Ship A doesn't add new verifier classes — only constraint clauses in the AUTHORITATIVE-CANON block. C2 unchanged at one instance.

**Planner review:** Confirm. No change.

### §5.3 New candidate (review framing) — §17-amendment, not new sibling

Spec §16.3 files a new candidate "Single-writer compatible with multiple trigger surfaces" with one instance. Review observation: this candidate is closely adjacent to existing Doctrine §17 (single write paths per field). The candidate's content is essentially a refinement/clarification of §17 — "single writer at the helper layer is compatible with multiple trigger surfaces" — rather than a new sibling principle.

**Planner recommendation:** **Reframe as §17-amendment candidate, not new sibling doctrine.** When Ship A lands cleanly + a second instance surfaces (likely F-55 #5.4 or Ship 2's writer consolidation), the amendment lands as a §17 refinement clause rather than §77b or similar.

**Revision request to Code:** Update spec §16.3 from "new doctrine candidate" framing to "§17 amendment candidate." Same content; different doctrinal status.

This is the seventh review revision but it's optional — the candidate disposition is internal to doctrine-housekeeping and doesn't affect Ship A's implementation. If Code prefers to keep §16.3 as-written, the candidate-vs-amendment distinction can wait for actual second instance.

**Lock outcome:** Confirm at Code's discretion. Recommended reframe but not required for spec LOCKED status. **NOT counted among the six required revisions in §4 above.**

---

## §6. Implementation handoff to S36

After Code applies the six §4 revisions and the spec flips to LOCKED, implementation begins in S36 per the cadence in `WORKING_WITH_CLAUDE.md` and `MULTIPLAYER_FIXES.md` v3 §11.

| Field | Value |
|---|---|
| **Implementation session** | S36 |
| **Model** | Opus high per v3 §4.6 (load-bearing primary-surface ship; primitives will echo into F-55 #5.4) |
| **Files touched** | `dnd_orchestration.py` (~250 LOC: ResolutionTexture + compute_stakes_tier + compute_resolution_texture + render extensions + RollDecision DC placeholder), `discord_dnd_bot.py` (~80 LOC: writer hook + parser regex + wrong-skill aside + matcher branch flip), `dnd_engine.py` (~5 LOC: HARD STOP RULE 1 extension) |
| **Test target** | ~33 new assertions across 2 new + 3 extended files per spec §14 |
| **Live-verify scenarios** | 8 (A1, A2, B, C, D-deferred, E, F-regression, plus §15.10 Ship 4.5 calibration) per spec §15 |
| **Promotion criteria** | Per spec §15.9 aggregate criteria — ≥3 LLM-emit resolutions (mixed pass/fail), zero unretried drift, zero unexpected co-occurrence, zero auto-fire failures, ≥1 wrong-skill aside if Scenario C walked, observable stakes_tier distribution across low/medium/high cells |
| **Doc-update pass** | After live-verify clean (S36+): ROADMAP.md (flip Ship A row to ✅), SESSIONS.md (S36 entry), DOCTRINE.md (C1 promotion if three-instance criterion holds — apply per decision 11 outcome), tests-to-run-post-session.md (Scenarios A1–F appended), MULTIPLAYER_FIXES.md (flip Ship A §4 row to ✅) |
| **Pre-promotion verify** | None — recon already cleared (Avrae A.2 form (a) clean per S34 #2). Multi-word skill compat is the only soft recon item; full live test deferred to S36 implementation phase (low risk per spec §11.B.3 confidence). |

---

## §7. Architectural shape — locked, no changes

Per S34 #2 lock + this review pass:

1. Ship A is **additive on Ship 1** — every primitive Ship 1 introduced is reused unchanged or extended additively.
2. **§17 single-writer status preserved** via consolidation at the `pending_directive_upsert` helper layer. Two disjoint trigger surfaces (DM-typed via `_handle_dm_roll_directive`, LLM-emitted via `_dm_respond_and_post` hook) both call the same helper.
3. **Two-embed UX** per locked decision A.8. No orchestration shift.
4. **TTL=300s** unchanged. Phantom-binding risk requires three-condition compound; rare in natural play.
5. **Cast resolution stays v1.x** (inherited from Ship 1 §11.5).
6. **Player-typed `!check` stays out of scope** (inherited from Ship 1 §15.2).
7. **Combat-mode rolls stay out of scope** (inherited Ship 1 §15.3, BUG_1_SPEC.md §F.1 gate 2).

All seven invariants confirmed at review.

---

## §8. Confidence summary

| Decision area | Spec confidence | Review confidence | Notes |
|---|---|---|---|
| Architectural shape (locked elements §2) | HIGH | HIGH | Additive on shipped Ship 1; recon cleared |
| ResolutionTexture dataclass shape (§4) | HIGH | HIGH (after revision §4.1) | Frozen + default-None compatible; immutability clarification needed |
| compute_stakes_tier scoring (§5) | MEDIUM-HIGH | MEDIUM-HIGH (after revision §4.3) | Five-axis scoring locked; commitment-axis simplification needed |
| Writer hook insertion + parser (§6, §7) | HIGH | HIGH | Recon-confirmed insertion point; last-match parser cleanly handles edge cases |
| Difficulty/margin/crit bands (§8, §9, §10) | MEDIUM-HIGH | MEDIUM-HIGH | Phrasing v1, tunable at verify per locked decision 10 |
| Wrong-skill aside (§13) | HIGH | HIGH | Cleanly mirrors Ship 1's wrong-actor aside |
| Test plan (§14) | HIGH | HIGH | ~33 assertions covering all surfaces |
| Live-verify scenarios (§15) | HIGH | HIGH | 8 scenarios; nat-tier and high-stakes deferred to natural play |
| Doctrine candidates (§16) | LOW-MEDIUM | MEDIUM | C1 pending; §16.3 framing reconsidered (recommended §17-amendment) |

Overall: **Spec is implementation-ready after the six §4 revisions land.** No architectural reservation; pure framing/wording tightening.

---

*End of review v1. Session 35b.*

---

## Tabular handoff

| Field | Value |
|---|---|
| **File written** | `/home/jordaneal/virgil-docs/specs/LLM_EMIT_RESOLUTION_BINDING_REVIEW.md` |
| **Status** | REVIEW v1 — six revisions surfaced; spec flips DRAFT → LOCKED after Code applies them |
| **Decisions reviewed** | 18 (12 pre-locked from v3 §12, 6 surfaced in spec §11.B.1–B.6) |
| **Decisions confirmed at Code's recommendation** | 16 |
| **Decisions confirmed with revision request** | 2 (§11.B.2 texture-computation framing, §11.B.6 housekeeping framing) — both line-level wording |
| **Decisions pushed back** | 0 |
| **Architectural changes** | None |
| **Spec revisions to apply** | 6 (§4.1–§4.6) — all framing/wording, no section rewrites |
| **Optional revision** | 1 (§5.3 — §16.3 candidate-vs-amendment framing). Not required for LOCKED. |
| **Doctrine candidates filed (not anchored)** | C1 pending Ship A verify per decision 11. C2 stays at one instance. C3 (single-writer-multiple-triggers) reframed as §17-amendment candidate. |
| **Ready-for-implementation status** | Yes, after Code applies the six §4 revisions |
| **Implementation session** | S36, Opus high |
| **Companion spec status** | DRAFT → LOCKED after revisions applied |
