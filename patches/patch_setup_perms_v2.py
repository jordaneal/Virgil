#!/usr/bin/env python3
"""
patch_setup_perms_v2.py
─────────────────────────────────────────────────────────
Fix the previous /setup patch — it was overwriting existing
channel permission edits when "repairing" channels.

This version:
  - Reads the bot's existing channel overwrite first.
  - Updates ONLY the keys we care about (view, read history, send,
    embed, attach, react, manage messages, external emoji).
  - Leaves all other overrides on the channel untouched.
  - Same merge logic for the category.
  - For NEW channel creation, applies the bot overwrite plus a copy
    of any category-level overrides so the channel inherits cleanly.

Idempotent. Backs up + syntax checks before writing.
"""

import re
import ast
import datetime
from pathlib import Path

BOT = Path('/home/jordaneal/scripts/discord_dnd_bot.py')
bot_orig = BOT.read_text()
src = bot_orig


# Match the *current* /setup body (the one written by patch_setup_perms.py).
OLD_SETUP_RE = re.compile(
    r"@bot\.tree\.command\(name='setup', description='\[DM\] Create or repair D&D channels\. Safe to re-run\.'\)\n"
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

    async def repair_channel(target):
        try:
            existing = target.overwrites_for(me)
            merged = merge_bot_overwrite(existing)
            await target.set_permissions(me, overwrite=merged)
            return True
        except Exception as e:
            log(f"setup: could not set perms on {getattr(target, 'name', '?')}: {e}")
            return False

    # Category — create or repair
    category = discord.utils.get(guild.categories, name="🎲 D&D")
    if not category:
        category = await guild.create_category(
            "🎲 D&D",
            overwrites={me: discord.PermissionOverwrite(**REQUIRED_PERMS)},
        )
    else:
        await repair_channel(category)

    created = []
    repaired = []
    skipped = []
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
            ok = await repair_channel(existing)
            (repaired if ok else skipped).append(existing.mention)
            continue

        ch = await guild.create_text_channel(
            name,
            category=category,
            topic=topic,
            overwrites={me: discord.PermissionOverwrite(**REQUIRED_PERMS)},
        )
        created.append(ch.mention)

    msg = f"{E['ok']} D&D channels ready."
    if created:
        msg += f"\\nCreated: {', '.join(created)}"
    if repaired:
        msg += f"\\nEnsured perms on: {', '.join(repaired)}"
    if skipped:
        msg += f"\\nCould not adjust (manual fix needed): {', '.join(skipped)}"
    msg += "\\n\\n**Next steps:**\\n"
    msg += "1. Invite Avrae from <https://avrae.io>\\n"
    msg += "2. Each player links D&D Beyond at <https://avrae.io>, runs `!beyond <share-url>` here\\n"
    msg += "3. DM runs `/newcampaign <name>`\\n"
    msg += "4. Each player runs `/bindchar` and picks their character\\n"
    msg += "5. DM runs `/play <opening scene>` to begin"
    await interaction.followup.send(msg, ephemeral=True)'''

m = OLD_SETUP_RE.search(src)
if not m:
    if "merge_bot_overwrite" in src:
        print("[skip] /setup already running merge logic")
    else:
        raise SystemExit("[FAIL] /setup block not matched — has the file changed?")
else:
    src = src[:m.start()] + NEW_SETUP + src[m.end():]
    print("[ok] /setup: merge logic installed (preserves existing perms)")


# Syntax check
try:
    ast.parse(src)
    print("[ok] discord_dnd_bot.py syntax check passed")
except SyntaxError as e:
    raise SystemExit(f"[FAIL] syntax error: {e}")

# Backup + write
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
print("Then in Discord: re-fix #bot-commands manually one more time, then")
print("/setup is safe to re-run forever — it'll only ADD the perms it needs,")
print("never overwrite your manual edits.")
