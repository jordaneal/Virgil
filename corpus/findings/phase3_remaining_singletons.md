# Phase 3 Remaining Singletons

**Date:** 2026-05-07  
**Extractor:** loot_reward_v1  
**Eval set:** loot_reward_handsample_v2.json (41 records)  
**Status after Patches 1–4:** 21/31 = 67.7% strict precision, 0 retention regressions

Patches 1–4 cleared 4 named families (8 records total). The 7 singleton families
below remain as FPs. Per Phase 3 operating rules (Lesson 4), singletons are
deliberately deferred — singleton-by-singleton patching produces brittle,
overfit rules. These are documented here for Phase 3.5 / Phase 4 gate-set
construction decisions.

---

## Remaining singleton FPs (7 records)

### 1. `description_offer_not_loot`

**Record:** C1E010_t1636  
**Trigger phrase:** `I'll give you`  
**Raw text:** `"I'll give you a detailed description. Essentially, this pyramid comes to a top..."`  
**Judge notes:** "I'll give you a detailed description" is a meta-statement offering
elaboration, not loot. Trigger fired on "I'll give you" + non-reward object.  
**Diagnosis:** QUEST_OFFER_TRIGGER fires on `i'?ll\s+give\s+you\b`, then routes to
MATERIAL_LOOT (Matt voice). The object "a detailed description" is speech-act framing,
not a physical item. Distinguishing grant-objects from speech-act objects requires
object-type classification (reward noun vs. speech noun), which is not in scope for
a single regex.  
**Candidate fix:** expand the ILL_GIVE_YOU_THAT_RE to also reject "I'll give you a
[speech-act noun]" (description, summary, rundown, overview, map). Risk: "I'll give
you a sword" → must not match. Narrow noun list only.

---

### 2. `damage_math_misread`

**Record:** C1E052_t984  
**Trigger phrase:** `I'll give you`  
**Raw text:** `"Seven plus eight, 15, reduced to half, that's seven. So I'll give you the direct amounts here. So this is with the reduction. So that's seven points of slashing damage."`  
**Judge notes:** "I'll give you the direct amounts here" refers to damage calculation,
not loot. DISCOURSE reject.  
**Diagnosis:** Same QUEST_OFFER_TRIGGER / Matt-voice routing as above. Context is
arithmetic narration; "the direct amounts" is a speech-act object, not a reward.
Preceding-turn context shows mid-combat damage tracking.  
**Candidate fix:** same speech-act noun approach as above ("amounts", "numbers",
"the math", "the total"). Or add a damage-arithmetic DISCOURSE pattern: `\d+\s+points?\s+of\s+(?:slashing|piercing|bludgeoning|fire|cold|acid|lightning|thunder|necrotic|radiant|psychic)\s+damage` in the sentence → DISCOURSE.

---

### 3. `mid_combat_existing_item_description`

**Record:** C1E052_t1161  
**Trigger phrase:** `gem with`  
**Raw text:** `"...you look at the gem with a faint glimmer of a form of a human inside the gem..."`  
**Judge notes:** "Gem with..." fires on mid-combat narration of an already-equipped
vestige item gaining significance, not a discovery. Weak trigger on common noun.  
**Diagnosis:** ENVIRONMENTAL_DISCOVERY_TRIGGER fires on
`\b(?:gold|silver)\s+(?:rings?|...)\s+(?:and|of|with|...)\b` or the `gem\s+with`
pattern. The item was already in the character's possession — this is description,
not discovery. Candidate signal: has_perception_buildup=True (it is, in this record),
but the item is previously obtained, not newly found.  
**Candidate fix:** The "gem with" pattern in ENVIRONMENTAL_DISCOVERY_TRIGGER
(`\b(?:jewelry|gems?|jewels?|...)\s+(?:of|with|sit|...)\b`) fires on "gem with a
faint glimmer". This pattern is too broad; it should require the gem to be stationary
in a scene (sitting, resting, lying) rather than being held/worn mid-action. Adding
a negative lookahead for motion verbs (holding, clutching, gripping) could help but
is non-trivial.

---

### 4. `condition_recovery_misread_as_knowledge`

**Record:** C1E062_t906  
**Trigger phrase:** `comes back to you`  
**Raw text:** `"As soon as your vision comes back to you and a breath of relief hits your form as suddenly you have control of your form."`  
**Judge notes:** "vision comes back to you" = recovering from incapacitation, not a
knowledge grant. Trigger ambiguous on recovery vs knowledge return.  
**Diagnosis:** KNOWLEDGE_GRANT_TRIGGER fires on `\b(?:it\s+)?comes\s+back\s+to\s+you\b`.
This pattern targets lore/memory returning ("it all comes back to you"), but "vision
comes back to you" is condition recovery (blindness ending). Signal: subject is
"vision", "consciousness", "control", "feeling" rather than lore/memory vocabulary.  
**Candidate fix:** Add subject-noun reject for condition-recovery subjects:
`\b(?:vision|consciousness|feeling|control|your\s+senses?)\s+(?:comes?|came)\s+back`.
Low false-positive risk but covers a narrow pattern.

---

### 5. `sale_price_misread_as_quest_offer`

**Record:** C1E099_t695  
**Trigger phrase:** `7,000 gold pieces`  
**Raw text:** `'"7,000 gold pieces."'` (NPC in buy/sell transaction)  
**Judge notes:** "7,000 gold pieces" in NPC voice during a buy/sell transaction is a
price quote, not a reward offer. Currency-in-NPC-voice routing fires too aggressively.  
**Diagnosis:** The bare currency pattern `\b\d+(?:,\d{3})*\s+gold\s+pieces\b` fires
in MATERIAL_LOOT_TRIGGER; NPC voice routing sends it to QUEST_OFFER. The preceding
context (turns 694) has "How much? Come on, give it to me." — strong price-negotiation
signal. The party is buying (DIRECTION_OUT), not receiving.  
**Candidate fix:** Extend DISCOURSE_DIRECTION_OUT or add a buy/sell context check:
if preceding 3–5 turns contain price-negotiation vocabulary ("how much", "cost",
"price", "buy", "purchase") → reject NPC currency mention as price quote.
Risk: some genuine QUEST_OFFER records might also have negotiation context.

---

### 6. `hostile_npc_action_misread`

**Record:** C2E022_t238  
**Trigger phrase:** `rifling through`  
**Raw text:** `"He goes and drags him back a little bit, begins rifling through whatever it might have had, and looks over right at Frumpkin."`  
**Judge notes:** "rifling through" fires on enemy/hostile NPC looting bodies and
throwing a trident. Not a reward to the party.  
**Diagnosis:** MATERIAL_LOOT_TRIGGER fires on `\brifling\s+through\b`. The actor is
a hostile NPC (merrow/gnoll), not Matt narrating party loot. `is_in_npc_voice` is
True (routed to QUEST_OFFER), but this is hostile-actor action narrated by Matt
in his own description (not quoted NPC speech). The trigger should require a
party-relevant receiver.  
**Candidate fix:** The `rifling through` pattern needs actor identification. Could
check the sentence subject: if subject is third-person pronoun ("he", "she", "it",
"they") with no party-member named → potentially hostile. High complexity;
subject extraction is beyond regex scope.

---

### 7. `awareness_phrase_misread_as_knowledge`

**Record:** C2E022_t947  
**Trigger phrase:** `you're aware of`  
**Raw text:** `"Okay, so as you get up on land, you focus and looking around side-to-side, make sure that you're aware of everything around you and get ready to defend and deflect."`  
**Judge notes:** "make sure you're aware of everything around you" is generic
combat-stance description, not specific information being granted.  
**Diagnosis:** KNOWLEDGE_GRANT_TRIGGER fires on
`\byou\'?re\s+(?:not\s+entirely\s+certain|aware\s+of|reminded\s+of|filled\s+with)\b`.
The `aware\s+of` branch is too broad: "be aware of your surroundings" is generic
vigilance, not information delivery. Distinguishing signal: the object of "aware of"
is a vague pronoun or plural ("everything", "anything") vs. a specific named thing
("the cultist symbol", "the trap mechanism").  
**Candidate fix:** Add reject when "aware of" is followed by vague indefinite object:
`you're\s+aware\s+of\s+(?:everything|anything|all|what's|what\s+is)\b`.
Low false-positive risk; specific-object "aware of" grants would not match.

---

## Phase 4 gate decision

Per Phase 3 operating rules, these 7 singletons are deferred. Phase 4 gate-set
construction will determine whether any of these patterns appear in held-out data
at sufficient frequency to warrant patches. Singleton families that do not recur
in Phase 4 held-out data are documented as known limitations in the findings doc.

**Phase 3 final state:**
- Strict precision: 21/31 = 67.7%
- Total emitted (hand-sample): 31
- Families cleared: donor_read_misread_as_npc, uncertainty_misread_as_knowledge,
  idiom_ill_give_you_that, rules_adjudication_negation,
  rules_adjudication_mechanic_explanation
- Retention regressions: 0
- Singletons deferred: 7 (listed above)
