"""S81 — central_thread compliance detector tests.

Smoke-tests detect_central_thread_compliance_failure deterministic
token-overlap detector:
  - Empty inputs return False
  - Clean narration (no overlap) returns False
  - Substantial overlap (≥40%) returns HIGH severity
  - Notable overlap (20-40%) returns MEDIUM
  - Incidental overlap (<20%) returns LOW (not flagged as violation)
  - Stopwords + short tokens filtered

Run: python3 test_central_thread_compliance_detector.py
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


# T1 — empty inputs
v, c, s = orch.detect_central_thread_compliance_failure('', 'narration text')
check('T1a: empty thread → no violation', v, False)
check('T1b: empty thread → confidence 0', c, 0.0)
check('T1c: empty thread → LOW', s, 'LOW')

v, c, s = orch.detect_central_thread_compliance_failure('thread text', '')
check('T1d: empty narration → no violation', v, False)

# T2 — clean narration (no content-token overlap)
thread = orch.compute_central_thread_directive(['ancient dragon stirs beneath stone'])
clean = 'The bartender pours another mug of ale and grumbles about the weather.'
v, c, s = orch.detect_central_thread_compliance_failure(thread, clean)
check('T2: clean narration → no violation', v, False)
check('T2: severity LOW on no overlap', s, 'LOW')

# T3 — HIGH violation (substantial token overlap with thread)
thread = orch.compute_central_thread_directive(
    ['ancient dragon stirs beneath crystal stone vault'],
)
# Overlap 4/5 = 80% — way above HIGH threshold (0.40)
violation_narration = (
    'The baker mutters about the ancient dragon rumored to stir '
    'beneath the crystal vault, sensing the stone tremble.'
)
v, c, s = orch.detect_central_thread_compliance_failure(thread, violation_narration)
check('T3: HIGH violation flagged', v, True)
check('T3: severity HIGH', s, 'HIGH')

# T4 — MEDIUM violation (notable overlap 20-40%)
thread = orch.compute_central_thread_directive(
    ['shadowy cult plots assassination beneath ancient temple grounds'],
)
# Want overlap of ~20-40%. Thread content tokens after filter (≥4 chars, not stopword):
# shadowy, cult, plots, assassination, beneath, ancient, temple, grounds = 8 tokens
# 2-3 overlap should land MEDIUM
medium_narration = (
    'The merchant mentions the cult rumored to be active in the temple district.'
)
v, c, s = orch.detect_central_thread_compliance_failure(thread, medium_narration)
check('T4: MEDIUM violation flagged', v, True)
check('T4: severity MEDIUM', s, 'MEDIUM')

# T5 — LOW (incidental overlap < 20%, not flagged as violation)
thread = orch.compute_central_thread_directive(
    ['ancient dragon stirs beneath crystal stone vault deep below city streets'],
)
# Thread tokens after filter: ancient, dragon, stirs, beneath, crystal, stone,
#   vault, deep, below, city, streets = 11 tokens
# 1 overlap = ~9% — under MEDIUM threshold
low_narration = (
    'A bird wheels overhead as the merchant tallies the deep ledger of receipts.'
)
v, c, s = orch.detect_central_thread_compliance_failure(thread, low_narration)
check('T5: LOW overlap → not flagged', v, False)
check('T5: severity LOW', s, 'LOW')

# T6 — stopwords + short tokens don't inflate detection
thread = orch.compute_central_thread_directive(
    ['the and of a to in for on with the and of'],
)
narration = 'the and of a to in for on with'
v, c, s = orch.detect_central_thread_compliance_failure(thread, narration)
check('T6: stopwords-only thread → not flagged', v, False)
check('T6: severity LOW (no content tokens)', s, 'LOW')

# T7 — content-tokens helper exposes the filter
tokens = orch._content_tokens('The ancient dragon stirs beneath stone')
check('T7: content tokens filter (stopwords + <4 chars)',
      tokens, {'ancient', 'dragon', 'stirs', 'beneath', 'stone'})


# ── Summary ──
total = PASS + FAIL
print(f"\ncentral_thread_compliance_detector: {PASS}/{total} passed")
if FAIL:
    print("\nFAILURES:")
    for f in FAILURES:
        print(f)
    sys.exit(1)
