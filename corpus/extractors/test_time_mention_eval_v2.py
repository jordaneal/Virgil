#!/usr/bin/env python3
"""
Regression test for time_mention v1.2 against eval set v2.

Eval set v2 carries Jordan's hand-judged verdicts on the v1 hand-sample.
Special expected_category sentinels:

  - NOT_TIME_MENTION : record SHOULD NOT be emitted. Stage 0 reject expected.
  - DUPLICATE        : record IS a dup of another in the same turn. Patch 1
                       turn-level dedup should keep the first occurrence
                       only; subsequent same-turn dups should not be emitted.
  - is_combat_state_required : record SHOULD be emitted with
                       `is_combat_state: true`. (v1.2 may still miss these
                       due to OQ5 25-turn lookback lock — known limitation.)

Three exclusive modes:

  --calibration  (default)  reads `calibration` from
                            findings/time_mention_eval_set_v2.json.

  --holdout                 reads `gate_holdout` from same file. Phase 4
                            populates this; v1.2 errors with a
                            "Phase 4 will populate" message.

  --validation              reads `validation` key from the SEPARATE file
                            findings/time_mention_validation_set_v1.json.
                            Phase 5 populates this; v1.2 errors with a
                            "Phase 5 will populate" message.

Modes cannot be combined.

Usage:
    python3 test_time_mention_eval_v2.py                # calibration only
    python3 test_time_mention_eval_v2.py --verbose      # detail per record
    python3 test_time_mention_eval_v2.py --holdout      # Phase 4+
    python3 test_time_mention_eval_v2.py --validation   # Phase 5+
"""

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import time_mention as tm

CORPUS = Path(__file__).resolve().parent.parent
EVAL_PATH = CORPUS / "findings" / "time_mention_eval_set_v2.json"
HOLDOUT_PATH = CORPUS / "findings" / "time_mention_eval_set_v3_holdout.json"
VALIDATION_PATH = CORPUS / "findings" / "time_mention_validation_set_v1.json"


def trigger_id(record):
    return f"{record['campaign']}E{record['episode']:03d}_t{record['trigger_turn_number']}"


def episodes_for(eval_records):
    eps = set()
    for r in eval_records:
        eid = r.get("trigger_id", "")
        if "_t" in eid:
            ep = eid.split("_t")[0]
            eps.add(ep)
    return sorted(eps)


def run_extractor_on_episodes(episodes):
    extracted_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    # Index produced records by (trigger_id, same_turn_record_index).
    produced_by_id = {}
    # Also index produced records by trigger_id (no idx) for "any record on this
    # turn" lookups (used for is_combat_state_required check).
    by_tid_only = defaultdict(list)
    for ep in episodes:
        recs = tm.process_episode(ep, extracted_at)
        for r in recs:
            tid = trigger_id(r)
            key = (tid, r["same_turn_record_index"])
            produced_by_id[key] = r
            by_tid_only[tid].append(r)
    return produced_by_id, by_tid_only


def normalize_produced_category(produced):
    """v1.2 produces `category=None, unknown_shape=True` for unclassifiable
    records. Eval set encodes that as expected_category=UNKNOWN_SHAPE."""
    if produced.get("unknown_shape"):
        return "UNKNOWN_SHAPE"
    return produced["category"]


def evaluate(eval_records, produced_by_id, by_tid_only, verbose=False):
    correct = 0
    wrong = 0
    miss = 0
    fp = 0
    duplicate_emitted = 0
    combat_state_misses = 0

    rows = []
    for entry in eval_records:
        tid = entry["trigger_id"]
        same_turn_idx = entry.get("same_turn_record_index", 0)
        key = (tid, same_turn_idx)
        produced = produced_by_id.get(key)
        expected_cat = entry["expected_category"]

        if expected_cat == "NOT_TIME_MENTION":
            # Should not have emitted this record at all (Stage 0 reject).
            # BUT — patch 1 dedup may keep the first idx. So check whether
            # ANY record on this turn was emitted; if not, it's correct.
            # If a record IS emitted at this exact (tid, idx), it's an FP.
            if produced is None:
                rows.append((entry, None, "OK_filtered"))
                correct += 1
            else:
                rows.append((entry, produced, f"FP: emitted as {normalize_produced_category(produced)}"))
                fp += 1
            continue

        if expected_cat == "DUPLICATE":
            # Patch 1 should suppress this. If extractor still emits at this
            # idx, it's a dup-emit failure.
            if produced is None:
                rows.append((entry, None, "OK_dedup_suppressed"))
                correct += 1
            else:
                rows.append((entry, produced, f"DUP_FAIL: still emitted as {normalize_produced_category(produced)}"))
                duplicate_emitted += 1
            continue

        if expected_cat == "is_combat_state_required":
            # Record SHOULD be emitted with is_combat_state=true.
            # Even if same_turn_record_index has shifted (post-dedup), accept
            # any record on this turn that carries is_combat_state=True.
            any_record_on_turn = by_tid_only.get(tid, [])
            with_combat = [r for r in any_record_on_turn if r.get("is_combat_state")]
            if with_combat:
                rows.append((entry, with_combat[0], "OK_combat_state"))
                correct += 1
            elif any_record_on_turn:
                rows.append((entry, any_record_on_turn[0],
                             "COMBAT_STATE_MISS: emitted without combat flag"))
                combat_state_misses += 1
            else:
                rows.append((entry, None, "MISS: no record emitted on turn"))
                miss += 1
            continue

        # Standard category check.
        if produced is None:
            rows.append((entry, None, "MISS: no record emitted"))
            miss += 1
            continue

        produced_cat = normalize_produced_category(produced)
        if produced_cat == expected_cat:
            rows.append((entry, produced, "OK"))
            correct += 1
        else:
            rows.append((entry, produced, f"WRONG: got {produced_cat!r} expected {expected_cat!r}"))
            wrong += 1

    total = len(eval_records)
    not_tm_count = sum(1 for e in eval_records if e["expected_category"] == "NOT_TIME_MENTION")
    dup_count = sum(1 for e in eval_records if e["expected_category"] == "DUPLICATE")

    print(f"\n=== eval results ({total} records) ===")
    print(f"  correct:               {correct} / {total} ({100*correct/total:.1f}%)")
    print(f"  wrong:                 {wrong}")
    print(f"  miss:                  {miss}")
    print(f"  fp (NOT_TIME_MENTION): {fp} / {not_tm_count} expected ({100*fp/total:.1f}% of total)")
    print(f"  dup-emit failures:     {duplicate_emitted} / {dup_count} expected ({100*duplicate_emitted/total:.1f}% of total)")
    print(f"  combat-state misses:   {combat_state_misses}")

    print()
    print("--- ship-gate check ---")
    strict_precision_pct = 100 * correct / total
    fp_rate_pct = 100 * fp / total
    dup_rate_pct = 100 * duplicate_emitted / total
    print(f"  Strict precision:       {strict_precision_pct:.1f}% (gate ≥ 80%)")
    print(f"  FP rate:                {fp_rate_pct:.1f}%  (gate ≤ 5%)")
    print(f"  Duplicate rate:         {dup_rate_pct:.1f}% (gate ≤ 3%)")

    if verbose:
        print("\n--- per-record verdicts ---")
        for entry, produced, verdict in rows:
            tid = entry["trigger_id"]
            idx = entry.get("same_turn_record_index", 0)
            print(f"  {tid}#{idx:<3} {verdict}")

    return {
        "total": total,
        "correct": correct,
        "wrong": wrong,
        "miss": miss,
        "fp": fp,
        "duplicate_emitted": duplicate_emitted,
        "combat_state_misses": combat_state_misses,
        "strict_precision_pct": strict_precision_pct,
        "fp_rate_pct": fp_rate_pct,
        "dup_rate_pct": dup_rate_pct,
        "rows": rows,
    }


def load_eval(path, key):
    if not path.exists():
        return None, f"file does not exist: {path}"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if key not in data:
        return None, f"key {key!r} not present in {path.name}"
    if not data[key]:
        return None, f"key {key!r} is empty in {path.name}"
    return data[key], None


def _hydrate_holdout_records(holdout_records):
    """For each judged held-out record, fetch raw_text from CRD3 source via
    episode + turn_number lookup. The held-out file's `raw_text` is
    deliberately stripped during calibration — this hydration only fires
    when --holdout is passed (mechanical enforcement). The hydrated record
    list is shape-compatible with calibration eval entries.
    """
    # Group by episode to load each episode's turn list once.
    by_episode = defaultdict(list)
    for r in holdout_records:
        ep = r["trigger_id"].split("_t")[0]
        by_episode[ep].append(r)

    hydrated = []
    for ep, recs in by_episode.items():
        turns = tm.load_episode_turns(ep)
        turns_by_num = {t["number"]: t for t in turns}
        for r in recs:
            turn_num = int(r["trigger_id"].split("_t")[1])
            t = turns_by_num.get(turn_num)
            if t is None:
                print(f"WARN: turn {turn_num} not found in {ep}", file=sys.stderr)
                continue
            r2 = dict(r)
            r2["raw_text"] = t["text"]
            hydrated.append(r2)
    return hydrated


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--calibration", action="store_true",
                        help="Run against the calibration split (default).")
    parser.add_argument("--holdout", action="store_true",
                        help="Run against the gate_holdout split (Phase 4+).")
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
        # Phase 4 (v3 holdout) — separate file, raw_text stripped, blind judging.
        arr, err = load_eval(HOLDOUT_PATH, "gate_holdout")
        if err:
            print(f"--holdout: {err}", file=sys.stderr)
            sys.exit(2)
        # Filter to judged records only — skip records with expected_category=null.
        judged = [r for r in arr if r.get("expected_category") is not None]
        unjudged = len(arr) - len(judged)
        if unjudged:
            print(f"--holdout: {unjudged}/{len(arr)} records unjudged "
                  f"(expected_category=null). Skipping unjudged for ship-gate "
                  f"computation. Phase 5 judges them.", file=sys.stderr)
        if not judged:
            print(f"--holdout: zero judged records. Phase 5 will populate "
                  f"expected_category for the {len(arr)} held-out records, "
                  f"after which --holdout produces the published-claim "
                  f"measurement.", file=sys.stderr)
            sys.exit(2)
        # Hydrate raw_text from CRD3 source for the regression run.
        eval_records = _hydrate_holdout_records(judged)
    elif args.validation:
        arr, err = load_eval(VALIDATION_PATH, "validation")
        if err:
            print(f"--validation: {err}", file=sys.stderr)
            print("Phase 5 will populate the validation set. "
                  "Not available in Phase 3 or Phase 4.", file=sys.stderr)
            sys.exit(2)
        eval_records = arr
    else:
        arr, err = load_eval(EVAL_PATH, "calibration")
        if err:
            print(f"--calibration: {err}", file=sys.stderr)
            sys.exit(2)
        eval_records = arr

    episodes = episodes_for(eval_records)
    print(f"Loaded {len(eval_records)} eval records across {len(episodes)} episode(s).")

    produced_by_id, by_tid_only = run_extractor_on_episodes(episodes)
    evaluate(eval_records, produced_by_id, by_tid_only, verbose=args.verbose)


if __name__ == "__main__":
    main()
