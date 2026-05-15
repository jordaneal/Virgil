"""S68 N-4 — NPC pronoun lock adversarial verify.

Phase A schema migration + npc_pronouns_set single-writer.
Phase B backfill extractor (regex over prose).
Phase C render in NPCs-IN-CONTEXT block with pronoun annotations.
Phase D live-lock on first narration mention.
Phase E anti-drift invariant in HARD STOP RULES.

Run: python3 test_npc_pronoun_lock.py
"""

import sys
import sqlite3
import inspect

sys.path.insert(0, '/home/jordaneal/scripts')

import dnd_engine
from dnd_engine import (
    db_init, create_campaign, init_scene_state,
    npc_upsert, npc_get_by_name, npc_pronouns_set, npc_pronouns_get,
    extract_pronouns_from_text, npc_pronouns_backfill_pass,
    get_recently_active_npcs_detail,
    build_dm_context,
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


def check_in(label, needle, haystack):
    global PASS, FAIL
    if needle in haystack:
        PASS += 1
    else:
        FAIL += 1
        FAILURES.append(f"  {label}: {needle!r} not found in {repr(haystack)[:200]}")


def check_not_in(label, needle, haystack):
    global PASS, FAIL
    if needle not in haystack:
        PASS += 1
    else:
        FAIL += 1
        FAILURES.append(f"  {label}: {needle!r} unexpectedly in {repr(haystack)[:200]}")


# ──────────────────────────────────────────────────────────────────────────────
# Phase A — schema migration
# ──────────────────────────────────────────────────────────────────────────────

db_init()  # idempotent
conn = sqlite3.connect(dnd_engine.DB_PATH)
cols = [r[1] for r in conn.execute("PRAGMA table_info(dnd_npcs)").fetchall()]
conn.close()
check_in('schema: pronouns column on dnd_npcs', 'pronouns', cols)


# ──────────────────────────────────────────────────────────────────────────────
# extract_pronouns_from_text — regex extractor
# ──────────────────────────────────────────────────────────────────────────────

# First-occurrence semantics
canonical, conflicts = extract_pronouns_from_text(
    "She steps forward, her hand on the hilt. They watch from the shadows."
)
check('extract: first-occurrence she wins', canonical, 'she/her')
check_in('extract: conflict detected (they/them also present)',
         'they/them', conflicts)

# Bootstrap-NPC-style prose ("He/him, Gundrik Ironfist, has...")
canonical, _ = extract_pronouns_from_text(
    "He/him, Gundrik Ironfist, has a gruff voice."
)
check('extract: bootstrap-style first sentence', canonical, 'he/him')

# they/them
canonical, _ = extract_pronouns_from_text(
    "They wear a tattered cloak; their boots are worn."
)
check('extract: they/them', canonical, 'they/them')

# Neopronouns
canonical, _ = extract_pronouns_from_text(
    "Xe walks across the room; xyr eyes flash."
)
check('extract: xe/xem neopronouns', canonical, 'xe/xem')

# No pronouns → empty
canonical, _ = extract_pronouns_from_text(
    "A statue carved of jet; the chamber smells of brimstone."
)
check('extract: no pronouns → empty', canonical, '')

# Empty/None input
check('extract: empty string → empty', extract_pronouns_from_text('')[0], '')
check('extract: None input → empty', extract_pronouns_from_text(None)[0], '')


# ──────────────────────────────────────────────────────────────────────────────
# npc_pronouns_set / npc_pronouns_get single-writer
# ──────────────────────────────────────────────────────────────────────────────

# Set up a fresh test NPC
T_GUILD = 'test-guild-s68-n4'
T_CAMP = create_campaign(T_GUILD, 'N-4 Test')
result = npc_upsert(T_CAMP, 'Test Subject', role='guard',
                    description='Stands at attention.', skeleton_origin=False)
check_truthy('writer: NPC inserted', result is not None)
test_npc_id = result[0]

# Initially empty
check('writer: pronouns initially empty', npc_pronouns_get(test_npc_id), '')

# Set
ok = npc_pronouns_set(test_npc_id, 'they/them')
check('writer: set returns True', ok, True)
check('writer: pronouns persisted', npc_pronouns_get(test_npc_id), 'they/them')

# Empty value refused
ok = npc_pronouns_set(test_npc_id, '')
check('writer: empty value refused (returns False)', ok, False)

# Bogus id returns False
check('writer: no-match id returns False',
      npc_pronouns_set(99999999, 'he/him'), False)


# ──────────────────────────────────────────────────────────────────────────────
# Backfill pass — bootstrap-NPC + first-sentence priority
# ──────────────────────────────────────────────────────────────────────────────

# Create a fresh campaign with NPCs whose pronouns are empty
BF_GUILD = 'test-guild-s68-n4-bf'
BF_CAMP = create_campaign(BF_GUILD, 'N-4 Backfill Test')

# Bootstrap-style description (pronoun in first sentence)
npc_upsert(BF_CAMP, 'Brokk Ironfist', role='blacksmith',
           description="He/him, Brokk Ironfist, sets his hammer down. "
                       "Years of sparks have scarred his arms.",
           skeleton_origin=True)
# they/them in first sentence
npc_upsert(BF_CAMP, 'Wren the Quiet', role='thief',
           description="They slip past the guards, their bootsteps muffled. "
                       "A scarred hand brushes the wall.",
           skeleton_origin=True)
# No pronouns in description → stays empty
npc_upsert(BF_CAMP, 'The Statue', role='ancient sentinel',
           description="A statue of dark jet. Eyes carved from onyx.",
           skeleton_origin=False)
# Conflicting pronouns — first-occurrence wins
npc_upsert(BF_CAMP, 'Tova the Healer', role='healer',
           description="She tends the wounded. They say her hands "
                       "are blessed by the gods.",
           skeleton_origin=True)

# Run backfill
stats = npc_pronouns_backfill_pass()
check_truthy('backfill: stats returned', stats is not None)
check_truthy('backfill: scanned non-zero', stats['scanned'] > 0)
check_truthy('backfill: locked non-zero', stats['locked'] > 0)

# Spot-check each NPC
brokk = npc_get_by_name(BF_CAMP, 'Brokk Ironfist')
check('backfill: Brokk (bootstrap-style) → he/him',
      brokk['pronouns'], 'he/him')

wren = npc_get_by_name(BF_CAMP, 'Wren the Quiet')
check('backfill: Wren (they/their in first sentence) → they/them',
      wren['pronouns'], 'they/them')

statue = npc_get_by_name(BF_CAMP, 'The Statue')
check('backfill: Statue (no pronouns) → empty (live-lock candidate)',
      statue['pronouns'], '')

tova = npc_get_by_name(BF_CAMP, 'Tova the Healer')
check('backfill: Tova (conflict, she first) → she/her wins',
      tova['pronouns'], 'she/her')

# Re-running backfill is idempotent (no double-write, no exceptions)
stats2 = npc_pronouns_backfill_pass()
brokk2 = npc_get_by_name(BF_CAMP, 'Brokk Ironfist')
check('backfill: idempotent on re-run (Brokk still he/him)',
      brokk2['pronouns'], 'he/him')


# ──────────────────────────────────────────────────────────────────────────────
# Phase C — render in NPCs-IN-CONTEXT block
# ──────────────────────────────────────────────────────────────────────────────

# get_recently_active_npcs_detail returns name + pronouns dicts
details = get_recently_active_npcs_detail(BF_CAMP, limit=10)
names = [d['name'] for d in details]
check_in('detail: Brokk in list', 'Brokk Ironfist', names)

brokk_detail = next((d for d in details if d['name'] == 'Brokk Ironfist'), None)
check_truthy('detail: Brokk detail entry', brokk_detail is not None)
check('detail: Brokk pronouns annotated',
      brokk_detail['pronouns'], 'he/him')

statue_detail = next((d for d in details if d['name'] == 'The Statue'), None)
check_truthy('detail: Statue detail entry', statue_detail is not None)
check('detail: Statue pronouns empty (not yet locked)',
      statue_detail['pronouns'], '')

# Source-level inspection: build_dm_context renders pronouns inline
build_src = inspect.getsource(build_dm_context)
check_in('render: source uses get_recently_active_npcs_detail',
         'get_recently_active_npcs_detail', build_src)
check_in('render: source renders pronouns in parens',
         "{d['name']} ({d['pronouns']})", build_src)


# ──────────────────────────────────────────────────────────────────────────────
# Phase E — anti-drift invariant in HARD STOP RULES
# ──────────────────────────────────────────────────────────────────────────────

check_in('invariant: HARD STOP rule 7 — NPC PRONOUN LOCK',
         'NPC PRONOUN LOCK', build_src)
check_in('invariant: baker drift scenario named',
         'baker scenario', build_src)
check_in('invariant: locked-pronoun MUST-tone',
         'MUST use ONLY the locked pronouns', build_src)


# ──────────────────────────────────────────────────────────────────────────────
# Phase D — live-lock helper (function presence + dispatch shape)
# ──────────────────────────────────────────────────────────────────────────────

import discord_dnd_bot as bot_mod
check_truthy('live-lock: helper present',
             hasattr(bot_mod, '_lock_npc_pronouns_from_narration'))

# Direct invocation against a freshly upserted NPC with no pronouns
live_camp = create_campaign('test-guild-s68-n4-live', 'N-4 Live-lock Test')
npc_upsert(live_camp, 'Bareface', role='innkeeper',
           description="An innkeeper.",
           skeleton_origin=False)
bare = npc_get_by_name(live_camp, 'Bareface')
check('live-lock: Bareface starts empty', bare['pronouns'], '')

# Simulate narration mentioning Bareface with pronouns near the name
narration = (
    "Bareface looks up as you enter the inn. Her eyes track you to "
    "the bar; her hand stays on a small knife under the counter."
)
npcs_list = [{'name': 'Bareface'}]
locked_count = bot_mod._lock_npc_pronouns_from_narration(
    live_camp, narration, npcs_list
)
check('live-lock: locked 1 NPC', locked_count, 1)
bare_after = npc_get_by_name(live_camp, 'Bareface')
check('live-lock: Bareface now she/her',
      bare_after['pronouns'], 'she/her')

# Second call is idempotent — already locked, no re-write
locked_again = bot_mod._lock_npc_pronouns_from_narration(
    live_camp, narration, npcs_list
)
check('live-lock: re-call skips already-locked (returns 0)',
      locked_again, 0)

# NPC name doesn't appear in narration → no lock
no_appear = bot_mod._lock_npc_pronouns_from_narration(
    live_camp,
    "Someone unnamed walks past.",
    [{'name': 'Bareface'}]
)
check('live-lock: name-not-in-narration → 0 locks',
      no_appear, 0)

# Narration with no pronoun signal near name → no lock
npc_upsert(live_camp, 'Mute Statue', role='guardian',
           description="Stands still.", skeleton_origin=False)
no_pronoun = bot_mod._lock_npc_pronouns_from_narration(
    live_camp,
    "Mute Statue stands by the gate. The crowd murmurs.",
    [{'name': 'Mute Statue'}]
)
check('live-lock: no pronoun near name → 0 locks', no_pronoun, 0)
mute = npc_get_by_name(live_camp, 'Mute Statue')
check('live-lock: Mute Statue still empty', mute['pronouns'], '')


# ──────────────────────────────────────────────────────────────────────────────
# Report
# ──────────────────────────────────────────────────────────────────────────────

print(f"\n{PASS} passed, {FAIL} failed")
if FAILURES:
    print("\nFAILURES:")
    for f in FAILURES:
        print(f)
    sys.exit(1)
sys.exit(0)
