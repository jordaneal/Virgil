"""S65 Fix 3 — DC-less roll closure tests.

Verifies the engine-computed DC pipeline:
  (1) RollDecision auto-fills `dc` from severity in `__post_init__` for
      skill_check / save categories.
  (2) Attack rolls leave `dc=None` (Avrae handles attack-vs-AC).
  (3) Caller-supplied DC wins over the auto-fill.
  (4) `should_call_roll` returns decisions with a DC populated for every
      non-attack roll path.
  (5) `to_prompt_directive` renders the DC inline as a literal integer,
      NOT as a `<DC>` placeholder.
  (6) Five different skill checks in succession all produce engine-bound
      DC — the adversarial verify scenario from the S65 plan.
  (7) Resolution binding consumes the engine-pre-filled DC through
      parse_skill_and_dc('perception 15') → ('perception', 15).

Run:
    cd /home/jordaneal/scripts && python3 test_dc_less_roll_closure.py
"""

import sys
from pathlib import Path

sys.path.insert(0, '/home/jordaneal/scripts')

import dnd_orchestration as orch
from dnd_orchestration import (
    RollDecision,
    _SEVERITY_TO_DC,
    _DEFAULT_DC_FOR_UNKNOWN_SEVERITY,
    should_call_roll,
    parse_skill_and_dc,
    INTENT_EXPLORATION, INTENT_CONTESTED, INTENT_RISKY,
    INTENT_COMBAT, INTENT_META, INTENT_TRIVIAL, INTENT_SOCIAL,
)


# ── (1) RollDecision __post_init__ DC auto-fill ──────────────────────

def test_skill_check_meaningful_autofills_dc_15():
    rd = RollDecision(True, skill='perception', category='skill_check', severity='meaningful')
    assert rd.dc == 15, f"expected DC 15, got {rd.dc}"


def test_skill_check_minor_autofills_dc_10():
    rd = RollDecision(True, skill='athletics', category='skill_check', severity='minor')
    assert rd.dc == 10, f"expected DC 10, got {rd.dc}"


def test_skill_check_dire_autofills_dc_20():
    rd = RollDecision(True, skill='persuasion', category='skill_check', severity='dire')
    assert rd.dc == 20, f"expected DC 20, got {rd.dc}"


def test_save_meaningful_autofills_dc_15():
    rd = RollDecision(True, save='dex', category='save', severity='meaningful')
    assert rd.dc == 15, f"save should auto-fill DC, got {rd.dc}"


def test_save_dire_autofills_dc_20():
    rd = RollDecision(True, save='wis', category='save', severity='dire')
    assert rd.dc == 20, f"dire save → DC 20, got {rd.dc}"


# ── (2) Attack rolls leave DC None ───────────────────────────────────

def test_attack_dc_stays_none():
    rd = RollDecision(True, category='attack', severity='meaningful',
                      reason='Attack roll')
    assert rd.dc is None, f"attack should leave DC=None, got {rd.dc}"


def test_initiative_dc_stays_none():
    rd = RollDecision(True, category='initiative', severity='meaningful',
                      reason='Init roll')
    assert rd.dc is None


def test_no_roll_dc_stays_none():
    rd = RollDecision(False, reason='Trivial action')
    assert rd.dc is None


# ── (3) Caller-supplied DC wins ──────────────────────────────────────

def test_caller_supplied_dc_wins_over_autofill():
    rd = RollDecision(True, skill='perception', category='skill_check',
                      severity='meaningful', dc=25)
    assert rd.dc == 25, f"caller-supplied DC=25 should win, got {rd.dc}"


def test_caller_supplied_dc_zero_is_respected():
    """DC=0 is a degenerate but legal value (theater check). Caller wins."""
    rd = RollDecision(True, skill='perception', category='skill_check',
                      severity='meaningful', dc=0)
    assert rd.dc == 0, f"DC=0 should be respected, got {rd.dc}"


# ── (4) should_call_roll populates DC on every non-attack path ──────

def test_should_call_roll_exploration_has_dc():
    decision = should_call_roll(INTENT_EXPLORATION, 'exploration',
                                'I search the desk drawers carefully', None)
    assert decision.needs_roll
    assert decision.dc == 15, f"exploration roll should have DC=15, got {decision.dc}"


def test_should_call_roll_contested_social_has_dc():
    decision = should_call_roll(INTENT_CONTESTED, 'social',
                                'I try to persuade him to talk', None)
    assert decision.needs_roll
    assert decision.dc == 15, f"contested in social should have DC=15, got {decision.dc}"


def test_should_call_roll_contested_combat_has_dire_dc():
    decision = should_call_roll(INTENT_CONTESTED, 'combat',
                                'I try to intimidate him to drop the weapon', None)
    assert decision.needs_roll
    assert decision.dc == 20, f"contested in combat should have DC=20 (dire), got {decision.dc}"


def test_should_call_roll_risky_has_dc():
    decision = should_call_roll(INTENT_RISKY, 'exploration',
                                'I sneak past the guard', None)
    assert decision.needs_roll
    assert decision.dc == 15, f"risky should have DC=15, got {decision.dc}"


def test_should_call_roll_combat_attack_has_no_dc():
    """Combat-intent → attack roll → DC stays None (Avrae handles)."""
    decision = should_call_roll(INTENT_COMBAT, 'combat',
                                'I attack the goblin with my sword', None)
    assert decision.needs_roll
    assert decision.dc is None


# ── (5) to_prompt_directive renders DC inline ────────────────────────

def test_directive_renders_dc_as_literal_integer():
    rd = RollDecision(True, skill='perception', category='skill_check',
                      severity='meaningful')
    out = rd.to_prompt_directive()
    assert '<DC>' not in out, f"<DC> placeholder must NOT appear in directive"
    # S65.A format unification — actor-outside-box shape. Box contains
    # only bare Avrae syntax (`!check perception 15`); actor name lives
    # in bold prefix outside the backticks.
    assert '- **<First Name>:** `!check perception 15`' in out, \
        f"new actor-outside-box shape missing; got: {out[:500]}"
    # Legacy bold-around-command wrap must NOT appear
    assert '**!check perception' not in out, \
        f"legacy bold-around-command wrap leaked into new template: {out[:500]}"
    # Old actor-inside-box shape must NOT appear
    assert '`!check perception 15 : <First Name>`' not in out, \
        f"old actor-inside-box shape leaked into new template: {out[:500]}"


def test_directive_says_engine_computed_dc():
    rd = RollDecision(True, skill='stealth', category='skill_check',
                      severity='dire')
    out = rd.to_prompt_directive()
    assert 'Engine-computed DC: 20' in out


def test_directive_emit_verbatim_instruction():
    """Directive instructs LLM to emit DC VERBATIM — no substitution allowed."""
    rd = RollDecision(True, skill='perception', category='skill_check',
                      severity='meaningful')
    out = rd.to_prompt_directive()
    assert 'emit it VERBATIM' in out or 'engine-computed' in out.lower()


def test_directive_preserves_difficulty_tier_table():
    """Tier table is preserved for informational purposes (narrative
    should match the tier, even though the LLM doesn't pick the DC)."""
    rd = RollDecision(True, skill='perception', category='skill_check',
                      severity='meaningful')
    out = rd.to_prompt_directive()
    assert 'DIFFICULTY TIER' in out
    assert '5  = trivial' in out
    assert '10 = easy' in out
    assert '15 = medium' in out
    assert '20 = hard' in out


# ── (6) Adversarial: five different skill checks in succession ──────

def test_five_skill_checks_all_have_dc():
    """Per S65 plan adversarial verify: trigger five different skill
    checks in succession; assert all five produce engine-bound DC."""
    scenarios = [
        (INTENT_EXPLORATION, 'exploration', 'I search the chest for traps'),
        (INTENT_EXPLORATION, 'exploration', 'I listen at the door'),
        (INTENT_CONTESTED,   'social',      'I try to bluff the guard'),
        (INTENT_RISKY,       'exploration', 'I attempt to pick the lock'),
        (INTENT_CONTESTED,   'social',      'I intimidate the merchant'),
    ]
    results = []
    for intent, mode, text in scenarios:
        d = should_call_roll(intent, mode, text, None)
        results.append((text, d.needs_roll, d.dc))
    # All five must have needs_roll=True AND a non-None DC
    for text, needs_roll, dc in results:
        assert needs_roll, f"{text!r} should have needs_roll=True"
        assert dc is not None, f"{text!r} produced DC-less roll (DC=None)"
        assert dc in _SEVERITY_TO_DC.values(), \
            f"{text!r} DC={dc} not in severity table"


# ── (7) Resolution binding consumes the engine-pre-filled DC ────────

def test_parse_skill_and_dc_consumes_engine_dc():
    """The directive emits `!check perception 15`; parse_skill_and_dc
    must extract ('perception', 15) so Ship 1/A resolution binding fires
    with the engine-pre-filled DC."""
    skill, dc = parse_skill_and_dc('perception 15')
    assert skill == 'perception'
    assert dc == 15


def test_parse_skill_and_dc_multi_word_skill():
    skill, dc = parse_skill_and_dc('sleight of hand 20')
    assert skill == 'sleight of hand'
    assert dc == 20


def test_parse_skill_and_dc_no_dc_falls_through():
    """Pre-S65-Fix-3 the LLM might still emit a DC-less directive
    (regression from forgetting the template). parse_skill_and_dc must
    return (skill, None) — resolution binding falls through to
    free-narration on no-DC arrival per RESOLUTION_BINDING_SPEC §11.2."""
    skill, dc = parse_skill_and_dc('perception')
    assert skill == 'perception'
    assert dc is None


# ── Severity table itself is canonical ──────────────────────────────

def test_severity_to_dc_table_values():
    assert _SEVERITY_TO_DC['minor'] == 10
    assert _SEVERITY_TO_DC['meaningful'] == 15
    assert _SEVERITY_TO_DC['dire'] == 20


def test_default_dc_for_unknown_severity_is_medium():
    """Unknown severity defaults to DC 15 (medium)."""
    rd = RollDecision(True, skill='perception', category='skill_check',
                      severity='unknown_severity')
    assert rd.dc == 15


# ── Test driver ─────────────────────────────────────────────────────

def main():
    tests = [
        # (1) auto-fill
        test_skill_check_meaningful_autofills_dc_15,
        test_skill_check_minor_autofills_dc_10,
        test_skill_check_dire_autofills_dc_20,
        test_save_meaningful_autofills_dc_15,
        test_save_dire_autofills_dc_20,
        # (2) attack/init/no-roll
        test_attack_dc_stays_none,
        test_initiative_dc_stays_none,
        test_no_roll_dc_stays_none,
        # (3) caller-supplied
        test_caller_supplied_dc_wins_over_autofill,
        test_caller_supplied_dc_zero_is_respected,
        # (4) should_call_roll
        test_should_call_roll_exploration_has_dc,
        test_should_call_roll_contested_social_has_dc,
        test_should_call_roll_contested_combat_has_dire_dc,
        test_should_call_roll_risky_has_dc,
        test_should_call_roll_combat_attack_has_no_dc,
        # (5) directive
        test_directive_renders_dc_as_literal_integer,
        test_directive_says_engine_computed_dc,
        test_directive_emit_verbatim_instruction,
        test_directive_preserves_difficulty_tier_table,
        # (6) adversarial five-in-succession
        test_five_skill_checks_all_have_dc,
        # (7) resolution binding consumes DC
        test_parse_skill_and_dc_consumes_engine_dc,
        test_parse_skill_and_dc_multi_word_skill,
        test_parse_skill_and_dc_no_dc_falls_through,
        # severity table canonical
        test_severity_to_dc_table_values,
        test_default_dc_for_unknown_severity_is_medium,
    ]
    fails = []
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except AssertionError as e:
            print(f"FAIL  {t.__name__}: {e}")
            fails.append(t.__name__)
        except Exception as e:
            print(f"ERROR {t.__name__}: {type(e).__name__}: {e}")
            fails.append(t.__name__)
    if fails:
        print(f"\n{len(fails)} test(s) failed: {fails}")
        sys.exit(1)
    print(f"\nAll {len(tests)} tests passed.")


if __name__ == '__main__':
    main()
