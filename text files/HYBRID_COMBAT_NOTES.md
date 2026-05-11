# Hybrid Combat — Architectural Notes (DRAFT v2)

**Status:** Notes-not-spec. v2 incorporates ChatGPT review (S37). Captures architectural thinking from S37 conversation while context is fresh. Not yet roadmap-filed. For Gemini review next, then final-draft pass.

**Trigger:** S36 Ship A ✅ promoted (the resolution-binding loop works). S37 conversation surfaced two extended-play concerns: novelty/repetition over long campaigns, and combat-pacing friction (30-minute init-based combats feel wrong in conversational AI play). ChatGPT review surfaced nine architectural flags and one structural reframe (combat compression ladder); v2 incorporates them.

**Not committed.** Filed as future architectural arc — sequencing TBD post-multiplayer-fixes plan (S37-S43).

---

## §1. The principle

5e's mechanical depth stays. 5e's rigid turn cadence goes — but **initiative itself stays as an engine-internal mechanism**, not a player-facing interaction model.

Players still track HP, levels, spell slots, hit dice, conditions. Monsters still have stat blocks, AC, saves, attack bonuses, damage dice. Class identity (rogue's sneak attack, fighter's multi-attack, wizard's spell selection) remains mechanically load-bearing. Avrae remains the mechanical authority.

What changes: the **cadence** of combat. Instead of player-visible "round 3, initiative 14, your turn," combat resolves in narrative beats whose internal sequencing is engine-driven. A beat is a meaningful unit of conflict (a rush, an exchange, a moment of pressure) that may resolve multiple mechanical effects from declared player intents, ordered internally via init.

The shift is structural, not mechanical. The audience-fit concern (players showed up for D&D, not PBTA) mostly evaporates because nothing the player *tracks* changes — only the *rhythm* of when they get to use what they're tracking.

---

## §2. The combat compression ladder (load-bearing reframe)

Combat shape is not one cadence. Combat shape scales with encounter stakes via four tiers:

| Tier | Name | Resolution shape | Beat count | Mechanical granularity |
|---|---|---|---|---|
| 0 | Trivial | Single-roll resolution | 1 roll | Aggregate effect (HP loss, scene advance) |
| 1 | Skirmish | Compressed beats | 2-3 beats | Per-beat hit/miss + damage + minor state shift |
| 2 | Dangerous encounter | Structured hybrid | 4-6 beats | Full state-axis modeling, declared-intent windows |
| 3 | Boss / setpiece | Near-full tactical cadence | 6-12+ beats | Per-action resolution, full reaction surface, legendary/lair mechanics |

Each tier is the *same architecture* at different granularities — engine-driven sequencing, multi-effect resolution, deterministic mechanics, narrative beats. Higher tiers expose more of the state machinery; lower tiers compress aggressively.

**Tier selection at encounter generation.** Stakes_tier from Ship A (compute_stakes_tier) maps to combat tier:
- `stakes_tier=low` + no objective → Tier 0
- `stakes_tier=low` + objective → Tier 1
- `stakes_tier=medium` → Tier 1 or Tier 2 depending on encounter design
- `stakes_tier=high` → Tier 2 default
- Explicit boss/setpiece flag → Tier 3

This solves the FLAG 2 (over-compression destroys tactical texture), FLAG 4 (martials need tactical cadence to shine), and FLAG 7 (state explosion at higher granularities) concerns simultaneously. Tier 0 doesn't model five axes; Tier 3 models all of them.

---

## §3. What stays unchanged across all tiers

- §1a (Avrae owns mechanics, LLM never decides outcomes)
- Three-layer 5e doctrine
- HP, hit dice, rests, conditions, exhaustion
- Spell slots, class resources, ability uses
- AC, saves, attack bonuses, damage dice
- Monster stat blocks, CR ratings, encounter difficulty calculations
- Class abilities trigger and resolve mechanically
- Long-term progression (XP, leveling, multiclassing)
- Avrae bookkeeping for HP / conditions / resources
- Ship 1 + Ship A's resolution-binding pattern (extends to combat, not replaced)

---

## §4. What changes

- **Init is engine-internal, not player-facing.** Engine computes init per-encounter via standard 5e dex-based mechanism (or Avrae's init tracker as the bookkeeping surface). Players never see "round 3, initiative 14." Engine uses init to order intent resolution within priority windows.
- **Player narrates intent; bot frames the beat.** "I rush the archer before he can fire" → bot reads scene, identifies relevant enemies, frames what's at stake, requests the appropriate roll(s).
- **Multi-effect resolution per beat, tier-scaled.** One declared intent at Tier 1 might resolve hit + damage + minor reposition. The same intent at Tier 3 might resolve as a single attack with separate rolls for hit, damage, opportunity attack from another enemy, and reaction prompt.
- **Variable beat count per encounter, emergent from encounter state machine.** Engine checks encounter state after each beat; encounter resolves when state-machine transition condition met.
- **Encounter end is objective-driven, not strictly HP-driven.** Default objective "wipe enemies"; better objectives (defend, escape, interrupt, survive, negotiate) first-class.

---

## §5. The state axes modeled (varies by tier)

Scene-based combat models up to five axes per encounter. Lower tiers ignore axes that don't matter:

1. **Momentum** — who has narrative initiative-of-the-moment (party pressing, enemies recovering, stalemate). Tier 2+ tracks.
2. **Danger** — current threat level (multiple adjacent, PC bloodied, environmental hazard active). Tier 1+ tracks.
3. **Positioning** — spatial state at **narrative granularity**, not grid coordinates:
   - Zones (the doorway, the high ground, the choke point, the open floor)
   - Engagement groups (the party is engaged with the front line; the wizard is rear-engaged with the archer)
   - Narrative ranges (adjacent, near, far, distant — discrete categories)
   - Threat relationships (the spearman threatens the wizard, the archer threatens the cleric)
   - **Tier 2+ tracks; no hidden grid simulation at any tier.**
4. **Enemy intent** — what enemies are about to do. **Engine-written, never LLM-written** (see §6.5). Tier 1+ tracks.
5. **Injury state** — aggregate party + enemy HP / condition state. Existing Avrae layer. All tiers track.

Tier 0 tracks only injury state. Tier 1 adds enemy intent + danger. Tier 2 adds positioning + momentum. Tier 3 adds full granularity including legendary/lair action timing.

---

## §6. Architectural pieces needed

### §6.1 Multi-effect resolution
Ship A's `ResolutionResult` binds one outcome to one narration constraint. Hybrid combat needs a sibling shape:

```python
@dataclass(frozen=True)
class BeatResolution:
    tier: int                              # 0-3
    rolls: list[ResolutionResult]          # one or more rolls inside the beat
    damage_dealt: dict[str, int]           # by target
    damage_taken: dict[str, int]           # by actor
    state_mutations: list[StateMutation]   # positioning, intent, momentum shifts
    reactions_triggered: list[Reaction]    # see §6.6
    encounter_state_after: EncounterState  # aggregate post-beat
```

Extends rather than replaces. Tier 0 BeatResolution carries one ResolutionResult and no mutations beyond HP. Tier 3 carries many.

### §6.2 Priority window system (NEW, addresses FLAG 1)
Hybrid combat doesn't eliminate initiative — it hides it. Engine maintains:

- **Encounter phase** (engagement → escalation → climax → resolution; or whatever phase model the encounter uses)
- **Active pressure** (which actors are currently positioned to act)
- **Reacting entities** (which actors have reactions available)
- **Interrupt eligibility** (which declared intents can be interrupted by which others)
- **Declared intents queue** (ordered by init within the current priority window)

Players don't see this. Player declares intent → enters queue → engine resolves intents in init order within the priority window → bot frames composite beat showing resolved sequence.

**Priority windows replace init turns.** A window is a chunk of time during which multiple actors declare intent. Engine resolves the window, transitions to next window. Tier 0-1 might have one window per beat; Tier 3 might have multiple windows per beat (declaration → main action → reaction window → next declaration).

### §6.3 Encounter state machine + objectives (expanded from v1, addresses FLAG 8)
Encounter has explicit state + objective:

```python
@dataclass
class EncounterState:
    objective: EncounterObjective          # default "wipe_enemies"; alternatives below
    phase: str                             # 'engaged' | 'enemies_fleeing' | 'objective_met' | 'objective_failed' | 'negotiating' | etc.
    combatants_alive: dict[str, bool]
    combatants_hp_aggregate: dict[str, int]
    objective_state: dict                  # objective-specific (caravan_hp, ritual_progress, timer_remaining, etc.)
    tier: int                              # set at encounter generation
```

Objective examples:
- `wipe_enemies` (default): ends when all enemies down/fled
- `defend_target`: ends when target reaches safety or destroyed
- `escape`: ends when party clears exit
- `interrupt_ritual`: ends when ritual interrupted or completes
- `survive_timer`: ends when timer expires or party drops
- `assassinate`: ends when target killed or escapes
- `negotiate`: ends when terms accepted or rejected

State transitions are objective-driven, not HP-driven. Default `wipe_enemies` keeps the simple shape; other objectives compose to richer encounter design.

**Objective is set at encounter generation, not LLM-decided mid-encounter.** Mutations come from observed events (party reaches exit zone → escape objective met).

### §6.4 Beat complexity tiers (expanded from v1, addresses FLAG 2)
Per-tier resolution shape:

- **Small beat (Tier 0)**: single roll resolves aggregate. "You charge the goblin. Roll athletics." → 1 roll, encounter advances or resolves.
- **Medium beat (Tier 1)**: one attack + one consequence. "You charge the archer. Roll athletics to close, then attack." → 2 rolls, beat resolves with hit/miss + minor state shift.
- **Large beat (Tier 2)**: multi-state shifts. "You charge the archer; the spearman moves to intercept. Athletics to break through, then attack roll." → 2-3 rolls, beat resolves with multi-actor effects.
- **Boss beat (Tier 3)**: segmented exchanges. Full reaction surface, legendary actions interleave, multiple priority windows within one narrative beat.

The compression level matches encounter stakes. No system-wide pre-commit to one shape.

### §6.5 Enemy intent system (LLM-readable, engine-writable, addresses FLAG 5)

Enemy intent is a persisted state axis with strict write-authority:

- **Set at encounter generation.** When an encounter spawns, each enemy gets initial intent based on deterministic rules (archers prefer range, melee engages nearest threat, ranged casters target spellcasters first, leaders coordinate, etc.). v1 uses rules; LLM-suggested-then-validated is v1.x.
- **Updated by observed events.** Enemy gets rushed → intent updates (defensive, retreat, counter-attack per rules). Enemy's plan interrupted → intent shifts. Engine drives the updates; never LLM.
- **LLM reads intent to frame beats.** "The archer is drawing back, preparing to fire next window" comes from intent state, not LLM invention.
- **Intent durability is load-bearing.** Enemies commit to plans across beats. Plans can be interrupted (interrupting the goblin shaman's summon ritual has consequences). Deception is intentional — an enemy can have hidden intent set at encounter generation that surfaces later, but it was committed upfront, not invented mid-beat.

**Same discipline as scene_state.location per Ship 2.** Enemy intent hits the four-property latent-canon test if LLM-writable; structural removal of write authority beats validation.

### §6.6 Reaction tier system (expanded from v1, addresses FLAG 3)

Reactions categorize into four classes by importance + prompt cost:

- **Automatic**: trigger without prompt. Shield-of-faith continues, sanctuary persists, simple defensive triggers. Engine resolves silently in the beat.
- **High-importance interrupt**: prompt player mid-beat. Counterspell on a big spell, shield on a critical hit, sentinel on a key escape. Worth the pause.
- **Cinematic queued**: trigger but resolve after main beat completes. Sentinel on a low-priority enemy, opportunity attack from secondary threats. Player sees outcome but beat doesn't pause.
- **Silent bypass**: ignore. Silvery barbs on a low-stakes attack, opportunity attack from low-threat enemies. Engine acknowledges via log but doesn't surface.

**Categorization is engine-decided**, not LLM-decided. Lookup table per reaction type × encounter tier × situational stakes. Tier 0-1 collapses most reactions to silent or automatic. Tier 3 surfaces full reaction depth.

Without filtering, six reaction prompts per beat is realistic at higher levels. Filtering is load-bearing for pacing.

### §6.7 Class identity preservation, martial-side (NEW, addresses FLAG 4)

Compressed beats favor casters (broad narrative actions fit naturally) over martials (sustained tactical tempo). v1 risks reducing martials to "I hit harder."

Candidate mechanics to surface inside beat resolution (not separate "your turn" surface):

- **Momentum control**: martials build/spend momentum across consecutive beats. Successful aggressive action builds momentum; spending momentum triggers extra effect (extra attack, knockdown, push).
- **Battlefield lock**: martials can constrain enemy positioning (Sentinel-style). Locked enemies cannot freely reposition; their intent updates accordingly.
- **Interrupt dominance**: martials get priority in reaction windows. When two reactions compete, martial reactions resolve first.
- **Protection mechanics**: martials draw aggro, redirect attacks from squishier allies (Protection fighting style, Cavalier mark, etc.).
- **Pressure generation**: sustained martial offense forces enemy intent shifts (defensive intent, retreat intent). Causal pressure on intent state.
- **Combo chaining**: consecutive successful beats build escalation bonus. Three hits in a row → next attack has advantage or extra damage.

**These are candidate mechanics, not v1 commits.** Ship hybrid combat without explicit martial spotlight mechanics first; observe whether martials feel diminished in practice. If observed friction surfaces, file v1.x ship for martial mechanics.

The risk of pre-building these: speculative imbalance might not match observed play. Some martial players may *prefer* compressed combat ("I make my attacks and the scene advances" beats "I count squares for 30 minutes").

The risk of skipping these: known failure mode of compressed-combat systems (PBTA and Blades both struggle with martial-vs-caster balance for exactly this reason). Evidence isn't speculative.

**v1 decision: ship without martial spotlight mechanics; pre-commit to v1.x ship if Tier 2+ verify surfaces martial-vs-caster imbalance.**

---

## §7. Player-vs-player coordination via declaration windows (expanded, addresses FLAG 6)

When multiple PCs are in combat, who acts first in a given beat?

**Declaration window approach:**

- Bot signals beat start (explicitly or via "what do you do" prompt to active PCs)
- Short interval (30-60 seconds, tunable) during which all participating PCs declare intent
- Engine collects declared intents, resolves them in init order (per §6.2 priority windows)
- Bot frames composite beat that includes all participating PCs and their resolved outcomes

This preserves simultaneity (no "wait your turn" feeling) without rewarding speed (everyone has the same declaration window). Quiet players don't get steamrolled; loud players don't dominate.

Edge cases:
- Player doesn't declare in window → engine assumes they "ready" or "hold," intent queues for next window
- Player declares mid-resolution → enters next window, doesn't interrupt current beat
- Solo play → declaration windows collapse to "type intent, beat resolves" with no waiting

**Window duration is tier-scaled.** Tier 0-1 might use 15-30s windows; Tier 3 might use 60-90s for tactical thinking time.

This solves §6's PvP coordination question and composes with §6.2's priority window system. Declaration windows are the *external* surface; priority windows are the *internal* resolution mechanism.

---

## §8. Avrae integration: bookkeeping layer vs combat engine (REFRAMED, addresses FLAG 9)

The architectural fork that needs explicit decision:

**Option A — Avrae as bookkeeping layer:**
HP / conditions / resources tracked in Avrae. Engine drives combat cadence independently. Avrae's init tracker is used for engine-internal init computation only (`!init begin` called to populate, but `!init next` driven by engine, not by player turn-passing). Avrae's "until next turn" / "start of turn" / "end of turn" mechanics get translated to engine-tracked equivalents.

**Option B — Avrae as combat engine:**
Combat enters strict init mode via `!init begin`. Cadence follows Avrae's turn order. Hybrid combat is "narrative framing on top of normal Avrae combat."

**Recommended: Option A (bookkeeping).** Preserves engine-driven cadence; uses Avrae for HP / conditions / resources / spell slots / death saves. Init exists internally but isn't the cadence driver.

**Mechanics that get hard under Option A:**

- **Reactions**: 5e ties reactions to "since your last turn." Hybrid has no player-facing turns. Engine needs its own reaction-window tracking (probably per priority window, not per round).
- **Concentration**: Avrae tracks. Concentration breaks on damage — bookkeeping works here.
- **Duration effects**: "spells last 1 minute" or "until end of next turn." Engine translates to beat-count-tracked durations or wall-clock durations depending on effect type.
- **Legendary actions**: tied to specific turn boundaries in 5e. Engine surfaces them at appropriate beats (after each PC's resolved intent in Tier 3, probably).
- **Lair actions**: tied to initiative 20 in 5e. Engine schedules them at priority window boundaries.
- **Multi-attack**: per-turn in 5e. Engine surfaces all attacks within a single declared intent at the beat-resolution level.

**This is a multi-ship architectural arc on its own.** Avrae compatibility for hybrid combat isn't a "ship 5.5" thing — it's its own design problem with recon, spec, implementation cycles. Probably 2-3 ships' worth of work just for the bookkeeping integration.

The bookkeeping-vs-engine fork is the load-bearing decision; everything else in §6 composes against it.

---

## §9. F-55 cluster reshape

The Combat Playability Cluster currently includes:
- #5.1 Combat Entry Assist
- #5.2 NPC Turn Automation
- #5.3 Combat Cockpit Turn Card
- #5.4 Intent-to-Avrae Resolver
- #5.5 NPC State-Sync (ships in multiplayer-fixes Ship 3)

In hybrid combat:
- **#5.1 still applies.** Stat block suggestion at combat entry is the same problem regardless of turn structure. Adds: tier classification at encounter generation (which compression tier should this encounter run at?).
- **#5.2 reshapes into enemy intent system.** NPCs don't take "turns." Enemy intent state becomes the surface — bot reads intent, frames beats. Deterministic rules engine for intent updates is v1; LLM-suggested-then-validated is v1.x.
- **#5.3 reshapes into Beat Card.** What's at stake this beat, what options the player has, what resources they can spend, what reactions are available. Tier-scaled (Tier 0 has no Beat Card; Tier 3 has rich Beat Card with full state surface).
- **#5.4 becomes load-bearing.** Intent-to-Avrae resolution is the primary surface for hybrid combat. Every player declared intent goes through "narrate → bot frames beat → roll → resolve."
- **#5.5 already locked in multiplayer-fixes Ship 3.**

New cluster siblings:
- **#5.6 Combat compression ladder** — tier system, tier selection logic, tier-scaled state axes
- **#5.7 Priority window system** — engine-internal init, declaration windows, intent queue
- **#5.8 Reaction tier system** — categorization, filtering, prompt-vs-silent logic
- **#5.9 Encounter objectives** — objective types, objective-driven state machines
- **#5.10 Avrae bookkeeping integration** — translation layer for reactions / concentration / durations / legendary / lair

This is post-multiplayer-fixes work. Probably 8-12 ships' worth of architectural development past where the plan currently ends.

---

## §10. The novelty / repetition concern (related but separate)

ChatGPT raised this alongside the combat-pacing question. The fix is causality and statefulness, not infinite content generation.

The world-systems list:
- Faction simulation
- Regional identity
- Encounter memory
- Unresolved consequences
- NPC persistence (partial — exists, shallow)
- World pressures
- Procedural variation
- Campaign arcs
- Scarcity
- Political motion
- Time progression (✅ shipped, Track 4 #3)

Most are F-54 (stagnation drift) territory — the motion-systems thread paused for multiplayer fixes. Post-multiplayer-fixes, that thread re-opens.

Architectural through-line: **the LLM doesn't invent the world; the world is generated by deterministic systems, and the LLM renders what the world currently is.** Same shape as §1a, scaled from mechanical outcomes to content generation. Worth filing as doctrine candidate once second-instance evidence accumulates (Ship 2's canon discipline is partially this shape).

---

## §11. Open questions for review

1. **Tier boundaries.** Where does Tier 1 end and Tier 2 begin? Stakes_tier maps cleanly to encounter design, but the precise tier-transition rules need spec-time work.
2. **Class identity sufficiency at lower tiers.** Tier 3 preserves martial identity via full action surface. Tier 1-2 compress, which is where the FLAG 4 risk lives. Do the candidate martial mechanics (§6.7) need to ship for Tier 1, or only when Tier 1 verify surfaces friction?
3. **Enemy intent system shape.** Deterministic rules-based for v1 (locked). LLM-suggested-then-validated as v1.x. When does v1.x earn its keep?
4. **Beat granularity heuristic.** Tier-driven, emergent from encounter_state transitions, or hybrid? Lean tier-driven (§2 ladder) with emergent within-tier (engine checks state after each beat, transitions when objective conditions met).
5. **Avrae bookkeeping path.** Option A locked. Specific translation mechanics (reactions, durations, legendary actions) need recon and spec.
6. **PvP coordination cadence.** Declaration windows (30-60s tunable) locked. Window duration per tier needs verify-time tuning.
7. **Hybrid combat as v2 architectural arc vs incremental cluster reshape.** Probably both — Tier 1 (skirmish) ships first as proof-of-concept, Tier 0 / 2 / 3 build out from there. Sequence after multiplayer-fixes plan completes.
8. **Objective system as v1 vs v1.x.** Default `wipe_enemies` works for most encounters. Other objectives become useful when DM-authored encounters with explicit objectives surface. Lean: file objective architecture in v1; default objective is `wipe_enemies`; other objectives unlock when first non-default encounter ships.
9. **Reaction tier categorization.** Engine-decided via lookup table. Categorization table needs to be authored — which reactions are auto vs interrupt vs cinematic vs silent? Probably a recon pass against 5e RAW reactions inventory at spec time.
10. **State explosion under multiplayer.** Five axes × N PCs × M enemies × summons × environment caps via positioning at narrative granularity (zones, engagement groups, ranges, threat relationships). Worth solo-testing the abstraction before multiplayer load surfaces real complexity.

---

## §12. What this doc is NOT

- Not a spec. Architectural thinking captured pre-design.
- Not a near-term ship. Post-multiplayer-fixes at earliest.
- Not a commit to PBTA-shaped combat. Mechanical depth is preserved; only cadence changes.
- Not a doctrine candidate (yet). Filing notes; doctrine waits for proving instances.
- Not a roadmap entry (yet). Stays in notes form until external review + planner-side review converge on a shape.

---

## §13. Next steps

1. Gemini review on this v2 doc
2. Final-draft pass synthesizing both external reviews + planner-side review
3. Roadmap entry in ROADMAP.md under candidate-next-layers post-multiplayer-fixes
4. Eventually: F-55 cluster reshape spec when post-multiplayer-fixes architectural queue re-opens; likely starts with #5.6 Combat compression ladder as the foundational ship

---

## §14. Change log

**v2 (this version, post-ChatGPT review):**
- §1 reframed: init is engine-internal, not eliminated
- §2 NEW: combat compression ladder (Tier 0-3) as load-bearing structural reframe
- §4 expanded: init-internal framing; tier-scaled multi-effect resolution; objective-driven endings
- §5 expanded: tier-scaled state axes; positioning at narrative granularity locked (zones, engagement groups, ranges, threat relationships)
- §6.2 NEW: priority window system
- §6.3 expanded: encounter objectives, objective-driven state machines
- §6.4 expanded: beat complexity tiers (small/medium/large/boss)
- §6.5 locked: enemy intent engine-writable only, durability framing
- §6.6 NEW: reaction tier system (auto/interrupt/cinematic/silent)
- §6.7 NEW: class identity preservation, martial-side
- §7 expanded: declaration windows for PvP coordination
- §8 reframed: bookkeeping vs combat engine fork; Option A (bookkeeping) recommended; Avrae integration listed as multi-ship arc
- §9 expanded: F-55 cluster reshape includes new siblings #5.6-#5.10
- §11 rewritten: questions sharpened against v2 reframes
