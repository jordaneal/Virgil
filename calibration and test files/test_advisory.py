"""Tests for OOC Advisory Lane (Track 6 #3) + Command Reference (Track 6 #3.1).

Covers:
  - build_advisory_context: pure-function state assembly
  - advisory_log_summary: telemetry shape
  - Empty/missing state handling
  - No chroma writes / no engine writers in the advisory pure-function path
  - Cross-campaign isolation (function takes pre-fetched per-campaign data)
  - Long-input handling
  - _load_commands_reference: graceful read + missing-file degrade
  - AVAILABLE COMMANDS block presence/absence in build_advisory_context

Run:
    cd /home/jordaneal/scripts && python3 test_advisory.py
"""

import sys
import tempfile
import unittest.mock as mock
from pathlib import Path

sys.path.insert(0, '/home/jordaneal/scripts')

import dnd_orchestration as orch


# ─── Constant + prompt shape ─────────────────────────────────────────

def test_advisory_system_prompt_exists():
    assert isinstance(orch.ADVISORY_SYSTEM_PROMPT, str)
    assert len(orch.ADVISORY_SYSTEM_PROMPT) > 200


def test_advisory_prompt_forbids_avrae_emission():
    p = orch.ADVISORY_SYSTEM_PROMPT
    assert '!' in p  # mentions `!attack` etc. as PLAYER options
    # Must spell out: do not emit yourself
    assert 'DO NOT emit them' in p or 'Do not emit' in p


def test_advisory_prompt_says_ooc_not_narration():
    """S65 Fix 4 — verify the hard-fork framing makes it clear this is
    an out-of-fiction channel. The literal 'OOC' acronym was retired in
    favor of explicit phrasing ('not in-character', 'NOT speaking to a
    player', 'operator-facing not in-fiction'). The intent is preserved
    structurally — the prompt must clearly establish OOC posture without
    relying on a single acronym."""
    p = orch.ADVISORY_SYSTEM_PROMPT
    # Must clearly establish out-of-fiction posture
    p_lower = p.lower()
    assert 'not in-character' in p_lower or 'out-of-character' in p_lower, \
        "ADVISORY_SYSTEM_PROMPT must mark itself as not-in-character"
    # Must clarify this is an aside / OOC channel (not gameplay narration)
    assert 'aside' in p_lower or 'operator-facing' in p_lower or 'not in-fiction' in p_lower
    # Must explicitly forbid narrating scene events
    assert 'do not narrate' in p_lower or 'not narrate scene' in p_lower


def test_advisory_prompt_warns_against_state_mutation():
    p = orch.ADVISORY_SYSTEM_PROMPT
    assert 'mutate' in p or 'advance time' in p


# ─── build_advisory_context — populated state ────────────────────────

def test_build_context_full_state():
    campaign = {'id': 1, 'name': 'Cinderhollow', 'tone': 'noir'}
    # Ship 2 (S39) — `location` freetext column was dropped; reads route
    # through `location_label` (FK-derived from dnd_locations). Pre-S65
    # this fixture passed `location: 'Old Mill'` and the advisory builder
    # silently dropped it (test was checking a stale field shape).
    scene = {
        'mode': 'combat',
        'location_label': 'Old Mill',
        'last_player_action': 'Maelin draws her bow.',
    }
    active_turn = {'character_name': 'Maelin', 'controller_id': 'u1', 'round': 2}
    combatants = {
        'combatants': [
            {'name': 'Maelin', 'init': 18, 'hp_current': 22, 'hp_max': 30,
             'conditions': '', 'alive': 1, 'side': 'pc'},
            {'name': 'Goblin A', 'init': 14, 'hp_current': 0, 'hp_max': 12,
             'conditions': '', 'alive': 0, 'side': 'npc'},
            {'name': 'Goblin B', 'init': 11, 'hp_current': 8, 'hp_max': 12,
             'conditions': 'frightened', 'alive': 1, 'side': 'npc'},
        ],
        'snapshot_age_s': 30.0,
    }
    inventory = [
        {'item_name': 'silver key', 'quantity': 1, 'metadata': '',
         'created_at': '2026-05-01T00:00:00'},
        {'item_name': 'healing potion', 'quantity': 2, 'metadata': '',
         'created_at': '2026-05-01T00:00:00'},
    ]
    pending = [
        {'creature': 'Goblin A', 'items': ['shortbow'],
         'coin': {'amount': 7, 'denom': 'sp'}},
    ]

    out = orch.build_advisory_context(
        campaign=campaign,
        bound_character_name='Maelin',
        scene_state=scene,
        active_turn=active_turn,
        combatants_snapshot=combatants,
        inventory=inventory,
        pending_loot=pending,
    )

    # Sanity: structured + factual
    assert 'STATE REFERENCE' in out
    assert 'Cinderhollow' in out
    assert 'Maelin' in out
    assert 'Mode: combat' in out
    assert 'Old Mill' in out
    assert 'Active turn: Maelin' in out
    assert 'round 2' in out
    assert 'Goblin A' in out
    assert 'DOWN' in out  # alive=0 surfaced
    assert 'frightened' in out  # conditions surfaced
    assert 'silver key' in out
    assert 'healing potion' in out
    assert 'Pending loot' in out


def test_build_context_combat_active_turn_only_renders_in_combat():
    # Outside combat, no active_turn passed
    scene = {'mode': 'exploration', 'location': 'Marketplace'}
    out = orch.build_advisory_context(
        campaign={'id': 1, 'name': 'X'},
        bound_character_name='Maelin',
        scene_state=scene,
        active_turn=None,
        combatants_snapshot={'combatants': [], 'snapshot_age_s': None},
        inventory=[],
        pending_loot=[],
    )
    assert 'Mode: exploration' in out
    assert 'Active turn:' not in out


# ─── Empty / missing state ───────────────────────────────────────────

def test_build_context_empty_campaign():
    out = orch.build_advisory_context(
        campaign=None,
        bound_character_name=None,
        scene_state=None,
        active_turn=None,
        combatants_snapshot=None,
        inventory=None,
        pending_loot=None,
    )
    assert 'Campaign: (none active)' in out
    # S65 Fix 4 — phrasing changed from "Asking player's character" to
    # "Bound character" under the role-as-DM framing. The "(none)" sentinel
    # remains; tests now assert on the new phrasing.
    assert 'Bound character: (none)' in out
    assert 'Mode: (no scene started)' in out
    assert 'Inventory: (empty)' in out


def test_build_context_no_inventory():
    out = orch.build_advisory_context(
        campaign={'id': 1, 'name': 'X'},
        bound_character_name='Maelin',
        scene_state={'mode': 'exploration'},
        active_turn=None,
        combatants_snapshot=None,
        inventory=[],
        pending_loot=[],
    )
    assert 'Inventory: (empty)' in out
    assert 'Pending loot' not in out  # only renders when present


def test_build_context_no_combatants_in_combat_mode():
    # Combat mode but no snapshot — should still render mode line cleanly
    out = orch.build_advisory_context(
        campaign={'id': 1, 'name': 'X'},
        bound_character_name='Maelin',
        scene_state={'mode': 'combat'},
        active_turn=None,
        combatants_snapshot={'combatants': [], 'snapshot_age_s': None},
        inventory=[],
        pending_loot=[],
    )
    assert 'Mode: combat' in out
    assert 'Combatants' not in out


# ─── Pure / deterministic ────────────────────────────────────────────

def test_build_context_deterministic():
    args = dict(
        campaign={'id': 1, 'name': 'X'},
        bound_character_name='Maelin',
        scene_state={'mode': 'exploration', 'location': 'Inn'},
        active_turn=None,
        combatants_snapshot=None,
        inventory=[{'item_name': 'rope', 'quantity': 1}],
        pending_loot=[],
    )
    out1 = orch.build_advisory_context(**args)
    out2 = orch.build_advisory_context(**args)
    assert out1 == out2


def test_build_context_no_input_mutation():
    inv = [{'item_name': 'rope', 'quantity': 1}]
    inv_copy = list(inv)
    pending = [{'creature': 'wolf', 'items': ['fang'],
                'coin': {'amount': 1, 'denom': 'gp'}}]
    pending_copy = list(pending)
    orch.build_advisory_context(
        campaign={'id': 1, 'name': 'X'},
        bound_character_name='Maelin',
        scene_state={'mode': 'exploration'},
        active_turn=None,
        combatants_snapshot=None,
        inventory=inv,
        pending_loot=pending,
    )
    assert inv == inv_copy
    assert pending == pending_copy


# ─── Cross-campaign isolation ────────────────────────────────────────
# build_advisory_context is a pure function over its inputs — there is no
# global state to leak. Verify by feeding two campaigns' state and confirming
# the output reflects ONLY the inputs given.

def test_build_context_cross_campaign_isolation():
    out_a = orch.build_advisory_context(
        campaign={'id': 1, 'name': 'Alpha'},
        bound_character_name='Maelin',
        scene_state={'mode': 'exploration'},
        active_turn=None,
        combatants_snapshot=None,
        inventory=[{'item_name': 'campA-only-token', 'quantity': 1}],
        pending_loot=[],
    )
    out_b = orch.build_advisory_context(
        campaign={'id': 2, 'name': 'Bravo'},
        bound_character_name='Thorin',
        scene_state={'mode': 'combat'},
        active_turn=None,
        combatants_snapshot=None,
        inventory=[{'item_name': 'campB-only-token', 'quantity': 1}],
        pending_loot=[],
    )
    # No cross-talk
    assert 'campA-only-token' in out_a and 'campA-only-token' not in out_b
    assert 'campB-only-token' in out_b and 'campB-only-token' not in out_a
    assert 'Alpha' in out_a and 'Alpha' not in out_b
    assert 'Bravo' in out_b and 'Bravo' not in out_a


# ─── No chroma / no writers ──────────────────────────────────────────
# build_advisory_context must not import or call chroma_* or any engine
# writer. The function lives in dnd_orchestration which doesn't import
# dnd_engine — that's the structural defense. Here we additionally
# patch the chroma module (defensive) and confirm zero calls.

def test_build_context_does_not_call_chroma():
    # Patch dnd_engine's chroma functions; running build_advisory_context
    # should never hit them (function doesn't import dnd_engine).
    import dnd_engine
    with mock.patch.object(dnd_engine, 'chroma_search') as ms, \
         mock.patch.object(dnd_engine, 'chroma_store') as mst:
        orch.build_advisory_context(
            campaign={'id': 1, 'name': 'X'},
            bound_character_name='Maelin',
            scene_state={'mode': 'exploration'},
            active_turn=None,
            combatants_snapshot=None,
            inventory=[],
            pending_loot=[],
        )
        assert ms.call_count == 0
        assert mst.call_count == 0


def test_build_context_does_not_call_engine_writers():
    import dnd_engine
    writer_names = (
        'set_scene_mode', 'update_scene', 'update_tension',
        'set_active_turn', 'clear_active_turn',
        'update_combatants_from_init_list', 'clear_combatants',
        'add_item', 'enqueue_loot', 'mark_loot_surfaced',
    )
    patches = []
    try:
        for n in writer_names:
            if hasattr(dnd_engine, n):
                p = mock.patch.object(dnd_engine, n)
                m = p.start()
                patches.append((n, p, m))
        orch.build_advisory_context(
            campaign={'id': 1, 'name': 'X'},
            bound_character_name='Maelin',
            scene_state={'mode': 'combat', 'location': 'Cave'},
            active_turn={'character_name': 'Maelin', 'controller_id': 'u1', 'round': 1},
            combatants_snapshot={'combatants': [
                {'name': 'Maelin', 'init': 15, 'hp_current': 20,
                 'hp_max': 25, 'conditions': '', 'alive': 1, 'side': 'pc'},
            ], 'snapshot_age_s': 10.0},
            inventory=[{'item_name': 'rope', 'quantity': 1}],
            pending_loot=[],
        )
        for n, _, m in patches:
            assert m.call_count == 0, f"{n} was unexpectedly called"
    finally:
        for _, p, _ in patches:
            p.stop()


# ─── Long / empty input ──────────────────────────────────────────────

def test_build_context_handles_long_last_action():
    # Ensure absurdly long last_player_action gets bounded (truncation lives
    # in build_advisory_context to keep the prompt compact).
    long_action = "x" * 10_000
    out = orch.build_advisory_context(
        campaign={'id': 1, 'name': 'X'},
        bound_character_name='Maelin',
        scene_state={'mode': 'exploration', 'last_player_action': long_action},
        active_turn=None,
        combatants_snapshot=None,
        inventory=[],
        pending_loot=[],
    )
    # The state block is expected to truncate; full 10k must not appear
    assert long_action not in out
    assert 'Last player action' in out


def test_build_context_handles_many_combatants():
    # Cap at 20 combatants in the rendered block; extra rows trimmed.
    combatants = [
        {'name': f'mob{i}', 'init': 30 - i, 'hp_current': 5,
         'hp_max': 10, 'conditions': '', 'alive': 1, 'side': 'npc'}
        for i in range(40)
    ]
    out = orch.build_advisory_context(
        campaign={'id': 1, 'name': 'X'},
        bound_character_name=None,
        scene_state={'mode': 'combat'},
        active_turn=None,
        combatants_snapshot={'combatants': combatants, 'snapshot_age_s': 1.0},
        inventory=[],
        pending_loot=[],
    )
    # First few rendered, last few not
    assert 'mob0' in out
    assert 'mob19' in out
    assert 'mob39' not in out


def test_build_context_handles_many_inventory_items():
    items = [{'item_name': f'item{i}', 'quantity': 1} for i in range(80)]
    out = orch.build_advisory_context(
        campaign={'id': 1, 'name': 'X'},
        bound_character_name='Maelin',
        scene_state={'mode': 'exploration'},
        active_turn=None,
        combatants_snapshot=None,
        inventory=items,
        pending_loot=[],
    )
    assert 'item0' in out
    assert 'item39' in out
    assert 'item79' not in out  # capped at 40


# ─── advisory_log_summary ────────────────────────────────────────────

def test_log_summary_combat_with_inventory():
    out = orch.advisory_log_summary(
        bound_character_name='Maelin',
        scene_state={'mode': 'combat'},
        inventory=[{'item_name': 'rope'}, {'item_name': 'torch'}],
        combatants_snapshot={'combatants': [{}, {}, {}], 'snapshot_age_s': 1.0},
    )
    assert 'state_combat=1' in out
    assert 'state_inventory_count=2' in out
    assert 'state_combatants=3' in out
    assert 'bound_char=1' in out


def test_log_summary_no_state():
    out = orch.advisory_log_summary(
        bound_character_name=None,
        scene_state=None,
        inventory=None,
        combatants_snapshot=None,
    )
    assert 'state_combat=0' in out
    assert 'state_inventory_count=0' in out
    assert 'state_combatants=0' in out
    assert 'bound_char=0' in out


# ─── Commands reference loader (Track 6 #3.1) ───────────────────────

def test_load_commands_reference_returns_content_when_file_exists():
    # Point the loader at a known fixture file.
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md',
                                      delete=False, encoding='utf-8') as f:
        f.write("# Test Commands\n\n## Virgil Slash Commands\n- `/test` — sample\n")
        path = f.name
    try:
        with mock.patch.object(orch, 'COMMANDS_DOC_PATH', Path(path)):
            out = orch._load_commands_reference()
            assert '# Test Commands' in out
            assert '/test' in out
    finally:
        Path(path).unlink(missing_ok=True)


def test_load_commands_reference_returns_empty_when_file_missing():
    with mock.patch.object(orch, 'COMMANDS_DOC_PATH',
                            Path('/tmp/definitely-does-not-exist-xyz123.md')):
        out = orch._load_commands_reference()
        assert out == ''


def test_load_commands_reference_returns_empty_on_read_error():
    # Point at a directory — read_text raises IsADirectoryError → ''
    with mock.patch.object(orch, 'COMMANDS_DOC_PATH', Path('/tmp')):
        out = orch._load_commands_reference()
        assert out == ''


def test_load_commands_reference_reads_fresh_each_call():
    # Confirm no caching: edit the file between calls, second call sees the change.
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md',
                                      delete=False, encoding='utf-8') as f:
        f.write("v1 content\n")
        path = f.name
    try:
        with mock.patch.object(orch, 'COMMANDS_DOC_PATH', Path(path)):
            out1 = orch._load_commands_reference()
            assert 'v1 content' in out1
            Path(path).write_text('v2 content\n', encoding='utf-8')
            out2 = orch._load_commands_reference()
            assert 'v2 content' in out2
            assert 'v1 content' not in out2
    finally:
        Path(path).unlink(missing_ok=True)


def test_build_context_includes_commands_block_when_provided():
    cmd_text = "# Test Commands\n\n## Virgil Slash Commands\n- `/test`"
    out = orch.build_advisory_context(
        campaign={'id': 1, 'name': 'X'},
        bound_character_name='Maelin',
        scene_state={'mode': 'exploration'},
        active_turn=None,
        combatants_snapshot=None,
        inventory=[],
        pending_loot=[],
        commands_reference=cmd_text,
    )
    assert '=== AVAILABLE COMMANDS ===' in out
    assert '/test' in out
    # State block precedes the commands block (sanity on ordering)
    assert out.index('STATE REFERENCE') < out.index('AVAILABLE COMMANDS')


def test_build_context_omits_commands_block_when_empty_string():
    # Explicit empty string → no header, no placeholder
    out = orch.build_advisory_context(
        campaign={'id': 1, 'name': 'X'},
        bound_character_name='Maelin',
        scene_state={'mode': 'exploration'},
        active_turn=None,
        combatants_snapshot=None,
        inventory=[],
        pending_loot=[],
        commands_reference='',
    )
    assert '=== AVAILABLE COMMANDS ===' not in out
    # Sanity: state still present
    assert 'STATE REFERENCE' in out


def test_build_context_calls_loader_when_commands_reference_is_none():
    # Default behavior: commands_reference=None → loader is called.
    cmd_text = "# Loader Hit\n## Virgil Slash Commands\n- `/loaded`"
    with mock.patch.object(orch, '_load_commands_reference', return_value=cmd_text) as ml:
        out = orch.build_advisory_context(
            campaign={'id': 1, 'name': 'X'},
            bound_character_name='Maelin',
            scene_state={'mode': 'exploration'},
            active_turn=None,
            combatants_snapshot=None,
            inventory=[],
            pending_loot=[],
        )
        assert ml.call_count == 1
        assert '/loaded' in out


def test_build_context_does_not_call_loader_when_reference_provided():
    # When caller passes a string (even ''), loader must not be called —
    # caller has the authoritative answer (and has logged telemetry on it).
    with mock.patch.object(orch, '_load_commands_reference') as ml:
        orch.build_advisory_context(
            campaign={'id': 1, 'name': 'X'},
            bound_character_name='Maelin',
            scene_state={'mode': 'exploration'},
            active_turn=None,
            combatants_snapshot=None,
            inventory=[],
            pending_loot=[],
            commands_reference='',
        )
        assert ml.call_count == 0


def test_build_context_pure_with_same_inputs_and_same_file_content():
    cmd_text = "# Stable\n## Virgil Slash Commands\n- `/stable`"
    args = dict(
        campaign={'id': 1, 'name': 'X'},
        bound_character_name='Maelin',
        scene_state={'mode': 'exploration'},
        active_turn=None,
        combatants_snapshot=None,
        inventory=[],
        pending_loot=[],
        commands_reference=cmd_text,
    )
    out1 = orch.build_advisory_context(**args)
    out2 = orch.build_advisory_context(**args)
    assert out1 == out2


def test_advisory_prompt_references_available_commands_block():
    # The system prompt must explicitly point the LLM at AVAILABLE COMMANDS.
    p = orch.ADVISORY_SYSTEM_PROMPT
    assert 'AVAILABLE COMMANDS' in p
    assert 'source of truth' in p


def test_advisory_prompt_warns_against_command_invention():
    # Must explicitly guide the LLM to admit "not available" rather than guess.
    p = orch.ADVISORY_SYSTEM_PROMPT
    assert "I don't see that as an available command" in p


# ─── Routing wiring (sanity, not a Discord integration test) ─────────

def test_advisory_task_in_router():
    # cloud_router.route() should accept task_type='advisory' without raising.
    # We don't actually call providers — just confirm the task name is in the
    # routing table by checking the source.
    import cloud_router
    src = open(cloud_router.__file__).read()
    assert "'advisory'" in src or '"advisory"' in src, (
        "cloud_router.py must handle task_type='advisory'"
    )


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
    if failures:
        print(f"\n{len(failures)} failure(s)")
        sys.exit(1)
    print(f"\n{len(funcs)} tests passed.")
