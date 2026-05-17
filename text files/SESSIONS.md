# VIRGIL SESSION LOG

Append-only chronological ledger. Architectural lessons live in `DOCTRINE.md`; failure modes live in `FAILURES.md`; current state in `VIRGIL_MASTER.md`; next moves in `ROADMAP.md`; reasoning behind decisions in `WHY.md`.

**Trim policy applied S70 (May 14, 2026):** Entries trimmed per editorial judgment — load-bearing detail kept where future planners need it; everything else compressed. No hard rule on length per session; the test is whether content compounds across future ships or whether the doctrine/failure cross-ref already carries the load.

---

## Pre-S52 — chronicle

**S5 — Avrae Pivot.** Retired Telegram D&D bot; rebuilt around Avrae as rules engine. Mechanical resolution moved to Avrae; narration to Virgil. The architectural pivot that made everything downstream possible.

**S6 — Orchestration Layer.** `dnd_orchestration.py` built as structured gameplay layer between player input and DM prompt. Roll discipline became a rules engine. Doctrine §1 (prompt-is-tone-structure-is-game) anchored.

**S7 — Phase 1.4 Complete.** Combat-mode FSM, mode-aware tonal directives, tension thermometer (`tension_int`), manual progress clocks, mode-aware intent classifier. Combat starts/ends without human intervention.

**S8 — Phase 2 Complete.** Eleven steps: combat stabilization, observability, multi-actor narrative fidelity, `/encounter` slash command. Cloud router quota corrections.

**S9 — Phase 3 Ships, Narration Drift Surfaces.** Phase 3.0 Suggested Actions live; Phase 3.1 Auto-Execute Tier 1 shipped but never fired due to Layer 2 narration drift. F-07 (hallucinated slash commands) + F-08 (Layer 2 drift) filed.

**S10 — Phase 1 Closes, Model Swap, Phase 3 Validates Live.** gpt-oss-120b model swap closed Layer 2 drift. Phase 3 auto-execute fired live for the first time ("Mode set: combat" + "Quest added: Retrieve the Crystal"). Orchestration regex audit hardened RX vocabularies.

**S11 — Phase 11.1 Mechanical Hints.** Advisory parser module (`mechanical_hints.py`). Strict regex whitelist for `!game coin / longrest / shortrest`. Cloud router gained `extraction` task type. Third instance of the advisory-parser pattern.

**S12 — Phase 12 Persistence Layer + `/travel` + Doc Restructure.** Persistent NPCs + locations (`dnd_npcs`, `dnd_locations`). Authored canon via `skeleton.md`. `/travel` Ship 1 with TRAVEL_TRANSITION directive. World recall via NPC autocomplete. Documentation split into VIRGIL_MASTER + ROADMAP + WORKING_WITH_CLAUDE + WHY.

**S13 — Ship 4 Telemetry + Campaign Management Surface.** Phantom-location telemetry + `world_health` report. Campaign cascade with two-gate destruction. CapabilityVerdict enum (CONFIRMED / VALID_BUT_UNCONFIGURED / INVALID). Doctrine §18-§23 anchored across the session.

**S14 — Track 3 Opens + Corpus Inventory.** Six ships converting declarative state into operational behavioral pressure (pacing directive, central thread, DM philosophy loader). Final web-app session before Claude Code migration. Doctrine §25 (directives-as-imperatives) anchored.

**S15 — Claude Code Migration + PC Contamination Guard + Backup-to-PC.** First Claude Code session. PC contamination guard at parser + engine layers. Backup-to-PC over Tailscale (Cygwin + SSH key bootstrap).

**S16 — Consequence Surfacing v1 + THE_GOAL.md.** `dnd_consequences` schema + dual-pass parser (player + DM channel separation). Single write paths for lifecycle. THE_GOAL.md arrived and was protected. Doctrine §32-§38 anchored (spec → review → revise → ship cadence; build-to-bar operating model).

**S18 — Observability Batch (S22-S25).** Four pure-visibility log lines: `unconsumed_roll_swept`, `npc_near_match`, `prompt_size:`, `directive_emit:`. B2 `!attack` template directive. Doctrine §39-§46 anchored across pure-observability-first discipline.

**S21 — Combat Persistence Directive v1.** `dnd_combatant_state` + `parse_init_list_embed` + `compute_persistence_directive`. Concrete combatant block in prompt during combat. Snapshot-over-delta pattern formalized.

**S22 #1 — Narrative Inventory v1.** `dnd_inventory` + `/inventory` + `/giveitem`. Silver-key cellar narrative verified live. Bot-Avrae write boundary (§65) anchored: Virgil owns narrative inventory; Avrae owns sheet-bound gear; no sync layer.

**S22 #2 — Loot Generation v1.** Death-edge detection inside `update_combatants_from_init_list`. `loot_tables.py` + `dnd_loot_pending`. AUTHORITATIVE/EXHAUSTIVE framing after pass-1 hallucination; chroma purge after pass-2 contamination. Three failure modes in two test passes; spec review couldn't have predicted any.

**S23 #1-#3 — Track 6 #1/#2/#3 + Discord Channel Cleanup.** `render_state_footer` pure function (mode/turn/round in Discord footer). `compute_combat_redirect_directive` for on-turn combat-bypass. `compute_setup_plan` extends pure-function pattern to infrastructure ops. Channels consolidated to 4-text + 1-voice. Idempotency contract proven.

**S25 — /setup housekeeping + OOC Advisory Lane v1.** Avrae perms + #commands + AFK voice. Advisory routing branch + `_advisory_respond` handler + `build_advisory_context`. Doctrine §63-§65 (fork at highest layer where invariants diverge; bot-Avrae write boundary).

**S25 #2 — Advisory Command Reference + Auto-Generated Virgil Section.** `COMMANDS.md` loaded fresh into advisory mode (no caching — edits take effect with no restart). Auto-generation from `bot.tree` decorators on every startup. Doctrine §66 (doc auto-generation as drift defense).

**S25 #3 — Multiplayer Test (Friend Joins, System Stress-Tested).** First multiplayer live test ("Tazz" joined). Eight failures catalogued (F-45 through F-52). Architectural implication: LLM is in decision path for things that should be deterministic Python. Reframe: directives are advisory not binding. Track 7 (Adjudication Layer) opens.

**S25 #4 — Track 7 #1 Adjudication Layer v1.** `adjudicator.py` module. Five action categories (FREE / CHECK / CAPABILITY / COMBAT / WORLD_BOUNDARY). 4/7 categories binding live; 3/7 deferred via cache miss.

**S25 #5 — Cache Auto-Populate.** Capability adjudication goes 7/7 via `!sheet` post auto-cache. F-53 filed + mitigated.

**S25 #6 — Bug 3: /travel location persistence + NPC list location-scoping.** `set_current_location` now fires unconditionally with `location_upsert` for unknown destinations. `get_recently_active_npcs(location_id=)` strict filter. F-44 chroma bleed filed.

**S26 — Track 6 #5.1 Combat Entry Assist.** `srd_resolver.py` + 334-monster SRD index + exact / Jaccard fuzzy / LLM-gated resolution. **§1b first project instance ANCHORED** (validated-suggester pattern: bot proposes, deterministic index validates, DM approves via Discord paste, Avrae executes).

**S27 — Track 4 #3 Time Progression v1.** `advance_time` single write path + `parse_elapsed` deterministic parser + `compute_time_directive` (7th §59 sibling) + `dnd_time_advancements` audit table + `/advance` slash. Six-phase enum (Morning/Midday/Afternoon/Evening/Night/Late Night) locked. Skeleton seed via narrow §17 exception. F-54 surface 1 closure.

**S28 — Bug 4 (`.typing()` soft-fail) + Track 4 #3 verify.** Three Shape A wrappers (typing context try/except). Doctrine §74 (aesthetic transport endpoints soft-fail). Track 4 #3 + Bug 4 jointly promoted.

**S29 — `/play` state-aware footer + Bug 5 (INSERT OR REPLACE clobber).** `/play` footer mirrors `_dm_respond_and_post`. Bug 5: `init_scene_state` used `INSERT OR REPLACE` with original column list; every ALTER TABLE-added column silently regressed to defaults on every `/play`. Fixed structurally via `ON CONFLICT(pk) DO UPDATE SET`. Doctrine §75 candidate (INSERT OR REPLACE is structurally hostile to ALTER TABLE-added columns).

**S31 — First-session orientation pin in #commands.** `COMMANDS_PIN_BODY` constant + `compute_setup_plan` extension. `/dmhelp` rewrite using runtime-fresh `_load_commands_reference`. Idempotency contract preserved.

**S32 — Bug 1 Phase 1: Pending Roll Directive Tracking, Telemetry-Only.** DM `!check`/`!save`/`!cast` directive parser + footer-binding matcher + `dnd_pending_roll_directives` table + `last_active_actor` column on `dnd_scene_state`. Four-trigger `footer_actor_changed:` observability. `dm_respond` NEVER auto-fired in Phase 1. Multiplayer playtest in same session surfaced Findings A/H/L (recursive hallucination loop / hydrate-Avrae sync gap / roll resolution unbound from rolled value) — drove S33 plan.

**S33 — Multiplayer Fixes Plan: 5-Ship Plan + Three-Reviewer Cycle.** No code. `MULTIPLAYER_FIXES.md` v2 drafted (584 lines, 14 review-cycle revisions). Three planner-discipline lessons named: "what's the minimum version that captures the principle" beats "reject the prescription"; surface axis disagreements when reviewers diverge; anticipated-friction dismissal must check playtest evidence first.

**S34 — Ship 1 Resolution Binding (DM-typed surface).** Engine-bound DC-vs-roll. Closes Finding L + F-45 + Bug 1 Phase 2. 40 new test assertions. Live verify A/B/D clean; E/F deferred via `MULTIPLAYER_VERIFY_DEFERRED.md`. Two doctrine candidates filed (engine-bound binding > validator; reused vocabulary across sibling verifier classes).

**S34 #2 — Multiplayer Fixes Plan V3: Primary-Surface Re-Diagnosis.** Ship 1 closed secondary DM-typed surface; primary LLM-emitted surface still open. Ship A (LLM-Emitted-Directive Resolution Binding) inserted as new primary. Avrae A.2 recon clean — form (a) (Avrae silently ignores trailing integer in `!check skill N`). v3 canonical; v2 archived.

**S35 — Ship A Spec + Review.** `LLM_EMIT_RESOLUTION_BINDING_SPEC.md` drafted (18 decisions: 12 pre-locked + 6 surfaced). 6 framing revisions. Spec LOCKED v1.

**S36 — Ship A Implementation + 9 Live-Verify Patches.** SHIPPED LIVE. ~120 test assertions. Nat-20 PASSED case rendered memorable-success texture; zero cascading rolls; Avrae compat confirmed for `**!check skill : Name**` bold-wrapped format. Patches covered classifier coverage expansion (~25 new verbs), DC strip for player view, dc-preservation against manual echo clobber, sentinel detection routing `[Roll resolution:` prefix to META (closes cascading-roll loop).

**S37 — Hybrid Combat Exploration: GPT + Gemini External Review → v3 Two-Horizon Reframe.** No code. Three iterations of `HYBRID_COMBAT_NOTES.md`. Gemini's binary-toggle pushback + broader directive (playtest-first, freeze feature list, ship dumb combat). Long-term reference design preserved; near-term execution disciplined per "evolve from observed friction."

**S37b / S38 — Ship 2 Spec Draft + Review (Scene State Canon Discipline).** 649-line spec. Four §11 decisions: Path A drop freetext column (D1), ship all 5 deletions (D2), defer adjacent tables (D3), bundle dead-column housekeeping (D4). §76 candidate phrasing drafted with 3 project instances (S22 #2 chroma / S32 location drift / S36 time-of-day).

---

# Session 39 — Ship 2 Implementation + §76 Anchored (May 11, 2026)

Ship 2 SHIPPED LIVE. Scene state canon discipline closed: five §76 deletion targets dropped from `dnd_scene_state` (`location` LLM-write freetext, `established_details`, `focus`, `open_questions`, `last_scene_change`) + three dead-column housekeeping drops (`active_npcs`, `active_threats`, legacy `tension`). Live DB migrated cleanly via idempotent ALTER TABLE DROP COLUMN (SQLite 3.45.1).

Path A: reads migrate to `location_label` derived from `dnd_locations.canonical_name` via `current_location_id`. `init_scene_state` signature dropped seed parameter; `extract_scene_updates` no longer makes LLM call (writes only `last_player_action`); `update_scene_state` shrank SCALAR_FIELDS to `{last_player_action}` + new `DELETED_FIELDS` guard logs LLM-write attempts as drops.

105 new test assertions across 2 new files. Closes Finding A.

**Doctrine §76 anchored** (Recursive hallucination memory loop / four-property latent-canon test) — three project instances S22 #2 / S32 / S36.

---

**S40 / S40b — Ship 3 Spec + Review (NPC State-Sync).** Spec drafted per `MULTIPLAYER_FIXES.md` v3 §6 — Finding H closure via fix candidate (a) auto-create Avrae sheet on `/hydrate` via bot-emitted `!init opt` under proposed §65a narrow exception. §76 audit on dnd_npcs clean (zero 4/4 hits — every LLM-influenced write goes through §17 single-writer helper). Review applied 4 spec revisions including Sub-D2 Case A/B split.

---

# Session 41 — Ship 3 Implementation: Avrae Bot-Filter HALT-and-Pivot to §1b Suggester (May 11, 2026)

Ship 3 SHIPPED LIVE post-architectural-pivot. Closes Finding H via §1b validated-suggester pattern. The originally-locked fix candidate (a) — bot-emit `!init opt` under §65a narrow exception — was empirically blocked by Avrae's API and pivoted in-session to candidate (a') per operator decision.

**Load-bearing narrative: HALT-and-pivot pattern.** Session opened with the spec body locked at fix candidate (a), executed implementation per spec, ran structured Avrae verify-pass, surfaced a structural API boundary that invalidated the locked architectural shape. Implementation, tests, and spec body all rotated to the new shape inside the same session.

**Three Avrae verify findings:**

1. **Avrae bot-filter (load-bearing HALT).** Identical `!init opt` commands mutate Avrae state when human-typed; silently filtered when bot-typed. Structural Avrae API behavior — cannot be engineered around without TOS-violating self-botting.
2. **`-h` is hidden-toggle, NOT HP.** Correct flag for both `!init add` and `!init opt` is `-hp`.
3. **`!init opt` cannot set max-HP.** Clean fix: `!init remove` + `!init add <init> <name> -hp <hp>` + `!init opt <name> -ac <ac>` — three lines, each pasted separately.

Helper `_avrae_project_npc(channel, campaign_id, npc_name, trigger)` posts the 3-line sequence to `#dm-aside` (not `#dm-narration` — Avrae doesn't read aside; §65 holds). Case A active `/hydrate` with numeric HP → warning aside + 3-line clean fix. Case B passive init_list → silent no-op (preserves Avrae's mid-combat authority).

**§1b second project instance ANCHORED** (Ship 3 joins Track 6 #5.1 SRD suggester). §12.5 composition observation lands (§17 gated-write discipline preempts §76 four-property surfaces). §65a NOT anchored (suggester dissolves the need). C3 NOT anchored (claim withdrawn — suggester isn't a single bot-side writer).

13 new test assertions; Scenario A live-verify GREEN (`<13/13 HP> (AC 13)`).

---

**S42 — Listener edge-case verification + multi-attack/dice-modifier patches.** Two structural parsing gaps patched in `avrae_listener.py`: (1) advantage/disadvantage rolls (`2d20kh1`/`2d20kl1`) silently returned None — `_DICE_NOTATION` constant allows modifier suffixes; (2) multi-target attacks captured only first sub-attack — new `_extract_attack_from_field` helper. Per-parse `listener_parsed:` telemetry. Crit-force / save-with-damage / death-save filed as deferred per fixture-availability. Listener verification trustworthy for post-Ship-3 playtest.

---

# Session 43 — Dumb Combat Narration + Atmospheric-vs-Adjudication Doctrine (May 11, 2026)

Auto-narration on three combat-mode state transitions (ROUND_START + BLOODIED_THRESHOLD_CROSSED + COMBATANT_DOWNED) via `_dm_respond_and_post`'s `transition_context` carrying categorical HP roster + verbatim MUST/MUST-NOT invariants. DEATH_SAVE_EVENT_START deferred per S42 fixture blocker.

**Load-bearing narrative:** atmospheric continuity, not adjudication — the cliff-edge is mechanical-state-mutation inference. Live verify A-F: doctrine HOLDS at cliff-edge (no mechanical drift in any narration); BLOODIED/DOWNED clean; ROUND_START has quality drift (phantom NPCs from `recent_npcs` block + stale-narrative bleed from `last_dm_response`) filed as v1.x prompt-purity candidate.

**Atmospheric-vs-adjudication doctrine (§77) ANCHORED** post-verify-clean. 4 new pure functions in `dnd_orchestration.py` (10th §59 sibling) + 39 new test assertions + 238-assertion regression sweep clean.

---

# Session 44 — Combat Narration Prompt Purity v1.x (May 11, 2026)

S43 filed-follow-up. Closes ROUND_START phantom-NPC + stale-narrative bleed via information-side suppression of 10 prompt blocks during combat narration. Single `suppress_for_combat_narration: bool` param threaded through `_dispatch_combat_narration` → `_dm_respond_and_post` → `dm_respond` → `build_dm_context`.

Three verify passes (2→9→10 blocks). Each pass identified residual leak via DB inspection or full block audit, never speculation. Final 10-block set:

1. `=== RELEVANT PAST EVENTS ===` (chroma retrieval)
2. `=== DM PACING EXAMPLES ===` (chroma knowledge-corpus retrieval)
3. `=== TRAVELING COMPANIONS ===` (primary phantom-NPC source)
4. `Recently active NPCs:` line (secondary phantom-NPC source)
5. `=== ACTIVE QUESTS ===`
6. `=== <NAME>'S NOTABLE ITEMS ===`
7. `=== CENTRAL THREAD ===`
8. `=== PENDING CONSEQUENCES ===`
9. `=== UNRESOLVED COMMITMENT ===`
10. `=== CURRENT SCENE ===` — pass-3 finding: `campaigns.current_scene` is a rolling buffer written by every `_dm_respond_and_post`. Combat narration was reading its own prior output back as "current scene" on each round-start.

17 new test assertions all green; pre-S44 behavior preserved for non-combat callers.

**Two-layer enforcement doctrine candidate filed:** §77 atmospheric continuity is enforced at instruction-side (S43 MUST/MUST-NOT clauses) + information-side (S44 context-block suppression); the layers compose.

Final live verify clean: "The clash begins in a hush, lantern light wavering over the cramped bar as the two figures lock eyes... No blows have yet landed; the moment hangs, waiting for the first move."

**Load-bearing methodological lesson:** even with strong instruction-side enforcement, the LLM uses available context when its task has weak anchoring. ROUND_START has no specific event-anchor; the LLM falls back to whatever's in the prompt's information layer. Removing that information layer is what closes the loop.

---

# Session 45 — Combat-Boundary Hardening Bundle (May 11, 2026)

Three-surface bundle closing the combat→exploration boundary in one ship. Three patches, three live-verified surfaces, all green. The two-layer enforcement doctrine candidate originally filed S44 gets its third structural instance and is anchored as **§78 mode-transition state-reset surfaces.**

**Surface C — Post-!init end narrative-buffer reset.** New helper `reset_narrative_buffers_on_combat_exit(campaign_id)` writes all three rolling narrative buffers (`dnd_campaigns.current_scene` + `dnd_scene_state.last_dm_response` + `dnd_scene_state.last_player_action`) to neutral atmospheric framing at `!init end`. The S44 pass-3 finding (rolling buffer was the dominant bleed source) closed by this reset.

**Surface D — Init-setup silence gate (v1 conservative + v2 top-level).** Surfaced during S45's own live verify when operator typed `2` to disambiguate Avrae's "Multiple Matches Found" prompt — single-char fell through `!`-prefix filter, hit batcher, fired `_dm_respond_and_post` with full unsuppressed context (mode='combat' but no active_turn). LLM generated phantom-companion combat narration BEFORE round 1 started.

v1 fix: `_dm_respond_and_post` gate forces `suppress_for_combat_narration=True` when mode='combat' AND no active_turn. v2 fix (after v1 still allowed premature combat narrative from bare disambig replies): `on_message` extension — ⏳ react and return BEFORE batcher accepts message. v1 retained as defense-in-depth.

**Surface F — COMBAT_END auto-closeout (4th combat-narration trigger).** Operator's "not plausible" critique: in real play, no one types structured RP between `!init end` and bot response. Surface F auto-fires closeout on `!init end` — same dispatch surface as ROUND_START / BLOODIED / DOWNED. `_dispatch_combat_narration` extended with `combat_state_override` and `scene_override` params, decoupling dispatch from current DB state.

Ordering: snapshot → mechanical cleanup → S45 buffer reset (synth fallback) → COMBAT_END dispatch (LLM closeout overwrites synth in current_scene → richer atmospheric context for next exploration turn).

**§78 anchored post-verify-clean.** Third project instance of two-layer enforcement pattern (S43 + S44 + S45). §78 governs structural integrity of the boundary itself, distinct from §77 (which governs content appropriateness):

1. **Mechanical state cleanup** is necessary but not sufficient.
2. **Narrative buffer reset** at the boundary closes the rolling-buffer leak.
3. **Transitional-window structural silence** — when mode flipped but mechanical state incomplete, narration is structurally premature regardless of message content.
4. **Boundary atmospheric closeout** — boundary itself dispatches with both-layer enforcement.

33 new + 78 regression = 111 assertions green. Three live-verify passes — pass 2 exposed surface D's residual after v1 conservative fix; in-session upgrade to v2 top-level gate; pass 3 all surfaces clean. Combat-boundary structurally sealed.

---

**S46 — Pre-playtest hygiene.** `PLAYTEST_OBSERVATION_FRAMEWORK.md` v2 revisions (§5 telemetry corrections, §2.3+§2.4 merge into Clarification rate, pure-operational rate metric, §3.1 emergent-canon pinning, Mode A/B → Tier 0/1-3 alignment). New `VIOLATION_VERIFIER_ERROR` sentinel — closes silent-failure mode where verifier crashes mid-session looked like cleanest session ever to a violation_class=none grep. VM:295 reconciled to "5 classified + 1 sentinel" framing. DIR.md planner-scratch convention added. **Discovered failure mode:** sync-direction race — `push-docs` overwrote a Code edit because PC was stale. WORKING_WITH_CLAUDE.md updated with inverse-failure-mode bullet.

---

# Session 47 — NPC Token-Prefix Collapse: Doctrine Amendment + Write-Path Refinement (May 12-13, 2026)

First doctrine amendment under this planner: write-path semantic refinement to `npc_upsert` that closes a steady-state rot loop in NPC canonical-name resolution. Three-session Path A cadence executed cleanly. External reviewer pass (ChatGPT + Gemini) anchored architectural shape with full convergence on 7 of 8 contested points.

**Doctrine §14.1 amendment.** §14 ("Strict literal match beats fuzzy") amended via new §14.1 sub-section:

> Strict literal matching remains the default identity rule. Exception: deterministic whole-token prefix collapse is permitted only when the incoming canonical_name matches a unique `skeleton_origin=1` row's leading whole-token within the same `campaign_id`. If multiple `skeleton_origin=1` rows in the same campaign share the leading whole-token, no collapse occurs; insert proceeds normally and ambiguity telemetry is logged.

Four named constraints lock the rule's surface area: **unique anchor / skeleton_origin=1 / same campaign_id / whole-token.** First amendment-to-existing-lock the project has shipped. Anchored via §N.M sub-numbering (new precedent in DOCTRINE.md).

**Write-path refinement.** Failure mode: strict-equality canonical_name lookup misses LLM-emitted short forms ("Eldrin" misses "Eldrin Stormbow"); INSERT branch creates bare-firstname row; per-turn mention_count increments accumulate on wrong row; steady-state loop produced 9× mention_count concentration on bare-firstname rows over 12 days in campaign 17.

Fix: ~40 LOC early-exit branch before strict-equality lookup. Queries `skeleton_origin=1` rows for same campaign, filters via `_is_token_prefix`. On unique-anchor: routes to skeleton-lock UPDATE semantic; emits `npc_token_prefix_collapse:` log. On multi-anchor: refuses collapse, emits `npc_anchor_ambiguous:`, falls through to INSERT.

**Operational migration (campaign 17).** Three skeleton-fragmentation rows (Eldrin mc=40, Lira mc=43, Borin mc=37) migrated into canonical anchors via sum-into-canonical. Anchor rows carry summed mention_count (44/51/42).

**Convergent external-review pattern, codified.** ChatGPT + Gemini converged 7 of 8 contested points. Single divergence (resolver hardening option 3): planner reconciled toward Gemini.

41 new test assertions; regression intact. **Live verify closed in campaign 17:** collapse log fired twice on "Eldrin" short-form emission, anchor mc bumped 44→46, zero bare-firstname rows regrew, resolver renders canonical names. Loop closed end-to-end.

---

**S48 — RollBuffer drain on `!init end`.** New `RollBuffer.size()` + drain call + `init_end_rollbuffer_drained:` telemetry in `_handle_init_event` evt_type='end'. Pre-fix: `buffer.consume: 1 events` surfacing immediately after `init: combat ended` (stale rolls polluting AVRAE EVENTS block in post-combat narration). Post-fix: drain at boundary, consume returns 0. Second instance of §78 four-layer rule applied at state-reset surface — DB substrate (S45) plus in-memory substrate (S48). Application not amendment.

---

# Session 49 — Rest-Event RollBuffer Drain (mode-agnostic, §78.5 anchored) (May 13, 2026)

Parallel surface to S48 at rest-event boundary. Pre-dispatch quick-check recon corrected an S48 framing error: the combat-mode branch of `_handle_rest_event` had fired once on Apr 30, contrary to S48's "never-fired" claim. The Apr 30 firing produced no visible drift — actor extraction fell to `'someone'` fallback, keeping rest events out of consume filters. Serendipitous, not structural protection.

**Mode-agnostic placement** (outside the `if current_mode == 'combat'` branch), AFTER `advance_time`. Telemetry includes `rest_kind` field. Mode-agnostic is the load-bearing design choice — rest events pollute RollBuffer regardless of mode, and serendipitous extraction-fallback protection is unreliable if Avrae's embed format changes.

**Test-development self-correction.** Initial mode-agnostic placement assertion used naive indent comparison (drain at depth 12, combat-branch body also at depth 12 — false equality, would have falsely-passed on the load-bearing design test). Switched to structural anchor. Caught pre-ship.

**§78.5 substrate-agnostic and boundary-agnostic application ANCHORED.** Three instances back the anchoring: S45 (DB substrate, init-end boundary) + S48 (in-memory substrate, init-end boundary) + S49 (in-memory substrate, rest-event boundary).

Combat-mode-branch §78 layer-2/4 gaps remain in code — deferred per observed-friction discipline.

**Live verify closed in campaign 17:** Long rest + short rest both fired drain with correct `rest_kind`. First journal evidence of structural protection over serendipity.

---

# Session 50 — COMBAT_END 0-Action Framing Fix (§78.6 anchored) (May 13, 2026)

Last symptom-fix from S46's filing. First doctrine-anchoring this planner instance has shipped.

**Symptom:** 0-action combat (init begin + init end with no rolls between) produced COMBAT_END narration that fabricated atmospheric events that did not occur: *"The clash of steel and shouted commands fade into a heavy silence, the dust settling on the cobblestones..."* — no clash, no shouts, no dust, no motion ever occurred. Within §77 (no adjudication crossed) but framing presupposed narratable events that didn't exist. Directive design issue, not LLM compliance.

**§78.6 anchored — layer-4 render is conditional on content-to-render.** §78 layer-4 (boundary atmospheric closeout) has two operational modes:
- **LLM render** — fires when narratable content exists during the bounded session.
- **Deterministic boundary marker** — fires when no narratable content existed. Engine emits fixed neutral text; LLM bypassed entirely.

**One-instance anchoring with named reasoning.** Standard discipline is two-instance threshold. §78.6 anchored at one instance because the distinction is structurally derived, not emergent — the moment you ask "when should layer-4 dispatch LLM render vs deterministic marker," the framework forces the distinction.

**Fix-shape F (hybrid).** In-memory beat counter (`_combat_beat_counter: dict[int, int]`) keyed by guild_id. Increments on BLOODIED + DOWNED only (HP-state transitions = actual combat content). ROUND_START + COMBAT_END do NOT increment. Reset on `!init begin`; cleared on `!init end` after dispatch. beats=0 → `"Combat ends. The moment passes."`; beats≥1 → existing LLM render unchanged.

**Cleanup-tail queue drained.** S46 filed five small follow-ups. Four shipped across S47-S50; DEATH_SAVE_EVENT_START fixture-gated. Next phase opens to playtest.

**Methodological note.** S48's test used hardcoded 4000-char source-text window; §78.6's branch additions pushed past it. Switched to dynamic end-of-function boundary (`\nasync def ` anchor). Pattern: prefer structural anchors over absolute character counts.

14 new + 38 regression = 52 assertions green. **Live verify closed in campaign 17.** §78.6 active in production.

---

# Session 51 — Every-Turn Time Signal in SCENE STATE Block (§76 read-side analogue) (May 13, 2026)

S50's verify walk surfaced body/footer divergence: footer rendered Day 10 Midday correctly (reads DB) but narration body defaulted to "morning light" because LLM had no current-time signal between time-advance moments. Sixth consecutive small ship in pre-playtest cleanup arc.

**Mechanism:** `compute_time_directive` fires only on `just_advanced=True` turns. SCENE STATE block carried Location / Tension / Recent NPCs / Last player action but NOT campaign_day or day_phase. LLM got time signal on turn immediately after time advances, then nothing on subsequent turns.

§76's body explicitly named this filing as candidate for future Ship 4/5. S50 verify produced concrete observed friction.

**Fix shape A.** Two lines added to `scene_state_section`:
```
Day: {scene_state.get('campaign_day', '?')}
Time of day: {scene_state.get('day_phase', '?')}
```

Between Location and Tension. `compute_time_directive` untouched per separate-responsibility logic: passive every-turn signal (S51) vs active narrate-the-advance beat (compute_time_directive).

**§76 read-side analogue first project instance.** Architecturally parallel to engine-bound binding > validator-on-LLM-output, but read-side. §76 stays at one instance; promotion to §76.1 waits for second read-side instance.

**Methodological note (third instance — anchoring threshold met).** S49 caught naive-indent test. S50 caught hardcoded 4000-char window. S51 caught two text-extraction bugs (wrong-paren find + docstring-boundary truncation) during test writing. Three-instance threshold met for source-text-fragility pattern — candidate filing decision for operator.

**Filed candidate — player-narrative-authority drift.** S51 verify walk surfaced adjacent drift: DM correctly refused player premise turn 2 ("There's no merchant stall here") — correct §77-aligned response. But turn 3 the DM caved and fully materialized merchant interior INSIDE training ground. Possibly §77 sub-section ("scene boundaries are DM-canon; player premise contradicting established scene gets refused-or-transitioned, not retroactively granted"). Recon-first ship if symptom recurs.

10 new test assertions. **Live verify closed in campaign 17** (May 13 multi-turn walk): Day 11 Midday → Evening; turns 1-4 post-advance all carry Evening framing (pre-S51: only turn 1 had signal; turns 2+ drifted to morning defaults).

---

**S52 — Telemetry fold into PLAYTEST_OBSERVATION_FRAMEWORK §5.2.** Planner-only doc-edit ship. Folds five primitives shipped across S48-S50 into framework's state-integrity metrics section: `init_end_rollbuffer_drained:` / `rest_event_rollbuffer_drained:` / `combat_end_zero_action:` / `combat_end_llm_dispatch:` / `combat_beat_incremented:`. Pattern: planner-only doc-edit ships earn their slot when (a) durable, (b) compounds across future ships, (c) gap is operator-defined.

---

# Session 53 — Scene Lifecycle v1.x §1.F.c NPC was_new drop (May 13, 2026)

Live-verify Finding 1 from Scene Lifecycle v1 (S52 spec). 27-turn stale exploration scene surfaced perverse-incentive loop: soft directive fired stale=3, LLM invented NPC "Marla" to fill space, npc_extractor caught was_new=True, §1.F.c fired, counter reset to 0. Counter never reached hard threshold. Directive rewarded elaboration it was trying to suppress.

Patch: dropped §1.F.c reset call from `_extract_and_persist_world`. Spec amendment footnote.

First instance of doctrine candidate **F-64** — *LLM-extracted activity signals as perverse-incentive surfaces in stagnation-detection contexts.*

Ship: 1-line code removal + spec footnote + 1 test assertion flip. ✅ SHIPPED.

---

# Session 63 — Scene Lifecycle v1.x §1.F.e consequence-DM-side drop (May 13, 2026)

Proactive patch per identical-shape rule to S53's §1.F.c drop. Inventory-before-patch found §1.F.e was specced in v1 but never wired in S56 Quest Layer implementation. The bot has been running on §1.F (a)/(b)/(d) only since v1 ship. Harm S53 surfaced for §1.F.c was prevented for §1.F.e by implementation gap.

Doc-only patch: §1.F.e formally dropped from locked list. **F-64 second instance** — wired+dropped (S53) vs specced+never-wired+formally-dropped (S63).

Ship: 0 LOC, spec amendment + FAILURES.md F-64 candidate filing. ✅ SHIPPED.

---

# Sessions 54-57 — Quest Layer v0 + v0.1 (May 13, 2026)

Path A three-session arc + same-session v0.1 UX patch. Mandate piece 2 of 3.

**S54-S56 v0 ✅ SHIPPED.** `dnd_quests` schema extended (6 columns: offer_npc_id FK, offered/accepted/delivered_turn, reward_summary, skeleton_origin) + `dnd_quests_audit` table + status enum clean migration. Five new slash subcommands: `/quest offer`, `/quest accept`, `/quest deliver`, `/quest fail`, `/quest abandon`. §59 sibling pattern at 12th + 13th instances (`compute_quest_offer_suggester`, `compute_active_quest_directive`). 37 tests passing.

**S57 v0.1 ✅ SHIPPED.** Dropped cosine-similarity paste-detection per "too mechanical" UX feedback. Card became pure operational; LLM renders offers organically after `/quest accept`. **§1b third project instance ANCHORED.** Cosine-similarity drop crystallized "no calibration-bound auxiliary" as infrastructural discipline.

---

# Sessions 58-62 — Composition Layer v0 + v0.x (May 13, 2026)

Path A three-session arc + same-session v0.x UX patch. Mandate piece 3 of 3.

**S58-S61 v0 ✅ SHIPPED.** `dnd_quest_acts` table + `current_act_id` column on `dnd_scene_state` + `dnd_quests_audit` extended with `to_act_index`. Two §59 siblings (#14 + #15). 8 slash subcommands at original spec; trimmed in S62 patch. **§1b fourth project instance ANCHORED** via Reading-3-direct (no cosine-similarity from S57 precedent).

R6 critical recon clean: Scene Lifecycle v1's compression machinery does NOT clear `current_act_id`. Composition's foundational anchor-persistence assumption held.

§11.13 + PRAGMA foreign_keys=ON + ON DELETE CASCADE on `dnd_quest_acts.quest_id` shipped in lock amendments.

**S62 v0.x ✅ SHIPPED.** Companion filter (NPCs in `dnd_companions` excluded from quest-voicer candidates — campaign 17 suggester goes silent because Eldrin/Lira/Borin are party not dispatchers, correct behavior). `/quest act add` Discord-side authoring slash. Filed forward: `/seed_create` + `/seed_update` §1b fifth-instance candidate.

F-54 motion-system stack complete: Scene Lifecycle (motion cadence) + Quest Layer (commitment spine) + Composition Layer (where-are-we anchoring) operating together.

---

# Session 64 — First playtest of complete F-54 stack (May 14, 2026)

20-minute playtest on new campaign. Operator confirmed game still not fun at this stage — playtest was bug-discovery cycle, not enjoyment.

Bugs surfaced:
- F-021 `/play` NameError — campaign-opener crashes
- DC-less roll requests fired twice (persuasion + investigation, engine-side adjudication skipped)
- `#dm-aside` role-confusion (Virgil told operator how to ask "your DM" about pronouns)
- NPC pronoun drift across turns
- `/travel duration:"1 hour"` advanced 4 hours (full phase, not 1 hour)

Filed for Tier 1 cleanup arc.

---

# Session 65 — Tier 1 batch 1: Front-door bugs (May 14, 2026)

Path B cleanup arc batch 1 of 3. **Standing practices adopted from this session forward:** pre-ship DB snapshot, per-fix rollback notes, sequential commits with atomic test verify, feature-disable switches.

**3 fixes SHIPPED:**
- F-021 `/play` NameError (2-line patch + 6 smoke tests + AST regression guard)
- DC-less roll closure (severity→DC table + `__post_init__` auto-fill + 25 tests)
- `#dm-aside` role-confusion hard-fork (ADVISORY_SYSTEM_PROMPT — "Virgil-as-engine + asker-as-DM" framing + 13 tests)

**1 fix HALTED:** F-008 AUTO_EXECUTE close. Audit surfaced `test_dnd_npcs` uses `execute_auto_actions` directly (class c consumer); close touches `build_dm_context` PLAYER UI SUGGESTIONS beyond directive emission. §1b third-instance anchor (Quest Layer v0.1) PROVISIONAL pending S65.1.

**S65.A same-session followup ✅ SHIPPED:** format unification across rolls/attacks/bookkeeping/Suggested Actions. Actor bold OUTSIDE box; box contains only Avrae syntax. 23 new tests.

---

# Session 65.1 — F-008 close + cleanup (May 14, 2026)

F-008 AUTO_EXECUTE close authorized per operator (a)-lean: ship test-harness migration + prompt-section surgery + feature flag. MODE/CLOCK_TICK §1b replacements deferred to observed-friction.

Shipped: C-1 F-008 close → §1b third-instance anchor PROVISIONAL → ANCHORED. C-2 test_npc_upsert tuple unpacking fixes (5 test files migrated). N-1 hint extractor tightening (verb-co-occurrence + cross-turn dedup; baker pricing scenario adversarial verify clean).

✅ SHIPPED.

---

# Session 66 — Tier 1 batch 2: World-state-responds (May 14, 2026)

**3 fixes SHIPPED:**
- `/travel` duration→phase_delta translator (floor-at-1-phase + truthful embed; 52 adversarial tests)
- F-031 quest delivery silent fail (PARTY_STASH_BUCKET='__party__' sentinel + truthful aside; 28 tests)
- F-035 loot auto-claim with `/loot drop` refusal (auto-claim at `mark_loot_surfaced`; 26 tests)

824 assertions across 18 files green. Filed N-5: LLM narrative-loot extraction (chest contents / ad-hoc found items).

✅ SHIPPED.

---

# Session 67 — Tier 1 batch 3: Durability + §76 audit (May 14, 2026)

**Fix 1 F-026 durability ✅ SHIPPED.** WAL mode + autocheckpoint at db_init. Nightly systemd timer (virgil-backup.timer @ 03:30 PDT) → virgil_backup.sh (sqlite3 .backup + integrity_check + 30d retention + PC push). Restore drill PASS — restore_drill.md procedure documented.

**Fix 2 F-016 §76 closure ⚠️ PARTIAL.** Phase A audit found 3 NEW 4/4 surfaces (consequences.summary, npcs.description fold, chroma DM-stores) — all mitigated by promotion gates / distance cutoffs. Phase C HALTED per blast-radius budget. Filed for S67.1.

Phase B (original target) shipped: all 3 LLM-narration write sites retired, `=== CURRENT SCENE ===` prompt block deleted, `scene_blurb` reader redirected to `last_dm_response`. 15 adversarial tests pass.

854 assertions across 19 files green. **Tier 1 cleanup arc CLOSED.**

✅ SHIPPED (partial Fix 2).

---

# Sessions N-10 + N-10 v0.1 — Canon Bootstrap Bot (May 14, 2026)

Path A three-session arc + same-session live-verify patch. Authored-canon-volume ship — load-bearing because operator confirmed option-3 authoring (premise-only, will not hand-author skeleton.md).

**N-10 v0 ✅ SHIPPED.** `/bootstrap premise:"..."` flow with per-element `#dm-aside` cards (faction → dispatcher NPC → quest → quest acts → location). Operator approves via `/bootstrap accept | skip | reroll | manual`. Two new §59 siblings (#16 + #17). **§1b sixth project instance ANCHORED** via Reading-2-direct.

§11.8 faction storage at v0: skeleton.md only (Causality Engine S69 introduces table). §11.9 NPC pronouns: prose-fold at v0 (column deferred to S68/N-4 with forward-coupling migration note).

**N-10 v0.1 ✅ SHIPPED.** Field-key normalization per card type (`/bootstrap manual name:"Grahn"` on NPC card now writes `canonical_name='Grahn'` — was silently lost). Prose-residual warning on name-class overrides. Reroll archetype-diversity hint.

Cascade fixed: pre-v0.1 bug chain was "override silently ignored → wrong canonical name → FK resolve fails → quest_offer never called → status stuck at default." Live-verified via Grahn reproduction.

63 new tests; 1006 total green.

---

# Session 68 — N-4 NPC pronoun lock + N-3 HALT (May 14, 2026)

**N-4 NPC pronoun lock ✅ SHIPPED.** `dnd_npcs.pronouns` column added. `npc_pronouns_set` §17 single writer. `extract_pronouns_from_text` regex (6 canonical pronoun sets, first-occurrence wins). `npc_pronouns_backfill_pass` runs at engine init, prioritizes first-sentence parse per N-10 forward-coupling. Live-lock pass in `_lock_npc_pronouns_from_narration` (first narration mention captures pronouns). HARD STOP RULE 7 added (locked-pronoun MUST-tone, names S64 baker drift scenario as the failure case).

Production backfill: scanned=23 locked=0 (no parseable pronoun signal in existing descriptions — bootstrap-NPC prose-fold instruction not enforced strongly enough during N-10 testing; live-lock handles the gap going forward).

**N-3 prior-price-check ⛔ HALTED.** Recon Phase A: no `dnd_scene_log` table indexes by NPC+item. `dnd_consequences.kind` enum doesn't carry `price_commitment`. `messages` is flat chat log without NPC binding. ChromaDB sessions are probabilistic. Hint_extractor logs aren't DB-bound. Clean fix needs schema work (new `dnd_npc_commitments` table + extractor). Filed forward as N-3.1 multi-spec.

41 new tests; 1047 total green.

**F-64 candidate cluster at 5/6 instances closed** (F-008, F-031, F-035, N-1, N-4). N-3.1 outstanding sixth. Formal F-XX anchoring walk pending — recommended host: N-3.1 spec session.

---

# Post-S68: External review + direction lock (May 14, 2026)

PROJECT_LONG_HORIZON_REVIEW.md produced (95 findings, Claude Opus 4.7, 3,374 lines, Section XVII empirical verifications). Operator surfaced playtest bugs in parallel. Three-way external review pass: GPT 1/3 + Oracle 2/3 + Gemini 3/3.

**Convergent review locked direction:** Conversational-Runtime Inversion as next architectural ship.

BIOS/OS/UI metaphor as load-bearing framing. DM-burden co-equal with player-burden. Litmus test: "would a good human DM stop the session to operate software for this?" §1a survives via inverted surface (detection-from-narration = deterministic gate). Slash sprawl problem (~40-47 commands) addressed structurally, not via consolidation cleanup.

S69 Causality Engine spec drafted, reviewed, locked DRAFT → LOCKED with §1.K amendment (8 commands including `/faction delete` w/ FK cascade). Phase 3 implementation paused pending Inversion ship. Will amend in-place per §11.6 lean (a) when Inversion lands.

Conversational-Runtime Inversion v0 sketch landed at `planner-scratch/conversational_runtime_inversion_v0_sketch.md`. 12 §11 candidates. **Doctrinal direction-lock — largest since "controlled canonization of stochastic generation."**

---

# Session 70 — Conversational-Runtime Inversion v0 Phase 1 (May 14, 2026)

Path A Phase 1 spec drafting for Conversational-Runtime Inversion v0. First architectural ship under the post-convergent-review direction-lock. Output: `specs/CONVERSATIONAL_RUNTIME_INVERSION_V0_SPEC.md` DRAFT (42k chars, §1-§14).

**Recon (six items, all clean — no HALT):**

- **R1** N-1 hint extractor pattern generalizes — closed verb set + structured-signal co-occurrence + whole-word tokenization + cross-turn dedup + per-fire telemetry. Architecturally supportable for Inversion's per-domain parsers.
- **R2** 47 slashes / 7 groups inventoried. Tier 1 BIOS ~18 / Tier 2 Authoring ~14 / Tier 3 Pacing ~13. `/quest accept` cascade clean (writes only `dnd_quests.status`); `/travel` cascade broad → deferred to v0.1.
- **R3** Detection insertion points clean. Pre-LLM hook at `discord_dnd_bot.py:2664` (`action = message.content.strip()`); post-LLM hook at `_extract_and_persist_world()` (`discord_dnd_bot.py:2789`).
- **R4** Five `#dm-aside` card precedents catalogued (`:548`, `:684`, `:5917`, `:6440`, `:6512`). Format pattern: header + body + pasteable-action suffix. Inversion suggester cards inherit.
- **R5** Prompt budget impact negligible at v0 fire volumes. Pre-detection parsers don't render to prompt; suggester cards render to operator channel only.
- **R6** §F-59 holds. Inversion's high-confidence detection routes operator-pasteable Avrae commands to `#dm-aside`, not direct bot-emit. S41 NPC State-Sync precedent generalizes.

**Discrepancy flagged for Session 2:** Sketch §11.6 still reads lean (b) (open S69 v0.1 spec at resume) vs operator dispatch §11.6 lean (a) (amend-in-place at Inversion ship time). Code drafted per operator override (a); flagged in §8.4 + §11.6 + §14 for Phase 2 walk confirmation.

**N-3.1 folded into Inversion v0** per §1 decision 4 / §7 (Code lean (a)). `dnd_commitments` schema sketch in §7.3 awaits Phase 2 lock.

**First-migration set proposed:** Transaction-completion + quest-acceptance + loot-drop at v0; travel + compression + mode → v0.1.

**§11 candidates needing Phase 2 deeper synthesis:** §11.2 (§1a doctrinal extension — operator+Oracle), §11.3 (§1b interaction — anchored-instance impact), §11.5 (first-migration set), §11.6 (sketch/dispatch discrepancy resolution).

**Doctrinal weight:** Project's largest direction-lock since "controlled canonization of stochastic generation." BIOS/OS/UI metaphor + litmus test + DM-burden co-equal framing carry as load-bearing reference points.

**Ship:** Spec drafted, no code, no HALTs. ✅ SHIPPED (Phase 1 of 3).

**Next:** Session 2 = Phase 2 review pass, Opus medium per WWC cadence. Walk §11.1-§11.12 in order; §11.2/§11.3/§11.5/§11.6 are the synthesis-heavy stops.

---

# Session 71 — Inversion v0 Phase 2 review pass (May 14, 2026)

Path A Phase 2 against `specs/CONVERSATIONAL_RUNTIME_INVERSION_V0_SPEC.md` DRAFT. Walks all 12 §11 decisions. Output: `specs/CONVERSATIONAL_RUNTIME_INVERSION_V0_REVIEW.md` (31k chars, §1-§8).

**Confidence split:** 8 HIGH · 1 MEDIUM-HIGH · 1 MEDIUM · 1 LOW.

**§11.6 discrepancy resolution:** Sketch lean (b) vs operator dispatch lean (a) reconciled at (a). Walk confirms (a) defensible — surface-layer-only amendment; S69 locked architecture (§3-§7, §10) holds byte-for-byte. Flagged for Oracle review on whether (a) sets locked-spec-amendment-as-precedent.

**Operator + Oracle escalation points:**
- **§11.2** §1a doctrinal extension shape — three candidates (amendment / new doctrine / sub-numbering). Code's weak lean (iii) §1a.x sub-numbering. LOW confidence; operator + Oracle territory.
- **§11.6** locked-spec amendment-in-place — Oracle review on doctrinal precedent shape.
- **§11.4** N-3.1 fold-in vs keep-separate — operator decision on ship-size economics.

**§1b instance lineage clarification:** Spec stated "five existing instances"; Code's review walk surfaced this is likely six per N-10 §1.K. Material at framing only, not at lean. Lineage: Track 6 #5.1 (S26) → NPC State-Sync (S41) → Quest Layer v0.1 → Composition Layer v0 → [possibly Scene Lifecycle or Track-5 v0.1] → N-10 CANON_BOOTSTRAP. Flagged in review §11.3 walk; resolved at lock.

**Recommended defaults summary:** 11.1 closed-vocab / 11.2 §1a.x sub-numbering / 11.3 parallel / 11.4 fold-in / 11.5 txn+quest-accept+loot-drop / 11.6 amend-in-place / 11.7 three-tier / 11.8 per-fire / 11.9 existing-slash+rejection / 11.10 §F-59 holds / 11.11 silent forward-compat / 11.12 gradual.

**R-finding integration check:** All six R-findings cleanly integrated. No contradictions surfaced at walk.

**Ship:** Review doc landed. No code, no HALTs. ✅ SHIPPED (Phase 2 of 3).

**Next:** Session 3 = Phase 3 implementation, Sonnet medium per WWC cadence.

---

# Session 77 — §1b.1 Clarification Handshake Primitive v0 Phase 3 implementation (May 16, 2026)

§1b.1 ANCHORED. Three-phase arc closes (S75 sketch → S76 review → S77 implementation). Single-arc ship: Layer A + Layer B + M-DELAYED in-fiction primary path together. Opus medium per WWC conditional bump (context-flag protocol + LLM-prompting language is synthesis-heavy).

**Scope shipped:**
- `clarification_handshake.py` NEW (~570 lines) — `ClarificationSession`/`ParserResult`/`RouteDecision` dataclasses; `aggregate_parser_outputs` Stage 1 routing; `set/clear/get_pending_clarification` DB single-writer; `build_layer_a_card` / `build_layer_b_question` / `build_layer_b_recursion_card` renderers; `parse_layer_b_reply` closed-vocab parser; `await_layer_b_reply` `bot.wait_for` wrapper; session lifecycle helpers with per-campaign 3-cap.
- `dnd_engine.py` — schema migration adds `pending_clarification TEXT DEFAULT NULL` to `dnd_scene_state` (idempotent ALTER TABLE per S65 standing practice); `build_dm_context` accepts new `pending_clarification_directive` kwarg, renders block between scene_state_section and char_ctx_section (engine-state directive band); `dm_respond` computes directive via `compute_pending_clarification_directive` from pending metadata and threads it through.
- `dnd_orchestration.py` — `compute_pending_clarification_directive` added as 22nd in-file / 24th total §59 sibling. MUST/MUST-NOT framing per HARD STOP convention. Marker-summary renderer (`_summarize_markers`) + always-fire log summary.
- `discord_dnd_bot.py` — pre-LLM hook at `:2727` swaps `_run_quest_acceptance_detection` → `_run_inversion_aggregator` (fans out parsers, normalizes to `ParserResult`, dispatches per Stage 1 route); `_dispatch_clarification_fallback` handles Layer A/B post-routing including listener `bot.wait_for` + recursion; `on_ready` posts restart-preservation notice to `#dm-aside` for campaigns with non-NULL `pending_clarification`. `time` import added (listener timestamp math). `_run_quest_acceptance_detection` retained for fall-through compatibility.
- `inversion_telemetry.py` — 12 new event types: `clarification_{in_fiction_fired,in_fiction_resolved,in_fiction_compliance_failure,layer_a_fired,layer_a_fallback_fired,layer_b_fired,layer_b_fallback_fired,resolved,skipped,expired,recursion_escalated,recursion_manual,cap_hit,pending_cleared_no_resolution}`. `record_parser_invocation` + `parser_calibration_snapshot` (every-50 rolling-window for drift detection per GPT post-council Flag 1+2).
- 8 new test files (112 new assertions): `test_clarification_aggregator.py` (12) / `test_clarification_session_state.py` (10) / `test_clarification_layer_a.py` (13) / `test_clarification_layer_b.py` (21) / `test_pending_clarification_directive.py` (17) / `test_clarification_telemetry.py` (13) / `test_clarification_in_fiction.py` (13) / `test_clarification_routing_e2e.py` (13). All green.
- DOCTRINE.md §1b.1 ANCHORED (sub-clause) with M-IMMEDIATE rejection record + decentralized aggregation lock + §F-59 refinement candidate filed forward. §59 count → 24. §1b instance list unchanged (six anchored; §1b.1 composes across them).
- VIRGIL_MASTER.md §10 snapshot updated. §59 count 23 → 24. §1b.1 sub-clause line added. S77 ship line added.
- ROADMAP.md priority queue updated (added Phase 3a S73 row that was missing; added §1b.1 row as ✅ SHIPPED; Phase 3b becomes 📋 next).

**Recon findings (R1-R10):**
- R1–R8 CLEAN per S75/S76 pre-recon.
- R9 IMPEDANCE — DM_PHILOSOPHY.md is 5861/6000 chars (139-char headroom); dispatch's ~250-word "On pending clarification" section would overflow and trigger truncation. **Resolved:** dropped static section in favor of dynamic `compute_pending_clarification_directive` (per-turn, only fires when pending). The dynamic directive carries identical operating-policy framing + concrete examples; static section was redundant prompt-budget cost. Architecturally cleaner — directive is state-gated, philosophy is always-on; pending clarification IS state-gated. Per F-60 "filings are starting points, not specs."
- R10 RESOLVED — `compute_pending_clarification_directive` placed in `dnd_orchestration.py` per §59 family-cohesion lean.

**Architectural correctness fix mid-session:** Initial wrap of quest_acceptance parser into `ParserResult` set `markers_present=bool(matched_verb)`, which would have routed every quest_accept MEDIUM through `IN_FICTION_CLARIFICATION` (M-DELAYED primary) instead of Phase 3a's existing medium-tier suggester. quest_acceptance doesn't surface structural markers (NPC/currency/item refs) at v0 — those come from the Phase 3b transaction + loot-drop parsers. Corrected `markers_present=False` for quest_accept; v0 ship preserves Phase 3a routing for quest_accept while keeping the M-DELAYED scaffold ready for Phase 3b parsers. Comment on the wrap site documents the rationale.

**Regression budget:** 1 caused (test_doctrine_76_four_property_audit needed `pending_clarification` + pre-existing `current_act_id` added to `EXPECTED_CLASSIFICATION` — both (False, True, True, False) → 2/4 clean). FIXED. 4 pre-existing failures observed (test_combat_narration_prompt_purity::test_default_unsuppressed_preserves_current_scene_block / test_init_end_buffer_reset / test_loot_directive / test_mechanical_hints) — file mtimes May 1-11 against engine state from later refactors (e.g., S67 retired `current_scene` block); not caused by S77 changes.

**Single restart deploy:** virgil-discord restarted at 12:51:15 PDT. 28 slash commands synced; chroma 1115 sessions / 740307 knowledge entries loaded; npc_pronoun_backfill scanned 27 / locked 0 (idempotent). No migration errors. Schema add of `pending_clarification` column ran cleanly under SQLite 3.45.1.

**Live verify Scenarios E + F + G deferred to Phase 3b.** v0 ships only quest_accept parser which is verb-only (no structural markers). Scenarios E (cross-domain Layer A) + F (M-DELAYED primary) require the transaction + loot-drop parsers shipping at Phase 3b with `markers_present` signals. Scenario G (compliance-failure telemetry) is mock-tested in `test_clarification_in_fiction.py` end-to-end. v0 verification at deploy: existing quest_accept paths preserved (no regression in Phase 3a behavior).

**§1b.1 ANCHORED at S77 ship.** Council pressure-test record (Oracle/GPT/Gemini three passes) documented in DOCTRINE.md §1b.1 for M-IMMEDIATE rejection with full reasoning. §F-59 refinement candidate ("operator-deliberate-commit" as authority claim with slash-paste + OOC-reply as instantiating surfaces) filed forward to next §F-59-touching ship. Empirical watch surfaces (per-parser calibration + per-scene clarification density + compliance failure tracking) operating in production.

**Doctrinal weight:** First anchor instance under WORKING_WITH_CLAUDE.md Planner-Lead-Architecture Discipline. The §11.13 M-IMMEDIATE → M-DELAYED pivot mid-dispatch (Gemini's third pressure-test pass surfacing Oracle's §1a-defense conflation) demonstrates the discipline's value: filed-forward council reasoning record prevents future re-litigation. **Note:** WORKING_WITH_CLAUDE.md did not yet contain the Planner-Lead-Architecture Discipline section at session start (dispatch referenced it as "already updated" but the file still had only Doc-currency discipline). Doc-currency drift surfaces between dispatch and live state — handoff flags this for planner attention.

**Ship:** ✅ SHIPPED (Phase 3 of 3). All shipped scope tested + deployed. Phase 3b infrastructure ready (aggregator + directive + schema + telemetry + cards + listener). Next session (S78) registers transaction + loot-drop parsers against existing aggregator; live verify Scenarios A + C + E + F at parser surfacing time.

**Next:** Session 78 = Inversion v0 Phase 3b implementation — transaction-completion + loot-drop parsers, register against §1b.1 aggregator's existing `ParserResult` shape with `markers_present` signals. Sonnet medium per WWC default cadence.

---

# Session 78 — Inversion v0 Phase 3b Implementation (May 16, 2026)

§1b.1 M-DELAYED primary path empirically activated. Two new closed-vocab parsers (`transaction_completion_parser`, `loot_drop_parser`) register against the S77 §1b.1 aggregator with full `markers_present` discrimination; post-LLM aggregator surface added. Recon-first per F-60; three architectural questions resolved at recon Phase A before implementation lock. Second anchor instance of Planner-Lead-Architecture Discipline (S77 first).

**Recon Phase A findings (R1-R5):**
- **R1 CLEAN with drift:** `_COIN_TRANSACTION_VERBS` is 47 verbs, not 18 as S74 documentation cited. The S65.1 baker-scenario hardening expanded coverage. Drift documented; structural implication unchanged.
- **R2 CLEAN:** N-1 (mechanical_hints) sole consumer is `_attach_hints` at `discord_dnd_bot.py:2806` → DM narration embed bullet-list edit. Isolated surface; LLM-extraction-with-suppression-gate mechanism (NOT §1a.x-disciplined).
- **R3 RESOLVED — Code's lock: (c) surface-separated.** N-1 stays unchanged (Avrae bookkeeping bullets on narration embed); transaction_completion fires alongside for §1b.1 aggregator routing (#dm-aside clarification surface). Vocabulary overlap is incidental — different mechanisms, different outputs, different consumer surfaces. Preserves S65.1 baker-scenario hardening without retrofit. Open for operator + Oracle confirmation at handoff per dispatch.
- **R4 IMPEDANCE → RESOLVED:** Post-LLM aggregator surface required. Clean integration point at `_dm_respond_and_post:4251` alongside existing `_attach_hints` post-LLM hook. quest_accept stays pre-LLM-only per S73.1 lesson (LLM paraphrase misses canonical acceptance verbs); transaction_completion + loot_drop register both surfaces.
- **R5 CLEAN:** All structural-signal accessors (`get_recently_active_npcs`, `get_pending_loot`, `get_inventory`) stable signatures.

Recon report landed at `planner-scratch/PHASE3B_RECON_REPORT.md`.

**Scope shipped:**
- `transaction_completion_parser.py` NEW (~350 lines). Player-intent + LLM-completion verb sets with full tense + 3rd-person coverage per S73.1 lesson. Phrasals checked first (`pay for` wins over `pay`). 3-tier confidence: HIGH (verb + currency + NPC) / MEDIUM-with-markers (verb + 1-of-{currency,NPC,item}) / MEDIUM-no-markers (verb only) / LOW. Surface-namespaced LRU dedup so pre-LLM and post-LLM don't collide.
- `loot_drop_parser.py` NEW (~330 lines). Player-intent + LLM-reveal verb sets. Item-class noun vocabulary (sword/potion/etc.) + container noun vocabulary (chest/box/etc., LLM-reveal only). Single-distinctive-token fallback for multi-word pending items (≥4 chars). 3-tier confidence per §1b.1 lock.
- `discord_dnd_bot.py` — `_run_inversion_aggregator` (pre-LLM) extended: 3 parsers fan-out (quest_accept + transaction_completion_pre + loot_drop_player). NEW `_run_inversion_aggregator_post_llm` at `_dm_respond_and_post:4251`: 2 parsers fan-out (transaction_completion_post + loot_drop_llm) + Phase 3a-style suggester card render for HIGH fires + compliance-failure detection when LLM narrates state-change despite pending_clarification set. Two new card renderers: `_format_transaction_post_llm_card` + `_format_loot_drop_llm_card`. `get_recently_active_npcs` added to engine imports.
- N-1 UNCHANGED per R3 (c) lock. `mechanical_hints.py` continues operating; `_attach_hints` post-LLM hook continues firing.
- Telemetry — `record_parser_invocation` extended to 5 parser domains (quest_accept + transaction_completion_pre/post + loot_drop_player/llm). Existing event taxonomy unchanged; per-fire `parser_fired` events extend with `parser_domain` and `surface` disambiguation via the `route` and `confidence` payloads.
- 3 new test files / 86 new assertions / all green:
  - `test_transaction_completion_parser.py` (42 assertions)
  - `test_loot_drop_parser.py` (29 assertions)
  - `test_phase3b_aggregator_integration.py` (15 assertions)
- DOCTRINE.md §1b.1 first-firing-instance line updated; §1a.x running anchor-instance count → 5 parser surfaces.
- WORKING_WITH_CLAUDE.md **Planner-Lead-Architecture Discipline section landed** (was flagged at S77 handoff as referenced-but-not-yet-written). S77 named first anchor; S78 named second anchor with full content.
- VIRGIL_MASTER.md §10 + ROADMAP.md updates per WWC Rule 1.

**No schema changes.** v0 Phase 3b is pure additive parser registration; no DB migration. Pre-ship backup ran defensively per S65 standing practice.

**Regression budget:** 0 caused. Full S77 sweep + Phase 3a sweep + §76 audit all green post-S78 changes. Pre-existing failures observed at S77 (mechanical_hints/init_end_buffer_reset/loot_directive/combat_narration_prompt_purity::current_scene_block) unchanged — pre-date current engine state per file mtimes May 1-11.

**Single restart deploy:** virgil-discord restarted at 13:30:30 PDT. 28 slash commands synced; chroma 1115 sessions / 740307 knowledge loaded; npc_pronoun_backfill clean. No errors at startup or parser-module import.

**Live verify Scenarios A + C + E + F:** Test prompts surfaced in handoff for operator-driven verification. Pre-verify: integration tests (`test_phase3b_aggregator_integration.py`) drive the four scenarios at the parser+aggregator boundary green — Stage 1 routing decisions for all four shapes are confirmed correct.

**§1b.1 first production firing instance** documented in DOCTRINE.md at operator's live-verify completion. (Test-pack-driven integration test counts as v0 firing-instance baseline; production-narration firing pending operator action.)

**F-64 sixth instance status:** S78 produces sixth instance candidate naturally. Transaction-completion parser's HIGH-tier fires on canonical "narration-claims-state-change" pattern: LLM narrates "Garrick pockets the gold" → engine state HASN'T been updated; without the §1a.x parser surfacing the operator-paste card, this would be a §F-64 silent contamination (narration claims canon; engine doesn't enforce). The parser+card surface IS the structural response to F-64. F-64 anchoring walk is the natural next-session topic — sixth instance now empirically present. Filed for S79 consideration.

**Doctrinal weight:** Phase 3b activates M-DELAYED in production. Future workload parsers (butler reminder/task intents; web onboarding flow) inherit the closed-vocab + ParserResult + §1b.1 aggregator pattern cleanly — 5 parser surfaces now demonstrate the shape across 2 narration loci (pre-LLM + post-LLM).

**Ship:** ✅ SHIPPED. All scope tested + deployed. M-DELAYED primary path live for transaction-completion + loot-drop ambiguity.

**Next:** S79 = either F-64 doctrine anchoring walk (sixth instance produced at S78 makes this the natural anchor host) OR S69 Causality Engine Path A Phase 3 implementation. Operator decides at end-of-session-handoff signal.

## S78 post-live-verify patches (same session)

Operator's first live verify produced two findings that were ship-blocking and demanded immediate patch:

**Finding 1 — race condition on LAYER_A/B routes.** Operator narrated `"I pay Mara 2gp for 1 loaf as agreed upon"`; the pre-LLM aggregator detected ≥2 parsers ≥MEDIUM (quest_accept on 'agreed' verb-only + transaction_completion on currency-marker), routed to LAYER_B (because quest_accept's empty payload broke the all-or-nothing enumerability check). Card surfaced in #dm-aside. But the LLM narration ran independently via the batcher 15s later and narrated the transaction as completed — operator was still reading the clarification card when the DM finalized the action. The bug: only IN_FICTION_CLARIFICATION set `pending_clarification` on `dnd_scene_state`; LAYER_A/B routes did not, so the prompt's `compute_pending_clarification_directive` had no state to inject. The race was structural, not timing.

**Finding 2 — LAYER_B card UX friction.** Operator: "this should be a 1,2,3 choice why type it out?" Layer B card asked operator to type domain names (`"transaction_completion"`, `"skip"`); operator preference is numbered options. Per WWC operational discipline rule 5 (operator design preferences are constraints).

**Patches landed:**

- `clarification_handshake.py`:
  - `_are_candidates_enumerable` loosened from `all()` to `any()` — LAYER_A now fires whenever any candidate has a populated payload (the operator's case now routes to LAYER_A with a single labeled transaction option, not LAYER_B).
  - `build_layer_a_card` filters out empty-payload candidates from the rendered options.
  - `build_layer_b_question` rewritten to use `**1.** transaction_completion / **2.** loot_drop / **3.** skip` numbered options.
  - `parse_layer_b_reply` extended to accept numeric replies (`"1"`, `"2"`, `"3"`) in addition to domain-name + skip-token replies.

- `discord_dnd_bot.py`:
  - `_dispatch_clarification_fallback` LAYER_A branch sets `pending_clarification` on direct (non-fallback) fires per S77 M-DELAYED discipline. Operator's same-turn narration now reads pending state and narrates scene continuing without finalizing.
  - `_dispatch_clarification_fallback` LAYER_B branch sets `pending_clarification` on direct fires.
  - All `clear_pending_clarification` calls in Layer B resolution paths (EXPIRED / EXPLICIT_SKIP / COMMIT_* / AMBIGUOUS-recursion / manual escalation) are now unconditional (idempotent if no state was set; cleans up direct-route state on resolution).

- `test_clarification_layer_b.py` extended with 7 new assertions covering numbered card format + numeric reply parsing + skip-slot semantics. All 28 LayerB tests + all other clarification + Phase 3b + Phase 3a + §76 audit suites pass post-patch.

**Architectural recovery — Layer A is now the dominant cross-domain route.** Pre-patch the all-or-nothing enumerability check fell to LAYER_B for any case where one parser had no payload. Post-patch LAYER_A fires whenever any parser has content; LAYER_B is reserved for truly-non-enumerable cases (≥2 parsers all empty). Operator's 1,2,3 UX request was for LAYER_B — the patches make LAYER_B rarer (good) AND give it better UX when it does fire (also good).

**Bot restarted at 13:53:51 PDT with patches live.** Restart-preservation notice fired correctly for campaign 111 (post-LLM aggregator had set pending state on the operator's earlier transaction-completion turn). Inspecting `dnd_scene_state.pending_clarification` confirmed `trigger_event_id` = `post_llm:ts=1778964371` with the transaction-completion candidate payload — proves the post-LLM aggregator is firing correctly even before the pre-LLM patch.

**Filed forward as S79 considerations:** quest_accept's MEDIUM fire on 'agreed' verb in non-quest narration is a real false-positive surface. Operator's utterance "as agreed upon" is referential, not a fresh acceptance. Two possible refinements: (a) tighten quest_accept's verb context (require co-occurring quest-shape signal); (b) expand the §1b.1 aggregator's discrimination layer. Filed as v0.x telemetry-driven tuning per WWC standing practice — production ignore-rate per quest_accept MEDIUM determines the right fix shape.

---

# Session 79 — F-64 Doctrine Anchoring Walk Phase 1 (May 16, 2026)

Path A doctrine-anchoring Phase 1. Independent planner structural analysis walk. No code; no canonical-doc amendments. Sonnet medium per WWC default. **Third Planner-Lead-Architecture Discipline anchor instance** (S77 first / S78 second / S79 third).

**Deliverable:** `planner-scratch/F64_ANCHORING_WALK.md` (~9k words; §0-§8). Council prompt skeleton at `planner-scratch/F64_COUNCIL_PROMPT_DRAFT.md`.

**Walk outcomes:** instance inventory reduced from 11 to 9 (reclassified N-1 over-firing → N-1 tuning surface; loot_drop_llm misfire → parser-vocab-overlap surface — both flagged for S81 recon confirmation). Framing test: current F-64 framing fits 8 of 9 instances cleanly; instance #11 (§F-08-a central thread compliance failure) doesn't fit (engine has the directive; LLM violates compliance — structurally inverted from F-64). Closure-pattern bifurcation: F-64's engine-side-surface closure covers 8 instances; instance #11 requires detection-telemetry + iteration closure.

**Anchoring readiness lean:** Outcome 2 — split into F-64 + §77.1 (planner's lean; council pressure-tests at S80). Confidence: HIGH on split / MEDIUM-HIGH on §77.1 placement / MEDIUM on F-64 anchor language.

**Six pressure-test questions surfaced for council** with anti-conformity protocol built into prompt skeleton per WWC Planner-Lead-Architecture Discipline Rule 4.

**Ship:** ✅ SHIPPED (walk + council prompt). Next: S80 council pressure-test dispatch.

---

# Session 80 — F-64 Council Pressure-Test (May 16, 2026)

Path A doctrine-anchoring Phase 2. Three-way council (Oracle / GPT / Gemini) pressure-tests S79 walk lean. Council produced **three convergent overrides** on planner's hypothesis:

1. **Gemini Q1 reword:** F-64 framing rephrased to remove inadvertent §1a-violation reading. Final framing: "LLM narrates a mechanical/canonical state change that bypasses deterministic parsers; state desyncs across turns." The LLM is doing its job (narrating); the engine is structurally unequipped to anchor the claim.
2. **Gemini Q3 placement change:** compliance-failure doctrine moves from §77.1 sub-clause to top-level §82 candidate. §77's atmospheric-continuity scope doesn't structurally absorb substrate-wide compliance-failure. §82 is a different failure mode, not a property axis — earns top-level anchoring (when threshold met), not sub-clause placement.
3. **GPT + Oracle Q5 deferral:** §82 anchoring DEFERRED at S81. 2 instances (S77 `clarification_in_fiction_compliance_failure` + S78 §F-08-a) insufficient empirical maturity. Threshold for §82 anchoring: 3 structurally-identical instances across distinct directive surfaces. Anchoring at 2 risks "prematurely formalizing a temporary implementation pattern." Compliance-failure telemetry SHIPS at S81 as §82-candidate-application; doctrine itself stays candidate until third instance accumulates.

**Council convergent locks (S80):**
- F-64 anchors at S81 (sixth-instance threshold met decisively; cluster cleaned by S79 walk reclassifications).
- Generic-with-payload telemetry pattern (GPT + Gemini Q6 convergent) — single `directive_compliance_failure` event with directive_name payload field; preserves grep surface; zero schema coupling.
- §F-44 absorbs S78 Bishop's bakery instance #7 per Oracle Q1 audit (NPC-axis cross-axis bleed).
- loot_drop_llm reclassification CONDITIONAL on S81 Code recon (Q4 unresolved).

**GPT closing macro-observation** filed for landing at S81: doctrine-graph proliferation watch — at 76+ anchored entries, doctrines start tangling rather than building. Standing discipline lands in WWC at S81.

**Ship:** ✅ SHIPPED (council pressure-test complete; three overrides applied). Next: S81 implementation.

---

# Session 81 — F-64 Anchoring + Compliance-Failure Telemetry Implementation (May 16, 2026)

Path A doctrine-anchoring Phase 3 implementation. Closes S79 walk + S80 council arc. Sonnet medium per WWC default. **Fourth Planner-Lead-Architecture Discipline anchor instance** (S77 first / S78 second / S79 third / S81 fourth — post-council-pressure-test implementation with three reviewer overrides applied).

**Recon Phase A findings (R1 + R2):**

- **R1 loot_drop_llm production audit CLEAN.** Telemetry data (`playtest/inversion_v0_20260516.jsonl`): 15 `loot_drop_llm` events emitted; 4 routed MEDIUM fires; 1 LAYER_A card surface (the exact S78 Mara transaction sequence misfire). All 4 fires produced advisory cards only; no engine writes; operator-loop caught reliably (no `/loot claim` paste). **Reclassification: loot_drop_llm misfire is parser-vocab-overlap surface, NOT F-64.** Filed forward as v0.x §1a.x parser-tuning queue.

- **R2 SESSIONS S43-S78 audit found 1 additional F-64-shape candidate.** S51 player-narrative-authority drift — DM caved on player premise contradicting scene canon; materialized merchant interior INSIDE training ground; subsequent narration treats LLM-authored state as ground truth. Filed at S51 as candidate "§77 sub-section" but never anchored. Structurally a clean F-64 instance (narration claims scene-boundary canon, engine doesn't enforce, subsequent narration treats LLM-authored state as ground truth). Subsumed into F-64 cluster at S81 anchor as instance #8.

- **Net cluster at S81 anchor:** **7 instances** (dispatch's 8-instance framing adjusts; loot_drop_llm out; S51 in; Bishop's bakery to F-44).
- No HALT-class impedance.

**Scope shipped:**

- **DOCTRINE.md §F-64 anchored entry.** Promoted from candidate. Full structural framing per Gemini Q1 reword. Architectural-relationship map made explicit (§1a / §1a.x / §1b / §1b.1 / §76 / §77 / §F-44). 7-instance cluster table with closure shape per instance. §82 sister-doctrine candidate filed forward.
- **FAILURES.md updates:** F-64 candidate section retired (cross-reference to DOCTRINE.md §F-64); §F-44 entry expanded with NPC-axis Bishop's bakery instance; §82 candidate entry filed with anchoring threshold + architectural-design-time guidance + generic-with-payload reasoning + filed-forward detector list (4 candidate directive surfaces).
- **`inversion_telemetry.py`** — `record_directive_compliance_failure` added per S80 Q6 generic-with-payload lock. Stable payload shape: `directive_name`, `severity`, `narration_excerpt` (capped 200), `detector`, `campaign_id`, `confidence`, `directive_intent` (capped 100). Grep surface preserved via `directive_name` field.
- **`discord_dnd_bot.py`** — S77 `clarification_in_fiction_compliance_failure` event refactored to fire via generic event with `directive_name="pending_clarification"`. Per S80 Q6 retirement of prior event name.
- **`dnd_orchestration.py`** — `detect_central_thread_compliance_failure` heuristic detector added. Deterministic content-token overlap (≥4 char, stopword-filtered) between thread directive body and narration. 3 severity bands per dispatch: LOW (<20% overlap, not flagged as violation), MEDIUM (20-40%), HIGH (≥40%).
- **`discord_dnd_bot.py`** — `_run_central_thread_compliance_check` post-LLM background task wired at `_dm_respond_and_post` alongside `_attach_hints` + post-LLM aggregator. Fires `directive_compliance_failure` event for MEDIUM/HIGH violations. Telemetry only; no state mutation.
- **WORKING_WITH_CLAUDE.md** — Doctrine-graph-proliferation-watch section landed per GPT S80 closing macro-observation. Three standing discipline rules: sub-anchor proliferation watch / anchor-threshold reinforcement / cross-doctrine relationship-map maintenance. S81 §82 deferral documented as first explicit application of anchor-threshold discipline under planner-lead-architecture. WWC Planner-Lead-Architecture Discipline anchor instance list extended (S79 third + S81 fourth added).
- **2 new test files** (31 new assertions, all green):
  - `test_directive_compliance_failure_telemetry.py` (16 assertions): event shape, payload caps, grep-surface verification, invalid-severity default.
  - `test_central_thread_compliance_detector.py` (15 assertions): empty inputs, clean narration, HIGH/MEDIUM/LOW severity bands, stopword filter.
- **Regression sweep clean** — all 15 clarification + Phase 3b + inversion-v0 + §76 audit test suites still green post-S81 changes.

**No schema changes.** Pure additive (telemetry + detector + doc-only doctrine anchor). Pre-ship backup ran defensively per S65.

**Single restart deploy:** virgil-discord restarted at 20:56:11 PDT. 28 slash commands synced; chroma 1141 sessions / 740307 knowledge loaded; npc_pronoun_backfill clean. No errors at startup or module imports.

**Live verify NOT required.** Anchor lands at documentation; telemetry instrumented but fires empirically as future narration generates compliance-failure events. Operator + planner read telemetry data over time per §82 architectural-design-time guidance.

**Doctrine state post-S81:**
- §F-64 ANCHORED (7-instance cluster; full architectural-relationship map).
- §82 CANDIDATE filed (2 instances; threshold 3 across distinct directive surfaces; deferred per council).
- §F-44 instance list expanded (Bishop's bakery NPC-axis instance added per S80 Q1 Oracle).
- §1a.x running anchor instance count unchanged (5 narration-detection parser surfaces).
- §59 sibling count unchanged (24; pending_clarification_directive is #22 in-file / #24 overall).

**Compounding leverage banked:**
1. §F-64 anchored doctrine names substrate-level failure mode with explicit architectural-relationship map. Future ships citing F-64 don't re-derive framing or re-litigate scope.
2. §1a.x empirically validated as architectural closure for §F-64. Doctrine-pair shape (failure-mode + architectural-response) parallels §76↔§17.
3. §82 candidate filed with explicit threshold + architectural-design-time guidance. Future MUST/MUST-NOT directive ships plan compliance-detection telemetry concurrent without waiting for §82 to anchor.
4. Generic-with-payload telemetry pattern reusable for any future telemetry surface where directive-disambiguation matters without schema coupling.
5. Doctrine-graph-proliferation-watch landed in WWC. Future anchoring decisions reference the discipline; sub-clause-vs-top-level questions resolved against the proliferation-watch test.
6. S78 Bishop's bakery instance compounds §F-44 cluster toward its own anchoring (substrate-level bleed cluster grows).
7. R1 + R2 recon produces empirical-evidence baseline. Anchor's empirical claim is verified, not assumed (loot_drop_llm reclassified per actual telemetry; S51 instance found per audit pass).
8. Fourth Planner-Lead-Architecture Discipline anchor instance — pattern operates across implementation ships (S77), recon-first dispatches (S78), doctrine-anchoring walks (S79), and post-council-pressure-test implementations (S81).

**Ship:** ✅ SHIPPED. §F-64 ANCHORED. §82 CANDIDATE filed. Compliance-failure telemetry instrumented. Doctrine-graph-proliferation-watch landed.

**Next:** Operator-decision priority queue (Phase 3c NPC-commitment-utterance + N-3.1 fold-in / S69 Causality Engine Path A Phase 3 / N-4 v1.x descriptor→name pronoun gap / §F-44 closure with Bishop's bakery instance compounding). Filed for operator handoff.
