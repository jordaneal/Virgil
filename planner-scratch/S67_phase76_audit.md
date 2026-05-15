# S67 — §76 Audit Findings (Fix 2 Phase A)

**Date:** 2026-05-14
**Session:** S67 Fix 2 Phase A
**Scope:** Apply the four-property latent-canon test (LLM-writable + persisted + retrieved + narratively-inferential) to 9 candidate surfaces beyond `dnd_campaigns.current_scene`.

---

## Methodology

Per DOCTRINE.md §76, a recursive-hallucination memory loop is any data surface that meets all four properties simultaneously:

1. **LLM-writable** — the field is populated (directly or indirectly) by LLM-generated text.
2. **Persisted** — the field lives in storage that survives a turn boundary.
3. **Retrieved** — the field is read back into a subsequent LLM prompt.
4. **Narratively inferential** — the retrieved text is prose-shaped and re-prompts narrative inference, not a structured fact (id, enum, boolean, etc.).

A surface meeting 4/4 is a candidate latent-canon contamination loop. Whether it is ACTIVELY contaminating depends on **mitigation layers** (rate-limiting, similarity gating, single-writer discipline). The four-property test is necessary, not sufficient — `current_scene` (the F-016 target) has 4/4 with zero mitigation; other surfaces meet 4/4 with non-trivial mitigation layers and present different remediation calculus.

---

## Audit Results

### Surface 1 — `dnd_campaigns.current_scene` ← F-016 target

| Property | Status | Evidence |
|---|---|---|
| LLM-writable | ✓ | `discord_dnd_bot.py:3451`: `update_scene(campaign['id'], f"Last actions: {combined_action[:200]} | DM: {response[:200]}")` — LLM `response` is fused into the field every narration turn. |
| Persisted | ✓ | `dnd_campaigns.current_scene TEXT` column. |
| Retrieved | ✓ | `dnd_engine.py:6447`: `current_scene_text = campaign.get('current_scene') or 'The adventure is just beginning.'` injected into `=== CURRENT SCENE ===` prompt block. |
| Narratively inferential | ✓ | Field is unstructured prose ("Last actions: ... | DM: ..."); LLM treats as scene description. |

**Verdict: 4/4. Mitigation: NONE.** Every turn writes, every turn reads, every turn re-prompts. Classic §76 loop. **PROCEED to Phase B closure.**

---

### Surface 2 — `dnd_consequences.summary` (LLM-extracted consequence prose)

| Property | Status | Evidence |
|---|---|---|
| LLM-writable | ✓ | `dnd_engine.py:5746`: `consequence_upsert(...)` called from `apply_consequence_proposals` which feeds LLM-extracted summary text. |
| Persisted | ✓ | `dnd_consequences.summary TEXT` column. |
| Retrieved | ✓ | `dnd_engine.py:6151`: `=== PENDING CONSEQUENCES ===` block in `build_dm_context`, content from `compute_consequence_directive(active_cons, ...)`. |
| Narratively inferential | ✓ | Summary is prose ("threatened to burn the inn", "promised to help"). Re-prompts character-state inference. |

**Verdict: 4/4. Mitigation: PROMOTION GATES.** `maybe_promote_consequences` requires `surface_count >= PROMOTION_SURFACE_COUNT (3)` × `distinct_surface_turns >= PROMOTION_DISTINCT_TURNS (3)` × `(current_turn - first_seen_turn) >= PROMOTION_AGE_TURNS (5)` before folding into `dnd_npcs.description`. The directive itself fires only on ACTIVE consequences, which carry their own §16 invariant constraints. **NEW 4/4 SURFACE — but mitigated. File for S67.1 Phase C decision.**

---

### Surface 3 — `dnd_npcs.description` (consequence-promotion fold)

| Property | Status | Evidence |
|---|---|---|
| LLM-writable | ✓ | `dnd_engine.py:5531`: `new_desc = existing_desc + ' ' + addition` where `addition = f"[promoted: {kind}] {summary}"`. The summary is LLM-extracted (Surface 2 above). |
| Persisted | ✓ | `dnd_npcs.description TEXT` column. |
| Retrieved | ✓ | NPC description rendered in `=== NPCs IN CONTEXT ===` block; surfaced via `compute_npcs_in_context_directive`. |
| Narratively inferential | ✓ | Description is prose with bracketed-prefix prepended consequence text. Re-prompts character-trait inference. |

**Verdict: 4/4. Mitigation: PROMOTION GATES (same as Surface 2) — only promoted consequences fold.** **NEW 4/4 SURFACE — but mitigated.** File for S67.1.

---

### Surface 4 — Chroma collection ("Relevant past events" block)

| Property | Status | Evidence |
|---|---|---|
| LLM-writable | ✓ | `discord_dnd_bot.py:3450`: `chroma_store(campaign['id'], 'dm', response)` — full LLM response stored every turn. Also `2713`: `chroma_store(campaign['id'], 'user', f"{display}: {action}")` (player text, mixed in). |
| Persisted | ✓ | Chroma sessions collection (`/mnt/virgil_storage/chroma_dnd`). |
| Retrieved | ✓ | `dnd_engine.py:6023`: `=== RELEVANT PAST EVENTS ===` block from `chroma_search` results. |
| Narratively inferential | ✓ | Chroma returns prose excerpts (200-char DM/Player snippets). |

**Verdict: 4/4. Mitigation: DISTANCE CUTOFF (`dist > 0.5` drops irrelevant matches; `dnd_engine.py:183`) + S44 combat-narration chroma-bypass + minimum-collection-count gate (`count() < 3` returns empty).** **NEW 4/4 SURFACE — but mitigated by embedding-similarity gates.** File for S67.1.

---

### Surface 5 — `dnd_quests.summary`

| Property | Status | Evidence |
|---|---|---|
| LLM-writable | ✗ | Post-S65.1 F-008 close, only `/quest add` slash (operator-typed) writes summary. `quest_add_with_dedup` passes empty summary. AUTO_EXECUTE QUEST_ADD path is dead (`AUTO_EXECUTE_ENABLED = False`). |
| Persisted | ✓ | `dnd_quests.summary TEXT`. |
| Retrieved | ✓ | Active-quest directive in prompt. |
| Narratively inferential | ✓ | Operator-authored prose. |

**Verdict: 3/4 (NOT LLM-writable). NOT a contamination surface.**

---

### Surface 6 — `dnd_quest_acts.act_description`

| Property | Status | Evidence |
|---|---|---|
| LLM-writable | ✗ | Both call sites (`/quest seed-skeleton` import + `/quest act add` slash) are operator-driven. Skeleton import reads `act_description` from skeleton.md (DM-authored canon). No LLM-extraction path. |
| Persisted | ✓ | `dnd_quest_acts.act_description TEXT`. |
| Retrieved | ✓ | Composition Layer v0 surfaces in active-act directive. |
| Narratively inferential | ✓ | Multi-sentence prose. |

**Verdict: 3/4 (NOT LLM-writable). NOT a contamination surface. Consistent with prior Composition Layer v0 audit.**

---

### Surface 7 — Suggester-stored offer dialogue

| Property | Status | Evidence |
|---|---|---|
| LLM-writable | N/A | Suggester proposal text is NOT persisted to DB. Only `quest_offer(...)` is called, which writes status/npc_id/turn fields. The proposal `voicer_npc_id` cooldown lives in process-local `_quest_offer_last_turn` dict (`discord_dnd_bot.py:1217`). |
| Persisted | ✗ | No DB persistence of offer text. |

**Verdict: NOT 4/4 (no persistence). NOT a contamination surface.**

---

### Surface 8 — `dnd_npcs.personality` / `appearance`

| Property | Status | Evidence |
|---|---|---|
| LLM-writable | N/A | Columns DO NOT EXIST in `dnd_npcs` schema (only `description`, `role`, `origin_excerpt`, etc.). |

**Verdict: NOT APPLICABLE — no schema. Captured in audit for completeness.**

---

### Surface 9 — `dnd_scene_state.last_dm_response`

| Property | Status | Evidence |
|---|---|---|
| LLM-writable | ✓ | `dnd_engine.py:7782`: `update_last_dm_response(campaign['id'], response or '')` — full LLM response stored. Single-writer-disciplined per S39. |
| Persisted | ✓ | `dnd_scene_state.last_dm_response TEXT`. |
| Retrieved | ✓ | `dnd_engine.py:7015`: `prior_dm_response = (scene_state or {}).get('last_dm_response') or ''` — passed to `compute_commitment_directive`. |
| Narratively inferential | ✗ | **Used for SIGNAL EXTRACTION only**, not prose re-injection. `_has_reaction_verbs(prior_dm_response, prior_target_hints)` is a boolean check — does the prior narration contain reaction-verbs near target NPCs? The TEXT itself doesn't re-enter the LLM prompt. |

**Verdict: 3/4 (NOT narratively inferential — signal extraction only). NOT a contamination surface.** This is the §76-disciplined replacement Ship 2 introduced for the deleted scene_state self-summary columns.

---

## Summary Table

| # | Surface | 4/4? | Mitigation | Verdict |
|---|---|---|---|---|
| 1 | `dnd_campaigns.current_scene` | ✓ | NONE | **F-016 target — PROCEED to Phase B closure** |
| 2 | `dnd_consequences.summary` | ✓ | Promotion gates (3×3×5) | NEW 4/4 — file for S67.1 |
| 3 | `dnd_npcs.description` (consequence-fold) | ✓ | Promotion gates (3×3×5) | NEW 4/4 — file for S67.1 |
| 4 | Chroma collection (DM stores) | ✓ | Distance cutoff 0.5 + S44 bypass | NEW 4/4 — file for S67.1 |
| 5 | `dnd_quests.summary` | 3/4 | — | Operator-only post-S65.1 |
| 6 | `dnd_quest_acts.act_description` | 3/4 | — | Operator-only |
| 7 | Suggester offer dialogue | N/A | — | No persistence |
| 8 | `dnd_npcs.personality` / `appearance` | N/A | — | No schema |
| 9 | `dnd_scene_state.last_dm_response` | 3/4 | — | Signal extraction only |

---

## HALT Decision: Phase C deferred to S67.1

Per S67 plan:
> "If audit surfaces 3+ new contamination surfaces: HALT, push the findings doc to operator, dispatch closure as a separate ship (S67.1 or later). Bundling 3+ §76 closures in one session risks the same blast-radius concern GPT 1/3 flagged for S65."

**Result: 3 new 4/4 surfaces found** (Surfaces 2, 3, 4) → **HALT Phase C closure**.

**Scope adjustment for S67:**
- **Phase A** (this doc): SHIP — audit findings produced.
- **Phase B** (`current_scene` closure): SHIP — the original F-016 target, unmitigated 4/4 surface, single-surface scope within blast-radius budget.
- **Phase C** (new-surface closures): DEFER to S67.1.

**Critical context for operator on S67.1 priority:**

The 3 new 4/4 surfaces have **non-trivial mitigation layers** that the F-016 target lacks. Specifically:
- Surfaces 2 + 3 require **9+ turns of consistent LLM narration** before contamination can fold (promotion gates).
- Surface 4 requires the LLM's prior narration to be **semantically similar** to the current player action (embedding distance < 0.5) before re-injection, and the S44 combat-narration bypass closes the highest-risk path.

So while the four-property test fires 4/4 on raw terms, the mitigations make these slower-rate contamination loops than `current_scene` (which writes/reads every turn unconditionally). The HALT preserves the BLAST-RADIUS budget but does NOT imply equal urgency.

Recommended S67.1 priority order:
1. **Chroma DM-stores** (Surface 4) — highest empirical contamination risk despite mitigation, because chroma touches every prompt and the distance cutoff sometimes admits near-misses.
2. **Consequence fold** (Surfaces 2+3 as a unit) — they're entangled (promotion writes 2 → folds into 3). Close them together or not at all.

---

## Doctrinal Note

This audit identified 3 mitigated 4/4 surfaces and confirmed 1 unmitigated 4/4 surface. The **four-property test continues to be a useful predicate** but mitigation-aware extensions would tighten the discrimination:

- **5th property candidate:** "**Rate-unlimited write**" — does the LLM write to this field every turn, or are there throttling gates? `current_scene` writes every turn; consequence promotion writes ~every 9+ turns; chroma re-injection requires semantic-similarity match.
- **6th property candidate:** "**Verbatim re-injection**" — is the persisted text re-injected verbatim, or used only for boolean/signal extraction? `current_scene` is verbatim; `last_dm_response` is signal-only.

These extensions don't replace §76 — they refine "which 4/4 surfaces need urgent closure" vs "which can be opportunistically tightened."

This is a candidate doctrine refinement (file under doctrine notes for the post-S68 F-XX anchoring walk).

---

## Operator Action Required

1. Confirm HALT on Phase C; authorize S67.1 to close Surfaces 2/3/4 as a separate ship.
2. Confirm Phase B (`current_scene` closure) proceeds in S67 as planned.
3. Consider whether the 5th + 6th doctrinal-property-candidates warrant filing as a §76 amendment proposal alongside the S67.1 closures.
