"""Consequence extractor — dual-pass advisory parser (Session 16).

Reads player text and DM narration in SEPARATED CHANNELS, returns lists
of candidate consequence records the engine MAY persist via
apply_consequence_proposals(). Suggestion-only — never writes directly.

Public API:
    parse_consequences_player(player_text: str) -> list[dict]
    parse_consequences_dm(dm_text: str) -> list[dict]

Each output dict has the canonical four-key shape:
    {
      "target":   <canonical NPC name as the parser saw it>,
      "kind":     <one of: threat, mercy, cruelty, betrayal, promise, alliance>,
      "severity": <int 1, 2, or 3 — parser judgment>,
      "summary":  <imperative phrase, ≤120 chars>,
    }

Hard invariants (CONSEQUENCE_SURFACING_SPEC §1, §5):
- Dual-pass with separated channels — never blend player + DM text.
  The single-blended parser failure mode (self-reinforcing hallucination
  loop) is the design rejection. Each parser sees ONE channel only.
- Kind taxonomy locked at 6. The definitions in the prompt are verbatim
  per §1.3 and must not be paraphrased.
- Severity is parser judgment 1-3, MAX-on-upsert at the engine layer.
- Shape validation only here. Canonical NPC resolution and
  PC-contamination guard happen in dnd_engine.apply_consequence_proposals.
- High-precision / low-recall prompts. When uncertain, return [].
- Never raises — returns [] on any failure.
"""

import json
import re
import time

from cloud_router import route
from dnd_engine import (
    log,
    CONSEQUENCE_KINDS, CONSEQUENCE_SEVERITIES, CONSEQUENCE_SUMMARY_MAX,
)


# ─────────────────────────────────────────────────────────
# Validator
# ─────────────────────────────────────────────────────────

# Shell metas + control characters. Refused anywhere in target/summary.
_BAD_CHARS = re.compile(r"[`;|&><$\\\n\r]")

_PROPOSAL_KEYS = ("target", "kind", "severity", "summary")


def _normalize_proposal(raw):
    """Coerce an LLM-emitted dict into the canonical 4-key shape.
    Strips whitespace; coerces non-string values; coerces severity to int.
    Returns dict or None on bad shape.
    """
    if not isinstance(raw, dict):
        return None

    target = raw.get("target", "")
    kind = raw.get("kind", "")
    severity = raw.get("severity", None)
    summary = raw.get("summary", "")

    if not isinstance(target, str):
        target = ""
    if not isinstance(kind, str):
        kind = ""
    if not isinstance(summary, str):
        summary = ""

    target = target.strip()
    kind = kind.strip().lower()
    summary = summary.strip()

    try:
        sev_int = int(severity) if severity is not None else None
    except (TypeError, ValueError):
        sev_int = None

    return {
        "target":   target,
        "kind":     kind,
        "severity": sev_int,
        "summary":  summary,
    }


def _validate_proposal(p):
    """Return (valid: bool, drop_reason: str | None).

    drop_reason is one of:
      bad_shape         — not a dict, or missing fields
      empty_target      — target string is empty
      invalid_kind      — kind not in the locked 6
      severity_missing  — severity is None / unparseable
      severity_oob      — severity not in {1, 2, 3}
      summary_empty     — summary empty after strip
      summary_too_long  — summary exceeds CONSEQUENCE_SUMMARY_MAX chars
      bad_chars         — shell metas or control chars in target or summary
    """
    if not isinstance(p, dict):
        return False, "bad_shape"
    for k in _PROPOSAL_KEYS:
        if k not in p:
            return False, "bad_shape"

    target = p.get("target", "")
    if not target:
        return False, "empty_target"
    if _BAD_CHARS.search(target):
        return False, "bad_chars"

    kind = p.get("kind", "")
    if kind not in CONSEQUENCE_KINDS:
        return False, "invalid_kind"

    sev = p.get("severity")
    if sev is None:
        return False, "severity_missing"
    if sev not in CONSEQUENCE_SEVERITIES:
        return False, "severity_oob"

    summary = p.get("summary", "")
    if not summary:
        return False, "summary_empty"
    if len(summary) > CONSEQUENCE_SUMMARY_MAX:
        return False, "summary_too_long"
    if _BAD_CHARS.search(summary):
        return False, "bad_chars"

    return True, None


def _extract_raw_array(text):
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


# ─────────────────────────────────────────────────────────
# OOC contamination guard — player-channel only (S21)
# ─────────────────────────────────────────────────────────

# Leading-position-only markers. Mid-message OOC (e.g. "I attack ((wait BRB))")
# is intentionally NOT covered in v1 — span-stripping is a different shape and
# we don't yet know if mid-message OOC is common enough to need it.
#
# DM parser is unaffected: dm_text comes from the LLM, not from players. OOC
# contamination there would be the LLM violating its own role — a different
# problem than this filter solves.
_OOC_MARKER_PATTERNS = [
    ('paren',   re.compile(r'^\s*\(\(')),                        # (( IRC convention
    ('bracket', re.compile(r'^\s*\[OOC\]', re.IGNORECASE)),       # [OOC]
    ('colon',   re.compile(r'^\s*OOC:',    re.IGNORECASE)),       # OOC:
    ('slash',   re.compile(r'^\s*//')),                           # //
]


def _check_ooc_marker(text):
    """Return marker name if text starts with a known OOC marker, else None.

    Markers checked: '((', '[OOC]' (case-insensitive), 'OOC:' (case-insensitive),
    '//'. All allow leading whitespace. Mid-message markers are not detected.
    """
    if not text or not isinstance(text, str):
        return None
    for name, pattern in _OOC_MARKER_PATTERNS:
        if pattern.match(text):
            return name
    return None


# ─────────────────────────────────────────────────────────
# System prompts — kind definitions LOCKED (spec §1.3, §5.2)
# ─────────────────────────────────────────────────────────

# Verbatim definitions used in BOTH parser prompts. Per §1.3 these must
# not be paraphrased — load-bearing for parser consistency.
KIND_DEFINITIONS_BLOCK = """The six consequence kinds (use exactly these words; no synonyms):
  - threat:   credible future harm or pressure (not executed action)
  - mercy:    restraint when harm was available
  - cruelty:  harm exceeding necessity
  - betrayal: violation of trust/expectation
  - promise:  explicit commitment affecting future state
  - alliance: mutual alignment / shared objective formation"""

SEVERITY_BLOCK = """Severity is your judgment of weight (return 1, 2, or 3):
  - 1: minor / implied / scene-bound — small in stakes, easily forgotten
  - 2: notable / direct / scene-shifting — clearly changes the NPC's standing
  - 3: major / paradigm-shifting / plot-defining — campaign-level weight"""


PLAYER_SYSTEM_PROMPT = f"""You read player turns from a Dungeons & Dragons game and extract
CONSEQUENCES the player initiated against named NPCs — commitments, social
acts, and acts performed against a specific NPC that the world should
remember.

Output ONLY a JSON array. No prose. No markdown. Empty array [] if no
consequence was clearly initiated by the player against a named NPC.

Each object MUST have exactly these four keys:
  "target":   the NPC's name as it appears in the player's text (proper noun)
  "kind":     one of the six locked kinds below
  "severity": integer 1, 2, or 3
  "summary":  short imperative phrase, ≤120 chars, describing what the player did

{KIND_DEFINITIONS_BLOCK}

{SEVERITY_BLOCK}

THE PRECISION RULE (the only rule that matters):
  When uncertain, OMIT. Better to miss a real consequence than fabricate one.
  Most player turns produce ZERO consequences. That is correct behavior.

What survives capture (KEEP):
  - Player's explicit threat against a named NPC: "I'll burn your inn down, Reginald."
  - Player's explicit mercy: "I lower my blade. Live, Lira. But never come back."
  - Player's explicit cruelty: "I strike Kael down even as he kneels."
  - Player's explicit promise: "Reginald, I'll bring you the artifact."
  - Player's explicit betrayal: "I take Thorne's coin and leave without delivering."
  - Player's explicit alliance: "I swear to defend you, Lira, with my blade."

What fails the rule (OMIT):
  - Player addresses no named NPC (only the DM, the world, themselves)
  - Player narrates intent but doesn't act ("I want to leave" — not a consequence)
  - Generic combat actions without commitment-bearing weight ("I attack the goblin")
  - Roleplay banter, jokes, or hypothetical statements without commitment
  - Player thinks about doing something but doesn't (no commitment)
  - Acts against unnamed entities ("the guard", "the bandit")

Output rules:
  - "target": exact name as the player typed it (proper noun, may include title)
  - "kind": exactly one of the six lowercase strings (threat, mercy, cruelty,
    betrayal, promise, alliance). No synonyms, no paraphrases.
  - "severity": integer judgment 1-3
  - "summary": ≤120 chars, imperative phrase like "player threatened to burn the inn down"

Example: "I tell Reginald I'll torch his inn if he speaks of us."
Output: [{{"target": "Reginald", "kind": "threat", "severity": 2, "summary": "player threatened to torch the inn if he speaks of their visit"}}]

Example: "I lower the blade. Lira, you can go."
Output: [{{"target": "Lira", "kind": "mercy", "severity": 2, "summary": "player spared Lira when she was at his mercy"}}]

Example: "I tell Thorne I'll deliver the package by week's end."
Output: [{{"target": "Thorne", "kind": "promise", "severity": 1, "summary": "player promised to deliver the package by week's end"}}]

Example: "I swing at the goblin."
Output: []

Example: "I look around the room."
Output: []

Example: "What's the DC on this?"
Output: []"""


DM_SYSTEM_PROMPT = f"""You read DM narration from a Dungeons & Dragons game and extract
CONSEQUENCES that the DM's narration established about a named NPC's
relationship to the player — world reactions, fallout, environmental
shifts the DM described, AND alignments or commitments the NPC made in
response to player action.

Output ONLY a JSON array. No prose. No markdown. Empty array [] if no
consequence emerged from the DM's narration.

Each object MUST have exactly these four keys:
  "target":   the NPC's name as it appears in the DM's narration
  "kind":     one of the six locked kinds below
  "severity": integer 1, 2, or 3
  "summary":  short imperative phrase, ≤120 chars

{KIND_DEFINITIONS_BLOCK}

{SEVERITY_BLOCK}

CRITICAL — DO NOT RE-CAPTURE PLAYER COMMITMENTS:
  A separate parser captures player-initiated consequences. Your job is
  ONLY to capture consequences that emerged from the DM's narration —
  NPC reactions, world fallout, NPC-side commitments. If the DM is
  merely describing the visible result of a player action, that is the
  same event as the player's commitment, and it has ALREADY been
  captured by the player parser. OMIT it.

THE PRECISION RULE:
  When uncertain, OMIT. Better to miss a real consequence than to
  inflate one event into two captures.

What survives capture (KEEP):
  - DM-narrated NPC alliance NPC offered without player explicitly asking:
    "Lira clasps your forearm: 'Whatever you ask, you have it.'" (alliance)
  - DM-narrated NPC betrayal of trust the player gave:
    "Reginald sells your location to the constables." (betrayal)
  - DM-narrated NPC mercy toward the player when player was at NPC's mercy:
    "Kael lowers his sword. 'Go. Don't make me hunt you down.'" (mercy)
  - DM-narrated NPC cruelty after the player has been disarmed/captured:
    "Thorne kicks you while you are bound. The crowd laughs." (cruelty)
  - DM-narrated NPC threat NPC made in response to the scene:
    "Garrick's hand rests on his hilt. 'Come back here, and I'll kill you myself.'" (threat)
  - DM-narrated NPC promise NPC made on their own initiative:
    "Mira: 'I'll have the room ready by sundown. You have my word.'" (promise)

What fails the rule (OMIT):
  - DM is just describing what the player already did (player parser handles)
  - Generic atmospheric description without NPC-specific consequence
  - DM describing world events not tied to a specific named NPC's reaction
  - NPC actions inside combat that are mechanical, not commitment-bearing
  - DM continuing established NPC posture from prior turns (already captured)

Output rules same as the player parser:
  - "target": exact name as the DM wrote it
  - "kind": exactly one of the six lowercase strings
  - "severity": integer 1-3, your judgment of weight
  - "summary": ≤120 chars, imperative phrase like "Reginald sold the players to the constables"

Example: "Lira sheathes her blade and clasps your hand. 'Wherever you go, I follow.'"
Output: [{{"target": "Lira", "kind": "alliance", "severity": 2, "summary": "Lira swore to follow the player wherever they go"}}]

Example: "Reginald nods and walks calmly to the back room. Moments later, the constables arrive."
Output: [{{"target": "Reginald", "kind": "betrayal", "severity": 3, "summary": "Reginald sold the players out to the constables"}}]

Example: "The guard moves aside, letting you pass. The market bustles around you."
Output: []

Example: "Kael's blade catches yours. He attacks again."
Output: []"""


# ─────────────────────────────────────────────────────────
# Parser entry points
# ─────────────────────────────────────────────────────────

def _parse_pass(text, system_prompt, channel_label):
    """Shared body for both passes. Calls route(), parses JSON, validates,
    returns list of validated proposals.

    channel_label is the source tag used in log lines ('player' or 'dm').
    Never raises.
    """
    if not text or not isinstance(text, str):
        return []

    started = time.monotonic()
    raw_response = ""
    validated = []
    dropped = []

    try:
        response, _provider = route(
            messages=[{"role": "user", "content": text}],
            task_type="extraction",
            system_prompt=system_prompt,
        )
        raw_response = response or ""

        candidates = _extract_raw_array(raw_response)
        if candidates is None:
            log(f"consequence_parse: source={channel_label} "
                f"text_chars={len(text)} parse_failed "
                f"raw_response={raw_response[:160]!r} "
                f"latency_ms={int((time.monotonic() - started) * 1000)}")
            return []

        seen_keys = set()
        for cand in candidates:
            normalized = _normalize_proposal(cand)
            if normalized is None:
                dropped.append(("?", "bad_shape"))
                continue
            ok, reason = _validate_proposal(normalized)
            if not ok:
                dropped.append((normalized.get("target", "?")[:40], reason or "unknown"))
                continue
            # Single-text de-dup. Same (target, kind) twice in one parse =
            # redundant; keep the first.
            key = (normalized["target"].lower(), normalized["kind"])
            if key in seen_keys:
                dropped.append((normalized["target"][:40], "duplicate_in_text"))
                continue
            seen_keys.add(key)
            validated.append(normalized)
    except Exception as e:
        log(f"consequence_parse: source={channel_label} error={e!r} "
            f"latency_ms={int((time.monotonic() - started) * 1000)}")
        return []

    log(f"consequence_parse: source={channel_label} "
        f"text_chars={len(text)} "
        f"validated={[(p['target'], p['kind']) for p in validated]} "
        f"dropped={[f'{t}:{r}' for t, r in dropped]} "
        f"latency_ms={int((time.monotonic() - started) * 1000)}")
    return validated


def parse_consequences_player(player_text, campaign_id=None):
    """Parse player_text for player-initiated consequences against named NPCs.

    Returns list of validated proposals. Never raises. Empty list on any
    failure (empty input, route exception, parse failure, all candidates
    invalid).

    OOC contamination guard (S21): leading-position OOC markers ((, [OOC],
    OOC:, //) short-circuit the parser — no LLM call, returns []. Logs
    `consequence_ooc_filtered: campaign={N} reason={marker} text='{first 80}'`
    so log analysis can tell which marker shape is common in real play.
    """
    marker = _check_ooc_marker(player_text)
    if marker is not None:
        snippet = (player_text or "")[:80].replace("\n", " ").replace("\r", " ")
        camp_str = campaign_id if campaign_id is not None else '?'
        log(f"consequence_ooc_filtered: campaign={camp_str} "
            f"reason={marker} text={snippet!r}")
        return []
    return _parse_pass(player_text, PLAYER_SYSTEM_PROMPT, channel_label="player")


def parse_consequences_dm(dm_text):
    """Parse dm_text for DM-narrated consequences (world reactions, fallout,
    NPC-side commitments). Returns list of validated proposals.

    Tries to avoid re-capturing player commitments — that's the player
    parser's job. Never raises.
    """
    return _parse_pass(dm_text, DM_SYSTEM_PROMPT, channel_label="dm")
