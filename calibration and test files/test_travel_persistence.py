"""Bug 3 — /travel destination persistence.

The /travel slash command (discord_dnd_bot.py) was previously a soft-resolve:
if the destination didn't already exist in dnd_locations, the command updated
only the embed footer (one-shot label_override) while leaving
dnd_scene_state.current_location_id pointing at the prior location forever.
The fix auto-creates the row via location_upsert and then calls
set_current_location unconditionally.

This file exercises the engine-side persistence sequence /travel performs.
The Discord interaction layer is not exercised here — we run the same
sequence of engine calls /travel runs and verify durable scene_state.

No network. No real DB writes — uses a tempfile that is deleted at exit.

Run on the server:
    cd /home/jordaneal/scripts && python3 test_travel_persistence.py
"""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, '/home/jordaneal/scripts')

_tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_tmp.close()
TEST_DB = Path(_tmp.name)

import dnd_engine                        # noqa: E402
dnd_engine.DB_PATH = TEST_DB
dnd_engine.log = lambda m: None
dnd_engine.db_init()

from dnd_engine import (                 # noqa: E402
    create_campaign, init_scene_state, get_scene_state,
    location_upsert, location_get, location_get_by_name, location_list,
    set_current_location, get_current_location,
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


def travel_persist(campaign_id: int, destination: str):
    """Replay the engine-side sequence /travel runs end-to-end. Returns
    (resolved, created, dest_loc_id) so tests can assert telemetry shape.
    """
    dest_loc = location_get_by_name(campaign_id, destination)
    created = False
    if dest_loc is None:
        new_id = location_upsert(campaign_id, destination)
        if new_id is not None:
            dest_loc = location_get(campaign_id, new_id)
            created = dest_loc is not None
    resolved = dest_loc is not None
    if dest_loc:
        set_current_location(campaign_id, dest_loc['id'])
    return resolved, created, (dest_loc['id'] if dest_loc else None)


# ─── /travel to existing location → set_current_location only, no insert ─────
CAMP = create_campaign('test-guild-travel', 'Travel Persistence')
init_scene_state(CAMP)
existing_id = location_upsert(CAMP, 'Veiled Spire', type='citadel')
set_current_location(CAMP, existing_id)
check('setup: starts at Veiled Spire',
      get_current_location(CAMP)['canonical_name'], 'Veiled Spire')

resolved, created, dest_id = travel_persist(CAMP, 'Veiled Spire')
check('travel: existing location resolved=True', resolved, True)
check('travel: existing location created=False', created, False)
check('travel: existing location id reused', dest_id, existing_id)
check('travel: scene_state still Veiled Spire',
      get_current_location(CAMP)['canonical_name'], 'Veiled Spire')


# ─── /travel to NEW location auto-creates row + persists pointer ──────────────
# This is the Bug 3 case — under the old behavior current_location_id
# would have stayed at Veiled Spire forever.
resolved, created, new_dest_id = travel_persist(CAMP, 'The Whispering Bog')
check('travel: new dest resolved=True (after upsert)', resolved, True)
check('travel: new dest created=True', created, True)
check_truthy('travel: new dest got an id', new_dest_id)
check('travel: scene_state moved to new dest',
      get_current_location(CAMP)['canonical_name'], 'Whispering Bog')

# The upserted row is canonically Whispering Bog (canonicalize_location_name
# strips the leading article). dnd_locations holds exactly two rows now.
names = sorted(r['canonical_name'] for r in location_list(CAMP))
check('travel: locations table has both rows',
      names, ['Veiled Spire', 'Whispering Bog'])


# ─── Re-running /travel to same new location is idempotent ───────────────────
# Second hit goes through location_get_by_name (finds the row), upsert is
# skipped, set_current_location no-ops at the FK layer. No duplicate row.
resolved, created, repeat_id = travel_persist(CAMP, 'Whispering Bog')
check('travel: idempotent resolved=True', resolved, True)
check('travel: idempotent created=False', created, False)
check('travel: idempotent same id', repeat_id, new_dest_id)
check('travel: idempotent no duplicate row',
      len(location_list(CAMP)), 2)


# ─── /travel from no-origin (current_location_id IS NULL) still persists ─────
# Early-game state — no location ever set. /travel should still grab the
# destination row and write current_location_id.
NEW_CAMP = create_campaign('test-guild-travel-nullorigin', 'Null Origin Travel')
init_scene_state(NEW_CAMP)
check('null-origin: starts unset', get_current_location(NEW_CAMP), None)

resolved, created, dest_id = travel_persist(NEW_CAMP, 'Frostmere Hollow')
check('null-origin: resolved=True', resolved, True)
check('null-origin: created=True', created, True)
check('null-origin: scene_state now set',
      get_current_location(NEW_CAMP)['canonical_name'], 'Frostmere Hollow')


# ─── Refusal at empty/whitespace destination — no row, no state change ───────
# location_upsert returns None on empty canonical name, so resolved/created
# both False and current_location_id stays put.
resolved, created, dest_id = travel_persist(NEW_CAMP, '   ')
check('travel: empty dest resolved=False', resolved, False)
check('travel: empty dest created=False', created, False)
check('travel: empty dest leaves prior location intact',
      get_current_location(NEW_CAMP)['canonical_name'], 'Frostmere Hollow')


# ─── get_scene_state must expose current_location_id (regression) ────────────
# Live S25 found this silently broken: get_scene_state never SELECTed
# current_location_id, so build_dm_context's location filter (and the
# at_location enrichments in consequence/commitment/init directives) all
# silently received None. Without this key the new NPC scoping is dead.
SS_CAMP = create_campaign('test-guild-scene-state-loc', 'Scene State Loc Key')
init_scene_state(SS_CAMP)
ss_loc = location_upsert(SS_CAMP, 'Lighthouse')
set_current_location(SS_CAMP, ss_loc)
_ss = get_scene_state(SS_CAMP)
check('scene_state: exposes current_location_id key',
      'current_location_id' in _ss, True)
check('scene_state: current_location_id matches set value',
      _ss['current_location_id'], ss_loc)


# ─── Cross-campaign isolation: travel in one campaign doesn't bleed ──────────
CAMP_A = create_campaign('test-guild-travel-iso-a', 'Iso A Travel')
CAMP_B = create_campaign('test-guild-travel-iso-b', 'Iso B Travel')
init_scene_state(CAMP_A)
init_scene_state(CAMP_B)
travel_persist(CAMP_A, 'Sunkstone')
travel_persist(CAMP_B, 'Glassreach')
check('iso: A at Sunkstone',
      get_current_location(CAMP_A)['canonical_name'], 'Sunkstone')
check('iso: B at Glassreach',
      get_current_location(CAMP_B)['canonical_name'], 'Glassreach')


# ─── Cleanup + summary ────────────────────────────────────────────────────────
try:
    os.unlink(TEST_DB)
except OSError:
    pass

print(f"\n{PASS} passed, {FAIL} failed")
if FAILURES:
    print("\nFAILURES:")
    for f in FAILURES:
        print(f)
    sys.exit(1)
sys.exit(0)
