# Encounter Cadence v1.1 — Full Parse Stats

**Run date:** 2026-05-05
**Extractor version:** `encounter_cadence_v1_1`
**Source:** CRD3 `c=2` alignment dir (140 unique episodes, 280 source files)
**Output dir:** `output/encounter_cadence/` — 140 per-episode JSON files
**Log:** `logs/encounter_cadence_full.log`
**Exit code:** 0
**`[EXTRACTOR_UNKNOWN]` count:** 0

Numbers only. Interpretation is Jordan's read.

---

## Volume

| Metric | Value |
|---|---:|
| Episodes processed | 140 |
| Output files emitted | 140 |
| Total records | 243 |
| C1 records | 163 |
| C2 records | 80 |
| Records per episode (min / median / max / mean) | 0 / 1 / 7 / 1.7 |
| Episodes with zero records | 30 |

**Zero-record episodes (30):**
C1E003, C1E014, C1E035, C1E036, C1E038, C1E047, C1E056, C1E057, C1E060, C1E064, C1E065, C1E073, C1E075, C1E091, C1E095, C1E096, C1E101, C1E104, C1E112, C1E115, C2E004, C2E008, C2E009, C2E011, C2E014, C2E027, C2E030, C2E031, C2E033, C2E037

---

## Category distribution

| Category | Count | % |
|---|---:|---:|
| `interruption` | 148 | 60.9% |
| `npc_turns_hostile` | 33 | 13.6% |
| `player_action_escalation` | 28 | 11.5% |
| `environmental_materialization` | 22 | 9.1% |
| `wave_or_phase_shift` | 10 | 4.1% |
| `trap_activation` | 2 | 0.8% |

---

## Wave subtype distribution (10 records)

| Subtype | Count |
|---|---:|
| `phase_shift` | 5 |
| `reinforcement` | 3 |
| `party_join` | 2 |

---

## Boolean field splits

| Field | True | False |
|---|---:|---:|
| `is_fresh_encounter` | 233 | 10 |
| `player_action_caused` | 32 | 211 |

---

## Numeric field distributions

| Field | Min | Median | Max | Mean |
|---|---:|---:|---:|---:|
| `narration_buildup_chars` | 62 | 803 | 1420 | 792 |
| `episode_position_pct` | 0.0067 | 0.4403 | 0.9688 | 0.4373 |
