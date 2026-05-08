"""Deterministic tests for dnd_combatant_state schema + helpers (Session 21).

Combat Persistence Directive v1 — per-combatant snapshot table fed by the
!init list parser. Single-writer invariant: only update_combatants_from_init_list
and clear_combatants write here.

Run:
    cd /home/jordaneal/scripts && python3 test_combatant_state.py
"""

import sys
import sqlite3
import tempfile
import time
from pathlib import Path

sys.path.insert(0, '/home/jordaneal/scripts')

import dnd_engine
_tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_tmp.close()
TEST_DB = Path(_tmp.name)
dnd_engine.DB_PATH = TEST_DB

captured = []
dnd_engine.log = lambda m: captured.append(m)
dnd_engine.db_init()

from dnd_engine import (
    update_combatants_from_init_list,
    clear_combatants,
    get_combatants,
)


# ─── Schema ─────────────────────────────────────────────────────────

def test_table_exists_with_expected_columns():
    conn = sqlite3.connect(TEST_DB)
    cols = conn.execute("PRAGMA table_info(dnd_combatant_state)").fetchall()
    conn.close()
    names = [c[1] for c in cols]
    assert names == [
        'campaign_id', 'name', 'init', 'hp_current', 'hp_max',
        'conditions', 'alive', 'side', 'updated_at'
    ], f"unexpected columns: {names}"


def test_primary_key_is_composite():
    conn = sqlite3.connect(TEST_DB)
    cols = conn.execute("PRAGMA table_info(dnd_combatant_state)").fetchall()
    conn.close()
    pk_cols = sorted(c[1] for c in cols if c[5] > 0)
    assert pk_cols == ['campaign_id', 'name'], (
        f"PK should be (campaign_id, name); got {pk_cols}"
    )


def test_index_on_campaign_id_exists():
    conn = sqlite3.connect(TEST_DB)
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' "
        "AND tbl_name='dnd_combatant_state'"
    ).fetchall()
    conn.close()
    names = [r[0] for r in rows]
    assert any('combatant_campaign' in n for n in names), (
        f"expected campaign-id index; got {names}"
    )


# ─── update_combatants_from_init_list ───────────────────────────────

def _parsed(combatants):
    return {'round': 1, 'current_init': 25, 'combatants': combatants}


def test_insert_basic_three_rows():
    clear_combatants(1)
    n = update_combatants_from_init_list(1, _parsed([
        {'init': 29, 'name': 'Garrick', 'active': False, 'hp_current': None,
         'hp_max': None, 'conditions': '', 'alive': 1},
        {'init': 25, 'name': 'throx', 'active': True, 'hp_current': 22,
         'hp_max': 22, 'conditions': 'Frightened', 'alive': 1},
        {'init': 13, 'name': 'Donovan', 'active': False, 'hp_current': 0,
         'hp_max': None, 'conditions': '', 'alive': 0},
    ]))
    assert n == 3
    snap = get_combatants(1)
    rows = snap['combatants']
    assert len(rows) == 3
    # Ordered by init DESC
    assert [r['name'] for r in rows] == ['Garrick', 'throx', 'Donovan']
    assert rows[1]['hp_current'] == 22 and rows[1]['hp_max'] == 22
    assert rows[1]['conditions'] == 'Frightened'
    assert rows[2]['alive'] == 0


def test_replace_in_place_drops_prior_rows():
    clear_combatants(2)
    update_combatants_from_init_list(2, _parsed([
        {'init': 30, 'name': 'A', 'active': False, 'hp_current': None,
         'hp_max': None, 'conditions': '', 'alive': 1},
        {'init': 20, 'name': 'B', 'active': False, 'hp_current': None,
         'hp_max': None, 'conditions': '', 'alive': 1},
    ]))
    update_combatants_from_init_list(2, _parsed([
        {'init': 25, 'name': 'C', 'active': True, 'hp_current': 10,
         'hp_max': 20, 'conditions': '', 'alive': 1},
    ]))
    snap = get_combatants(2)
    names = [r['name'] for r in snap['combatants']]
    assert names == ['C'], f"replace should drop A,B; got {names}"


def test_empty_combatants_writes_nothing():
    clear_combatants(3)
    n = update_combatants_from_init_list(3, _parsed([]))
    assert n == 0
    snap = get_combatants(3)
    assert snap['combatants'] == [] and snap['snapshot_age_s'] is None


def test_skips_blank_name_rows():
    clear_combatants(4)
    n = update_combatants_from_init_list(4, _parsed([
        {'init': 29, 'name': 'Real', 'active': False, 'hp_current': None,
         'hp_max': None, 'conditions': '', 'alive': 1},
        {'init': 25, 'name': '', 'active': False, 'hp_current': None,
         'hp_max': None, 'conditions': '', 'alive': 1},
        {'init': 13, 'name': '   ', 'active': False, 'hp_current': None,
         'hp_max': None, 'conditions': '', 'alive': 1},
    ]))
    assert n == 1
    snap = get_combatants(4)
    assert [r['name'] for r in snap['combatants']] == ['Real']


def test_cross_campaign_isolation():
    clear_combatants(5)
    clear_combatants(6)
    update_combatants_from_init_list(5, _parsed([
        {'init': 30, 'name': 'A5', 'active': False, 'hp_current': None,
         'hp_max': None, 'conditions': '', 'alive': 1},
    ]))
    update_combatants_from_init_list(6, _parsed([
        {'init': 30, 'name': 'A6', 'active': False, 'hp_current': None,
         'hp_max': None, 'conditions': '', 'alive': 1},
    ]))
    snap5 = get_combatants(5)
    snap6 = get_combatants(6)
    assert [r['name'] for r in snap5['combatants']] == ['A5']
    assert [r['name'] for r in snap6['combatants']] == ['A6']


# ─── clear_combatants ───────────────────────────────────────────────

def test_clear_drops_only_target_campaign():
    clear_combatants(7)
    clear_combatants(8)
    update_combatants_from_init_list(7, _parsed([
        {'init': 30, 'name': 'X', 'active': False, 'hp_current': None,
         'hp_max': None, 'conditions': '', 'alive': 1},
    ]))
    update_combatants_from_init_list(8, _parsed([
        {'init': 30, 'name': 'Y', 'active': False, 'hp_current': None,
         'hp_max': None, 'conditions': '', 'alive': 1},
    ]))
    clear_combatants(7)
    assert get_combatants(7)['combatants'] == []
    assert [r['name'] for r in get_combatants(8)['combatants']] == ['Y']


def test_clear_when_empty_is_idempotent():
    clear_combatants(9)
    clear_combatants(9)  # no error
    assert get_combatants(9)['combatants'] == []


# ─── get_combatants ─────────────────────────────────────────────────

def test_get_returns_empty_shape_when_none():
    clear_combatants(10)
    snap = get_combatants(10)
    assert snap == {'combatants': [], 'snapshot_age_s': None}


def test_snapshot_age_is_recent_after_write():
    clear_combatants(11)
    update_combatants_from_init_list(11, _parsed([
        {'init': 25, 'name': 'X', 'active': False, 'hp_current': None,
         'hp_max': None, 'conditions': '', 'alive': 1},
    ]))
    snap = get_combatants(11)
    assert snap['snapshot_age_s'] is not None
    assert 0 <= snap['snapshot_age_s'] < 5  # under 5s after a sync write


def test_snapshot_age_grows_over_time():
    clear_combatants(12)
    update_combatants_from_init_list(12, _parsed([
        {'init': 25, 'name': 'X', 'active': False, 'hp_current': None,
         'hp_max': None, 'conditions': '', 'alive': 1},
    ]))
    time.sleep(1.1)
    snap = get_combatants(12)
    assert snap['snapshot_age_s'] >= 1.0


def test_ordering_init_desc_then_name_asc_for_ties():
    clear_combatants(13)
    update_combatants_from_init_list(13, _parsed([
        {'init': 20, 'name': 'Charlie', 'active': False, 'hp_current': None,
         'hp_max': None, 'conditions': '', 'alive': 1},
        {'init': 20, 'name': 'Alice', 'active': False, 'hp_current': None,
         'hp_max': None, 'conditions': '', 'alive': 1},
        {'init': 25, 'name': 'Bob', 'active': False, 'hp_current': None,
         'hp_max': None, 'conditions': '', 'alive': 1},
    ]))
    snap = get_combatants(13)
    assert [r['name'] for r in snap['combatants']] == ['Bob', 'Alice', 'Charlie']


# ─── Telemetry ──────────────────────────────────────────────────────

def test_log_lines_emit_on_write_and_clear():
    captured.clear()
    clear_combatants(14)
    update_combatants_from_init_list(14, _parsed([
        {'init': 25, 'name': 'X', 'active': False, 'hp_current': None,
         'hp_max': None, 'conditions': '', 'alive': 1},
    ]))
    clear_combatants(14)
    text = "\n".join(captured)
    assert 'update_combatants_from_init_list: campaign=14 rows=1' in text
    assert 'clear_combatants: campaign=14' in text


# ─── Run ────────────────────────────────────────────────────────────

if __name__ == '__main__':
    failures = []
    funcs = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for fn in funcs:
        try:
            fn()
            print(f"  ok   {fn.__name__}")
        except AssertionError as e:
            failures.append((fn.__name__, str(e)))
            print(f"  FAIL {fn.__name__}: {e}")
        except Exception as e:
            failures.append((fn.__name__, repr(e)))
            print(f"  ERR  {fn.__name__}: {e!r}")
    if failures:
        print(f"\n{len(failures)} failure(s)")
        sys.exit(1)
    print(f"\n{len(funcs)} tests passed.")
