"""Unit tests for phantom_location_candidates (Ship 4 step 1).

Self-contained: builds just the dnd_locations table the function reads,
monkeypatches dnd_engine.DB_PATH per-test. No other engine state needed.
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
    """Per-test sqlite file with just the dnd_locations table.

    Schema mirrors the production CREATE in dnd_engine.db_init() —
    only the columns this function reads are required, but the full
    shape is reproduced so insert helpers behave like the real path.
    """
    db = tmp_path / "test_phantom.db"
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
    """)
    conn.commit()
    conn.close()
    monkeypatch.setattr(dnd_engine, 'DB_PATH', db)
    return db


def _insert(db, campaign_id, name, first, last,
            skeleton_origin=0, mention_count=1):
    """Direct INSERT — bypasses location_upsert because we want exact
    control over first_mentioned / last_mentioned / counts for the
    edge cases under test."""
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


# ─── Tests ────────────────────────────────────────────────────────────────────

def test_empty_campaign_returns_zero(tmpdb):
    r = dnd_engine.phantom_location_candidates(17)
    assert r == {'threshold': 3, 'count': 0, 'candidates': []}


def test_default_threshold_is_three(tmpdb):
    _insert(tmpdb, 17, 'Phantom', 'T1', 'T1')
    _insert(tmpdb, 17, 'Other1',  'T2', 'T2', skeleton_origin=1)
    _insert(tmpdb, 17, 'Other2',  'T3', 'T3', skeleton_origin=1)
    _insert(tmpdb, 17, 'Other3',  'T4', 'T4', skeleton_origin=1)
    r = dnd_engine.phantom_location_candidates(17)  # no threshold arg
    assert r['threshold'] == 3
    assert r['count'] == 1


def test_only_skeleton_rows_no_candidates(tmpdb):
    _insert(tmpdb, 17, 'Stonebridge', 'T1', 'T1', skeleton_origin=1)
    _insert(tmpdb, 17, 'Hollowmoor',  'T2', 'T2', skeleton_origin=1)
    _insert(tmpdb, 17, 'Redhaven',    'T3', 'T3', skeleton_origin=1)
    _insert(tmpdb, 17, 'Whispering',  'T4', 'T4', skeleton_origin=1)
    r = dnd_engine.phantom_location_candidates(17, threshold=1)
    assert r['count'] == 0


def test_skeleton_origin_excluded(tmpdb):
    """skeleton_origin=1 row: even with everything else matching the
    candidate shape, never flags. Authored canon is not phantom."""
    _insert(tmpdb, 17, 'AuthoredButLonely', 'T1', 'T1', skeleton_origin=1)
    _insert(tmpdb, 17, 'Other1', 'T2', 'T2', skeleton_origin=1)
    _insert(tmpdb, 17, 'Other2', 'T3', 'T3', skeleton_origin=1)
    _insert(tmpdb, 17, 'Other3', 'T4', 'T4', skeleton_origin=1)
    r = dnd_engine.phantom_location_candidates(17, threshold=3)
    assert r['count'] == 0


def test_mention_count_above_one_excluded(tmpdb):
    """Row with mention_count > 1 has been re-referenced — it earned
    its place. Not a phantom. Filler rows are skeleton_origin=1 so
    they're not themselves candidates that could pollute the count."""
    _insert(tmpdb, 17, 'StonebridgeIsh', 'T1', 'T9', mention_count=8)
    _insert(tmpdb, 17, 'Other1', 'T2', 'T2', skeleton_origin=1)
    _insert(tmpdb, 17, 'Other2', 'T3', 'T3', skeleton_origin=1)
    _insert(tmpdb, 17, 'Other3', 'T4', 'T4', skeleton_origin=1)
    r = dnd_engine.phantom_location_candidates(17, threshold=3)
    assert r['count'] == 0


def test_single_row_no_others_zero_turns(tmpdb):
    """A single phantom-shaped row with no other locations to compare
    against has turns_since=0 and never flags above threshold>=1."""
    _insert(tmpdb, 17, 'Stormbridge', 'T1', 'T1')
    r = dnd_engine.phantom_location_candidates(17, threshold=1)
    assert r['count'] == 0


def test_threshold_edge_equal_flags(tmpdb):
    """Exactly N other locations → flags at threshold=N (>= comparison)."""
    _insert(tmpdb, 17, 'Stormbridge', 'T1', 'T1')
    _insert(tmpdb, 17, 'Other1', 'T2', 'T2', skeleton_origin=1)
    _insert(tmpdb, 17, 'Other2', 'T3', 'T3', skeleton_origin=1)
    _insert(tmpdb, 17, 'Other3', 'T4', 'T4', skeleton_origin=1)
    r = dnd_engine.phantom_location_candidates(17, threshold=3)
    assert r['count'] == 1
    assert r['candidates'][0]['name']        == 'Stormbridge'
    assert r['candidates'][0]['turns_since'] == 3


def test_threshold_edge_below_no_flag(tmpdb):
    """N-1 other locations → does not flag at threshold=N."""
    _insert(tmpdb, 17, 'Stormbridge', 'T1', 'T1')
    _insert(tmpdb, 17, 'Other1', 'T2', 'T2', skeleton_origin=1)
    _insert(tmpdb, 17, 'Other2', 'T3', 'T3', skeleton_origin=1)
    r = dnd_engine.phantom_location_candidates(17, threshold=3)
    assert r['count'] == 0


def test_distinct_locations_not_chattiness(tmpdb):
    """A row that gets re-mentioned many times is still ONE distinct
    other location. Schema is one-row-per-location with last_mentioned
    bumped in place. Heavy re-mention does not inflate the count."""
    _insert(tmpdb, 17, 'Stormbridge', 'T1', 'T1')          # candidate
    _insert(tmpdb, 17, 'BusyTown', 'T2', 'T9',
            skeleton_origin=1, mention_count=8)
    r = dnd_engine.phantom_location_candidates(17, threshold=2)
    # ONE other distinct row → turns_since=1 for Stormbridge → no flag
    assert r['count'] == 0


def test_cross_campaign_isolation(tmpdb):
    """Locations in another campaign do not count toward this
    campaign's turn proxy."""
    _insert(tmpdb, 17, 'Stormbridge', 'T1', 'T1')
    _insert(tmpdb, 99, 'OtherA', 'T2', 'T2')
    _insert(tmpdb, 99, 'OtherB', 'T3', 'T3')
    _insert(tmpdb, 99, 'OtherC', 'T4', 'T4')
    r = dnd_engine.phantom_location_candidates(17, threshold=1)
    assert r['count'] == 0  # Stormbridge sees zero other locations in c17


def test_returned_candidates_sorted_by_id(tmpdb):
    a = _insert(tmpdb, 17, 'Phantom_A', 'T1', 'T1')
    b = _insert(tmpdb, 17, 'Phantom_B', 'T2', 'T2')
    _insert(tmpdb, 17, 'Other1', 'T3', 'T3', skeleton_origin=1)
    _insert(tmpdb, 17, 'Other2', 'T4', 'T4', skeleton_origin=1)
    _insert(tmpdb, 17, 'Other3', 'T5', 'T5', skeleton_origin=1)
    r = dnd_engine.phantom_location_candidates(17, threshold=2)
    ids = [c['id'] for c in r['candidates']]
    assert ids == [a, b]


def test_phantom_and_emergent_both_flag(tmpdb):
    """The metric does NOT distinguish phantom from emergent — that
    is the design. Stormbridge (typo) and River Wynd (real geography)
    are structurally identical: skeleton_origin=0, mention_count=1.
    Both flag. The human reads the names and judges."""
    _insert(tmpdb, 17, 'Stonebridge',     'T1', 'T9',
            skeleton_origin=1, mention_count=8)
    _insert(tmpdb, 17, 'Stormbridge',     'T2', 'T2')   # phantom
    _insert(tmpdb, 17, 'Hollowmoor',      'T3', 'T3', skeleton_origin=1)
    _insert(tmpdb, 17, 'River Wynd',      'T4', 'T4')   # emergent
    _insert(tmpdb, 17, 'Stumbling Stag',  'T5', 'T5', skeleton_origin=1)
    _insert(tmpdb, 17, 'Whispering Wood', 'T6', 'T6', skeleton_origin=1)
    r = dnd_engine.phantom_location_candidates(17, threshold=2)
    names = [c['name'] for c in r['candidates']]
    assert 'Stormbridge' in names
    assert 'River Wynd'  in names
    assert r['count'] == 2


def test_return_shape_includes_threshold_and_count(tmpdb):
    r = dnd_engine.phantom_location_candidates(17, threshold=5)
    assert r['threshold']  == 5
    assert r['count']      == 0
    assert r['candidates'] == []


def test_candidate_dict_has_expected_keys(tmpdb):
    _insert(tmpdb, 17, 'Stormbridge', 'T1', 'T1')
    _insert(tmpdb, 17, 'Other1', 'T2', 'T2', skeleton_origin=1)
    _insert(tmpdb, 17, 'Other2', 'T3', 'T3', skeleton_origin=1)
    _insert(tmpdb, 17, 'Other3', 'T4', 'T4', skeleton_origin=1)
    r = dnd_engine.phantom_location_candidates(17, threshold=3)
    c = r['candidates'][0]
    assert set(c.keys()) == {'id', 'name', 'first_mentioned', 'turns_since'}


def test_high_threshold_filters_everything(tmpdb):
    _insert(tmpdb, 17, 'Phantom', 'T1', 'T1')
    _insert(tmpdb, 17, 'Other1',  'T2', 'T2', skeleton_origin=1)
    _insert(tmpdb, 17, 'Other2',  'T3', 'T3', skeleton_origin=1)
    r = dnd_engine.phantom_location_candidates(17, threshold=99)
    assert r['count'] == 0
    assert r['threshold'] == 99
