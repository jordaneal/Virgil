#!/usr/bin/env python3
"""
patch_bindchar_dmhelp.py
─────────────────────────────────────────────────────────
Surgical patch to discord_dnd_bot.py:

  1. Adds fetch_avrae_sheet_data() helper — scans recent Avrae
     embeds in the channel for a sheet matching the requested
     character name and parses race/class/level from the
     "Race Class Level" first line of the description.

  2. Rewrites /bindchar — race/char_class/level become optional.
     If any are missing it tries to auto-fill from the Avrae
     sheet. Falls back to manual values, defaults level=1.

  3. Rewrites /dmhelp — full onboarding flow including DDB account
     creation, Avrae <-> DDB linking, !beyond import, /bindchar.

Runs idempotently. Backs up + syntax checks before writing.
"""

import re
import ast
import datetime
from pathlib import Path

FILE = Path('/home/jordaneal/scripts/discord_dnd_bot.py')
src_orig = FILE.read_text()
src = src_orig

# ─────────────────────────────────────────────────────────
# 1. Insert fetch_avrae_sheet_data helper before bindchar
# ─────────────────────────────────────────────────────────

HELPER_MARKER = "async def fetch_avrae_sheet_data"
HELPER = '''async def fetch_avrae_sheet_data(channel, character_name: str, lookback: int = 50):
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
                title = (embed.title or '').strip()
                if title.lower() != character_name.lower():
                    continue
                desc = (embed.description or '').strip()
                first_line = desc.split('\\n')[0].strip() if desc else ''
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


'''

if HELPER_MARKER not in src:
    bindchar_anchor = "@bot.tree.command(name='bindchar'"
    if bindchar_anchor not in src:
        raise SystemExit("[FAIL] bindchar anchor not found — file structure changed")
    src = src.replace(bindchar_anchor, HELPER + bindchar_anchor, 1)
    print("[ok] inserted fetch_avrae_sheet_data helper")
else:
    print("[skip] helper already present")

# ─────────────────────────────────────────────────────────
# 2. Replace /bindchar
# ─────────────────────────────────────────────────────────

OLD_BINDCHAR_RE = re.compile(
    r"@bot\.tree\.command\(name='bindchar'.*?"
    r"Use Avrae's `!beyond <share-url>` to load your sheet\.\",\s*\)",
    re.DOTALL
)

NEW_BINDCHAR = '''@bot.tree.command(name='bindchar', description='Bind your Discord account to a character. Auto-fills race/class/level from Avrae if available.')
@app_commands.describe(
    name='Character name (must match your Avrae character)',
    race='Optional — auto-filled from a recent Avrae !sheet or !beyond in this channel',
    char_class='Optional — auto-filled from Avrae',
    level='Optional — auto-filled from Avrae (defaults to 1 if not found)',
)
async def bindchar(interaction: discord.Interaction, name: str, race: str = '',
                   char_class: str = '', level: int = 0):
    guild_id = str(interaction.guild_id)
    campaign = get_active_campaign(guild_id)
    if not campaign:
        await interaction.response.send_message(
            "No active campaign. DM needs to run `/newcampaign` first.", ephemeral=True
        )
        return

    # Auto-fill any missing field from a recent Avrae sheet embed
    auto_filled = False
    if not race or not char_class or level == 0:
        await interaction.response.defer()
        sheet_data = await fetch_avrae_sheet_data(interaction.channel, name)
        if sheet_data:
            race = race or sheet_data['race']
            char_class = char_class or sheet_data['char_class']
            level = level if level > 0 else sheet_data['level']
            auto_filled = True
        if level == 0:
            level = 1
        bind_character(
            campaign_id=campaign['id'],
            controller_id=str(interaction.user.id),
            name=name,
            race=race,
            char_class=char_class,
            level=level,
        )
        suffix = " *(auto-filled from Avrae sheet)*" if auto_filled else ""
        hint = "" if auto_filled else (
            "\\n*Tip: run `!beyond <share-url>` or `!sheet` in this channel "
            "before `/bindchar` so I can grab race/class/level for you.*"
        )
        await interaction.followup.send(
            f"{E['ok']} {interaction.user.mention} is now playing **{name}** "
            f"({race or '?'} {char_class or '?'}, level {level}).{suffix}{hint}"
        )
        return

    # All fields provided manually
    bind_character(
        campaign_id=campaign['id'],
        controller_id=str(interaction.user.id),
        name=name,
        race=race,
        char_class=char_class,
        level=level,
    )
    await interaction.response.send_message(
        f"{E['ok']} {interaction.user.mention} is now playing **{name}** "
        f"({race} {char_class}, level {level})."
    )'''

m = OLD_BINDCHAR_RE.search(src)
if not m:
    raise SystemExit("[FAIL] could not match /bindchar block — already patched? aborting.")
src = src[:m.start()] + NEW_BINDCHAR + src[m.end():]
print("[ok] /bindchar replaced")

# ─────────────────────────────────────────────────────────
# 3. Replace /dmhelp
# ─────────────────────────────────────────────────────────

OLD_DMHELP_RE = re.compile(
    r"@bot\.tree\.command\(name='dmhelp'.*?"
    r"await interaction\.response\.send_message\(msg, ephemeral=True\)",
    re.DOTALL
)

NEW_DMHELP = '''@bot.tree.command(name='dmhelp', description='Show the player + DM cheatsheet.')
async def dmhelp(interaction: discord.Interaction):
    msg = (
        "**Virgil DM — Quick Reference**\\n\\n"
        "**First-time player setup**\\n"
        "1. Create a character at <https://www.dndbeyond.com>\\n"
        "2. Sign in to Avrae: <https://avrae.io> (Discord login)\\n"
        "3. In any channel: `!ddb` → click the link to connect D&D Beyond to Discord\\n"
        "4. Copy your character's share URL from D&D Beyond\\n"
        "5. `!beyond <share-url>` — Avrae imports your sheet\\n"
        "6. `/bindchar name:<CharacterName>` — Virgil auto-fills the rest\\n\\n"
        "**DM setup (per server)**\\n"
        "• `/setup` — create channel structure\\n"
        "• `/newcampaign <name>` — start a campaign\\n\\n"
        "**DM commands**\\n"
        "• `/play [scene]` — open the scene with opening narration\\n"
        "• `/nudge @player` — prompt a player to act\\n"
        "• `/campaigns` — list campaigns\\n\\n"
        "**During play**\\n"
        "• Talk in `#dm-narration` — Virgil narrates consequences\\n"
        "• Roll via Avrae anywhere: `!check stealth`, `!save dex`, "
        "`!attack`, `!cast fireball`\\n"
        "• `!sheet` to view your character, `!sr` short rest, `!lr` long rest\\n\\n"
        "Virgil reads Avrae's rolls automatically and reacts in narration."
    )
    await interaction.response.send_message(msg, ephemeral=True)'''

m2 = OLD_DMHELP_RE.search(src)
if not m2:
    raise SystemExit("[FAIL] could not match /dmhelp block — already patched? aborting.")
src = src[:m2.start()] + NEW_DMHELP + src[m2.end():]
print("[ok] /dmhelp replaced")

# ─────────────────────────────────────────────────────────
# Syntax check
# ─────────────────────────────────────────────────────────

try:
    ast.parse(src)
    print("[ok] syntax check passed")
except SyntaxError as e:
    raise SystemExit(f"[FAIL] syntax error in patched file: {e}")

# ─────────────────────────────────────────────────────────
# Backup + write
# ─────────────────────────────────────────────────────────

stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
backup = FILE.with_suffix(f'.py.bak.{stamp}')
backup.write_text(src_orig)
FILE.write_text(src)
print(f"[ok] wrote {FILE}")
print(f"[ok] backup at {backup}")
print()
print("Next:")
print("  systemctl --user restart virgil-discord")
print("  journalctl --user -u virgil-discord -n 20 --no-pager")
