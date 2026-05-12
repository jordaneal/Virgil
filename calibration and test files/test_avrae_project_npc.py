"""Tests for _avrae_project_npc — Ship 3 (S41 post-pivot) NPC sync SUGGESTER.

**S41 architectural pivot:** Avrae's API silently filters bot-emitted
`!`-commands (empirical S41 verify pass). The originally-locked bot-write
shape (§65a narrow exception) was structurally impossible. Pivoted to
§1b validated-suggester pattern per `_post_srd_suggestion` precedent
(Track 6 #5.1, S26 first instance). This makes Ship 3 the SECOND §1b
project instance.

Tests cover every idempotency reason path, the Case A/Case B trigger
split, telemetry coverage, and the suggestion-text format. All Discord
I/O is via AsyncMock; no live channel, no DB beyond tmpfile.

Run:
    cd /home/jordaneal/scripts && python3 test_avrae_project_npc.py
"""

import asyncio
import os
import sys
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.dirname(__file__))

import dnd_engine
_tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_tmp.close()
TEST_DB = Path(_tmp.name)
dnd_engine.DB_PATH = TEST_DB

captured = []
dnd_engine.log = lambda m: captured.append(m)
dnd_engine.db_init()

import discord_dnd_bot
discord_dnd_bot.log = lambda m: captured.append(m)
_project = discord_dnd_bot._avrae_project_npc

from dnd_engine import (
    npc_upsert, npc_hydrate_stats, create_campaign,
    update_combatants_from_init_list,
)


GUILD = 'test-guild-project'


def _campaign():
    return create_campaign(GUILD, 'ProjectTestCampaign')


def _seed_combatant(campaign_id, name, init, status_kind='none'):
    """Insert via update_combatants_from_init_list. status_kind='none' →
    status_token=<None>, hp_max=None; 'numeric' → hp_max=12 hp_current=12."""
    if status_kind == 'none':
        parsed = {
            'round': 1, 'current_init': init,
            'combatants': [{
                'init': init, 'name': name, 'active': True,
                'hp_current': None, 'hp_max': None,
                'conditions': '', 'alive': 1,
                'status_token': '<None>',
            }],
        }
    else:
        parsed = {
            'round': 1, 'current_init': init,
            'combatants': [{
                'init': init, 'name': name, 'active': True,
                'hp_current': 12, 'hp_max': 12,
                'conditions': '', 'alive': 1,
                'status_token': '<12/12 HP>',
            }],
        }
    update_combatants_from_init_list(campaign_id, parsed)


def _mock_channel_with_aside():
    """Returns (channel, aside_mock). Mocks both as AsyncMock; channel.guild
    is a MagicMock whose text_channels includes the aside mock so
    discord.utils.get(guild.text_channels, name='dm-aside') finds it."""
    ch = AsyncMock()
    ch.name = 'dm-narration'
    aside = AsyncMock()
    aside.name = 'dm-aside'
    guild = MagicMock()
    guild.text_channels = [ch, aside]
    ch.guild = guild
    return ch, aside


def _run(coro):
    return asyncio.run(coro)


# ─── Reason: gate_engine_missing ────────────────────────────────────

def test_gate_engine_missing_no_npc_row():
    captured.clear()
    cid = _campaign()
    ch, aside = _mock_channel_with_aside()
    ok, sig = _run(_project(ch, cid, 'GhostNPC', trigger='hydrate'))
    assert ok is False
    assert sig['reason'] == 'gate_engine_missing'
    assert any('gate_engine_missing' in m for m in captured)
    # No suggestion posted to ANY channel
    assert ch.send.await_count == 0
    assert aside.send.await_count == 0


# ─── Reason: gate_engine_stats_null ─────────────────────────────────

def test_gate_engine_stats_null_hp_missing():
    captured.clear()
    cid = _campaign()
    npc_upsert(cid, 'NullStat', skeleton_origin=False)
    _seed_combatant(cid, 'NullStat', init=10, status_kind='none')
    ch, aside = _mock_channel_with_aside()
    ok, sig = _run(_project(ch, cid, 'NullStat', trigger='hydrate'))
    assert ok is False
    assert sig['reason'] == 'gate_engine_stats_null'
    assert any('gate_engine_stats_null' in m for m in captured)
    assert aside.send.await_count == 0


# ─── Reason: gate_not_in_init ───────────────────────────────────────

def test_gate_not_in_init_npc_hydrated_but_no_combatant_row():
    captured.clear()
    cid = _campaign()
    npc_upsert(cid, 'NotFighting', skeleton_origin=False)
    npc_hydrate_stats(cid, 'NotFighting', cr_str='1/4', source='hook')
    ch, aside = _mock_channel_with_aside()
    ok, sig = _run(_project(ch, cid, 'NotFighting', trigger='hydrate'))
    assert ok is False
    assert sig['reason'] == 'gate_not_in_init'
    assert any('gate_not_in_init' in m for m in captured)
    assert aside.send.await_count == 0


# ─── Reason: noop_complete (Case B — passive init_list trigger) ─────

def test_noop_complete_case_b_init_list_trigger_numeric_hp():
    captured.clear()
    cid = _campaign()
    npc_upsert(cid, 'AlreadySynced', skeleton_origin=False)
    npc_hydrate_stats(cid, 'AlreadySynced', cr_str='1/4', source='hook')
    _seed_combatant(cid, 'AlreadySynced', init=12, status_kind='numeric')
    ch, aside = _mock_channel_with_aside()
    ok, sig = _run(_project(ch, cid, 'AlreadySynced', trigger='init_list'))
    assert ok is False
    assert sig['reason'] == 'noop_complete'
    assert any('noop_complete' in m for m in captured)
    # Critical: no suggestion posted; Avrae's mid-combat state preserved
    assert aside.send.await_count == 0


# ─── Reason: suggested_with_warning (Case A — /hydrate mid-combat) ──

def test_case_a_mid_combat_hydrate_posts_warning_with_suggestion():
    captured.clear()
    cid = _campaign()
    npc_upsert(cid, 'MidCombatNPC', skeleton_origin=False)
    npc_hydrate_stats(cid, 'MidCombatNPC', cr_str='1', source='hook')
    _seed_combatant(cid, 'MidCombatNPC', init=14, status_kind='numeric')
    ch, aside = _mock_channel_with_aside()

    ok, sig = _run(_project(ch, cid, 'MidCombatNPC', trigger='hydrate'))

    assert ok is True
    assert sig['reason'] == 'suggested_with_warning'
    assert any('suggested_with_warning' in m for m in captured)
    # Warning posted to #dm-aside
    assert aside.send.await_count == 1
    aside_text = aside.send.await_args.args[0]
    assert 'Mid-combat' in aside_text
    assert 'MidCombatNPC' in aside_text
    # Locked 3-line sequence: remove + add -hp + opt -ac (post-S41-3rd-verify)
    assert '!init remove MidCombatNPC' in aside_text
    assert '!init add' in aside_text
    assert 'MidCombatNPC -hp' in aside_text
    assert '!init opt MidCombatNPC -ac 13' in aside_text
    # Combat-state-loss warning explicit
    assert 'lose' in aside_text.lower() or 'will lose' in aside_text.lower()
    # Partial fix mentioned as fallback option
    assert 'partial fix' in aside_text.lower() or 'preserves combat state' in aside_text.lower()


# ─── Reason: suggested (happy path — post sync suggestion) ──────────

def test_suggested_happy_path_posts_command_block_to_aside():
    captured.clear()
    cid = _campaign()
    npc_upsert(cid, 'NeedsProjection', skeleton_origin=False)
    npc_hydrate_stats(cid, 'NeedsProjection', cr_str='1/2', source='hook')
    _seed_combatant(cid, 'NeedsProjection', init=11, status_kind='none')
    ch, aside = _mock_channel_with_aside()

    ok, sig = _run(_project(ch, cid, 'NeedsProjection', trigger='hydrate'))

    assert ok is True
    assert sig['reason'] == 'suggested'
    assert sig['hp'] == 22  # CR 1/2 hp_max
    assert sig['ac'] == 13  # CR 1/2 ac
    assert len(sig['commands_suggested']) == 3
    # Locked sequence (post-S41-third-verify): three-line remove + add -hp
    # + opt -ac. `!init add -h` is Avrae's hidden-toggle (NOT HP); the
    # working HP flag for both add and opt is `-hp`. AC must be set via
    # `!init opt -ac` since the add subcommand doesn't accept -ac cleanly.
    # CR 1/2 init_mod=1.
    assert sig['commands_suggested'][0] == '!init remove NeedsProjection'
    assert sig['commands_suggested'][1] == '!init add 1 NeedsProjection -hp 22'
    assert sig['commands_suggested'][2] == '!init opt NeedsProjection -ac 13'
    # Suggestion posted to #dm-aside (NOT narration)
    assert aside.send.await_count == 1
    assert ch.send.await_count == 0
    aside_text = aside.send.await_args.args[0]
    assert 'NeedsProjection' in aside_text
    assert '!init remove NeedsProjection' in aside_text
    assert '!init add 1 NeedsProjection -hp 22' in aside_text
    assert '!init opt NeedsProjection -ac 13' in aside_text
    # Reminds DM of the per-line paste discipline
    assert 'separate' in aside_text.lower() or 'each line' in aside_text.lower()
    # Telemetry
    assert any('avrae_projection_attempted' in m for m in captured)
    assert any('avrae_projection_succeeded' in m for m in captured)


def test_suggested_uses_corrected_3line_sequence():
    """Regression guard for the third S41 verify-pass finding: `!init add -h`
    is Avrae's hidden-toggle (NOT HP), and `!init add ... -ac` doesn't
    cleanly parse alongside other flags. The verified working sequence is:
      1. !init remove <name>      (clears stale state)
      2. !init add <init> <name> -hp <hp>  (sets max + current HP)
      3. !init opt <name> -ac <ac>          (sets AC via opt)
    Each line as a separate paste."""
    captured.clear()
    cid = _campaign()
    npc_upsert(cid, 'FlagCheck', skeleton_origin=False)
    npc_hydrate_stats(cid, 'FlagCheck', cr_str='1/4', source='hook')
    _seed_combatant(cid, 'FlagCheck', init=10, status_kind='none')
    ch, aside = _mock_channel_with_aside()

    ok, sig = _run(_project(ch, cid, 'FlagCheck', trigger='init_list'))
    assert ok is True
    aside_text = aside.send.await_args.args[0]
    # Happy path uses the verified 3-line sequence. CR 1/4: init_mod=1,
    # hp_max=13, ac=13.
    assert '!init remove FlagCheck' in aside_text
    assert '!init add 1 FlagCheck -hp 13' in aside_text
    assert '!init opt FlagCheck -ac 13' in aside_text
    # Must NOT have the hidden-toggle bug syntax (`-h <N>` on either subcommand)
    assert '!init add 1 FlagCheck -h 13' not in aside_text
    assert '!init opt FlagCheck -h 13' not in aside_text
    # Must NOT have the combined add-with-ac (verified unreliable in S41).
    assert '!init add 1 FlagCheck -hp 13 -ac 13' not in aside_text
    # Suggested commands tuple matches 3-line shape
    assert len(sig['commands_suggested']) == 3
    assert sig['commands_suggested'][0] == '!init remove FlagCheck'
    assert sig['commands_suggested'][1] == '!init add 1 FlagCheck -hp 13'
    assert sig['commands_suggested'][2] == '!init opt FlagCheck -ac 13'


# ─── Reason: aside_post_failed (#dm-aside.send raises) ──────────────

def test_aside_post_failed_when_dm_aside_send_raises():
    captured.clear()
    cid = _campaign()
    npc_upsert(cid, 'FailNPC', skeleton_origin=False)
    npc_hydrate_stats(cid, 'FailNPC', cr_str='1/4', source='hook')
    _seed_combatant(cid, 'FailNPC', init=8, status_kind='none')

    ch, aside = _mock_channel_with_aside()
    aside.send.side_effect = RuntimeError('discord forbidden')

    ok, sig = _run(_project(ch, cid, 'FailNPC', trigger='hydrate'))

    assert ok is False
    assert sig['reason'] == 'aside_post_failed'
    assert 'discord forbidden' in sig['error']
    assert any('avrae_projection_failed' in m for m in captured)
    assert any('aside_post_failed' in m for m in captured)


def test_aside_channel_missing_returns_aside_post_failed():
    """If #dm-aside isn't found in the guild, the suggester can't post.
    Treat as aside_post_failed with reason carrying the absence."""
    captured.clear()
    cid = _campaign()
    npc_upsert(cid, 'NoAsideNPC', skeleton_origin=False)
    npc_hydrate_stats(cid, 'NoAsideNPC', cr_str='1/4', source='hook')
    _seed_combatant(cid, 'NoAsideNPC', init=8, status_kind='none')

    ch = AsyncMock()
    ch.name = 'dm-narration'
    guild = MagicMock()
    # No dm-aside in text_channels
    guild.text_channels = [ch]
    ch.guild = guild

    ok, sig = _run(_project(ch, cid, 'NoAsideNPC', trigger='hydrate'))
    assert ok is False
    assert sig['reason'] == 'aside_post_failed'
    assert 'channel not found' in sig['error'].lower() or 'not found' in sig['error'].lower()


# ─── Idempotency ────────────────────────────────────────────────────

def test_idempotency_after_avrae_synced_passive_trigger_noops():
    """After first suggestion + DM pastes, combatant has numeric HP.
    Subsequent passive (init_list) trigger no-ops cleanly per Case B."""
    captured.clear()
    cid = _campaign()
    npc_upsert(cid, 'Idem', skeleton_origin=False)
    npc_hydrate_stats(cid, 'Idem', cr_str='1/4', source='hook')
    _seed_combatant(cid, 'Idem', init=10, status_kind='none')
    ch, aside = _mock_channel_with_aside()

    ok1, _ = _run(_project(ch, cid, 'Idem', trigger='init_list'))
    assert ok1 is True
    assert aside.send.await_count == 1

    # Simulate DM pasted + Avrae confirmed: combatant now has numeric HP
    _seed_combatant(cid, 'Idem', init=10, status_kind='numeric')
    aside.send.reset_mock()

    ok2, sig2 = _run(_project(ch, cid, 'Idem', trigger='init_list'))
    assert ok2 is False
    assert sig2['reason'] == 'noop_complete'
    assert aside.send.await_count == 0  # silent no-op


# ─── Trigger contract: command sequence shape is trigger-agnostic ──

def test_trigger_does_not_branch_command_emission_shape():
    """Same engine + combatant state with status=<None> → same suggested
    command sequence regardless of trigger. Per-trigger logic is the
    Case A/B branch at the numeric-HP idempotency layer."""
    captured.clear()
    cid_h = _campaign()
    cid_i = _campaign()
    for cid in (cid_h, cid_i):
        npc_upsert(cid, 'UniformProj', skeleton_origin=False)
        npc_hydrate_stats(cid, 'UniformProj', cr_str='2', source='hook')
        _seed_combatant(cid, 'UniformProj', init=15, status_kind='none')

    ch_h, aside_h = _mock_channel_with_aside()
    ch_i, aside_i = _mock_channel_with_aside()

    ok_h, sig_h = _run(_project(ch_h, cid_h, 'UniformProj', trigger='hydrate'))
    ok_i, sig_i = _run(_project(ch_i, cid_i, 'UniformProj', trigger='init_list'))

    assert ok_h is True and ok_i is True
    # Same suggested command sequence regardless of trigger
    assert sig_h['commands_suggested'] == sig_i['commands_suggested']


# ─── Telemetry coverage ────────────────────────────────────────────

def test_telemetry_one_outcome_log_per_path():
    """Every invocation emits at least one terminal telemetry log."""
    cid = _campaign()

    paths_with_outcome = []

    # gate_engine_missing
    captured.clear()
    ch, _ = _mock_channel_with_aside()
    _run(_project(ch, cid, 'NoSuchNPC', trigger='hydrate'))
    if any('avrae_projection_skipped' in m for m in captured):
        paths_with_outcome.append('gate_engine_missing')

    # gate_engine_stats_null
    captured.clear()
    npc_upsert(cid, 'TeleNullStat', skeleton_origin=False)
    _seed_combatant(cid, 'TeleNullStat', init=10, status_kind='none')
    ch, _ = _mock_channel_with_aside()
    _run(_project(ch, cid, 'TeleNullStat', trigger='hydrate'))
    if any('avrae_projection_skipped' in m for m in captured):
        paths_with_outcome.append('gate_engine_stats_null')

    # gate_not_in_init
    captured.clear()
    npc_upsert(cid, 'TeleNoInit', skeleton_origin=False)
    npc_hydrate_stats(cid, 'TeleNoInit', cr_str='1/4', source='hook')
    ch, _ = _mock_channel_with_aside()
    _run(_project(ch, cid, 'TeleNoInit', trigger='hydrate'))
    if any('avrae_projection_skipped' in m for m in captured):
        paths_with_outcome.append('gate_not_in_init')

    # noop_complete (Case B)
    captured.clear()
    npc_upsert(cid, 'TeleNoop', skeleton_origin=False)
    npc_hydrate_stats(cid, 'TeleNoop', cr_str='1/4', source='hook')
    _seed_combatant(cid, 'TeleNoop', init=10, status_kind='numeric')
    ch, _ = _mock_channel_with_aside()
    _run(_project(ch, cid, 'TeleNoop', trigger='init_list'))
    if any('avrae_projection_skipped' in m for m in captured):
        paths_with_outcome.append('noop_complete')

    # suggested
    captured.clear()
    npc_upsert(cid, 'TeleSugg', skeleton_origin=False)
    npc_hydrate_stats(cid, 'TeleSugg', cr_str='1/4', source='hook')
    _seed_combatant(cid, 'TeleSugg', init=10, status_kind='none')
    ch, _ = _mock_channel_with_aside()
    _run(_project(ch, cid, 'TeleSugg', trigger='init_list'))
    if any('avrae_projection_succeeded' in m for m in captured):
        paths_with_outcome.append('suggested')

    # suggested_with_warning (Case A)
    captured.clear()
    npc_upsert(cid, 'TeleWarn', skeleton_origin=False)
    npc_hydrate_stats(cid, 'TeleWarn', cr_str='1', source='hook')
    _seed_combatant(cid, 'TeleWarn', init=10, status_kind='numeric')
    ch, _ = _mock_channel_with_aside()
    _run(_project(ch, cid, 'TeleWarn', trigger='hydrate'))
    if any('avrae_projection_succeeded' in m for m in captured):
        paths_with_outcome.append('suggested_with_warning')

    assert len(paths_with_outcome) == 6, (
        f"expected 6 paths with outcome logs, got {len(paths_with_outcome)}: "
        f"{paths_with_outcome}"
    )


# ─── Critical guard: bot does NOT post to #dm-narration ─────────────

def test_no_bare_avrae_commands_ever_sent_to_narration_channel():
    """S41 pivot regression: the suggester must NEVER call channel.send
    on the narration channel (would emit a bare !-prefixed command Avrae
    would silently filter anyway, AND would violate §65 if it didn't
    get filtered). All output goes to #dm-aside."""
    captured.clear()
    cid = _campaign()
    npc_upsert(cid, 'NarrationGuard', skeleton_origin=False)
    npc_hydrate_stats(cid, 'NarrationGuard', cr_str='1/4', source='hook')

    # Run every reason path through the helper; assert ch.send count is
    # always zero. Some paths skip; some post to aside; none touch ch.
    for status, trigger in [
        ('none', 'init_list'),
        ('none', 'hydrate'),
        ('numeric', 'init_list'),
        ('numeric', 'hydrate'),
    ]:
        _seed_combatant(cid, 'NarrationGuard', init=10, status_kind=status)
        ch, _ = _mock_channel_with_aside()
        _run(_project(ch, cid, 'NarrationGuard', trigger=trigger))
        assert ch.send.await_count == 0, (
            f"helper called channel.send on the narration channel for "
            f"status={status} trigger={trigger}; S41 pivot requires all "
            f"output goes to #dm-aside (§65 + §1b suggester pattern)"
        )


# ─── Cleanup ─────────────────────────────────────────────────────────

def _cleanup():
    try:
        TEST_DB.unlink()
    except OSError:
        pass


# ─── Run ─────────────────────────────────────────────────────────────

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
