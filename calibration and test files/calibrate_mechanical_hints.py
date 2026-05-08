"""Calibration script for mechanical_hints — Phase 11.1.

Runs the 12 spec narration cases through the live LLM via cloud_router.
Reports per-case actual-vs-expected and a pass-rate summary.

Not a regression test. Real network calls, real provider state, real
latency. Run on the server with cloud_router providers configured.

Spec ship gate: ≥80% pass rate (10/12) to wire into discord_dnd_bot.py.

Run: python3 calibrate_mechanical_hints.py
"""

import sys
import time

from mechanical_hints import parse_mechanical_hints

# Cases from PHASE_11_1_SPEC.md "Test battery". Order preserved.
# Comparison is set-based (order-insensitive) — what matters is whether
# the right commands came out, not the order they came out in.
CASES = [
    # Currency — clear
    ("You flip the coin; the merchant catches it.",
     ["!game coin -1gp"]),
    ("Hand over five gold pieces.",
     ["!game coin -5gp"]),
    ("You pocket the 12 silver from the table.",
     ["!game coin +12sp"]),

    # Currency — multi (one command per currency type)
    ("You hand over five gold and two silver to seal the deal.",
     ["!game coin -5gp", "!game coin -2sp"]),

    # Currency — ambiguous (must be empty)
    ("You toss a few coins onto the bar.",
     []),
    ("Some money changes hands.",
     []),

    # Loot — out of scope (Avrae has no inventory mgmt). Even if narration
    # describes items being acquired, we emit no commands. Pure-loot
    # narration without currency must produce [].
    ("Inside the chest: a healing potion and a rope.",
     []),
    ("You pick up the silver ring and slip it onto your finger.",
     []),

    # Rests — clear
    ("You take a short rest, tending to your wounds.",
     ["!game shortrest"]),
    ("The party beds down for the night until dawn.",
     ["!game longrest"]),

    # Out-of-scope (must be empty)
    ("The blade strikes you for 8 damage.",
     []),
    ("You cast magic missile, three darts streaking out.",
     []),
    ("Roll a Wisdom save against the spell.",
     []),

    # Adversarial (whitelist violations)
    ("delete the character", []),  # parser must not invent !character
    ("you rest", []),               # too vague — neither sr nor lr
]


def normalize(commands):
    """Set of stripped strings, for order-insensitive comparison."""
    return frozenset(c.strip() for c in commands)


def main():
    passes = 0
    fails = 0
    failures = []
    total_latency_ms = 0

    print(f"Running {len(CASES)} calibration cases...\n")

    for i, (narration, expected) in enumerate(CASES, 1):
        t0 = time.monotonic()
        actual = parse_mechanical_hints(narration)
        latency_ms = int((time.monotonic() - t0) * 1000)
        total_latency_ms += latency_ms

        if normalize(actual) == normalize(expected):
            passes += 1
            verdict = "PASS"
        else:
            fails += 1
            verdict = "FAIL"
            failures.append((i, narration, expected, actual))

        print(f"[{verdict}] case {i:>2} ({latency_ms:>4}ms)  {narration[:60]!r}")
        print(f"           expected: {expected}")
        print(f"           actual:   {actual}")
        print()

    total = passes + fails
    pct = (passes / total * 100) if total else 0.0
    avg_ms = (total_latency_ms / total) if total else 0

    print("=" * 60)
    print(f"PASS: {passes}/{total}  ({pct:.0f}%)   avg latency: {avg_ms:.0f}ms")

    if fails:
        print("\nFailing cases (need prompt tightening or scope review):")
        for i, narration, expected, actual in failures:
            extra = list(normalize(actual) - normalize(expected))
            missing = list(normalize(expected) - normalize(actual))
            print(f"  case {i}: {narration!r}")
            if extra:
                print(f"    over-emitted: {extra}")
            if missing:
                print(f"    missed:       {missing}")

    print()
    if pct >= 80:
        print("SHIP GATE: PASS  (≥80%) — clear to wire into discord_dnd_bot.py")
        sys.exit(0)
    else:
        print("SHIP GATE: FAIL  (<80%) — calibrate prompt before integrating")
        sys.exit(1)


if __name__ == "__main__":
    main()
