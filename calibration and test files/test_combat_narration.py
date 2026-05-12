"""Tests for Ship S43 — dumb combat narration triggers + prompt build.

Covers:
  - _hp_state categorical labels (healthy / bloodied / downed / unknown)
  - compute_combat_state_transitions diff logic (BLOODIED + DOWNED edges)
  - compute_combat_narration_directive prompt build (mode gate, exact-HP
    exclusion, MUST/MUST-NOT verbatim, trigger-specific framing)
  - combat_narration_log_summary log line shape

Pure-function tests; no DB, no Discord, no LLM calls.

Run:
    cd /home/jordaneal/scripts && python3 test_combat_narration.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import dnd_orchestration as orch


# ─── _hp_state categorical labels ──────────────────────────────────

def test_hp_state_full_health_is_healthy():
    assert orch._hp_state(13, 13) == 'healthy'


def test_hp_state_above_half_is_healthy():
    assert orch._hp_state(8, 13) == 'healthy'


def test_hp_state_at_exactly_half_is_bloodied():
    # ≤50% threshold (half-exact counts as bloodied per 5e convention)
    assert orch._hp_state(6, 12) == 'bloodied'
    assert orch._hp_state(5, 10) == 'bloodied'


def test_hp_state_just_below_half_is_bloodied():
    assert orch._hp_state(5, 13) == 'bloodied'  # 5/13 ≈ 38%


def test_hp_state_one_hp_is_bloodied():
    assert orch._hp_state(1, 100) == 'bloodied'


def test_hp_state_zero_hp_is_downed():
    assert orch._hp_state(0, 13) == 'downed'


def test_hp_state_negative_hp_is_downed():
    assert orch._hp_state(-5, 13) == 'downed'


def test_hp_state_null_hp_max_is_unknown():
    assert orch._hp_state(13, None) == 'unknown'


def test_hp_state_null_hp_current_is_unknown():
    assert orch._hp_state(None, 13) == 'unknown'


def test_hp_state_zero_hp_max_is_unknown():
    # hp_max=0 is a default sentinel (pre-hydration); not real combat
    assert orch._hp_state(5, 0) == 'unknown'


# ─── compute_combat_state_transitions diff logic ──────────────────

def test_transitions_empty_inputs_returns_empty():
    assert orch.compute_combat_state_transitions([], []) == []


def test_transitions_no_prior_no_new_returns_empty():
    assert orch.compute_combat_state_transitions(None, None) == []


def test_transitions_healthy_to_bloodied_fires_bloodied():
    prior = [{'name': 'Goblin', 'hp_current': 13, 'hp_max': 13, 'alive': 1}]
    new = [{'name': 'Goblin', 'hp_current': 5, 'hp_max': 13, 'alive': 1}]
    t = orch.compute_combat_state_transitions(prior, new)
    assert len(t) == 1
    assert t[0]['kind'] == 'BLOODIED_THRESHOLD_CROSSED'
    assert t[0]['name'] == 'Goblin'
    assert t[0]['prior_state'] == 'healthy'
    assert t[0]['new_state'] == 'bloodied'


def test_transitions_healthy_to_healthy_fires_nothing():
    prior = [{'name': 'Goblin', 'hp_current': 13, 'hp_max': 13, 'alive': 1}]
    new = [{'name': 'Goblin', 'hp_current': 10, 'hp_max': 13, 'alive': 1}]
    t = orch.compute_combat_state_transitions(prior, new)
    assert t == []


def test_transitions_bloodied_back_to_healthy_fires_nothing():
    # Healing back up should NOT fire — only downward crossings
    prior = [{'name': 'Goblin', 'hp_current': 4, 'hp_max': 13, 'alive': 1}]
    new = [{'name': 'Goblin', 'hp_current': 12, 'hp_max': 13, 'alive': 1}]
    t = orch.compute_combat_state_transitions(prior, new)
    assert t == []


def test_transitions_healthy_to_downed_fires_downed_only():
    prior = [{'name': 'Goblin', 'hp_current': 13, 'hp_max': 13, 'alive': 1}]
    new = [{'name': 'Goblin', 'hp_current': 0, 'hp_max': 13, 'alive': 0}]
    t = orch.compute_combat_state_transitions(prior, new)
    assert len(t) == 1
    assert t[0]['kind'] == 'COMBATANT_DOWNED'
    assert t[0]['name'] == 'Goblin'


def test_transitions_bloodied_to_downed_fires_downed():
    prior = [{'name': 'Goblin', 'hp_current': 4, 'hp_max': 13, 'alive': 1}]
    new = [{'name': 'Goblin', 'hp_current': 0, 'hp_max': 13, 'alive': 0}]
    t = orch.compute_combat_state_transitions(prior, new)
    assert len(t) == 1
    assert t[0]['kind'] == 'COMBATANT_DOWNED'
    assert t[0]['prior_state'] == 'bloodied'


def test_transitions_downed_to_downed_fires_nothing():
    # Edge fires once on descent; staying down doesn't re-fire
    prior = [{'name': 'Goblin', 'hp_current': -2, 'hp_max': 13, 'alive': 0}]
    new = [{'name': 'Goblin', 'hp_current': -5, 'hp_max': 13, 'alive': 0}]
    t = orch.compute_combat_state_transitions(prior, new)
    assert t == []


def test_transitions_multi_combatant_each_diff_independently():
    prior = [
        {'name': 'A', 'hp_current': 13, 'hp_max': 13, 'alive': 1},
        {'name': 'B', 'hp_current': 13, 'hp_max': 13, 'alive': 1},
        {'name': 'C', 'hp_current': 4,  'hp_max': 13, 'alive': 1},
    ]
    new = [
        {'name': 'A', 'hp_current': 5,  'hp_max': 13, 'alive': 1},  # bloodied
        {'name': 'B', 'hp_current': 0,  'hp_max': 13, 'alive': 0},  # downed
        {'name': 'C', 'hp_current': 4,  'hp_max': 13, 'alive': 1},  # no change
    ]
    t = orch.compute_combat_state_transitions(prior, new)
    assert len(t) == 2
    kinds = {(e['name'], e['kind']) for e in t}
    assert ('A', 'BLOODIED_THRESHOLD_CROSSED') in kinds
    assert ('B', 'COMBATANT_DOWNED') in kinds


def test_transitions_new_combatant_pre_downed_fires_downed():
    """Edge case: combatant added mid-combat already at 0 HP (rare but
    possible — corpse re-add). Fires DOWNED once."""
    prior = []
    new = [{'name': 'Corpse', 'hp_current': 0, 'hp_max': 13, 'alive': 0}]
    t = orch.compute_combat_state_transitions(prior, new)
    assert len(t) == 1
    assert t[0]['kind'] == 'COMBATANT_DOWNED'
    assert t[0]['prior_state'] == 'unknown'


def test_transitions_new_combatant_alive_fires_nothing():
    """New combatant entering at full HP shouldn't fire anything."""
    prior = []
    new = [{'name': 'Fresh', 'hp_current': 13, 'hp_max': 13, 'alive': 1}]
    t = orch.compute_combat_state_transitions(prior, new)
    assert t == []


def test_transitions_missing_name_skipped():
    prior = [{'name': '', 'hp_current': 13, 'hp_max': 13, 'alive': 1}]
    new = [{'name': '', 'hp_current': 0, 'hp_max': 13, 'alive': 0}]
    t = orch.compute_combat_state_transitions(prior, new)
    assert t == []


# ─── compute_combat_narration_directive prompt build ──────────────

def _scene_combat():
    return {'mode': 'combat'}


def _scene_exploration():
    return {'mode': 'exploration'}


def _combat_state(combatants=None):
    return {'combatants': combatants or []}


def test_directive_mode_gate_exploration_returns_empty():
    trigger = {'kind': 'ROUND_START', 'round': 1}
    action, ctx = orch.compute_combat_narration_directive(
        trigger, _combat_state(), _scene_exploration(),
    )
    assert action == '' and ctx == ''


def test_directive_unknown_trigger_returns_empty():
    trigger = {'kind': 'UNKNOWN_TRIGGER'}
    action, ctx = orch.compute_combat_narration_directive(
        trigger, _combat_state(), _scene_combat(),
    )
    assert action == '' and ctx == ''


def test_directive_round_start_includes_sentinel_action():
    trigger = {'kind': 'ROUND_START', 'round': 3}
    action, ctx = orch.compute_combat_narration_directive(
        trigger, _combat_state(), _scene_combat(),
    )
    assert action == '[Combat narration: round 3 starts.]'
    assert 'TRIGGER: round_start' in ctx
    assert 'round 3' in ctx


def test_directive_bloodied_includes_combatant_name_in_action():
    trigger = {'kind': 'BLOODIED_THRESHOLD_CROSSED', 'name': 'Goblin'}
    action, ctx = orch.compute_combat_narration_directive(
        trigger, _combat_state(), _scene_combat(),
    )
    assert action == '[Combat narration: Goblin is bloodied.]'
    assert 'bloodied' in ctx.lower()
    assert 'Goblin' in ctx


def test_directive_downed_includes_combatant_name_and_framing():
    trigger = {'kind': 'COMBATANT_DOWNED', 'name': 'Goblin'}
    action, ctx = orch.compute_combat_narration_directive(
        trigger, _combat_state(), _scene_combat(),
    )
    assert action == '[Combat narration: Goblin dropped.]'
    assert 'combatant_downed' in ctx
    assert 'Goblin' in ctx


def test_directive_renders_categorical_hp_labels_never_exact_numbers():
    """Prompt-side enforcement of spec §2: per-combatant HP states render as
    categorical labels (healthy/bloodied/downed/dead), never exact HP/max
    integers. This is the cliff-edge — exact HP in prompt would let the LLM
    infer tactical optimization."""
    trigger = {'kind': 'ROUND_START', 'round': 1}
    state = _combat_state([
        {'name': 'Donovan', 'hp_current': 11, 'hp_max': 13, 'init': 14, 'alive': 1},
        {'name': 'Goblin',  'hp_current': 5,  'hp_max': 13, 'init': 10, 'alive': 1},
    ])
    action, ctx = orch.compute_combat_narration_directive(
        trigger, state, _scene_combat(),
    )
    # Categorical labels present
    assert 'healthy' in ctx
    assert 'bloodied' in ctx
    # Exact HP integers MUST NOT appear in roster section
    assert ' 11/13 ' not in ctx and '11/13' not in ctx
    assert ' 5/13 ' not in ctx and '5/13' not in ctx
    # Combatant names appear
    assert 'Donovan' in ctx
    assert 'Goblin' in ctx


def test_directive_includes_locked_must_must_not_invariants_verbatim():
    """The §3 MUST/MUST-NOT clauses are the prompt-side enforcement of the
    atmospheric-vs-adjudication doctrine. Verbatim presence is load-bearing —
    any rewording changes the LLM's runtime constraint surface.

    Includes S43-verify-pass-added clauses (phantom NPC + PC action
    attribution) per the post-Scenario-B/A drift findings."""
    trigger = {'kind': 'ROUND_START', 'round': 1}
    action, ctx = orch.compute_combat_narration_directive(
        trigger, _combat_state(), _scene_combat(),
    )
    # Header
    assert 'COMBAT NARRATION INVARIANTS' in ctx
    # MUST clauses
    assert 'MUST: summarize what listener confirmed' in ctx
    assert 'MUST: stay inside atmospheric continuity' in ctx
    # Original MUST NOTs (cliff-edge clauses)
    assert 'MUST NOT: establish new mechanical state' in ctx
    assert 'MUST NOT: narrate speculative outcomes' in ctx
    assert 'MUST NOT: declare a kill' in ctx
    assert 'MUST NOT: invent damage numbers' in ctx
    assert "MUST NOT: infer enemy morale" in ctx
    assert 'MUST NOT: describe action that didn\'t happen this round' in ctx
    # S43 verify-pass additions
    assert 'MUST NOT: introduce or narrate actions for any combatant NOT in the init roster' in ctx
    assert 'MUST NOT: attribute specific actions' in ctx


def test_directive_round_start_emphasizes_environmental_atmosphere():
    """S43 verify-pass drift fix: ROUND_START framing must steer the LLM
    toward environment (lighting/sound/tension/mood) rather than combatant
    actions. Pre-patch the bot was narrating 'Donovan darts forward' at
    round-top despite no player input."""
    trigger = {'kind': 'ROUND_START', 'round': 1}
    action, ctx = orch.compute_combat_narration_directive(
        trigger, _combat_state(), _scene_combat(),
    )
    assert 'environment' in ctx.lower() or 'tension' in ctx.lower()
    assert 'Do NOT narrate specific combatant actions' in ctx
    # Examples cued to keep the LLM on-rails
    assert 'darts forward' in ctx or 'raises their weapon' in ctx


def test_directive_combat_header_uses_atmospheric_continuity_framing():
    """The header line itself names the doctrine line — 'atmospheric, not
    adjudicative' is the rejection criterion the LLM should keep in mind."""
    trigger = {'kind': 'ROUND_START', 'round': 1}
    action, ctx = orch.compute_combat_narration_directive(
        trigger, _combat_state(), _scene_combat(),
    )
    assert 'atmospheric, not adjudicative' in ctx


def test_directive_round_start_does_not_preview_next_turn():
    """ROUND_START framing must instruct the LLM to NOT preview next-turn
    actions (excluded per spec §1 'no future-round projection')."""
    trigger = {'kind': 'ROUND_START', 'round': 2}
    action, ctx = orch.compute_combat_narration_directive(
        trigger, _combat_state(), _scene_combat(),
    )
    assert 'Do NOT preview next-turn actions' in ctx


def test_directive_bloodied_does_not_describe_about_to_fall():
    """BLOODIED framing must instruct the LLM to NOT describe the combatant
    as about to fall (cliff-edge: bloodied is not 'pre-dying')."""
    trigger = {'kind': 'BLOODIED_THRESHOLD_CROSSED', 'name': 'Goblin'}
    action, ctx = orch.compute_combat_narration_directive(
        trigger, _combat_state(), _scene_combat(),
    )
    assert 'Do NOT describe them as about-to-fall' in ctx


def test_directive_downed_uses_unconscious_framing_not_death():
    """DOWNED framing must use 'unconscious / down / out of the fight' —
    NOT 'dead' — unless listener confirms death-save failure."""
    trigger = {'kind': 'COMBATANT_DOWNED', 'name': 'Goblin'}
    action, ctx = orch.compute_combat_narration_directive(
        trigger, _combat_state(), _scene_combat(),
    )
    assert 'Do NOT declare death' in ctx
    assert ('unconscious' in ctx.lower() or 'down' in ctx.lower() or
            'out of the fight' in ctx.lower())


def test_directive_roster_includes_conditions_when_present():
    trigger = {'kind': 'ROUND_START', 'round': 1}
    state = _combat_state([
        {'name': 'Goblin', 'hp_current': 13, 'hp_max': 13, 'init': 10,
         'alive': 1, 'conditions': 'frightened'},
    ])
    action, ctx = orch.compute_combat_narration_directive(
        trigger, state, _scene_combat(),
    )
    assert 'frightened' in ctx
    assert 'conditions' in ctx.lower()


def test_directive_roster_renders_dead_label_when_alive_zero():
    trigger = {'kind': 'ROUND_START', 'round': 1}
    state = _combat_state([
        {'name': 'Corpse', 'hp_current': -10, 'hp_max': 13, 'init': 5,
         'alive': 0},
    ])
    action, ctx = orch.compute_combat_narration_directive(
        trigger, state, _scene_combat(),
    )
    assert 'dead' in ctx.lower()


# ─── combat_narration_log_summary log line shape ──────────────────

def test_log_summary_fired_true_includes_kind():
    trigger = {'kind': 'ROUND_START', 'round': 3}
    line = orch.combat_narration_log_summary(trigger, fired=True)
    assert 'combat_narration_fired:' in line
    assert 'kind=ROUND_START' in line
    assert 'fired=1' in line


def test_log_summary_fired_false_with_reason():
    trigger = {'kind': 'BLOODIED_THRESHOLD_CROSSED', 'name': 'Goblin'}
    line = orch.combat_narration_log_summary(
        trigger, fired=False, reason='mode_gate_or_empty',
    )
    assert 'fired=0' in line
    assert "name='Goblin'" in line
    assert 'reason=mode_gate_or_empty' in line


def test_log_summary_handles_missing_trigger_gracefully():
    line = orch.combat_narration_log_summary({}, fired=False, reason='no_trigger')
    assert 'kind=unknown' in line
    assert 'fired=0' in line


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
