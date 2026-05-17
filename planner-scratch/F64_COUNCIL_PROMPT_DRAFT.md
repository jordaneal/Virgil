# S80 Council Prompt — F-64 Doctrine Anchoring Pressure-Test

**Dispatch target:** Three-way external review (Oracle / GPT / Gemini) on planner-side independent structural analysis. Ready for operator dispatch.
**Planner walk reference:** `planner-scratch/F64_ANCHORING_WALK.md` (S79 deliverable).
**Discipline:** Third Planner-Lead-Architecture Discipline anchor instance — convergent-enthusiasm guard applies. If your read converges with planner's lean (Outcome 2: split into F-64 + §77.1), pressure-test before agreeing. Independent structural analysis required; do not synthesize from planner's framing without your own walk first.

---

## Context for council

The Virgil D&D bot has been carrying a doctrine candidate **§F-64 — Narration-commit gap** since session S53 (~25 sessions ago). FAILURES.md status: CANDIDATE-WITH-FIVE-INSTANCES. Anchoring was deferred per FAILURES.md to "N-3.1 ship — the right surface to anchor the doctrine because the architecture being designed IS the structural rule the candidate names." N-3.1 folded into Inversion v0 per S70 §11.4 lock; Inversion v0 Phase 3a (S73) + §1b.1 (S77) + Phase 3b (S78) have shipped without F-64 anchoring landing.

S78 live-verify surfaced 6 additional candidate instances; the planner's S79 walk reduces those to 4 in-cluster instances after two reclassifications (N-1 over-firing → N-1 tuning surface; loot_drop_llm misfire → parser-vocabulary-overlap surface). Adjusted cluster: **9 instances** total.

Operator's S78 handoff filed S79 as priority decision: F-64 anchoring walk OR S69 Causality Engine. S79 takes the F-64 path. The walk's output is planner's lean for council pressure-test, not lock.

**Read the planner walk first** (`F64_ANCHORING_WALK.md`). Then this prompt asks specific pressure-test questions that may reframe the walk's conclusions.

---

## Current F-64 candidate framing (from FAILURES.md)

> "Narration-commit gap as systemic contamination surface — when narration claims a state mutation that the engine does not deterministically enforce, the claimed state drifts across turns. Engine must enforce state mutations either at narration-detection time (deterministic parser feeding single-writer) or via operator-driven slash gate; LLM narration alone is not a structural state-mutation signal."

---

## Walk's lean (Outcome 2 — split into two doctrines)

**§F-64 anchored at current framing** for the engine-side enforcement gap (8 of 9 instances fit cleanly):
- Architectural response: §1a.x parser + §1b/§1b.1 suggester pattern.
- Sister to §76 (one-way narration→claim-without-write vs §76's two-way write-and-re-read loop).

**§77.1 NEW sub-clause anchored** for the instruction-side compliance-failure mode (instance #11 + S77 `clarification_in_fiction_compliance_failure` telemetry as prototype):
- Anchors as sub-clause of §77 (atmospheric continuity, two-layer enforcement).
- Architectural response: per-directive compliance-detection telemetry events + prompt-iteration data feedback loop.

Walk's planner-side confidence: HIGH on split / MEDIUM-HIGH on §77.1 placement / MEDIUM on F-64 anchor language.

---

## Pressure-test questions

### Q1 — Framing test independence

**Pressure-test the framing-test outcome.** Without reading the walk's framing analysis first, walk the 9 instances independently:

Group A (5 anchored): S53 §1.F.c NPC was_new / S63 §1.F.e consequence-DM-side / S66 F-031 quest delivery silent inventory / S66 F-035 loot evaporation / S68 N-4 NPC pronoun drift.

Group B (4 S78 candidates): N-4 descriptor→name gap / F-44 NPC-axis bleed (Mara at both bakeries) / LLM price invention + cross-turn inconsistency / central thread MUST/MUST-NOT compliance failure.

For each instance, ask: does the current F-64 framing fit cleanly? Where does it strain? Where does it fail?

Then surface YOUR framing-test outcome. If yours matches the walk's lean (8 fit, instance #11 doesn't), pressure-test why both you and the planner converged. If yours diverges, name the divergence and the reasoning behind it.

### Q2 — Is there a unified framing the walk missed?

Walk concluded the empirical evidence justifies a split (F-64 + §77.1). The strongest counter-argument worth pressure-testing: a single doctrine with two closure-shape sub-clauses (§F-64.1 engine-side surface + §F-64.2 compliance-detection telemetry) instead of two separately-anchored doctrines.

Is the split necessary, or is the §F-64.1/§F-64.2 sub-clause structure stronger? Specifically:
- Doctrine numbering simpler (one root, two sub-clauses) vs (two siblings under different parents).
- Future ships citing the doctrine can cross-reference closure shape without doctrine-spanning navigation.
- §76's precedent (§76.1 rate-unlimited + §76.2 verbatim re-injection sub-clauses) supports the unified shape.

Argue both sides; surface which the empirical instance evidence favors.

### Q3 — §77.1 placement vs alternatives

Walk recommends §77.1 (sub-clause of atmospheric continuity). Pressure-test against:
- **§F-08-extension** — rejected by walk because §F-08 is closed historical incident, not anchored doctrine; perpetuating metaphorical relationship to closed surface is doctrinal debt.
- **New top-level §82** — rejected by walk as overweighting (doctrine fits within §77's two-layer framing).
- **Sub-clause of §1a.x** — not considered by walk. §1a.x covers narration-detection-as-deterministic-gate; compliance-failure-detection is structurally adjacent. Worth testing.
- **Co-anchored with §F-64 itself** as §F-64.2 — see Q2.

What's the strongest doctrinal home for the compliance-failure-detection doctrine? Does §77's two-layer framing actually absorb the new sub-clause cleanly, or does the new doctrine deserve a separate anchor?

### Q4 — Instance reclassification audit

Walk reclassified two S78 candidates out of the F-64 cluster:

**Instance #8 (N-1 over-firing on price quotes/memory refs):** walk argues this is N-1 parser tuning (extractor over-claims; operator burden to filter), not F-64 (narration claims state engine doesn't enforce). Counter-argument: the N-1 hint IS a state-mutation suggestion the operator pastes; over-claiming creates an F-64-shape gap when operator over-pastes. Pressure-test the reclassification.

**Instance #10 (loot_drop_llm semantic misfire):** walk argues this is Phase 3b parser-vocabulary-overlap (parser false-positive), not F-64. Counter-argument: the false-positive parser fire IS an LLM-claimed-state surfacing as a clarification card; the engine responding to a wrongly-classified narration claim is structurally F-64-adjacent. Pressure-test.

Are the reclassifications correct, or does the F-64 cluster legitimately absorb these surfaces?

### Q5 — Anchoring readiness vs further deferral

Walk argues deferral (Outcome 3) is rejectable — F-64 has held candidate status 25+ sessions; the empirical evidence has only grown; the original "wait for N-3.1" rationale has dissolved (N-3.1 folded into Inversion v0 which has shipped without anchoring).

Counter-argument worth pressure-testing: anchoring NOW commits the framing pre-Causality-Engine ship (S69 Path A Phase 3). Causality Engine's architecture may surface F-64-shape instances that reshape the doctrine. Deferring until after S69 lets the doctrine absorb causality-side evidence before locking.

Is anchoring at S81 (post-walk + post-council) premature, or is the empirical evidence stable enough that S69 won't materially shift the framing?

### Q6 — Compliance-detection telemetry naming convention

Walk surfaces an implementation-detail question without strong lean: should §77.1's compliance-detection telemetry be **per-directive-named events** (high specificity; `clarification_in_fiction_compliance_failure`, `central_thread_compliance_failure`, `combat_narration_compliance_failure`, …) or a **generic event with directive-id payload** (`directive_compliance_failure { directive_id: ... }`)?

S77 shipped the per-directive-named shape. Future ships could either continue the pattern (telemetry surface grows with each new directive) or migrate to generic (simpler dashboard, but loses semantic specificity).

What's the doctrinal preference? Is this an architectural decision the §77.1 anchor should constrain, or implementation-detail the anchor leaves to per-directive ships?

---

## Anti-conformity protocol

Per WWC Planner-Lead-Architecture Discipline Rule 4 (S79 third anchor instance):

**If your read converges with the walk's lean** — Outcome 2 (split), §77.1 placement, HIGH/MEDIUM-HIGH/MEDIUM confidence shape — flag the convergence explicitly. Pressure-test WHY you and the planner converged. Independent structural analysis on which instances fit which framing should produce slightly different lean strengths or framings; if it doesn't, surface the question of whether your analysis is anchored on planner's framing or independent.

**If your read diverges** — name the divergence cleanly. Different outcome (1 or 3)? Different framing? Different doctrine placement? Different instance classification? Operator dispatches your divergence as the load-bearing input.

The walk is the planner's hypothesis. The council's job is to pressure-test it, not to confirm it. If pressure-test produces convergence, the doctrine anchors at S81 with confidence; if it produces divergence, S80 escalates to operator + Oracle for resolution before S81 implementation.

---

## What S80 produces

- Per-council-member structural analysis on the 6 pressure-test questions.
- Convergence-or-divergence summary across the three councils.
- Operator + Oracle lock on:
  - F-64 anchoring outcome (1/2/3 or council-surfaced 4th option).
  - §77.1 placement (or alternative).
  - Closure-pattern sub-clause structure.
  - Instance reclassification confirmation or override.
- Anchoring language draft for S81 implementation.

S81 implements the locked anchoring: DOCTRINE.md amendments, FAILURES.md instance-cluster update, any prototype-pattern telemetry events that aren't already shipped at S77.
