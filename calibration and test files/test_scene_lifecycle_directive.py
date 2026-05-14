"""Tests for compute_scene_lifecycle_directive (Scene Lifecycle v1, S52).

Eleventh §59 sibling — F-54 scene immortality. Pure function tests cover:
  - Mode gate (exploration+social pass; combat+travel reject)
  - Below-threshold quiet baseline (§5.5)
  - Soft tier at _STALE_SOFT_THRESHOLD
  - Hard/strong tier at _STALE_HARD_THRESHOLD
  - Accumulate-indefinitely above hard threshold (§11.G)
  - Explicit trigger bypasses threshold and hold suppression (§11.J/§11.F)
  - Climactic-hold suppression via commitment_directive_active (§11.L)
  - Climactic-hold suppression via last_combat_had_beats + window (§11.L)
  - Climactic-hold suppression clears after window expires
  - Signals dict shape and values
"""

import pytest
from dnd_orchestration import (
    compute_scene_lifecycle_directive,
    _STALE_SOFT_THRESHOLD,
    _STALE_HARD_THRESHOLD,
    _CLIMACTIC_HOLD_WINDOW,
)

EXPLORATION = {'mode': 'exploration'}
SOCIAL = {'mode': 'social'}
COMBAT = {'mode': 'combat'}
TRAVEL = {'mode': 'travel'}


# ─── Mode gate ───────────────────────────────────────────────────────────────

def test_mode_gate_exploration_passes():
    body, signals = compute_scene_lifecycle_directive(
        EXPLORATION, stale_turns=_STALE_SOFT_THRESHOLD, trigger_kind='auto'
    )
    assert body != '' or signals['tier'] != 'none' or signals.get('suppressed_reason')


def test_mode_gate_social_passes():
    body, signals = compute_scene_lifecycle_directive(
        SOCIAL, stale_turns=_STALE_SOFT_THRESHOLD, trigger_kind='auto'
    )
    assert signals['mode'] == 'social'


def test_mode_gate_combat_rejects():
    body, signals = compute_scene_lifecycle_directive(
        COMBAT, stale_turns=_STALE_HARD_THRESHOLD + 5, trigger_kind='auto'
    )
    assert body == ''
    assert signals['fired'] == 0
    assert signals['tier'] == 'none'


def test_mode_gate_travel_rejects():
    body, signals = compute_scene_lifecycle_directive(
        TRAVEL, stale_turns=_STALE_HARD_THRESHOLD + 5, trigger_kind='auto'
    )
    assert body == ''
    assert signals['fired'] == 0


def test_mode_gate_none_scene_rejects():
    body, signals = compute_scene_lifecycle_directive(
        None, stale_turns=_STALE_HARD_THRESHOLD + 5, trigger_kind='auto'
    )
    assert body == ''
    assert signals['fired'] == 0


def test_mode_gate_empty_scene_rejects():
    body, signals = compute_scene_lifecycle_directive(
        {}, stale_turns=_STALE_HARD_THRESHOLD + 5, trigger_kind='auto'
    )
    assert body == ''


# ─── Threshold / quiet baseline ──────────────────────────────────────────────

def test_below_soft_threshold_returns_empty():
    for stale in range(_STALE_SOFT_THRESHOLD):
        body, signals = compute_scene_lifecycle_directive(
            EXPLORATION, stale_turns=stale, trigger_kind='auto'
        )
        assert body == '', f"Expected empty at stale={stale}"
        assert signals['fired'] == 0
        assert signals['tier'] == 'none'


def test_at_soft_threshold_returns_gentle():
    body, signals = compute_scene_lifecycle_directive(
        EXPLORATION, stale_turns=_STALE_SOFT_THRESHOLD, trigger_kind='auto'
    )
    assert body != ''
    assert 'GENTLE' in body
    assert signals['fired'] == 1
    assert signals['tier'] == 'soft'
    assert str(_STALE_SOFT_THRESHOLD) in body


def test_just_below_hard_threshold_returns_soft():
    stale = _STALE_HARD_THRESHOLD - 1
    body, signals = compute_scene_lifecycle_directive(
        EXPLORATION, stale_turns=stale, trigger_kind='auto'
    )
    assert 'GENTLE' in body
    assert signals['tier'] == 'soft'
    assert str(stale) in body


def test_at_hard_threshold_returns_strong():
    body, signals = compute_scene_lifecycle_directive(
        EXPLORATION, stale_turns=_STALE_HARD_THRESHOLD, trigger_kind='auto'
    )
    assert 'COMPRESS NOW' in body
    assert signals['fired'] == 1
    assert signals['tier'] == 'strong'
    assert str(_STALE_HARD_THRESHOLD) in body


def test_above_hard_threshold_accumulates_still_strong():
    # §11.G: accumulate indefinitely; strong fires on every turn above threshold
    for stale in [_STALE_HARD_THRESHOLD + 1, _STALE_HARD_THRESHOLD + 10,
                  _STALE_HARD_THRESHOLD + 50]:
        body, signals = compute_scene_lifecycle_directive(
            EXPLORATION, stale_turns=stale, trigger_kind='auto'
        )
        assert 'COMPRESS NOW' in body, f"Expected COMPRESS NOW at stale={stale}"
        assert signals['tier'] == 'strong'
        assert signals['fired'] == 1


# ─── Explicit trigger ────────────────────────────────────────────────────────

def test_explicit_trigger_fires_at_zero_stale():
    body, signals = compute_scene_lifecycle_directive(
        EXPLORATION, stale_turns=0, trigger_kind='explicit'
    )
    assert 'DM-INITIATED' in body
    assert signals['fired'] == 1
    assert signals['tier'] == 'explicit'


def test_explicit_trigger_includes_reason():
    body, signals = compute_scene_lifecycle_directive(
        EXPLORATION, stale_turns=0, trigger_kind='explicit',
        explicit_reason='the tavern scene has wrapped'
    )
    assert 'the tavern scene has wrapped' in body


def test_explicit_trigger_empty_reason_no_clause():
    body, _ = compute_scene_lifecycle_directive(
        EXPLORATION, stale_turns=0, trigger_kind='explicit',
        explicit_reason=''
    )
    assert 'DM-INITIATED' in body
    assert '""' not in body  # empty reason should not render quoted empty string


def test_explicit_bypasses_climactic_hold():
    # Explicit trigger should NOT be suppressed by commitment or combat beats
    body, signals = compute_scene_lifecycle_directive(
        EXPLORATION, stale_turns=0, trigger_kind='explicit',
        commitment_directive_active=True,
        last_combat_had_beats=True,
        turns_since_combat_end=0,
    )
    assert 'DM-INITIATED' in body
    assert signals['fired'] == 1
    assert signals['suppressed_reason'] == ''


# ─── Climactic-hold suppression ──────────────────────────────────────────────

def test_climactic_hold_via_commitment_suppresses():
    body, signals = compute_scene_lifecycle_directive(
        EXPLORATION, stale_turns=_STALE_SOFT_THRESHOLD,
        trigger_kind='auto',
        commitment_directive_active=True,
    )
    assert body == ''
    assert signals['fired'] == 0
    assert signals['suppressed_reason'] == 'climactic_hold_suppressed'


def test_climactic_hold_via_combat_beats_inside_window():
    body, signals = compute_scene_lifecycle_directive(
        EXPLORATION, stale_turns=_STALE_HARD_THRESHOLD,
        trigger_kind='auto',
        last_combat_had_beats=True,
        turns_since_combat_end=_CLIMACTIC_HOLD_WINDOW - 1,
    )
    assert body == ''
    assert signals['suppressed_reason'] == 'climactic_hold_suppressed'


def test_climactic_hold_no_beats_does_not_suppress():
    # Beats flag is False: recent combat that had no narratable beats shouldn't hold
    body, signals = compute_scene_lifecycle_directive(
        EXPLORATION, stale_turns=_STALE_HARD_THRESHOLD,
        trigger_kind='auto',
        last_combat_had_beats=False,
        turns_since_combat_end=0,
    )
    assert body != ''
    assert signals['fired'] == 1


def test_climactic_hold_outside_window_does_not_suppress():
    # At or beyond window: suppression should lift even if there were beats
    body, signals = compute_scene_lifecycle_directive(
        EXPLORATION, stale_turns=_STALE_HARD_THRESHOLD,
        trigger_kind='auto',
        last_combat_had_beats=True,
        turns_since_combat_end=_CLIMACTIC_HOLD_WINDOW,
    )
    assert body != ''
    assert signals['fired'] == 1
    assert signals['suppressed_reason'] == ''


def test_climactic_hold_commitment_wins_even_without_beats():
    # commitment alone (no beat history) still suppresses
    body, signals = compute_scene_lifecycle_directive(
        EXPLORATION, stale_turns=_STALE_HARD_THRESHOLD,
        trigger_kind='auto',
        commitment_directive_active=True,
        last_combat_had_beats=False,
    )
    assert body == ''
    assert signals['suppressed_reason'] == 'climactic_hold_suppressed'


# ─── Signals dict shape ──────────────────────────────────────────────────────

def test_signals_always_contains_required_keys():
    for mode_dict in [EXPLORATION, SOCIAL, COMBAT, None]:
        _, signals = compute_scene_lifecycle_directive(
            mode_dict, stale_turns=0, trigger_kind='auto'
        )
        for key in ('fired', 'mode', 'stale_turns', 'tier', 'suppressed_reason'):
            assert key in signals, f"Missing key {key!r} for mode={mode_dict}"


def test_signals_stale_turns_reflects_input():
    for stale in [0, 3, 6, 15]:
        _, signals = compute_scene_lifecycle_directive(
            EXPLORATION, stale_turns=stale, trigger_kind='auto'
        )
        assert signals['stale_turns'] == stale


def test_signals_mode_reflects_scene_state():
    _, signals = compute_scene_lifecycle_directive(
        SOCIAL, stale_turns=10, trigger_kind='auto'
    )
    assert signals['mode'] == 'social'


def test_fired_0_when_empty_body():
    body, signals = compute_scene_lifecycle_directive(
        EXPLORATION, stale_turns=0, trigger_kind='auto'
    )
    assert body == ''
    assert signals['fired'] == 0


def test_fired_1_when_body_returned():
    body, signals = compute_scene_lifecycle_directive(
        EXPLORATION, stale_turns=_STALE_SOFT_THRESHOLD, trigger_kind='auto'
    )
    assert body != ''
    assert signals['fired'] == 1


# ─── Directive text content ──────────────────────────────────────────────────

def test_soft_directive_contains_must_not_semantics():
    body, _ = compute_scene_lifecycle_directive(
        EXPLORATION, stale_turns=_STALE_SOFT_THRESHOLD, trigger_kind='auto'
    )
    # Soft directive should lean toward compression but not force it
    assert 'lean toward it' in body
    assert 'escalate' in body


def test_hard_directive_contains_imperative():
    body, _ = compute_scene_lifecycle_directive(
        EXPLORATION, stale_turns=_STALE_HARD_THRESHOLD, trigger_kind='auto'
    )
    assert 'COMPRESS THIS SCENE' in body
    assert 'DO NOT' in body


def test_explicit_directive_contains_move_forward():
    body, _ = compute_scene_lifecycle_directive(
        EXPLORATION, stale_turns=0, trigger_kind='explicit'
    )
    assert 'move forward' in body.lower()
