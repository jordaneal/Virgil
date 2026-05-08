"""Tests for SRD suggestion hook — Track 6 #5.1.

Hook integration tests: mock resolver, mock Discord.
Tests 20–25 of 30 total per spec §9.

Functions under test: _handle_new_npc_for_srd_suggestion and
_post_srd_suggestion in discord_dnd_bot.py.

All Discord I/O is via AsyncMock; srd_resolver.resolve is patched.
No DB, no Discord connection, no real network calls.
"""

import asyncio
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.dirname(__file__))

import srd_resolver
import discord_dnd_bot

_handle = discord_dnd_bot._handle_new_npc_for_srd_suggestion
_post   = discord_dnd_bot._post_srd_suggestion


# ─────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────

def _make_result(**kwargs) -> srd_resolver.SRDResult:
    """Build a minimal SRDResult. Keyword overrides accepted."""
    defaults = dict(
        input_name="Goblin",
        srd_name="Goblin",
        cr="1/4",
        hp=7,
        ac=15,
        confidence=1.0,
        method="exact",
    )
    defaults.update(kwargs)
    return srd_resolver.SRDResult(**defaults)


def _make_aside_channel() -> AsyncMock:
    """Return an AsyncMock channel whose .send() is awaitable."""
    ch = AsyncMock()
    ch.name = "dm-aside"
    return ch


def _make_guild(aside_channel) -> MagicMock:
    """Return a MagicMock guild. discord.utils.get is patched by each test."""
    return MagicMock()


# ─────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────

class TestHookNoModeGate(unittest.TestCase):
    """Test 20: hook fires regardless of scene mode (§11.H locked)."""

    def test_20_hook_fires_exploration_mode(self):
        """20. mode='exploration' does NOT block the hook — no mode gate exists.

        The hook is invoked with campaign_id=1 and npc_name="Goblin".
        We verify the resolver is called and the post fires, proving no
        scene-mode check silently short-circuits the path (§11.H: no mode
        gate, locked).
        """
        aside = _make_aside_channel()
        guild = _make_guild(aside)
        result = _make_result(input_name="Goblin", srd_name="Goblin")

        with patch.object(srd_resolver, "resolve", return_value=result) as mock_resolve:
            with patch("discord.utils.get", return_value=aside):
                asyncio.run(_handle(campaign_id=1, npc_name="Goblin", guild=guild))

        # Resolver was called — mode gate would have prevented this
        mock_resolve.assert_called_once_with("Goblin", 1)
        # Suggestion was posted — no gate blocked the send
        aside.send.assert_called_once()


class TestHookPostPath(unittest.TestCase):
    """Tests 21–22: hit path (result → post) and miss path (None → no post)."""

    def test_21_resolver_hit_posts_suggestion(self):
        """21. Resolver returns SRDResult → _post_srd_suggestion called (channel.send fires)."""
        aside = _make_aside_channel()
        guild = _make_guild(aside)
        result = _make_result()

        with patch.object(srd_resolver, "resolve", return_value=result):
            with patch("discord.utils.get", return_value=aside):
                asyncio.run(_handle(1, "Goblin", guild))

        aside.send.assert_called_once()

    def test_22_resolver_miss_no_post(self):
        """22. Resolver returns None → _post_srd_suggestion NOT called (channel.send silent)."""
        aside = _make_aside_channel()
        guild = _make_guild(aside)

        with patch.object(srd_resolver, "resolve", return_value=None):
            with patch("discord.utils.get", return_value=aside):
                asyncio.run(_handle(1, "XyzPlorp", guild))

        aside.send.assert_not_called()


class TestHookSoftFail(unittest.TestCase):
    """Tests 23–24: soft-fail — hook swallows exceptions, never crashes caller."""

    def test_23_no_aside_channel_no_crash(self):
        """23. #dm-aside not found → hook completes without raising or posting.

        discord.utils.get returns None; the if-dm_aside guard is False;
        _post_srd_suggestion is never called.  Function must not raise.
        """
        aside = _make_aside_channel()
        guild = _make_guild(aside)
        result = _make_result()

        with patch.object(srd_resolver, "resolve", return_value=result):
            with patch("discord.utils.get", return_value=None):
                try:
                    asyncio.run(_handle(1, "Goblin", guild))
                except Exception as exc:
                    self.fail(f"Hook raised unexpectedly when channel missing: {exc!r}")

        # No channel found → no send
        aside.send.assert_not_called()

    def test_24_resolver_exception_swallowed(self):
        """24. Exception in srd_resolver.resolve → hook logs error, returns without crashing.

        The outer try/except in _handle_new_npc_for_srd_suggestion must catch
        any exception from the resolver and log it without propagating.
        """
        aside = _make_aside_channel()
        guild = _make_guild(aside)

        with patch.object(srd_resolver, "resolve", side_effect=RuntimeError("network timeout")):
            with patch("discord.utils.get", return_value=aside):
                try:
                    asyncio.run(_handle(1, "Goblin", guild))
                except Exception as exc:
                    self.fail(f"Hook propagated resolver exception: {exc!r}")

        # Exception swallowed before reaching channel.send
        aside.send.assert_not_called()


class TestSuggestionMessageContent(unittest.TestCase):
    """Test 25: message body contains all required elements per spec §5."""

    def test_25_message_contains_required_elements(self):
        """25. Suggestion message contains input name, SRD name, CR, HP, AC,
        !init madd command, and !init add fallback mention.

        Uses a distinct input_name ("Spiny Toad") to verify the input name
        is embedded separately from the SRD name ("Giant Frog").
        """
        aside = _make_aside_channel()
        guild = _make_guild(aside)

        result = _make_result(
            input_name="Spiny Toad",
            srd_name="Giant Frog",
            cr="1/4",
            hp=18,
            ac=11,
            confidence=0.82,
            method="llm",
        )

        with patch.object(srd_resolver, "resolve", return_value=result):
            with patch("discord.utils.get", return_value=aside):
                asyncio.run(_handle(1, "Spiny Toad", guild))

        aside.send.assert_called_once()
        body = aside.send.call_args[0][0]

        self.assertIn("Spiny Toad", body,   "input_name missing from suggestion body")
        self.assertIn("Giant Frog", body,   "srd_name missing from suggestion body")
        self.assertIn("CR 1/4",     body,   "CR missing from suggestion body")
        self.assertIn("HP 18",      body,   "HP missing from suggestion body")
        self.assertIn("AC 11",      body,   "AC missing from suggestion body")
        self.assertIn("!init madd", body,   "!init madd command missing from suggestion body")
        self.assertIn("!init add",  body,   "!init add fallback missing from suggestion body")


if __name__ == "__main__":
    unittest.main()
