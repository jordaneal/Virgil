# Cross-Extractor Analysis — Findings (v1.0)

**Ship:** Track 5, Ship 5 — Cross-Extractor Analysis Pipeline
**Source corpus:** CRD3 c=2 alignment, 140 unique episodes (94 C1, 46 C2)
**Source extractors:** Encounter Cadence v1.3, Time-Mention v1.3, Loot/Reward v1 (Phase 3.6), Compression Cadence v1p4
**Combined record count:** 4,751 across the four source sets
**Date completed:** 2026-05-13

This is **not** a new extractor. It is an analysis pipeline joining four shipped Track 5 extractors' record sets to answer research questions that single-extractor architecture cannot reach. The pipeline produces seven X-question answers (X1–X7) plus one reframed question (X3 → X3b) and a unified per-episode event-stream view of the corpus.

---

## 1. Questions asked

Seven cross-extractor research questions, derived from the four prior ships' §9 deferred-question inventories plus one new question visible only from the cross-extractor vantage point.

**X1.** What is the per-episode total scene-boundary count when EC inits, CC compressions, and TM scene_transitions are unified and deduped? How does it compare to CC's single-extractor 2.97 compressions/episode? (Closes CC-X2.)

**X2.** When Matt compresses a scene with scope=scene_exit, what kind of context opens the next scene? Player declaration, NPC arrival, environmental description, Matt-narrated frame-set. (Closes CC-X1.)

**X3 [rejected as filed] / X3b [directional flip].** Original X3: what fraction of LR rewards follow an EC perception/investigation/insight buildup at any distance within the same scene? Rejected — EC's taxonomy contains no perception/investigation categories. Replaced by X3b: do LR quest-offers precede EC combat-initiations? (Closes LR-X1 with reframed question.)

**X4.** What's the rate of episodes where expected payoff didn't fire? Unified across LR-X2 (buildup-without-reward) and CC-X3 (high-tension-without-compression).

**X5.** How much does EC join expand TM's `is_combat_state` flag from its current 0.3%? (Closes TM-X1.)

**X6.** Which extractor's record counts drive the C2 39% density delta over C1? Or is the delta CC-specific? (Closes CC-X4.)

**X7.** Do events from EC, TM, LR, CC cluster temporally within episodes, or distribute independently? Event-clustering shape; question visible only from cross-extractor vantage point.

Three source-ship questions remain open as future work: TM-X2 scene_transition cross-extractor primary signal validation (partially addressed in X1's TM+CC co-occurrence finding); LR-X3 offer/delivery cross-episode pairing (deferred to Phase 3 per §13.6); LR-X4 currency magnitude distribution by episode-position and campaign (not a cross-extractor question, can be answered single-extractor).

---

## 2. Method

**Phase walk.** Phase 1 produced the cross-extractor framework spec, locking seven §13 decisions in chat. Phase 2 produced the foundation: schema normalization, LR extension to 140-episode coverage, CC merge of handsample + recon records, unified JSONL record list (4,751 records), per-episode event-stream files (140 files), and a 5-episode hand-sample review. Phase 2.5 produced X1, X3, X4, X5 scripts with pre-X4 inline check on the 14 zero-CC episodes informing X4 rule design. Phase 2.6 produced X2, X3b, X6, X7 scripts plus the X3b directional flip.

**Decisions locked at Phase 1 §13.**
- §13.1 (b): per-pair intersection scope (each X-question uses the intersection of its required sources only)
- §13.2 (a): JSONL unified record format
- §13.3 (c): per-question configurable proximity window, default 15 turns
- §13.4 (a) modified: TM scene_transition as scene-boundary fence + EC-init reinforcement (load-bearing fence layer with belt-and-suspenders)
- §13.5 (c): parallel rule-based + statistical detection for negative-signal questions, kept as separate output columns
- §13.6 (a): LR-X3 (offer/delivery cross-episode pairing) deferred to Phase 3 of this ship, not pursued in Phase 2.x
- §13.7 (a): one unified findings doc

**Coverage normalization.**
- EC and TM: 140 episodes (original full-parse). EC fires only on 94 episodes (the other 46 are talk-heavy with no combat).
- LR: 123 episodes originally; Phase 2 re-ran the locked Phase 3.6 extractor on the 17 mechanically-excluded handsample+recon episodes (78 additional records). LR total: 552 records across 140 episodes.
- CC: 123 episodes originally; Phase 2 merged the existing handsample (42 records) and recon (30 records) record sets without re-extraction. CC total: 437 records across 126 episodes (C1E114 contributes 0 records as documented).

**Per-pair intersections.**
- EC × TM: 94 episodes
- EC × LR: 92 episodes
- EC × CC: 82 episodes
- TM × LR: 134 episodes
- TM × CC: 126 episodes
- LR × CC: 120 episodes
- All four: 80 episodes

**Failure mode discipline (§7 from Phase 1 spec).** Five named failure modes monitored throughout: F1 cross-scene proximity bleed (mitigated by TM scene_transition fence layer); F2 episode-coverage asymmetry blurring (mitigated by per-pair intersections); F3 single-extractor known FPs propagating (documented in §10); F4 single-extractor known under-coverage propagating (documented in §10); F5 turn-number alignment artifacts (Phase 2 hand-sample verified no alignment artifacts; co-occurring records are true co-occurrences).

**Eval-set construction.** No new eval set was constructed for this ship. Cross-extractor analyses inherit per-source reliability from each source ship's eval-set numbers, with the uncertainty-multiplication caveat documented in §10.

**No LLM in execution path.** All transformations deterministic — schema normalization, proximity joins, rule-based and statistical detection. Consistent with prior ships' constraint.

---

## 3. Reliability — read this before quoting any number below

Cross-extractor reliability is fundamentally different from single-extractor reliability. Two compounding factors:

**Uncertainty multiplication.** Each X-question's results inherit reliability from at least two source extractors. EC × LR joins, for example, multiply EC's ~80-90% strict precision (held-out) against LR's 68% strict precision (validation), producing a joined-record reliability of approximately 55-60% under independence assumption. This is the per-record uncertainty floor; aggregate findings (rates, distributions) are more robust than per-record claims.

**Source-coverage asymmetry.** EC fires on 94 of 140 episodes. Any X-question involving EC operates on a 94-episode subset, not the full corpus. The 46 EC-silent episodes are not "no signal" — they are "EC's taxonomy did not produce any record." Aggregate rates computed against EC-covered episodes only.

**Per-X reliability summary:**

| X-question | Source-pair | Records analyzed | Aggregate reliability | Per-record reliability |
|---|---|---:|---|---|
| X1 | All four | 687 merged clusters | High (counting + dedup) | N/A (no per-record claim) |
| X2 | TM × CC | 292 CC scene-exit | Medium (depends on TM and CC record correctness) | ~50-55% |
| X3 | EC × LR | 370 LR records | High (null result robust to mid-range error rates) | N/A |
| X3b | EC × LR | 61 QUEST_OFFER records | Low (n=5 matches) | High per-match (5/5 spot-check verified) |
| X4 | All four | 23 candidate episodes | Medium (rule + stat both validate) | Medium |
| X5 | EC × TM | 2,408 TM records | High (counting expansion) | High per-flip (10/10 spot-check verified) |
| X6 | All four | 140 episodes per source | High (aggregate ratio) | N/A (no per-record claim) |
| X7 | All four | 109 clusters, 80 episodes | High (independence test) | N/A |

**Sharpened claim language for downstream consumers:**

> Cross-extractor pipeline produces aggregate findings (rates, distributions, ratios) at publishable reliability. Per-record cross-extractor joins inherit multiplicative uncertainty from source extractors and should be treated as directional signal, not authoritative classification. Quote the aggregate; caveat the individual record.

The X1 unified scene-boundary count and X6 campaign delta are the most directly-publishable aggregate findings. X3's null result and X7's null result are both robust to mid-range source-extractor error rates. X4's 23 negative-signal candidates and X3b's 5 matches are the smallest-n findings and carry the largest interpretation caveats.

---

## 4. Headline findings

### X1 — Unified scene-boundary count: 8.59 per episode (2.9× CC alone)

| Metric | Value |
|---|---:|
| Episodes (all-four intersection) | 80 |
| Total merged scene-boundary clusters | 687 |
| Mean per episode | 8.59 |
| Median per episode | 9 |
| Max per episode | 24 |
| CC single-extractor baseline | 2.97 |
| **Unified vs CC alone** | **2.89× higher** |

**Cluster source-composition:**
- 1-source clusters: 604 (87.9%)
- 2-source clusters: 83 (12.1%) — **all TM+CC**
- 3-source clusters: 0
- 4-source clusters: 0

EC scene-boundaries never co-occur with CC or TM boundaries at the 3-turn dedup window. EC×TM = 0 and EC×CC = 0 across 80 episodes. The only co-occurring pair is TM+CC.

**Two-reading on the zero EC co-occurrence:**

(a) Structural separation. EC fires on encounter initiation (combat start, environmental danger) — events that **open** scenes. CC compressions and TM transitions fire when scenes **close**. They operate on opposite ends of scene structure, not coincident moments. Zero co-occurrence is the expected signal under this reading.

(b) Window-design confound. EC at scene-init turn N corresponds to a CC scene-exit on the *prior* scene, many turns earlier. The 3-turn dedup window cannot bridge that gap.

Both true simultaneously. The finding is real (EC and CC/TM operate on different scene-shape phases); the window design is an additional confound that doesn't invalidate it.

**Track 4 takeaway:** corpus-level scene activity is ~3× the CC single-extractor view. Scene Lifecycle v1 should baseline on ~8.6 boundaries/episode, not ~3.

### X2 — Post-compression next-scene-opening: 86% silent

| Opening type | Count | % |
|---|---:|---:|
| quiet_extended_scene | 251 | 86.0% |
| in_scene_compression | 13 | 4.5% |
| time_anchor_set | 11 | 3.8% |
| reward_delivery | 8 | 2.7% |
| travel_montage | 7 | 2.4% |
| quest_offer | 1 | 0.3% |
| combat_initiation | 1 | 0.3% |

86% of CC scene-exits are followed by 30+ turns of no extractor signal from the other three sources. **This is not a pipeline gap.** Scene-openings consist of Matt-narrated frame-set, player turns, and NPC dialogue — none of which are targeted by EC, LR, or TM detection. The 86% is the expected baseline for scene-openings that don't begin with a reward delivery, combat initiation, time mention, or another compression.

The **directly-publishable finding is the 14% that does fire**: when an extractor signal does follow a CC scene-exit within 30 turns, it skews toward more compression-flavored events (in_scene_compression 4.5% + time_anchor_set 3.8% + travel_montage 2.4% = 10.7%, or 76% of the non-quiet 14%).

**Compression begets compression.** When Matt cuts, he tends to continue cutting before stabilizing the next scene. This is a real Track 4-shippable pattern.

**CC-category × opening-type:**
- OVERNIGHT_REST (165 records) → quiet 87%, time_anchor_set 5%
- LOCATION_DEPARTURE (81 records) → quiet 84%, reward_delivery 6%
- TEMPORAL_MONTAGE (32 records) → quiet 88%, in_scene_compression 13%

Each CC category's quiet-rate is within 4pp of the corpus mean. Compression begets compression generalizes across categories.

### X3 — Reframed as X3b: LR quest-offers precede EC combat at 8.2% (n=5)

**X3 (original) rejected.** LR-X1's Phase 1 framing assumed EC's taxonomy carried perception/investigation/insight signals. EC's actual taxonomy: interruption, npc_turns_hostile, wave_or_phase_shift, player_action_escalation, environmental_materialization, trap_activation. **All six categories are combat-onset signals.** EC has no perception/investigation categories. The X3 join produced 0.3-0.5% match rates across windows 8-40 — the question as filed was unanswerable.

**X3b (directional flip) tested.** Hypothesis: LR quest-offers precede EC combat-initiations (the offer triggers the encounter, not the reverse).

| Window | Matches | Rate (over 61 QUEST_OFFER records) |
|---|---:|---:|
| 25 turns | 1 | 1.6% |
| 50 turns | 5 | 8.2% |
| 100 turns | 5 | 8.2% |
| Control: direction=delivered, w=25 | 3 / 309 | 1.0% |

8.2% offered-direction vs 1.0% delivered-direction control: the directional signal exists (~8× ratio). EC categories of matches: interruption (4), npc_turns_hostile (1).

**The C1E108 concentration is a data-quality flag.** 4 of 5 matches come from C1E108 (multiple QUEST_OFFERs at turns 17-18 all matching one combat at turn 57). Dropping C1E108 brings the rate to 1/61 = 1.6%, statistically indistinguishable from the delivered control.

**Verdict:** directionally suggestive but corpus evidence too thin for publishable claim at this sample size. The control comparison (8× ratio between offered and delivered) is the more meaningful finding than the absolute rate.

### X4 — Negative-signal rate: 23 candidates across 140 episodes

| Classification | Count |
|---|---:|
| no_flag | 103 |
| lr_x2_absence | 20 |
| stat_outlier_only | 14 |
| climactic_hold_combat | 2 |
| climactic_hold_reward | 1 |
| dropped_negative_rule | 0 |

**The 20 lr_x2_absence is the headline.** 22% of EC escalation events (interruption, npc_turns_hostile categories) have no LR reward within 25 turns same-scene. Closes LR-X2 from the Loot/Reward findings doc: combat events do not reliably produce rewards in the immediate-aftermath window.

**Climactic-hold candidates (3):**
- climactic_hold_combat: C1E114 (the canonical C1 finale), C1E076
- climactic_hold_reward: C1E108

C1E108 reframes the climactic-hold pattern: it's not just combat-arc held-scenes (the CC findings doc focused exclusively on this via C1E114). Reward-arc held-scenes also exist — LR ≥ 5 with late_frac ≥ 0.3 + CC = 0 indicates Matt sustaining a multi-beat reward delivery without compressing.

**14 stat-only flags = rule-precision validation.** §13.5 (c) parallel detection caught 14 episodes flagged by statistics but rejected by the rule system's `cc > 0` guard. Decomposed into three sub-patterns: TM-excess (6), LR-excess (5 where CC was also firing actively), late-quarter activity concentration (4 where CC was firing). None of these are missed Q6 candidates — they are correctly-rejected stat anomalies. The parallel-detection design proves the rule system is precise, even when stats fire.

**Rule-vs-stat disagreement breakdown (26 episodes):**
- Rule-only flags: 12 (mostly lr_x2_absence)
- Stat-only flags: 14 (all validated as rule-rejected anomalies)
- Both: 11 (mostly lr_x2_absence with statistical confirmation)

### X5 — TM combat-state expansion: 0.5% → 2.2% (4× expansion)

| Metric | Value |
|---|---:|
| Baseline TM `is_combat_state=True` | 12 (0.5%) |
| EC-join expanded combat-state | 52 (2.2%) |
| New flips | +40 |
| TM_UNKNOWN flips | 27 of 40 |

The 0.3% baseline TM combat-state rate documented in TM's findings doc is corrected to 2.2% with EC join. Still far below real combat-state frequency — but the cross-extractor mechanism works and the directionally-correct signal is preserved.

**TM_UNKNOWN getting 27 of 40 flips is the structural finding.** Those are TM records that fired (detected a time-bearing phrase) but didn't classify (UNKNOWN_SHAPE bucket, 58.2% of TM records). EC join contextualizes them as combat-state — they are time-mentions occurring during combat that TM's single-extractor architecture couldn't categorize. The cross-extractor pipeline rescues classification signal from a category TM single-extractor explicitly designed as "flagged for human review."

**Per-category expansion table:**
- TM_UNKNOWN: 0.5% → 2.4% (+27 flips)
- scene_transition: +4
- cumulative_anchor: +3
- in_scene_compression: +3
- travel_duration: +3

All 10 spot-checked flips verified clean in episode streams.

### X6 — Campaign density delta: TM largest absolute, EC and CC tied largest ratio

| Source | C1 rec/ep | C2 rec/ep | C2/C1 ratio |
|---|---:|---:|---:|
| EC | 1.63 | 2.16 | 1.32× |
| CC | 3.14 | 4.12 | 1.31× |
| LR | 3.91 | 4.53 | 1.16× |
| TM | 24.76 | 27.50 | 1.11× |

**EC and CC tied at 1.31-1.32× ratio** is the cleaner cross-source confirmation that **C2 ran tighter on combat-and-compression beats specifically**, not on time-mentions or rewards. Matt's increased pacing density in C2 expressed primarily as more frequent compressions and more frequent encounter initiations per episode, not as faster time-mention rhythm or denser reward delivery.

**TM largest absolute delta** (+2.74 records/ep) driven by scene_transition (1.24×) and cumulative_anchor (1.22×). TM's in_scene_compression slightly contracts (0.89×) — Matt narrates fewer mid-scene time-passages in C2, consistent with the more-frequent-scene-boundary picture.

**CC delta refinement.** Single-extractor CC findings reported 39% C2/C1 density delta (123-episode pool). On the extended 140-episode set (handsample + recon merged), the delta compresses to 31.1%. The handsample + recon episodes were proportionally more C1-heavy, pulling C1's rate up when added. The 31.1% figure is the corrected number for downstream consumers; the 39% from the CC findings doc was correct for the pool used at that time.

### X7 — Event clustering: null result (Z=0.13)

| Metric | Value |
|---|---:|
| Total clusters observed | 109 |
| Mean per episode | 1.36 |
| Max per episode | 7 |
| Zero-cluster episodes | 27 |
| Permutation baseline | 108.2 (±6.3) |
| **Excess vs independence** | **+0.8 (Z=0.13)** |
| 4-source clusters | 0 |
| 3-source clusters | 5 |

**Inter-extractor temporal clustering is statistically indistinguishable from independent-event expectation.** Permutation test under random source-label assignment produces 108.2 expected clusters; observed is 109 (+0.8, Z=0.13). Not significant at any conventional threshold.

**Two readings:**

(a) Matt doesn't coordinate scene-boundary signals across detection types. Each extractor fires on its own narrative surface; cross-extractor co-occurrence is whatever random co-incidence produces. Matt's DM style doesn't structure narrative such that, e.g., reward delivery and compression and combat initiation pile up at scene-arc moments.

(b) The 15-turn cluster window is too tight. Coordinated signaling may operate at scene-arc scales (50-100 turns) that this window can't capture.

(a) is the directly-testable interpretation given the experiment design. (b) is a v2 question.

**Source-pair participation:** TM dominates all pair combinations (TM+CC=64, TM+LR=43, EC+TM=5) because TM has ~25× the record density of EC. This is a counting confound, not a signaling finding.

---

## 5. Reframes worth highlighting

Two findings required revising the Phase 1 framing:

**X3 → X3b.** Phase 1 §1 inherited LR-X1 from the LR findings doc verbatim: "what fraction of LR rewards follow an EC perception/investigation/insight buildup." The question assumed EC's taxonomy carried perception/investigation/insight signals. Cross-extractor verification (X3 Check A) confirmed EC has no such categories — its six-category taxonomy is exclusively combat-onset. The X3 join produced ~0% match rate not because Matt doesn't telegraph rewards, but because the question was unanswerable as filed.

X3b (the directionally-flipped question) produced a thin but directionally-meaningful signal at 8.2% offered-direction vs 1.0% delivered-control. The reframe took ~20 lines of code and preserved the cross-extractor pipeline's value on this question, but the lesson is: **research questions filed in source ships' §9 should be re-validated against actual cross-extractor schema before Phase 1 locks them**. See §7 Tier 2 candidate.

**X2's 86% quiet is structural baseline, not pipeline gap.** Phase 2.6 Code reporting framed the 86%-quiet finding as "a pipeline coverage gap: the next scene's opening content isn't captured by EC, LR, or TM signal." Pushing back: 86% is the expected baseline. Scene-openings consist of Matt-narrated frame-set, player turns, and NPC dialogue — none of which are extractor-targeted events. The directly-publishable finding is the 14% that does fire: **compression begets compression**. Matt's most common post-compression next-event when one fires is another compression-flavored event (10.7% of the 14%, or 76% of non-quiet openings).

---

## 6. Failure mode observations

Five named failure modes from Phase 1 §7. Observed incidence:

**F1 cross-scene proximity bleed.** Mitigated successfully by TM scene_transition fence layer (§13.4). X3b spot-check verified all 5 matches respected scene fences. No F1 incidents observed in spot-checks.

**F2 episode-coverage asymmetry blurring counts.** Handled by per-pair intersection scope (§13.1). All X-question reports declare their pair scope explicitly. EC's 94-episode coverage was the binding constraint for X1 (80 episodes), X5 (94), X7 (80).

**F3 single-extractor known FPs propagating.** Observed in X3b: 4 of 5 matches came from a single episode (C1E108), which is a known C1E108 structural feature (multi-offer episode opening). The findings doc documents this as a data-quality flag rather than a corpus pattern.

**F4 single-extractor known under-coverage propagating.** Observed in X3 (rejected): EC's exclusion of perception/investigation categories propagated forward as 0% match rate. The pipeline correctly surfaced this as a question-misspecification, not a Matt-pattern finding.

**F5 turn-number alignment artifacts.** Verified clean in Phase 2 hand-sample. Observed F5 candidates in X1 (TM+CC identical-turn co-occurrences) all verified as true co-occurrences in stream spot-check.

---

## 7. v3 lessons-doc candidates filed

Two candidates filed for `lessons_doc_v3_candidates.md` Tier 2 (single-ship evidence, architectural form is general — promote at next v3 review if a second cross-extractor ship surfaces the same pattern).

### Candidate 24 — Phase 1 hypotheses must be validated against actual extractor taxonomies

**Source ship:** Cross-Extractor (X3 rejection, replaced by X3b).

**Pattern.** Cross-extractor research questions inherited verbatim from source ships' §9 deferred-question inventories may be unanswerable as filed when the inheriting question's premise depends on extractor capabilities the source ship's findings doc didn't enumerate. LR-X1 assumed EC's taxonomy carried perception/investigation/insight signals (a reasonable assumption from outside EC's findings doc); cross-extractor verification revealed EC's six categories are exclusively combat-onset. The X3 join produced ~0% match rate not because Matt doesn't telegraph rewards, but because the question was unanswerable.

**Forward rule.** Phase 1 specs for cross-extractor analysis ships must include an explicit verification step: each X-question's required source-extractor categories listed and confirmed against the source extractors' actual category lists. The verification step lives in Phase 1, not Phase 2 — catching this before Phase 2 spends effort building joins for unanswerable questions.

**Why Tier 2.** Single-ship evidence. The lesson is general (any future cross-extractor pipeline should run this verification) but the empirical demonstration is X3 alone. Promote to Tier 1 if a second cross-extractor ship surfaces an analogous misspecification.

### Candidate 25 — Cross-extractor proximity windows should be set against per-source category-density baselines

**Source ship:** Cross-Extractor (X3b's window-scaling, X4's rule-window selection).

**Pattern.** §13.3 (c) locked configurable per-question windows with a 15-turn default. X3b showed the signal rate jumps from 1.6% at 25t to 8.2% at 50t and is flat thereafter — the 15-turn default would have understated the signal. X4's R3 rule used 25 turns by default; the actual rule's sensitivity to that window wasn't tested before publication. Cross-extractor proximity windows interact with per-source category density: sparse sources (EC at 1.21/ep) need wider windows than dense sources (TM at 25.7/ep).

**Forward rule.** Phase 1 specs for cross-extractor analysis ships should set proximity-window defaults per source-pair, not globally. Window default = ~3-5× the typical inter-record turn-distance for the sparser source in the pair. Phase 1 spec should include a per-pair table of recommended windows derived from source-extractor record density.

**Why Tier 2.** Single-ship evidence. The lesson is mechanical (window-tuning against record density is good practice) but the empirical demonstration here is two X-questions. Promote if a second cross-extractor ship's results materially change at window-tuning.

---

## 8. What this enables for Track 4

Four directly-shippable findings for Virgil's Scene Lifecycle v1:

**Corpus scene-density baseline: 8.59 scene-boundaries per episode.** This is 2.89× the CC single-extractor view. Scene Lifecycle v1 should baseline on ~8-9 boundaries per episode, not the CC alone number of ~3. The 87.9% single-source cluster rate means most boundaries are detected by one extractor only — the lifecycle needs to integrate all four detection surfaces.

**Compression begets compression.** When Matt cuts (CC scene_exit), the next extractor signal within 30 turns is most commonly another compression-flavored event (10.7% in_scene_compression / time_anchor_set / travel_montage; 76% of non-quiet openings). Scene Lifecycle should expect compression clusters, not isolated single-compression scenes.

**Reward delivery is decoupled from immediate combat aftermath.** 22% of EC escalation events have no LR reward within 25 turns same-scene (X4 lr_x2_absence). The Scene Lifecycle shouldn't assume combat → reward as the dominant pacing pattern; rewards are distributed independently of combat resolution.

**C2 ran ~30% denser per episode on combat and compression specifically.** EC and CC C2/C1 ratios at 1.31-1.32× confirm the C2 pacing acceleration is structural to encounter-and-compression beats, not corpus-wide. Track 4's campaign-arc-aware design should expect this density delta on combat and compression rates, modest on time-mentions and rewards.

Two structural findings useful but not directive:

**Inter-extractor temporal coordination is not detectable at the 15-turn scale.** Matt's narrative structure doesn't pile multiple detection-type signals at coordinated moments. Each extractor operates on its own surface.

**Three climactic-hold candidates** (C1E114, C1E076, C1E108) form a small but structurally meaningful set of episodes where Matt sustained scenes that other ships would have compressed. C1E108 specifically extends the climactic-hold pattern from combat-arc to reward-arc — a multi-beat reward delivery held without scene compression. Worth flagging as named structural examples in Track 4 design.

---

## 9. Open questions

1. **LR-X3 — quest offer → delivery cross-episode pairing.** Deferred to Phase 3 per §13.6. Filed for future work; whether to pursue depends on post-Track-5 playtest evidence about quest-arc-completion gaps in Virgil.

2. **X7 at extended cluster windows.** The 15-turn cluster window produced null result. v2 question: does coordination signal appear at scene-arc-scale (50-100 turn) windows? Re-running X7 with wider clustering would answer.

3. **TM-X2 — scene_transition as cross-extractor scene-boundary primary signal.** Partially addressed in X1 (TM scene_transition is one of the three boundary-detection sources). Full TM-X2 framing would require comparing scene-segmentation built on TM scene_transition alone vs. the unified X1 three-source segmentation, with downstream impact analysis.

4. **X3b at corpus scale.** X3b's 8.2% rate over 61 QUEST_OFFER records is thin. Whether the offered→combat pattern generalizes requires a corpus with more quest-offer records. CRD3 may not provide enough; cross-campaign analysis (C1+C2+C3 if/when c=2 alignment becomes available for later seasons) would help.

5. **X2 quiet-bucket decomposition.** The 86% quiet bucket is structurally consistent with scene-openings that don't fire any extractor. A future ship could split this with NPC-introduction detection, narrator-frame-set detection, or player-action detection extractors that would land in the next Track 5 extractor wave.

6. **Climactic-hold structural pattern.** Three candidates in this corpus (C1E114, C1E076, C1E108). The pattern is real but n is too small for confident structural claims. Future cross-extractor work or a dedicated climactic-arc extractor could measure prevalence at scale.

---

## 10. Limitations

1. **Cross-extractor uncertainty multiplication.** Per-record claims inherit multiplicative uncertainty from source extractors (X2's ~50-55% per-record reliability; X4's medium per-candidate reliability). Aggregate claims are more robust than per-record claims. Quote the aggregate.

2. **C1E108 outlier effect on X3b.** Without C1E108, X3b's rate drops from 8.2% to 1.6%. The directional finding (8× ratio between offered and delivered-control) holds, but the absolute rate is single-episode driven. Treat as suggestive, not authoritative.

3. **EC's 94-episode coverage is the binding source-coverage constraint.** Any X-question involving EC operates on 80-94 episodes, not 140. Aggregate rates computed against EC-covered subset only.

4. **Source-extractor known FPs propagate.** EC's `interruption` catchall (41% of EC records), TM's UNKNOWN_SHAPE bucket (58.2%), CC's OVERNIGHT_REST polysemy (validation 33% strict on OR), LR's heterogeneous category precision (66.7% validation strict overall) all carry forward into cross-extractor results. X-question findings caveat each affected join.

5. **3-turn dedup window in X1.** EC scene-init records never co-occur with CC or TM boundaries at this window. The interpretation is partly structural (EC opens scenes, CC/TM close them) and partly window-design confound (EC at scene N might match CC at scene N-1's exit, beyond 3 turns). The unified scene-count of 8.59 is robust to this; the 87.9% single-source rate is partly a window-design artifact.

6. **X4 negative rules sensitivity.** The combat-dense override and low-activity override correctly suppressed 5 of 14 zero-CC episodes per the pre-X4 inline check. The override thresholds (EC ≥ 2 with phase-shift/wave/env_mat; source-counts below 25th percentile) are empirically tuned, not theoretically derived. Different thresholds would produce different climactic-hold candidate counts.

7. **X7 permutation test under independence assumption.** The null hypothesis is that source labels are independently distributable across events. This is the correct null for inter-extractor signal coordination. Z=0.13 is robust evidence against coordination at the 15-turn scale, but extending the cluster window would test a different hypothesis (scene-arc-scale coordination).

8. **No new eval-set for cross-extractor pipeline.** Reliability inherits from source ships. No blind held-out validation was constructed for cross-extractor joins specifically. Per §13.5 discipline, rule + statistical detection both ran on the same 140-episode corpus.

9. **Source corpus is CRD3 c=2 alignment only.** Inherited constraint from all four source ships.

---

## 11. Files

| Artifact | Path |
|---|---|
| Phase 1 spec | `corpus_builder/findings/track5_cross_extractor_analysis_phase1_spec.md` |
| Unified record JSONL | `corpus_builder/cross_extractor/all_records_unified.jsonl` |
| Per-episode event streams (140 files) | `corpus_builder/cross_extractor/streams/{episode}.json` |
| Schema normalizer | `corpus_builder/cross_extractor/normalize_schema.py` |
| Shared utilities | `corpus_builder/cross_extractor/x_utils.py` |
| X1 script + results | `corpus_builder/cross_extractor/analysis_x1.py`, `results/x1_unified_scene_boundaries.{md,csv}` |
| X2 script + results | `corpus_builder/cross_extractor/analysis_x2.py`, `results/x2_compression_next_opening.{md,csv}` |
| X3 script + results (rejected) | `corpus_builder/cross_extractor/analysis_x3.py`, `results/x3_reward_after_ec_buildup.{md,csv}` |
| X3b script + results | `corpus_builder/cross_extractor/analysis_x3b.py`, `results/x3b_offer_before_combat.{md,csv}` |
| X4 script + results | `corpus_builder/cross_extractor/analysis_x4.py`, `results/x4_negative_signal.{md,csv}` |
| X5 script + results | `corpus_builder/cross_extractor/analysis_x5.py`, `results/x5_tm_combat_state_expansion.{md,csv}` |
| X6 script + results | `corpus_builder/cross_extractor/analysis_x6.py`, `results/x6_campaign_density.{md,csv}` |
| X7 script + results | `corpus_builder/cross_extractor/analysis_x7.py`, `results/x7_event_clustering.{md,csv}` |
| Cross-extractor findings doc (this) | `corpus_builder/findings/track5_findings_cross_extractor.md` |
| LR re-run output | `corpus_builder/output/loot_reward/full_v36_extended/` |
| CC extended corpus | `corpus_builder/output/compression_cadence_corpus_v1p4_extended.json` |
| Lessons doc v3 candidates (updated, +24, +25) | `corpus_builder/docs/lessons_doc_v3_candidates.md` |
