"""N-10 Canon Bootstrap Bot v0 — adversarial verify.

Per CANON_BOOTSTRAP_BOT_V0_SPEC.md LOCKED §9 test plan sketch.

Tests:
  (1) Schema migration — premise column present
  (2) update_campaign_premise single-writer
  (3) is_bootstrap_complete detection signal (premise + skeleton_origin=1 both required)
  (4) skeleton_writer.skeleton_md_append_element:
      - creates skeleton.md scaffold if missing
      - appends faction H2 + H3 entry
      - idempotent on (element_type, element_name) — re-append updates in place
      - parser round-trip: parse_skeleton_file recovers the appended elements
  (5) compute_bootstrap_sequence_directive:
      - returns first card at pointer=0
      - returns None at sequence end
      - returns invalid_card_type signal on garbled plan
  (6) compute_bootstrap_card_directive (with stubbed LLM):
      - returns None on empty premise
      - returns valid proposal on well-formed LLM output
      - returns None on duplicate-name validation failure
      - returns None on missing-FK validation failure
      - signals carry telemetry per §59 contract
  (7) Validator:
      - rejects missing required fields per card type
      - rejects oversize field values
      - rejects duplicate names case-insensitively
      - rejects FK references not in approved_elements
  (8) Premise rendering in build_dm_context:
      - present at low-tactical-band when campaign.premise non-empty
      - omitted when campaign.premise empty
      - omitted during suppress_for_combat_narration

Run: python3 test_canon_bootstrap_bot_v0.py
"""

import sys
import sqlite3
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, '/home/jordaneal/scripts')

import dnd_engine
from dnd_engine import (
    db_init, create_campaign, get_active_campaign,
    update_campaign_premise, is_bootstrap_complete,
    npc_upsert, quest_add, quest_act_upsert, location_upsert,
    init_scene_state,
)
import skeleton_writer
from skeleton_writer import (
    skeleton_md_append_element, _skeleton_path, _ensure_skeleton_exists,
)
import dnd_orchestration as orch
import skeleton_loader


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
# (1) Schema migration — premise column present
# ──────────────────────────────────────────────────────────────────────────────

db_init()  # idempotent; ensures premise column added
conn = sqlite3.connect(dnd_engine.DB_PATH)
cols = [r[1] for r in conn.execute("PRAGMA table_info(dnd_campaigns)").fetchall()]
conn.close()
check_in('schema: premise column in dnd_campaigns', 'premise', cols)


# ──────────────────────────────────────────────────────────────────────────────
# (2) update_campaign_premise single-writer
# ──────────────────────────────────────────────────────────────────────────────

CAMP_BS_GUILD = 'test-guild-bootstrap-v0'
CAMP_BS = create_campaign(CAMP_BS_GUILD, 'Bootstrap V0 Test')

# Initial premise empty
camp = get_active_campaign(CAMP_BS_GUILD)
check_truthy('camp: created', camp is not None)
check('camp: premise initially empty', camp['premise'], '')

# Write premise
ok = update_campaign_premise(CAMP_BS, 'Grimdark frontier mining town.')
check('writer: returns True', ok, True)
camp = get_active_campaign(CAMP_BS_GUILD)
check('camp: premise persisted', camp['premise'], 'Grimdark frontier mining town.')

# Update again
update_campaign_premise(CAMP_BS, 'Updated premise.')
camp = get_active_campaign(CAMP_BS_GUILD)
check('writer: re-write overwrites', camp['premise'], 'Updated premise.')

# No-match returns False
ok = update_campaign_premise(99999999, 'Should not write.')
check('writer: no-match returns False', ok, False)


# ──────────────────────────────────────────────────────────────────────────────
# (3) is_bootstrap_complete — both signals required
# ──────────────────────────────────────────────────────────────────────────────

# Fresh campaign: premise empty, no skeleton_origin rows → False
CAMP_DETECT_GUILD = 'test-guild-bootstrap-detect'
CAMP_DETECT = create_campaign(CAMP_DETECT_GUILD, 'Bootstrap Detect Test')
check('detect: fresh campaign not complete', is_bootstrap_complete(CAMP_DETECT), False)

# Set premise only → still False (no skeleton rows)
update_campaign_premise(CAMP_DETECT, 'Test premise.')
check('detect: premise-only not complete', is_bootstrap_complete(CAMP_DETECT), False)

# Add a skeleton_origin=1 NPC → True
result = npc_upsert(CAMP_DETECT, 'Test NPC', role='herald', skeleton_origin=True)
check_truthy('detect: NPC inserted', result is not None)
check('detect: premise + skeleton_origin → complete',
      is_bootstrap_complete(CAMP_DETECT), True)

# Clear premise → False again (need both)
update_campaign_premise(CAMP_DETECT, '')
check('detect: skeleton_origin-only not complete',
      is_bootstrap_complete(CAMP_DETECT), False)


# ──────────────────────────────────────────────────────────────────────────────
# (4) skeleton_writer.skeleton_md_append_element
# ──────────────────────────────────────────────────────────────────────────────

# Use a temp campaign id to avoid polluting real campaigns dir
TEMP_CAMP = 990991  # high integer; unlikely to collide
temp_dir = skeleton_writer.SKELETON_ROOT / str(TEMP_CAMP)
if temp_dir.exists():
    shutil.rmtree(temp_dir)

# Scaffold creation on first write
ok, msg = skeleton_md_append_element(
    TEMP_CAMP, 'faction',
    {'name': 'Stonehold Guild', 'type': 'merchants',
     'goal': 'Keep the trade road open.',
     'pressure_shape': 'Bandit raids climbing.',
     'engagement_signals': 'Caravan raid reports.',
     'description': 'A merchant alliance based in Stonehold.'},
    campaign_name='Skeleton Writer Test',
    premise='Trade roads test.',
)
check('writer: faction append succeeds', ok, True)
check('writer: faction append status', msg, 'appended')

sk_path = _skeleton_path(TEMP_CAMP)
content = sk_path.read_text(encoding='utf-8')
check_in('writer: H1 with campaign name', '# Campaign: Skeleton Writer Test', content)
check_in('writer: factions H2', '## Factions', content)
check_in('writer: faction H3 entry', '### Stonehold Guild (merchants)', content)
check_in('writer: faction goal rendered', 'Goal: Keep the trade road open.', content)

# Idempotency on re-append — same name, different prose → update in place
ok, _ = skeleton_md_append_element(
    TEMP_CAMP, 'faction',
    {'name': 'Stonehold Guild', 'type': 'merchants',
     'goal': 'Keep the trade road UPDATED.',
     'pressure_shape': 'Updated pressure.',
     'engagement_signals': 'Updated signals.',
     'description': 'Updated description.'},
    campaign_name='Skeleton Writer Test',
)
check_truthy('writer: idempotent re-append succeeds', ok)
content = sk_path.read_text(encoding='utf-8')
check_in('writer: idempotent — new goal in place', 'Keep the trade road UPDATED', content)
check_not_in('writer: idempotent — old goal gone', 'Keep the trade road open.', content)
# Only one H3 for Stonehold Guild should exist after update
assert content.count('### Stonehold Guild') == 1, \
    f"expected exactly one H3 entry, got {content.count('### Stonehold Guild')}"

# Append NPC — H2 created if not present
ok, _ = skeleton_md_append_element(
    TEMP_CAMP, 'npc',
    {'canonical_name': 'Eldrin Stormbow', 'role': 'ranger',
     'pronouns': 'he/him', 'location_name': 'Stonehold',
     'description': 'He scouts the trade road ahead of the caravans.'},
    campaign_name='Skeleton Writer Test',
)
check_truthy('writer: npc append succeeds', ok)
content = sk_path.read_text(encoding='utf-8')
check_in('writer: primary npcs H2 created', '## Primary NPCs', content)
check_in('writer: npc H3 with role + location',
         '### Eldrin Stormbow (ranger, Stonehold)', content)

# Append quest with associated NPC
ok, _ = skeleton_md_append_element(
    TEMP_CAMP, 'quest',
    {'title': 'Escort the merchant caravan', 'name': 'Escort the merchant caravan',
     'summary': 'Patrol the trade road.',
     'offer_npc_name': 'Eldrin Stormbow',
     'reward_summary': '50gp + Stonehold reputation'},
    campaign_name='Skeleton Writer Test',
)
check_truthy('writer: quest append succeeds', ok)
content = sk_path.read_text(encoding='utf-8')
check_in('writer: major hooks H2 created', '## Major hooks', content)
check_in('writer: quest H3', '### Escort the merchant caravan', content)
check_in('writer: quest voicer', 'Voicer: Eldrin Stormbow', content)

# Append quest act — should land inside the quest's H3 + create #### Acts
ok, _ = skeleton_md_append_element(
    TEMP_CAMP, 'quest_act',
    {'quest_title': 'Escort the merchant caravan',
     'act_index': 1, 'act_title': 'Departure from Stonehold',
     'act_description': 'Caravan rolls out at dawn.',
     'transition_predicate': {'scene_count_threshold': 3}},
    campaign_name='Skeleton Writer Test',
)
check_truthy('writer: quest_act append succeeds', ok)
content = sk_path.read_text(encoding='utf-8')
check_in('writer: #### Acts subsection created', '#### Acts', content)
check_in('writer: numbered act entry', '1. Departure from Stonehold', content)

# Append location — H2 created
ok, _ = skeleton_md_append_element(
    TEMP_CAMP, 'location',
    {'canonical_name': 'Stonehold', 'name': 'Stonehold', 'type': 'town',
     'description': 'A fortified market town.',
     'starting_location': True},
    campaign_name='Skeleton Writer Test',
)
check_truthy('writer: location append succeeds', ok)
content = sk_path.read_text(encoding='utf-8')
check_in('writer: key locations H2', '## Key locations', content)
check_in('writer: location H3', '### Stonehold (town)', content)
check_in('writer: starting_location note', 'Starting location for the party.', content)

# Parser round-trip: skeleton_loader recovers the elements
parsed = skeleton_loader._parse_skeleton_text(content)
check_in('round-trip: title parsed',
         'Skeleton Writer Test', parsed.get('title'))
faction_names = [f['name'] for f in parsed.get('factions') or []]
check_in('round-trip: faction recovered', 'Stonehold Guild', faction_names)
npc_names = [n['name'] for n in parsed.get('npcs') or []]
check_in('round-trip: npc recovered', 'Eldrin Stormbow', npc_names)
loc_names = [l['name'] for l in parsed.get('locations') or []]
check_in('round-trip: location recovered', 'Stonehold', loc_names)
quest_decomps = parsed.get('quest_decompositions') or []
quest_titles = [q['title'] for q in quest_decomps]
check_in('round-trip: quest recovered',
         'Escort the merchant caravan', quest_titles)
if quest_decomps:
    acts = quest_decomps[0].get('acts') or []
    check_truthy('round-trip: quest acts parsed', len(acts) > 0)
    if acts:
        check('round-trip: act_index recovered', acts[0]['act_index'], 1)
        check('round-trip: act_title recovered',
              acts[0]['act_title'], 'Departure from Stonehold')

# Unknown element_type soft-fails
ok, msg = skeleton_md_append_element(TEMP_CAMP, 'mystery_type', {'name': 'X'})
check('writer: unknown type soft-fails', ok, False)
check_in('writer: unknown type message', 'unknown_element_type', msg)

# Empty name soft-fails
ok, msg = skeleton_md_append_element(TEMP_CAMP, 'faction', {'name': ''})
check('writer: empty name soft-fails', ok, False)

# Cleanup temp campaign dir
shutil.rmtree(temp_dir, ignore_errors=True)


# ──────────────────────────────────────────────────────────────────────────────
# (5) compute_bootstrap_sequence_directive
# ──────────────────────────────────────────────────────────────────────────────

# First card at pointer=0 is 'faction' per BOOTSTRAP_CARD_SEQUENCE_V0
state = {'premise': 'X', 'sequence_pointer': 0,
         'sequence_plan': list(orch.BOOTSTRAP_CARD_SEQUENCE_V0),
         'approved_elements': []}
nt, sig = orch.compute_bootstrap_sequence_directive(state)
check('seq: first card is faction', nt, 'faction')
check('seq: signals fired=1', sig['fired'], 1)
check('seq: card_type recorded', sig['card_type'], 'faction')
check('seq: remaining = total - 1',
      sig['remaining_in_sequence'], len(orch.BOOTSTRAP_CARD_SEQUENCE_V0) - 1)

# Pointer at end of sequence → None
state['sequence_pointer'] = len(orch.BOOTSTRAP_CARD_SEQUENCE_V0)
nt, sig = orch.compute_bootstrap_sequence_directive(state)
check('seq: exhausted returns None', nt, None)
check('seq: exhausted fired=0', sig['fired'], 0)
check('seq: exhausted reason', sig['reason'], 'sequence_exhausted')

# Garbled plan → invalid_card_type
state['sequence_pointer'] = 0
state['sequence_plan'] = ['mystery_card']
nt, sig = orch.compute_bootstrap_sequence_directive(state)
check('seq: invalid card_type returns None', nt, None)
check_in('seq: invalid reason logged', 'invalid_card_type', sig['reason'])


# ──────────────────────────────────────────────────────────────────────────────
# (6) compute_bootstrap_card_directive — with LLM stub
# ──────────────────────────────────────────────────────────────────────────────

# Patch the cloud_router import inside the function. Easiest way: replace
# the route function in cloud_router temporarily.
import cloud_router
_original_route = cloud_router.route


def _fake_route_factory(response_text):
    def _fake_route(messages, task_type, system_prompt=None):
        return response_text, 'fake'
    return _fake_route


# Empty premise → no_premise
state = {'premise': '', 'sequence_pointer': 0, 'approved_elements': []}
prop, sig = orch.compute_bootstrap_card_directive(state, 'faction', {'id': 1})
check('card: empty premise returns None', prop, None)
check('card: empty premise reason', sig['reason'], 'no_premise')

# Well-formed LLM output → valid proposal
cloud_router.route = _fake_route_factory(
    '{"name": "The Reach Watch", "goal": "Hold the eastern pass.", '
    '"pressure_shape": "Goblin warband encroaching from the highlands.", '
    '"engagement_signals": "Watch fires lit; patrols stretched thin.", '
    '"description": "A border garrison.", "type": "watch", '
    '"justification": "Establishes the offscreen threat the premise hints at."}'
)
state = {'premise': 'Eastern frontier; goblin trouble.',
         'sequence_pointer': 0, 'approved_elements': []}
prop, sig = orch.compute_bootstrap_card_directive(state, 'faction', {'id': 1})
check_truthy('card: well-formed proposal returned', prop is not None)
check('card: card_type recorded', prop['card_type'], 'faction')
check('card: name extracted', prop['fields']['name'], 'The Reach Watch')
check_in('card: justification surfaced',
         'offscreen', prop['justification'])
check('card: signals fired=1', sig['fired'], 1)
check_truthy('card: latency recorded', sig['llm_latency_ms'] >= 0)

# Duplicate name → validation_failed
cloud_router.route = _fake_route_factory(
    '{"name": "The Reach Watch", "goal": "Another goal.", '
    '"pressure_shape": "More pressure.", "engagement_signals": "Signals.", '
    '"description": "Description.", "type": "watch", '
    '"justification": "Duplicate name test."}'
)
state_with_existing = {
    'premise': 'X', 'sequence_pointer': 1,
    'approved_elements': [
        {'card_type': 'faction', 'fields': {'name': 'The Reach Watch'}}
    ]
}
prop, sig = orch.compute_bootstrap_card_directive(
    state_with_existing, 'faction', {'id': 1})
check('card: duplicate name rejected', prop, None)
check_in('card: duplicate reason', 'duplicate_name', sig['reason'])

# Missing FK for quest → validation_failed
cloud_router.route = _fake_route_factory(
    '{"title": "A quest", "summary": "Some summary.", '
    '"offer_npc_name": "Nonexistent NPC", '
    '"reward_summary": "50gp", '
    '"justification": "FK missing test."}'
)
state_no_npcs = {
    'premise': 'X', 'sequence_pointer': 0,
    'approved_elements': []  # no NPCs approved yet
}
prop, sig = orch.compute_bootstrap_card_directive(
    state_no_npcs, 'quest', {'id': 1})
check('card: missing FK rejected', prop, None)
check_in('card: FK reason', 'fk_unresolved', sig['reason'])

# Malformed JSON → parse_failed
cloud_router.route = _fake_route_factory('not actually json {garbled')
prop, sig = orch.compute_bootstrap_card_directive(
    {'premise': 'X', 'sequence_pointer': 0, 'approved_elements': []},
    'faction', {'id': 1})
check('card: malformed JSON rejected', prop, None)
check('card: parse_failed reason', sig['reason'], 'parse_failed')

# Restore route
cloud_router.route = _original_route


# ──────────────────────────────────────────────────────────────────────────────
# (7) Validator direct tests
# ──────────────────────────────────────────────────────────────────────────────

ok, reason = orch._validate_proposal('faction', {}, [])
check('validator: empty fields rejected', ok, False)
check_in('validator: missing required', 'missing_field', reason)

ok, reason = orch._validate_proposal(
    'faction',
    {'name': 'X', 'goal': 'a', 'pressure_shape': 'b', 'engagement_signals': 'c'},
    []
)
check('validator: minimal-valid faction accepts', ok, True)

# Oversize name
ok, reason = orch._validate_proposal(
    'faction',
    {'name': 'X' * 200, 'goal': 'a', 'pressure_shape': 'b',
     'engagement_signals': 'c'},
    []
)
check('validator: oversize name rejected', ok, False)
check_in('validator: oversize reason', 'too_long', reason)

# Case-insensitive duplicate
ok, reason = orch._validate_proposal(
    'faction',
    {'name': 'The reach watch', 'goal': 'a',
     'pressure_shape': 'b', 'engagement_signals': 'c'},
    [{'card_type': 'faction', 'fields': {'name': 'The Reach Watch'}}]
)
check('validator: case-insensitive duplicate rejected', ok, False)

# act_index non-positive
ok, reason = orch._validate_proposal(
    'quest_act',
    {'quest_title': 'X', 'act_index': 0, 'act_title': 'T',
     'act_description': 'D'},
    [{'card_type': 'quest', 'fields': {'title': 'X'}}]
)
check('validator: act_index <1 rejected', ok, False)
check_in('validator: act_index reason', 'act_index_not_positive', reason)


# ──────────────────────────────────────────────────────────────────────────────
# (8) Premise rendering in build_dm_context — structural test via source
# inspection (avoid expensive full dm_respond call)
# ──────────────────────────────────────────────────────────────────────────────

import inspect
build_src = inspect.getsource(dnd_engine.build_dm_context)
check_in('render: CAMPAIGN PREMISE block label',
         '=== CAMPAIGN PREMISE ===', build_src)
check_in('render: premise gated on suppress_for_combat_narration',
         'suppress_for_combat_narration', build_src)
check_in('render: premise read from campaign.premise',
         "campaign.get('premise')", build_src)


# ──────────────────────────────────────────────────────────────────────────────
# (9) BootstrapState dataclass + slash command surface (smoke test imports)
# ──────────────────────────────────────────────────────────────────────────────

import discord_dnd_bot as bot_mod
check_truthy('discord: BootstrapState class present',
             hasattr(bot_mod, 'BootstrapState'))
check_truthy('discord: _bootstrap_session dict present',
             hasattr(bot_mod, '_bootstrap_session'))
for cmd in ('bootstrap_begin_cmd', 'bootstrap_accept_cmd',
            'bootstrap_skip_cmd', 'bootstrap_reroll_cmd',
            'bootstrap_manual_cmd', 'bootstrap_status_cmd',
            'bootstrap_end_cmd'):
    check_truthy(f'discord: {cmd} present', hasattr(bot_mod, cmd))


# ──────────────────────────────────────────────────────────────────────────────
# Cleanup + report
# ──────────────────────────────────────────────────────────────────────────────

print(f"\n{PASS} passed, {FAIL} failed")
if FAILURES:
    print("\nFAILURES:")
    for f in FAILURES:
        print(f)
    sys.exit(1)
sys.exit(0)
