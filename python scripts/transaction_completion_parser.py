"""S78 — Inversion v0 Phase 3b: transaction-completion narration-detection parser.

Closed-vocab parser per §1a.x — detects transaction-completion intent across
player narrative AND LLM completion text. Two surfaces (`pre_llm` for player
intent like "I pay Garrick 5gp"; `post_llm` for LLM paraphrase like "Garrick
pockets the gold"). Both register against the §1b.1 aggregator.

Per §1a.x prerequisites:
  1. Closed verb frozenset — no LLM classification.
  2. Structured-signal co-occurrence — verb + currency value + NPC name match.
  3. Engine-side writer remains §17-disciplined — parser produces structured
     proposal; the existing `/coin` slash is the operator-paste gate; engine
     writers (transaction-side state) fire on operator approval.
  4. Three-tier confidence with §1b.1 markers_present discrimination.

Three-tier routing per S77 §1b.1 lock:
  HIGH: verb + currency value + NPC name token-match — SINGLE_DOMAIN_CLEAR
        through existing Phase 3a path (suggester card to #dm-aside, operator
        paste fires engine writer).
  MEDIUM-with-markers: verb + EITHER currency OR NPC (not both) — sets
        markers_present=True. Aggregator routes to IN_FICTION_CLARIFICATION
        (M-DELAYED primary): engine sets pending_clarification, LLM narrates
        scene continuing without finalizing, parser second-pass on operator's
        next utterance.
  MEDIUM-no-markers: verb only, no co-occurring signals — markers_present=False.
        Aggregator routes to SINGLE_DOMAIN_CLEAR (Phase 3a-style medium tier).
  LOW: dedup-suppressed or below-threshold — silent, telemetry-only.

Doctrinal composition with §11.6 N-1 (mechanical_hints) resolution:
  R3 lock at S78: (c) surface-separated. N-1 stays unchanged — its output
  surfaces Avrae bookkeeping commands as bullets on the DM narration embed
  via `_attach_hints`. This parser surfaces transactions to the §1b.1
  aggregator for clarification routing. Vocabulary overlap is incidental
  (both detect "pay"/"hand"/"gave"); downstream pipelines are non-overlapping.
  Recon report `planner-scratch/PHASE3B_RECON_REPORT.md` documents the
  reasoning.

NAMING per S77 convention: `transaction_completion_parser` to disambiguate
from N-1's `mechanical_hints` (advisory parser, pre-§1a.x, LLM-extraction).
This parser is §1a.x-disciplined narration-detection.
"""

from __future__ import annotations

import collections
import re
from typing import Literal, Optional


# ── Closed verb vocabulary ─────────────────────────────────────────────────
#
# Whole-word lowercase match. Per S73.1 vocabulary-paraphrase lesson, both
# player-side (pre-LLM input) and LLM-side (post-LLM completion) variants
# are included with full tense coverage.
#
# Player-intent verbs: actions the player narrates as their intent.
# LLM-completion verbs: actions the LLM paraphrases as transaction completion.
# Overlap is by design — many verbs work in both surfaces.

_PLAYER_INTENT_VERBS = frozenset({
    # Buy / pay / pay-for forms
    'pay', 'pays', 'paid', 'paying',
    'purchase', 'purchases', 'purchased', 'purchasing',
    'buy', 'buys', 'bought', 'buying',
    # Give / hand / hand-over forms
    'give', 'gives', 'gave', 'giving',
    'hand', 'hands', 'handed', 'handing',
    'offer', 'offers', 'offered', 'offering',
    'spend', 'spends', 'spent', 'spending',
})

_LLM_COMPLETION_VERBS = frozenset({
    # Receive / take / pocket forms (LLM paraphrase of NPC accepting)
    'pockets', 'pocketed', 'pocketing', 'pocket',
    'accepts', 'accepted', 'accepting', 'accept',
    'receives', 'received', 'receiving', 'receive',
    'takes', 'took', 'taking',
    'collects', 'collected', 'collecting', 'collect',
    'tucks', 'tucked', 'tucking', 'tuck',
    # Exchange / hand-over forms (mutual)
    'exchanges', 'exchanged', 'exchanging', 'exchange',
    'slides', 'slid', 'sliding',
    'passes', 'passed', 'passing',
})

# Phrasal verbs — matched as ordered subsequence on whole-word token list.
_PHRASAL_VERBS = frozenset({
    ('pay', 'for'),
    ('pays', 'for'),
    ('paid', 'for'),
    ('hand', 'over'),
    ('hands', 'over'),
    ('handed', 'over'),
    ('give', 'to'),
    ('gives', 'to'),
    ('gave', 'to'),
    ('hand', 'to'),
    ('hands', 'to'),
    ('handed', 'to'),
    ('takes', 'the', 'coin'),
    ('takes', 'the', 'gold'),
    ('takes', 'the', 'silver'),
    ('pockets', 'the', 'coin'),
    ('pockets', 'the', 'gold'),
})


_TOKEN_RE = re.compile(r"[a-zA-Z']+")

# Currency value regex — captures the numeric amount + denomination.
_CURRENCY_RE = re.compile(
    r"\b(\d+)\s*(gp|sp|cp|ep|pp|gold|silver|copper|electrum|platinum)\b",
    re.IGNORECASE,
)


# ── Cross-turn dedup ──────────────────────────────────────────────────────
# Per-campaign LRU. N=3 window matches quest_acceptance_parser default.
_RECENT_FIRES_PER_CAMPAIGN: dict[int, collections.deque] = {}
_DEDUP_WINDOW = 3

FEATURE_DISABLED = False


# ── Confidence-tier names ─────────────────────────────────────────────────
CONFIDENCE_HIGH = 'high'
CONFIDENCE_MEDIUM = 'medium'
CONFIDENCE_LOW = 'low'

# Surface names per S77 §1b.1 ParserResult disambiguation.
SURFACE_PRE_LLM = 'pre_llm'
SURFACE_POST_LLM = 'post_llm'


# ── Tokenization ──────────────────────────────────────────────────────────

def _tokens(text: str) -> list[str]:
    """Whole-word lowercase tokens; preserves contractions."""
    return [t.lower() for t in _TOKEN_RE.findall(text or '')]


def _has_verb(tokens: list[str], surface: str) -> tuple[bool, str]:
    """Return (matched, verb) for the first match. surface picks which
    vocabulary set takes priority — pre-LLM checks player-intent first;
    post-LLM checks LLM-completion first.

    Phrasals checked FIRST so longer-specific matches ("pay for") win
    over their single-verb prefixes ('pay'). Falls back to single-token
    match if no phrasal hits.
    """
    if surface == SURFACE_PRE_LLM:
        primary = _PLAYER_INTENT_VERBS
        secondary = _LLM_COMPLETION_VERBS
    else:
        primary = _LLM_COMPLETION_VERBS
        secondary = _PLAYER_INTENT_VERBS

    # Phrasal subsequence — checked first so "pay for" wins over "pay".
    n = len(tokens)
    for phrase in _PHRASAL_VERBS:
        plen = len(phrase)
        if plen > n:
            continue
        for i in range(n - plen + 1):
            if tuple(tokens[i:i + plen]) == phrase:
                return True, ' '.join(phrase)

    # Single-token fallback
    for t in tokens:
        if t in primary:
            return True, t
    for t in tokens:
        if t in secondary:
            return True, t
    return False, ''


# ── Structured-signal detectors ───────────────────────────────────────────


def _find_currency(narration: str) -> Optional[dict]:
    """Match the first currency value in narration. Returns dict with
    `amount` (int) + `denom` (str) or None.
    """
    m = _CURRENCY_RE.search(narration or '')
    if not m:
        return None
    try:
        amount = int(m.group(1))
    except ValueError:
        return None
    return {'amount': amount, 'denom': m.group(2).lower()}


_NPC_STOPWORDS = frozenset({
    'a', 'an', 'the', 'of', 'and', 'to', 'in', 'for', 'on', 'with',
})


def _find_npc(tokens: list[str], recent_npcs: list[str]) -> Optional[str]:
    """Whole-token match of any recently-active NPC's canonical_name
    against narration tokens. Returns the NPC name or None.

    Multi-token NPC names (e.g. "Ser Aldrich") match if any non-stopword
    content token of the name appears in the narration. Per
    quest_acceptance_parser._title_tokens stopword convention.
    """
    if not recent_npcs or not tokens:
        return None
    narration_set = set(tokens)
    for name in recent_npcs:
        if not name:
            continue
        name_tokens = [
            t.lower() for t in _TOKEN_RE.findall(name)
            if t.lower() not in _NPC_STOPWORDS and len(t) >= 3
        ]
        if not name_tokens:
            continue
        if any(nt in narration_set for nt in name_tokens):
            return name
    return None


def _find_item_ref(tokens: list[str], inventory: list[dict]) -> Optional[str]:
    """Whole-token match of inventory item names against narration tokens.
    Returns the first matched item_name or None. Used for 'pay for X'
    item reference detection.
    """
    if not inventory or not tokens:
        return None
    narration_set = set(tokens)
    for row in inventory:
        item_name = (row or {}).get('item_name', '')
        if not item_name:
            continue
        item_tokens = [
            t.lower() for t in _TOKEN_RE.findall(item_name)
            if t.lower() not in _NPC_STOPWORDS and len(t) >= 3
        ]
        if not item_tokens:
            continue
        if any(it in narration_set for it in item_tokens):
            return item_name
    return None


# ── Dedup ─────────────────────────────────────────────────────────────────


def _check_and_record_dedup(campaign_id: int, dedup_key: str) -> bool:
    """Return True if dedup_key fired recently for this campaign.
    Records the key for future calls. Mirrors quest_acceptance_parser shape.
    """
    buf = _RECENT_FIRES_PER_CAMPAIGN.get(campaign_id)
    if buf is not None and dedup_key in buf:
        return True
    buf = _RECENT_FIRES_PER_CAMPAIGN.setdefault(
        campaign_id, collections.deque(maxlen=_DEDUP_WINDOW)
    )
    buf.append(dedup_key)
    return False


def _reset_dedup_for_tests(campaign_id: Optional[int] = None):
    """Test-only — clears dedup buffer."""
    if campaign_id is None:
        _RECENT_FIRES_PER_CAMPAIGN.clear()
    else:
        _RECENT_FIRES_PER_CAMPAIGN.pop(campaign_id, None)


# ── Public parser entry point ─────────────────────────────────────────────


def parse_transaction_completion(
    narration: str,
    recent_npcs: list[str],
    inventory: list[dict],
    campaign_id: int,
    surface: str = SURFACE_PRE_LLM,
) -> dict:
    """Parse narration for transaction-completion intent.

    Inputs:
      - narration: free-text narration (player input at pre-LLM, or DM
        narration at post-LLM)
      - recent_npcs: list of canonical_name strings from
        get_recently_active_npcs(campaign_id, location_id=...)
      - inventory: list of inventory dicts from get_inventory(campaign_id,
        character_name) — used for 'pay for X' item-ref completion
      - campaign_id: for cross-turn dedup keying
      - surface: SURFACE_PRE_LLM or SURFACE_POST_LLM — affects verb-priority
        order and dedup_key namespacing

    Returns a dict with:
      - 'fired': bool — True if confidence ≥ medium
      - 'confidence': 'high' | 'medium' | 'low'
      - 'matched_verb': str
      - 'currency': dict | None — {'amount': int, 'denom': str}
      - 'npc_name': str — matched canonical_name or ''
      - 'item_name': str — matched inventory item_name or ''
      - 'markers_present': bool — True when ≥1 structural signal co-occurs
        with the verb but the parser didn't reach HIGH (the M-DELAYED
        primary path firing condition per S77 §1b.1 lock)
      - 'surface': str — SURFACE_PRE_LLM or SURFACE_POST_LLM
      - 'dedup_suppressed': bool
      - 'feature_disabled': bool

    Three-tier routing:
      HIGH: verb + currency + NPC — full transaction signature
      MEDIUM-with-markers: verb + (currency OR NPC, not both) — markers_present=True
      MEDIUM-no-markers: verb only — markers_present=False
      LOW: no verb or dedup-suppressed
    """
    out = {
        'fired': False,
        'confidence': CONFIDENCE_LOW,
        'matched_verb': '',
        'currency': None,
        'npc_name': '',
        'item_name': '',
        'markers_present': False,
        'surface': surface,
        'dedup_suppressed': False,
        'feature_disabled': False,
    }
    if FEATURE_DISABLED:
        out['feature_disabled'] = True
        return out
    tokens = _tokens(narration)
    if not tokens:
        return out

    has_verb, verb = _has_verb(tokens, surface)
    if not has_verb:
        return out
    out['matched_verb'] = verb

    # Structured signals
    currency = _find_currency(narration)
    if currency:
        out['currency'] = currency
    npc = _find_npc(tokens, recent_npcs or [])
    if npc:
        out['npc_name'] = npc
    item = _find_item_ref(tokens, inventory or [])
    if item:
        out['item_name'] = item

    # Confidence determination
    has_currency = currency is not None
    has_npc = bool(npc)
    has_item = bool(item)
    signal_count = sum([has_currency, has_npc, has_item])

    if has_verb and has_currency and has_npc:
        # HIGH: full transaction signature
        dedup_key = (
            f"transaction:{surface}:{currency['amount']}{currency['denom']}:{npc}"
        )
        if _check_and_record_dedup(campaign_id, dedup_key):
            out['dedup_suppressed'] = True
            return out
        out['fired'] = True
        out['confidence'] = CONFIDENCE_HIGH
        return out

    if has_verb and signal_count >= 1:
        # MEDIUM-with-markers — M-DELAYED primary path firing condition
        marker_tag = []
        if has_currency:
            marker_tag.append(f"{currency['amount']}{currency['denom']}")
        if has_npc:
            marker_tag.append(f"npc:{npc}")
        if has_item:
            marker_tag.append(f"item:{item}")
        dedup_key = f"transaction:{surface}:markers:{verb}:{'+'.join(marker_tag)}"
        if _check_and_record_dedup(campaign_id, dedup_key):
            out['dedup_suppressed'] = True
            return out
        out['fired'] = True
        out['confidence'] = CONFIDENCE_MEDIUM
        out['markers_present'] = True
        return out

    # MEDIUM-no-markers — verb only
    dedup_key = f"transaction:{surface}:verb_only:{verb}"
    if _check_and_record_dedup(campaign_id, dedup_key):
        out['dedup_suppressed'] = True
        return out
    out['fired'] = True
    out['confidence'] = CONFIDENCE_MEDIUM
    out['markers_present'] = False
    return out
