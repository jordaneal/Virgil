"""Sx — npc_upsert unique-skeleton-anchor token-prefix collapse (DOCTRINE.md §14.1).

When an incoming canonical_name shares its leading whole-token with exactly ONE
skeleton_origin=1 row in the same campaign, npc_upsert routes the upsert to that
anchor's recency-bump UPDATE branch instead of inserting a new row.

Four constraints lock the surface area:
  - unique anchor (multi-anchor ambiguity falls through to existing strict-equality)
  - skeleton_origin=1 (emergent rows never act as anchors)
  - same campaign_id (cross-campaign isolation preserved)
  - whole-token (matches _is_token_prefix semantics — not character-substring)

Skeleton-authored upserts (skeleton_origin=True) never collapse — they are
themselves authored canon, not parser hits.

Tests:
  1.  bare-firstname collapses to unique anchor (mc bumped, no new row, one collapse log)
  2.  multi-anchor refuses collapse and logs npc_anchor_ambiguous (insert proceeds normally)
  3.  emergent row (skeleton_origin=0) does NOT act as an anchor
  4.  cross-campaign isolation preserved (anchor in camp A doesn't anchor incoming in camp B)
  5.  whole-token rule rejects substring matches (Mir / Miranda do not collapse into Mira Wells)
  6.  idempotency on repeated short-form (5 calls → mc bumped 5x, 5 collapse logs)
  7.  skeleton×skeleton re-load not affected (skeleton_origin=True skips collapse path)
  8.  PC contamination guard still refuses (runs BEFORE collapse path)

Run: python3 test_npc_token_prefix_collapse.py
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
    create_campaign, bind_character,
    npc_upsert, npc_get_by_name,
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


def collapse_logs():
    """Return captured log lines that are npc_token_prefix_collapse lines."""
    return [m for m in captured if 'npc_token_prefix_collapse' in m]


def ambiguous_logs():
    """Return captured log lines that are npc_anchor_ambiguous lines."""
    return [m for m in captured if 'npc_anchor_ambiguous' in m]


def npc_row(campaign_id, canonical):
    """Helper: get (id, mention_count, skeleton_origin) for a row or None."""
    npc = npc_get_by_name(campaign_id, canonical)
    if npc is None:
        return None
    return (npc['id'], npc['mention_count'], npc['skeleton_origin'])


def npc_count(campaign_id):
    """Helper: total dnd_npcs row count for a campaign."""
    import sqlite3
    conn = sqlite3.connect(TEST_DB)
    n = conn.execute(
        "SELECT COUNT(*) FROM dnd_npcs WHERE campaign_id=?",
        (campaign_id,)
    ).fetchone()[0]
    conn.close()
    return n


# ──────────────────────────────────────────────────────────────────────────────
# Test 1: bare-firstname collapses to unique anchor
# ──────────────────────────────────────────────────────────────────────────────

CAMP_1 = create_campaign('guild-collapse-t1', 'Collapse T1')

captured.clear()
npc_upsert(CAMP_1, 'Eldrin Stormbow', skeleton_origin=True)  # anchor, mc=1
pre_count = npc_count(CAMP_1)

captured.clear()
result = npc_upsert(CAMP_1, 'Eldrin', skeleton_origin=False)

cl = collapse_logs()
anchor = npc_row(CAMP_1, 'Eldrin Stormbow')
bare = npc_row(CAMP_1, 'Eldrin')
post_count = npc_count(CAMP_1)

check('t1: anchor mention_count bumped to 2', anchor[1], 2)
check('t1: anchor skeleton_origin preserved', anchor[2], 1)
check('t1: no bare row inserted', bare, None)
check('t1: row count unchanged', post_count, pre_count)
check('t1: exactly one collapse log',  len(cl), 1)
check_truthy('t1: incoming in log',           "incoming='Eldrin'" in cl[0])
check_truthy('t1: anchor_name in log',        "anchor_name='Eldrin Stormbow'" in cl[0])
check_truthy('t1: anchor_id in log',          f"anchor_id={anchor[0]}" in cl[0])
check('t1: return is (anchor_id, False)',     result, (anchor[0], False))


# ──────────────────────────────────────────────────────────────────────────────
# Test 2: multi-anchor refuses collapse and logs npc_anchor_ambiguous
# ──────────────────────────────────────────────────────────────────────────────

CAMP_2 = create_campaign('guild-collapse-t2', 'Collapse T2')

npc_upsert(CAMP_2, 'Eldrin Stormbow',    skeleton_origin=True)
npc_upsert(CAMP_2, 'Eldrin Brightwater', skeleton_origin=True)

pre_storm  = npc_row(CAMP_2, 'Eldrin Stormbow')
pre_bright = npc_row(CAMP_2, 'Eldrin Brightwater')

captured.clear()
result = npc_upsert(CAMP_2, 'Eldrin', skeleton_origin=False)

cl  = collapse_logs()
amb = ambiguous_logs()
post_storm  = npc_row(CAMP_2, 'Eldrin Stormbow')
post_bright = npc_row(CAMP_2, 'Eldrin Brightwater')
post_bare   = npc_row(CAMP_2, 'Eldrin')

check('t2: zero collapse logs (no anchor was unique)', len(cl), 0)
check('t2: exactly one ambiguous log',                 len(amb), 1)
check_truthy('t2: incoming in ambiguous log', "incoming='Eldrin'" in amb[0])
check_truthy('t2: stormbow id in log',        f"id={pre_storm[0]}"  in amb[0])
check_truthy('t2: brightwater id in log',     f"id={pre_bright[0]}" in amb[0])
check_truthy('t2: stormbow name in log',      "name='Eldrin Stormbow'"    in amb[0])
check_truthy('t2: brightwater name in log',   "name='Eldrin Brightwater'" in amb[0])
check_truthy('t2: bare row WAS inserted (fall-through)', post_bare is not None)
check('t2: stormbow mention_count unchanged',   post_storm[1],  pre_storm[1])
check('t2: brightwater mention_count unchanged', post_bright[1], pre_bright[1])


# ──────────────────────────────────────────────────────────────────────────────
# Test 3: emergent row (skeleton_origin=0) does NOT act as anchor
# ──────────────────────────────────────────────────────────────────────────────

CAMP_3 = create_campaign('guild-collapse-t3', 'Collapse T3')

npc_upsert(CAMP_3, 'Eldrin Stormbow', skeleton_origin=False)  # emergent, NOT skeleton
pre_emergent = npc_row(CAMP_3, 'Eldrin Stormbow')

captured.clear()
npc_upsert(CAMP_3, 'Eldrin', skeleton_origin=False)

cl = collapse_logs()
post_emergent = npc_row(CAMP_3, 'Eldrin Stormbow')
post_bare     = npc_row(CAMP_3, 'Eldrin')

check('t3: zero collapse logs', len(cl), 0)
check_truthy('t3: bare row was inserted (no anchor)', post_bare is not None)
check('t3: emergent row mention_count unchanged', post_emergent[1], pre_emergent[1])
check('t3: emergent row skeleton_origin still 0', post_emergent[2], 0)


# ──────────────────────────────────────────────────────────────────────────────
# Test 4: cross-campaign isolation
# Anchor in CAMP_A shouldn't anchor incoming bare-firstname in CAMP_B.
# ──────────────────────────────────────────────────────────────────────────────

CAMP_4A = create_campaign('guild-collapse-t4a', 'Collapse T4A')
CAMP_4B = create_campaign('guild-collapse-t4b', 'Collapse T4B')

npc_upsert(CAMP_4A, 'Eldrin Stormbow', skeleton_origin=True)
pre_anchor_a = npc_row(CAMP_4A, 'Eldrin Stormbow')

captured.clear()
npc_upsert(CAMP_4B, 'Eldrin', skeleton_origin=False)

cl = collapse_logs()
post_anchor_a = npc_row(CAMP_4A, 'Eldrin Stormbow')
post_bare_b   = npc_row(CAMP_4B, 'Eldrin')

check('t4: zero collapse logs (cross-campaign)', len(cl), 0)
check_truthy('t4: bare row inserted in CAMP_B', post_bare_b is not None)
check('t4: CAMP_A anchor mention_count unchanged', post_anchor_a[1], pre_anchor_a[1])


# ──────────────────────────────────────────────────────────────────────────────
# Test 5: whole-token rule rejects substring matches
# "Mir" is NOT a token-prefix of "Mira Wells" (Mir != Mira at token level).
# "Miranda" likewise is NOT a token-prefix.
# ──────────────────────────────────────────────────────────────────────────────

CAMP_5 = create_campaign('guild-collapse-t5', 'Collapse T5')

npc_upsert(CAMP_5, 'Mira Wells', skeleton_origin=True)
pre_anchor = npc_row(CAMP_5, 'Mira Wells')

captured.clear()
npc_upsert(CAMP_5, 'Mir', skeleton_origin=False)
npc_upsert(CAMP_5, 'Miranda', skeleton_origin=False)

cl = collapse_logs()
post_anchor = npc_row(CAMP_5, 'Mira Wells')
post_mir     = npc_row(CAMP_5, 'Mir')
post_miranda = npc_row(CAMP_5, 'Miranda')

check('t5: zero collapse logs (substring not whole-token)', len(cl), 0)
check_truthy('t5: Mir row inserted',     post_mir is not None)
check_truthy('t5: Miranda row inserted', post_miranda is not None)
check('t5: anchor mention_count unchanged', post_anchor[1], pre_anchor[1])


# ──────────────────────────────────────────────────────────────────────────────
# Test 6: idempotency on repeated short-form
# 5 successive collapse calls → mc bumped 5x, 5 collapse logs, no new rows.
# ──────────────────────────────────────────────────────────────────────────────

CAMP_6 = create_campaign('guild-collapse-t6', 'Collapse T6')

npc_upsert(CAMP_6, 'Eldrin Stormbow', skeleton_origin=True)  # mc=1
pre_count = npc_count(CAMP_6)
pre_anchor = npc_row(CAMP_6, 'Eldrin Stormbow')

captured.clear()
for _ in range(5):
    npc_upsert(CAMP_6, 'Eldrin', skeleton_origin=False)

cl = collapse_logs()
post_count  = npc_count(CAMP_6)
post_anchor = npc_row(CAMP_6, 'Eldrin Stormbow')

check('t6: exactly 5 collapse logs',          len(cl), 5)
check('t6: anchor mention_count bumped 5x',   post_anchor[1], pre_anchor[1] + 5)
check('t6: row count unchanged across loop',  post_count, pre_count)


# ──────────────────────────────────────────────────────────────────────────────
# Test 7: skeleton×skeleton re-load NOT affected (skeleton_origin=True skips
# the collapse path entirely; re-load goes through the existing
# skeleton-re-load branch and does NOT bump mention_count).
# ──────────────────────────────────────────────────────────────────────────────

CAMP_7 = create_campaign('guild-collapse-t7', 'Collapse T7')

npc_upsert(CAMP_7, 'Eldrin Stormbow', skeleton_origin=True)
pre_anchor = npc_row(CAMP_7, 'Eldrin Stormbow')

captured.clear()
npc_upsert(CAMP_7, 'Eldrin Stormbow', skeleton_origin=True)  # re-load

cl = collapse_logs()
post_anchor = npc_row(CAMP_7, 'Eldrin Stormbow')

check('t7: zero collapse logs on skeleton re-load',   len(cl), 0)
check('t7: skeleton re-load does NOT bump mc',         post_anchor[1], pre_anchor[1])


# ──────────────────────────────────────────────────────────────────────────────
# Test 8: PC contamination guard still refuses
# Bound PC "Eldrin" exists in the campaign. Skeleton anchor "Eldrin Stormbow"
# is inserted with skeleton_origin=True (skeleton inserts bypass PC guard).
# Then upsert "Eldrin" with skeleton_origin=False: PC contamination guard
# (npc_upsert:2971-2976) fires FIRST and returns None — collapse path never runs.
# ──────────────────────────────────────────────────────────────────────────────

CAMP_8 = create_campaign('guild-collapse-t8', 'Collapse T8')

bind_character(CAMP_8, 'test-controller-1', 'Eldrin')  # bound PC named "Eldrin"
npc_upsert(CAMP_8, 'Eldrin Stormbow', skeleton_origin=True)  # skeleton bypasses PC guard
pre_anchor = npc_row(CAMP_8, 'Eldrin Stormbow')

captured.clear()
result = npc_upsert(CAMP_8, 'Eldrin', skeleton_origin=False)

cl  = collapse_logs()
amb = ambiguous_logs()
pc_refusal_logs = [m for m in captured if 'refused PC contamination' in m]
post_anchor = npc_row(CAMP_8, 'Eldrin Stormbow')
post_bare   = npc_row(CAMP_8, 'Eldrin')

check('t8: PC contamination guard returned None',  result, None)
check('t8: zero collapse logs',                    len(cl), 0)
check('t8: zero ambiguous logs',                   len(amb), 0)
check('t8: PC refusal log emitted',                len(pc_refusal_logs), 1)
check('t8: bare row NOT inserted',                 post_bare, None)
check('t8: anchor mention_count unchanged',        post_anchor[1], pre_anchor[1])


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
