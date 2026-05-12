# Ship 3 — NPC State-Sync Boundary — Design Review v1

**Status:** REVIEW v1 — S40b. Companion to `NPC_STATE_SYNC_SPEC.md` v1 (DRAFT, S40). Walks the 4 §11 decisions + 2 sub-decisions plus C3 candidate, §65a amendment, and §76 audit. Output of this doc is the lock pass — `SPEC.md` updates from DRAFT to LOCKED after Code reads this review and applies the surfaced revisions.

**Pattern:** Standard spec-then-review-then-implement cadence per `WORKING_WITH_CLAUDE.md`. Spec drafted in S40; review locks in S40b; implementation follows in S41.

**Track:** Multiplayer Fixes — Ship 3. Closes Finding H. Files as F-55 cluster sibling #5.5 (cluster prerequisite for #5.4/#5.2/#5.3).

---

## Review summary

| Field | Value |
|-------|-------|
| **Decisions reviewed** | 6 (D1, D2, D3, D4 + Sub-D1, Sub-D2) |
| **Decisions locked at Code's recommendation** | 5 (D1, D2, D3, D4, Sub-D1) |
| **Decisions locked with revision request** | 1 (Sub-D2 — mid-combat re-projection needs explicit guard) |
| **Decisions pushed back** | 0 |
| **New decisions surfaced by review** | 0 — spec covered the surface |
| **HALT escalations** | 0 |
| **Architectural shape changes** | 0 — locked v3 §6 shape holds |
| **C3 candidate review** | Confirmed — projection writer is genuinely single-helper with disjoint trigger surfaces; phrasing carries forward; anchoring criterion correctly deferred to post-S41 verify |
| **§65a amendment review** | Scope bounds hold; one minor phrasing tightening recommended (precondition language) |
| **§76 audit cross-check** | Spot-checks pass; "no fourth project instance" holds; **new doctrinal observation surfaced** for §12 (§17 gated-write discipline preempts §76 four-property surfaces — worth filing) |
| **Spec revisions to apply** | 3 framing/scope refinements (see §7) |
| **Cross-doc consistency** | Clean against HYBRID_COMBAT_NOTES v3 + PLAYTEST_OBSERVATION_FRAMEWORK; one framing addition recommended on PLAYTEST §3.2 mechanical-continuity connection |
| **Ready-for-implementation status** | Yes, after Code applies the 3 §7 revisions |
| **Implementation session** | S41 |

---

## §1. How to read this review

For each §11 decision in `NPC_STATE_SYNC_SPEC.md`, this doc records:

1. **The question** (one-line restatement)
2. **Code's lock recommendation** (verbatim or summarized from spec)
3. **Planner review** — confirm, push back, or revise
4. **Lock outcome** — what stands after Code applies any revisions

The review also walks the C3 candidate (§3), §65a amendment (§4), §76 audit cross-check (§5), and cross-doc consistency (§6) per the operator's review-task list. Spec revisions to apply land in §7.

---

## §2. Decision walks

### §2.1 Decision D1 — Avrae command sequence

**Question:** What exact `!init`-family commands does the projection writer emit? Should the syntax be locked in spec (via a pre-gating Avrae A.2-style recon ship) or deferred to S41 implementation-time live verify?

**Code's lock:** Recommend Option B (sequential two-command: `!init opt <name> -h <hp>` then `!init opt <name> -ac <ac>`); mark as "verify at implementation" rather than locking the exact CLI string in spec. MEDIUM confidence; implementation-time live verify required.

**Planner review:** **Confirm. Deferred-verify approach is correct.**

Comparison to Ship A's A.2 recon (operator's framing): A.2 ran before S35 spec lock and resolved a narrow yes/no question (does Avrae preserve the trailing integer in `!check perception 10`?). That recon was load-bearing — the spec couldn't proceed without the answer because the parser regex depended on Avrae's behavior.

Ship 3's D1 is structurally different. The architectural shape (engine writes, bot projects `!init`-family commands, idempotency at the writer) is locked regardless of which CLI flavor wins. The question is *implementation flavor*, not *architectural shape*. Three reasons the deferred approach is correct:

1. **The contract is locked even when the CLI isn't.** The writer's contract (§5.1) specifies: read engine state, emit a sequence to land HP+AC on Avrae's combatant, return (projected, signals). Tests written against this contract pass regardless of whether the implementation uses A/B/C.
2. **Pre-gating with a recon ship is calendar overhead without proportional risk reduction.** A.2 recon was one focused test. Ship 3's D1 has 3+ command variants to test, each with multiple flag combinations. A pre-gate ship would consume at least a session and produce a written-down syntax that S41 implementation would still need to re-verify in-bot. The deferred approach folds that verify into S41's opening minutes.
3. **The HALT path is well-defined.** If S41 surfaces "Avrae rejects all of A/B/C and the writer cannot land HP+AC at all," that's an architectural HALT — and it's appropriate to surface it at implementation time when a live Discord+Avrae environment is available. Pre-gating wouldn't have caught a deeper "Avrae cannot accept any of these flags" failure mode either.

**Confidence:** MEDIUM-HIGH (same as spec).

**Surfaced sub-point:** spec §5.2's fallback note ("if `!init opt` cannot carry attack stats, accept Avrae's default unarmed-strike fallback") is the right disposition. Attack stats on hydrated NPCs are a v1.x concern; HP+AC is the v1 promise.

**Lock outcome:** Confirm. Spec stays as written; D1 remains "verify at implementation" with the contract locked and the CLI deferred. No revision.

---

### §2.2 Decision D2 — Projection trigger timing

**Question:** Does the writer fire from (a) `_handle_init_list_event` only, (b) `/hydrate` only, or (c) both?

**Code's lock:** (c) both. Single writer, two disjoint trigger surfaces, idempotency at the writer.

**Planner review:** **Confirm.**

This is what makes Ship 3 a C3 second-instance candidate. Covering only one trigger surface would leave a gap:

- `/hydrate`-only: NPCs that exist in `dnd_npcs` from prior parser hits (no operator `/hydrate` since) would never project. Combat against them remains broken — same Finding H pattern.
- `_handle_init_list_event`-only: operator's `/hydrate` flow gives no feedback about Avrae sync until combat begins, breaking the natural "set up then start combat" workflow.

Both triggers feed the same writer; the writer's idempotency guard absorbs both correctly. The trigger surfaces are genuinely disjoint by author identity (DM-typed slash command vs Avrae-emitted init_list parse) and timing (pre-combat vs mid-combat). They don't race.

**Confidence:** HIGH.

**Lock outcome:** Confirm. Both triggers, single writer, idempotency at writer layer. No revision.

---

### §2.3 Decision D3 — Failure-mode handling

**Question:** If Avrae projection fails (channel send raises, Avrae returns error embed), does the engine row stay or roll back?

**Code's lock:** Engine stays as written; projection retries on next trigger; `#dm-aside` notification on failure. No engine rollback.

**Planner review:** **Confirm. Strict two-phase commit is the wrong shape here.**

Three structural reasons engine-stays-with-eventually-consistent-projection beats strict 2PC:

1. **Avrae isn't a 2PC participant.** Avrae is a Discord bot we send messages to and parse embeds back from. There is no atomic-commit primitive across "we wrote to SQLite" and "Avrae accepted our `!init opt`." A 2PC shape would require a transaction coordinator the architecture doesn't have and cannot easily acquire.
2. **Rollback creates partial-write windows.** If engine writes hp_max=13, then Avrae projection fails, then engine rolls back to hp_max=NULL — the operator just saw `/hydrate` succeed and is now confused why their NPC is back to unstatted. The current shape (engine commits; projection retries) keeps engine state predictable and lets projection lag heal on the next init_list event.
3. **Cluster trajectory says engine-authoritative.** Per the F-55 cluster commitment ("Virgil-authoritative-with-Avrae-as-projection"), engine is the source of truth. Rollback on projection failure would invert this — Avrae's acceptance would gate engine's write, which is exactly the relationship Ship 3 is meant to invert.

The retry cadence is naturally healthy because Trigger 1 fires on every `!init list` event, which is frequent during active combat (~per turn). Most projection failures resolve within one turn.

**Confidence:** HIGH.

**Lock outcome:** Confirm. Engine writes always land; projection retries; failure surfaces via `#dm-aside`. No revision.

---

### §2.4 Decision D4 — Stub-monster path for non-init-resident NPCs

**Question:** When `/hydrate` is run for an NPC not currently in init, should the writer emit `!init add` to create the combatant, or no-op and wait for the DM to add the combatant manually?

**Code's lock:** Option A. Writer no-ops with `gate_not_in_init`; ephemeral message tells the DM the NPC will sync on `!init add`. Combat begins when the DM says so; writer's role is sync, not initiation.

**Planner review:** **Confirm.**

The UX cost (DM must remember to `!init add` after `/hydrate`) is real but bounded — it's one extra command at combat-start time, and the ephemeral confirmation makes the expectation explicit. The structural cleanliness of "combat begins when DM says so" is worth preserving:

- DM authority over combat-entry is a long-standing invariant. The DM types `!init begin` and `!init add` deliberately; the bot doesn't pre-empt that.
- Auto-creating combatants on hydrate conflates two semantically different operations: "set this NPC's stats" vs "this NPC is now in combat." Conflating them via the writer would shadow the DM's combat-control affordance.
- The friction is small and addressable post-ship if it surfaces. Spec §11.D4 already files the v1.x consideration ("if post-ship live-verify surfaces 'operator forgot `!init add` after `/hydrate`' as common friction, file v1.x to extend the writer").

**Confidence:** MEDIUM-HIGH (real choice between two defensible options; A is the right default but operator may weigh).

**Lock outcome:** Confirm. Writer no-ops on `gate_not_in_init`; DM informed via ephemeral; v1.x extension filed if needed. No revision.

---

### §2.5 Sub-D1 — `-controller` flag

**Question:** Should the writer emit `-controller <bot_user_id>` when projecting an NPC, so Avrae knows the bot controls turn advancement for the NPC?

**Code's lock:** No. DM is the controller; writer only stat-syncs. Filed as v1.x consideration if `!init next` cadence surfaces friction.

**Planner review:** **Confirm.**

The `-controller` flag would invert DM authority over NPC turn-taking. Avrae's controller semantics determine which Discord user can advance an NPC's turn via `!init next` — if the bot is the controller, the DM may lose the ability to manually advance NPC turns. Bot-controller doesn't add automation (Avrae's turn cadence is independent of controller); it just shifts ownership.

Additionally, NPC turn automation is F-55 #5.2 territory — a separate ship that explicitly takes over NPC turn-taking. Setting `-controller` here would prematurely couple Ship 3 to #5.2's mechanics without #5.2's surrounding infrastructure (target selection, attack choice logic).

**Confidence:** HIGH.

**Lock outcome:** Confirm. No `-controller` flag in v1. Filed v1.x. No revision.

---

### §2.6 Sub-D2 — Re-projection on engine-vs-Avrae mismatch

**Question:** If engine state and Avrae state diverge (e.g., Avrae has damaged the NPC mid-combat to `<8/15>`, engine still has hp_max=15; OR operator re-hydrates with a different CR mid-combat), does the writer re-project on the next trigger or trust Avrae?

**Code's lock:** Spec §11.D2 sub-decision says "the writer queries engine stats vs Avrae stats; on mismatch, re-emits. Refines the idempotency guard."

**Planner review:** **Confirm architectural intent, REQUEST REVISION on phrasing.** The sub-decision as written conflates two cases with very different correct answers:

**Case A — Operator-driven mid-combat re-hydrate (e.g., `/hydrate npc:Talin cr:1` after Talin is already at `<8/15>` mid-combat with cr_str='1/4' originally).** Engine writes new hp_max=35. Should writer re-project? If YES: writer emits `!init opt Talin -h 35 -ac 13`. **Critical risk:** Avrae's `-h` flag may reset hp_current to the new max-HP (Talin's combat damage gets undone). If `-h` only sets max-HP without touching current, the re-projection is safe; if it resets current, it's a footgun.

**Case B — Passive re-projection on init_list trigger when combatant has numeric status (e.g., `<8/15>`).** Idempotency-guard Case 3 in spec §5.3 currently says "Already mechanically complete. Writer no-ops (`noop_complete`)." This is correct — don't second-guess Avrae's mid-combat state when the combatant is already mechanically valid.

The spec's Sub-D2 text reads as if Case A's re-projection is desired ("on mismatch, re-emits"), which would override Case B's correct no-op behavior. The phrasing needs to split the two cases explicitly:

- **Case B (passive init_list trigger):** writer NO-OPs when combatant has numeric status, regardless of whether engine hp_max matches Avrae hp_current. This is the §5.3 Case 3 contract and it's load-bearing.
- **Case A (operator-driven re-hydrate via `/hydrate`):** writer re-projects with `-h <new_max> -ac <new_ac>`. The risk that `-h` resets hp_current is real and needs implementation-time verify. If `-h` does reset current, spec adds a guard: writer warns via `#dm-aside` ("Mid-combat re-hydrate will reset Talin's HP to 35/35 — current 8/15 will be lost. Proceed?") OR refuses the projection (writer logs `avrae_projection_refused: reason=mid_combat_re_hydrate_unsafe`).

**Spec revision request:** Update §11.D2 sub-decision text to split Case A vs Case B explicitly, and add a "verify-at-implementation" note for Case A's `-h` semantics. This is the most consequential revision surfaced by review — silent mid-combat HP resets would be a player-experience disaster.

**Surfaced additional consideration:** §5.3 Case 3 ("Already mechanically complete. Writer no-ops") needs an explicit clause for the operator-driven re-hydrate path. Currently the §5.3 guard treats "Avrae has numeric HP" as a uniform no-op. The revision needs Case 3 to distinguish:
- Trigger 1 (init_list, passive): no-op on numeric HP (preserves mid-combat state).
- Trigger 2 (/hydrate, active): proceeds with projection IFF engine `cr_str` changed since last projection; carries the mid-combat-HP-reset warning.

**Confidence:** MEDIUM. The architectural intent is right (operator-driven re-hydrate should propagate); the phrasing needs tightening to avoid the mid-combat footgun.

**Lock outcome:** Architectural intent confirmed. Revision request applied per §7.1.

---

## §3. C3 candidate review

Spec §12.2 identifies the projection writer as a C3 second-instance candidate ("Single-writer compatible with multiple disjoint trigger surfaces"). Review checks per operator's review prompt:

**1. Both trigger surfaces actually flow through one helper?**

Confirmed. Spec §6.2 and §7.2 both call `avrae_project_npc(channel, campaign_id, npc_name)` with the same signature. No parallel implementation; one helper, two call sites.

**2. Helper's contract is the same across both surfaces?**

Confirmed. The `trigger=` parameter is telemetry-only (string annotation in the `avrae_projection_attempted:` log line); it does NOT branch behavior in the helper body. Idempotency guard logic, command emission, failure handling — all identical across triggers.

**3. C3's phrasing carries forward cleanly?**

Confirmed. The current C3 text in DOCTRINE.md Candidates section reads: *"When a §17 single-writer field gains a second trigger surface (different user action invoking the same write semantic), consolidate via one writer-helper rather than fork the field's write path. The helper is the single writer; the triggers are surfaces invoking it. Two disjoint-trigger surfaces calling one writer-helper is structurally compatible with §17."*

Ship 3 matches exactly: `dnd_npcs` HP+AC stats are the "field" (broadly construed across the row); `avrae_project_npc` is the helper; `/hydrate` slash and `_handle_init_list_event` hydration branch are the disjoint trigger surfaces. The Ship A first instance (Ship A's `dnd_pending_roll_directives.dc` column with `_handle_dm_roll_directive` + `_dm_respond_and_post` triggers) and Ship 3's second instance both manifest the same pattern.

**4. Anchoring criterion: post-S41 implementation + live verify clean?**

Confirmed. Spec §12.2 says "if this lands clean, C3 promotes from candidate to anchored doctrine." Spec doesn't pre-anchor in any §11 lock or implementation contract. The S40b review explicitly preserves this — anchoring happens at the doc-update pass after S41 verify clean.

**Planner observation on C3 promotion shape:** When C3 anchors (assuming S41 verify clean), the framing question filed at C3's original entry ("lands as a new §-entry or as a §17 amendment clause") is worth resolving during the anchor pass. Recommendation: **§17 amendment clause** rather than new §-entry. Reasoning: C3 is a refinement of §17's "single write paths per field" — not a new doctrine, just a clarification that multi-trigger doesn't break single-writer discipline if the writer is the helper. Anchoring as §17a (sibling to §65a's planned amendment shape) keeps the doctrine tree clean.

**C3 review status:** Clean. No spec revision required for C3. Anchoring waits on S41 verify.

---

## §4. §65a amendment review

Spec §3.2 drafts the §65a amendment text. Review checks per operator's review prompt:

**1. Scope bounds hold?**

Confirmed. The amendment text bounds the exception by:
- **Single writer surface:** `avrae_project_npc()` is the sole bot-emit entry point. ✓
- **Command scope:** `!init`-family only (`!init add`, `!init opt`, possibly `!init madd`). Explicit denial of `!attack`/`!cast`/`!check`/non-init commands. ✓
- **Trigger scope:** only `/hydrate` and `_handle_init_list_event` hydration branch. No other trigger. ✓
- **DM-authored-intent precondition:** every emission corresponds to a DM action the operator already initiated. ✓

**2. Amendment phrasing doesn't accidentally license bot-emitted commands outside the projection writer?**

Confirmed. The phrasing is structurally narrow — the exception is bounded by the single-writer-helper, not by category of command. A future code path that wanted to fire `!init opt` from a different trigger would be outside the amendment's scope. Defense-in-depth.

**3. Anchoring criterion: post-S41 verify clean?**

Confirmed. Spec §3.4 says "anchors when Ship 3 ships and live-verify is clean. It lands as a §65a subsection of the existing §65 entry in DOCTRINE.md, not a new §-number." Correct framing — narrow exception to an existing doctrine, not a new doctrine.

**4. Phrasing tightening recommendation:**

The "DM-authored-intent preserved" clause (#4 in §3.2) reads:

> "every emission corresponds to an action the DM already initiated (via `/hydrate` or by adding the NPC to init via `!init add`). The bot is not introducing new mechanical state — it's syncing existing engine state to Avrae's mirror."

Minor tightening: the phrase "introducing new mechanical state" is correct but could be stronger if it explicitly names what counts as "introduction" vs "sync." Suggested phrasing addition:

> "The bot is not introducing new mechanical state — it's syncing existing engine state to Avrae's mirror. **Specifically: the bot never authors HP/AC/stat values; it reads engine-canonical values written by deterministic systems (`npc_hydrate_stats`) and writes those same values to Avrae. The engine remains the single source of truth for the values being projected.**"

This addition pins the amendment to the engine-authoritative trajectory explicitly. Minor; not blocking; recommended for spec body update.

**§65a review status:** Clean with one minor phrasing tightening (§7.2).

---

## §5. §76 four-property audit cross-check

Spec §4.1 audits 20 `dnd_npcs` columns; zero 4/4 hits. Review checks per operator's prompt:

**1. Spot-check 3-5 columns:**

- **`canonical_name` (3+1 KEEP):** Read into LLM prompt via `get_recently_active_npcs` → SCENE STATE block recent_npcs_line. Write-path: `npc_upsert` with skeleton_origin protection, canonicalize_name normalization, near-match diagnostic. **Matches a fresh reading. ✓**
- **`description` (2-3/4 KEEP):** Not retrieved into SCENE STATE block (S38 review confirmed). Chroma-indirect retrieval is filed candidate per Ship 2 §6.3 + §13 item 3 (chroma-layer audit). Write-path: `npc_upsert` with skeleton_origin protection. **Matches a fresh reading. ✓**
- **`hp_max` (1-2/4 KEEP):** Not retrieved into LLM prompt. Consumed by Ship 3's projection writer. Write-path: `npc_hydrate_stats` with source-classified gating (skeleton/hook/adhoc/generic_fallback/explicit_hydrate). **Matches a fresh reading. ✓**
- **`avrae_source` (1/4 KEEP):** Set by `npc_register_avrae_madd` only. Not narrative; not retrieved into LLM prompt. Pure mechanical flag. **Matches a fresh reading. ✓**
- **`origin_excerpt` (2-3/4 KEEP):** Capped at 100 chars; written by `npc_upsert` with skeleton_origin protection. Not in any current prompt block (chroma-indirect only). **Matches a fresh reading. ✓**

Spot-checks pass. The audit is sound.

**2. "No fourth project instance" conclusion holds?**

Confirmed. Every column is either:
- Gated through a §17 single-writer helper (`npc_upsert`, `npc_hydrate_stats`, `npc_register_avrae_madd`, or Ship 3's new `avrae_project_npc`), OR
- Not narratively inferential (FK, integer, timestamp, enum-like flag).

No 4/4 hits. §76's three project instances (S22 #2 / S32 / S36) remain canonical; Ship 3 doesn't accumulate a fourth.

**3. §76's table-agnostic phrasing applies?**

Confirmed. The doctrine reads "any persisted scalar field" — no refinement needed for `dnd_npcs`.

**4. Doctrinal observation to file (per operator's review prompt):**

The operator's review prompt notes: *"This is the empirical validation that §17 gated-write discipline IS the §76-compliant pattern. Worth filing as a doctrinal observation in §12 if spec didn't already."*

Spec didn't file this. **Surface as revision request:** add a §12.5 (or fold into §4.3) observation:

> **§17 gated-write discipline preempts §76 four-property surfaces.** Where a column has a §17 single-writer helper as its only write path (e.g., `npc_upsert`, `npc_hydrate_stats`, `npc_register_avrae_madd`, `avrae_project_npc`), the column structurally cannot become a §76 four-property contamination surface — the gated-write boundary fails property 1 ("LLM-writable" requires a non-gated write path). The Ship 3 audit empirically validates this: 20 `dnd_npcs` columns audited, zero 4/4 hits, because every LLM-influenced write flows through a §17-disciplined helper. **Operational consequence:** when designing new persisted scalar columns, the four-property audit checklist can be short-circuited at column-add time by routing the column's write path through a single-writer helper with appropriate gates (skeleton_origin protection, canonicalize_name normalization, source classification, idempotency contract). This is the §17+§76 composition pattern: §17 names the discipline; §76 names the failure mode that discipline preempts.

This is a real doctrinal insight worth preserving for future ships. Surface as §7.3 revision request.

**§76 audit cross-check status:** Clean. One doctrinal observation surfaced for filing (§7.3).

---

## §6. Cross-doc consistency check

Per operator's review-task list, three checks against newer/adjacent docs:

### §6.1 PLAYTEST_OBSERVATION_FRAMEWORK §3.2 NPC continuity

PLAYTEST §3.2 measures NPC continuity across sessions: "remembered correctly / remembered with drift / forgotten." Ship 3 enables **mechanical continuity** specifically — once a hydrated NPC's HP+AC are in Avrae's combatant store, that state carries across the session (Avrae persists init state).

Cross-session continuity (HP carrying from session N to session N+1) is a different question — that depends on whether the campaign returns to the same combat encounter, which is operator-driven (`!init begin` after a session break). Ship 3 makes the mechanical state COHERENT within a session; cross-session is out of scope (and arguably should remain out of scope — combat encounters typically don't span sessions in tabletop convention).

**Spec doesn't frame this explicitly.** Recommended minor framing addition to spec §13 (out-of-scope) or §1.2:

> **Mechanical continuity vs narrative continuity (PLAYTEST §3.2 distinction).** Ship 3 closes the **mechanical-continuity** gap for hydrated NPCs — within a combat encounter, Avrae has the stats it needs to resolve attacks, HP decrements track, condition state persists. **Narrative continuity** (NPCs remembering past interactions, attitude shifts based on prior encounters) is a separate surface — closed by future motion-systems work / Ship 4 polish / consequence layer extensions, not by Ship 3. PLAYTEST §3.2's "remembered correctly / drifted / forgotten" categorization applies to BOTH surfaces — Ship 3 closes the mechanical-side gap; narrative-side gaps persist and are addressed by separate ships.

Minor framing; not blocking; surfaced as §7.4 spec revision request.

### §6.2 HYBRID_COMBAT_NOTES.md v3 "dumb combat" dependency

v3 §3.1 lists "dumb combat" as a future ship after Ship 3: standard Avrae init with LLM-narrated transitions, no compression, no hidden init. The dependency: dumb combat assumes Avrae owns mechanics. If hydrated NPCs are mechanically inert (Finding H pre-Ship-3), dumb combat against hydrated NPCs fails too — same mechanical-vs-narrated mismatch.

Spec §1 + §13 already note Ship 3 is the cluster prerequisite. The dependency is correctly framed. No additional framing needed.

**Cross-check status:** Clean.

### §6.3 Doctrinal observation surfacing

Per operator's review prompt: *"If Ship 3 surfaces any operational discipline statement (the way §76 produced 'every new persisted scalar column gets a manual 4-property check at add time'), it belongs in the spec for operator visibility."*

The §17+§76 composition observation (§5.4 of this review) IS such a statement: "when designing new persisted scalar columns, route the column's write path through a single-writer helper with appropriate gates." Surface as §7.3 spec revision request.

Beyond that, Ship 3 doesn't produce a new operational discipline statement at the level of §76's audit checklist. The §65a amendment text itself is the doctrinal lift; it's already in the spec.

**Cross-doc consistency status:** Clean with three minor framing additions (§7.3, §7.4).

---

## §7. Spec revisions to apply before LOCKED status

Code applies the following revisions before flipping `NPC_STATE_SYNC_SPEC.md` from DRAFT to LOCKED:

### §7.1 Revision to §11.D2 sub-decision (Sub-D2 — mid-combat re-projection)

Replace the current §11.D2 sub-decision text ("the writer queries engine stats vs Avrae stats; on mismatch, re-emits") with explicit Case A vs Case B splitting:

> **Sub-decision (Case-split):** the idempotency guard distinguishes by trigger:
>
> - **Case B — Passive `_handle_init_list_event` trigger:** writer NO-OPs when combatant has numeric status (`<X/Y>` or `<Healthy>`), regardless of engine hp_max value. This preserves mid-combat state per §5.3 Case 3. Avrae's mid-combat HP is the authoritative current-state value; the writer does not second-guess it.
> - **Case A — Active `/hydrate` trigger:** writer re-projects when engine `cr_str` has changed since the last projection (operator-driven re-hydrate). **Risk:** Avrae's `!init opt -h <N>` flag may reset hp_current to the new max-HP, which would undo mid-combat damage. **Verify-at-implementation:** test `!init opt -h` semantics in S41. If `-h` resets hp_current, writer adds a `#dm-aside` warning before re-projection ("Mid-combat re-hydrate will reset NPC HP to <new_max>/<new_max>. Current state will be lost.") AND filed v1.x for a `--confirm` gate on mid-combat re-hydrate.
>
> Update §5.3 Case 3 to reference this case-split: the existing "no-op when numeric status" rule applies to Trigger 1 only; Trigger 2 (active /hydrate) bypasses Case 3's guard when `cr_str` has changed.

This split is load-bearing — silent mid-combat HP resets would be a player-experience disaster.

### §7.2 Revision to §3.2 §65a amendment phrasing

Extend the "DM-authored-intent preserved" clause (#4 in spec §3.2) with explicit engine-authoritative language. Current text:

> "4. **DM-authored intent preserved:** every emission corresponds to an action the DM already initiated (via `/hydrate` or by adding the NPC to init via `!init add`). The bot is not introducing new mechanical state — it's syncing existing engine state to Avrae's mirror."

Replace with:

> "4. **DM-authored intent preserved:** every emission corresponds to an action the DM already initiated (via `/hydrate` or by adding the NPC to init via `!init add`). The bot is not introducing new mechanical state — it's syncing existing engine state to Avrae's mirror. **Specifically: the bot never authors HP/AC/stat values; it reads engine-canonical values written by deterministic systems (`npc_hydrate_stats`) and writes those same values to Avrae. The engine remains the single source of truth for the values being projected.**"

This pins the amendment to the engine-authoritative trajectory explicitly. Minor tightening; reinforces the structural bound.

### §7.3 New doctrinal observation in §12 (§17 + §76 composition)

Add a new subsection §12.5 (after §12.4 "No other new candidates filed"):

> **§12.5. Doctrinal observation: §17 gated-write discipline preempts §76 four-property surfaces.**
>
> Where a column has a §17 single-writer helper as its only write path (e.g., `npc_upsert`, `npc_hydrate_stats`, `npc_register_avrae_madd`, `avrae_project_npc`), the column structurally cannot become a §76 four-property contamination surface — the gated-write boundary fails property 1 ("LLM-writable" requires a non-gated write path). The Ship 3 audit empirically validates this: 20 `dnd_npcs` columns audited, zero 4/4 hits, because every LLM-influenced write flows through a §17-disciplined helper.
>
> **Operational consequence:** when designing new persisted scalar columns, the four-property audit checklist can be short-circuited at column-add time by routing the column's write path through a single-writer helper with appropriate gates (skeleton_origin protection, canonicalize_name normalization, source classification, idempotency contract). This is the §17+§76 composition pattern: §17 names the discipline; §76 names the failure mode that discipline preempts.
>
> **Filed as doctrinal observation** (not a new candidate); the insight earns DOCTRINE.md placement at Ship 3 doc-update pass, either as a §76 sibling note or as §17 amendment text (decided at doc-update time).

### §7.4 New framing addition (mechanical vs narrative continuity)

Add to spec §13 (out-of-scope) as a new item, or weave into §1.2:

> **Mechanical continuity vs narrative continuity (PLAYTEST §3.2 distinction).** Ship 3 closes the **mechanical-continuity** gap for hydrated NPCs — within a combat encounter, Avrae has the stats it needs to resolve attacks, HP decrements track, condition state persists. **Narrative continuity** (NPCs remembering past interactions, attitude shifts based on prior encounters) is a separate surface — closed by future motion-systems work, Ship 4, or consequence layer extensions, not by Ship 3. PLAYTEST §3.2's "remembered correctly / drifted / forgotten" categorization applies to both surfaces; Ship 3 closes the mechanical-side gap; narrative-side gaps persist and are addressed by separate ships.

All four revisions are framing/scope refinements — they preserve every architectural lock in D1-D4 + Sub-D1 and only tighten edge-case handling (Sub-D2), reinforce structural bounds (§65a phrasing), file a doctrinal observation (§17+§76 composition), and surface a downstream-consequence cross-doc framing (PLAYTEST §3.2 distinction). Spec status flips DRAFT → LOCKED after revisions land.

---

## §8. Doctrine candidate review (summary)

- **§65a amendment:** drafted in spec §3.2 with one phrasing tightening (§7.2). Anchors as a §65 subsection in DOCTRINE.md post-S41 verify clean. ✓
- **C3 second-instance candidate:** confirmed projection writer is single-helper with disjoint triggers per spec §12.2. Anchors as §17 amendment clause (recommended; vs new §-entry) post-S41 verify clean. ✓
- **§76 doctrine:** carries forward unchanged. No fourth project instance from Ship 3 audit. Doctrinal observation about §17+§76 composition surfaced for §12.5 (revision §7.3). ✓
- **No other new candidates filed by review.**

---

## §9. Implementation handoff to S41

After Code applies the four §7 revisions and the spec flips to LOCKED, implementation begins in S41 per the cadence in `WORKING_WITH_CLAUDE.md`.

| Field | Value |
|-------|-------|
| **Implementation session** | S41 |
| **Model** | Opus (cluster-prerequisite ship; §65a amendment surface; C3 second-instance verify) |
| **Files touched (primary)** | `discord_dnd_bot.py` (new `avrae_project_npc` helper + `/hydrate` integration at line 5245 + `_handle_init_list_event` integration at line 1396-1430), `dnd_engine.py` (no changes; engine helpers stay pure) |
| **Files touched (tests)** | `test_avrae_project_npc.py` (new), `test_npc_hydrate_stats.py` (+10 assertions for engine purity), `test_npc_hydrator.py` (sanity-check additions), `test_doctrine_76_dnd_npcs_audit.py` (new — per-table regression test) |
| **S41 opening verify-pass** | D1 implementation-time test of `!init opt` CLI flavor (A single-command vs B sequential); D1 fallback if `!init opt` cannot carry attack stats; Sub-D2 verify of `!init opt -h <N>` semantics (does it reset hp_current?) |
| **Test target** | ~50 new assertions across 2 new + 2 extended files |
| **Live-verify scenarios** | 6 (A–F) per spec §9 |
| **Promotion criteria** | Per spec §9 (all six scenarios pass) + §65a amendment anchors + C3 candidate promotes to anchored doctrine |
| **Doc-update pass post-ship** | ROADMAP.md (Ship 3 ✅), SESSIONS.md (S40 + S40b + S41 entries), DOCTRINE.md (anchor §65a as §65 subsection; anchor C3 as §17 amendment clause; file §17+§76 composition observation), MULTIPLAYER_FIXES.md (§6 row → ✅ SHIPPED LIVE), tests-to-run-post-session.md (Scenarios A–F appended), HYBRID_COMBAT_NOTES.md v3 cross-reference (Ship 3 cluster prerequisite confirmed). |

Note for S41: the implementation opens with the D1 live-verify pass (test `!init opt` syntax variants) and the Sub-D2 live-verify pass (test `-h` flag semantics for hp_current handling). These are S41 opening minutes; once they resolve, the projection writer implementation proceeds against locked Avrae syntax.

---

## Tabular handoff

| Field | Value |
|-------|-------|
| **File written** | `/home/jordaneal/virgil-docs/specs/NPC_STATE_SYNC_REVIEW.md` |
| **Status** | REVIEW v1 — locks applied; spec flips to LOCKED after Code applies the four §7 revisions |
| **Decisions reviewed** | 6 (4 §11 decisions + 2 sub-decisions) |
| **Decisions confirmed at Code's recommendation** | 5 (D1, D2, D3, D4, Sub-D1 — architectural locks all confirmed) |
| **Decisions confirmed with revision request** | 1 (Sub-D2 — mid-combat re-projection needs Case A/B split) |
| **Decisions pushed back** | 0 |
| **New decisions surfaced** | 0 — spec covered the surface |
| **HALT escalations** | 0 |
| **Architectural changes** | None |
| **Spec revisions to apply** | 4 (§7.1 Sub-D2 case-split; §7.2 §65a phrasing tightening; §7.3 §17+§76 composition observation; §7.4 PLAYTEST §3.2 distinction framing) |
| **C3 candidate review** | Confirmed — single helper, disjoint triggers; anchors post-S41 verify clean as §17 amendment clause (recommended) |
| **§65a amendment review** | Scope bounds hold; one minor phrasing tightening applied |
| **§76 audit cross-check** | Spot-checks pass; no fourth project instance; doctrinal observation surfaced for §12.5 |
| **Cross-doc consistency** | Clean against HYBRID_COMBAT_NOTES v3 + PLAYTEST_OBSERVATION_FRAMEWORK; minor framing addition for PLAYTEST §3.2 mechanical-vs-narrative distinction |
| **Ready-for-implementation status** | Yes, after Code applies the four §7 revisions |
| **Implementation session** | S41 |
| **Companion spec status** | DRAFT → LOCKED after revisions applied |

---

*End of review v1. Session 40b.*
