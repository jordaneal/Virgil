

---

## Doc-currency discipline (filed post-Inversion-sketch, S70-equivalent planner correction)

**The lapse:** SESSIONS.md drifted twelve sessions out of date (last entry S52 while project state was at Inversion sketch). ROADMAP, FAILURES, DOCTRINE, WHY, VIRGIL_MASTER all carried pre-mandate state. External reviewers (Oracle, GPT, Gemini) read canonical docs as authoritative source; reasoning ran against stale ground truth. Oracle drift in convergent-review "fire S65" instruction was downstream of this — docs Oracle reads named S52 as recent.

**Root cause:** Doc updates kept losing to higher-friction surfaces. Every session had something more urgent — a HALT to walk, a dispatch to draft, a review to weigh. Doc updates are durable but non-urgent. Without discipline they get squeezed out indefinitely. Each individual skip was defensible; the cumulative skip wasn't.

**Standing practice from this point forward (three discipline rules):**

### Rule 1 — Doc updates land same-turn as Code handoff

When a Code session lands and planner writes the post-session response, doc updates fire in the same response. Not "later," not "when there's a gap." Same turn.

Minimum updates per ship:
- **SESSIONS.md** — one entry per shipped session (compact: scope, ship status, doctrine impact, cross-references)
- **FAILURES.md** — only if a doctrine candidate moved status (new instance, anchored, refined)
- **ROADMAP.md** — only if §11 lock changed priority queue or filed-forward state
- **DOCTRINE.md** — only if anchored doctrine moved (new §-entry, instance-list update, candidate filed)
- **WHY.md** — only if architectural reasoning would compound across future sessions
- **VIRGIL_MASTER.md** — only if state snapshot changed materially

Most sessions touch SESSIONS + zero or one other doc. Total append cost: 5-15 minutes of writes per session.

### Rule 2 — Staleness flag on external-review dispatches

When operator says "ask GPT," "Oracle response below," "Gemini's take," or otherwise dispatches a review against the canonical docs, planner checks doc currency before drafting the prompt.

Three states:
- **Current** — docs reflect last shipped session. Dispatch as-is.
- **Stale** — docs lag ≤1 session behind shipped state. Planner names the staleness explicitly in the dispatch ("note: SESSIONS.md hasn't received the S68 entry yet; that ship covered N-4 pronoun lock + N-3 HALT to multi-spec").
- **Significantly stale** — docs lag ≥2 sessions. Halt dispatch, fire doc updates first, then dispatch with current docs.

Reviewer drift downstream of stale docs is a planner failure, not a reviewer failure. Naming the staleness costs one paragraph; updating before dispatch costs 10 minutes; both are cheaper than a review pass reasoning against wrong ground truth.

### Rule 3 — Session-start self-check on doc currency

At session start (operator sends "go," shares a Code handoff, poses a planning question), planner reads SESSIONS.md tail before architecture work resumes. If last entry doesn't match last known shipped session, doc updates fire first.

One tool call per session start. Catches drift before it compounds.

### What this discipline does not do

- Doesn't catch every architectural-reasoning failure. Drift in non-doc surfaces (operator confidence, planner self-assessment, doctrine pattern recognition) requires different discipline.
- Doesn't replace the existing end-of-session handoff format. Handoff stays; doc updates are additional, not substitute.
- Doesn't apply to planner-scratch files. Those are workshop, not canon. Currency expectation lower.
- Doesn't apply to specs/ files individually — specs land at lock time per Path A cadence and don't need session-by-session updates after lock.

### The meta-observation that earned this discipline

Planner optimizes for next architectural move and treats operational hygiene as overhead. This bias produces good architecture sketches and stale docs. The corrective is treating doc updates as part of the ship, not as work that happens between ships. The discipline is mechanical (rules above), not motivational (try harder).

Operator named this lapse twice in one conversation arc — first slash sprawl, then doc lag. Both were real failures planner should have flagged before operator did. Pattern noted; standing practice above is the structural response, not a one-time fix.

---

## Planner-Lead-Architecture Discipline (anchored S77; second instance S78)

A discipline complement to Doc-currency. Doc-currency keeps the record accurate; this one keeps the architectural reasoning record durable across dispatches.

**The shape of the failure mode this prevents.** Multi-phase ships (sketch → review → implementation) routinely surface architectural choices that earn operator + Oracle locks. Once locked, the reasoning trail tends to evaporate: the implementation dispatch quotes the lock, the implementation lands, the lock fact persists, but **the council pressure-test record that produced the lock** dissolves into chat history. Future planners reading the doctrine see "M-DELAYED locked" but cannot reconstruct why M-IMMEDIATE was rejected; future architectural choices in the same neighborhood risk re-litigating the question or repeating the rejected alternative under a different name.

S77's §1b.1 ship surfaced this directly. The Gemini third pressure-test pass uncovered that Oracle's earlier defense of M-IMMEDIATE had conflated *LLM-narration-as-content* (non-§1a-violating; the project's existing workflow) with *LLM-narration-as-gate* (§1a-violating; not what M-DELAYED does). The reasoning record matters more than the lock fact — without it, future planners might re-propose M-IMMEDIATE-equivalent shapes under a renamed framing.

**The three discipline rules.**

### Rule 1 — Council pressure-test record documented at anchoring time

When a doctrine candidate anchors (sub-clause earns a slot in DOCTRINE.md), the anchoring text documents:
- The architectural choice (e.g., M-DELAYED over M-IMMEDIATE)
- The reasoning record (which pressure-test pass surfaced what; what conflation it caught; what alternative was rejected with what reason)
- The empirical watch surfaces that will detect if the choice was wrong (telemetry events, calibration snapshots, compliance-failure tracking)

Anchoring without the reasoning record is incomplete. Future planners must be able to reconstruct the architectural judgment from the anchor alone.

### Rule 2 — Recon-first dispatch resolves architectural questions pre-implementation

Implementation dispatches with open architectural questions surface those questions as recon items (R1, R2, …) per F-60. Code resolves recon items via observable file/code state, produces a recon report in `planner-scratch/`, surfaces Code's recommendation with reasoning, and gates implementation on operator + Oracle confirmation when the question is architectural rather than purely technical.

Recon items distinguish:
- **Technical questions** (does file X exist? does function Y return shape Z?) — Code resolves silently and proceeds.
- **Architectural questions** (does new system A coexist with existing system B? what's the doctrinally clean shape?) — Code recommends, operator + Oracle confirm.

The recon report is durable artifact. It compounds across ships: when the next dispatch in the same neighborhood opens, the prior recon report grounds the new dispatch's framing.

### Rule 3 — Operator-readable architectural-judgment record

When Code's recommendation diverges from the dispatch's filed framing, the divergence is named explicitly in the handoff with reasoning. Dispatch-as-suggestion / Code-as-architecture-judgment (per F-60 "filings are starting points, not specs") is operationalized: Code is responsible for surfacing the divergence; operator is responsible for confirming or overriding.

This prevents silent drift where Code interprets the dispatch loosely without naming the interpretation, leaving operator to reverse-engineer the architectural judgment after the fact from the diff.

### Anchor instances

- **S77 (first anchor)** — §1b.1 Clarification Handshake Primitive v0. Recon found R9 impedance (DM_PHILOSOPHY.md byte-budget overflow); Code resolved by dropping the static prose section in favor of the dynamic `compute_pending_clarification_directive` (state-gated, only fires when pending). Mid-implementation: corrected `markers_present` mapping for quest_acceptance (verb-only does not surface structural markers; was incorrectly set to `True`). DOCTRINE.md §1b.1 ANCHORED with full M-IMMEDIATE rejection reasoning + §F-59 refinement candidate filed forward.

- **S78 (second anchor)** — §1b.1 Phase 3b parser registration. Recon-first dispatch resolved three architectural questions (R1-R5) before implementation. R3 N-1 vs transaction_completion vocabulary overlap surfaced; Code recommended (c) surface-separated (N-1 stays unchanged; transaction_completion fires alongside; consumer surfaces don't overlap) with reasoning grounded in R2's evidence (N-1's downstream consumer is isolated to `_attach_hints` embed edits). R4 surfaced need for post-LLM aggregator surface — Code identified clean integration point at `_dm_respond_and_post:4251` alongside existing `_attach_hints` post-LLM hook.

- **S79 (third anchor)** — F-64 doctrine-anchoring walk. Planner-side independent structural analysis (`planner-scratch/F64_ANCHORING_WALK.md`) BEFORE council pressure-test. Walk produced 9-instance inventory + framing test + closure-pattern analysis + architectural-relationship map + anchoring readiness lean (Outcome 2: split into F-64 + §77.1 doctrine pair). Council prompt drafted with anti-conformity protocol (`planner-scratch/F64_COUNCIL_PROMPT_DRAFT.md`).

- **S81 (fourth anchor)** — F-64 anchoring + compliance-failure telemetry implementation post-council. Three reviewer overrides applied per S80 council pressure-test: (1) Gemini Q1 reworded F-64 framing to remove inadvertent §1a-violation reading; (2) Gemini Q3 + others moved compliance doctrine from §77.1 sub-clause to top-level §82 candidate; (3) GPT + Oracle Q5 convergent deferred §82 anchoring (insufficient 2-instance maturity; threshold requires 3 distinct directive surfaces). Recon Phase A reclassified loot_drop_llm out (parser-vocab-overlap not F-64) + added S51 player-narrative-authority drift to cluster (R2 SESSIONS audit find). F-64 cluster lands at 7 instances at S81 anchor.

---

## Doctrine-graph proliferation watch (filed S81 post-§82 deferral)

**The observation:** GPT surfaced at S80 council pressure-test that the doctrine graph is approaching a danger zone where:
- Every repeated implementation pattern becomes a named doctrine
- Sub-clauses proliferate faster than invariants stabilize
- Doctrinal cleanliness starts outrunning empirical necessity

**Why this matters:** at 76+ anchored doctrine entries across DOCTRINE.md (numbered + sub-numbered), the graph is dense enough that doctrine-relationship maps become harder to maintain. Every new anchor invites the question "does this intersect §N or §M?" If anchoring threshold is too eager, doctrines start referencing each other in tangles rather than building on each other in hierarchies.

**Standing discipline from S81 forward:**

### Sub-anchor proliferation watch

When considering a sub-clause anchor (§N.M shape):
- Does the sub-clause name a property axis of the parent doctrine, or a different failure mode?
- §76.1/§76.2 pattern: property axes of one mechanism (rate-unlimited write + verbatim re-injection are both properties of the §76 four-property test). Clean sub-clause precedent.
- §82 candidate at S81: NOT a property axis of §77; it's a different failure mode (substrate-wide compliance failure vs §77's atmospheric-continuity scope). Earns top-level anchoring (when threshold met), not sub-clause placement.

The test: would future planners reading the sub-clause expect the parent doctrine's framing to apply directly, or would the sub-clause need its own architectural framing? If the latter, top-level anchoring is structurally cleaner.

### Anchor-threshold discipline reinforcement

Six-instance threshold (per FAILURES.md candidate framing) is empirical-evidence floor. §82 deferral at S81 is the first explicit application of this discipline under planner-lead-architecture: 2 instances is insufficient empirical maturity even when the architectural pattern is operationally already shipping.

The pattern is already operating (S77 `clarification_in_fiction_compliance_failure` retiring into generic; S78 §F-08-a candidate; S81 central_thread detector). That's pattern-emergence, not doctrine-anchoring. The architectural-design-time guidance can be filed as candidate-doctrine-application without the candidate itself anchoring.

### Cross-doctrine relationship-map maintenance

When a doctrine anchors, its architectural-relationship-map (which other doctrines it intersects, complements, or absorbs) becomes load-bearing for future planners. Anchoring without explicit relationship-map produces tangled cross-references.

§F-64 anchoring at S81 documents relationship-map explicitly (§1a, §1a.x, §1b, §1b.1, §76, §77, §F-44). Pattern reusable for future anchors. Future anchors that skip the relationship-map earn pushback at council pressure-test.

### What this discipline does not do

- Doesn't prevent architectural mistakes — those still get made. The discipline preserves the *reasoning* so future planners can identify whether a mistake-shape has been seen before.
- Doesn't replace operator + Oracle as final arbiters on architectural locks. The discipline structures the input to that decision, not the decision itself.
- Doesn't apply to purely-technical implementation choices (variable naming, function placement, test organization). Reserved for surface-level architectural judgments that compound across ships.
