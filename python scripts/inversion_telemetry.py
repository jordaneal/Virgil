"""Conversational-Runtime Inversion v0 — telemetry primitives (S73).

Per-fire JSONL telemetry for narration-detection parsers. Always-fire
discipline (spec §11.8 lock): every detection attempt logs, including skip
and reject — so the empirical baseline is observable regardless of whether
the parser produced a routed action.

JSONL landing path: /home/jordaneal/scripts/playtest/inversion_v0_<YYYYMMDD>.jsonl
(daily-rotated by ISO date). Directory auto-created. Each line is a single
JSON object with stable schema:

  {
    "ts": "2026-05-15T22:00:00",
    "domain": "quest_accept" | "transaction" | "loot_drop" | "npc_commitment",
    "event": "detected" | "routed" | "suppressed",
    "confidence": "high" | "medium" | "low",
    "campaign_id": int,
    "matched_verb": str,
    "matched_quest_id": int | None (quest_accept only),
    "dedup_suppressed": bool,
    "feature_disabled": bool,
    "route": "engine" | "suggester" | "silent",  (only on 'routed' event)
    "operator_response": "paste" | "dismiss" | "override" | null,  (deferred)
  }

The operator-response field is reserved for Phase 3a v0.1 — at v0 we log
detection + route only; operator paste-detection wiring lands when slash
command receives the suggested action (cosine-similarity-free per S57
crystallization).

Soft-fail: any error in telemetry write logs to stderr and returns without
raising. Detection layer never blocks on telemetry.
"""

from __future__ import annotations

import datetime
import json
import os
import sys
from pathlib import Path

_TELEMETRY_DIR = Path('/home/jordaneal/scripts/playtest')


def _today_jsonl_path() -> Path:
    today = datetime.datetime.now().strftime('%Y%m%d')
    return _TELEMETRY_DIR / f'inversion_v0_{today}.jsonl'


def _ensure_dir():
    try:
        _TELEMETRY_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"inversion_telemetry: dir create failed: {e!r}", file=sys.stderr)


def emit(event: str, domain: str, payload: dict) -> bool:
    """Emit a telemetry event. Always-fire. Returns True on success, False on
    soft-fail (caller does not check; this is fire-and-forget).

    event: 'detected' | 'routed' | 'suppressed'
    domain: parser domain name (e.g. 'quest_accept')
    payload: arbitrary dict — merged into the line; caller controls fields.
    """
    _ensure_dir()
    record = {
        'ts': datetime.datetime.now().isoformat(timespec='seconds'),
        'event': event,
        'domain': domain,
    }
    record.update(payload or {})
    try:
        with open(_today_jsonl_path(), 'a', encoding='utf-8') as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + '\n')
        return True
    except Exception as e:
        print(f"inversion_telemetry: emit failed: {e!r}", file=sys.stderr)
        return False


def emit_parse_outcome(domain: str, campaign_id: int, parse_result: dict,
                       route: str = 'silent') -> bool:
    """Convenience wrapper — flattens a parser's structured outcome dict
    into a telemetry record. Idempotent in semantics (one line per parser
    invocation, regardless of fire status).

    Always emits exactly one line. The 'event' classification follows:
      - dedup_suppressed=True OR feature_disabled=True → 'suppressed'
      - confidence in ('high','medium') AND fired=True → 'detected' or 'routed'
        (the caller distinguishes by passing route='engine'/'suggester' or
        'silent' for not-yet-routed)
      - else (confidence='low', no verb) → 'suppressed' with reason
    """
    fired = bool(parse_result.get('fired', False))
    confidence = parse_result.get('confidence', 'low')
    dedup = bool(parse_result.get('dedup_suppressed', False))
    disabled = bool(parse_result.get('feature_disabled', False))

    if disabled:
        event = 'suppressed'
        reason = 'feature_disabled'
    elif dedup:
        event = 'suppressed'
        reason = 'dedup'
    elif not fired:
        event = 'suppressed'
        reason = 'low_confidence'
    elif route == 'silent':
        event = 'detected'
        reason = None
    else:
        event = 'routed'
        reason = None

    payload = {
        'campaign_id': campaign_id,
        'confidence': confidence,
        'matched_verb': parse_result.get('matched_verb', ''),
        'matched_quest_id': parse_result.get('matched_quest_id'),
        'matched_quest_title': parse_result.get('matched_quest_title', ''),
        'dedup_suppressed': dedup,
        'feature_disabled': disabled,
        'route': route if event == 'routed' else None,
        'fired': fired,
    }
    if reason:
        payload['reason'] = reason
    return emit(event, domain, payload)


def _reset_for_tests():
    """Test-only helper: delete today's telemetry file. Tests use a temp dir
    via monkeypatching of _TELEMETRY_DIR instead in practice."""
    p = _today_jsonl_path()
    if p.exists():
        os.unlink(p)


# ── §1b.1 Clarification Handshake taxonomy (S77) ──────────────────────────────
#
# New event types for the clarification primitive. Per S77 dispatch, event
# names are stable strings; payloads carry parser_domains, parser_confidences,
# layer, time_to_resolve_ms (where applicable), recursion_iteration.
#
# Primary path events:
#   clarification_in_fiction_fired           — pending flag set, LLM narrates
#   clarification_in_fiction_resolved        — second-pass HIGH committed
#   clarification_in_fiction_compliance_failure — LLM narrated action despite
#                                                  pending directive
#
# Fallback path events:
#   clarification_layer_a_fired              — direct Layer A
#   clarification_layer_a_fallback_fired     — after in-fiction second-pass
#   clarification_layer_b_fired              — direct Layer B
#   clarification_layer_b_fallback_fired     — after in-fiction second-pass
#
# Resolution events:
#   clarification_resolved                   — operator paste or OOC committed
#   clarification_skipped                    — explicit skip
#   clarification_expired                    — Layer B timeout, no reply
#   clarification_recursion_escalated        — Layer B 2nd ambiguous reply
#   clarification_recursion_manual           — Layer B 3rd ambiguous escalation
#   clarification_cap_hit                    — per-campaign session cap exceeded
#   clarification_pending_cleared_no_resolution — pending cleared without commit
#
# Calibration telemetry (per GPT post-council Flag 2):
#   parser_calibration_snapshot              — per-parser fire-rate rolling window
#   clarification_density_snapshot           — per-scene clarification frequency


CLARIFICATION_DOMAIN = 'clarification'


def emit_clarification_event(event: str, campaign_id: int,
                              payload: dict | None = None) -> bool:
    """Convenience wrapper for §1b.1 clarification events. Always-fire
    discipline. Domain is fixed to 'clarification'; event names from the
    taxonomy above.
    """
    body = {'campaign_id': campaign_id}
    if payload:
        body.update(payload)
    return emit(event, CLARIFICATION_DOMAIN, body)


# ── Calibration snapshots ──────────────────────────────────────────────────
#
# Rolling-window counters for per-parser fire rates (calibration drift
# detection per GPT post-council Flag 1+2). The snapshot fires every N
# parser invocations; the in-memory counter is per-process (resets on
# restart) — telemetry consumer aggregates across runs.

_PARSER_INVOCATION_COUNT = 0
_PARSER_CONFIDENCE_COUNTS: dict[str, dict[str, int]] = {}
_CALIBRATION_SNAPSHOT_INTERVAL = 50  # per spec; v0.x tunable


def record_parser_invocation(domain: str, confidence: str) -> None:
    """Increment per-parser per-confidence counter; fire calibration
    snapshot every _CALIBRATION_SNAPSHOT_INTERVAL invocations. Soft-fail
    — telemetry never blocks parser path."""
    global _PARSER_INVOCATION_COUNT
    try:
        bucket = _PARSER_CONFIDENCE_COUNTS.setdefault(domain, {})
        bucket[confidence] = bucket.get(confidence, 0) + 1
        _PARSER_INVOCATION_COUNT += 1
        if _PARSER_INVOCATION_COUNT % _CALIBRATION_SNAPSHOT_INTERVAL == 0:
            emit('parser_calibration_snapshot', 'inversion', {
                'invocations': _PARSER_INVOCATION_COUNT,
                'per_parser': dict(_PARSER_CONFIDENCE_COUNTS),
            })
    except Exception:
        pass


def _reset_calibration_for_tests():
    """Test-only — clears counters."""
    global _PARSER_INVOCATION_COUNT
    _PARSER_INVOCATION_COUNT = 0
    _PARSER_CONFIDENCE_COUNTS.clear()


# ── §82 candidate — Instruction-Side Compliance telemetry (S81) ──────────
#
# Generic-with-payload event per S80 council convergent (GPT + Gemini Q6).
# Single event type accommodates all directive surfaces; directive_name field
# disambiguates which directive failed compliance. Grep surface preserved:
#   grep '"directive_name": "central_thread"'
# works equivalently to per-event-type grep with zero schema coupling.
#
# S77's `clarification_in_fiction_compliance_failure` event refactors to fire
# via this generic surface with `directive_name="pending_clarification"`.
#
# Payload shape per dispatch:
#   directive_name: str       — e.g., "central_thread", "pending_clarification"
#   severity: 'LOW' | 'MEDIUM' | 'HIGH'
#   narration_excerpt: str    — capped 200 chars
#   detector: str             — detection method (e.g., "post_llm_grep")
#   campaign_id: int
#   confidence: float         — detector's confidence in violation
#   directive_intent: str     — what the directive instructed (capped 100 chars)

_NARRATION_EXCERPT_CAP = 200
_DIRECTIVE_INTENT_CAP = 100


def record_directive_compliance_failure(
    directive_name: str,
    severity: str,
    narration_excerpt: str,
    detector: str,
    campaign_id: int,
    confidence: float,
    directive_intent: str,
) -> bool:
    """Record a §82-candidate directive-compliance-failure event. Generic
    payload shape per S80 council Q6 lock. Single event type — directive_name
    disambiguates per-directive grep surface without schema coupling.

    severity bands per S81 dispatch:
      LOW    — detector confidence < 0.5; soft signal worth aggregating
      MEDIUM — detector confidence 0.5-0.8; actionable empirical signal
      HIGH   — detector confidence > 0.8; near-certain violation

    Caps:
      narration_excerpt → 200 chars
      directive_intent  → 100 chars
    """
    if severity not in ('LOW', 'MEDIUM', 'HIGH'):
        severity = 'MEDIUM'
    excerpt = (narration_excerpt or '')[:_NARRATION_EXCERPT_CAP]
    intent = (directive_intent or '')[:_DIRECTIVE_INTENT_CAP]
    payload = {
        'directive_name': directive_name,
        'severity': severity,
        'narration_excerpt': excerpt,
        'detector': detector,
        'campaign_id': campaign_id,
        'confidence': float(confidence),
        'directive_intent': intent,
    }
    return emit('directive_compliance_failure', 'inversion', payload)
