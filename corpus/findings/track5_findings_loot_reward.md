# Loot/Reward — Findings (v1.0)

**Ship:** Track 5, Ship 3 — Loot/Reward Extractor
**Source corpus:** CRD3 c=2 alignment, 140 unique episodes (94 C1, 46 C2)
**Extractor version:** `loot_reward_v1` (Phase 3.6 final)
**Records emitted:** 568 across 140 episodes
**Date completed:** 2026-05-08

---

## 1. Questions asked

Six research questions verbatim from the spec (§1):

1. How often do rewards arrive after tension?
2. How does Matt frame social vs mechanical rewards?
3. How do NPC rewards differ from environmental rewards?
4. How does Matt build up to a reward (cadence, lead time)?
5. How does Matt handle reward consequence persistence (lasting narrative weight)?
6. How does Matt handle reward absence — when players expect a payoff and don't get one?

Question 6 is structurally different. Its detection shape is "expected event that didn't fire," which requires cross-extractor signal. Single-extractor coverage is partial; see §6.

---

## 2. Method

**Phase walk.** Recon on 7 C2 episodes (seed 5555, stratified early/mid/late, disjoint from all prior Encounter Cadence and Time-Mention eval sets). Recon produced the six-category taxonomy, the phrase-span Stage 0 architecture with NPC-voice routing, and the six §11 decisions locked before Phase 2. Hand-sample on 10 episodes (seed 6666), producing 41 judged calibration records across 5 calibration cycles. Patches 1–4 cleared four named FP families; seven singletons were deliberately deferred per Phase 3 operating rules. Phase 3.5 added sale-price disambiguation and fixed a latent quote-detection bug (curly-quote vs straight-quote encoding in `is_phrase_in_npc_speech`). Phase 3.6 added object-aware give/grant routing (Patch A) and bounded recap-state detection (Patch B). Gate-set construction (7 recon episodes, 25 records, seed 7777) measured once at Phase 4. Validation-set construction (123 mechanically-excluded episodes, 15 records, seed 9999) measured once at Phase 5.

**Decisions locked at §11.**
- §11.1: All six categories (MATERIAL_LOOT, QUEST_OFFER, NPC_FAVOR_GRATITUDE, MECHANICAL_GRANT, KNOWLEDGE_GRANT, ENVIRONMENTAL_DISCOVERY) retained.
- §11.2: Phrase-span Stage 0 with NPC-voice routing. This is the structural inversion of Time-Mention's NPC-voice handling: in Loot/Reward, the trigger phrase appearing inside NPC dialogue routes to QUEST_OFFER or NPC_FAVOR_GRATITUDE rather than being rejected. The recon's richest reward shapes — multi-clause quest offers, NPC gratitude — are exclusively inside NPC voice.
- §11.3: Reward-absence in-scope, single-extractor narrated-absence only. Broader cross-extractor form deferred.
- §11.4: CRD3 only (deviates from CORPUS_BUILDER.md table's `CRD3 + FIREBALL`; recon evidence argues reward events are multi-turn flow-shaped, which FIREBALL's snapshot format cannot carry).
- §11.5: 10-episode hand-sample (default).
- §11.6: NPC voice routes trigger phrase to QUEST_OFFER / NPC_FAVOR_GRATITUDE; Matt voice routes to MATERIAL_LOOT / KNOWLEDGE_GRANT / ENVIRONMENTAL_DISCOVERY / MECHANICAL_GRANT.

**Eval-set construction and integrity.**
- Hand-sample: 10 episodes, seed 6666. Judged as calibration surface; informed all Phase 3 patches.
- Gate: 7 recon episodes, 25 records, seed 7777. These episodes were also used for extractor development (pattern design, DISCOURSE filter tuning). Mechanical disjointness from hand-sample by episode; disjointness from calibration by record index. Measured once.
- Validation: 15 records, seed 9999, drawn from the 123 episodes outside both hand-sample and recon. First mechanically episode-disjoint surface in this ship. Judged blind (Phase 5b). Measured once.

No LLM was used in the execution path at any stage. All classification is deterministic regex.

---

## 3. Reliability — read this before quoting any number below

Three precision surfaces, measured sequentially:

| Surface | Episodes | Records | Correct | Precision | Notes |
|---|---:|---:|---:|---:|---|
| Hand-sample (calibration) | 10 | 29 | 21 | **72.4%** | 2 additional defensible; 6 FP families remain |
| Gate (held-out) | 7 | 25 | 17 | **68.0%** | C2E036_t1103 reclassified correct by Patch A; `verdict_at_v2` stale in JSON |
| Validation (mechanically excluded) | 12 | 15 | 10 | **66.7%** | 3 reclassified by Patch A, 1 cleared by Patch B; `verdict_at_v2` stale for 3 records |

Convergence within 4.4pp across three surfaces (72.4% → 68.0% → 66.7%) suggests the extractor's strict precision is a meaningful number, not a calibration artifact. When held-out and mechanically-excluded surfaces agree within noise, the calibration number is not just overfitting to the hand-sample.

**Sharpened claim language for downstream consumers:**

> Strict precision converged at 67–72% across calibration, gate, and validation surfaces. Frequency directionally reliable; individual records suggestive.

> FP rate ~28–30% of emitted records; concentrated in singleton families documented in §7.

> n=15 validation binomial CI ±25pp; precise wild-precision value uncertain even with three-surface convergence. The convergence is reassuring but not a substitute for a larger validation pool.

The gate surface shares episode IDs with the recon episodes used during extractor development. The gate records were not reviewed during calibration (raw_text withheld), but the FP shapes from those episodes may have informed DISCOURSE filter tuning. This is a known limitation of the single-ship pipeline when the full 140-episode corpus must be split into development / calibration / gate / validation.

---

## 4. Headline numbers

### Per-episode density

| Metric | Value |
|---|---:|
| Episodes processed | 140 |
| Episodes producing ≥1 record | 134 (95.7%) |
| Episodes producing zero records | 6 (4.3%) |
| Total records emitted | 568 |
| Mean records per episode | 4.06 |
| Median records per episode | 4.0 |
| Std. dev. | 2.97 |
| Min records (producing episodes) | 1 (C1E004) |
| Max records per episode | 19 (C1E014) |

Zero-record episodes: C1E050, C1E061, C1E064, C1E088, C1E109, C2E002. All six are C1-mid episodes; the pattern likely reflects downtime-heavy or non-combat-non-social sessions where no rewards fire.

Compared to the two prior ships: Encounter Cadence emitted 170 records (1.21/ep), Time-Mention emitted 3,592 records (25.7/ep). Loot/Reward at 4.06/ep sits between them — rewards fire more often than encounter initiations, far less often than time-mentions. Every combat-adjacent or social episode produces at least one reward record.

### Category breakdown

| Category | Count | Proportion | Voice |
|---|---:|---:|---|
| MECHANICAL_GRANT | 154 | 27.1% | Matt |
| QUEST_OFFER | 121 | 21.3% | NPC |
| MATERIAL_LOOT | 104 | 18.3% | Matt |
| KNOWLEDGE_GRANT | 88 | 15.5% | Matt |
| NPC_FAVOR_GRATITUDE | 88 | 15.5% | NPC |
| ENVIRONMENTAL_DISCOVERY | 13 | 2.3% | Matt |

MECHANICAL_GRANT is the single most frequent category — surprising given the spec's recon emphasis on material loot. This partly reflects Matt's frequent mid-combat advantage grants, inspiration grants, and short/long rest recovery narration. QUEST_OFFER (21.3%) and NPC_FAVOR_GRATITUDE (15.5%) together account for 36.8% of records and are exclusively NPC-voice — Matt's social reward delivery is substantially mediated through quoted NPC dialogue.

ENVIRONMENTAL_DISCOVERY at 2.3% (13 records) is the thinnest category. It was marked TENTATIVE at §4 and survived as a real category; the pattern (object presentation in a narrated scene without explicit handover) does occur but is rare relative to active-handover loot.

### Campaign split

| Campaign | Episodes | Records | Records/episode |
|---|---:|---:|---:|
| C1 | 89 | 355 | 3.99 |
| C2 | 45 | 213 | 4.73 |

C2 carries ~18% higher per-episode density. Whether this reflects genuine pacing drift between Matt's C1-era and C2-era reward structure or an episode-length artifact is open. Both campaigns produce records in essentially every non-pure-downtime episode.

### NPC-voice fraction

37.1% of all records (211 / 568) are `is_in_npc_voice=True`. These are exclusively QUEST_OFFER and NPC_FAVOR_GRATITUDE records. The fraction is stable with the category proportions above (QUEST_OFFER + NPC_FAVOR_GRATITUDE = 36.8%).

### Direction breakdown

| Direction | Count | Proportion |
|---|---:|---:|
| delivered | 447 | 78.7% |
| offered | 121 | 21.3% |

The `offered` count equals the QUEST_OFFER count exactly (121), confirming direction routing is correct. All non-QUEST_OFFER records route to `delivered`. The offer/delivery pairing problem — tracking whether a QUEST_OFFER record gets matched by a `delivered` record in a later episode — is out of scope for this ship; the `direction` field is the cross-episode join key.

### Currency totals

| Category | Corpus total (gp-equivalent) |
|---|---:|
| MATERIAL_LOOT | 528,523 gp |
| QUEST_OFFER | 468,285 gp |
| **Total** | **996,809 gp** |

Close to 1 million gold across 140 episodes and roughly 100 in-fiction campaign months. Per-episode mean is ~7,100 gp across all currency-bearing episodes. These figures are noisy — the extractor does not yet distinguish narrative exaggeration from actual party receipts, and individual high-value quest offers (5,000 gp advances) skew the distribution.

### v3.5 → v3.6 full-parse patch impact

Across the 123 unseen episodes (full_v36 vs full_v35_archive):

| Category | v3.5 | v3.6 | Delta |
|---|---:|---:|---:|
| MATERIAL_LOOT | 110 | 82 | −28 |
| MECHANICAL_GRANT | 115 | 136 | +21 |
| QUEST_OFFER | 105 | 101 | −4 |
| KNOWLEDGE_GRANT | 76 | 75 | −1 |
| NPC_FAVOR_GRATITUDE | 71 | 71 | 0 |
| ENVIRONMENTAL_DISCOVERY | 9 | 9 | 0 |
| **Total** | **486** | **474** | **−12** |

**Patch A (object-aware routing):** The +21 MECHANICAL_GRANT / −28 MATERIAL_LOOT shift reflects reclassification of "I'll give you advantage/inspiration/etc." records from MATERIAL_LOOT (and a few from QUEST_OFFER) to MECHANICAL_GRANT. The QUEST_OFFER_TRIGGER's short "I'll give you" match was suppressing the longer MECHANICAL_GRANT_TRIGGER match via the dedup pass; Patch A added an object-aware override that fires before `route_category` when the mechanical-benefit object is detected.

**Patch B (bounded recap-state rejection):** The net −12 record delta (beyond the Patch A reclassifications, which are count-neutral) is from recap-state rejection. v3.5's `derive_recap_state` searched all turns 0..candidate across the first 10% of the episode; any episode with a single RECAP_VOCAB token early on would flag all turns in the first ~260-turn window as recap. Patch B narrowed the lookback to ±15 turns, which eliminates false positives like C2E035 (where SAM's turn 3 "As I said last week..." was flagging correct loot records at turns 116 and 248). The 12 suppressed records in full_v36 are genuine recap-opening monologue reward mentions — Matt narrating prior session events, not new reward events.

---

## 5. Research questions

### Q1 — How often do rewards arrive after tension?

42 of 568 records carry `has_perception_buildup=True` (7.4%). These are reward-emitting turns that fell within the perception-buildup proximity window — a turn within ~8 turns of a perception/investigation/insight check trigger.

| Category | Buildup-flagged |
|---|---:|
| MATERIAL_LOOT | 19 |
| KNOWLEDGE_GRANT | 10 |
| MECHANICAL_GRANT | 6 |
| NPC_FAVOR_GRATITUDE | 3 |
| ENVIRONMENTAL_DISCOVERY | 3 |
| QUEST_OFFER | 1 |

MATERIAL_LOOT is the most commonly buildup-preceded reward shape (19/104 = 18.3% of its records carry the buildup flag), consistent with the recon observation that `make a perception check` / `make an investigation check` is the loudest pre-loot signal.

**Caveat:** 7.4% is a lower bound. The `has_perception_buildup` flag fires on a strict proximity condition (~8-turn window), and perception checks that precede loot discovery by more than that window are missed. The full cadence answer — what fraction of rewards follow *any* buildup regardless of distance — requires cross-extractor join with encounter_cadence records and is deferred.

### Q2 — How does Matt frame social vs mechanical rewards?

The NPC-voice / Matt-voice split tells the story directly:

- **Social rewards (QUEST_OFFER + NPC_FAVOR_GRATITUDE):** 209 records, 36.8% of corpus. Both categories are exclusively NPC-voice mediated — Matt delivers social rewards by voicing NPCs explicitly thanking, commissioning, or acknowledging the party. The trigger phrase is inside quoted NPC speech in nearly every case.
- **Mechanical rewards (MECHANICAL_GRANT):** 154 records, 27.1% of corpus. All Matt-voice. The pattern is Matt narrating a specific PC advantage, inspiration grant, rest recovery, or reroll in narrative present ("I'll give you advantage on this," "you regain 3d6 hit points").
- **Material rewards (MATERIAL_LOOT + ENVIRONMENTAL_DISCOVERY):** 117 records, 20.6%. Matt-voice, descriptive present-tense enumeration.
- **Informational rewards (KNOWLEDGE_GRANT):** 88 records, 15.5%. Matt-voice, report-of-learning framing.

The structural inversion identified in the spec (§5) confirms at corpus scale: the most socially-laden reward types (quest offers, gratitude) are delivered through NPC voice; the most mechanically-concrete rewards (advantage, healing) are delivered through Matt's GM narration. Track 4 can derive from this that "social reward" in Virgil should route through NPC dialogue output, not DM narration output.

### Q3 — How do NPC rewards differ from environmental rewards?

NPC-mediated rewards (QUEST_OFFER + NPC_FAVOR_GRATITUDE, 209 records) are 16.1× more frequent than environmental discovery (ENVIRONMENTAL_DISCOVERY, 13 records). The density distinction is meaningful: NPC relational rewards fire multiple times per social-interaction episode; environmental discoveries are sporadic, concentrated in exploration-heavy scenes.

Per-episode density among producing episodes:
- QUEST_OFFER: ~0.86/episode
- NPC_FAVOR_GRATITUDE: ~0.63/episode
- ENVIRONMENTAL_DISCOVERY: ~0.09/episode (less than one per episode across all 140)

ENVIRONMENTAL_DISCOVERY at 2.3% is the thinnest category by a factor of 7 over the next-thinnest (KNOWLEDGE_GRANT at 15.5%). The recon marked it TENTATIVE; the corpus confirms it is real but rare. Track 4 should not model environmental discovery as a standard reward shape — it's an occasional scene-texture element, not a session rhythm anchor.

### Q4 — How does Matt build up to a reward (cadence, lead time)?

The `has_perception_buildup` flag captures the single-extractor-detectable surface: 7.4% of rewards fire within 8 turns of a perception/investigation buildup. MATERIAL_LOOT is the most buildup-preceded shape (18.3% of its records).

What the single-extractor pass cannot answer: the full distribution of buildup lead times, rewards that followed a buildup beyond the 8-turn window, and non-perception-check buildups (combat-escalation → loot, social-negotiation → quest offer). These require cross-extractor join:
- encounter_cadence records carry episode position of combat initiation → loot reward delta
- time_mention `scene_transition` records carry downtime breaks → quest offer alignment

Filed for cross-extractor analysis phase. The partial answer here is: when buildup is detectable, it typically leads to MATERIAL_LOOT or KNOWLEDGE_GRANT (not QUEST_OFFER, which is NPC-dialogue-initiated and doesn't follow a perception check pattern).

### Q5 — How does Matt handle reward consequence persistence?

`has_persistence_marker=True` on 2 of 568 records (0.4%). The persistence vocabulary (`permanently`, `from now on`, `henceforth`, `until you`, `for the rest of`, `forever`) fires extremely rarely in the corpus. Both flagged records are borderline cases — one QUEST_OFFER (likely a durable obligation clause), one MECHANICAL_GRANT.

This is the research question with the thinnest single-extractor signal. The 0.4% rate almost certainly understates real persistence framing — Matt often embeds persistence language in the reward narration rather than in a discrete persistence-marker phrase. The regex fires on explicit scope markers attached to the reward phrase; implicit persistence ("you've been granted the title of...") is missed.

**Honest framing:** The persistence-marker flag as implemented is a directional signal that the record may carry durable narrative weight. The 0.4% rate should not be interpreted as "Matt almost never frames rewards as persistent." The signal is too thin to support a Q5 conclusion from single-extractor data alone.

### Q6 — How does Matt handle reward absence?

`absence_marker=True` on 0 of 568 records. The single-extractor absence detection (ABSENCE_NEGATION patterns + proximity to `had_buildup=True`) produced no records across the full corpus.

The architectural constraint: the absence detection requires both a perception buildup in the preceding 8 turns AND an explicit negation phrase (`nothing here`, `you see nothing`, `comes up empty`) in the same turn as a trigger phrase. In practice, Matt's absence narration typically appears in a turn without any reward-family trigger phrase, so the detection never fires. The mechanism was correctly implemented but fires on a near-empty surface.

The full Q6 shape — "buildup expected payoff didn't fire" — is cross-extractor:
- encounter_cadence escalations without subsequent loot records in the episode → candidate absence
- time_mention scene_transition immediately post-combat without preceding loot → candidate absence

This cross-extractor join is a separate ship, as stated in the spec. The single-extractor Q6 answer from this ship is: **the narrated-explicit-absence form is not detectable without cross-extractor context given current architecture**, and the broader form requires a dedicated analysis pipeline.

---

## 6. Failure analysis — remaining FP families

Tabulated from all three eval surfaces. These are deferred singletons or unresolved families as of Phase 3.6.

| Family | Records | Source | Description |
|---|---:|---|---|
| `description_offer_not_loot` | 1 | Handsample | "I'll give you a detailed description" — speech-act object, not material grant. `QUEST_OFFER_TRIGGER` fires on `I'll give you` + non-reward noun. |
| `damage_math_misread` | 1 | Handsample | "I'll give you the direct amounts here" — arithmetic narration mid-combat. |
| `hostile_npc_action_misread` | 1 | Handsample | "Rifling through whatever it might have had" — hostile NPC looting a body, not party loot. Actor-identification beyond regex scope. |
| `mid_combat_existing_item_description` | 1 | Handsample | "The gem with a faint glimmer" — pre-owned vestige item gaining narrative focus, not discovery. `ENVIRONMENTAL_DISCOVERY_TRIGGER` pattern too broad. |
| `condition_recovery_misread_as_knowledge` | 1 | Handsample | "Vision comes back to you" — condition recovery (blindness ending), not lore return. Subject-noun disambiguation needed. |
| `awareness_phrase_misread_as_knowledge` | 1 | Handsample | "Make sure that you're aware of everything around you" — generic vigilance phrase, not information grant. `aware of` + vague indefinite object. |
| `sale_price_with_refund_contingency` | 1 | Validation | "I can let you hold onto it for 500 gold" — rental/deposit pricing mimics quest contingency markers. `is_sale_transaction` catches standard `how much/transaction` context but not refund-form pricing. |
| `ill_give_you_your_action_turn_mechanics` | 1 | Validation | "I'll give you your action back" — turn-economy mechanics, not a MECHANICAL_GRANT reward. Object-aware override targets game-benefit nouns but not turn-structure nouns. |
| `for_your_aid_misrouted_to_npc_favor` | 1 | Validation | "For your aid" / "I can give you" in fragmentary NPC speech → NPC_FAVOR_GRATITUDE, judge expects QUEST_OFFER. Voice routing correct; category boundary ambiguous. |
| `rest_inquiry_past_tense` | 1 | Validation | "Did you take a long rest?" — past-tense inquiry about rest, not rest grant. Emits MECHANICAL_GRANT defensibly. |
| `npc_can_give_misrouted_to_quest_offer` | 1 | Validation | "I can give you a map" — generic capability statement not clearly an offer. |
| `debt_imposition_misread_as_quest_offer` | 1 | Gate | C2E004_t750 — durable debt framing (`until you've worked off the debt`) routed to QUEST_OFFER. Deliberate non-patch: clearing would require relaxing the contingency-offer pattern. |
| `rules_explanation_status_condition` | 1 | Gate | "You're aware of" in a status-condition explanation — same shape as KNOWLEDGE_GRANT but rules-adjudication context. |

All thirteen are singletons across the eval surfaces. None recur at sufficient frequency across the three surfaces to warrant a patch cycle. Per Phase 3 operating rules, singleton-by-singleton patching produces brittle, overfit rules.

---

## 7. v3 lessons-doc candidates filed

Six patterns confirmed across this ship's calibration cycles, recommended for `corpus_builder_lessons_v3_candidates.md`:

**Object-aware routing on generic give/grant verbs.** QUEST_OFFER_TRIGGER short-matched "I'll give you" (span end before object), suppressing the MECHANICAL_GRANT_TRIGGER's longer match via dedup. The fix — checking the mechanical-benefit object after the trigger span before calling `route_category` — produced consistent reclassification across all three eval surfaces (C2E036_t1103 in gate, three records in validation). Forward rule: when a longer trigger overlaps a shorter trigger on the same start position, the dedup pass drops the longer match; object-aware overrides must fire before `route_category`.

**Recap-state detection needs bounded windows.** Searching all turns 0..candidate for RECAP_VOCAB across the first 10% of the episode caused C2E035's SAM "as I said last week" (turn 3) to flag correct loot records at turns 116 and 248 as recap. A ±15-turn lookback window is sufficient to catch real episode-recap-opening monologues (where RECAP_VOCAB appears in the turns immediately before the reward turn) without burning correct records far from any recap language. Forward rule: recap-state detection must be windowed, not whole-episode.

**Donor-read DISCOURSE filter.** Matt reading out sponsor or donation content ("from the Matt Mercer fan club / $50 donation / we have a message from...") fires material-loot triggers on item names and currency-sounding amounts. Cleared as a Phase 3 patch family (`donor_read_misread_as_npc`). Forward rule: production-OOC reject vocabulary needs a donation-read branch for any extractor operating on CRD3; this is a corpus-wide false-positive family.

**Idiomatic-concession lookahead.** "I'll give you that" — concessive idiom meaning "fair point," not a material grant. Cleared by `ILL_GIVE_YOU_THAT_RE` (lookahead for `that + clause terminator or concessive conjunction`). The class likely includes "fair point," "I'll allow it," "point taken" — non-literal grant verbs that survive trigger-phrase detection. Forward rule: grant-verb triggers that commonly appear in idiomatic concession forms need a lookahead reject before category routing.

**Knowledge-grant inversion.** KNOWLEDGE_GRANT_TRIGGER included `you're not entirely certain` — the negation of knowledge, not its delivery. The phrase survives Stage 0 (it's Matt's voice, present tense, refers to a specific in-fiction state) but is semantically inverted. Cleared by KNOWLEDGE_NEGATION_RE. Forward rule: knowledge-shaped triggers are vulnerable to negation; include an explicit negation-check in Stage 0 or Stage 1 classification for any KNOWLEDGE_GRANT family.

**Sale-price-with-refund-contingency.** Rental and deposit pricing (`hold onto it for N gold`, `deposit of N`) mimics quest contingency markers (`advance of N`, `upon completion`). The `is_sale_transaction` helper catches standard transaction context (preceding `how much / transaction / for sale`) but not refund-form pricing. Deferred as a singleton; present in validation as an unresolved family.

---

## 8. What this enables for Track 4

This findings doc lands a structured, quantified account of how Matt frames rewards in CRD3. Three results are directive-shippable:

**NPC-voice routing inversion.** 36.8% of all reward records are NPC-voice mediated (QUEST_OFFER + NPC_FAVOR_GRATITUDE), and these are the social reward shapes — commissioning, payment, gratitude, relationship acknowledgement. Virgil's reward-output layer should route social/relational rewards through NPC dialogue, not DM narration. When the party completes a task for an NPC patron, Matt's pattern is to voice the NPC delivering thanks and payment, not to narrate it in third-person. This is a direct behavioral directive.

**Mechanical grant density.** MECHANICAL_GRANT is 27.1% of all records — the most frequent single category. Matt grants advantage, inspiration, rerolls, and rest recovery at a rate of roughly one per session. These are delivered tersely in Matt's own voice mid-play ("I'll give you advantage on this," "you regain"). Track 4 mechanical grant output should be short, present-tense, directly addressed to the PC ("you gain", "you regain").

**Reward-after-buildup frequency.** 7.4% of rewards are buildup-preceded by a perception/investigation check. For design: roughly 1 in 13 rewards in the corpus follows a visible roll-based tension beat. This is a directional signal that rewards frequently arrive without explicit roll buildup — material loot enumerations, quest offers, mechanical grants — rather than always following a suspense-building check. Virgil should not assume a roll always precedes a reward.

The single-extractor narrated-absence data (0 records) is not a findable; the absence detection architecture does not produce signal without cross-extractor context. Q4's full cadence answer and Q6's full absence answer require a cross-extractor join ship. Loot/Reward's records are structured for that join: `episode`, `trigger_turn_number`, `episode_position_pct`, and `direction` fields all participate in the encounter_cadence / time_mention overlap queries.

---

## 9. Open questions

1. **Q4 full buildup cadence.** What fraction of rewards follow a perception/investigation/insight check at any distance — not just within 8 turns? Requires cross-extractor join: encounter_cadence provides combat escalation as a buildup proxy; time_mention `scene_transition` provides scene-change as a context reset.
2. **Offer/delivery pairing.** 121 QUEST_OFFER records carry `direction=offered`. Were the offered amounts eventually delivered? Which offers expired unresolved? Requires cross-episode join; filed as Phase 1.5 candidate.
3. **Q6 full absence rate.** "Expected payoff didn't fire" after a tension escalation. Cross-extractor join required; not addressable by single-extractor architecture.
4. **Currency magnitude distribution.** The 996,809 gp total is dominated by a few large quest offers. What is the distribution shape — how often are rewards under 100 gp vs over 1,000 gp? Derivable from `currency_total_gp_equivalent` across the full parse; not pursued in this ship.
5. **Campaign-arc trends.** Do reward frequency or category proportions shift across C1/C2 episode arcs — early vs mid vs late campaign? The per-episode data is in the full parse output; a simple time-series pass over `episode_position_pct` would answer this.

---

## 10. Limitations

1. **123 of 140 episodes were never manually reviewed during eval-set construction.** The hand-sample covered 10 episodes; the recon 7; the validation drew 15 records from 12 episodes. Records from the remaining ~111 episodes are present in the full parse but no human spot-checked their classification.
2. **Gate surface shares episode IDs with recon development set.** The 7 recon episodes informed DISCOURSE filter design; the gate records from those episodes (with raw_text withheld) were measured once blind. Functional but not fully arm's-length.
3. **Absence detection produced zero records.** The `had_buildup + explicit-negation-phrase` proximity requirement is too strict: Matt's absence narration typically occurs in a turn without any reward-family trigger phrase. Single-extractor absence detection is effectively inoperative.
4. **Persistence-marker flag fires on <1% of records.** The 0.4% rate understates real persistence framing; Matt often embeds scope language in non-trigger sentences. Q5 is unanswerable from this signal alone.
5. **Source corpus is c=2 alignment only.** Same constraint as prior ships; confirmed byte-identical to c=3/c=4 by importer comparison only.
6. **Phase 3.6 full-parse extractor applied to 123 episodes; handsample/recon output is Phase 3.5.** The 17 handsample + recon episodes' output files were generated by the Phase 3.5 extractor before Patches A and B. 10 records in those files carry `is_recap_state=True` (no rejection layer in Phase 3.5). If re-parsed with Phase 3.6, those records would be filtered. The corpus-wide `is_recap_state` fraction (1.8%) is an artifact of this; the Phase 3.6 full_v36 pass produces 0 recap records.

---

## 11. Files

| Artifact | Path |
|---|---|
| Extractor source (Phase 3.6 final) | `corpus_builder/extractors/loot_reward.py` |
| Full-parse output (Phase 3.6) | `corpus_builder/output/loot_reward/full_v36/` (474 records, 123 episodes) |
| Full-parse output (Phase 3.5, archived) | `corpus_builder/output/loot_reward/full_v35_archive/` (486 records, 123 episodes) |
| Hand-sample output | `corpus_builder/output/loot_reward/C1E007.json` ... `C2E043.json` |
| Recon output | `corpus_builder/output/loot_reward/recon/` (53 records, 7 episodes) |
| Eval set v2 (hand-sample) | `corpus_builder/eval_sets/loot_reward_handsample_v2.json` |
| Gate set v2 | `corpus_builder/eval_sets/loot_reward_gate_v2.json` |
| Validation set v2 (judged) | `corpus_builder/eval_sets/loot_reward_validation_v2.json` |
| Corpus stats | `corpus_builder/findings/loot_reward_corpus_stats.json` |
| Phase 3 singleton doc | `corpus_builder/findings/phase3_remaining_singletons.md` |
| Phase 3.5 findings | `corpus_builder/findings/phase3p5_sale_price_patch.md` |
| Spec doc | `corpus_builder/findings/track5_loot_reward_phase1_spec.md` |
| Regression runner | `corpus_builder/extractors/test_loot_reward.py` |
| Full-parse runner (Phase 3.6) | `corpus_builder/extractors/run_loot_reward_full_parse_v36.py` |
| Validation builder | `corpus_builder/extractors/build_loot_reward_validation_v1.py` |
