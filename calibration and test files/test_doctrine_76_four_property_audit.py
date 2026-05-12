"""Doctrine §76 four-property latent-canon regression test (Ship 2, S39).

Locks the current `dnd_scene_state` shape against future four-property
contamination surfaces. Per SCENE_STATE_CANON_SPEC.md §6.1 audit table:
a persisted scalar field is a latent-canon contamination surface iff it
hits all four properties:
    1. LLM-writable (non-gated write path)
    2. Persisted (stored beyond the turn)
    3. Retrieved (read back into LLM prompt context)
    4. Narratively inferential (rendered value invites LLM elaboration)

After Ship 2, NO column should hit all four. This test enumerates
`dnd_scene_state` columns, classifies each against the four properties,
and fails if any column scores 4/4.

D5 default per S38 spec review: per-table regression test. Each future
ship adding LLM-writable persisted scalars adds its own parallel test
(D5-general system-wide audit pass is filed as v1.x post-Ship-3).

Run:
    cd /home/jordaneal/scripts && python3 test_doctrine_76_four_property_audit.py
"""

import sys
import sqlite3
import tempfile
from pathlib import Path

sys.path.insert(0, '/home/jordaneal/scripts')

import dnd_engine

_tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_tmp.close()
TEST_DB = Path(_tmp.name)
dnd_engine.DB_PATH = TEST_DB

captured = []
dnd_engine.log = lambda m: captured.append(m)
dnd_engine.db_init()


# Classification per SCENE_STATE_CANON_SPEC.md §6.1.
# `llm_writable`: a non-gated write path exists from LLM output → this column.
# `persisted`: the column outlives the turn (it's in dnd_scene_state).
# `retrieved`: the column's value is read back into LLM prompt context.
# `narratively_inferential`: the rendered value invites LLM elaboration
#   (free-form prose, lists, "one short sentence" type content). Numeric,
#   enum-bounded, or identity-tag values fail this property.
#
# Borderline calls (kept post-Ship-2 with documented rationale):
#   - last_player_action: write is always-set by extract; content is the
#     player's verbatim input (no LLM inference) — fails property 4.
#   - last_dm_response: write is single-writer-disciplined
#     (update_last_dm_response); readback target is the commitment-directive
#     deterministic matcher, not narrative elaboration — fails property 3
#     for the LLM-narrative-inference path.
EXPECTED_CLASSIFICATION = {
    'campaign_id':         (False, True,  True,  False),
    'mode':                (False, True,  True,  False),  # LOCKED, enum
    'last_player_action':  (True,  True,  True,  False),  # verbatim player input
    'updated_at':          (False, True,  False, False),
    'tension_int':         (False, True,  True,  False),  # numeric scale
    'progress_clocks':     (False, True,  True,  False),  # structured JSON
    'current_location_id': (False, True,  True,  False),  # FK integer
    'turn_counter':        (False, True,  True,  False),  # counter
    'last_dm_response':    (False, True,  True,  False),  # det. readback path
    'last_active_actor':   (False, True,  True,  False),  # canonical name
    'campaign_day':        (False, True,  True,  False),  # integer
    'day_phase':           (False, True,  True,  False),  # fixed enum
}


# ─── Enumerate live schema ─────────────────────────────────────────────────
conn = sqlite3.connect(TEST_DB)
ss_cols = [row[1] for row in conn.execute("PRAGMA table_info(dnd_scene_state)")]
conn.close()


PASS = 0
FAIL = 0
FAILURES = []


def fail(label, detail):
    global FAIL
    FAIL += 1
    FAILURES.append(f"  {label}: {detail}")


def ok(label):
    global PASS
    PASS += 1


# ─── Coverage assertion: every live column is classified ──────────────────
for col in ss_cols:
    if col not in EXPECTED_CLASSIFICATION:
        fail(f'coverage: column {col!r} not classified',
             "Add classification to EXPECTED_CLASSIFICATION in this test "
             "(four-property tuple) — Doctrine §76 demands every persisted "
             "scalar on dnd_scene_state be explicitly audited at add time.")
    else:
        ok(f'coverage: {col!r} classified')

# Every classified column must still exist in schema (catches deletions
# that weren't reflected in the classification table)
for col in EXPECTED_CLASSIFICATION:
    if col not in ss_cols:
        fail(f'staleness: classification for {col!r} but column dropped',
             "Remove classification entry — column no longer in schema.")


# ─── §76 invariant: no column hits 4/4 ────────────────────────────────────
for col, (writable, persisted, retrieved, inferential) in (
        EXPECTED_CLASSIFICATION.items()):
    if col not in ss_cols:
        continue
    hits = sum([writable, persisted, retrieved, inferential])
    if hits == 4:
        fail(f'§76 violation: {col!r} hits all four properties',
             f"Either delete the column (structural removal per §76) or "
             f"convert to gated-write helper (single-writer per §17). "
             f"Validators are not sufficient — see SCENE_STATE_CANON_SPEC.md "
             f"§1.3 for rationale.")
    else:
        ok(f'§76: {col!r} 4-property score = {hits}/4 (clean)')


# ─── Deleted columns absent (sanity check) ────────────────────────────────
SHIP2_DELETED = (
    'location', 'established_details', 'focus', 'open_questions',
    'last_scene_change', 'active_npcs', 'active_threats', 'tension',
)
for col in SHIP2_DELETED:
    if col in ss_cols:
        fail(f'Ship 2 deletion regression: {col!r} present in schema',
             "The Ship 2 (S39) DROP COLUMN migration should have removed "
             "this column. Check the migration block in db_init() for the "
             "idempotency guard.")
    else:
        ok(f'Ship 2: {col!r} deleted')


# ─── Cleanup ──────────────────────────────────────────────────────────────
try:
    TEST_DB.unlink()
except OSError:
    pass


print(f"\n{PASS} passed, {FAIL} failed")
if FAILURES:
    print("\nFAILURES:")
    for f in FAILURES:
        print(f)
    sys.exit(1)
sys.exit(0)
