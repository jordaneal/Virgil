"""Mechanical hints parser — Phase 11.1.

Advisory parser. Reads DM narration, returns a list of suggested Avrae
commands the player should run. Suggestion-only, never executes.

Public API:
    parse_mechanical_hints(narration: str, campaign_id: int | None = None) -> list[str]

Hard invariants:
- Narration-only input. No player input, no character context, no scene state.
- Whitelisted output. Only commands matching ALLOWED_PREFIXES survive.
- No state writes. Reads strings, returns strings.
- Never raises. Returns [] on any failure.

S65.1 N-1 tightening:
- Transaction-verb gate: hints only emit when narration contains a
  transaction-completion verb (paid, handed, slid coins, etc.). Pure
  dialogue ("how much?", price quotes, disputes) drops to []
  with reason `no_transaction_verb`.
- Cross-turn dedup: if `campaign_id` is supplied, identical hints
  emitted in the last N entries for that campaign are suppressed
  with reason `recent_duplicate`. Process-local cache; bounded.
"""

import collections
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
# S65.1 N-1 — Transaction-verb gate
# ─────────────────────────────────────────────────────────

# Closed vocabulary. Narration must contain at least one of these surface
# forms (whole-word match, case-insensitive) for a `!game coin` hint to
# emit. Bare price mentions ("five silvers", "1sp each"), questions
# ("how much?"), and disputes ("they were 50c before") do NOT trigger
# emission. The 2026-05-14 baker scenario fired four hints across one
# real transaction + three dispute turns; with this gate, only the
# actual transaction turn (which contains "hands over"/"accepts payment"
# /"slid the coins") fires.
_COIN_TRANSACTION_VERBS = frozenset({
    # Noun-overlap traps EXCLUDED: 'hands' ('flour-dusty hands' body part),
    # 'places' ('in these places' locations). All other forms kept — they
    # have rare-or-archaic noun usage that doesn't surface in fantasy
    # narration. Whole-word lowercase match (re.findall pre-tokenizes).
    'paid', 'pays', 'paying', 'pay',
    'handed', 'handing',  # 'hands' excluded
    'gave', 'gives', 'giving',
    'passed', 'passes', 'passing',
    'slid', 'slides', 'sliding',
    'dropped', 'drops', 'dropping',
    'tossed', 'tosses', 'tossing',
    'flipped', 'flips', 'flipping',
    'exchanged', 'exchanges', 'exchanging',
    'pocketed', 'pockets', 'pocketing',
    'accepted', 'accepts', 'accepting',
    'received', 'receives', 'receiving',
    'took', 'takes', 'taking',
    'placed', 'placing',  # 'places' excluded
    'spent', 'spending', 'spends',
    'transferred', 'transfers',
    'counted', 'counts', 'counting',
})

# Rest commands (longrest/shortrest/lr/sr) don't gate on transaction verbs;
# they gate on explicit rest-completion narration ("the party beds down",
# "you take an hour to bind your wounds"). The LLM prompt already
# enforces this; no additional gate needed for rest hints.


def _narration_has_transaction_verb(narration: str) -> bool:
    """Return True if narration contains a transaction-completion verb.

    Whole-word case-insensitive match against the closed vocabulary.
    Does not look at price proximity — coarse-grained but sufficient: if
    the narration is pure dialogue, NO transaction verb fires. If even
    one fires, hints are allowed (validator will still drop malformed
    commands).
    """
    if not narration:
        return False
    tokens = re.findall(r"[a-zA-Z]+", narration.lower())
    return any(t in _COIN_TRANSACTION_VERBS for t in tokens)


# ─────────────────────────────────────────────────────────
# S65.1 N-1 — Cross-turn dedup
# ─────────────────────────────────────────────────────────

# Process-local LRU per campaign. Resets on bot restart (acceptable —
# duplicate-suppression window is short). Bounded to ~12 entries per
# campaign (≈3-4 turns worth of hints).
_RECENT_HINTS_BUFLEN = 12
_RECENT_HINTS_PER_CAMPAIGN: dict[int, collections.deque] = {}


def _get_recent_hints(campaign_id: int) -> list[str]:
    buf = _RECENT_HINTS_PER_CAMPAIGN.get(campaign_id)
    return list(buf) if buf else []


def _record_recent_hints(campaign_id: int, hints: list[str]) -> None:
    if not campaign_id or not hints:
        return
    buf = _RECENT_HINTS_PER_CAMPAIGN.setdefault(
        campaign_id, collections.deque(maxlen=_RECENT_HINTS_BUFLEN)
    )
    for h in hints:
        buf.append(h)


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
- Only suggest what the narration literally describes happening — coins
  must visibly change hands or be paid out, not merely mentioned.
- Bare price quotes are NOT transactions. If the narration only QUOTES
  a price ("Five silvers for the loaves", "it costs 5sp", "they were
  50c each before") with NO accompanying transaction action, output [].
- Questions about price are NOT transactions. "How much?" with the
  NPC answering does NOT trigger a hint until coins are paid.
- Disputes about price are NOT transactions. "They were 50c before"
  with the NPC re-stating a price does NOT trigger a hint.
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
Output: []

DISPUTE / QUOTE / QUESTION — these should all output []:

Example narration: "Baker smiles: 'Five silver pieces for the five
loaves, good folk.' The clink of a copper coin in the wooden counter
echoes softly."
Output: []
(The baker QUOTES a price; no transaction completes. The "clink" is
ambient sound, not a payment action.)

Example narration: "Baker chuckles, wiping his flour-dusty hands.
'The market's been tighter lately, but I'm still charging a silver a
loaf—your half-price was a kindness, not a new rate.'"
Output: []
(Pure dispute. NPC re-states a price; player hasn't accepted or paid.)

Example narration: "The baker nods. 'Five loaves, at half-price for a
traveling song—so five silvers total. Hand them over and they're yours,
fresh as the sunrise.'"
Output: []
(NPC requests payment. Player has not yet handed over coin. Wait
for the actual transaction-completion narration before emitting.)"""


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


def parse_mechanical_hints(narration, campaign_id: int | None = None):
    """Read DM narration, return list of suggested Avrae commands.

    Never raises. Returns [] on any failure.

    S65.1 N-1 — two-stage suppression:
      1. Transaction-verb gate (coin hints only): if narration has no
         transaction-completion verb, drop coin hints with reason
         `no_transaction_verb`. Rest hints (longrest/shortrest) are not
         gated this way — the LLM prompt's rest examples already require
         a clear rest-completion narrative.
      2. Cross-turn dedup: if `campaign_id` is provided, suppress hints
         that exactly match anything emitted in this campaign's last
         ~12 entries (≈3-4 turns).

    Telemetry:
      hint_extractor_emitted   — per-fire (campaign, hint, verb match)
      hint_extractor_suppressed — per-suppression (campaign, hint, reason)
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

        # Stage 1: prompt-extracted candidates → schema validator
        prevalidated = []
        for cand in candidates:
            if not isinstance(cand, str):
                dropped.append((str(cand)[:60], "not_in_whitelist"))
                continue
            ok, reason = _validate(cand)
            if ok:
                prevalidated.append(cand.strip())
            else:
                dropped.append((cand[:60], reason or "unknown"))

        # Stage 2: transaction-verb gate (coin hints only)
        narration_has_verb = _narration_has_transaction_verb(narration)
        for cand in prevalidated:
            is_coin = cand.startswith("!game coin")
            if is_coin and not narration_has_verb:
                dropped.append((cand[:60], "no_transaction_verb"))
                log(f"hint_extractor_suppressed campaign_id={campaign_id} "
                    f"hint={cand!r} reason=no_transaction_verb")
                continue
            validated.append(cand)

        # Stage 3: cross-turn dedup (process-local, optional)
        if campaign_id and validated:
            recent = set(_get_recent_hints(campaign_id))
            survived = []
            for cand in validated:
                if cand in recent:
                    dropped.append((cand[:60], "recent_duplicate"))
                    log(f"hint_extractor_suppressed campaign_id={campaign_id} "
                        f"hint={cand!r} reason=recent_duplicate")
                    continue
                survived.append(cand)
            validated = survived

        # Stage 4: record what survived for next turn's dedup
        if campaign_id:
            _record_recent_hints(campaign_id, validated)

        # Per-fire telemetry
        for v in validated:
            log(f"hint_extractor_emitted campaign_id={campaign_id} "
                f"hint={v!r} transaction_verb_present={narration_has_verb}")

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
