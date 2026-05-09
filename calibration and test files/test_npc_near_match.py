"""S23 — npc_near_match / location_near_match fragmentation diagnostics.

When npc_upsert or location_upsert lands a NEW canonical row (insert branch
only), it now checks Levenshtein distance against every existing canonical name
in the same campaign. Distance <= 2 emits a near-match log line.

Pure observability — does NOT change matching behavior or the strict-equality
identity rule (Phase 6 lock). The near-match log surfaces candidates for
human review; it does not auto-merge.

Tests:
  1.  levenshtein_distance — pure function edge cases
  2.  npc exact-match: update branch, no near_match log
  3.  npc distance-1 fire (Donavan vs Donovan)
  4.  npc distance-2 fire (Danvan vs Donovan)
  5.  npc distance-3 no fire (Gordon vs Donovan, dist >> 2)
  6.  npc cross-campaign isolation (Donovan in camp A doesn't fire for Donavan in camp B)
  7.  npc update branch doesn't fire (same name twice)
  8.  location_near_match fires on insert (same distance-1 check for locations)
  9.  location update branch doesn't fire

Run: python3 test_npc_near_match.py
"""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, '/home/jordaneal/scripts')

# ── Temp DB setup ──

_tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_tmp.close()
TEST_DB = Path(_tmp.name)

import dnd_engine
dnd_engine.DB_PATH = TEST_DB

_orig_log = dnd_engine.log
captured = []
dnd_engine.log = lambda m: captured.append(m)

dnd_engine.db_init()

from dnd_engine import (
    levenshtein_distance,
    create_campaign, npc_upsert, npc_get_by_name,
    location_upsert,
)

# ── Harness ──

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


def near_match_logs():
    """Return captured log lines that are near-match lines."""
    return [m for m in captured if 'near_match' in m]


# ──────────────────────────────────────────────────────────────────────────────
# Tests 1: levenshtein_distance — pure function
# ──────────────────────────────────────────────────────────────────────────────

check('lev: equal strings → 0',         levenshtein_distance('Donovan', 'Donovan'), 0)
check('lev: empty a → len(b)',           levenshtein_distance('', 'abc'), 3)
check('lev: empty b → len(a)',           levenshtein_distance('abc', ''), 3)
check('lev: both empty → 0',            levenshtein_distance('', ''), 0)
check('lev: Donavan/Donovan → 1',        levenshtein_distance('Donavan', 'Donovan'), 1)
check('lev: Danvan/Donovan → 2',         levenshtein_distance('Danvan', 'Donovan'), 2)
check('lev: Gordon/Donovan → 5',         levenshtein_distance('Gordon', 'Donovan'), 5)
check('lev: single char sub → 1',        levenshtein_distance('a', 'b'), 1)
check('lev: single insert → 1',          levenshtein_distance('ab', 'abc'), 1)
check('lev: single delete → 1',          levenshtein_distance('abc', 'ab'), 1)


# ──────────────────────────────────────────────────────────────────────────────
# Setup: two campaigns
# ──────────────────────────────────────────────────────────────────────────────

CAMP_A = create_campaign('guild-near-match', 'Near Match Campaign A')
CAMP_B = create_campaign('guild-near-match-b', 'Near Match Campaign B')


# ──────────────────────────────────────────────────────────────────────────────
# Test 2: npc exact-match insert → second call hits update branch, no log
# ──────────────────────────────────────────────────────────────────────────────

captured.clear()
npc_upsert(CAMP_A, 'Donovan')   # first insert — no existing names, no near_match
npc_upsert(CAMP_A, 'Donovan')   # second call → update branch, no near_match check

check('exact_match: no near_match logs', len(near_match_logs()), 0)


# ──────────────────────────────────────────────────────────────────────────────
# Test 3: npc distance-1 fires (Donavan vs Donovan)
# ──────────────────────────────────────────────────────────────────────────────

captured.clear()
npc_upsert(CAMP_A, 'Donavan')   # new name; Donovan already exists in CAMP_A

nm = near_match_logs()
check('dist1: exactly one near_match log', len(nm), 1)
check_truthy('dist1: new name in log',      "new='Donavan'" in nm[0])
check_truthy('dist1: existing in log',      "existing='Donovan'" in nm[0])
check_truthy('dist1: distance=1 in log',    'distance=1' in nm[0])
check_truthy('dist1: keyword present',      'npc_near_match' in nm[0])


# ──────────────────────────────────────────────────────────────────────────────
# Test 4: npc distance-2 fires (Danvan vs Donovan — distance=2)
# ──────────────────────────────────────────────────────────────────────────────

captured.clear()
npc_upsert(CAMP_A, 'Danvan')    # new name; levenshtein('Danvan','Donovan') = 2

nm = near_match_logs()
# May match BOTH 'Donovan' and 'Donavan' (Danvan is distance <=2 from both)
check_truthy('dist2: at least one near_match log', len(nm) >= 1)
any_dist2 = any('distance=2' in m or 'distance=1' in m for m in nm)
check_truthy('dist2: distance <=2 fired',  any_dist2)


# ──────────────────────────────────────────────────────────────────────────────
# Test 5: npc distance-3 no fire (Gordon vs all existing names >> 2)
# ──────────────────────────────────────────────────────────────────────────────

captured.clear()
npc_upsert(CAMP_A, 'Gordon')    # distance to Donovan=5, Donavan=5, Danvan=4 — all >2

check('dist3_no_fire: no near_match logs', len(near_match_logs()), 0)


# ──────────────────────────────────────────────────────────────────────────────
# Test 6: cross-campaign isolation
# Donovan exists in CAMP_A. Inserting Donavan into CAMP_B must NOT fire a
# near_match log — the query is scoped to the target campaign.
# ──────────────────────────────────────────────────────────────────────────────

captured.clear()
npc_upsert(CAMP_B, 'Donavan')   # CAMP_B is empty; no existing names to compare

check('cross_campaign: no near_match fires for empty campaign', len(near_match_logs()), 0)


# ──────────────────────────────────────────────────────────────────────────────
# Test 7: npc update branch doesn't fire (same name in same campaign)
# Donavan is now in CAMP_B. A second call with 'Donavan' hits the update path.
# ──────────────────────────────────────────────────────────────────────────────

captured.clear()
npc_upsert(CAMP_B, 'Donavan')   # update path — no near_match check

check('update_branch: no near_match log', len(near_match_logs()), 0)


# ──────────────────────────────────────────────────────────────────────────────
# Test 8: location_near_match fires on insert (distance-1)
# ──────────────────────────────────────────────────────────────────────────────

captured.clear()
location_upsert(CAMP_A, 'Tavern')       # first insert — no existing locations
location_upsert(CAMP_A, 'Cavern')       # Cavern vs Tavern: one substitution → distance=1

nm_loc = [m for m in captured if 'location_near_match' in m]
check('loc_dist1: one location_near_match log', len(nm_loc), 1)
check_truthy('loc_dist1: new name in log',      "new='Cavern'" in nm_loc[0])
check_truthy('loc_dist1: existing in log',      "existing='Tavern'" in nm_loc[0])
check_truthy('loc_dist1: distance=1',           'distance=1' in nm_loc[0])


# ──────────────────────────────────────────────────────────────────────────────
# Test 9: location update branch doesn't fire
# ──────────────────────────────────────────────────────────────────────────────

captured.clear()
location_upsert(CAMP_A, 'Tavern')   # update path — no near_match check

check('loc_update_branch: no near_match log', len([m for m in captured if 'near_match' in m]), 0)


# ──────────────────────────────────────────────────────────────────────────────
# Tests 10-15: npc_token_prefix_match (S30 Ship 4)
# ──────────────────────────────────────────────────────────────────────────────

def prefix_logs():
    return [m for m in captured if 'npc_token_prefix_match' in m]

CAMP_C = create_campaign('guild-token-prefix', 'Token Prefix Campaign C')

# Test 10: prefix_to_full — new is bare name, existing is full name
# Insert "Lira Songheart" first, then insert "Lira" → "Lira"'s full == existing's first token
captured.clear()
npc_upsert(CAMP_C, 'Lira Songheart')   # first insert
captured.clear()
npc_upsert(CAMP_C, 'Lira')             # insert branch; "Lira" == first token of "Lira Songheart"
pl = prefix_logs()
check('prefix_to_full: exactly one log', len(pl), 1)
check_truthy('prefix_to_full: new=Lira in log', "new='Lira'" in pl[0])
check_truthy('prefix_to_full: existing=Lira Songheart', "existing='Lira Songheart'" in pl[0])
check_truthy('prefix_to_full: relation correct', 'relation=prefix_to_full' in pl[0])

# Test 11: full_to_prefix — new is full name, existing is bare name
# "Lira" already in CAMP_C; insert "Lira Stormwind" → "Lira Stormwind"'s first token == "Lira"
captured.clear()
npc_upsert(CAMP_C, 'Lira Stormwind')   # insert branch; "Lira" == existing "Lira" full name
pl = prefix_logs()
check('full_to_prefix: exactly one log', len(pl), 1)
check_truthy('full_to_prefix: new=Lira Stormwind', "new='Lira Stormwind'" in pl[0])
check_truthy('full_to_prefix: existing=Lira', "existing='Lira'" in pl[0])
check_truthy('full_to_prefix: relation correct', 'relation=full_to_prefix' in pl[0])

# Test 12: case-insensitive — "lira" canonicalizes to "Lira" so check via npc engine
# (engine calls canonicalize_name before upsert; the comparison uses .lower())
# Test it via a name that is already canonicalized (uppercase first letter, rest lowercase)
captured.clear()
npc_upsert(CAMP_C, 'Lira Brightwater')  # first token "Lira" matches existing "Lira" (case-insensitive)
pl = prefix_logs()
check('case_insensitive: full_to_prefix fires', len(pl) >= 1, True)
check_truthy('case_insensitive: relation=full_to_prefix', any('relation=full_to_prefix' in l for l in pl))

# Test 13: negative — no token-prefix match when first tokens diverge
CAMP_D = create_campaign('guild-token-no-match', 'Token No Match Campaign D')
captured.clear()
npc_upsert(CAMP_D, 'Bob Smith')         # insert
captured.clear()
npc_upsert(CAMP_D, 'Lira')             # "Lira" != "Bob" (first token of "Bob Smith")
pl = prefix_logs()
check('negative_no_match: no prefix log', len(pl), 0)

# Test 14: negative — shared first token but neither is the other's full name
# "Lira Songheart" vs "Lira Stormwind": first tokens match but neither equals
# the other's full string → no fire
CAMP_E = create_campaign('guild-token-shared-prefix', 'Shared First Token Campaign E')
captured.clear()
npc_upsert(CAMP_E, 'Lira Songheart')
captured.clear()
npc_upsert(CAMP_E, 'Lira Stormwind')   # first token "Lira" == "Lira" but full strings differ
pl = prefix_logs()
check('shared_first_token: no prefix log (neither is the other full string)', len(pl), 0)

# Test 15: cross-campaign isolation
# "Lira" in CAMP_C should not fire for "Lira Songheart" insert in CAMP_E
CAMP_F = create_campaign('guild-token-cross', 'Cross Campaign F')
captured.clear()
npc_upsert(CAMP_F, 'Lira Songheart')   # CAMP_F is empty; no CAMP_C rows visible
pl = prefix_logs()
check('cross_campaign: no prefix log across campaign boundary', len(pl), 0)


# ──────────────────────────────────────────────────────────────────────────────
# Cleanup
# ──────────────────────────────────────────────────────────────────────────────

try:
    os.unlink(TEST_DB)
except OSError:
    pass

print(f"\n{PASS} passed, {FAIL} failed")
if FAILURES:
    print("\nFAILURES:")
    for f in FAILURES:
        print(f)
    sys.exit(1)
sys.exit(0)
