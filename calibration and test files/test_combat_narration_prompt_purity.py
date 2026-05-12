"""Tests for Ship S44 — combat narration prompt purity v1.x.

Patches the ROUND_START phantom-NPC + stale-narrative-bleed surfaced in
S43 live verify. Adds `suppress_for_combat_narration: bool = False`
parameter threaded through `_dispatch_combat_narration` → `_dm_respond_and_post`
→ `dm_respond` → `build_dm_context`. When True:
  - `=== RELEVANT PAST EVENTS ===` chroma retrieval block is dropped
  - `Recently active NPCs:` line inside SCENE STATE block is dropped
All other blocks remain. Default False preserves pre-S44 behavior.

Doctrine §77 atmospheric-continuity line is UNAFFECTED — this is the
information-side enforcement layer complementing the instruction-side
MUST/MUST-NOT clauses in `_COMBAT_NARRATION_INVARIANTS`.

Run:
    cd /home/jordaneal/scripts && python3 test_combat_narration_prompt_purity.py
"""

import os
import sys
import sqlite3
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

import dnd_engine

_tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_tmp.close()
TEST_DB = Path(_tmp.name)
dnd_engine.DB_PATH = TEST_DB

captured = []
dnd_engine.log = lambda m: captured.append(m)
dnd_engine.db_init()

from dnd_engine import (
    build_dm_context, create_campaign, npc_upsert,
)


def _make_campaign():
    """Insert a campaign + a recently-mentioned NPC so the recent_npcs
    block has non-empty content (in default unsuppressed path)."""
    cid = create_campaign('test-guild-s44', 'S44 Combat Narration Purity')
    # Seed a couple of NPCs so get_recently_active_npcs returns content
    # when called from build_dm_context (default path).
    npc_upsert(cid, 'PhantomEldrin', role='companion', skeleton_origin=False)
    npc_upsert(cid, 'PhantomBorin', role='companion', skeleton_origin=False)
    return {
        'id': cid, 'name': 'S44 Combat Narration Purity',
        'guild_id': 'test-guild-s44', 'tone': '',
        'current_scene': '', 'world_notes': '',
    }


CHARS = [{
    'id': 1, 'name': 'Donovan Ruby', 'race': 'Dwarf',
    'class': 'Rogue', 'level': 3, 'controller': '12345',
}]

SCENE_STATE = {
    'campaign_id': None,  # filled per-test
    'mode': 'combat',
    'last_player_action': 'I attack the goblin',
    'tension_int': 50,
    'progress_clocks': [],
    'current_location_id': None,
    'location_label': 'Test Tavern',
    'campaign_day': 1,
    'day_phase': 'Morning',
    'turn_counter': 1,
    'last_dm_response': '',
    'last_active_actor': 'Donovan Ruby',
}


# ─── suppress_for_combat_narration=True drops both target blocks ──

def test_suppression_drops_relevant_past_events_block():
    """When True, the `=== RELEVANT PAST EVENTS ===` chroma block must
    not appear in the assembled prompt — even when relevant_history is
    non-empty (which it would be in production for nearly all turns)."""
    captured.clear()
    campaign = _make_campaign()
    scene = dict(SCENE_STATE, campaign_id=campaign['id'])
    relevant = (
        "The goblin's limp form collapsed and a dark stain spreading from "
        "its wound. Borin's axe hangs heavy. Eldrin stands poised."
    )
    prompt = build_dm_context(
        campaign, CHARS,
        relevant_history=relevant,
        scene_state=scene,
        mode='combat',
        suppress_for_combat_narration=True,
    )
    assert '=== RELEVANT PAST EVENTS ===' not in prompt, (
        "chroma retrieval block should be suppressed when "
        "suppress_for_combat_narration=True; this is the load-bearing "
        "fix for S43's stale-narrative bleed"
    )
    # Confirm the actual stale-narrative text is not in the prompt
    assert "goblin's limp form collapsed" not in prompt
    assert "Borin's axe hangs heavy" not in prompt
    assert "Eldrin stands poised" not in prompt


def test_suppression_drops_recently_active_npcs_line():
    """When True, the `Recently active NPCs:` line in SCENE STATE block
    must not appear — phantom-NPC fix for S43's ROUND_START drift."""
    captured.clear()
    campaign = _make_campaign()
    scene = dict(SCENE_STATE, campaign_id=campaign['id'])
    prompt = build_dm_context(
        campaign, CHARS,
        scene_state=scene,
        mode='combat',
        suppress_for_combat_narration=True,
    )
    assert 'Recently active NPCs:' not in prompt, (
        "recent_npcs line should be suppressed when "
        "suppress_for_combat_narration=True"
    )
    # Phantom NPCs should not appear by name (we seeded them)
    assert 'PhantomEldrin' not in prompt
    assert 'PhantomBorin' not in prompt
    # Telemetry confirms suppression took the suppression branch
    suppression_logs = [
        m for m in captured
        if 'reason=combat_narration_suppressed' in m
    ]
    assert len(suppression_logs) >= 1, (
        f"expected at least one combat_narration_suppressed log line; "
        f"got {captured[-5:]}"
    )


# ─── Default (False) preserves prior behavior ───────────────────────

def test_default_unsuppressed_includes_relevant_past_events():
    """Regression guard: when suppress_for_combat_narration defaults to
    False (any non-combat-narration call site), the chroma retrieval
    block remains in the prompt. Pre-S44 behavior preserved."""
    captured.clear()
    campaign = _make_campaign()
    scene = dict(SCENE_STATE, campaign_id=campaign['id'])
    relevant = "Previous turn narration content here."
    prompt = build_dm_context(
        campaign, CHARS,
        relevant_history=relevant,
        scene_state=scene,
        mode='exploration',
    )
    assert '=== RELEVANT PAST EVENTS ===' in prompt
    assert 'Previous turn narration content here.' in prompt


def test_default_unsuppressed_includes_recently_active_npcs():
    """Regression guard: default (False) preserves the recent_npcs line
    when NPCs have been mentioned recently. Non-combat-narration callers
    keep full context."""
    captured.clear()
    campaign = _make_campaign()
    scene = dict(SCENE_STATE, campaign_id=campaign['id'])
    prompt = build_dm_context(
        campaign, CHARS,
        scene_state=scene,
        mode='exploration',
    )
    # Default path should query get_recently_active_npcs (telemetry
    # confirms — non-suppressed log line shape)
    npcs_logs = [
        m for m in captured
        if 'npcs_in_context:' in m
        and 'reason=combat_narration_suppressed' not in m
    ]
    assert len(npcs_logs) >= 1, (
        "default path should run get_recently_active_npcs and emit the "
        "standard npcs_in_context: log"
    )


# ─── Scene-state core remains under suppression ─────────────────────

def test_suppression_preserves_scene_state_block():
    """SCENE STATE block as a whole must remain — Location, Tension,
    last_player_action all preserved per Ship 2 canon. Only the
    `Recently active NPCs:` line is dropped."""
    captured.clear()
    campaign = _make_campaign()
    scene = dict(SCENE_STATE, campaign_id=campaign['id'])
    prompt = build_dm_context(
        campaign, CHARS,
        scene_state=scene,
        mode='combat',
        suppress_for_combat_narration=True,
    )
    assert '=== SCENE STATE (authoritative) ===' in prompt
    assert 'Location:' in prompt
    assert 'Tension:' in prompt
    assert 'Last player action:' in prompt


def test_suppression_preserves_combat_directive_blocks():
    """All directive blocks (pacing, persistence, init, etc.) flow through
    their own params and are unaffected by the suppression flag. Spot-check
    that a passed-through transition_context analog (resolution_block)
    still appears."""
    captured.clear()
    campaign = _make_campaign()
    scene = dict(SCENE_STATE, campaign_id=campaign['id'])
    prompt = build_dm_context(
        campaign, CHARS,
        scene_state=scene,
        mode='combat',
        suppress_for_combat_narration=True,
        resolution_block='=== AUTHORITATIVE ROLL RESOLUTION ===\nOutcome: PASSED',
    )
    # resolution_block is just one example — confirms suppression flag
    # doesn't bleed into other directive paths
    assert 'AUTHORITATIVE ROLL RESOLUTION' in prompt
    assert 'Outcome: PASSED' in prompt


# ─── Two-layer enforcement composition observation guard ───────────

# ─── S44 verify-pass-2: expanded suppression set ───────────────────

def test_suppression_drops_dm_pacing_examples_block():
    """S44 verify-pass-2 finding: dm_guidance (chroma knowledge-base
    retrieval) was the residual bleed source after the first patch.
    `=== DM PACING EXAMPLES ===` block must be dropped under suppression."""
    captured.clear()
    campaign = _make_campaign()
    scene = dict(SCENE_STATE, campaign_id=campaign['id'])
    guidance = "Example: the orc bellows, swinging its axe in a brutal arc..."
    prompt = build_dm_context(
        campaign, CHARS,
        dm_guidance=guidance,
        scene_state=scene,
        mode='combat',
        suppress_for_combat_narration=True,
    )
    assert '=== DM PACING EXAMPLES ===' not in prompt
    assert 'the orc bellows' not in prompt


def test_suppression_drops_traveling_companions_block():
    """S44 verify-pass-2 finding: companions_section is the actual phantom-NPC
    source (Lira/Borin/Eldrin live in dnd_companions, not recent_npcs).
    `=== TRAVELING COMPANIONS ===` must be dropped under suppression."""
    captured.clear()
    campaign = _make_campaign()
    # Seed a companion that would otherwise appear
    conn = sqlite3.connect(TEST_DB)
    conn.execute(
        "INSERT INTO dnd_companions "
        "(campaign_id, name, persona, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (campaign['id'], 'PhantomLira', 'a bard', '2026-05-11', '2026-05-11'),
    )
    conn.commit()
    conn.close()
    scene = dict(SCENE_STATE, campaign_id=campaign['id'])
    prompt = build_dm_context(
        campaign, CHARS,
        scene_state=scene,
        mode='combat',
        suppress_for_combat_narration=True,
    )
    assert '=== TRAVELING COMPANIONS ===' not in prompt
    assert 'PhantomLira' not in prompt


def test_suppression_drops_active_quests_block():
    """quests_section can bleed quest titles/summaries/given-by NPCs into
    combat narration; suppressed under combat narration."""
    captured.clear()
    campaign = _make_campaign()
    conn = sqlite3.connect(TEST_DB)
    conn.execute(
        "INSERT INTO dnd_quests "
        "(campaign_id, title, summary, status, priority, given_by, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (campaign['id'], 'PhantomQuestTitle', 'a campaign-arc summary',
         'active', 'urgent', 'PhantomNPC', '2026-05-11', '2026-05-11'),
    )
    conn.commit()
    conn.close()
    scene = dict(SCENE_STATE, campaign_id=campaign['id'])
    prompt = build_dm_context(
        campaign, CHARS,
        scene_state=scene,
        mode='combat',
        suppress_for_combat_narration=True,
    )
    assert '=== ACTIVE QUESTS ===' not in prompt
    assert 'PhantomQuestTitle' not in prompt
    assert 'PhantomNPC' not in prompt
    assert 'campaign-arc summary' not in prompt


def test_suppression_drops_inventory_block():
    """inventory_section can bleed item names (e.g. 'silver key') into combat
    narration; suppressed under combat narration."""
    captured.clear()
    campaign = _make_campaign()
    conn = sqlite3.connect(TEST_DB)
    conn.execute(
        "INSERT INTO dnd_inventory "
        "(campaign_id, character_name, item_name, quantity, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (campaign['id'], 'Donovan Ruby', 'phantom_silver_key', 1, '2026-05-11'),
    )
    conn.commit()
    conn.close()
    scene = dict(SCENE_STATE, campaign_id=campaign['id'])
    prompt = build_dm_context(
        campaign, CHARS,
        scene_state=scene,
        mode='combat',
        acting_character_names=['Donovan Ruby'],
        suppress_for_combat_narration=True,
    )
    assert "NOTABLE ITEMS" not in prompt
    assert 'phantom_silver_key' not in prompt


def test_suppression_drops_central_thread_block():
    """central_thread_block carries campaign-arc directional pressure;
    irrelevant for combat round-top, bleeds non-combat narrative."""
    captured.clear()
    campaign = _make_campaign()
    scene = dict(SCENE_STATE, campaign_id=campaign['id'])
    prompt = build_dm_context(
        campaign, CHARS,
        scene_state=scene,
        mode='combat',
        central_thread_directive='Pursue the dragon cult to its root.',
        suppress_for_combat_narration=True,
    )
    assert '=== CENTRAL THREAD ===' not in prompt
    assert 'dragon cult' not in prompt


def test_suppression_drops_pending_consequences_block():
    """consequence_block surfaces per-NPC pressure framing (threats/promises/
    etc.) — surfaces non-combatant NPC pressures during combat narration."""
    captured.clear()
    campaign = _make_campaign()
    scene = dict(SCENE_STATE, campaign_id=campaign['id'])
    prompt = build_dm_context(
        campaign, CHARS,
        scene_state=scene,
        mode='combat',
        consequence_directive='PhantomConsequenceNPC threatens vengeance...',
        suppress_for_combat_narration=True,
    )
    assert '=== PENDING CONSEQUENCES ===' not in prompt
    assert 'PhantomConsequenceNPC' not in prompt


def test_suppression_drops_unresolved_commitment_block():
    """commitment_block tracks prior-turn unresolved action; bleeds
    prior-turn narrative content into combat-state-transition triggers."""
    captured.clear()
    campaign = _make_campaign()
    scene = dict(SCENE_STATE, campaign_id=campaign['id'])
    prompt = build_dm_context(
        campaign, CHARS,
        scene_state=scene,
        mode='combat',
        commitment_directive='Player committed to ATTACK action; resolve before scene-shift.',
        suppress_for_combat_narration=True,
    )
    assert '=== UNRESOLVED COMMITMENT ===' not in prompt
    assert 'committed to ATTACK' not in prompt


def test_default_unsuppressed_preserves_all_expanded_blocks():
    """Regression guard: when suppress_for_combat_narration=False (default,
    non-combat-narration callers), ALL the newly-suppressed blocks still
    render as before. Pre-S44 behavior for non-combat callers preserved."""
    captured.clear()
    campaign = _make_campaign()
    scene = dict(SCENE_STATE, campaign_id=campaign['id'])
    prompt = build_dm_context(
        campaign, CHARS,
        dm_guidance='example guidance prose',
        scene_state=scene,
        mode='exploration',
        central_thread_directive='Pursue the cult.',
        consequence_directive='NPC threatens.',
        commitment_directive='Prior commitment.',
    )
    # All blocks present in default path
    assert '=== DM PACING EXAMPLES ===' in prompt
    assert '=== CENTRAL THREAD ===' in prompt
    assert '=== PENDING CONSEQUENCES ===' in prompt
    assert '=== UNRESOLVED COMMITMENT ===' in prompt


def test_suppression_drops_current_scene_rolling_buffer():
    """S44 verify-pass-3 finding: `=== CURRENT SCENE ===` block carries
    `campaign.current_scene` which is a rolling-narration buffer
    (written after every _dm_respond_and_post as
    'Last actions: ... | DM: ...'). This was the residual leak after
    the 9-block expansion — combat narration's prior round-start output
    was being re-injected as 'current scene' on the next round-start."""
    captured.clear()
    campaign = _make_campaign()
    # Simulate the rolling buffer's typical content shape — prior turn's
    # narration text after a combat round.
    conn = sqlite3.connect(TEST_DB)
    conn.execute(
        "UPDATE dnd_campaigns SET current_scene=? WHERE id=?",
        ("Last actions: [Combat narration: round 1 starts.] | DM: The "
         "lute's lingering chord hangs over the bar, the lantern light "
         "catching the scarred hide of the blood-ied goblin.",
         campaign['id']),
    )
    conn.commit()
    conn.close()
    # Re-fetch campaign so the helper has the updated current_scene
    conn = sqlite3.connect(TEST_DB)
    row = conn.execute(
        "SELECT id, name, current_scene, world_notes, tone, guild_id "
        "FROM dnd_campaigns WHERE id=?", (campaign['id'],)
    ).fetchone()
    conn.close()
    campaign_fresh = {
        'id': row[0], 'name': row[1], 'current_scene': row[2],
        'world_notes': row[3], 'tone': row[4] or '',
        'guild_id': row[5] or 'test-guild-s44',
    }
    scene = dict(SCENE_STATE, campaign_id=campaign['id'])

    prompt = build_dm_context(
        campaign_fresh, CHARS,
        scene_state=scene,
        mode='combat',
        suppress_for_combat_narration=True,
    )
    assert '=== CURRENT SCENE ===' not in prompt, (
        "current_scene block must be suppressed during combat narration "
        "— it's a rolling-narration buffer that re-injects prior combat "
        "narration text"
    )
    # The specific leak phrase must be absent
    assert "lute's lingering chord" not in prompt
    assert 'blood-ied goblin' not in prompt
    assert "Last actions:" not in prompt


def test_default_unsuppressed_preserves_current_scene_block():
    """Regression guard: non-combat-narration callers still get the
    `=== CURRENT SCENE ===` block."""
    captured.clear()
    campaign = _make_campaign()
    conn = sqlite3.connect(TEST_DB)
    conn.execute(
        "UPDATE dnd_campaigns SET current_scene=? WHERE id=?",
        ("A dimly lit tavern.", campaign['id']),
    )
    conn.commit()
    conn.close()
    conn = sqlite3.connect(TEST_DB)
    row = conn.execute(
        "SELECT id, name, current_scene, world_notes, tone, guild_id "
        "FROM dnd_campaigns WHERE id=?", (campaign['id'],)
    ).fetchone()
    conn.close()
    campaign_fresh = {
        'id': row[0], 'name': row[1], 'current_scene': row[2],
        'world_notes': row[3], 'tone': row[4] or '',
        'guild_id': row[5] or 'test-guild-s44',
    }
    scene = dict(SCENE_STATE, campaign_id=campaign['id'])
    prompt = build_dm_context(
        campaign_fresh, CHARS,
        scene_state=scene,
        mode='exploration',
    )
    assert '=== CURRENT SCENE ===' in prompt
    assert 'A dimly lit tavern.' in prompt


def test_two_layer_enforcement_holds_together():
    """S44 information-side enforcement (this ship) complements S43
    instruction-side enforcement (the MUST/MUST-NOT clauses in
    _COMBAT_NARRATION_INVARIANTS). This test asserts the composition is
    structurally sound: combat narration callers get BOTH suppressed
    context AND the MUST/MUST-NOT clauses in the same prompt build.

    The clauses themselves live in dnd_orchestration's
    compute_combat_narration_directive return value (transition_context),
    not in build_dm_context's prompt block. So we verify that under
    suppression, the (transition_context-side) clauses would still apply
    intact alongside the information-side trim."""
    import dnd_orchestration as orch
    trigger = {'kind': 'ROUND_START', 'round': 1}
    combat_state = {'combatants': [
        {'name': 'Donovan Ruby', 'hp_current': 11, 'hp_max': 13,
         'init': 14, 'alive': 1},
        {'name': 'TestGoblin', 'hp_current': 13, 'hp_max': 13,
         'init': 10, 'alive': 1},
    ]}
    _, transition_context = orch.compute_combat_narration_directive(
        trigger, combat_state, {'mode': 'combat'},
    )
    # Instruction-side enforcement (S43): the MUST/MUST-NOT clauses
    assert 'COMBAT NARRATION INVARIANTS' in transition_context
    assert 'MUST NOT: introduce or narrate actions for any combatant NOT in the init roster' in transition_context
    # Information-side enforcement (S44): build_dm_context skips bleed blocks
    captured.clear()
    campaign = _make_campaign()
    scene = dict(SCENE_STATE, campaign_id=campaign['id'])
    relevant = "Stale combat narrative from a prior fight."
    prompt = build_dm_context(
        campaign, CHARS,
        relevant_history=relevant,
        scene_state=scene,
        mode='combat',
        suppress_for_combat_narration=True,
    )
    assert '=== RELEVANT PAST EVENTS ===' not in prompt
    assert 'Recently active NPCs:' not in prompt


# ─── Cleanup ────────────────────────────────────────────────────────

def _cleanup():
    try:
        TEST_DB.unlink()
    except OSError:
        pass


# ─── Run ────────────────────────────────────────────────────────────

if __name__ == '__main__':
    failures = []
    funcs = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for fn in funcs:
        try:
            fn()
            print(f"  ok   {fn.__name__}")
        except AssertionError as e:
            failures.append((fn.__name__, str(e)))
            print(f"  FAIL {fn.__name__}: {e}")
        except Exception as e:
            failures.append((fn.__name__, repr(e)))
            print(f"  ERR  {fn.__name__}: {e!r}")
    _cleanup()
    if failures:
        print(f"\n{len(failures)} failure(s)")
        sys.exit(1)
    print(f"\n{len(funcs)} tests passed.")
