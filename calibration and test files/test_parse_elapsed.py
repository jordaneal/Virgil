"""Pure-function tests for parse_elapsed (Track 4 #3, Session 27).

Per TRACK_4_3_SPEC.md §9 + Appendix A. Deterministic; no DB; no LLM.

Run:
    cd /home/jordaneal/scripts && python3 test_parse_elapsed.py
"""

import sys

sys.path.insert(0, '/home/jordaneal/scripts')

from dnd_engine import parse_elapsed


def test_a_day():
    assert parse_elapsed('a day') == (1, 0)


def test_one_day():
    assert parse_elapsed('one day') == (1, 0)


def test_numeric_one_day():
    assert parse_elapsed('1 day') == (1, 0)


def test_three_days():
    assert parse_elapsed('three days') == (3, 0)


def test_two_days():
    assert parse_elapsed('two days') == (2, 0)


def test_numeric_two_days():
    assert parse_elapsed('2 days') == (2, 0)


def test_an_hour():
    assert parse_elapsed('an hour') == (0, 1)


def test_one_hour():
    assert parse_elapsed('one hour') == (0, 1)


def test_a_few_hours():
    assert parse_elapsed('a few hours') == (0, 1)


def test_a_couple_hours():
    assert parse_elapsed('a couple hours') == (0, 1)


def test_overnight():
    assert parse_elapsed('overnight') == (1, 0)


def test_two_weeks():
    assert parse_elapsed('two weeks') == (14, 0)


def test_one_week():
    assert parse_elapsed('a week') == (7, 0)


def test_six_hours_one_phase():
    assert parse_elapsed('six hours') == (0, 1)


def test_seven_hours_two_phases():
    # 7 hours == 1 full phase + 1 over → ceil to 2 phases.
    assert parse_elapsed('seven hours') == (0, 2)


def test_twelve_hours_two_phases():
    assert parse_elapsed('twelve hours') == (0, 2)


def test_24_hours_one_day():
    assert parse_elapsed('24 hours') == (1, 0)


def test_unparseable():
    assert parse_elapsed('xyzzy') is None


def test_empty():
    assert parse_elapsed('') is None


def test_none_input():
    assert parse_elapsed(None) is None


def test_minutes_below_floor():
    assert parse_elapsed('five minutes') == (0, 0)


def test_a_moment():
    assert parse_elapsed('a moment') == (0, 0)


def test_about_two_days_hedge_strip():
    assert parse_elapsed('about two days') == (2, 0)


def test_roughly_an_hour():
    assert parse_elapsed('roughly an hour') == (0, 1)


def test_case_insensitive():
    assert parse_elapsed('A DAY') == (1, 0)


def test_whitespace_strip():
    assert parse_elapsed('  three days  ') == (3, 0)


def test_negative_numeric_returns_none():
    # The regex doesn't match a leading '-', so '-1 days' is not parsed.
    assert parse_elapsed('-1 days') is None


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
