#!/usr/bin/env python3
"""
patch_setup_perms.py
─────────────────────────────────────────────────────────
Fix /setup so the bot's permissions are set explicitly per channel,
not left to inherit from category/role defaults that can silently
deny "Read Message History" (the autocomplete failure we just hit).

Behavior:
  - Every channel created by /setup now has an explicit permission
    overwrite for the bot granting view, send, read history, embed,
    attach, add reactions, and manage messages.
  - Re-running /setup also REPAIRS existing channels by applying the
    same overwrite — so this command is now self-healing.
  - The category gets the overwrite too, so freshly-created channels
    inherit cleanly even if Discord adds future channels there.

Idempotent. Backs up + syntax checks before writing.
"""

import re
import ast
import datetime
from pathlib import Path

BOT = Path('/home/jordaneal/scripts/discord_dnd_bot.py')
bot_orig = BOT.read_text()
src = bot_orig


# ─────────────────────────────────────────────────────────
# Replace the body of /setup
# ─────────────────────────────────────────────────────────

OLD_SETUP_RE = re.compile(
    r"@bot\.tree\.command\(name='setup', description='\[DM\] Create channels for D&D\. Run once per server\.'\)\n"
    r"async def setup\(interaction: discord\.Interaction\):.*?"
    r"await interaction\.followup\.send\(msg, ephemeral=True\)",
    re.DOTALL
)

NEW_SETUP = '''@bot.tree.command(name='setup', description='[DM] Create or repair D&D channels. Safe to re-run.')
async def setup(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.manage_channels:
        await interaction.response.send_message("DM only — needs Manage Channels.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)

    guild = interaction.guild
    me = guild.me

    # The exact overwrite the bot needs everywhere it operates. Defining it
    # once and applying everywhere prevents the "autocomplete returns 'no
    # options'" bug from a missing read_message_history.
    bot_overwrite = discord.PermissionOverwrite(
        view_channel=True,
        read_message_history=True,
        send_messages=True,
        embed_links=True,
        attach_files=True,
        add_reactions=True,
        manage_messages=True,
        use_external_emojis=True,
    )

    # Category — created with bot overwrite so child channels inherit cleanly
    category = discord.utils.get(guild.categories, name="🎲 D&D")
    if not category:
        category = await guild.create_category(
            "🎲 D&D",
            overwrites={me: bot_overwrite},
        )
    else:
        # Repair: re-assert the overwrite on the existing category
        try:
            await category.set_permissions(me, overwrite=bot_overwrite)
        except Exception as e:
            log(f"setup: could not set category overwrite: {e}")

    created = []
    repaired = []
    for key, name in CHANNEL_NAMES.items():
        existing = discord.utils.get(guild.text_channels, name=name)
        topic = {
            'narration': "DM narration. Type your actions here. Avrae rolls go in #dice-rolls.",
            'rolls':     "Avrae rolls (`!check`, `!save`, `!attack`, `!cast`).",
            'sheets':    "Character sheets — Avrae's `!sheet` output goes here.",
            'loot':      "Party loot, items, gold.",
            'lore':      "World lore, NPCs, locations.",
            'ooc':       "Out-of-character chat. The DM doesn't watch this channel.",
            'commands':  "Bot commands and admin.",
        }.get(key, "")

        if existing:
            # Repair: ensure the bot has the right perms on this channel
            try:
                await existing.set_permissions(me, overwrite=bot_overwrite)
                repaired.append(existing.mention)
            except Exception as e:
                log(f"setup: could not repair perms on #{name}: {e}")
            continue

        ch = await guild.create_text_channel(
            name,
            category=category,
            topic=topic,
            overwrites={me: bot_overwrite},
        )
        created.append(ch.mention)

    msg = f"{E['ok']} D&D channels ready."
    if created:
        msg += f"\\nCreated: {', '.join(created)}"
    if repaired:
        msg += f"\\nRepaired permissions on: {', '.join(repaired)}"
    msg += "\\n\\n**Next steps:**\\n"
    msg += "1. Invite Avrae from <https://avrae.io>\\n"
    msg += "2. Each player links D&D Beyond at <https://avrae.io>, runs `!beyond <share-url>` here\\n"
    msg += "3. DM runs `/newcampaign <name>`\\n"
    msg += "4. Each player runs `/bindchar` and picks their character\\n"
    msg += "5. DM runs `/play <opening scene>` to begin"
    await interaction.followup.send(msg, ephemeral=True)'''

m = OLD_SETUP_RE.search(src)
if not m:
    if "Repaired permissions on" in src:
        print("[skip] /setup already patched")
    else:
        raise SystemExit("[FAIL] /setup block not matched")
else:
    src = src[:m.start()] + NEW_SETUP + src[m.end():]
    print("[ok] /setup: explicit per-channel bot overwrites + repair pass")


# ─────────────────────────────────────────────────────────
# Syntax check
# ─────────────────────────────────────────────────────────

try:
    ast.parse(src)
    print("[ok] discord_dnd_bot.py syntax check passed")
except SyntaxError as e:
    raise SystemExit(f"[FAIL] syntax error: {e}")


# ─────────────────────────────────────────────────────────
# Backup + write
# ─────────────────────────────────────────────────────────

stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
backup = BOT.with_suffix(f'.py.bak.{stamp}')
backup.write_text(bot_orig)
BOT.write_text(src)
print(f"[ok] wrote {BOT}")
print(f"[ok] backup {backup}")
print()
print("Next:")
print("  systemctl --user restart virgil-discord")
print()
print("Then in Discord, run /setup again — it will repair existing channels'")
print("permissions automatically. After that, /bindchar autocomplete works")
print("in any of our channels without manual permission edits.")
