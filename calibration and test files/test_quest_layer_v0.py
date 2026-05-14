"""Unit tests for Quest Layer v0 (S56).

Covers:
  - compute_quest_offer_suggester branching (mode gate, NPC-anchor gate,
    no-offerable gate, voicer-match gate, cooldown gate)
  - compute_active_quest_directive (empty, single, cap-at-3 sort,
    AUTHORITATIVE framing absent — added by engine block wrapper)
  - Schema migration idempotency (running db_init twice is safe; existing
    rows preserved)
  - quest_seed_skeleton idempotency
  - State machine transitions: quest_offer / quest_accept / quest_deliver
    / quest_fail / quest_abandon (engine-defends-invariants per §16)
  - quest_set_status alias normalization ('active' → 'in-progress')
  - Cosine-similarity paste-detection (SequenceMatcher.ratio)
  - Reward summary parser (gp / item / faction / freetext)
"""

import os
import sys
import tempfile
import sqlite3

sys.path.insert(0, os.path.dirname(__file__))

import pytest

import dnd_orchestration as orch


# ─── Orchestration: compute_quest_offer_suggester ────────────────────────────

SOCIAL = {'mode': 'social', 'current_location_id': 1}
EXPLORATION = {'mode': 'exploration', 'current_location_id': 1}
COMBAT = {'mode': 'combat', 'current_location_id': 1}

ELDRIN = {'id': 10, 'canonical_name': 'Eldrin Stormbow', 'skeleton_origin': 1,
          'location_id': 1}
BORIN = {'id': 11, 'canonical_name': 'Borin Ironhand', 'skeleton_origin': 1,
         'location_id': 1}
NON_SKELETON_NPC = {'id': 99, 'canonical_name': 'Random Merchant',
                    'skeleton_origin': 0, 'location_id': 1}


def _quest(qid, voicer_id, title="Test quest", reward="50gp"):
    return {
        'id': qid, 'title': title, 'summary': 'A summary',
        'status': 'offered', 'offer_npc_id': voicer_id,
        'reward_summary': reward, 'skeleton_origin': 1,
    }


def test_suggester_mode_gate_combat_rejects():
    proposal, signals = orch.compute_quest_offer_suggester(
        scene_state=COMBAT,
        canonical_npcs_at_location=[ELDRIN],
        active_quests=[],
        offerable_quests=[_quest(1, 10)],
        turns_since_last_offer_per_npc={},
    )
    assert proposal is None
    assert signals['fired'] == 0
    assert signals['reason'] == 'gate_mode'


def test_suggester_no_npcs_at_location_rejects():
    proposal, signals = orch.compute_quest_offer_suggester(
        scene_state=SOCIAL,
        canonical_npcs_at_location=[],
        active_quests=[],
        offerable_quests=[_quest(1, 10)],
        turns_since_last_offer_per_npc={},
    )
    assert proposal is None
    assert signals['reason'] == 'gate_no_npcs'


def test_suggester_only_non_skeleton_npcs_rejects():
    proposal, signals = orch.compute_quest_offer_suggester(
        scene_state=SOCIAL,
        canonical_npcs_at_location=[NON_SKELETON_NPC],
        active_quests=[],
        offerable_quests=[_quest(1, 10)],
        turns_since_last_offer_per_npc={},
    )
    assert proposal is None
    assert signals['reason'] == 'gate_no_npcs'


def test_suggester_no_offerable_rejects():
    proposal, signals = orch.compute_quest_offer_suggester(
        scene_state=EXPLORATION,
        canonical_npcs_at_location=[ELDRIN],
        active_quests=[],
        offerable_quests=[],
        turns_since_last_offer_per_npc={},
    )
    assert proposal is None
    assert signals['reason'] == 'gate_no_offerable'


def test_suggester_no_voicer_match_rejects():
    # Eldrin (id=10) at location, but the offerable quest specifies voicer=99
    # (non-skeleton NPC). Predicate fails.
    proposal, signals = orch.compute_quest_offer_suggester(
        scene_state=SOCIAL,
        canonical_npcs_at_location=[ELDRIN],
        active_quests=[],
        offerable_quests=[_quest(1, 99)],
        turns_since_last_offer_per_npc={},
    )
    assert proposal is None
    assert signals['reason'] == 'gate_no_voicer_match'


def test_suggester_voicer_match_fires():
    proposal, signals = orch.compute_quest_offer_suggester(
        scene_state=SOCIAL,
        canonical_npcs_at_location=[ELDRIN, BORIN],
        active_quests=[],
        offerable_quests=[_quest(5, 10, title='Investigate farmstead')],
        turns_since_last_offer_per_npc={},
    )
    assert proposal is not None
    assert proposal['voicer_npc_id'] == 10
    assert proposal['voicer_npc_name'] == 'Eldrin Stormbow'
    assert proposal['quest_id'] == 5
    assert proposal['quest_title'] == 'Investigate farmstead'
    assert signals['fired'] == 1


def test_suggester_voicer_null_fallback_fires():
    # Quest's offer_npc_id is None → priority-rule fallback per §1.D. First
    # skeleton_origin=1 NPC at location wins.
    proposal, signals = orch.compute_quest_offer_suggester(
        scene_state=EXPLORATION,
        canonical_npcs_at_location=[BORIN, ELDRIN],
        active_quests=[],
        offerable_quests=[_quest(7, None, title='Anything')],
        turns_since_last_offer_per_npc={},
    )
    assert proposal is not None
    # First skeleton NPC in input order = Borin.
    assert proposal['voicer_npc_id'] == 11


def test_suggester_cooldown_gate_suppresses():
    # Eldrin offered 2 turns ago; cooldown is 6.
    proposal, signals = orch.compute_quest_offer_suggester(
        scene_state=SOCIAL,
        canonical_npcs_at_location=[ELDRIN],
        active_quests=[],
        offerable_quests=[_quest(5, 10)],
        turns_since_last_offer_per_npc={10: 2},
    )
    assert proposal is None
    assert signals['reason'] == 'gate_cooldown'


def test_suggester_cooldown_clears_at_threshold():
    # Eldrin offered exactly _QUEST_OFFER_COOLDOWN turns ago — fires.
    proposal, signals = orch.compute_quest_offer_suggester(
        scene_state=SOCIAL,
        canonical_npcs_at_location=[ELDRIN],
        active_quests=[],
        offerable_quests=[_quest(5, 10)],
        turns_since_last_offer_per_npc={10: orch._QUEST_OFFER_COOLDOWN},
    )
    assert proposal is not None
    assert signals['fired'] == 1


def test_suggester_multi_npc_one_cooldown_fires_other():
    # Eldrin in cooldown; Borin has unoffered quest → suggester picks Borin.
    proposal, signals = orch.compute_quest_offer_suggester(
        scene_state=SOCIAL,
        canonical_npcs_at_location=[ELDRIN, BORIN],
        active_quests=[],
        offerable_quests=[_quest(5, 10), _quest(6, 11)],
        turns_since_last_offer_per_npc={10: 2, 11: 99},
    )
    assert proposal is not None
    # Quest 5 is iterated first; Eldrin filtered out by cooldown; quest 6
    # matches Borin.
    assert proposal['voicer_npc_id'] == 11
    assert proposal['quest_id'] == 6


# ─── Orchestration: compute_active_quest_directive ───────────────────────────

def test_directive_empty_returns_empty():
    body, sig = orch.compute_active_quest_directive(
        active_quests=[], scene_state=EXPLORATION
    )
    assert body == ''
    assert sig['fired'] == 0
    assert sig['active_count'] == 0


def test_directive_only_offered_returns_empty():
    # Offered quests do NOT render in the active-quest directive (per §5).
    body, sig = orch.compute_active_quest_directive(
        active_quests=[{'id': 1, 'title': 'X', 'status': 'offered'}],
        scene_state=EXPLORATION,
    )
    assert body == ''
    assert sig['fired'] == 0
    assert sig['active_count'] == 0


def test_directive_in_progress_renders():
    body, sig = orch.compute_active_quest_directive(
        active_quests=[
            {'id': 1, 'title': 'Escort caravan', 'status': 'in-progress',
             'priority': 'urgent', 'reward_summary': '100gp',
             'summary': 'To Redhaven'},
        ],
        scene_state=EXPLORATION,
    )
    assert 'Escort caravan' in body
    assert '100gp' in body
    assert 'urgent' in body
    assert sig['fired'] == 1
    assert sig['active_count'] == 1
    assert sig['rendered'] == 1


def test_directive_legacy_active_alias_renders():
    # Back-compat: 'active' rows (pre-migration) still render as in-progress.
    body, sig = orch.compute_active_quest_directive(
        active_quests=[{'id': 1, 'title': 'X', 'status': 'active'}],
        scene_state=EXPLORATION,
    )
    assert 'X' in body
    assert sig['fired'] == 1


def test_directive_caps_at_3():
    rows = [
        {'id': i, 'title': f'Q{i}', 'status': 'in-progress',
         'priority': 'normal', 'accepted_turn': i}
        for i in range(1, 8)
    ]
    body, sig = orch.compute_active_quest_directive(
        active_quests=rows, scene_state=EXPLORATION
    )
    assert sig['active_count'] == 7
    assert sig['rendered'] == 3
    # Overflow line.
    assert 'more outstanding' in body


def test_directive_priority_sort():
    # urgent should render before normal even if accepted later.
    rows = [
        {'id': 1, 'title': 'NormalOld', 'status': 'in-progress',
         'priority': 'normal', 'accepted_turn': 1},
        {'id': 2, 'title': 'UrgentNew', 'status': 'in-progress',
         'priority': 'urgent', 'accepted_turn': 10},
    ]
    body, _ = orch.compute_active_quest_directive(rows, EXPLORATION)
    # Urgent line should appear before normal in the body.
    assert body.index('UrgentNew') < body.index('NormalOld')


def test_directive_must_not_invent_clause_present():
    body, _ = orch.compute_active_quest_directive(
        active_quests=[{'id': 1, 'title': 'X', 'status': 'in-progress'}],
        scene_state=EXPLORATION,
    )
    # The forbidden-list framing per spec §5.5 cliff-edge.
    assert 'Do NOT invent new quests' in body


# ─── Schema migration + alias normalization ──────────────────────────────────

def test_alias_normalize_active_to_in_progress():
    import dnd_engine
    assert dnd_engine._normalize_quest_status('active') == 'in-progress'
    # S61 v0.x patch: 'delivered' is now the alias mapping to canonical 'completed'.
    assert dnd_engine._normalize_quest_status('delivered') == 'completed'
    assert dnd_engine._normalize_quest_status('offered') == 'offered'
    assert dnd_engine._normalize_quest_status('bogus') == 'bogus'  # passes through; validator rejects


def test_valid_quest_statuses_five_set():
    import dnd_engine
    assert dnd_engine.VALID_QUEST_STATUSES == {
        'offered', 'in-progress', 'completed', 'failed', 'abandoned'
    }


# ─── Engine: quest_seed_skeleton idempotency + state machine ─────────────────

@pytest.fixture
def temp_db(monkeypatch, tmp_path):
    """Set DB_PATH to a fresh per-test SQLite file and run db_init."""
    db_file = tmp_path / "test_virgil.db"
    monkeypatch.setattr('dnd_engine.DB_PATH', db_file)
    import dnd_engine
    dnd_engine.db_init()
    # Insert a fake campaign so FK-tolerant code paths work.
    conn = sqlite3.connect(str(db_file))
    conn.execute(
        "INSERT INTO dnd_campaigns (id, name, status, created_at) "
        "VALUES (?, ?, ?, ?)",
        (1, 'TestCampaign', 'active', '2026-05-13T00:00:00')
    )
    conn.commit()
    conn.close()
    return str(db_file)


def test_seed_skeleton_inserts_then_idempotent(temp_db):
    import dnd_engine as eng
    hooks = [
        {'title': 'Escort caravan', 'summary': '', 'reward': '', 'voicer_npc_id': None},
        {'title': 'Investigate farmstead', 'summary': '', 'reward': '', 'voicer_npc_id': None},
    ]
    r1 = eng.quest_seed_skeleton(1, hooks)
    assert r1['inserted'] == 2
    assert r1['skipped'] == 0
    # Run again — should be all skipped.
    r2 = eng.quest_seed_skeleton(1, hooks)
    assert r2['inserted'] == 0
    assert r2['skipped'] == 2


def test_seed_skeleton_orphan_after_rename(temp_db):
    import dnd_engine as eng
    eng.quest_seed_skeleton(1, [{'title': 'OldName', 'voicer_npc_id': None}])
    # Operator renames in skeleton.md → new title; old row stays.
    eng.quest_seed_skeleton(1, [{'title': 'NewName', 'voicer_npc_id': None}])
    rows = eng.get_all_quests(1)
    titles = sorted(r['title'] for r in rows)
    assert titles == ['NewName', 'OldName']


def test_quest_offer_writes_audit(temp_db):
    import dnd_engine as eng
    qid = eng.quest_add(1, 'Test', skeleton_origin=1)
    assert eng.quest_offer(1, qid, offer_npc_id=42, offered_turn=5)
    row = eng.get_quest_by_id(1, qid)
    assert row['status'] == 'offered'
    assert row['offer_npc_id'] == 42
    assert row['offered_turn'] == 5
    # Audit row exists.
    conn = sqlite3.connect(temp_db)
    audit = conn.execute(
        "SELECT from_status, to_status, source FROM dnd_quests_audit "
        "WHERE campaign_id=1 AND quest_id=? ORDER BY id",
        (qid,)
    ).fetchall()
    conn.close()
    assert ('', 'in-progress', 'add') in audit
    assert ('in-progress', 'offered', 'offer') in audit


def test_quest_accept_refuses_from_non_offered(temp_db):
    import dnd_engine as eng
    qid = eng.quest_add(1, 'Test')  # creates at status='in-progress'
    # Cannot accept directly from in-progress.
    assert not eng.quest_accept(1, qid, accepted_turn=1)


def test_quest_accept_from_offered_works(temp_db):
    import dnd_engine as eng
    qid = eng.quest_add(1, 'Test', skeleton_origin=1)
    eng.quest_offer(1, qid, offer_npc_id=10, offered_turn=2)
    assert eng.quest_accept(1, qid, accepted_turn=3)
    row = eng.get_quest_by_id(1, qid)
    assert row['status'] == 'in-progress'
    assert row['accepted_turn'] == 3


def test_quest_deliver_returns_payload(temp_db):
    import dnd_engine as eng
    qid = eng.quest_add(1, 'Goblins', reward_summary='50gp + favor')
    payload = eng.quest_deliver(1, qid, delivered_turn=4)
    assert payload is not None
    assert payload['quest_id'] == qid
    assert payload['reward_summary'] == '50gp + favor'
    assert payload['title'] == 'Goblins'
    row = eng.get_quest_by_id(1, qid)
    assert row['status'] == 'completed'  # S61 patch: delivered → completed
    assert row['delivered_turn'] == 4  # column name preserved for code-side back-compat


def test_quest_deliver_refuses_from_offered(temp_db):
    import dnd_engine as eng
    qid = eng.quest_add(1, 'X', skeleton_origin=1)
    eng.quest_offer(1, qid)
    # Cannot deliver without acceptance first.
    assert eng.quest_deliver(1, qid) is None


def test_quest_fail_refuses_terminal(temp_db):
    import dnd_engine as eng
    qid = eng.quest_add(1, 'X')
    eng.quest_deliver(1, qid)
    assert not eng.quest_fail(1, qid)


def test_quest_abandon_works_from_offered(temp_db):
    import dnd_engine as eng
    qid = eng.quest_add(1, 'X', skeleton_origin=1)
    eng.quest_offer(1, qid)
    assert eng.quest_abandon(1, qid, turn_counter=5)
    row = eng.get_quest_by_id(1, qid)
    assert row['status'] == 'abandoned'


def test_quest_set_status_alias_normalizes(temp_db):
    import dnd_engine as eng
    qid = eng.quest_add(1, 'X')  # status='in-progress'
    # S61 v0.x patch: alias mapping flipped — 'delivered' now normalizes to
    # 'completed' (canonical). Sending 'completed' should also work since
    # it IS canonical.
    assert eng.quest_set_status(1, qid, 'delivered')
    row = eng.get_quest_by_id(1, qid)
    assert row['status'] == 'completed'  # aliased delivered → completed


def test_get_active_quests_returns_in_progress(temp_db):
    import dnd_engine as eng
    eng.quest_add(1, 'IP1')
    qid2 = eng.quest_add(1, 'Done')
    eng.quest_deliver(1, qid2)
    eng.quest_add(1, 'IP2')
    active = eng.get_active_quests(1)
    titles = sorted(q['title'] for q in active)
    assert titles == ['IP1', 'IP2']


def test_get_offerable_skeleton_quests(temp_db):
    import dnd_engine as eng
    eng.quest_seed_skeleton(1, [
        {'title': 'A', 'voicer_npc_id': None},
        {'title': 'B', 'voicer_npc_id': None},
    ])
    # Non-skeleton operator-added quest, not eligible.
    eng.quest_add(1, 'Operator-added')
    offerable = eng.get_offerable_skeleton_quests(1)
    titles = sorted(q['title'] for q in offerable)
    assert titles == ['A', 'B']
    for q in offerable:
        assert q['status'] == 'offered'
        assert q['skeleton_origin'] == 1


def test_quest_status_legacy_migration_runs_idempotent(temp_db):
    """Running db_init twice must not break existing rows or duplicate
    migration writes. The UPDATE runs idempotently because second run
    finds no rows at 'active' / 'completed'."""
    import dnd_engine as eng
    # Simulate a pre-v0 row at legacy 'active'.
    conn = sqlite3.connect(temp_db)
    conn.execute(
        "INSERT INTO dnd_quests (campaign_id, title, status, "
        "created_at, updated_at) VALUES (1, 'Legacy', 'active', ?, ?)",
        ('2026-05-12T00:00:00', '2026-05-12T00:00:00')
    )
    conn.commit()
    conn.close()
    # Re-run db_init → migration UPDATE fires.
    eng.db_init()
    rows = eng.get_all_quests(1)
    legacy = [r for r in rows if r['title'] == 'Legacy']
    assert len(legacy) == 1
    assert legacy[0]['status'] == 'in-progress'
    # Run db_init AGAIN — no second migration, no duplicate rows.
    eng.db_init()
    rows_2 = eng.get_all_quests(1)
    assert len(rows_2) == len(rows)


# ─── Bot: reward parser ──────────────────────────────────────────────────────

def test_reward_parser_gp_only():
    from discord_dnd_bot import _parse_reward_summary_for_inventory as parse
    assert parse('50gp') == [{'name': 'gp', 'quantity': 50}]
    assert parse('100 gp') == [{'name': 'gp', 'quantity': 100}]


def test_reward_parser_gp_plus_item():
    from discord_dnd_bot import _parse_reward_summary_for_inventory as parse
    parsed = parse('50gp + shortbow')
    assert {'name': 'gp', 'quantity': 50} in parsed
    assert {'name': 'shortbow', 'quantity': 1} in parsed


def test_reward_parser_skips_faction():
    from discord_dnd_bot import _parse_reward_summary_for_inventory as parse
    parsed = parse('50gp + Stoneforge reputation')
    assert parsed == [{'name': 'gp', 'quantity': 50}]


def test_reward_parser_skips_freetext():
    from discord_dnd_bot import _parse_reward_summary_for_inventory as parse
    assert parse('the deepest gratitude') == []
    assert parse('lasting thanks') == []
    assert parse('') == []


def test_reward_parser_silver_normalization():
    from discord_dnd_bot import _parse_reward_summary_for_inventory as parse
    assert parse('25 silver') == [{'name': 'sp', 'quantity': 25}]
    assert parse('5 gold') == [{'name': 'gp', 'quantity': 5}]
