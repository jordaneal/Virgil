"""S77 — §1b.1 routing end-to-end (aggregator + directive integration).

End-to-end test that drives Stage 1 routing decisions through
clarification_handshake.aggregate_parser_outputs + verifies that:
  - IN_FICTION_CLARIFICATION route's candidates are renderable by the
    pending_clarification directive composer
  - LAYER_A route's candidates render a valid card
  - LAYER_B route's candidates render a valid question + reply parser
    accepts the matching domain

This is the integration-level confidence-check beyond the unit tests in
the other clarification test files; exercises the chain of decision →
artifact rendering that the pre-LLM hook performs at runtime.

Run: python3 test_clarification_routing_e2e.py
"""
import sys
sys.path.insert(0, '/home/jordaneal/scripts')

import clarification_handshake as ch
import dnd_orchestration as orch

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


def check_truthy(label, got):
    global PASS, FAIL
    if got:
        PASS += 1
    else:
        FAIL += 1
        FAILURES.append(f"  {label}: expected truthy, got={got!r}")


def make_pr(domain, confidence, fired=True, markers=False, payload=None):
    return ch.ParserResult(
        domain=domain, confidence=confidence, fired=fired,
        markers_present=markers, candidate=payload or {},
    )


# ── E1: Scenario F shape (1-MEDIUM-with-markers, M-DELAYED primary) ──
ch.FEATURE_DISABLED = False
parsers = [
    make_pr('transaction', 'medium', markers=True,
            payload={'npc': 'Garrick', 'currency': '5 gold', 'item': 'loaves'}),
    make_pr('quest_accept', 'low', fired=False),
    make_pr('loot_drop', 'low', fired=False),
]
decision = ch.aggregate_parser_outputs(parsers)
check('E1: route', decision.route, 'IN_FICTION_CLARIFICATION')
check('E1: candidate count', len(decision.candidates), 1)
# Directive renders the marker summary
body, signals = orch.compute_pending_clarification_directive({
    'candidates': decision.candidates,
})
check('E1: directive fired', signals['fired'], True)
check_truthy('E1: body contains markers',
             '5 gold' in body and 'Garrick' in body)

# ── E2: Scenario E shape (cross-domain Layer A direct) ──
parsers = [
    make_pr('quest_accept', 'medium',
            payload={'title': 'Stoneforge', 'slash': '/quest accept 7'}),
    make_pr('transaction', 'medium',
            payload={'npc': 'Brak', 'slash': '/coin -5gp'}),
    make_pr('loot_drop', 'medium',
            payload={'item': 'silver dagger', 'slash': '/loot claim silver_dagger'}),
]
decision = ch.aggregate_parser_outputs(parsers)
check('E2: route', decision.route, 'LAYER_A')
check('E2: 3 candidates', len(decision.candidates), 3)
card = ch.build_layer_a_card(decision.candidates,
                              narration_excerpt="I'll take it")
check_truthy('E2: card non-empty', len(card) > 0)
# Post-S78 UX pass: card uses humanized domain labels. Raw machine names
# replaced with operator-friendly phrases via _humanize_domain.
check_truthy('E2: card has all 3 labels (humanized + underscore-to-space fallback)',
             'accepting an offered quest' in card
             and 'transaction' in card
             and 'loot drop' in card)
check_truthy('E2: card has each slash',
             '/quest accept 7' in card and '/coin -5gp' in card
             and '/loot claim silver_dagger' in card)

# ── E3: Layer B route + reply parsing ──
parsers = [
    make_pr('transaction', 'medium', payload={}),
    make_pr('loot_drop', 'medium', payload={}),
]
decision = ch.aggregate_parser_outputs(parsers)
check('E3: route', decision.route, 'LAYER_B')
q = ch.build_layer_b_question(decision.candidates,
                               narration_excerpt='He extends a pouch')
check_truthy('E3: question non-empty', len(q) > 0)
intent = ch.parse_layer_b_reply('transaction', decision.candidates)
check('E3: reply commits transaction', intent['intent'], 'COMMIT_transaction')

intent_skip = ch.parse_layer_b_reply('skip', decision.candidates)
check('E3: reply skip', intent_skip['intent'], 'EXPLICIT_SKIP')


# ── Summary ──
total = PASS + FAIL
print(f"\nclarification_routing_e2e: {PASS}/{total} passed")
if FAIL:
    print("\nFAILURES:")
    for f in FAILURES:
        print(f)
    sys.exit(1)
