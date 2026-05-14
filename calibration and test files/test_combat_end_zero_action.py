"""Tests for Ship S50 — COMBAT_END 0-action framing fix (§78.6 layer-4
render-vs-marker).

S45 anchored §78 layer-4 (boundary atmospheric closeout) as unconditional
LLM dispatch on !init end. S50 recon surfaced that on 0-action combats
(mechanical begin + end with zero narratable beats between), the LLM
render produces vivid speculative atmospherics ("clash of steel and
shouted commands fade into a heavy silence, dust settling on the
cobblestones") that presuppose narratable combat events that did not
exist. Within §77 (no adjudication crossed) but framing drift.

§78.6 doctrine refinement: layer-4 RENDER is conditional on
content-to-render; the BOUNDARY MARKER itself is unconditional. Two
operational modes:
  - LLM render (multi-action) — existing S45-F dispatch path
  - Deterministic marker (0-action) — engine-emitted neutral text

Beat counter (BLOODIED + DOWNED dispatches) tracks per-guild during
combat. ROUND_START does NOT increment (always-fires regardless of
content). COMBAT_END reads + branches; does not increment.

Run:
    cd /home/jordaneal/scripts && python3 test_combat_end_zero_action.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))


# ---------------------------------------------------------------------------
# Unit coverage on the beat counter helpers (importable directly)
# ---------------------------------------------------------------------------
import discord_dnd_bot as bot_module


# ---------------------------------------------------------------------------
# Assertion 1 — reset establishes counter=0 for the guild
# ---------------------------------------------------------------------------
bot_module._combat_beat_counter.clear()  # fresh state
bot_module._reset_combat_beats(111)
assert bot_module._get_combat_beats(111) == 0, \
    "after reset, counter must be 0"
print("  ✓ 1. _reset_combat_beats establishes counter=0 for guild")

# ---------------------------------------------------------------------------
# Assertion 2 — increment bumps the counter and returns new value
# ---------------------------------------------------------------------------
bot_module._reset_combat_beats(111)
result = bot_module._increment_combat_beat(111)
assert result == 1 and bot_module._get_combat_beats(111) == 1, \
    f"after one increment, counter must be 1; got {result}"
result = bot_module._increment_combat_beat(111)
assert result == 2 and bot_module._get_combat_beats(111) == 2, \
    f"after two increments, counter must be 2; got {result}"
print("  ✓ 2. _increment_combat_beat bumps counter + returns new value")

# ---------------------------------------------------------------------------
# Assertion 3 — increment without prior reset still works (defaults to 0)
# ---------------------------------------------------------------------------
bot_module._combat_beat_counter.clear()  # no prior reset for guild 222
result = bot_module._increment_combat_beat(222)
assert result == 1, \
    f"increment without prior reset should default to 0+1=1; got {result}"
print("  ✓ 3. _increment_combat_beat handles never-touched guild gracefully")

# ---------------------------------------------------------------------------
# Assertion 4 — _get on never-touched guild returns 0 (no KeyError)
# ---------------------------------------------------------------------------
bot_module._combat_beat_counter.clear()
assert bot_module._get_combat_beats(333) == 0, \
    "get on never-touched guild must return 0, not raise"
print("  ✓ 4. _get_combat_beats handles never-touched guild")

# ---------------------------------------------------------------------------
# Assertion 5 — clear removes guild from counter dict
# ---------------------------------------------------------------------------
bot_module._reset_combat_beats(444)
bot_module._increment_combat_beat(444)
assert 444 in bot_module._combat_beat_counter
bot_module._clear_combat_beats(444)
assert 444 not in bot_module._combat_beat_counter, \
    "clear must remove the guild from the dict (not just zero it)"
print("  ✓ 5. _clear_combat_beats removes guild from dict entirely")

# ---------------------------------------------------------------------------
# Assertion 6 — clear on never-touched guild is a no-op (no KeyError)
# ---------------------------------------------------------------------------
bot_module._combat_beat_counter.clear()
bot_module._clear_combat_beats(555)  # never touched
assert bot_module._get_combat_beats(555) == 0
print("  ✓ 6. _clear_combat_beats handles never-touched guild")

# ---------------------------------------------------------------------------
# Assertion 7 — guild isolation: incrementing one guild does not affect
# another (load-bearing for multi-guild deployment)
# ---------------------------------------------------------------------------
bot_module._combat_beat_counter.clear()
bot_module._reset_combat_beats(666)
bot_module._reset_combat_beats(777)
bot_module._increment_combat_beat(666)
bot_module._increment_combat_beat(666)
bot_module._increment_combat_beat(777)
assert bot_module._get_combat_beats(666) == 2, \
    f"guild 666 counter must be 2; got {bot_module._get_combat_beats(666)}"
assert bot_module._get_combat_beats(777) == 1, \
    f"guild 777 counter must be 1 (isolated); got {bot_module._get_combat_beats(777)}"
bot_module._clear_combat_beats(666)
assert bot_module._get_combat_beats(666) == 0
assert bot_module._get_combat_beats(777) == 1, \
    "clearing one guild must not affect another's counter"
print("  ✓ 7. counter is guild-scoped — increments + clears are isolated")

# ---------------------------------------------------------------------------
# Assertion 8 — neutral closeout constant is non-empty, contains no
# combat-vocabulary atmospherics, and is short enough for Discord posting
# ---------------------------------------------------------------------------
closeout = bot_module._COMBAT_END_NEUTRAL_CLOSEOUT
assert isinstance(closeout, str) and closeout.strip(), \
    "_COMBAT_END_NEUTRAL_CLOSEOUT must be a non-empty string"
forbidden_vocab = ['clash', 'blow', 'strike', 'dust', 'steel', 'echo',
                   'shout', 'tension', 'cessation', 'falling', 'settle']
for word in forbidden_vocab:
    assert word.lower() not in closeout.lower(), \
        f"neutral closeout contains forbidden combat-vocab word: {word!r}"
assert len(closeout) <= 200, \
    f"neutral closeout should be brief (<=200 chars); got {len(closeout)}"
print("  ✓ 8. _COMBAT_END_NEUTRAL_CLOSEOUT is neutral + brief + non-empty")

# ---------------------------------------------------------------------------
# Source-text regression guards on the production wiring.
# ---------------------------------------------------------------------------
bot_path = os.path.join(os.path.dirname(__file__), 'discord_dnd_bot.py')
with open(bot_path) as f:
    bot_src = f.read()

# Locate _handle_init_event handler
init_handler_start = bot_src.find("async def _handle_init_event(message, init_evt):")
assert init_handler_start != -1
init_handler_end = bot_src.find("\nasync def _dispatch_combat_narration",
                                 init_handler_start)
assert init_handler_end != -1
init_handler_section = bot_src[init_handler_start:init_handler_end]

# Locate _dispatch_combat_narration
dispatch_start = bot_src.find("async def _dispatch_combat_narration")
assert dispatch_start != -1
dispatch_end = bot_src.find("\nasync def _post_hydration_prompt", dispatch_start)
assert dispatch_end != -1
dispatch_section = bot_src[dispatch_start:dispatch_end]

# ---------------------------------------------------------------------------
# Assertion 9 — reset call is wired in the !init begin branch
# ---------------------------------------------------------------------------
begin_branch_start = init_handler_section.find(
    "if evt_type == 'begin' and current_mode != 'combat':"
)
assert begin_branch_start != -1, "could not locate begin branch"
end_branch_start = init_handler_section.find(
    "elif evt_type == 'end' and current_mode == 'combat':"
)
assert end_branch_start != -1, "could not locate end branch"
begin_branch_section = init_handler_section[begin_branch_start:end_branch_start]
assert "_reset_combat_beats(message.guild.id)" in begin_branch_section, \
    "_reset_combat_beats must be called in the !init begin branch"
print("  ✓ 9. _reset_combat_beats wired in !init begin branch")

# ---------------------------------------------------------------------------
# Assertion 10 — increment call gated on BLOODIED + DOWNED kinds inside
# _dispatch_combat_narration. ROUND_START + COMBAT_END must NOT trigger it.
# ---------------------------------------------------------------------------
assert "_increment_combat_beat" in dispatch_section, \
    "_increment_combat_beat must be called from _dispatch_combat_narration"
# Verify the kind gate is correct
assert "'BLOODIED_THRESHOLD_CROSSED'" in dispatch_section, \
    "increment kind gate must include BLOODIED_THRESHOLD_CROSSED"
assert "'COMBATANT_DOWNED'" in dispatch_section, \
    "increment kind gate must include COMBATANT_DOWNED"
# Verify ROUND_START and COMBAT_END are NOT in the increment gate
gate_start = dispatch_section.find("trigger_event.get('kind') in (")
assert gate_start != -1, "could not locate increment kind gate"
gate_end = dispatch_section.find(")", gate_start)
gate_text = dispatch_section[gate_start:gate_end + 1]
assert "ROUND_START" not in gate_text, \
    f"ROUND_START must NOT appear in increment gate (would mis-classify " \
    f"0-action combats); gate: {gate_text}"
assert "COMBAT_END" not in gate_text, \
    f"COMBAT_END must NOT appear in increment gate (reads, never increments); " \
    f"gate: {gate_text}"
print("  ✓ 10. increment gated on BLOODIED+DOWNED only (not ROUND_START, not COMBAT_END)")

# ---------------------------------------------------------------------------
# Assertion 11 — COMBAT_END dispatch site has the beat-count branch
# (0 beats → deterministic closeout; ≥1 → existing LLM dispatch)
# ---------------------------------------------------------------------------
end_branch_section = init_handler_section[end_branch_start:]
assert "_get_combat_beats(message.guild.id)" in end_branch_section, \
    "_get_combat_beats must be called at the COMBAT_END dispatch site"
assert "if beats == 0:" in end_branch_section, \
    "COMBAT_END must branch on beats == 0 vs >= 1"
assert "_COMBAT_END_NEUTRAL_CLOSEOUT" in end_branch_section, \
    "0-action branch must post the deterministic neutral closeout"
assert "_dispatch_combat_narration(" in end_branch_section, \
    "multi-action branch must still dispatch to existing LLM render path"
print("  ✓ 11. COMBAT_END dispatch site branches on beat count")

# ---------------------------------------------------------------------------
# Assertion 12 — counter is cleared after COMBAT_END dispatch (either branch)
# ---------------------------------------------------------------------------
assert "_clear_combat_beats(message.guild.id)" in end_branch_section, \
    "_clear_combat_beats must be called after COMBAT_END dispatch"
# Verify clear comes AFTER the branch (not before, which would zero the
# counter before COMBAT_END can read it)
get_idx = end_branch_section.find("_get_combat_beats(message.guild.id)")
clear_idx = end_branch_section.find("_clear_combat_beats(message.guild.id)")
assert get_idx < clear_idx, \
    f"clear (idx={clear_idx}) must run AFTER get (idx={get_idx}) — " \
    f"clearing before reading would zero out the beat count"
print("  ✓ 12. counter cleared after dispatch (in correct order)")

# ---------------------------------------------------------------------------
# Assertion 13 — telemetry log lines for both branches are present
# ---------------------------------------------------------------------------
assert "combat_end_zero_action:" in end_branch_section, \
    "0-action branch must emit combat_end_zero_action: telemetry"
assert "combat_end_llm_dispatch:" in end_branch_section, \
    "multi-action branch must emit combat_end_llm_dispatch: telemetry"
assert "combat_beat_incremented:" in dispatch_section, \
    "increment site must emit combat_beat_incremented: telemetry"
print("  ✓ 13. telemetry log lines present for both branches + increment")

# ---------------------------------------------------------------------------
# Assertion 14 — full end-to-end simulated combat session via the helpers
# (proves the lifecycle: reset → increment*N → branch → clear)
# ---------------------------------------------------------------------------
bot_module._combat_beat_counter.clear()
test_guild = 1498592771471314977

# Simulate: !init begin (reset)
bot_module._reset_combat_beats(test_guild)
assert bot_module._get_combat_beats(test_guild) == 0

# Simulate: ROUND_START dispatch — does NOT increment (gate is in the
# production code; the helper itself doesn't gate, the caller does)
# So we test the gate by NOT calling _increment for ROUND_START.
# Then BLOODIED + DOWNED dispatches both fire:
bot_module._increment_combat_beat(test_guild)  # BLOODIED
bot_module._increment_combat_beat(test_guild)  # DOWNED
assert bot_module._get_combat_beats(test_guild) == 2

# Simulate: !init end → COMBAT_END dispatch reads beat count
final_beats = bot_module._get_combat_beats(test_guild)
assert final_beats == 2, "multi-action combat must show 2 beats"
# Branch decision: multi-action path
assert final_beats >= 1  # this branch in production fires LLM dispatch

# Simulate: cleanup
bot_module._clear_combat_beats(test_guild)
assert bot_module._get_combat_beats(test_guild) == 0
assert test_guild not in bot_module._combat_beat_counter

# Simulate: a fresh 0-action combat
bot_module._reset_combat_beats(test_guild)
final_beats = bot_module._get_combat_beats(test_guild)
assert final_beats == 0  # this branch in production posts neutral closeout
bot_module._clear_combat_beats(test_guild)
print("  ✓ 14. full session lifecycle: reset → increment×2 → branch → clear")

print()
print("All 14 S50 assertions pass.")
