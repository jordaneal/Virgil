# Time-Mention — session log

## Phase 1 — recon + taxonomy proposal (2026-05-06)

**Output artifact:** `/home/jordaneal/virgil-docs/TIME_MENTION_V1_SPEC.md`

### Read first

- `corpus_builder/corpus_builder_lessons_v1.md` — durable principles from Ship 1, applied as constraints throughout this spec.
- `virgil-docs/CORPUS_BUILDER.md` — Track 5 architecture, output contract, parallel-job protocol.
- `corpus_builder/findings/encounter_cadence_findings.md` — Ship 1's research output; shape reference for findings doc later.
- `virgil-docs/ENCOUNTER_CADENCE_V1_SPEC.md` — Ship 1's Phase 1 spec; section structure followed for parity.

### Recon

CRD3 c=2 source confirmed unchanged from Ship 1. 140 unique episodes across 280 files. MATT-only filter applies. Spot-checked C1E007 format — `{CHUNK, ALIGNMENT, TURNS}` with per-turn `NAMES`/`UTTERANCES`/`NUMBER`. Same structure as Ship 1.

### Sample

Seven episodes, disjoint from Ship 1's reviewed list:
- C1E007 (early C1 dungeon), C1E040 (early-mid Thordak attack), C1E064 (mid C1 travel), C1E108 (late C1 forging), C2E010 (early-mid C2 sewers), C2E025 (mid C2 escape), C2E040 (late C2 sea-pursuit).

Built per-episode dedup turn lists; ran broad time-pattern union regex over MATT turns. Hand-classified 188 raw hits as ~55-72 real fiction-time progressions — naive regex over-counts ~3x, same magnitude as Encounter Cadence's `\binitiative\b` problem. Stage 0 has clear work to do.

Largest single FP source: the word `second` is overloaded (time unit / "again" idiom / second-attack mechanic / second-floor architecture / "hold on a second" table-talk / "for a second" combat micro-beat / "see you in a second" episode break). Roughly 70% of `\bsecond\b` hits are noise.

### Taxonomy proposed

Four categories:
- **`in_scene_compression`** — time elapses during active scene (task, pause, montage). seconds → ~hour.
- **`travel_duration`** — time elapses during party travel/movement. minutes → weeks.
- **`scene_transition`** — discrete scene break (overnight, time-of-day pivot, session-cut framing). hours → days.
- **`cumulative_anchor`** — Matt explicitly states elapsed time or current time-of-day. anchor-establishing.

Plus `unknown_shape: true` flag for Stage-1 unclassifiable (per Lesson 2, no default sinkhole). Priority order for multi-match: scene_transition > travel_duration > cumulative_anchor > in_scene_compression.

Considered and rejected: `scene_pause` (folded into in_scene_compression), `time_of_day_anchor` (folded into cumulative_anchor), `spell_duration` (Stage 0 reject, mechanic-not-fiction), `deadline_set_by_npc` (filed for `narrative_pressure_v1`), `backstory_recall` (Stage 0 reject when NPC-quoted), `session_break_framing` (Stage 0 reject), `combat_round_count` (STATE flag, not category), `real_world_calendar` (Stage 0 reject), `in_universe_calendar_event` (folded into cumulative_anchor).

### Stage 0 designed

Required, not optional. Per Lesson 5. Three-way EVENT / STATE / DISCOURSE gate.

**STATE flags:** `is_combat_state` (combat round-counts, mid-combat duration), `is_recap_state` (early-episode recap blocks).

**DISCOURSE rejects (D1-D7):** production OOC + episode breaks; spell/rules duration; DM table-talk (`hold on a second`); combat micro-beat (`reels back for a second`); idiom artifacts (`a second time/attack/floor/level`); NPC dialogue (medium-risk; quote-mark detection with fallback); player-question pass-back. First-match-wins priority order specified.

### Causality window

Default preceding-context **500-800 chars / 5-8 turns** (smaller than Encounter Cadence's 1500/15-25). Justified: time-mention triggers are largely self-contained.

Anchor walk-back **up to 15 turns** for relative-references (`the next morning`, `moments later`, etc.). Records `time_anchor_turn_number`, `is_anchored`, `anchor_distance_turns`. Null when anchor not found within window.

### FP-family taxonomy (predicted upfront, per Lesson 4)

Nine FP shapes documented (FP1-FP9): spell/rules duration, production OOC, NPC dialogue, combat micro-beat `for a second`, idiomatic `second`, DM table-talk, real-world calendar, combat round-mechanic (STATE-flagged), recap-block (STATE-flagged). List explicitly incomplete by design — Phase 2 hand-sample will surface a tenth family, post-ship sampling will surface more. Each new family becomes documented patch, not silent regex addition.

### Held-out methodology (per Lesson 7)

Two sets, mechanical enforcement.
- **Gate-set:** ~25 records, `random.seed(7777)`, file `findings/time_mention_gate_set_v1.json`. `raw_text` stripped during calibration; `--holdout` flag required for access. Read once at Phase 4.
- **Validation-set:** ~15 records, `random.seed(9999)`, file `findings/time_mention_validation_set_v1.json`. Sampled at Phase 5 from full-parse output. `--validation` flag required. Run exactly once post-ship. Authoritative reliability claim.

Test runner has three exclusive modes: `--calibration` (default), `--holdout`, `--validation`. Modes cannot mix.

### §11 decisions surfaced for Jordan's lock

§11.1 granularity scope (recommend all-scales, combat round-counts as STATE, MEDIUM confidence) · §11.2 anchored references (recommend explicit anchor field with null-on-fail, MEDIUM) · §11.3 player time-mentions (recommend hard-reject, HIGH) · §11.4 OOC aggressiveness (recommend aggressive reject, HIGH) · §11.5 episode-break framing (recommend reject entire turn, MEDIUM-HIGH) · §11.6 multi-mention turns (recommend one record per phrase with `same_turn_record_index`, MEDIUM) · §11.7 cumulative_anchor as category vs flag (recommend separate category, MEDIUM).

Plus eight open questions: NPC-dialogue detection robustness, C1/C2 phrasing drift, granularity bucket validation, anchor walk-back depth, combat-state detection source, recap-block detection signal, hand-sample episode list, findings doc placement.

### Operating-doctrine checklist

All seven items in `corpus_builder_lessons_v1.md` §9 satisfied:
- Stage 0 designed before Stage 1 candidate detection.
- Causality window narrower than EC default with justification.
- Two held-out sets specified with mechanical enforcement.
- FP-family taxonomy documented Phase 1.
- No default catchall category.
- Detection vs classification separation documented.
- Eval-set overfit risk acknowledged in spec header and §8.

### Next step

Jordan locks §11.1-§11.7 + open-question answers in chat. Phase 2 (separate session) ships: `extractors/time_mention.py`, `samples/time_mention_sample.json`, `findings/time_mention_validation_v1.md`, gate-set + validation-set JSON scaffolds. Full-parse only after Phase 4 gate passes.

---

## Phase 2 — implementation + hand-sample (2026-05-06)

**Output artifacts:**
- `extractors/time_mention.py` (extractor, ~750 lines)
- `samples/time_mention_sample.json` (321 records across 10 locked episodes)
- `findings/time_mention_validation_v1.md` (this report's companion)
- `findings/time_mention_eval_set_v1.json` (calibration only, 321 records)
- `findings/time_mention_boundary_stability_v1.json` (196 records for §11.7 manual review)
- `findings/time_mention_d6_precision_v1.json` (171 records for OQ1 manual review)
- `extractors/test_time_mention_eval_v1.py` (regression runner, 3 exclusive modes)

**Locked decisions applied:**
- §11.1 minutes-and-up only — `_DURATION_UNIT` excludes `second|seconds`. T20-style sub-minute beats are accepted misses.
- §11.2 explicit anchor field with null-on-fail — `time_anchor_turn_number`, 15-turn back-walk.
- §11.3 hard-reject non-MATT triggers — `if t["speaker"] != "MATT": continue`.
- §11.4 aggressive OOC reject — D1 rejects whole turn.
- §11.5 episode-break framing rejected entire-turn.
- §11.6 multi-mention turns emit one record per phrase, indexed by `same_turn_record_index`.
- §11.7 cumulative_anchor as separate category — boundary-stability records dumped for Jordan's manual mark-up.
- OQ1 D6 fallback applied — 25-record spot-check of D6 rejects produced ~56-64% precision (well below 85% threshold), so D6 was demoted from reject to flag (`is_npc_dialogue_present`) per the lock's fallback clause.
- OQ5 combat-state re-derived in-extractor, init regex copied from `encounter_cadence.py` (commented `COPIED_POSITIVE_INIT`). Lock's 25-turn lookback retained even though it under-detects long encounters in the sample.
- OQ7 hand-sample list locked from prompt (no spec-list collisions).
- OQ8 paths per spec.

**Hand-sample run results:**
- 321 records, 0 zero-event episodes.
- Categories: cumulative_anchor 39%, scene_transition 22%, in_scene_compression 10%, travel_duration 5%, UNKNOWN_SHAPE 24%.
- Granularity skewed to `days` (29%) due to time-of-day anchors aggregating into the day bucket — flagged for v2 split.
- 50 DISCOURSE rejects across D1/D2/D3/D7 (D6 demoted to flag).
- 78 unknown_shape records — 64 are genuinely-unclassifiable (mostly NPC backstory durations), 14 are classifier misses with v2 patches identified.
- Multi-mention turn rate: 17.2% (higher than spec's recon estimate of 5-8%).
- 0 `[EXTRACTOR_UNKNOWN]` (source format stable).

**§3.3 / §3.4 boundary stability:** Phase 2 dumps 196 candidates to `boundary_stability_v1.json`; Jordan computes the proportion during his spot-check.

**D6 NPC-dialogue precision (sampled, n=25):** ~56-64%. Below the 85% threshold — D6 demoted to flag. 171 flagged records dumped for full manual review.

**Granularity-bucket distribution:** days 94, unspecified 71, minutes 43, weeks 33, years 28, hours 24, months 18, rounds 10.

**Anchor-found rate:** 7/16 = 43.8%. Below spec's 60% threshold — recommend widening to 25 turns in v2.

**Filed insights (candidate cross-extractor doctrine update):**
- **Lesson-9 candidate — phrase-span vs turn-level Stage 0.** Encounter Cadence's Stage 0 ran at turn level. Time-Mention's D6 reveals that turn-level reject loses real signal in heterogeneous turns (Matt narration mixed with NPC speech). Future extractors in densely-mixed-narration domains should design phrase-span-aware Stage 0 patterns. To be confirmed/incorporated after Ship 3 (Loot/Reward) hits the same shape.
- **Granularity-bucket overload.** The `days` bucket aggregates `morning|evening|afternoon|night|noon|...` along with explicit day-counts; in 29% of records this hides the actual time-of-day vs day-count distinction. Future granularity schemes for time-bearing extractors should split sub-day diurnal anchors from day counts.

**Phase 3 (gate-set construction + calibration regression) is not scheduled.** Will not run until Jordan completes the manual spot-check on:
- 321 calibration records (`time_mention_eval_set_v1.json`)
- 196 boundary-stability records (`time_mention_boundary_stability_v1.json`)
- 171 D6-flagged records (`time_mention_d6_precision_v1.json`)

---

## Phase 3 — v1.2 calibration with hard ship gates (2026-05-06)

**Output artifacts:**
- `extractors/time_mention.py` (v1.2)
- `samples/time_mention_sample_v1_2.json` (234 records)
- `samples/time_mention_sample_v1_1.json` (preserved v1, 321 records)
- `findings/time_mention_validation_v1_2.md`
- `findings/time_mention_eval_set_v2.json` (321 calibration records, Jordan + Claude blind judgments)
- `extractors/test_time_mention_eval_v2.py` (regression runner, 3 modes)

**Patches applied:**
- 1. Multi-mention turn-level dedup (`dedup_turn_records` — same-sentence ≤80 chars OR same-category-and-anchor ≤200 chars).
- 2. NPC-dialogue → UNKNOWN_SHAPE phrase-span routing (`is_phrase_in_npc_speech` — quote-mark count + same-sentence NPC voicing tag).
- 3. cumulative_anchor temporal-context tightening + D8 causal-since filter.
- 4. D1 production OOC extension (break + cast banter + meta-procedural; initial regex-bug fixed mid-session for `we're going to` form).
- 5. D5 idiomatic phrase filters (it's been [emotion/state] + wait a minute + drinks idioms + slammed-across-years simile + Hour-of-X event names).

**Ship gates (321-record calibration set):**
- Strict precision: **73.8%** (target ≥80%, baseline 55.5%) — **FAIL** by 6.2pp
- FP rate: **3.4%** (target ≤5%, baseline 11.2%) — **PASS**
- Duplicate rate: **3.4%** (target ≤3%, baseline 16.8%) — **FAIL** by 0.4pp
- No-regression retention: **85.4%** (target ≥95%) — **FAIL** by 9.6pp

**STOPPED at gate fail.** Per Phase 3 prompt's explicit stop-and-report rule. Three of four gates miss. Five patches show real signal (FP rate halved twice over; dup rate 5x improvement; precision +18pp). Tightening further requires Jordan-level decisions about Patch 1 dedup window size, Patch 3 cumulative_anchor temporal-context refinement, and OQ5 combat-state lookback — out of v1.2 scope.

**Filed insights (candidate cross-extractor doctrine update):**
- **Lesson 9 confirmed — phrase-span vs turn-level Stage 0.** Patch 2's phrase-span-aware NPC routing worked as designed; the architectural pattern is right for densely-mixed-narration domains. Future extractors should design phrase-span filters from Phase 1, not retrofit them after a turn-level Stage 0 ships.
- **Lesson 10 candidate — same-extractor patch interactions.** Patch 1 (dedup) and Patch 2 (NPC routing) interact: Patch 2 routes some legitimate Matt-narration UNKNOWN_SHAPE candidates next to NPC-speech-routed UNKNOWN_SHAPEs in the same turn; Patch 1 then dedups them as same-category-same-anchor neighbors. Result: real signal lost. Future calibration cycles should test patches PAIRWISE, not just sequentially. To be confirmed at Ship 3 if the same shape recurs.

**Recommendation surfaced for Jordan's lock (no auto-escalation):**
- Accept v1.2 as published v1.x baseline (precision 73.8%, FP 3.4%) for Track 4 informational use, or
- Lock 3 v1.3-candidate decisions: (a) widen Patch 1 dedup window 200 → 400 chars + add cross-turn dedup; (b) tighten Patch 3 cumulative_anchor temporal-context to require explicit time-of-day or duration vocab; (c) widen OQ5 combat-state lookback to 50 turns + damage-narration backup.

**Phase 4 (gate-set construction) is not scheduled.** Will not run until Jordan reviews v1.2 outcomes and locks the v1.3 path.

---

## Phase 3.5 — v1.3 retention recovery (2026-05-07)

**Output artifacts:**
- `extractors/time_mention.py` (v1.3)
- `samples/time_mention_sample_v1_3.json` (234 records, identical to v1.2)
- `samples/time_mention_sample_v1_2.json` (preserved)
- `findings/time_mention_validation_v1_3.md`

**Patch applied:**
- Patch 6: Tightened `CUMULATIVE_BACKWARD_TEMPORAL` `since` check from any-word/loose-verb-list to explicit time-context allow-list (event verbs, time-noun follow-ons, `[duration] ago`, named time anchors).

**Ship gates (321-record calibration set):**
- Strict precision: **73.8%** (target ≥78%, baselines: v1 55.5% / v1.2 73.8%) — **FAIL** −4.2pp
- FP rate: **3.4%** (target ≤5%, baselines: v1 11.2% / v1.2 3.4%) — **PASS**
- Duplicate rate: **3.4%** (target ≤5%, baselines: v1 16.8% / v1.2 3.4%) — **PASS**
- No-regression retention: **85.4%** (target ≥92%, v1.2 85.4%) — **FAIL** −6.6pp

**STOPPED at gate fail — third trigger (`since` disambiguation harder than expected).** Patch 6 had **zero record-level delta** because v1.2's existing `since` regex already filtered the failure modes Patch 6 was designed to catch. The retention loss lives in different patch interactions (Patch 1 dedup ↔ Patch 2 NPC routing) and pattern boundary mismatches (TRAVEL priority 2 over-firing, NPC-dialogue detection too loose for `i'?d say`).

Spot-tested Patch 6 directly on 10 `since`-form sentences — patch correctly classifies (rejects causal forms, accepts temporal forms). Patch is structurally correct but targets a surface area v1.2 had already covered.

**Diagnosed nine reclassified records directly** — none key on `since` disambiguation. Eight different failure shapes: bedtime-as-scene-transition gap, foot-travel idiom over-firing TRAVEL, "It has been steeped" idiom collision with in-scene-compression, weak NPC voicing tags (`I'd say`) over-firing turn-level NPC routing, "X traveling there" priority-2 over-fire, "It's been a series of dead ends" borderline cumulative_anchor, "1500 years ago" borderline backstory anchor, "next few days practicing" boundary scene-transition vs in-scene-compression.

**Confirmed insights for lessons doc v2:**
- **Lesson 9 confirmed (phrase-span vs turn-level Stage 0):** Patch 2 architecture validated; Phase 3.5 surfaces a corollary that NPC-dialogue detection itself needs phrase-proximity tightening (not just turn-level any-tag detection).
- **Lesson 10 confirmed (test patches pairwise):** Patch 1 ↔ Patch 2 entanglement still drives most of the retention loss; Patch 6 doesn't touch this.
- **Lesson 11 candidate (calibration-set ceiling effect):** v1.2 → v1.3 numbers identical because finite calibration set's coverage was already exhausted by Phase 3 patches. Diagnosis-first calibration: spot-test a 10-15 record diff against the patch BEFORE accepting the patch, to confirm record-level delta. A regex change passing design review but producing zero deltas is a signal that the diagnosis was wrong, not the regex.

**Recommendation surfaced for Jordan's lock (no auto-escalation):**
- Path A: accept v1.3 as published baseline (precision 73.8%, FP 3.4%, dup 3.4%, retention 85.4%) and proceed to Phase 4 gate-set construction.
- Path B: lock v1.4 patch directions targeting the eight failure shapes from §2 of the v1.3 validation doc — bedtime-scene-transition, TRAVEL-priority tightening, NPC-detection tightening — likely +10-15 retention records reclaimed; doesn't address the 3-4 genuine taxonomy-judgment boundary cases.

**Phase 4 (gate-set construction) is not scheduled.** Will not run until Jordan reviews v1.3 and locks Path A or Path B.

---

## Phase 4 — held-out gate-set construction (2026-05-07)

**Output artifacts:**
- `findings/time_mention_eval_set_v3_holdout.json` (25 records, expected_category null pending Phase 5 judging)
- `findings/time_mention_eval_set_v3_holdout_construction.md`
- `extractors/test_time_mention_eval_v2.py` (--holdout mode hydrates raw_text from CRD3 source)

**Sampling:** seed=7777, n=25, stratified by extractor `category` (incl. `unknown_shape: true` records). Source: `samples/time_mention_sample_v1_3.json` (234 records).

**Per-category counts (target → actual):**
- cumulative_anchor: 8 → 8
- scene_transition: 6 → 6
- in_scene_compression: 4 → 4
- travel_duration: 2 → 2
- unknown_shape: 5 → 5

**Episodes covered:** 9 of 10 (C1E085 absent; seed-7777 random pull happened not to draw any of its 9 records). All other locked-list episodes contributed.

**Calibration-exclusion check NOT_POSSIBLE — documented.** Mechanical (trigger_id, same_turn_record_index) overlap with v2 calibration is 25/25, by construction: v2 calibration covered all 321 v1 records from the same 10 episodes, and v1.3 dedup renumbering doesn't introduce new keys. Held-out methodology preserved via blind re-judging (Phase 5) + raw_text stripping + --holdout flag enforcement, per `corpus_builder_lessons_v1.md` Lesson 7's spirit. Filed as v1 limitation for findings doc.

**Mechanical enforcement verified:**
- `--calibration` (default) → 321 records, 73.8% precision (unchanged).
- `--holdout` → "zero judged records. Phase 5 will populate expected_category..." — errors cleanly without leaking held-out content.
- `--validation` → "Phase 5 will populate" — errors cleanly.

**Phase 5 (judging + held-out measurement)** is next session. Jordan + Claude judge the 25 records in chat blind, fill in `expected_category` / `verdict` / `failure_mode`, run `--holdout` for the published-claim ship-gate measurement.

---

## Phase 5 — full parse + validation-set + findings (2026-05-07)

**Output artifacts:**
- `output/time_mention/*.json` (140 episodes, 3,592 records)
- `findings/time_mention_full_parse_log.txt`
- `findings/time_mention_full_parse_stats_v1_3.md`
- `findings/time_mention_validation_set_v1.json` (15 records, `expected_category=null` pending Phase 5b)
- `findings/time_mention_validation_set_v1_construction.md`
- `findings/time_mention_findings.md`
- `lessons_doc_v2_candidates.md` (Lessons 9, 10, 11)
- `WHY.md` (one-line callout added to a new "Track 5 — Corpus extraction methodology" section)

**Full-parse stats:**
3,592 total records across 140 episodes (100% of episodes produced ≥1 record). Per-episode mean 25.66, median 25, max 53 (C1E027), min 8 (C1E085), stddev 9.38. Category distribution: UNKNOWN_SHAPE 58.2%, scene_transition 17.7%, cumulative_anchor 10.4%, in_scene_compression 7.9%, travel_duration 5.8%. Granularity skews to unspecified (29.5%) and days (22.1%); minutes + hours = 28% of corpus. Multi-mention turn rate 4.0% (down from hand-sample 17.2% — Patch 1 dedup working at corpus scale). C1: 24.76 records/episode, C2: 27.50/episode (~11% C2 density premium). Stage 0 reject volume: 713 total (D1 OOC 347, D7 player-pass-back 186, D5 idiom 99, D2 spell-duration 62, D8 causal-since 18, D3 table-talk 1). `[EXTRACTOR_UNKNOWN]` count: 0 — source format stable.

**Validation-set:** seed=9999, n=15, stratified (cumulative_anchor 5, scene_transition 4, in_scene_compression 2, travel_duration 1, unknown_shape 3). Mechanically excluded from the 10 hand-sample episodes — sampled from 130 unseen episodes. Episodes covered: C1E016, C1E027, C1E028, C1E037, C1E038, C1E043, C1E054, C1E055, C1E091, C1E094, C1E099, C1E110, C1E113, C2E005, C2E040 (15 distinct episodes, 1 record per episode). Fresh blind data; calibration overlap 0, hand-sample overlap 0.

**Lessons doc v2 candidates:** Lessons 9 (phrase-span vs turn-level Stage 0), 10 (test patches pairwise), 11 (regex change with zero record-level effect is a diagnosis signal). Filed in `lessons_doc_v2_candidates.md` pending Ship 3 (Loot/Reward) confirmation.

**Phase 5b (validation judge session):** Jordan + Claude judge the 15 records in chat, fill `expected_category` / `verdict` / `failure_mode`, run `--validation` regression once for the authoritative published claim.

**Time-Mention ship complete pending Phase 5b validation pass.**

## Cleanup — directory restructure (2026-05-07)

Moved corpus root files to `docs/` and `eval_sets/` subdirectories on both PC and server. All five time-mention test fixtures now live in `eval_sets/`: `time_mention_eval_set_v1.json`, `time_mention_eval_set_v2.json`, `time_mention_eval_set_v2_calibration.json`, `time_mention_eval_set_v3_holdout.json`, `time_mention_validation_set_v1.json`. Patched test runner path references from `findings/` to `eval_sets/` in `test_time_mention_eval_v2.py` (EVAL_PATH, HOLDOUT_PATH, VALIDATION_PATH) and `test_time_mention_eval_v1.py` (EVAL_PATH, VALIDATION_PATH). `_construction.md` companion docs stayed in `findings/` — they document how each set was built, not the sets themselves. Verified calibration and validation regression numbers unchanged (73.8% / 73.3%). README.md updated with directory layout reference. PC mirror synced.
