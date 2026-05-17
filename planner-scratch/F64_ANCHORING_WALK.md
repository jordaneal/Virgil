# §F-64 Doctrine Anchoring Walk — S79 Phase 1

**Status:** Planner-side independent structural analysis. No code, no canonical-doc amendments. Output: lean on anchoring decision + open questions for S80 council pressure-test.
**Date:** 2026-05-16
**Discipline:** Third Planner-Lead-Architecture Discipline anchor instance (S77 first / S78 second / S79 third). Walk-before-council per WWC Rule 1.

---

## §0 — Walk framing

F-64 candidate has carried "CANDIDATE-WITH-FIVE-INSTANCES" status across S53–S68. Doctrine anchoring deferred per FAILURES.md to N-3.1 ship — "the right surface to anchor the doctrine because the architecture being designed IS the structural rule the candidate names." N-3.1 was folded into Inversion v0 per S70 §11.4 lock; Inversion v0 Phase 3a (S73) + §1b.1 (S77) + Phase 3b (S78) have shipped without F-64 anchoring landing.

S78 live-verify surfaced 6 additional candidate instances that compound the cluster. Operator (S78 handoff): "F-64 anchoring walk OR S69 Causality Engine" filed as S79 priority decision. S79 takes the F-64 path.

**The walk's load-bearing question:** does the current F-64 framing absorb all 11+ instances cleanly, or does the empirical surface area now justify a different anchoring shape?

---

## §1 — Instance inventory

### Group A — Original 5 anchored instances (per FAILURES.md)

| # | Session | Surface | Narration claim | Engine non-enforcement | Fix shape | Closure status |
|---|---|---|---|---|---|---|
| 1 | S53 | §1.F.c NPC was_new | "NPC Marla appears" (LLM invents to fill space) | Activity-signal reset gave LLM perverse-incentive to keep inventing | Drop §1.F.c reset from `_extract_and_persist_world` | CLOSED |
| 2 | S63 | §1.F.e consequence-DM-side | (Would have been: consequence captured by DM-side extraction) | Activity-signal reset would have triggered identical loop | Pre-emptive spec drop (never wired) | CLOSED |
| 3 | S66 | F-031 quest delivery | "You receive the reward" | `add_item(campaign, '', ...)` returned `'invalid'` silently; no inventory write | Empty-string sentinel + PARTY_STASH_BUCKET + truthful aside | CLOSED |
| 4 | S66 | F-035 loot evaporation | "Coins and items spill from the goblin" | Operator burden to type slash commands; no auto-claim | Verb-vocabulary deterministic parser + auto-claim | CLOSED |
| 5 | S68 | N-4 NPC pronoun drift | "She speaks" (turn 1) then "he speaks" (turn 2) | No engine-side pronoun anchor; LLM re-rolled per turn | `dnd_npcs.pronouns` column + `npc_pronouns_set` + first-occurrence lock + HARD STOP RULE 7 | CLOSED (with v1.x gap surfaced at S78 — see #6) |

**Group A pattern:** *engine-side enforcement gap.* The engine LACKED a structural surface to track or write the state the narration was claiming. Closure shape: build the engine-side surface (column, parser, writer) and route narration through it.

### Group B — S78 live-verify candidate instances (6 filed)

| # | Surface | Narration claim | Engine non-enforcement | Doctrinal nearest |
|---|---|---|---|---|
| 6 | N-4 descriptor→name gap | "the baker" (he/him) turn 1 → "Mara" (she/her) turn 2 | N-4 keys on names; descriptor-only narration creates no NPC row; named NPC turn 2 is fresh entity | F-64 + N-4 v1.x extension |
| 7 | F-44 NPC-axis bleed (Mara at both bakeries) | Same NPC name at structurally distinct locations | Chroma RELEVANT PAST EVENTS retrieval is campaign-scoped, not location-scoped; NPC extractor name-match is global | §F-44 sibling (chroma bleed at NPC axis) |
| 8 | N-1 over-firing on price quotes/memory refs | LLM narrates "Mara remembers the two gold you handed her" → N-1 fires `!game coin -2gp` again | Verb-gate ('pockets'/'remembers' co-occurrence) didn't suppress; no transaction happened this turn | N-1 v1.x tuning (related to F-64 via N-1's lineage) |
| 9 | LLM price invention + cross-turn inconsistency | "1gp per loaf" turn 1 → "3gp per loaf" turn 2 with no operator action | No engine-side price anchor for any NPC/item pair | F-64 + N-3.1 / price-commitment-tracking surface (was the original "sixth instance" candidate) |
| 10 | loot_drop_llm semantic misfire | LLM narrates "Mara pockets the gold... slides loaves across counter" → loot_drop_llm parser flags as loot reveal | Parser-vocabulary overlap ('pockets' in both loot + transaction sets); transaction NPC match failed (Mara not at Bishop's Bakery's current_location_id) | Phase 3b parser-tuning surface; NOT F-64 (this is parser false-positive, not narration-commit gap) |
| 11 | §F-08-a central thread compliance failure | LLM narrates campaign-arc exposition (mine collapse + Grahn) through unrelated NPC despite directive saying "Do NOT name or restate the thread" | Directive negative-frames behavior; LLM violates it; no detection or enforcement | §77 (atmospheric continuity instruction-side enforcement layer); compliance-failure detection surface |

**Group B pattern:** mixed. Some instances (#6, #9) fit Group A's "engine-side enforcement gap" pattern. Others (#11) are a structurally distinct pattern — LLM ignoring instruction-side discipline despite the engine having the directive in place. Still others (#10) are parser-side false-positives unrelated to F-64. And #7 is an §F-44 sibling (chroma bleed) that's only tangentially F-64.

### Walk finding from inventory

**Instance #10 (loot_drop_llm misfire) is NOT an F-64 instance.** It's a parser-vocabulary cross-domain overlap surface. Filing it as F-64 is misclassification; it belongs in the §1a.x parser-tuning queue. Remove from the F-64 cluster.

**Instance #7 (NPC-axis chroma bleed) is a hybrid.** It's an §F-44 sibling structurally (chroma retrieval scoping gap), but the LLM USING the bled-in name to narrate "Mara at Bishop's Bakery" is an F-64-shape behavior (LLM claims state — that Mara is here — which the engine doesn't enforce). Counts in F-64 cluster as a manifestation; closure shape is §F-44-side (location-scoped chroma + location-aware NPC matching).

**Instance #8 (N-1 over-firing) is a sibling to F-64, not an instance.** N-1 emits hints that an operator would paste; the over-fire is a parser tuning issue. It does NOT fit "narration claims state, engine doesn't enforce." It's "extractor over-claims; operator burden to filter." Different shape. Remove from cluster.

**Adjusted cluster: 5 anchored (Group A) + 4 candidate (Group B without #8 and #10):**

Anchored:
1. S53 §1.F.c NPC was_new
2. S63 §1.F.e consequence-DM-side
3. S66 F-031 quest delivery
4. S66 F-035 loot evaporation
5. S68 N-4 NPC pronoun drift

Candidate (post-S78 surfaces):
6. N-4 descriptor→name gap
7. F-44 NPC-axis bleed (hybrid; counts as manifestation)
9. LLM price invention + cross-turn inconsistency
11. §F-08-a central thread compliance failure

**Adjusted total: 9 instances** (5 anchored + 4 candidate). The "sixth instance threshold" is met cleanly with #6 and #9 alone (both fit Group A pattern); #7 and #11 add structurally-distinct shapes that complicate the framing.

---

## §2 — Framing test

### Current F-64 candidate framing (per FAILURES.md)

> "Narration-commit gap as systemic contamination surface — when narration claims a state mutation that the engine does not deterministically enforce, the claimed state drifts across turns. Engine must enforce state mutations either at narration-detection time (deterministic parser feeding single-writer) or via operator-driven slash gate; LLM narration alone is not a structural state-mutation signal."

### Walk per instance

| # | Instance | Fits current framing cleanly? | Strain | Notes |
|---|---|---|---|---|
| 1 | S53 NPC was_new | YES | none | Canonical case — extractor caught LLM-invented NPC; engine reset on it; loop tightened. Fix removed the reset. |
| 2 | S63 consequence-DM-side | YES | none | Same shape, prevented before wired. |
| 3 | S66 F-031 quest delivery | YES | none | Reward narrated, inventory silent — perfect fit. |
| 4 | S66 F-035 loot evaporation | YES | none | Loot narrated, engine waited for slash — fit. |
| 5 | S68 N-4 pronoun drift | YES | none | Pronoun narrated, no engine anchor — fit. |
| 6 | N-4 descriptor→name gap | YES | mild | Same shape as #5 across coreference boundary. |
| 7 | F-44 NPC-axis bleed | PARTIAL | moderate | Engine has the NPC (matched by name globally); LLM narrates her at a new location. The "engine non-enforcement" is the location-scoping gap, not absence of the surface entirely. The F-64 framing fits as "engine doesn't enforce location-binding" but stretches the framing. |
| 9 | LLM price invention | YES | none | Price narrated 1gp→3gp; engine has no price column — canonical fit. |
| 11 | §F-08-a central thread compliance | NO | severe | The engine DOES have an enforcement surface — the central_thread_directive in the prompt explicitly says "Do NOT name or restate." The failure is LLM directive-compliance, not engine non-enforcement. F-64's framing reads backwards here: the engine IS instructing the LLM; the LLM is ignoring it. This is instruction-side enforcement failure (§77 layer), not engine-side enforcement gap. |

### Framing-test outcome

**Current F-64 framing absorbs 8 of 9 instances** (1–6, 7 partial, 9). Instance #11 (§F-08-a) does NOT fit — it's structurally inverted: engine has the directive surface, LLM violates compliance.

This means F-64's current framing names *one* failure mode (engine-side enforcement gap), and the S78 cluster surfaces *a second related-but-distinct* failure mode (instruction-side compliance failure).

### Alternative framings tested

**F-64A (compliance-failure-only):** "LLM narration fails MUST/MUST-NOT directive compliance; engine state diverges from narration claim."
- Fits instance #11 cleanly.
- Does NOT fit instances 1–6 / 9 — those failures have no engine-side directive that the LLM was violating; the engine simply lacked the enforcement surface.
- Verdict: this framing is too narrow for the cluster.

**F-64B (engine-narration sync, broad):** "Engine state and narration content require structural synchronization; absent synchronization, drift compounds."
- Absorbs all instances by construction.
- Too broad to anchor — gives no architectural guidance on closure shape. Doctrine should constrain choice, not enumerate failure space.
- Verdict: defensible as framing-of-framings (umbrella), but loses operational value.

**F-64 (current) + new §F-08-extension (compliance-failure surface):** Two anchored doctrines that cover the cluster between them.
- F-64 (engine-side enforcement gap): instances 1–7, 9.
- §F-08-extension (LLM instruction-compliance failure): instance 11. Could also absorb prior §F-08 historical Layer 2 drift framing as the original instance.
- Closure patterns diverge cleanly: F-64 closure is "build the engine-side surface"; §F-08-extension closure is "compliance-detection telemetry + prompt-tuning feedback loop."
- Verdict: best fit for the empirical evidence. Names two architecturally distinct failure modes that both belong to the LLM-narration-vs-engine-state problem space.

### Walk lean on framing

**Split into two anchored doctrines.** F-64 anchors at current framing for engine-side enforcement gap (8 instances). New companion doctrine — provisional name **§F-08.x** or **§77.1** depending on doctrine-relationship resolution (§3 below) — anchors the LLM instruction-compliance failure mode (instance #11 + the §1b.1 `clarification_in_fiction_compliance_failure` mechanism already shipped at S77 as the prototypical engine response).

The S77 compliance-failure-detection-telemetry pattern IS the architectural response to the new doctrine; it ships as the closure shape's prototype. Future MUST/MUST-NOT directives earn parallel compliance-detection events at their respective ships.

---

## §3 — Architectural relationship map

### §F-08 — Layer 2 narration drift

**Status check (walk finding):** §F-08 is NOT an anchored DOCTRINE.md section. It was filed in FAILURES at S9 ("F-07 hallucinated slash + F-08 Layer 2 drift") and closed at S10 via gpt-oss-120b model swap. The "Layer 2 drift" phrase has been used loosely in subsequent docs as a metaphor for LLM narration discipline failures, but the original §F-08 is a closed historical incident, not active doctrine.

The FAILURES.md text "Sister to §F-08 (Layer 2 narration drift — NPCs never commit)" recharacterizes §F-08 as "NPCs never commit." That's not what the original F-08 was — F-08 was hallucinated slash commands in LLM output. The recharacterization is fresh framing for the walk, not historical fidelity.

**Walk implication:** S79 should treat §F-08 as historical reference, not load-bearing anchor for F-64 relationships. If the walk anchors a new compliance-failure doctrine, naming it "§F-08-extension" or "§F-08.x" perpetuates a metaphorical relationship to a closed incident. **Recommended:** the new doctrine takes a fresh number (e.g., §77.1 as sub-clause of §77, or new top-level §82).

### §76 — Recursive-hallucination memory loop

F-64 and §76 are doctrinally adjacent but distinct. §76 names the **two-way** loop: LLM writes persisted state, engine re-reads it, LLM-writes-drift-influenced-output compound. F-64 names the **one-way** gap: LLM claims state, engine doesn't write, narration diverges from authority.

The §76 four-property test (LLM-writable + persisted + retrieved + narratively-inferential) doesn't apply to F-64 instances. F-64 instances have the engine NOT writing — so the LLM-writable property is FALSE in F-64. The two failure modes coexist; a single surface could hit both (e.g., chroma DM-stores at S72.2 was §76 6/6 + an F-64-shape contamination of past-narration into present-prompt).

**Walk implication:** F-64 anchors as **sister to §76, not sub-clause**. Both name LLM-narration-vs-engine-state drift; §76 covers persistence + re-read direction; F-64 covers claim-without-write direction.

### §1a + §1a.x

§1a's strict reading: LLM never decides binding state. F-64 is the inverse — F-64 names what HAPPENS when LLM narration claims a binding state change in the absence of an enforcement surface.

§1a.x (S73 anchored) names the architecture that responds: closed-vocab parser + structured-signal co-occurrence + engine-side §17 writer. §1a.x is the structural CLOSURE for F-64's pattern.

**Walk implication:** F-64 is **the failure mode §1a.x's architecture addresses**. Anchoring F-64 names what the §1a.x parser-and-writer pattern protects against. This is doctrine-pair shape (failure-mode doctrine + architectural-response doctrine), parallel to §F-08↔§F-07-fix or §76↔§17 / Path A retirement.

### §1b + §1b.1

§1b validated-suggester pattern is the architectural response when §1a.x detects ambiguity. §1b.1 (S77 anchored) extends with clarification handshake when the ambiguity needs operator disambiguation.

The §1b.1 `clarification_in_fiction_compliance_failure` telemetry event (S77) is structurally the **prototype** of the new compliance-failure-detection doctrine. It already exists in code. The walk's "new doctrine" anchors what §1b.1 already empirically practices.

**Walk implication:** F-64 split lands as F-64 (engine-side, addressed by §1a.x + §1b + §1b.1) + new compliance-doctrine (instruction-side, addressed by compliance-detection-telemetry + prompt iteration). Both share the LLM-narration-vs-engine-state root concern.

### §77 — Atmospheric continuity (instruction-side enforcement)

**Walk's key finding for §77 relationship.** §77 names two-layer enforcement: instruction-side MUST/MUST-NOT clauses + information-side context-block suppression. The S78 §F-08-a finding (central thread compliance failure) is structurally an **§77 instruction-side compliance failure** — the layer §77 already names as load-bearing.

This means the new compliance-doctrine doesn't need a fresh top-level number. It anchors cleanly as **§77.1 — Instruction-side compliance-failure detection**. §77 names the enforcement layer; §77.1 names what happens when the layer fails empirically and the architectural response (detection-telemetry + iteration).

§77.1 placement parallel to §76.1/§76.2 sub-numbering precedent (S72.2 anchored two sub-clauses to §76). Anchoring under §77 preserves §77's two-layer framing while extending with the compliance-failure surface.

**Walk implication:** new doctrine anchors as **§77.1**, not §F-08-extension and not new top-level §82.

### §78 — Four-layer mode-transition state-reset

Tangential to F-64. §78 covers combat-mode-transition state cleanup; the closeout narration could in principle claim state the engine didn't write, surfacing as F-64. But no observed §78-shape F-64 instance has surfaced. **No active relationship.**

### §F-44 — Chroma bleed (S25 #6)

§F-44 has the original location-axis instance closed at S25. S78 instance #7 (Mara at both bakeries) is the NPC-axis sibling. F-44 is independently anchored (chroma scoping); the NPC-axis closure may anchor as §F-44.1 sub-clause if it merits its own architectural response. The F-64-shape behavior in instance #7 (LLM narrates Mara at new location based on chroma-bled context) is downstream of the §F-44 gap.

**Walk implication:** instance #7 is an F-44 instance with an F-64-shape manifestation. Closure is §F-44-side (location-scoped chroma + location-aware NPC matching). It counts in the F-64 cluster as evidence the pattern recurs across substrates but its architectural address is §F-44.

### Doctrine-relationship summary

```
                              §1a (LLM never decides binding state — root invariant)
                              │
                ┌─────────────┼─────────────┐
                │             │             │
            §1a.x         §76          §F-44 (chroma bleed)
       (narration-      (LLM-write           │
        detection         loop)              │
        parser as                            │
        determ. gate)                        │
                │                            │
                ↓                            ↓
          ┌─────────────┐              §F-44.1 (NPC-axis;
          │             │               candidate)
        §1b            §1b.1
    (suggester)    (clarification
                    handshake)
                                                  §77 (atmospheric continuity
                                                  ┌────── two-layer enforcement)
                                                  │
                                              §77.1 (instruction-side
                                              compliance-failure detection
                                              — NEW; absorbs §F-08-a + S77
                                              clarification_in_fiction_compliance_failure
                                              telemetry as prototype)


§F-64 (engine-side enforcement gap — narration claims state, engine doesn't enforce)
      — failure mode; §1a.x + §1b + §1b.1 are the architectural CLOSURE
      — sister to §76 (one-way vs two-way); cousin to §F-44 (substrate-level bleed)
```

---

## §4 — Closure pattern analysis

### Group A (5 anchored) closure pattern: engine-side surface construction

Each instance closed via building the engine-side surface that was missing:
- S53: dropped the LLM-extracted reset signal (engine stops listening to unreliable LLM claim).
- S63: pre-emptive same shape.
- S66 F-031: empty-string sentinel + party-stash bucket + truthful aside (engine acknowledges what it actually wrote).
- S66 F-035: deterministic parser + auto-claim (engine wires up writer for narrated-loot pattern).
- S68 N-4: pronoun column + first-occurrence lock writer + HARD STOP RULE 7 (engine acquires the anchor LLM was inventing fresh).

**Common pattern:** parser feeding single-writer that lives in §17 discipline + (optional) HARD STOP RULE for instruction-side reinforcement. §1a.x doctrine names this architecture.

### Group B (4 candidate) closure pattern: bifurcated

| # | Instance | Closure pattern |
|---|---|---|
| 6 | N-4 descriptor→name gap | Group A pattern: extend N-4 to alias descriptors to subsequent names; lock pronouns from descriptor at narration-detection time. Engine-side surface. |
| 7 | F-44 NPC-axis bleed | §F-44 closure pattern: location-scoped chroma retrieval + location-aware NPC name matching. Substrate-level filter, not new writer. |
| 9 | LLM price invention | Group A pattern: build engine-side price/economic anchor (column, single-writer, narration-detection parser). Either lightweight (cached LLM-quoted prices indexed by NPC+item) or heavyweight (N-3.1-shape economic commitment table). |
| 11 | §F-08-a central thread compliance | Compliance-failure-detection telemetry + prompt-iteration. NO engine-side surface to write; the surface IS the prompt directive that the LLM is ignoring. Closure pattern is instrumentation + iteration. |

**Walk finding:** Group A pattern handles 3 of 4 Group B instances (6, 7, 9 — with 7 going through §F-44 substrate-fix rather than fresh F-64 writer). Instance 11 requires a structurally different closure pattern.

**Conclusion:** F-64 has ONE closure pattern (engine-side surface) covering 8 of the 9 instances. The new compliance-doctrine (§77.1) has its own closure pattern (detection-telemetry + iteration). Splitting is justified by closure-pattern divergence, not just framing-test outcome.

The S77-shipped `clarification_in_fiction_compliance_failure` telemetry event already PROVES the closure pattern works empirically. S78 §F-08-a finding is the second-instance candidate for the same response shape (central thread compliance failure deserves its own detection event mirroring the §1b.1 prototype).

---

## §5 — Anchoring readiness lean

### Three outcomes per dispatch

**Outcome 1 — Anchor F-64 as top-level §F-64.** Current framing survives.
- Walk verdict: PARTIAL. Current framing fits 8 of 9 instances cleanly; instance #11 doesn't fit. Anchoring F-64 at current framing leaves instance #11 + future compliance-failure instances unhomed.
- Confidence in this outcome as sole resolution: **LOW**.

**Outcome 2 — Anchor F-64 split into F-64 + §77.1 (compliance-failure-detection).**
- Walk verdict: STRONGEST FIT. F-64 anchors at current framing (engine-side enforcement gap, 8 instances). §77.1 anchors as new sub-clause of §77 (instruction-side compliance-failure detection, instance #11 + S77 `clarification_in_fiction_compliance_failure` prototype + future MUST/MUST-NOT directives' compliance events).
- Closure-pattern divergence supports the split. §77 sub-numbering precedent (§76.1/§76.2 at S72.2) supports placement.
- Confidence: **HIGH** (planner-side). Council pressure-test may reframe.

**Outcome 3 — Defer F-64; close §77.1 compliance-failure only.**
- Walk verdict: REJECTABLE. F-64 has held CANDIDATE-WITH-5-INSTANCES status across 25+ sessions; deferral is the path-of-least-action but the empirical evidence has only grown. The "wait for N-3.1 ship" rationale (FAILURES.md original framing) was that N-3.1 would be the natural anchoring surface; N-3.1 has folded into Inversion v0 which has shipped without anchoring. There's no remaining structural reason to defer.
- Confidence in deferral being correct: **LOW**.

### Planner lean

**Outcome 2 — split into F-64 + §77.1, both anchored at S81.**

**Confidence: HIGH** that splitting is correct framing.
**Confidence: MEDIUM-HIGH** that §77.1 is the right placement for the new doctrine (vs alternatives like new top-level or §F-08-extension).
**Confidence: MEDIUM** on the F-64 anchor language as currently drafted in FAILURES.md (may benefit from sharpening at anchoring time per council).

### Architectural shape per anchored outcomes

**§F-64 — Narration-commit gap as systemic contamination surface (ANCHORED):**
> When narration claims a state mutation that the engine does not deterministically enforce, the claimed state drifts across turns. Engine must enforce state mutations either at narration-detection time (closed-vocab parser feeding §17 single-writer per §1a.x) or via operator-driven slash gate (per §F-59 + §1b). LLM narration alone is not a structural state-mutation signal. Architectural response: §1a.x parser + §1b/§1b.1 suggester pattern. Sister to §76 (one-way claim-without-write; §76 covers two-way write-and-re-read loops). Cousin to §F-44 (substrate-level bleed surfaces that can manifest F-64-shape behavior downstream).

**§77.1 — Instruction-side compliance-failure detection (NEW sub-clause):**
> §77 names two-layer enforcement (instruction-side MUST/MUST-NOT + information-side context-block suppression). When the instruction-side layer fails empirically — the LLM ignores a MUST/MUST-NOT directive — the failure must be **detectable**, not just observable. Architectural response: per-directive compliance-detection telemetry event (prototype: `clarification_in_fiction_compliance_failure` at S77 §1b.1 ship). Each MUST/MUST-NOT directive earns its own compliance-detection surface at the directive's ship time or post-empirical-failure surfacing. Closure is not "enforce harder" (prompts have ceilings) — closure is "make the failure observable so iteration can be data-driven."

### Anchoring-instance list for §F-64 at S81 ship

Per anchoring convention, list specific firing instances:

1. **S53 — §1.F.c NPC was_new perverse-incentive loop.** First instance.
2. **S63 — §1.F.e consequence-DM-side pre-emptive drop.** Second instance.
3. **S66 — F-031 quest delivery silent inventory fail.** Third instance.
4. **S66 — F-035 loot evaporation.** Fourth instance.
5. **S68 — N-4 NPC pronoun drift.** Fifth instance.
6. **S78 — N-4 descriptor→name coreference gap.** Sixth instance (v1.x extension surface).
7. **S78 — LLM price invention + cross-turn inconsistency.** Seventh instance (the original "N-3.1 spec" surface, surfacing empirically before architectural ship).
8. **S78 — F-44 NPC-axis bleed (Mara at both bakeries).** Eighth instance (hybrid; F-44 substrate-fix + F-64 manifestation downstream).

### Anchoring-instance list for §77.1 at S81 ship

1. **S77 — §1b.1 `clarification_in_fiction_compliance_failure` event.** First instance + prototype implementation. Telemetry detects when LLM narrates state-change despite `pending_clarification` directive saying "narrate scene continuing without finalizing."
2. **S78 — Central thread MUST/MUST-NOT compliance failure** (the §F-08-a finding). Second instance, awaiting compliance-detection event at S81 implementation.

Plus filed-forward candidates for compliance-detection events at:
- `_COMBAT_NARRATION_INVARIANTS` (12 MUST/MUST-NOT clauses; detection event per clause or aggregate)
- `compute_commitment_directive` ("Your narration MUST address the prior commitment")
- HARD STOP RULES 1–7 (each is a MUST/MUST-NOT framing)
- N-4 HARD STOP RULE 7 specifically (pronoun lock)

The §77.1 doctrine names the pattern; per-directive implementation lands at observed-friction.

---

## §6 — Open questions for S80 council pressure-test

1. **Does the framing test outcome (split F-64 + §77.1) hold under council pressure-test, or does the council see a unified framing the walk missed?** Particularly: is there a third candidate framing where both engine-side and instruction-side compliance-failures cohere under a single doctrine without losing operational value?

2. **Is §77.1 the right placement for the compliance-failure doctrine, or should it anchor elsewhere?** Walk's leans:
   - §77.1 (sub-clause of atmospheric continuity) — recommended.
   - §F-08-extension (perpetuates loose metaphorical relationship to closed historical incident) — rejected.
   - New top-level §82 (overweighting; doctrine sits naturally within §77's two-layer framing) — rejected.
   Council: is there a fourth option (e.g., as sub-clause of §1a.x, or co-anchored with F-64)?

3. **Is the closure-pattern bifurcation (engine-side surface vs detection-telemetry) actually evidence of two doctrines, or evidence of one doctrine with two implementation shapes?** Walk's lean: two doctrines. Counter-argument worth pressure-testing: §F-64 could anchor with two closure-shape sub-clauses (§F-64.1 engine-side surface, §F-64.2 compliance-detection telemetry) instead of separate §77.1. Council should pressure-test which framing better supports future ships.

4. **Should instance #7 (F-44 NPC-axis bleed) count in the F-64 cluster, or should it stay in §F-44's lineage only?** Walk's lean: counts in F-64 as manifestation; closure is §F-44-side. Council should pressure-test the double-counting framing.

5. **Should §77.1's compliance-detection telemetry be a single generic event-type or per-directive-named events?** S77 shipped `clarification_in_fiction_compliance_failure` as named-per-directive. Future MUST/MUST-NOT directives could either each get their own event name (high specificity, telemetry surface area grows) or share a generic `directive_compliance_failure` event with directive-id payload (lower specificity, simpler dashboard). Walk doesn't have a strong lean; surface for council.

6. **Does §F-64 anchoring change the "LLM narration alone is not a state-mutation signal" rule's relationship to §1a?** Specifically: §1a says LLM never decides binding state. §F-64 names what happens when LLM narration claims state without engine enforcement. Should §F-64's anchor language make the §1a relationship more explicit (e.g., "§F-64 names the structural insufficiency of LLM narration as state-mutation signal — operationalizes §1a's binding-decision restriction")? Or is the current cousin framing sufficient?

---

## §7 — Filed forward (out of S79 scope, for downstream sessions)

These walk findings deserve future-session attention but are NOT in S79 Phase 1 walk scope:

- **Instance #8 (N-1 over-firing on price quotes/memory refs) reclassified as N-1 tuning surface**, not F-64. Filed for v1.x N-1 tuning queue.
- **Instance #10 (loot_drop_llm semantic misfire) reclassified as Phase 3b parser-vocabulary-overlap surface**, not F-64. Filed for v0.x §1a.x parser-tuning queue.
- **§F-44.1 sub-clause candidacy** (NPC-axis chroma bleed + location-aware NPC matching) — separate doctrine-anchoring walk if surface area grows.
- **Walk-finding correction to FAILURES.md framing language** for §F-08 metaphorical reference — replace "Sister to §F-08 (NPCs never commit)" with precise §77.1 relationship at S81 anchoring time.

---

## §8 — End-of-walk summary

**Deliverable:** this document. Independent planner structural analysis of F-64 candidate.

**Walk outcomes:**
- Adjusted instance count: **9 instances** (5 anchored Group A + 4 candidate Group B). Two original S78 candidates (#8 N-1 over-fire, #10 loot_drop_llm misfire) reclassified outside the F-64 cluster.
- Framing test: current F-64 framing fits 8 of 9 instances; instance #11 requires a structurally distinct doctrine.
- Closure-pattern analysis: F-64 has one consistent engine-side-surface closure pattern (covers 8 instances); instance #11 requires detection-telemetry + iteration closure pattern.
- Doctrine-relationship map clarified — §F-08 is historical, not anchored; new compliance-failure doctrine fits cleanly under §77 as §77.1.

**Anchoring readiness lean:**
- **Outcome 2: anchor F-64 + §77.1 (split) at S81 ship.**
- Confidence: HIGH on the split; MEDIUM-HIGH on §77.1 placement; MEDIUM on F-64 anchor language draft.

**Council prompt:** filed as separate deliverable `F64_COUNCIL_PROMPT_DRAFT.md`.

**Anti-conformity flag.** Per WWC Planner-Lead-Architecture Discipline Rule 4 (this walk is the third anchor instance of the discipline): if S80 council converges with planner lean (Outcome 2 + §77.1 placement) without pressure-test friction, flag for re-pressure-test. The walk's planner-side analysis is opinionated; convergent enthusiasm without independent grounding is the failure mode the discipline guards against.

**Next session:** S80 — council pressure-test on F-64 anchoring (Opus medium per WWC conditional; synthesis-heavy doctrine review).
