"""S66 Fix 2 — F-031 quest delivery silent inventory fail adversarial verify.

Pre-S66 bug shape: `_do_quest_deliver` called `add_item(campaign, '', item, qty)`
with an empty character_name. add_item's input validator rejected empty strings,
returning {action: 'invalid', quantity_now: None}. The handler ignored the
return value and logged success regardless — silent vapor.

Post-S66 fix:
  (1) New PARTY_STASH_BUCKET = '__party__' module-level constant in dnd_engine.
  (2) `_do_quest_deliver` passes PARTY_STASH_BUCKET instead of empty string.
  (3) Handler captures add_item return value; success/failure rendered
      truthfully in #dm-aside.
  (4) `/inventory` surfaces the party stash alongside per-character inventories.

Tests verify:
  - PARTY_STASH_BUCKET constant exists and equals '__party__'
  - add_item with empty character_name still returns action='invalid'
    (regression preserved — the old buggy call would still fail honestly
    if some other call site used empty string)
  - add_item with PARTY_STASH_BUCKET returns action='inserted' or 'incremented'
  - get_inventory(PARTY_STASH_BUCKET) surfaces the items
  - Multiple party-stash inserts increment correctly (idempotent re-delivery)
  - Cross-campaign isolation: party stash is per-campaign

Run: python3 test_quest_delivery_party_stash.py
"""

import sys

sys.path.insert(0, '/home/jordaneal/scripts')

import dnd_engine
from dnd_engine import (
    PARTY_STASH_BUCKET,
    add_item, get_inventory, remove_item,
    create_campaign,
)


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


# ──────────────────────────────────────────────────────────────────────────────
# (1) PARTY_STASH_BUCKET constant exists and is the documented value
# ──────────────────────────────────────────────────────────────────────────────

check('constant: PARTY_STASH_BUCKET == "__party__"',
      PARTY_STASH_BUCKET, '__party__')
check_truthy('constant: PARTY_STASH_BUCKET is truthy (won\'t hit empty-string guard)',
             PARTY_STASH_BUCKET)


# ──────────────────────────────────────────────────────────────────────────────
# (2) Regression: empty string still returns action='invalid' (so any
# other site that passes empty string still fails honestly — no silent
# vapor anywhere)
# ──────────────────────────────────────────────────────────────────────────────

CAMP = create_campaign('test-guild-s66-quest-fix', 'Quest Fix Test')

regression_result = add_item(CAMP, '', 'phantom item', 1)
check('regression: empty character_name → action=invalid',
      regression_result['action'], 'invalid')
check('regression: empty character_name → quantity_now=None',
      regression_result['quantity_now'], None)


# ──────────────────────────────────────────────────────────────────────────────
# (3) PARTY_STASH_BUCKET as character_name → real insert + retrievable
# ──────────────────────────────────────────────────────────────────────────────

result1 = add_item(CAMP, PARTY_STASH_BUCKET, 'silver dagger', 1)
check('party: insert succeeds', result1['action'], 'inserted')
check('party: quantity_now=1', result1['quantity_now'], 1)
check('party: item normalized', result1['item_name'], 'silver dagger')

# Retrievable via get_inventory
party_inv = get_inventory(CAMP, PARTY_STASH_BUCKET)
check_truthy('party: get_inventory returns rows', len(party_inv) > 0)
check('party: first item is silver dagger', party_inv[0]['item_name'], 'silver dagger')
check('party: quantity=1', party_inv[0]['quantity'], 1)


# ──────────────────────────────────────────────────────────────────────────────
# (4) Quest-delivery simulation: deliver a quest twice; second delivery
# should increment the existing party-stash row, not duplicate.
# ──────────────────────────────────────────────────────────────────────────────

result2 = add_item(CAMP, PARTY_STASH_BUCKET, 'silver dagger', 1)
check('party: re-add increments', result2['action'], 'incremented')
check('party: quantity_now=2 after second add', result2['quantity_now'], 2)

# 50gp reward (quantity-as-coin pattern, since reward parser sometimes
# produces this shape)
result3 = add_item(CAMP, PARTY_STASH_BUCKET, '50 gp', 1)
check('party: separate item inserts cleanly', result3['action'], 'inserted')


# ──────────────────────────────────────────────────────────────────────────────
# (5) /inventory surfaces party stash. Simulate the /inventory handler
# logic: get_inventory(campaign, target) + get_inventory(campaign, '__party__').
# ──────────────────────────────────────────────────────────────────────────────

# A character has no items, but party has items
empty_char_inv = get_inventory(CAMP, 'Donovan Ruby')
check('inv: character starts empty', empty_char_inv, [])

party_inv_now = get_inventory(CAMP, PARTY_STASH_BUCKET)
check('inv: party has 2 distinct items', len(party_inv_now), 2)

# The /inventory handler should still surface the party stash even when
# character has nothing. Simulated check:
def simulate_inventory_render(camp_id, character_name):
    char_rows = get_inventory(camp_id, character_name)
    party_rows = get_inventory(camp_id, PARTY_STASH_BUCKET)
    if not char_rows and not party_rows:
        return 'empty'
    parts = []
    if char_rows:
        parts.append(f"{character_name}: {[(r['item_name'], r['quantity']) for r in char_rows]}")
    else:
        parts.append(f"{character_name}: (empty)")
    if party_rows:
        parts.append(f"party: {[(r['item_name'], r['quantity']) for r in party_rows]}")
    return " | ".join(parts)

rendered = simulate_inventory_render(CAMP, 'Donovan Ruby')
check_truthy('inv-render: character section present',
             'Donovan Ruby' in rendered)
check_truthy('inv-render: party section present',
             'party' in rendered)
check_truthy('inv-render: silver dagger surfaces',
             'silver dagger' in rendered)


# ──────────────────────────────────────────────────────────────────────────────
# (6) Cross-campaign isolation: party stash in CAMP A is invisible to CAMP B
# ──────────────────────────────────────────────────────────────────────────────

OTHER_CAMP = create_campaign('test-guild-s66-quest-iso', 'Quest Fix Iso')

other_party_inv = get_inventory(OTHER_CAMP, PARTY_STASH_BUCKET)
check('iso: other campaign party stash empty', other_party_inv, [])

# Add item to OTHER_CAMP party stash → no spillover to CAMP
result_iso = add_item(OTHER_CAMP, PARTY_STASH_BUCKET, 'magic ring', 1)
check('iso: insert in other campaign succeeds', result_iso['action'], 'inserted')

camp_party_still_has = get_inventory(CAMP, PARTY_STASH_BUCKET)
camp_item_names = [r['item_name'] for r in camp_party_still_has]
check_truthy('iso: CAMP still has silver dagger',
             'silver dagger' in camp_item_names)
check('iso: CAMP does not have magic ring (no spillover)',
      'magic ring' in camp_item_names, False)


# ──────────────────────────────────────────────────────────────────────────────
# (7) Engineered failure: invalid quantity returns action='invalid'.
# The handler should report this honestly in #dm-aside via inv_failed.
# ──────────────────────────────────────────────────────────────────────────────

fail_result = add_item(CAMP, PARTY_STASH_BUCKET, 'broken item', 0)
check('fail: zero quantity → action=invalid', fail_result['action'], 'invalid')

fail_result2 = add_item(CAMP, PARTY_STASH_BUCKET, 'broken item', -5)
check('fail: negative quantity → action=invalid', fail_result2['action'], 'invalid')


# ──────────────────────────────────────────────────────────────────────────────
# (8) remove_item works against party stash (for /loot drop in Fix 3)
# ──────────────────────────────────────────────────────────────────────────────

remove_result = remove_item(CAMP, PARTY_STASH_BUCKET, 'silver dagger', 1)
check('remove: decrement from 2→1', remove_result['action'], 'decremented')
check('remove: quantity_now=1', remove_result['quantity_now'], 1)

remove_result2 = remove_item(CAMP, PARTY_STASH_BUCKET, 'silver dagger', 1)
check('remove: final decrement → removed', remove_result2['action'], 'removed')

# Should be gone now
post_remove = get_inventory(CAMP, PARTY_STASH_BUCKET)
post_names = [r['item_name'] for r in post_remove]
check('remove: silver dagger gone from party stash',
      'silver dagger' in post_names, False)


# ──────────────────────────────────────────────────────────────────────────────
# Cleanup + report
# ──────────────────────────────────────────────────────────────────────────────

print(f"\n{PASS} passed, {FAIL} failed")
if FAILURES:
    print("\nFAILURES:")
    for f in FAILURES:
        print(f)
    sys.exit(1)
sys.exit(0)
