"""S77 — §1b.1 compute_pending_clarification_directive (§59 sibling).

Tests the 24th §59 sibling directive composer per WWC sibling pattern:
  - Empty metadata → empty string, signals.fired=False
  - Pending metadata → MUST/MUST-NOT block, signals.fired=True
  - Marker summary renders into directive body
  - Always-fire signals dict for telemetry log_summary

Run: python3 test_pending_clarification_directive.py
"""
import sys
sys.path.insert(0, '/home/jordaneal/scripts')

import dnd_orchestration as orch

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


# T1 — None metadata → empty + fired=False
body, signals = orch.compute_pending_clarification_directive(None)
check('T1: empty body', body, '')
check('T1: fired False', signals['fired'], False)
check('T1: reason no_pending', signals['reason'], 'no_pending')

# T2 — empty dict
body, signals = orch.compute_pending_clarification_directive({})
check('T2: empty body', body, '')
check('T2: fired False', signals['fired'], False)

# T3 — pending with empty candidates
body, signals = orch.compute_pending_clarification_directive({'candidates': []})
check('T3: empty candidates body', body, '')
check('T3: reason empty_candidates', signals['reason'], 'empty_candidates')

# T4 — pending with one candidate
meta = {
    'candidates': [
        {'domain': 'transaction',
         'payload': {'npc': 'Garrick', 'currency': '5 gold'}},
    ],
}
body, signals = orch.compute_pending_clarification_directive(meta)
check('T4: fired True', signals['fired'], True)
check('T4: candidate_count', signals['candidate_count'], 1)
check_in('T4: MUST NOT framing', body, 'MUST NOT')
check_in('T4: MUST framing', body, 'MUST: narrate')
check_in('T4: examples header', body, 'Examples')
check_in('T4: marker summary', body, '5 gold')
check_in('T4: NPC in summary', body, 'Garrick')

# T5 — pending with multi-element marker summary
meta = {
    'candidates': [
        {'domain': 'transaction',
         'payload': {'npc': 'Garrick', 'currency': '5 gold', 'item': 'bread'}},
    ],
}
body, signals = orch.compute_pending_clarification_directive(meta)
check_in('T5: all markers in summary', body, 'and')

# T6 — log_summary always-fire shape
sig = {'fired': True, 'candidate_count': 1, 'reason': 'pending'}
out = orch.pending_clarification_log_summary(sig)
check_in('T6: log summary fired', out, 'fired=1')
check_in('T6: log summary candidates', out, 'candidates=1')


# ── Summary ──
total = PASS + FAIL
print(f"\npending_clarification_directive: {PASS}/{total} passed")
if FAIL:
    print("\nFAILURES:")
    for f in FAILURES:
        print(f)
    sys.exit(1)
