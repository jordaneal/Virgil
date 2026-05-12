"""Tests for Ship S45-F — COMBAT_END trigger (4th combat-narration kind).

Adds an auto-closeout narration dispatch on !init end, closing the
silence-until-player-types gap revealed by S45 verify. The COMBAT_END
trigger lives in the same dispatch surface as ROUND_START / BLOODIED /
DOWNED (10th §59 sibling extension) — same MUST/MUST-NOT enforcement,
same suppress_for_combat_narration=True information-side discipline.

Run:
    cd /home/jordaneal/scripts && python3 test_combat_narration_combat_end.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import dnd_orchestration as orch


def _combatant(name, hp_current=10, hp_max=10, init=10, conditions='', alive=1):
    return {
        'name': name, 'hp_current': hp_current, 'hp_max': hp_max,
        'init': init, 'conditions': conditions, 'alive': alive,
    }


# ---------------------------------------------------------------------------
# 1. COMBAT_END produces action + transition_context when mode='combat'
# ---------------------------------------------------------------------------
combat_state = {'combatants': [_combatant('Donovan Ruby', 8, 11),
                                _combatant('Goblin', 0, 7, alive=0)]}
scene_state = {'mode': 'combat'}
action, ctx = orch.compute_combat_narration_directive(
    {'kind': 'COMBAT_END'}, combat_state, scene_state)
assert action == "[Combat narration: combat resolves.]", \
    f"unexpected action: {action!r}"
assert ctx, "transition_context must be non-empty"
assert "TRIGGER: combat_end" in ctx
print("  ✓ 1. COMBAT_END produces action + context with mode='combat'")

# ---------------------------------------------------------------------------
# 2. COMBAT_END framing instructs aftermath, NOT continuation
# ---------------------------------------------------------------------------
assert "falling tension" in ctx or "settling" in ctx or "ceasing" in ctx.lower() \
       or "cessation" in ctx
assert "Combat has ended this moment" in ctx
assert "2-3 sentences" in ctx
print("  ✓ 2. COMBAT_END framing is aftermath-oriented, length-bounded")

# ---------------------------------------------------------------------------
# 3. COMBAT_END framing forbids post-combat decision narration
# ---------------------------------------------------------------------------
assert "Do NOT narrate post-combat decisions" in ctx \
    or "post-combat decisions" in ctx
assert "next moves" in ctx
assert "for the player to declare" in ctx
print("  ✓ 3. COMBAT_END framing forbids next-move narration")

# ---------------------------------------------------------------------------
# 4. COMBAT_END framing forbids introducing new combatants/NPCs
# ---------------------------------------------------------------------------
assert "Do NOT introduce any combatant or NPC who is not on the closing" in ctx
assert "thug emerges from the shadows" in ctx, \
    "must reference the specific phantom-NPC failure mode by name"
assert "companions appearing to congratulate" in ctx
print("  ✓ 4. COMBAT_END framing forbids phantom NPC introduction")

# ---------------------------------------------------------------------------
# 5. COMBAT_END roster includes dead/downed combatants with state labels
# ---------------------------------------------------------------------------
assert "Donovan Ruby" in ctx
assert "Goblin" in ctx
# Goblin was alive=0 → should render as dead
assert "dead" in ctx.lower() or "downed" in ctx.lower()
print("  ✓ 5. COMBAT_END roster preserves closing state (alive/dead/downed)")

# ---------------------------------------------------------------------------
# 6. COMBAT_END carries the full MUST/MUST-NOT invariant block
# ---------------------------------------------------------------------------
assert "COMBAT NARRATION INVARIANTS" in ctx
assert "MUST NOT: invent damage numbers" in ctx
assert "atmospheric continuity" in ctx
print("  ✓ 6. COMBAT_END carries full _COMBAT_NARRATION_INVARIANTS block")

# ---------------------------------------------------------------------------
# 7. COMBAT_END gates on scene mode = 'combat' (returns empty otherwise)
# ---------------------------------------------------------------------------
# Note: caller (S45-F dispatch in _handle_init_event) passes
# scene_override={'mode': 'combat'} so the gate passes even though the
# real DB state has already flipped to 'exploration'. Without that
# override, dispatch from real post-mode-flip state would no-op.
action_no_gate, ctx_no_gate = orch.compute_combat_narration_directive(
    {'kind': 'COMBAT_END'}, combat_state, {'mode': 'exploration'})
assert action_no_gate == '' and ctx_no_gate == '', \
    "mode='exploration' should fail the gate (call site provides override)"
print("  ✓ 7. COMBAT_END mode-gate rejects non-combat scenes")

# ---------------------------------------------------------------------------
# 8. log_summary handles COMBAT_END kind
# ---------------------------------------------------------------------------
summary = orch.combat_narration_log_summary({'kind': 'COMBAT_END'}, fired=True)
assert "kind=COMBAT_END" in summary
assert "fired=1" in summary
print("  ✓ 8. combat_narration_log_summary handles COMBAT_END")

# ---------------------------------------------------------------------------
# 9. COMBAT_END is recognized as a valid kind (regression guard on the
# kind whitelist; an unrecognized kind returns empty)
# ---------------------------------------------------------------------------
a, c = orch.compute_combat_narration_directive(
    {'kind': 'COMBAT_BOGUS'}, combat_state, scene_state)
assert a == '' and c == '', "bogus kind should be rejected"
a, c = orch.compute_combat_narration_directive(
    {'kind': 'ROUND_START', 'round': 2}, combat_state, scene_state)
assert a, "ROUND_START still works"
print("  ✓ 9. COMBAT_END is in the kind whitelist; unknown kinds still rejected")

# ---------------------------------------------------------------------------
# 10. Empty roster case (combatants cleared before snapshot — defensive)
# ---------------------------------------------------------------------------
empty_state = {'combatants': []}
a, c = orch.compute_combat_narration_directive(
    {'kind': 'COMBAT_END'}, empty_state, scene_state)
assert a == "[Combat narration: combat resolves.]"
assert "no combatants snapshot" in c or "(no combatants" in c, \
    "empty roster should render a placeholder line, not crash"
print("  ✓ 10. COMBAT_END handles empty roster defensively")

print()
print("All 10 S45-F COMBAT_END assertions pass.")
