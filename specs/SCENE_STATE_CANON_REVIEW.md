# Ship 2 — Scene State Canon Discipline — Design Review v1

**Status:** REVIEW v1 — S38. Companion to `SCENE_STATE_CANON_SPEC.md` v1 (DRAFT, S37). Walks each §11 decision with planner-side trade-offs, lock confirmation or pushback, and surfaced additions. Output of this doc is the lock pass — `SPEC.md` updates from DRAFT to LOCKED after Code reads this review and applies the surfaced revisions.

**Pattern:** Standard spec-then-review-then-implement cadence per `WORKING_WITH_CLAUDE.md`. Spec drafts in S37; review locks in S38; implementation follows in S39.

**Track:** Multiplayer Fixes — Ship 2. Closes Finding A. Anchors candidate Doctrine §76 when Ship 2 ships.

---

## Review summary

| Field | Value |
|-------|-------|
| **Decisions reviewed** | 4 (§11.D1–D4 in spec) + 1 surfaced (D5 — four-property regression scope) = **5 total** |
| **Decisions locked at Code's recommendation** | 4 (D1, D2, D3, D4) |
| **Decisions locked with revision request** | 0 (no framing pushback on D1–D4) |
| **Decisions pushed back** | 0 |
| **New decisions surfaced by review** | 1 (D5 — four-property regression test scope: per-table vs. general-discipline) |
| **HALT escalations** | 0 |
| **Architectural shape changes** | 0 — locked shape from MULTIPLAYER_FIXES.md v3 §5 holds |
| **Implementation-note refinements** | 3 (last_scene_change reader chain, init_scene_state seed param dead-code, live-verify discipline on fresh vs long-running campaigns) |
| **Doctrine candidate review** | §76 phrasing is table-agnostic in spec §3.1 — confirmed correct. No revision. |
| **Hybrid Combat Notes v3 / Playtest Framework consistency check** | Clean — Ship 2's audit framework extends to Ship 3 surfaces; §76 doctrine carries forward; PLAYTEST_FRAMEWORK §3.2 NPC continuity will inherit from Ship 2's discipline. |
| **Ready-for-implementation status** | Yes, after Code applies the 3 implementation-note refinements + adds D5 to §11 |
| **Implementation session** | S39 |

---

## §1. How to read this review

For each §11 decision in `SCENE_STATE_CANON_SPEC.md`, this doc records:

1. **The question** (one-line restatement)
2. **Code's lock recommendation** (verbatim from spec)
3. **Planner review** — confirm, push back, or revise
4. **Lock outcome** — what stands after Code applies any revisions

Where the spec missed a load-bearing decision, the review surfaces it as a new §11.D5 candidate. Where the spec missed an implementation-relevant detail, it surfaces as a refinement requested in §4 (revisions to apply).

Per the review prompt, the review also checks downstream-consequence concerns from `HYBRID_COMBAT_NOTES.md` v3 and `PLAYTEST_OBSERVATION_FRAMEWORK.md` — these surface in §3 (cross-doc consistency).

---

## §2. Decision walks

### §2.1 Decision D1 — Path for 2a location-column treatment

**Question:** Drop the freetext `location` column entirely (Path A) or keep it and extend `set_current_location` to write it from the FK (Path B)?

**Code's lock:** Path A (drop column). Reads migrate to JOIN on `dnd_locations.canonical_name` via `current_location_id`. Doctrinally cleaner per §76; removes future regression surface (§75 pattern — no risk of column re-admission to SCALAR_FIELDS).

**Planner review:** **Confirm. Path A.**

The data-preservation argument has no value here — the freetext field's content is by definition the contamination loop's substrate. Schema cleanliness wins.

The "wilderness / between locations" use case (which might argue for keeping a freetext column to carry a non-canonical descriptive label) is correctly handled by Path A's NULL-FK rendering ("between locations" / deliberate ambiguity). The legitimate canon for non-FK'd locations is to extend `dnd_locations` with non-skeleton entries (parser-promoted or operator-curated), not to keep a parallel freetext field.

Path B's "lower migration risk" argument is weak — a single ALTER DROP statement (or table-rebuild fallback for older SQLite) is roughly equivalent in implementation cost to extending `set_current_location` to write a derived field. Both are well-bounded edits.

The §75 pattern concern (silent regression on migrated schemas) is the controlling argument: Path B keeps a field that could later be re-admitted to SCALAR_FIELDS by mistake. Path A removes the surface entirely.

**Sub-decision: rename derived field from `location` to `location_label`.** Confirm. Grep-distinct naming is low-cost cosmetic; eliminates accidental conflation with the deleted column in future patches.

**Confidence:** HIGH. Same as spec's recommendation.

**Lock outcome:** Path A (drop freetext column). Read sites migrate to JOIN-derived `location_label`. No revision to spec body.

---

### §2.2 Decision D2 — Scope of 2c deletions: ship in v1 or defer

**Question:** The 2c audit surfaced THREE additional 4/4 hits beyond `established_details`: `focus`, `open_questions`, `last_scene_change`. Ship all in v1, ship some, or defer all to filed candidates?

**Code's lock:** D2-all (ship all five deletions in v1: `location` LLM-write, `established_details`, `focus`, `open_questions`, `last_scene_change`). Structurally consistent with §76; the deletions are mechanically identical (same migration shape, same write-path neutralization, same readback removal).

**Planner review:** **Confirm. D2-all + surfaced implementation refinements.**

The "compounding risk vs serial deletion" framing in the question deserves an answer: there is no compounding failure mode. The five deletions are independent — each affects a distinct field with a distinct readback site. A failure in (say) the `focus` deletion does not couple to a failure in `last_scene_change` deletion. The implementation can verify each deletion independently. Bundling does NOT introduce cross-field coupling.

The "any of these load-bearing for any current ship?" question was the load-bearing check. Review confirms:
- **`focus`**: read only at `build_dm_context` line 5204. Not consumed by adjudicator, commitment directive, pacing directive, or any other ship. Safe to delete.
- **`open_questions`**: read only at `build_dm_context` line 5208. Not consumed elsewhere. Safe to delete.
- **`last_scene_change`**: read at `build_dm_context` line 5210, also written by `extract_scene_updates` line 4810-4811 AND **seeded by `init_scene_state` line 1181**. The seed flow needs explicit attention — see refinement below.

**Surfaced implementation refinement 1 (REQUEST):** The spec should explicitly address the `last_scene_change` seed dead-code chain in §4.3 or §7.

Recon trace:
- `init_scene_state(campaign_id, seed: str = '')` writes `seed[:500]` into `dnd_scene_state.last_scene_change` at INSERT path (line 1177) and at ON CONFLICT path it preserves `last_scene_change` (line 1179).
- Callers: `discord_dnd_bot.py:3805` (`/play` command — passes a captured seed string) and `dnd_engine.py:4709` (`update_scene_state`'s init-if-missing branch — passes `seed=''`).
- Post-Ship-2 (with `last_scene_change` deleted), the seed parameter has no landing surface.

**Spec revision request:** Add a §4.3 (Ship 2b) or §7 (Migration path) note that `init_scene_state`'s `seed` parameter must be dropped or converted to a deprecation no-op alongside the `last_scene_change` deletion. The `/play` flow in `discord_dnd_bot.py:3805` must be updated to stop passing the seed. Recommend drop (clean signature); the seed was the legacy entry point into a now-deleted field.

**Sub-decision check on `focus`:** `Focus:` rendering at line 5204 is currently used by the LLM as a scene-attention anchor ("what is the party paying attention to right now"). Post-deletion, the LLM relies on `last_dm_response` and the player's recent action (in the chat context window). The review's read on this: `focus` was a per-turn LLM self-summary, exactly the §76 contamination shape. The replacement (recent narration + player action) is structurally cleaner. Operator may notice a narrative-coherence shift during live-verify; if so, the regression spec'd in §11.D2 (reversibility: re-introduce via ALTER ADD with deterministic single-writer) applies. Reversal does NOT restore LLM-write authority.

**Confidence:** MEDIUM-HIGH. The recommendation is correct under §76 doctrine. The MEDIUM-HIGH (vs HIGH) is because operator's live-verify may surface a "narrative coherence" regression on `focus` deletion specifically — `last_scene_change` and `open_questions` are clearly elaboration-only, but `focus` walked a line as scene-anchor. If a regression surfaces, the reversal path is well-defined (gated-write helper).

**Lock outcome:** D2-all (ship all five deletions). Refinement: explicitly address `init_scene_state.seed` parameter chain (drop or convert to no-op) and `/play` seed-passing flow at `discord_dnd_bot.py:3805` in spec §4.3 or §7.

---

### §2.3 Decision D3 — Adjacent-table audit boundary

**Question:** Should the 2c audit pass include `dnd_npcs.description`, `dnd_npcs.origin_excerpt`, `dnd_locations.description`, `dnd_locations.origin_excerpt` in this ship, or defer to future filed candidates?

**Code's lock:** D3-defer (adjacent tables OUT of Ship 2 scope). The fields go through gated upsert helpers with skeleton_origin protection; they're NOT pulled into the SCENE STATE block; chroma-mediated retrieval is the indirect path.

**Planner review:** **Confirm. D3-defer.**

The locked architectural shape per `MULTIPLAYER_FIXES.md` v3 §5 scopes Ship 2 to scene_state-table surfaces. The audit boundary aligns with that scope.

The "borderline column warrants inclusion now while audit context is fresh" pushback the review prompt invited has a real edge — chroma-mediated retrieval of `description` / `origin_excerpt` content IS structurally similar to S22 #2's chroma contamination instance (the first project instance of §76). But:

1. The chroma path is a **fundamentally different surface** from scalar lookup. Vector retrieval works on similarity, not on column-fetch — the four-property test applies to scalar columns; chroma needs its own audit framework.
2. The chroma-layer audit is already filed as a candidate at spec §13 item 3. Expanding Ship 2 to include the chroma path would double the ship's scope without clear architectural payoff.
3. The npc/location description fields have **gated upsert helpers** (`npc_upsert`, `location_upsert`) with **skeleton_origin protection** — they are NOT raw LLM-write surfaces. Property 1 (LLM-writable) is only partially hit. The audit framework's strongest application is to fields where ALL FOUR properties hit cleanly; partial-hits are weaker deletion candidates.

The boundary is defensible. Filed candidate status preserves the option to audit later if drift evidence accrues against the adjacent tables specifically.

**Surfaced consideration (not a revision request):** When Ship 3 (NPC State-Sync Boundary) specs, it should re-evaluate `dnd_npcs.description` and `dnd_npcs.origin_excerpt` against the four-property test as Ship 3's natural in-scope work. The §76 doctrine should be inherited by Ship 3 explicitly. See §3 below.

**Confidence:** HIGH. Same as spec's recommendation.

**Lock outcome:** D3-defer. Adjacent tables filed as candidates per spec §6.3 + §13 item 2/3. No revision.

---

### §2.4 Decision D4 — Dead-column housekeeping bundling

**Question:** Ship the dead-column drops (`active_npcs`, `active_threats`, `tension` legacy) bundled with Ship 2, or file separately?

**Code's lock:** D4-bundle (low marginal cost; same migration shape).

**Planner review:** **Confirm. D4-bundle + surfaced implementation refinement.**

The "could the dead-column drops surface unexpected break if a stale code path is still touching them somewhere not yet grepped?" question was the load-bearing check. Review performed the grep pre-emptively:

**Grep results for `active_npcs`:**
- `dnd_engine.py:331,1128,1146,1174` — schema + get/init paths (will need column-list updates alongside drop).
- `dnd_engine.py:4695,4702,4754` — comments + LOCKED_FIELDS guard (will be obsolete post-drop).
- `dnd_engine.py:5182-5184` — comments documenting that the field is unused at render time.
- **No active readers**; the `get_recently_active_npcs(...)` render path at line 5191 explicitly replaces this field.

**Grep results for `active_threats`:**
- `dnd_engine.py:332,1129,1147,1175` — schema + get/init paths.
- `dnd_engine.py:4695,4702,4754` — comments + LOCKED_FIELDS.
- `dnd_engine.py:5185` — comment "active_threats prompt block dropped — schema column kept; defer until threat model exists."
- **No active readers.**

**Grep results for `'tension'` (legacy string field, NOT `tension_int`):**
- `dnd_engine.py:334,1129,1149,1175` — schema + get/init paths.
- `dnd_engine.py:4695,4702` — LOCKED_FIELDS guard.
- `dnd_orchestration.py:3281,3308,3361` — **unrelated local variable** in a different code path (signals/scoring inside an orchestration function); does NOT read from `dnd_scene_state.tension`. Safe.
- **No active readers** of `dnd_scene_state.tension` (the legacy string). All tension-related render paths use `tension_int` (line 5205).

Grep is clean. Bundling is safe.

**Surfaced implementation refinement 2 (NOT a request for spec body change, but a pre-implementation discipline note):** Before issuing the DROP statements at S39 implementation, run the same grep on each column name to confirm no patches landed between S38 and S39 that introduced a new touch. This is general migration discipline (§75 pattern hygiene), not a Ship-2-specific concern, but worth calling out explicitly given that S38–S39 may be the longest single-spec stretch in the multiplayer-fixes plan.

**Confidence:** MEDIUM-HIGH (upgraded from spec's MEDIUM after grep confirms zero stale code paths). The "scope creep" pushback option is weak — the dead-column drops share migration mechanics with the §76 deletions; doing them in the same block is marginal cost. The "doctrinal purity" pushback (Ship 2 should be only-§76-application) is cosmetic; both options ship the same deletions.

**Lock outcome:** D4-bundle. No spec revision. Implementation discipline note: re-grep dead column names at S39 commit time.

---

### §2.5 Decision D5 (surfaced by review) — Four-property regression test scope

**Question:** Should the four-property regression test (spec §8.1, `test_doctrine_76_four_property_audit.py`) be scoped to `dnd_scene_state` only, or generalize to ALL persisted scalar columns across ALL tables in the codebase?

**Why this surfaces:** The review's check against `PLAYTEST_OBSERVATION_FRAMEWORK.md` §3.2 (NPC continuity) and `HYBRID_COMBAT_NOTES.md` v3 §3 (foundation for future motion-systems work) raises the question: when the next persisted state surface gets added (Ship 3's NPC state work, future scene-lifecycle work, etc.), does it automatically run through the four-property test, or does each new surface need to be re-audited manually at add-time?

The spec's regression test is currently scoped to `dnd_scene_state` — a future schema addition to, say, `dnd_npc_relationships` (hypothetical Ship 3 surface) would NOT be caught by the regression test if it introduced a 4/4 column. The test passes; the new column persists; the loop has a fresh contamination surface.

**Options:**
- **D5-scoped**: Keep regression test scoped to `dnd_scene_state`. Each future ship that adds a persisted scalar surface adds its own table-scoped regression test (matching pattern). §76 doctrine's anchored entry calls out this discipline.
- **D5-general**: Generalize regression test to enumerate ALL persisted scalar columns across ALL tables. Significantly more code (must enumerate writers, readers, narrative-inferential property per column) but catches schema additions automatically.

**Trade-offs:**

| Concern | D5-scoped | D5-general |
|---|---|---|
| Implementation cost | Low (table-scoped enumeration) | High (cross-table audit infrastructure) |
| Catches future schema additions | Only if matching test added per ship | Automatic |
| False positive rate | Low (narrow scope) | Higher (must classify "narratively inferential" across many fields) |
| Maintenance cost | Per-ship-table addition | Centralized; updates when audit logic itself changes |
| Doctrinal cleanliness | Each ship owns its own table's discipline | Centralized discipline enforcement |

**Recommended default:** **D5-scoped.**

**Confidence:** MEDIUM.

**Trade-offs explanation:**
- D5-scoped is the lower-cost path and matches Ship 2's actual deliverable (audit pass on `dnd_scene_state`).
- D5-general would require the audit logic itself to classify "narratively inferential" via heuristics (impossible to fully automate) — each new table's classification still needs human review at add time.
- The §76 doctrine's anchored entry (after Ship 2 ships) is the discipline-level enforcement: it specifies that **every new persisted scalar column undergoes a manual four-property check at add time**. The per-table regression test is the post-classification guard.
- Ship 3 inherits this discipline by adding its own table-scoped regression test, structured identically to Ship 2's.

**Alternative framing:** If operator wants centralization, D5-general can ship as a v1.x candidate after Ship 2 + Ship 3 produce two table-scoped regression tests with parallel structure (proof of pattern). The generalization earns its keep once the pattern is repeated.

**Lock outcome:** Surface as **NEW §11.D5** in spec §11. Recommend D5-scoped default with v1.x candidate for D5-general after Ship 3 ships. Spec revision request: add D5 to §11 (see §4 below).

---

## §3. Cross-doc consistency check (HYBRID_COMBAT_NOTES.md v3 + PLAYTEST_OBSERVATION_FRAMEWORK.md)

The review prompt requested three downstream-consequence checks. Each is reported below.

### §3.1 Does the four-property test extend to future state surfaces?

**Check:** The test's operational definition in spec §3.1 is table-agnostic ("a persisted scalar field is a latent-canon contamination surface iff..."). However, the regression test in §8.1 is `dnd_scene_state`-scoped.

**Finding:** The DOCTRINE phrasing is already correct for cross-surface inheritance. The regression test scope is a separate question — surfaced as D5 above.

**Recommendation:** When §76 anchors as a numbered DOCTRINE entry (after Ship 2 ships), the entry's phrasing should explicitly include a discipline statement like: *"Applied at every new persisted scalar column at add time. Each table that gains LLM-writable scalar fields adds its own four-property regression test in a parallel pattern."* This makes the doctrine carry forward to Ship 3 + future ships without re-derivation.

**Result:** Clean. No spec revision required. The doctrine carries forward; D5 above addresses the regression test scope question.

### §3.2 Does Ship 2's verify produce signal usable by PLAYTEST_OBSERVATION_FRAMEWORK §3.1 / §3.2?

**Check:** The framework's §3.1 (cross-session causality echoes) and §3.2 (NPC continuity) measure whether the world remembers across sessions. Ship 2 closes scene_state canon discipline; Ship 3 closes NPC state-sync; the two together establish the substrate that §3.1/§3.2 measure.

**Finding:** Ship 2 alone produces partial signal:
- **§3.1 cross-session causality** depends primarily on Ship 3 (NPC state) + future motion-systems work, NOT Ship 2 directly. Ship 2's contribution is to ensure that scene-state continuity (location, mode, day_phase) is engine-bound rather than LLM-laundered — a precondition for cross-session causality being measurable cleanly, but not the load-bearing surface.
- **§3.2 NPC continuity** is mostly Ship 3 territory. Ship 2 contributes the doctrinal foundation (four-property test); Ship 3 applies it to NPC fields.

**Live-verify scenario implication:** The spec's §9 scenarios (A–F) test scene_state-side closures specifically. They do NOT need to also test cross-session NPC continuity (that's Ship 3 + playtest territory). The spec's scoping is correct.

**Surfaced implementation refinement 3 (REQUEST):** §9 Scenario C live-verify discipline.

The scenario tests "Cross-turn drift resistance (combined 2a+2b)" with 5 turns of play. The expected result is "drift detection: grep narration across the 5 turns for cave-imagery / contradictory-location phrases. None expected."

This works on a **fresh campaign**. On a **long-running campaign** with pre-Ship-2 contaminated narration already chroma-indexed, the chroma retrieval at each turn could surface contaminated prior narration as context — producing false-positive drift indications that come from chroma, not from scene_state.

**Spec revision request:** Add to §9 Scenario C a discipline note: *"Test against a fresh campaign (no prior Ship-2-era narration). On long-running campaigns, residual chroma contamination from pre-Ship-2 LLM writes may produce false-positive drift signals via chroma retrieval — this is the F-40-pattern artifact and is closed only by chroma layer audit (filed candidate per §13 item 3). Ship 2's structural closure is verified on fresh campaigns."*

**Result:** Refinement applied; otherwise consistency is clean.

### §3.3 Does §76 carry forward cleanly to Ship 3?

**Check:** Ship 3 (NPC State-Sync Boundary) will likely surface a fourth instance of §76 (NPC state fields hitting the four-property test). Does Ship 2's §76 phrasing need refinement to cover NPC state alongside scene state?

**Finding:** The spec's §3.1 phrasing ("a persisted scalar field") is generic across tables. Ship 3 can apply the test to `dnd_npcs` columns without re-deriving the doctrine.

**Surfaced consideration (NOT a revision request):** Ship 3's spec will likely add a fourth project instance to the §76 candidate's instance roster (currently 3 instances: S22 #2 / S32 / S36). After Ship 3 ships, §76 has 4 instances and is well past the anchoring threshold. The anchoring event remains "Ship 2 ships and live-verify clean" per spec §3.4 — Ship 3 then strengthens the entry, doesn't change the anchoring criterion.

**Result:** Clean. §76 doctrine is table-agnostic in its current phrasing; Ship 3 inherits without modification. No revision required.

### §3.4 HYBRID_COMBAT_NOTES.md v3 specific cross-checks

The review prompt called out two specific v3 points:
- **v3 reinforces Ship 2's canon discipline as doctrinal foundation for future motion-systems work.** Confirmed in v3 §6 ("the LLM doesn't invent the world; deterministic systems generate the world, LLM renders what the world currently is" — Ship 2 is partially this shape). No spec changes needed; the framing already aligns.
- **v3's Ship 4/5 MVP-test scrutiny flagging means Ship 2 has heavier downstream consequence.** Confirmed: if Ship 4 (Scene-Scope-First Identity) ends up shipping under MVP-test scrutiny, it will need to apply the four-property test to its own surfaces (likely `dnd_npcs` again, scoped to scene-level retention). If Ship 4 defers per v3 §8 question 3, the four-property test still travels with whatever ships next.

**Result:** Clean. Ship 2's framework absorbs the v3 reframing without modification.

---

## §4. Spec revisions to apply before LOCKED status

Code applies the following revisions before flipping `SCENE_STATE_CANON_SPEC.md` from DRAFT to LOCKED:

### §4.1 Implementation refinement 1 — `init_scene_state.seed` parameter cleanup (D2 implementation note)

Add to spec **§4.3 (Implementation surface — Ship 2b)** or **§7 (Migration path — Code removals subsection)**:

> **`init_scene_state.seed` parameter dead-code chain (post-last_scene_change deletion).** The `init_scene_state(campaign_id, seed: str = '')` signature seeds `seed[:500]` into `dnd_scene_state.last_scene_change` at INSERT path (dnd_engine.py:1177) and preserves it at ON CONFLICT (line 1179). Post-deletion, the seed has no landing surface. Callers: `discord_dnd_bot.py:3805` (`/play` command — passes captured seed string) and `dnd_engine.py:4709` (`update_scene_state`'s init-if-missing branch — passes `seed=''`). Implementation drops the `seed` parameter from `init_scene_state` entirely; `/play` flow stops capturing/passing the seed. Updates the function signature to `init_scene_state(campaign_id: int) -> None`.

### §4.2 Implementation refinement 2 — `last_scene_change` reader audit confirmation (D2 implementation note)

Add to spec **§5.1 (Current state — established_details readers)** OR **§4.1 (Current state — location readers)** parallel section for `last_scene_change`:

Recon-confirmed reader enumeration for `last_scene_change`:
- `get_scene_state` line 1130 (SELECT) + line 1153 (dict assignment).
- `init_scene_state` line 1169, 1176, 1179 (seed→last_scene_change write path + ON CONFLICT preservation).
- `build_dm_context` line 5210 (renders `Last scene change: ...` in SCENE STATE block).
- Prompt-size telemetry line 6075 (char counting).
- `extract_scene_updates` line 4810-4811 (LLM-write target).

**No other readers.** Deletion is structurally clean. (Spec body can either include this enumeration directly or reference this review §4.2 as authoritative.)

### §4.3 Implementation refinement 3 — Live-verify discipline on fresh vs long-running campaigns

Add to spec **§9 Scenario C** as a discipline note:

> **Test discipline:** Run Scenario C against a **fresh campaign** (no prior Ship-2-era narration). On long-running campaigns, residual chroma contamination from pre-Ship-2 LLM writes may produce false-positive drift signals via chroma retrieval — this is the F-40-pattern artifact and is closed only by chroma layer audit (filed candidate per §13 item 3). Ship 2's structural closure is verified on fresh campaigns; long-running campaign verification waits on the chroma-layer audit ship.

### §4.4 New decision D5 added to §11

Add **§11.D5** to the spec, capturing the four-property regression test scope question per §2.5 of this review. Verbatim from review §2.5 (question / options / trade-offs / recommended default / confidence / lock outcome).

All four revisions are framing/scope refinements — they preserve every architectural lock in D1-D4 and only sharpen implementation discipline + surface the additional D5 decision. Spec status flips DRAFT → LOCKED after revisions land.

---

## §5. Doctrine candidate review

The spec files §76 as a candidate in DOCTRINE.md Candidates section per spec §3.4. The review confirms:

- **§76 phrasing** (spec §3.1) is table-agnostic. Ship 3 inherits without re-derivation. ✅
- **Three project instances** (spec §3.2) are correctly identified and sequenced. The S22 #2 / S32 / S36 roster is the anchoring evidence. ✅
- **Anchoring criterion** (spec §3.4) — Ship 2 ships + live-verify clean. ✅
- **Sibling principles** (spec §3.3) — §17, §1a, MULTIPLAYER_FIXES §2.3, §70. Cross-references are correct. ✅

**No revision to §76 candidate phrasing.** When the candidate anchors as a numbered DOCTRINE.md entry post-Ship-2 live-verify clean, the entry's text in spec §3.1 carries forward verbatim. The "applied at every new persisted scalar column at add time" discipline statement (per §3.1 above in this review) is an addendum the anchoring doc-update pass adds.

**No new candidates filed by review.** Ship 2 is a §76 application; no novel architectural pattern surfaces here that earns its own candidate slot.

---

## §6. Implementation handoff to S39

After Code applies the four §4 revisions and the spec flips to LOCKED, implementation begins in S39 per the cadence in `WORKING_WITH_CLAUDE.md`.

| Field | Value |
|-------|-------|
| **Implementation session** | S39 |
| **Model** | Opus (load-bearing structural deletion; §76 anchoring event) |
| **Files touched (primary)** | `dnd_engine.py` (schema migration block + get_scene_state + init_scene_state + update_scene_state + extract_scene_updates + build_dm_context + prompt-size telemetry), `discord_dnd_bot.py` (`/play` flow seed-passing removal) |
| **Files touched (tests)** | `test_commitment_directive.py`, `test_time_skeleton_seed.py`, `test_prompt_size.py` (fixture column-list updates), new tests: `test_scene_state_canon_deletion.py`, `test_extract_scene_updates_canon_deletion.py`, `test_doctrine_76_four_property_audit.py` |
| **Migration shape** | ALTER TABLE DROP COLUMN (SQLite 3.35+) or table-rebuild fallback per spec §7.1. Idempotent (PRAGMA-gated). |
| **Test target** | ~30 assertions across 3 new + 3 extended files |
| **Live-verify scenarios** | 6 (A–F) per spec §9, with fresh-campaign discipline note from §4.3 above |
| **Promotion criteria** | Per spec §9 (all six scenarios pass) + Doctrine §76 candidate anchors to numbered §-entry on live-verify clean |
| **Doc-update pass post-ship** | ROADMAP.md (Ship 2 ✅, multiplayer fixes plan §5 promoted), SESSIONS.md (S37 + S38 + S39 entries), DOCTRINE.md (§76 anchored from candidate → numbered + add C1 ↔ §76 cross-reference), MULTIPLAYER_FIXES.md (§5 row → ✅ SHIPPED LIVE), tests-to-run-post-session.md (Scenarios A–F appended), project_ship2_drift_evidence.md memory (mark closure or convert to historical reference) |

---

## Tabular handoff

| Field | Value |
|-------|-------|
| **File written** | `/home/jordaneal/virgil-docs/specs/SCENE_STATE_CANON_REVIEW.md` |
| **Status** | REVIEW v1 — locks applied; spec flips to LOCKED after Code applies the four §4 revisions |
| **Decisions reviewed** | 5 (4 from spec §11 + 1 surfaced) |
| **Decisions confirmed at Code's recommendation** | 4 (D1, D2, D3, D4 — all architectural locks confirmed) |
| **Decisions confirmed with revision request** | 0 (no architectural pushback) |
| **New decisions surfaced** | 1 (D5 — four-property regression test scope) |
| **Decisions pushed back** | 0 |
| **HALT escalations** | 0 |
| **Architectural changes** | None |
| **Spec revisions to apply** | 4 (§4.1 seed parameter chain; §4.2 last_scene_change reader audit confirmation; §4.3 live-verify fresh-campaign discipline note; §4.4 new D5 added to §11) |
| **Doctrine candidate review** | §76 phrasing confirmed table-agnostic; no candidate-text revision |
| **Cross-doc consistency** | Clean against HYBRID_COMBAT_NOTES v3 + PLAYTEST_OBSERVATION_FRAMEWORK; surfaced refinements absorbed in §4 |
| **Ready-for-implementation status** | Yes, after Code applies the four §4 revisions |
| **Implementation session** | S39 |
| **Companion spec status** | DRAFT → LOCKED after revisions applied |

---

*End of review v1. Session 38.*
