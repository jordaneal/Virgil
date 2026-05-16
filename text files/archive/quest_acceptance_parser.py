"""Conversational-Runtime Inversion v0 — Phase 3a (S73)

Closed-vocab narration-detection parser for quest-acceptance intent.

Architectural template per Inversion v0 spec §5 + R1 recon (mechanical_hints
generalizes). Pattern:
  - Closed verb frozenset (no LLM classification — §1a.x clean)
  - Structured-signal co-occurrence (verb + matching offered quest title/word)
  - Whole-word tokenization (no substring false-positives)
  - Cross-turn LRU dedup (per-campaign deque, mirrors N-1 hint extractor)
  - Per-fire telemetry (always-fire — success + reject + skip)
  - Three-tier confidence routing (high / medium / low per spec §11.7)

This module is pure-function over inputs + the module-level LRU dedup buffer.
No DB writes from inside parser (write is engine-side via quest_accept after
operator approval per §1a + §F-59 + §1b). Detection-insertion site is in
discord_dnd_bot._extract_and_persist_world stage 3 (post-LLM, post-NPC-extract).

§1a.x doctrinal extension: detection-from-narration is the deterministic gate.
The parser produces a structured signal (matched quest_id + confidence_tier);
operator approves via /quest accept paste. LLM never decides binding state.

NAMING: this surface is `quest_acceptance_parser` to disambiguate from S19's
`compute_commitment_directive` (player-action-honor escape directive) which
operates on a different surface (combat-intent scene-shift detection, not
quest-status transition). The two are independent.
"""

from __future__ import annotations

import collections
import re
from typing import Optional


# ── Closed verb vocabulary ─────────────────────────────────────────────────
#
# Whole-word matched against the narration. Each entry is a verb / phrase head
# that signals an acceptance intent. Phrasal entries (e.g. "I'll do it",
# "count me in") are matched as ordered token-sequence on the lowercased
# whole-word token list — see _has_acceptance_verb.
#
# Vocabulary maintenance discipline (spec §5.3): closed — new verbs land via
# spec amendment, not silent additions. Per-fire telemetry surfaces friction
# (phrases that should have detected but didn't) for periodic review.
#
# Excluded by design: ambiguous nouns that double as verbs in non-acceptance
# context ("deal" — could be transaction; "agreement" — passive noun; "yes"
# alone — too broad without quest signal). These file as v0.x candidates if
# observed friction shows them.

_SINGLE_TOKEN_ACCEPT_VERBS = frozenset({
    # base + past + 3rd-person conjugations covered.
    # LLM post-narration commonly paraphrases as "the party agrees" /
    # "she pledges" / "he accepts" — 3rd-person forms are load-bearing
    # for the post-LLM hook.
    'accept',
    'accepts',
    'accepted',
    'agree',
    'agrees',
    'agreed',
    'pledge',
    'pledges',
    'pledged',
    'commit',
    'commits',
    'committed',
})

# Phrasal entries — matched as ordered subsequence on the whole-word token
# list. Keys are tuples; "i'll" is stored as "i" + "ll" or "i'll" depending on
# tokenization; we tokenize via [a-zA-Z']+ to preserve contractions.
_PHRASAL_ACCEPT_VERBS = frozenset({
    ("i", "ll", "take"),
    ("i'll", "take"),
    ("i", "ll", "do", "it"),
    ("i'll", "do", "it"),
    ("we", "ll", "take"),
    ("we'll", "take"),
    ("we", "ll", "do", "it"),
    ("we'll", "do", "it"),
    ("we", "accept"),
    ("i", "accept"),
    ("count", "me", "in"),
    ("count", "us", "in"),
    ("you", "have", "a", "deal"),
    ("you", "have", "my", "word"),
})


# Token regex — preserves contractions ("we'll" → "we'll" or "we"+"ll"
# depending on locale). We tokenize alphabetic + apostrophe to be safe; tests
# cover both forms.
_TOKEN_RE = re.compile(r"[a-zA-Z']+")


# ── Cross-turn dedup (LRU per campaign) ────────────────────────────────────
#
# Mirrors N-1 hint extractor's _RECENT_HINTS_PER_CAMPAIGN. Process-local
# deque per campaign; suppresses same-quest re-fire within N turns. N=3 at v0
# per spec §3.5; tunable per-domain. Deque maxlen prevents unbounded growth
# on long-running processes.

_RECENT_QUEST_ACCEPTS_PER_CAMPAIGN: dict[int, collections.deque] = {}
_DEDUP_WINDOW = 3  # entries; per spec §3.5 default

# Feature-disable switch — operator may disable detection at runtime via
# `import quest_acceptance_parser; quest_acceptance_parser.FEATURE_DISABLED = True`.
# Tests confirm disabled-state returns the same "skip" telemetry tier as
# below-threshold detection (always-fire discipline).
FEATURE_DISABLED = False


# ── Confidence-tier names ──────────────────────────────────────────────────

CONFIDENCE_HIGH = 'high'
CONFIDENCE_MEDIUM = 'medium'
CONFIDENCE_LOW = 'low'  # silent; emits skip telemetry only


# ── Tokenization ───────────────────────────────────────────────────────────

def _tokens(text: str) -> list[str]:
    """Lowercase whole-word tokens. Preserves apostrophes in contractions."""
    return [t.lower() for t in _TOKEN_RE.findall(text or '')]


def _has_acceptance_verb(tokens: list[str]) -> tuple[bool, str]:
    """Return (matched, matched_verb) for the first matching verb/phrase.

    Single-token verbs check the set directly. Phrasal verbs check for
    ordered subsequence presence with no gaps.
    """
    # Single-token check
    for t in tokens:
        if t in _SINGLE_TOKEN_ACCEPT_VERBS:
            return True, t
    # Phrasal check — ordered subsequence, no gap
    n = len(tokens)
    for phrase in _PHRASAL_ACCEPT_VERBS:
        plen = len(phrase)
        if plen > n:
            continue
        for i in range(n - plen + 1):
            if tuple(tokens[i:i + plen]) == phrase:
                return True, ' '.join(phrase)
    return False, ''


# ── Quest-title matching (structured-signal co-occurrence) ─────────────────

def _title_tokens(title: str) -> set[str]:
    """Token-set for a quest title. Used for partial-match scoring against
    narration. Filters stopword-tier tokens to reduce false-positive matches.
    """
    if not title:
        return set()
    stop = {'a', 'an', 'the', 'of', 'and', 'to', 'in', 'for', 'on'}
    return {t for t in _tokens(title) if t not in stop and len(t) >= 3}


def _match_quest_in_narration(narration_tokens: list[str],
                               offered_quests: list[dict]) -> Optional[dict]:
    """Return the highest-scoring offered-quest dict whose title-tokens
    appear in the narration, or None.

    Scoring: count of title-tokens (post-stopword filter) present in narration.
    Tie-break: oldest offered quest (lowest id). Threshold: at least 1 matching
    content token (titles with only stopwords don't match — they require the
    verb-only medium-confidence path).
    """
    if not offered_quests or not narration_tokens:
        return None
    narration_set = set(narration_tokens)
    best = None
    best_score = 0
    for q in offered_quests:
        title = q.get('title', '')
        t_tokens = _title_tokens(title)
        if not t_tokens:
            continue
        score = len(t_tokens & narration_set)
        if score > best_score:
            best = q
            best_score = score
        elif score == best_score and score > 0 and best is not None:
            # Tie-break — keep lower id
            if int(q.get('id', 0)) < int(best.get('id', 0)):
                best = q
    return best if best_score > 0 else None


# ── Cross-turn dedup ───────────────────────────────────────────────────────

def _check_and_record_dedup(campaign_id: int, dedup_key: str) -> bool:
    """Return True if this dedup_key has fired recently for the campaign.
    Records the key for future calls. Per spec §3.5: dedup within N=3 turns.
    """
    buf = _RECENT_QUEST_ACCEPTS_PER_CAMPAIGN.get(campaign_id)
    if buf is not None and dedup_key in buf:
        return True
    buf = _RECENT_QUEST_ACCEPTS_PER_CAMPAIGN.setdefault(
        campaign_id, collections.deque(maxlen=_DEDUP_WINDOW)
    )
    buf.append(dedup_key)
    return False


def _reset_dedup_for_tests(campaign_id: int = None):
    """Test-only helper — clears dedup buffer for a campaign (or all)."""
    if campaign_id is None:
        _RECENT_QUEST_ACCEPTS_PER_CAMPAIGN.clear()
    else:
        _RECENT_QUEST_ACCEPTS_PER_CAMPAIGN.pop(campaign_id, None)


# ── Public parser entry point ──────────────────────────────────────────────

def parse_quest_acceptance(narration: str,
                            offered_quests: list[dict],
                            campaign_id: int) -> dict:
    """Parse narration for quest-acceptance intent.

    Inputs:
      - narration: free-text narration (operator OR LLM output — caller decides
        which channel feeds in; at Phase 3a the post-LLM hook in
        _extract_and_persist_world feeds DM narration that may include
        player-acceptance dialogue paraphrased by the LLM)
      - offered_quests: list of dicts from get_offered_quests(campaign_id)
        (status='offered' rows); each must have 'id' and 'title' keys
      - campaign_id: for cross-turn dedup keying

    Returns a dict with:
      - 'fired': bool — True if confidence ≥ medium (high or medium tier)
      - 'confidence': 'high' | 'medium' | 'low'
      - 'matched_verb': str (verb/phrase that triggered, '' if none)
      - 'matched_quest_id': int | None (quest id if structured-signal matched)
      - 'matched_quest_title': str (title of matched quest, '' if none)
      - 'dedup_suppressed': bool (True if this fire was suppressed by LRU)
      - 'feature_disabled': bool (True if FEATURE_DISABLED was set)

    Three-tier routing (spec §11.7 lock):
      - HIGH: verb present + structured-signal (quest title token match) +
        not dedup-suppressed → engine writer path (operator approval via
        pasteable /quest accept <id>; per §F-59 no auto-emit)
      - MEDIUM: verb present + no structured-signal (no offered-quest title
        match) + not dedup-suppressed → suggester card listing offered quests
        for operator approval
      - LOW: no verb (or feature disabled) → silent, emits skip telemetry

    Pure-function discipline: no DB writes, no side effects beyond the
    module-level dedup buffer. Soft-fail at call site — caller checks 'fired'.
    """
    out = {
        'fired': False,
        'confidence': CONFIDENCE_LOW,
        'matched_verb': '',
        'matched_quest_id': None,
        'matched_quest_title': '',
        'dedup_suppressed': False,
        'feature_disabled': False,
    }
    if FEATURE_DISABLED:
        out['feature_disabled'] = True
        return out
    tokens = _tokens(narration)
    if not tokens:
        return out
    has_verb, verb = _has_acceptance_verb(tokens)
    if not has_verb:
        return out
    out['matched_verb'] = verb
    matched_quest = _match_quest_in_narration(tokens, offered_quests or [])
    if matched_quest is not None:
        # HIGH confidence path
        dedup_key = f"quest_accept:{matched_quest.get('id')}"
        if _check_and_record_dedup(campaign_id, dedup_key):
            out['dedup_suppressed'] = True
            return out
        out['fired'] = True
        out['confidence'] = CONFIDENCE_HIGH
        out['matched_quest_id'] = int(matched_quest.get('id'))
        out['matched_quest_title'] = matched_quest.get('title', '')
        return out
    # MEDIUM confidence path — verb only, no structured signal
    # Dedup at the verb-only level by campaign + verb (so the same verb
    # firing twice in a window suppresses; but a new verb after re-utterance
    # fires fresh).
    dedup_key = f"quest_accept:verb_only:{verb}"
    if _check_and_record_dedup(campaign_id, dedup_key):
        out['dedup_suppressed'] = True
        return out
    out['fired'] = True
    out['confidence'] = CONFIDENCE_MEDIUM
    return out
