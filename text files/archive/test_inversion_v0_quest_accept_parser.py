"""S73 — Conversational-Runtime Inversion v0 Phase 3a quest-acceptance parser.

Closed-vocab narration-detection parser for quest-acceptance intent. Tests
the §1a.x deterministic-gate discipline: closed verb set + structured-signal
co-occurrence + whole-word tokenization + cross-turn LRU dedup + three-tier
confidence routing + feature-disable switch.

Coverage:
  T1  — verb-only narration with no offered quests → MEDIUM (verb fired,
        no structured signal)
  T2  — verb-only narration with offered quests but no title match → MEDIUM
  T3  — verb + matching quest title → HIGH (structured signal earns elevation)
  T4  — no verb → LOW (silent; fired=False)
  T5  — empty narration → LOW (no fire)
  T6  — feature-disabled returns disabled flag + low (no fire)
  T7  — phrasal "I'll take" with quest title match → HIGH
  T8  — phrasal "count me in" with no offered → MEDIUM
  T9  — cross-turn dedup suppresses same quest_id re-fire within window
  T10 — different quest_ids in window do NOT suppress each other
  T11 — verb-only dedup keys on verb (different verbs don't suppress)
  T12 — whole-word tokenization rejects substring (acceptable doesn't match
        accept-the-verb; "preaccept" doesn't false-fire)
  T13 — stopword title rejection (quest title "The Job" with stopwords only
        has no content-tokens → falls to medium not high)
  T14 — tie-break on equal token score picks lower id
  T15 — contraction-fold ("we'll" tokenization)

Run: python3 test_inversion_v0_quest_accept_parser.py
"""

import sys

sys.path.insert(0, '/home/jordaneal/scripts')

import quest_acceptance_parser as p

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


def reset():
    p._reset_dedup_for_tests()
    p.FEATURE_DISABLED = False


# ── T1: verb-only narration with no offered quests → MEDIUM ──
reset()
r = p.parse_quest_acceptance("I accept the offer.", [], 999)
check('T1: medium confidence', r['confidence'], 'medium')
check('T1: fired',             r['fired'],      True)
check('T1: verb',              r['matched_verb'], 'accept')
check('T1: no quest_id',       r['matched_quest_id'], None)

# ── T2: verb-only with offered quests but no title match → MEDIUM ──
reset()
r = p.parse_quest_acceptance(
    "I accept.",
    [{'id': 11, 'title': 'Slay the wyrm'}],
    999
)
check('T2: medium confidence', r['confidence'], 'medium')
check('T2: fired',             r['fired'],      True)
check('T2: no quest_id',       r['matched_quest_id'], None)

# ── T3: verb + matching title → HIGH ──
reset()
r = p.parse_quest_acceptance(
    "The party agrees to deliver the cargo to the dock master.",
    [{'id': 7, 'title': 'Dock master cargo delivery'}],
    999
)
check('T3: high confidence', r['confidence'], 'high')
check('T3: fired',           r['fired'],      True)
check('T3: verb',            r['matched_verb'], 'agrees')
check('T3: quest_id',        r['matched_quest_id'], 7)
check('T3: quest_title',     r['matched_quest_title'], 'Dock master cargo delivery')

# ── T4: no verb → LOW silent ──
reset()
r = p.parse_quest_acceptance(
    "The dragon roared and burned the village.",
    [{'id': 11, 'title': 'Slay the wyrm'}],
    999
)
check('T4: low confidence', r['confidence'], 'low')
check('T4: not fired',      r['fired'],      False)

# ── T5: empty narration → LOW ──
reset()
r = p.parse_quest_acceptance("", [{'id': 11, 'title': 'Slay the wyrm'}], 999)
check('T5: low confidence', r['confidence'], 'low')
check('T5: not fired',      r['fired'],      False)
r = p.parse_quest_acceptance(None, [], 999)
check('T5: None narration low',        r['confidence'], 'low')
check('T5: None narration not fired',  r['fired'],      False)

# ── T6: feature-disabled flag returned, no fire ──
reset()
p.FEATURE_DISABLED = True
r = p.parse_quest_acceptance("I accept the offer.", [], 999)
check('T6: feature_disabled flag',     r['feature_disabled'], True)
check('T6: fired False when disabled', r['fired'],            False)
check('T6: confidence low',            r['confidence'],       'low')
p.FEATURE_DISABLED = False

# ── T7: phrasal "I'll take" with quest title match → HIGH ──
reset()
r = p.parse_quest_acceptance(
    "I'll take the wyrm contract.",
    [{'id': 19, 'title': 'Wyrm contract'}],
    999
)
check('T7: phrasal high',     r['confidence'], 'high')
check('T7: phrasal verb',     r['matched_verb'], "i'll take")
check('T7: phrasal quest_id', r['matched_quest_id'], 19)

# ── T8: phrasal "count me in" with no offered → MEDIUM ──
reset()
r = p.parse_quest_acceptance("Count me in!", [], 999)
check('T8: count-me-in medium', r['confidence'], 'medium')
check('T8: count-me-in fired',  r['fired'],      True)
check('T8: verb',               r['matched_verb'], 'count me in')

# ── T9: cross-turn dedup same quest_id ──
reset()
quests = [{'id': 7, 'title': 'Dock master cargo'}]
r1 = p.parse_quest_acceptance("The party agrees to dock master cargo.", quests, 999)
r2 = p.parse_quest_acceptance("The party agrees to dock master cargo.", quests, 999)
check('T9: first fire fired',         r1['fired'], True)
check('T9: first fire not dedup',     r1['dedup_suppressed'], False)
check('T9: second fire dedup',        r2['dedup_suppressed'], True)
check('T9: second fire not fired',    r2['fired'], False)

# ── T10: different quest_ids in window do NOT suppress each other ──
reset()
qa = [{'id': 7, 'title': 'Dock master cargo'}]
qb = [{'id': 8, 'title': 'Forest patrol'}]
r1 = p.parse_quest_acceptance("Party agrees to dock master cargo.", qa, 999)
r2 = p.parse_quest_acceptance("Party agrees to forest patrol.",     qb, 999)
check('T10: q7 fires',          r1['fired'], True)
check('T10: q7 not dedup',      r1['dedup_suppressed'], False)
check('T10: q8 fires (different quest)', r2['fired'], True)
check('T10: q8 not dedup',      r2['dedup_suppressed'], False)

# ── T11: verb-only dedup keys on verb ──
reset()
r1 = p.parse_quest_acceptance("I accept.",  [], 999)
r2 = p.parse_quest_acceptance("I pledge.",  [], 999)
r3 = p.parse_quest_acceptance("I accept again.", [], 999)
check('T11: accept fires',          r1['fired'], True)
check('T11: pledge fires (different verb)', r2['fired'], True)
check('T11: accept-again dedup',    r3['dedup_suppressed'], True)

# ── T12: whole-word rejects substring ──
reset()
# "acceptable" contains "accept" as substring but should NOT match as whole word.
# Tokenization splits on non-letter chars so "acceptable" remains one token "acceptable".
r = p.parse_quest_acceptance("The risk seems acceptable.", [], 999)
check('T12: substring rejected', r['fired'], False)
check('T12: substring low',      r['confidence'], 'low')
# Confirm whole-word still works in the same campaign (after dedup reset).
reset()
r2 = p.parse_quest_acceptance("I accept the risk.", [], 999)
check('T12: whole-word fires',   r2['fired'], True)

# ── T13: stopword-only title falls to medium ──
reset()
r = p.parse_quest_acceptance(
    "I accept the job.",
    [{'id': 5, 'title': 'The'}],  # title is pure stopword, post-filter empty
    999
)
check('T13: stopword title → medium', r['confidence'], 'medium')
check('T13: no quest_id matched',     r['matched_quest_id'], None)

# ── T14: tie-break on equal token score picks lower id ──
reset()
quests = [
    {'id': 15, 'title': 'Cargo run'},
    {'id': 7,  'title': 'Cargo run'},  # same content tokens; lower id wins
]
r = p.parse_quest_acceptance("The party agrees to a cargo run.", quests, 999)
check('T14: tie-break lower id',    r['matched_quest_id'], 7)
check('T14: confidence high',       r['confidence'],       'high')

# ── T15: contraction-fold ("we'll") ──
reset()
# Tokenization with apostrophe should produce "we'll" (or "we"+"ll"); either form
# must match a phrasal entry.
r = p.parse_quest_acceptance("We'll take the cargo run job.", [{'id': 7, 'title': 'Cargo run'}], 999)
check('T15: contraction high', r['confidence'], 'high')
check('T15: quest_id',         r['matched_quest_id'], 7)

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
