"""Deterministic tests for Ship A (S36) — compute_stakes_tier.

Pure-function tests against `dnd_orchestration.compute_stakes_tier` +
`stakes_tier_log_summary`. Covers LLM_EMIT_RESOLUTION_BINDING_SPEC.md §5.

Run:
    cd /home/jordaneal/scripts && python3 test_compute_stakes_tier.py
"""

import sys
from pathlib import Path

sys.path.insert(0, '/home/jordaneal/scripts')

import dnd_orchestration as orch


def test_none_scene_returns_low():
    tier, signals = orch.compute_stakes_tier(None)
    assert tier == 'low'
    assert signals['mode'] == 'none'
    assert signals['score'] == 0


def test_empty_scene_returns_low():
    tier, signals = orch.compute_stakes_tier({})
    assert tier == 'low'


def test_combat_mode_alone_is_medium():
    # mode=combat contributes +2 → score=2 → medium
    tier, signals = orch.compute_stakes_tier({'mode': 'combat'})
    assert tier == 'medium', f"expected medium, got {tier}"
    assert signals['score'] == 2


def test_exploration_high_tension_is_medium():
    # mode=exploration +0, tension 75 ≥ 70 → +2 → score=2 → medium
    tier, signals = orch.compute_stakes_tier(
        {'mode': 'exploration', 'tension_int': 75}
    )
    assert tier == 'medium'
    assert signals['tension'] == 75


def test_combat_and_high_tension_is_high():
    # combat +2 + tension 80 ≥ 70 +2 = 4 → high
    tier, signals = orch.compute_stakes_tier(
        {'mode': 'combat', 'tension_int': 80}
    )
    assert tier == 'high'


def test_downtime_mode_is_low():
    # downtime -1 → low (negative score still buckets low)
    tier, signals = orch.compute_stakes_tier({'mode': 'downtime'})
    assert tier == 'low'
    assert signals['score'] == -1


def test_urgent_clock_alone_in_exploration_is_low():
    # exploration +0, urgent clock +1 → score=1 → low (under medium threshold)
    tier, signals = orch.compute_stakes_tier({
        'mode': 'exploration',
        'progress_clocks': [{'urgency_int': 8}],
    })
    assert tier == 'low'
    assert signals['urgent_clocks'] == 1


def test_strong_intent_grammar_fires():
    tier, signals = orch.compute_stakes_tier({
        'mode': 'combat',
        'tension_int': 50,
        'last_player_action': 'I attack the merchant',
    })
    # combat +2 + tension 50 +1 + strong_intent +1 = 4 → high
    assert tier == 'high'
    assert signals['strong_intent'] == 1


def test_log_summary_shape():
    tier = 'high'
    signals = {
        'mode': 'combat',
        'tension': 80,
        'urgent_clocks': 1,
        'strong_intent': 0,
        'combat_active': 1,
        'score': 6,
    }
    line = orch.stakes_tier_log_summary(signals, tier)
    assert line.startswith('stakes_tier: tier=high'), line
    assert 'mode=combat' in line
    assert 'tension=80' in line
    assert 'urgent_clocks=1' in line
    assert 'strong_intent=0' in line
    assert 'combat_active=1' in line
    assert 'score=6' in line


def test_unknown_mode_does_not_crash():
    # Defensive: any unknown mode string should not raise.
    tier, signals = orch.compute_stakes_tier({'mode': 'puzzling_mode'})
    assert tier == 'low'
    assert signals['mode'] == 'puzzling_mode'


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
