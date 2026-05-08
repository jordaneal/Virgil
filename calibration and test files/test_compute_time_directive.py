"""Pure-function tests for compute_time_directive
(Track 4 #3, Session 27).

Per TRACK_4_3_SPEC.md §9 + Appendix B. Pure function in dnd_orchestration;
no DB, no LLM. Caller resolves just_advanced via engine.time_just_advanced.

Run:
    cd /home/jordaneal/scripts && python3 test_compute_time_directive.py
"""

import sys

sys.path.insert(0, '/home/jordaneal/scripts')

import dnd_orchestration as orch


def _scene(day=3, phase='Evening'):
    return {'campaign_day': day, 'day_phase': phase, 'mode': 'exploration'}


def test_silent_when_not_just_advanced():
    assert orch.compute_time_directive(_scene(), False) == ''


def test_fires_when_just_advanced():
    body = orch.compute_time_directive(_scene(), True)
    assert body
    assert 'Day 3' in body or 'campaign_day=3' in body


def test_includes_day_and_phase():
    body = orch.compute_time_directive(_scene(day=5, phase='Morning'), True)
    assert 'campaign_day=5' in body
    assert 'day_phase=Morning' in body


def test_no_TIME_ADVANCE_keyword_bleed():
    """The leading marker is added by build_dm_context (=== TIME ADVANCE ===),
    not by the directive itself — verify the directive body doesn't carry
    its own TIME_ADVANCE: literal that would compete with the framing."""
    body = orch.compute_time_directive(_scene(), True)
    assert 'TIME_ADVANCE:' not in body


def test_silent_on_none_scene_state():
    assert orch.compute_time_directive(None, True) == ''


def test_silent_on_missing_day():
    assert orch.compute_time_directive({'day_phase': 'Morning'}, True) == ''


def test_silent_on_missing_phase():
    assert orch.compute_time_directive({'campaign_day': 1}, True) == ''


def test_directive_contains_one_beat_instruction():
    body = orch.compute_time_directive(_scene(), True)
    assert 'one in-fiction beat' in body


def test_directive_forbids_intervening_hours():
    body = orch.compute_time_directive(_scene(), True)
    assert 'intervening hours' in body


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
