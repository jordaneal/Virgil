"""S77 — §1b.1 Layer A card rendering.

Tests build_layer_a_card output format: header, per-candidate options
with pasteable slashes, narration excerpt truncation, explicit skip
framing. Reuses #dm-aside transport via _post_dm_aside (not tested here
— that's an integration-side concern).

Run: python3 test_clarification_layer_a.py
"""
import sys
sys.path.insert(0, '/home/jordaneal/scripts')

import clarification_handshake as ch

PASS = 0
FAIL = 0
FAILURES = []


def check(label, got, want):
    global PASS, FAIL
    if got == want:
        PASS += 1
    else:
        FAIL += 1
        FAILURES.append(f"  {label}: got={got!r} want={want!r}")


def check_in(label, haystack, needle):
    global PASS, FAIL
    if needle in haystack:
        PASS += 1
    else:
        FAIL += 1
        FAILURES.append(f"  {label}: {needle!r} not in {haystack!r}")


# T1 — empty candidates returns empty string
card = ch.build_layer_a_card([], '')
check('T1: empty candidates → empty string', card, '')

# T2 — single candidate (used at recursion fallback or single-candidate-A case)
# DM-voice copy post-S78 UX pass
card = ch.build_layer_a_card([
    {'domain': 'transaction_completion',
     'payload': {'slash': '/coin -5gp'}},
])
check_in('T2: DM-voice header', card, 'A quick check')
check_in('T2: humanized domain', card, 'paying or completing a trade')
check_in('T2: slash rendered', card, '/coin -5gp')
check_in('T2: skip path copy', card, "I'll keep going")

# T3 — multiple candidates labeled A/B/C with humanized domains
card = ch.build_layer_a_card([
    {'domain': 'quest_accept', 'payload': {'slash': '/quest accept 7'}},
    {'domain': 'transaction_completion', 'payload': {'slash': '/coin -5gp'}},
    {'domain': 'loot_drop_player', 'payload': {'slash': '/loot claim'}},
])
check_in('T3: label A', card, '**A.**')
check_in('T3: label B', card, '**B.**')
check_in('T3: label C', card, '**C.**')
check_in('T3: all 3 slashes', card, '/quest accept 7')
check_in('T3: humanized quest_accept', card, 'accepting an offered quest')
check_in('T3: humanized loot', card, 'claiming loot')

# T4 — narration excerpt rendered, truncated past 140 chars
long_narration = 'I' + ' lorem' * 40
card = ch.build_layer_a_card(
    [{'domain': 'transaction_completion', 'payload': {'slash': '/c'}}],
    narration_excerpt=long_narration,
)
check_in('T4: truncation marker', card, '...')

# T5 — unknown domain falls back to humanized form (underscores → spaces)
card = ch.build_layer_a_card([
    {'domain': 'mystery_domain', 'payload': {'slash': '/c'}},
])
check_in('T5: unknown domain humanized', card, 'mystery domain')

# T6 — empty-payload candidates filtered out; if all empty, no card
card = ch.build_layer_a_card([
    {'domain': 'quest_accept', 'payload': {}},
])
check('T6: empty-payload-only → no card', card, '')


# ── Summary ──
total = PASS + FAIL
print(f"\nclarification_layer_a: {PASS}/{total} passed")
if FAIL:
    print("\nFAILURES:")
    for f in FAILURES:
        print(f)
    sys.exit(1)
