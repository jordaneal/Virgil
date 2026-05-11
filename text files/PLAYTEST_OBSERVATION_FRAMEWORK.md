# Post-Ship-3 Playtest Observation Framework

**Status:** Captured S37 while fresh. Pre-Ship-2 spec drafting. Used post-Ship-3 to ground the playtest phase that gates further architectural work.

**Trigger:** S37 external review (ChatGPT + Gemini) named what playtest should actually measure. Both reviews converged on the same point: the project has crossed the threshold where player-experience data becomes trustworthy. The transition from "build the system" to "discover the game inside it" gates everything that comes next architecturally. This doc captures the metric framework so playtest doesn't default to "did it feel fast / did it feel fun" — those questions don't produce actionable architectural signal.

---

## §1. What this doc is for

After Ships 2 and 3 land, the multiplayer-fixes plan enters an extensive playtest phase. The purpose isn't validation ("does it work?") — it's discovery ("what kind of game emerges from this?"). The metrics below define what to look for so the playtest produces evidence that writes the next spec.

This is not a checklist. It's a sensitivity training — knowing in advance what's worth noticing during play, what to capture in session notes, what to grep journal logs for afterward.

---

## §2. Combat-specific metrics (per ChatGPT S37 review)

Playtest combat is the load-bearing observation surface. The hybrid combat reference design (`HYBRID_COMBAT_NOTES.md` v3) earns or doesn't earn its architectural ambition based on what these metrics reveal.

### §2.1 Time between meaningful decisions
**What:** Wall-clock time from one player-input-that-matters to the next player-input-that-matters per PC.

**Capture:** Note timestamps when a player meaningfully decides something (declare attack, choose target, spend resource, react to event). The gaps are the metric. Off-turn waiting that isn't engaged with the scene counts toward the gap.

**Threshold of concern:** If average gaps exceed 2-3 minutes regularly, combat momentum is at risk. Tabletop tolerates 30-second hesitation gaps; Discord magnifies them to multiple minutes through tab-out behavior.

**Architectural implication if observed:** Mode B (standard Avrae init + LLM narration) is insufficient. Some form of interaction compression is needed — declaration windows, parallel actions, structured beat resolution from `HYBRID_COMBAT_NOTES.md` §5 candidates.

### §2.2 Off-turn engagement
**What:** Do players stay emotionally engaged with the scene when it's not their turn, or do they mentally tab out?

**Capture:** Watch for off-turn players' presence in chat (reactions, comments, banter about the scene). Silence on off-turn is the warning sign. Compare to Avrae-init turn-by-turn cadence vs LLM-narration density.

**Threshold of concern:** If off-turn players consistently disengage within 2-3 turns, the system has lost them. Multiplayer combat is failing as a shared experience.

**Architectural implication if observed:** Narrative wrapping needs to address off-turn engagement — pulling other PCs into the scene narratively, surfacing what their characters are noticing/feeling. Or interaction compression so off-turn periods are shorter. Probably both.

### §2.3 State comprehension speed
**What:** How long after a beat resolves does the player understand the current state (who's at what HP, what conditions are active, who can act, what threats remain)?

**Capture:** Note questions like "wait, who's bloodied?" or "is the archer still up?" or "what's the goblin doing?" Each one is a state-comprehension failure.

**Threshold of concern:** Frequent state-comprehension questions mid-combat indicates the state surface isn't clear. The footer + Avrae embeds should be self-sufficient.

**Architectural implication if observed:** Beat Card surface (#5.3 in F-55 cluster) might earn its keep — explicit affordance display per player. Or the footer needs to carry more state. Or the LLM narration should restate state explicitly.

### §2.4 Clarification interruption frequency
**What:** How often do players have to stop the flow to ask the bot or each other "what just happened?" or "can I do X?"

**Capture:** Count clarification messages per combat scene. Compare combat scenes to exploration scenes.

**Threshold of concern:** If clarifications outnumber actions in combat, the rules-and-state surface is failing.

**Architectural implication if observed:** Either the LLM narration is unclear (prompt-side fix) or the system is exposing too much complexity (interaction compression). Need to disambiguate which.

### §2.5 Operational-vs-dramatic message ratio
**What:** What fraction of in-character messages are mechanical-operational ("I attack with my sword, +5 vs AC 14") vs dramatic-narrative ("I lunge at the goblin chief, blade flashing in the lantern light")?

**Capture:** Sample 20 player messages mid-combat. Tag each as operational, dramatic, or mixed.

**Threshold of concern:** If >70% operational, the system has reduced players to dice-rollers. If >70% dramatic, the system has reduced players to scriptwriters (mechanical agency may be diminished).

**Architectural implication if observed:** Bot's framing of beats is shaping player behavior. Mode A (skill challenge) probably produces more dramatic; Mode B (standard init) probably produces more operational. Goal is roughly balanced.

### §2.6 Momentum collapse frequency
**What:** How often does a combat scene lose narrative momentum — players stop engaging, conversation dies, the scene drags?

**Capture:** Note each scene where energy demonstrably drops. Try to identify what caused it (long pause, confusing event, off-turn drift, etc.).

**Threshold of concern:** Multiple collapses per session means the cadence is wrong.

**Architectural implication if observed:** Could be reaction-prompt overload, could be state confusion, could be turn-serialization too slow. The cause matters for the fix.

---

## §3. Novelty / repetition metrics (per ChatGPT S37 reframe)

ChatGPT's S37 reframe: **novelty is a simulation-depth problem, not a content-generation problem.** Players forgive surface repetition if outcomes differ, stakes evolve, factions react, relationships persist, economies shift, prior actions echo forward. Players become bored if the world resets emotionally, NPCs lack continuity, consequences evaporate, threats feel disconnected, scenes exist in isolation.

The metrics below test which side of that distinction Virgil's current architecture lands on.

### §3.1 Cross-session causality echoes
**What:** Do events from session N affect session N+1+? Does the world remember?

**Capture:** Specific moments where the bot references prior session events unprompted. The merchant remembers being helped. The bandit's surviving friends seek revenge. The faction's territory shifted because of the party's actions.

**Threshold of concern:** If session N+1 plays as if session N didn't happen, the project has shallow statefulness — ChatGPT's named long-term failure mode.

**Architectural implication if observed:** Motion-systems thread (F-54) is load-bearing. Faction simulation, NPC persistence depth, consequence durability — these need to ship to close the gap.

### §3.2 NPC continuity
**What:** When the party meets an NPC twice across sessions, does the NPC remember the prior encounter? Is their attitude shifted by past interactions?

**Capture:** Specific re-encounter moments. Tag as "remembered correctly," "remembered with drift," "forgotten."

**Threshold of concern:** If "forgotten" is common, NPC persistence depth is insufficient. If "remembered with drift" is common, the canon discipline (Ship 2 etc.) isn't extending to relationship state.

**Architectural implication if observed:** NPC state-sync (Ship 3) and scene state canon (Ship 2) may need extension to relationship/attitude state. Or the consequence layer (S16) needs deeper NPC-attached state.

### §3.3 Faction motion
**What:** Do off-screen entities (factions, rival NPCs, regional powers) change over time in response to or independent of the party's actions?

**Capture:** Watch for moments where the world shows it's been moving without the party. The bandit gang has consolidated. The merchant guild has expanded. The political situation in town has shifted.

**Threshold of concern:** If the world only changes when the party touches it, faction simulation is absent and the long-term boredom risk is high.

**Architectural implication if observed:** Faction simulation is a real ship, not a candidate. Multi-quarter arc per Gemini's framing.

### §3.4 Encounter recontextualization
**What:** Does a "generic goblin ambush" feel different at session 1 vs session 20 because of accumulated context?

**Capture:** Subjective but observable. Note encounters that feel mechanical-only vs encounters that carry narrative weight from prior events.

**Threshold of concern:** If session-20 encounters feel as flat as session-1 encounters, encounter memory is insufficient.

**Architectural implication if observed:** Encounter memory + causality systems become priority. ChatGPT's "the same goblin ambush can feel completely different 40 sessions later" depends on this layer.

### §3.5 Pacing fatigue
**What:** Around session 3-5, does engagement drop because the scenes feel similar even though events differ?

**Capture:** Self-observation. Note when interest wanes vs when it stays high. What was happening at each?

**Threshold of concern:** Early pacing fatigue means surface-level variation is exhausted before systemic depth has accumulated.

**Architectural implication if observed:** Procedural variation systems may help short-term; systemic depth is the long-term fix.

---

## §4. Pacing and content metrics

### §4.1 Session duration before fatigue
**What:** How long can a session run before all participants are fatigued? Distinguish DM fatigue (cognitive load of running) from player fatigue (cognitive load of engaging).

**Capture:** Note hour marks. Watch for energy drops. Note who fatigues first and what they were doing.

**Threshold of concern:** Sub-2-hour sessions limit the surface area available for emergent stories. 2-4 hours is healthy. 4+ is exceptional and valuable.

### §4.2 Content variety pressure
**What:** Does the system reach for tropes (goblins, caves, wagons, taverns, bandits, ruins, crystals) at high rate? Does it produce *un*-tropic encounters when prompted?

**Capture:** Tag generated encounters by archetype. Note frequency of repeat archetypes within a session and across sessions.

**Threshold of concern:** If >50% of encounters fall into the trope cluster, statistical gravity is winning. Per ChatGPT, this is fixable via systemic depth (causality recontextualizes tropes) rather than content generation (which is downstream).

### §4.3 DM-side flow
**What:** When you (Jordan) DM-flag or intervene, does the system absorb your input cleanly or does it fight you? Are the DM-aside surface and slash commands enough?

**Capture:** Note friction points where the DM surface felt insufficient. Note absences — DM tools you reached for that didn't exist.

**Threshold of concern:** Friction here compounds; if DMing is exhausting, sessions can't sustain.

---

## §5. System health metrics (already partially logged)

These exist in journal logs and `world_health:` reporting; playtest is the chance to validate that logged signal matches felt experience.

### §5.1 Hallucination rate (per Ship 2 + future motion-systems work)
- `directive_resolved:` violations (none expected post-Ship-A)
- `phantom_candidates:` — places the bot referenced without canonical row
- `npc_near_match:` — name fragmentation
- Scene state drift (e.g. day_phase mismatches, location flips, time-of-day inconsistencies)

### §5.2 State integrity
- `unconsumed_roll_swept:` — buffer drains expected after Ship A
- `unexpected_binding_co_occurrence:` — Ship 1 canary
- `roll_outcome_drift:` — Ship 1 verifier; expect zero
- `directive_skill_mismatch:` — Ship A wrong-skill aside
- `state_footer:` rendering correctness

### §5.3 Performance
- `prompt_size:` — total chars per turn; watch for 25k+ correlating with empty-narration
- `cloud_router_finish_reason:` — `length` finishes indicate response truncation
- Latency between player input and bot narration

### §5.4 Inference economy (per Gemini's hardware constraint)
- 11GB VRAM ceiling on the 1080 Ti — local Qwen has hard limits
- Cloud calls per turn — extraction parallel calls
- Total inference time per session — sustainability check

---

## §6. Observation discipline

### §6.1 Capture during play
- Discord screenshots of moments that surprised — good or bad
- Note timestamps of friction points; cross-reference journal logs after
- Capture verbatim NPC dialogue that landed well; capture verbatim narration that felt off
- Note the room's energy — when did people lean in, when did they tab out

### §6.2 Capture after play
- Cross-reference timestamps against journal logs
- Tag observations against the metric framework above
- Write a session post-mortem under `tests-to-run-post-session.md` or its own doc
- File specific friction points as ROADMAP candidate items if they suggest a ship

### §6.3 What NOT to do during playtest
- Do not pause to fix bugs mid-session. Note them, keep playing.
- Do not change architecture mid-session based on one moment. Watch for patterns.
- Do not over-tune prompts during play. The current prompt state IS what's being tested.
- Do not invite the system to be perfect. Invite it to be *informative*.

---

## §7. What the playtest evidence writes

After 3-5 sessions, the evidence should answer:

**Combat layer:**
- Does Mode B (standard Avrae init + LLM narration) feel functional in conversational multiplayer?
- If not, which specific metric (§2.1-§2.6) is failing?
- What's the minimum interaction-compression intervention that would fix it?
- Does Mode A (skill challenge for trivial conflicts) earn its keep?

**Motion-systems layer:**
- How fast does the world feel "small" without faction motion?
- What specific causality echoes work, which don't?
- Does NPC continuity hold across sessions?
- Which of the F-54 / motion-systems candidates is most load-bearing first?

**Ship 4/5 MVP-test:**
- Does Finding B (name-resolution drift) actually block play, or is it cosmetic?
- Does Ship 5 polish address observed friction or speculative concerns?
- Should either ship defer entirely?

**Whole-system:**
- Is the project at v1.0 readiness for friends-play?
- What's the highest-leverage single ship to take it from "functional" to "want-to-play-again"?

The answers write the post-playtest spec. The framework above is what produces those answers.

---

## §8. Update cadence

This doc itself is a candidate-state artifact. After the first playtest session, revise based on what actually got observed vs what this framework predicted would matter. The framework should evolve from anticipated friction to observed friction, same discipline that drives the rest of the project.

---

## §9. Cross-references

- `HYBRID_COMBAT_NOTES.md` v3 — long-term combat architecture reference; playtest evidence is the gate for any of its §4-§5 candidates
- `MULTIPLAYER_FIXES.md` v3 §5-§8 — Ships 2-5 scope; Ships 4-5 MVP-test scrutiny per S37 reframe
- `ROADMAP.md` FOOTINGS queue — post-Ship-3 sequence: listener verification → dumb combat → playtest phase → MVP-test 4/5
- `SESSIONS.md` S37 — origin of this framework's metric set (ChatGPT + Gemini external reviews)
- `tests-to-run-post-session.md` — operational test scenarios for ships; this doc complements with metric framework for free-play observation
- `WORKING_WITH_CLAUDE.md` — "evolve from observed friction, not anticipated friction" doctrine governs this framework's evolution
