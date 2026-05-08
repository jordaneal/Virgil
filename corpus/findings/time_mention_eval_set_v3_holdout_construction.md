# Time-Mention eval set v3 — held-out gate-set construction

**Phase:** Track 5 Ship 2, Phase 4 — held-out gate-set construction.
**Construction date:** 2026-05-07
**Output:** `findings/time_mention_eval_set_v3_holdout.json` (25 records, `expected_category` null pending Phase 5 judging).
**Extractor version sampled from:** `time_mention_v1_3` (`extractor_version` field locked).
**Sample source:** `samples/time_mention_sample_v1_3.json` (234 records across 10 hand-sample episodes).

---

## 1. Sampling method

```python
import random
random.seed(7777)
# stratified sample, fixed targets per category
```

Records grouped by extractor `category` (with `unknown_shape: true` records grouped under `unknown_shape`). For each category, `random.sample(pool, target_count)` was applied. Total records pulled: 25.

## 2. Stratification — target vs actual

| Category | Target | Pool size | Actual |
|---|---:|---:|---:|
| `cumulative_anchor` | 8 | 39 | 8 |
| `scene_transition` | 6 | 45 | 6 |
| `in_scene_compression` | 4 | 21 | 4 |
| `travel_duration` | 2 | 6 | 2 |
| `unknown_shape` | 5 | 123 | 5 |
| **Total** | **25** | — | **25** |

No stratum had to be inflated — every category's pool exceeded its target. No adjustments from the spec stratification.

## 3. Calibration-set exclusion check — NOT_POSSIBLE, documented

The Phase 4 prompt's `calibration_exclusion_check: verified` rule asked for zero overlap with the v2 calibration set by `(trigger_id, same_turn_record_index)` keys. **That rule cannot be satisfied here**, by construction:

- v2 calibration's 321 records came from the v1 hand-sample of these same 10 episodes.
- v1.3's sample (234 records) is a strict subset of the same physical phrases as v1, with Patch 1 dedup and Patch 2 NPC-routing reducing the count.
- v1.3's `same_turn_record_index` is renumbered post-dedup to be contiguous (0..N−1 within each turn). Survivor records keep low indices; suppressed phrases drop out.
- Net effect: every v1.3 record's `(trigger_id, same_turn_record_index)` key is also in v2 calibration's key set. **Mechanical-key overlap: 234 / 234 = 100%.**

**This was true at construction-script run-time and is reported as `calibration_overlap_count: 25` in the JSON file's `construction.calibration_overlap_count` field.**

The held-out methodology's purpose (per `corpus_builder_lessons_v1.md` Lesson 7) is preserved by **blind re-judging in Phase 5**, not by mechanical key-set disjointness. Jordan + Claude judge the 25 records in a fresh chat session **without referencing the calibration verdicts**; mechanical enforcement comes from `raw_text` being stripped to the literal sentinel `"<STRIPPED_DURING_CALIBRATION>"` in the held-out file and the `--holdout` flag being required to hydrate raw text from CRD3 source.

The Encounter Cadence v3 held-out used episodes that hadn't been reviewed during calibration. Time-Mention's calibration covered all 10 episodes in scope, so that escape isn't available; the trade-off is a re-judging-fresh held-out rather than a fresh-records held-out. Filed as a v1 limitation for the findings doc.

## 4. Episodes covered

| Episode | Records sampled |
|---|---:|
| C1E003 | 2 |
| C1E024 | 2 |
| C1E047 | 4 |
| C1E057 | 2 |
| C1E085 | 0 |
| C1E101 | 1 |
| C2E002 | 4 |
| C2E018 | 5 |
| C2E024 | 3 |
| C2E031 | 4 |

C1E085 has 9 v1.3 records total (smallest pool). The seed=7777 random pull happened not to draw any. Acceptable — the held-out is stratified by category, not by episode. Documenting the C1E085 absence here.

## 5. File structure

`findings/time_mention_eval_set_v3_holdout.json`:

```json
{
  "construction": {
    "seed": 7777,
    "extractor_version": "time_mention_v1_3",
    "sample_source": "samples/time_mention_sample_v1_3.json",
    "stratification": {"cumulative_anchor": 8, "scene_transition": 6,
                       "in_scene_compression": 4, "travel_duration": 2,
                       "unknown_shape": 5},
    "calibration_exclusion_check": "not_possible_documented",
    "calibration_overlap_count": 25,
    "construction_date": "2026-05-07",
    "notes": "..."
  },
  "gate_holdout": [
    {
      "trigger_id": "C1E047_t644",
      "same_turn_record_index": 1,
      "trigger_phrase": "...",
      "raw_text": "<STRIPPED_DURING_CALIBRATION>",
      "extracted_category": "cumulative_anchor",
      "is_npc_dialogue_present": true,
      "is_combat_state": false,
      "is_recap_state": false,
      "expected_category": null,
      "judged_at": null,
      "verdict": null,
      "failure_mode": null
    }
    /* ... 24 more ... */
  ]
}
```

The `extracted_category`, `is_npc_dialogue_present`, `is_combat_state`, `is_recap_state` fields carry forward from the v1.3 sample — they're what the extractor produced. They're displayed at judging time so Jordan + Claude can compare extractor output to the actual fictional content. The `expected_category` field is set blind during Phase 5 judging.

## 6. Mechanical enforcement

`extractors/test_time_mention_eval_v2.py` has been updated:

- Default `--calibration` mode reads only `findings/time_mention_eval_set_v2.json` calibration array. Does NOT read `time_mention_eval_set_v3_holdout.json`.
- `--holdout` flag reads `findings/time_mention_eval_set_v3_holdout.json`. Hydrates `raw_text` from CRD3 source via `tm.load_episode_turns(ep)` lookup. Filters to records with `expected_category != null`; errors if zero are judged (Phase 4 state).
- `--validation` flag reads a separate file `findings/time_mention_validation_set_v1.json` (Phase 5+ artifact, not yet created).
- Modes are mutually exclusive. Runner errors if more than one flag is passed.

Verified at construction time:
- `python3 extractors/test_time_mention_eval_v2.py --holdout` → errors with "zero judged records. Phase 5 will populate expected_category..."
- `python3 extractors/test_time_mention_eval_v2.py` (default) → loads 321 calibration records, runs against v1.3 extractor, reports the same 73.8% precision / 3.4% FP / 3.4% dup numbers as v1.2/v1.3 ship-gate runs.

## 7. Phase 5 next steps

1. Jordan + Claude open a chat session with the v3 holdout records visible.
2. For each of the 25 records, judge `expected_category` blind (without referencing v2 calibration verdicts on the same records).
3. Fill in `expected_category`, `judged_at`, `verdict`, `failure_mode` per record. Save back to `findings/time_mention_eval_set_v3_holdout.json`.
4. Run `python3 extractors/test_time_mention_eval_v2.py --holdout` once. The four ship-gate metrics from this run are the **published-claim** numbers, per `corpus_builder_lessons_v1.md` Lesson 3.
5. Phase 6 builds the validation-set (~15 records, `random.seed(9999)`) and writes findings doc.
