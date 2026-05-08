"""Deterministic unit tests for compute_consequence_directive (Session 16).

Pure function tests — no DB, no LLM. Inputs are constructed dicts that
match the shape returned by engine.get_active_consequences.

Run:
    cd /home/jordaneal/scripts && python3 test_consequence_directive.py
"""

import sys
sys.path.insert(0, '/home/jordaneal/scripts')

import dnd_engine
dnd_engine.log = lambda m: None

from dnd_orchestration import (
    compute_consequence_directive,
    consequence_log_summary,
    CONSEQUENCE_DIRECTIVE_CAP,
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


def make_c(cid, npc_id, kind='threat', severity=2, summary='did a thing',
           canonical_name='Someone', last_surfaced_turn=None):
    return {
        'id': cid,
        'npc_id': npc_id,
        'kind': kind,
        'severity': severity,
        'summary': summary,
        'canonical_name': canonical_name,
        'last_surfaced_turn': last_surfaced_turn,
    }


# ─── empty / silent paths ────────────────────────────────────────────────────
text, surfaced = compute_consequence_directive([], {1, 2, 3})
check('empty input: text', text, '')
check('empty input: surfaced', surfaced, [])

text, surfaced = compute_consequence_directive(None, [1, 2])
check('None input: text', text, '')
check('None input: surfaced', surfaced, [])

text, surfaced = compute_consequence_directive(
    [make_c(1, 100)], in_scope_npc_ids=set()
)
check('empty scope: text', text, '')
check('empty scope: surfaced', surfaced, [])

text, surfaced = compute_consequence_directive(
    [make_c(1, 100)], in_scope_npc_ids=None
)
check('None scope: text', text, '')


# ─── relevance filter: only in-scope NPCs surface ────────────────────────────
cs = [
    make_c(1, 100, canonical_name='Reginald'),
    make_c(2, 200, canonical_name='Lira'),  # out of scope
]
text, surfaced = compute_consequence_directive(cs, [100])
check('relevance: 1 surfaced', len(surfaced), 1)
check('relevance: surfaced is reginald', surfaced[0]['npc_id'], 100)
check('relevance: text includes reginald', 'Reginald' in text, True)
check('relevance: text excludes lira', 'Lira' not in text, True)


# ─── single relevant: full block format ──────────────────────────────────────
cs = [make_c(1, 100, kind='threat', severity=2,
              summary='player threatened to burn the inn',
              canonical_name='Reginald the Innkeeper')]
text, surfaced = compute_consequence_directive(cs, [100])
check_truthy('single: text non-empty', text)
check_truthy('single: contains kind tag', '[threat, sev 2]' in text)
check_truthy('single: contains npc name',
              'Reginald the Innkeeper' in text)
check_truthy('single: contains summary',
              'player threatened to burn the inn' in text)
check_truthy('single: contains do-not-restate guard',
              'remembered consequences' in text)


# ─── multiple at same severity: tie-broken by recency desc ──────────────────
cs = [
    make_c(1, 100, severity=2, last_surfaced_turn=5,  canonical_name='A'),
    make_c(2, 200, severity=2, last_surfaced_turn=10, canonical_name='B'),
    make_c(3, 300, severity=2, last_surfaced_turn=2,  canonical_name='C'),
]
text, surfaced = compute_consequence_directive(cs, [100, 200, 300])
ids_in_order = [c['id'] for c in surfaced]
# Most recent (10) first, then 5, then 2.
check('tie-break by recency: order',
      ids_in_order, [2, 1, 3])


# ─── never-surfaced NULL last sorts AFTER surfaced rows at same severity ────
cs = [
    make_c(1, 100, severity=2, last_surfaced_turn=None, canonical_name='Fresh'),
    make_c(2, 200, severity=2, last_surfaced_turn=5,    canonical_name='Stale'),
]
text, surfaced = compute_consequence_directive(cs, [100, 200])
# Stale (surfaced) comes BEFORE Fresh (never surfaced) at same severity.
check('null-last: stale first', surfaced[0]['id'], 2)
check('null-last: fresh second', surfaced[1]['id'], 1)


# ─── severity desc: high severity wins regardless of recency ────────────────
cs = [
    make_c(1, 100, severity=1, last_surfaced_turn=100, canonical_name='RecentLow'),
    make_c(2, 200, severity=3, last_surfaced_turn=1,   canonical_name='OldHigh'),
    make_c(3, 300, severity=2, last_surfaced_turn=50,  canonical_name='Mid'),
]
text, surfaced = compute_consequence_directive(cs, [100, 200, 300])
# Order: severity 3, 2, 1.
check('severity desc: top is sev 3', surfaced[0]['severity'], 3)
check('severity desc: middle is sev 2', surfaced[1]['severity'], 2)
check('severity desc: bottom is sev 1', surfaced[2]['severity'], 1)


# ─── cap at CONSEQUENCE_DIRECTIVE_CAP (3) ───────────────────────────────────
cs = [make_c(i, i + 100, severity=3, last_surfaced_turn=i,
              canonical_name=f"NPC{i}")
      for i in range(1, 8)]
text, surfaced = compute_consequence_directive(cs, [101, 102, 103, 104, 105, 106, 107])
check('cap: only N rows surfaced', len(surfaced), CONSEQUENCE_DIRECTIVE_CAP)
check('cap: equals 3',              CONSEQUENCE_DIRECTIVE_CAP, 3)


# ─── 4 relevant, severities [3,3,2,1] → drop sev 1 ──────────────────────────
cs = [
    make_c(1, 100, severity=3, last_surfaced_turn=10, canonical_name='A'),
    make_c(2, 200, severity=3, last_surfaced_turn=5,  canonical_name='B'),
    make_c(3, 300, severity=2, last_surfaced_turn=8,  canonical_name='C'),
    make_c(4, 400, severity=1, last_surfaced_turn=20, canonical_name='D'),  # drop
]
text, surfaced = compute_consequence_directive(cs, [100, 200, 300, 400])
surfaced_ids = sorted(c['id'] for c in surfaced)
check('cap drops lowest severity', surfaced_ids, [1, 2, 3])
# Sev 1 row's NPC ('D') should NOT appear in text.
check('cap: dropped row not in text', 'D ' not in text, True)


# ─── output format: each line has bullet + name + [kind, sev N] + summary ───
cs = [make_c(1, 100, kind='mercy', severity=2,
              summary='spared at the bridge',
              canonical_name='Lira')]
text, _ = compute_consequence_directive(cs, [100])
check_truthy('format: bullet present',  '  - Lira [mercy, sev 2]: spared at the bridge' in text)


# ─── directive includes leading prose + trailing manifestation guidance ─────
cs = [make_c(1, 100, canonical_name='X')]
text, _ = compute_consequence_directive(cs, [100])
check_truthy('format: leading prose', 'weight what the named NPCs feel' in text)
check_truthy('format: manifestation guidance', 'manifest them' in text)
check_truthy('format: posture pressure', 'NPC posture' in text)


# ─── consequence_log_summary ────────────────────────────────────────────────
empty_summary = consequence_log_summary([])
check('log summary: empty', empty_summary, 'emitted=0')

surfaced = [
    {'id': 1, 'canonical_name': 'Reginald', 'kind': 'threat', 'severity': 2},
    {'id': 5, 'canonical_name': 'Lira',     'kind': 'mercy',  'severity': 3},
]
s = consequence_log_summary(surfaced)
check_truthy('log: has emitted=2', 'emitted=2' in s)
check_truthy('log: has reginald',  'Reginald|threat|sev=2|id=1' in s)
check_truthy('log: has lira',       'Lira|mercy|sev=3|id=5' in s)


# ─── empty in_scope produces silence (regression guard) ─────────────────────
cs = [make_c(1, 100), make_c(2, 200)]
text, surfaced = compute_consequence_directive(cs, [])
check('empty scope after filter: silent text', text, '')
check('empty scope after filter: silent ids', surfaced, [])


# ─── final report ────────────────────────────────────────────────────────────
print(f"PASS: {PASS}  FAIL: {FAIL}")
if FAIL:
    print("\nFailures:")
    for f in FAILURES:
        print(f)

sys.exit(0 if FAIL == 0 else 1)
