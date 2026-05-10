#!/usr/bin/env python3
"""
Regression test for compression_cadence v1.

Two modes:

  (default / --handsample)
      Runs against eval set v2 (compression_cadence_handsample_v2.json, key "handsample").
      Computes strict precision = v2-correct records still emitted correctly /
      total records emitted from all 10 hand-sample episodes.

  --gate
      Runs against the Phase 4 gate-set (compression_cadence_gate_v1.json, key "gate").
      Before blind judging: expected_* fields are null → runner reports
      "all N unjudged — blind judging pending" without crashing.
      After blind judging: expected_category populated → reports gate precision.

Expected-category sentinels:
  - NONE : record SHOULD NOT be emitted (Stage 0 DISCOURSE reject expected).
  - verdict_at_v2 == "duplicate" : also should not be emitted (within-turn dedup).

Usage:
    python3 test_compression_cadence.py                      # handsample, concise
    python3 test_compression_cadence.py --verbose             # handsample, per-record
    python3 test_compression_cadence.py --gate               # gate-set mode
    python3 test_compression_cadence.py --gate --verbose     # gate-set, per-record
"""

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import compression_cadence as cc

CORPUS = Path(__file__).resolve().parent.parent
EVAL_PATH = CORPUS / "eval_sets" / "compression_cadence_handsample_v2.json"
GATE_PATH = CORPUS / "eval_sets" / "compression_cadence_gate_v1.json"


def make_trigger_id(record):
    """Build trigger_id string from a produced compression_cadence record."""
    return f"{record['campaign']}E{record['episode']:03d}_t{record['trigger_turn_number']}"


def episodes_for(eval_records):
    eps = set()
    for r in eval_records:
        tid = r.get("trigger_id", "")
        if "_t" in tid:
            ep = tid.split("_t")[0]
            eps.add(ep)
    return sorted(eps)


def run_extractor_on_episodes(episodes):
    extracted_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    produced_by_id = {}
    total_emitted = 0
    for ep in episodes:
        recs = cc.process_episode(ep, extracted_at)
        total_emitted += len(recs)
        for r in recs:
            tid = make_trigger_id(r)
            key = (tid, r["same_turn_record_index"])
            produced_by_id[key] = r
    return produced_by_id, total_emitted


# ---------------------------------------------------------------------------
# Handsample evaluation (Phase 2/3 calibration)
# ---------------------------------------------------------------------------

def evaluate_handsample(eval_records, produced_by_id, total_emitted, verbose=False):
    """
    Per-record classification:
      OK_strict      - v2_verdict=correct, still emitted with correct category
      OK_defensible  - v2_verdict=defensible, still emitted with correct category
      OK_filtered    - expected_category=NONE or verdict=duplicate, correctly NOT emitted
      FP             - expected_category=NONE or verdict=duplicate, still emitted (false positive)
      MISS           - expected_category!=NONE and not duplicate, not emitted (dropped correct record)
      WRONG_CAT      - expected_category!=NONE and not duplicate, emitted with wrong category
    """
    strict_correct = 0
    regressions = []

    # Failure-family tracking for all wrong outcomes.
    family_outcomes = defaultdict(list)
    rows = []

    for entry in eval_records:
        tid = entry["trigger_id"]
        same_turn_idx = entry.get("same_turn_record_index", 0)
        key = (tid, same_turn_idx)
        produced = produced_by_id.get(key)
        expected_cat = entry["expected_category"]
        v2_verdict = entry.get("verdict_at_v2", "")
        family = entry.get("failure_family")

        # Records that should NOT be emitted: NONE sentinel or duplicate verdict.
        should_reject = (expected_cat == "NONE") or (v2_verdict == "duplicate")

        if should_reject:
            if produced is None:
                status = "OK_filtered"
            else:
                produced_cat = produced["compression_category"]
                status = f"FP: emitted as {produced_cat!r}"
            rows.append((entry, produced, status))
            if family:
                family_outcomes[family].append(status)
            continue

        # Records that should be emitted.
        if produced is None:
            status = "MISS: no record emitted"
            if v2_verdict == "correct":
                regressions.append((entry, None, status))
        else:
            produced_cat = produced["compression_category"]
            if produced_cat == expected_cat:
                if v2_verdict == "correct":
                    status = "OK_strict"
                    strict_correct += 1
                else:
                    status = f"OK_defensible ({v2_verdict})"
            else:
                status = f"WRONG_CAT: got {produced_cat!r} expected {expected_cat!r}"
                if v2_verdict == "correct":
                    regressions.append((entry, produced, status))
        rows.append((entry, produced, status))
        if family:
            family_outcomes[family].append(status)

    total_eval = len(eval_records)
    strict_pct = strict_correct / total_emitted if total_emitted else 0.0

    print(f"\n=== compression_cadence eval results ({total_eval} v2 records) ===")
    print(f"  Total emitted (all hand-sample episodes): {total_emitted}")
    print(f"  Strict correct (v2=correct, match):       {strict_correct}")
    print(f"  Strict precision:                         {strict_correct}/{total_emitted} = {strict_pct:.4f} ({100*strict_pct:.1f}%)")

    print()
    print("--- per-failure-family outcome (should-reject + wrong-category families) ---")
    for fam, outcomes in sorted(family_outcomes.items()):
        total_fam = len(outcomes)
        still_wrong = sum(1 for s in outcomes if s.startswith("FP") or s.startswith("WRONG") or s.startswith("MISS"))
        icon = "CLEAR" if still_wrong == 0 else "REMAINING"
        print(f"  {fam}: {still_wrong}/{total_fam} still wrong  [{icon}]")

    print()
    if regressions:
        print(f"*** RETENTION REGRESSIONS ({len(regressions)}) — v2-correct records now wrong ***")
        for entry, produced, status in regressions:
            t = entry["trigger_id"]
            idx = entry.get("same_turn_record_index", 0)
            phrase = entry.get("trigger_phrase", "")
            print(f"  {t}#{idx}  phrase={phrase!r}  {status}")
    else:
        print("Retention regressions: NONE")

    if verbose:
        print("\n--- per-record verdicts ---")
        for entry, produced, verdict in rows:
            t = entry["trigger_id"]
            idx = entry.get("same_turn_record_index", 0)
            phrase = entry.get("trigger_phrase", "")
            print(f"  {t}#{idx:<3} {verdict:<60}  phrase={phrase!r}")

    return {
        "total_eval": total_eval,
        "strict_correct": strict_correct,
        "total_emitted": total_emitted,
        "strict_pct": strict_pct,
        "regressions": regressions,
    }


# ---------------------------------------------------------------------------
# Gate-set evaluation (Phase 4 blind judging)
# ---------------------------------------------------------------------------

def evaluate_gate(gate_records, produced_by_id, total_emitted, verbose=False):
    """
    Gate-set mode. Before blind judging: expected_category is null → all records
    are unjudged. After judging: expected_category populated; sentinel NONE means
    should-be-rejected.

    Gate precision (Phase 4 definition):
      strict_correct / total_emitted  (same denominator as Phase 3)
    """
    unjudged = 0
    strict_correct = 0
    fp_count = 0
    miss_count = 0
    wrong_cat = 0
    not_emitted_ok = 0

    rows = []
    for entry in gate_records:
        tid = entry["trigger_id"]
        idx = entry.get("same_turn_record_index", 0)
        key = (tid, idx)
        produced = produced_by_id.get(key)
        expected_cat = entry.get("expected_category")
        v1_verdict = entry.get("verdict_at_v1")

        if expected_cat is None:
            unjudged += 1
            if produced:
                emitted_as = produced["compression_category"]
                status = f"UNJUDGED (currently emitted as {emitted_as!r})"
            else:
                status = "UNJUDGED (not emitted)"
        elif expected_cat == "NONE":
            if produced is None:
                status = "OK_filtered"
                not_emitted_ok += 1
            else:
                status = f"FP: emitted as {produced['compression_category']!r}"
                fp_count += 1
        else:
            if produced is None:
                status = "MISS: no record emitted"
                miss_count += 1
            else:
                produced_cat = produced["compression_category"]
                if produced_cat == expected_cat:
                    if v1_verdict == "correct":
                        status = "OK_strict"
                        strict_correct += 1
                    else:
                        status = f"OK_defensible ({v1_verdict})"
                else:
                    status = f"WRONG_CAT: got {produced_cat!r} expected {expected_cat!r}"
                    wrong_cat += 1

        rows.append((entry, produced, status))

    total_gate = len(gate_records)
    judged = total_gate - unjudged
    strict_pct = strict_correct / total_emitted if (judged > 0 and total_emitted) else None

    print(f"\n=== compression_cadence gate results ({total_gate} gate records) ===")
    print(f"  Total emitted (all recon episodes):          {total_emitted}")
    print(f"  Gate records judged / total:                 {judged} / {total_gate}")
    if unjudged:
        print(f"  Unjudged (expected_category=null):           {unjudged}  [blind judging pending]")
    if judged > 0:
        print(f"  Strict correct (v1=correct, match):          {strict_correct}")
        print(f"  FPs (should-be-rejected, still emitted):     {fp_count}")
        print(f"  Misses (should-emit, not emitted):           {miss_count}")
        print(f"  Wrong category:                              {wrong_cat}")
        if strict_pct is not None:
            print(f"  Gate strict precision:                       "
                  f"{strict_correct}/{total_emitted} = {strict_pct:.4f} ({100*strict_pct:.1f}%)")
    else:
        print("  [All records unjudged — paste gate JSON to Claude for blind judging]")

    if verbose:
        print("\n--- per-record verdicts ---")
        for entry, produced, verdict in rows:
            t = entry["trigger_id"]
            i = entry.get("same_turn_record_index", 0)
            phrase = entry.get("trigger_phrase", "")
            print(f"  {t}#{i:<3} {verdict:<60}  phrase={phrase!r}")

    return {
        "total_gate": total_gate,
        "unjudged": unjudged,
        "strict_correct": strict_correct,
        "total_emitted": total_emitted,
        "strict_pct": strict_pct,
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verbose", action="store_true",
                        help="Print per-record verdicts.")
    parser.add_argument("--gate", action="store_true",
                        help="Run against the Phase 4 gate-set.")
    args = parser.parse_args()

    if args.gate:
        if not GATE_PATH.exists():
            print(f"FATAL: gate-set not found: {GATE_PATH}", file=sys.stderr)
            sys.exit(2)
        with open(GATE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        gate_records = data.get("gate", [])
        if not gate_records:
            print("FATAL: 'gate' key missing or empty in gate-set.", file=sys.stderr)
            sys.exit(2)
        print(f"Loaded {len(gate_records)} gate records from {GATE_PATH.name}")
        episodes = episodes_for(gate_records)
        print(f"Running extractor on {len(episodes)} episode(s): {episodes}")
        produced_by_id, total_emitted = run_extractor_on_episodes(episodes)
        evaluate_gate(gate_records, produced_by_id, total_emitted, verbose=args.verbose)
    else:
        if not EVAL_PATH.exists():
            print(f"FATAL: eval set not found: {EVAL_PATH}", file=sys.stderr)
            sys.exit(2)
        with open(EVAL_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        eval_records = data.get("handsample", [])
        if not eval_records:
            print("FATAL: 'handsample' key missing or empty in eval set.", file=sys.stderr)
            sys.exit(2)
        print(f"Loaded {len(eval_records)} eval records from {EVAL_PATH.name}")
        episodes = episodes_for(eval_records)
        print(f"Running extractor on {len(episodes)} episode(s): {episodes}")
        produced_by_id, total_emitted = run_extractor_on_episodes(episodes)
        evaluate_handsample(eval_records, produced_by_id, total_emitted, verbose=args.verbose)


if __name__ == "__main__":
    main()
