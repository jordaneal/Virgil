"""§1b.1 Clarification Handshake Primitive v0 — anchored at S77.

Sub-clause under §1b validated-suggester pattern. Sits between §1a.x's
*parser fires* and §1b's *operator pastes*. When a closed-vocab parser
produces an ambiguous structured signal (multi-domain match, cross-domain
semantic equivalence, or 1-parser-MEDIUM with structural markers), this
module inserts an operator-disambiguation step before the §1b validated-
suggester gate fires.

Architecture (post-S77 council pressure-test convergence):

  Primary path — M-DELAYED in-fiction clarification:
    1-parser-MEDIUM-with-markers → engine sets `pending_clarification`
    flag on `dnd_scene_state`; LLM narrates scene continuing WITHOUT
    finalizing the mentioned action (per pending_clarification directive
    injected into build_dm_context); parser fires second-pass on
    operator's next utterance. HIGH resolution commits via §17 path,
    still-ambiguous escalates to Layer A/B fallback.

  Fallback Layer A — richer suggester card:
    ≥2 parsers ≥MEDIUM, enumerable candidate set → multi-paste card to
    #dm-aside (per-candidate paste options + explicit skip).

  Fallback Layer B — bidirectional OOC handshake:
    ≥2 parsers ≥MEDIUM, NOT cleanly enumerable → free-text question to
    #dm-aside + bot.wait_for listener (5-min timeout, controller-only
    filter, 2-iteration recursion cap).

Doctrinal composition:
  §1a — unchanged; LLM never decides binding state. Parsers + operator
    action are the only state-mutation surfaces.
  §1a.x — closed-vocab parser remains the deterministic gate; aggregator
    reads parser outputs (HIGH/MEDIUM/LOW), never inspects raw markers.
  §1b — Layer A is card-content extension; Layer B is new §1b instance
    shape. §1b.1 is formal sub-clause.
  §F-59 — bot never auto-emits; operator action (paste or OOC reply) is
    the gate. M-DELAYED's "action" is the operator's next narration
    triggering parser second-pass.
  §17 — single writer for pending_clarification column.

Why M-DELAYED over M-IMMEDIATE (council pressure-test record):
  Three pressure-test passes (Oracle/GPT/Gemini) surfaced that the §1a
  defense of M-IMMEDIATE conflated LLM-narration-as-content (non-§1a-
  violating; project's existing LLM-mediated workflow) with LLM-
  narration-as-gate (§1a-violating; not what M-DELAYED does). M-DELAYED
  preserves §1a cleanly AND honors the Conversational-Runtime Inversion
  direction-lock litmus — "would a good human DM stop the session to
  operate software for this?" Answer for M-DELAYED: no, the DM clarifies
  in-fiction. Answer for M-IMMEDIATE: yes, OOC menu every ambiguous
  utterance. M-DELAYED ships clean.

Decentralized parser-output aggregation (council §11.5 lock):
  Parsers own ambiguity detection per §1a.x. This module's aggregator
  reads parser outputs (HIGH/MEDIUM/LOW), applies Stage 1 routing rule,
  never inspects raw markers. Domain-agnostic flagship primitive; v0
  wiring covers quest-accept; transaction-completion + loot-drop register
  at Phase 3b.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional


# ── Module-level state ──────────────────────────────────────────────────────

# In-memory active Layer B sessions per campaign (cleared on restart per
# §11.2 lock — DB-persisted pending_clarification flag survives restart
# but in-memory listener state does not, which is correct: M-DELAYED's
# in-fiction state lives in the DB; only the OOC-listener wait-for state
# is ephemeral).
_active_sessions: dict[int, list["ClarificationSession"]] = {}

# Operator-flippable kill switch. Set `FEATURE_DISABLED = True` at runtime
# to revert to pre-§1b.1 routing (every parser fires independently per
# Phase 3a behavior). Aggregator returns SINGLE_DOMAIN_CLEAR on highest-
# confidence parser when disabled; falls through to existing routing.
FEATURE_DISABLED = False

# Per-campaign session cap (Layer B sessions). Excess fires telemetry +
# silent log per §11.8 lock.
PER_CAMPAIGN_SESSION_CAP = 3

# Layer B listener timeout — 5 min default per §11.5 lock.
LAYER_B_TIMEOUT_SECONDS = 300

# Layer B recursion cap — 2 iterations of ambiguity-on-reply before
# manual-decision escalation per §11.8 lock.
LAYER_B_RECURSION_MAX = 2


# ── Dataclasses ─────────────────────────────────────────────────────────────


@dataclass
class ParserResult:
    """Normalized parser output for the aggregator. Each registered parser
    converts its native return dict into this shape so the aggregator does
    not need to know per-parser specifics.

    `markers_present` is set True when the parser saw structural intent
    markers (NPC name, currency, item reference, location, etc.) even
    though it didn't reach HIGH confidence on its own. Used by the
    1-parser-MEDIUM-with-markers routing rule.
    """
    domain: str
    confidence: Literal['high', 'medium', 'low']
    fired: bool = False
    markers_present: bool = False
    dedup_suppressed: bool = False
    feature_disabled: bool = False
    # Optional structured payload for downstream candidate rendering.
    candidate: dict = field(default_factory=dict)


@dataclass
class ClarificationSession:
    """Tracks a single clarification interaction lifecycle.

    layer:
      'IN_FICTION' — M-DELAYED primary path (no listener, no UI; DB-side
        pending_clarification flag drives the directive).
      'A' — Layer A multi-paste card posted to #dm-aside (no listener,
        operator paste fires §17 writer).
      'B' — Layer B free-text handshake (active bot.wait_for listener).
    """
    campaign_id: int
    controller_id: str
    trigger_event_id: str
    candidates: list = field(default_factory=list)
    layer: Literal['IN_FICTION', 'A', 'B'] = 'IN_FICTION'
    status: Literal['PENDING', 'RESOLVED', 'EXPIRED', 'CANCELLED'] = 'PENDING'
    created_at: float = field(default_factory=time.time)
    timeout_at: float = 0.0
    recursion_iteration: int = 0


@dataclass
class RouteDecision:
    """Aggregator output. The `route` literal dispatches:
      SILENT_LOG — no clarification surface; existing routing (if any).
      SINGLE_DOMAIN_CLEAR — 1 parser at HIGH; pass through to Phase 3a path.
      IN_FICTION_CLARIFICATION — M-DELAYED primary; engine sets pending flag.
      LAYER_A — multi-paste card (cross-domain enumerable).
      LAYER_B — bidirectional OOC handshake (non-enumerable).
    """
    route: Literal[
        'SILENT_LOG', 'SINGLE_DOMAIN_CLEAR',
        'IN_FICTION_CLARIFICATION', 'LAYER_A', 'LAYER_B',
    ]
    parser_results: list[ParserResult] = field(default_factory=list)
    candidates: list = field(default_factory=list)


# ── Aggregator (Stage 1 routing) ────────────────────────────────────────────


def aggregate_parser_outputs(parser_results: list[ParserResult]) -> RouteDecision:
    """Decentralized parser-output aggregation per §11.5 lock.

    Routing rule:
      - 0 parsers ≥MEDIUM, no structural intent signals → SILENT_LOG
      - 1 parser at HIGH (regardless of others) → SINGLE_DOMAIN_CLEAR
      - 1 parser at MEDIUM, markers present → IN_FICTION_CLARIFICATION
        (M-DELAYED primary path)
      - 1 parser at MEDIUM, no markers → SINGLE_DOMAIN_CLEAR (pass through
        to existing Phase 3a medium-tier suggester)
      - ≥2 parsers ≥MEDIUM with enumerable candidates → LAYER_A
      - ≥2 parsers ≥MEDIUM, non-enumerable → LAYER_B

    Feature-disable returns SINGLE_DOMAIN_CLEAR on the highest-confidence
    parser to preserve Phase 3a fall-through behavior.
    """
    if FEATURE_DISABLED:
        return RouteDecision(
            route='SINGLE_DOMAIN_CLEAR', parser_results=parser_results,
        )

    # Highs: any parser at HIGH wins outright (Phase 3a path commits).
    highs = [r for r in parser_results if r.confidence == 'high' and r.fired]
    mediums = [r for r in parser_results if r.confidence == 'medium' and r.fired]

    if len(highs) >= 1:
        # SINGLE_DOMAIN_CLEAR — existing Phase 3a routes the high-confidence
        # parser straight to its suggester card. Aggregator passes through.
        return RouteDecision(
            route='SINGLE_DOMAIN_CLEAR', parser_results=parser_results,
        )

    # Cross-domain ambiguity — ≥2 mediums.
    if len(mediums) >= 2:
        candidates = [_candidate_from_result(r) for r in mediums]
        if _are_candidates_enumerable(candidates):
            return RouteDecision(
                route='LAYER_A', parser_results=parser_results,
                candidates=candidates,
            )
        return RouteDecision(
            route='LAYER_B', parser_results=parser_results,
            candidates=candidates,
        )

    # Exactly 1 medium parser.
    if len(mediums) == 1:
        r = mediums[0]
        if r.markers_present:
            # M-DELAYED primary path. Engine sets pending; LLM narrates
            # pending scene; parser fires second-pass on next utterance.
            candidates = [_candidate_from_result(r)]
            return RouteDecision(
                route='IN_FICTION_CLARIFICATION',
                parser_results=parser_results,
                candidates=candidates,
            )
        # No markers — fall through to existing Phase 3a medium-tier
        # suggester (the parser's own suggester card path).
        return RouteDecision(
            route='SINGLE_DOMAIN_CLEAR', parser_results=parser_results,
        )

    # No fires.
    return RouteDecision(route='SILENT_LOG', parser_results=parser_results)


def _candidate_from_result(r: ParserResult) -> dict:
    """Convert a ParserResult into a candidate dict for card rendering."""
    return {
        'domain': r.domain,
        'confidence': r.confidence,
        'payload': dict(r.candidate or {}),
    }


def _are_candidates_enumerable(candidates: list[dict]) -> bool:
    """Returns True if AT LEAST ONE candidate has a non-empty payload.

    Loosened post-S78 live-verify (operator firing "I pay Mara 2gp for 1
    loaf as agreed upon" triggered quest_accept MEDIUM on 'agreed' verb
    + transaction_completion MEDIUM-with-markers on currency, but
    quest_accept's empty payload broke the all-or-nothing enumerability
    check and routed to LAYER_B unnecessarily). With the loosened rule,
    LAYER_A fires whenever any candidate has content — the card renders
    enumerable candidates as paste options and includes a skip option
    for the rest.
    """
    if not candidates:
        return False
    return any(bool(c.get('payload')) for c in candidates)


# ── pending_clarification persistence ───────────────────────────────────────
#
# Single-writer per §17 discipline. clarification_handshake.py owns the
# pending_clarification column on dnd_scene_state. Read paths:
#   - compute_pending_clarification_directive (per-turn directive composer)
#   - aggregate_parser_outputs caller (second-pass detection check)
#   - Layer A/B fallback handlers
#
# Storage shape (JSON-serialized in the TEXT column):
#   {
#     "trigger_event_id": "...",
#     "candidates": [...],
#     "created_at": <float epoch>,
#     "timeout_at": <float epoch>
#   }
#
# DB access uses sqlite3 with PRAGMA foreign_keys=ON per S61 standing
# practice. Soft-fails on error — callers do not block on persistence
# (telemetry surfaces the failure).


def _db_path():
    """Resolve DB_PATH lazily so test code can swap dnd_engine.DB_PATH
    before this module is imported. Avoids circular-import at module load.
    """
    from dnd_engine import DB_PATH
    return DB_PATH


def set_pending_clarification(campaign_id: int, candidates: list,
                              trigger_event_id: str,
                              timeout_seconds: int = LAYER_B_TIMEOUT_SECONDS,
                              ) -> Optional[ClarificationSession]:
    """Write pending_clarification metadata to dnd_scene_state. Returns
    the created session (in-memory tracking) or None on failure.

    M-DELAYED primary path. Engine sets flag; LLM reads
    compute_pending_clarification_directive on next narration; parser
    second-pass fires on operator's next utterance.
    """
    now = time.time()
    timeout_at = now + timeout_seconds
    metadata = {
        'trigger_event_id': trigger_event_id,
        'candidates': candidates,
        'created_at': now,
        'timeout_at': timeout_at,
    }
    try:
        conn = sqlite3.connect(_db_path())
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute(
            "UPDATE dnd_scene_state SET pending_clarification=? "
            "WHERE campaign_id=?",
            (json.dumps(metadata), campaign_id),
        )
        conn.commit()
        conn.close()
    except Exception:
        return None

    session = ClarificationSession(
        campaign_id=campaign_id,
        controller_id='',  # Layer/listener fills if relevant
        trigger_event_id=trigger_event_id,
        candidates=candidates,
        layer='IN_FICTION',
        status='PENDING',
        created_at=now,
        timeout_at=timeout_at,
    )
    return session


def clear_pending_clarification(campaign_id: int) -> bool:
    """Reset pending_clarification to NULL. Idempotent — safe to call on
    campaigns with no active pending state.
    """
    try:
        conn = sqlite3.connect(_db_path())
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute(
            "UPDATE dnd_scene_state SET pending_clarification=NULL "
            "WHERE campaign_id=?",
            (campaign_id,),
        )
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False


def get_pending_clarification(campaign_id: int) -> Optional[dict]:
    """Read pending_clarification JSON metadata or None if unset/missing.
    Soft-fails to None on any error (caller treats absent state safely).
    """
    try:
        conn = sqlite3.connect(_db_path())
        row = conn.execute(
            "SELECT pending_clarification FROM dnd_scene_state "
            "WHERE campaign_id=?",
            (campaign_id,),
        ).fetchone()
        conn.close()
    except Exception:
        return None
    if not row or not row[0]:
        return None
    try:
        return json.loads(row[0])
    except Exception:
        return None


def list_campaigns_with_pending_clarification() -> list[int]:
    """Return campaign_ids with active pending_clarification. Used at
    on_ready to post restart-preservation notifications.
    """
    try:
        conn = sqlite3.connect(_db_path())
        rows = conn.execute(
            "SELECT campaign_id FROM dnd_scene_state "
            "WHERE pending_clarification IS NOT NULL"
        ).fetchall()
        conn.close()
        return [int(r[0]) for r in rows]
    except Exception:
        return []


# ── Card renderers ──────────────────────────────────────────────────────────


_DOMAIN_HUMAN_LABEL = {
    'quest_accept': 'accepting an offered quest',
    'transaction_completion': 'paying or completing a trade',
    'loot_drop_player': 'claiming loot',
    'loot_drop_llm': 'spotting dropped items',
    'npc_commitment': 'a commitment from an NPC',
}


def _humanize_domain(domain: str) -> str:
    """Map machine domain name to operator-readable phrase. Falls back to
    the raw domain when no mapping exists (newly-shipped parsers earn
    a label entry at their ship; until then the raw name is fine).
    """
    return _DOMAIN_HUMAN_LABEL.get(domain, domain.replace('_', ' '))


def build_layer_a_card(candidates: list[dict],
                       narration_excerpt: str = '') -> str:
    """Render the Layer A multi-paste suggester card.

    DM-voice (post-S78 live-verify UX pass): the card is an operator-side
    aside, not a system log line. Renders in plain English with human
    domain labels.

    Filters out empty-payload candidates: those without populated payloads
    have no slash to paste and would only clutter the card. Operator
    ignore-path is the §F-59 skip.
    """
    if not candidates:
        return ''
    enumerable = [c for c in candidates if c.get('payload')]
    if not enumerable:
        return ''
    lines = ['**A quick check —**']
    if narration_excerpt:
        excerpt = narration_excerpt.strip()
        if len(excerpt) > 140:
            excerpt = excerpt[:140].rstrip() + '...'
        lines.append(f'Your turn could go a couple ways: _"{excerpt}"_')
    else:
        lines.append('Your turn could go a couple ways.')
    lines.append('')
    for idx, c in enumerate(enumerable):
        label = chr(ord('A') + idx) if idx < 26 else str(idx + 1)
        domain = c.get('domain', '?')
        human = _humanize_domain(domain)
        payload = c.get('payload', {}) or {}
        slash = payload.get('slash', '')
        if slash:
            lines.append(f'**{label}.** {human} — `{slash}`')
        else:
            lines.append(f'**{label}.** {human}')
    lines.append('')
    lines.append('_Paste the slash that fits, or ignore this if none do — '
                 'I\'ll keep going either way._')
    return '\n'.join(lines)


def build_layer_b_question(candidates: list[dict],
                           narration_excerpt: str = '') -> str:
    """Render the Layer B free-text clarification question.

    DM-voice copy: reads as an aside the DM is saying to the operator,
    not a log line. Human domain labels via _humanize_domain. Numbered
    options for quick reply.
    """
    lines = ['**A quick check —**']
    if narration_excerpt:
        excerpt = narration_excerpt.strip()
        if len(excerpt) > 140:
            excerpt = excerpt[:140].rstrip() + '...'
        lines.append(f'Your turn signaled a few things at once and I can\'t '
                     f'tell which: _"{excerpt}"_')
    else:
        lines.append('Your turn signaled a few things at once and I can\'t '
                     'tell which.')
    lines.append('')
    lines.append('Reply with a number:')
    seen: list[str] = []
    for c in candidates:
        domain = c.get('domain', '')
        if domain and domain not in seen:
            seen.append(domain)
    for idx, domain in enumerate(seen, start=1):
        lines.append(f'  **{idx}.** {_humanize_domain(domain)}')
    skip_num = len(seen) + 1
    lines.append(f'  **{skip_num}.** none of those — keep going')
    lines.append('')
    lines.append('_I\'ll move on if you don\'t say anything in 5 minutes._')
    return '\n'.join(lines)


def build_layer_b_recursion_card(candidates: list[dict],
                                  iteration: int) -> str:
    """Iteration-2 binary forced-choice card. Highest-2 candidates only.
    DM-voice copy per S78 UX pass.
    """
    if iteration >= LAYER_B_RECURSION_MAX:
        return _build_layer_b_manual_card(candidates)
    pair = candidates[:2]
    if len(pair) < 2:
        return _build_layer_b_manual_card(candidates)
    a = _humanize_domain(pair[0].get('domain', 'a'))
    b = _humanize_domain(pair[1].get('domain', 'b'))
    return (
        "**Let me narrow it down —**\n"
        f"Was it **{a}** or **{b}**? "
        "Reply **1**, **2**, or **3** for neither."
    )


def _build_layer_b_manual_card(candidates: list[dict]) -> str:
    """Iteration-3 manual decision card — DM-voice terse per §11.9."""
    return (
        "**One more try —**\n"
        "Pick whichever fits, or just keep playing and I'll move on."
    )


# ── Reply parsing ───────────────────────────────────────────────────────────


def parse_layer_b_reply(reply_text: str,
                        candidates: list[dict]) -> dict:
    """Closed-vocab parser for OOC clarification replies.

    Accepts both:
      - Numeric reply ("1", "2", "3") matching the numbered option in the
        Layer B card.
      - Domain name reply ("transaction_completion", "skip") for
        backward compatibility.

    Returns {'intent': ..., 'matched_domain': ...} where intent is one of:
      'COMMIT_<domain>' — operator chose a candidate
      'EXPLICIT_SKIP' — operator chose skip
      'AMBIGUOUS' — reply doesn't cleanly match
    """
    text = (reply_text or '').strip().lower()
    if not text:
        return {'intent': 'AMBIGUOUS', 'matched_domain': ''}

    # Distinct ordered domain list (mirrors the numbering in build_layer_b_question)
    seen: list[str] = []
    for c in candidates:
        d = (c.get('domain') or '').lower()
        if d and d not in seen:
            seen.append(d)

    # Numeric reply
    first_token = text.split()[0] if text else ''
    if first_token.isdigit():
        num = int(first_token)
        if 1 <= num <= len(seen):
            d = seen[num - 1]
            return {'intent': f'COMMIT_{d}', 'matched_domain': d}
        if num == len(seen) + 1:
            return {'intent': 'EXPLICIT_SKIP', 'matched_domain': ''}
        return {'intent': 'AMBIGUOUS', 'matched_domain': ''}

    skip_tokens = {'skip', 'none', 'nothing', 'no', 'cancel'}
    if text in skip_tokens or first_token in skip_tokens:
        return {'intent': 'EXPLICIT_SKIP', 'matched_domain': ''}

    for d in seen:
        if d and (d == text or d in text.split()):
            return {'intent': f'COMMIT_{d}', 'matched_domain': d}

    return {'intent': 'AMBIGUOUS', 'matched_domain': ''}


# ── Layer B async listener ──────────────────────────────────────────────────


async def await_layer_b_reply(bot, channel_id: int, controller_id: str,
                              trigger_timestamp: float,
                              timeout: int = LAYER_B_TIMEOUT_SECONDS):
    """bot.wait_for wrapper. Filter: channel + author + post-timestamp +
    !bot. Returns the discord.Message or None on timeout.

    Soft-fails to None on any error so the caller treats timeout-or-error
    identically (Layer B's silent-expiry semantic).
    """
    def _check(msg):
        try:
            if msg.channel.id != channel_id:
                return False
            if str(msg.author.id) != str(controller_id):
                return False
            if getattr(msg.author, 'bot', False):
                return False
            ts = msg.created_at.timestamp() if msg.created_at else 0
            return ts > trigger_timestamp
        except Exception:
            return False

    try:
        msg = await bot.wait_for('message', check=_check, timeout=timeout)
        return msg
    except asyncio.TimeoutError:
        return None
    except Exception:
        return None


# ── Session lifecycle helpers ───────────────────────────────────────────────


def add_session(session: ClarificationSession) -> bool:
    """Register a Layer B session in the per-campaign in-memory map.
    Enforces PER_CAMPAIGN_SESSION_CAP. Returns False when cap is hit
    (caller fires `clarification_cap_hit` telemetry + falls back to
    silent log).
    """
    sessions = _active_sessions.setdefault(session.campaign_id, [])
    sessions = [s for s in sessions if s.status == 'PENDING']
    _active_sessions[session.campaign_id] = sessions
    if len(sessions) >= PER_CAMPAIGN_SESSION_CAP:
        return False
    sessions.append(session)
    return True


def cancel_session(session: ClarificationSession,
                   status: str = 'CANCELLED') -> None:
    """Mark a session terminated and remove it from the active map."""
    session.status = status
    sessions = _active_sessions.get(session.campaign_id, [])
    _active_sessions[session.campaign_id] = [
        s for s in sessions if s is not session
    ]


def _reset_for_tests():
    """Test-only — clears module state. Tests use monkeypatching of
    _db_path in practice for DB-side state."""
    _active_sessions.clear()


# ── Directive composer placement note ──────────────────────────────────────
#
# `compute_pending_clarification_directive` lives in dnd_orchestration.py
# per §59 family-cohesion (21 sibling instances co-located). Code lean per
# S77 dispatch recon item R10. Reads pending_clarification metadata and
# emits prompt-block text + signal dict tuple following the canonical §59
# sibling shape.
