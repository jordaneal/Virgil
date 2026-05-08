"""Calibration + unit tests for check_action_capability (S9 v1).

Spec source: ROADMAP S9, Session 13 design review (locked-spec dictum:
strict full-string equality, fix data not logic), VIRGIL_MASTER §
"Architectural Invariants" → partial-projections principle.

Scope:
  - Weapon grounding only (spells, items, inventory deferred).
  - Validates "does the bound character have an attack entry that
    EXACTLY (lowercased) matches a noun in the claimed weapon family,
    OR a skeleton-declared specific item that does the same?"
  - Does NOT decide whether to roll, what damage, or any mechanic.
    That's still Avrae's territory.

Detection requires BOTH:
  1. A capability-invocation verb (draw, ready, raise, nock, aim,
     unsheathe, brandish, grab, pull, wield, lift, hoist, equip, use)
     used as the action's main verb.
  2. A weapon-family noun in proximity that matches one of the
     enumerated WEAPON_CAPABILITIES categories (sword/axe/dagger/...).

3-state verdict (CapabilityVerdict enum):
  - CONFIRMED: claim matches Avrae attack OR skeleton-declared
    capability. Strict full-string equality on the lowercased noun
    against the family alias list.
  - VALID_BUT_UNCONFIGURED: claim detected; no Avrae match, no skeleton
    confirmation, no explicit contradiction. The DEFAULT for unmatched
    claims under partial projections — absence of data is NOT evidence
    of absence.
  - INVALID: explicit contradiction from an authoritative source. v1
    has NO PRODUCER for this verdict; the enum slot is reserved for
    future DDB ingestion / skeleton-deny-list extensions. Tests that
    cover INVALID-rendering must construct a CapabilityDecision
    manually rather than calling check_action_capability.

Strict-equality consequences (per Session 13 locked spec):
  - 'Longsword' in attacks → 'sword' claim CONFIRMED (it's an alias).
  - '+1 Longsword' in attacks → 'sword' claim VALID_BUT_UNCONFIGURED
    (the prefixed form is NOT in the alias set; the fix is DATA — add
    aliases to WEAPON_CAPABILITIES — not normalization LOGIC).
  - 'Unarmed Strike' in attacks → 'sword' claim VALID_BUT_UNCONFIGURED
    (no contradiction signal in v1; INVALID is reserved).

Mode-independent: capability claims occur in any mode. "I raise my
staff toward the stars" in social mode still grounds against staff
in attacks. Don't tie this to combat mode.

Six categories of calibration:
  1. CONFIRMED — Avrae attack alias-matches the claim
  2. VALID_BUT_UNCONFIGURED — claim detected, no source confirms
  3. False-positive bait — verb-then-noun phrases that aren't claims
  4. No-claim baseline — actions that should silently pass through
  5. Mode-independence — same claim across modes behaves the same
  6. Avrae attack-name format under strict equality — prefixes/suffixes
     that pre-Session-13 fuzzy match would have caught are now
     VALID_BUT_UNCONFIGURED. This documents the strict-equality choice.
"""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import dnd_orchestration as orch  # noqa: E402
from dnd_orchestration import CapabilityVerdict  # noqa: E402


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _ctx(name='TestChar', attacks=None, **kwargs):
    """Build a minimal CharacterContext for testing."""
    return orch.CharacterContext(
        name=name,
        attacks=attacks or [],
        **kwargs,
    )


# Shorthand for parametrize IDs / readability
CONFIRMED = CapabilityVerdict.CONFIRMED
VBU = CapabilityVerdict.VALID_BUT_UNCONFIGURED


# ─── Calibration ──────────────────────────────────────────────────────────────
# Each case: (text, attacks_list, expected_needs_check, expected_verdict,
#            expected_category_or_None, rationale)

CALIBRATION = [
    # ── 1. CONFIRMED — Avrae attack alias-matches the claim ───────────────
    ("I draw my sword",         ['Longsword'],         True, CONFIRMED, 'sword',
     "exact alias: 'longsword' is in the sword family aliases"),
    ("I unsheathe my dagger",   ['Dagger'],            True, CONFIRMED, 'dagger',
     "exact match dagger"),
    ("I ready my bow",          ['Shortbow'],          True, CONFIRMED, 'bow',
     "'shortbow' is in the bow family aliases"),
    # 'arrow' maps to category='bow' for attribution purposes but is treated
    # as a specific noun for matching (it's NOT a WEAPON_CAPABILITIES key).
    # Per locked spec: specific noun → exact-equality match only. Avrae attacks
    # almost never contain 'arrow' literally, so this almost always returns
    # VBU. Documents the intentional v1 behavior.
    ("I nock an arrow",         ['Longbow', 'Dagger'], True, VBU, 'bow',
     "'arrow' is specific-noun under locked spec; 'longbow' isn't 'arrow' exactly"),
    ("I raise my staff toward the stars", ['Quarterstaff'], True, CONFIRMED, 'staff',
     "'quarterstaff' is in the staff family aliases"),
    ("I brandish my axe",       ['Battleaxe'],         True, CONFIRMED, 'axe',
     "'battleaxe' is in the axe family aliases"),
    ("I grab my mace",          ['Mace'],              True, CONFIRMED, 'mace',
     "exact match mace"),
    ("I pull my dagger",        ['Shortsword', 'Dagger'], True, CONFIRMED, 'dagger',
     "multi-weapon character, dagger present in attacks"),

    # ── 2. VALID_BUT_UNCONFIGURED — claim detected, no source confirms ────
    # Per partial-projections principle, these are NOT INVALID. INVALID
    # has no producer in v1; the safe default for unmatched claims is
    # VALID_BUT_UNCONFIGURED (deferring to the DM's external DDB view).
    ("I draw my sword",         ['Unarmed Strike'],    True, VBU, 'sword',
     "rogue with only Unarmed Strike — no sword attack — VBU not INVALID"),
    ("I aim my crossbow",       ['Quarterstaff'],      True, VBU, 'crossbow',
     "wizard with quarterstaff claims crossbow — no match"),
    ("I ready my bow",          ['Mace'],              True, VBU, 'bow',
     "cleric with mace claims bow — no match"),
    ("I unsheathe my rapier",   ['Unarmed Strike'],    True, VBU, 'sword',
     "specific weapon (rapier→sword family) without it"),

    # ── 3. False-positive bait — must NOT trigger needs_check ─────────────
    # Verbs and nouns that look weapony but aren't capability invocations.
    ("I draw the curtains",     ['Longsword'],         False, VBU, None,
     "'draw' + 'curtains' is not a weapon noun"),
    ("I draw near the throne",  ['Longsword'],         False, VBU, None,
     "'draw near' is movement idiom, no weapon noun"),
    ("I pull open the door",    ['Longsword'],         False, VBU, None,
     "'pull' but with 'door' not weapon"),
    ("I raise my voice in protest", ['Longsword'],     False, VBU, None,
     "'raise voice' is rhetorical idiom"),
    ("I raise concern about the plan", ['Longsword'],  False, VBU, None,
     "'raise concern' is idiomatic, not a claim"),
    ("I sword fight in the tournament", ['Longsword'], False, VBU, None,
     "'sword fight' compound noun, no invocation verb"),
    ("I draw a circle on the floor", ['Longsword'],    False, VBU, None,
     "'draw a circle' is sketching, not weapon"),
    ("I draw a deep breath",    ['Longsword'],         False, VBU, None,
     "'draw a breath' is idiom"),
    ("I bow before the king",   ['Longbow'],           False, VBU, None,
     "'bow' as verb (genuflect), not noun"),

    # ── 4. No-claim baseline ──────────────────────────────────────────────
    # Actions with no capability claim at all. Must silently pass.
    ("I look around the room",  ['Longsword'],         False, VBU, None,
     "no claim, no directive"),
    ("I attack the goblin",     ['Longsword'],         False, VBU, None,
     "generic combat verb, no specific weapon claim — Avrae handles"),
    ("I cast fireball",         ['Longsword'],         False, VBU, None,
     "spell claim, out of scope (deferred to S9.x)"),
    ("I tell the bartender about the rumor", ['Longsword'], False, VBU, None,
     "social action"),
    ("I search the chest for traps", ['Longsword'],    False, VBU, None,
     "exploration action"),
    ("",                        ['Longsword'],         False, VBU, None,
     "empty input"),

    # ── 5. Mode-independence ──────────────────────────────────────────────
    # The same claim grounds the same way regardless of scene mode.
    # (Mode isn't a parameter of check_action_capability — listed here
    # to document the architectural intent.)
    ("I raise my staff toward the stars", ['Quarterstaff'], True, CONFIRMED, 'staff',
     "social-mode capability claim still grounds"),
    ("I draw my sword", ['Longsword'], True, CONFIRMED, 'sword',
     "combat-mode capability claim grounds the same way"),

    # ── 6. Avrae attack-name format under strict equality ─────────────────
    # Pre-Session-13 these would have matched via substring. Session 13
    # locked strict equality; the FIX for prefixed/suffixed forms is to
    # add aliases to WEAPON_CAPABILITIES (data, not logic). Until then,
    # they correctly classify as VALID_BUT_UNCONFIGURED — partial-projection
    # safety.
    ("I draw my sword",         ['+1 Longsword'],          True, VBU, 'sword',
     "'+1 longsword' not in alias set — strict equality, VBU per spec"),
    ("I unsheathe my rapier",   ['Silvered Rapier'],       True, VBU, 'sword',
     "'silvered rapier' not in alias set"),
    ("I draw my sword",         ['Moon-Touched Shortsword'], True, VBU, 'sword',
     "'moon-touched shortsword' not in alias set"),
    ("I aim my crossbow",       ['Light Crossbow +1'],     True, VBU, 'crossbow',
     "'light crossbow +1' not in alias set"),

    # ── 7. Edge cases ─────────────────────────────────────────────────────
    ("I draw my sword",         [],                        True, VBU, 'sword',
     "character with empty attacks list — VBU not CONFIRMED"),
    ("I draw my sword",         ['Unarmed Strike', 'Longsword'], True, CONFIRMED, 'sword',
     "multiple attacks, one alias-matches → CONFIRMED"),

    # ── 8. New verbs (Session 15) — equip/use ─────────────────────────────
    ("I equip my sword",        ['Longsword'],         True, CONFIRMED, 'sword',
     "'equip' verb (Session 15) + alias match"),
    ("I use my dagger",         ['Dagger'],            True, CONFIRMED, 'dagger',
     "'use' verb (Session 15) + exact match"),
    ("I use the door",          ['Longsword'],         False, VBU, None,
     "'use' + non-weapon noun ('door') — no claim"),
]


# ─── Tests ────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "text,attacks,needs_check,verdict,category,rationale",
    CALIBRATION,
    ids=[f"{i:02d}_{c[5][:50]}" for i, c in enumerate(CALIBRATION)]
)
def test_calibration(text, attacks, needs_check, verdict, category, rationale):
    ctx = _ctx(attacks=attacks)
    decision = orch.check_action_capability(text, ctx)
    assert decision.needs_check == needs_check, (
        f"\n  text:           {text!r}"
        f"\n  attacks:        {attacks}"
        f"\n  expected needs_check: {needs_check}"
        f"\n  actual needs_check:   {decision.needs_check}"
        f"\n  reason:         {rationale}"
    )
    if needs_check:
        assert decision.verdict is verdict, (
            f"\n  text:           {text!r}"
            f"\n  attacks:        {attacks}"
            f"\n  expected verdict: {verdict}"
            f"\n  actual verdict:   {decision.verdict}"
            f"\n  reason:         {rationale}"
        )
        assert decision.capability == category, (
            f"\n  text:           {text!r}"
            f"\n  expected category: {category}"
            f"\n  actual category:   {decision.capability}"
        )


# ─── Direct API tests ─────────────────────────────────────────────────────────

def test_decision_dataclass_shape():
    """CapabilityDecision has the documented v1 fields."""
    ctx = _ctx(attacks=['Longsword'])
    d = orch.check_action_capability("I draw my sword", ctx)
    assert hasattr(d, 'needs_check')
    assert hasattr(d, 'verdict')
    assert hasattr(d, 'capability')
    assert hasattr(d, 'matched_attack')
    assert hasattr(d, 'reason')
    # Old binary 'has_capability' field was removed in S9 v1; verdict replaces it
    assert not hasattr(d, 'has_capability'), (
        "Stale field: S9 v1 replaced binary has_capability with the "
        "3-state verdict enum. Test or code is out of date."
    )


def test_verdict_enum_values():
    """CapabilityVerdict has exactly three v1 members."""
    members = {v.name for v in CapabilityVerdict}
    assert members == {'CONFIRMED', 'VALID_BUT_UNCONFIGURED', 'INVALID'}, (
        f"Unexpected verdict enum members: {members}"
    )


def test_directive_silent_when_no_check():
    """No claim detected → empty directive (silent in 99% of turns)."""
    ctx = _ctx(attacks=['Longsword'])
    d = orch.check_action_capability("I look around", ctx)
    assert d.to_prompt_directive() == ''


def test_directive_silent_when_confirmed():
    """CONFIRMED → silent. The DM doesn't need a constraint when the
    claim is grounded; narration proceeds normally."""
    ctx = _ctx(attacks=['Longsword'])
    d = orch.check_action_capability("I draw my sword", ctx)
    assert d.verdict is CapabilityVerdict.CONFIRMED
    assert d.to_prompt_directive() == ''


def test_directive_speaks_on_valid_but_unconfigured():
    """VALID_BUT_UNCONFIGURED → soft UNVERIFIED annotation. Locked
    wording per Session 13: explicitly mark as UNVERIFIED, instruct the
    DM not to treat the item as established equipment in subsequent
    narration. Non-blocking; informative."""
    ctx = _ctx(attacks=['Unarmed Strike'])
    d = orch.check_action_capability("I draw my sword", ctx)
    assert d.verdict is CapabilityVerdict.VALID_BUT_UNCONFIGURED
    out = d.to_prompt_directive()
    assert out != ''
    # Locked-wording invariants from Session 13
    assert 'UNVERIFIED' in out, "Must mark item as UNVERIFIED"
    assert 'established equipment' in out.lower(), (
        "Must instruct against treating as established equipment"
    )


def test_directive_invalid_renders_anti_fabrication():
    """INVALID has no producer in v1 — the renderer is exercised by
    constructing a decision manually. This test guards the renderer
    contract for future producers (DDB ingestion, deny-lists)."""
    d = orch.CapabilityDecision(
        needs_check=True,
        verdict=CapabilityVerdict.INVALID,
        capability='sword',
        matched_attack='',
        reason='manually constructed for renderer test',
    )
    out = d.to_prompt_directive()
    assert out != ''
    # Anti-fabrication invariant: must instruct against narrating success as fact
    assert 'do not narrate' in out.lower() or 'not narrate' in out.lower()
    # Soft-alternative invariant: must allow improvised/unarmed reinterpretation
    assert ('improvis' in out.lower()
            or 'unarmed' in out.lower()
            or 'clarif' in out.lower())


def test_matched_attack_populated_on_confirmed():
    """When CONFIRMED, matched_attack identifies which attack entry
    satisfied the claim."""
    ctx = _ctx(attacks=['Unarmed Strike', 'Longsword'])
    d = orch.check_action_capability("I draw my sword", ctx)
    assert d.verdict is CapabilityVerdict.CONFIRMED
    assert 'longsword' in d.matched_attack.lower()


def test_matched_attack_empty_on_unconfigured():
    """When VALID_BUT_UNCONFIGURED, no match exists, so matched_attack
    is empty. (CONFIRMED via skeleton sets matched_attack to a
    'skeleton-declared:' prefix; tested separately if/when skeleton
    plumbing gains direct test coverage.)"""
    ctx = _ctx(attacks=['Unarmed Strike'])
    d = orch.check_action_capability("I draw my sword", ctx)
    assert d.verdict is CapabilityVerdict.VALID_BUT_UNCONFIGURED
    assert d.matched_attack == ''


def test_capability_check_does_not_depend_on_mode():
    """Architectural intent: capability grounding is mode-independent.
    The function takes (text, character, skeleton_capabilities=None) only.
    No mode parameter."""
    import inspect
    sig = inspect.signature(orch.check_action_capability)
    params = list(sig.parameters.keys())
    assert 'mode' not in params, (
        "check_action_capability must not take a mode parameter — "
        "capability is mode-independent. mode-aware behavior belongs "
        "in classify_action_intent / should_call_roll, not here."
    )


def test_skeleton_capabilities_param_exists():
    """skeleton_capabilities is the v1 hint layer (Session 13). It's
    optional (default None) so callers without skeleton plumbing still
    work. When provided, it's a dict[str, set[str]] mapping character
    display name → set of weapon-family categories."""
    import inspect
    sig = inspect.signature(orch.check_action_capability)
    assert 'skeleton_capabilities' in sig.parameters
    # Default should be None so omitting it still works
    p = sig.parameters['skeleton_capabilities']
    assert p.default is None


def test_skeleton_promotes_to_confirmed():
    """When Avrae attacks don't match but skeleton declares the
    capability, verdict upgrades from VALID_BUT_UNCONFIGURED to
    CONFIRMED (per Session 13 — skeleton is a positive-only HINT
    layer; declarations CONFIRM presence, never CONTRADICT absence).

    Skeleton dict keys are character names; values are sets of
    weapon-family categories (already lowercased by skeleton_loader)."""
    ctx = _ctx(name='Donovan Ruby', attacks=['Unarmed Strike'])
    skeleton = {'Donovan Ruby': {'shortsword', 'shortbow', 'dagger'}}

    d = orch.check_action_capability(
        "I draw my dagger", ctx, skeleton_capabilities=skeleton
    )
    assert d.verdict is CapabilityVerdict.CONFIRMED, (
        "Skeleton-declared 'dagger' should upgrade verdict to CONFIRMED"
    )
    assert 'skeleton' in d.matched_attack.lower(), (
        "matched_attack should indicate the skeleton source"
    )


def test_skeleton_does_not_demote_unmatched():
    """A skeleton entry that DOESN'T list the claimed item leaves the
    verdict at VALID_BUT_UNCONFIGURED — it does NOT set INVALID.
    Skeleton hints are positive-only."""
    ctx = _ctx(name='Donovan Ruby', attacks=['Unarmed Strike'])
    skeleton = {'Donovan Ruby': {'shortsword'}}  # no 'sword' claim source

    # Player claims 'mace' — not in attacks, not in skeleton
    d = orch.check_action_capability(
        "I grab my mace", ctx, skeleton_capabilities=skeleton
    )
    assert d.verdict is CapabilityVerdict.VALID_BUT_UNCONFIGURED, (
        "Missing skeleton entry must NOT downgrade to INVALID — "
        "skeleton is positive-only per the partial-projections principle"
    )


# ─── Weapon family completeness ───────────────────────────────────────────────

def test_all_v1_categories_present():
    """All 10 v1 weapon families enumerated."""
    expected = {'sword', 'axe', 'dagger', 'mace', 'hammer',
                'bow', 'crossbow', 'spear', 'staff', 'whip'}
    actual = {wc.category for wc in orch.WEAPON_CAPABILITIES}
    assert expected.issubset(actual), f"missing categories: {expected - actual}"


def test_weapon_capability_dataclass_shape():
    """WeaponCapability has category and aliases."""
    wc = orch.WEAPON_CAPABILITIES[0]
    assert hasattr(wc, 'category')
    assert hasattr(wc, 'aliases')
    assert isinstance(wc.aliases, tuple)
