"""S77 — §1b.1 M-DELAYED in-fiction primary path.

Tests the engine-side machinery for M-DELAYED:
  - set/get/clear pending_clarification round-trip through dnd_scene_state
  - compute_pending_clarification_directive renders MUST/MUST-NOT block
    when pending state is present
  - build_dm_context's prompt assembly includes the directive block when
    pending_clarification_directive kwarg is non-empty (placement check)

Run: python3 test_clarification_in_fiction.py
"""
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, '/home/jordaneal/scripts')


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


def check_not_in(label, haystack, needle):
    global PASS, FAIL
    if needle not in haystack:
        PASS += 1
    else:
        FAIL += 1
        FAILURES.append(f"  {label}: {needle!r} unexpectedly in {haystack!r}")


# Sandbox DB
_tmpdir = tempfile.mkdtemp(prefix='clarification_inf_')
_tmp_db = os.path.join(_tmpdir, 'test.db')

import dnd_engine
dnd_engine.DB_PATH = type(dnd_engine.DB_PATH)(_tmp_db)
dnd_engine.db_init()

conn = sqlite3.connect(_tmp_db)
conn.execute("INSERT INTO dnd_scene_state (campaign_id, mode) VALUES (?, ?)",
             (1, 'exploration'))
conn.commit()
conn.close()

import clarification_handshake as ch
import dnd_orchestration as orch
ch._reset_for_tests()


# T1 — set + read round-trip
ch.set_pending_clarification(
    campaign_id=1,
    candidates=[
        {'domain': 'transaction',
         'payload': {'npc': 'Garrick', 'currency': '5 gold'}}
    ],
    trigger_event_id='trig-1',
)
meta = ch.get_pending_clarification(1)
check('T1: meta read', bool(meta), True)
check('T1: trigger_event_id', meta['trigger_event_id'], 'trig-1')
check('T1: candidate count', len(meta['candidates']), 1)

# T2 — directive composer fires on pending state
body, signals = orch.compute_pending_clarification_directive(meta)
check('T2: directive fired', signals['fired'], True)
check_in('T2: marker summary in body', body, '5 gold')
check_in('T2: MUST NOT framing', body, 'MUST NOT')

# T3 — clear → directive composer no-fires
ch.clear_pending_clarification(1)
meta2 = ch.get_pending_clarification(1)
check('T3: cleared meta', meta2, None)
body2, signals2 = orch.compute_pending_clarification_directive(meta2)
check('T3: post-clear no-fire', signals2['fired'], False)
check('T3: post-clear empty body', body2, '')

# T4 — build_dm_context includes pending block when directive present
ch.set_pending_clarification(
    campaign_id=1,
    candidates=[
        {'domain': 'transaction',
         'payload': {'npc': 'Garrick', 'currency': '5 gold'}}
    ],
    trigger_event_id='trig-2',
)
meta = ch.get_pending_clarification(1)
body, _ = orch.compute_pending_clarification_directive(meta)

camp = {'id': 1, 'name': 'Test', 'tone': '', 'premise': ''}
scene = {
    'mode': 'exploration', 'location_label': 'Inn',
    'last_player_action': 'I hand 5 gold to Garrick',
    'tension_int': 0, 'campaign_day': 1, 'day_phase': 'Morning',
    'progress_clocks': [],
}
prompt = dnd_engine.build_dm_context(
    campaign=camp, characters=[],
    pending_clarification_directive=body,
    scene_state=scene,
)
check_in('T4: PENDING CLARIFICATION block in prompt',
         prompt, '=== PENDING CLARIFICATION ===')
check_in('T4: directive body in prompt', prompt, 'MUST NOT')

# T5 — build_dm_context excludes pending block when directive empty
prompt2 = dnd_engine.build_dm_context(
    campaign=camp, characters=[],
    pending_clarification_directive='',
    scene_state=scene,
)
check_not_in('T5: no PENDING block when empty', prompt2,
             '=== PENDING CLARIFICATION ===')

# T6 — combat-narration suppression
prompt3 = dnd_engine.build_dm_context(
    campaign=camp, characters=[],
    pending_clarification_directive=body,
    scene_state=scene,
    suppress_for_combat_narration=True,
)
check_not_in('T6: suppressed under combat narration', prompt3,
             '=== PENDING CLARIFICATION ===')


# ── Summary ──
total = PASS + FAIL
print(f"\nclarification_in_fiction: {PASS}/{total} passed")
if FAIL:
    print("\nFAILURES:")
    for f in FAILURES:
        print(f)
    sys.exit(1)
