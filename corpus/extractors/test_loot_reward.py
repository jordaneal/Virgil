#!/usr/bin/env python3
"""
Regression test for loot_reward v1.

Two modes:

  (default / --handsample)
      Runs against eval set v2 (loot_reward_handsample_v2.json, key "handsample").
      Computes strict precision = v2-correct records still emitted correctly /
      total records emitted from all 10 hand-sample episodes.

  --gate
      Runs against the Phase 4 gate-set (loot_reward_gate_v1.json, key "gate").
      Before blind judging: expected_category fields are null → runner reports
      "unjudged" totals, confirms the extractor still emits each gate record.
      After blind judging: expected_category populated → reports gate precision.

Expected-category sentinels (handsample mode only):
  - NONE : record SHOULD NOT be emitted (Stage 0 DISCOURSE reject expected).

Usage:
    python3 test_loot_reward.py                      # handsample, concise
    python3 test_loot_reward.py --verbose             # handsample, per-record
    python3 test_loot_reward.py --gate                # gate-set mode
    python3 test_loot_reward.py --gate --verbose      # gate-set, per-record
"""

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import loot_reward as lr

CORPUS = Path(__file__).resolve().parent.parent
EVAL_PATH = CORPUS / "eval_sets" / "loot_reward_handsample_v2.json"
GATE_PATH = CORPUS / "eval_sets" / "loot_reward_gate_v2.json"
VALIDATION_PATH = CORPUS / "eval_sets" / "loot_reward_validation_v1.json"


def make_trigger_id(record):
    """Build trigger_id string from a produced loot_reward record."""
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
        recs = lr.process_episode(ep, extracted_at)
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
      OK_filtered    - expected_category=NONE, correctly NOT emitted
      FP             - expected_category=NONE, still emitted (false positive)
      MISS           - expected_category!=NONE, not emitted (dropped correct record)
      WRONG_CAT      - expected_category!=NONE, emitted with wrong category
    """
    strict_correct = 0
    regressions = []

    # FP family tracking (expected=NONE records).
    fp_families = defaultdict(list)
    rows = []

    for entry in eval_records:
        tid = entry["trigger_id"]
        same_turn_idx = entry.get("same_turn_record_index", 0)
        key = (tid, same_turn_idx)
        produced = produced_by_id.get(key)
        expected_cat = entry["expected_category"]
        v2_verdict = entry.get("verdict_at_v2", "")
        family = entry.get("failure_family")

        if expected_cat == "NONE":
            if produced is None:
                status = "OK_filtered"
            else:
                status = f"FP: emitted as {produced['category']!r}"
            rows.append((entry, produced, status))
            if family:
                fp_families[family].append(status)
            continue

        if produced is None:
            status = "MISS: no record emitted"
            if v2_verdict == "correct":
                regressions.append((entry, None, status))
        else:
            produced_cat = produced["category"]
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

    total_eval = len(eval_records)
    strict_pct = strict_correct / total_emitted if total_emitted else 0.0

    print(f"\n=== loot_reward eval results ({total_eval} v2 records) ===")
    print(f"  Total emitted (all hand-sample episodes): {total_emitted}")
    print(f"  Strict correct (v2=correct, match):       {strict_correct}")
    print(f"  Strict precision:                         {strict_correct}/{total_emitted} = {strict_pct:.4f} ({100*strict_pct:.1f}%)")

    print()
    print("--- per-failure-family FP status (expected_category=NONE families) ---")
    for fam, outcomes in sorted(fp_families.items()):
        total_fam = len(outcomes)
        remaining = sum(1 for s in outcomes if s.startswith("FP"))
        icon = "CLEAR" if remaining == 0 else "REMAINING"
        print(f"  {fam}: {remaining}/{total_fam} still emit as FP  [{icon}]")

    print()
    if regressions:
        print(f"*** RETENTION REGRESSIONS ({len(regressions)}) — v2-correct records now wrong ***")
        for entry, produced, status in regressions:
            tid = entry["trigger_id"]
            idx = entry.get("same_turn_record_index", 0)
            phrase = entry.get("trigger_phrase", "")
            print(f"  {tid}#{idx}  phrase={phrase!r}  {status}")
    else:
        print("Retention regressions: NONE")

    if verbose:
        print("\n--- per-record verdicts ---")
        for entry, produced, verdict in rows:
            tid = entry["trigger_id"]
            idx = entry.get("same_turn_record_index", 0)
            phrase = entry.get("trigger_phrase", "")
            print(f"  {tid}#{idx:<3} {verdict:<55}  phrase={phrase!r}")

    return {
        "total_eval": total_eval,
        "strict_correct": strict_correct,
        "total_emitted": total_emitted,
        "strict_pct": strict_pct,
        "regressions": regressions,
    }


# ---------------------------------------------------------------------------
# Gate-set evaluation (Phase 4)
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
    not_emitted_ok = 0  # expected=NONE and correctly not emitted

    rows = []
    for entry in gate_records:
        tid = entry["trigger_id"]
        idx = entry.get("same_turn_record_index", 0)
        key = (tid, idx)
        produced = produced_by_id.get(key)
        expected_cat = entry.get("expected_category")
        v1_verdict = entry.get("verdict_at_v2")

        if expected_cat is None:
            # Not yet judged.
            unjudged += 1
            status = f"UNJUDGED (currently emitted as {produced['category']!r})" if produced else "UNJUDGED (not emitted)"
        elif expected_cat == "NONE":
            if produced is None:
                status = "OK_filtered"
                not_emitted_ok += 1
            else:
                status = f"FP: emitted as {produced['category']!r}"
                fp_count += 1
        else:
            if produced is None:
                status = "MISS: no record emitted"
                miss_count += 1
            else:
                produced_cat = produced["category"]
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

    print(f"\n=== loot_reward gate results ({total_gate} gate records) ===")
    print(f"  Total emitted (all recon episodes):  {total_emitted}")
    print(f"  Gate records judged / total:         {judged} / {total_gate}")
    if unjudged:
        print(f"  Unjudged (expected_category=null):   {unjudged}  [blind judging pending]")
    if judged > 0:
        print(f"  Strict correct (v1=correct, match):  {strict_correct}")
        print(f"  FPs (should-be-rejected, still emit): {fp_count}")
        print(f"  Misses (should-emit, not emitted):   {miss_count}")
        print(f"  Wrong category:                      {wrong_cat}")
        if strict_pct is not None:
            print(f"  Gate strict precision:               {strict_correct}/{total_emitted} = {strict_pct:.4f} ({100*strict_pct:.1f}%)")
    else:
        print("  [All records unjudged — paste gate JSON to Claude for blind judging]")

    if verbose:
        print("\n--- per-record verdicts ---")
        for entry, produced, verdict in rows:
            t = entry["trigger_id"]
            i = entry.get("same_turn_record_index", 0)
            phrase = entry.get("trigger_phrase", "")
            print(f"  {t}#{i:<3} {verdict:<55}  phrase={phrase!r}")

    return {
        "total_gate": total_gate,
        "unjudged": unjudged,
        "strict_correct": strict_correct,
        "total_emitted": total_emitted,
        "strict_pct": strict_pct,
    }


# ---------------------------------------------------------------------------
# Validation-set mode (Phase 5) — all records unjudged pre-Phase-5b
# ---------------------------------------------------------------------------

def evaluate_validation(validation_records, produced_by_id, total_emitted, verbose=False):
    """
    Validation mode. Before blind judging all expected_category fields are null
    → reports "all N unjudged — blind judging pending".
    After judging (Phase 5b produces v2): expected_category populated; reports
    validation precision using the same metric as gate (strict_correct / total_emitted).
    """
    unjudged = 0
    strict_correct = 0
    fp_count = 0
    miss_count = 0
    wrong_cat = 0
    not_emitted_ok = 0

    rows = []
    for entry in validation_records:
        tid = entry["trigger_id"]
        idx = entry.get("same_turn_record_index", 0)
        key = (tid, idx)
        produced = produced_by_id.get(key)
        expected_cat = entry.get("expected_category")
        v2_verdict = entry.get("verdict_at_v2")

        if expected_cat is None:
            unjudged += 1
            if produced:
                status = f"UNJUDGED (emitted as {produced['category']!r})"
            else:
                status = "UNJUDGED (not emitted)"
        elif expected_cat == "NONE":
            if produced is None:
                status = "OK_filtered"
                not_emitted_ok += 1
            else:
                status = f"FP: emitted as {produced['category']!r}"
                fp_count += 1
        else:
            if produced is None:
                status = "MISS: no record emitted"
                miss_count += 1
            else:
                produced_cat = produced["category"]
                if produced_cat == expected_cat:
                    if v2_verdict == "correct":
                        status = "OK_strict"
                        strict_correct += 1
                    else:
                        status = f"OK_defensible ({v2_verdict})"
                else:
                    status = f"WRONG_CAT: got {produced_cat!r} expected {expected_cat!r}"
                    wrong_cat += 1

        rows.append((entry, produced, status))

    total_val = len(validation_records)
    judged = total_val - unjudged
    strict_pct = strict_correct / total_emitted if (judged > 0 and total_emitted) else None

    print(f"\n=== loot_reward validation results ({total_val} records) ===")
    print(f"  Total emitted (all validation episodes):  {total_emitted}")
    print(f"  Validation records judged / total:        {judged} / {total_val}")
    if unjudged:
        print(f"  Unjudged (expected_category=null):        {unjudged}  "
              f"[blind judging pending — Phase 5b]")
    if judged > 0:
        print(f"  Strict correct (v2=correct, match):       {strict_correct}")
        print(f"  FPs (should-be-rejected, still emit):     {fp_count}")
        print(f"  Misses (should-emit, not emitted):        {miss_count}")
        print(f"  Wrong category:                           {wrong_cat}")
        if strict_pct is not None:
            print(f"  Validation strict precision:              "
                  f"{strict_correct}/{total_emitted} = {strict_pct:.4f} ({100 * strict_pct:.1f}%)")
    else:
        print("  [All records unjudged — paste validation JSON to Claude for blind judging]")

    if verbose:
        print("\n--- per-record verdicts ---")
        for entry, produced, verdict in rows:
            t = entry["trigger_id"]
            i = entry.get("same_turn_record_index", 0)
            phrase = entry.get("trigger_phrase", "")
            print(f"  {t}#{i:<3} {verdict:<55}  phrase={phrase!r}")

    return {
        "total_validation": total_val,
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
    parser.add_argument("--gate", action="store_true",
                        help="Run against the Phase 4 gate-set.")
    parser.add_argument("--handsample", action="store_true",
                        help="Run against the Phase 2/3 hand-sample (default).")
    parser.add_argument("--validation", action="store_true",
                        help="Run against the Phase 5 validation set.")
    parser.add_argument("--verbose", action="store_true",
                        help="Print per-record verdicts.")
    args = parser.parse_args()

    mode_count = sum([args.gate, args.handsample, args.validation])
    if mode_count > 1:
        print("FATAL: --gate, --handsample, and --validation are mutually exclusive.",
              file=sys.stderr)
        sys.exit(2)

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

    elif args.validation:
        if not VALIDATION_PATH.exists():
            print(f"FATAL: validation set not found: {VALIDATION_PATH}", file=sys.stderr)
            sys.exit(2)
        with open(VALIDATION_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        val_records = data.get("validation", [])
        if not val_records:
            print("FATAL: 'validation' key missing or empty.", file=sys.stderr)
            sys.exit(2)
        print(f"Loaded {len(val_records)} validation records from {VALIDATION_PATH.name}")
        episodes = episodes_for(val_records)
        print(f"Running extractor on {len(episodes)} episode(s): {episodes}")
        produced_by_id, total_emitted = run_extractor_on_episodes(episodes)
        evaluate_validation(val_records, produced_by_id, total_emitted, verbose=args.verbose)

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
