"""Tests for render_state_footer time-progression extension
(Track 4 #3, Session 27).

Per TRACK_4_3_SPEC.md §9 (tests 28-31). Pure function — no DB.

Run:
    cd /home/jordaneal/scripts && python3 test_render_state_footer_time.py
"""

import sys

sys.path.insert(0, '/home/jordaneal/scripts')

import dnd_orchestration as orch


def _scene(mode='exploration', day=None, phase=None):
    s = {
        'mode': mode,
        'location': '',
        'focus': '',
        'tension': 'low',
        'active_npcs': [],
        'active_threats': [],
    }
    if day is not None:
        s['campaign_day'] = day
    if phase is not None:
        s['day_phase'] = phase
    return s


def _turn(name='Hero', round_=1, controller_id='u1'):
    return {
        'controller_id': controller_id,
        'character_name': name,
        'round': round_,
        'updated_at': '',
    }


# ─── §9 test 28 — backward compat ───────────────────────────────────

def test_legacy_no_time_fields_renders_unchanged():
    # No campaign_day or day_phase keys — should match prior shape exactly.
    s = _scene(mode='exploration')
    body, sig = orch.render_state_footer(s, None, None, [])
    assert body == '📖 Exploration\n'
    assert sig['campaign_day'] is None
    assert sig['day_phase'] is None


# ─── §9 test 29 — exploration with time fields ──────────────────────

def test_exploration_with_day_phase():
    s = _scene(day=3, phase='Evening')
    body, sig = orch.render_state_footer(s, None, None, [])
    assert body == '📖 Exploration · Day 3, Evening\n'
    assert sig['campaign_day'] == 3
    assert sig['day_phase'] == 'Evening'


def test_social_with_day_phase():
    s = _scene(mode='social', day=1, phase='Morning')
    body, _ = orch.render_state_footer(s, None, None, [])
    assert body == '💬 Social · Day 1, Morning\n'


# ─── §9 test 30 — combat header carries time too ────────────────────

def test_combat_with_day_phase():
    s = _scene(mode='combat', day=3, phase='Evening')
    turn = _turn(name='Donovan', round_=2)
    payload = {'combatants': [{
        'name': 'Donovan', 'init': 15, 'alive': 1,
        'hp_current': 20, 'hp_max': 25, 'conditions': '', 'side': 'pc',
    }]}
    body, sig = orch.render_state_footer(s, turn, payload, ['Donovan'])
    # The combat header has multiple lines; the first one carries the
    # round and time suffix.
    first_line = body.split('\n')[0]
    assert '⚔ Combat — Round 2 · Day 3, Evening' == first_line
    assert sig['mode'] == 'combat'
    assert sig['campaign_day'] == 3
    assert sig['day_phase'] == 'Evening'


# ─── §9 test 31 — signals dict shape ────────────────────────────────

def test_signals_dict_includes_time_keys():
    s = _scene(day=5, phase='Late Night')
    _, sig = orch.render_state_footer(s, None, None, [])
    assert 'campaign_day' in sig
    assert 'day_phase' in sig
    assert sig['campaign_day'] == 5
    assert sig['day_phase'] == 'Late Night'


def test_state_footer_log_summary_carries_day_phase():
    sig = {
        'mode': 'exploration', 'active_turn_name': None, 'round': None,
        'campaign_day': 3, 'day_phase': 'Evening',
    }
    out = orch.state_footer_log_summary(sig)
    assert 'day=3' in out
    assert 'phase=Evening' in out


def test_state_footer_log_summary_legacy_renders_none():
    sig = {
        'mode': 'exploration', 'active_turn_name': None, 'round': None,
        'campaign_day': None, 'day_phase': None,
    }
    out = orch.state_footer_log_summary(sig)
    assert 'day=none' in out
    assert 'phase=none' in out


def test_no_scene_state_returns_empty():
    body, _ = orch.render_state_footer(None, None, None, [])
    assert body == ''


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
