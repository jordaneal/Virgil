"""
test_arbitration.py — Track 7 #2 engine layer tests (§8.1).

Tests arbitrate() and ArbitrationResult without live DB or LLM calls.
All adjudicate() calls are mocked to return controlled AdjudicationResult
fixtures. Tests verify:

  - Single-actor degenerate produces byte-identical combined_constraint to
    the Track 7 #1 baseline (regression).
  - Priority sort, merge_plan, overridden_actors for 2- and 3-actor cases.
  - All-pairs (NOT adjacent-only) override semantics per §11.R.
  - actor_order contains CHARACTER NAMES not Discord usernames (§11.Q).
  - Feature flag ARBITRATION_ENABLED=False degrades to first-actor-only.
"""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(__file__))

import adjudicator
from adjudicator import (
    AdjudicationResult, ArbitrationResult, arbitrate,
    FREE_ACTION, CHECK_ACTION, CAPABILITY_ACTION, COMBAT_ACTION,
    WORLD_BOUNDARY_ACTION, FALLBACK,
    REFUSAL_CAPABILITY, REFUSAL_COMBAT_INACTIVE,
    render_adjudication_block,
)


# ─────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────

def _free_verdict(actor='actor') -> AdjudicationResult:
    return AdjudicationResult(
        category=FREE_ACTION,
        allowed=True,
        narration_constraint='',
        signals={'category': FREE_ACTION, 'allowed': 1},
    )


def _check_success_verdict(skill='stealth', dc=15, roll=18) -> AdjudicationResult:
    from adjudicator import _constraint_check_resolved
    constraint = _constraint_check_resolved(skill, dc, 'medium', roll, True)
    return AdjudicationResult(
        category=CHECK_ACTION,
        allowed=True,
        skill=skill,
        dc=dc,
        dc_band='medium',
        roll_consumed=True,
        roll_value=roll,
        success=True,
        narration_constraint=constraint,
        signals={'category': CHECK_ACTION, 'allowed': 1, 'success': 1},
    )


def _check_fail_verdict(skill='persuasion', dc=15, roll=8) -> AdjudicationResult:
    from adjudicator import _constraint_check_resolved, REFUSAL_CHECK_FAILED
    constraint = _constraint_check_resolved(skill, dc, 'medium', roll, False)
    return AdjudicationResult(
        category=CHECK_ACTION,
        allowed=False,
        refusal_kind=REFUSAL_CHECK_FAILED,
        skill=skill,
        dc=dc,
        dc_band='medium',
        roll_consumed=True,
        roll_value=roll,
        success=False,
        narration_constraint=constraint,
        signals={'category': CHECK_ACTION, 'allowed': 0, 'success': 0},
    )


def _capability_refused_verdict() -> AdjudicationResult:
    from adjudicator import _constraint_capability_refused
    constraint = _constraint_capability_refused('spell', 'fireball', None,
                                                 'class=rogue is not a caster class')
    return AdjudicationResult(
        category=CAPABILITY_ACTION,
        allowed=False,
        refusal_kind=REFUSAL_CAPABILITY,
        narration_constraint=constraint,
        signals={'category': CAPABILITY_ACTION, 'allowed': 0,
                 'refusal_kind': REFUSAL_CAPABILITY},
    )


def _combat_refused_verdict() -> AdjudicationResult:
    from adjudicator import _constraint_combat_inactive
    return AdjudicationResult(
        category=COMBAT_ACTION,
        allowed=False,
        refusal_kind=REFUSAL_COMBAT_INACTIVE,
        narration_constraint=_constraint_combat_inactive('attack'),
        signals={'category': COMBAT_ACTION, 'allowed': 0,
                 'refusal_kind': REFUSAL_COMBAT_INACTIVE},
    )


def _world_boundary_verdict() -> AdjudicationResult:
    from adjudicator import _constraint_world_boundary
    return AdjudicationResult(
        category=WORLD_BOUNDARY_ACTION,
        allowed=False,
        refusal_kind='world_boundary',
        narration_constraint=_constraint_world_boundary('become a god'),
        signals={'category': WORLD_BOUNDARY_ACTION, 'allowed': 0},
    )


def _make_cache(ctx_map: dict):
    """Return a character_cache callable from a {name: ctx} dict."""
    def _cache(name):
        return ctx_map.get(name)
    return _cache


def _mock_char_ctx(name: str, char_class: str = 'rogue', level: int = 5):
    ctx = MagicMock()
    ctx.name = name
    ctx.char_class = char_class
    ctx.level = level
    ctx.narrative_tags = set()
    ctx.attacks = []
    return ctx


# ─────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────

class TestArbitrateSingleActor(unittest.TestCase):
    """1-actor degenerate case (§8.1)."""

    def setUp(self):
        adjudicator.ARBITRATION_ENABLED = True

    def test_single_actor_result_length(self):
        """1 actor → ArbitrationResult.verdicts has length 1."""
        ctx = _mock_char_ctx('Donovan')
        verdict = _check_success_verdict()
        with patch('adjudicator.adjudicate', return_value=verdict):
            result = arbitrate(
                actions=[('Donovan', 'I sneak past the guard')],
                character_cache=_make_cache({'Donovan': ctx}),
            )
        self.assertEqual(len(result.verdicts), 1)
        self.assertEqual(result.primary_actor, 'Donovan')

    def test_single_actor_actor_order_is_character_name(self):
        """actor_order stores CHARACTER NAME not Discord username (§11.Q)."""
        ctx = _mock_char_ctx('Donovan')
        verdict = _check_success_verdict()
        with patch('adjudicator.adjudicate', return_value=verdict):
            result = arbitrate(
                actions=[('Donovan', 'I sneak past')],
                character_cache=_make_cache({'Donovan': ctx}),
            )
        self.assertEqual(result.actor_order, ['Donovan'])

    def test_single_actor_constraint_byte_identical_to_track7_1(self):
        """Single-actor combined_constraint is byte-identical to the
        Track 7 #1 baseline (render_adjudication_block output)."""
        ctx = _mock_char_ctx('Donovan')
        verdict = _check_success_verdict('stealth', 15, 18)
        with patch('adjudicator.adjudicate', return_value=verdict):
            result = arbitrate(
                actions=[('Donovan', 'I sneak')],
                character_cache=_make_cache({'Donovan': ctx}),
            )
        # Track 7 #1 baseline
        baseline = render_adjudication_block(verdict)
        self.assertEqual(result.combined_constraint, baseline)

    def test_single_actor_merge_plan_sequence(self):
        ctx = _mock_char_ctx('Donovan')
        verdict = _check_success_verdict()
        with patch('adjudicator.adjudicate', return_value=verdict):
            result = arbitrate(
                actions=[('Donovan', 'sneak')],
                character_cache=_make_cache({'Donovan': ctx}),
            )
        self.assertEqual(result.merge_plan, 'sequence')
        self.assertEqual(result.overridden_actors, [])


class TestArbitrateMultiActor(unittest.TestCase):
    """2-actor non-contradictory case (§8.1)."""

    def setUp(self):
        adjudicator.ARBITRATION_ENABLED = True

    def _two_actor_result(self, verdict_a, verdict_b):
        ctx_a = _mock_char_ctx('Donovan')
        ctx_b = _mock_char_ctx('Bruce')

        def _adjudicate_side(player_input, **kwargs):
            char = kwargs.get('character')
            if char and char.name == 'Donovan':
                return verdict_a
            return verdict_b

        with patch('adjudicator.adjudicate', side_effect=_adjudicate_side):
            return arbitrate(
                actions=[('Donovan', 'I sneak'), ('Bruce', 'I attack')],
                character_cache=_make_cache({'Donovan': ctx_a, 'Bruce': ctx_b}),
            )

    def test_two_actors_non_contradictory_length(self):
        """2 actors non-contradictory → verdicts length 2, sequence."""
        result = self._two_actor_result(
            _check_success_verdict('stealth', 15, 18),
            _free_verdict(),
        )
        self.assertEqual(len(result.verdicts), 2)
        self.assertEqual(result.merge_plan, 'sequence')
        self.assertEqual(result.overridden_actors, [])

    def test_two_actors_actor_order_character_names(self):
        """Multi-actor turn: actor_order == ['Donovan', 'Bruce'] (per §11.Q)."""
        result = self._two_actor_result(
            _check_success_verdict(),
            _free_verdict(),
        )
        # CHECK outranks FREE → Donovan first (regardless of arrival order)
        self.assertEqual(result.actor_order[0], 'Donovan')
        self.assertIn('Bruce', result.actor_order)

    def test_cross_player_override_check_fail_vs_free(self):
        """A=CHECK fail, B=FREE 'he agrees with us' → override, B overridden."""
        ctx_a = _mock_char_ctx('Donovan')
        ctx_b = _mock_char_ctx('Bruce')
        verdict_a = _check_fail_verdict('persuasion', 15, 8)
        verdict_b = _free_verdict()

        def _adj(player_input, **kwargs):
            char = kwargs.get('character')
            return verdict_a if (char and char.name == 'Donovan') else verdict_b

        with patch('adjudicator.adjudicate', side_effect=_adj):
            result = arbitrate(
                # Bruce's text uses "agrees" → triggers _FREE_ASSERTS_SUCCESS_AGAINST_FAIL
                actions=[('Donovan', 'I try to persuade him'),
                         ('Bruce', 'he agrees with us')],
                character_cache=_make_cache({'Donovan': ctx_a, 'Bruce': ctx_b}),
            )

        self.assertEqual(result.merge_plan, 'override')
        self.assertIn('Bruce', result.overridden_actors)

    def test_cross_player_override_capability_refused_vs_free(self):
        """A=CAPABILITY refused, B=FREE 'the room ignites' → override."""
        ctx_a = _mock_char_ctx('Donovan')
        ctx_b = _mock_char_ctx('Bruce')
        verdict_a = _capability_refused_verdict()
        verdict_b = _free_verdict()

        def _adj(player_input, **kwargs):
            char = kwargs.get('character')
            return verdict_a if (char and char.name == 'Donovan') else verdict_b

        with patch('adjudicator.adjudicate', side_effect=_adj):
            result = arbitrate(
                # Bruce's text uses "ignites" → triggers _FREE_ASSERTS_CAPABILITY_WORKED
                actions=[('Donovan', 'cast fireball'),
                         ('Bruce', 'the room ignites')],
                character_cache=_make_cache({'Donovan': ctx_a, 'Bruce': ctx_b}),
            )

        self.assertEqual(result.merge_plan, 'override')
        self.assertIn('Bruce', result.overridden_actors)

    def test_cross_player_no_override_help_action(self):
        """A=CHECK success, B=FREE 'I help him' → no conflict, sequence."""
        ctx_a = _mock_char_ctx('Donovan')
        ctx_b = _mock_char_ctx('Bruce')
        verdict_a = _check_success_verdict('athletics', 12, 16)
        verdict_b = _free_verdict()

        def _adj(player_input, **kwargs):
            char = kwargs.get('character')
            return verdict_a if (char and char.name == 'Donovan') else verdict_b

        with patch('adjudicator.adjudicate', side_effect=_adj):
            result = arbitrate(
                actions=[('Donovan', 'I lift it'), ('Bruce', 'I help him')],
                character_cache=_make_cache({'Donovan': ctx_a, 'Bruce': ctx_b}),
            )

        self.assertEqual(result.merge_plan, 'sequence')
        self.assertEqual(result.overridden_actors, [])


class TestArbitratePrioritySort(unittest.TestCase):
    """Priority sort and tiebreak (§8.1)."""

    def setUp(self):
        adjudicator.ARBITRATION_ENABLED = True

    def test_three_actors_mixed_categories_priority_order(self):
        """3 actors mixed categories → WORLD_BOUNDARY first, FREE last."""
        ctx_a = _mock_char_ctx('Donovan')
        ctx_b = _mock_char_ctx('Bruce')
        ctx_c = _mock_char_ctx('Wren')
        verdict_a = _free_verdict()
        verdict_b = _world_boundary_verdict()
        verdict_c = _check_success_verdict()

        def _adj(player_input, **kwargs):
            char = kwargs.get('character')
            if char and char.name == 'Donovan':
                return verdict_a
            if char and char.name == 'Bruce':
                return verdict_b
            return verdict_c

        with patch('adjudicator.adjudicate', side_effect=_adj):
            result = arbitrate(
                actions=[('Donovan', 'say hi'), ('Bruce', 'become god'), ('Wren', 'sneak')],
                character_cache=_make_cache(
                    {'Donovan': ctx_a, 'Bruce': ctx_b, 'Wren': ctx_c}
                ),
            )

        # Bruce (WORLD_BOUNDARY=5) > Wren (CHECK=2) > Donovan (FREE=1)
        self.assertEqual(result.actor_order[0], 'Bruce')
        self.assertEqual(result.actor_order[-1], 'Donovan')

    def test_same_category_arrival_tiebreak(self):
        """Same category → earlier arrival wins (lower arrival index)."""
        ctx_a = _mock_char_ctx('Donovan')
        ctx_b = _mock_char_ctx('Bruce')
        verdict_a = _check_success_verdict()
        verdict_b = _check_success_verdict()

        def _adj(player_input, **kwargs):
            char = kwargs.get('character')
            return verdict_a if (char and char.name == 'Donovan') else verdict_b

        with patch('adjudicator.adjudicate', side_effect=_adj):
            result = arbitrate(
                # Donovan arrives first (index 0), Bruce second (index 1)
                actions=[('Donovan', 'sneak'), ('Bruce', 'sneak too')],
                character_cache=_make_cache({'Donovan': ctx_a, 'Bruce': ctx_b}),
            )

        # Both CHECK — Donovan arrives first → Donovan leads
        self.assertEqual(result.actor_order[0], 'Donovan')


class TestArbitrateAllPairsOverride(unittest.TestCase):
    """3+-actor all-pairs override (§11.R, §8.1)."""

    def setUp(self):
        adjudicator.ARBITRATION_ENABLED = True

    def _three_actor_result_with_texts(self, vdict, text_map):
        """Build a 3-actor ArbitrationResult with explicit per-actor texts."""
        ctxs = {n: _mock_char_ctx(n) for n in vdict}

        def _adj(player_input, **kwargs):
            char = kwargs.get('character')
            if char and char.name in vdict:
                return vdict[char.name]
            return _free_verdict()

        actions = [(n, text_map.get(n, f"neutral action by {n}"))
                   for n in vdict]
        with patch('adjudicator.adjudicate', side_effect=_adj):
            return arbitrate(
                actions=actions,
                character_cache=_make_cache(ctxs),
            )

    def test_3actor_dual_override(self):
        """A=CHECK fail, B=FREE 'he agrees' contradicts, C=FREE 'she agrees'
        contradicts → overridden_actors=['B','C'] (all-pairs detects both)."""
        result = self._three_actor_result_with_texts(
            vdict={
                'A': _check_fail_verdict('persuasion', 15, 8),
                'B': _free_verdict(),
                'C': _free_verdict(),
            },
            text_map={
                'A': 'I try to persuade him',
                'B': 'he agrees with us',   # asserts persuasion succeeded
                'C': 'she agrees too',       # also asserts persuasion succeeded
            },
        )
        self.assertEqual(result.merge_plan, 'override')
        self.assertIn('B', result.overridden_actors)
        self.assertIn('C', result.overridden_actors)

    def test_3actor_non_adjacent_override(self):
        """A=CAPABILITY refused, B=CHECK (non-FREE), C=FREE 'the room ignites'.
        All-pairs: A-vs-B (non-contradictory — B is non-FREE), A-vs-C (contradicts).
        → overridden_actors=['C'] (B not overridden)."""
        result = self._three_actor_result_with_texts(
            vdict={
                'A': _capability_refused_verdict(),
                'B': _check_success_verdict(),   # non-FREE → never contradicts
                'C': _free_verdict(),             # FREE asserting capability worked
            },
            text_map={
                'A': 'cast fireball',
                'B': 'I sneak',             # non-FREE action, no social claim
                'C': 'the room ignites',    # asserts capability worked
            },
        )
        self.assertEqual(result.merge_plan, 'override')
        self.assertIn('C', result.overridden_actors)
        self.assertNotIn('B', result.overridden_actors)

    def test_3actor_no_contradictions_sequence(self):
        """3 actors with no contradicting FREE text → merge_plan='sequence'."""
        result = self._three_actor_result_with_texts(
            vdict={
                'A': _check_success_verdict(),
                'B': _check_success_verdict(),
                'C': _capability_refused_verdict(),
            },
            text_map={
                'A': 'I sneak',
                'B': 'I also sneak',
                'C': 'cast fireball',
            },
        )
        # All non-FREE, none contradicts any other → sequence
        self.assertEqual(result.merge_plan, 'sequence')
        self.assertEqual(result.overridden_actors, [])

    def test_3actor_capability_both_B_and_C_contradict(self):
        """A=CAPABILITY refused, B=FREE 'room ignites', C=FREE 'the spell works'
        → both B and C in overridden_actors."""
        result = self._three_actor_result_with_texts(
            vdict={
                'A': _capability_refused_verdict(),
                'B': _free_verdict(),
                'C': _free_verdict(),
            },
            text_map={
                'A': 'cast fireball',
                'B': 'the room ignites',      # asserts capability worked
                'C': 'the fireball erupts',   # also asserts capability worked
            },
        )
        self.assertEqual(result.merge_plan, 'override')
        self.assertIn('B', result.overridden_actors)
        self.assertIn('C', result.overridden_actors)


class TestArbitrateFeatureFlag(unittest.TestCase):
    """ARBITRATION_ENABLED=False degrades to first-actor-only (§1.9)."""

    def test_flag_off_single_actor_behavior(self):
        adjudicator.ARBITRATION_ENABLED = False
        try:
            ctx = _mock_char_ctx('Donovan')
            verdict = _check_success_verdict()
            with patch('adjudicator.adjudicate', return_value=verdict):
                result = arbitrate(
                    actions=[('Donovan', 'sneak'), ('Bruce', 'attack')],
                    character_cache=_make_cache({'Donovan': ctx}),
                )
            # Should only process first actor when flag is off
            self.assertEqual(len(result.verdicts), 1)
        finally:
            adjudicator.ARBITRATION_ENABLED = True

    def test_flag_on_processes_all_actors(self):
        adjudicator.ARBITRATION_ENABLED = True
        ctx_a = _mock_char_ctx('Donovan')
        ctx_b = _mock_char_ctx('Bruce')
        verdict = _free_verdict()
        with patch('adjudicator.adjudicate', return_value=verdict):
            result = arbitrate(
                actions=[('Donovan', 'sneak'), ('Bruce', 'attack')],
                character_cache=_make_cache({'Donovan': ctx_a, 'Bruce': ctx_b}),
            )
        self.assertEqual(len(result.verdicts), 2)


class TestArbitrateCacheMiss(unittest.TestCase):
    """Cache-miss actor gets no_character_context per §11.P."""

    def setUp(self):
        adjudicator.ARBITRATION_ENABLED = True

    def test_cache_miss_actor_gets_free_no_context(self):
        ctx_a = _mock_char_ctx('Donovan')
        # Bruce has no cache entry → cache miss
        verdict_a = _check_success_verdict()
        with patch('adjudicator.adjudicate', return_value=verdict_a):
            result = arbitrate(
                actions=[('Donovan', 'sneak'), ('Bruce', 'attack')],
                character_cache=_make_cache({'Donovan': ctx_a}),  # Bruce missing
            )
        # Both actors should appear in actor_order
        self.assertIn('Donovan', result.actor_order)
        self.assertIn('Bruce', result.actor_order)
        # Bruce's verdict should be FREE with no_character_context
        bruce_idx = result.actor_order.index('Bruce')
        bruce_verdict = result.verdicts[bruce_idx]
        self.assertEqual(bruce_verdict.refusal_kind, 'no_character_context')
        self.assertEqual(bruce_verdict.category, FREE_ACTION)


class TestArbitrateTelemetry(unittest.TestCase):
    """signals shape and log line (§11.E)."""

    def setUp(self):
        adjudicator.ARBITRATION_ENABLED = True

    def test_signals_actors_count(self):
        ctx_a = _mock_char_ctx('Donovan')
        ctx_b = _mock_char_ctx('Bruce')
        verdict = _free_verdict()
        with patch('adjudicator.adjudicate', return_value=verdict):
            result = arbitrate(
                actions=[('Donovan', 'hi'), ('Bruce', 'hello')],
                character_cache=_make_cache({'Donovan': ctx_a, 'Bruce': ctx_b}),
            )
        self.assertEqual(result.signals['actors'], 2)

    def test_signals_priority_order_matches_actor_order(self):
        ctx_a = _mock_char_ctx('Donovan')
        ctx_b = _mock_char_ctx('Bruce')
        verdict_a = _check_success_verdict()
        verdict_b = _free_verdict()

        def _adj(player_input, **kwargs):
            char = kwargs.get('character')
            return verdict_a if (char and char.name == 'Donovan') else verdict_b

        with patch('adjudicator.adjudicate', side_effect=_adj):
            result = arbitrate(
                actions=[('Bruce', 'free action'), ('Donovan', 'sneak')],
                character_cache=_make_cache({'Donovan': ctx_a, 'Bruce': ctx_b}),
            )
        # priority_order signal should match actor_order
        order_from_signals = result.signals['priority_order'].split(',')
        self.assertEqual(order_from_signals, result.actor_order)

    def test_log_line_includes_campaign(self):
        from adjudicator import arbitration_log_summary, ArbitrationResult
        r = ArbitrationResult(
            verdicts=[_free_verdict()],
            actor_order=['Donovan'],
            merge_plan='sequence',
            primary_actor='Donovan',
            signals={'actors': 1, 'verdicts': 'free', 'merge_plan': 'sequence',
                     'primary_actor': 'Donovan', 'overridden_actors': '-',
                     'priority_order': 'Donovan', 'input_total_chars': 5,
                     'input_per_actor': 'Donovan:5'},
        )
        line = arbitration_log_summary(r, campaign_id=42)
        self.assertIn('campaign=42', line)
        self.assertIn('actors=1', line)
        self.assertIn('merge_plan=sequence', line)


if __name__ == '__main__':
    unittest.main()
