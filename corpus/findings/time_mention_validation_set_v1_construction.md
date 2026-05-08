# Time-Mention Validation-Set v1 — Construction Notes

**Date:** 2026-05-07
**Phase:** Track 5 Ship 2, Phase 5
**Output:** `corpus_builder/findings/time_mention_validation_set_v1.json` (15 records, `expected_category=null`)

---

## Purpose

The validation-set is the second of two held-out evaluation surfaces required by Lesson 7. It carries the authoritative reliability claim for the v1.3 published baseline: it is read **exactly once** in Phase 5b (a separate chat session) where Jordan + Claude judge the 15 records blind and run `--validation` for a one-shot regression measurement.

The gate-set (Phase 4, 25 records) was sampled from the v1.3 hand-sample of the 10 locked episodes; mechanical-disjointness from calibration was `not_possible_documented` because v1.3 dedup renumbering preserves keys against the v2 calibration. The validation-set fixes this: it is mechanically excluded from the 10 hand-sample episodes — sampled from the 130 episodes that have never been touched by calibration, the boundary-stability dump, the D6 precision dump, or the gate-set construction.

This is **fresh blind data**. The reliability claim derived from Phase 5b's --validation pass should generalize farther than the gate-set's claim.

---

## Method

### Source pool

Full-parse output at `corpus_builder/output/time_mention/` (140 episode JSONs). Excluded the 10 hand-sample episodes:

```
C1E003, C1E024, C1E047, C1E057, C1E085,
C1E101, C2E002, C2E018, C2E024, C2E031
```

Remaining pool: **3,358 records across 130 episodes.**

### Stratification

Targets locked by Phase 5 prompt:

| Stratum | Target | Available | Sampled |
|---|---:|---:|---:|
| `cumulative_anchor` | 5 | 334 | 5 |
| `scene_transition` | 4 | 590 | 4 |
| `in_scene_compression` | 2 | 263 | 2 |
| `travel_duration` | 1 | 203 | 1 |
| `unknown_shape: true` | 3 | 1,968 | 3 |
| **Total** | **15** | **3,358** | **15** |

All strata met target without inflation. No bucket required substitution.

### Random seed

`random.seed(9999)`. Determinism is recoverable: re-running the build script with the same seed against the same `output/time_mention/` directory will reproduce the same 15-record sample.

### Exclusion verification

- **Hand-sample episode exclusion:** verified mechanically. Source pool was constructed by skipping any per-episode JSON whose stem matches the 10-episode list. Post-sample audit confirms `hand_sample_overlap_count = 0`.
- **Calibration overlap:** `calibration_overlap_count = 0` by construction. The v2 calibration (`time_mention_eval_set_v2.json`) covers only records from the 10 hand-sample episodes; excluding those episodes from the source pool guarantees no `(trigger_id, same_turn_record_index)` overlap with calibration.
- **Gate-set overlap:** `gate_holdout` (Phase 4) was sampled from the same 10 hand-sample episodes, so excluding those episodes also disjoints from the gate-set.

---

## Episode coverage

15 distinct episodes across both campaigns:

```
C1: E016, E027, E028, E037, E038, E043, E054, E055, E091, E094, E099, E110, E113
C2: E005, E040
```

13 of 15 are C1, 2 of 15 are C2. The C1 skew tracks the corpus's 94/46 episode split (~67% C1) and the random sample's natural distribution.

---

## Sampled records (categories + trigger phrases)

For Phase 5b reference; `raw_text` stripped from the JSON to enforce blind judging.

| Stratum | trigger_id | idx | trigger_phrase |
|---|---|---:|---|
| cumulative_anchor | C1E037_t59 | 2 | `a few days` |
| cumulative_anchor | C1E043_t1395 | 0 | `A few hours` |
| cumulative_anchor | C1E027_t626 | 0 | `It's been` |
| cumulative_anchor | C1E038_t497 | 0 | `in the morning` |
| cumulative_anchor | C1E054_t1345 | 0 | `in the morning` |
| scene_transition | C1E094_t2747 | 1 | `two weeks` |
| scene_transition | C1E055_t928 | 0 | `a short rest` |
| scene_transition | C1E099_t357 | 0 | `later in` |
| scene_transition | C2E040_t1673 | 0 | `a long rest` |
| in_scene_compression | C1E091_t1884 | 0 | `over the next` |
| in_scene_compression | C1E028_t2276 | 0 | `an hour` |
| travel_duration | C2E005_t301 | 0 | `an hour` |
| unknown_shape | C1E113_t3139 | 0 | `it's now` |
| unknown_shape | C1E016_t274 | 0 | `ten minutes` |
| unknown_shape | C1E110_t1475 | 0 | `one round` |

---

## Mechanical-enforcement contract for Phase 5b

The validation-set JSON has `expected_category=null`, `verdict=null`, `failure_mode=null`, `judged_at=null` for all 15 records. The test runner's `--validation` mode must error cleanly until those fields are populated; the runner is shared with the calibration / gate-set surfaces and uses the `--validation` flag as the gate. The runner re-hydrates `raw_text` from CRD3 source at runtime — the JSON itself never carries text.

Phase 5b protocol (separate chat session):
1. Jordan + Claude read each record's `raw_text` (hydrated by the runner) and judge `expected_category`, `verdict`, `failure_mode`.
2. Save the judged JSON.
3. Run `--validation` exactly once. Record the precision / FP rate / dup rate / regression numbers.
4. Append the run results to `findings/time_mention_session_log.md` (Phase 5b entry).

The validation regression is the authoritative published-claim measurement for v1.3. Re-running it after that is a methodology violation (Lesson 7).
