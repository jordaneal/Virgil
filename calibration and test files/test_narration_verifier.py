"""
test_narration_verifier.py — Track 7 #2 verification layer tests (§8.2).

Tests verify_narration() against controlled ArbitrationResult fixtures and
narration strings. No live DB, LLM, or Discord calls. Covers all four
detection classes (FABRICATED_COMBATANT, VERDICT_CONTRADICTION,
STATE_MUTATION_CLAIM, ACTOR_OMISSION) with positive and negative cases.
"""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(__file__))

import narration_verifier as nv
from narration_verifier import (
    verify_narration, VerificationResult,
    VIOLATION_FABRICATED_COMBATANT,
    VIOLATION_VERDICT_CONTRADICTION,
    VIOLATION_STATE_MUTATION_CLAIM,
    VIOLATION_ACTOR_OMISSION,
    build_verification_retry_prefix,
    build_escalation_placeholder,
    verification_log_summary,
)
import adjudicator
from adjudicator import (
    AdjudicationResult,
    ArbitrationResult,
    FREE_ACTION, CHECK_ACTION, CAPABILITY_ACTION, COMBAT_ACTION,
    REFUSAL_CAPABILITY, REFUSAL_COMBAT_INACTIVE,
)


# ─────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────

def _free_verdict(actor='actor') -> AdjudicationResult:
    return AdjudicationResult(
        category=FREE_ACTION,
        allowed=True,
        narration_constraint='',
        signals={},
    )


def _check_success_verdict(skill='stealth', dc=15, roll=18) -> AdjudicationResult:
    return AdjudicationResult(
        category=CHECK_ACTION,
        allowed=True,
        skill=skill,
        dc=dc,
        roll_value=roll,
        success=True,
        narration_constraint='Stealth check DC 15 rolled 18. SUCCESS.',
        signals={},
    )


def _check_fail_verdict(skill='persuasion', dc=15, roll=8) -> AdjudicationResult:
    return AdjudicationResult(
        category=CHECK_ACTION,
        allowed=False,
        refusal_kind='check_failed',
        skill=skill,
        dc=dc,
        roll_value=roll,
        success=False,
        narration_constraint='Persuasion check DC 15 rolled 8. FAILURE.',
        signals={},
    )


def _capability_refused_verdict() -> AdjudicationResult:
    return AdjudicationResult(
        category=CAPABILITY_ACTION,
        allowed=False,
        refusal_kind=REFUSAL_CAPABILITY,
        narration_constraint='Fireball capability refused.',
        signals={},
    )


def _combat_inactive_verdict() -> AdjudicationResult:
    return AdjudicationResult(
        category=COMBAT_ACTION,
        allowed=False,
        refusal_kind=REFUSAL_COMBAT_INACTIVE,
        narration_constraint='Combat not active.',
        signals={},
    )


def _make_arb_result(verdicts, actor_order, merge_plan='sequence',
                      overridden_actors=None):
    """Build a minimal ArbitrationResult for test purposes."""
    return ArbitrationResult(
        verdicts=verdicts,
        actor_order=actor_order,
        merge_plan=merge_plan,
        primary_actor=actor_order[0] if actor_order else '',
        combined_constraint='',
        overridden_actors=overridden_actors or [],
        signals={},
    )


# Helper to prevent real DB/filesystem calls in _build_canonical_set
def _patch_canonical_helpers():
    """Return a context manager that patches all external DB/FS calls
    in narration_verifier._build_canonical_set to return nothing."""
    from unittest.mock import patch
    return patch.multiple(
        'narration_verifier',
        # patch get_bound_character_names to an import that won't exist at test time
    )


def _verify(narration, verdicts, actor_order, **kwargs):
    """Convenience wrapper: call verify_narration with patched canonicals."""
    arb = _make_arb_result(verdicts, actor_order)
    with patch('narration_verifier._build_canonical_set',
               return_value=kwargs.pop('canonical_set', {'Donovan', 'Bruce',
                                                          'goblin1', 'Goblin 1',
                                                          'Bruce Banner'})):
        return verify_narration(
            narration_text=narration,
            arbitration_result=arb,
            scene_state=None,
            combatants=kwargs.pop('combatants', []),
            npcs_canonical=kwargs.pop('npcs_canonical', []),
        )


# ─────────────────────────────────────────────────────────
# FABRICATED_COMBATANT
# ─────────────────────────────────────────────────────────

class TestFabricatedCombatant(unittest.TestCase):

    def setUp(self):
        nv.VERIFICATION_ENABLED = True

    def test_fabricated_name_plus_combat_verb_fires(self):
        """Silent Beast + 'lunges' → FABRICATED_COMBATANT violation."""
        arb = _make_arb_result([_free_verdict()], ['Donovan'])
        with patch('narration_verifier._build_canonical_set',
                   return_value={'Donovan'}):
            result = verify_narration(
                "Silent Beast lunges from the shadows at Donovan.",
                arb, None, [], [],
            )
        self.assertFalse(result.passed)
        self.assertEqual(result.violation_class, VIOLATION_FABRICATED_COMBATANT)
        self.assertIn('Silent Beast', result.fabricated_names)

    def test_fabricated_name_non_combat_verb_passes(self):
        """Silent Beast + 'watches' (no combat verb) → passes."""
        arb = _make_arb_result([_free_verdict()], ['Donovan'])
        with patch('narration_verifier._build_canonical_set',
                   return_value={'Donovan'}):
            result = verify_narration(
                "Silent Beast watches from the shadows.",
                arb, None, [], [],
            )
        self.assertTrue(result.passed)

    def test_canonical_pc_name_plus_combat_verb_passes(self):
        """Bruce Banner (canonical PC) + combat verb → passes (canonical)."""
        arb = _make_arb_result([_check_success_verdict()], ['Bruce Banner'])
        with patch('narration_verifier._build_canonical_set',
                   return_value={'Bruce Banner', 'Donovan'}):
            result = verify_narration(
                "Bruce Banner swings his axe at the goblin.",
                arb, None, [], [],
            )
        self.assertTrue(result.passed)

    def test_canonical_combatant_name_passes(self):
        """Goblin 1 (canonical combatant in combatants list) → passes."""
        arb = _make_arb_result([_free_verdict()], ['Donovan'])
        with patch('narration_verifier._build_canonical_set',
                   return_value={'Donovan', 'Goblin 1'}):
            result = verify_narration(
                "Goblin 1 attacks Donovan with a rusty blade.",
                arb, None, [], [],
            )
        self.assertTrue(result.passed)

    def test_canonical_npc_plus_combat_verb_passes(self):
        """Canonical NPC by name + combat verb → passes."""
        arb = _make_arb_result([_free_verdict()], ['Donovan'])
        with patch('narration_verifier._build_canonical_set',
                   return_value={'Donovan', 'Keeper', 'Keeper of the Vein'}):
            result = verify_narration(
                "The Keeper strikes at Donovan.",
                arb, None, [], [],
            )
        self.assertTrue(result.passed)


# ─────────────────────────────────────────────────────────
# VERDICT_CONTRADICTION
# ─────────────────────────────────────────────────────────

class TestVerdictContradiction(unittest.TestCase):

    def setUp(self):
        nv.VERIFICATION_ENABLED = True

    def test_check_failed_narration_describes_success(self):
        """Adjudication CHECK failed → narration 'you slip past' → violation."""
        result = _verify(
            "You slip past the guard unnoticed.",
            [_check_fail_verdict()],
            ['Donovan'],
        )
        self.assertFalse(result.passed)
        self.assertEqual(result.violation_class, VIOLATION_VERDICT_CONTRADICTION)

    def test_check_failed_narration_describes_failure_passes(self):
        """Adjudication CHECK failed → narration 'you fail' → passes (correct)."""
        result = _verify(
            "Donovan fails to slip past the guard — spotted.",
            [_check_fail_verdict()],
            ['Donovan'],
        )
        self.assertTrue(result.passed)

    def test_capability_refused_narration_says_it_worked(self):
        """Adjudication CAPABILITY refused → narration 'the spell takes hold' → violation."""
        result = _verify(
            "The spell takes hold and fire erupts from Donovan's hands.",
            [_capability_refused_verdict()],
            ['Donovan'],
        )
        self.assertFalse(result.passed)
        self.assertEqual(result.violation_class, VIOLATION_VERDICT_CONTRADICTION)

    def test_combat_inactive_narration_lands_damage(self):
        """Adjudication COMBAT_INACTIVE → narration 'the bartender takes 8 damage'."""
        result = _verify(
            "Donovan swings and the bartender takes 8 damage.",
            [_combat_inactive_verdict()],
            ['Donovan'],
        )
        self.assertFalse(result.passed)
        # Could be VERDICT_CONTRADICTION or STATE_MUTATION_CLAIM (first match wins)
        self.assertIn(result.violation_class, (
            VIOLATION_VERDICT_CONTRADICTION,
            VIOLATION_STATE_MUTATION_CLAIM,
        ))

    def test_check_success_narration_describes_success_passes(self):
        """Adjudication CHECK success → narration describes success → passes."""
        result = _verify(
            "Donovan successfully slips past the lookout, melting into shadows.",
            [_check_success_verdict()],
            ['Donovan'],
        )
        self.assertTrue(result.passed)

    def test_free_verdict_any_narration_passes(self):
        """Adjudication FREE → no constraint to violate → always passes."""
        result = _verify(
            "You slip past unnoticed.",
            [_free_verdict()],
            ['Donovan'],
        )
        self.assertTrue(result.passed)

    def test_check_success_narration_describes_failure_fires(self):
        """Adjudication CHECK success → narration 'the lock holds' → violation."""
        result = _verify(
            "The lock holds. You're spotted.",
            [_check_success_verdict('lockpicking', 10, 18)],
            ['Donovan'],
        )
        self.assertFalse(result.passed)
        self.assertEqual(result.violation_class, VIOLATION_VERDICT_CONTRADICTION)


# ─────────────────────────────────────────────────────────
# STATE_MUTATION_CLAIM
# ─────────────────────────────────────────────────────────

class TestStateMutationClaim(unittest.TestCase):

    def setUp(self):
        nv.VERIFICATION_ENABLED = True

    def test_hp_damage_number_fires(self):
        """'the goblin takes 12 damage' → STATE_MUTATION_CLAIM."""
        result = _verify(
            "The goblin takes 12 damage from Donovan's blade.",
            [_free_verdict()],
            ['Donovan'],
        )
        self.assertFalse(result.passed)
        self.assertEqual(result.violation_class, VIOLATION_STATE_MUTATION_CLAIM)

    def test_rhetorical_description_passes(self):
        """'the goblin staggers, blood on its tunic' → passes (rhetorical)."""
        result = _verify(
            "The goblin staggers, blood welling from a deep gash in its side.",
            [_free_verdict()],
            ['Donovan'],
        )
        self.assertTrue(result.passed)

    def test_xp_gain_fires(self):
        """'you gain 200 XP' → STATE_MUTATION_CLAIM."""
        result = _verify(
            "You gain 200 XP for defeating the bandits.",
            [_free_verdict()],
            ['Donovan'],
        )
        self.assertFalse(result.passed)
        self.assertEqual(result.violation_class, VIOLATION_STATE_MUTATION_CLAIM)

    def test_permanently_sealed_fires(self):
        """'the door is permanently sealed' → STATE_MUTATION_CLAIM."""
        result = _verify(
            "The door is permanently sealed by the magical glyph.",
            [_free_verdict()],
            ['Donovan'],
        )
        self.assertFalse(result.passed)
        self.assertEqual(result.violation_class, VIOLATION_STATE_MUTATION_CLAIM)

    def test_dealt_damage_fires(self):
        """'deals 8 damage' → STATE_MUTATION_CLAIM."""
        result = _verify(
            "Donovan's axe deals 8 damage to the goblin.",
            [_free_verdict()],
            ['Donovan'],
        )
        self.assertFalse(result.passed)
        self.assertEqual(result.violation_class, VIOLATION_STATE_MUTATION_CLAIM)


# ─────────────────────────────────────────────────────────
# ACTOR_OMISSION
# ─────────────────────────────────────────────────────────

class TestActorOmission(unittest.TestCase):

    def setUp(self):
        nv.VERIFICATION_ENABLED = True

    def test_both_actors_present_passes(self):
        """Both Donovan (CHECK) and Bruce (COMBAT) named → passes."""
        result = _verify(
            "Donovan slips into the shadows while Bruce readies his weapon.",
            [_check_success_verdict(), _combat_inactive_verdict()],
            ['Donovan', 'Bruce'],
        )
        self.assertTrue(result.passed)

    def test_missing_non_free_actor_fires(self):
        """Bruce (COMBAT verdict) missing from narration → ACTOR_OMISSION."""
        result = _verify(
            "Donovan slips past the guard silently.",
            [_check_success_verdict(), _combat_inactive_verdict()],
            ['Donovan', 'Bruce'],
        )
        self.assertFalse(result.passed)
        self.assertEqual(result.violation_class, VIOLATION_ACTOR_OMISSION)
        self.assertIn('Bruce', result.detected_phrase)

    def test_missing_free_actor_passes(self):
        """Bruce's verdict is FREE → omitting Bruce from narration passes."""
        result = _verify(
            "Donovan slips past the guard silently.",
            [_check_success_verdict(), _free_verdict()],
            ['Donovan', 'Bruce'],
        )
        self.assertTrue(result.passed)

    def test_missing_cache_miss_actor_passes(self):
        """Actor with no_character_context (cache miss) → omission skipped."""
        cache_miss_verdict = AdjudicationResult(
            category=FREE_ACTION,
            allowed=True,
            refusal_kind='no_character_context',
            narration_constraint='',
            signals={},
        )
        result = _verify(
            "Donovan slips past the guard silently.",
            [_check_success_verdict(), cache_miss_verdict],
            ['Donovan', 'Bruce'],
        )
        self.assertTrue(result.passed)

    def test_single_actor_present_passes(self):
        """Single-actor narration mentions actor → passes."""
        result = _verify(
            "Donovan sneaks past the lookout.",
            [_check_success_verdict()],
            ['Donovan'],
        )
        self.assertTrue(result.passed)

    def test_single_actor_absent_fires(self):
        """Single-actor narration omits actor (rare degenerate) → fires."""
        result = _verify(
            "The lookout doesn't notice anything.",
            [_check_success_verdict()],
            ['Donovan'],
        )
        self.assertFalse(result.passed)
        self.assertEqual(result.violation_class, VIOLATION_ACTOR_OMISSION)

    def test_actor_omission_case_insensitive(self):
        """Substring check is case-insensitive."""
        result = _verify(
            "DONOVAN slips through the darkness.",
            [_check_success_verdict()],
            ['Donovan'],
        )
        self.assertTrue(result.passed)


# ─────────────────────────────────────────────────────────
# Retry constraint render
# ─────────────────────────────────────────────────────────

class TestRetryConstraintRender(unittest.TestCase):

    def setUp(self):
        nv.VERIFICATION_ENABLED = True

    def test_fabricated_constraint_names_class(self):
        result = _verify(
            "Silent Beast lunges at Donovan.",
            [_free_verdict()],
            ['Donovan'],
            canonical_set={'Donovan'},
        )
        self.assertFalse(result.passed)
        self.assertIn(VIOLATION_FABRICATED_COMBATANT, result.retry_constraint)

    def test_verdict_contradiction_constraint_names_class(self):
        result = _verify(
            "You slip past unnoticed.",
            [_check_fail_verdict()],
            ['Donovan'],
        )
        self.assertFalse(result.passed)
        self.assertIn(VIOLATION_VERDICT_CONTRADICTION, result.retry_constraint)

    def test_state_mutation_constraint_names_class(self):
        result = _verify(
            "The goblin takes 12 damage.",
            [_free_verdict()],
            ['Donovan'],
        )
        self.assertFalse(result.passed)
        self.assertIn(VIOLATION_STATE_MUTATION_CLAIM, result.retry_constraint)

    def test_actor_omission_constraint_names_missing_actor(self):
        result = _verify(
            "Donovan sneaks past.",
            [_check_success_verdict(), _combat_inactive_verdict()],
            ['Donovan', 'Bruce'],
        )
        self.assertFalse(result.passed)
        self.assertIn('Bruce', result.retry_constraint)

    def test_retry_prefix_build(self):
        """build_verification_retry_prefix produces === VERIFICATION FAILED === block."""
        result = _verify(
            "Silent Beast lunges.",
            [_free_verdict()],
            ['Donovan'],
            canonical_set={'Donovan'},
        )
        prefix = build_verification_retry_prefix(result)
        self.assertIn('=== VERIFICATION FAILED ===', prefix)
        self.assertIn('second pass', prefix)

    def test_retry_prefix_empty_on_pass(self):
        result = VerificationResult(passed=True)
        self.assertEqual(build_verification_retry_prefix(result), '')


# ─────────────────────────────────────────────────────────
# Feature flag
# ─────────────────────────────────────────────────────────

class TestVerificationFeatureFlag(unittest.TestCase):

    def test_flag_off_always_passes(self):
        nv.VERIFICATION_ENABLED = False
        try:
            arb = _make_arb_result([_check_fail_verdict()], ['Donovan'])
            with patch('narration_verifier._build_canonical_set',
                       return_value={'Donovan'}):
                result = verify_narration(
                    "You slip past unnoticed.",
                    arb, None, [], [],
                )
            self.assertTrue(result.passed)
        finally:
            nv.VERIFICATION_ENABLED = True

    def test_flag_on_detects_violations(self):
        nv.VERIFICATION_ENABLED = True
        arb = _make_arb_result([_check_fail_verdict()], ['Donovan'])
        with patch('narration_verifier._build_canonical_set',
                   return_value={'Donovan'}):
            result = verify_narration(
                "You slip past unnoticed.",
                arb, None, [], [],
            )
        self.assertFalse(result.passed)


# ─────────────────────────────────────────────────────────
# Escalation placeholder
# ─────────────────────────────────────────────────────────

class TestEscalationPlaceholder(unittest.TestCase):

    def setUp(self):
        nv.VERIFICATION_ENABLED = True

    def test_check_action_renders_skill_dc(self):
        arb = _make_arb_result(
            [_check_success_verdict('stealth', 15, 18)],
            ['Donovan'],
        )
        text = build_escalation_placeholder(arb)
        self.assertIn('Donovan', text)
        self.assertIn('DC 15', text)

    def test_capability_refused_renders_non_occurrence(self):
        arb = _make_arb_result(
            [_capability_refused_verdict()],
            ['Donovan'],
        )
        text = build_escalation_placeholder(arb)
        self.assertIn('Donovan', text)
        self.assertIn('capability', text.lower())

    def test_multi_actor_escalation_has_both_actors(self):
        arb = _make_arb_result(
            [_check_success_verdict(), _combat_inactive_verdict()],
            ['Donovan', 'Bruce'],
        )
        text = build_escalation_placeholder(arb)
        self.assertIn('Donovan', text)
        self.assertIn('Bruce', text)

    def test_free_actor_anomaly_logged(self):
        arb = _make_arb_result([_free_verdict()], ['Donovan'])
        text = build_escalation_placeholder(arb, failed_violation_class='actor_omission')
        # FREE verdict in escalation should log anomaly
        self.assertIn('Donovan', text)
        self.assertIn('VERIFICATION_ANOMALY', text)

    def test_none_result_returns_error_message(self):
        text = build_escalation_placeholder(None)
        self.assertIn('unavailable', text.lower())


# ─────────────────────────────────────────────────────────
# Log line helper
# ─────────────────────────────────────────────────────────

class TestVerificationLogLine(unittest.TestCase):

    def test_passed_log_line(self):
        r = VerificationResult(passed=True, signals={'narration_chars': 100,
                                                      'canonical_combatants_count': 5})
        line = verification_log_summary(42, r)
        self.assertIn('campaign=42', line)
        self.assertIn('passed=1', line)
        self.assertIn('retry_fired=0', line)
        self.assertIn('escalated=0', line)

    def test_failed_with_retry_log_line(self):
        initial = VerificationResult(
            passed=False,
            violation_class=VIOLATION_ACTOR_OMISSION,
            detected_phrase='Bruce absent',
            signals={'narration_chars': 80, 'canonical_combatants_count': 3},
        )
        retry = VerificationResult(passed=True, signals={})
        line = verification_log_summary(99, initial, retry_fired=True,
                                         retry_result=retry, escalated=False)
        self.assertIn('passed=0', line)
        self.assertIn('retry_fired=1', line)
        self.assertIn('retry_passed=1', line)
        self.assertIn('escalated=0', line)


# ─────────────────────────────────────────────────────────
# Known false-positive case (§11.M sub-decision, filed v1.x)
# ─────────────────────────────────────────────────────────

class TestActorOmissionKnownFalsePositive(unittest.TestCase):
    """Second-person 'you' addressing one of two PCs fires in v1 (as expected).
    This is the known FP per §11.M — test documents the behavior, does NOT
    suppress the detection. v1.x deferred."""

    def setUp(self):
        nv.VERIFICATION_ENABLED = True

    def test_pronoun_you_fires_in_v1(self):
        """Two PCs: LLM uses 'you spin away' for Bruce but doesn't name him.
        v1 fires ACTOR_OMISSION. This is expected behavior per §11.M FP note."""
        result = _verify(
            "Donovan slips into the shadows while you spin away from the blade.",
            [_check_success_verdict(), _combat_inactive_verdict()],
            ['Donovan', 'Bruce'],
        )
        # v1: fires because 'Bruce' is not a substring (pronoun FP)
        # This documents v1 behavior — the test will pass once v1.x ships
        # pronoun-aware detection (at which point this test changes to assertTrue)
        self.assertFalse(result.passed)
        self.assertEqual(result.violation_class, VIOLATION_ACTOR_OMISSION)


if __name__ == '__main__':
    unittest.main()
