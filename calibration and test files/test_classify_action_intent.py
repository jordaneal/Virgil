"""Calibration + unit tests for classify_action_intent (mode-aware).

Spec source: SESSIONS.md Session 7-style postmortem describing the
mode-aware classifier behavior:
  - social/downtime mode: SOCIAL and CONTESTED checked BEFORE RISKY,
    so idioms like "steal a glance" / "I tell him to leave" don't
    misfire as INTENT_RISKY in mode where they read social.
  - travel mode: TRIVIAL promoted, so casual movement during travel
    doesn't trigger exploration rolls.
  - RISKY_RX hardened with negative lookaheads on `steal` and `sneak`
    to exclude idiomatic uses universally (regardless of mode).

Calibration covers six categories (per the design review):
  1. idiomatic false positives — RISKY verbs in non-risky uses
  2. true risky actions that must still fire
  3. ambiguous social/risky overlap (mode disambiguates)
  4. combat intimidation/threats
  5. downtime harmless verbs
  6. travel shorthand actions

Plus regressions: every case previously handled by the in_combat-only
classifier should still classify the same way it did before, in the
modes where it was originally evaluated.
"""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import dnd_orchestration as orch  # noqa: E402


# ─── Calibration cases ────────────────────────────────────────────────────────
# Each case: (text, mode, expected_intent, rationale_comment)

CALIBRATION = [
    # ── 1. Idiomatic false positives — universal (any mode) ────────────────
    # "steal a glance" / "sneak a peek" are idioms, not stealth/larceny.
    # Negative lookaheads in RISKY_RX exclude these UNIVERSALLY.
    # Result is SOCIAL by fallthrough (default no-match → INTENT_SOCIAL),
    # which is functionally correct (should_call_roll treats SOCIAL as
    # no-roll). The point of the lookahead is preventing the FALSE
    # INTENT_RISKY classification, not pinning a specific non-RISKY tag.
    ("I steal a glance at the map",      'exploration', orch.INTENT_SOCIAL,
     "idiom: 'steal a glance' — lookahead prevents RISKY, falls through to SOCIAL"),
    ("I steal a peek at her notes",      'social',      orch.INTENT_SOCIAL,
     "idiom: 'steal a peek' falls through to SOCIAL in social mode"),
    ("I sneak a glance at the bartender",'social',      orch.INTENT_SOCIAL,
     "idiom: 'sneak a glance' falls through to SOCIAL"),
    ("I sneak a peek behind the curtain",'exploration', orch.INTENT_SOCIAL,
     "idiom: 'sneak a peek' falls through to SOCIAL"),

    # ── 2. True risky actions still fire ───────────────────────────────────
    ("I steal the merchant's coin pouch",  'social',      orch.INTENT_RISKY,
     "real larceny: 'steal the X' (concrete object) still risky"),
    # Note: "sneak past <X>" is CONTESTED by design — it's an opposed
    # action against the guards' perception. CONTESTED_RX has the
    # explicit phrase "sneak past". This is correct behavior, not a
    # mode-aware reorder concern. Plain "sneak <somewhere>" without
    # "past" hits RISKY.
    ("I sneak through the bushes",         'exploration', orch.INTENT_RISKY,
     "real stealth: 'sneak through' (no opposed actor) still risky"),
    ("I pickpocket the noble",             'social',      orch.INTENT_RISKY,
     "explicit larceny verb"),
    ("I hide behind the barrels",          'exploration', orch.INTENT_RISKY,
     "real concealment, no idiom"),

    # Regression check for the explicit CONTESTED phrase that's NOT
    # affected by the lookahead change — proves we didn't break it.
    ("I sneak past the guards", 'exploration', orch.INTENT_CONTESTED,
     "'sneak past' is explicit CONTESTED phrase (opposed action)"),

    # ── 3. Ambiguous social/risky overlap — mode disambiguates ─────────────
    # In social/downtime mode, SOCIAL is checked before RISKY, so
    # phrases that match both lean social.
    ("I tell the bartender about the rumor",     'social',      orch.INTENT_SOCIAL,
     "social mode: SOCIAL_RX 'tell' before RISKY"),
    ("I ask the merchant for directions",        'exploration', orch.INTENT_SOCIAL,
     "SOCIAL_RX wins in default exploration"),

    # ── 4. Combat intimidation / threats ───────────────────────────────────
    # CONTESTED stays contested in combat; should_call_roll handles severity.
    ("I intimidate the goblin into surrendering", 'combat',     orch.INTENT_CONTESTED,
     "CONTESTED_RX matches; classifier doesn't escalate to combat"),
    ("I threaten the captive",                    'social',     orch.INTENT_CONTESTED,
     "CONTESTED_RX 'threaten' in social mode"),

    # ── 5. Downtime harmless verbs ─────────────────────────────────────────
    # In downtime, things default to social/trivial; should_call_roll
    # skips rolls in downtime anyway, but the classification should
    # not falsely demand RISKY/EXPLORATION action.
    ("I drink at the bar",                'downtime', orch.INTENT_TRIVIAL,
     "downtime trivial action"),
    # NOTE: "I tell stories around the fire" would falsely trigger
    # COMBAT_RX because `\bfire\b` matches the noun "fire" — this is
    # a pre-existing COMBAT_RX false positive, NOT a mode-aware-classifier
    # concern. Filed as a separate roadmap item. Test text avoids it.
    ("I tell stories at the bar",         'downtime', orch.INTENT_SOCIAL,
     "downtime social, SOCIAL_RX 'tell' before RISKY"),
    ("I sneak a sip of the captain's rum",'downtime', orch.INTENT_SOCIAL,
     "downtime + idiom: lookahead prevents RISKY, falls through to SOCIAL"),

    # ── 6. Travel shorthand — TRIVIAL promotion ────────────────────────────
    # Travel mode promotes trivial classification for casual movement,
    # so "I keep walking" and similar don't trigger exploration rolls.
    ("I keep walking",                    'travel', orch.INTENT_TRIVIAL,
     "travel mode: walking is trivial, not exploration"),
    ("I follow the road north",           'travel', orch.INTENT_TRIVIAL,
     "travel mode: following the road is trivial"),
    ("I look around the camp",            'travel', orch.INTENT_TRIVIAL,
     "travel mode: 'look around' is trivial, not exploration"),
    # But genuine investigation in travel mode still hits exploration:
    ("I investigate the strange tracks",  'travel', orch.INTENT_EXPLORATION,
     "travel mode: explicit 'investigate' still exploration"),

    # ── 7. Regression: combat actions unchanged ────────────────────────────
    ("I attack the goblin",     'combat',      orch.INTENT_COMBAT,
     "combat baseline"),
    ("I attack the goblin",     'exploration', orch.INTENT_COMBAT,
     "COMBAT_RX wins regardless of mode (defer to Avrae)"),
    ("I cast fireball at them", 'combat',      orch.INTENT_COMBAT,
     "spell cast"),

    # ── 8. Regression: meta still wins ─────────────────────────────────────
    ("OOC: how does grappling work?", 'combat',      orch.INTENT_META,
     "OOC prefix"),
    ("How do I check my HP?",         'exploration', orch.INTENT_META,
     "META_RX 'how do i'"),

    # ── 9. Regression: exploration in default mode ─────────────────────────
    ("I search the room for traps",      'exploration', orch.INTENT_EXPLORATION,
     "exploration baseline"),
    ("I climb the wall",                 'exploration', orch.INTENT_EXPLORATION,
     "exploration physical"),

    # ── 10. Edge: empty / whitespace ───────────────────────────────────────
    ("",     'exploration', orch.INTENT_TRIVIAL, "empty input"),
    ("   ",  'exploration', orch.INTENT_TRIVIAL, "whitespace input"),
]


# ─── Tests ────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "text,mode,expected,rationale",
    CALIBRATION,
    ids=[f"{i:02d}_{c[1]}_{c[2]}_{c[3][:40]}" for i, c in enumerate(CALIBRATION)]
)
def test_calibration(text, mode, expected, rationale):
    actual = orch.classify_action_intent(text, mode=mode)
    assert actual == expected, (
        f"\n  text:     {text!r}"
        f"\n  mode:     {mode!r}"
        f"\n  expected: {expected}"
        f"\n  actual:   {actual}"
        f"\n  reason:   {rationale}"
    )


# ─── Direct API tests (signature shape, defaults) ─────────────────────────────

def test_signature_default_mode_is_exploration():
    """Default mode behaves as 'exploration' (no kwarg)."""
    a = orch.classify_action_intent("I search the room")
    b = orch.classify_action_intent("I search the room", mode='exploration')
    assert a == b == orch.INTENT_EXPLORATION


def test_signature_takes_mode_keyword():
    """mode is a keyword parameter (not positional)."""
    out = orch.classify_action_intent("I tell him to leave", mode='social')
    assert out == orch.INTENT_SOCIAL


def test_signature_does_not_accept_in_combat():
    """The legacy in_combat parameter has been removed.
    Passing it raises TypeError — confirms the dead-parameter cleanup
    landed and prevents accidental reintroduction."""
    with pytest.raises(TypeError):
        orch.classify_action_intent("I attack", in_combat=True)


def test_unknown_mode_falls_back_to_default_behavior():
    """An unrecognized mode value should not crash — classifier should
    gracefully default to exploration-like behavior."""
    out = orch.classify_action_intent("I search the room", mode='zorp')
    assert out == orch.INTENT_EXPLORATION


# ─── Regex-level: negative lookahead direct verification ──────────────────────

def test_risky_rx_excludes_steal_a_glance():
    """RISKY_RX should NOT match 'steal a glance' — universal lookahead."""
    assert not orch.RISKY_RX.search("I steal a glance at the map")


def test_risky_rx_excludes_sneak_a_peek():
    assert not orch.RISKY_RX.search("I sneak a peek at the document")


def test_risky_rx_still_matches_real_steal():
    """Negative lookahead must NOT over-suppress real larceny."""
    assert orch.RISKY_RX.search("I steal the gem from the case")


def test_risky_rx_still_matches_real_sneak():
    assert orch.RISKY_RX.search("I sneak past the patrol")



# ─────────────────────────────────────────────────────────
# Ship A live-verify patch (S36 #2) — classifier expansion regression
# Spec source: LLM_EMIT_RESOLUTION_BINDING_SPEC.md + operator pushback
# during Ship A live-verify (S36).
# ─────────────────────────────────────────────────────────


def test_trivial_no_longer_shadows_qualified_look():
    """Bare `look` removed from TRIVIAL_RX. Only `look around` stays trivial."""
    # Pre-patch this would have matched and short-circuited as trivial.
    assert orch.classify_action_intent("Look closely at the notice board", 'exploration') == 'exploration'
    assert orch.classify_action_intent("I look harder for clues", 'exploration') == 'exploration'
    # `look around` (bare scanning) still trivial:
    assert orch.classify_action_intent("I look around the tavern", 'exploration') == 'trivial'


def test_exploration_catches_natural_investigative_verbs():
    """New verb anchors: find, peer, peek, notice, spot, scan, scrutinize,
    comb, figure out, discern, check (broader than check-for-traps)."""
    for text in [
        "I try to find a hidden detail",
        "I peer at the parchment",
        "I peek behind the curtain",
        "I scrutinize the runes",
        "I scan the room for anything strange",
        "I comb the chamber",
        "I figure out the lock mechanism",
        "I check the parchment for hidden text",
    ]:
        intent = orch.classify_action_intent(text, 'exploration')
        assert intent == 'exploration', f"{text!r} → {intent}, expected exploration"


def test_exploration_catches_take_a_closer_look_idiom():
    """The 'take a closer/careful/hard look' idiom now routes to exploration."""
    for text in [
        "I take a closer look at the room",
        "I take a careful look at the map",
        "I take a hard look at his face",
    ]:
        intent = orch.classify_action_intent(text, 'exploration')
        assert intent == 'exploration', f"{text!r} → {intent}, expected exploration"


def test_exploration_catches_physical_athletics_verbs():
    """Athletics-shaped verbs: lift, hoist, force, pry, wrench, break, push, haul."""
    for text, expected_skill in [
        ("I try to lift the heavy stone", 'athletics'),
        ("I break down the door", 'athletics'),
        ("I push the bookshelf aside", 'athletics'),
        ("I haul the chest to the corner", 'athletics'),
    ]:
        decision = orch.should_call_roll(
            orch.classify_action_intent(text, 'exploration'),
            'exploration', text,
        )
        assert decision.needs_roll, f"{text!r} should ROLL"
        assert decision.skill == expected_skill, (
            f"{text!r} → skill={decision.skill}, expected {expected_skill}"
        )


def test_physical_break_open_overrides_combat():
    """smash/break/bash X open|down|through|apart routes to exploration
    athletics before COMBAT_RX claims it. Pre-patch: 'smash the chest open'
    classified as combat because `smash` was in COMBAT_RX."""
    for text in [
        "I smash the chest open",
        "I break the door down",
        "I bash the lock apart",
        "I crush the crate open",
    ]:
        intent = orch.classify_action_intent(text, 'exploration')
        assert intent == 'exploration', f"{text!r} → {intent}, expected exploration"


def test_real_combat_verbs_still_fire():
    """Regression: COMBAT_RX still catches genuine attack verbs."""
    for text in [
        "I attack the goblin",
        "I strike the orc with my sword",
        "I stab him in the back",
        "I cast fireball at the dragon",
    ]:
        intent = orch.classify_action_intent(text, 'exploration')
        assert intent == 'combat', f"{text!r} → {intent}, expected combat"


def test_ship_a_resolution_sentinel_classifies_meta():
    """S36 #6 — Ship A auto-fire synthesized input must NOT trigger a
    new roll. Pre-patch: classifier matched skill nouns inside the
    bracket-frame sentinel and routed to exploration → ROLL DIRECTIVE
    block told LLM to emit another !check → cascading-roll bug.
    Patched by sentinel-prefix detection routing to META → no-roll."""
    sentinels = [
        '[Roll resolution: Donovan Ruby rolled athletics (check); outcome bound at top-of-prompt.]',
        '[Roll resolution: Donovan Ruby rolled perception (check); outcome bound at top-of-prompt.]',
        '[Roll resolution: Mia rolled sleight of hand (check); outcome bound at top-of-prompt.]',
        '[Roll resolution: Karrok rolled dexterity (save); outcome bound at top-of-prompt.]',
    ]
    for s in sentinels:
        intent = orch.classify_action_intent(s, 'exploration')
        assert intent == 'meta', f"{s!r} → {intent}, expected meta"
        decision = orch.should_call_roll(intent, 'exploration', s)
        assert not decision.needs_roll, (
            f"{s!r} should not trigger a new roll; got {decision}"
        )


def test_skill_picker_routes_natural_verbs():
    """New EXPLORATION_DEFAULT_SKILLS entries route the right skill."""
    cases = [
        ("I look closely at the notice board", 'perception'),
        ("I look carefully at the runes", 'perception'),
        ("try to find a missing detail", 'investigation'),
        ("I peer at the parchment", 'perception'),
        ("I read carefully the inscription", 'investigation'),
        ("I scrutinize the seal", 'investigation'),
        ("I take a closer look at the room", 'perception'),
        ("I lift the heavy stone", 'athletics'),
        ("I push the bookshelf aside", 'athletics'),
        ("I smash the chest open", 'athletics'),
    ]
    for text, expected in cases:
        decision = orch.should_call_roll(
            orch.classify_action_intent(text, 'exploration'),
            'exploration', text,
        )
        assert decision.skill == expected, (
            f"{text!r} → skill={decision.skill}, expected {expected}"
        )
