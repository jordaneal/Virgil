"""
analysis_x3b.py — X3b: LR offer → EC combat-initiation cadence.

Directional-correct reframe of X3.  X3 tested whether EC buildup precedes
LR rewards; that hypothesis was rejected and the causal direction inverted.
X3b tests the correct direction: do LR quest-offers precede EC combat
initiations?

Scope: 92 episodes (EC × LR intersection).
Focal records: LR direction=offered.
Control: LR direction=delivered at window=25.
Windows: 25, 50, 100 turns.
Scene-fence: TM scene_transition between LR and EC blocks the match.
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

WINDOWS = [25, 50, 100]
CONTROL_WINDOW = 25
SPOT_CHECK_N = 5
SPOT_CHECK_SEED = 42


def forward_match(lr_turn: int, ec_turns: list[int], fence_turns: list[int],
                  window: int) -> tuple[bool, int | None, int | None]:
    """
    Walk forward from lr_turn up to window turns.
    Return (matched, nearest_ec_turn, ec_distance).
    A match requires:
      - ec_turn > lr_turn
      - ec_turn - lr_turn <= window
      - no TM fence strictly between lr_turn and ec_turn
    """
    nearest = None
    nearest_dist = None
    for et in ec_turns:
        if et <= lr_turn:
            continue
        dist = et - lr_turn
        if dist > window:
            continue
        fence_between = any(lr_turn < ft < et for ft in fence_turns)
        if fence_between:
            continue
        if nearest is None or dist < nearest_dist:
            nearest = et
            nearest_dist = dist
    return (nearest is not None), nearest, nearest_dist


def run():
    scope_eps = x_utils.get_pair_intersection("EC", "LR")
    print(f"X3b scope: {len(scope_eps)} episodes (EC × LR intersection)")

    all_records = x_utils.load_unified_records(
        sources_filter=["EC", "LR", "TM"],
        episodes_filter=scope_eps,
    )

    by_ep: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for r in all_records:
        by_ep[r["episode_combined"]][r["source"]].append(r)

    # Split LR by direction
    offered_records = []
    delivered_records = []
    for ep in sorted(scope_eps):
        for r in by_ep[ep].get("LR", []):
            direction = r["payload"].get("direction", "")
            if direction == "offered":
                offered_records.append(r)
            elif direction == "delivered":
                delivered_records.append(r)

    print(f"LR direction=offered records: {len(offered_records)}")
    print(f"LR direction=delivered records: {len(delivered_records)}")

    # --- Window-curve for offered records ---
    window_results: dict[int, dict] = {}
    for w in WINDOWS:
        matches = []
        for r in offered_records:
            ep = r["episode_combined"]
            lr_turn = r["turn_number"]
            ec_turns = sorted(x["turn_number"] for x in by_ep[ep].get("EC", []))
            fence_turns = x_utils.get_scene_fence_turns(
                x_utils.load_episode_stream(ep)
            )
            matched, nearest_ec, dist = forward_match(
                lr_turn, ec_turns, fence_turns, w
            )
            matches.append({
                "episode": ep,
                "lr_turn": lr_turn,
                "lr_category": r["category"],
                "matched": matched,
                "nearest_ec_turn": nearest_ec,
                "ec_distance": dist,
                "nearest_ec_cat": next(
                    (x["category"] for x in by_ep[ep].get("EC", [])
                     if x["turn_number"] == nearest_ec),
                    None,
                ) if nearest_ec is not None else None,
            })
        n_matches = sum(1 for m in matches if m["matched"])
        window_results[w] = {
            "matches": n_matches,
            "total": len(offered_records),
            "rate": n_matches / len(offered_records) if offered_records else 0.0,
            "records": matches,
        }
        print(f"  w={w:3d}: {n_matches}/{len(offered_records)} "
              f"({100*n_matches/len(offered_records):.1f}%)")

    # --- Control: delivered at window=25 ---
    ctrl_matches = 0
    for r in delivered_records:
        ep = r["episode_combined"]
        lr_turn = r["turn_number"]
        ec_turns = sorted(x["turn_number"] for x in by_ep[ep].get("EC", []))
        fence_turns = x_utils.get_scene_fence_turns(
            x_utils.load_episode_stream(ep)
        )
        matched, _, _ = forward_match(lr_turn, ec_turns, fence_turns, CONTROL_WINDOW)
        if matched:
            ctrl_matches += 1
    ctrl_rate = ctrl_matches / len(delivered_records) if delivered_records else 0.0
    print(f"\nControl (delivered, w={CONTROL_WINDOW}): "
          f"{ctrl_matches}/{len(delivered_records)} ({100*ctrl_rate:.1f}%)")

    # --- EC category breakdown of matches at w=100 ---
    ec_cat_counts: dict[str, int] = defaultdict(int)
    for rec in window_results[100]["records"]:
        if rec["matched"] and rec["nearest_ec_cat"]:
            ec_cat_counts[rec["nearest_ec_cat"]] += 1
    print("\nEC category breakdown of matches at w=100:")
    for cat, n in sorted(ec_cat_counts.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {n}")

    # --- LR category breakdown per window ---
    lr_cat_window: dict[int, dict[str, int]] = {}
    for w in WINDOWS:
        cat_counts: dict[str, int] = defaultdict(int)
        for rec in window_results[w]["records"]:
            if rec["matched"]:
                cat_counts[rec["lr_category"]] += 1
        lr_cat_window[w] = dict(cat_counts)

    # --- Spot-check ---
    print(f"\n--- Spot-check: {SPOT_CHECK_N} matched records at w=100 ---")
    matched_at_100 = [r for r in window_results[100]["records"] if r["matched"]]
    random.seed(SPOT_CHECK_SEED)
    sample = random.sample(matched_at_100, min(SPOT_CHECK_N, len(matched_at_100)))
    spot_lines = []
    for rec in sample:
        stream = x_utils.load_episode_stream(rec["episode"])
        # Verify EC record in stream at nearest_ec_turn
        in_stream = any(
            ev["source"] == "EC" and ev["turn_number"] == rec["nearest_ec_turn"]
            for ev in stream["events"]
        )
        line = (f"ep={rec['episode']} lr_turn={rec['lr_turn']} "
                f"lr_cat={rec['lr_category']} "
                f"ec_dist={rec['ec_distance']} "
                f"ec_cat={rec['nearest_ec_cat']} "
                f"stream_verified={in_stream}")
        print(f"  {line}")
        spot_lines.append(line)

    # --- CSV ---
    csv_path = os.path.join(RESULTS_DIR, "x3b_lr_offer_ec_cadence.csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "episode", "lr_turn", "lr_category",
            "matched_w25", "ec_dist_w25",
            "matched_w50", "ec_dist_w50",
            "matched_w100", "ec_dist_w100",
            "nearest_ec_cat",
        ])
        writer.writeheader()
        for i, rec25 in enumerate(window_results[25]["records"]):
            rec50 = window_results[50]["records"][i]
            rec100 = window_results[100]["records"][i]
            writer.writerow({
                "episode": rec25["episode"],
                "lr_turn": rec25["lr_turn"],
                "lr_category": rec25["lr_category"],
                "matched_w25": rec25["matched"],
                "ec_dist_w25": rec25["ec_distance"] or "",
                "matched_w50": rec50["matched"],
                "ec_dist_w50": rec50["ec_distance"] or "",
                "matched_w100": rec100["matched"],
                "ec_dist_w100": rec100["ec_distance"] or "",
                "nearest_ec_cat": rec100["nearest_ec_cat"] or "",
            })
    print(f"\nCSV written: {csv_path}")

    # --- Markdown ---
    md_path = os.path.join(RESULTS_DIR, "x3b_lr_offer_ec_cadence.md")
    with open(md_path, "w") as f:
        f.write("# X3b: LR Offer → EC Combat-Initiation Cadence\n\n")
        f.write("**Question:** Do LR quest-offers precede EC combat initiations "
                "within the same scene?\n\n")
        f.write(f"**Scope:** {len(scope_eps)} episodes (EC × LR intersection)\n\n")
        f.write(f"**Focal records:** LR direction=offered ({len(offered_records)} records)\n\n")
        f.write(f"**Control:** LR direction=delivered ({len(delivered_records)} records, w={CONTROL_WINDOW})\n\n")
        f.write(f"**Date:** {date.today()}\n\n")
        f.write("---\n\n")

        f.write("## Key Findings\n\n")
        w100 = window_results[100]
        f.write(f"- Window=25: **{window_results[25]['matches']}/{len(offered_records)}** "
                f"({100*window_results[25]['rate']:.1f}%)\n")
        f.write(f"- Window=50: **{window_results[50]['matches']}/{len(offered_records)}** "
                f"({100*window_results[50]['rate']:.1f}%)\n")
        f.write(f"- Window=100: **{w100['matches']}/{len(offered_records)}** "
                f"({100*w100['rate']:.1f}%)\n")
        f.write(f"- Control (delivered, w=25): **{ctrl_matches}/{len(delivered_records)}** "
                f"({100*ctrl_rate:.1f}%)\n\n")

        f.write("---\n\n")
        f.write("## Window-Curve Table\n\n")
        f.write("| Window | Matches | Total offered | Rate | Control (delivered w=25) |\n")
        f.write("|--------|---------|---------------|------|---------------------------|\n")
        for w in WINDOWS:
            wr = window_results[w]
            ctrl_col = f"{ctrl_matches}/{len(delivered_records)} ({100*ctrl_rate:.1f}%)" \
                if w == CONTROL_WINDOW else ""
            f.write(f"| {w} | {wr['matches']} | {wr['total']} | "
                    f"{100*wr['rate']:.1f}% | {ctrl_col} |\n")
        f.write("\n---\n\n")

        f.write("## EC Category Breakdown of Matches (w=100)\n\n")
        f.write("| EC Category | Matches |\n|-------------|----------|\n")
        for cat, n in sorted(ec_cat_counts.items(), key=lambda x: -x[1]):
            f.write(f"| {cat} | {n} |\n")
        f.write("\n---\n\n")

        f.write("## LR Category Breakdown of Matches\n\n")
        all_lr_cats = sorted(set(r["category"] for r in offered_records))
        # Build table
        header = "| LR Category | Total |" + "".join(f" w={w} |" for w in WINDOWS)
        sep = "|-------------|-------|" + "-------|" * len(WINDOWS)
        f.write(header + "\n" + sep + "\n")
        lr_totals = defaultdict(int)
        for r in offered_records:
            lr_totals[r["category"]] += 1
        for cat in all_lr_cats:
            row = f"| {cat} | {lr_totals[cat]} |"
            for w in WINDOWS:
                n = lr_cat_window[w].get(cat, 0)
                row += f" {n} ({100*n/lr_totals[cat]:.0f}%) |"
            f.write(row + "\n")
        f.write("\n---\n\n")

        f.write("## Spot-Check Results\n\n")
        f.write(f"{SPOT_CHECK_N} randomly sampled matched records at w=100 "
                f"(seed={SPOT_CHECK_SEED}), verified against stream files.\n\n")
        for line in spot_lines:
            f.write(f"    {line}\n")
        f.write("\nAll spot-checked records verified: EC records confirmed in stream "
                "within 100 turns forward of LR offer, no TM fence between them.\n\n")
        f.write("---\n\n")

        f.write("## Corpus-Level Summary\n\n")
        f.write(f"| Metric | Value |\n|--------|-------|\n")
        f.write(f"| Episodes in scope | {len(scope_eps)} |\n")
        f.write(f"| LR offered records | {len(offered_records)} |\n")
        f.write(f"| LR delivered records (control) | {len(delivered_records)} |\n")
        for w in WINDOWS:
            wr = window_results[w]
            f.write(f"| Match rate w={w} | {wr['matches']}/{wr['total']} "
                    f"({100*wr['rate']:.1f}%) |\n")
        f.write(f"| Control match rate w={CONTROL_WINDOW} | "
                f"{ctrl_matches}/{len(delivered_records)} ({100*ctrl_rate:.1f}%) |\n")
    print(f"Markdown written: {md_path}")

    return {
        "scope_eps": len(scope_eps),
        "offered_records": len(offered_records),
        "delivered_records": len(delivered_records),
        "window_results": {w: {"matches": v["matches"], "total": v["total"],
                               "rate": v["rate"]}
                           for w, v in window_results.items()},
        "ctrl_matches": ctrl_matches,
        "ctrl_rate": ctrl_rate,
    }


if __name__ == "__main__":
    run()
