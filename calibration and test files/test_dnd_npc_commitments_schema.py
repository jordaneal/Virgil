"""S73 — Conversational-Runtime Inversion v0 Phase 3a `dnd_npc_commitments` schema.

Validates the schema + single-writer + read accessor + FK cascade discipline
that lands at Phase 3a. Extractor (`parse_npc_commitment_utterances`) and
prompt directive (`compute_npc_commitment_anti_gaslight_directive`) land at
S75 — those have separate test surfaces. This file validates the table
itself + the `npc_commitment_*` accessors are §17-clean.

Coverage:
  T1  — table + indexes exist after db_init (idempotent)
  T2  — second db_init call leaves data intact (idempotent migration)
  T3  — valid commitment_upsert returns id + log line
  T4  — invalid commitment_kind refused (logs reason, returns None)
  T5  — invalid status refused
  T6  — empty/whitespace text refused
  T7  — non-existent npc_id refused (FK validation surface)
  T8  — get_active_npc_commitments returns only status='open'
  T9  — get_active_npc_commitments filtered by npc_id
  T10 — npc_commitment_set_status transitions status; only valid statuses allowed
  T11 — ON DELETE CASCADE: deleting an NPC removes their commitments
  T12 — cross-campaign isolation (campaign A NPC + campaign B query returns empty)

Run: python3 test_dnd_npc_commitments_schema.py
"""

import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, '/home/jordaneal/scripts')

_tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_tmp.close()
TEST_DB = Path(_tmp.name)

import dnd_engine
dnd_engine.DB_PATH = TEST_DB

captured_logs = []
_orig_log = dnd_engine.log
dnd_engine.log = lambda m: captured_logs.append(m)

dnd_engine.db_init()

from dnd_engine import (
    create_campaign,
    npc_upsert, npc_get_by_name,
    npc_commitment_upsert, npc_commitment_set_status,
    get_active_npc_commitments,
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


def fresh_conn():
    conn = sqlite3.connect(TEST_DB)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ── Fixture: campaign + two NPCs ──

cid = create_campaign("1", "S73 test")
res_a = npc_upsert(campaign_id=cid, name='Alarra')
npc_a_id = res_a[0] if isinstance(res_a, tuple) else res_a
res_b = npc_upsert(campaign_id=cid, name='Borek')
npc_b_id = res_b[0] if isinstance(res_b, tuple) else res_b
cid2 = create_campaign("2", "S73 test 2")
res_c = npc_upsert(campaign_id=cid2, name='Cordel')
npc_c_id = res_c[0] if isinstance(res_c, tuple) else res_c

# ── T1: table + indexes exist ──
conn = fresh_conn()
row = conn.execute(
    "SELECT name FROM sqlite_master WHERE name='dnd_npc_commitments' AND type='table'"
).fetchone()
check('T1: table exists', row is not None, True)
idx = {r[0] for r in conn.execute(
    "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='dnd_npc_commitments'"
).fetchall()}
check_truthy('T1: campaign_npc index', 'idx_npc_commitments_campaign_npc' in idx)
check_truthy('T1: campaign_status index', 'idx_npc_commitments_campaign_status' in idx)
conn.close()

# ── T2: second db_init is idempotent (no error, table intact, indexes intact) ──
pre_id = npc_commitment_upsert(
    campaign_id=cid, npc_id=npc_a_id,
    commitment_text='I will bring supplies by morning.',
    commitment_kind='promise',
)
check_truthy('T2: first upsert succeeded (id present)', pre_id is not None)
dnd_engine.db_init()  # second call
conn = fresh_conn()
post_count = conn.execute(
    "SELECT COUNT(*) FROM dnd_npc_commitments WHERE id=?", (pre_id,)
).fetchone()[0]
check('T2: row survives second db_init', post_count, 1)
conn.close()

# ── T3: valid commitment_upsert returns id + log line ──
captured_logs.clear()
new_id = npc_commitment_upsert(
    campaign_id=cid, npc_id=npc_a_id,
    commitment_text='Take this for ten silver.',
    commitment_kind='price',
    uttered_turn=42,
)
check_truthy('T3: valid upsert returned id', new_id is not None)
log_hit = [m for m in captured_logs if 'npc_commitment_upsert' in m and f'id={new_id}' in m]
check('T3: log line emitted', len(log_hit), 1)

# ── T4: invalid kind refused ──
captured_logs.clear()
bad = npc_commitment_upsert(
    campaign_id=cid, npc_id=npc_a_id,
    commitment_text='Some commitment.',
    commitment_kind='deliverable',  # not in enum
)
check('T4: invalid kind refused', bad, None)
log_hit = [m for m in captured_logs if 'bad kind' in m]
check('T4: log line emitted', len(log_hit), 1)

# ── T5: invalid status refused ──
captured_logs.clear()
bad = npc_commitment_upsert(
    campaign_id=cid, npc_id=npc_a_id,
    commitment_text='Some commitment.',
    status='maybe',
)
check('T5: invalid status refused', bad, None)
log_hit = [m for m in captured_logs if 'bad status' in m]
check('T5: log line emitted', len(log_hit), 1)

# ── T6: empty / whitespace text refused ──
check('T6: empty string refused',  npc_commitment_upsert(campaign_id=cid, npc_id=npc_a_id, commitment_text=''), None)
check('T6: whitespace refused',    npc_commitment_upsert(campaign_id=cid, npc_id=npc_a_id, commitment_text='   '), None)
check('T6: None refused',          npc_commitment_upsert(campaign_id=cid, npc_id=npc_a_id, commitment_text=None), None)

# ── T7: non-existent npc_id refused ──
captured_logs.clear()
bad = npc_commitment_upsert(
    campaign_id=cid, npc_id=99999,
    commitment_text='Phantom commitment.',
)
check('T7: bad npc_id refused', bad, None)
log_hit = [m for m in captured_logs if 'npc_not_found' in m]
check('T7: log line emitted', len(log_hit), 1)

# ── T8: get_active_npc_commitments returns only open ──
# Mark pre_id resolved; new_id stays open; add a third (open) and a fourth (expired).
npc_commitment_set_status(pre_id, 'resolved')
third_id = npc_commitment_upsert(
    campaign_id=cid, npc_id=npc_b_id,
    commitment_text='Borek will guard the gate at dawn.',
    commitment_kind='action',
)
fourth_id = npc_commitment_upsert(
    campaign_id=cid, npc_id=npc_b_id,
    commitment_text='Old promise.', commitment_kind='promise',
)
npc_commitment_set_status(fourth_id, 'expired')

active_all = get_active_npc_commitments(cid)
active_ids = {c['id'] for c in active_all}
check_truthy('T8: new_id present (open)',   new_id in active_ids)
check_truthy('T8: third_id present (open)', third_id in active_ids)
check_truthy('T8: pre_id absent (resolved)', pre_id not in active_ids)
check_truthy('T8: fourth_id absent (expired)', fourth_id not in active_ids)

# ── T9: filtered by npc_id ──
active_a = get_active_npc_commitments(cid, npc_id=npc_a_id)
active_b = get_active_npc_commitments(cid, npc_id=npc_b_id)
check('T9: A open count',  len(active_a), 1)
check('T9: B open count',  len(active_b), 1)
check('T9: A == new_id',   active_a[0]['id'], new_id)
check('T9: B == third_id', active_b[0]['id'], third_id)

# ── T10: set_status transitions; rejects bad status ──
check('T10: contradicted ok',   npc_commitment_set_status(new_id, 'contradicted'), True)
check('T10: bad refused',       npc_commitment_set_status(new_id, 'maybe'),        False)
# After contradicted, get_active no longer includes it.
active_a_post = get_active_npc_commitments(cid, npc_id=npc_a_id)
check('T10: contradicted excluded from active', len(active_a_post), 0)

# ── T11: ON DELETE CASCADE — deleting NPC removes their commitments ──
# Add a fresh commitment then delete NPC; row should disappear.
fresh_id = npc_commitment_upsert(
    campaign_id=cid, npc_id=npc_b_id,
    commitment_text='Borek pledges loyalty.', commitment_kind='promise',
)
check_truthy('T11: fresh commitment created', fresh_id is not None)
conn = fresh_conn()
# Direct NPC delete with cascade enabled
conn.execute("DELETE FROM dnd_npcs WHERE id=?", (npc_b_id,))
conn.commit()
remaining = conn.execute(
    "SELECT COUNT(*) FROM dnd_npc_commitments WHERE npc_id=?", (npc_b_id,)
).fetchone()[0]
conn.close()
check('T11: cascade removed all B commitments', remaining, 0)

# ── T12: cross-campaign isolation ──
# Commitment in campaign 1 for npc_a stays scoped.
camp2_active = get_active_npc_commitments(cid2)
check('T12: campaign 2 empty', len(camp2_active), 0)
# Add one in campaign 2.
c_id = npc_commitment_upsert(
    campaign_id=cid2, npc_id=npc_c_id,
    commitment_text='Cordel will deliver.', commitment_kind='action',
)
camp1_isolated = get_active_npc_commitments(cid)
check_truthy('T12: campaign 1 does not see camp 2 commitment',
             c_id not in {c['id'] for c in camp1_isolated})

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
