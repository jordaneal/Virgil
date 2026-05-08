#!/usr/bin/env python3
"""One-time generator: 5e-database 2014 SRD → srd_monsters.json.

Source: https://github.com/5e-bits/5e-database (MIT license)
SRD content: System Reference Document 5.1 © Wizards of the Coast LLC,
licensed under CC-BY 4.0 (https://creativecommons.org/licenses/by/4.0/).
Attribution: 5e-SRD by 5e-bits contributors and Wizards of the Coast.

Run once when the upstream source updates. Not executed at bot startup.
Output committed to the repo as srd_monsters.json.

Usage:
    python3 generate_srd_index.py [--output PATH]
"""

import argparse
import json
import os
import sys
import urllib.request


SOURCE_URL = (
    "https://raw.githubusercontent.com/5e-bits/5e-database/"
    "main/src/2014/en/5e-SRD-Monsters.json"
)
DEFAULT_OUTPUT = os.path.join(os.path.dirname(__file__), "srd_monsters.json")


def cr_float_to_str(cr: float) -> str:
    """Convert 5e-database float CR to canonical SRD string."""
    if cr == 0:      return "0"
    if cr == 0.125:  return "1/8"
    if cr == 0.25:   return "1/4"
    if cr == 0.5:    return "1/2"
    return str(int(cr)) if cr == int(cr) else str(cr)


def fetch_monsters(url: str) -> list:
    req = urllib.request.Request(url, headers={"User-Agent": "virgil-srd-index/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def build_index(monsters: list) -> dict:
    """Build lowercased-key index from raw monster list."""
    index = {}
    skipped = 0
    for m in monsters:
        name = m.get("name", "").strip()
        if not name:
            skipped += 1
            continue

        # AC: list of dicts with 'value'; take first entry's value
        ac_list = m.get("armor_class", [])
        if not ac_list or not isinstance(ac_list, list):
            skipped += 1
            continue
        ac = ac_list[0].get("value")
        if ac is None:
            skipped += 1
            continue

        hp = m.get("hit_points")
        cr_raw = m.get("challenge_rating")
        if hp is None or cr_raw is None:
            skipped += 1
            continue

        cr = cr_float_to_str(float(cr_raw))
        key = name.lower()
        index[key] = {
            "name": name,
            "cr":   cr,
            "hp":   int(hp),
            "ac":   int(ac),
        }

    return index


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=DEFAULT_OUTPUT,
                        help="Output path for srd_monsters.json")
    args = parser.parse_args()

    print(f"Fetching SRD monsters from 5e-database...")
    try:
        monsters = fetch_monsters(SOURCE_URL)
    except Exception as e:
        print(f"ERROR fetching source: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"  Raw monster count: {len(monsters)}")
    index = build_index(monsters)
    print(f"  Index entries built: {len(index)}")

    # Inject attribution header as a top-level metadata key
    output = {
        "_meta": {
            "source": "5e-bits/5e-database (MIT), SRD 5.1 content CC-BY 4.0 Wizards of the Coast",
            "url": SOURCE_URL,
            "generated_by": "generate_srd_index.py",
        }
    }
    output.update(index)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, sort_keys=True)

    print(f"  Written to: {args.output}")
    print(f"Done. {len(index)} monsters → srd_monsters.json")


if __name__ == "__main__":
    main()
