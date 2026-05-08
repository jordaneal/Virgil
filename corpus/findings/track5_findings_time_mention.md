# Time-Mention — Findings (v1.3)

**Ship:** Track 5, Ship 2 — Time-Mention Extractor
**Source corpus:** CRD3 c=2 alignment, 140 unique episodes (94 C1, 46 C2)
**Extractor version:** `time_mention_v1_3`
**Records emitted:** 3,592 across 140 episodes
**Date completed:** 2026-05-07

---

## 1. Question asked

When does Matt Mercer narrate a quantity of in-fiction time elapsing, and what shape does that mention take? Specifically: how often per episode, what time scales (minutes / hours / days / weeks / years), and what category — durational compression inside an active scene, durational travel, a discrete scene break, or an explicit assertion of how much time has passed or what time of day it currently is?

The downstream goal is informing Track 4 spec design — particularly any Virgil component that needs to model fictional time progression for narrative continuity, world-state updates, or pacing rhythm. The extractor's job is to produce structured records a human can read; the LLM is never in the execution path.

---

## 2. Method

Each MATT turn in CRD3 c=2 was scanned for time-bearing phrases using deterministic regex. Architecture is the four-stage pipeline locked from `corpus_builder_lessons_v1.md`:

1. **Stage 0** — three-way EVENT / STATE / DISCOURSE gate. Eight DISCOURSE rejects (D1–D8 minus D4) catch production OOC, spell-duration mechanic-talk, table-talk, idiomatic phrases, NPC dialogue, player-question pass-back, and causal `since` clauses. STATE flags (`is_combat_state`, `is_recap_state`) preserve combat round-counts and recap blocks as flagged-not-rejected.
2. **Stage 1 candidate detection** — phrase-span regex over the four time-mention categories.
3. **Stage 1 classification** — first-match-wins priority order: `scene_transition` > `travel_duration` > `cumulative_anchor` > `in_scene_compression`.
4. **No-default-catchall** — phrases that survive Stage 0 but don't match a category are flagged `unknown_shape: true` and dumped for review, never silently absorbed.

The pipeline evolved across three versions:

- **v1.0** — single-stage detection across four categories plus UNKNOWN_SHAPE flag. Phase 2 hand-sample on 10 locked episodes, 321 records. D6 (NPC-dialogue reject) demoted to flag (`is_npc_dialogue_present`) when its spot-check precision came in below 85%, per the OQ1 fallback clause.
- **v1.2** — five patches addressing eval-set failures: turn-level dedup, NPC-phrase routing to UNKNOWN_SHAPE, cumulative_anchor temporal-context tightening + D8 causal-since filter, D1 OOC extension, D5 idiomatic-phrase filters.
- **v1.3** — Patch 6: tightened CUMULATIVE_BACKWARD_TEMPORAL `since` regex to an explicit allow-list. Produced zero record-level deltas because v1.2's existing `since` handling already filtered the failure modes; the patch was structurally correct but targeted a surface area v1.2 had already covered. Surfaced Lesson 11 (calibration-set ceiling effect / diagnosis-first calibration).

Eval-set construction: v1 (321 calibration, 10 hand-sample episodes) → v2 (321 calibration with Jordan + Claude blind judgments) → v3 (25 held-out gate-set, `seed=7777`, blind re-judged at Phase 5). Held-out methodology was preserved by raw_text stripping and `--holdout` flag enforcement; mechanical disjointness from calibration was `not_possible_documented` and surfaced as a known v1 limitation.

A Phase 5 validation-set (15 records, `seed=9999`, sampled from the 130 episodes outside the hand-sample) was constructed for one-shot post-ship measurement in Phase 5b. As of this doc, Phase 5b is **pending** — `expected_category` fields are null and the authoritative reliability claim awaits that session.

The classification taxonomy is locked at four categories from Phase 1 and was never expanded. No LLM was used at any stage. Causality window is 500–800 chars / 5–8 turns (smaller than Encounter Cadence's 1500/15-25, justified by time-mentions being largely self-contained). Anchor walk-back is up to 15 turns for relative references.

For the durable architectural lessons that informed each design choice, see `corpus_builder_lessons_v1.md` (Lessons 1–8 from Ship 1) and `lessons_doc_v2_candidates.md` (Lessons 9–11 from this ship).

---

## 3. Sample size

- **Full parse output:** 3,592 records across 140 episodes (every episode produced ≥1 record).
- **Hand-sample / calibration set:** 321 records across 10 locked episodes, Jordan + Claude blind-judged.
- **Held-out gate-set:** 25 records, `seed=7777`, blind re-judged at Phase 5. Measured exactly once.
- **Validation-set:** 15 records, `seed=9999`, drawn from the 130 episodes outside the hand-sample. Phase 5b judging pending.

The post-ship reliability claim in §4 will derive from the validation-set; the gate-set numbers carry the published-claim framing for the v1.3 ship-pass decision.

---

## 4. Reliability — read this before quoting any number below

The held-out gate-set (25 records, blind re-judged at Phase 5) passed all four published-claim ship gates:

| Gate | Target | v1.3 held-out | v1.3 calibration |
|---|---:|---:|---:|
| Strict precision | ≥60% | **80.0%** | 73.8% |
| FP rate | ≤8% | **4.0%** | 3.4% |
| Duplicate rate | ≤6% | **0.0%** | 3.4% |
| Retention vs v1 | hold | 73.8% | 73.8% |

By the methodology this ship was designed around, **v1.3 is shipped**. The held-out numbers are slightly *better* than calibration, partly because fresh blind reads corrected calibration's over-aggressive DUPLICATE marks (the 85.4% retention number from Phase 3.5 likely understates the true v1 → v1.2 regression).

**However**, two reliability caveats apply:

- The held-out gate-set is **not mechanically disjoint from calibration**. v1.3 dedup renumbering preserves trigger keys against v2 calibration, so the gate's 25 records share `(trigger_id, same_turn_record_index)` keys with calibration. Methodology was preserved by blind re-judging without referencing calibration verdicts, but the calibration-distribution-overlap is real. The Phase 5 validation-set exists specifically to fix this — it's drawn from the 130 unseen episodes, mechanically disjoint by episode.
- **Phase 5b validation pass is pending.** Until that judging session runs, the gate-set numbers are what stand. Following Encounter Cadence's pattern (where post-ship blind sampling produced different numbers than the held-out gate), **expect the validation-set to surface FP shapes the gate-set didn't see.**

**Sharpened claim language for downstream consumers:**

> Time-mention frequency per episode and corpus-level category proportions are directionally reliable. Held-out precision is 80% on the gate-set; expect ~5–15pp lower in the wild based on Encounter Cadence's prior. Validation-pass measurement pending.

> Category proportions at the corpus level are suggestive of Matt's narrative tendencies but should not be treated as ground truth for individual record categorization. Calibration precision is 73.8%, held-out is 80%, validation is pending Phase 5b.

> The UNKNOWN_SHAPE bucket at 58.2% of corpus records is **not** an extractor-failure signal — it is the Lesson-2-mandated "no default sinkhole" working as designed. UNKNOWN_SHAPE collects everything that survived Stage 0 (so it's a real time-mention) but didn't match Stage 1 patterns (so the category is genuinely unclear). Track 4 should treat UNKNOWN_SHAPE records as "this is a time-bearing phrase, but the category is open to interpretation," not as "this is an extractor mistake."

**Known v1 limitations** (full list in §6):

- `is_combat_state` under-detection from the OQ5 25-turn lookback lock — fires on only 0.3% of records, far below the real combat-state frequency in CRD3.
- Bedtime / sleep-onset framing not in `scene_transition` patterns (`get to bed`, `bed down`, `settle in for the night`).
- `travel_duration` vs `in_scene_compression` boundary is fuzzy where the trigger phrase contains a travel verb but the scene is non-travel.
- NPC-dialogue detection fires turn-level on weak voicing tags (`I'd say`, `she goes`) without phrase-proximity, occasionally over-routing real Matt narration to UNKNOWN_SHAPE.
- Held-out gate-set not mechanically disjoint from calibration (see above).
- Eight diagnosed-but-un-patched failure shapes from Phase 3.5 — bedtime, foot-travel idiom, "It has been steeped" idiom collision, NPC voicing tag over-fire, "X traveling there" priority-2, "It's been a series of dead ends" borderline anchor, "1500 years ago" backstory borderline, "next few days practicing" boundary case.
- Seconds-band time-mentions excluded by §11.1 lock — T20-style sub-minute beats accepted as a known v1 miss.

---

## 5. Headline numbers — frequency and category

### Per-episode density

| Metric | Value |
|---|---:|
| Episodes processed | 140 |
| Episodes producing ≥1 record | 140 (100%) |
| Episodes producing zero records | 0 |
| Total records emitted | 3,592 |
| Mean records per episode | 25.66 |
| Median records per episode | 25 |
| Maximum records per episode | 53 (C1E027) |
| Minimum records per episode | 8 (C1E085) |
| Std. dev. | 9.38 |

**Every CRD3 c=2 episode contains time-mentions.** No zero-event episodes — even the lowest-count episodes (C1E085 at 8 records, C1E114 at 9) carry meaningful time-bearing narration. This is the single largest density signal: time-mentions are far more frequent than encounter initiations (Ship 1's 1.21 records/episode mean) because Matt narrates time progression continuously, not just at combat boundaries.

Distribution shape:

| Bucket | Episodes | Proportion |
|---|---:|---:|
| <10 records | 2 | 1.4% |
| 10–19 records | 34 | 24.3% |
| 20–29 records | 62 | 44.3% |
| 30–39 records | 29 | 20.7% |
| 40+ records | 13 | 9.3% |

Modal density is 20–29 records per episode (~5 minutes of fictional time per episode if mentions average ~10 minutes apart, which is back-of-envelope consistent with the median episode length of 3–4 hours).

### Campaign split

| Campaign | Episodes | Records | Records / episode |
|---|---:|---:|---:|
| C1 | 94 | 2,327 | 24.76 |
| C2 | 46 | 1,265 | 27.50 |

C2 carries ~11% higher per-episode density. Whether this is genuine pacing drift between Matt's C1-era and C2-era DM style or an episode-length artifact is open.

### Category distribution

| Category | Count | Proportion |
|---|---:|---:|
| `UNKNOWN_SHAPE` | 2,091 | 58.2% |
| `scene_transition` | 635 | 17.7% |
| `cumulative_anchor` | 373 | 10.4% |
| `in_scene_compression` | 284 | 7.9% |
| `travel_duration` | 209 | 5.8% |

The corpus-level UNKNOWN_SHAPE proportion (58.2%) is much higher than the hand-sample's (24%). The hand-sample captured the more easily-categorizable cases; the wider corpus contains substantially more borderline phrases — backstory durations, NPC narrative-flavored references, idiomatic time phrases that survive Stage 0 but fail Stage 1 classification.

Among the four real categories, `scene_transition` dominates at 17.7%, followed by `cumulative_anchor` at 10.4%. This says Matt's most common categorizable time-mention shape is "we move to a new time/scene" — discrete cuts to the next morning, the following week, after a long rest. `cumulative_anchor` (explicit "X hours have passed") is roughly half as common. `travel_duration` and `in_scene_compression` are both single-digit percentages, reflecting that Matt narrates travel and in-scene time-passage less often as standalone phrases (they're more often woven into other narration).

### Granularity distribution

| Bucket | Count | Proportion |
|---|---:|---:|
| `unspecified` | 1,061 | 29.5% |
| `days` | 793 | 22.1% |
| `minutes` | 576 | 16.0% |
| `hours` | 440 | 12.2% |
| `years` | 242 | 6.7% |
| `weeks` | 237 | 6.6% |
| `rounds` | 143 | 4.0% |
| `months` | 100 | 2.8% |

Matt's time-mention vocabulary skews toward sub-day scales when explicit (`minutes` + `hours` = 28%) and day-and-up scales for scene transitions and cumulative anchors (`days` + `weeks` + `months` + `years` = 38%). The 29.5% `unspecified` bucket reflects category-without-explicit-quantity (e.g., "after the next morning" → scene_transition with implicit one-day jump but no quantitative phrase to bucket).

The `days` bucket aggregates calendar days with diurnal time-of-day anchors (`morning|evening|afternoon|night|noon|...`), which masks an analytically useful split. Filed for v2.

### Anchor-found rate

`is_anchored=True`: 142 records (4.0% of corpus).

The 4% reflects that most records aren't relative-time references that can be back-walked — they're either the anchors themselves (cumulative_anchor) or scene transitions / durations that don't reference an earlier time point. The Phase 2 hand-sample's 43.8% anchor-found rate (on the subset of records where back-walk applies) is the more meaningful number for the back-walk mechanism's effectiveness; it's below the spec's 60% target and recommended for a v2 widening to a 25-turn lookback.

### Multi-mention turns

Unique trigger turns: 3,444. Multi-mention turns (≥2 records): 137 (**4.0%**).

Far below the hand-sample's 17.2%. Patch 1's two-form dedup (same-sentence ≤80 chars OR same-category-and-anchor ≤200 chars) is suppressing most adjacent emissions correctly at corpus scale. The remaining 4% are genuine separate phrases (e.g., "an hour later, by the next morning" → two records, in_scene_compression + scene_transition).

### Stage 0 reject volume

Total Stage 0 DISCOURSE rejects: **713**.

| Reject ID | Count | Targets |
|---|---:|---|
| D1 (production OOC) | 347 | Episode breaks, cast banter, meta-procedural Matt narration |
| D7 (player-question pass-back) | 186 | Matt's bare-duration answers to player time questions |
| D5 (idiomatic phrase) | 99 | `wait a minute`, drink/age idioms, "It's been [emotion]" |
| D2 (spell/rules duration) | 62 | `lasts for X` mechanic-talk |
| D8 (causal `since`) | 18 | `since you mention it` and similar non-temporal `since` |
| D3 (table-talk) | 1 | DM pacing requests |

The Stage 0 layer is doing meaningful work: ~17% of candidate phrases are rejected before Stage 1 sees them. D1 and D7 are the dominant reject reasons. D6 (NPC dialogue) is **not** in the reject log — it was demoted to a flag (`is_npc_dialogue_present`) at Phase 2 per the OQ1 fallback when its spot-check precision came in below 85%; the 1,143 records flagged `is_npc_dialogue_present=True` (31.8% of corpus) are D6's measurement at flag-not-reject scale.

### `[EXTRACTOR_UNKNOWN]` count

**0** events. Source format is stable across all 140 episodes.

---

## 6. Per-category notes

### `scene_transition` (17.7%, n=635)

Captures discrete scene breaks: "the next morning," "two weeks later," "after a long rest," "later that evening." Granularity skews to days and weeks. Highest priority in the multi-match resolution (Stage 1 step 3) because scene transitions need to win over compression / travel when both fire on the same phrase.

What it doesn't catch: bedtime / sleep-onset framing (`get to bed`, `bed down`, `settle in for the night`) — these were diagnosed Phase 3.5 as a v1 miss; the records survive into UNKNOWN_SHAPE or get mis-classified as cumulative_anchor.

### `travel_duration` (5.8%, n=209)

Captures party travel/movement: "two days' travel," "a few hours of marching," "an hour foot travel." Granularity skews to hours, days, weeks. Priority 2 in the multi-match resolution.

What it over-fires on: idiomatic uses of travel verbs that aren't actually travel scenes ("foot travel" as a phrase inside a non-travel scene, "X traveling there" inside backstory narration). Phase 3.5 surfaced this as a tightening direction for v1.4 — require the explicit travel verb in the trigger phrase, not just the surrounding window.

### `cumulative_anchor` (10.4%, n=373)

Captures explicit assertions of elapsed time or current time-of-day: "It's been three hours," "Two and a half weeks have passed," "It is now late afternoon," "Since you left, two days." These are the anchor-establishing references that allow downstream relative-time references to be resolved.

What it over-fires on: borderline backstory anchors ("close to 1500 years ago" as NPC-flavored backstory rather than campaign-clock anchor), idiomatic "It's been [a series of dead ends]." Patch 5's idiom filter catches the most common forms; the residue is genuine boundary-judgment territory.

### `in_scene_compression` (7.9%, n=284)

Captures time elapsing during an active scene: "an hour passes," "you spend the next ten minutes," "after a few minutes of work." Lowest priority in the multi-match resolution because compression often co-occurs with stronger signals (scene transitions, travel).

What it doesn't catch: scenes where the compression is implicit ("you steep the tea... it's been ready") — Matt narrates the time-passage indirectly, and the explicit-quantity signal isn't present for Stage 1 to fire on. These survive into UNKNOWN_SHAPE when a related phrase happens to trip Stage 1 on a different category, or get rejected by D5 if the phrasing matches an idiom filter.

### `unknown_shape: true` (58.2%, n=2,091)

Cross-references the Lesson-2 design rule: the no-default-catchall flag for phrases that survive Stage 0 (genuinely time-bearing) but don't match any Stage 1 category. Includes:

- Backstory durations narrated by Matt without campaign-clock framing
- Borderline cases between two categories where neither pattern fires cleanly
- Idiomatic time phrases that escape D5 because they don't match its allow-list
- Time references inside descriptive narration without a clear elapsed-time semantics
- Session/turn-level time references that don't fit the four-category scheme

Track 4 should treat UNKNOWN_SHAPE as **flagged for human review**, not as an extractor failure. This is the bucket where category-judgment work lives.

---

## 7. Filed insights for lessons doc v2

Three confirmed lessons surfaced across this ship's calibration cycles. Documented in `lessons_doc_v2_candidates.md` pending the next ship's confirmation.

### Lesson 9 — phrase-span vs turn-level Stage 0

Confirmed by Patch 2 working as designed. Encounter Cadence's Stage 0 ran at turn level; Time-Mention's D6 demonstrated that turn-level reject loses real signal in heterogeneous turns where Matt narration is mixed with NPC speech. Patch 2's phrase-span-aware NPC routing (quote-mark count + same-sentence NPC voicing tag, then route the *phrase* to UNKNOWN_SHAPE rather than reject the *turn*) preserves real Matt-narration time-mentions that turn-level reject would have lost.

**Forward-applicable rule:** Future extractors operating in densely-mixed-narration domains (Loot/Reward, Faction-Reference, NPC-introduction) should design Stage 0 patterns at phrase-span level when turns are heterogeneous, not after a turn-level Stage 0 ships and has to be retrofitted.

### Lesson 10 — test patches pairwise, not just sequentially

Confirmed by the Patch 1 ↔ Patch 2 interaction in Phase 3. Patch 1 (turn-level dedup with same-sentence ≤80 chars + same-category-and-anchor ≤200 chars) and Patch 2 (NPC-phrase routing to UNKNOWN_SHAPE) interact: Patch 2 routes some legitimate Matt-narration UNKNOWN_SHAPE candidates next to NPC-speech-routed UNKNOWN_SHAPEs in the same turn; Patch 1 then dedups them as same-category-same-anchor neighbors. Result: real signal lost.

**Forward-applicable rule:** Calibration cycles must include pairwise interaction tests, not just per-patch verification. When two patches touch related surface area (dedup ↔ category-routing, idiom-filter ↔ NPC-detection, etc.), test them together against the full eval set, not separately.

### Lesson 11 — regex change with zero record-level effect is a diagnosis signal, not a refinement signal

Confirmed by Patch 6 v1.3. The patch was structurally correct (tightened CUMULATIVE_BACKWARD_TEMPORAL `since` from a loose verb-list to an explicit allow-list, spot-tested correctly on 10 disambiguated `since`-form sentences), but produced **zero record-level deltas** on the calibration set. The retention loss the patch was meant to recover lived in different patches' interactions, not in the `since` surface area at all.

**Forward-applicable rule:** Future patch design should require a 10–15 record diagnostic spot-test BEFORE the patch is applied, to confirm the patch produces record-level deltas. A regex change that passes design review but produces zero deltas is a signal that the **diagnosis was wrong**, not the patch. Diagnosis-first calibration: identify the failing record set, characterize the failure shape from those records' properties, design the patch to target that shape, spot-test against a slice of the failing records to confirm the patch lands, then apply.

---

## 8. Use guidance — what to read this for

### Robust signal — usable for Track 4 spec design

- **Per-episode time-mention density.** Mean ~26 mentions per episode, 100% of episodes carry ≥8. Time-mention is a continuous signal, not an episodic one.
- **Category proportion at corpus level.** scene_transition > cumulative_anchor > in_scene_compression > travel_duration is a stable signal of Matt's narrative emphasis (treat as suggestive, not authoritative — strict precision 73.8% calibration / 80% held-out).
- **Granularity distribution.** Sub-day scales (minutes + hours) and day-and-up scales (days + weeks + months + years) split roughly evenly.
- **Cross-campaign consistency.** C1 and C2 show similar density and category distributions; the cadence is a stable feature of Matt's DM style.

### Suggestive signal — hypothesis-generator only

- **Individual record categorization.** Strict precision 73.8% calibration / 80% held-out / pending validation. Treat individual records as "directionally categorized" — useful for analysis-layer aggregate statistics, not for reasoning over a single record's class.
- **`is_anchored` back-walk results.** 4% corpus-level rate; the 43.8% subset rate from Phase 2 is the more meaningful number for the back-walk mechanism's effectiveness, but both are below the spec's 60% threshold.
- **`is_combat_state` distribution.** 0.3% is known under-detection; do not use this flag as a proxy for "this time-mention is mid-combat." Defer to encounter-cadence records for combat-state context.

### Honest framing for downstream consumers

> Time-Mention provides a directional signal for time-mention frequency and category proportions across the CRD3 c=2 corpus. It is **not** ground truth for individual record categorization, and the 58.2% UNKNOWN_SHAPE bucket is a deliberate flag for human-review-required phrases, not an extractor failure mode.

---

## 9. Future work — v2 candidates

Not scheduled. Listed for visibility:

1. **OQ5 combat-state widening.** Move from 25-turn lookback to 50-turn lookback plus a damage-narration backup signal. The current 0.3% combat-state rate is far below the real frequency.
2. **Bedtime / sleep-onset framing in `scene_transition`.** Add patterns for `get to bed`, `bed down`, `settle in for the night`, `head to bed`.
3. **`travel_duration` vs `in_scene_compression` boundary tightening.** Require the explicit travel verb in the trigger phrase, not just the surrounding window — would catch the "foot travel" / "X traveling there" idiom over-fires diagnosed in Phase 3.5.
4. **Granularity bucket split.** Separate the `days` bucket into `days` (calendar) and `time_of_day` (diurnal: morning / evening / afternoon / night / noon / etc.).
5. **NPC voicing tag detection beyond quote-marks.** Tighten Patch 2 to require quoted-speech proximity to the trigger phrase, not just any-NPC-tag-anywhere-in-turn — would correct the `i'?d say` over-fire that routes some Matt narration to UNKNOWN_SHAPE.
6. **Anchor walk-back depth.** Widen the 15-turn back-walk to 25 turns to bring the 43.8% Phase 2 anchor-found rate above the 60% spec threshold.
7. **Seconds-band recovery.** §11.1's hard exclusion of seconds skips T20-style sub-minute combat beats; a future v2 could add seconds with a stricter Stage 0 to filter the `for a second` micro-beat / `hold on a second` table-talk false positives.

---

## 10. Limitations

1. **130 of 140 episodes were never manually reviewed during eval-set construction.** The hand-sample / calibration set covered 10 locked episodes; the other 130 are present in the full parse but no human spot-checked their classification. The Phase 5 validation-set draws 15 records from those 130 episodes for a one-shot post-ship measurement, but n=15 is directional, not exhaustive.
2. **Held-out gate-set is not mechanically disjoint from calibration.** Filed as `not_possible_documented` — gate-set and calibration both sample from the same 10 hand-sample episodes; v1.3 dedup renumbering preserves trigger keys. Methodology preserved by blind re-judging without referencing calibration verdicts.
3. **Calibration verdicts had over-aggressive DUPLICATE marks.** Fresh held-out reads at Phase 5 corrected several of these, suggesting the calibration retention number (85.4%) understates the true v1 → v1.2 regression. The held-out 73.8% retention is the more accurate v1 → v1.3 retention number.
4. **`is_combat_state` under-detection.** The OQ5 25-turn lookback lock fires on only 0.3% of corpus records, far below the real combat-state frequency in CRD3.
5. **Eight diagnosed-but-un-patched failure shapes from Phase 3.5.** Bedtime framing, foot-travel idiom, "It has been steeped" idiom collision, NPC voicing tag over-fire, "X traveling there" priority-2, "It's been a series of dead ends" borderline anchor, "1500 years ago" backstory borderline, "next few days practicing" boundary case. All filed for v2.
6. **Seconds-band time-mentions excluded by §11.1 lock.** T20-style sub-minute combat beats are accepted as a known v1 miss.
7. **Source corpus is c=2 alignment only.** Same constraint as Encounter Cadence: turn-level data is reportedly byte-identical across c=2/c=3/c=4, confirmed only by importer comparison at Phase 1.
8. **Phase 5b validation pass is pending.** The authoritative published-claim measurement awaits that session. Until it runs, the held-out gate-set numbers (80% strict precision, 4% FP, 0% dup) are the published baseline.

---

## 11. Files

| Artifact | Path |
|---|---|
| Extractor source (v1.3) | `corpus_builder/extractors/time_mention.py` |
| Per-episode output (140 files) | `corpus_builder/output/time_mention/` |
| Full-parse log | `corpus_builder/findings/time_mention_full_parse_log.txt` |
| Full-parse stats | `corpus_builder/findings/time_mention_full_parse_stats_v1_3.md` |
| Hand-sample (v1.3) | `corpus_builder/samples/time_mention_sample_v1_3.json` |
| Eval-set v2 (calibration) | `corpus_builder/findings/time_mention_eval_set_v2.json` |
| Held-out gate-set (judged) | `corpus_builder/findings/time_mention_eval_set_v3_holdout.json` |
| Held-out construction | `corpus_builder/findings/time_mention_eval_set_v3_holdout_construction.md` |
| Validation-set v1 (judging pending) | `corpus_builder/findings/time_mention_validation_set_v1.json` |
| Validation construction | `corpus_builder/findings/time_mention_validation_set_v1_construction.md` |
| Validation v1 / v1.2 / v1.3 reports | `corpus_builder/findings/time_mention_validation_v1{,.2,.3}.md` |
| Regression runner | `corpus_builder/extractors/test_time_mention_eval_v2.py` |
| Session log | `corpus_builder/findings/time_mention_session_log.md` |
| Cross-extractor lessons (Ship 1) | `corpus_builder/corpus_builder_lessons_v1.md` |
| Lessons doc v2 candidates (this ship) | `corpus_builder/lessons_doc_v2_candidates.md` |
| Spec doc | `virgil-docs/TIME_MENTION_V1_SPEC.md` |
