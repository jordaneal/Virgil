#!/usr/bin/env python3
"""
Virgil DnD Discord Bot — Avrae co-DM architecture.

Avrae owns mechanics (rolls, sheets, attacks, spells, HP, initiative).
This bot owns NARRATIVE: scene description, NPC voice, world reactions,
and consequences keyed off Avrae's roll outputs.

Commands:
  /setup        — DM. Create channel structure for the server.
  /newcampaign  — DM. Start a new campaign.
  /campaigns    — DM. List campaigns for this server.
  /bindchar     — Bind a Discord user to a character (narrative only — Avrae
                  holds the actual sheet via D&D Beyond).
  /play         — DM. Open the scene with an opening narration.
  /nudge        — DM. Prompt a player to act in-character.
  /dmhelp       — Show the DM cheatsheet.

Messages in #dm-narration drive the DM. Avrae messages anywhere in the
guild feed the RollBuffer and enrich the next DM turn with mechanical
context.

Service: virgil-discord (systemctl --user)
Token:   DISCORD_BOT_TOKEN in .env
"""

import os
import re
import sys
import asyncio
import datetime
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv('/home/jordaneal/scripts/.env')

sys.path.insert(0, '/home/jordaneal/scripts')

# Engine + Avrae listener (both in /home/jordaneal/scripts/)
from dnd_engine import (
    db_init, chroma_init, chroma_store, dm_respond,
    get_active_campaign, get_characters, get_character_by_controller,
    create_campaign, bind_character, update_scene, list_campaigns,
    campaign_set_status, campaign_delete_cascade,
    init_scene_state, get_scene_state, set_scene_mode,
    clock_create, clock_tick, clock_untick, clock_reset, clock_delete, get_clocks,
    set_active_turn, clear_active_turn, get_active_turn,
    update_combatants_from_init_list, clear_combatants, get_combatants,
    quest_add, quest_set_status, quest_delete, get_active_quests, get_all_quests,
    companion_add, companion_remove, companion_edit, get_companions, COMPANION_CAP,
    update_tension,
    get_bound_character_names,
    canonicalize_actor_name,
    npc_upsert, npc_fragmentation_report, npc_list,
    stat_incomplete, npc_hydrate_stats, npc_register_avrae_madd, npc_get_by_name,
    location_upsert, location_get, location_get_by_name, location_list,
    set_current_location, get_current_location,
    phantom_location_candidates,
    world_health_report,
    consequence_list_for_command,
    add_item, get_inventory,
    get_pending_loot,
    advance_time, parse_elapsed, PHASES,
    log,
)
from cloud_router import route as cloud_route
from commands_doc_generator import update_commands_doc
import avrae_listener as al
import dnd_orchestration as orch
from mechanical_hints import parse_mechanical_hints
from npc_extractor import parse_npcs
import srd_resolver
from location_extractor import parse_locations
import npc_hydrator

import discord
from discord.ext import commands
from discord import app_commands


# Track 6 #4: names already prompted for CR this session (lost on restart —
# accepted; re-prompt fires on next !init list after restart).
_pending_hydration: set[tuple[int, str]] = set()


# ─────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────

DISCORD_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
LOG_PATH = Path('/mnt/virgil_storage/digest/discord_dnd.log')

# Override Avrae user ID via .env if needed (e.g. for testing servers).
AVRAE_USER_ID_OVERRIDE = os.getenv('AVRAE_USER_ID')
if AVRAE_USER_ID_OVERRIDE:
    try:
        al.set_avrae_user_id(int(AVRAE_USER_ID_OVERRIDE))
    except ValueError:
        pass

# How long to wait after a player message in #dm-narration before the DM
# responds. Lets multiple players' actions batch into one narration beat.
ACTION_BATCH_WINDOW = 15


# Canonical channel names (Session 23 #3 — channel cleanup; #4 — onboarding).
# Consolidated from the older 7-channel structure: rolls/sheets/loot/commands
# were dropped (Avrae rolls happen in #dm-narration, DDB owns sheets, slash
# commands work anywhere). 'ooc' renamed from #ooc-general to #party-chat.
# 'aside' added for Track 6 #3 advisory mode (channel created by /setup,
# routing not yet wired). 'welcome' added S23 #4 — points new players at
# virgildm.com via a pinned message; positioned first in OOC category.
#
# Branding note: site is "Virgil's Hearth" (marketing), bot is "Virgil DM"
# (product), codebase is "Virgil" (internal). Consolidation is a marketing
# decision, not a code fix.
#
# Insertion order matters — compute_setup_plan iterates dict in order, and
# Discord positions channels within a category by creation order. 'welcome'
# is placed before 'ooc' in this dict so a fresh /setup run creates it
# above #party-chat. On mixed-state guilds, /setup additionally edits the
# position to top-of-category for idempotent placement.
CHANNEL_NAMES = {
    'narration': 'dm-narration',
    'aside':     'dm-aside',
    'lore':      'lore-notes',
    'welcome':   'welcome',
    'commands':  'commands',
    'ooc':       'party-chat',
}

# Canonical category structure (Session 23 #3).
# Channel keys above map to category keys here. Voice channels listed
# separately since they need create_voice_channel.
CATEGORY_NAMES = {
    'dm':    '🎲 VIRGIL DM',
    'ooc':   '💬 OUT OF CHARACTER',
    'voice': '🔊 VOICE',
}

CHANNEL_CATEGORY = {
    'narration': 'dm',
    'aside':     'dm',
    'lore':      'dm',
    'welcome':   'ooc',
    'commands':  'ooc',
    'ooc':       'ooc',
}

# Channel keys that get read-only-for-players overwrites (DM/bot/Avrae
# write; @everyone read but not send). Both #lore-notes (DM session
# notes) and #welcome (pinned onboarding link, not a discussion channel)
# share this shape.
READ_ONLY_FOR_PLAYERS = {'lore', 'welcome'}

# Channel keys where Avrae is read-only (cannot send). #lore-notes is the
# DM's private notes surface — Avrae's `!`-prefixed output should never
# land there. Avrae still needs read so it can be referenced; just no write.
AVRAE_READ_ONLY = {'lore'}

VOICE_CHANNELS = (
    ('General', 'voice'),  # (channel_name, category_key)
    ('AFK',     'voice'),  # auto-move target after AFK_TIMEOUT_SECONDS idle
)

# Guild-wide AFK auto-move config. afk_timeout accepts a fixed set of values
# (60, 300, 900, 1800, 3600). 1800 = 30 min.
AFK_VOICE_CHANNEL_NAME = 'AFK'
AFK_TIMEOUT_SECONDS = 1800

# Legacy category that pre-Session-23 /setup created. Detected by /setup
# and removed if empty after channels are migrated to canonical categories.
LEGACY_CATEGORY_NAME = "🎲 D&D"

# #welcome pinned-message body (S23 #4). Posted once per guild by /setup,
# pinned, replaced only on content-drift (idempotent). Points at virgildm.com
# for the full onboarding flow; the bot's role here is ENTRY POINT, not a
# duplicate of the site's content.
WELCOME_PIN_BODY = (
    "**Welcome to the table.**\n\n"
    "🆕 **New to D&D?** Start here: https://virgildm.com\n"
    "   Six guided steps from \"I've never played\" to \"I'm ready for tonight.\"\n\n"
    "🎲 **Played before?** Skip to commands: https://virgildm.com#codex\n"
    "   Quick reference for `/bindchar`, `/refresh`, and what the DM will run.\n\n"
    "Once you're ready, head to #dm-narration and tell the DM you're set."
)

# Channel topic for #welcome — short, points at the site.
WELCOME_CHANNEL_TOPIC = "New here? Start at https://virgildm.com"

# #commands pinned-message body (S31). Posted once per guild by /setup,
# pinned, replaced only on content-drift (idempotent). Hybrid shape: 5
# inline commands for quick reference, then pointer to /dmhelp for the
# full list and #welcome for new-player onboarding.
COMMANDS_PIN_BODY = (
    "📋 **Slash Command Quick Reference**\n\n"
    "The most common commands you'll use here:\n"
    "• `/play` — start or resume a session\n"
    "• `/inventory` — view your character's items\n"
    "• `/refresh` — refresh character sheet cache\n"
    "• `/newcampaign` — DM only, create a new campaign\n"
    "• `/dmhelp` — full slash command reference\n\n"
    "Run `/dmhelp` for everything else. "
    "New here? See #welcome for setup and the player guide."
)


logging.basicConfig(level=logging.INFO)
logging.getLogger('discord').setLevel(logging.WARNING)


# Use mention-only command prefix so we don't conflict with Avrae's `!`.
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=commands.when_mentioned, intents=intents)
buffer = al.RollBuffer()


# ─────────────────────────────────────────────────────────
# Permission helper (Session 10 / 10F)
# ─────────────────────────────────────────────────────────

def is_dm_or_creator(interaction: discord.Interaction) -> bool:
    """Returns True if the user can run table-management commands.
    Two qualifying paths:
      - manage_guild perm (real DM in a multiplayer guild)
      - the user created the active campaign (solo-as-DM friction fix)
    Falls back to manage_guild only when no campaign or no creator stamped
    (legacy campaigns from before the migration).
    """
    if interaction.user.guild_permissions.manage_guild:
        return True
    if not interaction.guild_id:
        return False
    campaign = get_active_campaign(str(interaction.guild_id))
    if not campaign:
        return False
    creator_id = campaign.get('created_by_user_id') or ''
    return bool(creator_id and str(interaction.user.id) == creator_id)


# ─────────────────────────────────────────────────────────
# Channel helpers
# ─────────────────────────────────────────────────────────

def get_channel(guild: discord.Guild, key: str) -> discord.TextChannel | None:
    name = CHANNEL_NAMES.get(key, key)
    return discord.utils.get(guild.text_channels, name=name)


# ─────────────────────────────────────────────────────────
# Pure setup planner (Session 23 #3 — channel cleanup)
# ─────────────────────────────────────────────────────────
# Pure function — given a snapshot of guild category/channel state,
# return the actions /setup must take to produce the canonical
# structure. Tested without Discord API mocks. The /setup command
# builds the snapshot from discord.Guild, calls this function, then
# executes the returned plan via discord API calls.

def compute_setup_plan(
    text_channels: dict,
    voice_channels: dict,
    categories: set,
    channel_names: dict | None = None,
    category_names: dict | None = None,
    channel_category: dict | None = None,
    voice_channel_specs: tuple | None = None,
    legacy_category_name: str | None = None,
    commands_existing_pin_body: str | None = None,
) -> dict:
    """Return the actions /setup must take to converge `guild_state` to the
    canonical structure. Pure function — no I/O, no side effects.

    Args:
      text_channels       — {channel_name: parent_category_name|None}
      voice_channels      — {channel_name: parent_category_name|None}
      categories          — set of existing category names
      channel_names       — canonical text-channel name dict (defaults to
                            module-level CHANNEL_NAMES)
      category_names      — canonical category-name dict (defaults to
                            module-level CATEGORY_NAMES)
      channel_category    — channel-key → category-key map (defaults to
                            module-level CHANNEL_CATEGORY)
      voice_channel_specs — tuple of (channel_name, category_key) (defaults
                            to module-level VOICE_CHANNELS)
      legacy_category_name — old category to detect-and-delete if empty
                             after planned moves (defaults to module-level
                             LEGACY_CATEGORY_NAME)
      commands_existing_pin_body — stripped body of the current bot-authored
                             pin in #commands, or None if no such pin exists.
                             Used to compute commands_pin_action.

    Returns:
      {
        'categories_to_create':       list[str],
        'text_channels_to_create':    list[(name, category_name)],
        'voice_channels_to_create':   list[(name, category_name)],
        'text_channels_to_move':      list[(name, target_category_name)],
        'voice_channels_to_move':     list[(name, target_category_name)],
        'text_channels_existing':     list[str],   # already correct, no-op
        'voice_channels_existing':    list[str],
        'categories_existing':        list[str],
        'legacy_category_to_delete':  str | None,  # name if exists and empty post-move
        'commands_pin_action':        'create' | 'replace' | 'noop' | 'skipped',
      }

    Idempotency: re-running on a fully-canonical guild produces a plan
    where every list is empty and existing lists hold every canonical
    entity name.
    """
    cn = channel_names if channel_names is not None else CHANNEL_NAMES
    ca = category_names if category_names is not None else CATEGORY_NAMES
    cc = channel_category if channel_category is not None else CHANNEL_CATEGORY
    vcs = voice_channel_specs if voice_channel_specs is not None else VOICE_CHANNELS
    legacy = (legacy_category_name if legacy_category_name is not None
              else LEGACY_CATEGORY_NAME)

    plan = {
        'categories_to_create':      [],
        'text_channels_to_create':   [],
        'voice_channels_to_create':  [],
        'text_channels_to_move':     [],
        'voice_channels_to_move':    [],
        'text_channels_existing':    [],
        'voice_channels_existing':   [],
        'categories_existing':       [],
        'legacy_category_to_delete': None,
        'commands_pin_action':       'skipped',
    }

    # Categories — create any canonical ones missing.
    for cat_key, cat_name in ca.items():
        if cat_name in categories:
            plan['categories_existing'].append(cat_name)
        else:
            plan['categories_to_create'].append(cat_name)

    # Text channels — for each canonical channel, decide create / move / no-op.
    for chan_key, chan_name in cn.items():
        target_cat_key = cc.get(chan_key)
        target_cat_name = ca.get(target_cat_key) if target_cat_key else None
        if chan_name not in text_channels:
            plan['text_channels_to_create'].append((chan_name, target_cat_name))
            continue
        current_cat = text_channels[chan_name]
        if current_cat != target_cat_name:
            plan['text_channels_to_move'].append((chan_name, target_cat_name))
        else:
            plan['text_channels_existing'].append(chan_name)

    # Voice channels — same shape, voice instead of text.
    for vc_name, target_cat_key in vcs:
        target_cat_name = ca.get(target_cat_key) if target_cat_key else None
        if vc_name not in voice_channels:
            plan['voice_channels_to_create'].append((vc_name, target_cat_name))
            continue
        current_cat = voice_channels[vc_name]
        if current_cat != target_cat_name:
            plan['voice_channels_to_move'].append((vc_name, target_cat_name))
        else:
            plan['voice_channels_existing'].append(vc_name)

    # Legacy-category cleanup: if the old category exists AND no text/voice
    # channels remain in it after planned moves, mark it for deletion.
    if legacy and legacy in categories:
        # Names of all channels currently in legacy
        in_legacy_text = {
            n for n, c in text_channels.items() if c == legacy
        }
        in_legacy_voice = {
            n for n, c in voice_channels.items() if c == legacy
        }
        # Names of canonical channels that will be MOVED out of legacy
        moving_out_text = {
            n for n, _ in plan['text_channels_to_move']
            if text_channels.get(n) == legacy
        }
        moving_out_voice = {
            n for n, _ in plan['voice_channels_to_move']
            if voice_channels.get(n) == legacy
        }
        remaining = (
            (in_legacy_text - moving_out_text)
            | (in_legacy_voice - moving_out_voice)
        )
        if not remaining:
            plan['legacy_category_to_delete'] = legacy

    # Commands pin lifecycle (S31). 'skipped' is the defensive default
    # (already set above); only fires when 'commands' key is absent from
    # channel_names (custom dict, shouldn't happen in production).
    commands_chan_name = cn.get('commands')
    if commands_chan_name:
        if commands_chan_name not in text_channels:
            # Channel will be created this run — pin it fresh.
            plan['commands_pin_action'] = 'create'
        elif commands_existing_pin_body is None:
            # Channel exists but no bot-authored pin found.
            plan['commands_pin_action'] = 'create'
        elif commands_existing_pin_body.strip() == COMMANDS_PIN_BODY.strip():
            # Pin matches — no-op.
            plan['commands_pin_action'] = 'noop'
        else:
            # Pin drifted — replace.
            plan['commands_pin_action'] = 'replace'

    return plan


def setup_plan_log_summary(plan: dict) -> str:
    """Compact log representation of a setup plan.

    Used by /setup for the per-execution `setup_run:` log line.
    """
    if not plan:
        return ("channels_created=0 channels_moved=0 channels_existing=0 "
                "categories_created=0 categories_existing=0 "
                "legacy_deleted=0 commands_pin=skipped")
    chans_created = (len(plan.get('text_channels_to_create', []))
                     + len(plan.get('voice_channels_to_create', [])))
    chans_moved = (len(plan.get('text_channels_to_move', []))
                   + len(plan.get('voice_channels_to_move', [])))
    chans_existing = (len(plan.get('text_channels_existing', []))
                      + len(plan.get('voice_channels_existing', [])))
    cats_created = len(plan.get('categories_to_create', []))
    cats_existing = len(plan.get('categories_existing', []))
    legacy_del = 1 if plan.get('legacy_category_to_delete') else 0
    commands_pin = plan.get('commands_pin_action', 'skipped')
    return (
        f"channels_created={chans_created} "
        f"channels_moved={chans_moved} "
        f"channels_existing={chans_existing} "
        f"categories_created={cats_created} "
        f"categories_existing={cats_existing} "
        f"legacy_deleted={legacy_del} "
        f"commands_pin={commands_pin}"
    )


# ─────────────────────────────────────────────────────────
# Per-guild action batcher
# ─────────────────────────────────────────────────────────

class ActionBatcher:
    """Collects player actions for ACTION_BATCH_WINDOW seconds then fires
    one DM response covering everyone's actions."""

    def __init__(self):
        self._pending: dict[int, list] = {}
        self._timers: dict[int, asyncio.Task] = {}

    def add(self, guild_id: int, user_display: str, action: str, callback,
            window: int = None, user_id: str = None, **kwargs):
        if guild_id not in self._pending:
            self._pending[guild_id] = []
        # 3-tuple (display, action, user_id) — user_id consumed by persistence
        # directive's typing-identity comparison. Older 2-tuple unpack sites
        # tolerate the extra slot via the slicing pattern below.
        self._pending[guild_id].append((user_display, action, user_id))

        delay = window if window is not None else ACTION_BATCH_WINDOW
        # Cancel prior timer; restart the window.
        if guild_id in self._timers and not self._timers[guild_id].done():
            self._timers[guild_id].cancel()
        self._timers[guild_id] = asyncio.create_task(
            self._fire_after_delay(guild_id, delay, callback, kwargs)
        )

    async def _fire_after_delay(self, guild_id: int, delay: int, callback, kwargs):
        try:
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            return
        actions = self._pending.pop(guild_id, [])
        if not actions:
            return
        combined = "\n".join(f"{tup[0]}: {tup[1]}" for tup in actions)
        try:
            await callback(actions=actions, combined_action=combined, **kwargs)
        except Exception as e:
            log(f"batcher callback error: {e}")
            import traceback; log(traceback.format_exc())


batcher = ActionBatcher()


# ─────────────────────────────────────────────────────────
# Custom emojis (set via Dev Portal — IDs survive across servers)
# ─────────────────────────────────────────────────────────

E = {
    'think':       '<:virgil_think:1498591213677187082>',
    'ok':          '<:virgil_ok:1498591212943183942>',
    'lurk':        '<:virgil_lurk:1498591211911647262>',
    'facepalm':    '<:virgil_facepalm:1498591210753884210>',
    'derp':        '<:virgil_derp:1498591209738997761>',
    'angry':       '<:virgil_angry:1498591208099020951>',
    'nat20':       '<:nat_20:1498591201870483607>',
    'nat1':        '<:nat_1:1498591200771309598>',
    'loot':        '<:gimmie_loot:1498591195843133470>',
}


# ─────────────────────────────────────────────────────────
# Discord events
# ─────────────────────────────────────────────────────────

async def _warm_character_cache_on_startup(bot):
    """Scan recent channel history for Avrae sheet embeds and populate
    _CHARACTER_CACHE, eliminating the post-restart `/refresh` requirement.

    Mirrors `/refresh` scan logic but iterates all active-campaign guilds
    and scans both #character-sheets and #dm-narration. First sheet found
    per character name wins (channel.history yields newest-first).

    Failures in any guild/channel are swallowed and logged — startup must
    continue even if a single channel is inaccessible."""
    # Post-S23-#3 channel consolidation: 'sheets' is no longer canonical
    # (DDB owns sheets, Avrae's `!sheet` output now lands in dm-narration
    # like every other Avrae output). Bootstrap warm only scans narration.
    # If a legacy #character-sheets channel still exists on a server, the
    # warm pass on `narration` will find Avrae sheet embeds posted there
    # going forward; the historical-but-stale channel is harmless.
    #
    # Track 7 #1.1: SCAN_LIMIT raised from 50 → 300 so multi-PC campaigns
    # whose !sheet posts have aged past 50 messages still cache-warm
    # without operator intervention. cache_warm_incomplete diagnostic
    # emits per-campaign for any bound PC still uncached after the scan,
    # so the gap is observable empirically (we don't pretend coverage we
    # don't have) and the operator knows to ask the player to re-run
    # !sheet — the only path that respects the bot-Avrae write boundary
    # (Doctrine §65).
    SCAN_CHANNELS = ('narration',)
    SCAN_LIMIT = 300

    for guild in bot.guilds:
        try:
            campaign = get_active_campaign(str(guild.id))
            if not campaign:
                continue

            scanned = 0
            seen_names: set[str] = set()
            cached_names: list[str] = []

            for channel_key in SCAN_CHANNELS:
                channel = get_channel(guild, channel_key)
                if not channel:
                    continue
                try:
                    async for msg in channel.history(limit=SCAN_LIMIT):
                        scanned += 1
                        if not al.is_avrae(msg):
                            continue
                        for embed in msg.embeds:
                            ctx = orch.parse_avrae_sheet_embed(embed)
                            if not ctx:
                                continue
                            if ctx.name in seen_names:
                                continue
                            seen_names.add(ctx.name)
                            ctx.source_message_id = msg.id
                            orch.invalidate_cache(ctx.name)
                            orch.set_cached_context(ctx)
                            cached_names.append(ctx.name)
                            log(
                                f"cache_warm: cached name={ctx.name} "
                                f"race={ctx.race} class={ctx.char_class} "
                                f"level={ctx.level}"
                            )
                            # Phase 6: refresh canonical_name on the bound
                            # character matching this sheet, if found. Matching
                            # uses strict resolve_actor — no fuzzy fallback.
                            # If no match, log so operator can register an
                            # alias if needed.
                            try:
                                bound = orch.resolve_actor(campaign['id'], ctx.name)
                                if bound:
                                    orch.refresh_canonical_name(
                                        bound.get('controller', ''),
                                        ctx.name,
                                        campaign['id'],
                                    )
                                else:
                                    log(
                                        f"cache_warm: sheet name='{ctx.name}' "
                                        f"has no matching bound character in "
                                        f"campaign={campaign['id']} — register "
                                        f"an alias if it should map to an "
                                        f"existing character"
                                    )
                            except Exception as e:
                                log(f"cache_warm: refresh error name={ctx.name} err={e!r}")
                except discord.Forbidden:
                    log(
                        f"cache_warm: forbidden guild={guild.id} "
                        f"channel={channel_key}"
                    )
                except Exception as e:
                    log(
                        f"cache_warm: scan error guild={guild.id} "
                        f"channel={channel_key} err={e}"
                    )

            log(
                f"cache_warm: guild={guild.id} campaign={campaign['id']} "
                f"scanned={scanned} cached={cached_names}"
            )

            # Track 7 #1.1 — surface gaps. Compare bound PCs against what
            # cache_warm actually populated; log uncached names so the
            # capability adjudication degradation (primary_ctx=None →
            # gate defers) is observable, not silent. Cached set is
            # case-normalized for comparison so "Jordonovan Bigsby"
            # vs "jordonovan bigsby" doesn't false-positive.
            try:
                bound_names = get_bound_character_names(campaign['id']) or []
                cached_norm = {n.strip().lower() for n in cached_names}
                uncached = [
                    n for n in bound_names
                    if n.strip().lower() not in cached_norm
                ]
                if uncached:
                    log(
                        f"cache_warm_incomplete: guild={guild.id} "
                        f"campaign={campaign['id']} "
                        f"bound_uncached={uncached} — capability "
                        f"adjudication will defer for these PCs until "
                        f"player runs `!sheet` in #dm-narration"
                    )
            except Exception as e:
                log(f"cache_warm_incomplete: diagnostic error err={e!r}")
        except Exception as e:
            log(f"cache_warm: guild error guild={guild.id} err={e}")


@bot.event
async def on_ready():
    log(f"Discord DnD bot ready: {bot.user} ({bot.user.id})")
    try:
        synced = await bot.tree.sync()
        log(f"synced {len(synced)} slash commands")
    except Exception as e:
        log(f"sync error: {e}")
    # Track 6 #3.2 — regenerate the Virgil section of COMMANDS.md from
    # bot.tree decorators. Soft-fail: any error logs and continues so a
    # doc-write failure never blocks bot startup.
    try:
        result = update_commands_doc(
            bot, str(orch.COMMANDS_DOC_PATH)
        )
        log(
            f"commands_doc_update: count={result['commands_count']} "
            f"changed={1 if result['doc_changed'] else 0} "
            f"markers_found={1 if result['markers_found'] else 0} "
            f"error={result['error'] or 'none'}"
        )
    except Exception as e:
        log(f"commands_doc_update: top-level error err={e!r}")
    try:
        await _warm_character_cache_on_startup(bot)
    except Exception as e:
        log(f"cache_warm: top-level error err={e}")



@bot.tree.command(name='refresh', description='Refresh the cached character data from a recent Avrae !sheet.')
@app_commands.describe(name='Character name (defaults to your bound character)')
async def refresh(interaction: discord.Interaction, name: str = ''):
    guild_id = str(interaction.guild_id)
    campaign = get_active_campaign(guild_id)
    if not campaign:
        await interaction.response.send_message(
            "No active campaign.", ephemeral=True
        )
        return

    target_name = name
    if not target_name:
        char = get_character_by_controller(campaign['id'], str(interaction.user.id))
        if not char:
            await interaction.response.send_message(
                "You have no bound character. Pass a name or run `/bindchar` first.",
                ephemeral=True,
            )
            return
        target_name = char['name']

    await interaction.response.defer(ephemeral=True)
    found = None
    try:
        async for msg in interaction.channel.history(limit=50):
            if not al.is_avrae(msg):
                continue
            for embed in msg.embeds:
                ctx = orch.parse_avrae_sheet_embed(embed)
                if ctx and ctx.name.lower() == target_name.lower():
                    ctx.source_message_id = msg.id
                    orch.invalidate_cache(target_name)
                    orch.set_cached_context(ctx)
                    found = ctx
                    break
            if found:
                break
    except Exception as e:
        log(f"/refresh: scan failed: {e}")
        await interaction.followup.send(f"Scan failed: {e}", ephemeral=True)
        return

    if not found:
        await interaction.followup.send(
            f"No Avrae sheet for **{target_name}** found in this channel. "
            f"Have the player run `!sheet` here, then try `/refresh` again.",
            ephemeral=True,
        )
        return

    await interaction.followup.send(
        f"{E['ok']} Refreshed **{found.name}** "
        f"({found.race} {found.char_class} {found.level}). "
        f"Tags: {', '.join(sorted(found.narrative_tags)) or '—'}.",
        ephemeral=True,
    )

async def _handle_init_event(message, init_evt):
    """Map an Avrae init event onto campaign state.
    Pure mechanical mapping — no LLM.
    begin → combat mode
    end   → exploration mode + clear combat turn state
    turn  → set active turn controller (2A.2)
    'add' and 'end_prompt' are no-ops here.
    """
    try:
        if not message.guild:
            return
        campaign = get_active_campaign(str(message.guild.id))
        if not campaign:
            return
        scene = get_scene_state(campaign['id'])
        if not scene:
            return  # No scene state — /play hasn't been run

        evt_type = init_evt.get('init_event')
        current_mode = scene.get('mode') or 'exploration'

        if evt_type == 'begin' and current_mode != 'combat':
            set_scene_mode(campaign['id'], 'combat')
            log(f"init: combat started (guild={message.guild.id}) → mode='combat'")
        elif evt_type == 'end' and current_mode == 'combat':
            set_scene_mode(campaign['id'], 'exploration')
            clear_active_turn(campaign['id'])
            clear_combatants(campaign['id'])
            log(f"init: combat ended (guild={message.guild.id}) → mode='exploration', combat state cleared")
        elif evt_type == 'turn':
            controller_id = init_evt.get('controller_id')
            name = init_evt.get('name', '')
            round_num = init_evt.get('round', 0)
            if controller_id and name:
                set_active_turn(campaign['id'], str(controller_id), name, round_num)
    except Exception as e:
        log(f"_handle_init_event error: {e}")


async def _post_hydration_prompt(channel, campaign_id: int, npc_name: str):
    """Post a CR-prompt to #dm-aside for an NPC with no stats.

    Tracks the (campaign_id, npc_name) pair in _pending_hydration so duplicate
    prompts within a session are suppressed. Lost on restart — accepted.
    """
    key = (campaign_id, npc_name)
    if key in _pending_hydration:
        return
    try:
        aside_ch = discord.utils.get(channel.guild.text_channels, name='dm-aside')
        if aside_ch is None:
            return
        await aside_ch.send(
            f"Hydration needed: `{npc_name}` just entered initiative with no stats. "
            f"What CR? `/hydrate npc:{npc_name} cr:N`"
        )
        _pending_hydration.add(key)
    except Exception as e:
        log(f"_post_hydration_prompt error: npc='{npc_name}' err={e!r}")


async def _handle_init_list_event(message, parsed):
    """Map an Avrae `!init list` snapshot onto dnd_combatant_state.

    parsed is the output of avrae_listener.parse_init_list_embed — a full
    per-combatant snapshot. Pure mechanical mapping, no LLM. Replace-in-place
    via update_combatants_from_init_list, so each new snapshot supersedes the
    prior one for this campaign.
    """
    try:
        if not message.guild:
            return
        campaign = get_active_campaign(str(message.guild.id))
        if not campaign:
            return
        combatants = parsed.get('combatants') or []
        n = update_combatants_from_init_list(campaign['id'], parsed)
        hp_present = any(
            c.get('hp_max') is not None for c in combatants
        )
        conditions_present = any(
            (c.get('conditions') or '').strip() for c in combatants
        )

        # Step 2.5 — Track 6 #4 hydration + classification scan.
        # §11.M lock: status_token classifies !init add vs !init madd routing.
        # §11.L lock: caller checks cr_hint FIRST; posts prompt FIRST if None.
        campaign_id = campaign['id']
        bound_names = {n_name.lower() for n_name in (get_bound_character_names(campaign_id) or [])}
        for row in combatants:
            cbt_name = row['name']
            status_token = row.get('status_token', '<None>')
            if cbt_name.lower() in bound_names:
                log(f"hydration: campaign={campaign_id} npc='{cbt_name}' "
                    f"source=bound_pc_skip stats_filled=none cr=none "
                    f"status_token={status_token}")
                continue
            if status_token != '<None>':
                # Avrae-backed combatant (!init madd path): register, skip hydration.
                npc_register_avrae_madd(campaign_id, cbt_name, status_token=status_token)
                continue
            # status_token == '<None>': DM-added NPC (!init add path) — hydration.
            npc = npc_get_by_name(campaign_id, cbt_name)
            if npc is not None and not stat_incomplete(npc):
                log(f"hydration: campaign={campaign_id} npc='{cbt_name}' "
                    f"source=miss stats_filled=none cr={npc.get('cr_str') or 'none'} "
                    f"status_token={status_token}")
                continue
            cr_hint = npc.get('cr_str') if npc else None
            if cr_hint is None:
                # §11.L: caller posts prompt BEFORE engine call.
                await _post_hydration_prompt(message.channel, campaign_id, cbt_name)
                npc_hydrate_stats(campaign_id, cbt_name,
                                  cr_str=None, source='generic_fallback')
            else:
                src = ('skeleton'
                       if (npc and npc.get('skeleton_origin') and cr_hint)
                       else 'hook')
                npc_hydrate_stats(campaign_id, cbt_name, cr_str=cr_hint, source=src)

        log(
            f"init_list_parsed: campaign={campaign['id']} "
            f"round={parsed.get('round')} "
            f"current_init={parsed.get('current_init')} "
            f"combatants={n} "
            f"hp_present={1 if hp_present else 0} "
            f"conditions_present={1 if conditions_present else 0}"
        )
    except Exception as e:
        log(f"_handle_init_list_event error: {e}")


async def _handle_rest_event(message, rest_evt):
    """Map an Avrae rest event onto campaign state.
    Pure mechanical mapping — no LLM.

    Avrae !lr / !sr does not fire an init 'end' event, so combat mode can
    get stuck if a fight wraps without a clean !init end (or if init was
    never started). Treat any completed rest as a signal that combat is
    over: flip to exploration, clear any lingering active-turn state.

    Idempotent: if already in exploration, log only.
    """
    try:
        if not message.guild:
            return
        campaign = get_active_campaign(str(message.guild.id))
        if not campaign:
            return
        scene = get_scene_state(campaign['id'])
        if not scene:
            return  # No scene state — /play hasn't been run

        rest_kind = rest_evt.get('detail') or 'rest'
        current_mode = scene.get('mode') or 'exploration'

        if current_mode == 'combat':
            set_scene_mode(campaign['id'], 'exploration')
            clear_active_turn(campaign['id'])
            clear_combatants(campaign['id'])
            log(f"rest: {rest_kind} (guild={message.guild.id}) → "
                f"mode='exploration', combat state cleared")
        else:
            log(f"rest: {rest_kind} (guild={message.guild.id}) → "
                f"already mode='{current_mode}', no-op")

        # Track 4 #3 — time advancement on Avrae rest. Long rest jumps to
        # next morning regardless of current phase (set_phase='Morning'
        # per §11.I=a); short rest bumps one phase. Soft-fail per §59;
        # narration must never block on a time-advance error.
        rk = (rest_kind or '').strip().lower()
        try:
            if rk in ('long', 'longrest', 'lr', 'long rest'):
                advance_time(campaign['id'], 1, 0,
                             source='rest_long',
                             source_detail='Avrae !lr',
                             set_phase='Morning')
            elif rk in ('short', 'shortrest', 'sr', 'short rest'):
                advance_time(campaign['id'], 0, 1,
                             source='rest_short',
                             source_detail='Avrae !sr')
        except Exception as e:
            log(f"_handle_rest_event: advance_time error: {e!r}")
    except Exception as e:
        log(f"_handle_rest_event error: {e}")


@bot.event
async def on_message_edit(before: discord.Message, after: discord.Message):
    """Catches Avrae message edits as state-transition signals.
    Specifically: Avrae edits the 'Are you sure you want to end combat?'
    message in place to 'End of combat report: ...' when the DM confirms
    !init end. No new message is sent, so on_message never fires.
    We treat the edit as a state transition and re-run the init parser.
    """
    if not al.is_avrae(after):
        return
    # Only care about content changes that look like end-of-combat.
    # Retrieve fresh content — edit events can arrive with partial state.
    new_content = (getattr(after, 'content', '') or '').strip()
    if not new_content:
        return
    try:
        init_evt = al.parse_init_event(after)
        if init_evt and init_evt.get('init_event') == 'end':
            await _handle_init_event(after, init_evt)
        # Avrae also edits a posted `!init list` message in place when the
        # list is refreshed (button-driven refresh, end-of-combat replacement).
        # Pick up snapshot updates from edits as well.
        list_parsed = al.parse_init_list_embed(new_content)
        if list_parsed:
            await _handle_init_list_event(after, list_parsed)
    except Exception as e:
        log(f"on_message_edit init handler error: {e}")


@bot.event
async def on_message(message: discord.Message):
    """Routes every message:
      - If from Avrae → parse init events for mode + roll events for buffer.
      - If from a player in #dm-narration → batch as action, fire DM later.
      - Else → ignore.
    """
    # Avrae messages: capture mechanical events
    if al.is_avrae(message):
        try:
            # Track 7 #1.1 — auto-cache fresh Avrae sheet embeds. Players
            # running `!sheet` in #dm-narration must populate the cache
            # without operator intervention; the prior model required
            # `/refresh` after every `!sheet` and that workflow doesn't
            # survive context drift. Caching from on_message closes the
            # loop. Strict: only embeds that parse_avrae_sheet_embed
            # accepts (real sheets, not sheet-shaped lookalikes — the
            # parser already enforces minimum-fidelity gating). Failures
            # are swallowed; sheet-cache miss is recoverable, blocking
            # the rest of the Avrae handler is not.
            for embed in message.embeds:
                try:
                    sheet_ctx = orch.parse_avrae_sheet_embed(embed)
                    if sheet_ctx:
                        sheet_ctx.source_message_id = message.id
                        orch.invalidate_cache(sheet_ctx.name)
                        orch.set_cached_context(sheet_ctx)
                        log(
                            f"cache_autopopulate: name={sheet_ctx.name} "
                            f"race={sheet_ctx.race} class={sheet_ctx.char_class} "
                            f"level={sheet_ctx.level} source=on_message"
                        )
                except Exception as e:
                    log(f"cache_autopopulate: parse error err={e!r}")

            # Initiative events drive scene mode (combat ↔ exploration).
            # Pure regex, no LLM in the path.
            init_evt = al.parse_init_event(message)
            if init_evt:
                await _handle_init_event(message, init_evt)

            # !init list snapshot — populates dnd_combatant_state for the
            # persistence directive (Session 21). Independent of init_event;
            # an Avrae message can be a list output without being a turn event.
            try:
                list_parsed = al.parse_init_list_embed(
                    (getattr(message, 'content', '') or '').strip()
                )
                if list_parsed:
                    await _handle_init_list_event(message, list_parsed)
            except Exception as e:
                log(f"init_list parse error: {e}")

            event = al.parse_avrae_embed(message)
            if event:
                # Phase 6: resolve actor to canonical form before buffering.
                # On miss, store canonicalized raw + log so operator can register
                # an alias durably (system never guesses equivalence).
                guild_id_for_resolve = event.get('guild_id')
                if guild_id_for_resolve is not None:
                    try:
                        camp = get_active_campaign(str(guild_id_for_resolve))
                        if camp:
                            raw_actor = event.get('actor', '') or ''
                            resolved = orch.resolve_actor(camp['id'], raw_actor)
                            if resolved:
                                event['actor'] = resolved['canonical_name']
                            else:
                                canonical = canonicalize_actor_name(raw_actor)
                                event['actor'] = canonical
                                log(f"unresolved_actor: campaign={camp['id']} "
                                    f"name='{raw_actor}' canonical='{canonical}' "
                                    f"(no canonical/alias match)")
                    except Exception as e:
                        log(f"resolve_actor error: {e!r}")
                buffer.add(event)
                # Rest events flush combat mode (Avrae doesn't fire !init end
                # on !lr / !sr — pure mechanical mapping, no LLM).
                if event.get('kind') == 'rest':
                    await _handle_rest_event(message, event)
                # Flag interesting outcomes with a reaction so players see
                # the bot is "watching."
                try:
                    if event.get('nat') == 20 or event.get('crit'):
                        await message.add_reaction(discord.PartialEmoji.from_str(E['nat20']))
                    elif event.get('nat') == 1:
                        await message.add_reaction(discord.PartialEmoji.from_str(E['nat1']))
                except Exception:
                    pass
        except Exception as e:
            log(f"avrae parse error: {e}")
        return

    # Skip the bot itself + other non-Avrae bots
    if message.author.bot:
        return

    # Track 6 #3 — OOC Advisory Lane. Read-only Q&A surface in #dm-aside.
    # Branches off BEFORE the dm-narration gate so advisory traffic never
    # touches the narration path. Invariants enforced inside _advisory_respond:
    # no chroma writes, no scene mutation, no Avrae emission, no directive
    # composition. Different prompt-mode, different output shape.
    if message.guild and message.channel.name == CHANNEL_NAMES['aside']:
        action = (message.content or '').strip()
        if not action:
            return
        # Advisory does not respond to `!`-prefixed commands either —
        # those would be Avrae bookkeeping and don't belong in OOC anyway.
        if action.startswith('!'):
            return
        await _advisory_respond(message)
        return

    # Only process freeform player text in #dm-narration
    if not message.guild or message.channel.name != CHANNEL_NAMES['narration']:
        await bot.process_commands(message)
        return

    guild_id = message.guild.id
    campaign = get_active_campaign(str(guild_id))
    if not campaign:
        return  # No active campaign → silently ignore

    char = get_character_by_controller(campaign['id'], str(message.author.id))
    if not char:
        await message.channel.send(
            f"{message.author.mention} — you don't have a character bound. "
            f"Use `/bindchar` to link your D&D Beyond character to this campaign.",
            delete_after=20
        )
        return

    display = char['name']
    action = message.content.strip()
    if not action:
        return

    # Avrae bookkeeping (!sheet, !coin, !game *, !cc, !update, etc.) and rolls
    # (!roll, !check, !save, !attack, !cast) should not trigger DM narration.
    # Avrae owns the response; roll results flow through RollBuffer and get
    # consumed on the next narrative turn. Anything `!`-prefixed is for Avrae,
    # never the DM.
    if action.startswith('!'):
        return

    # 2A.3 — Turn gating in combat. Only the active controller may submit
    # actionable input during combat. If we're in combat AND have a recorded
    # active turn AND the author isn't the active controller → react ⏳ and
    # bail. If no turn is recorded yet (e.g. !init begin fired but no turn
    # cycle has happened), we let messages through — gating only kicks in
    # once Avrae has actually announced whose turn it is.
    scene = get_scene_state(campaign['id'])
    if scene and (scene.get('mode') or 'exploration') == 'combat':
        active = get_active_turn(campaign['id'])
        if active and str(active['controller_id']) != str(message.author.id):
            try:
                await message.add_reaction('⏳')
            except Exception:
                pass
            log(f"turn gate: dropped msg from {message.author.id} "
                f"(active='{active['character_name']}' controller={active['controller_id']})")
            return

    chroma_store(campaign['id'], 'user', f"{display}: {action}")

    in_combat = scene and (scene.get('mode') or 'exploration') == 'combat'
    batch_window = 1 if in_combat else ACTION_BATCH_WINDOW

    batcher.add(
        guild_id=guild_id,
        user_display=display,
        action=action,
        callback=_dm_respond_and_post,
        window=batch_window,
        user_id=str(message.author.id),
        campaign=campaign,
        characters=get_characters(campaign['id'])
    )

    # Quick reaction so players know the bot saw it
    try:
        await message.add_reaction(discord.PartialEmoji.from_str(E['lurk']))
    except Exception:
        pass


async def _attach_hints(message, embed, narration):
    """Background task: parse mechanical hints from narration, edit message
    in place to append a bookkeeping section if any survive the whitelist.

    Silent on timeout, empty result, or any error. Never blocks narration
    delivery — runs after the post has already happened.
    """
    try:
        hints = await asyncio.wait_for(
            asyncio.to_thread(parse_mechanical_hints, narration),
            timeout=5.0,
        )
    except asyncio.TimeoutError:
        log("_attach_hints: timeout (5s)")
        return
    except Exception as e:
        log(f"_attach_hints: parse error={e!r}")
        return

    if not hints:
        return

    bookkeeping = "\n".join(f"- `{h}`" for h in hints)
    suffix = f"\n\n─────────\n*Bookkeeping (you type these):*\n{bookkeeping}"

    # Discord embed description cap is 4096. Trim original to make room.
    headroom = 4096 - len(suffix) - 8
    base = embed.description or ""
    if len(base) > headroom:
        base = base[:headroom].rstrip() + "..."
    embed.description = base + suffix

    try:
        await message.edit(embed=embed)
        log(f"_attach_hints: appended {len(hints)} hint(s)")
    except discord.NotFound:
        log("_attach_hints: original message gone, skipping edit")
    except Exception as e:
        log(f"_attach_hints: edit failed {e!r}")


async def _extract_and_persist_world(campaign_id, narration, guild=None):
    """Background task: parse locations, then NPCs, persisting both via the
    deterministic engine write paths. Advisory only — never blocks narration
    delivery, never raises into the caller.

    Sequential (locations → NPCs) so that NPC location_hint values can
    resolve to real location_id FKs against rows just written. The
    alternative — parallel extraction — would require a second-pass
    reconciliation step we don't need for one extra ~500ms of total
    background latency.

    Failure model: if location extraction times out / errors, we still
    attempt NPC extraction. NPC location_id stays None for that turn.
    World writes are independent.

    Logs use 'loc_extract:' / 'location_upsert:' / 'npc_extract:' /
    'npc_upsert:' / 'npc_health:' prefixes. Grep by prefix for the
    causal trail.
    """
    # ── Stage 1: locations ──────────────────────────────────────────────
    locations_by_name = {}  # canonical_name → id, used for NPC FK resolution
    try:
        locs = await asyncio.wait_for(
            asyncio.to_thread(parse_locations, narration),
            timeout=8.0,
        )
    except asyncio.TimeoutError:
        log(f"loc_extract: timeout (8s) campaign={campaign_id}")
        locs = []
    except Exception as e:
        log(f"loc_extract: parse error={e!r} campaign={campaign_id}")
        locs = []

    if locs:
        log(f"loc_extract: campaign={campaign_id} "
            f"validated={[loc['name'] for loc in locs]}")

        # Two passes so parent_hint can resolve against locations from this
        # same batch (e.g. "Redhaven" + "Rusty Anchor in Redhaven" → child
        # gets a parent_location_id).
        first_pass_ids = {}
        for loc in locs:
            try:
                row_id = location_upsert(
                    campaign_id=campaign_id,
                    name=loc["name"],
                    type=loc["type"],
                    parent_location_id=None,
                    description=loc["description_fragment"],
                    origin_excerpt=narration[:100],
                    skeleton_origin=False,
                )
                if row_id:
                    first_pass_ids[loc["name"]] = row_id
                    locations_by_name[loc["name"]] = row_id
            except Exception as e:
                log(f"location_upsert: error campaign={campaign_id} "
                    f"name={loc['name']!r} err={e!r}")

        # Second pass — fill parent_location_id from parent_hint where
        # possible. Hint may resolve to a sibling in this batch, an existing
        # row from a prior turn, or nothing (logged but not an error).
        for loc in locs:
            parent_hint = loc.get("parent_hint", "")
            if not parent_hint or loc["name"] not in first_pass_ids:
                continue
            parent_row = locations_by_name.get(parent_hint)
            if parent_row is None:
                # Fall back to the engine — may have been persisted on a prior turn.
                try:
                    existing = location_get_by_name(campaign_id, parent_hint)
                except Exception as e:
                    log(f"location_resolve: error campaign={campaign_id} "
                        f"parent_hint={parent_hint!r} err={e!r}")
                    existing = None
                if existing is not None:
                    parent_row = existing["id"]
                    locations_by_name[parent_hint] = parent_row
            if parent_row is None:
                log(f"location_resolve: unresolved campaign={campaign_id} "
                    f"name={loc['name']!r} parent_hint={parent_hint!r}")
                continue
            if parent_row == first_pass_ids[loc["name"]]:
                # Self-parenting — skip silently.
                continue
            try:
                # parent_location_id is fillable-when-empty in location_upsert's
                # parser×parser branch, so a re-call with the resolved id sets
                # it without bumping mention_count beyond the natural re-mention
                # we'd see anyway. (One extra mention is acceptable; alternative
                # is a dedicated set_parent helper, deferred.)
                location_upsert(
                    campaign_id=campaign_id,
                    name=loc["name"],
                    parent_location_id=parent_row,
                )
            except Exception as e:
                log(f"location_upsert: error (parent backfill) campaign={campaign_id} "
                    f"name={loc['name']!r} err={e!r}")

        log(f"loc_extract: campaign={campaign_id} written={len(first_pass_ids)}")
    else:
        log(f"loc_extract: campaign={campaign_id} validated=0")

    # ── Stage 2: NPCs (with location_hint resolution) ───────────────────
    # Pull bound PCs so the parser can drop player-character mentions
    # from emergent NPC canon. Defense-in-depth: npc_upsert also refuses
    # PC-overlapping names at the engine layer.
    try:
        pc_names = get_bound_character_names(campaign_id)
    except Exception as e:
        log(f"npc_extract: pc_names lookup error={e!r} campaign={campaign_id}")
        pc_names = []

    try:
        npcs = await asyncio.wait_for(
            asyncio.to_thread(parse_npcs, narration, pc_names),
            timeout=8.0,
        )
    except asyncio.TimeoutError:
        log(f"npc_extract: timeout (8s) campaign={campaign_id}")
        return
    except Exception as e:
        log(f"npc_extract: parse error={e!r} campaign={campaign_id}")
        return

    if not npcs:
        log(f"npc_extract: campaign={campaign_id} validated=0")
        # Still emit the health metric on empty turns so the time-series
        # has continuous coverage — fragmentation can rise without writes.
        _emit_npc_health(campaign_id)
        _emit_phantom_candidates(campaign_id)
        _emit_world_health(campaign_id)
        return

    log(f"npc_extract: campaign={campaign_id} "
        f"validated={[n['name'] for n in npcs]}")

    written = 0
    location_resolution_log = []  # for one structured summary line

    for n in npcs:
        # Resolve location_hint → location_id, scoped to this campaign.
        location_id = None
        hint = n.get("location_hint", "")
        if hint:
            location_id = locations_by_name.get(hint)
            if location_id is None:
                # Fall back to engine lookup for prior-turn locations.
                try:
                    existing = location_get_by_name(campaign_id, hint)
                except Exception as e:
                    log(f"npc_location_resolve: error campaign={campaign_id} "
                        f"hint={hint!r} err={e!r}")
                    existing = None
                if existing is not None:
                    location_id = existing["id"]
                    locations_by_name[hint] = location_id

            if location_id is None:
                location_resolution_log.append(f"{n['name']}→unresolved({hint!r})")
            else:
                location_resolution_log.append(f"{n['name']}→loc#{location_id}")

        try:
            upsert_result = npc_upsert(
                campaign_id=campaign_id,
                name=n["name"],
                role=n["role"],
                location_id=location_id,
                description=n["description_fragment"],
                origin_excerpt=narration[:100],
                skeleton_origin=False,
            )
            if upsert_result:
                row_id, was_new = upsert_result
                written += 1
                if was_new and guild:
                    asyncio.ensure_future(
                        _handle_new_npc_for_srd_suggestion(
                            campaign_id, n["name"], guild
                        )
                    )
        except Exception as e:
            log(f"npc_upsert: error campaign={campaign_id} "
                f"name={n['name']!r} err={e!r}")

    log(f"npc_extract: campaign={campaign_id} written={written}")
    if location_resolution_log:
        log(f"npc_location_resolve: campaign={campaign_id} "
            f"resolved=[{', '.join(location_resolution_log)}]")

    _emit_npc_health(campaign_id)
    _emit_phantom_candidates(campaign_id)
    _emit_world_health(campaign_id)


def _emit_npc_health(campaign_id):
    """Log npc_health metric. Wrapped in try/except — never breaks the
    extraction batch. Sub-millisecond cost via indexed SELECT."""
    try:
        report = npc_fragmentation_report(campaign_id)
        log(f"npc_health: campaign={campaign_id} "
            f"entities={report['distinct_entities']} "
            f"rows={report['total_rows']} "
            f"fragmentation_rate={report['fragmentation_rate']:.0%} "
            f"fragments={report['fragment_rows']}")
    except Exception as e:
        log(f"npc_health: error campaign={campaign_id} err={e!r}")


def _emit_phantom_candidates(campaign_id, threshold=3):
    """Log phantom_candidates metric. Wrapped in try/except — never
    breaks the extraction batch. Telemetry only: surfaces parser-origin
    locations with mention_count=1 that haven't been re-referenced
    while N other distinct locations have been mentioned since.

    See dnd_engine.phantom_location_candidates docstring for the
    candidate definition and turn-proxy reasoning. Phantom vs emergent
    indistinguishability is by design — the metric flags candidates,
    the human distinguishes typo phantoms from real geography that
    hasn't yet earned a re-mention.

    Always emits a line, even on count=0, for continuous time-series
    coverage (mirrors _emit_npc_health pattern)."""
    try:
        report = phantom_location_candidates(campaign_id, threshold=threshold)
        if report['count'] == 0:
            log(f"phantom_candidates: campaign={campaign_id} "
                f"count=0 threshold={report['threshold']}")
        else:
            cands = ", ".join(
                f"id={c['id']}/{c['name']}/turns={c['turns_since']}"
                for c in report['candidates']
            )
            log(f"phantom_candidates: campaign={campaign_id} "
                f"count={report['count']} threshold={report['threshold']} "
                f"candidates=[{cands}]")
    except Exception as e:
        log(f"phantom_candidates: error campaign={campaign_id} err={e!r}")


def _emit_world_health(campaign_id, phantom_threshold=3):
    """Log world_health aggregate metric. Wrapped in try/except — never
    breaks the extraction batch.

    Roll-up of three component telemetry primitives (npc_fragmentation,
    location skeleton coverage, phantom location count) into a single
    greppable line. Granular npc_health and phantom_candidates lines
    keep firing independently; this is a composite, not a replacement.

    Deliberately not a single 0-100 score — see world_health_report
    docstring. The four numbers stay independent so the human reads
    them as components, not a verdict."""
    try:
        report = world_health_report(campaign_id, phantom_threshold=phantom_threshold)
        log(f"world_health: campaign={campaign_id} "
            f"npc_frag={report['npc_fragmentation_rate']:.0%} "
            f"npc_rows={report['npc_total']} "
            f"loc_skel_cov={report['loc_skeleton_coverage']:.0%} "
            f"loc_phantoms={report['loc_phantoms']} "
            f"loc_total={report['loc_total']} "
            f"cons_active={report['cons_active']} "
            f"cons_promoted={report['cons_promoted']} "
            f"cons_never_surf={report['cons_never_surfaced']}")
    except Exception as e:
        log(f"world_health: error campaign={campaign_id} err={e!r}")


# ─────────────────────────────────────────────────────────
# Track 6 #5.1 — SRD suggestion hook (Combat Entry Assist)
# ─────────────────────────────────────────────────────────

async def _handle_new_npc_for_srd_suggestion(
    campaign_id: int,
    npc_name: str,
    guild: discord.Guild,
) -> None:
    """Fire srd_resolver.resolve() for a newly-inserted NPC and post
    a suggestion to #dm-aside if a confident SRD candidate is found.

    Soft-fail throughout — any exception is logged and swallowed.
    Narration flow is NEVER blocked by a resolver failure (Doctrine §59).

    No mode gate (§11.H locked). Hook fires on every new NPC upsert
    regardless of scene mode. Session dedup in srd_resolver._SUGGESTED
    is secondary; was_new=False from npc_upsert is the primary guard.
    """
    try:
        result = srd_resolver.resolve(npc_name, campaign_id)
        if result is None:
            return
        dm_aside = discord.utils.get(
            guild.text_channels, name=CHANNEL_NAMES['aside']
        )
        if dm_aside:
            await _post_srd_suggestion(dm_aside, result, campaign_id)
    except Exception as e:
        log(f"_handle_new_npc_for_srd_suggestion error: "
            f"campaign={campaign_id} npc={npc_name!r} err={e!r}")


async def _post_srd_suggestion(
    channel: discord.TextChannel,
    result: srd_resolver.SRDResult,
    campaign_id: int,
) -> None:
    """Format and post the SRD suggestion to #dm-aside.

    Emits the transport-confirmation log line (posted=1) after the
    Discord send completes. The resolver already emitted posted=0 —
    two lines per success is the documented §8 two-line shape.
    """
    body = (
        f"🎯 **SRD match for \"{result.input_name}\":** "
        f"{result.srd_name} (CR {result.cr}, HP {result.hp}, AC {result.ac})\n"
        f"To add with Avrae's full stat block, type:\n"
        f"```\n!init madd \"{result.srd_name}\" -name \"{result.input_name}\"\n```"
        f"*(Or `!init add 0 \"{result.input_name}\"` — Virgil will ask for CR.)*"
    )
    await channel.send(body)
    log(f"srd_suggestion: campaign={campaign_id} input={result.input_name!r} "
        f"candidate={result.srd_name!r} cr={result.cr!r} "
        f"confidence={result.confidence:.2f} method={result.method} posted=1")


# ─────────────────────────────────────────────────────────
# OOC Advisory Lane (Track 6 #3) — handler in #dm-aside
# ─────────────────────────────────────────────────────────
# Read-only Q&A: scene/inventory/turn/combat reference, plain-prose answer.
# INVARIANTS (load-bearing — do not relax without spec change):
#   - No chroma_store / no chroma_search (Track 4 #2 contamination lesson:
#     OOC questions must not seed future narrative retrieval).
#   - No scene/combat/inventory/loot mutation (every read is via the engine's
#     pure-read helpers; no writers called from this path).
#   - No `!`-prefixed Avrae emission. Bot-Avrae write boundary preserved.
#   - No tactical directives (pacing, persistence, loot, redirect, footer).
#     Those exist for narrative pressure, not for player Q&A.
# Same router, different task ('advisory'), different system prompt.

ADVISORY_FALLBACK_MESSAGE = (
    "I'm having trouble pulling that up right now — try again in a moment, "
    "or ask in #dm-narration if it's urgent."
)
ADVISORY_MAX_CHARS = 1900  # Discord hard limit is 2000; leave headroom for trim notice


async def _advisory_respond(message: discord.Message):
    """Handle a single OOC advisory question in #dm-aside.

    Pure read path. See module-level invariants comment above. If anything
    in this function ever calls chroma_store, set_scene_mode, set_active_turn,
    update_combatants_from_init_list, add_item, enqueue_loot, or any other
    writer — that's a spec violation and a contamination risk.
    """
    guild_id = message.guild.id
    campaign = get_active_campaign(str(guild_id))
    if not campaign:
        # No active campaign yet. Friendly nudge, no LLM call.
        try:
            await message.channel.send(
                "No active campaign here yet. The DM can run "
                "`/newcampaign <name>` to start one.",
                reference=message, mention_author=False,
            )
        except Exception as e:
            log(f"advisory_respond: send failed (no campaign): {e!r}")
        return

    question = (message.content or '').strip()
    user_id = str(message.author.id)
    bound = get_character_by_controller(campaign['id'], user_id)
    bound_name = bound['name'] if bound else None

    # ── Read-only state pull (no writers anywhere in this block) ────
    try:
        scene_state = get_scene_state(campaign['id'])
    except Exception as e:
        log(f"advisory_respond: get_scene_state failed: {e!r}")
        scene_state = None
    try:
        active_turn = get_active_turn(campaign['id'])
    except Exception as e:
        log(f"advisory_respond: get_active_turn failed: {e!r}")
        active_turn = None
    try:
        combatants_snapshot = get_combatants(campaign['id'])
    except Exception as e:
        log(f"advisory_respond: get_combatants failed: {e!r}")
        combatants_snapshot = None
    try:
        inventory = get_inventory(campaign['id'], bound_name) if bound_name else []
    except Exception as e:
        log(f"advisory_respond: get_inventory failed: {e!r}")
        inventory = []
    try:
        pending_loot = get_pending_loot(campaign['id'])
    except Exception as e:
        log(f"advisory_respond: get_pending_loot failed: {e!r}")
        pending_loot = []

    # Track 6 #3.1 — Load COMMANDS.md fresh on every request so doc edits
    # take effect without a bot restart. Loader returns '' on missing file;
    # we log the missing state separately so the operator can spot it.
    commands_reference = orch._load_commands_reference()
    if commands_reference:
        commands_ref_loaded = 1
        commands_ref_chars = len(commands_reference)
    else:
        commands_ref_loaded = 0
        commands_ref_chars = 0
        if not orch.COMMANDS_DOC_PATH.is_file():
            log(f"advisory_commands_missing: path={orch.COMMANDS_DOC_PATH}")

    state_block = orch.build_advisory_context(
        campaign=campaign,
        bound_character_name=bound_name,
        scene_state=scene_state,
        active_turn=active_turn,
        combatants_snapshot=combatants_snapshot,
        inventory=inventory,
        pending_loot=pending_loot,
        commands_reference=commands_reference,
    )
    system_prompt = orch.ADVISORY_SYSTEM_PROMPT + "\n\n" + state_block

    messages = [{"role": "user", "content": question}]

    # ── Route to LLM (no chroma_search, no narration directives) ────
    try:
        try:
            async with message.channel.typing():
                text, provider = await asyncio.to_thread(
                    cloud_route, messages, "advisory", system_prompt, False,
                )
        except (discord.HTTPException, asyncio.TimeoutError) as e:
            log(f"typing_indicator_failed: command=advisory_respond err={e!r}")
            text, provider = await asyncio.to_thread(
                cloud_route, messages, "advisory", system_prompt, False,
            )
    except Exception as e:
        log(f"advisory_respond_failed: campaign={campaign['id']} "
            f"guild={guild_id} err={e!r}")
        try:
            await message.channel.send(
                ADVISORY_FALLBACK_MESSAGE,
                reference=message, mention_author=False,
            )
        except Exception as send_e:
            log(f"advisory_respond: fallback send failed: {send_e!r}")
        return

    body = (text or '').strip()
    if not body or body.startswith("All providers exhausted"):
        log(f"advisory_respond_failed: campaign={campaign['id']} "
            f"guild={guild_id} provider={provider} reason=empty_or_exhausted")
        try:
            await message.channel.send(
                ADVISORY_FALLBACK_MESSAGE,
                reference=message, mention_author=False,
            )
        except Exception as e:
            log(f"advisory_respond: fallback send failed: {e!r}")
        return

    # Truncate-with-pointer rather than split — single round-trip, single
    # message, lets the player ask a more specific follow-up if they need
    # more depth. v1 deliberately doesn't multi-message; spec says lean
    # toward the truncate path.
    truncated = False
    if len(body) > ADVISORY_MAX_CHARS:
        body = body[:ADVISORY_MAX_CHARS].rstrip() + (
            "\n\n*[…answer trimmed — ask a more specific question for detail.]*"
        )
        truncated = True

    try:
        await message.channel.send(
            body,
            reference=message, mention_author=False,
        )
    except Exception as e:
        log(f"advisory_respond: post failed: {e!r}")
        return

    log(
        f"advisory_respond: campaign={campaign['id']} guild={guild_id} "
        f"chars={len(body)} truncated={1 if truncated else 0} "
        f"provider={provider} "
        f"commands_ref_loaded={commands_ref_loaded} "
        f"commands_ref_chars={commands_ref_chars} "
        f"{orch.advisory_log_summary(bound_name, scene_state, inventory, combatants_snapshot)}"
    )


async def _dm_respond_and_post(campaign, characters, actions: list, combined_action: str,
                                transition_context: str = None,
                                location_label_override: str = None):
    """Called by the batcher. Pulls Avrae events for the relevant actors,
    fires the DM, posts narration.

    transition_context: optional structured directive (built by /travel and
    other transition-issuing commands). Forwarded to dm_respond as a top-
    priority instruction. Not persisted anywhere — one-shot.

    location_label_override: optional UI-only string for the footer. Used
    by /travel when the destination doesn't yet exist in dnd_locations
    (soft-existence policy) — DB stays NULL/unchanged, footer shows the
    intended destination. Subsequent turns fall back to DB lookup.
    """
    try:
        guild_id_str = campaign.get('guild_id', '')
        if not guild_id_str:
            log("_dm_respond_and_post: no guild_id on campaign")
            return

        guild = bot.get_guild(int(guild_id_str))
        if not guild:
            log(f"_dm_respond_and_post: guild {guild_id_str} not found")
            return

        channel = get_channel(guild, 'narration')
        if not channel:
            log("_dm_respond_and_post: narration channel not found")
            return

        # Pull Avrae events for the actors who just spoke (consume so they
        # don't re-narrate next turn). Keep events for non-acting characters
        # in the buffer in case they come up later.
        # Dedupe while preserving order (multiple actions from same actor
        # produced "Donovan Ruby, Donovan Ruby" in the footer).
        # Phase 6: canonicalize actor names before buffer.consume so the
        # exact-equality matcher hits across system-source name divergence.
        # actor_names_display preserves the original case for prompt rendering;
        # actor_names_canonical is what feeds buffer.consume.
        seen_canonical = set()
        actor_names_display = []
        actor_names_canonical = []
        for tup in actions:
            name = tup[0]
            resolved = orch.resolve_actor(campaign['id'], name)
            canonical = (resolved['canonical_name'] if resolved
                         else canonicalize_actor_name(name))
            if canonical and canonical not in seen_canonical:
                seen_canonical.add(canonical)
                actor_names_display.append(name)
                actor_names_canonical.append(canonical)
        # actor_names is the back-compat name for the prompt-facing list
        actor_names = actor_names_display
        # First-batched actor's Discord user ID for the persistence directive's
        # typing-identity comparison (§5.5). Multi-actor batches use the first
        # actor's identity; multi-PC turn-order tension is filed per multiplayer
        # table.
        first_user_id = None
        for tup in actions:
            if len(tup) >= 3 and tup[2]:
                first_user_id = str(tup[2])
                break
        avrae_events = buffer.consume(int(guild_id_str), actor_names_canonical)
        roll_kinds = [e.get('kind') for e in avrae_events if e.get('kind')]
        log(f"buffer.consume: {len(avrae_events)} events for "
            f"actors={actor_names_canonical} roll_kinds={roll_kinds}")

        try:
            async with channel.typing():
                response = await asyncio.to_thread(
                    dm_respond, campaign, characters, combined_action, avrae_events,
                    actor_names, transition_context, first_user_id, actions
                )
        except (discord.HTTPException, asyncio.TimeoutError) as e:
            log(f"typing_indicator_failed: command=_dm_respond_and_post err={e!r}")
            response = await asyncio.to_thread(
                dm_respond, campaign, characters, combined_action, avrae_events,
                actor_names, transition_context, first_user_id, actions
            )

        chroma_store(campaign['id'], 'dm', response)
        update_scene(campaign['id'], f"Last actions: {combined_action[:200]} | DM: {response[:200]}")

        response_md = (response
                       .replace('<b>', '**').replace('</b>', '**')
                       .replace('<i>', '*').replace('</i>', '*'))

        # Pick embed colour from response keywords + Avrae signal
        had_crit = any(e.get('nat') == 20 or e.get('crit') for e in avrae_events)
        had_fail = any(e.get('nat') == 1 for e in avrae_events)
        lower_resp = response.lower()
        if had_crit:
            color = discord.Color.gold()
        elif had_fail:
            color = discord.Color.dark_red()
        elif any(w in lower_resp for w in ['attack', 'damage', 'wound', 'blood', 'strike']):
            color = discord.Color.red()
        elif any(w in lower_resp for w in ['fail', 'miss', 'fumble', 'stumble']):
            color = discord.Color.orange()
        elif any(w in lower_resp for w in ['treasure', 'gold', 'loot', 'reward', 'chest']):
            color = discord.Color.gold()
        else:
            color = discord.Color.dark_red()

        embed = discord.Embed(description=response_md[:4000], color=color)
        actor_label = ', '.join(actor_names)
        footer_bits = [f"⚔ {actor_label}"]
        if avrae_events:
            footer_bits.append(f"({len(avrae_events)} roll{'s' if len(avrae_events) != 1 else ''} in play)")
        # Surface current location. Footer override wins on the transition
        # turn (when /travel destination didn't resolve to a row); otherwise
        # DB lookup. Soft failure on either path — never blocks posting.
        if location_label_override:
            footer_bits.append(f"📍 {location_label_override}")
        else:
            try:
                current_loc = get_current_location(campaign['id'])
                if current_loc:
                    footer_bits.append(f"📍 {current_loc['canonical_name']}")
            except Exception as e:
                log(f"current_location footer lookup failed: {e}")
        # Active-quest reminder. Compact comma list, capped to fit the
        # Discord footer limit. Soft failure — quest state is advisory UX.
        try:
            active_quests = get_active_quests(campaign['id'])
            if active_quests:
                # Quest schema has 'title' (not 'name') — confirmed from
                # session 1 SQL. Defensively try both.
                titles = []
                for q in active_quests:
                    t = q.get('title') or q.get('name') or ''
                    if t:
                        titles.append(t.strip())
                if titles:
                    quest_line = "🗒️ " + ", ".join(titles)
                    # Hard-cap to keep footer under Discord's 2048 limit.
                    if len(quest_line) > 200:
                        quest_line = quest_line[:197] + "..."
                    footer_bits.append(quest_line)
        except Exception as e:
            log(f"quest reminder footer lookup failed: {e}")

        # Active-state header (Track 6 #1). Prepend mode/turn/up-next
        # lines above the existing actor/location/quest line. Pure
        # function in orchestration; soft-fail so footer issues never
        # block narration posting.
        identity_line = " ".join(footer_bits)
        state_header = ''
        state_signals = {}
        try:
            scene_state = get_scene_state(campaign['id'])
            active_turn = get_active_turn(campaign['id'])
            combatants_payload = get_combatants(campaign['id'])
            bound_pcs = get_bound_character_names(campaign['id']) or []
            state_header, state_signals = orch.render_state_footer(
                scene_state, active_turn, combatants_payload, bound_pcs
            )
        except Exception as e:
            log(f"state footer render failed: {e}")
            state_header = ''
            state_signals = {}

        footer_text = state_header + identity_line if state_header else identity_line
        # Discord embed footer hard limit is 2048 chars.
        if len(footer_text) > 2048:
            footer_text = footer_text[:2045] + "..."
        embed.set_footer(text=footer_text)
        log(f"state_footer: campaign={campaign['id']} "
            f"{orch.state_footer_log_summary(state_signals)}")

        msg = await channel.send(embed=embed)
        log(f"_dm_respond_and_post: posted for guild {guild_id_str}, {len(avrae_events)} avrae events")
        asyncio.create_task(_attach_hints(msg, embed, response))
        asyncio.create_task(_extract_and_persist_world(campaign["id"], response, guild))
    except Exception as e:
        log(f"_dm_respond_and_post error: {e}")
        import traceback; log(traceback.format_exc())


# ─────────────────────────────────────────────────────────
# Slash commands — narrative only
# ─────────────────────────────────────────────────────────

@bot.tree.command(name='setup', description='[SETUP] Create or repair Virgil DM channels. Safe to re-run.')
async def setup(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.manage_channels:
        await interaction.response.send_message("DM only — needs Manage Channels.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)

    guild = interaction.guild
    me = guild.me

    # The bot perms we need everywhere we operate. Any value left at None
    # means "leave whatever was already set alone" — we never demote.
    REQUIRED_PERMS = {
        'view_channel': True,
        'read_message_history': True,
        'send_messages': True,
        'embed_links': True,
        'attach_files': True,
        'add_reactions': True,
        'manage_messages': True,
        'use_external_emojis': True,
    }

    def merge_bot_overwrite(existing: discord.PermissionOverwrite | None) -> discord.PermissionOverwrite:
        """Return a new PermissionOverwrite that preserves every existing
        explicit allow/deny and only sets the bot's required perms."""
        if existing is None:
            existing = discord.PermissionOverwrite()
        # PermissionOverwrite stores values as True/False/None per perm.
        # We want to keep existing explicit values (esp. True grants the
        # human added) and just ensure REQUIRED_PERMS are at least True.
        merged = discord.PermissionOverwrite()
        for perm_name, _ in iter(existing):
            current_value = getattr(existing, perm_name)
            setattr(merged, perm_name, current_value)
        for perm_name, want in REQUIRED_PERMS.items():
            current = getattr(merged, perm_name)
            # Only overwrite if currently unset (None) or explicitly denied (False).
            # We don't downgrade explicit True (a manual grant elsewhere).
            if current is None or current is False:
                setattr(merged, perm_name, want)
        return merged

    # Per-channel topic strings. Anything not listed defaults to ''.
    # Updated for S23 #3 canonical structure: rolls/sheets/loot/commands
    # consolidated into dm-narration; aside reserved for Track 6 #3 advisory
    # mode; ooc renamed party-chat.
    CHANNEL_TOPICS = {
        'narration': ("DM narration, Avrae rolls, init, attacks, loot. "
                      "Type your actions here — Avrae's `!check` / `!attack` / "
                      "`!cast` output lands here too."),
        'aside':     ("Out-of-character questions for the DM/Virgil. Reserved "
                      "for advisory mode (coming soon)."),
        'lore':      ("World lore, NPCs, locations, session notes. "
                      "DM writes; players read."),
        'welcome':   WELCOME_CHANNEL_TOPIC,
        'commands':  ("Bot commands and quick references. /inventory, "
                      "/refresh, /dmhelp, etc."),
        'ooc':       "Player banter — out of character, no DM/bot involvement.",
    }

    # Avrae lookup (S23 #4 — Avrae perms in all canonical channels). Soft-
    # fail if not in guild; logs once at /setup top so missing-Avrae state
    # is observable without spamming per-channel failures later.
    avrae_member = None
    try:
        avrae_id = al.get_avrae_user_id()
        avrae_member = guild.get_member(avrae_id)
        if avrae_member is None:
            log(f"setup: Avrae user_id={avrae_id} not in guild — "
                f"skipping Avrae permission grants")
    except Exception as e:
        log(f"setup: Avrae lookup failed: {e}")

    async def repair_bot_perms(target):
        """Ensure the bot has REQUIRED_PERMS on a target channel/category.
        Used for legacy code paths where we only want to top up bot perms
        without touching @everyone or Avrae. Most canonical surfaces now
        go through ensure_canonical_overwrites instead."""
        try:
            existing = target.overwrites_for(me)
            merged = merge_bot_overwrite(existing)
            await target.set_permissions(me, overwrite=merged)
            return True
        except Exception as e:
            log(f"setup: could not set perms on "
                f"{getattr(target, 'name', '?')}: {e}")
            return False

    def canonical_overwrites_dict(role_set: str, chan_key: str | None = None) -> dict:
        """Return overwrites dict for a canonical channel/category.

        role_set:
          'open'      — text channel everyone can read+write
                        (#dm-narration, #dm-aside, #party-chat, #ooc-commands)
          'read_only' — text channel everyone reads, only bot/DM/Avrae writes
                        (#welcome, #lore-notes)
          'category'  — category-level baseline (view+read_history, no send;
                        send is decided per-channel)
          'voice'     — voice channel; everyone connect+speak

        chan_key — canonical channel key (e.g. 'lore', 'narration'). Used
        to apply per-channel Avrae policy: keys in AVRAE_READ_ONLY get
        Avrae read access but no send (DM-only write surfaces).

        Sets @everyone, Virgil DM, and (if present) Avrae explicitly.
        Other roles (Dungeon Master, custom player roles) are NOT touched
        by this dict — set_permissions is per-target, so other overwrites
        survive.
        """
        if role_set == 'open':
            everyone_ow = discord.PermissionOverwrite(
                view_channel=True,
                read_message_history=True,
                send_messages=True,
            )
        elif role_set == 'read_only':
            everyone_ow = discord.PermissionOverwrite(
                view_channel=True,
                read_message_history=True,
                send_messages=False,
            )
        elif role_set == 'voice':
            everyone_ow = discord.PermissionOverwrite(
                view_channel=True,
                connect=True,
                speak=True,
            )
        else:  # 'category'
            everyone_ow = discord.PermissionOverwrite(
                view_channel=True,
                read_message_history=True,
            )

        out = {
            guild.default_role: everyone_ow,
            me: discord.PermissionOverwrite(**REQUIRED_PERMS),
        }
        if avrae_member is not None and role_set != 'voice':
            if chan_key in AVRAE_READ_ONLY:
                # Avrae sees the channel but cannot post (e.g. #lore-notes).
                out[avrae_member] = discord.PermissionOverwrite(
                    view_channel=True,
                    read_message_history=True,
                    send_messages=False,
                )
            else:
                # Avrae is text-only — full REQUIRED_PERMS on text and category
                # surfaces. Skip voice channels.
                out[avrae_member] = discord.PermissionOverwrite(**REQUIRED_PERMS)
        elif avrae_member is not None and role_set == 'voice':
            # Token view perm on voice so Avrae appears in the list,
            # but no connect/speak (Avrae doesn't use voice).
            out[avrae_member] = discord.PermissionOverwrite(view_channel=True)
        return out

    avrae_perms_applied = 0  # incremented by ensure_canonical_overwrites

    async def ensure_canonical_overwrites(target, role_set: str,
                                          chan_key: str | None = None) -> int:
        """Apply canonical_overwrites_dict to an existing channel/category
        via set_permissions per role/member (preserves other roles'
        overrides). Returns count of overwrites successfully applied."""
        nonlocal avrae_perms_applied
        applied = 0
        avrae_action = 'skipped'  # default: Avrae not in guild or voice channel
        desired = canonical_overwrites_dict(role_set, chan_key=chan_key)
        for role_or_member, ow in desired.items():
            try:
                if avrae_member is not None and role_or_member == avrae_member:
                    existing = target.overwrites_for(avrae_member)
                    avrae_action = 'applied' if existing == discord.PermissionOverwrite() else 'repaired'
                    if existing == ow:
                        avrae_action = 'skipped'
                await target.set_permissions(role_or_member, overwrite=ow)
                applied += 1
            except Exception as e:
                log(f"setup: could not set {role_or_member} perms on "
                    f"{getattr(target, 'name', '?')}: {e}")
        if avrae_member is not None and role_set != 'voice' and chan_key is not None:
            log(f"avrae_perms: guild={guild.id} channel={getattr(target, 'name', '?')} "
                f"action={avrae_action}")
            if avrae_action != 'skipped':
                avrae_perms_applied += 1
        return applied

    # ── Build the snapshot the planner needs ────────────────────────
    existing_categories = {c.name for c in guild.categories}
    existing_text = {
        c.name: (c.category.name if c.category else None)
        for c in guild.text_channels
    }
    existing_voice = {
        c.name: (c.category.name if c.category else None)
        for c in guild.voice_channels
    }

    # Pre-fetch commands pin body so compute_setup_plan can decide the action.
    # Only needed when the channel already exists; fresh creates always get 'create'.
    commands_pin_prefetch: str | None = None
    commands_chan_name_key = CHANNEL_NAMES.get('commands', '')
    if commands_chan_name_key and commands_chan_name_key in existing_text:
        try:
            pre_ch = discord.utils.get(guild.text_channels, name=commands_chan_name_key)
            if pre_ch:
                pre_pins = await pre_ch.pins()
                for p in pre_pins:
                    if p.author and p.author.id == me.id and (p.content or '').strip():
                        commands_pin_prefetch = (p.content or '').strip()
                        break
        except Exception as e:
            log(f"setup: failed to pre-fetch commands pin: {e}")

    plan = compute_setup_plan(
        text_channels=existing_text,
        voice_channels=existing_voice,
        categories=existing_categories,
        commands_existing_pin_body=commands_pin_prefetch,
    )

    # ── Execute the plan ────────────────────────────────────────────
    # Categories first so subsequent channel ops can reference them.
    cat_objects = {c.name: c for c in guild.categories}
    for cat_name in plan['categories_to_create']:
        try:
            cat = await guild.create_category(
                cat_name,
                overwrites=canonical_overwrites_dict('category'),
            )
            cat_objects[cat_name] = cat
            log(f"setup: created category {cat_name!r}")
        except Exception as e:
            log(f"setup: failed to create category {cat_name!r}: {e}")

    # NOTE: existing canonical categories get their @everyone/bot/Avrae
    # overwrites converged by the comprehensive ensure_canonical_overwrites
    # pass after legacy cleanup, not here. Removed the bot-only repair call
    # so we don't double-write perms within one /setup invocation.

    # Reverse-lookup: which channel-key produced which canonical name.
    name_to_key = {v: k for k, v in CHANNEL_NAMES.items()}

    # Create text channels
    created_text = []
    for chan_name, target_cat_name in plan['text_channels_to_create']:
        try:
            cat_obj = cat_objects.get(target_cat_name)
            chan_key = name_to_key.get(chan_name)
            topic = CHANNEL_TOPICS.get(chan_key, '')
            role_set = 'read_only' if chan_key in READ_ONLY_FOR_PLAYERS else 'open'
            overwrites = canonical_overwrites_dict(role_set, chan_key=chan_key)
            ch = await guild.create_text_channel(
                chan_name,
                category=cat_obj,
                topic=topic,
                overwrites=overwrites,
            )
            created_text.append(ch.mention)
            log(f"setup: created text channel #{chan_name} in "
                f"{target_cat_name!r}")
        except Exception as e:
            log(f"setup: failed to create #{chan_name}: {e}")

    # Move text channels into canonical categories
    moved_text = []
    for chan_name, target_cat_name in plan['text_channels_to_move']:
        existing = discord.utils.get(guild.text_channels, name=chan_name)
        if not existing:
            continue
        try:
            target_cat = cat_objects.get(target_cat_name)
            await existing.edit(category=target_cat)
            moved_text.append(existing.mention)
            log(f"setup: moved #{chan_name} → category {target_cat_name!r}")
        except Exception as e:
            log(f"setup: failed to move #{chan_name}: {e}")

    # NOTE: bot-only perm repair is now handled by the comprehensive
    # ensure_canonical_overwrites pass below (after legacy cleanup),
    # which sets @everyone + bot + Avrae explicitly per canonical
    # surface. Per-stage repairs would only top up bot perms, leaving
    # the @everyone/Avrae gap that S23 #4 is closing.

    # Create voice channels
    created_voice = []
    for chan_name, target_cat_name in plan['voice_channels_to_create']:
        try:
            cat_obj = cat_objects.get(target_cat_name)
            ch = await guild.create_voice_channel(
                chan_name,
                category=cat_obj,
                overwrites=canonical_overwrites_dict('voice'),
            )
            created_voice.append(f"🔊 {ch.name}")
            log(f"setup: created voice channel {chan_name} in "
                f"{target_cat_name!r}")
        except Exception as e:
            log(f"setup: failed to create voice {chan_name}: {e}")

    # Move voice channels
    moved_voice = []
    for chan_name, target_cat_name in plan['voice_channels_to_move']:
        existing = discord.utils.get(guild.voice_channels, name=chan_name)
        if not existing:
            continue
        try:
            target_cat = cat_objects.get(target_cat_name)
            await existing.edit(category=target_cat)
            moved_voice.append(f"🔊 {existing.name}")
            log(f"setup: moved voice {chan_name} → category "
                f"{target_cat_name!r}")
        except Exception as e:
            log(f"setup: failed to move voice {chan_name}: {e}")

    # Legacy category cleanup — only delete if the planner confirmed empty
    # post-move. The planner already accounts for canonical channels moved
    # OUT of legacy; if non-canonical channels remain in legacy (e.g.
    # #dice-rolls Jordan hasn't deleted yet), legacy_category_to_delete
    # is None and legacy stays.
    legacy_deleted = False
    if plan.get('legacy_category_to_delete'):
        legacy_cat = cat_objects.get(plan['legacy_category_to_delete'])
        if legacy_cat:
            try:
                # Re-check at execution time — moves above are async; some
                # may have failed silently. Refuse delete if anything
                # still hangs off the category.
                if not legacy_cat.channels:
                    await legacy_cat.delete(reason="Virgil setup: empty legacy category")
                    legacy_deleted = True
                    log(f"setup: deleted empty legacy category "
                        f"{legacy_cat.name!r}")
                else:
                    log(f"setup: legacy {legacy_cat.name!r} still has "
                        f"{len(legacy_cat.channels)} channels — skipping delete")
            except Exception as e:
                log(f"setup: failed to delete legacy "
                    f"{legacy_cat.name!r}: {e}")

    # ── Comprehensive permission convergence (S23 #4 — perm fix) ────
    # After all create/move/delete operations, every canonical category
    # and channel is reset to its known-good @everyone/bot/Avrae shape.
    # This runs BEFORE the welcome-pin block so the bot is guaranteed
    # send rights when it tries to post + pin in #welcome.
    #
    # Other roles (Dungeon Master, custom player roles) are NOT touched
    # — set_permissions is per-target, so any explicit grants survive.
    canonical_perm_writes = 0
    name_to_key_local = {v: k for k, v in CHANNEL_NAMES.items()}

    # Categories
    for cat_name in CATEGORY_NAMES.values():
        cat = cat_objects.get(cat_name) or discord.utils.get(
            guild.categories, name=cat_name
        )
        if cat:
            cat_objects[cat_name] = cat
            canonical_perm_writes += await ensure_canonical_overwrites(
                cat, 'category'
            )

    # Text channels
    for chan_name in CHANNEL_NAMES.values():
        ch = discord.utils.get(guild.text_channels, name=chan_name)
        if not ch:
            continue
        chan_key = name_to_key_local.get(chan_name)
        role_set = (
            'read_only' if chan_key in READ_ONLY_FOR_PLAYERS else 'open'
        )
        canonical_perm_writes += await ensure_canonical_overwrites(
            ch, role_set, chan_key=chan_key
        )

    # Voice channels
    for vc_name, _ in VOICE_CHANNELS:
        vc = discord.utils.get(guild.voice_channels, name=vc_name)
        if vc:
            canonical_perm_writes += await ensure_canonical_overwrites(
                vc, 'voice'
            )

    log(f"setup: applied canonical overwrites on {canonical_perm_writes} "
        f"role/channel pairs")

    # ── #welcome pinned message + positioning (S23 #4) ──────────────
    # The site (virgildm.com) holds the full onboarding flow. The bot's
    # job here is ENTRY POINT: a single pinned message in #welcome that
    # points players at the site, plus position-the-channel-first inside
    # OUT OF CHARACTER so it's the first thing new players see.
    #
    # Idempotency: pin is replaced ONLY when its content has drifted from
    # WELCOME_PIN_BODY. Re-running /setup on a server with a correct pin
    # is a no-op for the pin — welcome_pinned=0 in telemetry.
    welcome_channel_created = 0
    welcome_pinned = 0
    welcome_name = CHANNEL_NAMES['welcome']
    welcome_ch = discord.utils.get(guild.text_channels, name=welcome_name)

    if welcome_ch:
        # Was the channel created THIS run? Used in telemetry only.
        welcome_channel_created = 1 if any(
            n == welcome_name for n, _ in plan['text_channels_to_create']
        ) else 0

        # Position fix: ensure #welcome is first text channel within OOC.
        # Soft-fail — positioning is cosmetic. Critical-path is the pin.
        try:
            ooc_cat_name = CATEGORY_NAMES['ooc']
            if welcome_ch.category and welcome_ch.category.name == ooc_cat_name:
                first_text = next(iter(welcome_ch.category.text_channels), None)
                if first_text and first_text.id != welcome_ch.id:
                    await welcome_ch.edit(position=0)
                    log(f"setup: moved #{welcome_name} to top of "
                        f"{ooc_cat_name!r}")
        except Exception as e:
            log(f"setup: failed to position #{welcome_name}: {e}")

        # Pinned message: post-and-pin if missing, replace if drifted, no-op
        # if matches.
        try:
            pins = await welcome_ch.pins()
            existing_pin = None
            for p in pins:
                if p.author and p.author.id == me.id and (p.content or '').strip():
                    existing_pin = p
                    break

            target = WELCOME_PIN_BODY.strip()
            if existing_pin is None:
                msg = await welcome_ch.send(WELCOME_PIN_BODY)
                await msg.pin(reason="Virgil setup: welcome pin")
                welcome_pinned = 1
                log(f"setup: posted + pinned welcome message in "
                    f"#{welcome_name}")
            elif (existing_pin.content or '').strip() != target:
                # Drifted — unpin old and post fresh.
                try:
                    await existing_pin.unpin(
                        reason="Virgil setup: replacing drifted pin"
                    )
                except Exception:
                    pass
                try:
                    await existing_pin.delete()
                except Exception:
                    # Soft-fail on delete; the unpinned old message is
                    # harmless and the new pin still lands.
                    pass
                new_msg = await welcome_ch.send(WELCOME_PIN_BODY)
                await new_msg.pin(
                    reason="Virgil setup: replacement welcome pin"
                )
                welcome_pinned = 1
                log(f"setup: replaced drifted welcome pin in "
                    f"#{welcome_name}")
            # else: pin matches current text → no-op
        except Exception as e:
            log(f"setup: failed to manage welcome pin: {e}")

    # ── #ooc-commands positioning ───────────────────────────────────
    # Ensure #ooc-commands sits between #welcome and #party-chat inside
    # 💬 OUT OF CHARACTER. Fresh /setup runs hit this naturally via
    # CHANNEL_NAMES insertion order; partial-state servers (welcome and
    # party-chat already exist when commands gets created) need an
    # explicit nudge — Discord drops new channels at the bottom of a
    # category by default.
    commands_name = CHANNEL_NAMES['commands']
    commands_ch = discord.utils.get(guild.text_channels, name=commands_name)
    commands_channel_created = 1 if any(
        n == commands_name for n, _ in plan['text_channels_to_create']
    ) else 0

    if commands_ch and welcome_ch:
        try:
            ooc_cat_name = CATEGORY_NAMES['ooc']
            if (commands_ch.category and commands_ch.category.name == ooc_cat_name
                    and welcome_ch.category and welcome_ch.category.name == ooc_cat_name):
                target_pos = welcome_ch.position + 1
                if commands_ch.position != target_pos:
                    await commands_ch.edit(position=target_pos)
                    log(f"setup: positioned #{commands_name} after "
                        f"#{welcome_name}")
        except Exception as e:
            log(f"setup: failed to position #{commands_name}: {e}")

    # ── #commands pinned orientation message (S31) ──────────────────
    # Post/replace COMMANDS_PIN_BODY in #commands based on the plan action.
    # Soft-fail throughout — pin errors never abort the rest of /setup.
    commands_pin_action = plan.get('commands_pin_action', 'skipped')
    commands_pinned = 0
    commands_ch_for_pin = discord.utils.get(
        guild.text_channels, name=CHANNEL_NAMES.get('commands', '')
    )
    if commands_pin_action in ('create', 'replace') and commands_ch_for_pin:
        try:
            if commands_pin_action == 'replace':
                rep_pins = await commands_ch_for_pin.pins()
                for p in rep_pins:
                    if p.author and p.author.id == me.id and (p.content or '').strip():
                        try:
                            await p.unpin(
                                reason="Virgil setup: replacing drifted commands pin"
                            )
                        except Exception:
                            pass
                        try:
                            await p.delete()
                        except Exception:
                            pass
                        break
            new_msg = await commands_ch_for_pin.send(COMMANDS_PIN_BODY)
            await new_msg.pin(reason="Virgil setup: commands orientation pin")
            commands_pinned = 1
            verb = 'posted + pinned' if commands_pin_action == 'create' else 'replaced'
            log(f"setup: {verb} commands pin in "
                f"#{CHANNEL_NAMES.get('commands')}")
        except Exception as e:
            log(f"setup: failed to manage commands pin: {e}")
    elif commands_pin_action == 'noop':
        log(f"setup: commands pin current — no-op")
    elif commands_pin_action == 'skipped':
        log(f"setup: commands pin skipped — #commands not found")

    # ── AFK voice channel + guild AFK auto-move config ──────────────
    # Idempotent: only call guild.edit when afk_channel/afk_timeout drift
    # from desired. afk_timeout accepts a fixed set of values
    # (60, 300, 900, 1800, 3600 seconds).
    afk_name = AFK_VOICE_CHANNEL_NAME
    afk_ch = discord.utils.get(guild.voice_channels, name=afk_name)
    afk_channel_created = 1 if any(
        n == afk_name for n, _ in plan['voice_channels_to_create']
    ) else 0
    afk_timeout_set = 0
    if afk_ch:
        try:
            current_afk = guild.afk_channel
            current_timeout = guild.afk_timeout
            needs_channel_change = (current_afk is None
                                    or current_afk.id != afk_ch.id)
            needs_timeout_change = current_timeout != AFK_TIMEOUT_SECONDS
            if needs_channel_change or needs_timeout_change:
                await guild.edit(
                    afk_channel=afk_ch,
                    afk_timeout=AFK_TIMEOUT_SECONDS,
                    reason="Virgil setup: configure AFK auto-move",
                )
                afk_timeout_set = 1
                log(f"setup: configured AFK channel={afk_ch.name!r} "
                    f"timeout={AFK_TIMEOUT_SECONDS}s")
        except Exception as e:
            log(f"setup: failed to configure AFK: {e}")

    # ── Telemetry ───────────────────────────────────────────────────
    log(f"setup_run: guild={guild.id} "
        f"{setup_plan_log_summary(plan)} "
        f"welcome_channel_created={welcome_channel_created} "
        f"welcome_pinned={welcome_pinned} "
        f"commands_pin={commands_pin_action} "
        f"avrae_in_guild={1 if avrae_member else 0} "
        f"avrae_perms_applied={avrae_perms_applied} "
        f"commands_channel_created={commands_channel_created} "
        f"afk_channel_created={afk_channel_created} "
        f"afk_timeout_set={afk_timeout_set} "
        f"perm_writes={canonical_perm_writes}")

    # ── Build the user-facing summary ───────────────────────────────
    lines = [f"{E['ok']} Virgil DM channels ready."]
    if plan['categories_to_create']:
        lines.append(f"Categories created: {', '.join(plan['categories_to_create'])}")
    if created_text:
        lines.append(f"Channels created: {', '.join(created_text)}")
    if created_voice:
        lines.append(f"Voice channels created: {', '.join(created_voice)}")
    if moved_text:
        lines.append(f"Channels moved to canonical category: {', '.join(moved_text)}")
    if moved_voice:
        lines.append(f"Voice channels moved: {', '.join(moved_voice)}")
    if legacy_deleted:
        lines.append(
            f"Removed empty legacy category `{LEGACY_CATEGORY_NAME}`."
        )
    elif plan.get('legacy_category_to_delete') is None and \
            LEGACY_CATEGORY_NAME in existing_categories:
        lines.append(
            f"Note: legacy `{LEGACY_CATEGORY_NAME}` category still has "
            f"non-canonical channels — leave or remove manually."
        )
    if welcome_pinned:
        lines.append(
            f"Posted/updated welcome pin in #{welcome_name}."
        )
    if commands_pinned:
        lines.append(
            f"Posted/updated orientation pin in #{CHANNEL_NAMES.get('commands')}."
        )
    if not (plan['categories_to_create'] or created_text or created_voice
            or moved_text or moved_voice or legacy_deleted
            or welcome_pinned or commands_pinned):
        lines.append("Nothing to do — already canonical. Permissions reconciled.")
    else:
        lines.append("Permissions reconciled (@everyone, bot, Avrae) on every canonical channel.")
    if avrae_member is None:
        lines.append(
            "⚠ Avrae not detected in this server — invite from "
            "<https://avrae.io> so its rolls render in `#dm-narration`."
        )

    # Player vs DM next-steps split (S23 #4) — players land at #welcome,
    # which points them at the site. DM-side steps stay inline.
    lines.append("")
    lines.append("**For your players:**")
    lines.append(
        f"Point them at #{welcome_name} — the pinned message has the full "
        f"onboarding flow at https://virgildm.com."
    )
    lines.append("")
    lines.append("**For you (DM):**")
    lines.append("1. Invite Avrae from <https://avrae.io> if not already in the server")
    lines.append("2. Run `/newcampaign <name>` to create your first campaign")
    lines.append("3. Run `/play <opening scene>` to begin")
    lines.append("")
    lines.append("Type `/dmhelp` anytime for the full command list.")
    await interaction.followup.send("\n".join(lines), ephemeral=True)


@bot.tree.command(name='newcampaign', description='[DM] Start a new campaign for this server.')
@app_commands.describe(
    name='Campaign name',
    tone='Optional setting/tone (e.g. "grim dark fantasy", "Eberron noir"). Default: classic high fantasy.',
)
async def newcampaign(interaction: discord.Interaction, name: str, tone: str = ''):
    if not is_dm_or_creator(interaction):
        await interaction.response.send_message("DM or campaign owner only.", ephemeral=True)
        return
    guild_id = str(interaction.guild_id)
    campaign_id = create_campaign(guild_id, name, tone, creator_user_id=str(interaction.user.id))
    tone_note = f" Tone: *{tone}*." if tone else " (Default tone: classic high fantasy.)"
    await interaction.response.send_message(
        f"{E['ok']} Campaign **{name}** is active.{tone_note} "
        f"Players: use `/bindchar` to join."
    )


@bot.tree.command(name='campaigns', description='[DM] List active and inactive campaigns. Use /archived to see archived ones.')
async def campaigns(interaction: discord.Interaction):
    if not is_dm_or_creator(interaction):
        await interaction.response.send_message("DM or campaign owner only.", ephemeral=True)
        return
    guild_id = str(interaction.guild_id)
    rows = [r for r in list_campaigns(guild_id) if r['status'] != 'archived']
    if not rows:
        await interaction.response.send_message(
            "No active or inactive campaigns. Try `/archived` to see archived ones.",
            ephemeral=True
        )
        return
    lines = []
    for r in rows:
        marker = "▶" if r['status'] == 'active' else "  "
        lines.append(f"{marker} #{r['id']} **{r['name']}** ({r['status']})")
    await interaction.response.send_message("\n".join(lines), ephemeral=True)


@bot.tree.command(name='archived', description='[DM] List archived (soft-deleted) campaigns for this server.')
async def archived(interaction: discord.Interaction):
    if not is_dm_or_creator(interaction):
        await interaction.response.send_message("DM or campaign owner only.", ephemeral=True)
        return
    guild_id = str(interaction.guild_id)
    rows = [r for r in list_campaigns(guild_id) if r['status'] == 'archived']
    if not rows:
        await interaction.response.send_message("No archived campaigns.", ephemeral=True)
        return
    lines = [f"  #{r['id']} **{r['name']}** (archived)" for r in rows]
    lines.append(f"\n_Restore with `/setcampaign <id>`. Permanently delete with `/purgecampaign`._")
    await interaction.response.send_message("\n".join(lines), ephemeral=True)


@bot.tree.command(name='setcampaign', description='[DM] Switch the active campaign for this server.')
@app_commands.describe(campaign_id='Campaign id (see /campaigns).')
async def setcampaign(interaction: discord.Interaction, campaign_id: int):
    """Switch the active campaign. Demotes any current active in this
    guild to inactive in the same transaction. Un-archives if the
    target was archived (per design — switching is the act of
    un-archiving)."""
    if not is_dm_or_creator(interaction):
        await interaction.response.send_message("DM or campaign owner only.", ephemeral=True)
        return
    guild_id = str(interaction.guild_id)

    # Verify the campaign exists in THIS guild before flipping. The engine
    # primitive operates by id alone — we add the guild check here so the
    # slash command can't reach across servers.
    target = next((r for r in list_campaigns(guild_id) if r['id'] == campaign_id), None)
    if target is None:
        await interaction.response.send_message(
            f"{E['facepalm']} No campaign #{campaign_id} in this server.",
            ephemeral=True
        )
        return

    if target['status'] == 'active':
        await interaction.response.send_message(
            f"{E['ok']} **{target['name']}** is already active.",
            ephemeral=True
        )
        return

    # Capture previous-active name for the confirm message before the flip.
    prev_active = next((r for r in list_campaigns(guild_id) if r['status'] == 'active'), None)

    result = campaign_set_status(campaign_id, 'active')
    if not result['updated']:
        await interaction.response.send_message(
            f"{E['facepalm']} Could not switch: {result['reason']}.",
            ephemeral=True
        )
        return

    msg = f"{E['ok']} Active campaign: **{target['name']}** (#{campaign_id})."
    if prev_active is not None:
        msg += f" Previously active: **{prev_active['name']}** (#{prev_active['id']}) → inactive."
    if target['status'] == 'archived':
        msg += " (Un-archived.)"
    await interaction.response.send_message(msg, ephemeral=True)


@bot.tree.command(name='deletecampaign',
                  description='[DM] Soft-delete (archive) one or more campaigns. Comma-separated. Reversible via /setcampaign.')
@app_commands.describe(campaign_ids='Single id (e.g. 4) or comma-separated list (e.g. 5,6,7,8).')
async def deletecampaign(interaction: discord.Interaction, campaign_ids: str):
    """Soft-delete: flips status to 'archived'. Hidden from /campaigns
    by default. Reversible — /setcampaign on an archived row un-archives.

    Atomic batch: validates every id in the list against three rules
    before archiving anything. If ANY id fails (not in this server,
    currently active, already archived, or not an integer), the entire
    batch is rejected and nothing is changed. Caller must clean up the
    list and retry.
    """
    if not is_dm_or_creator(interaction):
        await interaction.response.send_message("DM or campaign owner only.", ephemeral=True)
        return
    guild_id = str(interaction.guild_id)

    # Parse the input — accept "4", "4,5,6", or "4, 5, 6". Strip spaces
    # around commas so trailing-space autocomplete artifacts don't kill
    # the parse.
    raw_parts = [p.strip() for p in campaign_ids.split(',') if p.strip()]
    if not raw_parts:
        await interaction.response.send_message(
            f"{E['facepalm']} No ids provided. Usage: `/deletecampaign 5` or `/deletecampaign 5,6,7`.",
            ephemeral=True
        )
        return

    parsed_ids = []
    bad_tokens = []
    for tok in raw_parts:
        try:
            parsed_ids.append(int(tok))
        except ValueError:
            bad_tokens.append(tok)
    if bad_tokens:
        await interaction.response.send_message(
            f"{E['facepalm']} Could not parse as ids: {', '.join(repr(t) for t in bad_tokens)}. "
            f"Use integers only, comma-separated.",
            ephemeral=True
        )
        return

    # Validate every id BEFORE writing anything. Atomic batch — if any
    # id is invalid for archiving, the whole batch fails and nothing
    # changes. The caller has to fix the list and retry.
    rows_by_id = {r['id']: r for r in list_campaigns(guild_id)}

    not_found    = [cid for cid in parsed_ids if cid not in rows_by_id]
    active_ids   = [cid for cid in parsed_ids
                    if cid in rows_by_id and rows_by_id[cid]['status'] == 'active']
    already_arch = [cid for cid in parsed_ids
                    if cid in rows_by_id and rows_by_id[cid]['status'] == 'archived']

    if not_found or active_ids or already_arch:
        problems = []
        if not_found:
            problems.append(f"not in this server: {', '.join(f'#{c}' for c in not_found)}")
        if active_ids:
            names = ', '.join(f"**{rows_by_id[c]['name']}** (#{c})" for c in active_ids)
            problems.append(f"currently active: {names}")
        if already_arch:
            names = ', '.join(f"**{rows_by_id[c]['name']}** (#{c})" for c in already_arch)
            problems.append(f"already archived: {names}")
        await interaction.response.send_message(
            f"{E['facepalm']} Batch refused — nothing was archived. "
            f"Issues: {'; '.join(problems)}.",
            ephemeral=True
        )
        return

    # All valid — archive the lot.
    archived_names = []
    for cid in parsed_ids:
        result = campaign_set_status(cid, 'archived')
        if result['updated']:
            archived_names.append(f"**{rows_by_id[cid]['name']}** (#{cid})")
        else:
            # Engine refusal mid-batch shouldn't happen since we validated,
            # but defense-in-depth: log it and report what made it through.
            log(f"deletecampaign: batch mid-failure campaign={cid} "
                f"reason={result['reason']!r}")

    if len(archived_names) == 1:
        await interaction.response.send_message(
            f"{E['ok']} Archived {archived_names[0]}. "
            f"Reversible via `/setcampaign {parsed_ids[0]}`. "
            f"Permanent removal: `/purgecampaign`.",
            ephemeral=True
        )
    else:
        await interaction.response.send_message(
            f"{E['ok']} Archived {len(archived_names)} campaigns: "
            f"{', '.join(archived_names)}. "
            f"Restore any with `/setcampaign <id>`. "
            f"Permanent removal: `/purgecampaign` or `/purgeallcampaigns`.",
            ephemeral=True
        )


@bot.tree.command(name='purgecampaign',
                  description='[DM] PERMANENTLY delete an archived campaign and all its data. Irreversible.')
@app_commands.describe(
    campaign_id='Campaign id (must already be archived).',
    confirm_phrase='Type exactly: DELETE <campaign_name>',
)
async def purgecampaign(interaction: discord.Interaction,
                        campaign_id: int, confirm_phrase: str):
    """Hard-delete a campaign and all dependent rows across 8 tables.
    Archived-only — the active campaign cannot be hit even with the
    right phrase, and inactive campaigns must be archived first.
    Two independent actions required before destruction is possible
    (archive + purge), per design.

    Confirmation phrase format: 'DELETE <campaign_name>' typed exactly,
    case-sensitive. Reduces fat-finger risk on permanent deletion.
    """
    if not is_dm_or_creator(interaction):
        await interaction.response.send_message("DM or campaign owner only.", ephemeral=True)
        return
    guild_id = str(interaction.guild_id)

    target = next((r for r in list_campaigns(guild_id) if r['id'] == campaign_id), None)
    if target is None:
        await interaction.response.send_message(
            f"{E['facepalm']} No campaign #{campaign_id} in this server.",
            ephemeral=True
        )
        return

    if target['status'] != 'archived':
        await interaction.response.send_message(
            f"{E['facepalm']} **{target['name']}** is `{target['status']}`, not archived. "
            f"Archive first (`/deletecampaign {campaign_id}`), then purge.",
            ephemeral=True
        )
        return

    expected = f"DELETE {target['name']}"
    # Normalize incoming phrase: strip surrounding whitespace, collapse
    # internal whitespace (handles non-breaking space from clients,
    # double-space autocomplete artifacts, etc). The expected phrase
    # is built from canonical campaign name so doesn't need normalization
    # — but applying the same normalization to both keeps it symmetric.
    import re as _re
    def _norm(s): return _re.sub(r'\s+', ' ', s.strip())
    if _norm(confirm_phrase) != _norm(expected):
        log(f"purgecampaign: phrase mismatch campaign={campaign_id} "
            f"got={confirm_phrase!r} expected={expected!r}")
        await interaction.response.send_message(
            f"{E['facepalm']} Confirmation phrase did not match. "
            f"To purge **{target['name']}**, type exactly: `{expected}`",
            ephemeral=True
        )
        return

    result = campaign_delete_cascade(campaign_id)
    if not result['deleted']:
        await interaction.response.send_message(
            f"{E['facepalm']} Could not purge: {result['reason']}.",
            ephemeral=True
        )
        return

    # rows_deleted summary — show the per-table counts so the DM can
    # see exactly what was lost. Useful for "did the cascade actually
    # work" verification on the first real run.
    counts = result['rows_deleted']
    summary = ", ".join(f"{tbl.replace('dnd_', '')}={n}"
                        for tbl, n in counts.items() if n > 0)
    if not summary:
        summary = "(no dependent rows)"

    await interaction.response.send_message(
        f"{E['ok']} Purged **{target['name']}** (#{campaign_id}). "
        f"Rows deleted: {summary}.",
        ephemeral=True
    )


@bot.tree.command(name='purgeallcampaigns',
                  description='[DM] PERMANENTLY delete EVERY archived campaign in this server. Irreversible.')
@app_commands.describe(confirm_phrase='Type exactly: DELETE ALL ARCHIVED')
async def purgeallcampaigns(interaction: discord.Interaction, confirm_phrase: str):
    """Bulk hard-delete: removes every archived campaign in this guild
    plus all their dependent rows across 8 tables.

    Two independent destruction gates (per design):
      1. Campaigns must already be archived. The active campaign cannot
         be hit by this command — even with the right phrase — because
         it is not archived. Inactive campaigns are also skipped (must
         /deletecampaign them first to bring them into scope).
      2. Confirmation phrase must match exactly: 'DELETE ALL ARCHIVED'.

    The phrase is global (not per-name) because per-name confirmation
    doesn't scale to bulk. This is the highest-friction destructive
    command in the system; the friction is the feature.
    """
    if not is_dm_or_creator(interaction):
        await interaction.response.send_message("DM or campaign owner only.", ephemeral=True)
        return
    guild_id = str(interaction.guild_id)

    # Same whitespace tolerance as /purgecampaign.
    import re as _re
    def _norm(s): return _re.sub(r'\s+', ' ', s.strip())
    expected = "DELETE ALL ARCHIVED"
    if _norm(confirm_phrase) != _norm(expected):
        log(f"purgeallcampaigns: phrase mismatch guild={guild_id} "
            f"got={confirm_phrase!r} expected={expected!r}")
        await interaction.response.send_message(
            f"{E['facepalm']} Confirmation phrase did not match. "
            f"To purge ALL archived campaigns in this server, type exactly: `{expected}`",
            ephemeral=True
        )
        return

    archived_rows = [r for r in list_campaigns(guild_id) if r['status'] == 'archived']
    if not archived_rows:
        await interaction.response.send_message(
            f"{E['ok']} No archived campaigns to purge.",
            ephemeral=True
        )
        return

    purged = []
    failed = []
    aggregate_counts = {}
    for r in archived_rows:
        result = campaign_delete_cascade(r['id'])
        if result['deleted']:
            purged.append(f"**{r['name']}** (#{r['id']})")
            for tbl, n in result['rows_deleted'].items():
                aggregate_counts[tbl] = aggregate_counts.get(tbl, 0) + n
        else:
            failed.append((r, result['reason']))
            log(f"purgeallcampaigns: cascade refused id={r['id']} "
                f"reason={result['reason']!r}")

    summary = ", ".join(f"{tbl.replace('dnd_', '')}={n}"
                        for tbl, n in aggregate_counts.items() if n > 0)
    if not summary:
        summary = "(no dependent rows)"

    msg = (f"{E['ok']} Purged {len(purged)} campaign"
           f"{'s' if len(purged) != 1 else ''}: "
           f"{', '.join(purged)}. "
           f"Total rows deleted: {summary}.")
    if failed:
        msg += (f"\n{E['facepalm']} {len(failed)} could not be purged: "
                + ", ".join(f"#{r['id']} ({reason})" for r, reason in failed))
    await interaction.response.send_message(msg, ephemeral=True)


async def scan_avrae_characters(channel, lookback: int = 50) -> list[dict]:
    """Scan recent messages for distinct Avrae sheet embeds.

    Returns a list of {name, race, char_class, level} dicts, deduped by
    name (most recent wins), in most-recent-first order.
    """
    found = {}
    try:
        async for msg in channel.history(limit=lookback):
            if not al.is_avrae(msg):
                continue
            for embed in msg.embeds:
                author_name = ''
                if embed.author and embed.author.name:
                    author_name = embed.author.name.strip()
                title = (embed.title or '').strip()
                candidate = author_name or title
                if not candidate:
                    continue
                desc = (embed.description or '').strip()
                first_line = desc.split('\n')[0].strip() if desc else ''
                tokens = first_line.split()
                if len(tokens) < 2 or not tokens[-1].isdigit():
                    continue
                level = int(tokens[-1])
                head = tokens[:-1]
                if len(head) >= 2:
                    char_class = head[-1]
                    race = ' '.join(head[:-1])
                else:
                    char_class = head[0] if head else ''
                    race = ''
                # Most recent first because history() yields newest first;
                # only keep the first occurrence of each name.
                if candidate not in found:
                    found[candidate] = {
                        'name': candidate,
                        'race': race,
                        'char_class': char_class,
                        'level': level,
                    }
    except Exception as e:
        log(f"scan_avrae_characters error: {e}")
    return list(found.values())


async def fetch_avrae_sheet_data(channel, character_name: str, lookback: int = 50):
    """Scan recent messages for an Avrae sheet embed matching character_name.

    Avrae's !beyond and !sheet output an embed where:
      - Title is the character name (e.g. "Donovan Ruby")
      - Description first line is "Race Class Level" (e.g. "Dwarf Rogue 1",
        "Half-Orc Barbarian 3", "Variant Human Wizard 2")

    Returns dict with race, char_class, level — or None if not found.
    """
    try:
        async for msg in channel.history(limit=lookback):
            if not al.is_avrae(msg):
                continue
            for embed in msg.embeds:
                # Avrae puts the character name on embed.author.name, not title
                author_name = ''
                if embed.author and embed.author.name:
                    author_name = embed.author.name.strip()
                title = (embed.title or '').strip()
                candidate = author_name or title
                if candidate.lower() != character_name.lower():
                    continue
                desc = (embed.description or '').strip()
                first_line = desc.split('\n')[0].strip() if desc else ''
                tokens = first_line.split()
                if len(tokens) < 2 or not tokens[-1].isdigit():
                    continue
                level = int(tokens[-1])
                head = tokens[:-1]
                # Class is last token before level; race is everything before
                if len(head) >= 2:
                    char_class = head[-1]
                    race = ' '.join(head[:-1])
                else:
                    char_class = head[0] if head else ''
                    race = ''
                return {'race': race, 'char_class': char_class, 'level': level}
    except Exception as e:
        log(f"fetch_avrae_sheet_data error: {e}")
    return None


async def _bindchar_autocomplete(interaction: discord.Interaction, current: str):
    """Surface Avrae characters from the channel as autocomplete choices."""
    try:
        chars = await scan_avrae_characters(interaction.channel)
        current_lower = (current or '').lower()
        choices = []
        for c in chars:
            label = f"{c['name']} ({c['race']} {c['char_class']} {c['level']})"
            if not current_lower or current_lower in c['name'].lower():
                choices.append(app_commands.Choice(name=label[:100], value=c['name']))
            if len(choices) >= 25:
                break
        return choices
    except Exception as e:
        log(f"_bindchar_autocomplete error: {e}")
        return []


@bot.tree.command(name='bindchar', description='Bind your Discord account to a character imported via Avrae.')
@app_commands.describe(name='Pick the character Avrae has loaded for you.')
@app_commands.autocomplete(name=_bindchar_autocomplete)
async def bindchar(interaction: discord.Interaction, name: str):
    guild_id = str(interaction.guild_id)
    campaign = get_active_campaign(guild_id)
    if not campaign:
        await interaction.response.send_message(
            "No active campaign. DM needs to run `/newcampaign` first.", ephemeral=True
        )
        return

    await interaction.response.defer()
    sheet_data = await fetch_avrae_sheet_data(interaction.channel, name)
    if not sheet_data:
        await interaction.followup.send(
            f"{E['facepalm']} I can't find an Avrae sheet for **{name}** in this channel.\n\n"
            "**Setup checklist**\n"
            "1. Make a character at <https://www.dndbeyond.com>\n"
            "2. Sign in to <https://avrae.io> with Discord\n"
            "3. In Discord: `!ddb` → click the link to connect D&D Beyond\n"
            "4. `!beyond <character-share-url>` to import\n"
            "5. Then run `/bindchar` and pick from the dropdown.",
            ephemeral=True,
        )
        return

    bind_character(
        campaign_id=campaign['id'],
        controller_id=str(interaction.user.id),
        name=name,
        race=sheet_data['race'],
        char_class=sheet_data['char_class'],
        level=sheet_data['level'],
    )
    await interaction.followup.send(
        f"{E['ok']} {interaction.user.mention} is now playing **{name}** "
        f"({sheet_data['race']} {sheet_data['char_class']}, level {sheet_data['level']})."
    )


@bot.tree.command(name='play', description='[DM] Open the scene with an opening narration.')
@app_commands.describe(scene='Optional scene seed (e.g. "the party arrives at the haunted mill")')
async def play(interaction: discord.Interaction, scene: str = None):
    if not is_dm_or_creator(interaction):
        await interaction.response.send_message("DM or campaign owner only.", ephemeral=True)
        return
    guild_id = str(interaction.guild_id)
    campaign = get_active_campaign(guild_id)
    if not campaign:
        await interaction.response.send_message(
            "No active campaign — `/newcampaign` first.", ephemeral=True
        )
        return

    chars = get_characters(campaign['id'])
    if not chars:
        await interaction.response.send_message(
            "No characters bound yet. Players need to run `/bindchar`.", ephemeral=True
        )
        return

    narration_ch = get_channel(interaction.guild, 'narration')
    if not narration_ch:
        await interaction.response.send_message(
            f"Missing #{CHANNEL_NAMES['narration']}. Run `/setup` first.", ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True)

    # First-session detection (S23 #4): if scene_state has never been
    # initialized for this campaign, this is the FIRST /play call and the
    # opening narration should include a hint footer for un-bound players.
    # Captured BEFORE init_scene_state replaces the row — that call always
    # creates a row (INSERT OR REPLACE), so the gate flips to False after
    # this point and subsequent /play calls correctly suppress the hint.
    prior_scene = get_scene_state(campaign['id'])
    is_first_session = prior_scene is None

    seed = scene or f"The party gathers, ready to begin {campaign['name']}."
    init_scene_state(campaign['id'], seed)

    # Track 4 #3 (Session 27) — seed campaign clock from skeleton.md's
    # optional `## Starting time` section. Narrow §17 exception per
    # §11.D=a + §J.3: writes directly to dnd_scene_state, bypasses
    # advance_time(), no audit-log row. Idempotency guard inside the
    # helper — only fires when scene_state is at defaults (1, Morning).
    # Soft-fail: any error here must not block /play opening narration.
    if is_first_session:
        try:
            from skeleton_loader import apply_starting_time_seed
            await asyncio.to_thread(apply_starting_time_seed, campaign['id'])
        except Exception as e:
            log(f"/play: apply_starting_time_seed error: {e!r}")

    # Open scene gets full DM treatment — knowledge_search will pull Mercer
    # campaign openings since we tag this as a "scene transition."
    try:
        async with narration_ch.typing():
            opening = await asyncio.to_thread(
                dm_respond, campaign, chars, f"[Open the scene] {seed}", [],
                None
            )
    except (discord.HTTPException, asyncio.TimeoutError) as e:
        log(f"typing_indicator_failed: command=play err={e!r}")
        opening = await asyncio.to_thread(
            dm_respond, campaign, chars, f"[Open the scene] {seed}", [],
            None
        )

    chroma_store(campaign['id'], 'dm', opening)
    update_scene(campaign['id'], opening[:500])

    opening_md = opening.replace('<b>', '**').replace('</b>', '**').replace('<i>', '*').replace('</i>', '*')
    body = opening_md[:4000]
    embed = discord.Embed(
        title=f"⚔  {campaign['name']}",
        description=body,
        color=discord.Color.dark_red()
    )

    # State-aware footer (4b). Mirrors `_dm_respond_and_post` assembly:
    # state header (mode glyph + ` · Day N, Phase` after Track 4 #3 §J.3
    # seed) + identity line (📍 location + 🗒️ active quests). No actor
    # field on /play — the DM is opening the scene, no player just acted.
    # Soft-fail at the call site per Doctrine §59: footer issues never
    # block the opening narration.
    state_header = ''
    state_signals = {}
    identity_bits = []
    try:
        scene_state = get_scene_state(campaign['id'])
        active_turn = get_active_turn(campaign['id'])
        combatants_payload = get_combatants(campaign['id'])
        bound_pcs = get_bound_character_names(campaign['id']) or []
        state_header, state_signals = orch.render_state_footer(
            scene_state, active_turn, combatants_payload, bound_pcs
        )
    except Exception as e:
        log(f"/play: state footer render failed: {e}")
        state_header = ''
        state_signals = {}

    try:
        current_loc = get_current_location(campaign['id'])
        if current_loc:
            identity_bits.append(f"📍 {current_loc['canonical_name']}")
    except Exception as e:
        log(f"/play: current_location footer lookup failed: {e}")

    try:
        active_quests = get_active_quests(campaign['id'])
        if active_quests:
            titles = []
            for q in active_quests:
                t = q.get('title') or q.get('name') or ''
                if t:
                    titles.append(t.strip())
            if titles:
                quest_line = "🗒️ " + ", ".join(titles)
                if len(quest_line) > 200:
                    quest_line = quest_line[:197] + "..."
                identity_bits.append(quest_line)
    except Exception as e:
        log(f"/play: quest reminder footer lookup failed: {e}")

    identity_line = " ".join(identity_bits)
    footer_text = state_header + identity_line if state_header else identity_line
    if len(footer_text) > 2048:
        footer_text = footer_text[:2045] + "..."
    if footer_text:
        embed.set_footer(text=footer_text)

    await narration_ch.send(embed=embed)
    log(f"state_footer: campaign={campaign['id']} "
        f"{orch.state_footer_log_summary(state_signals)}")
    await interaction.followup.send(f"{E['ok']} Scene opened in {narration_ch.mention}.", ephemeral=True)


@bot.tree.command(name='nudge', description='[DM] Prompt a player to act in-character.')
@app_commands.describe(player='The player to nudge')
async def nudge(interaction: discord.Interaction, player: discord.Member):
    if not is_dm_or_creator(interaction):
        await interaction.response.send_message("DM or campaign owner only.", ephemeral=True)
        return
    guild_id = str(interaction.guild_id)
    campaign = get_active_campaign(guild_id)
    if not campaign:
        await interaction.response.send_message("No active campaign.", ephemeral=True)
        return
    char = get_character_by_controller(campaign['id'], str(player.id))
    if not char:
        await interaction.response.send_message(f"{player.mention} has no character bound.", ephemeral=True)
        return
    narration_ch = get_channel(interaction.guild, 'narration')
    if not narration_ch:
        await interaction.response.send_message("No narration channel.", ephemeral=True)
        return
    await narration_ch.send(
        f"{E['think']} {player.mention} — **{char['name']}**, the moment turns to you. What do you do?"
    )
    await interaction.response.send_message(f"{E['ok']} Nudged.", ephemeral=True)


# ─────────────────────────────────────────────────────────
# /travel — narrative state transition (Phase 12-side, post-session)
# ─────────────────────────────────────────────────────────
# Authoritative scene transition. Implementation pattern reusable for future
# transition commands (/rest, /camp, /downtime, /fastforward) — the common
# shape is: build a transition_context block, set persistent state, call
# the DM with the directive so narration begins post-transition.

@bot.tree.command(
    name='travel',
    description='Compress travel to a destination. The DM picks up the scene at arrival.'
)
@app_commands.describe(
    destination='Where the party is going',
    elapsed='How long the journey takes (e.g. "1 day", "an hour", "three days"). Defaults to "a day".',
    arrival_time='Time of day at arrival (e.g. "evening", "dawn", "midnight"). Defaults to "evening".'
)
async def travel(interaction: discord.Interaction,
                 destination: str,
                 elapsed: str = 'a day',
                 arrival_time: str = 'evening'):
    guild_id = str(interaction.guild_id)
    campaign = get_active_campaign(guild_id)
    if not campaign:
        await interaction.response.send_message(
            "No active campaign here. Run `/play` first.", ephemeral=True
        )
        return

    characters = get_characters(campaign['id'])
    if not characters:
        await interaction.response.send_message(
            "No bound characters in this campaign.", ephemeral=True
        )
        return

    narration_ch = get_channel(interaction.guild, 'narration')
    if not narration_ch:
        await interaction.response.send_message(
            "No narration channel configured.", ephemeral=True
        )
        return

    # Resolve origin from current_location_id (may be NULL — early-stage
    # play can transition without a known origin per the C policy).
    try:
        origin_loc = get_current_location(campaign['id'])
    except Exception as e:
        log(f"/travel: origin lookup failed: {e}")
        origin_loc = None
    origin_name = origin_loc['canonical_name'] if origin_loc else 'an unknown place'

    # Resolve destination. Bug 3 fix: persist the travel destination
    # unconditionally. If the row doesn't exist yet, create it via
    # location_upsert and then set current_location_id. Without this,
    # /travel to an unseen location updates only the embed footer (one-shot)
    # while scene_state.current_location_id stays pointed at the prior
    # location forever — see FAILURES.md F-13.
    try:
        dest_loc = location_get_by_name(campaign['id'], destination)
    except Exception as e:
        log(f"/travel: destination lookup failed: {e}")
        dest_loc = None

    created = False
    if dest_loc is None:
        try:
            new_id = location_upsert(campaign['id'], destination)
        except Exception as e:
            log(f"/travel: location_upsert error: {e}")
            new_id = None
        if new_id is not None:
            try:
                dest_loc = location_get(campaign['id'], new_id)
            except Exception as e:
                log(f"/travel: location_get after upsert failed: {e}")
                dest_loc = None
            created = dest_loc is not None

    if dest_loc:
        try:
            ok = set_current_location(campaign['id'], dest_loc['id'])
            if not ok:
                log(f"/travel: set_current_location refused for "
                    f"campaign={campaign['id']} dest_id={dest_loc['id']}")
        except Exception as e:
            log(f"/travel: set_current_location error: {e}")
        dest_canonical = dest_loc['canonical_name']
    else:
        dest_canonical = destination.strip()

    # Track 4 #3 — deterministic time advancement from elapsed string.
    # `arrival_time` is display-only per §11.G=b lock and does NOT drive
    # advance_time(); it still flows into the TRAVEL_TRANSITION block as
    # flavor (existing behavior preserved). Soft-fail per §59 — a
    # parse/advance failure must never block the narration call.
    try:
        parsed = parse_elapsed(elapsed)
        if parsed is not None and parsed != (0, 0):
            advance_time(
                campaign['id'], parsed[0], parsed[1],
                source='travel',
                source_detail=f"{dest_canonical}; elapsed={elapsed}",
            )
    except Exception as e:
        log(f"/travel: advance_time error: {e!r}")

    # Build the transition directive. Engine prepends this as authoritative
    # context — the DM is told the journey is done, narrate at arrival.
    transition_block = (
        "TRAVEL_TRANSITION:\n"
        f"origin={origin_name}\n"
        f"destination={dest_canonical}\n"
        f"elapsed={elapsed}\n"
        f"arrival_time={arrival_time}\n"
        "instruction=Begin narration at arrival. Do not narrate the road "
        "journey, the road conditions, or any intervening events. Open with "
        "a single atmospheric beat at the destination, then hand agency "
        "back to the player."
    )

    log(f"/travel: campaign={campaign['id']} from={origin_name!r} "
        f"to={dest_canonical!r} resolved={1 if dest_loc else 0} "
        f"created={1 if created else 0}")

    # The synthetic player_action is human-readable so chat history stays
    # coherent, but the LLM's behavior is dominated by the transition_block.
    synthetic_action = f"The party travels to {dest_canonical}."

    # Acknowledge to player immediately. The DM call may take a few seconds.
    await interaction.response.send_message(
        f"{E.get('ok', '✅')} Travel: **{origin_name}** → **{dest_canonical}** "
        f"({elapsed}). The DM is opening the arrival scene...",
        ephemeral=True
    )

    # Do the DM call inline (not via batcher) — /travel is its own
    # narrative beat, not a chained player action. If the destination
    # didn't resolve to a row, override the footer so it shows the
    # intended destination rather than the (now-stale) prior location.
    primary_actor = characters[0]['name']
    label_override = None if dest_loc else dest_canonical
    await _dm_respond_and_post(
        campaign,
        characters,
        actions=[(primary_actor, synthetic_action)],
        combined_action=synthetic_action,
        transition_context=transition_block,
        location_label_override=label_override,
    )


@bot.tree.command(
    name='advance',
    description='[DM] Manually advance the campaign clock (days and/or phases).'
)
@app_commands.describe(
    days='Days to advance (default 0)',
    phases='Phases to advance (default 0)',
    set_phase='Optional: jump to a specific phase. Overrides phases.',
)
@app_commands.choices(set_phase=[
    app_commands.Choice(name='Morning',    value='Morning'),
    app_commands.Choice(name='Midday',     value='Midday'),
    app_commands.Choice(name='Afternoon',  value='Afternoon'),
    app_commands.Choice(name='Evening',    value='Evening'),
    app_commands.Choice(name='Night',      value='Night'),
    app_commands.Choice(name='Late Night', value='Late Night'),
])
async def advance_cmd(interaction: discord.Interaction,
                      days: int = 0,
                      phases: int = 0,
                      set_phase: app_commands.Choice[str] | None = None):
    """Track 4 #3 — DM-explicit narrative compression. Single-write-path
    surface for advancing the clock outside of /travel and Avrae rest
    events. Per §11.B=c lock; ships in v1."""
    if not is_dm_or_creator(interaction):
        await interaction.response.send_message(
            "DM or campaign owner only.", ephemeral=True
        )
        return
    guild_id = str(interaction.guild_id)
    campaign = get_active_campaign(guild_id)
    if not campaign:
        await interaction.response.send_message(
            "No active campaign here. Run `/play` first.", ephemeral=True
        )
        return
    sp_value = set_phase.value if set_phase else None
    # Defensive: validate phase string. The Choice constraint already
    # enforces this for slash-command callers, but PHASES is the
    # authoritative engine source so a hand-typed override would still
    # be caught.
    if sp_value is not None and sp_value not in PHASES:
        await interaction.response.send_message(
            f"Invalid phase. Must be one of: {', '.join(PHASES)}",
            ephemeral=True
        )
        return
    if days < 0 or phases < 0:
        await interaction.response.send_message(
            "Days and phases must be non-negative (no rewind in v1).",
            ephemeral=True
        )
        return
    if days == 0 and phases == 0 and sp_value is None:
        await interaction.response.send_message(
            "Specify `days`, `phases`, or `set_phase`.", ephemeral=True
        )
        return
    detail_bits = [f"days={days}", f"phases={phases}"]
    if sp_value:
        detail_bits.append(f"set_phase={sp_value}")
    source_detail = "/advance " + " ".join(detail_bits)
    try:
        result = advance_time(
            campaign['id'], days, phases,
            source='advance',
            source_detail=source_detail,
            set_phase=sp_value,
        )
    except Exception as e:
        log(f"/advance: advance_time error: {e!r}")
        result = None
    if result is None:
        await interaction.response.send_message(
            f"{E.get('facepalm', '⚠')} Advance failed (see logs). "
            f"Scene state may be missing — run `/play` first.",
            ephemeral=True
        )
        return
    await interaction.response.send_message(
        f"{E.get('ok', '✅')} Clock: "
        f"**{result.before_day}, {result.before_phase}** → "
        f"**{result.after_day}, {result.after_phase}**",
        ephemeral=True
    )


@bot.tree.command(name='mode', description='[DM] Manually set the scene mode (combat/exploration/social/travel/downtime).')
@app_commands.describe(mode='The new scene mode')
@app_commands.choices(mode=[
    app_commands.Choice(name='Exploration', value='exploration'),
    app_commands.Choice(name='Combat',      value='combat'),
    app_commands.Choice(name='Social',      value='social'),
    app_commands.Choice(name='Travel',      value='travel'),
    app_commands.Choice(name='Downtime',    value='downtime'),
])
async def mode_cmd(interaction: discord.Interaction, mode: app_commands.Choice[str]):
    if not is_dm_or_creator(interaction):
        await interaction.response.send_message("DM or campaign owner only.", ephemeral=True)
        return
    guild_id = str(interaction.guild_id)
    campaign = get_active_campaign(guild_id)
    if not campaign:
        await interaction.response.send_message("No active campaign.", ephemeral=True)
        return
    scene = get_scene_state(campaign['id'])
    if not scene:
        await interaction.response.send_message(
            "No scene state yet — run `/play` first to open the scene.",
            ephemeral=True
        )
        return
    current = scene.get('mode') or 'exploration'
    if current == mode.value:
        await interaction.response.send_message(
            f"Already in **{mode.value}** mode.", ephemeral=True
        )
        return
    set_scene_mode(campaign['id'], mode.value)
    await interaction.response.send_message(
        f"{E['ok']} Mode: **{current}** → **{mode.value}**", ephemeral=True
    )


async def clock_name_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    """Autocomplete for clock name parameters — returns live clock names."""
    campaign = get_active_campaign(str(interaction.guild_id))
    if not campaign:
        return []
    clocks = get_clocks(campaign['id'])
    return [
        app_commands.Choice(name=c['name'], value=c['name'])
        for c in clocks
        if current.lower() in c['name'].lower()
    ][:25]


clock_group = app_commands.Group(name='clock', description='[DM] Manage progress clocks for the current scene.')


@clock_group.command(name='create', description='[DM] Create a new progress clock.')
@app_commands.describe(name='Clock name (e.g. "Alarm Level")', capacity='Number of segments (2–12)')
async def clock_create_cmd(interaction: discord.Interaction, name: str, capacity: int):
    if not is_dm_or_creator(interaction):
        await interaction.response.send_message("DM or campaign owner only.", ephemeral=True)
        return
    campaign = get_active_campaign(str(interaction.guild_id))
    if not campaign:
        await interaction.response.send_message("No active campaign.", ephemeral=True)
        return
    err = clock_create(campaign['id'], name, capacity)
    if err:
        await interaction.response.send_message(f"{E['facepalm']} {err}", ephemeral=True)
    else:
        bar = "░" * capacity
        await interaction.response.send_message(
            f"{E['ok']} Clock created: **{name}** [{bar}] 0/{capacity}", ephemeral=True
        )


@clock_group.command(name='tick', description='[DM] Advance a clock by 1 or more segments.')
@app_commands.describe(name='Clock name', n='Number of ticks (default 1)')
@app_commands.autocomplete(name=clock_name_autocomplete)
async def clock_tick_cmd(interaction: discord.Interaction, name: str, n: int = 1):
    if not is_dm_or_creator(interaction):
        await interaction.response.send_message("DM or campaign owner only.", ephemeral=True)
        return
    campaign = get_active_campaign(str(interaction.guild_id))
    if not campaign:
        await interaction.response.send_message("No active campaign.", ephemeral=True)
        return
    clock, filled, err = clock_tick(campaign['id'], name, n)
    if err:
        await interaction.response.send_message(f"{E['facepalm']} {err}", ephemeral=True)
        return
    cap = clock['capacity']
    ticks = clock['ticks']
    bar = "█" * ticks + "░" * (cap - ticks)
    msg = f"{E['ok']} **{clock['name']}** [{bar}] {ticks}/{cap}"
    if filled:
        msg += "\n⚠️ **Clock filled!** The clock has reached its limit — trigger the consequence."
    await interaction.response.send_message(msg, ephemeral=True)


@clock_group.command(name='untick', description='[DM] Walk back a clock by 1 or more segments.')
@app_commands.describe(name='Clock name', n='Number of ticks to remove (default 1)')
@app_commands.autocomplete(name=clock_name_autocomplete)
async def clock_untick_cmd(interaction: discord.Interaction, name: str, n: int = 1):
    if not is_dm_or_creator(interaction):
        await interaction.response.send_message("DM or campaign owner only.", ephemeral=True)
        return
    campaign = get_active_campaign(str(interaction.guild_id))
    if not campaign:
        await interaction.response.send_message("No active campaign.", ephemeral=True)
        return
    clock, err = clock_untick(campaign['id'], name, n)
    if err:
        await interaction.response.send_message(f"{E['facepalm']} {err}", ephemeral=True)
        return
    cap = clock['capacity']
    ticks = clock['ticks']
    bar = "█" * ticks + "░" * (cap - ticks)
    await interaction.response.send_message(
        f"{E['ok']} **{clock['name']}** [{bar}] {ticks}/{cap}", ephemeral=True
    )


@clock_group.command(name='list', description='[PLAYER] Show all active progress clocks.')
async def clock_list_cmd(interaction: discord.Interaction):
    campaign = get_active_campaign(str(interaction.guild_id))
    if not campaign:
        await interaction.response.send_message("No active campaign.", ephemeral=True)
        return
    clocks = get_clocks(campaign['id'])
    if not clocks:
        await interaction.response.send_message("No active clocks.", ephemeral=True)
        return
    lines = []
    for c in clocks:
        ticks = c.get('ticks', 0)
        cap = c.get('capacity', 6)
        bar = "█" * ticks + "░" * (cap - ticks)
        lines.append(f"**{c['name']}** [{bar}] {ticks}/{cap}")
    await interaction.response.send_message("\n".join(lines), ephemeral=True)


@clock_group.command(name='reset', description='[DM] Reset a clock to 0 ticks.')
@app_commands.describe(name='Clock name')
@app_commands.autocomplete(name=clock_name_autocomplete)
async def clock_reset_cmd(interaction: discord.Interaction, name: str):
    if not is_dm_or_creator(interaction):
        await interaction.response.send_message("DM or campaign owner only.", ephemeral=True)
        return
    campaign = get_active_campaign(str(interaction.guild_id))
    if not campaign:
        await interaction.response.send_message("No active campaign.", ephemeral=True)
        return
    err = clock_reset(campaign['id'], name)
    if err:
        await interaction.response.send_message(f"{E['facepalm']} {err}", ephemeral=True)
    else:
        await interaction.response.send_message(f"{E['ok']} **{name}** reset to 0.", ephemeral=True)


@clock_group.command(name='delete', description='[DM] Remove a clock entirely.')
@app_commands.describe(name='Clock name')
@app_commands.autocomplete(name=clock_name_autocomplete)
async def clock_delete_cmd(interaction: discord.Interaction, name: str):
    if not is_dm_or_creator(interaction):
        await interaction.response.send_message("DM or campaign owner only.", ephemeral=True)
        return
    campaign = get_active_campaign(str(interaction.guild_id))
    if not campaign:
        await interaction.response.send_message("No active campaign.", ephemeral=True)
        return
    err = clock_delete(campaign['id'], name)
    if err:
        await interaction.response.send_message(f"{E['facepalm']} {err}", ephemeral=True)
    else:
        await interaction.response.send_message(f"{E['ok']} Clock **{name}** deleted.", ephemeral=True)


bot.tree.add_command(clock_group)


# ─────────────────────────────────────────────────────────
# Quest Log slash commands (2C.2) — DM-only management.
# Active quests inject into the DM prompt via dnd_engine.quests_to_prompt_block.
# ─────────────────────────────────────────────────────────

quest_group = app_commands.Group(
    name='quest', description='[DM] Manage the campaign quest log.'
)


async def quest_id_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[int]]:
    """Autocomplete on quest titles, returns the id as the value."""
    campaign = get_active_campaign(str(interaction.guild_id))
    if not campaign:
        return []
    quests = get_all_quests(campaign['id'])
    needle = current.lower()
    return [
        app_commands.Choice(
            name=f"#{q['id']} [{q['status']}] {q['title']}"[:100],
            value=q['id']
        )
        for q in quests
        if needle in q['title'].lower() or needle in str(q['id'])
    ][:25]


@quest_group.command(name='add', description='[DM] Add a new active quest.')
@app_commands.describe(
    title='Short quest title (e.g. "Recover the Sunstone")',
    summary='One-line description (optional)',
    priority='Priority — defaults to normal',
    given_by='NPC who gave the quest (optional)',
)
@app_commands.choices(priority=[
    app_commands.Choice(name='low', value='low'),
    app_commands.Choice(name='normal', value='normal'),
    app_commands.Choice(name='urgent', value='urgent'),
])
async def quest_add_cmd(
    interaction: discord.Interaction,
    title: str,
    summary: str = '',
    priority: app_commands.Choice[str] = None,
    given_by: str = '',
):
    if not is_dm_or_creator(interaction):
        await interaction.response.send_message("DM or campaign owner only.", ephemeral=True)
        return
    campaign = get_active_campaign(str(interaction.guild_id))
    if not campaign:
        await interaction.response.send_message("No active campaign.", ephemeral=True)
        return
    pri_value = priority.value if priority else 'normal'
    qid = quest_add(campaign['id'], title, summary, pri_value, given_by)
    await interaction.response.send_message(
        f"{E['ok']} Quest #{qid} added: **{title}** ({pri_value})",
        ephemeral=True,
    )


@quest_group.command(name='list', description='[PLAYER] Show quests for this campaign.')
@app_commands.describe(status='Filter by status (default: active)')
@app_commands.choices(status=[
    app_commands.Choice(name='active', value='active'),
    app_commands.Choice(name='completed', value='completed'),
    app_commands.Choice(name='failed', value='failed'),
    app_commands.Choice(name='all', value='all'),
])
async def quest_list_cmd(
    interaction: discord.Interaction,
    status: app_commands.Choice[str] = None,
):
    campaign = get_active_campaign(str(interaction.guild_id))
    if not campaign:
        await interaction.response.send_message("No active campaign.", ephemeral=True)
        return
    status_value = status.value if status else 'active'
    if status_value == 'all':
        quests = get_all_quests(campaign['id'])
    else:
        quests = get_all_quests(campaign['id'], status_filter=status_value)
    if not quests:
        await interaction.response.send_message(
            f"No quests with status `{status_value}`.", ephemeral=True
        )
        return
    lines = []
    status_icon = {'active': '⚔', 'completed': '✓', 'failed': '✗'}
    for q in quests:
        icon = status_icon.get(q['status'], '•')
        pri = q.get('priority', 'normal')
        pri_tag = f" [{pri}]" if pri != 'normal' else ''
        given = q.get('given_by', '')
        given_tag = f" — {given}" if given else ''
        summary = q.get('summary', '')
        summary_tag = f"\n   _{summary}_" if summary else ''
        lines.append(f"{icon} **#{q['id']}** {q['title']}{pri_tag}{given_tag}{summary_tag}")
    body = "\n".join(lines)
    if len(body) > 1900:
        body = body[:1900] + "\n…(truncated — too many quests to display)"
    await interaction.response.send_message(body, ephemeral=True)


@quest_group.command(name='complete', description='[DM] Mark a quest completed.')
@app_commands.describe(quest_id='Quest to complete')
@app_commands.autocomplete(quest_id=quest_id_autocomplete)
async def quest_complete_cmd(interaction: discord.Interaction, quest_id: int):
    if not is_dm_or_creator(interaction):
        await interaction.response.send_message("DM or campaign owner only.", ephemeral=True)
        return
    campaign = get_active_campaign(str(interaction.guild_id))
    if not campaign:
        await interaction.response.send_message("No active campaign.", ephemeral=True)
        return
    if quest_set_status(campaign['id'], quest_id, 'completed'):
        await interaction.response.send_message(
            f"{E['ok']} Quest #{quest_id} marked completed.", ephemeral=True
        )
    else:
        await interaction.response.send_message(
            f"{E['facepalm']} Quest #{quest_id} not found.", ephemeral=True
        )


@quest_group.command(name='fail', description='[DM] Mark a quest failed.')
@app_commands.describe(quest_id='Quest to fail')
@app_commands.autocomplete(quest_id=quest_id_autocomplete)
async def quest_fail_cmd(interaction: discord.Interaction, quest_id: int):
    if not is_dm_or_creator(interaction):
        await interaction.response.send_message("DM or campaign owner only.", ephemeral=True)
        return
    campaign = get_active_campaign(str(interaction.guild_id))
    if not campaign:
        await interaction.response.send_message("No active campaign.", ephemeral=True)
        return
    if quest_set_status(campaign['id'], quest_id, 'failed'):
        await interaction.response.send_message(
            f"{E['ok']} Quest #{quest_id} marked failed.", ephemeral=True
        )
    else:
        await interaction.response.send_message(
            f"{E['facepalm']} Quest #{quest_id} not found.", ephemeral=True
        )


@quest_group.command(name='delete', description='[DM] Permanently delete a quest.')
@app_commands.describe(quest_id='Quest to delete')
@app_commands.autocomplete(quest_id=quest_id_autocomplete)
async def quest_delete_cmd(interaction: discord.Interaction, quest_id: int):
    if not is_dm_or_creator(interaction):
        await interaction.response.send_message("DM or campaign owner only.", ephemeral=True)
        return
    campaign = get_active_campaign(str(interaction.guild_id))
    if not campaign:
        await interaction.response.send_message("No active campaign.", ephemeral=True)
        return
    if quest_delete(campaign['id'], quest_id):
        await interaction.response.send_message(
            f"{E['ok']} Quest #{quest_id} deleted.", ephemeral=True
        )
    else:
        await interaction.response.send_message(
            f"{E['facepalm']} Quest #{quest_id} not found.", ephemeral=True
        )


bot.tree.add_command(quest_group)


# ─────────────────────────────────────────────────────────
# Companion slash commands (2C.3) — DM-only management.
# Companions are pure prompt content: they appear in the DM system prompt
# but have no mechanical state. Hard cap of 3 per campaign.
# ─────────────────────────────────────────────────────────

companion_group = app_commands.Group(
    name='companion', description='[DM] Manage NPC companions traveling with the party.'
)


async def companion_id_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[int]]:
    """Autocomplete on companion names, returns id as the value."""
    campaign = get_active_campaign(str(interaction.guild_id))
    if not campaign:
        return []
    companions = get_companions(campaign['id'])
    needle = current.lower()
    return [
        app_commands.Choice(
            name=f"#{c['id']} {c['name']}"[:100],
            value=c['id']
        )
        for c in companions
        if needle in c['name'].lower() or needle in str(c['id'])
    ][:25]


async def companion_name_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    """Autocomplete for /companion add — returns canonical NPC names from
    dnd_npcs that aren't already in dnd_companions.

    Pulls from the world the parser has actually persisted, so the player
    picks from people the world has named instead of free-typing (and
    typo'ing — see Eldrin Stormbow vs Stormbrew from session 1).
    Side effect: quietly forces canonicalization between the two systems.
    """
    campaign = get_active_campaign(str(interaction.guild_id))
    if not campaign:
        return []
    try:
        npcs = npc_list(campaign['id'])
    except Exception as e:
        log(f"companion autocomplete: npc_list failed: {e}")
        return []
    try:
        existing_companion_names = {
            c['name'].lower() for c in get_companions(campaign['id'])
        }
    except Exception as e:
        log(f"companion autocomplete: get_companions failed: {e}")
        existing_companion_names = set()

    needle = current.lower()
    # Sort: most-mentioned first (most-relevant in narrative), name tiebreak.
    candidates = sorted(
        npcs,
        key=lambda n: (-n.get('mention_count', 0), n['canonical_name'].lower())
    )
    return [
        app_commands.Choice(
            name=n['canonical_name'],
            value=n['canonical_name'],
        )
        for n in candidates
        if needle in n['canonical_name'].lower()
        and n['canonical_name'].lower() not in existing_companion_names
    ][:25]


@companion_group.command(name='add', description='[DM] Add a traveling companion (max 3).')
@app_commands.describe(
    name='Companion name (e.g. "Lyssa") — autocompletes from NPCs the world has met',
    persona='One-line persona — archetype, voice, perspective in plain language',
)
@app_commands.autocomplete(name=companion_name_autocomplete)
async def companion_add_cmd(
    interaction: discord.Interaction,
    name: str,
    persona: str = '',
):
    if not is_dm_or_creator(interaction):
        await interaction.response.send_message("DM or campaign owner only.", ephemeral=True)
        return
    campaign = get_active_campaign(str(interaction.guild_id))
    if not campaign:
        await interaction.response.send_message("No active campaign.", ephemeral=True)
        return
    cid = companion_add(campaign['id'], name, persona)
    if cid is None:
        await interaction.response.send_message(
            f"{E['facepalm']} Companion cap reached ({COMPANION_CAP}). "
            f"Remove one first with `/companion remove`.",
            ephemeral=True,
        )
        return
    await interaction.response.send_message(
        f"{E['ok']} Companion #{cid} added: **{name}**",
        ephemeral=True,
    )


@companion_group.command(name='list', description='[PLAYER] Show traveling companions.')
async def companion_list_cmd(interaction: discord.Interaction):
    campaign = get_active_campaign(str(interaction.guild_id))
    if not campaign:
        await interaction.response.send_message("No active campaign.", ephemeral=True)
        return
    companions = get_companions(campaign['id'])
    if not companions:
        await interaction.response.send_message("No companions.", ephemeral=True)
        return
    lines = []
    for c in companions:
        persona = c.get('persona', '')
        if persona:
            lines.append(f"**#{c['id']} {c['name']}** — {persona}")
        else:
            lines.append(f"**#{c['id']} {c['name']}**")
    body = f"({len(companions)}/{COMPANION_CAP}) " + "\n".join(lines)
    if len(body) > 1900:
        body = body[:1900] + "\n…(truncated)"
    await interaction.response.send_message(body, ephemeral=True)


@companion_group.command(name='edit', description='[DM] Edit a companion.')
@app_commands.describe(
    companion_id='Companion to edit',
    name='New name (optional)',
    persona='New persona (optional)',
)
@app_commands.autocomplete(companion_id=companion_id_autocomplete)
async def companion_edit_cmd(
    interaction: discord.Interaction,
    companion_id: int,
    name: str = None,
    persona: str = None,
):
    if not is_dm_or_creator(interaction):
        await interaction.response.send_message("DM or campaign owner only.", ephemeral=True)
        return
    if name is None and persona is None:
        await interaction.response.send_message(
            f"{E['facepalm']} Provide at least one field to edit (name or persona).",
            ephemeral=True,
        )
        return
    campaign = get_active_campaign(str(interaction.guild_id))
    if not campaign:
        await interaction.response.send_message("No active campaign.", ephemeral=True)
        return
    if companion_edit(campaign['id'], companion_id, name=name, persona=persona):
        await interaction.response.send_message(
            f"{E['ok']} Companion #{companion_id} updated.", ephemeral=True
        )
    else:
        await interaction.response.send_message(
            f"{E['facepalm']} Companion #{companion_id} not found.", ephemeral=True
        )


@companion_group.command(name='remove', description='[DM] Remove a companion.')
@app_commands.describe(companion_id='Companion to remove')
@app_commands.autocomplete(companion_id=companion_id_autocomplete)
async def companion_remove_cmd(interaction: discord.Interaction, companion_id: int):
    if not is_dm_or_creator(interaction):
        await interaction.response.send_message("DM or campaign owner only.", ephemeral=True)
        return
    campaign = get_active_campaign(str(interaction.guild_id))
    if not campaign:
        await interaction.response.send_message("No active campaign.", ephemeral=True)
        return
    if companion_remove(campaign['id'], companion_id):
        await interaction.response.send_message(
            f"{E['ok']} Companion #{companion_id} removed.", ephemeral=True
        )
    else:
        await interaction.response.send_message(
            f"{E['facepalm']} Companion #{companion_id} not found.", ephemeral=True
        )


bot.tree.add_command(companion_group)


# ─────────────────────────────────────────────────────────
# Encounter presets (2C.4) — DM-only orchestration command.
# Bundles mode change + clock creation + tension shift into one declarative
# action. Pure orchestration: no LLM in the path. Idempotent — re-running
# the same encounter while already in it is a graceful no-op.
# ─────────────────────────────────────────────────────────

# Each preset declares: target mode, list of (clock_name, capacity), tension delta.
# Tension delta only applies when the encounter actually starts fresh — if mode
# was already correct AND every preset clock already exists, no tension change.
ENCOUNTER_PRESETS = {
    'stealth': {
        'mode': 'exploration',
        'clocks': [('Detection', 4)],
        'tension_delta': 20,
    },
    'social': {
        'mode': 'social',
        'clocks': [('Patience', 4), ('Trust', 4)],
        'tension_delta': 0,
    },
    'trap': {
        'mode': 'exploration',
        'clocks': [('Trap Reveal', 3)],
        'tension_delta': 30,
    },
}


@bot.tree.command(name='encounter', description='[DM] Start a stealth, social, or trap encounter (sets mode + spawns clocks).')
@app_commands.describe(type='Encounter preset to apply')
@app_commands.choices(type=[
    app_commands.Choice(name='stealth', value='stealth'),
    app_commands.Choice(name='social', value='social'),
    app_commands.Choice(name='trap', value='trap'),
])
async def encounter_cmd(interaction: discord.Interaction, type: app_commands.Choice[str]):
    if not is_dm_or_creator(interaction):
        await interaction.response.send_message("DM or campaign owner only.", ephemeral=True)
        return
    campaign = get_active_campaign(str(interaction.guild_id))
    if not campaign:
        await interaction.response.send_message("No active campaign.", ephemeral=True)
        return
    scene = get_scene_state(campaign['id'])
    if not scene:
        await interaction.response.send_message(
            "No scene state — run `/play` first.", ephemeral=True
        )
        return

    preset = ENCOUNTER_PRESETS[type.value]
    actions_taken = []

    # 1. Mode — set only if not already correct.
    current_mode = scene.get('mode') or 'exploration'
    mode_changed = False
    if current_mode != preset['mode']:
        set_scene_mode(campaign['id'], preset['mode'])
        mode_changed = True
        actions_taken.append(f"mode → {preset['mode']}")

    # 2. Clocks — create missing only. Never mutate existing clocks.
    existing_clock_names = {c['name'].lower() for c in get_clocks(campaign['id'])}
    clocks_created = []
    for clock_name, capacity in preset['clocks']:
        if clock_name.lower() not in existing_clock_names:
            err = clock_create(campaign['id'], clock_name, capacity)
            if err is None:
                clocks_created.append(f"{clock_name} ({capacity})")
    if clocks_created:
        actions_taken.append("clocks: " + ", ".join(clocks_created))

    # 3. Tension — only shifts if the encounter is genuinely starting fresh.
    # Defined as: mode was changed OR at least one preset clock was created.
    # Pure no-op re-runs do not bump tension.
    fresh_start = mode_changed or bool(clocks_created)
    if fresh_start and preset['tension_delta']:
        current_tension = scene.get('tension_int', 0) or 0
        new_tension = max(0, min(100, current_tension + preset['tension_delta']))
        if new_tension != current_tension:
            update_tension(campaign['id'], new_tension)
            actions_taken.append(f"tension {current_tension} → {new_tension}")

    if not actions_taken:
        await interaction.response.send_message(
            f"{E['ok']} **{type.value}** encounter already active — nothing to do.",
            ephemeral=True,
        )
    else:
        await interaction.response.send_message(
            f"{E['ok']} **{type.value}** encounter started.\n• " + "\n• ".join(actions_taken),
            ephemeral=True,
        )
    log(f"encounter: campaign={campaign['id']} type={type.value} actions={actions_taken or 'no-op'}")


# ─────────────────────────────────────────────────────────
# /skeleton — authored canon loader (Phase 12C)
# ─────────────────────────────────────────────────────────
# Per-campaign skeleton.md lives at:
#   /home/jordaneal/scripts/campaigns/<campaign_id>/skeleton.md
#
# load:   parses + writes skeleton entities to dnd_npcs / dnd_locations
#         with skeleton_origin=1. Idempotent — re-runnable any time.
# status: shows whether the file exists, when it was last loaded, and
#         counts of authored entities currently in canon.

skeleton_group = app_commands.Group(
    name='skeleton',
    description='[DM] Manage authored campaign canon (skeleton.md).'
)


@skeleton_group.command(
    name='load',
    description='[DM] (Re)load this campaign\'s skeleton.md into canon.'
)
async def skeleton_load_cmd(interaction: discord.Interaction):
    if not is_dm_or_creator(interaction):
        await interaction.response.send_message("DM or campaign owner only.", ephemeral=True)
        return
    campaign = get_active_campaign(str(interaction.guild_id))
    if not campaign:
        await interaction.response.send_message("No active campaign.", ephemeral=True)
        return

    # Apply may take a beat — defer so the interaction doesn't time out.
    await interaction.response.defer(ephemeral=True, thinking=True)

    try:
        from skeleton_loader import apply_skeleton, _skeleton_path
        result = await asyncio.to_thread(apply_skeleton, campaign['id'])
    except Exception as e:
        log(f"/skeleton load: error campaign={campaign['id']} err={e!r}")
        await interaction.followup.send(
            f"{E.get('facepalm', '⚠️')} Loader crashed: `{e!r}`",
            ephemeral=True
        )
        return

    if result['status'] == 'no_file':
        path = _skeleton_path(campaign['id'])
        await interaction.followup.send(
            f"{E.get('facepalm', '⚠️')} No skeleton file found at:\n"
            f"`{path}`\n\n"
            f"Create the file with the skeleton template and re-run.",
            ephemeral=True,
        )
        return

    if result['status'] == 'parse_error':
        await interaction.followup.send(
            f"{E.get('facepalm', '⚠️')} Parse error — nothing written:\n"
            f"```\n{result['error'][:1000]}\n```",
            ephemeral=True,
        )
        return

    bits = [
        f"{E.get('ok', '✅')} Skeleton loaded.",
        f"• locations written: **{result['locations_written']}**",
        f"• NPCs written:      **{result['npcs_written']}**",
        f"• parent FKs resolved:   {result['parent_resolutions']}",
        f"• NPC location FKs:      {result['location_resolutions']}",
    ]
    if result['unresolved_parents']:
        bits.append(
            f"• unresolved parent_hint: " +
            ", ".join(result['unresolved_parents'][:5])
        )
    if result['unresolved_npc_locations']:
        bits.append(
            f"• unresolved NPC location_hint: " +
            ", ".join(result['unresolved_npc_locations'][:5])
        )
    await interaction.followup.send("\n".join(bits), ephemeral=True)


@skeleton_group.command(
    name='status',
    description='[DM] Show this campaign\'s skeleton file status + entity counts.'
)
async def skeleton_status_cmd(interaction: discord.Interaction):
    if not is_dm_or_creator(interaction):
        await interaction.response.send_message("DM or campaign owner only.", ephemeral=True)
        return
    campaign = get_active_campaign(str(interaction.guild_id))
    if not campaign:
        await interaction.response.send_message("No active campaign.", ephemeral=True)
        return

    from skeleton_loader import _skeleton_path, parse_skeleton_file, SkeletonParseError
    path = _skeleton_path(campaign['id'])

    bits = [f"**Skeleton status — campaign #{campaign['id']}**"]
    if not path.is_file():
        bits.append(f"• file: ❌ missing — expected at `{path}`")
        bits.append(f"• Create it and run `/skeleton load`.")
        await interaction.response.send_message("\n".join(bits), ephemeral=True)
        return

    bits.append(f"• file: ✅ `{path}`")
    try:
        parsed = parse_skeleton_file(campaign['id'])
        if parsed is None:
            bits.append("• parse: failed to read")
        else:
            bits.append(f"• parsed:  {len(parsed['npcs'])} NPCs, "
                        f"{len(parsed['locations'])} locations, "
                        f"{len(parsed['factions'])} factions, "
                        f"{len(parsed['hooks'])} hooks")
            if parsed['unknown_sections']:
                bits.append(f"• unknown sections (ignored): "
                            f"{', '.join(parsed['unknown_sections'])}")
    except SkeletonParseError as e:
        bits.append(f"• parse: ⚠️ ERROR — `{e}`")

    # Authored canon currently in DB
    try:
        all_npcs = npc_list(campaign['id'])
        sk_npcs = [n for n in all_npcs if n.get('skeleton_origin') == 1]
        all_locs = location_list(campaign['id'])
        sk_locs = [loc for loc in all_locs if loc.get('skeleton_origin') == 1]
        bits.append(f"• in DB: {len(sk_npcs)} skeleton NPCs, "
                    f"{len(sk_locs)} skeleton locations "
                    f"({len(all_npcs)} total NPCs, {len(all_locs)} total locations)")
    except Exception as e:
        bits.append(f"• db read failed: `{e!r}`")

    await interaction.response.send_message("\n".join(bits), ephemeral=True)


bot.tree.add_command(skeleton_group)


# ─────────────────────────────────────────────────────────
# Consequence ledger debug surface (Session 16) — minimal v1.
# Read-only `/consequence list [npc]`. No add/remove/inspect. Captures
# come from the dual-pass parser; the operator inspects what was written.
# Per CONSEQUENCE_SURFACING_SPEC §11 — minimum surface to answer "is the
# parser capturing the right things?"
# ─────────────────────────────────────────────────────────

def format_consequence_list(rows) -> str:
    """Format dnd_consequences rows for the /consequence list output.

    Each row renders as two markdown lines:
        **{npc}** · {kind} sev {N} · `{status}` · [{sources}] · surf {N} · T{turn}
          _{summary}_

    No monospace code block — variable-width content otherwise paints
    rows as sparse padded whitespace. Bold/italic/inline-code do the
    visual weighting work instead.

    Capped at ~1900 chars (Discord's 2000-char limit minus framing); rows
    beyond the cap are dropped with a "... and N more" note.
    """
    if not rows:
        return "_No consequences captured yet._"

    active_count   = sum(1 for r in rows if r.get('status') == 'active')
    promoted_count = sum(1 for r in rows if r.get('status') == 'promoted')

    header = f"**Consequences** — {active_count} active · {promoted_count} promoted"
    out_lines = [header, ""]
    used = len(header) + 2  # header + the blank line below
    truncated = 0
    for r in rows:
        meta = (
            f"**{r.get('canonical_name') or '?'}** · "
            f"{r.get('kind') or '?'} sev {r.get('severity', 0)} · "
            f"`{r.get('status') or '?'}` · "
            f"[{r.get('sources') or ''}] · "
            f"surf {r.get('surface_count', 0)} · "
            f"T{r.get('first_seen_turn', 0)}"
        )
        summary = (r.get('summary') or '').strip()
        body = f"  _{summary[:200]}_" if summary else ""
        block = meta + (("\n" + body) if body else "")
        # +2 accounts for the row newline + the blank line separator below it.
        if used + len(block) + 2 > 1900:
            truncated += 1
            continue
        out_lines.append(block)
        out_lines.append("")  # blank line between rows for visual separation
        used += len(block) + 2
    if truncated:
        out_lines.append(f"_... and {truncated} more (truncated for length)_")
    return "\n".join(out_lines).rstrip()


consequence_group = app_commands.Group(
    name='consequence',
    description='[DM] Inspect captured consequences (read-only debug).',
)


@consequence_group.command(
    name='list',
    description='Show captured consequences for this campaign.',
)
@app_commands.describe(
    npc='Optional canonical NPC name to filter (e.g. "Reginald the Innkeeper")'
)
async def consequence_list_cmd(interaction: discord.Interaction,
                                npc: str = ''):
    if not is_dm_or_creator(interaction):
        await interaction.response.send_message(
            "DM or campaign owner only.", ephemeral=True
        )
        return
    campaign = get_active_campaign(str(interaction.guild_id))
    if not campaign:
        await interaction.response.send_message(
            "No active campaign.", ephemeral=True
        )
        return
    rows = consequence_list_for_command(
        campaign['id'],
        npc_canonical=(npc.strip() or None),
    )
    msg = format_consequence_list(rows)
    if npc and not rows:
        msg = f"_No consequences captured for `{npc}`._"
    await interaction.response.send_message(msg, ephemeral=True)


bot.tree.add_command(consequence_group)


# ─────────────────────────────────────────────────────────
# Inventory (Track 4 #1) — narrative items per character
# ─────────────────────────────────────────────────────────


async def _bound_character_autocomplete(interaction: discord.Interaction, current: str):
    """Surface bound characters in the active campaign as autocomplete choices."""
    try:
        campaign = get_active_campaign(str(interaction.guild_id))
        if not campaign:
            return []
        chars = get_characters(campaign['id'])
        current_lower = (current or '').lower()
        choices = []
        for c in chars:
            name = c.get('name') or ''
            if not name:
                continue
            if not current_lower or current_lower in name.lower():
                choices.append(app_commands.Choice(name=name[:100], value=name))
            if len(choices) >= 25:
                break
        return choices
    except Exception as e:
        log(f"_bound_character_autocomplete error: {e}")
        return []


@bot.tree.command(
    name='inventory',
    description='Show narrative inventory for a character (defaults to your bound character).',
)
@app_commands.describe(
    character='Pick a bound character. Defaults to your own bound character.'
)
@app_commands.autocomplete(character=_bound_character_autocomplete)
async def inventory_cmd(interaction: discord.Interaction, character: str = ''):
    campaign = get_active_campaign(str(interaction.guild_id))
    if not campaign:
        await interaction.response.send_message("No active campaign.", ephemeral=True)
        return

    target_name = (character or '').strip()
    if not target_name:
        bound = get_character_by_controller(campaign['id'], str(interaction.user.id))
        if not bound:
            await interaction.response.send_message(
                "No bound character — pass a name (`/inventory character:Donovan Ruby`) "
                "or run `/bindchar` first.",
                ephemeral=True,
            )
            return
        target_name = bound['name']

    rows = get_inventory(campaign['id'], target_name)
    if not rows:
        await interaction.response.send_message(
            f"**{target_name}**'s inventory: _Empty._", ephemeral=True
        )
        return

    lines = [f"**{target_name}**'s inventory:"]
    for r in rows:
        item = r['item_name']
        qty = r['quantity']
        if qty and qty > 1:
            lines.append(f"- {item} (×{qty})")
        else:
            lines.append(f"- {item}")
    await interaction.response.send_message("\n".join(lines), ephemeral=True)


@bot.tree.command(
    name='giveitem',
    description='[DM] Give an item to a character.',
)
@app_commands.describe(
    character='Character to give the item to (pick from bound characters).',
    item='Item name (will be stored lowercase, case-insensitive lookup).',
    quantity='How many to give. Default 1.',
)
@app_commands.autocomplete(character=_bound_character_autocomplete)
async def giveitem_cmd(interaction: discord.Interaction,
                       character: str, item: str, quantity: int = 1):
    if not is_dm_or_creator(interaction):
        await interaction.response.send_message(
            "DM or campaign owner only.", ephemeral=True
        )
        return
    campaign = get_active_campaign(str(interaction.guild_id))
    if not campaign:
        await interaction.response.send_message("No active campaign.", ephemeral=True)
        return
    if quantity is None or quantity <= 0:
        await interaction.response.send_message(
            "Quantity must be a positive integer.", ephemeral=True
        )
        return
    char_clean = (character or '').strip()
    item_clean = (item or '').strip()
    if not char_clean or not item_clean:
        await interaction.response.send_message(
            "Character and item must both be non-empty.", ephemeral=True
        )
        return

    result = add_item(campaign['id'], char_clean, item_clean, quantity=quantity)
    log(f"inventory_give: campaign={campaign['id']} character={char_clean!r} "
        f"item={result['item_name']!r} qty={quantity} action={result['action']}")
    if result['action'] == 'invalid':
        await interaction.response.send_message(
            "Invalid item name or quantity.", ephemeral=True
        )
        return
    qn = result.get('quantity_now')
    qty_clause = f" (now ×{qn})" if qn and qn > 1 else ""
    verb = 'Added' if result['action'] == 'inserted' else 'Incremented'
    await interaction.response.send_message(
        f"{verb}: **{char_clean}** — {result['item_name']}{qty_clause}",
        ephemeral=True,
    )


async def _hydrate_npc_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    campaign = get_active_campaign(str(interaction.guild_id))
    if not campaign:
        return []
    try:
        npcs = npc_list(campaign['id'])
    except Exception:
        return []
    needle = current.lower()
    return [
        app_commands.Choice(name=n['canonical_name'][:100], value=n['canonical_name'])
        for n in npcs
        if needle in n['canonical_name'].lower()
    ][:25]


@bot.tree.command(name='hydrate', description='[DM] Set NPC combat stats from a CR band.')
@app_commands.describe(
    npc='NPC name (must already be in this campaign)',
    cr='Challenge Rating (0, 1/8, 1/4, 1/2, 1, 2, ... 12)',
)
@app_commands.autocomplete(npc=_hydrate_npc_autocomplete)
async def hydrate(interaction: discord.Interaction, npc: str, cr: str):
    if not is_dm_or_creator(interaction):
        await interaction.response.send_message(
            "Only the DM can use this command.", ephemeral=True
        )
        return
    if not interaction.guild:
        await interaction.response.send_message(
            "Must be used in a server.", ephemeral=True
        )
        return
    campaign = get_active_campaign(str(interaction.guild.id))
    if not campaign:
        await interaction.response.send_message(
            "No active campaign found.", ephemeral=True
        )
        return

    normalized = npc_hydrator.normalize_cr(cr)
    if normalized is None:
        valid = '0, 1/8, 1/4, 1/2, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12'
        await interaction.response.send_message(
            f"Invalid CR `{cr}`. Valid bands: {valid}",
            ephemeral=True
        )
        return

    campaign_id = campaign['id']
    npc_row = npc_get_by_name(campaign_id, npc)
    if npc_row is None:
        await interaction.response.send_message(
            f"NPC `{npc}` not found in this campaign. "
            f"Add them first via `!init add` or ask Virgil.",
            ephemeral=True
        )
        return

    canonical = npc_row['canonical_name']
    wrote, signals = npc_hydrate_stats(
        campaign_id, canonical, cr_str=normalized, source='explicit_hydrate'
    )

    # Clear pending hydration prompt for this NPC if present.
    _pending_hydration.discard((campaign_id, canonical))

    stats_written = 1 if wrote else 0
    log(f"hydration_manual: campaign={campaign_id} npc='{canonical}' "
        f"cr={normalized} stats_written={stats_written} "
        f"fields_updated={signals.get('stats_filled', 'none')}")

    # Fetch fresh row to show current stats in response.
    fresh = npc_get_by_name(campaign_id, canonical)
    if fresh and wrote:
        hp = fresh.get('hp_max') or '?'
        ac = fresh.get('ac') or '?'
        atk = fresh.get('attack_bonus') or '?'
        dmg = fresh.get('damage_dice') or '?'
        await interaction.response.send_message(
            f"Hydrated `{canonical}` at CR {normalized}: "
            f"HP {hp}, AC {ac}, Atk +{atk}, Dmg {dmg}.",
            ephemeral=True
        )
    else:
        hp = fresh.get('hp_max') or '?' if fresh else '?'
        ac = fresh.get('ac') or '?' if fresh else '?'
        atk = fresh.get('attack_bonus') or '?' if fresh else '?'
        dmg = fresh.get('damage_dice') or '?' if fresh else '?'
        await interaction.response.send_message(
            f"Stats already complete for `{canonical}` at CR {normalized} — "
            f"no fields updated. "
            f"Current: HP {hp}, AC {ac}, Atk +{atk}, Dmg {dmg}.",
            ephemeral=True
        )


@bot.tree.command(name='dmhelp', description='Show the player + DM cheatsheet.')
async def dmhelp(interaction: discord.Interaction):
    # Load COMMANDS.md fresh per §66 — no caching, edits take effect without
    # a bot restart. Same path/pattern as advisory mode's _load_commands_reference.
    raw = orch._load_commands_reference()
    if not raw:
        await interaction.response.send_message(
            "Command reference unavailable — COMMANDS.md not found. Ask the DM.",
            ephemeral=True,
        )
        return

    # Extract the auto-generated Virgil section between markers, stripping
    # the HTML comment lines themselves (they render as noise in Discord).
    start_marker = '<!-- VIRGIL_AUTO_GENERATED:START -->'
    end_marker   = '<!-- VIRGIL_AUTO_GENERATED:END -->'
    start_idx = raw.find(start_marker)
    end_idx   = raw.find(end_marker)
    if start_idx != -1 and end_idx != -1:
        section = raw[start_idx + len(start_marker):end_idx]
        lines = [ln for ln in section.splitlines()
                 if not ln.strip().startswith('<!--')
                 and not ln.rstrip().endswith('-->')]
        virgil_text = '\n'.join(lines).strip()
    else:
        virgil_text = raw.strip()

    # Convert to clean plain text for DM. Format:
    #   **Title Case Heading:**  (blank line)  commands  (blank line before next)
    # Strip markdown list prefix — Discord renders `- item` with trailing commas.
    def _title(text):
        # Capitalize each word; keep all-caps tokens (e.g. "DM") unchanged.
        return ' '.join(
            w if (w.isupper() and len(w) > 1) else w.capitalize()
            for w in text.split()
        )

    plain_lines = []
    first_section = True
    for ln in virgil_text.splitlines():
        stripped = ln.strip()
        if ln.startswith('### '):
            if not first_section:
                plain_lines.append('')   # blank line between sections
            first_section = False
            plain_lines.append(f'**{_title(ln[4:])}:**')
        elif stripped.startswith('- '):
            plain_lines.append(stripped[2:].replace('`', ''))
        elif stripped:
            plain_lines.append(stripped.replace('`', ''))
        # Blank source lines skipped — spacing managed explicitly above.
    body = '\n'.join(plain_lines)

    # Chunk at bold-heading boundaries to stay under Discord's 2000-char
    # per-message limit without orphaning section headers.
    pieces = re.split(r'(?=\n\n\*\*)', body)
    chunks = []
    current = ""
    for piece in pieces:
        candidate = current + piece if current else piece
        if len(candidate) <= 1900:
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = piece if len(piece) <= 1900 else piece[:1900]
    if current:
        chunks.append(current)

    # Send as a private DM so the list persists (ephemeral disappears on dismiss).
    # Fall back to ephemeral in-channel if the user has DMs disabled.
    try:
        for chunk in chunks:
            await interaction.user.send(chunk)
        await interaction.response.send_message(
            "Sent you a DM with the full command list.", ephemeral=True
        )
    except discord.Forbidden:
        await interaction.response.send_message(body[:1900], ephemeral=True)


# ─────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────

def main():
    if not DISCORD_TOKEN:
        log("DISCORD_BOT_TOKEN not set — exiting")
        sys.exit(1)
    db_init()
    chroma_init()
    log("starting Discord DnD bot")
    bot.run(DISCORD_TOKEN, log_handler=None)


if __name__ == '__main__':
    main()
