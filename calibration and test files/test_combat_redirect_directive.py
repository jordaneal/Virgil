"""Deterministic tests for compute_combat_redirect_directive
(Track 6 #2, Session 23).

Pure function — takes scene_state / active_turn / combatants list /
bound_character_name, returns (body, signals). No DB, no side effects.

Run:
    cd /home/jordaneal/scripts && python3 test_combat_redirect_directive.py
"""

import sys

sys.path.insert(0, '/home/jordaneal/scripts')

import dnd_orchestration as orch


# ─── Fixture builders ───────────────────────────────────────────────

def _scene(mode='combat'):
    return {
        'mode':           mode,
        'location':       'Stumbling Stag',
        'focus':          '',
        'tension':        'low',
        'active_npcs':    [],
        'active_threats': [],
    }


def _turn(name='Donovan Ruby', round_=1, controller_id='123'):
    return {
        'controller_id':   controller_id,
        'character_name':  name,
        'round':           round_,
        'updated_at':      '2026-05-05T00:00:00',
    }


def _comb(name, init=10, alive=1, hp_current=None, hp_max=None,
          conditions='', side='unknown'):
    return {
        'name':       name,
        'init':       init,
        'hp_current': hp_current,
        'hp_max':     hp_max,
        'conditions': conditions,
        'alive':      alive,
        'side':       side,
    }


# ─── Master gate: scene mode ────────────────────────────────────────

def test_exploration_mode_does_not_fire():
    body, signals = orch.compute_combat_redirect_directive(
        _scene('exploration'),
        _turn('Donovan Ruby'),
        [_comb('goblin', alive=1, hp_current=2, hp_max=2)],
        bound_character_name='Donovan Ruby',
    )
    assert body == ''
    assert signals['fired'] == 0
    assert signals['reason'] == 'gate_mode'


def test_social_mode_does_not_fire():
    body, signals = orch.compute_combat_redirect_directive(
        _scene('social'),
        _turn('Donovan Ruby'),
        [_comb('goblin', alive=1)],
        bound_character_name='Donovan Ruby',
    )
    assert body == ''
    assert signals['reason'] == 'gate_mode'


def test_scene_state_none_does_not_fire():
    body, signals = orch.compute_combat_redirect_directive(
        None,
        _turn('Donovan Ruby'),
        [_comb('goblin', alive=1)],
        bound_character_name='Donovan Ruby',
    )
    assert body == ''
    assert signals['reason'] == 'gate_mode'


def test_scene_state_missing_mode_does_not_fire():
    # Defensive — mode key absent treated as gate_mode.
    body, signals = orch.compute_combat_redirect_directive(
        {'location': 'Stumbling Stag'},
        _turn('Donovan Ruby'),
        [_comb('goblin', alive=1)],
        bound_character_name='Donovan Ruby',
    )
    assert body == ''
    assert signals['reason'] == 'gate_mode'


# ─── Master gate: alive enemies ─────────────────────────────────────

def test_combat_with_no_combatants_does_not_fire():
    body, signals = orch.compute_combat_redirect_directive(
        _scene('combat'),
        _turn('Donovan Ruby'),
        [],
        bound_character_name='Donovan Ruby',
    )
    assert body == ''
    assert signals['reason'] == 'gate_no_enemies'
    assert signals['alive_enemies'] == 0


def test_combat_with_only_dead_enemies_does_not_fire():
    body, signals = orch.compute_combat_redirect_directive(
        _scene('combat'),
        _turn('Donovan Ruby'),
        [_comb('goblin', alive=0, hp_current=0, hp_max=2)],
        bound_character_name='Donovan Ruby',
    )
    assert body == ''
    assert signals['reason'] == 'gate_no_enemies'
    assert signals['alive_enemies'] == 0


def test_combat_with_only_PC_combatants_does_not_fire():
    # Solo combatant is the PC — no enemies — gate out.
    body, signals = orch.compute_combat_redirect_directive(
        _scene('combat'),
        _turn('Donovan Ruby'),
        [_comb('Donovan Ruby', alive=1, hp_current=11, hp_max=11)],
        bound_character_name='Donovan Ruby',
    )
    assert body == ''
    assert signals['reason'] == 'gate_no_enemies'
    assert signals['alive_enemies'] == 0


def test_combatants_none_does_not_crash():
    # None input handled gracefully (per Track 6 #1 precedent).
    body, signals = orch.compute_combat_redirect_directive(
        _scene('combat'),
        _turn('Donovan Ruby'),
        None,
        bound_character_name='Donovan Ruby',
    )
    assert body == ''
    assert signals['reason'] == 'gate_no_enemies'


# ─── Master gate: PC turn ───────────────────────────────────────────

def test_npc_turn_does_not_fire():
    # Active turn is the goblin (NPC), bound PC is Donovan.
    body, signals = orch.compute_combat_redirect_directive(
        _scene('combat'),
        _turn('goblin'),
        [_comb('goblin', alive=1, hp_current=2, hp_max=2),
         _comb('Donovan Ruby', alive=1, hp_current=11, hp_max=11)],
        bound_character_name='Donovan Ruby',
    )
    assert body == ''
    assert signals['reason'] == 'gate_npc_turn'
    assert signals['alive_enemies'] == 1


def test_active_turn_none_with_pc_binding_does_not_fire():
    # bound_character_name is set; active_turn is None — name mismatch
    # by virtue of empty name, classify as NPC turn (defensive — won't
    # fire without a confirmed PC turn).
    body, signals = orch.compute_combat_redirect_directive(
        _scene('combat'),
        None,
        [_comb('goblin', alive=1, hp_current=2, hp_max=2)],
        bound_character_name='Donovan Ruby',
    )
    assert body == ''
    assert signals['reason'] == 'gate_npc_turn'


def test_pc_turn_fires():
    body, signals = orch.compute_combat_redirect_directive(
        _scene('combat'),
        _turn('Donovan Ruby'),
        [_comb('goblin', alive=1, hp_current=2, hp_max=2),
         _comb('Donovan Ruby', alive=1, hp_current=11, hp_max=11)],
        bound_character_name='Donovan Ruby',
    )
    assert body != ''
    assert signals['fired'] == 1
    assert signals['reason'] == 'fired'
    assert signals['alive_enemies'] == 1


def test_pc_turn_match_is_case_insensitive():
    # bound 'Donovan Ruby', active turn 'donovan ruby'
    body, signals = orch.compute_combat_redirect_directive(
        _scene('combat'),
        _turn('donovan ruby'),
        [_comb('goblin', alive=1)],
        bound_character_name='Donovan Ruby',
    )
    assert signals['fired'] == 1


def test_bound_character_name_none_default_fires():
    # bound_character_name=None means "any human-typed input is the PC"
    # (2A.3 already dropped off-turn input). Default-fire.
    body, signals = orch.compute_combat_redirect_directive(
        _scene('combat'),
        _turn('whoever'),
        [_comb('goblin', alive=1, hp_current=2, hp_max=2)],
        bound_character_name=None,
    )
    assert signals['fired'] == 1
    # When no PC binding, the "enemy" filter can't exclude the PC, so
    # all alive combatants count as enemies. Including 'whoever' if it
    # were in the snapshot — but here goblin is the only one, so it's 1.
    assert signals['alive_enemies'] == 1


# ─── Body content ───────────────────────────────────────────────────

def test_body_contains_authoritative_combat_active_framing():
    body, _ = orch.compute_combat_redirect_directive(
        _scene('combat'),
        _turn('Donovan Ruby'),
        [_comb('goblin', alive=1, hp_current=2, hp_max=2)],
        bound_character_name='Donovan Ruby',
    )
    assert 'Combat is ACTIVE' in body
    assert 'Do NOT honor exit narration as resolution' in body
    assert '!init end' in body


def test_body_contains_threat_list_header():
    body, _ = orch.compute_combat_redirect_directive(
        _scene('combat'),
        _turn('Donovan Ruby'),
        [_comb('goblin', alive=1, hp_current=2, hp_max=2)],
        bound_character_name='Donovan Ruby',
    )
    assert 'Active threats:' in body


def test_body_renders_alive_enemy_with_hp():
    body, _ = orch.compute_combat_redirect_directive(
        _scene('combat'),
        _turn('Donovan Ruby'),
        [_comb('goblin', alive=1, hp_current=2, hp_max=2)],
        bound_character_name='Donovan Ruby',
    )
    assert '- goblin (2/2 HP)' in body


def test_body_renders_alive_enemy_with_hp_unknown_when_missing():
    body, _ = orch.compute_combat_redirect_directive(
        _scene('combat'),
        _turn('Donovan Ruby'),
        [_comb('goblin', alive=1, hp_current=None, hp_max=None)],
        bound_character_name='Donovan Ruby',
    )
    assert '- goblin (HP unknown)' in body


def test_body_renders_conditions_when_present():
    body, _ = orch.compute_combat_redirect_directive(
        _scene('combat'),
        _turn('Donovan Ruby'),
        [_comb('goblin', alive=1, hp_current=2, hp_max=2,
               conditions='Frightened')],
        bound_character_name='Donovan Ruby',
    )
    assert '- goblin (2/2 HP, Frightened)' in body


def test_body_omits_dead_enemies_from_threat_list():
    body, _ = orch.compute_combat_redirect_directive(
        _scene('combat'),
        _turn('Donovan Ruby'),
        [_comb('goblin', alive=1, hp_current=2, hp_max=2),
         _comb('orc', alive=0, hp_current=0, hp_max=8)],
        bound_character_name='Donovan Ruby',
    )
    assert '- goblin (2/2 HP)' in body
    assert 'orc' not in body  # dead → omitted


def test_body_omits_pc_from_threat_list():
    body, _ = orch.compute_combat_redirect_directive(
        _scene('combat'),
        _turn('Donovan Ruby'),
        [_comb('goblin', alive=1, hp_current=2, hp_max=2),
         _comb('Donovan Ruby', alive=1, hp_current=11, hp_max=11)],
        bound_character_name='Donovan Ruby',
    )
    assert '- goblin (2/2 HP)' in body
    assert 'Donovan Ruby' not in body  # PC filtered from threats


def test_body_renders_multiple_alive_enemies():
    body, _ = orch.compute_combat_redirect_directive(
        _scene('combat'),
        _turn('Donovan Ruby'),
        [_comb('goblin', init=14, alive=1, hp_current=2, hp_max=2),
         _comb('orc', init=12, alive=1, hp_current=8, hp_max=8),
         _comb('bandit', init=10, alive=1, hp_current=5, hp_max=11)],
        bound_character_name='Donovan Ruby',
    )
    assert '- goblin (2/2 HP)' in body
    assert '- orc (8/8 HP)' in body
    assert '- bandit (5/11 HP)' in body


def test_body_contains_redirect_guidance():
    body, _ = orch.compute_combat_redirect_directive(
        _scene('combat'),
        _turn('Donovan Ruby'),
        [_comb('goblin', alive=1, hp_current=2, hp_max=2)],
        bound_character_name='Donovan Ruby',
    )
    # Direct authority phrasing (no refusal language)
    assert 'redirect their narration toward' in body
    assert 'world reacting' in body
    assert 'Do NOT refuse' in body
    assert 'cannot do that' in body  # appears as "Do NOT say 'you cannot do that.'"


def test_body_does_not_advise_player_choice():
    # Out of scope: tactical coaching. Body should not tell player which
    # action to take, only that combat is active and threats are present.
    body, _ = orch.compute_combat_redirect_directive(
        _scene('combat'),
        _turn('Donovan Ruby'),
        [_comb('goblin', alive=1, hp_current=2, hp_max=2)],
        bound_character_name='Donovan Ruby',
    )
    # Negative invariants — no tactical-coaching language
    assert 'optimal' not in body.lower()
    assert 'should attack' not in body.lower()
    assert 'finish him' not in body.lower()


# ─── Threat summary (signals) ───────────────────────────────────────

def test_threat_summary_signal_lists_alive_enemy_names():
    _, signals = orch.compute_combat_redirect_directive(
        _scene('combat'),
        _turn('Donovan Ruby'),
        [_comb('goblin', init=14, alive=1, hp_current=2, hp_max=2),
         _comb('orc', init=12, alive=1, hp_current=8, hp_max=8)],
        bound_character_name='Donovan Ruby',
    )
    # threat_summary is a comma-separated list of alive enemy names.
    assert signals['threat_summary'] == 'goblin, orc'
    assert signals['alive_enemies'] == 2


def test_threat_summary_empty_when_no_alive_enemies():
    _, signals = orch.compute_combat_redirect_directive(
        _scene('combat'),
        _turn('Donovan Ruby'),
        [],
        bound_character_name='Donovan Ruby',
    )
    assert signals['threat_summary'] == ''


# ─── Graceful degrade ───────────────────────────────────────────────

def test_combatant_missing_alive_key_treated_as_dead():
    # Defensive — combatant dict missing 'alive' key shouldn't crash.
    body, signals = orch.compute_combat_redirect_directive(
        _scene('combat'),
        _turn('Donovan Ruby'),
        [{'name': 'goblin', 'init': 14}],  # no alive key
        bound_character_name='Donovan Ruby',
    )
    assert body == ''
    assert signals['reason'] == 'gate_no_enemies'


def test_combatant_with_invalid_alive_value_skipped():
    # Defensive — non-int alive value handled.
    body, signals = orch.compute_combat_redirect_directive(
        _scene('combat'),
        _turn('Donovan Ruby'),
        [{'name': 'goblin', 'alive': 'yes'}],
        bound_character_name='Donovan Ruby',
    )
    assert body == ''
    assert signals['reason'] == 'gate_no_enemies'


def test_combatant_with_empty_name_skipped():
    body, signals = orch.compute_combat_redirect_directive(
        _scene('combat'),
        _turn('Donovan Ruby'),
        [{'name': '', 'alive': 1, 'hp_current': 2, 'hp_max': 2}],
        bound_character_name='Donovan Ruby',
    )
    assert body == ''
    assert signals['reason'] == 'gate_no_enemies'


def test_non_dict_combatant_in_list_skipped():
    # Defensive — list contains a non-dict element; should skip not crash.
    body, signals = orch.compute_combat_redirect_directive(
        _scene('combat'),
        _turn('Donovan Ruby'),
        [None, 'string', _comb('goblin', alive=1, hp_current=2, hp_max=2)],
        bound_character_name='Donovan Ruby',
    )
    assert signals['fired'] == 1
    assert '- goblin (2/2 HP)' in body


# ─── Determinism + isolation ────────────────────────────────────────

def test_pure_function_deterministic():
    args = (
        _scene('combat'),
        _turn('Donovan Ruby'),
        [_comb('goblin', alive=1, hp_current=2, hp_max=2)],
        'Donovan Ruby',
    )
    b1, s1 = orch.compute_combat_redirect_directive(*args)
    b2, s2 = orch.compute_combat_redirect_directive(*args)
    assert b1 == b2
    assert s1 == s2


def test_no_input_mutation():
    scene = _scene('combat')
    turn = _turn('Donovan Ruby')
    combatants = [_comb('goblin', alive=1, hp_current=2, hp_max=2)]
    scene_copy = dict(scene)
    turn_copy = dict(turn)
    combatants_copy = [dict(c) for c in combatants]
    orch.compute_combat_redirect_directive(
        scene, turn, combatants, 'Donovan Ruby'
    )
    assert scene == scene_copy
    assert turn == turn_copy
    assert combatants == combatants_copy


def test_cross_campaign_isolation_via_inputs():
    # Pure function — if caller passes campaign-A's data and then
    # campaign-B's data, the function returns each correctly. No shared
    # state means no cross-campaign leak by construction.
    body_a, sig_a = orch.compute_combat_redirect_directive(
        _scene('combat'), _turn('Donovan Ruby'),
        [_comb('goblin', alive=1, hp_current=2, hp_max=2)],
        'Donovan Ruby',
    )
    body_b, sig_b = orch.compute_combat_redirect_directive(
        _scene('combat'), _turn('Garrick'),
        [_comb('orc', alive=1, hp_current=8, hp_max=8)],
        'Garrick',
    )
    assert 'goblin' in body_a and 'orc' not in body_a
    assert 'orc' in body_b and 'goblin' not in body_b
    assert sig_a['threat_summary'] == 'goblin'
    assert sig_b['threat_summary'] == 'orc'


# ─── Telemetry helper ───────────────────────────────────────────────

def test_log_summary_when_fired():
    s = {'fired': 1, 'alive_enemies': 2, 'reason': 'fired'}
    out = orch.combat_redirect_log_summary(s)
    assert out == 'fired=1 alive_enemies=2 reason=fired'


def test_log_summary_when_gate_mode():
    s = {'fired': 0, 'alive_enemies': 0, 'reason': 'gate_mode'}
    out = orch.combat_redirect_log_summary(s)
    assert out == 'fired=0 alive_enemies=0 reason=gate_mode'


def test_log_summary_when_gate_no_enemies():
    s = {'fired': 0, 'alive_enemies': 0, 'reason': 'gate_no_enemies'}
    out = orch.combat_redirect_log_summary(s)
    assert out == 'fired=0 alive_enemies=0 reason=gate_no_enemies'


def test_log_summary_when_gate_npc_turn():
    s = {'fired': 0, 'alive_enemies': 1, 'reason': 'gate_npc_turn'}
    out = orch.combat_redirect_log_summary(s)
    assert out == 'fired=0 alive_enemies=1 reason=gate_npc_turn'


def test_log_summary_with_empty_signals():
    assert orch.combat_redirect_log_summary({}) == 'fired=0 alive_enemies=0 reason=gate_mode'


def test_log_summary_with_none():
    assert orch.combat_redirect_log_summary(None) == 'fired=0 alive_enemies=0 reason=gate_mode'


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
