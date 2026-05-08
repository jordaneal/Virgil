"""Deterministic tests for dnd_inventory schema + helpers (Track 4 #1).

Narrative inventory — per-character items distinct from Avrae sheet-bound
combat gear. Single-writer invariant: only add_item / remove_item write here.

Run:
    cd /home/jordaneal/scripts && python3 test_inventory.py
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
dnd_engine.log = lambda m: captured.append(m)
dnd_engine.db_init()

from dnd_engine import (
    add_item, remove_item, get_inventory, has_item,
    _normalize_item_name,
)


def _reset():
    """Wipe inventory between tests so state doesn't leak."""
    captured.clear()
    conn = sqlite3.connect(TEST_DB)
    conn.execute("DELETE FROM dnd_inventory")
    conn.commit()
    conn.close()


# ─── Schema ─────────────────────────────────────────────────────────

def test_table_exists_with_expected_columns():
    conn = sqlite3.connect(TEST_DB)
    cols = conn.execute("PRAGMA table_info(dnd_inventory)").fetchall()
    conn.close()
    names = [c[1] for c in cols]
    assert names == [
        'id', 'campaign_id', 'character_name', 'item_name',
        'quantity', 'metadata', 'created_at',
    ], f"unexpected columns: {names}"


def test_index_on_lookup_columns_exists():
    conn = sqlite3.connect(TEST_DB)
    idx = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' "
        "AND tbl_name='dnd_inventory'"
    ).fetchall()
    conn.close()
    names = [i[0] for i in idx]
    assert 'idx_inventory_lookup' in names, f"index missing: {names}"


# ─── Normalization ──────────────────────────────────────────────────

def test_normalize_lowercases():
    assert _normalize_item_name('Silver Key') == 'silver key'


def test_normalize_collapses_whitespace():
    assert _normalize_item_name('  silver   key  ') == 'silver key'


def test_normalize_handles_empty():
    assert _normalize_item_name('') == ''
    assert _normalize_item_name(None) == ''


# ─── add_item ───────────────────────────────────────────────────────

def test_add_new_row_returns_inserted():
    _reset()
    r = add_item(1, 'Donovan', 'silver key', 1)
    assert r['action'] == 'inserted'
    assert r['quantity_now'] == 1
    assert r['item_name'] == 'silver key'


def test_add_existing_increments_quantity():
    _reset()
    add_item(1, 'Donovan', 'healing potion', 1)
    r = add_item(1, 'Donovan', 'healing potion', 2)
    assert r['action'] == 'incremented'
    assert r['quantity_now'] == 3


def test_add_case_insensitive_collapses_to_one_row():
    """Adding 'Silver Key' then 'silver key' should increment, not insert."""
    _reset()
    add_item(1, 'Donovan', 'Silver Key', 1)
    r = add_item(1, 'Donovan', 'silver key', 1)
    assert r['action'] == 'incremented', "case difference should still merge"
    assert r['quantity_now'] == 2


def test_add_zero_quantity_invalid():
    _reset()
    r = add_item(1, 'Donovan', 'silver key', 0)
    assert r['action'] == 'invalid'
    assert r['quantity_now'] is None


def test_add_negative_quantity_invalid():
    _reset()
    r = add_item(1, 'Donovan', 'silver key', -3)
    assert r['action'] == 'invalid'


def test_add_empty_item_invalid():
    _reset()
    r = add_item(1, 'Donovan', '', 1)
    assert r['action'] == 'invalid'


def test_add_metadata_persists():
    _reset()
    add_item(1, 'Donovan', 'silver key', 1, metadata='from old man at dock')
    rows = get_inventory(1, 'Donovan')
    assert rows[0]['metadata'] == 'from old man at dock'


def test_add_logs_inventory_add_line():
    _reset()
    add_item(1, 'Donovan', 'silver key', 1)
    text = "\n".join(captured)
    assert 'inventory_add: campaign=1' in text
    assert "character='Donovan'" in text
    assert "item='silver key'" in text
    assert 'action=inserted' in text


# ─── remove_item ────────────────────────────────────────────────────

def test_remove_partial_decrements():
    _reset()
    add_item(1, 'Donovan', 'gold', 10)
    r = remove_item(1, 'Donovan', 'gold', 3)
    assert r['action'] == 'decremented'
    assert r['quantity_now'] == 7


def test_remove_to_zero_deletes_row():
    _reset()
    add_item(1, 'Donovan', 'arrow', 5)
    r = remove_item(1, 'Donovan', 'arrow', 5)
    assert r['action'] == 'removed'
    assert r['quantity_now'] is None
    assert get_inventory(1, 'Donovan') == []


def test_remove_more_than_available_refuses():
    _reset()
    add_item(1, 'Donovan', 'arrow', 5)
    r = remove_item(1, 'Donovan', 'arrow', 10)
    assert r['action'] == 'insufficient'
    assert r['quantity_now'] == 5
    rows = get_inventory(1, 'Donovan')
    assert rows[0]['quantity'] == 5, "must not mutate when refused"


def test_remove_not_found():
    _reset()
    r = remove_item(1, 'Donovan', 'nonexistent', 1)
    assert r['action'] == 'not_found'
    assert r['quantity_now'] is None


def test_remove_case_insensitive():
    _reset()
    add_item(1, 'Donovan', 'silver key', 1)
    r = remove_item(1, 'Donovan', 'SILVER KEY', 1)
    assert r['action'] == 'removed'


def test_remove_zero_quantity_invalid():
    _reset()
    add_item(1, 'Donovan', 'gold', 5)
    r = remove_item(1, 'Donovan', 'gold', 0)
    assert r['action'] == 'invalid'


# ─── get_inventory ──────────────────────────────────────────────────

def test_get_inventory_empty():
    _reset()
    assert get_inventory(1, 'Donovan') == []


def test_get_inventory_ordering():
    _reset()
    add_item(1, 'Donovan', 'zither', 1)
    add_item(1, 'Donovan', 'apple', 1)
    add_item(1, 'Donovan', 'mace', 1)
    rows = get_inventory(1, 'Donovan')
    names = [r['item_name'] for r in rows]
    assert names == ['apple', 'mace', 'zither']


def test_get_inventory_returns_quantity_and_metadata():
    _reset()
    add_item(1, 'Donovan', 'gold', 50, metadata='starting purse')
    rows = get_inventory(1, 'Donovan')
    assert rows[0]['quantity'] == 50
    assert rows[0]['metadata'] == 'starting purse'
    assert rows[0]['created_at']  # truthy ISO timestamp


# ─── has_item ───────────────────────────────────────────────────────

def test_has_item_true_when_present():
    _reset()
    add_item(1, 'Donovan', 'silver key', 1)
    assert has_item(1, 'Donovan', 'silver key') is True


def test_has_item_case_insensitive_lookup():
    _reset()
    add_item(1, 'Donovan', 'silver key', 1)
    assert has_item(1, 'Donovan', 'Silver Key') is True
    assert has_item(1, 'Donovan', 'SILVER KEY') is True


def test_has_item_false_when_absent():
    _reset()
    assert has_item(1, 'Donovan', 'nonexistent') is False


def test_has_item_min_quantity_threshold():
    _reset()
    add_item(1, 'Donovan', 'arrow', 5)
    assert has_item(1, 'Donovan', 'arrow', min_quantity=5) is True
    assert has_item(1, 'Donovan', 'arrow', min_quantity=6) is False


def test_has_item_empty_inputs_return_false():
    _reset()
    assert has_item(1, 'Donovan', '') is False
    assert has_item(1, '', 'silver key') is False
    assert has_item(1, 'Donovan', 'gold', min_quantity=0) is False


# ─── Cross-campaign + cross-character isolation ─────────────────────

def test_cross_campaign_isolation():
    """Same character name in two campaigns → separate inventories."""
    _reset()
    add_item(1, 'Donovan', 'silver key', 1)
    add_item(2, 'Donovan', 'gold', 50)
    inv1 = get_inventory(1, 'Donovan')
    inv2 = get_inventory(2, 'Donovan')
    assert [r['item_name'] for r in inv1] == ['silver key']
    assert [r['item_name'] for r in inv2] == ['gold']


def test_cross_character_isolation():
    """Two characters in the same campaign keep separate inventories."""
    _reset()
    add_item(1, 'Donovan', 'silver key', 1)
    add_item(1, 'Lira', 'lute', 1)
    don = get_inventory(1, 'Donovan')
    lira = get_inventory(1, 'Lira')
    assert [r['item_name'] for r in don] == ['silver key']
    assert [r['item_name'] for r in lira] == ['lute']


def test_remove_in_one_campaign_doesnt_touch_other():
    _reset()
    add_item(1, 'Donovan', 'gold', 10)
    add_item(2, 'Donovan', 'gold', 20)
    remove_item(1, 'Donovan', 'gold', 10)
    assert get_inventory(1, 'Donovan') == []
    inv2 = get_inventory(2, 'Donovan')
    assert inv2[0]['quantity'] == 20


# ─── Cascade-delete safety (campaign-scoped tables tuple) ───────────

def test_inventory_in_campaign_scoped_tables():
    """Cascade delete must include dnd_inventory so /purgecampaign cleans up."""
    from dnd_engine import _CAMPAIGN_SCOPED_TABLES
    assert 'dnd_inventory' in _CAMPAIGN_SCOPED_TABLES


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
