"""S77 — §1b.1 telemetry extension (clarification event taxonomy + calibration).

Tests:
  - emit_clarification_event writes JSONL with stable shape
  - record_parser_invocation increments counters
  - parser_calibration_snapshot fires every N invocations
  - Event names match the documented taxonomy

Run: python3 test_clarification_telemetry.py
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


# Sandbox telemetry into temp dir
_tmpdir = tempfile.mkdtemp(prefix='clarification_tel_')
t._TELEMETRY_DIR = Path(_tmpdir)


def _read_today_lines():
    p = t._today_jsonl_path()
    if not p.exists():
        return []
    with open(p, encoding='utf-8') as f:
        return [json.loads(line) for line in f if line.strip()]


# T1 — emit_clarification_event writes shape
t._reset_for_tests()
t.emit_clarification_event('clarification_in_fiction_fired',
                             campaign_id=42,
                             payload={'parser_domains': ['transaction']})
lines = _read_today_lines()
check('T1: one line written', len(lines), 1)
check('T1: event name', lines[0]['event'], 'clarification_in_fiction_fired')
check('T1: domain stable', lines[0]['domain'], 'clarification')
check('T1: campaign_id', lines[0]['campaign_id'], 42)
check('T1: payload domains',
      lines[0].get('parser_domains'), ['transaction'])

# T2 — distinct event types co-emit
t.emit_clarification_event('clarification_in_fiction_resolved', 42,
                             {'parser_domains': ['transaction']})
t.emit_clarification_event('clarification_skipped', 42, {})
t.emit_clarification_event('clarification_layer_a_fired', 42,
                             {'parser_domains': ['t', 'q']})
lines = _read_today_lines()
events = [l['event'] for l in lines]
check('T2: contains in_fiction_resolved',
      'clarification_in_fiction_resolved' in events, True)
check('T2: contains skipped',
      'clarification_skipped' in events, True)
check('T2: contains layer_a_fired',
      'clarification_layer_a_fired' in events, True)

# T3 — calibration snapshot fires every N invocations
t._reset_for_tests()
t._reset_calibration_for_tests()
t._CALIBRATION_SNAPSHOT_INTERVAL = 5
for _ in range(5):
    t.record_parser_invocation('quest_accept', 'medium')
lines = _read_today_lines()
snapshots = [l for l in lines if l.get('event') == 'parser_calibration_snapshot']
check('T3: snapshot fired at N=5', len(snapshots), 1)
check('T3: snapshot domain', snapshots[0]['domain'], 'inversion')
check('T3: invocations counted', snapshots[0]['invocations'], 5)

# T4 — record_parser_invocation accumulates per-confidence
t._reset_calibration_for_tests()
t._CALIBRATION_SNAPSHOT_INTERVAL = 10
t.record_parser_invocation('quest_accept', 'high')
t.record_parser_invocation('quest_accept', 'high')
t.record_parser_invocation('quest_accept', 'low')
counts = t._PARSER_CONFIDENCE_COUNTS.get('quest_accept', {})
check('T4: 2 highs counted', counts.get('high'), 2)
check('T4: 1 low counted', counts.get('low'), 1)


# ── Summary ──
total = PASS + FAIL
print(f"\nclarification_telemetry: {PASS}/{total} passed")
if FAIL:
    print("\nFAILURES:")
    for f in FAILURES:
        print(f)
    sys.exit(1)
