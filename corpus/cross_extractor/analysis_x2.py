"""
analysis_x2.py — X2: Compression → next-scene-opening classification.

Question: When Matt compresses with scope=scene_exit, what kind of context
opens the next scene?

Scope: 126 episodes (TM × CC intersection).
Focal records: CC with extracted_compression_scope=scene_exit.
Classification: inferred from the first qualifying event in the stream
after the CC trigger turn.

Opening types:
  quest_offer          — LR direction=offered within 30 turns
  reward_delivery      — LR direction=delivered within 30 turns
  combat_initiation    — EC record within 30 turns
  time_anchor_set      — TM cumulative_anchor within 30 turns
  travel_montage       — TM travel_duration within 30 turns
  in_scene_compression — TM in_scene_compression within 30 turns
  quiet_extended_scene — no classifiable event within 30 turns

TM scene_transition within ≤10 turns is a boundary co-occurrence marker
(CC + TM together = same boundary); it is skipped and the scan continues.
TM_UNKNOWN (category=None) is not classifiable; skipped.
"""

import csv
import os
import random
import sys
from collections import defaultdict
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import x_utils

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

FORWARD_WINDOW = 30
BOUNDARY_WINDOW = 10
SPOT_CHECK_N = 10
SPOT_CHECK_SEED = 42

# Opening type priority labels
OPENING_TYPES = [
    "quest_offer",
    "reward_delivery",
    "combat_initiation",
    "time_anchor_set",
    "travel_montage",
    "in_scene_compression",
    "quiet_extended_scene",
]

# CC categories in display order
CC_CATS = [
    "OVERNIGHT_REST",
    "TEMPORAL_MONTAGE",
    "LOCATION_DEPARTURE",
    "NPC_DEPARTURE",
    "INVESTIGATIVE_CLOSURE",
    "SCENE_CUT",
    "STALE_HOLD_CANDIDATE",
]


def classify_next_event(
    trigger_turn: int,
    events: list[dict],
) -> tuple[str, int | None, str | None]:
    """
    Scan events strictly after trigger_turn, return
    (opening_type, event_turn, event_desc).

    Skip rules:
      - TM scene_transition with turn <= trigger_turn + BOUNDARY_WINDOW → skip
        (boundary co-occurrence)
      - TM with category=None (TM_UNKNOWN) → skip always

    First qualifying event within FORWARD_WINDOW turns classifies the opening.
    If none: quiet_extended_scene.
    """
    candidates = [
        ev for ev in events
        if ev["turn_number"] > trigger_turn
        and ev["turn_number"] <= trigger_turn + FORWARD_WINDOW
    ]
    # Sort by (turn_number, source) so EC/LR/CC events sort before TM at same turn
    # (ensures a same-turn EC doesn't get shadowed by TM boundary)
    candidates.sort(key=lambda e: (e["turn_number"], e["source"]))

    for ev in candidates:
        src = ev["source"]
        cat = ev.get("category")
        turn = ev["turn_number"]

        # Skip TM boundary co-occurrence
        if src == "TM" and cat == "scene_transition":
            if turn <= trigger_turn + BOUNDARY_WINDOW:
                continue  # skip boundary marker
            else:
                # scene_transition beyond 10t = new scene boundary, not classifiable
                continue

        # Skip TM_UNKNOWN
        if src == "TM" and cat is None:
            continue

        # Classify
        if src == "EC":
            return "combat_initiation", turn, f"EC/{cat}"
        if src == "LR":
            direction = ev.get("payload", {}).get("direction", "")
            if direction == "offered":
                return "quest_offer", turn, f"LR/{cat}"
            elif direction == "delivered":
                return "reward_delivery", turn, f"LR/{cat}"
        if src == "TM":
            if cat == "cumulative_anchor":
                return "time_anchor_set", turn, "TM/cumulative_anchor"
            if cat == "travel_duration":
                return "travel_montage", turn, "TM/travel_duration"
            if cat == "in_scene_compression":
                return "in_scene_compression", turn, "TM/in_scene_compression"
        # CC events after the trigger (same episode, different turn) — not a classifier
        # for "next-scene-opening", skip
        if src == "CC":
            continue

    return "quiet_extended_scene", None, None


def run():
    scope_eps = x_utils.get_pair_intersection("TM", "CC")
    print(f"X2 scope: {len(scope_eps)} episodes (TM × CC intersection)")

    # Load streams for all scope episodes (keyed by episode)
    streams: dict[str, dict] = {}
    for ep in scope_eps:
        streams[ep] = x_utils.load_episode_stream(ep)

    # Find CC scene_exit records
    all_records = x_utils.load_unified_records(
        sources_filter=["CC"],
        episodes_filter=scope_eps,
    )
    scene_exit_records = [
        r for r in all_records
        if r["payload"].get("extracted_compression_scope") == "scene_exit"
    ]
    print(f"CC scene_exit records in scope: {len(scene_exit_records)}")

    # Classify each scene_exit record
    classified = []
    for r in scene_exit_records:
        ep = r["episode_combined"]
        trigger_turn = r["turn_number"]
        cc_cat = r["category"]
        events = streams[ep]["events"]

        opening_type, event_turn, event_desc = classify_next_event(
            trigger_turn, events
        )

        # Check for boundary co-occurrence (TM scene_transition within BOUNDARY_WINDOW)
        has_boundary_cooccur = any(
            ev["source"] == "TM"
            and ev.get("category") == "scene_transition"
            and ev["turn_number"] > trigger_turn
            and ev["turn_number"] <= trigger_turn + BOUNDARY_WINDOW
            for ev in events
        )

        classified.append({
            "episode": ep,
            "trigger_turn": trigger_turn,
            "cc_category": cc_cat,
            "opening_type": opening_type,
            "first_event_turn": event_turn,
            "first_event_desc": event_desc,
            "has_boundary_cooccur": has_boundary_cooccur,
        })

    # --- Aggregate: per-opening-type frequency ---
    opening_counts: dict[str, int] = defaultdict(int)
    for rec in classified:
        opening_counts[rec["opening_type"]] += 1
    total = len(classified)

    print("\nOpening-type frequency:")
    for ot in OPENING_TYPES:
        n = opening_counts[ot]
        print(f"  {ot:<28} {n:3d}  ({100*n/total:.1f}%)")

    # --- CC category × opening type cross-tab ---
    cc_x_opening: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    cc_cat_totals: dict[str, int] = defaultdict(int)
    for rec in classified:
        cc_x_opening[rec["cc_category"]][rec["opening_type"]] += 1
        cc_cat_totals[rec["cc_category"]] += 1
    print("\nCC category × opening type cross-tab:")
    present_cc_cats = [c for c in CC_CATS if c in cc_cat_totals]
    for cc_cat in present_cc_cats:
        top = sorted(cc_x_opening[cc_cat].items(), key=lambda x: -x[1])[:3]
        top_str = "  ".join(f"{k}:{v}" for k, v in top)
        print(f"  {cc_cat:<28} total={cc_cat_totals[cc_cat]:3d}  top: {top_str}")

    # Boundary co-occurrence rate
    n_boundary = sum(1 for r in classified if r["has_boundary_cooccur"])
    print(f"\nBoundary co-occurrence (TM scene_transition within {BOUNDARY_WINDOW}t): "
          f"{n_boundary}/{total} ({100*n_boundary/total:.1f}%)")

    # --- Spot-check ---
    print(f"\n--- Spot-check: {SPOT_CHECK_N} records (seed={SPOT_CHECK_SEED}) ---")
    random.seed(SPOT_CHECK_SEED)
    sample = random.sample(classified, min(SPOT_CHECK_N, len(classified)))
    spot_lines = []
    all_verified = True
    for rec in sample:
        stream = streams[rec["episode"]]
        # Verify CC scene_exit exists in stream at trigger_turn
        cc_in_stream = any(
            ev["source"] == "CC"
            and ev["turn_number"] == rec["trigger_turn"]
            and ev["payload"].get("extracted_compression_scope") == "scene_exit"
            for ev in stream["events"]
        )
        # Verify first event (if not quiet) exists in stream
        if rec["first_event_turn"] is not None:
            fe_src = rec["first_event_desc"].split("/")[0]
            next_in_stream = any(
                ev["source"] == fe_src
                and ev["turn_number"] == rec["first_event_turn"]
                for ev in stream["events"]
            )
        else:
            next_in_stream = True  # quiet = no event, vacuously verified
        verified = cc_in_stream and next_in_stream
        if not verified:
            all_verified = False
        line = (f"ep={rec['episode']} t={rec['trigger_turn']} "
                f"cc_cat={rec['cc_category']} "
                f"opening={rec['opening_type']} "
                f"first_event={rec['first_event_desc']} "
                f"stream_verified={verified}")
        print(f"  {line}")
        spot_lines.append(line)

    # --- CSV ---
    csv_path = os.path.join(RESULTS_DIR, "x2_scene_openings.csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "episode", "trigger_turn", "cc_category", "opening_type",
            "first_event_turn", "first_event_desc", "has_boundary_cooccur",
        ])
        writer.writeheader()
        for rec in classified:
            writer.writerow(rec)
    print(f"\nCSV written: {csv_path}")

    # --- Markdown ---
    md_path = os.path.join(RESULTS_DIR, "x2_scene_openings.md")
    with open(md_path, "w") as f:
        f.write("# X2: Compression → Next-Scene-Opening Classification\n\n")
        f.write("**Question:** When Matt compresses with scope=scene_exit, what kind "
                "of context opens the next scene?\n\n")
        f.write(f"**Scope:** {len(scope_eps)} episodes (TM × CC intersection), "
                f"{total} CC scene_exit records\n\n")
        f.write(f"**Date:** {date.today()}\n\n")
        f.write("---\n\n")

        f.write("## Key Findings\n\n")
        top3 = sorted(opening_counts.items(), key=lambda x: -x[1])[:3]
        for ot, n in top3:
            f.write(f"- {ot}: **{n}/{total}** ({100*n/total:.1f}%)\n")
        f.write(f"- Boundary co-occurrence (TM scene_transition within {BOUNDARY_WINDOW}t): "
                f"{n_boundary}/{total} ({100*n_boundary/total:.1f}%)\n\n")
        f.write("**Limitation:** Cross-extractor signal cannot observe player turns "
                "or NPC dialogue directly. Opening shape is inferred from which "
                "extractor fires first after CC. `quiet_extended_scene` includes "
                "scenes where Matt sets context without any extractor firing.\n\n")
        f.write("---\n\n")

        f.write("## Per-Opening-Type Frequency\n\n")
        f.write("| Opening Type | Count | % |\n|--------------|-------|---|\n")
        for ot in OPENING_TYPES:
            n = opening_counts[ot]
            f.write(f"| {ot} | {n} | {100*n/total:.1f}% |\n")
        f.write(f"| **Total** | **{total}** | |\n")
        f.write("\n---\n\n")

        f.write("## CC Category × Opening Type Cross-Tab\n\n")
        # Header
        header = "| CC Category | Total |" + "".join(f" {ot} |" for ot in OPENING_TYPES)
        sep = "|-------------|-------|" + "------|" * len(OPENING_TYPES)
        f.write(header + "\n" + sep + "\n")
        for cc_cat in present_cc_cats:
            row = f"| {cc_cat} | {cc_cat_totals[cc_cat]} |"
            for ot in OPENING_TYPES:
                n = cc_x_opening[cc_cat].get(ot, 0)
                pct = 100 * n / cc_cat_totals[cc_cat]
                row += f" {n} ({pct:.0f}%) |"
            f.write(row + "\n")
        f.write("\n---\n\n")

        f.write("## Spot-Check Results\n\n")
        f.write(f"{SPOT_CHECK_N} randomly sampled records (seed={SPOT_CHECK_SEED}), "
                "verified against stream files.\n\n")
        for line in spot_lines:
            f.write(f"    {line}\n")
        f.write(f"\n{'All' if all_verified else 'NOT all'} spot-checked records "
                "verified in stream.\n\n")
        f.write("---\n\n")

        f.write("## Corpus-Level Summary\n\n")
        f.write(f"| Metric | Value |\n|--------|-------|\n")
        f.write(f"| Episodes in scope | {len(scope_eps)} |\n")
        f.write(f"| CC scene_exit records | {total} |\n")
        for ot in OPENING_TYPES:
            n = opening_counts[ot]
            f.write(f"| {ot} | {n} ({100*n/total:.1f}%) |\n")
        f.write(f"| Boundary co-occurrence | {n_boundary} ({100*n_boundary/total:.1f}%) |\n")
    print(f"Markdown written: {md_path}")

    return {
        "scope_eps": len(scope_eps),
        "total_scene_exit": total,
        "opening_counts": dict(opening_counts),
        "n_boundary_cooccur": n_boundary,
    }


if __name__ == "__main__":
    run()
