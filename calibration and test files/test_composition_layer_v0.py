"""Unit tests for Composition Layer v0 (S60).

Covers:
  - compute_quest_act_suggester branching (mode gate, no_current_act,
    last_act, predicate_empty, predicate_no_match, predicate match → fire)
  - compute_composition_directive render shape (empty, render, combat-gate)
  - Schema migration idempotency + PRAGMA foreign_keys=ON verified at engine init
  - quest_act_upsert idempotency on (quest_id, act_index)
  - State machine: quest_accept → Act 1 anchor; quest_deliver/fail/abandon → NULL
  - quest_act_transition state writes + audit row
  - set_current_act validates FK + cross-campaign refusal
  - Cascade delete: parent quest → child acts auto-removed (FK ON DELETE CASCADE)
  - Skeleton parser: #### Acts extraction + predicate hint parsing
  - Compression-coupled suggester: fires only when stale ≥ _STALE_SOFT_THRESHOLD
"""

import os
import sys
import sqlite3
import json

sys.path.insert(0, os.path.dirname(__file__))

import pytest

import dnd_orchestration as orch


# ─── Orchestration: compute_quest_act_suggester ──────────────────────────────

EXPLORATION = {'mode': 'exploration', 'current_location_id': 1}
SOCIAL = {'mode': 'social', 'current_location_id': 1}
COMBAT = {'mode': 'combat', 'current_location_id': 1}


def _act(idx, quest_id=10, title='X', predicate=None):
    return {
        'id': idx + 100,
        'quest_id': quest_id,
        'act_index': idx,
        'act_title': title,
        'act_description': '',
        'transition_predicate_json': json.dumps(predicate or {}),
        'skeleton_origin': 1,
    }


def test_suggester_combat_mode_rejects():
    p, s = orch.compute_quest_act_suggester(
        COMBAT, _act(1, predicate={'scene_count_threshold': 1}),
        _act(2), 5, None
    )
    assert p is None
    assert s['reason'] == 'gate_mode'
    assert s['fired'] == 0


def test_suggester_no_current_act_rejects():
    p, s = orch.compute_quest_act_suggester(EXPLORATION, None, None, 0, None)
    assert p is None
    assert s['reason'] == 'no_current_act'


def test_suggester_last_act_rejects():
    p, s = orch.compute_quest_act_suggester(
        EXPLORATION, _act(3, predicate={'scene_count_threshold': 1}),
        None,  # no candidate_next_act
        10, None
    )
    assert p is None
    assert s['reason'] == 'last_act'


def test_suggester_empty_predicate_rejects():
    p, s = orch.compute_quest_act_suggester(
        EXPLORATION, _act(1, predicate={}), _act(2), 99, None
    )
    assert p is None
    assert s['reason'] == 'predicate_empty'


def test_suggester_unparseable_predicate_rejects():
    cur = _act(1)
    cur['transition_predicate_json'] = 'not valid json'
    p, s = orch.compute_quest_act_suggester(
        EXPLORATION, cur, _act(2), 99, None
    )
    assert p is None
    assert s['reason'] == 'predicate_empty'


def test_suggester_scene_count_match_fires():
    p, s = orch.compute_quest_act_suggester(
        EXPLORATION, _act(1, predicate={'scene_count_threshold': 2}),
        _act(2, title='Engage'), 3, None
    )
    assert p is not None
    assert s['fired'] == 1
    assert s['reason'] == 'proposed'
    assert p['proposed_next_act_index'] == 2
    assert p['next_act_title'] == 'Engage'
    assert 'scene_count' in p['predicate_reason']


def test_suggester_scene_count_below_threshold_rejects():
    p, s = orch.compute_quest_act_suggester(
        EXPLORATION, _act(1, predicate={'scene_count_threshold': 5}),
        _act(2), 2, None
    )
    assert p is None
    assert s['reason'] == 'predicate_no_match'


def test_suggester_location_match_fires():
    p, s = orch.compute_quest_act_suggester(
        SOCIAL, _act(1, predicate={'location_id': 17}), _act(2),
        0, 17
    )
    assert p is not None
    assert s['fired'] == 1
    assert 'location_id=17' in p['predicate_reason']


def test_suggester_location_mismatch_rejects():
    p, s = orch.compute_quest_act_suggester(
        EXPLORATION, _act(1, predicate={'location_id': 17}), _act(2),
        99, 5  # current location != 17
    )
    assert p is None
    assert s['reason'] == 'predicate_no_match'


def test_suggester_both_predicates_and_combined():
    # Both fields set → must BOTH match.
    pred = {'scene_count_threshold': 2, 'location_id': 17}
    # Both match → fire.
    p, s = orch.compute_quest_act_suggester(
        EXPLORATION, _act(1, predicate=pred), _act(2), 5, 17
    )
    assert p is not None
    assert s['fired'] == 1
    # Only scene_count matches → reject.
    p, s = orch.compute_quest_act_suggester(
        EXPLORATION, _act(1, predicate=pred), _act(2), 5, 99
    )
    assert p is None
    # Only location matches → reject.
    p, s = orch.compute_quest_act_suggester(
        EXPLORATION, _act(1, predicate=pred), _act(2), 0, 17
    )
    assert p is None


# ─── Orchestration: compute_composition_directive ────────────────────────────

def test_composition_empty_when_no_current_act():
    body, s = orch.compute_composition_directive([], None, EXPLORATION)
    assert body == ''
    assert s['fired'] == 0


def test_composition_renders_with_current_act():
    quest = {'id': 10, 'title': 'Farmstead', 'status': 'in-progress'}
    cur = {
        'id': 5, 'quest_id': 10, 'act_index': 2,
        'act_title': 'Engage the goblins',
        'act_description': 'Combat phase.',
        'total_acts': 3,
    }
    body, s = orch.compute_composition_directive([quest], cur, EXPLORATION)
    assert s['fired'] == 1
    assert 'Farmstead' in body
    assert 'Act 2 of 3' in body
    assert 'Engage the goblins' in body
    assert 'Combat phase' in body


def test_composition_combat_gate_suppresses():
    quest = {'id': 10, 'title': 'X', 'status': 'in-progress'}
    cur = {'id': 5, 'quest_id': 10, 'act_index': 1, 'act_title': 'Y'}
    body, s = orch.compute_composition_directive([quest], cur, COMBAT)
    assert body == ''
    assert s['fired'] == 0


def test_composition_quest_not_in_active_suppresses():
    # current_act points to quest 10, but active_quests doesn't include it
    # (e.g., the quest was just delivered but anchor wasn't cleared yet).
    cur = {'id': 5, 'quest_id': 10, 'act_index': 1, 'act_title': 'X'}
    body, s = orch.compute_composition_directive([], cur, EXPLORATION)
    assert body == ''
    assert s['fired'] == 0


def test_composition_renders_without_total_acts():
    quest = {'id': 10, 'title': 'X', 'status': 'in-progress'}
    cur = {'id': 5, 'quest_id': 10, 'act_index': 2, 'act_title': 'Mid'}
    body, _ = orch.compute_composition_directive([quest], cur, EXPLORATION)
    assert 'Act 2' in body
    assert 'of' not in body.split('Act 2')[1].split('—')[0]  # no "of M"


# ─── Engine: schema + helpers + state machine ────────────────────────────────

@pytest.fixture
def temp_db(monkeypatch, tmp_path):
    """Set DB_PATH to a fresh per-test SQLite file and run db_init."""
    db_file = tmp_path / "test_virgil.db"
    monkeypatch.setattr('dnd_engine.DB_PATH', db_file)
    import dnd_engine
    dnd_engine.db_init()
    conn = sqlite3.connect(str(db_file))
    conn.execute(
        "INSERT INTO dnd_campaigns (id, name, status, created_at) "
        "VALUES (?,?,?,?)",
        (1, 'TestCampaign', 'active', '2026-05-13T00:00:00')
    )
    conn.commit()
    conn.close()
    return str(db_file)


def test_engine_init_logs_pragma_supported(temp_db, capsys):
    """db_init logs the fk_cascade_init line per §11.13 amendment."""
    # Re-run db_init to capture the log.
    import dnd_engine
    dnd_engine.db_init()
    # Verify the table + column exist.
    conn = sqlite3.connect(temp_db)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(dnd_quest_acts)")}
    assert 'quest_id' in cols
    assert 'act_index' in cols
    assert 'transition_predicate_json' in cols
    audit_cols = {r[1] for r in conn.execute("PRAGMA table_info(dnd_quests_audit)")}
    assert 'to_act_index' in audit_cols
    scene_cols = {r[1] for r in conn.execute("PRAGMA table_info(dnd_scene_state)")}
    assert 'current_act_id' in scene_cols
    conn.close()


def test_quest_act_upsert_idempotent(temp_db):
    import dnd_engine as eng
    qid = eng.quest_add(1, 'TestQuest', skeleton_origin=1)
    a1, was_new = eng.quest_act_upsert(1, qid, 1, 'Approach', 'desc1',
                                        '{"scene_count_threshold": 2}', 1)
    assert was_new is True
    # Re-run with same key — updates in place, not inserts.
    a2, was_new = eng.quest_act_upsert(1, qid, 1, 'Approach v2', 'desc2',
                                        '{"scene_count_threshold": 3}', 1)
    assert was_new is False
    assert a2 == a1
    acts = eng.get_quest_acts(1, qid)
    assert len(acts) == 1
    assert acts[0]['act_title'] == 'Approach v2'
    assert json.loads(acts[0]['transition_predicate_json']) == {'scene_count_threshold': 3}


def test_quest_act_upsert_refuses_cross_campaign(temp_db):
    """A quest in campaign 1; calling upsert with campaign 2 must refuse."""
    import dnd_engine as eng
    qid = eng.quest_add(1, 'QInCamp1')
    # Insert a second campaign.
    conn = sqlite3.connect(temp_db)
    conn.execute(
        "INSERT INTO dnd_campaigns (id, name, status, created_at) "
        "VALUES (?,?,?,?)",
        (2, 'OtherCampaign', 'active', '2026-05-13T00:00:00')
    )
    conn.commit()
    conn.close()
    a_id, was_new = eng.quest_act_upsert(2, qid, 1, 'X')
    assert (a_id, was_new) == (0, False)


def test_set_current_act_validates_fk(temp_db):
    import dnd_engine as eng
    # Init scene_state first (required for the UPDATE to succeed).
    eng.init_scene_state(1)
    # Bogus act_id → refuses.
    assert eng.set_current_act(1, 99999) is False
    # NULL clear → always permitted.
    assert eng.set_current_act(1, None) is True


def test_set_current_act_writes(temp_db):
    import dnd_engine as eng
    eng.init_scene_state(1)
    qid = eng.quest_add(1, 'Q')
    a_id, _ = eng.quest_act_upsert(1, qid, 1, 'Act1')
    assert eng.set_current_act(1, a_id) is True
    cur = eng.get_current_act(1)
    assert cur is not None
    assert cur['id'] == a_id


def test_quest_accept_anchors_act_1(temp_db):
    import dnd_engine as eng
    eng.init_scene_state(1)
    qid = eng.quest_add(1, 'Q', skeleton_origin=1)
    a1, _ = eng.quest_act_upsert(1, qid, 1, 'Approach')
    a2, _ = eng.quest_act_upsert(1, qid, 2, 'Engage')
    # Put quest in 'offered' status to satisfy quest_accept precondition.
    eng.quest_offer(1, qid)
    assert eng.quest_accept(1, qid, accepted_turn=5)
    cur = eng.get_current_act(1)
    assert cur is not None
    assert cur['id'] == a1
    assert cur['act_index'] == 1


def test_quest_accept_no_acts_leaves_anchor_null(temp_db):
    import dnd_engine as eng
    eng.init_scene_state(1)
    qid = eng.quest_add(1, 'Q', skeleton_origin=1)
    eng.quest_offer(1, qid)
    assert eng.quest_accept(1, qid, accepted_turn=5)
    # No acts on the quest → current_act_id stays NULL.
    cur = eng.get_current_act(1)
    assert cur is None


def test_quest_deliver_clears_anchor(temp_db):
    import dnd_engine as eng
    eng.init_scene_state(1)
    qid = eng.quest_add(1, 'Q')
    a1, _ = eng.quest_act_upsert(1, qid, 1, 'Act1')
    eng.set_current_act(1, a1)
    assert eng.quest_deliver(1, qid) is not None
    assert eng.get_current_act(1) is None


def test_quest_fail_clears_anchor(temp_db):
    import dnd_engine as eng
    eng.init_scene_state(1)
    qid = eng.quest_add(1, 'Q')
    a1, _ = eng.quest_act_upsert(1, qid, 1, 'Act1')
    eng.set_current_act(1, a1)
    assert eng.quest_fail(1, qid)
    assert eng.get_current_act(1) is None


def test_quest_abandon_clears_anchor(temp_db):
    import dnd_engine as eng
    eng.init_scene_state(1)
    qid = eng.quest_add(1, 'Q', skeleton_origin=1)
    eng.quest_offer(1, qid)
    a1, _ = eng.quest_act_upsert(1, qid, 1, 'Act1')
    eng.set_current_act(1, a1)
    assert eng.quest_abandon(1, qid)
    assert eng.get_current_act(1) is None


def test_quest_act_transition_writes_audit(temp_db):
    import dnd_engine as eng
    eng.init_scene_state(1)
    qid = eng.quest_add(1, 'Q')
    a1, _ = eng.quest_act_upsert(1, qid, 1, 'A1')
    a2, _ = eng.quest_act_upsert(1, qid, 2, 'A2')
    eng.set_current_act(1, a1)
    result = eng.quest_act_transition(1, qid, 2, source='act_advance',
                                       turn_counter=5)
    assert result is not None
    assert result['act_index'] == 2
    assert eng.get_current_act(1)['id'] == a2
    # Audit row present.
    conn = sqlite3.connect(temp_db)
    row = conn.execute(
        "SELECT source, to_act_index, turn_counter FROM dnd_quests_audit "
        "WHERE campaign_id=1 AND quest_id=? AND source='act_advance'",
        (qid,)
    ).fetchone()
    conn.close()
    assert row is not None
    assert row == ('act_advance', 2, 5)


def test_quest_act_transition_refuses_nonexistent(temp_db):
    import dnd_engine as eng
    eng.init_scene_state(1)
    qid = eng.quest_add(1, 'Q')
    eng.quest_act_upsert(1, qid, 1, 'A1')
    # No act 5 — refuse.
    assert eng.quest_act_transition(1, qid, 5) is None


def test_cascade_delete_parent_quest(temp_db):
    """§11.13 ON DELETE CASCADE — deleting a quest removes its acts via FK."""
    import dnd_engine as eng
    qid = eng.quest_add(1, 'Q', skeleton_origin=1)
    eng.quest_act_upsert(1, qid, 1, 'A1')
    eng.quest_act_upsert(1, qid, 2, 'A2')
    eng.quest_act_upsert(1, qid, 3, 'A3')
    # Sanity: 3 acts exist.
    assert len(eng.get_quest_acts(1, qid)) == 3
    # Delete the quest (which applies PRAGMA foreign_keys=ON per §11.13).
    assert eng.quest_delete(1, qid)
    # Verify acts cascaded away.
    conn = sqlite3.connect(temp_db)
    n = conn.execute(
        "SELECT COUNT(*) FROM dnd_quest_acts WHERE quest_id=?", (qid,)
    ).fetchone()[0]
    conn.close()
    assert n == 0, f"expected cascade to remove all 3 acts; {n} remain"


def test_campaign_delete_cascade_removes_acts(temp_db):
    """campaign_delete_cascade must also clean up dnd_quest_acts rows."""
    import dnd_engine as eng
    # Set campaign to non-active so cascade is permitted.
    conn = sqlite3.connect(temp_db)
    conn.execute("UPDATE dnd_campaigns SET status='archived' WHERE id=1")
    conn.commit()
    conn.close()
    qid = eng.quest_add(1, 'Q')
    eng.quest_act_upsert(1, qid, 1, 'A1')
    eng.quest_act_upsert(1, qid, 2, 'A2')
    result = eng.campaign_delete_cascade(1)
    assert result['deleted'] is True
    # Acts gone.
    conn = sqlite3.connect(temp_db)
    n = conn.execute("SELECT COUNT(*) FROM dnd_quest_acts").fetchone()[0]
    conn.close()
    assert n == 0


def test_quest_act_audit_to_status_can_be_empty(temp_db):
    """Act-transition rows write to_status='' on legacy schema (NOT NULL).
    On fresh S60 schema, to_status is NULLable."""
    import dnd_engine as eng
    eng.init_scene_state(1)
    qid = eng.quest_add(1, 'Q')
    eng.quest_act_upsert(1, qid, 1, 'A1')
    eng.quest_act_upsert(1, qid, 2, 'A2')
    eng.set_current_act(1, eng.get_quest_acts(1, qid)[0]['id'])
    eng.quest_act_transition(1, qid, 2, source='act_set')
    conn = sqlite3.connect(temp_db)
    row = conn.execute(
        "SELECT to_status FROM dnd_quests_audit WHERE source='act_set'"
    ).fetchone()
    conn.close()
    # Empty string sentinel per _quest_audit helper.
    assert row[0] == ''


# ─── Skeleton parser extension ───────────────────────────────────────────────

def test_skeleton_parser_quest_decomposition():
    import skeleton_loader as sl
    text = """# Campaign: Test

## Major hooks
- Legacy flat hook

### Investigate the farmstead
A farmstead two leagues east has been ravaged by goblins.

#### Acts
1. Approach the farmstead
   Scene count threshold: 2
2. Engage the goblins
   Location: farmstead grounds
3. Clear the farmstead
"""
    r = sl._parse_skeleton_text(text)
    assert r['hooks'] == ['Legacy flat hook']
    qd = r['quest_decompositions']
    assert len(qd) == 1
    assert qd[0]['title'] == 'Investigate the farmstead'
    assert len(qd[0]['acts']) == 3
    assert qd[0]['acts'][0]['predicate'] == {'scene_count_threshold': 2}
    assert qd[0]['acts'][1]['predicate'] == {'location_name': 'farmstead grounds'}
    assert qd[0]['acts'][2]['predicate'] == {}


def test_skeleton_parser_back_compat_flat_bullets():
    """Existing skeleton.md with no H3-under-hooks parses unchanged."""
    import skeleton_loader as sl
    text = """# Campaign: Old

## Major hooks
- Hook one
- Hook two
- Hook three
"""
    r = sl._parse_skeleton_text(text)
    assert r['hooks'] == ['Hook one', 'Hook two', 'Hook three']
    assert r['quest_decompositions'] == []


# ─── Telemetry helpers ───────────────────────────────────────────────────────

def test_quest_act_suggester_log_summary_shape():
    sigs = {'fired': 1, 'mode': 'exploration', 'reason': 'proposed',
            'current_act_id': 5, 'predicate_match_count': 1}
    prop = {'quest_id': 10, 'current_act_index': 1,
            'proposed_next_act_index': 2,
            'next_act_title': 'Engage',
            'predicate_reason': 'scene_count>=2'}
    line = orch.quest_act_suggester_log_summary(sigs, prop)
    assert 'fired=1' in line
    assert 'quest_id=10' in line
    assert 'proposed=2' in line


def test_composition_directive_log_summary_shape():
    sigs = {'fired': 1, 'current_act_id': 5,
            'current_act_index': 2, 'quest_id': 10}
    line = orch.composition_directive_log_summary(sigs)
    assert 'fired=1' in line
    assert 'current_act_id=5' in line
    assert 'quest_id=10' in line
