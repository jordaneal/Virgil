"""
analysis_x4.py — X4: Negative-signal rate.
Scope: 140 episodes (all streams).
"""

import csv
import os
import sys
from collections import defaultdict
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import x_utils

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

# R1 categories (climactic-hold-combat): EC with these cats trigger R1
R1_EC_CATS = {"interruption", "npc_turns_hostile"}
# Combat-dense override EC categories
COMBAT_DENSE_CATS = {"wave_or_phase_shift", "environmental_materialization"}

# Known anchor episodes for sanity check
R1_EXPECTED = {"C1E114", "C1E040", "C1E076"}
R2_EXPECTED = {"C1E108"}
COMBAT_DENSE_EXPECTED = {"C2E015", "C2E010", "C1E033", "C2E034", "C1E006"}
LOW_ACTIVITY_EXPECTED = {"C1E003", "C1E073", "C1E046", "C1E085", "C2E040"}


def _get_all_stream_episodes() -> list[str]:
    streams_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "streams")
    return [fn.replace(".json", "") for fn in os.listdir(streams_dir) if fn.endswith(".json")]


def compute_r3_count(
    ep: str,
    ec_records_ep: list[dict],
    lr_turns_ep: list[int],
    fence_turns: list[int],
    window: int = 25,
) -> int:
    """
    Per-episode count of EC records that have NO LR record within 'window' turns
    ahead in the same scene (TM fence applied).
    Returns count of EC records WITHOUT a qualifying LR ahead.
    """
    count_no_payoff = 0
    for ec_rec in ec_records_ep:
        et = ec_rec["turn_number"]
        found = False
        for lt in lr_turns_ep:
            if lt > et and (lt - et) <= window:
                # Check no fence strictly between ec and lr
                fence_between = any(et < ft < lt for ft in fence_turns)
                if not fence_between:
                    found = True
                    break
        if not found:
            count_no_payoff += 1
    return count_no_payoff


def run():
    all_eps = sorted(_get_all_stream_episodes())
    print(f"X4 scope: {len(all_eps)} episodes (all streams)")

    # Load all records
    all_records = x_utils.load_unified_records()

    # Group by episode
    by_ep: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for r in all_records:
        ep = r["episode_combined"]
        src = r["source"]
        by_ep[ep][src].append(r)

    # 1. Compute 25th percentile of total_records from stream files
    stream_totals = {}
    for ep in all_eps:
        stream = x_utils.load_episode_stream(ep)
        stream_totals[ep] = stream["total_records"]

    totals_sorted = sorted(stream_totals.values())
    p25_idx = int(len(totals_sorted) * 0.25)
    p25_threshold = totals_sorted[p25_idx]
    print(f"25th percentile of total_records: {p25_threshold}")

    # 2. Statistical side: compute corpus-wide mean and std for per-source counts
    source_counts = {src: [] for src in ["EC", "TM", "LR", "CC"]}
    late_fracs = []
    for ep in all_eps:
        stream = x_utils.load_episode_stream(ep)
        for src in source_counts:
            n = len(by_ep[ep].get(src, []))
            source_counts[src].append(n)
        late_fracs.append(x_utils.episode_late_fraction(stream, threshold=0.75))

    def mean_std(vals):
        n = len(vals)
        m = sum(vals) / n
        var = sum((v - m) ** 2 for v in vals) / n
        std = var ** 0.5
        return m, std

    stat_params = {}
    for src in ["EC", "TM", "LR", "CC"]:
        m, s = mean_std(source_counts[src])
        stat_params[src] = (m, s)
    late_mean, late_std = mean_std(late_fracs)
    print(f"Stat params: EC=({stat_params['EC'][0]:.2f}, {stat_params['EC'][1]:.2f}), "
          f"TM=({stat_params['TM'][0]:.2f}, {stat_params['TM'][1]:.2f}), "
          f"LR=({stat_params['LR'][0]:.2f}, {stat_params['LR'][1]:.2f}), "
          f"CC=({stat_params['CC'][0]:.2f}, {stat_params['CC'][1]:.2f}), "
          f"late_frac=({late_mean:.3f}, {late_std:.3f})")

    # 3. Per-episode classification
    ep_results = {}
    sanity_results = {}

    for ep_idx, ep in enumerate(all_eps):
        stream = x_utils.load_episode_stream(ep)
        ec_recs = by_ep[ep].get("EC", [])
        lr_recs = by_ep[ep].get("LR", [])
        tm_recs = by_ep[ep].get("TM", [])
        cc_recs = by_ep[ep].get("CC", [])

        ec_count = len(ec_recs)
        lr_count = len(lr_recs)
        tm_count = len(tm_recs)
        cc_count = len(cc_recs)
        total_records = stream_totals[ep]

        # late_frac = fraction of events in the last 25% of episode (position >= 0.75).
        # R1 threshold: late_frac >= 0.4 (40% of events in last quarter).
        # R2 threshold: late_frac >= 0.3 (30% of events in last quarter).
        # Both use the same 0.75 position cutoff; only the fraction bar differs.
        late_frac = x_utils.episode_late_fraction(stream, threshold=0.75)

        # Fence turns
        fence_turns = x_utils.get_scene_fence_turns(stream)
        lr_turns = sorted(r["turn_number"] for r in lr_recs)

        # R1: EC >= 1 with category in R1_EC_CATS AND late_frac >= 0.4 AND cc_count == 0
        r1_ec_qualifying = [r for r in ec_recs if r["category"] in R1_EC_CATS]
        r1 = (len(r1_ec_qualifying) >= 1 and late_frac >= 0.4 and cc_count == 0)

        # R2: LR count >= 5 AND late_frac >= 0.3 AND cc_count == 0
        r2 = (lr_count >= 5 and late_frac >= 0.3 and cc_count == 0)

        # R3: count of EC records without LR ahead within 25 turns (same scene)
        r3_count = compute_r3_count(ep, ec_recs, lr_turns, fence_turns, window=25)

        # Negative rules.
        # combat_dense: EC >= 2 with wave_or_phase_shift / environmental_materialization.
        # low_activity: total_records below p25 AND ec_count == 0. The ec_count guard
        # prevents suppressing climactic-hold-combat cases (C1E114, C1E076) whose
        # low total_records stem from CC=0, not from genuine inactivity — if EC fires,
        # the episode has real content that R1/R2 should evaluate.
        combat_dense_ec = [r for r in ec_recs if r["category"] in COMBAT_DENSE_CATS]
        neg_combat_dense = len(combat_dense_ec) >= 2
        neg_low_activity = total_records < p25_threshold and ec_count == 0
        negative_rule_fired = (r1 or r2) and (neg_combat_dense or neg_low_activity)

        # Statistical flags
        stat_flag_ec = ec_count > stat_params["EC"][0] + 2 * stat_params["EC"][1]
        stat_flag_tm = tm_count > stat_params["TM"][0] + 2 * stat_params["TM"][1]
        stat_flag_lr = lr_count > stat_params["LR"][0] + 2 * stat_params["LR"][1]
        stat_flag_late = late_frac > late_mean + 2 * late_std
        stat_flag = stat_flag_ec or stat_flag_tm or stat_flag_lr or stat_flag_late

        # Final classification
        r1_effective = r1 and not (neg_combat_dense or neg_low_activity)
        r2_effective = r2 and not (neg_combat_dense or neg_low_activity)

        if r1_effective:
            classification = "climactic_hold_combat"
        elif r2_effective:
            classification = "climactic_hold_reward"
        elif not r1 and not r2 and r3_count >= 3:
            classification = "lr_x2_absence"
        elif not r1 and not r2 and not stat_flag:
            classification = "no_flag"
        elif negative_rule_fired:
            classification = "dropped_negative_rule"
        elif not r1 and not r2 and stat_flag:
            classification = "stat_outlier_only"
        else:
            classification = "no_flag"

        ep_results[ep] = {
            "episode": ep,
            "ec_count": ec_count,
            "tm_count": tm_count,
            "lr_count": lr_count,
            "cc_count": cc_count,
            "late_frac": round(late_frac, 4),
            "rule_R1": r1,
            "rule_R2": r2,
            "rule_R3_count": r3_count,
            "stat_flag": stat_flag,
            "negative_rule_dropped": negative_rule_fired,
            "final_classification": classification,
            # Internal helpers for sanity check
            "_late_frac_r1": round(late_frac, 4),
            "_late_frac_r2": round(late_frac, 4),
            "_r1_ec_qualifying": len(r1_ec_qualifying),
            "_neg_combat_dense": neg_combat_dense,
            "_neg_low_activity": neg_low_activity,
        }

    # 4. Sanity check before corpus-wide reporting
    print("\n=== SANITY CHECK: Known zero-CC anchor episodes ===")
    sanity_ok = True

    # Expected R1 anchors
    for ep in sorted(R1_EXPECTED):
        res = ep_results.get(ep)
        if res is None:
            print(f"  MISSING: {ep}")
            sanity_ok = False
            continue
        r1 = res["rule_R1"]
        status = "OK" if r1 else "FAIL"
        print(f"  R1 {ep}: r1={r1} (ec_qualifying={res['_r1_ec_qualifying']}, "
              f"late_r1={res['_late_frac_r1']}, cc={res['cc_count']}) [{status}]")
        if not r1:
            sanity_ok = False

    # Expected R2 anchor
    for ep in sorted(R2_EXPECTED):
        res = ep_results.get(ep)
        if res is None:
            print(f"  MISSING: {ep}")
            sanity_ok = False
            continue
        r2 = res["rule_R2"]
        status = "OK" if r2 else "FAIL"
        print(f"  R2 {ep}: r2={r2} (lr={res['lr_count']}, "
              f"late_r2={res['_late_frac_r2']}, cc={res['cc_count']}) [{status}]")
        if not r2:
            sanity_ok = False

    # Expected combat-dense overrides
    print("\n  Expected combat-dense negative-rule drops:")
    for ep in sorted(COMBAT_DENSE_EXPECTED):
        res = ep_results.get(ep)
        if res is None:
            print(f"  MISSING: {ep}")
            continue
        print(f"    {ep}: neg_combat_dense={res['_neg_combat_dense']} "
              f"classification={res['final_classification']}")

    # Expected low-activity overrides
    print("\n  Expected low-activity negative-rule drops:")
    for ep in sorted(LOW_ACTIVITY_EXPECTED):
        res = ep_results.get(ep)
        if res is None:
            print(f"  MISSING: {ep}")
            continue
        total = stream_totals.get(ep, 0)
        print(f"    {ep}: total_records={total} (threshold={p25_threshold}) "
              f"neg_low={res['_neg_low_activity']} classification={res['final_classification']}")

    # STOP condition
    r1_c1e114 = ep_results.get("C1E114", {}).get("rule_R1", False)
    r2_c1e108 = ep_results.get("C1E108", {}).get("rule_R2", False)

    if not r1_c1e114 or not r2_c1e108:
        print("\n!!! STOP: R1 anchor (C1E114) or R2 anchor (C1E108) did not fire.")
        print(f"R1 fires on C1E114: {r1_c1e114}")
        print(f"R2 fires on C1E108: {r2_c1e108}")
        print("Threshold mismatch — halting before corpus-wide run.")
        print("Adjustment needed: inspect R1/R2 conditions.")
        # Report what would need to change and exit
        res114 = ep_results.get("C1E114", {})
        res108 = ep_results.get("C1E108", {})
        print(f"\nC1E114 diagnostic: {res114}")
        print(f"\nC1E108 diagnostic: {res108}")
        return None

    print(f"\nSanity check: R1 fires on C1E114: {r1_c1e114}")
    print(f"Sanity check: R2 fires on C1E108: {r2_c1e108}")

    # Check C1E040 separately (player_action_escalation not in R1_EC_CATS)
    r1_c1e040 = ep_results.get("C1E040", {}).get("rule_R1", False)
    print(f"\nNote: R1 fires on C1E040: {r1_c1e040}")
    ec_cats_040 = [r["category"] for r in by_ep.get("C1E040", {}).get("EC", [])]
    print(f"  C1E040 EC categories: {ec_cats_040}")
    print(f"  C1E040 EC cat 'player_action_escalation' NOT in R1_EC_CATS {{interruption, npc_turns_hostile}}")
    print(f"  Spec expected R1 for C1E040 but R1 cannot fire with current EC categories.")
    print(f"  STOP condition only requires C1E114 (fires: {r1_c1e114}) — no threshold adjustment needed.")
    print(f"  This discrepancy is documented as a data finding.")

    # 5. Corpus-wide classification counts
    classifications = defaultdict(int)
    for res in ep_results.values():
        classifications[res["final_classification"]] += 1

    print("\n=== X4 Classification Counts ===")
    for cls in [
        "climactic_hold_combat", "climactic_hold_reward", "lr_x2_absence",
        "stat_outlier_only", "dropped_negative_rule", "no_flag"
    ]:
        print(f"  {cls}: {classifications[cls]}")

    # Rule-vs-stat agreement
    rule_only = sum(1 for r in ep_results.values()
                    if (r["rule_R1"] or r["rule_R2"] or r["rule_R3_count"] >= 3)
                    and not r["stat_flag"])
    stat_only = sum(1 for r in ep_results.values()
                    if not (r["rule_R1"] or r["rule_R2"] or r["rule_R3_count"] >= 3)
                    and r["stat_flag"])
    both_rule_stat = sum(1 for r in ep_results.values()
                         if (r["rule_R1"] or r["rule_R2"] or r["rule_R3_count"] >= 3)
                         and r["stat_flag"])
    neither = sum(1 for r in ep_results.values()
                  if not (r["rule_R1"] or r["rule_R2"] or r["rule_R3_count"] >= 3)
                  and not r["stat_flag"])
    disagreement = rule_only + stat_only  # flags only one system catches

    print(f"\nRule-only: {rule_only}  Stat-only: {stat_only}  "
          f"Both: {both_rule_stat}  Neither: {neither}")
    print(f"Rule-vs-stat disagreement count: {disagreement}")

    # 6. Write CSV
    csv_path = os.path.join(RESULTS_DIR, "x4_negative_signals.csv")
    fieldnames = [
        "episode", "ec_count", "tm_count", "lr_count", "cc_count", "late_frac",
        "rule_R1", "rule_R2", "rule_R3_count", "stat_flag",
        "negative_rule_dropped", "final_classification",
    ]
    with open(csv_path, "w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for ep in sorted(ep_results.keys()):
            row = {k: v for k, v in ep_results[ep].items() if not k.startswith("_")}
            writer.writerow(row)
    print(f"\nCSV written: {csv_path}")

    # 7. Write markdown
    md_path = os.path.join(RESULTS_DIR, "x4_negative_signals.md")
    with open(md_path, "w") as f:
        f.write("# X4: Negative-Signal Rate\n\n")
        f.write("**Question:** Which episodes show suppressed climactic signals (negative rules) "
                "or unusual structural patterns?\n\n")
        f.write(f"**Scope:** 140 episodes (all streams)\n\n")
        f.write(f"**Date:** {date.today()}\n\n")
        f.write("---\n\n")
        f.write("## Key Findings\n\n")
        for cls, label in [
            ("climactic_hold_combat", "Climactic hold (combat)"),
            ("climactic_hold_reward", "Climactic hold (reward)"),
            ("lr_x2_absence", "LR-X2 absence (EC without reward payoff)"),
            ("stat_outlier_only", "Statistical outlier only"),
            ("dropped_negative_rule", "Negative-rule dropped"),
            ("no_flag", "No flag"),
        ]:
            f.write(f"- {label}: **{classifications[cls]}** episodes\n")
        f.write(f"- Rule-vs-stat disagreement: {disagreement} episodes "
                f"(rule_only={rule_only}, stat_only={stat_only})\n")
        f.write(f"- 25th percentile threshold: {p25_threshold} total records\n\n")
        f.write("**C1E040 discrepancy note:** The spec lists C1E040 as an expected R1 fire, "
                "but its only EC record has category `player_action_escalation`, which is not in "
                "R1_EC_CATS={interruption, npc_turns_hostile}. R1 does not fire on C1E040 under "
                "the literal spec rule. The mandatory STOP condition (C1E114 and C1E108) passes. "
                "No threshold adjustment made; discrepancy documented here.\n\n")
        f.write("---\n\n")
        f.write("## Classification Counts\n\n")
        f.write("| Classification | Count |\n|----------------|-------|\n")
        for cls in [
            "climactic_hold_combat", "climactic_hold_reward", "lr_x2_absence",
            "stat_outlier_only", "dropped_negative_rule", "no_flag"
        ]:
            f.write(f"| {cls} | {classifications[cls]} |\n")
        f.write("\n---\n\n")
        f.write("## Rule vs Stat Agreement\n\n")
        f.write("| Category | Count |\n|----------|-------|\n")
        f.write(f"| Rule signal only | {rule_only} |\n")
        f.write(f"| Stat signal only | {stat_only} |\n")
        f.write(f"| Both rule and stat | {both_rule_stat} |\n")
        f.write(f"| Neither | {neither} |\n")
        f.write(f"| Total disagreement | {disagreement} |\n")
        f.write("\n---\n\n")
        f.write("## Sanity Check: Known Zero-CC Episodes\n\n")
        f.write(f"Mandatory checks against 14 known zero-CC anchor episodes.\n\n")
        f.write("**STOP condition:** R1 fires on C1E114 and R2 fires on C1E108 — both passed.\n\n")
        f.write("| Episode | Expected | R1 | R2 | EC cats | late_r1 | late_r2 | "
                "CC | Total | neg_combat | neg_low | Classification |\n")
        f.write("|---------|----------|----|----|---------|---------|---------|"
                "----|-------|------------|---------|----------------|\n")
        for ep in sorted(R1_EXPECTED | R2_EXPECTED | COMBAT_DENSE_EXPECTED | LOW_ACTIVITY_EXPECTED):
            res = ep_results.get(ep, {})
            if not res:
                f.write(f"| {ep} | missing | - | - | - | - | - | - | - | - | - | MISSING |\n")
                continue
            if ep in R1_EXPECTED:
                expected = "R1"
            elif ep in R2_EXPECTED:
                expected = "R2"
            elif ep in COMBAT_DENSE_EXPECTED:
                expected = "neg_combat"
            else:
                expected = "neg_low"
            ec_cats_ep = [r["category"] for r in by_ep.get(ep, {}).get("EC", [])]
            f.write(
                f"| {ep} | {expected} | {res['rule_R1']} | {res['rule_R2']} | "
                f"{','.join(ec_cats_ep) or '-'} | "
                f"{res['_late_frac_r1']} | {res['_late_frac_r2']} | "
                f"{res['cc_count']} | {stream_totals.get(ep, '?')} | "
                f"{res['_neg_combat_dense']} | {res['_neg_low_activity']} | "
                f"{res['final_classification']} |\n"
            )
        f.write("\n")
        f.write(f"**Discrepancy:** C1E040 expected R1 but EC cat=player_action_escalation "
                f"not in R1_EC_CATS. Documented above; no adjustment made (STOP condition "
                f"C1E114 passed).\n\n")
        f.write("---\n\n")
        f.write("## Per-Episode Table\n\n")
        f.write("| episode | ec | tm | lr | cc | late_frac | R1 | R2 | R3 | stat | dropped | classification |\n")
        f.write("|---------|----|----|----|----|-----------|----|----|-----|------|---------|----------------|\n")
        for ep in sorted(ep_results.keys()):
            r = ep_results[ep]
            f.write(
                f"| {ep} | {r['ec_count']} | {r['tm_count']} | {r['lr_count']} | "
                f"{r['cc_count']} | {r['late_frac']} | {r['rule_R1']} | {r['rule_R2']} | "
                f"{r['rule_R3_count']} | {r['stat_flag']} | {r['negative_rule_dropped']} | "
                f"{r['final_classification']} |\n"
            )
        f.write("\n---\n\n")
        f.write("## Corpus-Level Summary\n\n")
        f.write(f"| Metric | Value |\n|--------|-------|\n")
        f.write(f"| Total episodes | {len(all_eps)} |\n")
        f.write(f"| 25th pct threshold | {p25_threshold} total records |\n")
        for cls in [
            "climactic_hold_combat", "climactic_hold_reward", "lr_x2_absence",
            "stat_outlier_only", "dropped_negative_rule", "no_flag"
        ]:
            f.write(f"| {cls} | {classifications[cls]} |\n")
        f.write(f"| Rule-vs-stat disagreement | {disagreement} |\n")
    print(f"Markdown written: {md_path}")

    return {
        "scope_eps": len(all_eps),
        "classifications": dict(classifications),
        "r1_c1e114": r1_c1e114,
        "r1_c1e040": r1_c1e040,
        "r1_c1e076": ep_results.get("C1E076", {}).get("rule_R1", False),
        "r2_c1e108": r2_c1e108,
        "rule_only": rule_only,
        "stat_only": stat_only,
        "both": both_rule_stat,
        "neither": neither,
    }


if __name__ == "__main__":
    run()
