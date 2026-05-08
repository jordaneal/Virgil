# Loot/Reward — Phase 1 Spec

**Ship:** Track 5, Ship 3 — Loot/Reward Extractor
**Phase:** 1 (recon + spec)
**Author:** Phase 1 recon, May 2026
**Locks pending:** §11 decisions, resolved in chat before Phase 2 opens

---

## §1. Mission

The extractor exists to answer six research questions, verbatim:

1. How often do rewards arrive after tension?
2. How does Matt frame social vs mechanical rewards?
3. How do NPC rewards differ from environmental rewards?
4. How does Matt build up to a reward (cadence, lead time)?
5. How does Matt handle reward consequence persistence (lasting narrative weight)?
6. How does Matt handle reward absence — when players expect a payoff and don't get one?

Question 6 is structurally different. Detection shape is "expected event that didn't fire," not "event that fired." It is likely to require cross-extractor signal (encounter_cadence escalations, time_mention scene-transitions). The single-extractor coverage is partial; see §6.

---

## §2. Recon set

Seven C2 episodes were sampled with `random.seed(5555)`, stratified across early / mid / late C2 to avoid clustering. The pool was the 17 C2 episodes (of 46 total) that appear in **none** of the prior eval, gate-set, or validation sets used by Encounter Cadence (v1, v2, v3) or Time-Mention (v1, v2, v3 holdout, validation, boundary stability, d6 precision).

**Recon episodes:**

| Episode | C2 phase |
|---|---|
| C2E004 | early |
| C2E010 | early |
| C2E016 | mid |
| C2E019 | mid |
| C2E033 | late |
| C2E035 | late |
| C2E036 | late |

**Disjointness check.** Union of episode codes referenced in the 10 eval / sample / validation JSONs covers 91 unique episodes (62 C1, 29 C2). The 7 recon episodes intersect zero of them.

**Reproducibility.** Sampling code: stratify the 17 disjoint C2 episodes into early (E001–E015), mid (E016–E030), late (E031–E046); seed `random.seed(5555)`; `random.sample(bucket, 2)` for each of early/mid/late, then `random.sample(remainder, 1)` for the seventh. Deterministic given the disjoint pool.

---

## §3. Observed reward shapes

Recon scanned MATT turns across the 7 episodes (~4,635 MATT turns total) for nine wide-net regex families: presentation verbs, object/loot nouns, currency amounts, perception-check buildup, social-reward framing, mechanical grants, persistence markers, absence/negation, and off-screen narration. Hits across all families were dense — every episode produced 100+ matches across the families, with the heavy clusters in PRESENTATION, OBJECT_LOOT, PERCEPTION_BUILDUP, and SOCIAL_REWARD.

The shapes that consistently surfaced as real reward-bearing events:

**Material loot enumeration.** "Rifling through his bits, you find 21 gold pieces, 45 silver pieces, two platinum pieces" (C2E035 t248). "You find an additional 85 gold pieces, 210 silver, and 45 copper" (C2E010 t1865). "You find a pouch of 20 platinum pieces" (C2E035 t2536). Pattern: `you find [N] [currency-or-item] [, N item]*`. Always Matt's voice. Always in narrative present.

**Quest payment offers (in NPC dialogue).** "I offer an advance of 500 gold pieces and a purse of 4,500 gold pieces upon returning with Miss Mardun within the month" (C2E019 t354). "Consider a 250 gold piece advance and a purse of 1,750 gold pieces upon completion" (C2E019 t367). "750 gold. The advances for both missions" (C2E019 t638). Pattern: NPC speaks an offer — `advance of`, `purse of`, `upon completion`, `for this task` — followed by currency or item enumeration. **The trigger phrase is inside NPC speech.**

**NPC gratitude / social reward.** "I am grateful that you all have kept her safe" (C2E033 t1098). "For that, I'm thankful" (C2E033 t1387). "There I shall reward you for your assistance" (C2E035 t116). Pattern: NPC voicing of `grateful`, `thankful`, `for your service/assistance`, `you have my thanks`, `count on me` — non-material reward landing inside dialogue.

**Mechanical grants (in Matt's voice).** "I'll give you advantage on this" (C2E016 t1862). "That last bit of inspiration to shrug off the poison" (C2E010 t1388). Pattern: Matt narrates a granted in-game benefit, often during combat or skill-resolution. Distinguished from rules-talk (see §7).

**Knowledge / lore grants.** "Gives you the location of the sewer that leads you there" (C2E010 t339). "You're not entirely certain where the inspiration for this knowledge comes from, but you have these images of one of the betrayer gods in history" (C2E016 t1081). Pattern: information as reward — directions, lore, identification of an item or person, prophetic vision. Always Matt's voice.

**Environmental discovery / found objects.** "Sets of gold and silver rings and jewelry" inside a box (C2E016 t760). "A tattered urn and a few small pieces of pottery with intricate gold scrolling" (C2E016 t721). "Jewelry of all sorts of gems and colors" (C2E033 t558). Pattern: object presentation in narrated environment, not handed over by an NPC. Borderline with MATERIAL_LOOT — distinguished by whether the party physically takes the items.

**Buildup phrases.** Most common by far: `Make a perception check`, `Make an investigation check`, `Make an insight check` (>50 hits across the 7 episodes). Lighter buildup signals: `catches your eye`, `your eyes fall on`, `glimmer`, `your eyes drift to`. Buildup precedes reward roughly 30–60% of the time on a quick eyeball; the inverse — buildup that resolves into a non-reward — also occurs (see §6).

**Persistence framing.** "Until you've worked off the debt to the city. To the number of 2,645 gold pieces" (C2E004 t750) — a durable anti-reward. "Permanently pushed to one side" (C2E019 t120) — physical persistence. "For the rest of the day" (C2E019 t1245). "Forever" (C2E016 t2499). Pattern: scope marker (`permanently`, `from now on`, `until you`, `for the rest of`, `henceforth`) attached to a reward or consequence. Cross-cuts category — this is a flag, not a category.

**Absence markers.** Sparse but real: "There is nothing here" (C2E016 t1341). "You see nothing" (C2E010 t580). "No sign of a door" (C2E035 t696). "Nothing catches your eye from those two" (C2E016 t820). Pattern: explicit linguistic negation following a search or perception. Quantitatively rare — ~1–3 per 600-turn episode in the recon.

---

## §4. Candidate taxonomy

Six proposed categories plus one cross-cutting flag. Each category lists trigger-phrase shapes and rough recon frequency. Categories appearing fewer than three times across the recon set are marked TENTATIVE.

**1. MATERIAL_LOOT** — physical objects or currency presented to the party as findable items.
*Trigger shapes:* `you find [N] gold/silver/platinum/copper`, `you find a/the [item]`, `[container] contains`, `inside the [container]`, `tucked / stashed / hidden`. *Recon frequency:* heavy in C2E010, C2E019, C2E035; moderate elsewhere. ~25–40 candidate hits per episode after Stage 0 estimated.

**2. QUEST_OFFER** — explicit reward offered by an NPC contingent on a task. Includes both *advance* (paid up-front) and *delivery* (paid on completion).
*Trigger shapes:* NPC dialogue containing `I offer`, `advance of`, `purse of [N]`, `upon completion`, `for this task`, `you'll be rewarded`, `if you can [task], [reward]`. *Recon frequency:* C2E019 carries 3 multi-clause offers (t354, t367, t638); C2E035 t116 contains "I shall reward you." Across the recon: ~5–8 distinct offer events.

**3. NPC_FAVOR_GRATITUDE** — non-material relational reward expressed by an NPC in dialogue.
*Trigger shapes:* `grateful`, `thankful`, `for your assistance/help/service`, `I owe you`, `count me as a friend`, `you have my thanks`. *Recon frequency:* moderate. ~3–6 events per episode where NPCs interact substantively.

**4. MECHANICAL_GRANT** — DM (Matt) grants an in-game mechanical benefit: advantage, inspiration, healing, rest recovery, ability use. **Distinguished from rules-adjudication discourse** by whether the grant lands on a specific PC in narrative present versus abstract rules description.
*Trigger shapes:* `I'll give you advantage`, `I'll allow [X]`, `you take a short/long rest`, `inspiration`, `you regain`. *Recon frequency:* moderate, ~5–10 per combat-heavy episode.

**5. KNOWLEDGE_GRANT** — information, lore, directions, identification, or prophetic vision presented as reward.
*Trigger shapes:* `gives you the location of`, `you learn`, `you find out`, `comes back to you`, `you remember`, `you're aware`, `images of [X]`. *Recon frequency:* moderate, ~3–8 per episode with research/social scenes. C2E010 t339 (sewer location), C2E016 t1081 (lore of betrayer gods), C2E035 t396 (marid defense).

**6. ENVIRONMENTAL_DISCOVERY** *(TENTATIVE)* — narrated presence of objects in a scene without explicit handover. Borderline with MATERIAL_LOOT (the party can pick them up if they choose) and with PRESENTATION-only narration (descriptive flavor, no reward implied).
*Trigger shapes:* `you see [item]`, `[container] sits / rests`, `on the table / floor / shelf`, decorative object descriptions with implied value (gold scrolling, jewels, gems). *Recon frequency:* ambiguous; counted at 4–6 likely instances across recon but most are scene-decoration and not actionable rewards. Whether this is a real category or a Stage 0 reject family is a §11 decision.

**7. ABSENCE_NEGATION** *(TENTATIVE; possibly out-of-scope; see §6)* — explicit linguistic negation following expected reward delivery.
*Trigger shapes:* `nothing here`, `you see nothing`, `no sign of`, `comes up empty`, `nothing of value/note/interest`, `the [container] is empty`. *Recon frequency:* very low. 1–3 per episode. Insufficient for a robust per-episode statistic on a single-extractor pass.

**Cross-cutting flag — PERSISTENCE_FRAMED.** Not a category; a boolean flag on any of the above.
*Trigger shapes:* `permanently`, `from now on`, `henceforth`, `until you`, `for the rest of`, `for life`, `as long as you carry/wear/wield`, `forever`. Attached to the parent record.

---

## §5. Stage 0 detection plan

**Recommendation: phrase-span Stage 0, not turn-level.** Justified directly from recon evidence — and from a structural inversion of Time-Mention's design.

In Time-Mention, NPC speech was a **DISCOURSE reject** (or near-reject via flag): the trigger phrase appearing inside NPC voice meant the time-mention was probably mechanic-talk or table-chat, not a real time event.

In Loot/Reward, NPC speech is **the primary delivery mechanism for QUEST_OFFER and NPC_FAVOR_GRATITUDE.** The richest reward turns in the recon set — C2E019 t354, t367, t638; C2E033 t1098; C2E035 t116 — all contain the trigger phrase inside NPC dialogue, often as the substantive action of the entire turn. Turn-level Stage 0 reject of NPC-voice turns would discard the most load-bearing reward shape in the corpus.

**Phrase-span Stage 0 design:**

- **EVENT** (continue to Stage 1):
  - Trigger phrase inside Matt's narrative voice → MATERIAL_LOOT, MECHANICAL_GRANT, KNOWLEDGE_GRANT, ENVIRONMENTAL_DISCOVERY candidates.
  - Trigger phrase inside NPC speech (quote-mark + voicing-tag proximity) → QUEST_OFFER, NPC_FAVOR_GRATITUDE candidates.
  - Stage 0 routes by *which voice* contains the trigger phrase, not whether the turn contains any voice.

- **STATE** (flag, pass forward):
  - In-combat narration (`is_combat_state`): mechanical grants like "advantage on this" are real combat-time rewards, but state matters for category assignment.
  - In-recap narration (`is_recap_state`): retrospective reward mentions during episode recap are not new reward events.

- **DISCOURSE** (reject):
  - **Rules-adjudication talk.** "It gives you additional hit points" (C2E016 t707), "What does haste does is it gives you" (C2E019 t220), "Until the end of your next turn" combat-mechanics references. Heuristic: trigger phrase paired with rules-vocabulary tokens (`feat`, `bonus action`, `attunement`, `Constitution`, `armor class`, `your AC`, `next turn`, dice notation `d4/d6/d8/d20`).
  - **OOC table chatter.** Sponsor reads, scheduling, "let's take a break."
  - **Player-to-Matt verbalization paraphrased by Matt.** "If you've interest in 'making coin'…" (C2E019 t350) — when Matt is paraphrasing the player's own ask back at them, not granting anything.

**Heterogeneous-turn handling.** Per Lesson 9, the recon shows reward-bearing turns are routinely heterogeneous: NPC speech mixed with Matt's narration mixed with rules-talk. Phrase-span detection requires:
- Quote-mark proximity (the trigger lies inside `"..."` or `'...'`).
- Voicing-tag adjacency (`he goes`, `she says`, `the figure speaks` within ~15 chars before the trigger phrase).
- Voicing-tag *type* matters: NPC dialogue tags route to QUEST_OFFER / NPC_FAVOR; absence of any tag routes to Matt narration (MATERIAL_LOOT / KNOWLEDGE_GRANT).

This is the single most consequential design choice in Phase 1. Getting it wrong burns a calibration cycle (Lesson 9, Lesson 10).

---

## §6. Reward-absence detection plan

Question 6 is structurally critical. Its detection shape is **expected payoff did not fire**, which is fundamentally cross-event, not single-event.

**Single-extractor feasible (Phase 1 in-scope candidate):**

- Explicit linguistic absence after a search or perception check: `Make a perception check` → low roll → `nothing of note`, `nothing here`, `you see nothing`, `comes up empty`. Recon shows ~1–3 per episode. Detectable as: a Stage 1 ABSENCE_NEGATION candidate within ~5 turns of a perception/investigation check trigger.
- Failed-roll narration: `you don't find`, `you can't tell`, `there's no sign`. Same shape, same frequency.

This catches the *narrated* reward absence — Matt explicitly closing a search beat without a payoff. It does **not** catch the broader Q6 shape: a tense scene that the players expect to terminate in a reward and which simply ends with no reward record. That requires cross-extractor signal.

**Cross-extractor required (out of scope for Phase 1 single-extractor):**

The full Q6 shape is "buildup expected payoff didn't fire." Detecting it requires joining records across extractors. Specifically:

- **encounter_cadence** records carry `trigger_category`, episode position, `is_fresh_encounter`, and combat-end markers. A combat that resolves without a subsequent loot record in the same episode is a candidate reward-absence.
- **time_mention** records carry `scene_transition` events. A `scene_transition` immediately following a tension-buildup that contains no preceding loot_reward record is another candidate.
- The join is: for each escalation/resolution beat in encounter_cadence, look forward N turns for any loot_reward record; if absent, flag the beat as reward-absent.

CORPUS_BUILDER.md filed cross-extractor analysis pipelines as **deferred** (see "Filed deferrals," cross-extractor pipelines = "its own ship with its own scope"). This means Q6's full form is not single-extractor work.

**Recommended scope for Phase 1:**

Two viable paths, locked at §11:

(a) **In-scope (limited).** Phase 1 ships with single-extractor absence detection (the ~1–3 per episode explicit-negation cases). Findings doc reports it as a partial answer to Q6 and explicitly flags that the broader form requires cross-extractor analysis. This is consistent with how Encounter Cadence handled its trap-activation single-record finding — ship the partial answer, document the limitation.

(b) **Defer Q6 to a cross-extractor analysis ship.** Phase 1 of Loot/Reward emits the records cleanly enough to be joinable. Q6 becomes a separate Track 5 ship that joins encounter_cadence + time_mention + loot_reward outputs and reports absence patterns. CORPUS_BUILDER.md reads this as opening up the deferred pipeline category.

§11 decision required.

**JSON fields needed for cross-extractor join (informational, even if Q6 deferred):**

For loot_reward records to join cleanly:
- `episode` (already required).
- `turn_number` (the trigger turn).
- `episode_position_pct` (already required).
- `reward_category` (per-extractor field, see §9).

For absence-detection joining specifically:
- encounter_cadence's `nearest_prior_trigger_turn_distance` (already emitted).
- time_mention's `scene_transition` records (already emitted).
- A new (loot_reward) per-episode field could carry `nearest_prior_loot_turn_distance` to symmetrize, but that's a Phase 2 schema decision.

---

## §7. Edge cases and known ambiguities

**Mid-combat loot.** Matt occasionally narrates a loot drop mid-combat — a defeated enemy's effects fall to the floor — without breaking initiative. Detection: same triggers as MATERIAL_LOOT but with `is_combat_state=True`. Treatment: emit as MATERIAL_LOOT with combat flag, do not reject. C2E016 phase-shifts and C2E033 wave-events both contain this shape based on encounter_cadence's prior parse.

**Off-screen / retrospective rewards.** "Over the next few hours, working with you, and over time…" (C2E004 t1368). "50 gold. You assemble this package…" (C2E016 t2295). Matt summarizes a reward exchange that happened during compressed downtime. These are real rewards but their `episode_position_pct` is misleading — the reward landed during in-fiction time that was narrated in a single sentence. Treatment: emit, but note that buildup-time measurement (Q4) will be undercounted for these.

**Player-initiated transactions (inverted direction).** "You put five gold in his hand" (C2E033 t522). "600 gold pieces, please" (C2E010 t322). Player paying NPC, not NPC rewarding party. These would FP into MATERIAL_LOOT or QUEST_OFFER if currency-amount is the only signal. Treatment: direction-detection — `you put`, `you pay`, `you give him/her`, `please [N] gold` are direction-out triggers and reject.

**Social rewards without explicit objects.** A nod, a look, a cleared path. C2E010 t235: "gives you a nod, and goes right back into the song." These are arguably reward-shape (small social acknowledgement) but very low signal. Treatment: don't try to catch ambient body-language acknowledgements; require explicit verbal gratitude (`grateful`, `thank`, `for your assistance`).

**Framing rewards that never materialize.** An NPC promises a reward that the campaign never delivers. C2E019 t367's "purse of 1,750 gold pieces upon completion" — the offer is a QUEST_OFFER record now, but whether it was ever delivered is a separate question requiring later-episode analysis. Treatment: emit the offer as `reward_direction=offered`, separately from any later delivery record. Q5 (persistence) and Q6 (absence) both depend on tracking offer-vs-delivery pairing across episodes — out of scope for Phase 1; flagged for Phase 1.5 if Jordan wants offer/delivery linkage.

**Knowledge-grant vs lore-narration boundary.** When does Matt narrating world history count as a "reward" (KNOWLEDGE_GRANT) vs scene-setting? Heuristic: if the narration is gated by a roll (Arcana, History, Religion check) or by a specific PC's perspective ("you remember", "comes back to you"), it's KNOWLEDGE_GRANT. Free-floating world exposition is not. Recon shows this boundary is fuzzy in C2E016 t1081-style cases.

**Anti-rewards / debts as durable consequence.** C2E004 t750 — 2,645 gold debt to Trostenwald. This is reward-shaped (large currency mention, persistence framing, NPC delivery) but the direction is owed, not given. Treatment: emit with `reward_direction=imposed` or similar, flag PERSISTENCE_FRAMED. Q5 directly cares about this.

**Mechanical-grant vs rules-adjudication discourse.** The most consequential ambiguity. "I'll give you advantage on this" (C2E016 t1862) is a real MECHANICAL_GRANT in narrative present. "What does haste does is it gives you—" (C2E019 t220) is rules talk. Both contain `gives you`. Heuristic: rules-talk is paired with rule-vocabulary (`feat`, `the spell`, `the ability`, dice notation, `your AC`); reward-grant is paired with PC name or `you` referring to a specific in-fiction action. This is the FP family most likely to require Phase 3 patches.

---

## §8. Source corpus

**Recommendation: CRD3 only for Phase 1.**

CORPUS_BUILDER.md row 3 lists Loot/Reward as `CRD3 + FIREBALL`. Recon argues against FIREBALL inclusion at Phase 1:

- Recon shows reward events are routinely **multi-turn**: buildup (perception check) → reveal (you find) → reaction. FIREBALL is single-turn DM-narration snapshots; it cannot carry the buildup.
- The most distinctive recon shape — QUEST_OFFER inside NPC dialogue spanning 3–8 utterances — is structurally a CRD3 phenomenon.
- Q4 (buildup cadence) and Q6 (reward absence) are inherently flow-shaped and require multi-turn context.

FIREBALL might inform a future single-turn-shape ship (e.g., "what does Matt's loot-reveal sentence structure look like in isolation?"), but that is not this extractor's question set. **This contradicts the CORPUS_BUILDER.md table; deviation is surfaced in §10 and resolved at §11.**

---

## §9. Output schema sketch

Required fields per CORPUS_BUILDER.md output contract: `campaign`, `episode`, `episode_position_pct`, `speaker`, `event_type`, `raw_text`, `preceding_context_chars`, `extractor_version`, `extracted_at`.

Per-extractor fields implied by the candidate taxonomy:

```json
{
  "...required fields...": "...",
  "reward_category": "MATERIAL_LOOT | QUEST_OFFER | NPC_FAVOR_GRATITUDE | MECHANICAL_GRANT | KNOWLEDGE_GRANT | ENVIRONMENTAL_DISCOVERY | ABSENCE_NEGATION | UNKNOWN_SHAPE",
  "reward_direction": "incoming | offered | delivered | imposed | outgoing",
  "currency_total_gp_equivalent": 0,
  "is_in_npc_voice": false,
  "is_combat_state": false,
  "is_recap_state": false,
  "has_persistence_marker": false,
  "has_perception_buildup": false,
  "buildup_chars": 0,
  "nearest_prior_perception_check_turn_distance": null,
  "trigger_phrase": "...",
  "absence_followup_after_buildup": false
}
```

Notes:

- `UNKNOWN_SHAPE` is mandatory per Lesson 2 (no default sinkhole). Stage-0-survivors that don't match Stage 1 patterns flag here.
- `currency_total_gp_equivalent` lets Q4 and Q5 compute reward-magnitude statistics. Conversion: 1 gp = 10 sp = 100 cp, 1 pp = 10 gp.
- `is_in_npc_voice` is the phrase-span Stage 0 routing signal (Lesson 9). Carried as data, not used to reject.
- `absence_followup_after_buildup` is the single-extractor Q6 partial signal (§6).

Schema does not lock at Phase 1; this is a sketch. Phase 2 implementation locks the final shape.

---

## §10. Risks and unknowns

**1. Source-corpus deviation from CORPUS_BUILDER.md.** §8 recommends CRD3-only against the table's `CRD3 + FIREBALL`. If §11 locks FIREBALL in, recon evidence suggests the FIREBALL pass will produce records but that they will not contribute to Q4 or Q6 (buildup, absence) and will primarily serve a narration-shape sub-question. Decide explicitly.

**2. Stage 0 voice-routing inversion.** §5 inverts Time-Mention's NPC-voice handling. The risk: Phase 2 implementation might inherit Time-Mention's `is_npc_dialogue_present` reject pattern by reflex. Phase 2 spec must be explicit that NPC voice → category routing, NOT reject. Lesson 9 cited and inverted.

**3. Mechanical-grant vs rules-talk DISCOURSE filter.** §7 flags this as the FP family most likely to need patches. The recon shows rules-talk fires `gives you` heavily (C2E016 t707, t711; C2E019 t220), and a coarse filter will produce Encounter-Cadence-style FP-family-in-waves (Lesson 4). Phase 1 spec should declare a starting heuristic but expect Phase 3 patches.

**4. Quest-offer / delivery pairing.** Q5 (persistence) implies tracking whether an `offered` record gets a matching `delivered` record later. Single-extractor-pass on a single episode does not support this; cross-episode joins are needed. Phase 1 emits the offer/delivery direction field but does not pair them. Phase 1.5 candidate.

**5. Reward-absence Q6 is structurally cross-extractor.** Single-pass coverage is partial (§6). The published claim must distinguish "narrated absence" (single-pass detectable) from "expected payoff absent" (cross-extractor). Risk: findings doc overstates Q6 coverage if §11 locks "in scope" without surfacing the partial nature.

**6. Currency-amount direction inversion.** §7 — player-paying-NPC vs NPC-paying-player. Phase 2 needs a `direction-out` reject family at Stage 0; otherwise FP rate on MATERIAL_LOOT will be inflated by transactional spending (shopping, bribes, payments).

**7. ENVIRONMENTAL_DISCOVERY boundary.** §4 marked TENTATIVE. If category retention falls below the 3-event threshold across the hand-sample, it folds into MATERIAL_LOOT or rejects at Stage 0. Decide at §11 or defer to hand-sample.

**8. Buildup detection over-fires.** `Make a perception check` is the loudest buildup signal but fires for many non-reward perception checks (combat awareness, suspicion, environmental scanning). Q4's buildup measurement will need to filter perception-check events that don't terminate in a reward — a reverse-direction Q6 problem.

**9. Held-out methodology must follow Lesson 7 exactly.** Two held-out sets from session 1: gate-set + validation-set. Mechanical enforcement (separate flags, separate runners) baked into the Phase 2 implementation, not an afterthought. Calibration / gate-set / validation-set episodes selected to be disjoint from each other and from prior extractors' sets where feasible.

**10. The FP-family taxonomy in §3-§7 is incomplete.** Lesson 4 — assume new families surface. Predicted families now: rules-talk-fires-`gives you` (high), player-paying-NPC currency (high), ambient-NPC-acknowledgement (medium), descriptive-loot-flavor (medium), recap-narration-mentions-prior-rewards (low but present in C2 episodes). Expect 1–2 new families per calibration cycle.

---

## §11. Decisions for Jordan to lock

Each decision is a binary or short-list pick. Resolve in chat before Phase 2 opens.

**1. Final taxonomy.** Lock six categories (MATERIAL_LOOT, QUEST_OFFER, NPC_FAVOR_GRATITUDE, MECHANICAL_GRANT, KNOWLEDGE_GRANT, ENVIRONMENTAL_DISCOVERY) as proposed in §4? Options:
   - (a) Lock all six.
   - (b) Drop ENVIRONMENTAL_DISCOVERY (TENTATIVE in recon); fold ambiguous instances into MATERIAL_LOOT or Stage 0 reject.
   - (c) Add a category emerging from your read (specify).

**2. Stage 0 approach.** §5 recommends phrase-span. Options:
   - (a) Phrase-span Stage 0 with NPC-voice → category routing (recommended).
   - (b) Turn-level Stage 0 — Lesson 9 violation, requires justification.
   - (c) Phrase-span Stage 0 with NPC-voice as a flag only (not a routing signal); all categories detected from Matt narration only, NPC-voiced rewards rejected. Loses QUEST_OFFER and most NPC_FAVOR_GRATITUDE; smaller scope.

**3. Reward-absence (Q6) scope.** §6 recommends path (a) or (b). Options:
   - (a) In-scope, single-extractor only. Ship with the ~1–3 per episode narrated-absence detection. Findings doc explicitly states the broader form is cross-extractor.
   - (b) Defer Q6 to a cross-extractor analysis ship. Phase 1 emits records cleanly enough to be joinable, but does not attempt absence detection.
   - (c) Phase 1.5 — ship Phase 1 single-extractor first, then add absence as Phase 1.5 if patterns emerge in the full parse.

**4. Source corpus.** §8 recommends CRD3 only. Options:
   - (a) CRD3 only (recommended; deviates from CORPUS_BUILDER.md table).
   - (b) CRD3 + FIREBALL per the table; FIREBALL contributes to a narration-shape sub-question only.
   - (c) CRD3 only for Phase 1, FIREBALL filed for a future single-turn-shape ship.

**5. Hand-sample episode count.** Default 10 per CORPUS_BUILDER.md hand-sample protocol. Options:
   - (a) 10 (default).
   - (b) Other count (specify) — recon does not argue for a deviation.

**6. NPC-voice handling in Stage 0.** Captures the Lesson 9 inversion explicitly. Options:
   - (a) Phrase-span: NPC voice routes trigger to QUEST_OFFER / NPC_FAVOR_GRATITUDE; Matt voice routes to MATERIAL_LOOT / KNOWLEDGE_GRANT / ENVIRONMENTAL_DISCOVERY / MECHANICAL_GRANT (recommended).
   - (b) Reject NPC-voiced trigger phrases entirely (Time-Mention pattern; loses QUEST_OFFER).
   - (c) Flag-only: emit `is_in_npc_voice=True` but route by Stage 1 category logic ignoring voice.

**7. Quest-offer / delivery pairing.** Tracks whether QUEST_OFFER records get matched DELIVERED records in later episodes. Options:
   - (a) Out of scope for Phase 1; Phase 2 emits direction field only.
   - (b) Phase 1.5 — add cross-episode pairing pass after Phase 1 ships.
   - (c) Defer indefinitely; Q5 persistence answered without offer-delivery pairing.
