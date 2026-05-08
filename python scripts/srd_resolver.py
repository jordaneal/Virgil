"""SRD monster resolver — Track 6 #5.1.

Pure function core. No DB access, no Discord, no dnd_engine imports beyond log.
Single entry point: resolve(creature_name, campaign_id) → SRDResult | None.

Doctrine §1b anchor: LLM proposes a candidate; _MONSTER_INDEX validates the
candidate exists in the SRD; confidence gate enforces the threshold; DM approves
by typing the suggested command. LLM never decides anything mechanically.

Doctrinal lineage: §12 advisory parser shape (logs internally, no signals
returned), §1b validated-suggester semantics, §59 telemetry discipline
(always-fire, soft-fail at call site in discord_dnd_bot.py).

Telemetry (two-line shape on success path):
  resolve() emits: method=exact/fuzzy/llm/miss/dedup, posted=0
  _post_srd_suggestion() emits: posted=1 after Discord send completes
  Miss/dedup paths: one line from resolve() only.
"""

import dataclasses
import json
import os
import re

from cloud_router import route
from dnd_engine import log


# ─────────────────────────────────────────────────────────
# Module state (process-lifetime)
# ─────────────────────────────────────────────────────────

_INDEX_PATH = os.path.join(os.path.dirname(__file__), "srd_monsters.json")

_MONSTER_INDEX: dict[str, dict] = {}       # lowercased-name → entry
_SUGGESTED: set[tuple[int, str]] = set()   # (campaign_id, name_lower) session dedup
_LLM_CACHE: dict[str, tuple[str, float] | None] = {}  # name_lower → (candidate, conf)

_JACCARD_THRESHOLD = 0.6
_CONFIDENCE_THRESHOLD = 0.65


def _load_index() -> None:
    """Load srd_monsters.json into _MONSTER_INDEX at import time."""
    global _MONSTER_INDEX
    try:
        with open(_INDEX_PATH, encoding="utf-8") as f:
            raw = json.load(f)
        # Filter out _meta key — it's not a monster
        _MONSTER_INDEX = {k: v for k, v in raw.items() if k != "_meta"}
        log(f"srd_resolver: index loaded entries={len(_MONSTER_INDEX)} path={_INDEX_PATH}")
    except Exception as e:
        _MONSTER_INDEX = {}
        log(f"srd_resolver: index load failed path={_INDEX_PATH} err={e!r} — all resolves will miss")


_load_index()


# ─────────────────────────────────────────────────────────
# Result type
# ─────────────────────────────────────────────────────────

@dataclasses.dataclass
class SRDResult:
    input_name:  str    # creature name from narration
    srd_name:    str    # matched SRD monster name (display/title-case)
    cr:          str    # CR as string: '0','1/8','1/4','1/2','1','2',...
    hp:          int    # average HP from SRD stat block
    ac:          int    # base AC from SRD stat block
    confidence:  float  # 1.0 for exact, Jaccard score for fuzzy, LLM score for llm
    method:      str    # 'exact' | 'fuzzy' | 'llm'


# ─────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────

def resolve(creature_name: str, campaign_id: int) -> "SRDResult | None":
    """Resolve creature_name to an SRD entry, or return None.

    Resolution order: exact → Jaccard fuzzy → LLM (§1b).
    Always fires a srd_suggestion: telemetry log line (posted=0 from here;
    posted=1 emitted separately by _post_srd_suggestion on success).

    Session dedup: once (campaign_id, name_lower) is in _SUGGESTED, returns
    None without re-posting. was_new=False in npc_upsert is the primary
    guard; _SUGGESTED is secondary protection within one process lifetime.
    """
    name_lower = creature_name.lower().strip()

    # Session dedup (secondary guard — was_new=False is primary, see §6)
    if (campaign_id, name_lower) in _SUGGESTED:
        log(f"srd_suggestion: campaign={campaign_id} input={creature_name!r} "
            f"candidate=none cr=none confidence=none method=dedup posted=0")
        return None

    # (a) Exact key match
    entry = _MONSTER_INDEX.get(name_lower)
    if entry:
        return _build_and_mark(creature_name, entry, 1.0, "exact", campaign_id)

    # (b) Jaccard token-overlap fuzzy match
    fuzzy = _fuzzy_match(name_lower)
    if fuzzy:
        entry, score = fuzzy
        return _build_and_mark(creature_name, entry, score, "fuzzy", campaign_id)

    # (c) LLM suggester — §1b: propose → validate → gate
    # try/except here is defense-in-depth: _llm_suggest already catches
    # internally, but resolve() must never propagate any exception upward.
    try:
        llm = _llm_suggest(creature_name)
    except Exception:
        llm = None
    if llm:
        candidate, confidence = llm
        entry = _MONSTER_INDEX.get(candidate.lower().strip())  # deterministic validator gate
        if entry and confidence >= _CONFIDENCE_THRESHOLD:
            return _build_and_mark(creature_name, entry, confidence, "llm", campaign_id)

    # Miss
    log(f"srd_suggestion: campaign={campaign_id} input={creature_name!r} "
        f"candidate=none cr=none confidence=none method=miss posted=0")
    return None


# ─────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────

def _build_and_mark(
    creature_name: str,
    entry: dict,
    confidence: float,
    method: str,
    campaign_id: int,
) -> SRDResult:
    """Construct SRDResult, mark dedup, emit resolver telemetry (posted=0)."""
    name_lower = creature_name.lower().strip()
    _SUGGESTED.add((campaign_id, name_lower))

    result = SRDResult(
        input_name=creature_name,
        srd_name=entry["name"],
        cr=entry["cr"],
        hp=int(entry["hp"]),
        ac=int(entry["ac"]),
        confidence=confidence,
        method=method,
    )
    log(f"srd_suggestion: campaign={campaign_id} input={creature_name!r} "
        f"candidate={entry['name']!r} cr={entry['cr']!r} "
        f"confidence={confidence:.2f} method={method} posted=0")
    return result


def _fuzzy_match(name_lower: str) -> "tuple[dict, float] | None":
    """Jaccard token-overlap fuzzy match across all _MONSTER_INDEX keys.

    Returns (entry, score) for the highest-scoring key above
    _JACCARD_THRESHOLD, or None.

    Token sets are order-insensitive: 'swarm bats' and 'bats swarm' produce
    identical token sets and identical Jaccard scores against any SRD key.
    """
    tokens = set(name_lower.split())
    if not tokens:
        return None
    best_score, best_entry = 0.0, None
    for key, entry in _MONSTER_INDEX.items():
        key_tokens = set(key.split())
        union = tokens | key_tokens
        if not union:
            continue
        score = len(tokens & key_tokens) / len(union)
        if score >= _JACCARD_THRESHOLD and score > best_score:
            best_score, best_entry = score, entry
    return (best_entry, best_score) if best_entry else None


_LLM_SYSTEM = """\
You are a D&D 5e expert. Given a creature name from DM narration,
identify the closest monster in the 5e System Reference Document (SRD).

Output ONLY a JSON object: {"candidate": "exact SRD name", "confidence": float}

Rules:
- candidate must be an exact 5e SRD monster name (e.g. "Giant Frog", not "Large Frog")
- confidence: 0.0–1.0 reflecting how well the input maps to the SRD monster
- If no reasonable SRD match exists: {"candidate": "", "confidence": 0.0}
- Do not invent names. Only use names from the 5e SRD.

Examples:
  "Spiny Toad"     → {"candidate": "Giant Frog",      "confidence": 0.75}
  "Forest Spider"  → {"candidate": "Giant Spider",     "confidence": 0.80}
  "Cave Bat"       → {"candidate": "Swarm of Bats",    "confidence": 0.65}
  "Goblin Captain" → {"candidate": "Goblin Boss",      "confidence": 0.85}
  "Fog Wraith"     → {"candidate": "Wraith",           "confidence": 0.60}
  "XyzPlorp"       → {"candidate": "",                 "confidence": 0.00}\
"""


def _llm_suggest(creature_name: str) -> "tuple[str, float] | None":
    """Call cloud_router for an LLM-suggested SRD candidate name.

    Returns (candidate_name, confidence) or None.
    Only caches DEFINITIVE LLM responses. Transient failures (network,
    timeout, parse error) do NOT write to _LLM_CACHE — next encounter
    of the same creature will retry. This prevents cache poisoning from
    one-time hiccups (§F.2 fix, Session 2 review doc).
    """
    key = creature_name.lower().strip()
    if key in _LLM_CACHE:
        return _LLM_CACHE[key]

    try:
        response, _ = route(
            messages=[{"role": "user", "content": f"Creature name: {creature_name}"}],
            task_type="extraction",
            system_prompt=_LLM_SYSTEM,
        )
        # Strip markdown fences if present
        body = (response or "").strip()
        if body.startswith("```"):
            body = re.sub(r"^```(?:json)?\s*", "", body)
            body = re.sub(r"\s*```$", "", body.strip())

        parsed = json.loads(body or "{}")
        candidate = str(parsed.get("candidate", "")).strip()
        confidence = float(parsed.get("confidence", 0.0))
        result: "tuple[str, float] | None" = (candidate, confidence) if candidate else None

        # Cache only definitive responses (including genuine no-match empty string)
        _LLM_CACHE[key] = result
        return result

    except Exception as e:
        # Transient failure — do NOT cache; allow retry on next encounter
        log(f"srd_resolver: llm_suggest error creature={creature_name!r} err={e!r}")
        return None
