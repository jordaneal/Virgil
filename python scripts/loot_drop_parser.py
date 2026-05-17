"""S78 — Inversion v0 Phase 3b: loot-drop narration-detection parser.

Closed-vocab parser per §1a.x — detects loot-claim/drop intent across
player narrative AND LLM completion text. Two surfaces:
  - `loot_drop_player` (pre-LLM): player narrates intent to claim
    pending loot — "I grab the longsword", "I take the silver dagger".
  - `loot_drop_llm` (post-LLM): LLM narrates a reveal that drops loot
    into scene — "the chest reveals a longsword", "inside the box is a
    healing potion".

Both surfaces register against the §1b.1 aggregator. Aggregator dedups
within a single turn via Stage 1 routing — if both fire on the same
narration, ≥2-parsers-≥MEDIUM ambiguity routes to LAYER_A/B as needed.

Per §1a.x prerequisites:
  1. Closed verb frozenset — no LLM classification.
  2. Structured-signal co-occurrence — verb + pending loot item match
     (exact string) OR verb + container/item-class noun.
  3. Engine-side writer remains §17-disciplined — parser produces
     structured proposal; existing /loot claim slash is the operator-paste
     gate (or the F-035 auto-claim path for HIGH-confidence player-intent
     fires per S66 ship).
  4. Three-tier confidence with §1b.1 markers_present discrimination.

Three-tier routing per S77 §1b.1 lock:
  HIGH: verb + pending loot exact-match — operator paste of /loot claim
        commits via existing path (or auto-claim per F-035).
  MEDIUM-with-markers: verb + item-class noun (sword/potion/etc.) but no
        exact pending match → markers_present=True (M-DELAYED primary).
  MEDIUM-no-markers: verb only.
  LOW: no verb or dedup-suppressed.
"""

from __future__ import annotations

import collections
import re
from typing import Literal, Optional


# ── Closed verb vocabulary ─────────────────────────────────────────────────

_PLAYER_INTENT_VERBS = frozenset({
    # take / grab / claim / pocket forms
    'take', 'takes', 'took', 'taking',
    'grab', 'grabs', 'grabbed', 'grabbing',
    'claim', 'claims', 'claimed', 'claiming',
    'pocket', 'pockets', 'pocketed', 'pocketing',
    'snatch', 'snatches', 'snatched', 'snatching',
    'pick', 'picks', 'picked', 'picking',  # 'pick up' phrasal also covered
    'seize', 'seizes', 'seized', 'seizing',
    'collect', 'collects', 'collected', 'collecting',
    'lift', 'lifts', 'lifted', 'lifting',
})

_LLM_REVEAL_VERBS = frozenset({
    # reveal / contain / discover forms (LLM-side reveal narration)
    'reveals', 'revealed', 'revealing', 'reveal',
    'contains', 'contained', 'containing', 'contain',
    'discovers', 'discovered', 'discovering', 'discover',
    'uncovers', 'uncovered', 'uncovering', 'uncover',
    'holds', 'held', 'holding', 'hold',
    'exposes', 'exposed', 'exposing', 'expose',
    'shows', 'showed', 'shown', 'showing', 'show',
})

# Phrasal verbs
_PHRASAL_VERBS = frozenset({
    ('pick', 'up'),
    ('picks', 'up'),
    ('picked', 'up'),
    ('picking', 'up'),
    ('take', 'the'),
    ('takes', 'the'),
    ('took', 'the'),
    ('grab', 'the'),
    ('grabs', 'the'),
    ('grabbed', 'the'),
    ('inside', 'is'),
    ('inside', 'are'),
    ('inside', 'lies'),
    ('inside', 'sits'),
    ('amongst', 'them'),
})


_TOKEN_RE = re.compile(r"[a-zA-Z']+")

# Item-class noun vocabulary — generic loot category markers. Used by
# MEDIUM-with-markers detection when the player verb fires but no exact
# pending loot match exists.
_ITEM_CLASS_NOUNS = frozenset({
    # Weapons
    'sword', 'longsword', 'shortsword', 'dagger', 'mace', 'axe', 'hammer',
    'bow', 'crossbow', 'spear', 'staff', 'wand', 'scimitar', 'rapier',
    # Armor
    'shield', 'helm', 'helmet', 'armor', 'chainmail', 'plate', 'cloak',
    # Containers / pouches
    'pouch', 'bag', 'sack', 'purse', 'chest', 'crate', 'box',
    # Magical / consumables
    'potion', 'scroll', 'ring', 'amulet', 'gem', 'jewel', 'crystal',
    'orb', 'talisman', 'rune',
    # Quest tokens / valuables
    'coin', 'coins', 'gold', 'silver', 'copper', 'platinum',
    'key', 'map', 'letter', 'document', 'tome', 'book',
    # Misc
    'rope', 'lantern', 'torch', 'flask', 'vial',
})

# Container nouns — used by LLM-reveal detection to identify reveal-shape
# narration (e.g., "the chest reveals X").
_CONTAINER_NOUNS = frozenset({
    'chest', 'box', 'crate', 'pouch', 'bag', 'sack', 'purse',
    'cabinet', 'cupboard', 'drawer', 'compartment', 'safe', 'vault',
    'urn', 'barrel', 'package', 'parcel', 'satchel',
})


# ── Cross-turn dedup ──────────────────────────────────────────────────────
_RECENT_FIRES_PER_CAMPAIGN: dict[int, collections.deque] = {}
_DEDUP_WINDOW = 3

FEATURE_DISABLED = False


CONFIDENCE_HIGH = 'high'
CONFIDENCE_MEDIUM = 'medium'
CONFIDENCE_LOW = 'low'

SURFACE_PRE_LLM = 'pre_llm'
SURFACE_POST_LLM = 'post_llm'


# ── Tokenization ──────────────────────────────────────────────────────────

def _tokens(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text or '')]


def _has_verb(tokens: list[str], surface: str) -> tuple[bool, str]:
    """Return (matched, verb) — surface picks verb-set priority.

    Phrasals checked first so longer-specific matches ("pick up") win
    over their single-verb prefixes ('pick').
    """
    if surface == SURFACE_PRE_LLM:
        primary = _PLAYER_INTENT_VERBS
        secondary = _LLM_REVEAL_VERBS
    else:
        primary = _LLM_REVEAL_VERBS
        secondary = _PLAYER_INTENT_VERBS

    # Phrasals first.
    n = len(tokens)
    for phrase in _PHRASAL_VERBS:
        plen = len(phrase)
        if plen > n:
            continue
        for i in range(n - plen + 1):
            if tuple(tokens[i:i + plen]) == phrase:
                return True, ' '.join(phrase)

    # Single-token fallback.
    for t in tokens:
        if t in primary:
            return True, t
    for t in tokens:
        if t in secondary:
            return True, t
    return False, ''


# ── Structured-signal detectors ───────────────────────────────────────────


_STOPWORDS = frozenset({
    'a', 'an', 'the', 'of', 'and', 'to', 'in', 'for', 'on', 'with',
})


def _find_pending_loot_match(tokens: list[str],
                              pending_loot: list[dict]) -> Optional[dict]:
    """Match narration tokens against pending loot item names.

    pending_loot rows have `items` (decoded list of {item_name, quantity})
    + `coin_amount`/`coin_denom`. We match against item_name strings; coin
    matches are out-of-scope for loot_drop (those route through N-1's
    coin-bookkeeping or the transaction parser).

    Returns the matched pending_loot row + matched item_name, or None.
    """
    if not pending_loot or not tokens:
        return None
    narration_set = set(tokens)
    for row in pending_loot:
        items = row.get('items') or []
        for item in items:
            if not isinstance(item, dict):
                continue
            item_name = (item.get('item_name') or '').strip()
            if not item_name:
                continue
            item_tokens = [
                t.lower() for t in _TOKEN_RE.findall(item_name)
                if t.lower() not in _STOPWORDS and len(t) >= 3
            ]
            if not item_tokens:
                continue
            if all(it in narration_set for it in item_tokens):
                return {'row': row, 'item_name': item_name}
            # Single distinctive-token fallback: "I grab the dagger" matches
            # pending "silver dagger" by the more-specific noun. Token must
            # be >= 4 chars to avoid false-positive on generic words.
            for it in item_tokens:
                if len(it) >= 4 and it in narration_set:
                    return {'row': row, 'item_name': item_name}
    return None


def _find_item_class_marker(tokens: list[str]) -> Optional[str]:
    """Match generic item-class noun (sword/potion/etc.) in narration.
    Returns the matched noun or None.
    """
    if not tokens:
        return None
    for t in tokens:
        if t in _ITEM_CLASS_NOUNS:
            return t
    return None


def _find_container_marker(tokens: list[str]) -> Optional[str]:
    """Match container noun (chest/box/etc.) in narration. Used to
    boost LLM-reveal detection confidence.
    """
    if not tokens:
        return None
    for t in tokens:
        if t in _CONTAINER_NOUNS:
            return t
    return None


# ── Dedup ─────────────────────────────────────────────────────────────────


def _check_and_record_dedup(campaign_id: int, dedup_key: str) -> bool:
    buf = _RECENT_FIRES_PER_CAMPAIGN.get(campaign_id)
    if buf is not None and dedup_key in buf:
        return True
    buf = _RECENT_FIRES_PER_CAMPAIGN.setdefault(
        campaign_id, collections.deque(maxlen=_DEDUP_WINDOW)
    )
    buf.append(dedup_key)
    return False


def _reset_dedup_for_tests(campaign_id: Optional[int] = None):
    if campaign_id is None:
        _RECENT_FIRES_PER_CAMPAIGN.clear()
    else:
        _RECENT_FIRES_PER_CAMPAIGN.pop(campaign_id, None)


# ── Public parser entry point ─────────────────────────────────────────────


def parse_loot_drop(narration: str,
                    pending_loot: list[dict],
                    campaign_id: int,
                    surface: str = SURFACE_PRE_LLM) -> dict:
    """Parse narration for loot-claim/drop intent.

    Inputs:
      - narration: free text (player input pre-LLM; DM completion post-LLM)
      - pending_loot: list from get_pending_loot(campaign_id) — pending
        (surfaced=0) loot rows with embedded items[]
      - campaign_id: for cross-turn dedup
      - surface: SURFACE_PRE_LLM | SURFACE_POST_LLM

    Returns:
      'fired': bool
      'confidence': 'high' | 'medium' | 'low'
      'matched_verb': str
      'matched_pending_loot_id': int | None
      'matched_item_name': str
      'item_class_marker': str — generic noun match or ''
      'container_marker': str — chest/box/etc. or '' (LLM-reveal only)
      'markers_present': bool
      'surface': str
      'dedup_suppressed': bool
      'feature_disabled': bool

    Routing:
      HIGH: verb + exact pending-loot item match
      MEDIUM-with-markers: verb + item-class noun (or container for LLM-reveal)
      MEDIUM-no-markers: verb only
      LOW: no verb or dedup-suppressed
    """
    out = {
        'fired': False,
        'confidence': CONFIDENCE_LOW,
        'matched_verb': '',
        'matched_pending_loot_id': None,
        'matched_item_name': '',
        'item_class_marker': '',
        'container_marker': '',
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
    pending_match = _find_pending_loot_match(tokens, pending_loot or [])
    class_marker = _find_item_class_marker(tokens)
    container_marker = (
        _find_container_marker(tokens) if surface == SURFACE_POST_LLM else None
    )

    if pending_match:
        # HIGH — exact pending loot match
        row = pending_match['row']
        out['matched_pending_loot_id'] = int(row.get('id') or 0)
        out['matched_item_name'] = pending_match['item_name']
        dedup_key = f"loot:{surface}:pending:{out['matched_pending_loot_id']}:{pending_match['item_name']}"
        if _check_and_record_dedup(campaign_id, dedup_key):
            out['dedup_suppressed'] = True
            return out
        out['fired'] = True
        out['confidence'] = CONFIDENCE_HIGH
        return out

    if class_marker or container_marker:
        # MEDIUM-with-markers
        if class_marker:
            out['item_class_marker'] = class_marker
        if container_marker:
            out['container_marker'] = container_marker
        marker_tag = class_marker or container_marker
        dedup_key = f"loot:{surface}:markers:{verb}:{marker_tag}"
        if _check_and_record_dedup(campaign_id, dedup_key):
            out['dedup_suppressed'] = True
            return out
        out['fired'] = True
        out['confidence'] = CONFIDENCE_MEDIUM
        out['markers_present'] = True
        return out

    # MEDIUM-no-markers
    dedup_key = f"loot:{surface}:verb_only:{verb}"
    if _check_and_record_dedup(campaign_id, dedup_key):
        out['dedup_suppressed'] = True
        return out
    out['fired'] = True
    out['confidence'] = CONFIDENCE_MEDIUM
    out['markers_present'] = False
    return out
