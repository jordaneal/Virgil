# Time-Mention Extractor v1 — Validation Report

**Phase:** Track 5 Ship 2, Phase 2 — implementation + hand-sample.
**Extractor version:** `time_mention_v1`
**Hand-sample episodes (OQ7 lock):** C1E003, C1E024, C1E047, C1E057, C1E085, C1E101, C2E002, C2E018, C2E024, C2E031.
**Date:** 2026-05-06

---

## 1. Headline numbers

| Metric | Value |
|---|---:|
| Episodes processed | 10 |
| Total records emitted | 321 |
| Distinct trigger turns | 262 |
| Multi-mention turns (§11.6) | 45 (17.2%) |
| Multi-mention extra records | 59 |
| `[FILTERED_DISCOURSE]` count | 50 |
| `[UNKNOWN_SHAPE]` count | 78 (24.3% of emitted) |
| `[EXTRACTOR_UNKNOWN]` count | 0 |

No episode produced zero records — every locked-list episode emitted at least 8 time-mentions.

### Per-episode counts

| Episode | Records |
|---|---:|
| C1E003 | 13 |
| C1E024 | 66 |
| C1E047 | 34 |
| C1E057 | 26 |
| C1E085 | 10 |
| C1E101 | 20 |
| C2E002 | 21 |
| C2E018 | 43 |
| C2E024 | 48 |
| C2E031 | 40 |

C1E024 (Briarwoods arrival in Emon — long political/social scene) and C2E024 (Hupperdook fair downtime) carry heavy NPC dialogue load, which inflates record count under the OQ1 fallback (D6 demoted from reject to flag — see §5).

---

## 2. Category distribution

| Category | Count | % |
|---|---:|---:|
| `cumulative_anchor` | 125 | 38.9% |
| `scene_transition` | 71 | 22.1% |
| `in_scene_compression` | 31 | 9.7% |
| `travel_duration` | 16 | 5.0% |
| `UNKNOWN_SHAPE` (`unknown_shape: true`) | 78 | 24.3% |

Per Lesson 2, no default catchall — the UNKNOWN_SHAPE flag is its own measurable outcome and is not a sinkhole. §6 of this report enumerates and triages all 78 unknown-shape records.

---

## 3. Granularity bucket distribution

| Bucket | Count |
|---|---:|
| `days` | 94 |
| `unspecified` | 71 |
| `minutes` | 43 |
| `weeks` | 33 |
| `years` | 28 |
| `hours` | 24 |
| `months` | 18 |
| `rounds` | 10 |

`unspecified` is large (22%) because relative-reference phrases ("the next morning", "shortly after", "moments later") don't carry an explicit unit. That's expected.

`rounds` records (10) are real combat-mechanic time but `is_combat_state: false` for all of them — see §7 below for the OQ5 lookback-window limitation.

---

## 4. Flag distribution

| Flag | True | % |
|---|---:|---:|
| `is_anchored` | 16 | 5.0% |
| `is_combat_state` | 0 | 0.0% |
| `is_recap_state` | 21 | 6.5% |
| `is_npc_dialogue_present` | 171 | 53.3% |
| `unknown_shape` | 78 | 24.3% |

`is_combat_state` zero across the sample is suspicious — see §7. `is_npc_dialogue_present` at 53% reflects the OQ1 fallback (D6 flag, not reject) — see §5.

---

## 5. D-pattern reject counts (Stage 0)

| Pattern | Rejects |
|---|---:|
| D1 (production OOC + breaks + sponsor) | 28 |
| D2 (spell/rules duration) | 9 |
| D3 (DM table-talk minutes-band) | 1 |
| D7 (player-question pass-back) | 7 |
| D6 (NPC dialogue) | **0 — demoted to flag per OQ1 fallback** |
| **Total DISCOURSE rejects** | **50** |

### D6 fallback decision — OQ1 lock applied mid-Phase-2

Initial run rejected 148 candidate turns under D6 (NPC dialogue). A 25-record sampled spot-check (deterministic `random.seed(101)`) of those rejects estimated D6 reject precision at **~56-64%** (14/22 clear-correct, 8/22 clear-FP, 3/22 ambiguous). Per the OQ1 lock — "If precision <85%, switch to flag-rather-than-reject" — D6 was demoted to a flag (`is_npc_dialogue_present: true`) rather than a reject. Records flagged but not dropped.

This change re-baselined the calibration set from 150 records → 321 records (the +171 are turns containing NPC dialogue alongside time phrases). The boundary-stability and D6-precision review files (§9) carry the records Jordan needs to manually triage.

**Common D6-FP shape from the spot-check:** Matt narrates a real fiction-time phrase ("the better part of 15 minutes pass", "moments later", "since you first saw her") in a turn that ALSO contains a quoted NPC line. Turn-level reject loses the Matt-narration phrase. Phrase-span-aware D6 detection (only reject if the time phrase falls inside the quoted span) is a candidate v2 patch — filed in §10.

---

## 6. Unknown-shape records (78)

Per Lesson 2, the no-default-catchall rule means every unknown_shape record gets surfaced for manual review. My triage of the 78:

**Genuinely-unclassifiable for v1 (acceptable as `unknown_shape`)** — 64 records:
- NPC backstory references inside dialogue (durations spoken by NPCs about their own past, deadlines, recurring schedules) — most of the 61 `[NPC]`-flagged unknown-shapes fall here. Examples: t81 "six weeks", t246 "two days" (NPC ETA), t530 "a month", t656 "000 years", t726 "two days" (NPC commission), t731 "two days", t766 "a day", t941 "a year", t1026 "five minutes", t1435 "three days", t1450 "ten years", t1481 "a few days", t1490 "the next hour", t1494 "a week", t1582 "five years", t1617 "a month", t1651 "a month", t1659 "a few months", t1666 "a few days" (all from C1E024); plus continuing NPC backstory in C1E057, C1E085, C1E101, C2E002, C2E018, C2E024, C2E031.
- Recurring-schedule fiction: "every six months" (C2E024_t2293), "a week" (C2E024_t517 "Once a week"), "a few days" (C2E024_t529).
- NPC age: "200 years old" (C2E024_t1029, C2E018_t2055).
- Borderline backstory: "since you first saw her" — Matt-narration but past-only.

**Classifier misses that v2 should fix** — 14 records:
- C1E003_t0 "many weeks" — Matt's recap intro ("Going back over what had transpired"). `is_recap_state: false` — recap detection failed because the trigger turn IS the recap-vocab turn AND idx=0 means the loop in `derive_recap_state` doesn't fire and the trigger-turn check should fire but doesn't catch "going back over what". Pattern needs widening. **v2 patch: extend RECAP_VOCAB**.
- C1E024_t77/t79 (3 records) "two weeks"/"a week" — between-session timeskip narration ("Pike left back there to finish up the renovation... The rest of the party moved on back to Emon... Within Emon, they returned... a week later..."). Should be `scene_transition` (between-session bridge). **v2 patch: pattern for "moved on back to" / "left back there" / "[duration] later" inter-session bridges**.
- C1E024_t1290 "a round" — "stunned for a round" mid-Stormlord-challenge combat, but combat init was >25 turns prior so OQ5-locked combat-state heuristic missed. **v2 patch (out of OQ5 scope)**.
- C1E047_t1603 "few days" — "His structure is still standing as well. A few buildings... a few days..." — fragmented; possibly classifiable with more pattern work.
- C1E101_t1435 "a round" — same OQ5 limitation as t1290.
- C2E018_t748 "three rounds" — gladiator-pit episode, combat is active but init was outside the 25-turn lookback.
- C2E018_t2384 "a few days" — "merchant guilds in Zadash... in the process of getting ready to figure out what their next endeavor is..." — fuzzy, borderline.
- C2E024_t719, C2E031_t719 "a day" (2 records) — both contain the idiom "As bright a day as it is" / similar. **v2 patch: idiom filter for "as X a day as" / "as bright a day"**.

The 14-record v2-patch list lands ~24 of the 78 if all patches succeed. The remaining 54 NPC-dialogue-borrowed time references are genuinely outside Matt-narration scope per the §11.3 lock.

---

## 7. Anchor-resolution stats (Stage 3)

| Metric | Value |
|---|---:|
| Records flagged `is_anchored: true` | 16 / 321 (5.0%) |
| Anchor-resolved (`time_anchor_turn_number != null`) | 7 / 16 (43.8%) |
| Mean `anchor_distance_turns` | 7.0 turns |
| Min / max distance | 2 / 15 turns |

Anchor-resolution rate is **44%** — well below the "if <60%, widen to 25 turns" threshold flagged in the spec's Open Question §11.OQ4. **Recommendation: widen to 25-turn back-walk in v2.**

The anchor walk-back uses both prior time-mentions and rest declarations as anchor candidates. The 9 unresolved cases are mostly "X later" / "moments later" / "by the time you" triggers fired in turns where the prior time-anchor sits >15 turns earlier (long stretches of player banter intervening between Matt's last anchor and the next time-mention).

---

## 8. Combat-state under-detection

`is_combat_state: true` count: **0 / 321** across the sample.

This is suspicious — at minimum the round-bucket records (10) and several "stunned for a round" moments (e.g., C1E024_t1290, C1E101_t1435, C2E018_t748) are inside active combat. The OQ5 lock caps the back-walk for the COPIED_POSITIVE_INIT regex at 25 turns, which under-detects long encounters where the init call sits 30-50+ turns prior to a mid-combat time-mention.

This is a **known v1 limitation under the OQ5 lock** — the lock's specification of 25 turns + 30-turn staleness fallback yields zero hits in this sample. Two options for v2:
- (a) Widen to 50-turn lookback (out-of-lock, requires Jordan's signoff).
- (b) Add a backup signal: damage-narration vocabulary in the last 5-10 turns implies combat-active, even if init is out of window. Same shape as Encounter Cadence v1.3's STATE flag.

Filed as v2 candidate in §10.

---

## 9. §11.7 / OQ1 review files (for Jordan's manual spot-check)

Two JSON files are dumped alongside this report. Each record carries a `manual_verdict: "[ ]"` placeholder for Jordan to fill during spot-check.

- **`time_mention_boundary_stability_v1.json`** — 196 records (71 `scene_transition` + 125 `cumulative_anchor`). Per §11.7 lock, mark each as `"3.3"` (unambiguously scene_transition), `"3.4"` (unambiguously cumulative_anchor), or `"ambiguous"`. If the ambiguous proportion exceeds 20% of the 196 total, flag for v2 collapse to a single category.

- **`time_mention_d6_precision_v1.json`** — 171 records (`is_npc_dialogue_present: true`). Per OQ1 lock, mark each as `"in_npc_speech"` (time phrase is genuinely inside NPC dialogue), `"in_matt_narration"` (Matt narrating; D6 flag is FP), or `"ambiguous"`. Used to recompute D6 precision against the full sample (replacing my 25-record spot-check estimate of 56-64%).

Both files are append-safe — Jordan edits in place, then a follow-up script can compute the proportions. The Phase 2 calibration regression baseline (150 → 321 records after OQ1 fallback) is in `time_mention_eval_set_v1.json`.

---

## 10. Anomalies and filed insights

### v2-candidate patches
- **D6 phrase-span check** — only reject (or flag) if the time phrase falls inside the quoted/voiced span, not at turn level. Likely improves precision back toward the 85% threshold.
- **Anchor walk-back widening** — 15 → 25 turns. Aligned with Lesson 6's 10-15-turn-minimum doctrine.
- **Combat-state backup signal** — damage narration vocabulary in last 5-10 turns implies combat-active.
- **Recap-vocab extension** — "going back over", "what had transpired" already added but t0 still misclassifies; investigate.
- **Idiom filter** — "as bright a day as", "as fine a day" — small idiom set.
- **Inter-session bridge patterns** — "moved on back to", "the rest of their business complete", "left back there to finish".

### New filed insight (candidate Lesson 9 for `corpus_builder_lessons_v1.md`)

**Phrase-span vs turn-level Stage 0 decisions.** Encounter Cadence's Stage 0 architecture operated at turn level — DISCOURSE rejection drops the whole turn. Time-Mention's D6 (NPC dialogue) reveals a structural limit: when a turn mixes NPC speech AND Matt narration AND time phrases appear in both, turn-level reject loses real signal. Future extractors operating in densely-mixed-narration domains (Loot/Reward will face this with NPC offering/requesting items; Faction-Reference will face this with NPC factions referenced in their own speech) should design Stage 0 patterns at phrase-span level when the turn is heterogeneous.

This is candidate Lesson 9 for the cross-extractor lessons doc — to be confirmed/incorporated after Loot/Reward (Ship 3) sees the same shape.

### Multi-mention-turn rate

17.2% of trigger turns produced multiple records (45 turns producing 104 records collectively, 59 of which are "extra"). Higher than the spec's anticipated "5-8% from recon" estimate. Drivers: time-of-day anchors that span multiple phrases ("It's late afternoon... an hour and a half from sundown... mid-afternoon"), NPC-dialogue turns with multiple NPC-spoken time references in a row, and Matt's "let me get you up to speed" recap-style turns.

### Granularity-bucket distribution skew

`days` dominates (94/321 = 29%). Breakdown reveals that the `days` bucket aggregates `morning|evening|afternoon|night|noon|midnight|dawn|dusk` (per `GRANULARITY_PATTERNS`) — i.e., time-of-day anchors land here. Many of these records are genuinely "hours-of-the-day" granularity but are bucketed as `days`. Consider splitting `days` into `days` (calendar day count) and `time_of_day` (sub-day diurnal anchors) in v2.

### `[EXTRACTOR_UNKNOWN]` count

Zero unknown-format records across 10 episodes. Source format is byte-stable per Ship 1 confirmation.

---

## 11. Phase 3 readiness

Phase 3 (gate-set construction + calibration regression) starts when Jordan completes:
1. Manual review of `time_mention_boundary_stability_v1.json` (§11.7 boundary check).
2. Manual review of `time_mention_d6_precision_v1.json` (OQ1 D6 precision).
3. Calibration verdicts on the 321 records in `time_mention_eval_set_v1.json` — convert `verdict_at_v1: "correct"` baselines into actual `"correct"` / `"wrong"` / `"miss"` based on the spot-check.

The regression test runner (`extractors/test_time_mention_eval_v1.py`) currently reports 321/321 = 100% on the auto-built baseline. After Jordan's verdicts land, the calibration metric will reflect real precision — the auto-baseline number is structurally inflated by being self-referential.

Phase 2 has NOT built the `gate_holdout` split. Phase 3 builds it from Jordan-corrected verdicts and a fresh random sample over the post-correction record set.
