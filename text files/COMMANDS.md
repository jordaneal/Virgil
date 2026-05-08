# Virgil + Avrae Command Reference

Last updated: May 7, 2026

This is the canonical command reference for Virgil and the Avrae subset Jordan's
campaigns use. Loaded into advisory mode (`#dm-aside`) on every request.

When commands change, update this file. Advisory mode reads it fresh on each
invocation — no restart needed for content updates.

The Virgil section auto-regenerates from `bot.tree` on every bot startup —
no hand-edits needed there. The Avrae section is hand-edited.

---

## Virgil Slash Commands

Slash commands work in any channel. Player-facing commands respond ephemerally
(only the caller sees them) unless noted otherwise.

<!-- VIRGIL_AUTO_GENERATED:START -->
<!-- This section is auto-generated from bot.tree on startup.
     Edit decorators in discord_dnd_bot.py, NOT this section. -->

### Player commands

- `/clock list` — Show all active progress clocks.
- `/companion list` — Show traveling companions.
- `/inventory [character]` — Show narrative inventory for a character (defaults to your bound character).
- `/quest list [status]` — Show quests for this campaign.

### DM commands

- `/advance [days] [phases] [set_phase]` — Manually advance the campaign clock (days and/or phases).
- `/archived` — List archived (soft-deleted) campaigns for this server.
- `/campaigns` — List active and inactive campaigns. Use /archived to see archived ones.
- `/clock create <name> <capacity>` — Create a new progress clock.
- `/clock delete <name>` — Remove a clock entirely.
- `/clock reset <name>` — Reset a clock to 0 ticks.
- `/clock tick <name> [n]` — Advance a clock by 1 or more segments.
- `/clock untick <name> [n]` — Walk back a clock by 1 or more segments.
- `/companion add <name> [persona]` — Add a traveling companion (max 3).
- `/companion edit <companion_id> [name] [persona]` — Edit a companion.
- `/companion remove <companion_id>` — Remove a companion.
- `/consequence list [npc]` — Show captured consequences for this campaign.
- `/deletecampaign <campaign_ids>` — Soft-delete (archive) one or more campaigns. Comma-separated. Reversible via /setcampaign.
- `/encounter <type>` — Start a stealth, social, or trap encounter (sets mode + spawns clocks).
- `/giveitem <character> <item> [quantity]` — Give an item to a character.
- `/hydrate <npc> <cr>` — Set NPC combat stats from a CR band.
- `/mode <mode>` — Manually set the scene mode (combat/exploration/social/travel/downtime).
- `/newcampaign <name> [tone]` — Start a new campaign for this server.
- `/nudge <player>` — Prompt a player to act in-character.
- `/play [scene]` — Open the scene with an opening narration.
- `/purgeallcampaigns <confirm_phrase>` — PERMANENTLY delete EVERY archived campaign in this server. Irreversible.
- `/purgecampaign <campaign_id> <confirm_phrase>` — PERMANENTLY delete an archived campaign and all its data. Irreversible.
- `/quest add <title> [summary] [priority] [given_by]` — Add a new active quest.
- `/quest complete <quest_id>` — Mark a quest completed.
- `/quest delete <quest_id>` — Permanently delete a quest.
- `/quest fail <quest_id>` — Mark a quest failed.
- `/setcampaign <campaign_id>` — Switch the active campaign for this server.
- `/skeleton load` — (Re)load this campaign's skeleton.md into canon.
- `/skeleton status` — Show this campaign's skeleton file status + entity counts.
- `/travel <destination> [elapsed] [arrival_time]` — Compress travel to a destination. The DM picks up the scene at arrival.

### Setup / housekeeping

- `/bindchar <name>` — Bind your Discord account to a character imported via Avrae.
- `/dmhelp` — Show the player + DM cheatsheet.
- `/refresh [name]` — Refresh the cached character data from a recent Avrae !sheet.
- `/setup` — Create or repair Virgil DM channels. Safe to re-run.

<!-- VIRGIL_AUTO_GENERATED:END -->

---

## Avrae Commands

The subset of Avrae's `!`-commands Jordan's flow uses. Avrae has many more —
see https://avrae.io for full reference. Avrae commands belong in
`#dm-narration` (Avrae rolls land there); they work in other text channels
too but the Virgil narration loop only reads narration.

### Combat — initiative

- `!init begin` — Start combat in the current channel.
- `!init end` — End combat. Avrae prompts for confirmation; combat doesn't actually end until you confirm.
- `!init add <init> <name> [-hp <N>]` — Add a generic combatant with given initiative roll. Use `-hp <N>` to set max HP.
- `!init madd <monster>` — Add a monster from Avrae's bestiary with full stats and HP.
- `!init list` — Show current initiative state (Virgil parses this for combat persistence).
- `!init next` — Advance to the next turn.
- `!init prev` — Back up one turn.
- `!init remove <name>` — Remove a combatant from the order.

### Combat — actions

- `!attack <weapon> -t <target>` — Attack a target. Multi-word weapon names are NOT quoted: `!attack unarmed strike -t Garrick` is correct, `!attack "unarmed strike" -t Garrick` is WRONG (Avrae uses positional parsing). The `-t <target>` is mandatory; bare `!attack` resolves against `<No Target>`.
- `!cast <spell> -t <target>` — Cast a spell at a target. Same syntax conventions as `!attack`.
- `!hp <amount>` — Modify the current combatant's HP (e.g. `!hp -7` deals 7 damage to whoever's turn it is).

### Rolls

- `!check <skill>` — Make a skill check. Multi-word skills unquoted: `!check sleight of hand` is correct.
- `!save <ability>` — Make a saving throw (e.g. `!save dex`).
- `!roll <expression>` — Generic dice roll (e.g. `!roll 1d20+5`, `!roll 2d6`).

### Sheet

- `!sheet` — Show your bound character's sheet as a Discord embed.
- `!update` — Re-pull the latest character data from D&D Beyond.
- `!beyond <share-url>` — Link a D&D Beyond character to your Discord account (one-time setup; shared via the DDB share link).

### Coin / inventory / rests

- `!game coin +Nsp` — Add coin (denominations: `cp`, `sp`, `gp`, `ep`, `pp`). Examples: `!game coin +12sp`, `!game coin -1gp`. Multi-currency loot needs separate commands per denom.
- `!game coin -Nsp` — Remove coin (same syntax).
- `!game longrest` (or alias `!game lr`, or `!lr`) — Take a long rest. Restores HP, hit dice, and spell slots.
- `!game shortrest` (or alias `!game sr`, or `!sr`) — Take a short rest. Restores some resources.

NOTE: Virgil tracks **narrative** inventory (loot, quest objects, found items)
via `/giveitem` and `/inventory`. Avrae tracks **mechanical** sheet-bound gear
(weapons, armor, equipment that affects rolls). They don't sync — that's
deliberate. Avrae owns mechanics; Virgil owns narrative.

---

## Maintenance protocol

- **Virgil slash commands** are auto-generated from bot decorators on every
  startup. Edit `description=` and `app_commands.describe` in
  `discord_dnd_bot.py`, NOT the auto-generated block above. The generator
  preserves everything outside the `<!-- VIRGIL_AUTO_GENERATED:* -->` markers,
  so this `## Notes` section and the entire Avrae section are safe to edit.
- Use category prefix tags `[DM]` / `[SETUP]` / `[PLAYER]` in the `description=`
  argument to override the default categorisation. Tags are stripped before
  rendering. Untagged commands fall back to a name-based heuristic.
- **Avrae commands** are hand-edited. Update when Jordan's flow uses new
  commands; Avrae is an external system so there's no introspection path.
- This file is loaded fresh into advisory mode on every request — no restart
  needed for Avrae-section or maintenance-note edits.

## Notes for Advisory Mode

When suggesting commands to a player:

- **Prefer Virgil slash commands** when both options exist (e.g., `/inventory` over `!i list`). Slash commands work in any channel; Avrae commands belong in `#dm-narration`.
- **Avrae commands belong in `#dm-narration`.** Virgil slash commands work anywhere.
- **Never emit `!`-prefixed commands yourself.** Describe them as options the player should type.
- **When unsure of exact syntax, point the player at this reference rather than guessing.** Hallucinated commands (`/heal`, `!equip`, `!stealth`) erode trust in advisory mode.
- **If a player asks about a command that isn't listed here, say so honestly.** "I don't see that as an available command — you might be thinking of `<closest match>`?" is fine; making up syntax for a non-existent command is not.
- **Multi-word names in Avrae commands are unquoted.** `!attack unarmed strike -t Garrick` and `!check sleight of hand` are correct. Quotes break Avrae's positional parsing.
