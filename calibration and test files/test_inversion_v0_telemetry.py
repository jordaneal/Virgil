"""S73 — Conversational-Runtime Inversion v0 telemetry primitive.

Validates the per-fire JSONL telemetry helper. §11.8 lock — always-fire
discipline (every parser invocation emits exactly one line, regardless of
fired/dedup/disabled state).

Coverage:
  T1  — emit() writes valid JSON line; ts present; event present; domain present
  T2  — multiple emits append (not truncate)
  T3  — emit_parse_outcome routed event (high confidence + engine route)
  T4  — emit_parse_outcome detected event (fired but route='silent' — rare)
  T5  — emit_parse_outcome suppressed/dedup event
  T6  — emit_parse_outcome suppressed/disabled event
  T7  — emit_parse_outcome suppressed/low_confidence event
  T8  — schema field stability: all known fields appear in payload
  T9  — soft-fail: bad path doesn't raise

Tests redirect _TELEMETRY_DIR to a temp dir so production logs aren't polluted.

Run: python3 test_inversion_v0_telemetry.py
"""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, '/home/jordaneal/scripts')

import inversion_telemetry as t

# Redirect telemetry dir to a temp location for this test.
_tmp = tempfile.mkdtemp(prefix='inv_v0_tel_test_')
t._TELEMETRY_DIR = Path(_tmp)

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


def check_truthy(label, got):
    global PASS, FAIL
    if got:
        PASS += 1
    else:
        FAIL += 1
        FAILURES.append(f"  {label}: expected truthy, got={got!r}")


def read_lines():
    p = t._today_jsonl_path()
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text().splitlines() if line.strip()]


def reset():
    t._reset_for_tests()


# ── T1: basic emit ──
reset()
ok = t.emit('detected', 'quest_accept', {'campaign_id': 42, 'confidence': 'medium'})
check('T1: emit ok', ok, True)
lines = read_lines()
check('T1: one line written', len(lines), 1)
rec = lines[0]
check_truthy('T1: ts present', 'ts' in rec)
check('T1: event',  rec.get('event'),  'detected')
check('T1: domain', rec.get('domain'), 'quest_accept')
check('T1: campaign_id', rec.get('campaign_id'), 42)
check('T1: confidence',  rec.get('confidence'),  'medium')

# ── T2: multiple emits append ──
reset()
t.emit('detected', 'quest_accept', {'campaign_id': 1})
t.emit('routed',   'quest_accept', {'campaign_id': 1})
t.emit('suppressed', 'quest_accept', {'campaign_id': 1})
lines = read_lines()
check('T2: three lines', len(lines), 3)
check('T2: order preserved 0', lines[0].get('event'), 'detected')
check('T2: order preserved 1', lines[1].get('event'), 'routed')
check('T2: order preserved 2', lines[2].get('event'), 'suppressed')

# ── T3: routed event (high + engine) ──
reset()
result = {
    'fired': True, 'confidence': 'high', 'matched_verb': 'agrees',
    'matched_quest_id': 7, 'matched_quest_title': 'Dock cargo',
    'dedup_suppressed': False, 'feature_disabled': False,
}
t.emit_parse_outcome('quest_accept', 999, result, route='engine')
rec = read_lines()[0]
check('T3: event routed',   rec.get('event'),   'routed')
check('T3: route engine',   rec.get('route'),   'engine')
check('T3: confidence high', rec.get('confidence'), 'high')
check('T3: matched_verb',   rec.get('matched_verb'), 'agrees')
check('T3: matched_quest_id', rec.get('matched_quest_id'), 7)

# ── T4: detected event (fired + silent route) ──
reset()
result = {'fired': True, 'confidence': 'medium', 'matched_verb': 'accept',
          'matched_quest_id': None, 'matched_quest_title': '',
          'dedup_suppressed': False, 'feature_disabled': False}
t.emit_parse_outcome('quest_accept', 1, result, route='silent')
rec = read_lines()[0]
check('T4: event detected', rec.get('event'), 'detected')
check('T4: route none',     rec.get('route'), None)
check('T4: fired',          rec.get('fired'), True)

# ── T5: suppressed/dedup ──
reset()
result = {'fired': False, 'confidence': 'high', 'matched_verb': 'agrees',
          'matched_quest_id': 7, 'matched_quest_title': 'Cargo',
          'dedup_suppressed': True, 'feature_disabled': False}
t.emit_parse_outcome('quest_accept', 1, result)
rec = read_lines()[0]
check('T5: event suppressed', rec.get('event'),  'suppressed')
check('T5: reason dedup',     rec.get('reason'), 'dedup')
check('T5: dedup_suppressed flag', rec.get('dedup_suppressed'), True)

# ── T6: suppressed/disabled ──
reset()
result = {'fired': False, 'confidence': 'low', 'matched_verb': '',
          'matched_quest_id': None, 'matched_quest_title': '',
          'dedup_suppressed': False, 'feature_disabled': True}
t.emit_parse_outcome('quest_accept', 1, result)
rec = read_lines()[0]
check('T6: event suppressed',     rec.get('event'),  'suppressed')
check('T6: reason feature_disabled', rec.get('reason'), 'feature_disabled')

# ── T7: suppressed/low_confidence ──
reset()
result = {'fired': False, 'confidence': 'low', 'matched_verb': '',
          'matched_quest_id': None, 'matched_quest_title': '',
          'dedup_suppressed': False, 'feature_disabled': False}
t.emit_parse_outcome('quest_accept', 1, result)
rec = read_lines()[0]
check('T7: event suppressed',     rec.get('event'),  'suppressed')
check('T7: reason low_confidence', rec.get('reason'), 'low_confidence')

# ── T8: schema field stability — every known field present in payload ──
reset()
result = {'fired': True, 'confidence': 'high', 'matched_verb': "i'll take",
          'matched_quest_id': 19, 'matched_quest_title': 'Wyrm contract',
          'dedup_suppressed': False, 'feature_disabled': False}
t.emit_parse_outcome('quest_accept', 7, result, route='engine')
rec = read_lines()[0]
required = ['ts', 'event', 'domain', 'campaign_id', 'confidence',
            'matched_verb', 'matched_quest_id', 'matched_quest_title',
            'dedup_suppressed', 'feature_disabled', 'route', 'fired']
for field in required:
    check_truthy(f'T8: field {field} present', field in rec)

# ── T9: soft-fail when path is unwritable ──
# Point to a non-existent/non-creatable path with no write perms.
saved = t._TELEMETRY_DIR
t._TELEMETRY_DIR = Path('/proc/1/no_such_path_for_telemetry')
ok = t.emit('detected', 'quest_accept', {})
check('T9: bad path returns False', ok, False)
t._TELEMETRY_DIR = saved

# ── Summary ──
print(f"\n{'=' * 60}")
print(f"PASS={PASS}  FAIL={FAIL}")
if FAIL:
    print("\nFailures:")
    for f in FAILURES:
        print(f)
    sys.exit(1)
print("ALL GREEN")
sys.exit(0)
