"""Apply the Phase 2 spot-check verdicts to compression_cadence_handsample_v1.json,
producing compression_cadence_handsample_v2.json.

Run from /home/jordaneal/corpus_builder/eval_sets/ (or any dir with the v1 file).
"""
import json
from datetime import datetime, timezone
from collections import Counter

# Verdicts: (trigger_id, same_turn_record_index) -> (verdict, expected_category, expected_surface_form, expected_compression_scope, expected_buildup_signal, failure_family, judge_notes)
VERDICTS = {
  ("C1E004_t620", 0): ("wrong", "NONE", None, None, None, "spell_prep_directive", "\"go ahead and choose your spells accordingly for the next day\" is OOC table direction for spell preparation, not narrating compressed time. Same family as Time-Mention's D2 spell-mechanic-talk filter. Scene continues into the evening rest."),
  ("C1E004_t628", 0): ("defensible", "OVERNIGHT_REST", "diurnal_transition", "scene_exit", "matt_initiated", "partial_rest_interruption", "Partial-rest interruption (waking 4hrs into evening rest due to a tremor) rather than clean overnight diurnal transition. Compression decision is real but scope is partial-rest, not full overnight. Borderline."),
  ("C1E004_t2185", 0): ("wrong", "NONE", None, None, None, "ooc_audience_address", "\"Those who can will be here for the Q and A for the next hour or so.\" Pure OOC — Matt addressing the audience about post-game Q&A panel. D1 OOC scheduling family."),
  ("C1E013_t1673", 0): ("wrong", "NONE", None, None, None, "verb_as_noun_modifier", "\"There's a single doorway that exits the room\" — \"exits\" is the doorway's function (verb-as-relative-clause), not an NPC departure. Trigger phrase shape match without semantic match. Homonym FP."),
  ("C1E013_t1865", 0): ("correct", "LOCATION_DEPARTURE", "location_exit", "scene_exit", "matt_initiated", None, None),
  ("C1E013_t2177", 0): ("correct", "OVERNIGHT_REST", "diurnal_transition", "scene_exit", "player_intent", None, None),
  ("C1E025_t583", 0): ("wrong", "NONE", None, None, None, "condition_recovery_misread_as_overnight", "\"as you come to consciousness\" with Briarwood standing over the PC — recovering from being knocked out mid-combat scene, not overnight rest. Same family as Loot/Reward's condition_recovery_misread_as_knowledge. Trigger-phrase polysemy."),
  ("C1E036_t355", 0): ("correct", "TEMPORAL_MONTAGE", "montage", "scene_exit", "matt_initiated", None, None),
  ("C1E036_t574", 0): ("correct", "TEMPORAL_MONTAGE", "montage", "scene_exit", "matt_initiated", None, None),
  ("C1E036_t584", 0): ("correct", "OVERNIGHT_REST", "diurnal_transition", "scene_exit", "matt_initiated", None, None),
  ("C1E036_t943", 0): ("wrong", "NONE", None, None, None, "production_segment_announcement", "\"we have been able to present to you over the next 20 minutes, the story of Vox Machina\" — pure OOC, Matt announcing a 20-minute pre-recorded animated short the audience is about to watch. D1 OOC (production-segment talk)."),
  ("C1E036_t1312", 0): ("wrong", "NONE", None, None, None, "stream_meta_guest_intro", "\"he's been live-tweeting throughout the evening\" / Chris Perkins guest intro — OOC stream meta. D1 OOC."),
  ("C1E050_t1405", 0): ("correct", "TEMPORAL_MONTAGE", "montage", "UNKNOWN", "player_intent", None, None),
  ("C1E050_t1486", 0): ("correct", "TEMPORAL_MONTAGE", "montage", "scene_exit", "matt_initiated", None, None),
  ("C1E050_t1510", 0): ("correct", "OVERNIGHT_REST", "diurnal_transition", "scene_exit", "matt_initiated", None, None),
  ("C1E050_t1867", 0): ("wrong", "NONE", None, None, None, "in_scene_micro_motion_within_town", "\"Eventually you make your way to the central town square\" — Westruun street-level navigation. Whole turn is detailed in-scene movement description. Sub-scale destination, not city/region departure. D3 micro-motion FP. Spec §7 FP2 prediction confirmed."),
  ("C1E050_t1995", 0): ("wrong", "NONE", None, None, None, "episode_end_ooc_framing", "\"And that's where we'll end tonight's game. (yelling)\" Episode-end OOC framing. Spec §9 explicitly identifies this shape. D1 OOC."),
  ("C1E056_t77", 0): ("wrong", "NONE", None, None, None, "convention_scheduling", "\"a couple panels throughout the week, as well as the main Geek and Sundry panel\" — convention/panel scheduling OOC. Already pre-flagged by Code as known FP. D1 OOC."),
  ("C1E056_t830", 0): ("correct", "OVERNIGHT_REST", "diurnal_transition", "scene_exit", "matt_initiated", None, None),
  ("C1E056_t1132", 0): ("wrong", "NONE", None, None, None, "subject_misattribution", "\"the remnants of the horde leaving westward behind the group of heroes\" — the \"leaving\" subject is the horde (NPCs), not the party. Trigger fired on wrong subject. Same shape family as Loot/Reward's hostile_npc_action_misread."),
  ("C1E056_t1582", 0): ("correct", "OVERNIGHT_REST", "diurnal_transition", "scene_exit", "matt_initiated", None, None),
  ("C1E056_t1582", 1): ("duplicate", "NONE", None, None, None, "within_turn_dedup_miss", "Same turn as C1E056_t1582 idx0 (\"the morning light\"). Two overlapping triggers in one turn referring to the same overnight compression event. Within-turn dedup should have caught this."),
  ("C1E056_t2018", 0): ("wrong", "NONE", None, None, None, "projective_future_montage", "\"most of the people, at least over the next week or so, will be outfitted\" — forward projection of what WILL happen, not a compression to a future point. Scene continues in present-moment council. Subjunctive/future-tense vocabulary."),
  ("C1E056_t2247", 0): ("wrong", "NONE", None, None, None, "episode_end_ooc_framing", "\"And that's where we'll end tonight's game\" — same shape as C1E050_t1995. D1 OOC episode-end framing."),
  ("C1E088_t263", 0): ("wrong", "NONE", None, None, None, "spell_duration_mechanic", "\"you guys are able to imbue, for the next 24 hours, Water Breathing onto the party\" — spell duration mechanic-talk. Same family as Time-Mention's D2 spell-duration filter."),
  ("C1E088_t741", 0): ("correct", "TEMPORAL_MONTAGE", "montage", "in_scene", "player_intent", None, None),
  ("C1E088_t4378", 0): ("wrong", "NONE", None, None, None, "condition_recovery_misread_as_overnight", "\"Keyleth, it's your turn. You come to consciousness. Once more you watch as Vax is darting off and a tentacle wraps around him\" — mid-combat condition recovery. Trigger-phrase polysemy. Same family as t583."),
  ("C1E090_t361", 0): ("correct", "NPC_DEPARTURE", "npc_exit", "in_scene", "matt_initiated", None, None),
  ("C1E090_t1317", 0): ("wrong", "NONE", None, None, None, "in_scene_micro_motion_approach", "\"You make your way to the structure\" — approach-to-and-enter the Cobalt Reserve building, then full interior description follows. Already pre-flagged by Code as known FP. D3 micro-motion."),
  ("C1E090_t1788", 0): ("correct", "NPC_DEPARTURE", "npc_exit", "in_scene", "matt_initiated", None, None),
  ("C1E090_t1868", 0): ("wrong", "LOCATION_DEPARTURE", "location_exit", "scene_exit", "player_intent", "category_misroute_party_action_as_npc", "\"And comes running after you guys as you exit the shop\" — the party is exiting the shop (Doty is the NPC chasing them). Trigger fired on party-departure phrase but classified as NPC_DEPARTURE. Real compression but wrong category. Reclassify as LOCATION_DEPARTURE."),
  ("C1E090_t2032", 0): ("correct", "LOCATION_DEPARTURE", "location_exit", "scene_exit", "matt_initiated", None, None),
  ("C1E090_t2574", 0): ("correct", "OVERNIGHT_REST", "diurnal_transition", "scene_exit", "matt_initiated", None, None),
  ("C1E090_t2695", 0): ("correct", "TEMPORAL_MONTAGE", "montage", "in_scene", "matt_initiated", None, None),
  ("C1E090_t2695", 1): ("wrong", "NONE", None, None, None, "descriptive_use_within_compression_turn", "\"shadows tend to linger throughout the day\" — descriptive use of \"throughout the day\" inside a flora/scene description. The compression already fired correctly on idx0 of the same turn. Over-emission within turn."),
  ("C1E093_t1430", 0): ("wrong", "NONE", None, None, None, "condition_recovery_misread_as_overnight", "\"Ten. So you have ten hit points. And you come to consciousness.\" — Healing from 0 HP back to consciousness mid-combat. Same family as t583, t4378."),
  ("C1E097_t960", 0): ("correct", "OVERNIGHT_REST", "diurnal_transition", "scene_exit", "matt_initiated", None, None),
  ("C1E097_t960", 1): ("duplicate", "NONE", None, None, None, "within_turn_dedup_miss", "Same turn as C1E097_t960 idx0 (\"the morning comes\"). Two overlapping triggers (\"the morning comes\" + \"you wake up\") on same compression event. Within-turn dedup miss."),
  ("C1E097_t1348", 0): ("correct", "TEMPORAL_MONTAGE", "montage", "in_scene", "matt_initiated", None, None),
  ("C1E097_t1375", 0): ("wrong", "NONE", None, None, None, "condition_recovery_misread_as_overnight", "\"Taryon, you come to consciousness ever so slightly, and looking down, you see hooves clattering\" — Taryon waking from being kidnapped/transported on horseback. Condition recovery during abduction scene."),
  ("C1E097_t1462", 0): ("wrong", "NONE", None, None, None, "condition_recovery_misread_as_overnight", "\"Taryon, as you've come to consciousness on the back of this horse\" — same scene as t1375, continued kidnapping awareness."),
  ("C1E097_t1537", 0): ("wrong", "NONE", None, None, None, "logistical_question_not_compression", "\"By the way, did you leave Doty behind or take Doty with you?\" — Matt asking a logistical party-composition question. The Wind Walk is the actual scene transition; \"leave Doty behind\" trigger fired on a non-compression phrase about NPC inclusion."),
}

def main():
    src = json.load(open("compression_cadence_handsample_v1.json"))
    recs = src["handsample"]
    out_recs = []
    for r in recs:
        key = (r["trigger_id"], r["same_turn_record_index"])
        if key not in VERDICTS:
            print(f"WARNING: no verdict for {key}")
            continue
        verdict, exp_cat, exp_sf, exp_cs, exp_bs, family, notes = VERDICTS[key]
        new_r = dict(r)
        if verdict == "correct":
            # keep self-reference values from v1
            pass
        else:
            new_r["expected_category"] = exp_cat
            new_r["expected_surface_form"] = exp_sf
            new_r["expected_compression_scope"] = exp_cs
            new_r["expected_buildup_signal"] = exp_bs
        new_r["verdict_at_v2"] = verdict
        new_r["failure_family"] = family
        new_r["judge_notes"] = notes
        new_r.pop("verdict_at_v1", None)
        new_r.pop("failure_mode", None)
        out_recs.append(new_r)

    from collections import Counter
    out = {
        "construction": dict(src["construction"]),
        "handsample": out_recs,
        "notes": "Eval-set v2 with blind-judge verdicts by Claude (Phase 2 spot-check). NONE category = should-have-been-rejected (DISCOURSE reject family) OR misclassification target. duplicate = within-turn over-emission (not strictly wrong but should not have been emitted as separate record).",
        "v2_summary": {
            "judged_at": datetime.now(timezone.utc).isoformat(),
            "judge": "Claude (Phase 2 spot-check, blind pass)",
            "total": len(out_recs),
            "correct": sum(1 for r in out_recs if r["verdict_at_v2"]=="correct"),
            "defensible": sum(1 for r in out_recs if r["verdict_at_v2"]=="defensible"),
            "wrong": sum(1 for r in out_recs if r["verdict_at_v2"]=="wrong"),
            "duplicate": sum(1 for r in out_recs if r["verdict_at_v2"]=="duplicate"),
            "strict_precision": round(sum(1 for r in out_recs if r["verdict_at_v2"]=="correct") / len(out_recs), 4),
            "defensible_included_precision": round(sum(1 for r in out_recs if r["verdict_at_v2"] in ("correct","defensible")) / len(out_recs), 4),
            "failure_families": dict(Counter(r["failure_family"] for r in out_recs if r["failure_family"]).most_common()),
        },
    }
    out["construction"]["phase"] = "Phase 2 spot-check (eval set v2)"
    out["construction"]["verdict_methodology"] = "Blind judge pass by Claude against locked spec §4 taxonomy and §6 Stage 0 rules. Each record judged on (a) extracted_category vs spec definition, (b) Stage 0 reject patterns from §6/§7 (D1 OOC, D2 NPC-voice, D3 micro-motion, D4 recap-state), (c) condition-recovery polysemy vs overnight-rest, (d) within-turn over-emission patterns."

    with open("compression_cadence_handsample_v2.json", "w") as f:
        json.dump(out, f, indent=2)
    print(f"Wrote compression_cadence_handsample_v2.json")
    print(f"Strict precision: {out['v2_summary']['strict_precision']:.1%}")
    print(f"Defensible-included: {out['v2_summary']['defensible_included_precision']:.1%}")
    print(f"Wrong: {out['v2_summary']['wrong']}, Duplicates: {out['v2_summary']['duplicate']}")

if __name__ == "__main__":
    main()
