# Compression Cadence — Findings (v1.0)

**Ship:** Track 5, Ship 4 — Compression Cadence Extractor
**Source corpus:** CRD3 c=2 alignment, 140 unique episodes (94 C1, 46 C2)
**Extractor version:** `compression_cadence_v1p4` (Phase 3 final, locked through Phase 6)
**Records emitted:** 365 across 123 pool episodes (140 minus 10 handsample minus 7 recon)
**Date completed:** 2026-05-12

---

## 1. Questions asked

Six research questions verbatim from the spec (§1):

1. How often does Matt compress (cut forward / retire scene / end montage / exit NPC focus) per episode, and how does the rate compare to total scene-count?
2. What surface forms does compression take — explicit cuts ("we cut to..."), montage compressions, NPC dismissals ("[NPC] takes their leave"), location departures, investigative-beat closures, search-loop terminations, tavern-scene endings, downtime collapses?
3. What signals precede a compression — does Matt telegraph it (player turn just declared closure intent / NPC purpose just resolved / objective just achieved / repeated-verb fatigue / dead-air signal) or surprise-cut?
4. How does Matt handle the vacuum between compressions — does the next scene open from a player declaration, an NPC arriving, an environmental shift, or Matt-initiated narrative?
5. Does Matt compress differently in C1 vs. C2 (shorter scenes? longer compressions? different surface forms)? Campaign-arc evolution of compression style.
6. How often does Matt RESIST compressing — i.e., how often does a scene appear stale (repeated verbs, no new info in N exchanges, NPC purpose resolved) and Matt does NOT compress?

Question 6 mirrors Loot/Reward's reward-absence question. Its detection shape is "expected compression that didn't fire," which requires cross-extractor signal. Single-extractor coverage is partial; see §5 Q6 and §10.

---

## 2. Method

**Phase walk.** Recon on 7 episodes (seed 3333, stratified C1/C2 × early/mid/late, disjoint from all 107 prior eval-set episodes across Encounter Cadence, Time-Mention, and Loot/Reward). Recon produced the six-category taxonomy (+ STALE_HOLD_CANDIDATE auxiliary), the phrase-span Stage 0 architecture, and the §13 decisions locked at (a) options before Phase 2. Hand-sample on 10 episodes (seed 2222), producing 42 records across 5 calibration cycles. Patches 1–4 cleared four named FP families; eight singletons were deliberately deferred per Phase 3 operating rules (Lesson 4: don't iterate on small-sample-specific failures). Gate-set construction (7 recon episodes, 25 records, seed 7777) measured once at Phase 4. Full-corpus parse (123 mechanically-excluded episodes) at Phase 5 produced 365 records. Validation-set construction (15 records, seed 9999, drawn from the 123 mechanically-excluded pool) measured once at Phase 6.

**Decisions locked at §13.**
- §13.1a: All six categories retained including LOCATION_DEPARTURE (TENTATIVE at §4 promoted to confirmed).
- §13.2a: Phrase-span Stage 0 with D1–D4 reject families. NPC-voice handling is reject-only (D2): when the trigger phrase appears inside quoted NPC speech, the candidate is rejected entirely. This is opposite Loot/Reward's NPC-voice routing — compression decisions are exclusively Matt-narrated, so any trigger inside NPC dialogue is a phrase-attribution failure.
- §13.3a: STALE_HOLD_CANDIDATE is a partial-signal Q6 surface, marked _CANDIDATE in category name to telegraph the partial coverage.
- §13.4a–§13.7a: Compression-scope UNKNOWN allowed when forward context insufficient; surface forms unified across categories where shape overlaps.

**Eval-set construction and integrity.**
- Hand-sample: 10 episodes, seed 2222. Phase 2 spot-check at 18/42 = 42.9% strict. Calibration cycles (Phase 3, Patches 1–4) lifted to 18/27 = 66.7% strict on retained records.
- Gate: 7 recon episodes, 25 records, seed 7777. These episodes were used for recon (taxonomy design, surface-form enumeration); the gate records were not reviewed during calibration (raw_text withheld at construction time). Measured once.
- Validation: 15 records, seed 9999, drawn from the 123 episodes outside both hand-sample and recon. First mechanically episode-disjoint surface in this ship. Judged blind (Phase 6). Measured once.

No LLM was used in the execution path at any stage. All classification is deterministic regex.

**D-rule lineage.** Spec §6 defined D1–D4. Phase 3 calibration added D5 (Patch 1, condition-recovery polysemy), D6 (Patch 2, within-turn same-family dedup), D7 (Patch 4, spell/rules-mechanic reject). Patch 3 extended D1 with episode-end broadcast-close vocabulary rather than introducing a new D-rule. Full lineage and definitions in `findings/compression_cadence_full_parse_stats.md` §5.7.

---

## 3. Reliability — read this before quoting any number below

Three precision surfaces, measured sequentially:

| Surface | Records | Correct | Precision | Notes |
|---|---:|---:|---:|---|
| Hand-sample (calibration) | 27 | 18 | **66.7%** | 8 singletons deferred per Lesson 4; 0 retention regressions across Patches 1–4 |
| Gate (held-out, recon episodes) | 25 | 16 | **64.0%** | −2.7pp gap; within noise of handsample |
| Validation (mechanically excluded) | 15 | 7 | **46.7%** | −17.3pp gap from gate; **divergent** |

The numbers diverge at validation, not converge. This is the opposite pattern from Loot/Reward (72.4% → 68.0% → 66.7%, convergent within 4.4pp) and the most important read in this doc.

**The drop is one category.** OVERNIGHT_REST is 9 of 15 validation records (60%) and 3 of 9 are correct (33.3%). Stripping OR out, the other six validation records score 4/6 = 67%, in line with gate. The validation drop is not a general extractor failure — it is a category-specific trigger-family overpromiscuity surfaced for the first time at validation.

OVERNIGHT_REST's wake-trigger family (`you come to consciousness`, `you wake up`, `as the morning comes to`, `the morning sun`) fires on a much wider polysemy surface than handsample and gate revealed:

- Mid-night disturbance wake (C1E044_t876 — distant screech wakes party at night, no morning transition)
- Single-character mid-watch wake (C2E022_t209 — Caleb wakes mid-watch to investigate a noise, party still asleep)
- Atmospheric morning-sun during active travel (C1E105_t492 — party flying as mist; sunbeams describe forest lighting, not waking from rest)
- Combat revival via healing potion (C2E043_t924 — Caleb pours a potion to revive Beauregard; D5 should have caught it but doesn't carry potion vocabulary)

Plus a watch-shift wake graded defensible (C2E020_t577) and one borderline atmospheric-vs-narrative call. Five of nine OR records hit some flavor of wake-event-that-isn't-diurnal-transition-to-morning.

Hand-sample (42 records, 19 OR) and gate (25 records, 7 OR) both pulled the canonical "after evening's rest, all of you wake" shape. Validation drew wider — 9 of 15 records OR, and the family fragmented. This is a sample-size effect on a long-tailed category-internal distribution: the dominant trigger-phrase variant was over-represented in calibration and gate samples, masking the family's true breadth.

**Sharpened claim language for downstream consumers:**

> Strict precision sits at 47–67% across calibration, gate, and validation surfaces. OVERNIGHT_REST is the brittleness axis — strip OR records from validation and the remaining six score 67%, in line with gate. Per-category precision (§5 Q2 table) is the more honest read than the headline rate.

> FP rate ~33–53% of emitted records depending on surface; concentrated in OVERNIGHT_REST polysemy and LOCATION_DEPARTURE micro-motion (recurring across all three surfaces). Other categories' FPs are singletons documented in §6.

> n=15 validation binomial CI ±25pp. The validation drop signal is meaningful (4-category coverage gap, three recurring families surfaced) but the precise validation precision value is uncertain at this sample size. Category-internal sample stratification at validation would have caught the OR breadth — flagged in §7 lessons.

The gate surface shares episode IDs with the recon set used for taxonomy and surface-form design. The gate records were not reviewed during calibration (raw_text withheld), but recon FP families from those episodes informed D1–D4 design. This is a known limitation of the single-ship pipeline when the 140-episode corpus must be split into development / calibration / gate / validation.

**Per-category strict precision across all three surfaces** (combined view; surface counts vary):

| Category | Combined records | Combined correct | Strict |
|---|---:|---:|---:|
| SCENE_CUT | 4 | 4 | 100% |
| TEMPORAL_MONTAGE | 13 | 10 | 76.9% |
| OVERNIGHT_REST | 35 | 17 | 48.6% |
| INVESTIGATIVE_CLOSURE | 6 | 4 | 66.7% |
| LOCATION_DEPARTURE | 11 | 6 | 54.5% |
| NPC_DEPARTURE | 6 | 3 | 50% |
| STALE_HOLD_CANDIDATE | 2 | 0 | 0% (1 defensible) |

SCENE_CUT and TEMPORAL_MONTAGE are the only categories landing above 75% strict. OVERNIGHT_REST, LOCATION_DEPARTURE, NPC_DEPARTURE all sit at 48–55% — the trigger families catch the right phrase shape but the wrong subject (PC vs NPC), wrong destination scope (sub-location vs scene-level), or wrong event type (mid-night vs morning wake). STALE_HOLD_CANDIDATE is a partial-signal category by design (§13.3a) — measurement against it is structural, not calibration-quality.

---

## 4. Headline numbers

### Per-episode density

| Metric | Value |
|---|---:|
| Episodes parsed (pool) | 123 (80 C1, 43 C2) |
| Episodes producing ≥1 record | 110 (89.4%) |
| Episodes producing zero records | 13 (10.6%) |
| Total records emitted | 365 |
| Mean records per episode | 2.97 |
| Median records per episode | 3.0 |
| Max records per episode | 13 (C2E016) |

Zero-record episodes (13): C1E003, C1E006, C1E033, C1E040, C1E046, C1E073, C1E076, C1E085, C1E108, C2E010, C2E015, C2E034, C2E040. Plus C1E114 (recon, excluded from pool but confirmed zero at extractor level — Matt holds all scenes open through the C1 climactic finale, per recon §8 Finding 1). Fourteen of 130 examined episodes (10.8%) produce no compression records at all.

Compared to prior ships: Encounter Cadence at 1.21 records/ep, Loot/Reward at 4.06/ep, Time-Mention at 25.7/ep. Compression Cadence at 2.97/ep sits between Encounter Cadence and Loot/Reward — scenes compress more often than they initiate combat, less often than they deliver rewards.

### Category breakdown

| Category | Count | Proportion | Voice |
|---|---:|---:|---|
| OVERNIGHT_REST | 143 | 39.2% | Matt |
| TEMPORAL_MONTAGE | 95 | 26.0% | Matt |
| LOCATION_DEPARTURE | 69 | 18.9% | Matt |
| NPC_DEPARTURE | 34 | 9.3% | Matt (heterogeneous turn) |
| INVESTIGATIVE_CLOSURE | 13 | 3.6% | Matt |
| SCENE_CUT | 10 | 2.7% | Matt |
| STALE_HOLD_CANDIDATE | 1 | 0.3% | Matt |

OVERNIGHT_REST is the dominant single category at 39.2% — the diurnal/rest transition is the most common compression shape in the corpus. This concentration is also the source of the precision brittleness in §3: when nearly 40% of records depend on a single trigger family, polysemy within that family disproportionately shapes the headline number.

TEMPORAL_MONTAGE at 26.0% and LOCATION_DEPARTURE at 18.9% account for another 45%. These three top-level shapes carry 84.1% of all compression records. NPC_DEPARTURE, INVESTIGATIVE_CLOSURE, SCENE_CUT, and STALE_HOLD_CANDIDATE together carry only 15.9%.

STALE_HOLD_CANDIDATE at 0.3% (1 record across 123 episodes) is structurally thin — see §5 Q6 for the architectural read.

### Campaign split

| Campaign | Episodes | Records | Records/episode |
|---|---:|---:|---:|
| C1 | 80 | 209 | 2.61 |
| C2 | 43 | 156 | 3.63 |

C2 runs 39% denser per episode than C1. This is the strongest C1-vs-C2 signal in the ship — see §5 Q5.

### Phase-third density

| Stratum | Episodes | Records | Records/episode |
|---|---:|---:|---:|
| C1_early | 27 | 82 | 3.04 |
| C1_mid | 27 | 64 | 2.37 |
| C1_late | 26 | 63 | 2.42 |
| C2_early | 14 | 38 | 2.71 |
| C2_mid | 14 | 73 | 5.21 |
| C2_late | 15 | 45 | 3.00 |

C2_mid is the densest stratum at 5.21 records/ep — nearly double the corpus mean. C1_mid and C1_late are the thinnest at ~2.4/ep. The C2_mid density may reflect mid-C2 pacing structure (extended travel arcs, multi-day mercenary jobs) or an episode-length artifact; not separable from this data alone.

### TM overlap rate

178 of 365 records carry `extracted_time_mention_overlap=True` (48.8%). Below spec §12.2's 60% disqualification threshold — the extractor passes the marginal-value test (over 50% of records are not just TM `scene_transition` duplicates). OVERNIGHT_REST and TEMPORAL_MONTAGE dominate the overlap pool by category proportion.

### Stage 0 filter activity

64 candidate phrases rejected across the corpus:

| Rule | Source | Count |
|---|---|---:|
| D1 | Spec §6 + Patch 3/4 | 18 |
| D2 | Spec §6 | 13 |
| D3 | Spec §6 (LOCATION_DEPARTURE only) | 4 |
| D4 | Spec §6 (recap-state) | not logged (turn-level skip) |
| D5 | Patch 1 (condition-recovery) | 8 |
| D6 | Patch 2 (within-turn dedup) | 21 |
| D7 | Patch 4 (spell/rules-mechanic) | 0 |

D6 carries the most weight (21 — including 19 OR within-turn duplicates). D7 fired zero times across the full corpus despite validation surfacing a true target (C1E091_t2095, Heroes' Feast spell-HP increase). D7 is under-coverage in its current vocabulary set.

---

## 5. Research questions

### Q1 — How often does Matt compress per episode, and how does the rate compare to scene count?

2.97 compression records per episode, mean across all 123 pool episodes (median 3.0, max 13 in C2E016). 10.6% of episodes produce zero compression records; 89.4% produce at least one.

Scene-count comparison is partial: this ship does not produce a scene-segmentation count directly. As a proxy, the encounter_cadence ship measured combat initiations at 1.21/ep — Compression Cadence at 2.97/ep is ~2.5× as frequent as combat initiation. If combat boundaries are taken as one source of scene boundaries, compression decisions produce additional scene-boundary signals at roughly 2× the rate. Full scene-count cross-extractor join (combat + compression + time_mention `scene_transition`) is filed as open question §9.1.

**Distribution shape.** Per-episode counts are right-skewed: median 3, mean 2.97, max 13. The top quartile (≥4 records) carries the bulk of total density; the bottom quartile is zero-record episodes plus single-record episodes.

### Q2 — What surface forms does compression take?

Six confirmed surface forms (plus STALE_HOLD_CANDIDATE as partial-signal auxiliary). Corpus proportions and per-category strict precision combined across all three eval surfaces:

| Surface form | Corpus % | Strict precision | Read |
|---|---:|---:|---|
| OVERNIGHT_REST (diurnal transition) | 39.2% | 48.6% | Dominant by volume, brittle on polysemy |
| TEMPORAL_MONTAGE (montage compression) | 26.0% | 76.9% | Second-most-frequent, robust |
| LOCATION_DEPARTURE (location exit) | 18.9% | 54.5% | Brittle on D3 micro-motion sub-cases |
| NPC_DEPARTURE (NPC exit) | 9.3% | 50% | Brittle on subject-confusion (PC vs NPC) |
| INVESTIGATIVE_CLOSURE | 3.6% | 66.7% | Low volume, mid precision |
| SCENE_CUT (explicit cut) | 2.7% | 100% | Low volume, highest precision |
| STALE_HOLD_CANDIDATE | 0.3% | 0% (1 defensible) | Partial-signal by design |

**SCENE_CUT** is the highest-precision category but lowest-volume — Matt uses explicit "cut to" or "we cut" framing rarely. When he does, it's unambiguous and the regex catches it cleanly.

**TEMPORAL_MONTAGE** at 76.9% strict and 26.0% of corpus is the most reliably-detected surface form by combined precision-times-volume. The two main FP shapes are atmospheric-description ("throughout the day", "morning sun") and spell-duration ("for the next 24 hours" on a Heroes' Feast effect).

**OVERNIGHT_REST**'s wake-trigger family is the corpus's biggest precision problem — see §3 for the read. The phrase-family was designed against the canonical "after evening's rest, all of you wake to morning" shape; validation surfaced wake events that share trigger-phrase vocabulary but aren't diurnal-to-morning compressions.

**LOCATION_DEPARTURE** at 54.5% strict suffers from in-scene micro-motion FPs that D3 didn't catch (combat-microposition, ship-internal navigation, town-square approach within established city). Same root pattern across handsample singletons 1–2, gate, and validation: "you make your way to [destination]" where destination is a sub-locale, not a scene-level location.

**NPC_DEPARTURE** at 50% strict suffers from subject-confusion: "exit the [location]" trigger fires regardless of whether the subject is an NPC (correct) or a PC (should route to LOCATION_DEPARTURE).

### Q3 — What signals precede a compression — telegraphed or surprise-cut?

The `buildup_signal` field captures the immediate-context signal preceding the trigger phrase. Distribution across all 365 records:

- `matt_initiated` — Matt's own narration with no immediate PC or NPC prompt: dominant majority of records. Most compressions are Matt's narrative call.
- `player_intent` — PC declares closure intent ("we head out", "let's get going") in the turn immediately preceding Matt's compression narration: minority. Concentrated in SCENE_CUT and LOCATION_DEPARTURE.
- `objective_completion` — the immediately-preceding beat resolves a stated objective (party reaches a destination, completes a task): present mainly in TEMPORAL_MONTAGE travel arcs.
- `repeated_stale_signal` — STALE_HOLD_CANDIDATE only; the partial-signal cluster threshold (§13.3a).
- `UNKNOWN` — context insufficient to classify.

The buildup_signal field captures the immediately-preceding turn's contribution but does not measure full lead time. The signal is sufficient to support the qualitative finding that **most compressions are Matt-initiated rather than player-prompted**: the dominant `matt_initiated` value means the trigger turn shows no immediate PC closure intent or objective resolution prompt. Matt elects to compress on his own narrative call substantially more often than he responds to a player closure cue.

**Caveat.** This is a directional finding, not a quantified one. The buildup_signal field is one of three Q3-relevant signals (the other two — repeated-verb fatigue and dead-air detection — would require cross-extractor signal). The full Q3 answer requires cross-extractor join with Time-Mention `scene_transition` events for "what kind of context immediately preceded the compression": Time-Mention has structured turn-position data that this extractor doesn't carry.

### Q4 — How does Matt handle the vacuum between compressions?

This question asks what kind of action opens the *next* scene after Matt compresses. The extractor records the compression trigger turn and the surrounding 5 turns of preceding context but does not extract the next-scene-opening turn. Q4 is not answerable from this ship's records alone.

The required cross-extractor signal: for each compression record, identify the next Matt-narrated turn that opens a new scene-state (no continuation of the prior scene), then classify the opening shape (player declaration, NPC arrival, environmental description, Matt-narrated frame-set). This is filed as open question §9.2.

Partial single-extractor signal: when a compression record's `compression_scope=scene_exit`, the next scene begins; when `compression_scope=in_scene`, the scene continues. 304 of 365 records carry `scene_exit` scope (83.3%); 47 carry `in_scene` (12.9%); 14 carry `UNKNOWN` (3.8%). The 83.3% scene_exit rate confirms that **most compression decisions do close a scene** rather than compress within an ongoing scene — but the *content* of the next scene is unanswerable from this extractor.

### Q5 — Does Matt compress differently in C1 vs. C2?

Yes, and the signal is clean. C2 produces compression records at 3.63/episode vs C1's 2.61/episode — **C2 is 39% denser per episode than C1**. The phase-third breakdown (§4) sharpens this: C2_mid at 5.21/ep is the densest stratum in the corpus, nearly double the corpus mean.

This is consistent with the broader observation that C2 pacing is tighter than C1: more episodes per arc, shorter scenes between major beats, more frequent diurnal compressions across travel arcs. The category mix in C2 vs C1 (not tabulated separately here but extractable from the full parse) shows OVERNIGHT_REST and TEMPORAL_MONTAGE carrying most of the C2 density delta — Matt compresses travel and rest more frequently in C2 than in C1.

**Caveat.** Episode length is not normalized in this comparison. C2 episodes are on average shorter than C1 episodes (Talks Machina format change, shorter sessions), so records-per-episode is a partial measure. Records per MATT turn or records per hour of session would give a different normalization; not pursued in this ship. The directional finding (C2 compresses more frequently) stands; the magnitude (39%) should be quoted with the per-episode caveat.

The category-mix shift is the more interpretable finding: Matt's compression repertoire didn't change categorically between campaigns (all six shapes appear in both), but the rate at which he reaches for compression — particularly overnight/rest and travel-montage compressions — increased.

### Q6 — How often does Matt RESIST compressing?

STALE_HOLD_CANDIDATE = 1 record across 365 (0.3%). The single-extractor partial-signal coverage is effectively inoperative on this question.

The architectural constraint: STALE_HOLD_CANDIDATE detection requires three stale signals (repeated verbs, no new info, NPC purpose resolved) in a 10-turn preceding window AND Matt prompting "what do you do?" without a compression trigger. The single emit in the full corpus (C2E037_t1351) is technically threshold-meeting but the prompt follows a substantial new-info reveal (water draining, ancient circle revealed) — not a true stale beat.

**The strongest Q6 signal in this ship is not from the STALE_HOLD_CANDIDATE category.** It is from the zero-record episodes, particularly **C1E114 (the recon-set 7th episode, mechanically excluded from the pool)**. Recon manually identified zero true-positive compression events in C1E114; the locked Phase 3 extractor confirms this at code level. C1E114 is the C1 climactic finale arc — Matt holds every scene open through the multi-hour finale without electing to compress.

The 13 zero-record pool episodes (plus C1E114) collectively suggest a real "Matt holds scene open" pattern that is invisible to compression-record-only analysis: episodes where the negative signal (no compression fires) is the entire finding. Cross-extractor signal would sharpen this — encounter_cadence + time_mention `scene_transition` cross-reference against compression-zero episodes would distinguish "Matt held the scene through tension" from "the episode genuinely had nothing to compress."

**Honest framing:** the single-extractor narrated-stale-hold form is not detectable at meaningful frequency given current architecture. The negative-signal form (compression-zero episodes correlated with high-tension content) is the more productive Q6 surface but requires cross-extractor analysis. This is the structural mirror of Loot/Reward's Q6 limitation.

---

## 6. Failure analysis — remaining FP families

Tabulated across all three eval surfaces. These are deferred singletons, unresolved families, or known patch-incompleteness shapes as of Phase 3.4 (extractor lock).

**Recurring families (≥2 surfaces):**

| Family | Total count | Surfaces | Description |
|---|---:|---|---|
| `in_scene_micro_motion_misrouted_to_location_departure` | 5 | HS×2, Gate×2, Val×1 | D3 covers in-scene navigation but misses sub-cases: combat micro-positioning, ship-internal navigation, town-square approach within established city scene. "You make your way to [sub-location]" pattern. |
| `atmospheric_description_misrouted_to_time_compression` | 2 | Gate×1, Val×1 | "Throughout the day" describing city atmospheric conditions; "morning sun" describing forest lighting during travel. Trigger family lacks descriptive-vs-narrative-advance disambiguation. |

**Singleton families (1 surface each), grouped:**

Handsample-deferred (Phase 3 Lesson 4, see `cc_phase3_remaining_singletons.md`):

| Family | Record | Category error |
|---|---|---|
| `in_scene_micro_motion_within_town` | C1E050_t1867 | FP LOCATION_DEPARTURE |
| `in_scene_micro_motion_approach` | C1E090_t1317 | FP LOCATION_DEPARTURE |
| `subject_misattribution` | C1E056_t1132 | FP LOCATION_DEPARTURE (subject = horde, not party) |
| `projective_future_montage` | C1E056_t2018 | FP TEMPORAL_MONTAGE (future tense, "will be") |
| `verb_as_noun_modifier` | C1E013_t1673 | FP NPC_DEPARTURE ("doorway that exits the room") |
| `descriptive_use_within_compression_turn` | C1E090_t2695 idx1 | FP TEMPORAL_MONTAGE (decorative phrase in compression turn) |
| `category_misroute_party_action_as_npc` | C1E090_t1868 | NPC→LOC misroute (party exits, not NPC) |
| `logistical_question_not_compression` | C1E097_t1537 | FP LOCATION_DEPARTURE (interrogative clause) |

Gate-surfaced:

| Family | Record | Category error |
|---|---|---|
| `watch_pass_uneventful_misrouted_to_investigative_closure` | C1E011_t1655 | INV→OR misroute (overnight watch passing) |
| `pc_exit_misrouted_to_npc_departure` | C1E053_t2183 | NPC→LOC misroute (PC subject for "exit") |
| `within_turn_dedup_failed_overnight_rest` | C2E011_t1849 idx1 | OR within-turn duplicate (D6 missed pair) |

Validation-surfaced:

| Family | Record | Category error |
|---|---|---|
| `mid_night_disturbance_wake_misrouted_to_overnight_rest` | C1E044_t876 | FP OR (mid-night wake, not morning) |
| `single_character_mid_watch_wake_misrouted_to_overnight_rest` | C2E022_t209 | FP OR (one PC, mid-watch, in-fiction stimulus response) |
| `healing_potion_revival_misrouted_to_overnight_rest` | C2E043_t924 | FP OR — **D5 under-coverage**; potion vocabulary not in D5's combat-context token list |
| `spell_duration_misrouted_to_temporal_montage` | C1E091_t2095 | FP TM — **D7 under-coverage**; Heroes' Feast HP-increase phrasing not in D7's vocabulary set |

**Known-unpatched patch incompletenesses.** D5 (Patch 1) and D7 (Patch 4) both have demonstrated under-coverage in validation — each missed at least one true target. D5 needs healing-potion vocabulary added to its combat-context token list (`pour a healing potion`, `feed a potion`, `revive`, `stabilize`). D7 needs spell-effect-duration vocabulary added (`maximum hit point increase for`, `for the next N hours` in spell-effect context). Per Phase 6 close, the extractor is locked at v1p4; these are documented for future work, not chased.

The recurring in-scene-micro-motion family (5 instances across 3 surfaces) is the single most consequential unpatched family. D3 catches the canonical "you make your way [around/across/up to/down]" cases but misses three named sub-patterns: combat micro-positioning, ship/building-internal navigation, and approach-to-named-building-within-established-city. A destination-scope classifier would address all three but exceeds regex-deterministic architecture; filed for v3 architecture lessons.

---

## 7. v3 lessons-doc candidates filed

Six patterns confirmed across this ship's calibration and validation, recommended for `corpus_builder_lessons_v3_candidates.md`:

**Trigger-phrase polysemy on physical-state vocabulary.** OVERNIGHT_REST's wake-trigger family (`come to consciousness`, `wake up`, `morning sun`) and Loot/Reward's KNOWLEDGE_GRANT family (`vision comes back`, `aware of`) both fire on physical-state vocabulary that doubles between in-fiction state-recovery and the target category's canonical shape. Validation revealed at least four distinct OR wake sub-shapes that share trigger vocabulary but are not diurnal-to-morning compressions. Forward rule: physical-state-vocabulary triggers (`consciousness`, `awareness`, `senses`, `wake`, sensory verbs) need a designated polysemy-check stage that distinguishes state-recovery from in-fiction event progression. Joint candidate with Loot/Reward Lesson 5.

**Within-turn dedup as default Stage 1 component.** Time-Mention Patch 1 and Compression Cadence Patch 2 (D6) both implemented within-turn same-family dedup with a character-distance window. Both ships independently arrived at the same architecture: when two trigger phrases of the same category fire in the same turn within N characters, emit only the first. Forward rule: within-turn same-family dedup with a configurable distance window should be a default Stage 1 component for any phrase-detection extractor. Joint candidate with Time-Mention Lesson 2.

**D-rule numbering with patch-ID provenance.** When calibration extends a spec-defined D-rule (this ship's Patch 3 extended D1 with episode-end broadcast-close vocabulary; Patch 4 extended D1 with stream-meta vocabulary) vs. introducing a new D-rule (Patches 1, 2, 4 → D5, D6, D7), the numbering should encode which is which. The mapping needs to be legible in the stats output and audit trail without reading the extractor source. Forward rule: D-rules carry both a numeric identifier and a provenance tag (spec / patch-N-extension / patch-N-new) in stats files and findings docs.

**Subject confusion in trigger-family matching (party vs NPC).** Several FP families across this ship share the pattern: a trigger phrase fires regardless of grammatical subject when the category requires a specific subject class. NPC_DEPARTURE fires on PC subjects ("exit the room" when the actor is "you"); LOCATION_DEPARTURE fires on inanimate-object subjects ("the horde leaving westward"). Forward rule: category families with a required subject class (NPC, party, named entity) need a subject-extraction heuristic at Stage 1; minimum form is a second-person-pronoun vs third-person-pronoun proximity check before category routing.

**Atmospheric-vs-narrative time phrase ambiguity.** Time-bearing phrases (`throughout the day`, `morning sun`, `over the course of the evening`) function as either narrative-advance (compression) or state-description (atmospheric). The two uses share lexical surface but differ in syntactic role (matrix clause vs. subordinate descriptive clause) and semantic function. Forward rule: time-bearing TM and OR triggers need a narrative-advance-vs-atmospheric disambiguation stage; minimum form is a check for descriptive-clause-internal position (within a `where/that/which` clause, or attached to a stative verb).

**Sample-size effect at small-N category stratification on long-tailed distributions.** Hand-sample (10 episodes, 42 records, 19 OR) and gate (25 records, 7 OR) both pulled the canonical OR shape; validation (15 records, 9 OR) drew wider and surfaced four new OR sub-shapes. The sample-proportional stratification masked the category's true breadth. Forward rule: at validation time, sample stratification by *trigger-phrase variant* within high-volume categories (not just by category) would catch family-internal polysemy that whole-category stratification misses. Particularly important when a category is >30% of corpus volume — OR at 39.2% was the natural place this surfaced.

---

## 8. What this enables for Track 4

This findings doc lands a structured account of how Matt compresses scenes in CRD3. Three results are directive-shippable for Virgil's Scene Lifecycle v1:

**Compression baseline rate.** Matt compresses on average 2.97 times per episode across the 123-episode pool, with 10.6% of episodes producing zero compressions. C2 runs 39% denser than C1 (3.63 vs 2.61 records/ep). Virgil's scene lifecycle has a numerical baseline: a typical session has ~3 explicit scene-compression decisions, with significant variance (max 13, median 3). The 10.6% zero-compression rate establishes that some sessions legitimately produce no compression — Scene Lifecycle v1 should not force a minimum compression rate.

**OVERNIGHT_REST dominance.** The diurnal/rest transition is the single most common compression shape at 39.2% of records. Scene Lifecycle v1 should treat overnight/rest compression as a first-class scene boundary, not a special case. Matt's pattern: rest is declared → watch is described → compression to morning. The wake-trigger vocabulary varies widely (this is the precision brittleness in §3) but the structural shape is consistent.

**Compression is overwhelmingly Matt-initiated.** The Q3 dominant signal (`matt_initiated` buildup_signal) indicates Matt elects to compress on his own narrative call far more often than he responds to a player closure cue. Virgil's Scene Lifecycle should not wait for explicit player closure intent before suggesting compression — DM-initiated compression is the default, player-prompted compression is the exception.

Two further structural findings are useful but not directly directive:

**STALE_HOLD_CANDIDATE structural insight.** The single-extractor stale-hold detection produced 1 record across 365 — effectively zero coverage. The negative-signal Q6 surface (compression-zero episodes) is more productive: 14 of 130 examined episodes (10.8%) produce zero compressions, and these are not uniformly distributed — they cluster around high-tension content (the C1E114 finale is the canonical instance). Scene Lifecycle should expect that high-tension/climactic episodes produce no compressions; the absence of compression is itself a scene-state signal.

**Cross-extractor join enables full Q3 and Q4.** Time-Mention `scene_transition` + Compression Cadence trigger turn + encounter_cadence combat-resolution gives the buildup-context and next-scene-opening data that single-extractor Compression Cadence cannot. Filed for cross-extractor analysis ship.

---

## 9. Open questions

1. **Q4 full cross-extractor scene-opening classification.** What kind of context opens the next scene after a compression? Requires cross-extractor join: compression record + next Matt-narrated turn + opening-shape classifier (player declaration, NPC arrival, environmental description, Matt-narrated frame-set).
2. **Q1 full scene-count denominator.** Compression Cadence at 2.97/ep vs total scene count per episode is partial without a unified scene-segmentation count. Encounter Cadence + Compression Cadence + Time-Mention `scene_transition` joined gives a scene-boundary count per episode; the compression/scene ratio is then derivable.
3. **Q6 cross-extractor stale-hold detection.** The negative-signal form (compression-zero episodes correlated with high-tension content) requires encounter_cadence + time_mention cross-reference. C1E114 is the canonical example; how many other zero-compression episodes share its tension profile?
4. **Category-mix shift across campaigns.** C2 is 39% denser per episode; which categories drive the delta? Visual inspection suggests OVERNIGHT_REST and TEMPORAL_MONTAGE carry most of it. Derivable from the full parse output by computing category × campaign × phase-third proportions.
5. **D3 destination-scope classifier.** A destination-scope check (sub-location vs scene-level) would address 5+ singletons across surfaces but exceeds regex-deterministic architecture. v3 architecture lessons candidate.
6. **D5/D7 vocabulary expansion.** Two demonstrated under-coverage cases at validation (healing-potion revival, spell-effect HP). Vocabulary additions are scoped patches that could land without changing architecture. Deliberately deferred per the Phase 6 lock decision (re-judging validation against patched extractor is overfitting).

---

## 10. Limitations

1. **Validation drop is real and category-localized.** The headline 46.7% validation strict is 17.3pp below gate and 20.0pp below handsample. The drop is concentrated in OVERNIGHT_REST (3 of 9 OR records correct at validation = 33.3%). Stripping OR, the remaining six validation records score 4/6 = 67%, in line with gate. Quote per-category precision (§3 table) rather than headline rate.
2. **Validation measured 3 of 7 categories.** Stratum-proportional sampling drew OR=9, LD=3, TM=3 across the 15 records. NPC_DEPARTURE, INVESTIGATIVE_CLOSURE, SCENE_CUT, STALE_HOLD_CANDIDATE were unmeasured at validation; their generalization rests on gate v2 numbers alone. Lesson 6 in §7 addresses the sample-design fix.
3. **Gate shares episode IDs with recon development set.** The 7 recon episodes informed taxonomy and surface-form design. Gate records from those episodes were measured blind (raw_text withheld at construction) but the FP shapes from those episodes informed D1–D4 design. Same caveat as Loot/Reward §10.
4. **D5/D7 demonstrably under-coverage.** Validation surfaced one D5 true target (healing-potion revival) and one D7 true target (spell-effect HP). Both rejected at v1p4 — vocabulary expansion deferred per Phase 6 lock.
5. **STALE_HOLD_CANDIDATE produces 1 record across the corpus.** The single-extractor partial-signal Q6 surface is effectively inoperative. The negative-signal form (compression-zero episodes) is more productive but requires cross-extractor analysis. Q6 is unanswerable at meaningful frequency from this ship's records alone.
6. **Episode length is not normalized in the C1-vs-C2 comparison.** The 39% C2-density delta is records-per-episode; C2 episodes are on average shorter than C1. The directional finding (C2 compresses more frequently) stands; the magnitude should be quoted with the per-episode caveat.
7. **Source corpus is c=2 alignment only.** Same constraint as prior ships; confirmed byte-identical to c=3/c=4 by importer comparison only.
8. **123 of 140 episodes were never manually reviewed.** Hand-sample 10 + recon 7 = 17 episodes had manual judgment applied to selected records. Validation drew 15 records from 12 distinct episodes. Records from the remaining ~111 episodes are in the full parse but unaudited.

---

## 11. Files

| Artifact | Path |
|---|---|
| Extractor source (v1p4 final) | `corpus_builder/extractors/compression_cadence.py` |
| Full-parse output | `corpus_builder/output/compression_cadence_corpus_v1p4.json` |
| Full-parse stats | `corpus_builder/findings/compression_cadence_full_parse_stats.md` |
| Hand-sample v2 (judged calibration) | `corpus_builder/eval_sets/compression_cadence_handsample_v2.json` (server-only) |
| Hand-sample v1 (schema reference) | `corpus_builder/eval_sets/compression_cadence_handsample_v1.json` |
| Gate set v1 (construction) | `corpus_builder/eval_sets/compression_cadence_gate_v1.json` |
| Gate set v2 (judged) | `corpus_builder/eval_sets/compression_cadence_gate_v2.json` |
| Validation v1 (construction) | `corpus_builder/eval_sets/compression_cadence_validation_v1.json` |
| Validation v2 (judged) | `corpus_builder/eval_sets/compression_cadence_validation_v2.json` |
| Phase 3 singletons doc | `corpus_builder/findings/cc_phase3_remaining_singletons.md` |
| Spec doc | `corpus_builder/findings/track5_compression_cadence_phase1_spec.md` |
| Gate v2 apply script | `corpus_builder/eval_sets/cc_gate_v2_apply.py` |
| Validation v2 apply script | `corpus_builder/eval_sets/cc_validation_v2_apply.py` |
