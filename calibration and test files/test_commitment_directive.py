"""Deterministic unit tests for compute_commitment_directive (Session 19).

Escape-only v1 of the committed-action resolution layer. Pure function
tests for the directive helper plus a small live test for the schema
migration's idempotency and cross-campaign isolation.

Run:
    cd /home/jordaneal/scripts && python3 test_commitment_directive.py
"""

import os
import sys
import sqlite3
import tempfile

sys.path.insert(0, '/home/jordaneal/scripts')

import dnd_engine

# Silence engine logs so the test output stays clean.
dnd_engine.log = lambda m: None

import dnd_orchestration as orch
from dnd_orchestration import (
    compute_commitment_directive,
    commitment_log_summary,
    is_scene_shift_intent,
    _has_reaction_verbs,
    _is_retracting,
    SCENE_SHIFT_RX,
    INTENT_COMBAT,
    INTENT_SOCIAL,
    INTENT_TRIVIAL,
    INTENT_RISKY,
    INTENT_CONTESTED,
    INTENT_EXPLORATION,
)

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


def call(prior='I swing my dagger at Garrick',
         current='I head outside to help the child',
         intent_prior=INTENT_COMBAT,
         intent_current=INTENT_TRIVIAL,
         avrae=False,
         dm_response='',
         hints=('Garrick',)):
    return compute_commitment_directive(
        intent_prior=intent_prior,
        intent_current=intent_current,
        current_action_text=current,
        prior_action_text=prior,
        avrae_resolved_since_prior=avrae,
        prior_dm_response=dm_response,
        prior_target_hints=list(hints),
    )


# ─── canonical positive case (Session 18 godmode test) ──────────────────────
# Player committed to combat ("I swing my dagger at Garrick"), scene-shifted
# the next turn ("I head outside to help the child"), no Avrae roll fired,
# prior DM response had no reaction verbs. All gates pass → directive fires.
text, sig = call()
check_truthy('canonical fire: signal[fired]', sig['fired'])
check_truthy('canonical fire: text non-empty', bool(text))
check_truthy('canonical fire: text contains prior action', 'I swing my dagger at Garrick' in text)
check_truthy('canonical fire: text contains current action', 'I head outside to help the child' in text)
check_truthy('canonical fire: text contains B2.1 narration mandate',
             'narration MUST address the prior commitment' in text)
check_truthy('canonical fire: text lists three options',
             '(a)' in text and '(b)' in text and '(c)' in text)


# ─── gate-isolated negatives (one per gate) ─────────────────────────────────
# Gate 1: prior intent must be COMBAT.
text, sig = call(intent_prior=INTENT_SOCIAL)
check('gate1 (SOCIAL prior): text empty', text, '')
check('gate1 (SOCIAL prior): not fired', sig['fired'], 0)

text, sig = call(intent_prior=INTENT_EXPLORATION)
check('gate1 (EXPLORATION prior): text empty', text, '')
check('gate1 (EXPLORATION prior): not fired', sig['fired'], 0)

# Gate 2: Avrae buffer drained → mechanical resolution happened.
text, sig = call(avrae=True)
check('gate2 (Avrae drained): text empty', text, '')
check('gate2 (Avrae drained): signal records drained', sig['avrae_drained'], 1)
check('gate2 (Avrae drained): not fired', sig['fired'], 0)

# Gate 3: prior DM response had a reaction verb in target proximity.
text, sig = call(dm_response='Garrick stumbles back, gasping for air.')
check('gate3 (reaction verb): text empty', text, '')
check('gate3 (reaction verb): signal records resolution', sig['reaction_verbs'], 1)
check('gate3 (reaction verb): not fired', sig['fired'], 0)

# Gate 4: current turn is not a scene shift — directive doesn't fire.
text, sig = call(current='I swing again', intent_current=INTENT_COMBAT)
check('gate4 (combat continuation): text empty', text, '')
check('gate4 (combat continuation): is_scene_shift=0', sig['is_scene_shift'], 0)
check('gate4 (combat continuation): not fired', sig['fired'], 0)

text, sig = call(current='I look at his expression', intent_current=INTENT_TRIVIAL)
check('gate4 (look around): text empty', text, '')
check('gate4 (look around): is_scene_shift=0', sig['is_scene_shift'], 0)

# Gate 5: explicit retraction suppresses the directive.
text, sig = call(current='Wait, never mind, I head outside')
check('gate5 (retraction): text empty', text, '')
check('gate5 (retraction): retraction_filtered=1', sig['retraction_filtered'], 1)
check('gate5 (retraction): not fired', sig['fired'], 0)

text, sig = call(current='Actually, I sheath my dagger and step back')
check('gate5 (sheath): retraction_filtered=1', sig['retraction_filtered'], 1)


# ─── SCENE_SHIFT_RX positives and negatives ─────────────────────────────────
shift_positives = [
    'I leave the tavern',
    'I head outside',
    'I head outside to help the child',
    'I head into the woods',
    'I walk away from him',
    'I run out the door',
    'I disengage',
    'I retreat',
    'I flee the scene',
    'I exit',
    'I depart for the inn',
    'I step outside',
    'I move on',
    'I travel to the next town',
    'I return to the inn',
]
for t in shift_positives:
    check_truthy(f'SCENE_SHIFT positive {t!r}', is_scene_shift_intent(t))

shift_negatives = [
    'I leave the door open',  # idiom carve-out
    'I attack the goblin',
    'I look around',
    'I sit by the fire',
    'I drink my ale',
    'I stay where I am',
]
for t in shift_negatives:
    check_falsy(f'SCENE_SHIFT negative {t!r}', is_scene_shift_intent(t))


# ─── reaction-verb proximity check ──────────────────────────────────────────
check_truthy(
    'react: target named with reaction verb in proximity',
    _has_reaction_verbs('Garrick stumbles back, gasping.', ['Garrick'])
)
check_truthy(
    'react: case-insensitive name match',
    _has_reaction_verbs('Garrick recoils.', ['garrick'])
)
check_truthy(
    'react: alternate verb forms',
    _has_reaction_verbs('Garrick parried the swing.', ['Garrick'])
)
check_falsy(
    'react: target named, no reaction verb',
    _has_reaction_verbs('Garrick stares at you, hand resting on his cudgel.',
                        ['Garrick'])
)
check_falsy(
    'react: empty dm_text',
    _has_reaction_verbs('', ['Garrick'])
)
check_falsy(
    'react: empty target_names',
    _has_reaction_verbs('Garrick stumbles.', [])
)
check_falsy(
    'react: target absent from text',
    _has_reaction_verbs('Lira recoils.', ['Garrick'])
)
# 120-char window check: reaction verb FAR from target name should miss.
distant = (
    'Garrick stares at you. ' + ('Filler. ' * 30) + 'A bystander dodges a cart.'
)
check_falsy(
    'react: reaction verb outside 120-char window',
    _has_reaction_verbs(distant, ['Garrick'])
)


# ─── retraction grammar ─────────────────────────────────────────────────────
retract_positives = [
    'Wait, never mind, I head outside',
    'On second thought, I sheath my dagger',
    'Actually, I want to talk',
    'Wait, let me think about this',
    'I sheath my blade and step back',
    'Hold on, let me reconsider',
    "I won't attack",
    'Stand down — I yield',
]
for t in retract_positives:
    check_truthy(f'retract positive {t!r}', _is_retracting(t))

retract_negatives = [
    'I attack',
    'I head outside',
    'Wait for the right moment, then strike',
    'I draw my sword',
    'I think the goblin is wounded',
]
for t in retract_negatives:
    check_falsy(f'retract negative {t!r}', _is_retracting(t))


# ─── commitment_log_summary shape ───────────────────────────────────────────
fired_summary = commitment_log_summary({
    'fired': 1,
    'prior_intent': 'combat',
    'current_intent': 'trivial',
    'is_scene_shift': 1,
    'avrae_drained': 0,
    'reaction_verbs': 0,
    'retraction_filtered': 0,
})
check_truthy('log summary fired=1 present', 'fired=1' in fired_summary)
check_truthy('log summary prior_intent=combat', 'prior_intent=combat' in fired_summary)
check_truthy('log summary is_scene_shift=1', 'is_scene_shift=1' in fired_summary)

empty_summary = commitment_log_summary({})
check_truthy('log summary empty fired=0', 'fired=0' in empty_summary)


# ─── composition order via build_dm_context ────────────────────────────────
out = dnd_engine.build_dm_context(
    campaign={'id': 1, 'name': 'Test', 'tone': '', 'current_scene': ''},
    characters=[],
    consequence_directive='CONSEQ-MARKER-XYZ',
    commitment_directive='COMMIT-MARKER-XYZ',
)
i_conseq = out.find('CONSEQ-MARKER-XYZ')
i_commit = out.find('COMMIT-MARKER-XYZ')
check_truthy('composition: consequence rendered', i_conseq > 0)
check_truthy('composition: commitment rendered', i_commit > 0)
check_truthy('composition: commitment AFTER consequence',
             i_conseq > 0 and i_commit > i_conseq)

out_empty = dnd_engine.build_dm_context(
    campaign={'id': 1, 'name': 'Test', 'tone': '', 'current_scene': ''},
    characters=[],
    commitment_directive='',
)
check_falsy('empty kwarg: no UNRESOLVED COMMITMENT block',
            '=== UNRESOLVED COMMITMENT ===' in out_empty)


# ─── schema + persistence: migration idempotency, cross-campaign ────────────
# Run db_init twice and confirm column set is stable.
dnd_engine.db_init()
conn = sqlite3.connect(dnd_engine.DB_PATH)
cols1 = sorted(row[1] for row in conn.execute('PRAGMA table_info(dnd_scene_state)'))
conn.close()
dnd_engine.db_init()
conn = sqlite3.connect(dnd_engine.DB_PATH)
cols2 = sorted(row[1] for row in conn.execute('PRAGMA table_info(dnd_scene_state)'))
conn.close()
check('migration idempotent: column set unchanged on re-run', cols1, cols2)
check_truthy('migration: last_dm_response present', 'last_dm_response' in cols1)


# Cross-campaign isolation. Use scratch campaign IDs that are unlikely
# to clash with live state. (Direct row insert + helper round-trip; the
# schema's PRIMARY KEY constraint guarantees independence.)
SCRATCH_A = 99001
SCRATCH_B = 99002
conn = sqlite3.connect(dnd_engine.DB_PATH)
try:
    conn.execute(
        "INSERT OR REPLACE INTO dnd_scene_state "
        "(campaign_id, location, mode, focus, established_details, "
        "active_npcs, active_threats, open_questions, tension, "
        "last_player_action, last_scene_change, updated_at) "
        "VALUES (?, '', 'exploration', '', '[]', '[]', '[]', '[]', 'low', "
        "'', '', ?)",
        (SCRATCH_A, '2026-05-04T00:00:00')
    )
    conn.execute(
        "INSERT OR REPLACE INTO dnd_scene_state "
        "(campaign_id, location, mode, focus, established_details, "
        "active_npcs, active_threats, open_questions, tension, "
        "last_player_action, last_scene_change, updated_at) "
        "VALUES (?, '', 'exploration', '', '[]', '[]', '[]', '[]', 'low', "
        "'', '', ?)",
        (SCRATCH_B, '2026-05-04T00:00:00')
    )
    conn.commit()
finally:
    conn.close()

dnd_engine.update_last_dm_response(SCRATCH_A, 'Garrick recoils as Donovan swings.')
dnd_engine.update_last_dm_response(SCRATCH_B, 'A different scene entirely.')
state_a = dnd_engine.get_scene_state(SCRATCH_A)
state_b = dnd_engine.get_scene_state(SCRATCH_B)
check_truthy('cross-campaign A: write reflected',
             'Garrick recoils' in (state_a or {}).get('last_dm_response', ''))
check_truthy('cross-campaign B: write reflected',
             'different scene entirely' in (state_b or {}).get('last_dm_response', ''))
check_truthy('cross-campaign A != B',
             (state_a or {}).get('last_dm_response') !=
             (state_b or {}).get('last_dm_response'))

# Truncation cap: tail-keep last 4000 chars.
big = 'X' * 5000 + 'TAIL_MARKER'
dnd_engine.update_last_dm_response(SCRATCH_A, big)
state_a2 = dnd_engine.get_scene_state(SCRATCH_A)
stored = (state_a2 or {}).get('last_dm_response', '')
check_truthy('truncation: stored len <= 4000', len(stored) <= 4000)
check_truthy('truncation: TAIL_MARKER preserved', stored.endswith('TAIL_MARKER'))

# Cleanup scratch rows.
conn = sqlite3.connect(dnd_engine.DB_PATH)
try:
    conn.execute('DELETE FROM dnd_scene_state WHERE campaign_id IN (?, ?)',
                 (SCRATCH_A, SCRATCH_B))
    conn.commit()
finally:
    conn.close()


# ─── summary ────────────────────────────────────────────────────────────────
print(f"\nPASS: {PASS}")
print(f"FAIL: {FAIL}")
if FAIL:
    print("\nFailures:")
    for f in FAILURES:
        print(f)
    sys.exit(1)
else:
    print("All commitment_directive tests passed.")
