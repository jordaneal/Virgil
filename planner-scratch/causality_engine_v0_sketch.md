# Causality Engine v0 (S69) — Architectural Sketch

**Status:** v0 sketch — pre-spec. §11 candidates surfaced not locked.
**Date:** 2026-05-14
**Authorized:** Post-S68 priority. N-10 shipped authored-canon volume; S68 shipped commitment rails (N-4 pronoun lock); S69 ships world-side pressures — the third layer needed to convert foundation into living campaign engine.

---

## 1. What this is

**Mandate (narrowed):** Persist offscreen pressures in deterministic state so narration can surface causality without inventing it ad hoc.

NOT: simulate a living world, economy simulation, autonomous NPC planning, procedural politics, scheduler systems.

**What v0 provides:**
1. Persistent faction/pressure state with deterministic mutation
2. Advancement conditions tied to story-scale temporal events
3. Visible consequences surfaced into narration via §59 directive
4. Tick mechanics driven by engine-recognized temporal progression, not per-message cadence

**What this enables for play:**
- Rumors evolve over sessions
- Threats advance whether party engages or not
- Opportunities expire deterministically
- NPCs react to elapsed time
- **Inaction becomes observable** — the load-bearing fun-delta

**Architectural placement.** Final mandate-piece-adjacent ship. Sits downstream of Quest Layer (party-side commitments), Composition Layer (where-are-we anchoring), N-10 Canon Bootstrap Bot (authored factions in skeleton.md). Reads from N-10's faction prose, promotes to runtime-mutable state, ticks against story-scale temporal events from existing infrastructure (`advance_time`, Scene Lifecycle compression, Avrae rest events).

**What v0 is NOT:**
- A relationship matrix or social-graph engine
- A resource simulation (gold, supplies, troop counts)
- Hierarchical planning trees (NPC goals nested under faction goals nested under campaign arc)
- Per-turn faction reasoning ("what would the cartel do this turn?")
- Adaptive challenge orchestration
- An autonomous PC-tracker (factions don't directly track or hunt players in v0)

---

## 2. Atmospheric vs hard-progression pressure split

**Load-bearing v0 architectural distinction** (per GPT review framing).

### Atmospheric pressure (v0 default — heavy bias)

World movement visible through:
- Rumors evolving ("word reaches the inn that the cartel has new recruits")
- Tension levels rising ("the harbor watch is doubled tonight")
- NPC mood shifts ("Eldrin seems distracted — the situation is weighing on him")
- Scarcity signals ("the price of grain has risen again")
- Caravan / arrival disruptions ("the eastern shipment didn't arrive")
- Political climate ("the council is debating the festival's safety")

**Properties:**
- Reversible or rebalanceable — narrative can pull back atmospheric pressure if party engages
- Soft urgency — creates story texture without forcing player resource decisions
- Compatible with solo-bard play — generates social/political/intrigue substrate
- Default tick semantics — atmospheric pressures advance on every engine-recognized tick

### Hard-progression pressure (v0 minimal — light touch)

Irreversible direct setbacks:
- Towns destroyed
- Quests failed
- Factions winning permanently
- Allied NPCs killed offscreen

**Properties:**
- Irreversible — once advanced, no narrative rebalancing
- High stakes — creates real campaign consequences
- Risk in solo play — accumulates as permanent strategic failure pressure

**v0 architectural rule:** Hard progression requires elevated tick threshold — multiple atmospheric advancements over multiple sessions before hard-progression stages unlock. v0 may ship with hard progression *capability* but disabled-by-default at v0 fire conditions, or may ship atmospheric-only with hard progression filed v1.x. §11 decision.

---

## 3. What surfaces it extends, what's new

**Reuses (no schema change):**
- skeleton.md faction prose (per N-10 §11.8 lock — bootstrap-authored factions live in skeleton.md only)
- `advance_time` from Track 4 #3 (S27-S28) — the §17-locked single writer for time progression
- Avrae rest events as tick triggers
- Scene Lifecycle compression as tick trigger
- `/travel` duration translator from S66
- Existing `dnd_consequences` ledger pattern — atmospheric pressure changes could surface as consequences for downstream NPC visibility (alternative to direct prompt rendering; §11)

**Proposed new:**
- `dnd_factions` table — runtime-mutable faction state promoted from skeleton.md
- `dnd_faction_audit` table — mirrors `dnd_quests_audit` / `dnd_time_advancements` pattern for stage transitions
- One-shot migration: skeleton.md faction blocks → `dnd_factions` rows (idempotent on faction name)
- Two §59 siblings:
  - `compute_faction_tick_predicate(scene_state, recent_events) → (factions_to_tick, signals)` — decides which factions advance on this engine event
  - `compute_pressure_directive(active_factions, scene_state) → (body, signals)` — renders atmospheric pressure into narration context
- New slash commands:
  - `/faction list` — operator-readable summary of active factions
  - `/faction tick <faction_id>` — manual operator tick (escape hatch, debug, narrative-driven advance)
  - `/faction hold <faction_id>` — operator pause on a specific faction (narrative reasons)
  - `/faction reset <faction_id> <stage>` — operator override
- Telemetry: `faction_advanced:`, `pressure_directive_fired:`, `faction_tick_predicate:`

**Not new:**
- No new ChromaDB collection (faction state is structured, not retrieval surface)
- No bot→Avrae writes
- No LLM-decided faction state transitions (§1a — operator and engine deterministic only)
- No mid-narration faction tick (advancement happens at engine-recognized boundaries, not per-message)

---

## 4. The faction state machine

**`dnd_factions` proposed schema (v0):**

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `campaign_id` | INTEGER FK | |
| `name` | TEXT | canonical faction name |
| `goal` | TEXT | one-sentence goal |
| `current_stage` | INTEGER DEFAULT 1 | which stage of advancement |
| `current_stage_description` | TEXT | prose surface narration reads (per stage) |
| `total_stages` | INTEGER | how many stages until "fully advanced" |
| `pressure_kind` | TEXT | `atmospheric` or `hard_progression` (§11.2 lock) |
| `visibility` | TEXT | `unknown` / `rumored` / `known` |
| `last_advanced_at` | INTEGER | turn counter of last advancement |
| `last_advanced_event` | TEXT | which event triggered the last tick (`travel` / `rest_long` / `scene_compress` / `manual`) |
| `tick_predicate_json` | TEXT | structured predicate config (§11.5 lock) |
| `skeleton_origin` | INTEGER | 1 if from N-10 bootstrap, 0 if `/faction add` |
| `created_at`, `updated_at` | INTEGER | |

**State machine:**

- **Stage 1 → 2 → ... → total_stages**: sequential advancement
- **Tick fires:** evaluate predicate against current scene_state and recent events; if match, advance stage by 1
- **At final stage:** faction enters `resolved` visibility status; remains in DB for narrative reference but no longer ticks
- **Operator-driven transitions:** `/faction tick`, `/faction hold`, `/faction reset` — engine-deterministic writes, audit row per transition

**Atmospheric vs hard-progression behavior:**

- Atmospheric factions: stages reverse-tickable via operator `/faction reset` if narrative needs (e.g., party engages and reduces tension); engine NEVER reverse-ticks atomically
- Hard progression factions: stages forward-only via engine + operator; reset requires explicit operator action with confirmation gate

---

## 5. Tick triggers (THE load-bearing v0 decision)

Per GPT framing: tick triggers are the single most consequential design decision.

**Story-scale temporal events (proposed v0 tick sources):**

| Event | Source | Tick weight |
|---|---|---|
| Travel compression | `/travel` duration phase advancement | 1 phase = 1 atmospheric tick consideration |
| Long rest | Avrae `!lr` → `advance_time(source='rest_long')` | 1 tick consideration |
| Short rest | Avrae `!sr` → `advance_time(source='rest_short')` | 0 ticks (too granular) |
| Scene compression | Scene Lifecycle v1 hard-tier fire | 1 tick consideration |
| Explicit `/advance` | Operator-driven `advance_time(source='advance')` | weighted by phase_delta |
| Manual `/faction tick` | Operator escape hatch | always advances target faction |

**Predicate evaluation per tick event:**

When a tick event fires, evaluate each active faction's `tick_predicate_json` against:
- Current scene_state (location, mode)
- Recent player actions (engagement signals — did the party do anything related to this faction's goal?)
- Event source and weight
- Faction's `last_advanced_at` — minimum gap between advancements (cooldown)

**Predicate vocabulary (narrow v0):**
- `min_turns_since_last_advance` (cooldown)
- `event_source_required` (e.g., "only ticks on rest_long")
- `engagement_signal_required` ("ticks ONLY if party did NOT engage with quest X this session") — the "inaction becomes observable" mechanism
- `engagement_signal_blocks` ("does NOT tick if party engaged with quest X this session")

**Cadence philosophy:** story-scale, not MMO-timer-scale. Per-message cadence rejected. Tick density per session should average 1-3 advancements across all factions, not per-faction.

**§11 candidate:** v0 narrow vocabulary (only the four above) vs broader vocabulary (npc_interaction, consequence_kind, location_visit). Lean narrow at v0 per Composition Layer §11.7 precedent.

---

## 6. Pressure directive rendering

**`compute_pressure_directive(active_factions, scene_state) → (body, signals)`** — §59 sibling.

**Body shape when firing:**

```
=== OFFSCREEN PRESSURES ===
The Iron Vein Cartel (rumored, stage 2 of 4): Word has reached the harbor watch that new ore shipments may not arrive this week.
The Festival of Dawn approaches (known, stage 3 of 5): Preparations intensify; the herald has been seen consulting with the council.
```

- Cap at 2-3 factions rendered per turn (severity-then-recency per consequence ledger precedent)
- Only `visibility != 'unknown'` factions render
- Stage description is the prose surface (`current_stage_description` from DB)
- Block placed in tactical band, after consequences, before Scene Lifecycle (similar to Composition Layer act directive position)

**LLM job:** weave atmospheric pressures into narration where natural. Forbidden: invent new faction details not in `current_stage_description`; declare faction advancement; reference factions not in the block.

**Engine job:** maintain faction state, advance via predicate, render visible factions. LLM never writes state, only reads.

**Quiet baseline:** when no factions are at `visibility != 'unknown'` OR all factions are still at stage 1 default, directive returns `('', {})`. Same 86%-quiet baseline discipline as Scene Lifecycle v1 §5.

---

## 7. Solo-bard calibration

Per GPT framing — solo campaigns are especially vulnerable to punishment accumulation.

**v0 defaults that protect solo play:**

1. **Atmospheric-heavy bias.** v0 ships with atmospheric pressure as default `pressure_kind`. Hard progression requires explicit skeleton.md authoring OR `/faction set kind:hard_progression` operator action.

2. **Engagement-signal-blocks cooldown.** Default predicate: factions don't tick on turns where party engaged with quest/NPC related to that faction. Engagement = active reason for the world to pause its pressure.

3. **Stage density tuned for solo cadence.** v0 default: 3-4 stages per atmospheric faction, 5-6 stages per hard-progression faction (longer arc to give solo player narrative space).

4. **Visibility gating.** Most factions start `unknown` at bootstrap, transition to `rumored` after first atmospheric tick, only reach `known` after multiple ticks or explicit player discovery. Prevents solo player from being aware of three escalating threats from session one.

5. **Pressure directive cap.** Maximum 2-3 factions rendered per turn (per §6). Even if 5 factions are active, narration only surfaces the most-tactically-relevant subset.

**§11 candidate:** are these defaults aggressive enough? Should v0 ship with all-atmospheric and hard-progression as v1.x candidate, or with the bias-toward-atmospheric semantic shipped at v0 with hard-progression capability disabled-by-default?

---

## 8. Forward-coupling from prior ships

**N-10 Canon Bootstrap Bot:** Per §11.8 lock, factions live in skeleton.md only. S69 ships the one-shot migration from skeleton.md faction blocks to `dnd_factions` rows. Migration runs at engine init post-S69-deploy. Idempotent on faction name. Bootstrap-authored factions get `skeleton_origin=1`.

**S68 N-4 pronoun lock:** Factions can have NPC affiliations (`Iron Vein Cartel` faction might have NPC member "Grahn"). N-4's pronoun lock on Grahn carries forward; faction state doesn't override NPC pronouns. Independent surfaces.

**Quest Layer v0/v0.1:** Quests can have faction associations (per Quest Layer schema if `associated_faction_id` exists — recon needed). If yes, quest engagement signals feed faction predicate evaluation. If no, file as v1.x integration.

**Composition Layer v0:** Quest acts and faction stages are independent state machines. They may correlate (party is in Act 2 of a quest while the antagonist faction is at Stage 3), but no schema coupling at v0.

**Scene Lifecycle v1:** Hard-tier compression is a tick trigger source. Per §5 above. Confirmed clean coupling.

**N-3.1 (filed forward):** Once commitment-tracking ships, faction commitments (promises factions make through their NPC representatives) feed the commitment ledger. v1.x coupling.

---

## 9. §11 architectural questions

Surfaced for operator lock before spec drafting. Leans named where confident.

1. **`dnd_factions` schema scope.** v0 schema per §4 above (minimal viable: identity, goal, stage, visibility, pressure_kind, predicate, audit). Or extended schema (regions, hostility levels, NPC member lists, faction-to-faction relationships)? *Lean: minimal viable.* Extended schema is v2+ temptation per GPT framing.

2. **Hard progression at v0 — ship capability or defer.** (a) v0 ships `pressure_kind='hard_progression'` capability but disabled-by-default at predicate level (operator must explicitly enable per faction). (b) v0 ships atmospheric-only; hard progression v1.x. *Lean: (a)* — capability ships but defaults protect solo play. Operator opt-in for hard-progression makes the intent explicit.

3. **Tick trigger event set.** Confirmed v0 sources per §5: travel compression, long rest, scene compression hard-tier, explicit `/advance`, manual `/faction tick`. Add downtime transitions (if recognized)? *Lean: ship the five sources; downtime as v1.x candidate if recognizable as a discrete event.*

4. **Predicate vocabulary breadth.** Narrow (cooldown, event_source, engagement_signal_required/blocks) vs broader (npc_interaction, consequence_kind, location_visit). *Lean: narrow at v0.* Composition Layer §11.7 precedent — narrow vocabulary ships first; v1.x expansion if operator authoring friction surfaces.

5. **Skeleton.md → DB promotion shape.** One-shot migration at engine init (S69 deploy) only, or repeatable via `/faction seed-skeleton`? *Lean: repeatable, mirroring `/quest seed-skeleton` precedent.* Operator may add factions to skeleton.md mid-campaign and want to import without DB-level surgery.

6. **Faction → consequence integration.** Does atmospheric pressure write to `dnd_consequences` ledger when stage advances ("the cartel grows bolder" as a consequence) or render directly via §6 pressure directive? *Lean: render directly at v0.* Cleaner separation of surfaces; consequences ledger stays focused on direct NPC interactions.

7. **Operator override semantics.** `/faction reset` requires confirmation gate for hard-progression factions? *Lean: yes.* Hard-progression by definition irreversible; operator override requires explicit confirmation to prevent accidental narrative-state mutation.

8. **`current_stage_description` authoring at v0.** Operator-authored via skeleton.md (each stage gets prose), or LLM-extracted from goal text via N-10 v0.2-style suggester? *Lean: operator-authored at v0.* N-10 Bootstrap Bot can author all stages at bootstrap time. LLM-extraction is v1.x if observed friction.

9. **Faction visibility transitions — auto or operator?** Atmospheric tick advances stage AND potentially visibility (`unknown → rumored → known`). Auto-transition on stage advance, or operator-driven? *Lean: auto-transition with threshold rules.* Stage 1 → `unknown`; Stage 2 → `rumored`; Stage 3+ → `known`. Operator override available via `/faction visibility`.

10. **§1b suggester for tick proposal?** Per Composition Layer v0 §1b fourth-instance precedent, should faction ticks fire via `#dm-aside` suggester ("Iron Vein Cartel is eligible to advance — approve with /faction tick?")? *Lean: NO at v0.* Faction ticks happen at engine-recognized temporal boundaries (rests, travel) which are already operator-driven. Adding a second approval gate is friction. Engine-deterministic tick with `/faction hold` as the operator escape hatch.

11. **Composition forward-compatibility — silent.** Per discipline: v0 schema doesn't pre-couple v1.x candidates (relationship matrices, resource simulation, NPC member lists).

12. **Initial faction count guidance.** Should N-10 Bootstrap Bot's faction card count change with S69 ship? Currently 1-2 factions per bootstrap. Lean: keep at 1-2 for v0; observed-friction reveals if more needed.

---

## 10. Operational concerns for Phase 1 recon

**Skeleton.md faction prose format audit.** N-10 v0/v0.1 authored faction blocks into skeleton.md. Phase 1 must inspect the actual format used — what fields the bot wrote, whether `tick_predicate` is parseable, whether stage descriptions exist or only top-level goal. Migration shape depends on this.

**Existing `dnd_*` table schema verification.** Confirm no `dnd_factions`-adjacent column exists on `dnd_campaigns` or elsewhere that the design didn't anticipate.

**`advance_time` call sites enumeration.** Confirm all four §17-locked sources still fire correctly; verify `last_advanced_event` capture point in tick predicate evaluation.

**Quest Layer association recon.** Does `dnd_quests` schema include `associated_faction_id` or equivalent? §8 forward-coupling depends on this.

**Pressure directive prompt-size budget.** Current baseline ~25-26k chars (post-S67). Pressure directive at ~200-400 chars when firing 2-3 factions. Budget-safe.

---

## 11. What this sketch does NOT do

- Lock §11 decisions. Spec doc handles.
- Address relationship matrices, social graphs, NPC member lists (v2+ temptation).
- Address resource simulation (gold, troops, supplies).
- Address hierarchical planning (faction goals nested under campaign arcs).
- Address NPC-as-faction-agent behavior (NPCs don't autonomously act on faction goals at v0).
- Address PC-tracker mechanics (factions don't hunt or directly target players).
- Address multi-faction interactions (one faction reacting to another's advancement).
- Address ARC payoff machinery (campaign-scale thematic construction is post-Causality-Engine territory).
- Pre-commit operator approval gate on tick proposals (engine-deterministic).
- Pre-commit emergent-faction-detection from narration (v1.x if observed).

---

## 12. Next move

Path A three-session cadence: spec → review → implement.

**Phase 1 recon scope:**
1. Skeleton.md faction prose format audit — what N-10 actually wrote
2. `dnd_factions`-adjacent column audit on existing tables
3. `advance_time` call sites and event-source threading
4. Quest Layer `associated_faction_id` recon
5. Pressure directive prompt-size baseline confirmation
6. Skeleton-faction promotion idempotency design recon

**Phase 2 walks §11.1 through §11.12 with operator.**

**Phase 3 ships locked spec.**

After v0 ships and the operator plays through a session with active factions, observed friction tells us which v1.x candidates earn slots (hard progression elevation, predicate vocabulary expansion, NPC-as-faction-agent behavior, multi-faction interactions).

**This is the architectural ship that converts the foundation into a campaign engine.** Per project-history-arc framing: the F-54 motion-system stack (Scene Lifecycle, Quest Layer, Composition Layer) provided the player-side motion primitives. N-10 closed the authored-canon-volume gap. S68 closed the NPC-commitment-rail gap. S69 closes the world-side-motion gap. After this, the project has its full motion-system stack operating, and observed friction drives whatever ships next.
