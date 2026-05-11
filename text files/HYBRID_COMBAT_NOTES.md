# Hybrid Combat — Architectural Notes (v3)

**Status:** Notes-not-spec. v3 incorporates ChatGPT review (S37) AND Gemini review (S37). Architectural thinking captured for the long term; near-term execution path explicitly reframed against engineering reality.

**Trigger:** S36 Ship A ✅ promoted (the resolution-binding loop works). S37 conversation surfaced two extended-play concerns: novelty/repetition over long campaigns, and combat-pacing friction (30-minute init-based combats feel wrong in conversational AI play).

**v2 history:** v1 surfaced the hybrid combat idea. ChatGPT review surfaced nine architectural flags and proposed a 4-tier compression ladder (incorporated into v2). Gemini review pushed back structurally: the 4-tier ladder violates "you can't compress 5e without breaking 5e," and at a broader scope (full repo review), Gemini argued the project should stop designing hypothetical pacing fixes entirely and playtest the current architecture extensively before committing to any combat architecture.

**v3 resolves the tension.** The long-term architectural vision (compression ladder, priority windows, encounter objectives, state-axis modeling) is preserved here as a reference design for the post-multiplayer-fixes era. **The near-term execution path is the structural retreat Gemini argued for:** playtest extensively, ship "dumb combat" (LLM-narrative-wrapped Avrae init) as the next combat ship, let observed friction drive what comes next.

---

## §1. The two-horizon framing

This doc carries two horizons because the architectural thinking and the execution path live at different time scales.

**Near-term execution (S37+, observable in months):**
- Finish the multiplayer-fixes plan as scoped, with the MVP-test scrutiny applied to Ships 4 and 5 (see §11)
- Extensive multi-hour playtesting in current architecture
- Ship "dumb combat" — standard Avrae init with LLM-narrated transitions (no hidden init, no compression, no parallel state surfaces)
- Listener edge-case verification (advantage, crits, multi-attack, resistance)
- Let observed friction during real play dictate what combat work earns its slot next

**Long-term reference design (v2+ horizon, years not months):**
- Combat compression ladder (Tier 0-3) if observed friction surfaces real need
- Priority window system for engine-internal sequencing
- Encounter objectives beyond "wipe enemies"
- Class identity preservation mechanics
- The full state-axis architecture from v2

**The discipline:** the long-term vision survives as a north star, but it does NOT direct the next ship. The next ship is whatever observed friction in extensive playtesting says it should be. This is "evolve from observed friction, not anticipated friction" applied to architecture itself.

---

## §2. The principle that survives both reviews

5e's mechanical depth stays. Avrae owns the math. Bot owns the narrative wrap. The LLM never decides mechanical outcomes.

This is consistent with §1a, the three-layer 5e doctrine, and everything Ship 1 + Ship A established. No combat architecture, near-term or long-term, modifies this.

What's negotiable across horizons: the *cadence* of combat (turn-by-turn vs beats vs skill-challenge sequence), the *visibility* of mechanical state to players (init shown vs hidden), and the *compression* of low-stakes encounters.

What is NOT negotiable across horizons: Avrae as mechanical truth, no parallel physics/positioning engine, no LLM-authored state mutations, no compression that strips player agency over reactions and resources.

---

## §3. Near-term execution path (the actual next ships)

### §3.1 What ships next, in order

1. **Ship 2 — Scene State Canon Discipline** (already locked in multiplayer-fixes plan v3; Finding A closure)
2. **Ship 3 — NPC State-Sync Boundary** (already locked; Finding H closure)
3. **Playtest phase** — extensive multi-hour solo and small-group sessions in the post-Ship-3 architecture. Pacing observation, content variety observation, combat friction observation. **No new architecture during this phase.**
4. **MVP-test pass on Ships 4 and 5** — re-examine against actual playtest evidence. Ship if observed friction justifies; defer if not.
5. **Listener edge-case verification ship** — confirm `avrae_listener.py` handles advantage, disadvantage, crits, resistance, multi-attack embeds correctly. Small ship, observation-driven.
6. **"Dumb combat" ship** — standard Avrae `!init begin` for combat; bot narrates top of each round to smooth transitions. No hidden init, no compression, no new state surfaces.
7. **Then evaluate** — has observed friction surfaced specific combat problems that the long-term architecture would solve? If yes, file targeted ships for those specific problems. If no, the project is closer to v1.0 than v2.

### §3.2 What does NOT ship near-term

The entire long-term reference design in §4-§9 of this doc is **not near-term work.** This includes:
- Combat compression ladder
- Priority window system
- Enemy intent state tracking
- Reaction tier system
- Class identity preservation mechanics (martial side specifically)
- Declaration windows for PvP coordination
- Positioning state at narrative granularity (zones, engagement groups, etc.)
- Encounter objectives system
- Avrae bookkeeping translation layer

Each of these may earn its keep eventually. None earn it preemptively. Each waits for observed friction in real play to justify its slot.

### §3.3 The discipline being applied

Gemini's broader review crystallized the discipline: **the project's most precious resource is engineering bandwidth, and architectural ambition without playtested grounding produces beautiful systems that solve speculative problems.**

The hybrid combat doc as originally written drifted from this. v3 corrects course. The architectural ambition lives in §4-§9 as reference, not as roadmap. The roadmap stays disciplined.

---

## §4. Long-term reference design — Combat compression ladder

(Reference material. Not committed work. May or may not earn its slot depending on observed friction.)

The compression ladder maps combat shape to encounter stakes:

| Tier | Name | Resolution shape | Beat count | Mechanical surface |
|---|---|---|---|---|
| 0 | Trivial | Skill challenge sequence (Ship A `!check` infrastructure) | 1-3 rolls | Skill check + narrative consequence; **not 5e combat** |
| 1 | Skirmish | Standard Avrae init with narrative compression | Full rounds | Standard 5e combat, bot narrates transitions and may compress some rounds when no one declares reactive intent |
| 2 | Dangerous encounter | Standard Avrae init with full reaction surface | Full rounds | Standard 5e combat, all mechanical surface preserved |
| 3 | Boss / setpiece | Standard Avrae init with legendary/lair surface | Full rounds | Standard 5e combat at maximum mechanical depth |

**Critical reframe from v2:** Tier 0 is explicitly *not* compressed 5e combat. It is a skill-challenge surface using Ship A's existing infrastructure. The player knows what they're getting — a skill check sequence, not tactical combat. Their character's reactions don't apply because they aren't in combat. This addresses Gemini's "you can't compress 5e without breaking 5e" pushback directly: don't pretend to compress 5e; explicitly use a different mechanical surface for trivial encounters.

Tiers 1, 2, and 3 all use standard Avrae init. The differences between them are *narrative-layer* concerns (how much the bot narrates, how much it compresses dry mechanical exchanges in narration). The *mechanical* layer is identical across tiers 1-3.

**What this loses from v2:** the hidden-init "narrative beats" idea. Initiative is visible. Players see "round 3, Garrick's turn." The bot's job is to make the transitions feel narratively connected, not to obscure the mechanics.

**What this gains:** structural simplicity, no NLP-to-Avrae translation layer for arbitrary intents, no parallel state surfaces, full player agency over reactive resources.

### §4.1 Tier 0 implementation note

Tier 0 is buildable today using only Ship A infrastructure. A "skill challenge encounter" is a sequence of `!check` directives + narrative consequences. No new architecture needed. If observed friction surfaces a need for this (e.g., "running a bandit ambush as full init feels disproportionate"), it ships as a small dedicated mode rather than as a combat-architecture rewrite.

### §4.2 Tier 1-3 implementation note

Tier 1-3 differ only in narration intensity, not in mechanical orchestration. Standard Avrae init handles all of them. The bot's contribution is varying narration — minimal for Tier 1 (smooth transitions), rich for Tier 3 (full atmospheric weight per beat).

This means **the entire compression ladder above Tier 0 reduces to "good narration during standard combat"** — which is what "dumb combat" already delivers in v3's near-term execution. The ladder framing is useful as a way to think about narration intensity, but it doesn't require new architecture.

---

## §5. Long-term reference design — What might earn architectural work eventually

The following ideas survive as architectural candidates but are explicitly NOT v1 work. They earn their slot only if observed friction during playtesting surfaces a specific need.

### §5.1 Encounter objectives beyond HP=0
ChatGPT FLAG 8 and Gemini both agreed this is the strongest architectural insight in v1/v2. Combat ends for many reasons: morale collapse, objective achieved, retreat, negotiation, environmental shift. Default `wipe_enemies` works for most encounters; explicit objectives (defend, escape, interrupt, survive, negotiate) unlock richer encounter design.

**When this earns its keep:** when the first DM-authored encounter wants an objective beyond "kill them all." File then; don't pre-build.

### §5.2 Enemy intent state (engine-written, LLM-read)
ChatGPT FLAG 5. Enemies commit to plans across beats; plans can be interrupted; deception is intentional rather than retroactively invented. The principle is correct and aligns with Ship 2's canon discipline (engine-writable, LLM-readable).

**When this earns its keep:** when observed friction surfaces "enemy behavior feels arbitrary, plans aren't sticky." Until then, enemies acting on each turn per RAW is fine.

### §5.3 Reaction tier system
ChatGPT FLAG 3. Categorize reactions (automatic / interrupt / cinematic queued / silent) to manage pacing under heavy reaction surface.

**When this earns its keep:** when observed friction surfaces "reactions are interrupting too often and pacing dies." Until then, RAW reaction prompts work fine and may be uncommon enough not to matter.

### §5.4 Class identity preservation (martial-side)
ChatGPT FLAG 4. Compressed beats favor casters. Martials need sustained tactical tempo to express identity.

**Under v3's reframe, this concern partially evaporates.** Tier 1-3 use standard 5e combat, which preserves martial identity natively. Only Tier 0 (skill challenge) abstracts away the action economy, and Tier 0 is opt-in/stakes-driven, so a martial player who wants tactical expression gets it in Tier 1+ encounters.

**When this earns its keep:** if Tier 0 ever surfaces as overused and martials feel diminished. Likely never; Tier 0 is for trivial encounters where compression is desired anyway.

### §5.5 Declaration windows for PvP coordination
ChatGPT FLAG 6. Multi-PC combat coordination via short declaration intervals.

**Under v3's reframe with standard Avrae init, this isn't needed.** Avrae's init order solves PvP coordination natively. Declaration windows were an answer to a hidden-init problem v3 doesn't have.

**When this earns its keep:** if Tier 0 skill-challenge encounters with multiple PCs surface coordination friction. Probably not.

### §5.6 Positioning state at narrative granularity
Gemini FLAG 3 and the broader directive both pushed back hard on this. Building parallel positioning state is a state-drift risk and a parallel physics engine. v3 rejects this entirely — positioning stays where it is today (Avrae's range awareness + LLM narrative consistency, neither authoritative).

**When this earns its keep:** never, probably. If positioning emerges as a real problem during playtest, it gets solved by leaning more on Avrae's range mechanics, not by building parallel state.

### §5.7 Priority window system / hidden init
ChatGPT FLAG 1. Engine-internal sequencing with hidden initiative.

**Under v3's reframe, this isn't needed.** Init is visible. Players see turn order. The "hidden init" idea was an artifact of the compression-without-skill-challenge framing that v3 abandons.

---

## §6. The novelty / repetition concern (separate but related)

ChatGPT raised this alongside combat pacing. The fix is causality and statefulness, not infinite content generation.

The world-systems list (faction simulation, regional identity, encounter memory, unresolved consequences, world pressures, etc.) lives in F-54 (stagnation drift) territory — the motion-systems thread paused for multiplayer fixes.

**v3 disposition:** this thread re-opens post-multiplayer-fixes naturally. Same discipline applies: ship the next motion-system primitive (probably Scene Lifecycle v1 was the candidate), playtest, observe what causality matters, build the next system from observed friction.

The architectural through-line — "the LLM doesn't invent the world; deterministic systems generate the world, LLM renders what the world currently is" — survives as a doctrine candidate that should anchor once second-instance evidence accumulates (Ship 2's canon discipline is partially this shape).

---

## §7. What this doc explicitly is NOT

- Not a spec
- Not a near-term ship
- Not a commitment to ANY of the architectural ideas in §4-§5 beyond "we may revisit if observed friction justifies"
- Not a roadmap entry (yet)
- Not doctrine (yet)
- Not a substitute for playtesting

Most importantly: **this doc is not authorization to design more combat architecture before extensive playtest evidence accumulates.** The discipline Gemini's broader review enforces is the controlling discipline. Architectural ambition without playtested grounding is the failure mode being explicitly avoided.

---

## §8. Open questions (sharpened for the v3 framing)

1. **When does the "dumb combat" ship actually happen?** Post-Ship-3? After full multiplayer-fixes plan? After the MVP-test pass on Ships 4/5? Probably: as part of the post-Ship-3 playtest phase, since playtesting combat without ANY narrative wrapping is the wrong baseline. Recommendation: dumb combat ships alongside playtest readiness.
2. **Listener edge-case verification — scope.** Advantage, disadvantage, crits (attack and damage doubling), resistance/vulnerability, multi-attack embeds (one `!a` command, multiple attack rolls), saves with halved damage, death saves. What else?
3. **MVP-test scrutiny on Ships 4 and 5.** Ship 4 (Scene-Scope-First Identity) — does Finding B's name-resolution drift actually block play, or is it cosmetic until something compounds? Ship 5 (Polish) — most of these are cosmetic by definition. Recommendation: defer Ship 4 unless playtest surfaces real blocking; defer Ship 5 entirely until observed friction surfaces specific items.
4. **The motion-systems thread post-multiplayer-fixes.** F-54 stagnation drift was the parallel thread before the multiplayer-fixes plan superseded it. Does it re-open after the playtest phase, or does playtest-observed friction supersede it too?
5. **Playtest cadence.** How many sessions, over what time window, before the project has enough evidence to make architectural decisions about combat? Lean: at least 3-5 multi-hour sessions across solo and small-group play, with explicit notes on pacing friction, content variety, combat feel, novelty fatigue.

---

## §9. Change log

**v3 (this version, post-Gemini review + Gemini broader directive):**
- Two-horizon framing introduced (§1): near-term execution path is structural retreat per Gemini's discipline; long-term reference design preserved as architectural thinking
- §3 NEW: explicit near-term execution path (the actual next ships)
- §4 reframed: compression ladder retained but Tier 0 explicitly recast as skill challenge (not compressed 5e), Tier 1-3 collapse to "good narration during standard Avrae init"
- §5 NEW: long-term architectural candidates explicitly filed as "earn-their-keep-only-if-observed-friction-justifies"; each candidate paired with disposition under v3's reframe
- §6 streamlined: novelty concern restated, same architectural through-line
- §7 hardened: explicit "this doc is not authorization to design more combat architecture before playtest"
- §8 rewritten: questions sharpened for v3 framing, mostly about near-term execution
- v2 §2 (4-tier ladder as committed structure) → §4 (filed as reference design only)
- v2 §6.2-§6.7 (priority windows, encounter state, beat tiers, enemy intent, reaction tiers, martial mechanics) → §5 (architectural candidates, each disposed against v3's reframe)
- v2 §7 (declaration windows) → §5.5 (not needed under standard init)
- v2 §8 (Avrae bookkeeping vs combat engine fork) → resolved: Avrae IS the combat engine (Option B from v2), no fork needed
- v2 §9 (F-55 cluster reshape including #5.6-#5.10) → REMOVED, those siblings don't exist as committed work
- v2 §11 (open questions) → §8 (sharpened against v3 framing, fewer speculative questions)

**v2 (post-ChatGPT review):** 4-tier compression ladder, priority windows, encounter objectives, full state-axis modeling, F-55 cluster reshape into 10 siblings.

**v1 (original):** hybrid combat concept, beat structure, multi-effect resolution, scene-based combat framing.
