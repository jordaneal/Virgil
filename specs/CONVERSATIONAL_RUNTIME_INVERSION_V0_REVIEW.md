# Conversational-Runtime Inversion v0 — Review Pass

**Status:** Review pass (Phase 2) over `specs/CONVERSATIONAL_RUNTIME_INVERSION_V0_SPEC.md` (DRAFT). Walks all 12 §11 decisions. Operator reviews; on lock, spec flips DRAFT → LOCKED.
**Date:** 2026-05-15
**Cadence:** Session 2 of Path A three-session cadence. Opus medium.
**Authorized:** Phase 1 dispatch's `End-of-session handoff` Session 2 directive.

---

## §1. Inventory note before walking

Phase 1 produced the spec with Code's leans listed in §1. Phase 1 recon (R1-R6) cleared without HALT. Phase 2's task is *adversarial-review* — walk each §11 candidate with trade-offs surfaced cleanly, recommend default with calibrated confidence, and surface anything spec drafting smoothed-over.

**Distinct findings entering Phase 2:**

- **§11.6 discrepancy.** Sketch §11.6 stated lean (b); operator dispatch overrode to lean (a). Spec drafted under (a). Phase 2 either locks (a) or surfaces (b) as alternative — spec re-draft cost if (b).
- **§1b anchored-instance count.** Spec §4.2 wrote "five anchored instances (Quest Layer v0.1, Composition Layer v0, NPC State-Sync, Track 6 #5.1, N-10)." `CANON_BOOTSTRAP_BOT_V0_SPEC.md` §1.K references itself as "sixth project instance." Likely an undercount by one (a fifth instance exists between Composition Layer v0 and N-10 — candidate: Scene Lifecycle v1 §11.M-adjacent surface or a Track-5 v0.1 patch). Material at §11.3 framing but not at lean — (a) parallel surfaces holds regardless of count.
- **N-3.1 fold-in.** Spec drafted with fold-in (a). Phase 2 confirms or surfaces (b) keep-separate as alternative.

No HALT triggered. Walk proceeds across all 12 decisions.

---

## §2. Summary table

| §11 | Question | Candidates | Recommended | Confidence |
|---|---|---|---|---|
| 11.1 | Detection vocabulary at v0 | (a) closed-vocab / (b) LLM classifier / (c) hybrid | **(a) closed-vocab** | HIGH |
| 11.2 | §1a doctrinal extension shape | (i) in-place amend / (ii) §1c new doctrine / (iii) §1a.x sub-numbering | **(iii) §1a.x sub-numbering** | LOW — operator + Oracle |
| 11.3 | §1b validated-suggester interaction | (a) parallel / (b) extension / (c) replacement | **(a) parallel surfaces** | HIGH |
| 11.4 | N-3.1 commitment-tracking fold-in | (a) fold into Inversion v0 / (b) stay separate | **(a) fold-in** | MEDIUM-HIGH |
| 11.5 | First-migration set at v0 | transaction + quest-accept + loot-drop vs alternatives | **txn + quest-accept + loot-drop** | HIGH |
| 11.6 | S69 implementation-spec shape | (a) amend-in-place / (b) v0.1 spec re-open | **(a) amend-in-place** (operator override) | MEDIUM (confirms operator dispatch; not Code-original lean) |
| 11.7 | Detection-confidence tier routing | three-tier (high/medium/low) | **three-tier per §3.3** | HIGH |
| 11.8 | Telemetry verbosity | per-fire vs aggregated | **per-fire** | HIGH |
| 11.9 | Operator manual override surface | existing slash + #dm-aside rejection vs new abort | **existing slash + rejection card** | HIGH |
| 11.10 | Bot→Avrae auto-execution | §F-59 holds vs revisit | **§F-59 holds unchanged** | HIGH |
| 11.11 | Composition forward-compat | silent (no v0.x pre-coupling) | **hold discipline** | HIGH |
| 11.12 | Migration sequencing | (a) big-bang / (b) gradual per-ship | **(b) gradual** | HIGH |

**Split:** 8 HIGH, 1 MEDIUM-HIGH (§11.4), 1 MEDIUM (§11.6 — operator-override-not-Code-lean), 1 LOW (§11.2 — operator + Oracle territory).

**§11.13 surfaced during walk:** None. Spec covers the architectural surface cleanly.

---

## §3. Full decision walk

### §3.1 — §11.1 Detection vocabulary at v0

**Question.** What parser shape underlies per-domain narration-detection?

**Candidates.**
- (a) Closed-vocabulary verb-and-signal parsers (per-domain frozenset + structured-signal cooccurrence)
- (b) LLM-classifier intent extraction (LLM classifies turns into structured intent categories)
- (c) Hybrid (closed-vocab primary + LLM fallback for low-confidence)

**Trade-offs.**

| Axis | (a) Closed-vocab | (b) LLM classifier | (c) Hybrid |
|---|---|---|---|
| §1a doctrinal clean | ✓ deterministic gate | ✗ re-introduces LLM-as-decider | ~ deterministic primary, LLM secondary |
| Precedent in project | ✓ N-1 (`mechanical_hints.py`) + S66 F-035 loot verb vocab | New surface | New surface |
| Robustness to phrasing | ✗ brittle; vocab maintenance burden | ✓ robust | ✓ robust on fallback path |
| Inspectability / debug | ✓ verb sets + signal-check fns | ✗ classifier opacity | ~ partial inspectability |
| Calibration drift | None — deterministic | LLM tuning drift | LLM tuning drift on fallback |
| Implementation cost at v0 | Low — N-1 pattern generalizes (R1) | Medium — new prompt + parser | High — two systems |
| Risk of friction surfacing | Medium — vocab gaps possible | Low | Low |

**Recommended default.** **(a) closed-vocabulary verb-and-signal parsers at v0.**

**Confidence: HIGH.** R1 confirmed N-1 pattern generalizes cleanly. §1a-clean. Lowest implementation cost. Friction surfaces at v0 are bridged by existing slashes (which remain operational); vocabulary-expansion governance files v0.x candidate.

(b) and (c) file v1.x; ship only if v0 closed-vocab surfaces unmitigated friction.

---

### §3.2 — §11.2 §1a doctrinal extension shape (DEEP SYNTHESIS)

**Question.** How is narration-detection-as-deterministic-gate doctrinally codified?

**Candidates.**
- (i) §1a in-place amendment (extend §1a's statement to explicitly name narration-detection-with-deterministic-parser)
- (ii) §1c new top-level doctrine (codify as third companion to §1a + §1b)
- (iii) §1a.x sub-numbering (anchored extension under §1a per §14.1 pattern)

**Synthesis — the load-bearing axis.**

The decision turns on *doctrinal-derivation framing* vs *citation-clarity for future spec sessions*.

The narration-detection-as-gate framing is *derivatively* §1a's intent — "LLM does not decide binding state" reaches the same conclusion whether the gate is (operator slash) or (closed-vocab parser fed by narration). The mechanism shifts; the principle doesn't. This derivative-of-§1a framing argues for **anchoring under §1a's number** — either (i) in-place or (iii) sub-numbering.

However, narration-detection introduces *structurally new* operational machinery — a parser surface that didn't exist when §1a was first written. Future specs will need to cite the narration-detection-as-gate principle separately from "LLM doesn't decide binding state" — they're conceptually adjacent but architecturally distinct. This citation-need argues for **separable identification** — (ii) §1c new doctrine OR (iii) §1a.x sub-numbering give the principle its own citation point.

(i) keeps §1a unified but risks doctrine-statement bloat. The clean two-sentence §1a (extended with a third clause) becomes a paragraph. Doctrine layer's value comes from terseness and clarity at citation.

(ii) §1c gives clean separable citation but breaks the §1a/§1b two-doctrine pairing that has hardened across six-ish §1b instances. The pairing has become its own load-bearing reference — operators and future specs cite "the §1a/§1b discipline" as a unit. Splitting to §1a/§1b/§1c blurs that.

(iii) preserves §1a as the doctrinal anchor (no bloat), gives the extension its own citation point (e.g., "§1a.1: narration-detection-as-deterministic-gate"), and maintains the §1a/§1b pairing's clarity. Mirrors §14.1's established sub-numbering pattern.

**Trade-offs.**

| Axis | (i) In-place amend | (ii) §1c new doctrine | (iii) §1a.x sub-numbering |
|---|---|---|---|
| Preserves §1a as anchor | ✓ | ✗ splits doctrine layer | ✓ |
| Preserves §1a/§1b pairing | ✓ | ✗ blurs to §1a/§1b/§1c | ✓ |
| Separable citation surface | ✗ ("see §1a clause 3"?) | ✓ ("see §1c") | ✓ ("see §1a.1") |
| Doctrine layer terseness | ✗ §1a statement bloats | ✓ each doctrine compact | ✓ each compact, hierarchically organized |
| Project precedent (§14.1) | None | None | ✓ |
| Mirrors derivation logic | ✓ (rule extends rule) | ✗ (suggests independence) | ✓ (sub-rule under rule) |
| Oracle/operator citation cost | Low | Low | Low |

**Recommended default.** **(iii) §1a.x sub-numbering.**

**Confidence: LOW — operator + Oracle territory.** Code's weak lean (iii) holds the trade-offs cleanly: §1a anchor preserved, derivation-framing honored, citation surface separable, project precedent (§14.1) operates. But this is doctrine-layer work — Oracle owns the call. (i) is a credible alternative if Oracle reads the extension as small-enough to absorb in-place; (ii) is the operator's call if separability outweighs the §1a/§1b pairing's load-bearing role.

**Open axis that would shift recommendation.** If Oracle reads narration-detection-as-gate as a *structurally independent* doctrine (not derivative of §1a's intent), (ii) becomes the right call. If Oracle reads the extension as a *clarification* (narrower than a new rule), (i) becomes right. Code's read — derivative-but-architecturally-new — lands at (iii).

---

### §3.3 — §11.3 §1b validated-suggester interaction (DEEP SYNTHESIS)

**Question.** How does narration-detection relate to the existing §1b validated-suggester pattern?

**Candidates.**
- (a) Parallel surfaces (§1b unchanged; narration-detection sits parallel as high-confidence shortcut)
- (b) Extension (§1b doctrine extends to include both slash-approval and narration-detection as gate forms)
- (c) Replacement (§1b deprecates; all flows route through narration-detection)

**Anchored-instance inventory.** Spec §4.2 cited "five anchored instances." Phase 2 audit:

1. Track 6 #5.1 SRD suggester (S26)
2. NPC State-Sync (S41)
3. Quest Layer v0.1
4. Composition Layer v0
5. *[gap — see §11.3 note below]*
6. CANON_BOOTSTRAP_BOT N-10 (per `CANON_BOOTSTRAP_BOT_V0_SPEC.md` §1.K "sixth project instance")

Phase 2 note: spec said five; precedent count appears to be six. The fifth instance is likely a Scene Lifecycle v1 §11.M-adjacent surface or a Track-5 v0.1 patch. Not material to the lean — (a) parallel surfaces operates regardless of count. **Surface for Phase 3 to verify the count when implementation cites §1b anchored-instances.**

**Trade-offs.**

| Axis | (a) Parallel | (b) Extension | (c) Replacement |
|---|---|---|---|
| Preserves §1b anchor across six prior instances | ✓ unchanged | ~ doctrine statement widens; instances re-fit | ✗ deprecates anchor |
| Implementation cost | Low — new surface adds; existing flows hold | Medium — re-citing existing instances under widened doctrine | High — migrating six instances |
| R4 evidence (5 `#dm-aside` card precedents work cleanly w/o modification) | ✓ | ✓ | ✓ |
| Doctrinal weight at v0 (largest direction-lock since stochastic-canonization) | Low — additive only | Medium — touches doctrine layer | High — touches doctrine + every instance |
| Blast radius if v0 surfaces friction | Contained — fall back to existing slashes | Medium — widened doctrine commitment | High — six surfaces affected |
| Honesty about architectural reality | ~ understates that narration-detection IS a validated-suggester surface | ✓ acknowledges shared gate-form | ✓ commits fully |
| Maturity required for lock | Low — v0 ships parallel; observe friction | Medium — needs anchored-instance walks | High — needs operator validation across all surfaces |

**Recommended default.** **(a) parallel surfaces at v0.**

**Confidence: HIGH.** R4 confirms existing card precedents (QUEST OFFER, QUEST ACT TRANSITION, REWARD READY, BOOTSTRAP, BOOTSTRAP COMPLETE) work cleanly without modification. (a) is implementation-safe — no existing instance touches; v0 ships purely additive. Blast radius contained. (b) is the likely v1.x position after observed friction demonstrates narration-detection reliably operates as the deterministic gate; the doctrine update lands when the evidence base supports it. (c) is too aggressive — replacing six anchored instances at v0 multiplies risk against an inversion-ship that's already large.

**Open axis.** None at v0. (b) earns its v1.x walk when Inversion observed-friction data accumulates.

---

### §3.4 — §11.4 N-3.1 commitment-tracking fold-in (DEEP SYNTHESIS)

**Question.** Does N-3.1 (commitment-tracking, HALTed at S68 for schema work) fold into Inversion v0 or stay separate?

**Candidates.**
- (a) Folds into Inversion v0 — same parser; same architectural problem
- (b) Stays separate — Inversion is surface, N-3.1 is commitment persistence; architectural cleanliness

**Synthesis.**

(a) is supported by the convergent-review framing — "slash sprawl is a symptom of deeper architectural framing" applies equally to commitment-tracking. N-3.1's HALT at S68 surfaced "need a commitment table"; Inversion surfaces "need narration-detection infrastructure." These are the same need from two angles.

Concretely: the per-domain parser §59 sibling family Inversion v0 ships includes a `commitment-utterance` domain whose detection writes to `dnd_commitments` via a new §17 single-writer (`commitment_upsert`). The parser machinery is *literally* the same that quest-acceptance / loot-drop / transaction-completion need. Building it twice is wasteful; building it once for N-3.1's purpose and separately for Inversion is wasteful in the same way.

(b) is supported by the argument that Inversion is operator-surface and N-3.1 is engine-canon — different load-bearing concerns. Folding risks coupling the spec ship to a schema decision that has its own deferred-work backlog (N-3 HALT was on schema).

**Trade-offs.**

| Axis | (a) Fold-in | (b) Stay separate |
|---|---|---|
| Parser reuse | ✓ one parser, two consumers | ✗ parser built twice OR commitment-tracking blocked on Inversion |
| Schema decision risk (N-3 HALT scope) | ~ Inversion takes on the schema decision | ✓ Inversion ships without schema decision |
| Doctrine F-64 anchoring (narration-commit-gap) | ✓ earns slot at Inversion lock | Filed forward; lands at separate N-3.1 spec |
| Ship-size at Inversion v0 | Larger — new table + writer + reader | Smaller — surface-only |
| Anti-gaslight rails at v0 | ✓ available immediately | ✗ deferred to N-3.1 separate ship |
| Operator review burden at lock | Higher — one more decision (schema) | Lower |
| Cleanliness of architectural separation | ~ blurs surface vs canon | ✓ clean |

**Recommended default.** **(a) folds into Inversion v0.**

**Confidence: MEDIUM-HIGH.** Lean is real but ship-size carries weight. Code's read: the parser-reuse argument is structurally compelling (building closed-vocab + signal-cooccurrence + cross-turn-dedup machinery twice would be a §59 sibling family duplication that violates project precedent). The schema decision is bounded — `dnd_commitments` shape is well-specified at §7.3 of the spec. Anti-gaslight rails earning v0 slot is a high-leverage win for the doctrine F-64 anchoring.

**Open axis.** If operator reads schema-decision-at-Inversion-v0 as too much to land in one ship, (b) is the right call — N-3.1 spec session opens separately post-Inversion, parser machinery duplicated minimally (the per-domain parser registry pattern allows late-add). The duplication cost is the lean's pivot point.

---

### §3.5 — §11.5 First-migration set at v0 (DEEP SYNTHESIS)

**Question.** Which Tier 3 surfaces invert at v0 ship?

**Code proposal (per spec §6).** Transaction-completion + quest-acceptance + loot-drop at v0; travel + compression + mode → v0.1.

**Synthesis — the load-bearing axis.**

Two dimensions: *friction-visibility* (which Tier 3 surfaces hit hardest in actual play) and *cascade-risk* (which surfaces have downstream coupling that complicates inversion).

**Friction-visibility ordering (Code's read against project history).**

| Surface | Friction visibility at observed play | Reasoning |
|---|---|---|
| Transaction-completion | Very high | N-1 hint extractor already shipped to address it; players narrate transactions constantly |
| Quest-acceptance | Very high | Player narrates "I'll take the job" every quest offer; DM must type `/quest accept id:abc` |
| Loot-drop | High | Player narrates leaving items; DM either types `/loot drop` or skips entirely (data gap) |
| Travel-intent | High | Operator typing `/travel destination:"X" duration:"1h"` is friction-visible but borderline-acceptable as direct DM action |
| Compression-intent | Medium | `/compress` carries Scene Lifecycle discipline; explicit operator decision feels appropriate today |
| Mode transitions | Medium-low | `/mode` is rare; Avrae init events handle most combat-mode entry |

**Cascade-risk ordering.**

| Surface | Cascade risk | Reasoning (R2 evidence) |
|---|---|---|
| Transaction-completion | Low | N-1 already handles; transaction-suggester flow exists; clean writer |
| Quest-acceptance | Low | `/quest accept` cascade limited to `dnd_quests.status`; clean writer (R2 confirmed) |
| Loot-drop | Low | `dnd_loot_drops` leaf table; no downstream cascade |
| Travel-intent | **HIGH** | Cascades to encounter rolls + faction ticks (per S69 spec §5) + scene compression coupling |
| Compression-intent | Medium | Touches Scene Lifecycle v1 compression discipline; wants explicit operator-confirm |
| Mode transitions | Medium | Couples to Avrae init events + Combat-track-1 discipline |

**The proposed set sits at the high-friction / low-cascade intersection.** Transaction + quest-accept + loot-drop are the three Tier 3 surfaces where (friction-visible) AND (cascade-clean) both hold at v0. Travel deferred because cascade risk hits S69's locked spec (which §11.6 is amending in-place); inverting `/travel` before S69 amendment lands risks coupling two architectural ships. Compression and mode deferred for adjacent reasons (Scene Lifecycle / Combat-track discipline).

**Trade-offs against alternatives.**

| Alternative set | Pros | Cons |
|---|---|---|
| **Proposed: txn + quest-accept + loot-drop** | Highest friction / lowest cascade; tight v0 ship | Travel friction defers to v0.1 |
| Add travel-intent to v0 | Higher friction coverage | Couples to S69 amendment + encounter/faction cascades |
| Drop loot-drop, add compression-intent | Compression discipline tested at v0 | Loot-drop friction higher than compression-friction; data gap on loot already a known issue |
| Single-surface v0 (txn only) | Lowest ship risk | Wastes per-domain parser infrastructure that's already being built |

**Recommended default.** **txn + quest-accept + loot-drop at v0.**

**Confidence: HIGH.** Proposed set sits cleanly at the friction-visible / cascade-clean intersection. R2 evidence confirms cascade-clean for all three. Per-domain parser infrastructure (built once) covers all three. Travel and compression file v0.1 with S69-amendment dependency for travel.

**Open axis.** None. Code's read aligns with R2 evidence and project history. Operator confirms or surfaces specific friction case Phase 1 missed.

---

### §3.6 — §11.6 S69 implementation-spec shape (DISCREPANCY RESOLUTION)

**Question.** When Inversion v0 ships, how does the locked Causality Engine v0 spec update for inversion-aware slash discipline?

**Candidates.**
- (a) Amend locked S69 spec in-place at Inversion v0 ship time (small §6.1 or §15 surface-delta clause)
- (b) Open S69 v0.1 spec session at resume (re-draft locked spec under inverted discipline)

**Discrepancy.** Sketch §11.6 reads "Lean: (b)" (cleaner spec hygiene; locked spec stays as doctrine-pre-inversion artifact). Operator dispatch override read "(a) amend-in-place" supersedes sketch. Spec drafted under (a). Phase 2 confirms (a) or surfaces (b) as alternative — (b) requires spec re-draft of §8.

**Synthesis.**

(a) trade-off:
- (+) Preserves S69's Session 2 review work (significant Phase 2 walk at Causality Engine review)
- (+) Cleaner ship cadence — Inversion lands → S69 amendment + implementation immediately follows
- (+) Locked architecture (§3-§7, §10) holds byte-for-byte; only surface layer (§6 tier framework slash discipline) changes
- (–) Locked-spec edits carry doctrinal weight; amendment requires Oracle confirmation that surface-layer change doesn't implicitly mutate doctrine layer
- (–) "Amend locked spec" pattern is new; project hasn't established precedent for in-place amendment of LOCKED specs

(b) trade-off:
- (+) Cleaner spec hygiene — locked S69 spec stays as the doctrine-pre-inversion artifact for reference
- (+) v0.1 spec session establishes inverted discipline explicitly; no in-place doctrinal weight question
- (–) Doubles review work (S69 v0.1 spec session + review pass + implementation)
- (–) Delays S69 implementation by the cost of v0.1 spec cadence
- (–) S69 architecture is unchanged; the "fresh spec" framing is heavier than the actual delta requires

**Trade-offs (decision-axis: amendment-weight vs spec-hygiene).**

| Axis | (a) Amend-in-place | (b) v0.1 re-spec |
|---|---|---|
| S69 architecture preserved | ✓ byte-for-byte | ✓ re-stated |
| Locked-spec edit precedent set | ✗ new pattern; needs Oracle approval | ✓ no in-place edits |
| Ship cadence | Faster (single amendment + impl) | Slower (full v0.1 spec cycle) |
| Doctrinal weight of amendment | Medium — requires care; surface-only intent | None — full re-spec |
| Operator review burden | Low — small amendment | High — full spec re-walk |
| Reference clarity for future specs | Slightly muddled — locked + amendment | Clean — single v0.1 spec is authority |
| Per-WWC ship-economics | Aligns | Adds cycle |

**Recommended default.** **(a) amend-in-place.** Per operator dispatch override.

**Confidence: MEDIUM.** This is the operator's override, not Code's original lean — sketch §11.6 stated (b). Code's reading of the trade-offs supports (a) as defensible (the amendment is genuinely surface-layer; architecture holds) but acknowledges that (a) sets a new pattern for locked-spec amendment that warrants Oracle confirmation. The MEDIUM confidence reflects that (a) is the operator's call; Code defers.

**Open axis.** If Oracle reads in-place amendment of LOCKED specs as a precedent-setting move that needs explicit doctrine (e.g., "§15.x — locked specs admit additive surface-layer amendments when downstream architectural ships invert the surface"), the answer shifts: lock (a) AND file an Oracle review of the amendment-pattern doctrine. Operator's call.

---

### §3.7 — §11.7 Detection-confidence-tier routing

**Question.** How do detection-confidence tiers route to action?

**Candidates.** Three-tier routing (high → engine writer; medium → `#dm-aside` suggester; low → silent) vs alternatives.

**Trade-offs.**

| Axis | Three-tier (proposed) | Two-tier (high/low only) | Four-tier (with very-high → silent-auto) |
|---|---|---|---|
| Suggester surface utility | ✓ medium-confidence has clean home | ✗ medium drops to silent (friction missed) | ✓ + very-high removes friction entirely |
| Risk of false-positive auto-writes | Medium (high-tier only writes) | Higher (more silent drops) | High (very-high auto-write at false-positive cost) |
| Operator burden at medium-tier | Single paste/click | None (but friction missed) | Single paste/click |
| Tunability per domain | ✓ thresholds per domain | Limited | Full |
| R5 prompt budget | ✓ negligible | ✓ | ✓ |
| Implementation cost | Medium | Low | High |

**Recommended default.** **Three-tier per §3.3.**

**Confidence: HIGH.** Three-tier matches §1b's deterministic-gate-with-operator-approval pattern. Per-domain threshold tuning files §11 candidate for v0.1 calibration.

---

### §3.8 — §11.8 Telemetry verbosity

**Question.** Per-detection-fire vs aggregated per-turn.

**Recommended default.** **Per-fire.** Standard project pattern; observability requires per-event signal.

**Confidence: HIGH.** No trade-off ambiguity. `narration_intent_detected:` / `narration_intent_routed:` / `narration_intent_suppressed:` per spec §3.4.

---

### §3.9 — §11.9 Operator manual override surface

**Question.** When narration-detection fires high-confidence but operator wants to refuse, what's the escape hatch?

**Candidates.**
- Existing slash + `#dm-aside` rejection card (proposed)
- New single-character abort (`/no`)
- Slash that mirrors detected intent

**Recommended default.** **Existing slash + `#dm-aside` rejection card.**

**Confidence: HIGH.** All 47 existing slashes remain operational. Operator types existing slash to override engine state (which the slash writer overwrites). `#dm-aside` rejection card surfaces if friction visible. No new abort surface needed at v0. Files `/no`-style as v0.x candidate if observed-friction surfaces.

---

### §3.10 — §11.10 Bot→Avrae auto-execution

**Question.** Does Inversion v0 cross §F-59 bot→Avrae prohibition?

**Recommended default.** **§F-59 holds unchanged.**

**Confidence: HIGH.** R6 confirmation. `DOCTRINE.md:560-564` text intact. S41 NPC State-Sync precedent generalizes: bot proposes operator-pasteable Avrae command via `#dm-aside`, operator pastes, Avrae executes. Inversion's transaction-completion high-confidence path uses exactly this pattern.

---

### §3.11 — §11.11 Composition forward-compat — silent

**Question.** Does v0 pre-couple v0.x emergent surfaces (LLM classifier, hybrid, advanced override)?

**Recommended default.** **Hold discipline — no pre-coupling.**

**Confidence: HIGH.** Standard project pattern since S65. v0 ships closed-vocab + parallel-surface §1b. v0.x candidates file in §12 of spec.

---

### §3.12 — §11.12 Migration sequencing for prior ships

**Question.** Big-bang Tier 3 migration at v0 vs gradual per-ship.

**Recommended default.** **(b) gradual.**

**Confidence: HIGH.** Big-bang multiplies blast radius against an inversion-ship that's already large. Per-ship sequential-commit discipline standing since S65 holds. v0 ships three Tier 3 inversions (§11.5); subsequent migrations follow observed-friction order.

---

## §4. R-finding integration check

Per Phase 1 handoff:

| R-finding | Integration into spec | Status |
|---|---|---|
| R1 (N-1 pattern generalizes) | §5 detection vocabulary architecture; §3.2 per-domain parser table | ✓ consistent |
| R2 (47 slashes / Tier classification) | §6 first-migration set; cascade audit for travel deferral | ✓ consistent |
| R3 (clean integration points at :2664 / :2789) | §3.1 layer placement | ✓ consistent |
| R4 (5 `#dm-aside` card precedents) | §11.3 parallel-surfaces lean; §3 suggester card format precedent | ✓ consistent (note: §1b instance count off by one — see §11.3) |
| R5 (prompt budget negligible) | §11.7 three-tier routing (no budget pressure); §3.4 telemetry verbosity | ✓ consistent |
| R6 (§F-59 holds) | §11.10 unchanged; §4.4 doctrinal framing | ✓ consistent |

**No R-finding/spec-recommendation contradictions surfaced at walk.**

One light flag: §1b instance count (5 in spec, ~6 per cross-referencing CANON_BOOTSTRAP §1.K). Material at framing but not at §11.3 lean. Phase 3 implementation cites accurate count when referencing §1b precedents.

---

## §5. Operator + Oracle decisions

These three decisions need operator + Oracle (not just Code's review) input before lock:

1. **§11.2 §1a doctrinal extension shape.** Code's weak lean (iii) §1a.x sub-numbering. Oracle reads on whether narration-detection-as-gate is derivative-of-§1a (lands at (i) or (iii)) vs structurally-independent (lands at (ii)). Affects all downstream spec citations.

2. **§11.6 S69 implementation-spec shape (amend-in-place precedent).** Locked under (a) per operator dispatch. Oracle reads on whether locked-spec amendment is doctrinally OK (precedent-setting pattern). If Oracle reads (a) as needing explicit doctrine — file §15.x candidate ("locked specs admit additive surface-layer amendments under inversion conditions") at Inversion lock.

3. **§11.4 N-3.1 commitment-tracking fold-in.** Code lean (a) MEDIUM-HIGH confidence. Operator's call on ship-size economics: lands schema decision + commit-table + commitment-utterance parser in Inversion v0 (a), or files N-3.1 separately post-Inversion (b). Affects v0 ship-size and F-64 doctrine candidate anchoring.

---

## §6. Summary of recommended defaults

| §11 | Recommended | Confidence | Walk-shifts-needed |
|---|---|---|---|
| 11.1 | (a) closed-vocab | HIGH | None |
| 11.2 | (iii) §1a.x sub-numbering | LOW | Oracle reads on derivation-vs-independence framing |
| 11.3 | (a) parallel surfaces | HIGH | None at v0 |
| 11.4 | (a) fold-in | MEDIUM-HIGH | Operator reads on ship-size economics |
| 11.5 | txn + quest-accept + loot-drop | HIGH | None |
| 11.6 | (a) amend-in-place | MEDIUM | Oracle reads on locked-spec-amendment precedent |
| 11.7 | three-tier | HIGH | None |
| 11.8 | per-fire | HIGH | None |
| 11.9 | existing slash + rejection card | HIGH | None |
| 11.10 | §F-59 holds | HIGH | None |
| 11.11 | hold discipline | HIGH | None |
| 11.12 | (b) gradual | HIGH | None |

**Aggregate:** 8 HIGH, 1 MEDIUM-HIGH (§11.4), 1 MEDIUM (§11.6), 1 LOW (§11.2). Three operator/Oracle escalation points named.

---

## §7. Surface additions

No §11.13 surfaced during walk. Spec covers the architectural surface cleanly. Forward-filed items live in §12 of spec.

**Small annotations for Phase 3 implementation:**

- §1b instance count audit at Phase 3 (count = 6 per CANON_BOOTSTRAP §1.K, not 5).
- Per-domain confidence-tier threshold calibration files §11 candidate at v0.1 if observed-friction surfaces tuning need.
- Locked-spec amendment doctrine candidate (§11.6 implication) — Oracle review filed at Inversion lock if §11.6 confirms (a).

---

## §8. Handoff

| Item | Value |
|---|---|
| **Review doc** | `/home/jordaneal/virgil-docs/specs/CONVERSATIONAL_RUNTIME_INVERSION_V0_REVIEW.md` (this file) |
| **Spec under review** | `/home/jordaneal/virgil-docs/specs/CONVERSATIONAL_RUNTIME_INVERSION_V0_SPEC.md` (DRAFT) |
| **Decisions walked** | 12 of 12 |
| **Confidence split** | 8 HIGH / 1 MEDIUM-HIGH / 1 MEDIUM / 1 LOW |
| **Operator + Oracle escalation points** | §11.2 (§1a extension — Oracle territory), §11.6 (locked-spec amendment precedent — Oracle review), §11.4 (ship-size economics — operator) |
| **§11.6 discrepancy resolution** | Spec drafted under (a) per operator override; walk confirms (a) defensible with Oracle precedent flag |
| **§11.13 surfaced** | None |
| **Spec→LOCKED action on operator review** | If operator locks all 12 recommended defaults, spec flips DRAFT → LOCKED. §11.2 and §11.6 LOW/MEDIUM confidences may invite re-walk before lock; ship-size economics at §11.4 may invite refinement. |
| **Next session** | **Session 3 = Phase 3 implementation. Sonnet medium per WWC cadence.** 21 prior §59 instances + N-10 recent ship; per-domain parsers + integration at `discord_dnd_bot.py:2664` and `:2789` + `#dm-aside` suggester cards (per R4 format) + `dnd_commitments` schema (if §11.4 (a) locks) + telemetry per §3.4 + closed-loop tests. |
| **Doctrinal weight** | Largest direction-lock since "controlled canonization of stochastic generation." Inversion lock makes BIOS/OS/UI metaphor + litmus test + DM-burden-co-equal framing project-wide reference points. |
