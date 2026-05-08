"""Unit tests for skeleton_loader — Phase 12C.

Uses a tempfile DB and a tempdir for skeleton files. No network.

Coverage:
  - _parse_h3_heading edge cases
  - _parse_skeleton_text on minimal, full, malformed inputs
  - parse_skeleton_file mtime caching (cache hit / cache invalidation / no file)
  - apply_skeleton happy path (locations + NPCs persist with skeleton_origin=1)
  - apply_skeleton parent resolution + NPC location_id resolution
  - apply_skeleton idempotence (re-run = same DB state, no duplicate rows)
  - apply_skeleton authority: parser cannot overwrite skeleton fields after load
  - get_skeleton_prompt_block content + truncation
  - SkeletonParseError on H3 outside known section

Run on the server:
    cd /home/jordaneal/scripts && python3 test_skeleton_loader.py
"""

import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, '/home/jordaneal/scripts')

# Tempfile DB BEFORE db_init.
_db_tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_db_tmp.close()
TEST_DB = Path(_db_tmp.name)

# Tempdir for skeleton files.
_skel_root = tempfile.mkdtemp(prefix='skeleton_test_')
SKEL_ROOT = Path(_skel_root)

import dnd_engine                 # noqa: E402
dnd_engine.DB_PATH = TEST_DB
dnd_engine.log = lambda m: None
dnd_engine.db_init()

import skeleton_loader            # noqa: E402
skeleton_loader.SKELETON_ROOT = SKEL_ROOT
# Quiet the loader's log too.
skeleton_loader.log = lambda m: None
# Reset the in-memory cache between test scenarios.
skeleton_loader._cache.clear()

from skeleton_loader import (     # noqa: E402
    _parse_h3_heading, _parse_skeleton_text,
    parse_skeleton_file, apply_skeleton, get_skeleton_prompt_block,
    SkeletonParseError,
)
from dnd_engine import (          # noqa: E402
    npc_get_by_name, npc_list, npc_upsert,
    location_get_by_name, location_list, location_upsert,
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

def check_falsy(label, got):
    global PASS, FAIL
    if not got:
        PASS += 1
    else:
        FAIL += 1
        FAILURES.append(f"  {label}: expected falsy, got={got!r}")


def write_skel(campaign_id: int, text: str) -> Path:
    d = SKEL_ROOT / str(campaign_id)
    d.mkdir(parents=True, exist_ok=True)
    p = d / "skeleton.md"
    p.write_text(text, encoding="utf-8")
    return p


# ─── _parse_h3_heading ────────────────────────────────────────────────────────
check('h3: bare name',
      _parse_h3_heading("Garrick"),
      {'name': 'Garrick', 'kind': '', 'parent_hint': ''})

check('h3: name + role only',
      _parse_h3_heading("Garrick (blacksmith)"),
      {'name': 'Garrick', 'kind': 'blacksmith', 'parent_hint': ''})

check('h3: name + role + location',
      _parse_h3_heading("Garrick (blacksmith, Redhaven)"),
      {'name': 'Garrick', 'kind': 'blacksmith', 'parent_hint': 'Redhaven'})

check('h3: location with "in" prefix',
      _parse_h3_heading("The Rusty Anchor (tavern in Redhaven)"),
      {'name': 'The Rusty Anchor', 'kind': 'tavern', 'parent_hint': 'Redhaven'})

check('h3: location bare type',
      _parse_h3_heading("Redhaven (town)"),
      {'name': 'Redhaven', 'kind': 'town', 'parent_hint': ''})

check('h3: extra whitespace',
      _parse_h3_heading("   Garrick   (  blacksmith ,  Redhaven  )   "),
      {'name': 'Garrick', 'kind': 'blacksmith', 'parent_hint': 'Redhaven'})

# Empty heading is structurally bad → raise
try:
    _parse_h3_heading("")
    check('h3: empty raises', 'no_raise', 'should_raise')
except SkeletonParseError:
    check('h3: empty raises', 'raised', 'raised')

# Empty name inside parens
try:
    _parse_h3_heading("(blacksmith)")
    check('h3: empty name raises', 'no_raise', 'should_raise')
except SkeletonParseError:
    check('h3: empty name raises', 'raised', 'raised')


# ─── _parse_skeleton_text ─────────────────────────────────────────────────────
SKEL_FULL = """\
# Campaign: Test Campaign

## Central conflict
The cult is rising. The party must stop them before the eclipse.

## Major hooks
- Find the missing brother
- Investigate the burned shrine
- Ally with the rebels

## Primary NPCs
### Garrick (blacksmith, Redhaven)
Motivation: Wants the cult exposed.
Voice: Gruff, plainspoken.

### Mira (innkeeper, Redhaven)
Motivation: Knows more than she lets on.

## Key locations
### Redhaven (town)
A coastal trade town. Tense — cult activity rising.

### The Rusty Anchor (tavern in Redhaven)
Smoky, low-ceilinged.

## Factions
### The Crimson Hand (cult)
Goal: Awaken something old.
"""

parsed = _parse_skeleton_text(SKEL_FULL)
check('full: title',          parsed['title'],          'Test Campaign')
check_truthy('full: central conflict set', parsed['central_conflict'])
check('full: hooks count',    len(parsed['hooks']),     3)
check('full: hook 0',         parsed['hooks'][0],       'Find the missing brother')
check('full: npcs count',     len(parsed['npcs']),      2)
check('full: npc 0 name',     parsed['npcs'][0]['name'], 'Garrick')
check('full: npc 0 role',     parsed['npcs'][0]['role'], 'blacksmith')
check('full: npc 0 loc hint', parsed['npcs'][0]['location_hint'], 'Redhaven')
check_truthy('full: npc 0 description', parsed['npcs'][0]['description'])
check('full: locations count',len(parsed['locations']), 2)
check('full: loc 0 name',     parsed['locations'][0]['name'], 'Redhaven')
check('full: loc 0 type',     parsed['locations'][0]['type'], 'town')
check('full: loc 1 parent',   parsed['locations'][1]['parent_hint'], 'Redhaven')
check('full: factions count', len(parsed['factions']),  1)
check('full: unknown sections empty', parsed['unknown_sections'], [])

# Minimal skeleton — title only
parsed_min = _parse_skeleton_text("# Campaign: Bare\n")
check('min: title',     parsed_min['title'],     'Bare')
check('min: npcs',      parsed_min['npcs'],      [])
check('min: locations', parsed_min['locations'], [])

# Empty file
parsed_empty = _parse_skeleton_text("")
check('empty: title',     parsed_empty['title'],     '')
check('empty: hooks',     parsed_empty['hooks'],     [])
check('empty: npcs',      parsed_empty['npcs'],      [])
check('empty: locations', parsed_empty['locations'], [])

# Unknown section is collected, not fatal
parsed_unknown = _parse_skeleton_text("""\
## Random Section
- not parsed
""")
check('unknown: collected', parsed_unknown['unknown_sections'], ['Random Section'])

# H3 outside section → strict raise
try:
    _parse_skeleton_text("### Garrick (blacksmith)\n")
    check('strict: h3 no section raises', 'no_raise', 'should_raise')
except SkeletonParseError:
    check('strict: h3 no section raises', 'raised', 'raised')


# ─── parse_skeleton_file: mtime cache + missing file ──────────────────────────
CAMP_FILE = 9201
write_skel(CAMP_FILE, SKEL_FULL)

# First read populates cache
p1 = parse_skeleton_file(CAMP_FILE)
check_truthy('file: parsed dict returned', p1)
check('file: title',       p1['title'],          'Test Campaign')
check('file: cache size 1', len(skeleton_loader._cache), 1)

# Second read hits cache (same object reference because we return cached value)
p2 = parse_skeleton_file(CAMP_FILE)
check('file: cached return is same object', p1 is p2, True)

# mtime change forces re-parse
time.sleep(0.05)  # ensure mtime resolution
write_skel(CAMP_FILE, SKEL_FULL.replace('Test Campaign', 'Updated'))
p3 = parse_skeleton_file(CAMP_FILE)
check('file: mtime update reparses', p3['title'], 'Updated')
check_falsy('file: not the cached object', p3 is p1)

# Missing file → None, cache cleared
CAMP_MISSING = 9202
check('file: missing → None', parse_skeleton_file(CAMP_MISSING), None)


# ─── apply_skeleton: happy path ───────────────────────────────────────────────
CAMP_APPLY = 9210
write_skel(CAMP_APPLY, SKEL_FULL)
result = apply_skeleton(CAMP_APPLY)

check('apply: status ok',                result['status'],            'ok')
check('apply: locations_written',        result['locations_written'], 2)
check('apply: npcs_written',             result['npcs_written'],      2)
check('apply: parent_resolutions',       result['parent_resolutions'], 1)
check('apply: location_resolutions',     result['location_resolutions'], 2)
check('apply: unresolved parents',       result['unresolved_parents'], [])
check('apply: unresolved npc_locations', result['unresolved_npc_locations'], [])

# DB contents
red = location_get_by_name(CAMP_APPLY, 'Redhaven')
check_truthy('db: Redhaven exists',        red is not None)
check('db: Redhaven skeleton_origin',      red['skeleton_origin'], 1)
check('db: Redhaven type',                 red['type'], 'town')

inn = location_get_by_name(CAMP_APPLY, 'Rusty Anchor')  # article stripped on canonicalize
check_truthy('db: Rusty Anchor exists',    inn is not None)
check('db: Rusty Anchor parent set',       inn['parent_location_id'], red['id'])
check('db: Rusty Anchor skeleton_origin',  inn['skeleton_origin'], 1)

garrick = npc_get_by_name(CAMP_APPLY, 'Garrick')
check_truthy('db: Garrick exists',         garrick is not None)
check('db: Garrick role',                  garrick['role'],            'blacksmith')
check('db: Garrick location_id',           garrick['location_id'],     red['id'])
check('db: Garrick skeleton_origin',       garrick['skeleton_origin'], 1)


# ─── apply_skeleton: idempotence ──────────────────────────────────────────────
result2 = apply_skeleton(CAMP_APPLY)
check('idempotent: status ok',             result2['status'],            'ok')
check('idempotent: same locations count',
      len(location_list(CAMP_APPLY)), 2)
check('idempotent: same npcs count',
      len([n for n in npc_list(CAMP_APPLY) if n['canonical_name'] in ('Garrick', 'Mira')]),
      2)
# Mention counts should NOT have bumped — skeleton reload doesn't count as a mention.
garrick_after = npc_get_by_name(CAMP_APPLY, 'Garrick')
check('idempotent: Garrick mention_count unchanged',
      garrick_after['mention_count'], 1)


# ─── apply_skeleton: authority — parser cannot overwrite skeleton fields ──────
# Simulate a parser hit AFTER skeleton load: should bump mention_count only,
# not touch role/location.
npc_upsert(CAMP_APPLY, 'Garrick', role='different_role', location_id=999,
           description='changed', skeleton_origin=False)
g = npc_get_by_name(CAMP_APPLY, 'Garrick')
check('authority: role unchanged after parser hit',
      g['role'], 'blacksmith')
check('authority: location unchanged after parser hit',
      g['location_id'], red['id'])
check('authority: still skeleton_origin',
      g['skeleton_origin'], 1)
check('authority: mention_count bumped',
      g['mention_count'], 2)


# ─── apply_skeleton: missing file ─────────────────────────────────────────────
CAMP_NO_FILE = 9211
result_missing = apply_skeleton(CAMP_NO_FILE)
check('missing: status', result_missing['status'], 'no_file')
check('missing: nothing written', result_missing['locations_written'], 0)


# ─── apply_skeleton: parse error ──────────────────────────────────────────────
CAMP_BAD = 9212
write_skel(CAMP_BAD, "### Orphan (no section)\n")
result_bad = apply_skeleton(CAMP_BAD)
check('parse_error: status',           result_bad['status'], 'parse_error')
check_truthy('parse_error: error msg', result_bad['error'])
check('parse_error: nothing written',  result_bad['locations_written'], 0)
check('parse_error: nothing written2', result_bad['npcs_written'], 0)


# ─── apply_skeleton: unresolved parent / npc location ─────────────────────────
CAMP_UNRES = 9213
write_skel(CAMP_UNRES, """\
# Campaign: Unres

## Primary NPCs
### Floater (rogue, Nowhere)
A wandering rogue.

## Key locations
### Branch (district, Trunk)
A district that references a non-existent parent.
""")
result_unres = apply_skeleton(CAMP_UNRES)
check('unres: still ok status',         result_unres['status'], 'ok')
check_truthy('unres: location written', result_unres['locations_written'] >= 1)
check_truthy('unres: npc written',      result_unres['npcs_written'] >= 1)
check_truthy('unres: parent unresolved logged',
             len(result_unres['unresolved_parents']) >= 1)
check_truthy('unres: npc location unresolved logged',
             len(result_unres['unresolved_npc_locations']) >= 1)
floater = npc_get_by_name(CAMP_UNRES, 'Floater')
check('unres: floater location_id None', floater['location_id'], None)


# ─── get_skeleton_prompt_block ────────────────────────────────────────────────
CAMP_BLOCK = 9220
write_skel(CAMP_BLOCK, SKEL_FULL)
block = get_skeleton_prompt_block(CAMP_BLOCK)
check_truthy('block: returned non-empty', len(block) > 0)
check_truthy('block: contains title',     'Test Campaign' in block)
check_truthy('block: contains npc',       'Garrick' in block)
check_truthy('block: contains location',  'Redhaven' in block)
check_truthy('block: contains hook',      'Find the missing brother' in block)
check_truthy('block: contains framing',   'authored canon' in block.lower())
check_truthy('block: contains directive', 'do not contradict' in block.lower())

# Truncation
block_short = get_skeleton_prompt_block(CAMP_BLOCK, max_chars=300)
check_truthy('block: truncated', len(block_short) <= 380)
check_truthy('block: truncation marker',
             'truncated' in block_short.lower())

# Missing file → empty string
check('block: missing file', get_skeleton_prompt_block(9999), '')


# ─── Cleanup + summary ────────────────────────────────────────────────────────
import shutil
try:
    os.unlink(TEST_DB)
except OSError:
    pass
try:
    shutil.rmtree(SKEL_ROOT)
except OSError:
    pass

print(f"\n{PASS} passed, {FAIL} failed")
if FAILURES:
    print("\nFAILURES:")
    for f in FAILURES:
        print(f)
    sys.exit(1)
sys.exit(0)
