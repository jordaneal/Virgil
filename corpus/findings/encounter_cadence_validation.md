# Encounter Cadence v1 — Hand-Sample Validation Report

**Run date:** 2026-05-05
**Extractor version:** `encounter_cadence_v1`
**Source dir:** `/mnt/virgil_storage/dnd_datasets/crd3/data/aligned data/c=2`
**Sample episodes (10):** C1E001, C1E020, C1E030, C1E049, C1E060, C1E095, C2E001, C2E020, C2E030, C2E045
**Output:** `/home/jordaneal/corpus_builder/samples/encounter_cadence_sample.json`
**`[EXTRACTOR_UNKNOWN]` count:** 0

This report summarizes the run only. **Recall / precision / taxonomy review is Jordan's manual spot-check** per `CORPUS_BUILDER.md` Hand-Sample Validation Protocol — the questions in that protocol are not answered here.

---

## 1. Volume

- **Records emitted:** 14 across 10 episodes.
- **Per-episode:** C1E001=1, C1E020=2, C1E030=2, C1E049=3, C1E060=0, C1E095=0, C2E001=1, C2E020=1, C2E030=0, C2E045=4.
- **Episodes with zero records:** C1E060, C1E095, C2E030 (3 of 10).

Phase 1 spec predicted C1E095 would be zero (downtime montage — confirmed) and C1E060 was a candidate (RP-heavy — confirmed). C2E030 was not pre-flagged but is also zero.

---

## 2. Categories × `is_fresh_encounter`

| Category | Fresh | Wave | Total |
|---|---:|---:|---:|
| `environmental_materialization` | 3 | 0 | 3 |
| `npc_turns_hostile` | 3 | 0 | 3 |
| `interruption` | 5 | 0 | 5 |
| `player_action_escalation` | 1 | 0 | 1 |
| `trap_activation` | 0 | 0 | 0 |
| `wave_or_phase_shift` | 0 | 2 | 2 |
| **Total** | **12** | **2** | **14** |

Wave sub-types: `party_join`=1 (C1E030 t517), `phase_shift`=1 (C1E049 t2812). `reinforcement`=0.

Five non-wave categories all populated except `trap_activation` (zero hits — see §5 anomaly #4).

---

## 3. Field distributions

- **`player_action_caused`:** True=1, False=13.
- **`narration_buildup_chars`:** min=95, median=893, max=1206, mean=819.
- **`preceding_context_chars`:** min=344, median=1429, max=1489, mean=1308. The 1500 budget is rarely fully consumed — most records consume the full window or stop within ~70 chars of it. The exception is C2E001 t1136 (344 chars total context, 95 chars MATT-narration buildup) which sits at the start of an arc with very little MATT text immediately preceding.

The single `player_action_caused=True` record (C2E045 t2529) is one of the four C2E045 records.

---

## 4. Schema and rule conformance check

- All 14 records carry every field from the locked schema. No null `extracted_at`, no missing `trigger_turn_number`, no `wave_subtype` set when `is_fresh_encounter=True`.
- `is_fresh_encounter ⇔ trigger_category == 'wave_or_phase_shift'` holds in all 14 records (the redundancy is intentional per locked schema note).
- `extracted_at` is identical across all 14 records of this run (single ISO timestamp at run start, per Design Constraint #4 idempotency requirement).
- `event_type` is `init_event` in all records.
- All 14 `speaker` values are `MATT`.
- `episode_position_pct` ranges 0.27–0.73 across the records — no obvious outliers.

A second `--sample` run produced byte-identical event-content fields across all records (only `extracted_at` differs). Idempotency confirmed.

---

## 5. Anomalies and edge cases hit during implementation

These are observed-during-coding; not classification judgments.

1. **`NPC_VOICING` regex catches non-speech "goes" / "says".** "He goes and he does like a hand motion" matches the `\b(?:he|she|it|they)\s+(?:goes|...)\b` pattern even though it's narrating physical motion, not speech. Hit at C1E020 t993, where the closest preceding MATT text contains "he goes and he does like a hand motion" — record was tagged `npc_turns_hostile`. Phrase ambiguity is a known English-regex hazard.

2. **`trigger_references_player` is anchored at the start of the trigger and uses a fixed phrase list.** It misses `"Initiative has now kicked in"` and similar consequence phrasings that don't begin with "as you" / "since you" / "having" / "stupid" / "now the" / "with that". Record at C1E049 t535 (Sam-failed-stealth → orc reaction) classified as `npc_turns_hostile` instead of `player_action_escalation` because (a) the player-action turn was 4 turns back rather than immediate, and (b) the trigger phrasing didn't match the references regex. The classifier's recall on `player_action_escalation` is conservative.

3. **`trap_activation` zero hits.** C2E045 t2014 is semantically a cabinet trap (recon §2 O5) but classified `environmental_materialization`. Cause: by the time MATT calls init at t2014, the trap-spring narration was at t1998 (16 turns earlier) and the player-interaction turn ("We stick our hands in") was at t1997. The 1500-char preceding context budget did not reach back that far — `player_acted` evaluated against the immediate-predecessor non-MATT turn, which by t2014 was Taliesin casting Sacred Flame (an action but not a mechanism interaction). The `trap_activation` rule effectively requires interaction → init within ~5 turns. The locked rule is unchanged; this is its observed shape.

4. **Adjacent fresh starts pollute each other's preceding context.** C1E020 t986 and t993 are 7 turns apart. The t993 record's preceding window includes the t986 trigger as a MATT turn, and t986's text contains "he goes and he does like a hand motion" — which fed into the `NPC_VOICING` false positive in #1. Locked rule §6.7 (no within-episode dedup at extractor) is the correct discipline; the noise this introduces is downstream-handleable.

5. **Wave detection is literal-phrase only.** C2E045 t2678 (party members fall through ceiling, "Both of you roll initiative. First of all, acrobatics check.") classified as `interruption`. The trigger has neither `who just landed` nor explicit `reroll`. It's a semantic wave but doesn't match any locked wave-pattern phrase. C2E045 t2568 (fire elemental summon, "Roll initiative for the elemental.") similarly classified as `interruption` — adding a new combatant to existing combat, but no wave phrase. Locked rule §3.6 wave-pattern set is regex-literal; semantic-wave-without-matching-phrase events stay `interruption`.

6. **`environmental_materialization` requires both buildup ≥500 chars AND scene-change vocab.** Several semantically-environmental events have buildup just below 500 (e.g., C1E030 t379 has 649 — passes; C2E001 t1136 has 95 — fails). The 500-char threshold is the locked default in the spec; this run shows it sits very close to a meaningful boundary. Three records cross it; others fall through to `interruption`.

7. **C1E020 t986 (Polymorph→Silence chase init) classifies `interruption`, not `player_action_escalation`.** Same root cause as #2 — the trigger ("Okay, cool. So that creates a sphere of a 20-foot radius of silence here. So he goes and he does like a hand motion. Nothing happens. Frustrated, he continues to run. I'm going to have you guys roll initiative.") narrates the spell consequence rather than acknowledging the player with one of the matched phrases. The player-action declarations (Polymorph dispel + Silence cast at turn 981) are present in the preceding window but the references-it gate doesn't fire.

---

## 6. Implementation-time decisions made within the locked rules

These are interpretation calls inside the locked spec — not rule changes. Surfaced for Jordan to confirm or correct before any full parse runs.

- **`player_action_caused` is computed from the most-recent non-MATT turn in the preceding window** (skipping intervening MATT turns), checked against `PLAYER_ACTION_VERBS` and `PLAYER_CHECK_DECLARATIONS` regex sets. The locked schema note is `(was there a player turn declaring an action immediately before the trigger)` — "immediately" interpreted as "closest" rather than "at index `trigger_idx-1`." If the strict-immediate interpretation is preferred, change is one-line.

- **NPC dialogue detection (priority 4) uses three regex patterns:** `QUOTED_SPEECH` (anything in straight or curly quotes ≥6 chars), `NPC_VOICING` (`he/she/it/they (says|goes|growls|...)`), `NPC_NAMED_SPEECH` (Capitalized name + speech verb). The closest 3 MATT turns concatenated is the search window. Anomaly #1 above shows `NPC_VOICING` over-fires on "he goes [non-speech]". Tightening to require quotes-following or excluding "goes" entirely is a one-line tradeoff.

- **`player_action_escalation` priority-3 gate:** classification fires only if (any non-MATT in window has action verbs) AND (trigger references player OR immediate non-MATT turn is action-bearing). Trigger-references regex anchored at start with phrases `as you / because you / since you / having / stupid / nice try / bad luck / now the / with that`. The locked rule says "trigger text references it" — an interpretive gap; the regex is conservative.

- **Wave-pattern set:** `WAVE_PARTY_JOIN` matches `the (people|three|both|two|few|other(s)?)` / `those` / `(both|all|the N) of you` followed by `who just (woke|landed|fell|joined|appeared|came in|came down|dropped in|now roll)`. `WAVE_REINFORCEMENT` matches `reinforcements? | backup | new wave | second wave | fresh wave | more (enemies|guards|figures|creatures)`. `WAVE_PHASE_SHIFT` matches `reroll initiative | reroll your initiative | new phase | phase (two|three|change|shift) | round resets`. These extend the locked illustrative phrases lightly; if too liberal, narrow to literal patterns from the prompt.

---

## 7. What this report does NOT do

Per `CORPUS_BUILDER.md` Hand-Sample Validation Protocol, Jordan's manual spot-check answers:

1. **Recall.** Does the extractor catch what it's supposed to catch?
2. **Precision.** Does the extractor avoid false positives?
3. **Taxonomy.** Are the classification categories observable and repeatable?

This report enumerates volume, distributions, and anomalies surfaced during code execution — it does not pre-judge those three questions. The 14 records are open in `samples/encounter_cadence_sample.json` for the spot-check.

The full parse on all 140 CRD3 episodes is **not** scheduled until Jordan signs off this validation. The `--full` mode is built and tested-import-clean but unrun.
