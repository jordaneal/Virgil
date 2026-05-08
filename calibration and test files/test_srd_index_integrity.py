"""Tests for SRD index data quality — Track 6 #5.1.

Data quality tests on srd_monsters.json.
Tests 26–30 of 30 total per spec §9.

No imports beyond stdlib — JSON is loaded directly from disk.
Verifies count, schema, CR vocabulary, and numeric sanity of every entry.
"""

import json
import os
import unittest

_INDEX_PATH = os.path.join(os.path.dirname(__file__), "srd_monsters.json")

# Valid CR strings per 5e SRD vocabulary (0, fractions, and integers 1–30).
_VALID_CRS: frozenset[str] = frozenset(
    {"0", "1/8", "1/4", "1/2"} | {str(n) for n in range(1, 31)}
)


class TestSRDIndexIntegrity(unittest.TestCase):
    """Tests 26–30: data quality of srd_monsters.json."""

    @classmethod
    def setUpClass(cls):
        """Load the JSON once for the entire test class."""
        with open(_INDEX_PATH, encoding="utf-8") as f:
            cls.raw = json.load(f)
        # Exclude _meta attribution key — it is not a monster entry
        cls.entries: dict[str, dict] = {
            k: v for k, v in cls.raw.items() if k != "_meta"
        }

    def test_26_json_valid_and_parseable(self):
        """26. JSON is valid and parseable; root is a dict.

        setUpClass would have raised json.JSONDecodeError if the file
        were malformed, so reaching this test proves parseability.
        """
        self.assertIsInstance(
            self.raw, dict,
            "srd_monsters.json root must be a JSON object (dict)"
        )
        # Sanity: _meta key exists for CC-BY 4.0 attribution
        self.assertIn("_meta", self.raw, "_meta attribution key must be present")

    def test_27_entry_count_at_least_300(self):
        """27. Monster entry count ≥ 300 (5e SRD has ~334 monsters)."""
        count = len(self.entries)
        self.assertGreaterEqual(
            count, 300,
            f"Expected ≥300 monster entries, got {count}"
        )

    def test_28_all_entries_have_required_fields(self):
        """28. Every entry has required fields name (str), cr (str), hp (int), ac (int).

        Uses subTest so all failures are reported, not just the first.
        """
        for key, entry in self.entries.items():
            with self.subTest(key=key):
                for field in ("name", "cr", "hp", "ac"):
                    self.assertIn(field, entry,
                                  f"{key!r}: missing required field {field!r}")

                self.assertIsInstance(entry["name"], str,
                                      f"{key!r}: 'name' must be str, got {type(entry['name']).__name__}")
                self.assertIsInstance(entry["cr"],   str,
                                      f"{key!r}: 'cr' must be str, got {type(entry['cr']).__name__}")
                self.assertIsInstance(entry["hp"],   int,
                                      f"{key!r}: 'hp' must be int, got {type(entry['hp']).__name__}")
                self.assertIsInstance(entry["ac"],   int,
                                      f"{key!r}: 'ac' must be int, got {type(entry['ac']).__name__}")

    def test_29_cr_values_are_valid(self):
        """29. Every CR value is in {"0","1/8","1/4","1/2"} ∪ {str(n) for n in 1..30}.

        Uses subTest so all invalid CRs are reported together.
        """
        for key, entry in self.entries.items():
            with self.subTest(key=key):
                self.assertIn(
                    entry["cr"], _VALID_CRS,
                    f"{key!r}: invalid cr={entry['cr']!r} (not in 5e SRD CR vocabulary)"
                )

    def test_30_hp_and_ac_are_positive_integers(self):
        """30. HP and AC are positive (> 0) integers for every entry.

        Zero HP or AC would indicate a parse error in generate_srd_index.py.
        Uses subTest so all failures are reported together.
        """
        for key, entry in self.entries.items():
            with self.subTest(key=key):
                self.assertGreater(
                    entry["hp"], 0,
                    f"{key!r}: hp must be > 0, got {entry['hp']}"
                )
                self.assertGreater(
                    entry["ac"], 0,
                    f"{key!r}: ac must be > 0, got {entry['ac']}"
                )


if __name__ == "__main__":
    unittest.main()
