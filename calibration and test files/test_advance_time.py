"""Engine-layer tests for advance_time + dnd_time_advancements
(Track 4 #3, Session 27).

Per TRACK_4_3_SPEC.md §9 + §K extensions.
Per-test sqlite file via monkeypatch on dnd_engine.DB_PATH.

Run:
    cd /home/jordaneal/scripts && python3 -m pytest test_advance_time.py -q
"""

import sqlite3
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, '/home/jordaneal/scripts')
import dnd_engine  # noqa: E402


@pytest.fixture
def tmpdb(monkeypatch, tmp_path):
    """Per-test sqlite file with the schema advance_time touches."""
    db = tmp_path / "test_time.db"
    conn = sqlite3.connect(db)
    conn.executescript("""
        CREATE TABLE dnd_scene_state (
            campaign_id INTEGER PRIMARY KEY,
            mode TEXT DEFAULT 'exploration',
            updated_at TEXT DEFAULT '',
            campaign_day INTEGER DEFAULT 1,
            day_phase TEXT DEFAULT 'Morning'
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


def _seed_scene(db, cid, day=1, phase='Morning'):
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO dnd_scene_state (campaign_id, campaign_day, day_phase, "
        "updated_at) VALUES (?, ?, ?, '')",
        (cid, day, phase)
    )
    conn.commit()
    conn.close()


def _read_state(db, cid):
    conn = sqlite3.connect(db)
    row = conn.execute(
        "SELECT campaign_day, day_phase FROM dnd_scene_state WHERE campaign_id=?",
        (cid,)
    ).fetchone()
    conn.close()
    return (row[0], row[1]) if row else None


def _log_count(db, cid):
    conn = sqlite3.connect(db)
    n = conn.execute(
        "SELECT COUNT(*) FROM dnd_time_advancements WHERE campaign_id=?",
        (cid,)
    ).fetchone()[0]
    conn.close()
    return n


def _last_log(db, cid):
    conn = sqlite3.connect(db)
    row = conn.execute(
        "SELECT before_day, before_phase, after_day, after_phase, "
        "days_delta, phase_delta, resolved_phase_delta, set_phase, "
        "source, source_detail FROM dnd_time_advancements "
        "WHERE campaign_id=? ORDER BY id DESC LIMIT 1",
        (cid,)
    ).fetchone()
    conn.close()
    return row


# ─── Basic advance ───────────────────────────────────────────────

def test_one_day_morning_to_morning(tmpdb):
    _seed_scene(tmpdb, 1)
    r = dnd_engine.advance_time(1, 1, 0, 'travel', '')
    assert r is not None
    assert (r.before_day, r.before_phase) == (1, 'Morning')
    assert (r.after_day, r.after_phase) == (2, 'Morning')
    assert _read_state(tmpdb, 1) == (2, 'Morning')


def test_short_rest_phase_bump(tmpdb):
    _seed_scene(tmpdb, 1)
    dnd_engine.advance_time(1, 0, 1, 'rest_short', '')
    assert _read_state(tmpdb, 1) == (1, 'Midday')


def test_full_cycle_wraps_day(tmpdb):
    _seed_scene(tmpdb, 1)
    r = dnd_engine.advance_time(1, 0, 6, 'advance', '')
    assert (r.after_day, r.after_phase) == (2, 'Morning')


def test_seven_phases_wraps_to_midday(tmpdb):
    _seed_scene(tmpdb, 1)
    r = dnd_engine.advance_time(1, 0, 7, 'advance', '')
    assert (r.after_day, r.after_phase) == (2, 'Midday')


def test_combined_deltas(tmpdb):
    _seed_scene(tmpdb, 1)
    r = dnd_engine.advance_time(1, 2, 3, 'travel', '')
    assert (r.after_day, r.after_phase) == (3, 'Evening')


# ─── Phase rollover ──────────────────────────────────────────────

def test_late_night_plus_one_to_morning_next_day(tmpdb):
    _seed_scene(tmpdb, 1, phase='Late Night')
    r = dnd_engine.advance_time(1, 0, 1, 'rest_short', '')
    assert (r.after_day, r.after_phase) == (2, 'Morning')


def test_night_plus_three_to_midday(tmpdb):
    _seed_scene(tmpdb, 1, phase='Night')
    r = dnd_engine.advance_time(1, 0, 3, 'advance', '')
    assert (r.after_day, r.after_phase) == (2, 'Midday')


# ─── Validation ──────────────────────────────────────────────────

def test_negative_days_rejected(tmpdb):
    _seed_scene(tmpdb, 1)
    assert dnd_engine.advance_time(1, -1, 0, 'travel', '') is None
    assert _read_state(tmpdb, 1) == (1, 'Morning')


def test_unknown_source_rejected(tmpdb):
    _seed_scene(tmpdb, 1)
    assert dnd_engine.advance_time(1, 1, 0, 'unknown', '') is None


def test_zero_zero_rejected(tmpdb):
    _seed_scene(tmpdb, 1)
    assert dnd_engine.advance_time(1, 0, 0, 'advance', '') is None


def test_no_scene_state_returns_none(tmpdb):
    # No row inserted for campaign=99
    assert dnd_engine.advance_time(99, 1, 0, 'travel', '') is None


def test_invalid_set_phase_rejected(tmpdb):
    _seed_scene(tmpdb, 1)
    assert dnd_engine.advance_time(1, 1, 0, 'travel', '',
                                   set_phase='Twilight') is None


# ─── Persistence ─────────────────────────────────────────────────

def test_state_reflected_after_advance(tmpdb):
    _seed_scene(tmpdb, 1)
    dnd_engine.advance_time(1, 1, 2, 'travel', 'detail')
    assert _read_state(tmpdb, 1) == (2, 'Afternoon')


def test_log_row_after_advance(tmpdb):
    _seed_scene(tmpdb, 1)
    dnd_engine.advance_time(1, 1, 2, 'travel', 'Redhaven')
    row = _last_log(tmpdb, 1)
    assert row[0] == 1 and row[1] == 'Morning'
    assert row[2] == 2 and row[3] == 'Afternoon'
    assert row[8] == 'travel'
    assert row[9] == 'Redhaven'


def test_two_advances_two_log_rows(tmpdb):
    _seed_scene(tmpdb, 1)
    dnd_engine.advance_time(1, 1, 0, 'travel', '')
    dnd_engine.advance_time(1, 0, 1, 'rest_short', '')
    assert _log_count(tmpdb, 1) == 2


def test_no_log_row_on_validation_failure(tmpdb):
    _seed_scene(tmpdb, 1)
    dnd_engine.advance_time(1, -1, 0, 'travel', '')
    assert _log_count(tmpdb, 1) == 0


def test_no_log_row_on_missing_scene_state(tmpdb):
    # advance_time on missing campaign — no log row written.
    dnd_engine.advance_time(42, 1, 0, 'travel', '')
    assert _log_count(tmpdb, 42) == 0


# ─── set_phase precedence (§11.I) ───────────────────────────────

def test_set_phase_only(tmpdb):
    _seed_scene(tmpdb, 1, phase='Morning')
    r = dnd_engine.advance_time(1, 1, 0, 'rest_long', 'lr',
                                set_phase='Morning')
    # +1 day, set_phase=Morning, current was Morning → resolved_delta=0
    assert (r.after_day, r.after_phase) == (2, 'Morning')
    assert r.resolved_phase_delta == 0
    assert r.set_phase == 'Morning'


def test_set_phase_evening_to_morning_long_rest(tmpdb):
    _seed_scene(tmpdb, 1, phase='Evening')
    # Long rest from Evening → next Morning. days_delta=1 means jump
    # one full day, set_phase='Morning' wins. Evening idx=3, Morning
    # idx=0; resolved_delta = (0-3) mod 6 = 3.
    r = dnd_engine.advance_time(1, 1, 0, 'rest_long', 'lr',
                                set_phase='Morning')
    # before idx 3 + resolved 3 + 1*6 = 12 → day +2, phase 0
    assert (r.after_day, r.after_phase) == (3, 'Morning')
    assert r.resolved_phase_delta == 3


def test_set_phase_wins_over_phase_delta(tmpdb):
    _seed_scene(tmpdb, 1, phase='Morning')
    # Pass both — set_phase should win, phase_delta should be ignored
    # in the math but still recorded in the log row.
    r = dnd_engine.advance_time(1, 0, 99, 'advance', 'both',
                                set_phase='Evening')
    assert r.set_phase == 'Evening'
    assert r.phase_delta == 99
    assert r.resolved_phase_delta == 3  # Morning(0) → Evening(3)
    assert (r.after_day, r.after_phase) == (1, 'Evening')


def test_set_phase_log_carries_all_three_values(tmpdb):
    _seed_scene(tmpdb, 1, phase='Morning')
    dnd_engine.advance_time(1, 0, 7, 'advance', '', set_phase='Evening')
    row = _last_log(tmpdb, 1)
    # phase_delta=7 (caller's value), resolved=3, set_phase='Evening'.
    assert row[5] == 7
    assert row[6] == 3
    assert row[7] == 'Evening'


# ─── Cascade integrity (§4 + §K) ─────────────────────────────────

def test_dnd_time_advancements_in_campaign_scoped_tables():
    """The new table must be in _CAMPAIGN_SCOPED_TABLES so /purgecampaign
    cascades clean it up. Per VIRGIL_MASTER §6 hard requirement."""
    assert 'dnd_time_advancements' in dnd_engine._CAMPAIGN_SCOPED_TABLES


# ─── Large phase_delta (§K test extensions) ──────────────────────

def test_phase_delta_12_full_two_days_same_phase(tmpdb):
    _seed_scene(tmpdb, 1, phase='Afternoon')
    r = dnd_engine.advance_time(1, 0, 12, 'advance', '')
    # 12 phases = 2 full cycles → +2 days, same phase.
    assert (r.after_day, r.after_phase) == (3, 'Afternoon')


def test_phase_delta_13_from_morning(tmpdb):
    _seed_scene(tmpdb, 1, phase='Morning')
    r = dnd_engine.advance_time(1, 0, 13, 'advance', '')
    # 13 phases from Morning(0) → idx=13; +2 days, phase idx=1=Midday
    assert (r.after_day, r.after_phase) == (3, 'Midday')


def test_phase_delta_25_from_evening(tmpdb):
    _seed_scene(tmpdb, 1, phase='Evening')
    r = dnd_engine.advance_time(1, 0, 25, 'advance', '')
    # Evening idx=3 + 25 = 28; 28 // 6 = 4 days, 28 % 6 = 4 = Night
    assert (r.after_day, r.after_phase) == (5, 'Night')


# ─── time_just_advanced recency check ─────────────────────────────

def test_just_advanced_true_immediately_after(tmpdb):
    _seed_scene(tmpdb, 1)
    dnd_engine.advance_time(1, 1, 0, 'travel', '')
    assert dnd_engine.time_just_advanced(1) is True


def test_just_advanced_false_for_no_advance(tmpdb):
    _seed_scene(tmpdb, 1)
    assert dnd_engine.time_just_advanced(1) is False


def test_just_advanced_window_zero_returns_false(tmpdb):
    _seed_scene(tmpdb, 1)
    dnd_engine.advance_time(1, 1, 0, 'travel', '')
    time.sleep(0.05)
    # window=0 means "not within the last 0 seconds" — should be False
    # for a row >0s old. Some clock fuzz tolerated.
    assert dnd_engine.time_just_advanced(1, window_seconds=0) is False


# ─── Telemetry contract — no_scene_state log line ───────────────

def test_missing_scene_state_logs_diagnostic(tmpdb, capsys):
    dnd_engine.advance_time(404, 1, 0, 'travel', '')
    captured = capsys.readouterr()
    # The function logs via dnd_engine.log() which prints to stdout.
    assert 'no scene_state row' in captured.out
