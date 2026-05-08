#!/usr/bin/env python3
"""
patch_bindchar_autocomplete.py
─────────────────────────────────────────────────────────
Converts /bindchar to a strict, autocomplete-driven flow:

  - Single arg: name (with autocomplete)
  - Autocomplete scans recent channel messages for Avrae
    sheet embeds and surfaces character names as choices.
  - On submit, /bindchar re-fetches the sheet for the chosen
    name and binds with full race/class/level.
  - If Avrae has no sheet in the channel, /bindchar refuses
    with a clear setup reminder.

Also updates /dmhelp to reflect the simplified flow.

Idempotent. Backs up + syntax checks before writing.
"""

import re
import ast
import datetime
from pathlib import Path

FILE = Path('/home/jordaneal/scripts/discord_dnd_bot.py')
src_orig = FILE.read_text()
src = src_orig


# ─────────────────────────────────────────────────────────
# 1. Add scan_avrae_characters helper next to fetch_avrae_sheet_data
# ─────────────────────────────────────────────────────────

SCAN_MARKER = "async def scan_avrae_characters"
SCAN_HELPER = '''async def scan_avrae_characters(channel, lookback: int = 50) -> list[dict]:
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
                first_line = desc.split('\\n')[0].strip() if desc else ''
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


'''

if SCAN_MARKER not in src:
    # Insert right before fetch_avrae_sheet_data
    anchor = "async def fetch_avrae_sheet_data"
    if anchor not in src:
        raise SystemExit("[FAIL] fetch_avrae_sheet_data anchor missing")
    src = src.replace(anchor, SCAN_HELPER + anchor, 1)
    print("[ok] inserted scan_avrae_characters helper")
else:
    print("[skip] scan_avrae_characters already present")


# ─────────────────────────────────────────────────────────
# 2. Replace /bindchar with autocomplete-driven version
# ─────────────────────────────────────────────────────────

OLD_BINDCHAR_RE = re.compile(
    r"@bot\.tree\.command\(name='bindchar'.*?"
    r"f\"\(\{race\} \{char_class\}, level \{level\}\)\.\"\s*\)",
    re.DOTALL
)

NEW_BINDCHAR = '''async def _bindchar_autocomplete(interaction: discord.Interaction, current: str):
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
            f"{E['facepalm']} I can't find an Avrae sheet for **{name}** in this channel.\\n\\n"
            "**Setup checklist**\\n"
            "1. Make a character at <https://www.dndbeyond.com>\\n"
            "2. Sign in to <https://avrae.io> with Discord\\n"
            "3. In Discord: `!ddb` → click the link to connect D&D Beyond\\n"
            "4. `!beyond <character-share-url>` to import\\n"
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
    )'''

m = OLD_BINDCHAR_RE.search(src)
if not m:
    # Already patched? Check for autocomplete signature.
    if "_bindchar_autocomplete" in src:
        print("[skip] /bindchar already autocomplete-driven")
    else:
        raise SystemExit("[FAIL] could not match current /bindchar block")
else:
    src = src[:m.start()] + NEW_BINDCHAR + src[m.end():]
    print("[ok] /bindchar replaced with autocomplete version")


# ─────────────────────────────────────────────────────────
# 3. Update /dmhelp
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
        "2. Sign in to <https://avrae.io> (Discord login)\\n"
        "3. In any channel: `!ddb` → click the link to connect D&D Beyond\\n"
        "4. Copy your character's share URL from D&D Beyond\\n"
        "5. `!beyond <share-url>` — Avrae imports your sheet\\n"
        "6. `/bindchar` — pick your character from the dropdown\\n\\n"
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
    raise SystemExit("[FAIL] could not match /dmhelp block")
src = src[:m2.start()] + NEW_DMHELP + src[m2.end():]
print("[ok] /dmhelp updated")


# ─────────────────────────────────────────────────────────
# Syntax check
# ─────────────────────────────────────────────────────────

try:
    ast.parse(src)
    print("[ok] syntax check passed")
except SyntaxError as e:
    raise SystemExit(f"[FAIL] syntax error: {e}")


# ─────────────────────────────────────────────────────────
# Backup + write
# ─────────────────────────────────────────────────────────

stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
backup = FILE.with_suffix(f'.py.bak.{stamp}')
backup.write_text(src_orig)
FILE.write_text(src)
print(f"[ok] wrote {FILE}")
print(f"[ok] backup {backup}")
print()
print("Next:")
print("  systemctl --user restart virgil-discord")
print("  journalctl --user -u virgil-discord -n 15 --no-pager")
