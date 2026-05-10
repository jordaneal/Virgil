#!/usr/bin/env python3
"""
cc_gate_v2_apply.py
Compression Cadence — Phase 4 gate v2 apply script.

Reads compression_cadence_gate_v1.json, applies blind-judge verdicts,
writes compression_cadence_gate_v2.json. Mirrors loot_reward Phase 4 pattern.

Usage (from corpus/eval_sets/ on server):
    python3 cc_gate_v2_apply.py
"""
import json
import os
from datetime import datetime, timezone

INPUT_PATH = "compression_cadence_gate_v1.json"
OUTPUT_PATH = "compression_cadence_gate_v2.json"

# ---------------------------------------------------------------------------
# Verdict dict. Key: (trigger_id, same_turn_record_index).
# Each value is a dict with:
#   verdict         : "correct" | "defensible" | "wrong" | "duplicate"
#   expected_*      : judged values (mirror extracted_* on correct)
#   failure_family  : str | None
#   judge_notes     : str | None
# ---------------------------------------------------------------------------
VERDICTS = {
    # 1. C1E011_t1064 — INVESTIGATIVE_CLOSURE
    # Spec §4 Shape 5 cites this exact record as a recon true positive.
    # "Nothing to find purchase for" is in the §5.5 trigger-shape list.
    # The literal climbing-grip sense vs. the discovery sense is a known
    # dual-read; spec author classified it as INVESTIGATIVE_CLOSURE. Match.
    ("C1E011_t1064", 0): {
        "verdict": "correct",
        "expected_category": "INVESTIGATIVE_CLOSURE",
        "expected_surface_form": "investigation_closed",
        "expected_compression_scope": "in_scene",
        "expected_buildup_signal": "matt_initiated",
        "failure_family": None,
        "judge_notes": None,
    },

    # 2. C1E011_t1655 — INVESTIGATIVE_CLOSURE → should be OVERNIGHT_REST
    # Raw text: "after an evening of taking turns resting [...] nothing
    # catches your eye [...] Eventually you all come to. Your Fomorian
    # friend is just sitting there [...] staring at the rest of the group."
    # The dominant compression event is the overnight watch + waking, not
    # an investigation closure. "Nothing catches your eye" is watch-period
    # observation, not a §5.5 trigger shape (not in the listed family).
    # Misroute: INVESTIGATIVE_CLOSURE family caught a non-listed phrase
    # while the legitimate OVERNIGHT_REST signals ("evening of resting",
    # "Eventually you all come to") were not selected as trigger.
    ("C1E011_t1655", 0): {
        "verdict": "wrong",
        "expected_category": "OVERNIGHT_REST",
        "expected_surface_form": "diurnal_transition",
        "expected_compression_scope": "scene_exit",
        "expected_buildup_signal": "matt_initiated",
        "failure_family": "watch_pass_uneventful_misrouted_to_investigative_closure",
        "judge_notes": "Trigger 'nothing catches your eye' is not in §5.5 INVESTIGATIVE_CLOSURE shape list. Real compression event is the overnight watch passing into morning ('after an evening of taking turns resting [...] Eventually you all come to'). Should have fired OVERNIGHT_REST on the diurnal transition. Watch-pass-uneventful is the §5 not-proposed WATCH_PASS shape resolved as OVERNIGHT_REST adjacent.",
    },

    # 3. C1E011_t3608 — LOCATION_DEPARTURE → should be NONE (D3 micro-motion)
    # Combat positioning during a single attack action. Preceding turn:
    # "I go around the other way." Matt: "Yeah, so you make your way to
    # here. You kneel down with the Bad News. You aim..." This is intra-
    # combat repositioning to take a shot. Stage 0 D3 reject (in-scene
    # micro-motion). Same family as spec §6 D3 examples ("you make your
    # way up to the secondary floor").
    ("C1E011_t3608", 0): {
        "verdict": "wrong",
        "expected_category": "NONE",
        "expected_surface_form": None,
        "expected_compression_scope": None,
        "expected_buildup_signal": None,
        "failure_family": "in_scene_micro_motion_misrouted_to_location_departure",
        "judge_notes": "D3 in-scene micro-motion: combat repositioning ('go around the other way' → 'make your way to here. You kneel down [...] aim'). Destination is a position within the active combat scene, not a scene-level location. Stage 0 D3 reject did not fire on this combat-positioning sub-pattern.",
    },

    # 4. C1E053_t981 — INVESTIGATIVE_CLOSURE
    # Spec §4 Shape 5 cites this exact record. Textbook investigation
    # closure following an explicit room-search investigation check.
    ("C1E053_t981", 0): {
        "verdict": "correct",
        "expected_category": "INVESTIGATIVE_CLOSURE",
        "expected_surface_form": "investigation_closed",
        "expected_compression_scope": "in_scene",
        "expected_buildup_signal": "matt_initiated",
        "failure_family": None,
        "judge_notes": None,
    },

    # 5. C1E053_t1911 — SCENE_CUT
    # Spec §4 Shape 1 cites this exact record. "As this time has passed,
    # you guys do return to the mansion" is the editorial-cut form with
    # implicit duration (TM overlap = true is correct; spec notes overlap
    # is possible when cut also states a duration).
    ("C1E053_t1911", 0): {
        "verdict": "correct",
        "expected_category": "SCENE_CUT",
        "expected_surface_form": "explicit_cut",
        "expected_compression_scope": "scene_exit",
        "expected_buildup_signal": "matt_initiated",
        "failure_family": None,
        "judge_notes": None,
    },

    # 6. C1E053_t2179 — OVERNIGHT_REST
    # Spec §4 Shape 2 cites this exact record. Pre-dawn hour of the
    # following morning following an explicit "evening's rest" prompt.
    ("C1E053_t2179", 0): {
        "verdict": "correct",
        "expected_category": "OVERNIGHT_REST",
        "expected_surface_form": "diurnal_transition",
        "expected_compression_scope": "scene_exit",
        "expected_buildup_signal": "matt_initiated",
        "failure_family": None,
        "judge_notes": None,
    },

    # 7. C1E053_t2183 — NPC_DEPARTURE → should be LOCATION_DEPARTURE
    # Subject of the "exit" trigger is "you guys" (PCs), not an NPC.
    # No NPC departs in this turn — two figures STAND UP across the
    # street as the PCs exit. The NPC_DEPARTURE family caught the right
    # phrase shape ("exit the room", "exit the building") but the wrong
    # subject. The actual compression is a scene-level location exit
    # (Wilhand's place → street, with new beat opening — surveillance).
    ("C1E053_t2183", 0): {
        "verdict": "wrong",
        "expected_category": "LOCATION_DEPARTURE",
        "expected_surface_form": "location_exit",
        "expected_compression_scope": "scene_exit",
        "expected_buildup_signal": "matt_initiated",
        "failure_family": "pc_exit_misrouted_to_npc_departure",
        "judge_notes": "Subject of the 'exit' trigger is 'you guys' (PCs), not an NPC. No NPC departs — two figures stand up across the street as the PCs exit. NPC_DEPARTURE family triggers on phrase shape regardless of subject. The actual compression is PC-driven LOCATION_DEPARTURE (Wilhand's place → street, new surveillance beat).",
    },

    # 8. C1E095_t665 — TEMPORAL_MONTAGE
    # Spec §4 Shape 3 cites this exact record ("as the months go by").
    # Multi-month arc compression. Note: Patch 3-style "Awesome. All
    # right." OOC prefix is correctly NOT triggering D1 reject because
    # phrase-span Stage 0 locates the trigger inside Matt's narration.
    ("C1E095_t665", 0): {
        "verdict": "correct",
        "expected_category": "TEMPORAL_MONTAGE",
        "expected_surface_form": "montage",
        "expected_compression_scope": "scene_exit",
        "expected_buildup_signal": "matt_initiated",
        "failure_family": None,
        "judge_notes": None,
    },

    # 9. C1E095_t783 — LOCATION_DEPARTURE
    # Spec §4 Shape 6 cites this exact record. Multi-region travel
    # ("Emon → Ozmit Sea → Marquet → Shamal"). Clear scene-level
    # destination scope (named cities/continents), exactly the
    # destination-scope contrast that the spec's TENTATIVE LOCATION_
    # DEPARTURE category was intended to capture.
    ("C1E095_t783", 0): {
        "verdict": "correct",
        "expected_category": "LOCATION_DEPARTURE",
        "expected_surface_form": "location_exit",
        "expected_compression_scope": "scene_exit",
        "expected_buildup_signal": "matt_initiated",
        "failure_family": None,
        "judge_notes": None,
    },

    # 10. C1E095_t789 — TEMPORAL_MONTAGE → should be NONE
    # "Throughout the day" here is descriptive (atmospheric description
    # of the city's typical conditions), not narrative time compression.
    # Next sentence: "as you arrived here about midday or so" — the
    # party JUST ARRIVED. No day has been compressed; the phrase is
    # describing what the city is LIKE.
    ("C1E095_t789", 0): {
        "verdict": "wrong",
        "expected_category": "NONE",
        "expected_surface_form": None,
        "expected_compression_scope": None,
        "expected_buildup_signal": None,
        "failure_family": "atmospheric_throughout_day_misread_as_montage",
        "judge_notes": "'Throughout the day' is meteorological/atmospheric ('the sun is ever-shining throughout the day') describing the city's typical conditions, not narrative compression. Next sentence confirms: 'as you arrived here about midday or so' — party just arrived, no time compressed forward. TEMPORAL_MONTAGE trigger family needs a narrative-advance vs. descriptive-locational disambiguation.",
    },

    # 11. C1E095_t1658 — TEMPORAL_MONTAGE
    # Spec §4 Shape 3 cites this exact record. "Over the course of the
    # evening, the room gets cleaned" — short scene-level evening
    # compression. compression_scope=UNKNOWN is honest given no forward
    # context in the trigger turn (§13.7a allows UNKNOWN).
    ("C1E095_t1658", 0): {
        "verdict": "correct",
        "expected_category": "TEMPORAL_MONTAGE",
        "expected_surface_form": "montage",
        "expected_compression_scope": "UNKNOWN",
        "expected_buildup_signal": "matt_initiated",
        "failure_family": None,
        "judge_notes": None,
    },

    # 12. C2E011_t152 — OVERNIGHT_REST
    # "You all come to consciousness" preceded by "should try to sleep"
    # → players sleep → "daylight greets you, [...] the morning". This
    # is the Patch 1 condition-recovery test case: the phrase fires on
    # a true overnight rest (no combat/abduction context). Patch 1
    # correctly NOT rejecting this proves Patch 1 is properly scoped.
    ("C2E011_t152", 0): {
        "verdict": "correct",
        "expected_category": "OVERNIGHT_REST",
        "expected_surface_form": "diurnal_transition",
        "expected_compression_scope": "scene_exit",
        "expected_buildup_signal": "matt_initiated",
        "failure_family": None,
        "judge_notes": None,
    },

    # 13. C2E011_t763 — NPC_DEPARTURE
    # Textbook NPC departure: NPC says "I need to go [...] good bye"
    # then "darts out into the rain". Heterogeneous turn (NPC dialogue
    # + Matt narration of the exit). Phrase-span Stage 0 correctly
    # locates the trigger inside Matt's narration ("exit the chamber").
    ("C2E011_t763", 0): {
        "verdict": "correct",
        "expected_category": "NPC_DEPARTURE",
        "expected_surface_form": "npc_exit",
        "expected_compression_scope": "in_scene",
        "expected_buildup_signal": "matt_initiated",
        "failure_family": None,
        "judge_notes": None,
    },

    # 14. C2E011_t1537 — NPC_DEPARTURE (defensible: trigger-phrase precision)
    # Spec §4 Shape 4 cites this exact record. Category is correct: an
    # NPC departure DOES occur in the turn ("the other three exit the
    # building"). However, the chosen trigger_phrase is "take a different
    # table" — Ulog's REPOSITIONING within the building, not a departure.
    # Within-turn-dedup-first-match selected the worse-fit trigger.
    # Acceptable as defensible: category claim correct, trigger phrase
    # imprecise due to dedup ordering.
    ("C2E011_t1537", 0): {
        "verdict": "defensible",
        "expected_category": "NPC_DEPARTURE",
        "expected_surface_form": "npc_exit",
        "expected_compression_scope": "in_scene",
        "expected_buildup_signal": "matt_initiated",
        "failure_family": None,
        "judge_notes": "Category claim is correct (NPC departure occurs: 'the other three exit the building'). However, chosen trigger_phrase is 'take a different table' — Ulog repositions within the building, doesn't depart. Within-turn-dedup-first-match selected the wrong instance. Spec §5.4 trigger 'head back to their [seat/table]' is for NPC ending interaction, not surveilling-repositioning. Acceptable but trigger-phrase precision could improve with within-turn ranked-match instead of first-match.",
    },

    # 15. C2E011_t1849 (idx 1) — OVERNIGHT_REST → DUPLICATE (within-turn)
    # Same turn as record idx 0. Both trigger OVERNIGHT_REST on phrases
    # within ~6 chars of each other ("find yourselves to rest for the
    # evening" + "you awaken"/"awaking in the early morning"). Patch 2
    # within-turn dedup should have suppressed the second emit. It did
    # not — likely because the surface_form match strategy tracked the
    # category but missed this phrase pair as same-event.
    ("C2E011_t1849", 1): {
        "verdict": "duplicate",
        "expected_category": "NONE",
        "expected_surface_form": None,
        "expected_compression_scope": None,
        "expected_buildup_signal": None,
        "failure_family": "within_turn_dedup_failed_overnight_rest",
        "judge_notes": "Same turn as idx 0; both fire OVERNIGHT_REST on the same diurnal-transition event. Two trigger phrases ('find yourselves to rest for the evening' + 'you awaken'/'awaking in the early morning') sit within ~6 chars in the same sentence. Patch 2 within-turn dedup should have kept only idx 0. Suspect Patch 2's same-category proximity check is keyed on something other than (category, turn_id) — perhaps surface_form or phrase-span — that allowed both to survive.",
    },

    # 16. C2E011_t1849 (idx 0) — OVERNIGHT_REST (kept by within-turn dedup)
    # Spec §4 Shape 2 cites this exact record. The first match in the
    # turn is correctly retained as the canonical OVERNIGHT_REST emit.
    ("C2E011_t1849", 0): {
        "verdict": "correct",
        "expected_category": "OVERNIGHT_REST",
        "expected_surface_form": "diurnal_transition",
        "expected_compression_scope": "scene_exit",
        "expected_buildup_signal": "matt_initiated",
        "failure_family": None,
        "judge_notes": None,
    },

    # 17. C2E027_t399 — LOCATION_DEPARTURE
    # Spec §4 Shape 6 cites this exact record. "Gather the last of your
    # things, retrieve the horses, and head out" — clean party-exit-
    # location compression following an emotional NPC interaction beat.
    ("C2E027_t399", 0): {
        "verdict": "correct",
        "expected_category": "LOCATION_DEPARTURE",
        "expected_surface_form": "location_exit",
        "expected_compression_scope": "scene_exit",
        "expected_buildup_signal": "matt_initiated",
        "failure_family": None,
        "judge_notes": None,
    },

    # 18. C2E027_t414 — TEMPORAL_MONTAGE
    # "Continue on your journey for the next hour or so before you catch
    # a glance [...] You see three shapes in the road." In-scene travel
    # compression terminating in a discovery beat. compression_scope=
    # in_scene is correct (still traveling, scene continues with new
    # encounter beat).
    ("C2E027_t414", 0): {
        "verdict": "correct",
        "expected_category": "TEMPORAL_MONTAGE",
        "expected_surface_form": "montage",
        "expected_compression_scope": "in_scene",
        "expected_buildup_signal": "matt_initiated",
        "failure_family": None,
        "judge_notes": None,
    },

    # 19. C2E027_t523 — OVERNIGHT_REST
    # "Nothing of note happens during your watch [...] As the morning
    # comes to". Watch-pass-into-morning shape — the §5 not-proposed
    # WATCH_PASS resolved as OVERNIGHT_REST adjacent. Diurnal transition
    # is the dominant signal.
    ("C2E027_t523", 0): {
        "verdict": "correct",
        "expected_category": "OVERNIGHT_REST",
        "expected_surface_form": "diurnal_transition",
        "expected_compression_scope": "scene_exit",
        "expected_buildup_signal": "matt_initiated",
        "failure_family": None,
        "judge_notes": None,
    },

    # 20. C2E027_t550 — TEMPORAL_MONTAGE
    # Spec §4 Shape 3 cites this exact record. Multi-day travel montage
    # ("for the next day [...] mid to late afternoon") terminating at a
    # new scene-level location (Quannah Breach outpost). buildup_signal=
    # objective_completion is defensible (party objective is reaching
    # the breach; compression telegraphs arrival).
    ("C2E027_t550", 0): {
        "verdict": "correct",
        "expected_category": "TEMPORAL_MONTAGE",
        "expected_surface_form": "montage",
        "expected_compression_scope": "scene_exit",
        "expected_buildup_signal": "objective_completion",
        "failure_family": None,
        "judge_notes": None,
    },

    # 21. C2E027_t1042 — SCENE_CUT
    # Spec §4 Shape 1 cites this exact record. Canonical "Cut to black"
    # — minimum-surface explicit-cut form.
    ("C2E027_t1042", 0): {
        "verdict": "correct",
        "expected_category": "SCENE_CUT",
        "expected_surface_form": "explicit_cut",
        "expected_compression_scope": "scene_exit",
        "expected_buildup_signal": "player_intent",
        "failure_family": None,
        "judge_notes": None,
    },

    # 22. C2E037_t207 — LOCATION_DEPARTURE → should be NONE (D3 micro-motion)
    # "Make your way to the top of the deck" — internal navigation on
    # the same ship. Destination is a sub-location of the current scene
    # (the ship), not a new named scene-level location. Spec §6 D3
    # examples include "you make your way up to the secondary floor",
    # which matches this pattern exactly. Stage 0 D3 reject did not
    # fire on this ship-internal navigation sub-pattern.
    ("C2E037_t207", 0): {
        "verdict": "wrong",
        "expected_category": "NONE",
        "expected_surface_form": None,
        "expected_compression_scope": None,
        "expected_buildup_signal": None,
        "failure_family": "in_scene_micro_motion_misrouted_to_location_departure",
        "judge_notes": "D3 in-scene micro-motion. Destination 'the top of the deck' is a sub-location of the current scene (the ship being boarded), matching spec §6 D3 example pattern ('you make your way up to the secondary floor'). The encounter that follows is on the same ship, not a new named scene-level location. Same family as C1E011_t3608 — both are D3 sub-patterns the calibrated extractor doesn't catch.",
    },

    # 23. C2E037_t1351 — STALE_HOLD_CANDIDATE (defensible)
    # stale_signal_count_preceding=3 meets the §5/§13.3a single-extractor
    # threshold (≥3 stale signals in preceding window). The category is
    # explicitly "_CANDIDATE" — partial-signal-by-design per §13.3a.
    # However, the immediate prompt follows a substantial reveal (water
    # draining, ancient circle revealed), so this isn't a "true" stale-
    # hold in the analytical sense — Matt is prompting after new info,
    # not on a repetitive beat. Acceptable as candidate-level signal
    # the spec explicitly designs as partial-coverage Q6.
    ("C2E037_t1351", 0): {
        "verdict": "defensible",
        "expected_category": "STALE_HOLD_CANDIDATE",
        "expected_surface_form": "stale_hold",
        "expected_compression_scope": "UNKNOWN",
        "expected_buildup_signal": "repeated_stale_signal",
        "failure_family": None,
        "judge_notes": "Cluster criterion (≥3 prior stale signals) is met — extractor's single-extractor Q6 partial-signal threshold per §5/§13.3a fires correctly. However, the immediate 'what do you do?' follows a substantial new-info reveal (water draining, ancient circle), not a repetitive beat. The _CANDIDATE suffix is honest about partial coverage; downstream Q6 analysis would filter these against scene-aliveness signals not available single-extractor. Defensible as designed-partial Phase 1 signal.",
    },

    # 24. C2E037_t1393 — OVERNIGHT_REST (defensible: dream-end vs. morning)
    # "And you wake up. [applause]" — Fjord wakes from a visionary dream
    # sequence. Literally a wake-up event (he WAS sleeping/dreaming).
    # The applause is meta-theatrical; the actual morning narration is
    # in t1398 (record 25), 5 turns later. Borderline: the wake event
    # is real, but the dramatic compression is dream-end + audience
    # punctuation, with the morning compression deferred to t1398.
    # Defensible — category is correct, framing is dream-bound.
    ("C2E037_t1393", 0): {
        "verdict": "defensible",
        "expected_category": "OVERNIGHT_REST",
        "expected_surface_form": "diurnal_transition",
        "expected_compression_scope": "scene_exit",
        "expected_buildup_signal": "matt_initiated",
        "failure_family": None,
        "judge_notes": "Fjord wakes from a visionary dream — literally a sleep-end event, so OVERNIGHT_REST is defensible. The dramatic framing is dream-end + audience applause; the actual morning narration is in t1398 (record 25), 5 turns later. Cross-turn dedup not part of Phase 3 patches, so emitting both is by design. Borderline between 'wake-up trigger fires correctly on a real event' and 'this is dream-end punctuation, not the canonical diurnal compression'. Defensible.",
    },

    # 25. C2E037_t1398 — OVERNIGHT_REST
    # Spec §4 Shape 2 cites this exact record. "As the rest of you come
    # to consciousness in the morning" — clean diurnal transition. Patch
    # 1 condition-recovery does NOT apply (no combat preceding; the
    # dream-vision in t1388-1393 is a vision sequence, not combat).
    ("C2E037_t1398", 0): {
        "verdict": "correct",
        "expected_category": "OVERNIGHT_REST",
        "expected_surface_form": "diurnal_transition",
        "expected_compression_scope": "scene_exit",
        "expected_buildup_signal": "matt_initiated",
        "failure_family": None,
        "judge_notes": None,
    },
}


def apply_verdicts(input_path: str, output_path: str) -> dict:
    """Read v1, apply VERDICTS, write v2. Return summary stats."""
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Update construction block
    data["construction"]["phase"] = "Phase 4 gate-set v2 (post blind judge)"

    counts = {"correct": 0, "defensible": 0, "wrong": 0, "duplicate": 0}
    failure_families: dict = {}
    per_category_strict: dict = {}  # extracted_category -> [correct_n, total_n]

    missing_keys = []

    for rec in data["gate"]:
        key = (rec["trigger_id"], rec["same_turn_record_index"])
        if key not in VERDICTS:
            missing_keys.append(key)
            continue

        v = VERDICTS[key]

        # Drop v1 placeholder fields
        rec.pop("verdict_at_v1", None)
        rec.pop("failure_mode", None)

        # Populate expected_*
        rec["expected_category"] = v["expected_category"]
        rec["expected_surface_form"] = v["expected_surface_form"]
        rec["expected_compression_scope"] = v["expected_compression_scope"]
        rec["expected_buildup_signal"] = v["expected_buildup_signal"]

        # Add v2 verdict fields
        rec["verdict_at_v2"] = v["verdict"]
        rec["failure_family"] = v["failure_family"]
        rec["judge_notes"] = v["judge_notes"]

        # Accumulate counts
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
    phase3_strict = 18 / 27  # 0.6667 — handsample v2 calibration result
    gen_gap_pp = (strict_precision - phase3_strict) * 100

    per_category_strict_fmt = {
        cat: f"{c}/{t} = {(c/t*100):.1f}%" for cat, (c, t) in sorted(per_category_strict.items())
    }

    data["notes"] = (
        "Gate-set v2 with blind-judge verdicts by Claude. Strict precision = correct/total. "
        "NONE category = should-have-been-rejected (Stage 0 reject family) OR misclassification "
        "target (e.g. NPC_DEPARTURE misrouted from PC subject; LOCATION_DEPARTURE misrouted from "
        "in-scene micro-motion). 'duplicate' verdict = within-turn dedup failure; expected_category "
        "is NONE because the record should not have been emitted independently."
    )

    data["v2_summary"] = {
        "judged_at": datetime.now(timezone.utc).isoformat(),
        "judge": "Claude (Phase 4 gate blind pass)",
        "total": total,
        "correct": counts["correct"],
        "defensible": counts["defensible"],
        "wrong": counts["wrong"],
        "duplicate": counts["duplicate"],
        "strict_precision": round(strict_precision, 4),
        "defensible_included_precision": round(defensible_included, 4),
        "phase3_calibration_strict_precision": round(phase3_strict, 4),
        "generalization_gap_pp": round(gen_gap_pp, 2),
        "failure_families": dict(sorted(failure_families.items(), key=lambda kv: -kv[1])),
        "per_category_strict": per_category_strict_fmt,
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
