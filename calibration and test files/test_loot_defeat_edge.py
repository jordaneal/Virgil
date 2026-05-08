"""Death-edge detection in update_combatants_from_init_list (Track 4 #2).

Replaces a standalone parse_defeat_event parser. Avrae does NOT emit standalone
defeat messages — defeat surfaces only inside the next !init list snapshot
(status field <Defeated> or <0/N HP>). The S21 init_list parser already
decodes both into alive=0; v1 detects defeats by comparing alive flags between
consecutive snapshots (alive=1 -> alive=0). PCs are filtered out via
get_bound_character_names.

Run:
    cd /home/jordaneal/scripts && python3 test_loot_defeat_edge.py
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
    update_combatants_from_init_list,
    clear_combatants,
    get_pending_loot,
)


def _parsed(combatants):
    return {'round': 1, 'current_init': 25, 'combatants': combatants}


def _row(name, alive=1, hp_current=None):
    return {'init': 20, 'name': name, 'active': False,
            'hp_current': hp_current, 'hp_max': None,
            'conditions': '', 'alive': alive}


def _bind_pc(campaign_id: int, name: str):
    """Insert a bound PC row directly so get_bound_character_names returns it.
    Mirrors what /bindchar does at the engine layer."""
    conn = sqlite3.connect(TEST_DB)
    conn.execute(
        "INSERT INTO dnd_characters (campaign_id, name, race, class, level, "
        "controller, alive, canonical_name, aliases) "
        "VALUES (?,?,?,?,?,?,1,?,?)",
        (campaign_id, name, 'human', 'fighter', 1, 'tester',
         name.lower(), '[]')
    )
    conn.commit()
    conn.close()


# ─── No edge → no enqueue ───────────────────────────────────────────

def test_first_snapshot_with_no_prior_no_defeat_enqueued():
    clear_combatants(100)
    update_combatants_from_init_list(100, _parsed([
        _row('Goblin', alive=1),
        _row('Wolf', alive=1),
    ]))
    assert get_pending_loot(100) == []


def test_alive_to_alive_no_defeat():
    clear_combatants(101)
    update_combatants_from_init_list(101, _parsed([_row('Goblin', alive=1)]))
    update_combatants_from_init_list(101, _parsed([_row('Goblin', alive=1)]))
    assert get_pending_loot(101) == []


def test_dead_to_dead_no_defeat():
    clear_combatants(102)
    update_combatants_from_init_list(102, _parsed([_row('Goblin', alive=0)]))
    update_combatants_from_init_list(102, _parsed([_row('Goblin', alive=0)]))
    assert get_pending_loot(102) == []


def test_disappear_from_snapshot_not_counted_as_defeat():
    # Conservative: !init remove and defeated-and-pruned are
    # indistinguishable. v1 only counts explicit alive=1 -> alive=0.
    clear_combatants(103)
    update_combatants_from_init_list(103, _parsed([_row('Goblin', alive=1)]))
    update_combatants_from_init_list(103, _parsed([]))  # disappeared
    assert get_pending_loot(103) == []


# ─── Edge fires → enqueue ───────────────────────────────────────────

def test_alive_to_dead_enqueues_loot():
    clear_combatants(104)
    update_combatants_from_init_list(104, _parsed([_row('Goblin', alive=1)]))
    update_combatants_from_init_list(104, _parsed([_row('Goblin', alive=0)]))
    rows = get_pending_loot(104)
    assert len(rows) == 1
    assert rows[0]['table_key'] == 'goblin'


def test_multiple_defeats_same_snapshot_each_enqueued():
    clear_combatants(105)
    update_combatants_from_init_list(105, _parsed([
        _row('Goblin', alive=1), _row('Wolf', alive=1),
    ]))
    update_combatants_from_init_list(105, _parsed([
        _row('Goblin', alive=0), _row('Wolf', alive=0),
    ]))
    rows = get_pending_loot(105)
    assert len(rows) == 2
    keys = sorted(r['table_key'] for r in rows)
    assert keys == ['goblin', 'wolf']


def test_only_newly_defeated_enqueued():
    clear_combatants(106)
    # First: Goblin already dead, Wolf still alive
    update_combatants_from_init_list(106, _parsed([
        _row('Goblin', alive=0), _row('Wolf', alive=1),
    ]))
    # Second: Wolf falls (new defeat); Goblin still dead (no new edge)
    update_combatants_from_init_list(106, _parsed([
        _row('Goblin', alive=0), _row('Wolf', alive=0),
    ]))
    rows = get_pending_loot(106)
    assert len(rows) == 1
    assert rows[0]['table_key'] == 'wolf'


def test_unknown_creature_enqueued_with_default_table():
    clear_combatants(107)
    update_combatants_from_init_list(107, _parsed([_row('Mystery Beast', alive=1)]))
    update_combatants_from_init_list(107, _parsed([_row('Mystery Beast', alive=0)]))
    rows = get_pending_loot(107)
    assert len(rows) == 1
    assert rows[0]['table_key'] == '_default'


# ─── PC filtering ──────────────────────────────────────────────────

def test_pc_defeat_does_not_enqueue_loot():
    _bind_pc(108, 'Donovan')
    clear_combatants(108)
    update_combatants_from_init_list(108, _parsed([_row('Donovan', alive=1)]))
    update_combatants_from_init_list(108, _parsed([_row('Donovan', alive=0)]))
    assert get_pending_loot(108) == []


def test_pc_filter_is_case_insensitive():
    _bind_pc(109, 'Throx')
    clear_combatants(109)
    # Avrae sometimes lowercases combatant names — make sure the filter
    # matches the bound PC regardless of casing.
    update_combatants_from_init_list(109, _parsed([_row('throx', alive=1)]))
    update_combatants_from_init_list(109, _parsed([_row('throx', alive=0)]))
    assert get_pending_loot(109) == []


def test_npc_defeat_alongside_pc_only_npc_enqueued():
    _bind_pc(110, 'Donovan')
    clear_combatants(110)
    update_combatants_from_init_list(110, _parsed([
        _row('Donovan', alive=1), _row('Goblin', alive=1),
    ]))
    update_combatants_from_init_list(110, _parsed([
        _row('Donovan', alive=0), _row('Goblin', alive=0),
    ]))
    rows = get_pending_loot(110)
    assert len(rows) == 1
    assert rows[0]['table_key'] == 'goblin'


# ─── Cross-campaign isolation ──────────────────────────────────────

def test_defeat_in_one_campaign_does_not_leak_to_other():
    clear_combatants(111)
    clear_combatants(112)
    update_combatants_from_init_list(111, _parsed([_row('Goblin', alive=1)]))
    update_combatants_from_init_list(112, _parsed([_row('Goblin', alive=1)]))
    update_combatants_from_init_list(111, _parsed([_row('Goblin', alive=0)]))
    assert len(get_pending_loot(111)) == 1
    assert get_pending_loot(112) == []


# ─── Telemetry ──────────────────────────────────────────────────────

def test_defeat_parsed_log_line_emits_on_edge():
    captured.clear()
    clear_combatants(113)
    update_combatants_from_init_list(113, _parsed([_row('Goblin', alive=1)]))
    update_combatants_from_init_list(113, _parsed([_row('Goblin', alive=0)]))
    text = "\n".join(captured)
    assert 'defeat_parsed: campaign=113' in text
    assert "creature='Goblin'" in text
    assert 'table=goblin' in text


def test_existing_update_log_line_unchanged():
    # The original 'update_combatants_from_init_list: campaign=N rows=N' line
    # must still emit — it's the load-bearing observability for S21.
    captured.clear()
    clear_combatants(114)
    update_combatants_from_init_list(114, _parsed([_row('Goblin', alive=1)]))
    text = "\n".join(captured)
    assert 'update_combatants_from_init_list: campaign=114 rows=1' in text


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
