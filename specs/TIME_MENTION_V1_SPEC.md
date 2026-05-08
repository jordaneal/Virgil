# Time-Mention Extractor v1 — Spec Proposal

**Status:** DRAFT — Track 5 Ship 2, Phase 1 reconnaissance + taxonomy proposal. No code shipped from this session. Phase 2 (separate session) implements + hand-samples after Jordan locks §10 decisions in chat.

**Companion architecture docs:** `CORPUS_BUILDER.md`, `corpus_builder/corpus_builder_lessons_v1.md`. Lessons v1 was read before this spec; the Stage 0 layer, FP-family taxonomy, dual held-out sets, and no-default-catchall rule below are direct applications of those lessons.

**Eval-set overfit risk acknowledged:** any ship-gate precision number measured in Phase 4 is an upper bound, not the published claim. The validation-set (§8) is the authoritative post-ship number, run exactly once.

---

## 1. Source data findings

CRD3 c=2 lives at `/mnt/virgil_storage/dnd_datasets/crd3/data/aligned data/c=2/`. Same source as Encounter Cadence (Ship 1) — no re-download. Format is unchanged:

- **140 unique episodes** across 280 files (each episode has `_2_0.json` and `_2_1.json` chunks). 94 C1, 46 C2. No C3, no Exandria Unlimited, no one-shots.
- **Per-file structure:** list of records, each `{CHUNK, ALIGNMENT, TURNS}`. Turns carry `NAMES` (list, usually one speaker), `UTTERANCES` (list of speech-recognition lines, joinable with `' '`), and `NUMBER` (sequential per episode). Spot-checked C1E007 — format identical to Ship 1's findings.
- **MATT-only filter still applies.** Time-mention extraction needs Matt's narration; player turns either reference time meta-discursively ("how long has it been?") or quote NPC dialogue (banter, not Matt-narrated time progression). Same import doctrine as `dnd_knowledge_import.py`.
- **Per-episode MATT turn counts (sampled):** C1E007 867, C1E040 542, C1E064 541, C1E108 821, C2E010 716, C2E025 788, C2E040 616. Consistent with Ship 1's ~30% MATT share of total turns.

No format surprise. Recon work concentrated in §2.

---

## 2. Sample observations (7 episodes)

Sampled to avoid Ship 1's reviewed set (C1E001/020/030/049/060/095, C2E001/020/030/045). Spread:

- **C1E007** — early C1, dungeon delve (Emberhold)
- **C1E040** — early-mid C1, Thordak attack on Emon
- **C1E064** — mid C1, Whitestone aftermath + travel
- **C1E108** — late C1, Vestige forging
- **C2E010** — early-mid C2, Zadash sewers
- **C2E025** — mid C2, Hupperdook escape + travel transition
- **C2E040** — late C2, sea-pursuit + jungle chase

**Method.** Built per-episode deduplicated turn lists (chunks repeat turns; dedup by `NUMBER`). Filtered to MATT speakers. Ran a broad union regex over candidate time phrases (numerics + units, relative-references, time-of-day, travel verbs, rest references, "over the next," etc.). Hand-classified all hits.

**Raw hit counts (all MATT, broad regex, before any Stage 0 filter):**

| Episode | Raw hits | Real fiction-time progressions (rough hand count) |
|---|---:|---:|
| C1E007 | 27 | 5-7 |
| C1E040 | 21 | 4-6 |
| C1E064 | 37 | 12-15 |
| C1E108 | 29 | 9-12 |
| C2E010 | 19 | 7-9 |
| C2E025 | 32 | 10-13 |
| C2E040 | 23 | 8-10 |
| **Total** | **188** | **~55-72** |

A naive grep over-counts roughly **3x** (188 raw vs. ~60 real). The same magnitude over-count Encounter Cadence saw with `\binitiative\b` (35 raw vs. 12 real). Stage 0 doing real work.

### Sampled observations (one quote per row, condensed)

**T1. C1E064 t1454 — overnight transition.** Players bedded down for the night; cut to: `"As you guys come to consciousness the next morning, the storm has come in now--"`. Clean scene break. Anchor: the prior long-rest declaration. Granularity: hours.

**T2. C1E064 t2187 — explicit time-of-day anchor.** Player asks about position; Matt answers with current time-state: `"You left in the morning. You would've gotten here-- actually, opposite of that. It's actually now getting to dusk."` Self-corrected anchor. Granularity: hours, current-state.

**T3. C1E064 t695 — campaign-clock advance.** Mid-scene: `"They are gone. The time has passed. They're miles and miles and miles..."`. Compresses unspecified time during an off-screen escape. Granularity: unspecified (probably hours).

**T4. C1E064 t166 — cumulative anchor.** `"It's been close to a week in the Feywild total, all the nights you've rested."` Recap of accumulated time across multiple sessions. Granularity: days/week.

**T5. C1E108 t820 — task duration.** `"with all of the smelting, put together I'd say it's probably been close to an hour."` Matt narrating elapsed time during a player task. Granularity: hour. In-scene, scene continues.

**T6. C1E108 t2166 — montage compression.** `"hammer and fold with more of it until eventually, you've managed to hammer in over the next 20 or so minutes..."`. Player activity compressed forward. Granularity: minutes. In-scene.

**T7. C1E108 t2342 — task completion.** `"After about five minutes or so, you finish and grab one of the trammels..."`. Bookends a task. Granularity: minutes.

**T8. C2E010 t140 — travel duration.** `"-- which you guys were traveling on foot-- it took you about the better part of two weeks. You passed through Nicodranas..."`. Travel-arc compression. Granularity: weeks.

**T9. C2E010 t270 — current-time anchor.** `"It's late afternoon. You're probably about an hour and a half, two hours from sundown."` Current-state anchor in response to a player question. Granularity: hours, current-state.

**T10. C2E010 t2074 — time-of-day shift.** `"the sun has set, and the night has gone purple to dark, navy blue as night has taken it."` Diurnal narration marking new sub-scene. Granularity: implied hours, transition.

**T11. C2E025 t2015 — transitional sunset.** `"...you guys all make your way back up the switchback path... just as the sun begins to hit the mountains, the skies turning to the oranges and reds of the coming sunset."` Travel + time-of-day transition combined. Granularity: hours.

**T12. C2E025 t2083 — long-rest overnight.** `"Long rest to you all. The next morning you come to consciousness, your first morning not hungover for a lot of you..."`. Same shape as T1. Granularity: overnight.

**T13. C2E025 t2243 — current-time-of-day anchor.** `"It's now pushing past maybe one or two in the morning. The fire is burned low to embers at this point..."`. Mid-scene anchor declaring current campaign-time. Granularity: hours, current-state.

**T14. C2E025 t1996 — short scene-transition.** `"about 20 or so minutes later you hear the footsteps return..."`. Compresses to next event. Granularity: minutes. Anchored to the immediately-prior scene event.

**T15. C2E025 t1900 — task duration.** `"You do a scan of Detect Magic through the room over the next 15 minutes or so."`. Same shape as T6.

**T16. C2E040 t1132 — travel duration.** `"You guys have been running for the better part of two hours now..."`. Same shape as T8 but mid-chase.

**T17. C2E040 t1273 — travel duration mid-action.** `"following the path, we'll say you've gone three or four hours of straight sprint through the forest."`. Travel compression embedded in chase scene.

**T18. C2E040 t1680 — multi-day travel forward.** `"Over the next couple of days you will because this is a multi-day travel to get to Darktow..."`. Travel arc with mechanical implications (exhaustion).

**T19. C1E007 t47 — atmospheric in-scene pause.** `"...stone ceiling above you that eventually comes to a stop. And you wait for about a minute, and the entire place is now in a very eerie silence."`. Brief in-scene compression following a setpiece.

**T20. C1E040 t172 — combat dramatic beat.** `"...missing the top of the keep... For a few seconds of silence, and you hear impact, shaking the ground for a few seconds."`. Sub-second narrative beat in/around combat.

### Filter-discipline observations

- **The word `second` is brutally overloaded.** `"hold on a second"` (table-talk), `"a second time"` (idiom for "again"), `"a second attack"` (D&D mechanic), `"a second floor"` (architecture), `"reels back for a second"` (combat micro-beat), `"see you in a second"` (episode break). Roughly 70% of `\bsecond\b` hits in MATT turns are noise. This is the single largest FP source.
- **Spell/rules durations are a wave.** `"Haste lasts for a minute,"` `"Bigby's Hand... only lasts for a minute,"` `"Modify Memory... ten minutes,"` `"the spell has faded."` Matt explaining game mechanics, not narrating fiction time.
- **NPC dialogue accounts for ~20-30% of the broad-regex hits in C1E064 and C1E040.** Matt voicing NPCs who reference time ("It's been over a year," "Eight days," "Two weeks"). Fiction signal but a different research question — these are deadlines and backstory reveals, not Matt-narrated campaign-clock advances.
- **Episode-break OOC is dense.** Every episode has `"back here in a few minutes"` / `"see you guys in a second"`. C2E040 even has cold-open table-banter referencing real-world "one week's time."
- **Combat round-counts are ambiguous.** `"Six seconds for all of you,"` `"We have six rounds of this challenge,"` `"33 points of damage in one round."` Some are real fiction-time mid-combat (the round IS time), some are pure mechanic-talk. Treated as STATE in §5.
- **Cumulative anchors and transitions cluster around episode mid-points and ends.** Rest declarations and "the next morning" wakings often sit at episode boundaries (downtime → adventure restart). Worth capturing episode-position.
- **Matt corrects himself.** T2 has `"around noon at the presentational stage-- not at noon, at dusk. Sorry, the other one."` Phase 2 must handle within-turn time corrections — probably take the latest assertion in the turn.

---

## 3. Proposed trigger taxonomy

Four categories. None are catchalls. Uncategorizable candidates either fail Stage 0 (rejected) or emit with `unknown_shape: true` (per Lesson 2).

### 3.1 `in_scene_compression`

**Definition.** Matt narrates a quantity of fictional time elapsing within an active scene without ending it. Covers brief pauses, task durations, and short montages. Granularity typically seconds-to-an-hour.

**Examples.**
- T5 (C1E108-820) — `"it's probably been close to an hour"` (smelting task).
- T6 (C1E108-2166) — `"over the next 20 or so minutes"` (forging montage).
- T7 (C1E108-2342) — `"After about five minutes or so, you finish"` (task bookend).
- T15 (C2E025-1900) — `"over the next 15 minutes or so"` (Detect Magic scan).
- T19 (C1E007-47) — `"you wait for about a minute"` (atmospheric pause).

**Signals.**
- Duration phrase: `(a|an|\d+|a few|a couple|several|some)\s+(second|minute|hour)s?` plus container verbs `wait/take/spend/finish/work/scan` OR `over the next [duration]` OR `after (about )?[duration]`.
- Scene continues after the trigger turn (no `the next morning` / `as you wake` follow-up). This is a Stage 1 disambiguator vs §3.3.
- No travel verb in the same clause (else §3.2 wins).

### 3.2 `travel_duration`

**Definition.** Matt narrates the time taken by party travel/movement between locations. Granularity minutes-to-weeks. Often campaign-arc compression.

**Examples.**
- T8 (C2E010-140) — `"took you about the better part of two weeks"` (foot travel).
- T16 (C2E040-1132) — `"running for the better part of two hours"` (chase).
- T17 (C2E040-1273) — `"three or four hours of straight sprint through the forest"` (chase compression).
- T18 (C2E040-1680) — `"Over the next couple of days... multi-day travel"` (sea voyage).

**Signals.**
- Travel verb in the same clause: `travel/journey/ride/sail/march/walk/run/sprint/fly/coast/hike/trek` + duration phrase.
- OR `the trip/journey takes`, `it took you about [duration]` paired with motion context in preceding turns.
- Larger-granularity duration phrases (hours-days-weeks) bias toward travel over §3.1.

### 3.3 `scene_transition`

**Definition.** Matt narrates a discrete break — overnight rest, time-of-day pivot that begins a new scene, or session-cut framing. Often without explicit quantity; the duration is implied by the transition.

**Examples.**
- T1 (C1E064-1454) — `"As you guys come to consciousness the next morning..."`.
- T10 (C2E010-2074) — `"the night has gone purple to dark... as night has taken it"`.
- T11 (C2E025-2015) — `"as the sun begins to hit the mountains... coming sunset"`.
- T12 (C2E025-2083) — `"Long rest to you all. The next morning you come to consciousness..."`.
- T14 (C2E025-1996) — `"about 20 or so minutes later you hear..."` (short-form transition).

**Signals.**
- Transition phrases: `the (next|following) (morning|day|night|evening|afternoon)`, `as (the sun|morning|evening|night|dawn|dusk)`, `(long rest|short rest)\.?`, `you (wake|come to consciousness)`, `(some time|moments|minutes|hours|days) later`, `the sun (rises|sets|begins to)`, `as (night|morning) (falls|takes|breaks)`.
- New scene begins immediately after — different setting / location / state.

### 3.4 `cumulative_anchor`

**Definition.** Matt explicitly states (a) how much time has passed since a reference point, or (b) what time-of-day it currently is in the campaign. Establishes or restates the campaign-clock anchor without itself advancing it. Often surfaces in response to player questions.

**Examples.**
- T2 (C1E064-2187) — `"It's actually now getting to dusk."`.
- T4 (C1E064-166) — `"It's been close to a week in the Feywild total, all the nights you've rested."`.
- T9 (C2E010-270) — `"It's late afternoon. You're probably about an hour and a half... from sundown."`.
- T13 (C2E025-2243) — `"It's now pushing past maybe one or two in the morning."`.

**Signals.**
- Anchor phrases: `(it's been|it has been|it is now|it's now|since you|since last)`, `(it's|it is) (early|late|mid-)?(morning|afternoon|evening|night|dawn|dusk|noon|midnight)`, `pushing (past|close to)`, `[duration] (since|ago)`.
- Often paired with a temporal preposition pointing backward.
- No travel verb, no scene transition phrase.

### 3.5 Unknown-shape (flag, not category)

Per Lesson 2, no default catchall. A candidate that passes Stage 0 (genuinely a time-mention) but matches none of §3.1-3.4 cleanly emits with `category: null`, `unknown_shape: true`. These are surfaced for hand-review and used to seed taxonomy revision in v2 if a new shape recurs. They are **not** counted in category proportions.

### Priority order (tiebreaker for multi-match)

`scene_transition` > `travel_duration` > `cumulative_anchor` > `in_scene_compression`. Rationale: scene-transition is the highest-impact event (changes scene state); travel beats anchor because travel is action+time, anchor is commentary; cumulative anchor beats in-scene compression because the cumulative-anchor signals are more specific.

---

## 4. Considered and rejected categories

- **`scene_pause` (separate from in_scene_compression).** Considered splitting "wait a minute" (atmospheric beat) from "you take five minutes to case" (task duration). Rejected: hand-distinguishing in-scene-pause from short task-duration is unreliable from text alone, and the granularity (both seconds-to-minutes) is the same. Folded into §3.1.
- **`time_of_day_anchor` (separate from cumulative_anchor).** Considered splitting "it's late afternoon" from "it's been a week total." Rejected: both serve the same research function (establishing where the campaign clock currently sits), differ only in granularity. Folded into §3.4.
- **`spell_duration` / `combat_duration`.** Rejected as a category — these are game-mechanic time, not fiction-time. Stage 0 rejects them as DISCOURSE. Combat round-counts pass forward as STATE flag (§5) for separate research.
- **`deadline_set_by_npc`.** "Eight days" / "Two weeks" / "by sundown" said by an NPC in dialogue. Real fiction signal but the campaign clock isn't advancing — the NPC is announcing a future window. Rejected as Stage 0 DISCOURSE for v1; filed for a future `narrative_pressure_v1` extractor (same parking-lot as Encounter Cadence's `world_event_sighting`).
- **`backstory_recall`.** "Six hours ago, the Cinder King roared..." said in NPC dialogue or Matt-narration recap. Backward-looking, no clock advance. Rejected — Stage 0 DISCOURSE if NPC-quoted, otherwise reject if no current-clock implication.
- **`session_break_framing`.** "We'll pick up two weeks from now" or "we'll see you guys in a few minutes." Rejected: real-time OOC; Stage 0 reject.
- **`combat_round_count`.** "Six rounds of this challenge," "after three rounds." Considered as a category. Rejected: better as a STATE flag because these are mid-event mechanic, not progression events. Some research questions want them; capture via flag, not category.
- **`unspecified_time_pass`.** "The time has passed. They're miles and miles and miles..." (T3). Considered as a category. Folded into §3.2 `travel_duration` when motion verbs appear, or §3.3 `scene_transition` when scene-end phrasing appears. If neither, emits with `unknown_shape: true`.
- **`real_world_calendar`.** "Two weeks from now, the first Thursday of September, I'll be out of town." Rejected: Stage 0 DISCOURSE — production OOC.
- **`in_universe_calendar_event`.** "It's almost Harvest Close in two weeks" (C2E010 t330). Rare; folded into §3.4 cumulative_anchor (the Harvest-Close phrase is itself a calendar anchor). Track via `unknown_shape: true` if pattern doesn't match cleanly.

Per the no-new-categories doctrine from Ship 1: 4 well-defined categories beat 7 overlapping ones.

---

## 5. Stage 0 discourse layer design

Required, not optional. Time-Mention is more vulnerable than Encounter Cadence to discourse-as-event confusion (recon shows ~3x naive over-count, dominated by the overloaded `second` token). Per Lesson 5, Stage 0 runs **before** Stage 1 candidate detection.

Each candidate (a MATT turn matching the broad time regex) is classified into:

### EVENT (continue to Stage 1)
Default. Matt narrating actual fiction-time progression or anchor.

### STATE (pass forward with flag, may modify Stage 1 classification)
- **`is_combat_state: true`** — trigger sits inside an active combat (most recent prior init within ~25 turns and no closeout signal). Combat round-counts (`six rounds of this challenge`, `after three rounds`) and mid-combat duration narration (`for a minute` of a Hold Person target) flag here.
- **`is_recap_state: true`** — trigger sits within an episode-recap block (early-episode "Last week we left off..." narration). These references are real fiction-time but already happened — they don't advance the clock now. Detected by episode position < 0.10 + presence of recap-triggering vocabulary in preceding turns.

STATE-flagged records are emitted (so they're available for analysis) but downstream stats can filter them out for "fresh time-progression" rates.

### DISCOURSE (reject the candidate, emit nothing)

**D1. Production OOC.** Episode openers (`welcome to`, `tonight's episode`, `give you guys some character backstory`, `we'll be with you in just a second`), break announcements (`back here in a few minutes`, `see you (guys )?in (a few minutes|a second)`, `we'll be back`, `[break]` token), sponsor reads (`stream of many eyes`, `wyrmwood`, `sponsor`, `patreon`, `D&D Beyond`), real-world references (`Thursday of September`, `out of town`, daylight-savings banter).

**D2. Spell/rules duration.** Matt explaining game mechanics. Patterns:
- `lasts for (a|an|\d+|the next)\s+(round|minute|hour|day|second)`
- `(at the )?end of (each of )?your turns?`
- `the spell (has )?(faded|ended|expires|drops)`
- `concentration (broken|drops|ends)`
- Co-occurrence with named D&D spell tokens (`Haste`, `Bigby's`, `Modify Memory`, `Hold Person`, `Hex`, `Detect Magic`, `Plane Shift`, `Stoneskin`, etc. — maintained as a spell-name list, not exhaustive).

**D3. DM table-talk.** Procedural pauses by Matt at the table. Patterns:
- `hold (on|tight) (a|just )?second`
- `(just|wait) a second(?: there)?`
- `one second please`
- `(let me|let's) (see|figure|look)`
- Standalone `a second` / `a minute` directly inside a question or imperative addressed to a named PC.

**D4. Combat micro-beat (overloaded "for a second").** `for a second` describing a one-instant pause in attack/reaction narration with no clock advance. Patterns:
- `(reels|steps|leans|locks|pauses|tense|hesitates) (back )?for a second`
- `(holds|waits|glances|looks) (at .+ )?for a second`
- Within ~3 turns of a damage-roll or attack-roll signal.

**D5. Idiom artifacts.**
- `a second (time|attack|strike|round|shot|level|floor|sweep)` — "again," D&D mechanic, or architecture; not time.
- `the second (one|of)` — ordinal, not time.
- `(I'll )?owe you a round` — drinks idiom.
- `gain an hour` (daylight savings table chatter).

**D6. NPC dialogue (in-character).** Matt voicing an NPC who mentions time. Default: reject for v1 — the campaign clock isn't advancing during NPC speech, the NPC is recalling the past or stating a future deadline. Detection signals:
- Quoted speech in the trigger sentence: `"..."` enclosing the time phrase.
- Tag verbs in the trigger sentence: `(he|she|they|the [name]) (says|goes|replies|continues|states|answers)` immediately preceding or following the time phrase.
- First-person voice in Matt-narration with non-Matt referent (`"my brother arrived three hours ago"` voiced by NPC).

NPC-dialogue detection is medium-risk (Lesson 5's open question for Encounter Cadence applies here too). Phase 2 hand-sample will report NPC-dialogue Stage 0 reject precision separately. If quote-mark detection is too lossy, fall back to "any preceding MATT turn with quote-marks within ~3 turns of trigger" → flag rather than hard-reject.

**D7. Player question pass-back.** Matt's turn is a brief response to a player question (single short MATT turn ≤ 60 chars containing only a duration). Pattern: turn length < 60 chars + immediately-preceding non-MATT turn ending in `?`. Likely a Q&A; emit only if the answer establishes a current-clock anchor (then route to §3.4).

### Stage 0 priority

A single candidate may match multiple DISCOURSE filters; first-match-wins in this order: D1 > D2 > D6 > D5 > D4 > D3 > D7. (Production OOC is hardest reject; idiom and table-talk are softer and may overlap with real signal.)

### Reject vs flag-and-continue policy

When Stage 0 rejects, the record is dropped — `unknown_cause` flag is for Stage-1 ambiguity, NOT for Stage-0 ambiguity. (Per Lesson 2: Stage 0 rejection is the "filter entirely" path.)

---

## 6. Causality-window defaults

Per Lesson 6, default for cause-effect detection is 10-15 turns. Time-Mention narrows that with explicit justification: time-mentions are mostly self-contained — the trigger turn carries the duration assertion. The exception is anchored relative-references.

### Default preceding-context window

**500-800 chars / ~5-8 turns.** Smaller than Encounter Cadence's 1500/15-25. Justification: §3.1, §3.2, §3.4 categories are classifiable from the trigger turn alone plus minimal preceding context (verb tense, scene continuity check, NPC-dialogue presence). §3.3 needs a slightly wider preceding window to verify the scene actually transitions (next 1-2 turns post-trigger), but post-trigger context can be a forward window of ~3 turns.

### Anchored relative-reference handling

Triggers containing relative-time phrases (`the next morning`, `the following day`, `later that night`, `moments later`, `[duration] later`, `shortly after`, `after that`, `the next [unit]`) are flagged `is_anchored: true`.

For anchored triggers, the extractor walks back up to **15 turns** to find the most-recent prior anchor candidate — the most recent prior time-mention, scene-transition, or rest declaration — and records its turn number in `time_anchor_turn_number` (nullable; null if no anchor found within window).

15-turn back-walk is justified because rest-declarations and prior time-mentions can sit a substantial number of turns before the wake-up narration (a long rest may be declared at turn 1380 with table chatter intervening before Matt narrates "the next morning" at turn 1454).

### Episode-position context

Time-mentions cluster differently from encounters:
- `scene_transition` (§3.3) over-represents at episode mid-points and ends (downtime → next-day, session-end framing).
- `cumulative_anchor` (§3.4) over-represents at episode openings (recap state) and after long rests.
- `travel_duration` (§3.2) clusters at scene boundaries.

Capture `episode_position_pct` per `CORPUS_BUILDER.md` Output Format Contract; analyses can stratify by category × position.

### Field summary

```json
{
  "time_anchor_turn_number": 1380,    // null if not anchored
  "is_anchored": true,
  "anchor_distance_turns": 74,         // null if not anchored
  "preceding_context_chars": 800,
  "is_combat_state": false,
  "is_recap_state": false,
  "unknown_shape": false               // per Lesson 2; never default-true
}
```

---

## 7. Predicted FP family taxonomy

Per Lesson 4, FP families come in waves. List of predicted shapes from §2 recon. The list is incomplete by design — Phase 2 hand-sample will surface new families. Each new family becomes a documented Stage 0 / Stage 1 patch, not a silent regex addition.

| # | FP shape | Example | Stage where filtered |
|---|---|---|---|
| FP1 | Spell/rules duration | `"Haste lasts for a minute"` | Stage 0 D2 |
| FP2 | Production OOC + episode breaks | `"back here in a few minutes"` | Stage 0 D1 |
| FP3 | NPC dialogue time references (deadline / backstory) | `"It's been over a year at least"` (NPC) | Stage 0 D6 (medium-risk; quote-mark fallback) |
| FP4 | Combat micro-beat `for a second` | `"reels back for a second"` | Stage 0 D4 |
| FP5 | Idiomatic `second` (a second time/attack/floor/level) | `"You have a second attack"` | Stage 0 D5 |
| FP6 | DM table-talk `hold on a second` | `"hold on just a second"` | Stage 0 D3 |
| FP7 | Real-world calendar references | `"the first Thursday of September"` | Stage 0 D1 (production-OOC subset) |
| FP8 | Combat round-mechanic call | `"Six seconds for all of you to--"` | Stage 0 STATE flag (`is_combat_state: true`); kept for separate research |
| FP9 | Recap-block time references | `"Last week we left off three days into..."` | Stage 0 STATE flag (`is_recap_state: true`); often re-statement of past time |

Open prediction: a tenth family will surface in Phase 2 hand-sample, and a tighter bound on the post-ship rate will only be visible after Phase 5's wild-corpus sampling. Per Lesson 3, the held-out gate-pass rate is an upper bound, not the published rate.

---

## 8. Held-out methodology spec (gate-set + validation-set)

Per Lesson 7. Mechanical enforcement, not policy.

### Gate-set (Phase 4 ship-gate measurement)

- **~25 records.** Sampled `random.seed(7777)` from records emitted by the Phase 2 extractor, drawn from episodes never reviewed during calibration.
- **File:** `corpus_builder/findings/time_mention_gate_set_v1.json`. Top-level keys `calibration` (full records, used during phases 2-4) and `gate_holdout` (records with `raw_text` STRIPPED during calibration mode).
- **Test runner:** `corpus_builder/extractors/test_time_mention_eval_v1.py`. Default mode reads only `calibration`. Held-out access requires explicit `--holdout` flag. Runner refuses to read `gate_holdout` records' `raw_text` unless `--holdout` is passed.
- **One-shot measurement.** Gate-set is read exactly once at Phase 4 to compute FP rate, classification precision, anchor-resolution accuracy. Results recorded in `findings/time_mention_validation_v1.md`.
- **If gate fails:** spec acknowledges that an iteration cycle can re-sample the gate-set ONCE, with `random.seed(7778)`, after fixing the regression. Beyond that, Phase 5 stops and reports.

### Validation-set (post-ship publication number)

- **~15 records.** Sampled separately from a different `random.seed(9999)`, drawn from a pool of records emitted by the FULL parse — including episodes the extractor saw at scale that calibration never touched.
- **File:** `corpus_builder/findings/time_mention_validation_set_v1.json`. Same JSON-stripping discipline as gate-set; `--validation` flag required.
- **Never named or examined during calibration.** Phase 1 (this doc), Phase 2 (extractor build), Phase 3 (calibration), Phase 4 (gate measurement) all operate without referencing the validation-set's contents. Even the existence of the file is created at Phase 5 — sampled from full-parse output, never from hand-sample.
- **Run exactly once after the gate-set passes.** Findings report both gate-set and validation-set numbers. Validation-set is the published claim; gate-set is the development tool.

### Mechanical enforcement (baked into Phase 2)

- Per-extractor JSON files are split. `gate_holdout` and `validation` arrays do NOT carry `raw_text` in the calibration-readable copy.
- Test runner has three modes: `--calibration` (default), `--holdout` (gate), `--validation` (one-time post-ship). Modes cannot be combined; runner errors if both flags passed.
- Findings doc's reliability section reports both numbers honestly. If validation-set FP/precision diverges sharply from gate-set, validation-set is authoritative (per Lesson 3's Encounter Cadence precedent).

---

## 9. Pattern-matching strategy (high level — no code)

No code in this session. Sketch only — Phase 2 implements.

### Stage 1 — Candidate extraction
Iterate `c=2` JSON files. Build per-episode turn list keyed by `NUMBER` (chunks repeat). Filter to `MATT` turns. Match each MATT turn against the **broad time regex union** (the same regex used in §2 recon, refined). Each match becomes a candidate.

### Stage 0 — Discourse / state filtering (runs BEFORE Stage 1)
Per §5. Each candidate is tagged EVENT / STATE / DISCOURSE. DISCOURSE candidates are dropped. STATE candidates pass forward with flags (`is_combat_state`, `is_recap_state`). EVENT candidates continue.

(Note: the §5 layer is named "Stage 0" per Ship 1's terminology. It runs after candidate match but before category classification — i.e. it filters candidates, not raw turns.)

### Stage 2 — Per-candidate category classification
For each surviving EVENT candidate, classify into §3.1-3.4 by checking category-specific signals (travel verbs, transition phrases, anchor phrases). Multi-category matches resolve via §3 priority order. Candidates that pass Stage 0 but match no category cleanly emit with `category: null`, `unknown_shape: true`.

### Stage 3 — Anchor resolution
For triggers flagged `is_anchored: true`, walk back up to 15 turns for the most-recent prior time-mention or rest-declaration. Record `time_anchor_turn_number`, `anchor_distance_turns`. Null if no anchor found.

### Stage 4 — Granularity bucket
Derive `granularity_bucket` from the duration phrase: `seconds | minutes | hours | days | weeks | months | years | unspecified`. Largest matching unit wins (`"a day and a half"` → `days`).

### Stage 5 — Output one record per fresh time-mention
Required fields per `CORPUS_BUILDER.md` Output Format Contract, plus extractor-specific:

```json
{
  "category": "scene_transition",
  "granularity_bucket": "hours",
  "is_anchored": true,
  "time_anchor_turn_number": 1380,
  "anchor_distance_turns": 74,
  "is_combat_state": false,
  "is_recap_state": false,
  "unknown_shape": false,
  "preceding_matt_context": "<concatenated last N MATT turns up to char budget>",
  "trigger_phrase": "the next morning"
}
```

### Hand-sample target

10 episodes spanning C1 early/mid/late + C2 early/mid/late. Disjoint from Ship 1's reviewed list AND from this Phase 1's recon list (so Phase 1's seven episodes don't bias Phase 2's hand-sample). Expected yield: ~50-90 EVENT records, ~30-50 STATE-flagged (combat round-counts + recaps), ~80-120 DISCOURSE rejects (Stage 0 working hard).

### Out-of-scope for v1
- OOC stripping at episode boundaries beyond the D1 patterns.
- Cross-episode anchor resolution (e.g., the `next morning` reference from C2E025 t2083 anchors to C2E024's session-end — not implemented).
- In-universe calendar normalization (Harvest Close, Zenith, etc.). Per `CORPUS_BUILDER.md` no-master-ontology rule.
- Player-spoken time references (filtered at MATT-only import).

---

## 10. §11 decisions needing Jordan's lock

Same shape as `ENCOUNTER_CADENCE_V1_SPEC.md` §6. Restate / trade-offs / recommended default / confidence.

### §11.1 — Time granularity scope: which scales does v1 capture?

**Restate.** Does v1 capture all granularities (seconds → years) including combat round-counts (~6 seconds), or scope to fiction-time-of-meaning (minutes → years) and exclude sub-minute round-mechanics?

**Trade-offs.**
- **All scales (proposed).** Captures sub-minute beats (T19, T20) which sometimes carry atmospheric weight. Captures combat round-counts via STATE flag. Largest research surface. Higher FP risk in the seconds band.
- **Minutes-and-up only.** Drops the entire "second" overloaded-token problem (FP4, FP5, FP6 mostly disappear). Cleaner Stage 0. Loses `"For a few seconds of silence"` (T20) and similar dramatic beats — about 5-8% of real signal across the recon sample.
- **Hours-and-up only.** Cleanest. Captures only campaign-arc-relevant compression. Loses task-duration (T5, T6, T15) — ~25% of real signal — which IS load-bearing for spec questions about session pacing.

**Recommended default.** **All scales, with combat round-counts as STATE flag.** Cites Lesson 6 (don't narrow without justification) and Lesson 8 (detection vs classification separable — keep detection broad, narrow via flags). The seconds-band FPs are addressed in Stage 0; we shouldn't pre-narrow scope for FP convenience.

**Confidence.** **MEDIUM.** If Phase 2 hand-sample shows the seconds-band Stage 0 reject precision is below ~85%, retreat to "minutes-and-up" and document the choice. The minutes-and-up fallback is a one-line config change.

---

### §11.2 — Anchored reference handling: explicit anchor field, or `is_anchored: false` flag only?

**Restate.** Triggers containing `the next morning` / `moments later` / etc. depend on a prior anchor for interpretation. Do we resolve anchors at extract-time (walk back 15 turns, record turn number) or just flag `is_anchored: true` and leave anchor resolution to downstream analysis?

**Trade-offs.**
- **Explicit anchor field (proposed).** `time_anchor_turn_number` resolved at extract-time. Phase-2 cost: one extra walk-back per anchored trigger (~30% of triggers in recon). Downstream gets ready-to-analyze records. Risk: anchor-resolution becomes a measurable accuracy claim with its own FP rate (yet another precision number to validate).
- **Flag-only.** Just emit `is_anchored: true` with no resolution. Cheaper. Defers work to downstream. Per Lesson 1, this is a clean "detection vs causal classification" split — emit detection, leave causal anchoring as a separate research pass.
- **Both.** Try resolution; if it succeeds, fill `time_anchor_turn_number`; if not, just flag. Same cost as explicit field but defends against anchor-resolution failure rate.

**Recommended default.** **Explicit anchor field with null-on-fail.** Cites Lesson 8 (separate detection from classification reliability claims) — the findings doc reports anchor-resolution accuracy independently, just like Encounter Cadence reported detection vs classification independently. If anchor resolution proves unreliable in Phase 4, downstream consumers can ignore the field; the data is still there.

**Confidence.** **MEDIUM.** The 15-turn back-walk for `the next morning` may often miss the original long-rest declaration (which can sit further back in casual table-chatter). Phase 2 hand-sample reports anchor-found rate; if <60%, widen to 25 turns (still aligned with Lesson 6's range).

---

### §11.3 — Player time-mentions: hard-reject or soft-reject?

**Restate.** Per `CORPUS_BUILDER.md`, MATT-only filter at import (same as `dnd_knowledge_import.py`). But sometimes a player asks `"how long has it been?"` and Matt's MATT-turn answer (sometimes one or two words) is the actual time-anchor establishment. Do we require the trigger phrase to be inside a MATT turn, or do we allow trigger phrases inside non-MATT turns when Matt's immediately-following turn confirms?

**Trade-offs.**
- **Hard-reject all non-MATT (proposed).** Matches Ship 1's MATT-only rule. Simplest. Misses the rare cases where a player's question carries the actual time language and Matt just confirms ("yes" / "ten minutes"). Phase 1 recon found ~3-5 such cases per episode — small but non-zero.
- **Soft-reject (allow non-MATT trigger if Matt's next turn confirms).** Catches the missed cases. Adds a multi-speaker rule that Encounter Cadence didn't have. Risk of over-counting if Matt's confirmation is `"sure"` / `"yeah"` without any time language.

**Recommended default.** **Hard-reject for v1.** Cites the single-extractor MATT-only doctrine and Lesson 4 (assume FP families come in waves — adding a multi-speaker rule introduces a new family before we've hardened single-speaker). Folds the missed-cases into Phase 5 wild-corpus sampling notes; if the missed-case rate is >10% of real time-mentions, file for v2.

**Confidence.** **HIGH.** Doctrinally aligned. The cost of missing 3-5 records per episode is far smaller than the cost of opening up multi-speaker triggers.

---

### §11.4 — OOC discourse boundary: how aggressive on Stage 0 reject?

**Restate.** Episode-break announcements (`back here in a few minutes`) are clearly OOC reject. But borderline cases: Matt's `"we'll pick up two weeks from now"` at session-end mixes in-fiction framing ("two weeks" might be the in-fiction gap until the next session) with real-world break framing. Reject all such mixed cases, or distinguish?

**Trade-offs.**
- **Aggressive reject (proposed).** Any Matt turn containing canonical break vocabulary (`back here in`, `we'll see you guys`, `take a quick`, `[break]`, `bathroom break`) → DISCOURSE reject regardless of additional time language. Loses the rare in-fiction-framing-at-session-end. Cleanest Stage 0.
- **Distinguish.** Try to detect "next session implies in-fiction time gap" — but no reliable signal in text. Phase 2 hand-sample would have to validate this. Almost certainly under-precise.

**Recommended default.** **Aggressive reject.** Cites Lesson 5 (Stage 0 doctrine) — discourse-as-event mixing is the largest extractor risk, err on the side of reject. The lost session-end framing is recoverable later via a separate extractor that operates on episode-end positions specifically.

**Confidence.** **HIGH.** Same reasoning as Encounter Cadence's §6.5 doctrine.

---

### §11.5 — Episode-break time references: always reject as DISCOURSE, or distinguish "next session" framing from in-fiction time?

**Restate.** Distinct from §11.4: when Matt frames a session-end with `"two weeks of travel ahead, see you next time"`, the "two weeks of travel" IS in-fiction time even though it co-occurs with break framing. Does the in-fiction phrase emit as a `travel_duration` record despite being adjacent to OOC?

**Trade-offs.**
- **Reject the entire turn (matches §11.4).** Simple. Loses real signal at session boundaries — likely 1-3 records per session-cut.
- **Split-and-emit.** Try to extract just the in-fiction phrase. Phase 2 cost: split-by-sentence + per-sentence Stage 0. Adds complexity proportional to gain.
- **Emit if in-fiction signal is dominant.** Use a heuristic: in-fiction phrase length > OOC phrase length → emit, else reject. Fragile.

**Recommended default.** **Reject the entire turn for v1**, document the loss in findings. Aligned with §11.4. If post-ship analysis shows session-boundary travel records are load-bearing for any spec question, ship a separate `episode_boundary_extractor` (parallel to `narrative_pressure_v1` parking lot).

**Confidence.** **MEDIUM-HIGH.** Loses real signal but stays doctrinally clean.

---

### §11.6 — Multi-mention turns: emit one record per turn or one per mention?

**Restate.** A single MATT turn can contain multiple time phrases (T2: "left in the morning... now getting to dusk" carries two anchors). Emit one record per turn (with all phrases concatenated) or one per phrase?

**Trade-offs.**
- **One per phrase (proposed).** Each detected phrase becomes a record. Same turn may produce 2-3 records. Allows category mixing within a turn (the C1E064 t2187 example would emit `cumulative_anchor` for "in the morning" and another `cumulative_anchor` for "now getting to dusk"). Risk of double-counting if both phrases describe the same fictional moment.
- **One per turn.** Simpler. Picks the most-specific category. Loses within-turn structure.

**Recommended default.** **One per phrase, with `same_turn_record_index` field.** Downstream can dedup by turn-number if it cares. Captures within-turn structure that might matter for Track 4 spec questions about anchor-density.

**Confidence.** **MEDIUM.** Multi-mention turns are rare (~5-8% of trigger turns from recon). Phase 2 hand-sample reports the proportion; if higher, revisit.

---

### §11.7 — `cumulative_anchor` as separate category vs. flag on other categories

**Restate.** §3.4 cumulative_anchor is conceptually orthogonal to the others — a `scene_transition` ("the next morning") often establishes a new anchor too. Should cumulative-anchor be its own category (current proposal) or a flag (`establishes_anchor: true`) on the underlying event?

**Trade-offs.**
- **Separate category (proposed).** §3.4's signal patterns (`it's been X total`, `it's now Y time-of-day`, `since last`) are textually distinct from §3.3's (`the next morning`, `as evening falls`). Hand-classifier can validate the boundary. Risk: overlap in compound sentences ("the next morning. It's been a week total now.").
- **Flag on other categories.** Cleaner conceptually. Forces Phase 1 to define the underlying event in 3 categories instead of 4 — but the "event" of just stating current time-of-day without scene transition (T9, T13) doesn't fit any of §3.1-3.3. Becomes `unknown_shape: true` traffic, which Lesson 2 said to keep small.

**Recommended default.** **Separate category.** §3.4's text signals are clean enough to classify, and folding it as a flag pushes recall onto the `unknown_shape` flag — defeats the no-sinkhole goal. Compound-sentence cases emit two records (per §11.6 multi-mention rule).

**Confidence.** **MEDIUM.** If Phase 2 hand-sample shows §3.3 / §3.4 boundary is unstable (cross-classifier disagreement >20%), collapse to a single `scene_transition_or_anchor` category and flag the sub-shape.

---

## 11. Open questions

1. **NPC-dialogue detection without quote marks.** Matt frequently voices NPCs without quote-mark punctuation (the same issue Encounter Cadence's §3.4 flagged). Phase 2 hand-sample must report NPC-dialogue Stage 0 D6 reject precision separately. If quote-mark detection is too lossy, fall back to "any preceding MATT turn quoted within ~3 turns" → STATE flag rather than DISCOURSE reject. Decide post-Phase-2.

2. **C1 vs C2 phrasing drift.** Six years of Matt's DM evolution between C1E001 and C2E046. Did time-mention phrasing change (especially `the next morning` framing, anchor declarations)? Phase 2 hand-sample should report category distribution split C1 vs C2 to surface drift; recon didn't measure this.

3. **Granularity bucket validation.** Are `seconds/minutes/hours/days/weeks/months/years` the right buckets, or is `unspecified` going to dominate (Matt often just says `"a while"` / `"some time"`)? Phase 2 reports bucket distribution.

4. **Anchor walk-back depth.** 15 turns may be insufficient for anchored references that fire after a long player-banter block. If Phase 2 hand-sample shows anchor-found rate < 60%, widen to 25 turns. Document the choice.

5. **Combat-state detection signal.** Stage 0's `is_combat_state` flag depends on knowing whether combat is active. Encounter Cadence's v1.3 has this signal; Time-Mention can either reuse Encounter Cadence's per-episode init events as input OR re-derive within the extractor. Reusing creates a cross-extractor dependency (filed in `CORPUS_BUILDER.md` as something to avoid). Re-deriving duplicates work. Phase 2 spec must decide.

6. **Recap-block detection signal.** `is_recap_state` requires identifying recap blocks. Heuristic: episode-position < 0.10 + presence of recap vocabulary (`last week`, `we left off`, `previously`, `as we begin tonight`). Phase 2 hand-sample validates this heuristic.

7. **Hand-sample episode list.** Phase 2 should sample 10 episodes disjoint from both Ship 1's reviewed list AND this Phase 1's seven recon episodes. Proposed: C1E003, C1E018, C1E055, C1E085, C1E105 (downtime check), C2E005, C2E015, C2E033, C2E042, C2E046. Adjust if Jordan has known-difficult episodes in mind.

8. **Findings doc placement.** Same convention as Ship 1: validation doc at `findings/time_mention_validation_v1.md`; findings doc at `findings/time_mention_findings.md` after full parse. Confirm.

---

## Decisions for Jordan to lock in chat (Phase 2 starts after this)

§11.1 granularity scope · §11.2 anchored references · §11.3 player-mention rejection · §11.4 OOC aggressiveness · §11.5 episode-break framing · §11.6 multi-mention rule · §11.7 cumulative_anchor as category vs flag. Plus answers to §11.OQ1 / §11.OQ5 / §11.OQ7 / §11.OQ8 (NPC-dialogue fallback, combat-state source, hand-sample list, doc placement).

Phase 2 ships: extractor at `corpus_builder/extractors/time_mention.py`, hand-sample at `corpus_builder/samples/time_mention_sample.json`, validation report at `corpus_builder/findings/time_mention_validation_v1.md`, gate-set + validation-set JSON files. Full parse only after Phase 4 gate passes; validation-set runs once at Phase 5.

---

## Operating-doctrine checklist (per `corpus_builder_lessons_v1.md` §9)

- [x] **Stage 0 discourse gate designed BEFORE Stage 1 candidate detection.** §5 specifies EVENT / STATE / DISCOURSE patterns from sample observations.
- [x] **Causality window default 5-8 turns for trigger context, 15 for anchor walk-back.** §6 states the values and reasoning. Narrower than Encounter Cadence with explicit justification.
- [x] **Two held-out sets specified.** Gate-set (~25 records), validation-set (~15). §8 specifies mechanical enforcement (separate JSON keys, separate flags, separate runner modes) baked into Phase 2.
- [x] **FP-family taxonomy documented from Phase 1.** §7 lists 9 predicted FP shapes and Stage-where-filtered.
- [x] **No default catchall category.** §3.5 specifies `unknown_shape: true` flag for Stage-1 unclassifiable; Stage 0 rejects DISCOURSE entirely.
- [x] **Detection vs classification separation documented.** §9 splits candidate extraction (broad regex) from category classification (Stage 2). Findings doc will report each independently.
- [x] **Eval-set overfit risk acknowledged.** Header note + §8 state explicitly that gate-set is upper-bound, validation-set is the published claim.
