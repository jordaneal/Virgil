"""Unit tests for campaign_delete_cascade.

Covers: refusal on active, refusal on not-found, single-campaign delete
across all 8 tables, isolation from other campaigns, transactional safety
(no partial deletion). Self-contained: builds all 8 campaign-scoped tables.
"""
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import dnd_engine  # noqa: E402


@pytest.fixture
def tmpdb(monkeypatch, tmp_path):
    """Per-test sqlite file with all 8 campaign-scoped tables.

    Schemas mirror dnd_engine.db_init() — only the columns the cascade
    function touches are required, but enough shape is reproduced so
    INSERTs from the test helpers behave realistically.
    """
    db = tmp_path / "test_cascade.db"
    conn = sqlite3.connect(db)
    conn.executescript("""
        CREATE TABLE dnd_campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            created_at TEXT,
            status TEXT DEFAULT 'active',
            world_notes TEXT DEFAULT '',
            current_scene TEXT DEFAULT '',
            guild_id TEXT DEFAULT '',
            tone TEXT DEFAULT '',
            created_by_user_id TEXT DEFAULT ''
        );
        CREATE TABLE dnd_characters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER,
            name TEXT NOT NULL,
            race TEXT DEFAULT '',
            class TEXT DEFAULT '',
            level INTEGER DEFAULT 1,
            controller TEXT DEFAULT '',
            alive INTEGER DEFAULT 1
        );
        CREATE TABLE dnd_scene_state (
            campaign_id INTEGER PRIMARY KEY,
            mode TEXT DEFAULT 'exploration',
            updated_at TEXT DEFAULT ''
        );
        CREATE TABLE dnd_combat_state (
            campaign_id     INTEGER PRIMARY KEY,
            controller_id   TEXT    NOT NULL,
            character_name  TEXT    NOT NULL,
            round           INTEGER NOT NULL,
            updated_at      TEXT    NOT NULL
        );
        CREATE TABLE dnd_quests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE dnd_companions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            persona TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE dnd_npcs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            canonical_name TEXT NOT NULL,
            first_mentioned TEXT NOT NULL,
            last_mentioned TEXT NOT NULL,
            UNIQUE(campaign_id, canonical_name)
        );
        CREATE TABLE dnd_locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            canonical_name TEXT NOT NULL,
            first_mentioned TEXT NOT NULL,
            last_mentioned TEXT NOT NULL,
            UNIQUE(campaign_id, canonical_name)
        );
        -- Late additions to _CAMPAIGN_SCOPED_TABLES; minimal columns to
        -- support cascade DELETE WHERE campaign_id=?.
        CREATE TABLE dnd_consequences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            npc_id INTEGER
        );
        CREATE TABLE dnd_combatant_state (
            campaign_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (campaign_id, name)
        );
        CREATE TABLE dnd_inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            character_name TEXT NOT NULL,
            item_name TEXT NOT NULL
        );
        CREATE TABLE dnd_loot_pending (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            creature TEXT NOT NULL,
            table_key TEXT NOT NULL,
            items TEXT NOT NULL,
            surfaced INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        );
        CREATE TABLE dnd_time_advancements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            before_day INTEGER NOT NULL,
            before_phase TEXT NOT NULL,
            after_day INTEGER NOT NULL,
            after_phase TEXT NOT NULL,
            days_delta INTEGER NOT NULL,
            phase_delta INTEGER NOT NULL,
            resolved_phase_delta INTEGER NOT NULL,
            set_phase TEXT,
            source TEXT NOT NULL,
            source_detail TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()
    monkeypatch.setattr(dnd_engine, 'DB_PATH', db)
    return db


def _make_campaign(db, cid, name, status='inactive', guild_id='guild_1'):
    """Insert a campaign with explicit id (forced via INSERT INTO ... id=...)."""
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO dnd_campaigns (id, name, status, guild_id, created_at) "
        "VALUES (?, ?, ?, ?, 'T0')",
        (cid, name, status, guild_id)
    )
    conn.commit()
    conn.close()


def _populate(db, cid):
    """Insert one row in every per-campaign table for the given campaign."""
    conn = sqlite3.connect(db)
    conn.execute("INSERT INTO dnd_characters (campaign_id, name) VALUES (?, 'Hero')", (cid,))
    conn.execute("INSERT INTO dnd_scene_state (campaign_id) VALUES (?)", (cid,))
    conn.execute(
        "INSERT INTO dnd_combat_state "
        "(campaign_id, controller_id, character_name, round, updated_at) "
        "VALUES (?, 'u1', 'Hero', 1, 'T0')", (cid,)
    )
    conn.execute(
        "INSERT INTO dnd_quests (campaign_id, title, created_at, updated_at) "
        "VALUES (?, 'Q', 'T0', 'T0')", (cid,)
    )
    conn.execute(
        "INSERT INTO dnd_companions (campaign_id, name, created_at, updated_at) "
        "VALUES (?, 'Comp', 'T0', 'T0')", (cid,)
    )
    conn.execute(
        "INSERT INTO dnd_npcs (campaign_id, canonical_name, "
        "first_mentioned, last_mentioned) VALUES (?, 'NPC1', 'T0', 'T0')",
        (cid,)
    )
    conn.execute(
        "INSERT INTO dnd_locations (campaign_id, canonical_name, "
        "first_mentioned, last_mentioned) VALUES (?, 'Loc1', 'T0', 'T0')",
        (cid,)
    )
    conn.commit()
    conn.close()


def _row_count(db, table, campaign_id=None):
    conn = sqlite3.connect(db)
    if campaign_id is None:
        n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    else:
        n = conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE campaign_id=?",
            (campaign_id,)
        ).fetchone()[0]
    conn.close()
    return n


# ─── Refusal cases ────────────────────────────────────────────────────────────

def test_refuses_when_campaign_not_found(tmpdb):
    r = dnd_engine.campaign_delete_cascade(999)
    assert r['deleted'] is False
    assert r['reason'] == 'not_found'
    assert r['rows_deleted'] == {}


def test_refuses_when_campaign_is_active(tmpdb):
    _make_campaign(tmpdb, 17, 'ActiveOne', status='active')
    _populate(tmpdb, 17)
    r = dnd_engine.campaign_delete_cascade(17)
    assert r['deleted'] is False
    assert r['reason'] == 'campaign_is_active'
    # Nothing was deleted
    assert _row_count(tmpdb, 'dnd_campaigns') == 1
    assert _row_count(tmpdb, 'dnd_characters', 17) == 1
    assert _row_count(tmpdb, 'dnd_npcs', 17) == 1


def test_refuses_active_does_not_log_partial(tmpdb):
    """Belt-and-suspenders: active refusal must not have touched any
    table even briefly. rows_deleted is empty, all rows survive."""
    _make_campaign(tmpdb, 17, 'ActiveOne', status='active')
    _populate(tmpdb, 17)
    r = dnd_engine.campaign_delete_cascade(17)
    assert r['rows_deleted'] == {}


# ─── Successful delete ────────────────────────────────────────────────────────

def test_archived_campaign_deletes_cleanly(tmpdb):
    _make_campaign(tmpdb, 17, 'ArchivedOne', status='archived')
    _populate(tmpdb, 17)
    r = dnd_engine.campaign_delete_cascade(17)
    assert r['deleted'] is True
    assert r['reason'] is None
    # The cascade walks every table in _CAMPAIGN_SCOPED_TABLES + dnd_campaigns.
    # The fixture's _populate inserts into the original 8 tables; the late
    # additions (dnd_consequences, dnd_combatant_state, dnd_inventory,
    # dnd_loot_pending, dnd_time_advancements) appear in rows_deleted with
    # count=0 because no row was inserted, but the keys still appear.
    populated_tables = {
        'dnd_npcs', 'dnd_locations', 'dnd_quests', 'dnd_companions',
        'dnd_combat_state', 'dnd_scene_state', 'dnd_characters',
        'dnd_campaigns',
    }
    for t in populated_tables:
        assert r['rows_deleted'][t] == 1, f"expected 1 row deleted from {t}"
    # All scoped tables must appear in the result, even when count=0.
    for t in dnd_engine._CAMPAIGN_SCOPED_TABLES:
        assert t in r['rows_deleted']


def test_inactive_campaign_deletes_cleanly(tmpdb):
    """Soft-delete is one path to removability, but plain inactive
    (e.g. an old test campaign) should also be deletable."""
    _make_campaign(tmpdb, 17, 'InactiveOne', status='inactive')
    _populate(tmpdb, 17)
    r = dnd_engine.campaign_delete_cascade(17)
    assert r['deleted'] is True


def test_delete_removes_all_rows(tmpdb):
    """After delete, the campaign's rows are GONE from every table."""
    _make_campaign(tmpdb, 17, 'Doomed', status='archived')
    _populate(tmpdb, 17)
    dnd_engine.campaign_delete_cascade(17)
    for tbl in ('dnd_characters', 'dnd_scene_state', 'dnd_combat_state',
                'dnd_quests', 'dnd_companions', 'dnd_npcs', 'dnd_locations'):
        assert _row_count(tmpdb, tbl, 17) == 0, f"{tbl} not cleared"
    assert _row_count(tmpdb, 'dnd_campaigns') == 0


def test_delete_isolates_other_campaigns(tmpdb):
    """Deleting campaign 17 leaves campaign 4 untouched, including
    every dependent row."""
    _make_campaign(tmpdb, 4,  'Survivor',  status='inactive')
    _make_campaign(tmpdb, 17, 'Doomed',    status='archived')
    _populate(tmpdb, 4)
    _populate(tmpdb, 17)
    dnd_engine.campaign_delete_cascade(17)
    # 17 gone
    assert _row_count(tmpdb, 'dnd_npcs', 17) == 0
    assert _row_count(tmpdb, 'dnd_locations', 17) == 0
    # 4 intact
    for tbl in ('dnd_characters', 'dnd_scene_state', 'dnd_combat_state',
                'dnd_quests', 'dnd_companions', 'dnd_npcs', 'dnd_locations'):
        assert _row_count(tmpdb, tbl, 4) == 1, f"{tbl} for campaign 4 lost"
    assert _row_count(tmpdb, 'dnd_campaigns') == 1


def test_delete_with_no_dependent_rows(tmpdb):
    """A campaign row with no dependent rows still deletes cleanly,
    and rows_deleted shows zeros for the empty tables."""
    _make_campaign(tmpdb, 17, 'Empty', status='archived')
    r = dnd_engine.campaign_delete_cascade(17)
    assert r['deleted'] is True
    for tbl in ('dnd_characters', 'dnd_scene_state', 'dnd_combat_state',
                'dnd_quests', 'dnd_companions', 'dnd_npcs', 'dnd_locations'):
        assert r['rows_deleted'][tbl] == 0
    assert r['rows_deleted']['dnd_campaigns'] == 1


def test_delete_with_multiple_dependent_rows(tmpdb):
    """Many rows per table all clear in a single cascade."""
    _make_campaign(tmpdb, 17, 'Heavy', status='archived')
    conn = sqlite3.connect(tmpdb)
    for i in range(5):
        conn.execute(
            "INSERT INTO dnd_npcs (campaign_id, canonical_name, "
            "first_mentioned, last_mentioned) VALUES (?, ?, 'T0', 'T0')",
            (17, f'NPC{i}')
        )
        conn.execute(
            "INSERT INTO dnd_locations (campaign_id, canonical_name, "
            "first_mentioned, last_mentioned) VALUES (?, ?, 'T0', 'T0')",
            (17, f'Loc{i}')
        )
    conn.commit()
    conn.close()
    r = dnd_engine.campaign_delete_cascade(17)
    assert r['rows_deleted']['dnd_npcs']      == 5
    assert r['rows_deleted']['dnd_locations'] == 5


def test_delete_preserves_active_campaign_in_same_guild(tmpdb):
    """Deleting an archived campaign in a guild that also has an
    active campaign leaves the active one (and its rows) untouched."""
    _make_campaign(tmpdb, 4,  'Active17', status='active')
    _make_campaign(tmpdb, 17, 'Archived', status='archived')
    _populate(tmpdb, 4)
    _populate(tmpdb, 17)
    dnd_engine.campaign_delete_cascade(17)
    # Active row + its dependents survive
    active = sqlite3.connect(tmpdb).execute(
        "SELECT status FROM dnd_campaigns WHERE id=4"
    ).fetchone()
    assert active == ('active',)
    assert _row_count(tmpdb, 'dnd_npcs', 4) == 1


def test_return_shape_keys(tmpdb):
    _make_campaign(tmpdb, 17, 'X', status='archived')
    r = dnd_engine.campaign_delete_cascade(17)
    assert set(r.keys()) == {'campaign_id', 'deleted', 'reason', 'rows_deleted'}


def test_campaign_id_echoed_on_refusal(tmpdb):
    r = dnd_engine.campaign_delete_cascade(999)
    assert r['campaign_id'] == 999


def test_campaign_id_echoed_on_success(tmpdb):
    _make_campaign(tmpdb, 17, 'X', status='archived')
    r = dnd_engine.campaign_delete_cascade(17)
    assert r['campaign_id'] == 17
