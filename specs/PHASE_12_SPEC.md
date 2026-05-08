# PHASE 12 SPEC — Campaign Skeleton

**Status:** Draft. Questions in §9 require sign-off before build.
**Author:** Claude (session 11), reviewed against PHASE_11_1_SPEC.md format.
**Scope owner:** Jordan.

---

## 1. Goal

Make the world remember itself across sessions. Today, the DM forgets the
blacksmith between sessions because nothing writes him down. Phase 12 adds
the persistence layer: NPCs, locations, an authored campaign skeleton, and
optionally a narrative-identity item ledger. The DM grounds every scene
against this state instead of improvising scene physics from scratch.

**The deeper architectural framing:** Phase 12 is not "AI memory." It is
introducing canonical narrative entities into the engine architecture.
Stable entity identity is the prerequisite for every higher-order narrative
system — relationships, faction state, emotional continuity, world-state
graphs. Without stable identity, all of those become noise built on noise.
Phase 12 doesn't implement those systems; it makes them safely buildable
later.

**Position in the three-track design** (see ROADMAP.txt design philosophy):
Phase 12 is the entry point to **Track 1 — Canonical World State**. Track 2
(Mechanical Authority, beginning with S9 equipment grounding) and Track 3
(Narrative Simulation) are sequenced after Track 1 stabilizes, because
each track's quality ceiling depends on the one below it. Phase 12's
restraint — NPCs + locations + skeleton, nothing more — is structural,
not aesthetic.

Phase 12 is **not** about rules enforcement (Track 2 / S9), encounter design,
or character progression. Those are separate phases. Scope here is strictly
narrative continuity.

---

## 2. Architectural invariants (carry forward, non-negotiable)

These are from the existing system; restating to ground the spec:

- Avrae owns mechanics; Virgil owns narrative.
- SQLite is authoritative structured state.
- LLMs never directly mutate structural state.
- All LLM calls go through cloud_router.
- Engine owns SQLite; orchestration owns rules-engine logic.
- Discord transport stays a thin shell.
- Advisory parser pattern: bounded text in → small LLM → strict structured
  output → deterministic validator → whitelist-restricted side effect.
  Phase 12 adds two new instances of this pattern (NPC, location).

---

## 3. Pillars (build in this order)

### 12A — Persistent NPCs

**Storage:** new SQLite table `dnd_npcs`, keyed by campaign_id +
canonical_name. See §6 for schema.

**Parser:** new module `npc_extractor.py`. Same pattern as
mechanical_hints. Input: DM narration text only. Output: JSON array of
candidate NPC objects. Validator: rejects entries without a proper name
(see §9.2 first-mention bar). Engine writer: insert-or-update by
canonical name match (see §9.1 name resolution).

**Prompt injection:** new block in dm_respond system prompt:

```
KNOWN NPCS IN THIS WORLD (do not invent names that contradict these):
- Garrick (blacksmith, Redhaven, last seen day 3): gruff, missing left ear
- Mira (innkeeper, Redhaven, last seen day 1): cautious, knows about the cult
[...]
```

Retrieval: top-N most recently mentioned + any NPC matching current
location. Cap at ~10 entries in prompt to control token cost.

### 12B — Persistent Locations

**Storage:** `dnd_locations` table, schema in §6. Hierarchical via
parent_location_id (e.g. "The Rusty Anchor" parent_id → "Redhaven").

**Parser:** `location_extractor.py`, same pattern. Extracts
`{name, type, parent, description_fragment}`.

**Prompt injection:** current location + immediate parent + sibling
locations player has visited. Capped similar to NPCs.

**Tag on scene_state:** add `current_location_id` column to
dnd_scene_state. Set/Get accessors in engine.

### 12C — Campaign skeleton authoring

**Storage:** Markdown file at `/home/jordaneal/scripts/campaigns/<id>/skeleton.md`.
Loaded fresh on every dm_respond call (cached in-memory with mtime check).

**Format** (open to revision — this is a starting structure):

```markdown
# Campaign: <name>

## Central conflict
<2-3 sentences. The thing the campaign is about.>

## Major hooks (3-5)
- Hook 1: <one sentence>
- Hook 2: <one sentence>
[...]

## Primary NPCs
### Garrick (blacksmith, Redhaven)
Motivation: Wants the cult exposed; lost his brother to them.
Voice: Gruff, plainspoken. Doesn't trust outsiders fast.

### Mira (innkeeper, Redhaven)
[...]

## Key locations
### Redhaven (town)
A coastal trade town. Tense — cult activity rising.

### The Rusty Anchor (tavern in Redhaven)
[...]

## Factions
### The Crimson Hand (cult)
Goal: Awaken something old. Currently recruiting.
```

**Authoring UX:** Jordan writes the markdown directly. Optional later: a
`/skeleton` Discord command that opens an editing flow with Virgil's
help. Out of scope for 12C v1.

**Prompt injection:** the entire skeleton file is prepended to the DM
system prompt as authoritative scaffolding. Token cost is real but
bounded — a 3000-token skeleton is fine; a 30000-token one is not.
Establish a soft size budget (~4000 tokens max, ~1500 typical).

### 12D — Item ledger (defer or v1?)

**Storage:** `dnd_items` table, schema in §6. Narrative identity only —
mechanical effect is a free-text hint, not enforced. Avrae + DDB
remain authoritative for mechanics.

**Parser:** new instance of advisory parser. Looks for "you find
{item}" / "you take {item}" patterns in narration. Strict whitelist on
output: must have a name, must be in a known location, must match a
narrative-acquisition phrasing.

**Prompt injection:** a "discovered items" list, scoped to recently
acquired or location-relevant.

**Recommendation: defer 12D to a Phase 12.1.** The first three pillars
are enough to make the world feel persistent. Items are a separate
shape of problem (DDB sync, mechanical hints) that overlaps with S14
and is better solved as one piece.

### 12E — Live calibration (mandatory before declaring shipped)

Run a real session of 60-90 minutes. Log every parser detection
(NPC, location). Manually review:

- False positives: did the parser create an NPC for "a guard"?
- False negatives: did a real named NPC slip through?
- Name reconciliation: did "Garrick" and "Garrick the Smith" merge or split?
- Prompt injection helping/hurting: is the DM grounding against the
  state, or being constrained by an over-specified skeleton?

Calibration informs prompt tightening before declaring 12 shipped.

---

## 4. Hard invariants for Phase 12 (DO NOT violate)

- Parsers are advisory. They write to SQLite via deterministic engine
  functions, not via LLM-generated SQL.
- Parsers have no access to player input, only DM output narration.
- Schema migrations are additive only. Existing campaigns must not break.
- Skeleton.md is authoritative over parser-detected state when they
  conflict. (See §9.7 for handling.)
- Prompt injection budget: total Phase 12 additions to the DM prompt
  must stay under 6000 tokens combined (skeleton + NPCs + locations).
  Hard cap. If retrieval blows it, drop NPCs first, then locations.
- **Single write-path per field.** `current_location_id` (and any other
  semi-authoritative scalar field) has exactly one mutation path
  defined in §9.9. Parsers may *propose* via a transition log; the
  engine writes.
- **No recursive authoritativeness.** Parser-created entities cannot
  promote themselves or trigger generation of further authoritative
  state. Specifically: a parser-detected NPC never auto-promotes to
  skeleton_origin=1; a parser-detected location never spawns a
  faction; nothing autonomously expands the world model. Skeleton
  promotion is a manual human action only (see §9.10).

---

## 5. What Phase 12 does NOT include

- Encounter / combat design. Separate phase.
- 5e rules enforcement (God Mode regression — listed S9). Separate.
- XP / character progression. Separate.
- Loot tables tied to CR. Separate.
- DDB API write-back for inventory. S14, deferred.
- Cross-campaign NPC sharing. Out of scope.
- NPC dialogue voice generation (TTS, distinct LLM voices per NPC).
  Out of scope.

---

## 6. Schema

```sql
CREATE TABLE IF NOT EXISTS dnd_npcs (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id       INTEGER NOT NULL,
    canonical_name    TEXT    NOT NULL,
    aliases           TEXT    DEFAULT '[]',  -- JSON array of alt names
    role              TEXT    DEFAULT '',    -- "blacksmith", "innkeeper"
    location_id       INTEGER,                -- FK dnd_locations, nullable
    description       TEXT    DEFAULT '',    -- short, parser-extracted
    skeleton_origin   INTEGER DEFAULT 0,     -- 1 if from skeleton.md
    mention_count     INTEGER DEFAULT 1,     -- recurrence strength
    origin_excerpt    TEXT    DEFAULT '',    -- 100-char excerpt from first mention
    first_mentioned   TEXT    NOT NULL,      -- ISO timestamp
    last_mentioned    TEXT    NOT NULL,
    UNIQUE (campaign_id, canonical_name)
);
CREATE INDEX IF NOT EXISTS idx_npcs_campaign ON dnd_npcs(campaign_id);
CREATE INDEX IF NOT EXISTS idx_npcs_location ON dnd_npcs(location_id);

CREATE TABLE IF NOT EXISTS dnd_locations (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id         INTEGER NOT NULL,
    canonical_name      TEXT    NOT NULL,
    aliases             TEXT    DEFAULT '[]',
    type                TEXT    DEFAULT '',  -- "town", "dungeon", "tavern"
    parent_location_id  INTEGER,              -- FK self, nullable
    description         TEXT    DEFAULT '',
    skeleton_origin     INTEGER DEFAULT 0,
    mention_count       INTEGER DEFAULT 1,
    origin_excerpt      TEXT    DEFAULT '',
    first_mentioned     TEXT    NOT NULL,
    last_mentioned      TEXT    NOT NULL,
    UNIQUE (campaign_id, canonical_name)
);
CREATE INDEX IF NOT EXISTS idx_locations_campaign ON dnd_locations(campaign_id);

ALTER TABLE dnd_scene_state ADD COLUMN current_location_id INTEGER DEFAULT NULL;

-- Phase 12.1 (deferred):
CREATE TABLE IF NOT EXISTS dnd_items (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id       INTEGER NOT NULL,
    name              TEXT    NOT NULL,
    narrative_effect  TEXT    DEFAULT '',
    mechanical_hint   TEXT    DEFAULT '',
    found_in_location INTEGER,
    found_at          TEXT    NOT NULL,
    holder            TEXT    DEFAULT 'unclaimed',  -- character name or unclaimed
    UNIQUE (campaign_id, name, found_at)
);
```

`skeleton_origin=1` flag: distinguishes "the campaign author wrote this
person down" from "the parser detected this person mid-session". Used
in conflict resolution (skeleton wins).

---

## 7. Parser scope per module

### npc_extractor.parse_npcs(narration: str) -> list[dict]

Returns list of:
```json
{
  "name": "Garrick",
  "role": "blacksmith",
  "location_hint": "Redhaven",
  "description_fragment": "gruff, missing his left ear"
}
```

**Validator rules:**
- `name` must match `^[A-Z][\w'\-]+(\s+[A-Z][\w'\-]+){0,2}$` (1-3
  capitalized words). Drops "the guard", "a hooded figure", "someone".
- `role` is optional but recommended.
- `description_fragment` capped at 100 chars.
- Drop entries where name is in a stoplist (common pronouns, generic
  fantasy nouns: "Lord", "Lady", "Sir" without a following name).

### location_extractor.parse_locations(narration: str) -> list[dict]

Returns list of:
```json
{
  "name": "The Rusty Anchor",
  "type": "tavern",
  "parent_hint": "Redhaven",
  "description_fragment": "smoky, low ceilings"
}
```

**Validator rules:**
- `name` must be a proper noun (capitalized phrase) OR a clearly
  distinctive descriptor ("the Crystal Caves", "the Old Mill").
- Reject pure-generic locations ("the dungeon", "the forest", "the
  road").

---

## 8. Prompt injection plan

DM system prompt grows by three blocks:

1. **CAMPAIGN SKELETON** (always, full file): authored content from
   skeleton.md. Authoritative.
2. **KNOWN NPCS** (retrieval): up to 10 entries selected by
   - any NPC matching current_location_id
   - top-N by last_mentioned recency
   - any skeleton_origin=1 NPC always included
3. **KNOWN LOCATIONS** (retrieval): current location + immediate parent
   + last-3-visited siblings.

All blocks include explicit grounding instruction:
*"Treat KNOWN NPCS and KNOWN LOCATIONS as established facts. Do not
invent contradicting names. If introducing a new NPC, give them a
distinct name not in the list."*

Token budget: skeleton ~1500 typical, NPCs ~600, locations ~400.
Total ~2500 typical, ~6000 hard cap.

### 8.1 Retrieval scoring (deterministic)

NPC and location retrieval are NOT vibes. Each candidate gets a score;
top-N by score fills the prompt block until token cap. Formula:

```
score =
  + 1000 if skeleton_origin == 1                    # always include canon
  +  100 if location matches current_location_id    # local relevance
  +  100 if location is parent/child of current     # adjacent relevance
  +   30 * recency_decay(last_mentioned)            # recency weight
  +   10 * log10(mention_count + 1)                 # recurrence weight
```

Where `recency_decay()` is a simple bucketed function:
- mentioned this session: 1.0
- mentioned last session: 0.6
- mentioned 2-5 sessions ago: 0.3
- older: 0.1

Tie-breakers: higher mention_count, then more recent last_mentioned,
then alphabetical for stability.

Why deterministic: prompt composition needs to be debuggable. If the
DM forgets Garrick mid-session, we can ask "what was Garrick's score
at that turn?" and get a real answer, not a vibe. Also makes future
tuning a function of constants in code, not prose in a spec.

---

## 9. Open questions (require decisions before build)

These are the genuinely hard architectural calls. ChatGPT review should
focus here.

### 9.1 Canonical name resolution

When narration says "Garrick" in session 1 and "Garrick the smith" in
session 3, are these the same NPC? Three approaches:

**A. Strict literal match.** Different strings → different rows. Simple
but creates duplicates.

**B. Fuzzy match on first token + role.** "Garrick" + "blacksmith"
matches "Garrick the smith" + "blacksmith". Closer to right but fuzzy
matching introduces false merges.

**C. LLM-mediated resolution at write time.** When parser emits a new
candidate, a second LLM call asks "is this the same as any of these
existing NPCs?" against the table.

**Decision: A for v1**, with manual `aliases` field to merge later. C
is the right long-term answer but adds latency and a new failure mode.
B is worst-of-both — fuzzy enough to break, not smart enough to be
right.

**Required helper:** `canonicalize_name(s: str) -> str` runs before
matching. Pure normalization, NOT fuzzy:
- strip leading/trailing whitespace
- collapse internal whitespace runs to single space
- normalize curly quotes/apostrophes to ASCII
- preserve capitalization (do NOT lowercase — distinguishes proper
  nouns from common nouns)

This makes `"Garrick"`, `" Garrick "`, `"Garrick "` all resolve to the
same row without entering fuzzy territory.

### 9.2 First-mention bar

Where's the line for "this counts as an NPC"? Options:

**A. Proper name only.** "Garrick" yes, "the guard" no.
**B. Proper name OR distinctive role+location.** "Garrick" yes, "the
guard at the Redhaven gate" yes (because role+location uniquely
identifies), "a guard" no.
**C. Aggressive — capture everything, prune later.**

**Lean: A for v1.** B is tempting but the parser will hallucinate
distinctiveness. C floods the table with junk.

### 9.3 Skeleton.md authoring loop

Does Jordan write skeleton.md by hand, or does Virgil help? If Virgil
helps, that's a meta-conversation flow ("ok, what's the central conflict?
who are the main NPCs? let me draft this"). Useful but its own design.

**Lean: hand-authored for v1.** Skeleton authoring command is a v2
feature. Spec a manual format, ship it, then build the helper if
authoring friction shows up.

### 9.4 Migration from existing campaigns

Active campaigns (yours included) have ChromaDB history but no
NPCs/locations table entries. Three options:

**A. Fresh start.** New table, populated forward only. Lose past NPCs.
**B. Manual backfill.** You write the existing NPCs into skeleton.md.
**C. Auto-backfill via batch parser pass over ChromaDB.** Risk of
hallucinated junk, but recovers more.

**Lean: B for v1.** You know who's in your campaign better than a
batch parser would. Write skeleton.md as part of 12C, it doubles as
backfill.

### 9.5 Conflict between skeleton and parser

Skeleton says "the king is Aldric." DM narrates "King Bardus." What
happens?

**Lean:** parser-detected NPCs with `skeleton_origin=0` never overwrite
`skeleton_origin=1` rows. Conflict gets logged, not silently merged.
DM's contradicting narration is treated as a parser miss, not a state
update. Surfaces as a `conflict:` log line for review.

### 9.6 Companion vs. NPC table

`dnd_companions` already exists for PC allies. Persistent NPCs are
distinct (world NPCs, not bound to a player). Two tables, not one.
Companions can reference an NPC row via `npc_id` in the future if
useful.

### 9.7 Performance

Adding two parsers per DM turn = +2 LLM calls. At ~300ms each on
extraction task (Phase 11.1 latency), that's +600ms per turn.
Acceptable? Alternatives:

**A. Run sequentially, accept latency.**
**B. Run in parallel via asyncio.gather.**
**C. Run as background fire-and-forget after DM response posts** (like
hint parser does today). State updates land before next turn, not
this one.

**Lean: C.** Same pattern as 11.1 mechanical hints. The DM's current
response doesn't need the new NPC reflected in itself; the *next*
response does. No latency cost on the active turn.

### 9.8 Calibration ground truth

Phase 11.1 had a synthetic test battery (12 cases) for calibration.
NPC/location extraction has no analogous ground truth — it requires
reading session text and judging. How do we test before live play?

**Lean:** write a small test battery (~10 narration paragraphs) with
expected NPC/location extractions, mirror the calibration script
pattern. Use ground-truth from the Critical Role transcripts already in
ChromaDB — those are real DM narration with known characters.

### 9.9 current_location_id ownership

`current_location_id` on `dnd_scene_state` is semi-authoritative — the
DM grounds against it, retrieval scopes against it. Ambiguous ownership
risks the same drift problem the broader spec is designed to prevent.

**Decision: exactly one mutation path.** Engine function
`set_current_location(campaign_id, location_id)` is the only writer.
Callable from:
1. **Explicit `/travel <location>` command** (DM-issued, deterministic)
2. **Scene-transition detector** in orchestration (parser proposes
   transition, deterministic rules confirm — same shape as Phase 3
   auto-execute)
3. **Skeleton load** if skeleton.md declares a starting location for a
   campaign

The location parser does NOT write current_location. It only writes
location *existence* (rows in `dnd_locations`). Player-position
tracking is a separate concern, deliberately decoupled from "this place
exists in the world."

If parser narration strongly implies a transition ("you arrive in
Redhaven"), that gets logged as a transition candidate event — engine
either confirms (deterministic rule: location matches a known one,
narrative cadence indicates arrival not reference) or ignores. Never
silent auto-write.

### 9.10 Skeleton promotion (parser → canon)

Parser-detected NPCs/locations have `skeleton_origin=0`. Skeleton.md
entries have `skeleton_origin=1`. Promotion path is **manual only**:

- Future tooling (`/skeleton propose-diff`) reads the current parser
  state and generates a markdown diff Jordan reviews and applies to
  skeleton.md by hand. No auto-promotion.
- The system can SUGGEST promotion (parser-detected NPC has
  `mention_count >= 5` and never been in skeleton → propose adding to
  skeleton). The system never PERFORMS promotion.

This preserves authored-canon as a fully human-controlled artifact.
Reflects ChatGPT review §"propose skeleton diffs, not auto-update."

---

## 10. Ship gate

Phase 12 ships when:

1. All 12A-12C tables created, migrations clean, no breakage of existing
   campaigns.
2. Calibration script for 12A and 12B passes ≥80% on synthetic battery.
3. One real session of play (60+ minutes) with parser logs reviewed:
   - <10% false positive rate on NPC extraction
   - <10% false negative on named NPCs
   - No skeleton conflicts silently overwritten
4. Token budget verified: total prompt growth under 6000 tokens hard cap.

---

## 11. Build sequence

| Step | What | Files touched | Verification |
|------|------|---------------|--------------|
| 12A.1 | Create dnd_npcs table + migration + accessors | dnd_engine.py | unit test on empty insert/get/update |
| 12A.2 | Build npc_extractor.py + validator | npc_extractor.py | unit tests + offline calibration |
| 12A.3 | Hook background extraction task into _dm_respond_and_post | discord_dnd_bot.py | live: post turn → NPC appears in DB after ~500ms |
| 12A.4 | Add KNOWN NPCS prompt block to dm_respond | dnd_engine.py | live: reference Garrick in turn 1, see name preserved in turn 5 |
| 12B.1-4 | Same shape for locations | location_extractor.py + above | analogous tests |
| 12C.1 | Create campaigns/<id>/skeleton.md template | filesystem | jordan writes one for current campaign |
| 12C.2 | Build skeleton loader with mtime cache | dnd_engine.py | unit test: edits to file reflected on next call |
| 12C.3 | Inject skeleton into dm_respond system prompt | dnd_engine.py | live: skeleton NPCs appear by name |
| 12E | Live session calibration | (review only) | log analysis after 60+ min play |

Estimate: 12A is ~2-3 sessions, 12B mirrors so ~1, 12C is ~1, 12E is
playing not building. Total: 4-6 sessions of work.

---

## 12. Risks I'm flagging for review

- **Parser scope creep.** NPC extraction prompt is wider than 11.1's
  whitelist. Risk of bloating the prompt and getting fuzzy outputs.
  Keep ruthlessly narrow. If the model isn't confident about role or
  location, emit just name. Better empty fields than wrong ones.
- **Skeleton bit-rot.** If you author skeleton.md and then play
  diverges from it, the prompt gets confusing for the DM. Need a way
  to evolve the skeleton mid-campaign without manual edit-every-session.
  **Mitigation:** v2 feature `/skeleton propose-diff` reads parser
  state, generates a markdown diff for human review and manual apply.
  System never auto-mutates skeleton.md. Authored canon stays
  human-controlled. (See §9.10.)
- **Skeleton scale ceiling (post-Phase-12 concern).** Single-file
  markdown works at ~10 NPCs / 15 locations / 3 factions. Eventual
  campaigns will outgrow this. Likely future shape (NOT Phase 12):
  segmented authored content — `skeleton/core.md`, `factions.md`,
  `locations.md`, `arc_N.md` — with a loader that selects relevant
  segments by scene context. Don't pre-build this. Note it exists.
- **Token costs.** Three blocks could compound over sessions as
  retrieval grows. Caps in §4 help, but real measurement needed in 12E.
- **The God Mode problem (S9) is adjacent.** Persistent NPCs grounds
  the world but doesn't make the DM enforce 5e rules. A character
  sheet ground-truth pass should run alongside this eventually, but
  is genuinely separate work.

---

**End of spec.** Questions in §9 should resolve before any build.
