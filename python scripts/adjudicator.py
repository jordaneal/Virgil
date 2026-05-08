"""
adjudicator.py
─────────────────────────────────────────────────────────
Track 7 #1 — Binding Adjudication Layer.
Track 7 #2 — Multi-Action Arbitration (arbitrate() + ArbitrationResult).

adjudicate(player_input, ...) → AdjudicationResult
  Single pure per-actor entry point. Unchanged from Track 7 #1.

arbitrate(actions, ...) → ArbitrationResult
  Multi-actor wrapper. Calls adjudicate() per actor, priority-sorts,
  all-pairs conflict-detects, renders combined_constraint. Single-actor
  degenerate case produces byte-identical output to Track 7 #1.
  Soft-fails at call site (Doctrine §59).

Promotes mechanical authority from advisory text (S9 capability, S19
commitment, S23 #2 redirect, S21 persistence) to a binding pre-LLM
verdict. Categorizes player input into one of five action classes
(FREE, CHECK, CAPABILITY, COMBAT, WORLD_BOUNDARY) plus internal
FALLBACK; applies deterministic gates per class; returns a structured
result whose narration_constraint is rendered as a top-of-prompt block
(echoed at HARD STOP RULES tail) so the LLM is bound to the verdict.

Composes BEFORE all sibling directives in dm_respond. Downstream
directives (capability_decision, combat_redirect) read AdjudicationResult
and silence themselves when adjudication has already issued the verdict
(§11.L deduplication).

See virgil-docs/TRACK_7_2_SPEC.md for the locked design.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Optional

# Reuse advisory infra. Adjudicator does not modify orchestration; it
# binds the existing 3-state verdict for weapon claims and routes
# vocabulary through the existing intent regexes for FALLBACK.
from dnd_orchestration import (
    classify_action_intent,
    check_action_capability,
    CapabilityVerdict,
    EXPLORATION_DEFAULT_SKILLS,
    CONTESTED_DEFAULT_SKILLS,
    EXPLORATION_RX,
    RISKY_RX,
    CONTESTED_RX,
    SOCIAL_RX,
    TRIVIAL_RX,
    COMBAT_RX,
    META_RX,
    INTENT_COMBAT,
    INTENT_EXPLORATION,
    INTENT_CONTESTED,
    INTENT_RISKY,
    INTENT_SOCIAL,
    INTENT_TRIVIAL,
    INTENT_META,
    _pick_skill,
)


# ─────────────────────────────────────────────────────────
# Feature flags (§1.9 lock — independent rollback per mechanism)
# ─────────────────────────────────────────────────────────
# ADJUDICATION_ENABLED: False forces FALLBACK from every adjudicate() call.
# ARBITRATION_ENABLED:  False short-circuits arbitrate() to first-actor-only
#                       single adjudicate() call (Track 7 #1 behavior).
# VERIFICATION_ENABLED: mirrors flag in narration_verifier.py; imported
#                       there. Declared here for co-location with the other
#                       two flags so operators find all three in one place.
ADJUDICATION_ENABLED = True
ARBITRATION_ENABLED  = True
VERIFICATION_ENABLED = True   # authoritative copy lives in narration_verifier.py


# ─────────────────────────────────────────────────────────
# Categories
# ─────────────────────────────────────────────────────────
FREE_ACTION           = 'free'
CHECK_ACTION          = 'check'
CAPABILITY_ACTION     = 'capability'
COMBAT_ACTION         = 'combat'
WORLD_BOUNDARY_ACTION = 'world_boundary'
FALLBACK              = 'fallback'

# Refusal kinds (populated when allowed=False)
REFUSAL_CAPABILITY      = 'capability'
REFUSAL_COMBAT_INACTIVE = 'combat_inactive'
REFUSAL_WORLD_BOUNDARY  = 'world_boundary'
REFUSAL_CHECK_FAILED    = 'check_failed'

# DC band thresholds (§5.4)
DC_EASY   = 10
DC_MEDIUM = 15
DC_HARD   = 20


@dataclass
class AdjudicationResult:
    category: str = FALLBACK
    allowed: bool = True
    refusal_kind: str = ''
    skill: str = ''
    dc: Optional[int] = None
    dc_band: str = ''
    roll_consumed: bool = False
    roll_value: Optional[int] = None
    success: Optional[bool] = None
    narration_constraint: str = ''
    signals: dict = field(default_factory=dict)


# ─────────────────────────────────────────────────────────
# Vocabulary (Appendix A — Code-drafted, observability-driven)
# ─────────────────────────────────────────────────────────

# §5.3 — reality-violating phrase patterns. Curated narrow.
_WORLD_BOUNDARY_PATTERNS = [
    re.compile(r'\bspawn\s+\d{3,}\b', re.IGNORECASE),
    re.compile(r'\bsummon\s+\d{3,}\b', re.IGNORECASE),
    re.compile(r'\bconjure\s+(?:a\s+)?(?:thousand|million|billion|infinite|endless|countless)\b', re.IGNORECASE),
    re.compile(r'\bcreate\s+\d{3,}\b', re.IGNORECASE),
    re.compile(r'\bbecome\s+(?:a\s+)?(?:god|deity|immortal|omnipotent|omniscient)\b', re.IGNORECASE),
    re.compile(r'\bascend\s+to\s+(?:godhood|divinity|the\s+heavens|a\s+higher\s+plane)\b', re.IGNORECASE),
    re.compile(r'\bbirth\s+(?:a|the)\s+\w+', re.IGNORECASE),
    re.compile(r'\bpoop\s+out\b', re.IGNORECASE),
    re.compile(r'\bvanish\s+from\s+existence\b', re.IGNORECASE),
    re.compile(r'\bbreak\s+(?:the|this)\s+(?:reality|simulation|fourth\s+wall)\b', re.IGNORECASE),
    re.compile(r'\bend\s+(?:the\s+)?(?:world|universe|campaign)\b', re.IGNORECASE),
    re.compile(r'\brewrite\s+(?:the\s+)?(?:rules|reality|laws\s+of\s+(?:physics|magic))\b', re.IGNORECASE),
    re.compile(r'\bi\s+(?:am|become)\s+(?:the\s+)?(?:dm|narrator|game\s*master)\b', re.IGNORECASE),
    re.compile(r'\b(?:teleport|warp)\s+(?:to|across)\s+(?:another|a\s+different)\s+(?:plane|dimension|reality)\b', re.IGNORECASE),
    re.compile(r'\bgain\s+(?:infinite|unlimited)\s+\w+', re.IGNORECASE),
    re.compile(r'\bone[- ]shot\s+(?:the\s+)?(?:bbeg|villain|boss|dragon)\b', re.IGNORECASE),
]

# Capability invocation: verb + feature-noun proximity. Spell names,
# class features, racial abilities. Weapon claims continue routing
# through dnd_orchestration.check_action_capability() (S9).
_CAPABILITY_INVOCATION_VERBS = (
    'cast', 'invoke', 'channel', 'use', 'activate', 'unleash',
    'trigger', 'manifest', 'summon',
)

# Spell-name detection — small curated list for v1, expanded from
# observed friction. The intent here is "did the player name a specific
# spell" not "is this a real spell" — naming is the trigger.
_SPELL_NAMES = {
    # Cantrips / common low-level
    'fire bolt', 'firebolt', 'mage hand', 'minor illusion', 'prestidigitation',
    'eldritch blast', 'sacred flame', 'guidance', 'light',
    # Common 1st-level
    'magic missile', 'shield', 'cure wounds', 'healing word', 'bless',
    'sleep', 'thunderwave', 'burning hands', 'detect magic', 'feather fall',
    # 2nd-level
    'misty step', 'invisibility', 'web', 'hold person', 'suggestion',
    # 3rd-level
    'fireball', 'lightning bolt', 'counterspell', 'fly', 'haste',
    'dispel magic', 'revivify', 'animate dead',
    # 4th-level+
    'wall of fire', 'polymorph', 'banishment', 'greater invisibility',
    'cone of cold', 'hold monster', 'wall of force',
    # 6th+
    'disintegrate', 'mass heal', 'true polymorph', 'wish', 'meteor swarm',
    'power word kill', 'time stop',
}

# Class-feature invocations (subset — expand from observed)
_CLASS_FEATURES = {
    'rage':            {'barbarian'},
    'second wind':     {'fighter'},
    'action surge':    {'fighter'},
    'sneak attack':    {'rogue'},
    'cunning action':  {'rogue'},
    'wild shape':      {'druid'},
    'channel divinity':{'cleric', 'paladin'},
    'lay on hands':    {'paladin'},
    'divine smite':    {'paladin'},
    'ki':              {'monk'},
    'flurry of blows': {'monk'},
    'bardic inspiration': {'bard'},
    'sorcery points': {'sorcerer'},
    'metamagic':       {'sorcerer'},
    'hex':             {'warlock'},
    'eldritch invocation': {'warlock'},
}

# Caster classes (any with spell slots). Used to gate spell claims.
_CASTER_CLASSES = {
    'wizard', 'sorcerer', 'cleric', 'druid', 'bard', 'warlock',
    'paladin', 'ranger', 'artificer',
    # Half-casters get gated by level too — paladin/ranger don't get
    # slots until level 2. Spell-level vs character-level gating is
    # not v1 — v1 only checks "is this a caster class at all."
}

# Spells requiring 3rd-level slot or higher. Crude but adequate v1
# gate against "I cast Fireball at level 1." Level-aware refinement
# filed for v2.
_HIGH_LEVEL_SPELLS = {
    'fireball': 5, 'lightning bolt': 5, 'counterspell': 5, 'fly': 5,
    'haste': 5, 'dispel magic': 5, 'revivify': 5, 'animate dead': 5,
    'wall of fire': 7, 'polymorph': 7, 'banishment': 7,
    'greater invisibility': 7, 'cone of cold': 9, 'hold monster': 9,
    'wall of force': 9, 'disintegrate': 11, 'mass heal': 17,
    'true polymorph': 17, 'wish': 17, 'meteor swarm': 17,
    'power word kill': 17, 'time stop': 17,
}

# Build the capability invocation regex lazily once.
_VERB_ALT = '|'.join(_CAPABILITY_INVOCATION_VERBS)
_CAPABILITY_INVOKE_RX = re.compile(
    rf'\b(?P<verb>{_VERB_ALT})\b',
    re.IGNORECASE,
)


# ─────────────────────────────────────────────────────────
# DC band selection
# ─────────────────────────────────────────────────────────

def _dc_for_check(category_intent: str, scene_state: Optional[dict],
                  text: str) -> tuple[int, str]:
    """Return (dc, band_label). Uses scene tension/mode + intent shape."""
    mode = (scene_state or {}).get('mode', 'exploration') or 'exploration'
    tension = int((scene_state or {}).get('tension_int') or 0)

    if category_intent == INTENT_EXPLORATION:
        if mode == 'combat':
            return DC_HARD if tension >= 2 else DC_MEDIUM, \
                   'hard' if tension >= 2 else 'medium'
        if mode in ('exploration', 'travel') and tension <= 0:
            return DC_EASY, 'easy'
        return DC_MEDIUM, 'medium'

    if category_intent == INTENT_CONTESTED:
        # Hostile contested → hard. Default contested → easy/medium.
        t = (text or '').lower()
        if any(w in t for w in ('intimidate', 'threaten', 'menace',
                                 'interrogate', 'deceive', 'lie')):
            return DC_HARD, 'hard'
        return DC_EASY, 'easy'

    if category_intent == INTENT_RISKY:
        if tension >= 2 or mode == 'combat':
            return DC_HARD, 'hard'
        return DC_MEDIUM, 'medium'

    return DC_MEDIUM, 'medium'


def _skill_for_check(category_intent: str, text: str) -> str:
    """Pick the skill name for a CHECK_ACTION based on intent + text."""
    if category_intent == INTENT_EXPLORATION:
        return _pick_skill(text, EXPLORATION_DEFAULT_SKILLS) or 'perception'
    if category_intent == INTENT_CONTESTED:
        return _pick_skill(text, CONTESTED_DEFAULT_SKILLS) or 'persuasion'
    if category_intent == INTENT_RISKY:
        t = (text or '').lower()
        if any(w in t for w in ('sneak', 'shadow', 'tail', 'slip', 'hide')):
            return 'stealth'
        if any(w in t for w in ('steal', 'pickpocket', 'lift', 'snatch')):
            return 'sleight_of_hand'
        return 'stealth'
    return 'perception'


# ─────────────────────────────────────────────────────────
# Roll consumption
# ─────────────────────────────────────────────────────────

def consume_recent_check(avrae_events: Optional[list],
                          actor_name: str,
                          skill: str) -> tuple[Optional[int], bool]:
    """Scan avrae_events for an unconsumed `!check <skill>` matching actor.

    avrae_events is the list shape produced by RollBuffer.recent() — each
    entry: {'actor', 'kind', 'detail', 'result', 'nat', 'ts', ...}.
    Returns (roll_value, consumed) — roll_value is None if no match.

    Match rule: kind=='check' AND actor matches (case-insensitive
    full-string) AND detail's lowercased form contains the skill (handles
    'sleight of hand' vs 'sleight_of_hand').
    """
    if not avrae_events or not actor_name or not skill:
        return None, False
    actor_lower = (actor_name or '').strip().lower()
    skill_norm = skill.replace('_', ' ').strip().lower()
    if not actor_lower or not skill_norm:
        return None, False
    for ev in avrae_events:
        if not isinstance(ev, dict):
            continue
        if ev.get('kind') != 'check':
            continue
        ev_actor = (ev.get('actor') or '').strip().lower()
        if ev_actor != actor_lower:
            continue
        ev_detail = (ev.get('detail') or '').strip().lower()
        if skill_norm not in ev_detail and ev_detail not in skill_norm:
            continue
        result = ev.get('result')
        if isinstance(result, int):
            return result, True
    return None, False


# ─────────────────────────────────────────────────────────
# Capability gates (§5.2 step 3)
# ─────────────────────────────────────────────────────────

def _detect_capability_claim(text: str) -> tuple[str, str]:
    """Return (claim_kind, claim_name) where claim_kind is one of:
        'spell', 'class_feature', 'racial', or '' (no claim).

    Spells require an invocation verb (cast/invoke/...) — too many spell
    names overlap with normal nouns ('shield', 'light', 'sleep'). Class
    features and racial abilities are detected on bare name presence —
    'rage' / 'sneak attack' / 'darkvision' are distinctive phrases that
    don't appear in normal narration in a 5e context.
    """
    t = (text or '').strip().lower()
    if not t:
        return '', ''
    if _CAPABILITY_INVOKE_RX.search(t):
        for spell in _SPELL_NAMES:
            if re.search(rf'\b{re.escape(spell)}\b', t):
                return 'spell', spell
    for feature in _CLASS_FEATURES:
        if re.search(rf'\b{re.escape(feature)}\b', t):
            return 'class_feature', feature
    if re.search(r'\b(darkvision|sunlight\s+sensitivity)\b', t):
        m = re.search(r'\b(darkvision|sunlight\s+sensitivity)\b', t)
        return 'racial', m.group(1)
    return '', ''


def _gate_capability(claim_kind: str, claim_name: str,
                     character) -> tuple[bool, str]:
    """Return (allowed, reason). character is CharacterContext or None.
    Per S9 partial-projections doctrine: refuse only on EXPLICIT
    contradiction; default to allow when source is incomplete."""
    if not character:
        return True, "no_character_context"

    char_class = (character.char_class or '').lower()
    level = character.level or 1
    tags = character.narrative_tags or set()

    if claim_kind == 'spell':
        if char_class and char_class not in _CASTER_CLASSES:
            return False, f"class={char_class!r} is not a caster class"
        min_level = _HIGH_LEVEL_SPELLS.get(claim_name)
        if min_level is not None and level < min_level:
            return False, (f"spell {claim_name!r} requires character "
                           f"level ~{min_level}; have {level}")
        return True, "caster + level adequate"

    if claim_kind == 'class_feature':
        required_classes = _CLASS_FEATURES.get(claim_name, set())
        if char_class and required_classes and char_class not in required_classes:
            return False, (f"feature {claim_name!r} requires "
                           f"{sorted(required_classes)}; class is "
                           f"{char_class!r}")
        return True, "class match or unknown class (defer)"

    if claim_kind == 'racial':
        feature = claim_name.replace(' ', '_')
        if feature == 'darkvision' and 'darkvision' not in tags:
            return False, "character has no darkvision tag"
        return True, "racial trait present or unknown (defer)"

    return True, "unknown claim kind"


# ─────────────────────────────────────────────────────────
# Combat gate (§5.2 step 2)
# ─────────────────────────────────────────────────────────

def _gate_combat(scene_state: Optional[dict],
                 combatants: Optional[list],
                 active_turn: Optional[dict]) -> tuple[bool, str]:
    """Return (allowed, reason) for COMBAT_ACTION. v1 binding: combat
    must be active in scene_state AND combatants snapshot non-empty AND
    active_turn populated."""
    mode = (scene_state or {}).get('mode')
    if mode != 'combat':
        return False, "scene_state.mode != 'combat'"
    rows = list(combatants or [])
    if not rows:
        return False, "combatants snapshot empty"
    if not active_turn:
        return False, "no active_turn row"
    return True, "combat active and tracker populated"


# ─────────────────────────────────────────────────────────
# Narration constraint bodies
# ─────────────────────────────────────────────────────────

def _constraint_world_boundary(input_text: str) -> str:
    return (
        f"The player has declared an action that exceeds the world's reality "
        f"({input_text!r}). REFUSE.\n\n"
        "Narrate the non-occurrence in-fiction:\n"
        "  - the air ripples and reasserts\n"
        "  - the ritual fails for reasons even the character doesn't understand\n"
        "  - the words don't catch — as if the world refuses them\n\n"
        "Do NOT:\n"
        "  - introduce an NPC who grants the request (no Keeper-of-the-Vein appears)\n"
        "  - narrate it working at smaller scale\n"
        "  - explain the metaphysical reason\n"
        "  - negotiate (\"perhaps you mean...\")\n\n"
        "This is a hard boundary. The action does not occur."
    )


def _constraint_combat_inactive(input_text: str) -> str:
    return (
        "The player has declared a combat action in non-combat mode. "
        "Combat is not active in this scene.\n\n"
        "Do NOT narrate the attack landing.\n"
        "Do NOT narrate the target taking damage.\n\n"
        "DO narrate the world's response: the target sees the move, others "
        "react, the room shifts. Then PROMPT the player: \"Combat hasn't "
        "started yet — do you want to commit, in which case roll initiative "
        "(!init begin)?\""
    )


def _constraint_combat_allowed(active_turn_name: str) -> str:
    return (
        f"Combat is ACTIVE. {active_turn_name or 'The player'} is on turn.\n\n"
        "Combat action is valid. Surface the appropriate Avrae command "
        "(!attack <weapon> -t <target>, or !cast <spell> -t <target>) to the "
        "player. Do NOT narrate the hit/miss outcome — that is Avrae's "
        "verdict to deliver. Narrate the moment of attempt only."
    )


def _constraint_capability_refused(claim_kind: str, claim_name: str,
                                    character, reason: str) -> str:
    char_desc = ''
    if character:
        char_class = (character.char_class or 'unknown class').title()
        level = character.level or 1
        char_desc = f"({character.name}, {char_class} {level})"
    return (
        f"The player has claimed a capability ({claim_kind}: {claim_name!r}) "
        f"the character does not have {char_desc}. REFUSE the action "
        f"in-fiction.\n\n"
        f"Reason: {reason}\n\n"
        "The words don't carry. The gesture fails. The intended effect does "
        "not occur.\n\n"
        "Do NOT:\n"
        "  - narrate the capability working\n"
        "  - introduce a scroll, wand, or item that grants it\n"
        "  - have an NPC interrupt with \"you don't have that\" (4th-wall break)\n"
        "  - negotiate (\"are you sure?\", \"do you mean...\")\n\n"
        "DO:\n"
        "  - narrate the moment of attempted invocation and its quiet failure\n"
        "  - surface an in-fiction reason if natural (no formal training, "
        "no slot, no source)"
    )


def _constraint_check_resolved(skill: str, dc: int, band: str,
                                roll: int, success: bool) -> str:
    outcome = 'SUCCESS' if success else 'FAILURE'
    skill_pretty = skill.replace('_', ' ')
    return (
        f"The player attempted a {skill_pretty.title()} check (DC {dc}, "
        f"{band} band). Avrae rolled {roll}.\n\n"
        f"This is a {outcome}. Narrate the {outcome.lower()} outcome only.\n\n"
        f"Do NOT narrate ambiguity (\"you think they might have...\"). Do NOT "
        f"narrate partial success. Roll {'≥' if success else '<'} DC means the "
        f"attempt {'succeeded' if success else 'failed'} cleanly."
    )


def _constraint_check_required(skill: str, dc: int, band: str) -> str:
    skill_pretty = skill.replace('_', ' ')
    return (
        f"The player attempted an action requiring a {skill_pretty.title()} "
        f"check (DC {dc}, {band} band). No roll has landed yet.\n\n"
        f"Surface the command: `!check {skill_pretty}`.\n\n"
        "Narrate ONLY the moment of attempt. Do NOT narrate outcome — "
        "what the player perceives, hears, or accomplishes arrives when "
        "the roll lands."
    )


# ─────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────

def adjudicate(player_input: str,
                scene_state: Optional[dict] = None,
                character=None,
                combatants: Optional[list] = None,
                active_turn: Optional[dict] = None,
                avrae_events: Optional[list] = None,
                skeleton_capabilities: Optional[dict] = None) -> AdjudicationResult:
    """Classify and gate a player action. Single pure entry point.

    Returns AdjudicationResult. Caller wraps in try/except (Doctrine §59);
    on exception, fall back to FALLBACK + empty constraint. Never blocks
    narration entirely.
    """
    text = (player_input or '').strip()
    signals = {
        'category': FALLBACK,
        'allowed': 1,
        'refusal_kind': '',
        'skill': '',
        'dc': None,
        'band': '',
        'roll_consumed': 0,
        'roll_value': None,
        'success': None,
        'input_preview': text[:140],
    }

    # Master flag (§9 rollback)
    if not ADJUDICATION_ENABLED:
        return AdjudicationResult(category=FALLBACK, allowed=True,
                                   narration_constraint='', signals=signals)

    if not text:
        return AdjudicationResult(category=FALLBACK, allowed=True,
                                   narration_constraint='', signals=signals)

    # META intent — OOC questions, rules clarifications. Pass through;
    # adjudicator stays out of the way.
    if META_RX.search(text):
        signals['category'] = FREE_ACTION
        return AdjudicationResult(category=FREE_ACTION, allowed=True,
                                   narration_constraint='', signals=signals)

    # 1. WORLD_BOUNDARY (highest precedence)
    for pat in _WORLD_BOUNDARY_PATTERNS:
        if pat.search(text):
            signals.update({
                'category': WORLD_BOUNDARY_ACTION,
                'allowed': 0,
                'refusal_kind': REFUSAL_WORLD_BOUNDARY,
            })
            return AdjudicationResult(
                category=WORLD_BOUNDARY_ACTION,
                allowed=False,
                refusal_kind=REFUSAL_WORLD_BOUNDARY,
                narration_constraint=_constraint_world_boundary(text[:140]),
                signals=signals,
            )

    # 2. CAPABILITY (spell / feature / racial) — runs BEFORE combat per
    # §11.A: capability gate first (do you have the means), combat gate
    # second (is the target valid). This matters because COMBAT_RX
    # contains 'cast' which would otherwise short-circuit "I cast
    # Fireball" before the spell-class gate runs.
    claim_kind, claim_name = _detect_capability_claim(text)
    if claim_kind:
        gate_ok, gate_reason = _gate_capability(claim_kind, claim_name, character)
        if not gate_ok:
            signals.update({
                'category': CAPABILITY_ACTION,
                'allowed': 0,
                'refusal_kind': REFUSAL_CAPABILITY,
            })
            return AdjudicationResult(
                category=CAPABILITY_ACTION,
                allowed=False,
                refusal_kind=REFUSAL_CAPABILITY,
                narration_constraint=_constraint_capability_refused(
                    claim_kind, claim_name, character, gate_reason
                ),
                signals=signals,
            )
        signals['category'] = CAPABILITY_ACTION
        return AdjudicationResult(
            category=CAPABILITY_ACTION,
            allowed=True,
            narration_constraint='',
            signals=signals,
        )

    # 3. COMBAT
    if COMBAT_RX.search(text):
        gate_ok, reason = _gate_combat(scene_state, combatants, active_turn)
        if gate_ok:
            active_name = (active_turn or {}).get('character_name', '') or ''
            signals['category'] = COMBAT_ACTION
            return AdjudicationResult(
                category=COMBAT_ACTION,
                allowed=True,
                narration_constraint=_constraint_combat_allowed(active_name),
                signals=signals,
            )
        signals.update({
            'category': COMBAT_ACTION,
            'allowed': 0,
            'refusal_kind': REFUSAL_COMBAT_INACTIVE,
        })
        return AdjudicationResult(
            category=COMBAT_ACTION,
            allowed=False,
            refusal_kind=REFUSAL_COMBAT_INACTIVE,
            narration_constraint=_constraint_combat_inactive(text[:140]),
            signals=signals,
        )

    # 3b. WEAPON capability — delegate to S9 and bind the verdict.
    # CONFIRMED → allow silently. VALID_BUT_UNCONFIGURED → allow (existing
    # advisory annotation continues to render). INVALID → REFUSE (first
    # producer in v1 — the activation point for §11.K).
    if character is not None:
        try:
            cap_decision = check_action_capability(
                text, character,
                skeleton_capabilities=skeleton_capabilities,
            )
            if cap_decision.needs_check and \
                    cap_decision.verdict is CapabilityVerdict.INVALID:
                signals.update({
                    'category': CAPABILITY_ACTION,
                    'allowed': 0,
                    'refusal_kind': REFUSAL_CAPABILITY,
                })
                return AdjudicationResult(
                    category=CAPABILITY_ACTION,
                    allowed=False,
                    refusal_kind=REFUSAL_CAPABILITY,
                    narration_constraint=_constraint_capability_refused(
                        'weapon', cap_decision.capability, character,
                        cap_decision.reason,
                    ),
                    signals=signals,
                )
        except Exception:
            # S9 failure is soft — do not let it block adjudication.
            pass

    # 4. CHECK — exploration / risky / contested intent
    intent = classify_action_intent(text,
                                     mode=(scene_state or {}).get('mode',
                                                                   'exploration'))
    if intent in (INTENT_EXPLORATION, INTENT_RISKY, INTENT_CONTESTED):
        skill = _skill_for_check(intent, text)
        dc, band = _dc_for_check(intent, scene_state, text)
        actor_name = character.name if character else ''
        roll_value, consumed = consume_recent_check(
            avrae_events, actor_name, skill,
        )
        if consumed and roll_value is not None:
            success = roll_value >= dc
            signals.update({
                'category': CHECK_ACTION,
                'allowed': 1 if success else 0,
                'refusal_kind': '' if success else REFUSAL_CHECK_FAILED,
                'skill': skill,
                'dc': dc,
                'band': band,
                'roll_consumed': 1,
                'roll_value': roll_value,
                'success': 1 if success else 0,
            })
            return AdjudicationResult(
                category=CHECK_ACTION,
                allowed=success,
                refusal_kind='' if success else REFUSAL_CHECK_FAILED,
                skill=skill,
                dc=dc,
                dc_band=band,
                roll_consumed=True,
                roll_value=roll_value,
                success=success,
                narration_constraint=_constraint_check_resolved(
                    skill, dc, band, roll_value, success,
                ),
                signals=signals,
            )
        # No buffered roll — emit CHECK_REQUIRED constraint
        signals.update({
            'category': CHECK_ACTION,
            'allowed': 1,
            'skill': skill,
            'dc': dc,
            'band': band,
        })
        return AdjudicationResult(
            category=CHECK_ACTION,
            allowed=True,
            skill=skill,
            dc=dc,
            dc_band=band,
            roll_consumed=False,
            success=None,
            narration_constraint=_constraint_check_required(skill, dc, band),
            signals=signals,
        )

    # 5. FREE — social / trivial / unmatched
    signals['category'] = FREE_ACTION
    return AdjudicationResult(
        category=FREE_ACTION,
        allowed=True,
        narration_constraint='',
        signals=signals,
    )


# ─────────────────────────────────────────────────────────
# Render helpers (top-of-prompt + HARD-STOP echo)
# ─────────────────────────────────────────────────────────

# Header for the top-of-prompt block. build_dm_context wraps with
# `=== ADJUDICATION RESULT ===` marker — see dnd_engine integration.

_HARD_STOP_ECHO = (
    "The ADJUDICATION RESULT block at the top of this prompt is BINDING. "
    "Do not narrate around the verdict. If the verdict refused the "
    "action, the action does not occur — narrate the world's response, "
    "not the player's intent."
)


def render_adjudication_block(result: AdjudicationResult) -> str:
    """Body for the top-of-prompt `=== ADJUDICATION RESULT ===` block.
    Empty when no constraint applies (FREE allowed, or FALLBACK)."""
    if not result or not result.narration_constraint:
        return ''
    return result.narration_constraint


def render_adjudication_hardstop_echo(result: AdjudicationResult) -> str:
    """Imperative restatement appended to HARD STOP RULES tail (§2).
    Empty when no constraint applies."""
    if not result or not result.narration_constraint:
        return ''
    return _HARD_STOP_ECHO


def adjudication_log_summary(result: AdjudicationResult) -> str:
    """Compact log line representation. Always-fire — empirical baseline."""
    if not result:
        return ("category=fallback allowed=1 refusal_kind= skill= dc=- "
                "band= roll_consumed=0 roll_value=- success=-")
    s = result.signals or {}
    dc = s.get('dc')
    rv = s.get('roll_value')
    succ = s.get('success')
    return (
        f"category={s.get('category', 'fallback')} "
        f"allowed={s.get('allowed', 1)} "
        f"refusal_kind={s.get('refusal_kind', '')} "
        f"skill={s.get('skill', '')} "
        f"dc={dc if dc is not None else '-'} "
        f"band={s.get('band', '')} "
        f"roll_consumed={s.get('roll_consumed', 0)} "
        f"roll_value={rv if rv is not None else '-'} "
        f"success={succ if succ is not None else '-'}"
    )


# ═════════════════════════════════════════════════════════
# Track 7 #2 — Multi-Action Arbitration
# ═════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────
# ArbitrationResult dataclass (§4)
# ─────────────────────────────────────────────────────────

# Category priority mapping for sort (higher = higher priority)
_CATEGORY_PRIORITY = {
    WORLD_BOUNDARY_ACTION: 5,
    COMBAT_ACTION:         4,
    CAPABILITY_ACTION:     3,
    CHECK_ACTION:          2,
    FREE_ACTION:           1,
    FALLBACK:              0,
}


@dataclass
class ArbitrationResult:
    """Multi-actor arbitration output. One per turn.

    actor_order contains PC CHARACTER NAMES (e.g. "Donovan", "Bruce"),
    NOT Discord usernames (e.g. "JORDAN", "TAZZ"). ACTOR_OMISSION
    substring detection in narration_verifier.py operates on these
    character name strings. The prompt-render shape "JORDAN (Donovan)"
    is human-clarity formatting in the rendered block only; the field
    stores character name strings. Per §11.Q lock.

    overridden_actors is a list[str], not a singular str, to capture
    the multi-overridden case (N≥3 actors, multiple contradicting
    lower-priority actors) from the all-pairs scan per §11.R.

    signals keys are explicit (not free-form dict-flatten). New keys
    require spec amendment per §11.E lock.
    """
    verdicts: list                    # list[AdjudicationResult], ordered by priority
    actor_order: list                 # list[str] CHARACTER NAMES, parallel to verdicts
    merge_plan: str = 'sequence'      # 'sequence' | 'override'
    primary_actor: str = ''           # CHARACTER NAME of highest-priority verdict's actor
    combined_constraint: str = ''     # imperative directive for build_dm_context
    overridden_actors: list = field(default_factory=list)  # per §11.R — list[str]
    signals: dict = field(default_factory=dict)


# ─────────────────────────────────────────────────────────
# Conflict detection helpers
# ─────────────────────────────────────────────────────────

_FREE_ASSERTS_SUCCESS_AGAINST_FAIL = re.compile(
    r'\b(?:agrees?|agreed|he\s+buys?\s+it|she\s+buys?\s+it|they\s+buy\s+it|'
    r'works?|worked|it\s+works?|lets?\s+(?:you|us)\s+(?:in|through|past)|'
    r'succeed(?:s|ed)?|you\s+(?:succeed|managed?|pull(?:s)?\s+it\s+off)|'
    r'believe(?:s|d)?|convinced?|persuaded?)\b',
    re.IGNORECASE,
)

_FREE_ASSERTS_FAIL_AGAINST_SUCCESS = re.compile(
    r'\b(?:fail(?:s|ed)?|you\s+fail|can\'?t\s+do|nuh\s+uh|not?\s+allowed?|'
    r'you\s+drop(?:ped)?|drops?\s+it|you\s+can\'?t|won\'?t\s+work|'
    r'doesn\'?t\s+work)\b',
    re.IGNORECASE,
)

_FREE_ASSERTS_CAPABILITY_WORKED = re.compile(
    r'\b(?:ignite(?:s|d)?|erupts?|takes?\s+hold|the\s+spell\s+(?:works?|fires?|'
    r'erupts?|takes?\s+hold)|the\s+(?:fireball|lightning|magic)\s+(?:erupts?|'
    r'strikes?|explodes?|fires?)|the\s+room\s+(?:ignites?|erupts?)|'
    r'fire\s+erupts?|magic\s+(?:surges?|fires?))\b',
    re.IGNORECASE,
)

_FREE_ASSERTS_COMBAT_DAMAGE = re.compile(
    r'\b(?:takes?\s+\d+\s+damage|the\s+(?:attack|blow|strike)\s+lands?|'
    r'(?:hits?|strikes?|slashes?)\s+(?:the|their|him|her)|'
    r'deals?\s+\d+|the\s+sword\s+connects?|lands?\s+the\s+hit)\b',
    re.IGNORECASE,
)


def _verdicts_contradict(high_verdict: AdjudicationResult,
                          low_verdict: AdjudicationResult,
                          low_text: str = '') -> bool:
    """Return True if low_verdict's FREE action text directly contradicts
    high_verdict's bound resolution.

    Contradiction requires BOTH:
      1. low_cat is FREE (unbound social claim)
      2. The free text explicitly asserts an outcome that opposes the
         high verdict's bound resolution (not just any FREE action — "I help
         him" is compatible with a CHECK success and does NOT contradict).

    Contradiction shapes (§5.1 step 3):
      - high=CHECK failed + low=FREE that asserts agreement/success (e.g.
        "he agrees with us") → CONFLICT
      - high=CHECK success + low=FREE that asserts failure ("you fail",
        "nuh uh you can't") → CONFLICT
      - high=CAPABILITY refused + low=FREE that asserts capability worked
        ("the room ignites") → CONFLICT
      - high=COMBAT refused + low=FREE that asserts damage landed → CONFLICT

    Non-conflicts ("I help him", "I attack", "I sip my drink") are
    compatible additions to the scene that do not assert an opposing outcome.
    """
    high_cat = getattr(high_verdict, 'category', FREE_ACTION)
    low_cat = getattr(low_verdict, 'category', FREE_ACTION)
    high_has_constraint = bool(getattr(high_verdict, 'narration_constraint', ''))
    text = (low_text or '').strip().lower()

    # Only FREE low-priority verdicts can constitute a social override
    if low_cat not in (FREE_ACTION, FALLBACK):
        return False

    # High-priority verdict must have a binding constraint to be overridable
    if not high_has_constraint:
        return False

    high_success = getattr(high_verdict, 'success', None)
    high_allowed = getattr(high_verdict, 'allowed', True)
    high_refusal_kind = getattr(high_verdict, 'refusal_kind', '')

    # CHECK failed: FREE asserts the thing Donovan was trying to do worked
    if high_cat == CHECK_ACTION and high_success is False:
        return bool(_FREE_ASSERTS_SUCCESS_AGAINST_FAIL.search(text))

    # CHECK succeeded: FREE asserts it failed
    if high_cat == CHECK_ACTION and high_success is True:
        return bool(_FREE_ASSERTS_FAIL_AGAINST_SUCCESS.search(text))

    # CAPABILITY refused: FREE asserts the capability worked
    if high_cat == CAPABILITY_ACTION and not high_allowed:
        return bool(_FREE_ASSERTS_CAPABILITY_WORKED.search(text))

    # COMBAT refused: FREE asserts damage landed
    if high_cat == COMBAT_ACTION and not high_allowed:
        return bool(_FREE_ASSERTS_COMBAT_DAMAGE.search(text))

    # WORLD_BOUNDARY refused: any FREE claim about the refused action is a conflict
    if high_cat == WORLD_BOUNDARY_ACTION and not high_allowed:
        return bool(text)  # any non-empty social assertion is contradictory

    return False


# ─────────────────────────────────────────────────────────
# Combined constraint render helpers
# ─────────────────────────────────────────────────────────

def _render_actor_block(actor: str, verdict: AdjudicationResult,
                         index: int) -> str:
    """Render one actor's verdict block for the combined_constraint."""
    cat = verdict.category or FALLBACK
    constraint = verdict.narration_constraint or ''
    allowed = verdict.allowed
    skill = verdict.skill or ''
    dc = verdict.dc
    success = verdict.success

    # Build a compact one-line verdict summary for the header
    if cat == CHECK_ACTION:
        if success is not None:
            outcome = 'SUCCESS' if success else 'FAILURE'
            rolled = verdict.roll_value
            roll_str = f" rolled {rolled}" if rolled is not None else ''
            summary = (f"{skill.replace('_',' ').title()} check"
                       + (f" DC {dc}" if dc else '')
                       + f"{roll_str}. {outcome}.")
        else:
            summary = (f"{skill.replace('_',' ').title()} check required"
                       + (f" DC {dc}" if dc else '') + '.')
    elif cat == CAPABILITY_ACTION and not allowed:
        summary = "CAPABILITY REFUSED."
    elif cat == CAPABILITY_ACTION:
        summary = "CAPABILITY ALLOWED."
    elif cat == COMBAT_ACTION and allowed:
        summary = "COMBAT ACTION — surface Avrae command."
    elif cat == COMBAT_ACTION and not allowed:
        summary = "COMBAT ACTION REFUSED — combat inactive."
    elif cat == WORLD_BOUNDARY_ACTION:
        summary = "WORLD BOUNDARY — action does not occur."
    elif cat == FREE_ACTION:
        summary = "FREE ACTION."
    else:
        summary = f"{cat.upper()}."

    block = f"{index}. {actor}: {summary}"
    if constraint:
        block += "\n   " + constraint.replace('\n', '\n   ')
    return block


def _render_combined_constraint_sequence(actor_verdict_pairs: list) -> str:
    """Render combined_constraint for merge_plan='sequence' (§5.2)."""
    count = len(actor_verdict_pairs)
    if count == 1:
        # Single-actor degenerate — byte-identical to Track 7 #1 block body
        actor, verdict = actor_verdict_pairs[0]
        return verdict.narration_constraint or ''

    header = (
        f"=== ARBITRATION RESULT ===\n"
        f"{count} players acted this turn. Address ALL in narration. "
        f"Order is binding:\n"
    )
    blocks = []
    for i, (actor, verdict) in enumerate(actor_verdict_pairs, 1):
        blocks.append(_render_actor_block(actor, verdict, i))
    footer = (
        "\nAddress each player by their actor name. "
        "All verdicts are independent — "
        "neither constrains the other's outcome. "
        "The narration must reflect all actors' actions in the same response, "
        "sequenced naturally."
    )
    return header + "\n\n".join(blocks) + footer


def _render_combined_constraint_override(
        actor_verdict_pairs: list,
        overridden_actors: list) -> str:
    """Render combined_constraint for merge_plan='override' (§5.2)."""
    count = len(actor_verdict_pairs)
    overridden_names = ', '.join(overridden_actors) if overridden_actors else '(unknown)'
    # Primary (highest-priority) actor = first in sorted list
    primary_actor = actor_verdict_pairs[0][0] if actor_verdict_pairs else '(unknown)'
    override_clause = (
        f"The verdicts CONFLICT. {primary_actor}'s verdict is BINDING; "
        f"{overridden_names}'s narration cannot reverse it."
    )

    header = (
        f"=== ARBITRATION RESULT ===\n"
        f"{count} players acted this turn. {override_clause}\n"
    )
    blocks = []
    for i, (actor, verdict) in enumerate(actor_verdict_pairs, 1):
        if actor in overridden_actors:
            cat = verdict.category or FREE_ACTION
            block = (
                f"{i}. {actor}: {cat.upper()} asserted something that "
                f"contradicts {primary_actor}'s resolved outcome."
            )
        else:
            block = _render_actor_block(actor, verdict, i)
        blocks.append(block)

    overridden_reactions = []
    for name in overridden_actors:
        overridden_reactions.append(
            f"  - {name}: narrate their REACTION to the outcome — "
            f"protest, lunge, adapt — but do NOT narrate the binding "
            f"actor's resolved outcome as reversed."
        )

    footer = (
        f"\nNarrate {primary_actor}'s resolved outcome. "
        f"Then narrate EACH overridden actor's REACTION to that outcome:\n"
        + "\n".join(overridden_reactions)
        + f"\n{primary_actor}'s verdict stands."
    )
    return header + "\n\n".join(blocks) + footer


# ─────────────────────────────────────────────────────────
# Main arbitration entry point
# ─────────────────────────────────────────────────────────

def arbitrate(actions: list,
              scene_state=None,
              characters: Optional[list] = None,
              combatants: Optional[list] = None,
              active_turn=None,
              intent_per_actor: Optional[dict] = None,
              avrae_events: Optional[list] = None,
              skeleton_capabilities: Optional[dict] = None,
              character_cache=None) -> ArbitrationResult:
    """Multi-actor arbitration entry point (Track 7 #2).

    actions: list of (actor_name, text) or (actor_name, text, user_id) tuples.
             actor_name must be the CHARACTER NAME (e.g. "Donovan", not the
             Discord username "JORDAN"). Per §11.Q lock.

    Returns ArbitrationResult. Caller wraps in try/except (Doctrine §59);
    on exception, fall back to first-actor-only single adjudicate() call
    (Track 7 #1 path). Never blocks narration.

    Single-actor degenerate case: produces ArbitrationResult with one
    verdict, merge_plan='sequence', combined_constraint byte-identical to
    what render_adjudication_block(adjudicate()) would produce.

    Soft-fail behavior for the Track 7 #1 fallback path:
      raise exceptions freely — caller catches them.
    """
    if not ARBITRATION_ENABLED:
        # Feature flag off: degrade to single-actor (first action only)
        actions = list(actions or [])
        if not actions:
            return _single_actor_fallback(
                '', scene_state, characters, combatants, active_turn,
                avrae_events, skeleton_capabilities, character_cache,
            )
        first = actions[0]
        actor_name = first[0] if len(first) >= 1 else ''
        text = first[1] if len(first) >= 2 else ''
        return _single_actor_fallback(
            text, scene_state, characters, combatants, active_turn,
            avrae_events, skeleton_capabilities, character_cache,
            actor_name=actor_name,
        )

    actions = list(actions or [])
    if not actions:
        return _single_actor_fallback(
            '', scene_state, characters, combatants, active_turn,
            avrae_events, skeleton_capabilities, character_cache,
        )

    # ── Step 1: Per-actor adjudication ──────────────────────────────
    verdict_pairs = []  # list of (actor_name, AdjudicationResult, arrival_index)
    chars_by_name = {}
    if characters:
        for c in characters:
            name = c.get('name') if isinstance(c, dict) else getattr(c, 'name', '')
            if name:
                chars_by_name[name] = c

    for arrival_idx, action_tup in enumerate(actions):
        actor_name = action_tup[0] if len(action_tup) >= 1 else ''
        text = action_tup[1] if len(action_tup) >= 2 else ''

        # Resolve cached context (character_cache is orch.get_cached_context)
        char_ctx = None
        if character_cache is not None:
            try:
                char_ctx = character_cache(actor_name)
            except Exception:
                char_ctx = None

        if char_ctx is None:
            # Cache miss — defer per §11.P (partial-projections doctrine)
            fallback_verdict = AdjudicationResult(
                category=FREE_ACTION,
                allowed=True,
                refusal_kind='no_character_context',
                narration_constraint='',
                signals={
                    'category': FREE_ACTION,
                    'allowed': 1,
                    'refusal_kind': 'no_character_context',
                    'input_preview': (text or '')[:140],
                },
            )
            verdict_pairs.append((actor_name, fallback_verdict, arrival_idx))
            continue

        try:
            verdict = adjudicate(
                player_input=text,
                scene_state=scene_state,
                character=char_ctx,
                combatants=combatants,
                active_turn=active_turn,
                avrae_events=avrae_events,
                skeleton_capabilities=skeleton_capabilities,
            )
        except Exception:
            verdict = AdjudicationResult(
                category=FALLBACK,
                allowed=True,
                narration_constraint='',
                signals={'category': FALLBACK, 'allowed': 1,
                         'input_preview': (text or '')[:140]},
            )
        verdict_pairs.append((actor_name, verdict, arrival_idx))

    # ── Step 2: Priority sort ────────────────────────────────────────
    # Primary key: category priority (descending). Tiebreak: arrival index
    # (ascending = earlier first). Per §11.C, §5.1 step 2.
    verdict_pairs.sort(
        key=lambda t: (-_CATEGORY_PRIORITY.get(t[1].category, 0), t[2])
    )

    actor_order = [t[0] for t in verdict_pairs]
    verdicts = [t[1] for t in verdict_pairs]
    primary_actor = actor_order[0] if actor_order else ''

    # ── Step 3: All-pairs conflict detection (§11.R, §5.1 step 3) ───
    # Build a map from actor_name → original action text for text-based
    # contradiction detection. The sorted verdict_pairs carry arrival_idx
    # but not text; rebuild from actions.
    _actor_text_map: dict = {}
    for action_tup in actions:
        a_name = action_tup[0] if len(action_tup) >= 1 else ''
        a_text = action_tup[1] if len(action_tup) >= 2 else ''
        _actor_text_map[a_name] = a_text

    # For every pair (i, j) where i < j (so i is higher-priority),
    # check if the lower-priority verdict contradicts the higher-priority
    # bound resolution. Collect every overridden actor (deduped, in
    # priority order they appear in the sorted list).
    overridden_set = []  # ordered, deduped
    n = len(verdict_pairs)
    for i in range(n):
        for j in range(i + 1, n):
            high_actor, high_verdict, _ = verdict_pairs[i]
            low_actor, low_verdict, _ = verdict_pairs[j]
            low_text = _actor_text_map.get(low_actor, '')
            if _verdicts_contradict(high_verdict, low_verdict, low_text):
                if low_actor not in overridden_set:
                    overridden_set.append(low_actor)

    merge_plan = 'override' if overridden_set else 'sequence'

    # ── Step 4: Combined constraint render ──────────────────────────
    # Per §11.O: sibling deduplication is per-actor scope (each verdict
    # suppresses ITS OWN advisory siblings). For the combined render, we
    # use each verdict's narration_constraint as-is (already deduplicated
    # per-verdict by adjudicate()'s §11.L logic).
    actor_verdict_pairs = list(zip(actor_order, verdicts))
    if merge_plan == 'sequence':
        combined = _render_combined_constraint_sequence(actor_verdict_pairs)
    else:
        combined = _render_combined_constraint_override(
            actor_verdict_pairs, overridden_set
        )

    # ── Step 5: Build signals (explicit keys per §11.E) ─────────────
    input_chars_per_actor = {}
    for action_tup in actions:
        a_name = action_tup[0] if len(action_tup) >= 1 else ''
        a_text = action_tup[1] if len(action_tup) >= 2 else ''
        input_chars_per_actor[a_name] = len(a_text or '')

    signals = {
        'actors': len(actor_order),
        'verdicts': ':'.join(v.category for v in verdicts),
        'merge_plan': merge_plan,
        'primary_actor': primary_actor,
        'overridden_actors': ','.join(overridden_set) if overridden_set else '-',
        'priority_order': ','.join(actor_order),
        'input_total_chars': sum(input_chars_per_actor.values()),
        'input_per_actor': ','.join(
            f"{a}:{c}" for a, c in input_chars_per_actor.items()
        ),
    }

    return ArbitrationResult(
        verdicts=verdicts,
        actor_order=actor_order,
        merge_plan=merge_plan,
        primary_actor=primary_actor,
        combined_constraint=combined,
        overridden_actors=overridden_set,
        signals=signals,
    )


def _single_actor_fallback(text: str,
                            scene_state=None,
                            characters=None,
                            combatants=None,
                            active_turn=None,
                            avrae_events=None,
                            skeleton_capabilities=None,
                            character_cache=None,
                            actor_name: str = '') -> ArbitrationResult:
    """Build a single-actor ArbitrationResult for degenerate or fallback cases."""
    char_ctx = None
    if character_cache is not None and actor_name:
        try:
            char_ctx = character_cache(actor_name)
        except Exception:
            char_ctx = None

    try:
        verdict = adjudicate(
            player_input=text,
            scene_state=scene_state,
            character=char_ctx,
            combatants=combatants,
            active_turn=active_turn,
            avrae_events=avrae_events,
            skeleton_capabilities=skeleton_capabilities,
        )
    except Exception:
        verdict = AdjudicationResult(
            category=FALLBACK,
            allowed=True,
            narration_constraint='',
            signals={'category': FALLBACK, 'allowed': 1,
                     'input_preview': (text or '')[:140]},
        )

    combined = verdict.narration_constraint or ''
    actor = actor_name or '?'
    return ArbitrationResult(
        verdicts=[verdict],
        actor_order=[actor],
        merge_plan='sequence',
        primary_actor=actor,
        combined_constraint=combined,
        overridden_actors=[],
        signals={
            'actors': 1,
            'verdicts': verdict.category,
            'merge_plan': 'sequence',
            'primary_actor': actor,
            'overridden_actors': '-',
            'priority_order': actor,
            'input_total_chars': len(text or ''),
            'input_per_actor': f"{actor}:{len(text or '')}",
        },
    )


# ─────────────────────────────────────────────────────────
# Arbitration render helpers
# ─────────────────────────────────────────────────────────

_ARBITRATION_HARD_STOP_ECHO = (
    "The ARBITRATION RESULT block at the top of this prompt is BINDING. "
    "Do not narrate around the verdicts. If a verdict refused an action, "
    "that action does not occur — narrate the world's response, not the "
    "player's intent. Every non-FREE actor named in the ARBITRATION RESULT "
    "must be addressed by character name in the narration."
)


def render_arbitration_block(result: ArbitrationResult) -> str:
    """Body for the top-of-prompt === ARBITRATION RESULT === block.
    For single-actor degenerate case, returns the bare narration_constraint
    (byte-identical to Track 7 #1 render_adjudication_block output).
    For multi-actor, returns the combined_constraint with === header embedded.
    """
    if not result or not result.combined_constraint:
        return ''
    # Single-actor degenerate: combined_constraint is already the bare
    # narration_constraint text — no extra header needed (build_dm_context
    # wraps with === ARBITRATION RESULT === itself).
    return result.combined_constraint


def render_arbitration_hardstop_echo(result: ArbitrationResult) -> str:
    """Imperative restatement for HARD STOP RULES tail.
    Empty when no binding constraint (single-actor FREE/FALLBACK or no actions)."""
    if not result or not result.combined_constraint:
        return ''
    return _ARBITRATION_HARD_STOP_ECHO


def arbitration_log_summary(result: ArbitrationResult,
                              campaign_id=None) -> str:
    """Per-turn log line per spec §6.4. Always-fire — empirical baseline.

    arbitration: campaign={N} actors={count} verdicts={cat:cat}
                 merge_plan={sequence|override} primary_actor={name}
                 overridden_actors={A,B|-} priority_order={A,B,C}
                 input_total_chars={N} input_per_actor={a:N,b:M}
    """
    if not result:
        return (f"arbitration: campaign={campaign_id or '?'} "
                f"actors=0 verdicts= merge_plan=sequence primary_actor=- "
                f"overridden_actors=- priority_order=- "
                f"input_total_chars=0 input_per_actor=")
    s = result.signals or {}
    return (
        f"arbitration: campaign={campaign_id or '?'} "
        f"actors={s.get('actors', len(result.actor_order))} "
        f"verdicts={s.get('verdicts', '')} "
        f"merge_plan={s.get('merge_plan', result.merge_plan)} "
        f"primary_actor={s.get('primary_actor', result.primary_actor)!r} "
        f"overridden_actors={s.get('overridden_actors', '-')} "
        f"priority_order={s.get('priority_order', '')} "
        f"input_total_chars={s.get('input_total_chars', 0)} "
        f"input_per_actor={s.get('input_per_actor', '')}"
    )
