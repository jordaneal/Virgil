# corpus_builder lessons v2

**Cross-extractor architectural lessons learned during Track 5 Ships 1 and 2 (Encounter Cadence, Time-Mention).** Read at the start of every future extractor's Phase 1.

**This doc supersedes `corpus_builder_lessons_v1.md`.** Lessons 1–8 are carried forward verbatim from v1. Lessons 9–11 are new in v2, surfaced and validated at Ship 2 (Time-Mention) and promoted into the durable set. The `lessons_doc_v2_candidates.md` file that staged Lessons 9–11 has been archived; this doc is now the canonical reference for all current lessons.

This document is durable principles, not narrative recap. The detailed history of how each lesson surfaced lives in `findings/encounter_cadence_session_log.md`, `findings/time_mention_session_log.md`, and the Phase 1-6 spec docs.

---

## Purpose

Every extractor in the corpus_builder queue (Loot/Reward next, then Faction-Reference, NPC-Introduction, etc.) will hit some subset of the same architectural problems Encounter Cadence and Time-Mention hit. Solving them once and writing them down means the next extractor doesn't pay the same calibration tax.

The lessons below are constraints on extractor design, not optional best practices. Phase 1 of any future extractor must satisfy the operating-doctrine checklist in §12. If a future extractor's design intentionally violates one of these constraints, the deviation must be surfaced and justified explicitly in that extractor's Phase 1 spec.

---

## Lesson 1 — Local lexical extraction is insufficient for causal gameplay interpretation

Pattern matching on lexical features (regex on trigger phrases, vocabulary lists, immediate-predecessor turn checks) can detect that an event happened, but cannot reliably classify what caused it. Causation in actual-play tabletop spans multiple turns and is often paraphrased past any reasonable phrase list.

For Encounter Cadence specifically: detecting "Matt called for initiative" worked at 14/14 from Phase 1. Classifying "what triggered the initiative call" never crossed 56% in the wild even after four versions of patches. The gap between detection and causal classification is an architectural gap, not a calibration gap.

**Implication for future extractors:** detection (did event X happen?) and causal classification (why did event X happen?) are different problems. Extractors that need both should design separate layers for them and report each independently. An extractor that conflates them will overstate the reliability of one based on the strength of the other.

---

## Lesson 2 — `interruption`-style catchall categories become semantic sinkholes without state memory

When the classification rules can't determine a cause, the record falls through to whatever the default category is. As detection rules tighten and the corpus grows, the default category accumulates everything the rules can't classify, structurally inflating its count and making category-proportion statistics unreliable.

In Encounter Cadence, `interruption` was designed as "Matt initiates combat without clear trigger" — a real pattern. But by v1.3 the category contained: real interruption events, player-action records where the cause happened outside the lookback window, NPC-hostile records where the dialogue paraphrased past the regex, environmental records where the buildup spread across too many turns. The 41% `interruption` proportion in the full parse mixes all of these.

**Implication for future extractors:** do not design a default catchall category. Either:
- Filter uncategorizable candidates entirely at Stage 0 (preferred when the candidate genuinely has no causal information attached)
- Emit them with an explicit `unknown_cause: true` flag rather than a category label (preferred when the event is real but the cause can't be determined)

The principle: never let a category's count become a measurement of "what the rules couldn't classify." That number should always be tracked separately and disclosed honestly.

---

## Lesson 3 — Eval-set passing does not equal generalization

Held-out gate methodology is a real improvement over training-set-only validation, but it does not fully prevent overfit. The held-out set, even when sampled from episodes never reviewed during calibration, still draws from the same broad pool of FP shapes and category boundaries that the calibration set surfaced. New FP families and category-boundary cases that weren't present in either calibration or held-out only appear when the extractor runs against fresh, never-touched data.

Encounter Cadence held-out gates passed (FP 0%, precision 56%). Post-ship blind sampling on never-touched episodes found FP ~7-10% and strict precision ~36%. The held-out gates were a real improvement signal — Stage 0 architecture genuinely worked — but the absolute numbers overstated generalization.

**Implication for future extractors:** build TWO held-out sets from session 1.

- **Gate-set** (~25 records) — used in Phase 4 ship-gate measurement. Drives the decision to ship or stop.
- **Validation-set** (~15 records) — used post-ship for honest precision claim. NEVER named, examined, or referenced during calibration. Run exactly once after the gate-set passes.

If the validation-set numbers diverge sharply from the gate-set numbers, the findings doc reports both with the validation-set as authoritative. The gate-set is a development tool; the validation-set is the published claim.

---

## Lesson 4 — FP families emerge in waves, not all at once

Each calibration cycle of Encounter Cadence exposed a new false-positive family the prior eval set didn't contain:

- v1.0 → v1.1: surfaced regex-artifact FPs (NPC voicing on physical motion, etc.)
- v1.1 → v1.2: surfaced `roll a [save/check]` non-init FPs
- v1.2 → v1.3: surfaced discourse-about-initiative FPs (recap, init-order narration, summon-init-rolls)
- v1.3 post-ship: surfaced episode-recap, mini-placement, exposition FPs that calibration didn't see

The FP rate at any single eval set is a lower bound on the true rate, not the true rate itself.

**Implication for future extractors:** in Phase 1 spec, propose an explicit FP-family taxonomy upfront. List 4-6 FP shapes you can predict from sample observations. Don't pretend the list is complete — assume new families will surface. When a new FP family does surface, treat it as a session-pause-and-document moment rather than a silent regex addition. The FP-family list becomes part of the extractor's documented limitations, not a hidden patch history.

---

## Lesson 5 — Discourse vs event separation matters

Initiative-language is not a reliable proxy for initiative-events. Players reference initiative in casual conversation. Episode breaks contain "what did you roll for initiative?" mid-combat narration. Recap intros recount past combats using initiative vocabulary. Summon spells require rolling an initiative number for ordering without initiating new combat.

The Stage 0 architectural change in v1.3 (classifying each candidate as DISCOURSE / STATE / EVENT before Stage 1 candidate detection) was the highest-impact single change of the entire ship. Held-out FP rate dropped 12% → 0%, calibration precision improved 70.9% → 72.7% (Stage 0 helped old data too, not just new shapes). Wave detection improved 60% → 80% on calibration via STATE-forced combat-active.

**Implication for future extractors:** default to Stage 0 discourse-layer design even when the candidate-detection logic seems unambiguous. Time-Mention is more vulnerable to discourse confusion than Encounter Cadence (players talk about time constantly), so Stage 0 is structurally required there. Loot/Reward will face similar issues with the word "treasure" appearing in OOC discussion. Faction-Reference will face it with NPC names appearing in non-faction contexts.

The Stage 0 layer should classify each candidate into:
- **EVENT** — real domain event. Continue to Stage 1.
- **STATE** — relevant context that affects classification but isn't itself the event. Pass forward as flag.
- **DISCOURSE** — meta-talk about the domain that isn't a real event. Reject the candidate.

---

## Lesson 6 — Causality windows are routinely 5-15 turns, not 1-3

Initial v1.0 design checked the immediate-predecessor turn for causal signals. This caught approximately zero of the trap-activation cases in the corpus. v1.1 widened the window to ~15 turns and immediately caught known-positive cases that v1.0 missed.

Patches across v1.1 → v1.3 repeatedly bumped lookback windows wider — first for traps, then for player actions, then for wave detection. Each time, recall improved. By v1.3, the de-facto window was 1500 chars / 15-25 turns for most classification logic.

The causality between cause and effect in actual-play narration is not the immediate-predecessor turn. A player declares intent at turn 50, Matt narrates consequences across turns 51-65, the resulting event fires at turn 66. The classification logic needs to look back across all of that.

**Implication for future extractors:** default lookback window for cause-effect detection is 10-15 turns minimum. Narrow only with explicit justification (e.g., Time-Mention's "the next morning" probably needs 5-10 turns max because time-references are more local than combat causality). The 1500-char preceding context budget for narration measurement (`narration_buildup_chars`) can stay at the local scale; classification logic should walk back further on demand.

This applies to every extractor doing any form of causal classification: consequence extraction, betrayal/promise detection, emotional payoff tracking, stealth escalation, NPC stance shifts, faction-reference triggers, time-mention anchoring.

---

## Lesson 7 — Held-out methodology must be physically enforced, not policy

In Phase 5 of Encounter Cadence, the held-out methodology was enforced by:
- Storing held-out records in a separate top-level JSON key
- Stripping `raw_text` from held-out records during calibration mode
- Requiring an explicit `--holdout` flag on the test runner to even read the held-out split
- Stopping-and-reporting if Code touched a held-out record during calibration

This worked. It would not have worked as a documentation-only "please don't peek" rule.

**Implication for future extractors:** bake held-out separation into the test runner from Phase 2 implementation, not as an afterthought during Phase 4 calibration. The test runner has two modes — calibration and held-out — that cannot be mixed in a single invocation. The held-out records are physically inaccessible during calibration. The `--holdout` flag must be passed explicitly and only after the calibration regression passes.

---

## Lesson 8 — Detection vs classification are independently shippable

Encounter Cadence's final state: detection works (init events captured cleanly), classification is suggestive only (cause attribution unreliable). Findings doc shipped both layers separately with different reliability claims:
- Frequency and position: directionally reliable, ship for Track 4 use
- Category proportions: hypothesis-generator only, do not drive spec design

Future extractors should structure their findings docs the same way: separate "what we detected" from "how we classified it" and publish reliability claims independently for each. Don't let weak classification poison the perception of strong detection (or vice versa).

---

## Lesson 9 — Stage 0 must operate at phrase-span level in heterogeneous-turn domains

Encounter Cadence's Stage 0 ran at turn level — a turn is either EVENT, STATE, or DISCOURSE. That worked because Encounter Cadence's domain (initiative calls) lives in turns that are usually homogeneous: Matt narrates the encounter setup in his own voice, then calls initiative. Time-Mention's domain (time-bearing phrases) lives in turns that are often heterogeneous: Matt narrates in his own voice while quoting an NPC, with the time-mention possibly attached to either voice.

Turn-level Stage 0 reject in heterogeneous-turn domains loses real signal. It rejects the whole turn even when the trigger phrase is in Matt's voice, just because the turn also contains NPC speech somewhere else. Phrase-span Stage 0 preserves the signal by checking whether the *trigger phrase itself* is inside NPC speech (quote-mark proximity, voicing-tag adjacency) rather than checking whether the turn anywhere contains NPC speech.

Time-Mention paid for this lesson with a retrofit: D6 (NPC-dialogue reject) was originally specified as a turn-level reject, came in below 85% precision in Phase 2 hand-sample, was demoted to a phrase-level flag (`is_npc_dialogue_present`) via the spec's OQ1 fallback, and was eventually replaced in Phase 3 v1.2 Patch 2 with a true phrase-span-aware Stage 0 layer (quote-mark count + same-sentence NPC voicing tag, with the *phrase* routed to UNKNOWN_SHAPE rather than the *turn* rejected). The retrofit cost a calibration cycle plus a held-out re-judge.

**Implication for future extractors:** future extractors operating in densely-mixed-narration domains — Loot/Reward (Matt narrates loot while a player or NPC speaks), Faction-Reference (Matt narrates faction-name with possibly-quoted dialogue), NPC-Introduction (mixed Matt narration and NPC voice from the start) — must design Stage 0 patterns at phrase-span level when turns are heterogeneous, not after a turn-level Stage 0 ships and has to be retrofitted. Phrase-span detection requires quoted-speech proximity to the trigger phrase, not turn-level any-tag detection. Turn-level Stage 0 is acceptable only when the domain's turns are demonstrably homogeneous (a claim that must be supported by sample observation in Phase 1).

---

## Lesson 10 — Calibration cycles must include pairwise interaction tests, not just per-patch verification

Per-patch verification is necessary but not sufficient. Each patch in isolation may pass its own spot-test, design review, and unit-style check. But two patches that touch related surface area can produce destructive interference that neither's per-patch test would catch.

Time-Mention v1.2 → v1.3 surfaced this directly. Patch 1 (turn-level dedup with same-sentence ≤80 chars + same-category-and-anchor ≤200 chars) and Patch 2 (NPC-phrase routing to UNKNOWN_SHAPE) interact destructively: Patch 2 routes some legitimate Matt-narration UNKNOWN_SHAPE candidates next to NPC-speech-routed UNKNOWN_SHAPEs in the same turn; Patch 1 then dedups them as same-category-same-anchor neighbors. Real signal was lost. The Patch 1 ↔ Patch 2 entanglement still drove most of the v1.2 → v1.3 retention loss after a third patch landed.

The specific interaction shapes that recurred:

- Dedup ↔ category-routing: a dedup window calibrated against pre-routing records becomes too aggressive when routing changes which records are adjacent in category-space.
- Idiom-filter ↔ NPC-detection: an idiom that's correctly rejected when it's clearly Matt narration becomes ambiguous when the NPC-detection flag fires on the same turn.
- Stage 0 reject ↔ Stage 1 priority order: a Stage 0 D-rule that would correctly reject in isolation lets a phrase through that then gets mis-classified by Stage 1 priority.

**Implication for future extractors:** calibration cycles must include pairwise interaction tests when two patches touch related surface area. Operationally:

1. Run baseline metrics (no patches).
2. For each candidate patch, run metrics with that patch only.
3. For each pair of candidate patches that touch related surface area, run metrics with both patches together.
4. Compare pair-metrics to the sum of individual-metrics. Where they differ, document the interaction.

Step 3 is the new step from Ship 2. Steps 1, 2, 4 were already in the Ship 1 calibration playbook.

---

## Lesson 11 — Diagnosis-first calibration: a patch with zero record-level deltas means the diagnosis was wrong

A regex change that passes design review but produces zero record-level deltas on the calibration set is a signal that the **diagnosis was wrong**, not the regex. The patch was rigorous in design but targeted at a surface area the prior version had already covered.

Time-Mention v1.3 paid for this directly. Patch 6 was structurally correct — tightened CUMULATIVE_BACKWARD_TEMPORAL `since` from a loose verb-list to an explicit allow-list, spot-tested correctly on 10 disambiguated `since`-form sentences (rejected `since you mention it`, `since the blade has been broken`; accepted `since you left`, `since 3 hours ago`). It produced zero record-level deltas: strict precision 73.8%/73.8%, FP rate 3.4%/3.4%, dup rate 3.4%/3.4%, retention 85.4%/85.4%.

The retention loss the patch was meant to recover lived in **different patches' interactions**, not in the `since` surface area at all. The originating diagnosis ("we lost retention because Patch 3's `since` regex is too loose") was internally coherent and consistent with the failure-mode descriptions in calibration verdicts. But the failure-mode descriptions were proximate causes, not root causes — the actual lost-retention records didn't key on `since` at all. Diagnosing nine v1.2 broken records directly would have surfaced eight different failure shapes that `since` disambiguation didn't touch. The cost of the diagnosis-error: a full Phase 3.5 calibration cycle for zero gain.

**Implication for future extractors:** patch design must require a 10–15 record diagnostic spot-test BEFORE the patch is applied:

1. Identify the failing record set (e.g., the 26 v1.2 retention-broken records).
2. Sample 10–15 of them.
3. Read each one directly. Characterize the failure shape from the actual record (what regex fired, what patterns missed, what context drove the mis-classification).
4. Group the failures by shape.
5. Design the patch to target the dominant shape.
6. Spot-test the patch against the failing records of that shape — confirm the patch lands at record level.
7. Then apply the patch and run the calibration cycle.

If step 6 produces zero deltas, the diagnosis (step 3) was wrong, not the patch. Re-do steps 1–5 with the actual root-cause shape.

This matters more as ship sizes grow. Encounter Cadence had ~14 records in its initial calibration; failure modes were dense per-record and easy to read directly. Time-Mention calibrated against 321 records — large enough that the proximate-cause descriptions in verdicts could mislead about root cause. Ship 3+ extractors will calibrate against similar or larger sample sizes. Diagnosis-first calibration is cheap (10–15 record reads is ~20 minutes) and saves a full calibration cycle when the diagnosis is wrong.

---

## Operating doctrine for future extractors

Phase 1 of any future extractor must satisfy the following checklist before locking the spec for Phase 2 implementation:

- [ ] **Stage 0 discourse gate designed BEFORE Stage 1 candidate detection.** Specify EVENT / STATE / DISCOURSE patterns from sample observations.
- [ ] **Stage 0 operates at phrase-span level if the domain's turns are heterogeneous.** Turn-level Stage 0 is acceptable only when sample observation supports a homogeneous-turn claim. Phrase-span detection requires quoted-speech proximity to the trigger phrase, not turn-level any-tag.
- [ ] **Causality window default 10-15 turns, narrower only with justification.** State the window value and the reasoning.
- [ ] **Two held-out sets specified.** Gate-set used in Phase 4 ship-gate measurement. Validation-set used once post-ship for honest precision claim. Mechanical enforcement (separate flags, separate runners) baked into the implementation spec.
- [ ] **FP-family taxonomy documented from Phase 1.** List 4-6 predicted FP shapes and how Stage 0 or Stage 1 should filter each.
- [ ] **No default catchall category.** Uncategorizable candidates either filter at Stage 0 or emit with explicit `unknown_cause: true` flag, never a default category label.
- [ ] **Detection vs classification separation documented.** State which layer does what; reliability claims on each will be reported independently in findings.
- [ ] **Eval-set overfit risk acknowledged in spec.** Phase 1 explicitly states that any ship-gate precision number is an upper bound, not a true rate, and that the validation-set will be the published claim.
- [ ] **Pairwise interaction testing in the calibration playbook.** When two patches touch related surface area (dedup ↔ category-routing, idiom-filter ↔ NPC-detection, Stage 0 ↔ Stage 1, etc.), the calibration cycle runs them together against the full eval set, not separately.
- [ ] **Diagnosis-first patch application.** Each patch must include a 10–15 record diagnostic spot-test against the failing record set before the patch is applied; a patch with zero record-level deltas on the calibration set is a signal the diagnosis was wrong, not the patch.

---

## What this doc isn't

- **Not extractor-specific guidance.** Each extractor's Phase 1 spec covers domain-specific patterns. This doc is the cross-cutting architectural patterns.
- **Not ontology-design rules.** The single-category-per-extractor rule from `CORPUS_BUILDER.md` still applies. This doc is about implementation architecture, not about deciding what an extractor should classify.
- **Not a replacement for `CORPUS_BUILDER.md`.** That doc covers project structure, eval-set construction, parallel-job protocols, output schema. This doc covers the architectural patterns we paid for during Ships 1 and 2 and want to apply forward.
- **Not final.** Versioned `v2`. Ship 3 (Loot/Reward) will likely surface lessons that weren't visible from Encounter Cadence or Time-Mention alone — at that point a new `lessons_doc_v3_candidates.md` stages those candidates until promotion.

---

## Reference: where these lessons come from

| Lesson | Ship | Phase surfaced | Detailed history |
|---|---|---|---|
| 1. Local lexical insufficient | Ship 1 | Phase 4 → Phase 5 | encounter_cadence_session_log Phase 4 + n=42 post-ship sampling |
| 2. Interruption sinkhole | Ship 1 | Phase 5 + post-ship | external review (GPT) + post-ship spot-check |
| 3. Eval-set ≠ generalization | Ship 1 | Phase 5 → post-ship | held-out 56% vs post-ship 36% gap |
| 4. FP families in waves | Ship 1 | Phase 4 + Phase 5 + post-ship | encounter_cadence_session_log Phase 4 (calibration 36% → ship gate 70.9%), Phase 5 (held-out 56% → wild 36%) |
| 5. Discourse vs event | Ship 1 | Phase 5 | Stage 0 +20pp wave, +1.8pp precision, FP 12% → 0% on held-out |
| 6. 10-15 turn windows | Ship 1 | Phase 2.5 + Phase 4 | filed insight in encounter_cadence_session_log Phase 2.5; v1.1 trap window widening |
| 7. Held-out enforcement | Ship 1 | Phase 5 | `--holdout` flag + structurally-stripped JSON |
| 8. Detection vs classification | Ship 1 | post-ship | detection 14/14 from Phase 1, classification never crossed 56% |
| 9. Phrase-span Stage 0 | Ship 2 | Phase 2 → Phase 3 v1.2 | time_mention_session_log Phase 2 D6 demotion; Phase 3 v1.2 Patch 2 phrase-span replacement |
| 10. Pairwise interaction tests | Ship 2 | Phase 3 v1.2 → v1.3 | time_mention_session_log Phase 3.5; Patch 1 ↔ Patch 2 entanglement diagnosis |
| 11. Diagnosis-first calibration | Ship 2 | Phase 3.5 v1.3 | time_mention_session_log Phase 3.5; Patch 6 zero-delta result |
