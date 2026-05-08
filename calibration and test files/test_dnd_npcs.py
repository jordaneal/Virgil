"""Deterministic unit tests for Phase 12A.1 — dnd_npcs engine plumbing.

Covers: canonicalize_name, schema/migration, npc_upsert (insert + all four
update branches), npc_get, npc_get_by_name, npc_list, npc_set_aliases,
npc_delete, cross-campaign isolation, origin_excerpt truncation.

No network. No real DB writes — uses a tempfile that is deleted at exit.

Run on the server:
    cd /home/jordaneal/scripts && python3 test_dnd_npcs.py
"""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, '/home/jordaneal/scripts')

# Override DB_PATH BEFORE db_init so we never touch the real DB.
_tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_tmp.close()
TEST_DB = Path(_tmp.name)

import dnd_engine                 # noqa: E402
dnd_engine.DB_PATH = TEST_DB
# Suppress engine log spam during tests; flip to print if debugging.
dnd_engine.log = lambda m: None

dnd_engine.db_init()

from dnd_engine import (           # noqa: E402
    canonicalize_name,
    npc_upsert, npc_get, npc_get_by_name, npc_list,
    npc_set_aliases, npc_delete,
)

# ── Tiny test harness (mirrors test_mechanical_hints.py) ──
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


# ─── canonicalize_name ────────────────────────────────────────────────────────
check('canon: plain',           canonicalize_name('Garrick'),         'Garrick')
check('canon: leading ws',      canonicalize_name('  Garrick'),       'Garrick')
check('canon: trailing ws',     canonicalize_name('Garrick  '),       'Garrick')
check('canon: internal runs',   canonicalize_name('Garrick   the   Smith'),
                                'Garrick the Smith')
check('canon: tabs+nl',         canonicalize_name('\tGarrick\n'),     'Garrick')
check('canon: empty',           canonicalize_name(''),                '')
check('canon: ws only',         canonicalize_name('   '),             '')
check('canon: curly apos',      canonicalize_name('O\u2019Connell'),  "O'Connell")
check('canon: curly quote',     canonicalize_name('\u201CGarrick\u201D'),
                                '"Garrick"')
check('canon: case preserved',  canonicalize_name('garrick'),         'garrick')


# ─── Insert: empty/missing campaign ───────────────────────────────────────────
CAMP = 9001  # synthetic campaign id, not present in dnd_campaigns
check('list: empty campaign', npc_list(CAMP), [])
check('upsert: empty name returns None', npc_upsert(CAMP, ''),    None)
check('upsert: ws-only name returns None', npc_upsert(CAMP, '  '), None)
check('upsert: curly-only-ws returns None', npc_upsert(CAMP, '\t\n'), None)


# ─── Insert: simple NPC ───────────────────────────────────────────────────────
gid = npc_upsert(CAMP, 'Garrick', role='blacksmith',
                 description='gruff, missing left ear',
                 origin_excerpt='You meet Garrick, a gruff smith.')
check_truthy('insert: returns id', gid)

g = npc_get(CAMP, gid)
check_truthy('get: row exists',                       g is not None)
check('get: canonical_name',     g['canonical_name'],  'Garrick')
check('get: role',               g['role'],            'blacksmith')
check('get: description',        g['description'],     'gruff, missing left ear')
check('get: aliases empty list', g['aliases'],         [])
check('get: skeleton_origin=0',  g['skeleton_origin'], 0)
check('get: mention_count=1',    g['mention_count'],   1)
check('get: location_id None',   g['location_id'],     None)
check_truthy('get: first_mentioned set', g['first_mentioned'])
check('get: first==last on insert',
      g['first_mentioned'], g['last_mentioned'])


# ─── Lookup variants ──────────────────────────────────────────────────────────
check('get_by_name: exact',      npc_get_by_name(CAMP, 'Garrick')['id'], gid)
check('get_by_name: padded',     npc_get_by_name(CAMP, '  Garrick ')['id'], gid)
check('get_by_name: missing',    npc_get_by_name(CAMP, 'Mira'),  None)
check('get_by_name: empty',      npc_get_by_name(CAMP, ''),      None)
check('get_by_name: case sensitive (no fuzzy)',
      npc_get_by_name(CAMP, 'garrick'), None)


# ─── Parser × parser: re-mention bumps mention_count + last_mentioned ─────────
import time as _time
_time.sleep(0.01)  # ensure ISO timestamp differs (microsecond resolution)
gid2 = npc_upsert(CAMP, 'Garrick')
check('upsert: same row id on dup',     gid2,                    gid)
g = npc_get(CAMP, gid)
check('upsert: mention_count bumped',   g['mention_count'],      2)
check_truthy('upsert: last_mentioned advanced',
             g['last_mentioned'] >= g['first_mentioned'])
# But first_mentioned is immutable.
g_first = g['first_mentioned']


# ─── Parser × parser: empty fields fill in, conflicts kept ────────────────────
gid3 = npc_upsert(CAMP, 'Garrick', role='', description='')  # nothing to fill
check('upsert: count bumped even with empty payload',
      npc_get(CAMP, gid)['mention_count'], 3)

# Conflict: existing role='blacksmith', new role='smith' — keep existing.
npc_upsert(CAMP, 'Garrick', role='smith')
check('upsert: parser conflict keeps existing role',
      npc_get(CAMP, gid)['role'], 'blacksmith')


# ─── Parser × parser: empty-then-fill ─────────────────────────────────────────
mid = npc_upsert(CAMP, 'Mira')                           # bare insert
m = npc_get(CAMP, mid)
check('mira: role empty', m['role'], '')
npc_upsert(CAMP, 'Mira', role='innkeeper')              # fill
m = npc_get(CAMP, mid)
check('mira: role filled by later upsert', m['role'], 'innkeeper')
check('mira: mention_count=2',             m['mention_count'], 2)


# ─── Skeleton lock: parser cannot overwrite authored canon ────────────────────
sid = npc_upsert(CAMP, 'Aldric', role='king',
                 description='just king',
                 skeleton_origin=True)
check('skeleton insert: skeleton_origin=1',
      npc_get(CAMP, sid)['skeleton_origin'], 1)
check('skeleton insert: mention_count=1',
      npc_get(CAMP, sid)['mention_count'], 1)

npc_upsert(CAMP, 'Aldric', role='usurper', description='different')
a = npc_get(CAMP, sid)
check('skeleton lock: role unchanged',        a['role'],            'king')
check('skeleton lock: description unchanged', a['description'],     'just king')
check('skeleton lock: still skeleton_origin', a['skeleton_origin'], 1)
check('skeleton lock: mention bumped',        a['mention_count'],   2)


# ─── Promotion: parser-detected → skeleton.md ─────────────────────────────────
pid = npc_upsert(CAMP, 'Bardus', role='guard')
check('promo precondition: skeleton_origin=0',
      npc_get(CAMP, pid)['skeleton_origin'], 0)
npc_upsert(CAMP, 'Bardus', role='captain', description='scarred',
           skeleton_origin=True)
b = npc_get(CAMP, pid)
check('promo: skeleton_origin=1',         b['skeleton_origin'], 1)
check('promo: role overridden',           b['role'],            'captain')
check('promo: description set',           b['description'],     'scarred')
# mention_count NOT bumped on skeleton load (load is not a narrative mention).
check('promo: mention_count not bumped',  b['mention_count'],   1)


# ─── Skeleton × skeleton re-load: fields update, no mention bump ──────────────
npc_upsert(CAMP, 'Aldric', role='king regent', skeleton_origin=True)
a = npc_get(CAMP, sid)
check('reload: role updated by skeleton',  a['role'],            'king regent')
check('reload: mention_count unchanged',   a['mention_count'],   2)


# ─── Cross-campaign isolation ─────────────────────────────────────────────────
CAMP2 = 9002
gid_other = npc_upsert(CAMP2, 'Garrick', role='different smith')
check_truthy('cross: separate row id',    gid_other != gid)
check('cross: CAMP still has 1 Garrick',
      len([n for n in npc_list(CAMP) if n['canonical_name'] == 'Garrick']), 1)
check('cross: CAMP2 Garrick role',
      npc_get_by_name(CAMP2, 'Garrick')['role'], 'different smith')
check('cross: CAMP Garrick role unchanged',
      npc_get_by_name(CAMP, 'Garrick')['role'], 'blacksmith')


# ─── npc_list filter by location_id ───────────────────────────────────────────
LOC_REDHAVEN = 1
LOC_OTHER    = 2
loc_npc1 = npc_upsert(CAMP, 'Tilda', location_id=LOC_REDHAVEN)
loc_npc2 = npc_upsert(CAMP, 'Boris', location_id=LOC_OTHER)
loc_npc3 = npc_upsert(CAMP, 'Cara',  location_id=LOC_REDHAVEN)
red = [n['canonical_name'] for n in npc_list(CAMP, location_id=LOC_REDHAVEN)]
other = [n['canonical_name'] for n in npc_list(CAMP, location_id=LOC_OTHER)]
check('list: redhaven filter',  sorted(red),    ['Cara', 'Tilda'])
check('list: other filter',     other,          ['Boris'])


# ─── npc_list ordering ────────────────────────────────────────────────────────
all_camp = npc_list(CAMP)
ids = [n['id'] for n in all_camp]
check('list: id ASC ordering', ids, sorted(ids))


# ─── aliases roundtrip ────────────────────────────────────────────────────────
check_truthy('aliases: set ok',
             npc_set_aliases(CAMP, gid, ['Garrick the Smith', 'Old Garrick']))
g = npc_get(CAMP, gid)
check('aliases: roundtrip', g['aliases'],
      ['Garrick the Smith', 'Old Garrick'])

check('aliases: reject non-list',     npc_set_aliases(CAMP, gid, 'bad'),  False)
check('aliases: reject non-string member',
      npc_set_aliases(CAMP, gid, ['ok', 42]), False)
# Previous valid aliases still in place.
check('aliases: rejection left state intact',
      npc_get(CAMP, gid)['aliases'],
      ['Garrick the Smith', 'Old Garrick'])

check('aliases: empty list ok',       npc_set_aliases(CAMP, gid, []),     True)
check('aliases: cleared',             npc_get(CAMP, gid)['aliases'],      [])


# ─── origin_excerpt truncation ────────────────────────────────────────────────
long_ex = 'X' * 250
oid = npc_upsert(CAMP, 'Bigtext', origin_excerpt=long_ex)
check('excerpt: truncated to 100',
      len(npc_get(CAMP, oid)['origin_excerpt']), 100)


# ─── npc_delete ───────────────────────────────────────────────────────────────
check('delete: returns True',  npc_delete(CAMP, oid),         True)
check('delete: gone',           npc_get(CAMP, oid),            None)
check('delete: idempotent',     npc_delete(CAMP, oid),         False)
check('delete: wrong campaign safe',
      npc_delete(CAMP2, gid),                                  False)
check('delete: cross-campaign untouched',
      npc_get(CAMP, gid) is not None, True)


# ─── npc_fragmentation_report ─────────────────────────────────────────────────
from dnd_engine import npc_fragmentation_report  # noqa: E402

# Empty campaign → all zeros
EMPTY = 9999
empty_report = npc_fragmentation_report(EMPTY)
check('frag: empty total_rows',         empty_report['total_rows'],         0)
check('frag: empty entities',           empty_report['distinct_entities'],  0)
check('frag: empty fragment_rows',      empty_report['fragment_rows'],      0)
check('frag: empty rate',               empty_report['fragmentation_rate'], 0.0)
check('frag: empty clusters',           empty_report['clusters'],           [])

# Single non-fragmenting campaign
FRAG_SOLO = 9100
npc_upsert(FRAG_SOLO, 'Garrick')
solo_report = npc_fragmentation_report(FRAG_SOLO)
check('frag: solo total',           solo_report['total_rows'],         1)
check('frag: solo entities',        solo_report['distinct_entities'],  1)
check('frag: solo fragments',       solo_report['fragment_rows'],      0)
check('frag: solo rate',            solo_report['fragmentation_rate'], 0.0)
check('frag: solo no clusters',     solo_report['clusters'],           [])

# Donovan's actual case — 3 entities, 6 rows, 50% fragmentation
FRAG_DONOVAN = 9101
for full in ['Eldrin Stormbow', 'Lira Songheart', 'Borin Ironhand']:
    npc_upsert(FRAG_DONOVAN, full)
for short in ['Eldrin', 'Lira', 'Borin']:
    npc_upsert(FRAG_DONOVAN, short)

donovan_report = npc_fragmentation_report(FRAG_DONOVAN)
check('frag: donovan total',         donovan_report['total_rows'],         6)
check('frag: donovan entities',      donovan_report['distinct_entities'],  3)
check('frag: donovan fragments',     donovan_report['fragment_rows'],      3)
check('frag: donovan rate',          donovan_report['fragmentation_rate'], 0.5)
check('frag: donovan cluster count', len(donovan_report['clusters']),      3)

primaries_seen = {c['primary'] for c in donovan_report['clusters']}
check('frag: donovan primaries are full names',
      primaries_seen, {'Eldrin Stormbow', 'Lira Songheart', 'Borin Ironhand'})

eldrin_cluster = next(c for c in donovan_report['clusters']
                      if c['primary'] == 'Eldrin Stormbow')
check('frag: donovan Eldrin fragment',  eldrin_cluster['fragments'], ['Eldrin'])
check('frag: donovan Eldrin combined mention_count',
      eldrin_cluster['combined_mention_count'], 2)

# Token-boundary discipline: "Mira" must NOT cluster with "Miranda"
FRAG_BOUND = 9102
npc_upsert(FRAG_BOUND, 'Mira')
npc_upsert(FRAG_BOUND, 'Miranda')
bound_report = npc_fragmentation_report(FRAG_BOUND)
check('frag: token boundary entities', bound_report['distinct_entities'], 2)
check('frag: token boundary fragments', bound_report['fragment_rows'],   0)
check('frag: token boundary rate',     bound_report['fragmentation_rate'], 0.0)

# Suffix is NOT a prefix — "Stormbow" does not cluster with "Eldrin Stormbow"
FRAG_SUFFIX = 9103
npc_upsert(FRAG_SUFFIX, 'Eldrin Stormbow')
npc_upsert(FRAG_SUFFIX, 'Stormbow')
suffix_report = npc_fragmentation_report(FRAG_SUFFIX)
check('frag: suffix not clustered entities', suffix_report['distinct_entities'], 2)
check('frag: suffix not clustered fragments', suffix_report['fragment_rows'],    0)

# Three-level prefix nesting — A / A B / A B C — should produce one cluster
FRAG_NEST = 9104
npc_upsert(FRAG_NEST, 'John James Smith')   # 3 tokens
npc_upsert(FRAG_NEST, 'John James')         # 2 tokens, prefix of above
npc_upsert(FRAG_NEST, 'John')               # 1 token, prefix of both
nest_report = npc_fragmentation_report(FRAG_NEST)
check('frag: nested entities',    nest_report['distinct_entities'],  1)
check('frag: nested total',       nest_report['total_rows'],         3)
check('frag: nested fragments',   nest_report['fragment_rows'],      2)
nest_cluster = nest_report['clusters'][0]
check('frag: nested primary',     nest_cluster['primary'], 'John James Smith')
check('frag: nested fragments list',
      sorted(nest_cluster['fragments']), ['John', 'John James'])

# Different first names don't cross-cluster
FRAG_DIFF = 9105
for name in ['John Smith', 'Mary Jones', 'John', 'Mary']:
    npc_upsert(FRAG_DIFF, name)
diff_report = npc_fragmentation_report(FRAG_DIFF)
check('frag: diff entities',  diff_report['distinct_entities'], 2)
check('frag: diff fragments', diff_report['fragment_rows'],     2)
check('frag: diff rate',      diff_report['fragmentation_rate'], 0.5)


# ─── PC contamination guard (Session 15) ─────────────────────────────────────
# Player characters are not NPCs. names_overlap detects token-prefix identity
# matches in either direction; npc_upsert refuses on match (skeleton exempt).
from dnd_engine import (           # noqa: E402
    names_overlap, get_bound_character_names,
    create_campaign, bind_character,
)

# names_overlap — pure function, no DB
check('overlap: equal',           names_overlap('Donovan Ruby', 'Donovan Ruby'), True)
check('overlap: prefix down',     names_overlap('Donovan', 'Donovan Ruby'),     True)
check('overlap: prefix up',       names_overlap('Donovan Ruby', 'Donovan'),     True)
check('overlap: last-name only',  names_overlap('Ruby', 'Donovan Ruby'),        True)
check('overlap: middle of 3',     names_overlap('James', 'Donovan James Ruby'), True)
check('overlap: middle name',     names_overlap('Donovan James Ruby', 'Donovan'), True)
check('overlap: no match',        names_overlap('Borin', 'Donovan'),            False)
check('overlap: substr not token', names_overlap('Don', 'Donovan Ruby'),        False)
check('overlap: empty a',         names_overlap('', 'Donovan'),                 False)
check('overlap: empty b',         names_overlap('Donovan', ''),                 False)
check('overlap: ws only a',       names_overlap('   ', 'Donovan'),              False)
check('overlap: case-sensitive',  names_overlap('donovan', 'Donovan'),          False)
check('overlap: same after canon', names_overlap('  Donovan  Ruby ', 'Donovan Ruby'), True)
# Sibling names that share NO tokens must not overlap
check('overlap: sibling first',   names_overlap('Daniel', 'Donovan Ruby'),      False)
# Equal-length tokens never qualify as prefix in either direction
check('overlap: equal-len no-match', names_overlap('Mary Jane', 'John Smith'),  False)
# Multi-token names that share ONLY a first name = distinct identities (data model)
check('overlap: multi-token shared first NOT match',
      names_overlap('Donovan James', 'Donovan Ruby'),                            False)


# ─── get_bound_character_names + npc_upsert PC refusal ──────────────────────
PC_GUILD = 'test-guild-pc-15'
PC_CAMP = create_campaign(PC_GUILD, 'PC Refusal Test')
check_truthy('pc: campaign created', PC_CAMP)

# Empty campaign → no bound PCs
check('pc: empty bound list', get_bound_character_names(PC_CAMP), [])

bind_character(PC_CAMP, 'controller-1', 'Donovan Ruby',
               race='Dwarf', char_class='Rogue', level=1)
check('pc: one bound name', get_bound_character_names(PC_CAMP), ['Donovan Ruby'])

# Refuse PC-overlapping names
refused_full = npc_upsert(PC_CAMP, 'Donovan Ruby', role='rogue')
check('npc_upsert: refuse PC full name', refused_full, None)

refused_first = npc_upsert(PC_CAMP, 'Donovan', role='rogue')
check('npc_upsert: refuse PC first name', refused_first, None)

# Last-name-only address form (the original Donovan/Ruby failure mode)
refused_last = npc_upsert(PC_CAMP, 'Ruby', role='rogue')
check('npc_upsert: refuse PC last name', refused_last, None)

# Even with NPC-style metadata, refuse
refused_with_metadata = npc_upsert(
    PC_CAMP, 'Donovan', role='rogue',
    description='party rogue', origin_excerpt='narration excerpt'
)
check('npc_upsert: refuse PC w/ metadata', refused_with_metadata, None)

# Non-overlapping names go through normally
ok_borin = npc_upsert(PC_CAMP, 'Borin', role='cleric')
check_truthy('npc_upsert: allow non-PC name', ok_borin)

# Skeleton-origin bypasses the check (authors are responsible for distinct
# canonical names; skeleton authority outranks contamination guard).
skeleton_donovan = npc_upsert(
    PC_CAMP, 'Donovan Ruby', role='legendary rogue',
    skeleton_origin=True
)
check_truthy('npc_upsert: skeleton bypass on PC name', skeleton_donovan)

# Multi-PC: bind a second character, both filtered
bind_character(PC_CAMP, 'controller-2', 'Sera Wynd',
               race='Elf', char_class='Wizard', level=2)
both_names = sorted(get_bound_character_names(PC_CAMP))
check('pc: two bound names', both_names, ['Donovan Ruby', 'Sera Wynd'])

refused_sera = npc_upsert(PC_CAMP, 'Sera Wynd', role='wizard')
check('npc_upsert: refuse 2nd PC', refused_sera, None)

refused_sera_first = npc_upsert(PC_CAMP, 'Sera', role='wizard')
check('npc_upsert: refuse 2nd PC first', refused_sera_first, None)

# Cross-campaign isolation: PC in PC_CAMP shouldn't filter other campaigns
OTHER_CAMP = create_campaign('test-guild-other', 'No PC Campaign')
ok_other = npc_upsert(OTHER_CAMP, 'Donovan Ruby', role='rogue')
check_truthy('npc_upsert: same name in different campaign OK', ok_other)


# ─── S7 — auto-execute quest dedup (Session 15) ──────────────────────────────
# parse_auto_execute → execute_auto_actions QUEST_ADD branch must dedup
# against existing ACTIVE quests (case+whitespace normalized). Manual
# /quest add remains unrestricted; this is auto-execute scope only.
from dnd_engine import (           # noqa: E402
    execute_auto_actions, quest_add, quest_set_status,
)

# Fresh campaign for these tests
QD_GUILD = 'test-guild-quest-dedup-15'
QD_CAMP = create_campaign(QD_GUILD, 'Quest Dedup Test')
check_truthy('quest dedup: campaign created', QD_CAMP)

# 1) First QUEST_ADD lands cleanly (no existing quests)
results = execute_auto_actions(QD_CAMP, [
    {'cmd': 'QUEST_ADD', 'args': ['Investigate the Crystal Cave']}
])
check('quest dedup: first add succeeds', len(results), 1)
check('quest dedup: first add success flag', results[0][0], True)

# 2) Identical title → dedup, no new row
results = execute_auto_actions(QD_CAMP, [
    {'cmd': 'QUEST_ADD', 'args': ['Investigate the Crystal Cave']}
])
check('quest dedup: identical title rejected', len(results), 0)

# 3) Case-insensitive dedup
results = execute_auto_actions(QD_CAMP, [
    {'cmd': 'QUEST_ADD', 'args': ['investigate the crystal cave']}
])
check('quest dedup: case-insensitive', len(results), 0)

# 4) Whitespace-normalized dedup ("Investigate  the  Crystal  Cave")
results = execute_auto_actions(QD_CAMP, [
    {'cmd': 'QUEST_ADD', 'args': ['Investigate  the  Crystal  Cave']}
])
check('quest dedup: whitespace-normalized', len(results), 0)

# 5) Different title → succeeds
results = execute_auto_actions(QD_CAMP, [
    {'cmd': 'QUEST_ADD', 'args': ['Find the Lost Heirloom']}
])
check('quest dedup: different title succeeds', len(results), 1)

# 6) Completing a quest unblocks re-adding the same title (non-active filter).
#    Find the original quest's id and complete it; then a new QUEST_ADD with
#    the same title should succeed.
all_quests_before = get_active_quests = None  # noqa: shadow + reset import
from dnd_engine import get_all_quests, get_active_quests as _get_active  # noqa: E402

before = _get_active(QD_CAMP)
crystal = next((q for q in before if 'crystal' in q['title'].lower()), None)
check_truthy('quest dedup: crystal cave still active', crystal is not None)

quest_set_status(QD_CAMP, crystal['id'], 'completed')
# Now re-add — should succeed because it's no longer in the ACTIVE list
results = execute_auto_actions(QD_CAMP, [
    {'cmd': 'QUEST_ADD', 'args': ['Investigate the Crystal Cave']}
])
check('quest dedup: completed quest unblocks re-add', len(results), 1)

# Cross-campaign isolation: same title in a different campaign should land
OTHER_QD_CAMP = create_campaign('test-guild-other-qd', 'Other Quest Campaign')
results = execute_auto_actions(OTHER_QD_CAMP, [
    {'cmd': 'QUEST_ADD', 'args': ['Investigate the Crystal Cave']}
])
check('quest dedup: cross-campaign isolated', len(results), 1)


# ─── S3 — get_recently_active_npcs (Session 15) ───────────────────────────────
# Derives "Recently active NPCs" prompt content from dnd_npcs.last_mentioned
# instead of the never-written legacy active_npcs field. Empty result MUST
# return [] (caller omits section entirely — never renders "(none)").
import time as _time   # noqa: E402
from dnd_engine import get_recently_active_npcs  # noqa: E402

# Empty campaign → []
EMPTY_CAMP = create_campaign('test-guild-recent-empty', 'Recent NPCs Empty')
check('recent_npcs: empty campaign', get_recently_active_npcs(EMPTY_CAMP), [])

# Single NPC → 1-element list
SOLO_CAMP = create_campaign('test-guild-recent-solo', 'Recent NPCs Solo')
npc_upsert(SOLO_CAMP, 'Lira Songheart', role='bard')
solo = get_recently_active_npcs(SOLO_CAMP)
check('recent_npcs: solo length', len(solo), 1)
check('recent_npcs: solo name', solo[0], 'Lira Songheart')

# Multiple NPCs ordered by last_mentioned DESC
MULTI_CAMP = create_campaign('test-guild-recent-multi', 'Recent NPCs Multi')
# Insert in chronological order, with explicit 0.01s spacing so timestamps
# differ even on fast hardware (last_mentioned is ISO TEXT including microseconds).
npc_upsert(MULTI_CAMP, 'Borin Ironhand')
_time.sleep(0.01)
npc_upsert(MULTI_CAMP, 'Eldrin Stormbow')
_time.sleep(0.01)
npc_upsert(MULTI_CAMP, 'Lira Songheart')
_time.sleep(0.01)
npc_upsert(MULTI_CAMP, 'Garrick')   # most recent

multi = get_recently_active_npcs(MULTI_CAMP)
check('recent_npcs: multi length', len(multi), 4)
check('recent_npcs: most recent first', multi[0], 'Garrick')
check('recent_npcs: oldest last', multi[-1], 'Borin Ironhand')

# Limit caps the result
limited = get_recently_active_npcs(MULTI_CAMP, limit=2)
check('recent_npcs: limit cap', len(limited), 2)
check('recent_npcs: limit keeps most-recent', limited[0], 'Garrick')

# Limit defaults to 6 — well above typical scene size
big = get_recently_active_npcs(MULTI_CAMP)
check('recent_npcs: default limit honored', len(big), 4)  # only 4 NPCs exist

# Re-mention bumps to top
_time.sleep(0.01)
npc_upsert(MULTI_CAMP, 'Borin Ironhand')   # bump Borin to most-recent
after_bump = get_recently_active_npcs(MULTI_CAMP)
check('recent_npcs: re-mention promotes', after_bump[0], 'Borin Ironhand')

# Cross-campaign isolation
ISO_CAMP_A = create_campaign('test-guild-iso-a', 'Iso A')
ISO_CAMP_B = create_campaign('test-guild-iso-b', 'Iso B')
npc_upsert(ISO_CAMP_A, 'Alpha')
npc_upsert(ISO_CAMP_B, 'Beta')
check('recent_npcs: cross-campaign A',
      get_recently_active_npcs(ISO_CAMP_A), ['Alpha'])
check('recent_npcs: cross-campaign B',
      get_recently_active_npcs(ISO_CAMP_B), ['Beta'])

# Limit must be at least 1 even when given 0/negative (defensive)
check('recent_npcs: limit=0 clamped',
      len(get_recently_active_npcs(MULTI_CAMP, limit=0)), 1)


# ─── S3.b — get_recently_active_npcs location_id filter (Bug 3 fix) ──────────
# Strict filter: only NPCs whose location_id matches. NPCs with NULL
# location_id are silent — the parser leaves NULL by default for any NPC
# it can't ground, so an "include NULL" rule grows the always-present set
# with every fabricated NPC (S25 live: Keeper resurfaced post-/travel).
# When location_id=None (default), prior campaign-wide behavior preserved.
from dnd_engine import location_upsert  # noqa: E402

LOC_CAMP = create_campaign('test-guild-recent-loc', 'Recent NPCs Loc Filter')
loc_tavern = location_upsert(LOC_CAMP, 'Stumbling Stag', type='tavern')
loc_spire  = location_upsert(LOC_CAMP, 'Veiled Spire',  type='citadel')

npc_upsert(LOC_CAMP, 'Tavernkeep', location_id=loc_tavern)
_time.sleep(0.01)
npc_upsert(LOC_CAMP, 'Spireguard', location_id=loc_spire)
_time.sleep(0.01)
npc_upsert(LOC_CAMP, 'Unbound Phantom')   # location_id IS NULL — must be silent under filter

# Default (no filter) — unchanged campaign-wide behavior
default_set = set(get_recently_active_npcs(LOC_CAMP))
check('recent_npcs+loc: no filter returns all',
      default_set, {'Tavernkeep', 'Spireguard', 'Unbound Phantom'})

# Filter to tavern → tavern NPC only. Unbound NPC excluded; spire NPC excluded.
at_tavern = set(get_recently_active_npcs(LOC_CAMP, location_id=loc_tavern))
check('recent_npcs+loc: tavern filter is strict',
      at_tavern, {'Tavernkeep'})
check('recent_npcs+loc: tavern filter excludes spire NPC',
      'Spireguard' in at_tavern, False)
check('recent_npcs+loc: tavern filter excludes NULL-location NPC',
      'Unbound Phantom' in at_tavern, False)

# Filter to spire → spire NPC only.
at_spire = set(get_recently_active_npcs(LOC_CAMP, location_id=loc_spire))
check('recent_npcs+loc: spire filter is strict',
      at_spire, {'Spireguard'})
check('recent_npcs+loc: spire filter excludes NULL-location NPC',
      'Unbound Phantom' in at_spire, False)

# Filter to a location with no NPCs at it → empty list (no NULL fallback)
loc_empty = location_upsert(LOC_CAMP, 'Empty Field', type='wilderness')
check('recent_npcs+loc: empty location returns []',
      get_recently_active_npcs(LOC_CAMP, location_id=loc_empty), [])

# Cross-campaign isolation preserved with filter
OTHER_LOC_CAMP = create_campaign('test-guild-recent-loc-other', 'Other Loc')
other_loc = location_upsert(OTHER_LOC_CAMP, 'Stumbling Stag', type='tavern')
npc_upsert(OTHER_LOC_CAMP, 'Different Tavernkeep', location_id=other_loc)
# Filtering campaign LOC_CAMP by other_loc id must NOT leak the other camp's
# NPC. Result is empty (no LOC_CAMP NPC has location_id=other_loc, and
# unattributed NPCs no longer leak under the strict rule).
filtered = set(get_recently_active_npcs(LOC_CAMP, location_id=other_loc))
check('recent_npcs+loc: cross-campaign isolation under filter',
      filtered, set())


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
