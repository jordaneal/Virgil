"""S78 — loot_drop_parser tests.

Pre-LLM player-intent + post-LLM LLM-reveal surfaces; pending-loot exact
match (HIGH); item-class noun markers (MEDIUM-with-markers); container
nouns for LLM-reveal detection; LRU dedup.

Run: python3 test_loot_drop_parser.py
"""
import sys
sys.path.insert(0, '/home/jordaneal/scripts')

import loot_drop_parser as p

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


# T1 — HIGH: verb + pending loot exact match
reset()
pending = [{'id': 7, 'creature': 'goblin',
            'items': [{'item_name': 'silver dagger', 'quantity': 1}]}]
r = p.parse_loot_drop(
    "I grab the silver dagger.", pending_loot=pending, campaign_id=1,
    surface=p.SURFACE_PRE_LLM,
)
check('T1: fired', r['fired'], True)
check('T1: HIGH', r['confidence'], 'high')
check('T1: matched_pending_loot_id', r['matched_pending_loot_id'], 7)
check('T1: matched_item_name', r['matched_item_name'], 'silver dagger')
check('T1: verb (phrasal-first match)', r['matched_verb'], 'grab the')

# T2 — MEDIUM-with-markers: verb + item-class noun (no pending match)
reset()
r = p.parse_loot_drop(
    "I grab the sword from the corpse.", pending_loot=[], campaign_id=1,
    surface=p.SURFACE_PRE_LLM,
)
check('T2: fired', r['fired'], True)
check('T2: MEDIUM', r['confidence'], 'medium')
check('T2: markers_present TRUE', r['markers_present'], True)
check('T2: class marker', r['item_class_marker'], 'sword')

# T3 — MEDIUM-no-markers: verb only
reset()
r = p.parse_loot_drop(
    "I take it.", pending_loot=[], campaign_id=1, surface=p.SURFACE_PRE_LLM,
)
check('T3: fired', r['fired'], True)
check('T3: MEDIUM', r['confidence'], 'medium')
check('T3: markers_present FALSE', r['markers_present'], False)

# T4 — LOW: no verb
reset()
r = p.parse_loot_drop(
    "The room is quiet.", pending_loot=[], campaign_id=1,
    surface=p.SURFACE_PRE_LLM,
)
check('T4: not fired', r['fired'], False)

# T5 — Post-LLM reveal verb fires
reset()
r = p.parse_loot_drop(
    "The chest reveals a longsword and a healing potion.",
    pending_loot=[], campaign_id=1, surface=p.SURFACE_POST_LLM,
)
check('T5: post-LLM fired', r['fired'], True)
check('T5: verb', r['matched_verb'], 'reveals')

# T6 — Container marker matched on post-LLM
reset()
r = p.parse_loot_drop(
    "The chest reveals a longsword.", pending_loot=[], campaign_id=1,
    surface=p.SURFACE_POST_LLM,
)
check('T6: container marker', r['container_marker'], 'chest')
check('T6: markers_present TRUE', r['markers_present'], True)

# T7 — Pre-LLM does NOT match container (container only fires on post-LLM)
reset()
r = p.parse_loot_drop(
    "I open the chest carefully.", pending_loot=[], campaign_id=1,
    surface=p.SURFACE_PRE_LLM,
)
# 'open' isn't in vocab, so no fire at all
check('T7: pre-LLM no fire on container without verb', r['fired'], False)

# T8 — Phrasal "pick up"
reset()
r = p.parse_loot_drop(
    "I pick up the dagger.", pending_loot=[], campaign_id=1,
    surface=p.SURFACE_PRE_LLM,
)
check('T8: phrasal fired', r['fired'], True)
check('T8: phrasal verb', r['matched_verb'], 'pick up')

# T9 — LRU dedup
reset()
pending = [{'id': 7, 'creature': 'goblin',
            'items': [{'item_name': 'silver dagger', 'quantity': 1}]}]
r1 = p.parse_loot_drop("I grab the silver dagger.", pending_loot=pending,
                       campaign_id=99, surface=p.SURFACE_PRE_LLM)
r2 = p.parse_loot_drop("I grab the silver dagger.", pending_loot=pending,
                       campaign_id=99, surface=p.SURFACE_PRE_LLM)
check('T9: first fire HIGH', r1['confidence'], 'high')
check('T9: dedup-suppressed', r2['dedup_suppressed'], True)

# T10 — Pre-LLM vs post-LLM dedup is namespaced
reset()
pending = [{'id': 7, 'creature': 'goblin',
            'items': [{'item_name': 'silver dagger', 'quantity': 1}]}]
r1 = p.parse_loot_drop("I grab the silver dagger.", pending_loot=pending,
                       campaign_id=99, surface=p.SURFACE_PRE_LLM)
r2 = p.parse_loot_drop("The bandit drops a silver dagger.",
                       pending_loot=pending,
                       campaign_id=99, surface=p.SURFACE_POST_LLM)
# Different surface, different dedup namespace — second fires (verb 'drops')
# actually 'drops' isn't in vocab — let me use 'reveals'
r2b = p.parse_loot_drop("The chest reveals the silver dagger.",
                        pending_loot=pending,
                        campaign_id=99, surface=p.SURFACE_POST_LLM)
check('T10: cross-surface no dedup', r2b['dedup_suppressed'], False)
check('T10: cross-surface fires HIGH on pending match',
      r2b['confidence'], 'high')

# T11 — FEATURE_DISABLED
reset()
p.FEATURE_DISABLED = True
r = p.parse_loot_drop("I grab the dagger.", pending_loot=[], campaign_id=1,
                      surface=p.SURFACE_PRE_LLM)
check('T11: feature_disabled', r['feature_disabled'], True)
check('T11: not fired', r['fired'], False)
reset()

# T12 — Multi-word pending item: single-token fallback
reset()
pending = [{'id': 7, 'creature': 'goblin',
            'items': [{'item_name': 'silver dagger', 'quantity': 1}]}]
r = p.parse_loot_drop("I grab the dagger.", pending_loot=pending, campaign_id=1,
                     surface=p.SURFACE_PRE_LLM)
check('T12: single-token fallback fires HIGH', r['confidence'], 'high')
check('T12: matched item_name', r['matched_item_name'], 'silver dagger')

# T13 — Empty narration
r = p.parse_loot_drop("", pending_loot=[], campaign_id=1,
                     surface=p.SURFACE_PRE_LLM)
check('T13: empty not fired', r['fired'], False)

# ── Summary ──
total = PASS + FAIL
print(f"\nloot_drop_parser: {PASS}/{total} passed")
if FAIL:
    print("\nFAILURES:")
    for f in FAILURES:
        print(f)
    sys.exit(1)
