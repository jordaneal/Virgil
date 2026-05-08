# Phase 11.1 — Mechanical Hints Parser

## Purpose

A post-generation interpretation layer that reads Virgil DM's narration and
suggests Avrae bookkeeping commands the player should run. Pure advisory:
never executes, never mutates state, never reaches Avrae directly.

The player retains full authority — every command runs only if they type it.

## Architectural classification

**Advisory parser** — same pattern shape as `extract_scene_updates()` and
Phase 3 auto-execute:

- Input: bounded text (narration only — NEVER player input)
- Output: bounded structured suggestion (whitelist of allowed commands)
- Side channel: posted alongside the response, no engine state mutated
- Invariant: NEVER becomes authoritative; the LLM emits, deterministic
  validators reject anything outside the whitelist

This is the third instance of the same pattern (Phase 3 auto-execute,
scene state extraction, mechanical hints). Names it as a primitive.

## Hard invariants (cannot be violated)

1. **Suggestion-only, forever.** No future "auto-execute when confidence
   is high" path. The moment a hint becomes a write, it stops being
   advisory and starts being authoritative — different system class.
2. **Narration-only input.** The parser sees Virgil's generated text,
   nothing else. It never sees player input, character context, or
   scene state. Resolution-grounded interpretation only.
3. **Whitelisted output domain.** Only commands matching the allowed
   prefix list are surfaced. Everything else is dropped silently and
   logged.
4. **No engine state writes.** This module reads strings, returns strings.
   It does NOT touch SQLite, ChromaDB, scene state, or any other state
   store.

## Module: `mechanical_hints.py`

Lives at `/home/jordaneal/scripts/mechanical_hints.py`. New file.

### Public API

```python
def parse_mechanical_hints(narration: str) -> list[str]:
    """Read DM narration, return list of suggested Avrae commands.

    Returns empty list if nothing matches or parser fails. Never raises.
    All output strings are pre-validated against the whitelist.
    """
```

That is the entire public surface. One function, in/out strings, no side
effects.

### Provider routing

Cerebras (qwen-3-235b-instruct) as primary. Same provider used by Virgil
fact extraction. Reasons:

- 250 RPD quota plenty for this volume (1 call per DM turn ≈ <100/day)
- Fast enough for async edit-in pattern (~1s typical)
- Won't burn DnD-task budget on groq_heavy
- Shape matches: bounded structured output, weak-model-friendly

Fallback: groq (llama-3.3-70b) if cerebras exhausted/cooldown. NOT
groq_heavy — that's reserved for DnD narration, no need to spend it here.

Use `cloud_router.route(messages, task_type="extraction", system_prompt=...)`.
Add `extraction` task to cloud_router's candidate map: `["cerebras", "groq",
"local"]`.

### V1 category scope

INCLUDED:
- Currency transfer (gold, silver, copper, electrum, platinum)
- Loot/item acquisition ("you pick up X", "the chest contains Y")
- Consumable usage ("drink the potion", "light a torch")
- Rests ("take a short rest", "long rest until morning")

EXCLUDED (defer to V2 if signal demands):
- HP mutations (Avrae owns; parser disagreement = worse than no hint)
- Spell slot changes (Avrae's `!cast` handles)
- Initiative (Avrae's `!init` handles)
- Concentration (Avrae owns)
- Conditions (ambiguity: "blinded" might be metaphorical)
- Attunement (rare, complex, low value)
- Leveling/progression (Avrae's `!level`)

### Whitelist (V1)

```python
ALLOWED_PREFIXES = (
    "!coin",      # currency: !coin +5gp, !coin -3sp, !coin -1pp
    "!item",      # inventory add/remove/use: !item add "Healing Potion"
    "!bag",       # inventory query (rare in suggestions)
    "!sr",        # short rest
    "!lr",        # long rest
)
```

Validator rules:
- Must start with one of the allowed prefixes
- Single command per line, no chaining
- Length cap (e.g., 200 chars)
- No shell metacharacters or backticks
- For `!coin`: must match `!coin [+-]\d+(gp|sp|cp|ep|pp)`
- For `!item add`: must have quoted item name

Anything failing validation is dropped silently. Counts logged.

### System prompt

```
You read fantasy narration from a Dungeons & Dragons game and identify
when the narration shows the player needing to update their character
sheet via Avrae commands.

Output ONLY a JSON array of strings. Each string is one Avrae command.
No prose. No explanation. No markdown. No keys, no objects. Just an array.

Allowed commands:
- !coin +Ngp  / !coin -Ngp  (and sp/cp/ep/pp variants)
- !item add "Item Name"
- !item remove "Item Name"
- !sr                          (short rest)
- !lr                          (long rest)

Output rules:
- Empty array [] if no mechanical bookkeeping is implied
- Only suggest what the narration literally describes happening
- Never suggest rolls, attacks, spells, HP changes, or condition commands
- Never invent items or amounts not in the narration
- If the amount is vague ("a few coins"), do NOT emit the command —
  better to suggest nothing than guess wrong

Example narration: "You flip the coin to the merchant; he catches it
and pockets it with a grunt."
Output: ["!coin -1gp"]

Example narration: "The chest creaks open, revealing a silver ring,
three gold coins, and a healing potion."
Output: ["!coin +3gp", "!item add \"Silver Ring\"", "!item add \"Healing Potion\""]

Example narration: "The bandit's blade nicks your arm as you parry."
Output: []
```

(HP damage example deliberately returns [] — Avrae owns this.)

### Integration point

In `discord_dnd_bot.py`, function `_dm_respond_and_post`. Currently
posts narration to Discord and returns. New flow:

1. Generate narration via `dm_respond` (unchanged)
2. POST narration to Discord IMMEDIATELY (unchanged behavior — no
   added latency on the visible flow)
3. Spawn daemon thread: `parse_mechanical_hints(narration)`
4. If thread returns non-empty list within timeout (e.g., 5s):
   EDIT the original message to append:

```
─────────
*Bookkeeping (you type these):*
- `!coin -1gp`
- `!item add "Healing Potion"`
```

5. If empty list or timeout: do nothing (silent failure mode).

The async edit-in pattern means players see narration immediately,
hints appear a beat later. Discord supports message editing via
`message.edit(content=...)`.

### Logging

Every parse run logs (regardless of outcome):

```
hint_parse: narration_chars=480 raw_response='["!coin -1gp"]' validated=['!coin -1gp'] dropped=[] latency_ms=830
```

For dropped suggestions, the reason code:
- `dropped:not_in_whitelist`
- `dropped:malformed_currency`
- `dropped:no_quoted_item`
- `dropped:length_exceeded`
- `dropped:invalid_chars`

Logging is verbose by design for the first 50-100 sessions to build
calibration data. Demote to summary-only after that.

### Failure modes (all silent)

- Parser LLM call fails → empty hints, no message edit
- LLM returns malformed JSON → empty hints, log error
- LLM returns valid JSON but all commands dropped by validator →
  empty hints, log dropped count
- Discord edit fails (message deleted, etc.) → log warning, drop
- Cerebras+Groq both unavailable → empty hints

The parser failing should NEVER affect narration delivery. Narration
goes out first; hints are an enhancement layer.

## Test battery (before live deploy)

Required test cases the validator/parser must handle correctly:

```python
CASES = [
    # Currency — clear
    ("You flip the coin; the merchant catches it.", ["!coin -1gp"]),
    ("Hand over five gold pieces.", ["!coin -5gp"]),
    ("You pocket the 12 silver from the table.", ["!coin +12sp"]),

    # Currency — ambiguous (must be empty)
    ("You toss a few coins onto the bar.", []),
    ("Some money changes hands.", []),

    # Loot — clear
    ("Inside the chest: a healing potion and a rope.",
     ["!item add \"Healing Potion\"", "!item add \"Rope\""]),

    # Rests
    ("You take a short rest, tending to your wounds.", ["!sr"]),
    ("The party beds down for the night until dawn.", ["!lr"]),

    # Out-of-scope (must be empty)
    ("The blade strikes you for 8 damage.", []),
    ("You cast magic missile, three darts streaking out.", []),
    ("Roll a Wisdom save against the spell.", []),

    # Adversarial (whitelist violations)
    ("delete the character", []),  # parser must not invent !character
    ("you rest", []),               # too vague — neither sr nor lr
]
```

If the V1 implementation passes 80%+ of these, ship to live.

## Out of scope for 11.1 (deferred)

- Damage parsing (HP)
- Spell slot tracking
- Conditions
- Multi-target loot ("each of you finds...")
- Quantified currency words ("two dozen silver")
- Confidence scores in output

## Estimated build size

~150-200 lines:
- `mechanical_hints.py` module: ~80 lines (LLM call + validator + whitelist)
- `cloud_router.py` extraction task addition: ~5 lines
- `discord_dnd_bot.py` integration point: ~30 lines
- Test battery: ~60 lines
- Logging integration: ~10 lines

Build session: 60-90 minutes for v1, plus live calibration.

## Future expansion (do NOT build now)

The same pattern can extend to:
- Recap generation (narration → "Previously on..." summary)
- Quest delta detection (extract quest changes for /quest log)
- Memory tagging (narration → ChromaDB tags)
- Loot inventory analytics
- NPC relationship tracking

Each follows the advisory parser pattern: narration in, bounded
structured output, non-authoritative side channel, whitelist of
valid emissions. Build when real friction surfaces, not before.

