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
