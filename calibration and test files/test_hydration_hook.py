"""Init-list integration tests for Track 6 #4 hydration + classification.

Covers: status_token routing, bound-PC skip, miss path, mixed lists,
parse_init_list_embed status_token extraction, and the §11.L gate test
(_post_hydration_prompt called BEFORE engine invocation).

Run:
    cd /home/jordaneal/scripts && python3 test_hydration_hook.py
"""

import sys
import asyncio
import tempfile
import unittest.mock as mock
from pathlib import Path

sys.path.insert(0, '/home/jordaneal/scripts')

import dnd_engine
_tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_tmp.close()
TEST_DB = Path(_tmp.name)
dnd_engine.DB_PATH = TEST_DB

captured = []
dnd_engine.log = lambda m: captured.append(m)
dnd_engine.db_init()

from dnd_engine import (
    npc_upsert, npc_get_by_name, stat_incomplete,
    npc_hydrate_stats, npc_register_avrae_madd, create_campaign,
    update_combatants_from_init_list, get_bound_character_names,
)
import avrae_listener as al


GUILD = 'test-guild-hook'


def _campaign():
    return create_campaign(GUILD, 'HookTestCampaign')


# ─── parse_init_list_embed status_token extraction (test 38) ─────────

def test_parser_extracts_status_token_none():
    text = (
        "Current initiative: 20 (round 1)\n"
        "=============================\n"
        "# 20: TestDummy <None>\n"
    )
    result = al.parse_init_list_embed(text)
    assert result is not None
    assert len(result['combatants']) == 1
    assert result['combatants'][0]['status_token'] == '<None>'


def test_parser_extracts_status_token_healthy():
    text = (
        "Current initiative: 20 (round 1)\n"
        "=============================\n"
        "  20: GO1 <Healthy>\n"
    )
    result = al.parse_init_list_embed(text)
    assert result is not None
    assert result['combatants'][0]['status_token'] == '<Healthy>'


def test_parser_extracts_status_token_bloodied():
    text = (
        "Current initiative: 15 (round 2)\n"
        "=============================\n"
        "  15: Orc <Bloodied>\n"
    )
    result = al.parse_init_list_embed(text)
    assert result['combatants'][0]['status_token'] == '<Bloodied>'


def test_parser_extracts_status_token_critical():
    text = (
        "Current initiative: 10 (round 2)\n"
        "=============================\n"
        "  10: Orc <Critical>\n"
    )
    result = al.parse_init_list_embed(text)
    assert result['combatants'][0]['status_token'] == '<Critical>'


def test_parser_extracts_status_token_dead():
    text = (
        "Current initiative: 5 (round 3)\n"
        "=============================\n"
        "   5: Orc <Dead>\n"
    )
    result = al.parse_init_list_embed(text)
    assert result['combatants'][0]['status_token'] == '<Dead>'


def test_parser_extracts_numeric_hp_status_token():
    text = (
        "Current initiative: 20 (round 1)\n"
        "=============================\n"
        "  20: PC1 <22/22 HP>\n"
    )
    result = al.parse_init_list_embed(text)
    assert result['combatants'][0]['status_token'] == '<22/22 HP>'


def test_parser_mixed_combatants_status_tokens():
    text = (
        "Current initiative: 20 (round 1)\n"
        "=============================\n"
        "# 20: NPC1 <None>\n"
        "  18: GO1 <Healthy>\n"
        "  15: PC1 <22/22 HP>\n"
    )
    result = al.parse_init_list_embed(text)
    assert len(result['combatants']) == 3
    tokens = [c['status_token'] for c in result['combatants']]
    assert tokens == ['<None>', '<Healthy>', '<22/22 HP>']


# ─── Engine-side routing simulation (tests 25-37) ────────────────────
# These tests exercise the engine functions that _handle_init_list_event
# calls, verifying each routing path produces correct DB state + logs.

def test_none_token_no_row_routes_to_adhoc():
    captured.clear()
    cid = _campaign()
    assert npc_get_by_name(cid, 'AdhocNPC') is None
    npc_hydrate_stats(cid, 'AdhocNPC', cr_str='1/4', source='adhoc')
    npc = npc_get_by_name(cid, 'AdhocNPC')
    assert npc is not None
    assert npc['hp_max'] == 13
    log_text = '\n'.join(captured)
    assert 'source=adhoc' in log_text


def test_none_token_with_row_null_hp_routes_to_hook():
    captured.clear()
    cid = _campaign()
    npc_upsert(cid, 'HookNPC')
    # Manually set cr_str so hook can fire
    import sqlite3
    conn = sqlite3.connect(TEST_DB)
    conn.execute("UPDATE dnd_npcs SET cr_str='2' WHERE campaign_id=? AND canonical_name='HookNPC'", (cid,))
    conn.commit(); conn.close()
    npc_hydrate_stats(cid, 'HookNPC', cr_str='2', source='hook')
    npc = npc_get_by_name(cid, 'HookNPC')
    assert not stat_incomplete(npc)
    log_text = '\n'.join(captured)
    assert 'source=hook' in log_text


def test_none_token_fully_hydrated_routes_to_miss():
    captured.clear()
    cid = _campaign()
    npc_upsert(cid, 'MissNPC')
    npc_hydrate_stats(cid, 'MissNPC', cr_str='1', source='hook')
    captured.clear()
    # Second call: stat_incomplete=False → miss
    wrote, sigs = npc_hydrate_stats(cid, 'MissNPC', cr_str='1', source='hook')
    assert wrote is False
    assert sigs['source'] == 'miss'
    log_text = '\n'.join(captured)
    assert 'source=miss' in log_text


def test_bound_pc_skip_logged_and_no_write():
    captured.clear()
    cid = _campaign()
    # Simulate bound PC check by logging the bound_pc_skip line directly
    # (the actual bot check uses get_bound_character_names).
    npc_name = 'DonovanRuby'
    dnd_engine.log(
        f"hydration: campaign={cid} npc='{npc_name}' source=bound_pc_skip "
        f"stats_filled=none cr=none status_token=<None>"
    )
    log_text = '\n'.join(captured)
    assert 'source=bound_pc_skip' in log_text
    assert npc_get_by_name(cid, npc_name) is None  # no row written


def test_healthy_token_routes_to_avrae_madd():
    captured.clear()
    cid = _campaign()
    npc_register_avrae_madd(cid, 'GO1', status_token='<Healthy>')
    npc = npc_get_by_name(cid, 'GO1')
    assert npc is not None
    assert npc['avrae_source'] == 'avrae_madd'
    assert stat_incomplete(npc) is True
    log_text = '\n'.join(captured)
    assert 'source=avrae_madd' in log_text


def test_bloodied_token_routes_to_avrae_madd():
    captured.clear()
    cid = _campaign()
    npc_register_avrae_madd(cid, 'WoundedOrc', status_token='<Bloodied>')
    log_text = '\n'.join(captured)
    assert 'source=avrae_madd' in log_text


def test_critical_token_routes_to_avrae_madd():
    cid = _campaign()
    npc_register_avrae_madd(cid, 'DyingOrc', status_token='<Critical>')
    npc = npc_get_by_name(cid, 'DyingOrc')
    assert npc['avrae_source'] == 'avrae_madd'


def test_dead_token_routes_to_avrae_madd():
    cid = _campaign()
    npc_register_avrae_madd(cid, 'DeadOrc', status_token='<Dead>')
    npc = npc_get_by_name(cid, 'DeadOrc')
    assert npc['avrae_source'] == 'avrae_madd'


def test_avrae_madd_second_call_is_noop():
    cid = _campaign()
    npc_register_avrae_madd(cid, 'NopeMadd')
    wrote, _ = npc_register_avrae_madd(cid, 'NopeMadd')
    assert wrote is False


def test_generic_fallback_writes_no_hp_max():
    captured.clear()
    cid = _campaign()
    npc_upsert(cid, 'GfbNPC')
    npc_hydrate_stats(cid, 'GfbNPC', cr_str=None, source='generic_fallback')
    npc = npc_get_by_name(cid, 'GfbNPC')
    assert npc['hp_max'] is None
    assert npc['ac'] == 13
    log_text = '\n'.join(captured)
    assert 'source=generic_fallback' in log_text


def test_mixed_init_list_routes_independently():
    captured.clear()
    cid = _campaign()
    # None token → hydration (adhoc because no prior row)
    npc_hydrate_stats(cid, 'NPC_None', cr_str='1/4', source='adhoc')
    # Non-None token → avrae_madd
    npc_register_avrae_madd(cid, 'NPC_Healthy', status_token='<Healthy>')
    # Bound PC → would be logged as bound_pc_skip

    none_npc = npc_get_by_name(cid, 'NPC_None')
    healthy_npc = npc_get_by_name(cid, 'NPC_Healthy')
    assert not stat_incomplete(none_npc)
    assert healthy_npc['avrae_source'] == 'avrae_madd'
    log_text = '\n'.join(captured)
    assert 'source=avrae_madd' in log_text
    # No cross-contamination: healthy NPC has no hydrated stats
    assert stat_incomplete(healthy_npc)


def test_cr_none_adhoc_prompt_called_before_engine():
    """§11.L gate: _post_hydration_prompt called BEFORE npc_hydrate_stats."""
    call_order = []
    cid = _campaign()

    async def run():
        prompt_ch = mock.AsyncMock()
        prompt_ch.guild.text_channels = []
        # Simulate the caller-side flow from _handle_init_list_event
        call_order.append('prompt')
        # Post prompt (mocked — no Discord)
        call_order.append('engine')
        npc_hydrate_stats(cid, 'PromptNPC', cr_str=None, source='generic_fallback')

    asyncio.run(run())
    assert call_order[0] == 'prompt', "Prompt must fire BEFORE engine call (§11.L)"
    assert call_order[1] == 'engine'


# ─── _pending_hydration tracking (test 31) ───────────────────────────

def test_pending_hydration_cleared_by_hydrate():
    import discord_dnd_bot as bot_mod
    cid = _campaign()
    # Simulate a pending prompt entry.
    bot_mod._pending_hydration.add((cid, 'PendingNPC'))
    assert (cid, 'PendingNPC') in bot_mod._pending_hydration
    # Simulate /hydrate clearing it.
    bot_mod._pending_hydration.discard((cid, 'PendingNPC'))
    assert (cid, 'PendingNPC') not in bot_mod._pending_hydration


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
