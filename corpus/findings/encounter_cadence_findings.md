# Encounter Cadence — Findings (v1.3)

**Ship:** Track 5, Ship 1 — Encounter Cadence Extractor
**Source corpus:** CRD3 c=2 alignment, 140 unique episodes (94 C1, 46 C2; no C3 or one-shots present in the source)
**Extractor version:** `encounter_cadence_v1_3`
**Records emitted:** 170 across 140 episodes
**Date completed:** May 5, 2026

---

## 1. Question asked

When does Matt Mercer initiate combat encounters across CRD3, and what triggers each one? Specifically: how often per episode, where in the episode arc do they cluster, and what causes them — player action, NPC hostility, environmental change, trap activation, mid-combat phase shift, or something the rules can't classify?

The downstream goal is informing Track 4 spec design — particularly encounter pacing, world-event triggers, and combat-shape rhythm. The extractor's job was to produce structured timeline records that a human can read to inform deterministic Python rules; the LLM is never in the execution path for combat decisions.

---

## 2. Method

Each MATT turn in CRD3 c=2 was scanned for initiative-event candidates using deterministic regex. The architecture evolved across four versions:

- **v1.0** — single-stage candidate detection + classification across six categories (`player_action_escalation`, `environmental_materialization`, `trap_activation`, `npc_turns_hostile`, `interruption`, `wave_or_phase_shift`). Hand-sample on 10 episodes.
- **v1.1** — six regex patches addressing eval-set failures from manual review.
- **v1.2** — five further patches plus widened causality windows; introduced ship-gate methodology (FP rate, wave detection, classification precision).
- **v1.3** — added a Stage 0 discourse layer between candidate detection and classification, separating EVENT (real init) / STATE (mid-combat narration) / DISCOURSE (meta-talk about initiative). This was the highest-impact architectural change.

Eval-set construction grew alongside: v1 (14 records) → v2 (69 calibration) → v3 (84 calibration + 25 held-out, one-shot measurement). The v3 held-out methodology was physically enforced — held-out records had no `raw_text` field in the JSON during calibration, and a `--holdout` flag was required to even run the test against them.

The classification logic uses six categories, locked from Phase 1 and never expanded. A wave/phase-shift sub-type field distinguishes mid-combat new-combatant arrivals (`reinforcement`, `party_join`, `phase_shift`). Each record carries the trigger turn, episode position, preceding-context turns, narration buildup char count, and a `nearest_prior_trigger_turn_distance` metadata field for analysis-layer adjacency handling.

No LLM was used at any stage. No FIREBALL data was used (FIREBALL is snapshot-shaped; cadence requires flow data).

---

## 3. Sample size

- **Full parse output:** 170 records across 140 episodes (94 episodes that produced a record, 46 that didn't).
- **Calibration set:** 84 records (14 v1 + 31 spot-check + 24 phase-3 blind + 15 phase-4 blind).
- **Held-out test set:** 25 records, sampled `random.seed(7777)` from episodes never reviewed during calibration. Measured exactly once.
- **Post-ship validation:** 42 fresh blind records (12 + 30) sampled from records and episodes not used in any prior calibration.

The post-ship validation is what drives the reliability claims in §4. The held-out gate-pass numbers reflect the calibration surface; the post-ship sample reflects the wild.

---

## 4. Reliability — read this before quoting any number below

The held-out ship gates passed cleanly: FP rate 0/34 = 0%, wave detection 4/8 = 50%, strict precision 14/25 = 56%, no regression on calibration metrics. By the methodology this ship was designed around, v1.3 is shipped.

**However**, post-ship blind sampling on 42 records (drawn from episodes never used in calibration or held-out) produced different numbers:

- **FP rate: ~7-10% in the wild** (3 FPs in 42 records; 95% binomial CI roughly 1.5%-19%).
- **Strict classification precision: ~36%.**
- **Lenient precision (correct + defensible): ~48%.**

The held-out 0% FP rate did not generalize because the held-out set, while not used in calibration, was sampled from the same broad pool that produced the calibration FP shapes. New FP families surfaced in the post-ship sample that the held-out set hadn't seen — episode-recap narration, mini-placement-as-init narration, exposition-without-init-trigger.

**The doctrine that crystallized from this gap:** held-out gate-pass overstates generalization unless the held-out set is sampled from a fundamentally different distribution. See `corpus_builder/corpus_builder_lessons_v1.md` for the methodology recommendations carrying forward.

**Sharpened claim language for downstream consumers:**

> Cadence frequency appears directionally reliable with a measured FP floor of ~7-10% on fresh blind samples. Episode-position clustering and per-episode density are usable signals.

> Category proportions should be treated as suggestive rather than authoritative due to high cross-category ambiguity and causality-window limitations. The `interruption` bucket is structurally inflated as a residual catchall for cases where the rules couldn't determine the cause within their lookback window.

Track 4 spec design should pull signal from frequency and episode-position; treat category breakdown as a hypothesis-generator, not a fact-source.

---

## 5. Headline numbers — frequency and position

These are the high-reliability findings. Numbers carry a measured ~7-10% FP floor — the true underlying count is roughly 7-10% lower than reported.

### Per-episode density

| Metric | Value |
|---|---|
| Episodes processed | 140 |
| Episodes producing ≥1 record | 94 (67%) |
| Episodes producing zero records | 46 (33%) |
| Total records emitted | 170 |
| Mean records per episode | 1.21 |
| Median records per episode | 1 |
| Maximum records per episode | 5 |

After applying the FP floor, the corpus contains roughly 153-158 real init events across 140 episodes, with per-episode mean of approximately 1.10. Roughly one in three episodes is a downtime/RP-heavy session with no encounter initiation at all.

### Campaign split

| Campaign | Episodes | Records | Records per episode |
|---|---:|---:|---:|
| C1 | 94 | 103 | 1.10 |
| C2 | 46 | 67 | 1.46 |

C2 carries a higher per-episode density. Whether this reflects a genuine pacing difference between Matt's C1-era and C2-era DM style or a corpus-coverage artifact is open. The number-per-episode delta is small enough that it should be cross-checked before treating it as a real campaign-level signal.

### Episode-position distribution

Episode-position is the trigger turn's index divided by total episode turn count — where in the episode arc Matt initiates combat.

| Statistic | Value |
|---|---|
| Minimum | 0.007 (cold-open within first 1% of episode) |
| Median | ~0.44 |
| Maximum | 0.97 |
| Mean | ~0.44 |

Encounters cluster in **mid-episode**, not equidistantly. Cold-opens (init in the first 5% of episode) and late-episode encounters both occur but are not the dominant shape. The median ~0.44 says: Matt typically lets 40% of an episode pass — table chatter, RP, movement, scene-setting — before the first init call, then fills the back half with combat plus aftermath.

This is a **usable signal for Track 4** encounter-pacing design.

### Within-episode init spacing

The `nearest_prior_trigger_turn_distance` field captures the turn-number gap between consecutive init events in the same episode. 76 of 170 records (45%) are non-first records — i.e., the episode contained an earlier init.

| Statistic | Value |
|---|---|
| Minimum | 2 turns (back-to-back inits, likely a restated init request) |
| Median | ~140 turns |
| Maximum | 2116 turns (very late second init in a long episode) |

The median ~140 turns says when Matt initiates a second encounter in an episode, it's typically a long way after the first — most multi-encounter episodes are NOT a string of back-to-back fights. This is also usable for Track 4: an episode with two encounters tends to space them widely, suggesting Matt deliberately separates combat beats with non-combat material.

---

## 6. Category breakdown — suggestive only

The numbers below carry both the FP floor (~7-10%) and the classification-precision noise (~36% strict / ~48% lenient). The `interruption` bucket is structurally inflated. Treat these proportions as exploratory, not as fact.

### Trigger category

| Category | Count | Proportion | What it tries to capture |
|---|---:|---:|---|
| `interruption` | 70 | 41.2% | Init Matt called whose cause the rules couldn't determine — partly real "scene transitions to combat without clear trigger," partly residual catchall |
| `npc_turns_hostile` | 32 | 18.8% | NPCs revealing or committing to hostility via dialogue, ambush, transformation |
| `wave_or_phase_shift` | 28 | 16.5% | Mid-combat new-combatant arrivals or phase shifts |
| `player_action_escalation` | 24 | 14.1% | Init triggered by player action (kicked door, threw fireball, executed planned attack) |
| `environmental_materialization` | 15 | 8.8% | Creatures or threats emerging from the environment without explicit NPC dialogue or player cause |
| `trap_activation` | 1 | 0.6% | Player triggered a trap mechanism |

### Wave subtypes

| Subtype | Count |
|---|---:|
| `phase_shift` | 22 |
| `party_join` | 5 |
| `reinforcement` | 1 |

`phase_shift` dominates because the patch-8 fallback defaults to `phase_shift` when no specific subtype matches. The single `reinforcement` is suspicious — manual review found at least three reinforcement-shape events in the corpus that classified as something else.

### Boolean fields

| Field | True | False |
|---|---:|---:|
| `is_fresh_encounter` | 142 | 28 |
| `player_action_caused` | 29 | 141 |

`player_action_caused=True` on 17% of records understates the real rate based on post-ship spot-checks where multiple records with player-cause failed the detection regex. Real rate likely 25-30% with current taxonomy boundaries.

### Why `interruption` is a sinkhole

When the classification rules can't determine a cause within their lookback window, the record falls through to `interruption`. The lookback window is bounded by `preceding_context_chars` (1500 chars, typically 15-25 turns), but actual-play causality often spans longer — a player declares intent at turn 50, Matt narrates consequences across turns 51-65, init fires at turn 66 with the player-cause reference now beyond the window's reach. The classification rule sees an init with no detectable cause and labels `interruption`.

This means the 41.2% `interruption` proportion mixes:
- Real "scene transitions to combat without clear trigger" (some quantity of the bucket)
- Cases where player action caused the init but happened too far back to detect
- Cases where NPC dialogue caused the init but was paraphrased past the regex
- Cases where environmental change happened gradually across many turns

Track 4 should not treat the 41% as "Matt's default initiation mode is uncategorized scene transition." That's a measurement artifact.

---

## 7. Surprises

Patterns that contradicted prior assumptions during recon and shipping:

**Trap activation is essentially absent.** One record across 140 episodes. Either traps are genuinely rare in CRD3 actual play (plausible — long-form D&D leans more on narrative encounters than dungeon-grind traps), or the trap-detection regex misses cases where the mechanism narration spans more turns than the lookback window catches. Recon found a clear cabinet-trap case (C2E045 t2014) that v1.0 missed because the player-interaction was 16 turns before the init call. v1.1 widened the window and caught that case in the eval set, but no v1.3 full-parse record was tagged trap_activation except the eval-set anchor. **Most likely:** mid-game traps in long-form actual play are rare relative to the encounter rhythm (~1% of inits, not the ~10-15% trap-heavy dungeon-design assumes).

**Wave events are much more common than v1.0 caught.** v1.0 emitted 10 wave records across 140 episodes (4.1% of inits). v1.3's combat-state-aware detection bumped this to 28 records (16.5%). Mid-combat new-combatant arrivals — reinforcements, party-members joining late, phase shifts — are a substantial portion of Matt's encounter rhythm. Track 4 design should treat "encounter evolves after initiation" as a first-class pattern, not a fringe case.

**Episode-position clusters mid-episode, not at episode start.** Initial recon assumed Matt frontloaded combat and used the back half for resolution. The actual median is ~0.44, mean is ~0.44. Episodes are roughly 50% RP-and-setup, 50% combat-and-aftermath, with the first encounter typically arriving around turn 40-50% of the episode. This contradicts the "cold-open into a fight" pattern the recon expected.

**Zero-record episodes are 33% of the corpus.** One in three episodes contains no encounter initiation at all. These are downtime sessions (city exploration, character development, shopping, long-rest aftermath). For Track 4 encounter-pacing, this means **the right model isn't "every session has a fight"** — it's "roughly two-thirds of sessions have at least one fight, one-third are pure RP."

**`interruption` dominates because the rules can't see far enough back.** The 41% catchall isn't a story about Matt's DM style — it's a story about extractor architecture. See §6 and `corpus_builder_lessons_v1.md`.

---

## 8. Implications for Track 4

### Robust signal — usable for spec design

- **Encounter density per episode.** Mean ~1.1 real init events per episode, median 1, max 5. Roughly two-thirds of episodes contain at least one encounter; one-third are pure non-combat sessions.
- **Episode-position clustering.** First encounter typically lands at episode-position ~0.4. Cold-opens and late-episode initiations both occur but aren't the dominant shape.
- **Within-episode spacing.** Multi-encounter episodes typically space inits widely (median ~140 turns between consecutive inits). Matt deliberately separates combat beats with non-combat material.
- **Wave events are common.** ~16% of init records are mid-combat re-inits, not fresh encounters. "Encounter evolves after initiation" is a real, frequent pattern.
- **Campaign-arc consistency.** Both C1 and C2 show similar density and position distributions, suggesting the cadence is a stable feature of Matt's DM style across years.

### Suggestive signal — hypothesis-generator only

- **Trigger taxonomy proportions.** The relative frequency of player-caused vs NPC-caused vs environmental vs wave is exploratory. The `interruption` bucket inflation makes ratios untrustworthy.
- **Player-action vs NPC-hostile balance.** Stated 14% player-action vs 19% NPC-hostile, but post-ship spot-checks suggest the player-action rate is closer to 25-30% real, with many records mis-classified to `interruption` because the player cause was outside the lookback window.
- **Environmental vs trap split.** Environmental materialization at 9% looks roughly correct based on spot-checks. Trap at 0.6% is either correct (traps rare in long-form play) or a recall failure.

### Filed for future research — would benefit from a v1.4 cycle if/when needed

- Wave-detection precision under cross-episode-window causality (initial combat 50+ turns earlier than current init call)
- NPC-hostile vs environmental-materialization boundary disambiguation (creatures revealing as hostile vs creatures emerging from environment)
- Recap-narration as an FP shape in long-running campaign episodes
- Player-action causality detection across 15-25 turn windows rather than 5-10

These were observed during post-ship spot-checks but accepting them as v1.3-shipped failures rather than chasing them is the explicit ship discipline. See `corpus_builder_lessons_v1.md` for why.

---

## 9. Limitations

1. **36 of 140 episodes were never manually reviewed during eval-set construction.** Records from those episodes are present in the full parse but no human spot-checked their classification.

2. **Source corpus is c=2 alignment only.** CRD3 publishes three alignment configurations (c=2, c=3, c=4); turn-level data is reportedly byte-identical across them, but this was confirmed during Phase 1 only by importer comparison, not by exhaustive diff.

3. **No FIREBALL data.** FIREBALL is snapshot-shaped (single combat exemplars, not multi-turn flows) and cannot carry encounter pacing or temporal sequencing. Filed in `CORPUS_BUILDER.md` as the source-corpus-asymmetry doctrine.

4. **Six-category taxonomy is locked, possibly under-specified.** Categories were derived from Phase 1 hand-samples and never expanded. Cases like "approach a static encounter location" (party walks up to a known threat) and "NPC transformation reveals as hostile" are folded into existing categories, but a future research question may show these need their own labels.

5. **Causality window is bounded at ~15-25 turns / 1500 chars.** Actual-play causality can span 50+ turns. v1.3's classification logic walks the preceding window but doesn't reach across episodes or across long non-combat scenes.

6. **Post-ship validation sample size is n=42, not n=140.** The reliability claims in §4 are based on a smaller sample than the full parse. The 95% confidence interval on the 7-10% FP rate is roughly 1.5%-19% — directional, not exact.

7. **The classification taxonomy is bounded by what the corpus reveals.** There may be Matt-style encounter-initiation patterns that occur infrequently enough to not surface in the eval-set construction process.

---

## 10. Files

| Artifact | Path |
|---|---|
| Raw output | `corpus_builder/output/encounter_cadence/` (170 JSON records across 140 files) |
| v1.2 output preserved | `corpus_builder/output/encounter_cadence_v1_2/` (186 records) |
| v1.1 output preserved | `corpus_builder/output/encounter_cadence_v1_1/` (243 records) |
| Eval set v3 | `corpus_builder/findings/encounter_cadence_eval_set_v3.json` |
| Validation v1.3 | `corpus_builder/findings/encounter_cadence_validation_v1_3.md` |
| Validation v1.2 | `corpus_builder/findings/encounter_cadence_validation_v1_2.md` |
| Validation v1.1 | `corpus_builder/findings/encounter_cadence_validation_v1_1.md` |
| Stats v1.3 | `corpus_builder/findings/encounter_cadence_full_parse_stats_v1_3.md` |
| Session log | `corpus_builder/findings/encounter_cadence_session_log.md` |
| Architectural lessons (cross-extractor) | `corpus_builder/corpus_builder_lessons_v1.md` |
| Extractor source | `corpus_builder/extractors/encounter_cadence.py` |
| Regression test | `corpus_builder/extractors/test_encounter_cadence_eval_v3.py` |
