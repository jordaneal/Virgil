

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

**Architectural anchor instance (first):** S73 Phase 3a quest-acceptance closed-vocab parser (`quest_acceptance_parser.py` + detection insertion at `discord_dnd_bot._extract_and_persist_world` stage 3). Subsequent Inversion v0 surfaces (transaction-completion at S74; loot-drop at S74; NPC-commitment-utterance at S75) inherit §1a.x equivalence per the same four prerequisites.

---

## §1b — Running-list update (post-N-10, post-S67 audit, post-S73 anchor)

§1b validated-suggester pattern (bot proposes, deterministic gate validates, DM approves, system executes) now has six anchored project instances. Filed as running-list observation per S67 audit (B) lean — NOT promoted to formal §1b.1 sub-pattern.

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

## §F-64 — Filed as anchored candidate (post-S68 cluster confirmation)

**Status:** CANDIDATE-WITH-FIVE-INSTANCES. See `FAILURES.md` §F-64 for full instance enumeration and architectural relationship to §F-08 / §76 / §1a.

**One-line:** Narration claims state change → engine does not enforce → state drifts. LLM narration alone is not a structural state-mutation signal.

**Closure pattern across five instances:**

| Instance | Surface | Fix shape |
|---|---|---|
| S53 §1.F.c | Activity-signal reset on LLM-extracted NPC was_new | Drop the LLM-extracted signal from §1.F set |
| S63 §1.F.e | Activity-signal reset on LLM-extracted consequence | Drop pre-emptively (never wired; doc-only) |
| S66 F-031 | Quest delivery silent inventory fail | Fix writer's empty-string sentinel bug + party-stash bucket |
| S66 F-035 | Loot evaporation across narration boundary | Auto-claim via verb-vocabulary deterministic parser |
| S68 N-4 | NPC pronoun drift across turns | Lock pronouns on first occurrence in dedicated column |

**Anchor candidate name (pending N-3.1 ship):** *"Narration-commit gap as systemic contamination surface."*

**Anchor pending at:** N-3.1 commitment-tracking multi-spec ship, which provides the architectural primitive demonstrating the structural response (narration-detection parser feeding single-writer with read-back-for-anti-gaslight directive). Anchoring at N-3.1 ship gives both the pattern and the response in operator-readable form.

If Inversion v0 folds N-3.1 per §11.4 candidate, doctrine anchoring walk happens at Inversion v0 lock instead of separate N-3.1 spec session. Same outcome via different surface.

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

**Result: 23 instances** (corrected from VIRGIL_MASTER's pre-S72 "17 at S70").

**dnd_orchestration.py (21 instances):**

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
