# lessons_doc_v3_candidates

**Staging doc for v3-bound architectural lessons surfaced during Track 5 Ships 3, 4, and 5 (Loot/Reward, Compression Cadence, Cross-Extractor Analysis).** Read alongside `corpus_builder_lessons_v2.md`; this doc stages additions to that canonical set, awaiting promotion at the next v2→v3 transition point.

This doc is not authoritative. `corpus_builder_lessons_v2.md` remains the canonical reference. Candidates below are recommendations for v3 promotion based on cross-ship pattern recurrence; promotion-readiness varies per candidate and is tiered explicitly in §1–§2.

The promotion model follows v1→v2: candidates filed in `lessons_doc_v{N}_candidates.md` during ship phases, validated across two or more ships, then promoted into the next canonical `corpus_builder_lessons_v{N}.md` with the candidates doc archived. v1→v2 promoted three lessons (Lessons 9–11) staged in `lessons_doc_v2_candidates.md` after Ships 1–2.

---

## Purpose

Track 5 Ships 3, 4, and 5 surfaced fourteen patterns across their findings docs (LR §7, CC §7, Cross-Extractor §7). Four of those patterns are cross-ship architectural lessons applicable to future extractors; eight are single-ship architectural or operational lessons that may or may not generalize; two are CRD3-corpus-specific FP filters that belong in corpus-handling guidance rather than cross-cutting architectural doctrine.

This doc separates the three tiers so the next v2→v3 promotion review has tiered candidates to evaluate rather than a flat list. Tier 1 candidates are ready for promotion as-written. Tier 2 candidates need one more ship's confirmation before promotion. Tier 3 candidates are corpus-specific and should land in `CORPUS_BUILDER.md` or equivalent rather than the architectural lessons doc.

---

## Tier 1 — Cross-ship confirmed, recommended for v3 promotion

These four lessons each surfaced in two or more ships with independently-arrived-at implementations or pattern descriptions. Pattern recurrence across ships is the bar v1→v2 used for promoting Lessons 9–11; these meet it.

### Candidate 12 — Within-turn same-family dedup as default Stage 1 component

**Source ships:** Time-Mention (Patch 1), Compression Cadence (Patch 2 / D6).
**Pattern.** Both ships independently implemented within-turn same-family dedup with a character-distance window: when two trigger phrases of the same category fire within N characters in the same turn, emit only the first. Time-Mention used the pattern for cumulative-temporal phrase pairs ("for the next hour" + "in the next hour" in one narration block); Compression Cadence used it for OVERNIGHT_REST phrase pairs ("find yourselves to rest" + "you awaken" in one diurnal-transition narration).

**Implementation parameters that converged:** character-distance window between trigger-phrase start positions (200 chars in CC; ~150 chars in TM Patch 1); same-category-only check (not cross-category); first-instance retained, subsequent suppressed.

**Forward rule for v3.** Phrase-detection extractors with category-level emission should include within-turn same-family dedup as a default Stage 1 component, with the character-distance window configurable per extractor. The window value should be set from sample observation of the typical multi-phrase narration block length, not as a fixed cross-extractor constant.

**Why this is Tier 1.** Two independent ships landed on the same architecture. The pattern generalizes to any extractor with phrase-level triggers that emit at category granularity. v2 Lesson 9 (phrase-span Stage 0) is the parent architectural pattern; within-turn dedup is a complementary downstream component that v2 didn't enumerate.

---

### Candidate 13 — Trigger-phrase polysemy on physical-state vocabulary

**Source ships:** Loot/Reward (`condition_recovery_misread_as_knowledge` family + KNOWLEDGE_NEGATION inversion), Compression Cadence (D5 / Patch 1 condition-recovery, plus validation OR brittleness).

**Pattern.** Physical-state vocabulary (`come to consciousness`, `vision returns`, `aware of`, `wake up`, `awareness`, sensory verbs) doubles between in-fiction state-recovery (knockout, blindness ending, mid-combat revival) and the target category's canonical shape (KNOWLEDGE_GRANT in LR, OVERNIGHT_REST in CC). Loot/Reward surfaced one record at calibration; Compression Cadence surfaced one calibration case (Patch 1 cleared) plus four distinct validation sub-shapes that share trigger vocabulary but aren't the canonical category event.

**Why simple negation-checks don't suffice.** LR's KNOWLEDGE_NEGATION_RE (Phase 3 patch for `you're not entirely certain`) catches one polysemy axis (negation). CC's D5 (Patch 1, condition-recovery with combat-context check) catches a second (state-recovery context). Validation showed D5's combat-context vocabulary missed healing-potion revival; CC's findings showed at least four distinct OR wake sub-shapes that the canonical-shape calibration sample didn't surface.

**Forward rule for v3.** Categories whose trigger vocabulary includes physical-state, sensory, or cognitive-state verbs need a designated polysemy-check stage that distinguishes state-recovery and atmospheric-description senses from the canonical event sense. Minimum implementation: a context-class check on the preceding 3–5 turns (combat / abduction / atmospheric / canonical-event-context) before category routing. Vocabulary lists for state-recovery contexts should include healing/potion/revival vocabulary, not just knockout/grapple vocabulary.

**Why this is Tier 1.** Joint pattern across two ships with independently-implemented partial fixes that both proved insufficient at validation. The full architectural solution exceeds either ship's patch scope; promoting the lesson is the next step toward addressing it cross-extractor.

---

### Candidate 14 — Subject-class check for category families with required subject

**Source ships:** Compression Cadence (`pc_exit_misrouted_to_npc_departure` in gate; `category_misroute_party_action_as_npc` in handsample singletons; `subject_misattribution` in handsample singletons; `verb_as_noun_modifier` in handsample singletons).

**Pattern.** Several FP families share a single structural shape: a trigger phrase fires regardless of grammatical subject when the category requires a specific subject class. NPC_DEPARTURE fires on PC subjects ("exit the room" when the actor is "you"); LOCATION_DEPARTURE fires on inanimate subjects ("the horde leaving westward", "doorway that exits the room"); NPC_DEPARTURE fires on inanimate subjects ("doorway that exits"). The trigger family is shape-correct; the subject-class binding is missing.

**Single-ship qualifier.** This lesson surfaces only in Compression Cadence at the level documented above. However, the underlying architectural shape — categories with required subject-class binding — is general and will recur in any extractor where category semantics tie to actor identity (NPC_INTRODUCTION, FACTION_REFERENCE, the broader social-extractor queue). Recommending Tier 1 promotion because the architectural form is general even though the corpus evidence is single-ship.

**Forward rule for v3.** Category families with a required subject class (NPC, party, named entity, animate vs inanimate) need a subject-extraction heuristic at Stage 1. Minimum form is a second-person-pronoun-vs-third-person-pronoun proximity check before category routing; richer form requires animacy detection on the subject noun phrase. Phase 1 specs for future extractors should enumerate which categories carry required subject-class bindings and what the binding rule is.

**Why this is Tier 1.** The forward rule is general and the implementation pattern is implementable in regex (subject-pronoun proximity is a deterministic check). Future social-domain extractors will hit this immediately.

---

### Candidate 15 — Sample-size effect at small-N category stratification on long-tailed distributions

**Source ships:** Compression Cadence (validation OR breadth not visible in handsample or gate).

**Pattern.** Hand-sample (42 records, 19 OR records) and gate (25 records, 7 OR records) both pulled the canonical OVERNIGHT_REST trigger-phrase shape ("after evening's rest, all of you wake"). Validation (15 records, 9 OR) drew wider via a different seed and stratification, surfacing four new OR sub-shapes (mid-night disturbance wake, single-character mid-watch wake, atmospheric morning-sun, combat-revival potion). Within-category trigger-phrase polysemy was masked by the calibration sample's concentration on the canonical phrase variant.

**The mask is a sample-design effect, not a sample-size effect alone.** Stratum-proportional sampling at validation (by campaign × phase third) selected OR records proportional to OR's corpus volume (39.2%), but did not stratify within the OR category by trigger-phrase variant. The high-volume canonical phrases drew in proportion to their corpus volume; the low-volume edge phrases drew not at all in handsample/gate.

**Single-ship qualifier.** This lesson surfaces in Compression Cadence only. Loot/Reward did not exhibit category-internal polysemy at the same severity (MECHANICAL_GRANT, the highest-volume LR category at 27.1%, has a more uniform trigger-phrase distribution than OR). The architectural lesson is general but the empirical demonstration is single-ship. Recommending Tier 1 because the architectural form interacts with v2 Lesson 3 (eval-set ≠ generalization) and Lesson 7 (held-out enforcement) — these existing lessons assumed category-level stratification was sufficient; this candidate sharpens that assumption.

**Forward rule for v3.** When a category exceeds ~30% of corpus volume, validation-set construction should stratify within the category by trigger-phrase variant, not just allocate to the category proportionally. Operationally: identify the top 3–5 trigger-phrase variants for the high-volume category from the full-parse output, then sample with floor allocation across variants before filling remainder by category volume. The variant-level sample design is additional work at validation construction (~30 min) and catches family-internal polysemy that whole-category stratification misses.

**Why this is Tier 1.** The lesson tightens v2 Lessons 3 and 7 directly. The architectural form is general. The empirical demonstration is single-ship but the mechanism is clear and the cost of the fix is bounded.

---

## Tier 2 — Filed awaiting confirmation in a later ship

These candidates are real architectural patterns with single-ship evidence but uncertain generalization. Filed for visibility; recommend re-evaluating at next v2→v3 promotion review.

### Candidate 16 — Object-aware routing on generic give/grant verbs

**Source ship:** Loot/Reward (Patch A, Phase 3.6).

**Pattern.** QUEST_OFFER_TRIGGER matched "I'll give you" with span ending before the object noun, suppressing MECHANICAL_GRANT_TRIGGER's longer match via the dedup pass. Patch A added an object-aware override that fires before `route_category` when the mechanical-benefit object is detected in the post-trigger context. The fix produced consistent reclassification across all three LR eval surfaces (1 record in gate, 3 records in validation).

**Forward rule.** When a longer trigger overlaps a shorter trigger on the same start position, the dedup pass drops the longer match. Object-aware overrides must fire before `route_category` to reclassify based on the post-trigger object noun.

**Why Tier 2.** Compression Cadence did not encounter this pattern (its trigger families don't share start-position overlap across categories). Encounter Cadence and Time-Mention findings docs would need to be checked for prior evidence. If another ship surfaces the same pattern, promote; otherwise the lesson is LR-specific.

---

### Candidate 17 — Atmospheric-vs-narrative time phrase ambiguity

**Source ship:** Compression Cadence (gate `atmospheric_throughout_day_misread_as_montage`, validation `atmospheric_description_misrouted_to_time_compression`).

**Pattern.** Time-bearing phrases (`throughout the day`, `morning sun`, `over the course of the evening`) function as either narrative-advance (compression / time-skip) or state-description (atmospheric, descriptive-locational). The two uses share lexical surface but differ in syntactic role and semantic function: matrix clause vs. subordinate descriptive clause, agentive vs. stative verb, time-progression vs. time-frame-of-reference.

**Forward rule.** Time-bearing triggers for compression and time-mention categories need a narrative-advance-vs-atmospheric disambiguation stage. Minimum form is a check for descriptive-clause-internal position (trigger within a `where/that/which/throughout` clause attached to a stative verb such as `is`, `lingers`, `shines`) before category routing.

**Why Tier 2.** Recurring within Compression Cadence (gate + validation) but only one ship. Time-Mention's findings doc would need to be checked for analogous evidence — TM presumably has similar atmospheric-description records at calibration that were either cleared by a different mechanism or remain as singletons. Promote if TM cross-check confirms; otherwise file as CC-specific.

---

### Candidate 18 — Recap-state detection needs bounded lookback windows

**Source ship:** Loot/Reward (Patch B, Phase 3.6).

**Pattern.** Recap-state detection that searches all turns 0..candidate across the first 10% of an episode causes legitimate later turns to be flagged as recap when any RECAP_VOCAB token appears early in the episode. LR's specific bug: SAM's turn 3 "as I said last week" in C2E035 flagged correct loot records at turns 116 and 248 as recap. Patch B narrowed the lookback to ±15 turns and resolved the false positives.

**Forward rule.** Recap-state detection must be windowed, not whole-episode. A ±15-turn lookback catches real episode-recap-opening monologues (where RECAP_VOCAB appears in turns immediately before the trigger turn) without flagging legitimate records far from any recap language.

**Why Tier 2.** Compression Cadence's D4 (spec §6) already implemented bounded recap-state detection (position ≤3% of episode + 15-turn lookback). The lesson is therefore confirmed at architecture-design time, not patch-time, in CC. Promote if a future ship implements unbounded recap-state detection and pays for it; otherwise this is already standard practice and doesn't need a separate v3 lesson.

---

### Candidate 19 — D-rule numbering with patch-ID provenance

**Source ship:** Compression Cadence (Phase 3 calibration extended spec-defined D1 with Patch 3 and Patch 4 vocabulary; Patches 1/2/4 introduced new D5/D6/D7).

**Pattern.** When calibration extends a spec-defined D-rule (CC's Patch 3 added episode-end broadcast-close vocabulary to D1; Patch 4 added stream-meta vocabulary to D1) vs. introducing a new D-rule (Patches 1, 2, 4 → D5, D6, D7), the audit trail in stats files and findings docs needs to encode which is which. The CC Phase 5 stats md initially listed `D1, D2, D5, D6, D7` without explaining the gap; the legend was added retroactively.

**Forward rule.** D-rules carry both a numeric identifier and a provenance tag (spec / patch-N-extension / patch-N-new) in stats files and findings docs. Phase 5 stats output should auto-emit a D-rule legend mapping each D-N to its spec § reference or patch ID.

**Why Tier 2.** This is operational, not architectural — it's about audit-trail legibility, not extractor design. May not warrant a v3 lesson at all; might belong in a separate operational-practices doc. Filed here for visibility; promotion-readiness depends on whether v3 maintainers want operational lessons in the same doc as architectural ones.

---

### Candidate 20 — Idiomatic-concession lookahead for grant-verb triggers

**Source ship:** Loot/Reward (`ILL_GIVE_YOU_THAT_RE` cleared "I'll give you that" — concessive idiom, not material grant).

**Pattern.** Grant-verb triggers (`I'll give you`, `you may have`, `here's`) commonly appear in idiomatic concession forms that aren't literal grants. "I'll give you that" = fair point; "I'll allow it" = ruling on a player request; "point taken" = concession. These idioms survive Stage 0 (Matt's voice, present tense, refers to a specific in-fiction state) but are semantically inverted.

**Forward rule.** Grant-verb triggers that commonly appear in idiomatic concession forms need a lookahead reject before category routing. Implementation: regex lookahead for `that + clause terminator or concessive conjunction`.

**Why Tier 2.** Single-ship. Compression Cadence's trigger families don't include grant-verbs. The pattern is general (idiomatic-vs-literal verb senses) but the specific implementation is LR-domain. Promote if another grant-verb-bearing extractor surfaces analogous evidence.

---

### Candidate 21 — Knowledge-grant inversion check

**Source ship:** Loot/Reward (KNOWLEDGE_NEGATION_RE cleared `you're not entirely certain` — negation of knowledge, not delivery).

**Pattern.** KNOWLEDGE_GRANT triggers include phrases like `you're aware that` or `you know that` which can be negated (`you're not entirely certain`, `you don't yet know`) to produce semantically inverted records that pass Stage 0 (Matt's voice, present tense, specific in-fiction state) but invert the category's claim.

**Forward rule.** Knowledge-shaped triggers are vulnerable to negation; include an explicit negation-check in Stage 0 or Stage 1 classification for any KNOWLEDGE_GRANT-style family.

**Why Tier 2.** Single-ship. Related to Candidate 13 (physical-state polysemy) which also handles negation, but the implementation is different (Candidate 13 handles state-recovery context; Candidate 21 handles direct lexical negation). If Candidate 13 promotes to v3 with a richer polysemy-check framing, Candidate 21 may fold into it.

---

### Candidate 24 — Phase 1 hypotheses must be validated against actual extractor taxonomies

**Source ship:** Cross-Extractor Analysis (X3 rejection, replaced by X3b directional flip).

**Pattern.** Cross-extractor research questions inherited verbatim from source ships' §9 deferred-question inventories may be unanswerable as filed when the inheriting question's premise depends on extractor capabilities the source ship's findings doc didn't enumerate. LR-X1 assumed EC's taxonomy carried perception/investigation/insight signals (a reasonable assumption from outside EC's findings doc); cross-extractor verification revealed EC's six categories are exclusively combat-onset (interruption, npc_turns_hostile, wave_or_phase_shift, player_action_escalation, environmental_materialization, trap_activation). The X3 join produced ~0.3% match rate not because Matt doesn't telegraph rewards, but because the question was unanswerable.

The reframe to X3b (directional flip: do LR quest-offers precede EC combat-initiations?) took ~20 lines of code and preserved the cross-extractor pipeline's value on this question, but the lesson is that the misspecification should have been caught at Phase 1, not Phase 2.

**Forward rule for v3.** Phase 1 specs for cross-extractor analysis ships must include an explicit taxonomy-verification step: each X-question's required source-extractor categories listed and confirmed against the source extractors' actual category lists. The verification step lives in Phase 1, not Phase 2 — catching this before Phase 2 spends effort building joins for unanswerable questions.

**Why Tier 2.** Single-ship evidence. The lesson is general (any future cross-extractor pipeline should run this verification) but the empirical demonstration is X3 alone. Promote to Tier 1 if a second cross-extractor ship surfaces an analogous misspecification.

---

### Candidate 25 — Cross-extractor proximity windows should be set against per-source category-density baselines

**Source ship:** Cross-Extractor Analysis (X3b window-scaling, X4 R3 window-sensitivity).

**Pattern.** Phase 1 §13.3 (c) locked configurable per-question windows with a 15-turn default. X3b showed the signal rate jumps from 1.6% at 25 turns to 8.2% at 50 turns and is flat thereafter — the 15-turn default would have understated the signal materially. X4's R3 rule used 25 turns by default; the actual rule's sensitivity to that window wasn't tested before publication. Cross-extractor proximity windows interact with per-source category density: sparse sources (EC at 1.21 records/episode) need wider windows than dense sources (TM at 25.7 records/episode).

A single global default window is wrong on its face when paired sources have order-of-magnitude differences in record density. The Phase 1 spec's §13.3 lock was operationally correct (per-question configurable, default 15) but didn't anticipate that the "configurable" part would matter substantially for every join.

**Forward rule for v3.** Phase 1 specs for cross-extractor analysis ships should set proximity-window defaults per source-pair, not globally. Window default = ~3-5× the typical inter-record turn-distance for the sparser source in the pair. Phase 1 spec should include a per-pair table of recommended windows derived from source-extractor record density, alongside the per-pair intersection counts.

**Why Tier 2.** Single-ship evidence. The lesson is mechanical (window-tuning against record density is good practice) but the empirical demonstration here is two X-questions in one ship. Promote if a second cross-extractor ship's results materially change at window-tuning.

---

## Tier 3 — Corpus-specific, recommend filing in `CORPUS_BUILDER.md` or `notes/`

These two patterns are real and recurring but specific to the CRD3 corpus's production-context features. They belong in corpus-handling documentation rather than cross-extractor architectural doctrine.

### Candidate 22 — Donor-read DISCOURSE filter for CRD3

**Source ship:** Loot/Reward (`donor_read_misread_as_npc` family cleared as Phase 3 patch).

**Pattern.** Matt reading out sponsor or donation content during stream breaks ("from the Matt Mercer fan club / \$50 donation / we have a message from...") fires material-loot triggers on item names and currency-sounding amounts.

**Recommended location.** `CORPUS_BUILDER.md` section on CRD3-specific OOC vocabulary. This is a corpus-handling concern, not a cross-extractor architectural lesson; it would apply only to extractors operating on CRD3 (or similar live-stream-with-donor-reads corpora).

---

### Candidate 23 — Sale-price-with-refund-contingency disambiguation

**Source ship:** Loot/Reward (`sale_price_with_refund_contingency` family, deferred singleton).

**Pattern.** Rental and deposit pricing ("hold onto it for 500 gold", "deposit of N gp") mimics quest contingency markers ("advance of N gp", "upon completion"). LR's `is_sale_transaction` helper catches standard transaction context but not refund-form pricing.

**Recommended location.** LR-specific patch backlog or `CORPUS_BUILDER.md` section on D&D-specific commerce vocabulary. The pattern is too narrow to warrant a cross-extractor lesson.

---

## Summary

| Tier | Count | Disposition |
|---|---:|---|
| Tier 1 — recommended for v3 promotion | 4 | Promote as Lessons 12–15 at next v2→v3 transition |
| Tier 2 — filed awaiting cross-ship confirmation | 8 | Re-evaluate at next v3 promotion review or next ship |
| Tier 3 — corpus-specific, file elsewhere | 2 | Move to `CORPUS_BUILDER.md` or extractor-specific docs |
| **Total candidates filed** | **14** | |

Source breakdown by ship:
- Loot/Reward (Ship 3): 6 candidates (Tier 1: 0; Tier 2: 4; Tier 3: 2)
- Compression Cadence (Ship 4): 6 candidates (Tier 1: 4; Tier 2: 2)
- Cross-Extractor Analysis (Ship 5): 2 candidates (Tier 1: 0; Tier 2: 2)

Compression Cadence carries the cross-ship-joint candidates because its findings explicitly framed its lessons against TM and LR precedent; Loot/Reward's candidates are framed against its own ship's calibration only. Cross-Extractor's candidates are pipeline-architectural rather than extractor-architectural — they apply to future cross-extractor work specifically. This is a documentation pattern, not a substantive difference — LR's candidates may have joint-ship character that wasn't surfaced at LR's findings time.

---

## What this doc isn't

- **Not authoritative.** `corpus_builder_lessons_v2.md` remains the canonical reference. v3 doesn't exist yet; this is a staging file for its eventual creation.
- **Not exhaustive.** Future ships will surface additional candidates. This doc captures Ships 3, 4, and 5 only.
- **Not a substitute for findings docs.** Each candidate's full context lives in its source ship's findings doc §6 and §7. This doc summarizes for cross-ship promotion review, not for first-time learning of the pattern.

---

## Reference: candidate source documents

| Candidate | Source ship | Source doc | Source section |
|---|---|---|---|
| 12. Within-turn dedup | Time-Mention + Compression Cadence | `track5_findings_time_mention.md`, `track5_findings_compression_cadence.md` | TM Patch 1; CC §7 |
| 13. Physical-state polysemy | Loot/Reward + Compression Cadence | `track5_findings_loot_reward.md`, `track5_findings_compression_cadence.md` | LR §7 Lesson 5; CC §7 |
| 14. Subject-class check | Compression Cadence | `track5_findings_compression_cadence.md` | §6, §7 |
| 15. Sample-size effect on long-tailed categories | Compression Cadence | `track5_findings_compression_cadence.md` | §3, §7 |
| 16. Object-aware routing | Loot/Reward | `track5_findings_loot_reward.md` | §7 Lesson 1 |
| 17. Atmospheric vs narrative time phrase | Compression Cadence | `track5_findings_compression_cadence.md` | §6, §7 |
| 18. Bounded recap-state lookback | Loot/Reward | `track5_findings_loot_reward.md` | §7 Lesson 2 |
| 19. D-rule provenance numbering | Compression Cadence | `track5_findings_compression_cadence.md` | §2, §7 |
| 20. Idiomatic-concession lookahead | Loot/Reward | `track5_findings_loot_reward.md` | §7 Lesson 4 |
| 21. Knowledge-grant inversion | Loot/Reward | `track5_findings_loot_reward.md` | §7 Lesson 5 |
| 22. Donor-read DISCOURSE | Loot/Reward | `track5_findings_loot_reward.md` | §7 Lesson 3 |
| 23. Sale-price refund disambiguation | Loot/Reward | `track5_findings_loot_reward.md` | §7 Lesson 6 |
| 24. Phase 1 hypotheses against actual extractor taxonomies | Cross-Extractor Analysis | `track5_findings_cross_extractor.md` | §5, §7 |
| 25. Cross-extractor proximity windows per source-pair | Cross-Extractor Analysis | `track5_findings_cross_extractor.md` | §7 |
