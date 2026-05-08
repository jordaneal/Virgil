# PHASE 6 — Actor Identity Reconciliation (spec)

**Status:** SPEC ONLY (Session 15). No implementation. Lock decisions before
shipping. Sub-items 6A/6B/6C correspond to ROADMAP entries.

**Problem source:** Session 8 lesson, surfaced by 2B.1 logging. Friend
multiplayer is gated on this; solo currently masks the bug because there's
only one identity at the table.

---

## 1. Problem statement

The system has multiple identity strings for one character entity, and
the matching layer between them does substring comparison that fails
when the strings have no overlap.

**The bug** (Session 8 logs, recorded at `SESSIONS.md` Session 8):

```
Avrae says:        'throx'           (lowercased Avrae character nickname)
Virgil batches as: 'Donovan Ruby'    (bound character display name)
Cache keyed by:    depends on sheet  (CharacterContext.name from embed)
```

`buffer.consume(actor_filter=['Donovan Ruby'])` returns 0 events because
the buffer holds events tagged `actor='throx'`. The substring matcher
(`avrae_listener.py:442`, `avrae_listener.py:462`) checks
`'donovan ruby' in 'throx' or 'throx' in 'donovan ruby'` — both false.
Roll-and-narrate flow breaks: the DM narrates without the roll context.

**Why solo masks it:** at a one-character table, the buffer's entire
contents are this one player's events. Even when matching fails, the
events expire after 75s (`EVENT_TTL_SECONDS`), the next narrative turn
extracts no Avrae context, and the bot improvises around the missing
roll. Single-player play looks "fine" because the narrative is
plausible without the roll number — the missing data is invisible.

Multiplayer surfaces it badly: when actor A's events live in the buffer
under `'throx'` and actor B speaks, B's `buffer.consume(['B's name'])`
should pull NOTHING (correct) but currently might still pull A's events
via the substring matcher's permissive comparison, OR (more often)
pulls nothing for either actor because neither name canonicalizes.

---

## 2. Identity sources (enumerated from current code)

Each entry: name source, where it's set, where it's read, line citations.

### 2.1. **`dnd_characters.name`** — bound character display name
- **Set by** `bind_character(campaign_id, controller_id, name, ...)` —
  `dnd_engine.py:509-528`. The `name` is whatever the user typed in
  `/bindchar`. No normalization.
- **Read by** `get_characters` (`dnd_engine.py:450`),
  `get_character_by_controller` (`dnd_engine.py:465`).
- **Used in** `discord_dnd_bot.py:498-545` — `display = char['name']`,
  passed to `batcher.add(user_display=display, ...)`.
- **User-facing** in PARTY block (`dnd_engine.py:2330`) and as
  acting-character labels in narration footers.

### 2.2. **`CharacterContext.name`** — sheet embed character name
- **Set by** `parse_avrae_sheet_embed(embed)` —
  `dnd_orchestration.py:155-171`. Source: `embed.author.name`
  (with strip + trailing-paren-marker cleanup at
  `avrae_listener.py:142-144`). For sheet embeds (`!sheet`/`!beyond`),
  this is whatever DDB / Avrae sheet shows.
- **Used as** `_CHARACTER_CACHE` key (`dnd_orchestration.py:135, 144`).
  `set_cached_context(ctx)` does `_CHARACTER_CACHE[ctx.name] = ctx` —
  exact-string keying.
- **Looked up by** `get_cached_context(name)`
  (`dnd_orchestration.py:138`) — exact-string match.
- **Cache miss** → bot operates without sheet data
  (`dm_respond: no cached context for 'Donovan Ruby'` log line).

### 2.3. **Avrae roll-event `actor` field**
- **Set by** `_extract_actor(embed, raw, message)` —
  `avrae_listener.py:138-152`. Priority: `embed.author.name` (post
  trailing-marker strip) → title regex `r"^([A-Z][\w'-]+(...))\s+(?:attacks|makes|casts|...)\b"`
  → fallback `'Someone'`.
- **Stored on** `event['actor']` in the dict produced by
  `parse_avrae_embed` (`avrae_listener.py:381`).
- **Critically:** roll embeds use Avrae's character NICKNAME, which can
  diverge from the sheet name. Sheet says "Donovan Ruby"; roll embeds
  say "Throx" if that's the user's chosen Avrae nickname.

### 2.4. **`dnd_combat_state.character_name`** — init-driven combat state
- **Set by** `set_active_turn(campaign_id, controller_id, character_name, round_num)` —
  `dnd_engine.py:953-963`. Called from `_handle_init_event` when
  Avrae's `!init next` announces a turn.
- **Source** is `parse_init_event` (`avrae_listener.py:229`'s regex)
  which extracts `(?P<name>.+?)\s*\(<@!?(?P<controller_id>\d+)>\)`.
  So this name is "whatever Avrae rendered before the
  `(@user)` mention" — typically the Avrae nickname, not the sheet
  name.
- **Read by** `get_active_turn(campaign_id)` (`dnd_engine.py:970-987`)
  for the turn-gate in `on_message` (`discord_dnd_bot.py:519-535`).

### 2.5. **`dnd_characters.controller`** — Discord user ID (anchor)
- **Set by** `bind_character` (`dnd_engine.py:509`) — `controller_id`
  parameter, stored as TEXT.
- The only stable, unique-per-person anchor in the system. Names are
  user-mutable; controller IDs are Discord-managed.
- **Critically:** roll embeds DO NOT include controller_id in
  `parse_avrae_embed`'s output (`avrae_listener.py:380-389`). So for
  non-init events, controller_id cannot be recovered from the event
  alone. Init events DO carry it (`avrae_listener.py:298, 304`).

### 2.6. **`embed.author.name` of Avrae sheet vs roll embeds**
- For `!sheet` / `!beyond`: typically the DDB display name
  ("Donovan Ruby").
- For `!a` / `!cast` / `!check`: Avrae's character nickname (can be
  anything the user set).
- Both flow through `_extract_actor`, but produce different values for
  the same character.

### Summary table

| Source                                       | Set when                | Read when                  | Stable? |
| -------------------------------------------- | ----------------------- | -------------------------- | ------- |
| `dnd_characters.name`                        | `/bindchar`             | every narrative turn       | yes     |
| `CharacterContext.name` (cache key)          | `!sheet`/`!beyond` seen | every narrative turn       | yes     |
| Roll event `actor`                           | every roll              | `buffer.consume`           | per Avrae nickname |
| `dnd_combat_state.character_name`            | `!init next` events     | turn-gate                  | per Avrae init label |
| `dnd_characters.controller` (Discord user ID) | `/bindchar`             | `get_character_by_controller` | yes — true anchor |
| Avrae sheet `embed.author.name`              | `!sheet`/`!beyond`      | sheet parse + cache        | per DDB sheet     |

These can all diverge. Reconciliation is the problem.

---

## 3. 6A — Canonical form decision

**Confirmed: Avrae sheet name lowercased, with the existing
`canonicalize_name` shape.**

### Reasoning

- The Avrae sheet name is the closest thing to "what this character
  actually is" in the canonical sense — DDB-driven, stable across
  sessions, what the player sees on their character sheet.
- `dnd_characters.name` is user-typed at bind time and can drift
  (typos, casual nicknames). Not authoritative for mechanics.
- Roll-event `actor` is Avrae's NICKNAME, which is even more
  user-mutable than the sheet name.
- controller_id is the true anchor for identity but it isn't a name.
  The strings we need to match across systems (sheet embed, roll
  embed, init label, batched display) ARE names; matching requires
  comparing names against names. So the canonical FORM is a name,
  derived from the most authoritative name source (the sheet).
  controller_id remains the underlying anchor — `dnd_characters` rows
  key off it — but the canonical_name column is what the resolution
  layer compares against.

### Function signature

```python
def canonicalize_actor_name(name: str) -> str:
    """Symmetric normalization for actor identity matching.

    Returns the name with whitespace normalized (single-spaced, stripped),
    lowercased, with curly quotes ASCII-folded. Idempotent. Empty or
    None returns ''.

    NOT the same as engine.canonicalize_name — that strips honorifics
    and preserves case. This one lowercases (because Avrae roll embeds
    sometimes lowercase) and does NOT strip honorifics (player choices
    like "Sir Aldric" should match across sources, not collapse).
    """
```

**Normalization rules (locked):**
- Strip leading/trailing whitespace.
- Collapse internal whitespace runs to single spaces.
- ASCII-fold curly quotes (`‘’` → `'`, `“”` → `"`).
- Lowercase (so cross-source case differences match: sheet "Donovan
  Ruby" and roll-embed "donovan ruby" canonicalize to the same string).
- **No honorific stripping.** Diverges from `engine.canonicalize_name`
  on this one point. Rationale: different strings = different
  identities. If the system silently collapses "Sir Aldric" → "Aldric",
  a campaign with both characters becomes ambiguous. Determinism +
  explicit aliases beats silent normalization. The user opts in via
  `register_actor_alias` if they want two strings to resolve to the
  same identity.
- **No punctuation stripping** beyond whitespace + curly quotes.
  Avrae nicknames can include hyphens, apostrophes, etc.; aggressive
  normalization risks false-positive merges.

### Module location

Put `canonicalize_actor_name` in **`dnd_engine.py`** alongside the
existing `canonicalize_name` and `canonicalize_location_name`. It's a
deterministic engine-level normalizer; same shape as its neighbors.

Rationale: `dnd_orchestration` already imports `canonicalize_name` from
the engine. Putting actor-name normalization there too keeps all
identity-canonicalizers grep-able from one location and avoids a new
module.

### Why NOT use `controller_id` as the canonical_name value

Considered and rejected on identity-matching grounds. The strings we
need to compare across systems are names — sheet embeds, roll embeds,
init labels, batched displays all emit names. Resolution requires
comparing observed names against a canonical name. controller_id is
the right database anchor (and `dnd_characters` rows already key on
it) but it can't be the comparison surface — there's no source
emitting the controller_id alongside the name in the events we need
to match.

---

## 4. 6B — Reconciliation layer

### Where it lives

**New module: `dnd_orchestration` augmentation** — `IdentityRegistry`
class (or a flat-function set, equivalent). Lives next to
`_CHARACTER_CACHE` because cache lookups are the dominant consumer.

**Why orchestration not engine:** the engine owns SQLite and stable
state; orchestration owns runtime coordination logic (cache, intent
classifier, capability check). Identity reconciliation is runtime
coordination. Aligns with the "engine owns SQLite, orchestration owns
rules-engine logic" boundary (VIRGIL_MASTER §4).

### Schema additions (engine layer)

`dnd_characters` gains two columns (idempotent ALTER, same pattern as
existing migrations in `db_init`):

- `canonical_name TEXT` — lowercased sheet name. Single source of
  truth per character row. Set on `/bindchar` from the most recent
  sheet embed for the controller; refreshed when `cache_warm` or
  `parse_avrae_sheet_embed` produces a context.
- `aliases TEXT DEFAULT '[]'` — JSON list of alternate name forms
  observed for this character (Avrae nicknames from roll events,
  whatever Avrae's init label said, etc.). All lowercased.

These columns extend `dnd_characters` without changing the existing
single-write-path (`bind_character`); a new helper function (see API
below) maintains them.

### API shape (orchestration)

```python
def resolve_actor(campaign_id: int, raw_name: str) -> dict | None:
    """Map a raw observed name to a bound character row.

    STRICT-ONLY resolution:
      1. canonicalize_actor_name(raw_name) → cand
      2. Exact match against dnd_characters.canonical_name (alive, in
         this campaign).
      3. Exact match against any entry in dnd_characters.aliases.
      4. Miss → return None.

    No substring fallback. No prefix matching. No fuzzy logic.
    Aliases are saved data; substring matching is runtime guessing.
    We want saved data. If a real-world pattern emerges where two
    name strings legitimately refer to the same character, the
    operator calls register_actor_alias to record it durably — the
    system never decides the equivalence on its own.

    Returns the dnd_characters row dict (with canonical_name field
    populated) or None on miss. Never raises.
    """


def register_actor_alias(campaign_id: int, controller_id: str, alias: str) -> bool:
    """Append `alias` (canonicalized) to dnd_characters.aliases for the
    bound character of `controller_id` in `campaign_id`. Idempotent —
    no-op if alias already present. Returns True if the table changed,
    False if the alias was already there or the controller has no
    bound character. Logs `actor_alias_added: ...` on success."""


def refresh_canonical_name(controller_id: str, sheet_name: str, campaign_id: int = None) -> None:
    """Called when parse_avrae_sheet_embed produces a CharacterContext
    for a known controller. Sets dnd_characters.canonical_name to
    canonicalize_actor_name(sheet_name) for all alive bound characters
    of this controller (or just the campaign if specified). Logs
    canonical_name_refreshed: ... on update."""
```

### Reconciliation flow at runtime

**On bind** (`/bindchar`): existing `bind_character` is unchanged. A
new follow-up step:
1. Query the channel for the most recent `!sheet`/`!beyond` embed for
   this controller (already done by `_warm_character_cache_on_startup`
   pattern — reuse the scan).
2. If found, set `canonical_name = canonicalize_actor_name(embed.author.name)`.
3. If not found, leave `canonical_name = canonicalize_actor_name(name)` —
   the bind name itself. Will be refreshed when the user `!sheet`s.

**On Avrae roll event** (`avrae_listener.parse_avrae_embed` →
`buffer.add`):
1. Before adding to the buffer, call
   `resolve_actor(campaign_id, event['actor'])`.
2. If it returns a row: replace `event['actor']` with the row's
   `canonical_name`. The buffer now stores canonical strings.
3. If None: log `unresolved_actor: campaign=N name='<raw>' (no
   canonical/alias match)` and add the event with the canonicalized
   raw actor name (lowercased, stripped) — NOT promoted to anyone's
   identity. The event sits in the buffer; if no narrative turn pulls
   it within `EVENT_TTL_SECONDS` (75s), it expires. Persistent
   unresolution shows up in logs as a pattern the operator can
   investigate and resolve via `register_actor_alias`.

**On batched narrative turn** (`_dm_respond_and_post` line ~897):
1. Existing code: `actor_names` is built from `user_display` strings
   (the bound names).
2. Replace with: `actor_names_canonical = [resolve_actor(...).canonical_name for each]`.
3. Pass `actor_names_canonical` to `buffer.consume`.
4. Buffer.consume's matcher becomes EXACT equality on canonicalized
   strings (drop the substring `in` test). Both sides are canonical;
   exact match is the right semantic.

### Strict-only resolution — locked

Substring matching is **REJECTED** as a resolution path.

Rationale:
- Substring matching is runtime guessing. Aliases are saved data.
  We want saved data, not guesses. The distinction is the entire
  point of Phase 6 — the current bug is exactly that the substring
  matcher tries to do reconciliation work that should be explicit.
- Saved aliases are auditable, durable across restarts, and have a
  clear authority story: a human or a sheet refresh added them.
  Substring matches have none of those properties.
- "Smart" name resolution that occasionally false-positives is worse
  than dumb resolution that consistently misses — the latter
  surfaces the gap; the former hides it.

Operational consequence: when an unrecognized name appears (new Avrae
nickname, edge-case rendering), the system degrades silently — logs
the miss, doesn't narrate that actor's roll, the player calls
`register_actor_alias` (or whatever surface fronts it) to fix the
match permanently. The fix is operator action, not heuristic.

### Why not an in-memory dict instead of schema columns

Considered. Rejected for two reasons:
1. Bot restart drops the dict; aliases observed across past sessions
   would have to be re-discovered. The whole point of S14 cache-warm
   was to eliminate post-restart degradation.
2. Persisting in `dnd_characters` aligns with the existing data model
   ("the engine owns canonical state"). An in-memory dict is a
   different category of state with different staleness semantics.

---

## 5. 6C — Live verification plan

### Setup

Need TWO bound characters in the same campaign. Solo today's campaign
17 won't surface multi-actor reconciliation. Recommended:
1. Stand up a second test campaign (`/setcampaign`-controlled) with
   two `/bindchar` entries from two different Discord accounts (or one
   account with two characters via `/bindchar` + `/character` in
   Avrae).
2. Have each character `!sheet` once so cache + canonical_name populate
   for both.

### Test sequence (deterministic, no LLM dependence)

**Test 1 — single-character canonical match (smoke test):**
- Char A binds as "Aldric". `!sheet` shows "Aldric the Bold".
  After bind: `canonical_name='aldric the bold'`. After warm:
  `_CHARACTER_CACHE['Aldric the Bold']` populated.
- Player A rolls `!a longsword`. Avrae embed actor = "Aldric the Bold".
- Buffer.add → resolve_actor canonicalizes 'aldric the bold' →
  buffer event tagged `actor='aldric the bold'`.
- Player A types narrative. `actor_names_canonical = ['aldric the bold']`.
- `buffer.consume(['aldric the bold'])` → exact match → returns the
  attack event. Narration includes the to-hit + damage.
- **Pass:** `buffer.consume: 1 events for actors=['aldric the bold']`.

**Test 2 — Avrae nickname diverges from sheet name:**
- Char B binds as "Throx Donovan". `!sheet` shows "Throx Donovan".
  Player sets Avrae nickname to "throx" via Avrae's `!character`
  system.
- Player B rolls `!a dagger`. Avrae embed actor = "throx" (NOT the
  sheet name).
- Buffer.add → `resolve_actor(campaign_id, 'throx')` →
  canonicalize_actor_name('throx') = 'throx' → exact match against
  canonical_name='throx donovan'? No. Exact match against any
  alias? No (none registered yet). Returns None.
- Log: `unresolved_actor: campaign=N name='throx' (no canonical/alias
  match)`. Event stored with `actor='throx'`.
- Player B narrative turn: `actor_names_canonical=['throx donovan']`.
  `buffer.consume(['throx donovan'])` returns 0 events. Narration
  fires without the roll context. Log line shows the miss.
- **Operator action**: notices the `unresolved_actor:` log, calls
  `register_actor_alias(campaign_id, controller_id='B's id', alias='throx')`.
  `dnd_characters.aliases` now contains `["throx"]` for B's row.
- Next time B rolls with the 'throx' nickname:
  `resolve_actor(...)` step 2 misses but step 3 (alias match) hits.
  Event tagged `actor='throx donovan'` (canonical). Narration consumes
  it cleanly.
- **Pass:** First roll degrades silently with logged miss; after
  manual alias registration, all subsequent rolls match. Aliases
  persist across bot restart (column on `dnd_characters`).

**Test 3 — cross-actor isolation:**
- A and B both rolled this turn. Buffer holds events tagged
  `actor='aldric the bold'` and `actor='throx donovan'`.
- A's narrative turn fires alone. `actor_names_canonical = ['aldric the bold']`.
- `buffer.consume(['aldric the bold'])` returns ONLY A's event;
  B's event remains in the buffer untouched.
- **Pass:** A's narration references A's roll only; B's event is
  available for B's next turn.

**Test 4 — combat turn-gate compatibility:**
- Init begin. Both A and B in init.
- Avrae announces "Throx Donovan's turn (@user_b_id)" → `parse_init_event`
  extracts `name='Throx Donovan'`, `controller_id='user_b_id'`.
- `set_active_turn` writes `character_name='Throx Donovan'`.
- A tries to act → turn-gate (`discord_dnd_bot.py:519`) checks
  `active['controller_id']` against `message.author.id`. A's user_id
  ≠ `user_b_id` → ⏳ react and bail.
- **Pass:** Turn-gate respects controller_id (not name) — already
  correct in current code. Reconciliation doesn't break this; the
  active_turn record is still keyed by controller. (Document that
  combat coordination uses controller_id as anchor, name is for display.)

**Failure-mode test 5 — unresolved actor:**
- Roll event with actor name that matches nothing (e.g. typo in
  Avrae nickname, or character not yet bound).
- Buffer.add logs `unresolved_actor: ...` and stores raw.
- Buffer event eventually expires via TTL or is consumed by the
  next narrative turn that happens to match via substring (or doesn't).
- **Pass:** No crash; system degrades to current behavior (event
  unmatched, narration improvises).

---

## 6. Failure modes

### 6.1. Canonical-form collision (two players, same canonical name)

Two characters in the same campaign with identical canonicalized
sheet names. Discord-side they're different controllers (always);
Virgil-side their canonical_name string collides.

**Resolution under strict-only:** `resolve_actor` does not have a
controller_id input for non-init events, so when two rows match
exactly on `canonical_name` it has no signal to disambiguate.
Behavior: log `ambiguous_actor: campaign=N name='<x>' matched_rows=[id_a, id_b]`
and return None (degrade to unresolved). The roll's narrative effect
is lost on that turn; the operator handles the collision by renaming
one character (registers an explicit alias for distinctness, or
edits the character at the source). The system NEVER picks a row
from an ambiguous match.

This is rare (two players in one campaign with identical sheet names
is unusual) and the failure mode is loud (logged + degrades, doesn't
silently misroute). Acceptable for v1.

### 6.2. Avrae nickname change mid-campaign

Player rebinds in Avrae from "throx" to "donovan-the-bold" between
sessions. Existing buffer events for the old nickname are stale (TTL
75s, irrelevant after a few minutes). New roll events use the new
nickname. Substring fallback may or may not match the new nickname
against existing aliases.

**Resolution:** when a new nickname is observed, register it as an
alias via `register_actor_alias`. Old nicknames remain in the alias
list — they're append-only unless a manual prune happens. Storage
cost is trivial (text JSON, dozens of entries max per character over
the lifetime of a campaign).

### 6.3. Character with no Avrae binding yet

Player has a `dnd_characters` row from `/bindchar` but hasn't run
`!sheet`/`!beyond` yet. `canonical_name = canonicalize_actor_name(name)`
defaults to the bind name. No aliases. Cache is empty (no
CharacterContext).

**Resolution:** `resolve_actor` works against canonical_name (the bind
name lowercased) — exact match. When the player eventually `!sheet`s,
`refresh_canonical_name` updates the canonical_name column from the
sheet's `embed.author.name`. The bind name becomes an alias if the
sheet name differs. No data loss; aliases accumulate.

### 6.4. Sheet name changes after binding

Player edits character on DDB; new `!sheet` shows the new name.
`refresh_canonical_name` overwrites the canonical_name column.
The OLD name should be appended as an alias automatically before
overwrite. (Spec note: `refresh_canonical_name` performs the
overwrite + auto-alias-append in one transaction.)

### 6.5. Avrae sends `'Someone'` (fallback case)

`_extract_actor` falls back to the literal string `'Someone'` when
nothing else is identifiable (`avrae_listener.py:152`).
`canonicalize_actor_name('Someone')` returns `'someone'`. This will
NOT match any real character. Buffer event is stored, narration
turn fires with `actor_names=['donovan ruby']` or similar, no match,
event stays in buffer until TTL.

**Resolution:** `'someone'` is NOT promoted to anyone's alias.
`resolve_actor` checks for the literal `'someone'` and returns None
explicitly, with log line `unresolved_actor_fallback: ...`. No
data corruption; the event simply doesn't get narrated. This
is correct behavior — we don't know who acted, so we don't claim
to.

### 6.6. Solo bot, single character, current state

Today's campaign 17 with Donovan Ruby has ONE bound character, ONE
controller, one cache entry. The current substring matcher works
because both 'Donovan Ruby' (bound name) and 'Donovan Ruby' (sheet
name) are identical. Phase 6 doesn't break this — it adds the
canonical_name column (initialized to the lowercased bind name on
migration) and the resolve_actor function (single-row case is
trivially handled).

---

## 7. Migration impact on campaign 17

Pre-migration state (current, observed in `dnd_characters` line 32):
- `id=32, name='Donovan Ruby', race='Dwarf', class='Rogue', level=1, controller='691905804965773362', alive=1`

Migration steps:
1. `ALTER TABLE dnd_characters ADD COLUMN canonical_name TEXT` (idempotent
   per `PRAGMA table_info` check).
2. `ALTER TABLE dnd_characters ADD COLUMN aliases TEXT DEFAULT '[]'`.
3. Backfill: `UPDATE dnd_characters SET canonical_name = lower(trim(name))
   WHERE canonical_name IS NULL`. (If `dnd_characters.name` has curly
   quotes / multi-space, run through Python normalizer instead of pure
   SQL.)

Post-migration state:
- `id=32, name='Donovan Ruby', canonical_name='donovan ruby', aliases='[]', ...`

Live-verification on campaign 17 after migration:
- `_warm_character_cache_on_startup` runs → finds the most recent
  Donovan Ruby `!sheet`/`!beyond` embed → calls
  `refresh_canonical_name(controller='691905804965773362', sheet_name='Donovan Ruby', campaign_id=17)`.
- canonical_name was already 'donovan ruby' (from backfill); no change.
- Donovan rolls `!a dagger` → Avrae embed actor = 'Donovan Ruby' (or
  whatever Avrae's nickname currently is for the Donovan character).
- `resolve_actor(17, 'Donovan Ruby')` → canonicalizes to
  'donovan ruby' → exact match against canonical_name → returns the
  row. Buffer event tagged `actor='donovan ruby'`.
- Narrative turn: `actor_names_canonical=['donovan ruby']` →
  `buffer.consume` exact match → returns the event.

**Single-character solo case is fully covered with no behavior change
for the user.** The only observable difference is the journal lines:
existing `buffer.consume: 1 events for actors=['Donovan Ruby']` becomes
`buffer.consume: 1 events for actors=['donovan ruby']` (lowercased).
That's a log-format change only.

---

## 8. Out of scope (explicitly)

- **Narration address forms.** Whether the DM calls a character "Sir
  Bingus" or "Bingus" or "Bingo" in narration prose is a downstream
  narration-policy concern, NOT identity resolution. Phase 6 does not
  modify the prompt-rendering pipeline. `dnd_characters.name` and
  `CharacterContext.name` continue to feed the prompt as today; the
  new `canonical_name` column exists ONLY for cross-system matching
  and is never directly rendered.
- **Substring or fuzzy resolution.** Strict-only locked above. If a
  real-world pattern emerges, the operator records it via
  `register_actor_alias` — the system never decides equivalence on
  its own.
- Cross-campaign identity (two campaigns, same player, same
  character). Each campaign is a fresh canonical scope.
- DDB integration beyond what's already plumbed (sheet embeds via
  Avrae). Phase 6 doesn't ingest DDB directly.
- Bot-side character renaming. The user changes their character name
  via `/bindchar` (which creates a new row, soft-retires the old).
  Aliases append; no rename flow.

---

## 9. Open questions for review

These don't need to be answered to ship; they're flagged so future
review can resolve them:

1. **Operator surface for `register_actor_alias`.** Function exists
   in orchestration; needs a calling surface (slash command? log
   pattern that prompts manual SQL?). v1 ships the function; the
   slash-command wrapper can come later. For solo-Donovan-Ruby the
   function won't fire anyway.
2. **`last_active_at` column for ambiguity tie-break.** Defer until
   collision is observed.

---

## 10. Implementation order (when this ships)

Not part of the spec, but for sanity:
1. `canonicalize_actor_name` in `dnd_engine` + tests.
2. Schema migration (canonical_name + aliases columns) + idempotent
   backfill.
3. `resolve_actor`, `register_actor_alias`, `refresh_canonical_name`
   in `dnd_orchestration` + tests. Strict-only resolution per §4.
4. Wire `parse_avrae_embed` → `buffer.add` to call `resolve_actor`
   and tag events with canonical strings (or canonicalized raw on
   miss + log line).
5. Wire `_dm_respond_and_post` to resolve actor_names to canonical
   before `buffer.consume`.
6. Drop substring matching in `RollBuffer.consume` / `recent` —
   exact-equality on the canonicalized strings.
7. `_warm_character_cache_on_startup` → also refresh canonical_name
   for each warmed character.
8. Wire `bind_character` follow-up to set canonical_name from latest
   sheet embed if available.
9. Live verify per §5.
