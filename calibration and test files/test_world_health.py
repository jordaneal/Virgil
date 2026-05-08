"""Unit tests for world_health_report (Ship 4 step 4).

Self-contained: builds dnd_locations + dnd_npcs tables (needed by
the npc_fragmentation_report it composes), monkeypatches
dnd_engine.DB_PATH per-test.
"""
import sqlite3
import sys
from pathlib import Path

import pytest

# Tests run from "calibration and test files/" — engine is one dir up.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import dnd_engine  # noqa: E402


# ─── Fixture ──────────────────────────────────────────────────────────────────

@pytest.fixture
def tmpdb(monkeypatch, tmp_path):
    """Per-test sqlite file with locations + NPCs tables.

    Schema mirrors production CREATE TABLE in dnd_engine.db_init().
    """
    db = tmp_path / "test_world_health.db"
    conn = sqlite3.connect(db)
    conn.executescript("""
        CREATE TABLE dnd_locations (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id         INTEGER NOT NULL,
            canonical_name      TEXT    NOT NULL,
            aliases             TEXT    DEFAULT '[]',
            type                TEXT    DEFAULT '',
            parent_location_id  INTEGER,
            description         TEXT    DEFAULT '',
            skeleton_origin     INTEGER DEFAULT 0,
            mention_count       INTEGER DEFAULT 0,
            origin_excerpt      TEXT    DEFAULT '',
            first_mentioned     TEXT    NOT NULL,
            last_mentioned      TEXT    NOT NULL,
            UNIQUE(campaign_id, canonical_name)
        );
        CREATE TABLE dnd_npcs (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id       INTEGER NOT NULL,
            canonical_name    TEXT    NOT NULL,
            aliases           TEXT    DEFAULT '[]',
            role              TEXT    DEFAULT '',
            location_id       INTEGER,
            description       TEXT    DEFAULT '',
            skeleton_origin   INTEGER DEFAULT 0,
            mention_count     INTEGER DEFAULT 0,
            origin_excerpt    TEXT    DEFAULT '',
            first_mentioned   TEXT    NOT NULL,
            last_mentioned    TEXT    NOT NULL,
            UNIQUE(campaign_id, canonical_name)
        );
        CREATE TABLE dnd_consequences (
            id                       INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id              INTEGER NOT NULL,
            npc_id                   INTEGER NOT NULL,
            kind                     TEXT    NOT NULL,
            summary                  TEXT    NOT NULL,
            severity                 INTEGER NOT NULL,
            sources                  TEXT    NOT NULL,
            captured_at              TEXT    NOT NULL,
            captured_turn            INTEGER NOT NULL,
            first_seen_turn          INTEGER NOT NULL,
            last_seen_turn           INTEGER NOT NULL,
            last_surfaced_at         TEXT,
            last_surfaced_turn       INTEGER,
            surface_count            INTEGER NOT NULL DEFAULT 0,
            distinct_surface_turns   INTEGER NOT NULL DEFAULT 0,
            status                   TEXT    NOT NULL DEFAULT 'active',
            promoted_at              TEXT,
            UNIQUE(campaign_id, npc_id, kind)
        );
    """)
    conn.commit()
    conn.close()
    monkeypatch.setattr(dnd_engine, 'DB_PATH', db)
    return db


def _ins_loc(db, campaign_id, name, first, last,
             skeleton_origin=0, mention_count=1):
    conn = sqlite3.connect(db)
    cur = conn.execute(
        "INSERT INTO dnd_locations "
        "(campaign_id, canonical_name, first_mentioned, last_mentioned, "
        " skeleton_origin, mention_count) VALUES (?, ?, ?, ?, ?, ?)",
        (campaign_id, name, first, last, skeleton_origin, mention_count)
    )
    conn.commit()
    rid = cur.lastrowid
    conn.close()
    return rid


def _ins_npc(db, campaign_id, name, first, last,
             skeleton_origin=0, mention_count=1):
    conn = sqlite3.connect(db)
    cur = conn.execute(
        "INSERT INTO dnd_npcs "
        "(campaign_id, canonical_name, first_mentioned, last_mentioned, "
        " skeleton_origin, mention_count) VALUES (?, ?, ?, ?, ?, ?)",
        (campaign_id, name, first, last, skeleton_origin, mention_count)
    )
    conn.commit()
    rid = cur.lastrowid
    conn.close()
    return rid


# ─── Tests ────────────────────────────────────────────────────────────────────

def test_empty_campaign_zero_everywhere(tmpdb):
    r = dnd_engine.world_health_report(17)
    assert r == {
        'campaign_id':            17,
        'npc_total':              0,
        'npc_distinct':           0,
        'npc_fragmentation_rate': 0.0,
        'loc_total':              0,
        'loc_skeleton':           0,
        'loc_skeleton_coverage':  0.0,
        'loc_phantoms':           0,
        'phantom_threshold':      3,
        'cons_active':            0,
        'cons_promoted':          0,
        'cons_never_surfaced':    0,
    }


def test_default_phantom_threshold_is_three(tmpdb):
    r = dnd_engine.world_health_report(17)
    assert r['phantom_threshold'] == 3


def test_custom_phantom_threshold_echoed(tmpdb):
    r = dnd_engine.world_health_report(17, phantom_threshold=8)
    assert r['phantom_threshold'] == 8


def test_locations_only_no_npcs(tmpdb):
    """Locations populated, NPCs empty: location metrics flow,
    NPC metrics zero out cleanly."""
    _ins_loc(tmpdb, 17, 'Stonebridge', 'T1', 'T1', skeleton_origin=1)
    _ins_loc(tmpdb, 17, 'Hollowmoor',  'T2', 'T2', skeleton_origin=1)
    r = dnd_engine.world_health_report(17)
    assert r['loc_total']             == 2
    assert r['loc_skeleton']          == 2
    assert r['loc_skeleton_coverage'] == 1.0
    assert r['loc_phantoms']          == 0
    assert r['npc_total']             == 0
    assert r['npc_distinct']          == 0
    assert r['npc_fragmentation_rate'] == 0.0


def test_npcs_only_no_locations(tmpdb):
    """NPCs populated, locations empty: NPC metrics flow,
    location metrics zero out (and coverage stays 0.0, no div-by-zero)."""
    _ins_npc(tmpdb, 17, 'Eldrin Stormbow', 'T1', 'T1', skeleton_origin=1)
    _ins_npc(tmpdb, 17, 'Lira Songheart',  'T2', 'T2', skeleton_origin=1)
    r = dnd_engine.world_health_report(17)
    assert r['npc_total']              == 2
    assert r['npc_distinct']           == 2
    assert r['npc_fragmentation_rate'] == 0.0
    assert r['loc_total']              == 0
    assert r['loc_skeleton']           == 0
    assert r['loc_skeleton_coverage']  == 0.0
    assert r['loc_phantoms']           == 0


def test_skeleton_coverage_partial(tmpdb):
    """7 skeleton + 2 parser = 78% coverage (matches campaign 17 today)."""
    for n in ['Stoneforge', 'Stonebridge', 'Old Trade Road', 'Redhaven',
              'Hollowmoor', 'Stumbling Stag', 'Whispering Woods']:
        _ins_loc(tmpdb, 17, n, 'T1', 'T1', skeleton_origin=1)
    _ins_loc(tmpdb, 17, 'Stormbridge', 'T2', 'T2')  # parser
    _ins_loc(tmpdb, 17, 'River Wynd',  'T3', 'T3')  # parser
    r = dnd_engine.world_health_report(17)
    assert r['loc_total']    == 9
    assert r['loc_skeleton'] == 7
    assert abs(r['loc_skeleton_coverage'] - (7 / 9)) < 1e-9


def test_skeleton_coverage_all_skeleton(tmpdb):
    _ins_loc(tmpdb, 17, 'A', 'T1', 'T1', skeleton_origin=1)
    _ins_loc(tmpdb, 17, 'B', 'T2', 'T2', skeleton_origin=1)
    r = dnd_engine.world_health_report(17)
    assert r['loc_skeleton_coverage'] == 1.0


def test_skeleton_coverage_all_parser(tmpdb):
    _ins_loc(tmpdb, 17, 'A', 'T1', 'T1')
    _ins_loc(tmpdb, 17, 'B', 'T2', 'T2')
    r = dnd_engine.world_health_report(17)
    assert r['loc_skeleton_coverage'] == 0.0


def test_phantom_count_flows_through(tmpdb):
    """phantom_location_candidates result is composed in unchanged."""
    _ins_loc(tmpdb, 17, 'Stormbridge', 'T1', 'T1')           # phantom-shaped
    _ins_loc(tmpdb, 17, 'A', 'T2', 'T2', skeleton_origin=1)  # filler
    _ins_loc(tmpdb, 17, 'B', 'T3', 'T3', skeleton_origin=1)
    _ins_loc(tmpdb, 17, 'C', 'T4', 'T4', skeleton_origin=1)
    r = dnd_engine.world_health_report(17, phantom_threshold=3)
    assert r['loc_phantoms'] == 1


def test_phantom_count_responds_to_threshold(tmpdb):
    """Same db, two thresholds → different phantom counts."""
    _ins_loc(tmpdb, 17, 'Stormbridge', 'T1', 'T1')
    _ins_loc(tmpdb, 17, 'A', 'T2', 'T2', skeleton_origin=1)
    _ins_loc(tmpdb, 17, 'B', 'T3', 'T3', skeleton_origin=1)
    _ins_loc(tmpdb, 17, 'C', 'T4', 'T4', skeleton_origin=1)
    low  = dnd_engine.world_health_report(17, phantom_threshold=3)
    high = dnd_engine.world_health_report(17, phantom_threshold=99)
    assert low['loc_phantoms']  == 1
    assert high['loc_phantoms'] == 0


def test_npc_fragmentation_flows_through(tmpdb):
    """Two-row cluster: 'Eldrin Stormbow' + 'Eldrin' → 1 distinct, 50% frag."""
    _ins_npc(tmpdb, 17, 'Eldrin Stormbow', 'T1', 'T2', mention_count=2)
    _ins_npc(tmpdb, 17, 'Eldrin',          'T3', 'T3')
    r = dnd_engine.world_health_report(17)
    assert r['npc_total']              == 2
    assert r['npc_distinct']           == 1
    assert r['npc_fragmentation_rate'] == 0.5


def test_cross_campaign_isolation(tmpdb):
    """Locations and NPCs from another campaign do not pollute the report."""
    _ins_loc(tmpdb, 17, 'Stonebridge', 'T1', 'T1', skeleton_origin=1)
    _ins_loc(tmpdb, 99, 'OtherWorld',  'T2', 'T2', skeleton_origin=1)
    _ins_npc(tmpdb, 17, 'Eldrin', 'T3', 'T3', skeleton_origin=1)
    _ins_npc(tmpdb, 99, 'Stranger', 'T4', 'T4', skeleton_origin=1)
    r = dnd_engine.world_health_report(17)
    assert r['loc_total'] == 1
    assert r['npc_total'] == 1
    assert r['campaign_id'] == 17


def test_return_shape_keys(tmpdb):
    r = dnd_engine.world_health_report(17)
    assert set(r.keys()) == {
        'campaign_id',
        'npc_total', 'npc_distinct', 'npc_fragmentation_rate',
        'loc_total', 'loc_skeleton', 'loc_skeleton_coverage',
        'loc_phantoms', 'phantom_threshold',
        'cons_active', 'cons_promoted', 'cons_never_surfaced',
    }


def test_consequence_health_empty(tmpdb):
    """No consequences captured = zero across the board, empty dicts."""
    r = dnd_engine.consequence_health_report(17)
    assert r == {
        'campaign_id':    17,
        'active':         0,
        'promoted':       0,
        'never_surfaced': 0,
        'by_kind':        {},
        'by_source':      {},
    }


def test_consequence_health_active_breakdown(tmpdb):
    """Insert active rows of multiple kinds + sources; verify counts."""
    import sqlite3
    # Need an NPC for the FK-style npc_id reference; insert minimal one.
    _ins_npc(tmpdb, 17, 'Garrick', 'T1', 'T1')
    _ins_npc(tmpdb, 17, 'Lira',    'T1', 'T1')
    conn = sqlite3.connect(tmpdb)
    rows = [
        # (npc_id, kind, sources, surface_count)
        (1, 'threat',   'player',     0),  # never surfaced
        (1, 'mercy',    'dm',         2),  # surfaced
        (2, 'threat',   'dm,player',  1),  # surfaced, dual-source
        (2, 'alliance', 'player',     0),  # never surfaced
    ]
    for npc_id, kind, sources, surf in rows:
        conn.execute(
            "INSERT INTO dnd_consequences "
            "(campaign_id, npc_id, kind, summary, severity, sources, "
            " captured_at, captured_turn, first_seen_turn, last_seen_turn, "
            " surface_count, distinct_surface_turns, status) "
            "VALUES (17, ?, ?, 's', 1, ?, 'T0', 0, 0, 0, ?, 0, 'active')",
            (npc_id, kind, sources, surf)
        )
    conn.commit()
    conn.close()
    r = dnd_engine.consequence_health_report(17)
    assert r['active'] == 4
    assert r['promoted'] == 0
    assert r['never_surfaced'] == 2
    assert r['by_kind'] == {'threat': 2, 'mercy': 1, 'alliance': 1}
    assert r['by_source'] == {'player': 2, 'dm': 1, 'dm,player': 1}


def test_consequence_health_promoted_excluded_from_active(tmpdb):
    """Promoted rows are counted separately, excluded from active breakdowns."""
    import sqlite3
    _ins_npc(tmpdb, 17, 'Reginald', 'T1', 'T1')
    conn = sqlite3.connect(tmpdb)
    conn.execute(
        "INSERT INTO dnd_consequences "
        "(campaign_id, npc_id, kind, summary, severity, sources, "
        " captured_at, captured_turn, first_seen_turn, last_seen_turn, "
        " surface_count, distinct_surface_turns, status, promoted_at) "
        "VALUES (17, 1, 'threat', 's', 2, 'player', 'T0', 0, 0, 0, 5, 3, 'promoted', 'T15')"
    )
    conn.commit()
    conn.close()
    r = dnd_engine.consequence_health_report(17)
    assert r['active'] == 0
    assert r['promoted'] == 1
    assert r['by_kind'] == {}
    assert r['by_source'] == {}


def test_consequence_health_cross_campaign_isolation(tmpdb):
    """A consequence on campaign 99 must not leak into campaign 17's report."""
    import sqlite3
    _ins_npc(tmpdb, 99, 'Other', 'T1', 'T1')
    conn = sqlite3.connect(tmpdb)
    conn.execute(
        "INSERT INTO dnd_consequences "
        "(campaign_id, npc_id, kind, summary, severity, sources, "
        " captured_at, captured_turn, first_seen_turn, last_seen_turn, "
        " surface_count, distinct_surface_turns, status) "
        "VALUES (99, 1, 'threat', 's', 1, 'player', 'T0', 0, 0, 0, 0, 0, 'active')"
    )
    conn.commit()
    conn.close()
    r = dnd_engine.consequence_health_report(17)
    assert r['active'] == 0
    r99 = dnd_engine.consequence_health_report(99)
    assert r99['active'] == 1


def test_world_health_composes_consequence_counts(tmpdb):
    """world_health_report includes the new cons_* fields, sourced from
    consequence_health_report."""
    import sqlite3
    _ins_npc(tmpdb, 17, 'Mira', 'T1', 'T1')
    conn = sqlite3.connect(tmpdb)
    conn.execute(
        "INSERT INTO dnd_consequences "
        "(campaign_id, npc_id, kind, summary, severity, sources, "
        " captured_at, captured_turn, first_seen_turn, last_seen_turn, "
        " surface_count, distinct_surface_turns, status) "
        "VALUES (17, 1, 'mercy', 's', 2, 'dm', 'T0', 0, 0, 0, 0, 0, 'active')"
    )
    conn.commit()
    conn.close()
    r = dnd_engine.world_health_report(17)
    assert r['cons_active']         == 1
    assert r['cons_promoted']       == 0
    assert r['cons_never_surfaced'] == 1


def test_campaign_17_realistic_state(tmpdb):
    """Realistic snapshot mirroring campaign 17 post-Session-12 (modulo
    turn proxy specifics, which we already cover separately).

    Locations: 7 skeleton + 2 parser-origin (Stormbridge phantom, River Wynd
    emergent), both with mention_count=1.
    NPCs: 3 skeleton (full names) + 3 parser (short forms).

    Expected:
      loc_total=9, loc_skeleton=7, coverage≈78%
      npc_total=6, distinct=3 (each short-form attaches to its long-form),
      frag_rate=50%.
      Phantom count flows from phantom_location_candidates at threshold=3.
    """
    # Skeleton locations
    for n in ['Stoneforge Guild Hall', 'Stonebridge', 'Old Trade Road',
              'Redhaven', 'Hollowmoor', 'Stumbling Stag', 'Whispering Woods']:
        _ins_loc(tmpdb, 17, n, 'T0', 'T0', skeleton_origin=1)
    # Parser locations — staggered first_mentioned so turns_since differs
    _ins_loc(tmpdb, 17, 'Stormbridge', 'T1', 'T1')
    _ins_loc(tmpdb, 17, 'River Wynd',  'T2', 'T2')

    # NPCs — long forms (skeleton) and short forms (parser)
    _ins_npc(tmpdb, 17, 'Eldrin Stormbow', 'T0', 'T0',
             skeleton_origin=1, mention_count=2)
    _ins_npc(tmpdb, 17, 'Lira Songheart',  'T0', 'T0',
             skeleton_origin=1, mention_count=2)
    _ins_npc(tmpdb, 17, 'Borin Ironhand',  'T0', 'T0',
             skeleton_origin=1, mention_count=2)
    _ins_npc(tmpdb, 17, 'Eldrin', 'T1', 'T1')
    _ins_npc(tmpdb, 17, 'Lira',   'T2', 'T2')
    _ins_npc(tmpdb, 17, 'Borin',  'T3', 'T3')

    r = dnd_engine.world_health_report(17)
    assert r['loc_total']             == 9
    assert r['loc_skeleton']          == 7
    assert abs(r['loc_skeleton_coverage'] - (7 / 9)) < 1e-9
    assert r['npc_total']              == 6
    assert r['npc_distinct']           == 3
    assert r['npc_fragmentation_rate'] == 0.5
