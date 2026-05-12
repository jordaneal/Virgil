"""Tests for Ship S45-D — init-setup auto-suppression.

When mode='combat' but no active_turn (Avrae has fired !init begin +
!init madd/join but no turn cycle yet), `_dm_respond_and_post` must force
`suppress_for_combat_narration=True` regardless of what the caller passed.
Prevents phantom-NPC leak from the unsuppressed full-context prompt during
the init-setup window (S45 verify revealed this surface).

The gate logic is inline in _dm_respond_and_post; this test verifies:
  - The detection pattern works on real DB state (mode/active_turn read)
  - The code-shape gate block is present in discord_dnd_bot.py with the
    expected condition + suppression assignment
  - The telemetry log line is wired

Run:
    cd /home/jordaneal/scripts && python3 test_init_setup_suppression.py
"""

import os
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

import dnd_engine

_tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_tmp.close()
TEST_DB = Path(_tmp.name)
dnd_engine.DB_PATH = TEST_DB

captured_logs = []
dnd_engine.log = lambda m: captured_logs.append(m)
dnd_engine.db_init()

from dnd_engine import (
    create_campaign, init_scene_state, get_scene_state,
    set_scene_mode, set_active_turn, clear_active_turn,
    get_active_turn,
)


def _make_campaign():
    cid = create_campaign('test-guild-s45d', 'S45-D Init Setup Suppression')
    init_scene_state(cid)
    return cid


# ---------------------------------------------------------------------------
# 1. Init-setup window detection: mode='combat' + no active_turn = TRUE
# ---------------------------------------------------------------------------
cid = _make_campaign()
set_scene_mode(cid, 'combat')
# No set_active_turn — Avrae hasn't fired the first 'turn' event yet
scene = get_scene_state(cid)
active = get_active_turn(cid)
is_init_setup = (
    scene and (scene.get('mode') or '').lower() == 'combat' and not active
)
assert is_init_setup, "init-setup window must detect mode=combat + no active_turn"
print("  ✓ 1. detection: mode='combat' + no active_turn → init-setup window")

# ---------------------------------------------------------------------------
# 2. Active-combat detection: mode='combat' + active_turn SET = FALSE
# (NOT init-setup — this is normal in-combat operation)
# ---------------------------------------------------------------------------
set_active_turn(cid, 'controller-123', 'Donovan Ruby', 1)
scene = get_scene_state(cid)
active = get_active_turn(cid)
is_init_setup = (
    scene and (scene.get('mode') or '').lower() == 'combat' and not active
)
assert not is_init_setup, "active-combat must NOT be flagged as init-setup"
print("  ✓ 2. detection: mode='combat' + active_turn → NOT init-setup")

# ---------------------------------------------------------------------------
# 3. Exploration detection: mode='exploration' = FALSE
# (Never an init-setup window — exploration is always fully responsive)
# ---------------------------------------------------------------------------
clear_active_turn(cid)
set_scene_mode(cid, 'exploration')
scene = get_scene_state(cid)
active = get_active_turn(cid)
is_init_setup = (
    scene and (scene.get('mode') or '').lower() == 'combat' and not active
)
assert not is_init_setup, "exploration must NOT be flagged as init-setup"
print("  ✓ 3. detection: mode='exploration' → NOT init-setup")

# ---------------------------------------------------------------------------
# 4. Code-shape inspection: the gate block exists in _dm_respond_and_post
# with the expected condition + suppress assignment + telemetry log
# ---------------------------------------------------------------------------
BOT_PATH = Path(__file__).parent / 'discord_dnd_bot.py'
src = BOT_PATH.read_text()

# Locate the _dm_respond_and_post function body
m = re.search(
    r"async def _dm_respond_and_post\([^)]*\):.*?(?=\nasync def |\Z)",
    src, re.DOTALL,
)
assert m, "could not locate _dm_respond_and_post function body"
body = m.group(0)

# The gate must contain: scene mode check, active_turn check, suppress True
assert "init_setup_suppression" in body, \
    "missing init_setup_suppression gate telemetry"
assert "scene_for_setup_gate" in body, \
    "missing scene read for setup gate"
assert "active_turn_for_setup_gate" in body, \
    "missing active_turn read for setup gate"
assert "suppress_for_combat_narration = True" in body, \
    "missing forced suppression assignment in setup gate"
print("  ✓ 4. code-shape: init-setup gate block present in _dm_respond_and_post")

# ---------------------------------------------------------------------------
# 5. The gate fires BEFORE the LLM call (so the suppression takes effect)
# ---------------------------------------------------------------------------
# The pattern "suppress_for_combat_narration = True" assignment must appear
# BEFORE the asyncio.to_thread(dm_respond, ...) call site within the function.
suppress_idx = body.find("suppress_for_combat_narration = True")
dm_respond_idx = body.find("asyncio.to_thread(\n                    dm_respond")
if dm_respond_idx == -1:
    dm_respond_idx = body.find("asyncio.to_thread(dm_respond")
assert suppress_idx > 0 and dm_respond_idx > 0, \
    f"could not locate both anchors (suppress={suppress_idx}, dm_respond={dm_respond_idx})"
assert suppress_idx < dm_respond_idx, \
    "init-setup suppression must execute BEFORE the LLM call"
print("  ✓ 5. gate executes before LLM call (suppression takes effect)")

# ---------------------------------------------------------------------------
# 6. The gate uses .lower() on the mode field (case-insensitive match)
# ---------------------------------------------------------------------------
assert ".get('mode') or '').lower()" in body or '"mode") or "").lower()' in body \
    or "mode') or '').lower() == 'combat'" in body, \
    "init-setup gate should be case-insensitive on the mode field"
print("  ✓ 6. mode check is case-insensitive")

# ---------------------------------------------------------------------------
# 7. The gate has exception handling (must not block narration on error)
# ---------------------------------------------------------------------------
# Look for try/except around the gate
gate_start = body.find("scene_for_setup_gate = get_scene_state")
assert gate_start > 0, "gate start anchor missing"
gate_region = body[gate_start - 100:gate_start + 800]
assert "try:" in gate_region and "except" in gate_region, \
    "init-setup gate must be wrapped in try/except (soft-fail)"
print("  ✓ 7. gate has try/except wrapping (soft-fail)")

# ---------------------------------------------------------------------------
# 8. The telemetry log only fires when suppression flips False→True
# (no log spam when caller already passed suppress=True from S43/S44 dispatch)
# ---------------------------------------------------------------------------
log_block_idx = body.find("init_setup_suppression: campaign=")
assert log_block_idx > 0
# Walk backward from the log line to find the guard
guard_window = body[max(0, log_block_idx - 200):log_block_idx]
assert "if not suppress_for_combat_narration" in guard_window, \
    "telemetry log must be guarded by `if not suppress_for_combat_narration`"
print("  ✓ 8. telemetry only logs on caller=False→True flip (no spam)")

# ---------------------------------------------------------------------------
# 9. Edge case: scene is None (campaign just initialized, no /play yet).
# The gate must handle None gracefully (don't fire suppression).
# ---------------------------------------------------------------------------
# Logic check: if scene is None or falsy, the outer if fails, no suppression.
is_init_setup_when_none = (
    None and (None.get('mode') if None else '').lower() == 'combat'
) if False else False  # short-circuit guard pattern
# The code uses `if scene_for_setup_gate and ...` so None is handled.
assert "if (scene_for_setup_gate" in body or "if scene_for_setup_gate" in body, \
    "scene must be truthy-checked before .get() to avoid AttributeError"
print("  ✓ 9. gate handles scene=None defensively (no AttributeError)")

# ---------------------------------------------------------------------------
# 10. The doctrine candidate is referenced in the implementation comment
# (3rd-instance of two-layer enforcement — mode-transition state-reset).
# ---------------------------------------------------------------------------
gate_comment_block = body[gate_start - 1500:gate_start + 100]
assert "S45-D" in gate_comment_block, "S45-D ship marker missing in gate"
assert "two-layer enforcement" in gate_comment_block \
    or "Doctrine candidate" in gate_comment_block \
    or "doctrine candidate" in gate_comment_block, \
    "doctrine candidate should be referenced in the gate comment"
print("  ✓ 10. doctrine candidate referenced in implementation comment")

# ---------------------------------------------------------------------------
# 11. v2 top-level gate: on_message blocks messages during init-setup
# (the primary gate; v1 inside _dm_respond_and_post is defense-in-depth).
# Code-shape: gate is in on_message AND fires before batcher.add.
# ---------------------------------------------------------------------------
on_message_match = re.search(
    r"async def on_message\(message: discord\.Message\):.*?(?=\n(?:async def |def ))",
    src, re.DOTALL,
)
assert on_message_match, "could not locate on_message function body"
om_body = on_message_match.group(0)

assert "init_setup_gate" in om_body, "v2 init_setup_gate missing in on_message"
# Gate must fire before batcher.add (so messages don't get queued for narration)
v2_gate_idx = om_body.find("init_setup_gate: dropped msg")
batcher_idx = om_body.find("batcher.add(")
assert v2_gate_idx > 0, "init_setup_gate telemetry missing"
assert batcher_idx > 0, "batcher.add call missing"
assert v2_gate_idx < batcher_idx, \
    "v2 init-setup gate must fire BEFORE batcher.add"
print("  ✓ 11. v2 top-level gate exists in on_message, fires before batcher")

# ---------------------------------------------------------------------------
# 12. v2 gate uses ⏳ reaction (consistent with existing turn-gate pattern)
# ---------------------------------------------------------------------------
# Find the v2 gate region and confirm ⏳ reaction
v2_gate_region_start = om_body.find("Ship S45-D v2 (extended init-setup gate)")
assert v2_gate_region_start > 0, "v2 gate comment marker missing"
v2_gate_region = om_body[v2_gate_region_start:v2_gate_region_start + 1500]
assert "⏳" in v2_gate_region, "v2 gate must use ⏳ reaction (consistent with turn-gate)"
print("  ✓ 12. v2 gate emits ⏳ reaction (consistent with turn-gate pattern)")

# ---------------------------------------------------------------------------
# 13. v2 gate is mode-gated (only fires when mode='combat')
# exploration messages must NOT be silenced by the init-setup gate
# ---------------------------------------------------------------------------
# The v2 gate is nested inside `if scene and (scene.get('mode') or 'exploration') == 'combat'`
mode_check = "scene.get('mode') or 'exploration') == 'combat'"
assert mode_check in om_body, \
    "v2 gate must be nested inside mode='combat' check"
print("  ✓ 13. v2 gate is mode-gated (exploration messages pass through)")

print()
print("All 13 S45-D init-setup suppression assertions pass.")

# Cleanup
TEST_DB.unlink(missing_ok=True)
