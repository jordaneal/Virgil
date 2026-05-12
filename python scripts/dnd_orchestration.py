"""
dnd_orchestration.py
─────────────────────────────────────────────────────────
Phase 1.1 of the gameplay-orchestration plan.

Two responsibilities, intentionally narrow:

  1. CHARACTER CONTEXT CACHE
     - get_character_context(name) returns a stable struct of
       static identity (race, class, level, AC, weapons, spells,
       proficiencies, passive perception, narrative_tags).
     - Lives in-process, keyed by character name, cleared on
       bot restart or explicit invalidation.
     - Volatile state (current HP, slots, conditions) is NOT
       cached here — Avrae remains source of truth for those,
       and Virgil reads them from MECHANICAL EVENTS.

  2. ROLL DISCIPLINE RULES ENGINE
     - classify_action_intent(text, mode) → IntentTag
     - should_call_roll(intent, mode, character_ctx) → RollDecision
     - Narration consumes the RollDecision; it does not make
       its own roll-or-no-roll judgment in prose.

This module imports nothing from discord. It's pure logic so it
can be unit-tested without the bot running.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ─────────────────────────────────────────────────────────
# CHARACTER CONTEXT CACHE
# ─────────────────────────────────────────────────────────

# Class → narrative tags. Conservative; we only tag what we're
# very confident about. Everything else gets inferred from the
# attack list or proficiencies at parse time.
CLASS_TAG_HINTS = {
    'rogue':     {'stealth_specialist', 'lockpicker', 'skirmisher'},
    'fighter':   {'frontliner', 'martial'},
    'paladin':   {'frontliner', 'divine_caster', 'healer'},
    'cleric':    {'divine_caster', 'healer'},
    'wizard':    {'arcane_caster', 'scholar'},
    'sorcerer':  {'arcane_caster'},
    'warlock':   {'arcane_caster'},
    'bard':      {'arcane_caster', 'social_specialist'},
    'druid':     {'primal_caster', 'wilderness'},
    'ranger':    {'wilderness', 'ranged_combatant'},
    'monk':      {'martial', 'mobile'},
    'barbarian': {'frontliner', 'martial'},
    'artificer': {'arcane_caster', 'tinkerer'},
}

# Race → narrative tags. Same conservatism — only mark what's
# universally true for the race.
RACE_TAG_HINTS = {
    'dwarf':       {'darkvision'},
    'elf':         {'darkvision'},
    'half-elf':    {'darkvision'},
    'half-orc':    {'darkvision'},
    'gnome':       {'darkvision'},
    'tiefling':    {'darkvision'},
    'drow':        {'darkvision', 'sunlight_sensitivity'},
    'goliath':     {'mountain_native'},
    'halfling':    set(),  # no darkvision
    'human':       set(),
}


@dataclass
class CharacterContext:
    """Static character data we reference for narration. Volatile
    state (HP/slots/conditions) is not in here — that's Avrae's job."""
    name: str
    race: str = ''
    char_class: str = ''
    level: int = 1
    ac: int = 10
    hp_max: int = 1
    initiative: int = 0
    passive_perception: int = 10
    saves: dict[str, int] = field(default_factory=dict)
    skills: dict[str, int] = field(default_factory=dict)
    attacks: list[str] = field(default_factory=list)
    resistances: list[str] = field(default_factory=list)
    narrative_tags: set[str] = field(default_factory=set)

    # Cache hygiene
    last_refresh: float = 0.0
    source_message_id: Optional[int] = None
    version: int = 1

    @property
    def primary_name(self) -> str:
        # First whitespace token of name. Used as the DM-facing address form
        # when the full name is multi-token ("Donovan Ruby" -> "Donovan").
        # Single-token names return unchanged.
        if not self.name:
            return self.name
        return self.name.split()[0]

    def to_prompt_block(self) -> str:
        """Render as a compact block for the DM system prompt."""
        skill_top = sorted(self.skills.items(), key=lambda x: -x[1])[:5]
        skill_str = ", ".join(f"{s} {b:+d}" for s, b in skill_top) or "—"
        atk_str = "; ".join(self.attacks[:5]) if self.attacks else "—"
        tag_str = ", ".join(sorted(self.narrative_tags)) or "—"
        addr = f" (address as {self.primary_name})" if self.primary_name != self.name else ""
        return (
            f"{self.name}{addr} — Level {self.level} {self.race} {self.char_class}\n"
            f"AC {self.ac}, HP {self.hp_max}, Initiative {self.initiative:+d}, "
            f"Passive Perception {self.passive_perception}\n"
            f"Notable skills: {skill_str}\n"
            f"Attacks: {atk_str}\n"
            f"Tags: {tag_str}"
        )

    def to_compact_line(self) -> str:
        """One-line summary for multi-actor narration. Used when 2+ actors
        are in the same batch — full per-actor sheets would balloon the
        prompt. Format: 'Name — Class Level | tags: t1, t2, t3'."""
        tags = sorted(self.narrative_tags)[:5]
        tag_str = ", ".join(tags) if tags else "—"
        cls = self.char_class or "?"
        addr = f" (address as {self.primary_name})" if self.primary_name != self.name else ""
        return f"{self.name}{addr} — {cls} {self.level} | tags: {tag_str}"


_CHARACTER_CACHE: dict[str, CharacterContext] = {}


def get_cached_context(name: str) -> Optional[CharacterContext]:
    return _CHARACTER_CACHE.get(name)


def set_cached_context(ctx: CharacterContext) -> None:
    ctx.last_refresh = time.time()
    _CHARACTER_CACHE[ctx.name] = ctx


def invalidate_cache(name: str | None = None) -> None:
    """Drop one character's cache or the entire cache."""
    if name is None:
        _CHARACTER_CACHE.clear()
    else:
        _CHARACTER_CACHE.pop(name, None)


# ── Phase 6 — Identity reconciliation ─────────────────────────────────────────
# Resolve an observed actor name (from any source — sheet embed, roll embed,
# init label, batched display) to a bound dnd_characters row in this campaign.
# STRICT-ONLY: exact-equality on canonicalized strings against canonical_name
# OR aliases. No substring fallback. See PHASE_6_IDENTITY_SPEC §4.
#
# Aliases are durable, persisted in dnd_characters.aliases. Operators add them
# via register_actor_alias when a real-world equivalence pattern surfaces;
# the system never decides equivalence on its own.

def resolve_actor(campaign_id: int, raw_name: str) -> Optional[dict]:
    """Map an observed name to a bound dnd_characters row by exact-equality
    match on canonicalized strings. Returns the row dict (with canonical_name
    + aliases populated) or None on miss. Never raises.

    Resolution order:
      1. canonicalize_actor_name(raw_name) → cand
      2. Exact match against dnd_characters.canonical_name
      3. Exact match against any entry in dnd_characters.aliases
      4. None on miss

    No substring matching. No fuzzy logic. See spec §4 for rationale.
    """
    if not raw_name:
        return None
    from dnd_engine import (  # noqa: E402
        canonicalize_actor_name,
        get_character_by_canonical,
        get_character_by_alias,
    )
    cand = canonicalize_actor_name(raw_name)
    if not cand:
        return None
    hit = get_character_by_canonical(campaign_id, cand)
    if hit is not None:
        return hit
    hit = get_character_by_alias(campaign_id, cand)
    if hit is not None:
        return hit
    return None


def register_actor_alias(campaign_id: int, controller_id: str, alias: str) -> bool:
    """Append `alias` (canonicalized) to the alive bound character of
    `controller_id` in `campaign_id`. Idempotent. Returns True if the table
    was updated, False if the alias was already there or the controller has
    no bound character. Logs `actor_alias_added: ...` on success.

    This is the OPERATOR ACTION that records a durable equivalence after
    `unresolved_actor:` log lines surface a real pattern.
    """
    if not (controller_id and alias):
        return False
    from dnd_engine import (  # noqa: E402
        canonicalize_actor_name, log,
        get_character_by_controller, append_character_alias,
    )
    canonical_alias = canonicalize_actor_name(alias)
    if not canonical_alias:
        return False
    char = get_character_by_controller(campaign_id, str(controller_id))
    if char is None:
        log(f"register_actor_alias: no bound character for "
            f"campaign={campaign_id} controller={controller_id} "
            f"alias='{canonical_alias}', refused")
        return False
    appended = append_character_alias(char['id'], canonical_alias)
    if appended:
        log(f"actor_alias_added: campaign={campaign_id} character_id={char['id']} "
            f"name='{char.get('name')}' alias='{canonical_alias}'")
    return appended


def refresh_canonical_name(controller_id: str, sheet_name: str,
                           campaign_id: Optional[int] = None) -> None:
    """Set canonical_name on the alive bound character(s) of `controller_id`
    based on a freshly-observed sheet embed. Called when parse_avrae_sheet_embed
    yields a context for a known controller (e.g. cache_warm or an in-session
    !sheet).

    If the existing canonical_name differs from the new one, the OLD canonical
    is appended to aliases (so events tagged with the old form still resolve).
    No-op if sheet_name canonicalizes to '' or matches existing.
    """
    if not (controller_id and sheet_name):
        return
    from dnd_engine import (  # noqa: E402
        canonicalize_actor_name, log,
        get_character_by_controller,
        set_character_canonical_name, append_character_alias,
    )
    new_canonical = canonicalize_actor_name(sheet_name)
    if not new_canonical:
        return
    # If campaign_id provided, scope. Otherwise apply to whichever campaigns
    # have a bound character for this controller. For v1, the campaign-scoped
    # path is enough since cache_warm is per-guild/per-campaign.
    if campaign_id is None:
        # Caller didn't scope; we can't loop without knowing campaigns. Skip.
        return
    char = get_character_by_controller(campaign_id, str(controller_id))
    if char is None:
        return
    existing = (char.get('canonical_name') or '').strip().lower()
    if existing == new_canonical:
        return  # no change
    if existing:
        # Preserve the old canonical as an alias so stale events still resolve.
        append_character_alias(char['id'], existing)
    set_character_canonical_name(char['id'], new_canonical)
    log(f"canonical_name_refreshed: campaign={campaign_id} character_id={char['id']} "
        f"controller={controller_id} '{existing}' -> '{new_canonical}'")


def parse_avrae_sheet_embed(embed) -> Optional[CharacterContext]:
    """Build a CharacterContext from an Avrae !sheet / !beyond embed.

    Returns None if the embed doesn't look like a character sheet."""
    name = ''
    if embed.author and embed.author.name:
        name = embed.author.name.strip()
    if not name and embed.title:
        name = embed.title.strip()
    if not name:
        return None

    desc = (embed.description or '').strip()
    if not desc:
        return None

    ctx = CharacterContext(name=name)

    # Line 1: "Race Class Level" — but only if it actually looks like one.
    # !coin / !item embeds have descriptions starting with "**Label**: value"
    # patterns whose final token is also a digit (e.g. "**Platinum**: 0"),
    # which would extract garbage class names. Two-part guard: parsed level
    # must be in D&D range (1-20), AND the head tokens (race/class portion)
    # must contain no asterisks (markdown markers indicate non-sheet embeds).
    lines = [l.strip() for l in desc.split('\n') if l.strip()]
    if lines:
        tokens = lines[0].split()
        if len(tokens) >= 2 and tokens[-1].isdigit():
            level = int(tokens[-1])
            if 1 <= level <= 20:
                head = tokens[:-1]
                head_str = ' '.join(head)
                if '*' not in head_str:
                    ctx.level = level
                    if len(head) >= 2:
                        ctx.char_class = head[-1]
                        ctx.race = ' '.join(head[:-1])
                    else:
                        ctx.char_class = head[0] if head else ''

    # Subsequent lines are "**Field**: value" — pull what we care about
    body = '\n'.join(lines[1:])

    def grab(label: str, default: str = '') -> str:
        m = re.search(rf"\*\*{re.escape(label)}\*\*:?\s*([^\n*]+)", body, re.IGNORECASE)
        return m.group(1).strip() if m else default

    ac_raw = grab('AC')
    if ac_raw:
        m = re.search(r'\d+', ac_raw)
        if m:
            ctx.ac = int(m.group(0))

    hp_raw = grab('HP')
    if hp_raw:
        m = re.search(r'(\d+)\s*/\s*(\d+)', hp_raw)
        if m:
            ctx.hp_max = int(m.group(2))
        else:
            m = re.search(r'\d+', hp_raw)
            if m:
                ctx.hp_max = int(m.group(0))

    init_raw = grab('Initiative')
    if init_raw:
        m = re.search(r'[+-]?\d+', init_raw)
        if m:
            ctx.initiative = int(m.group(0))

    senses = grab('Senses')
    if senses:
        m = re.search(r'passive\s+Perception\s+(\d+)', senses, re.IGNORECASE)
        if m:
            ctx.passive_perception = int(m.group(1))
        if 'darkvision' in senses.lower():
            ctx.narrative_tags.add('darkvision')

    saves_raw = grab('Save Proficiencies') or grab('Saves')
    for m in re.finditer(r'(\w+)\s*([+-]\d+)', saves_raw):
        ctx.saves[m.group(1).lower()] = int(m.group(2))

    skills_raw = grab('Skill Proficiencies') or grab('Skills')
    for m in re.finditer(r'([A-Za-z][A-Za-z\s]+?)\s*([+-]\d+)', skills_raw):
        skill = m.group(1).strip().lower()
        # Strip trailing parenthetical like "(Expertise)"
        skill = re.sub(r'\s*\(.*?\)\s*$', '', skill).strip()
        if skill and skill not in ctx.skills:
            ctx.skills[skill] = int(m.group(2))

    resistances = grab('Resistances')
    if resistances:
        ctx.resistances = [r.strip().lower() for r in resistances.split(',')]

    # Attacks come from a field, not the description
    for f in embed.fields:
        if f.name.lower() == 'attacks':
            for line in (f.value or '').split('\n'):
                line = line.strip()
                if not line:
                    continue
                m = re.match(r'\*\*([^*]+)\*\*', line)
                if m:
                    ctx.attacks.append(m.group(1).strip())

    # Narrative tag inference
    cls_lower = ctx.char_class.lower()
    race_lower = ctx.race.lower()
    for race_key, tags in RACE_TAG_HINTS.items():
        if race_key in race_lower:
            ctx.narrative_tags |= tags
    for cls_key, tags in CLASS_TAG_HINTS.items():
        if cls_key in cls_lower:
            ctx.narrative_tags |= tags

    # Inferred from skill proficiencies
    if ctx.skills.get('stealth', 0) >= 5:
        ctx.narrative_tags.add('stealth_specialist')
    if ctx.skills.get('persuasion', 0) >= 5 or ctx.skills.get('deception', 0) >= 5:
        ctx.narrative_tags.add('social_specialist')
    if ctx.skills.get('investigation', 0) >= 5 or ctx.skills.get('arcana', 0) >= 5:
        ctx.narrative_tags.add('scholar')

    # Inferred from attacks
    atk_blob = ' '.join(ctx.attacks).lower()
    if any(w in atk_blob for w in ('shortbow', 'longbow', 'crossbow', 'sling')):
        ctx.narrative_tags.add('ranged_combatant')
    if 'thieves' in atk_blob or cls_lower == 'rogue':
        ctx.narrative_tags.add('lockpicker')

    # Sentinel: refuse embeds that match the sheet *shape* (author name +
    # description) but contain no actual character data. !coin / !item /
    # similar Avrae embeds share the structural shape but populate none of
    # the real-sheet fields. Distinguish by requiring at least ONE
    # parsed-from-text indicator to be non-default.
    if (ctx.level == 1 and not ctx.race and not ctx.char_class
            and ctx.ac == 10 and ctx.hp_max == 1 and not ctx.attacks):
        return None

    return ctx


# ─────────────────────────────────────────────────────────
# ROLL DISCIPLINE RULES ENGINE
# ─────────────────────────────────────────────────────────

# Coarse intent tags. Order matters: first match wins in classify_action_intent.
INTENT_TRIVIAL    = 'trivial'         # walk, look around plainly, drink, sit, talk casually
INTENT_RISKY      = 'risky'           # action with uncertain outcome, no opposed actor
INTENT_CONTESTED  = 'contested'       # action against another willful actor (deceive, intimidate)
INTENT_COMBAT     = 'combat'          # attack/cast in combat — defer to Avrae
INTENT_EXPLORATION = 'exploration'    # search, investigate, listen, climb, jump
INTENT_SOCIAL     = 'social'          # talking, negotiating, gathering info
INTENT_META       = 'meta'            # OOC, rules question, asking the DM something


META_RX = re.compile(
    r'^(ooc:|\(|out of character|how do i|what does|am i supposed|can i|'
    r'do i need|how many|am i still|is this|wait,? )',
    re.IGNORECASE
)
COMBAT_RX = re.compile(
    # `fire`, `shoot`, and `loose` were previously listed but dropped —
    # all three have non-combat homonyms common in fantasy narration
    # ("around the fire", "loose stones", noun "shoot of a plant") with
    # no reliable regex-level disambiguation. The remaining verbs are
    # unambiguous combat actions. Cost of dropping these three is the
    # COMBAT-intent nudge ("Avrae handles attack rolls") doesn't fire on
    # "I fire my bow" or "I shoot the deer" — but Avrae mechanics work
    # regardless of the nudge, and players using Avrae already know the
    # !attack / !cast syntax.
    r'\b(attack|swing|strike|stab|slash|cast|smite|'
    r'hit|hurl|throw|charge|pounce|engage|fight|kill|finish|drop|'
    r'punch|kick|grapple|tackle|shove|wrestle|bash|smash|jab|'
    r'headbutt|brawl|pummel|throttle|choke|bite|claw|slam|'
    r'knee\s|elbow\s|'
    r'behead|decapitate|slay|murder|execute|gut|eviscerate|'
    r'impale|skewer|slice|maim|wound|injure|crush|mangle|butcher)\b',
    re.IGNORECASE
)
EXPLORATION_RX = re.compile(
    # Ship A live-verify patch (S36 #2): expanded verb coverage so natural
    # operator phrasings ("look closely", "find a hidden detail", "read
    # carefully", "check the parchment", "lift the heavy stone", etc.)
    # route to exploration intent instead of falling through to social
    # default or being shadowed by TRIVIAL_RX's bare-`look` match.
    r'\b('
    # Original verbs:
    r'search|investigate|examine|inspect|study|listen|'
    r'climb|jump|leap|swim|tracks?|follow|'
    r'disarm|pick|unlock|squeeze|crawl|'
    # Look-qualified forms (TRIVIAL no longer shadows these). Two clauses:
    # 1) direct adverbial: "look closely/carefully/etc"
    # 2) "look around <adverb>" — bare "look around" stays trivial; only
    #    qualified-with-adverb "look around carefully" is exploration.
    r'look\s+(?:closely|carefully|harder|hard|closer|over|inside|'
    r'behind|under|intently|slowly|methodically)|'
    r'look\s+around\s+(?:carefully|closely|harder|hard|intently|'
    r'slowly|methodically)|'
    # Idiomatic "take a closer/careful/hard look":
    r'take\s+(?:a|another)\s+(?:closer|careful|hard|harder|good|long)'
    r'\s+look|'
    # Investigative natural verbs. `peek` gets fixed-width negative
    # lookbehinds to exclude the "steal a peek" / "sneak a peek" idioms
    # that the existing RISKY_RX lookahead also recognizes as social
    # (parallel idiom handling — keep both regexes consistent).
    r'find|read\s+(?:closely|carefully|over)|peer|'
    r'(?<!steal a )(?<!sneak a )peek|scrutinize|'
    r'notice|spot|comb|scan|figure\s+out|discern|'
    # check-for variants — broader than just traps:
    r'check\s+(?:for|the|over|inside|behind|under)|'
    # Physical exertion (athletics-shaped). Object-between patterns use
    # bounded gap so "push the bookshelf aside" / "smash the chest open"
    # match without being too greedy.
    r'lift|hoist|pry|wrench|haul|drag|tug|yank|scramble|'
    r'force\s+(?:open|the|it|\w+\s+open)|'
    r'break\s+(?:open|down|through|\w+\s+(?:open|down|through))|'
    r'smash\s+(?:\S+\s+){0,4}(?:open|down|through|apart)|'
    r'kick\s+(?:open|down|\w+\s+(?:open|down))|'
    r'push\s+(?:\S+\s+){0,4}(?:over|down|through|aside|away|out|'
    r'across|back|apart)|'
    r'shove\s+(?:\S+\s+){0,4}(?:open|aside|over|down|through|away)|'
    r'shoulder\s+(?:\S+\s+){0,2}(?:open|down|through|aside)|'
    r'swing\s+(?:on|off|across|over)|'
    # Acrobatics-shaped (mobility + balance):
    r'dodge|tumble|vault|balance(?!\s+sheet)|'
    r'roll\s+(?:under|past|through|away|aside)|'
    r'duck\s+(?:under|behind|into|past)|'
    # Stealth-shaped exploration (non-RISKY stealth movement):
    r'creep|slink|tiptoe|sneak\s+up|'
    # Skill-noun forms — "use perception", "roll investigation", "athletics check"
    r'perception|investigation|survival|athletics|acrobatics'
    r')\b',
    re.IGNORECASE
)
CONTESTED_RX = re.compile(
    r'\b(persuade|convince|deceive|lie to|bluff|intimidate|threaten|'
    r'menace|seduce|charm|trick|fast-?talk|sneak past|hide from|'
    r'bargain|haggle|interrogate|'
    r'disguise|impersonate|imitate|pose\s+as|'
    # Skill-noun forms — players reference skills by name in natural play:
    # "I use persuasion", "make a deception check", "roll intimidation".
    r'persuasion|deception|intimidation|insight|performance)\b',
    re.IGNORECASE
)
SOCIAL_RX = re.compile(
    r'\b(ask|tell|greet|introduce|mention|inquire|chat|gossip|'
    r'listen to|approach .* and|speak (?:to|with)|talk (?:to|with))\b',
    re.IGNORECASE
)
RISKY_RX = re.compile(
    # Negative lookaheads on `steal` and `sneak` exclude idiomatic uses
    # ("steal a glance", "sneak a peek") that aren't real stealth/larceny.
    # The idiom noun list is enumerated explicitly so real larceny with
    # concrete objects ("steal a gem", "sneak a dagger from the table")
    # still matches. New idioms can be appended as observed.
    r'\b('
    r'steal(?!\s+a\s+(?:glance|peek|look|sip|taste|bite|kiss|moment|breath|nap|hug))'
    r'|sneak(?!\s+a\s+(?:peek|glance|look|sip|taste|bite|kiss|hug))'
    r'|pickpocket|sabotage|forge|tail|shadow|eavesdrop|'
    r'pick up the .* without|grab .* quietly|slip|'
    r'snatch|swipe|pilfer|filch|nick|'
    r'take .* (?:from|off|away from) (?:him|her|them|his|her|their|someone|the\s\w+)|'
    r'take (?:his|her|their) \w+|'
    r'grab .* (?:from|off|out of)|'
    r'rip .* (?:from|off|out of)|'
    r'pry .* (?:from|off|out of)|'
    r'wrest|'
    r'hide|conceal|vanish|disappear|blend\s+in|'
    # Skill-noun: "I use stealth", "roll stealth"
    r'stealth)\b',
    re.IGNORECASE
)
TRIVIAL_RX = re.compile(
    # Ship A live-verify patch (S36 #2): removed bare `look` from the
    # alternation. Previously `look(?: around)?` would short-circuit on
    # any sentence starting with "look" — including "look closely",
    # "look carefully", "look harder" — blocking those from reaching
    # EXPLORATION_RX. Now only the literal `look around` is trivial;
    # all qualified looks fall through to exploration.
    r'^(i\s+)?(walk|head|go|move|sit|stand|wait|rest|drink|eat|'
    r'order|buy|pay|nod|smile|wave|wait|enter|leave|exit|continue|'
    r'follow|approach|look\s+around)\b',
    re.IGNORECASE
)


# Ship A live-verify patch (S36 #2): pre-COMBAT carve-out so
# "smash/break/bash/crush X open|down|through|apart" routes to
# exploration athletics instead of being caught by COMBAT_RX's
# `smash|bash|crush` verbs. EXPLORATION_RX already has these patterns;
# this regex just settles the classifier order question.
_PHYSICAL_BREAK_OPEN_RX = re.compile(
    # Ship A S36 #2 + #8: pre-COMBAT carve-out for physical-exertion
    # verbs that overlap with COMBAT_RX. Two clauses:
    # (a) "smash/bash/crush/break/shove X open|down|through|apart|in|aside"
    # (b) "swing on/off/across/over <object>" (mobility, not weapon swing)
    r'\b(?:'
    r'(?:smash|bash|crush|break|shove)\s+(?:\S+\s+){0,4}'
    r'(?:open|down|through|apart|in|aside)'
    r'|'
    r'swing\s+(?:on|off|across|over)\s+\w+'
    r')\b',
    re.IGNORECASE,
)


def classify_action_intent(text: str, mode: str = 'exploration') -> str:
    """Classify a player's typed action. Cheap rule-based; LLM fallback later.

    Mode-aware evaluation order. Per Session 7 spec:
      - social/downtime: SOCIAL and CONTESTED checked BEFORE RISKY, so
        idiomatic phrases like "I tell him to leave" don't get caught
        by the RISKY net before SOCIAL has a chance.
      - travel: casual movement promoted to TRIVIAL ("I keep walking",
        "I follow the road") to avoid demanding rolls during travel
        compression.
      - combat / exploration / unknown: standard order — COMBAT, then
        CONTESTED, EXPLORATION, RISKY, SOCIAL, TRIVIAL.

    META always wins (OOC questions are never gameplay actions).
    COMBAT always wins after META (Avrae handles attack rolls regardless
    of declared mode).

    Mode is the SOLE classifier signal beyond text. The previous
    `in_combat` parameter was removed in Session 13 — combat semantics
    derive from mode == 'combat'. This avoids redundant state
    (in_combat=True with mode='social' was a logical contradiction)
    and prevents future contributors from inventing extra semantics
    for a parameter the architecture doesn't need.
    """
    t = (text or '').strip()
    if not t:
        return INTENT_TRIVIAL
    # Ship A live-verify patch (S36 #6): detect the bracket-frame sentinel
    # used by Ship 1 / Ship A's auto-fire matcher
    # (`[Roll resolution: ...; outcome bound at top-of-prompt.]`). Classify
    # as META so should_call_roll returns no-roll, preventing the LLM from
    # being prompted to emit a NEW !check during the resolution-narration
    # turn. Pre-patch: classifier matched skill nouns inside the bracket
    # text ("athletics", "perception") → fired exploration intent → ROLL
    # DIRECTIVE block told LLM to end with another roll request → LLM
    # cascaded a fresh directive that triggered another Avrae roll
    # (operator-flagged bug at S36 #6).
    if t.startswith('[Roll resolution:'):
        return INTENT_META
    if META_RX.search(t):
        return INTENT_META
    # Ship A live-verify patch (S36 #2): pre-COMBAT carve-out for
    # "smash/break/bash/crush X open|down|through|apart" — these are
    # physical exertion (athletics) on inanimate objects, not combat
    # actions on creatures. COMBAT_RX has `smash` / `bash` / `crush`
    # which would otherwise claim these. The exploration regex already
    # has the patterns; here we just promote exploration over combat
    # when both might match the physical-breaking shape.
    if _PHYSICAL_BREAK_OPEN_RX.search(t):
        return INTENT_EXPLORATION
    # COMBAT is universal — Avrae owns attack/spell mechanics regardless
    # of declared mode. The classifier just routes the intent.
    if COMBAT_RX.search(t):
        return INTENT_COMBAT

    if mode == 'travel':
        # Travel mode promotes casual movement to TRIVIAL so /travel
        # compression isn't broken by exploration rolls on every "I
        # keep walking." But explicit investigation verbs still hit
        # exploration — TRIVIAL_RX is anchored to ^(i )?(walk|head|...).
        if TRIVIAL_RX.search(t):
            return INTENT_TRIVIAL
        if CONTESTED_RX.search(t):
            return INTENT_CONTESTED
        if EXPLORATION_RX.search(t):
            return INTENT_EXPLORATION
        if RISKY_RX.search(t):
            return INTENT_RISKY
        if SOCIAL_RX.search(t):
            return INTENT_SOCIAL
        return INTENT_TRIVIAL  # travel default: keep moving, no roll

    if mode in ('social', 'downtime'):
        # SOCIAL and CONTESTED checked BEFORE RISKY so social-mode
        # phrases that incidentally match RISKY verbs don't misfire.
        # CONTESTED still beats SOCIAL because contested actions need
        # rolls (intimidation, persuasion vs unwilling actor) where
        # plain social doesn't.
        if CONTESTED_RX.search(t):
            return INTENT_CONTESTED
        if SOCIAL_RX.search(t):
            return INTENT_SOCIAL
        if EXPLORATION_RX.search(t):
            return INTENT_EXPLORATION
        if RISKY_RX.search(t):
            return INTENT_RISKY
        if TRIVIAL_RX.search(t):
            return INTENT_TRIVIAL
        return INTENT_SOCIAL  # social default

    # Default mode (exploration / combat / unknown) — original order.
    if CONTESTED_RX.search(t):
        return INTENT_CONTESTED
    if EXPLORATION_RX.search(t):
        return INTENT_EXPLORATION
    if RISKY_RX.search(t):
        return INTENT_RISKY
    if SOCIAL_RX.search(t):
        return INTENT_SOCIAL
    if TRIVIAL_RX.search(t):
        return INTENT_TRIVIAL
    return INTENT_SOCIAL  # exploration default: general roleplay, no roll


@dataclass
class RollDecision:
    """The output of the discipline engine. Narration consumes this verbatim;
    it must not invent its own roll-or-not call."""
    needs_roll: bool
    skill: str = ''           # e.g. "stealth", "persuasion", "perception"
    save: str = ''            # e.g. "dex", "wis"
    category: str = ''        # one of: skill_check | save | attack | initiative | none
    severity: str = 'minor'   # minor | meaningful | dire
    reason: str = ''          # human-readable why-or-why-not, for the prompt

    def to_prompt_directive(self, init_directive_body: str = '') -> str:
        """Compact directive for the DM system prompt.

        init_directive_body: when non-empty (init directive fired), prepend
        it to the attack template body inside the === ROLL DIRECTIVE === block.
        This composes the init precondition with the existing B2.1 attack
        mandate as a single ordered block. Empty → current behavior unchanged.
        Only applied in the attack branch (§11.8 locked: inside ROLL DIRECTIVE,
        init is a precondition on the attack, not a sibling narrative block).
        """
        if not self.needs_roll:
            return f"ROLL DECISION: NO ROLL. {self.reason}"
        if self.category == 'attack':
            # Combat attack rolls require BOTH an attack name AND a target.
            # Bare `!attack` makes Avrae roll against <No Target>, which silently
            # discards the attack's effect on the world. The directive is a
            # FILL-IN template — the LLM picks weapon/spell from the character
            # context and target from the player's action text or scene NPCs.
            #
            # Avrae uses positional parsing with no quoting needed for
            # multi-word names — `!attack unarmed strike -t Garrick` is
            # correct, NOT `!attack "unarmed strike" -t Garrick`. The same
            # convention as `!check sleight of hand` in the skill path.
            template = (
                '!attack <weapon-name> -t <target>   '
                '(or for a spell: !cast <spell-name> -t <target>)'
            )
            attack_text = (
                f"ROLL DECISION: attack roll required ({self.severity}). "
                f"Your message MUST narrate the player's attempt BEFORE the "
                f"command — describe the swing, lunge, aim, or cast, and the "
                f"target's brief brace or dodge attempt — THEN end with the "
                f"templated command. A response that is ONLY the command, with "
                f"no narration, is INSUFFICIENT and breaks the table. "
                f"End your message asking the player to roll: `{template}`. "
                f"This is a TEMPLATE — fill `<weapon-name>` from the character's "
                f"available attacks (e.g. `unarmed strike`, `shortsword`, "
                f"`crossbow`, `longbow`), `<spell-name>` from the character's "
                f"known spells (e.g. `fireball`, `eldritch blast`), and `<target>` "
                f"from the NPC the player named (use the canonical NPC name from "
                f"the scene context — e.g. `Garrick`, not `the bartender`). "
                f"DO NOT wrap multi-word names in quotes — Avrae uses positional "
                f"parsing. `!attack unarmed strike -t Garrick` is correct; "
                f"`!attack \"unarmed strike\" -t Garrick` is WRONG. "
                f"The `-t <target>` argument is REQUIRED. Omitting it makes Avrae "
                f"roll against `<No Target>` and the attack vanishes with no "
                f"effect on the world. "
                f"Reason: {self.reason}"
            )
            if init_directive_body:
                return f"{init_directive_body}\n\n{attack_text}"
            return attack_text
        if self.skill:
            # Avrae expects quoted multi-word skill names
            skill_display = self.skill.replace('_', ' ')
            cmd = f"!check {skill_display}"
            label = f"{skill_display.title()} check"
        elif self.save:
            cmd = f"!save {self.save}"
            label = f"{self.save.upper()} save"
        else:
            cmd = "!roll"
            label = "roll"
        # Ship A §12.2 + S36 #5 live-verify patch: operator-locked format
        # for the directive emission. Single bold line on its own at the
        # end of the message, character name after colon.
        if self.skill or self.save:
            return (
                f"ROLL DECISION: {label} required ({self.severity}). "
                f"Reason: {self.reason}\n\n"
                f"END YOUR MESSAGE WITH A ROLL REQUEST. Format your "
                f"message as TWO parts:\n\n"
                f"1) ONE OR TWO sentences of NARRATIVE describing the "
                f"acting character's attempt — what they do, what tension "
                f"is in the moment. Then a blank line.\n"
                f"2) On its own final line, ENTIRELY BOLD (wrapped in "
                f"`**...**`), in this exact shape:\n\n"
                f"  `**{cmd} <DC> : <First Name>**`\n\n"
                f"  Where:\n"
                f"  - `<DC>` is an integer DC from the 5e RAW bands below\n"
                f"  - `<First Name>` is the acting character's first name "
                f"(e.g. 'Donovan' from 'Donovan Ruby' in the ACTING "
                f"CHARACTER block above)\n\n"
                f"EXAMPLE (substitute the real character name + DC):\n"
                f"  Donovan leans closer, scanning the runes for any "
                f"shift in the carved lines.\n\n"
                f"  **!check perception 15 : Donovan**\n\n"
                f"DC GUIDANCE: pick a DC from the 5e RAW bands:\n"
                f"  5  = trivial (the actor would succeed on instinct)\n"
                f"  10 = easy (routine for a competent character)\n"
                f"  15 = medium (real friction, default for most "
                f"uncertain attempts)\n"
                f"  20 = hard (visible effort or skill required)\n"
                f"  25 = very hard (extraordinary attempt; only experts "
                f"succeed)\n"
                f"  30 = nearly impossible (heroic stakes; success is rare)\n"
                f"The DC is what the engine binds the outcome to. The "
                f"narration after the roll is auto-generated bound to the "
                f"rolled value vs the DC you picked.\n"
                f"The bold roll-request line MUST appear as the final line "
                f"of your message, alone, with NO trailing text after it. "
                f"The line MUST be entirely wrapped in `**...**` so it "
                f"renders bold to the player."
            )
        return (
            f"ROLL DECISION: {label} required ({self.severity}). "
            f"End your message asking the player to roll: `{cmd}`. "
            f"Reason: {self.reason}"
        )


# Default skill mapping for exploration/contested intents
EXPLORATION_DEFAULT_SKILLS = {
    # Ship A live-verify patch (S36 #2): expanded skill anchors so the
    # new EXPLORATION_RX verbs route to specific skills instead of
    # falling through to perception default. _pick_skill iterates in
    # insertion order — multi-word keys (e.g. "look closely") must
    # appear BEFORE their single-word prefix (e.g. "look") to win.

    # Original anchors:
    'search': 'investigation',
    'investigate': 'investigation',
    'examine': 'investigation',
    'inspect': 'investigation',
    'study': 'investigation',
    # Look-qualified — multi-word first per _pick_skill ordering rule:
    'look closer': 'perception',
    'look closely': 'perception',
    'look carefully': 'perception',
    'look harder': 'perception',
    'look hard': 'perception',
    'look over': 'perception',
    'look inside': 'perception',
    'look behind': 'perception',
    'look under': 'perception',
    'listen': 'perception',
    # Investigative natural verbs (perception for "see/sense", investigation for "deduce/analyze"):
    'peer': 'perception',
    'peek': 'perception',
    'notice': 'perception',
    'spot': 'perception',
    'scan': 'perception',
    'scrutinize': 'investigation',
    'comb': 'investigation',
    'figure out': 'investigation',
    'discern': 'insight',
    'find': 'investigation',
    'read closely': 'investigation',
    'read carefully': 'investigation',
    'read over': 'investigation',
    # check-for variants (multi-word; "check for traps" stays first for back-compat):
    'check for traps': 'investigation',
    'check for': 'investigation',
    'check the': 'investigation',
    'check over': 'investigation',
    'check inside': 'investigation',
    'check behind': 'investigation',
    'check under': 'investigation',
    # Athletics anchors:
    'climb': 'athletics',
    'jump': 'athletics',
    'leap': 'athletics',
    'swim': 'athletics',
    'lift': 'athletics',
    'hoist': 'athletics',
    'force open': 'athletics',
    'force the': 'athletics',
    'pry': 'athletics',
    'wrench': 'athletics',
    'break open': 'athletics',
    'break down': 'athletics',
    'break through': 'athletics',
    'smash': 'athletics',
    'kick open': 'athletics',
    'kick down': 'athletics',
    'push over': 'athletics',
    'push down': 'athletics',
    'push through': 'athletics',
    'push aside': 'athletics',
    'haul': 'athletics',
    'drag': 'athletics',
    # Bare-word fallbacks for physical verbs — substring match catches
    # "push the bookshelf aside" / "bash the lock apart" where the
    # multi-word keys above can't span the object gap.
    'bash': 'athletics',
    'smash': 'athletics',
    'push': 'athletics',
    'break': 'athletics',
    'force': 'athletics',
    'kick': 'athletics',
    'shove': 'athletics',
    'shoulder': 'athletics',
    'tug': 'athletics',
    'yank': 'athletics',
    'scramble': 'athletics',
    'swing on': 'athletics',
    'swing off': 'athletics',
    'swing across': 'athletics',
    # Acrobatics-shaped (mobility/balance):
    'dodge': 'acrobatics',
    'tumble': 'acrobatics',
    'vault': 'acrobatics',
    'balance': 'acrobatics',
    'roll under': 'acrobatics',
    'roll past': 'acrobatics',
    'roll through': 'acrobatics',
    'roll aside': 'acrobatics',
    'duck under': 'acrobatics',
    'duck behind': 'stealth',
    'duck into': 'stealth',
    'duck past': 'acrobatics',
    # Stealth-shaped exploration verbs (non-RISKY):
    'creep': 'stealth',
    'slink': 'stealth',
    'tiptoe': 'stealth',
    'sneak up': 'stealth',
    # Tracking / wilderness:
    'track': 'survival',
    # Thieves' tools (special handling):
    'disarm': 'thieves',
    'pick': 'thieves',
    'unlock': 'thieves',
    # Mobility:
    'squeeze': 'acrobatics',
    'crawl': 'stealth',
}

CONTESTED_DEFAULT_SKILLS = {
    'persuade': 'persuasion',
    'convince': 'persuasion',
    'deceive': 'deception',
    'lie': 'deception',
    'bluff': 'deception',
    'intimidate': 'intimidation',
    'threaten': 'intimidation',
    'menace': 'intimidation',
    'seduce': 'persuasion',
    'charm': 'persuasion',
    'trick': 'deception',
    'fast-talk': 'deception',
    'fasttalk': 'deception',
    'sneak past': 'stealth',
    'hide from': 'stealth',
    'bargain': 'persuasion',
    'haggle': 'persuasion',
    'interrogate': 'intimidation',
}


def _pick_skill(text: str, table: dict[str, str]) -> str:
    t = text.lower()
    for keyword, skill in table.items():
        if keyword in t:
            return skill
    return ''


def should_call_roll(intent: str, mode: str, text: str,
                     character: Optional[CharacterContext] = None) -> RollDecision:
    """Decide if a roll is required. Mode-aware. Tag-aware.

    NEVER asks for a roll when:
      - intent is meta or trivial
      - mode is downtime
      - mode is travel and intent is social
      - the result would be auto-success given character context
        (e.g. darkvision character "looks around" in a cave)
    """
    if intent == INTENT_META:
        return RollDecision(False, reason="Out-of-character question.")
    if intent == INTENT_TRIVIAL:
        return RollDecision(False, reason="Trivial action; no failure stake.")
    if mode == 'downtime':
        return RollDecision(False, reason="Downtime mode; rolls reserved for special activities.")
    if intent == INTENT_COMBAT:
        return RollDecision(
            True,
            category='attack',
            severity='meaningful',
            reason="Combat action — Avrae handles attack rolls via !attack / !cast.",
        )
    if intent == INTENT_SOCIAL:
        # Casual social usually doesn't need a roll
        return RollDecision(False, reason="Casual social interaction; narrate the response.")

    # Auto-success short-circuits using character tags
    if character:
        tags = character.narrative_tags
        text_l = text.lower()
        if 'darkvision' in tags and ('see in the dark' in text_l or
                                     'see in dark' in text_l or
                                     'look around the dark' in text_l):
            return RollDecision(False, reason="Character has darkvision; this is automatic.")

    if intent == INTENT_EXPLORATION:
        skill = _pick_skill(text, EXPLORATION_DEFAULT_SKILLS) or 'perception'
        # 'thieves' is a marker meaning "thieves' tools check" — Avrae uses
        # different syntax for this; for now we map it to dexterity check.
        if skill == 'thieves':
            if character and 'lockpicker' in character.narrative_tags:
                return RollDecision(
                    True, skill='', save='', category='skill_check',
                    severity='meaningful',
                    reason="Lockpicker with thieves' tools; ask for `!check sleight of hand`.",
                )
            return RollDecision(
                True, skill='sleight_of_hand', category='skill_check',
                severity='meaningful',
                reason="Manipulating a lock or trap.",
            )
        return RollDecision(
            True, skill=skill, category='skill_check',
            severity='meaningful',
            reason=f"Exploration action with uncertain outcome.",
        )

    if intent == INTENT_CONTESTED:
        skill = _pick_skill(text, CONTESTED_DEFAULT_SKILLS) or 'persuasion'
        # If we're in combat-adjacent mode, contested social attempts are
        # higher-stakes (failure has immediate consequences)
        severity = 'meaningful' if mode != 'combat' else 'dire'
        return RollDecision(
            True, skill=skill, category='skill_check',
            severity=severity,
            reason="Contested action against an unwilling actor.",
        )

    if intent == INTENT_RISKY:
        # Risky actions default to a stealth or sleight-of-hand depending on text
        text_l = text.lower()
        if any(w in text_l for w in ('sneak', 'shadow', 'tail', 'slip')):
            skill = 'stealth'
        elif any(w in text_l for w in ('steal', 'pickpocket', 'lift')):
            skill = 'sleight_of_hand'
        else:
            skill = 'stealth'
        return RollDecision(
            True, skill=skill, category='skill_check',
            severity='meaningful',
            reason="Risky action with real consequences on failure.",
        )

    return RollDecision(False, reason="Default: narrate without a roll.")

# ─────────────────────────────────────────────────────────
# CAPABILITY GROUNDING (S9 v1 — weapon claims, 3-state verdict)
# ─────────────────────────────────────────────────────────
#
# Detects explicit weapon-capability claims in player narration and
# classifies them as one of three verdicts. The advisory pattern:
# orchestration produces a directive; the DM prompt consumes it;
# narration stays subordinate to canonical state.
#
# Architectural framing (Session 13 — locked after design review):
# S9 is NOT a truth engine. S9 is a constraint-aware narration safety
# layer over PARTIAL projections. Truth sources:
#
#   1. Avrae attacks      = combat configuration subset (NOT ownership)
#   2. Skeleton.md        = author-declared capability HINTS (additive)
#   3. DDB                = external visual truth, DM-visible, NOT ingested
#
# Because all three sources are partial projections, the bot must NEVER
# treat absence of data as evidence of absence. Unmatched claims default
# to VALID_BUT_UNCONFIGURED, not INVALID. INVALID is reserved for
# explicit contradiction from an authoritative source — unreachable in
# v1 (no producer exists yet) but the enum slot is preserved so future
# DDB ingestion or skeleton-deny-list extensions can populate it without
# restructuring.
#
# Scope (intentional v1 boundary):
#   - Weapons only. Spells, items, inventory deferred (S9.x / S20).
#   - Primary actor only. Cross-actor "I borrow Borin's sword" claims
#     deferred until multiplayer surfaces friction.
#   - Mode-independent. Capability claims occur in any mode; the
#     check doesn't read mode and shouldn't.
#
# This layer ensures narration does not contradict established canonical
# state. It does NOT decide damage, rolls, or combat mechanics — those
# stay with Avrae. "Not in attacks" does not mean "impossible to
# possess" — attacks represent combat-ready capabilities only.


# Weapon taxonomy moved to weapon_schema.py (Session 15 refactor) so that
# future capability sources (DDB ingestion, skeleton-deny-list) depend on a
# neutral schema rather than reaching back into orchestration. Re-exported
# here for backward compatibility with `from dnd_orchestration import
# WEAPON_CAPABILITIES` callers and `orch.WeaponCapability` references.
from weapon_schema import WeaponCapability, WEAPON_CAPABILITIES  # noqa: F401, E402


# Capability invocation phrases. Two-part match: invocation verb +
# weapon-family noun in proximity (1-3 words apart, optional
# article/possessive between).
#
# The noun list inside the regex is built dynamically from
# WEAPON_CAPABILITIES below so adding a family in one place is enough.
#
# Rejected by design:
#   - "draw the curtains" — "curtains" not a weapon noun
#   - "draw near"        — no weapon noun at all
#   - "raise voice"      — "voice" not a weapon noun
#   - "bow before X"     — "bow" is verb here, not noun (no invocation
#                          verb precedes it)
#   - "sword fight"      — no invocation verb precedes "sword"

_INVOCATION_VERBS = (
    'draw', 'unsheathe', 'unsheath', 'ready', 'raise',
    'nock', 'aim', 'brandish', 'grab', 'pull', 'wield',
    'lift', 'hoist', 'equip', 'use',
)

# Special-case standalone idioms that we want to suppress even when
# the verb-noun shape would otherwise match. "nock an arrow" we WANT
# to detect (it's an archery capability claim) so we treat 'arrow' as
# a bow-family alias for the noun-side of detection only — see
# _NOUN_TO_CATEGORY below.

# Nouns that, if they appear after an invocation verb, mark the claim.
# Built by flattening all aliases plus a few "implies-a-bow" specifics
# like 'arrow' (for "nock an arrow"). Mapped to category for the
# decision output.
_NOUN_TO_CATEGORY: dict[str, str] = {}
for _wc in WEAPON_CAPABILITIES:
    for _alias in _wc.aliases:
        _NOUN_TO_CATEGORY[_alias] = _wc.category
# Specific phrase-level additions: "nock an arrow" / "draw an arrow"
# imply a bow capability claim even though "arrow" isn't a weapon
# itself. Conservative: only 'arrow' for now; expand if friction.
_NOUN_TO_CATEGORY['arrow'] = 'bow'

# Build the regex. Word-boundaries on both sides; verb directly
# followed by an optional article/possessive ('a', 'an', 'the', 'my',
# 'his', 'her', 'their') and then the noun. No room for arbitrary
# words between verb and noun — keeps the false-positive surface tight.
_NOUN_ALT = '|'.join(re.escape(n) for n in sorted(_NOUN_TO_CATEGORY.keys(), key=len, reverse=True))
_VERB_ALT = '|'.join(_INVOCATION_VERBS)
WEAPON_CLAIM_RX = re.compile(
    rf'\b(?P<verb>{_VERB_ALT})\s+'
    rf'(?:(?:a|an|the|my|his|her|their|both|two|some)\s+)?'
    rf'(?:(?:of\s+)?(?:my|his|her|their)\s+)?'
    rf'(?P<noun>{_NOUN_ALT})s?\b',
    re.IGNORECASE,
)


class CapabilityVerdict(Enum):
    """Three-state classification of a capability claim, per S9 design.

    Defined at module scope (not function-local) so callers can pattern-
    match on identity, type-check imports cleanly, and future producers
    in other modules can emit verdicts without import gymnastics.

    NO behavior assumptions are baked into the enum. No precedence
    ordering, no helper methods, no implicit conversions. Each value
    has a defined semantic meaning and nothing else.
    """

    CONFIRMED = 'confirmed'
    """The claim is supported by an authoritative source.
    v1 producers: Avrae attacks match, OR skeleton.md explicitly
    declares the capability for this character (skeleton hint layer
    arrives in S9 step 2)."""

    VALID_BUT_UNCONFIGURED = 'valid_but_unconfigured'
    """The claim is not confirmed by any authoritative source AND is
    not explicitly contradicted by any authoritative source.
    Default verdict for unmatched claims under partial projections —
    absence of data is NOT evidence of absence. Allows narration to
    proceed; carries an informative annotation noting that Avrae
    didn't show the capability and DDB visibility is not ingested."""

    INVALID = 'invalid'
    """Explicit contradiction from an authoritative source.
    Reserved for: future DDB ingestion that returns no inventory match,
    future skeleton-deny-list extensions, or DM-override mechanisms
    that explicitly disallow a capability. UNREACHABLE in v1 — no
    producer emits this verdict. The enum slot exists so future
    extensions can populate it without restructuring the consumer
    side (directive renderer, dm_respond wiring, calibration suite)."""


@dataclass
class CapabilityDecision:
    """The output of the capability grounding check (3-state).

    needs_check=False is the dominant case: most player turns don't
    contain a weapon claim at all, and the directive returns empty
    so the system prompt is unchanged.

    When needs_check=True, `verdict` is one of CapabilityVerdict's
    three values. The directive renderer maps verdict → directive:
      CONFIRMED               → silent (no constraint needed)
      VALID_BUT_UNCONFIGURED  → soft annotation (informative, non-blocking)
      INVALID                 → anti-fabrication directive (currently
                                unreachable in v1)
    """
    needs_check:    bool
    verdict:        CapabilityVerdict = CapabilityVerdict.VALID_BUT_UNCONFIGURED
    capability:     str = ''       # 'sword', 'bow', etc — the family claimed
    matched_attack: str = ''       # which attack satisfied a CONFIRMED claim
    reason:         str = ''       # human-readable, for logs

    def to_prompt_directive(self) -> str:
        """Compact directive for the DM system prompt.

        Returns '' (empty string) for both no-claim turns AND
        CONFIRMED claims — the prompt stays unchanged when nothing
        needs to be communicated to the DM.

        VALID_BUT_UNCONFIGURED renders an informative-not-coercive
        annotation. The bot does NOT assert probability about missing
        data — it explicitly defers to the DM's external view.

        INVALID renders the anti-fabrication directive. v1 has no
        producer for this branch; the code exists to keep the
        consumer surface stable when future producers are added.
        """
        if not self.needs_check:
            return ''
        if self.verdict is CapabilityVerdict.CONFIRMED:
            return ''
        if self.verdict is CapabilityVerdict.VALID_BUT_UNCONFIGURED:
            return (
                f"CAPABILITY CHECK: Player claims '{self.capability}'. "
                f"Mark this item as UNVERIFIED — not present in Avrae "
                f"attacks, no skeleton confirmation, DDB visibility not "
                f"ingested. Do not block narration, but do not treat the "
                f"item as established equipment in subsequent narration. "
                f"Do not reference it as if previously confirmed."
            )
        # INVALID — explicit contradiction. Unreachable in v1 but the
        # branch is here so the consumer surface is stable when future
        # producers (DDB ingestion, skeleton deny-list) are added.
        return (
            f"CAPABILITY CHECK: Character has no matching attack entry for "
            f"this {self.capability} claim, and an authoritative source has "
            f"explicitly contradicted it. Do not narrate successful use of "
            f"the claimed weapon as established fact. Either narrate the "
            f"realization/problem, ask for clarification, or reinterpret as "
            f"an improvised/unarmed attempt with appropriate consequences."
        )


def check_action_capability(
    text: str,
    character: Optional[CharacterContext],
    skeleton_capabilities: Optional[dict[str, set[str]]] = None,
) -> CapabilityDecision:
    """Detect explicit weapon-capability claims and classify them with
    a 3-state CapabilityVerdict.

    Authoritative sources consulted (in priority order):
      1. character.attacks      — Avrae combat-config truth (CONFIRMED on match)
      2. skeleton_capabilities  — author-declared HINT layer (CONFIRMED on match)
      3. (future) DDB ingestion — not yet implemented

    v1 producers per verdict:
      CONFIRMED              — claim matches character.attacks entry,
                               OR claim matches skeleton-declared
                               capability for this character.
      VALID_BUT_UNCONFIGURED — claim detected; no source confirms;
                               no source contradicts. Default verdict
                               under partial projections.
      INVALID                — no producer in v1. Reserved for future
                               authoritative-contradiction sources.

    skeleton_capabilities is `dict[str, set[str]]` mapping character
    display name → set of weapon-family categories. Lookup is
    case-and-whitespace-normalized — author-side typos in capitalization
    don't silently miss. Pass None or {} to skip skeleton consultation
    (e.g. when no skeleton has been authored for this campaign).

    Returns CapabilityDecision(needs_check=False) when no claim is
    detected (the dominant case — most turns).

    Robust to:
      - empty/None text
      - None character (no-check)
      - empty attacks list AND missing skeleton (verdict stays
        VALID_BUT_UNCONFIGURED — absence of data is NOT evidence
        of absence)
      - prefixed/suffixed Avrae attack names ("+1 Longsword", etc.)
    """
    t = (text or '').strip()
    if not t or character is None:
        return CapabilityDecision(needs_check=False)

    m = WEAPON_CLAIM_RX.search(t)
    if not m:
        return CapabilityDecision(needs_check=False)

    noun = m.group('noun').lower()
    category = _NOUN_TO_CATEGORY.get(noun)
    if category is None:
        # Defensive: regex only contains nouns from _NOUN_TO_CATEGORY,
        # so this branch is unreachable in practice. Kept for safety.
        return CapabilityDecision(needs_check=False)

    # Strict full-string equality matching. Lowercase both sides; no
    # substring, no token, no regex inference, no partial matching.
    # Per Session 13 locked spec — if anything doesn't match cleanly
    # under this system, the fix is data (aliases in WEAPON_CAPABILITIES),
    # not logic.
    noun_lower = noun  # already lowered by m.group('noun').lower() above

    # Determine the set of allowed canonical item names that would
    # satisfy this claim. Two cases per the locked resolution order:
    #
    #   - Player noun is a generic noun (i.e., a key in
    #     WEAPON_CAPABILITIES family map) → allowed = full alias list
    #     for that family (lowercased).
    #
    #   - Player noun is a specific item (appears only as an alias,
    #     not as a family key) → allowed = {noun_lower} only. Strict
    #     specific-item grounding.
    family_keys = {wc.category for wc in WEAPON_CAPABILITIES}
    if noun_lower in family_keys:
        cap = next(wc for wc in WEAPON_CAPABILITIES if wc.category == noun_lower)
        allowed_items = {a.lower() for a in cap.aliases}
    else:
        allowed_items = {noun_lower}

    # Step 1+2 (Avrae): walk character.attacks looking for any entry
    # whose lowercased form is exactly in allowed_items.
    for original in (character.attacks or []):
        if original.lower() in allowed_items:
            return CapabilityDecision(
                needs_check=True,
                verdict=CapabilityVerdict.CONFIRMED,
                capability=category,
                matched_attack=original,
                reason=f"Claim '{noun}' confirmed via Avrae attack entry '{original}'.",
            )

    # Step 3+4 (Skeleton): same exact-match rule. Character-name lookup
    # is whitespace+case-normalized so author-side typos in capitalization
    # don't silently miss.
    if skeleton_capabilities and character.name:
        char_norm = ' '.join(character.name.split()).lower()
        for declared_name, declared_items in skeleton_capabilities.items():
            if ' '.join(declared_name.split()).lower() != char_norm:
                continue
            # Skeleton items are also lowercased at parse time
            # (skeleton_loader does this). Strict equality intersection.
            declared_lower = {d.lower() for d in declared_items}
            hit = declared_lower & allowed_items
            if hit:
                matched = sorted(hit)[0]  # deterministic pick when multiple match
                return CapabilityDecision(
                    needs_check=True,
                    verdict=CapabilityVerdict.CONFIRMED,
                    capability=category,
                    matched_attack=f"skeleton-declared: {matched}",
                    reason=f"Claim '{noun}' confirmed via skeleton declaration "
                           f"for character {declared_name!r}.",
                )
            # Character has a skeleton entry but no overlap with allowed_items.
            # Stay VALID_BUT_UNCONFIGURED — skeleton hints are POSITIVE
            # only (CONFIRM presence, never CONTRADICT absence).
            break

    # Step 5: no Avrae match, no skeleton confirmation. Default to
    # VALID_BUT_UNCONFIGURED — absence of data is NOT evidence of
    # absence. The DM has external DDB visibility and judges from there.
    return CapabilityDecision(
        needs_check=True,
        verdict=CapabilityVerdict.VALID_BUT_UNCONFIGURED,
        capability=category,
        matched_attack='',
        reason=f"Claim '{noun}' has no Avrae attack match and no "
               f"skeleton confirmation; no contradiction (DDB not ingested).",
    )


# ─────────────────────────────────────────────────────────────────────
# Pacing directive (Track 3 entry point — Session 14)
# ─────────────────────────────────────────────────────────────────────
# Converts existing scene state (tension_int, progress_clocks) into an
# imperative DM directive. Same advisory pattern as roll_directive and
# capability_directive: read state, surface as constraint on the next
# narrative move, let the LLM weight it.
#
# Architectural intent: Phase 1/12 solved "what is true?" / "what
# exists?" / "what can the player do?". This solves "what narrative
# move should happen next?". The system already declared tension and
# clocks in the prompt; the directive layer makes them *operational*
# instead of decorative.
#
# Imperative-only phrasing rule:
#   GOOD — "Force a decision."
#   GOOD — "An NPC must commit to a course of action this turn."
#   BAD  — "The air feels tense."   (flavor; not a behavioral instruction)
#   BAD  — "Describe urgency."      (asks for description, not action)
#
# Tiers are read at scene_state.tension_int boundaries 25/60/85,
# matching tension_label() in dnd_engine. Urgent-clock callout fires
# independently when any clock is ≥80% filled.
#
# v1 thresholds are calibrated against intuition, not log data — same
# spirit as S9 v1 and roll discipline v1. Tune from `pacing_directive:`
# log emissions after observed-friction sessions.

PACING_TIER_SILENT     = 'silent'      # tension ≤25 and no urgent clock
PACING_TIER_MOUNTING   = 'mounting'    # 26–60
PACING_TIER_DANGEROUS  = 'dangerous'   # 61–85
PACING_TIER_CLIMAX     = 'climax'      # 86+

_PACING_TIER_DIRECTIVES = {
    PACING_TIER_MOUNTING: (
        "MOUNTING. Don't let the scene settle without cost. Introduce a "
        "small friction this turn — an NPC notices something, an "
        "unfavorable detail surfaces, time pressure tightens. Resolutions "
        "should carry a price, not arrive clean."
    ),
    PACING_TIER_DANGEROUS: (
        "DANGEROUS. Escalate consequences this turn. The world should not "
        "feel safe. Force decisions; do not allow indefinite safe "
        "wandering or easy retreat. Threats commit to action — they do "
        "not posture."
    ),
    PACING_TIER_CLIMAX: (
        "CLIMAX. Something concrete must shift this turn — an NPC commits, "
        "a clock fires, a confrontation lands, a stake resolves. Move the "
        "story. Do NOT pad with description or atmospheric hedging. The "
        "scene is at apocalyptic register; deliver weight."
    ),
}

PACING_URGENT_CLOCK_THRESHOLD = 0.80  # ≥80% filled triggers urgent callout


def _pacing_tier(tension_int: int) -> str:
    """Map tension_int (0-100) to a pacing tier name."""
    if tension_int <= 25:
        return PACING_TIER_SILENT
    elif tension_int <= 60:
        return PACING_TIER_MOUNTING
    elif tension_int <= 85:
        return PACING_TIER_DANGEROUS
    else:
        return PACING_TIER_CLIMAX


def _urgent_clocks(clocks: list) -> list:
    """Return clocks at or above PACING_URGENT_CLOCK_THRESHOLD filled."""
    out = []
    for c in clocks or []:
        ticks = c.get('ticks', 0)
        cap = c.get('capacity', 0)
        if cap and (ticks / cap) >= PACING_URGENT_CLOCK_THRESHOLD:
            out.append(c)
    return out


def compute_pacing_directive(scene_state) -> str:
    """Return imperative pacing directive text, or '' when silent.

    Reads scene_state.tension_int and scene_state.progress_clocks.
    Silent ONLY when tension ≤25 AND no clock is ≥80% filled. Otherwise
    emits the tier directive followed by an urgent-clock callout if any
    clock is near firing.

    The directive is appended to the system prompt as its own block
    (=== PACING DIRECTIVE ===) by build_dm_context. Empty return string
    suppresses the block entirely.
    """
    if not scene_state:
        return ''
    tension = int(scene_state.get('tension_int') or 0)
    clocks = scene_state.get('progress_clocks') or []
    urgent = _urgent_clocks(clocks)
    tier = _pacing_tier(tension)

    if tier == PACING_TIER_SILENT and not urgent:
        return ''

    parts = []
    if tier != PACING_TIER_SILENT:
        parts.append(_PACING_TIER_DIRECTIVES[tier])

    if urgent:
        clock_lines = []
        for c in urgent:
            ticks = c.get('ticks', 0)
            cap = c.get('capacity', 0)
            pct = int(100 * ticks / cap) if cap else 0
            clock_lines.append(f"'{c.get('name','?')}' at {ticks}/{cap} ({pct}%)")
        parts.append(
            "URGENT CLOCK: " + ", ".join(clock_lines) +
            " — about to fire. Make this visible in the world this "
            "turn: characters react to it, the environment shifts, NPCs "
            "notice. Do not narrate around it."
        )

    return "\n\n".join(parts)


def pacing_log_summary(scene_state) -> str:
    """Compact representation of pacing inputs for log lines.

    Format: tier=X tension=N clocks=[(name:ticks/cap:pct%), ...]
    Used by dm_respond when emitting `pacing_directive:` log lines.
    """
    if not scene_state:
        return "tier=silent tension=0 clocks=[]"
    tension = int(scene_state.get('tension_int') or 0)
    clocks = scene_state.get('progress_clocks') or []
    tier = _pacing_tier(tension)
    clock_strs = []
    for c in clocks:
        ticks = c.get('ticks', 0)
        cap = c.get('capacity', 0)
        pct = int(100 * ticks / cap) if cap else 0
        clock_strs.append(f"({c.get('name','?')}:{ticks}/{cap}:{pct}%)")
    return f"tier={tier} tension={tension} clocks=[{', '.join(clock_strs)}]"


# ─────────────────────────────────────────────────────────────────────
# Central thread directive (Track 3 — Session 14)
# ─────────────────────────────────────────────────────────────────────
# Surfaces the first authored skeleton hook as the campaign's central
# thread, phrased as imperative DIRECTIONAL pressure rather than literal
# repetition. Same architectural shape as the pacing directive: convert
# decoration into operational constraint.
#
# Phrasing guard: the directive explicitly forbids restating the hook
# verbatim. The failure mode this guards against is the LLM
# pattern-matching to "central thread = X" by keyword-stuffing X into
# every response. We want the thread to shape narrative weight (NPC
# behavior, environmental detail, time pressure, consequences) without
# becoming a refrain.
#
# Composes with the pacing directive: pacing pressures FOR a decision;
# central thread pressures TOWARD which direction. Together they push
# purposeful escalation rather than escalation in random directions.
#
# Skeleton convention: the first bullet under `## Major hooks` is the
# load-bearing thread. Subsequent hooks are subplot/optional. v1 surfaces
# only the first hook; later iterations may rotate or weight by activity.

def compute_central_thread_directive(hooks: list) -> str:
    """Return imperative directive surfacing the campaign's central thread.

    Reads the first authored hook as the central thread (skeleton.md
    convention). Phrased to pressure continuity through indirect
    presence — atmosphere, NPC behavior, environmental detail — rather
    than literal restatement.

    Returns empty when no hooks are authored. Same advisory pattern as
    compute_pacing_directive.
    """
    if not hooks:
        return ''
    central = (hooks[0] or '').strip()
    if not central:
        return ''
    return (
        f"The campaign's central thread: {central}\n\n"
        "This is the gravitational pull of the world — what the campaign "
        "is *about*. It should shape this turn through indirect signals: "
        "NPC behavior shifts, environmental detail, time pressure, the "
        "shape of consequences. Do NOT name or restate the thread in "
        "narration unless the scene already calls for it directly. The "
        "thread should feel like weight the player senses, not a refrain "
        "the DM repeats."
    )


# ─────────────────────────────────────────────────────────────────────
# Consequence surfacing directive (Track 3 — Session 16)
# ─────────────────────────────────────────────────────────────────────
# Reads active dnd_consequences rows and the in-scope NPC id set, emits
# imperative pressure that colors the scene by what the world remembers.
# Same architectural shape as pacing and central thread — convert
# accumulated structured state into an operational directive.
#
# Composition note: consequence directive is rendered with the other
# tactical directives (pacing, central thread). Philosophy frames how
# all of them are interpreted; consequences sit BELOW the frame, with
# the other move-shaping directives.
#
# Cap-at-3 with severity-then-recency ordering — see
# CONSEQUENCE_SURFACING_SPEC.md §1.6 / §6.3. Emitting more than three
# at once dilutes the LLM's attention. Three preserves narrative weight
# per row.

CONSEQUENCE_DIRECTIVE_CAP = 3


def compute_consequence_directive(active_consequences,
                                   in_scope_npc_ids) -> tuple:
    """Return (directive_text, surfaced_consequence_dicts).

    active_consequences: list of dicts (engine.get_active_consequences),
        each with at least: id, npc_id, kind, severity, summary,
        canonical_name, last_surfaced_turn.
    in_scope_npc_ids: iterable of npc_ids considered "present in this
        turn's scene" — typically recently-active NPCs ∪ NPCs at the
        current location. Consequences whose npc_id is NOT in this set
        are not surfaced.

    Returns ('', []) when nothing relevant.

    Sort is severity DESC, then last_surfaced_turn DESC (NULL last),
    then id ASC for determinism. Caps at CONSEQUENCE_DIRECTIVE_CAP rows.

    Caller is responsible for calling consequence_emit_surface(id,
    current_turn) on every returned dict's id, then passing the directive
    text to build_dm_context.
    """
    if not active_consequences:
        return '', []
    scope = set(int(i) for i in (in_scope_npc_ids or []))
    if not scope:
        return '', []

    relevant = [c for c in active_consequences
                if int(c.get('npc_id', 0)) in scope]
    if not relevant:
        return '', []

    def _sort_key(c):
        # severity DESC → negate. last_surfaced_turn DESC with NULL last
        # → never-surfaced rows get a +inf key (sort after surfaced rows
        # at the same severity in ascending tuple compare).
        sev = -int(c.get('severity') or 0)
        lst = c.get('last_surfaced_turn')
        if lst is None:
            lst_sort = float('inf')
        else:
            lst_sort = -int(lst)
        return (sev, lst_sort, int(c.get('id', 0)))

    relevant.sort(key=_sort_key)
    top = relevant[:CONSEQUENCE_DIRECTIVE_CAP]

    lines = []
    for c in top:
        name = c.get('canonical_name') or f"NPC#{c.get('npc_id')}"
        kind = c.get('kind', '?')
        sev = c.get('severity', 0)
        summary = c.get('summary', '')
        lines.append(f"  - {name} [{kind}, sev {sev}]: {summary}")

    body = (
        "The following weight what the named NPCs feel and how they "
        "posture:\n"
        + "\n".join(lines)
        + "\n\n"
        "Let these color the scene through NPC posture, dialog, and "
        "choices. Do not have the DM narrator restate them as "
        "\"remembered consequences\" — manifest them. An NPC who was "
        "threatened is wary, watches the door, speaks carefully. An "
        "NPC shown mercy may show quiet recognition, may extend trust, "
        "may be unable to meet the player's eye. An NPC betrayed "
        "remembers the betrayal in tone, in the held grudge, in what "
        "they no longer offer."
    )
    return body, top


def consequence_log_summary(surfaced_consequences) -> str:
    """Compact log representation of what the directive emitted this turn.
    surfaced_consequences: list of dicts as returned in the top-N slice.
    Used by dm_respond when emitting `consequence_directive:` log lines.
    """
    if not surfaced_consequences:
        return "emitted=0"
    bits = []
    for c in surfaced_consequences:
        bits.append(
            f"({c.get('canonical_name','?')}|{c.get('kind','?')}|"
            f"sev={c.get('severity',0)}|id={c.get('id',0)})"
        )
    return f"emitted={len(surfaced_consequences)} rows=[{', '.join(bits)}]"


# ─────────────────────────────────────────────────────────────────────
# Committed-action resolution directive (Track 3 — Session 19)
# ─────────────────────────────────────────────────────────────────────
# Detects the godmode-escape failure mode: player commits to COMBAT
# (turn N), next turn shifts the scene without resolving the prior
# commitment (turn N+1), the DM accepts the new action and the prior
# violence silently evaporates. Emits an imperative directive forcing
# the LLM to either narrate the prior commitment's consequence,
# refuse the disengagement, or charge a roll for it.
#
# Same architectural shape as pacing/central-thread/consequence: pure
# function reading scene state, returns a directive string or empty.
# Composes AFTER consequence in build_dm_context — last in the tactical
# band, matches the directive_emit telemetry slot reserved Session 18.
#
# Scope is escape-only: detection of an unresolved commitment paired with
# a scene-shift in the current turn. Layer-3 (Avrae init binding) and
# layer-4 (deterministic mode flip) of the four-layer attack chain are
# explicitly out of scope (see COMMITTED_ACTION_RESOLUTION_REVIEW §11.A
# / §11.4). This directive does NOT compute target names, write to
# Avrae, or flip mode.
#
# Locked decisions (per review):
#   §11.1 COMBAT-only scope
#   §11.2 regex resolution check (no second LLM call)
#   §11.3 recompute prior intent from last_player_action (no schema)
#   §11.5 imperative phrasing + B2.1 narration mandate
#   §11.6 single-turn lookback
#   §11.7 last_dm_response persisted in dnd_scene_state
#   §11.8 composition order: AFTER consequence, BEFORE philosophy in
#         build_dm_context's tactical band ordering (review locked
#         "after consequence" — engine renders philosophy higher,
#         tactical band closes with commitment as the final block)
#   §11.B target hints from recently_active_npcs ∪ at_location
#   §11.D retraction grammar in v1 with diagnostic

# Verbs that indicate the player is moving away from the scene/context.
# Conservative — concrete spatial/temporal-shift verbs only. Idiomatic
# uses ("leave the door open", "head off the spear") are excluded by
# negative lookaheads where they're known false positives.
SCENE_SHIFT_RX = re.compile(
    r'\b('
    r'leave(?!\s+(?:the|that|it|him|her|them|this)\s+(?:door|window|gate|trap)\s+open)'
    r'|exit'
    r'|depart'
    r'|head\s+(?:out|outside|inside|off|over|down|up|back|away|to|toward|towards|into|for)'
    r'|walk\s+(?:away|out|outside|off|back|over|into|to|toward|towards)'
    r'|run\s+(?:away|off|out|outside|back|over|into|to|toward|towards)'
    r'|go\s+(?:outside|inside|to|back|over|out|into|toward|towards)'
    r'|move\s+on'
    r'|continue\s+(?:on|forward|down|up|toward|towards)'
    r'|travel'
    r'|return\s+to'
    r'|step\s+(?:out|outside|away|back)'
    r'|disengage'
    r'|retreat'
    r'|flee'
    r')\b',
    re.IGNORECASE,
)

# Reaction-verb stems indicating the prior DM response narrated the
# target's response to the player's commitment. Stems cover the common
# tense forms; the regex anchors on the verb stem and tolerates -s/-es/-ed.
_REACTION_VERBS = re.compile(
    r'\b('
    r'dodges?|dodged|blocks?|blocked|parries|parried|deflects?|deflected'
    r'|falls?|fell|crumples?|crumpled|reels?|reeled'
    r'|staggers?|staggered|recoils?|recoiled|retreats?|retreated'
    r'|backs?\s+away|backed\s+away|laughs?|laughed|sneers?|sneered'
    r'|snarls?|snarled|roars?|roared|charges?|charged'
    r'|swings?\s+back|swung\s+back|retaliates?|retaliated'
    r'|counters?|countered|slumps?|slumped|collapses?|collapsed'
    r'|drops?\s+(?:to|the)|dropped\s+(?:to|the)'
    r'|grunts?|grunted|gasps?|gasped|cries?\s+out|cried\s+out'
    r'|stumbles?|stumbled|wheezes?|wheezed'
    r'|dies?|died|killed|slain'
    r')\b',
    re.IGNORECASE,
)

# Player-side retraction grammar. Matches when the current turn is an
# explicit walk-back of a prior commitment ("never mind", "wait, let me
# rethink", "I sheath my dagger"). Suppresses the directive — the player
# is consciously withdrawing the prior move, not silently ignoring it.
_RETRACTION_RX = re.compile(
    r'\b('
    r'never\s+mind|nevermind'
    r'|change\s+my\s+mind|changed\s+my\s+mind'
    r'|on\s+second\s+thought'
    r'|actually,?\s+(?:i|let\s+me|wait)'
    r'|wait,?\s+(?:let\s+me|actually|i)'
    r'|hold\s+on,?\s+(?:let\s+me|actually|i)'
    r'|(?:i|i\'?ll|i\s+will)\s+(?:sheath|sheathe|holster|put\s+away|lower)'
    r'|stand\s+down|step\s+back\s+from'
    r'|(?:don|won|wouldn|shouldn)\'?t\s+(?:attack|swing|strike|hit)'
    r")\b",
    re.IGNORECASE,
)


def is_scene_shift_intent(text: str) -> bool:
    """Return True when the current turn's text indicates a scene shift.

    Boolean helper rather than a new INTENT_* tag so the existing
    7-tag classifier taxonomy stays clean. Scene shift can co-occur
    with TRIVIAL ("I leave"), SOCIAL ("I tell him I'm leaving"), etc.
    """
    if not text:
        return False
    return bool(SCENE_SHIFT_RX.search(text))


def _is_retracting(text: str) -> bool:
    """Return True when the current turn explicitly walks back a prior
    commitment.

    Matches retraction grammar (see _RETRACTION_RX). Used by
    compute_commitment_directive to suppress the directive when the
    player is consciously withdrawing — the godmode failure mode is
    *silent* erosion of commitment, not explicit retraction. Explicit
    retraction is a creative narrative choice the spec must allow.
    """
    if not text:
        return False
    return bool(_RETRACTION_RX.search(text))


def _has_reaction_verbs(dm_text: str, target_names) -> bool:
    """Return True when dm_text contains a reaction verb within ~120
    chars of a named target.

    Heuristic only. False positives possible (DM mentions a reaction
    verb unrelated to the target). v1 errs toward "resolved" — false
    negatives on detection (directive over-fires) are worse for godmode
    prevention than false positives (directive under-fires).

    target_names: iterable of NPC name strings (canonical or alias).
    """
    if not dm_text or not target_names:
        return False
    lower_text = dm_text.lower()
    for name in target_names:
        if not name:
            continue
        name_l = name.lower()
        # Find every occurrence of the target's name in dm_text and
        # check whether a reaction verb sits within a 120-char window
        # around it. Anchoring on the name is more robust than anchoring
        # on the verb because name matches are sparser.
        start = 0
        while True:
            idx = lower_text.find(name_l, start)
            if idx == -1:
                break
            window_start = max(0, idx - 120)
            window_end = min(len(dm_text), idx + len(name_l) + 120)
            window = dm_text[window_start:window_end]
            if _REACTION_VERBS.search(window):
                return True
            start = idx + len(name_l)
    return False


_COMMITMENT_DIRECTIVE_BODY = (
    "The player committed to a violent action last turn that the world has "
    "not yet resolved:\n"
    "  Prior action: {prior_action}\n"
    "  Current action: {current_action}\n\n"
    "The current action implies a scene shift away from the prior commitment. "
    "The world cannot honor both. Choose ONE this turn:\n"
    "  (a) Narrate the prior action's consequence first — what the target did "
    "in response, what landed or didn't, who reacted how. THEN handle the new "
    "action's consequence (it may or may not be possible, given the prior "
    "outcome).\n"
    "  (b) Refuse the new action explicitly through an in-fiction beat — the "
    "prior commitment has the floor. The target retaliates before the player "
    "can leave; bystanders move to block the exit; the player is mid-swing "
    "and cannot pivot.\n"
    "  (c) Require a roll for the new action that costs the player something "
    "— a disengage check at disadvantage, an opportunity attack from the "
    "target, a stealth roll to leave unnoticed.\n\n"
    "Do NOT silently accept both as if no contradiction exists. The player's "
    "prior commitment is the one with weight; the current action is being "
    "attempted in its shadow.\n\n"
    "Your narration MUST address the prior commitment before any new content; "
    "a response that ignores the prior commitment is INSUFFICIENT and breaks "
    "the table."
)


def compute_commitment_directive(
    intent_prior: str,
    intent_current: str,
    current_action_text: str,
    prior_action_text: str,
    avrae_resolved_since_prior: bool,
    prior_dm_response: str,
    prior_target_hints,
) -> tuple:
    """Return (directive_text, signals_dict).

    Pure function. Reads no DB, no buffers. Caller assembles signals.

    Gates (all must hold for the directive to fire):
      1. intent_prior == INTENT_COMBAT (locked §11.1: COMBAT-only)
      2. avrae_resolved_since_prior is False (no Avrae attack/cast/damage
         event for this actor since the prior turn — buffer drain check)
      3. _has_reaction_verbs(prior_dm_response, prior_target_hints) is False
         (regex resolution check, locked §11.2)
      4. is_scene_shift_intent(current_action_text) is True (current turn
         is a scene shift, not a continuation)
      5. _is_retracting(current_action_text) is False (locked §11.D —
         explicit retraction is a creative narrative choice, not godmode)

    Returns ('', {gate signals}) when any gate blocks. The signals dict is
    used by the caller for the per-turn `commitment_directive:` log line
    so the empirical baseline is observable regardless of whether the
    directive actually emitted.

    Composition (locked §11.8): caller renders this AFTER the consequence
    block in the tactical band of build_dm_context.
    """
    signals = {
        'fired': 0,
        'prior_intent': intent_prior or 'unknown',
        'current_intent': intent_current or 'unknown',
        'is_scene_shift': 0,
        'avrae_drained': 1 if avrae_resolved_since_prior else 0,
        'reaction_verbs': 0,
        'retraction_filtered': 0,
    }

    # Gate 1: COMBAT-only prior intent (§11.1).
    if intent_prior != INTENT_COMBAT:
        return '', signals

    # Gate 2: Avrae buffer drain.
    if avrae_resolved_since_prior:
        return '', signals

    # Gate 3: prior DM narration narratively resolved the commitment.
    has_react = _has_reaction_verbs(prior_dm_response, prior_target_hints)
    signals['reaction_verbs'] = 1 if has_react else 0
    if has_react:
        return '', signals

    # Gate 4: current turn is a scene shift.
    is_shift = is_scene_shift_intent(current_action_text)
    signals['is_scene_shift'] = 1 if is_shift else 0
    if not is_shift:
        return '', signals

    # Gate 5: not an explicit retraction.
    if _is_retracting(current_action_text):
        signals['retraction_filtered'] = 1
        return '', signals

    # All gates passed — emit the directive.
    body = _COMMITMENT_DIRECTIVE_BODY.format(
        prior_action=(prior_action_text or '(unrecorded)').strip()[:300],
        current_action=(current_action_text or '').strip()[:300],
    )
    signals['fired'] = 1
    return body, signals


def commitment_log_summary(signals: dict) -> str:
    """Compact log representation of commitment-directive gate signals.

    Used by dm_respond when emitting the per-turn `commitment_directive:`
    log line. The line fires every turn (not just when the directive
    emits) so the empirical baseline of gate hit rates is observable.
    """
    if not signals:
        return ("fired=0 prior_intent=unknown current_intent=unknown "
                "is_scene_shift=0 avrae_drained=0 reaction_verbs=0 "
                "retraction_filtered=0")
    return (
        f"fired={signals.get('fired', 0)} "
        f"prior_intent={signals.get('prior_intent', 'unknown')} "
        f"current_intent={signals.get('current_intent', 'unknown')} "
        f"is_scene_shift={signals.get('is_scene_shift', 0)} "
        f"avrae_drained={signals.get('avrae_drained', 0)} "
        f"reaction_verbs={signals.get('reaction_verbs', 0)} "
        f"retraction_filtered={signals.get('retraction_filtered', 0)}"
    )


# ─────────────────────────────────────────────────────────────────────
# Combat initiation orchestration directive (Track 3 — Session 20)
# ─────────────────────────────────────────────────────────────────────
# Detects the layer-3 binding failure mode: player commits to COMBAT in
# exploration mode with no active initiative tracker. Emrae's !attack -t
# <target> binds to <None> when no init tracker exists — the attack rolls
# against AC 10, emits "<None>: Dealt N damage!", and the violence silently
# evaporates. This directive instructs the LLM to emit !init begin +
# !init add <target> BEFORE !attack so Avrae has a real combatant to bind.
#
# Shape B (LLM-emits, §11.1 locked): extends the B2.1 attack template.
# The bot stays read-only on the Avrae channel. Only the LLM emits
# !-prefixed commands, exactly as it already does for !attack/!cast.
#
# Detection (§11.4): three AND'd gates — intent==COMBAT, mode!='combat',
# get_active_turn() is None proxy. All deterministic, no second LLM call.
#
# Mode flip (§11.2): reactive via existing _handle_init_event when Avrae
# responds to !init begin. No new intent-driven flip path.
#
# Composition (§11.8): INSIDE the === ROLL DIRECTIVE === block, BEFORE the
# existing !attack template. Init is a precondition on the attack, not a
# sibling narrative-pressure directive.

# Target hint cap: rendering limit for the candidate-target list.
_INIT_TARGET_HINT_CAP = 6

# Three-command body (with target hints available).
_INIT_DIRECTIVE_BODY = (
    "INIT NOT YET ACTIVE — INITIATIVE TRACKER MUST START THIS TURN.\n"
    "The world has not yet entered combat mechanically. Before your attack "
    "command, you MUST emit two preparatory commands so Avrae can bind the "
    "attack to a real combatant:\n\n"
    "  !init begin\n"
    "  !init add <target>\n\n"
    "Only THEN emit:\n\n"
    "  !attack <weapon-name> -t <target>\n\n"
    "(Three commands total, one per line, in this exact order. Replace "
    "<target> with the NPC the player committed to attacking."
    "{target_hint_block})\n\n"
    "YOUR NARRATION MUST come BEFORE all three commands — describe the "
    "player's draw, the room's reaction, the target's posture. A response "
    "that is ONLY commands is INSUFFICIENT and breaks the table.\n\n"
    "Correct example (narration first, then all three commands in order):\n"
    "  The barkeep's eyes go cold as your hand drops to the hilt of your dagger.\n"
    "  The common room holds its breath.\n"
    "  !init begin\n"
    "  !init add Garrick\n"
    "  !attack dagger -t Garrick\n\n"
    "Wrong example — do NOT do this (commands with no narration before them):\n"
    "  !init begin\n"
    "  !init add Garrick\n"
    "  !attack dagger -t Garrick"
)

# No-target-hint body (target_hints empty — emit !init begin only).
_INIT_PRECONDITION_BLOCK = (
    "INIT NOT YET ACTIVE — INITIATIVE TRACKER MUST START THIS TURN.\n"
    "The world has not yet entered combat mechanically. Begin the initiative "
    "tracker before the attack:\n\n"
    "  !init begin\n\n"
    "No NPC target is currently in scope for this scene. Name the target "
    "explicitly in your narration so the world can answer — once you have "
    "named them, also emit:\n\n"
    "  !init add <target-name>\n"
    "  !attack <weapon-name> -t <target-name>\n\n"
    "YOUR NARRATION MUST come BEFORE all commands — describe the player's "
    "draw, the room's reaction, the target's posture. A response that is "
    "ONLY commands is INSUFFICIENT and breaks the table."
)


def _render_target_hint_block(target_hints: list) -> str:
    """Format target-hint candidates into the prompt-readable infix string.

    Returns a formatted string starting with a space, suitable for
    direct interpolation into _INIT_DIRECTIVE_BODY's {target_hint_block}
    slot. Returns '' when the list is empty (caller uses the no-hint
    body instead). Truncates at _INIT_TARGET_HINT_CAP names.
    """
    if not target_hints:
        return ''
    names = [n for n in target_hints if n][:_INIT_TARGET_HINT_CAP]
    if not names:
        return ''
    return f" Candidate targets: {', '.join(names)}."


def compute_init_directive(
    intent_current: str,
    mode: str,
    has_active_turn: bool,
    target_hints: list,
) -> tuple:
    """Return (directive_body, signals_dict).

    Pure function. Reads no DB, no buffers. Caller assembles signals.

    Gates (all must hold for the directive to fire):
      1. intent_current == INTENT_COMBAT (§11.4 — same scope as godmode_gap)
      2. mode != 'combat' (scene not already in combat)
      3. has_active_turn is False (no active init tracker via get_active_turn proxy)

    Returns ('', {gate signals}) when any gate blocks. Signals dict fires
    on every call for the per-turn init_directive: log line so the empirical
    gate-hit baseline is observable regardless of whether the directive emits.

    When target_hints is empty, emits !init begin only with narration guidance
    for the LLM to name the target (loud-failure-recoverable per B2.1 doctrine).
    """
    signals = {
        'fired': 0,
        'intent_current': intent_current or 'unknown',
        'mode': mode or 'unknown',
        'has_active_turn': 1 if has_active_turn else 0,
        'target_hint_count': len(target_hints or []),
    }

    # Gate 1: COMBAT intent only (§11.1 locked: COMBAT-only scope).
    if intent_current != INTENT_COMBAT:
        return '', signals

    # Gate 2: mode is not already combat.
    if mode == 'combat':
        return '', signals

    # Gate 3: no active init tracker (proxy via has_active_turn from
    # get_active_turn(campaign_id) is not None at the call site).
    if has_active_turn:
        return '', signals

    # All gates passed — emit the directive.
    hints = [h for h in (target_hints or []) if h]
    if hints:
        body = _INIT_DIRECTIVE_BODY.format(
            target_hint_block=_render_target_hint_block(hints),
        )
    else:
        body = _INIT_PRECONDITION_BLOCK

    signals['fired'] = 1
    return body, signals


def init_log_summary(signals: dict) -> str:
    """Compact log representation of init-directive gate signals.

    Used by dm_respond when emitting the per-turn init_directive: log
    line. Fires every turn (not just when the directive emits) so the
    empirical baseline of gate hit rates is observable.

    Format mirrors commitment_log_summary for log-grep consistency.
    """
    if not signals:
        return ("fired=0 intent_current=unknown mode=unknown "
                "has_active_turn=0 target_hint_count=0")
    return (
        f"fired={signals.get('fired', 0)} "
        f"intent_current={signals.get('intent_current', 'unknown')} "
        f"mode={signals.get('mode', 'unknown')} "
        f"has_active_turn={signals.get('has_active_turn', 0)} "
        f"target_hint_count={signals.get('target_hint_count', 0)}"
    )


# ─────────────────────────────────────────────────────────────────────
# Combat persistence directive (Track 3 — Session 21)
# ─────────────────────────────────────────────────────────────────────
# Three sub-pressures composed into one === COMBAT PERSISTENCE === block:
#   1. Enemy persistence — do NOT narrate combat as wrapped while combatants
#      are alive. Avrae owns HP via !init list; combat ends only on !init end.
#   2. Condition awareness — honor any condition Avrae shows. Per-creature
#      when the snapshot has data; eight-condition reminder in fallback only.
#   3. Initiative-order enforcement — ON-turn confirm + naming-only.
#      OFF-turn block dropped per §11.B retroactive lock — Phase 2A.3 hard
#      gate at on_message catches off-turn messages before dm_respond runs.
#
# Detection: pure function, no DB. Caller (dm_respond) supplies mode +
# active_turn + combatants snapshot + typing identity. Master gate is
# mode=='combat'; everything below silent otherwise. See
# COMBAT_PERSISTENCE_DIRECTIVE_SPEC.md.

_PERSISTENCE_ABSTRACT_FALLBACK_BODY = (
    "COMBAT IS ACTIVE — AVRAE HOLDS THE MECHANICAL STATE.\n\n"
    "No `!init list` snapshot has been parsed yet this combat. Avrae owns HP "
    "and conditions. Combat ends ONLY when `!init end` fires, NEVER via "
    "narrative declaration. Do NOT narrate the encounter as wrapped, the "
    "enemies fled, or the fight resolved. If conditions are in play "
    "(frightened, grappled, paralyzed, prone, restrained, stunned, "
    "unconscious, poisoned, etc.), honor whatever Avrae shows in `!init list` "
    "/ `!status` outputs.\n\n"
    "(Tip: type `!init list` to surface the current combatant state.)"
)


def _format_snapshot_age(age_s):
    """Format snapshot age as '{N}s' or '>{N}min'. None → 'unknown age'."""
    if age_s is None:
        return 'unknown age'
    try:
        s = int(age_s)
    except (TypeError, ValueError):
        return 'unknown age'
    if s < 0:
        s = 0
    if s < 60:
        return f"{s}s"
    return f">{s // 60}min"


def _format_combatant_row(c):
    """Render one combatant row for the directive body. Decoding rules:
       - alive=0 → 'DEFEATED' (replaces HP/conditions clause)
       - hp_max=None → 'HP unknown'
       - else → 'HP {cur}/{max}'
       - conditions appended as ', conditions: ...' when non-empty
       - active=True → trailing '  ← active turn' marker
    """
    init_val = c.get('init', 0)
    name = (c.get('name') or '').strip() or '?'
    alive = c.get('alive', 1)
    if not alive:
        body = "DEFEATED"
    else:
        hp_cur = c.get('hp_current')
        hp_max = c.get('hp_max')
        if hp_max is None:
            body = "HP unknown"
        else:
            cur_str = str(hp_cur) if hp_cur is not None else "?"
            body = f"HP {cur_str}/{hp_max}"
        conditions = (c.get('conditions') or '').strip()
        if conditions:
            body += f", conditions: {conditions}"
    active_marker = "  ← active turn" if c.get('active') else ""
    return f"  {init_val:>3}: {name} — {body}{active_marker}"


def _render_combatants_block(combatants, snapshot_age_s):
    """Concrete combatants block (load-bearing path)."""
    rows = "\n".join(_format_combatant_row(c) for c in combatants)
    age = _format_snapshot_age(snapshot_age_s)
    return (
        "COMBAT IS ACTIVE — AVRAE HOLDS THE MECHANICAL STATE.\n\n"
        f"Last `!init list` snapshot ({age} ago):\n"
        f"{rows}\n\n"
        "Combat ends ONLY when `!init end` fires. Do NOT narrate the "
        "encounter as wrapped, the enemies fled, or the fight resolved while "
        "combatants above show HP > 0 (or HP unknown — assume alive until "
        "proven otherwise). If the encounter feels like it's resolving, "
        "surface that posture (enemies broken, surrendering, regrouping) and "
        "stop short of authoring the close — leave the resolution for "
        "`!init end` to confirm.\n\n"
        "Honor any condition listed above per its 5e rules — a frightened "
        "combatant cannot rally, a grappled one cannot move, a paralyzed one "
        "cannot act. Do not narrate around or through a condition this "
        "snapshot has set."
    )


def _render_turn_order_on_turn_block(char_name, controller, round_num, typing_actor):
    """ON-turn confirm block. Renders when typing user matches active controller."""
    return (
        f"INITIATIVE: round {round_num}, {char_name}'s turn "
        f"(Discord {controller}).\n"
        f"The current message is from {typing_actor} — ON-TURN. Narrate from "
        f"{char_name}'s frame. Resolve their declared action; the next "
        "initiative slot belongs to whoever is next in Avrae's order, not "
        "whoever types next."
    )


def _render_turn_order_naming_only(char_name, controller, round_num):
    """Naming-only block. Renders when typing identity is missing or
    can't be matched. (OFF-turn never reaches this path in production —
    Phase 2A.3 gate drops the message at on_message — but the function
    handles defensive fallback cases.)
    """
    return (
        f"INITIATIVE: round {round_num}, {char_name}'s turn "
        f"(Discord {controller}).\n"
        f"Narrate from {char_name}'s frame; the next initiative slot belongs "
        "to whoever is next in Avrae's order."
    )


def compute_persistence_directive(
    mode: str,
    active_turn: dict | None,
    combatants_snapshot: dict | None = None,
    typing_user_id: str | None = None,
    typing_character_name: str | None = None,
) -> tuple:
    """Return (directive_body, signals_dict).

    Pure function. Reads no DB. Caller assembles all inputs:
      - mode: from scene_state.mode (master gate; must == 'combat').
      - active_turn: from get_active_turn(campaign_id) — or None.
      - combatants_snapshot: from get_combatants(campaign_id).
      - typing_user_id / typing_character_name: caller-supplied identity for
        the typing player (Discord ID + canonical character name).

    Master gate: mode != 'combat' → returns ('', signals_with_combat_active=0).
    Otherwise composes:
      - concrete combatants block (or abstract fallback if no snapshot)
      - initiative block (ON-turn confirm or naming-only) when active_turn populated
    """
    signals = {
        'fired': 0,
        'combat_active': 0,
        'hp_known': 0,
        'conditions_known': 0,
        'combatants': 0,
        'snapshot_age_s': None,
        'active_turn_controller': 'none',
    }

    if mode != 'combat':
        return '', signals
    signals['combat_active'] = 1

    snap = combatants_snapshot or {}
    combatants = snap.get('combatants') or []
    snapshot_age = snap.get('snapshot_age_s')
    signals['combatants'] = len(combatants)
    signals['snapshot_age_s'] = snapshot_age
    signals['hp_known'] = (
        1 if any(c.get('hp_max') is not None for c in combatants) else 0
    )
    signals['conditions_known'] = (
        1 if any((c.get('conditions') or '').strip() for c in combatants) else 0
    )

    # Derive each combatant's active flag from active_turn (authoritative)
    # rather than the parsed snapshot's # marker — `dnd_combat_state` is
    # refreshed per !init turn, while the snapshot only refreshes per
    # !init list. The active turn name is the truer signal between snapshots.
    active_name = (active_turn or {}).get('character_name') or ''
    active_name_norm = active_name.strip().lower()
    annotated = []
    for c in combatants:
        ann = dict(c)
        ann['active'] = (
            active_name_norm != ''
            and (ann.get('name') or '').strip().lower() == active_name_norm
        )
        annotated.append(ann)

    if annotated:
        sections = [_render_combatants_block(annotated, snapshot_age)]
    else:
        sections = [_PERSISTENCE_ABSTRACT_FALLBACK_BODY]

    if active_turn:
        controller = active_turn.get('controller_id')
        char_name = active_turn.get('character_name', '') or ''
        round_num = active_turn.get('round', 0) or 0
        signals['active_turn_controller'] = (
            str(controller) if controller else 'none'
        )

        on_turn = bool(
            typing_user_id is not None
            and controller
            and str(typing_user_id) == str(controller)
        )
        if on_turn:
            sections.append(_render_turn_order_on_turn_block(
                char_name=char_name,
                controller=controller,
                round_num=round_num,
                typing_actor=typing_character_name or 'the typing player',
            ))
        else:
            sections.append(_render_turn_order_naming_only(
                char_name=char_name,
                controller=controller,
                round_num=round_num,
            ))

    body = "\n\n".join(sections)
    signals['fired'] = 1
    return body, signals


def persistence_log_summary(signals: dict) -> str:
    """Compact log representation of persistence-directive gate signals.

    Used by dm_respond when emitting the per-turn `persistence_directive:`
    log line. Fires every turn (not just when the directive emits) so the
    empirical baseline is observable. Mirrors commitment_log_summary +
    init_log_summary shapes.
    """
    if not signals:
        return ("fired=0 combat_active=0 hp_known=0 conditions_known=0 "
                "combatants=0 snapshot_age_s=none "
                "active_turn_controller=none")
    age = signals.get('snapshot_age_s')
    age_str = (
        f"{int(age)}" if isinstance(age, (int, float)) and age is not None
        else 'none'
    )
    return (
        f"fired={signals.get('fired', 0)} "
        f"combat_active={signals.get('combat_active', 0)} "
        f"hp_known={signals.get('hp_known', 0)} "
        f"conditions_known={signals.get('conditions_known', 0)} "
        f"combatants={signals.get('combatants', 0)} "
        f"snapshot_age_s={age_str} "
        f"active_turn_controller={signals.get('active_turn_controller', 'none')}"
    )


# ─── Loot directive (Track 4 #2, Session 22) ─────────────────────────────────
# Pure function. Takes a list of pending loot rows (from get_pending_loot) and
# composes a narration directive instructing the LLM to surface defeated
# creatures' drops. v1 contract: surface for player to claim — DO NOT auto-add
# to inventory. Coin pickup is hinted via inline mechanical command
# (!game coin +Nsp); the bot-Avrae write boundary stays intact (only LLMs
# emit !-commands, never the bot itself).

_VALID_DENOMS = {'cp', 'sp', 'gp', 'ep', 'pp'}


def _format_loot_bullet(row: dict) -> str:
    """Render one pending-loot row as a markdown bullet line.

    Shape: `- {creature} ({coin}; {item, item, item})`. Coin or items section
    omitted if empty. Coin formatted as `N sp` (space-separated, lowercase
    denom)."""
    creature = (row.get('creature') or '').strip() or '(unnamed)'
    parts = []
    coin_amt = row.get('coin_amount')
    coin_denom = (row.get('coin_denom') or '').lower()
    if coin_amt is not None and coin_denom in _VALID_DENOMS:
        parts.append(f"{coin_amt} {coin_denom}")
    items = row.get('items') or []
    if items:
        parts.append(", ".join(items))
    if parts:
        return f"- {creature} ({'; '.join(parts)})"
    return f"- {creature}"


def _total_coin_summary(rows: list[dict]) -> str:
    """Sum coin across pending rows, grouped by denomination. Returns a
    short string like '5 sp, 3 gp' or 'none' when no coin present."""
    totals: dict[str, int] = {}
    for r in rows:
        amt = r.get('coin_amount')
        denom = (r.get('coin_denom') or '').lower()
        if amt is None or denom not in _VALID_DENOMS:
            continue
        totals[denom] = totals.get(denom, 0) + int(amt)
    if not totals:
        return 'none'
    # Order by canonical D&D denomination
    order = ['cp', 'sp', 'ep', 'gp', 'pp']
    parts = [f"{totals[d]} {d}" for d in order if d in totals]
    return ", ".join(parts) if parts else 'none'


def _coin_hint_example(summary: str) -> str:
    """Build the concrete `!game coin +Nsp`-style example from the directive's
    own total_coin_summary. The example is GROUND TRUTH for this drop, not a
    static placeholder — without dynamic anchoring the LLM treats the example
    as data and emits its number instead of the listed amount (S22 live test
    failure mode: directive said 12 sp, static example said 3 sp, LLM emitted
    +3cp). Returns '' when no coin in pending."""
    if not summary or summary == 'none':
        return ''
    first = summary.split(',')[0].strip()
    if not first:
        return ''
    parts = first.split()
    if len(parts) != 2:
        return ''
    amt, denom = parts
    return f"{amt}{denom}"


def compute_loot_directive(pending_loot: list[dict]) -> tuple:
    """Render pending loot as a narration directive.

    Returns (directive_body, signals).
      signals = {
        'fired': bool,            # True iff body is non-empty
        'pending_count': int,
        'total_coin_summary': str,
      }

    Body shape (omitted entirely when no pending loot):

        === LOOT TO SURFACE ===
        The party has defeated:
        - Goblin Patrol (3 sp; rusty shortsword, crude bow)
        - Wolf (wolf pelt, wolf fang)

        These items are AUTHORITATIVE and EXHAUSTIVE — they are everything
        the bodies carry. ... [tightened framing — see body below]

    Pure function — caller is responsible for marking surfaced after the
    LLM call succeeds.
    """
    rows = pending_loot or []
    signals = {
        'fired': False,
        'pending_count': len(rows),
        'total_coin_summary': 'none',
    }
    if not rows:
        return '', signals
    bullets = "\n".join(_format_loot_bullet(r) for r in rows)
    summary = _total_coin_summary(rows)
    coin_example = _coin_hint_example(summary)
    if coin_example:
        # Anchor the example to the directive's own data so the LLM treats
        # the listed amount as ground truth, not as a substitutable template.
        coin_line = (
            f"For coin pickup, surface a mechanical hint using the actual "
            f"amount: !game coin +{coin_example} for the {summary} listed "
            f"above."
        )
    else:
        # Explicit "no coin" framing prevents the LLM from inventing coin
        # the table did not list.
        coin_line = "This drop has no coin — narrate the items only."
    body = (
        "The party has defeated:\n"
        f"{bullets}\n\n"
        "These items are AUTHORITATIVE and EXHAUSTIVE — they are everything "
        "the bodies carry. Do NOT invent additional items, change quantities, "
        "or substitute thematic alternatives. Narrate the discovery of THESE "
        "specific items only — if the table lists three items and coin, the "
        "player finds exactly three items and exactly that coin, nothing "
        "more.\n\n"
        "If retrieved past events (\"RELEVANT PAST EVENTS\" block above) "
        "describe different loot for this body, ignore those descriptions. "
        "The list in this block supersedes any prior narration and is the "
        "current ground truth.\n\n"
        f"{coin_line}\n\n"
        "Do NOT auto-add items to inventory. Surface them for the player "
        "to claim or leave — the player will use /giveitem or claim "
        "narratively."
    )
    signals['fired'] = True
    signals['total_coin_summary'] = summary
    return body, signals


def loot_log_summary(signals: dict) -> str:
    """Compact log representation of loot-directive signals.
    Used by dm_respond when emitting the per-turn `loot_directive:` log line.
    Fires every turn so the empirical baseline is observable."""
    if not signals:
        return "fired=0 pending_count=0"
    return (
        f"fired={1 if signals.get('fired') else 0} "
        f"pending_count={signals.get('pending_count', 0)}"
    )


# ─── Active-State Footer (Track 6 #1) ────────────────────────────────
# Bot-appended state header that prepends above the existing
# ⚔ {actor} 📍 {location} 🗒️ {quests} line in the Discord embed footer.
# Pure function: takes already-loaded state dicts, returns a
# multi-line string. The caller (discord_dnd_bot._dm_respond_and_post)
# is responsible for the DB reads and wrapping the call in try/except
# so footer errors never block narration posting.

_PC_TURN_HINT = (
    "Your turn — narrate your action, or use !attack / !cast / !check."
)
_NPC_TURN_HINT = (
    "NPC turn — wait for resolution, or !init next to skip ahead."
)
_NO_ACTIVE_TURN_LINE = (
    "Turn: (not set — Avrae state may be stale; try !init list)"
)


def _is_pc_turn(active_name: str, bound_pc_names) -> bool:
    """Case-insensitive membership test against bound PC names."""
    if not active_name:
        return False
    bound = bound_pc_names or set()
    if isinstance(bound, (list, tuple)):
        bound = set(bound)
    if active_name in bound:
        return True
    lowered = {n.lower() for n in bound if n}
    return active_name.lower() in lowered


def _find_init(combatants: list, name: str):
    """Return init value for combatant `name` (case-insensitive), or None."""
    if not name or not combatants:
        return None
    target = name.strip().lower()
    for c in combatants:
        cname = (c.get('name') or '').strip().lower()
        if cname == target:
            return c.get('init')
    return None


def _next_combatant(combatants: list, current_name: str):
    """Return the combatant immediately after `current_name` in init DESC
    order (wrapping back to top), or None if the current combatant isn't
    in the snapshot or there's only one combatant.

    combatants is expected pre-sorted init DESC (engine.get_combatants
    guarantees this).
    """
    if not combatants or not current_name or len(combatants) < 2:
        return None
    target = current_name.strip().lower()
    names = [(c.get('name') or '').strip().lower() for c in combatants]
    try:
        idx = names.index(target)
    except ValueError:
        return None
    next_idx = (idx + 1) % len(combatants)
    if next_idx == idx:
        return None
    return combatants[next_idx]


def render_state_footer(scene_state: dict | None,
                        active_turn: dict | None,
                        combatants_payload: dict | None,
                        bound_pc_names=None) -> tuple:
    """Render the active-state footer header lines.

    Pure function. Returns (footer_text, signals).

    footer_text is a multi-line string ending in '\\n' (so the caller can
    simply prepend it to the existing footer line) or '' if there's
    nothing useful to render (no scene_state).

    signals: {'mode', 'active_turn_name', 'round'} — for the
    state_footer log line.

    Inputs:
      scene_state         — engine.get_scene_state(campaign_id), or None.
      active_turn         — engine.get_active_turn(campaign_id), or None.
      combatants_payload  — engine.get_combatants(campaign_id) (the dict
                            with 'combatants' key), or None.
      bound_pc_names      — list/set of bound PC names (case-insensitive
                            membership). Used to choose player vs NPC hint.

    Caller MUST wrap this call in try/except — see render_state_footer
    docs in COMBAT_PERSISTENCE_DIRECTIVE_SPEC.md for the soft-fail
    contract. Footer must NEVER prevent narration from posting.
    """
    signals = {
        'mode': 'unknown',
        'active_turn_name': None,
        'round': None,
        'campaign_day': None,
        'day_phase': None,
    }
    if not scene_state:
        # No scene state means we don't even know mode; skip header.
        return '', signals

    mode = (scene_state.get('mode') or 'exploration').lower()
    signals['mode'] = mode

    # Track 4 #3 — time progression footer extension. Only render the
    # `· Day N, Phase` suffix when both fields are present (legacy
    # scene_state rows pre-migration have neither — backward compat per
    # §9 test 28).
    day = scene_state.get('campaign_day')
    phase = scene_state.get('day_phase')
    if day is not None and phase:
        time_suffix = f" · Day {day}, {phase}"
        signals['campaign_day'] = day
        signals['day_phase'] = phase
    else:
        time_suffix = ''

    if mode == 'combat':
        body, signals = _render_combat_header(
            active_turn, combatants_payload, bound_pc_names, signals
        )
        if not body:
            return body, signals
        # Splice the time suffix into the first line (the
        # `⚔ Combat — Round N` header) before its trailing newline.
        if time_suffix and '\n' in body:
            head, sep, rest = body.partition('\n')
            body = head + time_suffix + sep + rest
        return body, signals
    if mode == 'exploration':
        return f'📖 Exploration{time_suffix}\n', signals
    if mode == 'social':
        return f'💬 Social{time_suffix}\n', signals
    # Unknown mode — render with a warning prefix so the issue is visible.
    return f'⚠ {mode}{time_suffix}\n', signals


def _render_combat_header(active_turn: dict | None,
                          combatants_payload: dict | None,
                          bound_pc_names,
                          signals: dict) -> tuple:
    """Build the combat-mode block. Mutates `signals` for telemetry."""
    combatants = []
    if combatants_payload:
        combatants = combatants_payload.get('combatants') or []

    if not active_turn:
        # Mode says combat but no active turn row — Avrae state stale.
        # Show the known/unknown round if any combatant data exists,
        # else '?'. (combatants_snapshot has no round; keep '?' for v1.)
        body = "⚔ Combat — Round ?\n" + _NO_ACTIVE_TURN_LINE + "\n"
        return body, signals

    name = (active_turn.get('character_name') or '').strip()
    round_num = active_turn.get('round')
    signals['active_turn_name'] = name or None
    signals['round'] = round_num

    round_label = round_num if round_num is not None else '?'
    cur_init = _find_init(combatants, name)
    init_label = f' ({cur_init})' if cur_init is not None else ''

    lines = [f"⚔ Combat — Round {round_label}"]
    lines.append(f"Turn: {name or '(unknown)'}{init_label}")

    nxt = _next_combatant(combatants, name)
    if nxt:
        nxt_name = (nxt.get('name') or '').strip() or '(unknown)'
        nxt_init = nxt.get('init')
        nxt_init_label = f' ({nxt_init})' if nxt_init is not None else ''
        lines.append(f"Up next: {nxt_name}{nxt_init_label}")

    if _is_pc_turn(name, bound_pc_names):
        lines.append(_PC_TURN_HINT)
    else:
        lines.append(_NPC_TURN_HINT)

    return "\n".join(lines) + "\n", signals


def state_footer_log_summary(signals: dict) -> str:
    """Compact log representation of state-footer signals.
    Used by _dm_respond_and_post for the per-turn `state_footer:` line.

    Extended in Track 4 #3 (Session 27) with `day=` and `phase=` fields.
    Both render `none` when scene_state predates the time-progression
    migration or carries NULLs."""
    if not signals:
        return "mode=unknown active_turn=none round=none day=none phase=none"
    name = signals.get('active_turn_name') or 'none'
    round_v = signals.get('round')
    round_s = str(round_v) if round_v is not None else 'none'
    day_v = signals.get('campaign_day')
    day_s = str(day_v) if day_v is not None else 'none'
    phase_s = signals.get('day_phase') or 'none'
    return (
        f"mode={signals.get('mode', 'unknown')} "
        f"active_turn={name} round={round_s} "
        f"day={day_s} phase={phase_s}"
    )


# ─── Combat Redirect Directive (Track 6 #2, Session 23) ──────────────
# Pure function. Companion to S19's compute_commitment_directive.
# S19's directive narrows to escape-intent transitions (COMBAT prior →
# scene-shift current). This directive is broader: fires on every PC
# on-turn narration in active combat that has at least one alive enemy.
# Adds informational pressure (LLM should narrate threats reacting,
# not refuse player input). Hard refusal lives in 2A.3 off-turn gate;
# this is explanatory.
#
# Master gate (all must hold):
#   1. scene_state.mode == 'combat'
#   2. combatants snapshot has ≥1 alive enemy (alive=1 AND name !=
#      bound_character_name, case-insensitive)
#   3. active_turn.character_name == bound_character_name (case-insens),
#      OR bound_character_name is None (default-fire — any human-typed
#      input is the PC)
#
# Returns (body, signals). signals = {fired, reason, alive_enemies,
# threat_summary}.

_REDIRECT_PROLOGUE = (
    "Combat is ACTIVE. The player's narration may attempt to bypass "
    "combat (leaving the scene, ignoring threats, treating combat as "
    "resolved). Do NOT honor exit narration as resolution. Do NOT "
    "narrate the player escaping, departing, or shifting to a new "
    "scene unless they have explicitly used !init end or all enemies "
    "are at 0 HP."
)

_REDIRECT_GUIDANCE = (
    "If the player narrates departure, redirect their narration toward "
    "the active threat. Frame the redirect as the world reacting: "
    "\"Garrick steps between you and the door, blade still raised.\" "
    "Do NOT refuse the player's input as invalid. Do NOT say \"you "
    "cannot do that.\" Inform the player about the world state through "
    "narration of the threat's response.\n\n"
    "The player can end combat with !init end if combat should be over."
)


def _format_threat_bullet(c: dict) -> str:
    """Render one alive-enemy bullet for the COMBAT REDIRECT body.

    Combatant dict keys (from get_combatants): name, hp_current, hp_max,
    conditions, alive, side. Renders with HP when known, "HP unknown"
    when not, and conditions appended when present.
    """
    name = (c.get('name') or '').strip() or '(unnamed)'
    hp_cur = c.get('hp_current')
    hp_max = c.get('hp_max')
    if hp_cur is not None and hp_max is not None:
        hp_label = f"{hp_cur}/{hp_max} HP"
    else:
        hp_label = "HP unknown"
    conditions = (c.get('conditions') or '').strip()
    if conditions:
        return f"- {name} ({hp_label}, {conditions})"
    return f"- {name} ({hp_label})"


def _is_pc_name(name: str, bound_character_name: str | None) -> bool:
    """Case-insensitive PC-match against the typing player's bound name."""
    if not name or not bound_character_name:
        return False
    return name.strip().lower() == bound_character_name.strip().lower()


def compute_combat_redirect_directive(
    scene_state: dict | None,
    active_turn: dict | None,
    combatants: list | None,
    bound_character_name: str | None = None,
) -> tuple:
    """Render combat-redirect directive when on-turn player narration in
    active combat needs informational pressure to keep the world reactive.

    Pure function. Reads no DB. Caller assembles all inputs and is
    responsible for try/except wrapping at the call site (directive
    failure must NEVER prevent narration from posting).

    Args:
      scene_state          — engine.get_scene_state(campaign_id) or None.
      active_turn          — engine.get_active_turn(campaign_id) or None.
      combatants           — list of combatant dicts (from
                             engine.get_combatants(campaign_id)['combatants'])
                             or None / [].
      bound_character_name — typing player's bound character name.
                             Can be None (default-fire — any narration
                             must be from the PC since 2A.3 already
                             dropped off-turn input).

    Returns:
      (body, signals)
        body:    multi-line directive string, or '' if gate fails.
                 Caller (build_dm_context) wraps with `=== COMBAT
                 REDIRECT ===` header.
        signals: {fired, reason, alive_enemies, threat_summary}.

    signals.reason values:
      'fired'           — gate passed, body non-empty
      'gate_mode'       — scene_state missing or mode != 'combat'
      'gate_no_enemies' — combat mode but zero alive non-PC combatants
      'gate_npc_turn'   — alive enemies present but active turn isn't PC
    """
    signals = {
        'fired': 0,
        'reason': 'gate_mode',
        'alive_enemies': 0,
        'threat_summary': '',
    }

    # Gate 1: combat mode
    mode = (scene_state or {}).get('mode') if scene_state else None
    if mode != 'combat':
        return '', signals

    # Gate 2: at least one alive enemy
    rows = list(combatants or [])
    alive_enemies = []
    for c in rows:
        if not isinstance(c, dict):
            continue
        try:
            if int(c.get('alive', 0)) != 1:
                continue
        except (TypeError, ValueError):
            continue
        cname = (c.get('name') or '').strip()
        if not cname:
            continue
        if _is_pc_name(cname, bound_character_name):
            continue  # PCs aren't threats
        alive_enemies.append(c)

    signals['alive_enemies'] = len(alive_enemies)
    if not alive_enemies:
        signals['reason'] = 'gate_no_enemies'
        return '', signals

    # Gate 3: PC turn (or no-PC-binding default-fire)
    active_name = ((active_turn or {}).get('character_name') or '').strip()
    if bound_character_name is not None and not _is_pc_name(
        active_name, bound_character_name
    ):
        signals['reason'] = 'gate_npc_turn'
        return '', signals

    # Compose threat list — sorted by init DESC where available
    # (combatants from get_combatants are already init-DESC sorted, so
    # alive_enemies preserves that order).
    threat_lines = [_format_threat_bullet(c) for c in alive_enemies]
    threat_summary = ", ".join(
        f"{(c.get('name') or '').strip()}"
        for c in alive_enemies
    )
    signals['threat_summary'] = threat_summary

    body = (
        f"{_REDIRECT_PROLOGUE}\n\n"
        f"Active threats:\n"
        + "\n".join(threat_lines)
        + f"\n\n{_REDIRECT_GUIDANCE}"
    )

    signals['fired'] = 1
    signals['reason'] = 'fired'
    return body, signals


def combat_redirect_log_summary(signals: dict) -> str:
    """Compact log representation of combat-redirect-directive signals.

    Used by dm_respond when emitting the per-turn `combat_redirect:`
    log line. Fires every turn (not just when the directive emits) so
    the empirical baseline is observable. Mirrors persistence_log_summary
    + commitment_log_summary shapes."""
    if not signals:
        return "fired=0 alive_enemies=0 reason=gate_mode"
    return (
        f"fired={signals.get('fired', 0)} "
        f"alive_enemies={signals.get('alive_enemies', 0)} "
        f"reason={signals.get('reason', 'gate_mode')}"
    )


# ─────────────────────────────────────────────────────────
# Time directive (Track 4 #3, Session 27)
# ─────────────────────────────────────────────────────────
# Seventh §59 directive sibling. Pure function over (scene_state,
# just_advanced); empty string on every turn except the one immediately
# following an advancement. Caller resolves `just_advanced` via
# engine.time_just_advanced() (recency check on dnd_time_advancements
# per §11.E sub-(iii)α). Caller wraps in try/except per §59.

def compute_time_directive(scene_state, just_advanced: bool) -> str:
    """Return the time-advancement directive string for this turn.

    Pure function. Returns the multi-line directive when `just_advanced`
    is True and scene_state carries time fields; '' otherwise.

    The instruction text asks the LLM for one in-fiction beat marking
    the new time of day, then to hand agency back to the player. Per
    §11.E sub-(i)α + sub-(ii)α — fires on the just-advanced turn only.
    """
    if not scene_state or not just_advanced:
        return ''
    day = scene_state.get('campaign_day')
    phase = scene_state.get('day_phase')
    if day is None or not phase:
        return ''
    return (
        f"campaign_day={day}\n"
        f"day_phase={phase}\n"
        "instruction=Open with one in-fiction beat marking the new time "
        "of day — dawn light, lanterns guttering out, market stalls "
        "opening, the chill of a late-night street, whatever fits the "
        "location. One sentence, location-appropriate. Then return "
        "agency to the player. Do NOT narrate the intervening hours."
    )


# ─────────────────────────────────────────────────────────
# OOC Advisory Lane (Track 6 #3)
# ─────────────────────────────────────────────────────────
# Read-only OOC Q&A surface in #dm-aside. Players ask Virgil out-of-character
# questions about state, mechanics, options. Advisory mode does NOT mutate
# scene state, does NOT emit `!`-prefixed Avrae commands, does NOT write to
# ChromaDB session memory (chroma is a cross-turn behavior source — OOC
# noise must never re-surface as narrative grounding), and does NOT compose
# tactical directives (those are pressure for narration, not for Q&A).
#
# Same LLM, different system prompt, different context shape: factual state
# reference only, no past-narration retrieval.

ADVISORY_SYSTEM_PROMPT = (
    "You are Virgil, speaking out-of-character to help the player understand "
    "the game. This is a private aside channel — not in-character narration.\n"
    "\n"
    "Your job:\n"
    "- Answer the player's questions about what's happening, what they have, "
    "what they can do.\n"
    "- Explain mechanics, options, and game state plainly.\n"
    "- Reference the scene, inventory, active turn, and combat state below "
    "as factual reference.\n"
    "- Suggest commands the player could run, but DO NOT emit them yourself.\n"
    "- Be brief, practical, and friendly — like a DM leaning over to whisper "
    "a clarification.\n"
    "\n"
    "What you must NOT do:\n"
    "- Do not narrate scene events (\"you draw your sword...\") — this is "
    "OOC, not gameplay.\n"
    "- Do not mutate the scene, advance time, or trigger combat.\n"
    "- Do not invent items, NPCs, or world state the player doesn't already "
    "have.\n"
    "- Do not emit `!`-prefixed Avrae commands — only describe them as "
    "options for the player to type.\n"
    "- Do not break character so far that you forget you are still Virgil — "
    "the warm, knowledgeable DM voice persists, just out of scene.\n"
    "\n"
    "Critical command guidance:\n"
    "- A complete command reference is included below in the AVAILABLE "
    "COMMANDS section. Use it as the source of truth for command syntax "
    "and availability.\n"
    "- When suggesting a command, match the syntax in AVAILABLE COMMANDS "
    "exactly.\n"
    "- If the player asks about a command not in AVAILABLE COMMANDS, say so "
    "honestly (\"I don't see that as an available command\") rather than "
    "guessing or inventing syntax.\n"
    "- Suggest commands the player could run; DO NOT emit them yourself.\n"
    "\n"
    "Format:\n"
    "- Plain prose, conversational.\n"
    "- Short answers preferred.\n"
    "- Use bullet lists only when the player asks \"what are my options\".\n"
)


# COMMANDS.md doc path — read fresh on every advisory request so doc edits
# take effect without a bot restart. Module-level Path so tests can monkey-
# patch the location for fixture-based testing.
import os
from pathlib import Path as _Path

COMMANDS_DOC_PATH = _Path(
    os.environ.get(
        'VIRGIL_COMMANDS_DOC',
        '/home/jordaneal/virgil-docs/COMMANDS.md'
    )
)


def _load_commands_reference() -> str:
    """Read COMMANDS.md fresh on every call (no caching). Returns the full
    file content as a string, or '' if the file is missing or unreadable.

    Caller decides telemetry — this function just gives back content.
    Pure-ish: same file content at the configured path → same output.

    Cost: a single ~5–10 KB synchronous file read per advisory request.
    Negligible relative to the LLM call that follows.
    """
    try:
        return COMMANDS_DOC_PATH.read_text(encoding='utf-8')
    except FileNotFoundError:
        return ''
    except Exception:
        # Corrupt encoding, permission errors, etc — degrade silently to
        # empty so advisory still answers, just without the reference.
        return ''


def build_advisory_context(
    campaign: Optional[dict],
    bound_character_name: Optional[str],
    scene_state: Optional[dict],
    active_turn: Optional[dict],
    combatants_snapshot: Optional[dict],
    inventory: Optional[list],
    pending_loot: Optional[list],
    commands_reference: Optional[str] = None,
) -> str:
    """Pure read. Assembles state-reference context for advisory mode.

    Returns a formatted block to feed into the router as system context.
    All inputs are pre-fetched by the caller (one place that knows about
    the engine — keeps this module free of dnd_engine imports for
    pure-function testability).

    Includes:
    - Campaign name + scene mode + location
    - Active turn (if combat)
    - Combatants snapshot (HP / conditions / alive flag)
    - Bound character's narrative inventory
    - Pending loot (if any)
    - AVAILABLE COMMANDS block — full COMMANDS.md content when present,
      omitted entirely when missing (no header, no placeholder)

    `commands_reference` is the loaded COMMANDS.md text. Caller (typically
    `_advisory_respond`) calls `_load_commands_reference()` first, logs
    presence/size for telemetry, then passes the string in. When None,
    this function calls the loader itself — convenient for tests that
    don't care about telemetry.

    Does NOT include:
    - Tactical directives (pacing, persistence, loot, redirect, footer)
    - Past-narration retrieval (no chroma_search)
    - DnD knowledge corpus exemplars
    - Mode-flip / capability decisions (advisory doesn't decide rolls)
    """
    lines: list[str] = []
    lines.append("=== STATE REFERENCE (read-only) ===")

    if campaign:
        camp_name = (campaign.get('name') or '').strip() or 'unnamed'
        lines.append(f"Campaign: {camp_name}")
    else:
        lines.append("Campaign: (none active)")

    if bound_character_name:
        lines.append(f"Asking player's character: {bound_character_name}")
    else:
        lines.append("Asking player's character: (no bound character)")

    # Scene block
    if scene_state:
        mode = (scene_state.get('mode') or 'exploration').strip() or 'exploration'
        lines.append(f"Mode: {mode}")
        # Ship 2 (S39) — location renders from derived label (JOIN on
        # dnd_locations via current_location_id). The freetext `location`
        # column was deleted as a §76 four-property latent-canon surface.
        # Scene focus line removed — its backing column was a §76 deletion
        # target; no replacement (advisory state block doesn't need it).
        loc = (scene_state.get('location_label') or '').strip()
        if loc:
            lines.append(f"Location: {loc}")
        last_action = (scene_state.get('last_player_action') or '').strip()
        if last_action:
            # Truncate to a reasonable length so advisory context doesn't
            # balloon on long narration turns.
            lines.append(f"Last player action: {last_action[:280]}")
    else:
        lines.append("Mode: (no scene started)")

    # Active turn (combat only — None outside combat)
    if active_turn:
        lines.append(
            f"Active turn: {active_turn.get('character_name', '?')} "
            f"(round {active_turn.get('round', '?')})"
        )

    # Combatant snapshot
    if combatants_snapshot and combatants_snapshot.get('combatants'):
        combatants = combatants_snapshot['combatants']
        lines.append("Combatants (init DESC):")
        for c in combatants[:20]:  # cap at 20 to stay under prompt size
            name = (c.get('name') or '?').strip()
            hp_cur = c.get('hp_current')
            hp_max = c.get('hp_max')
            alive = c.get('alive')
            conds = (c.get('conditions') or '').strip()
            init_v = c.get('init')
            hp_str = (
                f"{hp_cur}/{hp_max}"
                if hp_cur is not None and hp_max is not None
                else "?/?"
            )
            row = f"- {name} (init {init_v}, HP {hp_str}"
            if not alive:
                row += ", DOWN"
            if conds:
                row += f", conds: {conds}"
            row += ")"
            lines.append(row)

    # Inventory (narrative items only — Avrae owns sheet gear)
    if inventory:
        lines.append(f"{bound_character_name or 'Character'}'s inventory:")
        for item in inventory[:40]:  # cap to keep prompt bounded
            name = (item.get('item_name') or '?').strip()
            qty = item.get('quantity', 1)
            lines.append(f"- {name} x{qty}")
    else:
        lines.append("Inventory: (empty)")

    # Pending loot (unclaimed defeats)
    if pending_loot:
        lines.append("Pending loot (unclaimed):")
        for row in pending_loot[:10]:
            creature = (row.get('creature') or '?').strip()
            items = row.get('items') or []
            coin = row.get('coin') or {}
            bits = []
            if coin.get('amount'):
                bits.append(f"{coin['amount']} {coin.get('denom', 'gp')}")
            if items:
                bits.append(f"{len(items)} item(s)")
            tail = f" — {', '.join(bits)}" if bits else ""
            lines.append(f"- from {creature}{tail}")

    state_block = "\n".join(lines)

    # AVAILABLE COMMANDS block — appended only when COMMANDS.md is present.
    # When missing we omit entirely (no header, no placeholder) so the LLM
    # doesn't hallucinate around an empty section. Caller logs the missing
    # state for telemetry; this function stays content-only.
    if commands_reference is None:
        commands_reference = _load_commands_reference()
    if commands_reference:
        return (
            f"{state_block}\n\n"
            f"=== AVAILABLE COMMANDS ===\n{commands_reference.rstrip()}\n"
        )
    return state_block


def advisory_log_summary(
    bound_character_name: Optional[str],
    scene_state: Optional[dict],
    inventory: Optional[list],
    combatants_snapshot: Optional[dict],
) -> str:
    """Compact log signature for advisory_respond: telemetry. Pure function."""
    in_combat = 0
    if scene_state and (scene_state.get('mode') or '').strip() == 'combat':
        in_combat = 1
    inv_n = len(inventory or [])
    comb_n = len(((combatants_snapshot or {}).get('combatants')) or [])
    has_char = 1 if bound_character_name else 0
    return (
        f"state_combat={in_combat} state_inventory_count={inv_n} "
        f"state_combatants={comb_n} bound_char={has_char}"
    )


# ─────────────────────────────────────────────────────────
# Ship 1 (S34) — Resolution Binding (RESOLUTION_BINDING_SPEC.md)
# ─────────────────────────────────────────────────────────
# Closes Finding L + F-45 regression + Bug 1 Phase 2.
#
# Eighth Doctrine §59 instance: pure function sibling to
# compute_persistence_directive et al. Computes roll_total vs DC from a
# consumed pending directive row + the Avrae roll embed that matched it,
# returns an immutable ResolutionResult that downstream renders as the
# AUTHORITATIVE-CANON top-of-prompt block + bottom-of-prompt hardstop echo.
# Engine-bound binding > validator-on-LLM-output (filed doctrine candidate).
#
# Ship A (S36) extension: ResolutionTexture sub-dataclass attached to
# ResolutionResult.texture carries difficulty band + margin tier + stakes
# tier + crit signal for AUTHORITATIVE-CANON block scaling. Internal
# scaffolding — player never sees the breakdown; only the LLM consumes
# it as constraint on narration shape.


@dataclass(frozen=True)
class ResolutionTexture:
    """Narrative-texture signals attached to a ResolutionResult (Ship A §4)."""
    # Derived from DC vs actor modifier:
    effective_dc: int
    modifier: int
    difficulty_band: str       # 'trivial'|'easy'|'medium'|'hard'|'very_hard'|'nearly_impossible'

    # Derived from roll_total vs dc:
    margin: int
    margin_tier: str           # 'catastrophic_fail'|'clear_fail'|'close_fail'
                               # |'razor_pass'|'clean_pass'|'smashing_pass'

    # Derived from scene state at consume time:
    stakes_tier: str           # 'low' | 'medium' | 'high'
    stakes_signals: dict = field(default_factory=dict)


def _bucket_difficulty(effective_dc: int) -> str:
    """Map effective DC (DC - modifier) to a 5e RAW difficulty band (spec §8)."""
    if effective_dc <= 5:    return 'trivial'
    if effective_dc <= 10:   return 'easy'
    if effective_dc <= 15:   return 'medium'
    if effective_dc <= 20:   return 'hard'
    if effective_dc <= 25:   return 'very_hard'
    return 'nearly_impossible'


def _bucket_margin(margin: int) -> str:
    """Map margin (roll_total - dc, signed) to a margin tier (spec §9).
    Margin == 0 is the single-value razor_pass bucket — strict-≥ pass per
    Ship 1 §5.4."""
    if margin <= -10:  return 'catastrophic_fail'
    if margin <= -5:   return 'clear_fail'
    if margin <= -1:   return 'close_fail'
    if margin == 0:    return 'razor_pass'
    if margin <= 9:    return 'clean_pass'
    return 'smashing_pass'


# Ship A §5.2 — strong-intent regex against scene_state.last_player_action.
# Engine-bound (player text + regex); no LLM-touched field reads.
_STRONG_INTENT_RX = re.compile(
    r"\b(?:attack|threaten|demand|refuse|accept|commit|leave|enter|"
    r"attempt|charge|cast|strike|defy|swear|insist|interrupt)\b",
    re.IGNORECASE,
)


def compute_stakes_tier(
    scene_state: Optional[dict],
    active_turn: Optional[dict] = None,
    active_quests: Optional[list] = None,
    combatants: Optional[list] = None,
) -> tuple[str, dict]:
    """Compute stakes-tier signal for narrative texture scaling (Ship A §5).

    Pure function. Reads no DB; caller supplies all inputs. No side effects.
    Ninth Doctrine §59 instance — sibling to compute_persistence_directive
    et al.

    Returns (stakes_tier, signals_dict):
      - stakes_tier ∈ {'low', 'medium', 'high'}
      - signals_dict carries per-input contributions for log telemetry
    """
    signals = {
        'mode': 'unknown',
        'tension': 0,
        'urgent_clocks': 0,
        'strong_intent': 0,
        'combat_active': 0,
        'score': 0,
    }

    if not isinstance(scene_state, dict):
        signals['mode'] = 'none'
        return 'low', signals

    mode = (scene_state.get('mode') or 'exploration').strip().lower()
    signals['mode'] = mode

    score = 0
    if mode == 'combat':
        score += 2
    elif mode == 'social':
        score += 1
    elif mode == 'downtime':
        score -= 1

    tension = scene_state.get('tension_int') or 0
    try:
        tension = int(tension)
    except (TypeError, ValueError):
        tension = 0
    signals['tension'] = tension
    if tension >= 70:
        score += 2
    elif tension >= 40:
        score += 1

    clocks = scene_state.get('progress_clocks') or []
    urgent = 0
    if isinstance(clocks, list):
        for c in clocks:
            if isinstance(c, dict) and int(c.get('urgency_int') or 0) >= 7:
                urgent = 1
                break
    signals['urgent_clocks'] = urgent
    if urgent:
        score += 1

    last_action = scene_state.get('last_player_action') or ''
    strong_intent = 1 if _STRONG_INTENT_RX.search(last_action) else 0
    signals['strong_intent'] = strong_intent
    if strong_intent:
        score += 1

    combat_active = 0
    if mode == 'combat' and isinstance(combatants, list):
        for c in combatants:
            if isinstance(c, dict) and int(c.get('alive') or 0) == 1:
                # Treat any alive combatant as "active threat" surface; v1.x
                # may distinguish enemy-alive vs PC-alive.
                combat_active = 1
                break
    signals['combat_active'] = combat_active
    if combat_active:
        score += 1

    signals['score'] = score

    if score >= 4:
        tier = 'high'
    elif score >= 2:
        tier = 'medium'
    else:
        tier = 'low'

    return tier, signals


def stakes_tier_log_summary(signals: dict, tier: str) -> str:
    """Compact log line per Doctrine §59 / Ship A spec §5.5. Always-fire."""
    s = signals or {}
    return (
        f"stakes_tier: tier={tier} "
        f"mode={s.get('mode', 'unknown')} "
        f"tension={s.get('tension', 0)} "
        f"urgent_clocks={s.get('urgent_clocks', 0)} "
        f"strong_intent={s.get('strong_intent', 0)} "
        f"combat_active={s.get('combat_active', 0)} "
        f"score={s.get('score', 0)}"
    )


def compute_resolution_texture(
    dc: int,
    roll_total: int,
    nat: Optional[int],
    scene_state: Optional[dict],
    active_turn: Optional[dict] = None,
    active_quests: Optional[list] = None,
    combatants: Optional[list] = None,
) -> ResolutionTexture:
    """Assemble difficulty + margin + stakes tiers into a ResolutionTexture
    (Ship A §5.6). Pure. Caller supplies all inputs."""
    modifier = (roll_total - nat) if isinstance(nat, int) else 0
    effective_dc = dc - modifier
    difficulty_band = _bucket_difficulty(effective_dc)
    margin = roll_total - dc
    margin_tier = _bucket_margin(margin)
    stakes_tier, stakes_signals = compute_stakes_tier(
        scene_state, active_turn, active_quests, combatants
    )
    return ResolutionTexture(
        effective_dc=effective_dc,
        modifier=modifier,
        difficulty_band=difficulty_band,
        margin=margin,
        margin_tier=margin_tier,
        stakes_tier=stakes_tier,
        stakes_signals=stakes_signals,
    )


@dataclass(frozen=True)
class ResolutionResult:
    actor: str
    check_kind: str           # 'check' | 'save' (cast deferred §11.5)
    skill_or_save: str        # 'perception' | 'wisdom' | 'sleight of hand' | ...
    dc: int
    roll_total: int
    passed: bool              # engine-computed: roll_total >= dc
    rolled_at: float
    directive_id: int         # campaign_id in v1 (§5.2 — no per-row id yet)
    nat: Optional[int] = None  # natural die roll, when surfaced by Avrae
    crit: bool = False         # explicit crit flag from Avrae embed
    texture: Optional[ResolutionTexture] = None   # Ship A §4 — narrative scaling


_DC_PARSE_RX = re.compile(
    r"^(?P<skill>[a-zA-Z_][a-zA-Z_\s\-]*?)\s+(?P<dc>\d+)\s*$",
)


def parse_skill_and_dc(skill_raw: str) -> tuple[str, Optional[int]]:
    """Split a directive's captured skill text into (skill, dc).

    Locked edge cases (RESOLUTION_BINDING_SPEC.md §6.3):
      'perception 10'      → ('perception', 10)
      'perception'         → ('perception', None)
      'sleight of hand 12' → ('sleight of hand', 12)   (multi-word skill)
      'perception 100'     → ('perception', 100)       (high-DC allowed)
      'perception 0'       → ('perception', 0)         (theater check)
      'stealth adv'        → ('stealth adv', None)     (non-numeric trailing)
      'perception 10 adv'  → ('perception 10 adv', None)  (trailing word after DC)
      'perception -5'      → ('perception -5', None)   (\\d+ rejects negatives)

    Caller passes through `_directive_skill_is_clean` upstream to reject
    flags/comments before us; we only split out the trailing integer DC.
    """
    s = (skill_raw or '').strip()
    m = _DC_PARSE_RX.match(s)
    if m:
        return m.group('skill').strip(), int(m.group('dc'))
    return s, None


def resolve_directive(directive_row: Optional[dict],
                      avrae_event: Optional[dict],
                      scene_state: Optional[dict] = None,
                      active_turn: Optional[dict] = None,
                      active_quests: Optional[list] = None,
                      combatants: Optional[list] = None) -> Optional[ResolutionResult]:
    """Compute the resolution of a consumed pending roll directive.

    Pure function — reads no DB, no buffers. Caller (matcher in
    discord_dnd_bot.py) supplies all inputs. No side effects.

    Returns None when inputs are structurally incomplete (no DC, no
    roll_total, kind mismatch); caller falls through to telemetry-only
    behavior. Returns a populated ResolutionResult otherwise.

    Ship A (S36): when `scene_state` is supplied (any non-None value),
    texture is computed via `compute_resolution_texture` and embedded in
    the returned ResolutionResult.texture field. When scene_state is None,
    texture is None — backwards-compatible with Ship 1 callers.

    Cast directives return None (§11.5 — cast resolution requires
    target-side save adjudication, filed v1.x). RAW D&D 5e per §11.3:
    nat-20 / nat-1 do NOT auto-succeed/fail on skill checks. `passed` is
    strictly `roll_total >= dc`.
    """
    if not isinstance(directive_row, dict) or not isinstance(avrae_event, dict):
        return None

    kind = (avrae_event.get('kind') or '').lower()
    if kind not in ('check', 'save'):
        return None  # cast / attack / damage / rest skip

    roll_total = avrae_event.get('result')
    if roll_total is None or not isinstance(roll_total, int):
        return None  # malformed embed; matcher falls through to telemetry-only

    dc = directive_row.get('dc')
    if dc is None or not isinstance(dc, int):
        return None  # no-DC directive — see §11.2

    actor = (directive_row.get('actor_name') or '').strip()
    skill_or_save = (directive_row.get('check_type') or '').strip()
    if not actor or not skill_or_save:
        return None  # defensive — Phase 1 invariants guarantee both non-empty

    nat_raw = avrae_event.get('nat')
    nat_val = int(nat_raw) if isinstance(nat_raw, int) else None

    # Ship A — compute texture when scene_state supplied. Pre-instantiation
    # (frozen=True; no replace() patching).
    texture: Optional[ResolutionTexture] = None
    if scene_state is not None:
        texture = compute_resolution_texture(
            dc=dc,
            roll_total=roll_total,
            nat=nat_val,
            scene_state=scene_state,
            active_turn=active_turn,
            active_quests=active_quests,
            combatants=combatants,
        )

    return ResolutionResult(
        actor=actor,
        check_kind=kind,
        skill_or_save=skill_or_save,
        dc=dc,
        roll_total=roll_total,
        passed=roll_total >= dc,
        rolled_at=float(avrae_event.get('ts') or time.time()),
        directive_id=int(directive_row.get('campaign_id') or 0),
        nat=nat_val,
        crit=bool(avrae_event.get('crit') or False),
        texture=texture,
    )


def resolution_log_summary(result: Optional[ResolutionResult],
                            campaign_id: int,
                            reason: str = 'unresolvable') -> str:
    """Compact log line per Doctrine §59 / spec §4.5. Always-fire — fires
    for both successful resolutions (result non-None) and skipped cases
    (result None, with caller-supplied skip reason)."""
    if result is None:
        return (f"directive_resolution_skipped: campaign={campaign_id} "
                f"reason={reason}")
    outcome = 'PASSED' if result.passed else 'FAILED'
    return (
        f"directive_resolved: campaign={campaign_id} "
        f"actor={result.actor} "
        f"skill={result.skill_or_save} "
        f"check_kind={result.check_kind} "
        f"dc={result.dc} "
        f"roll_total={result.roll_total} "
        f"outcome={outcome} "
        f"nat={result.nat if result.nat is not None else 'none'} "
        f"crit={1 if result.crit else 0}"
    )


# Ship A §8.3 — locked difficulty-band guidance clauses
_DIFFICULTY_GUIDANCE = {
    'trivial': (
        "This was a trivial check. Narrate the outcome with confidence and "
        "zero friction; the actor's skill leaves no doubt."
    ),
    'easy': (
        "This was an easy check. Narrate efficient execution; minor "
        "competence on display."
    ),
    'medium': (
        "This was a medium check. Narrate appropriate effort; the outcome "
        "reflects steady skill, not chance."
    ),
    'hard': (
        "This was a hard check. Narrate visible effort or close-quarters "
        "tension; the success or failure feels earned."
    ),
    'very_hard': (
        "This was a very hard check. Narrate strain, focus, or "
        "near-impossibility; outcomes carry weight regardless of pass/fail."
    ),
    'nearly_impossible': (
        "This was a nearly-impossible check. Narrate the attempt as "
        "exceptional regardless of outcome; success is heroic, failure "
        "is honorable."
    ),
}

# Ship A §9.2 — locked margin-tier guidance clauses
_MARGIN_GUIDANCE = {
    'catastrophic_fail': (
        "Margin ≤ −10. Narrate a substantial failure — the gap between "
        "attempt and outcome is wide; render visible cost or consequence."
    ),
    'clear_fail': (
        "Margin −5 to −9. Narrate a clear failure; the actor knows they "
        "fell short but the gap was not catastrophic."
    ),
    'close_fail': (
        "Margin −1 to −4. Narrate a near-miss; one detail short of "
        "success, render the moment of falling just-shy."
    ),
    'razor_pass': (
        "Margin = 0 (exact tie). Narrate the razor-thin quality; one "
        "moment of doubt before barely-succeeding."
    ),
    'clean_pass': (
        "Margin +1 to +9. Narrate competent success; render control "
        "without flourish."
    ),
    'smashing_pass': (
        "Margin ≥ +10. Narrate exceptional success; render flair, an "
        "unintended bonus detail, or a confident extra beat."
    ),
}

# Ship A §5.2-derived stakes-tier guidance clauses
_STAKES_GUIDANCE = {
    'low': (
        "Low stakes — exploration or downtime context. Render outcome "
        "with appropriate weight; consequences are local and recoverable."
    ),
    'medium': (
        "Medium stakes — meaningful friction, real but not climactic. "
        "Render outcome with noticeable weight."
    ),
    'high': (
        "High stakes — active urgent clocks, combat pressure, or "
        "committed-action moment. Narration must feel weighty; "
        "consequences land harder."
    ),
}


def _render_crit_clause(result: 'ResolutionResult') -> str:
    """Ship A §10.2 — render crit-tier constraint clause when nat==20 or
    nat==1. Returns empty string when neither fires.

    Texture is locked verbatim for the four cells (nat 20 + PASSED, nat 20
    + FAILED, nat 1 + PASSED, nat 1 + FAILED) plus scene-mode tonal
    modulation for nat 1 + FAILED per §10.2."""
    nat = result.nat
    if nat not in (20, 1):
        return ''

    passed = result.passed
    if nat == 20 and passed:
        return (
            "Critical signal: NAT 20. The roll was spectacular and the "
            "outcome cleared the DC. Narrate a memorable success — extra "
            "detail, a lore drop, an NPC reaction, an unintended bonus, "
            "or future-scene advantage. Render the spectacular quality "
            "of the moment."
        )
    if nat == 20 and not passed:
        return (
            "Critical signal: NAT 20 with FAILED outcome. The roll was "
            "spectacular but the goal was beyond reach. Narrate the "
            "near-miss as memorable — the actor did everything right, "
            "the situation was just impossible. Lean into the tension "
            "between the spectacular roll and the still-thwarted attempt; "
            "render the actor's competence visible even in failure."
        )
    if nat == 1 and passed:
        return (
            "Critical signal: NAT 1 with PASSED outcome. The natural roll "
            "was catastrophic but the actor's skill carried them through. "
            "Narrate the graceless quality of the success — they got "
            "there, but the path was awkward, fumbled, or pure-luck. "
            "Render the success as honest but ugly; the actor noticed "
            "how close it was to going wrong."
        )
    # nat == 1 and not passed
    # Scene-mode tonal modulation per §10.2:
    # downtime/travel → comic; combat/social → grim; exploration → either
    mode = ''
    try:
        mode = (result.texture.stakes_signals.get('mode') or '')
    except Exception:
        mode = ''
    if mode in ('combat', 'social'):
        tone = 'grim — comedy breaks immersion here'
    elif mode in ('downtime', 'travel'):
        tone = 'comic — low-stakes contexts where bad-luck humor lands'
    else:
        tone = (
            'either funny or grim — LLM judges based on scene tone '
            '(investigation in a haunted ruin should stay grim; '
            'a bantering perception check at a fair can be comic)'
        )
    return (
        "Critical signal: NAT 1. The roll was catastrophic and the "
        "outcome failed. Narrate a memorable failure. Scene mode dictates "
        f"the tone: {tone}. Render bad luck visibly."
    )


def render_resolution_block(result: Optional[ResolutionResult]) -> str:
    """Render ResolutionResult as the inner text of the top-of-prompt
    AUTHORITATIVE ROLL RESOLUTION block (spec §7.3 + Ship A §10.3).
    Returns empty when result is None — caller's section-assembly
    truthiness check handles suppression.

    When result.texture is non-None (Ship A path), the block includes
    difficulty + margin + stakes + crit-tier lines. When texture is None
    (Ship 1 v1 path), block reads as Ship 1 v1 (pass/fail only)."""
    if result is None:
        return ''
    skill_pretty = (result.skill_or_save or '').replace('_', ' ').title()
    outcome = 'PASSED' if result.passed else 'FAILED'
    outcome_word = 'success' if result.passed else 'failure'
    opposite_word = 'failure' if result.passed else 'success'
    negation = '' if result.passed else 'NOT '

    head = (
        f"{result.actor} attempted a {skill_pretty} {result.check_kind} "
        f"(DC {result.dc}).\n"
        f"Roll total: {result.roll_total}.\n"
        f"Outcome: {outcome}.\n"
    )

    # Texture lines + crit signal — emit when texture present (Ship A path).
    texture_block = ''
    if result.texture is not None:
        t = result.texture
        mod_sign = '+' if t.modifier >= 0 else ''
        signed_margin = f"+{t.margin}" if t.margin > 0 else str(t.margin)
        texture_lines = [
            f"Difficulty: {t.difficulty_band} "
            f"(effective DC {t.effective_dc} after actor modifier "
            f"{mod_sign}{t.modifier}).",
            f"Margin: {signed_margin} ({t.margin_tier}).",
            f"Stakes: {t.stakes_tier}.",
        ]
        crit_signal_line = ''
        if result.nat == 20:
            crit_signal_line = 'Critical signal: NAT 20.'
        elif result.nat == 1:
            crit_signal_line = 'Critical signal: NAT 1.'
        if crit_signal_line:
            texture_lines.append(crit_signal_line)
        texture_block = '\n' + '\n'.join(texture_lines) + '\n'

    must_narrate = (
        f"\nYou MUST narrate this as a {outcome_word}. "
        f"{result.actor} does {negation}achieve the intended outcome.\n"
    )

    # Per-tier guidance — only when texture present.
    guidance_block = ''
    if result.texture is not None:
        t = result.texture
        guidance_lines = [
            "The texture of the narration must reflect:",
            f"  - Difficulty: {_DIFFICULTY_GUIDANCE.get(t.difficulty_band, '')}",
            f"  - Margin: {_MARGIN_GUIDANCE.get(t.margin_tier, '')}",
            f"  - Stakes: {_STAKES_GUIDANCE.get(t.stakes_tier, '')}",
        ]
        crit_clause = _render_crit_clause(result)
        if crit_clause:
            guidance_lines.append(f"  - {crit_clause}")
        guidance_block = '\n'.join(guidance_lines) + '\n'

    tail = (
        f"Do NOT narrate {opposite_word}. "
        f"Do NOT invent an alternative interpretation."
    )

    return head + texture_block + must_narrate + guidance_block + tail


def render_resolution_hardstop_echo(result: Optional[ResolutionResult]) -> str:
    """Render the single-line bottom-of-prompt repeat (spec §7.2). The
    §48 concrete-in-prompt pattern — repeat the bare verdict at moment of
    generation. Empty when result is None."""
    if result is None:
        return ''
    return f"Outcome: {'PASSED' if result.passed else 'FAILED'}."


# ─────────────────────────────────────────────────────────
# Ship S43 (dumb combat) — Combat narration trigger detection + prompt build
# ─────────────────────────────────────────────────────────
# **North-star principle (filed doctrine candidate, anchors post-S43 verify
# clean):** combat narration is atmospheric continuity, not adjudication.
# The cliff-edge — the moment narration starts inferring tactical outcomes,
# hidden intent, optimal targeting, or consequences beyond what listener +
# engine established, the ship has silently graduated from "combat glue"
# into "combat adjudication" and the renderer-not-ruler discipline is
# broken. Every prompt invariant below treats this as the rejection
# criterion.
#
# v1 trigger set (locked per S43 prompt §1):
#   ROUND_START                — Avrae round transition (round_num increased)
#   BLOODIED_THRESHOLD_CROSSED — combatant HP crossed 50% downward
#   COMBATANT_DOWNED           — combatant HP reached 0
#   DEATH_SAVE_EVENT_START     — DEFERRED v1 (S42 fixture blocker; stubbed)
#
# Excluded from v1: per-turn narration, ordinary attacks/misses,
# reinforcements, environmental escalation, pacing pressure (no deterministic
# detection surface). These DO NOT fire combat narration regardless of state.


def _hp_state(hp_current, hp_max) -> str:
    """Categorical HP label per Ship S43 prompt §2 — NEVER exact numbers.
    Granularity: healthy / bloodied (≤50% hp_max) / downed (hp ≤ 0) /
    unknown (hp_max is None — pre-hydration combatant)."""
    if hp_max is None or hp_max <= 0:
        return 'unknown'
    if hp_current is None:
        return 'unknown'
    if hp_current <= 0:
        return 'downed'
    if hp_current <= hp_max / 2:
        return 'bloodied'
    return 'healthy'


def compute_combat_state_transitions(prior_combatants: list,
                                     new_combatants: list) -> list:
    """Diff prior + new combatant snapshots; return list of state-transition
    events per Ship S43 §1 trigger set.

    Inputs: each combatants list is a sequence of dicts with at least
    {name, hp_current, hp_max, alive}. Order doesn't matter (matched by name).

    Returns a list of trigger events, each shaped:
      {
        'kind': 'BLOODIED_THRESHOLD_CROSSED' | 'COMBATANT_DOWNED',
        'name': str,
        'prior_state': 'healthy' | 'bloodied' | 'downed' | 'unknown',
        'new_state':   'healthy' | 'bloodied' | 'downed' | 'unknown',
      }

    Detection rules:
      - BLOODIED: prior_state == 'healthy' AND new_state == 'bloodied'.
        Downward 50%-crossing only; healing back from bloodied to healthy
        does NOT fire. (Avoids spam on per-turn healing waves.)
      - DOWNED: prior_state != 'downed' AND new_state == 'downed'.
        Edge fires once per descent; staying at 0 HP does not re-fire.

    ROUND_START is detected at the caller layer (init_event 'turn' with
    round_num increase), not here — this function compares HP states only.

    Pure: no DB, no side effects.
    """
    if not isinstance(prior_combatants, list) or not isinstance(new_combatants, list):
        return []
    prior_by_name = {}
    for c in prior_combatants:
        if not isinstance(c, dict):
            continue
        n = (c.get('name') or '').strip()
        if n:
            prior_by_name[n] = c
    transitions = []
    for c in new_combatants:
        if not isinstance(c, dict):
            continue
        name = (c.get('name') or '').strip()
        if not name:
            continue
        prior = prior_by_name.get(name)
        new_state = _hp_state(c.get('hp_current'), c.get('hp_max'))
        if prior is None:
            # New combatant; only fire if they entered already-downed
            # (unusual but possible — pre-spent corpse added to init).
            if new_state == 'downed':
                transitions.append({
                    'kind': 'COMBATANT_DOWNED',
                    'name': name,
                    'prior_state': 'unknown',
                    'new_state': 'downed',
                })
            continue
        prior_state = _hp_state(prior.get('hp_current'), prior.get('hp_max'))
        # DOWNED edge: descent into HP ≤ 0
        if prior_state != 'downed' and new_state == 'downed':
            transitions.append({
                'kind': 'COMBATANT_DOWNED',
                'name': name,
                'prior_state': prior_state,
                'new_state': new_state,
            })
            continue  # don't also fire bloodied if same transition
        # BLOODIED edge: downward 50%-crossing (healthy → bloodied)
        if prior_state == 'healthy' and new_state == 'bloodied':
            transitions.append({
                'kind': 'BLOODIED_THRESHOLD_CROSSED',
                'name': name,
                'prior_state': prior_state,
                'new_state': new_state,
            })
    return transitions


# Combat narration prompt invariants — §3 MUST / MUST-NOT clauses + S43
# verify-pass-surfaced additions. Locked at S43 spec; modifications require
# operator re-approval because these are the prompt-side enforcement of
# the atmospheric-vs-adjudication doctrine line.
#
# S43 verify-pass additions (May 11, 2026, post-Scenario-B drift):
#   - MUST NOT: introduce combatants not in the roster (phantom-NPC fix —
#     the LLM was pulling Eldrin/Borin/Lira from `recent_npcs` block and
#     narrating their combat actions despite them not being in init).
#   - MUST NOT: attribute specific actions to PCs the player hasn't
#     narrated (round-start action-attribution fix — the LLM was narrating
#     "Donovan darts forward" at round-top despite no player input).
_COMBAT_NARRATION_INVARIANTS = (
    "COMBAT NARRATION INVARIANTS:\n"
    "- MUST: summarize what listener confirmed happened this round.\n"
    "- MUST: stay inside atmospheric continuity — describe the scene as it stands.\n"
    "- MUST NOT: establish new mechanical state. You cannot deal damage, "
    "kill combatants, apply conditions, or trigger reactions that the "
    "listener did not confirm.\n"
    "- MUST NOT: narrate speculative outcomes. If a combatant is bloodied, "
    "you may describe them faltering; you may NOT describe them about to fall.\n"
    "- MUST NOT: declare a kill, knockout, or unconsciousness unless the "
    "listener confirms it via HP→0 or death-save outcome.\n"
    "- MUST NOT: invent damage numbers, attack outcomes, or condition "
    "applications. Avrae is the source of mechanical truth.\n"
    "- MUST NOT: infer enemy morale, tactical intent, or \"what they're "
    "about to do.\" You are the scene's narrator, not its tactician.\n"
    "- MUST NOT: describe action that didn't happen this round.\n"
    "- MUST NOT: introduce or narrate actions for any combatant NOT in the "
    "init roster above. If an NPC name appears in your scene memory but is "
    "NOT in the roster, they are NOT in this fight — keep them out of the "
    "narration entirely. The roster is the authoritative actor list.\n"
    "- MUST NOT: attribute specific actions (attacking, moving, drawing "
    "weapons, etc.) to any PC unless the player has narrated that action "
    "OR the listener has confirmed a mechanical event. At round-start, "
    "describe environmental atmosphere (lighting, sound, tension) rather "
    "than specific PC actions."
)


def compute_combat_narration_directive(trigger_event: dict,
                                       combat_state: dict,
                                       scene_state) -> tuple:
    """Build the combat-narration prompt context for one trigger event.

    Tenth Doctrine §59 instance — pure function over (trigger, combat_state,
    scene_state), no DB writes, no LLM calls. Returns
    (combined_action: str, transition_context: str).

    combined_action is the synthesized player_action string passed to
    `_dm_respond_and_post`. Sentinel-shaped (`[Combat narration: ...]`) so
    `classify_action_intent` recognizes it as META intent and doesn't
    cascade into roll classification (Ship A §5.2 precedent).

    transition_context is the directive block injected into the prompt —
    contains categorical HP labels (NEVER exact numbers per spec §2), the
    locked §3 MUST/MUST-NOT invariants, and trigger-specific framing.

    trigger_event shape:
      {'kind': 'ROUND_START', 'round': int}
      {'kind': 'BLOODIED_THRESHOLD_CROSSED', 'name': str}
      {'kind': 'COMBATANT_DOWNED', 'name': str}
      {'kind': 'COMBAT_END'}  # Ship S45-F — auto-closeout on !init end

    combat_state shape (from get_combatants):
      {'combatants': [{name, init, hp_current, hp_max, conditions, alive}, ...]}

    Returns ('', '') when scene_state isn't combat mode (gate per §1).
    Caller must pass scene_state with mode='combat' for COMBAT_END dispatch
    even though the mechanical mode flag may have already flipped — the
    dispatch represents the closing moment OF combat, not post-combat.
    """
    if not isinstance(trigger_event, dict):
        return ('', '')
    kind = trigger_event.get('kind')
    if kind not in ('ROUND_START', 'BLOODIED_THRESHOLD_CROSSED',
                    'COMBATANT_DOWNED', 'COMBAT_END'):
        return ('', '')
    # Mode gate — Ship S43 §1: triggers only fire when mode='combat'.
    mode = (scene_state or {}).get('mode') if isinstance(scene_state, dict) else None
    if (mode or '').lower() != 'combat':
        return ('', '')

    combatants = (combat_state or {}).get('combatants') or []

    # Build categorical roster (init order preserved; NEVER exact HP).
    roster_lines = []
    for c in combatants:
        if not isinstance(c, dict):
            continue
        name = (c.get('name') or '').strip()
        if not name:
            continue
        state = _hp_state(c.get('hp_current'), c.get('hp_max'))
        if not c.get('alive', 1):
            state = 'dead'
        init_v = c.get('init', '?')
        conds = (c.get('conditions') or '').strip()
        line = f"  - {name} ({state}, init {init_v})"
        if conds:
            line += f" [conditions: {conds}]"
        roster_lines.append(line)
    roster_block = "\n".join(roster_lines) if roster_lines else "  (no combatants snapshot)"

    # Trigger-specific framing line (sentinel + brief context for the LLM).
    if kind == 'ROUND_START':
        round_num = trigger_event.get('round', '?')
        action = f"[Combat narration: round {round_num} starts.]"
        framing = (
            f"TRIGGER: round_start (round {round_num})\n"
            "Render one short atmospheric beat marking the round-top. "
            "Focus on environment and tension — lighting, sound, the room's "
            "mood, the pause between exchanges. Do NOT narrate specific "
            "combatant actions (no 'X darts forward', no 'Y raises their "
            "weapon'). Combatants are present per the roster; you describe "
            "the scene around them, not what they do. Do NOT preview "
            "next-turn actions. Then hand back to the next acting combatant "
            "per init order."
        )
    elif kind == 'BLOODIED_THRESHOLD_CROSSED':
        name = trigger_event.get('name', '?')
        action = f"[Combat narration: {name} is bloodied.]"
        framing = (
            f"TRIGGER: bloodied_threshold_crossed (combatant={name})\n"
            f"Render one short atmospheric beat — {name} is now bloodied. "
            "Describe them faltering / staggering / showing damage. Do NOT "
            "describe them as about-to-fall, dying, or out of the fight — "
            "they're hurt but standing. Avrae will tell us when they go down."
        )
    elif kind == 'COMBATANT_DOWNED':
        name = trigger_event.get('name', '?')
        action = f"[Combat narration: {name} dropped.]"
        framing = (
            f"TRIGGER: combatant_downed (combatant={name})\n"
            f"Render one short atmospheric beat — {name} drops to 0 HP "
            "this round. Listener confirms the descent. Describe the fall "
            "concretely. Do NOT declare death unless the listener confirms "
            "death-save failure or instant-death threshold; 'unconscious / "
            "down / out of the fight' is the safe framing."
        )
    else:  # COMBAT_END (Ship S45-F — auto-closeout on !init end)
        action = "[Combat narration: combat resolves.]"
        framing = (
            "TRIGGER: combat_end\n"
            "Combat has ended this moment. Render one short atmospheric "
            "beat marking the close — 2-3 sentences. Describe the falling "
            "tension, the cessation of motion, the room settling. "
            "Combatants who were standing at the close remain standing; "
            "combatants marked downed/dead in the roster are still down. "
            "Do NOT narrate post-combat decisions, dialogue, or next moves "
            "— that's for the player to declare next turn. Do NOT preview "
            "the next exploration beat or describe what the party does now. "
            "Do NOT introduce any combatant or NPC who is not on the closing "
            "roster above — no 'a thug emerges from the shadows', no "
            "companions appearing to congratulate the party. Close THIS "
            "moment and stop."
        )

    transition_context = (
        f"=== COMBAT NARRATION (atmospheric, not adjudicative) ===\n"
        f"{framing}\n\n"
        f"Combatant roster (categorical HP labels — NEVER state exact numbers):\n"
        f"{roster_block}\n\n"
        f"{_COMBAT_NARRATION_INVARIANTS}"
    )
    return (action, transition_context)


def combat_narration_log_summary(trigger_event: dict, fired: bool,
                                  reason: str = '') -> str:
    """Compact log line per Doctrine §59 / Ship S43 spec §6. Always-fire
    when a trigger is evaluated, even if it doesn't dispatch."""
    kind = (trigger_event or {}).get('kind', 'unknown')
    name = (trigger_event or {}).get('name', '')
    parts = [
        f"combat_narration_fired: kind={kind} fired={1 if fired else 0}",
    ]
    if name:
        parts.append(f"name='{name}'")
    if reason:
        parts.append(f"reason={reason}")
    return " ".join(parts)
