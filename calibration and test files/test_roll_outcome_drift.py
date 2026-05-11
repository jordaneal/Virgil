"""Deterministic tests for Ship 1 (S34) — ROLL_OUTCOME_DRIFT verifier class.

Covers RESOLUTION_BINDING_SPEC.md §12.2:
  - fires on success-on-failure phrasing + passed=False
  - fires on failure-on-success phrasing + passed=True
  - no-op when resolution_result is None
  - passes when phrasing aligns with passed flag
  - VERDICT_CONTRADICTION fires first when both classes would (priority §8.4)
  - detection-order placement (after STATE_MUTATION, before ACTOR_OMISSION)
  - retry_constraint includes actor/skill/kind/DC/roll_total/outcome
  - build_verification_retry_prefix produces non-empty prefix
  - build_escalation_placeholder emits deterministic ROLL_OUTCOME_DRIFT block
  - empty narration passes (fail-open envelope)
  - VERIFICATION_ENABLED=False short-circuits to passed

Pure-function tests — no DB, no Discord, no LLM.

Run:
    cd /home/jordaneal/scripts && python3 test_roll_outcome_drift.py
"""

import sys
from pathlib import Path

sys.path.insert(0, '/home/jordaneal/scripts')

import narration_verifier as nv
from dnd_orchestration import ResolutionResult


def _rr(passed: bool, actor='Donovan Ruby', skill='perception',
        dc=10, roll_total=14, kind='check'):
    return ResolutionResult(
        actor=actor, check_kind=kind, skill_or_save=skill,
        dc=dc, roll_total=roll_total, passed=passed,
        rolled_at=1.0, directive_id=22,
    )


# ─── ROLL_OUTCOME_DRIFT detection ───────────────────────────────────

def test_drift_fires_on_success_phrase_with_failed_resolution():
    # "you succeed" matches _CHECK_FAILURE_SUCCESS_PHRASES (vocab reuse §11.12)
    res = nv.verify_narration(
        narration_text="You succeed with practiced ease.",
        arbitration_result=None,
        resolution_result=_rr(passed=False, roll_total=6, dc=10),
    )
    assert res.passed is False, f"expected fail, got {res.signals}"
    assert res.violation_class == nv.VIOLATION_ROLL_OUTCOME_DRIFT, \
        f"unexpected class: {res.violation_class}"


def test_drift_fires_on_failure_phrase_with_passed_resolution():
    # "you fail" matches _CHECK_SUCCESS_FAILURE_PHRASES
    res = nv.verify_narration(
        narration_text="You fail to find anything in the dust.",
        arbitration_result=None,
        resolution_result=_rr(passed=True, roll_total=18, dc=10),
    )
    assert res.passed is False, f"expected fail, got {res.signals}"
    assert res.violation_class == nv.VIOLATION_ROLL_OUTCOME_DRIFT, \
        f"unexpected class: {res.violation_class}"


def test_drift_is_noop_when_resolution_result_is_none():
    res = nv.verify_narration(
        narration_text="Donovan Ruby succeeds with practiced ease.",
        arbitration_result=None,
        resolution_result=None,
    )
    # No arbitration, no resolution — passes (no binding to drift against).
    assert res.passed is True


def test_drift_passes_when_phrasing_aligns_with_failed():
    # Failure phrasing on passed=False resolution should NOT trigger drift
    # (the binding outcome is failure; "you fail" honors that).
    res = nv.verify_narration(
        narration_text="You fail to spot the trapdoor.",
        arbitration_result=None,
        resolution_result=_rr(passed=False, roll_total=6, dc=10),
    )
    assert res.passed is True, f"unexpected violation: {res.violation_class}"


# ─── Detection priority / order ─────────────────────────────────────

def test_verdict_contradiction_fires_first_when_both_classes_apply():
    # Build an arbitration_result with a CHECK verdict for which the narration
    # describes success-on-failure. Even if resolution_result would also
    # detect drift, VERDICT_CONTRADICTION sits in slot 2 (before
    # ROLL_OUTCOME_DRIFT in slot 4) so the verdict-contradiction class wins.
    from types import SimpleNamespace
    verdict = SimpleNamespace(
        category='check', allowed=True, success=False,
        refusal_kind='', skill='perception', dc=10,
    )
    ar = SimpleNamespace(
        verdicts=[verdict],
        actor_order=['Donovan Ruby'],
        primary_actor='Donovan Ruby',
    )
    res = nv.verify_narration(
        narration_text="You succeed and spot the trap immediately.",
        arbitration_result=ar,
        resolution_result=_rr(passed=False, roll_total=6, dc=10),
    )
    assert res.passed is False
    assert res.violation_class == nv.VIOLATION_VERDICT_CONTRADICTION, \
        f"priority breach: {res.violation_class}"


def test_drift_class_constant_exists():
    # §8.1 — class constant must be exported for log enum.
    assert nv.VIOLATION_ROLL_OUTCOME_DRIFT == 'roll_outcome_drift'


# ─── Retry constraint shape ─────────────────────────────────────────

def test_retry_constraint_includes_resolution_fields():
    r = _rr(passed=False, actor='Donovan Ruby', skill='perception',
            dc=10, roll_total=6, kind='check')
    text = nv._retry_constraint_roll_outcome_drift("you succeed", r)
    assert nv.VIOLATION_ROLL_OUTCOME_DRIFT in text
    assert 'Donovan Ruby' in text
    assert 'perception' in text
    assert 'check' in text
    assert 'DC 10' in text
    assert 'rolled 6' in text
    assert 'FAILED' in text
    # Spec §8.6 — explicit "player's self-report is irrelevant" sentence.
    assert "self-report is irrelevant" in text


def test_retry_prefix_non_empty_for_drift_result():
    res = nv.verify_narration(
        narration_text="You succeed brilliantly.",
        arbitration_result=None,
        resolution_result=_rr(passed=False, roll_total=6, dc=10),
    )
    assert not res.passed
    prefix = nv.build_verification_retry_prefix(res)
    assert prefix.strip(), "expected non-empty retry prefix"
    assert '=== VERIFICATION FAILED ===' in prefix


# ─── Escalation placeholder ─────────────────────────────────────────

def test_escalation_placeholder_renders_resolution_block():
    r = _rr(passed=False, actor='Donovan Ruby', skill='perception',
            dc=10, roll_total=6, kind='check')
    text = nv.build_escalation_placeholder(
        arbitration_result=None,
        failed_violation_class=nv.VIOLATION_ROLL_OUTCOME_DRIFT,
        resolution_result=r,
    )
    assert 'Donovan Ruby' in text
    assert 'Perception check at DC 10' in text
    assert 'rolled 6' in text
    assert 'Failure' in text
    assert 'The attempt fails' in text


# ─── Soft-fail envelope ─────────────────────────────────────────────

def test_empty_narration_passes():
    res = nv.verify_narration(
        narration_text="",
        arbitration_result=None,
        resolution_result=_rr(passed=False),
    )
    assert res.passed is True


def test_disabled_flag_returns_passed():
    saved = nv.VERIFICATION_ENABLED
    try:
        nv.VERIFICATION_ENABLED = False
        res = nv.verify_narration(
            narration_text="You succeed brilliantly.",
            arbitration_result=None,
            resolution_result=_rr(passed=False),
        )
        assert res.passed is True
    finally:
        nv.VERIFICATION_ENABLED = saved


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
