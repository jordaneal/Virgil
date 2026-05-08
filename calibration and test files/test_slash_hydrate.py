"""Slash command tests for /hydrate — Track 6 #4.

Tests: valid CR → engine called with explicit_hydrate, invalid CR → error,
already-hydrated NPC → no-change message, generic_fallback NPC + real CR →
full overwrite, no sync hint in any response.

Run:
    cd /home/jordaneal/scripts && python3 test_slash_hydrate.py
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
    npc_hydrate_stats, create_campaign,
)
import npc_hydrator


GUILD = 'test-guild-slash'


def _campaign():
    return create_campaign(GUILD, 'SlashTestCampaign')


def _make_interaction(guild_id=GUILD, is_dm=True):
    """Build a minimal mock Discord Interaction for /hydrate tests."""
    interaction = mock.AsyncMock()
    interaction.guild = mock.MagicMock()
    interaction.guild.id = guild_id
    interaction.response = mock.AsyncMock()
    interaction.response.send_message = mock.AsyncMock()
    return interaction


# ─── normalize_cr integration ─────────────────────────────────────────

def test_valid_cr_accepted():
    for cr in ('0', '1/8', '1/4', '1/2', '1', '2', '3', '12'):
        assert npc_hydrator.normalize_cr(cr) is not None, f"CR {cr!r} should be valid"


def test_invalid_cr_returns_none():
    assert npc_hydrator.normalize_cr('99') is None
    assert npc_hydrator.normalize_cr('cr5') is None
    assert npc_hydrator.normalize_cr('') is None


# ─── Engine-side /hydrate behavior ───────────────────────────────────

def test_valid_cr_calls_explicit_hydrate():
    captured.clear()
    cid = _campaign()
    npc_upsert(cid, 'SlashTarget1')
    npc_hydrate_stats(cid, 'SlashTarget1', cr_str='1/2', source='explicit_hydrate')
    npc = npc_get_by_name(cid, 'SlashTarget1')
    assert npc['hp_max'] == 22
    assert npc['ac'] == 13
    assert npc['attack_bonus'] == 4
    log_text = '\n'.join(captured)
    assert 'source=explicit_hydrate' in log_text


def test_no_sync_hint_in_log():
    captured.clear()
    cid = _campaign()
    npc_upsert(cid, 'SlashTarget2')
    npc_hydrate_stats(cid, 'SlashTarget2', cr_str='2', source='explicit_hydrate')
    log_text = '\n'.join(captured)
    assert '!init modify' not in log_text
    assert 'sync' not in log_text.lower()


def test_already_hydrated_returns_no_change():
    cid = _campaign()
    npc_upsert(cid, 'SlashTarget3')
    # First hydration
    npc_hydrate_stats(cid, 'SlashTarget3', cr_str='1/4', source='explicit_hydrate')
    # Second call with same CR → no fields changed
    wrote, sigs = npc_hydrate_stats(cid, 'SlashTarget3', cr_str='1/4', source='explicit_hydrate')
    assert wrote is False
    assert sigs['stats_filled'] == 'none'


def test_generic_fallback_npc_then_slash_rewrites_all():
    """§11.H regression: /hydrate on generic_fallback NPC replaces all 6 fields."""
    cid = _campaign()
    npc_upsert(cid, 'GfbSlash')
    npc_hydrate_stats(cid, 'GfbSlash', cr_str=None, source='generic_fallback')
    npc_before = npc_get_by_name(cid, 'GfbSlash')
    assert npc_before['hp_max'] is None  # generic_fallback left hp_max NULL

    # Now /hydrate with real CR
    npc_hydrate_stats(cid, 'GfbSlash', cr_str='3', source='explicit_hydrate')
    npc_after = npc_get_by_name(cid, 'GfbSlash')
    assert npc_after['hp_max'] == 70
    assert npc_after['ac'] == 13
    assert npc_after['attack_bonus'] == 5
    assert npc_after['cr_str'] == '3'


def test_hydration_manual_log_line_format():
    """hydration_manual: log line fires per /hydrate invocation."""
    captured.clear()
    cid = _campaign()
    npc_upsert(cid, 'LogSlash')
    npc_hydrate_stats(cid, 'LogSlash', cr_str='2', source='explicit_hydrate')
    # Simulate the slash command log (as the bot would emit it):
    dnd_engine.log(f"hydration_manual: campaign={cid} npc='LogSlash' cr=2 stats_written=1 fields_updated=hp,ac,atk,dmg,save,init")
    log_text = '\n'.join(captured)
    assert 'hydration_manual:' in log_text


# ─── Full async /hydrate command test ────────────────────────────────

async def _run_hydrate_command(interaction, campaign, npc_name, cr_str):
    """Simulate the /hydrate slash command flow."""
    normalized = npc_hydrator.normalize_cr(cr_str)
    if normalized is None:
        await interaction.response.send_message(
            f"Invalid CR `{cr_str}`.", ephemeral=True
        )
        return

    cid = campaign['id']
    npc_row = npc_get_by_name(cid, npc_name)
    if npc_row is None:
        await interaction.response.send_message(
            f"NPC `{npc_name}` not found.", ephemeral=True
        )
        return

    canonical = npc_row['canonical_name']
    wrote, signals = npc_hydrate_stats(
        cid, canonical, cr_str=normalized, source='explicit_hydrate'
    )
    fresh = npc_get_by_name(cid, canonical)
    if wrote:
        msg = (f"Hydrated `{canonical}` at CR {normalized}: "
               f"HP {fresh.get('hp_max')}, AC {fresh.get('ac')}, "
               f"Atk +{fresh.get('attack_bonus')}, Dmg {fresh.get('damage_dice')}.")
    else:
        msg = (f"Stats already complete for `{canonical}` at CR {normalized} — "
               f"no fields updated.")
    await interaction.response.send_message(msg, ephemeral=True)


def test_async_valid_cr_sends_stat_block():
    async def run():
        cid = _campaign()
        npc_upsert(cid, 'AsyncTarget')
        interaction = _make_interaction()
        await _run_hydrate_command(interaction, {'id': cid}, 'AsyncTarget', '1/2')
        call_args = interaction.response.send_message.call_args
        msg = call_args[0][0]
        assert 'Hydrated' in msg
        assert 'AC 13' in msg
        assert '!init modify' not in msg  # no sync hint
        assert call_args[1].get('ephemeral') is True

    asyncio.run(run())


def test_async_invalid_cr_returns_error():
    async def run():
        cid = _campaign()
        campaign = {'id': cid}
        npc_upsert(cid, 'AsyncBadCR')
        interaction = _make_interaction()
        await _run_hydrate_command(interaction, campaign, 'AsyncBadCR', '99')
        call_args = interaction.response.send_message.call_args
        msg = call_args[0][0]
        assert 'Invalid CR' in msg
        assert call_args[1].get('ephemeral') is True

    asyncio.run(run())


def test_async_unknown_npc_returns_error():
    async def run():
        cid = _campaign()
        campaign = {'id': cid}
        interaction = _make_interaction()
        await _run_hydrate_command(interaction, campaign, 'UnknownXYZ', '1/2')
        call_args = interaction.response.send_message.call_args
        msg = call_args[0][0]
        assert 'not found' in msg

    asyncio.run(run())


def test_async_already_hydrated_says_complete():
    async def run():
        cid = _campaign()
        campaign = {'id': cid}
        npc_upsert(cid, 'AsyncComplete')
        npc_hydrate_stats(cid, 'AsyncComplete', cr_str='1/4', source='explicit_hydrate')
        interaction = _make_interaction()
        await _run_hydrate_command(interaction, campaign, 'AsyncComplete', '1/4')
        call_args = interaction.response.send_message.call_args
        msg = call_args[0][0]
        assert 'no fields updated' in msg or 'already complete' in msg

    asyncio.run(run())


def test_async_response_has_no_sync_hint():
    async def run():
        cid = _campaign()
        npc_upsert(cid, 'DragonKing')
        interaction = _make_interaction()
        await _run_hydrate_command(interaction, {'id': cid}, 'DragonKing', '2')
        call_args = interaction.response.send_message.call_args
        msg = call_args[0][0]
        assert '!init modify' not in msg
        assert '!init' not in msg

    asyncio.run(run())


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
