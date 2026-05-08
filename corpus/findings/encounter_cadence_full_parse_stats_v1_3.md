# Encounter Cadence v1.3 — Full Parse Stats

**Run date:** 2026-05-05
**Extractor version:** `encounter_cadence_v1_3`
**Source:** CRD3 `c=2` alignment dir (140 unique episodes, 280 source files)
**Output dir:** `output/encounter_cadence/` — 140 per-episode JSON files
**v1.2 output preserved at:** `output/encounter_cadence_v1_2/` (186 records)
**v1.1 output preserved at:** `output/encounter_cadence_v1_1/` (243 records)
**Eval set:** `findings/encounter_cadence_eval_set_v3.json` (84 calibration + 25 holdout)
**Validation:** `findings/encounter_cadence_validation_v1_3.md`

---

## Ship gates (held-out 25-record set, one-shot measurement)

| Gate | Threshold | v1.3 | Status |
|---|---:|---:|---|
| 1. FP rate | ≤ 8% | **0.0%** (0 / 34) | PASS |
| 2. Wave detection | ≥ 50% | **50.0%** (4 / 8) | PASS |
| 3. Strict precision | ≥ 50% | **56.0%** (14 / 25) | PASS |
| 4. No-regression on v2 subset (precision ≥ 65%, wave ≥ 60%, FP ≤ 5%) | — | 72.7% / 80% / 1.4% | PASS |

---

## Volume comparison (v1.1 → v1.2 → v1.3)

| Metric | v1.1 | v1.2 | v1.3 |
|---|---:|---:|---:|
| Total records | 243 | 186 | **170** |
| C1 records | 163 | 110 | 103 |
| C2 records | 80 | 76 | 67 |
| Episodes with zero records | 30 | 41 | 46 |
| Records per episode (median) | 1 | 1 | 1 |
| Records per episode (max) | 7 | 5 | 5 |

The v1.2 → v1.3 net drop (16 records) is the discourse-layer filter at work: 16 records that v1.2 emitted are now correctly identified as episode-break recap, init-order narration, or other discourse-shape false positives.

---

## Category distribution

| Category | v1.1 | v1.2 | v1.3 | Δ vs v1.2 |
|---|---:|---:|---:|---:|
| `interruption` | 148 (60.9%) | 82 (44.1%) | 70 (41.2%) | −12 |
| `npc_turns_hostile` | 33 (13.6%) | 35 (18.8%) | 32 (18.8%) | −3 |
| `wave_or_phase_shift` | 10 (4.1%) | 26 (14.0%) | 28 (16.5%) | +2 |
| `player_action_escalation` | 28 (11.5%) | 25 (13.4%) | 24 (14.1%) | −1 |
| `environmental_materialization` | 22 (9.1%) | 17 (9.1%) | 15 (8.8%) | −2 |
| `trap_activation` | 2 (0.8%) | 1 (0.5%) | 1 (0.6%) | 0 |

`interruption` dropped because ~12 records that v1.2 defaulted to interruption are now either (a) filtered as DISCOURSE (the 3 phase4-shape FPs in calibration plus equivalent shapes in the rest of the corpus) or (b) reclassified as wave because Stage 0 STATE forced `combat_active=True`.

`wave_or_phase_shift` rose by 2 — one more `phase_shift` and the same `party_join`/`reinforcement` counts. The STATE-forced combat_active boost is moving borderline records from interruption to wave, but the impact in absolute terms is modest because most wave records already triggered via literal patterns or the existing damage-resolution heuristic.

---

## Wave subtype distribution

| Subtype | v1.1 | v1.2 | v1.3 |
|---|---:|---:|---:|
| `phase_shift` | 5 | 20 | 22 |
| `party_join` | 2 | 5 | 5 |
| `reinforcement` | 3 | 1 | 1 |

---

## Boolean field splits

| Field | v1.2 True/False | v1.3 True/False |
|---|---|---|
| `is_fresh_encounter` | 160 / 26 | 142 / 28 |
| `player_action_caused` | 30 / 156 | 29 / 141 |

---

## Numeric field distributions

| Field | Min | Median | Max | Mean |
|---|---:|---:|---:|---:|
| `narration_buildup_chars` | 60 | ~810 | 1420 | ~800 |
| `preceding_context_chars` | ~200 | ~1450 | 1500 | ~1325 |
| `episode_position_pct` | 0.007 | ~0.44 | 0.97 | — |
| `nearest_prior_trigger_turn_distance` | 2 | ~140 | 2116 | — |

76 of 170 records (45%) have a non-null `nearest_prior_trigger_turn_distance` — i.e., they're not the first init record in their episode.

---

## Stage 0 filtering activity

The `[FILTERED_DISCOURSE]` log line fired for every Stage-0-rejected candidate. In the eval set:
- 3 phase4 calibration discourse records filtered (5K arrival ad, welcome-back recap, init-order narration)
- 3 held-out discourse records filtered (`fp_summon_init_order`, `fp_meta_reroll_discussion`, `fp_init_order_recount`)

Across the full 140-episode corpus, 16 v1.2 records were dropped by v1.3. The exact split between "filtered as DISCOURSE" vs "reclassified" requires a v1.2-vs-v1.3 record-id diff, which is not in this stats summary.

---

## Zero-record episodes (46)

5 new vs v1.2: episodes where v1.2 was emitting only discourse-shape FPs (e.g., post-break narration where Matt says "What did you roll for initiative?" mid-combat). Verified manually for the held-out FPs (C2E043 = init-order narration, C1E054 = meta-reroll discussion, C1E040 = summon init-order — Stage 0 caught all three).

---

## What v1.3 still misses

The 11 calibration failures (excluding v1's known C2E045_t2529) and 11 held-out failures cluster as:

- **Wave records without prior-episode init AND without literal wave phrasing or strong damage signal in last 3 MATT turns** — same family v1.2 missed: combat in progress without v1's Stage 1 catching the prior init. Held-out: H07, H10, H11, H21.
- **NPC-turns-hostile cases requiring deep contextual reasoning** — banshee approaches, guards waiting in formation, etc. Held-out: H01, H08, H19, H25.
- **Environmental materialization with thin narration buildup** — Held-out: H02, H13, H24.
- **Player-action-escalation requiring third-person action detection** — held-out H05.

These are the same recall-territory failures noted in the v1.2 validation. The Stage 0 architecture addressed FP precision but the recall floor on these specific shapes is bounded by the existing patterns.

---

## What this report does NOT do

This is descriptive stats + ship-gate measurement. The full findings doc — what does the cadence data imply for Track 4 specs? — is Jordan's read, written separately at `findings/encounter_cadence_findings.md` (not yet started).

The held-out set is now consumed. Any v1.4 calibration would need a new held-out sample.
