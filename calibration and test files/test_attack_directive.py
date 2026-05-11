"""Test the attack RollDecision template directive (B2 fix).

Pre-fix bug: combat intent produced a RollDecision(needs_roll=True,
category='attack') with empty skill/save, which fell to the `else` branch in
to_prompt_directive() and emitted `!roll` as the quoted command. The HARD STOP
rule then said "the only Avrae command that may appear is the exact command
quoted" — but the LLM's reason field said "Avrae handles attack rolls via
!attack / !cast" so it freelanced `!attack` with NO target. Avrae rolled
against <No Target> and the attack silently vanished.

Post-fix: the attack branch emits a TEMPLATE with `<weapon-name>` and
`<target>` placeholders, plus an explicit instruction that `-t <target>` is
mandatory. The HARD STOP rule has a carve-out telling the LLM to fill the
placeholders rather than emit them literally.

Tests verify:
  1.  attack RollDecision produces a directive that mentions !attack
  2.  the directive contains the -t target requirement
  3.  the directive flags <No Target> as the failure mode
  4.  the directive mentions !cast as the spell alternative
  5.  the directive is clearly a template (mentions placeholders)
  6.  non-attack RollDecisions are unchanged (regression)
  7.  should_call_roll for INTENT_COMBAT still produces category='attack'

Run: python3 test_attack_directive.py
"""

import sys

sys.path.insert(0, '/home/jordaneal/scripts')

import dnd_orchestration as orch
from dnd_orchestration import RollDecision, should_call_roll, INTENT_COMBAT

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
        FAILURES.append(f"  {label}: {needle!r} not found in: {haystack[:200]!r}...")


def check_not_in(label, needle, haystack):
    global PASS, FAIL
    if needle not in haystack:
        PASS += 1
    else:
        FAIL += 1
        FAILURES.append(f"  {label}: {needle!r} unexpectedly found in: {haystack[:200]!r}...")


# ──────────────────────────────────────────────────────────────────────────────
# Test 1: attack RollDecision produces a template directive
# ──────────────────────────────────────────────────────────────────────────────

attack_decision = RollDecision(
    needs_roll=True,
    category='attack',
    severity='meaningful',
    reason="Combat action — Avrae handles attack rolls via !attack / !cast.",
)
out = attack_decision.to_prompt_directive()

check_in('attack: mentions !attack',                  '!attack', out)
check_in('attack: mentions -t target',                '-t <target>', out)
check_in('attack: weapon placeholder present',        '<weapon-name>', out)
check_in('attack: spell placeholder present',         '<spell-name>', out)
check_in('attack: !cast alternative present',         '!cast', out)
check_in('attack: <No Target> failure mode flagged',  '<No Target>', out)
check_in('attack: marked as TEMPLATE',                'TEMPLATE', out)
check_in('attack: REQUIRED hint for -t',              'REQUIRED', out)
check_in('attack: example weapon names listed',       'unarmed strike', out)
check_in('attack: example spell names listed',        'fireball', out)
check_in('attack: severity surfaces',                 'meaningful', out)
check_in('attack: reason field surfaces',             'Avrae handles attack rolls', out)
check_in('attack: canonical-name reminder',           'canonical NPC name', out)
# B2.1 follow-up: no-quotes rule (Avrae uses positional parsing)
check_in('attack: no-quotes rule explicit',           'DO NOT wrap', out)
check_in('attack: positive example unquoted',         '!attack unarmed strike -t Garrick', out)
check_not_in('attack: template itself unquoted',      '!attack "<weapon-name>"', out)
# B2.1 follow-up: narration-required (LLM was emitting command-only)
check_in('attack: narration mandate explicit',        'narrate the player', out)
check_in('attack: insufficient flag for command-only', 'INSUFFICIENT', out)
check_in('attack: narration body required',           'BEFORE the command', out)


# ──────────────────────────────────────────────────────────────────────────────
# Test 2: regression — non-attack RollDecisions are unchanged
# ──────────────────────────────────────────────────────────────────────────────

skill_decision = RollDecision(
    needs_roll=True,
    skill='stealth',
    category='skill_check',
    severity='meaningful',
    reason="Sneaking past a guard.",
)
skill_out = skill_decision.to_prompt_directive()
check_in('skill: mentions !check',                '!check stealth <DC>', skill_out)
check_not_in('skill: no attack template',         '<weapon-name>', skill_out)
check_not_in('skill: no <No Target> warning',     '<No Target>', skill_out)
check_in('skill: includes DC GUIDANCE',           'DC GUIDANCE', skill_out)
check_in('skill: format template requires colon-name bold line',
         '**!check stealth <DC> : <First Name>**', skill_out)


save_decision = RollDecision(
    needs_roll=True,
    save='dex',
    category='save',
    severity='dire',
    reason="Reflex save against trap.",
)
save_out = save_decision.to_prompt_directive()
check_in('save: mentions !save',                  '!save dex <DC>', save_out)
check_not_in('save: no attack template',          '<weapon-name>', save_out)
check_in('save: includes DC GUIDANCE',            'DC GUIDANCE', save_out)
check_in('save: format template requires colon-name bold line',
         '**!save dex <DC> : <First Name>**', save_out)


no_roll_decision = RollDecision(needs_roll=False, reason="Casual chat.")
no_out = no_roll_decision.to_prompt_directive()
check_in('no_roll: NO ROLL prefix',               'NO ROLL', no_out)
check_not_in('no_roll: no template',              '<weapon-name>', no_out)


generic_roll_decision = RollDecision(
    needs_roll=True,
    severity='minor',
    reason="Generic d20.",
)
gen_out = generic_roll_decision.to_prompt_directive()
check_in('generic: falls back to !roll',          '`!roll`', gen_out)
check_not_in('generic: no attack template',       '<weapon-name>', gen_out)


# ──────────────────────────────────────────────────────────────────────────────
# Test 3: should_call_roll for INTENT_COMBAT still produces category='attack'
# (the orchestrator side is unchanged; just verify the contract holds)
# ──────────────────────────────────────────────────────────────────────────────

combat_decision = should_call_roll(INTENT_COMBAT, 'exploration', 'I attack the bartender')
check('combat: needs_roll=True',           combat_decision.needs_roll, True)
check('combat: category=attack',           combat_decision.category, 'attack')
check('combat: severity=meaningful',       combat_decision.severity, 'meaningful')

# And its directive output should be the new attack template
combat_out = combat_decision.to_prompt_directive()
check_in('combat: directive uses template',       'TEMPLATE', combat_out)
check_in('combat: directive includes -t',         '-t <target>', combat_out)


# ──────────────────────────────────────────────────────────────────────────────
# Test 4: combat in actual combat mode still produces attack template
# (mode shouldn't change the shape of the directive — only severity/etc.)
# ──────────────────────────────────────────────────────────────────────────────

combat_in_combat = should_call_roll(INTENT_COMBAT, 'combat', 'I swing my axe at the orc')
check('combat_mode: needs_roll=True',           combat_in_combat.needs_roll, True)
check('combat_mode: category=attack',           combat_in_combat.category, 'attack')
combat_in_combat_out = combat_in_combat.to_prompt_directive()
check_in('combat_mode: directive uses template',       'TEMPLATE', combat_in_combat_out)


# ──────────────────────────────────────────────────────────────────────────────
# Cleanup
# ──────────────────────────────────────────────────────────────────────────────

print(f"\n{PASS} passed, {FAIL} failed")
if FAILURES:
    print("\nFAILURES:")
    for f in FAILURES:
        print(f)
    sys.exit(1)
sys.exit(0)
