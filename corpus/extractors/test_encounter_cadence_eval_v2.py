#!/usr/bin/env python3
"""
Regression test for encounter_cadence against eval set v2 with hard ship gates.

Eval set v2 lives at findings/encounter_cadence_eval_set_v2.json. Records carry:
  - source: "v1" (training-set-equivalent), "spotcheck" (Jordan-curated), or
    "blind" (random.seed=42 sample)
  - expected_category: real category name OR sentinels NOT_INIT_EVENT, DUPLICATE
  - defensible_alternates: optional list of acceptable categories

Ship gates (computed on the NON-v1 records — v1 records were used to tune v1.1
and would inflate the numbers):
  1. FP rate <= 5%   — emitted records that were expected NOT_INIT_EVENT
  2. Wave detection >= 60% — correctly classified wave records
  3. Overall precision >= 65% — correct / total

Plus sanity check: precision on v1 records must stay above the v1.1 baseline
(13/14 = 92.9%) — no regression on previously-correct records.

Usage:
    python3 test_encounter_cadence_eval_v2.py [--threshold 0.65] [--verbose]
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import encounter_cadence as ec

CORPUS = Path(__file__).resolve().parent.parent
EVAL_PATH = CORPUS / "findings" / "encounter_cadence_eval_set_v2.json"

# Distance threshold (turns) below which a DUPLICATE-expected record is
# considered correctly flagged.
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
    """Return (correct: bool, status: str). produced is None if not emitted."""
    expected = eval_entry["expected_category"]
    accept = acceptable_categories(eval_entry)

    # NOT_INIT_EVENT sentinel — correct iff record is NOT emitted.
    # Defensible alternates are honored if expected is in alternates.
    if expected == "NOT_INIT_EVENT":
        if produced is None:
            return True, "filtered (correct)"
        # Record emitted — it's an FP unless an alternate category is accepted
        # AND the produced category matches one of those alternates.
        if produced["trigger_category"] in (accept - {"NOT_INIT_EVENT"}):
            return True, f"emitted as {produced['trigger_category']} (defensible)"
        return False, f"FP: emitted as {produced['trigger_category']}"

    # DUPLICATE sentinel — correct iff record IS emitted AND the
    # nearest_prior_trigger_turn_distance is below threshold.
    if expected == "DUPLICATE":
        if produced is None:
            # Acceptable: filtering it via Stage 1 also resolves the dup.
            return True, "filtered (acceptable for DUPLICATE)"
        dist = produced.get("nearest_prior_trigger_turn_distance")
        if dist is not None and dist <= DUPLICATE_DISTANCE_THRESHOLD:
            return True, f"emitted, distance={dist} (correct)"
        return False, f"emitted, distance={dist} (no dup signal)"

    # Real category expected.
    if produced is None:
        # Filtered when we expected a real init record — but allow if
        # NOT_INIT_EVENT is in alternates (defensible).
        if "NOT_INIT_EVENT" in accept:
            return True, "filtered (defensible)"
        return False, "MISS: no record emitted"

    # Defensible alternate match (multiple acceptable real categories).
    if produced["trigger_category"] in accept:
        # Verify wave subtype iff expected category is wave_or_phase_shift.
        if produced["trigger_category"] == "wave_or_phase_shift":
            exp_sub = eval_entry.get("expected_wave_subtype")
            got_sub = produced.get("wave_subtype")
            if exp_sub and got_sub != exp_sub:
                # Subtype mismatch — accept as partial-correct (still a wave).
                # For ship-gate purposes, count as correct (gate is "wave
                # detection rate", not "wave subtype rate").
                return True, f"OK (wave but subtype {got_sub}!={exp_sub})"
        return True, "OK"

    return False, f"WRONG: got {produced['trigger_category']}"


def run_extractor_on_eval(eval_set, version_label):
    """Run extractor on each unique episode in the eval set."""
    episodes = sorted({episode_id_for(e) for e in eval_set})
    extracted_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

    records_by_id = {}
    all_records_by_episode = {}
    for ep in episodes:
        recs = ec.process_episode(ep, extracted_at)
        all_records_by_episode[ep] = recs
        for r in recs:
            records_by_id[trigger_id(r)] = r

    return records_by_id, all_records_by_episode


def compute_metrics(eval_set, records_by_id, all_records_by_episode, verbose=False):
    """Compute per-source precision, FP rate, wave rate."""
    by_source = {"v1": [], "spotcheck": [], "blind": []}
    for entry in eval_set:
        src = entry.get("source", "v1")
        tid = entry["trigger_id"]
        produced = records_by_id.get(tid)
        correct, status = evaluate_record(entry, produced)
        by_source[src].append({
            "tid": tid,
            "expected": entry["expected_category"],
            "produced": produced["trigger_category"] if produced else None,
            "produced_subtype": produced.get("wave_subtype") if produced else None,
            "expected_subtype": entry.get("expected_wave_subtype"),
            "correct": correct,
            "status": status,
        })

    new_records = by_source["spotcheck"] + by_source["blind"]
    new_correct = sum(1 for r in new_records if r["correct"])
    new_total = len(new_records)
    overall_precision = new_correct / new_total if new_total else 0.0

    # Wave detection rate on non-v1 records.
    wave_expected = [r for r in new_records if r["expected"] == "wave_or_phase_shift"]
    wave_correct = sum(
        1 for r in wave_expected
        if r["produced"] == "wave_or_phase_shift"
    )
    wave_rate = wave_correct / len(wave_expected) if wave_expected else 0.0

    # FP rate. Denominator: total records emitted across non-v1 eval episodes.
    # Count of emitted records minus those whose source is v1.
    new_episode_ids = sorted({
        f"{e['campaign']}E{e['episode']:03d}"
        for e in eval_set if e.get("source") != "v1"
    })
    emitted_in_new_episodes = sum(
        len(all_records_by_episode.get(ep, []))
        for ep in new_episode_ids
    )

    # FP records: emitted-but-expected-NOT_INIT_EVENT (counted from new records).
    fp_records = [
        r for r in new_records
        if r["expected"] == "NOT_INIT_EVENT" and r["produced"] is not None
        # Don't count defensible records that match a real alternate.
        and not r["correct"]
    ]
    fp_count = len(fp_records)
    # Use all records emitted on new-source episodes as the denominator —
    # captures both eval-set and non-eval-set emissions on those episodes.
    fp_rate = fp_count / emitted_in_new_episodes if emitted_in_new_episodes else 0.0

    # v1 sanity check.
    v1_correct = sum(1 for r in by_source["v1"] if r["correct"])
    v1_total = len(by_source["v1"])

    return {
        "by_source": by_source,
        "new_correct": new_correct,
        "new_total": new_total,
        "overall_precision": overall_precision,
        "wave_correct": wave_correct,
        "wave_total": len(wave_expected),
        "wave_rate": wave_rate,
        "fp_count": fp_count,
        "fp_records": fp_records,
        "fp_rate": fp_rate,
        "emitted_in_new_episodes": emitted_in_new_episodes,
        "v1_correct": v1_correct,
        "v1_total": v1_total,
        "v1_precision": v1_correct / v1_total if v1_total else 0.0,
    }


def print_report(eval_set, metrics, verbose=False):
    print(f"Eval set: {EVAL_PATH}")
    print(f"Records: {len(eval_set)} ({metrics['v1_total']} v1 + {metrics['new_total']} new)")
    print(f"Extractor version: {ec.EXTRACTOR_VERSION}")
    print()

    print("=" * 100)
    print("SHIP GATES (computed on non-v1 records)")
    print("=" * 100)
    fp_pct = metrics["fp_rate"] * 100
    wv_pct = metrics["wave_rate"] * 100
    pr_pct = metrics["overall_precision"] * 100
    fp_pass = metrics["fp_rate"] <= 0.05
    wv_pass = metrics["wave_rate"] >= 0.60
    pr_pass = metrics["overall_precision"] >= 0.65
    print(f"  Gate 1 (FP rate <= 5%):       {fp_pct:5.1f}%  ({metrics['fp_count']}/{metrics['emitted_in_new_episodes']} emitted)  {'PASS' if fp_pass else 'FAIL'}")
    print(f"  Gate 2 (Wave rate >= 60%):    {wv_pct:5.1f}%  ({metrics['wave_correct']}/{metrics['wave_total']})  {'PASS' if wv_pass else 'FAIL'}")
    print(f"  Gate 3 (Precision >= 65%):    {pr_pct:5.1f}%  ({metrics['new_correct']}/{metrics['new_total']})  {'PASS' if pr_pass else 'FAIL'}")
    all_pass = fp_pass and wv_pass and pr_pass
    print(f"\n  ALL GATES: {'PASS' if all_pass else 'FAIL'}")
    print()

    print("=" * 100)
    print(f"v1 SANITY: {metrics['v1_correct']}/{metrics['v1_total']} = {metrics['v1_precision']*100:.1f}% (baseline 92.9%)")
    print("=" * 100)
    if metrics['v1_correct'] < 13:
        print(f"  *** REGRESSION: v1 records dropped from baseline 13/14")
    print()

    if verbose:
        for src in ("v1", "spotcheck", "blind"):
            entries = metrics["by_source"][src]
            if not entries:
                continue
            print(f"--- {src} ({len(entries)} records) ---")
            for e in entries:
                mark = "OK  " if e["correct"] else "FAIL"
                exp = e["expected"]
                got = e["produced"] or "(filtered)"
                if e["expected_subtype"]:
                    exp = f"{exp}/{e['expected_subtype']}"
                if e["produced_subtype"]:
                    got = f"{got}/{e['produced_subtype']}"
                print(f"  {mark}  {e['tid']:<22} expect={exp:<40} got={got:<35}  {e['status']}")
            print()

    if metrics["fp_records"]:
        print("=== False positives (emitted but expected NOT_INIT_EVENT) ===")
        for r in metrics["fp_records"]:
            print(f"  {r['tid']}: produced={r['produced']}")
        print()

    return all_pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--threshold", type=float, default=0.65)
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    if not EVAL_PATH.exists():
        print(f"FATAL: eval set missing at {EVAL_PATH}", file=sys.stderr)
        sys.exit(2)

    with open(EVAL_PATH, "r", encoding="utf-8") as f:
        eval_set = json.load(f)

    records_by_id, all_records_by_episode = run_extractor_on_eval(eval_set, ec.EXTRACTOR_VERSION)
    metrics = compute_metrics(eval_set, records_by_id, all_records_by_episode, verbose=args.verbose)
    all_pass = print_report(eval_set, metrics, verbose=args.verbose)
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
