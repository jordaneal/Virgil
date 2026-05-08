"""S22 — RollBuffer._sweep() TTL-expiration logging.

Verifies that _sweep() emits unconsumed_roll_swept: log lines for every
event that ages past EVENT_TTL_SECONDS without being consumed, and that
consumed events (removed by consume() before TTL expires) produce no log.

Pure visibility — no behavior change. _sweep() still deletes the expired
events; the log is the new addition.

Tests:
  1. happy-path consumption: event consumed within TTL → no log on sweep
  2. TTL expiration of unmatched event: old ts → one log line, correct format
  3. 'Someone' actor case: actor='Someone' appears correctly in the log
  4. expired-and-consumed: consume() clears event before TTL artifice → no log

Run: python3 test_avrae_sweep.py
"""

import sys
import time

sys.path.insert(0, '/home/jordaneal/scripts')

import avrae_listener

# ── Capture harness ──

captured = []
avrae_listener.log = lambda m: captured.append(m)

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


def check_falsy(label, got):
    global PASS, FAIL
    if not got:
        PASS += 1
    else:
        FAIL += 1
        FAILURES.append(f"  {label}: expected falsy, got={got!r}")


# ──────────────────────────────────────────────────────────────────────────────
# Test 1: Happy-path consumption — no log fires
#
# An event consumed (via consume()) while still within TTL is removed from
# the buffer. A subsequent _sweep() with an artificially short TTL sees an
# empty bucket and has nothing to log. This is the intended hot path: every
# consumed roll should be invisible to sweep.
# ──────────────────────────────────────────────────────────────────────────────

captured.clear()
buf1 = avrae_listener.RollBuffer(ttl_seconds=300, max_per_guild=50)
buf1.add({'guild_id': 10, 'actor': 'donovan ruby', 'kind': 'attack',
          'detail': 'shortsword', 'result': 15, 'nat': 11, 'damage': 6,
          'crit': False, 'channel_id': 1, 'ts': time.time()})
buf1.consume(10, ['donovan ruby'])   # removes event; _sweep inside sees it fresh
buf1._ttl = 0                        # force: any remaining event would be expired
buf1.recent(10)                      # triggers _sweep on now-empty bucket

check('happy_path: no log fires after consume', len(captured), 0)


# ──────────────────────────────────────────────────────────────────────────────
# Test 2: TTL expiration of an unmatched event — one log line, correct format
#
# Add an event with a timestamp 200s in the past. The default TTL is 75s, so
# this event is well past expiry. Calling recent() triggers _sweep(), which
# should log exactly one unconsumed_roll_swept line and then drop the event.
# ──────────────────────────────────────────────────────────────────────────────

captured.clear()
buf2 = avrae_listener.RollBuffer(ttl_seconds=75, max_per_guild=50)
old_ts = time.time() - 200   # 200s old, past 75s TTL
buf2.add({'guild_id': 20, 'actor': 'Aldric', 'kind': 'check',
          'detail': 'perception', 'result': 14, 'nat': 9, 'damage': None,
          'crit': False, 'channel_id': 1, 'ts': old_ts})
buf2.recent(20, ['Aldric'])  # triggers _sweep

check('ttl_expiry: exactly one log line', len(captured), 1)
check_truthy('ttl_expiry: keyword present',    'unconsumed_roll_swept' in captured[0])
check_truthy('ttl_expiry: actor in log',       "actor='Aldric'" in captured[0])
check_truthy('ttl_expiry: action in log',      "action='check'" in captured[0])
check_truthy('ttl_expiry: age_s key present',  'age_s=' in captured[0])

# Event must be gone after sweep
check('ttl_expiry: event removed from buffer', len(buf2.recent(20)), 0)


# ──────────────────────────────────────────────────────────────────────────────
# Test 3: 'Someone' actor case
#
# When Avrae embed parsing can't identify the actor, _extract_actor returns
# 'Someone'. This event should log with actor='Someone' — not an empty string,
# not dropped silently.
# ──────────────────────────────────────────────────────────────────────────────

captured.clear()
buf3 = avrae_listener.RollBuffer(ttl_seconds=75, max_per_guild=50)
old_ts = time.time() - 200
buf3.add({'guild_id': 30, 'actor': 'Someone', 'kind': 'roll',
          'detail': '', 'result': 12, 'nat': 12, 'damage': None,
          'crit': False, 'channel_id': 1, 'ts': old_ts})
buf3._sweep(30)

check('someone_actor: one log fires',         len(captured), 1)
check_truthy('someone_actor: actor=Someone',  "actor='Someone'" in captured[0])
check_truthy('someone_actor: action=roll',    "action='roll'" in captured[0])


# ──────────────────────────────────────────────────────────────────────────────
# Test 4: Expired-and-consumed — no log because consumed before sweep
#
# Event is consumed within its TTL. We then shrink the TTL to 0 so that ANY
# remaining event would be "expired". _sweep() on the now-empty bucket emits
# nothing — the consume() already removed the event before it could age out.
# ──────────────────────────────────────────────────────────────────────────────

captured.clear()
buf4 = avrae_listener.RollBuffer(ttl_seconds=300, max_per_guild=50)
buf4.add({'guild_id': 40, 'actor': 'Throx', 'kind': 'save',
          'detail': 'dexterity', 'result': 18, 'nat': 17, 'damage': None,
          'crit': False, 'channel_id': 1, 'ts': time.time()})
buf4.consume(40, ['throx'])  # removes the event; no log fires here (event fresh)
buf4._ttl = 0                # if anything remained it would expire immediately
buf4._sweep(40)              # bucket is empty — nothing to log

check('expired_and_consumed: no log fires', len(captured), 0)


# ──────────────────────────────────────────────────────────────────────────────
# Results
# ──────────────────────────────────────────────────────────────────────────────

print(f"\n{PASS} passed, {FAIL} failed")
if FAILURES:
    print("\nFAILURES:")
    for f in FAILURES:
        print(f)
    sys.exit(1)
sys.exit(0)
