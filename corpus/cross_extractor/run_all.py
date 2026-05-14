"""
run_all.py — Orchestrates X1, X5, X3, X4 in order and prints final report.
Run order: x_utils (import) → X1 → X5 → X3 → X4
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 60)
print("Running X1: Unified scene-boundary count")
print("=" * 60)
import analysis_x1
x1 = analysis_x1.run()

print("\n" + "=" * 60)
print("Running X5: TM combat-state expansion via EC join")
print("=" * 60)
import analysis_x5
x5 = analysis_x5.run()

print("\n" + "=" * 60)
print("Running X3: Reward-after-EC-buildup cadence")
print("=" * 60)
import analysis_x3
x3 = analysis_x3.run()

print("\n" + "=" * 60)
print("Running X4: Negative-signal rate")
print("=" * 60)
import analysis_x4
x4 = analysis_x4.run()

if x4 is None:
    print("\n!!! X4 halted due to sanity check failure. Final report not printed.")
    sys.exit(1)

# Final report
print("\n")
print("=" * 60)
print("=== X1 RESULTS ===")
print(f"Scope: {x1['n_episodes']} episodes (all-4-source intersection)")
print(f"CC single-extractor mean: 2.97 boundaries/ep")
print(f"Unified scene-count mean: {x1['mean']:.2f} / median: {x1['median']} / max: {x1['max']}")
t = x1['total_clusters']
print(
    f"Source-contribution histogram: "
    f"1-src={x1['total_1src']}({100*x1['total_1src']/t:.1f}%) "
    f"2-src={x1['total_2src']}({100*x1['total_2src']/t:.1f}%) "
    f"3-src={x1['total_3src']}({100*x1['total_3src']/t:.1f}%)"
)

print("\n=== X5 RESULTS ===")
print(f"Scope: {x5['scope_eps']} episodes (EC×TM intersection), {x5['total_tm']} TM records")
print(f"TM baseline is_combat_state: {x5['baseline_true']} records ({100*x5['baseline_rate']:.1f}%)")
print(f"TM expanded (EC join ±25t): {x5['expanded_true']} records ({100*x5['expanded_rate']:.1f}%)")
delta_pp = 100 * (x5['expanded_rate'] - x5['baseline_rate'])
print(f"Expansion delta: +{x5['n_flipped']} records (+{delta_pp:.1f}pp)")
print(f"Top category for expansion: {x5['top_cat']} ({x5['top_cat_flips']} flips)")

print("\n=== X3 RESULTS ===")
wc = x3['window_counts']
total_lr = x3['total_lr']
print(f"Scope: {x3['scope_eps']} episodes (EC×LR intersection), {total_lr} LR records")
print(f"LR single-extractor baseline (8t window): 7.4%")
print(f"Window=8:  {wc[8]}/{total_lr} ({100*wc[8]/total_lr:.1f}%)  vs 7.4% baseline")
print(f"Window=15: {wc[15]}/{total_lr} ({100*wc[15]/total_lr:.1f}%)")
print(f"Window=25: {wc[25]}/{total_lr} ({100*wc[25]/total_lr:.1f}%)")
print(f"Window=40: {wc[40]}/{total_lr} ({100*wc[40]/total_lr:.1f}%)")
print(f"Hypothesis (15-25% at any-distance-within-scene): {x3['hypothesis']}")

print("\n=== X4 RESULTS ===")
cls = x4['classifications']
print(f"Scope: {x4['scope_eps']} episodes")
print(f"Classification counts:")
print(f"  climactic_hold_combat:  {cls.get('climactic_hold_combat', 0)}")
print(f"  climactic_hold_reward:  {cls.get('climactic_hold_reward', 0)}")
print(f"  lr_x2_absence:          {cls.get('lr_x2_absence', 0)}")
print(f"  stat_outlier_only:      {cls.get('stat_outlier_only', 0)}")
print(f"  dropped_negative_rule:  {cls.get('dropped_negative_rule', 0)}")
print(f"  no_flag:                {cls.get('no_flag', 0)}")
print(f"R1 fires on C1E114: {'YES' if x4['r1_c1e114'] else 'NO'}")
print(f"R1 fires on C1E040: {'YES' if x4['r1_c1e040'] else 'NO'} "
      f"(EC cat=player_action_escalation, not in R1_EC_CATS — documented discrepancy)")
print(f"R1 fires on C1E076: {'YES' if x4['r1_c1e076'] else 'NO'}")
print(f"R2 fires on C1E108: {'YES' if x4['r2_c1e108'] else 'NO'}")
print(f"Rule-only: {x4['rule_only']}  Stat-only: {x4['stat_only']}  "
      f"Both: {x4['both']}  Neither: {x4['neither']}")
