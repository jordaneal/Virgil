# S72.1 — §76 hygiene closures + §59 / §1b doctrine audit handoff

**Date:** 2026-05-15
**Sessions:** S72.1 (A) §76 closures recon + (B) §59 / §1b / VIRGIL_MASTER refresh
**Status:** (A) HALTed at Surface 3; (A) Surfaces 1 + 2 closed as doctrinal-classification-only (no code change); (B) shipped — DOCTRINE.md + VIRGIL_MASTER.md edits landed.

---

## §1. (A) S67.1 §76 hygiene closures — recon outcome

Three surfaces audited against the 6-property test refinement candidate.

### Surface 1 — `dnd_consequences.summary` — CLOSED AT PATH B (no code change)

**Recon evidence:**
- Writers: `consequence_upsert` (`dnd_engine.py:5649` INSERT, `:5670` UPDATE)
- Rate: gated by `consequence_extractor` invocation (per-turn extraction, not per-write)
- Re-injection: signal/marker form via `compute_consequence_directive` (`dnd_orchestration.py:1675`) — severity-capped 1-3 directive lines, NOT verbatim prose
- Promotion gate: PROMOTION_SURFACE_COUNT=3 + PROMOTION_DISTINCT_TURNS=2 + PROMOTION_AGE_TURNS=10 (compound triple-gate; `dnd_engine.py:5496-5498`)

**6-property classification:** 4/6 — mitigated, not urgent. S67 audit's "mitigated by promotion gates" framing holds under refined test.

**Closure shape:** Path B in place. Existing mitigation (promotion-gate + signal-form re-injection) is sufficient under 6-property test. No code change.

### Surface 2 — `dnd_npcs.description` fold — CLOSED AT PATH B (no code change)

**Recon evidence:**
- LLM-write path: `maybe_promote_consequences` (`dnd_engine.py:5767-5829`) appends `[promoted: kind] summary` to `description` after consequence-promotion gate fires
- npc_upsert is the primary writer but has skeleton_origin protection (S68 N-4 precedent)
- npc_extractor only writes `description_fragment` (length-capped, not full description)
- Rate: only `maybe_promote_consequences` modifies description LLM-side; gated by S1's promotion thresholds (compound triple-gate)
- Re-injection: tagged prose append (`[promoted: kind] summary`) — partially-verbatim of S1 summary

**6-property classification:** 4-5/6 — mitigated, borderline. Tagged-prose append is partially-verbatim of S1; if S1 closes cleanly at signal-form re-injection, S2 follows.

**Closure shape:** Path B in place. Transitive S1 promotion-gate is the load-bearing mitigation. The S68 N-4 pronoun-column precedent (structured-field-replacement for LLM-write column) suggests a future "split notable_traits column from description" cleanup at v0.x, but not load-bearing at S72.1. No code change.

### Surface 3 — chroma DM-stores — HALT (closure shape not locked)

**Recon evidence:**
- Writer: `chroma_store('dm', response)` at `discord_dnd_bot.py:3526` — fires every DM turn, **rate-unlimited**
- Storage: ChromaDB sessions collection (`_chroma_collection`, `dnd_engine.py:101`)
- Reader: `chroma_search` at `dnd_engine.py:164-192` — called per turn in `dm_respond` flow at `dnd_engine.py:7580`
- Re-injection: `f"[{ts}] DM: {doc[:200]}"` — **verbatim** (200-char truncation ≠ summarization)
- Existing mitigation: read-side `dist > 0.5` distance cutoff (`dnd_engine.py:183`)

**6-property classification: 6/6 — full.** First empirical 6/6 surface under refined test.

**Why distance cutoff is insufficient:** Distance > 0.5 filters retrievals that are too dissimilar to the current query — it filters NOISE. It does NOT break the recursive contamination loop. If LLM narrates X → X stored → future query Y close to X retrieves verbatim X → LLM narrates Y biased by X → future Z close to X+Y... the loop continues because distance cutoff doesn't gate the WRITE side and re-injection IS verbatim.

**Why HALT:** S67 audit framing ("mitigated by distance cutoffs") undersold the risk under the 6-property test. Closure shape was not locked at S67. Operator + Oracle decision needed on:

| Path | Shape | Trade-off |
|---|---|---|
| A | Retire chroma DM-stores entirely; replace with deterministic-summary cache | Cleanest; loses LLM-narration similarity recall; biggest implementation |
| B | Write all turns, retrieve only player turns (`role='user'`) | Structurally breaks the loop (LLM-output never re-injects); preserves player-turn similarity recall; small ship |
| C | Harden distance cutoff + add explicit age cutoff (older than N turns drops); rate-limit reads | Refines existing gate; doesn't structurally break loop; smallest ship |
| D | Accept 6/6 risk; rely on existing distance + 200-char truncation; ship 6-property promotion as audit-only | No code change; doctrine update only; lets operator observe before deciding |

**Code's weak lean: Path B.** Structurally breaks the loop, smallest ship that closes the doctrine question, preserves the architectural value chroma_search delivers (player-turn similarity recall is the higher-leverage half of the retrieval — DM-narration recall is mostly already in the prompt context via `last_dm_response`).

**Filed:** for operator + Oracle review at next planning session. No code change at S72.1.

---

## §2. (B) §59 / §1b / VIRGIL_MASTER refresh — landed

### §2.1 §59 canonical instance count

Grep across `dnd_orchestration.py` + `dnd_engine.py` + `discord_dnd_bot.py`:

**23 instances** (corrected from VIRGIL_MASTER's pre-S72 "17 at S70"):
- 21 in `dnd_orchestration.py`
- 1 in `dnd_engine.py` (`build_dm_context:6226`)
- 1 in `discord_dnd_bot.py` (`compute_setup_plan:1288` — S23 #3)

S72 undercount cause: S72's regex missed `_suggester` siblings, `build_advisory_context`, `build_dm_context`, and `compute_setup_plan`. S72.1 canonical regex catches all sub-shapes.

**Full instance list landed in DOCTRINE.md §59 section** (new section added at S72.1).

### §2.2 §1b lineage discrepancy resolved

**Discrepancy:** DOCTRINE.md §1b table (line 11-19) listed 5 shipped instances with N-10 at slot 5. CANON_BOOTSTRAP_BOT §1.K + §8 stamped itself as "sixth project instance" with slot 5 reserved for "Track 6 v0.x SRD card revival." VIRGIL_MASTER §4 line 108 + §10 line 188 picked up CANON_BOOTSTRAP's 6-position framing.

**Resolution:** Post-S67 audit, DOCTRINE.md collapsed the reservation slot (no Track 6 v0.x SRD revival in scope; the reservation framing was Phase-time). DOCTRINE.md is the source of truth — 5 shipped instances post-N-10 with no reservation.

**VIRGIL_MASTER corrections landed:**
- Line 108 (§4 cross-reference): "Six anchored project instances" → "Five anchored project instances post-N-10 per DOCTRINE.md §1b running-list" + reservation-framing explanation
- Line 188 (§10 snapshot): "6 §1b anchored instances" → "5 §1b anchored instances"

### §2.3 §59 count corrections landed in VIRGIL_MASTER

- Line 110 (§4 cross-reference): "17 instances at S70" → "23 instances at S72.1 audit" + file breakdown + naming-convention observation
- Line 187 (§10 snapshot): "17 §59 sibling instances" → "23 §59 sibling instances" + per-file breakdown

### §2.4 DOCTRINE.md §76 candidates section — S67.1 (A) empirical material added

Added classification table for S1/S2/S3 under 6-property test + S3 closure-shape candidates A/B/C/D. The 5th + 6th properties earn formal-§76 promotion if operator + Oracle pass on S3 closure also resolves doctrine question (Code's weak lean: Path B + 6-property promotion).

### §2.5 DOCTRINE.md §59 — new audit section landed

DOCTRINE.md previously lacked a §59 instance list (only VIRGIL_MASTER §4 had the count); added a §59 audit section with full instance table + naming-convention observation. Per project precedent (§1b running-list lives in DOCTRINE.md), §59 deserves its own anchor for canonical citation.

---

## §3. Inversion v0 spec implications

Inversion v0 spec §11.3 walk flagged "5 in spec vs 6 per CANON_BOOTSTRAP §1.K" as a light implementation-time flag. Resolution: spec's 5 was correct per DOCTRINE.md; CANON_BOOTSTRAP's "sixth" was pre-S67-audit framing. **Inversion v0 narration-detection-as-deterministic-gate (if §11.3 ships parallel surfaces) anchors as §1b 6th-instance, not 7th.**

Inversion v0 spec §10.2 commitment-table also relevant — recon at S72 surfaced namespace collision with S19 `compute_commitment_directive` (player-action-honor escape directive — instance #4 in §59 audit). Spec's `dnd_commitments` → propose `dnd_npc_commitments` rename as captured in S72 HALT handoff.

---

## §4. Handoff tabular (WWC standard)

| Item | Value |
|---|---|
| **Session** | S72.1 (A) §76 hygiene closures + (B) §59 / §1b / VIRGIL_MASTER audit refresh |
| **Code changes** | **None.** Doc-only ship. |
| **(A) Surface 1 status** | Closed at Path B; no code change. `dnd_consequences.summary` is 4/6 mitigated under 6-property test (rate-limited extractor + signal-form re-injection). |
| **(A) Surface 2 status** | Closed at Path B; no code change. `dnd_npcs.description` fold is 4-5/6 mitigated under 6-property test (transitive promotion-gate from S1). |
| **(A) Surface 3 status** | **HALT.** Chroma DM-stores classify 6/6 under refined test. Existing mitigation (distance cutoff) does not break recursive loop. Closure paths A/B/C/D surfaced for operator + Oracle review. Code's weak lean: Path B (retrieve only player turns). |
| **(B) §59 count** | 17 → **23** (21 orchestration + 1 engine + 1 discord_dnd_bot). VIRGIL_MASTER + DOCTRINE.md updated. |
| **(B) §1b count** | "Six" (VIRGIL_MASTER) → **Five** (DOCTRINE.md source of truth; reservation slot collapsed post-S67 audit). Documentation discrepancy resolved. |
| **(B) DOCTRINE.md edits** | §76 candidates section: appended S67.1 (A) recon empirical material + S3 closure-path candidates. §59: new instance-audit section added. |
| **(B) VIRGIL_MASTER.md edits** | §4 line 108: §1b count corrected. §4 line 110: §59 count + breakdown corrected. §10 line 187: §59 count corrected. §10 line 188: §1b count corrected. |
| **Inversion v0 implications** | Spec §11.3 "five" was correct (DOCTRINE.md source). Narration-detection anchors as §1b 6th-instance if §11.3 (a) ships. |
| **6-property test promotion** | Earned by S3 empirical material. Pending operator + Oracle pass alongside S3 closure-path decision. |
| **DB snapshot** | Not required (doc-only ship). |
| **Restart** | Not required (no code changes). |
| **PC push** | DOCTRINE.md + VIRGIL_MASTER.md + this handoff doc. |
| **Next session candidates** | (1) S72.2 — chroma DM-stores closure ship per operator-locked path. (2) Inversion v0 Phase 3a per S72 HALT handoff sequencing. (3) S69 amend-in-place per Inversion lock. |

---

## §5. Files touched at S72.1

- `/home/jordaneal/virgil-docs/DOCTRINE.md` — §76 empirical material + new §59 audit section
- `/home/jordaneal/virgil-docs/VIRGIL_MASTER.md` — §4 + §10 count corrections
- `/home/jordaneal/virgil-docs/planner-scratch/S72_1_doctrine_audit_handoff.md` — this file

No code files touched. No DB schema changes. No restart.
