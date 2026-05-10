#!/usr/bin/env python3
"""
Avrae listener — parses Avrae's embed output into structured roll events
and maintains a short-window per-guild buffer that the DM consults when
narrating.

This is the bridge between Avrae (mechanics) and Virgil DM (narrative).

Robust by design: any unparseable embed is captured as a raw-text event
rather than dropped. The DM still gets *something* to react to.
"""

import re
import time
import datetime
from collections import defaultdict
from typing import Optional, List, Dict, Any

# How long mechanical events stay relevant for narration. Anything older
# than this is swept on the next access.
EVENT_TTL_SECONDS = 75

# Bug 1 Phase 1 (Session 32) — How long a DM roll directive stays
# pending before lazy-sweep marks it expired. Co-located with
# EVENT_TTL_SECONDS so siblings stay in scan range. 300s = 5 min;
# Phase 2 retunes from observed age-at-resolution + age-at-expiry
# distribution.
PENDING_DIRECTIVE_TTL_SECONDS = 300

# The user ID of Avrae production bot. Discoverable, but cached here so we
# don't have to look it up at startup. If it changes, override AVRAE_USER_ID
# in .env or call set_avrae_user_id().
AVRAE_USER_ID_DEFAULT = 261302296103747584


_avrae_user_id = AVRAE_USER_ID_DEFAULT


def log(msg: str):
    """Timestamped log to stdout (captured by systemd journal).
    Module-level so tests can monkey-patch: avrae_listener.log = lambda m: None"""
    print(f"[{datetime.datetime.now().isoformat(timespec='seconds')}] {msg}", flush=True)


def set_avrae_user_id(user_id: int):
    global _avrae_user_id
    _avrae_user_id = int(user_id)


def get_avrae_user_id() -> int:
    """Return the configured Avrae user ID. Used by /setup to resolve
    Avrae as a guild member and grant explicit channel permissions."""
    return _avrae_user_id


def is_avrae(message) -> bool:
    """True if the message is from Avrae (by author ID)."""
    try:
        return message.author and message.author.id == _avrae_user_id
    except Exception:
        return False


# ─────────────────────────────────────────────────────────
# Parsing
# ─────────────────────────────────────────────────────────

# Matches "1d20 (15) + 4 = `19`" or "1d20 (15) - 1 = 14" or "= **19**"
# Captures: natural roll inside parens, final result after =.
_ROLL_RE = re.compile(
    r"\b(\d*d\d+)\s*\(([^)]+)\)"           # dice notation + (rolls)
    r".*?"                                  # mods
    r"=\s*[`*_~]*\s*(-?\d+)\s*[`*_~]*",     # final = N (with optional formatting)
    re.IGNORECASE | re.DOTALL,
)

# Matches a damage roll line — distinguishes from to-hit when both are present.
_DAMAGE_LINE_RE = re.compile(
    r"(?:\*\*)?(?:Damage|DMG)\b[^:]*(?:\*\*)?\s*:\s*"
    r".*?=\s*[`*_~]*\s*(-?\d+)\s*[`*_~]*",
    re.IGNORECASE | re.DOTALL,
)

_TO_HIT_LINE_RE = re.compile(
    r"(?:\*\*)?(?:To Hit|Attack(?:\s*\d+)?)\b[^:]*(?:\*\*)?\s*:\s*"
    r"\b\d*d\d+\s*\(([^)]+)\)"
    r".*?=\s*[`*_~]*\s*(-?\d+)\s*[`*_~]*",
    re.IGNORECASE | re.DOTALL,
)

_CRIT_RE = re.compile(r"\bcrit(?:ical)?\b", re.IGNORECASE)


def _kept_nat_roll(text: str) -> Optional[int]:
    """Extract the kept (non-dropped) natural d20 roll value.

    For advantage/disadvantage Avrae uses strikethrough on the dropped die,
    e.g. '1d20 (~~3~~ 17)' → 17 was kept, 3 was dropped. We strip the
    strikethrough segment before parsing so we read the kept die.

    Returns None if not a d20 or unparseable.
    """
    m = _ROLL_RE.search(text)
    if not m:
        return None
    dice = m.group(1).lower()
    if not dice.endswith('d20'):
        return None
    inside = m.group(2).strip()
    # Remove strikethrough segments (the dropped die in adv/dis)
    inside_clean = re.sub(r"~~[^~]*~~", "", inside)
    tokens = re.findall(r"-?\d+", inside_clean)
    if not tokens:
        # Fallback: maybe the WHOLE thing was strikethrough (shouldn't happen
        # with Avrae, but be safe)
        tokens = re.findall(r"-?\d+", inside)
    if not tokens:
        return None
    try:
        return int(tokens[0])
    except ValueError:
        return None


def _final_result(text: str) -> Optional[int]:
    """Extract the final '= N' result from a roll string."""
    m = _ROLL_RE.search(text)
    if not m:
        # Fallback: bare = N
        m2 = re.search(r"=\s*[`*_~]*\s*(-?\d+)\s*[`*_~]*", text)
        if m2:
            try:
                return int(m2.group(1))
            except ValueError:
                return None
        return None
    try:
        return int(m.group(3))
    except ValueError:
        return None


def _embed_to_text(embed) -> str:
    """Flatten an embed into a single string for regex extraction."""
    parts = []
    if embed.title:
        parts.append(embed.title)
    if embed.description:
        parts.append(embed.description)
    for field in (embed.fields or []):
        parts.append(f"{field.name}: {field.value}")
    if embed.footer and embed.footer.text:
        parts.append(embed.footer.text)
    return "\n".join(parts)


def _extract_actor(embed, raw: str, message) -> str:
    """Best-effort actor name from embed.author > title parse > 'Someone'."""
    if embed.author and embed.author.name:
        # Avrae character embeds often put "Character Name" as author
        name = embed.author.name.strip()
        # Strip trailing role markers like " (Player)" if present
        name = re.sub(r"\s*\([^)]+\)\s*$", "", name)
        if name and name.lower() != 'avrae':
            return name
    # Title patterns: "Throx attacks with X", "Throx makes a Stealth check"
    title = (embed.title or "").strip()
    m = re.match(r"([A-Z][\w'\-]+(?:\s+[A-Z][\w'\-]+)*)\s+(?:attacks|makes|casts|rolls|takes|uses|recovers|tries|begins|enters)\b", title)
    if m:
        return m.group(1)
    return "Someone"


def _classify_kind(embed, raw: str) -> str:
    """Classify the embed into one of: attack, check, save, cast, damage,
    rest, roll. Best-effort, falls through to 'roll'."""
    title = (embed.title or "").lower()
    desc = (embed.description or "").lower()
    text = (title + " " + desc).lower()

    if 'short rest' in text or 'long rest' in text:
        return 'rest'
    # Cast before save — spell descriptions often say "make a save"
    if 'casts' in title or re.search(r"\bcast\s", title):
        return 'cast'
    if 'attacks with' in title or 'attack' in title or _TO_HIT_LINE_RE.search(raw):
        return 'attack'
    if 'saving throw' in text or re.search(r"\bsave\b", title):
        return 'save'
    if 'check' in title or re.search(r"makes (?:a|an) \w+ check", title):
        return 'check'
    if 'damage' in title or ('takes' in title and 'damage' in text):
        return 'damage'
    return 'roll'


def _extract_detail(embed, kind: str) -> str:
    """Extract the 'thing' associated with the action (weapon, skill, spell)."""
    title = embed.title or ""
    if kind == 'attack':
        m = re.search(r"attacks with (?:a |an |the )?(.+?)(?:\!|\.|$)", title, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    if kind == 'check':
        m = re.search(r"makes (?:a |an )?(.+?) check", title, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    if kind == 'save':
        m = re.search(r"makes (?:a |an )?(.+?) (?:save|saving throw)", title, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    if kind == 'cast':
        m = re.search(r"casts (.+?)(?:\!|\.|$)", title, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    if kind == 'rest':
        if 'long rest' in title.lower():
            return 'long rest'
        if 'short rest' in title.lower():
            return 'short rest'
    return ''



# ─────────────────────────────────────────────────────────
# Initiative event parser  (Avrae !init plaintext output)
# ─────────────────────────────────────────────────────────
# Avrae sends !init output as PLAIN TEXT, not embeds. These patterns were
# captured from a live combat session (see [INIT_CAPTURE] log entries) so
# they reflect the real format, not a guess at it.

# !init begin produces two messages back-to-back. Either is a reliable
# "combat just started" signal.
_INIT_BEGIN_RE = re.compile(
    r"awaiting combatants|everyone roll for initiative",
    re.IGNORECASE,
)

# !init add <mod> <name>:  "<name> was added to combat with initiative ... = `<n>`."
_INIT_ADD_RE = re.compile(
    r"^(?P<name>.+?) was added to combat with initiative .*?=\s*`?(?P<init>-?\d+)`?\.?$",
    re.IGNORECASE,
)

# Per-turn header: "**Initiative <N> (round <R>)**: <name> (<@id>)"
_INIT_TURN_RE = re.compile(
    r"^\*\*Initiative\s+(?P<init>-?\d+)\s+\(round\s+(?P<round>\d+)\)\*\*:\s*"
    r"(?P<name>.+?)\s*\(<@!?(?P<controller_id>\d+)>\)",
    re.IGNORECASE,
)

# !init end confirmation prompt — combat HAS NOT ended yet.
_INIT_END_PROMPT_RE = re.compile(
    r"are you sure you want to end combat",
    re.IGNORECASE,
)

# Actual end. Avrae EDITS the "Are you sure?" message in place — no new
# message is sent. Three observed forms (from live sessions):
#   "Combat ended."
#   "-----COMBAT ENDED-----"   (code block variant)
#   "End of combat report: ..."
_INIT_END_RE = re.compile(r"combat ended|end of combat report", re.IGNORECASE)


def parse_init_event(message) -> Optional[Dict[str, Any]]:
    """Parse Avrae !init plaintext output into a structured init event,
    or return None if the message isn't init-related.

    Event shapes:
      {'init_event': 'begin'}                          combat starting
      {'init_event': 'add', 'name': str, 'init': int}  combatant added
      {'init_event': 'turn', 'init': int, 'round': int,
       'name': str, 'controller_id': int}              turn transition
      {'init_event': 'end_prompt'}                     "are you sure?" prompt
      {'init_event': 'end'}                            combat actually ended

    All events also carry channel_id, guild_id, ts.
    """
    if not is_avrae(message):
        return None
    content = (getattr(message, 'content', '') or '').strip()
    if not content:
        return None

    base = {
        'channel_id': message.channel.id if message.channel else None,
        'guild_id': message.guild.id if message.guild else None,
        'ts': time.time(),
    }

    # Order matters: end_prompt must be checked before end (the prompt
    # contains "end combat" which would otherwise match _INIT_END_RE).
    if _INIT_END_PROMPT_RE.search(content):
        return {**base, 'init_event': 'end_prompt'}

    if _INIT_END_RE.search(content):
        return {**base, 'init_event': 'end'}

    if _INIT_BEGIN_RE.search(content):
        return {**base, 'init_event': 'begin'}

    m = _INIT_ADD_RE.search(content)
    if m:
        try:
            init_val = int(m.group('init'))
        except (ValueError, TypeError):
            init_val = None
        return {**base, 'init_event': 'add',
                'name': m.group('name').strip(), 'init': init_val}

    m = _INIT_TURN_RE.search(content)
    if m:
        try:
            init_val = int(m.group('init'))
            round_val = int(m.group('round'))
            controller_id = int(m.group('controller_id'))
        except (ValueError, TypeError):
            return None
        return {**base, 'init_event': 'turn',
                'init': init_val, 'round': round_val,
                'name': m.group('name').strip(),
                'controller_id': controller_id}

    return None


# ─────────────────────────────────────────────────────────
# !init list snapshot parser  (Avrae plaintext, full combatant state)
# ─────────────────────────────────────────────────────────
# Avrae renders `!init list` as a plaintext message (sometimes inside a
# ```md code fence). The parser extracts a full per-combatant snapshot:
# init, name, active-marker, HP (when present), conditions, alive flag.
# Used by the persistence directive layer (Session 21).
#
# The header + separator pair is REQUIRED for a positive match — guards
# against narrative messages that happen to mention "Current initiative."

_INIT_LIST_HEADER_RE = re.compile(
    r"^Current initiative:\s*(?P<current_init>-?\d+)\s*"
    r"\(round\s+(?P<round>\d+)\)\s*$",
    re.MULTILINE,
)
_INIT_LIST_SEPARATOR_RE = re.compile(r"^={3,}\s*$", re.MULTILINE)
# Combatant row: optional '#' marker, init, name (anything except '<'), <status>.
# Trailing content after `>` (e.g. `(AC N)` suffix on sheet-bound combatants —
# observed live 2026-05-04) is ignored. Future Avrae renderers may add more
# trailing surfaces; permissive trailer keeps parse working without regex churn.
_INIT_LIST_ROW_RE = re.compile(
    r"^(?P<marker>[# ])\s*(?P<init>-?\d+):\s*"
    r"(?P<name>[^<\n]+?)\s*"
    r"<(?P<status>[^>\n]*)>"
    r"[^\n]*$",
    re.MULTILINE,
)
# Indented dash/star continuation = condition tied to previous combatant.
# (Format unconfirmed without real-combat HP samples; safe fallback regex.)
_INIT_LIST_CONDITION_RE = re.compile(
    r"^[ \t]+[-*]\s+(?P<condition>.+?)\s*$",
    re.MULTILINE,
)
# Status decoders. "n/m HP" or "n/m" — capture HP numbers.
_INIT_LIST_HP_RE = re.compile(
    r"^\s*(?P<cur>-?\d+)\s*/\s*(?P<max>-?\d+)\s*(?:HP\s*)?$",
    re.IGNORECASE,
)
# Defeated / KO markers. Catch the obvious surfaces; conservative fallback.
_INIT_LIST_DEFEATED_RE = re.compile(
    r"\b(?:defeated|dead|down|ko|knocked\s*out)\b",
    re.IGNORECASE,
)


def _decode_init_list_status(status: str) -> Dict[str, Any]:
    """Decode the contents of `<...>` in a `!init list` row.

    Returns {'hp_current', 'hp_max', 'alive', 'parse_kind'} where
    parse_kind is one of: 'none' | 'numeric' | 'private' | 'defeated' | 'unknown'.
    """
    s = (status or '').strip()
    if not s or s.lower() == 'none':
        return {'hp_current': None, 'hp_max': None, 'alive': 1,
                'parse_kind': 'none'}
    if _INIT_LIST_DEFEATED_RE.search(s):
        return {'hp_current': 0, 'hp_max': None, 'alive': 0,
                'parse_kind': 'defeated'}
    m = _INIT_LIST_HP_RE.match(s)
    if m:
        try:
            cur = int(m.group('cur'))
            mx = int(m.group('max'))
        except (TypeError, ValueError):
            return {'hp_current': None, 'hp_max': None, 'alive': 1,
                    'parse_kind': 'unknown'}
        alive = 1 if cur > 0 else 0
        return {'hp_current': cur, 'hp_max': mx, 'alive': alive,
                'parse_kind': 'numeric'}
    # Non-numeric, non-defeated, non-None → private mode descriptor like
    # "Healthy" / "Bloodied". Treat as alive, HP unknown.
    return {'hp_current': None, 'hp_max': None, 'alive': 1,
            'parse_kind': 'private'}


def parse_init_list_embed(text: str) -> Optional[Dict[str, Any]]:
    """Parse Avrae `!init list` plaintext into a structured snapshot.

    Returns None when the text isn't a recognizable `!init list` output.
    Returns a dict on success:
      {
        'round': int,
        'current_init': int,
        'combatants': [
          {'init': int, 'name': str, 'active': bool,
           'hp_current': int|None, 'hp_max': int|None,
           'conditions': str,           # comma-joined; '' when none
           'alive': int},               # 0/1
          ...
        ],
      }

    Pure regex, no LLM. Tolerates surrounding code fences (```md ... ```)
    and trailing whitespace.
    """
    if not text:
        return None

    # Strip surrounding code fences (``` or ```md) — Avrae sometimes wraps
    # the list in a Discord markdown code block. Strip only fence lines, not
    # the content between them.
    cleaned_lines = []
    for line in text.split('\n'):
        if line.strip().startswith('```'):
            continue
        cleaned_lines.append(line)
    cleaned = '\n'.join(cleaned_lines)

    header_m = _INIT_LIST_HEADER_RE.search(cleaned)
    sep_m = _INIT_LIST_SEPARATOR_RE.search(cleaned)
    if not header_m or not sep_m:
        return None

    try:
        current_init = int(header_m.group('current_init'))
        round_num = int(header_m.group('round'))
    except (TypeError, ValueError):
        return None

    # Split body into lines AFTER the separator. Walk lines so condition
    # continuation rows attach to the previous combatant.
    sep_end = sep_m.end()
    body = cleaned[sep_end:]
    combatants: List[Dict[str, Any]] = []
    last: Optional[Dict[str, Any]] = None
    last_conditions: Optional[List[str]] = None

    for raw_line in body.split('\n'):
        if not raw_line.strip():
            continue
        m = _INIT_LIST_ROW_RE.match(raw_line)
        if m:
            try:
                init_val = int(m.group('init'))
            except (TypeError, ValueError):
                init_val = 0
            status_raw = m.group('status') or ''
            decoded = _decode_init_list_status(status_raw)
            entry = {
                'init': init_val,
                'name': (m.group('name') or '').strip(),
                'active': m.group('marker') == '#',
                'hp_current': decoded['hp_current'],
                'hp_max': decoded['hp_max'],
                'conditions': '',
                'alive': decoded['alive'],
                'status_token': f"<{status_raw}>",
            }
            if decoded['parse_kind'] == 'unknown':
                # Surface for empirical follow-up so format unknowns are
                # observable even when the parser fails open.
                log(f"[INIT_LIST_PARSE_UNKNOWN] status={(m.group('status') or '')!r} "
                    f"name={entry['name']!r}")
            combatants.append(entry)
            last = entry
            last_conditions = []
            continue
        # Condition continuation tied to most-recent combatant.
        cm = _INIT_LIST_CONDITION_RE.match(raw_line)
        if cm and last is not None and last_conditions is not None:
            cond = (cm.group('condition') or '').strip()
            if cond:
                last_conditions.append(cond)
                last['conditions'] = ', '.join(last_conditions)

    # No combatants matched after a header+separator pair → still a
    # recognizable list, just empty (combat with zero combatants in flight).
    return {
        'round': round_num,
        'current_init': current_init,
        'combatants': combatants,
    }


def parse_avrae_embed(message) -> Optional[Dict[str, Any]]:
    """Turn one Avrae message into a structured event, or None if it doesn't
    look mechanical (e.g. lookup output, error, help)."""
    if not is_avrae(message):
        return None


    if not message.embeds:
        # Plain text Avrae messages are usually errors/help — skip.
        return None

    embed = message.embeds[0]
    raw = _embed_to_text(embed)
    if not raw.strip():
        return None

    # Skip pure-lookup embeds (spell/monster/item lookup). These have a
    # description like "**Spell** ..." and no roll syntax.
    if not _ROLL_RE.search(raw) and 'rest' not in raw.lower():
        return None

    kind = _classify_kind(embed, raw)
    actor = _extract_actor(embed, raw, message)
    detail = _extract_detail(embed, kind)

    # Pull result + nat
    result = None
    nat = None
    damage = None
    crit = bool(_CRIT_RE.search(raw))

    if kind == 'attack':
        # Attack: extract to-hit and damage separately
        hit_m = _TO_HIT_LINE_RE.search(raw)
        if hit_m:
            inside_clean = re.sub(r"~~[^~]*~~", "", hit_m.group(1))
            tokens = re.findall(r"-?\d+", inside_clean) or re.findall(r"-?\d+", hit_m.group(1))
            if tokens:
                try:
                    nat = int(tokens[0])
                except ValueError:
                    nat = None
            try:
                result = int(hit_m.group(2))
            except ValueError:
                result = None
        else:
            result = _final_result(raw)
            nat = _kept_nat_roll(raw)
        dmg_m = _DAMAGE_LINE_RE.search(raw)
        if dmg_m:
            try:
                damage = int(dmg_m.group(1))
            except ValueError:
                damage = None
    elif kind == 'cast':
        # Cast: damage line is what matters for narration; nat is rare
        dmg_m = _DAMAGE_LINE_RE.search(raw)
        if dmg_m:
            try:
                damage = int(dmg_m.group(1))
            except ValueError:
                damage = None
    elif kind == 'damage':
        damage = _final_result(raw)
    elif kind == 'rest':
        pass  # No numeric result needed
    else:
        result = _final_result(raw)
        nat = _kept_nat_roll(raw)

    return {
        'actor': actor,
        'kind': kind,
        'detail': detail,
        'result': result,
        'nat': nat,
        'damage': damage,
        'crit': crit,
        'channel_id': message.channel.id if message.channel else None,
        'guild_id': message.guild.id if message.guild else None,
        'ts': time.time(),
        'raw': raw[:500],
    }


# ─────────────────────────────────────────────────────────
# Per-guild rolling buffer
# ─────────────────────────────────────────────────────────

class RollBuffer:
    """In-memory rolling buffer of recent Avrae events, keyed by guild.

    Events older than EVENT_TTL_SECONDS are dropped on every access.
    Capped at 50 events per guild to prevent unbounded growth.
    """

    def __init__(self, ttl_seconds: int = EVENT_TTL_SECONDS, max_per_guild: int = 50):
        self._ttl = ttl_seconds
        self._max = max_per_guild
        self._events: Dict[int, List[Dict[str, Any]]] = defaultdict(list)

    def add(self, event: Dict[str, Any]):
        guild_id = event.get('guild_id')
        if guild_id is None:
            return
        bucket = self._events[guild_id]
        bucket.append(event)
        # Trim oldest if over cap
        if len(bucket) > self._max:
            del bucket[: len(bucket) - self._max]

    def _sweep(self, guild_id: int):
        now = time.time()
        cutoff = now - self._ttl
        bucket = self._events.get(guild_id, [])
        if not bucket:
            return
        surviving = []
        for e in bucket:
            if e.get('ts', 0) >= cutoff:
                surviving.append(e)
            else:
                age_s = round(now - e.get('ts', 0), 1)
                log(f"unconsumed_roll_swept: actor='{e.get('actor', '')}' "
                    f"action='{e.get('kind', '')}' age_s={age_s}")
        self._events[guild_id] = surviving

    def recent(self, guild_id: int, actor_filter: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Return current events for this guild, optionally filtered by actor
        name. Phase 6: STRICT EXACT-EQUALITY match on lowercased strings.
        Caller is responsible for passing canonicalized actor names; events
        are stored with canonicalized actor strings via the on_message
        resolution layer (discord_dnd_bot.on_message)."""
        self._sweep(guild_id)
        events = list(self._events.get(guild_id, []))
        if actor_filter:
            wanted = {a.lower() for a in actor_filter if a}

            def match(ev):
                actor = (ev.get('actor') or '').lower()
                if not actor:
                    return True  # Don't drop unknown-actor events
                return actor in wanted

            events = [e for e in events if match(e)]
        return events

    def consume(self, guild_id: int, actor_filter: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Same as recent(), but also clears matched events so they aren't
        re-narrated in the next turn. Non-matched events are preserved.
        Phase 6: STRICT EXACT-EQUALITY (no substring fallback)."""
        self._sweep(guild_id)
        events = list(self._events.get(guild_id, []))
        if not events:
            return []
        if actor_filter:
            wanted = {a.lower() for a in actor_filter if a}

            def match(ev):
                actor = (ev.get('actor') or '').lower()
                return bool(actor and actor in wanted)

            consumed = [e for e in events if match(e)]
            self._events[guild_id] = [e for e in events if not match(e)]
            return consumed
        else:
            self._events[guild_id] = []
            return events

    def clear(self, guild_id: int):
        self._events[guild_id] = []
