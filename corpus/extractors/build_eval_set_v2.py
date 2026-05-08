#!/usr/bin/env python3
"""
One-time builder for findings/encounter_cadence_eval_set_v2.json.

Combines:
  - 14 v1 records carried forward from encounter_cadence_eval_set_v1.json
  - Spot-check records (Jordan-curated, from construction notes) — 31 records
  - Blind sample records (random.seed=42 from construction notes) — 24 records

For records the v1.1 full parse emitted, raw_text is pulled from
output/encounter_cadence/<episode>.json. Sentinels NOT_INIT_EVENT and DUPLICATE
are used for records v1.1 emitted but Jordan flagged as false-positive or
duplicate — the regression test handles them specially.
"""

import json
from pathlib import Path

CORPUS = Path(__file__).resolve().parent.parent
OUTPUT_DIR = CORPUS / "output" / "encounter_cadence"
V1_PATH = CORPUS / "findings" / "encounter_cadence_eval_set_v1.json"
V2_PATH = CORPUS / "findings" / "encounter_cadence_eval_set_v2.json"

# ---------------------------------------------------------------------------
# Spot-check records, transcribed from eval_set_v2_construction.md verdicts
# table. Format: (trigger_id, expected_category, expected_is_fresh,
# expected_wave_subtype, source_label, notes).
# ---------------------------------------------------------------------------

SPOTCHECK = [
    ("C1E102_t944",  "NOT_INIT_EVENT",            None,   None,           "spotcheck", "wisdom save in mid-combat is not an init event"),
    ("C1E102_t1440", "npc_turns_hostile",         True,   None,           "spotcheck", "Vecna transformation reveal — narration_buildup at 1436 explicit but trigger turn at 1440 didn't reach back far enough"),
    ("C1E102_t2358", "NOT_INIT_EVENT",            None,   None,           "spotcheck", "wisdom check during ritual is not init"),
    ("C2E042_t251",  "npc_turns_hostile",         True,   None,           "spotcheck", "NPC accepts challenge ('Come at me!') and dives — dialogue-trigger should fire"),
    ("C2E042_t1074", "interruption",              True,   None,           "spotcheck", "bare 'Roll initiative!' with thin RP buildup, defensible"),
    ("C1E029_t448",  "npc_turns_hostile",         True,   None,           "spotcheck", "banshee approaches, drift in, eyes fall on PCs — env+npc reveal"),
    ("C1E029_t1587", "player_action_escalation",  True,   None,           "spotcheck", "Liam kicks door, Travis rages — direct player-caused"),
    ("C1E028_t220",  "interruption",              True,   None,           "spotcheck", "cold-open opening narration, defensible default"),
    ("C1E002_t1499", "wave_or_phase_shift",       False,  "phase_shift",  "spotcheck", "init called mid-active-combat (mandibles, attack rolls, damage)"),
    ("C1E107_t1204", "environmental_materialization", True, None,         "spotcheck", "bulette + children emerge from walls"),
    ("C1E031_t144",  "npc_turns_hostile",         True,   None,           "spotcheck", "guards in waiting pattern, 'shoot me' anticipation"),
    ("C1E031_t152",  "DUPLICATE",                 None,   None,           "spotcheck", "same encounter as t144 — analysis-layer dedup"),
    ("C1E031_t686",  "npc_turns_hostile",         True,   None,           "spotcheck", "guards loose volley after 'Loose!' command"),
    ("C2E003_t53",   "interruption",              True,   None,           "spotcheck", "cold-open, thin context, defensible default"),
    ("C2E003_t1875", "player_action_escalation",  True,   None,           "spotcheck", "Marisha climbs wall, sees red eyes — player action triggered"),
    ("C2E003_t2449", "NOT_INIT_EVENT",            None,   None,           "spotcheck", "constitution save mid-combat is not init"),
    ("C2E026_t864",  "environmental_materialization", True, None,         "spotcheck", "insectoid creatures burst from dirt"),
    ("C2E026_t2875", "player_action_escalation",  True,   None,           "spotcheck", "tree-fell ambush executed, party planned action"),
    ("C1E027_t83",   "npc_turns_hostile",         True,   None,           "spotcheck", "invisible attacker chokes Jarett — could be env/npc"),
    ("C1E027_t175",  "wave_or_phase_shift",       False,  "party_join",   "spotcheck", "Trinket already rolled at t157, 'now the rest of you' is wave"),
    ("C1E113_t1352", "wave_or_phase_shift",       False,  "phase_shift",  "spotcheck", "dragon turn complete, init re-rolled mid-combat"),
    ("C2E025_t1023", "player_action_escalation",  True,   None,           "spotcheck", "stealth setup, monster aware — init"),
    ("C1E098_t1779", "environmental_materialization", True, None,         "spotcheck", "cherub screams, structure shakes — wisdom save fires before combat init"),
    ("C1E044_t378",  "environmental_materialization", True, None,         "spotcheck", "shadow-quiver formulating — was tagged player_action_escalation"),
    ("C1E055_t1340", "environmental_materialization", True, None,         "spotcheck", "dragon swoops in, long buildup"),
    ("C1E061_t806",  "NOT_INIT_EVENT",            None,   None,           "spotcheck", "survival check, not init — was tagged npc_turns_hostile"),
    ("C1E068_t1382", "NOT_INIT_EVENT",            None,   None,           "spotcheck", "concentration check during Hex — not init"),
    ("C1E071_t1554", "wave_or_phase_shift",       False,  "phase_shift",  "spotcheck", "Scanlan-only init mid-Vorugal-fight"),
    ("C1E071_t1767", "wave_or_phase_shift",       False,  "party_join",   "spotcheck", "those who are entering the fray"),
    ("C1E033_t851",  "NOT_INIT_EVENT",            None,   None,           "spotcheck", "movement+dash narration — not init"),
    ("C2E007_t134",  "environmental_materialization", True, None,         "spotcheck", "before round start, settling positioning"),
]

BLIND = [
    ("C1E023_t407",  "npc_turns_hostile",         True,   None,           "blind", "blind sample"),
    ("C1E007_t706",  "wave_or_phase_shift",       False,  "phase_shift",  "blind", "blind sample"),
    ("C1E092_t2062", "player_action_escalation",  True,   None,           "blind", "blind sample"),
    ("C1E086_t1234", "wave_or_phase_shift",       False,  "party_join",   "blind", "blind sample"),
    ("C1E076_t479",  "NOT_INIT_EVENT",            None,   None,           "blind", "blind sample"),
    ("C1E039_t79",   "environmental_materialization", True, None,         "blind", "blind sample"),
    ("C1E022_t1709", "npc_turns_hostile",         True,   None,           "blind", "blind sample"),
    ("C1E019_t851",  "npc_turns_hostile",         True,   None,           "blind", "blind sample"),
    ("C2E017_t1644", "NOT_INIT_EVENT",            None,   None,           "blind", "blind sample"),
    ("C1E008_t952",  "player_action_escalation",  True,   None,           "blind", "blind sample"),
    ("C1E007_t1655", "wave_or_phase_shift",       False,  "phase_shift",  "blind", "blind sample"),
    ("C1E021_t66",   "interruption",              True,   None,           "blind", "blind sample"),
    ("C1E072_t1135", "NOT_INIT_EVENT",            None,   None,           "blind", "blind sample"),
    ("C1E076_t1224", "NOT_INIT_EVENT",            None,   None,           "blind", "blind sample"),
    ("C2E046_t1030", "wave_or_phase_shift",       False,  "party_join",   "blind", "blind sample"),
    ("C1E094_t2221", "npc_turns_hostile",         True,   None,           "blind", "blind sample (OR wave; defensible — accept either)"),
    ("C1E021_t1497", "player_action_escalation",  True,   None,           "blind", "blind sample"),
    ("C2E005_t956",  "player_action_escalation",  True,   None,           "blind", "blind sample"),
    ("C1E108_t57",   "interruption",              True,   None,           "blind", "blind sample"),
    ("C1E111_t1707", "player_action_escalation",  True,   None,           "blind", "blind sample"),
    ("C1E092_t553",  "NOT_INIT_EVENT",            None,   None,           "blind", "blind sample"),
    ("C1E072_t1129", "NOT_INIT_EVENT",            None,   None,           "blind", "blind sample"),
    ("C2E046_t1800", "wave_or_phase_shift",       False,  "phase_shift",  "blind", "blind sample"),
    ("C2E044_t1757", "npc_turns_hostile",         True,   None,           "blind", "blind sample"),
]

# Records where >1 expected_category is acceptable per construction notes.
# Maps trigger_id -> set of acceptable categories.
#
# C1E044_t378: source text contains "roll an insight check" not "roll
# initiative" — no init in surrounding turns either. Jordan labelled
# environmental_materialization based on the shadow-formulation language but
# the trigger is a Stage-1 false positive in v1.1. Either label is acceptable.
#
# C1E033_t851: trigger text "Everyone else roll initiative. We're in a new
# combat round." is ambiguous between a phase_shift and ongoing-combat
# narration. Jordan labelled NOT_INIT_EVENT but a wave_or_phase_shift call is
# defensible.
DEFENSIBLE = {
    "C1E094_t2221": {"npc_turns_hostile", "wave_or_phase_shift"},
    "C1E027_t83":   {"npc_turns_hostile", "environmental_materialization"},
    "C1E098_t1779": {"environmental_materialization", "NOT_INIT_EVENT"},
    "C1E044_t378":  {"environmental_materialization", "NOT_INIT_EVENT"},
    "C1E033_t851":  {"NOT_INIT_EVENT", "wave_or_phase_shift"},
}


def load_record_from_output(trigger_id):
    """Pull the v1.1-emitted record from output/encounter_cadence/<ep>.json."""
    ep, t = trigger_id.split("_t")
    turn_no = int(t)
    p = OUTPUT_DIR / f"{ep}.json"
    with open(p, "r", encoding="utf-8") as f:
        recs = json.load(f)
    for r in recs:
        if r["trigger_turn_number"] == turn_no:
            return r
    return None


def build_entry(trigger_id, expected_cat, expected_fresh, expected_wave, source, note):
    rec = load_record_from_output(trigger_id)
    if rec is None:
        raise RuntimeError(f"Record {trigger_id} not in v1.1 output")
    ep, t = trigger_id.split("_t")
    return {
        "trigger_id": trigger_id,
        "campaign": rec["campaign"],
        "episode": rec["episode"],
        "trigger_turn_number": rec["trigger_turn_number"],
        "expected_category": expected_cat,
        "expected_is_fresh_encounter": expected_fresh,
        "expected_wave_subtype": expected_wave,
        "v1_1_classification": rec["trigger_category"],
        "v1_1_is_fresh_encounter": rec["is_fresh_encounter"],
        "v1_1_wave_subtype": rec["wave_subtype"],
        "raw_text": rec["raw_text"],
        "source": source,
        "notes": note,
        "defensible_alternates": (
            sorted(DEFENSIBLE[trigger_id])
            if trigger_id in DEFENSIBLE else None
        ),
    }


def main():
    with open(V1_PATH, "r", encoding="utf-8") as f:
        v1_records = json.load(f)

    # Carry v1 records forward; tag with source="v1" and backfill raw_text +
    # v1.1 classification fields from the v1.1 full-parse output.
    v2 = []
    for r in v1_records:
        entry = dict(r)
        entry["source"] = "v1"
        rec = load_record_from_output(r["trigger_id"])
        if rec is not None:
            entry["v1_1_classification"] = rec["trigger_category"]
            entry["v1_1_is_fresh_encounter"] = rec["is_fresh_encounter"]
            entry["v1_1_wave_subtype"] = rec["wave_subtype"]
            entry["raw_text"] = rec["raw_text"]
        v2.append(entry)

    for tid, cat, fresh, wave, source, note in SPOTCHECK + BLIND:
        v2.append(build_entry(tid, cat, fresh, wave, source, note))

    with open(V2_PATH, "w", encoding="utf-8") as f:
        json.dump(v2, f, indent=2, ensure_ascii=False)

    by_source = {}
    for e in v2:
        by_source[e["source"]] = by_source.get(e["source"], 0) + 1
    print(f"Wrote {len(v2)} records to {V2_PATH}")
    print(f"By source: {by_source}")


if __name__ == "__main__":
    main()
