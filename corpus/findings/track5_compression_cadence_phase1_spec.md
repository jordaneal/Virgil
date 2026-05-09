# Compression Cadence — Phase 1 Spec

**Ship:** Track 5, Ship 4 — Compression Cadence Extractor
**Phase:** 1 (recon + spec)
**Author:** Phase 1 recon, May 2026
**Locks pending:** §13 decisions, resolved in chat before Phase 2 opens

---

## §1. Mission

The extractor exists to answer six research questions, verbatim:

1. How often does Matt compress (cut forward / retire scene / end montage / exit NPC focus) per episode, and how does the rate compare to total scene-count?
2. What surface forms does compression take — explicit cuts ("we cut to..."), montage compressions, NPC dismissals ("[NPC] takes their leave"), location departures, investigative-beat closures, search-loop terminations, tavern-scene endings, downtime collapses?
3. What signals precede a compression — does Matt telegraph it (player turn just declared closure intent / NPC purpose just resolved / objective just achieved / repeated-verb fatigue / dead-air signal) or surprise-cut?
4. How does Matt handle the vacuum between compressions — does the next scene open from a player declaration, an NPC arriving, an environmental shift, or Matt-initiated narrative?
5. Does Matt compress differently in C1 vs. C2 (shorter scenes? longer compressions? different surface forms)? Campaign-arc evolution of compression style.
6. How often does Matt RESIST compressing — i.e., how often does a scene appear stale (repeated verbs, no new info in N exchanges, NPC purpose resolved) and Matt does NOT compress? This is the negative-signal question that mirrors Loot/Reward's Q6 (reward absence). Q6 detection shape is "expected compression that didn't fire" — likely needs cross-extractor signal (repeated-verb detection, no-new-info windows). Single-extractor coverage will be partial.

Question 6 is structurally critical for Scene Lifecycle v1. If Matt rarely resists compressing, Scene Lifecycle's compression triggers can be aggressive; if Matt often holds scenes open past where the rules would compress, Scene Lifecycle v1 needs softer triggers and DM-override pathways. Recon observed both patterns — see §8.

### Boundary discipline

**IS:** Compression-decision records — the moments Matt actively elects to end a scene's active continuity, retire an NPC from present focus, cut to a new time, or compress past dead time. The trigger surfaces, buildup signals, compression cadence between events, and category of compression shape.

**IS NOT:**
- Time-Mention's territory. Time-Mention captures durational language ("two hours pass", "the next morning"). Compression Cadence captures the *compression decision* — the moment Matt elects to end a scene's continuity. Overlap exists when a compression decision carries explicit temporal language; see §9 and §12.
- Encounter Cadence's territory. Initiative events are scene boundaries; Encounter Cadence already mines them. Compression Cadence excludes combat-entry transitions.
- A general scene-segmentation extractor. Compression-decision shape only — when Matt actively chooses to compress, not a full scene-graph parse.

---

## §2. Source data findings

**Source corpus:** CRD3 c=2 alignment, MATT-only filter. The extraction target is compression *decisions*, which are narrated exclusively (or near-exclusively) by Matt. Recon confirms this: all 14 identified true-positive compression events in the 7-episode recon set were in MATT turns. NPC dialogue occasionally precedes a compression (Matt voices an NPC's farewell line, then narrates the departure), but the compression-decision trigger phrase — the moment that closes the scene's continuity — is always in Matt's voice, not attributed to NPC dialogue.

**Source format note.** The c=2 data is multi-file per episode (e.g., `C1E053_2_0.json`, `C1E053_2_1.json`). Turn dedup is required across files; the loot_reward loader handles this and can be reused in Phase 2.

---

## §3. Recon set

Seven episodes sampled with `random.seed(3333)`, stratified across C1 and C2 campaign phases.

**Phase definitions:**
- C1 early: C1E001–C1E034 (positions 1–31 in the sorted 94-episode C1 set)
- C1 mid: C1E035–C1E075 (positions 32–62)
- C1 late: C1E076–C1E115 (positions 63–94)
- C2 early: C2E001–C2E015 (positions 1–15)
- C2 mid: C2E016–C2E030 (positions 16–30)
- C2 late: C2E031–C2E046 (positions 31–46)

**Sampling method.** Full union of all episodes referenced in all prior eval sets (Encounter Cadence v1/v2/v3, Time-Mention v1/v2/v2-calibration/v3-holdout/validation, Loot/Reward handsample-v1/v2/gate-v1/v2/validation-v1/v2) comprises 107 unique episodes. Available disjoint pool: 33 episodes (26 C1, 7 C2). One episode sampled per phase bucket; 7th drawn from the remaining disjoint pool after phase buckets filled. Deterministic given the disjoint pool.

**Recon episodes:**

| Episode | Campaign phase | Total turns | MATT turns | Compression events (true positives) |
|---|---|---:|---:|---:|
| C1E011 | C1 early | 4,284 | 1,259 | 1 |
| C1E053 | C1 mid | 2,381 | 569 | 4 |
| C1E095 | C1 late | 2,675 | 693 | 4 |
| C1E114 | C1 late (7th) | 3,689 | 1,134 | 0 |
| C2E011 | C2 early | 2,468 | 572 | 2 |
| C2E027 | C2 mid | 1,979 | 475 | 4 |
| C2E037 | C2 late | 1,529 | 387 | 2 |
| **Total** | | **19,005** | **5,089** | **17** |

**Disjointness:** All 7 recon episodes are confirmed disjoint from all 107 prior eval-set episodes. No deviation.

**Compression event count note.** The 17 per-episode counts are "true positive" estimates from manual review of wide-net candidates: clear scene-scale compression decisions only. In-scene physical motion ("you make your way across the room"), OOC scheduling talk ("pick this up next week"), and recap-state episode-opening framing are excluded from this count. Phase 2 calibration will produce the authoritative counts.

---

## §4. Observed compression shapes

Wide-net regex across six compression families (EXPLICIT_CUT, MORNING_CUT, MONTAGE, NPC_DISMISSAL, LOCATION_DEPART, INVESTIGATION_CLOSE) plus two auxiliary families (STALE_SIGNAL for Q6, RECAP_OPENING for Stage 0 reject). Total 60 wide-net candidates across 7 episodes. Manual review of those candidates identified 17 true-positive compression events plus a large FP surface, detailed in §7.

**Shape 1: Explicit scene cut.** Matt announces a cut directly. Low-volume but high-signal.

> *C2E027 t1042 (52.7%):* "Cut to black."

> *C1E053 t1911 (80.3%):* "As this time has passed, you guys do return to the mansion, yeah."

Voice: Matt. Always scene-scale. Zero TM overlap (no explicit temporal quantifier in the "Cut to black" form; overlap possible when the cut also states a duration). Recon count: 2.

**Shape 2: Overnight/diurnal transition.** Matt compresses overnight or across a diurnal boundary to the next morning scene. Most common overlap with Time-Mention's `scene_transition` category.

> *C2E011 t1849 (74.9%):* "You guys all eventually find yourselves to rest for the evening, awaking in the early morning. The chilled morning air comes through. The sky: still mostly gray, with patches of blue."

> *C2E037 t1398 (91.4%):* "As the rest of you come to consciousness in the morning, Fjord seems to be sleeping in a little bit before suddenly shooting up with a gasp."

> *C1E053 t2179 (91.5%):* "Grog sprung awake, gathered the folks in the pre-dawn hour of the following morning. You gather your stuff, exit the mansion, and start making your way towards the Margrave's house."

Voice: Matt. TM overlap confirmed on all three (TM category: `scene_transition`). The TM record fires on the temporal phrase; the Compression Cadence record fires on the compression *decision*. Recon count: 3.

**Shape 3: Temporal montage.** Matt narrates compressed in-fiction time — hours to months — with activity described in summary. Spans from short in-scene compression ("spend the next hour") to multi-month arcs ("as the months go by").

> *C1E095 t665 (24.9%):* "Awesome. All right. So as the months go by and you all have your individual adventures, as you converse and talk amongst yourselves, the date of Winter's Crest begins to creep up."

> *C1E095 t1150 (43.0%):* "You spend the next hour asking from person to person on these white sands."

> *C1E095 t1658 (62.0%):* "Okay. Over the course of the evening, the room gets cleaned as best as it can."

> *C2E027 t550 (27.8%):* "As you guys continue your trek northward for the next day, you slowly push forward and watch as the rolling hills of this northern valley begin to even out."

Voice: Matt. TM overlap partial — short-duration montages ("spend the next hour") fire TM's `in_scene_compression`; some longer montages appear in TM's UNKNOWN_SHAPE bucket or miss TM entirely (C1E095 t665 and t1658 had no TM overlap). Recon count: 4.

**Shape 4: NPC departure.** An NPC ends their active presence in the scene. Two sub-shapes: (a) NPC speaks a final line and exits; (b) Matt narrates the NPC's physical departure without dialogue.

> *C1E053 t2288 (96.1%):* "Tress puts her hand to the side. Ivon looks at her. 'We'll take our chances with the wild.' Turns around and exits the room."

> *C2E011 t1537 (62.3%):* "At this point, you see Ulog make his way up and take a different table at the far corner. Then slowly, over the next 15 or so minutes, the other three exit the building."

Voice: heterogeneous — NPC dialogue followed by Matt-narrated departure. The compression signal is in Matt's narration ("exits the room", "exit the building"), not the NPC's dialogue. Phrase-span Stage 0 needed to locate the trigger inside Matt's narration voice, not NPC speech. TM overlap: C2E011 t1537 has TM `in_scene_compression` (because of "next 15 or so minutes"), but the NPC departure trigger is orthogonal. Recon count: 2.

**Shape 5: Investigative closure.** Matt closes a search or investigation beat explicitly: nothing more to find here, the room has been searched.

> *C1E053 t981 (41.2%):* "Okay. You come to the conclusion that there is nothing else to find in this room."

> *C1E011 t1064 (24.8%):* "There is nothing to find purchase for, here. It's just a pit."

Voice: Matt. Zero TM overlap — no temporal quantifier, no time-mention language. This is pure Compression Cadence new signal. Recon count: 2.

**Shape 6: Location departure at scene scale.** Party departs a named or distinct scene-level location. Distinguished from in-scene physical motion by the destination scope (a new city, a new geographical region, or a named location the party is done with).

> *C2E027 t399 (20.2%):* "You gather the last of your things, retrieve the horses, and head out."

> *C1E095 t783 (29.3%):* "All right, so you make your way to Emon, then you charter a ship across the Ozmit Sea and make your way to the continent of Marquet."

Voice: Matt. Zero TM overlap for true positives. **This shape has the highest FP risk in the recon**: the LOCATION_DEPART trigger family fires on every "you make your way to X" turn, including room-level navigation within a dungeon or building. The true positives require the destination to be a scene-level location (a new city, a named region, the "outside" of a building the party is leaving for good). Recon count: 2 confirmed, many FPs.

**Voice routing summary.** Compression decisions are almost exclusively in Matt's narrative voice. NPC departure turns are the exception — they are heterogeneous (NPC dialogue + Matt narration). No case in recon had the compression trigger phrase inside pure NPC voice. Player-driven compressions ("let's skip ahead") were not observed in Matt's turn stream (Matt paraphrases or narrates them, but the trigger always remains in Matt's voice).

---

## §5. Candidate taxonomy

Six proposed categories from §4 observations. All appear ≥2 times in the recon; LOCATION_DEPARTURE carries the caveat that its true-positive count is estimated and its FP rate is the highest of the six.

**1. SCENE_CUT** — Matt announces an explicit cut or uses direct editorial framing to end a scene's continuity.
*Trigger shapes:* `cut to black`, `we cut to`, `cut away to`, `time has passed`, `some time later`, `skip ahead to`. *Voice:* Matt. *TM overlap:* low (fires on explicit-cut language that Time-Mention doesn't classify as a time-mention unless a duration follows). *Recon count:* 2. *Frequency: rare.*

**2. OVERNIGHT_REST** — Matt compresses overnight to the next morning, usually following a long rest.
*Trigger shapes:* `you awaken`, `awaking in the early morning`, `as the morning comes`, `you find yourselves to rest for the evening`, `the following morning`, `you come to consciousness`. *Voice:* Matt. *TM overlap:* high (all 3 recon instances also had TM `scene_transition` records). *Recon count:* 3. *Frequency: moderate — fires roughly once per episode that includes a long rest.*

**3. TEMPORAL_MONTAGE** — Matt narrates compressed in-fiction time (ranging from one hour to several months) with a summary of activity during that period.
*Trigger shapes:* `over the next [N] hours/days/weeks/months`, `as the months go by`, `over the course of the evening/day/week`, `spend the next [N] [unit]`, `throughout the [day/night/week]`, `as you continue your trek [duration]`. *Voice:* Matt. *TM overlap:* partial (short-duration montages overlap TM's `in_scene_compression`; longer montages often appear in TM's UNKNOWN_SHAPE or miss TM entirely). *Recon count:* 4. *Frequency: moderate.*

**4. NPC_DEPARTURE** — An NPC ends their active presence in the scene. May follow NPC dialogue (heterogeneous turn) or be pure Matt narration.
*Trigger shapes:* `exits the room`, `exit the building`, `turns around and exits`, `takes their leave`, `bids you farewell`, `departs`, `head back to their [work/seat/table]`, plus Matt-narrated group departures. *Voice:* Matt narration following possible NPC dialogue. *TM overlap:* low (except when the departure turn also contains an explicit time phrase). *Recon count:* 2. *Frequency: moderate in social-interaction episodes.*

**5. INVESTIGATIVE_CLOSURE** — Matt closes a search, exploration, or investigation beat by declaring nothing more remains.
*Trigger shapes:* `nothing else to find in this room`, `nothing to find purchase for`, `you come to the conclusion that there is nothing else`, `nothing more of note`, `you've searched the area`, `there is nothing here`. *Voice:* Matt. *TM overlap:* zero in recon. This is clean new signal — no time-mention language involved. *Recon count:* 2. *Frequency: low — fires when a search beat ends.*

**6. LOCATION_DEPARTURE** *(TENTATIVE — high FP risk)* — Party departs a scene-level named location.
*Trigger shapes:* `gather the last of your things [...] and head out`, `make your way to [city/continent/region]`, `you leave [location name] behind`, `you set out for`. *Voice:* Matt. *TM overlap:* zero for true positives. *Recon count:* 2 confirmed. *High FP risk* — the LOCATION_DEPART trigger family fires on every "you make your way to X" regardless of scale. True positives require destination-scope detection (scene-level vs. within-scene). Mark TENTATIVE; final decision in §13. *Frequency: low per session (1–2 major location exits per episode).*

**Not proposed:** A WATCH_PASS category (overnight watch with nothing happening — "nothing of note happens during your watch") appeared once in recon (C2E027 t523). One instance is insufficient; this shape may be OVERNIGHT_REST adjacent and will be resolved during Phase 2 hand-sampling.

---

## §6. Stage 0 detection plan

**Recommendation: phrase-span Stage 0.**

The recon shows compression-decision turns are frequently heterogeneous. Two cases in the recon set demonstrate this clearly:

1. *NPC_DEPARTURE turns* — C1E053 t2288 opens with Matt voicing NPC dialogue ("We'll take our chances with the wild.") before transitioning to Matt-narration ("Turns around and exits the room"). Turn-level Stage 0 would need to examine the turn as a whole; the compression trigger is in Matt's narration, not in NPC speech. A turn-level DISCOURSE reject that fires on "any NPC dialogue present" would incorrectly suppress this record.

2. *Table-talk prefix on compression turns* — C1E095 t665 opens with "Awesome. All right." (OOC affirmation) before "So as the months go by..." (compression narration). A turn-level OOC reject would suppress this record. The compression phrase is in Matt's in-fiction narrative voice; only the prefix is OOC.

The homogeneous-turn claim is not supportable across the full domain. Phrase-span Stage 0 is required.

**Stage 0 architecture:**

- **EVENT** — trigger phrase is inside Matt's in-fiction narrative voice. Proceed to Stage 1.
- **STATE** — turn carries a flag that affects classification but isn't itself a compression event.
  - `is_combat_state`: if compression fires during what appears to be active combat, flag rather than reject. (Rare — compression generally doesn't fire mid-combat, but montage compressions in downtime adjacent to combat beats exist.)
  - `is_recap_state`: episode-opening recap framing (C2E037 t39 opens with "Last we left off..." before narrating "the following day"). The "following day" phrase appears inside the episode-opening recap, not as a new compression decision. This is a known edge case; see §9.
- **DISCOURSE** — trigger phrase is inside one of the known reject contexts:
  - **D1 OOC scheduling.** "Next week", "pick this up next week", "join us next [time/week]", "we'll air the panel next week." These fire on MORNING_CUT and MONTAGE triggers constantly at episode end and in opening sponsor segments. Highest-volume false-positive family. Detectable by: position >95% of episode OR production-scheduling vocabulary (`loot crate`, `subscribe`, `twitch`, `patreon`, `comic con`, panel scheduling).
  - **D2 NPC-voice trigger phrase.** If the compression trigger phrase is inside quoted NPC speech (rather than in Matt's surrounding narration), reject or route to NPC_DEPARTURE. Phrase-span proximity check: quote-mark enclosure or voicing-tag adjacency within 15 chars before the trigger.
  - **D3 In-scene micro-motion.** "You make your way across the room to a spot", "you make your way up to the secondary floor", "you head down to the cargo hold" — physical navigation within the current scene, not a scene-level departure. Heuristic: destination is a sub-location of the current scene (a different room, floor, or spot within the building/dungeon), not a new named exterior location. This is the hardest Stage 0 filter to implement; see §12.
  - **D4 Recap-state opening.** The episode-opening recap ("Last we left off, [...] the following day") uses compression vocabulary to describe past events, not to compress a current scene. Detectable by episode-position ≤3% + RECAP_VOCAB proximity.

---

## §7. FP-family taxonomy upfront

Per Lesson 4, predicting 5 FP families from recon observation. Assume new families surface in Phase 3.

**FP1: OOC scheduling talk** (high volume). Highest-volume FP family in recon. "Next week", "next month", end-of-episode sponsor segments. Fires on MORNING_CUT, MONTAGE triggers at high episode-position. Clearable by D1 filter (position + scheduling vocabulary). Expected to be most common FP family.

**FP2: In-scene physical motion** (high volume). "You make your way across", "you head down", "you make your way to [the next room]" — navigational turns inside active scenes. Fires on LOCATION_DEPART and MORNING_CUT triggers. High volume in dungeon-crawl and ship-boarding episodes (C2E027, C2E037). Distinguishable in principle by destination scope but hard to execute with simple regex. Expect this to drive most LOCATION_DEPART FPs.

**FP3: NPC dialogue using compression vocabulary** (medium volume). An NPC says something like "I'll take my leave" or "we'll talk more tomorrow" in-character, and the scene continues — Matt has NOT compressed. The trigger phrase is inside NPC speech, not Matt's narration. Phrase-span D2 handles this if the NPC voicing tag is detectable, but Matt's NPC-voicing style in CRD3 uses varied tags (sometimes the tag precedes the phrase, sometimes follows). Expect calibration-phase patches here.

**FP4: Recap-state compression language** (medium volume). Episode-opening recap: "Last we left off, the Mighty Nein [found X], as the following day arrived..." This uses MORNING_CUT/TEMPORAL_MONTAGE vocabulary but is describing past events. D4 clears the opening ~3%; the edge case is a mid-episode character flashback using past-tense compression language. Seen in C2E037 t39. Expect 1–2 calibration patches.

**FP5: Player-question echo compression** (low volume). Matt paraphrases a player's intent and immediately narrates the outcome: "Sure. You come back to find...". The "you come to" fires on MORNING_CUT; the actual event is just a player-action resolution, not a scene compression. Context-distinguishable (immediate player-turn precedes it), but requires preceding-turn inspection. Not confirmed in recon but predicted from the trigger-phrase surface.

---

## §8. Q6 detection plan

Q6 ("how often does Matt resist compressing?") is structurally the most difficult question. Two distinct findings from recon:

**Finding 1 — Matt DOES hold stale scenes.** C1E114 produced 5 STALE_SIGNAL hits ("what do you want to do?", "is there anything else?", "anything else here?") and **zero compression events**. This is the C1 late-arc finale area — a climactic episode where Matt sustained engagement through repeated player-inquiry prompts without cutting. The episode also has the highest total turn count in the recon set (4,284 turns). C2E037 produced 7 stale signals with only 1 compression event. Matt's pattern of holding scenes open is real and not rare.

**Implication for Scene Lifecycle v1:** Matt does not always compress when a scene appears stale. He appears to hold scenes open deliberately during climactic, emotionally active beats. Scene Lifecycle v1 cannot implement aggressive auto-compression; it needs explicit DM-override pathways, and its compression triggers should be soft (DM-assistive) rather than automatic.

**Finding 2 — Single-extractor Q6 coverage is partial.** The STALE_SIGNAL regex detects Matt's "what do you want to do?" prompts, which cluster in scenes where the scene purpose has been fulfilled. A true stale-but-not-compressed observation requires:
- STALE_SIGNAL appears (detectable single-extractor)
- The scene has been active for many turns at the same location/NPC (requires state memory or cross-extractor anchor)
- Matt does NOT follow with a compression event within N turns (detectable single-extractor if both STALE_SIGNAL and compression families run on the same episode)

What is single-extractor feasible: count of STALE_SIGNAL clusters (3+ occurrences within a 30-turn window) that are NOT followed by a compression event within 20 turns. This catches the coarse pattern. It will miss:
- Scenes where Matt holds open without the "what do you do?" prompt form (silent continuation)
- Scenes where the stale pattern is caused by player indecision rather than scene completion

What requires cross-extractor signal for full coverage:
- NPC purpose resolved (Loot/Reward's QUEST_OFFER/NPC_FAVOR records mark NPC-purpose completion)
- Scene transition without prior compression (Time-Mention's `scene_transition` records mark when Matt eventually did cut)
- Encounter ended without loot record following (Encounter Cadence + Loot/Reward join)

**Q6 scope options** are in §13.

---

## §9. Edge cases and known ambiguities

**Overnight long-rest (Time-Mention overlap).** OVERNIGHT_REST records will almost always co-occur with TM `scene_transition` records. Both fire on the same trigger phrase ("the following morning", "awaking in the early morning"). The distinction: TM records the time-bearing phrase; Compression Cadence records the compression *decision*. If §13 locks `time_mention_overlap` flag-and-emit (not suppress), these are separate records for different analytical purposes. If the overlap is deemed redundant, OVERNIGHT_REST can be dropped and Scene Lifecycle v1 can join against TM's `scene_transition` records instead. See §13.

**Travel compressions (Time-Mention overlap).** TEMPORAL_MONTAGE with a travel verb ("as you continue your trek northward for the next day") overlaps both TM's `travel_duration` and Compression Cadence's taxonomy. These are triply-contested records: TM fires `travel_duration`, Encounter Cadence may have a preceding episode position near a wave event, and Compression Cadence fires TEMPORAL_MONTAGE. Emit with `time_mention_overlap=True` flag; let downstream analysis distinguish.

**Combat-end → exploration transitions (Encounter Cadence overlap).** When combat ends and Matt says "With the battle concluded, you find yourselves standing among the ruins..." and transitions to an exploration beat, this is a scene compression but also follows Encounter Cadence's `wave_or_phase_shift` territory. The combat-end narration may include compression language ("over the next few minutes, you tend to your wounds"). Emit with `is_combat_state=True` flag; do not double-count with Encounter Cadence.

**In-scene minor time jumps vs. full scene cuts.** "You spend the next ten minutes searching" is a TEMPORAL_MONTAGE (in-scene compression), but the scene is still active — the party is in the same location, same beat. "Cut to black / morning eventually comes" closes the scene entirely. The distinction matters for Q1 (compression rate vs. scene-count). Proposal: `compression_scope` field — `in_scene` vs. `scene_exit`. This can be derived from whether a new named location or time-of-day opens following the compression, but that requires forward-looking context beyond the trigger turn.

**Recap-state compression language.** C2E037 t39 is flagged as RECAP_OPENING (position 2.6%) but uses "the following day" language that would otherwise trigger OVERNIGHT_REST. This is a compression-vocabulary reference to a *past* compression already narrated in the prior session, not a new compression decision. D4 (recap-state at position ≤3%) catches this case. The residual risk: a flashback or character-backstory narration mid-episode that uses compression vocabulary in past tense. Expect 1 calibration patch.

**"You come to" polysemy.** "You come to [a place]" (motion) vs. "you come to [consciousness]" (awakening from rest/unconsciousness). Both trigger MORNING_CUT. Motion sense is FP2; awakening sense is OVERNIGHT_REST. Distinguishable by following noun: awakening precedes `consciousness`, `the morning`, `and gather yourselves`; motion precedes `a place-name` or directional phrase.

**Episodic "cut to break" framing.** C2E027 t860: "...you make your way into the brothel. And that's where we're going to take a break." This is OOC framing for an episode break, not a scene compression. The actual scene compression may follow after the break. DISCOURSE reject: "take a break" + position-based OOC filter.

---

## §10. Source corpus

**CRD3 only.** Matches the source-corpus choice of all three prior ships (Encounter Cadence, Time-Mention, Loot/Reward). Loot/Reward §8 already documented the CRD3-only deviation from CORPUS_BUILDER.md's table entry (which lists `CRD3 + FIREBALL`) and the reasoning: compression decisions are multi-turn flow-shaped events — they require seeing the turns that precede the compression to detect the buildup signals (Q3) and the turns that follow to assess the vacuum between compressions (Q4). FIREBALL is single-turn DM-narration snapshots; it cannot carry any of those multi-turn shapes. The same argument applies here, more strongly: a compression decision spans the scene that ends, the closing turn, and the scene-opening turn that follows. FIREBALL cannot represent that structure.

---

## §11. Output schema sketch

Required fields per CORPUS_BUILDER.md output contract: `campaign`, `episode`, `episode_position_pct`, `speaker`, `event_type`, `raw_text`, `preceding_context_chars`, `extractor_version`, `extracted_at`.

Per-extractor fields implied by the candidate taxonomy and research questions:

```json
{
  "...required fields...": "...",
  "trigger_turn_number": 0,
  "compression_category": "SCENE_CUT | OVERNIGHT_REST | TEMPORAL_MONTAGE | NPC_DEPARTURE | INVESTIGATIVE_CLOSURE | LOCATION_DEPARTURE | UNKNOWN_SHAPE",
  "surface_form": "explicit_cut | diurnal_transition | montage | npc_exit | investigation_closed | location_exit",
  "compression_scope": "in_scene | scene_exit",
  "buildup_signal": "player_intent | npc_resolution | objective_completion | repeated_stale_signal | matt_initiated | none",
  "buildup_window_turns": 0,
  "is_recap_state": false,
  "is_combat_state": false,
  "time_mention_overlap": false,
  "stale_signal_count_preceding": 0,
  "trigger_phrase": "...",
  "preceding_turns": []
}
```

Notes:
- `UNKNOWN_SHAPE` is mandatory per Lesson 2 (no default sinkhole). Stage-0-survivors that don't match Stage 1 patterns emit here.
- `compression_scope` is aspirational — `scene_exit` vs. `in_scene` requires forward-looking context that may not be single-extractor feasible at Phase 2. Sketch it; decide at §13.
- `buildup_signal` is the causal-classification field. Per Lesson 1, detection and causal classification are independent. The `buildup_signal` field will carry lower reliability than the `compression_category` detection; findings doc will report them separately.
- `time_mention_overlap`: True when the trigger turn also has a Time-Mention record (inner join on episode + trigger_turn_number). Can be derived post-extract rather than at extract time.
- `stale_signal_count_preceding`: count of STALE_SIGNAL hits in the preceding 30-turn window. Q6's single-extractor partial signal.

Schema does not lock at Phase 1; this is a sketch. Phase 2 implementation locks the final shape.

---

## §12. Risks and unknowns

**1. Compression-vocabulary in non-compression context is the dominant FP risk.** The distinction that matters — Matt *deciding* to compress vs. Matt *using compression-shaped language* in passing — is harder to draw than it looks. "You make your way to X" appears in both in-scene micro-navigation and genuine scene-scale departures. "The following morning" appears in both genuine overnight compressions and recap-state episode-opening framing. Every trigger family has a non-compression usage; Stage 0 filters some of these, but calibration patches will be needed.

**2. Time-Mention overlap is moderate, not disqualifying.** Recon measured ~25–30% TM overlap rate on true-positive compression events (5–6 of ~17). The overlap is concentrated in OVERNIGHT_REST and some TEMPORAL_MONTAGE records. SCENE_CUT, NPC_DEPARTURE, and INVESTIGATIVE_CLOSURE have effectively zero TM overlap in recon. The extractor adds meaningful new signal even accounting for overlap. However, if Phase 2 calibration on a larger sample finds TM overlap >60% of true positives, the extractor's marginal value drops substantially, and the §13 decision on overlap handling becomes critical.

**3. LOCATION_DEPARTURE may not be feasible as a single-extractor category.** The recon's LOCATION_DEPART trigger family was the most promiscuous: 16 of 22 hits in C2E027 were in-scene micro-navigation false positives. The 2 true positives required destination-scope judgment that simple regex cannot make. If §13 drops LOCATION_DEPARTURE from the taxonomy, the extractor focuses on the 4 higher-signal categories; if retained, Phase 2 must design a destination-scope Stage 1 filter (likely named-location vocabulary + preceding-context travel setup).

**4. Q6 negative-signal is partially feasible, not fully feasible.** Single-extractor Q6 (STALE_SIGNAL clusters without compression follow-through) is implementable and produces meaningful signal: C1E114 with 5 stale signals and 0 compressions is a strong example. But the broader "Matt held a stale scene open" pattern requires cross-extractor context (Loot/Reward NPC-purpose completion, Time-Mention scene-transition as the eventual cut) to reconstruct the full shape.

**5. `buildup_signal` classification will face Lesson 1's wall.** The cause-classification question ("what preceded this compression?") is harder than event detection. Buildup signals span 5–15 turns (Lesson 6 window). Player declarations of departure intent, NPC purpose resolutions, and silent Matt-initiated cuts all precede compressions — but determining which one is causal requires reading the preceding context, not just matching a regex. Report `buildup_signal` as suggestive-only, per Lesson 8.

**6. C1E114 recon produces 0 compression events.** This is an outlier — the episode has the highest turn count in the recon set (4,284) and 5 stale signals. If C1E114 is indeed the C1 finale, its 0-compression profile is a genuine finding rather than a detection failure. But it is worth verifying in Phase 2: if a 4,284-turn episode truly has no compression decisions, that is a major data point for Scene Lifecycle v1 (Matt sustains scenes indefinitely during climactic moments).

**7. NPC_DEPARTURE sub-shape ambiguity.** The recon shows two NPC_DEPARTURE shapes: (a) NPC speaks a farewell line + departs (C1E053 t2288); (b) Matt narrates group departure without NPC dialogue (C2E011 t1537). Shape (a) has a voicing-tag + departure pattern; shape (b) has only the departure pattern in Matt's narration. Phase 2 must treat these as one category but verify phrase-span Stage 0 handles both without losing shape (a) to a "NPC dialogue detected, reject" rule.

---

## §13. Decisions for Jordan to lock

Each decision is a binary or short-list pick. Resolve in chat before Phase 2 opens.

**1. Final taxonomy.** Lock the six-category proposal (SCENE_CUT, OVERNIGHT_REST, TEMPORAL_MONTAGE, NPC_DEPARTURE, INVESTIGATIVE_CLOSURE, LOCATION_DEPARTURE) or modify? Options:
- (a) Lock all six. Include LOCATION_DEPARTURE as TENTATIVE; Phase 2 hand-sampling determines whether it survives (as with Loot/Reward's ENVIRONMENTAL_DISCOVERY).
- (b) Drop LOCATION_DEPARTURE. Five categories only; location-exit compression is too FP-prone without destination-scope detection. Filed for a future higher-scope version of this extractor.
- (c) Merge OVERNIGHT_REST into TEMPORAL_MONTAGE as a sub-shape. Five categories, with `surface_form` field distinguishing diurnal vs. multi-hour vs. multi-day montage.
- (d) Add a category not in the spec (specify).

**2. Stage 0 approach.** Recon supports phrase-span; see §6. Options:
- (a) Phrase-span Stage 0, per §6 recommendation.
- (b) Turn-level Stage 0 — Lesson 9 violation; requires explicit justification for why this domain is homogeneous enough to permit it.

**3. Q6 scope.** Single-extractor partial coverage confirmed feasible. Options:
- (a) In-scope, single-extractor only. Ship with STALE_SIGNAL cluster detection (≥3 occurrences in a 30-turn window without compression follow-through within 20 turns). Findings doc explicitly reports the broader form as cross-extractor.
- (b) Defer Q6 entirely. Phase 1 emits records cleanly enough to be joinable; Q6 cross-extractor analysis is a future ship.
- (c) Phase 1.5 — ship Phase 1 single-extractor first; if stale-hold pattern is strong enough in full parse, add a Q6 sub-analysis pass at Phase 1.5.

**4. Time-Mention overlap handling.** The extractor will emit records that also appear as TM records (specifically OVERNIGHT_REST and some TEMPORAL_MONTAGE). Options:
- (a) Emit with `time_mention_overlap=True` flag. Both records exist; downstream analysis can deduplicate or join as needed. The compression-decision layer adds information TM doesn't carry (compression category, buildup signal, stale-signal count).
- (b) Suppress overlapping records. If a compression candidate fires on a turn that has a TM `scene_transition` record, emit only if the compression adds a non-TM category (e.g., NPC_DEPARTURE aspect in the same turn). Reduces overlap but risks losing compression-decision metadata.
- (c) Drop OVERNIGHT_REST from the taxonomy entirely. Let TM's `scene_transition` serve as the overnight-compression proxy; Compression Cadence focuses on the non-TM signal surface (SCENE_CUT, NPC_DEPARTURE, INVESTIGATIVE_CLOSURE, TEMPORAL_MONTAGE for non-diurnal forms).

**5. Hand-sample episode count.** Default 10 per CORPUS_BUILDER.md protocol. Options:
- (a) 10 (default).
- (b) Other count — recon does not argue for deviation.

**6. Player-driven compressions.** Recon did not observe player-initiated compressions ("let's skip ahead") in Matt's turn stream — when players say this, Matt narrates the outcome in his own voice. Options:
- (a) Matt-voice only (recommended). If players drive a compression, the compression record fires on Matt's follow-up narration, not the player declaration. Player-intent is captured in `buildup_signal=player_intent` on the Matt-turn record.
- (b) Mine player-turn compressions separately. Would require PLAYER-speaker filter and a separate Stage 0. Not recommended given the scope of Phase 1.

**7. `compression_scope` field.** `in_scene` (party stays in scene, just time compresses) vs. `scene_exit` (scene continuity ends, next turn opens a new scene). Options:
- (a) Include as a sketch field; Phase 2 determines feasibility. Note: `scene_exit` detection requires forward-looking context (does the following turn open at a new location?), which may not be single-extractor feasible.
- (b) Drop from schema. Report compression events flat; `compression_scope` is derivable by hand-reading the output but not auto-classified in v1.
