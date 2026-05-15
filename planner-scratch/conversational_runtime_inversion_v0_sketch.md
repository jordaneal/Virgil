# Conversational-Runtime Inversion v0 — Architectural Sketch

**Status:** v0 sketch — pre-spec. §11 candidates surfaced not locked.
**Date:** 2026-05-14
**Authorized:** Three-way convergent review (Claude planner + GPT + Gemini) locked direction post-S69-pause. Doctrinal direction-lock — largest since the original "controlled canonization of stochastic generation" framing.

---

## 1. What this is

**Mandate:** Invert the project's operator surface from slash-command-primary to narration-primary. Conversation becomes the UI layer; slash commands become BIOS — present but rare and structural, not the everyday operating surface.

**Load-bearing metaphor (carry forward as framing principle):**

- **Commands are BIOS** — system-level structural primitives. Boot, configure, reset, escape hatch. Operator types these when the system needs structural mutation that has no narrative path. `/newcampaign`, `/setcampaign`, `/bindchar`, `/setup`, debug surfaces.
- **Engine is OS** — deterministic state machinery underneath everything. §1a, §17, §76, §59 patterns all still operate. Engine remains the canonical write surface; LLM still never decides binding outcomes.
- **Conversation is UI** — operator and player both interact with the world through narration. The system *detects* intent from narration via deterministic parsers (closed-vocabulary or hybrid — §11 candidate) and routes to the deterministic gate. Slash exists as escape hatch and BIOS-tier control.

**The litmus test (carry forward):**

> "Would a good human DM stop the session to operate software for this?"

If yes, the surface stays as command. If no, the surface inverts to narration-detected.

By this test:
- `/newcampaign` — yes, a human DM does session-zero setup separately. Stays BIOS.
- `/bindchar` — yes, character-sheet binding is session-zero work. Stays BIOS.
- `/quest accept <id>` — no, a player just says "I'll take the job" and the DM continues. Inverts.
- `/faction stage edit <id> <stage> <description>` — emphatically no. Inverts or migrates to bootstrap/aside flow.
- `/travel destination:"X" duration:"1 hour"` — borderline. DM might say "we travel three hours to the Old Mill" naturally. Inverts as primary surface; slash stays as deterministic escape hatch.

**Why this is doctrinal direction-lock, not feature work:**

The convergent review surfaced that the slash sprawl is a symptom of a deeper architectural framing. We've been treating operator surface as primary deterministic control because §1a says LLM doesn't decide binding state. The inverted framing keeps §1a intact — *detection* from narration is the deterministic gate, not LLM decision. The engine reads operator narration and player narration through the same parsers; deterministic verbs and structured signals route to engine writers; LLM is still excluded from binding state writes.

This means the slash surface that the project has been accumulating across every architectural ship (Quest, Composition, Bootstrap, S69-paused factions) is mostly *not load-bearing*. Most of those slashes can invert to narration-detected with the deterministic gate intact.

---

## 2. What this is NOT

- A removal of slash commands entirely. BIOS-tier and escape-hatch slashes remain.
- A weakening of §1a. The doctrinal *extension* keeps the binding-decision restriction; the gate moves from "operator slash" to "engine narration parser feeding deterministic writer."
- A rewrite of existing engine writers. `npc_upsert`, `quest_upsert`, `quest_act_upsert`, `faction_upsert` etc. all remain. What changes is what *fires* them — narration-detection rather than slash handler.
- An LLM-decides-state pivot. The LLM still narrates only; engine still writes only. The parser between them is the new architectural surface.
- A v0.x emergent-surface speculation. Surfaces that don't have observed friction stay filed-forward.
- An immediate migration of every existing slash. v0 picks a narrow first-migration set (§11 candidate); other surfaces migrate in observed-friction order.

---

## 3. The DM-burden / player-burden framing

Convergent-review insight: the slash-burden problem isn't just player UX. It's *equally* a DM-burden problem.

Current state: when player narrates "I'll buy the sourdough," the operator (Jordan, in DM role) must mentally translate to `!game coin -5cp`, type it, watch Avrae respond, then narrate. The DM is operating software to render a transaction the player described in plain language.

Inverted state: player narrates "I'll buy the sourdough." Engine narration parser detects transaction intent (closed verb vocabulary + price context per N-1 hint extractor precedent). Deterministic suggester proposes `!game coin -5cp` in `#dm-aside` (or auto-executes per §11 lock on bot→Avrae writes — same §F-59 question that surfaced in N-6 filing). DM approves implicitly via continuing narration, or explicitly via a single-character slash if friction surfaces.

**The litmus test applies symmetrically.** A good human DM doesn't stop the session to type software commands either. The inversion serves both roles.

This also reframes what gets built first. Inverting player-side surfaces (quest acceptance, travel intent, transactions) AND DM-side surfaces (compression intent, faction tick decisions, NPC commitment authoring) happen in the same architectural arc, not separate ships.

---

## 4. What surfaces it extends, what's new

**Reuses (no schema change in scope at v0):**
- All existing engine writers (`npc_upsert`, `quest_upsert`, `faction_upsert`, etc.) — §17 single-writer discipline holds; only the *caller* of these writers changes
- All existing `dnd_*` tables — schema unaffected
- `#dm-aside` channel — remains the suggester surface for ambiguous detection
- N-1 hint extractor precedent — closed-vocabulary verb + price detection pattern is the load-bearing architectural template

**Proposed new:**
- Narration-detection layer in `dnd_orchestration.py` — new §59 sibling family (one per detection domain: transaction, quest-intent, travel-intent, compression-intent, etc.)
- Per-domain parsers: closed-vocabulary verb sets + structured-signal co-occurrence requirements (matching N-1 hint extractor's discipline)
- Detection-confidence-tier routing — high-confidence detection routes to deterministic writer; low-confidence routes to `#dm-aside` suggester for operator approval; no-detection stays silent
- New telemetry primitives: `narration_intent_detected:` per fire, `narration_intent_routed:` per detection-to-action, `narration_intent_suppressed:` per low-confidence-without-suggester

**Doctrinal additions (§11 candidate — extension shape):**
- §1a extension or §1c new doctrine — codifying narration-detection-as-deterministic-gate. Names that detection from narration is structurally equivalent to operator slash for the purposes of §1a's binding-decision restriction (LLM still never decides; deterministic parser + structured signals does)

**Not new:**
- No new ChromaDB collection
- No bot→Avrae writes (the §F-59 question remains — bot→Avrae auto-execution is the same N-6 surface filed forward; inversion doesn't resolve it, only sharpens its visibility)
- No LLM classifier for intent (closed-vocabulary deterministic parsers only at v0; LLM classification is v1.x candidate if narrow vocabulary surfaces friction)
- No removal of existing slashes at v0 (inverted surfaces gain narration paths; slashes remain operational as escape hatch)

---

## 5. Detection vocabulary architecture

**Three candidate patterns** for per-domain parsers, with leans:

### (a) Closed-vocabulary verb-and-signal parsers (lean at v0)

Per-domain regex/grammar over a closed verb set + structured-signal co-occurrence. Same shape as N-1 hint extractor and S66 F-035 loot auto-claim verb vocabulary.

Example — quest-acceptance detection:
- Verb vocabulary: `accept`, `take`, `agree to`, `do it`, `count me in`, `I'll do`, `I'll take`
- Required signal: active quest offer in `dnd_quests WHERE status='offered'` matching player text via canonical-name or first-name match
- Confidence tier: high if verb + matching quest reference both present; medium if only verb; low if neither

**Pros:** Deterministic, inspectable, fast, doctrinally clean (§1a clean — no LLM classification). Inherits proven precedent from N-1 and S66 verb vocabularies.
**Cons:** Brittle to phrasing variation. Vocabulary maintenance burden as edge cases surface. Misses creative phrasings.
**Lean: v0 ships with closed-vocabulary parsers per domain.**

### (b) LLM-classifier intent extraction (filed v1.x candidate)

LLM classifies player and operator turns into structured intent categories with confidence scores. Engine routes per classification.

**Pros:** Robust to phrasing. Captures intent the operator didn't anticipate.
**Cons:** Re-introduces LLM as decider — §1a tension. Calibration drift risk. Determinism weakens.
**Filed v1.x; ships only if v0 closed-vocabulary surfaces friction the closed-set can't absorb.**

### (c) Hybrid — closed vocabulary primary + LLM classifier as fallback for low-confidence (filed v1.x)

Closed-vocab detects high-confidence cases; ambiguous turns trigger LLM classifier as secondary signal feeding `#dm-aside` suggester for operator approval.

**Pros:** Preserves determinism for clear cases; expands coverage for ambiguous ones; LLM never auto-executes.
**Cons:** More complex; calibration of "ambiguous" threshold; two systems to maintain.
**Filed v1.x; ships only after (a) operates at scale and friction shape becomes visible.**

---

## 6. Migration sequencing — which slashes invert at v0

The convergent review surfaced three tiers of slash surface:

### Tier 1 — BIOS (stays slash, not inverted)

Session-zero / structural / cross-cutting:
- `/newcampaign`, `/setcampaign`
- `/bindchar`
- `/setup` (whatever current shape exists)
- Debug / introspection surfaces (`/inventory`, `/quest list`, future `/status`)

These pass the litmus test as commands a human DM would type out-of-session or at session boundaries.

### Tier 2 — Authoring (mostly inverts, partial bootstrap-flow inheritance)

Operator authoring surfaces:
- `/quest add`, `/quest act add`, `/quest stage edit` — already partly absorbed by N-10 Bootstrap Bot
- `/faction set kind:`, `/faction stage edit` — pre-S69-lock surface; inverts at v0 if S69 ships under inversion discipline (most likely)
- `/bootstrap manual` field overrides — already an alias-layer; preserves under inversion as the override escape hatch

Authoring surfaces mostly already live in skeleton.md + bootstrap cards. Inversion finishes what bootstrap started.

### Tier 3 — Pacing / play surfaces (inverts at v0)

Active-play operator surfaces that fail the litmus test sharply:
- `/quest accept`, `/quest deliver`, `/quest fail`, `/quest abandon` — player narration carries clear intent for most cases
- `/loot drop` — narration "we leave the silver dagger behind" detects cleanly
- `/travel destination:"X" duration:"1 hour"` — operator narration "we travel three hours to the mill" detects cleanly
- `/compress` — operator narration "after the festival winds down" or "time passes" detects cleanly (carries existing Scene Lifecycle compression discipline)
- `/mode` — combat-mode transitions detected via Avrae init events; operator narration "rolls for initiative" detects cleanly

**Tier 3 inverts at v0.** Tier 2 partially inverts as cleanup. Tier 1 stays.

**§11 candidate:** which Tier 3 surfaces invert as primary v0 ship vs partial migration (e.g., `/quest accept` inverts at v0, but `/travel` waits for v0.1). Lean: ship the most-friction-visible Tier 3 inversions first — quest acceptance, loot drop, simple travel. File the others for observed-friction sequencing.

---

## 7. §1a doctrinal extension

The inversion requires a doctrinal framing for narration-detection-as-deterministic-gate.

**Three candidate shapes (§11 walks one):**

### (i) §1a amendment (in-place extension)

Add a clause to §1a explicitly naming narration-detection-with-deterministic-parser as equivalent to operator-slash for the binding-decision restriction. Strict-literal precedent (§14.1 sub-numbering pattern) applies.

### (ii) §1c new doctrine

File a new top-level doctrine number codifying "Detection-from-narration is a deterministic gate when (a) parser is closed-vocabulary or structured-signal, (b) writer remains engine-side and §17-disciplined, (c) low-confidence routes to suggester for operator approval." Parallels §1a + §1b as a third-of-three companion doctrines.

### (iii) §1a.x sub-numbering

Like §14.1 pattern — anchored extension under §1a's number. Acknowledges that the extension is doctrinally derived from §1a's intent, not a new separable rule.

**No confident lean.** Operator + Oracle territory. The decision affects how downstream architectural work cites the doctrine; matters for clarity in future spec sessions.

---

## 8. §1b validated-suggester interaction

**The question:** does narration-detection *replace*, *extend*, or *sit parallel to* the §1b slash-approval pattern as the canonical validated-suggester gate?

Three candidates:

### (a) Parallel surfaces (lean at v0)

§1b slash-approval remains the canonical pattern. Narration-detection sits parallel as a high-confidence shortcut — when detection confidence is high, route directly to engine; when low, fall through to existing §1b suggester (`#dm-aside` card + slash approval).

§1b doctrine unchanged. Inversion is a new surface, not a replacement.

### (b) Extension — narration-detection IS the §1b gate

§1b doctrine extends: "validated-suggester pattern" now includes both slash-approval and narration-detection as canonical gate forms. Both remain deterministic; both remain operator-driven (operator either types slash or narrates intent).

Existing §1b anchored instances (Quest Layer v0.1, Composition Layer v0, NPC State-Sync, Track 6 #5.1, N-10) all gain the narration-detection surface as additional gate form.

### (c) Replacement — narration-detection supersedes §1b

§1b deprecates. All validated-suggester flows route through narration-detection at v0.x. Slashes become escape-hatch-only.

**Lean (a) at v0.** Replacement is too aggressive; extension blurs the §1b anchor that just hardened across five instances. Parallel preserves the §1b pattern intact while opening the new surface for what the convergent review correctly identified as load-bearing fun-delta.

(b) is the likely v1.x position after observed friction shows narration-detection is reliably operating as the deterministic gate.

---

## 9. N-3.1 commitment-tracking — fold-in or separate?

N-3.1 (commitment-tracking layer; was N-3 HALTed at S68 for schema work) is the load-bearing instance of the narration-commit-gap doctrine candidate. The convergent review surfaced that this arc may merge into the inversion ship.

**Two candidates:**

### (a) N-3.1 folds into Inversion v0 — they're the same architectural problem

Inversion ships narration-detection for transactions; commitment-tracking writes detected commitments to a structured table; engine reads back for anti-gaslight rails. Same parser feeds both. Single architectural ship.

### (b) N-3.1 stays separate — different load-bearing concerns

Inversion is *surface*; N-3.1 is *commitment persistence*. They share detection infrastructure but solve different problems. Separating preserves architectural cleanliness.

**Lean (a).** The convergent review's framing — "the slash sprawl is a symptom of deeper architectural framing" — applies equally to commitment-tracking. N-3.1's HALT at S68 surfaced "need a commitment table"; Inversion v0 surfaces "need narration-detection infrastructure." These are the same need viewed from two angles.

**§11 candidate for spec session.** v0 sketch flags the question, doesn't lock.

---

## 10. S69 factions — return shape under inverted discipline

S69 was paused on slash sprawl concerns. Under Inversion v0:

- `/faction seed` — stays as BIOS-tier (skeleton.md migration trigger; structural, not play-time)
- `/faction tick <id>` — stays as escape-hatch deterministic surface (rare, operator-deliberate)
- `/faction list` — folds into future `/status` consolidation (Tier 1 BIOS-tier inspection)
- `/faction stage edit`, `/faction set kind:`, `/faction hold`, `/faction reset`, `/faction delete` — invert under §6 Tier 2 / Tier 3 discipline

Faction stage advancement under inversion: engine still ticks on engine-recognized events (travel, rest, scene compression — sketch §5 of S69 locked spec). Detection adds a new fire path — operator narration "the cartel grows bolder" or "word of the cartel reaches the council" detects faction-engagement signal and feeds predicate evaluation.

**S69 resumes after Inversion v0 lands** under the inverted slash discipline. Three slashes (seed, tick, list-via-status) instead of eight. Other operator surfaces route through detection + suggester.

§11 candidate: should S69's locked spec amend at Inversion v0 ship time, or open a v0.1 spec session at S69 resume to fold inversion discipline in?

---

## 11. Architectural questions for §11 decisions

Surfaced for operator lock before spec drafting. Leans named where confident.

1. **Detection vocabulary at v0.** (a) closed-vocabulary verb-and-signal parsers, (b) LLM classifier, (c) hybrid. *Lean: (a) at v0.* §1a clean. N-1 / S66 precedent operates.

2. **§1a doctrinal extension shape.** (i) §1a amendment in-place, (ii) §1c new doctrine, (iii) §1a.x sub-numbering. *No confident lean.* Operator + Oracle territory.

3. **§1b validated-suggester interaction.** (a) parallel surfaces, (b) extension, (c) replacement. *Lean: (a) at v0.* Preserves §1b anchor; parallel is the lowest-risk shape.

4. **N-3.1 commitment-tracking fold-in.** (a) folds into Inversion v0 as same architectural ship, (b) stays separate. *Lean: (a).* Same parser; same load-bearing problem viewed from two angles.

5. **First-migration set at v0.** Which Tier 3 surfaces invert as primary v0 ship? Candidates by friction-visibility:
   - Quest acceptance (player-side narration "I'll take the job")
   - Loot drop (player-side "we leave it behind")
   - Simple travel-intent ("we travel to X")
   - Transaction-completion (player-side "I'll buy the bread") — already partially landed via N-1 hint extractor
   - Compression-intent (operator-side "time passes" / "we wind down")
   
   *Lean: ship transaction + quest-acceptance + loot-drop at v0; travel and compression in v0.1.* Smallest viable set; highest friction-visible cases first.

6. **S69 resumption shape.** (a) amend locked S69 spec at Inversion v0 ship time, (b) open S69 v0.1 spec session at resume. *Lean: (b).* Cleaner spec hygiene; locked spec stays as the doctrine-pre-inversion artifact for reference.

7. **Detection-confidence tier routing.** High-confidence auto-route to writer; medium-confidence to `#dm-aside` suggester for operator approval; low-confidence silent. *Lean: three-tier per above.* §11 candidate for threshold tuning per domain.

8. **Telemetry verbosity.** Per-detection-fire vs aggregated per-turn. *Lean: per-detection-fire at v0.* Standard project pattern; observability requires per-event signal.

9. **Operator manual override surface.** When narration-detection fires high-confidence but operator wants to refuse, what's the escape hatch shape? Single-character abort (`/no`), slash that mirrors what was detected, or `#dm-aside` rejection card. *Lean: `#dm-aside` rejection card + the existing slash as override.* The existing slashes remain operational; operator types them to override detection. No new abort surface needed.

10. **Bot→Avrae auto-execution.** §F-59 anchored bot→Avrae writes as prohibited. Inversion doesn't change this — high-confidence detection still routes to `#dm-aside` suggester for operator-pasted Avrae command, not direct bot→Avrae fire. *Lean: §F-59 holds.* Surface as confirmed-not-changed in spec.

11. **Composition forward-compat — silent.** Per discipline. v0 doesn't pre-couple v0.x emergent surfaces (LLM classifier, hybrid detection, advanced override flows).

12. **Migration sequencing for prior ships.** Inversion v0 introduces detection; prior ships (Quest, Composition, Bootstrap, S68 N-4) have slash surfaces that would benefit from inversion. (a) Big-bang Inversion v0 migrates all Tier 3 surfaces at once, (b) gradual per-ship migration in observed-friction order. *Lean: (b).* Big-bang multiplies blast radius; gradual preserves the per-ship sequential-commit discipline standing since S65.

---

## 12. Operational concerns for Phase 1 recon

**N-1 hint extractor pattern extraction.** Phase 1 must inspect the actual N-1 implementation in `dnd_orchestration.py` — verb vocabulary structure, signal co-occurrence requirements, confidence-tier routing if any. The Inversion v0 parsers generalize this pattern; recon confirms the generalization shape.

**Existing slash handler inventory.** Phase 1 enumerates every slash currently shipped. Tiers them per §6 framework. Surfaces unexpected dependencies between slashes (e.g., does `/quest accept` cascade to anything beyond `dnd_quests.status` write?).

**Detection-routing integration point.** Where in `_dm_respond_and_post` (or wherever turn processing lives) does narration-detection fire? Pre-LLM-response (player narration) and post-LLM-response (operator/DM narration)? §11 candidate.

**`#dm-aside` suggester format inventory.** Existing card formats from Quest Layer v0.1, Composition Layer v0, NPC State-Sync, Bootstrap Bot. Inversion v0 suggester cards inherit these patterns; recon ensures consistency.

**Prompt-size baseline.** Current ~22k chars post-S67. Detection parsers themselves don't render to prompt; they fire pre-prompt. But detection-suggester cards in `#dm-aside` may augment prompt context if operator approves. §11 candidate for prompt-size impact at v0 fire-volumes.

---

## 13. What this sketch does NOT do

- Lock §11 decisions. Spec doc handles.
- Resolve §1a doctrinal extension shape (operator + Oracle).
- Pre-commit to LLM classifier or hybrid detection (filed v1.x).
- Migrate every slash at v0 (gradual per-ship migration via §11.12 lean).
- Address the §F-59 bot→Avrae prohibition (confirmed unchanged; surface in spec).
- Address emergent narration-detection-vocabulary expansion (v0.x territory).
- Address multi-character party detection (player narration in multiplayer routing).
- Address operator-vs-player text disambiguation (channel-source already disambiguates; if not, surface as recon item).
- Pre-commit S69 resumption shape (§11.6 walk-time decision).

---

## 14. Next move

Path A three-session cadence: spec → review → implement.

**Phase 1 recon scope:**
1. N-1 hint extractor implementation audit — vocabulary structure, confidence-tier routing, generalization shape
2. Existing slash handler inventory and Tier 1/2/3 classification
3. Detection-routing integration point identification in turn-processing pipeline
4. `#dm-aside` suggester card format catalog from prior ships
5. Prompt-size impact estimation at expected v0 fire-volume
6. §F-59 bot→Avrae prohibition confirmation — verify Inversion v0 doesn't accidentally cross this surface

**Phase 2 walks §11.1 through §11.12 with operator.**

**Phase 3 ships locked spec with first-migration set per §11.5 lock.**

After v0 ships and operator plays through a session, observed friction tells us which v1.x candidates earn slots (additional Tier 3 migrations, LLM classifier introduction, hybrid detection, advanced override surfaces).

**This is the architectural ship that converts the project's UX direction.** The slash-sprawl pattern that has been accumulating since the original mandate gets a structural correction. The BIOS/OS/UI metaphor becomes the project's new direction-lock — commands at the substrate, engine in the middle, conversation at the surface. §1a + §17 + §59 + §76 + §1b all remain operational; what changes is the operator-facing surface that sits on top of them.

The convergent review framed this as the project's largest doctrinal direction-lock since "controlled canonization of stochastic generation." Spec session is where that framing becomes architecturally concrete.
