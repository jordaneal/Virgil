# Encounter Cadence v1.3 — Calibration Validation Report

**Run date:** 2026-05-05
**Extractor version:** `encounter_cadence_v1_3`
**Eval set:** `findings/encounter_cadence_eval_set_v3.json` (84 calibration + 25 holdout)
**Regression test:** `extractors/test_encounter_cadence_eval_v3.py`
**Sample output (v1.3):** `samples/encounter_cadence_sample_v1_3.json`
**Sample outputs preserved:** `samples/encounter_cadence_sample_v1_1.json`, `samples/encounter_cadence_sample_v1_2.json`
**`[EXTRACTOR_UNKNOWN]` count:** 0

---

## 1. Headline result — all four hard ship gates pass on the held-out set

| Gate | Threshold | v1.2 (baseline) | v1.3 | Status |
|---|---:|---:|---:|---|
| 1. Held-out FP rate | ≤ 8% | ~12% | **0.0%** (0 / 34 emitted) | PASS |
| 2. Held-out wave rate | ≥ 50% | 50% (4/8) | **50.0%** (4 / 8) | PASS |
| 3. Held-out precision | ≥ 50% | 36% | **56.0%** (14 / 25) | PASS |
| 4. No regression on v2 calibration metrics (precision ≥ 65%, wave ≥ 60%, FP ≤ 5%) | — | — | **72.7% / 80% / 1.4%** | PASS |

The architectural change (Stage 0 discourse layer) caught the three discourse-shape FPs that the construction notes flagged (`fp_summon_init_order`, `fp_meta_reroll_discussion`, `fp_init_order_recount`) plus all three calibration phase4 discourse FPs (`5K arrival from last week`, episode recap intro, mid-combat init-order narration). Held-out FP rate dropped from baseline ~12% to 0%.

---

## 2. Eval set v3 construction

Built by `extractors/build_eval_set_v3.py` from:
- v2 records carried forward (14 v1 + 31 spotcheck + 24 blind = 69)
- 15 phase4_blind records (Jordan's end-of-Phase-4 fresh-blind sample, including 3 NOT_INIT_EVENT discourse-shape FPs)
- 25 holdout records (`random.seed(7777)` over Jordan-unreviewed episodes — `eval_set_v3_holdout_construction.md`)

Methodology rule baked into the JSON structure: holdout records have NO `raw_text` field, only `trigger_id`, episode metadata, and expected category. The regression test pulls live records from the extractor at run time. The default test mode (calibration only) does not even read the holdout split. Use `--holdout` only after calibration regression passes.

`DEFENSIBLE` map extended for phase4_blind records Jordan flagged as defensible at construction time (C1E037_t2049, C1E052_t106, C1E016_t1738, C2E034_t2173) and for two holdout records flagged defensible (C2E006_t1872, C2E021_t1369).

---

## 3. Architectural change — Stage 0 discourse layer

v1.2's diagnosis (from external review): the extractor was treating `initiative-language` as a proxy for `initiative-event`. Three FP families slipped through:
- **Discourse-about-initiative** (episode-break ads, recap intros, "what did you roll?" narration)
- **Mechanical-roll-not-event** (summon init for ordering, "you can reroll initiative if you want")
- **Combat-state-cross-window-loss** (wave events where combat-active was true >30 turns earlier)

v1.3 adds Stage 0 between candidate detection and Stage 1 classification. It assigns each candidate one of three labels:

- **DISCOURSE** — meta-narration ABOUT initiative rather than triggering it. **Reject** the candidate; emit `[FILTERED_DISCOURSE]` log line.
- **STATE** — mid-combat-state narration (damage rolls, turn-order narration, hits/misses) in the last 5 turns. Continue to Stage 1 with `force_combat_active=True`. This forces the wave classification gate to fire even when the existing `init_active AND damage` heuristic misses (the cross-window-loss case).
- **EVENT** — default. Continue to Stage 1 with normal `combat_active` calculation.

**DISCOURSE detection:**
- `DISCOURSE_EPISODE_BREAK` — `welcome back`, `last we left off`, `previously on`, `that does it for us`, `we'll be right back`, `[break]`, `[BREAK]`, `\d+K arrival`, `last week's`, `available for one more day`, `comic available`, etc. Checked in trigger and last 3 turns.
- `DISCOURSE_INIT_RECOUNT` — `what did you roll for initiative`, `pre-rolled initiative`, `can I reroll initiative`, `initiative count \d+`, `who's next in initiative`, `roll initiative for [it/him/...] separately/as part of`, etc. Checked in trigger only.

**STATE detection:**
- `STATE_DAMAGE` — `\d+ points of [type] damage` in last 5 turns
- `STATE_TURN_ORDER` — `your turn`, `top of the round`, `that ends [name]'s turn`, `back to you`
- `STATE_COMBAT_ROLLS` — `\d+ to hit`, `that hits`, `make a saving throw`, `roll for damage`

The summon-init filter described in the prompt was NOT implemented in v1.3. Reasoning: the calibration v2 record C2E045_t2568 (`Roll initiative for the elemental` — wave/reinforcement) has the same surface shape as the held-out `fp_summon_init_order` record (H04). A summon-init filter that catches the FP would also kill the calibration wave catch, regressing Gate 4. Stage 0's other patterns caught the three discourse FPs without needing the summon filter; Gate 1 passes at 0% with margin. Filed as a v1.4 consideration if/when more held-out data shows summon-init FPs distinguishable from wave/reinforcement.

---

## 4. Calibration metrics (84 records)

| Subset | Records | Precision | Wave rate | FP rate |
|---|---:|---:|---:|---:|
| Overall | 84 | 76.2% | 13/17 = 76.5% | 1/103 = 1.0% |
| v1 | 14 | 13/14 = 92.9% | 4/4 = 100% | 0/14 = 0.0% |
| spotcheck | 31 | 22/31 = 71.0% | 4/5 = 80.0% | 1/40 = 2.5% |
| blind (v2) | 24 | 18/24 = 75.0% | 4/5 = 80.0% | 0/31 = 0.0% |
| phase4_blind | 15 | 11/15 = 73.3% | 1/3 = 33.3% | 0/18 = 0.0% |
| **v2 subset (Gate 4)** | **55** | **40/55 = 72.7%** | **8/10 = 80.0%** | **1/71 = 1.4%** |

Comparing v2 subset before/after Stage 0:
- Precision **70.9% → 72.7%** (+1.8 pp)
- Wave rate **60.0% → 80.0%** (+20 pp — STATE-forced combat_active picked up two waves the heuristic missed)
- FP rate **1.4% → 1.4%** (no change — the lone surviving FP C1E033_t851 has literal "Everyone else roll initiative" embedded in mid-combat narration)

phase4_blind precision 53.3% → 73.3%, FP 12.5% → 0%. All three phase4 discourse FPs filtered:
- C1E018_t1160 (5K arrival ad) → `[FILTERED_DISCOURSE] episode_break in trigger: '5K arrival'`
- C2E013_t21 (welcome back / comic plug) → `[FILTERED_DISCOURSE] episode_break in trigger: 'welcome back'`
- C2E032_t1720 (mid-combat init-order narration) → `[FILTERED_DISCOURSE] init_recount in trigger: 'what did you roll for initiative'`

---

## 5. Held-out metrics (25 records — measured ONCE)

| Metric | Value | Gate | Status |
|---|---:|---:|---|
| Records emitted on held-out episodes | 34 | — | — |
| Strict precision | 14/25 = 56.0% | ≥ 50% | PASS |
| Wave detection | 4/8 = 50.0% | ≥ 50% | PASS |
| FP rate | 0/34 = 0.0% | ≤ 8% | PASS |

All three held-out NOT_INIT_EVENT records (H04, H06, H15) filtered as DISCOURSE. The four wave records caught: H09, H14, H17, H22. The four wave records missed: H07 (C1E006), H10/H11 (C2E006), H21 (C2E021) — three of these were already in v1.2's preserved output but classified as `interruption`; H21 has DEFENSIBLE alternate {wave, interruption} but didn't pass either way.

---

## 6. Field schema additions (v1.3 vs v1.2)

No new fields. The `[FILTERED_DISCOURSE]` log line is the new diagnostic surface; it's stderr-only and doesn't appear in records (filtered candidates produce no record).

All other fields unchanged from v1.2. Output records remain idempotent on event content.

---

## 7. Acceptance criteria check

| Criterion | Status |
|---|---|
| All four held-out ship gates pass | ✓ |
| No regression on v1.2 calibration v2-subset metrics | ✓ (precision 70.9% → 72.7%, wave 60% → 80%, FP 1.4% → 1.4%) |
| v1.3 `--full` output written to `output/encounter_cadence/` | ✓ (170 records) |
| v1.2 `--full` output preserved at `output/encounter_cadence_v1_2/` | ✓ (186 records) |
| Stats file at `findings/encounter_cadence_full_parse_stats_v1_3.md` | ✓ |
| Stage 0 catches calibration phase4 discourse records | ✓ (3/3 filtered) |
| Stage 0 catches held-out discourse records | ✓ (3/3 filtered, FP rate 0%) |

---

## 8. What this report does NOT do

This is calibration + ship-gate validation. The full findings doc — interpretation of the v1.3 output, what cadence trends emerge, what Track 4 specs benefit — is Jordan's read, written separately at `findings/encounter_cadence_findings.md` (not yet started).

The held-out set is now consumed (one-shot measurement). Any future v1.4 calibration would need a new held-out sample.
