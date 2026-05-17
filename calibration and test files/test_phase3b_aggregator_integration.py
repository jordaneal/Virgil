"""S78 — Phase 3b aggregator integration scenarios.

Drives Stage 1 routing through clarification_handshake.aggregate_parser_outputs
with realistic Phase 3b parser output combinations. Covers the four canonical
live-verify scenarios at the parser+aggregator boundary (no Discord plumbing).

  Scenario A — transaction direct (SINGLE_DOMAIN_CLEAR)
  Scenario C — loot-drop direct (SINGLE_DOMAIN_CLEAR)
  Scenario E — multi-domain LAYER_A
  Scenario F — M-DELAYED primary (IN_FICTION_CLARIFICATION)

Run: python3 test_phase3b_aggregator_integration.py
"""
import sys
sys.path.insert(0, '/home/jordaneal/scripts')

import clarification_handshake as ch
import quest_acceptance_parser as qa
import transaction_completion_parser as tx
import loot_drop_parser as ld

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


def reset_all():
    ch.FEATURE_DISABLED = False
    ch._reset_for_tests()
    qa._reset_dedup_for_tests()
    qa.FEATURE_DISABLED = False
    tx._reset_dedup_for_tests()
    tx.FEATURE_DISABLED = False
    ld._reset_dedup_for_tests()
    ld.FEATURE_DISABLED = False


def make_pr_from_qa(result):
    cand = {}
    if result.get('matched_quest_id') is not None:
        cand = {'title': result.get('matched_quest_title', ''),
                'slash': f"/quest accept {result.get('matched_quest_id')}"}
    return ch.ParserResult(
        domain='quest_accept',
        confidence=result.get('confidence', 'low'),
        fired=bool(result.get('fired')),
        markers_present=False,  # per S77 lock
        candidate=cand,
    )


def make_pr_from_tx(result, surface_label='pre_llm'):
    cand = {}
    if result.get('npc_name') or result.get('currency'):
        c = result.get('currency') or {}
        cand = {
            'npc': result.get('npc_name', ''),
            'currency': f"{c.get('amount')}{c.get('denom')}" if c else '',
            'item': result.get('item_name', ''),
            'title': 'transaction completion',
        }
    return ch.ParserResult(
        domain='transaction_completion',
        confidence=result.get('confidence', 'low'),
        fired=bool(result.get('fired')),
        markers_present=bool(result.get('markers_present')),
        candidate=cand,
    )


def make_pr_from_ld(result):
    cand = {}
    if result.get('matched_item_name') or result.get('item_class_marker'):
        slash = ''
        if result.get('matched_pending_loot_id'):
            slash = f"/loot claim {result['matched_pending_loot_id']}"
        cand = {
            'item': (result.get('matched_item_name')
                     or result.get('item_class_marker', '')),
            'slash': slash,
            'title': 'loot claim',
        }
    return ch.ParserResult(
        domain='loot_drop_player',
        confidence=result.get('confidence', 'low'),
        fired=bool(result.get('fired')),
        markers_present=bool(result.get('markers_present')),
        candidate=cand,
    )


# ── Scenario A — transaction direct (HIGH → SINGLE_DOMAIN_CLEAR) ──
reset_all()
qa_r = qa.parse_quest_acceptance("I pay Garrick 5gp for the loaves.",
                                  offered_quests=[], campaign_id=1)
tx_r = tx.parse_transaction_completion(
    "I pay Garrick 5gp for the loaves.",
    recent_npcs=['Garrick'], inventory=[], campaign_id=1,
    surface=tx.SURFACE_PRE_LLM,
)
ld_r = ld.parse_loot_drop("I pay Garrick 5gp for the loaves.",
                          pending_loot=[], campaign_id=1, surface=ld.SURFACE_PRE_LLM)
decision = ch.aggregate_parser_outputs([
    make_pr_from_qa(qa_r), make_pr_from_tx(tx_r), make_pr_from_ld(ld_r),
])
check('A: transaction HIGH', tx_r['confidence'], 'high')
check('A: route SINGLE_DOMAIN_CLEAR', decision.route, 'SINGLE_DOMAIN_CLEAR')

# ── Scenario C — loot-drop direct ──
reset_all()
pending = [{'id': 7, 'creature': 'goblin',
            'items': [{'item_name': 'longsword', 'quantity': 1}]}]
qa_r = qa.parse_quest_acceptance("I grab the longsword.",
                                  offered_quests=[], campaign_id=1)
tx_r = tx.parse_transaction_completion(
    "I grab the longsword.", recent_npcs=[], inventory=[], campaign_id=1,
    surface=tx.SURFACE_PRE_LLM,
)
ld_r = ld.parse_loot_drop("I grab the longsword.", pending_loot=pending,
                          campaign_id=1, surface=ld.SURFACE_PRE_LLM)
decision = ch.aggregate_parser_outputs([
    make_pr_from_qa(qa_r), make_pr_from_tx(tx_r), make_pr_from_ld(ld_r),
])
check('C: loot HIGH', ld_r['confidence'], 'high')
check('C: route SINGLE_DOMAIN_CLEAR', decision.route, 'SINGLE_DOMAIN_CLEAR')

# ── Scenario E — multi-domain LAYER_A ("I'll take it") ──
reset_all()
offered = [{'id': 7, 'title': 'Stoneforge Errand'}]
qa_r = qa.parse_quest_acceptance("I'll take it.",
                                  offered_quests=offered, campaign_id=1)
# qa_r MEDIUM (verb only, no title token match)
tx_r = tx.parse_transaction_completion(
    "I'll take it.", recent_npcs=['Garrick'], inventory=[], campaign_id=1,
    surface=tx.SURFACE_PRE_LLM,
)
# tx_r LOW — bare 'take' is NOT in transaction vocab (transaction-shape
# verbs are pay/purchase/buy/give/hand/etc.; LLM-completion side includes
# 'takes' [3rd-pers] not bare 'take'). This is intentional per dispatch's
# verb spec — "I'll take it" is structurally ambiguous between
# quest_accept ("I'll take" phrasal) and loot_drop_player ('take' verb)
# but does NOT exercise transaction_completion vocabulary.
pending = [{'id': 7, 'creature': 'goblin',
            'items': [{'item_name': 'silver dagger', 'quantity': 1}]}]
ld_r = ld.parse_loot_drop("I'll take it.", pending_loot=pending, campaign_id=1,
                          surface=ld.SURFACE_PRE_LLM)
# ld_r MEDIUM (verb 'take' + no class noun in utterance)
decision = ch.aggregate_parser_outputs([
    make_pr_from_qa(qa_r), make_pr_from_tx(tx_r), make_pr_from_ld(ld_r),
])
check('E: qa MEDIUM', qa_r['confidence'], 'medium')
check('E: tx LOW (no transaction verb in utterance)',
      tx_r['confidence'], 'low')
check('E: ld MEDIUM', ld_r['confidence'], 'medium')
# 2 parsers ≥MEDIUM (qa + ld). Aggregator routes to LAYER_A or LAYER_B
# depending on candidate enumerability. ld's candidate has empty slash
# (no pending match), qa's also has empty slash (no quest title match).
# Both have populated payloads (title), so LAYER_A wins enumerability.
check('E: route is fallback (LAYER_A or LAYER_B)',
      decision.route in ('LAYER_A', 'LAYER_B'), True)
check('E: 2 candidates routed', len(decision.candidates), 2)

# ── Scenario F — M-DELAYED primary path ──
reset_all()
# "I hand 5 gold to Garrick for the loaves" — currency + NPC + out-of-vocab "hand"
# Transaction parser fires MEDIUM-with-markers (currency + npc); not HIGH
# because "hand" is in player-intent vocab so verb fires. Actually 'hand'
# IS in vocab. Let me check — yes `_PLAYER_INTENT_VERBS` includes 'hand'.
# So it'd hit HIGH (verb + currency + npc). For M-DELAYED, we need an
# OUT-OF-VOCAB verb. Test with "I drop them on the counter" — 'drop' is
# NOT in tx vocab, so it'd be LOW. Better: "I slide 5 gold to Garrick"
# — 'slide' is in LLM_COMPLETION_VERBS but not PLAYER_INTENT, so on
# pre-LLM surface it falls through to secondary set and DOES fire.
# Use truly out-of-vocab verb like 'place':
qa_r = qa.parse_quest_acceptance("I place 5 gold near Garrick.",
                                  offered_quests=[], campaign_id=1)
tx_r = tx.parse_transaction_completion(
    "I place 5 gold near Garrick.",  # 'place' not in vocab
    recent_npcs=['Garrick'], inventory=[], campaign_id=1,
    surface=tx.SURFACE_PRE_LLM,
)
ld_r = ld.parse_loot_drop("I place 5 gold near Garrick.",
                          pending_loot=[], campaign_id=1, surface=ld.SURFACE_PRE_LLM)
# tx_r LOW (no verb in vocab) — no M-DELAYED fires from this utterance.
# This proves the M-DELAYED edge: when verb is OOV, parser is silent.
# Documented in S78 handoff: M-DELAYED fires only when verb is IN vocab
# but structural signals are partial (1 of 2 of {currency, NPC}).
check('F-edge: OOV verb → tx LOW', tx_r['confidence'], 'low')

# M-DELAYED proper test: in-vocab verb + ONE structural signal.
# "I hand it to Garrick" — verb 'hand' in vocab + npc 'Garrick' + no currency
reset_all()
tx_r2 = tx.parse_transaction_completion(
    "I hand it to Garrick.",
    recent_npcs=['Garrick'], inventory=[], campaign_id=2,
    surface=tx.SURFACE_PRE_LLM,
)
check('F: tx MEDIUM-with-markers (npc only)',
      tx_r2['confidence'], 'medium')
check('F: markers_present TRUE',
      tx_r2['markers_present'], True)
# Build aggregator decision with only tx firing MEDIUM-with-markers
decision_F = ch.aggregate_parser_outputs([
    ch.ParserResult(domain='quest_accept', confidence='low', fired=False),
    ch.ParserResult(
        domain='transaction_completion',
        confidence='medium', fired=True, markers_present=True,
        candidate={'npc': 'Garrick', 'title': 'transaction completion'},
    ),
    ch.ParserResult(domain='loot_drop_player', confidence='low', fired=False),
])
check('F: aggregator routes IN_FICTION_CLARIFICATION (M-DELAYED primary)',
      decision_F.route, 'IN_FICTION_CLARIFICATION')
check('F: 1 candidate', len(decision_F.candidates), 1)
check('F: candidate domain',
      decision_F.candidates[0]['domain'], 'transaction_completion')

# ── Summary ──
total = PASS + FAIL
print(f"\nphase3b_aggregator_integration: {PASS}/{total} passed")
if FAIL:
    print("\nFAILURES:")
    for f in FAILURES:
        print(f)
    sys.exit(1)
