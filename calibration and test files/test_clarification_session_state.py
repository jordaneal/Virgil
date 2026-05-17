"""S77 — §1b.1 Clarification session state + persistence.

Tests pending_clarification DB column, set/clear/get helpers, session
lifecycle (PENDING → RESOLVED/EXPIRED/CANCELLED), per-campaign cap
enforcement, and restart-preservation via list_campaigns_with_pending.

Run: python3 test_clarification_session_state.py
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


# Use a temp DB so tests don't touch production data.
_tmpdir = tempfile.mkdtemp(prefix='clarification_test_')
_tmp_db = os.path.join(_tmpdir, 'test.db')
os.environ['DND_DB_PATH'] = _tmp_db  # not used by engine but harmless

import dnd_engine
dnd_engine.DB_PATH = type(dnd_engine.DB_PATH)(_tmp_db)
dnd_engine.db_init()

# Seed a scene_state row for campaign 1.
conn = sqlite3.connect(_tmp_db)
conn.execute("INSERT INTO dnd_scene_state (campaign_id, mode) VALUES (?, ?)",
             (1, 'exploration'))
conn.execute("INSERT INTO dnd_scene_state (campaign_id, mode) VALUES (?, ?)",
             (2, 'exploration'))
conn.commit()
conn.close()

import clarification_handshake as ch
ch._reset_for_tests()


# T1 — get_pending returns None when not set
got = ch.get_pending_clarification(1)
check('T1: no pending → None', got, None)

# T2 — set_pending writes, get_pending reads
session = ch.set_pending_clarification(
    campaign_id=1,
    candidates=[{'domain': 'transaction', 'payload': {'npc': 'Garrick'}}],
    trigger_event_id='evt-1',
)
check('T2: session created', session is not None, True)
got = ch.get_pending_clarification(1)
check('T2: pending readback', bool(got and got.get('trigger_event_id') == 'evt-1'), True)

# T3 — clear_pending resets to NULL
ok = ch.clear_pending_clarification(1)
check('T3: clear returned True', ok, True)
check('T3: pending readback after clear', ch.get_pending_clarification(1), None)

# T4 — list_campaigns_with_pending_clarification
ch.set_pending_clarification(1, [{'domain': 'transaction', 'payload': {'npc': 'G'}}], 'evt-2')
ch.set_pending_clarification(2, [{'domain': 'quest_accept', 'payload': {'title': 'X'}}], 'evt-3')
pending_list = ch.list_campaigns_with_pending_clarification()
check('T4: list returns 2 campaigns', sorted(pending_list), [1, 2])

ch.clear_pending_clarification(1)
ch.clear_pending_clarification(2)

# T5 — per-campaign session cap (PER_CAMPAIGN_SESSION_CAP = 3)
ch._reset_for_tests()
ok = []
for i in range(4):
    sess = ch.ClarificationSession(
        campaign_id=99,
        controller_id='user-1',
        trigger_event_id=f'evt-{i}',
        candidates=[{'domain': 'transaction'}],
        layer='B',
    )
    ok.append(ch.add_session(sess))
check('T5: first 3 sessions registered', ok[:3], [True, True, True])
check('T5: 4th rejected by cap', ok[3], False)

# T6 — cancel_session removes from active map
ch._reset_for_tests()
s = ch.ClarificationSession(campaign_id=100, controller_id='u', trigger_event_id='e', layer='B')
ch.add_session(s)
ch.cancel_session(s, 'EXPIRED')
check('T6: cancelled session status', s.status, 'EXPIRED')
check('T6: cancelled session removed from active',
      len(ch._active_sessions.get(100, [])), 0)


# ── Summary ──
total = PASS + FAIL
print(f"\nclarification_session_state: {PASS}/{total} passed")
if FAIL:
    print("\nFAILURES:")
    for f in FAILURES:
        print(f)
    sys.exit(1)
