"""S66 Fix 3 — F-035 loot auto-claim adversarial verify.

Pre-S66 bug shape: loot pipeline ended at `mark_loot_surfaced(id)` — the row
was marked surfaced and disappeared, but no inventory write fired. Players
who scrolled past the loot narration without manually invoking /giveitem
lost the items permanently.

Post-S66 fix:
  (1) At mark_loot_surfaced time in dm_respond, each pending row's
      structured items list is iterated and add_item(PARTY_STASH_BUCKET, ...)
      fires per item.
  (2) `loot_auto_claimed` telemetry line fires per item with action result.
  (3) `compute_loot_directive` narrative framing updated: items are
      auto-claimed; operator uses /loot drop to refuse.
  (4) /loot drop slash command removes items from party stash.

Tests verify:
  - enqueue_loot creates pending row with structured items
  - Simulated surface-and-clear path auto-claims items to PARTY_STASH_BUCKET
  - Multiple items in one row all auto-claim
  - Coin field is NOT auto-claimed (stays in mechanical_hints / Avrae domain)
  - /loot drop simulated path removes from party stash
  - Bare-item-mention guard: if pending_loot_rows is empty, no auto-claim
  - Cross-campaign isolation: party stash is per-campaign

Run: python3 test_loot_auto_claim.py
"""

import sys

sys.path.insert(0, '/home/jordaneal/scripts')

import dnd_engine
from dnd_engine import (
    PARTY_STASH_BUCKET,
    add_item, get_inventory, remove_item,
    enqueue_loot, mark_loot_surfaced, get_pending_loot,
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
# (1) enqueue_loot creates pending row with structured items
# ──────────────────────────────────────────────────────────────────────────────

LOOT_CAMP = create_campaign('test-guild-s66-loot', 'Loot Test')

result = enqueue_loot(
    LOOT_CAMP, 'Goblin Patrol', 'goblin_patrol',
    {'amount': 3, 'denom': 'sp'},
    ['rusty shortsword', 'crude bow']
)
check_truthy('enqueue: row created', result.get('id'))
check('enqueue: creature stored', result['creature'], 'Goblin Patrol')
check('enqueue: items stored', result['items'], ['rusty shortsword', 'crude bow'])

# Retrievable as pending
pending = get_pending_loot(LOOT_CAMP)
check('pending: 1 row', len(pending), 1)
check('pending: items match', pending[0]['items'],
      ['rusty shortsword', 'crude bow'])
check('pending: coin present', pending[0]['coin'],
      {'amount': 3, 'denom': 'sp'})


# ──────────────────────────────────────────────────────────────────────────────
# (2) Simulated surface-and-clear path: replicate the dm_respond logic that
# auto-claims items into PARTY_STASH_BUCKET.
# ──────────────────────────────────────────────────────────────────────────────

def simulate_surface_and_claim(campaign_id, pending_rows):
    """Reproduce dm_respond's S66 Fix 3 auto-claim block exactly."""
    surfaced_n = 0
    auto_claimed_items = 0
    for row in pending_rows:
        rid = row.get('id')
        if rid is not None:
            mark_loot_surfaced(rid)
            surfaced_n += 1
        for item_name in (row.get('items') or []):
            if not item_name or not item_name.strip():
                continue
            add_res = add_item(campaign_id, PARTY_STASH_BUCKET,
                               item_name.strip(), 1)
            action = (add_res or {}).get('action', 'unknown')
            if action in ('inserted', 'incremented'):
                auto_claimed_items += 1
    return surfaced_n, auto_claimed_items


surfaced_n, claimed_n = simulate_surface_and_claim(LOOT_CAMP, pending)
check('surface: 1 row surfaced', surfaced_n, 1)
check('claim: 2 items auto-claimed', claimed_n, 2)

# Verify items landed in party stash
party_inv = get_inventory(LOOT_CAMP, PARTY_STASH_BUCKET)
party_items = sorted(r['item_name'] for r in party_inv)
check('party-stash: contains both items', party_items,
      ['crude bow', 'rusty shortsword'])

# After surfacing, dnd_loot_pending should have surfaced=1 → get_pending_loot empty
post_surface = get_pending_loot(LOOT_CAMP)
check('surface: pending now empty', len(post_surface), 0)


# ──────────────────────────────────────────────────────────────────────────────
# (3) Coin is NOT auto-claimed into inventory. Coin stays in mechanical_hints
# / Avrae's domain. Confirm no inventory row exists for coin denominations.
# ──────────────────────────────────────────────────────────────────────────────

coin_items_in_stash = [r['item_name'] for r in party_inv
                        if any(d in r['item_name'].lower()
                                for d in ('gp', 'sp', 'cp', 'ep', 'pp'))]
check('coin: not in inventory (mechanical_hints handles)',
      coin_items_in_stash, [])


# ──────────────────────────────────────────────────────────────────────────────
# (4) Empty items list — coin-only loot shouldn't claim anything
# ──────────────────────────────────────────────────────────────────────────────

coin_only_camp = create_campaign('test-guild-s66-loot-coin', 'Coin Only')
enqueue_loot(coin_only_camp, 'Wolf', 'wolf',
             {'amount': 0, 'denom': 'gp'}, [])
pending_co = get_pending_loot(coin_only_camp)
_, claimed_co = simulate_surface_and_claim(coin_only_camp, pending_co)
check('coin-only: zero items claimed', claimed_co, 0)
party_co = get_inventory(coin_only_camp, PARTY_STASH_BUCKET)
check('coin-only: party stash empty', party_co, [])


# ──────────────────────────────────────────────────────────────────────────────
# (5) Empty pending list (no combat ended this turn) — no auto-claim, no error
# ──────────────────────────────────────────────────────────────────────────────

silent_camp = create_campaign('test-guild-s66-loot-silent', 'Silent')
silent_pending = get_pending_loot(silent_camp)
check('silent: no pending rows', len(silent_pending), 0)
s_n, c_n = simulate_surface_and_claim(silent_camp, silent_pending)
check('silent: 0 rows surfaced (no pending)', s_n, 0)
check('silent: 0 items claimed', c_n, 0)


# ──────────────────────────────────────────────────────────────────────────────
# (6) /loot drop simulated — remove item from party stash
# ──────────────────────────────────────────────────────────────────────────────

# LOOT_CAMP currently has {rusty shortsword × 1, crude bow × 1}
drop_result = remove_item(LOOT_CAMP, PARTY_STASH_BUCKET, 'crude bow', 1)
check('drop: action=removed', drop_result['action'], 'removed')

# Verify only rusty shortsword remains
post_drop = get_inventory(LOOT_CAMP, PARTY_STASH_BUCKET)
remaining = [r['item_name'] for r in post_drop]
check('drop: crude bow gone', 'crude bow' in remaining, False)
check_truthy('drop: rusty shortsword still in stash',
             'rusty shortsword' in remaining)

# Drop nonexistent item
ghost_drop = remove_item(LOOT_CAMP, PARTY_STASH_BUCKET, 'fictional gem', 1)
check('drop: nonexistent item → not_found', ghost_drop['action'], 'not_found')

# Drop more than exists
over_drop = remove_item(LOOT_CAMP, PARTY_STASH_BUCKET, 'rusty shortsword', 99)
check('drop: insufficient quantity → action=insufficient',
      over_drop['action'], 'insufficient')


# ──────────────────────────────────────────────────────────────────────────────
# (7) Double-combat: two distinct creature defeats in one turn → both
# get auto-claimed without dedup collision
# ──────────────────────────────────────────────────────────────────────────────

multi_camp = create_campaign('test-guild-s66-loot-multi', 'Multi Combat')

enqueue_loot(multi_camp, 'Bandit Leader', 'bandit_leader',
             {'amount': 10, 'denom': 'gp'}, ['leather armor'])
enqueue_loot(multi_camp, 'Bandit Thug', 'bandit_thug',
             None, ['shortsword', 'belt pouch'])

multi_pending = get_pending_loot(multi_camp)
check('multi: 2 rows pending', len(multi_pending), 2)

_, multi_claimed = simulate_surface_and_claim(multi_camp, multi_pending)
check('multi: 3 items auto-claimed (leather + shortsword + belt pouch)',
      multi_claimed, 3)

multi_inv = get_inventory(multi_camp, PARTY_STASH_BUCKET)
multi_items = sorted(r['item_name'] for r in multi_inv)
check('multi: all 3 distinct items in stash', multi_items,
      ['belt pouch', 'leather armor', 'shortsword'])


# ──────────────────────────────────────────────────────────────────────────────
# (8) Cross-campaign isolation
# ──────────────────────────────────────────────────────────────────────────────

iso_a = create_campaign('test-guild-s66-loot-iso-a', 'Iso A')
iso_b = create_campaign('test-guild-s66-loot-iso-b', 'Iso B')

enqueue_loot(iso_a, 'Goblin', 'goblin', None, ['dagger'])
pa = get_pending_loot(iso_a)
simulate_surface_and_claim(iso_a, pa)

a_party = get_inventory(iso_a, PARTY_STASH_BUCKET)
b_party = get_inventory(iso_b, PARTY_STASH_BUCKET)
check_truthy('iso: A has dagger',
             any(r['item_name'] == 'dagger' for r in a_party))
check('iso: B empty (no spillover)', b_party, [])


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
