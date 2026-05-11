# Virgil Doctrine

A catalog of architectural lessons promoted from session work into project-wide principles.

Each entry: when it was learned (which session), what triggered it, the doctrine itself, and ships where it's been applied since. Order is roughly chronological, with closely-related doctrines clustered.

## Index

- §1a. [LLM never decides mechanical outcomes (binding-mechanics surface)](#1a-llm-never-decides-mechanical-outcomes)
- §1b. [LLM may suggest within bounded structured surfaces when a deterministic validator gates the suggestion](#1b-llm-may-suggest-within-bounded-structured-surfaces)
- §2. [Hard-stop rules go at the END of the prompt](#2-hard-stop-rules-go-at-the-end-of-the-prompt)
- §3. [Capture real system output; don't trust docs](#3-capture-real-system-output-dont-trust-docs)
- §4. [AI reviewers excel at architecture, fail at empirical format](#4-ai-reviewers-excel-at-architecture-fail-at-empirical-format)
- §5. [When the user pushes back, pause and listen](#5-when-the-user-pushes-back-pause-and-listen)
- §6. [Evolve from observed friction, not anticipated](#6-evolve-from-observed-friction-not-anticipated)
- §7. [Discard the first design — the lighter version is usually right](#7-discard-the-first-design)
- §8. [One live verification per step. Don't batch](#8-one-live-verification-per-step)
- §9. [Don't engineer against model limits — swap the model](#9-dont-engineer-against-model-limits)
- §10. [Trace the full pipeline before declaring done](#10-trace-the-full-pipeline-before-declaring-done)
- §11. [Design preferences are the user's, not Claude's unilateral call](#11-design-preferences-are-the-users)
- §12. [Advisory parser pattern](#12-advisory-parser-pattern)
- §13. [Suggestion-only forever for advisory parsers](#13-suggestion-only-forever)
- §14. [Strict literal match + telemetry + future merge tool > fuzzy match](#14-strict-literal-match-beats-fuzzy)
- §15. [`═══` framing for authoritative canon dominates LLM attention](#15-authoritative-canon-framing)
- §16. [Engine defends its own invariants at the write boundary](#16-engine-defends-its-own-invariants)
- §17. [Single write paths per field](#17-single-write-paths-per-field)
- §18. [Engine primitive first, command second](#18-engine-primitive-first)
- §19. [Two independent gates before destruction](#19-two-independent-gates-before-destruction)
- §20. [Atomic batch with no partial state](#20-atomic-batch-no-partial-state)
- §21. [Diagnostic-before-treatment under pressure](#21-diagnostic-before-treatment)
- §22. [Re-stage from most recent output, not session-start snapshot](#22-re-stage-from-most-recent-output)
- §23. [Time estimates don't belong in priority calls](#23-time-estimates-dont-belong)
- §24. [Hold a position when pushed unless given new information](#24-hold-a-position-when-pushed)
- §25. [Directives-as-imperatives (the Track 3 backbone)](#25-directives-as-imperatives)
- §26. [Ever-growing exception lists mean the fix is wrong](#26-ever-growing-exception-lists)
- §27. [Workflow rules outrank apparent simplicity](#27-workflow-rules-outrank-simplicity)
- §28. [Defense-in-depth at parser + engine](#28-defense-in-depth-at-parser-engine)
- §29. [Cleanup ships with the fix](#29-cleanup-ships-with-the-fix)
- §30. [PC-vs-NPC identity is structure, not prompt](#30-pc-vs-npc-identity-is-structure)
- §31. [Verify the running process, not just the file on disk](#31-verify-the-running-process)
- §32. [Spec → review → revise → ship](#32-spec-review-revise-ship)
- §33. [Build-to-a-bar (don't gate on play data)](#33-build-to-a-bar)
- §34. [No pre-sequencing — ship one v1, observe, re-decide](#34-no-pre-sequencing)
- §35. [Dual-pass channel separation (player vs DM parsing)](#35-dual-pass-channel-separation)
- §36. [Parser-judged severity, not code-baked thresholds](#36-parser-judged-severity)
- §37. [Documentation passes are code review passes](#37-doc-passes-are-code-reviews)
- §38. [Filed-not-sequenced for unbuilt layers](#38-filed-not-sequenced)
- §39. [Pure-observability is the default first move on a failure mode](#39-pure-observability-first)
- §40. [Observability ships earn batching](#40-observability-ships-earn-batching)
- §41. [Every verification command needs a positive-confirmation test](#41-verification-commands-need-positive-confirmation)
- §42. [Live testing surfaces bugs spec'd tests can't reach](#42-live-testing-surfaces-bugs)
- §43. [Codebase conventions outrank external knowledge](#43-codebase-conventions-outrank-external-knowledge)
- §44. [Run a SECOND live test for trade-off-instead-of-fix outcomes](#44-run-a-second-live-test)
- §45. [Honest scope discipline beats fake completeness](#45-honest-scope-discipline)
- §46. [When the fix is small enough, "ship now or file?" → ship](#46-ship-now-or-file)
- §47. [Specs drift from code; grep before locking](#47-specs-drift-from-code)
- §48. [Concrete-in-prompt narrows the LLM's drift surface](#48-concrete-in-prompt)
- §49. [Format-unknowns demand fail-open + parse-unknown log line](#49-format-unknowns-demand-fail-open)
- §50. [Snapshot over delta (single canonical source)](#50-snapshot-over-delta)
- §51. [Bound-set autocomplete for any name parameter](#51-bound-set-autocomplete)
- §52. [Failure modes stack — fix what surfaces, don't predict next](#52-failure-modes-stack)
- §53. [Chroma session memory is a cross-turn behavior source](#53-chroma-is-a-cross-turn-behavior-source)
- §54. [Procedural confirmation ≠ re-decision](#54-procedural-confirmation-is-not-re-decision)
- §55. [Bot-appended over LLM-emitted for structured data](#55-bot-appended-over-llm-emitted)
- §56. [Diagnostic-grep-then-design beats design-from-spec](#56-diagnostic-grep-then-design)
- §57. [Verification plans describe target state, not prescribe command sequence](#57-verification-plans-describe-target-state)
- §58. [Sibling directives provide redundant coverage](#58-sibling-directives)
- §59. [Pure-function-in-orchestration sibling pattern](#59-pure-function-in-orchestration)
- §60. [Existing structural gates can do double duty](#60-existing-structural-gates-double-duty)
- §61. [Auto-cleanup of empty legacy containers](#61-auto-cleanup-empty-containers)
- §62. [Channel-as-author beats channel-as-name for filtering](#62-channel-as-author-beats-channel-as-name)
- §63. [Fork at the highest layer where invariants diverge](#63-fork-at-the-highest-layer)
- §64. [Naming-is-load-bearing-only-when-it's-load-bearing](#64-naming-is-load-bearing-only-when-it-is)
- §65. [Bot-Avrae write boundary: bot never emits `!`-commands](#65-bot-avrae-write-boundary)
- §66. [Doc auto-generation as drift defense](#66-doc-auto-generation-as-drift-defense)
- §67. [Advisory-to-binding promotion as load-bearing pattern shift](#67-advisory-to-binding-promotion-as-load-bearing-pattern-shift)
- §68. [Layer-deaf-not-broken — check input population before redesigning a layer](#68-layer-deaf-not-broken--check-input-population-before-redesigning-a-layer)
- §69. [Spec rules depending on data semantics that don't yet exist](#69-spec-rules-depending-on-data-semantics-that-dont-yet-exist)
- §70. [Fix blast radius can be wider than the bug](#70-fix-blast-radius-can-be-wider-than-the-bug)
- §71. [Verify computed claims in specs before locking](#71-verify-computed-claims-in-specs-before-locking)
- §72. [Outer guard required even when inner function already catches](#72-outer-guard-required-even-when-inner-function-already-catches)
- §73. [Discord verification is a human-in-the-loop handoff, not a Code task](#73-discord-verification-is-a-human-in-the-loop-handoff)
- §74. [Aesthetic transport endpoints soft-fail](#74-aesthetic-transport-endpoints-soft-fail)
- §75. [`INSERT OR REPLACE` is structurally hostile to ALTER TABLE-added columns](#75-insert-or-replace-is-structurally-hostile-to-alter-table-added-columns)

---

## §1a. LLM never decides mechanical outcomes

**Learned:** Session 6
**Trigger:** Five sessions of trying to make the LLM smart enough to be a DM. Phase 1.1 + 1.3 took one session because we stopped trying to make the LLM smarter and started making the system around it more structured.
**Doctrine:** The prompt is tone and pacing. The game is structured state. On the binding-mechanics surface: damage rolls, hit/miss resolution, HP tracking, spell slot consumption, condition application, save outcomes — all deterministic. Avrae owns these. LLM never approaches this surface. When the prompt isn't working, the answer is usually structure, not more prompt. Move decisions OUT of the prompt and INTO a rules engine; the prompt restates the engine's decision, never makes it.
**Applied in:** Every session after S6. Specifically: S7 combat-mode FSM, S8 orchestration/engine boundary, S11 advisory parsers, S12 canonical world state, S15 PC-vs-NPC identity guard, S21 concrete-state combatants block, S22 #1 inventory render, S23 #1 bot-appended state footer. Combat Playability Cluster #5.2 NPC Turn Automation (target selection + attack-choice fully deterministic — lowest-HP / closest-in-init / threat-prioritized rules drive enemy turns, LLM restricted to narration flavor only) and #5.3 Combat Cockpit (Turn Card lists affordances only via deterministic rendering, no LLM involvement).

The corollary: Friends & Fables learned this lesson over four years and rebuilt their engine. We learned it in six sessions and built the right architecture on the first attempt of the second iteration.

## §1b. LLM may suggest within bounded structured surfaces

**Learned:** Filed post-Gemini architecture review (May 2026); split from §1a to clarify where §1a's restriction does and does not apply.
**Trigger:** Track 7 #1 correctly rejected LLM-classified intent for the adjudication layer because the classification fed directly into binding verdicts with no validator gate — that was §1a territory. The rejection does NOT generalize. §1b names the validated-suggester pattern that operates correctly elsewhere in the system.
**Doctrine:** Targeted LLM calls returning structured output (JSON, enum, bounded vocabulary) are permitted when: (1) the output is a SUGGESTION, not an authoritative decision; (2) a deterministic Python layer validates the output before anything mechanically binds; (3) the user (DM or player) approves the suggestion before it affects mechanical state, OR the validator's reject path gracefully falls through to deterministic-only behavior. Pattern: LLM proposes → Python validates → user approves OR Python rejects → mechanical authority (Avrae or SQLite) executes the validated decision.
**Canonical instances already operating:** `npc_extractor.py` (LLM extracts NPC mentions from narration; name validators gate persistence; `npc_upsert` is the deterministic write); `consequence_extractor.py` (LLM extracts consequence proposals; severity caps and promotion thresholds gate persistence); `mechanical_hints.py` (LLM advisory parser; deterministic capability verdict system gates the runtime use); `dnd_knowledge_import.py` (LLM-augmented retrieval; chroma similarity scores + post-retrieval ranking deterministic).
**Why the split matters:** Track 7 #1's spec rejected LLM-classified intent for the ADJUDICATION layer because the classified intent BOUND mechanical outcomes through the adjudication chain — correct under §1a. That decision does NOT generalize to all LLM uses. §1b explicitly permits the validated-suggester pattern that Track 7 #1 correctly rejected for its specific surface but that operates correctly elsewhere.
**Doctrinal application — Combat Playability Cluster (#5):** #5.1 SRD fuzzy match — §1b applies (LLM suggests candidate monster name + confidence score; SRD index validates existence; DM approves the proposed `!init madd` command before it fires). #5.4 target disambiguation — §1b applies (LLM suggests target when intent is ambiguous across multiple valid init-list targets; init-list validator confirms target exists; player confirms before binding; deterministic fallback to clarifying-prompt when LLM call fails or confidence is low). #5.2 NPC turn target selection and attack-choice — §1a applies, stays fully deterministic. #5.3 Turn Card — §1a applies, deterministic rendering only.

## §2. Hard-stop rules go at the END of the prompt

**Learned:** Session 6
**Trigger:** LLM ignored "STOP after asking for a roll" the first time around.
**Doctrine:** For must-obey rules, place them at the end of the prompt and label them aggressively (e.g., HARD STOP RULES block). Last instruction wins.
**Applied in:** S10 (HARD STOP RULES 4-6), S18 (B2 attack-template carve-out in HARD STOP RULE 5).

## §3. Capture real system output; don't trust docs

**Learned:** Session 7
**Trigger:** Three reviewers (DeepSeek, Gemini, ChatGPT) all assumed Avrae uses embeds with descriptive titles for `!init`. They don't — Avrae emits plaintext, no embeds. `[INIT_CAPTURE]` revealed the truth.
**Doctrine:** When writing a parser against an external system, capture real output before writing code. Documentation describes intent; reality is the system. Format reconnaissance is a load-bearing pre-condition, not optional.
**Applied in:** S11 (`!coin` syntax was bare in some Avrae docs, actual is `!game coin +-Ngp`), S22 #2 (defeat-event format absent from Avrae across 30+ days of journals — pivoted from standalone parser to snapshot-delta).

## §4. AI reviewers excel at architecture, fail at empirical format

**Learned:** Session 7
**Trigger:** Three strong AI reviewers converged on the same plan philosophy and all were wrong on at least one implementation detail (Avrae wire format, session_id necessity, L4D pacing model, regex-only end detection).
**Doctrine:** AI reviewers are excellent at architecture and philosophy, weak at empirical format detection. The cure is the same every time: capture real data, write code against real data, validate against real data.
**Applied in:** S11 (calibration script against real LLM scenarios), S18 (B2 codebase-convention catch — Jordan caught what reviewers wouldn't have).

## §5. When the user pushes back, pause and listen

**Learned:** Session 7
**Trigger:** Multiple times in S7, Jordan pushed back ("clocks need autocomplete"; "don't chain push and systemctl"; "the L4D model is overengineered") and was right every time.
**Doctrine:** When the user pushes back, pause and listen, don't defend. Pushback is information; treat it as such.
**Applied in:** S10 (Jordan's stated preference on knowledge guidance — reverted same session), S13 (multiple corrections about workflow, time estimates, end-of-session call), S14 (skeleton.md edit workflow), S22 #2 (chroma purge approval).

## §6. Evolve from observed friction, not anticipated

**Learned:** Session 8
**Trigger:** Jordan said "I really don't want to be doing any / commands in Discord, I just want to roleplay." First Phase 3 sketch was auto-extraction with a proposal queue, lifecycle states, and per-feature extraction threads — premature abstraction.
**Doctrine:** The system evolves from OBSERVED friction, not ANTICIPATED friction. Ship the smallest change that makes the friction visible. Watch usage. Let data drive what comes next.
**Applied in:** S14 (S6 cache-warming, COMBAT_RX cleanup, sentinel — all from observed gaps), S16 (operating-model reframe formalizes this).

## §7. Discard the first design

**Learned:** Session 8
**Trigger:** Three "discard the first design" moments in S8: schema flattening on companions (3 fields → 1), idempotency tightening on `/encounter`, proposal queue → suggestion layer on Phase 3.
**Doctrine:** When external review pressure forces a redesign, the lighter version is usually right. The first design tends to over-build; the corrected version tends to be smaller and more correct.
**Applied in:** S9 (Suggested Actions allowed list cut, section reordering), S22 #1 (Phase 5 capability integration cut from inventory v1).

## §8. One live verification per step

**Learned:** Session 8
**Trigger:** Every Phase 2 patch shipped to the server, was tested in Discord, and produced the expected log lines BEFORE the next step started.
**Doctrine:** One live session per step is the discipline. Don't batch. Live verification per patch is cheap insurance, high payoff.
**Applied in:** S15, S18 (with the addition of `tests-to-run-post-session.md` as a standing artifact).

## §9. Don't engineer against model limits

**Learned:** Session 10
**Trigger:** Nine cumulative rules (HARD STOP 1-6 plus three sub-clauses) plus penalties weren't enough to make Llama follow instructions consistently. gpt-oss followed them with rules 1-3 alone.
**Doctrine:** Engineering effort spent fighting model limits is often misplaced. When a system architecturally separates "structure" (orchestration) from "interpretation" (LLM), the cost of swapping the LLM is small and the upside is large.
**Applied in:** Validates §1 — Virgil's structural layer ran identically on both models; only narration voice changed.

## §10. Trace the full pipeline before declaring done

**Learned:** Session 10
**Trigger:** Routing first patch silently failed — putting `groq_heavy` at the head of the candidate list wasn't enough; `sort_by_score` reorders by latency.
**Doctrine:** When patching a system with multiple sorting/filtering passes, trace the full pipeline before declaring done. Test the patch logic in isolation before plumbing it through a live system, especially when the system has scoring/filtering.
**Applied in:** S13 (cascade tracing), S16 (`extract_scene_updates` task_type drift caught via doc-update sweep).

## §11. Design preferences are the user's

**Learned:** Session 10
**Trigger:** Set `USE_KNOWLEDGE_GUIDANCE = False` without user buy-in, against Jordan's stated preference. Reverted same session.
**Doctrine:** Design preferences are not technical decisions Claude makes alone. When in doubt, escalate.
**Applied in:** S15 (architecture and Discord-behavioral escalation rule formalized in `feedback_escalation_points.md`), S16 (operating-model reframe), S21 (§11.B retroactive lock — Jordan picked the option, not Claude).

## §12. Advisory parser pattern

**Learned:** Session 11 (formalized as a third instance after Session 6 scene extraction and Session 9 Phase 3 auto-execute)
**Trigger:** Phase 11.1 mechanical hints needed a small dedicated LLM whose only job is reading Virgil's narration and emitting Avrae bookkeeping suggestions.
**Doctrine:** Advisory parser pattern: bounded text input → small LLM → strict structured output → deterministic validator → whitelist-restricted side effect. Reusable across domains.
**Applied in:** S16 (consequence_extractor — dual-pass), S22 #2 (loot generation — pure-function variant). Pattern also applied in S12A/B/C, S13, S15 — six-plus instances total.

## §13. Suggestion-only forever

**Learned:** Session 11
**Trigger:** Phase 11.1 mechanical hints. The temptation to add "auto-execute when confidence is high" was foreseen and refused.
**Doctrine:** Advisory parsers stay advisory. No "auto-execute when confidence is high" path. Auto-fire turns advisory into authoritative — a different system class. Player retains full authority over execution.
**Applied in:** S22 #1 (`/giveitem` is DM-mediated; auto-add to inventory rejected), S22 #2 (loot directive emits `!game coin +Nsp` for the player to type, not auto-fire).

## §14. Strict literal match beats fuzzy

**Learned:** Session 12
**Trigger:** Phase 12 chose strict matching with `npc_health` fragmentation reporting because fuzzy collapse risks false-positive identity merges.
**Doctrine:** Strict literal match + telemetry + future merge tool beats fuzzy match. Cost: occasional duplicate rows. Benefit: no silently-wrong merges. Telemetry tells us if drift is bounded or exponential.
**Applied in:** S13 (Ship 4 phantom-location telemetry — "skeleton_origin=0 AND mention_count=1" surfaces phantoms without auto-purging), S15 (`names_overlap` with explicit clauses, not fuzzy), S18 S23 (levenshtein `near_match` log surfaces disagreement; resolution stays human).

## §15. Authoritative-canon framing

**Learned:** Session 12
**Trigger:** Skeleton block prepended with explicit `═══ AUTHORITATIVE CANON ═══` framing was honored verbatim — Eldrin's authored description surfaced in narration on first try.
**Doctrine:** `═══` AUTHORITATIVE-CANON framing dominates LLM attention. Use for content the LLM must honor verbatim.
**Applied in:** S12 transition_context for `/travel`, S22 #2 loot directive ("AUTHORITATIVE and EXHAUSTIVE" framing in v1.1, with "supersedes any prior narration" override against chroma).

## §16. Engine defends its own invariants

**Learned:** Session 12
**Trigger:** `set_current_location` validates FK existence before writing. Engine refuses bad writes; callers trust the engine.
**Doctrine:** The engine defends its own invariants at the write boundary. Cost: one extra SELECT per transition. Benefit: no orphan FK state ever. Callers stay thin and trust the engine.
**Applied in:** S13 (`campaign_delete_cascade` refuses on active campaign; `campaign_set_status` enforces status enum), S15 (`npc_upsert` PC-overlap refusal at write boundary), S16 (`consequence_upsert` rejects re-capture of promoted rows), S22 #1 (`add_item`/`remove_item` refuse non-positive / over-removal).

## §17. Single write paths per field

**Learned:** Session 12
**Trigger:** Phase 12 enforced single write paths for `dnd_npcs` (through five-branch behavior matrix in `npc_upsert`) and for `dnd_scene_state.current_location_id` (through `set_current_location` only).
**Doctrine:** Each mutable field has exactly one writer. New code paths add behavior to the existing writer; they do not introduce parallel writers. The constraint is load-bearing for invariant enforcement (§16) and for cascade correctness (§19).
**Applied in:** S22 #1 (`add_item`/`remove_item` for `dnd_inventory`), S27 (`advance_time` is the sole runtime writer of `dnd_scene_state.campaign_day` / `day_phase` and `dnd_time_advancements`). Pattern applies across every mutable field in the system.

**Narrow-exception framing (S27).** When a second writer is genuinely needed, frame the exception narrowly enough that it cannot grow. Track 4 #3's `apply_starting_time_seed` is the project's first explicit narrow exception: campaign initialization writes `campaign_day` / `day_phase` directly during the first `/play`, bypasses `advance_time()`, and does NOT append to the audit log. The framing: *"`advance_time()` is the sole writer for runtime time advancement. Campaign initialization has a separate one-shot writer in the skeleton loader, scoped to the first-scene_state seed only, idempotent because the seed only fires when the row is at defaults."* Three guards keep the exception narrow: (1) one-shot — only fires on first `/play`, (2) idempotent — refuses to overwrite an advanced clock, (3) different audit channel — does not pollute the runtime advancement log. Future "second writer" temptations need this same narrow framing or they should be promoted to a real source enum value on the existing writer.

## §18. Engine primitive first

**Learned:** Session 13
**Trigger:** Both `campaign_delete_cascade` and `campaign_set_status` shipped with full test coverage before any Discord wiring. The Discord layer became thin and predictable.
**Doctrine:** Engine primitive first, command second. Build the primitive with full test coverage. The command becomes thin because every behavior it depends on is provably correct.
**Applied in:** S15 (`names_overlap` + `get_bound_character_names` shipped with 22 assertions before extractor wiring), S16 (consequence engine helpers before `/consequence list`), S22 #1 (inventory engine functions before `/inventory` and `/giveitem`), S22 #2 (loot engine + extractor before directive wiring).

## §19. Two independent gates before destruction

**Learned:** Session 13
**Trigger:** Hard-delete commands require BOTH structural state (archived) AND human confirmation (typed phrase). Either gate alone is insufficient.
**Doctrine:** Destructive operations need two independent gates. Active campaign cannot be hit by `/purgeallcampaigns` even with the right phrase because it isn't archived. The user must perform two independent actions to destroy data — that's not bureaucracy, it's the design.
**Applied in:** S15 (PC contamination guard at extractor + engine — same shape; either alone catches contamination, together they survive future edits to either layer).

## §20. Atomic batch no partial state

**Learned:** Session 13
**Trigger:** `/deletecampaign 5,17,6` doesn't archive 5, fail on 17, and leave you with mixed state. It refuses the whole batch and reports every problem at once.
**Doctrine:** Atomic batch operations validate every element before applying any. Predictable failure beats partial success when the user can fix and retry in one step.
**Applied in:** S22 #2 (loot enqueue ships per-defeat as separate rows but the surface-and-clear cycle is all-or-nothing per turn — failures leave the queue intact).

## §21. Diagnostic-before-treatment

**Learned:** Session 13 (named in S13; reinforced as a recurring meta-principle in S16 and S18)
**Trigger:** When `/purgecampaign` rejected the seemingly-correct phrase, my first instinct was to ship a fix. Jordan asked for the diagnostic first. The Python codepoint comparison showed the strings were byte-identical when manually typed — the issue was in transit from Discord, not in the comparison logic.
**Doctrine:** Always ask for current data before prescribing. Don't ship a fix while a diagnostic is still pending. The diagnostic IS the architecture step, not the fix.
**Applied in:** S16 (`godmode_gap` log line shipped before any constraint layer), S18 (entire S22-S25 batch is pure-observability before any constraint).

## §22. Re-stage from most recent output

**Learned:** Session 13
**Trigger:** Patched `discord_dnd_bot.py` against the wrong base; would have erased earlier step's changes if Jordan hadn't caught it.
**Doctrine:** When iterating across multiple Discord-side patches in one session, always re-stage from the most recent output. `/mnt/project/` is the SESSION-START snapshot; mid-session work re-stages from `/mnt/user-data/outputs/` or actual server pull. Post-Claude-Code: always re-read the file on disk before editing — don't trust a copy held in conversation context.
**Applied in:** Violated again in S13 (the rule was applied AFTER the violation); re-violated in S15 — the in-session staging discipline took two sessions to internalize. Carried forward to Claude Code era.

## §23. Time estimates don't belong

**Learned:** Session 13
**Trigger:** Led a recommendation with "~30 min scope." Jordan: "30 min scope? no bad logic try again remove scope."
**Doctrine:** Time estimates don't belong in priority recommendations. Time-to-ship is anxiety dressed as planning. The right axis is leverage, risk-of-rot, and what unblocks downstream work — not how fast it ships.
**Applied in:** S14 (roadmap rankings explicitly used leverage/risk-of-rot/daily friction), S16 (build-to-a-bar reasoning).

## §24. Hold a position when pushed

**Learned:** Session 14
**Trigger:** When Jordan asked "those are your top 2 choices for most valuable to the project?" I read it as a directive to re-rank instead of as a question, abandoned my picks (S6/S3) without defending them, and ended up confused.
**Doctrine:** Hold a position when pushed unless given new information. "Are you sure?" is not new information. Either defend the picks with reasoning or admit there's no coherent ranking criterion and ask what to optimize for.
**Applied in:** Strong corollary to §5 — listening is not the same as flipping. Listen when there's information; defend when there isn't.

## §25. Directives-as-imperatives

**Learned:** Session 14 (Track 3 entry — pacing, central thread, philosophy)
**Trigger:** Phase 1/12 solved "what is true?" / "what exists?" / "what can the player do?". Existing state — tension, clocks, hooks — was being declared in the prompt but ignored as decoration. The fix wasn't to build new state; it was to convert state into imperative directives.
**Doctrine:** Convert state from declaration to instruction. "Force a decision" beats "the air feels tense." Imperative-not-descriptive phrasing is the entire difference between Track 3 working and not working. Generalizes: most "the bot doesn't do X" complaints in a directive-driven system are "we need to convert state Y into a directive Z that says do X."
**Applied in:** S22 #2 (loot directive — AUTHORITATIVE/EXHAUSTIVE framing), S23 #2 (combat redirect — explanatory pressure on on-turn combat narration).

## §26. Ever-growing exception lists

**Learned:** Session 14
**Trigger:** First COMBAT_RX false-positive fix was a wall of fixed-width negative lookbehinds (`(?<!\bthe\s)(?<!\ba\s)...`). Test cases were all phrasings I thought of; every new false positive would require another lookbehind.
**Doctrine:** When a fix's design depends on an ever-growing exception list, the fix is wrong. Find a smaller scope where the exceptions disappear. (Cost of dropping `fire`/`shoot`/`loose` from COMBAT_RX: zero false positives, ever, at the cost of "I fire my bow" not auto-prompting the Avrae nudge.)
**Applied in:** S18 S23 (levenshtein `near_match` chosen over multi-rule fragmentation detection — single distance threshold, no exception list).

## §27. Workflow rules outrank simplicity

**Learned:** Session 14
**Trigger:** First instinct on adding a `## Player Capabilities` section to skeleton.md was a server-side `cat >> heredoc`. Jordan: "we don't do patches read your notes better." Workflow is build-locally / push / verify, not edit-on-server.
**Doctrine:** When a workflow rule conflicts with apparent simplicity, the workflow is usually right; default to it. The discipline that ships features is the same discipline that protects the system.
**Applied in:** S15 Claude Code migration — same rule survives the surface change (always re-read disk file before editing; don't trust conversation copy).

## §28. Defense-in-depth at parser + engine

**Learned:** Session 15
**Trigger:** PC contamination bug — the npc_extractor wrote "Donovan Ruby" as an NPC. Either layer alone (parser filter OR engine refusal) would catch it; together they survive future edits to either layer.
**Doctrine:** For load-bearing invariants, defend at both the parser and the engine. Same shape as the Phase 12 "two independent gates" discipline (§19) applied to canon contamination instead of destruction.
**Applied in:** S16 (consequence layer — `apply_consequence_proposals` validates and the engine refuses unresolved/PC-overlapping targets), S25 (advisory mode — both prompt rule AND structural absence of writes from the advisory code path).

## §29. Cleanup ships with the fix

**Learned:** Session 15
**Trigger:** Two PC-contamination rows (id=7, id=8) were already in `dnd_npcs` before the guard fix shipped. Deleting them in the same session as the fix means the system is in a coherent state.
**Doctrine:** Cleanup IS part of the ship. Leaving stale data after fixing the root cause means every future session has to look at the table and wonder which rows are bugs and which are data.
**Applied in:** S22 #2 (chroma purge of contaminated docs alongside the directive override clause — same session).

## §30. PC-vs-NPC identity is structure

**Learned:** Session 15
**Trigger:** Phase 12's design assumed the parser would see "Donovan Ruby" in narration and the LLM would respect a prompt instruction not to extract PCs. The narrative rule was being ignored.
**Doctrine:** Prompt rules are tone and pacing (§1). Structure is the game. PC-vs-NPC identity is structure — solve it with parser filters and engine refusals, not with prompt instructions.
**Applied in:** S22 #2 (PC filter on loot defeat enqueue uses `get_bound_character_names`, case-insensitive — not a prompt rule), S25 (advisory mode forbids state mutation structurally, not just by prompt).

## §31. Verify the running process

**Learned:** Session 15
**Trigger:** First Donovan/Ruby fix went out, Jordan reported the bug still happening. Diagnostic via journalctl: PID `1640406` had been running since 09:15:20 — long before the 13:35 fix. The bot wasn't restarted; the test was against pre-fix code.
**Doctrine:** When verification depends on a service restart, give the user the restart command first AND make it clear the test won't see the fix until it runs. Always verify the running process, not just the file on disk.
**Applied in:** S18 live verification — first move when "S22 didn't fire" was reported was checking the bot's actual start time (which preceded this session and already had the code).

## §32. Spec → review → revise → ship

**Learned:** Session 16
**Trigger:** Initial CONSEQUENCE_SURFACING_SPEC.md surfaced 9 locked decisions and 6 open questions. Jordan's review pass turned every open question into a locked one. Implementation read the locked spec like a contract.
**Doctrine:** Spec the unbuilt layer to the bar. Have the user review and lock decisions. Implementation reads the locked spec like a contract — every architectural choice traces back to a §1 lock. The spec stops being aspirational the moment it's reviewed; it becomes the authority. Speccing is the speed-up, not the slow-down.
**Applied in:** S22 #1 (inventory v1 spec-brief), S22 #2 (loot generation spec, with mid-spec architectural pivot).

## §33. Build-to-a-bar

**Learned:** Session 16
**Trigger:** Jordan is not playtesting until the system feels ready to share with friends. "Wait for friction data" is not a viable gate when the user won't produce the data.
**Doctrine:** Don't gate work on play data the user won't produce. Spec the unbuilt layer to the bar `THE_GOAL.md` describes, review it, ship it, tune from logs. Build-to-a-bar is the standing operating model.
**Applied in:** S18, S21, S22 #1, S22 #2, S23 #1, S23 #2, S23 #3, S25 — every ship since S16. Formalized in `feedback_no_playtest_gate.md`.

## §34. No pre-sequencing

**Learned:** Session 16
**Trigger:** Initial draft of CONSEQUENCE_SURFACING_SPEC proposed a sequenced "next 4 layers" appendix — `consequence surfacing → reputation/faction → curiosity reward → memory tiering`. Jordan: "Sequence proposals are dependency trees, not commitments."
**Doctrine:** Don't propose multi-spec sequences. Ship one v1, observe logs, re-decide what's next. Candidate next layers are a *menu of filed candidates*, never a sequenced roadmap.
**Applied in:** Every subsequent ship. Formalized in `feedback_no_pre_sequencing.md`. Spec docs (S16, S19, S20) all land as candidate-not-committed.

## §35. Dual-pass channel separation

**Learned:** Session 16
**Trigger:** A single blended parser reading both player and DM text creates self-reinforcing hallucination loops — the player threatens, the DM narrates the threat landing, the parser sees both and inflates one event into multiple consequences.
**Doctrine:** When parsing for state extraction across player and DM channels, run two parsers each on its own channel. Use a `sources` field that comma-merges on overlap. This is the same `mechanics-vs-narrative` invariant applied at the parser layer.
**Applied in:** S16 only so far (consequence_extractor); the pattern is filed for any future cross-channel extraction.

## §36. Parser-judged severity

**Learned:** Session 16
**Trigger:** Hardcoding "threat > betrayal > cruelty" or similar would bake one DM's intuition into the source.
**Doctrine:** Severity is parser-judged (e.g., 1-3); the validator only enforces the range. Descriptive anchors live in the parser prompt, not in code thresholds. Tunable from logs without a code change.

## §37. Doc passes are code reviews

**Learned:** Session 16 (and reinforced S18)
**Trigger:** Two consecutive sessions where doc-update sweeps surfaced real code drift. Session 16: `_CAMPAIGN_SCOPED_TABLES` missing `dnd_consequences` (caught while writing the doc update for VIRGIL_MASTER). Session 16 autonomous: `extract_scene_updates` using wrong `task_type` (caught while updating world_health docs).
**Doctrine:** Documentation passes are code review passes. Implementation focus and documentation focus have different attentional shapes; each surfaces different drift. Run both as routine session steps.
**Applied in:** S18 (premature doc-update sweep before second test pass — when the live test changed the answer, the doc had to be re-updated; the corollary is "doc-update sweep belongs AFTER the last live test, not after the last code ship").

## §38. Filed-not-sequenced

**Learned:** Session 16
**Trigger:** Committed-action layer is structurally similar to consequence surfacing. Could have been sequenced as "next ship"; instead filed as a candidate.
**Doctrine:** Specs for unbuilt layers land as filed candidates, not committed sequences. Ordering between filed candidates is re-decided after each ship's logs accumulate signal. No sequence appendix, no "recommended next" — just a menu the user picks from.
**Applied in:** COMMITTED_ACTION_RESOLUTION_SPEC.md (filed S16), reputation/faction/curiosity/items (filed throughout). Direct instance of §34.

## §39. Pure-observability first

**Learned:** Session 16 (`godmode_gap`), generalized in Session 18 (S22-S25 batch)
**Trigger:** When Jordan flagged the godmode failure mode in S16, the first move was a log line, not a fix. Behavior change is architecture territory; observability is fair game.
**Doctrine:** Pure-observability is the default first move when a failure mode surfaces. Ship the *measurement* without the *fix* — preserves architectural authority for the user and gives the eventual fix real signal to calibrate against. Diagnostic now, fix later (or never).
**Applied in:** S18 entire batch (S22 unconsumed_roll_swept, S23 npc_near_match, S24 prompt_size, S25 directive_emit), S22 #2 (`loot_directive: fired={0|1}` log on every turn for empirical baseline), S23 #2 (`combat_redirect:` empty-firing log).

## §40. Observability ships earn batching

**Learned:** Session 18
**Trigger:** Single log-line ships are too small to justify the doc-update overhead individually; bundling four (S22-S25) into a coherent batch amortizes the bookkeeping.
**Doctrine:** Observability is its own ship class. Pure-visibility log lines, no behavior change, no auto-merge — bundle related observability work into a coherent batch. The middle ground (a coherent batch of small, low-risk, no-behavior-change items) is its own valid shape.

## §41. Verification commands need positive-confirmation

**Learned:** Session 18
**Trigger:** `journalctl -u virgil-discord` returned nothing because `virgil-discord.service` is a USER unit (`--user -u` is required). Silent empty output looked identical to "the log didn't fire" — wasted ~2 minutes on the wrong hypothesis.
**Doctrine:** Every verification command needs a positive-confirmation test before it's trusted as a diagnostic. The grep should be tested with a known-firing log line first. Silent empty output from a broken grep looks identical to silent empty output from missing code. Future verification artifacts include a "test the grep itself" line.
**Applied in:** `tests-to-run-post-session.md` is now a standing artifact; future single-line observability ships append to it rather than landing without verification instructions.

## §42. Live testing surfaces bugs

**Learned:** Session 18
**Trigger:** B2 `<No Target>: Dealt 2 damage!` bug had been present since the combat directive was first written. Nothing in the test suite would have caught it because the test suite doesn't render to Discord and doesn't read Avrae responses.
**Doctrine:** Live testing surfaces bugs that spec'd test coverage can't reach. The bot's own observability isn't enough; user-rendered output is its own failure surface. Future ships consider: what would a human seeing this in Discord notice that the test harness wouldn't?
**Applied in:** S22 #2 (two-pass live verification caught the chroma contamination only after the v1 → v1.1 directive fix), S23 #1 (Stage 2 footer — Discord client rendering of `\n` confirmed via screenshot, not paste).

## §43. Codebase conventions outrank external knowledge

**Learned:** Session 18
**Trigger:** B2 spec added quotes for multi-word names (argparse positional convention). The codebase's `!check sleight of hand` path was right there in the same file, unquoted.
**Doctrine:** Codebase conventions are stronger than external knowledge. When adding new directive shapes or commands, grep the existing directives for syntax convention BEFORE writing — the established codebase is the spec; external knowledge is a hypothesis.
**Applied in:** S22 #1 (followed `_bindchar_autocomplete` / `clock_name_autocomplete` family for `_bound_character_autocomplete`).

## §44. Run a SECOND live test

**Learned:** Session 18 (B2 → B2.1 arc)
**Trigger:** B2 looked correct in spec, in tests, and in the first live test. The codebase convention violation (quoted multi-word names) and the narration-shrinkage regression both required a second live test against a human's eye.
**Doctrine:** Ship the spec, ship the test, run the live test — then run a SECOND live test that consciously looks for new failure modes the first fix might have introduced. Pre-and-post comparison is the only way to catch trade-off-instead-of-fix outcomes.
**Applied in:** S22 #2 — pass 1 (substitution-and-static-example) → v1.1 fix → pass 2 (chroma contamination surfaced, masked by pass 1's failure) → v1.2 (chroma purge + retrieval override).

## §45. Honest scope discipline

**Learned:** Session 18
**Trigger:** The post-B2.1 `<None>` issue was tempting to "also fix" — add target-resolution to the orchestration layer. Instead, B2.1 stopped at "the orchestration layer is now correct," and the Avrae-binding-layer failure was filed for the committed-action spec where it belongs.
**Doctrine:** Honest scope discipline beats fake completeness. The bigger ship has the right scope; the smaller ship preserves it. Cramming work meant for a different spec into the current ship balloons the fix into architecture territory and undoes the small-ship discipline.

## §46. Ship now or file

**Learned:** Session 18
**Trigger:** B2.1 fix shape was tiny (one Edit + 6 new assertions). The question was "ship now or file?" not "what shape?"
**Doctrine:** When a fix is small enough that the escalation question is "ship now or file?" — not "what shape?" — the right default is ship. Escalation cost equals shipping cost at that scale.

## §47. Specs drift from code

**Learned:** Session 21 (and reinforced S22 #1, S22 #2)
**Trigger:** §11.B's wording ("hard gate would be a parallel invariant violation") sounded principled in spec review, but Phase 2A.3 had already shipped exactly that gate.
**Doctrine:** Specs drift from code faster than code drifts from specs. When locking spec decisions that touch existing architectural surfaces, verify the surfaces still match the spec's mental model. Phase 1 of every spec includes grepping the codebase against every spec assumption that touches an existing surface (schema, regex, verdict lattice, decorator chain). The cheap thing — five minutes of greps — beats the expensive thing — locking decisions on a stale model.
**Applied in:** S22 #1 (Phase 1 diagnostic surfaced three spec-vs-reality divergences: vestigial schema, INVALID/VALID framing, WEAPON_CLAIM_RX scope — all caught before Phase 2 began), S22 #2 (Phase 1 grep across 30+ days of journals proved Avrae doesn't emit standalone defeat events; pivoted from new parser to snapshot-delta).

## §48. Concrete-in-prompt

**Learned:** Session 21
**Trigger:** Original §11.A recommendation was directive-only with abstract claims ("Avrae has the data, honor it"). Jordan retracted in favor of a parser-side data layer rendering "Garrick — HP unknown", "Donovan Ruby — HP 11/11" directly in the prompt.
**Doctrine:** When the LLM is told an abstract claim, it can drift around it. When the LLM sees concrete state pinned in the prompt, drift narrows to "what to do given THIS state" rather than "decide what's true and respond." Concrete-in-prompt narrows the LLM's drift surface.
**Applied in:** S22 #1 (`=== DONOVAN RUBY'S NOTABLE ITEMS === silver key` pinned in prompt — LLM took the cue and ran with the cellar narrative on the first test, no verdict layer required).

## §49. Format-unknowns demand fail-open

**Learned:** Session 21
**Trigger:** Phase 1 of the persistence spec explicitly flagged "HP rendering with sheet-bound characters — UNCONFIRMED." First real `!init list` confirmed the format with one new wrinkle (the AC suffix). The fix was 5 chars in a regex; the cost of NOT having flagged the unknown would have been a silent parser-failure mode.
**Doctrine:** When a spec ships with format-unknowns, the listener should have a fail-open path AND emit a parse-unknown log line, so the unknowns become observable on first real exposure. `[INIT_LIST_PARSE_UNKNOWN]` did its job.

## §50. Snapshot over delta

**Learned:** Session 21 (locked-(ii) over original §11.A option (ii)) and reinforced Session 22 #2
**Trigger:** Original §11.A option (ii) was incremental damage-event tracking (parse damage embeds, subtract HP). Locked-(ii) uses `!init list` snapshots — one canonical source, replace-in-place, no delta reconstruction across ~10 distinct embed shapes.
**Doctrine:** When choosing between "track every change event" and "replace-in-place from a periodic snapshot," prefer the snapshot. Single canonical source > delta reconstruction. Cost: snapshot can go stale between manual refreshes (filed as v1.x candidate if friction is high).
**Applied in:** S22 #2 (death-edge detection inside `update_combatants_from_init_list` — SELECT prior alive states before DELETE-INSERT, compute alive=1 → alive=0 transitions on insert. Single deterministic data source, no new parser needed).

## §51. Bound-set autocomplete

**Learned:** Session 22 #1
**Trigger:** Free-text `character` parameter in `/inventory` and `/giveitem` had typo-and-name-divergence risk.
**Doctrine:** Any slash command that takes a name from a bounded server-side set should have an autocomplete helper that queries that set. Never ask a user to free-text a name that already exists in DB.
**Applied in:** Joins existing `_bindchar_autocomplete`, `clock_name_autocomplete`, `quest_id_autocomplete`, `companion_name_autocomplete`, `companion_id_autocomplete` family. Pattern is now mature.

## §52. Failure modes stack

**Learned:** Session 22 #2 (loot v1 → v1.1 → v1.2 arc)
**Trigger:** v1 (loose language) → v1.1 (AUTHORITATIVE/EXHAUSTIVE framing + dynamic coin example) → v1.2 (retrieval override + chroma purge). Three failure modes, each surfaced only after the prior was fixed.
**Doctrine:** Prompt directives don't fail in just one way, and the failure modes don't reveal themselves all at once. First test exposes one axis; second test, with that axis fixed, exposes the next axis that had been masked by the first failure. When a directive ships and live-tests fail, fix what surfaces and re-test — don't try to predict what the next failure will be.
**Applied in:** Companion to §44 (run a SECOND live test). Pattern parallels S19's commitment directive layered defenses (multiple gates because multiple failure modes).

## §53. Chroma is a cross-turn behavior source

**Learned:** Session 22 #2 (and reinforced as a §4 invariant in S25)
**Trigger:** Pass-2 of loot live-test kept the iron ring + parchment + copper coins from the prior failed turn. Diagnosis: `chroma_search` retrieved the contaminated DM turn from pass 1 as "RELEVANT PAST EVENTS" and the LLM treated it as authoritative.
**Doctrine:** Chroma session memory is a load-bearing source of cross-turn behavior, not just nice-to-have context. Any failed LLM narration that gets stored becomes a re-injection vector for future similar turns — contamination compounds unless explicitly broken. When a directive enforces specific outputs and live testing fails, the failed narration goes into chroma; before re-testing, audit chroma for the failed phrases. Either purge or include an explicit override clause ("supersedes any prior narration and is the current ground truth"). Defense-in-depth around chroma writes — don't import chroma writers from new code paths unless the path produces canon-grade narrative material.
**Applied in:** S25 (advisory mode forbids chroma writes structurally — `dnd_orchestration.py` doesn't import `dnd_engine`'s chroma functions on the advisory path).

## §54. Procedural confirmation is not re-decision

**Learned:** Session 22 #2
**Trigger:** Jordan's response to the chroma purge proposal was "Show me the doc ids before delete (procedural confirmation, not a re-decision). Export-then-delete is the right safety pattern."
**Doctrine:** A destructive operation gets a procedural step where the agent shows its work and the human confirms targets are correct. The *whether-to-do-it* decision was already made when the prior message approved the plan. Don't conflate procedural confirmation with re-decision — agent enumerates targets + shows export plan + executes; human's role at that step is to verify the targets, not to re-decide the action.

## §55. Bot-appended over LLM-emitted

**Learned:** Session 23 #1
**Trigger:** State footer's content (mode, round, current turn, next combatant, PC-vs-NPC) is all available as DB-backed deterministic data. Pulling it through the LLM adds a translation step where the LLM can hallucinate or drift.
**Doctrine:** When the data is structured and deterministic, bot-append it. Costs zero LLM tokens, can't be hallucinated wrong, survives prompt-engineering changes elsewhere, deterministically testable as pure functions. Reach for LLM-emitted only when the surface needs creative variation, evaluation, or content the bot can't compute.

## §56. Diagnostic-grep-then-design

**Learned:** Session 23 #1
**Trigger:** Phase 1 of the spec called for finding where the existing footer comes from before designing the extension. Output of `grep -n "footer\|⚔\|📍" *.py` localized the writer in 5 seconds.
**Doctrine:** When extending an existing UI surface or behavior, the first 60 seconds of work is a grep to find the existing writer. Don't design from the spec; design from where the code actually is. The grep answer is load-bearing for design choice (bot-appended vs LLM), integration point (single hook), test boundary (pure function), and telemetry placement.
**Applied in:** Specific instance of §47, framed for UI/code extension.

## §57. Verification plans describe target state

**Learned:** Session 23 #1 (and reinforced S23 #2)
**Trigger:** Test plan had `!init begin` + add combatants + narrate, expecting combat-with-active-turn footer. Avrae's behavior (round 0 pre-state, no active actor until `!init next`) made the fallback path fire instead. Two consecutive sessions, three Avrae init rolls, and the predictions were 0/3.
**Doctrine:** Verification plans for external state machines describe target state ("on Donovan's turn, type a bypass") rather than prescribe command sequence ("Stage 3 = !init next then narrate"). Stage assignments should be conditional on Avrae state, not numerical.
**Applied in:** S23 #2 bonus stage — Jordan ran `!init begin` + adds + `!init next` until landing on Donovan, then typed the bypass. The bonus stage was the right pattern.

## §58. Sibling directives

**Learned:** Session 23 #2
**Trigger:** Bonus stage exposed: between Donovan's turn narration being posted and the next narration arriving, Avrae auto-advances to GO1's turn. When the bypass arrives, active_turn is now GO1 — `combat_redirect` correctly gates out as "PC turn only." But the redirect *behavior* still landed via the persistence directive on the NPC's turn.
**Doctrine:** Don't try to make a single directive fire on every variation of a failure mode; layer complementary directives that fire on different turn phases / intent classifications / state transitions, and the architectural intent gets covered redundantly. Single-failure-mode-fixed-by-two-directives is healthy, not a defect.

## §59. Pure-function-in-orchestration

**Learned:** Session 23 #1 (third instance — formalized as the canonical pattern)
**Trigger:** `render_state_footer` was the third sibling. By S23 #2 there were four. By S23 #3, five — and the pattern extended from narrative directives to infrastructure ops (`compute_setup_plan`).
**Doctrine:** Compute pure functions returning `(body, signals)` (or `plan` dict for ops). Caller wraps in try/except, fetches inputs from DB, calls the pure function, emits per-turn empirical-baseline log line regardless of fire status, executes via I/O wrapper. Soft-fail at call site so directive errors NEVER block narration posting. Future ships defaulting to this template inherit testability, idempotency-as-property, observability for free.
**Applied in:** Five canonical instances by S23 #3:
1. `compute_loot_directive` (Track 4 #2, S22 #2)
2. `compute_persistence_directive` (Track 3, S21)
3. `render_state_footer` (Track 6 #1, S23 #1)
4. `compute_combat_redirect_directive` (Track 6 #2, S23 #2)
5. `compute_setup_plan` (S23 #3)

Plus `build_advisory_context` in S25 — sixth instance.

## §60. Existing structural gates double duty

**Learned:** Session 23 #3 (and reinforced S25)
**Trigger:** Line-594 routing gate that filtered non-`#dm-narration` text channels was already in place for the original 7-channel structure. When `#dm-aside` was added, the gate gave it correct no-op behavior automatically — no special-casing needed.
**Doctrine:** When adding a new routed surface, check whether existing routing infrastructure already handles the no-op case correctly. Often it does, and the new surface inherits the protection for free.
**Applied in:** S25 (Track 6 #3 advisory routing — single `if message.channel.name == CHANNEL_NAMES['aside']: ... return` branch ABOVE the existing gate; inherits all existing protections).

## §61. Auto-cleanup empty containers

**Learned:** Session 23 #3
**Trigger:** Planner's `legacy_category_to_delete` field ran end-to-end without operator intervention — `/setup` migrated channels out of `🎲 D&D` and detected the category was empty afterward, so it deleted the category in the same execution.
**Doctrine:** When migrating from a v1 layout to v2, detect-and-clean empty containers automatically. Saves a manual cleanup step and turns a multi-step migration into a single command. Side benefit: makes the migration robust against operator-forgetting.

## §62. Channel-as-author beats channel-as-name

**Learned:** Session 23 #3
**Trigger:** Avrae listener filters by author (`al.is_avrae(message)` — user ID), not by channel name. Consolidating dice rolls into `#dm-narration` required zero listener changes.
**Doctrine:** When routing decisions depend on "who sent it" rather than "where it landed," filter by author/sender ID. Channel names are operator-configurable surfaces that drift; user IDs are stable. Save channel-name filtering for genuinely surface-specific behavior.

## §63. Fork at the highest layer

**Learned:** Session 25
**Trigger:** First instinct on Track 6 #3 advisory was "advisory is just narration with a different prompt" — refactor `_dm_respond_and_post` to share with advisory. Actual implementation went the other direction: separate handler, separate context-builder, separate router task, separate post path.
**Doctrine:** When adding a new mode that shares a substrate with an existing mode but has different invariants, fork at the highest layer where the invariants diverge. Don't refactor the existing mode to accommodate; build a parallel sibling and let the routing layer decide. The shared substrate becomes the inputs (state readers), not the orchestration. Every "must NOT do X" rule then enforces structurally because the new path simply doesn't have a code path that does X.

## §64. Naming-is-load-bearing-only-when-it-is

**Learned:** Session 25
**Trigger:** `#ooc-commands` got renamed to `#commands` mid-ship because the OOC category prefix made the channel name redundant. Touched `CHANNEL_NAMES`, `CHANNEL_CATEGORY`, the topic dict, and 16 test sites. All failures were `sorted(...)` mismatches, fast to diagnose.
**Doctrine:** Don't be afraid to rename mid-ship if the original name reads poorly. The test surface for a canonical-shape constant is broad but failures are mechanical. The cost of a bad name persists; the cost of a rename is bounded to test churn.

## §65. Bot-Avrae write boundary

**Learned:** Session 22 #1, reinforced S22 #2 and S25 (load-bearing core invariant)
**Trigger:** Loot directive emits `!game coin +Nsp` as a mechanical hint inline; the *player* types it. The bot itself never writes Avrae commands. Advisory mode (S25) explicitly forbids `!`-prefixed bot emission.
**Doctrine:** Avrae is the sole authority for mechanics. Virgil is the mechanics-consumer, not a mechanics-mirror. The bot does NOT emit `!`-prefixed commands. LLMs can emit them (in narration responses, for the player to copy or as suggestions); the bot side never does. This is a load-bearing invariant in VIRGIL_MASTER §4.
**Applied in:** S25 (advisory prompt explicitly forbids `!`-prefixed emission; structural defense — advisory path doesn't touch Avrae anyway).

## §66. Doc auto-generation as drift defense

**Learned:** Session 25 #2 (Track 6 #3.2)
**Trigger:** Track 6 #3.1 shipped `COMMANDS.md` as a manual reference. Maintenance protocol committed Code to update the doc when commands changed, but discipline-based defenses against drift always erode. Auto-generation from bot decorators eliminates Virgil-side drift structurally.
**Doctrine:** When a doc duplicates structured information already present in code, generate the duplicated portion from the code on a deterministic trigger (startup, build, scheduled job). Preserve hand-edited regions via marker-bracketing (`<!-- AUTO_GENERATED:START -->` / `END`). Idempotency required: same input produces no write. Soft-fail on missing markers or files.
**Applied in:** Session 25 #2 (Virgil command section of `COMMANDS.md`, generated from `bot.tree.get_commands()` on startup, Avrae section preserved between markers).

## §67. Advisory-to-binding promotion as load-bearing pattern shift

**Learned:** Session 25 #4 (Track 7 #1)
**Trigger:** Multiplayer test (S25 #3) exposed that the directives shipped through S23 (persistence, loot, redirect, footer) and S25 (advisory) were all *advisory* — the LLM was asked to honor them but wasn't structurally bound. Under play pressure from a real second player who probed limits naturally, the LLM folded on every meaningful test. Failed rolls produced success narration. "Says who" defeated capability refusals. Player declarations became outcomes. The eight failures (F-45 through F-52) shared one root.
**Doctrine:** Advisory directives compose cleanly and scale, but the contract with the LLM is fragile. When an architectural decision *must* hold regardless of LLM cooperation, promote the relevant gate from advisory (LLM is asked to honor) to binding (Python decides, narration is constrained). Binding looks like: pure function returns a structured verdict (allowed / refusal_kind / narration_constraint) BEFORE the prompt is built; verdict renders top-of-prompt as a hard constraint and bottom-of-prompt as last cache before generation; sibling advisory directives deduplicate against the binding verdict so they don't double-block. The LLM never decides whether the gate fired — it only narrates the approved outcome.
**Applied in:** Session 25 #4 (Track 7 #1 Adjudication Layer — five action categories, single pure function, top+bottom rendering, §11.L deduplication of redundant advisory directives). Sibling advisory directives (capability_decision, commitment_directive, combat_redirect) become consumers of adjudication's verdict instead of independent advisors.

## §68. Layer-deaf-not-broken — check input population before redesigning a layer

**Learned:** Session 25 #4 (Track 7 #1 live test) → Session 25 #5 (Track 7 #1.1 fix)
**Trigger:** Track 7 #1 capability adjudication landed 4/7 binding instead of 7/7. The three capability tests (Fireball / Sneak Attack / Rage) all logged `category=capability allowed=1` — adjudication *deferred* because `primary_ctx=None` for every Jordonovan turn. Pre-existing condition: `cache_warm` at startup loaded only Bruce Banner; Jordonovan was never cached. Adjudication's `_gate_capability` returned `(True, "no_character_context")` per the partial-projections doctrine — INVALID verdicts only fire on EXPLICIT contradiction from authoritative data, never inferred from gaps. Without Jordonovan's sheet, the gate had no authoritative source to contradict against. The fix was small (cache_autopopulate on `!sheet` post); the architecture jumped from 4/7 to 7/7 binding.
**Doctrine:** When a layer appears to under-perform, BEFORE redesigning it, check whether its inputs are populated. A layer that defers safely on missing input is functioning correctly — it's just deaf, not broken. The fix lives upstream at the input layer, not in the deferring layer's logic. This applies to any gate that depends on authoritative data (capability adjudication, NPC stat hydration, location resolution, inventory checks).
**Applied in:** Session 25 #5 (cache_autopopulate triggered on `!sheet` post → adjudication 4/7 → 7/7 binding with one startup-time fix). The architecture was deaf, not broken.

## §69. Spec rules depending on data semantics that don't yet exist

**Learned:** Session 25 #6 (Bug 3)
**Trigger:** Spec for Bug 3 locked the rule "NULL `location_id` = always-present" — intuition being narrators, deities, party-wide entities should surface regardless of location. Data model didn't match: `npc_extractor` leaves `location_id NULL` by default for any NPC it can't location-pin, so NULL meant "fabricated junk drawer" not "always-present set." Post-Bug-3 testing showed Keeper of the Vein still surfacing because Keeper had `location_id IS NULL`. Strict filter (NULL = silent) was the right call.
**Doctrine:** When a spec rule depends on data semantics, verify the column actually carries that meaning. If it doesn't, either (a) add a column that does — deferred until needed; or (b) use the strict interpretation that matches the actual data model. Locking a rule that depends on intended-but-unimplemented data semantics pre-commits the drift. The "always-present NPC" set comes back later with a dedicated `is_omnipresent` flag column when there's actually a use for it.
**Applied in:** Session 25 #6 (`get_recently_active_npcs(..., location_id=...)` strict filter — `WHERE location_id = ?` only, NULL silent).

## §70. Fix blast radius can be wider than the bug

**Learned:** Session 25 #6 (Bug 3 mid-ship catch)
**Trigger:** Mid-Bug-3 verification, the new NPC location filter quietly degraded to None-passthrough (`location_filtered=0` everywhere despite `current_location_id` being correctly set in DB). Tracing led to `get_scene_state` having never SELECTed `current_location_id` from `dnd_scene_state` — function's returned dict had no such key, so `scene_state.get('current_location_id')` always returned None. Fixing the SELECT incidentally re-activated three other directives' location-enrichment paths: consequence directive (line 4779), commitment directive (line 4831), init directive (line 4856) all had `current_loc = scene_state.get('current_location_id')` guards followed by `at_location` enrichment that had been silently dormant since the column was added.
**Doctrine:** When a SELECT regression silently degrades a feature, fixing it can incidentally fix unrelated features that depend on the same SELECT. After fixing a data-access regression, verify what else reads from the same well — don't assume the fix's blast radius is local. The wider blast radius is sometimes the bigger win.
**Applied in:** Session 25 #6 (Bug 3 fix re-activated dormant location-enrichment in three sibling directives; `npcs_in_context: location_filtered=1` only landed AFTER the get_scene_state SELECT was extended).

---

## §71. Verify computed claims in specs before locking

**Learned:** Session 26 (Track 6 #5.1 — spec v1 → v1.2 Jaccard test corrections)
**Trigger:** Tests 9–10 in the v1 spec asserted specific Jaccard scores for fuzzy-match examples: "cave giant spider" and "giant cave spider" were claimed to produce different Jaccard scores against "giant spider" (0.5 and 0.667 respectively). Both tokenize to `{"cave", "giant", "spider"}` — Jaccard is order-insensitive. Both score 0.667 against any key containing `{"giant", "spider"}`. The 0.5 score was mathematically impossible: there was no input/key pair that produced it. The review doc caught it by running the math; the v1.2 spec replaced the examples with verified ones ("cave toad" → None at J=0.0; "swarm bats" → Swarm of Bats at J=2/3). If the error had reached implementation, test 9's `None` assertion would have failed on first run with no clear path to diagnosis.
**Doctrine:** Specs that contain computed claims — Jaccard scores, probability bounds, threshold comparisons, character counts, row counts, timing assumptions — must have those claims verified before the spec is locked. A computed claim that cannot be reproduced when implemented is a spec defect, not an implementation trade-off. Verification belongs in the spec session (run the math in a REPL, grep the data, count the rows). If you can't verify the claim at spec time, mark it as an estimate rather than a locked assertion. This is distinct from §47 (specs drift from code over time); §71 addresses spec-internal inconsistency at write time — the spec contradicts itself before any code exists.
**Applied in:** Session 26 (TRACK_6_5_1_SPEC.md v1.1 → v1.2: tests 9–10 Jaccard examples replaced after running `len({'cave','toad'} & {'giant','frog'}) / len({'cave','toad'} | {'giant','frog'})` in Python to confirm J=0.0 for "cave toad" and J=2/3 for "swarm bats" before locking the corrected test assertions).

## §72. Outer guard required even when inner function already catches

**Learned:** Session 26 (Track 6 #5.1 — defense-in-depth test 14 catch)
**Trigger:** Test 14 patched `_llm_suggest` to raise `RuntimeError("network")` and verified that `resolve()` returned `None` without propagating. `resolve()` had no try/except around the `_llm_suggest` call — the test failed. `_llm_suggest` already catches all exceptions internally (its try/except returns `None` on any failure). The inner catch was correct, but `resolve()` is the load-bearing outer boundary: if `_llm_suggest` is ever replaced, refactored, or called through a different path that bypasses the internal catch, `resolve()` must remain safe regardless. The outer guard is the contract boundary; the inner catch is an implementation detail.
**Doctrine:** When function A is the public-facing safe boundary and function B is a helper A calls, A must guard against exceptions from B even when B is already safe. The inner catch is B's implementation; the outer guard is A's contract with its callers. If B changes — its catch is removed, its signature changes, it's mocked in a test — A's outer guard is the last line of defense. Sibling to §28 (defense-in-depth at parser + engine layer boundary): §28 applies to the parser/engine boundary specifically; §72 applies to any public function calling a helper that is "supposed to" be safe. "Supposed to be safe" is not a contract; a surrounding try/except is.
**Applied in:** Session 26 (srd_resolver.py `resolve()` — added `try: llm = _llm_suggest(creature_name) / except Exception: llm = None` block around the call. Test 14 caught the missing guard; fix was one line; 31/32 → 32/32 tests passing).

## §73. Discord verification is a human-in-the-loop handoff

**Learned:** Session 27 (Track 4 #3 Time Progression v1 — implementation handoff). Refined later same session after the cooldown duration assumption proved wrong by a factor of 6+.
**Trigger:** Track 4 #3 implementation cycle hit a Discord rate-limit lockout (HTTP 429 / error 40062) from a cluster of `systemctl --user restart virgil-discord` calls during test-driven migration. The bot ended Session 27 at status `inactive`, the live verification scenario could not run, and the ship sat at ⏳ LIVE VERIFY PENDING with the gateway in cooldown. The cluster came from Code reaching for restart as the heaviest available "did this take effect" tool — restart-as-import-validation conflated with restart-as-Discord-verification. Code cannot post to Discord, observe channel responses, or close the behavioral verification loop. Restart cycles in pursuit of Discord feedback produce no signal Code can read AND burn rate-limit budget against the gateway.
**Doctrine:** Discord-side behavioral verification is Jordan's lane, not Code's. Code stays in the structural lane (write code, run tests, syntax-check, ONE restart at end of session) and produces a numbered list of Discord prompts/commands for Jordan to enter. Jordan replies "ok done" once the prompts have been entered. Code then reads `journalctl --user -u virgil-discord` and greps for the expected log shapes, debugging from journal evidence — without restarting again in the same session. If a fix requires a code change, that change ships in the next session with its own single restart. Module-import validation runs via `python3 -c "import <module>"`, never via `systemctl restart`. Restart is the deploy step, not the feedback loop.

**Workflow contract:**
1. Code implements, runs tests offline, syntax-checks, and restarts the bot ONCE at end of session.
2. Code produces a numbered list of Discord prompts/commands for Jordan, with expected behavior per step (footer text, aside message, log line shape) and the grep patterns Code will use to verify.
3. Jordan enters the prompts in Discord at his pace. Replies "ok done" or notes any visible anomaly.
4. Code reads `journalctl --user -u virgil-discord --since "<session start>"`, greps for the expected telemetry, and reports verification status per step.
5. If a fix is required, that fix ships in a new session — never two restarts in the same session.

**Why this is locked rather than guidance:** the cluster-restart pattern is structurally appealing to Code's iterative discipline. Without an explicit rule, Code will reach for restart again. The fix is making the validation tool lighter (`python3 -c "import <module>"` for import-validation; tests for behavior-validation; restart only as the deploy step), not exhorting Code to be restrained.

**Cloudflare-edge ban shape (S27 mid-session correction).** Discord puts its API behind Cloudflare. The 429s under `error code: 40062` are NOT Discord's per-route application rate limits — they are Cloudflare's edge-level WAF lockout, triggered when an account/IP looks like a credential-stuffing attacker. Three properties to internalize:

- **Multi-hour, not 30-minute.** S27's first writeup of §73 assumed a ~30-minute cooldown. The actual decay observed: cluster of ~50 failed `/users/@me` retries between 12:22-12:33 PDT; login endpoint thawed by 14:01 (~90 min later); `POST /channels/{id}/typing` was STILL locked at 14:48 (~135 min later). Realistic clear for moderate hammering is 3-6 hours, sometimes a full day. "Wait 30 minutes" is the wrong mental model.
- **Decays per-endpoint, not globally.** "Bot logs in successfully" does NOT mean "bot is fully usable." Login can clear while typing, message-send, and other endpoints remain throttled. The library logs both layers as `429`, which obscures the difference. Always sanity-check a non-login endpoint before declaring the cooldown over.
- **4-minute login latency is the canary.** A normal Discord login completes in ~3 seconds. If the journal shows a 60+ second gap between `starting Discord DnD bot` and `Discord DnD bot ready`, the gateway is barely-thawing — assume other endpoints are still locked even though login succeeded. Don't run live-verify until login latency is back to seconds.

**The amplifier (systemd auto-restart) is a separate fix.** §73's trigger pattern was Code-initiated (one explicit `systemctl restart` at a time), but the *damage* came from systemd's default auto-restart loop free-firing additional retries between Code's commands — `Restart=always` with no `StartLimitBurst` cap turned each Code-initiated restart into ~5-10 systemd-initiated restarts before the human noticed. Even with §73 fully observed, a single restart against an already-throttled service can amplify into a Cloudflare-tripping cluster. The structural fix lives in the `.service` unit: `StartLimitIntervalSec=300` + `StartLimitBurst=3` caps the auto-loop at 3 attempts in 5 minutes, after which systemd marks the unit `failed` and requires manual `systemctl --user reset-failed`. Audit any future bot service file for these guards before assuming "one restart" actually means one restart.

**Applied in:** S27 closeout (Track 4 #3 live verification handoff). S27 mid-session §73 refinement (multi-hour correction added after the same cooldown the doctrine was written about persisted past the 30-minute assumption). S27 systemd unit hardening (`virgil-discord.service` patched with `StartLimitIntervalSec=300` + `StartLimitBurst=3`).

## §74. Aesthetic transport endpoints soft-fail

**Learned:** Session 27 (Track 4 #3 verify-attempt-1 blocked by Cloudflare-edge 429 on `POST /channels/{id}/typing`). Shipped + reaffirmed Session 28 (Bug 4).
**Trigger:** S27 verify-attempt-1 of Track 4 #3 hit a hung `/play` — the slash command never replied to the user. Root cause: `async with narration_ch.typing():` raised `discord.HTTPException: 429 Too Many Requests (error code: 40062)` from Cloudflare's edge layer (residual cooldown from earlier in the session). The exception propagated through `app_commands._do_call` → `CommandInvokeError`, surfacing to the user as "spinning slash command, no reply." Track 4 #3's code did NOT error — `scene state initialized for campaign 20` fired before the 429 hit. The bug was purely Discord transport: the typing indicator (an aesthetic "user is typing..." dot that decays after ~10s) was wired such that its 429 could block the entire narration handler.
**Doctrine:** Discord's HTTP layer is tiered. **Aesthetic endpoints** (typing, presence, status updates — anything where failure has zero narrative consequence and the indicator decays on its own) must be wrapped in `try/except (discord.HTTPException, asyncio.TimeoutError)` at every call site, with the handler body executing regardless of whether the aesthetic context succeeded. **Semantic endpoints** (message send, embed post — anything that delivers content the player will read) keep their existing per-handler boundaries and may legitimately surface failures up the stack. Handlers should not have to know which transport tier any given endpoint belongs to; the soft-fail wrapper at the call site is what makes the distinction operational. Per-site telemetry (e.g. `typing_indicator_failed: command={...} err={repr}`) fires only on the exception path, so transport-tier degradation is observable without log noise on the happy path.

**Soft-fail shape — Shape A (preferred for short bodies):** wrap the context manager in try/except, duplicate the handler body under except. Two-fold execution path: aesthetic context wins → body runs inside it; aesthetic context raises → body runs without it. The duplicated body is acceptable because it's typically 1–4 lines and the alternative (helper function) only pays off at ~10+ lines.

```python
try:
    async with channel.typing():
        # body
except (discord.HTTPException, asyncio.TimeoutError) as e:
    log(f"typing_indicator_failed: command={label} err={e!r}")
    # body  (duplicated, no aesthetic context)
```

**Why this is locked rather than handler-by-handler discretion:** without a structural rule, the next aesthetic endpoint added to a handler (presence updates, reaction adds, etc.) repeats the S27 failure mode — a handler-author who wasn't around for the 429-hung-`/play` outage assumes the context manager is safe and skips the wrapper. The doctrine says: every aesthetic Discord call gets the wrapper, no exceptions, no judgment calls.

**Cross-references:** §59 (pure-function-in-orchestration / soft-fail at call site — sibling pattern; §74 specializes §59 for transport-tier endpoints rather than orchestration helpers). §73 (Discord verification is a human-in-the-loop handoff — surfaced the cooldown that surfaced §74).

**Applied in:** S28 Bug 4 ship — three Shape A wrappers in `discord_dnd_bot.py` at `_advisory_respond` (line 1574), `_dm_respond_and_post` (line 1707), and `/play` (line 2950). All three are `async with channel.typing():` sites. Per-site `typing_indicator_failed:` telemetry. S28 verify confirmed the wrappers don't change happy-path behavior (zero exception-path log lines fired during three live `/play` invocations).

## §75. `INSERT OR REPLACE` is structurally hostile to ALTER TABLE-added columns

**Learned:** Session 29 (Bug 5 / ROADMAP 4d — surfaced by 4b's state-aware footer verify-walk).
**Trigger:** S29 verify of 4b's `/play` footer wiring on campaign 21 showed `Day 1, Morning` instead of the expected `Day 5, Evening` (S28 had directly written `(5, 'Evening')` to `dnd_scene_state` via SQL). 4b's wiring was correct — the value rendered IS what was in the DB. The bug was upstream: `init_scene_state` was using `INSERT OR REPLACE` listing only the original-schema columns. Every column added via ALTER TABLE migration since the original schema (`campaign_day`, `day_phase`, `current_location_id`, `turn_counter`, `last_dm_response`, `tension_int`, `progress_clocks`) was absent from the column list. SQLite's `INSERT OR REPLACE` is a delete-then-insert: the existing row is removed entirely, a new row is inserted with the listed columns set to their VALUES, and unlisted columns fall back to schema defaults. Track 4 #3's `advance_time()` writes survived in-session, but the moment `/play` ran (which calls `init_scene_state` unconditionally), the migrated columns flipped back to `(1, 'Morning')`. The audit log in `dnd_time_advancements` was untouched (separate table), so the live scene state lied while the audit trail told the truth.
**Doctrine:** When a table accumulates columns via ALTER TABLE migration, any writer using `INSERT OR REPLACE` with a fixed column list silently regresses every column added since the writer was authored. The bug is invisible at write time (no error), invisible in tests that don't exercise the migrated columns, and surfaces only when a downstream feature depends on the migrated column's persistence across writes. **Default to `INSERT INTO ... ON CONFLICT(pk) DO UPDATE SET` listing only the fields the writer actually intends to set.** New rows still get full schema defaults via the plain INSERT path; existing rows preserve every column the writer doesn't explicitly touch. This is the correct pattern for any `upsert`-shaped writer on a table that has ever been migrated, and for tables that may be migrated in the future. The narrow alternative (add the missing columns to the existing list) closes the immediate bug but ships a time bomb — the next ALTER TABLE-added column repeats the failure on whatever future feature depends on its persistence. Cost difference between narrow and structural is typically zero (same line count); the structural fix earns its keep on the next migration.

**Cross-references:** §70 (fix blast radius can be wider than the bug — sibling pattern; §70 covers SELECT regressions, §75 covers INSERT regressions, both in the same migration-history shape). §47 (specs drift from code over time — this is a structural fork: drift in writer column lists vs schema column count is silent regression, not declared drift).

**Applied in:** S29 (`dnd_engine.py:init_scene_state` switched from `INSERT OR REPLACE INTO dnd_scene_state (...12 original columns...) VALUES (...)` to `INSERT INTO ... VALUES (...) ON CONFLICT(campaign_id) DO UPDATE SET last_scene_change=excluded.last_scene_change, updated_at=excluded.updated_at`. Live-verified by re-seeding campaign 21 to `(5, 'Evening')`, running `/play`, and confirming sqlite post-`/play` still showed `21|5|Evening|<refreshed timestamp>` — day/phase preserved, only `updated_at` rotated. Pre-fix the same sequence produced `(1, 'Morning')`).

**Audit trail:** other writers in the codebase using `INSERT OR REPLACE` against migrated tables should be reviewed at the next opportunity. Not urgent unless a user-visible regression surfaces; the pattern is now known and documented for future migration safety.

---

## Candidates (filed, not anchored)

Doctrine candidates surface during ship work but anchor only after a second project instance shows the pattern (per §34 "no pre-sequencing" + §38 "filed-not-sequenced"). The candidates listed here have **one project instance**; they earn an anchored §-number when a second ship demonstrates the same shape.

### C1. Engine-computed binding > validator-on-LLM-output

**Filed:** Session 34 (Ship 1 Resolution Binding) per `RESOLUTION_BINDING_REVIEW.md` §3.1.
**Phrasing:** When an LLM-output failure mode can be closed by engine-computing the bound outcome and rendering it as a top-of-prompt constraint (rather than validating the LLM's output after the fact), the engine-computed path is structurally stronger. Validators close drift via retry pressure; engine binding closes drift via making the drift surface inaccessible. Both have a role — binding is the first reach; validation is the safety net.
**Project instances so far:**
1. **Track 7 #1 CHECK_ACTION binding (S25 #4)** — adjudicator computes pass/fail from buffered roll vs DC; renders `narration_constraint` at top-of-prompt; LLM cannot drift on the outcome on the adjudicator surface.
2. **Ship 1 Resolution Binding on DM-typed surface (S34)** — same architectural shape applied to the DM-typed-directive surface that bypasses adjudicator. Engine computes `passed = (roll_total >= dc)` from `dnd_pending_roll_directives.dc` + Avrae embed `result`; AUTHORITATIVE-CANON block renders top-of-prompt; `ROLL_OUTCOME_DRIFT` verifier is the safety net for any residual drift.
3. **Ship A Resolution Binding on LLM-emitted surface (S36)** — third instance. Same primitives extended with `ResolutionTexture` sub-dataclass for difficulty/margin/stakes/crit-tier scaling. New writer hook at narration-emission time (in `_dm_respond_and_post` post-channel-send) closes the load-bearing 90% play loop. Engine-bound DC; LLM picks DC inline per HARD STOP RULE 1 + DC GUIDANCE band table; engine computes pass/fail and texture; AUTHORITATIVE-CANON block at top-of-prompt of the auto-fire turn renders the bound outcome plus difficulty/margin/stakes guidance and crit constraint clauses.
**Anchor when:** Per locked decision 11 (v3 §12), wait for Ship A verify to confirm the shape holds. **S36 verify clean — three instances now have live empirical proof.** Anchoring deferred to a future doc-update pass; promotion to numbered §-entry could land in S37+ when operator and planner agree it's time. Fourth instance candidates: cast resolution binding (v1.x), Ship 4's `IDENTITY_DRIFT` verifier class operating against `SceneComposition`.
**Sibling principles:** `MULTIPLAYER_FIXES.md` §2.3 (structural removal of write authority beats validation); §1a (LLM never decides mechanical outcomes — the controlling invariant); §17 (single write paths per field).

### C2. Reused vocabulary across sibling verifier classes

**Filed:** Session 34 (Ship 1 Resolution Binding) per `RESOLUTION_BINDING_REVIEW.md` §3.2.
**Phrasing:** When two violation classes in `narration_verifier` detect the same linguistic surface (LLM uses success/failure phrasing, contradiction phrasing, etc.) but against different binding objects (adjudicator vs. resolver vs. future binding surfaces), reuse the vocabulary tables rather than fork them. The class differentiation is which binding object is populated at call time; the detection phrases are identical regardless of which surface produced the binding. Single-tuning surface keeps false-positive rate calibrated in one place.
**Project instances so far:**
1. **Ship 1 ROLL_OUTCOME_DRIFT (S34)** — reuses `VERDICT_CONTRADICTION`'s `_CHECK_FAILURE_SUCCESS_PHRASES` / `_CHECK_SUCCESS_FAILURE_PHRASES` tables. The two classes differ only in which result object they compare against (`arbitration_result.verdicts` for CHECK vs `resolution_result.passed` for ROLL_OUTCOME_DRIFT); the phrases that signal success-on-failure and failure-on-success are the same.
**Anchor when:** a second sibling class reuses the same vocabulary tables. Likely candidate is cast-resolution-drift (v1.x cast resolution binding) or multi-actor-resolution-drift (Ship 4.5 if it slots).
**Sibling principles:** §63 (fork at the highest layer where invariants diverge — this candidate operates one layer below: "when do siblings share implementation surface?"); §17 (single write paths per field — the same logic at the vocabulary-tuning surface).

### C3. Single-writer compatible with multiple disjoint trigger surfaces

**Filed:** Session 36 (Ship A LLM-Emitted-Directive Resolution Binding) per `LLM_EMIT_RESOLUTION_BINDING_SPEC.md` §3 and review §5.3.
**Phrasing:** When a §17 single-writer field gains a second trigger surface (different user action invoking the same write semantic), consolidate via one writer-helper rather than fork the field's write path. The helper is the single writer; the triggers are surfaces invoking it. Two disjoint-trigger surfaces calling one writer-helper is structurally compatible with §17 — the field's invariants are preserved at the helper layer, and the surface diversity adds expressive power without compromising write-side discipline.
**Project instances so far:**
1. **Ship A `dnd_pending_roll_directives.dc` column (S36)** — written by both `_handle_dm_roll_directive` (human DM trigger via `on_message` `!`-prefix intercept) and the new `_dm_respond_and_post` post-channel-send hook (LLM-emit trigger), both calling `pending_directive_upsert` as the single writer-helper. The triggers are disjoint by author identity (human-typed vs bot-narration-emitted); they don't race; both surfaces upsert through the helper which enforces the column's invariants. Operator's manual `!check` echo after the LLM's emit is handled by the `directive_preserve_existing_dc` carve-out in the human-trigger branch — when dc=N exists and dc=None would be written for the same actor+skill, the upsert is skipped, preserving Ship A's row.
**Anchor when:** a second instance surfaces. Likely candidates: F-55 #5.4 (Intent-to-Avrae Resolver) may consolidate writes from multiple trigger surfaces through a single helper; Ship 2 (Scene State Canon Discipline) may consolidate scene_state writes through a single canonical writer that multiple surfaces call.
**Sibling principles:** §17 (single write paths per field — this candidate is a refinement: "single writer at the helper layer, multiple disjoint trigger surfaces is compatible with §17"). Review framing question per `LLM_EMIT_RESOLUTION_BINDING_REVIEW.md` §5.3: when this anchors, decide whether it lands as a new §-entry or as a §17 amendment clause.

---

*Order: §1-§75 are append-only. New doctrines get appended; existing numbers are stable for cross-reference from SESSIONS.md. Candidates promote to numbered §-entries when their second project instance ships.*
