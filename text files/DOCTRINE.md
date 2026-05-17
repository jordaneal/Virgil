

---

## §1a.x — Deterministic-gate authority via narration-detection (S73 anchored)

**Status:** ANCHORED at S73 Inversion v0 Phase 3a (quest-acceptance closed-vocab parser ship).

§1a's binding-decision restriction extends to detection-from-narration: when a closed-vocabulary parser produces a high-confidence structured signal from narration content, the parser output is structurally equivalent to an operator-typed slash for the purposes of §1a's gate. The LLM's narration is interpreted by deterministic Python code (frozenset verb matching + whole-word tokenization + structured-signal co-occurrence + cross-turn LRU dedup); the LLM does not decide binding state. The operator approves binding via paste of the suggested slash (per §1b validated-suggester pattern; per §F-59 the bot never auto-emits).

**Constraint per §14.1 sub-numbering precedent:** §1a.x extends §1a's scope through a new input surface (narration-detection rather than operator-slash). §1a's strict reading is preserved unchanged; §1a.x names the bounded extension. The four prerequisites for §1a.x equivalence:

1. **Parser is closed-vocabulary** — frozenset of verbs/phrases; no LLM classification, no calibration-bound matching (cosine-similarity, fuzzy-match, etc.). New verbs land via spec amendment, not silent additions.
2. **Structured-signal co-occurrence** — high-confidence routing requires the verb + a matching structured signal from engine state (e.g., quest title token-match against `dnd_quests WHERE status='offered'`). Verb-only fires route to medium-confidence suggester.
3. **Writer remains engine-side and §17-disciplined** — the parser produces a structured proposal; engine writers (`quest_accept`, `quest_offer`, etc.) remain the single write paths.
4. **Low-confidence routes to suggester for operator approval** — the operator paste-detection gate (§1b) acts as the binding-decision step for medium-confidence; high-confidence still requires operator paste (no auto-emit per §F-59).

**Why §1a.x rather than §1a in-place amendment, §1c new doctrine, or §76 footnote:**
Mirrors §14.1's established sub-numbering pattern. §1a anchor preserved (no doctrine-statement bloat). §1a/§1b two-doctrine pairing unbroken (avoids splitting to §1a/§1b/§1c). The extension is doctrinally derived from §1a's intent (no LLM-decided binding state), not a new separable rule — sub-numbering honors that derivation. Operator + Oracle locked at Inversion v0 review (§11.2 (iii) at S71).

**Architectural anchor instance (first):** S73 Phase 3a quest-acceptance closed-vocab parser (`quest_acceptance_parser.py` + detection insertion at `discord_dnd_bot._extract_and_persist_world` stage 3).

**Anchored instances post-S78** (5 narration-detection parser surfaces):

1. `quest_acceptance` (pre-LLM only per S73.1 lesson) — S73 anchor.
2. `transaction_completion_pre_llm` (player-intent surface) — S78.
3. `transaction_completion_post_llm` (LLM-paraphrase surface) — S78.
4. `loot_drop_player` (pre-LLM player-intent surface) — S78.
5. `loot_drop_llm` (post-LLM LLM-reveal surface) — S78.

All five register against the §1b.1 aggregator (`clarification_handshake.aggregate_parser_outputs`) under unified `ParserResult` shape. Each preserves the four §1a.x prerequisites: closed-vocab, structured-signal co-occurrence, engine-side writer §17 discipline, low-confidence routes to suggester for operator approval.

---

## §1b.1 — Clarification handshake via #dm-aside (ANCHORED at S77)

**Status:** ANCHORED at S77 Inversion v0 Phase 3 implementation ship. Formal sub-clause of §1b per §76.1/.2 sub-numbering precedent.

Sits between §1a.x's *parser fires* and §1b's *operator pastes*. When a closed-vocab parser produces an ambiguous structured signal — multi-domain match, cross-domain semantic equivalence, or 1-parser-MEDIUM with structural markers — §1b.1 inserts an operator-disambiguation step before §1b's validated-suggester gate fires.

**Architecture (final post-S77):**

- **Primary path: M-DELAYED in-fiction clarification.** Engine sets `pending_clarification` flag on `dnd_scene_state` (JSON column, single-writer per §17 via `clarification_handshake.set_pending_clarification`); LLM narrates scene continuing WITHOUT finalizing (per `compute_pending_clarification_directive` injected into `build_dm_context` — 24th §59 sibling); parser fires second-pass on operator's next utterance. HIGH resolution commits via §17 path. Still-ambiguous escalates to Layer A or Layer B fallback.

- **Fallback Layer A: richer suggester card.** Cross-domain enumerable case (≥2 parsers ≥MEDIUM with payload candidates). Multi-paste card to `#dm-aside` (per-candidate paste options + explicit skip). Operator paste IS the §F-59 gate.

- **Fallback Layer B: bidirectional OOC handshake.** No clean candidate enumeration (≥2 parsers ≥MEDIUM, non-enumerable payloads). Free-text question to `#dm-aside` + `bot.wait_for` listener (5-min timeout, channel + author + post-timestamp + !bot filter). Operator OOC reply IS the §F-59 gate per council Shape A.2 lock — naming "operator-deliberate-commit" as authority claim. 2-iteration recursion cap (binary forced-choice card at iter 2; manual decision at iter 3).

**Decentralized parser-output aggregation.** Parsers own ambiguity detection per §1a.x. Aggregator reads parser outputs (HIGH/MEDIUM/LOW + `markers_present`), applies Stage 1 routing rule, never inspects raw markers. Domain-agnostic flagship primitive; v0 wiring covers `quest_accept`; Phase 3b registers `transaction_completion` + `loot_drop` against existing aggregator without refactor.

**M-IMMEDIATE explicitly rejected at v0.** Council pressure-test record across three passes (Oracle/GPT/Gemini) surfaced that the §1a defense of M-IMMEDIATE conflated LLM-narration-as-content (non-§1a-violating; project's existing LLM-mediated workflow) with LLM-narration-as-gate (§1a-violating; not what M-DELAYED does). M-DELAYED preserves §1a cleanly AND honors the Conversational-Runtime Inversion direction-lock litmus ("would a good human DM stop the session to operate software for this?" — answer for M-DELAYED: no, DM clarifies in-fiction; answer for M-IMMEDIATE: yes, OOC menu every ambiguous utterance).

**§F-59 doctrine-refinement candidate filed forward:** Naming "operator-deliberate-commit" as the authority claim, with "paste of slash" and "OOC reply" as instantiating surfaces. Lands at next §F-59-touching ship; not scope-expanded at this anchoring.

**Empirical watch surfaces (per GPT post-council Flag 1+2+4):**
- Per-parser MEDIUM/HIGH/LOW fire-rate rolling-window snapshot (`parser_calibration_snapshot`, every 50 invocations) — calibration drift detection.
- Per-scene clarification frequency (planned `clarification_density_snapshot` at scene transition) — operationalization-of-player-speech detection.
- LLM in-fiction compliance failure tracking (`clarification_in_fiction_compliance_failure`) — empirical signal for prompt tuning when LLM narrates action as completed despite pending directive.

**First firing instance:** S77 ships infrastructure clean (aggregator + directive + schema + telemetry + cards + listener); S78 ships the parsers that activate the M-DELAYED primary path empirically. Transaction-completion + loot-drop parsers register against the §1b.1 aggregator with full `markers_present` discrimination — covering player-intent (pre-LLM) and LLM-completion / LLM-reveal (post-LLM) narration loci. Live verify Scenarios A (transaction direct), C (loot direct), E (multi-domain Layer A), F (M-DELAYED primary) at S78 ship's post-restart verification. Actual production first-firing campaign + utterance documented at operator's live-verify completion.

---

## §1b — Running-list update (post-N-10, post-S73 anchor, post-§1b.1 sub-clause)

§1b validated-suggester pattern (bot proposes, deterministic gate validates, DM approves, system executes) now has six anchored project instances + §1b.1 sub-clause covering the clarification surface across parsers. Filed as running-list observation per S67 audit (B) lean.

**Project instances:**

1. **Track 6 #5.1 SRD suggester** (S26) — bot proposes SRD-rules-based action; deterministic gate validates against SRD index; operator approves via slash; engine executes.

2. **S41 NPC State-Sync** (NPC-side state confirmation via `#dm-aside` card; deterministic gate validates structured-FK match; operator approves via slash; engine executes write).

3. **Quest Layer v0.1** (S57 cosine-similarity drop) — quest-offer suggester proposes via `#dm-aside`; deterministic gate is canonical `/quest offer accept <id>` slash; LLM renders offer narrative after operator-slash. Earlier v0 ship had cosine-similarity paste-detection as auxiliary; dropped per "too mechanical" UX feedback. The drop crystallized "no calibration-bound auxiliary" as infrastructural discipline.

4. **Composition Layer v0** (S61) — quest-act-transition suggester proposes via `#dm-aside`; deterministic predicate-match gate validates scene-state against skeleton-authored act predicates; operator approves via slash. Shipped Reading-2-direct (no cosine-similarity layer); inherited from S57 crystallization.

5. **N-10 Canon Bootstrap Bot v0** (post-S68) — per-element card proposals via `#dm-aside` (faction → dispatcher NPC → quest → quest acts → location); deterministic gate is canonical `/bootstrap accept|skip|reroll|manual` slash + file-write integrity check; operator approves per-card; engine + skeleton.md write on approval.

6. **Conversational-Runtime Inversion v0 Phase 3a — quest-acceptance narration-detection** (S73) — closed-vocab parser fires on post-LLM narration containing acceptance verbs (`accept` / `agree` / `pledge` / `commit` / phrasal `I'll take` / `count me in` etc.); deterministic gate is structured-signal co-occurrence (quest title token-match against `dnd_quests WHERE status='offered'`); three-tier confidence routing (HIGH: verb + title match → `#dm-aside` card with pasteable `/quest accept <id>`; MEDIUM: verb only → `#dm-aside` card listing offered quests; LOW: silent); operator approves via paste; `quest_accept` engine writer fires on slash. Distinct validator shape vs prior five — narration-detection-as-deterministic-gate via §1a.x anchored at this ship.

**Observed sub-pattern (NOT formally anchored):** All six instances use a *deterministic-validator suggester* — the validator gate is structured-signal-or-file-integrity, never calibration-bound (cosine-similarity, LLM-classifier-confidence-threshold, fuzzy-match). The S57 cosine drop is the explicit project-side rejection of calibration-bound auxiliary. Future §1b instances inherit this discipline as observed pattern.

**Sub-anchor question (S73 update):** Inversion v0 Phase 3a's narration-detection-as-gate is the predicted "sixth instance with a distinct validator shape" the post-S67 DOCTRINE.md filed. Formal §1b.1 sub-anchor remains operator-level decision; S73 lands the sixth instance with the §1a.x sub-numbering doctrine (above) capturing the structurally-distinct validator shape without scope-creeping §1b itself. Phase 3c (S75) NPC-commitment-utterance suggester ships the seventh instance; question whether 7 instances earn formal §1b.1 sub-anchor returns at that ship.

**Why running-list not sub-anchor:** Operator-level decision per S67 audit. Formal sub-anchoring invites taxonomy expansion ("does this ship a new §1b.N?") and names something the project doesn't intend to support as alternative pattern (calibration-bound validators). Running-list keeps the cross-instance discipline visible without scope-creeping the doctrine.

---

## §F-64 — Narration-bypass state desync (ANCHORED at S81)

**Status:** ANCHORED at S81. Cluster: 7 instances across S51–S78. S79 walk + S80 council pressure-test produced the framing. Three-reviewer convergent override on prior candidate phrasing — Gemini Q1 reworded to remove the inadvertent §1a-violation reading.

**One-line:** LLM narrates a mechanical/canonical state change that bypasses deterministic parsers; state desyncs across turns.

**Structural framing.** §F-64 names the empirical failure mode where LLM-side narration asserts a state mutation that no deterministic surface (parser + §17 writer + read-back directive) captures. The engine MUST NOT enforce LLM-claimed mutations per §1a; §F-64 names what occurs when the LLM's unbacked claim produces narrative-runtime divergence that compounds across turns. The failure is structural absence of a writer-side surface, not §1a violation by the LLM — the LLM is doing its job (narrating); the engine is structurally unequipped to anchor the narrated claim.

**Architectural relationship to surrounding doctrine:**

- **§1a** — LLM never decides binding state (root invariant). §F-64 is the empirical failure mode that occurs when LLM narration attempts to author state §1a forbids it from deciding. §1a is the rule; §F-64 names the surface where the rule's structural absence (no enforcement) lets the LLM's narration drift past the engine.
- **§1a.x** — Deterministic-gate authority via narration-detection. §1a.x IS the architectural closure for §F-64's pattern — parser detects intent, §17 writer commits, engine read-back anti-gaslights subsequent narration. Doctrine-pair shape (failure-mode + architectural-response), parallel to §76↔§17 / Path A retirement.
- **§1b / §1b.1** — Validated-suggester + clarification handshake. Extend §1a.x's closure when parser-detection is ambiguous (operator gate via paste or OOC reply).
- **§76** — Recursive-hallucination loop. §F-64 is one-way (narration → claim → no enforcement); §76 is two-way (narration → claim → re-injection → drift loop). Adjacent failure modes with distinct architectural responses (§F-64 ↔ §1a.x parser; §76 ↔ closure via Path A retirement or Path B structural break).
- **§77** — Atmospheric continuity / two-layer enforcement. §77 anchors instruction-side (MUST/MUST-NOT) + information-side (context-block suppression) enforcement for atmospheric directives. §F-64 differs in scope (any state-bearing surface, not just atmospheric) and mechanism (writer-side absence, not instruction-side compliance). §82 candidate names the instruction-side compliance failure mode (see `FAILURES.md` §82).
- **§F-44** — Cross-axis bleed (chroma campaign-scoped vs NPC extractor name-global). §F-44 is substrate-level bleed; §F-64 is narration-asserted-state-without-write. Cousin doctrines. F-44 instances can manifest as F-64-shape behavior downstream (e.g., S78 Bishop's bakery NPC bleed → LLM narrates Mara at new location based on bled-in chroma context).

**Closure pattern:** parser + §17 writer + read-back-for-anti-gaslight directive injection. Each anchored instance follows this shape:

| # | Instance | Surface | Closure |
|---|---|---|---|
| 1 | S53 §1.F.c NPC was_new | LLM-extracted activity-signal claims state mutation; engine reset trusts the claim | Drop the LLM-extracted signal from §1.F set (engine stops listening to unreliable LLM claim) |
| 2 | S63 §1.F.e consequence-DM-side | Same shape, never wired | Pre-emptive doc-only drop |
| 3 | S66 F-031 quest delivery silent inventory fail | Narration claims reward delivered; writer fails silently on empty-string | Fix writer's empty-string sentinel + party-stash bucket + truthful aside |
| 4 | S66 F-035 loot evaporation | Narration describes loot drop; engine never auto-claims | Auto-claim via verb-vocabulary deterministic parser (§1a.x application) |
| 5 | S68 N-4 NPC pronoun drift | Narration uses pronouns; engine has no pronoun anchor | `dnd_npcs.pronouns` column + first-occurrence lock via §17 single-writer + HARD STOP RULE 7 |
| 6 | S78 baker descriptor→name pronoun gap | Anonymous descriptor "the baker" turn 1 → named "Mara" turn 2; N-4 keys on names, descriptor produces no NPC row | TBD — N-4 v1.x ship surface (alias descriptors to subsequent names; lock pronouns from descriptor context) |
| 7 | S78 LLM price invention + cross-turn inconsistency | LLM narrates 1gp/loaf turn 1, 3gp/loaf turn 2; engine has no price/economic commitment anchor | TBD — N-3.1 commitment-tracking ship surface (was originally filed as F-64 sixth-instance host; surfaces empirically before architectural ship) |
| 8 | S51 player-narrative-authority drift | LLM caved on player premise contradicting scene canon; materialized merchant interior INSIDE training ground; subsequent narration treats LLM-authored state as ground truth | TBD — scene-boundary enforcement surface (filed at S51 as candidate "§77 sub-section"; subsumed into §F-64 cluster at S81 anchor per R2 audit) |

**Future instances inherit §1a.x architectural response.** When new state-bearing surface ships, planner verifies §F-64 closure: closed-vocab parser detects intent; §17 writer commits; read-back directive anti-gaslights subsequent LLM narration. Surfaces shipping without this closure pattern earn §F-64 instance status until addressed.

**Sister-doctrine candidate filed:** §82 — Instruction-Side Compliance (FAILURES.md §82 candidate). Where §F-64 names writer-side absence (engine lacks the surface), §82 names instruction-side compliance failure (engine HAS the directive surface; LLM violates compliance). Two architecturally-independent design-time choices, not property-axes of one mechanism. §82 anchoring deferred per S80 council convergent (insufficient empirical maturity at 2 instances; threshold requires 3 structurally-identical instances across distinct directive surfaces).

---

## §76 — Recursive-hallucination memory loop / four-property latent-canon test

**The 4-property base test (anchored S39):** A persisted field hits §76 contamination risk when ALL FOUR properties hold:
1. **LLM-writable** — LLM output reaches the field (directly or via extractor)
2. **Persisted** — field survives across turns (DB, file, chroma collection)
3. **Retrieved** — field is read back into subsequent prompt context
4. **Narratively-inferential** — field content informs the LLM's narrative generation, not just structural metadata

A 4/4 surface forms a recursive contamination loop: LLM writes → persists → LLM reads → LLM writes drift-influenced output → persists drift → loop tightens. Closure shape (drop the field; convert to deterministic-only write; route reads to non-LLM-derived sources) per anchored instance.

**Urgency classification (6-property test, anchored S72.2).** The 4-property test alone is **insufficient** for urgency classification. A 4/4 surface identifies §76 contamination risk; it does NOT identify how tightly the recursive loop closes. Properties 5+6 (rate-unlimited write, verbatim re-injection) evaluate loop closure: tight loops (6/6) require structural closure (retrieval filter, write-side gating, or full retirement); loose loops (4/6) tolerate mitigation. **Future §76 audits MUST walk the full 6-property check on any 4/4 surface.** Running the 4-property test alone risks classifying a 6/6 surface as "mitigated" when the mitigation addresses only one axis of the loop. S67 audit precedent: chroma DM-stores classified as distance-cutoff-mitigated when distance cutoffs filter retrieval-noise without breaking verbatim recursive re-injection — the loop's tightness was unaddressed. S72.2 corrected.

### §76.1 — Rate-unlimited write property (sub-clause anchored S72.2)

A 4/4 §76 surface where the LLM writes every turn (no event gating, no rate limiting at the writer layer) elevates the contamination loop's iteration frequency to maximum. Rate-unlimited writes make recursive contamination operationally fast — every iteration of the LLM produces material that re-enters the LLM's input on the next iteration. Distinguishes urgent 4/4 surfaces from background 4/4 surfaces where rate is structurally gated.

**Anchored at S72.2 chroma DM-stores closure** — first empirical 6/6 surface. `chroma_store('dm', response)` at `discord_dnd_bot.py:3526` fired every DM turn with no gating. Pre-closure, the rate was bounded only by turn cadence (every DM narration → one write).

Sibling-property: contrast with `consequences.summary` (rate-limited via `consequence_extractor` invocation gating + promotion thresholds compound — `PROMOTION_SURFACE_COUNT=3` + `PROMOTION_DISTINCT_TURNS=2` + `PROMOTION_AGE_TURNS=10`); contrast with `dnd_npcs.description` LLM-write fold (rate-limited transitively through consequence-promotion gates).

### §76.2 — Verbatim re-injection property (sub-clause anchored S72.2)

A 4/4 §76 surface where the LLM-written content re-enters prompt context verbatim (or near-verbatim, e.g., truncated-but-unsummarized) makes the recursive contamination loop tight. The LLM reads its own prior output as if it were canonical input; drift compounds without any compression or signal-reduction layer to break the cycle. Distinguishes verbatim-re-injection surfaces from signal/marker re-injection surfaces (severity-capped directive lines, structured-tag references) where the loop's re-injection content has been compressed into form that cannot drive open-form drift.

**Anchored at S72.2 chroma DM-stores closure** — first empirical 6/6 surface. `chroma_search` at `dnd_engine.py:182-188` (pre-closure) injected `f"[{ts}] DM: {doc[:200]}"` — the 200-char truncation does NOT summarize; it merely cuts. The injected text was the LLM's prior narration, formatted as "[YYYY-MM-DD] DM: <first 200 chars of prior narration>", read by the LLM as if it were canonical past-event context.

Sibling-property: contrast with `compute_consequence_directive` (signal/marker form — severity-capped 1-3 directive lines, structured taxonomy, not open-form prose); contrast with `[promoted: kind] summary` append into `dnd_npcs.description` (tagged prose, partially-verbatim of summary, borderline — closer to verbatim than signal/marker but compressed by promotion-gate severity-cap).

### §76 — Project instance list

Four anchored project instances (post-S72.2):

| # | Surface | Anchor session | 4/4? | 5+6 tier | Closure |
|---|---|---|---|---|---|
| 1 | `dnd_scene_state` (5 freetext columns: `location`, `established_details`, `focus`, `open_questions`, `last_scene_change`) | S22 #2 → S32 → S36 → S39 anchor | 4/4 | 6/6 (pre-S39: rate-unlimited write + verbatim `=== CURRENT SCENE ===` re-injection) | Path A — full retirement (Ship 2 / S39 dropped 5 columns + 3 dead-column housekeeping) |
| 2 | `consequences.summary` (S1) | S67 audit | 4/4 | 4/6 — mitigated, not urgent | Path B-mitigation in place (extractor-invocation gated + signal/marker re-injection via `compute_consequence_directive`); no closure needed per 6-property test |
| 3 | `dnd_npcs.description` LLM-write fold (S2) | S67 audit | 4/4 | 4-5/6 — mitigated, borderline | Path B-mitigation transitive (only `maybe_promote_consequences` appends; gated by S1's promotion-gate triple); future Path A v0.x candidate: split notable_traits column to fully retire LLM-write into description |
| 4 | chroma DM-stores (S3) | S67.1 audit → S72.2 closure | 4/4 | **6/6** (rate-unlimited write + verbatim re-injection) | **Path B-structural** (S72.2) — write side `chroma_store('dm', response)` unchanged; read side `chroma_search` filters to `role='user'` only via native `where: {$and: [campaign_id, role:user]}` clause. Loop structurally broken on retrieval; DM substrate preserved for future architectural use |

**Closure-shape doctrine note:** Path A is full retirement (drop the surface entirely). Path B is structural break on either write or read side while preserving the other half (asymmetric closure). For 6/6 surfaces, Path A and Path B-structural are both acceptable; both break the loop. Path B-mitigation (gating without structurally breaking the loop) is acceptable for 4/6 surfaces but NOT for 6/6 — S67 audit precedent showed why.

---

## §59 — Pure-function sibling pattern instance audit (S72.1)

Canonical instance grep across `dnd_orchestration.py` + `dnd_engine.py` + `discord_dnd_bot.py` for `compute_*_directive` / `compute_*_suggester` / `render_*` / `build_*_context` / `compute_setup_plan`.

**Result: 24 instances** post-S77 (`compute_pending_clarification_directive` added; corrected from VIRGIL_MASTER's pre-S72 "17 at S70" and post-S72.1 "23").

**dnd_orchestration.py (22 instances):**

| # | Name | Line | Notes |
|---|---|---|---|
| 1 | `compute_pacing_directive` | :1540 | |
| 2 | `compute_central_thread_directive` | :1626 | |
| 3 | `compute_consequence_directive` | :1675 | Reads S1 §76 surface |
| 4 | `compute_commitment_directive` | :1954 | S19 player-action-honor escape directive; load-bearing across 5 references |
| 5 | `compute_init_directive` | :2140 | |
| 6 | `compute_persistence_directive` | :2338 | |
| 7 | `compute_loot_directive` | :2533 | |
| 8 | `render_state_footer` | :2683 | text + structural metadata |
| 9 | `compute_combat_redirect_directive` | :2889 | |
| 10 | `compute_time_directive` | :3016 | §76 read-side analogue first-instance per S51 |
| 11 | `build_advisory_context` | :3163 | Context-assembly sibling |
| 12 | `render_resolution_block` | :3815 | |
| 13 | `render_resolution_hardstop_echo` | :3889 | |
| 14 | `compute_combat_narration_directive` | :4054 | |
| 15 | `compute_scene_lifecycle_directive` | :4237 | |
| 16 | `compute_quest_offer_suggester` | :4329 | §1b 3rd-instance §59 sibling (Quest Layer v0.1) |
| 17 | `compute_active_quest_directive` | :4486 | |
| 18 | `compute_quest_act_suggester` | :4593 | §1b 4th-instance §59 sibling (Composition Layer v0) |
| 19 | `compute_composition_directive` | :4744 | |
| 20 | `compute_bootstrap_sequence_directive` | :5046 | |
| 21 | `compute_bootstrap_card_directive` | :5347 | §1b 5th-instance §59 sibling (N-10 Canon Bootstrap) |
| 22 | `compute_pending_clarification_directive` | :5493 | §1b.1 sub-clause directive composer (S77) |

**dnd_engine.py (1 instance):**

| # | Name | Line | Notes |
|---|---|---|---|
| 22 | `build_dm_context` | :6226 | Full prompt assembly; reads all directive outputs |

**discord_dnd_bot.py (1 instance):**

| # | Name | Line | Notes |
|---|---|---|---|
| 23 | `compute_setup_plan` | :1288 | S23 #3 — first non-orchestration §59 sibling |

**Naming-convention observation:** Four sub-shapes earned exception with reasoning:
- `compute_*_directive` (12 instances) — emits prompt-block text + signal dict tuple; dominant pattern
- `compute_*_suggester` (2 instances) — emits proposal candidate or None + signal dict; §1b-adjacent shape
- `render_*` (3 instances) — emits text + structural metadata for resolution/footer blocks
- `build_*_context` (2 instances) — assembles full prompt context from multiple directive outputs; super-sibling shape
- `compute_setup_plan` (1 instance, S23 #3) — naming exception; pre-dates the convention

**S72 undercount cause:** S72's recon regex (`^def compute_.*_directive\|^def render_`) missed `_suggester` siblings, `build_advisory_context`, `build_dm_context`, and `compute_setup_plan`. S72.1 audit corrects.

**VIRGIL_MASTER refresh:** §4 line 110 + §10 line 187 updated to 23 instances with file breakdown.

---

## §1a doctrinal extension — RESOLVED at S73 (Inversion v0 §11.2 lock)

Operator + Oracle locked (iii) §1a.x sub-numbering at Inversion v0 review (S71 Session 2). Anchored at S73 Phase 3a ship — see §1a.x section above. Candidate (i) §1a in-place amendment and (ii) §1c new top-level doctrine retired.
