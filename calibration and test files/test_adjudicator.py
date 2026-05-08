"""Unit tests for adjudicator (Track 7 #1).

Coverage:
  1. Classification correctness across the five categories + FALLBACK.
  2. World-boundary phrase set — refusal regardless of character.
  3. Combat gate — active/inactive states.
  4. Capability gate — spell, class feature, racial.
  5. CHECK roll consumption (consumed vs pending) + DC band selection.
  6. Render functions — non-empty for binding constraints, empty for FREE.
  7. S9 INVALID code path — first activation under adjudication (§11.K).
  8. ADJUDICATION_ENABLED flag — disables to FALLBACK.

Spec source: /home/jordaneal/virgil-docs/ADJUDICATION_LAYER_SPEC.md
"""
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import adjudicator  # noqa: E402
import dnd_orchestration as orch  # noqa: E402


def _ctx(name='Donovan', char_class='rogue', level=4,
         attacks=None, tags=None):
    return orch.CharacterContext(
        name=name,
        char_class=char_class,
        level=level,
        attacks=attacks or [],
        narrative_tags=tags or set(),
    )


def _scene(mode='exploration', tension=0):
    return {'mode': mode, 'tension_int': tension}


def _check_event(actor, skill, result, ts=None):
    return {
        'actor': actor,
        'kind': 'check',
        'detail': skill,
        'result': result,
        'nat': result,
        'ts': ts if ts is not None else time.time(),
    }


# ──────────────────────────────────────────────────────────
# 1. World-boundary refusal
# ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("text", [
    "I spawn 100000 crystals at my feet",
    "I conjure infinite gold",
    "I become a god of the underworld",
    "I ascend to godhood",
    "I poop out a crystal baby",
    "I rewrite the rules of physics",
    "I am the DM now",
    "I create 500 zombies",
    "I summon 1000 drakes",
    "I one-shot the dragon",
])
def test_world_boundary_refuses(text):
    r = adjudicator.adjudicate(text)
    assert r.category == adjudicator.WORLD_BOUNDARY_ACTION
    assert r.allowed is False
    assert r.refusal_kind == adjudicator.REFUSAL_WORLD_BOUNDARY
    assert r.narration_constraint  # non-empty


def test_world_boundary_overrides_combat():
    """World-boundary precedence beats combat verbs in same input."""
    r = adjudicator.adjudicate("I attack and become a god")
    assert r.category == adjudicator.WORLD_BOUNDARY_ACTION
    assert r.allowed is False


def test_world_boundary_does_not_match_normal_play():
    r = adjudicator.adjudicate("I summon my courage and step forward")
    assert r.category != adjudicator.WORLD_BOUNDARY_ACTION


# ──────────────────────────────────────────────────────────
# 2. Combat gate
# ──────────────────────────────────────────────────────────

def test_combat_action_refused_when_mode_not_combat():
    r = adjudicator.adjudicate(
        "I attack the bartender",
        scene_state=_scene(mode='social'),
        character=_ctx(),
    )
    assert r.category == adjudicator.COMBAT_ACTION
    assert r.allowed is False
    assert r.refusal_kind == adjudicator.REFUSAL_COMBAT_INACTIVE


def test_combat_action_refused_when_combatants_empty():
    r = adjudicator.adjudicate(
        "I swing at the goblin",
        scene_state=_scene(mode='combat'),
        combatants=[],
        active_turn={'character_name': 'Donovan', 'round': 1},
    )
    assert r.category == adjudicator.COMBAT_ACTION
    assert r.allowed is False


def test_combat_action_refused_when_no_active_turn():
    r = adjudicator.adjudicate(
        "I attack the goblin",
        scene_state=_scene(mode='combat'),
        combatants=[{'name': 'Goblin', 'alive': 1}],
        active_turn=None,
    )
    assert r.allowed is False


def test_combat_action_allowed_when_fully_active():
    r = adjudicator.adjudicate(
        "I attack the goblin",
        scene_state=_scene(mode='combat'),
        character=_ctx(),
        combatants=[
            {'name': 'Goblin', 'alive': 1, 'hp_current': 7, 'hp_max': 7}
        ],
        active_turn={'character_name': 'Donovan', 'controller_id': 1, 'round': 1},
    )
    assert r.category == adjudicator.COMBAT_ACTION
    assert r.allowed is True
    assert r.refusal_kind == ''
    assert 'ACTIVE' in r.narration_constraint


# ──────────────────────────────────────────────────────────
# 3. Capability gate
# ──────────────────────────────────────────────────────────

def test_spell_refused_for_non_caster():
    r = adjudicator.adjudicate(
        "I cast Fireball at the goblins",
        scene_state=_scene(mode='exploration'),
        character=_ctx(char_class='rogue', level=4),
    )
    assert r.category == adjudicator.CAPABILITY_ACTION
    assert r.allowed is False
    assert r.refusal_kind == adjudicator.REFUSAL_CAPABILITY


def test_spell_refused_for_low_level_caster():
    r = adjudicator.adjudicate(
        "I cast Fireball",
        character=_ctx(char_class='wizard', level=1),
    )
    assert r.category == adjudicator.CAPABILITY_ACTION
    assert r.allowed is False


def test_spell_allowed_for_high_level_caster():
    r = adjudicator.adjudicate(
        "I cast Fireball at the goblins",
        scene_state=_scene(mode='exploration'),
        character=_ctx(char_class='wizard', level=5),
    )
    assert r.category == adjudicator.CAPABILITY_ACTION
    assert r.allowed is True


def test_class_feature_refused_for_wrong_class():
    r = adjudicator.adjudicate(
        "I rage and charge",
        character=_ctx(char_class='wizard', level=5),
    )
    assert r.category == adjudicator.CAPABILITY_ACTION
    assert r.allowed is False


def test_class_feature_allowed_for_matching_class():
    r = adjudicator.adjudicate(
        "I activate rage and bellow",
        character=_ctx(char_class='barbarian', level=2),
    )
    assert r.category == adjudicator.CAPABILITY_ACTION
    assert r.allowed is True


def test_capability_passes_when_no_character_context():
    """Defer (allow) when we can't verify — partial-projections doctrine."""
    r = adjudicator.adjudicate(
        "I cast Fireball",
        character=None,
    )
    # No character → can't refuse; passes through
    assert r.allowed is True


# ──────────────────────────────────────────────────────────
# 4. CHECK_ACTION + roll consumption + DC bands
# ──────────────────────────────────────────────────────────

def test_check_required_when_no_roll_buffered():
    r = adjudicator.adjudicate(
        "I sneak past the guard",
        scene_state=_scene(mode='exploration'),
        character=_ctx(),
        avrae_events=[],
    )
    assert r.category == adjudicator.CHECK_ACTION
    assert r.skill == 'stealth'
    assert r.dc is not None
    assert r.roll_consumed is False
    assert '!check stealth' in r.narration_constraint


def test_check_consumes_buffered_roll_success():
    r = adjudicator.adjudicate(
        "I sneak past the guard",
        scene_state=_scene(mode='exploration'),
        character=_ctx(name='Donovan'),
        avrae_events=[_check_event('Donovan', 'stealth', 18)],
    )
    assert r.category == adjudicator.CHECK_ACTION
    assert r.roll_consumed is True
    assert r.roll_value == 18
    assert r.success is True


def test_check_consumes_buffered_roll_failure():
    r = adjudicator.adjudicate(
        "I sneak past the guard",
        scene_state=_scene(mode='exploration'),
        character=_ctx(name='Donovan'),
        avrae_events=[_check_event('Donovan', 'stealth', 5)],
    )
    assert r.roll_consumed is True
    assert r.success is False
    assert r.allowed is False
    assert r.refusal_kind == adjudicator.REFUSAL_CHECK_FAILED
    assert 'FAILURE' in r.narration_constraint


def test_check_does_not_consume_other_actor_roll():
    r = adjudicator.adjudicate(
        "I sneak past the guard",
        character=_ctx(name='Donovan'),
        avrae_events=[_check_event('Frank', 'stealth', 18)],
    )
    assert r.roll_consumed is False


def test_check_does_not_consume_wrong_skill_roll():
    r = adjudicator.adjudicate(
        "I sneak past the guard",
        character=_ctx(name='Donovan'),
        avrae_events=[_check_event('Donovan', 'perception', 18)],
    )
    assert r.roll_consumed is False


def test_dc_band_easy_for_low_tension_exploration():
    r = adjudicator.adjudicate(
        "I search the dusty shelf",
        scene_state=_scene(mode='exploration', tension=0),
        character=_ctx(),
    )
    assert r.category == adjudicator.CHECK_ACTION
    assert r.dc == adjudicator.DC_EASY
    assert r.dc_band == 'easy'


def test_dc_band_hard_for_combat_exploration():
    r = adjudicator.adjudicate(
        "I search for hidden traps",
        scene_state=_scene(mode='combat', tension=3),
        character=_ctx(),
    )
    assert r.category == adjudicator.CHECK_ACTION
    assert r.dc == adjudicator.DC_HARD


def test_dc_band_hard_for_intimidation():
    r = adjudicator.adjudicate(
        "I intimidate the merchant",
        scene_state=_scene(mode='social'),
        character=_ctx(),
    )
    assert r.category == adjudicator.CHECK_ACTION
    assert r.dc == adjudicator.DC_HARD


# ──────────────────────────────────────────────────────────
# 5. FREE_ACTION baseline
# ──────────────────────────────────────────────────────────

def test_free_action_for_casual_chat():
    r = adjudicator.adjudicate(
        "I order an ale and chat with the bartender",
        scene_state=_scene(mode='social'),
        character=_ctx(),
    )
    assert r.category == adjudicator.FREE_ACTION
    assert r.allowed is True
    assert r.narration_constraint == ''


def test_meta_question_is_free():
    r = adjudicator.adjudicate("Out of character: how does grappling work?")
    assert r.category == adjudicator.FREE_ACTION
    assert r.narration_constraint == ''


def test_empty_input_is_fallback():
    r = adjudicator.adjudicate("")
    assert r.category == adjudicator.FALLBACK
    assert r.narration_constraint == ''


# ──────────────────────────────────────────────────────────
# 6. Render functions
# ──────────────────────────────────────────────────────────

def test_render_block_empty_for_free():
    r = adjudicator.AdjudicationResult(
        category=adjudicator.FREE_ACTION, allowed=True,
        narration_constraint='', signals={},
    )
    assert adjudicator.render_adjudication_block(r) == ''
    assert adjudicator.render_adjudication_hardstop_echo(r) == ''


def test_render_block_non_empty_for_refusal():
    r = adjudicator.adjudicate("I become a god")
    assert adjudicator.render_adjudication_block(r)
    assert adjudicator.render_adjudication_hardstop_echo(r)


def test_log_summary_always_returns_string():
    r = adjudicator.adjudicate("I look around the tavern")
    line = adjudicator.adjudication_log_summary(r)
    assert 'category=' in line
    assert 'allowed=' in line


# ──────────────────────────────────────────────────────────
# 7. S9 INVALID code path (§11.K activation)
# ──────────────────────────────────────────────────────────

def test_s9_invalid_render_does_not_crash():
    """Adjudication is the first INVALID producer in v1. Confirm S9's
    INVALID render branch executes without exception."""
    decision = orch.CapabilityDecision(
        needs_check=True,
        verdict=orch.CapabilityVerdict.INVALID,
        capability='sword',
        matched_attack='',
        reason='test-only — explicit contradiction',
    )
    rendered = decision.to_prompt_directive()
    assert isinstance(rendered, str)
    assert rendered  # non-empty
    assert 'sword' in rendered.lower()


# ──────────────────────────────────────────────────────────
# 8. Feature flag (§9 rollback)
# ──────────────────────────────────────────────────────────

def test_disabled_returns_fallback(monkeypatch):
    monkeypatch.setattr(adjudicator, 'ADJUDICATION_ENABLED', False)
    r = adjudicator.adjudicate(
        "I become a god",  # would normally be world_boundary refusal
        scene_state=_scene(),
        character=_ctx(),
    )
    assert r.category == adjudicator.FALLBACK
    assert r.allowed is True
    assert r.narration_constraint == ''


# ──────────────────────────────────────────────────────────
# 9. Signals shape — telemetry contract (§11.I)
# ──────────────────────────────────────────────────────────

def test_signals_includes_required_keys():
    r = adjudicator.adjudicate(
        "I sneak past",
        scene_state=_scene(),
        character=_ctx(),
        avrae_events=[_check_event('Donovan', 'stealth', 12)],
    )
    sig = r.signals
    for key in ('category', 'allowed', 'refusal_kind', 'skill', 'dc',
                'band', 'roll_consumed', 'roll_value', 'success'):
        assert key in sig
