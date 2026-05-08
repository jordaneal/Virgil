# Encounter Cadence v1.2 — Full Parse Stats

**Run date:** 2026-05-05
**Extractor version:** `encounter_cadence_v1_2`
**Source:** CRD3 `c=2` alignment dir (140 unique episodes, 280 source files)
**Output dir:** `output/encounter_cadence/` — 140 per-episode JSON files
**v1.1 output preserved at:** `output/encounter_cadence_v1_1/` (243 records, for comparison)
**Eval set:** `findings/encounter_cadence_eval_set_v2.json` (69 records: 14 v1 + 31 spot-check + 24 blind)
**Regression test:** `extractors/test_encounter_cadence_eval_v2.py`
**Sample output:** `samples/encounter_cadence_sample_v1_2.json` (v1.1 sample preserved at `samples/encounter_cadence_sample_v1_1.json`)

---

## Ship gates (computed on the 55 non-v1 eval-set records)

| Gate | Threshold | v1.1 | v1.2 | Status |
|---|---:|---:|---:|---|
| FP rate | ≤ 5% | 11.9% | **1.4%** (1 / 73 emitted) | PASS |
| Wave detection | ≥ 60% | 0.0% | **60.0%** (6 / 10) | PASS |
| Overall precision | ≥ 65% | 29.1% | **70.9%** (39 / 55) | PASS |

v1 sanity: **13/14 = 92.9%** (unchanged from v1.1 baseline; the one remaining v1 failure — C2E045_t2529 — was already a known limitation in v1.1).

---

## Volume comparison

| Metric | v1.1 | v1.2 | Delta |
|---|---:|---:|---:|
| Total records | 243 | 186 | −57 (−23.5%) |
| C1 records | 163 | 110 | −53 |
| C2 records | 80 | 76 | −4 |
| Episodes with zero records | 30 | 41 | +11 |
| Records per episode (median) | 1 | 1 | 0 |
| Records per episode (max) | 7 | 5 | −2 |

The 57-record net drop is dominated by patch 7 Stage-1 false-positive filtering. v1.1 emitted records on `roll a [save/check]` triggers; v1.2's tightened POSITIVE_INIT requires the literal word `initiative` adjacent to the verb. In the eval set, 12 records expected as `NOT_INIT_EVENT` were emitted by v1.1; v1.2 filters 11 of them (only C1E033_t851 leaks through, which has the literal phrase `everyone else roll initiative` and is genuinely ambiguous between phase_shift and false-positive — see eval-set construction notes).

---

## Category distribution

| Category | v1.1 | v1.2 | Delta |
|---|---:|---:|---:|
| `interruption` | 148 (60.9%) | 82 (44.1%) | −66 |
| `npc_turns_hostile` | 33 (13.6%) | 35 (18.8%) | +2 |
| `player_action_escalation` | 28 (11.5%) | 25 (13.4%) | −3 |
| `environmental_materialization` | 22 (9.1%) | 17 (9.1%) | −5 |
| `wave_or_phase_shift` | 10 (4.1%) | 26 (14.0%) | +16 |
| `trap_activation` | 2 (0.8%) | 1 (0.5%) | −1 |

The big shifts:
- **`interruption` dropped 66 records.** v1.1's default catch-all over-fired on FP-Stage-1-reject candidates and on records that v1.2 now classifies as wave (via patch 8) or `npc_turns_hostile` (via patch 10).
- **`wave_or_phase_shift` more than doubled (10 → 26).** Patch 8's combat_active fallback (init_active AND damage-resolution in last K MATT turns) catches subsequent inits within episodes that v1.1's literal-pattern-only detector missed.
- **`npc_turns_hostile` rose marginally (33 → 35).** Patch 10's ambush vocab + NPC-command + hostile-reveal patterns added two records on net.

## Wave subtype distribution (26 records vs v1.1's 10)

| Subtype | v1.1 | v1.2 |
|---|---:|---:|
| `phase_shift` | 5 | 20 |
| `party_join` | 2 | 5 |
| `reinforcement` | 3 | 1 |

`phase_shift` dominates because the patch 8 fallback defaults to `phase_shift` when no specific subtype matches. The drop in `reinforcement` (3 → 1) is unexpected and may be worth a recall audit — patch 8's tightened combat_active gate may be filtering some summon-language records that don't have damage in last 3 MATT turns.

---

## Boolean field splits

| Field | v1.1 True/False | v1.2 True/False |
|---|---|---|
| `is_fresh_encounter` | 233 / 10 | 160 / 26 |
| `player_action_caused` | 32 / 211 | 30 / 156 |

`is_fresh_encounter=True` dropped by 73 records — direct consequence of the 16-record wave reclassification plus the 57 filtered FPs.

---

## Numeric field distributions

| Field | Min | Median | Max | Mean |
|---|---:|---:|---:|---:|
| `narration_buildup_chars` | 62 | 823.5 | 1420 | 810 |
| `preceding_context_chars` | 198 | 1445.5 | 1500 | 1330 |
| `episode_position_pct` | 0.0067 | 0.4403 | 0.9688 | — |
| `nearest_prior_trigger_turn_distance` (patch 11) | 2 | 138 | 2116 | — |

87 of 186 records (47%) have a non-null `nearest_prior_trigger_turn_distance` — i.e., they're not the first init record in their episode. The min of 2 turns and median of 138 turns shows the back-to-back-init phenomenon is rare in absolute terms but real: 4 records have distance ≤ 10 turns, marking them as candidates for analysis-layer dedup (e.g., C1E031_t152 is 8 turns after t144 — a restated init request, not a separate encounter).

---

## Zero-record episodes (41)

C1E003, C1E014, C1E024, C1E036, C1E038, C1E044, C1E047, C1E053, C1E056, C1E057, C1E060, C1E064, C1E065, C1E072, C1E073, C1E075, C1E088, C1E089, C1E090, C1E091, C1E095, C1E096, C1E101, C1E103, C1E104, C1E106, C1E109, C1E112, C1E115, C2E002, C2E004, C2E008, C2E009, C2E011, C2E014, C2E024, C2E027, C2E030, C2E031, C2E033, C2E037

11 new zero-record episodes vs v1.1: C1E024, C1E044, C1E053, C1E072, C1E088, C1E089, C1E090, C1E103, C1E106, C1E109, C2E002, C2E024 — most of these were episodes where v1.1 emitted only false-positive records (downtime/RP-heavy sessions like C1E044 where v1.1 emitted 7 FPs on "roll a [save/check]" patterns). Verified manually for C1E044: that episode is a downtime / Vasselheim shopping session with no actual init events.

---

## What v1.2 still misses

The 16 non-v1 eval-set failures (= 39 correct / 55 attempted) cluster as:

- **Wave records without prior-episode init AND without explicit wave phrasing (4):** C1E002_t1499, C1E113_t1352, C1E071_t1554, C1E086_t1234. The patch 8 fallback requires `init_active=True` (a prior init in the episode), which v1.2's Stage 1 still doesn't catch in episodes where Matt called init mid-narration without setup.
- **NPC-turns-hostile cases requiring deep contextual reasoning (4):** C1E029_t448 (banshee approach, surface chatter), C1E031_t144 (guards waiting pattern but trigger is bare "In fact, roll initiative"), C1E027_t83 (invisible attacker via choking-sounds narration), C2E044_t1757 (NPC sighting + scrambling-away).
- **Player-action-escalation requiring detection of third-person action (3):** C2E003_t1875 (Marisha climbs wall), C2E025_t1023 (stealth setup), C1E111_t1707 (action verb >10 turns back).
- **Other miscellaneous (5):** C1E031_t686 (npc-turns-hostile mis-classified as wave because volley narration matches wave fallback), C2E026_t2875 (player-action mis-classified as npc), C1E094_t2221 (npc mis-classified as player-action), C1E039_t79 (env-materialization mis-classified as interruption — narration_buildup likely below threshold), C1E033_t851 (lone surviving FP).

These map cleanly to recall-audit territory: each one is a specific signal v1.2 doesn't model. They're filed for v1.3 if/when Jordan decides the marginal records are worth more patches. Per the prompt, v1.2 ships at gate-pass — no further patches without review.

---

## What this report does NOT do

This report is calibration validation + descriptive stats. The full findings doc — what does the cadence data imply for Track 4 specs? — is Jordan's read, written separately at `findings/encounter_cadence_findings.md` (not yet started).

The defensible-alternates handling in the eval-set test means a few records are accepted under either of two acceptable expected categories (C1E044_t378, C1E033_t851, C1E098_t1779, C1E094_t2221, C1E027_t83). These are explicit ambiguity calls flagged in `extractors/build_eval_set_v2.py`'s DEFENSIBLE map.
