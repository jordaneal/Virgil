"""S73 — Conversational-Runtime Inversion v0 quest-acceptance suggester card.

Validates the card format function `_format_quest_acceptance_suggester_card`
in `discord_dnd_bot.py`. Format per R4 precedent (5 existing card sites) +
Reading-2 direct (Quest Layer v0.1 post-S57 crystallization — no in-character
dialogue; pure operational suggestion).

Coverage:
  T1  — HIGH confidence card renders quest_id + title + verb + pasteable slash
  T2  — MEDIUM with offered quests lists pasteable slashes per quest
  T3  — MEDIUM with no offered quests surfaces "no offered" framing
  T4  — MEDIUM with >5 offered quests truncates and shows "+N more"
  T5  — quest with no title falls back to (untitled) label
  T6  — verb appears quoted in card body
  T7  — §F-59 holds: card never emits `!`-prefixed Avrae commands directly
  T8  — Reading-2 framing: no LLM-generated dialogue in card (suggester is
        pure operational text, not in-character speech)

Run: python3 test_inversion_v0_suggester_card.py
"""

import importlib
import sys

sys.path.insert(0, '/home/jordaneal/scripts')

# Import the card formatter directly. Pulling discord_dnd_bot has side effects
# (initializes Discord bot intents etc.); we extract just the function we need.
# Test the function by reading the source and exec-loading the function in
# isolation.
import re
src = open('/home/jordaneal/scripts/discord_dnd_bot.py').read()
match = re.search(
    r'^def _format_quest_acceptance_suggester_card\(.*?(?=^def |^async def )',
    src,
    re.MULTILINE | re.DOTALL
)
assert match, 'function not found in discord_dnd_bot.py'
func_src = match.group(0)
ns = {}
exec(func_src, ns)
_format_quest_acceptance_suggester_card = ns['_format_quest_acceptance_suggester_card']

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


def check_contains(label, haystack, needle):
    global PASS, FAIL
    if needle in haystack:
        PASS += 1
    else:
        FAIL += 1
        FAILURES.append(f"  {label}: '{needle}' not in card:\n    {haystack[:200]}")


# ── T1: HIGH confidence card ──
r_high = {
    'confidence': 'high',
    'matched_verb': 'agrees',
    'matched_quest_id': 7,
    'matched_quest_title': 'Dock master cargo',
}
card = _format_quest_acceptance_suggester_card(r_high, [])
check_contains('T1: QUEST ACCEPTANCE DETECTED header', card, '[QUEST ACCEPTANCE DETECTED]')
check_contains('T1: high marker',                     card, '**high**')
check_contains('T1: verb appears',                    card, 'agrees')
check_contains('T1: title appears',                   card, 'Dock master cargo')
check_contains('T1: pasteable slash',                 card, '/quest accept 7')

# ── T2: MEDIUM with offered quests ──
r_med = {
    'confidence': 'medium',
    'matched_verb': 'accept',
    'matched_quest_id': None,
    'matched_quest_title': '',
}
offered = [
    {'id': 7,  'title': 'Dock master cargo'},
    {'id': 11, 'title': 'Slay the wyrm'},
]
card = _format_quest_acceptance_suggester_card(r_med, offered)
check_contains('T2: medium marker',           card, '**medium**')
check_contains('T2: verb appears',            card, 'accept')
check_contains('T2: quest 7 listed',          card, 'Quest #7')
check_contains('T2: quest 11 listed',         card, 'Quest #11')
check_contains('T2: pasteable for 7',         card, '/quest accept 7')
check_contains('T2: pasteable for 11',        card, '/quest accept 11')

# ── T3: MEDIUM with no offered quests ──
card = _format_quest_acceptance_suggester_card(r_med, [])
check_contains('T3: no-offered framing',  card, 'no offered quests')
check_contains('T3: /quest add hint',     card, '/quest add')

# ── T4: MEDIUM with >5 offered quests truncates ──
many_offered = [{'id': i, 'title': f'Quest {i}'} for i in range(1, 9)]  # 8 quests
card = _format_quest_acceptance_suggester_card(r_med, many_offered)
listed = card.count('Quest #')
check('T4: only 5 listed',         listed, 5)
check_contains('T4: more suffix',  card, '+3 more')

# ── T5: untitled quest fallback ──
r_high_untitled = {
    'confidence': 'high',
    'matched_verb': 'agrees',
    'matched_quest_id': 99,
    'matched_quest_title': '',
}
card = _format_quest_acceptance_suggester_card(r_high_untitled, [])
check_contains('T5: untitled label', card, '(untitled)')

# ── T6: verb appears quoted ──
card = _format_quest_acceptance_suggester_card(r_high, [])
check_contains('T6: verb quoted in body', card, "_'agrees'_")

# ── T7: §F-59 holds — no !-prefixed Avrae commands in card ──
# Run card emission for several scenarios; none should contain `!command`.
for r in [r_high, r_med, r_high_untitled]:
    card = _format_quest_acceptance_suggester_card(r, offered)
    has_bang = bool(re.search(r'(?<!\w)!(?:init|game|cast|attack)\b', card))
    check(f'T7: no !-prefixed Avrae (verb={r["matched_verb"]!r})', has_bang, False)

# ── T8: Reading-2 — no LLM-generated dialogue in card ──
# The card is pure operational text; no "the NPC says" / "you say" framing.
# We check for the absence of those exact strings (and quoted dialogue patterns
# that would suggest in-character speech).
card = _format_quest_acceptance_suggester_card(r_high, offered)
for forbidden in ['the npc says', 'you say', '"says', 'narrates:']:
    has = forbidden.lower() in card.lower()
    check(f'T8: no in-character dialogue ({forbidden!r})', has, False)

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
