# Eval set v2 — 64 records

Combines:
- 14 records from v1 eval set (Phase 2 hand-sample, hand-fixed by Phase 2.5)
- 26 records from Phase 3 spot-check batches (Jordan-curated episodes)
- 24 records from random blind sample (seed=42 over unseen episodes)

To be assembled by Code at Phase 4 step 1 from the source artifacts. This file documents the construction, not the records themselves.

## v1 (14 records) — already exists
Source: `corpus_builder/findings/encounter_cadence_eval_set_v1.json`. All 14 records preserved with their `expected_*` fields from Phase 2.5.

## Phase 3 spot-check (26 records) — verdicts from Jordan-Claude review
Source: full parse output `corpus_builder/output/encounter_cadence/`.
Episodes Jordan uploaded for review: C1E002, C1E007 (1 record), C1E025, C1E027, C1E028, C1E029, C1E031, C1E033, C1E044, C1E055, C1E058, C1E061, C1E068, C1E071, C1E093, C1E098, C1E102, C1E107, C1E113, C1E114, C2E003, C2E007, C2E019, C2E025, C2E026, C2E039, C2E042.

Verdicts table (record_id, expected_category, expected_is_fresh_encounter, expected_wave_subtype, verdict_at_v1_1, failure_mode):

C1E102_t944, NOT_INIT_EVENT, n/a, n/a, false_positive, "wisdom save in mid-combat is not an init event"
C1E102_t1440, npc_turns_hostile, true, null, wrong, "Vecna transformation reveal — narration_buildup at 1436 explicit but trigger turn at 1440 didn't reach back far enough"
C1E102_t2358, NOT_INIT_EVENT, n/a, n/a, false_positive, "wisdom check during ritual is not init"
C2E042_t251, npc_turns_hostile, true, null, wrong, "NPC accepts challenge ('Come at me!') and dives — dialogue-trigger should fire"
C2E042_t1074, interruption, true, null, correct, "bare 'Roll initiative!' with thin RP buildup, defensible"
C1E029_t448, npc_turns_hostile, true, null, wrong, "banshee approaches, drift in, eyes fall on PCs — env+npc reveal"
C1E029_t1587, player_action_escalation, true, null, wrong, "Liam kicks door, Travis rages — direct player-caused"
C1E028_t220, interruption, true, null, correct, "cold-open opening narration, defensible default"
C1E002_t1499, wave_or_phase_shift, false, phase_shift, wrong, "init called mid-active-combat (mandibles, attack rolls, damage)"
C1E107_t1204, environmental_materialization, true, null, correct, "bulette + children emerge from walls"
C1E031_t144, npc_turns_hostile, true, null, wrong, "guards in waiting pattern, 'shoot me' anticipation"
C1E031_t152, DUPLICATE, n/a, n/a, duplicate, "same encounter as t144 — analysis-layer dedup"
C1E031_t686, npc_turns_hostile, true, null, wrong, "guards loose volley after 'Loose!' command"
C2E003_t53, interruption, true, null, correct, "cold-open, thin context, defensible default"
C2E003_t1875, player_action_escalation, true, null, wrong, "Marisha climbs wall, sees red eyes — player action triggered"
C2E003_t2449, NOT_INIT_EVENT, n/a, n/a, false_positive, "constitution save mid-combat is not init"
C2E026_t864, environmental_materialization, true, null, correct, "insectoid creatures burst from dirt"
C2E026_t2875, player_action_escalation, true, null, wrong, "tree-fell ambush executed, party planned action"
C1E027_t83, npc_turns_hostile, true, null, defensible, "invisible attacker chokes Jarett — could be env/npc"
C1E027_t175, wave_or_phase_shift, false, party_join, wrong, "Trinket already rolled at t157, 'now the rest of you' is wave"
C1E113_t1352, wave_or_phase_shift, false, phase_shift, wrong, "dragon turn complete, init re-rolled mid-combat"
C2E025_t1023, player_action_escalation, true, null, wrong, "stealth setup, monster aware → init"
C1E098_t1779, environmental_materialization, true, null, defensible, "cherub screams, structure shakes — wisdom save fires before combat init"
C1E001_t1573, environmental_materialization, true, null, defensible, "vines/ogres mid-fireball — could be wave (combat already implicit)"
C2E001_t1136, npc_turns_hostile, true, null, correct, "transformation widening from patch 6 worked"

C1E044_t378, environmental_materialization, true, null, wrong, "shadow-quiver formulating — was tagged player_action_escalation"
C1E055_t1340, environmental_materialization, true, null, correct, "dragon swoops in, long buildup"
C1E061_t806, NOT_INIT_EVENT, n/a, n/a, false_positive, "survival check, not init — was tagged npc_turns_hostile"
C1E068_t1382, NOT_INIT_EVENT, n/a, n/a, false_positive, "concentration check during Hex — not init"
C1E071_t1554, wave_or_phase_shift, false, phase_shift, wrong, "Scanlan-only init mid-Vorugal-fight"
C1E071_t1767, wave_or_phase_shift, false, party_join, wrong, "those who are entering the fray"
C1E033_t851, NOT_INIT_EVENT, n/a, n/a, false_positive, "movement+dash narration — not init"
C2E007_t134, environmental_materialization, true, null, correct, "before round start, settling positioning"

(Note: this is partial — Code rebuilds the full table by reading raw_text and Jordan's prior verdicts in the chat. ~26 spot-check records total.)

## Phase 3 blind sample (24 records) — Claude blind-judged
Source: random.seed=42 over records from episodes not yet reviewed.

Sampled record IDs and expected categories:

C1E023_t407, npc_turns_hostile, true, null
C1E007_t706, wave_or_phase_shift, false, phase_shift
C1E092_t2062, player_action_escalation, true, null
C1E086_t1234, wave_or_phase_shift, false, party_join
C1E076_t479, NOT_INIT_EVENT, n/a, n/a
C1E039_t79, environmental_materialization, true, null
C1E022_t1709, npc_turns_hostile, true, null
C1E019_t851, npc_turns_hostile, true, null
C2E017_t1644, NOT_INIT_EVENT, n/a, n/a
C1E008_t952, player_action_escalation, true, null
C1E007_t1655, wave_or_phase_shift, false, phase_shift
C1E021_t66, interruption, true, null
C1E072_t1135, NOT_INIT_EVENT, n/a, n/a
C1E076_t1224, NOT_INIT_EVENT, n/a, n/a
C2E046_t1030, wave_or_phase_shift, false, party_join
C1E094_t2221, npc_turns_hostile, true, null  # OR wave; defensible — accept either
C1E021_t1497, player_action_escalation, true, null
C2E005_t956, player_action_escalation, true, null
C1E108_t57, interruption, true, null
C1E111_t1707, player_action_escalation, true, null
C1E092_t553, NOT_INIT_EVENT, n/a, n/a
C1E072_t1129, NOT_INIT_EVENT, n/a, n/a
C2E046_t1800, wave_or_phase_shift, false, phase_shift
C2E044_t1757, npc_turns_hostile, true, null
