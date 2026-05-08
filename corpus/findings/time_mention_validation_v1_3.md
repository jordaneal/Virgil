# Time-Mention Extractor v1.3 — Validation Report

**Phase:** Track 5 Ship 2, Phase 3.5 — targeted retention recovery, single patch.
**Extractor version:** `time_mention_v1_3`
**Hand-sample episodes (OQ7 lock):** unchanged from Phase 2/3.
**Eval set:** `findings/time_mention_eval_set_v2.json` (321 calibration records).
**Date:** 2026-05-07

---

## STOP-AND-REPORT — Patch 6 had no measurable effect; two of four gates still miss

| Gate | Target | v1 | v1.2 | **v1.3** | Status |
|---|---:|---:|---:|---:|---|
| Strict precision | ≥ 78% | 55.5% | 73.8% | **73.8%** | **FAIL** −4.2pp |
| FP rate | ≤ 5% | 11.2% | 3.4% | **3.4%** | **PASS** |
| Duplicate rate | ≤ 5% | 16.8% | 3.4% | **3.4%** | **PASS** |
| No-regression retention | ≥ 92% | n/a | 85.4% | **85.4%** | **FAIL** −6.6pp |

**Two gates pass, two fail. Patch 6 produced zero record-level deltas.** Per the prompt's third stop-and-report trigger:

> Surface area of `since` disambiguation reveals it's harder than expected (more contextual than regex)

— this is the actual finding. Not because the regex was wrong, but because v1.2 was *already* filtering the failure modes Patch 6 targeted. The retention loss the patch was meant to recover lives in different patches' interactions.

---

## 1. What Patch 6 did

Tightened `CUMULATIVE_BACKWARD_TEMPORAL` from a loose `since\s+(?:you|we|they)\s+(?:left|arrived|...)` to an explicit allow-list:

- `since (you|we|they|the party|he|she|it) [last|first]? <event-verb>` (left, arrived, woke, met, encountered, departed, returned, started, began, crossed, entered, exited, spoke, talked, finished, got, went)
- `since (you've|we've|they've) <participle>`
- `since [the last|that] <time-noun>` (morning, evening, day, week, battle, encounter, fight, rest, meal, etc.)
- `since N <duration-unit>` (since 3 hours)
- `since (yesterday|earlier|previously|breakfast|lunch|dinner|sundown|sunup|sunrise|sunset|nightfall|daybreak)`
- `<duration> ago`

Spot-tested directly with 10 `since`-form sentences — patch correctly rejects causal forms (`since you're looking`, `since the blade has been broken`, `since the chamber where`, `since the name has come up`, `since you mention it`) and accepts temporal forms.

## 2. Why Patch 6 had no effect on the eval set

The v1.2 `CUMULATIVE_BACKWARD_TEMPORAL` regex (from Patch 3) already required either:
- `(?:last|first)\s+\w+(?:ed|t)?` after a subject pronoun, OR
- one of an explicit verb list (`left|arrived|met|saw|got|came|went|entered|started|began|finished`), OR
- `(?:you'?ve|we'?ve|they'?ve)\s+(?:been|seen|met|left|arrived)`, OR
- bare `\bago\b`

That v1.2 pattern *already* rejected `since you're looking` / `since the blade has been broken` / `since the chamber where` / `since you mention it`. Patch 6's allow-list refinement is more rigorous in design (uniform structure, broader verb list) but matches the same surface area of records on this 321-record calibration set.

**The retention loss in v1.2 (26 broken records) does not key on the loose `since` path.** Examined nine of the v1.2 broken records directly:

| trigger_id | expected | v1.3 emitted | sentence (truncated) |
|---|---|---|---|
| C1E047_t593 | scene_transition | cumulative_anchor | "As you all get to bed, a few hours into the evening, Keyleth, you are starting to doze off..." |
| C1E047_t1081 | in_scene_compression | travel_duration | "you're probably about an hour and a half foot travel before you exit the southern portion..." |
| C1E057_t1303 | in_scene_compression | UNKNOWN_SHAPE | "It has been steeped way too long." |
| C2E018_t2072 | scene_transition | UNKNOWN_SHAPE | "I'd say by the time you've gotten here, it'd be about noon in the day." |
| C2E024_t533 | in_scene_compression | UNKNOWN_SHAPE | "You've probably been here for the better part of an hour or two..." |
| C2E024_t2371 | cumulative_anchor | travel_duration | "Let's see, we had about three days traveling there." |
| C2E031_t878 | cumulative_anchor | UNKNOWN_SHAPE | "It's been a series of dead ends." |
| C2E031_t1035 | UNKNOWN_SHAPE | cumulative_anchor | "they existed close to 1500 years ago." |
| C2E031_t1051 | in_scene_compression | scene_transition | "Practicing the next few days and trying some things out..." |

None of these are `since`-disambiguation cases. The actual root causes are:

- **t593**: SCENE_TRANSITION patterns don't include `(?:get|going|head)\s+to\s+bed` or sleep-onset framing — bedtime → cumulative_anchor wins via the time-of-day-with-offset pattern.
- **t1081**: TRAVEL_PHRASE matches `foot travel` — fires priority 2 (travel) over priority 4 (in_scene_compression), so even though the meaning is in-scene-compressed travel time, travel_duration wins.
- **t1303**: D5 idiom filter ("it's been [past-participle state]") matches `It has been steeped` — correctly rejects to UNKNOWN_SHAPE per Patch 5, but Jordan judged this should be in_scene_compression (steeping took fictional time). Conflict between Patch 5 idiom rule and Jordan's domain judgment.
- **t2072**: `is_npc_dialogue_present=True` because turn has `"I'd say"` (NPC voicing tag pattern fires on `i'?d` too loosely? Or because of a quoted speech somewhere in the turn). Patch 2 routes phrase to UNKNOWN_SHAPE even though phrase is in Matt narration.
- **t533**: Same as t2072 — NPC routing over-fires on Matt narration that contains quotes elsewhere in turn.
- **t2371**: TRAVEL_PHRASE fires on `traveling there` — priority over cumulative_anchor.
- **t878**: CUMULATIVE_TIME_VOCAB doesn't fire on "dead ends" sentence; falls through to UNKNOWN_SHAPE. Patch 3's temporal-context check rejected. Jordan's judgment of cumulative_anchor here is a borderline call ("It's been" pattern with implicit cumulative meaning but no explicit time vocab).
- **t1035**: SCENE_TRANSITION_PHRASE fires `years ago` via the relative-time anchor; CUMULATIVE then catches `1500 years ago`. Both patterns match; priority order picks cumulative_anchor. Jordan judged this UNKNOWN_SHAPE because the NPC backstory ("close to 1500 years ago") is borderline campaign-clock anchor.
- **t1051**: SCENE_TRANSITION_PHRASE matches `the next few days`. Jordan judged in_scene_compression (montage of practice). Genuine boundary case between scene_transition and in_scene_compression for multi-day practice montages.

These are eight different failure shapes, none of which `since` disambiguation touches. Patch 6's regex tightening was structurally correct but targeted at a surface area v1.2 had already covered.

---

## 3. Filed insights confirmed

**Lesson 9 — phrase-span vs turn-level Stage 0.** Patch 2 (Phase 3) confirmed working as designed. The architecture pattern is right.

**Lesson 10 — patch interactions need pairwise testing.** Phase 3 noted the Patch 1 ↔ Patch 2 entanglement. Phase 3.5 surfaces a corollary: **patches targeting structurally-similar surface area double up.** Patch 3's existing `since`-tightening already covered Patch 6's intended cases; Patch 6 added rigor without adding coverage. A stronger v2 lessons-doc framing: before applying a regex tightening, spot-test it against a 10-15 record diff sample to confirm record-level delta. A patch that passes design review but produces zero deltas is a signal that the diagnosis was wrong, not the regex.

**Lesson 11 (candidate) — calibration-set ceiling effect.** The v1.2 → v1.3 numbers are identical because the 321-record calibration is a finite surface, and v1.2 already exhausted the patches' coverage. The remaining 26 broken records require *different* patches than the ones designed in Phase 3. To break through the 73.8% precision ceiling on this calibration set, a v1.4 would need to address scene_transition/cumulative_anchor/travel_duration boundary disambiguation directly (priority order tweaks, pattern-overlap resolution) rather than tightening Stage 0 further.

---

## 4. Recommendation surfaced for Jordan's lock (no auto-escalation)

Two paths:

**Path A: Accept v1.3 as published baseline.** Numbers identical to v1.2. Strict precision 73.8%, FP rate 3.4%, dup rate 3.4%, retention 85.4%. v1.x ships with the soft thresholds met (FP and dup), the hard thresholds (precision and retention) honestly under-target. Phase 4 builds gate-set on v1.3 and proceeds.

**Path B: Lock v1.4 patch directions.** Three concrete decisions surfaced from §2's failure-shape analysis:
1. Add SCENE_TRANSITION patterns for sleep-onset / bedtime framing (`get to bed`, `bed down`, `settle in for the night`).
2. Tighten priority 2 TRAVEL detection to require explicit travel verb in the trigger phrase, not just the window — current logic over-fires on "foot travel" / "traveling there" idioms inside non-travel scenes.
3. Tighten Patch 2 NPC-dialogue detection: `i'?d say` and similar weak voicing tags shouldn't trigger turn-level `is_npc_dialogue_present`. Require quoted speech proximity to the trigger phrase, not just any-NPC-tag-anywhere-in-turn.

Path B targets ~10-15 of the 26 retention-broken records. Doesn't address the genuine boundary cases (t1051 montage, t878 borderline anchor, t1035 backstory borderline) which are taxonomy-judgment not regex.

---

## 5. Files

| Artifact | Path |
|---|---|
| Extractor source (v1.3) | `extractors/time_mention.py` |
| Hand-sample (v1.3) | `samples/time_mention_sample_v1_3.json` (234 records, identical to v1.2) |
| Hand-sample (v1.2, preserved) | `samples/time_mention_sample_v1_2.json` |
| Hand-sample (v1, preserved) | `samples/time_mention_sample_v1_1.json` |
| Eval set v2 | `findings/time_mention_eval_set_v2.json` |
| Regression runner | `extractors/test_time_mention_eval_v2.py` |
| Validation v1 | `findings/time_mention_validation_v1.md` |
| Validation v1.2 | `findings/time_mention_validation_v1_2.md` |
| Validation v1.3 | this file |
| Cross-extractor lessons | `corpus_builder_lessons_v1.md` |
