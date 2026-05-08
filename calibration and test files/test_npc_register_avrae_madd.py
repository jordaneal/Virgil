"""Tests for npc_register_avrae_madd() — Track 6 #4.

Covers: row creation, avrae_source='avrae_madd', NULL stat cols, idempotency,
no-clobber of existing description/role fields.

Run:
    cd /home/jordaneal/scripts && python3 test_npc_register_avrae_madd.py
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
    npc_upsert, npc_get_by_name, stat_incomplete,
    npc_register_avrae_madd, create_campaign,
)

GUILD = 'test-guild-avrae-madd'


def _campaign():
    return create_campaign(GUILD, 'TestCampaign')


def test_first_call_creates_row_with_avrae_source():
    cid = _campaign()
    wrote, _ = npc_register_avrae_madd(cid, 'Goblin')
    npc = npc_get_by_name(cid, 'Goblin')
    assert npc is not None
    assert npc['avrae_source'] == 'avrae_madd'


def test_first_call_leaves_stat_cols_null():
    cid = _campaign()
    npc_register_avrae_madd(cid, 'Goblin2')
    npc = npc_get_by_name(cid, 'Goblin2')
    assert npc['hp_max'] is None
    assert npc['ac'] is None
    assert npc['attack_bonus'] is None
    assert npc['damage_dice'] is None
    assert npc['cr_str'] is None


def test_second_call_is_idempotent():
    cid = _campaign()
    npc_register_avrae_madd(cid, 'Goblin3')
    wrote, _ = npc_register_avrae_madd(cid, 'Goblin3')
    assert wrote is False  # second call is a no-op


def test_existing_row_gets_avrae_source_without_clobbering_description():
    cid = _campaign()
    npc_upsert(cid, 'RichGoblin', role='scout', description='A clever scout.', skeleton_origin=False)
    npc_register_avrae_madd(cid, 'RichGoblin')
    npc = npc_get_by_name(cid, 'RichGoblin')
    assert npc['avrae_source'] == 'avrae_madd'
    assert npc['role'] == 'scout'
    assert npc['description'] == 'A clever scout.'


def test_existing_row_gets_avrae_source_without_clobbering_role():
    cid = _campaign()
    npc_upsert(cid, 'BossGoblin', role='boss', skeleton_origin=False)
    npc_register_avrae_madd(cid, 'BossGoblin')
    npc = npc_get_by_name(cid, 'BossGoblin')
    assert npc['avrae_source'] == 'avrae_madd'
    assert npc['role'] == 'boss'


def test_avrae_madd_log_line_emitted():
    captured.clear()
    cid = _campaign()
    npc_register_avrae_madd(cid, 'LogGoblin', status_token='<Healthy>')
    log_text = '\n'.join(captured)
    assert 'source=avrae_madd' in log_text
    assert "npc='LogGoblin'" in log_text
    assert 'stats_filled=none' in log_text


def test_stat_incomplete_true_after_register():
    cid = _campaign()
    npc_register_avrae_madd(cid, 'StatGoblin')
    npc = npc_get_by_name(cid, 'StatGoblin')
    assert stat_incomplete(npc) is True


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
