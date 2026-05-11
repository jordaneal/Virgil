"""
narration_verifier.py
─────────────────────────────────────────────────────────
Track 7 #2 — Post-LLM Narration Verification.

Parallel sibling to adjudicator.py per Doctrine §63: different actor
(LLM vs player), different invariants (did the narration honor the verdict
and stay in canon?), different vocabulary surfaces, different mitigation
paths. Forked at the highest layer where invariants diverge.

Single pure entry point:
  verify_narration(narration_text, arbitration_result, scene_state,
                   combatants, npcs_canonical) -> VerificationResult

Four detection classes (§11.F lock):
  FABRICATED_COMBATANT  — narration introduces a named creature not in
                          canonical sources AND uses a combat verb nearby.
  VERDICT_CONTRADICTION — narration contradicts the binding AdjudicationResult
                          for the turn (e.g. LLM narrates success on a
                          failed check).
  STATE_MUTATION_CLAIM  — narration asserts HP/XP/death/permanent-state
                          numbers the LLM has no authority to write.
  ACTOR_OMISSION        — narration omits a non-FREE actor whose verdict
                          was binding (§11.M, §11.Q).

Reads from dnd_npcs, dnd_combat_state, skeleton-declared NPCs, and
bound PCs. Never writes. Pure-read.

Soft-fail at call site (Doctrine §59): on any exception, caller treats
result as passed=True and posts original narration (fail-open).

See virgil-docs/TRACK_7_2_SPEC.md §5.3 for detection flow.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


# ─────────────────────────────────────────────────────────
# Feature flag (§1.9 rollback — independent of ARBITRATION_ENABLED)
# ─────────────────────────────────────────────────────────
# When False, verify_narration() returns VerificationResult(passed=True)
# immediately. Allows narration verification to be disabled without
# touching arbitration.
VERIFICATION_ENABLED = True


# ─────────────────────────────────────────────────────────
# Violation class constants
# ─────────────────────────────────────────────────────────
VIOLATION_FABRICATED_COMBATANT  = 'fabricated_combatant'
VIOLATION_VERDICT_CONTRADICTION = 'verdict_contradiction'
VIOLATION_STATE_MUTATION_CLAIM  = 'state_mutation_claim'
VIOLATION_ROLL_OUTCOME_DRIFT    = 'roll_outcome_drift'  # Ship 1 (S34)
VIOLATION_ACTOR_OMISSION        = 'actor_omission'


# ─────────────────────────────────────────────────────────
# Result dataclass
# ─────────────────────────────────────────────────────────

@dataclass
class VerificationResult:
    passed: bool = True
    violation_class: str = ''        # '' | VIOLATION_* constant
    detected_phrase: str = ''        # first 140 chars of the offending phrase
    retry_constraint: str = ''       # imperative directive for retry prompt
    canonical_combatants: list = field(default_factory=list)
    fabricated_names: list = field(default_factory=list)
    signals: dict = field(default_factory=dict)


# ─────────────────────────────────────────────────────────
# FABRICATED_COMBATANT vocabulary (§5.3 step 1)
# ─────────────────────────────────────────────────────────
# Combat-active verbs that, when found within 20 chars of a Capitalized
# candidate name, trigger fabricated-combatant detection. Curated narrow
# to minimize false-positive on descriptive combat prose that doesn't
# introduce new entities.
_FABRICATED_COMBATANT_VERBS = (
    r'attacks?',
    r'swings?',
    r'hits?',
    r'charges?',
    r'blocks?',
    r'parries?',
    r'springs?',
    r'strikes?',
    r'rakes?',
    r'lashes?',
    r'conjures?',
    r'casts?\s+at',
    r'fires?\s+at',
    r'slashes?',
    r'lunges?',
    r'rears?\s+up',
)

_COMBAT_VERB_RX = re.compile(
    r'(?:' + '|'.join(_FABRICATED_COMBATANT_VERBS) + r')',
    re.IGNORECASE,
)

# Sentence-start words that can superficially look like Proper-Noun
# candidates but are common narrative openers. Excluding them reduces
# false-positives on "The goblin charges" where "The" is capitalized
# because it opens a sentence.
_SENTENCE_STARTERS = frozenset({
    'The', 'A', 'An', 'This', 'That', 'These', 'Those', 'Their', 'Its',
    'His', 'Her', 'Your', 'Our', 'My', 'He', 'She', 'It', 'They', 'You',
    'We', 'I', 'But', 'And', 'Or', 'So', 'Yet', 'For', 'Nor',
    'With', 'From', 'At', 'In', 'On', 'As', 'By', 'Of', 'To',
    'Then', 'Now', 'Suddenly', 'Meanwhile', 'Finally', 'However',
    'While', 'When', 'As', 'Before', 'After', 'Above', 'Below',
    'Dungeon', 'Master', 'DM', 'GM',
})

# Regex to capture Capitalized two-or-three-word sequences as NER candidates.
# Excludes known stopword sentence-openers at the first position.
_NAMED_CANDIDATE_RX = re.compile(
    r'\b([A-Z][a-z]{1,}(?:\s+[A-Z][a-z]+){0,2})\b'
)


def _extract_named_candidates(text: str) -> list[str]:
    """Return Capitalized-name candidates from narration text, excluding
    common sentence-starter words and short tokens unlikely to be entity names."""
    candidates = []
    for m in _NAMED_CANDIDATE_RX.finditer(text):
        phrase = m.group(1).strip()
        first_word = phrase.split()[0]
        if first_word in _SENTENCE_STARTERS:
            continue
        if len(first_word) < 3:
            continue
        candidates.append(phrase)
    return candidates


def _name_is_canonical(name: str, canonical_set: set) -> bool:
    """Case-insensitive substring check: is `name` covered by any canonical entry?"""
    name_lower = name.lower()
    for canonical in canonical_set:
        if name_lower in canonical.lower() or canonical.lower() in name_lower:
            return True
    return False


def _has_combat_verb_nearby(text: str, name: str, window: int = 20) -> bool:
    """Check for a combat verb within `window` chars of `name` in `text`."""
    for m in re.finditer(re.escape(name), text, re.IGNORECASE):
        start = max(0, m.start() - window)
        end = min(len(text), m.end() + window)
        context = text[start:end]
        if _COMBAT_VERB_RX.search(context):
            return True
    return False


# ─────────────────────────────────────────────────────────
# STATE_MUTATION_CLAIM vocabulary (§5.3 step 3)
# ─────────────────────────────────────────────────────────

_STATE_MUTATION_PATTERNS = [
    # HP-mechanics claim: "takes 12 damage" / "deals 8 hp"
    re.compile(r'\b(?:takes?|deals?|does)\s+\d+\s+(?:damage|hp)\b', re.IGNORECASE),
    # Death claim (Avrae's call)
    re.compile(r'\bis\s+(?:now\s+)?(?:dead|killed|slain)\b', re.IGNORECASE),
    # XP claim
    re.compile(r'\byou\s+(?:gain|earn)\s+\d+\s+(?:xp|experience)\b', re.IGNORECASE),
    # Irreversible-state claim outside canonical writers
    re.compile(r'\bpermanently\s+(?:open|closed|sealed|destroyed|broken|locked|'
               r'ruined|collapsed|flooded|frozen|burning)\b', re.IGNORECASE),
]


# ─────────────────────────────────────────────────────────
# VERDICT_CONTRADICTION vocabulary (§5.3 step 2)
# ─────────────────────────────────────────────────────────
# Per-verdict-category phrase lists. First match against narration wins.

# CHECK failure: narration describes success when the check failed
_CHECK_FAILURE_SUCCESS_PHRASES = [
    re.compile(r'\byou\s+(?:slip|slipped)\s+past\b', re.IGNORECASE),
    re.compile(r"\bthe\s+lock\s+clicks?\s+open\b", re.IGNORECASE),
    re.compile(r"\b(?:doesn'?t?|does\s+not)\s+notice\b", re.IGNORECASE),
    re.compile(r'\bunnoticed\b', re.IGNORECASE),
    re.compile(r'\byou\s+(?:succeed|succeeded)\b', re.IGNORECASE),
    re.compile(r'\byou\s+manage(?:d)?\s+to\b', re.IGNORECASE),
    re.compile(r'\bsuccess(?:fully)?\b', re.IGNORECASE),
    re.compile(r'\byou\s+make\s+it\b', re.IGNORECASE),
]

# CHECK success: narration describes failure when the check succeeded
_CHECK_SUCCESS_FAILURE_PHRASES = [
    re.compile(r"\byou'?re\s+spotted\b", re.IGNORECASE),
    re.compile(r'\bthe\s+lock\s+holds?\b', re.IGNORECASE),
    re.compile(r'\byou\s+(?:fail|failed)\b', re.IGNORECASE),
    re.compile(r'\byou\s+(?:are|were)\s+caught\b', re.IGNORECASE),
    re.compile(r'\byou\s+stumble\b', re.IGNORECASE),
    re.compile(r'\bfail(?:s|ed)?\s+(?:the|your)\b', re.IGNORECASE),
]

# CAPABILITY refused: narration describes it working
_CAPABILITY_REFUSED_SUCCESS_PHRASES = [
    re.compile(r'\bthe\s+spell\s+takes?\s+hold\b', re.IGNORECASE),
    re.compile(r'\bthe\s+(?:rage|fury)\s+rises?\b', re.IGNORECASE),
    re.compile(r'\byour\s+(?:spell|magic|ability|power)\s+(?:works?|fires?|activates?|takes?\s+hold)\b', re.IGNORECASE),
    re.compile(r'\bthe\s+incantation\s+(?:works?|takes?\s+hold|fires?)\b', re.IGNORECASE),
    re.compile(r'\bthe\s+(?:fireball|lightning\s+bolt|magic\s+missile)\s+(?:erupts?|strikes?|explodes?|fires?)\b', re.IGNORECASE),
]

# COMBAT inactive: narration describes combat landing when combat is inactive
_COMBAT_INACTIVE_DAMAGE_PHRASES = [
    re.compile(r'\b(?:takes?|deals?|does)\s+\d+\s+(?:damage|hp)\b', re.IGNORECASE),
    re.compile(r'\bthe\s+(?:attack|blow|strike|slash)\s+(?:lands?|connects?|hits?)\b', re.IGNORECASE),
    re.compile(r'\byou\s+(?:hit|strike|slash|cut|wound)\s+(?:the|your|their)\b', re.IGNORECASE),
    re.compile(r'\bdrops?\s+to\s+\d+\s+(?:hp|hit\s*points?)\b', re.IGNORECASE),
]


def _build_canonical_set(campaign_id: int,
                          combatants: Optional[list],
                          npcs_canonical: Optional[list],
                          extra_names: Optional[list] = None) -> set:
    """Assemble the full canonical name set for fabrication detection.

    Pulls from:
      a) npcs_canonical (passed in — already-resolved list of canonical NPC names)
      b) active combatants list (dnd_combat_state snapshot)
      c) bound PCs (get_bound_character_names)
      d) skeleton-declared NPCs
      e) extra_names if provided (e.g., actor_order from ArbitrationResult)
    """
    canonical = set()

    # Canonical NPCs from dnd_npcs (caller resolves these before calling)
    for name in (npcs_canonical or []):
        if name:
            canonical.add(name.strip())

    # Active combatants from dnd_combat_state snapshot
    for c in (combatants or []):
        if isinstance(c, dict):
            n = c.get('name') or c.get('character_name') or ''
            if n:
                canonical.add(n.strip())

    # Extra names (actor_order character names, passed explicitly)
    for name in (extra_names or []):
        if name:
            canonical.add(name.strip())

    # Bound PCs — always canonical
    try:
        from dnd_engine import get_bound_character_names
        pc_names = get_bound_character_names(campaign_id)
        for n in pc_names:
            if n:
                canonical.add(n.strip())
    except Exception:
        pass

    # Skeleton-declared NPCs
    try:
        from skeleton_loader import parse_skeleton_file
        parsed = parse_skeleton_file(campaign_id)
        for npc in (parsed or {}).get('npcs', []):
            n = npc.get('name') or ''
            if n:
                canonical.add(n.strip())
    except Exception:
        pass

    return canonical


# ─────────────────────────────────────────────────────────
# Retry-constraint render per class
# ─────────────────────────────────────────────────────────

def _retry_constraint_fabricated_combatant(detected_phrase: str,
                                            canonical_names: list) -> str:
    canon_list = ', '.join(sorted(canonical_names)[:10]) or '(none loaded)'
    return (
        f"Class: {VIOLATION_FABRICATED_COMBATANT}\n"
        f"Detected: {detected_phrase!r}\n\n"
        "You MUST regenerate. The retry MUST:\n"
        "  - Describe combat using ONLY the creatures listed in "
        "=== COMBAT REDIRECT === or === ARBITRATION RESULT ===.\n"
        "  - Do NOT introduce new creatures into combat. Fabricated "
        "combatants (entities not in the canonical NPC or combatant lists) "
        "must not appear as combat participants.\n"
        f"  Canonical names on record: {canon_list}"
    )


def _retry_constraint_verdict_contradiction(detected_phrase: str,
                                             verdict_summary: str) -> str:
    return (
        f"Class: {VIOLATION_VERDICT_CONTRADICTION}\n"
        f"Detected: {detected_phrase!r}\n\n"
        "You MUST regenerate. The retry MUST:\n"
        f"  - Honor the binding verdict above: {verdict_summary}\n"
        "  - Narrate ONLY the verdict outcome. Do NOT narrate a "
        "contradicting outcome, a partial reversal, or an ambiguous result.\n"
        "  - If the verdict is FAILURE, narrate failure only. If SUCCESS, "
        "narrate success only. If REFUSED, narrate non-occurrence only."
    )


def _retry_constraint_state_mutation(detected_phrase: str) -> str:
    return (
        f"Class: {VIOLATION_STATE_MUTATION_CLAIM}\n"
        f"Detected: {detected_phrase!r}\n\n"
        "You MUST regenerate. The retry MUST:\n"
        "  - Describe consequences RHETORICALLY — never assert mechanical "
        "numbers (HP, damage dice, XP, death). Avrae owns those numbers.\n"
        "  - Use rhetorical forms: 'the goblin staggers, blood welling,' not "
        "'the goblin takes 12 damage.'\n"
        "  - Never declare a creature dead — describe them as incapacitated, "
        "collapsed, or staggered. Avrae's tracker owns death state."
    )


def _retry_constraint_roll_outcome_drift(detected_phrase: str, result) -> str:
    """Ship 1 (S34) retry constraint for ROLL_OUTCOME_DRIFT.

    `result` is an orchestration.ResolutionResult. The final sentence —
    'player's self-report is irrelevant' — targets the F-45 failure shape
    directly: the LLM was drifting because it was responding to the player's
    'I passed' text. Make the structural reason explicit on retry.
    """
    outcome = 'PASSED' if result.passed else 'FAILED'
    outcome_word = 'success' if result.passed else 'failure'
    opposite_word = 'failure' if result.passed else 'success'
    return (
        f"Class: {VIOLATION_ROLL_OUTCOME_DRIFT}\n"
        f"Detected: {detected_phrase!r}\n\n"
        "You MUST regenerate. The retry MUST:\n"
        f"  - Honor the binding resolution: {result.actor} "
        f"{result.skill_or_save} {result.check_kind} DC {result.dc}, "
        f"rolled {result.roll_total}, outcome {outcome}.\n"
        f"  - Narrate ONLY the {outcome_word} outcome. Do NOT narrate "
        f"{opposite_word}, partial reversal, or alternative interpretation.\n"
        "  - The roll resolution is engine-computed and binding. The "
        "player's self-report is irrelevant. The DC was set at directive emit."
    )


def _retry_constraint_actor_omission(missing_actor: str, category: str) -> str:
    return (
        f"Class: {VIOLATION_ACTOR_OMISSION}\n"
        f"Detected: {missing_actor!r} (verdict: {category}) absent from narration\n\n"
        "You MUST regenerate. The retry MUST:\n"
        f"  - Address {missing_actor!r} explicitly by name. Their verdict "
        f"({category}) is binding and must be honored in this narration.\n"
        "  - Every non-FREE actor in === ARBITRATION RESULT === must be "
        "named at least once in the response.\n"
        "  - Do not address them only by pronoun — use the character name."
    )


# ─────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────

def verify_narration(narration_text: str,
                     arbitration_result,
                     scene_state: Optional[dict] = None,
                     combatants: Optional[list] = None,
                     npcs_canonical: Optional[list] = None,
                     resolution_result=None) -> VerificationResult:
    """Verify LLM-produced narration against the bound arbitration result
    and canonical-state sources.

    Returns VerificationResult. Caller wraps in try/except (Doctrine §59);
    on any exception, treat as passed=True and post the original narration
    (fail-open). Never blocks narration entirely.

    Detection order (first violation wins) — Ship 1 (S34) extends with
    ROLL_OUTCOME_DRIFT in slot 4 (per RESOLUTION_BINDING_SPEC.md §8.4 —
    structural-impossibility classes before behavioral-drift classes;
    ACTOR_OMISSION stays last as the broadest catch):
      1. FABRICATED_COMBATANT
      2. VERDICT_CONTRADICTION
      3. STATE_MUTATION_CLAIM
      4. ROLL_OUTCOME_DRIFT
      5. ACTOR_OMISSION

    `resolution_result` is an orchestration.ResolutionResult (Ship 1) — when
    populated, drives the ROLL_OUTCOME_DRIFT pass. None on player-input-path
    turns where the matcher did not auto-fire (arbitration owns the binding).
    """
    signals: dict = {
        'passed': 1,
        'violation_class': '',
        'detected_phrase': '',
        'retry_constraint_chars': 0,
        'narration_chars': len(narration_text or ''),
        'canonical_combatants_count': 0,
    }

    if not VERIFICATION_ENABLED:
        return VerificationResult(passed=True, signals=signals)

    text = (narration_text or '').strip()
    if not text:
        # Empty narration — treat as passed; the empty-narration diagnostic
        # in dm_respond handles this case separately.
        return VerificationResult(passed=True, signals=signals)

    # Resolve campaign_id from arbitration_result or scene_state
    campaign_id = None
    try:
        if scene_state:
            campaign_id = scene_state.get('campaign_id')
        if campaign_id is None and arbitration_result is not None:
            # ArbitrationResult doesn't carry campaign_id directly; fall back
            campaign_id = getattr(arbitration_result, 'campaign_id', None)
    except Exception:
        pass

    # Build canonical set for fabrication detection
    actor_names = []
    if arbitration_result is not None:
        try:
            actor_names = list(arbitration_result.actor_order or [])
        except Exception:
            pass

    canonical_set = _build_canonical_set(
        campaign_id or 0,
        combatants=combatants,
        npcs_canonical=npcs_canonical,
        extra_names=actor_names,
    )
    signals['canonical_combatants_count'] = len(canonical_set)

    # ── 1. FABRICATED_COMBATANT ──────────────────────────────────────
    candidates = _extract_named_candidates(text)
    fabricated = []
    for candidate in candidates:
        if not _name_is_canonical(candidate, canonical_set):
            if _has_combat_verb_nearby(text, candidate):
                fabricated.append(candidate)

    if fabricated:
        detected_phrase = f"{fabricated[0]} (+ combat verb)"[:140]
        retry = _retry_constraint_fabricated_combatant(
            detected_phrase, sorted(canonical_set)
        )
        signals.update({
            'passed': 0,
            'violation_class': VIOLATION_FABRICATED_COMBATANT,
            'detected_phrase': detected_phrase,
            'retry_constraint_chars': len(retry),
        })
        return VerificationResult(
            passed=False,
            violation_class=VIOLATION_FABRICATED_COMBATANT,
            detected_phrase=detected_phrase,
            retry_constraint=retry,
            canonical_combatants=sorted(canonical_set),
            fabricated_names=fabricated,
            signals=signals,
        )

    # ── 2. VERDICT_CONTRADICTION ──────────────────────────────────────
    if arbitration_result is not None:
        try:
            for verdict in (arbitration_result.verdicts or []):
                cat = getattr(verdict, 'category', '')
                allowed = getattr(verdict, 'allowed', True)
                success = getattr(verdict, 'success', None)
                refusal_kind = getattr(verdict, 'refusal_kind', '')

                contradiction_phrase = None

                # CHECK failed → narration describes success
                if cat == 'check' and success is False:
                    for pat in _CHECK_FAILURE_SUCCESS_PHRASES:
                        m = pat.search(text)
                        if m:
                            contradiction_phrase = text[
                                max(0, m.start()-20):m.end()+20
                            ][:140]
                            break

                # CHECK succeeded → narration describes failure
                elif cat == 'check' and success is True:
                    for pat in _CHECK_SUCCESS_FAILURE_PHRASES:
                        m = pat.search(text)
                        if m:
                            contradiction_phrase = text[
                                max(0, m.start()-20):m.end()+20
                            ][:140]
                            break

                # CAPABILITY refused → narration says it worked
                elif cat == 'capability' and not allowed and refusal_kind == 'capability':
                    for pat in _CAPABILITY_REFUSED_SUCCESS_PHRASES:
                        m = pat.search(text)
                        if m:
                            contradiction_phrase = text[
                                max(0, m.start()-20):m.end()+20
                            ][:140]
                            break

                # COMBAT inactive → narration says damage landed
                elif cat == 'combat' and not allowed and refusal_kind == 'combat_inactive':
                    for pat in _COMBAT_INACTIVE_DAMAGE_PHRASES:
                        m = pat.search(text)
                        if m:
                            contradiction_phrase = text[
                                max(0, m.start()-20):m.end()+20
                            ][:140]
                            break

                if contradiction_phrase:
                    skill = getattr(verdict, 'skill', '') or ''
                    dc = getattr(verdict, 'dc', None)
                    verdict_summary = (
                        f"{cat.upper()}"
                        + (f" {skill} DC {dc}" if skill and dc else "")
                        + (f" success={success}" if success is not None else "")
                        + (f" refusal={refusal_kind}" if refusal_kind else "")
                    )
                    retry = _retry_constraint_verdict_contradiction(
                        contradiction_phrase, verdict_summary
                    )
                    signals.update({
                        'passed': 0,
                        'violation_class': VIOLATION_VERDICT_CONTRADICTION,
                        'detected_phrase': contradiction_phrase,
                        'retry_constraint_chars': len(retry),
                    })
                    return VerificationResult(
                        passed=False,
                        violation_class=VIOLATION_VERDICT_CONTRADICTION,
                        detected_phrase=contradiction_phrase,
                        retry_constraint=retry,
                        signals=signals,
                    )
        except Exception:
            # Verdict iteration failure is soft — do not block narration.
            pass

    # ── 3. STATE_MUTATION_CLAIM ──────────────────────────────────────
    for pat in _STATE_MUTATION_PATTERNS:
        m = pat.search(text)
        if m:
            detected_phrase = text[max(0, m.start()-10):m.end()+10][:140]
            retry = _retry_constraint_state_mutation(detected_phrase)
            signals.update({
                'passed': 0,
                'violation_class': VIOLATION_STATE_MUTATION_CLAIM,
                'detected_phrase': detected_phrase,
                'retry_constraint_chars': len(retry),
            })
            return VerificationResult(
                passed=False,
                violation_class=VIOLATION_STATE_MUTATION_CLAIM,
                detected_phrase=detected_phrase,
                retry_constraint=retry,
                signals=signals,
            )

    # ── 4. ROLL_OUTCOME_DRIFT ────────────────────────────────────────
    # Ship 1 (S34) — engine-bound resolution surface. Mirrors
    # VERDICT_CONTRADICTION's check-success-on-failure / check-failure-on-
    # success detection but compares against the ResolutionResult populated
    # by the matcher's auto-fire path (RESOLUTION_BINDING_SPEC.md §8).
    # Vocabulary reuse with VERDICT_CONTRADICTION per §11.12 lock.
    if resolution_result is not None:
        try:
            passed_flag = getattr(resolution_result, 'passed', None)
            if passed_flag is False:
                phrase_patterns = _CHECK_FAILURE_SUCCESS_PHRASES
            elif passed_flag is True:
                phrase_patterns = _CHECK_SUCCESS_FAILURE_PHRASES
            else:
                phrase_patterns = []
            for pat in phrase_patterns:
                m = pat.search(text)
                if m:
                    detected_phrase = text[
                        max(0, m.start()-20):m.end()+20
                    ][:140]
                    retry = _retry_constraint_roll_outcome_drift(
                        detected_phrase, resolution_result
                    )
                    signals.update({
                        'passed': 0,
                        'violation_class': VIOLATION_ROLL_OUTCOME_DRIFT,
                        'detected_phrase': detected_phrase,
                        'retry_constraint_chars': len(retry),
                    })
                    return VerificationResult(
                        passed=False,
                        violation_class=VIOLATION_ROLL_OUTCOME_DRIFT,
                        detected_phrase=detected_phrase,
                        retry_constraint=retry,
                        signals=signals,
                    )
        except Exception:
            # Soft-fail: ROLL_OUTCOME_DRIFT detection error never blocks narration.
            pass

    # ── 5. ACTOR_OMISSION ────────────────────────────────────────────
    # Per §11.M, §11.Q: actor_order contains CHARACTER NAMES (not Discord
    # usernames). Substring scan case-insensitive. Skip FREE actors and
    # cache-miss actors (no_character_context).
    if arbitration_result is not None:
        try:
            verdicts = list(arbitration_result.verdicts or [])
            actor_order = list(arbitration_result.actor_order or [])
            text_lower = text.lower()

            for actor_name, verdict in zip(actor_order, verdicts):
                cat = getattr(verdict, 'category', 'free')
                refusal_kind = getattr(verdict, 'refusal_kind', '')

                # Skip FREE verdicts — no binding constraint
                if cat in ('free', 'fallback'):
                    continue

                # Skip cache-miss actors — no binding constraint was issued
                if refusal_kind == 'no_character_context':
                    continue

                # Substring check: character name must appear in narration
                if actor_name and actor_name.lower() not in text_lower:
                    detected_phrase = (
                        f"{actor_name} (verdict: {cat}) absent from narration"
                    )[:140]
                    retry = _retry_constraint_actor_omission(actor_name, cat)
                    signals.update({
                        'passed': 0,
                        'violation_class': VIOLATION_ACTOR_OMISSION,
                        'detected_phrase': detected_phrase,
                        'retry_constraint_chars': len(retry),
                    })
                    return VerificationResult(
                        passed=False,
                        violation_class=VIOLATION_ACTOR_OMISSION,
                        detected_phrase=detected_phrase,
                        retry_constraint=retry,
                        signals=signals,
                    )
        except Exception:
            pass

    # All checks passed
    return VerificationResult(passed=True, signals=signals)


# ─────────────────────────────────────────────────────────
# Retry-prompt builder
# ─────────────────────────────────────────────────────────

def build_verification_retry_prefix(result: VerificationResult) -> str:
    """Build the === VERIFICATION FAILED === prefix to prepend to the
    system prompt on a retry call (§6.2). Returns empty string when
    result.passed is True or retry_constraint is empty."""
    if result.passed or not result.retry_constraint:
        return ''
    return (
        "=== VERIFICATION FAILED ===\n"
        "The previous narration violated a binding constraint:\n"
        f"  {result.retry_constraint}\n\n"
        "This is the second pass. If you violate again, your output will be "
        "replaced with a deterministic placeholder honoring the verdict.\n"
        "=== END VERIFICATION FAILED ===\n\n"
    )


# ─────────────────────────────────────────────────────────
# Escalation placeholder builder (§6.3, per-category branches)
# ─────────────────────────────────────────────────────────

def build_escalation_placeholder(arbitration_result,
                                  failed_violation_class: str = '',
                                  resolution_result=None) -> str:
    """Build the deterministic per-category escalation narration when both
    LLM passes fail verification. One block per non-FREE actor in priority
    order. Terse, mechanical, honest — never blocks posting.

    Ship 1 (S34) extension: when the failed class is ROLL_OUTCOME_DRIFT
    and a resolution_result was supplied, emit a deterministic resolution
    placeholder mirroring the existing CHECK-class block shape
    (RESOLUTION_BINDING_SPEC.md §8.7)."""
    if failed_violation_class == VIOLATION_ROLL_OUTCOME_DRIFT and resolution_result:
        try:
            outcome = 'Success' if resolution_result.passed else 'Failure'
            tail = ('The attempt succeeds.' if resolution_result.passed
                    else 'The attempt fails.')
            return (
                f"{resolution_result.actor} — "
                f"{resolution_result.skill_or_save.replace('_', ' ').title()} "
                f"{resolution_result.check_kind} at DC {resolution_result.dc} "
                f"(rolled {resolution_result.roll_total}). "
                f"Result: {outcome}. {tail}"
            )
        except Exception as e:
            return f"[Resolution escalation placeholder error: {e}]"

    if arbitration_result is None:
        return "[Narration unavailable — arbitration error.]"

    blocks = []
    try:
        for actor_name, verdict in zip(
            arbitration_result.actor_order or [],
            arbitration_result.verdicts or [],
        ):
            cat = getattr(verdict, 'category', 'free')
            allowed = getattr(verdict, 'allowed', True)
            refusal_kind = getattr(verdict, 'refusal_kind', '')
            skill = getattr(verdict, 'skill', '') or ''
            dc = getattr(verdict, 'dc', None)
            success = getattr(verdict, 'success', None)

            if cat in ('free', 'fallback'):
                # FREE_ACTION anomaly case — should not escalate, but guard it
                blocks.append(
                    f"{actor_name}'s action passes without resolution. "
                    f"(See logs: [VERIFICATION_ANOMALY] — "
                    f"escalation reached FREE verdict class={failed_violation_class})"
                )
                continue

            if cat == 'check':
                if success is None:
                    blocks.append(
                        f"{actor_name} — {skill.replace('_',' ').title()} check"
                        + (f" at DC {dc}" if dc else "") + ". Roll pending."
                    )
                else:
                    outcome = 'Success' if success else 'Failure'
                    rolled = getattr(verdict, 'roll_value', None)
                    roll_str = f" (rolled {rolled})" if rolled is not None else ""
                    blocks.append(
                        f"{actor_name} — {skill.replace('_',' ').title()} check"
                        + (f" at DC {dc}" if dc else "")
                        + f"{roll_str}. Result: {outcome}."
                        + (" The attempt succeeds." if success
                           else " The attempt fails.")
                    )

            elif cat == 'capability' and not allowed:
                cap_name = refusal_kind or 'capability'
                blocks.append(
                    f"{actor_name} attempts {cap_name}. "
                    "The capability does not apply. "
                    "The words don't shape. Nothing happens."
                )

            elif cat == 'combat' and not allowed:
                action_summary = getattr(verdict, 'narration_constraint', '')
                action_summary = action_summary[:60] if action_summary else 'combat action'
                blocks.append(
                    f"{actor_name} attempts a {action_summary}. "
                    "Combat is not active. "
                    "Use !init begin to start combat, then surface the action through Avrae."
                )

            elif cat == 'world_boundary':
                blocks.append(
                    f"{actor_name}'s attempt does not resolve. "
                    "The world reasserts. The action does not occur."
                )

            else:
                # Generic non-FREE verdict
                blocks.append(
                    f"{actor_name} — verdict: {cat.upper()}"
                    + (" allowed" if allowed else " refused")
                    + "."
                )

    except Exception as e:
        return f"[Escalation placeholder error: {e}]"

    return "\n\n".join(blocks) if blocks else "[No binding verdicts to surface.]"


# ─────────────────────────────────────────────────────────
# Log line helper
# ─────────────────────────────────────────────────────────

def verification_log_summary(campaign_id: int,
                              result: VerificationResult,
                              retry_fired: bool = False,
                              retry_result: Optional[VerificationResult] = None,
                              escalated: bool = False) -> str:
    """Compact log line per Doctrine §59 / spec §6.4. Always-fire."""
    passed = 1 if result.passed else 0
    vclass = result.violation_class or 'none'
    detected = result.detected_phrase or ''
    retry_passed = '-'
    if retry_fired and retry_result is not None:
        retry_passed = '1' if retry_result.passed else '0'
    sig = result.signals or {}
    narration_chars = sig.get('narration_chars', 0)
    canonical_count = sig.get('canonical_combatants_count', 0)
    return (
        f"verification: campaign={campaign_id} "
        f"passed={passed} "
        f"violation_class={vclass} "
        f"detected={detected[:140]!r} "
        f"retry_fired={1 if retry_fired else 0} "
        f"retry_passed={retry_passed} "
        f"escalated={1 if escalated else 0} "
        f"narration_chars={narration_chars} "
        f"canonical_combatants_count={canonical_count}"
    )
