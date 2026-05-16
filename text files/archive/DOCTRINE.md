

---

## §1b — Running-list update (post-N-10, post-S67 audit)

§1b validated-suggester pattern (bot proposes, deterministic gate validates, DM approves, system executes) now has five anchored project instances. Filed as running-list observation per S67 audit (B) lean — NOT promoted to formal §1b.1 sub-pattern.

**Project instances:**

1. **Track 6 #5.1 SRD suggester** (S26) — bot proposes SRD-rules-based action; deterministic gate validates against SRD index; operator approves via slash; engine executes.

2. **S41 NPC State-Sync** (NPC-side state confirmation via `#dm-aside` card; deterministic gate validates structured-FK match; operator approves via slash; engine executes write).

3. **Quest Layer v0.1** (S57 cosine-similarity drop) — quest-offer suggester proposes via `#dm-aside`; deterministic gate is canonical `/quest offer accept <id>` slash; LLM renders offer narrative after operator-slash. Earlier v0 ship had cosine-similarity paste-detection as auxiliary; dropped per "too mechanical" UX feedback. The drop crystallized "no calibration-bound auxiliary" as infrastructural discipline.

4. **Composition Layer v0** (S61) — quest-act-transition suggester proposes via `#dm-aside`; deterministic predicate-match gate validates scene-state against skeleton-authored act predicates; operator approves via slash. Shipped Reading-2-direct (no cosine-similarity layer); inherited from S57 crystallization.

5. **N-10 Canon Bootstrap Bot v0** (post-S68) — per-element card proposals via `#dm-aside` (faction → dispatcher NPC → quest → quest acts → location); deterministic gate is canonical `/bootstrap accept|skip|reroll|manual` slash + file-write integrity check; operator approves per-card; engine + skeleton.md write on approval.

**Observed sub-pattern (NOT formally anchored):** All five instances use a *deterministic-validator suggester* — the validator gate is structured-signal-or-file-integrity, never calibration-bound (cosine-similarity, LLM-classifier-confidence-threshold, fuzzy-match). The S57 cosine drop is the explicit project-side rejection of calibration-bound auxiliary. Future §1b instances inherit this discipline as observed pattern; formal sub-anchor pending sixth instance with a distinct validator shape (Inversion v0's narration-detection-as-deterministic-gate may be that sixth instance, surfacing the question whether sub-anchoring earns its slot).

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

## §76 — Four-property test refinement candidates (filed post-S67 audit)

S67 §76 audit surfaced two new doctrinal property candidates beyond the existing four. Filed for amendment consideration post-S68 architecture stabilization.

**Existing four properties (LLM-writable + persisted + retrieved + narratively-inferential):** unchanged; all still load-bearing for the recursive-hallucination loop detection.

**Candidate 5th property — rate-unlimited write.** Distinguishes urgent 4/4 (LLM writes every turn) from background 4/4 (LLM writes on gated event). Three surfaces audited at S67 hit 4/4 but were rate-limited via promotion gates or distance cutoffs — the gates make them "slower-rate contamination loops than `current_scene` was." Rate-unlimited write is the property that elevates a 4/4 surface from "audit-worthy" to "urgent close."

**Candidate 6th property — verbatim re-injection.** Distinguishes 4/4 surfaces where the LLM-written content re-enters prompt context verbatim from surfaces where it re-enters as signal/marker. `current_scene` was verbatim re-injection (entire prior narration paragraph rendered as `=== CURRENT SCENE ===` block). Consequence summary is signal/marker (severity-capped 1-3 directive lines, not full prose). Verbatim re-injection is the property that makes the recursive loop tight.

**6-property full test (proposed):** A field hits §76 contamination risk when (1) LLM-writable + (2) persisted + (3) retrieved + (4) narratively-inferential, with urgency tier elevated by (5) rate-unlimited write and (6) verbatim re-injection.

**Anchoring:** filed for operator + Oracle pass post-N-3.1 ship (alongside F-64 anchoring), or sooner if Inversion v0 surfaces a §76 audit that exercises the refined test. Property additions are doctrine-level changes requiring operator confirmation; planner discipline files them as candidates rather than appending unilaterally.

---

## §1a candidate doctrinal extension (filed for Inversion v0 spec)

Conversational-Runtime Inversion v0 sketch surfaces a §1a doctrinal extension question (§11.2 candidate at Inversion spec time). Three candidate shapes:

**(i) §1a amendment in-place.** Add clause naming narration-detection-with-deterministic-parser as equivalent to operator-slash for binding-decision restriction. Strict-literal extension precedent (§14.1 sub-numbering pattern).

**(ii) §1c new top-level doctrine.** File new top-level number codifying detection-from-narration-is-deterministic-gate. Parallels §1a + §1b as third-of-three companion doctrines.

**(iii) §1a.x sub-numbering.** Anchored extension under §1a's number. Acknowledges the extension is doctrinally derived from §1a's intent.

**No confident lean** per Inversion sketch §11.2. Operator + Oracle territory at Inversion spec lock session. Decision affects how downstream architectural work cites the doctrine.

Filed here as the open doctrinal-extension question awaiting Inversion review pass.
