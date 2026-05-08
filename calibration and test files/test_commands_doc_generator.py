"""Tests for the auto-generation of the Virgil section of COMMANDS.md.

Track 6 #3.2 — `commands_doc_generator` introspects `bot.tree.get_commands()`
and rewrites the marked block in COMMANDS.md. Tests use a tiny fake bot
+ tempfile fixtures so no Discord client is required.

Run:
    cd /home/jordaneal/scripts && python3 test_commands_doc_generator.py
"""

import sys
import tempfile
import unittest.mock as mock
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

sys.path.insert(0, '/home/jordaneal/scripts')

import commands_doc_generator as gen


# ─── Fake bot.tree types ─────────────────────────────────────────────
# Mirror the duck-typed surface introspect_virgil_commands consumes:
# every command has .name / .description / .parameters; groups have
# .commands. Real discord.py types satisfy the same shape.

@dataclass
class FakeParam:
    name: str
    description: str = ""
    required: bool = False


@dataclass
class FakeCommand:
    name: str
    description: str = ""
    parameters: list = field(default_factory=list)


@dataclass
class FakeGroup:
    name: str
    description: str = ""
    commands: list = field(default_factory=list)


class FakeTree:
    def __init__(self, commands):
        self._commands = commands

    def get_commands(self):
        return self._commands


class FakeBot:
    def __init__(self, commands):
        self.tree = FakeTree(commands)


# ─── Tag stripping ───────────────────────────────────────────────────

def test_strip_dm_tag():
    cleaned, cat = gen._strip_category_tag("[DM] Open the scene.")
    assert cleaned == "Open the scene."
    assert cat == gen.CATEGORY_DM


def test_strip_setup_tag():
    cleaned, cat = gen._strip_category_tag("[SETUP] Create channels.")
    assert cleaned == "Create channels."
    assert cat == gen.CATEGORY_SETUP


def test_strip_player_tag():
    cleaned, cat = gen._strip_category_tag("[PLAYER] Show inventory.")
    assert cleaned == "Show inventory."
    assert cat == gen.CATEGORY_PLAYER


def test_strip_no_tag():
    cleaned, cat = gen._strip_category_tag("Just a description.")
    assert cleaned == "Just a description."
    assert cat is None


def test_strip_tag_case_insensitive():
    cleaned, cat = gen._strip_category_tag("[dm] lowercase tag.")
    assert cleaned == "lowercase tag."
    assert cat == gen.CATEGORY_DM


def test_strip_tag_handles_empty():
    cleaned, cat = gen._strip_category_tag("")
    assert cleaned == ""
    assert cat is None


# ─── Categorization ──────────────────────────────────────────────────

def test_categorize_tag_wins_over_name():
    # Even if name suggests SETUP, an explicit [DM] tag overrides.
    assert gen._categorize("setup", None, gen.CATEGORY_DM) == gen.CATEGORY_DM


def test_categorize_name_setup_fallback():
    assert gen._categorize("setup", None, None) == gen.CATEGORY_SETUP
    assert gen._categorize("dmhelp", None, None) == gen.CATEGORY_SETUP
    assert gen._categorize("refresh", None, None) == gen.CATEGORY_SETUP


def test_categorize_name_dm_fallback():
    assert gen._categorize("play", None, None) == gen.CATEGORY_DM
    assert gen._categorize("travel", None, None) == gen.CATEGORY_DM


def test_categorize_subcommand_inherits_parent():
    # /clock list — child of clock group, no own tag → DM via parent name
    assert gen._categorize("list", "clock", None) == gen.CATEGORY_DM


def test_categorize_default_player():
    assert gen._categorize("totally_made_up", None, None) == gen.CATEGORY_PLAYER


# ─── Introspection ───────────────────────────────────────────────────

def test_introspect_top_level_commands():
    bot = FakeBot([
        FakeCommand(name="play", description="[DM] Open the scene."),
        FakeCommand(name="bindchar", description="Bind a character."),
    ])
    rows = gen.introspect_virgil_commands(bot)
    by_name = {r["name"]: r for r in rows}
    assert "/play" in by_name
    assert by_name["/play"]["category"] == gen.CATEGORY_DM
    assert by_name["/play"]["description"] == "Open the scene."  # tag stripped
    assert "/bindchar" in by_name
    assert by_name["/bindchar"]["category"] == gen.CATEGORY_SETUP


def test_introspect_group_commands():
    group = FakeGroup(
        name="clock", description="[DM] Manage clocks.",
        commands=[
            FakeCommand(name="create", description="Create a clock."),
            FakeCommand(name="list", description="Show clocks."),
        ],
    )
    bot = FakeBot([group])
    rows = gen.introspect_virgil_commands(bot)
    names = [r["name"] for r in rows]
    # Group itself doesn't render — only leaves.
    assert "/clock" not in names
    assert "/clock create" in names
    assert "/clock list" in names
    # Subcommands inherit parent's [DM] tag since they have no own tag.
    by_name = {r["name"]: r for r in rows}
    assert by_name["/clock create"]["category"] == gen.CATEGORY_DM


def test_introspect_subcommand_own_tag_overrides_parent():
    group = FakeGroup(
        name="clock", description="[DM] Manage clocks.",
        commands=[
            FakeCommand(name="public", description="[PLAYER] Show clocks."),
        ],
    )
    bot = FakeBot([group])
    rows = gen.introspect_virgil_commands(bot)
    assert rows[0]["category"] == gen.CATEGORY_PLAYER


def test_introspect_parameters():
    bot = FakeBot([
        FakeCommand(
            name="giveitem",
            description="[DM] Give an item.",
            parameters=[
                FakeParam(name="character", required=True, description="Who"),
                FakeParam(name="item", required=True, description="What"),
                FakeParam(name="quantity", required=False, description="N"),
            ],
        ),
    ])
    rows = gen.introspect_virgil_commands(bot)
    params = rows[0]["parameters"]
    assert [p["name"] for p in params] == ["character", "item", "quantity"]
    assert params[0]["required"] is True
    assert params[2]["required"] is False


def test_introspect_handles_none_bot():
    assert gen.introspect_virgil_commands(None) == []


def test_introspect_handles_bot_without_tree():
    class NoTree: pass
    assert gen.introspect_virgil_commands(NoTree()) == []


# ─── Rendering ───────────────────────────────────────────────────────

def test_render_param_signature_required_and_optional():
    sig = gen._format_param_signature([
        {"name": "character", "required": True},
        {"name": "item", "required": True},
        {"name": "quantity", "required": False},
    ])
    assert sig == "<character> <item> [quantity]"


def test_render_param_signature_empty():
    assert gen._format_param_signature([]) == ""


def test_render_command_line_with_params():
    row = {
        "name": "/giveitem",
        "description": "Give an item.",
        "parameters": [
            {"name": "character", "required": True},
            {"name": "item", "required": True},
            {"name": "quantity", "required": False},
        ],
        "category": gen.CATEGORY_DM,
    }
    line = gen._format_command_line(row)
    assert line == "- `/giveitem <character> <item> [quantity]` — Give an item."


def test_render_command_line_no_params():
    row = {
        "name": "/dmhelp",
        "description": "Show the cheatsheet.",
        "parameters": [],
        "category": gen.CATEGORY_SETUP,
    }
    assert gen._format_command_line(row) == "- `/dmhelp` — Show the cheatsheet."


def test_render_section_orders_player_dm_setup():
    rows = [
        {"name": "/setup", "description": "Setup.", "parameters": [],
         "category": gen.CATEGORY_SETUP},
        {"name": "/play", "description": "Play.", "parameters": [],
         "category": gen.CATEGORY_DM},
        {"name": "/inventory", "description": "Inv.", "parameters": [],
         "category": gen.CATEGORY_PLAYER},
    ]
    out = gen.render_virgil_section(rows)
    p_idx = out.index("Player commands")
    d_idx = out.index("DM commands")
    s_idx = out.index("Setup / housekeeping")
    assert p_idx < d_idx < s_idx


def test_render_section_alphabetical_within_category():
    rows = [
        {"name": "/zebra", "description": "z", "parameters": [],
         "category": gen.CATEGORY_PLAYER},
        {"name": "/apple", "description": "a", "parameters": [],
         "category": gen.CATEGORY_PLAYER},
        {"name": "/mango", "description": "m", "parameters": [],
         "category": gen.CATEGORY_PLAYER},
    ]
    out = gen.render_virgil_section(rows)
    assert out.index("/apple") < out.index("/mango") < out.index("/zebra")


def test_render_section_empty_returns_placeholder():
    out = gen.render_virgil_section([])
    assert "No Virgil slash commands registered" in out


def test_render_section_skips_empty_categories():
    # Only DM rows present — Player + Setup headings should NOT render.
    rows = [
        {"name": "/play", "description": "p", "parameters": [],
         "category": gen.CATEGORY_DM},
    ]
    out = gen.render_virgil_section(rows)
    assert "DM commands" in out
    assert "Player commands" not in out
    assert "Setup / housekeeping" not in out


# ─── update_commands_doc ─────────────────────────────────────────────

def _make_doc_with_markers(virgil_body: str = "(initial placeholder)\n",
                            avrae_body: str = "## Avrae Commands\n\n- `!attack` — attack.\n",
                            notes_body: str = "## Notes\n\nstuff.\n") -> str:
    return (
        f"# Virgil + Avrae Command Reference\n\n"
        f"## Virgil Slash Commands\n\n"
        f"{gen.START_MARKER}\n"
        f"{virgil_body}"
        f"{gen.END_MARKER}\n\n"
        f"---\n\n"
        f"{avrae_body}\n"
        f"---\n\n"
        f"{notes_body}"
    )


def test_update_doc_replaces_block_between_markers():
    bot = FakeBot([
        FakeCommand(name="play", description="[DM] Open the scene."),
    ])
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md',
                                      delete=False, encoding='utf-8') as f:
        f.write(_make_doc_with_markers())
        path = f.name
    try:
        result = gen.update_commands_doc(bot, path)
        assert result["error"] is None
        assert result["markers_found"] is True
        assert result["doc_changed"] is True
        assert result["commands_count"] == 1
        new = Path(path).read_text(encoding="utf-8")
        assert "/play" in new
        assert "Open the scene." in new
        # Tag stripped
        assert "[DM]" not in new.split(gen.END_MARKER)[0]
    finally:
        Path(path).unlink(missing_ok=True)


def test_update_doc_preserves_avrae_section_byte_for_byte():
    bot = FakeBot([FakeCommand(name="play", description="[DM] Open.")])
    avrae = "## Avrae Commands\n\n- `!attack <weapon> -t <target>` — Attack.\n- `!cast <spell>` — Cast.\n"
    notes = "## Notes for Advisory Mode\n\nDo not invent commands.\n"
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md',
                                      delete=False, encoding='utf-8') as f:
        f.write(_make_doc_with_markers(avrae_body=avrae, notes_body=notes))
        path = f.name
    try:
        gen.update_commands_doc(bot, path)
        new = Path(path).read_text(encoding="utf-8")
        # Both Avrae bullets and the Notes section survive verbatim.
        assert "- `!attack <weapon> -t <target>` — Attack." in new
        assert "- `!cast <spell>` — Cast." in new
        assert "Do not invent commands." in new
    finally:
        Path(path).unlink(missing_ok=True)


def test_update_doc_idempotent_second_run_no_change():
    bot = FakeBot([
        FakeCommand(name="play", description="[DM] Open the scene."),
        FakeCommand(name="bindchar", description="Bind."),
    ])
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md',
                                      delete=False, encoding='utf-8') as f:
        f.write(_make_doc_with_markers())
        path = f.name
    try:
        r1 = gen.update_commands_doc(bot, path)
        snap1 = Path(path).read_text(encoding="utf-8")
        r2 = gen.update_commands_doc(bot, path)
        snap2 = Path(path).read_text(encoding="utf-8")
        assert r1["doc_changed"] is True
        assert r2["doc_changed"] is False
        assert snap1 == snap2
    finally:
        Path(path).unlink(missing_ok=True)


def test_update_doc_missing_markers_returns_error_no_write():
    bot = FakeBot([FakeCommand(name="play", description="[DM] Open.")])
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md',
                                      delete=False, encoding='utf-8') as f:
        f.write("# No markers here.\n\nJust prose.\n")
        path = f.name
    try:
        original = Path(path).read_text(encoding="utf-8")
        result = gen.update_commands_doc(bot, path)
        assert result["error"] == "markers_missing"
        assert result["markers_found"] is False
        assert result["doc_changed"] is False
        # File untouched
        assert Path(path).read_text(encoding="utf-8") == original
    finally:
        Path(path).unlink(missing_ok=True)


def test_update_doc_missing_file_returns_error_no_crash():
    bot = FakeBot([FakeCommand(name="play", description="[DM] Open.")])
    result = gen.update_commands_doc(bot, "/tmp/definitely-not-here-xyz.md")
    assert result["error"].startswith("file_not_found")
    assert result["doc_changed"] is False


def test_update_doc_no_commands_writes_placeholder():
    bot = FakeBot([])
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md',
                                      delete=False, encoding='utf-8') as f:
        f.write(_make_doc_with_markers())
        path = f.name
    try:
        result = gen.update_commands_doc(bot, path)
        assert result["error"] is None
        assert result["commands_count"] == 0
        new = Path(path).read_text(encoding="utf-8")
        assert "No Virgil slash commands registered" in new
    finally:
        Path(path).unlink(missing_ok=True)


def test_update_doc_atomic_via_tmp_replace():
    # If write fails partway, original file should remain (tmp+replace).
    # We approximate by patching Path.replace to raise after tmp is created;
    # final file content stays equal to the original.
    bot = FakeBot([FakeCommand(name="play", description="[DM] Open.")])
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md',
                                      delete=False, encoding='utf-8') as f:
        f.write(_make_doc_with_markers())
        path = f.name
    try:
        original = Path(path).read_text(encoding="utf-8")
        with mock.patch.object(Path, 'replace',
                                side_effect=PermissionError("nope")):
            result = gen.update_commands_doc(bot, path)
        assert result["error"].startswith("write_error")
        # Original file untouched (replace never happened)
        assert Path(path).read_text(encoding="utf-8") == original
    finally:
        Path(path).unlink(missing_ok=True)


def test_update_doc_real_avrae_section_preserved_through_replacement():
    # Regression guard: the marker regex must be non-greedy so the Avrae
    # section between two `<!--`-prefixed marker pairs (if anyone ever
    # adds another comment-block convention) doesn't get accidentally
    # swallowed.
    bot = FakeBot([FakeCommand(name="play", description="[DM] Open.")])
    avrae = (
        "## Avrae Commands\n\n"
        "<!-- some operator note that LOOKS like a marker -->\n"
        "- `!attack` — attack.\n"
    )
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md',
                                      delete=False, encoding='utf-8') as f:
        f.write(_make_doc_with_markers(avrae_body=avrae))
        path = f.name
    try:
        gen.update_commands_doc(bot, path)
        new = Path(path).read_text(encoding="utf-8")
        assert "operator note that LOOKS like a marker" in new
        assert "- `!attack` — attack." in new
    finally:
        Path(path).unlink(missing_ok=True)


# ─── Run ─────────────────────────────────────────────────────────────

if __name__ == '__main__':
    failures = []
    funcs = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for fn in funcs:
        try:
            fn()
            print(f"  ok   {fn.__name__}")
        except AssertionError as e:
            failures.append((fn.__name__, str(e)))
            print(f"  FAIL {fn.__name__}: {e}")
        except Exception as e:
            failures.append((fn.__name__, repr(e)))
            print(f"  ERR  {fn.__name__}: {e!r}")
    if failures:
        print(f"\n{len(failures)} failure(s)")
        sys.exit(1)
    print(f"\n{len(funcs)} tests passed.")
