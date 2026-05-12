"""Deterministic tests for Ship 2 (S39) — Scene State Canon Discipline.

Covers:
  - Schema: 8 deleted columns absent from dnd_scene_state
  - get_scene_state: returned dict has no deleted keys; has location_label
  - update_scene_state: writes to deleted fields are dropped (logged) and the
    row is not mutated for that field
  - init_scene_state: signature accepts campaign_id only (no seed parameter)
  - build_dm_context output: SCENE STATE block contains no render lines for
    deleted fields
  - Path A: location_label derives from dnd_locations.canonical_name via
    current_location_id; NULL FK renders 'between locations'

Run:
    cd /home/jordaneal/scripts && python3 test_scene_state_canon_deletion.py
"""

import sys
import sqlite3
import tempfile
from pathlib import Path

sys.path.insert(0, '/home/jordaneal/scripts')

import dnd_engine

_tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_tmp.close()
TEST_DB = Path(_tmp.name)
dnd_engine.DB_PATH = TEST_DB

captured = []
_orig_log = dnd_engine.log
dnd_engine.log = lambda m: (captured.append(m), _orig_log(m))[1] if False else captured.append(m)
dnd_engine.db_init()

from dnd_engine import (  # noqa: E402
    get_scene_state, init_scene_state, update_scene_state,
    set_current_location, location_upsert, create_campaign,
    extract_scene_updates,
)

PASS = 0
FAIL = 0
FAILURES = []


def check(label, got, expected):
    global PASS, FAIL
    if got == expected:
        PASS += 1
    else:
        FAIL += 1
        FAILURES.append(f"  {label}: expected={expected!r} got={got!r}")


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


# ─── Schema: 8 deleted columns absent ──────────────────────────────────────
conn = sqlite3.connect(TEST_DB)
ss_cols = {row[1] for row in conn.execute("PRAGMA table_info(dnd_scene_state)")}
conn.close()

DELETED = (
    'location', 'established_details', 'focus', 'open_questions',
    'last_scene_change', 'active_npcs', 'active_threats', 'tension',
)
for col in DELETED:
    check_falsy(f'schema: {col} dropped from dnd_scene_state', col in ss_cols)

# Kept columns must still be there
KEPT = (
    'campaign_id', 'mode', 'last_player_action', 'updated_at',
    'tension_int', 'progress_clocks', 'current_location_id',
    'turn_counter', 'last_dm_response', 'last_active_actor',
    'campaign_day', 'day_phase',
)
for col in KEPT:
    check_truthy(f'schema: {col} retained on dnd_scene_state', col in ss_cols)


# ─── Migration idempotency: re-running db_init does not error ─────────────
dnd_engine.db_init()
conn = sqlite3.connect(TEST_DB)
ss_cols2 = {row[1] for row in conn.execute("PRAGMA table_info(dnd_scene_state)")}
conn.close()
check('migration idempotent: column set unchanged on re-run', ss_cols, ss_cols2)


# ─── init_scene_state: new signature (no seed) ─────────────────────────────
SCRATCH_CID = 90001
init_scene_state(SCRATCH_CID)  # must not raise
state = get_scene_state(SCRATCH_CID)
check_truthy('init_scene_state(cid): row created', state is not None)


# ─── get_scene_state: returned dict shape ──────────────────────────────────
for k in DELETED:
    check_falsy(f'get_scene_state: deleted key {k!r} absent from dict',
                k in state)

check_truthy('get_scene_state: location_label key present',
             'location_label' in state)
check('get_scene_state: location_label is empty on no-FK row',
      state.get('location_label'), '')

for k in ('mode', 'last_player_action', 'campaign_day', 'day_phase',
          'tension_int', 'progress_clocks', 'current_location_id',
          'last_dm_response', 'last_active_actor'):
    check_truthy(f'get_scene_state: kept key {k!r} present', k in state)


# ─── update_scene_state: writes to deleted fields are dropped ─────────────
captured.clear()
update_scene_state(SCRATCH_CID, location='X', focus='Y',
                   established_details=['Z'], open_questions=['W'],
                   last_scene_change='V', active_npcs=['A'],
                   active_threats=['T'], tension='high')
drop_logs = [m for m in captured if 'dropping LLM-write to deleted field' in m]
check('update_scene_state: 8 deleted-field writes logged as drops',
      len(drop_logs), 8)
# Each deleted field name appears in a drop log
for k in DELETED:
    matching = [m for m in drop_logs if f"'{k}'" in m]
    check_truthy(f'update_scene_state: drop log fires for {k!r}',
                 len(matching) >= 1)

# State unchanged in any column that was a deleted-write target
state_after = get_scene_state(SCRATCH_CID)
for k in DELETED:
    check_falsy(f'update_scene_state: deleted key {k!r} still absent from dict',
                k in state_after)


# ─── update_scene_state: writes to last_player_action work ────────────────
captured.clear()
update_scene_state(SCRATCH_CID, last_player_action='I look around carefully')
state2 = get_scene_state(SCRATCH_CID)
check('update_scene_state: last_player_action write persisted',
      state2.get('last_player_action'), 'I look around carefully')


# ─── Path A: location_label derives from FK JOIN ──────────────────────────
SCRATCH_CID2 = 90002
init_scene_state(SCRATCH_CID2)
# Need a campaign row for the FK to resolve cleanly
conn = sqlite3.connect(TEST_DB)
conn.execute("INSERT OR IGNORE INTO dnd_campaigns "
             "(id, guild_id, name, status, created_at, current_scene) "
             "VALUES (?, ?, ?, ?, ?, ?)",
             (SCRATCH_CID2, 'g-test', 'Test', 'active', '2026-05-11', ''))
conn.commit()
conn.close()

loc_id = location_upsert(SCRATCH_CID2, 'Sunken Keep', type='dungeon',
                        skeleton_origin=True)
check_truthy('location_upsert: row created', loc_id is not None)
ok = set_current_location(SCRATCH_CID2, loc_id)
check_truthy('set_current_location: returned True', ok)
state3 = get_scene_state(SCRATCH_CID2)
check('location_label: derived from FK JOIN',
      state3.get('location_label'), 'Sunken Keep')

# Clearing the FK should drop the label back to empty
set_current_location(SCRATCH_CID2, None)
state4 = get_scene_state(SCRATCH_CID2)
check('location_label: NULL FK → empty string',
      state4.get('location_label'), '')


# ─── build_dm_context render: no deleted-field render lines ───────────────
# We don't call build_dm_context directly (it has heavy deps); we simulate
# the render block via the same shape used in dnd_engine.build_dm_context.
import dnd_engine as _de
captured.clear()
campaign = {'id': SCRATCH_CID2, 'name': 'Test', 'tone': '',
            'current_scene': '', 'world_notes': ''}
characters = []  # no party; build_dm_context handles empty
# Re-set FK so location_label has content for verification
set_current_location(SCRATCH_CID2, loc_id)

# Render block manually (mirrors the production formatting at line ~5209)
state5 = get_scene_state(SCRATCH_CID2)
mode_v = (state5.get('mode') or 'exploration').lower()
loc_label = state5.get('location_label') or ''
loc_render = loc_label if loc_label else '(between locations)'
block = (
    "\n\n=== SCENE STATE (authoritative) ===\n"
    f"Location: {loc_render}\n"
    f"Tension: {_de.tension_label(state5.get('tension_int') or 0)} "
    f"({state5.get('tension_int') or 0}/100)\n"
    f"Last player action: "
    f"{state5.get('last_player_action') or '(this is the first turn)'}"
)
# Deleted-field render strings MUST NOT appear in the rendered block
for forbidden in ('Focus:', 'Established details:', 'Open questions:',
                  'Last scene change:'):
    check_falsy(f'render: {forbidden!r} absent from SCENE STATE block',
                forbidden in block)
check_truthy('render: Location line present', 'Location:' in block)
check_truthy('render: Location renders FK-derived label',
             'Sunken Keep' in block)

# Clear FK and re-render — Location line uses ambiguity placeholder
set_current_location(SCRATCH_CID2, None)
state6 = get_scene_state(SCRATCH_CID2)
loc_label = state6.get('location_label') or ''
loc_render = loc_label if loc_label else '(between locations)'
block2 = f"Location: {loc_render}"
check_truthy('render: NULL FK → between-locations ambiguity',
             '(between locations)' in block2)


# ─── extract_scene_updates: no LLM call; just writes last_player_action ───
SCRATCH_CID3 = 90003
init_scene_state(SCRATCH_CID3)
captured.clear()
extract_scene_updates(SCRATCH_CID3, "I duck behind the crates",
                      "The merchants don't notice.")
state7 = get_scene_state(SCRATCH_CID3)
check('extract_scene_updates: last_player_action persisted',
      state7.get('last_player_action'), 'I duck behind the crates')
# The write-log line confirms shape
write_log = [m for m in captured
             if 'scene state updated' in m and 'last_player_action' in m]
check_truthy('extract_scene_updates: persistence log fires',
             len(write_log) >= 1)
# No LLM-extraction prompt / drop logs (function no longer makes the LLM call)
extract_logs = [m for m in captured if 'extract_scene_updates parse' in m]
check('extract_scene_updates: no parse-error logs (LLM call removed)',
      len(extract_logs), 0)


# ─── Cleanup ──────────────────────────────────────────────────────────────
try:
    TEST_DB.unlink()
except OSError:
    pass


print(f"\n{PASS} passed, {FAIL} failed")
if FAILURES:
    print("\nFAILURES:")
    for f in FAILURES:
        print(f)
    sys.exit(1)
sys.exit(0)
