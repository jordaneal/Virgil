"""S65.1 Fix 2 — F-008 AUTO_EXECUTE close adversarial verify.

Asserts that with AUTO_EXECUTE_ENABLED=False:
  (1) parse_auto_execute still strips a tail emitted by the LLM (display
      cleanup is preserved; the tail is never shown to the player).
  (2) parse_auto_execute returns the parsed actions list (parser is still
      operational, but no state write happens).
  (3) execute_auto_actions returns [] immediately when called with a non-
      empty actions list — NO quest row written, NO clock tick fires,
      NO mode change happens.
  (4) `quest_add_with_dedup` (the S65.1 migration target) works normally
      for the test-harness path.
  (5) The raw `quest_add` slash path also continues to work — manual
      /quest add remains unrestricted (DM may deliberately re-add identical
      titles).

Adversarial verify per S65.1 plan §Fix 2D — operator-paste-verbatim:
  "Emit AUTO_EXECUTE_BEGIN QUEST_ADD|fake_quest AUTO_EXECUTE_END from LLM
   narration in a test fixture; assert no quest row written, no clock tick
   fires, no mode change happens."

Run: python3 test_auto_execute_closed.py
"""

import sys

sys.path.insert(0, '/home/jordaneal/scripts')

import dnd_engine
from dnd_engine import (
    AUTO_EXECUTE_ENABLED,
    parse_auto_execute, execute_auto_actions,
    quest_add, quest_add_with_dedup,
    get_active_quests, get_all_quests,
    create_campaign,
    init_scene_state, get_scene_state,
    clock_create, get_clocks,
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


# ──────────────────────────────────────────────────────────────────────────────
# Test 0: feature flag is False (the close shipped)
# ──────────────────────────────────────────────────────────────────────────────

check('feature flag: AUTO_EXECUTE_ENABLED is False (S65.1 ship)',
      AUTO_EXECUTE_ENABLED, False)


# ──────────────────────────────────────────────────────────────────────────────
# Test 1: parse_auto_execute still strips a tail emitted by the LLM
# ──────────────────────────────────────────────────────────────────────────────

llm_response = (
    "The bandits draw their blades. Combat begins.\n"
    "\n"
    "AUTO_EXECUTE_BEGIN\n"
    "QUEST_ADD|Defeat the Bandits\n"
    "MODE|combat\n"
    "AUTO_EXECUTE_END"
)
cleaned, actions = parse_auto_execute(llm_response)
check('parse: tail stripped from cleaned response',
      'AUTO_EXECUTE_BEGIN' not in cleaned, True)
check('parse: tail stripped (END marker too)',
      'AUTO_EXECUTE_END' not in cleaned, True)
check_truthy('parse: narration preserved in cleaned',
             'bandits draw their blades' in cleaned)


# ──────────────────────────────────────────────────────────────────────────────
# Test 2: parse_auto_execute still returns the parsed actions list (parser
# is still operational; no state mutation happens at parse time anyway)
# ──────────────────────────────────────────────────────────────────────────────

check('parse: actions parsed (parser still operational)',
      len(actions), 2)
check('parse: actions[0] is QUEST_ADD',
      actions[0]['cmd'], 'QUEST_ADD')
check('parse: actions[1] is MODE',
      actions[1]['cmd'], 'MODE')


# ──────────────────────────────────────────────────────────────────────────────
# Test 3: execute_auto_actions returns [] when disabled — NO state write
# ──────────────────────────────────────────────────────────────────────────────

ADV_GUILD = 'test-adversarial-f008'
ADV_CAMP = create_campaign(ADV_GUILD, 'Adversarial F-008 Verify')
init_scene_state(ADV_CAMP)
clock_create(ADV_CAMP, 'Detection', 4)

# Snapshot pre-state
pre_quests = get_all_quests(ADV_CAMP)
pre_scene = get_scene_state(ADV_CAMP)
pre_mode = (pre_scene.get('mode') if pre_scene else None) or 'exploration'
pre_clocks = get_clocks(ADV_CAMP)
pre_detection = next((c for c in pre_clocks if c['name'] == 'Detection'), None)
pre_detection_value = pre_detection['ticks'] if pre_detection else None

# Adversarial: simulate an LLM-emitted tail being processed through the pipeline
adversarial_actions = [
    {'cmd': 'QUEST_ADD', 'args': ['fake_quest']},
    {'cmd': 'CLOCK_TICK', 'args': ['Detection', 2]},
    {'cmd': 'MODE', 'args': ['combat']},
]
results = execute_auto_actions(ADV_CAMP, adversarial_actions)
check('execute: returns [] when disabled', results, [])

# Verify NO state changed
post_quests = get_all_quests(ADV_CAMP)
post_scene = get_scene_state(ADV_CAMP)
post_mode = (post_scene.get('mode') if post_scene else None) or 'exploration'
post_clocks = get_clocks(ADV_CAMP)
post_detection = next((c for c in post_clocks if c['name'] == 'Detection'), None)
post_detection_value = post_detection['ticks'] if post_detection else None

check('adversarial: no new quest row written',
      len(post_quests), len(pre_quests))
check('adversarial: mode unchanged (no auto-flip)',
      post_mode, pre_mode)
check('adversarial: clock value unchanged (no tick)',
      post_detection_value, pre_detection_value)


# ──────────────────────────────────────────────────────────────────────────────
# Test 4: quest_add_with_dedup still works (the S65.1 migration target)
# ──────────────────────────────────────────────────────────────────────────────

DEDUP_CAMP = create_campaign('test-adversarial-dedup', 'Adversarial Dedup')
init_scene_state(DEDUP_CAMP)

result = quest_add_with_dedup(DEDUP_CAMP, 'Test Quest A')
check_truthy('dedup: first add returns non-None', result is not None)
check('dedup: first add was_new=True', result[1], True)

result2 = quest_add_with_dedup(DEDUP_CAMP, 'Test Quest A')
check('dedup: duplicate returns None', result2, None)

result3 = quest_add_with_dedup(DEDUP_CAMP, 'Test Quest B')
check_truthy('dedup: different title succeeds', result3 is not None)


# ──────────────────────────────────────────────────────────────────────────────
# Test 5: raw quest_add (manual /quest add slash) still works — no dedup
# ──────────────────────────────────────────────────────────────────────────────

MANUAL_CAMP = create_campaign('test-adversarial-manual', 'Adversarial Manual')
init_scene_state(MANUAL_CAMP)

qid1 = quest_add(MANUAL_CAMP, 'Same Title')
check_truthy('manual: first add returns id', qid1 is not None)

qid2 = quest_add(MANUAL_CAMP, 'Same Title')
check_truthy('manual: SECOND add returns id (no dedup, unrestricted)',
             qid2 is not None)
check_truthy('manual: ids are different (two distinct rows)', qid1 != qid2)


# ──────────────────────────────────────────────────────────────────────────────
# Test 6: execute_auto_actions with empty actions is silent no-op
# ──────────────────────────────────────────────────────────────────────────────

silent_results = execute_auto_actions(ADV_CAMP, [])
check('silent: empty actions returns []', silent_results, [])


# ──────────────────────────────────────────────────────────────────────────────
# Test 7: parse_auto_execute on response without a tail returns ([], cleaned)
# ──────────────────────────────────────────────────────────────────────────────

no_tail = "Just narration, no tail.\nThe scene unfolds."
clean_nt, actions_nt = parse_auto_execute(no_tail)
check('no-tail: cleaned response unchanged', clean_nt, no_tail)
check('no-tail: actions empty', actions_nt, [])


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
