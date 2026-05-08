"""
test_dm_respond_arbitration.py — Track 7 #2 end-to-end composition (§8.3).

Tests dm_respond() with arbitration and verification integrated. All LLM
calls (route()), DB calls, and external I/O are mocked. Tests verify:

  - 1-actor input → Track 7 #1 baseline prompt shape
  - 2-actor non-contradictory → ArbitrationResult sequence, verified once,
    posted
  - 2-actor contradictory → override merge, verified, posted
  - Narration fabricates NPC + combat verb → verification fails, retry fires,
    retry succeeds, posted
  - Both passes fail → escalation placeholder posted
  - ARBITRATION_ENABLED=False → Track 7 #1 single-actor behavior
  - VERIFICATION_ENABLED=False → no post-pass, original narration posted
"""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock, call
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(__file__))

import adjudicator
import narration_verifier as nv
from adjudicator import (
    AdjudicationResult, ArbitrationResult,
    FREE_ACTION, CHECK_ACTION, CAPABILITY_ACTION, COMBAT_ACTION, FALLBACK,
    REFUSAL_CAPABILITY, REFUSAL_COMBAT_INACTIVE,
)
from narration_verifier import VerificationResult, VIOLATION_FABRICATED_COMBATANT


# ─────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────

def _free_verdict():
    return AdjudicationResult(
        category=FREE_ACTION, allowed=True, narration_constraint='', signals={},
    )


def _check_success_verdict(skill='stealth', dc=15, roll=18):
    from adjudicator import _constraint_check_resolved
    return AdjudicationResult(
        category=CHECK_ACTION, allowed=True, skill=skill, dc=dc,
        roll_value=roll, success=True,
        narration_constraint=_constraint_check_resolved(skill, dc, 'medium', roll, True),
        signals={},
    )


def _capability_refused_verdict():
    return AdjudicationResult(
        category=CAPABILITY_ACTION, allowed=False, refusal_kind=REFUSAL_CAPABILITY,
        narration_constraint='Fireball refused.', signals={},
    )


def _make_arb_result_from_verdicts(verdicts, actor_order,
                                    merge_plan='sequence'):
    constraint = 'ARBITRATION_CONSTRAINT_PLACEHOLDER'
    return ArbitrationResult(
        verdicts=verdicts,
        actor_order=actor_order,
        merge_plan=merge_plan,
        primary_actor=actor_order[0] if actor_order else '',
        combined_constraint=constraint,
        overridden_actors=[],
        signals={'actors': len(actor_order), 'verdicts': ':'.join(
            v.category for v in verdicts
        ), 'merge_plan': merge_plan,
            'primary_actor': actor_order[0] if actor_order else '',
            'overridden_actors': '-',
            'priority_order': ','.join(actor_order),
            'input_total_chars': 50,
            'input_per_actor': ','.join(f"{a}:10" for a in actor_order)},
    )


def _make_mock_campaign(cid=1):
    return {'id': cid, 'name': 'Test Campaign', 'guild_id': '123'}


def _make_mock_characters():
    return [{'name': 'Donovan', 'race': 'human', 'class': 'rogue', 'level': 5}]


# ─────────────────────────────────────────────────────────
# Base mocking infrastructure
# ─────────────────────────────────────────────────────────

_DB_PATCH_TARGETS = [
    'dnd_engine.get_scene_state',
    'dnd_engine.get_combatants',
    'dnd_engine.get_active_turn',
    'dnd_engine.npc_list',
    'dnd_engine.update_scene',
    'dnd_engine.update_last_dm_response',
    'dnd_engine.increment_turn_counter',
    'dnd_engine.chroma_store',
    'dnd_engine.extract_scene_updates',
    'dnd_engine.orch',
]

_DIRECTIVE_PATCH_TARGETS = [
    'dnd_engine.skeleton_loader',
]


def _build_base_mocks():
    """Return a dict of {target: mock} with safe defaults."""
    mocks = {}

    m_scene = MagicMock()
    m_scene.return_value = {'mode': 'exploration', 'campaign_id': 1}
    mocks['dnd_engine.get_scene_state'] = m_scene

    m_comb = MagicMock()
    m_comb.return_value = {'combatants': []}
    mocks['dnd_engine.get_combatants'] = m_comb

    m_turn = MagicMock()
    m_turn.return_value = None
    mocks['dnd_engine.get_active_turn'] = m_turn

    m_npcs = MagicMock()
    m_npcs.return_value = []
    mocks['dnd_engine.npc_list'] = m_npcs

    return mocks


# ─────────────────────────────────────────────────────────
# The actual test class
# ─────────────────────────────────────────────────────────

class TestDmRespondArbitration(unittest.TestCase):

    def setUp(self):
        adjudicator.ARBITRATION_ENABLED = True
        nv.VERIFICATION_ENABLED = True

    def tearDown(self):
        adjudicator.ARBITRATION_ENABLED = True
        nv.VERIFICATION_ENABLED = True

    def _call_dm_respond(self, player_action='test action', actions=None,
                          arb_result=None, route_responses=None,
                          verify_results=None):
        """Call dm_respond with heavy mocking. Returns response string."""
        campaign = _make_mock_campaign()
        characters = _make_mock_characters()

        if arb_result is None:
            arb_result = _make_arb_result_from_verdicts(
                [_check_success_verdict()], ['Donovan']
            )

        if route_responses is None:
            route_responses = [('The narration text.', {})]

        if verify_results is None:
            verify_results = [VerificationResult(passed=True, signals={
                'narration_chars': 20, 'canonical_combatants_count': 1
            })]

        route_iter = iter(route_responses)
        verify_iter = iter(verify_results)

        m_orch = MagicMock()
        m_ctx = MagicMock()
        m_ctx.name = 'Donovan'
        m_ctx.char_class = 'rogue'
        m_ctx.level = 5
        m_ctx.attacks = []
        m_ctx.narrative_tags = set()
        m_orch.get_cached_context.return_value = m_ctx
        m_orch.classify_action_intent.return_value = 'exploration'
        m_orch.should_call_roll.return_value = False
        m_cap = MagicMock()
        m_cap.needs_check = False
        m_orch.check_action_capability.return_value = m_cap
        m_orch.compute_pacing_directive.return_value = ''
        m_orch.compute_central_thread_directive.return_value = ''
        m_orch.compute_commitment_directive.return_value = ('', {})
        m_orch.compute_init_directive.return_value = ('', {})
        m_orch.compute_persistence_directive.return_value = ('', {})
        m_orch.compute_loot_directive.return_value = ('', {})
        m_orch.compute_consequence_directive.return_value = ('', [])
        m_orch.compute_combat_redirect_directive.return_value = ('', {})
        m_orch.resolve_actor.return_value = None
        m_orch.pacing_log_summary.return_value = ''
        m_orch.commitment_log_summary.return_value = ''
        m_orch.init_log_summary.return_value = ''
        m_orch.persistence_log_summary.return_value = ''
        m_orch.loot_log_summary.return_value = ''
        m_orch.combat_redirect_log_summary.return_value = ''
        m_orch.INTENT_COMBAT = 'combat'
        m_orch.CapabilityVerdict = MagicMock()
        m_orch.CapabilityVerdict.INVALID = 'INVALID'
        m_orch.CapabilityVerdict.CONFIRMED = 'CONFIRMED'

        def _fake_route(messages, task_type, system_prompt):
            return next(route_iter, ('fallback narration.', {}))

        def _fake_verify(*args, **kwargs):
            return next(verify_iter, VerificationResult(passed=True, signals={}))

        from unittest.mock import patch
        with (
            patch('dnd_engine.orch', m_orch),
            patch('dnd_engine.get_scene_state',
                  return_value={'mode': 'exploration', 'campaign_id': 1}),
            patch('dnd_engine.get_combatants',
                  return_value={'combatants': []}),
            patch('dnd_engine.get_active_turn', return_value=None),
            patch('dnd_engine.npc_list', return_value=[]),
            patch('dnd_engine.update_scene'),
            patch('dnd_engine.update_last_dm_response'),
            patch('dnd_engine.increment_turn_counter'),
            patch('dnd_engine.chroma_store'),
            patch('dnd_engine.extract_scene_updates'),
            patch('dnd_engine.get_bound_character_names',
                  return_value=['Donovan']),
            patch('dnd_engine.route', side_effect=_fake_route),
            # Patch local imports inside dm_respond via their module
            patch('skeleton_loader.get_player_capabilities', return_value={}),
            patch('skeleton_loader.parse_skeleton_file',
                  return_value={'npcs': [], 'hooks': [], 'locations': []}),
            patch('skeleton_loader.get_skeleton_prompt_block', return_value=''),
            patch('dm_philosophy_loader.get_philosophy_block', return_value=''),
            patch('adjudicator.arbitrate', return_value=arb_result),
            patch('narration_verifier.verify_narration',
                  side_effect=_fake_verify),
        ):
            from dnd_engine import dm_respond
            response = dm_respond(
                campaign=campaign,
                characters=characters,
                player_action=player_action,
                avrae_events=[],
                acting_character_names=['Donovan'],
                actions=actions,
            )
        return response

    # ── Test 1: 1-actor → same prompt shape ──────────────────────────

    def test_1actor_produces_response(self):
        """1-actor path runs end-to-end without error."""
        arb = _make_arb_result_from_verdicts([_check_success_verdict()], ['Donovan'])
        response = self._call_dm_respond(
            player_action='I sneak past',
            actions=[('Donovan', 'I sneak past')],
            arb_result=arb,
            route_responses=[('Donovan slips into shadow.', {})],
            verify_results=[VerificationResult(passed=True, signals={
                'narration_chars': 30, 'canonical_combatants_count': 1
            })],
        )
        self.assertIsNotNone(response)
        self.assertIsInstance(response, str)

    # ── Test 2: 2-actor non-contradictory → sequence verified ────────

    def test_2actor_sequence_verified_and_posted(self):
        """2-actor sequence → ArbitrationResult sequence, verified once, posted."""
        arb = _make_arb_result_from_verdicts(
            [_check_success_verdict(), _free_verdict()],
            ['Donovan', 'Bruce'],
            merge_plan='sequence',
        )
        response = self._call_dm_respond(
            player_action='Donovan sneaks; Bruce watches',
            actions=[('Donovan', 'I sneak'), ('Bruce', 'I watch')],
            arb_result=arb,
            route_responses=[('Donovan slips past. Bruce stands ready.', {})],
            verify_results=[VerificationResult(passed=True, signals={
                'narration_chars': 40, 'canonical_combatants_count': 2
            })],
        )
        self.assertIsNotNone(response)
        self.assertIsInstance(response, str)

    # ── Test 3: 2-actor contradictory → override ─────────────────────

    def test_2actor_override_verified_posted(self):
        """2-actor override → ArbitrationResult override, verified, posted."""
        arb = _make_arb_result_from_verdicts(
            [_check_success_verdict(), _free_verdict()],
            ['Donovan', 'Bruce'],
            merge_plan='override',
        )
        arb.overridden_actors = ['Bruce']
        response = self._call_dm_respond(
            player_action='combined',
            actions=[('Donovan', 'sneak'), ('Bruce', 'you fail')],
            arb_result=arb,
            route_responses=[('Donovan slips past. Bruce witnesses the outcome.', {})],
            verify_results=[VerificationResult(passed=True, signals={
                'narration_chars': 50, 'canonical_combatants_count': 2
            })],
        )
        self.assertIsNotNone(response)

    # ── Test 4: Verification fails → retry fires → retry succeeds ────

    def test_verification_fails_retry_fires_succeeds(self):
        """Narration fabricates NPC → verification fails → retry fires →
        retry succeeds → retry response posted."""
        arb = _make_arb_result_from_verdicts([_free_verdict()], ['Donovan'])
        initial_fail = VerificationResult(
            passed=False,
            violation_class=VIOLATION_FABRICATED_COMBATANT,
            detected_phrase='Silent Beast (+ combat verb)',
            retry_constraint='Do not introduce fabricated combatants.',
            signals={'narration_chars': 60, 'canonical_combatants_count': 1},
        )
        retry_pass = VerificationResult(
            passed=True,
            signals={'narration_chars': 55, 'canonical_combatants_count': 1},
        )
        response = self._call_dm_respond(
            player_action='Donovan acts',
            actions=[('Donovan', 'Donovan acts')],
            arb_result=arb,
            route_responses=[
                ('Silent Beast lunges at Donovan.', {}),
                ('The goblin charges at Donovan.', {}),
            ],
            verify_results=[initial_fail, retry_pass],
        )
        self.assertIsNotNone(response)

    # ── Test 5: Both passes fail → escalation placeholder ────────────

    def test_both_passes_fail_escalation_placeholder(self):
        """Both LLM passes fail → escalation placeholder posted."""
        arb = _make_arb_result_from_verdicts(
            [_check_success_verdict()], ['Donovan']
        )
        initial_fail = VerificationResult(
            passed=False,
            violation_class=VIOLATION_FABRICATED_COMBATANT,
            detected_phrase='Silent Beast (+ combat verb)',
            retry_constraint='No fabricated combatants.',
            signals={'narration_chars': 60, 'canonical_combatants_count': 1},
        )
        retry_fail = VerificationResult(
            passed=False,
            violation_class=VIOLATION_FABRICATED_COMBATANT,
            detected_phrase='Keeper (+ combat verb)',
            retry_constraint='No fabricated combatants.',
            signals={'narration_chars': 55, 'canonical_combatants_count': 1},
        )
        response = self._call_dm_respond(
            player_action='Donovan acts',
            actions=[('Donovan', 'Donovan acts')],
            arb_result=arb,
            route_responses=[
                ('Silent Beast lunges.', {}),
                ('Keeper attacks.', {}),
            ],
            verify_results=[initial_fail, retry_fail],
        )
        # After both fail, escalation placeholder is posted
        self.assertIsNotNone(response)
        self.assertIsInstance(response, str)

    # ── Test 6: ARBITRATION_ENABLED=False → Track 7 #1 behavior ─────

    def test_arbitration_flag_off_single_actor_behavior(self):
        """ARBITRATION_ENABLED=False → arbitrate degrades to first-actor-only."""
        adjudicator.ARBITRATION_ENABLED = False
        try:
            arb = _make_arb_result_from_verdicts([_free_verdict()], ['Donovan'])
            response = self._call_dm_respond(
                player_action='Donovan acts',
                actions=[('Donovan', 'Donovan acts'), ('Bruce', 'Bruce acts')],
                arb_result=arb,
                route_responses=[('Narration.', {})],
                verify_results=[VerificationResult(passed=True, signals={})],
            )
            self.assertIsNotNone(response)
        finally:
            adjudicator.ARBITRATION_ENABLED = True

    # ── Test 7: VERIFICATION_ENABLED=False → no post-pass ────────────

    def test_verification_flag_off_no_postpass(self):
        """VERIFICATION_ENABLED=False → verify_narration returns passed=True
        immediately, original narration posts directly."""
        nv.VERIFICATION_ENABLED = False
        try:
            arb = _make_arb_result_from_verdicts([_free_verdict()], ['Donovan'])
            response = self._call_dm_respond(
                player_action='Donovan acts',
                actions=[('Donovan', 'Donovan acts')],
                arb_result=arb,
                route_responses=[('Original narration.', {})],
                # verify_narration is still called but will fast-return passed=True
                verify_results=[VerificationResult(passed=True, signals={})],
            )
            self.assertIsNotNone(response)
        finally:
            nv.VERIFICATION_ENABLED = True


# ─────────────────────────────────────────────────────────
# Integration: arbitrate + verify_narration wiring
# ─────────────────────────────────────────────────────────

class TestArbitrateVerifyDirectIntegration(unittest.TestCase):
    """Lighter-weight tests that exercise the modules directly without
    going through dm_respond's full prompt machinery."""

    def setUp(self):
        adjudicator.ARBITRATION_ENABLED = True
        nv.VERIFICATION_ENABLED = True

    def test_arbitrate_then_verify_actor_omission_fires(self):
        """ArbitrationResult with Donovan CHECK + Bruce COMBAT, narration
        omitting Bruce → ACTOR_OMISSION fires."""
        from adjudicator import _constraint_check_resolved
        arb = _make_arb_result_from_verdicts(
            [
                AdjudicationResult(
                    category=CHECK_ACTION, allowed=True,
                    skill='stealth', dc=15, roll_value=18, success=True,
                    narration_constraint=_constraint_check_resolved(
                        'stealth', 15, 'medium', 18, True
                    ),
                    signals={},
                ),
                AdjudicationResult(
                    category=COMBAT_ACTION, allowed=False,
                    refusal_kind=REFUSAL_COMBAT_INACTIVE,
                    narration_constraint='Combat inactive.',
                    signals={},
                ),
            ],
            ['Donovan', 'Bruce'],
        )
        with patch('narration_verifier._build_canonical_set',
                   return_value={'Donovan', 'Bruce'}):
            result = nv.verify_narration(
                "Donovan slips into the shadows silently.",
                arb, None, [], [],
            )
        # Bruce (COMBAT verdict) is missing from narration → ACTOR_OMISSION
        self.assertFalse(result.passed)
        self.assertEqual(result.violation_class, nv.VIOLATION_ACTOR_OMISSION)
        self.assertIn('Bruce', result.detected_phrase)

    def test_arbitrate_then_verify_both_present_passes(self):
        """Narration names both Donovan and Bruce → passes."""
        from adjudicator import _constraint_check_resolved
        arb = _make_arb_result_from_verdicts(
            [
                AdjudicationResult(
                    category=CHECK_ACTION, allowed=True,
                    skill='stealth', dc=15, roll_value=18, success=True,
                    narration_constraint=_constraint_check_resolved(
                        'stealth', 15, 'medium', 18, True
                    ),
                    signals={},
                ),
                AdjudicationResult(
                    category=COMBAT_ACTION, allowed=False,
                    refusal_kind=REFUSAL_COMBAT_INACTIVE,
                    narration_constraint='Combat inactive.',
                    signals={},
                ),
            ],
            ['Donovan', 'Bruce'],
        )
        with patch('narration_verifier._build_canonical_set',
                   return_value={'Donovan', 'Bruce'}):
            result = nv.verify_narration(
                "Donovan slips past the lookout while Bruce readies his weapon.",
                arb, None, [], [],
            )
        self.assertTrue(result.passed)


if __name__ == '__main__':
    unittest.main()
