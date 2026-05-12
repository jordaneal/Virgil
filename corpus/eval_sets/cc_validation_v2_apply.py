#!/usr/bin/env python3
"""
cc_validation_v2_apply.py
Compression Cadence — Phase 6 validation v2 apply script.

Reads compression_cadence_validation_v1.json, applies blind-judge verdicts,
writes compression_cadence_validation_v2.json. Mirrors cc_gate_v2_apply.py
pattern with array key 'validation' (not 'gate').

Usage (from corpus_builder/eval_sets/ on server):
    python3 cc_validation_v2_apply.py
"""
import json
import os
from datetime import datetime, timezone

INPUT_PATH = "compression_cadence_validation_v1.json"
OUTPUT_PATH = "compression_cadence_validation_v2.json"

# ---------------------------------------------------------------------------
# Verdict dict. Key: (trigger_id, same_turn_record_index).
# Each value:
#   verdict         : "correct" | "defensible" | "wrong" | "duplicate"
#   expected_*      : judged values (mirror extracted_* on correct)
#   failure_family  : str | None
#   judge_notes     : str | None
# ---------------------------------------------------------------------------
VERDICTS = {
    # 1. C1E005_t3244 — OVERNIGHT_REST (defensible)
    # Raw text is unusually spare ("As Grog, you come to consciousness again--").
    # The "again" is suggestive of prior unconsciousness in-session (knockout
    # recovery scenario). Preceding 3 turns are OOC chatter about Trinket — no
    # combat-context tokens for D5 to fire on. Episode position 91.4% (late)
    # could be either end-of-session denouement (post-rest morning) OR a mid-
    # session post-knockout wake. Trigger fires correctly on a real wake event;
    # category claim plausible but unverifiable from context alone.
    ("C1E005_t3244", 0): {
        "verdict": "defensible",
        "expected_category": "OVERNIGHT_REST",
        "expected_surface_form": "diurnal_transition",
        "expected_compression_scope": "scene_exit",
        "expected_buildup_signal": "matt_initiated",
        "failure_family": None,
        "judge_notes": "Raw text too sparse to verify ('As Grog, you come to consciousness again--'). The 'again' suggests prior in-session unconsciousness (knockout-recovery). Preceding 3 turns are OOC about Trinket — D5 has no combat-context tokens to trigger on. Episode position 91.4% admits both end-of-session post-rest framing and mid-session knockout recovery. Defensible: trigger fires on a real wake event but category claim isn't disprovable.",
    },

    # 2. C1E009_t991 — OVERNIGHT_REST (correct)
    # Textbook diurnal transition. Phase-span Stage 0 correctly locates the
    # trigger inside Matt's narration after the OOC sponsor prefix ("All
    # right, so the 826 donation's working again"). Explicit framing:
    # "after an evening's rest, taking your respective turns keeping watch,
    # all of you come to consciousness once more."
    ("C1E009_t991", 0): {
        "verdict": "correct",
        "expected_category": "OVERNIGHT_REST",
        "expected_surface_form": "diurnal_transition",
        "expected_compression_scope": "scene_exit",
        "expected_buildup_signal": "matt_initiated",
        "failure_family": None,
        "judge_notes": None,
    },

    # 3. C1E014_t959 — LOCATION_DEPARTURE (correct)
    # Party walks across the main thoroughfare to Gilmore's Glorious Goods —
    # named shop with its own scene/beat (the bigger-on-the-inside reveal,
    # Gilmore as NPC, etc). Destination scope is scene-level despite being
    # within the same city: the shop interior has a distinct narrative beat.
    # Distinguishable from D3 micro-motion: D3 examples are sub-locations
    # of the *current* scene (rooms within a building); Gilmore's is a
    # destination scene the party is transitioning *to*.
    ("C1E014_t959", 0): {
        "verdict": "correct",
        "expected_category": "LOCATION_DEPARTURE",
        "expected_surface_form": "location_exit",
        "expected_compression_scope": "scene_exit",
        "expected_buildup_signal": "matt_initiated",
        "failure_family": None,
        "judge_notes": None,
    },

    # 4. C1E044_t876 — OVERNIGHT_REST → should be NONE
    # "All of you wake up" caused by a distant screech mid-night. Subsequent
    # text confirms still nighttime: "as there is a very still wind tonight."
    # Spec §4 Shape 2 OVERNIGHT_REST requires diurnal transition to next
    # morning scene. Mid-night disturbance wake is not that shape. Trigger
    # phrase 'you wake up' fires on the wake event without checking whether
    # the wake leads to morning or to a mid-night beat.
    ("C1E044_t876", 0): {
        "verdict": "wrong",
        "expected_category": "NONE",
        "expected_surface_form": None,
        "expected_compression_scope": None,
        "expected_buildup_signal": None,
        "failure_family": "mid_night_disturbance_wake_misrouted_to_overnight_rest",
        "judge_notes": "Mid-night disturbance wake (distant screech), not diurnal transition. Subsequent text 'as there is a very still wind tonight' confirms still nighttime. Spec OVERNIGHT_REST requires next-morning compression. Trigger family 'you wake up' lacks morning-vs-mid-night disambiguation.",
    },

    # 5. C1E049_t3292 — LOCATION_DEPARTURE → should be NONE (D3 combat-microposition)
    # Mid-combat: "You Dimension Door and you appear right at the doorway.
    # You cannot Dimension Door through dimensions. But you make your way
    # to the outside of the door. You are still drifting with the momentum
    # you had going backwards, so you appear back at the door and start
    # going backwards again." This is spell-resolution narration during an
    # active combat round. Same family as Phase 4 gate record C1E011_t3608
    # (combat aim-and-position). Recurring D3 sub-pattern: combat-action
    # micro-positioning that the in-scene-micro-motion filter misses
    # because is_combat_state remained false.
    ("C1E049_t3292", 0): {
        "verdict": "wrong",
        "expected_category": "NONE",
        "expected_surface_form": None,
        "expected_compression_scope": None,
        "expected_buildup_signal": None,
        "failure_family": "in_scene_micro_motion_misrouted_to_location_departure",
        "judge_notes": "D3 in-scene micro-motion: Dimension Door spell-resolution during active combat (preceding turns: death save, push out of grasp, Vex's failed save). 'Make your way to the outside of the door' is spell-effect narration, not scene-level departure. Recurring family with gate C1E011_t3608. is_combat_state false on this record — combat-state detection didn't catch the active combat round.",
    },

    # 6. C1E058_t2889 — TEMPORAL_MONTAGE (correct)
    # Multi-hour day-summary compression. "As you guys spend the rest of the
    # afternoon [...] as the sun sets [...] throughout the day, you can see
    # Allura and Gilmore [...] are beginning to mark areas in the town."
    # Narrative-summary use of 'throughout the day' (during this period,
    # action X is happening), distinct from gate C1E095_t789's atmospheric
    # use ('the sun is ever-shining throughout the day' = state-of-place
    # description).
    ("C1E058_t2889", 0): {
        "verdict": "correct",
        "expected_category": "TEMPORAL_MONTAGE",
        "expected_surface_form": "montage",
        "expected_compression_scope": "scene_exit",
        "expected_buildup_signal": "matt_initiated",
        "failure_family": None,
        "judge_notes": None,
    },

    # 7. C1E091_t2095 — TEMPORAL_MONTAGE → should be NONE (spell duration)
    # "Ten maximum hit point increase to everybody for the next 24 hours"
    # is the effect of a spell (Heroes' Feast: 2d10 max HP for 24 hours).
    # Spec §5.3 explicitly excludes spell duration from TEMPORAL_MONTAGE.
    # D7 (Patch 4 spell/rules-mechanic reject) is the designated filter for
    # this case. Per Phase 5 stats, D7 fired 0 times in the full parse —
    # this validation record is one of its true targets.
    ("C1E091_t2095", 0): {
        "verdict": "wrong",
        "expected_category": "NONE",
        "expected_surface_form": None,
        "expected_compression_scope": None,
        "expected_buildup_signal": None,
        "failure_family": "spell_duration_misrouted_to_temporal_montage",
        "judge_notes": "Spell duration (Heroes' Feast: 2d10 max HP increase for 24 hours). Spec §5.3 explicitly excludes spell-duration from TEMPORAL_MONTAGE. D7/Patch 4 is the designated reject — fired 0 times in full parse, demonstrably under-coverage. Trigger 'for the next 24 hours' on HP-increase phrasing isn't in D7's vocabulary set.",
    },

    # 8. C1E105_t492 — OVERNIGHT_REST → should be NONE (atmospheric)
    # Party flying in mist form. "Sunbeams come through from the morning sun
    # that's rising up higher and higher in the sky as you've traveled."
    # Atmospheric description of forest lighting during active travel — not
    # a wake-from-rest event. Same family as gate C1E095_t789 (descriptive
    # 'throughout the day' at city arrival). Trigger 'morning sun' fires
    # on diurnal-time vocabulary without checking whether the surrounding
    # narrative is wake-from-rest or active-environment description.
    ("C1E105_t492", 0): {
        "verdict": "wrong",
        "expected_category": "NONE",
        "expected_surface_form": None,
        "expected_compression_scope": None,
        "expected_buildup_signal": None,
        "failure_family": "atmospheric_description_misrouted_to_time_compression",
        "judge_notes": "Atmospheric description of forest lighting during active travel ('sunbeams come through from the morning sun that's rising up higher and higher in the sky as you've traveled'). Party is flying, not waking from rest. Recurring family with gate C1E095_t789 — atmospheric/state-of-place phrasing fires the time-compression triggers without narrative-advance disambiguation.",
    },

    # 9. C1E113_t594 — OVERNIGHT_REST (correct)
    # Textbook diurnal transition: "the dark of rest takes you" → "you all
    # awake" → morning sky description ("purple and orange [...] sky that
    # breaks through the canopy"). Multiple within-turn wake-phrases ('as
    # you all awake' / 'You all awake' / 'as you come to consciousness')
    # but D6 either suppressed extras or trigger-phrase ranges spread
    # beyond the 200-char window. Surviving emit is one canonical record
    # for the morning compression.
    ("C1E113_t594", 0): {
        "verdict": "correct",
        "expected_category": "OVERNIGHT_REST",
        "expected_surface_form": "diurnal_transition",
        "expected_compression_scope": "scene_exit",
        "expected_buildup_signal": "matt_initiated",
        "failure_family": None,
        "judge_notes": None,
    },

    # 10. C2E014_t1413 — OVERNIGHT_REST (correct)
    # Textbook diurnal transition with explicit morning framing: "As the
    # morning comes to, you all wake up relatively early [...] It's
    # shortly after sunrise." Phase-span Stage 0 correctly handles the
    # OOC prefix ('Anybody else? Anything? All right then.') by locating
    # the trigger inside Matt's subsequent narration.
    ("C2E014_t1413", 0): {
        "verdict": "correct",
        "expected_category": "OVERNIGHT_REST",
        "expected_surface_form": "diurnal_transition",
        "expected_compression_scope": "scene_exit",
        "expected_buildup_signal": "matt_initiated",
        "failure_family": None,
        "judge_notes": None,
    },

    # 11. C2E020_t577 — OVERNIGHT_REST (defensible)
    # "As you come to consciousness through this evening's rest for your
    # final watch [...] Who is taking the final watch with you?" Wake is
    # FOR the final watch, not for morning. Strictly: not a diurnal
    # transition (the watch is mid-night, before morning). Defensibly:
    # the wake event is within the overnight-rest period and the final
    # watch immediately precedes morning. Borderline category fit.
    ("C2E020_t577", 0): {
        "verdict": "defensible",
        "expected_category": "OVERNIGHT_REST",
        "expected_surface_form": "diurnal_transition",
        "expected_compression_scope": "in_scene",
        "expected_buildup_signal": "matt_initiated",
        "failure_family": None,
        "judge_notes": "Wake is for the final watch (mid-night, pre-morning), not the morning itself. Strict reading: not a diurnal-to-morning transition (raw text confirms 'sleep is probably not going to find its way to you again for the rest of the evening' and 'Who is taking the final watch with you?'). Defensible reading: wake is within the overnight-rest period and the final watch immediately precedes morning. compression_scope=in_scene (still in night-rest period) is more honest than scene_exit.",
    },

    # 12. C2E022_t209 — OVERNIGHT_REST → should be NONE (single-character watch wake)
    # Caleb (Liam) wakes mid-watch in response to a noise: "But a little
    # twinkle hits your ears, Caleb [...] something down below [...] seems
    # to go off." Liam: "I'm awake?" Matt: "Yes, you come to consciousness."
    # Single character, mid-watch, in response to in-fiction stimulus —
    # not a party-wide diurnal transition. Position 8.34% (early episode)
    # rules out recap-state. Trigger phrase 'you come to consciousness'
    # fires on Matt's confirmation utterance without checking party-wide
    # vs single-character or watch-vs-morning context.
    ("C2E022_t209", 0): {
        "verdict": "wrong",
        "expected_category": "NONE",
        "expected_surface_form": None,
        "expected_compression_scope": None,
        "expected_buildup_signal": None,
        "failure_family": "single_character_mid_watch_wake_misrouted_to_overnight_rest",
        "judge_notes": "Caleb wakes mid-watch in response to a noise — single character, in-fiction stimulus response, not party-wide morning transition. Raw text 'Yes, you come to consciousness' is Matt's confirmation of Liam's question 'I'm awake?'. Same broader family as record 4 (mid-night wake) — wake events that aren't diurnal-to-morning being misrouted to OVERNIGHT_REST.",
    },

    # 13. C2E030_t1179 — TEMPORAL_MONTAGE (correct)
    # Travel compression: "You all begin to make your way through this
    # section of the Savalierwood, following the best pathways you can
    # for the next hour, hour and a half before you begin to break into
    # the North Clover area of the city." In-scene travel montage
    # terminating in arrival at North Clover. compression_scope=in_scene
    # is correct (active travel, scene continues with maneuvering beat).
    ("C2E030_t1179", 0): {
        "verdict": "correct",
        "expected_category": "TEMPORAL_MONTAGE",
        "expected_surface_form": "montage",
        "expected_compression_scope": "in_scene",
        "expected_buildup_signal": "matt_initiated",
        "failure_family": None,
        "judge_notes": None,
    },

    # 14. C2E031_t1063 — LOCATION_DEPARTURE (correct)
    # Party transitions to a meeting scene: "You make your way to the
    # subterranean basement of The Evening Nip [...] he does return from
    # the storage room [...] sees you and sits on the other side of the
    # table." The basement is a distinct meeting scene with its own NPC
    # (The Gentleman) and beat. Distinguishable from D3 sub-location
    # navigation by the destination's scene-level distinctness — separate
    # narrative beat opens at the basement, not a continuation of the
    # tavern scene above.
    ("C2E031_t1063", 0): {
        "verdict": "correct",
        "expected_category": "LOCATION_DEPARTURE",
        "expected_surface_form": "location_exit",
        "expected_compression_scope": "scene_exit",
        "expected_buildup_signal": "matt_initiated",
        "failure_family": None,
        "judge_notes": None,
    },

    # 15. C2E043_t924 — OVERNIGHT_REST → should be NONE (combat revival)
    # "All right. So you come to consciousness on the ground." Caleb is
    # revived by a healing potion in combat. Preceding turns include
    # death save (turn 919: "Mark off one of your failed death saving
    # throws"), grappling ("shrug past", "push out of his grasp"), and
    # the explicit revival action (turn 922: "I will pour a healing
    # potion into his mouth"). Spec §6 D5/Patch 1 is the designated
    # condition-recovery polysemy reject — should have caught this.
    ("C2E043_t924", 0): {
        "verdict": "wrong",
        "expected_category": "NONE",
        "expected_surface_form": None,
        "expected_compression_scope": None,
        "expected_buildup_signal": None,
        "failure_family": "healing_potion_revival_misrouted_to_overnight_rest",
        "judge_notes": "Combat revival via healing potion. Preceding turns: death save (turn 919), grappling vocabulary (turn 919), 'I will pour a healing potion into his mouth' (turn 922). D5/Patch 1 condition-recovery-polysemy reject should have fired but didn't — D5's combat-context token list doesn't include healing-potion vocabulary. Same patch-incompleteness pattern as record 7 (D7/Patch 4 missing spell-HP vocabulary).",
    },
}


def apply_verdicts(input_path: str, output_path: str) -> dict:
    """Read v1, apply VERDICTS, write v2. Return summary stats."""
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    data["construction"]["phase"] = "Phase 6 validation v2 (post blind judge)"

    counts = {"correct": 0, "defensible": 0, "wrong": 0, "duplicate": 0}
    failure_families: dict = {}
    per_category_strict: dict = {}

    missing_keys = []

    # validation array (NOT 'gate' — schema difference from gate v2)
    for rec in data["validation"]:
        key = (rec["trigger_id"], rec["same_turn_record_index"])
        if key not in VERDICTS:
            missing_keys.append(key)
            continue

        v = VERDICTS[key]

        rec.pop("verdict_at_v1", None)
        rec.pop("failure_mode", None)

        rec["expected_category"] = v["expected_category"]
        rec["expected_surface_form"] = v["expected_surface_form"]
        rec["expected_compression_scope"] = v["expected_compression_scope"]
        rec["expected_buildup_signal"] = v["expected_buildup_signal"]

        rec["verdict_at_v2"] = v["verdict"]
        rec["failure_family"] = v["failure_family"]
        rec["judge_notes"] = v["judge_notes"]

        counts[v["verdict"]] += 1

        if v["failure_family"]:
            failure_families[v["failure_family"]] = (
                failure_families.get(v["failure_family"], 0) + 1
            )

        cat = rec["extracted_category"]
        if cat not in per_category_strict:
            per_category_strict[cat] = [0, 0]
        per_category_strict[cat][1] += 1
        if v["verdict"] == "correct":
            per_category_strict[cat][0] += 1

    if missing_keys:
        raise RuntimeError(f"Missing verdicts for keys: {missing_keys}")

    total = sum(counts.values())
    strict_precision = counts["correct"] / total if total else 0.0
    defensible_included = (counts["correct"] + counts["defensible"]) / total if total else 0.0
    phase3_handsample_strict = 18 / 27   # 0.6667
    phase4_gate_strict = 16 / 25         # 0.64
    gen_gap_handsample_pp = (strict_precision - phase3_handsample_strict) * 100
    gen_gap_gate_pp = (strict_precision - phase4_gate_strict) * 100

    per_category_strict_fmt = {
        cat: f"{c}/{t} = {(c/t*100):.1f}%" for cat, (c, t) in sorted(per_category_strict.items())
    }

    data["notes"] = (
        "Validation v2 with blind-judge verdicts by Claude. Strict precision = correct/total. "
        "NONE category = should-have-been-rejected (Stage 0 reject family) OR misclassification "
        "target. Validation pool measured 3 of 7 categories (OVERNIGHT_REST=9, LOCATION_DEPARTURE=3, "
        "TEMPORAL_MONTAGE=3) per Phase 5 stratum-proportional sampling. NPC_DEPARTURE, "
        "INVESTIGATIVE_CLOSURE, SCENE_CUT, STALE_HOLD_CANDIDATE unmeasured at validation; their "
        "generalization rests on gate v2 numbers."
    )

    data["v2_summary"] = {
        "judged_at": datetime.now(timezone.utc).isoformat(),
        "judge": "Claude (Phase 6 validation blind pass)",
        "total": total,
        "correct": counts["correct"],
        "defensible": counts["defensible"],
        "wrong": counts["wrong"],
        "duplicate": counts["duplicate"],
        "strict_precision": round(strict_precision, 4),
        "defensible_included_precision": round(defensible_included, 4),
        "phase3_handsample_strict_precision": round(phase3_handsample_strict, 4),
        "phase4_gate_strict_precision": round(phase4_gate_strict, 4),
        "generalization_gap_from_handsample_pp": round(gen_gap_handsample_pp, 2),
        "generalization_gap_from_gate_pp": round(gen_gap_gate_pp, 2),
        "failure_families": dict(sorted(failure_families.items(), key=lambda kv: -kv[1])),
        "per_category_strict": per_category_strict_fmt,
        "categories_measured_at_validation": ["OVERNIGHT_REST", "LOCATION_DEPARTURE", "TEMPORAL_MONTAGE"],
        "categories_unmeasured_at_validation": ["NPC_DEPARTURE", "INVESTIGATIVE_CLOSURE", "SCENE_CUT", "STALE_HOLD_CANDIDATE"],
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return data["v2_summary"]


if __name__ == "__main__":
    if not os.path.exists(INPUT_PATH):
        raise SystemExit(f"Input not found: {INPUT_PATH}")

    summary = apply_verdicts(INPUT_PATH, OUTPUT_PATH)
    print(f"Wrote {OUTPUT_PATH}")
    print(json.dumps(summary, indent=2))
