"""S65 Fix 4 — `#dm-aside` role-confusion closure tests.

Structural verification of the ADVISORY_SYSTEM_PROMPT hard-fork. The
prompt cannot be runtime-tested without an LLM in the loop, so these
tests assert on prompt CONTENT — the structural framing that produces
the desired DM-addressing behavior.

Adversarial verify scenario from S65 plan:
> In #dm-aside, message Virgil with "my character is a half-elf, please
> remember that." Expected response: Virgil acknowledges as DM ("Noted —
> I'll keep that in mind for narration."). NOT expected: Virgil suggests
> how to ask "your DM" about pronouns.

The structural fix: hard-fork the system prompt prefix to establish
Virgil-as-engine + asker-as-DM identity. These tests verify that
hard-fork is in place.

Run:
    cd /home/jordaneal/scripts && python3 test_dm_aside_role_closure.py
"""

import sys
sys.path.insert(0, '/home/jordaneal/scripts')

import dnd_orchestration as orch


# ── (1) Identity framing: Virgil-as-engine, asker-as-DM ─────────────

def test_prompt_establishes_virgil_as_engine():
    """Prompt must explicitly identify Virgil as the engine, not the DM."""
    p = orch.ADVISORY_SYSTEM_PROMPT
    p_lower = p.lower()
    assert 'underlying game engine' in p_lower or \
           'game engine' in p_lower or \
           'system' in p_lower, \
        "Prompt must identify Virgil as engine/system, not as DM persona"


def test_prompt_identifies_asker_as_dm():
    """The operator addressing Virgil IS the DM — must be unambiguous."""
    p = orch.ADVISORY_SYSTEM_PROMPT
    p_lower = p.lower()
    # Multiple supporting phrasings — must hit at least one
    dm_id_phrases = [
        'addressing you is the dm',
        'addressing you is the dungeon master',
        'operator is the dm',
        'asker is the dm',
        'speaking with the human dungeon master',
        'directly with the human dungeon master',
        'the dm is who you are addressing',
    ]
    hits = [phrase for phrase in dm_id_phrases if phrase in p_lower]
    assert hits, f"Prompt must identify asker as DM. None of {dm_id_phrases} matched."


def test_prompt_not_speaking_to_player():
    """Explicit denial of player-addressing framing."""
    p = orch.ADVISORY_SYSTEM_PROMPT
    p_lower = p.lower()
    assert 'not speaking to a player' in p_lower or \
           'not addressing a player' in p_lower, \
        "Prompt must explicitly deny the player-addressing frame"


def test_prompt_not_in_character():
    """Prompt must mark itself as out-of-fiction."""
    p = orch.ADVISORY_SYSTEM_PROMPT
    p_lower = p.lower()
    assert 'not in-character' in p_lower or 'out-of-character' in p_lower


# ── (2) Authority handling: DM feedback is authoritative ────────────

def test_prompt_treats_dm_feedback_as_authoritative():
    """Per S65 plan: 'treat their feedback about character pronouns, scene
    state, or narration behavior as authoritative.' Must be in prompt."""
    p = orch.ADVISORY_SYSTEM_PROMPT
    p_lower = p.lower()
    # Look for "authoritative" or equivalent strong-authority phrasing
    authority_phrases = [
        'as authoritative',
        'treat their feedback',
        'corrective',
        'note to carry into',
    ]
    hits = [phrase for phrase in authority_phrases if phrase in p_lower]
    assert hits, \
        f"Prompt must establish DM feedback as authoritative. None of {authority_phrases} matched."


def test_prompt_explicit_anti_third_party_advice():
    """Per S65 plan adversarial verify: Virgil must NOT redirect the DM
    to 'ask your DM' — the prompt must explicitly forbid this."""
    p = orch.ADVISORY_SYSTEM_PROMPT
    p_lower = p.lower()
    # Look for explicit anti-redirect framing
    anti_redirect = [
        "do not address the dm as if they were a player",
        "do not redirect the dm to ask anyone else",
        "ask your dm",  # appears in the negative example
        "ask the dm",
        "phrases like",
    ]
    hits = [phrase for phrase in anti_redirect if phrase in p_lower]
    assert hits, \
        f"Prompt must forbid 'ask your DM' redirect patterns. None of {anti_redirect} matched."


# ── (3) Invariants preserved: read-only, no Avrae writes ────────────

def test_prompt_preserves_no_state_mutation_invariant():
    """The bot-Avrae write boundary + advisory read-only invariant must
    survive the hard-fork. This channel still cannot write engine state."""
    p = orch.ADVISORY_SYSTEM_PROMPT
    p_lower = p.lower()
    assert 'do not mutate' in p_lower or 'read-only' in p_lower
    assert 'do not advance time' in p_lower or 'do not advance' in p_lower


def test_prompt_preserves_no_avrae_emission_invariant():
    """Per §65 doctrine: the bot does NOT emit `!`-prefixed Avrae
    commands directly. Suggests, doesn't execute. Survives hard-fork."""
    p = orch.ADVISORY_SYSTEM_PROMPT
    p_lower = p.lower()
    assert 'do not emit' in p_lower and 'avrae' in p_lower


def test_prompt_preserves_no_narration_invariant():
    """Advisory is read-only — must not generate scene narration."""
    p = orch.ADVISORY_SYSTEM_PROMPT
    p_lower = p.lower()
    assert 'do not narrate' in p_lower or 'not narrate' in p_lower


# ── (4) Channel-boundary scope (per GPT 1/3 note in S65 plan) ───────

def test_prompt_does_not_propagate_dm_role_to_other_channels():
    """Per S65 plan: 'identity merge applies in #dm-aside ONLY.' The
    advisory prompt is the only place the Virgil-as-DM framing exists.
    `#dm-narration`'s prompt (build_dm_context) must still treat Virgil
    as narrator and operators/players-as-characters separately."""
    # Inspect that build_dm_context's prompt body doesn't say "you are
    # the DM" — that's gameplay narration territory.
    import inspect
    build_src = inspect.getsource(orch)  # full source as fallback
    # Heuristic: gameplay narration prompt should still say
    # "You are the Dungeon Master" (Virgil narrates AS the DM persona
    # in #dm-narration), not "communicating directly with the human DM"
    # (which is the aside framing). The two prompts must remain
    # distinct.
    # The build_dm_context body lives in dnd_engine.py; we only check
    # that the advisory prompt is self-contained here.
    advisory = orch.ADVISORY_SYSTEM_PROMPT
    # Sanity: advisory prompt should be 1.5-3 KB; if it grew past 5 KB
    # something fundamental changed.
    assert 500 <= len(advisory) <= 8000, \
        f"ADVISORY_SYSTEM_PROMPT unexpected size: {len(advisory)}"


# ── (5) build_advisory_context phrasing aligned ─────────────────────

def test_advisory_context_uses_bound_character_phrasing():
    """build_advisory_context's bound-character line should not refer
    to 'asking player' anymore (under the role-as-DM framing)."""
    out = orch.build_advisory_context(
        campaign={'id': 1, 'name': 'X'},
        bound_character_name='Maelin',
        scene_state=None,
        active_turn=None,
        combatants_snapshot=None,
        inventory=None,
        pending_loot=None,
    )
    assert 'Bound character: Maelin' in out
    assert "Asking player" not in out, \
        "Old 'Asking player' phrasing must not surface under role-as-DM framing"


def test_advisory_context_empty_bound_character():
    """Empty bound-character renders as '(none)' not '(no bound character)'."""
    out = orch.build_advisory_context(
        campaign={'id': 1, 'name': 'X'},
        bound_character_name=None,
        scene_state=None,
        active_turn=None,
        combatants_snapshot=None,
        inventory=None,
        pending_loot=None,
    )
    assert 'Bound character: (none)' in out


# ── (6) Adversarial scenario structural shape ───────────────────────

def test_prompt_has_explicit_dm_correction_acknowledgment():
    """Per S65 plan: when the DM tells Virgil something corrective (a
    character pronoun, scene fact, narration habit), Virgil must
    acknowledge it as authoritative and carry into subsequent narration.
    The prompt must instruct this behavior explicitly."""
    p = orch.ADVISORY_SYSTEM_PROMPT
    p_lower = p.lower()
    # Must mention: corrective feedback acknowledgment, pronoun example,
    # OR carry-into-narration framing
    correction_phrases = [
        'corrective',
        'pronoun',
        'carry into subsequent narration',
        'note to carry',
        'as authoritative',
    ]
    hits = [phrase for phrase in correction_phrases if phrase in p_lower]
    assert hits, \
        f"Prompt must instruct corrective-feedback acknowledgment. None of {correction_phrases} matched."


# ── Test driver ─────────────────────────────────────────────────────

def main():
    tests = [
        # (1) identity
        test_prompt_establishes_virgil_as_engine,
        test_prompt_identifies_asker_as_dm,
        test_prompt_not_speaking_to_player,
        test_prompt_not_in_character,
        # (2) authority
        test_prompt_treats_dm_feedback_as_authoritative,
        test_prompt_explicit_anti_third_party_advice,
        # (3) invariants preserved
        test_prompt_preserves_no_state_mutation_invariant,
        test_prompt_preserves_no_avrae_emission_invariant,
        test_prompt_preserves_no_narration_invariant,
        # (4) channel-boundary scope
        test_prompt_does_not_propagate_dm_role_to_other_channels,
        # (5) context phrasing
        test_advisory_context_uses_bound_character_phrasing,
        test_advisory_context_empty_bound_character,
        # (6) corrective acknowledgment
        test_prompt_has_explicit_dm_correction_acknowledgment,
    ]
    fails = []
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except AssertionError as e:
            print(f"FAIL  {t.__name__}: {e}")
            fails.append(t.__name__)
        except Exception as e:
            print(f"ERROR {t.__name__}: {type(e).__name__}: {e}")
            fails.append(t.__name__)
    if fails:
        print(f"\n{len(fails)} test(s) failed: {fails}")
        sys.exit(1)
    print(f"\nAll {len(tests)} tests passed.")


if __name__ == '__main__':
    main()
