# corpus_builder lessons doc v2 — pending candidates

**Status:** Pending. These are confirmed lessons from Track 5 Ship 2 (Time-Mention) awaiting cross-extractor confirmation at Ship 3 (Loot/Reward) before promotion into `corpus_builder_lessons_v1.md` v2.

The pattern is intentional: Lessons 1–8 in v1 were each surfaced by Ship 1 (Encounter Cadence) and validated at v1's writing time. Lessons 9–11 below were surfaced and validated at Ship 2; they recur as candidates here, then get promoted into v2 of the lessons doc once Ship 3 either confirms or contradicts them. Ship 3 may also surface its own Lesson-12+ candidates which will be added to this file.

For the durable v1 lessons in current effect, see `corpus_builder_lessons_v1.md`. For the detailed history of how each candidate below surfaced, see `findings/time_mention_session_log.md`.

---

## Lesson 9 (candidate) — phrase-span vs turn-level Stage 0

**Surfaced:** Phase 2 hand-sample, when D6 (NPC-dialogue reject) precision came in below 85% and the spec's OQ1 fallback demoted D6 from a turn-level reject to a phrase-level flag (`is_npc_dialogue_present`).

**Confirmed:** Phase 3 v1.2 calibration. Patch 2 (NPC-phrase routing to UNKNOWN_SHAPE) replaced the demoted D6 flag with a phrase-span-aware Stage 0 layer: quote-mark count + same-sentence NPC voicing tag, and the *phrase* gets routed to UNKNOWN_SHAPE rather than the *turn* getting rejected. This worked as designed across the calibration set.

**The lesson.** Encounter Cadence's Stage 0 ran at turn level — a turn is either EVENT, STATE, or DISCOURSE. That worked because Encounter Cadence's domain (initiative calls) lives in turns that are usually homogeneous: Matt narrates the encounter setup in his own voice, then calls initiative. Time-Mention's domain (time-bearing phrases) lives in turns that are often heterogeneous: Matt narrates in his own voice while quoting an NPC, with the time-mention possibly attached to either voice.

Turn-level Stage 0 reject in heterogeneous-turn domains loses real signal: it rejects the whole turn even when the trigger phrase is in Matt's voice, just because the turn also contains NPC speech somewhere else. Phrase-span Stage 0 preserves the signal by checking whether the *trigger phrase itself* is inside NPC speech (quote-mark proximity, voicing-tag adjacency) rather than checking whether the turn anywhere contains NPC speech.

**Forward-applicable rule.** Future extractors operating in densely-mixed-narration domains — Loot/Reward (Matt narrates loot while a player or NPC speaks), Faction-Reference (Matt narrates faction-name with possibly-quoted dialogue), NPC-introduction (mixed Matt narration and NPC voice from the start) — should design Stage 0 patterns at phrase-span level when turns are heterogeneous, not after a turn-level Stage 0 ships and has to be retrofitted. The retrofit cost is a calibration cycle plus a held-out re-judge; designing phrase-span up front is cheaper.

**Phase 3.5 corollary.** NPC-dialogue detection itself needs phrase-proximity tightening, not just turn-level any-tag detection. The current Patch 2 fires `is_npc_dialogue_present=True` when *any* NPC voicing tag (`I'd say`, `she goes`, etc.) appears anywhere in the turn — even when the trigger phrase is structurally distant. This over-routes some Matt narration to UNKNOWN_SHAPE. Future phrase-span Stage 0 designs should require quoted-speech proximity to the trigger phrase, not turn-level any-tag.

**Pending confirmation at Ship 3.** Loot/Reward will operate in densely-mixed-narration territory. If its Stage 0 design adopts phrase-span filtering from Phase 1 and ships cleanly without the retrofit Time-Mention paid, Lesson 9 promotes to v2 of the lessons doc.

---

## Lesson 10 (candidate) — test patches pairwise, not just sequentially

**Surfaced:** Phase 3 v1.2 calibration. The Patch 1 ↔ Patch 2 interaction was diagnosed mid-cycle: Patch 1 (turn-level dedup with same-sentence ≤80 chars + same-category-and-anchor ≤200 chars) and Patch 2 (NPC-phrase routing to UNKNOWN_SHAPE) interact destructively. Patch 2 routes some legitimate Matt-narration UNKNOWN_SHAPE candidates next to NPC-speech-routed UNKNOWN_SHAPEs in the same turn; Patch 1 then dedups them as same-category-same-anchor neighbors. Result: real signal lost.

**Confirmed:** Phase 3.5 v1.3. The Patch 1 ↔ Patch 2 entanglement still drives most of the v1.2 → v1.3 retention loss; Patch 6 (the v1.3 patch, targeting `since` disambiguation) doesn't touch this surface area at all.

**The lesson.** Per-patch verification is necessary but not sufficient. Each patch in isolation may pass its own spot-test, design review, and unit-style check. But two patches that touch related surface area can produce destructive interference that neither's per-patch test would catch.

The specific shapes that recurred:

- Dedup ↔ category-routing: a dedup window calibrated against pre-routing records becomes too aggressive when routing changes which records are adjacent in category-space.
- Idiom-filter ↔ NPC-detection: an idiom that's correctly rejected when it's clearly Matt narration becomes ambiguous when the NPC-detection flag fires on the same turn.
- Stage 0 reject ↔ Stage 1 priority order: a Stage 0 D-rule that would correctly reject in isolation lets a phrase through that then gets mis-classified by Stage 1 priority.

**Forward-applicable rule.** Calibration cycles must include pairwise interaction tests, not just per-patch verification. When two patches touch related surface area (dedup ↔ category-routing, idiom-filter ↔ NPC-detection, Stage 0 ↔ Stage 1, etc.), test them together against the full eval set, not separately. Operationally:

1. Run baseline metrics (no patches).
2. For each candidate patch, run metrics with that patch only.
3. For each pair of candidate patches that touch related surface area, run metrics with both patches together.
4. Compare pair-metrics to the sum of individual-metrics. Where they differ, document the interaction.

Step 3 is the new step. Steps 1, 2, 4 were already in the calibration playbook from Ship 1.

**Pending confirmation at Ship 3.** Loot/Reward will likely have ≥3 patches in its v1.x calibration cycle. If its calibration cycle adopts pairwise interaction testing and surfaces an interaction that per-patch testing missed, Lesson 10 promotes to v2.

---

## Lesson 11 (candidate) — regex change with zero record-level effect is a diagnosis signal, not a refinement signal

**Surfaced:** Phase 3.5 v1.3. Patch 6 was structurally correct — tightened CUMULATIVE_BACKWARD_TEMPORAL `since` from a loose verb-list to an explicit allow-list (event verbs, time-noun follow-ons, `[duration] ago`, named time anchors). Spot-tested correctly on 10 disambiguated `since`-form sentences (rejected `since you mention it`, `since the blade has been broken`; accepted `since you left`, `since 3 hours ago`).

**Confirmed:** Same phase. Patch 6 produced **zero record-level deltas** on the calibration set. The v1.2 → v1.3 metrics were identical: strict precision 73.8%/73.8%, FP rate 3.4%/3.4%, dup rate 3.4%/3.4%, retention 85.4%/85.4%.

The retention loss the patch was meant to recover lived in **different patches' interactions**, not in the `since` surface area at all. Diagnosing nine v1.2 broken records directly surfaced eight different failure shapes — bedtime framing, foot-travel idiom, idiom collision, NPC voicing tag over-fire, travel priority over-fire, borderline anchors, taxonomy boundary cases — none of which `since` disambiguation touched. Patch 6 was rigorous in design but targeted at a surface area v1.2 had already covered.

**The lesson.** A regex change that passes design review but produces zero deltas is a signal that the **diagnosis was wrong**, not the regex. The diagnosis "we lost retention because Patch 3's `since` regex is too loose" was internally coherent and consistent with the failure-mode descriptions in calibration verdicts. But the failure-mode descriptions were proximate causes, not root causes — the actual lost-retention records didn't key on `since` at all.

The cost of this diagnosis-error: a full Phase 3.5 calibration cycle (extractor patch, sample re-run, eval-set re-run, regression check, validation report) for zero gain.

**Forward-applicable rule — diagnosis-first calibration.** Future patch design should require a 10–15 record diagnostic spot-test BEFORE the patch is applied:

1. Identify the failing record set (e.g., the 26 v1.2 retention-broken records).
2. Sample 10–15 of them.
3. Read each one directly. Characterize the failure shape from the actual record (what regex fired, what patterns missed, what context drove the mis-classification).
4. Group the failures by shape.
5. Design the patch to target the dominant shape.
6. Spot-test the patch against the failing records of that shape — confirm the patch lands at record level.
7. Then apply the patch and run the calibration cycle.

If step 6 produces zero deltas, the diagnosis (step 3) was wrong, not the patch. Re-do steps 1–5 with the actual root-cause shape.

**Why this matters more for Ship 3+.** Ship 1 (Encounter Cadence) had ~14 records in its initial calibration; the failure modes were dense per-record and easy to read directly. Ship 2 (Time-Mention) calibrated against 321 records — large enough that the proximate-cause descriptions in verdicts could mislead about root cause. Ship 3+ extractors will likely calibrate against similar or larger sample sizes. Diagnosis-first calibration is cheap (10–15 record reads is ~20 minutes) and saves a full calibration cycle when wrong.

**Pending confirmation at Ship 3.** Loot/Reward will likely have a v1.x patch cycle with a diagnosis step. If its patch design includes the diagnostic spot-test before patch application and surfaces a similar "diagnosis-was-wrong" signal that would have caused a wasted cycle, Lesson 11 promotes to v2.

---

## What v2 of the lessons doc will look like

When Ship 3's findings phase confirms (or contradicts) these candidates, the lessons doc bumps to v2 with:

- Lessons 1–8 carried forward verbatim from v1 (durable, well-validated).
- Lessons 9–11 promoted from this candidates file, refined with Ship 3's evidence.
- Any new Lesson 12+ surfaced by Ship 3 added.
- The §9 operating-doctrine checklist updated to incorporate any new doctrines from the promoted lessons (e.g., "phrase-span Stage 0 from Phase 1 in heterogeneous-turn domains," "pairwise interaction tests in calibration cycles," "diagnosis-first patch application").

Until Ship 3, this file is the canonical reference for Lessons 9–11. Future extractor Phase 1 specs should read both `corpus_builder_lessons_v1.md` and this file.
