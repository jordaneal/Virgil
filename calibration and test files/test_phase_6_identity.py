"""Phase 6 — Actor identity reconciliation tests.

Covers:
  - canonicalize_actor_name (pure function, no DB)
  - get_character_by_canonical / get_character_by_alias (engine, DB)
  - set_character_canonical_name / append_character_alias (engine writes)
  - resolve_actor (orchestration, strict-only)
  - register_actor_alias (orchestration write path)
  - refresh_canonical_name (orchestration write path)
  - RollBuffer.consume / .recent — strict-equality matching (avrae_listener)

Spec: PHASE_6_IDENTITY_SPEC.md (Session 15, locked strict-only resolution).

No network. Uses tempfile DB.

Run: python3 test_phase_6_identity.py
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

import dnd_engine                # noqa: E402
dnd_engine.DB_PATH = TEST_DB
dnd_engine.log = lambda m: None

dnd_engine.db_init()

from dnd_engine import (         # noqa: E402
    canonicalize_actor_name,
    create_campaign, bind_character,
    get_character_by_canonical, get_character_by_alias,
    set_character_canonical_name, append_character_alias,
)

import dnd_orchestration as orch   # noqa: E402
orch.log = lambda m: None  # silence orchestration logs in tests


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


# ──────────────────────────────────────────────────────────────────────────────
# canonicalize_actor_name — pure function
# ──────────────────────────────────────────────────────────────────────────────

# Plain forms
check('canon_actor: plain',           canonicalize_actor_name('Donovan Ruby'), 'donovan ruby')
check('canon_actor: already lower',   canonicalize_actor_name('donovan ruby'), 'donovan ruby')
check('canon_actor: uppercase',       canonicalize_actor_name('DONOVAN RUBY'), 'donovan ruby')

# Whitespace handling
check('canon_actor: leading ws',      canonicalize_actor_name('  Donovan'), 'donovan')
check('canon_actor: trailing ws',     canonicalize_actor_name('Donovan  '), 'donovan')
check('canon_actor: internal ws run', canonicalize_actor_name('Donovan   Ruby'), 'donovan ruby')
check('canon_actor: tabs+nl',         canonicalize_actor_name('\tDonovan\nRuby\t'), 'donovan ruby')
check('canon_actor: ws only',         canonicalize_actor_name('   '), '')

# Empty / None
check('canon_actor: empty',           canonicalize_actor_name(''), '')
check('canon_actor: None',            canonicalize_actor_name(None), '')

# Curly quotes folded
check('canon_actor: curly apos',      canonicalize_actor_name("O’Connell"), "o'connell")
check('canon_actor: curly quotes',    canonicalize_actor_name("“Donovan”"), '"donovan"')

# Honorifics PRESERVED (no stripping)
check('canon_actor: keeps Sir',       canonicalize_actor_name('Sir Aldric'), 'sir aldric')
check('canon_actor: keeps Lady',      canonicalize_actor_name('Lady Vex'), 'lady vex')

# Idempotent
once = canonicalize_actor_name('  DonovanRuby  ')
twice = canonicalize_actor_name(once)
check('canon_actor: idempotent', once, twice)

# Punctuation preserved
check('canon_actor: hyphen',          canonicalize_actor_name('Don-O-Van'), 'don-o-van')
check('canon_actor: apostrophe',      canonicalize_actor_name("O'Connell"), "o'connell")


# ──────────────────────────────────────────────────────────────────────────────
# Schema migration — new columns + backfill
# ──────────────────────────────────────────────────────────────────────────────

# A character bound BEFORE schema migration would have canonical_name backfilled
# from the lowercased name. Test the migration logic by binding fresh and
# verifying the column behavior.
P6_GUILD = 'test-guild-phase-6'
CAMP = create_campaign(P6_GUILD, 'Phase 6 Test')
check_truthy('schema: campaign created', CAMP)

# Bind a character — the existing bind_character does not yet populate canonical
# (Phase 6 wires it in a follow-up patch). After bind, canonical_name should
# be backfilled to lower(name) by db_init's migration logic running the next
# time db_init runs. For this test, we'll explicitly set canonical_name via
# the engine helper to simulate the backfill.
CONTROLLER_A = '111111111111111111'
char_a_id = bind_character(CAMP, CONTROLLER_A, 'Donovan Ruby',
                           race='Dwarf', char_class='Rogue', level=1)
check_truthy('bind: returns id', char_a_id)

# Manually backfill canonical_name (mirrors what db_init does on existing rows)
set_character_canonical_name(char_a_id, 'donovan ruby')

# Verify lookup by canonical
got = get_character_by_canonical(CAMP, 'donovan ruby')
check_truthy('by_canonical: hit', got is not None)
if got:
    check('by_canonical: name preserved', got['name'], 'Donovan Ruby')
    check('by_canonical: canonical match', got['canonical_name'], 'donovan ruby')
    check('by_canonical: aliases empty list', got['aliases'], [])
    check('by_canonical: controller', got['controller'], CONTROLLER_A)

# Wrong canonical → miss
check('by_canonical: miss returns None',
      get_character_by_canonical(CAMP, 'aldric'), None)

# Empty canonical → None
check('by_canonical: empty returns None',
      get_character_by_canonical(CAMP, ''), None)

# Append alias and look up by alias
appended = append_character_alias(char_a_id, 'throx')
check('append_alias: first time True', appended, True)

got_by_alias = get_character_by_alias(CAMP, 'throx')
check_truthy('by_alias: hit', got_by_alias is not None)
if got_by_alias:
    check('by_alias: same character', got_by_alias['id'], char_a_id)
    check('by_alias: aliases list', got_by_alias['aliases'], ['throx'])

# Idempotent alias — same string twice returns False
check('append_alias: idempotent', append_character_alias(char_a_id, 'throx'), False)

# Add a second alias
append_character_alias(char_a_id, 'donovan')
got_check = get_character_by_canonical(CAMP, 'donovan ruby')
if got_check:
    check('aliases: both stored',
          sorted(got_check['aliases']), ['donovan', 'throx'])

# Lookup by second alias
got_donovan = get_character_by_alias(CAMP, 'donovan')
check_truthy('by_alias: second alias hit', got_donovan is not None)


# ──────────────────────────────────────────────────────────────────────────────
# Strict-only — multiple matches return None (ambiguous)
# ──────────────────────────────────────────────────────────────────────────────

# Two characters with same canonical_name in same campaign: ambiguous → None
CONTROLLER_B = '222222222222222222'
char_b_id = bind_character(CAMP, CONTROLLER_B, 'Donovan Ruby II',  # different bind name
                           race='Halfling', char_class='Bard', level=1)
set_character_canonical_name(char_b_id, 'donovan ruby')  # collision

# Both rows have canonical_name='donovan ruby' → resolve must return None
ambiguous = get_character_by_canonical(CAMP, 'donovan ruby')
check('ambiguous: returns None on multiple matches', ambiguous, None)

# Restore distinct canonical for char_b before continuing
set_character_canonical_name(char_b_id, 'donovan ruby ii')


# ──────────────────────────────────────────────────────────────────────────────
# resolve_actor — orchestration strict-only
# ──────────────────────────────────────────────────────────────────────────────

# Hits canonical_name
r = orch.resolve_actor(CAMP, 'Donovan Ruby')
check_truthy('resolve: canonical hit', r is not None)
if r:
    check('resolve: canonical match returns row', r['id'], char_a_id)

# Hits alias
r = orch.resolve_actor(CAMP, 'Throx')   # uppercase input — canonicalized down
check_truthy('resolve: alias hit (case-insensitive)', r is not None)
if r:
    check('resolve: alias maps to right character', r['id'], char_a_id)

# Miss returns None — no substring fallback
r = orch.resolve_actor(CAMP, 'Aldric')
check('resolve: miss returns None', r, None)

# Substring-but-not-equal returns None (the bug we explicitly fix)
r = orch.resolve_actor(CAMP, 'Donovan')
# 'donovan' is in aliases, so this DOES hit (alias match).
check_truthy("resolve: 'Donovan' alias-hit", r is not None)

# Substring that is NOT a registered alias must NOT match
r = orch.resolve_actor(CAMP, 'Donovan Ruby Junior')   # superstring of canonical
check('resolve: superstring of canonical = no match', r, None)

# Empty input
check('resolve: empty input None', orch.resolve_actor(CAMP, ''), None)
check('resolve: None input None',  orch.resolve_actor(CAMP, None), None)


# ──────────────────────────────────────────────────────────────────────────────
# register_actor_alias — orchestration write
# ──────────────────────────────────────────────────────────────────────────────

# Successful registration (new alias)
result = orch.register_actor_alias(CAMP, CONTROLLER_A, 'TheBlade')
check('register_alias: new alias True', result, True)

# Verify it's stored canonicalized
r = get_character_by_alias(CAMP, 'theblade')
check_truthy('register_alias: alias resolves', r is not None)

# Idempotent
check('register_alias: dup False',
      orch.register_actor_alias(CAMP, CONTROLLER_A, 'TheBlade'), False)
check('register_alias: dup case-folded False',
      orch.register_actor_alias(CAMP, CONTROLLER_A, 'theblade'), False)

# No bound character → False
check('register_alias: missing controller False',
      orch.register_actor_alias(CAMP, '999999999999999999', 'someone'),
      False)


# ──────────────────────────────────────────────────────────────────────────────
# refresh_canonical_name — preserves old as alias when value changes
# ──────────────────────────────────────────────────────────────────────────────

# Bind a fresh character to test refresh in isolation
CONTROLLER_C = '333333333333333333'
char_c_id = bind_character(CAMP, CONTROLLER_C, 'Aldric',
                           race='Human', char_class='Fighter', level=1)
set_character_canonical_name(char_c_id, 'aldric')

# Refresh to the SAME value → no-op (no alias added)
orch.refresh_canonical_name(CONTROLLER_C, 'Aldric', CAMP)
got = get_character_by_canonical(CAMP, 'aldric')
check('refresh: no-op same canonical', got['aliases'] if got else None, [])

# Refresh to DIFFERENT value → old becomes alias, new is canonical
orch.refresh_canonical_name(CONTROLLER_C, 'Lord Aldric', CAMP)
got = get_character_by_canonical(CAMP, 'lord aldric')
check_truthy('refresh: new canonical applied', got is not None)
if got:
    check('refresh: old appended to aliases', got['aliases'], ['aldric'])

# Old canonical is no longer the canonical lookup
check('refresh: old canonical no longer matches',
      get_character_by_canonical(CAMP, 'aldric'), None)
# But old IS findable via alias
check_truthy('refresh: old still findable via alias',
             get_character_by_alias(CAMP, 'aldric') is not None)


# ──────────────────────────────────────────────────────────────────────────────
# RollBuffer — strict equality on canonicalized strings
# ──────────────────────────────────────────────────────────────────────────────

from avrae_listener import RollBuffer  # noqa: E402

buf = RollBuffer(ttl_seconds=300, max_per_guild=50)

# Add events with canonicalized actor strings (post-Phase-6, that's what
# discord_dnd_bot.on_message stores — canonicalized at buffer.add time).
buf.add({'guild_id': 1, 'actor': 'donovan ruby', 'kind': 'attack',
         'detail': 'shortsword', 'result': 17, 'nat': 12, 'damage': 6,
         'crit': False, 'channel_id': 1, 'ts': 9999999999})
buf.add({'guild_id': 1, 'actor': 'aldric', 'kind': 'check',
         'detail': 'perception', 'result': 14, 'nat': 9, 'damage': None,
         'crit': False, 'channel_id': 1, 'ts': 9999999999})

# Exact match returns one event
got = buf.recent(1, ['donovan ruby'])
check('buffer: exact match returns 1', len(got), 1)
if got:
    check('buffer: right actor', got[0]['actor'], 'donovan ruby')

# No match — superstring of canonical
got = buf.recent(1, ['donovan ruby junior'])
check('buffer: superstring no match', len(got), 0)

# No match — substring (the OLD bug; strict-only correctly returns 0)
got = buf.recent(1, ['donovan'])
check('buffer: substring no match (strict)', len(got), 0)

# Multi-actor filter
got = buf.recent(1, ['donovan ruby', 'aldric'])
check('buffer: multi-actor filter', len(got), 2)

# Case-folding in the matcher (filter strings get lowered)
got = buf.recent(1, ['Donovan Ruby'])
check('buffer: case-folded filter', len(got), 1)

# Consume removes matched events
got = buf.consume(1, ['donovan ruby'])
check('buffer: consume returns matched', len(got), 1)
got_after = buf.recent(1, None)
check('buffer: consumed event removed', len(got_after), 1)
if got_after:
    check('buffer: aldric event remains', got_after[0]['actor'], 'aldric')

# Empty actor on event — kept by recent (don't drop unknowns)
buf.add({'guild_id': 2, 'actor': '', 'kind': 'roll', 'detail': '', 'result': 5,
         'nat': 5, 'damage': None, 'crit': False, 'channel_id': 1, 'ts': 9999999999})
got = buf.recent(2, ['someone'])
check('buffer: empty-actor event preserved', len(got), 1)


# ──────────────────────────────────────────────────────────────────────────────
# Cleanup
# ──────────────────────────────────────────────────────────────────────────────
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
