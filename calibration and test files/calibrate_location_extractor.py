"""Calibration script for location_extractor — Phase 12B.2.

Runs 15 narration cases through the live LLM via cloud_router. Reports
per-case actual-vs-expected and a pass-rate summary.

Spec §10 ship gate: ≥80% pass rate on the synthetic battery before wiring
into discord_dnd_bot.py at 12B.3.

Locations are HARDER than NPCs — three failure modes the parser will hit:
  (a) emitting "the X" where X is a pure type ("the forest", "the road")
  (b) emitting an entire region or political entity ("the eastern lands")
  (c) emitting a faction-as-place ("Crimson Hand territory")

The pass gate is NAME-SET match. type / parent_hint / description are
soft signals — reported but not gating.

Run: python3 calibrate_location_extractor.py
"""

import sys
import time

from location_extractor import parse_locations


# Each case: (narration, expected_names, expected_type_by_name)
CASES = [
    # 1. Bare named town with descriptor
    ("You arrive in Redhaven, a salt-stained port town buzzing with sailors.",
     {"Redhaven"}, {"Redhaven": "town"}),

    # 2. Named tavern with parent location and atmosphere
    ("In Redhaven, the Rusty Anchor sits at the end of the docks — smoky, low-ceilinged, and full of laughter.",
     {"Rusty Anchor"}, {"Rusty Anchor": "tavern"}),
     # NOTE: parser may also emit Redhaven here. We're testing whether
     # Rusty Anchor specifically is captured. Permissive on Redhaven.

    # 3. Pure type-words — must drop
    ("You take the road north toward the mountains, the forest dark on either side.",
     set(), {}),

    # 4. Distinctive descriptor (article + adjective + type-word)
    ("The Whispering Woods stretch dark before you, leaves trembling without wind.",
     {"Whispering Woods"}, {}),

    # 5. Generic interior — must drop
    ("A tavern keeper greets you. The room is warm and the fire crackles.",
     set(), {}),

    # 6. Multi-word proper noun guildhall
    ("You enter the Stoneforge Guild Hall, lantern-lit and smelling of iron from the smithy beyond.",
     {"Stoneforge Guild Hall"}, {}),

    # 7. Faction, not location — must drop
    ("The Crimson Hand has been busy in the south, raiding caravans for weeks.",
     set(), {}),

    # 8. Distinctive descriptor for ruin
    ("The Old Mill creaks in the wind, abandoned for years and overrun by ivy.",
     {"Old Mill"}, {}),

    # 9. Multi-location: town and its tavern in one paragraph
    ("Redhaven's docks groan under the wind. At the far end, the Iron Tankard's lantern still glows.",
     {"Redhaven", "Iron Tankard"}, {}),

    # 10. Cardinal-direction region — must drop (these are abstract)
    ("Travelers say the northern lands grow colder each year.",
     set(), {}),

    # 11. Castle with proper name
    ("Aldric's Keep looms above the valley, its battlements scarred by old siege weapons.",
     {"Aldric's Keep"}, {}),

    # 12. Mixed: named region (keep) + abstract direction (drop)
    ("You leave the Whispering Woods behind and head east into the open plains.",
     {"Whispering Woods"}, {}),

    # 13. Single named dungeon
    ("The Crystal Caves yawn open, their walls glittering with embedded shards.",
     {"Crystal Caves"}, {}),

    # 14. Embedded prefix that looks like article — must NOT strip
    ("Theramore's silver gates rise above the harbor mist.",
     {"Theramore"}, {}),

    # 15. Generic interior + named building outside
    ("You step out of the cellar into the open square. The Stoneforge Guild Hall stands across from you.",
     {"Stoneforge Guild Hall"}, {}),
]


def evaluate(actual, expected_names, expected_type_by_name):
    """Return (name_match, false_positives, false_negatives, type_warnings).

    name_match is True iff expected_names ⊆ actual_names AND no extras
    appear that weren't expected. We allow over-extraction in case 2
    (Redhaven alongside Rusty Anchor) by computing FP/FN strictly but
    flagging name_match generously."""
    actual_names = {loc["name"] for loc in actual}
    fp = sorted(actual_names - expected_names)
    fn = sorted(expected_names - actual_names)
    name_match = (not fp and not fn)

    type_warnings = []
    actual_by_name = {loc["name"]: loc for loc in actual}
    for name, expected_type in expected_type_by_name.items():
        got = actual_by_name.get(name)
        if got is None:
            continue
        got_type = (got.get("type") or "").lower()
        if (expected_type.lower() not in got_type
                and got_type not in expected_type.lower()):
            type_warnings.append(
                f"{name}: expected type~{expected_type!r}, got={got.get('type')!r}"
            )

    return name_match, fp, fn, type_warnings


def main():
    passes = 0
    fails = 0
    failures = []
    total_latency_ms = 0
    total_fp = 0
    total_fn = 0
    total_expected = sum(len(exp) for _, exp, _ in CASES)

    print(f"Running {len(CASES)} calibration cases...\n")

    for i, (narration, expected_names, expected_type) in enumerate(CASES, 1):
        t0 = time.monotonic()
        actual = parse_locations(narration)
        latency_ms = int((time.monotonic() - t0) * 1000)
        total_latency_ms += latency_ms

        name_match, fp, fn, type_warnings = evaluate(
            actual, expected_names, expected_type
        )
        total_fp += len(fp)
        total_fn += len(fn)

        if name_match:
            passes += 1
            verdict = "PASS"
        else:
            fails += 1
            verdict = "FAIL"
            failures.append((i, narration, expected_names, actual, fp, fn))

        actual_summary = [
            f"{loc['name']}({loc['type']})" if loc['type'] else loc['name']
            for loc in actual
        ]
        print(f"[{verdict}] case {i:>2} ({latency_ms:>4}ms)  {narration[:64]!r}")
        print(f"           expected names: {sorted(expected_names) or '∅'}")
        print(f"           actual:         {actual_summary}")
        if type_warnings:
            for w in type_warnings:
                print(f"           type-soft:      {w}")
        print()

    total = passes + fails
    pct = (passes / total * 100) if total else 0.0
    avg_ms = (total_latency_ms / total) if total else 0
    fp_rate = (total_fp / total * 100) if total else 0.0
    fn_rate = (total_fn / total_expected * 100) if total_expected else 0.0

    print("=" * 60)
    print(f"PASS: {passes}/{total}  ({pct:.0f}%)   avg latency: {avg_ms:.0f}ms")
    print(f"False positives: {total_fp} ({fp_rate:.0f}% of cases produced phantom locations)")
    print(f"False negatives: {total_fn}/{total_expected} ({fn_rate:.0f}% of named locations missed)")

    if fails:
        print("\nFailing cases (need prompt tightening or scope review):")
        for i, narration, expected, actual, fp, fn in failures:
            print(f"  case {i}: {narration!r}")
            if fp:
                print(f"    over-extracted: {fp}")
            if fn:
                print(f"    missed:         {fn}")

    print()
    if pct >= 80:
        print("SHIP GATE: PASS  (≥80%) — clear to wire into 12B.3")
        sys.exit(0)
    else:
        print("SHIP GATE: FAIL  (<80%) — calibrate prompt before integrating")
        sys.exit(1)


if __name__ == "__main__":
    main()
