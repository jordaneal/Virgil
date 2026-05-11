"""Deterministic tests for Ship 1 (S34) — Resolution Binding engine layer.

Covers RESOLUTION_BINDING_SPEC.md §12.1:
  - ResolutionResult dataclass instantiation + immutability
  - resolve_directive pass/fail/save/cast/None branches
  - boundary (roll_total == dc) and nat/crit captures
  - render_resolution_block PASSED + FAILED + Title-Cased skill
  - render_resolution_hardstop_echo single-line shape
  - resolution_log_summary directive_resolved / directive_resolution_skipped lines

Pure-function tests — no DB, no Discord, no LLM calls.

Run:
    cd /home/jordaneal/scripts && python3 test_resolve_directive.py
"""

import sys
from pathlib import Path

sys.path.insert(0, '/home/jordaneal/scripts')

import dnd_orchestration as orch
from dnd_orchestration import (
    ResolutionResult,
    resolve_directive,
    resolution_log_summary,
    render_resolution_block,
    render_resolution_hardstop_echo,
)


def _row(dc=10, actor='Donovan Ruby', skill='perception', campaign_id=22):
    return {
        'actor_name': actor,
        'check_type': skill,
        'dc': dc,
        'campaign_id': campaign_id,
        'created_at': '',
        'expires_at': '',
        'source_message_id': 'msg_x',
    }


def _event(kind='check', result=14, nat=None, crit=False, ts=1.0):
    return {
        'kind': kind,
        'result': result,
        'nat': nat,
        'crit': crit,
        'ts': ts,
        'actor': 'Donovan Ruby',
        'detail': 'perception',
    }


# ─── resolve_directive happy path ────────────────────────────────────

def test_resolve_passed_when_roll_total_at_or_above_dc():
    r = resolve_directive(_row(dc=10), _event(kind='check', result=15))
    assert isinstance(r, ResolutionResult)
    assert r.passed is True
    assert r.dc == 10
    assert r.roll_total == 15
    assert r.check_kind == 'check'


def test_resolve_failed_when_roll_total_below_dc():
    r = resolve_directive(_row(dc=10), _event(kind='check', result=6))
    assert r is not None
    assert r.passed is False
    assert r.dc == 10
    assert r.roll_total == 6


def test_resolve_save_kind_produces_same_shape():
    r = resolve_directive(_row(dc=15, skill='dexterity'),
                           _event(kind='save', result=18))
    assert r is not None
    assert r.check_kind == 'save'
    assert r.skill_or_save == 'dexterity'
    assert r.passed is True


def test_resolve_returns_none_for_cast_kind():
    r = resolve_directive(_row(), _event(kind='cast', result=12))
    assert r is None


def test_resolve_returns_none_for_attack_kind():
    # Defensive — attack kind never produces a check/save resolution.
    r = resolve_directive(_row(), _event(kind='attack', result=12))
    assert r is None


def test_resolve_returns_none_when_directive_has_no_dc():
    # Spec §11.2 lock — no-DC directive falls through to free-narration.
    r = resolve_directive(_row(dc=None), _event(kind='check', result=14))
    assert r is None


def test_resolve_returns_none_when_event_result_missing():
    # Spec §4.3 — malformed embed (no result) → None, matcher degrades.
    bad_event = _event()
    bad_event['result'] = None
    r = resolve_directive(_row(), bad_event)
    assert r is None


def test_resolve_captures_nat_when_present():
    # Spec §5.3 — nat field captured even though v1 doesn't act on it.
    r = resolve_directive(_row(dc=10), _event(result=20, nat=20))
    assert r is not None
    assert r.nat == 20


def test_resolve_captures_crit_boolean():
    r = resolve_directive(_row(dc=10), _event(result=20, nat=20, crit=True))
    assert r is not None
    assert r.crit is True


def test_resolve_passed_true_on_boundary_dc_equal_roll():
    # Spec §5.4 — strict >=. roll_total == dc is PASSED.
    r = resolve_directive(_row(dc=10), _event(result=10))
    assert r is not None
    assert r.passed is True


# ─── render_resolution_block ─────────────────────────────────────────

def test_render_block_passed_text():
    r = ResolutionResult(actor='Donovan Ruby', check_kind='check',
                          skill_or_save='perception', dc=10, roll_total=14,
                          passed=True, rolled_at=1.0, directive_id=22)
    block = render_resolution_block(r)
    assert 'Outcome: PASSED.' in block
    assert 'success' in block.lower()
    assert 'Donovan Ruby does achieve the intended outcome' in block
    assert 'Do NOT narrate failure' in block


def test_render_block_failed_text():
    r = ResolutionResult(actor='Donovan Ruby', check_kind='check',
                          skill_or_save='perception', dc=15, roll_total=6,
                          passed=False, rolled_at=1.0, directive_id=22)
    block = render_resolution_block(r)
    assert 'Outcome: FAILED.' in block
    assert 'failure' in block.lower()
    assert 'Donovan Ruby does NOT achieve the intended outcome' in block
    assert 'Do NOT narrate success' in block


def test_render_block_titlecases_multiword_skill():
    r = ResolutionResult(actor='Mia', check_kind='check',
                          skill_or_save='sleight of hand', dc=12, roll_total=15,
                          passed=True, rolled_at=1.0, directive_id=22)
    block = render_resolution_block(r)
    assert 'Sleight Of Hand check' in block, f"missing TitleCase: {block!r}"


def test_render_block_renders_check_literal_for_check_kind():
    r = ResolutionResult(actor='Mia', check_kind='check',
                          skill_or_save='stealth', dc=12, roll_total=15,
                          passed=True, rolled_at=1.0, directive_id=22)
    block = render_resolution_block(r)
    assert 'Stealth check' in block


def test_render_block_renders_save_literal_for_save_kind():
    r = ResolutionResult(actor='Mia', check_kind='save',
                          skill_or_save='dexterity', dc=12, roll_total=15,
                          passed=True, rolled_at=1.0, directive_id=22)
    block = render_resolution_block(r)
    assert 'Dexterity save' in block


# ─── render_resolution_hardstop_echo ─────────────────────────────────

def test_render_hardstop_echo_passed_and_failed_lines():
    passed = ResolutionResult(actor='A', check_kind='check',
                               skill_or_save='p', dc=10, roll_total=10,
                               passed=True, rolled_at=1.0, directive_id=1)
    failed = ResolutionResult(actor='A', check_kind='check',
                               skill_or_save='p', dc=10, roll_total=5,
                               passed=False, rolled_at=1.0, directive_id=1)
    assert render_resolution_hardstop_echo(passed) == 'Outcome: PASSED.'
    assert render_resolution_hardstop_echo(failed) == 'Outcome: FAILED.'
    assert render_resolution_hardstop_echo(None) == ''


# ─── resolution_log_summary ──────────────────────────────────────────

def test_log_summary_for_resolved():
    r = ResolutionResult(actor='Donovan Ruby', check_kind='check',
                          skill_or_save='perception', dc=10, roll_total=14,
                          passed=True, rolled_at=1.0, directive_id=22,
                          nat=11, crit=False)
    line = resolution_log_summary(r, campaign_id=22)
    assert line.startswith('directive_resolved:'), line
    assert 'actor=Donovan Ruby' in line
    assert 'skill=perception' in line
    assert 'dc=10' in line
    assert 'roll_total=14' in line
    assert 'outcome=PASSED' in line


def test_log_summary_for_skipped():
    line = resolution_log_summary(None, campaign_id=22, reason='no_dc')
    assert line.startswith('directive_resolution_skipped:'), line
    assert 'reason=no_dc' in line


# ─── ResolutionResult immutability ───────────────────────────────────

def test_resolution_result_is_immutable():
    # frozen=True — mutation must raise.
    r = ResolutionResult(actor='A', check_kind='check', skill_or_save='p',
                         dc=10, roll_total=10, passed=True, rolled_at=1.0,
                         directive_id=1)
    raised = False
    try:
        r.dc = 99  # type: ignore[misc]
    except Exception:
        raised = True
    assert raised, "ResolutionResult must be immutable (frozen=True)"


# ─── Runner ──────────────────────────────────────────────────────────

if __name__ == '__main__':
    import traceback
    funcs = [v for k, v in sorted(globals().items())
             if k.startswith('test_') and callable(v)]
    failures = []
    for fn in funcs:
        try:
            fn()
            print(f"  ok   {fn.__name__}")
        except AssertionError as e:
            failures.append((fn.__name__, repr(e)))
            print(f"  FAIL {fn.__name__}: {e!r}")
        except Exception as e:
            failures.append((fn.__name__, repr(e)))
            print(f"  ERR  {fn.__name__}: {e!r}")
            traceback.print_exc()
    if failures:
        print(f"\n{len(failures)} failure(s)")
        sys.exit(1)
    print(f"\n{len(funcs)} tests passed.")
