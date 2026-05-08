"""Deterministic unit tests for Phase 12B.1 — dnd_locations engine plumbing.

Covers: canonicalize_location_name (incl. article stripping),
schema/migration, location_upsert (insert + all four update branches),
location_get, location_get_by_name, location_list (incl. parent filter),
location_set_aliases, location_delete (incl. inbound FK cleanup),
set_current_location (incl. FK validation, None clearing, cross-campaign
refusal), get_current_location, plus integration with NPC location_id
and dnd_scene_state.

No network. Uses a tempfile DB that is deleted at exit.

Run on the server:
    cd /home/jordaneal/scripts && python3 test_dnd_locations.py
"""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, '/home/jordaneal/scripts')

# Override DB_PATH BEFORE db_init.
_tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_tmp.close()
TEST_DB = Path(_tmp.name)

import dnd_engine                 # noqa: E402
dnd_engine.DB_PATH = TEST_DB
dnd_engine.log = lambda m: None

dnd_engine.db_init()

from dnd_engine import (           # noqa: E402
    canonicalize_location_name,
    location_upsert, location_get, location_get_by_name, location_list,
    location_set_aliases, location_delete,
    set_current_location, get_current_location,
    init_scene_state,
    npc_upsert, npc_get,
)

# ── Tiny harness ──
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


# ─── canonicalize_location_name ───────────────────────────────────────────────
check('canon: plain',           canonicalize_location_name('Redhaven'),  'Redhaven')
check('canon: leading ws',      canonicalize_location_name('  Redhaven'), 'Redhaven')
check('canon: trailing ws',     canonicalize_location_name('Redhaven  '), 'Redhaven')
check('canon: internal runs',   canonicalize_location_name('Rusty   Anchor'),
                                'Rusty Anchor')
check('canon: tabs+nl',         canonicalize_location_name('\tRedhaven\n'), 'Redhaven')
check('canon: empty',           canonicalize_location_name(''),          '')
check('canon: ws only',         canonicalize_location_name('   '),       '')
check('canon: curly apos',      canonicalize_location_name('Loch\u2019s End'),
                                "Loch's End")

# Article stripping — case-insensitive on the article, case preserved on rest
check('canon: strip "The"',     canonicalize_location_name('The Rusty Anchor'),
                                'Rusty Anchor')
check('canon: strip "the"',     canonicalize_location_name('the Rusty Anchor'),
                                'Rusty Anchor')
check('canon: strip "THE"',     canonicalize_location_name('THE Rusty Anchor'),
                                'Rusty Anchor')
check('canon: strip "A"',       canonicalize_location_name('A Hidden Cave'),
                                'Hidden Cave')
check('canon: strip "a"',       canonicalize_location_name('a Hidden Cave'),
                                'Hidden Cave')
check('canon: strip "An"',      canonicalize_location_name('An Old Shrine'),
                                'Old Shrine')
check('canon: strip "an"',      canonicalize_location_name('an Old Shrine'),
                                'Old Shrine')

# Non-strip cases — embedded prefixes that LOOK like articles
check('canon: keep Theramore',  canonicalize_location_name('Theramore'),  'Theramore')
check('canon: keep Avernus',    canonicalize_location_name('Avernus'),    'Avernus')
check('canon: keep Anvilrest',  canonicalize_location_name('Anvilrest'),  'Anvilrest')
check('canon: keep Andora',     canonicalize_location_name('Andora'),     'Andora')

# Bare article never strips (last token preserved)
check('canon: bare The',        canonicalize_location_name('The'),        'The')
check('canon: bare A',          canonicalize_location_name('A'),          'A')

# Article inside name — only LEADING article strips
check('canon: keep mid-the',    canonicalize_location_name('Inn of the Bear'),
                                'Inn of the Bear')

# Stacked leading articles strip iteratively (matches honorific stripping
# precedent — "Sir Doctor Bardus" → "Bardus"). The leading-token-only rule
# means mid-name "the" is preserved (see "Inn of the Bear" above).
check('canon: stacked articles strip iteratively',
      canonicalize_location_name('The The Anchor'),  'Anchor')

# Curly normalization + strip combined
check('canon: combo strip',     canonicalize_location_name('  the  Rusty\u2019s Inn  '),
                                "Rusty's Inn")


# ─── Insert: empty / invalid name ─────────────────────────────────────────────
CAMP = 8001
check('list: empty campaign', location_list(CAMP), [])
check('upsert: empty name returns None', location_upsert(CAMP, ''),    None)
check('upsert: ws-only name returns None', location_upsert(CAMP, '  '), None)


# ─── Insert: simple location ──────────────────────────────────────────────────
rid = location_upsert(CAMP, 'Redhaven', type='town',
                      description='salt-stained port',
                      origin_excerpt='You arrive in Redhaven, a salt-stained port.')
check_truthy('insert: returns id', rid)

r = location_get(CAMP, rid)
check_truthy('get: row exists',                r is not None)
check('get: canonical_name',     r['canonical_name'],  'Redhaven')
check('get: type',               r['type'],            'town')
check('get: description',        r['description'],     'salt-stained port')
check('get: aliases empty list', r['aliases'],         [])
check('get: skeleton_origin=0',  r['skeleton_origin'], 0)
check('get: mention_count=1',    r['mention_count'],   1)
check('get: parent_location_id None', r['parent_location_id'],  None)
check_truthy('get: first_mentioned set', r['first_mentioned'])
check('get: first==last on insert',
      r['first_mentioned'], r['last_mentioned'])


# ─── Lookup variants — including article-stripped equivalence ─────────────────
check('get_by_name: exact',      location_get_by_name(CAMP, 'Redhaven')['id'], rid)
check('get_by_name: padded',     location_get_by_name(CAMP, '  Redhaven ')['id'], rid)

# The big behavior change for locations: "The Foo" and "Foo" find the same row
inn_id = location_upsert(CAMP, 'The Rusty Anchor', type='tavern',
                         parent_location_id=rid)
check_truthy('insert "The Rusty Anchor" returns id', inn_id)
check('get_by_name: stored as "Rusty Anchor" (article stripped)',
      location_get(CAMP, inn_id)['canonical_name'], 'Rusty Anchor')
check('get_by_name: lookup with article finds same row',
      location_get_by_name(CAMP, 'The Rusty Anchor')['id'], inn_id)
check('get_by_name: lookup without article finds same row',
      location_get_by_name(CAMP, 'Rusty Anchor')['id'], inn_id)
check('get_by_name: case-insensitive article only',
      location_get_by_name(CAMP, 'the rusty anchor'), None)  # case still matters on rest


# ─── Upsert collapses article variants (the wins for locations) ───────────────
# Same person, two narration forms, ONE row — the location identity-frag fix
maw_first = location_upsert(CAMP, 'The Crystal Maw', type='dungeon')
maw_second = location_upsert(CAMP, 'Crystal Maw')  # bare form mid-session
check('upsert: article variants collapse',     maw_first,                     maw_second)
check('upsert: mention_count bumped on collapse',
      location_get(CAMP, maw_first)['mention_count'], 2)


# ─── Parser × parser: re-mention bumps count + last_mentioned ─────────────────
import time as _time
_time.sleep(0.01)
rid2 = location_upsert(CAMP, 'Redhaven')
check('upsert: same row id on dup',     rid2,                         rid)
r = location_get(CAMP, rid)
check('upsert: mention_count bumped',   r['mention_count'],           2)
check_truthy('upsert: last_mentioned advanced',
             r['last_mentioned'] >= r['first_mentioned'])


# ─── Parser × parser: empty fields fill, conflicts kept ───────────────────────
forge_id = location_upsert(CAMP, 'Stoneforge', type='guild hall')
location_upsert(CAMP, 'Stoneforge', type='different type')
check('upsert: parser conflict keeps existing type',
      location_get(CAMP, forge_id)['type'], 'guild hall')

# Empty-then-fill
shrine = location_upsert(CAMP, 'Old Shrine')
check('shrine: type empty', location_get(CAMP, shrine)['type'], '')
location_upsert(CAMP, 'Old Shrine', type='temple')
check('shrine: type filled by later upsert',
      location_get(CAMP, shrine)['type'], 'temple')


# ─── Skeleton lock: parser cannot overwrite authored canon ────────────────────
sid = location_upsert(CAMP, 'Aldric\'s Keep', type='fortress',
                      description='ruined battlements',
                      skeleton_origin=True)
check('skeleton insert: skeleton_origin=1',
      location_get(CAMP, sid)['skeleton_origin'], 1)
location_upsert(CAMP, 'Aldric\'s Keep', type='palace', description='different')
keep = location_get(CAMP, sid)
check('skeleton lock: type unchanged',        keep['type'],            'fortress')
check('skeleton lock: description unchanged', keep['description'],     'ruined battlements')
check('skeleton lock: still skeleton_origin', keep['skeleton_origin'], 1)
check('skeleton lock: mention bumped',        keep['mention_count'],   2)


# ─── Promotion: parser → skeleton ─────────────────────────────────────────────
promo_id = location_upsert(CAMP, 'Lower Quarter', type='district')
check('promo precondition: skeleton_origin=0',
      location_get(CAMP, promo_id)['skeleton_origin'], 0)
location_upsert(CAMP, 'Lower Quarter', type='slums', description='thieves run it',
                skeleton_origin=True)
lq = location_get(CAMP, promo_id)
check('promo: skeleton_origin=1',         lq['skeleton_origin'], 1)
check('promo: type overridden',           lq['type'],            'slums')
check('promo: description set',           lq['description'],     'thieves run it')
check('promo: mention_count not bumped',  lq['mention_count'],   1)


# ─── Cross-campaign isolation ─────────────────────────────────────────────────
CAMP2 = 8002
rid_other = location_upsert(CAMP2, 'Redhaven', type='different town')
check_truthy('cross: separate row id',    rid_other != rid)
check('cross: CAMP Redhaven type unchanged',
      location_get_by_name(CAMP, 'Redhaven')['type'], 'town')
check('cross: CAMP2 Redhaven type',
      location_get_by_name(CAMP2, 'Redhaven')['type'], 'different town')


# ─── Hierarchical: parent_location_id ─────────────────────────────────────────
# Redhaven (rid) is parent of Rusty Anchor (inn_id, set above)
children = location_list(CAMP, parent_location_id=rid)
child_names = [c['canonical_name'] for c in children]
check_truthy('children: Rusty Anchor under Redhaven', 'Rusty Anchor' in child_names)
check('children: parent matches', children[0]['parent_location_id'], rid)

# Sibling: another tavern in Redhaven
sister = location_upsert(CAMP, 'The Iron Tankard', type='tavern',
                         parent_location_id=rid)
sib_children = location_list(CAMP, parent_location_id=rid)
check('children: 2 under Redhaven', len(sib_children), 2)


# ─── location_list ordering ───────────────────────────────────────────────────
all_camp = location_list(CAMP)
ids = [n['id'] for n in all_camp]
check('list: id ASC ordering', ids, sorted(ids))


# ─── aliases roundtrip ────────────────────────────────────────────────────────
check_truthy('aliases: set ok',
             location_set_aliases(CAMP, rid, ['Red Haven', 'The Port']))
r = location_get(CAMP, rid)
check('aliases: roundtrip', r['aliases'], ['Red Haven', 'The Port'])

check('aliases: reject non-list',     location_set_aliases(CAMP, rid, 'bad'),  False)
check('aliases: reject non-string member',
      location_set_aliases(CAMP, rid, ['ok', 42]), False)
check('aliases: rejection left state intact',
      location_get(CAMP, rid)['aliases'],
      ['Red Haven', 'The Port'])

check('aliases: empty list ok',       location_set_aliases(CAMP, rid, []),     True)
check('aliases: cleared',             location_get(CAMP, rid)['aliases'],      [])


# ─── origin_excerpt truncation ────────────────────────────────────────────────
long_ex = 'X' * 250
oid = location_upsert(CAMP, 'Bigtext Pass', origin_excerpt=long_ex)
check('excerpt: truncated to 100',
      len(location_get(CAMP, oid)['origin_excerpt']), 100)


# ─── set_current_location: FK validation, None clearing, refusal cases ────────
init_scene_state(CAMP)        # required for current_location_id writes
init_scene_state(CAMP2)

# Initially unset
check('current: starts None', get_current_location(CAMP), None)

# Valid set
check_truthy('current: set valid id', set_current_location(CAMP, rid))
check('current: get returns Redhaven',
      get_current_location(CAMP)['canonical_name'], 'Redhaven')

# Update to another valid id
check_truthy('current: switch to inn', set_current_location(CAMP, inn_id))
check('current: now Rusty Anchor',
      get_current_location(CAMP)['canonical_name'], 'Rusty Anchor')

# Clear with None
check_truthy('current: clear with None', set_current_location(CAMP, None))
check('current: cleared', get_current_location(CAMP), None)

# Refuse non-existent id
check('current: refuse invalid id',
      set_current_location(CAMP, 999_999), False)
check('current: still cleared after refused write',
      get_current_location(CAMP), None)

# Refuse cross-campaign id (rid_other belongs to CAMP2, not CAMP)
check('current: refuse cross-campaign id',
      set_current_location(CAMP, rid_other), False)
check('current: still cleared after cross-campaign refusal',
      get_current_location(CAMP), None)

# CAMP2 still works independently
check_truthy('current: CAMP2 set independent',
             set_current_location(CAMP2, rid_other))
check('current: CAMP2 has own location',
      get_current_location(CAMP2)['canonical_name'], 'Redhaven')

# Refuse for campaign with no scene_state row
NO_STATE_CAMP = 8003
loc_in_no_state = location_upsert(NO_STATE_CAMP, 'Lonely Tower')
check('current: refuse when scene_state missing',
      set_current_location(NO_STATE_CAMP, loc_in_no_state), False)


# ─── location_delete: inbound FK cleanup ──────────────────────────────────────
# Setup: create a parent + child + NPC in the child, set CAMP2 current to parent
del_camp = 8010
init_scene_state(del_camp)
parent_loc = location_upsert(del_camp, 'Hollowmoor', type='region')
child_loc = location_upsert(del_camp, 'The Hollow Inn', type='tavern',
                            parent_location_id=parent_loc)
# An NPC pinned to the child location
npc_id = npc_upsert(del_camp, 'Tilda', location_id=child_loc)
# Party in the child
set_current_location(del_camp, child_loc)

# Sanity preconditions
check('del-pre: child has parent',
      location_get(del_camp, child_loc)['parent_location_id'], parent_loc)
check('del-pre: npc has location',
      npc_get(del_camp, npc_id)['location_id'], child_loc)
check('del-pre: current is child',
      get_current_location(del_camp)['id'], child_loc)

# Delete the child — children, NPC, current_location all cleared
check_truthy('delete child returns True', location_delete(del_camp, child_loc))
check('delete: row gone', location_get(del_camp, child_loc), None)
check('delete: npc.location_id cleared',
      npc_get(del_camp, npc_id)['location_id'], None)
check('delete: current_location_id cleared',
      get_current_location(del_camp), None)

# Now delete the parent — should succeed (no children left, no NPCs)
check_truthy('delete parent returns True', location_delete(del_camp, parent_loc))
check('delete: parent gone', location_get(del_camp, parent_loc), None)

# Idempotent + cross-campaign safe
check('delete: idempotent', location_delete(del_camp, parent_loc), False)
check('delete: wrong-campaign safe', location_delete(CAMP2, rid),  False)
check('delete: CAMP2 location untouched',
      location_get(CAMP2, rid_other) is not None, True)

# Re-parent on parent-only delete (child must survive, just with NULL parent)
re_camp = 8011
init_scene_state(re_camp)
top = location_upsert(re_camp, 'Skyreach', type='region')
mid = location_upsert(re_camp, 'Cloudkeep', type='fortress', parent_location_id=top)
location_delete(re_camp, top)
check('reparent: child survives',
      location_get(re_camp, mid) is not None, True)
check('reparent: child parent_location_id cleared',
      location_get(re_camp, mid)['parent_location_id'], None)


# ─── Schema migration: current_location_id column exists on dnd_scene_state ──
import sqlite3 as _sql
_c = _sql.connect(TEST_DB)
_cols = {row[1] for row in _c.execute("PRAGMA table_info(dnd_scene_state)")}
_c.close()
check_truthy('migration: current_location_id column added',
             'current_location_id' in _cols)
check_truthy('migration: tension_int still present',
             'tension_int' in _cols)
check_truthy('migration: progress_clocks still present',
             'progress_clocks' in _cols)


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
