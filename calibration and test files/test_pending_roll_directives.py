"""Deterministic tests for Bug 1 Phase 1 engine layer (Session 32).

Covers:
  - dnd_pending_roll_directives schema (table + index + cascade)
  - last_active_actor column on dnd_scene_state
  - update_last_active_actor (write + footer_actor_changed log)
  - pending_directive_upsert / get_active / consume / delete_by_message
  - lazy TTL sweep on get_active emitting pending_directive_expired

Phase 1 is telemetry-only — these tests assert the engine surface only.
Discord-side parser/matcher live-verifies separately (per §73).

Run:
    cd /home/jordaneal/scripts && python3 test_pending_roll_directives.py
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
    update_last_active_actor,
    pending_directive_upsert,
    pending_directive_get_active,
    pending_directive_consume,
    pending_directive_delete_by_message,
    pending_directive_age_seconds,
    get_scene_state,
    init_scene_state,
    _CAMPAIGN_SCOPED_TABLES,
)


def _reset_logs():
    captured.clear()


def _reset_state(campaign_id):
    conn = sqlite3.connect(TEST_DB)
    conn.execute("DELETE FROM dnd_pending_roll_directives WHERE campaign_id=?",
                 (campaign_id,))
    conn.execute("UPDATE dnd_scene_state SET last_active_actor='' "
                 "WHERE campaign_id=?", (campaign_id,))
    conn.commit()
    conn.close()


def test_pending_table_columns():
    conn = sqlite3.connect(TEST_DB)
    cols = conn.execute(
        "PRAGMA table_info(dnd_pending_roll_directives)"
    ).fetchall()
    conn.close()
    names = [c[1] for c in cols]
    assert names == [
        'campaign_id', 'actor_name', 'check_type', 'source_message_id',
        'created_at', 'expires_at',
    ], f"unexpected columns: {names}"


def test_pending_table_primary_key_is_campaign_id():
    conn = sqlite3.connect(TEST_DB)
    pk_cols = [c[1] for c in conn.execute(
        "PRAGMA table_info(dnd_pending_roll_directives)"
    ) if c[5]]  # column 5 is `pk` flag
    conn.close()
    assert pk_cols == ['campaign_id'], f"unexpected PK: {pk_cols}"


def test_pending_table_index_on_message_id():
    conn = sqlite3.connect(TEST_DB)
    idx = conn.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type='index' AND tbl_name='dnd_pending_roll_directives'"
    ).fetchall()
    conn.close()
    names = [r[0] for r in idx]
    assert 'idx_pending_directive_msg' in names, f"index missing: {names}"


def test_cascade_list_includes_pending_directives():
    assert 'dnd_pending_roll_directives' in _CAMPAIGN_SCOPED_TABLES, \
        "_CAMPAIGN_SCOPED_TABLES must include dnd_pending_roll_directives"


def test_last_active_actor_column_present():
    conn = sqlite3.connect(TEST_DB)
    cols = {c[1] for c in conn.execute(
        "PRAGMA table_info(dnd_scene_state)"
    ).fetchall()}
    conn.close()
    assert 'last_active_actor' in cols, \
        f"last_active_actor column missing: {cols}"


def test_update_last_active_actor_writes_and_logs_on_transition():
    init_scene_state(101, 'seed')
    _reset_state(101)
    _reset_logs()
    update_last_active_actor(101, 'Donovan Ruby', 'dm_respond')
    state = get_scene_state(101)
    assert state.get('last_active_actor') == 'Donovan Ruby'
    assert any('footer_actor_changed' in m and 'from=none' in m and
               "to=Donovan Ruby" in m and 'trigger=dm_respond' in m
               for m in captured), \
        f"footer_actor_changed not logged: {captured!r}"


def test_update_last_active_actor_noop_on_unchanged():
    init_scene_state(102, 'seed')
    _reset_state(102)
    update_last_active_actor(102, 'Hilda', 'dm_respond')
    _reset_logs()
    update_last_active_actor(102, 'Hilda', 'dm_respond')
    assert not any('footer_actor_changed' in m for m in captured), \
        f"unexpected footer_actor_changed log on no-op: {captured!r}"


def test_update_last_active_actor_logs_clear_transition():
    init_scene_state(103, 'seed')
    _reset_state(103)
    update_last_active_actor(103, 'Throx', 'combat_turn_set')
    _reset_logs()
    update_last_active_actor(103, '', 'combat_turn_clear')
    assert any('footer_actor_changed' in m and 'from=Throx' in m and
               'to=none' in m and 'trigger=combat_turn_clear' in m
               for m in captured), \
        f"clear transition not logged: {captured!r}"


def test_update_last_active_actor_play_clears():
    init_scene_state(104, 'seed')
    _reset_state(104)
    update_last_active_actor(104, 'Zara', 'dm_respond')
    _reset_logs()
    update_last_active_actor(104, '', 'play')
    state = get_scene_state(104)
    assert state.get('last_active_actor') == ''
    assert any('trigger=play' in m for m in captured), \
        f"play trigger not logged: {captured!r}"


def test_pending_directive_upsert_insert_returns_replaced_false():
    init_scene_state(201, 'seed')
    _reset_state(201)
    result = pending_directive_upsert(201, 'Donovan Ruby', 'stealth',
                                      'msg_a', 300)
    assert result['replaced'] is False
    assert result['prior'] is None


def test_pending_directive_upsert_replace_returns_prior():
    init_scene_state(202, 'seed')
    _reset_state(202)
    pending_directive_upsert(202, 'Donovan Ruby', 'stealth', 'msg_a', 300)
    result = pending_directive_upsert(202, 'Hilda', 'perception',
                                      'msg_b', 300)
    assert result['replaced'] is True
    assert result['prior']['actor_name'] == 'Donovan Ruby'
    assert result['prior']['check_type'] == 'stealth'


def test_pending_directive_get_active_returns_row():
    init_scene_state(203, 'seed')
    _reset_state(203)
    pending_directive_upsert(203, 'Donovan Ruby', 'stealth', 'msg_a', 300)
    row = pending_directive_get_active(203)
    assert row is not None
    assert row['actor_name'] == 'Donovan Ruby'
    assert row['check_type'] == 'stealth'
    assert row['source_message_id'] == 'msg_a'


def test_pending_directive_get_active_returns_none_when_absent():
    init_scene_state(204, 'seed')
    _reset_state(204)
    assert pending_directive_get_active(204) is None


def test_pending_directive_lazy_expiry_sweeps_and_logs():
    init_scene_state(205, 'seed')
    _reset_state(205)
    # ttl=0 means expires_at == created_at, so utcnow() >= expires_at fires
    # the sweep on the very next read.
    pending_directive_upsert(205, 'Donovan Ruby', 'stealth', 'msg_a', 0)
    _reset_logs()
    row = pending_directive_get_active(205)
    assert row is None
    assert any('pending_directive_expired' in m and
               'actor=Donovan Ruby' in m and 'skill=stealth' in m
               for m in captured), \
        f"pending_directive_expired not logged: {captured!r}"
    # Confirm the row was actually deleted (next read still returns None
    # without re-emitting an expiry log)
    _reset_logs()
    assert pending_directive_get_active(205) is None
    assert not any('pending_directive_expired' in m for m in captured)


def test_pending_directive_consume_deletes():
    init_scene_state(206, 'seed')
    _reset_state(206)
    pending_directive_upsert(206, 'Donovan Ruby', 'stealth', 'msg_a', 300)
    assert pending_directive_consume(206) is True
    assert pending_directive_get_active(206) is None
    assert pending_directive_consume(206) is False  # idempotent miss


def test_pending_directive_delete_by_message_matches_only_correct_msg():
    init_scene_state(207, 'seed')
    _reset_state(207)
    pending_directive_upsert(207, 'Donovan Ruby', 'stealth', 'msg_a', 300)
    # Wrong message id: no-op
    assert pending_directive_delete_by_message(207, 'msg_zzz') is None
    # Correct message id: deletes + returns prior dict
    removed = pending_directive_delete_by_message(207, 'msg_a')
    assert removed is not None
    assert removed['actor_name'] == 'Donovan Ruby'
    assert removed['check_type'] == 'stealth'
    assert pending_directive_get_active(207) is None


def test_pending_directive_age_seconds_negative_on_garbage():
    assert pending_directive_age_seconds('not a date') == -1
    assert pending_directive_age_seconds('') == -1


def test_pending_directive_age_seconds_positive_on_real_value():
    init_scene_state(208, 'seed')
    _reset_state(208)
    pending_directive_upsert(208, 'Donovan Ruby', 'stealth', 'msg_a', 300)
    row = pending_directive_get_active(208)
    age = pending_directive_age_seconds(row['created_at'])
    assert age >= 0


def test_pending_directives_cleared_by_campaign_delete_cascade():
    from dnd_engine import campaign_delete_cascade, create_campaign, campaign_set_status
    cid = create_campaign('test_guild_pdr', 'Cascade Test', creator_user_id='u1')
    init_scene_state(cid, 'seed')
    pending_directive_upsert(cid, 'Donovan Ruby', 'stealth', 'msg_a', 300)
    # Cascade refuses active campaigns; archive first.
    campaign_set_status(cid, 'archived')
    result = campaign_delete_cascade(cid)
    assert result['deleted'], f"cascade did not delete: {result!r}"
    assert result['rows_deleted'].get('dnd_pending_roll_directives', 0) == 1, \
        f"cascade did not delete pending directive row: {result!r}"


# ─── Runner ──────────────────────────────────────────────────────────

if __name__ == '__main__':
    import traceback
    funcs = [v for k, v in sorted(globals().items())
             if k.startswith('test_') and callable(v)]
    failures = []
    for fn in funcs:
        try:
            fn()
            print(f"  ok   {fn.__name__}")
        except AssertionError as e:
            failures.append((fn.__name__, repr(e)))
            print(f"  FAIL {fn.__name__}: {e!r}")
        except Exception as e:
            failures.append((fn.__name__, repr(e)))
            print(f"  ERR  {fn.__name__}: {e!r}")
            traceback.print_exc()
    if failures:
        print(f"\n{len(failures)} failure(s)")
        sys.exit(1)
    print(f"\n{len(funcs)} tests passed.")
