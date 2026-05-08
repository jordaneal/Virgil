# Encounter Cadence v1.2 — Calibration Validation Report

**Run date:** 2026-05-05
**Extractor version:** `encounter_cadence_v1_2`
**Eval set:** `findings/encounter_cadence_eval_set_v2.json` (69 records: 14 v1 + 31 spot-check + 24 blind)
**Regression test:** `extractors/test_encounter_cadence_eval_v2.py`
**Sample output (v1.2):** `samples/encounter_cadence_sample_v1_2.json`
**Sample output (v1.1, preserved):** `samples/encounter_cadence_sample_v1_1.json`
**`[EXTRACTOR_UNKNOWN]` count:** 0

---

## 1. Headline result

All three ship gates pass.

| Gate | Threshold | v1.1 (on v2 eval set) | v1.2 | Status |
|---|---:|---:|---:|---|
| FP rate | ≤ 5% | 11.9% | **1.4%** | PASS |
| Wave detection rate | ≥ 60% | 0.0% | **60.0%** (6 / 10) | PASS |
| Overall precision | ≥ 65% | 29.1% (16 / 55) | **70.9%** (39 / 55) | PASS |

v1 sanity: **13/14 = 92.9%** — unchanged from v1.1's baseline. The only failing v1 record (C2E045_t2529) was already a known v1.1 limitation; it now misclassifies as `wave_or_phase_shift` instead of `player_action_escalation`, but both are wrong relative to the expected `npc_turns_hostile`. Net v1 precision unchanged.

---

## 2. Eval set v2 construction

Built by `extractors/build_eval_set_v2.py` from Jordan's construction notes (`eval_set_v2_construction.md`). Total 69 records:

- **14 v1 records** carried forward from `encounter_cadence_eval_set_v1.json` with raw_text and v1.1 classification fields backfilled from `output/encounter_cadence_v1_1/`.
- **31 spot-check records** — Jordan-curated verdicts on records v1.1's full parse emitted across 27 episodes. Six are sentinel `NOT_INIT_EVENT` (records v1.1 falsely emitted), one is sentinel `DUPLICATE` (C1E031_t152).
- **24 blind sample records** — random.seed=42 sample over records v1.1 emitted in episodes Jordan hadn't manually reviewed. Six are sentinel `NOT_INIT_EVENT`.

The construction notes' "~26 spot-check" estimate was off by five — the actual table has 31 unique-vs-v1 entries. Doesn't affect the gates: gates apply to non-v1 records (55 in this v2 eval set), not to a fixed denominator.

DEFENSIBLE map: 5 records have explicit alternate-acceptable categories (the test passes if classified as any of them). Most notable: C1E044_t378's expected_category in the construction notes is `environmental_materialization`, but inspecting the source episode, the trigger turn says "I need you to roll an insight check" — there is no actual init event. Patch 7 correctly filters it; eval test accepts either label.

---

## 3. Patch-by-patch effect on the eval set

| Patch | Records targeted | Outcome on the 55-record non-v1 set |
|---|---|---|
| 7 — Stage 1 FP gating | 12 NOT_INIT_EVENT records v1.1 emitted as false positives | 11 of 12 filtered. C1E033_t851 leaks (literal "everyone else roll initiative" in source). FP rate 11.9% → 1.4%. |
| 8 — Wave persistence + semantic | 10 wave records on the 50 non-v1 set | 6 of 10 caught. Wave rate 0% → 60%. Misses are: C1E002_t1499, C1E113_t1352, C1E071_t1554 (no prior init in episode, so init_active=False), C1E086_t1234 (post-break narration triggers scene_transition override). |
| 9 — `player_action_escalation` widening | C1E029_t1587 explicitly; physical-consequence pattern catches kick-the-door cases | C1E029_t1587 fixed via player-action-then-MATT-physical-consequence pattern. C1E111_t1707, C2E003_t1875, C2E025_t1023 still miss (action verb out-of-window or non-"I"-prefix). |
| 10 — `npc_turns_hostile` widening | 7 npc records misclassified as interruption | C1E102_t1440 (transformation reveal — flesh pulled tight), C2E042_t251 (NPC dialogue + dive), C1E022_t1709 (figures step out), C1E019_t851 (existing NPC dialogue, picked up via trigger-text check) all fixed. |
| 11 — `nearest_prior_trigger_turn_distance` metadata | 1 DUPLICATE record (C1E031_t152) | Field populated for 87 of 186 full-parse records (47%). C1E031_t152's distance = 8, well within the 30-turn dup-detection threshold. |

---

## 4. Per-record verdict (v1.2)

Verbose run output saved with the test runner. Summary:

- **v1 (14 records):** 13 OK, 1 FAIL (C2E045_t2529 — same as v1.1).
- **spotcheck (31 records):** 20 OK, 11 FAIL.
- **blind (24 records):** 19 OK, 5 FAIL.

OK includes the four "filtered (defensible)" / "filtered (correct)" cases where Stage 1 reject is acceptable. The single emitted FP (C1E033_t851) is the lone Stage-1 leak.

---

## 5. Known v1.2 limitations (filed for review, not addressed)

Per the Phase 4 prompt's stop-and-report-on-gate-failure rule, the gates pass and v1.2 ships. These are the failures left on the table:

1. **C2E045_t2529 (v1):** dragon reveal mid-negotiation. Now classifies as wave (was player_action_escalation in v1.1). Both wrong relative to expected `npc_turns_hostile`. The transformation-reveal vocab from patch 6 doesn't catch "rears up, wings up in the air" without a quoted threat. Filed.

2. **Wave records without prior-episode init AND without literal wave phrasing (4):** C1E002_t1499, C1E113_t1352, C1E071_t1554, C1E086_t1234. Patch 8's fallback requires `init_active=True`, which depends on Stage 1 catching a prior init. In episodes where Matt called init mid-narration without setup (C1E002 t1499), Stage 1 has nothing to anchor on. Recall-audit territory.

3. **Player-action records requiring third-person action detection (3):** C2E003_t1875, C2E025_t1023, C1E111_t1707. PLAYER_ACTION_VERBS requires `\bI|we\b` prefix. Cases like "Jester is going to cast" or "Beau is going to take out" don't match. Loosening the regex would over-fire; better to detect via a player-name+verb pattern in a future patch.

4. **NPC-turns-hostile cases requiring contextual reasoning (4):** C1E029_t448 (banshee — pre-trigger MATT narration is OOC banter, not the banshee), C1E031_t144 (guards waiting pattern but trigger is bare), C1E027_t83 (invisible attacker via choking sounds), C2E044_t1757 (sighting + scrambling away).

5. **C1E031_t686:** trigger contains massive damage narration ("31 points of piercing damage") and init_active=True from t144. Patch 8 fallback fires → wave, but expected `npc_turns_hostile`. Pre-init damage narration is structurally indistinguishable from mid-combat damage narration in this case.

6. **C2E026_t2875, C1E094_t2221:** category mis-assignment between player_action_escalation and npc_turns_hostile.

7. **C1E039_t79:** env_materialization expected, got interruption. narration_buildup probably below the 500-char threshold despite the trigger being a clear environmental ambush ("It bursts out of the surface, I need you all to roll initiative").

8. **C1E033_t851:** the surviving FP. Trigger contains literal "Everyone else roll initiative" but Jordan labels it NOT_INIT_EVENT (movement+dash narration that incidentally says "roll initiative"). The text alone supports either reading; eval has it in DEFENSIBLE alternates {NOT_INIT_EVENT, wave_or_phase_shift} so a wave classification would also pass.

---

## 6. Field schema additions (v1.2 vs v1.1)

New field: `nearest_prior_trigger_turn_distance` — integer (turn-number gap to the previous emitted record in this episode) or null (first record). Patch 11.

All other fields unchanged. Output records remain idempotent on event content (verified via re-running `--sample` and diffing).

---

## 7. Acceptance criteria check

| Criterion | Status |
|---|---|
| All three ship gates pass on eval set v2's non-v1 records | ✓ |
| No regression on v1's 14 records (≥ 13/14) | ✓ (13/14, same baseline) |
| v1.2 `--full` output written to `output/encounter_cadence/` | ✓ (186 records) |
| v1.1 `--full` output preserved at `output/encounter_cadence_v1_1/` | ✓ (243 records) |
| Stats file at `findings/encounter_cadence_full_parse_stats_v1_2.md` | ✓ |
| `nearest_prior_trigger_turn_distance` field populated | ✓ (87 of 186 records non-null) |
| `[FILTERED_NON_INIT]` log line added for Stage-1 rejections matching FP shapes | ✓ |
