"""Deterministic tests for the dnd_loot_pending schema + writers
(Track 4 #2, Session 22).

Single-writer invariant: only enqueue_loot inserts; only mark_loot_surfaced
flips the surfaced flag. Queue read by get_pending_loot. Surface-and-clear
cycle is verified by test_loot_directive + test_loot_defeat_edge.

Run:
    cd /home/jordaneal/scripts && python3 test_loot_pending.py
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
    enqueue_loot,
    mark_loot_surfaced,
    get_pending_loot,
    enqueue_loot_for_defeats,
    _CAMPAIGN_SCOPED_TABLES,
)


# ─── Schema ─────────────────────────────────────────────────────────

def test_table_exists_with_expected_columns():
    conn = sqlite3.connect(TEST_DB)
    cols = conn.execute("PRAGMA table_info(dnd_loot_pending)").fetchall()
    conn.close()
    names = [c[1] for c in cols]
    assert names == [
        'id', 'campaign_id', 'creature', 'table_key',
        'coin_amount', 'coin_denom', 'items',
        'surfaced', 'surfaced_at', 'created_at',
    ], f"unexpected columns: {names}"


def test_index_on_campaign_surfaced_exists():
    conn = sqlite3.connect(TEST_DB)
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' "
        "AND tbl_name='dnd_loot_pending'"
    ).fetchall()
    conn.close()
    names = [r[0] for r in rows]
    assert any('loot_pending_lookup' in n for n in names), (
        f"expected (campaign_id, surfaced) lookup index; got {names}"
    )


def test_cascade_tuple_includes_dnd_loot_pending():
    assert 'dnd_loot_pending' in _CAMPAIGN_SCOPED_TABLES, (
        "Track 4 #2 — purge cascades MUST clear dnd_loot_pending or stale "
        "loot rows survive across campaigns."
    )


# ─── enqueue_loot ───────────────────────────────────────────────────

def test_enqueue_inserts_row_returns_id():
    res = enqueue_loot(
        campaign_id=1,
        creature='Goblin Patrol',
        table_key='goblin',
        coin={'amount': 5, 'denom': 'sp'},
        items=['rusty shortsword', 'crude bow'],
    )
    assert res['id'] is not None
    assert res['creature'] == 'Goblin Patrol'
    assert res['coin'] == {'amount': 5, 'denom': 'sp'}
    assert res['items'] == ['rusty shortsword', 'crude bow']


def test_enqueue_with_no_coin_stores_null_amount_and_denom():
    enqueue_loot(
        campaign_id=2,
        creature='Wolf',
        table_key='wolf',
        coin=None,
        items=['wolf pelt'],
    )
    rows = get_pending_loot(2)
    assert len(rows) == 1
    assert rows[0]['coin'] is None
    assert rows[0]['coin_amount'] is None
    assert rows[0]['coin_denom'] is None


def test_enqueue_refuses_empty_creature():
    res = enqueue_loot(
        campaign_id=3, creature='', table_key='goblin',
        coin=None, items=['x'],
    )
    assert res['id'] is None
    assert get_pending_loot(3) == []


def test_enqueue_log_line_format():
    captured.clear()
    enqueue_loot(
        campaign_id=4,
        creature='Skeleton',
        table_key='skeleton',
        coin={'amount': 3, 'denom': 'sp'},
        items=['bone fragments'],
    )
    text = "\n".join(captured)
    assert 'loot_generated:' in text
    assert "creature='Skeleton'" in text
    assert 'coin_amt=3' in text
    assert 'coin_denom=sp' in text
    assert 'items=1' in text


# ─── get_pending_loot ───────────────────────────────────────────────

def test_get_returns_only_unsurfaced_rows():
    # campaign 5 — two enqueues, mark one surfaced
    a = enqueue_loot(5, 'Goblin', 'goblin', {'amount': 2, 'denom': 'sp'}, ['x'])
    enqueue_loot(5, 'Wolf', 'wolf', None, ['wolf pelt'])
    mark_loot_surfaced(a['id'])
    rows = get_pending_loot(5)
    assert len(rows) == 1
    assert rows[0]['creature'] == 'Wolf'


def test_get_orders_by_created_at_then_id():
    enqueue_loot(6, 'A', 'goblin', None, ['x'])
    time.sleep(0.01)
    enqueue_loot(6, 'B', 'wolf', None, ['y'])
    rows = get_pending_loot(6)
    assert [r['creature'] for r in rows] == ['A', 'B']


def test_get_returns_empty_list_when_none():
    assert get_pending_loot(99) == []


def test_get_decodes_items_json_back_to_list():
    enqueue_loot(7, 'Cultist', 'cultist',
                 {'amount': 4, 'denom': 'gp'},
                 ['ritual dagger', 'dark robes', 'unholy symbol'])
    rows = get_pending_loot(7)
    assert rows[0]['items'] == ['ritual dagger', 'dark robes', 'unholy symbol']


# ─── mark_loot_surfaced ─────────────────────────────────────────────

def test_mark_surfaced_flips_flag_and_sets_timestamp():
    res = enqueue_loot(8, 'Bandit', 'bandit',
                       {'amount': 6, 'denom': 'sp'},
                       ['leather armor'])
    mark_loot_surfaced(res['id'])
    conn = sqlite3.connect(TEST_DB)
    row = conn.execute(
        "SELECT surfaced, surfaced_at FROM dnd_loot_pending WHERE id=?",
        (res['id'],)
    ).fetchone()
    conn.close()
    assert row[0] == 1
    assert row[1] is not None and row[1] != ''


def test_mark_surfaced_with_none_id_is_noop():
    # Enqueue then call mark with None — should not crash, not change anything.
    enqueue_loot(10, 'Goblin', 'goblin', None, ['x'])
    mark_loot_surfaced(None)  # type: ignore[arg-type]
    rows = get_pending_loot(10)
    assert len(rows) == 1


# ─── Cross-campaign isolation ───────────────────────────────────────

def test_cross_campaign_queries_isolate():
    enqueue_loot(20, 'A', 'goblin', None, ['x'])
    enqueue_loot(21, 'B', 'wolf', None, ['y'])
    a = get_pending_loot(20)
    b = get_pending_loot(21)
    assert [r['creature'] for r in a] == ['A']
    assert [r['creature'] for r in b] == ['B']


def test_mark_surfaced_does_not_leak_across_campaigns():
    a = enqueue_loot(22, 'A', 'goblin', None, ['x'])
    b = enqueue_loot(23, 'B', 'wolf', None, ['y'])
    mark_loot_surfaced(a['id'])
    assert get_pending_loot(22) == []
    assert len(get_pending_loot(23)) == 1


# ─── enqueue_loot_for_defeats ───────────────────────────────────────

def test_enqueue_loot_for_defeats_one_creature():
    captured.clear()
    n = enqueue_loot_for_defeats(30, ['Goblin'])
    assert n == 1
    rows = get_pending_loot(30)
    assert len(rows) == 1
    assert rows[0]['table_key'] == 'goblin'
    text = "\n".join(captured)
    assert 'defeat_parsed: campaign=30' in text
    assert "creature='Goblin'" in text
    assert 'loot_generated: campaign=30' in text


def test_enqueue_loot_for_defeats_multiple():
    n = enqueue_loot_for_defeats(31, ['Goblin', 'Wolf', 'unknown_thing'])
    assert n == 3
    rows = get_pending_loot(31)
    assert len(rows) == 3
    keys = [r['table_key'] for r in rows]
    assert keys == ['goblin', 'wolf', '_default']


def test_enqueue_loot_for_defeats_skips_empty_names():
    n = enqueue_loot_for_defeats(32, ['', '   ', 'Goblin'])
    assert n == 1
    assert len(get_pending_loot(32)) == 1


def test_enqueue_loot_for_defeats_empty_input_returns_zero():
    assert enqueue_loot_for_defeats(33, []) == 0
    assert get_pending_loot(33) == []


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
