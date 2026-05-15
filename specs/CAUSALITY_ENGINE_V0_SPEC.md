# CAUSALITY_ENGINE_V0_SPEC.md

**Status:** DRAFT — Phase 1 spec drafting (May 14, 2026). Session 2 = review pass (Opus medium per cadence). Session 3 = implementation.
**Session:** S69 Path A Phase 1 spec drafting against `planner-scratch/causality_engine_v0_sketch.md` + external review refinements.
**Ship:** Causality Engine v0 — final mandate-piece-adjacent ship. Converts the motion-system foundation (Scene Lifecycle / Quest Layer / Composition Layer / N-10 Canon Bootstrap / S68 N-4 commitment rails) into a living campaign engine by adding world-side motion.
**Addresses:** The world-side-motion gap. Pre-S69 the world is static between play sessions — no offscreen pressures advance, no causal threads tick deterministically. N-10 produced authored canon volume; S68 N-4 locked NPC pronouns. S69 ships the engine that **makes inaction observable**.
**Precedent specs:** `QUEST_LAYER_V0_SPEC.md` LOCKED + v0.1 patch (§1b third instance), `COMPOSITION_LAYER_V0_SPEC.md` LOCKED + v0.x patch (§1b fourth instance — narrow predicate vocabulary precedent), `CANON_BOOTSTRAP_BOT_V0_SPEC.md` LOCKED + v0.1 patch (§11.8 faction storage in skeleton.md only; S69 ships migration), `SCENE_LIFECYCLE_V1_SPEC.md` LOCKED + v1.x patch (§11.D hard-tier compression as tick trigger source; §59 sibling shape).

---

## §1. Proposed decisions

These are Code's recommendations for decisions the spec makes. NOT locks. Each goes to operator + planner review in Session 2 before implementation opens.

---

### §1.A — Ship `dnd_factions` table + minimum-plus-FKs schema

**Recommendation: ship `dnd_factions` table AND `dnd_quests.associated_faction_id` AND `dnd_npcs.affiliated_faction_id` columns as a single coherent schema delta at v0.**

R2 + R4 evidence: zero faction-adjacent state exists today. Quest Layer v0 §12.2 explicitly deferred faction modeling to v1.x — S69 is that v1.x. R4 surfaced that 3 of 4 proposed engagement-signal sources (quest-faction association, NPC-faction membership, scene-faction tagging) have no structured surface. Without `associated_faction_id` on `dnd_quests` and `affiliated_faction_id` on `dnd_npcs`, the engagement-signal predicate vocabulary (§11.4) has no FK targets — predicates can only fire on operator commands, which defeats the "inaction becomes observable" load-bearing product delta.

**Schema delta:**
```sql
CREATE TABLE dnd_factions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    type TEXT DEFAULT '',
    goal TEXT DEFAULT '',
    description TEXT DEFAULT '',
    current_stage INTEGER DEFAULT 1,
    total_stages INTEGER DEFAULT 4,
    current_stage_description TEXT DEFAULT '',
    pressure_kind TEXT DEFAULT 'atmospheric',  -- 'atmospheric' | 'hard_progression'
    visibility TEXT DEFAULT 'unknown',         -- 'unknown' | 'rumored' | 'known' | 'resolved'
    pressure_summary TEXT DEFAULT '',          -- N-10 'Pressure:' line
    engagement_signals TEXT DEFAULT '',        -- N-10 'Engagement signals:' line
    last_advanced_at INTEGER DEFAULT 0,
    last_advanced_event TEXT DEFAULT '',
    tick_predicate_json TEXT DEFAULT '{}',
    skeleton_origin INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE dnd_faction_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL,
    faction_id INTEGER NOT NULL,
    from_stage INTEGER,
    to_stage INTEGER,
    from_visibility TEXT,
    to_visibility TEXT,
    source TEXT NOT NULL,        -- 'travel' | 'rest_long' | 'scene_compress' | 'advance' | 'manual_tick' | 'manual_hold' | 'manual_reset' | 'seed_skeleton'
    source_detail TEXT DEFAULT '',
    turn_counter INTEGER,
    created_at TEXT NOT NULL
);

-- Additive FKs (NULL default; preserves back-compat for existing rows)
ALTER TABLE dnd_quests ADD COLUMN associated_faction_id INTEGER;
ALTER TABLE dnd_npcs ADD COLUMN affiliated_faction_id INTEGER;
```

**Reasoning:** Same shape as Quest Layer v0 (new table + audit + additive FKs on adjacent tables). The two FK columns are the minimum that makes the engagement-signal predicate vocabulary functional; without them §11.4 collapses to "operator commands only" which defeats the product delta. Scene-faction tagging (the 4th source) defers to v1.x — locations don't have faction tagging at v0, operator can use NPC presence at location as proxy.

---

### §1.B — Atmospheric vs hard-progression: ship capability, default protect-solo

**Recommendation: ship `pressure_kind` column with both values supported; v0 defaults all skeleton-origin factions to `atmospheric`; operator opts in via `/faction set kind:hard_progression` per faction.**

Per sketch §2 + §11.2. Hard progression is irreversible direct setback — town destroyed, allied NPC killed offscreen. Capability ships but isn't reached without explicit operator action. Solo-bard play is protected by default.

Per external review framing: "v0 favors hidden causality over visible ticking meters." Hard-progression with auto-advance would feel like strategy-UI; atmospheric pressure with reversible-via-engagement ticking feels like world simulation. Both available; default is the immersive one.

**Reasoning:** Capability ships now (no v1.x re-architecture needed if hard progression becomes desired). Default is conservative (no accidental campaign-state destruction from solo player going slow). Operator opt-in makes the intent explicit and adds friction at the right gate (per-faction acknowledgment of irreversible stakes).

---

### §1.C — Tick triggers: 4 engine-recognized sources + 1 manual + 1 hook

**Recommendation: tick check fires on these events at v0:**

| Event | Source | Hook point |
|---|---|---|
| Travel compression | `advance_time(source='travel')` | hook in `advance_time` post-write |
| Long rest | `advance_time(source='rest_long')` | same hook |
| Explicit operator advance | `advance_time(source='advance')` | same hook |
| Scene compression hard-tier fire | Scene Lifecycle v1 hard-tier | new hook in compression fire site |
| Manual operator tick | `/faction tick <faction_id>` | direct write |

**NOT in v0:** short rest (too granular), per-message cadence (rejected), per-narration-turn fire (rejected — story-scale only).

Per R3 evidence: `_VALID_TIME_SOURCES = ('travel', 'rest_long', 'rest_short', 'advance')` is clean; `dnd_time_advancements` audit table records each fire with `source` + `source_detail` + `created_at`. Scene Lifecycle compression does NOT fire `advance_time` — it's an in-memory `_scene_stale_turns` counter increment. So compression as a tick source requires a separate hook in the compression-fire path (not a hook in `advance_time`).

**Reasoning:** Story-scale temporal events anchor advancement. Per-message cadence rejected per sketch §5 — would feel like MMO-timer; story-scale feels like world. Short rest excluded as too granular (party can short-rest 6 times in a day; faction tick at that cadence defeats slow-burn narrative). Operator escape hatch (`/faction tick`) covers narrative-driven advance.

---

### §1.D — Narrow predicate vocabulary (4 keys at v0)

**Recommendation: `tick_predicate_json` accepts exactly four keys at v0:**

1. `min_turns_since_last_advance` — integer cooldown (per-faction)
2. `event_source_required` — string from `_VALID_TIME_SOURCES` ∪ `{'scene_compress'}` — restricts which engine events can tick this faction
3. `engagement_signal_required` — string `'quest:<title>'` or `'npc:<canonical_name>'` — faction ticks ONLY if engagement occurred this session (active quest engagement or NPC interaction)
4. `engagement_signal_blocks` — string `'quest:<title>'` or `'npc:<canonical_name>'` — faction does NOT tick if engagement occurred this session

Per external review refinement #2: **engagement signals come only from explicit structured surfaces.** No semantic inference, no LLM-extracted "the party kind of talked about the cartel." Predicates must be mechanically inspectable. Protects determinism and §1a.

**Engagement-signal evaluation:** at tick-evaluation time, engine reads:
- Active quest set (`dnd_quests` rows with `status='in-progress'` AND `associated_faction_id == faction.id`) → quest engagement signal fires if party performed any action in a turn where one of these quests was in-progress this session
- NPC interactions this session (`dnd_npcs.last_mentioned` within this session's turn range AND `affiliated_faction_id == faction.id`) → NPC engagement signal fires if any affiliated NPC was mentioned this session

Both reads are deterministic SQL queries. No LLM call. No semantic match.

**Reasoning:** Composition Layer v0 §11.7 precedent — narrow vocabulary ships first; v1.x expansion if operator authoring friction surfaces. External review explicitly tightened the predicate vocabulary to reject LLM-extracted engagement; this lock makes that hardening structural.

---

### §1.E — Two new §59 siblings (#20 + #21) for tick + render

**Recommendation:**

- **`compute_faction_tick_predicate(scene_state, recent_events, factions) → (factions_to_tick, signals)`** — §59 sibling #20. Pure function over (scene_state, recent advance_time events, active factions). Evaluates each faction's `tick_predicate_json` against the inputs. Returns list of faction_ids to advance + signals dict.
- **`compute_pressure_directive(active_factions, scene_state) → (body, signals)`** — §59 sibling #21. Renders atmospheric pressure into narration context as `=== OFFSCREEN PRESSURES ===` block. Quiet baseline when no factions are `visibility != 'unknown'`.

Both follow established §59 contract: pure function, soft-fail at call site, always-fire telemetry on every evaluation (even no-fire), `(body, signals)` shape.

**Reasoning:** §59 sibling pattern is mature at 19 prior instances (count post-N-10). Both siblings inherit testability, soft-fail-at-call-site, per-turn-telemetry-for-free.

---

### §1.F — Auto-transition visibility on stage advance

**Recommendation: visibility transitions deterministically on stage advance per these thresholds:**

- Stage 1 → `unknown` (default)
- Stage 2 → `rumored`
- Stage 3+ → `known`
- Final stage → `resolved`

Operator override available via `/faction visibility <faction_id> <unknown|rumored|known|resolved>`.

Per sketch §7 (visibility gating as immersion architecture). Solo-player isn't aware of 3 escalating threats from session 1 — most factions start `unknown`, become `rumored` after first atmospheric tick, only reach `known` after multiple ticks or explicit player discovery.

**Reasoning:** External review explicit framing — "hidden causality feels like world simulation, visible ticking meters feel like strategy UI." Visibility gating IS the immersion architecture; auto-transition keeps the engine in charge while operator can override for narrative reasons.

---

### §1.G — Migration: `/faction seed` repeatable + bootstrap-time auto-promote

**Recommendation: skeleton.md faction blocks promote to `dnd_factions` rows via:**

1. **One-shot auto-promote at engine init** — if `dnd_factions` rows exist for a campaign already, skip (idempotent). Else parse `parse_skeleton_file(campaign_id)['factions']` and insert rows with `skeleton_origin=1`.
2. **Repeatable `/faction seed`** slash command — mirrors `/quest seed-skeleton` precedent (R6). Operator runs after editing skeleton.md mid-campaign; idempotent on `(campaign_id, name, skeleton_origin=1)`.

Per R1 + R6 evidence. R1 confirmed N-10 wrote `name + type + description + Goal: + Pressure: + Engagement signals:` labeled prose. R6 confirmed `/quest seed-skeleton` precedent shape works for factions.

**Reasoning:** Auto-promote at engine init means S69 ship is operator-transparent for existing campaigns; `/faction seed` covers mid-campaign edits. Same pattern Quest Layer used.

---

### §1.H — Stage-prose authoring: default-then-edit at v0

**Recommendation: at migration time, factions get default placeholder stages:**

- `total_stages = 4` (atmospheric default)
- `current_stage = 1`
- `current_stage_description = goal` (the N-10-authored Goal: line, copied)

Operator edits stages via `/faction set stage_description:"<text>" <faction_id> <stage>` slash command (operator-authored prose per stage post-migration).

Per R1 evidence: **N-10 v0/v0.1 did NOT author per-stage prose.** Migration can't pull stages from skeleton.md because they weren't authored. Three options considered:

| Option | Pros | Cons |
|---|---|---|
| (a) Default placeholder stages at migration; operator edits later | Ships cleanly; operator authority over staged narration | Default stages feel flat until operator edits |
| (b) LLM-extracted stages from goal text | Auto-populated stages | §1a violation — LLM decides faction mechanical progression |
| (c) N-10 v0.2 augmentation: bootstrap card asks for per-stage prose | Best authoring UX | Couples S69 to N-10 v0.2 — schedule delay |

**Recommendation: (a) default-then-edit.** §1a clean. Operator authority preserved. Future N-10 v0.2 can author stages at bootstrap time — but S69 ships without that dependency.

**Reasoning:** Ships now, doesn't gate on N-10 v0.2. Default stages feel flat ONLY if operator never edits — and the v0 ship surfaces per-stage editing as a first-class operator command. Filed as §11.6 candidate for operator review.

---

### §1.I — Pressure directive placement: tactical band, below consequences

**Recommendation: render `compute_pressure_directive` block in tactical band of `build_dm_context`, AFTER consequences, BEFORE Scene Lifecycle.**

Per sketch §6 + Composition Layer v0 §11.4 precedent. Tactical band carries immediate-stakes directives. Offscreen pressures are atmospheric texture in the same tier as consequence pressure (the world is reacting / the world has reacted).

**Reasoning:** Pressure is per-turn-relevant when active factions surface. Placing it BELOW consequences keeps direct-NPC-interactions higher priority than ambient world-state. Above Scene Lifecycle keeps it visible before scene-end pressure.

---

### §1.J — §1b: NOT a suggester pattern at v0

**Recommendation: faction ticks are engine-deterministic. NO `#dm-aside` suggester card for ticks. Operator `/faction hold <faction_id>` is the escape hatch.**

Per sketch §11.10. §1b suggester pattern (sixth instance via N-10) is mature, but faction ticks happen at engine-recognized temporal boundaries (rests, travel, compression) which are ALREADY operator-driven. Adding a second approval gate per tick is friction.

**Reasoning:** §1a clean (engine writes via predicate evaluation; operator can hold/reset via slashes). The "every state mutation requires operator approval" temptation would defeat the v0 product delta — operator can't approve dozens of small atmospheric ticks per session.

---

### §1.K — Slash command surface

**Recommendation: ship these slashes at v0:**

- `/faction list` — operator-readable summary of active factions
- `/faction seed` — repeatable skeleton.md → DB promotion (mirror `/quest seed-skeleton`)
- `/faction tick <faction_id>` — manual operator tick (escape hatch)
- `/faction hold <faction_id>` — pause ticking on this faction (narrative reasons)
- `/faction reset <faction_id> <stage>` — operator override; requires confirmation gate for `pressure_kind='hard_progression'`
- `/faction set <faction_id> <field>:<value>` — per-field operator edit (stage_description, pressure_kind, visibility, total_stages)
- `/faction visibility <faction_id> <unknown|rumored|known|resolved>` — operator-driven visibility override

Total: 7 slashes (one group, six subcommands plus list).

**Reasoning:** Mirrors Quest Layer's slash surface count (10 commands after S65.1). Operator authority over hard-progression factions is gated via confirmation per §11.7 precedent.

---

### §1.L — Forward-coupling discipline

**Recommendation: S69 v0 does NOT pre-couple to v1.x candidates.**

NOT shipping at v0:
- Relationship matrices (faction-to-faction reactions)
- Resource simulation (gold, troops, supplies)
- NPC member rosters (faction.member_npc_ids)
- Hierarchical planning (faction goals nested under campaign arcs)
- Adaptive challenge orchestration
- PC-tracking (factions don't hunt or target players directly)
- Multi-faction interactions
- Emergent faction detection from narration

Per sketch §11 — all filed v1.x or out-of-scope.

**Reasoning:** Composition Layer v0 §11.11 silent-forward-compatibility precedent. Schema doesn't pre-commit. Observed friction post-S69 drives what ships next.

---

## §2. Problem statement

The Virgil project's motion-system stack delivers player-side and authored-canon motion: Scene Lifecycle v1 detects scene stagnation, Quest Layer v0 surfaces structured commitments, Composition Layer v0 anchors narrative phase, N-10 Canon Bootstrap Bot v0 produces authored canon volume, S68 N-4 locks NPC pronouns. **What's missing is world-side motion — the architectural ship that makes inaction observable in the game world.**

Pre-S69 the world is static between play sessions. No offscreen pressures advance, no causal threads tick deterministically. If the party ignores the bandit raids for three sessions, nothing in the engine knows. If they spend two sessions in town while the rebel uprising should be cresting, the engine doesn't reflect that. Narration can hand-wave consequences ("you hear the raiders struck another caravan"), but those references aren't anchored in persistent state — they're ad-hoc fabrications that don't reliably influence subsequent narration.

**The load-bearing product delta: inaction becomes observable.** When a faction has a `current_stage_description` and the engine ticks that stage based on engine-recognized story-scale temporal events (travel compressions, long rests, scene compressions, operator advances), the world's pressures advance deterministically. Narration surfaces those advancements as atmospheric texture. The party feels the world moving even when they're not directly engaging with it.

**Visibility gating preserves mystery as architectural goal.** Per external review framing: hidden causality feels like world simulation; visible ticking meters feel like strategy UI. v0 defaults factions to `unknown` visibility — players don't see internal stage counters or progression bars. They see narration: "Word reaches the harbor watch that the cartel has new recruits." The engine knows it's stage 2 of 4; the player just experiences the world's pressure. This is the immersion architecture, not just UX polish.

**What v0 IS NOT:**
- A relationship matrix or social-graph engine.
- A resource simulation (gold, supplies, troop counts).
- Hierarchical planning trees (NPC goals nested under faction goals nested under campaign arcs).
- Per-turn faction reasoning ("what would the cartel do this turn?" — semantic inference).
- Adaptive challenge orchestration.
- An autonomous PC-tracker (factions don't directly track or hunt players in v0).
- Per-message tick cadence.

**What v0 IS:**
- Persistent faction state with deterministic mutation (engine writes via predicate evaluation; LLM never writes faction state).
- Advancement conditions tied to story-scale temporal events (travel, rest, scene compression).
- Visible consequences surfaced into narration via `compute_pressure_directive` §59 sibling.
- Tick mechanics driven by engine-recognized temporal progression, not per-message cadence.

---

## §3. Atmospheric vs hard-progression split

Per sketch §2 — load-bearing architectural distinction.

### §3.1 Atmospheric pressure (v0 default — heavy bias)

World movement visible through:
- Rumors evolving ("word reaches the inn that the cartel has new recruits")
- Tension levels rising ("the harbor watch is doubled tonight")
- NPC mood shifts ("Eldrin seems distracted — the situation is weighing on him")
- Scarcity signals ("the price of grain has risen again")
- Caravan / arrival disruptions ("the eastern shipment didn't arrive")
- Political climate ("the council is debating the festival's safety")

**Properties:**
- Reversible or rebalanceable — narrative can pull back atmospheric pressure if party engages (operator `/faction reset <stage>` available; engine never auto-reverses)
- Soft urgency — creates story texture without forcing player resource decisions
- Compatible with solo-bard play — generates social/political/intrigue substrate
- Default tick semantics: atmospheric pressures evaluate predicate on every engine-recognized tick event

### §3.2 Hard-progression pressure (v0 minimal — light touch)

Irreversible direct setbacks:
- Towns destroyed
- Quests failed
- Factions winning permanently
- Allied NPCs killed offscreen

**Properties:**
- Irreversible — once advanced, no narrative rebalancing (operator can `/faction reset` with confirmation gate, but engine never auto-reverses)
- High stakes — creates real campaign consequences
- Risk in solo play — accumulates as permanent strategic failure pressure
- Elevated tick threshold — per §1.B lock, hard-progression factions require explicit operator opt-in; no skeleton-origin faction is `pressure_kind='hard_progression'` by default

### §3.3 v0 architectural rule

Hard progression *capability* ships at v0; defaults protect solo play. Operator opts in per faction via `/faction set kind:hard_progression <faction_id>`. The opt-in surface is the explicit acknowledgment of irreversible stakes.

Operator `/faction reset` on a `hard_progression` faction requires confirmation per §1.K + §11.7 — two-gate destruction discipline (§19 doctrine).

---

## §4. `dnd_factions` schema

Per §1.A — minimum-plus-FKs.

### §4.1 Primary table

```sql
CREATE TABLE dnd_factions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    type TEXT DEFAULT '',                     -- N-10 H3 parenthetical ('guild', 'cartel', etc.)
    goal TEXT DEFAULT '',                     -- N-10 'Goal:' line
    description TEXT DEFAULT '',              -- N-10 first prose line(s)
    current_stage INTEGER DEFAULT 1,
    total_stages INTEGER DEFAULT 4,           -- atmospheric default; hard-progression operator-set 5-6
    current_stage_description TEXT DEFAULT '', -- prose surface narration reads
    pressure_kind TEXT DEFAULT 'atmospheric', -- 'atmospheric' | 'hard_progression'
    visibility TEXT DEFAULT 'unknown',        -- 'unknown' | 'rumored' | 'known' | 'resolved'
    pressure_summary TEXT DEFAULT '',         -- N-10 'Pressure:' line (informational, not predicate input)
    engagement_signals TEXT DEFAULT '',       -- N-10 'Engagement signals:' line (informational, not predicate input)
    last_advanced_at INTEGER DEFAULT 0,       -- turn counter of last tick
    last_advanced_event TEXT DEFAULT '',      -- e.g., 'travel' / 'rest_long' / 'scene_compress' / 'manual_tick'
    tick_predicate_json TEXT DEFAULT '{}',    -- structured predicate config (§4.3)
    skeleton_origin INTEGER DEFAULT 0,        -- 1 if from skeleton.md migration, 0 if `/faction add`
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX idx_factions_campaign ON dnd_factions(campaign_id);
CREATE INDEX idx_factions_campaign_visibility ON dnd_factions(campaign_id, visibility);
```

### §4.2 Audit table

```sql
CREATE TABLE dnd_faction_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL,
    faction_id INTEGER NOT NULL,
    from_stage INTEGER,
    to_stage INTEGER,
    from_visibility TEXT,
    to_visibility TEXT,
    source TEXT NOT NULL,
    source_detail TEXT DEFAULT '',
    turn_counter INTEGER,
    created_at TEXT NOT NULL
);

CREATE INDEX idx_faction_audit_faction ON dnd_faction_audit(faction_id);
CREATE INDEX idx_faction_audit_campaign_source ON dnd_faction_audit(campaign_id, source);
```

Mirrors `dnd_quests_audit` + `dnd_time_advancements` precedent.

### §4.3 `tick_predicate_json` shape

Per §1.D — narrow vocabulary, four keys:

```json
{
  "min_turns_since_last_advance": 12,
  "event_source_required": "rest_long",
  "engagement_signal_required": "quest:Investigate Mine Collapse",
  "engagement_signal_blocks": "npc:Grahn"
}
```

All keys optional. Empty `{}` = always-eligible (every recognized tick event advances the faction).

### §4.4 Adjacent additive FKs

```sql
ALTER TABLE dnd_quests ADD COLUMN associated_faction_id INTEGER;  -- NULL default
ALTER TABLE dnd_npcs ADD COLUMN affiliated_faction_id INTEGER;    -- NULL default
```

Both NULL default — preserves back-compat. No FK enforcement at schema (per SQLite per-connection PRAGMA; project pattern of soft FKs via §16 helpers).

### §4.5 §17 single writers

- `faction_upsert(campaign_id, name, ...) → tuple[int, bool] | None` — mirrors `npc_upsert` shape; idempotent on `(campaign_id, canonicalize_faction_name(name))`.
- `faction_advance(campaign_id, faction_id, source, source_detail, turn_counter) → bool` — sole writer for `current_stage` + `last_advanced_at` + `last_advanced_event`. Appends audit row.
- `faction_set_visibility(campaign_id, faction_id, visibility, source) → bool` — sole writer for `visibility`. Appends audit row.
- `faction_set_field(campaign_id, faction_id, field, value) → bool` — operator `/faction set` writes (stage_description, pressure_kind, total_stages).

---

## §5. Tick mechanics

Per §1.C — story-scale temporal events only.

### §5.1 Tick event sources

| Source | Hook | Fires on |
|---|---|---|
| `travel` | `advance_time(source='travel')` post-write | every `/travel` invocation |
| `rest_long` | `advance_time(source='rest_long')` post-write | Avrae `!lr` event handler |
| `advance` | `advance_time(source='advance')` post-write | operator `/advance` |
| `scene_compress` | Scene Lifecycle v1 hard-tier fire | new hook in compression-fire path |
| `manual_tick` | `/faction tick <faction_id>` | operator direct write |

NOT in v0:
- `rest_short` (too granular — party can short-rest 6 times in a day)
- Per-message cadence
- Per-narration-turn fire
- Player-text-extracted engagement signals (per §1.D rejection)

### §5.2 Tick evaluation flow

On each tick event firing:

```
1. Engine fires advance_time OR compression hard-tier.
2. Hook calls compute_faction_tick_predicate(scene_state, recent_event, active_factions).
3. For each active faction (visibility != 'resolved'):
   - Evaluate tick_predicate_json against:
     - last_advanced_at + min_turns_since_last_advance (cooldown)
     - event_source_required (does event source match?)
     - engagement_signal_required (did engagement happen this session?)
     - engagement_signal_blocks (did blocking engagement happen this session?)
   - If predicate matches AND faction not at final stage:
     - faction_advance() writes new stage + audit row
     - If stage advance crosses visibility threshold (§1.F), faction_set_visibility() fires
4. Engine logs faction_tick_predicate: campaign=N evaluated=N advanced=N
5. Engine logs faction_advanced: campaign=N faction_id=N from_stage=N to_stage=N source=X per advancement
```

### §5.3 Engagement-signal evaluation

Per §1.D — structured surfaces only. Engine reads:

- **Quest engagement:** `SELECT 1 FROM dnd_quests WHERE campaign_id=? AND associated_faction_id=? AND status='in-progress'`. If any row matches the faction's id AND the player has interacted in this session (heuristic: turn counter advanced since session start), engagement signal fires.
- **NPC engagement:** `SELECT 1 FROM dnd_npcs WHERE campaign_id=? AND affiliated_faction_id=? AND last_mentioned >= <session_start_ts>`. If any row matches, engagement signal fires.

Both reads are deterministic SQL queries. No LLM call. No semantic match.

`engagement_signal_required` parses as `quest:<title>` or `npc:<canonical_name>` — engine resolves to faction-id via lookup.

`engagement_signal_blocks` parses identically; the faction does NOT tick if the lookup fires.

### §5.4 Cadence philosophy

Story-scale, not MMO-timer-scale. Tick density per session should average 1-3 advancements across all factions (not per-faction). Per-message cadence rejected. Each tick event evaluates all active factions; most evaluations result in no-advance (predicate not matched OR within cooldown).

### §5.5 Solo-bard calibration

Per sketch §7 + §1.B. v0 defaults that protect solo play:

1. **Atmospheric-heavy bias.** Default `pressure_kind = 'atmospheric'`. Hard-progression requires explicit operator opt-in.
2. **Engagement-signal-blocks cooldown.** Factions don't tick when party engaged with related quest/NPC in this session.
3. **Stage density tuned for solo cadence.** Atmospheric default `total_stages = 4`; hard-progression operator-set to 5-6 (longer arc).
4. **Visibility gating.** Most factions start `unknown`; transition to `rumored` on stage 2; `known` on stage 3+.
5. **Pressure directive cap.** Max 2-3 factions rendered per turn (per §6 below). Even if 5 factions are active, narration surfaces the most-tactically-relevant subset.

---

## §6. Pressure directive shape (§59 sibling #21)

Per §1.E + sketch §6.

### §6.1 Function signature

```python
def compute_pressure_directive(
    active_factions: list[dict],
    scene_state: dict,
) -> tuple[str, dict]:
    """§59 sibling #21. Pure function over active factions and scene state.
    Returns (directive_body, signals). Always-fire telemetry.
    """
```

### §6.2 Body shape when firing

```
=== OFFSCREEN PRESSURES ===
The Iron Vein Cartel (rumored): Word has reached the harbor watch that new ore shipments may not arrive this week.
The Festival of Dawn approaches (known): Preparations intensify; the herald has been seen consulting with the council.
```

**Render rules:**
- Cap at 2-3 factions per turn (priority: hard_progression > known > rumored; recency tiebreaker on `last_advanced_at`).
- Only `visibility != 'unknown'` AND `visibility != 'resolved'` factions render.
- Stage description is `current_stage_description` from DB (verbatim render).
- Block placed in tactical band, AFTER consequences, BEFORE Scene Lifecycle (per §1.I).

### §6.3 Quiet baseline

When no factions are `visibility != 'unknown'` OR all are `visibility = 'resolved'`, returns `('', {'fired': 0, ...})`. Same 86%-quiet baseline discipline as Scene Lifecycle v1 §5.

### §6.4 Signals dict

```python
signals = {
    'fired': int,                  # 0 or 1
    'rendered_count': int,         # how many factions in the block
    'eligible_count': int,         # factions that passed visibility filter
    'cap_dropped_count': int,      # eligible - rendered (cap saturation)
    'chars': int,
    'pressure_kinds': list[str],   # ['atmospheric', 'hard_progression'] per rendered faction
}
```

Per-turn telemetry: `pressure_directive_fired: campaign=N fired=0|1 rendered=N eligible=N cap_dropped=N chars=N`.

### §6.5 LLM job vs engine job

**LLM:** weave atmospheric pressures into narration where natural. Forbidden:
- Inventing new faction details not in `current_stage_description`
- Declaring faction advancement ("the cartel has now seized control" without engine-side tick)
- Referencing factions not in the block

**Engine:** maintain faction state, advance via predicate, render visible factions. LLM never writes state, only reads.

---

## §7. Solo-bard calibration

Per §5.5 + sketch §7. Detail per axis:

### §7.1 Atmospheric-heavy bias
- Default `pressure_kind='atmospheric'` at migration time and `/faction add` operator path.
- Hard-progression opt-in: `/faction set kind:hard_progression <faction_id>` per faction.

### §7.2 Engagement-signal-blocks cooldown
- Default `tick_predicate_json` at migration includes `"engagement_signal_blocks": "quest:<auto-detected related quest>"` IF a quest with matching `associated_faction_id` exists.
- Operator can override the predicate JSON via `/faction set tick_predicate_json:"<json>"`.

### §7.3 Stage density
- Atmospheric default: `total_stages = 4`.
- Hard-progression operator-set: 5-6 (longer arc).
- Operator can override via `/faction set total_stages:<n> <faction_id>`.

### §7.4 Visibility gating
- Stage 1 → `unknown` (default at migration)
- Stage 2 → `rumored`
- Stage 3+ → `known`
- Final stage → `resolved`
- Operator override: `/faction visibility <faction_id> <state>`.

### §7.5 Pressure directive cap
- Per-turn render cap = 3 factions max.
- Priority order: `hard_progression` > `known` > `rumored`; ties broken by most-recent `last_advanced_at`.

---

## §8. Forward-coupling

### §8.1 N-10 Canon Bootstrap Bot
- Per §11.8 lock: factions live in skeleton.md only at N-10 v0/v0.1. S69 ships the one-shot migration AND the repeatable `/faction seed` slash.
- Migration extracts `name + type + description + Goal: + Pressure: + Engagement signals:` per R1 evidence.
- Bootstrap-authored factions get `skeleton_origin=1`.
- **Forward note for N-10 v0.2:** consider authoring per-stage descriptions at bootstrap time. Currently operator edits via `/faction set stage_description` post-migration.

### §8.2 S68 N-4 pronoun lock
- Independent surfaces. NPC pronouns persist regardless of faction membership. `dnd_npcs.affiliated_faction_id` is additive; doesn't override pronouns.

### §8.3 Quest Layer v0 / v0.1
- `dnd_quests.associated_faction_id` ships at S69 (additive NULL default).
- `/faction tick` predicate can fire on quest engagement (status='in-progress' + matching faction id).
- N-10 v0 bootstrap currently writes `associated_faction_name` as freetext in quest's structured fields; migration at S69 ship resolves the freetext name → faction_id FK.

### §8.4 Composition Layer v0
- Quest acts and faction stages are independent state machines. They may correlate (party is in Act 2 of a quest while the antagonist faction is at Stage 3), but no schema coupling at v0.

### §8.5 Scene Lifecycle v1
- Hard-tier compression IS a tick trigger source per §1.C. Implementation hook added in the compression-fire path.
- Atmospheric pressure ticks don't interfere with scene-stale counter; independent state.

### §8.6 N-3.1 (filed forward, S68 N-3 HALTED)
- Once `dnd_npc_commitments` ships at N-3.1, faction-NPC commitments could feed both ledgers. v1.x coupling.

---

## §9. Recon findings

Six items, evidence-backed against the live codebase (May 14, 2026).

---

### R1. N-10 faction prose format

**Evidence (live skeleton.md inspection):**

Campaign 111 (N-10 v0.1 bootstrap test, "Bootstrap Test"):
```markdown
## Factions
### Miner's Union (guild)
A coalition of miners and their families seeking to reclaim their livelihood
Goal: Reopen the mine to restore town prosperity
Pressure: Economic desperation
Engagement signals: Petitions, protests, and sabotage of rival operations
```

Campaign 17 (hand-authored, "Stoneforge Guild"):
```markdown
## Factions
### Stoneforge Guild (adventuring guild)
The guild that posts quests on the notice board. Donovan Ruby and the
companions are members. Based in the Stoneforge Guild Hall.
```

**Format synthesis (canonical bot output shape):**
- H3 heading: `### {name} ({type})`
- Body line 1: free-prose description
- Body line 2 (optional): `Goal: {goal sentence}`
- Body line 3 (optional): `Pressure: {pressure_summary}`
- Body line 4 (optional): `Engagement signals: {engagement_signals_text}`

**What's there:** name, type, description, goal, pressure, engagement signals.

**What's NOT there:** per-stage descriptions, total_stages, tick_predicate_json, visibility. **N-10 wrote no per-stage prose.**

**Hand-authored campaigns** (campaign 17) have looser format — description only, no labeled lines. Migration parser must handle both shapes (labeled-when-present, fall-back-to-description-only).

**Migration shape:** parse `parse_skeleton_file(campaign_id)['factions']` list (skeleton_loader already produces this). For each:
- `name` ← H3 heading name (parsed)
- `type` ← H3 parenthetical (parsed)
- `description` ← prose body
- `goal`, `pressure_summary`, `engagement_signals` ← extract via labeled-line regex if present, else empty
- `current_stage_description` ← copy from `goal` (default placeholder per §1.H)
- `total_stages` ← 4 (atmospheric default per §1.B + §1.H)
- `pressure_kind` ← `'atmospheric'` (default per §1.B)
- `visibility` ← `'unknown'` (default per §1.F)
- `current_stage` ← 1
- `tick_predicate_json` ← `'{}'` (empty predicate; engine ticks on any event)
- `skeleton_origin` ← 1

**Finding:** N-10 wrote enough to migrate base fields cleanly. Per-stage prose authoring is the gap; surfaced as §1.H + §11.6 candidate. **No HALT** — N-10 DID author faction prose; the per-stage gap is a §11 decision.

---

### R2. `dnd_factions`-adjacent column audit

**Evidence (live DB inspection, May 14, 2026):**

```sql
sqlite> .tables
... no 'dnd_factions' table exists ...
... no 'dnd_faction_audit' table exists ...

sqlite> PRAGMA table_info(dnd_quests);
... no 'associated_faction_id' column ...
... no 'faction_id' column ...

sqlite> PRAGMA table_info(dnd_npcs);
... no 'affiliated_faction_id' column ...
... no 'faction_id' column ...

sqlite> PRAGMA table_info(dnd_campaigns);
... no faction-adjacent columns ...

sqlite> PRAGMA table_info(dnd_scene_state);
... no faction-adjacent columns ...

sqlite> PRAGMA table_info(dnd_locations);
... no faction-adjacent columns ...

sqlite> SELECT DISTINCT given_by FROM dnd_quests WHERE given_by != '';
Grahn       -- NPC name freetext; not faction reference
```

**Finding:** **No faction-adjacent state exists.** Quest Layer v0 §12.2 explicitly deferred faction modeling to v1.x — S69 IS that v1.x. `dnd_quests.given_by` is freetext NPC name (not faction); no semantic collision with new schema.

**Implication:** S69 is THE faction schema introducer. Per §1.A, S69 v0 ships both `dnd_factions` AND `dnd_faction_audit` AND additive FKs (`associated_faction_id` on `dnd_quests`, `affiliated_faction_id` on `dnd_npcs`) in a single coherent schema delta.

**No HALT.** Recon confirmed the gap; gap is exactly what S69 fills.

---

### R3. `advance_time` source enum + call site verification

**Evidence:**

```python
# dnd_engine.py:1966
_VALID_TIME_SOURCES = ('travel', 'rest_long', 'rest_short', 'advance')
```

Call sites (5 production):
| Site | Source | Notes |
|---|---|---|
| `discord_dnd_bot.py:2362` (`_handle_rest_event` long rest) | `'rest_long'` | Avrae `!lr` event |
| `discord_dnd_bot.py:2367` (`_handle_rest_event` short rest) | `'rest_short'` | Avrae `!sr` event |
| `discord_dnd_bot.py:5287` (`/travel`) | `'travel'` | S66 Fix 1 |
| `discord_dnd_bot.py:5431` (`/advance`) | `'advance'` | Operator |
| `dnd_engine.py:1687` (`init_end_buffer_reset_post_init`) | N/A — retired in S67 Fix 2 Phase B | Not in `_VALID_TIME_SOURCES` |

**`dnd_time_advancements` audit table:**
```sql
sqlite> PRAGMA table_info(dnd_time_advancements);
0|id|INTEGER
1|campaign_id|INTEGER
2|before_day|INTEGER
3|before_phase|TEXT
4|after_day|INTEGER
5|after_phase|TEXT
6|days_delta|INTEGER
7|phase_delta|INTEGER
8|resolved_phase_delta|INTEGER
9|set_phase|TEXT
10|source|TEXT       -- ← clean enum match
11|source_detail|TEXT
12|created_at|TEXT
```

Recent rows show clean source values: `'travel'` (Seq:A→B, Seq:B→C), `'travel'` (Test:1day, Test:empty, Test:banana). Source is per-row distinguishable.

**Finding:** Source enum is clean. `advance_time` is the §17 single writer. Tick predicate's `event_source_required` can match against `dnd_time_advancements.source` for the most-recent row OR a hook can be added inside `advance_time` post-write to fire faction tick check synchronously.

**Scene Lifecycle compression caveat:** compression hard-tier fire does NOT call `advance_time` — it increments an in-memory `_scene_stale_turns` counter. To make compression a tick source per §1.C, S69 must add a new hook in Scene Lifecycle's compression-fire path that fires `compute_faction_tick_predicate` with `event_source='scene_compress'`.

**No HALT.** Recon confirmed; hook-shape decision lands cleanly.

---

### R4. Engagement signal structured surface enumeration

**Evidence:**

| Source | Structured today? | Notes |
|---|---|---|
| (a) Quest-faction association | **No — schema gap** | `dnd_quests` has no `associated_faction_id` |
| (b) NPC-faction membership | **No — schema gap** | `dnd_npcs` has no `affiliated_faction_id` |
| (c) Scene-faction tagging | **No — schema gap** | `dnd_scene_state` / `dnd_locations` have no faction reference |
| (d) Operator commands (`/faction tick` etc.) | **New at v0** | Net-new in this ship |

**Finding:** 3 of 4 proposed engagement signal sources have schema gaps. Per brief refinement #2, engagement signals must come ONLY from explicit structured surfaces — semantic inference and LLM-extracted signals are rejected.

**Implication:** Without (a) and (b), `engagement_signal_required` and `engagement_signal_blocks` predicate keys can ONLY fire on operator-typed commands. That defeats the "inaction becomes observable" load-bearing product delta — players never engage with operator commands, they engage with quests and NPCs.

**Resolution:** Per §1.A, ship `associated_faction_id` on `dnd_quests` AND `affiliated_faction_id` on `dnd_npcs` as part of S69's schema delta. This makes (a) and (b) structured surfaces from S69 ship-time forward.

**Scene-faction tagging (c) defers to v1.x.** Locations don't have faction columns; adding them is scope expansion. Operator can use NPC presence at location as proxy (an NPC affiliated with a faction at the current location = faction-tagged scene).

**Not HALT-level.** The HALT criterion was "NONE of the proposed engagement signal sources have structured surfaces." Per §1.A lock, S69 ships (a) and (b) as structured surfaces — gap resolved at ship time. Filed implicitly via §1.A schema lock.

---

### R5. Pressure directive prompt-size baseline

**Evidence (live logs):**

```
prompt_size: campaign=23 system=22105 retrieval=716  directives=5603 total=22105
prompt_size: campaign=23 system=20942 retrieval=1010 directives=5603 total=20942
prompt_size: campaign=23 system=20067 retrieval=1001 directives=5603 total=20067
prompt_size: campaign=23 system=19469 retrieval=513  directives=5603 total=19469
prompt_size: campaign=23 system=20255 retrieval=1301 directives=5603 total=20255
```

Recent sample: 19-22k chars total prompt. Directives at 5603 chars baseline (Scene Lifecycle's threshold-fired directive adds ~937 chars when it fires).

**Pressure directive projected delta:**
- Per faction rendered: ~100-150 chars (name + visibility + stage description + framing line).
- Max render = 3 factions per turn (§6.5 cap).
- Block header + framing = ~80 chars.
- **Total projected: ~300-500 chars when firing.**
- Quiet baseline (no eligible factions): 0 chars.

**Net projected post-S69:** mean ~20-22k chars (current) + 300-500 chars (pressure directive when firing). **Same-tier delta as Scene Lifecycle's threshold fire.** Budget-safe — well within prompt-size headroom.

**Finding:** Pressure directive is prompt-budget-cheap. No architectural optimization needed.

---

### R6. Skeleton-faction promotion idempotency

**Evidence:**

`/quest seed-skeleton` precedent (`dnd_engine.py:3428`):
```python
def quest_seed_skeleton(campaign_id: int, hooks: list[dict]) -> dict:
    """Idempotent skeleton-quest seeder. Inserts a row per hook at
    status='offered', skeleton_origin=1. Dedup key: (campaign_id, title,
    skeleton_origin=1) — existing matches are skipped.
    ...
    EDGE CASE (Finding 3): if operator edits a skeleton.md hook title
    mid-campaign and re-seeds, the renamed hook inserts as a new row;
    the original-title row persists as an orphan with skeleton_origin=1.
    Operator cleans up via /quest delete <old_id>.
    """
```

**Finding:** Same pattern viable for `/faction seed`:
- Dedup key: `(campaign_id, canonicalize_faction_name(name), skeleton_origin=1)`
- Idempotent: re-running with no skeleton.md changes is a no-op.
- Edge case mirrors Quest Layer Finding 3: operator renames a faction in skeleton.md → renamed faction inserts as new row; original-name row persists as orphan; operator cleans up via `/faction delete <old_id>` (or `/faction reset <old_id>` + `/faction set visibility:resolved` if narrative wants the original to remain).

**Return shape:** `{inserted: N, skipped: N, factions_resolved: list[str], factions_unresolved: list[str]}`. Mirrors `quest_seed_skeleton` return.

**No HALT.** Pattern is clean.

---

## §10. §76 four-property latent-canon audit

New `dnd_factions` columns and supporting fields, each scored against the four properties per Doctrine §76:

| New surface | LLM-writable? | Persisted? | Retrieved? | Narratively inferential? | Score | Verdict |
|---|---|---|---|---|---|---|
| `dnd_factions.name` | No (skeleton.md author OR `/faction add` operator OR `faction_upsert` from skeleton-loader) | Yes | Yes (pressure directive) | No (canonical token, not prose) | 1/4 | Safe |
| `dnd_factions.type` | No (same writers) | Yes | No (informational only at v0) | No (short label) | 1/4 | Safe |
| `dnd_factions.goal` | No (skeleton.md author; not LLM-extracted at v0) | Yes | Yes (informational + may surface in `current_stage_description` default) | Yes (prose) | **3/4** | **Safe — operator-written, §17-disciplined** |
| `dnd_factions.description` | No (skeleton.md author) | Yes | No (informational; not rendered at v0) | Yes (prose) | 2/4 | Safe |
| `dnd_factions.current_stage` | No (`faction_advance` only) | Yes | No (used for stage_description lookup; not rendered directly) | No (integer) | 1/4 | Safe |
| `dnd_factions.current_stage_description` | No (operator `/faction set stage_description`; v0 default copies `goal`) | Yes | Yes (pressure directive — verbatim render) | Yes (prose) | **3/4** | **Safe — operator-written, §17-disciplined** |
| `dnd_factions.total_stages` | No (`/faction set total_stages` or migration default) | Yes | No (not rendered) | No (integer) | 1/4 | Safe |
| `dnd_factions.pressure_kind` | No (`/faction set kind` or migration default) | Yes | No (used for cap-priority; not rendered) | No (enum) | 1/4 | Safe |
| `dnd_factions.visibility` | No (`faction_set_visibility` only — engine OR `/faction visibility`) | Yes | Yes (pressure directive — filter + label) | No (enum) | 1/4 | Safe |
| `dnd_factions.pressure_summary` | No (skeleton.md author) | Yes | No (informational only at v0; predicate INPUT is mechanical, not this field) | Yes (prose) | 2/4 | Safe |
| `dnd_factions.engagement_signals` | No (skeleton.md author) | Yes | No (informational only at v0; predicate INPUT is structured FK lookup, not this field) | Yes (prose) | 2/4 | Safe |
| `dnd_factions.last_advanced_at` | No (`faction_advance` only) | Yes | No (used for cooldown predicate) | No (integer) | 1/4 | Safe |
| `dnd_factions.last_advanced_event` | No (`faction_advance` only) | Yes | No (telemetry / audit context) | No (enum) | 1/4 | Safe |
| `dnd_factions.tick_predicate_json` | No (operator `/faction set tick_predicate_json` OR migration default) | Yes | No (predicate evaluation input only) | No (JSON config) | 1/4 | Safe |
| `dnd_quests.associated_faction_id` | No (`/quest set associated_faction_id` OR migration FK resolution) | Yes | No (predicate eval input only) | No (integer FK) | 1/4 | Safe |
| `dnd_npcs.affiliated_faction_id` | No (`/npc set affiliated_faction_id` OR N-10 bootstrap-time author) | Yes | No (predicate eval input only) | No (integer FK) | 1/4 | Safe |

**Verdict: zero new 4/4 §76 surfaces.** Two surfaces (`goal`, `current_stage_description`) hit 3/4 but the LLM-writable property fails — both are operator-written via `/faction set` or skeleton.md authoring; engine never extracts them from LLM narration. Per S41 §76 footnote: where a column's only write path is a §17-disciplined helper, the column structurally cannot become a 4/4 contamination surface.

**Operational discipline:**
- Skeleton.md author authority preserved for `goal`, `description`, `pressure_summary`, `engagement_signals`.
- `current_stage_description` defaults to `goal` at migration; operator edits via `/faction set stage_description` only.
- Engine never updates prose surfaces from LLM output.
- `pressure_summary` and `engagement_signals` are INFORMATIONAL prose — not predicate input. Predicate evaluation uses structured FK lookups (per §5.3). The prose surfaces exist for human-readable `/faction list` output, not for engine logic.

---

## §11. Decision points — operator's call required

13 decisions (12 active + 1 filed for awareness per external review).

---

### §11.1 — Schema scope: minimum-plus-FKs

**Question:** Ship just `dnd_factions` + `dnd_faction_audit`, or also additive FKs on `dnd_quests` + `dnd_npcs`?

**Candidates:**
- **(a) Minimum-plus-FKs** — `dnd_factions` + `dnd_faction_audit` + `dnd_quests.associated_faction_id` + `dnd_npcs.affiliated_faction_id`
- (b) Faction tables only — defer FKs to v1.x
- (c) Extended schema — include relationship matrix, NPC member roster, faction-to-faction reactions

**Recommendation: (a) minimum-plus-FKs** per §1.A.

**Confidence: HIGH.** R4 makes (b) untenable — predicate vocabulary collapses to operator commands only without FKs, defeating the product delta. (c) is v2+ temptation per sketch §11.1.

---

### §11.2 — Hard-progression at v0: capability ships, opt-in default

**Question:** Ship hard-progression capability at v0 or defer to v1.x?

**Candidates:**
- **(a) Capability ships; default protect-solo (operator opts in per faction)**
- (b) Capability ships; default mixed (let operator/skeleton.md choose)
- (c) Atmospheric only at v0; hard-progression v1.x

**Recommendation: (a)** per §1.B.

**Confidence: HIGH.** External review framing — visibility-gating-as-immersion-architecture means default-immersive (atmospheric) preserves the load-bearing product delta. Opt-in surface makes hard-progression intent explicit; no accidental solo-player campaign-state destruction.

**Walk-to-confirm:** operator may want stricter (c) — atmospheric only at v0, hard-progression filed v1.x. Confirm at Session 2 whether the opt-in friction (per-faction `/faction set kind:hard_progression`) is sufficient OR whether ANY hard-progression at v0 carries risk that operator would rather not ship.

---

### §11.3 — Tick trigger event set

**Question:** Which engine events fire faction tick evaluation?

**Candidates:**
- **(a) Five sources: travel, rest_long, advance, scene_compress, manual_tick**
- (b) Three sources: rest_long, manual_tick, scene_compress (drop travel + advance — too frequent)
- (c) Single source: manual_tick only (operator-driven entirely)

**Recommendation: (a)** per §1.C.

**Confidence: MEDIUM.** Open axis: tick density per session. v0 ships with cooldown via `min_turns_since_last_advance` predicate key — operator can tune per faction. If observed tick density is too high (operator-feedback at playtest), defer to (b) by removing travel from the auto-tick set.

---

### §11.4 — Predicate vocabulary: narrow at v0

**Question:** Which keys does `tick_predicate_json` accept?

**Candidates:**
- **(a) Narrow (4 keys): min_turns_since_last_advance, event_source_required, engagement_signal_required, engagement_signal_blocks**
- (b) Broader: + npc_interaction, consequence_kind, location_visit, combat_outcome
- (c) Open vocab: arbitrary keys parsed at evaluation time

**Recommendation: (a)** per §1.D + sketch §11.4 + Composition Layer v0 §11.7 precedent.

**Confidence: HIGH.** External review explicitly tightened vocabulary to reject LLM-extracted engagement signals. Narrow vocab + structured FK lookups (per §5.3) preserves determinism + §1a.

---

### §11.5 — Skeleton.md → DB promotion: repeatable, mirror Quest Layer

**Question:** One-shot migration at deploy or repeatable `/faction seed`?

**Candidates:**
- (a) One-shot only — migration runs once at engine init post-deploy
- **(b) Repeatable `/faction seed`** — operator runs after editing skeleton.md mid-campaign
- (c) Both — auto-promote at engine init AND repeatable slash

**Recommendation: (c) both** per §1.G.

**Confidence: HIGH.** R6 evidence confirms `/quest seed-skeleton` precedent shape works. Operator may add factions to skeleton.md mid-campaign; `/faction seed` makes the import explicit. Auto-promote at engine init keeps S69-deploy transparent for existing campaigns.

**Walk-to-confirm:** edge case from Quest Layer Finding 3 — operator renames a faction in skeleton.md → renamed faction inserts as new row; original-name row persists as orphan. Recommend documenting in `/faction seed` docstring; operator cleans up via `/faction delete <old_id>` or `/faction set visibility:resolved <old_id>`.

---

### §11.6 — Stage-prose authoring at v0

**Question:** How does `current_stage_description` get authored per stage?

**Candidates:**
- **(a) Default-then-edit** — migration copies `goal` to `current_stage_description`; operator edits via `/faction set stage_description`
- (b) LLM-extracted from goal — engine generates per-stage prose from goal text
- (c) N-10 v0.2 augmentation — bootstrap card asks for per-stage prose
- (d) Mandatory operator authoring before faction becomes visible

**Recommendation: (a)** per §1.H.

**Confidence: MEDIUM.** R1 evidence: N-10 didn't author per-stage prose. (b) violates §1a. (c) couples S69 to N-10 v0.2 timing. (d) adds friction operator may not want.

**Walk-to-confirm:** default placeholder stages feel flat ONLY if operator never edits. Whether the placeholder is acceptable at v0 depends on operator's authoring discipline. If operator wants per-stage prose authored at bootstrap time, file as N-10 v0.2 dependency and defer S69 ship until N-10 v0.2 lands. Walk surfaces the trade-off.

**Open axis:** operator's preference for ship-immediate-with-placeholder vs ship-coupled-to-N-10-v0.2.

---

### §11.7 — Operator override gates for hard-progression

**Question:** Does `/faction reset` on a hard-progression faction require confirmation?

**Candidates:**
- **(a) Confirmation required** — two-gate destruction per §19 doctrine
- (b) No confirmation — operator authority is sufficient
- (c) Confirmation required only when stage decreases (not when increases)

**Recommendation: (a)** per §1.K + §19.

**Confidence: HIGH.** Hard-progression by definition is irreversible. Operator override requires explicit confirmation to prevent accidental narrative-state mutation. Two-gate destruction is the project pattern (cf. `/quest delete`, `/purgecampaign`).

---

### §11.8 — Faction → consequence ledger integration

**Question:** Does atmospheric pressure write to `dnd_consequences` ledger on stage advance?

**Candidates:**
- **(a) Render directly via pressure directive** — no ledger write
- (b) Write consequence row on every faction advance — feeds NPC-side visibility
- (c) Hybrid — write consequence row only on visibility transition (unknown→rumored, rumored→known)

**Recommendation: (a)** per sketch §11.6.

**Confidence: MEDIUM.** Cleaner separation of surfaces at v0; consequences ledger stays focused on direct NPC interactions. (c) is an interesting v1.x candidate — making faction visibility transitions visible at the NPC level — but adds coupling complexity at v0.

**Walk-to-confirm:** operator may want (c) — visibility-transition writes a `kind='faction_state_shift'` consequence row so NPCs reference the world's changing pressure during conversations. File as v1.x candidate if (a) ships at v0.

---

### §11.9 — Visibility transition thresholds

**Question:** Stage thresholds for auto-visibility transitions?

**Candidates:**
- **(a) Default thresholds:** Stage 1=unknown, Stage 2=rumored, Stage 3+=known, Final=resolved
- (b) Configurable per faction via `tick_predicate_json.visibility_thresholds`
- (c) Manual only — engine never auto-transitions visibility

**Recommendation: (a)** per §1.F.

**Confidence: HIGH.** Simple deterministic rule. Operator override via `/faction visibility` available for narrative reasons. Configurable thresholds (b) is v1.x if observed friction surfaces.

---

### §11.10 — §1b suggester pattern: NO at v0

**Question:** Should faction ticks fire via `#dm-aside` suggester ("Iron Vein Cartel is eligible to advance — approve with /faction tick?")?

**Candidates:**
- **(a) NO at v0** — engine-deterministic ticks
- (b) YES — suggester for every tick proposal
- (c) Hybrid — suggester for hard-progression ticks only

**Recommendation: (a)** per §1.J + sketch §11.10.

**Confidence: HIGH.** Tick events are already operator-driven (rests, travel, compression). Adding a per-tick approval gate is friction. `/faction hold` is the escape hatch for "don't tick this faction right now."

**Walk-to-confirm:** if operator wants visibility into pending ticks before they fire (e.g., a `#dm-aside` notification per tick saying "Iron Vein Cartel advanced to Stage 2"), that's a different shape than a suggester — file as v1.x notification-card candidate, distinct from §1b approval pattern.

---

### §11.11 — Composition forward-compatibility: silent

**Question:** Does S69 schema pre-couple to v1.x candidates (relationships, NPC rosters, resource sim)?

**Candidates:**
- **(a) Silent — no pre-coupling at schema layer**
- (b) Stub columns for v1.x — `relationship_matrix_json`, `member_npc_ids`, etc.

**Recommendation: (a)** per §1.L + Composition Layer v0 §11.11 precedent.

**Confidence: HIGH.** Schema doesn't pre-commit. Stub columns rot. Observed friction post-S69 drives what ships next.

---

### §11.12 — Initial faction count at N-10 bootstrap

**Question:** Should N-10's faction card count change with S69 ship?

**Candidates:**
- **(a) Keep at 1-2 factions per bootstrap** — current N-10 v0/v0.1 default
- (b) Bump to 2-3 — encourage more factions per campaign
- (c) Make operator-configurable at bootstrap time

**Recommendation: (a)** per sketch §11.12.

**Confidence: MEDIUM.** Observed-friction reveals whether more factions per campaign are useful. v0 ships with current N-10 default; tuning is v0.x patch territory.

---

### §11.13 — Long-horizon faction lifecycle (FILED, not sequenced at v0)

**Question:** With pure sequential stage advancement, factions terminal-state-freeze. Long-horizon, factions accumulate as forever-resolved stale entities, or campaigns end up cluttered with frozen `resolved` factions.

**Candidates (for v1.x consideration, not v0 ship):**
- (a) Dormant state — `resolved` factions can re-enter active state on narrative trigger
- (b) Cyclical factions — pressure builds → resolves → re-builds (seasonal patterns)
- (c) Stabilized factions — `resolved` factions stay quiescent but operator can re-activate
- (d) Pressure-recycling mechanics — resolved faction's pressure feeds a successor faction
- (e) No special handling — `resolved` factions sit in DB indefinitely as historical record

**Recommendation: (e) at v0** — `resolved` factions persist in DB, never tick again, visible via `/faction list` as historical record. **Long-horizon lifecycle behavior filed for v1.x doctrinal awareness.**

Per external review framing #3: "future-facing concept space: dormant, stabilized, simmering, cyclical factions. Pressure-recycling mechanics. NOT a v0 implementation requirement; v0 ships sequential-advancement-only. Filed so spec acknowledges the long-horizon entropy problem without scope-creeping into solving it."

**Confidence: HIGH on (e) at v0.** Genuine v1.x uncertainty on which long-horizon shape (a-d) earns priority — that's an observed-friction question post-S69.

**Filed-not-sequenced.** Operator review at Session 2 confirms whether (e) at v0 is acceptable; v1.x design pass owns the actual long-horizon choice when observed friction surfaces.

---

## §12. Open questions filed forward — out of v0 scope

These surface during recon or are implied by v0 decisions but are not v0 work.

**§12.1 — LLM-extracted faction stages from goal text.**
Per §1.H rejection. v0 ships default-placeholder stages; operator edits. v1.x candidate if observed friction shows operators not editing stages and default-placeholder feels flat.

**§12.2 — N-10 v0.2 bootstrap-time per-stage authoring.**
Per §1.H option (c) rejection at v0. v1.x N-10 spec extension: bootstrap card asks operator for per-stage prose at faction-card approval time. Couples N-10 to S69's `current_stage_description` field.

**§12.3 — Scene-faction tagging.**
Per R4 (c). `dnd_locations.faction_id` or `dnd_scene_state.scene_factions` deferred to v1.x. Operator uses NPC presence at location as proxy at v0.

**§12.4 — Faction-to-faction relationships.**
Per §11.11. Relationship matrix, hostility levels, alliance graphs. v2+ temptation per sketch §11.1.

**§12.5 — NPC member rosters per faction.**
Per §1.L. `dnd_factions.member_npc_ids` array. v1.x if observed friction shows operator wanting to query "all NPCs in the Cartel."

**§12.6 — Resource simulation.**
Gold, troops, supplies as faction resources. v2+ per sketch §1.

**§12.7 — Hierarchical planning trees.**
NPC goals nested under faction goals nested under campaign arcs. v2+.

**§12.8 — Adaptive challenge orchestration.**
Faction state influences encounter generation. v2+.

**§12.9 — Multi-faction interactions.**
One faction's advancement affects another faction's pressure. v1.x if observed friction.

**§12.10 — Emergent faction detection from narration.**
Advisory parser detects "the rebel network is gaining traction" in narration → proposes new faction via §1b suggester. v1.x. Couples to N-3.1 commitment-tracking infrastructure when it ships.

**§12.11 — Faction visibility-transition consequence-ledger writes.**
Per §11.8 (c). Faction visibility transition writes a `kind='faction_state_shift'` consequence row so NPCs reference the world's changing pressure during conversations. v1.x.

**§12.12 — Faction notification cards (non-approval).**
Per §11.10 walk-to-confirm. `#dm-aside` notification on every tick (operator visibility into pending state changes), distinct from §1b approval pattern. v1.x if observed friction shows operator wanting more visibility into engine-driven advancements.

**§12.13 — Long-horizon faction lifecycle.**
Per §11.13. Dormant / cyclical / stabilized / simmering / pressure-recycling mechanics. v1.x or later doctrinal pass.

---

## §13. Out of scope — v0 explicitly does not

- Relationship matrices or social-graph engines (filed §12.4).
- Resource simulation — gold, troops, supplies as faction state (filed §12.6).
- Hierarchical planning trees (filed §12.7).
- Per-turn faction reasoning ("what would the cartel do this turn?") — semantic inference rejected per §1a.
- Adaptive challenge orchestration (filed §12.8).
- Autonomous PC-tracker — factions don't directly track or hunt players (filed §13).
- Multi-faction interactions (filed §12.9).
- Emergent faction detection from narration (filed §12.10).
- LLM-decided faction state transitions (§1a — operator and engine deterministic only).
- Per-message tick cadence (rejected — story-scale only per §1.C).
- Scene-faction tagging (filed §12.3 — v1.x).
- LLM-extracted faction stages from goal text (filed §12.1 — operator-written discipline).
- NPC-as-faction-agent autonomous behavior — NPCs don't autonomously act on faction goals at v0 (filed §13).
- ARC payoff machinery — campaign-scale thematic construction is post-Causality-Engine territory.
- Pre-commit operator approval gate on tick proposals (per §1.J + §11.10 — engine-deterministic).
- Long-horizon faction lifecycle solutions (filed §11.13 + §12.13).

---

## §14. Handoff

| Field | Value |
|---|---|
| **Spec status** | DRAFT — Phase 1 spec drafting complete (May 14, 2026). Session 2 = review pass (Opus medium per cadence). Session 3 = implementation. |
| **Spec file** | `/home/jordaneal/virgil-docs/specs/CAUSALITY_ENGINE_V0_SPEC.md` |
| **§1 decisions** | 12 proposed decisions (§1.A–§1.L). |
| **§11 count** | **13 total — 12 active for spec lock, 1 filed for awareness (§11.13 long-horizon lifecycle, per external review).** 7 HIGH confidence, 5 MEDIUM, 0 LOW. |
| **§12 count** | 13 open questions filed forward. |
| **HALT escalations** | 0. Three recon items that could have HALTed didn't: R1 (N-10 wrote faction prose — per-stage gap is §11.6 candidate, not HALT); R2 (no faction-adjacent state exists — confirmed gap, S69 ships schema); R4 (3 of 4 engagement-signal sources have schema gaps — resolved by §1.A minimum-plus-FKs lock). |
| **Recon findings** | R1: N-10 wrote `name + type + description + Goal: + Pressure: + Engagement signals:` labeled prose; NO per-stage authoring. R2: no faction-adjacent state exists; S69 is the schema introducer. R3: `_VALID_TIME_SOURCES = ('travel', 'rest_long', 'rest_short', 'advance')` clean; `dnd_time_advancements` audit table provides per-event source enum; scene compression needs separate hook. R4: 3 of 4 engagement-signal sources have schema gaps; §1.A ships FK columns to make (a) quest-faction and (b) NPC-faction structured; (c) scene-faction defers to v1.x. R5: prompt-size baseline ~20-22k chars (post-S67); pressure directive 300-500 chars when firing — budget-safe. R6: `/quest seed-skeleton` precedent shape works for `/faction seed`. |
| **Architectural recommendation** | Ship `dnd_factions` + `dnd_faction_audit` + additive FKs (`associated_faction_id` on dnd_quests, `affiliated_faction_id` on dnd_npcs) in single schema delta (§1.A). Atmospheric default, hard-progression capability ships with opt-in (§1.B). Narrow 4-key predicate vocabulary (§1.D) — engagement signals from structured surfaces only, no LLM extraction. Two new §59 siblings #20 + #21 (§1.E). Default-then-edit stage prose authoring (§1.H — per-stage prose gap is operator post-migration; N-10 v0.2 bootstrap-card extension filed as §12.2). `/faction seed` repeatable migration (§1.G + R6 precedent). §1b suggester pattern NOT applied at v0 — engine-deterministic ticks with `/faction hold` escape hatch (§1.J). |
| **Deeper-synthesis decisions for Session 2** | §11.2 (hard-progression capability at v0 — opt-in vs defer entirely); §11.5 (`/faction seed` shape + Finding-3-style edge case for rename); §11.6 (stage-prose authoring at v0 — placeholder-then-edit vs N-10 v0.2 coupling vs defer); §11.13 (long-horizon lifecycle filed-not-sequenced framing). |
| **Next session** | Session 2 = review pass. Opus medium per WWC cadence — mature §59 sibling pattern (19 prior instances + S69's 2 new = 21); recon-clean architecture; three deeper-synthesis decisions plus 9 standard walks. Session 3 = implementation, estimated ~3-4 days for engine + orchestration + 7 slash commands + 25-30 test surface. |

---
