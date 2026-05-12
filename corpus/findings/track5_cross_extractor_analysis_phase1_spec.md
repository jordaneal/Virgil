# Cross-Extractor Analysis — Phase 1 Spec

**Ship:** Track 5, Ship 5 (analysis pipeline, not a new extractor) — Cross-Extractor Analysis
**Phase:** 1 (recon + framework proposal)
**Author:** Phase 1 recon, May 2026
**Locks pending:** §13 decisions, resolved in chat before Phase 2 opens

---

## §1. Mission

This is **not** a new extractor. It is an analysis pipeline that joins the four shipped Track 5 extractors' record sets (Encounter Cadence, Time-Mention, Loot/Reward, Compression Cadence) to answer research questions that single-extractor architecture cannot reach.

Each of the four prior ships ended with §9 Open Questions deferring specific findings to "cross-extractor analysis." Inventorying those deferred questions across the four findings docs produces a structured set of join-dependent claims about Matt's DM cadence that no single extractor's records carry alone.

**Deferred questions inventoried from prior ships:**

From Encounter Cadence (§8 + post-ship spot-checks):
- EC-X1: Wave-detection precision under cross-episode-window causality — initial combat 50+ turns earlier than current init call
- EC-X2: Player-action causality detection across 15-25 turn windows rather than 5-10 (the `interruption` catchall inflation is partly a window-size problem)

From Time-Mention (§9 + §8):
- TM-X1: `is_combat_state` widening via EC join — currently fires on only 0.3% of corpus records vs. real combat-state frequency much higher
- TM-X2: `scene_transition` as cross-extractor scene-boundary primary signal — joins to LR Q4, CC Q4, CC Q1

From Loot/Reward (§9):
- LR-X1: Q4 full buildup cadence — what fraction of rewards follow a perception/investigation check at any distance, not just within 8 turns
- LR-X2: Q6 absence rate — buildup with no payoff, requires encounter_cadence escalation join
- LR-X3: Offer/delivery pairing — were QUEST_OFFER records eventually fulfilled by later `delivered`-direction records (cross-episode join)
- LR-X4: Currency magnitude distribution by episode-position and campaign

From Compression Cadence (§9):
- CC-X1: Q4 full scene-opening classification — what kind of context opens the next scene after compression
- CC-X2: Q1 unified scene-count denominator — total scene boundaries per episode = EC inits + CC compressions + TM scene_transitions (deduped)
- CC-X3: Q6 negative-signal stale-hold — zero-compression episodes correlated with high-tension content (C1E114 as canonical)
- CC-X4: Category-mix shift across campaigns — which categories drive the C2 39% density delta over C1

**Boundary discipline.**

**IS:** Joins, aggregations, and cross-references over the four extractors' shipped record sets. Read-only access to those record sets; no new extraction. Output is analysis findings doc(s), tables, and per-episode merged event-stream files.

**IS NOT:**
- A new extractor. No new categories, no new trigger detection, no new regex.
- A retrospective fix for any single extractor's known bugs. CC's D5/D7 vocabulary gaps, EC's `interruption` catchall, TM's `is_combat_state` under-detection are not addressed by patching the source extractors — they're addressed by the cross-extractor pipeline producing the corrected signal as a derived field.
- A replacement for any single extractor's findings doc. Single-extractor findings remain authoritative for their domain; cross-extractor findings address the cross-cutting questions.

---

## §2. Source data — the four extractor outputs

This ship reads from four shipped record sets. Each is on the server; PC mirrors may be partial.

| Source | Records | Episodes | Path (server) |
|---|---:|---:|---|
| Encounter Cadence v1.3 | 170 | 140 | `corpus_builder/output/encounter_cadence/` |
| Time-Mention v1.3 | 3,592 | 140 | `corpus_builder/output/time_mention/` |
| Loot/Reward v1 (Phase 3.6) | 474 | 123 | `corpus_builder/output/loot_reward/full_v36/` |
| Compression Cadence v1p4 | 365 | 123 | `corpus_builder/output/compression_cadence_corpus_v1p4.json` |
| **Combined record total** | **4,601** | | |

**Episode coverage asymmetry.**
- EC and TM parsed all 140 unique CRD3 c=2 episodes (no exclusions; their eval sets came from the same 140-episode pool).
- LR and CC parsed 123 episodes each: the full 140 minus their respective hand-sample and recon episodes (LR: 10 hand-sample + 7 recon = 17 excluded; CC: 10 hand-sample + 7 recon = 17 excluded). The 17 excluded per ship overlap partially.
- Cross-extractor joins must handle this asymmetry: either restrict to the intersection (~106 episodes parsed by all four — needs precise count) or analyze per-pair at the pair's intersection.

**Schema deltas — confirmed.** All four extractors carry per-record fields for episode identity, turn position, and episode-percent position, but field naming and value shape differ:

| Field semantic | EC / TM / LR | CC |
|---|---|---|
| Episode identity | `campaign` (str: "C1", "C2") + `episode` (int) split | `episode` (str: "C1E001", combined) |
| Turn number | dedicated int field (e.g. `init_turn_number`, `trigger_turn_number`) | `trigger_id` (str: "C1E001_t152", parse turn from suffix) |
| Episode-percent position | `episode_position_pct` (float) | `episode_position_pct` (float, consistent) |

Phase 2 starts with a schema-normalization pass producing a unified record set. Required CC-specific steps:
1. Parse `trigger_id` (str) to extract integer turn number from the `_t{N}` suffix.
2. Split CC's `episode` (combined str) into `campaign` + `episode_int` to match the EC/TM/LR shape.
3. Emit normalized records with unified `(campaign, episode_int, turn_number, episode_position_pct, source, category, payload)` columns.

The normalization is non-trivial but bounded — three transformations on CC, identity-pass on the other three (modulo any field-naming differences between EC/TM/LR which Phase 2 verifies on first read). Phase 2 should not modify source records; the unified record set is a derived artifact.

**Source corpus c=2 asymmetry.** Same constraint as prior ships. All four sources read CRD3 c=2 alignment only; cross-extractor pipeline inherits this constraint, not a deviation from it.

---

## §3. Recon

Five questions sampled across the four-source product, with hand-traces of what the join would look like.

### R1. Episode-level event-stream view (CC-X2, EC-X1, TM-X2)

Pick one episode (recon proposal: C2E020 — appears across all four extractor eval sets, mid-corpus pacing, both combat and non-combat content) and merge all four extractors' records into a single sorted-by-turn-number event stream.

**Expected stream shape:**

```
C2E020  turn 152  TM   scene_transition       morning watch concluded
C2E020  turn 209  CC   OVERNIGHT_REST         diurnal transition
C2E020  turn 233  EC   pressure_world_event   legion sighting (non-combat)
C2E020  turn 577  CC   OVERNIGHT_REST         (defensible-judged)
C2E020  turn 660  TM   in_scene_compression   "next hour"
C2E020  turn 763  LR   QUEST_OFFER            NPC commission
...
```

Recon question: how dense is the per-episode event stream? If a typical episode has ~20–40 events across the four extractors and they cluster temporally (multiple events within 5-10 turns), proximity joins produce rich signal. If events are sparse and uniformly distributed, proximity joins are thin.

**Hypothesis.** Most episodes will have 20-40 cross-extractor events. Clusters will occur at scene boundaries (CC scene-exit + TM scene_transition + EC init or LR loot all within 10 turns). Quiet episodes (C1E095 "Daring Days" downtime, C1E114 finale) will be uniformly distributed with no cluster structure.

### R2. Compression → next-scene-opening join (CC-X1)

For each CC record with `compression_scope=scene_exit` (304 of 365 records), find the next Matt-narrated turn that opens a new scene-state, then classify the opening shape.

**Classification candidate buckets:**
- player_declaration — PC turn declares party action, Matt's next narration responds
- npc_arrival — Matt narrates an NPC entering or speaking first
- environmental_description — Matt narrates location/atmosphere first
- matt_narrated_frame_set — Matt sets the scene before player input

**Detection mechanism (Phase 2 candidate).** Walk forward from CC record's `trigger_turn_number` until the next Matt turn that doesn't share narrative continuity with the prior scene. Continuity detection: tokens like "still", "you continue", "the same"; gap detection: scene-resetting tokens like "you find yourselves", "as you arrive", new NPC name introductions.

**Recon question:** Is "next Matt turn after a CC scene-exit" the right detection anchor? Or does cross-extractor signal (next TM scene_transition record, next EC init record) give better grounding?

### R3. Reward-after-buildup cadence at arbitrary distance (LR-X1)

For each LR record, find the preceding EC perception/investigation buildup event (if any) within an extended window. EC's records carry buildup-related signals (`buildup_signal` field via the immediately-preceding turn); cross-extractor join would extend this to LR's full preceding window.

**Recon question:** What window size makes sense? LR's `has_perception_buildup` field uses ~8 turns (7.4% positive rate). EC's causality window is 15-25 turns. TM's scene_transition signals could be used as scene-boundary anchors to allow window-extending only within the same scene (don't count perception-checks from a prior scene as buildup for a later reward).

**Hypothesis.** Buildup-at-arbitrary-distance-within-same-scene will produce a significantly higher rate than LR's 7.4%, possibly 15-25%. The order of magnitude matters for Track 4 design.

### R4. Zero-compression episode tension profile (CC-X3)

14 episodes produce zero CC records (13 pool + C1E114). For each, compute:
- EC init count (high tension → frequent inits expected)
- TM scene_transition count (low → scenes held open expected)
- LR record count (high → reward delivery active expected)
- Episode position of any LR records (clustered late → climactic-finale shape)

**Recon question:** Does the C1E114 pattern (high EC inits, low TM scene_transitions, high LR density clustered late) generalize to the other 13 zero-compression episodes? If yes, the cross-extractor signal validates the spec §8 Finding 1 ("Matt holds scenes open through climactic finales") at corpus scale. If no, the 14 zero-compression episodes are heterogeneous and the negative-signal Q6 surface is noisier than the single canonical example suggested.

### R5. Quest offer → delivery cross-episode join (LR-X3)

121 LR QUEST_OFFER records have `direction=offered`. For each, search later episodes for `direction=delivered` LR records that share the offer's currency-magnitude or NPC reference.

**Recon question:** What's the join key? Currency magnitude is brittle (Matt may not narrate exact amounts at delivery). NPC name is more robust but requires NER on the offer/delivery records, which is out of scope for a regex-deterministic pipeline.

**Likely outcome.** This question may require LLM-assisted matching at the join step, deviating from the no-LLM-in-execution-path constraint of prior ships. If so, this is a deliberate scope expansion for this ship and must be locked at §13.

---

## §4. Proposed join taxonomy

Four join types, ranked by complexity:

### 4.1 Sequential (same-episode, time-ordered)

Merge records from N sources by episode + turn_number into a unified time-ordered event stream per episode. No matching logic — just sort and emit.

**Use cases:** R1 (event-stream view), exploratory analysis, per-episode dashboards.
**Complexity:** Low. Pure data transform.
**Output shape:** Per-episode JSON files in `cross_extractor_streams/{episode}.json`.

### 4.2 Proximity (same-episode, windowed)

For each record in source A, find the nearest record in source B within an N-turn window in the same episode. N is the join's free parameter.

**Use cases:** LR-X1 (reward after perception buildup at extended window), CC-X1 (compression before next scene opening), TM-X1 (TM record near EC init for `is_combat_state` correction).
**Complexity:** Medium. Need windowing logic + scene-boundary handling to avoid cross-scene matches.
**Output shape:** Joined record tables; can be derived columns on existing record sets.

### 4.3 Count-based (per-episode aggregates)

Aggregate records per source per episode into a per-episode count vector; correlate or analyze cross-extractor count patterns.

**Use cases:** CC-X3 (zero-compression episode tension profiling), CC-X2 (unified scene-count), per-episode density correlations.
**Complexity:** Low–medium. Aggregate + join + analyze.
**Output shape:** Per-episode summary table with one row per episode, columns per source aggregate.

### 4.4 Presence/absence (negative-signal joins)

Identify episodes (or scenes) where source A produces records but source B does NOT, when the expected pattern would have B respond. Cross-extractor version of LR/CC's Q6.

**Use cases:** LR-X2 (buildup-without-reward = absence detection), CC-X3 (high-tension-without-compression).
**Complexity:** Medium–high. Requires defining "expected response" rules in advance, which is fragile.
**Output shape:** Candidate negative-signal records flagged for review; not authoritative findings without human judgment.

---

## §5. Proposed cross-extractor research questions

Seven questions, derived from §1's deferred-from-prior-ships inventory plus two new questions visible only from the cross-extractor vantage point.

**X1 (from CC-X2).** What is the per-episode total scene-boundary count when EC inits, CC compressions, and TM scene_transitions are unified and deduped? How does it compare to CC's per-episode 2.97 compressions?

**X2 (from CC-X1, LR-X4 derivative).** When Matt compresses a scene, what kind of context opens the next scene? Player declaration, NPC arrival, environmental description, Matt-narrated frame-set. Per CC's 304 scene_exit records.

**X3 (from LR-X1).** What fraction of LR rewards follow an EC perception/investigation/insight buildup at any distance within the same scene? Compare to LR's single-extractor 7.4%.

**X4 (from LR-X2 + CC-X3 unified).** What's the negative-signal rate — episodes where expected payoff (combat → reward, buildup → reward) didn't fire? Unified across LR and CC's Q6 questions.

**X5 (from TM-X1).** How much does EC join expand TM's `is_combat_state` flag coverage from its current 0.3%? Set TM `is_combat_state=True` for any TM record within N turns of an EC init; what's the expanded rate?

**X6 (from CC-X4).** Which extractor's record counts drive the C2 39% density delta over C1? CC at 39% denser is documented; do LR, TM, EC show similar campaign shifts, or is the C2 acceleration a CC-specific signal?

**X7 (new — only visible cross-extractor).** Event clustering shape: do EC inits, CC compressions, LR rewards, and TM scene_transitions cluster temporally within episodes (multi-source events within ~10 turns of each other) or distribute independently? Cluster density is a measure of scene-boundary salience; high clustering = Matt builds toward boundaries with multiple coordinated signals; low clustering = boundaries are independent events.

Each question's full single-extractor framing is in the source ship's §9. This doc inherits those framings rather than restating them.

---

## §6. Architecture sketch

This is a pipeline, not an extractor. The shape:

```
[EC records] ────┐
[TM records] ────┼──── normalize schema ──── join by episode + turn_number ────┐
[LR records] ────┤                                                              ├──── per-episode event-stream JSON files
[CC records] ────┘                                                              │
                                                                                ├──── per-question analysis scripts → findings tables
                                                                                │
                                                                                └──── cross-extractor findings doc
```

**Components proposed:**

1. **Schema normalizer.** Reads each of the four source record sets; normalizes field names to a unified schema (`source`, `episode`, `turn_number`, `episode_position_pct`, `category`, `record_payload`); writes a unified record list. Does not modify source records.

2. **Per-episode event-stream builder.** Reads the unified record list; emits one JSON file per episode with events sorted by turn_number. Output: `cross_extractor_streams/{episode}.json`.

3. **Per-question analysis scripts.** One Python script per X-question (X1–X7). Each reads the unified record list (or the per-episode streams), produces a results table, and writes a markdown summary block.

4. **Cross-extractor findings doc.** Aggregates per-question results into a unified findings doc (`track5_findings_cross_extractor.md`), mirroring single-extractor findings structure.

**No new code shared with extractors.** The pipeline reads extractor outputs as data; no source-extractor modifications.

---

## §7. Predicted FP / failure shapes

Cross-extractor joins have failure modes distinct from single-extractor work. Filed for visibility:

**F1. Cross-scene proximity bleed.** A proximity join in turn-number space will match records across scene boundaries when the boundary is not explicitly marked. Example: an LR perception-buildup-buildup query might match an EC init from a prior scene (turn 850) to a later LR reward (turn 870) when the prior scene ended at turn 855. Mitigation: use TM `scene_transition` records as scene-boundary fences for windowed joins.

**F2. Episode-coverage asymmetry blurring counts.** EC and TM cover 140 episodes; LR and CC cover 123 each (different 17-episode exclusions per ship). Per-episode counts in unified analyses must restrict to the intersection or normalize counts per-source-coverage.

**F3. Single-extractor known FPs propagating.** EC's `interruption` catchall (41% of EC records, partly inflated by lookback-window limits) and TM's UNKNOWN_SHAPE bucket (58.2%) carry known imprecision forward. Cross-extractor analyses must surface these as caveats in any aggregate that includes those categories.

**F4. Single-extractor known under-coverage propagating.** CC's STALE_HOLD_CANDIDATE (1 record total) and LR's absence-detection (0 records total) are architecturally thin. Cross-extractor approaches to LR-X2 and CC-X3 must use multi-source negative-signal detection rather than relying on the source extractor's absence-flag.

**F5. Turn-number alignment artifacts.** All four extractors compute `turn_number` from the same CRD3 c=2 turn iteration, so alignment should be exact. To verify: pick a single episode (e.g. C1E001) and spot-check that all four sources count turns consistently. Filed as a Phase 2 verification step.

---

## §8. What this ship does not address

- **D5/D7 vocabulary expansion in CC.** Per CC's Phase 6 lock decision, the source extractor is closed.
- **EC's `interruption` catchall reclassification.** Same lock principle — EC v1.3 is shipped state.
- **TM's UNKNOWN_SHAPE bucket triage.** Same.
- **Currency magnitude statistical analysis (LR-X4 alone).** Can be done from LR's records without joins; not a cross-extractor question. Filed as LR v2 candidate if pursued.
- **LR offer/delivery pairing (LR-X3) using LLM-assisted matching.** Out of scope unless §13 explicitly locks an LLM-in-the-loop decision.

---

## §9. Decisions to lock at §13

Phase 1 surfaces seven decisions Jordan resolves in chat before Phase 2 opens. Each has at least two options; recommendations are mine, override expected.

**§13.1 — Episode-coverage scope.**
Cross-extractor analyses restrict to:
- (a) The four-source intersection (~106 episodes parsed by all four extractors).
- (b) Per-pair intersection (each X-question uses the intersection of just its required sources).
- (c) Full union, with per-source-presence flags on each record.

Recommendation: **(b)**. Per-question, per-pair intersection maximizes data per question without forcing the worst-case intersection on questions that need only two sources.

**§13.2 — Schema normalization output format.**
- (a) JSON Lines (one record per line, streaming-friendly).
- (b) Per-source CSV + a combined parquet/feather binary.
- (c) JSON per-episode files only (no global record list).

Recommendation: **(a)**. JSONL is the simplest cross-language; analysis scripts can stream-read.

**§13.3 — Proximity join window default.**
- (a) 15 turns (EC's causality window).
- (b) 25 turns (EC's extended window for X1).
- (c) Configurable per-question, default 15.

Recommendation: **(c)**. Per-question defaults allow X3 (LR-X1) to use a wider window than X5 (TM-X1) which is mid-combat-scoped.

**§13.4 — Scene-boundary fences.**
Use TM `scene_transition` records as scene-boundary fences for proximity joins:
- (a) Yes — always; proximity joins do not cross a `scene_transition`.
- (b) No — proximity joins use turn-count only.
- (c) Hybrid — per-question; X3 uses fences, X5 does not.

Recommendation: **(a)**. Scene-crossing matches are F1; using TM as the fence layer is the cleanest mitigation.

**§13.5 — Q6 negative-signal detection.**
- (a) Rule-based — define "expected response" per question (e.g. EC init within N turns of LR perception-buildup) and flag absences.
- (b) Statistical — compute base rates per episode and flag outliers.
- (c) Both, parallel.

Recommendation: **(b)**. Rule-based requires upfront commitment to an "expected response" that may not exist; statistical flags outliers without prejudging the underlying rule.

**§13.6 — LR offer/delivery pairing (LR-X3 from §1 inventory; not in §5's X1–X7).**
- (a) Phase 3 candidate — X1–X7 produce the foundation in Phase 2; X3 builds on it in a later phase of this ship.
- (b) In scope for Phase 2, regex-only — currency-magnitude matching, brittle.
- (c) In scope for Phase 2, LLM-assisted — explicit deviation from the no-LLM constraint.

Recommendation: **(a)**. LR-X3 is filed for Phase 3, not deferred indefinitely. The other six X-questions are well-scoped for Phase 2 and produce the unified event-stream + scene-fence infrastructure that X3 needs. Whether X3's Phase 3 uses LLM-assisted matching depends on what post-Track-5 playtest evidence surfaces about quest-arc completion as a Virgil-architectural gap.

**§13.7 — Findings doc scope.**
- (a) One unified `track5_findings_cross_extractor.md` covering X1–X7.
- (b) Per-question micro-findings docs (one per X-question), plus a meta doc.
- (c) Append cross-extractor results to each source ship's findings doc as §12 "Cross-extractor follow-up."

Recommendation: **(a)**. One doc, mirroring the single-extractor findings structure. Single source-of-truth, easier to cross-reference.

---

## §10. Phase 2 entry criteria

Before Phase 2 opens:

- §13 decisions locked in chat.
- §2 schema normalization plan finalized (CC `trigger_id` parse + `episode` string split confirmed; EC/TM/LR field-name detail verified on first read).
- Episode-coverage intersection enumerated: which episodes are in all four sources, which are in 3-of-4, etc.
- One recon episode (C2E020 proposed) hand-traced end-to-end through the unified event-stream to validate the merge produces interpretable output before the full pipeline is built.

Phase 2 deliverables:
1. Schema normalizer + unified JSONL record list.
2. Per-episode event-stream files for the intersection set.
3. Phase 2 hand-sample: 5 episodes' event streams reviewed for join quality + F1–F5 failure-mode spot-checks.

---

## §11. Open questions for §13 chat

1. Should LR/CC's deliberately-excluded 17-episode pools be brought into the cross-extractor analysis?
   - **CC: no re-parse needed.** The 10 handsample + 7 recon CC records already exist as data on disk; they're just not in `corpus_v1p4.json`. Phase 2 can either (a) merge the handsample + recon record sets into the unified record list, or (b) read all three CC files at normalization time. Same result, no extractor work. CC coverage: 140 episodes across the merged record set.
   - **LR: real re-run required.** LR Phase 3.6 final does not have a parsed output for the 17 excluded episodes. Cost: one re-parse run with the locked Phase 3.6 extractor; benefit: cross-extractor analyses cover all 140 episodes uniformly for LR. No eval-set contamination — LR's eval sets are judged and locked.
   - Recommended: extend LR coverage to 140; CC merges existing records. Net: 140 EC + 140 TM + 140 LR + 140 CC.

2. Should the cross-extractor pipeline be runnable per-extractor-pair as well as four-way? Per-pair is more useful for question-specific analyses; four-way is more useful for X1 and X7 (unified scene-count, event clustering). Recommendation: build the schema normalizer + four-way unified record list once; per-pair scripts pull the sources they need from that list.

3. Phase 2 should run in tmux for the full-corpus run (4,601 records × ~30 episodes-with-clusters = potentially long join times); per-episode event streams are independent so the pipeline parallelizes naturally. Confirm tmux runner pattern same as prior ships.

---

## §12. Operating doctrine checklist (from `corpus_builder_lessons_v2.md` §12)

This is an analysis pipeline, not a phrase-detection extractor. The checklist applies in modified form:

- [N/A] Stage 0 discourse gate — no phrase detection.
- [N/A] Stage 0 at phrase-span level — no phrase detection.
- [✓] Causality window default 10-15 turns, narrower only with justification → §13.3 locks the proximity window.
- [✓] Two held-out sets specified → §13 decides whether eval-set construction is needed for cross-extractor analyses or whether single-extractor eval-set numbers are inherited as caveats.
- [✓] FP-family taxonomy documented from Phase 1 → §7 F1–F5.
- [N/A] No default catchall category — no classification.
- [✓] Detection vs classification separation documented → joins produce derived signals; analysis layer produces interpretations. Reliability claims on each separated.
- [✓] Eval-set overfit risk acknowledged in spec → joined-record reliability inherits source-extractor reliability; cross-extractor claims must caveat the multiplicative-uncertainty effect (joining two 70%-precision records produces a joined record with ~50% combined-claim reliability).
- [✓] Pairwise interaction testing — applies to per-question scripts; results of X1 and X3 should be consistent (X3 uses X1's scene-count denominator).
- [✓] Diagnosis-first patch application — no patches; replaces with diagnosis-first analysis script design (each X-question's script must spot-check 10–15 results against raw episode data before the result table is finalized).

---

## §13. Decisions

**Locked when Jordan resolves §9 in chat. Phase 2 does not open until locked.**

§13.1: TBD
§13.2: TBD
§13.3: TBD
§13.4: TBD
§13.5: TBD
§13.6: TBD
§13.7: TBD

(Plus §11.1's recommendation on the LR re-parse decision.)

---

## §14. Files to be produced

| Artifact | Path |
|---|---|
| Schema normalizer | `corpus_builder/cross_extractor/normalize_schema.py` |
| Unified JSONL record list | `corpus_builder/cross_extractor/all_records_unified.jsonl` |
| Per-episode event streams | `corpus_builder/cross_extractor/streams/{episode}.json` |
| Per-question analysis scripts (X1–X7) | `corpus_builder/cross_extractor/analysis_x{N}.py` |
| Cross-extractor findings doc | `corpus_builder/findings/track5_findings_cross_extractor.md` |
| Phase 2 hand-sample notes | `corpus_builder/findings/cross_extractor_phase2_handsample.md` |
| Phase 1 spec (this doc) | `corpus_builder/findings/track5_cross_extractor_analysis_phase1_spec.md` |
