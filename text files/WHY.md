

---

## Why Quest Layer v0.1 dropped cosine-similarity paste-detection (S57)

Quest Layer v0 shipped operator-paste-detection-via-cosine-similarity as an auxiliary UX layer on top of canonical `/quest offer accept <id>` slash. Reading-3 framing: canonical slash is the deterministic §1b gate; cosine-similarity is auxiliary ergonomics that lets operator paste the offer dialogue directly without typing the slash.

Live verify said: "too mechanical." The paste-detection logged every match with similarity scores; the gate became visible during in-fiction narration at exactly the wrong moment. Auxiliary surface defeated the validated-suggester pattern's design intent — gates should be invisible when operating correctly, visible only when refused or failed.

S57 patch dropped cosine-similarity entirely. `/quest offer accept <id>` slash is the sole §1b gate at Quest Layer v0.1. LLM renders offers organically when operator accepts.

**Why the drop crystallized doctrine:** §1b anchored across three instances at v0.1 ship (Track 6 #5.1, S41 NPC State-Sync, Quest Layer v0.1). All three: canonical-slash deterministic gate, no calibration-bound validator anywhere. The drop named "no calibration-bound auxiliary" as infrastructural discipline. Composition Layer v0 inherited this directly — shipped Reading-2-direct with no cosine-similarity layer at all. N-10 Canon Bootstrap Bot inherited it too. By the time the §1b sub-pattern observation landed in S67 audit ("deterministic-validator suggester" as the canonical §1b shape), five instances had operated cleanly without calibration drift.

The lesson stays: when a fix can be expressed as deterministic structured-signal gate OR as calibration-bound proxy (cosine, regex over open prose, LLM-classifier confidence threshold), doctrinal cleanliness prefers the structured-signal gate even when the proxy is operationally lighter. The proxy weakens the §1b gate exactly where the gate needs to be load-bearing.

---

## Why Composition Layer kept `current_act_id` on `dnd_scene_state` (S61)

Composition Layer v0 had three candidate locations for the scene→act anchor: (a) `dnd_scene_state.current_act_id` mirroring `current_location_id`; (b) JSON column on `dnd_quests`; (c) derived-at-read-time from quest+turn-counter.

(a) locked. R6 critical recon clean: Scene Lifecycle v1's compression machinery writes only in-memory counter + LLM-side directive injection + three narrative buffers — no structural columns on `dnd_scene_state`. Proposed `current_act_id` would persist across compression by structural inheritance. The foundational anchor-persistence assumption held without additional code.

**Why this matters doctrinally:** Composition Layer needed the property "scene state survives Scene Lifecycle compression turns." (b) on `dnd_quests` would have that property too. (c) derived-at-read-time would as well. What made (a) the lock-worthy candidate: it mirrors `current_location_id`'s existing pattern, single-writer set_current_act folds into existing patterns rather than adds a sibling writer, and the read-path is the simplest possible (one column lookup). No new §17 amendment-pressure, no new derivation logic, no new audit shape.

The decision pattern: when multiple candidates satisfy load-bearing properties, prefer the candidate that minimizes new architectural surface. (a) added zero new patterns; (b)/(c) each added one.

---

## Why N-10 Canon Bootstrap Bot ships before Causality Engine

S69 Causality Engine spec locked post-Session-2, Phase 3 implementation paused. N-10 dispatched immediately. Sequence question: why N-10 first?

The convergent review's framing crystallized at this decision point. Operator confirmed option-3 authoring (will provide premise, will approve cards, will NOT hand-author skeleton.md). Every downstream architectural layer (Quest Layer dispatcher NPCs, Composition Layer acts, Causality Engine faction goals) depends on authored canon existing. If Causality Engine ships into thin authored canon, the world-pressure architecture has nothing to push with — atmospheric pressure renders against empty faction state; faction tick predicates evaluate against zero engagement signals; pressure directive returns quiet baseline forever.

N-10 closes the load-bearing prerequisite: authored canon volume. With N-10 shipped, Causality Engine has factions to tick, dispatcher NPCs to involve in pressure narration, quests to evaluate engagement against. The fun-delta ship (Causality Engine making inaction observable) requires the canon-volume ship (N-10 producing the substrate) to operate.

**Why this isn't pre-coupling:** N-10 doesn't know about Causality Engine specifically. It authors factions because the operator's option-3 constraint requires bot-authored canon for every downstream layer that reads from skeleton.md. N-10 would still ship as load-bearing even if Causality Engine were filed-forward forever — N-10 also closes Quest Layer dispatcher-NPC gap (campaign 17 companion-filter surfaced this in S62) and provides the structured canon Bootstrap-flow already proved operator approves cards reliably.

The sequencing decision: ship the prerequisite when the dependency is named, not when the dependent ship dispatches. N-10's prerequisite status was named at S62 + the operator's "I'm not writing anything" confirmation; dispatching it then rather than after S69 was the structural call.

---

## Why §1b sub-pattern observation stays in running-list (S67 audit lean B)

S67 §76 audit surfaced Code's recommendation to formally anchor the "deterministic-validator suggester" sub-pattern as a §1b sub-anchor (A) or keep as running-list observation in DOCTRINE.md instance list (B). Five §1b instances at S67 (Track 6 #5.1, S41 NPC State-Sync, Quest Layer v0.1, Composition Layer v0, N-10). Pattern: canonical operator slash gate + deterministic-validator (parser, file-write integrity check, FK resolve, schema validation), no calibration-bound auxiliary.

(B) running-list footnote held. Reasoning:

**(A) formal sub-anchoring would over-formalize what's already implicit.** §1b's existing text describes the validated-suggester pattern as "bot proposes, deterministic gate validates, DM approves, system executes." The five instances all operate under this framing without explicit sub-pattern naming. Formalizing "deterministic-validator" as §1b.1 implies §1b.2 should be the alternative (calibration-bound validator) — but the project actively rejected that alternative in S57 cosine drop. The sub-anchor would name something the project doesn't intend to support as a valid pattern.

**(A) invites scope creep on future ships.** Sub-anchoring creates the question "does this ship anchor a new §1b.N?" for every future §1b instance. The observation-footnote keeps the pattern visible (DOCTRINE.md instance list is a real surface future planners read) without inviting taxonomy expansion.

**Operator + Oracle level for (A); planner + Code level for (B).** Formal doctrine anchoring is operator's call. The observation-footnote is planner discipline — keep the instance list current, name the cross-instance pattern in comments, let formal anchoring earn its slot only when the pattern's existence is empirically contested.

If a sixth §1b instance ships with a different validator shape (LLM-classifier-confidence-threshold-as-gate, for example), that's the event that justifies revisiting (A). Until then, running-list observation is the load-bearing-but-not-load-formalized state.

---

## Why narration-commit-gap doctrine candidate (F-64) anchors at N-3.1, not earlier

F-64 candidate at five instances post-S68 (S53, S63, F-031, F-035, N-4 pronoun lock — narration claimed state change, engine didn't enforce, state drifted). The doctrine framing is empirically grounded. Why not anchor formally?

**Anchoring waits for the surface that demonstrates the architectural fix.** F-64 names the failure pattern; doctrine anchoring names both the pattern and the structural response. The five instances closed each individually via different fix shapes (drop the activity-signal, fix the writer's empty-string bug, auto-claim via verb-vocabulary detection, lock the pronoun column at first occurrence). No single architectural primitive has shipped that demonstrates the doctrine's structural response to the pattern.

N-3.1 (commitment-tracking multi-spec) is that primitive. The spec ships a `dnd_npc_commitments` table + narration-detection extractor + structured-signal directive that injects prior commitments back into prompt context. The architectural response: narration claims drive engine writes via deterministic parsers; engine reads back to anti-gaslight narration. That's the structural fix the F-64 doctrine framing describes in abstract — N-3.1 ships it concrete.

Anchoring at N-3.1 ship gives the doctrine both the failure pattern AND the architectural response, in operator-readable form. Anchoring before N-3.1 would name the pattern without naming the response, which is the failure mode §F-23 anchored ("first spec proposed sequenced appendix without earned slot").

**If Inversion v0 folds N-3.1 per §11.4 candidate**, the doctrine anchoring walk happens at Inversion v0 lock, not at a separate N-3.1 spec session. Same outcome via different surface; the doctrine still earns its anchor at the ship that demonstrates the structural response.
