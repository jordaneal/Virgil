"""Tests for Ship S49 — RollBuffer drain at rest-event boundary.

§78 layer-1 in-memory state reset, mode-agnostic application (third
instance of the four-layer rule, sibling to S45 DB-init-end + S48
in-memory-init-end). Every Avrae rest embed lands in RollBuffer via
on_message → buffer.add with kind='rest'. The actor-extraction fallback
to 'someone' currently keeps these entries from matching PC-actor
consume filters (zero observed buffer.consume hits on roll_kinds=['rest']
across full journal), but that protection is serendipitous, not
structural — if a future Avrae embed parses to a real PC name, the rest
event would surface in the next matching-actor turn's footer AND in the
LLM prompt's AVRAE EVENTS block.

Surgical fix: buffer.clear(guild_id) called UNCONDITIONALLY (regardless
of mode) at the end of _handle_rest_event, after advance_time. Mirrors
S48's pattern at _handle_init_event with the key design difference of
mode-agnostic placement — combat-mode-branch §78 layer-2/4 audit gaps
remain deferred per planner reconciliation.

Run:
    cd /home/jordaneal/scripts && python3 test_rest_event_rollbuffer_drain.py
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))

import avrae_listener as al


def _make_event(guild_id, actor, kind='rest', detail='long rest'):
    return {
        'guild_id': guild_id,
        'actor': actor,
        'kind': kind,
        'detail': detail,
        'result': None,
        'nat': None,
        'damage': None,
        'crit': False,
        'ts': time.time(),
    }


# ---------------------------------------------------------------------------
# Assertion 1 — RollBuffer.size()/clear() smoke (sibling to S48 unit coverage)
# ---------------------------------------------------------------------------
buf = al.RollBuffer()
assert buf.size(123) == 0, "fresh buffer should report size 0"
buf.add(_make_event(123, 'donovan ruby', kind='rest', detail='long rest'))
buf.add(_make_event(123, 'someone', kind='rest', detail='short rest'))
assert buf.size(123) == 2, "after two rest adds, size should be 2"
buf.clear(123)
assert buf.size(123) == 0, "after clear, size should be 0"
print("  ✓ 1. RollBuffer.size()/clear() handle rest-kind events identically to other kinds")

# ---------------------------------------------------------------------------
# Assertion 2 — drain is guild-scoped for rest events (other guilds untouched)
# ---------------------------------------------------------------------------
buf.add(_make_event(111, 'donovan ruby', kind='rest', detail='long rest'))
buf.add(_make_event(222, 'borin', kind='rest', detail='short rest'))
assert buf.size(111) == 1 and buf.size(222) == 1
buf.clear(111)
assert buf.size(111) == 0, "cleared guild empty"
assert buf.size(222) == 1, "other guild's rest event survives — drain is guild-scoped"
print("  ✓ 2. rest-event drain is guild-scoped — other guilds untouched")

# ---------------------------------------------------------------------------
# Assertion 3 — future-proofed symptom: rest event with real PC actor name
# is drained before next matching-actor consume can surface it.
# This is the scenario S48 recon Phase 5 #1 named as structurally possible
# but empirically unfired. Test guards against the serendipity breaking.
# ---------------------------------------------------------------------------
sim_buf = al.RollBuffer()
sim_guild = 1498592771471314977  # live test guild
sim_buf.add(_make_event(sim_guild, 'donovan ruby', kind='rest', detail='long rest'))
assert sim_buf.size(sim_guild) == 1, "precondition: rest event with real-PC actor in buffer"
sim_buf.clear(sim_guild)  # the new rest-event drain step
post_consume = sim_buf.consume(sim_guild, ['donovan ruby'])
assert post_consume == [], \
    f"post-drain consume must be empty, got {post_consume!r} — serendipity protection lost"
print("  ✓ 3. real-PC-actor rest event is drained before consume can surface it")

# ---------------------------------------------------------------------------
# Assertion 4 — idempotency: clear twice produces same final state
# ---------------------------------------------------------------------------
idem_buf = al.RollBuffer()
idem_buf.add(_make_event(555, 'donovan ruby', kind='rest', detail='long rest'))
idem_buf.clear(555)
first_size = idem_buf.size(555)
idem_buf.clear(555)
second_size = idem_buf.size(555)
assert first_size == second_size == 0, "rest-event drain must be idempotent"
print("  ✓ 4. rest-event drain is idempotent across repeated calls")

# ---------------------------------------------------------------------------
# Source-text regression guards on the production handler.
# These verify the wiring inside _handle_rest_event without spinning up a
# Discord fixture — the operator-spec scenarios 3 + 4 (mode-agnostic +
# ordering) reduce to source-text placement assertions because the unit
# behavior of buffer.clear is already proven above.
# ---------------------------------------------------------------------------
bot_path = os.path.join(os.path.dirname(__file__), 'discord_dnd_bot.py')
with open(bot_path) as f:
    bot_src = f.read()

handler_start = bot_src.find("async def _handle_rest_event(message, rest_evt):")
assert handler_start != -1, "could not locate _handle_rest_event handler"
# Handler body extends to next top-level definition or decorator.
handler_end_match = bot_src.find("\n@bot.event\nasync def on_message_edit", handler_start)
assert handler_end_match != -1, "could not locate handler end"
handler_section = bot_src[handler_start:handler_end_match]

# ---------------------------------------------------------------------------
# Assertion 5 — drain call exists inside _handle_rest_event body
# ---------------------------------------------------------------------------
drain_idx = handler_section.find("buffer.clear(message.guild.id)")
assert drain_idx != -1, \
    "buffer.clear(message.guild.id) call missing from _handle_rest_event body"
print("  ✓ 5. drain call is wired inside _handle_rest_event")

# ---------------------------------------------------------------------------
# Assertion 6 — drain is MODE-AGNOSTIC (outside the combat-mode-gated branch).
# The combat-mode branch only does DB-side cleanup; drain must run for the
# 'already mode=exploration' path as well, since rest events pollute the
# buffer regardless of mode. This is the load-bearing test for the
# mode-agnostic design choice locked at fix-shape selection.
#
# Structural check: the "Track 4 #3 — time advancement on Avrae rest" comment
# is the first mode-agnostic anchor after the combat-mode if/else block
# closes. Drain must appear AFTER that anchor (i.e. in the mode-agnostic
# region). If drain were gated inside the combat-mode if-branch, it would
# appear BEFORE this anchor.
# ---------------------------------------------------------------------------
mode_branch_start = handler_section.find("if current_mode == 'combat':")
assert mode_branch_start != -1, "could not locate combat-mode branch"
mode_agnostic_anchor = handler_section.find("# Track 4 #3 — time advancement")
assert mode_agnostic_anchor != -1, \
    "could not locate mode-agnostic anchor comment (Track 4 #3 — time advancement)"
assert mode_agnostic_anchor > mode_branch_start, \
    "anchor precondition broken: Track 4 #3 comment should follow the combat-mode branch"
assert drain_idx > mode_agnostic_anchor, \
    f"drain (idx={drain_idx}) must be in the mode-agnostic region " \
    f"(after Track 4 #3 anchor at idx={mode_agnostic_anchor}) — " \
    f"drain currently appears inside the combat-mode-gated branch, " \
    f"breaking mode-agnostic design"
print("  ✓ 6. drain is mode-agnostic (placed after combat-mode if/else block)")

# ---------------------------------------------------------------------------
# Assertion 7 — drain runs AFTER advance_time call (ordering)
# ---------------------------------------------------------------------------
advance_time_idx = handler_section.find("advance_time(campaign['id'],")
assert advance_time_idx != -1, "could not locate advance_time call in handler"
assert drain_idx > advance_time_idx, \
    f"drain (idx={drain_idx}) must run AFTER advance_time (idx={advance_time_idx}) — " \
    f"time advancement is primary handler purpose; drain rides after"
print("  ✓ 7. drain runs after advance_time call (ordering)")

# ---------------------------------------------------------------------------
# Assertion 8 — telemetry log format includes the operator-grep prefix
# and the rest_kind field (distinguishes long-rest vs short-rest patterns
# in playtest data — per spec, this is a required telemetry field)
# ---------------------------------------------------------------------------
assert "rest_event_rollbuffer_drained:" in handler_section, \
    "telemetry log prefix missing — operator grep pattern will break"
assert "drained_count=" in handler_section, \
    "telemetry must include drained_count field"
assert "rest_kind=" in handler_section, \
    "telemetry must include rest_kind field to distinguish long-rest vs short-rest"
assert "campaign=" in handler_section and "guild=" in handler_section, \
    "telemetry must include campaign + guild identifiers"
print("  ✓ 8. telemetry log line format intact (rest_event_rollbuffer_drained: + rest_kind)")

# ---------------------------------------------------------------------------
# Assertion 9 — drain has a try/except wrapper so it can never block the
# rest of the handler. Mirrors S48 pattern; the rest handler's primary job
# is mode flip + advance_time, not buffer hygiene.
# ---------------------------------------------------------------------------
drain_preceding_section = handler_section[max(0, drain_idx - 200):drain_idx]
assert "try:" in drain_preceding_section, \
    "drain must be inside a try/except wrapper to soft-fail per §59"
print("  ✓ 9. drain is soft-failing via try/except wrapper")

# ---------------------------------------------------------------------------
# Assertion 10 — RollBuffer.size() is reused from S48 (no duplicate accessor).
# Confirms §17 single-write-path preserved on RollBuffer.
# ---------------------------------------------------------------------------
listener_path = os.path.join(os.path.dirname(__file__), 'avrae_listener.py')
with open(listener_path) as f:
    listener_src = f.read()
size_method_count = listener_src.count("def size(self, guild_id: int) -> int:")
assert size_method_count == 1, \
    f"expected exactly 1 RollBuffer.size() definition, found {size_method_count}"
clear_method_count = listener_src.count("def clear(self, guild_id: int):")
assert clear_method_count == 1, \
    f"expected exactly 1 RollBuffer.clear() definition, found {clear_method_count}"
print("  ✓ 10. RollBuffer accessors (size + clear) reused — no duplicate write paths")

print()
print("All 10 S49 assertions pass.")
