# S65.1 — Candidate Scope

**Date filed:** 2026-05-14
**Source:** S65 close + S65.A format unification close + 2026-05-14T09:47–09:49 baker-pricing playtest

This doc enumerates candidate fixes for S65.1. Operator authorization required to ship any. Items are grouped by scope tier: **single-surface** (1-day fix candidate) vs **multi-spec** (needs design phase).

---

## Carryover from S65

### C-1 — F-008 AUTO_EXECUTE close (HALTED in S65)
- **Status:** Phase A audit complete. Phase B decision = HALT per S65 criteria.
- **HALT reasons (per S65 plan):**
  1. Class (c) consumers exist — `test_dnd_npcs.py` exercises `execute_auto_actions` directly (7 call sites for QUEST_ADD dedup).
  2. Closure touches `build_dm_context` beyond directive emission — AUTO_EXECUTE prompt block at `dnd_engine.py:6447–6519` is sibling to "PLAYER UI SUGGESTIONS" which references the AUTO_EXECUTE tail.
- **Authorization required.** See `S65_F008_audit_findings.md` for full audit + recommended close shape.
- **Doctrinal note.** §1b third-instance anchor (Quest Layer v0.1) is PROVISIONAL until close ships.
- **Scope:** medium. Single-day if operator authorizes the close-shape proposed in audit doc.

### C-2 — npc_upsert tuple-binding pre-existing test failures
- **Status:** Surfaced during S65 regression sweep. NOT an S65 regression.
- **Failures:** 5 test files (test_dnd_npcs.py, test_dnd_locations.py, test_dnd_consequences.py, test_consequence_command.py, test_directive_emit.py) treat `npc_upsert` return as int when it's `tuple[int, bool] | None`.
- **Recommended fix (smallest diff):** update tests to unpack `(gid, was_new) = npc_upsert(...)`.
- **Alternative:** introduce `npc_upsert_id_only()` helper or change signature to accept `was_new_out` ref param.
- **Scope:** single-surface. ~30 minutes mechanical update.

---

## NEW from 2026-05-14 baker-pricing playtest

The playtest surfaced four issues. They cluster into one single-surface fix (N-1) and one multi-spec layer (N-2).

### N-1 — Bookkeeping hint fires on dialogue, not on actual transactions [SINGLE-SURFACE CANDIDATE]

**Scenario from playtest (turns 9:47–9:49):**

| Turn | Player action | Hint fired | Correct? |
|---|---|---|---|
| 9:47 "pay for 5 loaves" | actual purchase action | (none) | ❌ miss |
| 9:48 "how much?" | a question | `!game coin -5sp` | ❌ false fire |
| 9:49 "50c each before" | dispute | `!game coin -1sp` | ❌ false fire |
| 9:49 "yeah but I wanted 5" | continuation | `!game coin -5sp` (duplicate) | ❌ false fire |

**Net effect if player follows hints verbatim:** loses `6sp` for what should be a single `5sp` (or `2.5sp`) transaction.

**Root cause.** The hint extractor (`hint_parse` LLM-side extraction, log line in `dnd_engine.log`) parses LLM narration for price mentions. The LLM re-states prices on every dispute turn; each restatement becomes a fresh `!game coin` proposal. The actual purchase turn ("pay for 5 loaves") had no hint because the LLM didn't explicitly state the price in that narration.

**Recommended fix (single-surface).** Tighten the hint extractor:
1. Require an explicit transaction-completion verb in the narration (`paid`, `handed over`, `accepted payment`, `slid the coins`) co-occurring with the price mention, NOT a bare price quote.
2. Dedupe across recent turns — if `!game coin -5sp` was emitted in the prior turn for the same NPC, suppress duplicate emission this turn.

**Scope:** ~1-day spec + ~1-day implement + adversarial verify (run the exact baker scenario, assert hint fires exactly once on the purchase turn).

**Out-of-scope for N-1.** Issues 1/3/4 (NPC commitment-tracking) — that's N-2.

---

### N-2 — NPC commitment-tracking layer (Issues 1 + 3 + 4 from playtest) [MULTI-SPEC SCOPE]

**Three observed failures in the baker scenario:**

#### Issue 1 — NPC retcons free transaction into "half-price deal"
- 9:47: persuasion DC15 succeeded (rolled 20). Baker: "Consider it on the house, dear."
- 9:49: Baker re-narrates: "your half-price was a kindness for a traveler's song, not a new rate."
- The free transaction was retconned to half-price within one turn.

#### Issue 3 — NPC confirms hallucinated player history
- Jordan: "they were 50c each before." (no prior price was ever established)
- Baker: "I'm still charging a silver a loaf" — implicitly confirms a prior price existed.
- No anti-gaslight rail forces NPCs to flag "I don't recall stating that" for unestablished facts.

#### Issue 4 — Inconsistent totals across dispute turns
- Free (9:47) → 5sp/5 loaves (9:48) → 1sp/loaf (9:49a) → 5sp/5 loaves (9:49b).
- Engine can't reconcile what was said one turn ago.

**Root cause (unified).** No structured NPC commitment state. Each turn the LLM regenerates pricing/promise narration from scratch, optimizing for in-turn coherence, not cross-turn consistency. Prior NPC commitments (free loaf, quoted price, promised favor) are not surfaced as constraints to the next narration.

**Why multi-spec.**
- Requires schema decision: where does `npc_commitments` live? On `dnd_npcs`? Separate `npc_commitments` table? Inline in scene state?
- Requires extraction logic: parse LLM narration for commitments — "on the house", "I'll deliver tomorrow", "five silvers for five loaves" — and store as structured facts.
- Requires retrieval logic: surface relevant commitments back into `build_dm_context` so the next turn's LLM sees them.
- Requires authoritative-fact arbitration: when player and NPC disagree about prior commitment, the stored commitment is the truth, not the player's claim.

**Related findings in long-horizon review.** Likely overlaps with F-028 (factions/NPC memory) and §76 recursive-hallucination layer thinking. Worth cross-referencing during spec design.

**Scope:** multi-spec. Estimated 3-day spec + 2-week implementation + adversarial verify suite. Defer until after C-1 (F-008 close) so the doctrinal anchor is solid before introducing a new §76 surface.

---

## Recommended S65.1 Ship Order

1. **C-2** (test_npc_upsert tuple fixes) — 30 min, mechanical, blocks nothing else. Ship first as warmup.
2. **C-1** (F-008 close) — single-day if operator authorizes. Restores §1b third-instance anchor.
3. **N-1** (hint extractor tightening) — 1-2 days. Single-surface, high-leverage UX fix. Ships after C-1 so it lands on a clean doctrinal substrate.
4. **N-2** (NPC commitment-tracking) — DO NOT BUNDLE into S65.1. File as separate multi-spec arc (S66 or S67 candidate). Requires spec-design phase before any code.

## HALT Criteria for S65.1

Same as S65 base criteria. Pre-ship DB snapshot. Per-fix rollback notes. Feature-disable switches for new always-on behavior. Sequential commits with test verify before next fix.

## Open Questions for Operator

1. Authorize C-1 (F-008 close) per the audit doc's recommended shape?
2. Prioritize N-1 (hint extractor) for S65.1 or defer?
3. File N-2 (NPC commitments) into the long-horizon backlog now, or wait for a second playtest to confirm the failure shape?
