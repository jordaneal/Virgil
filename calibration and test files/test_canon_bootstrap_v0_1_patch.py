"""N-10 v0.1 — Canon Bootstrap Bot post-ship patch verify.

Three same-session live-verify patches from operator playtest evidence
(post-N-10 ship, 2026-05-14T15:51 Grahn scenario):

  Fix 1: Per-card-type field-key normalization in `/bootstrap manual`
  Fix 2: Prose-residual warning on name-class overrides
  Fix 3: Reroll directive archetype-diversity hint

Test sections:
  (1) _normalize_bootstrap_field_key — unit tests per card type
  (2) Manual override end-to-end (Grahn reproduction) — commits use
      canonical_name='Grahn', not LLM's untouched draft
  (3) Prose-residual warning fires only on name-class overrides
  (4) Reroll archetype-diversity hint extraction + injection

Run: python3 test_canon_bootstrap_v0_1_patch.py
"""

import sys
import shutil
sys.path.insert(0, '/home/jordaneal/scripts')

import dnd_engine
import dnd_orchestration as orch
import discord_dnd_bot as bot_mod
import skeleton_writer


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
# (1) _normalize_bootstrap_field_key — per card type alias mapping
# ──────────────────────────────────────────────────────────────────────────────

# NPC card: name → canonical_name; canonical_name stays
check('alias: npc name→canonical_name',
      bot_mod._normalize_bootstrap_field_key('npc_dispatcher', 'name'),
      'canonical_name')
check('alias: npc canonical_name passthrough',
      bot_mod._normalize_bootstrap_field_key('npc_dispatcher', 'canonical_name'),
      'canonical_name')
# Non-name keys pass through unchanged
check('alias: npc role passthrough',
      bot_mod._normalize_bootstrap_field_key('npc_dispatcher', 'role'),
      'role')
check('alias: npc pronouns passthrough',
      bot_mod._normalize_bootstrap_field_key('npc_dispatcher', 'pronouns'),
      'pronouns')

# Quest card: name → title; title stays
check('alias: quest name→title',
      bot_mod._normalize_bootstrap_field_key('quest', 'name'),
      'title')
check('alias: quest title passthrough',
      bot_mod._normalize_bootstrap_field_key('quest', 'title'),
      'title')
check('alias: quest summary passthrough',
      bot_mod._normalize_bootstrap_field_key('quest', 'summary'),
      'summary')

# Quest_act: name + title both → act_title
check('alias: quest_act name→act_title',
      bot_mod._normalize_bootstrap_field_key('quest_act', 'name'),
      'act_title')
check('alias: quest_act title→act_title',
      bot_mod._normalize_bootstrap_field_key('quest_act', 'title'),
      'act_title')
check('alias: quest_act act_title passthrough',
      bot_mod._normalize_bootstrap_field_key('quest_act', 'act_title'),
      'act_title')

# Location card: name → canonical_name
check('alias: location name→canonical_name',
      bot_mod._normalize_bootstrap_field_key('location', 'name'),
      'canonical_name')

# Faction card: name unchanged (faction uses 'name' canonically)
check('alias: faction name passthrough',
      bot_mod._normalize_bootstrap_field_key('faction', 'name'),
      'name')

# Unknown card_type passes through
check('alias: unknown card_type passthrough',
      bot_mod._normalize_bootstrap_field_key('mystery_type', 'name'),
      'name')


# ──────────────────────────────────────────────────────────────────────────────
# (2) Manual override end-to-end — Grahn scenario reproduction
# Bot proposes 'Gundrik Ironfist'; operator overrides name:'Grahn';
# `/bootstrap accept` commits canonical_name='Grahn' (NOT 'Gundrik Ironfist')
# ──────────────────────────────────────────────────────────────────────────────

GRAHN_GUILD = 'test-guild-n10-v01-grahn'
GRAHN_CAMP = dnd_engine.create_campaign(GRAHN_GUILD, 'Grahn Reproduction')
dnd_engine.init_scene_state(GRAHN_CAMP)
dnd_engine.update_campaign_premise(GRAHN_CAMP, 'Test premise for Grahn scenario.')

# Simulate session state with the Gundrik draft active as current_proposal
state = bot_mod.BootstrapState(
    campaign_id=GRAHN_CAMP,
    premise='Test premise for Grahn scenario.',
    sequence_pointer=1,  # second card slot = first npc_dispatcher per V0 sequence
    current_card_type='npc_dispatcher',
    current_proposal={
        'card_type': 'npc_dispatcher',
        'fields': {
            'canonical_name': 'Gundrik Ironfist',
            'role': "Miner's Union Rep",
            'pronouns': 'he/him',
            'description': "He/him, Gundrik Ironfist, has a gruff voice.",
            'associated_faction_name': None,
        },
        'justification': 'Gundrik fits the premise.',
    },
)
# Stash in module-level session dict so _commit_proposal has access via state
bot_mod._bootstrap_session[GRAHN_CAMP] = state

# Simulate operator running `/bootstrap manual name:"Grahn"` — apply override
# using the same normalization logic the slash handler uses
import re as _re
parsed = _re.findall(r'(\w+)\s*:\s*(?:"([^"]*)"|(\S+))', 'name:"Grahn"')
applied_keys = []
for key, quoted, unquoted in parsed:
    val = quoted if quoted else unquoted
    normalized_key = bot_mod._normalize_bootstrap_field_key(
        state.current_card_type, key
    )
    state.current_proposal['fields'][normalized_key] = val
    applied_keys.append(normalized_key)

check('e2e: override normalized to canonical_name', applied_keys, ['canonical_name'])
check('e2e: fields.canonical_name = Grahn',
      state.current_proposal['fields']['canonical_name'], 'Grahn')

# Now run _commit_proposal (the real one from discord_dnd_bot)
fake_campaign = {'id': GRAHN_CAMP, 'name': 'Grahn Reproduction'}
ok, msg = bot_mod._commit_proposal(state, fake_campaign)
check_truthy('e2e: commit succeeds', ok)

# Verify DB has canonical_name='Grahn'
import sqlite3 as _sq
conn = _sq.connect(dnd_engine.DB_PATH)
row = conn.execute(
    "SELECT canonical_name FROM dnd_npcs WHERE campaign_id=? AND skeleton_origin=1 "
    "ORDER BY id DESC LIMIT 1",
    (GRAHN_CAMP,)
).fetchone()
conn.close()
check_truthy('e2e: DB row created', row is not None)
check('e2e: DB canonical_name = Grahn (override took effect)',
      row[0], 'Grahn')
# Critically: NOT 'Gundrik Ironfist'
check_not_in('e2e: DB canonical_name is NOT Gundrik Ironfist',
             'Gundrik', row[0])

# Clean up session
bot_mod._bootstrap_session.pop(GRAHN_CAMP, None)


# ──────────────────────────────────────────────────────────────────────────────
# (3) Prose-residual warning detection — fires on name-class, not others
# ──────────────────────────────────────────────────────────────────────────────

# Confirm NAME_CLASS_CANONICAL map is correctly populated per card type
nc = bot_mod._BOOTSTRAP_NAME_CLASS_CANONICAL
check('warn-map: faction name-class', nc.get('faction'), {'name'})
check('warn-map: npc canonical_name-class',
      nc.get('npc_dispatcher'), {'canonical_name'})
check('warn-map: location canonical_name-class',
      nc.get('location'), {'canonical_name'})
check('warn-map: quest title-class', nc.get('quest'), {'title'})
check('warn-map: quest_act act_title-class',
      nc.get('quest_act'), {'act_title'})

# Simulate override-key flow per card type and check whether warning would fire
def _would_warn(card_type, operator_key):
    name_class = bot_mod._BOOTSTRAP_NAME_CLASS_CANONICAL.get(card_type, set())
    normalized = bot_mod._normalize_bootstrap_field_key(card_type, operator_key)
    return normalized in name_class

# Name overrides on each card type → warn
check_truthy('warn: NPC name override warns',
             _would_warn('npc_dispatcher', 'name'))
check_truthy('warn: NPC canonical_name override warns',
             _would_warn('npc_dispatcher', 'canonical_name'))
check_truthy('warn: quest title override warns', _would_warn('quest', 'title'))
check_truthy('warn: quest name (aliased to title) warns',
             _would_warn('quest', 'name'))
check_truthy('warn: faction name override warns',
             _would_warn('faction', 'name'))
check_truthy('warn: location name override warns',
             _would_warn('location', 'name'))
check_truthy('warn: quest_act act_title override warns',
             _would_warn('quest_act', 'act_title'))

# Non-name overrides → no warn
check('warn: NPC role override does NOT warn',
      _would_warn('npc_dispatcher', 'role'), False)
check('warn: NPC pronouns override does NOT warn',
      _would_warn('npc_dispatcher', 'pronouns'), False)
check('warn: quest summary override does NOT warn',
      _would_warn('quest', 'summary'), False)
check('warn: quest reward_summary override does NOT warn',
      _would_warn('quest', 'reward_summary'), False)
check('warn: faction goal override does NOT warn',
      _would_warn('faction', 'goal'), False)
check('warn: location type override does NOT warn',
      _would_warn('location', 'type'), False)
check('warn: quest_act act_description override does NOT warn',
      _would_warn('quest_act', 'act_description'), False)


# ──────────────────────────────────────────────────────────────────────────────
# (4) Reroll archetype-diversity hint — extraction + prompt injection
# ──────────────────────────────────────────────────────────────────────────────

# NPC archetype extraction
hint = orch._extract_prior_archetype_hint(
    {'fields': {'role': "Miner's Union Rep", 'canonical_name': 'Gundrik Ironfist'}},
    'npc_dispatcher'
)
check_truthy('hint: NPC archetype hint non-empty', bool(hint))
check_in("hint: NPC role surfaces", "Miner's Union Rep", hint)
check_in('hint: NPC prior-name surfaces', 'Gundrik Ironfist', hint)
check_in('hint: NPC asks for different archetype',
         'DIFFERENT archetype', hint)
check_in('hint: NPC mentions cultural origin/species',
         'cultural', hint)

# Faction archetype extraction
hint = orch._extract_prior_archetype_hint(
    {'fields': {'name': "Miner's Union", 'type': 'union'}}, 'faction'
)
check_truthy('hint: faction hint non-empty', bool(hint))
check_in('hint: faction type surfaces', 'union', hint)

# Quest archetype extraction
hint = orch._extract_prior_archetype_hint(
    {'fields': {'title': 'Investigate Mine Collapse'}}, 'quest'
)
check_truthy('hint: quest hint non-empty', bool(hint))
check_in('hint: quest verb-shape framing', 'verb', hint)

# Quest_act archetype extraction
hint = orch._extract_prior_archetype_hint(
    {'fields': {'act_title': 'Approach the mine'}}, 'quest_act'
)
check_truthy('hint: quest_act hint non-empty', bool(hint))
check_in('hint: quest_act mentions mode shift', 'beat', hint)

# Location archetype extraction
hint = orch._extract_prior_archetype_hint(
    {'fields': {'type': 'town', 'canonical_name': 'Stonehold'}}, 'location'
)
check_truthy('hint: location hint non-empty', bool(hint))
check_in('hint: location type surfaces', 'town', hint)

# No prior proposal → empty hint
check('hint: None prior proposal → empty',
      orch._extract_prior_archetype_hint(None, 'npc_dispatcher'), '')

# Empty fields → empty hint
check('hint: empty fields → empty',
      orch._extract_prior_archetype_hint({'fields': {}}, 'npc_dispatcher'), '')


# Verify hint flows into the directive prompt via compute_bootstrap_card_directive
# by stubbing the LLM router and inspecting the prompt sent.
import cloud_router
_original_route = cloud_router.route
_captured_prompts = []


def _capture_route(messages, task_type, system_prompt=None):
    _captured_prompts.append({'messages': messages, 'task_type': task_type,
                                'system_prompt': system_prompt})
    return '{"canonical_name": "RerollName", "role": "different role", '\
           '"pronouns": "they/them", "description": "they/them, a stub.", '\
           '"justification": "stub."}', 'fake'


cloud_router.route = _capture_route

# Case A: no reroll (no prior_proposal) → no archetype hint in prompt
state_dict = {'premise': 'Test premise', 'sequence_pointer': 1,
              'approved_elements': []}
prop, sig = orch.compute_bootstrap_card_directive(
    state_dict, 'npc_dispatcher', {'id': 1}, '', None)
check_truthy('integration: card returned', prop is not None)
check('integration: prior_archetype_hint signal falsy on first attempt',
      bool(sig.get('prior_archetype_hint')), False)
# Confirm REROLL HINT block not in prompt
first_prompt = _captured_prompts[-1]['messages'][0]['content']
check_not_in('integration: first-attempt prompt has no REROLL HINT block',
             '=== REROLL HINT ===', first_prompt)

# Case B: reroll (prior_proposal supplied) → archetype hint in prompt
prior = {
    'card_type': 'npc_dispatcher',
    'fields': {'canonical_name': 'Gundrik Ironfist',
               'role': "Miner's Union Rep",
               'pronouns': 'he/him',
               'description': '...'},
}
state_dict_reroll = {
    'premise': 'Test premise', 'sequence_pointer': 1,
    'approved_elements': [], 'rerolls_for_current': 1,
}
prop, sig = orch.compute_bootstrap_card_directive(
    state_dict_reroll, 'npc_dispatcher', {'id': 1},
    'Reroll number 1', prior)
check_truthy('integration: reroll card returned', prop is not None)
check('integration: prior_archetype_hint signal True on reroll',
      sig.get('prior_archetype_hint'), True)
reroll_prompt = _captured_prompts[-1]['messages'][0]['content']
check_in('integration: reroll prompt has REROLL HINT block',
         '=== REROLL HINT ===', reroll_prompt)
check_in('integration: reroll prompt contains archetype-diversity wording',
         'DIFFERENT archetype', reroll_prompt)
check_in('integration: reroll prompt cites prior role',
         "Miner's Union Rep", reroll_prompt)
check_in('integration: reroll prompt cites prior name',
         'Gundrik Ironfist', reroll_prompt)

# Telemetry: bootstrap_card_log_summary surfaces prior_archetype_hint
log_line = orch.bootstrap_card_log_summary(sig)
check_in('telemetry: log surfaces prior_archetype_hint=1',
         'prior_archetype_hint=1', log_line)

# Restore router
cloud_router.route = _original_route


# ──────────────────────────────────────────────────────────────────────────────
# Cleanup + report
# ──────────────────────────────────────────────────────────────────────────────

# Clean up Grahn test campaign's skeleton dir if present (avoid pollution)
sk_dir = skeleton_writer.SKELETON_ROOT / str(GRAHN_CAMP)
if sk_dir.exists():
    shutil.rmtree(sk_dir, ignore_errors=True)

print(f"\n{PASS} passed, {FAIL} failed")
if FAILURES:
    print("\nFAILURES:")
    for f in FAILURES:
        print(f)
    sys.exit(1)
sys.exit(0)
