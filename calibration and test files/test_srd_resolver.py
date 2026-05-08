"""Tests for srd_resolver.py — Track 6 #5.1.

Pure function tests: no DB, no Discord.
30 tests across three files per spec §9.
This file: 19 tests (index integrity, exact, fuzzy, LLM gate, dedup, logging).
"""

import importlib
import json
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))
import srd_resolver


def _fresh_resolver():
    """Reload srd_resolver to reset module-level state (_SUGGESTED, _LLM_CACHE)."""
    srd_resolver._SUGGESTED.clear()
    srd_resolver._LLM_CACHE.clear()


class TestIndexIntegrity(unittest.TestCase):
    """Tests 1–3: index loaded, spot-check, key format."""

    def test_01_index_nonempty(self):
        """1. _MONSTER_INDEX is non-empty after import (index loaded)."""
        self.assertGreater(len(srd_resolver._MONSTER_INDEX), 0)

    def test_02_giant_frog_fields(self):
        """2. _MONSTER_INDEX["giant frog"] has correct fields."""
        entry = srd_resolver._MONSTER_INDEX.get("giant frog")
        self.assertIsNotNone(entry, "giant frog must be in the index")
        self.assertEqual(entry["name"], "Giant Frog")
        self.assertEqual(entry["cr"], "1/4")
        self.assertEqual(entry["hp"], 18)
        self.assertEqual(entry["ac"], 11)

    def test_03_all_keys_lowercase(self):
        """3. All keys in _MONSTER_INDEX are lowercase."""
        for key in srd_resolver._MONSTER_INDEX:
            self.assertEqual(key, key.lower(), f"Key not lowercase: {key!r}")


class TestExactMatch(unittest.TestCase):
    """Tests 4–6: exact key match."""

    def setUp(self):
        _fresh_resolver()

    def test_04_exact_title_case(self):
        """4. resolve("Giant Frog", 1) → SRDResult(srd_name="Giant Frog", method="exact")."""
        result = srd_resolver.resolve("Giant Frog", 1)
        self.assertIsNotNone(result)
        self.assertEqual(result.srd_name, "Giant Frog")
        self.assertEqual(result.method, "exact")
        self.assertEqual(result.confidence, 1.0)

    def test_05_exact_lowercase_input(self):
        """5. resolve("giant frog", 1) → same result (case-insensitive)."""
        result = srd_resolver.resolve("giant frog", 1)
        self.assertIsNotNone(result)
        self.assertEqual(result.srd_name, "Giant Frog")
        self.assertEqual(result.method, "exact")

    def test_06_exact_uppercase_input(self):
        """6. resolve("GOBLIN", 1) → SRDResult(srd_name="Goblin", method="exact")."""
        result = srd_resolver.resolve("GOBLIN", 1)
        self.assertIsNotNone(result)
        self.assertEqual(result.srd_name, "Goblin")
        self.assertEqual(result.method, "exact")
        self.assertEqual(result.confidence, 1.0)


class TestFuzzyMatch(unittest.TestCase):
    """Tests 7–10: Jaccard token-overlap fuzzy match."""

    def setUp(self):
        _fresh_resolver()

    def test_07_fuzzy_miss_no_overlap(self):
        """7. _fuzzy_match("totally unknown creature xyzzy") → None."""
        result = srd_resolver._fuzzy_match("totally unknown creature xyzzy")
        self.assertIsNone(result)

    def test_08_fuzzy_miss_clear_semantic(self):
        """8. _fuzzy_match("cave toad") → None.

        tokens {"cave","toad"} ∩ {"giant","frog"} = ∅, Jaccard=0.0.
        No SRD entry has overlap above the 0.6 threshold.
        """
        result = srd_resolver._fuzzy_match("cave toad")
        self.assertIsNone(result)

    def test_09_fuzzy_hit_swarm_bats(self):
        """9. _fuzzy_match("swarm bats") → entry for Swarm of Bats at Jaccard≈0.67.

        tokens {"swarm","bats"} ∩ {"swarm","of","bats"} = 2, union=3, J=0.667.
        DM omits "of"; fuzzy match recovers the correct SRD name.
        """
        result = srd_resolver._fuzzy_match("swarm bats")
        self.assertIsNotNone(result, "Expected Swarm of Bats match")
        entry, score = result
        self.assertEqual(entry["name"], "Swarm of Bats")
        self.assertGreaterEqual(score, 0.6)
        self.assertAlmostEqual(score, 2 / 3, places=3)

    def test_10_fuzzy_above_threshold_resolve(self):
        """10. resolve("swarm bats", 2) → SRDResult method=fuzzy."""
        result = srd_resolver.resolve("swarm bats", 2)
        self.assertIsNotNone(result)
        self.assertEqual(result.method, "fuzzy")
        self.assertEqual(result.srd_name, "Swarm of Bats")


class TestLLMGate(unittest.TestCase):
    """Tests 11–14: LLM suggestion + §1b validator gate (mock _llm_suggest)."""

    def setUp(self):
        _fresh_resolver()

    def test_11_llm_hit_validates(self):
        """11. LLM returns ("Giant Frog", 0.82) + index has it → SRDResult method=llm."""
        with patch.object(srd_resolver, "_llm_suggest", return_value=("Giant Frog", 0.82)):
            result = srd_resolver.resolve("Spiny Toad", 1)
        self.assertIsNotNone(result)
        self.assertEqual(result.method, "llm")
        self.assertEqual(result.srd_name, "Giant Frog")
        self.assertAlmostEqual(result.confidence, 0.82, places=3)

    def test_12_llm_hallucinated_name_rejected(self):
        """12. LLM returns ("Phantasmal Wyrm", 0.90) → None (validator gate rejects)."""
        with patch.object(srd_resolver, "_llm_suggest",
                          return_value=("Phantasmal Wyrm", 0.90)):
            result = srd_resolver.resolve("Dragon-like thing", 1)
        self.assertIsNone(result)

    def test_13_llm_low_confidence_rejected(self):
        """13. LLM returns ("Giant Frog", 0.40) → None (below _CONFIDENCE_THRESHOLD)."""
        with patch.object(srd_resolver, "_llm_suggest", return_value=("Giant Frog", 0.40)):
            result = srd_resolver.resolve("Froggy", 1)
        self.assertIsNone(result)

    def test_14_llm_exception_returns_none(self):
        """14. _llm_suggest raises exception → resolve() returns None, no propagation."""
        with patch.object(srd_resolver, "_llm_suggest", side_effect=RuntimeError("network")):
            result = srd_resolver.resolve("Unknownthing", 1)
        self.assertIsNone(result)


class TestSessionDedup(unittest.TestCase):
    """Tests 15–16: _SUGGESTED dedup keyed by (campaign_id, name_lower)."""

    def setUp(self):
        _fresh_resolver()

    def test_15_dedup_same_campaign(self):
        """15. resolve("Giant Frog", 1) first call → result; second → None (dedup)."""
        first = srd_resolver.resolve("Giant Frog", 1)
        self.assertIsNotNone(first)
        second = srd_resolver.resolve("Giant Frog", 1)
        self.assertIsNone(second)

    def test_16_dedup_per_campaign(self):
        """16. Dedup is per-campaign: Goblin deduped in campaign 1, fires in campaign 2."""
        first = srd_resolver.resolve("Goblin", 1)
        self.assertIsNotNone(first)
        deduped = srd_resolver.resolve("Goblin", 1)
        self.assertIsNone(deduped)
        # Different campaign — should fire
        other_campaign = srd_resolver.resolve("Goblin", 2)
        self.assertIsNotNone(other_campaign)


class TestLogging(unittest.TestCase):
    """Tests 17–19: telemetry log lines emitted on all paths."""

    def setUp(self):
        _fresh_resolver()

    def test_17_miss_emits_log(self):
        """17. Miss path emits log line with method=miss posted=0."""
        log_lines = []
        with patch.object(srd_resolver, "log", side_effect=lambda m: log_lines.append(m)):
            with patch.object(srd_resolver, "_llm_suggest", return_value=None):
                result = srd_resolver.resolve("XyzPlorp123", 1)
        self.assertIsNone(result)
        miss_lines = [l for l in log_lines if "method=miss" in l and "posted=0" in l]
        self.assertEqual(len(miss_lines), 1, f"Expected one miss log line, got: {log_lines}")

    def test_18_dedup_emits_log(self):
        """18. Dedup path emits log line with method=dedup posted=0."""
        # First call to set up dedup entry
        srd_resolver.resolve("Goblin", 1)
        log_lines = []
        with patch.object(srd_resolver, "log", side_effect=lambda m: log_lines.append(m)):
            result = srd_resolver.resolve("Goblin", 1)
        self.assertIsNone(result)
        dedup_lines = [l for l in log_lines if "method=dedup" in l and "posted=0" in l]
        self.assertEqual(len(dedup_lines), 1, f"Expected dedup log line, got: {log_lines}")

    def test_19_hit_emits_resolver_log_posted_zero(self):
        """19. Hit path: _build_and_mark emits posted=0; transport log (posted=1)
        is emitted separately by _post_srd_suggestion (two-line shape per §8)."""
        log_lines = []
        with patch.object(srd_resolver, "log", side_effect=lambda m: log_lines.append(m)):
            result = srd_resolver.resolve("Goblin", 1)
        self.assertIsNotNone(result)
        # Resolver emits posted=0
        resolver_lines = [l for l in log_lines
                          if "srd_suggestion:" in l and "posted=0" in l and "method=exact" in l]
        self.assertEqual(len(resolver_lines), 1,
                         f"Expected resolver posted=0 line, got: {log_lines}")
        # No posted=1 from resolver itself
        posted_one = [l for l in log_lines if "posted=1" in l]
        self.assertEqual(len(posted_one), 0,
                         "Resolver must not emit posted=1; that belongs to _post_srd_suggestion")


class TestLLMCacheNoPoisoning(unittest.TestCase):
    """Verify _LLM_CACHE transient-failure fix: exceptions don't poison the cache."""

    def setUp(self):
        _fresh_resolver()

    def test_llm_exception_does_not_cache(self):
        """Transient LLM failure must NOT write None to _LLM_CACHE."""
        key = "transient fail creature"
        with patch("srd_resolver.route", side_effect=RuntimeError("timeout")):
            result = srd_resolver._llm_suggest("Transient Fail Creature")
        self.assertIsNone(result)
        self.assertNotIn(key, srd_resolver._LLM_CACHE,
                         "Transient exception must not poison _LLM_CACHE")

    def test_llm_genuine_nomatch_does_cache(self):
        """Genuine LLM no-match (empty candidate) SHOULD cache to avoid re-asking."""
        key = "xyzplorp beast"
        mock_resp = json.dumps({"candidate": "", "confidence": 0.0})
        with patch("srd_resolver.route", return_value=(mock_resp, "groq")):
            result = srd_resolver._llm_suggest("XyzPlorp Beast")
        self.assertIsNone(result)
        # Key should be cached (as None, the definitive no-match)
        self.assertIn(key, srd_resolver._LLM_CACHE,
                      "Genuine no-match response should be cached to prevent re-asking")


if __name__ == "__main__":
    unittest.main()
