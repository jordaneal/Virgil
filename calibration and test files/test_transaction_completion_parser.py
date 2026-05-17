"""S78 — transaction_completion_parser tests.

Closed-vocab + structured-signal co-occurrence + 3-tier confidence +
LRU dedup + pre-LLM vs post-LLM surface separation.

Run: python3 test_transaction_completion_parser.py
"""
import sys
sys.path.insert(0, '/home/jordaneal/scripts')

import transaction_completion_parser as p

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
    p._reset_dedup_for_tests()
    p.FEATURE_DISABLED = False


# T1 — HIGH: verb + currency + NPC
reset()
r = p.parse_transaction_completion(
    "I pay Garrick 5gp for the loaves.",
    recent_npcs=['Garrick'], inventory=[], campaign_id=1,
    surface=p.SURFACE_PRE_LLM,
)
check('T1: fired', r['fired'], True)
check('T1: HIGH', r['confidence'], 'high')
check('T1: verb', r['matched_verb'], 'pay')
check('T1: currency amount', r['currency']['amount'], 5)
check('T1: currency denom', r['currency']['denom'], 'gp')
check('T1: npc match', r['npc_name'], 'Garrick')
check('T1: markers_present is False at HIGH', r['markers_present'], False)

# T2 — MEDIUM-with-markers: verb + currency, no NPC
reset()
r = p.parse_transaction_completion(
    "I hand 5 gold to the merchant.",
    recent_npcs=[], inventory=[], campaign_id=1, surface=p.SURFACE_PRE_LLM,
)
check('T2: fired', r['fired'], True)
check('T2: MEDIUM', r['confidence'], 'medium')
check('T2: markers_present TRUE', r['markers_present'], True)
check('T2: currency match', r['currency']['amount'], 5)
check('T2: no npc match', r['npc_name'], '')

# T3 — MEDIUM-with-markers: verb + NPC, no currency
reset()
r = p.parse_transaction_completion(
    "I hand it to Garrick.",
    recent_npcs=['Garrick'], inventory=[], campaign_id=1,
    surface=p.SURFACE_PRE_LLM,
)
check('T3: fired', r['fired'], True)
check('T3: MEDIUM', r['confidence'], 'medium')
check('T3: markers_present TRUE', r['markers_present'], True)
check('T3: npc match', r['npc_name'], 'Garrick')
check('T3: no currency', r['currency'], None)

# T4 — MEDIUM-no-markers: verb only
reset()
r = p.parse_transaction_completion(
    "I pay.", recent_npcs=[], inventory=[], campaign_id=1,
    surface=p.SURFACE_PRE_LLM,
)
check('T4: fired', r['fired'], True)
check('T4: MEDIUM', r['confidence'], 'medium')
check('T4: markers_present FALSE', r['markers_present'], False)

# T5 — LOW: no verb
reset()
r = p.parse_transaction_completion(
    "I look around the inn.", recent_npcs=['Garrick'], inventory=[], campaign_id=1,
    surface=p.SURFACE_PRE_LLM,
)
check('T5: not fired', r['fired'], False)
check('T5: LOW', r['confidence'], 'low')

# T6 — Post-LLM surface fires on LLM-completion verbs
reset()
r = p.parse_transaction_completion(
    "Garrick pockets the gold with a satisfied nod.",
    recent_npcs=['Garrick'], inventory=[], campaign_id=1,
    surface=p.SURFACE_POST_LLM,
)
check('T6: post-LLM fired', r['fired'], True)
check('T6: verb (phrasal-first match)', r['matched_verb'], 'pockets the gold')
check('T6: surface', r['surface'], 'post_llm')

# T7 — Phrasal "pay for" recognized
reset()
r = p.parse_transaction_completion(
    "I pay for the meal.", recent_npcs=[], inventory=[], campaign_id=1,
    surface=p.SURFACE_PRE_LLM,
)
check('T7: phrasal fired', r['fired'], True)
check('T7: phrasal verb', r['matched_verb'], 'pay for')

# T8 — LRU dedup suppresses re-fire on same key
reset()
r1 = p.parse_transaction_completion(
    "I pay Garrick 5gp.", recent_npcs=['Garrick'], inventory=[], campaign_id=99,
    surface=p.SURFACE_PRE_LLM,
)
r2 = p.parse_transaction_completion(
    "I pay Garrick 5gp.", recent_npcs=['Garrick'], inventory=[], campaign_id=99,
    surface=p.SURFACE_PRE_LLM,
)
check('T8: first fire HIGH', r1['confidence'], 'high')
check('T8: dedup-suppressed second fire', r2['dedup_suppressed'], True)
check('T8: dedup-suppressed not_fired', r2['fired'], False)

# T9 — Different currencies don't suppress each other
reset()
r1 = p.parse_transaction_completion(
    "I pay Garrick 5gp.", recent_npcs=['Garrick'], inventory=[], campaign_id=99,
    surface=p.SURFACE_PRE_LLM,
)
r2 = p.parse_transaction_completion(
    "I pay Garrick 10sp.", recent_npcs=['Garrick'], inventory=[], campaign_id=99,
    surface=p.SURFACE_PRE_LLM,
)
check('T9: distinct currency not deduped', r2['dedup_suppressed'], False)
check('T9: second fire HIGH', r2['confidence'], 'high')

# T10 — Pre-LLM and post-LLM dedup keys are namespaced (cross-surface no-collide)
reset()
r1 = p.parse_transaction_completion(
    "I pay Garrick 5gp.", recent_npcs=['Garrick'], inventory=[], campaign_id=99,
    surface=p.SURFACE_PRE_LLM,
)
r2 = p.parse_transaction_completion(
    "Garrick accepts 5gp.", recent_npcs=['Garrick'], inventory=[], campaign_id=99,
    surface=p.SURFACE_POST_LLM,
)
check('T10: cross-surface no dedup', r2['dedup_suppressed'], False)

# T11 — FEATURE_DISABLED returns disabled flag
reset()
p.FEATURE_DISABLED = True
r = p.parse_transaction_completion(
    "I pay Garrick 5gp.", recent_npcs=['Garrick'], inventory=[], campaign_id=1,
    surface=p.SURFACE_PRE_LLM,
)
check('T11: feature_disabled', r['feature_disabled'], True)
check('T11: not fired', r['fired'], False)
reset()

# T12 — Empty narration → not fired
r = p.parse_transaction_completion(
    "", recent_npcs=['Garrick'], inventory=[], campaign_id=1,
    surface=p.SURFACE_PRE_LLM,
)
check('T12: empty narration not fired', r['fired'], False)

# T13 — Currency-without-numeric ("five gold") NOT matched (regex requires digit)
reset()
r = p.parse_transaction_completion(
    "I pay five gold to Garrick.",  # 'five' is not '\d+'
    recent_npcs=['Garrick'], inventory=[], campaign_id=1, surface=p.SURFACE_PRE_LLM,
)
# Verb + NPC fires, no currency match → markers_present TRUE (npc only)
check('T13: markers_present (npc only)', r['markers_present'], True)
check('T13: no currency', r['currency'], None)
check('T13: npc match', r['npc_name'], 'Garrick')

# T14 — Inventory item match (for 'pay for X' patterns)
reset()
inv = [{'item_name': 'healing potion', 'quantity': 2}]
r = p.parse_transaction_completion(
    "I pay for the healing potion.", recent_npcs=[], inventory=inv,
    campaign_id=1, surface=p.SURFACE_PRE_LLM,
)
check('T14: item match', r['item_name'], 'healing potion')
check('T14: markers_present TRUE (item)', r['markers_present'], True)

# T15 — NPC stopword filter (don't false-match "the" in "the merchant")
reset()
r = p.parse_transaction_completion(
    "I pay the merchant.", recent_npcs=['the merchant'], inventory=[],
    campaign_id=1, surface=p.SURFACE_PRE_LLM,
)
# "merchant" (>=3 chars, non-stopword) matches
check('T15: NPC stopword filter allows content', r['npc_name'], 'the merchant')

# ── Summary ──
total = PASS + FAIL
print(f"\ntransaction_completion_parser: {PASS}/{total} passed")
if FAIL:
    print("\nFAILURES:")
    for f in FAILURES:
        print(f)
    sys.exit(1)
