"""S66 Fix 1 — /travel duration → phase_delta translator adversarial verify.

Tests the deterministic time-advancement layer for /travel. Pre-S66 the
parser already returned (0,1) for '1 hour' inputs but the call site
skipped the advance_time call when parsed was None or (0,0) — so
'banana', '', and '5 minutes' produced ZERO phase advancement. Per S66
plan §Fix 1B, any /travel call must advance at least one phase.

Tests verify:
  (1) parse_elapsed canonical cases unchanged
  (2) Floor-at-1-phase: '' / 'banana' / '5 minutes' all → (0,1) when
      threaded through the /travel handler's floor logic
  (3) advance_time receives the floored delta and writes accurately
  (4) Multi-hour and multi-day inputs preserved unchanged

Run: python3 test_travel_duration_floor.py
"""

import sys

sys.path.insert(0, '/home/jordaneal/scripts')

import dnd_engine
from dnd_engine import parse_elapsed, advance_time, create_campaign, init_scene_state


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


# ──────────────────────────────────────────────────────────────────────────────
# (1) parse_elapsed canonical cases — pre-S66 behavior unchanged
# ──────────────────────────────────────────────────────────────────────────────

check('canon: 1 hour',          parse_elapsed('1 hour'),        (0, 1))
check('canon: an hour',         parse_elapsed('an hour'),       (0, 1))
check('canon: 4 hours',         parse_elapsed('4 hours'),       (0, 1))
check('canon: 8 hours',         parse_elapsed('8 hours'),       (0, 2))
check('canon: a day',           parse_elapsed('a day'),         (1, 0))
check('canon: 1 day',           parse_elapsed('1 day'),         (1, 0))
check('canon: half a day',      parse_elapsed('half a day'),    (0, 3))
check('canon: 5 minutes',       parse_elapsed('5 minutes'),     (0, 0))
check('canon: banana',          parse_elapsed('banana'),        None)
check('canon: empty',           parse_elapsed(''),              None)
check('canon: None input',      parse_elapsed(None),            None)


# ──────────────────────────────────────────────────────────────────────────────
# (2) /travel floor-at-1-phase rule: when parser returns None or (0,0),
# the handler must floor to (0,1) before calling advance_time.
#
# We test this by simulating the handler's logic directly: parse_elapsed
# || (0, 0); if (0, 0) then floor to (0, 1).
# ──────────────────────────────────────────────────────────────────────────────

def simulate_travel_floor(elapsed_str):
    """Reproduce the /travel handler's floor logic exactly."""
    parsed = parse_elapsed(elapsed_str) or (0, 0)
    days_d, phase_d = parsed
    floor_applied = False
    if days_d == 0 and phase_d == 0:
        days_d, phase_d = 0, 1
        floor_applied = True
    return (days_d, phase_d, floor_applied)


check('floor: 1 hour stays (0,1) no floor',
      simulate_travel_floor('1 hour'),       (0, 1, False))
check('floor: 4 hours stays (0,1) no floor',
      simulate_travel_floor('4 hours'),      (0, 1, False))
check('floor: 8 hours stays (0,2) no floor',
      simulate_travel_floor('8 hours'),      (0, 2, False))
check('floor: 1 day stays (1,0) no floor',
      simulate_travel_floor('1 day'),        (1, 0, False))
check('floor: half a day stays (0,3) no floor',
      simulate_travel_floor('half a day'),   (0, 3, False))

# Sub-phase / unparseable inputs all floor to (0,1)
check('floor: 5 minutes floored to (0,1)',
      simulate_travel_floor('5 minutes'),    (0, 1, True))
check('floor: banana floored to (0,1)',
      simulate_travel_floor('banana'),       (0, 1, True))
check('floor: empty string floored to (0,1)',
      simulate_travel_floor(''),             (0, 1, True))
check('floor: a moment floored to (0,1)',
      simulate_travel_floor('a moment'),     (0, 1, True))


# ──────────────────────────────────────────────────────────────────────────────
# (3) advance_time receives floored delta and writes accurately. Use
# a fresh test campaign to avoid colliding with prod state.
# ──────────────────────────────────────────────────────────────────────────────

TRAVEL_GUILD = 'test-guild-s66-travel'
TRAVEL_CAMP = create_campaign(TRAVEL_GUILD, 'Travel Test')
init_scene_state(TRAVEL_CAMP)

# Starting state: day 1, Morning (default init)
import sqlite3
conn = sqlite3.connect(dnd_engine.DB_PATH)
row = conn.execute(
    "SELECT campaign_day, day_phase FROM dnd_scene_state WHERE campaign_id=?",
    (TRAVEL_CAMP,)
).fetchone()
conn.close()
check_truthy('init: scene state exists', row is not None)
check('init: day 1', row[0], 1)
check('init: Morning phase', row[1], 'Morning')

# Apply '1 hour' → (0, 1) → Morning → Midday
days_d, phase_d, _ = simulate_travel_floor('1 hour')
ta = advance_time(TRAVEL_CAMP, days_d, phase_d, source='travel',
                  source_detail='Test:1hour')
check_truthy('1 hour: advance returns TimeAdvancement', ta is not None)
check('1 hour: phase advanced 1', ta.resolved_phase_delta, 1)
check('1 hour: from Morning',  ta.before_phase, 'Morning')
check('1 hour: to Midday',     ta.after_phase, 'Midday')

# Apply '8 hours' → (0, 2) → Midday → Evening
days_d, phase_d, _ = simulate_travel_floor('8 hours')
ta = advance_time(TRAVEL_CAMP, days_d, phase_d, source='travel',
                  source_detail='Test:8hours')
check_truthy('8 hours: advance returns TimeAdvancement', ta is not None)
check('8 hours: phase advanced 2', ta.resolved_phase_delta, 2)
check('8 hours: from Midday',     ta.before_phase, 'Midday')
check('8 hours: to Evening',      ta.after_phase, 'Evening')

# Apply 'banana' → floored to (0, 1) → Evening → Night
days_d, phase_d, floored = simulate_travel_floor('banana')
check_truthy('banana: floor applied', floored)
ta = advance_time(TRAVEL_CAMP, days_d, phase_d, source='travel',
                  source_detail='Test:banana')
check_truthy('banana: advance returns TimeAdvancement (no crash)',
             ta is not None)
check('banana: phase advanced 1 (floor)', ta.resolved_phase_delta, 1)
check('banana: from Evening',  ta.before_phase, 'Evening')
check('banana: to Night',      ta.after_phase, 'Night')

# Apply empty string → floored to (0, 1) → Night → Late Night
days_d, phase_d, floored = simulate_travel_floor('')
check_truthy('empty: floor applied', floored)
ta = advance_time(TRAVEL_CAMP, days_d, phase_d, source='travel',
                  source_detail='Test:empty')
check_truthy('empty: advance returns TimeAdvancement', ta is not None)
check('empty: phase advanced 1 (floor)', ta.resolved_phase_delta, 1)
check('empty: to Late Night', ta.after_phase, 'Late Night')

# Apply '1 day' → (1, 0) → wraps day, phase stays Late Night
days_d, phase_d, _ = simulate_travel_floor('1 day')
ta = advance_time(TRAVEL_CAMP, days_d, phase_d, source='travel',
                  source_detail='Test:1day')
check_truthy('1 day: advance returns TimeAdvancement', ta is not None)
check('1 day: days_delta=1', ta.days_delta, 1)
check('1 day: phase stays', ta.before_phase, ta.after_phase)
check('1 day: day +1', ta.after_day, ta.before_day + 1)


# ──────────────────────────────────────────────────────────────────────────────
# (4) Sequential travel: travel A→B 1hr, then B→C 4hr. Confirm two
# distinct phase advancements applied correctly (no state corruption).
# ──────────────────────────────────────────────────────────────────────────────

SEQ_CAMP = create_campaign('test-guild-s66-travel-seq', 'Travel Seq Test')
init_scene_state(SEQ_CAMP)

# 1 hour
days_d, phase_d, _ = simulate_travel_floor('1 hour')
ta1 = advance_time(SEQ_CAMP, days_d, phase_d, source='travel',
                   source_detail='Seq:A→B')
check_truthy('seq 1: advance returned', ta1 is not None)

# 4 hours
days_d, phase_d, _ = simulate_travel_floor('4 hours')
ta2 = advance_time(SEQ_CAMP, days_d, phase_d, source='travel',
                   source_detail='Seq:B→C')
check_truthy('seq 2: advance returned', ta2 is not None)

# Both should have advanced 1 phase each, total 2 phases from Morning
check('seq: ta1 phase delta = 1', ta1.resolved_phase_delta, 1)
check('seq: ta2 phase delta = 1', ta2.resolved_phase_delta, 1)
check('seq: starts Morning', ta1.before_phase, 'Morning')
check('seq: ta1 ends Midday', ta1.after_phase, 'Midday')
check('seq: ta2 starts Midday', ta2.before_phase, 'Midday')
check('seq: ta2 ends Afternoon', ta2.after_phase, 'Afternoon')


# ──────────────────────────────────────────────────────────────────────────────
# Cleanup + report
# ──────────────────────────────────────────────────────────────────────────────

print(f"\n{PASS} passed, {FAIL} failed")
if FAILURES:
    print("\nFAILURES:")
    for f in FAILURES:
        print(f)
    sys.exit(1)
sys.exit(0)
