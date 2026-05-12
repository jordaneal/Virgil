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
    update_last_active_actor,
    reset_narrative_buffers_on_combat_exit,
    pending_directive_upsert, pending_directive_get_active,
    pending_directive_consume, pending_directive_delete_by_message,
    pending_directive_age_seconds,
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


# ─────────────────────────────────────────────────────────
# Bug 1 Phase 1 (Session 32) — DM roll-directive parser
# ─────────────────────────────────────────────────────────
# When the DM types `!check stealth` / `!save dex` / `!cast guidance`
# in #dm-narration, parse the directive and (telemetry-only in Phase 1)
# snapshot a pending row bound to the current footer-actor. Phase 2 binds
# auto-narration to a verified pending row; Phase 1 ships the matching
# layer + telemetry only — `dm_respond` is NEVER auto-fired here.
#
# Trigger surface: literal `!check ` / `!save ` / `!cast ` (trailing
# space). Avrae shorthand (`!c`) and modifier flags (`-dc 15`, `adv`)
# are NOT recognized as bare-skill in v1; they fall to the
# `directive_text_unparsed:` log line for Phase 2 calibration.

# Bare-skill regex. Strips a leading `<@DM_id>` mention if present;
# captures the rest of the line as the candidate skill string.
_DM_DIRECTIVE_RX = re.compile(
    r"^\s*(?:<@!?\d+>\s*)?"            # optional leading @-mention
    r"!(?P<kind>check|save|cast)\s+"   # !check / !save / !cast
    r"(?P<skill>.+?)\s*$",
    re.IGNORECASE,
)
_DIRECTIVE_TRIGGER_PREFIXES = ('!check ', '!save ', '!cast ')

# Tokens that mean the captured skill string carries trailing arguments
# (advantage/disadvantage flags, DC overrides, comments). When any of
# these appear in the skill string, the directive is logged as unparsed
# rather than emitted as a pending row.
_DIRECTIVE_TRAILING_MODIFIER_TOKENS = {
    'adv', 'advantage', 'dis', 'disadvantage',
}
# Group-roll surface phrases (the DM addressing the whole party). Logged
# as `reason=group_directive` skip — kept defensive for when a group
# pattern slips into the captured skill string.
_DIRECTIVE_GROUP_KEYWORDS = (
    'everyone', 'all of you', 'the party', 'party rolls',
)


# Ship A (S36) — LLM-emit directive parser. Distinct from _DM_DIRECTIVE_RX
# which assumes the directive is the WHOLE message (^...$ anchors). LLM
# emissions are embedded inside narration prose, typically at end of
# response. S36 #5 patch: accept operator-locked format
# `**!check skill DC : <First Name>**` — skill_raw capture stops at `:`
# or `*` (bold markers) so the colon-and-name suffix doesn't leak into
# the skill string; the trailing `:` + name + closing `**` are tolerated
# via the optional suffix clause.
_LLM_EMIT_DIRECTIVE_RX = re.compile(
    r"!(?P<kind>check|save|cast)\s+(?P<skill_raw>[^\n!:*]+?)\s*"
    r"(?::\s*[^\n!*]+?)?"     # optional ": <Character Name>" suffix
    r"\s*(?=\n|$|\*)",        # stop at newline, end-of-string, or `**` close
    re.IGNORECASE,
)


def _parse_llm_emit_directive(response: str) -> dict | None:
    """Find the last !check/!save/!cast directive in the response text.

    Multi-emit per Ship A §11.B.1 lock: LAST occurrence wins. The LLM's
    final emission is treated as the operative one (matches HARD STOP
    RULE 1's "your reply MUST end with the roll request" framing).

    Returns {'kind': str, 'skill_raw': str, 'multi_count': int} on match;
    None when no directive present.

    Caller passes skill_raw through orch.parse_skill_and_dc to extract DC.
    """
    if not response:
        return None
    matches = list(_LLM_EMIT_DIRECTIVE_RX.finditer(response))
    if not matches:
        return None
    m = matches[-1]
    return {
        'kind': m.group('kind').lower(),
        'skill_raw': m.group('skill_raw').strip(),
        'multi_count': len(matches),
    }


# Ship A live-verify patch (S36 #3): strip trailing DC integer from
# !check/!save patterns in response text BEFORE posting to Discord.
# Player sees `!check perception` (no DC); engine has the bound DC in
# the pending directive row via _parse_llm_emit_directive parse done
# earlier. Avrae silently ignores trailing integers per A.2 recon,
# so the strip doesn't change Avrae's behavior. Cast directives NOT
# stripped — Avrae's !cast accepts trailing integer as spell level
# override, so leaving cast alone preserves spell mechanics. Reverses
# locked decision 9 (Finding J retired) per operator pushback in S36.
_DC_STRIP_RX = re.compile(
    # Strips trailing DC integer from `!check skill DC` and `!save stat DC`.
    # S36 #5 patch: also handles the operator-locked
    # `**!check skill DC : <First Name>**` format — preserves the
    # `: <Name>` suffix and `**` bold-close markers in the player-facing
    # text while removing only the DC integer. Cast directives are NOT
    # stripped (Avrae's !cast takes trailing integer as spell level).
    r"(?P<head>!(?:check|save)\s+[^\n!:*]+?)"
    r"\s+\d+"                              # the DC integer (this is what gets stripped)
    r"(?P<tail>\s*(?::\s*[^\n!*]+?)?\s*(?:\*\*|(?=\n|$)))",
    re.IGNORECASE,
)


def _strip_dc_from_llm_emit(response: str) -> str:
    """Remove trailing DC integer from !check/!save directives in the
    response. Idempotent — applying to already-stripped text is a no-op.
    Cast directives unchanged. S36 #5 patch: preserves `: <Name>` suffix
    and `**` bold close markers; only strips the DC integer."""
    if not response:
        return response
    return _DC_STRIP_RX.sub(r"\g<head>\g<tail>", response)


def _wrong_skill_aside(expected_skill: str, actual_skill: str) -> str:
    """Ship A §13.3 — analog to _wrong_actor_aside. Posted to #dm-aside
    when matcher receives a roll whose actor matches but skill does NOT
    match the pending directive. Per locked decision 12 option (b), the
    pending directive row stays alive; wrong-skill roll falls through to
    normal player-input buffer flow."""
    return (
        f"Roll directive bound to {expected_skill} — "
        f"that {actual_skill} roll is not consumed. "
        f"Wait for a {expected_skill} roll, or revise the directive."
    )


def _is_dm_message(message, campaign) -> bool:
    """Sister of is_dm_or_creator() but for raw discord.Message events
    (on_message has no Interaction). Mirrors the same two-path check:
    manage_guild perm OR campaign.created_by_user_id match.

    `campaign` is the active campaign dict for this guild.
    """
    try:
        author = getattr(message, 'author', None)
        if author is None:
            return False
        guild_perms = getattr(author, 'guild_permissions', None)
        if guild_perms is not None and getattr(guild_perms, 'manage_guild', False):
            return True
        if not campaign:
            return False
        creator_id = (campaign.get('created_by_user_id') or '')
        return bool(creator_id and str(author.id) == creator_id)
    except Exception:
        return False


def _classify_unparsed_reason(action: str) -> str:
    """Best-effort reason classification for `directive_text_unparsed:`.

    Returns one of: trailing_args | shorthand | comment | other.
    Don't over-engineer — `other` is a fine fallback.
    """
    a = (action or '').lower()
    if '#' in a:
        return 'comment'
    if ' -' in a or a.endswith(' -'):
        return 'trailing_args'  # flag-shaped (e.g. -dc 15)
    # Trailing modifier word like "adv" / "dis"
    last_token = a.rsplit(' ', 1)[-1] if ' ' in a else ''
    if last_token in _DIRECTIVE_TRAILING_MODIFIER_TOKENS:
        return 'trailing_args'
    # `!c` shorthand isn't covered by the trigger prefixes (so we don't
    # see it here in practice), but if a future trigger ever extends to
    # `!c ` we want this branch to label it correctly.
    if a.startswith('!c ') and not a.startswith('!check '):
        return 'shorthand'
    return 'other'


def _parse_dm_directive(action: str) -> dict | None:
    """Parse a DM-authored !check/!save/!cast directive into structured
    form, or return None if the regex doesn't match.

    Returns: {'kind': 'check'|'save'|'cast', 'skill': str} on success.
    Caller is responsible for trailing-modifier rejection (handled in
    _handle_dm_roll_directive so the rejection paths can log distinctly).
    """
    m = _DM_DIRECTIVE_RX.match(action or '')
    if not m:
        return None
    kind = (m.group('kind') or '').lower().strip()
    skill = (m.group('skill') or '').strip()
    if not kind or not skill:
        return None
    return {'kind': kind, 'skill': skill}


def _directive_skill_is_clean(skill: str) -> tuple[bool, str | None]:
    """Validate a captured skill string is a bare skill name (no trailing
    flags, comments, or group keywords).

    Returns (clean, reason). reason is one of trailing_args | comment |
    group_directive | None (when clean=True).
    """
    s = (skill or '').strip()
    s_low = s.lower()
    if '#' in s:
        return False, 'comment'
    if s.startswith('-') or ' -' in s:
        return False, 'trailing_args'
    tokens = s_low.split()
    if any(t in _DIRECTIVE_TRAILING_MODIFIER_TOKENS for t in tokens):
        return False, 'trailing_args'
    for kw in _DIRECTIVE_GROUP_KEYWORDS:
        if kw in s_low:
            return False, 'group_directive'
    return True, None


def _normalize_skill_for_match(skill: str) -> str:
    """Lowercase + collapse whitespace. The matcher uses this on both
    the directive's stored skill and Avrae's _extract_detail() output
    so casing/spacing differences don't drop matches.

    Phase 1 does NOT include alias normalization (sneak↔stealth) — those
    misses are intentionally observable as TTL expirations in v1, and
    Phase 2 designs alias handling from the observed miss rate.
    """
    return ' '.join((skill or '').lower().split())


async def _post_dm_aside(guild, text: str) -> None:
    """Post a one-shot operational aside to #dm-aside. Soft-fail —
    aside posting must NEVER block the matcher path.
    """
    try:
        if guild is None:
            return
        ch = get_channel(guild, 'aside')
        if ch is None:
            log("dm_aside_post: #dm-aside channel not found")
            return
        await ch.send(text)
    except Exception as e:
        log(f"dm_aside_post: error={e!r}")


# Aside wording (locked in BUG_1_SPEC.md §K — operational tone, not error).
_NO_FOOTER_ASIDE = (
    "Roll directive not tracked: no active actor in footer yet. "
    "Address a player before issuing a directed check."
)


def _wrong_actor_aside(expected_actor: str, actual_actor: str) -> str:
    return (
        f"Roll directive bound to {expected_actor} — that roll is not "
        f"consumed. Wait for {expected_actor} to roll, or address "
        f"{actual_actor} first."
    )


async def _handle_dm_roll_directive(message, campaign, parsed: dict) -> None:
    """Phase 1 matcher — directive-emit branch. Telemetry + Ship 1 DC binding.

    Reads last_active_actor + scene mode, applies the skip cascade
    (combat → group → no-footer), emits a pending directive row when
    none of the skip conditions hold, and logs the appropriate telemetry
    line per BUG_1_SPEC.md §F.

    Ship 1 (S34) — parses an inline trailing DC ("!check perception 10" →
    dc=10) and stores it on the directive row. The DC is the binding
    surface for resolution at Avrae roll arrival
    (RESOLUTION_BINDING_SPEC.md §6).

    Soft-fail throughout: matcher errors must NEVER raise into on_message.
    """
    try:
        kind = parsed['kind']
        skill_raw = parsed['skill']
        campaign_id = campaign['id']

        # Ship 1 — split trailing DC integer off the captured skill text.
        # parse_skill_and_dc returns (bare_skill, dc | None); a missing DC
        # falls through to free-narration on roll arrival (§11.2 lock).
        skill, dc = orch.parse_skill_and_dc(skill_raw)

        # Skip-cascade gate 1: trailing-args / group-directive / comment.
        # Logs `directive_creation_skipped` with the classified reason
        # (or `directive_text_unparsed` for comment-shaped surface).
        # Run clean check against the BARE skill so 'perception 10' is
        # accepted (DC was already separated off above).
        clean, reason = _directive_skill_is_clean(skill)
        if not clean:
            if reason == 'group_directive':
                log(f"directive_creation_skipped: campaign={campaign_id} "
                    f"reason=group_directive")
                return
            # trailing_args / comment / other: log as unparsed text
            log(f"directive_text_unparsed: campaign={campaign_id} "
                f"raw={(message.content or '')!r} reason={reason}")
            return

        scene = get_scene_state(campaign_id)
        mode = (scene.get('mode') if scene else 'exploration') or 'exploration'

        # Skip-cascade gate 2: combat mode (Phase 1 explicitly excludes
        # combat-mode directive tracking — Phase 2 retunes if observed
        # play data shows it's needed).
        if mode == 'combat':
            log(f"directive_creation_skipped: campaign={campaign_id} "
                f"reason=combat_mode")
            return

        # Skip-cascade gate 3: no footer-actor yet (e.g. opening turn after
        # /play, before any player has spoken). Log + post operational
        # aside; do NOT create a row.
        footer_actor = (scene.get('last_active_actor') if scene else '') or ''
        footer_actor = footer_actor.strip()
        if not footer_actor:
            log(f"directive_creation_skipped_no_footer: campaign={campaign_id} "
                f"skill={skill} reason=no_active_actor")
            await _post_dm_aside(message.guild, _NO_FOOTER_ASIDE)
            return

        # Ship A live-verify patch (S36 #4): preserve Ship A's dc=N pending
        # row when a no-DC manual !check arrives for the same actor+skill.
        # Operator's natural pattern: bot emits "!check skill DC" → operator
        # types "!check skill" themselves to roll → previously this would
        # REPLACE the dc=N row with dc=None and break Ship A's resolution.
        # New rule: if existing row has dc=N AND new directive has no DC
        # AND actor+skill match, treat as manual roll completing the
        # auto-emit. Skip the upsert. Log for telemetry.
        if dc is None:
            existing = pending_directive_get_active(campaign_id)
            if existing is not None and existing.get('dc') is not None:
                existing_actor = (existing.get('actor_name') or '').strip()
                existing_skill = _normalize_skill_for_match(
                    existing.get('check_type', '')
                )
                new_skill_norm = _normalize_skill_for_match(skill)
                if (existing_actor == footer_actor
                        and existing_skill == new_skill_norm
                        and existing_skill):
                    log(f"directive_preserve_existing_dc: "
                        f"campaign={campaign_id} actor={footer_actor} "
                        f"skill={skill} existing_dc={existing['dc']}")
                    return

        # Emit / replace. Single-writer is pending_directive_upsert via
        # this matcher; the helper returns prior-row info so we can log
        # `pending_directive_replaced` before the swap.
        result = pending_directive_upsert(
            campaign_id=campaign_id,
            actor_name=footer_actor,
            check_type=skill,
            source_message_id=str(message.id),
            ttl_seconds=al.PENDING_DIRECTIVE_TTL_SECONDS,
            dc=dc,
        )
        if result.get('replaced') and result.get('prior'):
            prior = result['prior']
            old_age = pending_directive_age_seconds(prior.get('created_at') or '')
            log(f"pending_directive_replaced: campaign={campaign_id} "
                f"old_actor={prior.get('actor_name', '')} "
                f"old_skill={prior.get('check_type', '')} "
                f"new_actor={footer_actor} new_skill={skill} "
                f"old_age_s={old_age}")

        # Bind log fires with directive_age_s=0 by definition (just emitted).
        # Ship 1 extends the line with dc=<N|none> so the directive-emit
        # surface carries the binding-or-not signal forward.
        dc_str = str(dc) if dc is not None else 'none'
        log(f"directive_bound_to_footer_actor: campaign={campaign_id} "
            f"actor={footer_actor} skill={skill} dc={dc_str} "
            f"directive_age_s=0")
    except Exception as e:
        log(f"_handle_dm_roll_directive error: {e!r}")


def _handle_dm_roll_arrival(campaign_id: int, event: dict) -> dict:
    """Phase 1 matcher — Avrae roll-arrival branch.

    Sync helper (called from inside the existing on_message Avrae branch).
    Returns a dict {'aside': None | str, 'auto_fire': None | dict}. The
    async caller posts any aside text and schedules any auto-fire payload
    (Ship 1 §9 wiring).

    Ship 1 (S34) — when the match path runs, calls `resolve_directive`
    against the pending row + Avrae event to produce a ResolutionResult.
    Non-None resolutions are returned in the `auto_fire` payload so the
    caller can schedule `_dm_respond_and_post` with the resolution_result
    kwarg. None resolutions (no-DC, cast kind, malformed embed) preserve
    Phase 1 telemetry-only behavior.
    """
    out: dict = {'aside': None, 'auto_fire': None}

    # Defensive: only check/save/cast events are matched against pending
    # directives. Attack/damage/rest/roll silent-ignore in Phase 1.
    kind = (event.get('kind') or '').lower()
    if kind not in ('check', 'save', 'cast'):
        return out

    pending = pending_directive_get_active(campaign_id)
    if not pending:
        return out

    avrae_skill = _normalize_skill_for_match(event.get('detail') or '')
    pending_skill = _normalize_skill_for_match(pending.get('check_type') or '')
    if not avrae_skill or not pending_skill or avrae_skill != pending_skill:
        # Ship A §13 (decision 12, option b) — skill mismatch now fires
        # log + aside instead of silent-ignore. Pending directive row
        # stays alive (no consume call); wrong-skill roll falls through
        # to normal player-input buffer flow per Track 7 #1. Pre-Ship-A
        # behavior was silent-ignore.
        if avrae_skill and pending_skill:
            # Both present but mismatched — surface the friction.
            log(f"directive_skill_mismatch: campaign={campaign_id} "
                f"expected_skill={pending.get('check_type', '')} "
                f"actual_skill={event.get('detail', '')} "
                f"actor={event.get('actor', '')}")
            out['aside'] = _wrong_skill_aside(
                expected_skill=pending.get('check_type', ''),
                actual_skill=event.get('detail', ''),
            )
        # If avrae_skill or pending_skill is empty/None, fall through
        # silently — that's the malformed-embed defensive case.
        return out

    avrae_actor = canonicalize_actor_name(event.get('actor') or '')
    pending_actor = canonicalize_actor_name(pending.get('actor_name') or '')

    age_s = pending_directive_age_seconds(pending.get('created_at') or '')

    if avrae_actor == pending_actor and avrae_actor:
        # Ship 1 (S34) — compute resolution before consume so the matcher
        # has both the pending row (with dc) and the avrae event surface.
        # Soft-fail per §9.5: any resolve error is logged + degrades to
        # telemetry-only; row still consumes; no auto-fire.
        resolution = None
        resolve_err = None
        # Ship A (S36) — plumb scene_state + active_turn + combatants +
        # active_quests through to resolve_directive so texture is computed
        # at consume time. Soft-fail on any state-read failure: degrade to
        # Ship-1-shape resolution (texture=None) rather than failing the
        # whole matcher.
        _scene_state = None
        _active_turn = None
        _combatants_list = None
        _active_quests = None
        try:
            _scene_state = get_scene_state(campaign_id)
            _active_turn = get_active_turn(campaign_id)
            _combatants_payload = get_combatants(campaign_id) or {}
            _combatants_list = _combatants_payload.get('combatants') or []
            _active_quests = get_active_quests(campaign_id) or []
        except Exception as e:
            log(f"resolve_state_read error: campaign={campaign_id} err={e!r}")
        try:
            resolution = orch.resolve_directive(
                pending, event,
                scene_state=_scene_state,
                active_turn=_active_turn,
                active_quests=_active_quests,
                combatants=_combatants_list,
            )
        except Exception as e:
            resolve_err = repr(e)
            log(f"resolve_directive_error: campaign={campaign_id} "
                f"actor={pending.get('actor_name', '')} "
                f"skill={pending.get('check_type', '')} err={resolve_err}")

        # Always-fire empirical-baseline log per §10.2 / §10.3.
        if resolution is not None:
            log(orch.resolution_log_summary(resolution, campaign_id))
            # Ship A §5.5 — stakes_tier telemetry when texture fired.
            if resolution.texture is not None:
                log(orch.stakes_tier_log_summary(
                    resolution.texture.stakes_signals,
                    resolution.texture.stakes_tier,
                ))
            outcome_str = 'PASSED' if resolution.passed else 'FAILED'
            roll_total_str = str(resolution.roll_total)
            dc_str = str(resolution.dc)
        else:
            # Determine skip reason for the empirical baseline.
            if resolve_err is not None:
                skip_reason = 'unresolvable'
            elif kind == 'cast':
                skip_reason = 'cast_kind'
            elif pending.get('dc') is None:
                skip_reason = 'no_dc'
            elif not isinstance(event.get('result'), int):
                skip_reason = 'malformed_embed'
            else:
                skip_reason = 'unresolvable'
            log(orch.resolution_log_summary(
                None, campaign_id, reason=skip_reason
            ))
            outcome_str = 'skipped'
            roll_total = event.get('result')
            roll_total_str = (str(roll_total) if isinstance(roll_total, int)
                              else 'none')
            pdc = pending.get('dc')
            dc_str = str(pdc) if isinstance(pdc, int) else 'none'

            # Ship A live-verify patch (S36 #9): when the LLM emitted a
            # directive without a DC, surface a #dm-aside so the operator
            # knows resolution skipped and the outcome will be free-narrated
            # on their next turn. Only fires for no_dc (the operator-actionable
            # case); cast_kind / malformed_embed / unresolvable stay log-only
            # since those are either deferred-by-design or defensive.
            if skip_reason == 'no_dc':
                out['aside'] = (
                    f"Bot's roll request had no DC — resolution skipped. "
                    f"The outcome will be free-narrated on your next "
                    f"action (no engine-bound pass/fail this turn). "
                    f"Skill: {pending.get('check_type', '')}."
                )

        # Phase 1 would-fire log, Ship 1 extension (§10.1): adds roll_total,
        # dc, outcome fields. Log line NAME preserved per spec — the
        # Bug 1 Phase 2 criterion 4 grep cross-references the same name.
        log(f"directive_would_fire_dm_respond: campaign={campaign_id} "
            f"actor={pending.get('actor_name', '')} "
            f"skill={pending.get('check_type', '')} "
            f"directive_age_s={age_s} "
            f"roll_total={roll_total_str} "
            f"dc={dc_str} "
            f"outcome={outcome_str}")

        pending_directive_consume(campaign_id)

        if resolution is not None:
            # Ship 1 (§9.3) — synthesized bracket-framed input gives the LLM
            # narrative grounding (actor, skill, kind) without re-asserting an
            # unbound action (avoiding F-45 surface). AUTHORITATIVE-CANON
            # block at top-of-prompt does the actual binding work.
            synthesized_input = (
                f"[Roll resolution: {resolution.actor} rolled "
                f"{resolution.skill_or_save} ({resolution.check_kind}); "
                f"outcome bound at top-of-prompt.]"
            )
            controller_id = _resolve_bound_controller_id(
                campaign_id, resolution.actor
            )
            synthesized_actions = [
                (resolution.actor, synthesized_input, controller_id)
            ]
            out['auto_fire'] = {
                'campaign_id': campaign_id,
                'actions': synthesized_actions,
                'combined_action': synthesized_input,
                'resolution': resolution,
            }
        return out

    # Skill match + actor mismatch → log + aside, do NOT consume.
    log(f"directive_actor_mismatch: campaign={campaign_id} "
        f"expected_actor={pending.get('actor_name', '')} "
        f"actual_actor={event.get('actor', '')} "
        f"skill={pending.get('check_type', '')}")
    out['aside'] = _wrong_actor_aside(
        expected_actor=pending.get('actor_name', ''),
        actual_actor=event.get('actor', ''),
    )
    return out


def _resolve_bound_controller_id(campaign_id: int, actor_name: str) -> str | None:
    """Ship 1 (§9.4) — best-effort lookup of the Discord user ID controlling
    a bound PC. Falls through to None when sheet/binding is missing. Soft-fail
    only: this is informational metadata for downstream persistence-directive
    typing-identity comparison (irrelevant in exploration mode where Ship 1
    resolution fires)."""
    try:
        chars = get_characters(campaign_id) or []
        target = (actor_name or '').strip().lower()
        for c in chars:
            if (c.get('name') or '').strip().lower() == target:
                cid = c.get('controller')
                return str(cid) if cid else None
    except Exception as e:
        log(f"_resolve_bound_controller_id error: {e!r}")
    return None

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
    turn  → set active turn controller (2A.2). On round transition
            (round_num > prior_round), fire S43 ROUND_START narration trigger.
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
            # Ship S45-F: snapshot combat state BEFORE mechanical cleanup
            # so the COMBAT_END dispatch (below) has the closing roster.
            # The dispatch fires AFTER cleanup but uses these snapshots
            # via override params so the directive's mode gate + roster
            # build both succeed even though DB state has flipped.
            pre_clear_combat_state = get_combatants(campaign['id'])

            set_scene_mode(campaign['id'], 'exploration')
            clear_active_turn(campaign['id'])
            clear_combatants(campaign['id'])
            # Ship S45 — reset narrative buffers at combat→exploration
            # boundary. Mechanical cleanup above doesn't touch the three
            # rolling narrative buffers (current_scene, last_dm_response,
            # last_player_action) which otherwise leak combat-specific
            # framing into the next exploration message and drive
            # post-combat drift (S44 follow-up diagnosis).
            #
            # Ordering note: buffer reset establishes a clean synthesized
            # fallback. If the COMBAT_END dispatch below succeeds, its LLM
            # closeout narration will overwrite the synthesized text in
            # current_scene (richer atmospheric resolution for the next
            # exploration turn's context). If dispatch fails (LLM timeout,
            # no combatants, etc.), the synthesized reset stands as the
            # fallback. Either way, no stale combat narration survives the
            # boundary.
            reset_narrative_buffers_on_combat_exit(campaign['id'])
            log(f"init: combat ended (guild={message.guild.id}) → mode='exploration', combat state cleared")

            # Ship S45-F: COMBAT_END auto-closeout narration. Closes the
            # silence-until-player-types gap the operator flagged in S45
            # verify ("not plausible that we wait for a structured sentence
            # before dm responds to init end"). Fires the same dispatch
            # surface as ROUND_START/BLOODIED/DOWNED with full S43
            # instruction-side + S44 information-side enforcement; the
            # directive's roster shows the closing combatant state with
            # categorical HP labels and the MUST/MUST-NOT clauses prevent
            # post-combat speculation. Soft-fails per §59 — combat narration
            # never blocks mechanical state.
            await _dispatch_combat_narration(
                campaign,
                {'kind': 'COMBAT_END'},
                combat_state_override=pre_clear_combat_state,
                scene_override={'mode': 'combat'},
            )
        elif evt_type == 'turn':
            controller_id = init_evt.get('controller_id')
            name = init_evt.get('name', '')
            round_num = init_evt.get('round', 0)
            # Ship S43 — detect round transition for ROUND_START trigger.
            # Compare against prior active_turn's round BEFORE overwriting.
            prior_turn = get_active_turn(campaign['id'])
            prior_round = (prior_turn or {}).get('round') or 0
            if controller_id and name:
                set_active_turn(campaign['id'], str(controller_id), name, round_num)
            # ROUND_START fires when round_num strictly increases (covers
            # round 1 from round 0 init-begin OR round N from round N-1).
            # Only when mode='combat' (gate per spec §1).
            if (current_mode == 'combat' and isinstance(round_num, int)
                    and round_num > prior_round and round_num > 0):
                await _dispatch_combat_narration(
                    campaign,
                    {'kind': 'ROUND_START', 'round': round_num},
                )
    except Exception as e:
        log(f"_handle_init_event error: {e}")


async def _dispatch_combat_narration(campaign, trigger_event,
                                      combat_state_override=None,
                                      scene_override=None):
    """Fire one combat-narration auto-post via _dm_respond_and_post.

    Ship S43 dumb-combat dispatcher. Gates on scene_state.mode='combat'.
    Computes the directive via orch.compute_combat_narration_directive
    (pure function); empty action+context return signals the trigger
    should be silently skipped (mode-gate fail, unsupported trigger, etc.).

    Soft-fail on every error — combat narration must NEVER block the
    underlying Avrae event flow. Mechanical state is Avrae's; narration
    is a render-side enhancement.

    Ship S45-F: optional `combat_state_override` and `scene_override`
    decouple dispatch from current DB state. Used by COMBAT_END dispatch
    which fires AFTER mechanical cleanup (clear_combatants + mode flip)
    has already run. Override params let the caller snapshot pre-clear
    combat state + simulate mode='combat' for the directive's gate while
    the DB already reflects the post-combat state. Both override params
    default to None → fall back to current DB state (S43/S44 behavior
    unchanged).
    """
    try:
        scene = (scene_override if scene_override is not None
                 else get_scene_state(campaign['id']))
        combat_state = (combat_state_override if combat_state_override is not None
                        else get_combatants(campaign['id']))
        action, transition_context = orch.compute_combat_narration_directive(
            trigger_event, combat_state, scene,
        )
        if not action or not transition_context:
            log(orch.combat_narration_log_summary(
                trigger_event, fired=False, reason='mode_gate_or_empty',
            ))
            return
        # Build a synthetic action tuple — actor='Combat', no user_id (None).
        # _dm_respond_and_post tolerates 1-tuple and 3-tuple shapes.
        # Ship S44: pass suppress_for_combat_narration=True so build_dm_context
        # drops the chroma retrieval block (=== RELEVANT PAST EVENTS ===) and
        # the `Recently active NPCs:` line — both surfaced as storytelling
        # drift sources in S43's ROUND_START verify. The combat narration
        # directive (transition_context above) carries the authoritative
        # roster; chroma + recent_npcs duplicate and confuse the context.
        # §77 doctrine line (atmospheric vs adjudication) is unaffected;
        # this is the information-side enforcement layer complementing the
        # instruction-side MUST/MUST-NOT clauses in _COMBAT_NARRATION_INVARIANTS.
        characters = get_characters(campaign['id']) or []
        await _dm_respond_and_post(
            campaign,
            characters,
            [('Combat', action, None)],
            action,
            transition_context=transition_context,
            suppress_for_combat_narration=True,
        )
        log(orch.combat_narration_log_summary(trigger_event, fired=True))
    except Exception as e:
        log(f"_dispatch_combat_narration error: trigger={trigger_event!r} "
            f"err={e!r}")


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


# ─────────────────────────────────────────────────────────
# Ship 3 (S41) — NPC State-Sync suggester (§1b second instance)
# ─────────────────────────────────────────────────────────
# **Avrae bot-filter HALT-and-pivot (S41 verify pass, May 11, 2026):** the
# originally-locked architectural shape (bot-emit `!init opt` commands
# directly to #dm-narration, §65a narrow exception) was empirically blocked
# by Avrae's API. Identical commands mutate state when human-typed and are
# silently filtered when bot-typed. Documented as structural API boundary
# in NPC_STATE_SYNC_SPEC.md §13.
#
# Pivot per operator decision: convert from bot-WRITER to bot-SUGGESTER
# following the Track 6 #5.1 `_post_srd_suggestion` precedent. Bot posts a
# copy-paste command block to #dm-aside; DM pastes; Avrae accepts. This
# IS Doctrine §1b's second project instance (first: SRD suggestion hook,
# S26). §65 holds in its original form — no amendment needed.
#
# Called from two disjoint trigger surfaces (same call sites as the
# prior writer shape — only the helper's internal behavior changed):
#   - /hydrate slash command (trigger='hydrate', Case A)
#   - _handle_init_list_event hydration branch (trigger='init_list', Case B)
#
# Locked command syntax (per S41 D1 verify pass; the syntax is now suggested
# to the DM rather than emitted by the bot):
#   `!init opt <name> -hp <N>` sets max HP (NOT `-h` — that's Avrae's
#   hidden-toggle shorthand; the verify pass surfaced this when bot-emitted
#   `-h 13` silently hid the combatant instead of setting HP).
#   `!init opt <name> -ac <N>` sets AC.
#   Each command must be pasted as a separate Discord message — Avrae's
#   parser cannot consume back-to-back commands in one code block.
#
# Sub-D2 case split survives the pivot — only the aside text changes:
#   Case A (active /hydrate, combatant has numeric HP in Avrae): suggester
#     posts a WARNING aside with the command sequence; DM sees HP-reset
#     risk explicitly before pasting.
#   Case B (passive init_list trigger, combatant has numeric HP):
#     suggester NO-OPs silently. Avrae's mid-combat HP authoritative.

async def _avrae_project_npc(channel, campaign_id: int, npc_name: str,
                              trigger: str) -> tuple[bool, dict]:
    """Suggest the Avrae command sequence the DM needs to paste to sync
    a hydrated NPC's stats. §1b validated-suggester pattern.

    Reads dnd_npcs canonical state, queries dnd_combatant_state for current
    Avrae mirror, posts a copy-paste suggestion to #dm-aside if projection
    would be useful (and safe). DM pastes the commands manually; Avrae
    accepts (responds to human-typed commands, filters bot-typed).

    Args:
        channel: discord channel object — used only for guild lookup to
            resolve #dm-aside. The suggestion is posted to #dm-aside, not
            this channel.
        campaign_id: campaign id.
        npc_name: canonical NPC name (must match dnd_combatant_state.name).
        trigger: 'hydrate' or 'init_list' — determines Case A vs Case B
            behavior on mid-combat re-suggestion.

    Returns:
        (acted, signals): acted=True when a suggestion was posted;
        signals['reason'] is one of:
          'suggested' | 'suggested_with_warning' | 'noop_complete' |
          'gate_not_in_init' | 'gate_engine_missing' |
          'gate_engine_stats_null' | 'aside_post_failed'

    The function name is preserved from the pre-pivot bot-writer shape to
    minimize call-site churn; the behavior is suggester-pattern per S41
    Avrae bot-filter HALT-and-pivot.
    """
    # 1. Engine state — must have NPC row with non-NULL hp_max + ac
    npc = npc_get_by_name(campaign_id, npc_name)
    if npc is None:
        log(f"avrae_projection_skipped: campaign={campaign_id} "
            f"npc='{npc_name}' trigger={trigger} reason=gate_engine_missing")
        return (False, {'reason': 'gate_engine_missing'})

    hp_max = npc.get('hp_max')
    ac = npc.get('ac')
    if hp_max is None or ac is None:
        log(f"avrae_projection_skipped: campaign={campaign_id} "
            f"npc='{npc_name}' trigger={trigger} reason=gate_engine_stats_null "
            f"hp_max={hp_max} ac={ac}")
        return (False, {'reason': 'gate_engine_stats_null'})

    # 2. Combatant state — NPC must be currently in init (Avrae has a row)
    snapshot = get_combatants(campaign_id)
    target = None
    npc_name_lower = npc_name.lower()
    for c in (snapshot or {}).get('combatants', []):
        if (c.get('name') or '').lower() == npc_name_lower:
            target = c
            break

    if target is None:
        log(f"avrae_projection_skipped: campaign={campaign_id} "
            f"npc='{npc_name}' trigger={trigger} reason=gate_not_in_init")
        return (False, {'reason': 'gate_not_in_init'})

    # 3. Resolve #dm-aside (suggestion destination)
    aside_ch = discord.utils.get(channel.guild.text_channels, name='dm-aside')
    if aside_ch is None:
        log(f"avrae_projection_failed: campaign={campaign_id} "
            f"npc='{npc_name}' trigger={trigger} reason=aside_channel_missing")
        return (False, {'reason': 'aside_post_failed',
                        'error': 'dm-aside channel not found'})

    # Engine init_mod for the `!init add <modifier> <name>` rebuild syntax.
    # Defaults to 0 if NULL (every hydration source fills it from CR band,
    # so NULL is the missing-engine-state case which gate_engine_stats_null
    # should have caught — defensive fallback only).
    init_mod = npc.get('init_mod') or 0

    # Locked command syntax per S41 second verify pass (operator-confirmed):
    # `-hp <N>` works at both `!init add` (sets max=current=N initially)
    # AND `!init opt` (sets current HP). The earlier hypothesized `-h` flag
    # was Avrae's hidden-toggle — applying it at !init add produced <Very
    # Dead> (max=0 combatant) on every test. `-ac <N>` works at `!init opt`
    # (live-verified set AC from 0 to 13). Combined `!init add ... -hp X
    # -ac Y` not validated; the 3-line sequence below uses only verified
    # flag-subcommand pairs to guarantee correct behavior.
    rebuild_add_cmd = f"!init add {init_mod} {npc_name} -hp {hp_max}"
    rebuild_ac_cmd = f"!init opt {npc_name} -ac {ac}"
    rebuild_seq = [
        f"!init remove {npc_name}",
        rebuild_add_cmd,
        rebuild_ac_cmd,
    ]

    # 4. Case A / Case B idempotency split
    avrae_has_numeric_hp = target.get('hp_max') is not None
    if avrae_has_numeric_hp:
        if trigger == 'init_list':
            # Case B: passive trigger; don't second-guess Avrae's mid-combat HP.
            # No suggestion posted — Avrae state is the authoritative read.
            log(f"avrae_projection_skipped: campaign={campaign_id} "
                f"npc='{npc_name}' trigger={trigger} reason=noop_complete "
                f"avrae_hp_max={target.get('hp_max')}")
            return (False, {'reason': 'noop_complete'})
        # Case A: active /hydrate mid-combat. Post suggestion WITH warning.
        # Clean fix is remove + re-add (loses mid-combat state); partial fix
        # via opt-only leaves max-HP wrong but preserves combat state.
        body = (
            f"⚠️ **Mid-combat `/hydrate` for `{npc_name}`** "
            f"(engine: HP {hp_max}, AC {ac})\n"
            f"Avrae's `!init opt` cannot set max-HP, so a clean sync needs "
            f"remove + re-add — **this will lose `{npc_name}`'s current "
            f"HP / conditions / init position**. Paste each line separately "
            f"(Avrae filters batched commands):\n"
            f"```\n{rebuild_seq[0]}\n```"
            f"```\n{rebuild_seq[1]}\n```"
            f"```\n{rebuild_seq[2]}\n```"
            f"*Or partial fix (preserves combat state, leaves max-HP wrong): "
            f"`!init opt {npc_name} -hp {hp_max}` then "
            f"`!init opt {npc_name} -ac {ac}`.*"
        )
        try:
            await aside_ch.send(body)
        except Exception as e:
            log(f"avrae_projection_failed: campaign={campaign_id} "
                f"npc='{npc_name}' trigger={trigger} reason=aside_post_failed "
                f"error={e!r}")
            return (False, {'reason': 'aside_post_failed', 'error': repr(e)})
        log(f"avrae_projection_succeeded: campaign={campaign_id} "
            f"npc='{npc_name}' trigger={trigger} reason=suggested_with_warning "
            f"hp={hp_max} ac={ac}")
        return (True, {
            'reason': 'suggested_with_warning',
            'hp': hp_max,
            'ac': ac,
            'commands_suggested': rebuild_seq,
        })

    # 5. Happy path: post the canonical remove + re-add + AC-opt suggestion.
    # Avrae's `!init opt` doesn't set max-HP, so `!init opt -hp 13` would
    # produce `<13/0>` (current=13, max=0) which breaks bloodied/death-save
    # calculations. The clean fix is remove + re-add with `-hp` (sets both
    # current AND max at add-time) followed by `!init opt -ac` (the only
    # subcommand that accepts -ac). Combatant has <None> status (no
    # mid-combat state to lose) — this is a clean three-step operation.
    body = (
        f"🔧 **Sync `{npc_name}` to Avrae** (HP {hp_max}, AC {ac}). "
        f"`!init opt` can't set max-HP, so the clean fix is remove + re-add "
        f"with `-hp`, then set AC via `!init opt`. Paste each line as a "
        f"separate message (Avrae filters back-to-back commands):\n"
        f"```\n{rebuild_seq[0]}\n```"
        f"```\n{rebuild_seq[1]}\n```"
        f"```\n{rebuild_seq[2]}\n```"
    )
    log(f"avrae_projection_attempted: campaign={campaign_id} "
        f"npc='{npc_name}' trigger={trigger} commands={len(rebuild_seq)}")
    try:
        await aside_ch.send(body)
    except Exception as e:
        log(f"avrae_projection_failed: campaign={campaign_id} "
            f"npc='{npc_name}' trigger={trigger} reason=aside_post_failed "
            f"error={e!r}")
        return (False, {'reason': 'aside_post_failed', 'error': repr(e)})
    log(f"avrae_projection_succeeded: campaign={campaign_id} "
        f"npc='{npc_name}' trigger={trigger} reason=suggested hp={hp_max} "
        f"ac={ac} commands={len(rebuild_seq)}")
    return (True, {
        'reason': 'suggested',
        'hp': hp_max,
        'ac': ac,
        'commands_suggested': rebuild_seq,
    })


async def _handle_init_list_event(message, parsed):
    """Map an Avrae `!init list` snapshot onto dnd_combatant_state.

    parsed is the output of avrae_listener.parse_init_list_embed — a full
    per-combatant snapshot. Pure mechanical mapping, no LLM. Replace-in-place
    via update_combatants_from_init_list, so each new snapshot supersedes the
    prior one for this campaign.

    Ship S43 (dumb combat): snapshot prior combatant state BEFORE the write,
    diff after, fire BLOODIED_THRESHOLD_CROSSED + COMBATANT_DOWNED triggers
    when in mode='combat'. Mode-gate is at the dispatcher; this surface
    always snapshots so future ships have the diff signal available.
    """
    try:
        if not message.guild:
            return
        campaign = get_active_campaign(str(message.guild.id))
        if not campaign:
            return
        combatants = parsed.get('combatants') or []
        # S43 — capture prior combatant snapshot for HP-transition diff
        # BEFORE the engine update wipes/re-inserts the table.
        prior_snapshot = get_combatants(campaign['id']) or {}
        prior_combatants_list = prior_snapshot.get('combatants') or []
        scene_for_mode = get_scene_state(campaign['id']) or {}
        scene_mode = (scene_for_mode.get('mode') or 'exploration').lower()
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
                # Ship 3 (S41): even on source=miss the engine row may be
                # stat-complete but Avrae's combatant still <None>. Fire the
                # projection writer to bring Avrae into line. The writer's
                # Case B guard absorbs the case where Avrae is already in sync.
                await _avrae_project_npc(
                    message.channel, campaign_id, cbt_name, trigger='init_list'
                )
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
            # Ship 3 (S41): post-hydration projection. trigger='init_list' (Case B).
            # Writer's idempotency absorbs already-synced + skips on numeric HP.
            await _avrae_project_npc(
                message.channel, campaign_id, cbt_name, trigger='init_list'
            )

        log(
            f"init_list_parsed: campaign={campaign['id']} "
            f"round={parsed.get('round')} "
            f"current_init={parsed.get('current_init')} "
            f"combatants={n} "
            f"hp_present={1 if hp_present else 0} "
            f"conditions_present={1 if conditions_present else 0}"
        )
        # Ship S43 (dumb combat) — compute HP-state transitions vs prior
        # snapshot; fire BLOODIED_THRESHOLD_CROSSED + COMBATANT_DOWNED
        # narration triggers when in mode='combat'. Mode gate at dispatcher;
        # the diff itself runs unconditionally so future ships have signal.
        if scene_mode == 'combat':
            try:
                transitions = orch.compute_combat_state_transitions(
                    prior_combatants_list, combatants,
                )
                for trigger in transitions:
                    await _dispatch_combat_narration(campaign, trigger)
            except Exception as e:
                log(f"_handle_init_list_event combat_narration "
                    f"dispatch error: {e!r}")
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
    """Catches Avrae message edits as state-transition signals AND DM
    directive edits as cancellation signals (Bug 1 Phase 1, S32).

    Avrae path: Avrae edits the 'Are you sure you want to end combat?'
    message in place to 'End of combat report: ...' when the DM confirms
    !init end. No new message is sent, so on_message never fires.
    We treat the edit as a state transition and re-run the init parser.

    DM directive path: when the DM edits a message that holds a pending
    roll directive, re-parse the new content. If the new content no
    longer matches the same kind+skill, cancel the directive.
    """
    if al.is_avrae(after):
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
        return

    # Bug 1 Phase 1 — DM directive edit-cancel path. Only checks
    # messages in #dm-narration; other channels never carry directives.
    # Soft-fail throughout — edit handling must never raise.
    try:
        guild = getattr(after, 'guild', None)
        channel = getattr(after, 'channel', None)
        if guild is None or channel is None:
            return
        if getattr(channel, 'name', '') != CHANNEL_NAMES['narration']:
            return
        campaign = get_active_campaign(str(guild.id))
        if not campaign:
            return
        if not _is_dm_message(after, campaign):
            return
        # Look up the pending directive for this campaign and check whether
        # this edit's source message is the one that issued it.
        pending = pending_directive_get_active(campaign['id'])
        if not pending or str(pending.get('source_message_id', '')) != str(after.id):
            return
        new_text = (getattr(after, 'content', '') or '').strip()
        new_low = new_text.lower()
        new_parsed = None
        if new_low.startswith(_DIRECTIVE_TRIGGER_PREFIXES):
            new_parsed = _parse_dm_directive(new_text)
        # Same kind+skill after edit → no-op (typo fix or cosmetic
        # whitespace change). Otherwise cancel + log.
        same_skill = False
        if new_parsed:
            new_skill_norm = _normalize_skill_for_match(new_parsed.get('skill', ''))
            old_skill_norm = _normalize_skill_for_match(pending.get('check_type', ''))
            same_skill = bool(new_skill_norm) and (new_skill_norm == old_skill_norm)
        if not same_skill:
            removed = pending_directive_delete_by_message(
                campaign['id'], str(after.id)
            )
            if removed is not None:
                log(f"pending_directive_cancelled: campaign={campaign['id']} "
                    f"reason=edit")
    except Exception as e:
        log(f"on_message_edit dm-directive handler error: {e!r}")


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
                # Bug 1 Phase 1 (S32) + Ship 1 (S34) — match this roll
                # against any pending DM directive for the campaign. Phase 1
                # consumed the row and logged telemetry; Ship 1 additionally
                # resolves DC-vs-roll and auto-fires _dm_respond_and_post
                # with the bound ResolutionResult when a DC was present.
                # Soft-fail end-to-end: matcher errors must NEVER raise into
                # on_message. _dm_respond_and_post failure falls through to
                # the deterministic fallback aside per §11.11.
                try:
                    if event.get('kind') in ('check', 'save', 'cast') and message.guild:
                        arrival_camp = get_active_campaign(str(message.guild.id))
                        if arrival_camp:
                            arrival = _handle_dm_roll_arrival(arrival_camp['id'], event)
                            if arrival and arrival.get('aside'):
                                await _post_dm_aside(message.guild, arrival['aside'])
                            if arrival and arrival.get('auto_fire'):
                                asyncio.create_task(
                                    _fire_resolution_narration(
                                        arrival_camp, arrival['auto_fire'],
                                        message.guild,
                                    )
                                )
                except Exception as e:
                    log(f"_handle_dm_roll_arrival outer error: {e!r}")
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

    # Bug 1 Phase 1 (S32) — DM roll directive parsing in #dm-narration.
    # Branches BEFORE the no-bound-char gate so the DM (who typically
    # isn't a bound player) doesn't get the bound-char error reply on
    # directive emission. Only fires when the author is the DM/creator
    # AND the text starts with `!check ` / `!save ` / `!cast `. Anything
    # else falls through to the existing flow unchanged.
    _action_text = (message.content or '').strip()
    _action_low = _action_text.lower()
    if _is_dm_message(message, campaign) and _action_low.startswith(_DIRECTIVE_TRIGGER_PREFIXES):
        parsed = _parse_dm_directive(_action_text)
        if parsed:
            await _handle_dm_roll_directive(message, campaign, parsed)
        else:
            # Directive prefix matched but bare-skill regex failed
            # (trailing args, comment, malformed). Log so Phase 2 can
            # calibrate alias / variant handling from the miss surface.
            log(f"directive_text_unparsed: campaign={campaign['id']} "
                f"raw={_action_text!r} "
                f"reason={_classify_unparsed_reason(_action_text)}")
        return  # Don't fall through — Avrae owns the !-prefix response.

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
    # bail.
    #
    # Ship S45-D v2 (extended init-setup gate): when mode='combat' but no
    # active turn has been set yet (Avrae fired !init begin + adds/joins
    # but the first !init next hasn't cycled), the bot must STAY SILENT.
    # Init-setup is structurally a window where narration is premature —
    # Avrae owns this window. Any player input here is either Avrae
    # disambiguation (e.g. bare number to pick a monster source) or
    # premature RP; either way, narration is wrong.
    #
    # Prior v1 (suppress_for_combat_narration auto-applied in
    # _dm_respond_and_post) closed the phantom-companion leak but the LLM
    # still generated combat narration from bare inputs like "2". v2 gates
    # at the on_message level — bot reacts ⏳ and returns. ROUND_START
    # dispatch will fire when Avrae announces the first turn, providing
    # the proper atmospheric opener.
    scene = get_scene_state(campaign['id'])
    if scene and (scene.get('mode') or 'exploration') == 'combat':
        active = get_active_turn(campaign['id'])
        if not active:
            # Init-setup window — combat mode set, no turn cycled yet.
            try:
                await message.add_reaction('⏳')
            except Exception:
                pass
            log(f"init_setup_gate: dropped msg from {message.author.id} "
                f"(mode=combat, no active_turn — Avrae setup phase)")
            return
        if str(active['controller_id']) != str(message.author.id):
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
                                location_label_override: str = None,
                                resolution_result=None,
                                suppress_for_combat_narration: bool = False):
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

        # Ship S45-D v1: init-setup defense-in-depth suppression. When
        # mode='combat' but no active_turn has been set yet (Avrae !init
        # begin + adds/joins phase before !init next), the bot is
        # structurally NOT in a position to render full exploration
        # context.
        #
        # v2 (the primary gate) lives in `on_message` and prevents player
        # messages from reaching `_dm_respond_and_post` at all during this
        # window — bot stays silent. This v1 gate remains as defense-in-
        # depth for non-`on_message` call sites (slash commands,
        # `_handle_dm_roll_arrival` auto-fire, /travel, etc.) where the
        # top-level gate doesn't apply. Same suppression set as S44
        # dispatch path (10 blocks): keeps the bot responsive (it still
        # replies) but structurally clean (no phantom NPC leak).
        #
        # Doctrine candidate (3rd instance of two-layer enforcement): mode
        # transitions are state-reset surfaces; the init-setup window is a
        # transitional state where the mode flag has flipped but mechanical
        # state isn't fully populated yet, and the bot must structurally
        # narrow its context accordingly.
        try:
            scene_for_setup_gate = get_scene_state(campaign['id'])
            if (scene_for_setup_gate
                    and (scene_for_setup_gate.get('mode') or '').lower() == 'combat'):
                active_turn_for_setup_gate = get_active_turn(campaign['id'])
                if not active_turn_for_setup_gate:
                    if not suppress_for_combat_narration:
                        log(f"init_setup_suppression: campaign={campaign['id']} "
                            f"applied=1 (mode=combat, no active_turn)")
                    suppress_for_combat_narration = True
        except Exception as e:
            log(f"init_setup_suppression: scene gate error: {e!r}")

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

        # Bug 1 Phase 1 (S32) — exploration-mode footer-actor write.
        # First actor in the batch is the canonical "footer actor" for
        # this turn (mirrors the persistence directive's first-actor pick).
        # Stored as display form so the journal stays human-readable; the
        # matcher canonicalizes both sides at compare time.
        # Soft-fail: footer-actor bookkeeping must never block narration.
        try:
            primary_actor = actor_names_display[0] if actor_names_display else ''
            update_last_active_actor(campaign['id'], primary_actor, 'dm_respond')
        except Exception as e:
            log(f"update_last_active_actor failed (_dm_respond_and_post): {e!r}")

        try:
            async with channel.typing():
                response = await asyncio.to_thread(
                    dm_respond, campaign, characters, combined_action, avrae_events,
                    actor_names, transition_context, first_user_id, actions,
                    resolution_result, suppress_for_combat_narration,
                )
        except (discord.HTTPException, asyncio.TimeoutError) as e:
            log(f"typing_indicator_failed: command=_dm_respond_and_post err={e!r}")
            response = await asyncio.to_thread(
                dm_respond, campaign, characters, combined_action, avrae_events,
                actor_names, transition_context, first_user_id, actions,
                resolution_result,
            )

        # Ship A live-verify patch (S36 #3) — DC strip. Parse the LLM-emit
        # directive BEFORE the response is stored / posted, cache the
        # parsed dict for the writer hook below, then strip the trailing
        # DC from the player-facing response. Avrae sees the stripped
        # form (silently ignores trailing integer per A.2 recon anyway);
        # engine retains DC via the cached parse used downstream.
        _ship_a_emit_cache = _parse_llm_emit_directive(response)
        if _ship_a_emit_cache is not None:
            response = _strip_dc_from_llm_emit(response)

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

        # Ship A (S36) — LLM-emitted-directive writer hook. Uses the
        # pre-strip cached parse (computed above) so we don't re-parse
        # the stripped response (which no longer has the DC visible).
        # Writes a pending directive row keyed by the current acting
        # character + parsed skill + parsed DC. Avrae's roll embed
        # arrival (within seconds) triggers _handle_dm_roll_arrival →
        # resolve → auto-fire textured outcome narration. Soft-fail
        # end-to-end: parser or upsert failure must NEVER raise into
        # _dm_respond_and_post.
        try:
            emit_directive = _ship_a_emit_cache
            if emit_directive is not None:
                primary_actor = (
                    actor_names_display[0] if actor_names_display else ''
                )
                if primary_actor:
                    skill, dc = orch.parse_skill_and_dc(
                        emit_directive['skill_raw']
                    )
                    pending_directive_upsert(
                        campaign_id=campaign['id'],
                        actor_name=primary_actor,
                        check_type=skill,
                        source_message_id=str(msg.id),
                        ttl_seconds=al.PENDING_DIRECTIVE_TTL_SECONDS,
                        dc=dc,
                    )
                    dc_str = str(dc) if dc is not None else 'none'
                    log(f"llm_emit_directive_bound: "
                        f"campaign={campaign['id']} "
                        f"actor={primary_actor} skill={skill} dc={dc_str} "
                        f"kind={emit_directive['kind']} "
                        f"source_message_id={msg.id}")
                    multi_count = emit_directive.get('multi_count', 1)
                    if multi_count > 1:
                        log(f"llm_emit_multi_directive_count: "
                            f"campaign={campaign['id']} count={multi_count}")
        except Exception as e:
            log(f"_llm_emit_directive_write error: {e!r}")

        asyncio.create_task(_attach_hints(msg, embed, response))
        asyncio.create_task(_extract_and_persist_world(campaign["id"], response, guild))
    except Exception as e:
        log(f"_dm_respond_and_post error: {e}")
        import traceback; log(traceback.format_exc())


async def _fire_resolution_narration(campaign: dict, payload: dict, guild) -> None:
    """Ship 1 (§9.5, §11.11) auto-fire wrapper for resolution-bound narration.

    Schedules `_dm_respond_and_post` with the synthesized actions list +
    resolution_result kwarg. On exception, logs `_dm_respond_and_post_failure:`
    and posts a deterministic fallback aside to #dm-aside so the DM has
    visibility of the engine-computed resolution even when the LLM-path
    failed (matches the verifier escalation placeholder shape).
    """
    resolution = payload.get('resolution')
    actions = payload.get('actions') or []
    combined_action = payload.get('combined_action') or ''
    campaign_id = payload.get('campaign_id')
    try:
        characters = get_characters(campaign_id) or []
        await _dm_respond_and_post(
            campaign, characters,
            actions=actions,
            combined_action=combined_action,
            resolution_result=resolution,
        )
    except Exception as e:
        actor = getattr(resolution, 'actor', '?')
        skill = getattr(resolution, 'skill_or_save', '?')
        log(f"_dm_respond_and_post_failure: campaign={campaign_id} "
            f"actor={actor} skill={skill} err={e!r}")
        if resolution is not None:
            try:
                outcome = 'PASSED' if resolution.passed else 'FAILED'
                fallback_text = (
                    f"Roll resolution: {resolution.actor} "
                    f"{resolution.skill_or_save.replace('_', ' ').title()} "
                    f"{resolution.check_kind} at DC {resolution.dc} "
                    f"(rolled {resolution.roll_total}). "
                    f"Result: {outcome}."
                )
                await _post_dm_aside(guild, fallback_text)
            except Exception as inner_e:
                log(f"_fire_resolution_narration fallback aside failed: {inner_e!r}")


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
    # Captured BEFORE init_scene_state writes the row — that call always
    # creates a row (ON CONFLICT preserves), so the gate flips to False after
    # this point and subsequent /play calls correctly suppress the hint.
    prior_scene = get_scene_state(campaign['id'])
    is_first_session = prior_scene is None

    # Ship 2 (S39): seed parameter dropped. The legacy seed string used to
    # land in dnd_scene_state.last_scene_change, which was a four-property
    # latent-canon contamination surface (Doctrine §76) and is now deleted.
    # /play's opening narration is generated by the regular DM-respond loop
    # downstream — no scene_state seeding required. The `scene` slash-command
    # argument is no longer consumed here; it's preserved in the call signature
    # for back-compat but does not flow into scene_state.
    init_scene_state(campaign['id'])

    # Bug 1 Phase 1 (S32) — clear footer-actor on /play. Opening narration
    # doesn't address a specific player, so any prior turn's actor must
    # not bleed into the next directive's footer-binding window. Soft-fail
    # so footer-actor bookkeeping never blocks the opening.
    try:
        update_last_active_actor(campaign['id'], '', 'play')
    except Exception as e:
        log(f"update_last_active_actor failed (/play): {e!r}")

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

    # Ship 3 (S41, post-pivot): suggest the Avrae sync command sequence to
    # #dm-aside if NPC is currently in init. §1b suggester pattern; DM
    # pastes the commands. Avrae filters bot-typed commands (S41 verify pass
    # finding, NPC_STATE_SYNC_SPEC.md §13), so direct bot-emit is blocked.
    # The channel arg here is only used for guild lookup → #dm-aside.
    narration_ch = get_channel(interaction.guild, 'narration')
    projection_status_line = ''
    if narration_ch is not None:
        proj_ok, proj_signals = await _avrae_project_npc(
            narration_ch, campaign_id, canonical, trigger='hydrate'
        )
        reason = proj_signals.get('reason', 'unknown')
        if reason == 'suggested':
            projection_status_line = ' See #dm-aside for the Avrae sync paste.'
        elif reason == 'suggested_with_warning':
            projection_status_line = (
                ' Mid-combat re-hydrate — see #dm-aside for HP-reset warning + paste.'
            )
        elif reason == 'noop_complete':
            projection_status_line = ' Avrae already in sync.'
        elif reason == 'gate_not_in_init':
            projection_status_line = (
                ' Not in init — Avrae sync will be suggested on `!init add` + `!init list`.'
            )
        elif reason == 'aside_post_failed':
            projection_status_line = ' #dm-aside post FAILED — sync manually if needed.'
        elif reason == 'gate_engine_stats_null':
            projection_status_line = ' Engine stats incomplete; no Avrae sync suggested.'

    if fresh and wrote:
        hp = fresh.get('hp_max') or '?'
        ac = fresh.get('ac') or '?'
        atk = fresh.get('attack_bonus') or '?'
        dmg = fresh.get('damage_dice') or '?'
        await interaction.response.send_message(
            f"Hydrated `{canonical}` at CR {normalized}: "
            f"HP {hp}, AC {ac}, Atk +{atk}, Dmg {dmg}.{projection_status_line}",
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
            f"Current: HP {hp}, AC {ac}, Atk +{atk}, Dmg {dmg}.{projection_status_line}",
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
