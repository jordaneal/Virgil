"""Tests for Ship S47-arc — RollBuffer drain on `!init end`.

§78 layer-1 in-memory state reset (sibling to S45's DB-side narrative
buffer reset). RollBuffer holds in-memory Avrae events keyed by guild.
Without explicit drain at !init end, stale combat-mechanical events
(check/save/attack/cast/damage/roll) leak into post-combat narration —
both the `(N rolls in play)` footer artifact AND the LLM prompt's
AVRAE EVENTS block via _format_avrae_events.

Surgical fix: buffer.clear(guild_id) called as a sibling step to
reset_narrative_buffers_on_combat_exit inside _handle_init_event
evt_type='end'. New RollBuffer.size(guild_id) supports drain telemetry.

Run:
    cd /home/jordaneal/scripts && python3 test_init_end_rollbuffer_drain.py
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))

import avrae_listener as al


def _make_event(guild_id, actor, kind='check'):
    return {
        'guild_id': guild_id,
        'actor': actor,
        'kind': kind,
        'detail': '',
        'result': 15,
        'nat': 10,
        'damage': None,
        'crit': False,
        'ts': time.time(),
    }


# ---------------------------------------------------------------------------
# Assertion 1 — RollBuffer.size() returns raw storage count (no sweep)
# ---------------------------------------------------------------------------
buf = al.RollBuffer()
assert buf.size(123) == 0, "fresh buffer should report size 0"
buf.add(_make_event(123, 'donovan ruby'))
assert buf.size(123) == 1, "after one add, size should be 1"
buf.add(_make_event(123, 'donovan ruby', kind='save'))
buf.add(_make_event(123, 'borin', kind='attack'))
assert buf.size(123) == 3, "after three adds, size should be 3"
print("  ✓ 1. RollBuffer.size() returns raw storage count")

# ---------------------------------------------------------------------------
# Assertion 2 — RollBuffer.clear() empties the guild's bucket
# ---------------------------------------------------------------------------
buf.clear(123)
assert buf.size(123) == 0, "after clear, size should be 0"
print("  ✓ 2. RollBuffer.clear() empties the guild's bucket")

# ---------------------------------------------------------------------------
# Assertion 3 — drain is guild-scoped (other guilds untouched)
# ---------------------------------------------------------------------------
buf.add(_make_event(111, 'donovan ruby'))
buf.add(_make_event(222, 'borin'))
buf.add(_make_event(222, 'lira'))
assert buf.size(111) == 1 and buf.size(222) == 2, "precondition: two guilds populated"
buf.clear(111)
assert buf.size(111) == 0, "cleared guild should be empty"
assert buf.size(222) == 2, "other guild's events must survive — drain is guild-scoped"
print("  ✓ 3. drain is guild-scoped — other guilds untouched")

# ---------------------------------------------------------------------------
# Assertion 4 — buffer accepts new events after clear + consume still works
# (no destructive internal state — clear leaves the buffer fully functional)
# ---------------------------------------------------------------------------
buf.add(_make_event(111, 'donovan ruby'))
assert buf.size(111) == 1, "buffer should accept new events post-clear"
events = buf.consume(111, ['donovan ruby'])
assert len(events) == 1, "consume should pull the post-drain event"
assert buf.size(111) == 0, "consume should leave the bucket empty"
print("  ✓ 4. buffer is fully functional after clear (no destructive state)")

# ---------------------------------------------------------------------------
# Assertion 5 — size() / clear() on never-touched guild are safe (no KeyError)
# ---------------------------------------------------------------------------
fresh_buf = al.RollBuffer()
assert fresh_buf.size(999) == 0, "never-touched guild should return 0, not raise"
fresh_buf.clear(999)
assert fresh_buf.size(999) == 0, "clear on never-touched guild should be a no-op"
print("  ✓ 5. size() / clear() on never-touched guild are safe")

# ---------------------------------------------------------------------------
# Assertion 6 — symptom reproduction from S47-arc recon: 'check' event for
# 'donovan ruby' persists in buffer at !init end. Without drain, next
# Donovan turn's consume surfaces it. With drain, post-clear consume is empty.
# (Live journal evidence: dnd_engine.log 2026-05-11T22:14:58 buffer.consume
#  for actors=['donovan ruby'] returned 1 event after !init end.)
# ---------------------------------------------------------------------------
sim_buf = al.RollBuffer()
sim_guild = 1498592771471314977  # the live test guild from recon evidence
sim_buf.add(_make_event(sim_guild, 'donovan ruby', kind='check'))
assert sim_buf.size(sim_guild) == 1, "precondition: stale check roll in buffer"
sim_buf.clear(sim_guild)  # the new !init end drain step
post_consume = sim_buf.consume(sim_guild, ['donovan ruby'])
assert post_consume == [], \
    f"post-drain consume must be empty, got {post_consume!r} — symptom not fixed"
print("  ✓ 6. S47-arc symptom (stale check roll surfaces post-init-end) is drained")

# ---------------------------------------------------------------------------
# Assertion 7 — idempotency (calling clear twice produces same final state)
# ---------------------------------------------------------------------------
idem_buf = al.RollBuffer()
idem_buf.add(_make_event(555, 'donovan ruby'))
idem_buf.clear(555)
size_after_first = idem_buf.size(555)
idem_buf.clear(555)
size_after_second = idem_buf.size(555)
assert size_after_first == size_after_second == 0, "clear must be idempotent"
print("  ✓ 7. drain is idempotent across repeated calls")

# ---------------------------------------------------------------------------
# Assertion 8 — source-order regression: drain call precedes
# _dispatch_combat_narration inside _handle_init_event evt_type='end' body.
# Verifies §78 layer-1 completion runs prior to S45-F COMBAT_END dispatch
# so the closeout narration's avrae_events stays cleanly empty.
# ---------------------------------------------------------------------------
bot_path = os.path.join(os.path.dirname(__file__), 'discord_dnd_bot.py')
with open(bot_path) as f:
    bot_src = f.read()
end_branch_start = bot_src.find("elif evt_type == 'end' and current_mode == 'combat'")
assert end_branch_start != -1, "could not locate _handle_init_event end branch"
# Scan to end of _handle_init_event (next top-level async def). Was a fixed
# 4000-char window; S50's §78.6 branch pushed the dispatch call past that
# boundary. Dynamic boundary survives future additions to the end branch.
end_branch_stop = bot_src.find("\nasync def ", end_branch_start)
assert end_branch_stop != -1, "could not locate end of _handle_init_event"
end_branch_section = bot_src[end_branch_start:end_branch_stop]
drain_idx = end_branch_section.find("buffer.clear(message.guild.id)")
dispatch_idx = end_branch_section.find("_dispatch_combat_narration(")
assert drain_idx != -1, "buffer.clear(message.guild.id) call missing from end branch"
assert dispatch_idx != -1, "_dispatch_combat_narration call missing from end branch"
assert drain_idx < dispatch_idx, \
    f"drain (idx={drain_idx}) must precede COMBAT_END dispatch (idx={dispatch_idx})"
print("  ✓ 8. drain call precedes _dispatch_combat_narration (source order)")

# ---------------------------------------------------------------------------
# Assertion 9 — source-order regression: drain runs AFTER S45 narrative-
# buffer reset. Keeps layer-1 cleanup contiguous (DB-side first, in-memory
# second — both belong to the same boundary cleanup phase).
# ---------------------------------------------------------------------------
reset_idx = end_branch_section.find(
    "reset_narrative_buffers_on_combat_exit(campaign['id'])"
)
assert reset_idx != -1, \
    "S45 reset_narrative_buffers_on_combat_exit call missing — has it been moved?"
assert reset_idx < drain_idx, \
    f"S45 reset (idx={reset_idx}) must precede new drain (idx={drain_idx})"
print("  ✓ 9. drain runs after S45 narrative-buffer reset (contiguous layer-1)")

# ---------------------------------------------------------------------------
# Assertion 10 — telemetry log format guard. Operator greps for
# `init_end_rollbuffer_drained:` as the canonical drain-fired signal.
# Verify the production log line uses this prefix and carries
# campaign / guild / drained_count fields.
# ---------------------------------------------------------------------------
assert "init_end_rollbuffer_drained:" in end_branch_section, \
    "telemetry log prefix missing — operator grep pattern will break"
assert "drained_count=" in end_branch_section, \
    "telemetry must include drained_count field"
assert "campaign=" in end_branch_section and "guild=" in end_branch_section, \
    "telemetry must include campaign + guild identifiers"
print("  ✓ 10. telemetry log line format is intact (init_end_rollbuffer_drained:)")

print()
print("All 10 S47-arc assertions pass.")
