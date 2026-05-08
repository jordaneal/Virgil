"""Unit tests for campaign_set_status.

Covers refusal paths, three valid status transitions, the active-flip
rule (only one active per guild, demoted sibling tracked), un-archiving
on activate, cross-guild isolation. Self-contained — only dnd_campaigns
needed.
"""
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import dnd_engine  # noqa: E402


@pytest.fixture
def tmpdb(monkeypatch, tmp_path):
    db = tmp_path / "test_setstatus.db"
    conn = sqlite3.connect(db)
    conn.executescript("""
        CREATE TABLE dnd_campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            created_at TEXT,
            status TEXT DEFAULT 'active',
            guild_id TEXT DEFAULT '',
            tone TEXT DEFAULT '',
            created_by_user_id TEXT DEFAULT ''
        );
    """)
    conn.commit()
    conn.close()
    monkeypatch.setattr(dnd_engine, 'DB_PATH', db)
    return db


def _make(db, cid, status='inactive', guild_id='guild_A', name=None):
    if name is None:
        name = f'Camp{cid}'
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO dnd_campaigns (id, name, status, guild_id, created_at) "
        "VALUES (?, ?, ?, ?, 'T0')",
        (cid, name, status, guild_id)
    )
    conn.commit()
    conn.close()


def _status(db, cid):
    conn = sqlite3.connect(db)
    row = conn.execute(
        "SELECT status FROM dnd_campaigns WHERE id=?", (cid,)
    ).fetchone()
    conn.close()
    return row[0] if row else None


# ─── Refusal cases ────────────────────────────────────────────────────────────

def test_refuses_unknown_campaign(tmpdb):
    r = dnd_engine.campaign_set_status(999, 'archived')
    assert r['updated'] is False
    assert r['reason']  == 'not_found'


def test_refuses_invalid_status(tmpdb):
    _make(tmpdb, 17, status='inactive')
    r = dnd_engine.campaign_set_status(17, 'deleted')
    assert r['updated'] is False
    assert r['reason']  == 'invalid_status'
    assert _status(tmpdb, 17) == 'inactive'


def test_refuses_invalid_status_does_not_check_existence(tmpdb):
    """Invalid-status check fires BEFORE the not_found check, so an
    invalid status with a missing campaign_id reports invalid_status,
    not not_found. Documents the precedence."""
    r = dnd_engine.campaign_set_status(999, 'pretend')
    assert r['reason'] == 'invalid_status'


def test_refuses_empty_status(tmpdb):
    _make(tmpdb, 17, status='inactive')
    r = dnd_engine.campaign_set_status(17, '')
    assert r['updated'] is False
    assert r['reason']  == 'invalid_status'


# ─── Simple transitions ───────────────────────────────────────────────────────

def test_inactive_to_archived(tmpdb):
    _make(tmpdb, 17, status='inactive')
    r = dnd_engine.campaign_set_status(17, 'archived')
    assert r['updated']             is True
    assert r['previous_status']     == 'inactive'
    assert r['new_status']          == 'archived'
    assert r['previous_active_id']  is None
    assert _status(tmpdb, 17) == 'archived'


def test_archived_to_inactive(tmpdb):
    _make(tmpdb, 17, status='archived')
    r = dnd_engine.campaign_set_status(17, 'inactive')
    assert r['updated']         is True
    assert r['previous_status'] == 'archived'
    assert r['new_status']      == 'inactive'
    assert _status(tmpdb, 17) == 'inactive'


def test_setting_same_status_is_idempotent(tmpdb):
    """No-op style update — setting archived → archived succeeds, no
    sibling demotion (only triggered by setting 'active')."""
    _make(tmpdb, 17, status='archived')
    r = dnd_engine.campaign_set_status(17, 'archived')
    assert r['updated']            is True
    assert r['previous_status']    == 'archived'
    assert r['new_status']         == 'archived'
    assert r['previous_active_id'] is None


# ─── Activate + sibling demotion ──────────────────────────────────────────────

def test_activate_demotes_sibling_active(tmpdb):
    """The classic switch case. Activating campaign 4 demotes
    currently-active campaign 17."""
    _make(tmpdb, 17, status='active')
    _make(tmpdb, 4,  status='inactive')
    r = dnd_engine.campaign_set_status(4, 'active')
    assert r['updated']            is True
    assert r['new_status']         == 'active'
    assert r['previous_active_id'] == 17
    assert _status(tmpdb, 4)  == 'active'
    assert _status(tmpdb, 17) == 'inactive'


def test_activate_with_no_sibling_active(tmpdb):
    """Activating a campaign in a guild with no active campaign:
    no demotion occurs, previous_active_id stays None."""
    _make(tmpdb, 4, status='inactive')
    r = dnd_engine.campaign_set_status(4, 'active')
    assert r['updated']            is True
    assert r['previous_active_id'] is None
    assert _status(tmpdb, 4) == 'active'


def test_activate_unarchives_if_archived(tmpdb):
    """Switching to 'active' un-archives. Per design — switching IS
    the act of un-archiving."""
    _make(tmpdb, 17, status='archived')
    r = dnd_engine.campaign_set_status(17, 'active')
    assert r['updated']         is True
    assert r['previous_status'] == 'archived'
    assert r['new_status']      == 'active'
    assert _status(tmpdb, 17) == 'active'


def test_activate_unarchives_and_demotes(tmpdb):
    """Combined: archived 17 becomes active, demoting active 4."""
    _make(tmpdb, 4,  status='active')
    _make(tmpdb, 17, status='archived')
    r = dnd_engine.campaign_set_status(17, 'active')
    assert r['previous_active_id'] == 4
    assert _status(tmpdb, 4)  == 'inactive'
    assert _status(tmpdb, 17) == 'active'


def test_activate_on_already_active_no_demotion(tmpdb):
    """Setting active on an already-active campaign: there's no OTHER
    active campaign to demote (the sibling query is `id!=?`).
    previous_active_id stays None."""
    _make(tmpdb, 17, status='active')
    r = dnd_engine.campaign_set_status(17, 'active')
    assert r['updated']            is True
    assert r['previous_active_id'] is None
    assert _status(tmpdb, 17) == 'active'


# ─── Cross-guild isolation ────────────────────────────────────────────────────

def test_activate_does_not_demote_other_guild(tmpdb):
    """Each guild has its own active campaign. Activating a campaign
    in guild B does not affect guild A's active campaign."""
    _make(tmpdb, 17, status='active',   guild_id='guild_A')
    _make(tmpdb, 99, status='active',   guild_id='guild_B')
    _make(tmpdb, 100, status='inactive', guild_id='guild_B')
    r = dnd_engine.campaign_set_status(100, 'active')
    assert r['previous_active_id'] == 99      # demoted in guild_B only
    assert _status(tmpdb, 17)  == 'active'    # guild_A untouched
    assert _status(tmpdb, 99)  == 'inactive'
    assert _status(tmpdb, 100) == 'active'


# ─── Return-shape / echoing ───────────────────────────────────────────────────

def test_return_shape_keys(tmpdb):
    _make(tmpdb, 17, status='inactive')
    r = dnd_engine.campaign_set_status(17, 'archived')
    assert set(r.keys()) == {
        'campaign_id', 'updated', 'reason',
        'previous_status', 'new_status', 'previous_active_id',
    }


def test_campaign_id_echoed_on_refusal(tmpdb):
    r = dnd_engine.campaign_set_status(999, 'archived')
    assert r['campaign_id'] == 999


def test_campaign_id_echoed_on_success(tmpdb):
    _make(tmpdb, 17, status='inactive')
    r = dnd_engine.campaign_set_status(17, 'archived')
    assert r['campaign_id'] == 17
