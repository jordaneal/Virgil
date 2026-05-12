"""Tests for the skeleton.md `## Starting time` seed-write path
(Track 4 #3, Session 27).

Per TRACK_4_3_SPEC.md §11.D=a + §J.3 narrow-§17 exception.

Run:
    cd /home/jordaneal/scripts && python3 -m pytest test_time_skeleton_seed.py -q
"""

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, '/home/jordaneal/scripts')

import dnd_engine  # noqa: E402
import skeleton_loader  # noqa: E402


@pytest.fixture
def tmpenv(monkeypatch, tmp_path):
    """Per-test sqlite + skeleton path."""
    db = tmp_path / "seed.db"
    conn = sqlite3.connect(db)
    # Ship 2 (S39) — schema mirrors production post-§76 deletion. Eight
    # columns removed (see SCENE_STATE_CANON_SPEC.md §6.1 audit table):
    # location, established_details, focus, open_questions, last_scene_change,
    # active_npcs, active_threats, and legacy tension.
    conn.executescript("""
        CREATE TABLE dnd_scene_state (
            campaign_id INTEGER PRIMARY KEY,
            mode TEXT DEFAULT 'exploration',
            last_player_action TEXT DEFAULT '',
            updated_at TEXT DEFAULT '',
            tension_int INTEGER DEFAULT 0,
            progress_clocks TEXT DEFAULT '[]',
            last_dm_response TEXT DEFAULT '',
            current_location_id INTEGER DEFAULT NULL,
            turn_counter INTEGER DEFAULT 0,
            last_active_actor TEXT DEFAULT '',
            campaign_day INTEGER DEFAULT 1,
            day_phase TEXT DEFAULT 'Morning'
        );
    """)
    conn.commit()
    conn.close()
    monkeypatch.setattr(dnd_engine, 'DB_PATH', db)
    monkeypatch.setattr(skeleton_loader, 'SKELETON_ROOT', tmp_path)
    # Clear the loader's parsed cache so each test starts clean.
    with skeleton_loader._cache_lock:
        skeleton_loader._cache.clear()
    return tmp_path


def _seed_scene(db, cid, day=1, phase='Morning'):
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO dnd_scene_state (campaign_id, campaign_day, day_phase, "
        "updated_at) VALUES (?, ?, ?, '')",
        (cid, day, phase)
    )
    conn.commit()
    conn.close()


def _write_skel(root, cid, body):
    d = Path(root) / str(cid)
    d.mkdir(parents=True, exist_ok=True)
    (d / 'skeleton.md').write_text(body)


# ─── Parse-only tests ───────────────────────────────────────────

def test_starting_time_section_parses(tmpenv):
    _write_skel(tmpenv, 5, "# Campaign: Test\n\n## Starting time\nday=15\nphase=Evening\n")
    parsed = skeleton_loader.parse_skeleton_file(5, force_reload=True)
    assert parsed['starting_time'] == {'day': 15, 'phase': 'Evening'}


def test_no_starting_time_section_returns_none(tmpenv):
    _write_skel(tmpenv, 6, "# Campaign: Test\n\n## Major hooks\n- A hook\n")
    parsed = skeleton_loader.parse_skeleton_file(6, force_reload=True)
    assert parsed['starting_time'] is None


def test_invalid_phase_silently_dropped(tmpenv):
    _write_skel(tmpenv, 7, "# Campaign: Test\n\n## Starting time\nday=2\nphase=Twilight\n")
    parsed = skeleton_loader.parse_skeleton_file(7, force_reload=True)
    # day still parses; phase is silently dropped (not in canonical list)
    assert parsed['starting_time'] == {'day': 2}


def test_phase_case_insensitive_normalized(tmpenv):
    _write_skel(tmpenv, 8, "# Campaign: Test\n\n## Starting time\nphase=late night\n")
    parsed = skeleton_loader.parse_skeleton_file(8, force_reload=True)
    assert parsed['starting_time'] == {'phase': 'Late Night'}


# ─── Seed-write integration tests ───────────────────────────────

def test_seed_writes_when_scene_at_defaults(tmpenv):
    _write_skel(tmpenv, 10, "# Campaign: Test\n\n## Starting time\nday=15\nphase=Evening\n")
    _seed_scene(tmpenv / 'seed.db' if False else dnd_engine.DB_PATH, 10)
    out = skeleton_loader.apply_starting_time_seed(10)
    assert out['status'] == 'ok'
    assert out['day'] == 15
    assert out['phase'] == 'Evening'
    state = dnd_engine.get_scene_state(10)
    assert state['campaign_day'] == 15
    assert state['day_phase'] == 'Evening'


def test_seed_skipped_when_clock_already_advanced(tmpenv):
    _write_skel(tmpenv, 11, "# Campaign: Test\n\n## Starting time\nday=15\nphase=Evening\n")
    _seed_scene(dnd_engine.DB_PATH, 11, day=3, phase='Afternoon')
    out = skeleton_loader.apply_starting_time_seed(11)
    assert out['status'] == 'skipped_already_advanced'
    state = dnd_engine.get_scene_state(11)
    # Lived state wins.
    assert state['campaign_day'] == 3
    assert state['day_phase'] == 'Afternoon'


def test_seed_no_section_status(tmpenv):
    _write_skel(tmpenv, 12, "# Campaign: Test\n\n## Major hooks\n- A hook\n")
    _seed_scene(dnd_engine.DB_PATH, 12)
    out = skeleton_loader.apply_starting_time_seed(12)
    assert out['status'] == 'no_section'
    state = dnd_engine.get_scene_state(12)
    # Defaults preserved.
    assert state['campaign_day'] == 1
    assert state['day_phase'] == 'Morning'


def test_seed_no_scene_state(tmpenv):
    _write_skel(tmpenv, 13, "# Campaign: Test\n\n## Starting time\nday=15\nphase=Evening\n")
    # No scene_state row — seed declines to write (initialization order
    # contract: caller calls init_scene_state first).
    out = skeleton_loader.apply_starting_time_seed(13)
    assert out['status'] == 'no_scene_state'


def test_seed_does_not_write_audit_log_row(tmpenv):
    """§J.3 narrow §17 exception — initialization is NOT an advancement
    event; the seed writes scene_state directly without appending to
    dnd_time_advancements."""
    # Build the audit-log table so the existence-check is meaningful.
    conn = sqlite3.connect(dnd_engine.DB_PATH)
    conn.executescript("""
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
    _write_skel(tmpenv, 14, "# Campaign: Test\n\n## Starting time\nday=7\nphase=Night\n")
    _seed_scene(dnd_engine.DB_PATH, 14)
    skeleton_loader.apply_starting_time_seed(14)
    conn = sqlite3.connect(dnd_engine.DB_PATH)
    n = conn.execute(
        "SELECT COUNT(*) FROM dnd_time_advancements WHERE campaign_id=?",
        (14,)
    ).fetchone()[0]
    conn.close()
    assert n == 0
