"""Calibration script for npc_extractor — Phase 12A.2.

Runs 15 narration cases through the live LLM via cloud_router. Reports
per-case actual-vs-expected and a pass-rate summary.

Not a regression test. Real network calls, real provider state, real
latency. Run on the server with cloud_router providers configured.

Spec §10 ship gate: ≥80% pass rate on the synthetic battery before wiring
into discord_dnd_bot.py at 12A.3.

The pass gate is NAME-SET match. Role / location_hint / description are
soft signals — reported but not gating. The primary failure modes we're
calibrating against are over-extraction (phantom NPCs) and under-extraction
(missed names), not field-quality.

Run: python3 calibrate_npc_extractor.py
"""

import sys
import time

from npc_extractor import parse_npcs


# Each case: (narration, expected_names, expected_role_by_name)
# expected_role_by_name is informational only — soft check, not gating.
# Edge cases covered (per Jordan's 12A.2 directive):
#   - generic roles without name      → []
#   - pronoun-only references         → []
#   - "Honorific Name" pattern        → keep
#   - "Honorific" alone               → drop
#   - multi-NPC scenes                → all extracted
#   - implied vs named                → only named
#   - faction / place / archetype     → drop
#   - apposition naming ("X, an old Y")
CASES = [
    # 1. Bare named NPC
    ("Garrick steps out of the shadows.",
     {"Garrick"}, {}),

    # 2. Named NPC with role
    ("Garrick the blacksmith pounds the anvil, sparks flying around him.",
     {"Garrick"}, {"Garrick": "blacksmith"}),

    # 3. Named NPC with role and location
    ("In Redhaven, Mira the innkeeper pours you a drink and asks where you've been.",
     {"Mira"}, {"Mira": "innkeeper"}),

    # 4. Multi-NPC scene
    ("Aldric and Bardus argue near the fire while Cara watches from across the tent.",
     {"Aldric", "Bardus", "Cara"}, {}),

    # 5. Generic role, no name — must drop
    ("A guard shouts at you to halt!",
     set(), {}),

    # 6. Pronoun only — no antecedent in this snippet, must drop
    ("He glances at you, then turns away without a word.",
     set(), {}),

    # 7. Generic role-as-actor — must drop
    ("The blacksmith barely looks up as you enter the smithy.",
     set(), {}),

    # 8. Honorific alone — must drop
    ("Sir nodded grimly and walked off.",
     set(), {}),

    # 9. Honorific + name. Identity is title-stripped deterministically by
    #    _strip_honorific (Session 12 doctrine — under strict literal match,
    #    "Sir Aldric" and "Aldric" must collapse to one row). Title may be
    #    captured in the role field.
    ("Sir Aldric draws his blade with a flourish.",
     {"Aldric"}, {}),

    # 10. Faction, not NPC — must drop
    ("The Crimson Hand has been busy in the south, raiding caravans and burning villages.",
     set(), {}),

    # 11. Place, not NPC — must drop
    ("Redhaven's docks creak under the wind, salt thick in the air.",
     set(), {}),

    # 12. Apposition naming ("X, an old Y")
    ("An old man named Tobin shuffles toward you, his beard tangled with sea salt.",
     {"Tobin"}, {}),

    # 13. Mixed: named NPC + ephemeral archetype — only the named survives
    ("Mira tends the bar while a hooded figure watches from the corner booth.",
     {"Mira"}, {}),

    # 14. Recurring named NPC, no other detail
    ("You spot Garrick across the square, hammer slung over his shoulder.",
     {"Garrick"}, {}),

    # 15. Speech attribution with name
    ('"Stop right there!" shouts Cassius, his voice cutting through the rain.',
     {"Cassius"}, {}),
]


def evaluate(actual, expected_names, expected_role_by_name):
    """Return (name_match, false_positives, false_negatives, role_warnings)."""
    actual_names = {n["name"] for n in actual}
    fp = sorted(actual_names - expected_names)
    fn = sorted(expected_names - actual_names)
    name_match = (not fp and not fn)

    role_warnings = []
    actual_by_name = {n["name"]: n for n in actual}
    for name, expected_role in expected_role_by_name.items():
        got = actual_by_name.get(name)
        if got is None:
            continue  # already reported as a missed name
        got_role = (got.get("role") or "").lower()
        if expected_role.lower() not in got_role and got_role not in expected_role.lower():
            role_warnings.append(f"{name}: expected role~{expected_role!r}, got={got.get('role')!r}")

    return name_match, fp, fn, role_warnings


def main():
    passes = 0
    fails = 0
    failures = []
    total_latency_ms = 0
    total_fp = 0
    total_fn = 0
    total_expected = sum(len(exp) for _, exp, _ in CASES)

    print(f"Running {len(CASES)} calibration cases...\n")

    for i, (narration, expected_names, expected_role) in enumerate(CASES, 1):
        t0 = time.monotonic()
        actual = parse_npcs(narration)
        latency_ms = int((time.monotonic() - t0) * 1000)
        total_latency_ms += latency_ms

        name_match, fp, fn, role_warnings = evaluate(
            actual, expected_names, expected_role
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
            f"{n['name']}({n['role']})" if n['role'] else n['name']
            for n in actual
        ]
        print(f"[{verdict}] case {i:>2} ({latency_ms:>4}ms)  {narration[:64]!r}")
        print(f"           expected names: {sorted(expected_names) or '∅'}")
        print(f"           actual:         {actual_summary}")
        if role_warnings:
            for w in role_warnings:
                print(f"           role-soft:      {w}")
        print()

    total = passes + fails
    pct = (passes / total * 100) if total else 0.0
    avg_ms = (total_latency_ms / total) if total else 0
    fp_rate = (total_fp / total * 100) if total else 0.0
    fn_rate = (total_fn / total_expected * 100) if total_expected else 0.0

    print("=" * 60)
    print(f"PASS: {passes}/{total}  ({pct:.0f}%)   avg latency: {avg_ms:.0f}ms")
    print(f"False positives: {total_fp} ({fp_rate:.0f}% of cases produced phantom NPCs)")
    print(f"False negatives: {total_fn}/{total_expected} ({fn_rate:.0f}% of named NPCs missed)")

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
        print("SHIP GATE: PASS  (≥80%) — clear to wire into 12A.3 background extraction")
        sys.exit(0)
    else:
        print("SHIP GATE: FAIL  (<80%) — calibrate prompt before integrating")
        sys.exit(1)


if __name__ == "__main__":
    main()
