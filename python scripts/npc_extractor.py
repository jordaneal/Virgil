"""NPC extractor — Phase 12A.2.

Advisory parser. Reads DM narration, returns a list of candidate NPC
records the engine MAY persist. Suggestion-only — never writes.

Public API:
    parse_npcs(narration: str) -> list[dict]

Each output dict has the canonical four-key shape:
    {
      "name":                 <1-3 capitalized words, validated>,
      "role":                 <occupation, "" if unknown>,
      "location_hint":        <place name, "" if unknown>,
      "description_fragment": <short physical/demeanor detail, "" if none>,
    }

Hard invariants (PHASE_12_SPEC §4, §7, §9.1):
- Narration-only input. No player input, no scene state, no character context.
- Strict whitelist on names: must match _NAME_RE AND survive both stoplists.
- Identity normalization is DETERMINISTIC. Honorific prefixes (Sir, Lord,
  Captain, Father, etc.) are stripped from canonical names regardless of
  what the LLM emits. "Sir Aldric" and "Aldric" both become "Aldric".
- No engine writes. Reads strings, returns dicts.
- Never raises. Returns [] on any failure.

Wiki-entry test (the design constraint):
  If a candidate wouldn't survive being written into a persistent campaign
  wiki, it is NOT an NPC. That excludes: pronouns, archetypes, generic
  roles, factions, places, deities. Better to miss a real NPC than admit
  a fake one.

Why honorifics are stripped (Session 12 review):
  Under strict literal matching (§9.1 v1), preserving titles fragments
  identity — narration alternates between "Sir Aldric" / "Aldric" / "the
  knight", and three forms means three rows for one person. The bare
  proper noun is the stable semantic core. Titles become role metadata,
  not identity keys. Manual `aliases` handles exceptional ambiguity.
"""

import json
import re
import time

from cloud_router import route
from dnd_engine import log, canonicalize_name, names_overlap

# ─────────────────────────────────────────────────────────
# Validator
# ─────────────────────────────────────────────────────────

# Strict format per PHASE_12_SPEC §7: 1-3 capitalized words.
# Each word: uppercase letter then one+ word chars / apostrophes / hyphens.
_NAME_RE = re.compile(r"^[A-Z][\w'\-]+(\s+[A-Z][\w'\-]+){0,2}$")

# First-word rejection: articles, pronouns, demonstratives, numerics. If the
# parser emits "The Guard", "He Frowns", "A Stranger" — drop on first word.
_NAME_FIRST_WORD_STOPLIST = frozenset({
    # Articles, determiners
    "The", "A", "An", "Some", "Any", "All", "Every", "Each", "No", "Another",
    # Pronouns + possessives
    "He", "She", "They", "It", "We", "You", "I", "Me", "Us", "Them",
    "His", "Her", "Their", "Our", "Your", "My", "Its",
    # Demonstratives
    "This", "That", "These", "Those",
    # Numerics
    "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
    "Ten", "Many", "Few", "Several",
})

# Honorific tokens that get DETERMINISTICALLY STRIPPED from the start of
# canonicalized names. Identity normalization, not generation style.
#
# Doctrine (PHASE_12_SPEC §9.1 + Session 12 review):
#   Under strict literal matching, "Sir Aldric" and "Aldric" produce two
#   separate rows for the same person. Narration naturally alternates
#   between forms ("Sir Aldric draws his blade" / "Aldric is wounded"),
#   so the only stable identity is the title-stripped name. Honorifics
#   are descriptive metadata, not identity-bearing.
#
# Stripping is whole-word and iterative ("Sir Doctor Bardus" → "Bardus")
# but NEVER consumes the last token — "Sir" alone stays "Sir" and is then
# caught by the whole-name stoplist below. "Lordran" stays "Lordran"
# because "Lord" must be a separate token to be stripped.
_HONORIFIC_PREFIXES = frozenset({
    # Nobility / chivalric
    "Sir", "Lord", "Lady", "Madam", "Madame", "Master", "Mistress", "Dame",
    "Knight", "Squire",
    "King", "Queen", "Prince", "Princess", "Duke", "Duchess",
    "Baron", "Baroness", "Count", "Countess", "Earl", "Marquis",
    # Military rank
    "Captain", "Sergeant", "Lieutenant", "General", "Commander", "Colonel",
    "Major", "Corporal", "Admiral",
    # Religious / academic
    "Father", "Mother", "Brother", "Sister", "Elder", "Abbot", "Abbess",
    "Mr", "Mrs", "Ms", "Dr", "Doctor", "Professor", "Magister",
})

# Whole-name rejection: tokens that LOOK proper but aren't. Honorifics
# alone (no following name — caught here AFTER strip leaves them alone),
# generic role-as-name, species-as-name, archetypes. Compared against the
# whole canonicalized + stripped name. "Sir" alone fails here; "Sir Aldric"
# becomes "Aldric" via _strip_honorific and passes.
_NAME_WHOLE_STOPLIST = _HONORIFIC_PREFIXES | frozenset({
    # Generic role-as-name
    "Guard", "Soldier", "Bandit", "Brigand", "Mercenary", "Outlaw",
    "Warrior", "Mage", "Wizard", "Sorcerer", "Witch", "Warlock",
    "Priest", "Priestess", "Monk", "Cleric", "Druid", "Ranger", "Rogue",
    "Thief", "Bard", "Paladin", "Fighter", "Barbarian", "Knightess",
    "Innkeeper", "Barkeep", "Bartender", "Blacksmith", "Smith",
    "Merchant", "Trader", "Farmer", "Hunter", "Cook", "Sailor",
    "Stranger", "Figure", "Man", "Woman", "Person", "Child", "Children",
    "Boy", "Girl", "Youth", "Elders",
    "Traveler", "Wanderer", "Pilgrim", "Adventurer", "Stableboy", "Stablehand",
    # Race/species alone
    "Elf", "Dwarf", "Human", "Halfling", "Gnome", "Orc", "Goblin",
    "Hobgoblin", "Kobold", "Tiefling", "Dragonborn", "Half-Elf", "Half-Orc",
    "Drow", "Elves", "Dwarves", "Humans", "Goblins", "Orcs",
    # Supernatural archetypes
    "Dragon", "Demon", "Devil", "Angel", "Spirit", "Ghost", "Wraith",
    "Skeleton", "Zombie", "Vampire", "Lich", "Wight", "Shade",
    # Player + party (own systems)
    "Party",
})

# Per-field length caps (chars after strip). Spec §7: description_fragment
# capped at 100. Rest are conservative.
_FIELD_LEN_CAPS = {
    "name":                 60,
    "role":                 60,
    "location_hint":        80,
    "description_fragment": 100,
}

# Shell metacharacters and control chars. Refused anywhere in any field.
_BAD_CHARS = re.compile(r"[`;|&><$\\\n\r]")

# Canonical output shape. Always emit these four keys.
_NPC_KEYS = ("name", "role", "location_hint", "description_fragment")


def _strip_honorific(name):
    """Remove leading honorific tokens (whole-word, case-sensitive).
    Iterative — handles stacked prefixes like 'Sir Doctor Bardus' → 'Bardus'.

    Hard rules:
      - NEVER strips the last remaining token. 'Sir' alone stays 'Sir' and
        is then caught by _NAME_WHOLE_STOPLIST.
      - Only strips whole-word matches. 'Lordran' stays 'Lordran' because
        the prefix 'Lord' would have to be a separate whitespace-separated
        token to be stripped.
      - Operates on the canonicalized name (post-canonicalize_name), so
        whitespace and quote variations are already normalized.
    """
    if not name:
        return name
    parts = name.split()
    while len(parts) > 1 and parts[0] in _HONORIFIC_PREFIXES:
        parts = parts[1:]
    return ' '.join(parts)


def _normalize_npc(npc):
    """Coerce an LLM-emitted dict into the canonical 4-key shape.
    Strips whitespace, normalizes quotes via canonicalize_name on `name`,
    deterministically strips leading honorific tokens for stable identity,
    coerces non-string values to ''. Returns dict or None on bad shape.
    """
    if not isinstance(npc, dict):
        return None

    raw_name = npc.get("name", "")
    if not isinstance(raw_name, str):
        raw_name = ""
    name = canonicalize_name(raw_name)
    name = _strip_honorific(name)

    def _clean(field):
        v = npc.get(field, "")
        if not isinstance(v, str):
            return ""
        return v.strip()

    return {
        "name":                 name,
        "role":                 _clean("role"),
        "location_hint":        _clean("location_hint"),
        "description_fragment": _clean("description_fragment"),
    }


def _validate_npc(npc, pc_names=None):
    """Return (valid: bool, drop_reason: str | None).

    drop_reason is one of:
      bad_shape         — not a dict, or no name
      bad_name_format   — fails _NAME_RE
      name_in_stoplist  — first word or whole name on a stoplist
      length_exceeded   — any field over its cap
      bad_chars         — shell metas or control chars in any field
      pc_match          — name overlaps a bound PC (PCs are not NPCs)

    pc_names: optional list of bound-PC canonical names for this campaign.
    Any candidate whose name shares a token-prefix relationship with a PC
    name (either direction) is dropped.
    """
    if not isinstance(npc, dict):
        return False, "bad_shape"

    name = npc.get("name", "")
    if not name or not isinstance(name, str):
        return False, "bad_shape"

    if not _NAME_RE.match(name):
        return False, "bad_name_format"

    first_word = name.split()[0]
    if first_word in _NAME_FIRST_WORD_STOPLIST:
        return False, "name_in_stoplist"
    if name in _NAME_WHOLE_STOPLIST:
        return False, "name_in_stoplist"

    if pc_names:
        for pc_name in pc_names:
            if names_overlap(name, pc_name):
                return False, "pc_match"

    for field, cap in _FIELD_LEN_CAPS.items():
        v = npc.get(field, "")
        if not isinstance(v, str):
            return False, "bad_shape"
        if len(v) > cap:
            return False, "length_exceeded"
        if v and _BAD_CHARS.search(v):
            return False, "bad_chars"

    return True, None


# ─────────────────────────────────────────────────────────
# LLM call
# ─────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You read fantasy narration from a Dungeons & Dragons game and extract
NAMED NPCs (non-player characters) — specific people the world should remember.

Output ONLY a JSON array of objects. No prose. No markdown. No keys outside
the schema. Empty array [] if no named NPC appears.

Each object has EXACTLY these four keys (use empty string for unknown fields):
  "name":                  proper-noun name, 1-3 capitalized words
  "role":                  occupation or title (e.g. "blacksmith", "innkeeper")
  "location_hint":         place name where they appear in this narration
  "description_fragment":  short physical or demeanor detail, max ~80 chars

THE WIKI-ENTRY TEST (the only rule that matters):
  If you wouldn't write this person into a persistent campaign wiki — OMIT them.

What survives the wiki test (KEEP):
  - Proper names: "Garrick", "Mira", "Cassius", "Aldric"
  - Names appearing with honorifics: "Sir Aldric", "Captain Smith". Honorific
    prefixes (Sir, Lord, Captain, Father, Doctor, etc.) are stripped from
    canonical identity automatically — emit them attached or not, whichever
    is natural.
  - Names introduced via apposition: "Tobin, an old sailor" → name=Tobin, role=sailor

What fails the wiki test (OMIT):
  - Generic roles without a proper name: "the blacksmith", "a guard", "the innkeeper"
  - Pronouns referring to unnamed actors: "he glances away", "she nods"
  - Archetypes and mysterious figures: "a hooded figure", "an old man" (no name)
  - Honorifics with no name attached: "Sir nodded", "the Lord shrugged"
  - Crowds and groups: "the bandits", "a band of mercenaries"

What is NOT an NPC for THIS extractor:
  - Factions / organizations / cults: "The Crimson Hand", "the Order of the Sun"
  - Places, towns, regions, taverns: "Redhaven", "The Rusty Anchor"
  - Deities, spirits, abstract entities, monsters-as-archetype
  - The player's own character or party companions

Output rules:
  - "name": the proper noun. If a title precedes it, you may include the title
    or just emit the bare name — both are normalized to the same identity.
  - "role": occupation only. Not a descriptor. "blacksmith" yes; "scarred" no.
    Honorific titles (knight, captain, priest) are valid roles.
  - "description_fragment": a short physical or demeanor cue. Max ~80 chars.
  - When in doubt — OMIT. Better to miss a real NPC than fabricate one.

Example: "Garrick steps out of the shadows."
Output: [{"name": "Garrick", "role": "", "location_hint": "", "description_fragment": ""}]

Example: "Garrick the blacksmith pounds the anvil, sparks flying around him."
Output: [{"name": "Garrick", "role": "blacksmith", "location_hint": "", "description_fragment": "sparks flying from his anvil"}]

Example: "In Redhaven, Mira the innkeeper pours you a drink."
Output: [{"name": "Mira", "role": "innkeeper", "location_hint": "Redhaven", "description_fragment": ""}]

Example: "Sir Aldric draws his blade with a flourish."
Output: [{"name": "Aldric", "role": "knight", "location_hint": "", "description_fragment": ""}]

Example: "Aldric and Bardus argue near the fire while Cara watches."
Output: [{"name": "Aldric", "role": "", "location_hint": "", "description_fragment": ""}, {"name": "Bardus", "role": "", "location_hint": "", "description_fragment": ""}, {"name": "Cara", "role": "", "location_hint": "", "description_fragment": "watching from nearby"}]

Example: "A guard shouts at you to halt."
Output: []

Example: "He glances at you, then turns away."
Output: []

Example: "The Crimson Hand has been busy in the south."
Output: []

Example: "Mira tends the bar while a hooded figure watches from the corner."
Output: [{"name": "Mira", "role": "", "location_hint": "", "description_fragment": ""}]"""


def _extract_raw_candidates(text):
    """Pull a JSON array out of model output. Returns list | None.

    Handles markdown fences and prose wrappers. Returns None if no parseable
    array is found, or if the parsed value isn't a list.
    """
    body = (text or "").strip()
    if body.startswith("```"):
        body = re.sub(r"^```(?:json)?\s*", "", body)
        body = re.sub(r"\s*```$", "", body)
    m = re.search(r"\[.*\]", body, re.DOTALL)
    if not m:
        return None
    try:
        parsed = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, list):
        return None
    return parsed


def parse_npcs(narration, pc_names=None):
    """Read DM narration, return list of candidate NPC dicts.

    Each dict has exactly four keys: name, role, location_hint,
    description_fragment. All values are strings. `name` is canonicalized
    and validated; the other three may be empty strings.

    pc_names: optional list of bound-PC canonical names for the campaign.
    Any candidate whose name shares a token-prefix relationship with a PC
    name is dropped with reason='pc_match'. Caller should pass
    engine.get_bound_character_names(campaign_id).

    Never raises. Returns [] on any failure (empty input, route exception,
    parse failure, all candidates invalid).
    """
    if not narration or not isinstance(narration, str):
        return []

    started = time.monotonic()
    raw_response = ""
    validated = []
    dropped = []

    try:
        response, _provider = route(
            messages=[{"role": "user", "content": narration}],
            task_type="extraction",
            system_prompt=SYSTEM_PROMPT,
        )
        raw_response = response or ""

        candidates = _extract_raw_candidates(raw_response)
        if candidates is None:
            log(f"npc_parse: narration_chars={len(narration)} "
                f"raw_response={raw_response[:160]!r} "
                f"validated=[] dropped=[parse_failed] "
                f"latency_ms={int((time.monotonic() - started) * 1000)}")
            return []

        seen_names = set()
        for cand in candidates:
            normalized = _normalize_npc(cand)
            if normalized is None:
                dropped.append((str(cand)[:60], "bad_shape"))
                continue
            ok, reason = _validate_npc(normalized, pc_names=pc_names)
            if not ok:
                dropped.append((normalized.get("name", "")[:60], reason or "unknown"))
                continue
            # De-dup within a single narration. The engine handles cross-turn
            # de-dup via canonical_name UNIQUE constraint, but a single turn
            # naming someone twice should still produce one record.
            if normalized["name"] in seen_names:
                dropped.append((normalized["name"][:60], "duplicate_in_turn"))
                continue
            seen_names.add(normalized["name"])
            validated.append(normalized)

    except Exception as e:
        log(f"npc_parse: error={e!r} "
            f"latency_ms={int((time.monotonic() - started) * 1000)}")
        return []

    log(f"npc_parse: narration_chars={len(narration)} "
        f"raw_response={raw_response[:160]!r} "
        f"validated={[n['name'] for n in validated]} "
        f"dropped={[f'{c}:{r}' for c, r in dropped]} "
        f"latency_ms={int((time.monotonic() - started) * 1000)}")
    return validated
