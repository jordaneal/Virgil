#!/usr/bin/env python3
"""
patch_dm_prompt_v3.py
─────────────────────────────────────────────────────────
Major DM behavior fixes:

  1. Rewrites build_dm_context() — the DM now CALLS for rolls when player
     intent requires one (and stops, doesn't narrate the result), reads
     MECHANICAL EVENTS to narrate consequences, breaks character for OOC
     questions, and is hard-anchored to the campaign's setting/tone.

  2. Adds a `tone` column to dnd_campaigns. /newcampaign accepts an
     optional `tone` parameter so DMs can pin "grim dark fantasy",
     "comedic high fantasy", "Eberron noir", etc. Default is plain
     high fantasy with explicit anti-genre-bleed guards (no sci-fi,
     no Elder Scrolls lore, no Marvel, etc).

  3. Fixes the "Donovan Ruby, Donovan Ruby" duplicate footer bug —
     dedupes actor_names while preserving order.

  4. Reinforces the knowledge_search section: exemplars are for
     ENERGY only, never copy their setting/names/details.

Idempotent. Backs up + syntax checks both files before writing.
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
# 1. dnd_engine.py — db_init() add tone column
# ─────────────────────────────────────────────────────────

OLD_INIT_MIGRATION = '''    # Migration: add guild_id if pre-existing schema
    cols = [row[1] for row in conn.execute("PRAGMA table_info(dnd_campaigns)").fetchall()]
    if 'guild_id' not in cols:
        conn.execute("ALTER TABLE dnd_campaigns ADD COLUMN guild_id TEXT DEFAULT ''")
    conn.commit()
    conn.close()'''

NEW_INIT_MIGRATION = '''    # Migration: add columns if pre-existing schema
    cols = [row[1] for row in conn.execute("PRAGMA table_info(dnd_campaigns)").fetchall()]
    if 'guild_id' not in cols:
        conn.execute("ALTER TABLE dnd_campaigns ADD COLUMN guild_id TEXT DEFAULT ''")
    if 'tone' not in cols:
        conn.execute("ALTER TABLE dnd_campaigns ADD COLUMN tone TEXT DEFAULT ''")
    conn.commit()
    conn.close()'''

if NEW_INIT_MIGRATION in engine_src:
    print("[skip] db_init migration already includes tone")
elif OLD_INIT_MIGRATION in engine_src:
    engine_src = engine_src.replace(OLD_INIT_MIGRATION, NEW_INIT_MIGRATION)
    print("[ok] db_init: tone column migration added")
else:
    raise SystemExit("[FAIL] db_init migration block not found")


# Also add tone to the CREATE TABLE for fresh installs
OLD_CREATE = '''CREATE TABLE IF NOT EXISTS dnd_campaigns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        created_at TEXT,
        status TEXT DEFAULT 'active',
        world_notes TEXT DEFAULT '',
        current_scene TEXT DEFAULT '',
        guild_id TEXT DEFAULT ''
    )'''

NEW_CREATE = '''CREATE TABLE IF NOT EXISTS dnd_campaigns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        created_at TEXT,
        status TEXT DEFAULT 'active',
        world_notes TEXT DEFAULT '',
        current_scene TEXT DEFAULT '',
        guild_id TEXT DEFAULT '',
        tone TEXT DEFAULT ''
    )'''

if NEW_CREATE in engine_src:
    print("[skip] CREATE TABLE already includes tone")
elif OLD_CREATE in engine_src:
    engine_src = engine_src.replace(OLD_CREATE, NEW_CREATE)
    print("[ok] CREATE TABLE: tone column added")
else:
    raise SystemExit("[FAIL] CREATE TABLE for dnd_campaigns not found")


# ─────────────────────────────────────────────────────────
# 2. dnd_engine.py — get_active_campaign returns tone
# ─────────────────────────────────────────────────────────

OLD_GET_ACTIVE = '''def get_active_campaign(guild_id: str):
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT id, name, current_scene, world_notes FROM dnd_campaigns "
        "WHERE status='active' AND guild_id=? ORDER BY id DESC LIMIT 1",
        (guild_id,)
    ).fetchone()
    conn.close()
    if row:
        return {
            'id': row[0], 'name': row[1],
            'current_scene': row[2], 'world_notes': row[3],
            'guild_id': guild_id
        }
    return None'''

NEW_GET_ACTIVE = '''def get_active_campaign(guild_id: str):
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT id, name, current_scene, world_notes, tone FROM dnd_campaigns "
        "WHERE status='active' AND guild_id=? ORDER BY id DESC LIMIT 1",
        (guild_id,)
    ).fetchone()
    conn.close()
    if row:
        return {
            'id': row[0], 'name': row[1],
            'current_scene': row[2], 'world_notes': row[3],
            'tone': row[4] or '',
            'guild_id': guild_id
        }
    return None'''

if NEW_GET_ACTIVE in engine_src:
    print("[skip] get_active_campaign already selects tone")
elif OLD_GET_ACTIVE in engine_src:
    engine_src = engine_src.replace(OLD_GET_ACTIVE, NEW_GET_ACTIVE)
    print("[ok] get_active_campaign: returns tone")
else:
    raise SystemExit("[FAIL] get_active_campaign not found")


# ─────────────────────────────────────────────────────────
# 3. dnd_engine.py — create_campaign accepts tone
# ─────────────────────────────────────────────────────────

OLD_CREATE_FN = '''def create_campaign(guild_id: str, name: str) -> int:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE dnd_campaigns SET status='inactive' WHERE status='active' AND guild_id=?",
        (guild_id,)
    )
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO dnd_campaigns (name, created_at, status, guild_id) VALUES (?,?,?,?)",
        (name, datetime.datetime.now().isoformat(), 'active', guild_id)
    )
    campaign_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return campaign_id'''

NEW_CREATE_FN = '''def create_campaign(guild_id: str, name: str, tone: str = '') -> int:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE dnd_campaigns SET status='inactive' WHERE status='active' AND guild_id=?",
        (guild_id,)
    )
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO dnd_campaigns (name, created_at, status, guild_id, tone) "
        "VALUES (?,?,?,?,?)",
        (name, datetime.datetime.now().isoformat(), 'active', guild_id, tone)
    )
    campaign_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return campaign_id'''

if NEW_CREATE_FN in engine_src:
    print("[skip] create_campaign already accepts tone")
elif OLD_CREATE_FN in engine_src:
    engine_src = engine_src.replace(OLD_CREATE_FN, NEW_CREATE_FN)
    print("[ok] create_campaign: accepts tone")
else:
    raise SystemExit("[FAIL] create_campaign not found")


# ─────────────────────────────────────────────────────────
# 4. dnd_engine.py — replace build_dm_context() with v3 prompt
# ─────────────────────────────────────────────────────────

# Match from `def build_dm_context` up to (but not including) `def dm_respond`.
BUILD_DM_RE = re.compile(
    r"def build_dm_context\([^)]*\):.*?(?=\ndef dm_respond\()",
    re.DOTALL
)

NEW_BUILD_DM = '''def build_dm_context(campaign, characters, relevant_history="", dm_guidance="",
                     action_type="", avrae_events=None):
    """Compose the system prompt that drives the DM LLM call."""
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
        "STRICTLY NO firearms, NO modern technology, NO science fiction elements, "
        "NO content from other fictional settings (Elder Scrolls/Dwemer/Tamriel, "
        "Marvel, Pokemon, Star Wars, Cyberpunk, etc). Stay in classic fantasy idiom."
    )
    tone = (campaign.get('tone') or '').strip() or DEFAULT_TONE

    history_section = (
        f"\\n\\n=== RELEVANT PAST EVENTS ===\\n{relevant_history}"
        if relevant_history else ""
    )

    guidance_section = (
        f"\\n\\n=== HOW EXPERIENCED DMS HANDLE SIMILAR MOMENTS ===\\n"
        f"These excerpts are for ENERGY and PACING only. NEVER copy their "
        f"settings, character names, places, or specific details — only the "
        f"shape of how they advance a beat.\\n\\n"
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

    action_hint = (
        f"\\n\\nThe player's action looks like a **{action_type}**."
        if action_type and action_type != "general roleplay" else ""
    )

    return f"""You are the Dungeon Master for a D&D 5th Edition campaign called "{campaign['name']}".

=== SETTING & TONE ===
{tone}

=== PARTY ===
{char_summaries}

=== CURRENT SCENE ===
{campaign.get('current_scene') or 'The adventure is just beginning.'}{history_section}{guidance_section}{avrae_section}

=== HOW THIS GAME WORKS ===

You and Avrae split the work cleanly:
- AVRAE handles ALL dice, sheets, HP, attacks, spells, saves, checks, initiative.
- YOU handle scene description, NPC dialogue, world reactions, pacing, story.

=== WHEN TO CALL FOR ROLLS ===

If the player declares an action whose outcome is uncertain (sneak, persuade, attack, perceive, climb, lie, intimidate, recall lore, pick a lock, etc.), CALL FOR THE APPROPRIATE ROLL and stop. End your message with the call.

Examples of how to call for rolls:
  "Roll a Stealth check — `!check stealth`."
  "Make a Persuasion check to win him over — `!check persuasion`."
  "Roll initiative — `!init join`."
  "Make a Dexterity save — `!save dex`."
  "Roll an attack — `!attack` or `!action <weapon name>`."

After calling for a roll, STOP. Do NOT narrate the outcome — Avrae will roll, the result will appear in the next turn's MECHANICAL EVENTS block, and THEN you narrate the consequence.

If the action does not need a roll (free description, walking somewhere safe, opening a normal door, asking a clear question), narrate normally without a roll.

=== READING MECHANICAL EVENTS ===

When MECHANICAL EVENTS are present, those rolls already happened. Narrate the OUTCOME in prose — never re-ask for the roll, never quote the number.

- Total 17+ on a check = solid success. 25+ = exceptional. 5 or below = failure with consequence.
- Nat 20 on the die = spectacular flourish, the world bends to acknowledge it.
- Nat 1 = catastrophic, something memorable goes wrong.
- Attacks against ordinary foes (AC ~13–15) hit if the total is at least that; misses are near-grazes.
- Damage in flesh: 1–3 a scratch, 4–9 a solid hit, 10–19 staggering, 20+ grievous, crits brutal.

=== OUT-OF-CHARACTER REQUESTS ===

If the player asks a meta-question (e.g. "how do I roll", "what should I check", "are you supposed to ask me to roll", anything starting with "OOC:" or in parentheses), DROP CHARACTER. Answer plainly in *italics* with a short, helpful note. Then return to the scene with one fresh sentence.

=== VOICE & PACING ===

- Open with one or two concrete sensory details — sight, sound, smell — grounded in the SETTING & TONE above.
- Move the story forward EVERY turn. Never describe the same thing twice.
- 1–3 short paragraphs per turn. 2–4 sentences per paragraph.
- NPCs have names, voices, quirks, and goals. Even minor ones get a sliver of personality.
- End with: a question to the player, a roll call, or a beat that demands a response.

=== STRICT AVOID LIST ===

- Forbidden phrases (these cliché your prose): "the air clings", "silence is oppressive", "shadows seem to writhe", "shadows seem to twist", "the very [X]", "as if [X] itself was [Y]", "darkness seems to swallow", "your every move", "with calculated silence", "luminescent orbs".
- Do NOT mix genres. NEVER introduce technology, sci-fi, or content from other fictional universes (Elder Scrolls, Dwemer, Marvel, Pokemon, Star Wars, etc) unless the SETTING & TONE explicitly permits.
- Do NOT restate what the player just typed.
- Do NOT invent roll results when no MECHANICAL EVENT is present — call for the roll instead.
- Do NOT pad with atmosphere when story should advance.

=== OUTPUT FORMAT ===

Plain prose. **bold** for important names or words. *italics* for thought, whisper, or OOC asides. No headers, no bullet lists in normal play.{action_hint}"""


'''

m = BUILD_DM_RE.search(engine_src)
if not m:
    raise SystemExit("[FAIL] build_dm_context block not matched")
engine_src = engine_src[:m.start()] + NEW_BUILD_DM + engine_src[m.end():]
print("[ok] build_dm_context: v3 prompt installed")


# ─────────────────────────────────────────────────────────
# 5. discord_dnd_bot.py — /newcampaign accepts tone
# ─────────────────────────────────────────────────────────

OLD_NEWCAMPAIGN = '''@bot.tree.command(name='newcampaign', description='[DM] Start a new campaign for this server.')
@app_commands.describe(name='Campaign name')
async def newcampaign(interaction: discord.Interaction, name: str):
    if not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message("DM only.", ephemeral=True)
        return
    guild_id = str(interaction.guild_id)
    campaign_id = create_campaign(guild_id, name)
    await interaction.response.send_message(
        f"{E['ok']} Campaign **{name}** is active. Players: use `/bindchar` to join."
    )'''

NEW_NEWCAMPAIGN = '''@bot.tree.command(name='newcampaign', description='[DM] Start a new campaign for this server.')
@app_commands.describe(
    name='Campaign name',
    tone='Optional setting/tone (e.g. "grim dark fantasy", "Eberron noir"). Default: classic high fantasy.',
)
async def newcampaign(interaction: discord.Interaction, name: str, tone: str = ''):
    if not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message("DM only.", ephemeral=True)
        return
    guild_id = str(interaction.guild_id)
    campaign_id = create_campaign(guild_id, name, tone)
    tone_note = f" Tone: *{tone}*." if tone else " (Default tone: classic high fantasy.)"
    await interaction.response.send_message(
        f"{E['ok']} Campaign **{name}** is active.{tone_note} "
        f"Players: use `/bindchar` to join."
    )'''

if NEW_NEWCAMPAIGN in bot_src:
    print("[skip] /newcampaign already accepts tone")
elif OLD_NEWCAMPAIGN in bot_src:
    bot_src = bot_src.replace(OLD_NEWCAMPAIGN, NEW_NEWCAMPAIGN)
    print("[ok] /newcampaign: accepts tone")
else:
    raise SystemExit("[FAIL] /newcampaign block not matched")


# ─────────────────────────────────────────────────────────
# 6. discord_dnd_bot.py — dedupe actor_names in footer
# ─────────────────────────────────────────────────────────

OLD_ACTOR = '''        actor_names = [name for name, _ in actions]
        avrae_events = buffer.consume(int(guild_id_str), actor_names)'''

NEW_ACTOR = '''        # Dedupe while preserving order (multiple actions from same actor
        # produced "Donovan Ruby, Donovan Ruby" in the footer).
        seen_actors = set()
        actor_names = []
        for name, _ in actions:
            if name not in seen_actors:
                seen_actors.add(name)
                actor_names.append(name)
        avrae_events = buffer.consume(int(guild_id_str), actor_names)'''

if NEW_ACTOR in bot_src:
    print("[skip] actor_names already deduped")
elif OLD_ACTOR in bot_src:
    bot_src = bot_src.replace(OLD_ACTOR, NEW_ACTOR)
    print("[ok] actor_names: deduped")
else:
    raise SystemExit("[FAIL] actor_names block not matched")


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

engine_backup = ENGINE.with_suffix(f'.py.bak.{stamp}')
engine_backup.write_text(engine_orig)
ENGINE.write_text(engine_src)
print(f"[ok] wrote {ENGINE}")
print(f"[ok] backup {engine_backup}")

bot_backup = BOT.with_suffix(f'.py.bak.{stamp}')
bot_backup.write_text(bot_orig)
BOT.write_text(bot_src)
print(f"[ok] wrote {BOT}")
print(f"[ok] backup {bot_backup}")

print()
print("Next:")
print("  systemctl --user restart virgil-discord")
print("  journalctl --user -u virgil-discord -n 15 --no-pager")
print()
print("Then in Discord, restart your client (clears slash command cache),")
print("run /newcampaign with an optional tone:")
print("  /newcampaign name:Test Run 2 tone:grim dark fantasy, ruined kingdom")
print("Then /bindchar, /play, and try again.")
