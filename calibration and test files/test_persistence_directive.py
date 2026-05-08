"""Deterministic tests for compute_persistence_directive (Session 21).

Combat Persistence Directive v1 — three composed sub-pressures (enemy
persistence, condition awareness, initiative-order confirm) driven by mode +
active_turn + combatants snapshot + typing identity.

Per §11.B retroactive lock: OFF-turn rendering dropped — Phase 2A.3 hard gate
catches off-turn messages upstream of dm_respond. v1 ships ON-turn confirm +
naming-only blocks only.

Run:
    cd /home/jordaneal/scripts && python3 test_persistence_directive.py
"""

import sys
sys.path.insert(0, '/home/jordaneal/scripts')

import dnd_orchestration as orch
from dnd_orchestration import (
    compute_persistence_directive,
    persistence_log_summary,
    _format_combatant_row,
    _format_snapshot_age,
    _PERSISTENCE_ABSTRACT_FALLBACK_BODY,
)


# ─── Master gate ────────────────────────────────────────────────────

def test_master_gate_exploration_silent():
    body, sig = compute_persistence_directive(mode='exploration', active_turn=None)
    assert body == ''
    assert sig['fired'] == 0 and sig['combat_active'] == 0


def test_master_gate_social_silent():
    body, sig = compute_persistence_directive(mode='social', active_turn=None)
    assert body == '' and sig['fired'] == 0


def test_master_gate_travel_silent():
    body, sig = compute_persistence_directive(mode='travel', active_turn=None)
    assert body == '' and sig['fired'] == 0


def test_master_gate_downtime_silent():
    body, sig = compute_persistence_directive(mode='downtime', active_turn=None)
    assert body == '' and sig['fired'] == 0


def test_master_gate_empty_string_silent():
    body, sig = compute_persistence_directive(mode='', active_turn=None)
    assert body == '' and sig['fired'] == 0


def test_master_gate_none_silent():
    body, sig = compute_persistence_directive(mode=None, active_turn=None)
    assert body == '' and sig['fired'] == 0


# ─── Abstract fallback (combat + no snapshot) ───────────────────────

def test_combat_without_snapshot_renders_abstract_fallback():
    body, sig = compute_persistence_directive(
        mode='combat', active_turn=None, combatants_snapshot=None,
    )
    assert sig['combat_active'] == 1
    assert sig['fired'] == 1
    assert sig['combatants'] == 0
    assert sig['hp_known'] == 0 and sig['conditions_known'] == 0
    assert "No `!init list` snapshot" in body
    assert "(Tip: type `!init list`" in body


def test_combat_with_empty_snapshot_renders_abstract_fallback():
    body, sig = compute_persistence_directive(
        mode='combat', active_turn=None,
        combatants_snapshot={'combatants': [], 'snapshot_age_s': None},
    )
    assert sig['fired'] == 1
    assert "No `!init list` snapshot" in body


def test_abstract_fallback_lists_eight_conditions():
    body, _ = compute_persistence_directive(
        mode='combat', active_turn=None, combatants_snapshot=None,
    )
    for cond in ['frightened', 'grappled', 'paralyzed', 'prone',
                 'restrained', 'stunned', 'unconscious', 'poisoned']:
        assert cond in body, f"abstract fallback should mention {cond}"


# ─── Concrete combatants block ──────────────────────────────────────

def _snap(combatants, age=10.0):
    return {'combatants': combatants, 'snapshot_age_s': age}


def test_concrete_block_renders_each_combatant():
    snap = _snap([
        {'init': 29, 'name': 'Garrick', 'hp_current': None, 'hp_max': None,
         'conditions': '', 'alive': 1},
        {'init': 25, 'name': 'throx', 'hp_current': 22, 'hp_max': 22,
         'conditions': 'Frightened', 'alive': 1},
    ])
    body, sig = compute_persistence_directive(
        mode='combat', active_turn=None, combatants_snapshot=snap,
    )
    assert sig['combatants'] == 2
    assert sig['hp_known'] == 1
    assert sig['conditions_known'] == 1
    assert 'Garrick' in body and 'throx' in body
    assert 'HP 22/22' in body
    assert 'Frightened' in body
    assert 'HP unknown' in body  # Garrick


def test_concrete_block_includes_snapshot_age():
    snap = _snap([
        {'init': 25, 'name': 'X', 'hp_current': None, 'hp_max': None,
         'conditions': '', 'alive': 1},
    ], age=42.7)
    body, _ = compute_persistence_directive(
        mode='combat', active_turn=None, combatants_snapshot=snap,
    )
    assert '42s ago' in body


def test_defeated_combatant_renders_DEFEATED():
    snap = _snap([
        {'init': 10, 'name': 'Down', 'hp_current': 0, 'hp_max': None,
         'conditions': '', 'alive': 0},
    ])
    body, _ = compute_persistence_directive(
        mode='combat', active_turn=None, combatants_snapshot=snap,
    )
    assert 'DEFEATED' in body


def test_active_marker_derived_from_active_turn():
    snap = _snap([
        {'init': 29, 'name': 'Garrick', 'hp_current': None, 'hp_max': None,
         'conditions': '', 'alive': 1},
        {'init': 25, 'name': 'throx', 'hp_current': None, 'hp_max': None,
         'conditions': '', 'alive': 1},
    ])
    active = {'controller_id': '12345', 'character_name': 'throx', 'round': 1}
    body, _ = compute_persistence_directive(
        mode='combat', active_turn=active, combatants_snapshot=snap,
        typing_user_id='12345', typing_character_name='throx',
    )
    # Find the throx line; must contain active marker. Garrick must NOT.
    throx_line = next(
        l for l in body.split('\n') if 'throx' in l and 'INITIATIVE' not in l
    )
    garrick_line = next(l for l in body.split('\n') if 'Garrick' in l)
    assert '← active turn' in throx_line
    assert '← active turn' not in garrick_line


def test_active_marker_case_insensitive():
    """active_turn.character_name from Avrae may differ in case; matcher
    folds to lowercase before comparing."""
    snap = _snap([
        {'init': 25, 'name': 'Throx', 'hp_current': None, 'hp_max': None,
         'conditions': '', 'alive': 1},
    ])
    active = {'controller_id': '1', 'character_name': 'throx', 'round': 1}
    body, _ = compute_persistence_directive(
        mode='combat', active_turn=active, combatants_snapshot=snap,
    )
    line = next(l for l in body.split('\n') if 'Throx' in l)
    assert '← active turn' in line


def test_no_active_turn_means_no_active_marker_anywhere():
    snap = _snap([
        {'init': 29, 'name': 'Garrick', 'hp_current': None, 'hp_max': None,
         'conditions': '', 'alive': 1},
        {'init': 25, 'name': 'throx', 'hp_current': None, 'hp_max': None,
         'conditions': '', 'alive': 1},
    ])
    body, _ = compute_persistence_directive(
        mode='combat', active_turn=None, combatants_snapshot=snap,
    )
    assert '← active turn' not in body


# ─── Initiative-order block (ON-turn confirm + naming-only) ─────────

def test_active_turn_with_matching_typing_user_renders_on_turn():
    active = {'controller_id': '12345', 'character_name': 'Donovan', 'round': 3}
    body, sig = compute_persistence_directive(
        mode='combat', active_turn=active, combatants_snapshot=None,
        typing_user_id='12345', typing_character_name='Donovan',
    )
    assert 'ON-TURN' in body
    assert 'round 3' in body
    assert "Donovan's turn" in body
    assert 'Discord 12345' in body
    assert sig['active_turn_controller'] == '12345'


def test_active_turn_with_no_typing_identity_renders_naming_only():
    active = {'controller_id': '12345', 'character_name': 'Donovan', 'round': 2}
    body, sig = compute_persistence_directive(
        mode='combat', active_turn=active, combatants_snapshot=None,
    )
    # Naming-only block — no ON-TURN/OFF-TURN labels
    assert 'ON-TURN' not in body
    assert 'OFF-TURN' not in body
    assert "Donovan's turn" in body
    assert sig['active_turn_controller'] == '12345'


def test_active_turn_with_mismatched_typing_user_falls_to_naming_only():
    """In production 2A.3 catches this case upstream. Defensively: if a
    mismatched ID does reach the directive (test paths, edge), render
    naming-only — never an OFF-turn block (those are dropped in v1)."""
    active = {'controller_id': '12345', 'character_name': 'Donovan', 'round': 2}
    body, _ = compute_persistence_directive(
        mode='combat', active_turn=active, combatants_snapshot=None,
        typing_user_id='99999', typing_character_name='Other',
    )
    assert 'ON-TURN' not in body
    assert 'OFF-TURN' not in body  # explicitly dropped per §11.B lock
    assert "Donovan's turn" in body


def test_active_turn_none_omits_initiative_block():
    body, _ = compute_persistence_directive(
        mode='combat', active_turn=None, combatants_snapshot=None,
    )
    assert 'INITIATIVE:' not in body


# ─── Body content invariants ────────────────────────────────────────

def test_body_forbids_narrating_combat_as_wrapped():
    snap = _snap([
        {'init': 25, 'name': 'X', 'hp_current': None, 'hp_max': None,
         'conditions': '', 'alive': 1},
    ])
    body, _ = compute_persistence_directive(
        mode='combat', active_turn=None, combatants_snapshot=snap,
    )
    # Must mention !init end as the canonical close, must forbid wrapping
    assert '!init end' in body
    assert 'wrapped' in body or 'narrate' in body


def test_body_mentions_avrae_owns_state():
    body, _ = compute_persistence_directive(
        mode='combat', active_turn=None, combatants_snapshot=None,
    )
    assert 'Avrae' in body


# ─── Telemetry / log summary ────────────────────────────────────────

def test_log_summary_silent_state():
    sig = {'fired': 0, 'combat_active': 0, 'hp_known': 0,
           'conditions_known': 0, 'combatants': 0,
           'snapshot_age_s': None, 'active_turn_controller': 'none'}
    s = persistence_log_summary(sig)
    assert 'fired=0' in s and 'combat_active=0' in s
    assert 'snapshot_age_s=none' in s
    assert 'active_turn_controller=none' in s


def test_log_summary_full_state():
    sig = {'fired': 1, 'combat_active': 1, 'hp_known': 1,
           'conditions_known': 1, 'combatants': 3,
           'snapshot_age_s': 42.0, 'active_turn_controller': '12345'}
    s = persistence_log_summary(sig)
    assert 'fired=1' in s
    assert 'hp_known=1 conditions_known=1' in s
    assert 'combatants=3' in s
    assert 'snapshot_age_s=42' in s
    assert 'active_turn_controller=12345' in s


def test_log_summary_handles_empty_signals():
    s = persistence_log_summary({})
    assert 'fired=0' in s


# ─── Helper functions ───────────────────────────────────────────────

def test_format_snapshot_age_under_60():
    assert _format_snapshot_age(0) == '0s'
    assert _format_snapshot_age(42) == '42s'
    assert _format_snapshot_age(59) == '59s'


def test_format_snapshot_age_over_60_uses_minutes():
    assert _format_snapshot_age(60) == '>1min'
    assert _format_snapshot_age(125) == '>2min'


def test_format_snapshot_age_handles_none():
    assert _format_snapshot_age(None) == 'unknown age'


def test_format_combatant_row_alive_no_hp():
    row = _format_combatant_row({
        'init': 25, 'name': 'X', 'alive': 1,
        'hp_current': None, 'hp_max': None, 'conditions': '',
    })
    assert 'HP unknown' in row
    assert 'X' in row


def test_format_combatant_row_hp_present():
    row = _format_combatant_row({
        'init': 25, 'name': 'X', 'alive': 1,
        'hp_current': 12, 'hp_max': 22, 'conditions': '',
    })
    assert 'HP 12/22' in row


def test_format_combatant_row_with_conditions():
    row = _format_combatant_row({
        'init': 25, 'name': 'X', 'alive': 1,
        'hp_current': 22, 'hp_max': 22, 'conditions': 'Frightened, Prone',
    })
    assert 'conditions: Frightened, Prone' in row


def test_format_combatant_row_defeated():
    row = _format_combatant_row({
        'init': 25, 'name': 'X', 'alive': 0,
        'hp_current': 0, 'hp_max': 22, 'conditions': '',
    })
    assert 'DEFEATED' in row
    assert 'HP' not in row  # HP clause replaced by DEFEATED


def test_format_combatant_row_active_marker():
    row = _format_combatant_row({
        'init': 25, 'name': 'X', 'alive': 1, 'active': True,
        'hp_current': 22, 'hp_max': 22, 'conditions': '',
    })
    assert '← active turn' in row


def test_format_combatant_row_no_active_marker_when_false():
    row = _format_combatant_row({
        'init': 25, 'name': 'X', 'alive': 1, 'active': False,
        'hp_current': 22, 'hp_max': 22, 'conditions': '',
    })
    assert '← active turn' not in row


# ─── Idempotency / purity ───────────────────────────────────────────

def test_directive_is_pure_function():
    snap = _snap([
        {'init': 25, 'name': 'X', 'hp_current': 22, 'hp_max': 22,
         'conditions': '', 'alive': 1},
    ])
    a, _ = compute_persistence_directive(
        mode='combat', active_turn=None, combatants_snapshot=snap,
    )
    b, _ = compute_persistence_directive(
        mode='combat', active_turn=None, combatants_snapshot=snap,
    )
    assert a == b


# ─── Run ────────────────────────────────────────────────────────────

if __name__ == '__main__':
    failures = []
    funcs = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for fn in funcs:
        try:
            fn()
            print(f"  ok   {fn.__name__}")
        except AssertionError as e:
            failures.append((fn.__name__, str(e)))
            print(f"  FAIL {fn.__name__}: {e}")
        except Exception as e:
            failures.append((fn.__name__, repr(e)))
            print(f"  ERR  {fn.__name__}: {e!r}")
    if failures:
        print(f"\n{len(failures)} failure(s)")
        sys.exit(1)
    print(f"\n{len(funcs)} tests passed.")
