"""Tests for Ship S45 — post-`!init end` narrative-buffer reset.

S44 follow-up: mechanical cleanup on !init end (mode flip + clear_combatants
+ clear_active_turn) does not touch the three rolling narrative buffers
(current_scene, last_dm_response, last_player_action), so the next
exploration message reads polluted buffers and the model produces
locally-coherent-but-globally-wrong drift.

Surgical fix: `reset_narrative_buffers_on_combat_exit` writes neutral
closeout text to all three buffers. Called by `_handle_init_event`
evt_type='end' AFTER existing mechanical cleanup.

Run:
    cd /home/jordaneal/scripts && python3 test_init_end_buffer_reset.py
"""

import os
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
    update_scene, update_last_dm_response, update_scene_state,
    set_scene_mode, set_active_turn, clear_active_turn,
    reset_narrative_buffers_on_combat_exit,
    _INIT_END_CLOSEOUT_SCENE, _INIT_END_CLOSEOUT_DM, _INIT_END_CLOSEOUT_PLAYER,
)
import sqlite3


def _make_campaign():
    cid = create_campaign('test-guild-s45', 'S45 Init End Buffer Reset')
    init_scene_state(cid)
    return cid


def _get_current_scene(cid):
    conn = sqlite3.connect(TEST_DB)
    row = conn.execute(
        "SELECT current_scene FROM dnd_campaigns WHERE id=?", (cid,)
    ).fetchone()
    conn.close()
    return row[0] if row else None


def _seed_combat_pollution(cid):
    """Simulate end-of-combat state: all 3 buffers carry combat narration."""
    update_scene(cid, "The clash begins in a hush, lantern light wavering "
                      "as the two figures lock eyes, steel rasping free.")
    update_last_dm_response(cid, "The goblin snarls, its dagger flashing as "
                                 "it lunges for Donovan's exposed flank.")
    update_scene_state(cid, last_player_action="Donovan slashes at the goblin")
    set_scene_mode(cid, 'combat')


# ---------------------------------------------------------------------------
# Assertion 1 — current_scene receives closeout (not stale combat narration)
# ---------------------------------------------------------------------------
cid = _make_campaign()
_seed_combat_pollution(cid)
assert "clash begins" in _get_current_scene(cid), \
    "precondition: combat narration should be in current_scene before reset"
reset_narrative_buffers_on_combat_exit(cid)
post = _get_current_scene(cid)
assert post == _INIT_END_CLOSEOUT_SCENE, \
    f"current_scene should be closeout text, got {post!r}"
assert "clash begins" not in post, "stale combat narration must be overwritten"
print("  ✓ 1. current_scene overwritten with closeout text")

# ---------------------------------------------------------------------------
# Assertion 2 — last_dm_response receives closeout (not stale combat response)
# ---------------------------------------------------------------------------
ss = get_scene_state(cid)
assert ss['last_dm_response'] == _INIT_END_CLOSEOUT_DM, \
    f"last_dm_response should be closeout text, got {ss['last_dm_response']!r}"
assert "goblin snarls" not in ss['last_dm_response'], \
    "stale combat response must be overwritten"
print("  ✓ 2. last_dm_response overwritten with closeout text")

# ---------------------------------------------------------------------------
# Assertion 3 — last_player_action receives marker (not stale combat action)
# ---------------------------------------------------------------------------
assert ss['last_player_action'] == _INIT_END_CLOSEOUT_PLAYER, \
    f"last_player_action should be marker, got {ss['last_player_action']!r}"
assert "slashes" not in ss['last_player_action'], \
    "stale combat action must be overwritten"
print("  ✓ 3. last_player_action overwritten with [combat ended] marker")

# ---------------------------------------------------------------------------
# Assertion 4 — telemetry log fires
# ---------------------------------------------------------------------------
assert any(f"init_end_buffer_reset: campaign={cid}" in m for m in captured_logs), \
    f"expected telemetry log 'init_end_buffer_reset: campaign={cid}' in {captured_logs[-10:]}"
print("  ✓ 4. telemetry init_end_buffer_reset log emitted")

# ---------------------------------------------------------------------------
# Assertion 5 — closeout strings are non-empty and not the fallback opener
# ---------------------------------------------------------------------------
# Empty current_scene triggers `build_dm_context` to fall back to
# "The adventure is just beginning." which would be wrong post-combat.
assert _INIT_END_CLOSEOUT_SCENE.strip() != "", "scene closeout must be non-empty"
assert "adventure is just beginning" not in _INIT_END_CLOSEOUT_SCENE, \
    "closeout must not collide with build_dm_context fallback"
assert "Combat resolves" in _INIT_END_CLOSEOUT_SCENE, \
    "closeout must signal combat resolution"
assert "exploration" in _INIT_END_CLOSEOUT_SCENE.lower(), \
    "closeout must reference mode transition"
print("  ✓ 5. closeout strings are non-empty and distinct from fallback opener")

# ---------------------------------------------------------------------------
# Assertion 6 — idempotency (calling reset twice produces same final state)
# ---------------------------------------------------------------------------
cid2 = _make_campaign()
_seed_combat_pollution(cid2)
reset_narrative_buffers_on_combat_exit(cid2)
snap1_scene = _get_current_scene(cid2)
snap1_ss = get_scene_state(cid2)
reset_narrative_buffers_on_combat_exit(cid2)
snap2_scene = _get_current_scene(cid2)
snap2_ss = get_scene_state(cid2)
assert snap1_scene == snap2_scene, "current_scene must be idempotent across resets"
assert snap1_ss['last_dm_response'] == snap2_ss['last_dm_response'], \
    "last_dm_response must be idempotent"
assert snap1_ss['last_player_action'] == snap2_ss['last_player_action'], \
    "last_player_action must be idempotent"
print("  ✓ 6. reset is idempotent across repeated calls")

# ---------------------------------------------------------------------------
# Assertion 7 — reset works on freshly initialized scene_state (defensive)
# ---------------------------------------------------------------------------
cid3 = _make_campaign()
# No combat pollution seeded — scene_state defaults are all empty/default
reset_narrative_buffers_on_combat_exit(cid3)
ss3 = get_scene_state(cid3)
assert ss3['last_dm_response'] == _INIT_END_CLOSEOUT_DM
assert ss3['last_player_action'] == _INIT_END_CLOSEOUT_PLAYER
assert _get_current_scene(cid3) == _INIT_END_CLOSEOUT_SCENE
print("  ✓ 7. reset works on freshly-initialized scene_state (defensive)")

# ---------------------------------------------------------------------------
# Assertion 8 — closeout marker for player action is bracketed (distinct from
# real player input which would never start with '[' for free-form narration)
# ---------------------------------------------------------------------------
assert _INIT_END_CLOSEOUT_PLAYER.startswith("["), \
    "player-action marker must be bracketed to distinguish from real input"
assert _INIT_END_CLOSEOUT_PLAYER.endswith("]"), \
    "player-action marker must be bracketed (close)"
assert "combat ended" in _INIT_END_CLOSEOUT_PLAYER, \
    "marker must signal what just happened"
print("  ✓ 8. player-action marker is bracketed and signal-clear")

# ---------------------------------------------------------------------------
# Assertion 9 — regression guard: helper imports cleanly + is callable
# ---------------------------------------------------------------------------
import inspect
sig = inspect.signature(reset_narrative_buffers_on_combat_exit)
assert list(sig.parameters.keys()) == ['campaign_id'], \
    f"helper signature changed: {sig}"
return_annotation = sig.return_annotation
assert return_annotation is None, f"helper should return None, got {return_annotation}"
print("  ✓ 9. helper signature (campaign_id) -> None is stable")

# ---------------------------------------------------------------------------
# Assertion 10 — integration: after reset, a subsequent dm_respond-style
# write (simulating next exploration turn) does NOT see stale combat text
# in the buffer (because reset cleared it, subsequent writes start clean)
# ---------------------------------------------------------------------------
cid4 = _make_campaign()
_seed_combat_pollution(cid4)
reset_narrative_buffers_on_combat_exit(cid4)
# Simulate the next exploration-mode `_dm_respond_and_post` call writing to
# current_scene with its own rolling buffer (the S44 pass-3 pattern).
update_scene(cid4, "Last actions: Donovan looks around the bar. | "
                   "DM: The bar is quiet now. Patrons drift back to their drinks.")
post4 = _get_current_scene(cid4)
assert "Combat resolves" not in post4, \
    "next exploration-mode write must fully overwrite the closeout"
assert "clash begins" not in post4, \
    "and must not resurrect the pre-reset combat narration"
assert "bar is quiet" in post4, \
    "new exploration narration must land in the buffer"
print("  ✓ 10. integration: next exploration write overwrites closeout cleanly")

print()
print("All 10 S45 assertions pass.")

# Cleanup
TEST_DB.unlink(missing_ok=True)
