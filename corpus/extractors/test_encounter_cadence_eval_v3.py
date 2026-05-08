#!/usr/bin/env python3
"""
Regression test for encounter_cadence against eval set v3.

Two splits, computed independently:
  - calibration_set (84 records): full per-record verbose output, used to
    drive patch development. v1.2 baseline metrics (precision >= 65%, wave
    >= 60% on the 55 non-v1 records, FP <= 5%) must not regress.
  - holdout_set (25 records): SHIP-GATE measurement only. Run with
    --holdout. Default mode (calibration only) does NOT touch holdout, to
    prevent accidental optimization against it.

Held-out ship gates (computed only when --holdout flag passed):
  1. FP rate <= 8% on held-out
  2. Wave detection >= 50% on held-out
  3. Strict precision >= 50% on held-out
  4. No regression on the 55-record non-v1 calibration subset
     (precision >= 65%, wave >= 60%, FP <= 5%)

Usage:
    python3 test_encounter_cadence_eval_v3.py                # calibration only
    python3 test_encounter_cadence_eval_v3.py --verbose      # detail per record
    python3 test_encounter_cadence_eval_v3.py --holdout      # also measure held-out
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import encounter_cadence as ec

CORPUS = Path(__file__).resolve().parent.parent
EVAL_PATH = CORPUS / "findings" / "encounter_cadence_eval_set_v3.json"

DUPLICATE_DISTANCE_THRESHOLD = 30


def trigger_id(record):
    return f"{record['campaign']}E{record['episode']:03d}_t{record['trigger_turn_number']}"


def episode_id_for(eval_entry):
    return f"{eval_entry['campaign']}E{eval_entry['episode']:03d}"


def acceptable_categories(eval_entry):
    if eval_entry.get("defensible_alternates"):
        return set(eval_entry["defensible_alternates"])
    return {eval_entry["expected_category"]}


def evaluate_record(eval_entry, produced):
    expected = eval_entry["expected_category"]
    accept = acceptable_categories(eval_entry)

    if expected == "NOT_INIT_EVENT":
        if produced is None:
            return True, "filtered (correct)"
        if produced["trigger_category"] in (accept - {"NOT_INIT_EVENT"}):
            return True, f"emitted as {produced['trigger_category']} (defensible)"
        return False, f"FP: emitted as {produced['trigger_category']}"

    if expected == "DUPLICATE":
        if produced is None:
            return True, "filtered (acceptable for DUPLICATE)"
        dist = produced.get("nearest_prior_trigger_turn_distance")
        if dist is not None and dist <= DUPLICATE_DISTANCE_THRESHOLD:
            return True, f"emitted, distance={dist} (correct)"
        return False, f"emitted, distance={dist} (no dup signal)"

    if produced is None:
        if "NOT_INIT_EVENT" in accept:
            return True, "filtered (defensible)"
        return False, "MISS: no record emitted"

    if produced["trigger_category"] in accept:
        if produced["trigger_category"] == "wave_or_phase_shift":
            exp_sub = eval_entry.get("expected_wave_subtype")
            got_sub = produced.get("wave_subtype")
            if exp_sub and got_sub != exp_sub:
                return True, f"OK (wave but subtype {got_sub}!={exp_sub})"
        return True, "OK"

    return False, f"WRONG: got {produced['trigger_category']}"


def run_extractor_on_episodes(episodes):
    extracted_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    records_by_id = {}
    all_records_by_episode = {}
    for ep in episodes:
        recs = ec.process_episode(ep, extracted_at)
        all_records_by_episode[ep] = recs
        for r in recs:
            records_by_id[trigger_id(r)] = r
    return records_by_id, all_records_by_episode


def compute_split_metrics(eval_entries, records_by_id, all_records_by_episode):
    """Compute precision, wave rate, FP rate over the given entries."""
    results = []
    for entry in eval_entries:
        tid = entry["trigger_id"]
        produced = records_by_id.get(tid)
        correct, status = evaluate_record(entry, produced)
        results.append({
            "tid": tid,
            "expected": entry["expected_category"],
            "produced": produced["trigger_category"] if produced else None,
            "produced_subtype": produced.get("wave_subtype") if produced else None,
            "expected_subtype": entry.get("expected_wave_subtype"),
            "correct": correct,
            "status": status,
        })

    correct = sum(1 for r in results if r["correct"])
    total = len(results)
    precision = correct / total if total else 0.0

    wave_expected = [r for r in results if r["expected"] == "wave_or_phase_shift"]
    wave_correct = sum(1 for r in wave_expected if r["produced"] == "wave_or_phase_shift")
    wave_rate = wave_correct / len(wave_expected) if wave_expected else 0.0

    episode_ids = sorted({episode_id_for(e) for e in eval_entries})
    emitted_in_episodes = sum(
        len(all_records_by_episode.get(ep, []))
        for ep in episode_ids
    )

    fp_records = [r for r in results
                  if r["expected"] == "NOT_INIT_EVENT"
                  and r["produced"] is not None
                  and not r["correct"]]
    fp_count = len(fp_records)
    fp_rate = fp_count / emitted_in_episodes if emitted_in_episodes else 0.0

    return {
        "results": results,
        "correct": correct,
        "total": total,
        "precision": precision,
        "wave_correct": wave_correct,
        "wave_total": len(wave_expected),
        "wave_rate": wave_rate,
        "fp_count": fp_count,
        "fp_records": fp_records,
        "fp_rate": fp_rate,
        "emitted_in_episodes": emitted_in_episodes,
    }


def print_split_report(name, metrics, verbose=False):
    print(f"--- {name}: {metrics['correct']}/{metrics['total']} = "
          f"{metrics['precision']*100:.1f}% | "
          f"wave {metrics['wave_correct']}/{metrics['wave_total']} = "
          f"{metrics['wave_rate']*100:.1f}% | "
          f"FP {metrics['fp_count']}/{metrics['emitted_in_episodes']} = "
          f"{metrics['fp_rate']*100:.1f}% ---")
    if verbose:
        for r in metrics["results"]:
            mark = "OK  " if r["correct"] else "FAIL"
            exp = r["expected"]
            got = r["produced"] or "(filtered)"
            if r["expected_subtype"]:
                exp = f"{exp}/{r['expected_subtype']}"
            if r["produced_subtype"]:
                got = f"{got}/{r['produced_subtype']}"
            print(f"  {mark}  {r['tid']:<22} expect={exp:<40} got={got:<35}  {r['status']}")
    if metrics["fp_records"]:
        print(f"  FPs: {[r['tid'] for r in metrics['fp_records']]}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--holdout", action="store_true",
                        help="Also run held-out test set and check ship gates. "
                             "Use this only after calibration regression passes.")
    args = parser.parse_args()

    if not EVAL_PATH.exists():
        print(f"FATAL: eval set missing at {EVAL_PATH}", file=sys.stderr)
        sys.exit(2)

    with open(EVAL_PATH, "r", encoding="utf-8") as f:
        eval_set = json.load(f)

    calibration = eval_set["calibration_set"]
    holdout = eval_set["holdout_set"] if args.holdout else None

    # Run extractor on all calibration episodes (and holdout if requested).
    cal_episodes = sorted({episode_id_for(e) for e in calibration})
    holdout_episodes = sorted({episode_id_for(e) for e in holdout}) if holdout else []
    all_episodes = sorted(set(cal_episodes + holdout_episodes))

    records_by_id, all_records_by_episode = run_extractor_on_episodes(all_episodes)

    print(f"Eval set: {EVAL_PATH}")
    print(f"Extractor version: {ec.EXTRACTOR_VERSION}")
    print(f"Calibration: {len(calibration)} records over {len(cal_episodes)} episodes")
    if holdout:
        print(f"Holdout:     {len(holdout)} records over {len(holdout_episodes)} episodes")
    print()

    # Calibration metrics, broken out by source.
    by_source = {}
    for e in calibration:
        by_source.setdefault(e.get("source", "unknown"), []).append(e)

    print("=" * 100)
    print("CALIBRATION SET (patches develop here; baseline = v1.2)")
    print("=" * 100)
    cal_overall = compute_split_metrics(calibration, records_by_id, all_records_by_episode)
    print_split_report(f"Calibration overall ({len(calibration)})", cal_overall,
                       verbose=args.verbose)
    for src in ("v1", "spotcheck", "blind", "phase4_blind"):
        entries = by_source.get(src, [])
        if not entries:
            continue
        m = compute_split_metrics(entries, records_by_id, all_records_by_episode)
        print_split_report(f"{src} subset ({len(entries)})", m,
                           verbose=args.verbose)

    # Non-v1 subset (everything except v1).
    non_v1 = [e for e in calibration if e.get("source") != "v1"]
    non_v1_metrics = compute_split_metrics(non_v1, records_by_id, all_records_by_episode)
    print_split_report(f"non-v1 calibration ({len(non_v1)})", non_v1_metrics)

    # The v1.2 ship-gate baseline subset = v2's 55 records (spotcheck + blind),
    # excluding phase4_blind which is a calibration extension. Gate 4 is
    # measured here for apples-to-apples comparison with v1.2's published
    # metrics (precision >= 65%, wave >= 60%, FP <= 5%).
    v2_subset = [e for e in calibration if e.get("source") in ("spotcheck", "blind")]
    v2_metrics = compute_split_metrics(v2_subset, records_by_id, all_records_by_episode)
    print_split_report(f"v2 subset ({len(v2_subset)} = spotcheck + blind)", v2_metrics)
    print()

    cal_no_regression = (
        v2_metrics["precision"] >= 0.65
        and v2_metrics["wave_rate"] >= 0.60
        and v2_metrics["fp_rate"] <= 0.05
    )

    print(f"Gate 4 baseline check (v1.2 ship-gate metrics on v2 55-record subset):")
    print(f"  precision >= 65%: {v2_metrics['precision']*100:.1f}%  "
          f"{'PASS' if v2_metrics['precision'] >= 0.65 else 'FAIL'}")
    print(f"  wave rate >= 60%: {v2_metrics['wave_rate']*100:.1f}%  "
          f"{'PASS' if v2_metrics['wave_rate'] >= 0.60 else 'FAIL'}")
    print(f"  FP rate    <= 5%: {v2_metrics['fp_rate']*100:.1f}%  "
          f"{'PASS' if v2_metrics['fp_rate'] <= 0.05 else 'FAIL'}")
    print(f"  Gate 4 baseline: {'PASS' if cal_no_regression else 'FAIL'}")
    print()

    if not holdout:
        print("Held-out NOT measured (use --holdout to run ship gates).")
        sys.exit(0 if cal_no_regression else 1)

    # Holdout regression — only run when explicitly requested.
    print("=" * 100)
    print("HELD-OUT SET (ship-gate measurement — DO NOT calibrate against)")
    print("=" * 100)
    h_metrics = compute_split_metrics(holdout, records_by_id, all_records_by_episode)
    print_split_report(f"Holdout ({len(holdout)})", h_metrics, verbose=args.verbose)
    print()

    # Hard ship gates.
    g1 = h_metrics["fp_rate"] <= 0.08
    g2 = h_metrics["wave_rate"] >= 0.50
    g3 = h_metrics["precision"] >= 0.50
    g4 = cal_no_regression

    print("=" * 100)
    print("HARD SHIP GATES")
    print("=" * 100)
    print(f"  Gate 1 (Held-out FP rate <= 8%):     {h_metrics['fp_rate']*100:.1f}%  "
          f"({h_metrics['fp_count']}/{h_metrics['emitted_in_episodes']})  "
          f"{'PASS' if g1 else 'FAIL'}")
    print(f"  Gate 2 (Held-out wave >= 50%):       {h_metrics['wave_rate']*100:.1f}%  "
          f"({h_metrics['wave_correct']}/{h_metrics['wave_total']})  "
          f"{'PASS' if g2 else 'FAIL'}")
    print(f"  Gate 3 (Held-out precision >= 50%):  {h_metrics['precision']*100:.1f}%  "
          f"({h_metrics['correct']}/{h_metrics['total']})  "
          f"{'PASS' if g3 else 'FAIL'}")
    print(f"  Gate 4 (Calibration no-regression):  {'PASS' if g4 else 'FAIL'}")
    print()
    all_pass = g1 and g2 and g3 and g4
    print(f"  ALL GATES: {'PASS' if all_pass else 'FAIL'}")

    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
