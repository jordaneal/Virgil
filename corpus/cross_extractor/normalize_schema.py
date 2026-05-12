#!/usr/bin/env python3
"""
Step 2.4 — Schema normalizer.

Reads all four extractor outputs and produces a single unified JSONL at:
  corpus_builder/cross_extractor/all_records_unified.jsonl

Unified record shape:
  {
    "source": "EC"|"TM"|"LR"|"CC",
    "campaign": "C1"|"C2",
    "episode_int": <int>,
    "episode_combined": "C1E001",
    "turn_number": <int>,
    "episode_position_pct": <float>,
    "category": <str>,
    "payload": {...all other source-specific fields...}
  }

Output sorted by (episode_combined, turn_number, source, same_turn_record_index).
"""
import json
import os
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent  # corpus_builder/
OUTPUT_PATH = Path(__file__).resolve().parent / "all_records_unified.jsonl"

EC_DIR = BASE / "output" / "encounter_cadence"
TM_DIR = BASE / "output" / "time_mention"
LR_MAIN_DIR = BASE / "output" / "loot_reward" / "full_v36"
LR_EXT_DIR = BASE / "output" / "loot_reward" / "full_v36_extended"
CC_PATH = BASE / "output" / "compression_cadence_corpus_v1p4_extended.json"

EPISODE_RE = re.compile(r'^(C\d+)E(\d+)$')


def parse_episode_str(ep_str):
    """Parse 'C1E001' -> (campaign='C1', episode_int=1)"""
    m = EPISODE_RE.match(ep_str)
    if not m:
        raise ValueError(f"Cannot parse episode string: {ep_str!r}")
    return m.group(1), int(m.group(2))


def make_episode_combined(campaign, episode_int):
    return f"{campaign}E{episode_int:03d}"


# ---------------------------------------------------------------------------
# EC
# ---------------------------------------------------------------------------
def load_ec():
    records = []
    SHARED_KEYS = {"campaign", "episode", "trigger_turn_number", "trigger_category",
                   "episode_position_pct"}
    for fn in sorted(os.listdir(EC_DIR)):
        if not fn.endswith(".json"):
            continue
        with open(EC_DIR / fn, encoding="utf-8") as f:
            recs = json.load(f)
        for r in recs:
            campaign = r["campaign"]
            episode_int = r["episode"]
            episode_combined = make_episode_combined(campaign, episode_int)
            turn_number = r["trigger_turn_number"]
            category = r["trigger_category"]
            episode_position_pct = r.get("episode_position_pct")
            payload = {k: v for k, v in r.items() if k not in SHARED_KEYS}
            records.append({
                "source": "EC",
                "campaign": campaign,
                "episode_int": episode_int,
                "episode_combined": episode_combined,
                "turn_number": turn_number,
                "episode_position_pct": episode_position_pct,
                "category": category,
                "payload": payload,
            })
    return records


# ---------------------------------------------------------------------------
# TM
# ---------------------------------------------------------------------------
def load_tm():
    records = []
    SHARED_KEYS = {"campaign", "episode", "trigger_turn_number", "category",
                   "episode_position_pct"}
    for fn in sorted(os.listdir(TM_DIR)):
        if not fn.endswith(".json"):
            continue
        with open(TM_DIR / fn, encoding="utf-8") as f:
            recs = json.load(f)
        for r in recs:
            campaign = r["campaign"]
            episode_int = r["episode"]
            episode_combined = make_episode_combined(campaign, episode_int)
            turn_number = r["trigger_turn_number"]
            category = r["category"]
            episode_position_pct = r.get("episode_position_pct")
            payload = {k: v for k, v in r.items() if k not in SHARED_KEYS}
            records.append({
                "source": "TM",
                "campaign": campaign,
                "episode_int": episode_int,
                "episode_combined": episode_combined,
                "turn_number": turn_number,
                "episode_position_pct": episode_position_pct,
                "category": category,
                "payload": payload,
            })
    return records


# ---------------------------------------------------------------------------
# LR (both full_v36 and full_v36_extended)
# ---------------------------------------------------------------------------
def load_lr():
    records = []
    SHARED_KEYS = {"campaign", "episode", "trigger_turn_number", "category",
                   "episode_position_pct"}
    for lr_dir in [LR_MAIN_DIR, LR_EXT_DIR]:
        for fn in sorted(os.listdir(lr_dir)):
            if not fn.endswith(".json"):
                continue
            with open(lr_dir / fn, encoding="utf-8") as f:
                recs = json.load(f)
            for r in recs:
                campaign = r["campaign"]
                episode_int = r["episode"]
                episode_combined = make_episode_combined(campaign, episode_int)
                turn_number = r["trigger_turn_number"]
                category = r["category"]
                episode_position_pct = r.get("episode_position_pct")
                payload = {k: v for k, v in r.items() if k not in SHARED_KEYS}
                records.append({
                    "source": "LR",
                    "campaign": campaign,
                    "episode_int": episode_int,
                    "episode_combined": episode_combined,
                    "turn_number": turn_number,
                    "episode_position_pct": episode_position_pct,
                    "category": category,
                    "payload": payload,
                })
    return records


# ---------------------------------------------------------------------------
# CC
# ---------------------------------------------------------------------------
TRIGGER_ID_RE = re.compile(r'^(.+)_t(\d+)$')


def load_cc():
    records = []
    SHARED_KEYS = {"trigger_id", "episode", "extracted_category", "episode_position_pct"}
    with open(CC_PATH, encoding="utf-8") as f:
        raw = json.load(f)
    for r in raw:
        ep_str = r["episode"]          # "C1E001"
        campaign, episode_int = parse_episode_str(ep_str)
        episode_combined = ep_str      # already canonical
        # Parse turn_number from trigger_id
        tid = r["trigger_id"]
        m = TRIGGER_ID_RE.match(tid)
        if not m:
            raise ValueError(f"Cannot parse trigger_id: {tid!r}")
        turn_number = int(m.group(2))
        category = r["extracted_category"]
        episode_position_pct = r.get("episode_position_pct")
        payload = {k: v for k, v in r.items() if k not in SHARED_KEYS}
        records.append({
            "source": "CC",
            "campaign": campaign,
            "episode_int": episode_int,
            "episode_combined": episode_combined,
            "turn_number": turn_number,
            "episode_position_pct": episode_position_pct,
            "category": category,
            "payload": payload,
        })
    return records


# ---------------------------------------------------------------------------
# Sort key
# ---------------------------------------------------------------------------
def sort_key(r):
    # same_turn_record_index from payload if present (CC and others)
    stri = r["payload"].get("same_turn_record_index", 0)
    if stri is None:
        stri = 0
    return (r["episode_combined"], r["turn_number"], r["source"], stri)


def main():
    print("Loading EC ...")
    ec = load_ec()
    print(f"  EC: {len(ec)} records")

    print("Loading TM ...")
    tm = load_tm()
    print(f"  TM: {len(tm)} records")

    print("Loading LR ...")
    lr = load_lr()
    print(f"  LR: {len(lr)} records")

    print("Loading CC ...")
    cc = load_cc()
    print(f"  CC: {len(cc)} records")

    all_records = ec + tm + lr + cc
    print(f"\nTotal before sort: {len(all_records)}")
    all_records.sort(key=sort_key)
    print(f"Total after sort:  {len(all_records)}")

    # Verify sum
    ec_count = sum(1 for r in all_records if r["source"] == "EC")
    tm_count = sum(1 for r in all_records if r["source"] == "TM")
    lr_count = sum(1 for r in all_records if r["source"] == "LR")
    cc_count = sum(1 for r in all_records if r["source"] == "CC")
    assert ec_count + tm_count + lr_count + cc_count == len(all_records)
    print(f"\nPer-source counts: EC={ec_count}  TM={tm_count}  LR={lr_count}  CC={cc_count}")
    print(f"Sum check: {ec_count}+{tm_count}+{lr_count}+{cc_count} = {ec_count+tm_count+lr_count+cc_count}  ✓")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        for r in all_records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\nOutput: {OUTPUT_PATH}")

    # Episode coverage per source
    ec_eps = set(r["episode_combined"] for r in all_records if r["source"] == "EC")
    tm_eps = set(r["episode_combined"] for r in all_records if r["source"] == "TM")
    lr_eps = set(r["episode_combined"] for r in all_records if r["source"] == "LR")
    cc_eps = set(r["episode_combined"] for r in all_records if r["source"] == "CC")

    print(f"\nEpisode coverage: EC={len(ec_eps)}  TM={len(tm_eps)}  LR={len(lr_eps)}  CC={len(cc_eps)}")
    all_eps_union = ec_eps | tm_eps | lr_eps | cc_eps
    print(f"Union of all episodes: {len(all_eps_union)}")

    # Step 2.5 — Intersection analysis
    print("\n=== STEP 2.5: EPISODE-COVERAGE INTERSECTION ===\n")

    in_all_4 = ec_eps & tm_eps & lr_eps & cc_eps
    print(f"Episodes in ALL 4 sources: {len(in_all_4)}")

    # Per-pair intersections
    pairs = [
        ("EC", "TM", ec_eps, tm_eps),
        ("EC", "LR", ec_eps, lr_eps),
        ("EC", "CC", ec_eps, cc_eps),
        ("TM", "LR", tm_eps, lr_eps),
        ("TM", "CC", tm_eps, cc_eps),
        ("LR", "CC", lr_eps, cc_eps),
    ]
    print("\nPer-pair intersection counts:")
    for a_name, b_name, a_set, b_set in pairs:
        inter = a_set & b_set
        print(f"  {a_name} x {b_name}: {len(inter)} episodes")

    # Episodes in fewer than 4 sources
    source_sets = {"EC": ec_eps, "TM": tm_eps, "LR": lr_eps, "CC": cc_eps}
    partial = []
    for ep in sorted(all_eps_union):
        present = [s for s, eps in source_sets.items() if ep in eps]
        missing = [s for s, eps in source_sets.items() if ep not in eps]
        if len(present) < 4:
            partial.append((ep, present, missing))

    print(f"\nEpisodes in fewer than 4 sources: {len(partial)}")
    if partial:
        print(f"  {'Episode':<12}  {'Present':<20}  {'Missing'}")
        for ep, present, missing in partial:
            print(f"  {ep:<12}  {','.join(present):<20}  {','.join(missing)}")

    return all_records


if __name__ == "__main__":
    main()
