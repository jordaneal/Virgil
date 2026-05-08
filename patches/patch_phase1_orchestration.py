#!/usr/bin/env python3
"""
patch_phase1_orchestration.py
─────────────────────────────────────────────────────────
Phase 1.1 wiring patch. Assumes /home/jordaneal/scripts/dnd_orchestration.py
already exists (scp it first).

Changes:

  dnd_engine.py
    - import dnd_orchestration as orch
    - dm_respond() classifies intent + calls should_call_roll() and
      passes both into build_dm_context.
    - build_dm_context() accepts character_context (CharacterContext or None)
      + roll_decision (RollDecision) and renders them into the prompt.
    - The "WHEN TO CALL FOR ROLLS" block becomes deterministic — the prompt
      only restates the engine's decision, never invents one.

  discord_dnd_bot.py
    - On /bindchar, after fetching the Avrae sheet, build a CharacterContext
      and stash it in the cache.
    - /refresh command: re-scans #bot-commands and other channels for the
      most recent sheet embed and rebuilds the cache.
    - _dm_respond_and_post() loads the cached context for the most recent
      actor and threads it through dm_respond.

Idempotent. Backs up + syntax checks.
"""

import re
import ast
import datetime
from pathlib import Path

ENGINE = Path('/home/jordaneal/scripts/dnd_engine.py')
BOT = Path('/home/jordaneal/scripts/discord_dnd_bot.py')

engine_orig = ENGINE.read_text()
bot_orig = BOT.read_text()
engine_src = engine_orig
bot_src = bot_orig


# ─────────────────────────────────────────────────────────
# 1. dnd_engine.py — add `import dnd_orchestration as orch` near other imports
# ─────────────────────────────────────────────────────────

if 'import dnd_orchestration' not in engine_src:
    # Insert after the first cluster of imports
    anchor = "from cloud_router import route\n"
    if anchor not in engine_src:
        raise SystemExit("[FAIL] cloud_router import anchor missing in dnd_engine.py")
    engine_src = engine_src.replace(
        anchor,
        anchor + "import dnd_orchestration as orch\n",
        1,
    )
    print("[ok] dnd_engine.py: imported dnd_orchestration")
else:
    print("[skip] dnd_engine.py already imports dnd_orchestration")


# ─────────────────────────────────────────────────────────
# 2. dnd_engine.py — replace dm_respond() to use orchestration
# ─────────────────────────────────────────────────────────

DM_RESPOND_RE = re.compile(
    r"def dm_respond\(campaign, characters, player_action, avrae_events=None\):.*?"
    r"return f\"DM error: \{e\}\"",
    re.DOTALL
)

NEW_DM_RESPOND = '''def dm_respond(campaign, characters, player_action, avrae_events=None,
                acting_character_name: str = ""):
    """Run one DM turn. Returns response string.

    The roll-or-not decision is made HERE by the orchestration engine.
    The DM prompt only RESTATES that decision — it never invents one.
    """
    # 1. Resolve character context (cached) for the actor, if any
    character_ctx = None
    if acting_character_name:
        character_ctx = orch.get_cached_context(acting_character_name)
    elif characters:
        # Fall back to the first character in the campaign
        character_ctx = orch.get_cached_context(characters[0]['name'])

    # 2. Determine current mode (default exploration; combat if avrae events show attacks)
    mode = 'exploration'
    in_combat = False
    if avrae_events:
        for ev in avrae_events:
            if ev.get('kind') in ('attack', 'cast') and ev.get('damage'):
                mode = 'combat'
                in_combat = True
                break

    # 3. Classify intent + decide on roll
    intent = orch.classify_action_intent(player_action, in_combat=in_combat)
    roll_decision = orch.should_call_roll(intent, mode, player_action, character_ctx)

    # 4. Knowledge guidance (if enabled)
    scene_blurb = (campaign.get('current_scene') or '')[:200]
    avrae_summary = ""
    if avrae_events:
        bits = []
        for ev in avrae_events:
            if ev.get('nat') == 20:
                bits.append("critical success")
            elif ev.get('nat') == 1:
                bits.append("catastrophic failure")
            elif ev.get('crit'):
                bits.append("critical hit")
            kind = ev.get('kind')
            if kind:
                bits.append(kind)
        avrae_summary = " ".join(bits)

    relevant = chroma_search(campaign['id'], player_action)

    if USE_KNOWLEDGE_GUIDANCE:
        guidance = multi_query_knowledge_search(
            player_action, intent, scene_blurb, avrae_summary
        )
    else:
        guidance = ""

    # 5. Build prompt with all the structured signals
    system = build_dm_context(
        campaign, characters,
        relevant_history=relevant,
        dm_guidance=guidance,
        action_type=intent,
        avrae_events=avrae_events,
        character_context=character_ctx,
        roll_decision=roll_decision,
        mode=mode,
    )
    try:
        response, _ = route(
            messages=[{"role": "user", "content": player_action}],
            task_type="dnd",
            system_prompt=system,
        )
        return response
    except Exception as e:
        log(f"dm_respond error: {e}")
        return f"DM error: {e}"'''

m = DM_RESPOND_RE.search(engine_src)
if not m:
    if 'roll_decision = orch.should_call_roll' in engine_src:
        print("[skip] dm_respond already uses orchestration")
    else:
        raise SystemExit("[FAIL] dm_respond block not matched")
else:
    engine_src = engine_src[:m.start()] + NEW_DM_RESPOND + engine_src[m.end():]
    print("[ok] dnd_engine.py: dm_respond rewired through orchestration")


# ─────────────────────────────────────────────────────────
# 3. dnd_engine.py — replace build_dm_context to accept new signals
# ─────────────────────────────────────────────────────────

BUILD_DM_RE = re.compile(
    r"def build_dm_context\([^)]*\):.*?(?=\ndef dm_respond\()",
    re.DOTALL
)

NEW_BUILD_DM = '''def build_dm_context(campaign, characters, relevant_history="", dm_guidance="",
                     action_type="", avrae_events=None,
                     character_context=None, roll_decision=None, mode="exploration"):
    """Compose the system prompt that drives the DM LLM call.

    The prompt is now intentionally narrow: tone, pacing, voice. It does NOT
    decide whether to call for a roll — that's the orchestration engine's job.
    """
    if characters:
        char_summaries = "\\n".join(
            f"- {c['name']}: Level {c.get('level', 1)} "
            f"{(c.get('race') or '?').title()} {(c.get('class') or '?').title()}"
            for c in characters
        )
    else:
        char_summaries = "- (no bound characters yet — narrate broadly)"

    DEFAULT_TONE = (
        "Classic high fantasy D&D — medieval, magical, swords and spells. "
        "Taverns, dungeons, ancient ruins, gods, monsters, beasts. "
        "STRICTLY NO firearms, NO modern technology, NO neon, NO grav-cars, "
        "NO LED lights, NO holograms, NO cyberpunk elements, NO science fiction. "
        "STRICTLY NO Elder Scrolls / Tamriel / Cyrodiil / Dwemer references. "
        "STRICTLY NO Marvel, Pokemon, Star Wars, or other fictional-universe content."
    )
    tone = (campaign.get('tone') or '').strip() or DEFAULT_TONE

    history_section = (
        f"\\n\\n=== RELEVANT PAST EVENTS ===\\n{relevant_history}"
        if relevant_history else ""
    )

    guidance_section = (
        f"\\n\\n=== DM PACING EXAMPLES ===\\n"
        f"For ENERGY and PACING only. NEVER copy settings, names, places, or "
        f"specific details — only the shape of how an experienced DM advances a beat.\\n\\n"
        f"{dm_guidance}"
        if dm_guidance else ""
    )

    avrae_block = _format_avrae_events(avrae_events) if avrae_events else ""
    avrae_section = (
        f"\\n\\n=== MECHANICAL EVENTS (from Avrae, just rolled) ===\\n"
        f"{avrae_block}\\n"
        f"These rolls already happened. Narrate the OUTCOME in prose. "
        f"Do NOT re-ask for the roll. Do NOT quote the number."
        if avrae_block else ""
    )

    char_ctx_section = (
        f"\\n\\n=== ACTING CHARACTER ===\\n{character_context.to_prompt_block()}"
        if character_context else ""
    )

    roll_directive = (
        f"\\n\\n=== ROLL DIRECTIVE ===\\n{roll_decision.to_prompt_directive()}"
        if roll_decision else ""
    )

    mode_block = f"\\n\\n=== CURRENT MODE ===\\n{mode}"

    return f"""You are the Dungeon Master for a D&D 5th Edition campaign called "{campaign['name']}".

=== SETTING & TONE (HARD CONSTRAINT — DO NOT VIOLATE) ===
{tone}

=== PARTY ===
{char_summaries}

=== CURRENT SCENE ===
{campaign.get('current_scene') or 'The adventure is just beginning.'}{mode_block}{char_ctx_section}{history_section}{guidance_section}{avrae_section}{roll_directive}

=== HOW THIS GAME WORKS ===

You and Avrae split work cleanly:
- AVRAE handles ALL dice, sheets, HP, attacks, spells, saves, checks.
- YOU handle scene description, NPC dialogue, world reactions, pacing.

You DO NOT decide whether to call for a roll. That decision is made FOR you and given as a ROLL DIRECTIVE above. Follow it exactly:
- If the directive says NO ROLL: narrate the outcome based on character ability + tags. Do not invent a roll. Do not ask the player to roll.
- If the directive says a specific roll is required: end your message asking the player to make that exact roll, then STOP. Do not narrate the outcome until the roll comes back as a MECHANICAL EVENT next turn.

=== READING MECHANICAL EVENTS ===

When MECHANICAL EVENTS are present, those rolls already happened. Narrate the OUTCOME — never re-ask for the roll, never quote the number.
- Total 17+ on a check = solid success. 25+ = exceptional. 5 or below = failure with consequence.
- Nat 20 = spectacular. Nat 1 = catastrophic.

=== CHARACTER AWARENESS ===

If an ACTING CHARACTER block is present, narrate AS IF you can see their sheet:
- Reference their tags naturally ("with darkvision, the cave is dim but legible" / "the rogue's hand is already on the lock").
- Match the difficulty and tone to their level.
- Don't ignore their proficiencies — a stealth_specialist sneaking is competent by default.

=== OUT-OF-CHARACTER REQUESTS ===

If the player asks a meta-question (the ROLL DIRECTIVE will say so), DROP CHARACTER. Answer in *italics* with a short, helpful note. Then return to scene.

=== LENGTH (MANDATORY) ===

Maximum 2 short paragraphs. Maximum 6 sentences total. Brevity is mandatory.

=== STRICT AVOID ===

Forbidden phrases: "the air clings", "silence is oppressive", "shadows seem to writhe", "shadows seem to twist", "the very [X]", "as if [X] itself was [Y]", "darkness seems to swallow", "with calculated silence", "luminescent orbs", "neon-drenched", "grav-cars", "holographic", "kaleidoscope", "swirling vortex".

Do NOT mix genres. Do NOT restate what the player said. Do NOT pad atmosphere when story should advance.

=== OUTPUT FORMAT ===

Plain prose. **bold** for key names. *italics* for thought, whisper, or OOC asides.

=== FINAL TONE REMINDER ===
{tone}"""


'''

m2 = BUILD_DM_RE.search(engine_src)
if not m2:
    raise SystemExit("[FAIL] build_dm_context block not matched")
engine_src = engine_src[:m2.start()] + NEW_BUILD_DM + engine_src[m2.end():]
print("[ok] dnd_engine.py: build_dm_context accepts orchestration signals")


# ─────────────────────────────────────────────────────────
# 4. discord_dnd_bot.py — import orchestration
# ─────────────────────────────────────────────────────────

if 'import dnd_orchestration' not in bot_src:
    # Insert near the dnd_engine import
    anchor = "from dnd_engine import"
    idx = bot_src.find(anchor)
    if idx == -1:
        raise SystemExit("[FAIL] dnd_engine import not found in discord_dnd_bot.py")
    line_end = bot_src.find('\n', idx)
    bot_src = bot_src[:line_end+1] + "import dnd_orchestration as orch\n" + bot_src[line_end+1:]
    print("[ok] discord_dnd_bot.py: imported dnd_orchestration")
else:
    print("[skip] discord_dnd_bot.py already imports dnd_orchestration")


# ─────────────────────────────────────────────────────────
# 5. discord_dnd_bot.py — extend /bindchar to cache CharacterContext
# ─────────────────────────────────────────────────────────

# We don't replace the whole /bindchar — we inject the cache step right
# after fetch_avrae_sheet_data succeeds.

OLD_BIND_FETCH = '''    await interaction.response.defer()
    sheet_data = await fetch_avrae_sheet_data(interaction.channel, name)
    if not sheet_data:'''

NEW_BIND_FETCH = '''    await interaction.response.defer()
    sheet_data = await fetch_avrae_sheet_data(interaction.channel, name)
    # Also build the rich CharacterContext from the embed and cache it
    try:
        async for msg in interaction.channel.history(limit=50):
            if not al.is_avrae(msg):
                continue
            for embed in msg.embeds:
                ctx = orch.parse_avrae_sheet_embed(embed)
                if ctx and ctx.name.lower() == name.lower():
                    ctx.source_message_id = msg.id
                    orch.set_cached_context(ctx)
                    log(f"cached CharacterContext for {ctx.name} ({len(ctx.narrative_tags)} tags)")
                    break
            else:
                continue
            break
    except Exception as e:
        log(f"bindchar: failed to cache CharacterContext: {e}")
    if not sheet_data:'''

if NEW_BIND_FETCH in bot_src:
    print("[skip] /bindchar already caches CharacterContext")
elif OLD_BIND_FETCH in bot_src:
    bot_src = bot_src.replace(OLD_BIND_FETCH, NEW_BIND_FETCH)
    print("[ok] /bindchar: caches CharacterContext on bind")
else:
    raise SystemExit("[FAIL] /bindchar fetch block not matched")


# ─────────────────────────────────────────────────────────
# 6. discord_dnd_bot.py — add /refresh command
# ─────────────────────────────────────────────────────────

REFRESH_MARKER = "name='refresh'"
REFRESH_BLOCK = '''
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
'''

if REFRESH_MARKER in bot_src:
    print("[skip] /refresh already present")
else:
    # Insert before the on_message handler
    anchor = "@bot.event\nasync def on_message"
    if anchor not in bot_src:
        raise SystemExit("[FAIL] on_message anchor missing")
    bot_src = bot_src.replace(anchor, REFRESH_BLOCK + "\n" + anchor, 1)
    print("[ok] /refresh command added")


# ─────────────────────────────────────────────────────────
# 7. discord_dnd_bot.py — pass acting_character_name into dm_respond
# ─────────────────────────────────────────────────────────

OLD_CALL = '''        text = dm_respond(campaign, characters, combined, avrae_events=avrae_events)'''

NEW_CALL = '''        # Pick the most recent unique actor (already deduped above) as the
        # focal character for sheet-aware narration.
        acting = actor_names[0] if actor_names else ''
        text = dm_respond(campaign, characters, combined,
                          avrae_events=avrae_events, acting_character_name=acting)'''

if NEW_CALL in bot_src:
    print("[skip] dm_respond call already passes acting_character_name")
elif OLD_CALL in bot_src:
    bot_src = bot_src.replace(OLD_CALL, NEW_CALL)
    print("[ok] discord_dnd_bot.py: dm_respond receives acting_character_name")
else:
    raise SystemExit("[FAIL] dm_respond call site not matched")


# ─────────────────────────────────────────────────────────
# Syntax check both files
# ─────────────────────────────────────────────────────────

try:
    ast.parse(engine_src)
    print("[ok] dnd_engine.py syntax check passed")
except SyntaxError as e:
    raise SystemExit(f"[FAIL] dnd_engine.py syntax error: {e}")

try:
    ast.parse(bot_src)
    print("[ok] discord_dnd_bot.py syntax check passed")
except SyntaxError as e:
    raise SystemExit(f"[FAIL] discord_dnd_bot.py syntax error: {e}")


# ─────────────────────────────────────────────────────────
# Backup + write
# ─────────────────────────────────────────────────────────

stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')

ENGINE.with_suffix(f'.py.bak.{stamp}').write_text(engine_orig)
ENGINE.write_text(engine_src)
print(f"[ok] wrote {ENGINE}")

BOT.with_suffix(f'.py.bak.{stamp}').write_text(bot_orig)
BOT.write_text(bot_src)
print(f"[ok] wrote {BOT}")

print()
print("Reminder: dnd_orchestration.py must already be in /home/jordaneal/scripts/")
print()
print("Next:")
print("  systemctl --user restart virgil-discord")
print("  journalctl --user -u virgil-discord -n 15 --no-pager")
