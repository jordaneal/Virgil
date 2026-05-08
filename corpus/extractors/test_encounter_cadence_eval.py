#!/usr/bin/env python3
"""
Regression test for the Encounter Cadence extractor against
findings/encounter_cadence_eval_set_v1.json.

Loads the eval set, runs the extractor against each unique sample episode in
the eval set, and asserts per-record:
  - trigger_category matches expected_category
  - is_fresh_encounter matches expected_is_fresh_encounter
  - wave_subtype matches expected_wave_subtype
  - player_action_caused matches expected_player_action_caused (when specified)

Prints per-record pass/fail and total precision rate. Exit code 0 if precision
>= the configured threshold, 1 otherwise. Use this script after every
extractor calibration patch to catch regressions.

Usage:
    python3 test_encounter_cadence_eval.py [--threshold 0.70]
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import encounter_cadence as ec

CORPUS_BUILDER = Path(__file__).resolve().parent.parent
EVAL_SET_PATH = CORPUS_BUILDER / "findings" / "encounter_cadence_eval_set_v1.json"


def trigger_id_for(record):
    return f"{record['campaign']}E{record['episode']:03d}_t{record['trigger_turn_number']}"


def run_eval(threshold):
    if not EVAL_SET_PATH.exists():
        print(f"FATAL: eval set missing at {EVAL_SET_PATH}", file=sys.stderr)
        return 2

    with open(EVAL_SET_PATH, "r", encoding="utf-8") as f:
        eval_set = json.load(f)

    eval_by_id = {e["trigger_id"]: e for e in eval_set}
    episodes = sorted({f"{e['campaign']}E{e['episode']:03d}" for e in eval_set})
    extracted_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

    # Run extractor on each episode and collect records keyed by trigger_id.
    records_by_id = {}
    for ep in episodes:
        for rec in ec.process_episode(ep, extracted_at):
            records_by_id[trigger_id_for(rec)] = rec

    # Header.
    print(f"Eval set: {EVAL_SET_PATH}")
    print(f"Episodes: {len(episodes)}")
    print(f"Eval records: {len(eval_set)}")
    print(f"Extractor records produced for eval episodes: {len(records_by_id)}")
    print()
    print(f"{'trigger_id':<22} {'cat':<32} {'expected':<32} {'fresh':<6} {'wave':<13} {'PAC':<5} verdict")
    print("-" * 130)

    correct = 0
    failures = []
    for expected in eval_set:
        tid = expected["trigger_id"]
        rec = records_by_id.get(tid)
        if rec is None:
            failures.append((tid, "no record produced"))
            print(f"{tid:<22} {'(none)':<32} {expected['expected_category']:<32} {'-':<6} {'-':<13} {'-':<5} MISS")
            continue

        cat_ok = rec["trigger_category"] == expected["expected_category"]
        fresh_ok = rec["is_fresh_encounter"] == expected["expected_is_fresh_encounter"]
        wave_ok = rec["wave_subtype"] == expected["expected_wave_subtype"]
        pac_exp = expected.get("expected_player_action_caused")
        pac_ok = True if pac_exp is None else rec["player_action_caused"] == pac_exp

        all_ok = cat_ok and fresh_ok and wave_ok and pac_ok
        if all_ok:
            correct += 1
            verdict = "OK"
        else:
            mismatches = []
            if not cat_ok:
                mismatches.append(f"cat({rec['trigger_category']}!={expected['expected_category']})")
            if not fresh_ok:
                mismatches.append(f"fresh({rec['is_fresh_encounter']}!={expected['expected_is_fresh_encounter']})")
            if not wave_ok:
                mismatches.append(f"wave({rec['wave_subtype']}!={expected['expected_wave_subtype']})")
            if not pac_ok:
                mismatches.append(f"pac({rec['player_action_caused']}!={pac_exp})")
            failures.append((tid, ", ".join(mismatches)))
            verdict = "FAIL"

        pac_str = str(rec["player_action_caused"])[:5]
        print(
            f"{tid:<22} {rec['trigger_category']:<32} "
            f"{expected['expected_category']:<32} "
            f"{str(rec['is_fresh_encounter']):<6} "
            f"{str(rec['wave_subtype']):<13} "
            f"{pac_str:<5} {verdict}"
        )

    total = len(eval_set)
    precision = correct / total if total else 0.0
    print()
    print(f"PRECISION: {correct}/{total} = {precision*100:.1f}%")
    print(f"Threshold: {threshold*100:.0f}%  ->  {'PASS' if precision >= threshold else 'FAIL'}")

    if failures:
        print(f"\nFailures ({len(failures)}):")
        for tid, reason in failures:
            print(f"  {tid}: {reason}")

    return 0 if precision >= threshold else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--threshold", type=float, default=0.70,
                        help="Minimum precision required to pass (default 0.70).")
    args = parser.parse_args()
    sys.exit(run_eval(args.threshold))


if __name__ == "__main__":
    main()
