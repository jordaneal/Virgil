#!/usr/bin/env python3
"""
Regression test for time_mention against eval set v1.

Three exclusive modes per the Phase 2 prompt:

  --calibration  (default)  reads `calibration` from
                            findings/time_mention_eval_set_v1.json.
                            Used during calibration-cycle iteration.

  --holdout                 reads `gate_holdout` key from the same file.
                            Phase 3 (separate session) populates this.
                            For Phase 2, errors with a "phase 3 will populate"
                            message.

  --validation              reads `validation` key from the SEPARATE file
                            findings/time_mention_validation_set_v1.json.
                            Phase 5 (separate session) populates this.
                            For Phase 2, errors with a "phase 5 will populate"
                            message.

Modes cannot be combined. Runner errors if any two flags are passed.

Usage:
    python3 test_time_mention_eval_v1.py                # calibration only
    python3 test_time_mention_eval_v1.py --verbose      # detail per record
    python3 test_time_mention_eval_v1.py --holdout      # Phase 3+
    python3 test_time_mention_eval_v1.py --validation   # Phase 5+
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import time_mention as tm

CORPUS = Path(__file__).resolve().parent.parent
EVAL_PATH = CORPUS / "findings" / "time_mention_eval_set_v1.json"
VALIDATION_PATH = CORPUS / "findings" / "time_mention_validation_set_v1.json"


def trigger_id(record):
    return f"{record['campaign']}E{record['episode']:03d}_t{record['trigger_turn_number']}"


def load_eval(path, key):
    if not path.exists():
        return None, f"file does not exist: {path}"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if key not in data:
        return None, f"key {key!r} not present in {path.name}"
    arr = data[key]
    if not arr:
        return None, f"key {key!r} is empty in {path.name}"
    return arr, None


def episodes_for(eval_records):
    eps = set()
    for r in eval_records:
        eid = r.get("trigger_id", "")
        # trigger_id format: C1E003_t1234
        if "_t" in eid:
            ep = eid.split("_t")[0]
            eps.add(ep)
    return sorted(eps)


def run_extractor_on_episodes(episodes):
    extracted_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    records_by_id = {}
    for ep in episodes:
        # A turn can produce multiple records (multi-mention §11.6) — index
        # by (trigger_id, same_turn_record_index) since trigger_id alone is
        # not unique for multi-mention turns.
        recs = tm.process_episode(ep, extracted_at)
        for r in recs:
            key = (trigger_id(r), r["same_turn_record_index"])
            records_by_id[key] = r
    return records_by_id


def evaluate(eval_records, produced_by_id, verbose=False):
    correct = 0
    wrong = 0
    miss = 0
    fp = 0
    rows = []
    for entry in eval_records:
        tid = entry["trigger_id"]
        same_turn_idx = entry.get("same_turn_record_index", 0)
        key = (tid, same_turn_idx)
        produced = produced_by_id.get(key)
        expected_cat = entry["expected_category"]

        # NOT_TIME_MENTION: extractor should not have emitted anything (or
        # should have emitted with unknown_shape=true and expected category
        # would mark that). Treated as Stage 0 reject expected.
        if expected_cat == "NOT_TIME_MENTION":
            if produced is None:
                rows.append((tid, "OK_filtered", entry, None))
                correct += 1
            else:
                rows.append((tid, f"FP: emitted as {produced['category']}", entry, produced))
                fp += 1
            continue

        if produced is None:
            rows.append((tid, "MISS: no record emitted", entry, None))
            miss += 1
            continue

        # Normalize unknown_shape records to literal "UNKNOWN_SHAPE" so they
        # compare cleanly against eval entries. Per Lesson 2, unknown_shape
        # is its own measurable outcome, not a null sinkhole.
        if produced.get("unknown_shape"):
            produced_cat = "UNKNOWN_SHAPE"
        else:
            produced_cat = produced["category"]
        if produced_cat == expected_cat:
            rows.append((tid, "OK", entry, produced))
            correct += 1
        else:
            rows.append(
                (tid, f"WRONG: got {produced_cat!r} expected {expected_cat!r}",
                 entry, produced)
            )
            wrong += 1

    total = len(eval_records)
    print(f"\n=== eval results ({total} records) ===")
    print(f"  correct: {correct} / {total} ({100*correct/total:.1f}%)")
    print(f"  wrong:   {wrong}")
    print(f"  miss:    {miss}")
    print(f"  fp:      {fp}")

    if verbose:
        print("\n--- per-record ---")
        for tid, verdict, entry, produced in rows:
            print(f"  {tid:30s}  {verdict}")
            if produced and verdict.startswith(("WRONG", "FP")):
                print(f"     phrase={produced['trigger_phrase']!r}")

    return correct, wrong, miss, fp


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--calibration", action="store_true",
                        help="Run against the calibration split (default).")
    parser.add_argument("--holdout", action="store_true",
                        help="Run against the gate_holdout split (Phase 3+).")
    parser.add_argument("--validation", action="store_true",
                        help="Run against the validation split (Phase 5+).")
    parser.add_argument("--verbose", action="store_true",
                        help="Print per-record verdicts.")
    args = parser.parse_args()

    flags = [args.calibration, args.holdout, args.validation]
    if sum(1 for f in flags if f) > 1:
        print("FATAL: --calibration / --holdout / --validation are mutually exclusive.",
              file=sys.stderr)
        sys.exit(2)

    if args.holdout:
        arr, err = load_eval(EVAL_PATH, "gate_holdout")
        if err:
            print(f"--holdout: {err}", file=sys.stderr)
            print("Phase 3 will populate the gate_holdout split. "
                  "Not available in Phase 2.", file=sys.stderr)
            sys.exit(2)
        eval_records = arr

    elif args.validation:
        arr, err = load_eval(VALIDATION_PATH, "validation")
        if err:
            print(f"--validation: {err}", file=sys.stderr)
            print("Phase 5 will populate the validation set. "
                  "Not available in Phase 2 or Phase 3.", file=sys.stderr)
            sys.exit(2)
        eval_records = arr

    else:
        # Default: --calibration
        arr, err = load_eval(EVAL_PATH, "calibration")
        if err:
            print(f"--calibration: {err}", file=sys.stderr)
            sys.exit(2)
        eval_records = arr

    episodes = episodes_for(eval_records)
    print(f"Loaded {len(eval_records)} eval records across {len(episodes)} episode(s).")

    produced = run_extractor_on_episodes(episodes)
    evaluate(eval_records, produced, verbose=args.verbose)


if __name__ == "__main__":
    main()
