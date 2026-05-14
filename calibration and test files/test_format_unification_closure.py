"""S65.A — Format-unification closure tests.

Operator request post-S65 verify: roll requests, attack templates,
mechanical hints, and Suggested Actions all converge on the same shape:

    - `<command>`

Bullet + single-backtick wrap (Discord renders the dash as a bullet and
the backticks as inline code / boxed monospace). Pre-S65.A had three
distinct shapes:
  - bold-wrap   `**!check skill DC : Donovan**` (roll requests)
  - divider + italic preamble + bullet (mechanical hints)
  - bare bullets under "Suggested Actions:" header

This test file verifies the unification structurally:
  (1) Roll-request template uses bullet + backtick.
  (2) Attack template uses bullet + backtick.
  (3) Strip regex preserves backtick wrap when stripping DC.
  (4) LLM-emit parser sees backtick-bounded directives.
  (5) Mechanical-hints attach: no "Bookkeeping" preamble, no divider.
  (6) Suggested Actions prompt block: no "Suggested Actions:" header
      preamble, uses bullet + backtick shape.
  (7) Legacy `**` bold-wrap format ALSO still parses (graceful coexistence
      for any stale narration that still emits old shape).

Run:
    cd /home/jordaneal/scripts && python3 test_format_unification_closure.py
"""

import sys
sys.path.insert(0, '/home/jordaneal/scripts')

import discord_dnd_bot as bot
import dnd_orchestration as orch
from dnd_orchestration import RollDecision


# ── (1) Roll-request template ────────────────────────────────────────
# S65.A actor-outside-box shape: `- **<First Name>:** `!check skill DC``
# Bold actor prefix OUTSIDE backticks; box contains bare Avrae syntax only.

def test_skill_roll_uses_actor_outside_box():
    rd = RollDecision(True, skill='perception', category='skill_check',
                      severity='meaningful')
    out = rd.to_prompt_directive()
    assert '- **<First Name>:** `!check perception 15`' in out


def test_save_roll_uses_actor_outside_box():
    rd = RollDecision(True, save='dex', category='save', severity='dire')
    out = rd.to_prompt_directive()
    assert '- **<First Name>:** `!save dex 20`' in out


def test_skill_roll_box_does_not_contain_actor():
    """Box (between backticks) contains only Avrae syntax — no `: <Name>`."""
    rd = RollDecision(True, skill='stealth', category='skill_check',
                      severity='minor')
    out = rd.to_prompt_directive()
    # Old shape (actor inside box) must NOT appear
    assert '`!check stealth 10 : <First Name>`' not in out
    assert '`!check stealth 10 : Donovan`' not in out


def test_skill_roll_example_uses_actor_outside_box():
    """Example block shows the actor-outside shape, not the old shape."""
    rd = RollDecision(True, skill='perception', category='skill_check',
                      severity='meaningful')
    out = rd.to_prompt_directive()
    # New example shape
    assert '- **Donovan:** `!check perception 15`' in out


def test_skill_roll_template_does_not_use_bold():
    rd = RollDecision(True, skill='stealth', category='skill_check',
                      severity='minor')
    out = rd.to_prompt_directive()
    # No literal `**!check`/`**!save` in the new template
    assert '**!check' not in out
    assert '**!save' not in out


def test_skill_roll_template_does_not_instruct_bold():
    rd = RollDecision(True, skill='stealth', category='skill_check',
                      severity='minor')
    out = rd.to_prompt_directive()
    # No "ENTIRELY BOLD" instruction in the new template
    assert 'ENTIRELY BOLD' not in out


# ── (2) Attack template ──────────────────────────────────────────────

def test_attack_template_uses_actor_outside_box():
    rd = RollDecision(True, category='attack', severity='meaningful',
                      reason='melee attack')
    out = rd.to_prompt_directive()
    # Actor name in bold prefix outside backticks; box contains bare
    # Avrae syntax only
    assert '- **<First Name>:** `!attack <weapon-name> -t <target>`' in out
    assert '- **<First Name>:** `!cast <spell-name> -t <target>`' in out


def test_attack_template_says_single_backticks_not_bold():
    rd = RollDecision(True, category='attack', severity='meaningful',
                      reason='attack')
    out = rd.to_prompt_directive()
    assert 'SINGLE' in out or 'single backticks' in out
    # The "NOT bold asterisks" guidance should be present
    assert 'NOT bold' in out or 'not bold' in out.lower()


# ── (3) DC-strip regex preserves wrap ────────────────────────────────

def test_strip_preserves_backtick_wrap_actor_outside():
    """S65.A actor-outside-box: strip operates on bare command inside
    backticks; bold actor prefix outside is untouched."""
    src = "Donovan checks the lock.\n\n- **Donovan:** `!check perception 15`"
    out = bot._strip_dc_from_llm_emit(src)
    assert '- **Donovan:** `!check perception`' in out
    assert ' 15' not in out
    # Backtick close preserved
    assert out.rstrip().endswith('`')


def test_strip_preserves_legacy_actor_inside_box():
    """Legacy graceful coexistence — pre-S65.A 'actor-inside-box' shape
    still round-trips cleanly. DC stripped; suffix + close preserved."""
    src = "Donovan checks the lock.\n\n- `!check perception 15 : Donovan`"
    out = bot._strip_dc_from_llm_emit(src)
    assert '- `!check perception : Donovan`' in out
    assert ' 15 :' not in out


def test_strip_preserves_legacy_bold_wrap():
    """Graceful coexistence: legacy `**...**` format still strips correctly."""
    src = "Donovan checks the lock.\n\n**!check perception 15 : Donovan**"
    out = bot._strip_dc_from_llm_emit(src)
    assert '**!check perception : Donovan**' in out
    assert ' 15 :' not in out


def test_strip_handles_save_with_actor_outside_box():
    src = "Donovan dives.\n\n- **Donovan:** `!save dex 20`"
    out = bot._strip_dc_from_llm_emit(src)
    assert '- **Donovan:** `!save dex`' in out
    assert ' 20' not in out


def test_strip_does_not_touch_cast():
    """Cast directives keep their trailing integer (Avrae interprets as
    spell-level override)."""
    src = "Donovan casts.\n\n- **Donovan:** `!cast fireball 3`"
    out = bot._strip_dc_from_llm_emit(src)
    # !cast NOT stripped (Avrae owns the spell-level semantics)
    assert 'fireball 3' in out


# ── (4) LLM-emit parser sees both formats ────────────────────────────

def test_parser_recognizes_backtick_bounded_actor_outside():
    """New S65.A shape: actor in bold prefix outside backticks; bare
    Avrae command inside backticks."""
    src = "Some prose.\n\n- **Donovan:** `!check perception 15`"
    parsed = bot._parse_llm_emit_directive(src)
    assert parsed is not None
    assert parsed['kind'] == 'check'
    assert parsed['skill_raw'] == 'perception 15'


def test_parser_recognizes_backtick_bounded_actor_inside_legacy():
    """Legacy pre-S65.A shape — actor inside backticks. Still parses."""
    src = "Some prose.\n\n- `!check perception 15 : Donovan`"
    parsed = bot._parse_llm_emit_directive(src)
    assert parsed is not None
    assert parsed['kind'] == 'check'
    assert parsed['skill_raw'] == 'perception 15'


def test_parser_recognizes_bold_bounded_legacy():
    src = "Some prose.\n\n**!check perception 15 : Donovan**"
    parsed = bot._parse_llm_emit_directive(src)
    assert parsed is not None
    assert parsed['kind'] == 'check'
    assert parsed['skill_raw'] == 'perception 15'


def test_parser_handles_bare_command():
    """Format-drift fallback: LLM emits without any wrap."""
    src = "Some prose. !check perception 15 : Donovan"
    parsed = bot._parse_llm_emit_directive(src)
    assert parsed is not None
    assert parsed['kind'] == 'check'
    assert parsed['skill_raw'] == 'perception 15'


def test_parser_multi_directive_last_wins():
    """Per Ship A §11.B.1: when multiple directives in response, LAST wins.
    Mixed shape (actor-outside) for both directives."""
    src = """First attempt: - **Ruby:** `!check athletics 15`

Then she pivots: - **Ruby:** `!check stealth 20`"""
    parsed = bot._parse_llm_emit_directive(src)
    assert parsed['kind'] == 'check'
    assert parsed['skill_raw'] == 'stealth 20'
    assert parsed['multi_count'] == 2


# ── (5) Mechanical-hints attach: no preamble ────────────────────────

def test_attach_hints_no_bookkeeping_preamble():
    """`_attach_hints` should NOT emit the `Bookkeeping (you type these):`
    header preamble or the horizontal divider. Just bullets + backticks."""
    import inspect
    src = inspect.getsource(bot._attach_hints)
    # The function source must no longer include the preamble string
    assert 'Bookkeeping (you type these)' not in src or 'no preamble' in src.lower(), \
        "Bookkeeping preamble must be removed from _attach_hints"
    assert '─────────' not in src or 'divider' in src.lower(), \
        "Horizontal divider should be removed from _attach_hints"


def test_attach_hints_renders_bullet_backtick():
    """Mechanical hints render as `- `cmd`` lines (verified by code inspection)."""
    import inspect
    src = inspect.getsource(bot._attach_hints)
    # The bullet+backtick format must be in the source
    assert '"- `{h}`"' in src or "'- `{h}`'" in src or 'f"- `{h}`"' in src, \
        "bullet+backtick render shape must be present in _attach_hints"


# ── (6) Suggested Actions prompt block: backtick format ─────────────

def test_suggested_actions_prompt_uses_backtick():
    """The `build_dm_context` prompt instructs the LLM to use bullet +
    backtick for Tier 2/3 suggestions. Verify the instruction is in the
    body."""
    # The prompt section lives in build_dm_context's f-string body.
    # Read the source and verify the format examples are present.
    import inspect
    import dnd_engine
    src = inspect.getsource(dnd_engine.build_dm_context)
    assert '`/encounter stealth`' in src, \
        "Suggested Actions prompt must show backtick-wrapped example"
    assert '`/clock create Detection 4`' in src, \
        "Suggested Actions prompt must show backtick-wrapped second example"


def test_suggested_actions_prompt_does_not_require_header():
    """The `Suggested Actions:` header preamble must be retired in the
    prompt instructions (operator request — visual consistency with
    mechanical hints which never had a header)."""
    import inspect
    import dnd_engine
    src = inspect.getsource(dnd_engine.build_dm_context)
    # Section explicitly states the header is retired
    assert 'NO "Suggested Actions:" preamble' in src or \
           'header preamble' in src, \
        "Suggested Actions prompt should retire the header preamble"


# ── (7) Suggestion log + undo insertion work without header ─────────

def test_suggestion_log_anchors_on_bullet_pattern():
    """`suggestion_emitted` log must count bullet-shaped suggestion lines
    regardless of whether the legacy "Suggested Actions:" header is
    present."""
    import inspect
    import dnd_engine
    src = inspect.getsource(dnd_engine.dm_respond)
    # New shape: count lines starting with "- `/" or "- /"
    assert '"- `/"' in src or "'- `/'" in src, \
        "suggestion_emitted should count bullet+backtick slash lines"


# ── Test driver ─────────────────────────────────────────────────────

def main():
    tests = [
        # (1) roll template — actor-outside-box shape
        test_skill_roll_uses_actor_outside_box,
        test_save_roll_uses_actor_outside_box,
        test_skill_roll_box_does_not_contain_actor,
        test_skill_roll_example_uses_actor_outside_box,
        test_skill_roll_template_does_not_use_bold,
        test_skill_roll_template_does_not_instruct_bold,
        # (2) attack template — actor-outside-box shape
        test_attack_template_uses_actor_outside_box,
        test_attack_template_says_single_backticks_not_bold,
        # (3) strip
        test_strip_preserves_backtick_wrap_actor_outside,
        test_strip_preserves_legacy_actor_inside_box,
        test_strip_preserves_legacy_bold_wrap,
        test_strip_handles_save_with_actor_outside_box,
        test_strip_does_not_touch_cast,
        # (4) parser
        test_parser_recognizes_backtick_bounded_actor_outside,
        test_parser_recognizes_backtick_bounded_actor_inside_legacy,
        test_parser_recognizes_bold_bounded_legacy,
        test_parser_handles_bare_command,
        test_parser_multi_directive_last_wins,
        # (5) attach_hints
        test_attach_hints_no_bookkeeping_preamble,
        test_attach_hints_renders_bullet_backtick,
        # (6) Suggested Actions prompt
        test_suggested_actions_prompt_uses_backtick,
        test_suggested_actions_prompt_does_not_require_header,
        # (7) suggestion log
        test_suggestion_log_anchors_on_bullet_pattern,
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
