# Track 6 #5.1 — Combat Entry Assist — Design Spec v1.2 (LOCKED)

**Status:** LOCKED — Session 2 complete. §11.A–§11.E LOCKED (all Option 1, 2026-05-08). §11.F starting values accepted as initial guesses, tunable from logs. §11.G implementation-phase (Session 3). §11.H locked (no mode gate). Tests 9–10 replaced with valid Jaccard examples (review §G.1). Two-line success log shape documented (review §G.2). `was_new` dedup primacy noted (review §F.3). `init_directive` cross-reference added (review §H scope note). Session 3 (implementation) may begin.
**Pattern:** New pure-function SRD resolver module (`srd_resolver.py`), NPC-extractor-post-upsert hook, `#dm-aside` suggestion posting. Doctrine §1b validated-suggester pattern — inaugural implementation in the codebase.
**Track:** Track 6 #5.1 — first ship in the Combat Playability Cluster (F-55). Independent of the resolver primitive (#5.4); no dependency on remaining cluster ships.
**Failure mode this begins addressing:**
- **F-55 surface 1 (combat entry friction).** The DM narrates a creature, then must remember `!init begin`, construct `!init add 0 "Spiny Toad"` cold, and answer Track 6 #4's CR prompt — four cognitive steps to add one combatant. #5.1 collapses this to two: DM narrates the creature; system suggests the `!init madd` command with CR; DM types the suggested command. For any creature with an SRD analog, the DM never has to pick a CR.

---

## 1. Locked decisions (§11.A–§11.H all locked)

1. **Hook point is NPC extractor post-upsert for new creatures.** When `npc_upsert()` creates a new `dnd_npcs` row (`was_new=True` per §11.G), `_handle_new_npc_for_srd_suggestion()` fires: runs the SRD resolver and posts a suggestion to `#dm-aside` if a confident candidate is found. **No mode gate** — hook fires regardless of scene mode (§11.H locked). Session dedup is the only re-post guard. `!init add` raw-message intercept filed as v1.x (§12) — the narration hook fires first in the typical DM flow and requires no new message-pattern matching.

2. **SRD index: local JSON bundled from 5e-database (MIT + CC-BY 4.0 SRD content).** Loaded at bot startup into `_MONSTER_INDEX: dict[str, dict]` in `srd_resolver.py`. No runtime network dependency. Index shape: `{"giant frog": {"name": "Giant Frog", "cr": "1/4", "hp": 18, "ac": 11}, ...}`. Lookup key is lowercased canonical name. Approximately 330 SRD monsters (~40 KB JSON, generated once by `scripts/generate_srd_index.py`).

3. **SRD resolution order: Python exact → Python fuzzy → LLM structured-output call (§1b).** (a) Case-insensitive exact key lookup in `_MONSTER_INDEX`; (b) Jaccard token-overlap fuzzy match (threshold ≥ 0.6) across all index keys; (c) if no Python match, targeted `_llm_suggest()` call with structured output returning `{"candidate": str, "confidence": float}`; (d) Python validates LLM output: candidate must exist in `_MONSTER_INDEX` AND `confidence >= 0.65`. If either check fails, no suggestion surfaces. The SRD index is the deterministic validator gate — this is the §1b pattern.

4. **LLM model: `cloud_router` with `task_type="extraction"`.** Same model path as `mechanical_hints.py`. Structured output contract: `{"candidate": string, "confidence": float}` — candidate is a monster name, not CR (CR is retrieved from the index after validation). Context provided: creature name only (narration context is v1.x, §12). Process-lifetime LLM cache by `creature_name_lower` so each unique name costs at most one LLM call per bot restart.

5. **Suggestion UI: informational text post to `#dm-aside` only. No autonomous bot emission, no react-emoji approval flow.** The bot posts a formatted message with a copyable `!init madd` command. The DM typing that command is the §1b "user approves" step. Consistent with Track 6 #4 §11.D lock: bot never autonomously emits `!` commands.

6. **Multi-monster shortcut (plural creature names): deferred to v1.x.** "3 goblins" / "two wolves" generates no suggestion in v1; DM uses `!init add` or `!init madd` manually. Filed in §12.

7. **Session-level deduplication: module-level `_SUGGESTED: set[tuple[int, str]]` keyed by `(campaign_id, creature_name_lower)`.** Once a suggestion posts for a given campaign + creature pair in the current process lifetime, don't re-post. Bot restart clears the set (no persistence required).

8. **Telemetry: always-fire `srd_suggestion:` log line per resolver call**, including misses. Fields: `campaign={N} input='{name}' candidate='{srd_name|none}' cr={cr|none} confidence={float|none} method={exact|fuzzy|llm|miss|dedup} posted={0|1}`.

---

## 2. Goal and context

### F-55 surface 1: combat entry friction

F-55 identified three friction stacks. #5.1 addresses surface 1:

**Current DM flow:**
1. DM narrates creature ("A spiny toad lunges from the swamp")
2. DM remembers to type `!init begin` (if not already in combat — addressed by init_directive, S20)
3. DM types `!init add 0 "Spiny Toad"` — modifier number cold, name format uncertain
4. Avrae adds combatant with default HP/AC (no monster-manual backing for "Spiny Toad")
5. Track 6 #4 hydration fires: "Hydration needed: `Spiny Toad` just entered initiative with no stats. What CR? `/hydrate npc:Spiny Toad cr:N`"
6. DM has to think up a CR for a creature they just invented

**Target DM flow with #5.1 (SRD match found):**
1. DM narrates "A spiny toad lunges from the swamp"
2. Bot posts to `#dm-aside`: "SRD match for 'Spiny Toad': Giant Frog (CR 1/4, HP 18, AC 11). Suggested: `!init madd "Giant Frog" -name "Spiny Toad"`"
3. DM reads, types the `!init madd` command — one step, no CR decision needed
4. Avrae adds combatant with full canonical stat block (HP, AC, attacks, saves from Avrae's monster manual)
5. Track 6 #4 step 2.5 fires: `status_token=<Healthy>` → `npc_register_avrae_madd()` → hydration skipped (Avrae owns stats)

**Surface 1 partial closure:** When an SRD analog exists for the narrated creature, the CR-decision + hydration-prompt friction (steps 5–6 in the current flow) collapses to a single `!init madd` copy-paste. `!init begin` reminder, `!init join` for players, and multi-monster plural handling remain unaddressed in v1 (filed §12). The 6→2 reduction is the SRD-match best case, not the average — DMs narrating homebrew creatures with no SRD analog see a `method=miss` log line and the existing `!init add` → hydration path, no regression.

**Fallback (no SRD match, or DM ignores suggestion):** existing `!init add` → Track 6 #4 hydration → CR prompt path. No regression, no change.

### THE_GOAL alignment

- *"I want combat to be fun."* — Reducing entry friction means the DM starts a fight without a mechanics tax.
- *"I want to feel something when I kill an enemy."* — An `!init madd` creature carries Avrae's canonical HP/AC/attacks, which makes combat HP tracking and attack rolls mechanically real rather than approximate.

### Doctrine §1b anchoring — inaugural implementation

This is the first §1b-explicit implementation written after the §1a/§1b doctrine split. The pattern itself is not architecturally new — `mechanical_hints.py`, `npc_extractor.py`, `consequence_extractor.py`, and `dnd_knowledge_import.py` are all canonical §1b instances already operating per Doctrine §1b's "canonical instances already operating" list. `srd_resolver.py` follows the §12 advisory parser pattern (parser logs internally, no signals returned) rather than the §59 compute-in-orchestration sibling pattern (which returns `(body, signals)` for the orchestration layer to log). Doctrinal lineage: §12 advisory parser shape, §1b validated-suggester semantics, §59 telemetry discipline (always-fire, soft-fail at call site). The full chain:

```
LLM proposes:     {"candidate": "Giant Frog", "confidence": 0.82}
                        ↓
Python validates: "giant frog" ∈ _MONSTER_INDEX  ✓
                  confidence 0.82 ≥ 0.65           ✓
                        ↓
Suggestion posts: "Giant Frog (CR 1/4, HP 18, AC 11) — type !init madd ..."
                        ↓
DM approves:      types `!init madd "Giant Frog" -name "Spiny Toad"`  (explicit DM action)
                        ↓
Avrae executes:   adds Giant Frog with canonical stat block
                        ↓
Track 6 #4:       status_token=<Healthy> → npc_register_avrae_madd()
                  [hydration skipped — Avrae owns stats]
```

At no step does the LLM decide anything mechanically. The index validates, the DM approves, Avrae executes.

---

## 3. Architecture

### New artifacts

| Artifact | Location | Purpose |
|----------|----------|---------|
| `srd_resolver.py` | new module | Pure function SRD resolution: exact → fuzzy → LLM. No DB, no Discord. |
| `srd_monsters.json` | `/home/jordaneal/scripts/srd_monsters.json` | Bundled SRD monster index (generated once, not runtime) |
| `generate_srd_index.py` | `scripts/generate_srd_index.py` | One-time generator: 5e-database → `srd_monsters.json` |
| `_handle_new_npc_for_srd_suggestion()` | `discord_dnd_bot.py` | Async hook: gate check → resolver call → `#dm-aside` post |
| `_post_srd_suggestion()` | `discord_dnd_bot.py` | Formats and posts suggestion message to channel |

### What doesn't change

- `npc_upsert()` in `dnd_engine.py` — return shape may need a `was_new` signal (§11.G — implementation-phase discovery). All existing callers unaffected either way.
- `_handle_init_list_event()` — unchanged. Hydration is the fallback path; #5.1 is a pre-decision suggestion layer. If the DM uses `!init madd` following a suggestion, `status_token=<Healthy>` routes to `npc_register_avrae_madd()` as before.
- `parse_init_list_embed()` — unchanged.
- `npc_register_avrae_madd()` — unchanged. Fires via the existing Track 6 #4 path when `!init madd` is used.
- `mechanical_hints.py` — architectural sibling, no changes. `srd_resolver.py` follows the same pure-function + cloud_router pattern.

### Precedence diagram (full combat entry flow with #5.1)

```
DM narrates "A spiny toad lunges..."
    ↓
npc_extractor.py → parse_npcs() → ["Spiny Toad", ...]
    ↓
npc_upsert(campaign_id, "Spiny Toad") → row_id (new insert)
    ↓  [NEW — #5.1 hook fires when was_new=True; no mode gate (§11.H locked)]
_handle_new_npc_for_srd_suggestion(campaign_id, "Spiny Toad", guild)
    srd_resolver.resolve("Spiny Toad", campaign_id)
      → exact match: miss
      → Jaccard fuzzy: miss
      → LLM: {"candidate": "Giant Frog", "confidence": 0.82}
      → validate: "giant frog" ∈ _MONSTER_INDEX ✓; 0.82 ≥ 0.65 ✓
      → SRDResult(input_name="Spiny Toad", srd_name="Giant Frog", cr="1/4", hp=18, ac=11)
    → post to #dm-aside: "🎯 SRD match for 'Spiny Toad': Giant Frog (CR 1/4, HP 18, AC 11) ..."
    → _SUGGESTED.add((campaign_id, "spiny toad"))
    → log: srd_suggestion: ... method=llm confidence=0.82 posted=1
    ↓
DM types: !init madd "Giant Frog" -name "Spiny Toad"
    ↓
_handle_init_list_event → status_token=<Healthy> → npc_register_avrae_madd()
    [Track 6 #4 avrae_madd path — hydration skipped]
```

Fallback (miss or DM ignores suggestion):
```
DM types: !init add 0 "Spiny Toad"
    ↓
_handle_init_list_event → status_token=<None> → hydration path
    → _post_hydration_prompt: "What CR? /hydrate npc:Spiny Toad cr:N"
    → generic_fallback stats written (no hp_max)
    [Track 6 #4 hydration path — unchanged]
```

---

## 4. SRD monster index

### Source and licensing

**5e-database** (https://github.com/5e-bits/5e-database) — MIT license for the tooling; SRD content under CC-BY 4.0 (System Reference Document 5.1, Wizards of the Coast). CC-BY 4.0 explicitly permits bundling in tools of this kind. Approximately 330 monsters in the SRD subset.

The JSON is generated once and committed to the repo as `srd_monsters.json`. Not fetched at runtime. Index is loaded at module import; `_MONSTER_INDEX` is an in-memory dict for the process lifetime.

### Index format

```json
{
  "giant frog":    {"name": "Giant Frog",    "cr": "1/4", "hp": 18,  "ac": 11},
  "goblin":        {"name": "Goblin",        "cr": "1/4", "hp": 7,   "ac": 15},
  "owlbear":       {"name": "Owlbear",       "cr": "3",   "hp": 91,  "ac": 13},
  "young red dragon": {"name": "Young Red Dragon", "cr": "10", "hp": 178, "ac": 18}
}
```

Key: lowercased canonical name. Value: `name` (display/title-case), `cr` (string), `hp` (int, average from stat block), `ac` (int). Four fields only — spec intentionally narrow. Full stat blocks are not needed: Avrae has the authoritative data, and `npc_hydrator.py` handles CR-band approximations for `!init add` creatures.

### Validation cross-check

All `cr` values in `srd_monsters.json` must be valid inputs to `normalize_cr()` from `npc_hydrator.py`. Test 25 (§9) enforces this. CR values above CR 12 (the current hydration table ceiling) are fine — the suggestion uses the monster's actual SRD HP/AC from the index, not the CR-band table.

### Generation script (one-time, not runtime)

`scripts/generate_srd_index.py`:
1. Reads from 5e-database `monsters.json` (or the API static dump equivalent)
2. Filters to SRD-only entries (field `document__slug == "wotc-srd"` or equivalent)
3. Extracts `name`, `challenge_rating` (→ `cr`), `hit_points` (→ `hp`), `armor_class[0].value` (→ `ac`)
4. Writes `srd_monsters.json` with lowercased-name keys
5. Prints count: "Generated N monsters → srd_monsters.json"

Not run at bot startup. Run once when the 5e-database source updates (rare). The resulting file is committed.

---

## 5. Resolver module (`srd_resolver.py`)

### Module structure

```python
"""SRD monster resolver — Track 6 #5.1.

Pure function core. No DB access, no Discord, no dnd_engine imports.
Single entry point: resolve(creature_name, campaign_id) → SRDResult | None.

Doctrine §1b anchor: LLM proposes a candidate; _MONSTER_INDEX validates
the candidate exists in the SRD; confidence gate enforces the threshold;
DM approves by typing the suggested command.
"""

import dataclasses, json, os, re
from cloud_router import route
from dnd_engine import log

_INDEX_PATH = os.path.join(os.path.dirname(__file__), 'srd_monsters.json')
_MONSTER_INDEX: dict[str, dict] = {}       # loaded at import
_SUGGESTED: set[tuple[int, str]] = set()   # session dedup
_LLM_CACHE: dict[str, tuple[str, float] | None] = {}  # process-lifetime cache

_JACCARD_THRESHOLD = 0.6
_CONFIDENCE_THRESHOLD = 0.65

@dataclasses.dataclass
class SRDResult:
    input_name:  str    # creature name from narration
    srd_name:    str    # matched SRD monster name (display)
    cr:          str
    hp:          int
    ac:          int
    confidence:  float
    method:      str    # 'exact' | 'fuzzy' | 'llm'
```

### Resolution algorithm

```python
def resolve(creature_name: str, campaign_id: int) -> SRDResult | None:
    name_lower = creature_name.lower().strip()

    # Session dedup
    if (campaign_id, name_lower) in _SUGGESTED:
        log(f"srd_suggestion: campaign={campaign_id} input='{creature_name}' "
            f"candidate=none cr=none confidence=none method=dedup posted=0")
        return None

    # (a) Exact match
    entry = _MONSTER_INDEX.get(name_lower)
    if entry:
        return _build_and_mark(creature_name, entry, 1.0, 'exact', campaign_id)

    # (b) Jaccard fuzzy
    fuzzy = _fuzzy_match(name_lower)
    if fuzzy:
        entry, score = fuzzy
        return _build_and_mark(creature_name, entry, score, 'fuzzy', campaign_id)

    # (c) LLM suggester — §1b: propose → validate → gate
    llm = _llm_suggest(creature_name)
    if llm:
        candidate, confidence = llm
        entry = _MONSTER_INDEX.get(candidate.lower().strip())   # validator gate
        if entry and confidence >= _CONFIDENCE_THRESHOLD:
            return _build_and_mark(creature_name, entry, confidence, 'llm', campaign_id)

    # Miss
    log(f"srd_suggestion: campaign={campaign_id} input='{creature_name}' "
        f"candidate=none cr=none confidence=none method=miss posted=0")
    return None
```

`_build_and_mark()` constructs the `SRDResult`, adds to `_SUGGESTED`, and emits the telemetry log. Returns the result.

### Fuzzy match (Jaccard token overlap)

```python
def _fuzzy_match(name_lower: str) -> tuple[dict, float] | None:
    tokens = set(name_lower.split())
    best_score, best_entry = 0.0, None
    for key, entry in _MONSTER_INDEX.items():
        key_tokens = set(key.split())
        union = len(tokens | key_tokens)
        score = len(tokens & key_tokens) / union if union else 0.0
        if score >= _JACCARD_THRESHOLD and score > best_score:
            best_score, best_entry = score, entry
    return (best_entry, best_score) if best_entry else None
```

Jaccard covers exact-word-overlap cases: "Giant Poisonous Snake" ↔ "Giant Poisonous Snake" (trivially exact via step (a)), "Black Young Dragon" ↔ "Young Black Dragon" (0.67), "Cave Giant Spider" ↔ "Giant Spider" (0.5 — below threshold, correct miss). Semantic matches like "Spiny Toad" ↔ "Giant Frog" score 0.0 on Jaccard — this is expected; that's when the LLM fires.

### LLM suggester (§1b)

```python
_LLM_SYSTEM = """You are a D&D 5e expert. Given a creature name from DM narration,
identify the closest monster in the 5e System Reference Document (SRD).

Output ONLY a JSON object: {"candidate": "exact SRD name", "confidence": float}

Rules:
- candidate must be an exact 5e SRD monster name (e.g. "Giant Frog", not "Large Frog")
- confidence: 0.0–1.0 reflecting how well the input maps to the SRD monster
- If no reasonable SRD match exists: {"candidate": "", "confidence": 0.0}
- Do not invent names. Only use names from the 5e SRD.

Examples:
  "Spiny Toad"     → {"candidate": "Giant Frog",      "confidence": 0.75}
  "Forest Spider"  → {"candidate": "Giant Spider",     "confidence": 0.80}
  "Cave Bat"       → {"candidate": "Swarm of Bats",    "confidence": 0.65}
  "Goblin Captain" → {"candidate": "Goblin Boss",      "confidence": 0.85}
  "Fog Wraith"     → {"candidate": "Wraith",           "confidence": 0.60}
  "XyzPlorp"       → {"candidate": "",                 "confidence": 0.00}"""


def _llm_suggest(creature_name: str) -> tuple[str, float] | None:
    key = creature_name.lower().strip()
    if key in _LLM_CACHE:
        return _LLM_CACHE[key]
    try:
        response, _ = route(
            messages=[{"role": "user", "content": f"Creature name: {creature_name}"}],
            task_type="extraction",
            system_prompt=_LLM_SYSTEM,
        )
        parsed = json.loads(response or "{}")
        candidate = str(parsed.get("candidate", "")).strip()
        confidence = float(parsed.get("confidence", 0.0))
        result = (candidate, confidence) if candidate else None
    except Exception:
        result = None
    _LLM_CACHE[key] = result
    return result
```

**Validator gate (in `resolve()`, mandatory):** after `_llm_suggest()` returns `(candidate, confidence)`, `_MONSTER_INDEX.get(candidate.lower())` must return a non-None entry. If the LLM hallucinated a name not in the SRD index, the gate catches it and `resolve()` returns None. This is the §1b structure: LLM proposes, index validates, no suggestion without validation.

---

## 6. Hook integration

### `npc_upsert()` return — `was_new` signal (§11.G discovery)

Current `npc_upsert()` signature returns `int | None` (row ID on success, None on failure/refusal). The `int` return does not distinguish INSERT from UPDATE — callers currently check `if row_id:` to confirm success regardless of operation type.

The hook needs `was_new=True` only for genuinely new row inserts. Two implementation-phase options:
- **(a)** Modify `npc_upsert()` to return `(row_id, was_new: bool)` — small breaking change to callers (currently just the NPC extractor background task in `discord_dnd_bot.py` and `skeleton_loader.py`). Cleaner signal.
- **(b)** Inspect the returned `row_id` against a `SELECT mention_count FROM dnd_npcs WHERE id=?` check in the hook — a new NPC always has `mention_count=1`. Adds one DB read but avoids modifying `npc_upsert()`.

**Recommendation: option (a).** The return-shape change is localized and makes the signal explicit. Option (b) adds a DB round-trip inside an already-async hook. Implementation-phase decision — surfaced here for awareness, not a Jordan call.

### `_handle_new_npc_for_srd_suggestion()` in `discord_dnd_bot.py`

New async helper. Called from the NPC extractor background task immediately after a successful `npc_upsert()` insert.

```python
async def _handle_new_npc_for_srd_suggestion(
    campaign_id: int,
    npc_name: str,
    guild: discord.Guild,
) -> None:
    try:
        result = srd_resolver.resolve(npc_name, campaign_id)
        if result is None:
            return
        dm_aside = discord.utils.get(guild.text_channels, name=CHANNEL_NAMES['aside'])
        if dm_aside:
            await _post_srd_suggestion(dm_aside, result)
    except Exception as e:
        log(f"_handle_new_npc_for_srd_suggestion error: npc='{npc_name}' err={e!r}")
```

**Removed from v1:** the `get_scene_state` read and the `mode != 'combat'` early return (§11.H locked — no mode gate). `get_scene_state` import in this hook is no longer needed unless used elsewhere in the file.

Soft-fail: any exception is logged and swallowed. Narration flow is never blocked by a resolver failure — Doctrine §59 sibling pattern applies.

### Dedup primacy: `was_new` is the primary guard; `_SUGGESTED` is secondary

The primary mechanism preventing duplicate hook invocations is `npc_upsert()`'s `was_new` return (§11.G). When `npc_upsert()` updates an existing `dnd_npcs` row, `was_new=False` and the hook does not fire — so a creature with a prior row never reaches the resolver, regardless of `_SUGGESTED` state. `_SUGGESTED` is secondary protection covering edge cases within the same process lifetime (e.g., the extractor parsing the same name twice in one narration response).

Bot restart clears `_SUGGESTED` but not the `dnd_npcs` row. Restart mid-combat does not produce duplicate suggestions: on the next narration encounter of the same creature, `npc_upsert()` updates the existing row and returns `was_new=False`. The dedup set is redundant in this case — `was_new=False` catches it at the upsert level.

### `_post_srd_suggestion()` in `discord_dnd_bot.py`

```python
async def _post_srd_suggestion(channel, result: 'SRDResult') -> None:
    body = (
        f"🎯 **SRD match for \"{result.input_name}\":** "
        f"{result.srd_name} (CR {result.cr}, HP {result.hp}, AC {result.ac})\n"
        f"To add with Avrae's full stat block, type:\n"
        f"```\n!init madd \"{result.srd_name}\" -name \"{result.input_name}\"\n```\n"
        f"*(Or `!init add 0 \"{result.input_name}\"` — Virgil will ask for CR.)*"
    )
    await channel.send(body)
    log(f"srd_suggestion: campaign=... input='{result.input_name}' "
        f"candidate='{result.srd_name}' cr='{result.cr}' "
        f"confidence={result.confidence:.2f} method={result.method} posted=1")
```

The "Or `!init add`" line is load-bearing: it makes clear that ignoring the suggestion is fine and the hydration fallback remains available. DMs who prefer manual control should never feel locked into the suggested command.

---

## 7. Suggestion text design

The suggestion covers all three DM choices:

1. **Use the SRD creature:** Type the `!init madd` command → Avrae loads canonical stats → Track 6 #4 avrae_madd path fires → hydration skipped.
2. **Use a homebrew variant with Virgil stats:** Type `!init add 0 "{name}"` → Track 6 #4 hydration fires → CR prompt in `#dm-aside`.
3. **Ignore suggestion entirely:** Type any `!init` variant → existing paths handle it → no regression.

The `!init madd` command uses the SRD creature name with `-name` flag to preserve the DM's narrative name in Avrae's tracker. This is the `-name` workflow confirmed in Track 6 #4 §11.M live verification: `!init madd Goblin -name "Test Thug"` shows "Test Thug `<Healthy>`" in the init list.

---

## 8. Telemetry

### Log line shape

```
srd_suggestion: campaign={N} input='{creature_name}' candidate='{srd_name|none}'
                cr={cr|none} confidence={float|none}
                method={exact|fuzzy|llm|miss|dedup} posted={0|1}
```

**Two-line shape on success path:** `resolve()` emits the analytical line via `_build_and_mark` — method (exact/fuzzy/llm), confidence, candidate, `posted=0` (resolver does not post to Discord). `_post_srd_suggestion()` emits the transport confirmation line with `posted=1` once the Discord send completes. Method and confidence are identical between the two lines; `posted` is the only field that flips. Two lines per success is intentional, not a duplicate.

**Single-line shape on miss/dedup paths:** `resolve()` emits one line with `posted=0` and `method=miss` or `method=dedup`. No second line — no Discord post is attempted.

**Grep patterns:** `grep "srd_suggestion:.*posted=1"` — accepted suggestions only. `grep "srd_suggestion:"` — all resolver activity (1 line per miss/dedup, 2 lines per success).

**Method semantics:**

| Method | Meaning |
|--------|---------|
| `exact` | Python exact key match in `_MONSTER_INDEX` |
| `fuzzy` | Jaccard token-overlap match ≥ threshold |
| `llm` | LLM call succeeded; candidate in index; confidence ≥ threshold |
| `miss` | All three methods failed; no suggestion |
| `dedup` | Already suggested this `(campaign_id, name)` pair this session; skipped |

**Interpreting session logs:** high `method=miss posted=0` rate suggests creature names in this campaign don't have SRD analogs (homebrew-heavy campaigns expected). High `method=llm` rate suggests Jaccard is too conservative — lower `_JACCARD_THRESHOLD` if the LLM consistently agrees with the DM's acceptance pattern. `posted=1` with `method=llm confidence=0.68` and DM consistently using the suggestion → threshold is calibrated.

### Integration with `directive_emit:`

No new `directive_emit:` field required. The `srd_suggestion:` line is a standalone per-event telemetry shape (not a per-turn directive), analogous to `npc_upsert:` rather than `combat_redirect:`. Per-encounter count: 1 line for miss/dedup, 2 lines for success.

---

## 9. Test surface

### `test_srd_resolver.py` (pure function tests — no DB, no Discord)

**Index integrity:**
1. `_MONSTER_INDEX` is non-empty after import (smoke: index loaded)
2. `_MONSTER_INDEX["giant frog"]` has correct `name`, `cr`, `hp`, `ac` fields
3. All keys in `_MONSTER_INDEX` are lowercase (no mixed-case keys)

**Exact match:**
4. `resolve("Giant Frog", 1)` → `SRDResult(srd_name="Giant Frog", method="exact", confidence=1.0)`
5. `resolve("giant frog", 1)` → same result (case-insensitive)
6. `resolve("GOBLIN", 1)` → `SRDResult(srd_name="Goblin", method="exact", confidence=1.0)`

**Fuzzy match:**
7. `_fuzzy_match("black young dragon")` → entry for "Young Black Dragon", Jaccard ≈ 0.67
8. `_fuzzy_match("totally unknown creature xyzzy")` → `None`
9. `_fuzzy_match("cave toad")` → `None` (tokens `{"cave", "toad"}` ∩ `{"giant", "frog"}` = ∅, Jaccard = 0.0, correct miss — no SRD entry has token overlap above threshold)
10. `_fuzzy_match("swarm bats")` → entry for "Swarm of Bats" at Jaccard = 2/3 ≈ 0.67 (tokens `{"swarm", "bats"}` ∩ `{"swarm", "of", "bats"}` = 2, union = 3, above threshold — DM omits "of", fuzzy match recovers it)

**LLM gate (unit tests — mock `_llm_suggest`):**
11. When `_llm_suggest` returns `("Giant Frog", 0.82)` and "giant frog" ∈ index → `resolve()` returns `SRDResult(method="llm", confidence=0.82)`
12. When `_llm_suggest` returns `("Phantasmal Wyrm", 0.90)` and "phantasmal wyrm" NOT in index → `resolve()` returns `None` (§1b validator gate rejects)
13. When `_llm_suggest` returns `("Giant Frog", 0.40)` → `resolve()` returns `None` (below confidence threshold)
14. When `_llm_suggest` raises exception → `resolve()` returns `None`, no propagation, miss log emitted

**Session dedup:**
15. `resolve("Spiny Toad", 1)` returns result; second call same session same campaign → returns `None` with `method=dedup` log
16. Dedup is per-campaign: `resolve("Goblin", 1)` deduped; `resolve("Goblin", 2)` fires normally

**Logging:**
17. Miss path emits log line with `method=miss posted=0`
18. Dedup path emits log line with `method=dedup posted=0`
19. Hit path: `_build_and_mark` emits log line with `posted=0` and correct `method`; `_post_srd_suggestion` emits a second log line with `posted=1` when the Discord send completes (two lines per success — see §8 two-line shape)

### `test_srd_suggestion_hook.py` (hook integration — mock resolver, mock Discord)

20. Hook fires for any new NPC upsert regardless of scene mode — `mode='exploration'` does NOT block the hook (§11.H locked)
21. Hook fires and resolver returns `SRDResult` → `_post_srd_suggestion` called
22. Hook fires and resolver returns `None` → `_post_srd_suggestion` NOT called
23. `#dm-aside` channel not found → hook swallows exception gracefully, no crash
24. Any exception in resolver call → hook swallows, logs error, returns without crashing
25. Suggestion message contains all required elements: input name, SRD name, CR, HP, AC, `!init madd` command, `!init add` fallback mention

### `test_srd_index_integrity.py` (data quality)

26. All entries in `srd_monsters.json` have non-null `name`, `cr`, `hp`, `ac`
27. All `cr` values pass `normalize_cr()` from `npc_hydrator.py` (cross-check against hydration table and fraction strings)
28. No duplicate keys in the index
29. `hp` and `ac` values are positive integers for all entries
30. All keys are lowercase strings matching `re.fullmatch(r'[a-z ]+', key)`

---

## 10. Edge cases and integration

### Existing NPC re-entering combat

If "Goblin" has a prior `dnd_npcs` row (from a previous session's narration), `npc_upsert()` updates (not inserts) → `was_new=False` → hook does not fire → no suggestion. This is correct: the NPC is canonical and the DM knows what they're adding. Session dedup provides secondary protection even if `was_new` detection misfires.

### SRD creature with CR above hydration table ceiling (CR 12)

`srd_monsters.json` includes high-CR monsters (Adult Red Dragon, Ancient Gold Dragon, etc.) that are above the Track 6 #4 hydration table ceiling of CR 12. The suggestion still fires using the SRD index's actual HP/AC, and correctly routes the DM toward `!init madd` (Avrae has canonical stats for any SRD monster regardless of CR). No hydration is needed or triggered for `!init madd` creatures.

### Both suggestion AND hydration could fire for the same NPC

Cannot happen in the normal flow. If the DM uses `!init madd` following a suggestion, `status_token=<Healthy>` → `npc_register_avrae_madd()` fires, hydration skipped. If the DM uses `!init add` despite (or without) a suggestion, `status_token=<None>` → hydration fires. The two paths are mutually exclusive at the routing level. Session dedup prevents the suggestion from re-firing on a second `!init add` for the same NPC.

### PC names reaching the hook

The PC contamination guard in `npc_upsert()` refuses names overlapping bound PCs and returns `None`. When `npc_upsert()` returns `None`, `was_new=False` → hook does not fire. No suggestion for PC names.

### SRD index missing or corrupt at import

If `srd_monsters.json` is missing or unparseable, `_MONSTER_INDEX` defaults to `{}`. All `resolve()` calls return `None` (miss path). Telemetry logs `method=miss`. Hydration fallback continues unchanged. No bot degradation beyond missing suggestions.

### New-combat entry: `init_directive` is the `!init begin` layer

The §2 "Target DM flow" (narrate → type `!init madd`) assumes combat is already active. For new-combat entry where `mode != 'combat'` at suggestion time, the DM still needs to type `!init begin` before the suggested `!init madd` makes mechanical sense. The Combat Initiation Orchestration directive shipped in S20 (`init_directive`) provides the prompt-side nudge toward `!init begin` when player intent indicates combat — `#5.1` layers on top of that existing path rather than replacing it. The 2-step "narrate → type `!init madd`" framing in §2 is accurate for ongoing combat; new-combat flow is 3 steps including `!init begin`. Honest scope per Doctrine §45.

### Integration with `narration_verifier` (Track 7 #2)

When DM uses the suggested `!init madd` command, `npc_register_avrae_madd()` fires → `dnd_npcs` row created with `avrae_source='avrae_madd'`. `narration_verifier.verify_narration()` checks NPC names against `npcs_canonical`; the registered row prevents false `FABRICATED_COMBATANT` violations for this creature. The #5.1 suggestion accelerates arrival at canonical registration — via the avrae_madd route rather than the hydration route, but the net effect on verification is identical.

### Creature name with special characters

Apostrophes, hyphens, non-ASCII characters in creature names will likely miss the Jaccard fuzzy match (tokenization differs) and fire the LLM. If the LLM suggests a valid SRD monster, the suggestion posts. If the LLM hallucinates, the validator rejects. No crash. Hydration fallback fires on `!init add`. This is the intended behavior: the system degrades gracefully to the existing flow when the creature has no SRD analog.

### LLM cache and process restart

`_LLM_CACHE` is process-lifetime only. Bot restart clears both `_LLM_CACHE` and `_SUGGESTED`. Creatures that were suggested last session may fire a new LLM call on next session start; the cost is one extra call per unique creature per bot restart. Acceptable at session scale.

---

## 11. Decision points needing Jordan's call

### §11.A — Hook point: NPC extractor post-upsert vs. `!init add` intercept vs. both (LOCKED — Option 1)

**LOCKED: Option 1. NPC extractor post-upsert only.**

Option 1 fires at narration time — before the DM has typed any `!init` command. With the §11.H lock (no mode gate), this fires regardless of scene mode and gives the DM maximum lead time. The `!init add` intercept (Option 2) arrives after the DM has already committed to the manual path; Option 3 collapses into Option 1 plus the §12-filed v1.x fallback.

Low `srd_suggestion: posted=1` rate in logs is the signal to file the `!init add` intercept as a live v1.x ship. Option 1 requires `npc_upsert()` to carry a `was_new` signal (§11.G — implementation-phase).

---

### §11.B — SRD index source and CC-BY 4.0 licensing confirmation (LOCKED — Option 1)

**LOCKED: Option 1. 5e-database, CC-BY 4.0 attribution in the generated JSON header.**

5e-database (https://github.com/5e-bits/5e-database) — MIT tooling, CC-BY 4.0 SRD content. CC-BY 4.0 requires attribution (author, title, URL, license reference); a comment block in `srd_monsters.json` is sufficient and standard practice for 5e tooling projects. Option 3 (live API) is dead on arrival — §1 decision 2 requires a local deterministic validator. Option 2 (Open5e) contains equivalent content; the generator can swap sources without changing the index format or any downstream code.

---

### §11.C — LLM model selection (LOCKED — Option 1)

**LOCKED: Option 1. `cloud_router` with `task_type="extraction"`.**

Same path as `mechanical_hints.py` — the proven §12 advisory parser shape in this codebase. Process-lifetime `_LLM_CACHE` bounds cost to one call per unique creature name per bot restart. Option 3 (skip LLM) eliminates the primary use case: "Spiny Toad" → "Giant Frog" is a semantic match Jaccard cannot reach. Option 2 (local model) is the operational lever if cloud latency or cost becomes a concern after session data accumulates.

**Session 3 implementation note:** `_LLM_CACHE` should NOT cache on exception — only cache definitive LLM responses. Transient failures (network, timeout, rate limit) must not poison the cache for subsequent encounters. See Session 3 scope in the patch message for the corrected `_llm_suggest` implementation.

---

### §11.D — Multi-monster plural detection: v1 or v1.x (LOCKED — Option 1)

**LOCKED: Option 1. Single-creature v1; plural deferred to v1.x.**

"3 goblins" / "two wolves" generates no suggestion in v1. DM uses `!init madd` manually. Session logs (`method=miss` rate on plural inputs) are the signal to ship plural handling — count detection, plural-to-singular normalization, and command repetition all add scope that should be motivated by observed friction, not anticipated (Doctrine §6).

---

### §11.E — Suggestion UI: informational text vs. react-emoji approval flow (LOCKED — Option 1)

**LOCKED: Option 1. Informational text only — no react handler, no interaction button.**

Track 6 #4 §11.D (permanent lock): bot does NOT autonomously emit `!` commands. Option 3 (interaction button) is a hard §11.D violation — dead on arrival. Option 2 (react-emoji) is Option 1 with an extra ceremony step: under §11.D, a ✅ react cannot cause the bot to emit the command; the DM still has to type it. The DM typing the copyable `!init madd` code block IS the §1b "user approves" step — explicit, zero-ceremony, zero-ambiguity.

If DMs report suggestions being lost in `#dm-aside` scroll, the v1.x path is a persistent suggestion format or a pin-on-post approach — not a react-to-emit flow.

---

### §11.F — Confidence threshold starting values (tuning, not a lock)

**Proposed:** `_CONFIDENCE_THRESHOLD = 0.65` for LLM confidence; `_JACCARD_THRESHOLD = 0.6` for fuzzy match.

These are tunable constants in `srd_resolver.py`. Too high → many misses, few suggestions. Too low → noisy suggestions the DM dismisses.

The `srd_suggestion: confidence={float} method={...}` log enables post-session calibration: if most accepted suggestions have confidence 0.72–0.90, the starting threshold is calibrated. If DMs are dismissing suggestions with confidence 0.67–0.70, raise the threshold.

**Not a lock — tune from logs after a few sessions.** No Jordan call required beyond confirming the starting values are acceptable as initial guesses.

---

### §11.G — `npc_upsert()` return shape: `was_new` signal

**Context (surfaced during required reading):** Current `npc_upsert()` returns `int | None` without distinguishing INSERT from UPDATE. The hook needs `was_new=True` to avoid firing suggestions for re-encountered canonical NPCs.

**Implementation-phase resolution options:**
- **(a)** Modify `npc_upsert()` to return `(row_id, was_new: bool)` — clean signal, small breaking change to two callers (NPC extractor task in `discord_dnd_bot.py` and `skeleton_loader.py`).
- **(b)** After `npc_upsert()` returns, call `npc_get_by_name()` and check `mention_count == 1` — no signature change, one extra DB read per upsert during combat.

**Not a Jordan call** — this is a code-level decision for Session 3. Surfaced here so the reviewer is aware. Recommendation: option (a). The clean signal costs less than the extra DB round-trip.

---

### §11.H — Combat-mode gate on the hook (LOCKED — Option a)

**Context (surfaced during planner-side review):** §1 decision 1 + §6 hook guard the hook with `if scene.get('mode') != 'combat': return`. Verified against `discord_dnd_bot.py`: `_extract_and_persist_world` is spawned at line 1649 as a background task AFTER the LLM narration posts; mode only flips to `combat` when Avrae emits `!init begin` (line 712-713). The canonical combat-entry flow is:

1. Player narrates → LLM responds "A spiny toad lunges from the swamp"
2. `_extract_and_persist_world` fires → `npc_upsert("Spiny Toad")` → **mode is still `exploration`** (no `!init begin` yet)
3. Hook gate returns early → no suggestion posts
4. DM types `!init begin`, then `!init add 0 "Spiny Toad"` cold → CR prompt fires via Track 6 #4 — exactly the friction #5.1 was meant to short-circuit

With the `mode='combat'` gate, the hook only fires for NPCs introduced DURING ongoing combat (reinforcements). That's combat-reinforcement assist, not combat-entry assist — and combat-entry is the F-55 surface 1 scope.

**Options:**
- **Option (a) — LOCKED:** Drop the `mode='combat'` gate. Hook fires on every new NPC upsert (`was_new=True` per §11.G). Session dedup prevents re-posting; suggestion only posts when SRD resolver returns a result. Worst case: occasional noise suggestion for a shopkeeper or non-combatant that the DM ignores. Accepted cost.
- **Option (b):** Keep the gate. Accept narrow scope; rebrand as combat-reinforcement assist. Rejected — does not close F-55 surface 1.
- **Option (c):** Defer — cache the suggestion at upsert time, post when mode flips to combat. Rejected — adds state, adds latency between narration and suggestion, and the DM has already moved on.

**Locked:** Option (a). No mode gate. Hook fires on every successful new-row `npc_upsert`. Session dedup remains the only re-post guard.

---

## 12. Future work (out of scope — file but don't expand)

- **`!init add` raw-message intercept (v1.x).** Fallback hook for DMs who skip narration. Regex on user messages matching `!init add <name>`. Posts suggestion to `#dm-aside` concurrent with Avrae processing. Session dedup prevents double-suggestion if NPC extractor already fired.

- **Multi-monster plural shortcut (v1.x).** "3 goblins" / "a pack of bandits" / "two wolves" detection. LLM returns count alongside candidate; suggestion emits N `!init madd` commands. Defer until single-creature volume is understood.

- **Narration context for LLM suggester (v1.x).** Pass recent narration snippet alongside creature name. "The creature emerges from a swamp" gives habitat context; "armored knight" narration gives class context. Currently: name only.

- **Skeleton stat-hint integration (v1.x).** When skeleton.md declares an NPC with a `CR:` line (Track 6 #4 v1.x), the suggestion can cross-reference skeleton-authored CR vs. SRD CR and flag divergence.

- **Encounter balance advisory (separate track).** "Giant Frog at CR 1/4 vs. your level-5 party — this is trivial combat." Party-level aggregation not yet implemented; Track 4 #4+ territory.

- **Suggestion history slash command (v1.x).** `/srd-suggestions` — lists suggestions made this session with outcome inference (which NPC names appear as `avrae_madd` vs. `<None>` in subsequent init-list parses).

- **Index update cadence.** `srd_monsters.json` is generated once from 5e-database. When 5e-database adds content (rare for SRD-constrained builds), re-run `generate_srd_index.py` and commit. No runtime impact.

- **Skeleton-authored homebrew analogs (v2).** DM declares in skeleton.md: "Spiny Toad → Giant Frog" for a known homebrew/narrative substitute. System uses this mapping directly without LLM call. Filed as a stretch goal when the homebrew-creature miss rate is visible in logs.

---

## Appendix A — SRD monster index JSON schema

```json
{
  "type": "object",
  "description": "Lowercase monster name → SRD entry. Key = canonical lowercase name.",
  "patternProperties": {
    "^[a-z ]+$": {
      "type": "object",
      "required": ["name", "cr", "hp", "ac"],
      "properties": {
        "name": {"type": "string",  "description": "Display name (title case)"},
        "cr":   {"type": "string",  "description": "CR as string: '0','1/8','1/4','1/2','1','2',..."},
        "hp":   {"type": "integer", "description": "Average HP from SRD stat block"},
        "ac":   {"type": "integer", "description": "Base AC from SRD stat block (no shield)"}
      }
    }
  }
}
```

Sample entries (representative, not exhaustive):
```json
{
  "goblin":             {"name": "Goblin",            "cr": "1/4", "hp": 7,   "ac": 15},
  "giant frog":         {"name": "Giant Frog",        "cr": "1/4", "hp": 18,  "ac": 11},
  "twig blight":        {"name": "Twig Blight",       "cr": "1/8", "hp": 4,   "ac": 13},
  "owlbear":            {"name": "Owlbear",           "cr": "3",   "hp": 91,  "ac": 13},
  "bandit captain":     {"name": "Bandit Captain",    "cr": "2",   "hp": 65,  "ac": 15},
  "young red dragon":   {"name": "Young Red Dragon",  "cr": "10",  "hp": 178, "ac": 18}
}
```

---

## Appendix B — LLM suggester prompt contract (locked for v1)

**System prompt** (see §5 `_LLM_SYSTEM` constant for full text):

Key constraints locked for v1:
- Output: `{"candidate": "exact SRD name", "confidence": float}` — two fields, no deviation
- candidate must be an exact SRD monster name or empty string
- confidence is 0.0–1.0
- Six exemplars provided (Spiny Toad, Forest Spider, Cave Bat, Goblin Captain, Fog Wraith, XyzPlorp)

**Validation gate (mandatory, in `resolve()`):**
```python
# After _llm_suggest() returns (candidate, confidence):
entry = _MONSTER_INDEX.get(candidate.lower().strip())
if not entry or confidence < _CONFIDENCE_THRESHOLD:
    return None   # §1b: index validates; below-threshold = no suggestion
```

This gate is the §1b enforcement point. The LLM is a proposer, not a decision-maker. If the LLM proposes a name that isn't in the SRD index, the gate discards it silently.

**Tuning surface:** Six exemplars can be extended in v1.x if `method=llm` produces poor suggestions (low DM acceptance rate inferred from `posted=1` followed by `!init add` rather than `!init madd` in subsequent init-list logs).

---

*Spec drafted: 2026-05-07, Session 1 of three. Patched to v1.1: 2026-05-08 (§11.H locked, mode gate removed, §2 closure framing, §2 doctrinal anchor). Locked to v1.2: 2026-05-08 (§11.A–§11.E all locked Option 1; tests 9–10 replaced with valid Jaccard examples; §8 two-line log shape documented; §6 was_new dedup primacy noted; §10 init_directive cross-reference added). Session 3 (implementation) may begin. _LLM_CACHE transient-failure fix rolls into Session 3 scope.*
