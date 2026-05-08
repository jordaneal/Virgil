"""Mechanical hints parser — Phase 11.1.

Advisory parser. Reads DM narration, returns a list of suggested Avrae
commands the player should run. Suggestion-only, never executes.

Public API:
    parse_mechanical_hints(narration: str) -> list[str]

Hard invariants:
- Narration-only input. No player input, no character context, no scene state.
- Whitelisted output. Only commands matching ALLOWED_PREFIXES survive.
- No state writes. Reads strings, returns strings.
- Never raises. Returns [] on any failure.
"""

import json
import re
import time

from cloud_router import route
from dnd_engine import log

# ─────────────────────────────────────────────────────────
# Whitelist + validator
# ─────────────────────────────────────────────────────────

ALLOWED_PREFIXES = ("!game ",)

MAX_CMD_LEN = 200

# Shell metacharacters / chaining / backticks. Newlines checked separately.
_BAD_CHARS = re.compile(r"[`;|&><$\\]")

# !game coin <amount> — single currency only. Multi-currency narration
# produces multiple commands (one per currency type) instead of using
# Avrae's multi-currency single-call form. Simpler validator, same outcome.
_COIN_RE = re.compile(r"^!game\s+coin\s+[+-]\d+(gp|sp|cp|ep|pp)$")

# !game longrest, !game shortrest, !game lr, !game sr — all four accepted.
_REST_RE = re.compile(r"^!game\s+(longrest|shortrest|lr|sr)$")


def _validate(cmd):
    """Return (valid: bool, drop_reason: str | None).

    drop_reason is one of:
      not_in_whitelist | malformed_currency
      length_exceeded  | invalid_chars
    """
    if not isinstance(cmd, str):
        return False, "not_in_whitelist"

    cmd = cmd.strip()
    if not cmd:
        return False, "not_in_whitelist"

    if len(cmd) > MAX_CMD_LEN:
        return False, "length_exceeded"

    if "\n" in cmd or "\r" in cmd:
        return False, "invalid_chars"

    if _BAD_CHARS.search(cmd):
        return False, "invalid_chars"

    if not cmd.startswith(ALLOWED_PREFIXES):
        return False, "not_in_whitelist"

    # Discriminate by second token: coin | longrest | shortrest | lr | sr
    parts = cmd.split(maxsplit=2)
    if len(parts) < 2:
        return False, "not_in_whitelist"
    sub = parts[1]

    if sub == "coin":
        return (True, None) if _COIN_RE.match(cmd) else (False, "malformed_currency")

    if sub in ("longrest", "shortrest", "lr", "sr"):
        return (True, None) if _REST_RE.match(cmd) else (False, "not_in_whitelist")

    return False, "not_in_whitelist"


# ─────────────────────────────────────────────────────────
# LLM call
# ─────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You read fantasy narration from a Dungeons & Dragons game and identify
when the narration shows the player needing to update their character
sheet via Avrae bot commands.

Output ONLY a JSON array of strings. Each string is one Avrae command.
No prose. No explanation. No markdown. No keys, no objects. Just an array.

Allowed commands:
- !game coin +Ngp  / !game coin -Ngp   (currencies: pp, gp, ep, sp, cp)
- !game longrest                        (or short alias: !game lr)
- !game shortrest                       (or short alias: !game sr)

Output rules:
- Empty array [] if no mechanical bookkeeping is implied.
- Only suggest what the narration literally describes happening.
- Never suggest rolls, attacks, spells, HP changes, or condition commands.
- Never invent amounts not in the narration.
- One currency per coin command. If narration mentions mixed currency
  (e.g. "5 gold and 2 silver"), emit two separate !game coin commands.
- Item acquisition / loss is OUT OF SCOPE — Avrae does not manage
  inventory. Do NOT emit any item, bag, or equipment commands. Inventory
  lives in D&D Beyond, not in our bookkeeping. Output [] for pure-loot
  narration with no currency.
- If the amount is vague ("a few coins"), do NOT emit the command —
  better to suggest nothing than guess wrong.
- If "rest" is mentioned but the type is not clear from context (short
  rest, long rest, overnight, until morning, an hour to recover, etc.),
  do NOT emit a rest command. Bare "you rest" is too vague.

Example narration: "You flip a gold piece to the merchant; he catches it
and pockets it with a grunt."
Output: ["!game coin -1gp"]

Example narration: "The chest creaks open, revealing a silver ring,
three gold coins, and a healing potion."
Output: ["!game coin +3gp"]

Example narration: "You hand over five gold and two silver to seal the
deal."
Output: ["!game coin -5gp", "!game coin -2sp"]

Example narration: "The party beds down for the night until dawn."
Output: ["!game longrest"]

Example narration: "You take an hour to bind your wounds and catch your
breath."
Output: ["!game shortrest"]

Example narration: "The bandit's blade nicks your arm as you parry."
Output: []

Example narration: "You rest."
Output: []"""


def _extract_json_array(text):
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


def parse_mechanical_hints(narration):
    """Read DM narration, return list of suggested Avrae commands.

    Never raises. Returns [] on any failure.
    """
    if not narration or not isinstance(narration, str):
        return []

    started = time.monotonic()
    raw_response = ""
    validated = []
    dropped = []

    try:
        response, _provider = route(
            messages=[{"role": "user", "content": narration}],
            task_type="extraction",
            system_prompt=SYSTEM_PROMPT,
        )
        raw_response = response or ""

        candidates = _extract_json_array(raw_response)
        if candidates is None:
            log(f"hint_parse: narration_chars={len(narration)} "
                f"raw_response={raw_response[:160]!r} "
                f"validated=[] dropped=[parse_failed] "
                f"latency_ms={int((time.monotonic() - started) * 1000)}")
            return []

        for cand in candidates:
            if not isinstance(cand, str):
                dropped.append((str(cand)[:60], "not_in_whitelist"))
                continue
            ok, reason = _validate(cand)
            if ok:
                validated.append(cand.strip())
            else:
                dropped.append((cand[:60], reason or "unknown"))

    except Exception as e:
        log(f"hint_parse: error={e!r} "
            f"latency_ms={int((time.monotonic() - started) * 1000)}")
        return []

    log(f"hint_parse: narration_chars={len(narration)} "
        f"raw_response={raw_response[:160]!r} "
        f"validated={validated} "
        f"dropped={[f'{c}:{r}' for c, r in dropped]} "
        f"latency_ms={int((time.monotonic() - started) * 1000)}")
    return validated
