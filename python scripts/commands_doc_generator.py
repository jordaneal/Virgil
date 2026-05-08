"""Auto-generate the Virgil section of COMMANDS.md from bot.tree commands.

Track 6 #3.2 — eliminate maintenance drift on Virgil-side slash commands.
The Avrae section of COMMANDS.md is operator-maintained (external system,
no introspection path); the Virgil section is regenerated on every bot
startup from `bot.tree.get_commands()` by `update_commands_doc(bot, path)`.

Replacement happens in-place between marker comments:

    <!-- VIRGIL_AUTO_GENERATED:START -->
    ...auto content...
    <!-- VIRGIL_AUTO_GENERATED:END -->

Avrae section sits OUTSIDE the markers and is preserved byte-for-byte.

This module imports nothing from `dnd_engine` or `discord_dnd_bot` so the
introspector and renderer can be unit-tested without launching Discord.
The only Discord coupling is at runtime when the live `bot` is passed in.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional


# ─────────────────────────────────────────────────────────
# Markers + categorization
# ─────────────────────────────────────────────────────────

START_MARKER = "<!-- VIRGIL_AUTO_GENERATED:START -->"
END_MARKER = "<!-- VIRGIL_AUTO_GENERATED:END -->"

# Recognised inline category tags. The first match (case-insensitive) wins.
# Tags appear at the start of the description; they're stripped before the
# description is rendered so the auto-section reads cleanly.
_TAG_DM = "[DM]"
_TAG_SETUP = "[SETUP]"
_TAG_PLAYER = "[PLAYER]"
_KNOWN_TAGS = (_TAG_DM, _TAG_SETUP, _TAG_PLAYER)

# Name-based fallback when no tag is present. Mirrors how the existing
# COMMANDS.md was hand-organized in 6 #3.1 — this fallback is the safety
# net for legacy commands that haven't been re-tagged yet.
_SETUP_NAMES = frozenset({"setup", "bindchar", "refresh", "dmhelp"})
_DM_NAMES = frozenset({
    "play", "newcampaign", "campaigns", "archived", "setcampaign",
    "deletecampaign", "purgecampaign", "purgeallcampaigns", "nudge",
    "travel", "mode", "encounter", "giveitem",
    # group prefixes (subcommands inherit unless they have their own tag)
    "clock", "quest", "companion", "skeleton", "consequence",
})

CATEGORY_DM = "DM"
CATEGORY_SETUP = "SETUP"
CATEGORY_PLAYER = "PLAYER"

# Render order + section headings. Order matches the operator's existing
# COMMANDS.md so the auto-output reads naturally for anyone scanning the file.
_CATEGORY_HEADINGS = [
    (CATEGORY_PLAYER, "### Player commands"),
    (CATEGORY_DM,     "### DM commands"),
    (CATEGORY_SETUP,  "### Setup / housekeeping"),
]


# ─────────────────────────────────────────────────────────
# Description tag stripping
# ─────────────────────────────────────────────────────────

def _strip_category_tag(description: str) -> tuple[str, Optional[str]]:
    """Detect and strip a leading `[TAG]` from a description.

    Returns (cleaned_description, category | None). `None` means no
    recognised tag — caller falls back to name-based heuristic.
    """
    if not description:
        return "", None
    text = description.lstrip()
    upper = text.upper()
    for tag in _KNOWN_TAGS:
        if upper.startswith(tag):
            cleaned = text[len(tag):].lstrip()
            if tag == _TAG_DM:
                return cleaned, CATEGORY_DM
            if tag == _TAG_SETUP:
                return cleaned, CATEGORY_SETUP
            if tag == _TAG_PLAYER:
                return cleaned, CATEGORY_PLAYER
    return text, None


def _categorize(name: str, parent_name: Optional[str],
                tagged_category: Optional[str]) -> str:
    """Decide the category bucket for a command.

    Precedence: explicit tag > name fallback (subcommand checks own name,
    then parent group name) > PLAYER default.
    """
    if tagged_category is not None:
        return tagged_category
    candidates = [name]
    if parent_name:
        candidates.append(parent_name)
    for n in candidates:
        if n in _SETUP_NAMES:
            return CATEGORY_SETUP
        if n in _DM_NAMES:
            return CATEGORY_DM
    return CATEGORY_PLAYER


# ─────────────────────────────────────────────────────────
# Introspection
# ─────────────────────────────────────────────────────────

def introspect_virgil_commands(bot) -> list[dict]:
    """Walk `bot.tree.get_commands()` and return a flat list of command rows.

    Each row:
        {
            'name': '/quest add',           # full /-path including group
            'description': 'Add a new ...',  # tag stripped
            'parameters': [                  # ordered as declared
                {'name': 'priority', 'description': '...', 'required': False},
                ...
            ],
            'category': 'DM',                # 'DM' | 'SETUP' | 'PLAYER'
        }

    Group containers themselves don't render — only their leaf commands do.
    A group's category propagates to subcommands via the name-fallback
    when the subcommand has no own tag.
    """
    rows: list[dict] = []
    if bot is None or not hasattr(bot, "tree"):
        return rows
    try:
        top_level = list(bot.tree.get_commands())
    except Exception:
        return rows

    for cmd in top_level:
        # Discord.py exposes Group instances via the same .get_commands() —
        # detect by presence of `.commands` attribute (set on Group only).
        subs = getattr(cmd, "commands", None)
        if subs:
            # Iterate group children. Group's own description carries the
            # tag for category-fallback; subcommands can override.
            _, group_tag = _strip_category_tag(cmd.description or "")
            for sub in subs:
                rows.append(_build_row(sub, parent=cmd, fallback_tag=group_tag))
        else:
            rows.append(_build_row(cmd, parent=None, fallback_tag=None))
    return rows


def _build_row(cmd, parent=None, fallback_tag: Optional[str] = None) -> dict:
    """Convert a single discord.py app-command into our row dict."""
    raw_desc = (getattr(cmd, "description", "") or "").strip()
    cleaned, own_tag = _strip_category_tag(raw_desc)
    # If the subcommand has no own tag, inherit the parent group's tag.
    effective_tag = own_tag if own_tag is not None else fallback_tag

    parent_name = getattr(parent, "name", None) if parent else None
    category = _categorize(cmd.name, parent_name, effective_tag)

    if parent_name:
        full_name = f"/{parent_name} {cmd.name}"
    else:
        full_name = f"/{cmd.name}"

    params = []
    for p in (getattr(cmd, "parameters", None) or []):
        params.append({
            "name": p.name,
            "description": (p.description or "").strip(),
            "required": bool(getattr(p, "required", False)),
        })

    return {
        "name": full_name,
        "description": cleaned,
        "parameters": params,
        "category": category,
    }


# ─────────────────────────────────────────────────────────
# Rendering
# ─────────────────────────────────────────────────────────

def _format_param_signature(params: list[dict]) -> str:
    """Render parameters as `<required>` `[optional]` tokens, space-joined."""
    if not params:
        return ""
    bits = []
    for p in params:
        token = f"<{p['name']}>" if p.get("required") else f"[{p['name']}]"
        bits.append(token)
    return " ".join(bits)


def _format_command_line(row: dict) -> str:
    """Render one command as a markdown bullet."""
    sig = _format_param_signature(row["parameters"])
    head = f"`{row['name']}`"
    if sig:
        head = f"`{row['name']} {sig}`"
    desc = row["description"] or "(no description)"
    return f"- {head} — {desc}"


def render_virgil_section(commands: list[dict]) -> str:
    """Format the introspected command list as the markdown that goes
    between the marker comments in COMMANDS.md.

    Sections render in a fixed order (Player → DM → Setup) so doc diffs
    only reflect actual command changes, not list-shuffle noise.
    """
    if not commands:
        return (
            "_No Virgil slash commands registered. (Auto-generation ran but "
            "found nothing — check `bot.tree.sync()` ordering at startup.)_"
        )

    by_cat: dict[str, list[dict]] = {
        CATEGORY_PLAYER: [],
        CATEGORY_DM: [],
        CATEGORY_SETUP: [],
    }
    for row in commands:
        by_cat.setdefault(row["category"], []).append(row)

    # Stable alphabetical ordering within each section.
    for cat in by_cat:
        by_cat[cat].sort(key=lambda r: r["name"])

    out_blocks: list[str] = []
    for cat, heading in _CATEGORY_HEADINGS:
        rows = by_cat.get(cat) or []
        if not rows:
            continue
        out_blocks.append(heading)
        out_blocks.append("")
        for r in rows:
            out_blocks.append(_format_command_line(r))
        out_blocks.append("")  # blank line between sections

    return "\n".join(out_blocks).rstrip() + "\n"


# ─────────────────────────────────────────────────────────
# Doc update — idempotent in-place rewrite
# ─────────────────────────────────────────────────────────

# Match `<!-- START -->...<!-- END -->` as a single non-greedy block,
# preserving everything outside the markers.
_MARKER_RX = re.compile(
    re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER),
    re.DOTALL,
)


def update_commands_doc(bot, doc_path) -> dict:
    """Idempotent in-place update of COMMANDS.md's Virgil section.

    Reads the file, replaces content between START/END markers with a
    freshly-generated Virgil section, writes back ONLY when content
    actually changed. Avrae section (outside the markers) is preserved
    byte-for-byte.

    Returns:
        {
            'commands_count': int,    # number of leaf commands rendered
            'doc_changed': bool,      # True iff bytes were written
            'markers_found': bool,    # False if file lacks marker pair
            'error': str | None,      # populated on file errors
        }

    Soft-fails: never raises. Bot startup must not block on doc generation.
    """
    result = {
        "commands_count": 0,
        "doc_changed": False,
        "markers_found": False,
        "error": None,
    }
    path = Path(doc_path)

    # Read file — return error on missing/unreadable; bot startup continues.
    try:
        existing = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        result["error"] = f"file_not_found: {path}"
        return result
    except Exception as e:
        result["error"] = f"read_error: {e!r}"
        return result

    # Markers must be present — operator adds them once during migration.
    # Without markers, refuse to modify (we'd have nowhere to write).
    if START_MARKER not in existing or END_MARKER not in existing:
        result["error"] = "markers_missing"
        return result
    result["markers_found"] = True

    # Introspect + render fresh.
    try:
        rows = introspect_virgil_commands(bot)
    except Exception as e:
        result["error"] = f"introspect_error: {e!r}"
        return result
    result["commands_count"] = len(rows)

    try:
        rendered = render_virgil_section(rows)
    except Exception as e:
        result["error"] = f"render_error: {e!r}"
        return result

    new_block = (
        f"{START_MARKER}\n"
        f"<!-- This section is auto-generated from bot.tree on startup.\n"
        f"     Edit decorators in discord_dnd_bot.py, NOT this section. -->\n\n"
        f"{rendered}\n"
        f"{END_MARKER}"
    )
    new_doc = _MARKER_RX.sub(new_block, existing, count=1)

    if new_doc == existing:
        # No-op write avoidance — preserves mtime, avoids spurious VCS diffs.
        return result

    # Atomic write via temp + rename so a crash mid-write doesn't truncate.
    try:
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(new_doc, encoding="utf-8")
        tmp.replace(path)
    except Exception as e:
        result["error"] = f"write_error: {e!r}"
        return result

    result["doc_changed"] = True
    return result
