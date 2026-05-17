

---

## §F-64 — ANCHORED at S81

Promoted from candidate to anchored doctrine. See `DOCTRINE.md` §F-64 for full anchored entry (cluster table, architectural-relationship map, closure pattern).

S81 anchor reflects the S79 walk + S80 council pressure-test arc. Cluster lands at 7 instances post-S81 recon Phase A (R1 reclassified loot_drop_llm misfire out as parser-vocab-overlap surface; R2 added S51 player-narrative-authority drift as instance #8 in cluster).

S78 instance #7 (Bishop's bakery NPC bleed) reclassifies to §F-44 cluster per S80 Q1 Oracle convergent. See §F-44 entry below.

---

## §F-44 — Cross-axis bleed (chroma + NPC extractor)

**Status:** ANCHORED at S25 #6 (chroma bleed); NPC-axis instance added S78 (Bishop's bakery same-NPC-different-location bleed).

**Original instance (S25 #6):** `get_recently_active_npcs` returned campaign-wide NPCs after `/travel`; tavern NPCs surfaced in subsequent locations. Closed via strict location-scoping (`location_id=` parameter; NULL `location_id` rows silently excluded).

**S78 NPC-axis instance:** Operator traveled Westmarket Inn → Bishop's Bakery; LLM narrated "Mara" (Westmarket baker) as the baker at Bishop's Bakery, complete with cross-location memory ("she remembers the two gold you handed her earlier"). Two structural causes compound:
- **Chroma RELEVANT PAST EVENTS retrieval is campaign-scoped, not location-scoped.** Similarity search on "bakery"/"bread"/"baker" at Bishop's Bakery surfaces the Westmarket Mara encounter prose verbatim into prompt context.
- **NPC extractor name-matching is global per campaign.** When the LLM narrates "Mara" at Bishop's Bakery, the extractor matches the existing Mara NPC row (Westmarket-located) rather than creating a new entity.

**Closure shape (planned):** Symmetric to S25 #6's fix — location-scoped chroma retrieval filter + NPC extractor location-aware matching (when LLM uses a known NPC name at a new location, treat as new NPC entity unless explicit operator confirmation). Both belong on the priority queue.

**F-64 relationship:** F-44 NPC-axis bleed can manifest as F-64-shape behavior downstream (LLM narrates Mara at new location based on bled-in chroma context — narration claims state — Mara is here — that engine doesn't enforce). Counts in F-44 cluster as primary; F-64 manifestation is downstream effect.

---

## §82 candidate — Instruction-Side Compliance (CANDIDATE, 2 instances)

**Status:** CANDIDATE. Anchoring deferred per S80 council convergent (insufficient empirical maturity at 1 anchored + 1 candidate; threshold requires 3 structurally-identical instances across distinct directive surfaces).

**One-line:** LLM violates instruction-side MUST/MUST-NOT directive compliance; narration diverges from engine-declared policy.

**Structural framing:** §82 names the substrate-wide failure mode where the engine's directive surface (MUST/MUST-NOT framing in prompt context) does NOT produce LLM compliance. Distinct from §F-64: §F-64 is writer-side absence (no parser/writer captures narration's state claim); §82 is instruction-side compliance gap (engine HAS the directive surface; LLM violates).

**Architectural response (planned at anchor):** compliance-detection telemetry + prompt-iteration feedback loop. Generic `directive_compliance_failure` event captures violations; operator + planner read telemetry to surface drift; prompt discipline tightens iteratively. Closure is not "enforce harder" (prompts have ceilings) — closure is "make the failure observable so iteration can be data-driven."

**Doctrine-relationship to §77:** §77 anchors two-layer enforcement (instruction-side MUST/MUST-NOT + information-side context-block suppression) for atmospheric directives. §82 differs in scope — substrate-wide instruction-side compliance, not just atmospheric. Co-anchored placement (sub-clause of §77) rejected at S80 per Gemini Q3 reasoning: §77's atmospheric-continuity scope doesn't structurally absorb substrate-wide compliance-failure. §82 earns top-level anchoring (when threshold met), not sub-clause placement.

**Instances:**

1. **S77 `clarification_in_fiction_compliance_failure`** (anchored). LLM violates pending_clarification directive's MUST-NOT-narrate-action-as-completed framing; narration finalizes action despite engine's pending state. Prototype implementation of the compliance-detection-telemetry pattern. At S81 refactored to fire via generic `directive_compliance_failure` event with `directive_name="pending_clarification"`.

2. **S78 §F-08-a central thread compliance failure** (candidate). LLM ignores `compute_central_thread_directive`'s "Do NOT name or restate the thread" framing; bakes central_thread exposition into unrelated NPC dialogue (Westmarket baker narrating mine collapse + Grahn the Miner's Union leader). At S81 instrumented with post-LLM heuristic detector firing `directive_compliance_failure` with `directive_name="central_thread"`.

**Anchoring threshold:** 3 structurally-identical instances across distinct directive surfaces (different §59 sibling directives, not different turns of the same directive). Current empirical evidence: 2 instances. Compliance-failure telemetry SHIPS at S81 as §82-candidate-application; doctrine itself stays candidate until third instance accumulates.

**Why deferred:** Per S80 council (GPT + Oracle + Gemini convergent), anchoring at 2 instances risks "prematurely formalizing a temporary implementation pattern." The architectural-design-time guidance below is already operating empirically — planners can plan compliance-detection telemetry concurrent with new directive ships without §82 anchoring.

**Architectural-design-time guidance for new directive surfaces (planner discipline pre-anchor):** when shipping a new MUST/MUST-NOT directive, plan compliance-detection telemetry concurrent with directive ship. Don't wait for §82 to anchor; the practice is already operating. Each new MUST/MUST-NOT directive earns its own compliance-detection event at directive ship time (per S81 generic-with-payload telemetry pattern: `directive_compliance_failure` with `directive_name="<name>"`).

**Why generic-with-payload (not per-event-named):** Per S80 council convergent on Q6 (GPT + Gemini). Single event type accommodates all directive surfaces; no schema coupling to prompt text. Grep surface preserved (`grep 'directive_name": "<name>"'` works equivalently to per-event-type grep). Per-event-named pattern (S77 prototype) was filed-forward as alternative — operational experience may surface specific directives warranting per-event grep; planner revisits with sharper threshold definition for hybrid.

**Filed forward for downstream detectors (per WWC architectural-design-time guidance):**
- `_COMBAT_NARRATION_INVARIANTS` 12 MUST/MUST-NOT clauses (compliance detection per clause or aggregate).
- `compute_commitment_directive` ("Your narration MUST address the prior commitment").
- `compute_pacing_directive` (tier-imperative MUST framing at high tension).
- HARD STOP RULES 1-7 (each is a MUST/MUST-NOT framing; #7 specifically for pronoun lock).

§82 doctrine names the pattern; per-directive detector implementation lands at observed-friction.
