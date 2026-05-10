# Encounter Cadence Extractor v1 — Spec Proposal

**Status:** DRAFT — Track 5 Ship 1, Phase 1 reconnaissance + taxonomy proposal. No code shipped from this session. Phase 2 (separate session) implements + hand-samples after Jordan locks §6 decisions in chat.

**Companion architecture doc:** `CORPUS_BUILDER.md`

---

## 1. Source data findings

CRD3 lives at `/mnt/virgil_storage/dnd_datasets/crd3/data/aligned data/`.

- **Format.** Per-episode JSON files, one record per wiki-summary alignment chunk. Each record: `CHUNK` (wiki summary text), `ALIGNMENT` (chunk_id, turn_start, turn_end, score), `TURNS` (list of dialogue turns with `NAMES`, `UTTERANCES`, `NUMBER`).
- **Three alignment configs (`c=2`, `c=3`, `c=4`).** These are different chunkings of the SAME episode dialogue, varying only in how the wiki summary is segmented. Verified empirically: turn-level data is byte-identical across configs for the episodes I checked (C1E001, C2E020). **For this extractor, parse `c=2` only** — fewest files (280 vs 530), simpler iteration, no dedup risk.
- **Speaker tagging.** Turn `NAMES` is a list (usually one speaker, occasionally `["ALL"]`). Matt Mercer turns are tagged `MATT` (uppercase). The dataset uses 6 main player tags (`LAURA`, `SAM`, `TRAVIS`, `MARISHA`, `LIAM`, `TALIESIN`) plus C1's `ORION` and `ASHLEY`, and C2's `DEBORAH` (Sam stand-in). Guests appear under their first names. Production crew (`ZAC`, `KEVIN`) and ambient labels (`AUDIENCE MEMBER`, `ALL`) appear in small counts.
- **Granularity.** Turn-level. No timestamps. No within-turn sentence breaks except as line-of-utterance arrays inside a single turn (`UTTERANCES` is a list — speech-recognition segmentation, not semantic). Joining utterances with `' '` reproduces the spoken turn cleanly. Turn `NUMBER` is sequential 0..N within an episode.
- **Episode coverage.** 140 unique episodes total. **C1: 94 episodes** (E001-E115 with gaps — episodes 12, 15, 26, 41, 45, 48, 51, 59, 66-70, 74, 77-84 are missing). **C2: 46 episodes** (E001-E046, continuous). **No C3, no Exandria Unlimited, no one-shots.** The dataset is a 2020 paper artifact — predates much of CR's later content.
- **Importer ground truth.** `dnd_knowledge_import.py` confirms the format. It rebuilds turns by iterating each record's `TURNS` array and pulling `NAMES[0]` + `UTTERANCES`, then filters to `MATT` for ChromaDB storage. Same access pattern this extractor uses.
- **Episode-level turn counts.** Sample range: 1500-3700 turns/episode. MATT's share runs ~30% of turns by count, but ~50%+ of meaningful narration (most non-MATT turns are short banter).

**One-liner:** CRD3 is a flat file-per-episode JSON corpus with `MATT`-labeled DM turns, no timestamps, dialogue numbered sequentially per episode. Suitable for cadence work as `CORPUS_BUILDER.md` claimed.

---

## 2. Sample observations (6 episodes)

Sampled across phases:
- **C1E001** (pilot — character intros, late-episode combat)
- **C1E020** (early-mid C1 — assassin chase scene)
- **C1E030** (Halloween / Whitestone — vampire spawn ambush)
- **C1E049** (mid C1 — orc camp + sphinx trial)
- **C1E095** (late C1 — "Daring Days" downtime montage, **0 combat starts**)
- **C2E020** (mid C2 — cart-travel episode, legion sighting)
- **C2E045** (late C2 — dragon encounter)

Method: pulled all MATT turns containing `\binitiative\b`, plus 3-4 turns of preceding context per hit. Then human-classified as fresh-start vs mid-combat noise.

### Raw observations (one quote per observation, edited to fit)

**O1. C1E030 turn 379 — fog ambush.** Players resting in tunnel; Matt narrates temperature dropping over ~16 turns; fog forms; turns humanoid. `"the fog begins to form into a physical humanoid essence and reach out for you. For the three that are conscious, roll initiative."` Telegraph: SOFT/LONG. Player agency: zero — purely DM-initiated.

**O2. C1E030 turn 517 — vampire reinforcement.** Mid-combat. Combat already underway with awake party; Matt narrates a strike, then `"the people who just woke up, roll initiative."` This is a NEW init roll for newly-entering combatants but the encounter itself is ONGOING. Pacing-relevant but architecturally distinct from a fresh start.

**O3. C1E049 turn 535 — failed-stealth escalation.** Sam (gnome) tries to bowling-ball past orcs in a Resilient Sphere while singing. Matt: `"Stupid gnome!"` then `"Initiative has now kicked in; I need everyone to roll initiative."` Telegraph: DURING. Player agency: HIGH (their action caused it).

**O4. C1E049 turn 2434 — sphinx trial.** Players walk into a chamber where a creature mounts a platform, delivers a speech (`"You, you seek power, glory, retribution... You must be proven. It must be earned."`), then `"Roll initiative."` Telegraph: HARD via NPC dialogue. Player agency: location-based (chose to enter).

**O5. C2E045 turn 2014 — trap activation.** Players investigating cabinet, stick hands in. Matt: `"it immediately closes on your arms as teeth suddenly emerge from the sides of the door"` — attack rolls happen pre-init, then `"All right, I need you guys to roll initiative."` Telegraph: HARD/INSTANT.

**O6. C2E045 turn 2529 — boss reveal turning hostile.** Travis is solo with an NPC the party knew; rest of party falls in through ceiling; dragon is revealed and `"the dragon rears up, caught off guard, wings up in the air."` Then `"Well, let's roll initiative first."` Telegraph: SOFT (long social setup) → HARD pivot. NPC was in scene; combat fired when scene shifted.

**O7. C1E020 turn 986 — botched stealth turning into combat.** Player polymorphs to cast Silence at a fleeing target; spell fails; `"I'm going to have you guys roll initiative."` Telegraph: DURING. Same shape as O3.

**O8. C1E020 turn 993 — interruption during search.** Players searching a body after the chase. `"as you guys are searching the body you hear all of a sudden the sound of some sort of scuffle, a flash of some sort of arcane energy, you all feel the energy from a magical effect of some sort discharge nearby."` Then init. Telegraph: SHORT. Players were doing a non-combat task; new threat arrived.

**O9. C2E020 turn 233 — legion sighting (NOT combat).** Players traveling; Matt narrates `"What was a dark shadow appears to be hundreds and hundreds of soldiers, an army regiment that is shifting from the northwestern side of the Empire... you may intersect with their path if you continue, or you can slow down or speed up. It's your choice."` Pressure event. World-event. Never escalates to combat; pure pacing/atmosphere. **Not init-anchored.**

**O10. C1E001 turn 1573 — environmental ambush via NPC casting.** Goblin scene; vines emerge from a tunnel and grab goblins. `"these strange reddish vines begin to protrude and to begin to grab nearby goblins and pull them up... Everyone roll initiative."` Telegraph: HARD via narrated emergence.

### Filter-discipline observations

- **`\binitiative\b` raw count is high-noise.** Across the 7 sampled episodes, MATT turns mention "initiative" 35 times. Hand-classified, ~12 are fresh starts; the rest are mid-combat order references (`"top of the initiative round"`, `"next in the initiative order"`, `"changed his initiative"`, `"in the initiative order"`, `"You're already in initiative"`, etc.). A naive grep over-counts by ~3x.
- **Filter that worked in recon.** Require a "fresh start" pattern (`roll initiative`, `initiative kicked in`, `need (everyone|you|all) to roll`) AND exclude a "mid-combat" pattern (`initiative order`, `next in the initiative`, `top of the initiative`, `currently in initiative`, `still in initiative`, `out of initiative`, `change(d) (his|her|their) initiative`). On the 7 samples this yielded 12 fresh starts vs 35 raw hits — a tractable hit rate for hand-validation.
- **C1E095 is real.** A genuine episode with zero combat starts. Downtime montage. The extractor must accept zero records as valid output for some episodes.
- **OOC contamination is heavy at episode boundaries.** First 30+ MATT turns of C1E001 are pure announcements (mic checks, sponsor reads, Stream of Many Eyes promo). C2E020 also has a long announcement block. These never trigger init, so they don't directly false-positive — but they affect `episode_position_pct` if not stripped.
- **First-encounter timing varies wildly.** Across the samples: C1E049 first init at 15% into the episode; C1E001 first init at 73% (long character-intro lead-in). Not a normal distribution; depends entirely on episode shape.
- **Init recurrence within an episode.** When init fires, it often fires AGAIN within tens of turns (waves, second encounter same scene). Encounter-as-event cardinality requires a within-episode dedup heuristic.

---

## 3. Proposed trigger taxonomy

Five categories. None match the illustrative ones in `CORPUS_BUILDER.md` ("environmental_ambush" etc.) — those were named before observation; mine are derived from samples §2.

### 3.1 `player_action_escalation`
**Definition.** Player declares an action that causes hostility — failed stealth, declared violence, social-fail with a hostile NPC. Combat fires AS the player's action resolves.
**Examples.**
- O3 (C1E049-535) — Sam's stealth fails, orcs notice, init.
- O7 (C1E020-986) — Polymorph→Silence on a fleeing NPC, NPC reacts, init.
**Signals.** A non-MATT turn immediately precedes the trigger (player declared action). Trigger text often contains `"kicked in"`, `"because you"`, or narrates the action's failure.

### 3.2 `environmental_materialization`
**Definition.** A scene element (mist, fog, growing sound, temperature shift, geological change) is described over multiple turns, then resolves into a hostile entity or effect.
**Examples.**
- O1 (C1E030-379) — Fog → humanoid.
- O10 (C1E001-1573) — Vines emerge from tunnel.
**Signals.** Long preceding MATT-narration block (often >300 chars across multiple turns). Trigger text contains physical-emergence verbs (`form into`, `emerge`, `materialize`, `coalesce`, `take shape`, `crystallize`). No direct player-action precursor.

### 3.3 `trap_activation`
**Definition.** A player physically interacts with an environmental object (chest, door, lever, body, ground) that springs a hostile mechanism. Often: attack rolls or damage land BEFORE init is called.
**Examples.**
- O5 (C2E045-2014) — Cabinet teeth.
**Signals.** Player turn declares interaction (`"open"`, `"reach in"`, `"grab"`, `"step on"`, `"touch"`). Trigger text contains mechanism vocabulary (`teeth emerge`, `pressure plate`, `springs`, `releases`, `slams shut`). Damage rolls in the trigger turn or the immediately-preceding MATT turn.

### 3.4 `npc_turns_hostile`
**Definition.** An NPC who is in dialogue with the party (or finishing a speech) becomes hostile. Includes predetermined dungeon-trial encounters where an NPC speaks then attacks.
**Examples.**
- O4 (C1E049-2434) — Sphinx trial speech → init.
- O6 (C2E045-2529) — Dragon-aligned NPC reveals dragon, scene pivots to combat.
**Signals.** Direct NPC dialogue (in-character voice from MATT — quoted text, NPC-naming) in turns immediately preceding the trigger. Trigger text often pivots with `"then"`, `"as you finish"`, `"with that"`, or starts mid-sentence after dialogue. Dialogue may end with a threat, ultimatum, or motion-cue.

### 3.5 `interruption`
**Definition.** Players are doing something non-combat (resting, traveling, searching, talking among themselves) when an unrelated threat arrives or an off-screen event becomes on-screen.
**Examples.**
- O8 (C1E020-993) — Players searching body, scuffle/arcane discharge nearby.
**Signals.** Preceding turns are player-to-player chatter or low-stakes activity (`"searching"`, `"resting"`, `"walking"`). Trigger text contains arrival vocabulary (`"you hear"`, `"you see"`, `"suddenly"`, `"a sound"`, `"in the distance"`). No player-action causal link.

### 3.6 `wave_or_phase_shift` (mid-combat sub-event)
**Definition.** Encounter is already underway; a NEW init call happens because (a) new combatants are entering (sleeping party wakes, reinforcements arrive, party member falls in from another scene) or (b) the existing scene re-rolls due to phase change.
**Examples.**
- O2 (C1E030-517) — Sleeping party wakes mid-fight.
- C1E049-2812 — Time-flux room forces full reroll.
- C2E045-2678 — Party members fall through ceiling into ongoing dragon fight.
**Signals.** Trigger text refers to `"reroll"`, `"now in initiative"`, `"the people who just woke"`, `"you who just landed"`, or a subset of party (`"both of you"`, `"the three of you"`) rather than `"everyone"`. Often paired with mid-combat narration in the same turn.

**Note on category 3.6.** Not a "new encounter" by hand-validation. Including it because it's clearly a pacing event and the extractor will see it. Tag separately so analysis can include or exclude it. See §6.6.

---

## 4. Considered and rejected categories

- **`scheduled_event`** (pre-arranged ambush/trial). Rejected. Indistinguishable from §3.2 / §3.4 by text alone — Matt's prep notes aren't in the corpus. Whether the encounter was on the DM's pre-session list vs improvised is invisible to the extractor.
- **`combat_continuation`** (ongoing fight, no init re-roll). Rejected — it's the **absence** of an event, not an event. Out of scope.
- **`social_pressure_only`** (NPC threat that never escalates to combat). Rejected for v1. No init anchor → no deterministic textual signal that's shared across instances. The "encounter" the extractor catches is the init-anchored one. Filed for a future `narrative_pressure_v1` extractor (see §7).
- **`world_event_sighting`** (e.g., O9 — legion seen on travel). Rejected for v1, same reason as above. Filed for the queue.
- **`time_pressure_introduction`**. Belongs to the Time-Mention extractor (already on the queue, item #2). Don't poach scope.
- **`npc_attacks_no_init`** (one-off attack roll without formal init — e.g., a thrown javelin from a distant scout). Rejected for v1. Hard to distinguish from in-combat attacks in a corpus where Matt sometimes describes attacks before init is called (see O5).
- **`environment_changes_threatening`** (room fills with water, walls close in). Rejected — usually fires as a pure environmental hazard with saving throws, not init. No deterministic anchor.
- **`fail-forward initiative` (re-init after long-rest interruption)**. Folded into §3.5 `interruption`.

---

## 5. Pattern-matching strategy (high level)

No code in this session. Sketch only — implementation comes in Phase 2.

**Stage 1 — Candidate extraction.** Iterate `c=2` JSON files. Build per-episode turn list keyed by `NUMBER` (rebuild because chunks repeat turn entries). Filter to `MATT` turns. Match each MATT turn against a "fresh init" regex set (positive patterns: `roll initiative`, `initiative (has |now |)kicked in`, `need (everyone|you|you guys|all|everybody) (to (go ahead and )?(roll|reroll|to roll))`). EXCLUDE turns matching the "mid-combat" regex set (`initiative order`, `next in the initiative`, `top of the initiative`, `(currently|still) in initiative`, `out of initiative`, `change(d) (his|her|their) initiative`).

**Stage 2 — Per-candidate classification.** For each surviving trigger turn, look at the preceding MATT turns and the immediately-preceding non-MATT turn (the player provocation, if any). Classify into §3.1-3.6 by checking for category-specific patterns in this window. Multi-category matches go to the highest-priority category by rule (proposed priority order: `wave_or_phase_shift` → `trap_activation` → `npc_turns_hostile` → `player_action_escalation` → `environmental_materialization` → `interruption`; rationale: more-specific signals win when present).

**Stage 3 — Output one record per fresh start.** Required fields per `CORPUS_BUILDER.md` §Output Format Contract, plus extractor-specific:
```json
{
  "trigger_category": "<one of §3.1-3.6>",
  "preceding_player_turn": "<text or null>",
  "preceding_matt_context": "<concatenated last N MATT turns>",
  "telegraph": "<hard|soft|during>",
  "is_fresh_encounter": true|false
}
```
- `is_fresh_encounter=false` only for §3.6 `wave_or_phase_shift`. Default true.
- `telegraph` is a coarse label derived from preceding-context length: <100 chars MATT-narration in last 4 turns = `during`; 100-500 chars = `hard`; >500 chars = `soft`.

**Hand-sample target.** Run on 10 episodes spanning C1 early/mid/late + C2 mid/late. Expected yield: ~30-60 records. Hand-validate all per `CORPUS_BUILDER.md` §Hand-Sample Validation Protocol.

**Out-of-scope for v1 implementation.** OOC stripping at episode boundaries (announcements never trigger init, so they don't contaminate; only affects `episode_position_pct`). Multi-stage encounter dedup. Inter-episode encounter linking. Source filter beyond MATT/non-MATT.

---

## 6. §6 decisions needing Jordan's lock

Same shape as `COMBAT_INITIATION_ORCHESTRATION_REVIEW.md` §11. Restate, trade-offs, recommended default, confidence.

### §6.1 — Encounter scope: combat-only, or include pressure events without init?

**Restate.** Does v1 cover ONLY init-anchored events (categories §3.1-3.6), or also non-combat pressure (legion sighting, environmental challenge that never escalates, NPC encounter without combat, dream/vision)?

**Trade-offs.**
- **Combat-only (proposed).** `\binitiative\b` is a hard textual anchor. Deterministic regex viable. Hand-validation is tractable (~12 fresh starts per 7 episodes = ~250 across CRD3). Misses ~half the "encounter-feeling" events in low-combat episodes (e.g., C2E020 has lots of pacing events but only 1 init).
- **Broader scope.** Catches more research signal. But: no shared textual anchor. Each pressure type needs its own regex set, each gets its own false-positive risk. Hand-validation explodes (recall check across categories that don't share a signal). Effectively becomes 3-5 ships in one — violates the single-category rule in `CORPUS_BUILDER.md` §Extractor Design Constraints (#5).

**Recommended default.** **Combat-only.** Cites Design Constraint #5 (single-category per extractor) and Design Constraint #1 (deterministic only — broader scope wants soft signals that resist regex). Filed for follow-up: §3.5-style `narrative_pressure_v1` becomes its own ship after Time-Mention runs (queue item #2 partially overlaps).

**Confidence.** **HIGH.** The single-category rule is doctrinal. Scope creep here turns Phase 2 into a multi-week build.

---

### §6.2 — Source filter: pure MATT turns, or include MATT-following-player-turn?

**Restate.** When extracting context for a candidate trigger, do we look only at MATT turns (per `dnd_knowledge_import.py`'s import filter) or do we also retain the player-turn that immediately preceded the trigger (because §3.1 player_action_escalation NEEDS the player's declared action to classify)?

**Trade-offs.**
- **MATT-only.** Simplest. Matches existing import. Loses the player-action signal that distinguishes §3.1 from §3.2.
- **MATT + last non-MATT before trigger.** One extra turn read per candidate. Lets §3.1 classification work. The "last non-MATT" turn may be banter rather than action, but then §3.1's other signals (fresh-start regex post-banter) fail anyway.
- **Full window of all preceding turns regardless of speaker.** Most data. Most noise. Banter contamination.

**Recommended default.** **MATT + last non-MATT turn before each trigger candidate.** Cited as `preceding_player_turn` in the output schema. Player-action signal is load-bearing for §3.1 vs §3.2. The extractor remains MATT-anchored (the trigger turn is always MATT) but doesn't ignore the immediate causal predecessor.

**Confidence.** **MEDIUM.** Possible Phase-2 finding: the "last non-MATT turn" is often brief banter, not action. If so, retreat to MATT-only and merge §3.1 into §3.2. File the trigger: if hand-sample shows `preceding_player_turn` is action-bearing in <40% of §3.1 candidates, collapse the categories.

---

### §6.3 — Boundary for "fresh start" (mid-combat init filtering)

**Restate.** A naive `\binitiative\b` filter over-counts ~3x because mid-combat references (`top of the initiative round`, `your initiative is X`) pollute. The hand-recon used a positive+negative regex pair. What's the lock for v1?

**Trade-offs.**
- **Recon-derived rule (proposed).** Positive pattern: `roll initiative | initiative kicked in | need (everyone|you|all) to (go ahead and )?(roll|reroll)`. Negative pattern: `(initiative order | next in (the )?initiative | top of (the )?initiative | (currently|still) in initiative | out of initiative | change(d) (his|her|their) initiative)`. Hits 12/35 raw on the recon set.
- **Stricter.** Require `roll initiative` literal. Drops borderline cases like `initiative kicked in` (O3) and `everyone roll`. False negatives on real triggers.
- **State-tracking.** Track within-episode whether init is already active (saw `roll initiative` recently → next init is wave/phase, not fresh). Requires per-episode state; fragile across long encounters where init genuinely re-fires.

**Recommended default.** **Recon-derived rule.** Tag §3.6 wave/phase events using the negative-set patterns AND nearby positive-set hit (i.e., a re-roll inside an active fight). Treat state-tracking as a Phase-3 refinement only if hand-sample shows §3.6 is mis-tagged.

**Confidence.** **MEDIUM.** Recon ran on 7 episodes. The patterns may have idiosyncrasies the broader corpus doesn't share. Phase 2's hand-sample IS the calibration — recall the rule against actual hits.

---

### §6.4 — Preceding-context window: char budget, turn budget, both?

**Restate.** `CORPUS_BUILDER.md` §Output Format Contract names `preceding_context_chars` as a required field. What value, and is it a budget cap or a budget hint?

**Trade-offs.**
- **Char budget = 1500 (proposed).** Matches what recon used; captures ~10-15 turns of context typically. Long enough to see the build-up for §3.2 (environmental_materialization can ramp over 16+ turns). Short enough to keep records human-readable.
- **Turn budget = 8.** Cleaner stop condition. But turn lengths vary wildly (one MATT turn can be 2000+ chars; one banter turn can be 5 chars). Char budget gives more consistent context size.
- **Both (char OR turn cap, whichever fires first).** Belt-and-suspenders. Adds field complexity.

**Recommended default.** **Char budget = 1500, applied to ALL preceding turns regardless of speaker.** The schema field becomes `preceding_context_chars: 1500` (the budget, fixed across records) with the actual concatenated context stored in `preceding_matt_context` and `preceding_player_turn`. The extractor walks back from the trigger turn until the char budget is exceeded.

**Confidence.** **MEDIUM.** 1500 is a recon-derived guess. Phase 2 hand-sample shows whether 1500 catches the §3.2 build-up consistently. Bumping to 2500 is cheap if needed; record schema doesn't change, just the extractor's walk-back loop.

---

### §6.5 — OOC chatter and announcement contamination at episode boundaries

**Restate.** First 30+ MATT turns of episodes are typically OOC: mic checks, sponsor reads, Stream of Many Eyes plugs, sponsor breaks. These never trigger init — but they do affect `episode_position_pct` (the trigger at turn 1573 of 2160 in C1E001 becomes 73% with OOC included, ~78% if first 100 OOC turns stripped). Do we strip OOC, or accept the noise?

**Trade-offs.**
- **No strip (proposed).** Simplest. `episode_position_pct = trigger_turn_index / total_turns`. 5-10% noise per episode but consistent — same fraction is OOC across episodes, so cross-episode comparison stays valid.
- **Strip via heuristic.** Drop all turns before the first MATT turn containing canonical session-start phrases (`Welcome back`, `our last episode left off`, `we left off with`, `as we begin tonight's episode`, `let's pick up where we left off`). Adds a fragile rule that may misfire on episodes that open mid-scene.
- **Strip via length heuristic.** Drop initial MATT turns shorter than X chars or matching announcement keywords (`patreon`, `stream of many eyes`, `sponsor`, etc.). More fragile, more rules.

**Recommended default.** **No strip for v1.** Matches Design Constraint #1 (deterministic, simple). Document the noise in findings. If post-parse the noise turns out to be load-bearing for any analysis Jordan does, ship a separate `episode_boundary_extractor` to mark where the play-game starts, and join its output downstream.

**Confidence.** **HIGH.** Premature optimization. The numerator (first encounter turn index) doesn't move when OOC is included; only the denominator-relative percentage shifts. Either Jordan can mentally adjust, or a Phase-3 ship adds the boundary marker.

---

### §6.6 — Wave/phase events: tag separately, exclude, or merge with fresh starts?

**Restate.** §3.6 is structurally different from §3.1-3.5 — it's an in-combat event, not an encounter start. Some research questions want it counted ("how often does Matt re-init mid-fight?"); others want it excluded ("how many encounters does an episode have?"). What's the v1 default in the output?

**Trade-offs.**
- **Emit, tag with `is_fresh_encounter: false` (proposed).** Both questions answerable from the same output by filtering on the field. Costs one extra field per record. Doesn't muddy fresh-start statistics if downstream filters on the field.
- **Emit, no fresh/wave distinction.** Simplest schema. Forces every analysis to pre-classify by re-reading raw text. Defeats the point of the extractor.
- **Don't emit at all.** Loses real signal. The "Matt re-rolls init mid-fight" pattern is rare-but-meaningful (saw it once in C1E049 — time-flux phase change).

**Recommended default.** **Emit with `is_fresh_encounter: false` flag.** Field is binary. `trigger_category=wave_or_phase_shift` ⇔ `is_fresh_encounter=false` for v1; the redundancy is intentional (allows future categories to also be wave-flagged if needed).

**Confidence.** **HIGH.** Same shape as the rest of CORPUS_BUILDER's output discipline (versioned, classification-rich, downstream-filterable).

---

### §6.7 — Within-episode dedup window for back-to-back init calls

**Restate.** Sometimes Matt calls init twice within ~10 turns (recon saw this in C1E020 turns 986+993 — chase scene resolved into init, then within minutes a second scuffle triggered another init). Are these (a) two encounters, (b) one encounter with a wave, (c) ambiguous?

**Trade-offs.**
- **No dedup (proposed).** Each fresh-start trigger emits a record. Both 986 and 993 are §3.5 `interruption` (or §3.1) records. Downstream analysis can dedup by turn-distance threshold if it cares.
- **Dedup at extractor.** Within N-turn window, treat as one encounter; re-init becomes a wave. Couples extractor output to a within-episode threshold that may not generalize.

**Recommended default.** **No dedup.** Cites Design Constraint #5 and the Output Format Contract's "minimal post-processing" intent. Two close inits = two records. If downstream wants to cluster them, that's a separate analysis pass.

**Confidence.** **HIGH.** Dedup is a downstream concern. The extractor's job is faithful event extraction.

---

## 7. Open questions

1. **§3.4 NPC dialogue detection without quote marks.** Matt sometimes voices NPCs without quotes (`He goes, "I appreciate the offer..."`) and sometimes without any quote marks at all. Detection of "this is NPC speech" via regex is medium-risk. Phase 2 hand-sample will tell us how lossy quote-stripped detection is. If it's bad, fall back to "any preceding MATT turn is dialogue-eligible context" and let the category overlap.

2. **C1 vs C2 stylistic drift.** Six years of Matt-DM evolution between C1 episode 1 and C2 episode 46. Did his init-call phrasing change? Recon didn't measure this; Phase 2 hand-sample should report category distribution split C1 vs C2 to surface drift.

3. **`extractor_version` discipline for taxonomy.** If Jordan locks §3.x then Phase 2 hand-sample reveals a category needs splitting (or merging), do we bump `encounter_cadence_v1` → `v2` post-hand-sample-pre-full-parse? Per `CORPUS_BUILDER.md` §Extractor Design Constraints (#6), yes — bump on classification-logic change. v1 in this spec means "the schema and categories that survive Phase 2 hand-sample," not "first text I write in Phase 2." Confirm this interpretation.

4. **What's the FIREBALL relevance for this extractor?** None per `CORPUS_BUILDER.md` §Source corpora — FIREBALL is single-turn snapshots, no multi-turn cadence. v1 declares CRD3-only in its findings. Confirming I read this correctly — Track 5 doesn't run this against FIREBALL even if it could.

5. **Findings doc placement.** `CORPUS_BUILDER.md` says findings live at `findings/{extractor_name}_findings.md`. Does the validation doc (`findings/{extractor_name}_validation.md` per the Hand-Sample Validation Protocol) survive past Phase 2, or is it merged into the findings doc after the full parse? Probably separate: validation = "did the extractor work?", findings = "what did the data say?". Confirming.

6. **Jordan-validation episode list.** Phase 2 hand-sample protocol calls for 10 episodes spanning phases. Proposed list: C1E001, C1E020, C1E030, C1E049, C1E060 (zero-init episode for false-positive check), C1E095 (zero-init downtime episode), C2E001, C2E020, C2E030, C2E045. Adjust if Jordan has known-difficult episodes in mind.

---

## Decisions for Jordan to lock in chat (Phase 2 starts after this)

§6.1 scope · §6.2 source filter · §6.3 fresh-start regex · §6.4 context window · §6.5 OOC handling · §6.6 wave-event tagging · §6.7 dedup. Plus answers to §7.3 / §7.4 / §7.5 / §7.6.

Phase 2 ships: extractor at `corpus_builder/extractors/encounter_cadence.py`, hand-sample at `corpus_builder/samples/encounter_cadence_sample.json`, validation report at `corpus_builder/findings/encounter_cadence_validation.md`. Full-parse only after Jordan signs off the validation report.
