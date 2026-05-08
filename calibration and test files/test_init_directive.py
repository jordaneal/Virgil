"""Deterministic unit and integration tests for compute_init_directive (Session 20).

Combat Initiation Orchestration v1, Shape B — LLM-emits via directive.
Covers the three-gate detection logic, target-hint rendering, B2.1 narration
mandate preservation, prompt composition, telemetry, cross-campaign isolation,
and the reactive mode-flip loop closure.

Run:
    cd /home/jordaneal/scripts && python3 test_init_directive.py
"""

import os
import re
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
dnd_engine.route = lambda messages, task_type, system_prompt: ("Narrated response.", "mock")
dnd_engine.db_init()

from dnd_engine import (
    create_campaign, bind_character, init_scene_state,
    get_active_campaign, get_characters, dm_respond,
    npc_upsert, set_scene_mode, set_active_turn, clear_active_turn,
    get_active_turn,
)

import dnd_orchestration as orch
from dnd_orchestration import (
    compute_init_directive,
    init_log_summary,
    _render_target_hint_block,
    _INIT_TARGET_HINT_CAP,
    INTENT_COMBAT,
    INTENT_SOCIAL,
    INTENT_TRIVIAL,
    INTENT_EXPLORATION,
    INTENT_RISKY,
    INTENT_CONTESTED,
)

try:
    import dm_philosophy_loader as _phil
    _phil.get_philosophy_block = lambda: ''
except Exception:
    pass

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


def call(intent_current=INTENT_COMBAT, mode='exploration',
         has_active_turn=False, target_hints=('Garrick',)):
    return compute_init_directive(
        intent_current=intent_current,
        mode=mode,
        has_active_turn=has_active_turn,
        target_hints=list(target_hints),
    )


GUILD_COUNTER = [0]


def make_campaign(name='Init Test', mode='exploration'):
    GUILD_COUNTER[0] += 1
    guild = f'guild-init-{GUILD_COUNTER[0]}'
    cid = create_campaign(guild, name)
    init_scene_state(cid, 'A test scene.')
    if mode != 'exploration':
        set_scene_mode(cid, mode)
    return guild, cid


def get_camp_chars(guild, cid):
    campaign = get_active_campaign(guild)
    chars = get_characters(cid)
    return campaign, chars


# ─────────────────────────────────────────────────────────────────────────────
# §8.1 — Positive case: all three gates pass → directive fires
# ─────────────────────────────────────────────────────────────────────────────

body, sig = call()
check_truthy('positive: fired=1 in signals', sig['fired'])
check_truthy('positive: body non-empty', bool(body))
check('positive: intent_current recorded', sig['intent_current'], INTENT_COMBAT)
check('positive: mode recorded', sig['mode'], 'exploration')
check('positive: has_active_turn=0', sig['has_active_turn'], 0)
check('positive: target_hint_count=1', sig['target_hint_count'], 1)

# Three-command sequence present and ordered correctly
check_truthy('positive: body contains !init begin', '!init begin' in body)
check_truthy('positive: body contains !init add',   '!init add' in body)
check_truthy('positive: body contains !attack',     '!attack' in body)
# Order: !init begin must come before !init add, which must come before !attack
idx_begin = body.index('!init begin')
idx_add   = body.index('!init add')
idx_atk   = body.index('!attack')
check_truthy('positive: !init begin before !init add', idx_begin < idx_add)
check_truthy('positive: !init add before !attack',     idx_add < idx_atk)

# Target hint name appears in body
check_truthy('positive: Garrick in body', 'Garrick' in body)

# B2.1 narration mandate preserved
check_truthy('positive: narration mandate present',
             'NARRATION MUST' in body or 'narration MUST' in body)

# Concrete correct example present
check_truthy('positive: correct example present',
             'Correct example' in body or 'correct example' in body)

# Wrong example present
check_truthy('positive: wrong example present',
             'Wrong example' in body or 'wrong example' in body)


# ─────────────────────────────────────────────────────────────────────────────
# §8.1 — Gate isolation: intent gate (gate 1)
# ─────────────────────────────────────────────────────────────────────────────

for bad_intent in (INTENT_SOCIAL, INTENT_TRIVIAL, INTENT_EXPLORATION,
                   INTENT_RISKY, INTENT_CONTESTED, 'unknown', ''):
    body2, sig2 = call(intent_current=bad_intent)
    check_falsy(f'gate1/{bad_intent}: body empty', body2)
    check(f'gate1/{bad_intent}: fired=0', sig2['fired'], 0)
    check(f'gate1/{bad_intent}: intent_current recorded',
          sig2['intent_current'], bad_intent or 'unknown')


# ─────────────────────────────────────────────────────────────────────────────
# §8.1 — Gate isolation: mode gate (gate 2)
# ─────────────────────────────────────────────────────────────────────────────

body3, sig3 = call(mode='combat')
check_falsy('gate2/combat: body empty', body3)
check('gate2/combat: fired=0', sig3['fired'], 0)
check('gate2/combat: mode=combat recorded', sig3['mode'], 'combat')

# Other non-exploration modes still pass gate 2 (not combat)
for pass_mode in ('exploration', 'social', 'travel', 'downtime', ''):
    body_m, sig_m = call(mode=pass_mode)
    check_truthy(f'gate2/{pass_mode or "empty"}: fires (not combat)',
                 sig_m['fired'])


# ─────────────────────────────────────────────────────────────────────────────
# §8.1 — Gate isolation: active-turn gate (gate 3)
# ─────────────────────────────────────────────────────────────────────────────

body4, sig4 = call(has_active_turn=True)
check_falsy('gate3/active_turn=True: body empty', body4)
check('gate3/active_turn=True: fired=0', sig4['fired'], 0)
check('gate3/active_turn=True: has_active_turn=1', sig4['has_active_turn'], 1)


# ─────────────────────────────────────────────────────────────────────────────
# §8.1 — Empty target hints: !init begin only, no !init add template
# ─────────────────────────────────────────────────────────────────────────────

body5, sig5 = call(target_hints=[])
check_truthy('empty_hints: fires', sig5['fired'])
check_truthy('empty_hints: body non-empty', bool(body5))
check_truthy('empty_hints: !init begin present', '!init begin' in body5)
check('empty_hints: target_hint_count=0', sig5['target_hint_count'], 0)
# Guidance to name target present
check_truthy('empty_hints: guidance to name target',
             'name' in body5.lower() or 'No NPC' in body5)


# ─────────────────────────────────────────────────────────────────────────────
# §8.1 — Target hint rendering
# ─────────────────────────────────────────────────────────────────────────────

# Single name
h1 = _render_target_hint_block(['Garrick'])
check_truthy('hint_single: non-empty', bool(h1))
check_truthy('hint_single: Garrick present', 'Garrick' in h1)

# Multiple names — all present when within cap
names3 = ['Garrick', 'Bouncer', 'Innkeeper']
h3 = _render_target_hint_block(names3)
for n in names3:
    check_truthy(f'hint_multi: {n} present', n in h3)

# Empty list → empty string
check('hint_empty: returns empty string', _render_target_hint_block([]), '')

# Filtering None/empty entries
h_filter = _render_target_hint_block(['', None, 'ValidName'])
check_truthy('hint_filter: ValidName present', 'ValidName' in h_filter)

# Very long list — truncated to cap
long_list = [f'NPC_{i}' for i in range(20)]
h_long = _render_target_hint_block(long_list)
count_in_hint = sum(1 for n in long_list if n in h_long)
check_truthy(f'hint_truncation: at most {_INIT_TARGET_HINT_CAP} names appear',
             count_in_hint <= _INIT_TARGET_HINT_CAP)

# Full hint body contains the hint block
body_multi, _ = call(target_hints=['Garrick', 'Bouncer'])
check_truthy('hint_full_body: Garrick in body', 'Garrick' in body_multi)
check_truthy('hint_full_body: Bouncer in body', 'Bouncer' in body_multi)


# ─────────────────────────────────────────────────────────────────────────────
# §8.1 — Idempotency (pure function — no side effects)
# ─────────────────────────────────────────────────────────────────────────────

b_a, s_a = call()
b_b, s_b = call()
check('idempotent: body identical on repeated calls', b_a, b_b)
check('idempotent: signals identical on repeated calls', s_a, s_b)


# ─────────────────────────────────────────────────────────────────────────────
# §8.1 — init_log_summary format
# ─────────────────────────────────────────────────────────────────────────────

_, sig_fire = call()
summary = init_log_summary(sig_fire)
check_truthy('log_summary: fired=1 present', 'fired=1' in summary)
check_truthy('log_summary: intent_current present', 'intent_current=' in summary)
check_truthy('log_summary: mode present', 'mode=' in summary)
check_truthy('log_summary: has_active_turn present', 'has_active_turn=' in summary)
check_truthy('log_summary: target_hint_count present', 'target_hint_count=' in summary)

# Empty signals → safe fallback
empty_summary = init_log_summary({})
check_truthy('log_summary: empty signals OK', 'fired=0' in empty_summary)


# ─────────────────────────────────────────────────────────────────────────────
# §8.1 — Composition: init body renders INSIDE ROLL DIRECTIVE, BEFORE attack
# ─────────────────────────────────────────────────────────────────────────────

rd_attack = orch.RollDecision(
    True, category='attack', severity='meaningful',
    reason='Combat action — Avrae handles attack rolls via !attack / !cast.'
)

# Without init body — baseline
base_directive = rd_attack.to_prompt_directive()
check_truthy('composition/base: ROLL DECISION present', 'ROLL DECISION' in base_directive)
check_truthy('composition/base: !attack present', '!attack' in base_directive)

# With init body — prepended
init_body_sample, _ = call()
extended_directive = rd_attack.to_prompt_directive(init_directive_body=init_body_sample)
check_truthy('composition/extended: starts with init body',
             extended_directive.startswith('INIT NOT YET ACTIVE'))
check_truthy('composition/extended: ROLL DECISION present',
             'ROLL DECISION' in extended_directive)
# Init block appears BEFORE the ROLL DECISION line
idx_init_hdr = extended_directive.index('INIT NOT YET ACTIVE')
idx_roll_dec = extended_directive.index('ROLL DECISION')
check_truthy('composition/extended: init before ROLL DECISION',
             idx_init_hdr < idx_roll_dec)

# Non-attack categories are unaffected by init_directive_body
rd_skill = orch.RollDecision(True, skill='perception', category='skill_check',
                             severity='minor', reason='test')
skill_dir = rd_skill.to_prompt_directive(init_directive_body='SHOULD_BE_IGNORED')
check_falsy('composition/skill: init body not inserted for non-attack',
            'SHOULD_BE_IGNORED' in skill_dir)
check_truthy('composition/skill: !check still present', '!check' in skill_dir)


# ─────────────────────────────────────────────────────────────────────────────
# Integration: init_directive: log fires every turn; directive_emit: init= field
# ─────────────────────────────────────────────────────────────────────────────

guild_a, cid_a = make_campaign('Log Test A')
bind_character(cid_a, 'log_a_ctrl', 'Aldric', race='Human', char_class='Fighter', level=1)
camp_a, chars_a = get_camp_chars(guild_a, cid_a)

captured.clear()
dm_respond(camp_a, chars_a, 'I look around the room.')

init_log_lines = [m for m in captured if m.startswith('init_directive:')]
check('telemetry: init_directive: fires every turn (non-combat)',
      len(init_log_lines), 1)
check_truthy('telemetry: init_directive: contains fired=',
             any('fired=' in m for m in init_log_lines))

de_lines = [m for m in captured if 'directive_emit:' in m]
check('telemetry: directive_emit: fires', len(de_lines), 1)
check_truthy('telemetry: directive_emit: contains init=',
             any('init=' in m for m in de_lines))

# Non-COMBAT intent → init=0 in directive_emit
if de_lines:
    parsed = {}
    for tok in re.finditer(r'(\w+)=([^\s]+)', de_lines[0]):
        parsed[tok.group(1)] = tok.group(2)
    check('telemetry: non-combat intent → init=0', parsed.get('init'), '0')

# COMBAT intent in exploration mode → init=1 in directive_emit
captured.clear()
dm_respond(camp_a, chars_a, 'I attack the barkeep with my dagger.')

de_lines2 = [m for m in captured if 'directive_emit:' in m]
init_dir_lines2 = [m for m in captured if m.startswith('init_directive:')]
check_truthy('telemetry/combat: init_directive: fires', bool(init_dir_lines2))
if de_lines2:
    parsed2 = {}
    for tok in re.finditer(r'(\w+)=([^\s]+)', de_lines2[0]):
        parsed2[tok.group(1)] = tok.group(2)
    check('telemetry/combat: exploration mode → init=1', parsed2.get('init'), '1')

# COMBAT mode → init=0 even on attack
guild_b, cid_b = make_campaign('Log Test B', mode='combat')
bind_character(cid_b, 'log_b_ctrl', 'Borin', race='Dwarf', char_class='Paladin', level=2)
camp_b, chars_b = get_camp_chars(guild_b, cid_b)

captured.clear()
dm_respond(camp_b, chars_b, 'I attack the barkeep with my dagger.')
de_lines3 = [m for m in captured if 'directive_emit:' in m]
if de_lines3:
    parsed3 = {}
    for tok in re.finditer(r'(\w+)=([^\s]+)', de_lines3[0]):
        parsed3[tok.group(1)] = tok.group(2)
    check('telemetry/combat_mode: mode=combat → init=0', parsed3.get('init'), '0')


# ─────────────────────────────────────────────────────────────────────────────
# Integration: ROLL DIRECTIVE block in full system prompt contains init body
# when gate fires
# ─────────────────────────────────────────────────────────────────────────────

from dnd_engine import build_dm_context, get_scene_state

guild_c, cid_c = make_campaign('Prompt Composition Test')
bind_character(cid_c, 'comp_ctrl', 'Sera', race='Elf', char_class='Rogue', level=3)
camp_c, chars_c = get_camp_chars(guild_c, cid_c)
scene_c = get_scene_state(cid_c)

# Compute roll_decision and init_body manually
rd_c = orch.should_call_roll(INTENT_COMBAT, 'exploration', 'I attack the barkeep')
init_b, init_s = orch.compute_init_directive(
    intent_current=INTENT_COMBAT,
    mode='exploration',
    has_active_turn=False,
    target_hints=['Barkeep'],
)
prompt_c = build_dm_context(
    camp_c, chars_c,
    roll_decision=rd_c,
    mode='exploration',
    scene_state=scene_c,
    init_directive=init_b,
)

check_truthy('prompt/combat+init: ROLL DIRECTIVE block present',
             '=== ROLL DIRECTIVE ===' in prompt_c)
check_truthy('prompt/combat+init: init body inside prompt', '!init begin' in prompt_c)
check_truthy('prompt/combat+init: !init add inside prompt', '!init add' in prompt_c)
check_truthy('prompt/combat+init: ROLL DECISION still present',
             'ROLL DECISION' in prompt_c)

# Confirm ordering: ROLL DIRECTIVE header, then init body, then ROLL DECISION
roll_dir_idx  = prompt_c.index('=== ROLL DIRECTIVE ===')
init_begin_idx = prompt_c.index('INIT NOT YET ACTIVE')
roll_dec_idx   = prompt_c.index('ROLL DECISION')
check_truthy('prompt/ordering: === ROLL DIRECTIVE === before init body',
             roll_dir_idx < init_begin_idx)
check_truthy('prompt/ordering: init body before ROLL DECISION',
             init_begin_idx < roll_dec_idx)

# Negative: combat mode → init body absent from prompt
init_b_neg, _ = orch.compute_init_directive(
    intent_current=INTENT_COMBAT,
    mode='combat',
    has_active_turn=False,
    target_hints=['Barkeep'],
)
prompt_neg = build_dm_context(
    camp_c, chars_c,
    roll_decision=rd_c,
    mode='combat',
    scene_state=scene_c,
    init_directive=init_b_neg,  # empty — gate 2 blocked
)
check_falsy('prompt/combat_mode: init body absent when mode=combat',
            'INIT NOT YET ACTIVE' in prompt_neg)


# ─────────────────────────────────────────────────────────────────────────────
# Cross-campaign isolation: target hints from wrong campaign don't leak
# ─────────────────────────────────────────────────────────────────────────────

guild_d, cid_d = make_campaign('Campaign D')
guild_e, cid_e = make_campaign('Campaign E')

npc_upsert(cid_d, 'DragonD', role='villain')
bind_character(cid_d, 'iso_ctrl_d', 'Kira', race='Human', char_class='Wizard', level=4)
bind_character(cid_e, 'iso_ctrl_e', 'Mira', race='Elf', char_class='Bard', level=2)

camp_d, chars_d = get_camp_chars(guild_d, cid_d)
camp_e, chars_e = get_camp_chars(guild_e, cid_e)

captured.clear()
# Run dm_respond for campaign E — should NOT see campaign D's NPC in init log
dm_respond(camp_e, chars_e, 'I attack with my dagger.')
init_lines_e = [m for m in captured if m.startswith('init_directive:')]
check_truthy('isolation: init_directive: fires for campaign E', bool(init_lines_e))
# DragonD should not appear in campaign E's init directive body
dm_body_e = ''.join(init_lines_e)
check_falsy('isolation: DragonD absent from campaign E log', 'DragonD' in dm_body_e)


# ─────────────────────────────────────────────────────────────────────────────
# Integration: reactive mode flip — gate 2 closes after _handle_init_event
# fires set_scene_mode('combat') in response to !init begin
# ─────────────────────────────────────────────────────────────────────────────

guild_f, cid_f = make_campaign('Reactive Flip Test')
bind_character(cid_f, 'flip_ctrl', 'Roland', race='Human', char_class='Fighter', level=3)
camp_f, chars_f = get_camp_chars(guild_f, cid_f)

# Turn 1: exploration mode, no active turn → directive fires
captured.clear()
dm_respond(camp_f, chars_f, 'I swing my dagger at Garrick.')
de_turn1 = [m for m in captured if 'directive_emit:' in m]
init_dir_turn1 = [m for m in captured if m.startswith('init_directive:')]
check_truthy('reactive_flip/turn1: init_directive: fires', bool(init_dir_turn1))
if de_turn1:
    parsed_t1 = {}
    for tok in re.finditer(r'(\w+)=([^\s]+)', de_turn1[0]):
        parsed_t1[tok.group(1)] = tok.group(2)
    check('reactive_flip/turn1: init=1 in directive_emit', parsed_t1.get('init'), '1')

# Simulate _handle_init_event: Avrae fires set_scene_mode('combat')
# and set_active_turn (as if !init begin was processed)
set_scene_mode(cid_f, 'combat')
set_active_turn(cid_f, 'flip_ctrl', 'Roland', 1)

# Turn 2: mode=combat + active turn → gate 2 and gate 3 both close → directive silent
captured.clear()
camp_f_refreshed, chars_f_refreshed = get_camp_chars(guild_f, cid_f)
dm_respond(camp_f_refreshed, chars_f_refreshed, 'I attack again with my dagger.')
de_turn2 = [m for m in captured if 'directive_emit:' in m]
init_dir_turn2 = [m for m in captured if m.startswith('init_directive:')]
check_truthy('reactive_flip/turn2: init_directive: fires every turn', bool(init_dir_turn2))
if de_turn2:
    parsed_t2 = {}
    for tok in re.finditer(r'(\w+)=([^\s]+)', de_turn2[0]):
        parsed_t2[tok.group(1)] = tok.group(2)
    check('reactive_flip/turn2: mode=combat → init=0', parsed_t2.get('init'), '0')

# Verify: get_active_turn confirms init is active → gate 3 was closed
active = get_active_turn(cid_f)
check_truthy('reactive_flip/turn2: get_active_turn confirms active', active is not None)


# ─────────────────────────────────────────────────────────────────────────────
# Cleanup
# ─────────────────────────────────────────────────────────────────────────────

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
