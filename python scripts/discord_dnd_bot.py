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
import time
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

load_dotenv('/home/jordaneal/scripts/.env')

sys.path.insert(0, '/home/jordaneal/scripts')

# Engine + Avrae listener (both in /home/jordaneal/scripts/)
from dnd_engine import (
    db_init, chroma_init, chroma_store, dm_respond,
    get_active_campaign, get_characters, get_character_by_controller,
    create_campaign, bind_character, list_campaigns,
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
    get_focused_quest,
    quest_offer, quest_accept, quest_deliver, quest_fail, quest_abandon,
    quest_seed_skeleton, get_offered_quests, get_quest_by_id,
    get_offerable_skeleton_quests,
    quest_act_upsert, set_current_act, quest_act_transition,
    get_quest_acts, get_act_by_id, get_current_act,
    get_turn_counter,
    companion_add, companion_remove, companion_edit, get_companions, COMPANION_CAP,
    update_tension,
    get_bound_character_names,
    canonicalize_actor_name,
    npc_upsert, npc_fragmentation_report, npc_list,
    get_recently_active_npcs,
    stat_incomplete, npc_hydrate_stats, npc_register_avrae_madd, npc_get_by_name,
    location_upsert, location_get, location_get_by_name, location_list,
    set_current_location, get_current_location,
    phantom_location_candidates,
    world_health_report,
    consequence_list_for_command,
    add_item, get_inventory, remove_item, PARTY_STASH_BUCKET,
    get_pending_loot,
    advance_time, parse_elapsed, PHASES,
    update_campaign_premise, is_bootstrap_complete,
    log,
)
from skeleton_writer import skeleton_md_append_element
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
#
# S65.A format unification: backtick boundary added alongside `**`. The
# new operator-locked format is a bullet + backtick wrap:
#     - `!check perception 15 : Donovan`
# Boundary char class now excludes `` ` `` so a closing backtick stops
# the skill_raw capture cleanly; the trailing lookahead accepts either
# `*` (legacy bold close) or `` ` `` (current code close) as the
# right-edge marker. Both formats parse to the same skill/DC/actor.
_LLM_EMIT_DIRECTIVE_RX = re.compile(
    r"!(?P<kind>check|save|cast)\s+(?P<skill_raw>[^\n!:*`]+?)\s*"
    r"(?::\s*[^\n!*`]+?)?"     # optional ": <Character Name>" suffix
    r"\s*(?=\n|$|\*|`)",       # stop at newline, EOL, `**` close, or backtick close
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
    #
    # S65.A format unification: backtick boundary added alongside `**`.
    # The current operator-locked format is `` `!check skill DC : Name` ``
    # (single backticks, rendered as inline code). Strip regex now accepts
    # `**` (legacy) OR `` ` `` (current) as the closing-token alternation,
    # and the boundary char classes exclude `` ` `` so the backtick close
    # is preserved in `tail` after substitution. Both formats round-trip
    # cleanly: DC integer is stripped; surrounding wrap/bullet survives.
    r"(?P<head>!(?:check|save)\s+[^\n!:*`]+?)"
    r"\s+\d+"                              # the DC integer (this is what gets stripped)
    r"(?P<tail>\s*(?::\s*[^\n!*`]+?)?\s*(?:\*\*|`|(?=\n|$)))",
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


# ─────────────────────────────────────────────────────────
# Quest Layer v0 (S56 + v0.1 S57 UX patch) — suggester dispatch
# §1b Reading-2: canonical-slash only. No in-character dialogue in
# #dm-aside; card is pure operational suggestion. LLM renders the offer
# scene organically on the next narration turn after /quest accept.
# ─────────────────────────────────────────────────────────

async def _dispatch_quest_offer_suggester(campaign: dict, guild,
                                          scene_state: dict) -> None:
    """Auto-fire suggester after narration posts. Reads canonical NPCs at
    current location, offerable skeleton quests, cooldown state. If proposal
    fires, posts #dm-aside card and stamps the cooldown clock.

    Soft-fail throughout — suggester errors MUST NEVER block narration."""
    try:
        if guild is None or scene_state is None:
            return
        current_loc = scene_state.get('current_location_id')
        if current_loc is None:
            # No location bound — suggester has nothing to anchor against.
            # Logged as gate_no_npcs at the compute layer.
            return
        # Canonical NPCs at location, filtered to skeleton_origin=1.
        # S62 v0.x patch: EXCLUDE party companions (rows in dnd_companions).
        # A canonical NPC who is also traveling with the party isn't a
        # quest-giver — they're already committed to the party's existing
        # quests by being in the band. Operator-feedback bug from S61
        # playtest: Eldrin/Lira/Borin showed up as quest voicers despite
        # being in the party companion list.
        all_at_loc = npc_list(campaign['id'], location_id=current_loc) or []
        try:
            _companion_names = {
                (c.get('name') or '').strip().lower()
                for c in (get_companions(campaign['id']) or [])
            }
        except Exception as _e:
            log(f"quest_offer_suggester: get_companions error={_e!r}")
            _companion_names = set()
        skel_npcs = [
            n for n in all_at_loc
            if n.get('skeleton_origin')
            and (n.get('canonical_name') or '').strip().lower() not in _companion_names
        ]
        # Offerable skeleton quests.
        offerable = get_offerable_skeleton_quests(campaign['id'])
        # Active quests (offered + in-progress) — used by the suggester to
        # avoid re-proposing in-flight quests. Conservative filter at v0:
        # offerable already excludes in-progress by status='offered' filter;
        # but include offered+in-progress here for future suggester logic.
        active = (get_offered_quests(campaign['id'])
                  + get_active_quests(campaign['id']))
        # Per-NPC cooldown map.
        guild_id_int = guild.id if hasattr(guild, 'id') else int(scene_state.get('_guild_id') or 0)
        current_turn = get_turn_counter(campaign['id'])
        candidate_npc_ids = [n.get('id') for n in skel_npcs if n.get('id')]
        cooldown_map = _build_cooldown_map(guild_id_int, candidate_npc_ids,
                                           current_turn)
        proposal, signals = orch.compute_quest_offer_suggester(
            scene_state=scene_state,
            canonical_npcs_at_location=skel_npcs,
            active_quests=active,
            offerable_quests=offerable,
            turns_since_last_offer_per_npc=cooldown_map,
        )
        # Always-fire telemetry (§59 contract).
        log(orch.quest_offer_log_summary(
            signals,
            voicer_npc_name=proposal['voicer_npc_name'] if proposal else '',
            quest_title=proposal['quest_title'] if proposal else '',
            quest_id=proposal['quest_id'] if proposal else 0,
        ))
        if proposal is None:
            return
        # Stamp the cooldown clock (matches the "card posted" semantic —
        # even if the operator declines, the NPC has been "given the floor"
        # this turn).
        _record_quest_offer_post(guild_id_int, proposal['voicer_npc_id'],
                                  current_turn)
        # Capture the proposal moment in the audit trail. The quest is
        # already at status='offered' (from /quest seed-skeleton); this
        # call updates offer_npc_id + offered_turn with the suggested voicer
        # + current turn so the audit log preserves "card-posted-at" history
        # even if the operator never accepts.
        try:
            quest_offer(
                campaign['id'], proposal['quest_id'],
                offer_npc_id=proposal['voicer_npc_id'],
                offered_turn=current_turn,
                source='propose',
            )
        except Exception as e:
            log(f"quest_offer_proposal_audit: error={e!r}")
        # Build the suggester card and post (pure operational; no
        # in-character dialogue per v0.1 S57 UX patch).
        card = _format_quest_offer_card(proposal)
        await _post_dm_aside(guild, card)
    except Exception as e:
        log(f"quest_offer_dispatch: error={e!r}")
        import traceback
        log(traceback.format_exc())


def _format_quest_offer_card(proposal: dict) -> str:
    """Render the suggester card text — pure operational suggestion per v0.1
    S57 UX patch. No in-character dialogue (Reading-2 framing). The LLM
    renders the offer scene organically on the next narration turn after
    /quest accept flips the quest to in-progress."""
    reward = (proposal.get('reward_summary') or '').strip() or '(unspecified)'
    summary = (proposal.get('quest_summary') or '').strip()
    summary_line = f"\n_Summary:_ {summary}" if summary else ""
    return (
        f"**[QUEST OFFER PROPOSED]**\n"
        f"NPC voicer: **{proposal['voicer_npc_name']}** (at current location)\n"
        f"Quest #{proposal['quest_id']}: **{proposal['quest_title']}**"
        f"{summary_line}\n"
        f"Reward: {reward}\n\n"
        f"_Run `/quest accept {proposal['quest_id']}` when the party commits "
        f"in-character (the LLM will pick up the new in-progress quest on "
        f"the next turn). "
        f"`/quest abandon {proposal['quest_id']}` dismisses._"
    )


# ─────────────────────────────────────────────────────────
# Composition Layer v0 (S60) — quest-act suggester dispatch
# §1b fourth project instance — canonical /quest act advance slash gate,
# deterministic-validator predicate (no cosine-similarity, Reading-2 direct).
# Fires only on Scene Lifecycle compression turn per §11.9 lock.
# ─────────────────────────────────────────────────────────

# Per-(guild_id, quest_id) turn-counter snapshot when a quest_act suggester
# card was last posted. Used to cooldown re-firing on the same compression
# (compression cadence already rate-limits; this is belt-and-suspenders).
_quest_act_suggester_last_turn: dict[tuple[int, int], int] = {}


def _scene_count_at_current_act(campaign_id: int, quest_id: int) -> int:
    """Approximate scene-count since current_act was anchored. v0
    approximation: scenes between the most-recent act-anchor write and
    current turn, derived from dnd_quests_audit (act_advance/act_set rows)
    + dnd_scene_state.turn_counter.

    Falls back to scene_state.turn_counter when no audit history exists
    (Act 1 case — the anchor was set by quest_accept which doesn't write
    an act-transition audit row). The approximation is operator-friendly:
    "how many turns since this act started" → predicate scene_count_threshold
    compares against this directly.

    Soft-fail: returns 0 on error so suggester decides safe (no fire)."""
    try:
        import sqlite3 as _sq
        from dnd_engine import DB_PATH as _DBP, get_turn_counter as _gtc
        cur_turn = _gtc(campaign_id) or 0
        conn = _sq.connect(_DBP)
        row = conn.execute(
            "SELECT MAX(turn_counter) FROM dnd_quests_audit "
            "WHERE campaign_id=? AND quest_id=? "
            "AND source IN ('act_advance','act_set','act_override')",
            (campaign_id, quest_id)
        ).fetchone()
        conn.close()
        last_transition_turn = (row[0] if row and row[0] is not None else 0)
        # When no transition audit exists, fall back to accepted_turn
        # (Act 1 was anchored by quest_accept).
        if not last_transition_turn:
            q = get_quest_by_id(campaign_id, quest_id) or {}
            last_transition_turn = q.get('accepted_turn') or 0
        return max(0, cur_turn - last_transition_turn)
    except Exception as e:
        log(f"_scene_count_at_current_act: error={e!r}")
        return 0


async def _dispatch_quest_act_suggester(campaign: dict, guild,
                                        scene_state: dict) -> None:
    """Compression-coupled act-transition suggester per §11.9. Fires from
    Scene Lifecycle compression dispatch path (when tier=soft or strong
    fires). Reads current_act + candidate_next_act + scene_count +
    location_id; calls compute_quest_act_suggester; posts card to
    #dm-aside if proposal returned.

    §1b fourth project instance: NO cosine-similarity, NO paste-detection.
    Canonical-slash gate is /quest act advance <quest_id>. Operator
    approves; engine writes via quest_act_transition.

    Soft-fail throughout — suggester errors MUST NEVER block narration."""
    try:
        if guild is None or scene_state is None:
            return
        current_act = get_current_act(campaign['id'])
        if not current_act:
            # No anchor — suggester silent. Log per §59 always-fire.
            log("quest_act_suggester: fired=0 reason=no_current_act "
                f"campaign={campaign['id']}")
            return
        quest_id = current_act['quest_id']
        # Get the candidate next act (act_index = current + 1).
        all_acts = get_quest_acts(campaign['id'], quest_id) or []
        current_idx = current_act['act_index']
        candidate_next = next(
            (a for a in all_acts if a['act_index'] == current_idx + 1),
            None
        )
        scene_count = _scene_count_at_current_act(campaign['id'], quest_id)
        loc_id = scene_state.get('current_location_id')
        proposal, signals = orch.compute_quest_act_suggester(
            scene_state=scene_state,
            current_act=current_act,
            candidate_next_act=candidate_next,
            scene_count_at_current_act=scene_count,
            current_location_id=loc_id,
        )
        log(orch.quest_act_suggester_log_summary(signals, proposal))
        if proposal is None:
            return
        # Cooldown check (belt-and-suspenders; compression cadence rate-
        # limits already).
        guild_id_int = guild.id if hasattr(guild, 'id') else 0
        current_turn = get_turn_counter(campaign['id']) or 0
        last = _quest_act_suggester_last_turn.get((guild_id_int, quest_id))
        if last is not None and (current_turn - last) < 3:
            log(f"quest_act_suggester: fired=0 reason=local_cooldown "
                f"campaign={campaign['id']} quest_id={quest_id}")
            return
        _quest_act_suggester_last_turn[(guild_id_int, quest_id)] = current_turn
        card = _format_quest_act_card(proposal, current_act, candidate_next)
        await _post_dm_aside(guild, card)
    except Exception as e:
        log(f"quest_act_suggester_dispatch: error={e!r}")
        import traceback
        log(traceback.format_exc())


def _format_quest_act_card(proposal: dict, current_act: dict,
                            next_act: dict) -> str:
    """Render the act-transition suggester card — pure operational suggestion.
    No in-character dialogue (Reading-2 framing, §1b fourth instance).
    Operator runs `/quest act advance <quest_id>` to approve."""
    quest_id = proposal.get('quest_id')
    cur_idx = proposal.get('current_act_index')
    nxt_idx = proposal.get('proposed_next_act_index')
    cur_title = (current_act.get('act_title') or '').strip()
    nxt_title = (next_act.get('act_title') or '').strip()
    reason = proposal.get('predicate_reason') or 'predicate match'
    nxt_desc = (next_act.get('act_description') or '').strip()
    desc_line = f"\n_Next act:_ {nxt_desc}" if nxt_desc else ""
    return (
        f"**[QUEST ACT TRANSITION PROPOSED]**\n"
        f"Quest #{quest_id}\n"
        f"Current: **Act {cur_idx} — {cur_title}**\n"
        f"Proposed: **Act {nxt_idx} — {nxt_title}**"
        f"{desc_line}\n"
        f"Predicate reason: {reason}\n\n"
        f"_Run `/quest act advance {quest_id}` to confirm "
        f"(LLM will pick up the new act on the next turn)._"
    )


def _parse_reward_summary_for_inventory(reward_summary: str) -> list[dict]:
    """Parse a structured reward_summary for inventory-side auto-add per
    §11.6 (d) hybrid. Returns a list of {'name': str, 'quantity': int} dicts.

    Strict format expected per §7 reward_summary audit guidance:
      "50gp" → [{'name': 'gp', 'quantity': 50}]
      "50gp + Stoneforge favor" → [{'name': 'gp', 'quantity': 50}]
                                   (faction tokens not auto-added at v0)
      "shortbow" → [{'name': 'shortbow', 'quantity': 1}]
      "50gp + shortbow" → [{'name': 'gp', 'quantity': 50},
                            {'name': 'shortbow', 'quantity': 1}]
    Freetext like "the deepest gratitude" → [] (no auto-add)."""
    import re
    items: list[dict] = []
    if not reward_summary:
        return items
    # Split on '+' or ','
    parts = re.split(r'[+,]', reward_summary)
    for raw in parts:
        token = raw.strip()
        if not token:
            continue
        # Match "Ngp" / "Nsp" / "Ncp" / "Npp" / "Ngold" / "Nsilver" pattern.
        m = re.match(r'^\s*(\d+)\s*(gp|sp|cp|pp|gold|silver)\s*$', token, re.I)
        if m:
            qty = int(m.group(1))
            unit = m.group(2).lower()
            # Normalize unit tokens to gp/sp/cp/pp.
            unit_map = {'gold': 'gp', 'silver': 'sp'}
            unit = unit_map.get(unit, unit)
            items.append({'name': unit, 'quantity': qty})
            continue
        # Match "<faction> reputation" / "<faction> favor" — skip auto-add
        # (faction layer doesn't exist per spec §12.2).
        if re.search(r'\b(reputation|favor)\b', token, re.I):
            continue
        # Match a single named item — only register if token is reasonably
        # item-shaped (no verbs, no "gratitude" / "thanks" / "honor" type
        # freetext). v0 heuristic: token is 1-3 words, no descriptors like
        # "deepest" / "lasting" / "eternal".
        if re.search(r'\b(gratitude|thanks|honor|respect|recognition|'
                     r'praise|story|tale)\b', token, re.I):
            continue
        words = token.split()
        if 1 <= len(words) <= 3 and all(re.match(r'^[a-zA-Z\-]+$', w)
                                         for w in words):
            items.append({'name': token, 'quantity': 1})
    return items


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
# §78.6 layer-4 render-vs-marker — per-guild combat beat counter
# ─────────────────────────────────────────────────────────
# Counts narratable beats during a combat session so COMBAT_END can branch:
# 0 beats → deterministic neutral closeout (no LLM); ≥1 beats → LLM render.
# Increments on BLOODIED_THRESHOLD_CROSSED + COMBATANT_DOWNED dispatches
# (HP-state transitions = actual combat content). ROUND_START does NOT
# increment (structurally always-fires regardless of content — counting it
# would mis-classify exactly the 0-action case we're detecting). COMBAT_END
# reads + branches; does not increment.
# Reset on !init begin; cleared on !init end after dispatch completes.
# In-memory by design — transience matches transience of combat sessions
# (§78.5 substrate-match: DB column for ephemeral state would be wrong
# substrate). Keyed by guild_id.
_combat_beat_counter: dict[int, int] = {}

# §78.6 deterministic boundary marker — posted to #dm-narration in lieu of
# LLM dispatch when COMBAT_END fires with zero narratable beats. Neutral
# closeout that doesn't presuppose combat events occurred. Sibling-shape to
# S45's _INIT_END_CLOSEOUT_SCENE but distinct surface (this posts to Discord;
# S45's writes to current_scene buffer).
_COMBAT_END_NEUTRAL_CLOSEOUT = "Combat ends. The moment passes."


def _reset_combat_beats(guild_id: int) -> None:
    _combat_beat_counter[guild_id] = 0


def _increment_combat_beat(guild_id: int) -> int:
    _combat_beat_counter[guild_id] = _combat_beat_counter.get(guild_id, 0) + 1
    return _combat_beat_counter[guild_id]


def _get_combat_beats(guild_id: int) -> int:
    return _combat_beat_counter.get(guild_id, 0)


def _clear_combat_beats(guild_id: int) -> None:
    _combat_beat_counter.pop(guild_id, None)


# ─────────────────────────────────────────────────────────
# Scene lifecycle stale counter (Scene Lifecycle v1, S52)
# F-54 scene immortality — §59 sibling state substrate
# ─────────────────────────────────────────────────────────

_scene_stale_turns: dict[int, int] = {}

# §11.L modified: capture per-guild whether last combat had narratable beats,
# so the climactic-hold predicate has signal in post-combat exploration.
# Set at COMBAT_END before _clear_combat_beats; persists until next combat start.
_last_combat_had_beats: dict[int, bool] = {}


def _reset_scene_stale(guild_id: int) -> None:
    _scene_stale_turns.pop(guild_id, None)


def _increment_scene_stale(guild_id: int) -> int:
    _scene_stale_turns[guild_id] = _scene_stale_turns.get(guild_id, 0) + 1
    return _scene_stale_turns[guild_id]


def _get_scene_stale(guild_id: int) -> int:
    return _scene_stale_turns.get(guild_id, 0)


# ─────────────────────────────────────────────────────────
# Quest Layer v0 (S56 + v0.1 S57 UX patch) — in-memory state
# §1b third project instance — Reading-2 framing per S57 patch:
# canonical `/quest accept <id>` slash is the ONLY acceptance trigger.
# Cosine-similarity paste-detection was dropped per live-verify UX finding
# (in-character RP text in #dm-aside read as "too mechanical, not free
# flowing enough"). The suggester card is now pure operational suggestion;
# the LLM renders the offer scene organically on the next narration turn
# after /quest accept flips status to in-progress.
# ─────────────────────────────────────────────────────────

# Per-(guild_id, npc_id) turn-counter of last offer-card posted. Used by
# the suggester's cooldown gate (§11.3, _QUEST_OFFER_COOLDOWN = 6 turns).
# Missing key = never offered for that NPC.
_quest_offer_last_turn: dict[tuple[int, int], int] = {}


def _record_quest_offer_post(guild_id: int, npc_id: int,
                              turn_counter: int) -> None:
    """Stamp the cooldown clock for (guild_id, npc_id) at the current turn.
    Called on suggester-card post to #dm-aside, BEFORE operator approval."""
    _quest_offer_last_turn[(guild_id, npc_id)] = turn_counter


def _turns_since_last_offer(guild_id: int, npc_id: int,
                             current_turn: int) -> int:
    """Return turns since last offer-card to this NPC. Returns a large value
    when no prior offer recorded (effectively bypasses the cooldown gate)."""
    last = _quest_offer_last_turn.get((guild_id, npc_id))
    if last is None:
        return 9999
    return max(0, current_turn - last)


def _build_cooldown_map(guild_id: int, npc_ids: list[int],
                        current_turn: int) -> dict:
    """Convenience: build the per-NPC cooldown dict the suggester expects."""
    return {nid: _turns_since_last_offer(guild_id, nid, current_turn)
            for nid in npc_ids}


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

    # §1b.1 Clarification Handshake — restart-preservation notice (S77).
    # M-DELAYED pending_clarification flag survives restart in the DB.
    # In-memory Layer B listener sessions do not (cleared at module import).
    # For each campaign that has a non-NULL pending_clarification, post a
    # one-time notice to #dm-aside so the operator knows the in-fiction
    # context is preserved and can continue narrating to resolve.
    try:
        import clarification_handshake as ch
        import sqlite3 as _sq
        from dnd_engine import DB_PATH as _DBP
        pending_campaigns = ch.list_campaigns_with_pending_clarification()
        for cid in pending_campaigns:
            try:
                conn = _sq.connect(_DBP)
                row = conn.execute(
                    "SELECT guild_id FROM dnd_campaigns WHERE id=?",
                    (cid,),
                ).fetchone()
                conn.close()
                _guild_id = row[0] if row else None
                if not _guild_id:
                    continue
                _guild = bot.get_guild(int(_guild_id))
                if _guild is None:
                    continue
                await _post_dm_aside(
                    _guild,
                    "*I just restarted — there was a pending clarification "
                    "from last turn. Keep playing and I'll pick it up from "
                    "your next move, or paste the matching slash if you "
                    "know which one fits.*",
                )
                log(f"clarification_restart_notice: campaign={cid}")
            except Exception as _ne:
                log(f"clarification_restart_notice: campaign={cid} err={_ne!r}")
    except Exception as e:
        log(f"clarification_restart_notice: top-level error err={e}")



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
            # §78.6 reset the per-guild combat beat counter at session start.
            # Beats accumulate via BLOODIED/DOWNED dispatches during combat
            # and gate the COMBAT_END render path at session end.
            _reset_combat_beats(message.guild.id)
            # §11.I: combat entry is an activity signal — reset stale counter.
            # Post-combat exploration starts fresh regardless of pre-combat value.
            _reset_scene_stale(message.guild.id)
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
            # §78 layer-1 in-memory state reset (sibling to S45's DB-side
            # narrative buffer reset). RollBuffer holds in-memory Avrae events
            # keyed by guild. Drain at the combat→exploration boundary to
            # prevent stale combat-mechanical events (check/save/attack/cast/
            # damage/roll) from leaking into post-combat narration — both the
            # `(N rolls in play)` footer artifact AND the LLM prompt's AVRAE
            # EVENTS block via _format_avrae_events. Mirrors clear_combatants
            # / clear_active_turn blunt-full-reset pattern on the in-memory
            # substrate. Ordering: runs BEFORE _dispatch_combat_narration so
            # COMBAT_END's buffer.consume(['combat']) stays cleanly empty
            # per S45-F's clean-closeout intent.
            try:
                drained_count = buffer.size(message.guild.id)
                buffer.clear(message.guild.id)
                log(f"init_end_rollbuffer_drained: campaign={campaign['id']} "
                    f"guild={message.guild.id} drained_count={drained_count}")
            except Exception as e:
                log(f"init_end_rollbuffer_drained: error campaign={campaign['id']} "
                    f"guild={message.guild.id} err={e!r}")
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
            #
            # §78.6 layer-4 render-vs-marker branch: if zero narratable
            # beats fired during this combat (no BLOODIED, no DOWNED
            # dispatches), the LLM render presupposition fails — the
            # directive's "falling tension / cessation of motion / room
            # settling" framing has no narrative referent. Branch to
            # deterministic neutral closeout (boundary marker without LLM
            # speculation). Multi-action combats fall through to the
            # existing S45-F dispatch unchanged.
            beats = _get_combat_beats(message.guild.id)
            if beats == 0:
                log(f"combat_end_zero_action: campaign={campaign['id']} "
                    f"guild={message.guild.id} beats=0 "
                    f"deterministic_closeout=1")
                try:
                    narration_ch = get_channel(message.guild, 'narration')
                    if narration_ch:
                        await narration_ch.send(_COMBAT_END_NEUTRAL_CLOSEOUT)
                    else:
                        log("combat_end_zero_action: narration channel "
                            "not found, closeout marker not posted")
                except Exception as e:
                    log(f"combat_end_zero_action: post error err={e!r}")
            else:
                log(f"combat_end_llm_dispatch: campaign={campaign['id']} "
                    f"guild={message.guild.id} beats={beats}")
                await _dispatch_combat_narration(
                    campaign,
                    {'kind': 'COMBAT_END'},
                    combat_state_override=pre_clear_combat_state,
                    scene_override={'mode': 'combat'},
                )
            # §11.L modified: capture beat history BEFORE clearing, so the
            # climactic-hold predicate has signal in post-combat exploration.
            # _combat_beat_counter is about to be cleared; this flag persists
            # until next combat start (§11.I reset at !init begin).
            _last_combat_had_beats[message.guild.id] = (
                _get_combat_beats(message.guild.id) > 0
            )
            # §78.6 counter cleanup after dispatch (either branch).
            _clear_combat_beats(message.guild.id)
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
        # §78.6 beat counter — increment only on HP-state-transition kinds
        # (actual combat content). ROUND_START fires regardless of content
        # and is excluded by design; COMBAT_END reads the counter and does
        # not increment.
        if trigger_event.get('kind') in ('BLOODIED_THRESHOLD_CROSSED',
                                          'COMBATANT_DOWNED'):
            try:
                guild_id_for_beat = campaign.get('guild_id', '')
                if guild_id_for_beat:
                    new_count = _increment_combat_beat(int(guild_id_for_beat))
                    log(f"combat_beat_incremented: campaign={campaign['id']} "
                        f"guild={guild_id_for_beat} kind={trigger_event.get('kind')} "
                        f"beats={new_count}")
            except Exception as e:
                log(f"combat_beat_incremented: error err={e!r}")
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

        # §78 layer-1 in-memory state reset, mode-agnostic application
        # (sibling to S48's init-end drain). Every Avrae rest embed lands
        # in RollBuffer via on_message → buffer.add with kind='rest'. The
        # actor-extraction fallback to 'someone' currently keeps these
        # entries from matching PC-actor consume filters (zero observed
        # buffer.consume hits on roll_kinds=['rest'] across full journal),
        # but that protection is serendipitous, not structural — if a
        # future Avrae embed parses to a real PC name, the rest event
        # would surface in the next matching-actor turn's footer
        # ((N rolls in play)) AND in the LLM prompt's AVRAE EVENTS block.
        # Drain at the rest boundary, regardless of mode, closes the
        # substrate-completion gap before the serendipity breaks.
        try:
            drained_count = buffer.size(message.guild.id)
            buffer.clear(message.guild.id)
            log(f"rest_event_rollbuffer_drained: campaign={campaign['id']} "
                f"guild={message.guild.id} drained_count={drained_count} "
                f"rest_kind={rest_kind}")
        except Exception as e:
            log(f"rest_event_rollbuffer_drained: error campaign={campaign['id']} "
                f"guild={message.guild.id} err={e!r}")

        # §1.F.d: advance_time is an activity signal; reset stale counter.
        _reset_scene_stale(message.guild.id)
        log(f"scene_lifecycle_reset: campaign={campaign['id']} "
            f"guild={message.guild.id} reason=rest_advance_time rest_kind={rest_kind}")
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

    # Quest Layer v0.1 (S57 UX patch) — cosine-similarity paste-detection
    # REMOVED. Reading-2 framing per §11.12 patched lock: canonical /quest
    # accept <id> slash is the only acceptance trigger. No paste-detection
    # auxiliary layer. LLM renders the offer scene organically on the next
    # narration turn after /quest accept flips status to in-progress.

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

    # ── Conversational-Runtime Inversion v0 — Phase 3a + §1b.1 (S77) ─────
    # Pre-LLM aggregator. Per S77 dispatch, the single _run_quest_acceptance
    # detection task expands into _run_inversion_aggregator which fans out
    # across all registered v0 parsers (quest-accept at Phase 3a; transaction
    # + loot-drop register at Phase 3b) and routes per §1b.1 Stage 1 rule:
    #
    #   - 0 parsers ≥MEDIUM → silent log
    #   - 1 parser at HIGH → SINGLE_DOMAIN_CLEAR (existing Phase 3a path)
    #   - 1 parser at MEDIUM with markers → IN_FICTION_CLARIFICATION
    #     (M-DELAYED primary; pending_clarification flag set, LLM narrates
    #     scene continuing without finalizing)
    #   - 1 parser at MEDIUM without markers → SINGLE_DOMAIN_CLEAR
    #   - ≥2 parsers ≥MEDIUM enumerable → LAYER_A multi-paste card
    #   - ≥2 parsers ≥MEDIUM non-enumerable → LAYER_B OOC handshake
    #
    # Soft-fail at call site — aggregator/detection never blocks narration.
    try:
        asyncio.create_task(
            _run_inversion_aggregator(
                campaign['id'], action, message.guild,
                str(message.author.id), message,
            )
        )
    except Exception as e:
        log(f"inversion_v0_aggregator: scheduling error "
            f"campaign={campaign['id']} err={e!r}")

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


async def _attach_hints(message, embed, narration, campaign_id: int | None = None):
    """Background task: parse mechanical hints from narration, edit message
    in place to append a bookkeeping section if any survive the whitelist.

    Silent on timeout, empty result, or any error. Never blocks narration
    delivery — runs after the post has already happened.

    S65.1 N-1: `campaign_id` enables cross-turn dedup in the parser and
    `hint_extractor_emitted/suppressed` telemetry.
    """
    try:
        hints = await asyncio.wait_for(
            asyncio.to_thread(parse_mechanical_hints, narration, campaign_id),
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

    # S65.A format unification (operator request): bullet + backtick command,
    # no preamble, no horizontal divider. Visual consistency with roll
    # requests, attack templates, and Suggested Actions — all now render as
    # bullet + boxed command. Redundant "Bookkeeping (you type these):"
    # framing removed; the boxed command + bullet read as "this is a
    # mechanical thing for you to type" without needing explanatory text.
    bookkeeping = "\n".join(f"- `{h}`" for h in hints)
    suffix = f"\n\n{bookkeeping}"

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


async def _extract_and_persist_world(campaign_id, narration, guild=None,
                                      guild_id_int: int = 0):
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
                    # §1.F.c was an LLM-extracted activity signal in v1 spec but
                    # was dropped in S53 v1.x patch: live verify (May 2026)
                    # surfaced LLM-forgeable signal pattern — scene-padded NPC
                    # introductions reset the stagnation counter and defeated
                    # detection. The guild_id_int param is preserved for a
                    # potential corroborated-signal v1.x candidate (NPC was_new
                    # AND location/roll co-occurring). See spec §1.F footnote
                    # and §12.10 for the v1.x direction.
        except Exception as e:
            log(f"npc_upsert: error campaign={campaign_id} "
                f"name={n['name']!r} err={e!r}")

    log(f"npc_extract: campaign={campaign_id} written={written}")
    if location_resolution_log:
        log(f"npc_location_resolve: campaign={campaign_id} "
            f"resolved=[{', '.join(location_resolution_log)}]")

    # S68 N-4 — pronoun lock pass on first narration mention.
    # For each NPC just extracted/mentioned, if pronouns column is still
    # empty, scan a window around the NPC name in the narration for the
    # canonical pronoun set. First-occurrence wins.
    try:
        _lock_npc_pronouns_from_narration(campaign_id, narration, npcs)
    except Exception as e:
        log(f"npc_pronoun_live_lock: error campaign={campaign_id} err={e!r}")

    _emit_npc_health(campaign_id)
    _emit_phantom_candidates(campaign_id)
    _emit_world_health(campaign_id)

    # S73.1 — Quest-acceptance detection moved from this post-LLM hook to
    # pre-LLM hook in on_message. Live verify at S73 showed LLM-paraphrased
    # acceptance ("nods at the agreement", "hands the party") missed the
    # closed-vocab parser; canonical acceptance verbs live in player input.
    # Helper `_run_quest_acceptance_detection` retained — fires from
    # on_message pre-chroma_store. Post-LLM hook reserved for NPC-utterance
    # extraction at S75 (Phase 3c) which IS structurally a post-LLM surface.


async def _run_quest_acceptance_detection(campaign_id: int, narration: str,
                                          guild) -> None:
    """Conversational-Runtime Inversion v0 — Phase 3a quest-acceptance detection.

    Fires the closed-vocab `parse_quest_acceptance` parser against the recent
    narration; routes per three-tier confidence (§11.7 lock); emits per-fire
    telemetry (§11.8 lock); posts suggester card to #dm-aside on detection.

    Per §F-59 + §11.10 lock: bot proposes via #dm-aside with pasteable slash;
    operator approves by pasting. No auto-emit of /quest accept.

    Soft-fail at caller (the _extract_and_persist_world wrapper catches and logs).
    """
    from quest_acceptance_parser import parse_quest_acceptance
    from inversion_telemetry import emit_parse_outcome

    try:
        offered = get_offered_quests(campaign_id)
    except Exception as e:
        log(f"inversion_v0_quest_accept: offered_lookup error "
            f"campaign={campaign_id} err={e!r}")
        offered = []

    result = parse_quest_acceptance(narration, offered, campaign_id)

    # Telemetry — always-fire. Decide event classification first.
    route = 'silent'
    if result.get('fired'):
        if result.get('confidence') == 'high':
            route = 'engine'  # destined for engine via operator paste
        elif result.get('confidence') == 'medium':
            route = 'suggester'

    emit_parse_outcome('quest_accept', campaign_id, result, route=route)

    if not result.get('fired'):
        return  # silent / suppressed / disabled — no card

    # Render and post suggester card to #dm-aside.
    card = _format_quest_acceptance_suggester_card(result, offered)
    if not card:
        return
    await _post_dm_aside(guild, card)

    log(f"inversion_v0_quest_accept: campaign={campaign_id} "
        f"confidence={result.get('confidence')} "
        f"verb={result.get('matched_verb')!r} "
        f"quest_id={result.get('matched_quest_id')}")


async def _run_inversion_aggregator(campaign_id: int, narration: str,
                                    guild, controller_id: str,
                                    trigger_message) -> None:
    """§1b.1 Clarification Handshake aggregator (S77).

    Wraps all v0 parsers, normalizes outputs to ParserResult, applies
    Stage 1 routing via clarification_handshake.aggregate_parser_outputs,
    then dispatches per route:

      - SINGLE_DOMAIN_CLEAR: pass through to existing Phase 3a behavior
        (currently quest-acceptance only at v0; Phase 3b registers
        transaction + loot-drop)
      - IN_FICTION_CLARIFICATION: M-DELAYED primary. set_pending_clarification
        on dnd_scene_state; LLM picks up directive on next narration; parser
        fires second-pass on operator's next utterance.
      - LAYER_A: render multi-paste card via _post_dm_aside
      - LAYER_B: render OOC handshake + bot.wait_for listener (5-min timeout)
      - SILENT_LOG: silent

    Second-pass detection: when pending_clarification is already set,
    re-route based on current parser outcomes. HIGH on any parser clears
    pending and commits via existing §17 path. Still-ambiguous escalates
    to Layer A/B fallback.

    Soft-fail throughout — aggregator never blocks narration. Telemetry
    fires per-event per §11.8 always-fire discipline.
    """
    from quest_acceptance_parser import parse_quest_acceptance
    from transaction_completion_parser import (
        parse_transaction_completion, SURFACE_PRE_LLM as TX_PRE,
    )
    from loot_drop_parser import (
        parse_loot_drop, SURFACE_PRE_LLM as LD_PRE,
    )
    from inversion_telemetry import (
        emit_parse_outcome, emit_clarification_event, record_parser_invocation,
    )
    import clarification_handshake as ch

    # Detect second-pass — pending_clarification already set from a prior
    # utterance. M-DELAYED's second-pass detection path.
    try:
        pending_meta = ch.get_pending_clarification(campaign_id)
    except Exception:
        pending_meta = None

    # Fan out across registered parsers.
    parser_results: list[ch.ParserResult] = []

    # ── Quest-acceptance parser (Phase 3a, S73-anchored) ─────────────────
    try:
        offered = get_offered_quests(campaign_id)
    except Exception as e:
        log(f"inversion_v0_aggregator: offered_lookup error "
            f"campaign={campaign_id} err={e!r}")
        offered = []
    try:
        qa_result = parse_quest_acceptance(narration, offered, campaign_id)
    except Exception as e:
        log(f"inversion_v0_aggregator: quest_accept parse error "
            f"campaign={campaign_id} err={e!r}")
        qa_result = {
            'fired': False, 'confidence': 'low', 'matched_verb': '',
            'matched_quest_id': None, 'matched_quest_title': '',
            'dedup_suppressed': False, 'feature_disabled': False,
        }

    record_parser_invocation('quest_accept', qa_result.get('confidence', 'low'))

    qa_candidate = {}
    if qa_result.get('matched_quest_id') is not None:
        qa_candidate = {
            'title': qa_result.get('matched_quest_title', ''),
            'slash': f"/quest accept {qa_result.get('matched_quest_id')}",
        }
    # quest_accept parser is verb-only at v0 — it does not surface NPC /
    # currency / item markers itself; structural markers come from the
    # Phase 3b transaction + loot-drop parsers. Setting markers_present=False
    # keeps quest_accept MEDIUM routing through SINGLE_DOMAIN_CLEAR (Phase 3a
    # behavior preserved) rather than the M-DELAYED IN_FICTION path.
    parser_results.append(ch.ParserResult(
        domain='quest_accept',
        confidence=qa_result.get('confidence', 'low'),
        fired=bool(qa_result.get('fired')),
        markers_present=False,
        dedup_suppressed=bool(qa_result.get('dedup_suppressed')),
        feature_disabled=bool(qa_result.get('feature_disabled')),
        candidate=qa_candidate,
    ))

    qa_route = 'silent'
    if qa_result.get('fired'):
        qa_route = 'engine' if qa_result.get('confidence') == 'high' else 'suggester'
    emit_parse_outcome('quest_accept', campaign_id, qa_result, route=qa_route)

    # ── Transaction-completion parser (Phase 3b pre-LLM, S78) ────────────
    try:
        scene_loc = None
        try:
            scene_state = get_scene_state(campaign_id) or {}
            scene_loc = scene_state.get('current_location_id')
        except Exception:
            scene_state = {}
        recent_npcs = get_recently_active_npcs(campaign_id, limit=6,
                                                 location_id=scene_loc) or []
        # Inventory is keyed by character; use active actor when available.
        # Pre-LLM hook: scene's last_active_actor is the best heuristic;
        # falls back to empty list when unset.
        inventory: list = []
        try:
            actor_name = (scene_state or {}).get('last_active_actor', '') or ''
            if actor_name:
                inventory = get_inventory(campaign_id, actor_name) or []
        except Exception:
            inventory = []
        tx_result = parse_transaction_completion(
            narration, recent_npcs, inventory, campaign_id,
            surface=TX_PRE,
        )
    except Exception as e:
        log(f"inversion_v0_aggregator: transaction_pre parse error "
            f"campaign={campaign_id} err={e!r}")
        tx_result = {
            'fired': False, 'confidence': 'low', 'matched_verb': '',
            'currency': None, 'npc_name': '', 'item_name': '',
            'markers_present': False, 'surface': TX_PRE,
            'dedup_suppressed': False, 'feature_disabled': False,
        }

    record_parser_invocation('transaction_completion_pre',
                              tx_result.get('confidence', 'low'))

    tx_candidate = {}
    if tx_result.get('npc_name') or tx_result.get('currency'):
        # Build a candidate payload for §1b.1 enumeration. The slash isn't
        # canonical at v0 (the engine doesn't yet ship a /transaction commit;
        # transactions surface via /coin operator paste per N-1 bookkeeping
        # + future engine writer). Suggester card body renders npc + currency.
        c = tx_result.get('currency') or {}
        tx_candidate = {
            'npc': tx_result.get('npc_name', ''),
            'currency': f"{c.get('amount')}{c.get('denom')}" if c else '',
            'item': tx_result.get('item_name', ''),
            'title': 'transaction completion',
        }
    parser_results.append(ch.ParserResult(
        domain='transaction_completion',
        confidence=tx_result.get('confidence', 'low'),
        fired=bool(tx_result.get('fired')),
        markers_present=bool(tx_result.get('markers_present')),
        dedup_suppressed=bool(tx_result.get('dedup_suppressed')),
        feature_disabled=bool(tx_result.get('feature_disabled')),
        candidate=tx_candidate,
    ))
    emit_parse_outcome(
        'transaction_completion_pre', campaign_id, tx_result,
        route='engine' if tx_result.get('confidence') == 'high'
        else ('suggester' if tx_result.get('fired') else 'silent'),
    )

    # ── Loot-drop player-intent parser (Phase 3b pre-LLM, S78) ───────────
    try:
        pending = get_pending_loot(campaign_id) or []
        ld_result = parse_loot_drop(narration, pending, campaign_id, surface=LD_PRE)
    except Exception as e:
        log(f"inversion_v0_aggregator: loot_drop_player parse error "
            f"campaign={campaign_id} err={e!r}")
        ld_result = {
            'fired': False, 'confidence': 'low', 'matched_verb': '',
            'matched_pending_loot_id': None, 'matched_item_name': '',
            'item_class_marker': '', 'markers_present': False,
            'surface': LD_PRE, 'dedup_suppressed': False, 'feature_disabled': False,
        }

    record_parser_invocation('loot_drop_player',
                              ld_result.get('confidence', 'low'))

    ld_candidate = {}
    if ld_result.get('matched_item_name') or ld_result.get('item_class_marker'):
        slash = ''
        if ld_result.get('matched_pending_loot_id'):
            slash = f"/loot claim {ld_result['matched_pending_loot_id']}"
        ld_candidate = {
            'item': (ld_result.get('matched_item_name')
                     or ld_result.get('item_class_marker', '')),
            'slash': slash,
            'title': 'loot claim',
        }
    parser_results.append(ch.ParserResult(
        domain='loot_drop_player',
        confidence=ld_result.get('confidence', 'low'),
        fired=bool(ld_result.get('fired')),
        markers_present=bool(ld_result.get('markers_present')),
        dedup_suppressed=bool(ld_result.get('dedup_suppressed')),
        feature_disabled=bool(ld_result.get('feature_disabled')),
        candidate=ld_candidate,
    ))
    emit_parse_outcome(
        'loot_drop_player', campaign_id, ld_result,
        route='engine' if ld_result.get('confidence') == 'high'
        else ('suggester' if ld_result.get('fired') else 'silent'),
    )

    # Apply Stage 1 routing.
    decision = ch.aggregate_parser_outputs(parser_results)

    # Second-pass branch: pending state exists.
    if pending_meta is not None:
        # If any parser hit HIGH on this utterance, commit + clear pending.
        highs = [r for r in parser_results
                 if r.confidence == 'high' and r.fired]
        if highs:
            ch.clear_pending_clarification(campaign_id)
            emit_clarification_event(
                'clarification_in_fiction_resolved',
                campaign_id,
                {'parser_domains': [r.domain for r in highs]},
            )
            # Fall through to existing Phase 3a path — quest_accept's
            # SINGLE_DOMAIN_CLEAR posts the suggester card / engine writer.
            if qa_result.get('fired'):
                card = _format_quest_acceptance_suggester_card(qa_result, offered)
                if card:
                    await _post_dm_aside(guild, card)
                log(f"inversion_v0_aggregator: second_pass_resolved "
                    f"campaign={campaign_id} domain=quest_accept "
                    f"verb={qa_result.get('matched_verb')!r}")
            return

        # Second-pass still ambiguous — escalate to Layer A/B fallback.
        if decision.route in ('LAYER_A', 'LAYER_B'):
            await _dispatch_clarification_fallback(
                campaign_id, decision, narration, guild,
                controller_id, trigger_message, fallback=True,
            )
            return

        # Second-pass with no clean fallback. Clear pending; let narration
        # proceed (per dispatch's "pending cleared, no resolution" branch).
        ch.clear_pending_clarification(campaign_id)
        emit_clarification_event(
            'clarification_pending_cleared_no_resolution', campaign_id,
            {'parser_domains': [r.domain for r in parser_results
                                 if r.fired]},
        )
        return

    # First-pass branch: no pending state.
    if decision.route == 'SILENT_LOG':
        return

    if decision.route == 'SINGLE_DOMAIN_CLEAR':
        # Fall through to existing Phase 3a path. Currently only
        # quest-acceptance ships at v0; render its suggester card if fired.
        if qa_result.get('fired'):
            card = _format_quest_acceptance_suggester_card(qa_result, offered)
            if card:
                await _post_dm_aside(guild, card)
            log(f"inversion_v0_aggregator: single_domain_clear "
                f"campaign={campaign_id} domain=quest_accept "
                f"confidence={qa_result.get('confidence')}")
        return

    if decision.route == 'IN_FICTION_CLARIFICATION':
        # M-DELAYED primary path. Set pending_clarification flag; LLM
        # narrates scene continuing on next turn via directive injection.
        trigger_event_id = f"campaign={campaign_id}:ts={int(time.time())}"
        session = ch.set_pending_clarification(
            campaign_id=campaign_id,
            candidates=decision.candidates,
            trigger_event_id=trigger_event_id,
        )
        emit_clarification_event(
            'clarification_in_fiction_fired', campaign_id,
            {
                'parser_domains': [c.get('domain') for c in decision.candidates],
                'trigger_event_id': trigger_event_id,
                'layer': 'IN_FICTION',
            },
        )
        log(f"inversion_v0_aggregator: in_fiction_fired "
            f"campaign={campaign_id} candidates={len(decision.candidates)} "
            f"trigger={trigger_event_id}")
        return

    if decision.route in ('LAYER_A', 'LAYER_B'):
        await _dispatch_clarification_fallback(
            campaign_id, decision, narration, guild,
            controller_id, trigger_message, fallback=False,
        )
        return


async def _run_central_thread_compliance_check(campaign_id: int,
                                                narration: str) -> None:
    """§82 candidate detector — central_thread MUST/MUST-NOT compliance.

    Soft-fail post-LLM check. Reads the campaign's skeleton hooks, derives
    the central_thread directive text, runs deterministic token-overlap
    detection against the narration. Fires `directive_compliance_failure`
    telemetry event when overlap density indicates the LLM restated the
    thread despite the "Do NOT name or restate" directive.

    Telemetry only — no state mutation, no operator-facing surface. The
    point is to make the failure observable so prompt iteration can be
    data-driven (per §82 architectural-design-time guidance).
    """
    try:
        from skeleton_loader import parse_skeleton_file
        from inversion_telemetry import record_directive_compliance_failure
        import dnd_orchestration as orch

        parsed = parse_skeleton_file(campaign_id)
        hooks = (parsed or {}).get('hooks') or []
        central_thread_text = orch.compute_central_thread_directive(hooks)
        if not central_thread_text:
            return
        violation, confidence, severity = (
            orch.detect_central_thread_compliance_failure(
                central_thread_text, narration,
            )
        )
        # Record LOW-severity samples too (aggregate observability), but
        # only fire as a violation when MEDIUM/HIGH.
        if severity in ('MEDIUM', 'HIGH'):
            record_directive_compliance_failure(
                directive_name='central_thread',
                severity=severity,
                narration_excerpt=narration,
                detector='post_llm_token_overlap',
                campaign_id=campaign_id,
                confidence=confidence,
                directive_intent=(
                    "Do NOT name or restate the thread in narration; "
                    "shape this turn through indirect signals only"
                ),
            )
            log(f"central_thread_compliance: violation campaign={campaign_id} "
                f"severity={severity} confidence={confidence:.2f}")
    except Exception as e:
        log(f"central_thread_compliance: error campaign={campaign_id} err={e!r}")


async def _run_inversion_aggregator_post_llm(campaign_id: int, narration: str,
                                              guild, controller_id: str) -> None:
    """§1b.1 Phase 3b post-LLM aggregator (S78). Fires transaction_completion
    + loot_drop_llm parsers against the DM narration (LLM completion text).

    Distinct from `_run_inversion_aggregator` (pre-LLM): the LLM-side
    surfaces canonical scene-shape transactions ("Garrick pockets the
    gold") and reveal-shape loot drops ("the chest reveals a longsword"),
    which the player-input pre-LLM hook structurally misses.

    quest_accept is NOT run here — S73.1 verified that LLM paraphrase
    misses canonical acceptance verbs; quest_accept stays at pre-LLM only.

    Layer B listener attribution for post-LLM fires: controller_id falls
    back to first-actor's Discord user_id from the batched actions. When
    not resolvable, Layer B post-LLM fires skip the OOC handshake and
    route through silent-log to avoid blocking on attribution ambiguity.

    Soft-fail throughout — aggregator never blocks downstream.
    """
    from transaction_completion_parser import (
        parse_transaction_completion, SURFACE_POST_LLM as TX_POST,
    )
    from loot_drop_parser import (
        parse_loot_drop, SURFACE_POST_LLM as LD_POST,
    )
    from inversion_telemetry import (
        emit_parse_outcome, emit_clarification_event, record_parser_invocation,
    )
    import clarification_handshake as ch

    # Second-pass detection mirrors pre-LLM hook.
    try:
        pending_meta = ch.get_pending_clarification(campaign_id)
    except Exception:
        pending_meta = None

    parser_results: list[ch.ParserResult] = []

    # ── Transaction-completion post-LLM ─────────────────────────────────
    try:
        scene_state = get_scene_state(campaign_id) or {}
        scene_loc = scene_state.get('current_location_id')
        recent_npcs = get_recently_active_npcs(campaign_id, limit=6,
                                                 location_id=scene_loc) or []
        inventory: list = []
        try:
            actor_name = (scene_state or {}).get('last_active_actor', '') or ''
            if actor_name:
                inventory = get_inventory(campaign_id, actor_name) or []
        except Exception:
            inventory = []
        tx_result = parse_transaction_completion(
            narration, recent_npcs, inventory, campaign_id,
            surface=TX_POST,
        )
    except Exception as e:
        log(f"inversion_v0_aggregator_post_llm: transaction_post parse error "
            f"campaign={campaign_id} err={e!r}")
        tx_result = {
            'fired': False, 'confidence': 'low', 'matched_verb': '',
            'currency': None, 'npc_name': '', 'item_name': '',
            'markers_present': False, 'surface': TX_POST,
            'dedup_suppressed': False, 'feature_disabled': False,
        }

    record_parser_invocation('transaction_completion_post',
                              tx_result.get('confidence', 'low'))

    tx_candidate = {}
    if tx_result.get('npc_name') or tx_result.get('currency'):
        c = tx_result.get('currency') or {}
        tx_candidate = {
            'npc': tx_result.get('npc_name', ''),
            'currency': f"{c.get('amount')}{c.get('denom')}" if c else '',
            'item': tx_result.get('item_name', ''),
            'title': 'transaction completion (LLM-side)',
        }
    parser_results.append(ch.ParserResult(
        domain='transaction_completion',
        confidence=tx_result.get('confidence', 'low'),
        fired=bool(tx_result.get('fired')),
        markers_present=bool(tx_result.get('markers_present')),
        dedup_suppressed=bool(tx_result.get('dedup_suppressed')),
        feature_disabled=bool(tx_result.get('feature_disabled')),
        candidate=tx_candidate,
    ))
    emit_parse_outcome(
        'transaction_completion_post', campaign_id, tx_result,
        route='engine' if tx_result.get('confidence') == 'high'
        else ('suggester' if tx_result.get('fired') else 'silent'),
    )

    # ── Loot-drop LLM-reveal ────────────────────────────────────────────
    try:
        pending = get_pending_loot(campaign_id) or []
        ld_result = parse_loot_drop(narration, pending, campaign_id,
                                    surface=LD_POST)
    except Exception as e:
        log(f"inversion_v0_aggregator_post_llm: loot_drop_llm parse error "
            f"campaign={campaign_id} err={e!r}")
        ld_result = {
            'fired': False, 'confidence': 'low', 'matched_verb': '',
            'matched_pending_loot_id': None, 'matched_item_name': '',
            'item_class_marker': '', 'container_marker': '',
            'markers_present': False, 'surface': LD_POST,
            'dedup_suppressed': False, 'feature_disabled': False,
        }

    record_parser_invocation('loot_drop_llm',
                              ld_result.get('confidence', 'low'))

    ld_candidate = {}
    if ld_result.get('matched_item_name') or ld_result.get('item_class_marker'):
        slash = ''
        if ld_result.get('matched_pending_loot_id'):
            slash = f"/loot claim {ld_result['matched_pending_loot_id']}"
        ld_candidate = {
            'item': (ld_result.get('matched_item_name')
                     or ld_result.get('item_class_marker', '')),
            'container': ld_result.get('container_marker', ''),
            'slash': slash,
            'title': 'loot reveal (LLM-side)',
        }
    parser_results.append(ch.ParserResult(
        domain='loot_drop_llm',
        confidence=ld_result.get('confidence', 'low'),
        fired=bool(ld_result.get('fired')),
        markers_present=bool(ld_result.get('markers_present')),
        dedup_suppressed=bool(ld_result.get('dedup_suppressed')),
        feature_disabled=bool(ld_result.get('feature_disabled')),
        candidate=ld_candidate,
    ))
    emit_parse_outcome(
        'loot_drop_llm', campaign_id, ld_result,
        route='engine' if ld_result.get('confidence') == 'high'
        else ('suggester' if ld_result.get('fired') else 'silent'),
    )

    # Stage 1 routing
    decision = ch.aggregate_parser_outputs(parser_results)

    # Second-pass branch: pending_clarification already set.
    if pending_meta is not None:
        highs = [r for r in parser_results
                 if r.confidence == 'high' and r.fired]
        if highs:
            ch.clear_pending_clarification(campaign_id)
            emit_clarification_event(
                'clarification_in_fiction_resolved',
                campaign_id,
                {
                    'parser_domains': [r.domain for r in highs],
                    'surface': 'post_llm',
                },
            )
            log(f"inversion_v0_aggregator_post_llm: second_pass_resolved "
                f"campaign={campaign_id} "
                f"domains={[r.domain for r in highs]}")
            return
        # Compliance-failure detection — pending was set and LLM narrated
        # something that the transaction parser hit MEDIUM/HIGH on. This
        # is the empirical signal the directive's MUST/MUST-NOT framing
        # failed to suppress completion narration.
        #
        # S81 refactor: fires via generic record_directive_compliance_failure
        # event per §82 candidate (S80 council Q6 generic-with-payload lock).
        # directive_name="pending_clarification" disambiguates per-directive
        # grep surface without schema coupling. Prior S77 event name
        # `clarification_in_fiction_compliance_failure` retired.
        any_fire = [r for r in parser_results if r.fired]
        if any_fire and tx_result.get('confidence') == 'high':
            from inversion_telemetry import record_directive_compliance_failure
            record_directive_compliance_failure(
                directive_name='pending_clarification',
                severity='HIGH',
                narration_excerpt=narration,
                detector='post_llm_parser_high_on_pending',
                campaign_id=campaign_id,
                confidence=0.9,
                directive_intent=(
                    "MUST NOT narrate the action as completed; "
                    "narrate scene continuing while pending"
                ),
            )
            log(f"inversion_v0_aggregator_post_llm: compliance_failure "
                f"campaign={campaign_id} "
                f"directive=pending_clarification "
                f"verb={tx_result.get('matched_verb')!r}")
        # Layer A/B fallback on post-LLM second-pass is a degraded surface
        # (no canonical operator-action context); skip OOC handshake.
        return

    # First-pass branch
    if decision.route == 'SILENT_LOG':
        return
    if decision.route == 'SINGLE_DOMAIN_CLEAR':
        # Post-LLM HIGH transaction or loot — render Phase-3a-style
        # suggester card for operator paste.
        if tx_result.get('fired') and tx_result.get('confidence') == 'high':
            await _post_dm_aside(
                guild,
                _format_transaction_post_llm_card(tx_result),
            )
            log(f"inversion_v0_aggregator_post_llm: single_domain_clear "
                f"campaign={campaign_id} domain=transaction_completion")
        if ld_result.get('fired') and ld_result.get('confidence') == 'high':
            await _post_dm_aside(
                guild,
                _format_loot_drop_llm_card(ld_result),
            )
            log(f"inversion_v0_aggregator_post_llm: single_domain_clear "
                f"campaign={campaign_id} domain=loot_drop_llm")
        return
    if decision.route == 'IN_FICTION_CLARIFICATION':
        # Post-LLM IN_FICTION is rare — would require the LLM narrating
        # ambiguous markers on its own. v0 surfaces this if it fires.
        trigger_event_id = f"campaign={campaign_id}:post_llm:ts={int(time.time())}"
        ch.set_pending_clarification(
            campaign_id=campaign_id,
            candidates=decision.candidates,
            trigger_event_id=trigger_event_id,
        )
        emit_clarification_event(
            'clarification_in_fiction_fired', campaign_id,
            {
                'parser_domains': [c.get('domain') for c in decision.candidates],
                'trigger_event_id': trigger_event_id,
                'layer': 'IN_FICTION',
                'surface': 'post_llm',
            },
        )
        log(f"inversion_v0_aggregator_post_llm: in_fiction_fired "
            f"campaign={campaign_id} candidates={len(decision.candidates)}")
        return
    if decision.route in ('LAYER_A', 'LAYER_B'):
        # Post-LLM Layer B is degraded surface — skip listener, route to
        # Layer A card or silent log to avoid attribution ambiguity.
        if decision.route == 'LAYER_A' or not controller_id:
            card = ch.build_layer_a_card(decision.candidates,
                                          narration_excerpt=narration[:140])
            if card:
                await _post_dm_aside(guild, card)
            emit_clarification_event(
                'clarification_layer_a_fired', campaign_id,
                {
                    'parser_domains': [c.get('domain') for c in decision.candidates],
                    'layer': 'A',
                    'surface': 'post_llm',
                },
            )
            log(f"inversion_v0_aggregator_post_llm: layer_a_fired "
                f"campaign={campaign_id}")
        return


def _format_transaction_post_llm_card(tx_result: dict) -> str:
    """Render the operator-side aside for a HIGH transaction-completion
    detection from the LLM narration. DM-voice copy per S78 UX pass.
    """
    c = tx_result.get('currency') or {}
    npc = tx_result.get('npc_name', '').strip()
    item = tx_result.get('item_name', '').strip()
    amt = f"{c.get('amount')}{c.get('denom')}" if c else ''

    context_bits = []
    if amt:
        context_bits.append(f"**{amt}**")
    if npc:
        context_bits.append(f"to **{npc}**")
    if item:
        context_bits.append(f"for **{item}**")
    context = ' '.join(context_bits) or 'a trade just happened'

    bookkeeping = (
        f"`!game coin -{amt}`" if amt else "`!game coin -?gp` (fill in the amount)"
    )
    return (
        f"*Looks like a trade just landed in narration — {context}. "
        f"Paste {bookkeeping} for Avrae bookkeeping, or skip if the "
        f"narration didn't actually commit anything.*"
    )


def _format_loot_drop_llm_card(ld_result: dict) -> str:
    """Render the operator-side aside for a HIGH loot-drop reveal
    detection from the LLM narration. DM-voice copy.
    """
    item = ld_result.get('matched_item_name', '').strip()
    loot_id = ld_result.get('matched_pending_loot_id')
    container = ld_result.get('container_marker', '').strip()
    slash = f"`/loot claim {loot_id}`" if loot_id else "`/loot list`"
    container_phrase = f" from the {container}" if container else ''
    item_phrase = f"**{item}**" if item else 'something'
    return (
        f"*The narration just revealed {item_phrase}{container_phrase}. "
        f"Paste {slash} to surface and claim it, or skip if the reveal "
        f"was just flavor.*"
    )


async def _dispatch_clarification_fallback(campaign_id: int, decision,
                                          narration: str, guild,
                                          controller_id: str,
                                          trigger_message,
                                          fallback: bool = False) -> None:
    """Render and post the Layer A or Layer B card. fallback=True means
    we're escalating from a still-ambiguous second-pass; emit the
    *_fallback_fired event so production telemetry can distinguish direct
    cross-domain ambiguity from in-fiction-escalation cases.
    """
    from inversion_telemetry import emit_clarification_event
    import clarification_handshake as ch

    if decision.route == 'LAYER_A':
        card = ch.build_layer_a_card(decision.candidates,
                                     narration_excerpt=narration)
        if card:
            await _post_dm_aside(guild, card)
        # Post-S78 live-verify race fix: set pending_clarification so the
        # narration pipeline (which fires ~15s later via the batcher) reads
        # the pending flag and the LLM narrates the scene continuing
        # WITHOUT finalizing the action. Operator paste of the card's slash
        # commits via §17. The next operator narration's aggregator pass
        # clears pending (existing pending-clear logic).
        trigger_event_id = f"campaign={campaign_id}:layer_a:ts={int(time.time())}"
        if not fallback:
            ch.set_pending_clarification(
                campaign_id=campaign_id,
                candidates=decision.candidates,
                trigger_event_id=trigger_event_id,
            )
        emit_clarification_event(
            'clarification_layer_a_fallback_fired' if fallback
            else 'clarification_layer_a_fired',
            campaign_id,
            {
                'parser_domains': [c.get('domain') for c in decision.candidates],
                'layer': 'A',
                'fallback': fallback,
            },
        )
        if fallback:
            ch.clear_pending_clarification(campaign_id)
        log(f"inversion_v0_aggregator: layer_a_fired "
            f"campaign={campaign_id} candidates={len(decision.candidates)} "
            f"fallback={int(fallback)} pending_set={int(not fallback)}")
        return

    if decision.route == 'LAYER_B':
        question = ch.build_layer_b_question(decision.candidates,
                                             narration_excerpt=narration)
        if question:
            await _post_dm_aside(guild, question)

        # Post-S78 live-verify race fix: set pending_clarification so the
        # narration pipeline reads it and the LLM narrates the scene
        # continuing without finalizing. Operator reply (number or domain)
        # resolves via the listener.
        trigger_event_id = f"campaign={campaign_id}:ts={int(time.time())}"
        if not fallback:
            ch.set_pending_clarification(
                campaign_id=campaign_id,
                candidates=decision.candidates,
                trigger_event_id=trigger_event_id,
            )

        session = ch.ClarificationSession(
            campaign_id=campaign_id,
            controller_id=controller_id,
            trigger_event_id=trigger_event_id,
            candidates=decision.candidates,
            layer='B',
            status='PENDING',
            created_at=time.time(),
            timeout_at=time.time() + ch.LAYER_B_TIMEOUT_SECONDS,
        )
        registered = ch.add_session(session)
        if not registered:
            emit_clarification_event(
                'clarification_cap_hit', campaign_id,
                {
                    'parser_domains': [c.get('domain') for c in decision.candidates],
                    'fallback': fallback,
                },
            )
            log(f"inversion_v0_aggregator: layer_b_cap_hit "
                f"campaign={campaign_id}")
            return

        emit_clarification_event(
            'clarification_layer_b_fallback_fired' if fallback
            else 'clarification_layer_b_fired',
            campaign_id,
            {
                'parser_domains': [c.get('domain') for c in decision.candidates],
                'layer': 'B',
                'fallback': fallback,
                'trigger_event_id': trigger_event_id,
            },
        )
        log(f"inversion_v0_aggregator: layer_b_fired "
            f"campaign={campaign_id} candidates={len(decision.candidates)} "
            f"fallback={int(fallback)}")

        # Wait for OOC reply.
        try:
            aside_channel = get_channel(guild, 'aside')
            channel_id = aside_channel.id if aside_channel else None
        except Exception:
            channel_id = None
        if not channel_id:
            ch.cancel_session(session, 'EXPIRED')
            # Pending is set on direct routes (post-S78 race fix) as well
            # as fallback routes — clear unconditionally on resolution
            # (idempotent if no state set).
            ch.clear_pending_clarification(campaign_id)
            return

        bot_ref = trigger_message._state._get_client() if trigger_message else None
        if bot_ref is None:
            # Best-effort fallback — discord.py's Bot is available via the
            # module global `bot` if we're in the on_message handler chain.
            bot_ref = globals().get('bot')
        if bot_ref is None:
            ch.cancel_session(session, 'EXPIRED')
            # Pending is set on direct routes (post-S78 race fix) as well
            # as fallback routes — clear unconditionally on resolution
            # (idempotent if no state set).
            ch.clear_pending_clarification(campaign_id)
            return

        reply = await ch.await_layer_b_reply(
            bot_ref, channel_id, controller_id,
            trigger_timestamp=session.created_at,
        )
        if reply is None:
            # Timeout — silent expiry per §11.5 lock.
            emit_clarification_event(
                'clarification_expired', campaign_id,
                {'trigger_event_id': trigger_event_id, 'layer': 'B'},
            )
            ch.cancel_session(session, 'EXPIRED')
            # Pending is set on direct routes (post-S78 race fix) as well
            # as fallback routes — clear unconditionally on resolution
            # (idempotent if no state set).
            ch.clear_pending_clarification(campaign_id)
            return

        reply_intent = ch.parse_layer_b_reply(
            reply.content or '', decision.candidates,
        )
        intent_kind = reply_intent.get('intent', 'AMBIGUOUS')

        if intent_kind == 'EXPLICIT_SKIP':
            emit_clarification_event(
                'clarification_skipped', campaign_id,
                {'trigger_event_id': trigger_event_id, 'layer': 'B'},
            )
            ch.cancel_session(session, 'RESOLVED')
            ch.clear_pending_clarification(campaign_id)
            return

        if intent_kind.startswith('COMMIT_'):
            emit_clarification_event(
                'clarification_resolved', campaign_id,
                {
                    'trigger_event_id': trigger_event_id,
                    'layer': 'B',
                    'matched_domain': reply_intent.get('matched_domain', ''),
                    'time_to_resolve_ms': int(
                        (time.time() - session.created_at) * 1000
                    ),
                },
            )
            ch.cancel_session(session, 'RESOLVED')
            ch.clear_pending_clarification(campaign_id)
            # The §17 writer for the matched domain fires via the standard
            # operator-paste flow. Layer B v0 surfaces the OOC reply as
            # "operator-deliberate-commit" per council Shape A.2 lock; the
            # downstream writer hookup ships at the per-domain Phase 3b
            # parser registration. v0 quest_accept only: no auto-writer
            # invocation here yet.
            return

        # AMBIGUOUS reply — recursion handling.
        session.recursion_iteration += 1
        if session.recursion_iteration < ch.LAYER_B_RECURSION_MAX:
            recursion_card = ch.build_layer_b_recursion_card(
                decision.candidates, session.recursion_iteration,
            )
            await _post_dm_aside(guild, recursion_card)
            emit_clarification_event(
                'clarification_recursion_escalated', campaign_id,
                {
                    'trigger_event_id': trigger_event_id,
                    'iteration': session.recursion_iteration,
                },
            )
            # Recursion listener wait — same channel + controller filter.
            reply2 = await ch.await_layer_b_reply(
                bot_ref, channel_id, controller_id,
                trigger_timestamp=time.time(),
            )
            if reply2 is None:
                emit_clarification_event(
                    'clarification_expired', campaign_id,
                    {'trigger_event_id': trigger_event_id, 'layer': 'B',
                     'iteration': session.recursion_iteration},
                )
            else:
                intent2 = ch.parse_layer_b_reply(
                    reply2.content or '', decision.candidates,
                )
                if intent2.get('intent', '').startswith('COMMIT_'):
                    emit_clarification_event(
                        'clarification_resolved', campaign_id,
                        {
                            'trigger_event_id': trigger_event_id,
                            'iteration': session.recursion_iteration,
                            'matched_domain': intent2.get('matched_domain', ''),
                        },
                    )
                elif intent2.get('intent') == 'EXPLICIT_SKIP':
                    emit_clarification_event(
                        'clarification_skipped', campaign_id,
                        {'trigger_event_id': trigger_event_id,
                         'iteration': session.recursion_iteration},
                    )
                else:
                    # Still ambiguous on second attempt — manual decision card.
                    manual_card = ch._build_layer_b_manual_card(decision.candidates)
                    await _post_dm_aside(guild, manual_card)
                    emit_clarification_event(
                        'clarification_recursion_manual', campaign_id,
                        {'trigger_event_id': trigger_event_id,
                         'iteration': session.recursion_iteration},
                    )
        else:
            manual_card = ch._build_layer_b_manual_card(decision.candidates)
            await _post_dm_aside(guild, manual_card)
            emit_clarification_event(
                'clarification_recursion_manual', campaign_id,
                {'trigger_event_id': trigger_event_id,
                 'iteration': session.recursion_iteration},
            )

        ch.cancel_session(session, 'RESOLVED')
        ch.clear_pending_clarification(campaign_id)


def _format_quest_acceptance_suggester_card(result: dict,
                                             offered: list) -> str:
    """Render the inversion-v0 quest-acceptance suggester card.

    Format per R4 precedent (5 existing card sites) + Reading-2 direct
    (Quest Layer v0.1 post-S57 crystallization — no in-character dialogue;
    pure operational suggestion).

    High-confidence: single quest match → render direct pasteable /quest accept.
    Medium-confidence: verb only, no match → list offered quests for operator.
    """
    confidence = result.get('confidence', 'low')
    verb = (result.get('matched_verb') or '').strip()
    if confidence == 'high':
        qid = result.get('matched_quest_id')
        title = (result.get('matched_quest_title') or '').strip() or '(untitled)'
        return (
            f"**[QUEST ACCEPTANCE DETECTED]**\n"
            f"Confidence: **high** — narration verb _{verb!r}_ matched offered "
            f"quest #{qid}: **{title}**\n\n"
            f"_Run `/quest accept {qid}` to flip the quest to in-progress, "
            f"or ignore if the narration didn't intend acceptance._"
        )
    # MEDIUM
    if not offered:
        # Verb fired but no offered quests exist — operator may want to know.
        return (
            f"**[QUEST ACCEPTANCE DETECTED — no offered quests]**\n"
            f"Confidence: **medium** — narration verb _{verb!r}_ suggested "
            f"acceptance but no quests are currently at status=offered.\n\n"
            f"_If a quest offer was just made and isn't tracked, "
            f"run `/quest add` to register it before accepting._"
        )
    listing_lines = []
    for q in offered[:5]:
        qid = q.get('id')
        title = (q.get('title') or '').strip() or '(untitled)'
        listing_lines.append(f"  • Quest #{qid}: **{title}** — "
                              f"`/quest accept {qid}`")
    listing = '\n'.join(listing_lines)
    more_suffix = ''
    if len(offered) > 5:
        more_suffix = f"\n_(+{len(offered) - 5} more — see `/quest list`)_"
    return (
        f"**[QUEST ACCEPTANCE DETECTED]**\n"
        f"Confidence: **medium** — narration verb _{verb!r}_ suggested "
        f"acceptance but no offered quest title matched.\n"
        f"Currently offered:\n{listing}{more_suffix}\n\n"
        f"_Run the appropriate `/quest accept <id>` to flip, "
        f"or ignore if narration didn't intend acceptance._"
    )


def _lock_npc_pronouns_from_narration(campaign_id: int, narration: str,
                                       npcs: list) -> int:
    """S68 N-4 — scan narration for pronouns near each NPC name; lock first
    occurrence via `npc_pronouns_set` if `pronouns` is currently empty.

    Returns count of NPCs locked this call. Idempotent — NPCs with already-
    locked pronouns are skipped.

    Per N-10 v0.1 forward-coupling: bootstrap-NPCs carry pronouns in first
    sentence of description (backfill picks those up at engine init); this
    pass handles emergent NPCs introduced in narration without pre-set
    pronouns.
    """
    from dnd_engine import npc_pronouns_set, npc_pronouns_get, npc_get_by_name
    from dnd_engine import extract_pronouns_from_text
    if not narration or not npcs:
        return 0
    locked = 0
    for n in npcs:
        name = (n.get('name') or '').strip()
        if not name:
            continue
        try:
            existing_row = npc_get_by_name(campaign_id, name)
        except Exception:
            continue
        if not existing_row:
            continue
        npc_id = existing_row['id']
        # Skip if already locked
        if (existing_row.get('pronouns') or '').strip():
            continue
        # Find a window of ~200 chars around the first mention of the NPC
        # name in narration and extract pronouns from that window.
        lower_narration = narration.lower()
        lower_name = name.lower()
        idx = lower_narration.find(lower_name)
        if idx < 0:
            # NPC parsed but name doesn't appear verbatim — try first token
            first_token = name.split()[0].lower() if name.split() else lower_name
            idx = lower_narration.find(first_token)
        if idx < 0:
            continue
        window_start = max(0, idx - 200)
        window_end = min(len(narration), idx + len(name) + 300)
        window = narration[window_start:window_end]
        canonical, conflicts = extract_pronouns_from_text(window)
        if not canonical:
            continue
        ok = npc_pronouns_set(npc_id, canonical)
        if ok:
            locked += 1
            log(f"npc_pronoun_locked: campaign={campaign_id} "
                f"npc_id={npc_id} name={name!r} pronouns={canonical!r} "
                f"source=narration")
            if conflicts:
                log(f"npc_pronoun_conflict: campaign={campaign_id} "
                    f"npc_id={npc_id} name={name!r} "
                    f"locked={canonical!r} also_found={conflicts}")
    if locked:
        log(f"npc_pronoun_live_lock: campaign={campaign_id} locked={locked}")
    return locked


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
                                suppress_for_combat_narration: bool = False,
                                scene_lifecycle_inputs: dict = None):
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

        # Scene Lifecycle v1 — build inputs for compute_scene_lifecycle_directive.
        # Snapshot stale counter BEFORE narration posts (counter is the signal
        # that this turn's directive computes against; update happens after post).
        # §1.F.b: Avrae roll consumed this turn → activity signal → will reset counter.
        _sl_guild_id_int = int(guild_id_str)
        _sl_had_avrae_roll = bool(avrae_events)
        if scene_lifecycle_inputs is None:
            _sl_stale = _get_scene_stale(_sl_guild_id_int)
            scene_lifecycle_inputs = {
                'stale_turns': _sl_stale,
                'trigger_kind': 'auto',
                'last_combat_had_beats': _last_combat_had_beats.get(_sl_guild_id_int, False),
                # §11.L: counter was reset at combat start (§11.I), so stale_turns
                # is a valid proxy for turns since last combat end in exploration.
                'turns_since_combat_end': _sl_stale,
                'explicit_reason': '',
            }

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
                    scene_lifecycle_inputs,
                )
        except (discord.HTTPException, asyncio.TimeoutError) as e:
            log(f"typing_indicator_failed: command=_dm_respond_and_post err={e!r}")
            response = await asyncio.to_thread(
                dm_respond, campaign, characters, combined_action, avrae_events,
                actor_names, transition_context, first_user_id, actions,
                resolution_result, False, scene_lifecycle_inputs,
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
        # S67 Fix 2 Phase B (F-016 close) — dnd_campaigns.current_scene is no
        # longer written. The LLM-narration → self-summary loop (4/4 §76
        # contamination surface, unmitigated) is closed. Scene-detail memory
        # flows via: (a) authoritative SCENE STATE block (structured
        # fields), (b) chroma RELEVANT PAST EVENTS (distance-cutoff mitigated),
        # (c) last_dm_response for signal extraction (not prose re-injection).
        # The `current_scene` column stays in schema for now (cleanup deferred
        # to a post-Tier-1 schema sweep); the read paths in build_dm_context
        # and dm_respond's scene_blurb were redirected to last_dm_response.

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
        # S73.2 — Focused-quest reminder (single quest, not comma-list).
        # Resolves via dnd_scene_state.current_act_id when authored
        # (Composition Layer anchor), else falls back to most-recently-
        # accepted in-progress quest. `/quest list` is the full-ledger view.
        # Soft failure — quest state is advisory UX.
        try:
            focused = get_focused_quest(campaign['id'])
            if focused:
                title = (focused.get('title') or focused.get('name') or '').strip()
                if title:
                    quest_line = f"🗒️ {title}"
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

        asyncio.create_task(_attach_hints(msg, embed, response, campaign["id"]))
        asyncio.create_task(_extract_and_persist_world(
            campaign["id"], response, guild, guild_id_int=_sl_guild_id_int
        ))
        # §1b.1 Phase 3b post-LLM aggregator (S78). Fires transaction-
        # completion + loot-drop parsers against the LLM narration. Distinct
        # from the pre-LLM hook at on_message:2727 which scans player input.
        # Post-LLM surface captures LLM-paraphrased transaction completion
        # ("Garrick pockets the gold") and LLM reveal narration ("the chest
        # reveals a longsword"). Soft-fail per S77 discipline.
        try:
            asyncio.create_task(_run_inversion_aggregator_post_llm(
                campaign["id"], response, guild, first_user_id or '',
            ))
        except Exception as _post_llm_e:
            log(f"inversion_v0_aggregator_post_llm: scheduling error "
                f"campaign={campaign['id']} err={_post_llm_e!r}")
        # §82 candidate — central_thread compliance detector (S81). Fires
        # post-LLM heuristic scan for thread-content tokens in narration.
        # Telemetry only; no state mutation. Empirical signal for prompt
        # iteration per §82 architectural-design-time guidance.
        try:
            asyncio.create_task(_run_central_thread_compliance_check(
                campaign["id"], response,
            ))
        except Exception as _ct_e:
            log(f"central_thread_compliance: scheduling error "
                f"campaign={campaign['id']} err={_ct_e!r}")

        # Scene Lifecycle v1 — update stale counter AFTER posting (§1.F).
        # §1.F.b: Avrae roll consumed → reset (something mechanical happened).
        # Otherwise: increment toward soft/hard threshold.
        try:
            if _sl_had_avrae_roll:
                _reset_scene_stale(_sl_guild_id_int)
                log(f"scene_lifecycle_reset: campaign={campaign['id']} "
                    f"guild={_sl_guild_id_int} reason=avrae_roll")
            else:
                _new_stale = _increment_scene_stale(_sl_guild_id_int)
                log(f"scene_lifecycle_increment: campaign={campaign['id']} "
                    f"guild={_sl_guild_id_int} stale_turns={_new_stale}")
        except Exception as e:
            log(f"scene_lifecycle_counter_update: error={e!r}")

        # Quest Layer v0 (S56) — fire suggester after narration posts.
        # §1b third-instance: canonical-slash + auxiliary-cosine framing.
        # Suggester writes nothing; on proposal, posts card to #dm-aside
        # and caches proposal for paste-detection. Operator approves via
        # paste-match OR explicit /quest accept <id>. Soft-fail throughout.
        try:
            _scene_for_quest = get_scene_state(campaign['id'])
            await _dispatch_quest_offer_suggester(
                campaign, guild, _scene_for_quest
            )
        except Exception as e:
            log(f"quest_offer_dispatch_outer: error={e!r}")

        # Composition Layer v0 (S60) §11.9 — compression-coupled act-
        # transition suggester. Fires only when the stale counter has hit
        # _STALE_SOFT_THRESHOLD (the same trigger that fires the Scene
        # Lifecycle directive's soft/strong tier). Mirrors compression
        # cadence — natural narrative-pause moment. Per locked §11.12:
        # canonical /quest act advance slash gate; deterministic-validator
        # predicate (Reading-2 direct, no cosine-similarity).
        try:
            _post_stale = _get_scene_stale(_sl_guild_id_int)
            if _post_stale >= orch._STALE_SOFT_THRESHOLD:
                _scene_for_act = get_scene_state(campaign['id'])
                await _dispatch_quest_act_suggester(
                    campaign, guild, _scene_for_act
                )
        except Exception as e:
            log(f"quest_act_suggester_dispatch_outer: error={e!r}")
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

    # §11.O: session-open is a hard reset for the stale counter. A new /play
    # call signals a fresh narrative context; any prior stale count must not
    # carry into the opening turn and immediately fire a lifecycle directive.
    if interaction.guild_id:
        _reset_scene_stale(interaction.guild_id)
        _last_combat_had_beats.pop(interaction.guild_id, None)

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
    # Ship 2 (S39) dropped `seed` parameter behavior — the `scene` slash
    # argument is preserved in the signature for back-compat but is no
    # longer consumed downstream. S65 Fix 1 (F-021): replace the legacy
    # `{seed}` reference (NameError) with `{scene or ''}`. When `/play` is
    # invoked without the optional `scene` arg, the bracketed marker becomes
    # `[Open the scene] ` — classifier still routes it (META prefix is the
    # `[Open` bracket-frame), narration falls back to the regular DM-respond
    # opening logic.
    _seed_text = scene or ''
    try:
        async with narration_ch.typing():
            opening = await asyncio.to_thread(
                dm_respond, campaign, chars, f"[Open the scene] {_seed_text}", [],
                None
            )
    except (discord.HTTPException, asyncio.TimeoutError) as e:
        log(f"typing_indicator_failed: command=play err={e!r}")
        opening = await asyncio.to_thread(
            dm_respond, campaign, chars, f"[Open the scene] {_seed_text}", [],
            None
        )

    chroma_store(campaign['id'], 'dm', opening)
    # S67 Fix 2 Phase B — current_scene write retired. /play's opening
    # narration lands in chroma (for retrieval) and last_dm_response (via
    # dm_respond's persist call) — no need for the separate prose-snapshot.

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


@bot.tree.command(name='compress', description='[DM] Explicitly compress the current scene.')
@app_commands.describe(reason='Optional context for the compression (e.g. "we have covered everything here")')
async def compress(interaction: discord.Interaction, reason: str = ''):
    """DM-only explicit scene compression (Scene Lifecycle v1, §1.H).

    Fires compute_scene_lifecycle_directive with trigger_kind='explicit' regardless
    of the current stale counter. DM authority over scene transition is final.
    Resets the stale counter after dispatch (§11.J). Mode gate: refuses in combat.
    """
    if not is_dm_or_creator(interaction):
        await interaction.response.send_message("DM or campaign owner only.", ephemeral=True)
        return
    guild_id_str = str(interaction.guild_id)
    campaign = get_active_campaign(guild_id_str)
    if not campaign:
        await interaction.response.send_message("No active campaign.", ephemeral=True)
        return
    scene = get_scene_state(campaign['id'])
    if not scene:
        await interaction.response.send_message(
            "No active scene — run `/play` first.", ephemeral=True
        )
        return
    mode = (scene.get('mode') or 'exploration').lower()
    if mode == 'combat':
        await interaction.response.send_message(
            "Scene compression is not available in combat mode.", ephemeral=True
        )
        return

    narration_ch = get_channel(interaction.guild, 'narration')
    if not narration_ch:
        await interaction.response.send_message(
            f"Missing #{CHANNEL_NAMES['narration']}. Run `/setup` first.", ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True)

    try:
        characters = get_characters(campaign['id'])
        reason_str = (reason or '').strip()
        combined_action = (
            f"[Scene Lifecycle: DM-initiated compression"
            + (f": {reason_str}" if reason_str else "")
            + "]"
        )
        _compress_inputs = {
            'stale_turns': _get_scene_stale(interaction.guild_id or 0),
            'trigger_kind': 'explicit',
            'last_combat_had_beats': _last_combat_had_beats.get(
                interaction.guild_id or 0, False
            ),
            'turns_since_combat_end': 9999,
            'explicit_reason': reason_str,
        }
        await _dm_respond_and_post(
            campaign, characters,
            actions=[('[DM]', combined_action)],
            combined_action=combined_action,
            scene_lifecycle_inputs=_compress_inputs,
        )
        # §11.J: explicit compression resets the stale counter — DM intent
        # is that the scene is being closed; start fresh.
        if interaction.guild_id:
            _reset_scene_stale(interaction.guild_id)
        log(f"/compress: campaign={campaign['id']} guild={guild_id_str} "
            f"reason={reason_str!r}")
        await interaction.followup.send(
            f"{E.get('ok', '✅')} Scene compression triggered.", ephemeral=True
        )
    except Exception as e:
        log(f"/compress: error={e!r}")
        await interaction.followup.send(
            "Scene compression failed — check journal for details.", ephemeral=True
        )


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
    #
    # S66 Fix 1 — floor-at-one-phase rule. Any /travel call advances at
    # least one phase. Parser returns (0,0) for sub-phase durations
    # ('5 minutes') and None for unparseable input ('banana'); both
    # floor to (0, 1). Embed below reports the ACTUAL applied delta
    # rather than echoing raw input (the pre-S66 "Midday → Afternoon
    # despite '1 hour' input" surprise was a truthfulness gap, not a
    # math bug — the parser already returned (0,1) for '1 hour', but
    # the user never saw that.)
    parsed = parse_elapsed(elapsed) or (0, 0)
    days_d, phase_d = parsed
    floor_applied = False
    if days_d == 0 and phase_d == 0:
        days_d, phase_d = 0, 1
        floor_applied = True
        log(f"/travel: floor-at-1-phase applied campaign={campaign['id']} "
            f"elapsed={elapsed!r}")
    ta = None
    try:
        ta = advance_time(
            campaign['id'], days_d, phase_d,
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

    # §1.F.a: location change is an activity signal — reset stale counter.
    # §1.F.d: advance_time (via travel) is also an activity signal.
    # Both fire on /travel; a single reset covers both.
    if interaction.guild_id:
        _reset_scene_stale(interaction.guild_id)
        log(f"scene_lifecycle_reset: campaign={campaign['id']} "
            f"guild={interaction.guild_id} reason=travel_location_change "
            f"dest={dest_canonical!r}")

    log(f"/travel: campaign={campaign['id']} from={origin_name!r} "
        f"to={dest_canonical!r} resolved={1 if dest_loc else 0} "
        f"created={1 if created else 0}")

    # The synthetic player_action is human-readable so chat history stays
    # coherent, but the LLM's behavior is dominated by the transition_block.
    synthetic_action = f"The party travels to {dest_canonical}."

    # Acknowledge to player immediately. The DM call may take a few seconds.
    # S66 Fix 1C — truthful embed. Report the ACTUAL applied delta so the
    # operator sees the phase math, not just the elapsed input string.
    if ta:
        delta_parts = []
        if ta.days_delta:
            delta_parts.append(f"{ta.days_delta}d")
        if ta.resolved_phase_delta:
            delta_parts.append(
                f"{ta.resolved_phase_delta} phase"
                f"{'s' if ta.resolved_phase_delta != 1 else ''}"
            )
        delta_str = " + ".join(delta_parts) or "no change"
        floor_note = " — defaulted to 1 phase" if floor_applied else ""
        timing = (
            f" — advanced {delta_str} "
            f"({ta.before_phase} → {ta.after_phase}){floor_note}"
        )
    else:
        timing = ""
    await interaction.response.send_message(
        f"{E.get('ok', '✅')} Travel: **{origin_name}** → **{dest_canonical}** "
        f"(input: `{elapsed}`){timing}. The DM is opening the arrival scene...",
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
@app_commands.describe(status='Filter by status (default: in-progress)')
@app_commands.choices(status=[
    app_commands.Choice(name='offered', value='offered'),
    app_commands.Choice(name='in-progress', value='in-progress'),
    app_commands.Choice(name='completed', value='completed'),
    app_commands.Choice(name='failed', value='failed'),
    app_commands.Choice(name='abandoned', value='abandoned'),
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
    status_value = status.value if status else 'in-progress'
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
    status_icon = {
        'offered': '?', 'in-progress': '⚔', 'completed': '✓',
        'delivered': '✓',  # legacy alias rows display same icon
        'failed': '✗', 'abandoned': '…',
    }
    for q in quests:
        icon = status_icon.get(q['status'], '•')
        pri = q.get('priority', 'normal')
        pri_tag = f" [{pri}]" if pri != 'normal' else ''
        given = q.get('given_by', '')
        given_tag = f" — {given}" if given else ''
        summary = q.get('summary', '')
        summary_tag = f"\n   _{summary}_" if summary else ''
        reward = (q.get('reward_summary') or '').strip()
        reward_tag = f"\n   _reward: {reward}_" if reward else ''
        lines.append(
            f"{icon} **#{q['id']}** [{q['status']}] {q['title']}"
            f"{pri_tag}{given_tag}{summary_tag}{reward_tag}"
        )
    body = "\n".join(lines)
    if len(body) > 1900:
        body = body[:1900] + "\n…(truncated — too many quests to display)"
    await interaction.response.send_message(body, ephemeral=True)


@quest_group.command(name='complete',
                     description='[DM] Mark a quest completed — fires reward dispatch.')
@app_commands.describe(quest_id='Quest to complete')
@app_commands.autocomplete(quest_id=quest_id_autocomplete)
async def quest_complete_cmd(interaction: discord.Interaction, quest_id: int):
    """Canonical resolution command. Engine helper `quest_deliver` performs
    the state transition; the slash command was renamed in S61 v0.x patch
    (operator preference — "complete" reads more plainly than "deliver").
    Status enum value: 'completed'."""
    if not is_dm_or_creator(interaction):
        await interaction.response.send_message("DM or campaign owner only.", ephemeral=True)
        return
    campaign = get_active_campaign(str(interaction.guild_id))
    if not campaign:
        await interaction.response.send_message("No active campaign.", ephemeral=True)
        return
    # Route through quest_deliver to get reward-dispatch behavior (§11.6).
    await _do_quest_deliver(interaction, campaign, quest_id)


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


# ─────────────────────────────────────────────────────────
# Quest Layer v0 (S56) — new slash commands per §11.7
# /quest offer, /quest accept, /quest deliver, /quest abandon,
# /quest seed-skeleton. Existing add/list/complete/fail/delete preserved.
# ─────────────────────────────────────────────────────────

# /quest offer DROPPED in S61 v0.x patch — auto-fire suggester via
# compression-coupled path covers the practical surface; manual fire was
# never observed in live verify. Operator can still trigger an offer via
# editing skeleton.md + /quest seed if they want a specific quest to surface.


@quest_group.command(name='accept',
                     description='[DM] Canonical §1b gate — offered → in-progress.')
@app_commands.describe(quest_id='Quest to accept (must be at status=offered)')
@app_commands.autocomplete(quest_id=quest_id_autocomplete)
async def quest_accept_cmd(interaction: discord.Interaction, quest_id: int):
    """Canonical §1b deterministic gate per §11.12 Reading-2 (v0.1 patch).
    Transitions a quest from offered → in-progress. Refuses non-offered
    prior status."""
    if not is_dm_or_creator(interaction):
        await interaction.response.send_message("DM or campaign owner only.", ephemeral=True)
        return
    campaign = get_active_campaign(str(interaction.guild_id))
    if not campaign:
        await interaction.response.send_message("No active campaign.", ephemeral=True)
        return
    current_turn = get_turn_counter(campaign['id'])
    if quest_accept(campaign['id'], quest_id, accepted_turn=current_turn,
                    source='accept'):
        await interaction.response.send_message(
            f"{E['ok']} Quest #{quest_id} accepted (in-progress).",
            ephemeral=True
        )
    else:
        # Refusal reason already logged at the engine layer.
        await interaction.response.send_message(
            f"{E['facepalm']} Cannot accept #{quest_id} — must be at "
            f"status='offered'. Check `/quest list status:offered`.",
            ephemeral=True
        )


async def _do_quest_deliver(interaction: discord.Interaction, campaign: dict,
                             quest_id: int) -> None:
    """Shared implementation of /quest deliver and /quest complete (alias).
    Transitions in-progress → delivered, dispatches reward summary to
    #dm-aside, auto-adds parseable items to inventory."""
    current_turn = get_turn_counter(campaign['id'])
    result = quest_deliver(campaign['id'], quest_id, delivered_turn=current_turn)
    if result is None:
        await interaction.response.send_message(
            f"{E['facepalm']} Cannot deliver #{quest_id} — must be at "
            f"status='in-progress'.", ephemeral=True
        )
        return
    # §11.6 (d) hybrid: aside post + auto-inventory.
    # S66 Fix 2 (F-031 close) — quest rewards land in PARTY_STASH_BUCKET
    # (__party__), NOT in an empty-string bucket (the pre-S66 bug — empty
    # character_name made add_item return action='invalid' silently, and
    # the inv_lines below would falsely report success). The bucket is a
    # party-shared sentinel; /inventory surfaces it separately from
    # individual character inventories.
    reward = result.get('reward_summary', '') or '(unspecified)'
    title = result.get('title', f'#{quest_id}')
    parsed_items = _parse_reward_summary_for_inventory(
        result.get('reward_summary', '')
    )
    inv_lines = []
    inv_failed = []
    for item in parsed_items:
        try:
            add_result = add_item(
                campaign['id'], PARTY_STASH_BUCKET,
                item['name'], item['quantity']
            )
            action = (add_result or {}).get('action', 'unknown')
            if action in ('inserted', 'incremented'):
                inv_lines.append(
                    f"  + {item['name']} ×{item['quantity']} "
                    f"→ party stash ({action})"
                )
                log(f"quest_delivered: campaign={campaign['id']} "
                    f"quest_id={quest_id} item={item['name']!r} "
                    f"qty={item['quantity']} party_stash=true "
                    f"add_item_result={action}")
            else:
                inv_failed.append(
                    f"  ! {item['name']} ×{item['quantity']} "
                    f"(add_item returned action={action})"
                )
                log(f"quest_delivered: campaign={campaign['id']} "
                    f"quest_id={quest_id} item={item['name']!r} "
                    f"qty={item['quantity']} party_stash=true "
                    f"add_item_result={action} ERROR")
        except Exception as e:
            log(f"quest_deliver_inventory_add: error item={item!r} err={e!r}")
            inv_failed.append(
                f"  ! {item['name']} ×{item['quantity']} (add failed: {e})"
            )
    aside_text = (
        f"**[REWARD READY]** Quest #{quest_id} delivered: **{title}**.\n"
        f"Reward: {reward}\n"
    )
    # S66 Fix 2 — truthful aside. Success and failure are reported
    # separately so the operator can't be misled into thinking items
    # landed when they didn't (the pre-S66 bug — empty bucket made every
    # add_item silently return 'invalid', but the operator saw "+item"
    # lines anyway).
    if inv_lines:
        aside_text += (
            f"\n**Auto-added to party stash:**\n"
            + "\n".join(inv_lines) + "\n"
        )
    if inv_failed:
        aside_text += (
            f"\n**⚠ Inventory add FAILED for:**\n"
            + "\n".join(inv_failed) + "\n"
            f"_(Check `add_item` logs; reward may need manual `/giveitem`.)_\n"
        )
    if not inv_lines and not inv_failed:
        aside_text += f"\n_(No structured items parsed; reward stays narrative.)_\n"
    # Suggested narration line for operator paste (§11.6 (b) seed).
    aside_text += (
        f"\nSuggested narration: \"The {title.lower()} has been seen through "
        f"to its end. The reward — {reward} — passes hands. The road continues.\"\n"
        f"_Paste into #dm-narration when the reward scene resolves._"
    )
    await _post_dm_aside(interaction.guild, aside_text)
    log(f"quest_deliver_dispatch: campaign={campaign['id']} quest_id={quest_id} "
        f"items_parsed={len(parsed_items)} reward='{reward}'")
    await interaction.response.send_message(
        f"{E['ok']} Quest #{quest_id} delivered. Reward summary + inventory "
        f"updates posted to #dm-aside.", ephemeral=True
    )


# /quest deliver DROPPED in S61 v0.x patch — `/quest complete` is the
# canonical operator slash going forward. The engine helper `quest_deliver`
# remains as the underlying state-transition function (preserved name for
# code-side back-compat); only the slash command surface flipped.


@quest_group.command(name='abandon',
                     description='[DM] Mark a quest abandoned (party walked away).')
@app_commands.describe(quest_id='Quest to abandon')
@app_commands.autocomplete(quest_id=quest_id_autocomplete)
async def quest_abandon_cmd(interaction: discord.Interaction, quest_id: int):
    if not is_dm_or_creator(interaction):
        await interaction.response.send_message("DM or campaign owner only.", ephemeral=True)
        return
    campaign = get_active_campaign(str(interaction.guild_id))
    if not campaign:
        await interaction.response.send_message("No active campaign.", ephemeral=True)
        return
    current_turn = get_turn_counter(campaign['id'])
    if quest_abandon(campaign['id'], quest_id, turn_counter=current_turn,
                     source='abandon'):
        await interaction.response.send_message(
            f"{E['ok']} Quest #{quest_id} abandoned.", ephemeral=True
        )
    else:
        await interaction.response.send_message(
            f"{E['facepalm']} Cannot abandon #{quest_id} — quest not found "
            f"or already in a terminal state.", ephemeral=True
        )


@quest_group.command(name='seed',
                     description='[DM] Read skeleton.md and import its quests + acts (idempotent — safe to re-run).')
async def quest_seed_skeleton_cmd(interaction: discord.Interaction):
    """Bridges skeleton.md `## Major hooks` into dnd_quests as
    skeleton_origin=1 rows at status='offered'. Idempotent: re-running with
    no skeleton.md changes is a no-op. Edge case (Finding 3): if operator
    edits an existing hook title mid-campaign, the renamed hook inserts as
    a new row; the original-title row persists as an orphan. Operator
    cleans up via `/quest delete <old_id>`."""
    if not is_dm_or_creator(interaction):
        await interaction.response.send_message("DM or campaign owner only.", ephemeral=True)
        return
    campaign = get_active_campaign(str(interaction.guild_id))
    if not campaign:
        await interaction.response.send_message("No active campaign.", ephemeral=True)
        return
    # Load skeleton.md hooks.
    try:
        from skeleton_loader import parse_skeleton_file
        parsed = parse_skeleton_file(campaign['id'], force_reload=True)
    except Exception as e:
        log(f"quest_seed_skeleton: skeleton parse error={e!r}")
        await interaction.response.send_message(
            f"{E['facepalm']} skeleton.md parse failed: {e}", ephemeral=True
        )
        return
    if parsed is None:
        await interaction.response.send_message(
            f"{E['facepalm']} No skeleton.md found for campaign "
            f"`{campaign['name']}`. Author one at "
            f"`campaigns/{campaign['id']}/skeleton.md` first.",
            ephemeral=True
        )
        return
    hooks_raw = parsed.get('hooks') or []
    if not hooks_raw:
        await interaction.response.send_message(
            f"{E['facepalm']} skeleton.md has no `## Major hooks` section "
            f"(or it's empty). Add at least one hook bullet first.",
            ephemeral=True
        )
        return
    # v0 format: hooks are flat bullet strings. voicer_npc_id stays None
    # (priority-rule fallback in suggester handles voicer selection per §1.D).
    # Structured `## Quest hooks` format (title + voicer + reward) is a
    # v0.1 follow-up filed §12.9.
    hook_dicts = [
        {
            'title': h.strip(),
            'summary': '',
            'reward': '',
            'voicer_npc_id': None,
        }
        for h in hooks_raw if (h or '').strip()
    ]
    # Composition Layer v0 (S60) — also seed quests from quest_decompositions
    # (the new ### Quest title H3 + #### Acts shape). Decomposition titles
    # are deduplicated against flat-bullet hooks (same title = same quest).
    decompositions = parsed.get('quest_decompositions') or []
    decomp_titles = {(d.get('title') or '').strip() for d in decompositions}
    # Add each decomposition title to the hook list if not already present
    # as a flat bullet.
    flat_titles = {hd['title'] for hd in hook_dicts}
    for d in decompositions:
        t = (d.get('title') or '').strip()
        if not t or t in flat_titles:
            continue
        hook_dicts.append({
            'title':   t,
            'summary': (d.get('description') or '').strip()[:500],
            'reward':  '',
            'voicer_npc_id': None,
        })
    result = quest_seed_skeleton(campaign['id'], hook_dicts)

    # Composition Layer v0 — seed acts for each quest decomposition.
    # Match decomposition title back to a dnd_quests row (newly inserted
    # OR existing skeleton_origin=1 with matching title). Idempotency
    # delegated to quest_act_upsert (UNIQUE constraint on quest_id +
    # act_index handles re-seed without duplicates).
    acts_inserted = 0
    acts_updated = 0
    location_unresolved = 0
    if decompositions:
        # Build a title→quest_id lookup from current skeleton-origin quests.
        all_quests = get_all_quests(campaign['id']) or []
        title_to_qid = {
            (q.get('title') or '').strip(): q.get('id')
            for q in all_quests
            if q.get('skeleton_origin') == 1
        }
        # Resolve location names via engine helper. Soft: any unresolved
        # location_name stays as a string in the predicate JSON (suggester
        # treats it as location_id mismatch, falls through to operator-only
        # for that act). Logged at seed time.
        from dnd_engine import location_get_by_name
        for d in decompositions:
            qtitle = (d.get('title') or '').strip()
            qid = title_to_qid.get(qtitle)
            if not qid:
                log(f"quest_seed_skeleton_acts: skipped — quest title "
                    f"{qtitle!r} not in dnd_quests")
                continue
            for act in d.get('acts') or []:
                # Convert the parser's predicate dict to JSON storage shape.
                # location_name → location_id resolution at seed time.
                pred = dict(act.get('predicate') or {})
                loc_name = pred.pop('location_name', None)
                if loc_name:
                    loc_row = location_get_by_name(campaign['id'], loc_name)
                    if loc_row:
                        pred['location_id'] = loc_row['id']
                    else:
                        location_unresolved += 1
                        log(f"quest_seed_skeleton_acts: location_name "
                            f"{loc_name!r} not in dnd_locations "
                            f"campaign={campaign['id']} quest_id={qid} "
                            f"act_index={act.get('act_index')}")
                import json as _json_seed
                predicate_json = _json_seed.dumps(pred)
                act_id, was_new = quest_act_upsert(
                    campaign['id'], qid,
                    act_index=act.get('act_index'),
                    act_title=act.get('act_title') or '',
                    act_description=act.get('act_description') or '',
                    transition_predicate_json=predicate_json,
                    skeleton_origin=1,
                )
                if was_new:
                    acts_inserted += 1
                else:
                    acts_updated += 1

    msg_parts = [
        f"{E['ok']} Skeleton seed complete: "
        f"quests inserted={result['inserted']}, skipped={result['skipped']}",
    ]
    if acts_inserted or acts_updated:
        msg_parts.append(
            f"_Acts: inserted={acts_inserted}, updated={acts_updated}"
            + (f", location_unresolved={location_unresolved}"
               if location_unresolved else "")
            + "._"
        )
    elif decompositions:
        msg_parts.append(
            "_Quest decompositions found but no acts seeded (quests not yet "
            "in dnd_quests — run seed again after the quests land)._"
        )
    if result['inserted'] > 0 and result['voicer_unresolved'] == result['inserted']:
        msg_parts.append(
            "_All voicers unresolved (skeleton.md flat-bullet format). "
            "Suggester will use priority-rule fallback (first "
            "skeleton_origin=1 NPC at current location)._"
        )
    if result['skipped'] > 0:
        msg_parts.append(
            "_Skipped rows are existing skeleton_origin=1 quests with "
            "matching title. Use `/quest list status:offered` to inspect; "
            "`/quest delete <id>` for orphans from prior hook renames._"
        )
    await interaction.response.send_message(
        "\n".join(msg_parts), ephemeral=True
    )


# ─────────────────────────────────────────────────────────
# Composition Layer v0 (S60) — quest-act slash commands per §11.7 + §11.13
# All under the existing /quest group (extends the surface; no new top-level
# slash command). Canonical §1b gate: /quest act advance + /quest act set.
# Operator orphan-cleanup via /quest act delete (Quest Layer v0 precedent).
# ─────────────────────────────────────────────────────────

quest_act_group = app_commands.Group(
    name='act',
    description='[DM] Quest act anchor — advance / set / list / delete.',
    parent=quest_group,
)


async def quest_act_id_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[int]]:
    """Autocomplete for /quest act delete — lists acts across the campaign."""
    campaign = get_active_campaign(str(interaction.guild_id))
    if not campaign:
        return []
    # All-acts query: iterate every quest's acts.
    import sqlite3 as _sq
    from dnd_engine import DB_PATH as _DBP
    conn = _sq.connect(_DBP)
    try:
        rows = conn.execute(
            "SELECT a.id, a.act_index, a.act_title, q.title "
            "FROM dnd_quest_acts a "
            "JOIN dnd_quests q ON q.id = a.quest_id "
            "WHERE q.campaign_id=? "
            "ORDER BY q.id ASC, a.act_index ASC LIMIT 25",
            (campaign['id'],)
        ).fetchall()
    finally:
        conn.close()
    needle = current.lower()
    return [
        app_commands.Choice(
            name=f"#{r[0]} [{r[3]} → Act {r[1]}] {r[2]}"[:100],
            value=r[0],
        )
        for r in rows
        if needle in (r[2] or '').lower() or needle in (r[3] or '').lower()
        or needle in str(r[0])
    ][:25]


@quest_act_group.command(
    name='advance',
    description='[DM] Advance the quest to its next act (canonical §1b gate).',
)
@app_commands.describe(quest_id='Quest whose act to advance (must have current_act_id set)')
@app_commands.autocomplete(quest_id=quest_id_autocomplete)
async def quest_act_advance_cmd(interaction: discord.Interaction, quest_id: int):
    if not is_dm_or_creator(interaction):
        await interaction.response.send_message("DM or campaign owner only.", ephemeral=True)
        return
    campaign = get_active_campaign(str(interaction.guild_id))
    if not campaign:
        await interaction.response.send_message("No active campaign.", ephemeral=True)
        return
    cur = get_current_act(campaign['id'])
    if cur is None or cur.get('quest_id') != quest_id:
        await interaction.response.send_message(
            f"{E['facepalm']} Quest #{quest_id} is not the currently anchored "
            f"quest, or that quest has no acts authored. Accept the quest "
            f"first (and ensure its acts are seeded via `/quest seed` from "
            f"skeleton.md `#### Acts` subsection).",
            ephemeral=True
        )
        return
    next_index = cur['act_index'] + 1
    current_turn = get_turn_counter(campaign['id'])
    result = quest_act_transition(
        campaign['id'], quest_id, next_index,
        source='act_advance', turn_counter=current_turn,
    )
    if result is None:
        await interaction.response.send_message(
            f"{E['facepalm']} Cannot advance — quest #{quest_id} has no "
            f"act {next_index} (current is final act, or quest has no acts).",
            ephemeral=True
        )
        return
    await interaction.response.send_message(
        f"{E.get('ok', '✅')} Advanced to **Act {next_index} — "
        f"{result['act_title']}**. Composition directive will surface on the "
        f"next turn.",
        ephemeral=True
    )


# S61 v0.x patch — /quest act set, /quest act list, /quest act delete all
# DROPPED. Operator surface trimmed to just /quest act advance + /quest act
# add (the latter added in S62 patch). Non-sequential jumps + per-act
# inspection + orphan cleanup were unused in live verify; sqlite-direct
# manipulation remains available for the rare edge case.


@quest_act_group.command(
    name='add',
    description='[DM] Author an act on an existing quest (Discord-side; no skeleton.md edit needed).',
)
@app_commands.describe(
    quest_id='Quest to attach the act to',
    act_index='Sequential ordinal (1, 2, 3...). Re-using an index updates that act in place.',
    title='Short act title (e.g. "Approach the farmstead")',
    description='Optional longer description for prompt-side context',
)
@app_commands.autocomplete(quest_id=quest_id_autocomplete)
async def quest_act_add_cmd(interaction: discord.Interaction,
                             quest_id: int, act_index: int,
                             title: str, description: str = ''):
    """S62 v0.x patch — Discord-side act authoring per operator feedback
    ("I am never going to open an md file"). Skeleton.md authoring remains
    available via `/quest seed` but is no longer the only path.

    Idempotent on (quest_id, act_index) — re-using an index updates the
    existing act in place rather than duplicating. Predicate JSON defaults
    to empty (operator-only auto-suggester); v0.x doesn't expose predicate
    authoring via slash (rare, narrow surface). If you want predicate
    auto-fire, author via skeleton.md `#### Acts` subsection with
    `Scene count threshold: N` / `Location: <name>` hints, then /quest seed."""
    if not is_dm_or_creator(interaction):
        await interaction.response.send_message("DM or campaign owner only.", ephemeral=True)
        return
    campaign = get_active_campaign(str(interaction.guild_id))
    if not campaign:
        await interaction.response.send_message("No active campaign.", ephemeral=True)
        return
    quest = get_quest_by_id(campaign['id'], quest_id)
    if quest is None:
        await interaction.response.send_message(
            f"{E['facepalm']} Quest #{quest_id} not found.", ephemeral=True
        )
        return
    if act_index < 1:
        await interaction.response.send_message(
            f"{E['facepalm']} act_index must be >= 1.", ephemeral=True
        )
        return
    act_id, was_new = quest_act_upsert(
        campaign['id'], quest_id, act_index, title,
        act_description=description,
        transition_predicate_json='{}',
        skeleton_origin=0,
    )
    if not act_id:
        await interaction.response.send_message(
            f"{E['facepalm']} Could not author act — engine refused. Check "
            f"quest is in this campaign.", ephemeral=True
        )
        return
    verb = "Added" if was_new else "Updated"
    await interaction.response.send_message(
        f"{E.get('ok', '✅')} {verb} Quest #{quest_id} **Act {act_index}: "
        f"{title}**. Re-run `/quest act add` with the same act_index to "
        f"edit; sequential ordinals (1, 2, 3...) drive `/quest act advance`.",
        ephemeral=True
    )


bot.tree.add_command(quest_group)


# ═════════════════════════════════════════════════════════
# N-10 Canon Bootstrap Bot v0 — slash surface + session state + dispatch.
# §1b sixth project instance. Bot proposes via #dm-aside cards; operator
# approves via `/bootstrap accept` slash; engine writes via existing §17
# single-writers (npc_upsert / quest_add / quest_act_upsert / location_upsert)
# + skeleton_md_append_element (new single-writer for skeleton.md file).
# Per CANON_BOOTSTRAP_BOT_V0_SPEC.md LOCKED + REVIEW.md §11.1–§11.12.
# ═════════════════════════════════════════════════════════


@dataclass
class BootstrapState:
    """Process-local in-memory session per spec §3.2.

    NOT persisted. Cleared on `/bootstrap end`, `/bootstrap accept` of the
    final card, or process restart. State is per-campaign; one active
    session at a time.
    """
    campaign_id: int
    premise: str
    sequence_pointer: int = 0
    sequence_plan: list = field(default_factory=lambda: list(
        orch.BOOTSTRAP_CARD_SEQUENCE_V0
    ))
    approved_elements: list = field(default_factory=list)
    skipped_elements: list = field(default_factory=list)
    current_proposal: dict | None = None
    current_card_type: str | None = None
    rerolls_for_current: int = 0
    started_at: str = ''


_bootstrap_session: dict[int, BootstrapState] = {}


# N-10 v0.1 — operator-friendly field aliases per card type. Operator types
# `name:"X"` expecting "the displayed name" but the actual canonical key
# differs per card type. Without normalization, the override stores
# `fields['name']='X'` and `_commit_proposal` reads `fields.get('canonical_name')`
# — the override is silently ignored. Per playtest evidence (post-N-10 ship,
# 2026-05-14T15:51 Grahn scenario): `/bootstrap manual name:"Grahn"` on an
# NPC card produced `dnd_npcs.canonical_name='Gundrik Ironfist'` (the LLM's
# untouched draft). This map fixes the cascade.

_BOOTSTRAP_FIELD_ALIASES = {
    'faction': {
        # faction card uses 'name' canonically; alias is identity.
        'name': 'name',
    },
    'npc_dispatcher': {
        'name':           'canonical_name',
        'canonical_name': 'canonical_name',
    },
    'location': {
        'name':           'canonical_name',
        'canonical_name': 'canonical_name',
    },
    'quest': {
        'name':  'title',
        'title': 'title',
    },
    'quest_act': {
        'name':      'act_title',
        'title':     'act_title',
        'act_title': 'act_title',
    },
}

# Name-class canonical keys per card type — used to detect when the operator
# overrode a name and trigger the prose-residual warning.
_BOOTSTRAP_NAME_CLASS_CANONICAL = {
    'faction':         {'name'},
    'npc_dispatcher':  {'canonical_name'},
    'location':        {'canonical_name'},
    'quest':           {'title'},
    'quest_act':       {'act_title'},
}


def _normalize_bootstrap_field_key(card_type: str, key: str) -> str:
    """Map an operator-supplied field name to the canonical field key for
    the current card type. Unknown keys pass through unchanged so operator
    can still override less-common fields directly.

    Per N-10 v0.1 patch.
    """
    aliases = _BOOTSTRAP_FIELD_ALIASES.get(card_type) or {}
    return aliases.get(key, key)


def _bootstrap_state_to_dict(state: BootstrapState) -> dict:
    """Serialize to the dict shape orch.compute_bootstrap_card_directive
    expects. Pure read of process-local state."""
    return {
        'premise': state.premise,
        'sequence_pointer': state.sequence_pointer,
        'sequence_plan': state.sequence_plan,
        'approved_elements': state.approved_elements,
        'rerolls_for_current': state.rerolls_for_current,
    }


def _format_bootstrap_card(state: BootstrapState, proposal: dict) -> str:
    """Render a #dm-aside card per spec §4.2. Plain Discord message; ≤2000 chars."""
    fields = proposal.get('fields') or {}
    card_type = proposal.get('card_type', '?')
    seq_index = state.sequence_pointer + 1
    seq_total = len(state.sequence_plan)
    justification = (proposal.get('justification') or '').strip()

    type_label_by = {
        'faction': 'FACTION',
        'npc_dispatcher': 'DISPATCHER NPC',
        'quest': 'QUEST',
        'quest_act': 'QUEST ACT',
        'location': 'LOCATION',
    }
    label = type_label_by.get(card_type, card_type.upper())

    name = (fields.get('name') or fields.get('canonical_name')
            or fields.get('title') or '?').strip()

    body_lines = [
        f"**[BOOTSTRAP — {label} CARD {seq_index}/{seq_total}]**",
        f"Proposed: **{name}**",
        "",
    ]

    if card_type == 'faction':
        body_lines.append(f"Goal: {fields.get('goal', '?')}")
        body_lines.append(f"Pressure: {fields.get('pressure_shape', '?')}")
        body_lines.append(f"Engagement signals: {fields.get('engagement_signals', '?')}")
    elif card_type == 'npc_dispatcher':
        body_lines.append(f"Role: {fields.get('role', '?')} ({fields.get('pronouns', '?')})")
        body_lines.append(f"{fields.get('description', '?')}")
        if fields.get('location_name'):
            body_lines.append(f"Location: {fields['location_name']}")
        if fields.get('associated_faction_name'):
            body_lines.append(f"Faction: {fields['associated_faction_name']}")
    elif card_type == 'quest':
        body_lines.append(f"Offered by: **{fields.get('offer_npc_name', '?')}**")
        body_lines.append(f"_Summary:_ {fields.get('summary', '?')}")
        body_lines.append(f"Reward: {fields.get('reward_summary', '?')}")
        if fields.get('associated_faction_name'):
            body_lines.append(f"Faction: {fields['associated_faction_name']}")
    elif card_type == 'quest_act':
        body_lines.append(f"For quest: **{fields.get('quest_title', '?')}**")
        body_lines.append(f"Act {fields.get('act_index', '?')}: {fields.get('act_title', '?')}")
        body_lines.append(f"{fields.get('act_description', '?')}")
        pred = fields.get('transition_predicate') or {}
        pred_parts = []
        if pred.get('scene_count_threshold'):
            pred_parts.append(f"scenes ≥ {pred['scene_count_threshold']}")
        if pred.get('location_name'):
            pred_parts.append(f"at location \"{pred['location_name']}\"")
        if pred_parts:
            body_lines.append(f"Transition: {', '.join(pred_parts)}")
    elif card_type == 'location':
        loc_type = fields.get('type', '?')
        body_lines.append(f"Type: {loc_type}")
        body_lines.append(f"{fields.get('description', '?')}")
        if fields.get('parent_location_name'):
            body_lines.append(f"Inside: {fields['parent_location_name']}")
        if fields.get('starting_location'):
            body_lines.append("**Starting location for the party.**")

    if justification:
        body_lines.append("")
        body_lines.append(f"_Justification:_ {justification}")

    body_lines.append("")
    body_lines.append("— `/bootstrap accept` to write + advance")
    body_lines.append("— `/bootstrap skip` to drop + advance")
    body_lines.append("— `/bootstrap reroll` to regenerate")
    body_lines.append("— `/bootstrap manual <field>:\"<value>\"` to override")

    body = "\n".join(body_lines)
    # 2000-char hard cap per R3
    if len(body) > 1950:
        body = body[:1950] + "\n…[truncated]"
    return body


async def _dispatch_bootstrap_card(guild, state: BootstrapState,
                                     reroll_hint: str = '') -> bool:
    """Generate next card proposal + post to #dm-aside. Returns True if a
    card was successfully dispatched, False on error / sequence end."""
    next_type, seq_signals = orch.compute_bootstrap_sequence_directive(
        _bootstrap_state_to_dict(state)
    )
    log(orch.bootstrap_sequence_log_summary(seq_signals))

    if next_type is None:
        await _post_dm_aside(
            guild,
            f"{E.get('ok', '✅')} **[BOOTSTRAP COMPLETE]** "
            f"All cards processed. Run `/play` to begin the campaign.\n"
            f"Approved: {len(state.approved_elements)} · "
            f"Skipped: {len(state.skipped_elements)}"
        )
        log(f"bootstrap_session_completed: campaign={state.campaign_id} "
            f"elements_approved={len(state.approved_elements)} "
            f"elements_skipped={len(state.skipped_elements)}")
        _bootstrap_session.pop(state.campaign_id, None)
        return False

    state.current_card_type = next_type
    # N-10 v0.1 — pass prior_proposal so the reroll directive can extract
    # an archetype hint and ask for a meaningfully different shape.
    prior_proposal_for_hint = (
        state.current_proposal if state.rerolls_for_current > 0 else None
    )
    proposal, card_signals = await asyncio.to_thread(
        orch.compute_bootstrap_card_directive,
        _bootstrap_state_to_dict(state), next_type,
        {'id': state.campaign_id}, reroll_hint, prior_proposal_for_hint
    )
    log(orch.bootstrap_card_log_summary(card_signals))

    if proposal is None:
        await _post_dm_aside(
            guild,
            f"{E.get('facepalm', '🤦')} **[BOOTSTRAP CARD ERROR]** "
            f"Couldn't generate a {next_type} proposal "
            f"(reason: {card_signals.get('reason', 'unknown')}). "
            f"Try `/bootstrap reroll` to retry, `/bootstrap skip` to advance "
            f"past this card, or `/bootstrap end` to close the session."
        )
        log(f"bootstrap_card_dispatch_failed: campaign={state.campaign_id} "
            f"card_type={next_type} reason={card_signals.get('reason')}")
        # Hold the failed state so operator can reroll/skip
        state.current_proposal = None
        return False

    state.current_proposal = proposal
    log(f"bootstrap_card_proposed: campaign={state.campaign_id} "
        f"card_type={next_type} "
        f"element_name={(proposal['fields'].get('name') or proposal['fields'].get('canonical_name') or proposal['fields'].get('title') or proposal['fields'].get('act_title') or '?')!r} "
        f"sequence_index={state.sequence_pointer} "
        f"reroll_count={state.rerolls_for_current} "
        f"prior_archetype_hint={1 if card_signals.get('prior_archetype_hint') else 0}")

    await _post_dm_aside(guild, _format_bootstrap_card(state, proposal))
    return True


def _resolve_npc_id_for_quest(campaign_id: int, npc_name: str):
    """Find a previously-bootstrapped NPC's id by canonical name. Returns
    int or None."""
    if not npc_name:
        return None
    try:
        row = npc_get_by_name(campaign_id, npc_name)
        if row:
            return row['id']
    except Exception:
        pass
    return None


def _resolve_location_id(campaign_id: int, location_name: str):
    """Find a previously-bootstrapped location's id by canonical name."""
    if not location_name:
        return None
    try:
        row = location_get_by_name(campaign_id, location_name)
        if row:
            return row['id']
    except Exception:
        pass
    return None


def _resolve_quest_id_by_title(campaign_id: int, quest_title: str):
    """Find a quest id by its title (case-insensitive, whitespace-normalized).
    Returns int or None."""
    if not quest_title:
        return None
    try:
        norm_target = ' '.join(quest_title.split()).lower()
        for q in get_all_quests(campaign_id) or []:
            qt = ' '.join((q.get('title') or '').split()).lower()
            if qt == norm_target:
                return q.get('id')
    except Exception:
        pass
    return None


def _commit_proposal(state: BootstrapState, campaign: dict) -> tuple[bool, str]:
    """Apply current proposal to canonical tables + skeleton.md. Returns
    (success, status_msg) for operator-facing rendering."""
    proposal = state.current_proposal
    if not proposal:
        return False, "no_current_proposal"

    card_type = proposal['card_type']
    fields = proposal['fields']
    campaign_id = state.campaign_id

    try:
        if card_type == 'faction':
            # §11.8 LOCKED — factions live in skeleton.md only at v0. No
            # canonical table write (dnd_factions deferred to S69).
            ok, msg = skeleton_md_append_element(
                campaign_id, 'faction',
                {**fields, 'name': fields.get('name')},
                campaign_name=campaign.get('name', ''),
                premise=state.premise,
            )
            return ok, f"faction:{msg}"

        if card_type == 'npc_dispatcher':
            # Canonical write via npc_upsert
            location_id = _resolve_location_id(campaign_id,
                                                 fields.get('location_name') or '')
            result = npc_upsert(
                campaign_id,
                fields.get('canonical_name', ''),
                role=fields.get('role', ''),
                location_id=location_id,
                description=fields.get('description', ''),
                origin_excerpt='',
                skeleton_origin=True,
            )
            if result is None:
                return False, "npc_upsert_refused"
            npc_id, _was_new = result
            # Skeleton.md append (soft-fail)
            sk_ok, sk_msg = skeleton_md_append_element(
                campaign_id, 'npc',
                {**fields, 'name': fields.get('canonical_name')},
                campaign_name=campaign.get('name', ''),
                premise=state.premise,
            )
            return True, f"npc:inserted id={npc_id} skeleton={sk_msg if sk_ok else 'failed'}"

        if card_type == 'quest':
            npc_id = _resolve_npc_id_for_quest(campaign_id,
                                                 fields.get('offer_npc_name') or '')
            quest_id = quest_add(
                campaign_id,
                fields.get('title', ''),
                summary=fields.get('summary', ''),
                given_by=fields.get('offer_npc_name', ''),
                reward_summary=fields.get('reward_summary', ''),
                skeleton_origin=1,
            )
            # Set offer_npc_id if NPC was resolved
            if npc_id is not None and quest_id is not None:
                try:
                    quest_offer(campaign_id, quest_id,
                                  offer_npc_id=npc_id,
                                  offered_turn=get_turn_counter(campaign_id))
                except Exception as e:
                    log(f"bootstrap: quest_offer side-effect failed: {e!r}")
            sk_ok, sk_msg = skeleton_md_append_element(
                campaign_id, 'quest',
                {**fields, 'name': fields.get('title')},
                campaign_name=campaign.get('name', ''),
                premise=state.premise,
            )
            return True, f"quest:inserted id={quest_id} skeleton={sk_msg if sk_ok else 'failed'}"

        if card_type == 'quest_act':
            quest_id = _resolve_quest_id_by_title(campaign_id,
                                                    fields.get('quest_title') or '')
            if quest_id is None:
                return False, "quest_not_found_for_act"
            pred = fields.get('transition_predicate') or {}
            # Map operator-friendly location_name → location_id JSON if resolvable
            pred_json_obj = {}
            if pred.get('scene_count_threshold'):
                pred_json_obj['scene_count_threshold'] = int(pred['scene_count_threshold'])
            if pred.get('location_name'):
                loc_id = _resolve_location_id(campaign_id, pred['location_name'])
                if loc_id is not None:
                    pred_json_obj['location_id'] = loc_id
                else:
                    pred_json_obj['location_name'] = pred['location_name']
            import json as _json
            act_id, _was_new = quest_act_upsert(
                campaign_id, quest_id,
                act_index=int(fields.get('act_index') or 1),
                act_title=fields.get('act_title', ''),
                act_description=fields.get('act_description', ''),
                transition_predicate_json=_json.dumps(pred_json_obj),
                skeleton_origin=1,
            )
            sk_ok, sk_msg = skeleton_md_append_element(
                campaign_id, 'quest_act',
                {
                    'quest_title': fields.get('quest_title'),
                    'name': fields.get('act_title'),  # for parser
                    'act_index': int(fields.get('act_index') or 1),
                    'act_title': fields.get('act_title'),
                    'act_description': fields.get('act_description'),
                    'transition_predicate': pred,
                },
                campaign_name=campaign.get('name', ''),
                premise=state.premise,
            )
            return True, f"quest_act:inserted id={act_id} skeleton={sk_msg if sk_ok else 'failed'}"

        if card_type == 'location':
            parent_id = _resolve_location_id(campaign_id,
                                              fields.get('parent_location_name') or '')
            loc_id = location_upsert(
                campaign_id,
                fields.get('canonical_name', ''),
                type=fields.get('type', '') or '',
                parent_location_id=parent_id,
                description=fields.get('description', ''),
                origin_excerpt='',
                skeleton_origin=True,
            )
            if loc_id is None:
                return False, "location_upsert_refused"
            # Set as current_location if starting_location=True
            if fields.get('starting_location'):
                try:
                    set_current_location(campaign_id, loc_id)
                except Exception as e:
                    log(f"bootstrap: set_current_location failed: {e!r}")
            sk_ok, sk_msg = skeleton_md_append_element(
                campaign_id, 'location',
                {**fields, 'name': fields.get('canonical_name')},
                campaign_name=campaign.get('name', ''),
                premise=state.premise,
            )
            return True, f"location:inserted id={loc_id} skeleton={sk_msg if sk_ok else 'failed'}"

        return False, f"unknown_card_type:{card_type}"
    except Exception as e:
        log(f"bootstrap commit_proposal error: card_type={card_type} err={e!r}")
        return False, f"exception:{e!r}"


# ─── /bootstrap slash group ───────────────────────────────

bootstrap_group = app_commands.Group(
    name='bootstrap',
    description='[DM] Canon Bootstrap Bot v0 — propose campaign canon from a premise.'
)


@bootstrap_group.command(
    name='begin',
    description='[DM] Open a bootstrap session from a 2-3 sentence premise.'
)
@app_commands.describe(
    premise='2-3 sentences: genre, setting, character role, what\'s pressuring the world.'
)
async def bootstrap_begin_cmd(interaction: discord.Interaction, premise: str):
    if not is_dm_or_creator(interaction):
        await interaction.response.send_message(
            "DM or campaign owner only.", ephemeral=True)
        return
    campaign = get_active_campaign(str(interaction.guild_id))
    if not campaign:
        await interaction.response.send_message(
            "No active campaign. Run `/newcampaign` first.", ephemeral=True)
        return
    cid = campaign['id']
    premise_clean = (premise or '').strip()
    if not premise_clean:
        await interaction.response.send_message(
            "Premise is required. Example: "
            "`/bootstrap begin premise:\"Grimdark frontier mining town, "
            "hexcrawl, the mine collapsed and something climbed out.\"`",
            ephemeral=True)
        return
    if is_bootstrap_complete(cid):
        await interaction.response.send_message(
            f"{E.get('facepalm', '🤦')} Campaign **{campaign['name']}** is "
            f"already bootstrap-complete (premise set + skeleton_origin "
            f"elements exist). Re-bootstrap not supported at v0 — file v1.x "
            f"expansion-mode candidate after live signal.",
            ephemeral=True)
        return
    # Persist premise
    update_campaign_premise(cid, premise_clean)
    # Open in-memory session
    import datetime as _dt
    state = BootstrapState(
        campaign_id=cid,
        premise=premise_clean,
        started_at=_dt.datetime.now().isoformat(timespec='seconds'),
    )
    _bootstrap_session[cid] = state
    log(f"bootstrap_session_opened: campaign={cid} "
        f"premise_chars={len(premise_clean)} sequence_total={len(state.sequence_plan)}")
    await interaction.response.send_message(
        f"{E.get('ok', '✅')} Bootstrap session opened for **{campaign['name']}**. "
        f"Watch #dm-aside for the first card. Premise stored "
        f"({len(premise_clean)} chars). Sequence: "
        f"{len(state.sequence_plan)} cards — `/bootstrap status` for "
        f"progress, `/bootstrap end` to close.",
        ephemeral=True)
    # Fire first card
    await _dispatch_bootstrap_card(interaction.guild, state)


@bootstrap_group.command(
    name='accept',
    description='[DM] Approve the current bootstrap card; write canon + advance.'
)
async def bootstrap_accept_cmd(interaction: discord.Interaction):
    if not is_dm_or_creator(interaction):
        await interaction.response.send_message(
            "DM or campaign owner only.", ephemeral=True)
        return
    campaign = get_active_campaign(str(interaction.guild_id))
    if not campaign:
        await interaction.response.send_message(
            "No active campaign.", ephemeral=True)
        return
    state = _bootstrap_session.get(campaign['id'])
    if not state:
        await interaction.response.send_message(
            "No active bootstrap session. Run `/bootstrap begin premise:\"...\"`.",
            ephemeral=True)
        return
    if not state.current_proposal:
        await interaction.response.send_message(
            "No card to accept. Try `/bootstrap reroll` or `/bootstrap skip`.",
            ephemeral=True)
        return

    ok, msg = _commit_proposal(state, campaign)
    if ok:
        # Snapshot the approved element for downstream context
        state.approved_elements.append({
            'card_type': state.current_proposal['card_type'],
            'fields': state.current_proposal['fields'],
            'justification': state.current_proposal.get('justification', ''),
        })
        log(f"bootstrap_card_approved: campaign={state.campaign_id} "
            f"card_type={state.current_proposal['card_type']} "
            f"sequence_index={state.sequence_pointer} write_status={msg}")
        state.current_proposal = None
        state.rerolls_for_current = 0
        state.sequence_pointer += 1
        await interaction.response.send_message(
            f"{E.get('ok', '✅')} Accepted ({msg}). Advancing…",
            ephemeral=True)
        await _dispatch_bootstrap_card(interaction.guild, state)
    else:
        log(f"bootstrap_card_approve_failed: campaign={state.campaign_id} "
            f"reason={msg}")
        await interaction.response.send_message(
            f"{E.get('facepalm', '🤦')} Couldn't commit proposal: {msg}. "
            f"Try `/bootstrap reroll` for a different draft, "
            f"`/bootstrap skip` to advance past this card, or "
            f"`/bootstrap manual <field>:\"<value>\"` to override.",
            ephemeral=True)


@bootstrap_group.command(
    name='skip',
    description='[DM] Skip the current bootstrap card without writing canon; advance.'
)
async def bootstrap_skip_cmd(interaction: discord.Interaction):
    if not is_dm_or_creator(interaction):
        await interaction.response.send_message(
            "DM or campaign owner only.", ephemeral=True)
        return
    campaign = get_active_campaign(str(interaction.guild_id))
    if not campaign:
        await interaction.response.send_message(
            "No active campaign.", ephemeral=True)
        return
    state = _bootstrap_session.get(campaign['id'])
    if not state:
        await interaction.response.send_message(
            "No active bootstrap session.", ephemeral=True)
        return
    skipped_type = state.current_card_type or '?'
    state.skipped_elements.append({
        'card_type': skipped_type,
        'fields': (state.current_proposal or {}).get('fields'),
    })
    log(f"bootstrap_card_skipped: campaign={state.campaign_id} "
        f"card_type={skipped_type} sequence_index={state.sequence_pointer}")
    state.current_proposal = None
    state.rerolls_for_current = 0
    state.sequence_pointer += 1
    await interaction.response.send_message(
        f"{E.get('ok', '✅')} Skipped {skipped_type}. Advancing…",
        ephemeral=True)
    await _dispatch_bootstrap_card(interaction.guild, state)


@bootstrap_group.command(
    name='reroll',
    description='[DM] Regenerate the current card with a different shape (soft reroll, unlimited).'
)
async def bootstrap_reroll_cmd(interaction: discord.Interaction):
    if not is_dm_or_creator(interaction):
        await interaction.response.send_message(
            "DM or campaign owner only.", ephemeral=True)
        return
    campaign = get_active_campaign(str(interaction.guild_id))
    if not campaign:
        await interaction.response.send_message(
            "No active campaign.", ephemeral=True)
        return
    state = _bootstrap_session.get(campaign['id'])
    if not state:
        await interaction.response.send_message(
            "No active bootstrap session.", ephemeral=True)
        return
    state.rerolls_for_current += 1
    log(f"bootstrap_card_reroll: campaign={state.campaign_id} "
        f"card_type={state.current_card_type} "
        f"reroll_count={state.rerolls_for_current}")
    await interaction.response.send_message(
        f"{E.get('ok', '✅')} Rerolling (#{state.rerolls_for_current})…",
        ephemeral=True)
    await _dispatch_bootstrap_card(interaction.guild, state,
                                     reroll_hint='Reroll number {}'.format(
                                         state.rerolls_for_current))


@bootstrap_group.command(
    name='manual',
    description='[DM] Override one or more fields on the current card before accepting.'
)
@app_commands.describe(
    overrides='Space-separated overrides like name:"Eldrin Stormbow" role:"village herald"'
)
async def bootstrap_manual_cmd(interaction: discord.Interaction, overrides: str):
    if not is_dm_or_creator(interaction):
        await interaction.response.send_message(
            "DM or campaign owner only.", ephemeral=True)
        return
    campaign = get_active_campaign(str(interaction.guild_id))
    if not campaign:
        await interaction.response.send_message(
            "No active campaign.", ephemeral=True)
        return
    state = _bootstrap_session.get(campaign['id'])
    if not state or not state.current_proposal:
        await interaction.response.send_message(
            "No active card to override. Run `/bootstrap begin` first.",
            ephemeral=True)
        return
    # Parse overrides shape: `field:"value" field2:"value2"` — quoted values
    # tolerated; unquoted single-word values also OK.
    import re as _re
    parsed_pairs = _re.findall(
        r'(\w+)\s*:\s*(?:"([^"]*)"|(\S+))', overrides or ''
    )
    if not parsed_pairs:
        await interaction.response.send_message(
            "Couldn't parse overrides. Format: "
            "`/bootstrap manual overrides:'name:\"Eldrin\" role:\"herald\"'`",
            ephemeral=True)
        return
    # N-10 v0.1 — normalize operator-friendly field aliases to canonical keys
    # per card type before storing into fields. Without this, `name:"X"` on
    # an NPC card silently doesn't propagate to canonical_name and the
    # commit-time write uses the LLM's untouched draft.
    card_type = state.current_card_type or ''
    name_class_canonical = _BOOTSTRAP_NAME_CLASS_CANONICAL.get(card_type, set())
    applied = []
    touched_name_class = False
    for key, quoted, unquoted in parsed_pairs:
        val = quoted if quoted else unquoted
        normalized_key = _normalize_bootstrap_field_key(card_type, key)
        state.current_proposal['fields'][normalized_key] = val
        if normalized_key in name_class_canonical:
            touched_name_class = True
        # Always log normalized vs original so the alias mapping is observable
        log(f"bootstrap_manual_override: campaign={state.campaign_id} "
            f"card_type={card_type} original_key={key!r} "
            f"normalized_key={normalized_key!r} value={val!r}")
        if normalized_key != key:
            applied.append(f"{key}→{normalized_key}={val!r}")
        else:
            applied.append(f"{key}={val!r}")
    # Re-post the card with overrides applied
    await _post_dm_aside(interaction.guild,
                          _format_bootstrap_card(state, state.current_proposal))
    residual_warning = ""
    if touched_name_class:
        residual_warning = (
            "\n⚠ Description and justification may still reference the prior "
            "name. Run `/bootstrap reroll` if you want the prose regenerated "
            "with the new name."
        )
    await interaction.response.send_message(
        f"{E.get('ok', '✅')} Override applied ({', '.join(applied)}). "
        f"Card re-posted; `/bootstrap accept` to commit or `/bootstrap reroll` "
        f"to regenerate.{residual_warning}",
        ephemeral=True)


@bootstrap_group.command(
    name='status',
    description='[DM] Show current bootstrap session progress.'
)
async def bootstrap_status_cmd(interaction: discord.Interaction):
    campaign = get_active_campaign(str(interaction.guild_id))
    if not campaign:
        await interaction.response.send_message(
            "No active campaign.", ephemeral=True)
        return
    state = _bootstrap_session.get(campaign['id'])
    if not state:
        # Check if already bootstrap-complete
        if is_bootstrap_complete(campaign['id']):
            await interaction.response.send_message(
                f"Campaign **{campaign['name']}** is bootstrap-complete. "
                f"No active session.",
                ephemeral=True)
        else:
            await interaction.response.send_message(
                "No active bootstrap session. Run "
                "`/bootstrap begin premise:\"...\"`.",
                ephemeral=True)
        return
    lines = [
        f"**Bootstrap session** for **{campaign['name']}** "
        f"(started {state.started_at})",
        f"Premise: {state.premise[:200]}"
        + ("…" if len(state.premise) > 200 else ""),
        f"Sequence: {state.sequence_pointer + 1}/{len(state.sequence_plan)} "
        f"(current: {state.current_card_type or 'awaiting next'})",
        f"Approved: {len(state.approved_elements)} · "
        f"Skipped: {len(state.skipped_elements)} · "
        f"Rerolls on current: {state.rerolls_for_current}",
    ]
    await interaction.response.send_message("\n".join(lines), ephemeral=True)


@bootstrap_group.command(
    name='end',
    description='[DM] Close the bootstrap session early; keep whatever\'s been approved.'
)
async def bootstrap_end_cmd(interaction: discord.Interaction):
    if not is_dm_or_creator(interaction):
        await interaction.response.send_message(
            "DM or campaign owner only.", ephemeral=True)
        return
    campaign = get_active_campaign(str(interaction.guild_id))
    if not campaign:
        await interaction.response.send_message(
            "No active campaign.", ephemeral=True)
        return
    state = _bootstrap_session.pop(campaign['id'], None)
    if not state:
        await interaction.response.send_message(
            "No active bootstrap session.", ephemeral=True)
        return
    log(f"bootstrap_session_completed: campaign={state.campaign_id} "
        f"elements_approved={len(state.approved_elements)} "
        f"elements_skipped={len(state.skipped_elements)} reason=operator_end")
    await interaction.response.send_message(
        f"{E.get('ok', '✅')} Bootstrap session closed. "
        f"Approved: {len(state.approved_elements)} · "
        f"Skipped: {len(state.skipped_elements)}. "
        f"Canonical state preserves whatever was approved.",
        ephemeral=True)


bot.tree.add_command(bootstrap_group)


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
    # S66 Fix 2C — surface party stash alongside the character's inventory
    # so quest-delivery and loot auto-claim rewards are visible. The
    # bucket is __party__ (PARTY_STASH_BUCKET), not a bound character.
    party_rows = get_inventory(campaign['id'], PARTY_STASH_BUCKET)

    if not rows and not party_rows:
        await interaction.response.send_message(
            f"**{target_name}**'s inventory: _Empty._ (Party stash also empty.)",
            ephemeral=True
        )
        return

    lines = [f"**{target_name}**'s inventory:"]
    if rows:
        for r in rows:
            item = r['item_name']
            qty = r['quantity']
            if qty and qty > 1:
                lines.append(f"- {item} (×{qty})")
            else:
                lines.append(f"- {item}")
    else:
        lines.append("_(empty)_")

    if party_rows:
        lines.append("")
        lines.append("**Party stash** (quest rewards + loot):")
        for r in party_rows:
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


# S66 Fix 3C — refusal surface for auto-claimed loot. Default is YOU GET
# THE LOOT (Fix 3B auto-claims at mark_loot_surfaced); operator uses
# /loot drop <item> to remove items the party doesn't want. Aligns with
# how tabletop play works: loot from combat is presumed-taken unless
# someone says otherwise.
async def _party_stash_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    campaign = get_active_campaign(str(interaction.guild_id))
    if not campaign:
        return []
    try:
        rows = get_inventory(campaign['id'], PARTY_STASH_BUCKET)
    except Exception:
        return []
    needle = (current or '').lower()
    return [
        app_commands.Choice(name=r['item_name'][:100], value=r['item_name'])
        for r in rows
        if needle in r['item_name'].lower()
    ][:25]


@bot.tree.command(
    name='loot',
    description='[DM] Drop an item from the party stash (refuse auto-claimed loot).',
)
@app_commands.describe(
    item='Item name to drop from the party stash (autocompletes from current stash).',
    quantity='How many to drop. Default 1.',
)
@app_commands.autocomplete(item=_party_stash_autocomplete)
async def loot_drop_cmd(interaction: discord.Interaction,
                        item: str, quantity: int = 1):
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
    item_clean = (item or '').strip()
    if not item_clean:
        await interaction.response.send_message(
            "Item name must be non-empty.", ephemeral=True
        )
        return
    if quantity is None or quantity <= 0:
        await interaction.response.send_message(
            "Quantity must be a positive integer.", ephemeral=True
        )
        return

    result = remove_item(campaign['id'], PARTY_STASH_BUCKET,
                         item_clean, quantity=quantity)
    action = result.get('action')
    log(f"loot_dropped: campaign={campaign['id']} "
        f"item={result.get('item_name')!r} qty={quantity} "
        f"action={action}")

    if action == 'removed':
        await interaction.response.send_message(
            f"{E['ok']} Dropped from party stash: **{result['item_name']}** "
            f"(all of them). Narrate leaving it behind in the next turn.",
            ephemeral=True
        )
    elif action == 'decremented':
        await interaction.response.send_message(
            f"{E['ok']} Dropped from party stash: **{result['item_name']}** "
            f"×{quantity} (now ×{result['quantity_now']}).",
            ephemeral=True
        )
    elif action == 'not_found':
        await interaction.response.send_message(
            f"{E['facepalm']} No `{item_clean}` in party stash. "
            f"Check `/inventory` for what's actually there.",
            ephemeral=True
        )
    elif action == 'insufficient':
        await interaction.response.send_message(
            f"{E['facepalm']} Party stash only has ×{result['quantity_now']} "
            f"of **{result['item_name']}** — can't drop {quantity}.",
            ephemeral=True
        )
    else:
        await interaction.response.send_message(
            f"{E['facepalm']} Invalid item or quantity. (action={action})",
            ephemeral=True
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
