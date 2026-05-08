"""Content contracts for /play first-session hint (Track 6 #4 / S23 #4).

The first-session hint is appended to the opening embed body when /play
runs on a campaign whose `dnd_scene_state` row hasn't been initialized
yet. Detection logic lives inline in the /play command (a single bool
captured before init_scene_state replaces the row), so the load-bearing
test surface here is the hint's CONTENT — three commands, in order,
matching what the site's "first night" section will list once Jordan
re-syncs the Artifact source.

Run:
    cd /home/jordaneal/scripts && python3 test_play_first_session.py
"""

import sys

sys.path.insert(0, '/home/jordaneal/scripts')

import discord_dnd_bot as bot


# ─── Hint constant exists and is a string ───────────────────────────

def test_hint_constant_exists():
    assert hasattr(bot, 'PLAY_FIRST_SESSION_HINT')
    assert isinstance(bot.PLAY_FIRST_SESSION_HINT, str)
    assert len(bot.PLAY_FIRST_SESSION_HINT.strip()) > 0


# ─── Three commands, in correct order, with correct text ────────────

def test_hint_lists_three_commands_in_order():
    hint = bot.PLAY_FIRST_SESSION_HINT
    # The three commands appear in the spec'd order
    bind_idx = hint.index('/bindchar')
    refresh_idx = hint.index('/refresh')
    narrate_idx = hint.index('#dm-narration')
    assert bind_idx < refresh_idx < narrate_idx, (
        f"expected /bindchar < /refresh < #dm-narration; "
        f"got bind={bind_idx} refresh={refresh_idx} narrate={narrate_idx}"
    )


def test_hint_describes_bindchar_purpose():
    assert 'pick your character' in bot.PLAY_FIRST_SESSION_HINT


def test_hint_describes_refresh_purpose():
    # Phrasing varies but the intent must surface "pull sheet from Avrae"
    assert 'sheet' in bot.PLAY_FIRST_SESSION_HINT
    assert 'Avrae' in bot.PLAY_FIRST_SESSION_HINT


def test_hint_describes_narrate_handoff():
    # The third step is "narrate your action when ready" — exact wording
    # matters less than the intent that players know to type in narration.
    assert 'arrate' in bot.PLAY_FIRST_SESSION_HINT  # narrate / Narrate
    assert '#dm-narration' in bot.PLAY_FIRST_SESSION_HINT


# ─── Header shape — labels the hint as "first time" ─────────────────

def test_hint_header_marks_first_time():
    # "First time here?" is the load-bearing player-facing framing.
    # Future edits can change phrasing but must preserve the "first time"
    # cue so players self-identify.
    assert 'irst time' in bot.PLAY_FIRST_SESSION_HINT  # first time / First time


def test_hint_uses_numbered_list():
    # 1. ... 2. ... 3. — visual cue that these are sequential steps,
    # not options.
    assert '1.' in bot.PLAY_FIRST_SESSION_HINT
    assert '2.' in bot.PLAY_FIRST_SESSION_HINT
    assert '3.' in bot.PLAY_FIRST_SESSION_HINT


# ─── Separator before hint ──────────────────────────────────────────

def test_hint_starts_with_separator():
    # The hint is appended INSIDE the opening embed's description, so it
    # needs visual separation from the narration body. The separator
    # convention (rule line + double-newlines) keeps the opening prose
    # intact and the hint visually distinct.
    head = bot.PLAY_FIRST_SESSION_HINT[:30]
    assert '\n\n' in head, "hint must start with a paragraph break"


# ─── Length budget — fits within Discord embed description ──────────

def test_hint_within_discord_embed_budget():
    # Discord embed description hard-caps at 4096; opening narration
    # often runs 1500-3500 chars. Hint must be small enough to leave
    # room for the narration without truncation in typical cases.
    assert len(bot.PLAY_FIRST_SESSION_HINT) < 500, (
        f"hint is {len(bot.PLAY_FIRST_SESSION_HINT)} chars — keep under "
        f"500 so a 3500-char opening still fits in the 4000-char cap "
        f"used by /play"
    )


# ─── Appending to a sample narration produces well-formed body ──────

def test_hint_concatenates_cleanly_with_narration():
    sample = "The party gathers in the tavern."
    body = sample + bot.PLAY_FIRST_SESSION_HINT
    # The narration is preserved unchanged at the start
    assert body.startswith(sample)
    # Visual separator follows the narration before the hint
    assert sample + '\n\n' in body or sample in body[: len(sample) + 5]
    # Three commands all present
    assert '/bindchar' in body
    assert '/refresh' in body
    assert '#dm-narration' in body


# ─── Run ────────────────────────────────────────────────────────────

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
