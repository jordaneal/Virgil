"""Deterministic tests for render_state_footer (Track 6 #1, Session 23).

Pure function — takes scene_state / active_turn / combatants_payload
dicts plus the bound-PC list, returns (footer_text, signals). No DB.

Run:
    cd /home/jordaneal/scripts && python3 test_state_footer.py
"""

import sys

sys.path.insert(0, '/home/jordaneal/scripts')

import dnd_orchestration as orch


# ─── Fixture builders ───────────────────────────────────────────────

def _scene(mode='exploration'):
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


def _comb(name, init, alive=1, hp_current=None, hp_max=None):
    return {
        'name':       name,
        'init':       init,
        'hp_current': hp_current,
        'hp_max':     hp_max,
        'conditions': '',
        'alive':      alive,
        'side':       'unknown',
    }


def _payload(*combatants):
    return {'combatants': list(combatants), 'snapshot_age_s': 1.0}


# ─── Combat mode ────────────────────────────────────────────────────

def test_combat_player_turn_renders_pc_hint():
    scene = _scene('combat')
    turn = _turn('Donovan Ruby', round_=2)
    payload = _payload(_comb('Donovan Ruby', 14), _comb('goblin', 12))
    text, signals = orch.render_state_footer(
        scene, turn, payload, ['Donovan Ruby']
    )
    assert '⚔ Combat — Round 2' in text
    assert 'Turn: Donovan Ruby (14)' in text
    assert 'Up next: goblin (12)' in text
    assert 'Your turn' in text
    assert 'narrate your action' in text
    assert 'NPC turn' not in text
    assert signals['mode'] == 'combat'
    assert signals['active_turn_name'] == 'Donovan Ruby'
    assert signals['round'] == 2


def test_combat_npc_turn_renders_npc_hint():
    scene = _scene('combat')
    turn = _turn('goblin', round_=2)
    payload = _payload(_comb('goblin', 18), _comb('Donovan Ruby', 14))
    text, signals = orch.render_state_footer(
        scene, turn, payload, ['Donovan Ruby']
    )
    assert 'Turn: goblin (18)' in text
    assert 'Up next: Donovan Ruby (14)' in text
    assert 'NPC turn' in text
    assert 'wait for resolution' in text
    assert 'Your turn' not in text
    assert signals['active_turn_name'] == 'goblin'


def test_combat_pc_match_is_case_insensitive():
    # Bound name 'Donovan Ruby' but Avrae state uses 'donovan ruby' lower
    scene = _scene('combat')
    turn = _turn('donovan ruby', round_=1)
    payload = _payload(_comb('donovan ruby', 15))
    text, _ = orch.render_state_footer(
        scene, turn, payload, ['Donovan Ruby']
    )
    assert 'Your turn' in text
    assert 'NPC turn' not in text


def test_combat_no_active_turn_renders_fallback():
    # Combat mode but get_active_turn returned None — Avrae state stale.
    scene = _scene('combat')
    payload = _payload(_comb('goblin', 12))
    text, signals = orch.render_state_footer(scene, None, payload, [])
    assert '⚔ Combat — Round ?' in text
    assert 'not set' in text
    assert '!init list' in text
    assert signals['mode'] == 'combat'
    assert signals['active_turn_name'] is None
    assert signals['round'] is None


def test_combat_round_question_mark_when_missing():
    scene = _scene('combat')
    turn = _turn('goblin')
    turn['round'] = None  # explicitly unknown
    payload = _payload(_comb('goblin', 12))
    text, signals = orch.render_state_footer(scene, turn, payload, [])
    assert '⚔ Combat — Round ?' in text
    assert signals['round'] is None


def test_combat_round_renders_when_present():
    scene = _scene('combat')
    turn = _turn('goblin', round_=5)
    payload = _payload(_comb('goblin', 10))
    text, signals = orch.render_state_footer(scene, turn, payload, [])
    assert '⚔ Combat — Round 5' in text
    assert signals['round'] == 5


# ─── Exploration / social / unknown ─────────────────────────────────

def test_exploration_mode_renders_simple_header():
    text, signals = orch.render_state_footer(
        _scene('exploration'), None, None, []
    )
    assert text == '📖 Exploration\n'
    assert signals['mode'] == 'exploration'
    assert signals['active_turn_name'] is None
    assert signals['round'] is None


def test_social_mode_renders_simple_header():
    text, signals = orch.render_state_footer(
        _scene('social'), None, None, []
    )
    assert text == '💬 Social\n'
    assert signals['mode'] == 'social'


def test_unknown_mode_renders_warning_prefix():
    text, signals = orch.render_state_footer(
        _scene('downtime'), None, None, []
    )
    assert text.startswith('⚠ ')
    assert 'downtime' in text
    assert signals['mode'] == 'downtime'


def test_scene_state_none_renders_empty():
    text, signals = orch.render_state_footer(None, None, None, [])
    assert text == ''
    assert signals['mode'] == 'unknown'


# ─── Graceful degrade — combatants edge cases ───────────────────────

def test_active_turn_with_empty_combatants_omits_up_next():
    scene = _scene('combat')
    turn = _turn('goblin', round_=1)
    text, _ = orch.render_state_footer(scene, turn, _payload(), [])
    assert 'Turn: goblin' in text
    assert 'Up next' not in text


def test_active_turn_with_none_payload_does_not_throw():
    scene = _scene('combat')
    turn = _turn('goblin', round_=1)
    # combatants_payload=None — engine read failed mid-flight
    text, _ = orch.render_state_footer(scene, turn, None, [])
    assert 'Turn: goblin' in text
    assert 'Up next' not in text


def test_active_turn_unknown_to_snapshot_omits_up_next_and_init():
    # Avrae says 'goblin' but snapshot only has 'Donovan' — name mismatch.
    scene = _scene('combat')
    turn = _turn('goblin', round_=1)
    payload = _payload(_comb('Donovan Ruby', 14))
    text, _ = orch.render_state_footer(
        scene, turn, payload, ['Donovan Ruby']
    )
    assert 'Turn: goblin' in text
    # No init label since lookup failed
    assert 'Turn: goblin (' not in text
    # Up next requires the current name be findable in the snapshot
    assert 'Up next' not in text


def test_only_one_combatant_no_up_next():
    # Solo combatant — no "Up next" line (would just point at self).
    scene = _scene('combat')
    turn = _turn('Donovan Ruby', round_=1)
    payload = _payload(_comb('Donovan Ruby', 14))
    text, _ = orch.render_state_footer(
        scene, turn, payload, ['Donovan Ruby']
    )
    assert 'Turn: Donovan Ruby (14)' in text
    assert 'Up next' not in text


def test_up_next_wraps_to_top_of_init():
    # Last combatant in init order → Up next is the highest init.
    scene = _scene('combat')
    turn = _turn('goblin', round_=1)
    payload = _payload(
        _comb('Donovan Ruby', 14),
        _comb('orc', 12),
        _comb('goblin', 8),
    )
    text, _ = orch.render_state_footer(
        scene, turn, payload, ['Donovan Ruby']
    )
    assert 'Turn: goblin (8)' in text
    assert 'Up next: Donovan Ruby (14)' in text


def test_up_next_in_middle_of_init():
    scene = _scene('combat')
    turn = _turn('orc', round_=1)
    payload = _payload(
        _comb('Donovan Ruby', 14),
        _comb('orc', 12),
        _comb('goblin', 8),
    )
    text, _ = orch.render_state_footer(
        scene, turn, payload, ['Donovan Ruby']
    )
    assert 'Turn: orc (12)' in text
    assert 'Up next: goblin (8)' in text


# ─── Determinism ────────────────────────────────────────────────────

def test_pure_function_deterministic():
    scene = _scene('combat')
    turn = _turn('Donovan Ruby', round_=3)
    payload = _payload(_comb('Donovan Ruby', 15), _comb('goblin', 10))
    text1, sig1 = orch.render_state_footer(
        scene, turn, payload, ['Donovan Ruby']
    )
    text2, sig2 = orch.render_state_footer(
        scene, turn, payload, ['Donovan Ruby']
    )
    assert text1 == text2
    assert sig1 == sig2


def test_no_input_mutation():
    # Pure function must not mutate its inputs (defensive — caller may
    # reuse these dicts for other purposes).
    scene = _scene('combat')
    turn = _turn('Donovan Ruby', round_=1)
    payload = _payload(_comb('Donovan Ruby', 14))
    bound = ['Donovan Ruby']
    scene_copy = dict(scene)
    turn_copy = dict(turn)
    payload_copy = {'combatants': list(payload['combatants']),
                    'snapshot_age_s': payload['snapshot_age_s']}
    bound_copy = list(bound)
    orch.render_state_footer(scene, turn, payload, bound)
    assert scene == scene_copy
    assert turn == turn_copy
    assert payload['combatants'] == payload_copy['combatants']
    assert bound == bound_copy


# ─── PC turn detection — list / set / None inputs ───────────────────

def test_bound_pc_names_as_set_works():
    scene = _scene('combat')
    turn = _turn('Donovan Ruby', round_=1)
    payload = _payload(_comb('Donovan Ruby', 14))
    text, _ = orch.render_state_footer(
        scene, turn, payload, {'Donovan Ruby'}
    )
    assert 'Your turn' in text


def test_bound_pc_names_none_treats_as_npc():
    scene = _scene('combat')
    turn = _turn('Donovan Ruby', round_=1)
    payload = _payload(_comb('Donovan Ruby', 14))
    text, _ = orch.render_state_footer(scene, turn, payload, None)
    # No bound list → can't confirm PC → render NPC hint as default.
    assert 'NPC turn' in text


def test_bound_pc_names_empty_list_treats_as_npc():
    scene = _scene('combat')
    turn = _turn('Donovan Ruby', round_=1)
    payload = _payload(_comb('Donovan Ruby', 14))
    text, _ = orch.render_state_footer(scene, turn, payload, [])
    assert 'NPC turn' in text


# ─── Telemetry helper ───────────────────────────────────────────────

def test_state_footer_log_summary_combat():
    s = {'mode': 'combat', 'active_turn_name': 'goblin', 'round': 3}
    out = orch.state_footer_log_summary(s)
    assert out == 'mode=combat active_turn=goblin round=3 day=none phase=none'


def test_state_footer_log_summary_exploration():
    s = {'mode': 'exploration', 'active_turn_name': None, 'round': None}
    out = orch.state_footer_log_summary(s)
    assert out == 'mode=exploration active_turn=none round=none day=none phase=none'


def test_state_footer_log_summary_empty_signals():
    # Track 4 #3 (Session 27) extended the summary with `day=` and `phase=`.
    assert orch.state_footer_log_summary({}) == (
        'mode=unknown active_turn=none round=none day=none phase=none'
    )


def test_state_footer_log_summary_none():
    assert orch.state_footer_log_summary(None) == (
        'mode=unknown active_turn=none round=none day=none phase=none'
    )


# ─── Trailing newline contract ──────────────────────────────────────

def test_combat_footer_ends_with_newline():
    scene = _scene('combat')
    turn = _turn('goblin', round_=1)
    payload = _payload(_comb('goblin', 12))
    text, _ = orch.render_state_footer(scene, turn, payload, [])
    assert text.endswith('\n')


def test_exploration_footer_ends_with_newline():
    text, _ = orch.render_state_footer(
        _scene('exploration'), None, None, []
    )
    assert text.endswith('\n')


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
