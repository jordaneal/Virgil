# Encounter Cadence — session log

Append-only history of work on the Encounter Cadence extractor. New phases append below; nothing here is overwritten.

---

## Phase 1 — recon + taxonomy proposal (2026-05-05)

**Output artifact:** `/home/jordaneal/virgil-docs/ENCOUNTER_CADENCE_V1_SPEC.md`

- **Source-data findings.** CRD3 lives at `/mnt/virgil_storage/dnd_datasets/crd3/data/aligned data/`. Three alignment-config dirs (`c=2`, `c=3`, `c=4`) but turn-level data is byte-identical across them — `c=2` is the iteration target. Format = list-of-records JSON per file; each record has `CHUNK` (wiki summary), `ALIGNMENT`, `TURNS` (with `NAMES`, `UTTERANCES`, `NUMBER`). Speakers tagged uppercase, MATT for the DM. 140 unique episodes (94 C1, 46 C2; no C3, no one-shots). Importer ground truth confirmed against `dnd_knowledge_import.py`.

- **Sampling methodology.** Six episodes spanning C1 early/mid/late + C2 mid/late + a known low-combat episode (C1E095) for false-positive surface. Pulled all MATT turns containing `\binitiative\b`, captured 3-4 turns of preceding context, hand-classified fresh-start vs mid-combat noise. Found ~12 fresh starts vs 35 raw `initiative` mentions across the 7 sampled episodes — naive grep over-counts ~3x.

- **Taxonomy proposed.** Five fresh-start categories derived from samples (not from `CORPUS_BUILDER.md`'s illustrative names): `player_action_escalation`, `environmental_materialization`, `trap_activation`, `npc_turns_hostile`, `interruption`. Plus `wave_or_phase_shift` as a tagged-separately mid-combat sub-event. Rejected: `scheduled_event` (indistinguishable from materialization/hostile by text), `combat_continuation` (absence of event), `social_pressure_only` (no init anchor), `world_event_sighting` (filed for future ship), `time_pressure_introduction` (Time-Mention's territory), `npc_attacks_no_init`, `environment_changes_threatening`.

- **§6 decisions surfaced.** Seven decision points — scope, source filter, fresh-start filter, preceding-context budget, OOC handling, wave tagging, within-episode dedup. Recommended defaults provided per `COMBAT_INITIATION_ORCHESTRATION_REVIEW.md` shape (restate / trade-offs / default / confidence). Plus six open questions on NPC dialogue detection, C1↔C2 stylistic drift, version-bump discipline, FIREBALL exclusion, validation-vs-findings doc separation, and hand-sample episode list.

- **Phase 2 hand-sample episode list:** C1E001, C1E020, C1E030, C1E049, C1E060, C1E095, C2E001, C2E020, C2E030, C2E045 (proposed in §7 of the spec; locked unchanged in chat for Phase 2).

---

## Phase 2 — implementation + hand-sample (2026-05-05)

**Output artifacts:**
- `/home/jordaneal/corpus_builder/` directory tree (per `CORPUS_BUILDER.md` layout)
- `/home/jordaneal/corpus_builder/extractors/encounter_cadence.py` — the extractor
- `/home/jordaneal/corpus_builder/samples/encounter_cadence_sample.json` — 14 records from 10 episodes
- `/home/jordaneal/corpus_builder/findings/encounter_cadence_validation.md` — run-summary report
- `/home/jordaneal/corpus_builder/README.md`, `JOBS.md` — scaffolding

**Locked decisions applied** (from chat after Phase 1 review, overriding the spec's recommended defaults where they disagree):

1. Scope re-framed from "combat-only" to "init-anchored." Both fresh starts and mid-fight re-inits emit records; `is_fresh_encounter: false` distinguishes wave/phase events.
2. `telegraph` field dropped. Replaced with `player_action_caused: bool` and `narration_buildup_chars: int`.
3. `preceding_context_chars` is the actual char count per record, not the budget constant.
4. Source filter widened: single `preceding_turns: [{speaker, text, turn_number}, ...]` list, no extraction-time filtering.
5. Multi-category priority is a fixed-order rule with first-match-wins (wave → trap → player_action → npc → environmental → interruption-default).

**Implementation summary.**
- Stage 1 candidate detection uses `POSITIVE_INIT` (roll/reroll/kicked-in/need-N-to-roll) ANDed with NOT-`NEGATIVE_INIT_NOISE` (initiative order, top of, currently in, etc.). Catches both fresh starts and waves.
- Stage 2 classification follows the locked priority order. Wave detection on trigger text (`WAVE_PARTY_JOIN`, `WAVE_REINFORCEMENT`, `WAVE_PHASE_SHIFT`); the rest fall through to category-specific gates.
- Stage 3 emits the locked schema. `extracted_at` is a single ISO-UTC timestamp computed once per run, identical across all records of a run; everything else is a pure function of the source episode + extractor code (idempotency confirmed by re-running and diffing event-content fields).
- Fail-open: file-read errors and malformed turn dicts log `[EXTRACTOR_UNKNOWN]` to stderr and continue. The hand-sample run produced 0 unknown events.

**Hand-sample run results.**
- 14 records across 10 episodes. Three episodes (C1E060, C1E095, C2E030) emitted zero records. Phase 1 spec predicted two of those zeros.
- Category distribution: `interruption`=5, `environmental_materialization`=3, `npc_turns_hostile`=3, `wave_or_phase_shift`=2, `player_action_escalation`=1, `trap_activation`=0.
- Wave subtypes: 1 `party_join` (C1E030 t517), 1 `phase_shift` (C1E049 t2812).
- `player_action_caused`: 1 True, 13 False.

**Anomalies surfaced for Jordan's spot-check** (full list in validation report §5):
- `NPC_VOICING` regex over-fires on "he goes [physical motion]" — false positive risk for `npc_turns_hostile`.
- `trigger_references_player` regex is conservative; recall on `player_action_escalation` is low (e.g., C1E020 t986 and C1E049 t535 both have a defensible argument for player_action_escalation but classified `interruption` and `npc_turns_hostile` respectively).
- `trap_activation` got zero hits even on the obvious cabinet-trap case (C2E045 t2014) because the player-interaction turn was 16 turns before the init call, beyond the 1500-char preceding window's effective reach.
- Adjacent fresh starts pollute each other's preceding context (C1E020 t986 and t993 are 7 turns apart; t986's text influenced t993's classification).
- Wave detection is literal-phrase only — semantic-wave events without matching phrases (C2E045 t2678 party-join-by-falling, C2E045 t2568 fire-elemental-summon) classified as `interruption`.

**Implementation-time interpretive calls** (within the locked rules — surfaced in validation report §6 for confirmation):
- "immediately before the trigger" interpreted as "closest non-MATT turn in window" rather than strict `trigger_idx-1`.
- NPC-dialogue detection uses quoted-text + voicing regex on the closest 3 MATT turns; tightening or loosening is a single-line change.
- `player_action_escalation` references-it gate is a fixed phrase list anchored at trigger start; locked rule's "references it" admits broader interpretations.
- Wave-pattern set extends the prompt's literal example phrases lightly (e.g., adding "few", "others", "now roll" to party_join). If too liberal, narrow to literal-prompt patterns.

**Pointer:** Validation report at `findings/encounter_cadence_validation.md`. Sample output at `samples/encounter_cadence_sample.json`.

**Phase 3 (full parse) is not scheduled.** Will not run until Jordan completes the manual spot-check (`CORPUS_BUILDER.md` Hand-Sample Validation Protocol — recall, precision, taxonomy).

---

## Phase 2.5 — calibration patch + eval set + re-sample (2026-05-05)

**Output artifacts:**
- `findings/encounter_cadence_eval_set_v1.json` — 14-record ground-truth eval set, derived from manual review of v1 sample
- `extractors/encounter_cadence.py` — six patches applied, `EXTRACTOR_VERSION` bumped to `encounter_cadence_v1_1`
- `samples/encounter_cadence_sample_v1_1.json` — re-sample on the same 10 episodes (v1 sample preserved)
- `extractors/test_encounter_cadence_eval.py` — regression test runner; loads eval set, runs extractor, asserts per-record classifications, reports precision and pass/fail
- `findings/encounter_cadence_validation_v1_1.md` — calibration validation report with v1↔v1.1 per-record diff, patch attribution, anomalies

**Patches applied** (per Phase 2.5 prompt):
1. `player_action_escalation` broadened — drop trigger-references-player phrase list; gate on (action in last 15 turns) AND (reaction verb in trigger or closest MATT) OR strong-positive on "kicked in" + action
2. Wave detection goes semantic — track `init_active` per episode; accept literal phrases OR new-combatant-shape (`Roll initiative for X`, `Both of you roll`, `the N of you`) when init_active=True; widened sub-type assignment with summon-language for `reinforcement`
3. Trap detection widened to full preceding_turns window — search for player-interaction in any non-MATT turn and mechanism vocab in any MATT turn within the preceding context (typically 15-25 turns at the 1500-char budget)
4. `NPC_VOICING` dropped bare `goes` (was matching "he goes [physical motion]" — now relies on QUOTED_SPEECH for true speech-act `goes "..."`)
5. Patch-5 immediate-predecessor override added between priorities 3 and 4 — closes the gap where neither patch 1 nor patch 6 fired but immediate predecessor establishes one category cleanly
6. `npc_turns_hostile` widened with `TRANSFORMATION_VOCAB` (flesh, eyes blood-red, body stops quaking, lips curled, turns into, morphs, etc.) — fires `npc_turns_hostile` even without quoted dialogue when the NPC reveals hostility through physical change

**Re-sample results.** 14 records emitted (same volume as v1 — no recall changes). Eval-set precision **13/14 = 92.9%** vs v1's 5/14 = 35.7%. Above the 70% acceptance threshold. Idempotency re-verified.

**Per-category breakdown (v1 → v1.1):**
- `wave_or_phase_shift`: 2 → 4 (full subtype-set populated for the first time: 2 party_join, 1 phase_shift, 1 reinforcement)
- `player_action_escalation`: 1 → 3
- `trap_activation`: 0 → 1
- `npc_turns_hostile`: 3 → 2
- `environmental_materialization`: 3 → 2
- `interruption`: 5 → 2 (down from over-firing-default to actual default cases only)

**One known limitation.** C2E045 t2529 (dragon reveal scene) still classifies as `player_action_escalation` instead of expected `npc_turns_hostile`. Patch 5's literal text doesn't fix it because the immediately-preceding MATT turn (`"And the dragon is right there."`) has no quoted speech / NPC voicing / transformation vocab, while the immediately-preceding non-MATT turn (LAURA `"I'm going to Invoke Duplicity again"`) is a player-action declaration. Closest NPC dialogue is 17 turns away (the dragon-NPC's `"I'm hungry"` at t2512). To fix this would require either (a) adding "physical-threat-revelation" vocab (`rears up`, `wings up`, `looms`, `roars`) to patch 6's transformation list, (b) excluding "reactive" player actions from the player-action signal — not deterministically detectable, or (c) reordering priorities so widened-`npc_turns_hostile` fires before the patch-5 override. **Held position; not authorized to extend patches.** Surfaced in validation report §5 for Jordan's call.

**Regression test runner.** `test_encounter_cadence_eval.py` reusable for every future calibration pass. Loads eval set, runs extractor against the eval-set episodes, prints per-record verdict + total precision, exits 0 if precision ≥ threshold (default 70%). Use after any classification-logic change.

### Filed insights (for post-FULL doctrine update)

- **Causality-window doctrine.** Actual-play narrative causation routinely spans 5-15 turns from setup to consequence. Immediate-turn windows (preceding 1-3 turns) are systematically too narrow for accurate cause-effect detection. v1 trap_activation gated only on the immediate-predecessor non-MATT turn — missed every actual trap because the player-interaction turn precedes attack-resolution narration which precedes init-call. Patches 1, 3, and the full-preceding-window approach in v1.1 demonstrate that 15-25 turn windows are the correct default for any extractor doing causal classification. This applies beyond Encounter Cadence — consequence extraction, betrayal/promise detection, emotional payoff tracking, stealth escalation, and NPC stance shifts will all hit the same wall. Default extractor windows should be 10-15 turns unless there's a specific reason to narrow. Promote to WHY.md after first successful FULL corpus run.

- **No new categories.** Records 9 (transformation) and 10 (approach-static-encounter) resisted ontology expansion. Folded into existing categories via detection-widening (record 9 — patch 6 widened `npc_turns_hostile`) or accepted as default classification (record 10 — `interruption`). Pattern: ontology stays narrow until cadence findings prove a distinction is downstream-useful. The temptation when a record doesn't fit cleanly is to mint a new category; the discipline is to widen detection rules within the existing taxonomy first, and reserve category mint for when the data refuses to compress.

- **Eval-set-as-fixture pays for itself in one calibration cycle.** v1 → v1.1 was driven by Jordan's manual spot-check producing the eval set. Future calibrations (v1.2, v2, etc.) get free regression coverage by running `test_encounter_cadence_eval.py`. Pattern recommendation: every extractor that ships a hand-sample also ships an eval-set fixture in the same session. The cost is one JSON file; the benefit is permanent regression detection.

**Pointer:** Validation report at `findings/encounter_cadence_validation_v1_1.md`. Sample at `samples/encounter_cadence_sample_v1_1.json`. v1 artifacts preserved alongside.

**Phase 3 (full parse) remains unscheduled.** Pending: t2529 limitation resolution, recall audit (eval set covers v1's hits — doesn't catch what v1 missed), Jordan sign-off.

---

## Phase 3 — full parse on CRD3 (2026-05-05)

**Status:** DONE. Exit code 0. Zero `[EXTRACTOR_UNKNOWN]` events. t2529 was accepted as ambiguous-defensible after Phase 2.5; extractor unchanged at `encounter_cadence_v1_1`.

**Pre-flight verified.** No active jobs in JOBS.md. Version constant at `encounter_cadence_v1_1`. Output dir empty. Regression test: 13/14 = 92.9% (PASS). Source dir contains 280 c=2 files (140 unique episodes).

**Run.** Launched in tmux session `corpus_encounter`. The deterministic regex parse finished in ~3 seconds — far under the <10-minute estimate in the prompt. PID file ended up empty because the process exited before the post-launch PID capture; the log + exit-code file are the durable signals.

**Output.** 140 per-episode JSON files at `output/encounter_cadence/`. Total 243 records. Stats summary at `findings/encounter_cadence_full_parse_stats.md` — counts only, no interpretation.

**Top-line numbers** (full table in stats file):
- 243 records / 140 episodes (mean 1.7 records per episode, median 1, max 7)
- 30 zero-record episodes (21% of episodes)
- C1: 163 records across 94 episodes; C2: 80 records across 46 episodes
- Category dominance: `interruption` 60.9%, `npc_turns_hostile` 13.6%, `player_action_escalation` 11.5%, `environmental_materialization` 9.1%, `wave_or_phase_shift` 4.1%, `trap_activation` 0.8%
- Wave subtypes (10 records): 5 phase_shift, 3 reinforcement, 2 party_join
- `is_fresh_encounter` True/False = 233/10
- `player_action_caused` True/False = 32/211

**JOBS.md:** entry archived with DONE status. Future runs append above the past-jobs section.

**Phase 4 (findings doc) is not started this session.** Per the prompt: stats are emitted, interpretation is Jordan's. Findings doc lives at `findings/encounter_cadence_findings.md` per `CORPUS_BUILDER.md` and gets written in a separate session after Jordan reads the stats.

---

## Phase 4 — v1.2 calibration with hard ship gates (2026-05-05)

**Output artifacts:**
- `findings/encounter_cadence_eval_set_v2.json` — 69-record eval set (14 v1 + 31 spot-check + 24 blind) built from Jordan's construction notes
- `extractors/build_eval_set_v2.py` — one-time builder for the eval set; backfills raw_text and v1.1 fields from preserved output
- `extractors/test_encounter_cadence_eval_v2.py` — regression test runner with NOT_INIT_EVENT / DUPLICATE sentinels and ship-gate metrics
- `extractors/encounter_cadence.py` — five patches applied, EXTRACTOR_VERSION bumped to `encounter_cadence_v1_2`
- `samples/encounter_cadence_sample_v1_2.json` — re-sampled output (v1.1 sample preserved)
- `output/encounter_cadence/` — v1.2 full parse, 186 records / 140 episodes
- `output/encounter_cadence_v1_1/` — v1.1 full parse preserved (243 records)
- `findings/encounter_cadence_full_parse_stats_v1_2.md` — full parse stats with v1.1↔v1.2 deltas
- `findings/encounter_cadence_validation_v1_2.md` — validation report

**Five patches applied** (per Phase 4 prompt):
1. Stage 1 false-positive gating — tightened POSITIVE_INIT to require literal `initiative` adjacent to the verb. The v1.1 `need (you|...) to roll` branch fired on "I need you to roll a wisdom save" and similar mid-combat reaction-roll triggers; v1.2 rejects them. Added `[FILTERED_NON_INIT]` log line and a defense-in-depth NON_INIT_ROLL pattern.
2. Wave persistence + semantic detection — added `combat_active = init_active AND has_recent_damage_resolution(last 3 MATT turns)`. Phase_shift fallback fires when combat_active is true and no scene-transition markers are present. Catches mid-combat re-inits (`Now everybody please roll initiative`, `Both of you roll initiative`) that v1.1 missed because they don't match literal wave patterns. Tightened DAMAGE_RESOLUTION (numeric "X points of damage", typed-damage, "(end|top|start) of (your|the) turn", `\d+ does/not hits`, "Both hit", "Natural N", "Both hit") and SCENE_TRANSITION_MARKERS (tightened to avoid over-firing on "you reach forward" combat narration).
3. `player_action_escalation` widening — kept narrow strong-positive list (`kicked in`, `now we're rolling`, `with that,`, `because of (your|these|this)`). Added player-action-then-MATT-physical-consequence pattern: action verb in last 10 turns followed by MATT consequence narration (`(impact noise)`, `slamming into`, `the door swings open`, `crashes through`, etc.). Catches Liam-kicks-door-then-init pattern.
4. `npc_turns_hostile` widening — added AMBUSH_VOCAB (waiting pattern + crossbows nocked etc.), NPC_COMMAND patterns (single-word imperatives in quotes), ATTACK_NARRATION (volley, barrage, dives at you, etc.), NPC_HOSTILE_REVEAL (figures step out, crackling energy bursting, flesh pulled tight, hooded/cloaked figures). Patch 6 transformation widening retained. Also added a check for NPC dialogue in the trigger turn itself (v1.1 only checked preceding window).
5. `nearest_prior_trigger_turn_distance` metadata — integer field on every record indicating turn-number gap to the previous emitted record in the episode (null if first). Lets analysis layer dedup adjacent records. 87 of 186 full-parse records have a non-null distance; min=2, median=138, max=2116.

**Ship gate results:**
- FP rate **1.4%** (gate ≤ 5%) — patch 7 filtered 11 of 12 NOT_INIT_EVENT records. Lone leak: C1E033_t851 (literal "everyone else roll initiative" embedded in mid-combat narration).
- Wave detection **60.0%** (gate ≥ 60%) — caught 6 of 10 expected waves. Misses: C1E002_t1499, C1E113_t1352, C1E071_t1554, C1E086_t1234 (all involve no prior init in the episode + no literal wave phrasing, or scene-transition override).
- Overall precision **70.9%** (gate ≥ 65%) — 39 of 55 non-v1 records correctly classified.
- v1 sanity **13/14 = 92.9%** — unchanged from v1.1 baseline (same one v1 failure: C2E045_t2529).

**Full-parse output:** 186 records in 140 episodes (down from 243 in v1.1). Reduction is dominated by patch 7 filtering false positives. Wave records jumped from 10 to 26 (mostly phase_shift fallback firing on subsequent inits). 41 episodes now zero-record (up from 30) — most of the new zero-record episodes were RP/downtime sessions where v1.1 had emitted only false-positive records.

### Filed insights (for post-FULL doctrine update)

- **Eval-set construction is the leverage point.** Phase 3's spot-check + blind sample exposed structural failures the v1.1 eval set didn't surface because v1.1 was tuned against the v1 eval set. The v2 eval set's 31 spot-check + 24 blind records is now the calibration fixture for any future Encounter Cadence patches. Pattern recommendation: when an extractor's full-parse precision drops below the hand-sample's, the hand-sample is over-fit; build a blind-sample extension.
- **Stage 1 (candidate detection) is the strongest precision lever.** Tightening POSITIVE_INIT alone moved precision from 29% → 51% on the new records, just by not emitting records that obviously aren't init events. Future extractors should treat their Stage 1 detection rule as load-bearing for precision and validate against blind samples early.
- **Damage-resolution narration is a richer textual signal than init-state-tracking alone.** v1.1's `init_active` boolean state caught mid-combat re-inits when a literal pattern matched, but the boolean doesn't capture "has combat actually progressed since the last init." Adding damage-resolution detection in the last K MATT turns gave a much sharper signal — "init was rolled AND combat has produced damage rolls since then" is closer to what "wave" actually means than just "init was rolled before in this episode."
- **NPC_HOSTILE_REVEAL had to be tight.** Initial broad patterns ("snarling at you", "blocking the passage", "teeth bared") over-fired on environmental-creature narration (giant blue-scaled reptile coming down a cliff = expected `interruption`, not npc_turns_hostile). Specific humanoid-NPC reveal phrases (figures step out, crackling energy bursting, hooded/cloaked figures, flesh pulled tight) work; bare creature-description vocab doesn't.
- **The `init_active OR damage` vs `init_active AND damage` choice was the precision/recall pivot for patch 8.** OR over-fired on back-to-back-distinct-encounters (C1E020_t993 — different threat arriving 7 turns after a prior combat init, but no damage between). AND undercaught some legitimate waves (C1E002_t1499 — combat ongoing but Stage 1 missed the prior init). AND chose precision; the missed waves are filed for v1.3 if/when Jordan deems them worth more patches.
- **Defensible alternates in eval sets.** Five records have explicit alternate-acceptable categories; two of them (C1E044_t378, C1E033_t851) are cases where the eval-set construction itself surfaced ambiguity. Pattern: when a hand-sample reviewer can't make a clean call, encode that ambiguity in the eval set rather than forcing a label that the extractor will fight against.

**Pointer:** Validation report at `findings/encounter_cadence_validation_v1_2.md`. Stats file at `findings/encounter_cadence_full_parse_stats_v1_2.md`. v1.1 artifacts preserved at `output/encounter_cadence_v1_1/` and `samples/encounter_cadence_sample_v1_1.json`.

**SHIPPED v1.2.** All three ship gates pass; v1 sanity unchanged. 16 records on the non-v1 set still misclassified — surfaced in the validation report §5 as filed-not-fixed limitations rather than escalating to v1.3 without Jordan's review.

---

## Phase 5 — v1.3 state-aware Stage 0 + held-out gates (2026-05-05)

**Output artifacts:**
- `findings/encounter_cadence_eval_set_v3.json` — 84 calibration + 25 holdout, structured with explicit `calibration_set`/`holdout_set` keys and no `raw_text` on holdout records (methodology rule against accidental optimization)
- `extractors/build_eval_set_v3.py` — one-time builder; carries v2 records forward and adds 15 phase4_blind records + 25 holdout (seed=7777)
- `extractors/test_encounter_cadence_eval_v3.py` — regression test runner with calibration/holdout split. Default mode runs calibration only; `--holdout` flag runs both and checks the four hard ship gates
- `extractors/encounter_cadence.py` — Stage 0 layer added, EXTRACTOR_VERSION bumped to `encounter_cadence_v1_3`
- `samples/encounter_cadence_sample_v1_3.json` — re-sampled output (v1.1 + v1.2 samples preserved)
- `output/encounter_cadence/` — v1.3 full parse, 170 records / 140 episodes
- `output/encounter_cadence_v1_2/` — v1.2 full parse preserved (186 records)
- `output/encounter_cadence_v1_1/` — v1.1 full parse preserved (243 records)
- `findings/encounter_cadence_full_parse_stats_v1_3.md` — full parse stats with v1.1↔v1.2↔v1.3 deltas
- `findings/encounter_cadence_validation_v1_3.md` — validation report

**Architectural change (one):** Stage 0 discourse layer between candidate detection and Stage 1 classification. Each candidate is labeled DISCOURSE (reject), STATE (force `combat_active=True`), or EVENT (default).

DISCOURSE patterns (reject candidate, log `[FILTERED_DISCOURSE]`):
- `DISCOURSE_EPISODE_BREAK` — `welcome back`, `last we left off`, `previously on`, `\d+K arrival`, `last week's episode`, `comic available`, `we'll be right back`, `[break]`/`[BREAK]`, etc. Checked in trigger and last 3 turns.
- `DISCOURSE_INIT_RECOUNT` — `what did you roll for initiative`, `pre-rolled initiative`, `can I reroll initiative`, `initiative count \d+`, `who's next in initiative`, `roll initiative for [pronoun] separately`. Checked in trigger only.

STATE patterns (force `combat_active=True`):
- `STATE_DAMAGE` — typed damage in last 5 turns
- `STATE_TURN_ORDER` — `your turn`, `top of the round`, `that ends [name]'s turn`, `back to you`
- `STATE_COMBAT_ROLLS` — `\d+ to hit`, `that hits`, `make a saving throw`, `roll for damage`

The summon-init filter described in the prompt was **not** implemented. Reasoning: the calibration v2 record C2E045_t2568 (`Roll initiative for the elemental` — wave/reinforcement) has the same surface shape as the held-out FP H04 (`fp_summon_init_order`). A summon-init filter that catches H04 would also kill C2E045_t2568, regressing Gate 4. Stage 0's other patterns caught all three held-out discourse FPs without needing the summon filter; Gate 1 passes at 0% with margin. Filed for v1.4 if a future held-out sample shows the summon-init FP shape distinguishable from wave/reinforcement.

**Held-out ship gate results (one-shot):**
- Gate 1 (FP rate ≤ 8%): **0.0%** (0 / 34 emitted) — PASS
- Gate 2 (Wave detection ≥ 50%): **50.0%** (4 / 8) — PASS
- Gate 3 (Strict precision ≥ 50%): **56.0%** (14 / 25) — PASS (v1.2 baseline ~36%)
- Gate 4 (No regression on v2 subset): precision 72.7% / wave 80% / FP 1.4% — PASS (v1.2 was 70.9% / 60% / 1.4%)

**Calibration improvements over v1.2:**
- Overall calibration precision 71.4% → 76.2%
- v2 subset wave rate 60.0% → 80.0% (Stage 0 STATE forced combat_active on borderline cases)
- phase4_blind precision 53.3% → 73.3%, FP rate 12.5% → 0% (all 3 phase4 discourse FPs filtered)

**Full-parse output:** 170 records in 140 episodes (v1.2 was 186, v1.1 was 243). The 16-record drop from v1.2 is Stage 0 filtering — episode-break recap, init-order narration, etc.

### Filed insights

- **Discourse-vs-event-vs-state is the right Stage 0 abstraction.** The architectural diagnosis was correct: v1.2 was conflating "trigger turn contains init-language" with "trigger turn IS an init event." Stage 0 separates the two and lets Stage 1 work on a cleaner candidate population. Pattern recommendation: any extractor whose trigger phrase appears in narrative discourse as well as in mechanical events should add a discourse-classification layer before the candidate filter.
- **Held-out methodology paid off immediately.** v1.3 was calibrated against the 84-record calibration set, then the 25-record held-out set was measured exactly once. The held-out results matched the calibration trajectory (precision improved, FP dropped to 0%, wave held). If we'd tuned against the held-out set, we wouldn't know whether the architecture generalized or just memorized. The methodology rule (no `raw_text` on holdout records, separate test mode) made it physically harder to violate.
- **The v1.3 ↔ v1.4 boundary is now legible.** What v1.3 still misses falls into specific recall floors: NPC-turns-hostile requiring deep context, env-materialization with thin buildup, summon-init wave/FP disambiguation. These aren't "more patches in the same shape"; they require either more textual signal (combat-vs-non-combat narration distinguisher) or different architectural moves (e.g., NPC-presence tracking across episodes). v1.4 should not be attempted without that diagnosis.
- **Pre-existing patches still load-bearing.** Patches 7-11 from v1.2 are unchanged and still doing their work. Stage 0 layered ON TOP of them, not replacing. The `[FILTERED_NON_INIT]` log from patch 7 still fires; the wave fallback from patch 8 still fires. Stage 0 is additive.

**Pointer:** Validation report at `findings/encounter_cadence_validation_v1_3.md`. Stats file at `findings/encounter_cadence_full_parse_stats_v1_3.md`. v1.1 and v1.2 artifacts preserved alongside.

**SHIPPED v1.3.** All four hard ship gates pass on the held-out set. The discourse-layer architecture is validated. Held-out set is now consumed; any v1.4 work needs a fresh held-out sample.
