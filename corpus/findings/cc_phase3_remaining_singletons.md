# Compression Cadence — Phase 3 Remaining Singletons

**Status:** Phase 3 complete. Patches 1–4 landed clean at 18/27 = 66.7%.
**Date:** 2026-05-09
**Next gate:** Phase 4 gate-set construction.

These 8 families were deliberately deferred per Lesson 4 (don't iterate on
small-sample-specific failures). Each appears exactly once in the 10-episode
hand-sample. Gate-set or Phase 5 validation will determine which recur at
frequency worth patching.

---

## 1. `in_scene_micro_motion_within_town` — C1E050_t1867

**Trigger phrase:** "you make your way to the central"
**Extracted category:** LOCATION_DEPARTURE (FP)
**Raw text:** "Eventually you make your way to the central town square..." followed by
extended in-scene description of Westruun's defenses and the heads on pikes.
**Diagnosis:** Sub-scale destination (town square) within the city already in scene.
Whole turn is detailed in-scene movement + environment description. D3 micro-motion
FP. LOCATION_DEPARTURE_TRIGGER fires on `you make your way to [capitalized]` which
matches "to the central" but the destination is sub-locale, not city/region departure.
**Patch shape required:** D3 micro-motion extension: reject LOCATION_DEPARTURE when
destination noun is a sub-locale within an established scene (town square, market,
well, church). Hard to express cleanly in regex without false-positive risk on
legitimate departures. Needs destination-scope classifier.

---

## 2. `in_scene_micro_motion_approach` — C1E090_t1317

**Trigger phrase:** "You make your way to the structure"
**Extracted category:** LOCATION_DEPARTURE (FP)
**Raw text:** "You make your way to the structure. The exterior of it is this light-grey
stone, it's a cylindrical building..." Full building description and interior entry follow.
**Diagnosis:** Approach-to-and-enter a named building (Cobalt Reserve) within the
current city (Vasselheim). Already pre-flagged in recon. Same D3 micro-motion family
as C1E050_t1867 but approach vs. within-town-navigation shape.
**Patch shape required:** Same as singleton 1. "you make your way to the [structure/building]"
followed immediately by architectural description = approach FP. Destination-scope
detection or post-trigger context check (architecture vocab in next N chars).

---

## 3. `subject_misattribution` — C1E056_t1132

**Trigger phrase:** "leaving westward behind"
**Extracted category:** LOCATION_DEPARTURE (FP)
**Raw text:** "...you notice the burning spires, and you see the remnants of the horde
leaving westward behind the group of heroes..."
**Diagnosis:** "leaving" subject is the horde (NPCs), not the party. LOCATION_DEPARTURE
trigger `leaving [Named] behind` fired on wrong grammatical subject. Party-perspective
check needed: the party is the observer here, not the actor.
**Patch shape required:** Subject-extraction heuristic for LOCATION_DEPARTURE: reject
when the subject of the "leaving" clause is NPC/third-person (horde, army, enemies)
and the party is in observer position. Needs dependency parsing or heuristic
subject-noun detection preceding the trigger phrase.

---

## 4. `projective_future_montage` — C1E056_t2018

**Trigger phrase:** "over the next week"
**Extracted category:** TEMPORAL_MONTAGE (FP)
**Raw text:** "...most of the people, at least over the next week or so, will be outfitted
with the proper materials, food for the journey, and be able to make their way back
towards Westruun."
**Diagnosis:** Forward projection of what WILL happen — future tense ("will be outfitted").
Scene continues in present-moment council. Not a time-skip to a future point.
**Patch shape required:** Tense detector: reject TEMPORAL_MONTAGE when trigger phrase
is embedded in a future-tense clause (`will be`, `will have`, `are going to`, `would be`
within ±30 chars of trigger). Must not catch legitimate "over the next week [past-tense
narration]" e.g., "over the next week, they trained hard."

---

## 5. `verb_as_noun_modifier` — C1E013_t1673

**Trigger phrase:** "exits the room"
**Extracted category:** NPC_DEPARTURE (FP)
**Raw text:** "There's a single doorway that exits the room that is currently closed."
**Diagnosis:** "exits" is a relative clause on "doorway" (verb-as-relative-clause), not
an NPC departing. Homonym FP: the trigger pattern `exits the room` fired on the
architectural description of where the door leads.
**Patch shape required:** NPC-subject check for NPC_DEPARTURE: reject when the subject
of the trigger clause is an inanimate noun (doorway, passage, corridor, window) rather
than a person/NPC. Could also check that there is no animacy signal (NPC name, pronoun
he/she/they) in the same sentence before the trigger.

---

## 6. `descriptive_use_within_compression_turn` — C1E090_t2695 idx1

**Trigger phrase:** "throughout the day"
**Extracted category:** TEMPORAL_MONTAGE (FP / over-emission)
**Raw text:** "...with elements of gray bark, with moss that grow at the base and tuck
under the branches, where the shadows tend to linger throughout the day."
**Diagnosis:** Descriptive use of "throughout the day" inside a scene-description
clause about a tree's shadow patterns. The legitimate TEMPORAL_MONTAGE compression
already fired correctly on idx0 of the same turn ("over the next hour"). This is
over-emission of a decorative temporal phrase within an active compression turn.
**Note:** The within-turn dedup (Patch 2) uses a 200-char distance threshold; these
two phrases are ~1500+ chars apart in the turn so dedup doesn't fire. A tighter
approach: if a compression record has already been emitted for this turn, reject
TEMPORAL_MONTAGE triggers that appear inside descriptive/relative clauses
(subordinate clause detection). Hard to do with regex alone.

---

## 7. `category_misroute_party_action_as_npc` — C1E090_t1868

**Trigger phrase:** "exit the shop"
**Extracted category:** NPC_DEPARTURE (wrong category, should be LOCATION_DEPARTURE)
**Raw text:** "Doty turns. 'Ahh!' And comes running after you guys as you exit the shop."
**Diagnosis:** Party is the actor exiting ("as you exit the shop"), Doty is the NPC
chasing them. NPC_DEPARTURE trigger `exit[s] the room/shop` fired on a party-departure
context. Correct category is LOCATION_DEPARTURE.
**Expected category:** LOCATION_DEPARTURE (not NONE — the compression event is real,
just misrouted).
**Patch shape required:** Category re-routing: when "exit the [location]" trigger fires
AND the grammatical subject is second-person ("you", "you guys") rather than
third-person, route to LOCATION_DEPARTURE instead of NPC_DEPARTURE. Subject-person
detection for the clause preceding the trigger.

---

## 8. `logistical_question_not_compression` — C1E097_t1537

**Trigger phrase:** "you leave Doty behind"
**Extracted category:** LOCATION_DEPARTURE (FP)
**Raw text:** "...By the way, did you leave Doty behind or take Doty with you?"
**Diagnosis:** Matt asking a logistical party-composition question mid-transition. The
Wind Walk is the actual scene transition; "leave Doty behind" fired inside a yes/no
question about NPC inclusion. The trigger phrase is embedded in an interrogative
clause, not a declarative narration of departure.
**Patch shape required:** Interrogative-clause detect for LOCATION_DEPARTURE: reject
when trigger phrase appears inside a question ("did you [trigger]", "did they", "are
you [leaving]?"). Check for question mark at end of sentence or interrogative opener
("did", "do you", "are you", "have you") preceding the trigger.

---

## Summary table

| # | Family | Record | Category error | Patch complexity |
|---|--------|--------|---------------|-----------------|
| 1 | in_scene_micro_motion_within_town | C1E050_t1867 | FP LOCATION_DEPARTURE | High — destination-scope classifier |
| 2 | in_scene_micro_motion_approach | C1E090_t1317 | FP LOCATION_DEPARTURE | High — destination-scope classifier |
| 3 | subject_misattribution | C1E056_t1132 | FP LOCATION_DEPARTURE | High — subject extraction |
| 4 | projective_future_montage | C1E056_t2018 | FP TEMPORAL_MONTAGE | Medium — tense detector |
| 5 | verb_as_noun_modifier | C1E013_t1673 | FP NPC_DEPARTURE | Medium — animacy/subject check |
| 6 | descriptive_use_within_compression_turn | C1E090_t2695 idx1 | FP TEMPORAL_MONTAGE | High — subordinate clause detect |
| 7 | category_misroute_party_action_as_npc | C1E090_t1868 | WRONG_CAT NPC→LOC | Medium — subject-person routing |
| 8 | logistical_question_not_compression | C1E097_t1537 | FP LOCATION_DEPARTURE | Low — interrogative detect |

Families 1–3 cluster around LOCATION_DEPARTURE subject/scope detection — likely worth
addressing together in Phase 4 if gate-set confirms they recur. Families 4–8 are
isolated shapes; defer until gate-set frequency data available.
