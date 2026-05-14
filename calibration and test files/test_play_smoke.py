"""S65 Fix 1 smoke test — /play handler must not NameError.

Verifies F-021 closure: pre-patch, `/play` referenced an undefined `seed`
variable at discord_dnd_bot.py:4870, 4876 (Ship 2 / S39 rename left two
f-string sites unupdated). On invocation the f-string evaluated, raised
NameError, propagated past the discord.HTTPException/asyncio.TimeoutError
catch (which only catches typing-indicator failures), crashed the slash
handler, and the interaction timed out.

Post-patch (S65): the f-string is `f"[Open the scene] {scene or ''}"`.
Calling the /play handler with mocked dependencies must complete without
raising.

Run:
    cd /home/jordaneal/scripts && python3 test_play_smoke.py
"""

import sys
import asyncio
import tempfile
import unittest.mock as mock
from pathlib import Path

sys.path.insert(0, '/home/jordaneal/scripts')


# ── Test fixture setup ───────────────────────────────────────────────

# Point engine + chroma to a tempdir so import doesn't hit /mnt.
_tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_tmp.close()
TEST_DB = Path(_tmp.name)

import dnd_engine  # noqa: E402
dnd_engine.DB_PATH = TEST_DB
dnd_engine.log = lambda m: None
dnd_engine.db_init()

# Pre-populate a campaign + character so the /play guards don't early-return
from dnd_engine import create_campaign, bind_character  # noqa: E402

GUILD = 'test-play-smoke'
TEST_USER_ID = '111000'


def _setup_campaign():
    cid = create_campaign(GUILD, 'PlaySmokeCampaign',
                          creator_user_id=TEST_USER_ID)
    bind_character(cid, TEST_USER_ID, 'TestChar', race='human',
                   char_class='fighter', level=1)
    return cid


def _make_interaction(user_id=TEST_USER_ID, guild_id=GUILD):
    """Mock Discord Interaction surface."""
    interaction = mock.MagicMock()
    interaction.guild_id = guild_id
    interaction.user = mock.MagicMock()
    interaction.user.id = user_id
    # Use AsyncMock so the awaitable response methods don't fail
    interaction.response = mock.MagicMock()
    interaction.response.send_message = mock.AsyncMock()
    interaction.response.defer = mock.AsyncMock()
    interaction.followup = mock.MagicMock()
    interaction.followup.send = mock.AsyncMock()
    # Build a guild that get_channel can index by name
    interaction.guild = mock.MagicMock()
    interaction.guild.id = guild_id
    return interaction


def _run_play_handler(interaction, scene=None):
    """Invoke discord_dnd_bot.play with all expected externals mocked.

    Uses .callback attribute for the bot.tree.command-decorated handler.
    """
    import discord_dnd_bot as bot_mod

    # Discord environment + LLM externals all mocked.
    with mock.patch.object(bot_mod, 'is_dm_or_creator', return_value=True), \
         mock.patch.object(bot_mod, 'get_channel', return_value=mock.MagicMock()), \
         mock.patch.object(bot_mod, 'dm_respond', return_value='Opening narration body.'), \
         mock.patch.object(bot_mod, 'chroma_store'), \
         mock.patch.object(bot_mod, 'update_scene'), \
         mock.patch.object(bot_mod, 'init_scene_state'):
        # Build a narration_ch with an async typing() context + send()
        narration_ch = mock.MagicMock()
        narration_ch.typing = mock.MagicMock()
        narration_ch.typing.return_value.__aenter__ = mock.AsyncMock(return_value=None)
        narration_ch.typing.return_value.__aexit__ = mock.AsyncMock(return_value=None)
        narration_ch.send = mock.AsyncMock()
        narration_ch.mention = '#dm-narration'
        with mock.patch.object(bot_mod, 'get_channel', return_value=narration_ch):
            # The bot.tree.command decorator stores the original function as .callback
            handler = bot_mod.play
            if hasattr(handler, 'callback'):
                handler = handler.callback
            asyncio.run(handler(interaction, scene=scene))


def test_play_no_nameerror_no_scene_arg():
    """/play without scene argument must not raise NameError."""
    _setup_campaign()
    interaction = _make_interaction()
    # Pre-patch this would raise NameError: name 'seed' is not defined.
    # Post-patch it must complete cleanly.
    _run_play_handler(interaction, scene=None)
    # If we reach here, no NameError was raised.


def test_play_no_nameerror_with_scene_arg():
    """/play with explicit scene argument also must not raise NameError."""
    interaction = _make_interaction()
    _run_play_handler(interaction, scene="the party arrives at the haunted mill")


def test_play_handler_calls_dm_respond_with_scene_text():
    """Verify the f-string body now includes the scene argument (or empty)."""
    import discord_dnd_bot as bot_mod
    interaction = _make_interaction()
    captured_action = []

    def _spy_dm_respond(campaign, chars, action, *args, **kwargs):
        captured_action.append(action)
        return 'opening'

    with mock.patch.object(bot_mod, 'is_dm_or_creator', return_value=True), \
         mock.patch.object(bot_mod, 'dm_respond', side_effect=_spy_dm_respond), \
         mock.patch.object(bot_mod, 'chroma_store'), \
         mock.patch.object(bot_mod, 'update_scene'), \
         mock.patch.object(bot_mod, 'init_scene_state'):
        narration_ch = mock.MagicMock()
        narration_ch.typing = mock.MagicMock()
        narration_ch.typing.return_value.__aenter__ = mock.AsyncMock(return_value=None)
        narration_ch.typing.return_value.__aexit__ = mock.AsyncMock(return_value=None)
        narration_ch.send = mock.AsyncMock()
        narration_ch.mention = '#dm-narration'
        with mock.patch.object(bot_mod, 'get_channel', return_value=narration_ch):
            handler = bot_mod.play
            if hasattr(handler, 'callback'):
                handler = handler.callback
            asyncio.run(handler(interaction, scene="haunted mill"))

    assert captured_action, "dm_respond should have been called"
    action = captured_action[0]
    assert '[Open the scene]' in action, f"Expected marker in action, got: {action!r}"
    assert 'haunted mill' in action, f"Expected scene text in action, got: {action!r}"


def test_play_handler_static_no_seed_reference():
    """AST guard: /play function must NOT reference an undefined `seed` name.

    This is the structural regression test against F-021. If a future
    rename leaves another `seed` reference, this fails immediately.
    """
    import ast
    import builtins
    with open('/home/jordaneal/scripts/discord_dnd_bot.py') as f:
        tree = ast.parse(f.read())
    # Locate module-level names
    module_names = set()
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            module_names.add(n.name)
        elif isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name): module_names.add(t.id)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            for alias in n.names:
                module_names.add(alias.asname or alias.name.split('.')[0])
        elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
            module_names.add(n.target.id)
    builtin_names = set(dir(builtins))

    play_fn = next(
        (n for n in tree.body
         if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == 'play'),
        None
    )
    assert play_fn is not None, "/play function not found in discord_dnd_bot.py"

    # Collect locals (params + assignments + for/with/except + nested-fn args + imports)
    local = set()
    for arg in play_fn.args.args + play_fn.args.kwonlyargs + play_fn.args.posonlyargs:
        local.add(arg.arg)
    if play_fn.args.vararg: local.add(play_fn.args.vararg.arg)
    if play_fn.args.kwarg: local.add(play_fn.args.kwarg.arg)
    for sub in ast.walk(play_fn):
        if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            if isinstance(sub, ast.Lambda) or sub is not play_fn:
                if isinstance(sub, ast.Lambda):
                    for arg in sub.args.args + sub.args.kwonlyargs:
                        local.add(arg.arg)
                else:
                    local.add(sub.name)
                    for arg in sub.args.args + sub.args.kwonlyargs + sub.args.posonlyargs:
                        local.add(arg.arg)
        elif isinstance(sub, ast.Assign):
            for t in sub.targets:
                if isinstance(t, ast.Name): local.add(t.id)
                elif isinstance(t, ast.Tuple):
                    for e in t.elts:
                        if isinstance(e, ast.Name): local.add(e.id)
        elif isinstance(sub, ast.AnnAssign) and isinstance(sub.target, ast.Name):
            local.add(sub.target.id)
        elif isinstance(sub, ast.AugAssign) and isinstance(sub.target, ast.Name):
            local.add(sub.target.id)
        elif isinstance(sub, (ast.For, ast.AsyncFor)):
            if isinstance(sub.target, ast.Name): local.add(sub.target.id)
            elif isinstance(sub.target, ast.Tuple):
                for e in sub.target.elts:
                    if isinstance(e, ast.Name): local.add(e.id)
        elif isinstance(sub, (ast.With, ast.AsyncWith)):
            for item in sub.items:
                if item.optional_vars and isinstance(item.optional_vars, ast.Name):
                    local.add(item.optional_vars.id)
        elif isinstance(sub, ast.ExceptHandler) and sub.name:
            local.add(sub.name)
        elif isinstance(sub, (ast.Import, ast.ImportFrom)):
            for alias in sub.names:
                local.add(alias.asname or alias.name.split('.')[0])
        elif isinstance(sub, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            for gen in sub.generators:
                if isinstance(gen.target, ast.Name): local.add(gen.target.id)

    # No Name(Load) reference may resolve to an undefined symbol.
    undefined_loads = []
    for sub in ast.walk(play_fn):
        if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load):
            if sub.id not in local and sub.id not in module_names and sub.id not in builtin_names:
                undefined_loads.append((sub.id, sub.lineno))

    # Specifically `seed` must not be in undefined loads (F-021 closure)
    seed_hits = [(n, ln) for n, ln in undefined_loads if n == 'seed']
    assert not seed_hits, f"F-021 regression: /play references undefined `seed` at {seed_hits}"
    # No other undefined-name issues either
    assert not undefined_loads, f"/play references other undefined names: {undefined_loads}"


def test_play_handler_static_no_brace_seed_in_fstring():
    """Source-level guard: literal `{seed}` must not appear in any f-string
    in discord_dnd_bot.py outside of comments. This catches the exact F-021
    failure shape if a rename ever reintroduces it."""
    with open('/home/jordaneal/scripts/discord_dnd_bot.py') as f:
        lines = f.readlines()
    hits = []
    for i, line in enumerate(lines, 1):
        # Skip pure comment lines
        stripped = line.lstrip()
        if stripped.startswith('#'):
            continue
        # Look for f-string `{seed}` pattern in code regions
        if 'f"' in line or "f'" in line:
            if '{seed}' in line:
                # Confirm it's not inside an inline comment
                code_before_comment = line.split('#', 1)[0]
                if '{seed}' in code_before_comment:
                    hits.append((i, line.strip()))
    assert not hits, f"F-021 regression: undefined `{{seed}}` in f-string at {hits}"


# ── Adversarial: /play twice in quick succession ─────────────────────

def test_play_twice_rapid_no_crash():
    """Adversarial verify per S65 plan: /play twice rapid-fire — no
    duplicate-command crash or race condition.

    The handler is independent per-invocation. Verifies the second
    invocation also completes cleanly with `scene=None`.
    """
    interaction1 = _make_interaction()
    interaction2 = _make_interaction()
    _run_play_handler(interaction1, scene=None)
    _run_play_handler(interaction2, scene=None)


# ── Test driver ─────────────────────────────────────────────────────

def main():
    tests = [
        test_play_no_nameerror_no_scene_arg,
        test_play_no_nameerror_with_scene_arg,
        test_play_handler_calls_dm_respond_with_scene_text,
        test_play_handler_static_no_seed_reference,
        test_play_handler_static_no_brace_seed_in_fstring,
        test_play_twice_rapid_no_crash,
    ]
    fails = []
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except AssertionError as e:
            print(f"FAIL  {t.__name__}: {e}")
            fails.append(t.__name__)
        except Exception as e:
            print(f"ERROR {t.__name__}: {type(e).__name__}: {e}")
            fails.append(t.__name__)
    if fails:
        print(f"\n{len(fails)} test(s) failed: {fails}")
        sys.exit(1)
    print(f"\nAll {len(tests)} tests passed.")


if __name__ == '__main__':
    main()
