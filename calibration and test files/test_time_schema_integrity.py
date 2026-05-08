"""Schema-level tests for Track 4 #3 time progression v1
(Session 27).

Per TRACK_4_3_SPEC.md §9 (tests 38-41). Self-contained: builds an
empty DB, runs db_init(), confirms columns and tables exist with the
expected defaults.

Run:
    cd /home/jordaneal/scripts && python3 -m pytest test_time_schema_integrity.py -q
"""

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, '/home/jordaneal/scripts')

import dnd_engine  # noqa: E402


@pytest.fixture
def freshdb(monkeypatch, tmp_path):
    db = tmp_path / "fresh.db"
    monkeypatch.setattr(dnd_engine, 'DB_PATH', db)
    dnd_engine.db_init()
    return db


def _columns(db, table):
    conn = sqlite3.connect(db)
    cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    conn.close()
    return cols


def test_campaign_day_column_exists(freshdb):
    cols = _columns(freshdb, 'dnd_scene_state')
    assert 'campaign_day' in cols


def test_day_phase_column_exists(freshdb):
    cols = _columns(freshdb, 'dnd_scene_state')
    assert 'day_phase' in cols


def test_dnd_time_advancements_table_exists(freshdb):
    conn = sqlite3.connect(freshdb)
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name='dnd_time_advancements'"
    ).fetchall()
    conn.close()
    assert len(rows) == 1


def test_default_campaign_day_is_one(freshdb):
    conn = sqlite3.connect(freshdb)
    # Need a parent campaign row first since dnd_scene_state.campaign_id
    # has no FK enforced, but we'll just insert directly.
    conn.execute("INSERT INTO dnd_scene_state (campaign_id) VALUES (?)", (1,))
    conn.commit()
    row = conn.execute(
        "SELECT campaign_day, day_phase FROM dnd_scene_state WHERE campaign_id=?",
        (1,)
    ).fetchone()
    conn.close()
    assert row[0] == 1
    assert row[1] == 'Morning'


def test_dnd_time_advancements_indices_exist(freshdb):
    conn = sqlite3.connect(freshdb)
    indices = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' "
        "AND tbl_name='dnd_time_advancements'"
    )}
    conn.close()
    assert 'idx_time_adv_campaign' in indices
    assert 'idx_time_adv_created' in indices


def test_table_in_campaign_scoped_tables():
    assert 'dnd_time_advancements' in dnd_engine._CAMPAIGN_SCOPED_TABLES


def test_pre_v1_row_default_migration(freshdb):
    """A scene_state row created before the migration (no time fields)
    auto-defaults to (1, 'Morning') on read because the ALTER TABLE
    ADD COLUMN ... DEFAULT clauses backfill any existing rows."""
    conn = sqlite3.connect(freshdb)
    conn.execute("INSERT INTO dnd_scene_state (campaign_id) VALUES (?)", (42,))
    conn.commit()
    conn.close()
    state = dnd_engine.get_scene_state(42)
    assert state is not None
    assert state['campaign_day'] == 1
    assert state['day_phase'] == 'Morning'


# ─── §K cascade-integrity test ──────────────────────────────────

def test_purgecampaign_cleans_time_advancements(freshdb):
    """Spec §4 cascade requirement — campaign_delete_cascade must
    wipe dnd_time_advancements rows for the deleted campaign.
    Per VIRGIL_MASTER §6: missing the table from
    _CAMPAIGN_SCOPED_TABLES leaves orphan rows after purge."""
    conn = sqlite3.connect(freshdb)
    # Create an inactive campaign (cascade refuses active).
    conn.execute(
        "INSERT INTO dnd_campaigns (id, name, status, guild_id, created_at) "
        "VALUES (?, ?, ?, ?, '')",
        (50, 'PurgeTest', 'inactive', 'guild_test')
    )
    conn.execute(
        "INSERT INTO dnd_scene_state (campaign_id, campaign_day, day_phase) "
        "VALUES (?, ?, ?)",
        (50, 1, 'Morning')
    )
    conn.commit()
    conn.close()
    # Advance once via the writer so a real audit row exists.
    r = dnd_engine.advance_time(50, 1, 0, 'travel', 'pre-purge')
    assert r is not None
    # Confirm the row exists.
    conn = sqlite3.connect(freshdb)
    n_before = conn.execute(
        "SELECT COUNT(*) FROM dnd_time_advancements WHERE campaign_id=?",
        (50,)
    ).fetchone()[0]
    conn.close()
    assert n_before == 1
    # Run the cascade.
    result = dnd_engine.campaign_delete_cascade(50)
    assert result['deleted'] is True
    assert 'dnd_time_advancements' in result['rows_deleted']
    assert result['rows_deleted']['dnd_time_advancements'] == 1
    # Confirm orphan-row count is 0.
    conn = sqlite3.connect(freshdb)
    n_after = conn.execute(
        "SELECT COUNT(*) FROM dnd_time_advancements WHERE campaign_id=?",
        (50,)
    ).fetchone()[0]
    conn.close()
    assert n_after == 0
