# Track 4 #3 — Time Progression — Design Spec v1.2 (LOCKED)

**Status:** LOCKED — Session 2 complete. §11.A–§11.I all locked (2026-05-08). Push-backs accepted: §11.B=(c) skip /rest per Doctrine §6 observed-friction discipline; §11.G=(b) arrival_time display-only to avoid the live `arrival_time='evening'` default trap. Surfaced additions §J.1–§J.6 patched into spec body (phase_delta normalization formula in §5, set_phase precedence invariant in §11.I, skeleton-seed §17 exception in §11.D and §6, dnd_time_advancements cascade requirement in §4, no-op telemetry contract in §8). §J.7 cross-ref fix applied in §12. Post-lock §11.I call-site count tightened from "all six" to "four" per actual locks. Session 3 (implementation) may begin. Test extensions per §K (set_phase, cascade, large-phase_delta, skeleton-seed) roll into Session 3 scope.

**Pattern:** New deterministic time-advancement primitive (`advance_time()` in `dnd_engine.py`), pure-function directive sibling (`compute_time_directive` / extension to `render_state_footer` per §59), Avrae rest-event hook extension. No LLM in the time-decision path (Doctrine §1a). LLM time-mention extraction (Doctrine §1b application) deferred to v1.x.

**Track:** Track 4 #3 — first ship in the motion-systems thread under F-54 (stagnation drift). Independent of the Combat Playability Cluster (Track 6 #5.x); neither thread blocks the other (FAILURES.md F-55 disposition).

**Failure mode this begins addressing:**
- **F-54 surface 1 — "the world doesn't visibly evolve."** Sessions feel good for 30–60 minutes then drift over longer arcs because the world persists but does not move. Time progression v1 closes this single symptom by introducing a campaign clock that visibly advances at scene transitions, travel, and rest events. Other F-54 symptoms (scene immortality, motif compulsion F-52, advancement starvation, equal-weight narration) are sibling ships under the motion-systems thread, not promised by v1. Honest scope per Doctrine §45.

---

## 1. Proposed decisions (recommendations for Jordan's review — NOT locked)

These are doctrinal floor items derived from Doctrine §1a / §17 / §59 / §45. They are recommendations, not commitments — Jordan's review pass can reject any of them. Decisions that are genuine architecture trade-offs (granularity, schema location, who-advances, surface, in-fiction vs structured, multiplayer, §1b extraction integration, /travel reconciliation) live in §11.

1. **Time advancement is deterministic Python only (Doctrine §1a).** The LLM does NOT decide when time advances or by how much. Every time-field write originates from a `/`-command handler, an Avrae-event listener, or a deterministic parser of a structured DM input — never from LLM narration parsing. The LLM may *narrate the consequence* of an advancement that already happened deterministically ("the sun sets," "you wake at first light") — that is allowed and expected, but the write happened first.

2. **Single write path for time fields (Doctrine §17).** All writes to whatever time fields exist (whether a column on `dnd_scene_state`, rows in a `dnd_time_advancements` log, or both — see §11.C) flow through one engine helper: `advance_time(campaign_id, days_delta, phase_delta, source, source_detail) → TimeAdvancement | None`. New surfaces (rest, travel, /advance, hooks) call this single writer; they do not introduce parallel writers. The constraint is load-bearing for invariant enforcement (§16) and audit-log integrity.

3. **Soft-fail at every call site (Doctrine §59).** Any exception in time advancement is caught and logged at the orchestration layer; narration always posts. Time progression bugs MUST NEVER block a DM turn. Same sibling pattern as `compute_loot_directive`, `compute_persistence_directive`, `render_state_footer`, `compute_combat_redirect_directive`, `compute_setup_plan`, `build_advisory_context`. v1's directive/footer additions become the seventh canonical instance.

4. **Always-fire telemetry per advancement.** A `time_advance:` log line emits on every successful call to `advance_time()` (and a `time_advance: source=... err=...` line on caught exceptions). Diagnostic baseline so post-ship session logs answer the empirical question: how often does the clock actually advance, by what source, by what amount? Mirrors the always-fire discipline from `directive_emit:`, `commitment_directive:`, `srd_suggestion:`.

5. **F-54 closure proof — narrow.** v1 ships the deterministic primitives that make the world's clock visible and advanceable. v1 closes ONLY the "the world doesn't visibly evolve" symptom of F-54. Calendar systems, day-of-week effects, NPC schedules, weather, seasons, in-game-event scheduling, motif decay, scene immortality countermeasures — all §12 future work. Companion motion-system ships (Scene Lifecycle v1, motif decay, advancement surfacing) are siblings, not v1 promises.

6. **Honest scope statement.** Time progression is foundational, not finished. v1 produces the smallest deterministic surface that lets a campaign accumulate visible time across sessions. Quality of time-mention parsing, calendar fidelity, and NPC/world-event coupling are all v1.x or later, gated on observed log signal. No layer is added speculatively.

---

## 2. Goal and context

### F-54 surface 1: the world doesn't visibly evolve

F-54 is the umbrella diagnostic for stagnation drift — the architectural floor is correct (persistence, canonical state, adjudication, directives all work), but the world does not visibly *move* over a session. Subordinate symptoms include scene immortality, motif compulsion (F-52), advancement starvation, equal-weight narration, and **absence of visible advancement signals.** The last symptom is what v1 addresses: a player should be able to look at a Discord embed footer and read "Day 3, Evening" — and that signal should advance when the party rests, travels, or completes a long task.

**Current state (verified by §3 grep):**
- `dnd_scene_state` has no time columns. Mode flips between exploration / combat / social / travel / downtime, but there is no campaign-day, time-of-day, or elapsed-time field anywhere in the schema.
- `/travel` accepts an `elapsed: str = 'a day'` parameter today — but it goes only into the `TRAVEL_TRANSITION` directive block as one-shot prompt content. It is never persisted; the destination row gets `current_location_id` updated, but no time field is written. After a `/travel arrival_time=midnight`, the next narration block has no awareness that midnight just happened.
- `/rest` does not exist. Avrae's `!lr` / `!sr` are observed by `_handle_rest_event` and only flip combat→exploration plus clear combatants. No time advances.
- `dm_philosophy.md` says "Time pressure is real" but gives the DM no clock to anchor that pressure to.
- `skeleton.md` declares no starting day, time of day, or season.

The result: every narration turn lives in an undated present. A six-month campaign feels like one long session because no signal external to the prose says "this is later than last time." The world persists; it does not move.

### THE_GOAL alignment

- *"A campaign should be able to run for six months and feel like it's been six months."* — A visible, advancing campaign clock is the simplest possible surface for cross-session continuity. The clock is not the *only* signal of a long campaign (NPC arcs, faction shifts, completed quests all do this work too), but it is the cheapest and most legible.
- *"The world should breathe."* — Day-phase advancement gives the world a respiratory rhythm: morning → afternoon → evening → night → next day. The corpus findings (3,592 records across 140 episodes; every CRD3 episode contains time-mentions; mean ~26 per episode) confirm that skilled DMs narrate this rhythm continuously. The breath is already the texture of good play; the system just needs to know which beat it is on.
- *"Memorable details should recur intentionally, not compulsively."* — The DM directive that fires on advancement turns can request *one* in-fiction time-mention beat ("dusk arrives," "morning breaks"), not a per-turn weather report. Texture, not tic.

### Doctrine §1a anchor

This is the second post-§1a/§1b-split spec to write the §1a side of the line explicitly. (Track 6 #5.1 was the §1b inaugural; this is the §1a sibling.) The LLM is **not** in the time-advancement decision path. The chain:

```
Trigger (deterministic):
  /travel command         → parse elapsed string
  Avrae !lr observed      → standard +long rest interval
  /rest command           → parse rest kind
  /advance command        → DM specifies delta directly
                                ↓
Validator (deterministic):
  parse_elapsed(elapsed_str) → (days_delta, phase_delta) | error
                                ↓
Writer (single path):
  advance_time(campaign_id, days_delta, phase_delta,
               source, source_detail)
                                ↓
Reader (per-turn, pure function):
  compute_time_directive(scene_state) → directive string
  render_state_footer(scene_state)    → footer line carries day+phase
                                ↓
LLM narrates:
  "Dusk arrives. The town's lanterns flicker on..."
  (consequence-only — the advancement already happened)
```

At no point does the LLM decide what time it is or whether time advances. The proposer→validator→writer chain is fully deterministic. The LLM's only role is consequence narration on advancement turns.

For the §1b inaugural application of LLM time-mention extraction (e.g., DM types "After about an hour of searching..." in narration → a §1b suggester proposes a +1 phase advancement → DM approves), see §11.F — defer to v1.x recommended.

### What v1 is NOT

- **Not a calendar.** No month names, no day-of-week, no seasons, no holidays, no festival dates. Pure day-counter + phase-of-day enum. Calendar systems are §12 (the campaign skeleton can declare a starting calendar reference in v2 if needed).
- **Not a weather system.** Day-phase is *not* "morning is sunny, evening is rainy." Weather is a separate motion-system thread and is filed §12.
- **Not NPC-schedule-aware.** v1 does not know that the blacksmith closes at sundown. NPC schedules can read from time state in v1.x once the primitive is stable.
- **Not a scene-lifecycle solution.** Scenes don't expire because time passed. Scene lifecycle is the second filed motion-system candidate; coupling them is exactly the pre-sequencing F-54's prescription was rejected for.
- **Not a §1b time-mention extractor.** The corpus findings doc already exists for that surface; the §1b suggester ships at v1.x once v1 primitives are observable. v1 ships deterministic only.

---

## 3. Architecture

### Diagnostic-grep findings (Doctrine §56) — what doesn't change vs what's new

Per §47 / §56, the spec is anchored to current code state, not assumed state. Findings from the diagnostic-grep pass:

#### Pre-existing (v1 builds on top of, does not replace)

| Surface | File | Current behavior | v1 relationship |
|---|---|---|---|
| `dnd_scene_state` schema | `dnd_engine.py:325` | 12 columns: `campaign_id`, `location`, `mode`, `focus`, `established_details`, `active_npcs`, `active_threats`, `open_questions`, `tension`, `last_player_action`, `last_scene_change`, `updated_at`. **No time columns.** | v1 adds `campaign_day INTEGER` and `day_phase TEXT` columns (per §11.C lock — Option (a)). Existing columns unchanged. |
| `/travel` command | `discord_dnd_bot.py:2965` | Accepts `elapsed: str = 'a day'` and `arrival_time: str = 'evening'`. Renders into the `TRAVEL_TRANSITION:` directive block. Persists `current_location_id` only. | v1 calls `advance_time()` from `/travel` after the location write. The existing `elapsed` string is parsed by `parse_elapsed()` (deterministic). The `arrival_time` parameter is **display-only** per §11.G=b lock — it flows into the TRAVEL_TRANSITION block as flavor but does NOT drive `advance_time()`. |
| `_handle_rest_event` | `discord_dnd_bot.py:831` | Avrae `!lr`/`!sr` observed → flips combat→exploration + clears combatants. **No time advance.** Comment: "Pure mechanical mapping — no LLM." | v1 extends this hook to call `advance_time()` after the mode flip. Long rest = `(+1 day, set_phase='Morning')`. Short rest = `(0 days, +1 phase)`. Per §11.B lock — Avrae rest is the v1 rest path. Existing combat-clear logic unchanged. |
| `render_state_footer` | `dnd_orchestration.py:2356` | Returns mode-only header: `"📖 Exploration\n"`, `"💬 Social\n"`, `"⚔ Combat — Round N\n"`. Pure function, soft-failed in `_dm_respond_and_post`. | v1 extends to append `· Day {N}, {Phase}` after the mode glyph, e.g. `"📖 Exploration · Day 3, Evening\n"`. Pure function unchanged in shape. |
| `transition_context` plumbing | `dnd_engine.py:4813` | Reusable directive block for `/travel`. Comment: "reusable for future `/rest`, `/camp`, `/downtime`, `/fastforward`." | v1 ships `/advance` using the same `transition_context` shape. `/rest` is filed §12 per §11.B=c lock; the plumbing remains staged for the v1.x `/rest` lift. |
| `dm_philosophy.md` | `dm_philosophy.md` | "Time pressure is real. Consequences linger. The DM's job is not to..." | v1 adds a paragraph: when the campaign clock advances, narrate the transition once, then move on. No clock-stuffing per turn. (Optional doc-pass; not gating.) |
| `skeleton.md` schema | `skeleton_loader.py` | No time-of-start declaration. Current campaign 17 skeleton has no time fields. | v1 reads default starting state from optional `## Starting time` skeleton section per §11.D=a lock; falls back to defaults `(day=1, phase="Morning")` if absent. Loader's seed-write is a narrow §17 exception (§J.3) — direct INSERT/UPDATE on `dnd_scene_state`, NOT through `advance_time()`. |
| `init_directive` / `commitment_directive` etc. | `dnd_orchestration.py` | Pure-function directive siblings, all read scene_state + return string. | v1 adds `compute_time_directive(scene_state, just_advanced)` as the seventh sibling — fires non-empty only when an advancement just happened, per §11.E=(i)α + (ii)α lock. |

#### Net-new artifacts

| Artifact | Location | Purpose |
|---|---|---|
| `advance_time()` | `dnd_engine.py` (new function) | Single write path. Validates inputs, writes the new state, appends to advancement log, emits telemetry. |
| `parse_elapsed(elapsed_str)` | `dnd_engine.py` (pure function) | Maps `"1 day"` / `"an hour"` / `"three days"` / `"overnight"` / `"a few hours"` → `(days_delta, phase_delta)`. Deterministic regex/keyword table. Returns `None` on unparseable input (logs `parse_elapsed: input=... result=none`). |
| `compute_time_directive()` | `dnd_orchestration.py` (pure function) | The seventh §59 sibling. Returns directive string when the most recent advancement is fresh; empty otherwise. Per §11.E=(iii)α — recency check on `dnd_time_advancements` log table within ~60s window (tunable). |
| `dnd_time_advancements` table | `dnd_engine.py` schema | Append-only log. One row per advancement event. Per §11.C=a lock — both column-on-scene_state AND log table. Must be added to `_CAMPAIGN_SCOPED_TABLES` per §4 cascade requirement. |
| `/advance` slash command | `discord_dnd_bot.py` | DM-only manual time advancement. §11.B locked Option (c) — ships in v1. |
| ~~`/rest` slash command~~ | ~~`discord_dnd_bot.py`~~ | **Filed §12 per §11.B locked Option (c).** `/rest` was speculative (offline-Avrae use case); not v1 scope. The `transition_context` plumbing remains staged for the v1.x ship. |
| Skeleton-loader seed (§11.D=a applies) | `skeleton_loader.py` | Direct INSERT/UPDATE on `dnd_scene_state` for `(campaign_day, day_phase)` from the `## Starting time` declaration; bypasses `advance_time()` and does NOT write to `dnd_time_advancements`. Narrow §17 exception, initialization-only, idempotent (only fires when scene_state row is absent). See §11.D. |
| `time_advance:` telemetry log | wherever `advance_time()` is called | Always-fire per advancement. |
| `parse_elapsed:` telemetry log | inside `parse_elapsed()` | Always-fire per parse attempt (success or fail). |

#### Architecture is honest about pre-existing surface

`/travel`'s `elapsed` parameter is the most important anchor: it already exists and is used by Jordan in actual play. v1 must not break that surface. The reconciliation was a §11 decision; per §11.G=b lock, `/travel` writes the clock from `parse_elapsed(elapsed)` only — `arrival_time` is display-only flavor in the TRAVEL_TRANSITION block. This avoids the live `arrival_time='evening'` default trap that option (d) would have introduced.

### Precedence diagram (full advancement flow)

```
DM types: /travel destination:Redhaven elapsed:"two days"
    ↓
discord_dnd_bot.travel():
    set_current_location(...)              [existing]
    parse_elapsed("two days") → (2, 0)     [new — deterministic]
    advance_time(campaign_id, 2, 0,         [new — single writer]
                 source='travel',
                 source_detail='Redhaven, two days')
        ↓
        validate inputs  (days >= 0, phase in enum)
        SELECT current campaign_day, day_phase FROM dnd_scene_state
        compute new state → (campaign_day=5, day_phase='Morning')   # was day 3 evening
        UPDATE dnd_scene_state SET campaign_day=5, day_phase='Morning'
        INSERT INTO dnd_time_advancements (...)
        log("time_advance: campaign=N before=3,Evening after=5,Morning "
            "delta=2d+0p source=travel detail='Redhaven, two days'")
        return TimeAdvancement(...)
    ↓
build_dm_context():                         [unchanged]
    transition_context = "TRAVEL_TRANSITION: ..." (existing)
    [optional] time_directive = compute_time_directive(scene_state, just_advanced=True)
        → "TIME_ADVANCE: Day 5, Morning. Narrate one beat of arrival "
          "in the new time of day, then hand agency back to the player."
    ↓
render_state_footer(scene_state):           [extended]
    mode='exploration' → "📖 Exploration · Day 5, Morning\n"
    ↓
LLM narrates arrival at Redhaven on Day 5 morning.
Player sees footer "📖 Exploration · Day 5, Morning" — visible signal.
```

Soft-fail wrapping at every call site:

```python
# In /travel:
try:
    parsed = parse_elapsed(elapsed)
    if parsed:
        advance_time(campaign['id'], *parsed,
                     source='travel', source_detail=destination)
except Exception as e:
    log(f"/travel: advance_time error: {e!r}")
    # narration continues; the location write already succeeded
```

---

## 4. Schema

This section describes the schema per §11.C=a lock — column on `dnd_scene_state` + new `dnd_time_advancements` log table.

### Proposed addition to `dnd_scene_state`

```sql
ALTER TABLE dnd_scene_state ADD COLUMN campaign_day INTEGER DEFAULT 1;
ALTER TABLE dnd_scene_state ADD COLUMN day_phase TEXT DEFAULT 'Morning';
```

- **`campaign_day`** — integer, monotonically non-decreasing per campaign. Starts at 1. No overflow concern (10-year campaign at 1 in-game day per session = 520 days).
- **`day_phase`** — TEXT enum. Allowed values (locked at the engine layer, not in the DB constraint): `Morning`, `Midday`, `Afternoon`, `Evening`, `Night`, `Late Night`. Six phases, even-spaced conceptually. Per §11.A=a lock.

Defaults `day=1, phase='Morning'` mean every existing campaign auto-migrates to "Day 1, Morning" on first read. No data migration script required (SQLite ADD COLUMN with DEFAULT covers it).

### New table: `dnd_time_advancements` (audit log)

```sql
CREATE TABLE IF NOT EXISTS dnd_time_advancements (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id     INTEGER NOT NULL,
    before_day      INTEGER NOT NULL,
    before_phase    TEXT    NOT NULL,
    after_day       INTEGER NOT NULL,
    after_phase     TEXT    NOT NULL,
    days_delta      INTEGER NOT NULL,
    phase_delta     INTEGER NOT NULL,
    source          TEXT    NOT NULL,    -- 'travel'|'rest_long'|'rest_short'|'advance'|'narration_suggester' (v1.x)
    source_detail   TEXT    DEFAULT '',  -- e.g. 'Redhaven, two days', 'long rest', 'DM:/advance hours:6'
    created_at      TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_time_adv_campaign ON dnd_time_advancements(campaign_id);
CREATE INDEX IF NOT EXISTS idx_time_adv_created  ON dnd_time_advancements(campaign_id, created_at);
```

The log is **append-only**. No UPDATE, no DELETE. v1 has no UI surface that reads from it; it exists for post-session diagnostic queries:

- "How many advancement events fired this session?"
- "Which sources fire most often — travel, rest, or /advance?"
- "Did the campaign clock actually advance over the long arc?"

Without the log, the only post-hoc record of advancement is the `time_advance:` log line in `dnd.log`, which gets rotated/lost over time. The log table is the durable record.

§11.C considered alternatives — **column-only** (no log table), or **log-only** (no column, derive current state from the most recent log row) — and locked **both** (Option (a)).

**Campaign cascade requirement (VIRGIL_MASTER §6 hard requirement).** The new `dnd_time_advancements` table MUST be appended to `_CAMPAIGN_SCOPED_TABLES` in the same patch as the table creation. Per VIRGIL_MASTER §6: *"When you add a new per-campaign table, append it to `_CAMPAIGN_SCOPED_TABLES` in the same patch or campaign purges silently leave orphan rows."*

`_CAMPAIGN_SCOPED_TABLES` currently holds 8 tables; v1 extends to 9. The `/purgecampaign` and `/purgeallcampaigns` cascades flow through this constant; missing the new table means a purged campaign leaves rows in `dnd_time_advancements` indefinitely.

A cascade-integrity test is added in §9 (Session 3 scope): create a campaign, advance time once, run `/purgecampaign`, verify `dnd_time_advancements` row count for that campaign is 0.

The `dnd_scene_state` column additions (`campaign_day`, `day_phase`) do NOT need cascade work — `dnd_scene_state` is already in `_CAMPAIGN_SCOPED_TABLES`, and column-level additions inherit the row-level cascade behavior.

### Schema invariants (engine-enforced, not DB-enforced)

- `day_phase` must be one of the six allowed values per §11.A=a lock. `advance_time()` rejects bad input (returns None with a logged diagnostic); the DB column is TEXT for forward compatibility if v1.x extends or revises the enum.
- `campaign_day >= 1` always. `advance_time()` refuses negative deltas in v1 (no "rewind"). Filed §12 if ever needed.
- After every successful `advance_time()`, the scene_state row and the most recent log row agree on `(campaign_day, day_phase)`. If they diverge, log a `time_advance: invariant_breach` line and trust the log as authoritative.

---

## 5. Time advancement rules

### Who advances time (per §11.B lock)

**Authoritative writers (deterministic, single-path through `advance_time()`):**

| Source | Trigger | Default delta | Notes |
|---|---|---|---|
| `travel` | `/travel` command after location write | parsed from `elapsed` string via `parse_elapsed()`; falls back to `(1, 0)` on parse failure | Existing `elapsed` parameter preserved (Doctrine §47 — don't break the live surface) |
| `rest_long` | Avrae `!lr` observed by `_handle_rest_event` | `(+1 day, set phase='Morning')` | Wake-up to morning is the canonical D&D long-rest narrative shape |
| `rest_short` | Avrae `!sr` observed by `_handle_rest_event` | `(0 days, +1 phase)` | One-hour-equivalent → next phase; doesn't roll over the day boundary in v1 unless already in Late Night |
| `advance` | `/advance` slash command | DM-specified `days` and `phases` (with optional `set_phase`) | DM authority for narrative compression. §11.B locked Option (c). |
| ~~`rest_command`~~ | ~~`/rest kind:long\|short`~~ | ~~Same defaults as Avrae rest events~~ | **Filed §12 per §11.B locked Option (c).** Avrae `!lr`/`!sr` is the v1 rest path. |
| `narration_suggester` | §1b LLM time-mention extraction (v1.x — §11.F) | parsed from suggested phrase; DM approves | **Deferred to v1.x per §11.F locked Option (a).** Source enum reserved for v1.x; not written by v1. |

**Non-writers (explicitly):**

- LLM narration. Even if the DM's narration includes "two hours later," the system does NOT parse that to advance time in v1. (v1.x ships the §1b suggester for that surface.)
- Player input. Players narrate intent; players do not advance the clock.
- Mode flips alone. `/mode travel` or `/mode social` do not advance time. Time is independent of mode in v1.

### `advance_time()` contract

```python
def advance_time(
    campaign_id: int,
    days_delta:  int,
    phase_delta: int,
    source:      str,
    source_detail: str = '',
    set_phase:   str | None = None,    # §11.I locked Option (a)
) -> TimeAdvancement | None:
    """Single write path for campaign time.

    Pure-function-internally over (current_day, current_phase, deltas,
    set_phase) → (new_day, new_phase). Then writes both dnd_scene_state
    and dnd_time_advancements transactionally.

    Validates:
      - days_delta >= 0          (no rewind in v1)
      - phase_delta >= 0          (no rewind; arbitrary magnitude allowed)
      - source in {'travel','rest_long','rest_short','advance'}
        (v1-locked enum; 'narration_suggester' reserved for v1.x §1b ship)
      - set_phase in PHASES or None
      - scene_state row exists for campaign_id (else returns None with
        err='no scene_state row' — see §8 missing-campaign no-op contract)

    set_phase precedence (load-bearing — §11.I):
      When set_phase is not None, phase_delta is ignored; the writer
      computes resolved_phase_delta = (target_idx - current_idx) mod 6
      and records all three values in the audit log.

    Returns:
      TimeAdvancement(before_day, before_phase, after_day, after_phase,
                      days_delta, phase_delta, resolved_phase_delta,
                      source, source_detail, set_phase)
      on success.
      None on validation failure, missing scene_state row, or DB error
      (with a logged diagnostic line).

    Soft-fail at the call site: callers wrap in try/except per Doctrine §59.
    """
```

### Phase rollover semantics

The six phases form a cycle: `Morning → Midday → Afternoon → Evening → Night → Late Night → Morning (next day)`.

- `phase_delta=+1` from `Evening` → `Night` (same day).
- `phase_delta=+2` from `Late Night` → `Midday` (next day, increments `campaign_day` by 1).
- `phase_delta=0` with `days_delta=+2` → next day same phase. But long-rest narratively jumps to Morning regardless of current phase — that requires set-phase semantics, which a pure-delta signature cannot express. The signature options (set_phase param vs sibling helper vs caller-side modular math) are surfaced as **§11.I** (not implementation-phase, since the choice ripples into the locked call sites and affects §17 single-write-path discipline). §11.I is locked Option (a): `set_phase: str | None = None` parameter on `advance_time()`.

**Normalization for arbitrary `phase_delta` magnitudes.** The writer normalizes via direct modular math, not phase-by-phase iteration:

```
total_steps    = current_phase_idx + phase_delta + (days_delta * 6)
new_day        = before_day + (total_steps // 6)
new_phase_idx  = total_steps % 6
```

This handles any non-negative `phase_delta` correctly: `phase_delta=12` from any phase resolves to `(+2 days, same phase)`; `phase_delta=13` from `Morning` resolves to `(+2 days, Midday)`; `phase_delta=25` from `Evening` resolves to `(+4 days, Late Night)`. The writer never iterates phase-by-phase; the modular form is O(1) regardless of input magnitude. The writer rejects negative `phase_delta` per the existing v1 invariant (no rewind). Tests pin the formula at `phase_delta=12, 13, 25` to protect against future "iterate +1 phase N times" implementations (§K test extension).

### Display format (per §11.E lock)

Footer: `📖 Exploration · Day 3, Evening`

In-fiction: when an advancement just happened, the directive (§11.E) requests one in-fiction beat. The corpus findings show Matt does both — `scene_transition` ("the next morning") and `cumulative_anchor` ("It is now late afternoon"). Both shapes are valid; the DM picks based on scene flow.

---

## 6. Surface integration

### `/travel` integration (per §11.G lock — Option (b), `arrival_time` display-only)

Current call shape preserved. `/travel` writes the clock from `parse_elapsed(elapsed)` only; `arrival_time` flows into the `TRAVEL_TRANSITION` prompt block as flavor text but does NOT drive `advance_time()`. This avoids the live `arrival_time='evening'` default trap (every defaulted call would silently land in Evening under the rejected option (d)).

```python
async def travel(interaction, destination, elapsed='a day', arrival_time='evening'):
    ...
    # existing location resolution unchanged
    set_current_location(...)

    # NEW: deterministic time advancement (§11.G=b — elapsed only)
    try:
        parsed = parse_elapsed(elapsed)            # 'two days' → (2, 0)
        if parsed is not None:
            advance_time(campaign['id'], parsed[0], parsed[1],
                         source='travel',
                         source_detail=f"{destination}; elapsed={elapsed}")
        # arrival_time is NOT passed to advance_time — display-only per §11.G=b lock.
        # It still appears in the TRAVEL_TRANSITION block (existing behavior preserved).
    except Exception as e:
        log(f"/travel: advance_time error: {e!r}")

    # existing DM call unchanged
    await _dm_respond_and_post(...)
```

DMs who want explicit phase control after travel use `/advance phases:N` (or `/advance set_phase=Evening` once §11.I=a's `set_phase` parameter is wired through `/advance`'s args). v1.x escape: if observed friction shows DMs typing explicit `arrival_time='midnight'` and confused that the clock didn't reflect midnight, v1.x ships option (d) with `arrival_time` default flipped to `None` (gated on explicit-provided detection).

### `_handle_rest_event` integration (per §11.B lock)

```python
async def _handle_rest_event(message, rest_evt):
    ...
    # existing combat-state cleanup unchanged
    if current_mode == 'combat':
        set_scene_mode(campaign['id'], 'exploration')
        clear_active_turn(campaign['id'])
        clear_combatants(campaign['id'])

    # NEW: time advancement based on rest kind (§11.I=a — set_phase param)
    try:
        if rest_kind in ('long', 'longrest', 'lr'):
            # Long rest jumps to next morning regardless of current phase
            advance_time(campaign['id'], 1, 0,
                         source='rest_long',
                         source_detail='Avrae !lr',
                         set_phase='Morning')
        elif rest_kind in ('short', 'shortrest', 'sr'):
            # Short rest bumps one phase
            advance_time(campaign['id'], 0, 1,
                         source='rest_short',
                         source_detail='Avrae !sr')
    except Exception as e:
        log(f"_handle_rest_event: advance_time error: {e!r}")
```

### ~~Optional new `/rest` command~~ — filed §12 per §11.B=c lock

Per §11.B locked Option (c), `/rest` is **NOT** a v1 ship. The Avrae `!lr`/`!sr` event hook is the v1 rest path. `/rest` was speculative (offline-Avrae use case); Doctrine §6 (observed-friction discipline) defers it to v1.x. The `transition_context` plumbing remains staged for the v1.x ship (line 2961 of `discord_dnd_bot.py` lists `/rest` among planned future-transition siblings). Filed in §12 with the trigger condition for the v1.x lift.

### New `/advance` command (per §11.B lock — ships in v1)

```python
@bot.tree.command(name='advance', description='[DM] Manually advance the campaign clock.')
@app_commands.describe(
    days='Days to advance',
    phases='Phases to advance',
    set_phase='Optional: jump to a specific phase (Morning/Midday/.../Late Night)',
)
async def advance_cmd(interaction, days: int = 0, phases: int = 0,
                       set_phase: str | None = None):
    ...
    advance_time(campaign['id'], days, phases,
                 source='advance',
                 source_detail=f'/advance days={days} phases={phases}'
                               + (f' set_phase={set_phase}' if set_phase else ''),
                 set_phase=set_phase)
```

DM authority surface for narrative compression that travel doesn't cover (e.g. "skip three days of downtime"). The optional `set_phase` parameter exposes §11.I=a's writer parameter to the DM directly — useful for "advance to next morning regardless of current phase" without computing a phase delta by hand.

### Directive block (per §11.E lock — fires on just-advanced turns only)

```
TIME_ADVANCE:
campaign_day=5
day_phase=Morning
just_advanced=true
prior_phase=Evening
prior_day=3
source=travel
instruction=Open with one in-fiction beat marking the new time of day
(dawn light, lanterns guttering out, market stalls opening, whatever fits the
location). Then hand agency back to the player. Do not narrate the
intervening hours.
```

Fires only on the turn immediately following an advancement (per §11.E sub-(ii)α lock — just-advanced-only timing).

### Footer (per §11.E lock — always-on once §11.A and §11.C are locked)

`📖 Exploration · Day 5, Morning`

Always-on per §11.A + §11.C + §11.E locks. The prompt also gets a directive (in-fiction beat) on advancement turns per §11.E sub-(i)α + sub-(ii)α; both surfaces ship in v1.

### Skeleton starting time (per §11.D lock)

Optional skeleton field:

```markdown
## Starting time
day=1
phase=Morning
```

Loader reads this on `/play` if scene_state row doesn't already exist. Falls back to `(1, 'Morning')` if absent. Per §11.D lock + §17 narrow-exception (§J.3): the loader's seed-write goes directly to `dnd_scene_state`, NOT through `advance_time()` (the seed is initialization, not advancement; no `dnd_time_advancements` row is written).

---

## 7. Display format

### Structured (footer)

`Day 3, Evening` is the canonical structured form. Always present in the footer when scene_state exists. Cheap to render, unambiguous, doesn't depend on LLM cooperation.

### In-fiction (LLM narration)

The corpus findings (track5_findings_time_mention.md) show Matt's two dominant categorizable shapes:

- **`scene_transition`** (17.7% of corpus records) — "the next morning," "two weeks later," "after a long rest." Discrete cuts.
- **`cumulative_anchor`** (10.4%) — "It is now late afternoon," "It's been three hours." Explicit clock statements.

The directive instructs the LLM to fire **one** of these on advancement turns and stop. No turn-after-turn restating. The advance is a moment, not a steady drip — matches THE_GOAL's "memorable details should recur intentionally, not compulsively."

### When does each fire?

- Footer: every turn when scene_state exists. Reflects current state, regardless of whether time just advanced.
- In-fiction directive: only on the turn immediately following an advancement (one-shot, not persisted across turns). Per §11.E lock — sub-(ii)α just-advanced-only timing.

### Recommended pairing (per §11.E lock — both surfaces ship)

Both. Structured footer for player situational awareness; in-fiction beat once per advancement to tie the advancement into the narrative texture. The corpus findings give independent empirical justification for both shapes — Matt does both, neither dominates.

---

## 8. Telemetry

### `time_advance:` log line — always-fire per call

Format:

```
time_advance: campaign={N} source={travel|rest_long|rest_short|advance|rest_command|narration_suggester}
              before={day},{phase} after={day},{phase}
              days_delta={int} phase_delta={int}
              detail='{source_detail}'
```

Emits:
- On every successful `advance_time()` call.
- On caught-exception path: `time_advance: campaign={N} source=... err={repr}` (single-line, no `before`/`after`).

`grep "time_advance:"` answers: how often does the clock advance, per session, per source.

**Missing-campaign no-op contract.** `advance_time()` reads the current scene_state row first via `SELECT campaign_day, day_phase FROM dnd_scene_state WHERE campaign_id=?`. If no row exists (caller bug — passes a stale or fake campaign_id; or race condition — campaign was purged between reads), the writer returns `None` and emits a distinct diagnostic log line:

```
time_advance: campaign={N} source={...} err='no scene_state row'
```

The writer does NOT INSERT into `dnd_time_advancements` without a corresponding scene_state UPDATE. The column-and-log-write atomicity is preserved: either both writes succeed inside the transaction, or neither does.

### `parse_elapsed:` log line — always-fire per parse attempt

Format:

```
parse_elapsed: input='{raw}' result={days},{phases}|none
```

Helps tune the parser's keyword/regex table from real DM-typed strings. Especially important since `/travel`'s `elapsed` is a free-text field today.

### Integration with `directive_emit:`

Add `time={1|0}` field to the existing `directive_emit:` log line in `dm_respond` — fires `1` when `compute_time_directive` returned non-empty content this turn, `0` otherwise. Per-turn aggregate signal for the time directive's empirical base rate.

```
directive_emit: campaign=N pacing=... central_thread=... ... time=1
```

### State-footer signals extension

`render_state_footer` already returns a `signals` dict with `mode`, `active_turn_name`, `round`. Extend with `campaign_day`, `day_phase` for the per-turn `state_footer:` log line. The footer log already fires every turn; this just surfaces the existing scene_state fields into the diagnostic.

### Grep patterns

| Pattern | Tells you |
|---|---|
| `grep "time_advance:"` | Every advancement event |
| `grep "time_advance:.*source=travel"` | Travel-driven advances only |
| `grep "time_advance:.*err="` | Soft-fails at any call site |
| `grep "parse_elapsed:.*=none"` | Strings the parser couldn't handle (tuning surface) |
| `grep "directive_emit:.*time=1"` | Turns where the time directive fired non-empty |

---

## 9. Test surface

Test count is proportional to the resolver+hook count from Track 6 #5.1. Roughly 25–35 tests across pure-function, DB integrity, and integration surfaces.

### `test_advance_time.py` (engine-layer single-write-path tests)

**Basic advance:**
1. `advance_time(c, 1, 0, 'travel', '')` from `(1, 'Morning')` → `(2, 'Morning')`, returns `TimeAdvancement` with correct fields
2. `advance_time(c, 0, 1, 'rest_short', '')` from `(1, 'Morning')` → `(1, 'Midday')`
3. `advance_time(c, 0, 6, 'advance', '')` from `(1, 'Morning')` → `(2, 'Morning')` — full cycle wraps the day
4. `advance_time(c, 0, 7, 'advance', '')` from `(1, 'Morning')` → `(2, 'Midday')`
5. `advance_time(c, 2, 3, 'travel', '')` from `(1, 'Morning')` → `(3, 'Evening')` — combined deltas

**Phase rollover:**
6. From `(1, 'Late Night')` with `phase_delta=+1` → `(2, 'Morning')`
7. From `(1, 'Night')` with `phase_delta=+3` → `(2, 'Midday')`

**Validation:**
8. `days_delta=-1` → returns `None`, logs error (no rewind in v1)
9. Bad source (`source='unknown'`) → returns `None`, logs error
10. `phase_delta=0, days_delta=0` → returns `None`, logs error (zero advance is meaningless; if this becomes a real shape later, allow with diagnostic flag)

**Persistence:**
11. After `advance_time()` succeeds, `get_scene_state(c)['campaign_day']` reflects new day
12. After `advance_time()` succeeds, `get_scene_state(c)['day_phase']` reflects new phase
13. After `advance_time()` succeeds, latest row in `dnd_time_advancements` for that campaign matches scene_state
14. Two consecutive `advance_time()` calls produce two rows in the log

**Soft-fail at engine layer:**
15. DB error (mock) inside `advance_time()` → returns `None`, logs exception, scene_state unchanged

### `test_parse_elapsed.py` (pure-function parser tests)

16. `parse_elapsed('a day')` → `(1, 0)`
17. `parse_elapsed('1 day')` → `(1, 0)`
18. `parse_elapsed('three days')` → `(3, 0)`
19. `parse_elapsed('an hour')` → `(0, 1)` — one phase as the smallest sub-day unit (per §11.A=a lock — 6 phases)
20. `parse_elapsed('a few hours')` → `(0, 1)` (or `(0, 2)` — locked at parser ship time)
21. `parse_elapsed('overnight')` → `(1, 0)` with phase set to Morning via the rest-shape variant; OR `(0, +N to Morning)` — implementation-phase decision documented
22. `parse_elapsed('two weeks')` → `(14, 0)`
23. `parse_elapsed('xyzzy')` → `None`, logs `parse_elapsed: input='xyzzy' result=none`
24. `parse_elapsed('')` → `None`

### `test_compute_time_directive.py` (sibling pure-function)

25. `compute_time_directive(scene_state, just_advanced=False)` → `''` (silent on non-advancement turns)
26. `compute_time_directive(scene_state, just_advanced=True)` → non-empty directive containing `Day {N}, {phase}` and an instruction to narrate one beat
27. Directive does not contain literal "TIME_ADVANCE:" keyword bleeding into narration (the marker is for prompt structure only)

### `test_render_state_footer.py` (existing test file extended)

28. Footer with no time fields (legacy scene_state) renders as before — `'📖 Exploration\n'` (backward compat)
29. Footer with `campaign_day=3, day_phase='Evening'` renders `'📖 Exploration · Day 3, Evening\n'`
30. Combat footer extends similarly: `'⚔ Combat — Round 2 · Day 3, Evening\n...'`
31. `signals` dict includes `campaign_day` and `day_phase` keys

### `test_travel_time_integration.py` (command integration)

32. `/travel destination:Redhaven elapsed:'two days'` → after the call, scene_state reflects +2 days
33. `/travel destination:Redhaven elapsed:'xyzzy'` (unparseable) → time does NOT advance, narration still posts (soft-fail), location still updates
34. `/travel` with an explicit `arrival_time='midnight'` — verify scene_state phase is set purely from `parse_elapsed(elapsed)`; `arrival_time` flows into TRAVEL_TRANSITION text only (per §11.G=b lock — `arrival_time` is display-only, does NOT modify the clock)

### `test_rest_time_integration.py` (Avrae hook integration)

35. Avrae `!lr` event → time advances by `(+1 day, phase=Morning)`, mode flips to exploration as before
36. Avrae `!sr` event → time advances by `(+1 phase)`, mode unchanged
37. `_handle_rest_event` exception inside `advance_time` does not crash the existing combat-clear logic

### `test_time_schema_integrity.py` (DB-level)

38. `dnd_scene_state` has `campaign_day` and `day_phase` columns after schema init
39. `dnd_time_advancements` table exists after schema init
40. Default values for new campaigns: `campaign_day=1, day_phase='Morning'`
41. Migration from a pre-v1 row (no time columns set) succeeds — defaults apply

Total: ~30–40 tests. Comparable to Track 6 #5.1 (30 tests across resolver + hook + index integrity).

---

## 10. Edge cases and integration

### Multiplayer time consistency

Time state is per-campaign (not per-player, not per-party-instance). Doctrine §17 single-write-path means concurrent advancement attempts serialize through `advance_time()`. SQLite's default-isolation behavior (BEGIN IMMEDIATE on UPDATE) is sufficient for the v1 multiplayer surface (≤4 concurrent players per campaign; a `/travel` and an `!lr` cannot fire simultaneously without one of them blocking briefly). Per §11.H lock — campaign-wide; per-party-instance filed §12.

### Campaign restart / process restart

Persistence: scene_state row + dnd_time_advancements log are both on disk. Bot restart preserves time state; the next `/play` reads from scene_state and continues. No process-lifetime state required.

### Existing campaign migration

`ALTER TABLE ... ADD COLUMN ... DEFAULT 1` (and DEFAULT 'Morning') means existing rows auto-default on read. Campaign 17 (live) starts at "Day 1, Morning" on first read. Jordan can use `/advance` if he wants to set a different starting state, or skeleton.md `## Starting time` (per §11.D lock) declares it explicitly via the loader's seed-write path.

### Time-of-day affecting NPC availability

Out of scope for v1. NPCs do not check time before answering. v1.x: per-NPC `available_phases` field on `dnd_npcs`, read by the NPC reference layer. Filed §12.

### Rest mechanics consistency

Avrae handles HP/spell-slot recovery on `!lr`/`!sr`. v1's time advancement is **independent** of those mechanics — advancing the clock does NOT trigger HP regen, and Avrae's HP regen does NOT trigger time advancement (v1 advances only when the rest *event* fires, which Avrae emits on `!lr`/`!sr`). The two systems run in parallel through the shared rest event.

If the DM advances time via `/advance` *without* a corresponding rest, Avrae HP/spell slots are unaffected — the party "ages" without resting. This is intentional (a multi-day forced march without rest IS a thing in D&D). Filed for review if Jordan wants a §11 follow-up.

### `/travel` to an unresolved destination

Existing `/travel` handles unresolved destinations via the `location_label_override` path. v1 still calls `advance_time()` regardless of whether the destination row resolved — time advances even when the location row is fresh/unknown. (The time advancement is independent of location persistence.)

### Travel with elapsed=0 or negative

`/travel` with `elapsed='0 minutes'` or similar parses to `(0, 0)` → `advance_time()` returns None per validation rule (§9 test 10). Telemetry logs the no-op. Narration proceeds. Filed v1.x if "instant teleport travel" becomes a UX shape (probably not).

### Advancement during combat

Time advances DURING active combat are unusual but legal — e.g. a multi-round chase that crosses a phase boundary. v1 allows `advance_time()` while `mode=combat`. The footer shows `⚔ Combat — Round N · Day 3, Evening` correctly. The DM can use `/advance` mid-combat; the directive's "one beat" instruction still applies on the next narration turn.

### `is_anchored` carryover from corpus findings

The corpus extractor's `is_anchored` field (relative-time references like "the next morning" referencing a prior anchor) does not have a runtime analog in v1. v1 advances atomically; the engine doesn't need to remember the previous phase except in the immediate just-advanced flag (§11.E). Anchors are corpus-extractor concern, not runtime.

### Skeleton overrides (per §11.D lock)

If skeleton.md declares `## Starting time day=15 phase=Evening` and the campaign's existing scene_state has `day=23, phase=Morning`, the skeleton declaration is ignored on reload (scene_state wins; skeleton applies only on first scene_state initialization). Loader behavior matches existing skeleton fields' override discipline. Subject to §11.D.

### LLM narration that contradicts the clock

The LLM might narrate "the sun is setting" when the footer says "Day 3, Morning." v1 has no detector for this — the LLM is asked, in the time directive, to honor the clock, but a hallucination is possible. Detection is out of scope for v1. The §1b time-mention extractor (deferred to v1.x — §11.F) would surface these as a side effect: a narration phrase that parses to a phase mismatching scene_state could be flagged for DM review. Filed §12.

### Campaign-wide vs per-party-instance multiplayer

If a campaign supports multiple party instances ("split the party" across two voice channels), v1's single campaign-wide clock means one party's `/travel` advances the world for both. This is almost certainly correct for v1 — the world's clock isn't party-relative — but it is a design choice. §11.H surfaces it.

### Boot-sequence first-turn behavior

On the very first turn after `/play` for a new campaign, `compute_time_directive(scene_state, just_advanced=True)` should NOT fire (no prior advancement). The `just_advanced` flag is determined per the §11.E sub-(iii)α lock — recency check on the log table; if no log row exists for the campaign, the flag is False.

### Concurrent `/advance` and Avrae rest event

Race: DM types `/advance days:1` while Avrae fires `!lr`. Both call `advance_time()`. SQLite serializes; both writes succeed; clock advances by 1 day + 1 day = 2 days. This is technically "correct" (two distinct advancement events both happened) but probably not what the DM wanted. Filed for v1.x if observed in logs. The `dnd_time_advancements` log makes this debuggable — two rows separated by milliseconds with different sources.

---

## 11. Decision points needing Jordan's call

All nine §11 decisions are LOCKED as of 2026-05-08 (Session 2 lock-in-chat). Each section header carries the locked option, confidence, and the reasoning behind any push-back from the spec's pre-lock proposed default. Pre-lock option lists and "Why this is §11" rationale are preserved as historical context — useful for v1.x re-decision triggers when locked options need to be revisited from observed log signal.

### §11.A — Time granularity (LOCKED — Option (a))

**LOCKED: Option (a). Day + 6-phase enum.** Confidence: high. Corpus empirics support 6 phases over 4 (Late Night and Midday are observed in `cumulative_anchor` patterns); (c) hours over-specifies and pulls runtime narrative into mechanical-clock territory; (d) minutes is overkill; (e) day-only is too narrow for F-54 closure. v1.x escape: if logs show DMs frequently typing arrival-time strings outside the 6 phases, add aliases to the parser rather than re-tier granularity.

**Restate.** What's the smallest unit of time the clock tracks?

**Options.**

- **(a) Day + 6-phase enum (proposed).** `Morning / Midday / Afternoon / Evening / Night / Late Night`. Maps cleanly to `cumulative_anchor` corpus phrases ("It is now late afternoon," "pushing past one or two in the morning"). Coarse enough to never demand precise mechanical synchronization with Avrae spell durations; fine enough to give the world rhythm. THE_GOAL's "world should breathe" reads as texture, not precision.
- **(b) Day + 4-phase enum.** `Morning / Afternoon / Evening / Night`. Simpler. Loses "late night" and "midday" — borderline phrase compression onto neighbors.
- **(c) Day + hours (integer 0–23).** Most precise. Maps cleanly to D&D mechanical timings (long rest = 8h; spell durations in hours). Risk: pulls runtime narrative into mechanical-clock territory and forces decisions about when 9:43 a.m. becomes "late morning" — texture lost.
- **(d) Day + minutes (integer 0–1439).** Maximum precision. Almost certainly overkill — the corpus shows skilled DMs almost never use minute-level anchors except inside in-scene compression ("ten minutes of work"), and those are in-scene not campaign-clock advances.
- **(e) Abstract beats — only "Day N" with no time-of-day.** Simplest. Loses the diurnal texture entirely; the F-54 "world doesn't breathe" symptom only partially closes.

**Proposed default.** Option (a) — Day + 6-phase enum. The corpus skews toward day-and-up scales for cumulative_anchor (Matt's "it's late afternoon" pattern); 6 phases covers the observed vocabulary; cardinal advance (`+1 phase`) maps cleanly to short-rest semantics. Re-decidable from logs after a few sessions if 6 phases prove too granular or too coarse.

**Why this is §11, not §1.** Defensible alternatives exist. Option (c) — hours — is a real architecture (some VTTs use it). Option (b) — 4 phases — is simpler and might be enough. Surfaced for Jordan's call rather than pre-locked.

### §11.B — Who advances time (LOCKED — Option (c))

**LOCKED: Option (c). Travel + Avrae rests + /advance, skip /rest.** Confidence: medium. Push-back accepted from review: `/rest` solves a hypothetical (offline-Avrae play); Doctrine §6 (observed friction, not anticipated) and the "Don't add features… for hypothetical future requirements" baseline both push against it. `/advance` covers the genuine DM-explicit narrative-compression gap; `/rest` files in §12 with the `transition_context` plumbing already staged for the v1.x ship (line 2961 of `discord_dnd_bot.py` lists it as a planned future sibling). Re-decide if Jordan plans solo-no-Avrae sessions or if 5+ subsequent sessions show a rest-without-Avrae pattern in logs.

**Restate.** Which surfaces are authorized to call `advance_time()`?

**Options.**

- **(a) Travel + Avrae rests + /advance + /rest (proposed).** Four surfaces. `/travel` parses its existing `elapsed` string. Avrae `!lr`/`!sr` advance via the existing `_handle_rest_event` hook. `/advance` is a new DM-explicit surface. `/rest` is a new narrative-rest surface (separate from Avrae rest, for solo DM convenience).
- **(b) Travel + Avrae rests only.** No new commands. Smallest surface; relies on existing flows. DMs who want manual narrative compression have no clean surface ("just edit the DB"). Probably too narrow.
- **(c) Travel + Avrae rests + /advance only.** Skip `/rest`. Avrae's `!lr`/`!sr` already fire the rest event; a new `/rest` would be redundant unless the DM is solo without Avrae driving.

**Rejected (filed for completeness, not defensible as v1):**

- **(d) `/advance` only.** Doctrinal-cosplay — kills the live `/travel` `elapsed` parameter and the existing `_handle_rest_event` integration without a benefit. Doctrine §47 (specs respect the live surface) rules this out.
- **(e) Ship the §1b narration suggester in v1.** Duplicates §11.F; cannot be locked here without contradicting the v1-vs-v1.x decision in §11.F. Belongs in that decision, not this one.

**Proposed default.** Option (a). Adds two new commands (`/rest` and `/advance`) but keeps the surface surveyable. `/rest` provides offline-Avrae solo-DM coverage; `/advance` provides explicit narrative compression. Doctrine §1a is preserved (none of these are LLM-driven).

**Why this is §11.** Option (c) skipping `/rest` is also defensible — surface-area minimization is a real pull. The (a)-vs-(b)-vs-(c) trade-off is Jordan's call.

### §11.C — Schema location (LOCKED — Option (a))

**LOCKED: Option (a). Column on `dnd_scene_state` + `dnd_time_advancements` log table.** Confidence: high. Column gives cheap per-turn reads (footer fires every turn); log table gives durable advancement history without grep. Single-writer discipline preserved — both writes happen inside `advance_time()`'s one transaction. Cascade requirement on the new table is documented in §4 per VIRGIL_MASTER §6.

**Restate.** Where does time state live?

**Options.**

- **(a) Column on `dnd_scene_state` + `dnd_time_advancements` log table (proposed, both).** Current state is read directly from scene_state (cheap, single row); audit trail is in the log. Maps cleanly to existing scene_state read patterns. Two write surfaces but one writer (`advance_time()` writes both atomically).
- **(b) Column on `dnd_scene_state` only.** No log table. Telemetry log line is the only post-hoc record. Cheaper, but loses the durable audit trail — over a six-month campaign, knowing how many times the clock advanced and from what source requires keeping `dnd.log` files indefinitely.
- **(c) `dnd_time` table only (no scene_state column).** Each advancement is an INSERT; current state is the most recent row's `after_*` fields. Cleanest event-sourced design but every read of "current time" is a SELECT-with-ORDER-BY-DESC-LIMIT-1, which is fine performance-wise but slightly more costly than a column read.
- **(d) Column on `dnd_scene_state` + module-level in-memory log (no DB table).** The log lives only in process memory and rotates on restart. Loses durability.

**Proposed default.** Option (a). Column for cheap reads (used per-turn by footer/directive); log table for durability. The schema cost is small (two columns + one new table); the diagnostic value is real for a six-month-campaign goal.

**Why this is §11.** Option (b) is genuinely simpler and fits the "ship the smallest version that works" doctrine. Option (c) is event-sourcing-clean and fits the §17 single-source-of-truth shape better. The trade-off is real.

### §11.D — Skeleton starting-time field (LOCKED — Option (a))

**LOCKED: Option (a). Optional `## Starting time` skeleton section, falls back to defaults if absent.** Confidence: high. Existing campaigns auto-default to `(1, 'Morning')` per the column DEFAULTs; new or edited skeletons can declare `day=N` and `phase=Phase` for non-default starts. Pair with the seed-write §17 exception below (§J.3 patch).

**Restate.** Does `skeleton.md` declare a campaign starting day/phase, or do all campaigns start at default `(1, 'Morning')`?

**Options.**

- **(a) Optional skeleton field, falls back to defaults if absent (proposed).** New section: `## Starting time` with `day=` and `phase=` lines. `skeleton_loader.py` parses on `/play` and seeds scene_state if the row is fresh. Existing campaigns without the field default to `(1, 'Morning')` per the column DEFAULTs.
- **(b) No skeleton field — always defaults.** All campaigns start "Day 1, Morning." DM uses `/advance` after `/play` if a different starting state is wanted. Smaller surface; one fewer skeleton parser shape.
- **(c) Required field — campaigns refuse to load without it.** Rejected — breaks all existing campaigns.

**Proposed default.** Option (a). Optional field is the smallest spec-skeleton shape that gives campaigns choice without breaking compat. The current campaign 17 skeleton has no time field; it gets defaults; if Jordan wants to change Campaign 17's start, he adds the field.

**Why this is §11.** Option (b) — defaults only — is also defensible. Skeleton-as-config is a §11 trade-off, not a doctrinal lock. If skeleton starts collecting too many configurable fields, the maintenance shape changes; we should pick deliberately.

**Seed-write path (§17 exception, narrow).** When the skeleton loader detects a fresh `dnd_scene_state` row AND `skeleton.md` declares `## Starting time`, the loader directly INSERTs/UPDATEs `dnd_scene_state.campaign_day` and `day_phase` with the declared values. The seed write does NOT route through `advance_time()` and does NOT write a row to `dnd_time_advancements`.

Rationale: campaign initialization is not an advancement event — nothing advanced; the campaign began. Routing the seed through `advance_time()` would pollute the advancement log with non-events that downstream queries (`grep "time_advance:" | wc -l` for advancement frequency, source-distribution analysis) would have to filter out via a sentinel `source='seed'`. The narrow §17 framing: *"`advance_time()` is the sole writer for runtime time advancement. Campaign initialization has a separate one-shot writer in the skeleton loader, scoped to the first-scene_state seed only, idempotent because the seed only fires when the row is absent."* Sibling note added to §6 architecture table.

### §11.E — Surface architecture, timing, and `just_advanced` mechanic (LOCKED — (i)α + (ii)α + (iii)α)

**LOCKED: combined (i)α + (ii)α + (iii)α.** Confidence: high. Footer always carries `Day N, Phase` (extends `render_state_footer`); directive fires only on just-advanced turns (one in-fiction beat); just-advanced is detected via recency check on `dnd_time_advancements` (`MAX(created_at)` within ~60s window, tunable from telemetry). The combined lock follows corpus empirics (Matt does both surfaces, both timings) and lands on the most-debuggable just-advanced mechanic (the log table is already the audit). Re-decide window if `directive_emit:.*time=1` correlations against `time_advance:` show >5% missed-fires after tuning to 120s; switch to (iii)β process-memory flag and accept restart-loss as the simpler trade.

**Restate.** How does the prompt see the clock, when does each surface fire, and how does the system know "this is an advancement turn"? Three sub-questions that lock together — they cannot be locked independently because surface choice constrains display options, and timing constrains the just-advanced mechanic. The former separate §11.E (prompt surface) + §11.F (display) split risked contradictory locks (e.g., "footer only" + "in-fiction beat on advancement" with no surface to deliver the beat). One §11, three nested sub-questions.

#### Sub-question (i) — Surfaces

- **(α) Footer always + directive only on just-advanced turns (proposed).** Footer carries `Day 3, Evening` every turn (ambient signal for player situational awareness). Directive block fires only on the turn immediately following an advancement, instructing one in-fiction beat. Empirical justification from corpus findings: Matt does both `scene_transition` (17.7%, "the next morning") and `cumulative_anchor` (10.4%, "It is now late afternoon"); both shapes are validated DM moves. Footer is cheap (extends existing `render_state_footer` per §59); directive is one-shot.
- **(β) Footer only.** No directive. LLM gets `Day 3, Evening` in the footer prelude (or wherever footer text reaches the model) and picks up texture from there. Smallest prompt cost; least LLM-cooperation risk. Locks (ii) timing to "footer-every-turn" and (iii) just-advanced mechanic to "not needed." Risk: LLM ignores the footer and narrates without time texture; player-side clock advances feel mechanical rather than narrative.
- **(γ) Directive only.** No footer extension. Maximally narrative; loses per-turn ambient signal for the player. Footer extension is cheap, so this option is essentially dominated by (α).
- **(δ) Footer always + directive every turn (low-pressure restate).** "It is currently Day 3, Evening" prepended to every prompt. F-30 prompt-bloat risk: another always-on block competing with pacing/central_thread/consequence/commitment/capability/init/loot/redirect/footer. Risks F-52-adjacent compulsive re-mention of time-of-day (THE_GOAL: "memorable details should recur intentionally, not compulsively").

#### Sub-question (ii) — Directive timing (only meaningful if (i) ≠ β)

- **(α) On just-advanced turn only (proposed under (i)α).** One-shot per advancement; ties the in-fiction beat to the structural transition. Matches the corpus's discrete-cut shape.
- **(β) Every turn.** Always-on; restates current time-of-day every prompt. Same F-52 motif-compulsion risk as (i)δ — different surface but same compounding pressure.
- **(γ) Phase-bordering turns only.** Heuristic — fires when `day_phase` differs from the prior turn's value, regardless of whether `advance_time()` was called. Probably duplicates (α) under §17 single-writer discipline (the only way phase changes is through `advance_time()`); only meaningful if (iii) loses the flag.

#### Sub-question (iii) — `just_advanced` mechanic (only meaningful if (ii) = α)

- **(α) Recency check on `dnd_time_advancements` log (proposed).** Per-turn `compute_time_directive` reads `MAX(created_at)` for this campaign from the log table; fires if within a tunable window (~60s starting guess). Durable across bot restart — the log row survives, so a campaign that advanced just before a crash still sees the directive on the next turn. Risk: long-running turns (multi-actor arbitration ≥10s, chained narration spreading further apart) could mis-window. Window is tunable from telemetry once `time_advance:` and `directive_emit:.*time=1` lines accumulate.
- **(β) Process-memory flag.** `advance_time()` sets `_just_advanced[campaign_id] = True`; next `dm_respond` consumes (read-and-clear). Clean semantics — fires exactly once per advancement, immune to long-turn windowing. Risk: bot crash between `advance_time()` and the consuming `dm_respond` loses the flag; the post-restart turn won't see the just-advanced signal even though the log row exists. No window-tuning needed.
- **(γ) Per-process counter.** `_advance_seq[campaign_id]` increments on advance; per-turn comparator against `_last_seen_seq[campaign_id]`. Robust to long turns. Same restart-loss as (β) but more durable across slow turns within a process.

**Proposed default.** (i)α + (ii)α + (iii)α — footer always; directive on just-advanced turns; recency check on the log table for the just-advanced signal. The recency window is the most-debuggable mechanism (the log table is the audit; mis-fires show up in `directive_emit:.*time=1` against `time_advance:` correlations) and degrades gracefully under long turns (a missed just-advanced fire isn't a correctness bug; the next advancement re-fires; the footer continues to carry day+phase).

**Why this is one §11, not three.** The choices nest. (i)β kills the directive surface, which makes (ii) and (iii) moot. (ii)β kills the just-advanced concept, which makes (iii) moot. Locking them separately risks contradictory locks. One decision; three sub-questions; lean (α/α/α).

### §11.F — §1b LLM time-mention extraction in v1 vs v1.x (LOCKED — Option (a))

**LOCKED: Option (a). Defer to v1.x.** Confidence: high. Same shape as Track 6 #5.1's pattern — primitives first, observed signal, then build the §1b suggester on a known-good baseline. Ship the §1a primitives clean; let v1 logs answer the empirical question of "does the deterministic clock match what skilled DMs do in narration?" before adding the §1b layer.

**Restate.** Should the bot watch DM/LLM narration for time mentions and validator-gate them as advancement signals? This is the inaugural §1b application from the post-#5.1 ship pattern (§1b validated-suggester).

**Options.**

- **(a) Defer to v1.x (proposed lean).** v1 ships deterministic primitives only. Once v1's logs accumulate, the §1b suggester is a follow-up ship: small LLM call extracts `(category, granularity, phrase)` from the previous narration turn → validator checks against a `parse_elapsed`-shaped allow-list → bot posts a suggestion to `#dm-aside` (`"Detected possible time advance: 'an hour later'. Apply +1 phase? Type /advance phases:1"`). DM approves explicitly. Mirrors Track 6 #5.1 §1b pattern precisely.
- **(b) Ship in v1.** Inaugural §1a/§1b pairing in one spec. More scope; richer first ship; matches the structural shape of "first §1a since the doctrine split." Risk: unproven primitives + unproven extractor in one ship; harder to attribute behavior in logs.
- **(c) Build the suggester but gate it OFF in v1 (config flag).** Code lives in the codebase but doesn't fire until Jordan flips `TIME_SUGGESTER_ENABLED=1`. Ships infrastructure without runtime risk. Doctrinal cost: feature flag, which `Don't add features… for hypothetical future requirements` discourages.

**Proposed default.** Option (a). Defer to v1.x. Ship the §1a primitives clean; let v1 logs answer the empirical question of "does the deterministic clock match what skilled DMs do in narration?" before adding the §1b layer that bridges narration to advancement.

**Why this is §11.** Option (b) is a defensible scope choice if Jordan wants the §1a/§1b pairing in one spec. Genuine trade-off — Session 2 will lean harder once the v1 surface is locked.

### §11.G — `/travel` `elapsed` and `arrival_time` reconciliation (LOCKED — Option (b))

**LOCKED: Option (b). `arrival_time` is display-only.** Confidence: medium. Push-back accepted from review: the existing `arrival_time: str = 'evening'` default would silently land every default-call in Evening under (a)/(d), which is a real surprise for existing campaigns (`/travel destination:X elapsed:'two days'` from Day 1 Morning would land at Day 3 Evening, not Day 3 Morning, purely from the function-signature default). Surface-minimization wins: `/travel` writes the clock from `parse_elapsed(elapsed)` only; `arrival_time` flows into the `TRAVEL_TRANSITION` prompt block as flavor (LLM sees it) but does NOT drive `advance_time()`. DMs who want explicit phase control after travel use `/advance phases:N`. v1.x escape: if observed friction shows DMs typing `arrival_time='midnight'` and confused that the clock didn't reflect midnight, v1.x ships (d) with `arrival_time` default flipped to `None` (gated on explicit-provided detection).

**Restate.** `/travel` already accepts `elapsed: str = 'a day'` and `arrival_time: str = 'evening'` — both are free-text strings rendered into the `TRAVEL_TRANSITION` prompt block. v1 wants to use them to drive `advance_time()`. How?

**Options.**

- **(a) Parse `elapsed` deterministically; `arrival_time` becomes an explicit phase override (proposed).** `parse_elapsed('two days')` → `(2, 0)` advance; if `arrival_time='evening'` is also specified, set phase to 'Evening' after the day advance. Single function call. `arrival_time` is also mapped through a parser (`'dawn'→'Morning'`, `'midnight'→'Late Night'`, etc.). Precedence: explicit `arrival_time` > parsed `elapsed` for the phase. Days come from `elapsed` only.
- **(b) Parse `elapsed` for days + phases; `arrival_time` passes through to the prompt block only (display-only).** No phase override — the structured day/phase comes purely from `elapsed`'s parse. `arrival_time` is preserved in the directive text the LLM sees but doesn't write the clock. Risk: DMs typing `arrival_time='midnight'` may expect the clock to reflect midnight, but it won't unless `elapsed` parses to that phase.
- **(c) Add a new structured `/travel days:N phases:M` overload, deprecate the free-text `elapsed`.** Cleanest going forward; breaks the live surface. Doctrine §47 violation (specs drift from code; respect the live surface).
- **(d) Parse both; if they conflict, log and prefer `arrival_time` over parsed phase.** Same as (a) but with explicit conflict telemetry.

**Proposed default.** Option (d). Same write semantics as (a), plus a `time_advance: conflict=elapsed_vs_arrival_time before=... reconciled=arrival_time` log line on disagreement. Costs nothing at the writer; gives observability.

**Why this is §11.** Option (b) is genuinely defensible — keeping `arrival_time` as display-only preserves the existing prompt-block intent. Option (a)/(d) are slightly more aggressive. Trade-off is real.

### §11.H — Multiplayer time-sharing (LOCKED — Option (a))

**LOCKED: Option (a). Campaign-wide.** Confidence: high. One `(campaign_day, day_phase)` per `campaign_id`. (b) per-party-instance is structurally sensible only when "split the party" is a live UX concern; today no per-campaign table carries `party_instance_id`, and adding one to time alone creates partial state-sharding. Multi-party would shard alongside scene_state, active NPCs, and active threats — not as a standalone time feature. Filed §12.

**Restate.** v1 stores one `(campaign_day, day_phase)` per `campaign_id`. If the party splits across two voice channels and one half travels, does the clock advance for everyone or just the travelers?

**Options.**

- **(a) Campaign-wide for v1 (proposed lean).** One clock per campaign. Both halves of a split party share the world's time. Almost certainly correct for the v1 multiplayer surface — the world's time isn't party-relative.
- **(b) Per-party-instance.** Each party tracks its own clock. Adds a `party_instance_id` dimension. Out of scope for v1; filed §12 if multi-party shows up.
- **(c) Per-character.** Maximum granularity. Almost certainly wrong (the world has one clock for everyone in it).

**Proposed default.** Option (a). Surfaced as §11 only because Jordan should see the choice explicitly — the multi-party surface comes up periodically.

**Why this is §11.** Default is high-confidence, but the choice is structural and worth Jordan's explicit acknowledgment.

---

### §11.I — `advance_time()` signature: how to express "set phase to Morning" (LOCKED — Option (a))

**LOCKED: Option (a). Add `set_phase: str | None = None` parameter to `advance_time()`.** Confidence: medium-high. (b) sibling helper noted as close runner-up; deciding factor was signature-stability (an optional keyword argument absorbs future writer parameters more cleanly than two named helpers — e.g. v1.x's §1b suggester may add a `narration_hint` parameter). All set-phase semantics live inside the writer; call sites read naturally; the audit-log row carries both requested and resolved forms (see precedence invariant below). Re-decide if Session 3 implementation reveals call-site readability is materially worse with (a) — if `set_phase='Morning'` keeps tripping reviewers asking "wait, what does that override?", switch to (b); both options preserve §17 and produce identical telemetry.

**Restate.** §5's long-rest semantics ("rest narratively jumps to Morning regardless of current phase") cannot be expressed by a pure-delta signature. A `phase_delta` integer can land on a specific target phase only if the caller computes `(target - current) mod 6` — but reading scene_state and computing the delta in the caller leaks logic outside the single writer, weakening Doctrine §17 discipline. Under the locked configuration (§11.B=c skip /rest + §11.D=a + §J.3 seed-bypass + §11.G=b arrival_time display-only), the signature ripples into 4 v1 call sites (travel, /advance, Avrae `!lr` hook, Avrae `!sr` hook), so this is not implementation-phase.

**Options.**

- **(a) Add `set_phase: str | None = None` to `advance_time()` (proposed).** When set, overrides `phase_delta` — the writer reads current phase, computes the modular delta internally, writes both the requested override and the resolved delta into the log row for audit clarity. One helper, one optional param, all set-phase semantics live inside the writer. Call sites read naturally:

  ```python
  # Long rest: jump to next morning regardless of current phase
  advance_time(c, 1, 0, source='rest_long', source_detail='Avrae !lr',
               set_phase='Morning')

  # Travel with explicit arrival time
  advance_time(c, 2, 0, source='travel', source_detail='Redhaven',
               set_phase='Evening')

  # Short rest: just bump one phase
  advance_time(c, 0, 1, source='rest_short', source_detail='Avrae !sr')
  ```

- **(b) Add a sibling `advance_time_to_phase(campaign_id, days_delta, target_phase, source, source_detail)` helper.** Internally calls `advance_time()` with the computed delta. Two named helpers, one writer underneath. Cleaner per-call-site readability ("rest = `advance_time_to_phase(c, 1, 'Morning', 'rest_long')`"); slightly more API surface; same single-writer discipline preserved.

- **(c) Force callers to compute the modular delta themselves.** Single signature, no extra params. Each call site that wants set-phase semantics duplicates the modular-delta math: `target_idx = PHASES.index('Morning'); current_idx = PHASES.index(current_phase); phase_delta = (target_idx - current_idx) % 6`. §17 shape weakened — multiple sites doing identical phase-resolution logic; future signature change requires touching all six.

**Proposed default.** Option (a). One signature, one optional param, all phase-resolution logic inside the writer. The audit-log row can carry both the caller-requested form (e.g. `set_phase=Morning, days_delta=1`) and the resolved form (e.g. `phase_delta=4` if rolling Evening→Morning) for diagnostic clarity. Option (b) is the close runner-up — the named helper reads more cleanly at call sites.

**Why this is §11.** The signature is load-bearing for §17. Option (c) genuinely simplifies the writer but multiplies call-site math. Option (b) is API-design defensible. Cannot be relegated to implementation-phase without locking the §17 shape post-hoc.

**`set_phase` precedence invariant (load-bearing).** When `set_phase` is not None, the writer ignores `phase_delta` entirely and computes `resolved_phase_delta = (target_idx - current_idx) mod 6`. The audit-log row records all three values:

- `set_phase` — the caller's declared target (e.g. `'Morning'`)
- `phase_delta` — the caller's also-passed-but-ignored delta (e.g. `2`)
- `resolved_phase_delta` — the actual delta written (e.g. `4`)

This makes call-site bugs (passing both arguments inadvertently) visible in the log without crashing the writer. Soft-handle per Doctrine §59: do not raise on conflicting arguments; `set_phase` wins, and `phase_delta` is recorded with `set_phase_overrode_phase_delta=true` for the diagnostic.

Test cases (added in Session 3 per §K):
- set_phase only (phase_delta=0)
- phase_delta only (set_phase=None)
- both passed together — verify set_phase wins, log shape complete with all three values

---

## 12. Future work (filed-not-sequenced — Doctrine §38)

Listed for visibility. Not a sequence. Each ship re-decides priority from logs after the prior ship lands.

- **§1b time-mention extractor (v1.x candidate).** Per §11.F=a lock. Watch DM/LLM narration; suggest advancements with DM approval. Inaugural §1b application after Track 6 #5.1's pattern. Triggered when v1 logs accumulate enough `time_advance:` and `parse_elapsed:` baseline data to validate the suggester against observed DM behavior.
- **`/rest` slash command (v1.x candidate).** Per §11.B=c lock. Filed because `/rest` was speculative in v1 (offline-Avrae use case); ships in v1.x if 5+ subsequent sessions show a rest-without-Avrae narrative pattern in logs, OR if Jordan plans imminent solo-no-Avrae sessions. The `transition_context` plumbing is staged (line 2961 of `discord_dnd_bot.py`); the lift is small.
- **Calendar layer.** Month names, day-of-week, year, in-universe calendar (Harvest Close, Zenith, etc.). Skeleton declares calendar reference; loader maps `campaign_day` to "23 Sundas of Harvest Year 1481." Filed once `campaign_day` numbers feel meaningful enough that a calendar overlay would help.
- **Weather system.** Day-phase × location → weather descriptor. Adjacent motion-system thread; not coupled to time progression v1.
- **NPC schedules.** Per-NPC `available_phases` field. NPC reference layer reads it. Blacksmith closes at sundown; tavern keeper's at the bar 'Midday' through 'Late Night.' Filed once narrative friction with always-available NPCs is observed.
- **Day-of-week effects.** Market day, holy day, festival day. Coupled to calendar; same filing dependency.
- **Seasonal effects.** Winter snow, summer heat. Coupled to calendar + weather.
- **In-game-event scheduling.** "The festival starts in three days" → countdown directive when within window. Filed once consequence-surfacing analog for forward-looking events feels needed.
- **Travel-time-from-distance.** Travel parser today is `parse_elapsed("two days")` — DM declares the duration. v2 could derive it from `distance_between(origin, destination) × terrain_modifier`. Lots of state required (location coordinates, terrain types) — far from v1.
- **Time-of-day advisory directive.** Light-level / vision penalties at Night and Late Night phases (no candles → disadvantage on perception). Adjacency to capability gating. Filed once vision mechanics surface.
- **Scene lifecycle coupling.** Track 4 #4 candidate. Scenes that have lasted across multiple advancement events get retirement pressure. Sibling motion-system ship.
- **Motif decay.** F-52 the lute problem. Could be coupled to time advancement (motifs introduced N phases ago decay). Filed once Scene Lifecycle's design is clearer.
- **Time-rewind support.** v1 forbids negative deltas. If campaign-replay-from-an-earlier-state ever becomes a UX need, allow it via DM-explicit `/advance` + a confirmation gate.
- **Campaign-clock visualization.** A `/timestate` command: pretty-prints recent advancement log entries. Diagnostic sugar for the DM.
- **Multi-party split-clock.** Per §11.H option (b). Filed once multi-party surfaces in active play.
- **Cross-campaign time alignment.** Probably never needed (each campaign is independent), but if a meta-narrative ever bridges campaigns…

---

## Appendix A — `parse_elapsed` keyword/regex sketch (illustrative; not locked)

The parser maps free-text duration strings to `(days_delta, phase_delta)`. Deterministic — no LLM. Small lookup table + regex matchers, in priority order.

```python
# Exact keyword matches
EXACT = {
    'a day': (1, 0), 'one day': (1, 0), '1 day': (1, 0),
    'overnight': (1, 0),                    # caller may pass set_phase='Morning' per §11.I=a + Avrae !lr semantics
    'a week': (7, 0), 'one week': (7, 0),
    'a few hours': (0, 1),
    'a couple hours': (0, 1),
    'an hour': (0, 1), 'one hour': (0, 1), '1 hour': (0, 1),
    'a few minutes': (0, 0),                # below granularity floor → no advance
    'a moment': (0, 0),                     # below granularity floor
    # ... extended in implementation
}

# Number-word lookup
NUMBER_WORDS = {
    'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
    'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
    'a couple': 2, 'a few': 3, 'several': 4,
}

# Patterns: '<number> <unit>'
PATTERNS = [
    (r'(\d+|[a-z ]+)\s+days?',   lambda n: (n, 0)),
    (r'(\d+|[a-z ]+)\s+weeks?',  lambda n: (n*7, 0)),
    (r'(\d+|[a-z ]+)\s+hours?',  lambda n: (0, max(1, n // 6))),  # ~6h per phase
    (r'(\d+|[a-z ]+)\s+minutes?',lambda n: (0, 0)),                # below floor
]
```

Tunable from telemetry: `parse_elapsed: input='a half hour' result=none` is the signal that the parser needs another keyword.

Per §11.A=a lock (6 phases), the `~6h per phase` mapping is the v1 default. v1.x can extend the keyword table (e.g. `'a half hour'` → `(0, 0)` no-advance, or `'an hour and a half'` → `(0, 1)` ceiling) based on observed `parse_elapsed:.*=none` log lines.

---

## Appendix B — `compute_time_directive` body sketch (illustrative)

```python
def compute_time_directive(scene_state: dict | None,
                           just_advanced: bool) -> str:
    """Pure function. Returns directive string for the current turn,
    or '' to render silent. Sibling of compute_pacing_directive,
    compute_central_thread_directive, etc.

    just_advanced: True per §11.E sub-(iii)α lock — recency check against
    MAX(created_at) on dnd_time_advancements for this campaign within
    ~60s of this turn's start (window tunable from telemetry). Re-decide
    to (iii)β process-memory flag if directive_emit:.*time=1 correlations
    against time_advance: show >5% missed-fires after window tuning to 120s.

    Returns '' on every turn except the immediate post-advancement one.
    Per Doctrine §59 sibling pattern — caller wraps in try/except.
    """
    if not scene_state or not just_advanced:
        return ''
    day = scene_state.get('campaign_day') or 1
    phase = scene_state.get('day_phase') or 'Morning'
    return (
        "TIME_ADVANCE:\n"
        f"campaign_day={day}\n"
        f"day_phase={phase}\n"
        "instruction=Open with one in-fiction beat marking the new time of day. "
        "One sentence, location-appropriate. Then return agency to the player. "
        "Do not narrate the intervening hours."
    )
```

The instruction text is the v1 starting point; tunable based on observed LLM compliance.

---

## Appendix C — Sample telemetry session

A short play session might produce these lines (illustrative):

```
[10:14:02] /play campaign=17
[10:14:02] state_footer: campaign=17 mode=exploration day=1 phase=Morning
[10:14:35] state_footer: campaign=17 mode=exploration day=1 phase=Morning
[10:18:20] parse_elapsed: input='two days' result=2,0
[10:18:20] time_advance: campaign=17 source=travel before=1,Morning after=3,Morning days_delta=2 phase_delta=0 detail='Redhaven; elapsed=two days'
[10:18:21] state_footer: campaign=17 mode=exploration day=3 phase=Morning
[10:18:21] directive_emit: campaign=17 pacing=medium central_thread=1 ... time=1
[10:23:11] state_footer: campaign=17 mode=exploration day=3 phase=Morning
[10:23:11] directive_emit: campaign=17 ... time=0
[11:02:48] time_advance: campaign=17 source=rest_long before=3,Morning after=4,Morning days_delta=1 phase_delta=0 detail='Avrae !lr'
[11:02:49] state_footer: campaign=17 mode=exploration day=4 phase=Morning
[11:02:49] directive_emit: campaign=17 ... time=1
```

Post-session: `grep "time_advance:" dnd.log | wc -l` → advancement count. `grep "time_advance:.*err=" dnd.log` → soft-fail audit.

---

*Spec drafted: 2026-05-08, Session 1 of three. Patched to v1.1 same-day after pre-Session-2 feedback: merged former §11.E (prompt surface) + §11.F (display) into a single §11.E covering surface + timing + just_advanced mechanic; trimmed §11.B (d/e) to one-line rejections; added §11.I (`advance_time()` signature shape). Locked to v1.2: 2026-05-08 (§11.A–§11.I all locked; push-backs accepted at §11.B=(c) and §11.G=(b); surfaced additions §J.1–§J.7 patched into spec body — phase_delta normalization formula in §5, set_phase precedence invariant in §11.I, skeleton-seed §17 exception in §11.D and §6, dnd_time_advancements cascade requirement in §4, no-op telemetry contract in §8, §12 cross-ref fix; post-lock §11.I call-site count tightened from "all six" to "four"; `/rest` filed §12 with v1.x trigger condition). Diagnostic-grep informed §3. Corpus findings (track5_findings_time_mention.md) informed §11.A (granularity), §11.E (surface and display), and §6 (directive shape). §11 contains nine locked architecture decisions; §12 files eight sibling motion-system threads (including `/rest`) without sequencing them. Session 3 (implementation) may begin. Test extensions per §K (set_phase, cascade, large-phase_delta, skeleton-seed) roll into Session 3 scope.*
