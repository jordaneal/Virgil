"""S81 — §82 candidate generic directive_compliance_failure telemetry.

Tests:
  - record_directive_compliance_failure emits with stable shape
  - Payload caps (narration_excerpt → 200; directive_intent → 100)
  - Grep surface: directive_name disambiguates per-directive grep without
    schema coupling
  - Invalid severity defaults to MEDIUM

Run: python3 test_directive_compliance_failure_telemetry.py
"""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, '/home/jordaneal/scripts')

import inversion_telemetry as t

PASS = 0
FAIL = 0
FAILURES = []


def check(label, got, want):
    global PASS, FAIL
    if got == want:
        PASS += 1
    else:
        FAIL += 1
        FAILURES.append(f"  {label}: got={got!r} want={want!r}")


def check_in(label, haystack, needle):
    global PASS, FAIL
    if needle in haystack:
        PASS += 1
    else:
        FAIL += 1
        FAILURES.append(f"  {label}: {needle!r} not in {haystack!r}")


# Sandbox telemetry
_tmpdir = tempfile.mkdtemp(prefix='compliance_tel_')
t._TELEMETRY_DIR = Path(_tmpdir)


def _read_today_lines():
    p = t._today_jsonl_path()
    if not p.exists():
        return []
    with open(p, encoding='utf-8') as f:
        return [json.loads(line) for line in f if line.strip()]


# T1 — emit with full payload
t._reset_for_tests()
ok = t.record_directive_compliance_failure(
    directive_name='central_thread',
    severity='HIGH',
    narration_excerpt='The baker mentions the recent mine collapse',
    detector='post_llm_token_overlap',
    campaign_id=42,
    confidence=0.87,
    directive_intent='Do NOT name or restate the thread in narration',
)
check('T1: emit returned True', ok, True)
lines = _read_today_lines()
check('T1: one line written', len(lines), 1)
check('T1: event name', lines[0]['event'], 'directive_compliance_failure')
check('T1: domain', lines[0]['domain'], 'inversion')
check('T1: directive_name', lines[0]['directive_name'], 'central_thread')
check('T1: severity', lines[0]['severity'], 'HIGH')
check('T1: campaign_id', lines[0]['campaign_id'], 42)
check('T1: confidence', lines[0]['confidence'], 0.87)
check_in('T1: detector', lines[0]['detector'], 'post_llm_token_overlap')
check_in('T1: directive_intent', lines[0]['directive_intent'], 'Do NOT')

# T2 — narration_excerpt capped at 200 chars
t._reset_for_tests()
long_text = 'X' * 500
t.record_directive_compliance_failure(
    directive_name='pending_clarification', severity='MEDIUM',
    narration_excerpt=long_text, detector='test', campaign_id=1,
    confidence=0.5, directive_intent='test intent',
)
lines = _read_today_lines()
check('T2: narration_excerpt capped at 200', len(lines[0]['narration_excerpt']), 200)

# T3 — directive_intent capped at 100 chars
t._reset_for_tests()
long_intent = 'Y' * 300
t.record_directive_compliance_failure(
    directive_name='central_thread', severity='LOW',
    narration_excerpt='short', detector='test', campaign_id=1,
    confidence=0.3, directive_intent=long_intent,
)
lines = _read_today_lines()
check('T3: directive_intent capped at 100', len(lines[0]['directive_intent']), 100)

# T4 — invalid severity defaults to MEDIUM
t._reset_for_tests()
t.record_directive_compliance_failure(
    directive_name='central_thread', severity='OOPS',
    narration_excerpt='x', detector='t', campaign_id=1,
    confidence=0.5, directive_intent='y',
)
lines = _read_today_lines()
check('T4: invalid severity → MEDIUM', lines[0]['severity'], 'MEDIUM')

# T5 — grep-surface check (per-directive disambiguation)
t._reset_for_tests()
t.record_directive_compliance_failure(
    directive_name='central_thread', severity='MEDIUM',
    narration_excerpt='thread bleed', detector='t', campaign_id=1,
    confidence=0.5, directive_intent='i',
)
t.record_directive_compliance_failure(
    directive_name='pending_clarification', severity='HIGH',
    narration_excerpt='action narrated', detector='t', campaign_id=1,
    confidence=0.9, directive_intent='i',
)
t.record_directive_compliance_failure(
    directive_name='central_thread', severity='LOW',
    narration_excerpt='minor overlap', detector='t', campaign_id=1,
    confidence=0.3, directive_intent='i',
)
lines = _read_today_lines()
check('T5: 3 events written', len(lines), 3)
central = [l for l in lines if l['directive_name'] == 'central_thread']
pending = [l for l in lines if l['directive_name'] == 'pending_clarification']
check('T5: grep central_thread → 2', len(central), 2)
check('T5: grep pending_clarification → 1', len(pending), 1)


# ── Summary ──
total = PASS + FAIL
print(f"\ndirective_compliance_failure_telemetry: {PASS}/{total} passed")
if FAIL:
    print("\nFAILURES:")
    for f in FAILURES:
        print(f)
    sys.exit(1)
