"""Location extractor — Phase 12B.2.

Advisory parser. Reads DM narration, returns a list of candidate location
records the engine MAY persist. Suggestion-only — never writes.

Public API:
    parse_locations(narration: str) -> list[dict]

Each output dict has the canonical four-key shape:
    {
      "name":                 <canonicalized location name, validated>,
      "type":                 <"town"/"dungeon"/"tavern"/etc, "" if unknown>,
      "parent_hint":          <containing place name, "" if unknown>,
      "description_fragment": <short atmospheric detail, "" if none>,
    }

Hard invariants (PHASE_12_SPEC §4, §7, §9.1):
- Narration-only input. No player input, no scene state, no character context.
- Strict whitelist on names: must match _NAME_RE AFTER canonicalization
  (article-stripping is identity normalization, NOT generation style).
- Identity normalization is DETERMINISTIC. Leading articles (the/a/an)
  are stripped from canonical names regardless of LLM emission. "The Rusty
  Anchor" and "Rusty Anchor" both become "Rusty Anchor".
- Generic location words (forest, dungeon, road, etc.) without a
  distinctive identity-bearing token are dropped. "Forest" out;
  "Whispering Woods" in.
- No engine writes. Reads strings, returns dicts.
- Never raises. Returns [] on any failure.

Wiki-entry test (the design constraint):
  If a candidate wouldn't survive being written into a persistent campaign
  wiki, it is NOT a location. That excludes: pure type-words, transient
  scenery ("the road", "the corner"), abstract regions ("the south"),
  faction-territory ("the empire") which is a faction concept not a place.

Why this differs from NPC extraction:
  NPCs are easier — proper names are usually unambiguous. Locations have
  three failure modes the LLM will hit constantly:
    (a) emitting "the X" where X is a pure type → caught by stoplist
    (b) emitting an entire region ("the eastern lands") → caught by regex
    (c) emitting a faction-as-place ("the Crimson Hand's territory") →
        caller must keep the parser narrow; we err on dropping.
"""

import json
import re
import time

from cloud_router import route
from dnd_engine import log, canonicalize_location_name

# ─────────────────────────────────────────────────────────
# Validator
# ─────────────────────────────────────────────────────────

# Strict format: 1-4 capitalized words. One word more than NPCs because
# location names are commonly longer ("The Whispering Pines of Eldermoor"
# canonicalizes to "Whispering Pines of Eldermoor" — but that has lowercase
# "of" which the regex won't pass; we intentionally reject those because
# they're descriptive prose, not identity tokens).
# Each word: uppercase letter then word chars / apostrophes / hyphens.
_NAME_RE = re.compile(r"^[A-Z][\w'\-]+(\s+[A-Z][\w'\-]+){0,3}$")

# Whole-name rejection: pure-generic locations. Compared against the whole
# canonicalized name AFTER article stripping. "Forest" alone → drop.
# "Whispering Forest" → keep ("Whispering" is the distinctive token).
# "The Forest" canonicalizes to "Forest" → drop.
_NAME_WHOLE_STOPLIST = frozenset({
    # Generic landscape
    "Forest", "Woods", "Wood", "Mountain", "Mountains", "Hill", "Hills",
    "Valley", "River", "Lake", "Sea", "Ocean", "Coast", "Shore", "Beach",
    "Plains", "Plain", "Desert", "Swamp", "Marsh", "Moor", "Meadow",
    "Field", "Cliff", "Cave", "Cavern", "Caves", "Caverns", "Glade",
    "Grove", "Pass", "Ridge", "Peak", "Summit", "Glen", "Vale",
    # Generic settlements / structures
    "City", "Town", "Village", "Hamlet", "Settlement", "Castle", "Fort",
    "Fortress", "Keep", "Tower", "Citadel", "Palace", "Manor", "Estate",
    "Temple", "Shrine", "Cathedral", "Chapel", "Monastery", "Abbey",
    "Inn", "Tavern", "Bar", "Pub", "Alehouse",
    "Market", "Square", "Plaza", "Forum", "Bazaar",
    "Gate", "Bridge", "Wall", "Walls", "Tower", "Watchtower",
    "Smithy", "Forge", "Mill", "Stable", "Stables", "Warehouse",
    "Library", "Archive", "Vault", "Vaults", "Crypt", "Tomb", "Tombs",
    # Generic interior
    "Hall", "Room", "Chamber", "Corridor", "Hallway", "Passage", "Stair",
    "Stairs", "Stairway", "Chambers", "Quarters", "Cellar", "Basement",
    "Attic", "Loft",
    # Generic dungeon / quest
    "Dungeon", "Dungeons", "Lair", "Den", "Hideout", "Hideaway", "Sanctum",
    "Sanctuary",
    # Roads / passages
    "Road", "Roads", "Path", "Trail", "Way", "Highway", "Street",
    "Streets", "Alley", "Alleys", "Avenue", "Lane",
    # Abstract / cardinal-direction "regions"
    "North", "South", "East", "West", "Northeast", "Northwest",
    "Southeast", "Southwest", "Realm", "Lands", "Land", "Region",
    "Kingdom", "Empire", "Country", "Province", "Territory", "District",
    # Time-of-day or weather as scene words masquerading as places
    "Outside", "Inside", "Indoors", "Outdoors", "Above", "Below",
    "Underground", "Surface",
})

# Per-field length caps. Spec §7: description_fragment capped at 100.
_FIELD_LEN_CAPS = {
    "name":                 80,
    "type":                 30,
    "parent_hint":          80,
    "description_fragment": 100,
}

# Shell metacharacters and control chars. Refused anywhere in any field.
_BAD_CHARS = re.compile(r"[`;|&><$\\\n\r]")

# Canonical output shape.
_LOCATION_KEYS = ("name", "type", "parent_hint", "description_fragment")


def _normalize_location(loc):
    """Coerce an LLM-emitted dict into the canonical 4-key shape.
    Strips whitespace, normalizes via canonicalize_location_name on `name`
    (which strips leading articles deterministically — see engine docstring),
    coerces non-string values to ''. Returns dict or None on bad shape.

    parent_hint is canonicalized too for consistency, but NOT validated as
    strictly — it's a hint string that 12B.3 will look up in the locations
    table to resolve to a real parent_location_id.
    """
    if not isinstance(loc, dict):
        return None

    raw_name = loc.get("name", "")
    if not isinstance(raw_name, str):
        raw_name = ""
    name = canonicalize_location_name(raw_name)

    raw_parent = loc.get("parent_hint", "")
    if not isinstance(raw_parent, str):
        raw_parent = ""
    parent_hint = canonicalize_location_name(raw_parent)

    def _clean(field):
        v = loc.get(field, "")
        if not isinstance(v, str):
            return ""
        return v.strip()

    return {
        "name":                 name,
        "type":                 _clean("type"),
        "parent_hint":          parent_hint,
        "description_fragment": _clean("description_fragment"),
    }


def _validate_location(loc):
    """Return (valid: bool, drop_reason: str | None).

    drop_reason is one of:
      bad_shape         — not a dict, or no name
      bad_name_format   — fails _NAME_RE post-canonicalization
      name_in_stoplist  — pure-generic location word
      length_exceeded   — any field over its cap
      bad_chars         — shell metas or control chars in any field
    """
    if not isinstance(loc, dict):
        return False, "bad_shape"

    name = loc.get("name", "")
    if not name or not isinstance(name, str):
        return False, "bad_shape"

    if not _NAME_RE.match(name):
        return False, "bad_name_format"

    if name in _NAME_WHOLE_STOPLIST:
        return False, "name_in_stoplist"

    for field, cap in _FIELD_LEN_CAPS.items():
        v = loc.get(field, "")
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
NAMED LOCATIONS — specific places the world should remember.

Output ONLY a JSON array of objects. No prose. No markdown. No keys outside
the schema. Empty array [] if no named location appears.

Each object has EXACTLY these four keys (use empty string for unknown fields):
  "name":                  proper-noun place name OR distinctive descriptor
  "type":                  short category ("town", "dungeon", "tavern", "region")
  "parent_hint":           name of the containing place if mentioned
                           (e.g. "Redhaven" for a tavern within Redhaven)
  "description_fragment":  short atmospheric detail, max ~80 chars

THE WIKI-ENTRY TEST (the only rule that matters):
  If you wouldn't write this place into a persistent campaign wiki — OMIT it.

What survives the wiki test (KEEP):
  - Proper-noun place names: "Redhaven", "Stoneforge", "Whispering Woods"
  - Distinctive descriptors that name a unique place:
    "The Crystal Caves", "The Old Mill", "The Iron Tankard"
    Leading articles (the/a/an) are stripped automatically — emit them
    attached or not, whichever is natural.
  - Notable interiors WITH a proper name: "The Rusty Anchor" (a tavern),
    "The Stoneforge Guild Hall"

What fails the wiki test (OMIT):
  - Pure type-words: "the forest", "a tavern", "the dungeon", "the road"
  - Generic interiors: "the room", "the hall", "the corridor"
  - Transient scenery: "the corner", "the doorway", "the window"
  - Cardinal-direction regions: "the north", "the eastern lands"
  - Abstract realms: "the kingdom", "the empire" (those are political
    entities, not places-on-a-map for our purposes)
  - Weather / time scene words: "outside", "underground", "the daylight"

What is NOT a location for THIS extractor:
  - Factions / organizations: "The Crimson Hand", "the Order of the Sun"
  - NPCs and their groups (handled by a separate parser)
  - Items, books, banners
  - Deities and planes of existence

Output rules:
  - "name": the proper-noun name. If preceded by "the/a/an", you may
    include the article or not — it is normalized away regardless.
  - "type": short category. Common values: town, city, village, dungeon,
    tavern, inn, temple, shrine, fortress, castle, region, district,
    forest, mountain, river. Use "" if unclear.
  - "parent_hint": if the narration says "in Redhaven, the Rusty Anchor",
    parent_hint for Rusty Anchor is "Redhaven". "" if not mentioned.
  - "description_fragment": atmosphere, not history. "smoky low ceilings"
    yes; "founded by King Aldric" no.
  - When in doubt — OMIT. Better to miss a real place than fabricate one.

Example: "You arrive in Redhaven, a salt-stained port town."
Output: [{"name": "Redhaven", "type": "town", "parent_hint": "", "description_fragment": "salt-stained port town"}]

Example: "The Rusty Anchor sits at the end of Redhaven's docks, smoky and low-ceilinged."
Output: [{"name": "Rusty Anchor", "type": "tavern", "parent_hint": "Redhaven", "description_fragment": "smoky, low-ceilinged"}]

Example: "You take the road north toward the mountains."
Output: []

Example: "The Whispering Woods stretch dark before you."
Output: [{"name": "Whispering Woods", "type": "forest", "parent_hint": "", "description_fragment": "stretches dark ahead"}]

Example: "A tavern keeper greets you. The room is warm."
Output: []

Example: "You enter the Stoneforge Guild Hall, lantern-lit and smelling of iron."
Output: [{"name": "Stoneforge Guild Hall", "type": "guild hall", "parent_hint": "", "description_fragment": "lantern-lit, scent of iron"}]

Example: "The Crimson Hand has been busy in the south."
Output: []

Example: "The Old Mill creaks in the wind, abandoned for years."
Output: [{"name": "Old Mill", "type": "ruin", "parent_hint": "", "description_fragment": "creaking, abandoned"}]"""


def _extract_raw_candidates(text):
    """Pull a JSON array out of model output. Returns list | None."""
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


def parse_locations(narration):
    """Read DM narration, return list of candidate location dicts.

    Each dict has exactly four keys: name, type, parent_hint,
    description_fragment. All values are strings. `name` is canonicalized
    (article-stripped) and validated; the other three may be empty.

    Never raises. Returns [] on any failure.
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
            log(f"loc_parse: narration_chars={len(narration)} "
                f"raw_response={raw_response[:160]!r} "
                f"validated=[] dropped=[parse_failed] "
                f"latency_ms={int((time.monotonic() - started) * 1000)}")
            return []

        seen_names = set()
        for cand in candidates:
            normalized = _normalize_location(cand)
            if normalized is None:
                dropped.append((str(cand)[:60], "bad_shape"))
                continue
            ok, reason = _validate_location(normalized)
            if not ok:
                dropped.append((normalized.get("name", "")[:60], reason or "unknown"))
                continue
            # De-dup within a single narration by canonical name.
            if normalized["name"] in seen_names:
                dropped.append((normalized["name"][:60], "duplicate_in_turn"))
                continue
            seen_names.add(normalized["name"])
            validated.append(normalized)

    except Exception as e:
        log(f"loc_parse: error={e!r} "
            f"latency_ms={int((time.monotonic() - started) * 1000)}")
        return []

    log(f"loc_parse: narration_chars={len(narration)} "
        f"raw_response={raw_response[:160]!r} "
        f"validated={[loc['name'] for loc in validated]} "
        f"dropped={[f'{c}:{r}' for c, r in dropped]} "
        f"latency_ms={int((time.monotonic() - started) * 1000)}")
    return validated
