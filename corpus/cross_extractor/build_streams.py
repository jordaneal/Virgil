#!/usr/bin/env python3
"""
Step 2.6 — Per-episode event streams.

Reads cross_extractor/all_records_unified.jsonl and writes one stream file per
episode to cross_extractor/streams/{episode_combined}.json.

Stream file format:
  {
    "episode_combined": "C2E020",
    "campaign": "C2",
    "episode_int": 20,
    "total_records": 38,
    "per_source_counts": {"EC": 1, "TM": 22, "LR": 8, "CC": 7},
    "events": [
      {"source": "TM", "turn_number": 152, "category": "...",
       "episode_position_pct": 7.5, "payload": {...}},
      ...
    ]
  }

Events sorted by (turn_number, source).
"""
import json
import os
from collections import defaultdict
from pathlib import Path

BASE = Path(__file__).resolve().parent
JSONL_PATH = BASE / "all_records_unified.jsonl"
STREAMS_DIR = BASE / "streams"


def sort_event_key(e):
    stri = e["payload"].get("same_turn_record_index", 0)
    if stri is None:
        stri = 0
    return (e["turn_number"], e["source"], stri)


def main():
    STREAMS_DIR.mkdir(exist_ok=True)

    # Load all records
    all_records = []
    with open(JSONL_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                all_records.append(json.loads(line))

    print(f"Loaded {len(all_records)} records from unified JSONL")

    # Group by episode
    by_episode = defaultdict(list)
    for r in all_records:
        by_episode[r["episode_combined"]].append(r)

    print(f"Unique episodes: {len(by_episode)}")

    total_events_written = 0
    episode_totals = {}

    for ep_combined, records in sorted(by_episode.items()):
        # Determine campaign and episode_int from first record
        campaign = records[0]["campaign"]
        episode_int = records[0]["episode_int"]

        # Per-source counts
        per_source = defaultdict(int)
        for r in records:
            per_source[r["source"]] += 1

        # Build event list sorted by (turn_number, source)
        events = []
        for r in records:
            events.append({
                "source": r["source"],
                "turn_number": r["turn_number"],
                "category": r["category"],
                "episode_position_pct": r["episode_position_pct"],
                "payload": r["payload"],
            })
        events.sort(key=sort_event_key)

        stream = {
            "episode_combined": ep_combined,
            "campaign": campaign,
            "episode_int": episode_int,
            "total_records": len(events),
            "per_source_counts": dict(per_source),
            "events": events,
        }

        out_path = STREAMS_DIR / f"{ep_combined}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(stream, f, indent=2, ensure_ascii=False)

        episode_totals[ep_combined] = len(events)
        total_events_written += len(events)

    print(f"Total stream files written: {len(by_episode)}")
    print(f"Total events across all streams: {total_events_written}")

    # Top 3 and bottom 3 by total_records
    sorted_eps = sorted(episode_totals.items(), key=lambda x: x[1], reverse=True)
    print(f"\nTop 3 episodes by total_records:")
    for ep, count in sorted_eps[:3]:
        print(f"  {ep}: {count}")
    print(f"\nBottom 3 episodes by total_records:")
    for ep, count in sorted_eps[-3:]:
        print(f"  {ep}: {count}")


if __name__ == "__main__":
    main()
