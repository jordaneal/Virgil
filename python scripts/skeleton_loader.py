"""Skeleton loader — Phase 12C.

Reads authored campaign-skeleton markdown files and:
  1. Promotes their entities to canon (skeleton_origin=1) via the engine
     write paths — see apply_skeleton().
  2. Returns a prompt-ready blob for injection into dm_respond's system
     prompt — see get_skeleton_prompt_block().

Both share a single parsed cache keyed by campaign_id and gated on file
mtime, so re-runs and per-turn calls are cheap.

Authority model (PHASE_12_SPEC §9.10):
  - skeleton.md entries always have skeleton_origin=1.
  - The loader NEVER auto-mutates skeleton.md. Author-controlled file.
  - Parser-detected entities (skeleton_origin=0) cannot overwrite
    skeleton-authored fields. That's enforced at the engine layer in
    npc_upsert / location_upsert.
  - Re-running the loader on the same file is a no-op for already-
    matching rows; field updates flow through the engine's "skeleton
    re-load" branch.

File layout:
  /home/jordaneal/scripts/campaigns/<campaign_id>/skeleton.md

Format (per spec §12C):

    # Campaign: <name>

    ## Central conflict
    <prose>

    ## Major hooks
    - Hook line
    - Hook line

    ## Primary NPCs
    ### <Name> (<role>, <location>)
    Motivation: <text>
    Voice: <text>
    [free prose continues until next ### or ## header]

    ## Key locations
    ### <Name> (<type>[, in <parent>])
    [free prose description]

    ## Factions
    ### <Name> (<type>)
    [free prose — factions are NOT persisted in 12C; reserved for future]

Strictness:
  This parser is strict because skeleton.md is human-authored. Malformed
  headings raise SkeletonParseError with the offending line. Better to
  fail loud than write partial garbage.
"""

import os
import re
import threading
from pathlib import Path

from dnd_engine import (
    log,
    npc_upsert, npc_get_by_name,
    location_upsert, location_get_by_name,
    canonicalize_location_name,
)


SKELETON_ROOT = Path("/home/jordaneal/scripts/campaigns")


class SkeletonParseError(ValueError):
    """Raised when skeleton.md has malformed structure. Includes line context."""


def _skeleton_path(campaign_id: int) -> Path:
    return SKELETON_ROOT / str(campaign_id) / "skeleton.md"


# ── In-memory mtime cache ─────────────────────────────────────────────────────
# Keyed by campaign_id. Value: (mtime, parsed_dict). Lock protects concurrent
# reads from dm_respond + apply_skeleton (the latter is rare; the former is
# every turn).
_cache = {}
_cache_lock = threading.Lock()


# ── Header regexes ────────────────────────────────────────────────────────────
# H1 campaign title:    "# Campaign: Foo" (optional, advisory)
# H2 sections:          "## Primary NPCs" / "## Key locations" / etc.
# H3 entry headings:    "### Name (role, location)" / "### Name (type)"
_RE_H1 = re.compile(r"^\#\s+(.*?)\s*$")
_RE_H2 = re.compile(r"^\#\#\s+(.*?)\s*$")
_RE_H3 = re.compile(r"^\#\#\#\s+(.*?)\s*$")
_RE_H4 = re.compile(r"^\#\#\#\#\s+(.*?)\s*$")
# Composition Layer v0 (S60) — recognize "1. ", "2. ", etc. as act-index
# prefixes inside `#### Acts` subsections under quest H3s.
_RE_ACT_INDEX = re.compile(r"^\s*(\d+)\.\s+(.*?)\s*$")
# Per-act predicate hint lines authored under each numbered act. Operator-
# friendly: "Scene count threshold: 2" / "Location: farmstead grounds".
_RE_ACT_HINT = re.compile(
    r"^\s*(scene\s+count\s+threshold|location|location_id|"
    r"scene_count|scene_count_threshold)\s*:\s*(.+?)\s*$",
    re.I,
)

# H3 parens parser. Examples:
#   "Garrick (blacksmith, Redhaven)"  → name='Garrick', kind='blacksmith', loc='Redhaven'
#   "Garrick"                          → name='Garrick', kind='',           loc=''
#   "The Rusty Anchor (tavern in Redhaven)" → name='The Rusty Anchor', kind='tavern', loc='Redhaven'
#   "Redhaven (town)"                  → name='Redhaven', kind='town',     loc=''
_RE_H3_PARENS = re.compile(r"^(?P<name>[^()]+?)\s*\((?P<inside>[^()]*)\)\s*$")

# Sections we care about. Lowercase comparison.
_NPC_SECTIONS = {"primary npcs", "npcs", "characters"}
_LOCATION_SECTIONS = {"key locations", "locations", "places"}
# Track 4 #3 (Session 27) — optional `## Starting time` section. Body
# is a few `key=value` lines (day=N, phase=NAME). Per §11.D=a lock —
# falls back to defaults `(day=1, phase='Morning')` if absent.
_STARTING_TIME_SECTIONS = {"starting time", "start time", "starting clock"}
# Player capabilities — author-declared capability HINT layer for S9.
# One bullet per character: "- <Name>: <category>, <category>, ..."
# This is a HINT layer only — it can upgrade verdict confidence in the
# capability check (no-Avrae-match → CONFIRMED) but never produces
# INVALID. Absence of a player capabilities section is normal; the
# default verdict for unmatched claims stays VALID_BUT_UNCONFIGURED.
_PLAYER_CAPABILITIES_SECTIONS = {"player capabilities", "character capabilities", "capabilities"}
# Sections we PARSE but don't persist in 12C. Reserved for later phases.
_RESERVED_SECTIONS = {"factions", "central conflict", "major hooks", "hooks"}


def _parse_h3_heading(heading: str) -> dict:
    """Parse an H3 entry heading into {name, kind, location_or_parent_hint}.

    Strict: requires either bare name or "(...)" parens form. Raises
    SkeletonParseError on malformed input.

    Returns:
      {'name': str, 'kind': str, 'parent_hint': str}
        - name: the proper noun before the parens (or whole line if no parens)
        - kind: first comma-separated token inside parens — role for NPCs,
                type for locations
        - parent_hint: remainder after first comma, with leading "in "
                       stripped — the containing place name. Also handles
                       " in " as separator when no comma is present:
                       "(tavern in Redhaven)" → kind='tavern', parent='Redhaven'
    """
    h = heading.strip()
    if not h:
        raise SkeletonParseError("empty H3 heading")

    # Reject orphan parens like "(blacksmith)" — no proper name before them.
    if h.startswith("("):
        raise SkeletonParseError(f"H3 heading missing name before parens: {heading!r}")

    m = _RE_H3_PARENS.match(h)
    if not m:
        # Bare name — allowed, no metadata. Reject anything containing
        # parens we couldn't parse cleanly.
        if "(" in h or ")" in h:
            raise SkeletonParseError(f"malformed parens in H3 heading: {heading!r}")
        return {'name': h, 'kind': '', 'parent_hint': ''}

    name = m.group('name').strip()
    inside = m.group('inside').strip()
    if not name:
        raise SkeletonParseError(f"empty name in heading: {heading!r}")

    if not inside:
        return {'name': name, 'kind': '', 'parent_hint': ''}

    # Split on comma first. If no comma, fall back to " in " as a separator
    # so "(tavern in Redhaven)" parses correctly.
    if "," in inside:
        parts = [p.strip() for p in inside.split(",", 1)]
        kind = parts[0]
        parent = parts[1] if len(parts) > 1 else ''
        # Strip leading "in " from parent.
        if parent.lower().startswith("in "):
            parent = parent[3:].strip()
    else:
        # Look for " in " as the kind/parent boundary, case-insensitive.
        m_in = re.search(r"\s+in\s+", inside, flags=re.IGNORECASE)
        if m_in:
            kind = inside[:m_in.start()].strip()
            parent = inside[m_in.end():].strip()
        else:
            kind = inside
            parent = ''

    return {'name': name, 'kind': kind, 'parent_hint': parent}


def _parse_skeleton_text(text: str) -> dict:
    """Parse the full skeleton.md into a structured dict.

    Returns:
      {
        'title':           str,
        'central_conflict': str,
        'hooks':           list[str],
        'npcs':            list[{name, role, location_hint, description}],
        'locations':       list[{name, type, parent_hint, description}],
        'factions':        list[{name, type, description}],   # parsed, not yet persisted
        'player_capabilities': dict[str, set[str]],            # S9 hint layer
        'unknown_sections': list[str],                          # H2s we didn't recognize
      }

    The `player_capabilities` map is keyed by character display name
    (as written in the skeleton) and values are sets of weapon-family
    category strings. Capability strings are NOT validated by the
    parser — that's the consumer's responsibility, since validation
    requires importing the v1 weapon family list from orchestration.

    Raises SkeletonParseError on structural problems (bad H3 heading inside
    a known section). Unknown H2 sections are collected, not fatal.
    """
    result = {
        'title':                '',
        'central_conflict':     '',
        'hooks':                [],
        'npcs':                 [],
        'locations':            [],
        'factions':             [],
        'player_capabilities':  {},
        'starting_time':        None,   # {'day': int, 'phase': str} | None
        'unknown_sections':     [],
        # Composition Layer v0 (S60) — quest-decomposition extraction.
        # Each entry corresponds to an `### <Quest title>` H3 inside the
        # ## Major hooks section, with optional `#### Acts` subsection.
        # Existing flat-bullet hooks remain in `result['hooks']`; this
        # field is additive and stays empty for skeletons that don't use
        # the v0 authoring extension.
        # Shape: [{'title': str, 'description': str, 'acts': [
        #   {'act_index': int, 'act_title': str, 'act_description': str,
        #    'predicate': dict}  # narrow vocab: scene_count_threshold + location_id
        # ]}]
        'quest_decompositions': [],
    }

    section = None             # current H2 section (lowercased) or None
    entry_kind = None          # 'npc' | 'location' | 'faction' | None
    current_entry = None       # the dict we're building
    description_lines = []     # buffered prose for the current entry
    central_conflict_lines = []
    # Composition Layer v0 (S60) — quest-decomposition parsing state.
    # When entry_kind=='hooks' AND an H3 appears, switch into per-quest
    # parsing. `current_quest` is the dict being built; `current_act` is
    # the dict for the in-progress act under `#### Acts`.
    current_quest = None
    current_quest_desc_lines = []
    in_acts_subsection = False
    current_act_entry = None
    current_act_desc_lines = []

    def _flush_act():
        nonlocal current_act_entry
        if current_act_entry is None or current_quest is None:
            current_act_entry = None
            return
        desc = "\n".join(current_act_desc_lines).strip()
        # Parse hint lines out of the description into structured predicate.
        predicate = {}
        remaining_desc_lines = []
        for dline in current_act_desc_lines:
            mh = _RE_ACT_HINT.match(dline)
            if mh:
                key_raw = mh.group(1).strip().lower()
                val_raw = mh.group(2).strip()
                # Map operator-friendly keys to JSON keys.
                if key_raw in ('scene count threshold', 'scene_count_threshold',
                               'scene_count'):
                    try:
                        predicate['scene_count_threshold'] = int(val_raw)
                    except ValueError:
                        pass
                elif key_raw in ('location', 'location_id'):
                    # Operator authors location by name here; engine-side
                    # resolution to dnd_locations.id happens at seed time.
                    # Stash the raw name; bot-side seeder resolves.
                    predicate['location_name'] = val_raw
            else:
                if dline.strip():
                    remaining_desc_lines.append(dline)
        current_act_entry['act_description'] = "\n".join(remaining_desc_lines).strip()
        current_act_entry['predicate'] = predicate
        current_quest['acts'].append(current_act_entry)
        current_act_entry = None

    def _flush_quest():
        nonlocal current_quest, in_acts_subsection
        _flush_act()
        if current_quest is None:
            return
        # Description is everything pre-Acts; Acts content goes into acts list.
        current_quest['description'] = "\n".join(current_quest_desc_lines).strip()
        result['quest_decompositions'].append(current_quest)
        current_quest = None
        in_acts_subsection = False

    def _flush_entry():
        """Move buffered description into current_entry and append to result."""
        nonlocal current_entry
        if current_entry is None:
            return
        desc = "\n".join(description_lines).strip()
        # Per-kind structured-line extraction (Motivation:, Voice:, etc.)
        # for NPCs. Keep the raw description too — used for prompt injection.
        if entry_kind == 'npc':
            current_entry['description'] = desc
            result['npcs'].append(current_entry)
        elif entry_kind == 'location':
            current_entry['description'] = desc
            result['locations'].append(current_entry)
        elif entry_kind == 'faction':
            current_entry['description'] = desc
            result['factions'].append(current_entry)
        current_entry = None

    for raw_line in text.splitlines():
        line = raw_line.rstrip()

        m_h1 = _RE_H1.match(line)
        if m_h1 and not _RE_H2.match(line) and not _RE_H3.match(line):
            # H1 only — campaign title.
            _flush_entry()
            _flush_quest()
            description_lines = []
            current_quest_desc_lines = []
            title = m_h1.group(1)
            # Spec format is "Campaign: <name>"; strip the prefix if present.
            if title.lower().startswith("campaign:"):
                title = title[len("campaign:"):].strip()
            result['title'] = title
            section = None
            entry_kind = None
            continue

        m_h2 = _RE_H2.match(line)
        if m_h2:
            _flush_entry()
            _flush_quest()
            description_lines = []
            current_quest_desc_lines = []
            section_raw = m_h2.group(1)
            section = section_raw.strip().lower()
            if section in _NPC_SECTIONS:
                entry_kind = 'npc'
            elif section in _LOCATION_SECTIONS:
                entry_kind = 'location'
            elif section == 'factions':
                entry_kind = 'faction'
            elif section in _PLAYER_CAPABILITIES_SECTIONS:
                entry_kind = 'player_capabilities'
            elif section in _STARTING_TIME_SECTIONS:
                entry_kind = 'starting_time'
            elif section in {'central conflict'}:
                entry_kind = 'central_conflict'
                central_conflict_lines = []
            elif section in {'major hooks', 'hooks'}:
                entry_kind = 'hooks'
            else:
                entry_kind = None
                result['unknown_sections'].append(section_raw)
            continue

        m_h3 = _RE_H3.match(line)
        # Bypass H3 match if the line is actually H4 (#### starts with ###).
        if m_h3 and not _RE_H4.match(line):
            _flush_entry()
            _flush_quest()
            description_lines = []
            current_quest_desc_lines = []
            heading = m_h3.group(1)
            parsed = _parse_h3_heading(heading)
            if entry_kind == 'npc':
                current_entry = {
                    'name':          parsed['name'],
                    'role':          parsed['kind'],
                    'location_hint': parsed['parent_hint'],
                    'description':   '',
                }
            elif entry_kind == 'location':
                current_entry = {
                    'name':        parsed['name'],
                    'type':        parsed['kind'],
                    'parent_hint': parsed['parent_hint'],
                    'description': '',
                }
            elif entry_kind == 'faction':
                current_entry = {
                    'name':        parsed['name'],
                    'type':        parsed['kind'],
                    'description': '',
                }
            elif entry_kind == 'hooks':
                # Composition Layer v0 (S60) — H3 inside hooks = a quest
                # decomposition entry. Title from H3, prose buffered until
                # `#### Acts` (or end-of-section).
                current_quest = {
                    'title':       heading.strip(),
                    'description': '',
                    'acts':        [],
                }
                in_acts_subsection = False
            else:
                # H3 outside a recognized section — strict mode: refuse.
                raise SkeletonParseError(
                    f"H3 heading {heading!r} found outside a known section "
                    f"(current section={section!r})"
                )
            continue

        m_h4 = _RE_H4.match(line)
        if m_h4:
            # Composition Layer v0 (S60) — `#### Acts` inside a quest H3
            # under ## Major hooks. Switches into act-parsing sub-mode.
            heading_lower = m_h4.group(1).strip().lower()
            if entry_kind == 'hooks' and current_quest is not None and heading_lower == 'acts':
                _flush_act()
                in_acts_subsection = True
            # Other H4s currently unrecognized — silently skipped (forward-
            # compatible: future per-quest subsections won't break the parser).
            continue

        # Body text. Buffer based on what section we're in.
        if entry_kind in ('npc', 'location', 'faction'):
            if current_entry is not None:
                description_lines.append(line)
        elif entry_kind == 'hooks':
            stripped = line.strip()
            # Composition Layer v0 (S60) — three sub-modes inside hooks:
            # (1) inside a quest H3's `#### Acts` subsection → parse numbered
            #     "1. <Act title>" lines as acts; indented lines become the
            #     act description.
            # (2) inside a quest H3 BEFORE `#### Acts` → buffer prose into
            #     current_quest_desc_lines.
            # (3) outside any quest H3 (legacy flat-bullet hooks) → bullet
            #     markers become `result['hooks']` strings as before.
            if current_quest is not None and in_acts_subsection:
                m_idx = _RE_ACT_INDEX.match(line)
                if m_idx:
                    # New act entry.
                    _flush_act()
                    act_index = int(m_idx.group(1))
                    act_title = m_idx.group(2).strip()
                    current_act_entry = {
                        'act_index':       act_index,
                        'act_title':       act_title,
                        'act_description': '',
                        'predicate':       {},
                    }
                    current_act_desc_lines = []
                elif current_act_entry is not None:
                    # Buffer description / predicate-hint lines for the act.
                    if line.strip() or current_act_desc_lines:
                        current_act_desc_lines.append(line)
                # Lines before the first "N. " in the Acts subsection are
                # ignored (allows blank lines / intro prose).
            elif current_quest is not None:
                # Inside a quest H3 BEFORE `#### Acts` — buffer prose as
                # the quest description.
                current_quest_desc_lines.append(line)
            elif stripped.startswith(("-", "*")):
                # Legacy flat-bullet hook (existing skeleton.md shape).
                hook = stripped.lstrip("-* ").strip()
                if hook:
                    result['hooks'].append(hook)
        elif entry_kind == 'player_capabilities':
            stripped = line.strip()
            # Format per bullet: "- <Character Name>: <cap>, <cap>, ..."
            # Empty lines and non-bullet prose are silently ignored
            # (allows section blurbs / intro paragraphs).
            if not stripped.startswith(("-", "*")):
                continue
            body = stripped.lstrip("-* ").strip()
            if ':' not in body:
                # No colon → not a capability declaration. Ignore
                # silently — author may have written prose bullets.
                continue
            name_part, _, caps_part = body.partition(':')
            name = name_part.strip()
            if not name:
                continue
            caps = {
                c.strip().lower()
                for c in caps_part.split(',')
                if c.strip()
            }
            if not caps:
                continue
            # Merge into existing entry if the same character is named
            # twice (defensive against author error). Set union semantics.
            existing = result['player_capabilities'].get(name, set())
            result['player_capabilities'][name] = existing | caps
        elif entry_kind == 'central_conflict':
            if line.strip():
                central_conflict_lines.append(line.strip())
        elif entry_kind == 'starting_time':
            stripped = line.strip()
            if not stripped or '=' not in stripped:
                continue
            # Strip leading bullet markers if author used "- day=1" style.
            if stripped.startswith(('-', '*')):
                stripped = stripped.lstrip('-* ').strip()
            key, _, value = stripped.partition('=')
            key = key.strip().lower()
            value = value.strip()
            if not value:
                continue
            if result['starting_time'] is None:
                result['starting_time'] = {}
            if key in ('day', 'campaign_day'):
                try:
                    day_val = int(value)
                    if day_val >= 1:
                        result['starting_time']['day'] = day_val
                except ValueError:
                    pass
            elif key in ('phase', 'day_phase', 'time_of_day'):
                # Case-insensitive match against the canonical 6-phase
                # enum; normalize to canonical capitalization.
                v_lower = value.lower()
                for canonical in ('Morning', 'Midday', 'Afternoon',
                                  'Evening', 'Night', 'Late Night'):
                    if canonical.lower() == v_lower:
                        result['starting_time']['phase'] = canonical
                        break

    # End-of-file flush.
    _flush_entry()
    _flush_quest()
    if central_conflict_lines:
        result['central_conflict'] = " ".join(central_conflict_lines)

    return result


def parse_skeleton_file(campaign_id: int, force_reload: bool = False) -> dict | None:
    """Read and parse skeleton.md for a campaign. Returns parsed dict or None
    if the file doesn't exist. Raises SkeletonParseError on malformed content.

    Cached by mtime — repeat calls on an unchanged file are sub-millisecond.
    Pass force_reload=True to bypass cache (e.g. after explicit edit).
    """
    path = _skeleton_path(campaign_id)
    if not path.is_file():
        # Clear stale cache entry if file was deleted.
        with _cache_lock:
            _cache.pop(campaign_id, None)
        return None

    try:
        mtime = path.stat().st_mtime
    except OSError as e:
        log(f"skeleton: stat failed for {path}: {e}")
        return None

    with _cache_lock:
        cached = _cache.get(campaign_id)
        if (not force_reload) and cached is not None and cached[0] == mtime:
            return cached[1]

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        log(f"skeleton: read failed for {path}: {e}")
        return None

    parsed = _parse_skeleton_text(text)

    with _cache_lock:
        _cache[campaign_id] = (mtime, parsed)

    log(f"skeleton: parsed campaign={campaign_id} "
        f"npcs={len(parsed['npcs'])} locations={len(parsed['locations'])} "
        f"factions={len(parsed['factions'])} hooks={len(parsed['hooks'])} "
        f"unknown_sections={parsed['unknown_sections']}")
    return parsed


def apply_starting_time_seed(campaign_id: int) -> dict:
    """Track 4 #3 — seed campaign clock from the optional `## Starting
    time` section in skeleton.md.

    Narrow §17 exception per §11.D=a + §J.3: campaign initialization
    writes directly to dnd_scene_state.campaign_day and day_phase, NOT
    through advance_time(), and does NOT append a row to
    dnd_time_advancements (initialization is not an advancement event).

    Idempotent guard: only fires when the existing scene_state row is
    at default-state `(campaign_day=1, day_phase='Morning')`. Re-running
    the loader on a campaign that has already advanced is a no-op (the
    skeleton declaration loses to lived state per §10).

    Returns:
      {
        'status':  'ok' | 'no_file' | 'parse_error' | 'no_section' |
                   'no_scene_state' | 'skipped_already_advanced',
        'day':     int | None,
        'phase':   str | None,
      }
    """
    out = {'status': 'ok', 'day': None, 'phase': None}
    try:
        parsed = parse_skeleton_file(campaign_id, force_reload=True)
    except SkeletonParseError as e:
        out['status'] = 'parse_error'
        log(f"apply_starting_time_seed: parse error campaign={campaign_id} "
            f"err={e!r}")
        return out
    if parsed is None:
        out['status'] = 'no_file'
        return out
    starting_time = parsed.get('starting_time')
    if not starting_time:
        out['status'] = 'no_section'
        return out
    day = starting_time.get('day')
    phase = starting_time.get('phase')
    # Lazy import to avoid circular: skeleton_loader is imported by
    # dnd_engine path consumers, but we only need engine helpers here.
    import sqlite3
    from dnd_engine import DB_PATH, get_scene_state, _now
    scene = get_scene_state(campaign_id)
    if scene is None:
        out['status'] = 'no_scene_state'
        log(f"apply_starting_time_seed: campaign={campaign_id} "
            f"err='no scene_state row' "
            f"(call init_scene_state first)")
        return out
    # Idempotency guard — skeleton seed is initialization-only. If the
    # campaign clock has already moved off defaults, skeleton declaration
    # loses (per §10 — scene_state wins on reload).
    if (scene.get('campaign_day') or 1) != 1 or (scene.get('day_phase') or 'Morning') != 'Morning':
        out['status'] = 'skipped_already_advanced'
        out['day'] = scene.get('campaign_day')
        out['phase'] = scene.get('day_phase')
        log(f"apply_starting_time_seed: campaign={campaign_id} "
            f"skipped (already at day={scene.get('campaign_day')} "
            f"phase={scene.get('day_phase')})")
        return out
    if day is None and phase is None:
        out['status'] = 'no_section'
        return out
    final_day = day if day is not None else 1
    final_phase = phase if phase is not None else 'Morning'
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "UPDATE dnd_scene_state SET campaign_day=?, day_phase=?, "
            "updated_at=? WHERE campaign_id=?",
            (final_day, final_phase, _now(), campaign_id)
        )
        conn.commit()
    finally:
        conn.close()
    out['day'] = final_day
    out['phase'] = final_phase
    log(f"apply_starting_time_seed: campaign={campaign_id} "
        f"seeded day={final_day} phase={final_phase!r}")
    return out


def apply_skeleton(campaign_id: int) -> dict:
    """Promote authored canon to the database.

    Writes locations FIRST so NPC location_hints can resolve to FK during
    the same call. Both go through the deterministic engine write paths
    with skeleton_origin=True.

    Returns:
      {
        'status':              'ok' | 'no_file' | 'parse_error',
        'error':               <str if parse_error>,
        'locations_written':   int,
        'npcs_written':        int,
        'parent_resolutions':  int,    # parent_hint → parent_location_id
        'location_resolutions': int,   # location_hint → location_id (NPC FK)
        'unresolved_parents':  list[str],
        'unresolved_npc_locations': list[str],
      }

    Idempotent: re-running on the same file lands the same authoritative
    state via the engine's skeleton-reload branch (npc_upsert /
    location_upsert).
    """
    result = {
        'status': 'ok',
        'error': '',
        'locations_written': 0,
        'npcs_written': 0,
        'parent_resolutions': 0,
        'location_resolutions': 0,
        'unresolved_parents': [],
        'unresolved_npc_locations': [],
    }

    try:
        parsed = parse_skeleton_file(campaign_id, force_reload=True)
    except SkeletonParseError as e:
        result['status'] = 'parse_error'
        result['error'] = str(e)
        log(f"apply_skeleton: parse error campaign={campaign_id} err={e!r}")
        return result

    if parsed is None:
        result['status'] = 'no_file'
        log(f"apply_skeleton: no skeleton file for campaign={campaign_id}")
        return result

    # Locations: two passes (mirrors discord_dnd_bot's parser approach).
    # Pass 1: insert/promote all rows. Pass 2: backfill parent_location_id
    # now that siblings exist.
    location_ids = {}  # canonical_name → id
    for loc in parsed['locations']:
        try:
            row_id = location_upsert(
                campaign_id=campaign_id,
                name=loc['name'],
                type=loc['type'],
                parent_location_id=None,
                description=loc['description'][:500] if loc['description'] else '',
                origin_excerpt=(loc['description'][:100] if loc['description'] else ''),
                skeleton_origin=True,
            )
            if row_id:
                # canonicalize the name same way the engine does, for lookup.
                canonical = canonicalize_location_name(loc['name'])
                location_ids[canonical] = row_id
                result['locations_written'] += 1
        except Exception as e:
            log(f"apply_skeleton: location_upsert error campaign={campaign_id} "
                f"name={loc['name']!r} err={e!r}")

    # Pass 2: parent backfill.
    for loc in parsed['locations']:
        parent_hint = loc.get('parent_hint', '')
        if not parent_hint:
            continue
        parent_canonical = canonicalize_location_name(parent_hint)
        parent_id = location_ids.get(parent_canonical)
        if parent_id is None:
            # Maybe a prior turn / prior load wrote it.
            try:
                existing = location_get_by_name(campaign_id, parent_hint)
            except Exception as e:
                log(f"apply_skeleton: location_get_by_name error: {e}")
                existing = None
            if existing is not None:
                parent_id = existing['id']
                location_ids[parent_canonical] = parent_id
        if parent_id is None:
            result['unresolved_parents'].append(
                f"{loc['name']} → {parent_hint}"
            )
            continue
        # Self-parent guard.
        own_canonical = canonicalize_location_name(loc['name'])
        if location_ids.get(own_canonical) == parent_id:
            continue
        try:
            location_upsert(
                campaign_id=campaign_id,
                name=loc['name'],
                parent_location_id=parent_id,
                skeleton_origin=True,
            )
            result['parent_resolutions'] += 1
        except Exception as e:
            log(f"apply_skeleton: location_upsert (parent backfill) error: {e}")

    # NPCs.
    for npc in parsed['npcs']:
        # Resolve location_hint to an id if possible.
        location_id = None
        hint = npc.get('location_hint', '')
        if hint:
            hint_canonical = canonicalize_location_name(hint)
            location_id = location_ids.get(hint_canonical)
            if location_id is None:
                try:
                    existing = location_get_by_name(campaign_id, hint)
                except Exception as e:
                    log(f"apply_skeleton: location_get_by_name error: {e}")
                    existing = None
                if existing is not None:
                    location_id = existing['id']
                    location_ids[hint_canonical] = location_id
            if location_id is None:
                result['unresolved_npc_locations'].append(
                    f"{npc['name']} → {hint}"
                )
            else:
                result['location_resolutions'] += 1

        try:
            upsert_result = npc_upsert(
                campaign_id=campaign_id,
                name=npc['name'],
                role=npc['role'],
                location_id=location_id,
                description=npc['description'][:500] if npc['description'] else '',
                origin_excerpt=(npc['description'][:100] if npc['description'] else ''),
                skeleton_origin=True,
            )
            if upsert_result:
                result['npcs_written'] += 1
        except Exception as e:
            log(f"apply_skeleton: npc_upsert error campaign={campaign_id} "
                f"name={npc['name']!r} err={e!r}")

    log(f"apply_skeleton: campaign={campaign_id} "
        f"locations_written={result['locations_written']} "
        f"npcs_written={result['npcs_written']} "
        f"parent_resolutions={result['parent_resolutions']} "
        f"location_resolutions={result['location_resolutions']} "
        f"unresolved_parents={result['unresolved_parents']} "
        f"unresolved_npc_locations={result['unresolved_npc_locations']}")
    return result


def get_skeleton_prompt_block(campaign_id: int, max_chars: int = 6000) -> str:
    """Return a prompt-ready injection block for dm_respond, or '' if no
    skeleton exists for this campaign. Sub-millisecond on cached path.

    Format mirrors the authored markdown (intentionally) so the LLM sees
    the same structure the human author wrote. Compressed somewhat — we
    drop body prose that exceeds a per-entry budget so a 200-word NPC
    bio doesn't dominate the prompt.

    Soft size budget per spec §12C: ~1500 tokens typical, ~4000 max. At
    ~4 chars/token, max_chars=6000 is the same ballpark. Truncates the
    block end-of-section if the budget would otherwise blow.
    """
    try:
        parsed = parse_skeleton_file(campaign_id)
    except SkeletonParseError as e:
        log(f"get_skeleton_prompt_block: parse error — falling back to no "
            f"skeleton injection. err={e!r}")
        return ""

    if parsed is None:
        return ""

    bits = []
    bits.append("═══════════════════════════════════════════════════════════════")
    bits.append("CAMPAIGN SKELETON (authored canon — authoritative)")
    bits.append("═══════════════════════════════════════════════════════════════")
    if parsed['title']:
        bits.append(f"# Campaign: {parsed['title']}")
        bits.append("")

    if parsed['central_conflict']:
        bits.append("## Central conflict")
        bits.append(parsed['central_conflict'])
        bits.append("")

    if parsed['hooks']:
        bits.append("## Major hooks")
        for h in parsed['hooks']:
            bits.append(f"- {h}")
        bits.append("")

    if parsed['npcs']:
        bits.append("## Primary NPCs")
        for n in parsed['npcs']:
            head = n['name']
            meta_bits = []
            if n['role']:
                meta_bits.append(n['role'])
            if n['location_hint']:
                meta_bits.append(n['location_hint'])
            if meta_bits:
                head += f" ({', '.join(meta_bits)})"
            bits.append(f"### {head}")
            if n['description']:
                # Per-entry budget: keep 400 chars of authored bio.
                bio = n['description']
                if len(bio) > 400:
                    bio = bio[:400].rstrip() + "..."
                bits.append(bio)
            bits.append("")

    if parsed['locations']:
        bits.append("## Key locations")
        for loc in parsed['locations']:
            head = loc['name']
            meta_bits = []
            if loc['type']:
                meta_bits.append(loc['type'])
            if loc['parent_hint']:
                meta_bits.append(f"in {loc['parent_hint']}")
            if meta_bits:
                head += f" ({', '.join(meta_bits)})"
            bits.append(f"### {head}")
            if loc['description']:
                desc = loc['description']
                if len(desc) > 300:
                    desc = desc[:300].rstrip() + "..."
                bits.append(desc)
            bits.append("")

    if parsed['factions']:
        bits.append("## Factions")
        for f in parsed['factions']:
            head = f['name']
            if f['type']:
                head += f" ({f['type']})"
            bits.append(f"### {head}")
            if f['description']:
                desc = f['description']
                if len(desc) > 300:
                    desc = desc[:300].rstrip() + "..."
                bits.append(desc)
            bits.append("")

    bits.append("═══════════════════════════════════════════════════════════════")
    bits.append(
        "Honor the skeleton above. Use these names, places, and motivations "
        "verbatim when relevant. Do NOT contradict authored canon. The "
        "skeleton is more reliable than any single retrieved memory."
    )
    bits.append("═══════════════════════════════════════════════════════════════")

    block = "\n".join(bits)
    if len(block) > max_chars:
        # Hard truncate at the budget boundary, mark explicitly.
        block = block[:max_chars].rstrip() + "\n\n[skeleton truncated to fit prompt budget]"
    return block


# ─────────────────────────────────────────────────────────
# S9 — Player capabilities accessor
# ─────────────────────────────────────────────────────────
# Thin accessor for the orchestration layer. Wraps parse_skeleton_file
# and returns just the player_capabilities map, with capability strings
# validated against the v1 weapon-family list. Unknown families are
# logged and dropped (Q3 — log warning, don't fail).
#
# This is the boundary that lets us swap skeleton → DDB later without
# touching the rules engine. dnd_orchestration imports nothing from
# skeleton_loader; dm_respond fetches capabilities from this accessor
# and passes them down. Clean layered architecture: data source →
# orchestration → rules engine.

def get_player_capabilities(campaign_id: int) -> dict[str, set[str]]:
    """Return the per-character capability hint map from skeleton.md.

    Returns a `dict[str, set[str]]` mapping character display name
    (as written in the skeleton) to the set of weapon-family
    categories the author has declared the character known to wield.

    Capability strings are filtered against the v1 weapon-family list
    (`WEAPON_CAPABILITIES.category` names from `dnd_orchestration`).
    Unknown families are dropped from the returned map and a warning
    is logged so the author can grep `journalctl` and find typos.

    Returns `{}` (empty dict) on any of:
      - skeleton.md doesn't exist for this campaign
      - skeleton.md fails to parse (the parse error is logged
        elsewhere by parse_skeleton_file's caller)
      - skeleton.md has no `## Player Capabilities` section
      - all declared capabilities were unknown (filtered out)

    Empty dict is the safe default — orchestration treats it as
    "no skeleton hints available" and continues to default unmatched
    claims to VALID_BUT_UNCONFIGURED.
    """
    # weapon_schema is the neutral taxonomy module (Session 15 extraction).
    # Both dnd_orchestration and skeleton_loader depend on it; neither
    # depends on the other for capability data. Future DDB ingestion
    # joins as a third consumer.
    from weapon_schema import WEAPON_CAPABILITIES
    # Specific-item grounding (Session 13 locked spec): authors can
    # declare either a family-level generic ("sword") OR a specific
    # item ("shortsword"). The valid set is the UNION of family
    # category names and all their aliases.
    valid_items: set[str] = set()
    for wc in WEAPON_CAPABILITIES:
        valid_items.add(wc.category)
        for a in wc.aliases:
            valid_items.add(a.lower())

    parsed = parse_skeleton_file(campaign_id)
    if parsed is None:
        return {}

    raw = parsed.get('player_capabilities') or {}
    if not raw:
        return {}

    filtered: dict[str, set[str]] = {}
    for name, declared in raw.items():
        valid = declared & valid_items
        unknown = declared - valid_items
        if unknown:
            log(f"skeleton_capabilities: campaign={campaign_id} "
                f"character={name!r} unknown_items={sorted(unknown)} "
                f"(must be one of: {sorted(valid_items)})")
        if valid:
            filtered[name] = valid
    return filtered
