"""S77 — §1b.1 Clarification Handshake aggregator (Stage 1 routing).

Tests the decentralized parser-output aggregation per §11.5 lock. Aggregator
reads ParserResult outputs (HIGH/MEDIUM/LOW + markers_present); routes per:
  - 0 ≥MEDIUM → SILENT_LOG
  - 1 HIGH → SINGLE_DOMAIN_CLEAR
  - 1 MEDIUM + markers → IN_FICTION_CLARIFICATION (M-DELAYED primary)
  - 1 MEDIUM without markers → SINGLE_DOMAIN_CLEAR
  - ≥2 MEDIUM enumerable → LAYER_A
  - ≥2 MEDIUM non-enumerable → LAYER_B

Coverage:
  T1  — 0 parsers fired → SILENT_LOG
  T2  — 1 parser HIGH fired → SINGLE_DOMAIN_CLEAR
  T3  — 1 parser MEDIUM with markers → IN_FICTION_CLARIFICATION
  T4  — 1 parser MEDIUM without markers → SINGLE_DOMAIN_CLEAR
  T5  — 2 parsers MEDIUM, both enumerable (payload populated) → LAYER_A
  T6  — 2 parsers MEDIUM, non-enumerable (empty payloads) → LAYER_B
  T7  — 3 parsers MEDIUM enumerable → LAYER_A
  T8  — FEATURE_DISABLED → SINGLE_DOMAIN_CLEAR regardless of input
  T9  — HIGH dominates: 1 HIGH + 2 MEDIUM → SINGLE_DOMAIN_CLEAR
  T10 — non-fired MEDIUM parsers do not count (fired=False is excluded)

Run: python3 test_clarification_aggregator.py
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


def reset():
    ch.FEATURE_DISABLED = False


def make_pr(domain, confidence, fired=True, markers=False, payload=None):
    return ch.ParserResult(
        domain=domain, confidence=confidence, fired=fired,
        markers_present=markers, candidate=payload or {},
    )


# T1 — 0 fires
reset()
d = ch.aggregate_parser_outputs([
    make_pr('quest_accept', 'low', fired=False),
])
check('T1: SILENT_LOG', d.route, 'SILENT_LOG')

# T2 — 1 HIGH
reset()
d = ch.aggregate_parser_outputs([
    make_pr('quest_accept', 'high', payload={'title': 'X', 'slash': '/quest accept 1'}),
])
check('T2: SINGLE_DOMAIN_CLEAR', d.route, 'SINGLE_DOMAIN_CLEAR')

# T3 — 1 MEDIUM + markers
reset()
d = ch.aggregate_parser_outputs([
    make_pr('transaction', 'medium', markers=True,
            payload={'npc': 'Garrick', 'currency': '5gp'}),
])
check('T3: IN_FICTION_CLARIFICATION', d.route, 'IN_FICTION_CLARIFICATION')

# T4 — 1 MEDIUM without markers
reset()
d = ch.aggregate_parser_outputs([
    make_pr('quest_accept', 'medium', markers=False, payload={}),
])
check('T4: SINGLE_DOMAIN_CLEAR', d.route, 'SINGLE_DOMAIN_CLEAR')

# T5 — 2 MEDIUM enumerable
reset()
d = ch.aggregate_parser_outputs([
    make_pr('quest_accept', 'medium', payload={'title': 'X', 'slash': '/quest accept 1'}),
    make_pr('transaction', 'medium', payload={'npc': 'Garrick', 'slash': '/coin -5gp'}),
])
check('T5: LAYER_A route', d.route, 'LAYER_A')
check('T5: candidate count', len(d.candidates), 2)

# T6 — 2 MEDIUM non-enumerable
reset()
d = ch.aggregate_parser_outputs([
    make_pr('quest_accept', 'medium', payload={}),
    make_pr('transaction', 'medium', payload={}),
])
check('T6: LAYER_B', d.route, 'LAYER_B')

# T7 — 3 MEDIUM enumerable
reset()
d = ch.aggregate_parser_outputs([
    make_pr('quest_accept', 'medium', payload={'title': 'A', 'slash': '/quest accept 1'}),
    make_pr('transaction', 'medium', payload={'item': 'potion', 'slash': '/coin -5gp'}),
    make_pr('loot_drop', 'medium', payload={'item': 'silver dagger', 'slash': '/loot claim'}),
])
check('T7: LAYER_A 3 candidates', d.route, 'LAYER_A')
check('T7: candidate count', len(d.candidates), 3)

# T8 — FEATURE_DISABLED
ch.FEATURE_DISABLED = True
d = ch.aggregate_parser_outputs([
    make_pr('quest_accept', 'medium', markers=True, payload={'npc': 'Garrick'}),
])
check('T8: FEATURE_DISABLED → SINGLE_DOMAIN_CLEAR', d.route, 'SINGLE_DOMAIN_CLEAR')
reset()

# T9 — HIGH dominates
d = ch.aggregate_parser_outputs([
    make_pr('quest_accept', 'high', payload={'title': 'X', 'slash': '/quest accept 1'}),
    make_pr('transaction', 'medium', payload={'npc': 'Garrick'}),
    make_pr('loot_drop', 'medium', payload={'item': 'dagger'}),
])
check('T9: HIGH dominates', d.route, 'SINGLE_DOMAIN_CLEAR')

# T10 — non-fired excluded
d = ch.aggregate_parser_outputs([
    make_pr('quest_accept', 'medium', fired=False, payload={'title': 'X'}),
    make_pr('transaction', 'medium', fired=True, markers=True, payload={'npc': 'G'}),
])
check('T10: non-fired excluded → IN_FICTION (1 fired MEDIUM with markers)',
      d.route, 'IN_FICTION_CLARIFICATION')


# ── Summary ──
total = PASS + FAIL
print(f"\nclarification_aggregator: {PASS}/{total} passed")
if FAIL:
    print("\nFAILURES:")
    for f in FAILURES:
        print(f)
    sys.exit(1)
