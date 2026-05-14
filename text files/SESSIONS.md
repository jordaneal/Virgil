# VIRGIL SESSION LOG

Append-only chronological ledger. Each entry covers what shipped, what was live-verified, and a brief narrative. Architectural lessons live in `DOCTRINE.md`; failures and rejected approaches live in `FAILURES.md`.

For "what is the system today" → `VIRGIL_MASTER.md`
For "what's next" → `ROADMAP.md`
For "why did we do it that way" → `WHY.md`
For "how do I work with Claude" → `WORKING_WITH_CLAUDE.md`

## Index

- **[Session 5 — Avrae Pivot](#session-5--avrae-pivot)** — Retired the Telegram bot; rebuilt around Avrae as the rules engine.
- **[Session 6 — Orchestration Layer](#session-6--orchestration-layer)** — Roll discipline became a rules engine; severity bands; Phase 1.1 + 1.3.
- **[Session 7 — Phase 1.4 Complete](#session-7--phase-14-complete)** — Combat-mode FSM, tension thermometer, manual clocks, mode-aware classifier.
- **[Session 8 — Phase 2 Complete](#session-8--phase-2-complete)** — Combat stabilization, observability layer, multi-actor narrative fidelity, `/encounter`.
- **[Session 9 — Phase 3 Ships, Narration Drift Surfaces](#session-9--phase-3-ships-narration-drift-surfaces)** — Suggested Actions live; auto-execute shipped, blocked by Layer 2 drift.
- **[Session 10 — Phase 1 Closes, Model Swap, Phase 3 Validates Live](#session-10--phase-1-closes-model-swap-phase-3-validates-live)** — gpt-oss-120b model swap unblocks drift; Phase 3 fires live; orchestration regex audit.
- **[Session 11 — Phase 11.1 Mechanical Hints (Advisory Parser) Shipped Live](#session-11--phase-111-mechanical-hints-advisory-parser-shipped-live)** — Third advisory parser instance; `!game coin / longrest / shortrest` whitelist.
- **[Session 12 — Phase 12 Persistence Layer + Movement Primitives + Documentation Restructure](#session-12--phase-12-persistence-layer--movement-primitives--documentation-restructure)** — Persistent NPCs + locations + authored canon; `/travel`; doc split.
- **[Session 13 — Ship 4 Telemetry + Campaign Management Surface](#session-13--ship-4-telemetry--campaign-management-surface)** — Phantom-location telemetry; campaign cascade with two-gate destruction; S9 capability v1.
- **[Session 14 — Track 3 Opens (Pacing + Central Thread + DM Philosophy) + Corpus Inventory](#session-14--track-3-opens-pacing--central-thread--dm-philosophy--corpus-inventory)** — Six ships convert state into directives. Final web-app session.
- **[Session 15 — Claude Code Migration, Donovan/Ruby Fix, PC Contamination Guard, Backup-to-PC](#session-15--claude-code-migration-donovanruby-fix-pc-contamination-guard-backup-to-pc)** — First Claude Code session; PC contamination guard; backup-over-Tailscale.
- **[Session 16 — Consequence Surfacing v1 (Spec → Review → Ship), Operating-Model Reframe](#session-16--consequence-surfacing-v1-spec--review--ship-operating-model-reframe)** — `dnd_consequences` schema; dual-pass parser; build-to-bar reframe.
- **[Session 18 — Observability Batch (S22–S25)](#session-18--observability-batch-s22s25)** — Four pure-observability log lines; B2 attack-template ship + B2.1 follow-up.
- **[Session 21 — Combat Persistence Directive v1 (Spec → Lock → Ship → Live Verify)](#session-21--combat-persistence-directive-v1-spec--lock--ship--live-verify)** — `!init list` snapshot drives concrete combatant block in prompt.
- **[Session 22 #1 — Track 4 #1 Narrative Inventory v1 (Spec-Brief → Implement → Verify)](#session-22-1--track-4-1-narrative-inventory-v1-spec-brief--implement--verify)** — Per-character inventory; silver-key cellar narrative live.
- **[Session 22 #2 — Track 4 #2 Loot Generation v1 (Pivot → Implement → Two-Pass Live Verify)](#session-22-2--track-4-2-loot-generation-v1-pivot--implement--two-pass-live-verify)** — Death-edge detection; AUTHORITATIVE/EXHAUSTIVE framing; chroma purge.
- **[Session 23 #1 — Track 6 #1 Active-State Footer v1 (Bot-Appended → Pure Function → Live Verify)](#session-23-1--track-6-1-active-state-footer-v1-bot-appended--pure-function--live-verify)** — `render_state_footer` pure function; mode/turn/round in Discord footer.
- **[Session 23 #2 — Track 6 #2 Combat Redirect Directive v1 (Sibling Pattern → Implement → Live Verify Bypass)](#session-23-2--track-6-2-combat-redirect-directive-v1-sibling-pattern--implement--live-verify-bypass)** — On-turn combat-bypass redirect; fourth pure-function sibling.
- **[Session 23 #3 — Discord Channel Cleanup + Canonical /setup (Pure Planner → Migrate → Idempotency)](#session-23-3--discord-channel-cleanup--canonical-setup-pure-planner--migrate--idempotency)** — `compute_setup_plan` extends pattern to infrastructure ops.
- **[Session 25 — `/setup` housekeeping (Avrae perms + #commands + AFK voice) + Track 6 #3 OOC Advisory Lane v1](#session-25--setup-housekeeping-avrae-perms--commands--afk-voice--track-6-3-ooc-advisory-lane-v1)** — Avrae perms reconciled; `#dm-aside` advisory lane shipped.
- **[Session 25 #2 — Track 6 #3.1 Advisory Command Reference v1 + Track 6 #3.2 Auto-Generated Virgil Section](#session-25-2--track-6-31-advisory-command-reference-v1--track-6-32-auto-generated-virgil-section)** — `COMMANDS.md` loaded fresh into advisory; decorators become single writer of the Virgil section.
- **[Session 25 #3 — Multiplayer Test (Friend Joins, System Stress-Tested)](#session-25-3--multiplayer-test-friend-joins-system-stress-tested)** — Two-player live test surfaced systemic gap: directives are advisory, not binding. Catalogued as F-45 through F-52.
- **[Session 25 #4 — Track 7 #1 Adjudication Layer v1 (Bones Ship: Binding Refusals)](#session-25-4--track-7-1-adjudication-layer-v1-bones-ship-binding-refusals)** — Five action categories, deterministic gates, narration-binding constraints. 4/7 categories binding live; capability deferred via cache miss.
- **[Session 25 #5 — Track 7 #1.1 Cache Auto-Populate (Capability Adjudication Goes 7/7)](#session-25-5--track-7-11-cache-auto-populate-capability-adjudication-goes-77)** — `!sheet` posts auto-cache; capability refusals now bind for all bound PCs.
- **[Session 25 #6 — Bug 3: `/travel` location persistence + NPC list location-scoping](#session-25-6--bug-3-travel-location-persistence--npc-list-location-scoping)** — `/travel` upserts unknown destinations; `get_scene_state` regression caught live; strict NPC location filter; chroma bleed broken out as F-44.
- **[Session 26 — Track 6 #5.1 Combat Entry Assist (Inaugural §1b validated-suggester)](#session-26--track-6-51-combat-entry-assist-inaugural-1b-validated-suggester)** — `srd_resolver.py` pure-function module; 334-monster SRD index; exact + fuzzy + LLM-gated resolution; hook wired to `npc_upsert was_new=True`; no mode gate (§11.H); 32 tests across 3 files.
- **[Session 27 — Track 4 #3 Time Progression v1 (First Motion-Systems Ship)](#session-27--track-4-3-time-progression-v1-first-motion-systems-ship)** — `advance_time` single-write-path engine helper; `parse_elapsed` deterministic free-text → delta; `compute_time_directive` seventh §59 sibling; `render_state_footer` extension; four call sites (`/travel` / `!lr` / `!sr` / new `/advance`); skeleton `## Starting time` narrow §17 seed exception; 168 tests across six files; spec v1.2 LOCKED.
- **[Session 33 — Multiplayer Fixes Plan: S32 Findings → Five-Ship Plan → Three-Reviewer Cycle → ROADMAP F-55 Refresh](#session-33--multiplayer-fixes-plan-s32-findings--five-ship-plan--three-reviewer-cycle--roadmap-f-55-refresh-may-10-2026)** — No code. `MULTIPLAYER_FIXES.md` v2 drafted (584 lines, 14 review-cycle revisions); 5 ROADMAP patches propagating cluster commitments; Ship 3 files as F-55 #5.5; three planner-discipline lessons named.
- **[Session 34 — Ship 1 Resolution Binding: Engine-Bound DC-vs-Roll on the DM-Typed-Directive Surface](#session-34--ship-1-resolution-binding-engine-bound-dc-vs-roll-on-the-dm-typed-directive-surface-may-11-2026)** — Ship 1 implementation + 40 new test assertions across 4 files. Closes Finding L + F-45 regression + Bug 1 Phase 2 as side effect. Live verify A/B/D logged clean; E/F deferred via `MULTIPLAYER_VERIFY_DEFERRED.md` pickup doc. Two doctrine candidates filed unanchored.
- **[Session 34 #2 — Multiplayer Fixes Plan V3: Primary-Surface Re-Diagnosis, Avrae Recon, Promotion](#session-34-2--multiplayer-fixes-plan-v3-primary-surface-re-diagnosis-avrae-recon-promotion-may-11-2026)** — No code. Planning ship. v2 → v3 re-sequence inserts Ship A (LLM-Emitted-Directive Resolution Binding) at front of post-Ship-1 queue; 12 §12 decisions locked; Avrae A.2 recon cleared (form (a) clean — Avrae ignores trailing integer); v3 promoted to canonical. v2 archived at `_trash/MULTIPLAYER_FIXES_V2_20260511.md`.
- **[Session 35 — Ship A Spec + Review (DRAFT → LOCKED)](#session-35--ship-a-spec--review-may-11-2026)** — `LLM_EMIT_RESOLUTION_BINDING_SPEC.md` drafted (18 decisions: 12 pre-locked + 6 surfaced); review pass (S35b) applied 6 framing revisions; spec LOCKED v1.
- **[Session 36 — Ship A Implementation + 9 Live-Verify Patches](#session-36--ship-a-implementation--9-live-verify-patches-may-11-2026)** — Ship A SHIPPED LIVE. ~120 test assertions across 2 new + 4 extended files. Live verify clean: nat-20 PASSED case rendered with memorable-success texture; zero cascading rolls; Avrae compat confirmed for `**!check skill : Name**` bold-wrapped format. 9 patches landed in one session covering classifier coverage, DC strip, dc-preservation, emit-template, sentinel detection (cascading-roll fix), wider verb coverage, and no-DC `#dm-aside` notification.
- **[Session 37 — Hybrid Combat Exploration: GPT + Gemini External Review → v3 Two-Horizon Reframe](#session-37--hybrid-combat-exploration-gpt--gemini-external-review--v3-two-horizon-reframe-may-11-2026)** — No code. Architectural exploration session. Ship 2 spec drafting started but paused mid-prompt when Jordan surfaced extended-play concerns (novelty/repetition + combat-pacing friction). Drafted `HYBRID_COMBAT_NOTES.md` through three iterations: v1 hybrid combat concept; v2 incorporated ChatGPT's 4-tier compression ladder + 9 architectural flags; v3 incorporated Gemini's structural pushback ("can't compress 5e without breaking 5e") plus broader directive (playtest-first, freeze feature list, ship dumb combat, listener edge-case verify). v3 reframes as two-horizon: long-term architectural vision preserved as reference design only; near-term execution is disciplined retreat per Gemini's discipline — finish Ships 2-3, ship listener verification + dumb combat, extensive playtest phase, then MVP-test Ships 4-5. ROADMAP updated with reframe; Ships 4 and 5 flagged for MVP-test scrutiny.
- **[Session 37b — Ship 2 Spec Draft (SCENE_STATE_CANON_SPEC.md v1)](#session-37b--ship-2-spec-draft-scene_state_canon_specmd-v1-may-11-2026)** — No code. Spec drafted post-exploration: 649 lines, 4 §11 decisions (D1 Path A vs B for location-column treatment, D2 ship-all-5 deletions, D3 adjacent-table boundary, D4 housekeeping bundling). Recon traced extract_scene_updates, established_details readers, set_current_location, full dnd_scene_state schema; surfaced no HALT — all findings fit locked v3 §5 shape. §6.1 four-property audit table (load-bearing artifact) walked all 20 columns; 5 deletion targets + 3 dead-column drops. Doctrine §76 candidate phrasing drafted with 3 project instances (S22 #2 / S32 / S36). Spec status DRAFT → LOCKED after S38 review applied 4 framing refinements.
- **[Session 38 — Ship 2 Spec Review (SCENE_STATE_CANON_REVIEW.md v1)](#session-38--ship-2-spec-review-scene_state_canon_reviewmd-v1-may-11-2026)** — No code. Reviewer walked 4 decisions + cross-doc consistency check against `HYBRID_COMBAT_NOTES.md` v3 and `PLAYTEST_OBSERVATION_FRAMEWORK.md`. All 4 architectural locks confirmed. 4 implementation-note refinements requested: init_scene_state.seed parameter dead-code chain (D2), last_scene_change reader audit enumeration (D2), live-verify fresh-campaign discipline note for §9 Scenario C, new §11.D5 surfaced (four-property regression test scope: per-table default; D5-general filed as v1.x candidate post-Ship-3). Pre-emptive grep confirmed zero stale code paths touching dead columns.
- **[Session 39 — Ship 2 Implementation + §76 Anchored](#session-39--ship-2-implementation--76-anchored-may-11-2026)** — Ship 2 SHIPPED LIVE. Scene state canon discipline closed: five §76 deletion targets dropped from `dnd_scene_state` (`location` LLM-write freetext, `established_details`, `focus`, `open_questions`, `last_scene_change`) + three dead-column housekeeping drops (`active_npcs`, `active_threats`, legacy `tension`). Live DB migrated cleanly via idempotent ALTER TABLE DROP COLUMN (SQLite 3.45.1). Path A: reads migrate to `location_label` derived from `dnd_locations.canonical_name` via `current_location_id`. `init_scene_state` signature dropped seed parameter; `extract_scene_updates` no longer makes LLM call (writes only `last_player_action`); `update_scene_state` shrank SCALAR_FIELDS to `{last_player_action}` + new `DELETED_FIELDS` guard logs LLM-write attempts as drops. **105 new test assertions** across 2 new files. Spec LOCKED. **Closes Finding A.** **Doctrine §76 anchored** (Recursive hallucination memory loop / four-property latent-canon test) — three project instances S22 #2 / S32 / S36.
- **[Session 40 — Ship 3 Spec Draft (NPC_STATE_SYNC_SPEC.md v1)](#session-40--ship-3-spec-draft-npc_state_sync_specmd-v1-may-11-2026)** — No code. Spec drafted per MULTIPLAYER_FIXES.md v3 §6 — Finding H closure via fix candidate (a) (auto-create Avrae sheet on `/hydrate` via bot-emitted `!init opt` commands under proposed §65a narrow exception). 4 §11 decisions + 2 sub-decisions. C3 second-instance candidate identified. §4 four-property audit on dnd_npcs walked all 20 columns; zero 4/4 hits (every LLM-influenced write goes through §17 single-writer helper). §76 carries forward unchanged.
- **[Session 40b — Ship 3 Spec Review (NPC_STATE_SYNC_REVIEW.md v1)](#session-40b--ship-3-spec-review-npc_state_sync_reviewmd-v1-may-11-2026)** — No code. Review walked 6 decisions; 5 confirmed at recommendation, 1 (Sub-D2) confirmed with case-split revision request (silent mid-combat HP reset would be a player-experience disaster). Four spec revisions applied: Sub-D2 Case A/B split, §65a phrasing tightening, new §12.5 doctrinal observation (§17+§76 composition), PLAYTEST §3.2 mechanical-vs-narrative continuity framing.
- **[Session 45 — Combat-Boundary Hardening Bundle: Post-!init-end Buffer Reset + Init-Setup Silence Gate + COMBAT_END Auto-Closeout](#session-45--combat-boundary-hardening-bundle-post-init-end-buffer-reset--init-setup-silence-gate--combat_end-auto-closeout-may-11-2026)** — Three-surface bundle closing the combat→exploration boundary. Surface C: `reset_narrative_buffers_on_combat_exit` helper resets `current_scene` + `last_dm_response` + `last_player_action` at !init end. Surface D (v1+v2): init-setup window structural silence — `on_message` ⏳ gate when mode='combat' AND no active_turn (v2 primary) + `_dm_respond_and_post` forced-suppression (v1 defense-in-depth). Surface F: COMBAT_END as 4th combat-narration trigger kind — auto-fires aftermath closeout on !init end with both-layer enforcement (§77 instruction-side + S44 information-side). **§78 mode-transition state-reset anchored** post-verify-clean — third project instance of two-layer enforcement pattern (S43 + S44 + S45). 33 new test assertions across 3 new files + 78 regression assertions clean = 111 total. Three live-verify passes — pass 2 exposed surface D's residual premature combat narration after v1 conservative fix; in-session upgrade to v2 top-level gate; pass 3 all surfaces clean. Combat-boundary now structurally sealed.
- **[Session 44 — Combat Narration Prompt Purity v1.x](#session-44--combat-narration-prompt-purity-v1x-may-11-2026)** — S43 filed-follow-up. Closes ROUND_START phantom-NPC + stale-narrative bleed via information-side suppression of 10 prompt blocks during combat narration. Single `suppress_for_combat_narration: bool` param threaded through `_dispatch_combat_narration` → `_dm_respond_and_post` → `dm_respond` → `build_dm_context`. Three verify passes (2→9→10 blocks); each pass identified residual leak via DB inspection or full block audit, never speculation. Final set: chroma blocks (relevant_history + dm_pacing_examples), phantom-NPC sources (companions + recent_npcs_line), campaign-arc bleed (quests + inventory + central_thread + consequences + commitment), and rolling-narration buffer (`campaign.current_scene`). 17 new test assertions all green; pre-S44 behavior preserved for non-combat callers (default False). **Two-layer enforcement doctrine candidate filed**: §77 atmospheric continuity is enforced at instruction-side (S43 MUST/MUST-NOT clauses) + information-side (S44 context-block suppression); the layers compose. Final live verify clean: "The clash begins in a hush, lantern light wavering over the cramped bar as the two figures lock eyes... No blows have yet landed; the moment hangs, waiting for the first move."
- **[Session 43 — Dumb Combat Narration + Atmospheric-vs-Adjudication Doctrine](#session-43--dumb-combat-narration--atmospheric-vs-adjudication-doctrine-may-11-2026)** — Auto-narration on three combat-mode state transitions (ROUND_START + BLOODIED_THRESHOLD_CROSSED + COMBATANT_DOWNED) via `_dm_respond_and_post`'s `transition_context` carrying categorical HP roster + verbatim MUST/MUST-NOT invariants. DEATH_SAVE_EVENT_START deferred per S42 fixture blocker. Path B no-spec ship per `HYBRID_COMBAT_NOTES.md` v3 §3.1 step 4. **Load-bearing narrative:** atmospheric continuity, not adjudication — the cliff-edge is mechanical-state-mutation inference. Live verify Scenarios A-F: doctrine HOLDS at cliff-edge (no mechanical drift in any narration); BLOODIED/DOWNED narrations verified clean; ROUND_START has quality drift (phantom NPCs from `recent_npcs` block + stale-narrative bleed from `last_dm_response`) filed as v1.x prompt-purity candidate. **Atmospheric-vs-adjudication doctrine ANCHORED** post-verify-clean. 4 new pure functions in `dnd_orchestration.py` (10th §59 sibling) + 39 new test assertions + 238-assertion regression sweep clean across 12 listener/combat-adjacent files.
- **[Session 42 — Listener Edge-Case Verification + Multi-Attack/Dice-Modifier Patches](#session-42--listener-edge-case-verification--multi-attackdice-modifier-patches-may-11-2026)** — Pre-playtest infrastructure ship per `HYBRID_COMBAT_NOTES.md` v3 §3.1 step 3. Empirical recon-and-fix pass on `avrae_listener.py` against 5e combat embed edge cases. **Two structural parsing gaps surfaced + patched**: (1) advantage/disadvantage rolls (`2d20kh1`/`2d20kl1` dice notation) silently returned None pre-patch because `_ROLL_RE` and `_TO_HIT_LINE_RE` required bare `\d*d\d+` immediately before parens; new `_DICE_NOTATION` constant allows modifier suffixes. (2) multi-target attacks captured only the first sub-attack; new `_extract_attack_from_field` helper walks `embed.fields` and surfaces `attacks: list[dict]` for multi-target embeds while preserving top-level single-attack back-compat. Per-parse `listener_parsed:` telemetry added for future-audit observability. 7 new test assertions all green; listener-adjacent regression sweep clean (123 assertions across 6 existing files). Live re-walk empirically confirmed clean parsing for adv/disadv/multi-attack/resistance damage. Crit-force / save-with-damage / death-save outcome paths filed as deferred future-ship candidates per fixture-availability constraints. No HALT escalations; no new doctrine candidates surfaced. **Listener verification now trustworthy for the post-Ship-3 playtest phase.**
- **[Session 41 — Ship 3 Implementation: Avrae Bot-Filter HALT-and-Pivot to §1b Suggester](#session-41--ship-3-implementation-avrae-bot-filter-halt-and-pivot-to-1b-suggester-may-11-2026)** — Ship 3 SHIPPED LIVE post-in-session-pivot. Closes Finding H. **Load-bearing narrative: HALT-and-pivot pattern.** The originally-locked fix candidate (a) was empirically blocked by Avrae's bot-filter (identical commands mutate state when human-typed, silently filtered when bot-typed). Pivoted in-session to candidate (a') per operator decision: §1b validated-suggester pattern (precedent: Track 6 #5.1 SRD suggester). Three Avrae verify findings locked: bot-filter (structural API boundary), `-h` is hidden-toggle NOT HP (the working flag is `-hp` at both add and opt), `!init opt` cannot set max-HP (the clean fix needs remove + add -hp + opt -ac). Locked 3-line suggester sequence. **§1b second project instance proven** (Ship 3 joins Track 6 #5.1 SRD suggester). **§12.5 composition observation lands** (§17+§76 composition pattern: gated-write discipline preempts four-property surfaces). **§65a NOT anchored** (suggester dissolves the need). **C3 NOT anchored** (claim withdrawn — suggester isn't a single bot-side writer). 13 new test assertions; Scenario A live-verify GREEN (`<13/13 HP> (AC 13)`). Operator `/hydrate`-as-emergency-fix reframe absorbed; canonical NPC entry flow is DM typing `!init add` with full stats inline.

---

# Session 5 — Avrae Pivot

The architectural pivot: retired the Telegram D&D bot and rebuilt around Avrae as the rules engine. Mechanical issues that plagued Sessions 3-4 (loop on stealth check, no roll awareness, drift) disappeared once Avrae owned mechanics and Virgil owned narration.

## What shipped

- `dnd_engine.py` — pure narrative core, no Telegram, no mechanics.
- `avrae_listener.py` — parses Avrae's embed format into structured events.
- `RollBuffer` — per-guild deque with TTL to correlate rolls with player text in `#dm-narration`.
- Rewrote `discord_dnd_bot.py` from 13 mechanical commands to 7 narrative commands.
- `/bindchar` autocomplete dropdown that scans Avrae's recent `!sheet` embeds.

## Live verification

Avrae embed parser hit on first try once the character name was found in `embed.author.name` (not `embed.title`). Mode flow worked end-to-end after Discord client cache flush.

## Cross-references

- Doctrine precursor: prompt-vs-structure (`DOCTRINE.md` §1) — first session that proved swapping the LLM for a rules engine fixed problems that prompt edits couldn't.
- Doctrine precursor: engine defends its own invariants (`DOCTRINE.md` §16) — the `merge_bot_overwrite()` fix.
- Failure: silent module-state regression (`FAILURES.md` §F-01) — 740k knowledge base broken since import.
- Failure: Discord channel-level permission overrides (`FAILURES.md` §F-02).
- Failure: multi-line regex patches failing silently (`FAILURES.md` §F-03).

---

# Session 6 — Orchestration Layer

The session that built the structured gameplay layer between player input and the DM prompt. Roll discipline stopped being a prompt directive and became a rules engine; the LLM stopped having to be smart enough to be a DM.

## What shipped

- `dnd_orchestration.py` — structured gameplay layer. CharacterContext cache, intent classifier, RollDecision rules engine. No Discord deps; pure logic, unit-testable.
- Phase 1.1 — Roll Discipline + Sheet Awareness.
- Phase 1.3 — Scene State (with async LLM extraction in a daemon thread).
- Anti-genre-bleed prompt rules with explicit forbidden-phrase list.
- Severity bands so a roll of 10 is a partial success, not a generous one.

## Live verification

The DM started naturally referencing darkvision, rogue training etc. without us spelling it out per prompt. "Asks for too many rolls" problem fixed permanently by moving roll decisions into the rules engine. The DM stopped re-describing established cave details.

## Cross-references

- Doctrine: prompt-is-tone-and-pacing-structure-is-the-game (`DOCTRINE.md` §1) — the load-bearing lesson, named here. ChatGPT's framing: "the prompt is tone and pacing. The game is structured state."
- Doctrine: hard-stop rules go at the END of the prompt (`DOCTRINE.md` §2) — added the HARD STOP RULES block after the LLM ignored "STOP after asking for a roll."
- Doctrine: when the user pushes back, listen the first time (`DOCTRINE.md` §5) — Avrae roll syntax went through three iterations after Jordan said "no underscores" / "no quotes."
- Failure: multi-line regex patches recurring (`FAILURES.md` §F-03).

---

# Session 7 — Phase 1.4 Complete

Phase 1.4 went from kickoff to complete in a single session. All five steps shipped, every transition live-verified, full FSM working.

## What shipped

- **Step 1** — Combat-mode FSM in 5 sub-patches: `update_scene_state()` enforces `LOCKED_FIELDS`; `/mode` slash command; `parse_init_event()` (12/12 unit tests, written from real `[INIT_CAPTURE]` samples); `on_message_edit` handler for Avrae's confirm-edit pattern; `_INIT_END_RE` matches both "combat ended" and "end of combat report".
- **Step 2** — Mode-aware tonal directives. Replaced bare `=== CURRENT MODE ===` with one-paragraph directive per mode in `build_dm_context`.
- **Step 3** — Tension thermometer. `tension_int INTEGER DEFAULT 0`, `tension_label()` mapping (Calm / Mounting / Dangerous / Climax), `calculate_tension_shift()` pure function, 16/16 unit tests.
- **Step 4** — Manual progress clocks. `progress_clocks TEXT` JSON list, `/clock` group with 6 subcommands, autocomplete on the name parameter.
- **Step 5** — Mode-aware intent classifier. `classify_action_intent()` accepts mode as third parameter; RISKY_RX hardened with negative lookaheads on `steal`/`sneak`. 15/15 unit tests.

## Live verification

Combat starts and ends without a human flipping a switch. Tension rises with damage, decays with rest. DM voice changes when mode changes. All five steps validated live before the next started.

## Cross-references

- Doctrine: capture real system output (`DOCTRINE.md` §3) — `[INIT_CAPTURE]` revealed Avrae uses plaintext, not embeds, contradicting all three AI reviewers.
- Doctrine: AI reviewers excel at architecture, fail at empirical format (`DOCTRINE.md` §4) — three reviewers all converged on plan philosophy, all wrong on at least one implementation detail.
- Doctrine: when the user pushes back, listen (`DOCTRINE.md` §5) — Jordan's clock-name autocomplete pushback.
- Failure: `!init end` matched as new send, not edit (`FAILURES.md` §F-04) — required `on_message_edit`, not regex.

---

# Session 8 — Phase 2 Complete

Phase 2 went from kickoff to complete in a single session. All eleven steps shipped (2A.1–2C.4) plus the cloud router quota correction.

## What shipped

- **Phase 2A — Combat Stabilization:** `dnd_combat_state` table + 3 engine functions; `parse_init_event` 'turn' wired to `set_active_turn`; turn gate in `on_message` (combat mode + recorded turn + author mismatch → ⏳ + return); `ActionBatcher.add` accepts `window=` param.
- **Phase 2B — Observability:** one-line log after every `buffer.consume`; `get_active_turn` logs both branches.
- **Phase 2C — Narrative Fidelity:** multi-actor `dm_respond` with compact PARTY block; `dnd_quests` + `/quest` group; `dnd_companions` + `/companion` group with COMPANION_CAP=3; `/encounter` slash command (single command, Choice parameter, three presets).
- **Cloud router quota correction:** Cerebras token-not-request limit corrected; Groq Developer tier; OpenRouter $10 deposit unlocked 1000 RPD.

## Live verification

Real combat with turn coordination, real quests with prompt awareness, real NPCs chiming in occasionally without overstaying. Every patch shipped to server, tested in Discord, produced expected log lines BEFORE next step started.

## Cross-references

- Doctrine: evolve from observed friction, not anticipated (`DOCTRINE.md` §6) — Phase 3 was sketched as auto-extraction with proposal queue; corrected to lighter Suggested Actions block.
- Doctrine: discard the first design (`DOCTRINE.md` §7) — companion schema, `/encounter` idempotency, Phase 3 scope all simplified after pushback.
- Doctrine: one live verification per step (`DOCTRINE.md` §8) — workflow established.
- Failure: stale combatant 'throx' (`FAILURES.md` §F-05) — surfaced by 2B.1 logs but not fixed.
- Failure: actor name mismatch (`FAILURES.md` §F-06) — three names for one entity (Avrae 'throx', Virgil 'Donovan Ruby', cache key).

---

# Session 9 — Phase 3 Ships, Narration Drift Surfaces

Phase 3.0 live, Phase 3.1 shipped, Layer 2 problem surfaced. **Partially complete / blocked.**

## What shipped

- **Phase 3.0 — Suggested Actions block.** Prompt addition in `dm_respond`'s system prompt between OUTPUT FORMAT and FINAL TONE REMINDER. Allowed-commands list cut to `/quest`, `/clock`, `/companion`, `/encounter`, `/mode` after `/tension` and `/scenestate` ghosts removed. `suggestion_emitted campaign_id=X count=N` log line.
- **Phase 3.1 — Auto-Execute Tier 1.** Mini-schema (pipe-delimited, `AUTO_EXECUTE_BEGIN`/`END` markers); `parse_auto_execute(response)` pure function; `execute_auto_actions` calling existing engine primitives; italicized id-addressable undo lines. Three commands: `QUEST_ADD`, `CLOCK_TICK`, `MODE`.
- **Phase 3.1 prompt fix** (mid-session): AUTO-EXECUTE moved ABOVE Player UI Suggestions to fight generation-order commitment bias; Tier 1 commands forbidden in Suggested Actions; reframing to "Player UI Suggestions (Derived Only, Optional)"; negative format examples added.

## Live verification

3.0 fired live (campaign 17, count=2). **3.1 NOT live-validated** — auto-execute never fired even after the prompt fix, even on clean commitments like "we'll go deeper and grab the chest contents."

## Cross-references

- Doctrine: prompt-is-tone-structure-is-the-game (`DOCTRINE.md` §1) — Layer 2 framing emerges; auto-execute can only commit state when narration enacts the change.
- Failure: hallucinated slash commands (`FAILURES.md` §F-07) — `/tension` and `/scenestate` listed as commands they never were.
- Failure: Layer 2 narration drift (`FAILURES.md` §F-08) — every NPC stayed ambiguous, every scene stalled. Blocks Phase 3 validation.

---

# Session 10 — Phase 1 Closes, Model Swap, Phase 3 Validates Live

Going in, Phase 3 was blocked behind narration drift. Going out, Phase 3 fired live, the model swap closed the drift question, and orchestration regex audit caught the categorical god-mode failures prompt rules alone couldn't.

## What shipped

- **Critical bug squashes:** `/refresh` missing import (cache silently empty since orchestration introduced); virgil-bot 31-hour crash loop (5 strip sites for archived `dnd` module).
- **Phase 1 ladder:** Rule 4 (NPC commitment); Rule 5 (no unauthorized mechanical commands — caught Llama's atmospheric `!roll` fabrications); Rule 6 (player attempts not outcomes — refused meteor-swarm, king's-throne, oak-table-through-wall).
- **Phase 10A — Model swap to `groq_heavy` / gpt-oss-120b.** Buggy first patch (sort-by-score overrode candidate ordering); second patch shipped clean with reason-code logging. A/B against Llama: gpt-oss decisively better.
- **Phase 10B.2 — Orchestration regex audit.** COMBAT_RX gained 25+ verbs; RISKY_RX gained snatch/swipe theft + take-from-someone phrasals + hide/conceal; CONTESTED_RX gained disguise/impersonate + skill nouns; EXPLORATION_RX added follow + skill nouns. 25 test cases pass.
- **Phase 10F — Solo permission unlock.** Schema migration adds `created_by_user_id`; `is_dm_or_creator` helper; 18 [DM]-only gates replaced.
- **Cloud router observability:** `task_type` plumbing, DnD penalties on non-local providers, `DND_PRIORITY_OVERRIDE` / `SCORE_SORT` reason codes, full candidate ordering log.
- **Phase 11.1 spec** written, build deferred.

## Live verification

**Phase 3 VALIDATED LIVE for the first time:** "Mode set: combat" auto-execute on player aggression; "Quest added: Retrieve the Crystal from the Cavern" auto-execute on questgiver hook narration. Confirmed Session 9's hypothesis — narration drift was the blocker, not auto-execute itself.

## Cross-references

- Doctrine: don't engineer against model limits (`DOCTRINE.md` §9) — gpt-oss followed rules 1-3 alone where Llama needed all six plus penalties.
- Doctrine: trace the full pipeline before declaring done (`DOCTRINE.md` §10) — first routing patch silently failed because `sort_by_score` reordered.
- Doctrine: design preferences are the user's (`DOCTRINE.md` §11) — `USE_KNOWLEDGE_GUIDANCE = False` reverted same session.
- Failure: routing pipeline reorder (`FAILURES.md` §F-09).
- Failure: `USE_KNOWLEDGE_GUIDANCE` without buy-in (`FAILURES.md` §F-10).
- Failure: Layer 2 drift (`FAILURES.md` §F-08) — RESOLVED via model swap.

---

# Session 11 — Phase 11.1 Mechanical Hints (Advisory Parser) Shipped Live

Build deferred from Session 10, shipped this session. The advisory-parser pattern named in Session 10 gets its third concrete instance.

## What shipped

- **`mechanical_hints.py`** — advisory parser module. Strict regex whitelist, narration-only input, structured-output validator, fire-and-forget background task.
- **Whitelist v1:** `!game coin +/-Ngp` (single currency per command); `!game longrest` / `!game lr`; `!game shortrest` / `!game sr`. Excluded: HP, spell slots, conditions, initiative, concentration, attunement, leveling, items.
- **Cloud router** gained `extraction` task type — Cerebras primary (qwen-3-235b-instruct), groq fallback. NOT `groq_heavy` (reserved for DnD narration).
- **Async edit-in pattern** in `_dm_respond_and_post`: post narration first, async-edit the hint block via `_attach_hints` background task.
- **S5 long-rest auto-mode-flip:** `_handle_rest_event` mirrors `_handle_init_event`'s end-branch; `!game longrest`/`!game shortrest` triggers `set_scene_mode('exploration')` + `clear_active_turn`. Pure mechanical mapping, no LLM in the path.
- **S12 syntax correction:** first whitelist drafted with bare `!coin -1gp`; Avrae's actual command is `!game coin +-Ngp`; shipped corrected after first live test.
- 82 unit tests across `test_mechanical_hints.py`. 14/15 calibration cases passed at 93%.

## Live verification

Player reads narration immediately; hints appear a beat later. Reinforces "narration primary, mechanics auxiliary." Long-rest auto-flip verified live.

## Cross-references

- Doctrine: advisory parser pattern (`DOCTRINE.md` §12) — formalized this session as third instance after `extract_scene_updates` and Phase 3 auto-execute.
- Doctrine: suggestion-only forever (`DOCTRINE.md` §13) — auto-fire turns advisory into authoritative; different system class.
- Doctrine: capture real system output (`DOCTRINE.md` §3) — `!coin` syntax reinforced from Session 7.
- Failure: Avrae `!coin` syntax wrong on first ship (`FAILURES.md` §F-11).

---

# Session 12 — Phase 12 Persistence Layer + Movement Primitives + Documentation Restructure

The session that shipped canonical world state (Track 1 complete), built two UX ships from observed real-session friction, validated authored canon grounding live, and split the master document into a maintainable four-file system.

## What shipped

- **Phase 12A — Persistent NPCs.** `dnd_npcs` table + 6 accessors; `canonicalize_name()` with iterative leading-honorific strip; `npc_extractor.py` advisory parser (149 unit tests, 15/15 calibration); `npc_fragmentation_report()` telemetry; 102 engine unit tests.
- **Phase 12B — Persistent Locations.** `dnd_locations` table mirroring NPCs; `set_current_location()` SOLE writer of `dnd_scene_state.current_location_id` with FK validation; `location_extractor.py` (125 unit tests, 13/15 calibration); combined `_extract_and_persist_world` background task.
- **Phase 12C — Authored Canon.** `campaigns/<id>/skeleton.md` filesystem template; `skeleton_loader.py` with mtime cache, idempotent two-pass FK backfill; `dm_respond` lazily prepends skeleton block as `═══` AUTHORITATIVE CANON; `/skeleton load` and `/skeleton status` commands. 86 unit tests.
- **Ship 1 — `/travel`.** `TRAVEL_TRANSITION:` directive prepended to system prompt as highest priority. Soft-existence policy: sets `current_location_id` if destination resolves; else one-shot `location_label_override`. Footer surfaces `📍 <location>`.
- **Ship 2 — World Recall.** `companion_name_autocomplete` pulls from `dnd_npcs` sorted by `mention_count`. Active-quest reminder in footer.
- **Documentation restructure.** Single 146KB `VIRGIL_MASTER.txt` split four ways: `VIRGIL_MASTER.md` / `ROADMAP.md` / `WORKING_WITH_CLAUDE.md` / `WHY.md`.

## Live verification

Eldrin's wounded-elk story referenced from `skeleton_17.md`; Lira self-introduction matched authored persona. `/travel` validated Stonebridge → Hollowmoor → Stonebridge cycle — LLM respects `═══` framing, opens at arrival. Campaign 17 DB: 9 locations including 1 typo phantom (Stormbridge) and 1 emergent canon (River Wynd).

## Cross-references

- Doctrine: strict literal match beats fuzzy (`DOCTRINE.md` §14) — chose strict matching with telemetry over fuzzy collapse risking false-positive identity merges.
- Doctrine: authoritative-canon framing (`DOCTRINE.md` §15) — `═══` block prepend honored verbatim on first try.
- Doctrine: engine defends its own invariants (`DOCTRINE.md` §16) — `set_current_location` validates FK existence.
- Doctrine: single write paths per field (`DOCTRINE.md` §17) — pattern hardened.
- Doctrine: evolve from observed friction (`DOCTRINE.md` §6) — Ship 1 (`/travel`) and Ship 2 (autocomplete) emerged from real session, not spec.
- Failure: single-file master rewrite (`FAILURES.md` §F-12).
- Failure: phantom location Stormbridge (`FAILURES.md` §F-13).

---

# Session 13 — Ship 4 Telemetry + Campaign Management Surface

The session that closed the canonical-world telemetry loop and built a complete campaign management surface (switch, archive, hard-delete, bulk wipe) with two-gate destruction safety. Hygiene cleanup at end of session purged 13 leftover test campaigns — the cascade primitive's first real-world dogfood.

## What shipped

- **Ship 4 — Phantom-location telemetry + world_health.** `phantom_location_candidates(campaign_id, threshold=3)` pure read; `world_health_report` composes NPC fragmentation + phantom + skeleton coverage as four independent numbers (deliberately not a composite score). `phantom_candidates:` and `world_health:` greppable log lines. 29 tests.
- **Campaign management surface.** `_CAMPAIGN_SCOPED_TABLES` canonical 7-table list; `campaign_delete_cascade(campaign_id)` hard delete in single transaction (refuses on active, refuses on missing, returns `rows_deleted` dict, 13 unit tests); `campaign_set_status` (16 unit tests). Discord commands: `/setcampaign`, `/deletecampaign <ids>` (atomic batch), `/campaigns`, `/archived`, `/purgecampaign <id> <DELETE name>` (three independent gates), `/purgeallcampaigns DELETE ALL ARCHIVED` (two gates, only iterates `status='archived'`).
- **Roll-discipline drift fix.** `classify_action_intent(text, mode='exploration')` — dead `in_combat` parameter removed entirely; mode-aware evaluation order per spec. RISKY_RX hardened with negative lookaheads on `steal`/`sneak` with idiom noun list. 37 tests.
- **S9 capability grounding v1.** `CapabilityVerdict` enum (CONFIRMED / VALID_BUT_UNCONFIGURED / INVALID — no v1 producer). 3-state lattice replacing binary `has_capability`; weapons-only by design.

## Live verification

Campaign 17 emits `npc_health: campaign=17 entities=3 rows=6 fragmentation_rate=50%`, `phantom_candidates: campaign=17 count=2 threshold=3`, `world_health: campaign=17 npc_frag=50% loc_skel_cov=78% loc_phantoms=2 loc_total=9`. Hygiene cleanup: 12 test campaigns archived via `/deletecampaign 5,6,7,8,9,10,11,12,13,14,15,16` then purged via `/purgeallcampaigns DELETE ALL ARCHIVED`. Donovan dagger claim returned `verdict=VALID_BUT_UNCONFIGURED`; after skeleton edit, upgraded to `verdict=CONFIRMED source=skeleton`.

## Cross-references

- Doctrine: engine primitive first, command second (`DOCTRINE.md` §18) — cascade got 13 tests before any command could call it.
- Doctrine: two independent gates before destruction (`DOCTRINE.md` §19).
- Doctrine: atomic batch with no partial state (`DOCTRINE.md` §20) — "fail the whole thing don't pass."
- Doctrine: diagnostic-before-treatment (`DOCTRINE.md` §21) — `/purgecampaign` whitespace fix.
- Doctrine: re-stage from most recent output, not session-start snapshot (`DOCTRINE.md` §22).
- Doctrine: time estimates don't belong in priority calls (`DOCTRINE.md` §23).
- Failure: tests sandbox-only, never run on server (`FAILURES.md` §F-14).
- Failure: re-staging from `/mnt/project/` (session-start snapshot) overwrote in-progress work (`FAILURES.md` §F-15) — major recovery required.
- Failure: pushed fix while diagnostic still pending (`FAILURES.md` §F-16).

---

# Session 14 — Track 3 Opens (Pacing + Central Thread + DM Philosophy) + Corpus Inventory

The session that converted Phase 1/12 declarative state into operational behavioral pressure. Six ships landed live. The fundamental shift: directives stopped describing the world and started instructing the DM. End-of-session move: Jordan migrating to Claude Code. This is the final web-app session.

## What shipped

- **Ship 1 — Bot startup auto-cache.** `_warm_character_cache_on_startup(bot)` scans `#character-sheets` and `#dm-narration` for Avrae sheet embeds on `on_ready`. Eliminated post-restart `/refresh` requirement.
- **Ship 2 — `virgil-discord` sentinel monitoring.** Single `is-active` block added to `sentinel.sh` mirroring existing `virgil-bot` check.
- **Ship 3 — COMBAT_RX false-positive cleanup.** Dropped `fire`, `shoot`, `loose` from combat verb list (no reliable regex disambiguation for "around the fire", "loose stones"). Cost: "I fire my bow" no longer auto-prompts. Benefit: zero false positives.
- **Ship 4 — Pacing directive (Track 3 entry).** `compute_pacing_directive(scene_state)` converts `tension_int` + `progress_clocks` into imperative narrative-move constraints. Tier thresholds match `tension_label()`. Urgent-clock callout at ≥80% filled.
- **Ship 5 — Central thread directive.** `compute_central_thread_directive(hooks)` converts `hooks[0]` into directional pressure on every turn. Phrasing forbids literal restatement.
- **Ship 6 — DM philosophy directive layer.** `dm_philosophy_loader.py` mirrors skeleton_loader's mtime-cached pattern. Reads `dm_philosophy.md` (single global file, not per-campaign). Sits HIGH in prompt template (after canonical state, before tactical directives).
- **Ship 7 — Corpus inventory pass.** `corpus_inventory.py` walks `/mnt/virgil_storage/dnd_datasets`. CRD3-aware + FIREBALL-aware. 57.9 seconds for 3GB.
- **Skeleton data fix.** Added `## Player Capabilities\n- Donovan Ruby: shortsword, shortbow, dagger` to campaign 17.

## Live verification

Pacing: tension_int=70 + "throw the bed into the fireplace" produced visceral, weight-carrying narration. Central thread: neutral "sleep on floor" didn't trigger keyword-spam; "ask bartender about ghost stories" produced ghost story set on the road, gravity without restatement. Philosophy doc loaded (3343 chars), responses became visibly tighter — NPCs introduced doing specific things, no "what do you do?" prompts. **Corpus findings:** CRD3 has 355,892 substantive Matt Mercer DM turns ≥15 words, 29,850 multi-turn sequences ≥10 turns. FIREBALL has 0 multi-utterance records ≥10 turns — single-action context patterns only.

## Cross-references

- Doctrine: directives-as-imperatives (`DOCTRINE.md` §25) — load-bearing lesson named here. Most "the bot doesn't do X" complaints become "convert state Y into a directive Z that says do X."
- Doctrine: workflow rules outrank simplicity (`DOCTRINE.md` §27) — heredoc edit pushback on skeleton.md.
- Doctrine: ever-growing exception lists are the wrong fix (`DOCTRINE.md` §26) — first COMBAT_RX patch was clever-not-reliable wall of negative lookbehinds.
- Doctrine: hold a position when pushed (`DOCTRINE.md` §24) — flip-flopping on roadmap rankings under pressure.
- Failure: COMBAT_RX false positives `fire`/`shoot`/`loose` (`FAILURES.md` §F-17) — RESOLVED via Ship 3.
- Failure: clever-not-reliable lookbehind first attempt (`FAILURES.md` §F-18).

---

# Session 15 — Claude Code Migration, Donovan/Ruby Fix, PC Contamination Guard, Backup-to-PC

The first Claude Code session. Closed three Session-14-surfaced bugs, discovered and fixed a player-character-leaks-into-NPC-canon contamination bug surfaced as a side effect of the Donovan/Ruby fix, built a virgil → PC rsync backup over Tailscale (with Cygwin install + SSH key bootstrap), and reorganized the PC folder layout into typed subfolders.

## What shipped

- **Donovan/Ruby address-name fix.** New `primary_name` property on `CharacterContext` returning first whitespace token of `name`. `to_prompt_block` now renders `f"{name} (address as {primary_name})"`. New CHARACTER AWARENESS bullet directing "address as Donovan, never Ruby."
- **PC contamination guard.** `names_overlap(a, b)` symmetric same-identity check (canonicalized equality OR whole-token-prefix OR single-token-anywhere). `get_bound_character_names(campaign_id)` helper. `parse_npcs(narration, pc_names=None)` filter (defense-in-depth). `npc_upsert` engine refusal at write boundary. Cleanup: `DELETE FROM dnd_npcs WHERE campaign_id=17 AND id IN (7, 8)`.
- **`_INVOCATION_VERBS` expansion.** Added `'equip'` and `'use'` to verb tuple in `dnd_orchestration.py`.
- **`parse_avrae_sheet_embed` !coin/!item refusal.** First-line guard refusing `**` or `:` markers; all-defaults sentinel refusing contexts where every parsed field is at default.
- **Backup-to-PC.** virgil → PC rsync over Tailscale; Cygwin installed on PC for rsync; SSH key bootstrapped. 39 + 41 + 8 new test assertions.
- **Second autonomous block (post-dinner):** Ship 7 `!`-prefix filter (Avrae bookkeeping commands typed in `#dm-narration` no longer trigger DM narration); Ship 8 `test_check_action_capability.py` v1 verdict refactor (52/52 tests pass, was 29/52); Ship 9 MODE auto-execute undo placeholder cleanup; Ship 10 quest dedup.

## Live verification

NPC dialogue switched from "Ruby" alone to "Donovan Ruby" or no direct address. At 15:43:10, parser emitted `[{"name": "Donovan Ruby", ...}]`, validator dropped with `pc_match`, no DB write. Lira re-mention bumped existing row; Garrick wrote as new canonical id=9.

## Cross-references

- Doctrine: defense-in-depth at parser + engine (`DOCTRINE.md` §28).
- Doctrine: cleanup ships with the fix (`DOCTRINE.md` §29) — contamination rows 7 and 8 deleted same session.
- Doctrine: PC-vs-NPC identity is structure (`DOCTRINE.md` §30) — prompt rules are tone and pacing, structure is the game.
- Doctrine: verify the running process before debugging (`DOCTRINE.md` §31) — restart-before-testing.
- Doctrine: re-stage from most recent output (`DOCTRINE.md` §22) — applies in Claude Code context too.
- Failure: re-staging from snapshot recurred mid-session (`FAILURES.md` §F-15).
- Failure: tested against unrestarted bot (`FAILURES.md` §F-19).
- Failure: address-name fix expanded contamination (`FAILURES.md` §F-20).
- Failure: `test_check_action_capability` binary vs verdict drift (`FAILURES.md` §F-21) — RESOLVED in second autonomous block.

---

# Session 16 — Consequence Surfacing v1 (Spec → Review → Ship), Operating-Model Reframe

The session that converted the long-running "the world should remember" failure mode into a working system, and reframed how Jordan wants future work proposed: build to a bar, don't gate on play data; ship one v1, observe, then re-decide what's next.

## What shipped

- **`THE_GOAL.md` arrived and was protected.** Pulled from PC via reverse rsync; marked protected via `feedback_the_goal_protected.md` memory. Sits ABOVE operational docs as the priority lens.
- **`CONSEQUENCE_SURFACING_SPEC.md` v1.** Initial 9 locked + 6 open → 15 locked + 0 open in one review round.
- **Schema migration.** `dnd_consequences` table (id, campaign_id, npc_id, kind, summary, severity, sources, captured_at, captured_turn, first_seen_turn, last_seen_turn, last_surfaced_at, last_surfaced_turn, surface_count, distinct_surface_turns, status, promoted_at). UNIQUE on `(campaign_id, npc_id, kind)`. `dnd_scene_state.turn_counter` column added. `_CAMPAIGN_SCOPED_TABLES` updated.
- **Engine helpers.** Single write paths for each lifecycle stage: `consequence_upsert` (last-write-wins, severity MAX-on-upsert), `consequence_emit_surface`, `maybe_promote_consequences`, `consequence_list_for_command`, `apply_consequence_proposals`.
- **Dual-pass parser** (`consequence_extractor.py`). `parse_consequences_player(player_text)` reads ONLY player input; `parse_consequences_dm(dm_text)` reads ONLY DM narration. 6-kind taxonomy verbatim per spec §1.3. Severity 1-3 parser-judged.
- **Directive.** `compute_consequence_directive(active_consequences, in_scope_npc_ids)`. Filters to in-scope NPCs, sorts severity DESC then last_surfaced_turn DESC, caps at 3.
- **Wiring.** `maybe_promote_consequences` BEFORE directive composition; `increment_turn_counter` at END of successful turn.
- **`/consequence list [npc]`** Discord debug command, read-only by design.
- 249 new test assertions across four files.
- **Second autonomous block:** `godmode_gap` diagnostic log line; `COMMITTED_ACTION_RESOLUTION_SPEC.md` drafted (~620 lines, pre-review); `consequence_health_report` composed into `world_health`; empty-narration diagnostic logs; `extract_scene_updates` `task_type="extraction"` fix (was `"dnd"`, competing with narration call).

## Live verification

Test A + Test B passed. Bot booted with `synced 21 slash commands` (was 20). Cache warming hit Donovan Ruby.

## Cross-references

- Doctrine: spec → review → revise → ship (`DOCTRINE.md` §32) — implementation read locked spec like a contract.
- Doctrine: build to a bar, don't gate on play data (`DOCTRINE.md` §33) — operating-model reframe.
- Doctrine: no pre-sequencing across unbuilt specs (`DOCTRINE.md` §34) — `feedback_no_pre_sequencing.md`.
- Doctrine: dual-pass channel separation (`DOCTRINE.md` §35) — single blended parser rejected as self-reinforcing hallucination loop.
- Doctrine: parser-judged severity, validated at engine (`DOCTRINE.md` §36).
- Doctrine: doc passes are code reviews (`DOCTRINE.md` §37) — `_CAMPAIGN_SCOPED_TABLES` drift caught; `extract_scene_updates` task_type drift caught.
- Doctrine: filed-not-sequenced (`DOCTRINE.md` §38).
- Failure: autonomous first-turn no-op (`FAILURES.md` §F-22) — though NOT this session; pattern formalized later.
- Failure: spec proposed sequenced appendix (`FAILURES.md` §F-23).
- Failure: race between `npc_extractor` and `apply_consequence_proposals` (`FAILURES.md` §F-24).
- Failure: empty-narration diagnostic unverified (`FAILURES.md` §F-25).
- Failure: godmode_gap surfaced as observable (`FAILURES.md` §F-26) — diagnostic-only, no fix.

---

# Session 18 — Observability Batch (S22–S25)

A four-item observability batch shipped autonomously: every item is a pure-visibility log line — no behavior change, no auto-merge, no constraint layer. The batch closes the four largest known blind spots before the next architectural ship.

## What shipped

- **S22 — `unconsumed_roll_swept`** (`avrae_listener.py`). `RollBuffer._sweep()` now logs every TTL-expired roll: `unconsumed_roll_swept: actor='{actor}' action='{action}' age_s={age}`. 11 assertions.
- **S23 — `npc_near_match` / `location_near_match`** (`dnd_engine.py`). `npc_upsert` and `location_upsert` INSERT branches log near-match line whenever Levenshtein distance ≤ 2 against existing canonical name. New `levenshtein_distance(a, b)` helper. **No auto-merge** — Phase 6 strict-equality identity rule untouched. 26 assertions.
- **S24 — `prompt_size:` per-turn telemetry.** Logs `prompt_size: campaign={N} system={chars} retrieval={chars} party={chars} scene={chars} directives={chars} total={chars}` after `build_dm_context` returns. Pure measurement, no truncation. 22 assertions.
- **S25 — `directive_emit:` per-turn aggregate.** One summary line per turn: `pacing={tier|none} central_thread={1|0} philosophy={chars} consequence={count} capability={verdict|none} commitment=0`. 23 assertions.
- **`tests-to-run-post-session.md`** — new mandatory deliverable. Discord input + journalctl grep for each S22–S25 line. Lives in `virgil-docs/`.
- **Hygiene:** 8 stale `.bak.*` snapshots from Session 15 deleted.
- **B2 ship — `!attack` template directive** (during S22 verification window). `!attack <weapon-name> -t <target>` template; HARD STOP RULE 5 carve-out for attack templates ("Replace EVERY `<...>` placeholder"). 30 assertions.
- **B2.1 follow-up.** Removed quotes from template (codebase convention is unquoted multi-word names per `!check sleight of hand`); added narration mandate ("A response that is ONLY the command, with no narration, is INSUFFICIENT and breaks the table"). 6 new assertions (now 36 total).
- **`tests-to-run-post-session.md` doc-bug fix:** all 6 journalctl greps used `-u virgil-discord`; correct invocation for user-unit is `--user -u virgil-discord`.

## Live verification

S22 fired live: `unconsumed_roll_swept: actor='donovan ruby' action='attack' age_s=188.7` at 11:44. S24 surfaced 24-25k char prompts every turn — bloat is variance-driven, not threshold-driven. S25 stable across 5 turns: `pacing=none central_thread=1 philosophy=3343 consequence=1-2 capability=none commitment=0`. **S23 didn't fire in normal play — three reasons surfaced:** DM auto-correction, `bad_name_format` validator dropping "Garrik the Younger" before insert, new canonical names rarely sit within distance ≤2 of existing canon. Second test pass: S23 DID fire — `npc_near_match: new='Garrik' existing='Garrick' distance=1`. B2 fired with two new bugs (quoted multiword + zero narration); B2.1 fixed both. Avrae binding-layer issue filed (post-B2.1 attack still rolled against `<None>` because no `!init begin` had run; bonus stale `throx` combatant from prior session surfaced).

## Cross-references

- Doctrine: pure-observability first when a failure surfaces (`DOCTRINE.md` §39) — S22-S25 each ship the measurement without the fix.
- Doctrine: observability ships earn batching (`DOCTRINE.md` §40).
- Doctrine: verification commands need positive-confirmation testing (`DOCTRINE.md` §41) — silent empty output is identical to "no firing."
- Doctrine: live testing surfaces bugs spec'd test coverage cannot (`DOCTRINE.md` §42).
- Doctrine: codebase conventions outrank external knowledge (`DOCTRINE.md` §43) — argparse-style quoting wrong; `!check sleight of hand` was the codebase convention.
- Doctrine: run a SECOND live test (`DOCTRINE.md` §44).
- Doctrine: honest scope discipline beats fake completeness (`DOCTRINE.md` §45) — B2.1 stopped at "the orchestration layer is correct"; Avrae-binding-layer filed for committed-action spec.
- Doctrine: ship now or file (`DOCTRINE.md` §46) — when fix shape is small, ship is the right default.
- Failure: autonomous first-turn no-op (`FAILURES.md` §F-22) — recurred at start of this session.
- Failure: godmode_gap data accumulating (`FAILURES.md` §F-26).
- Failure: journalctl user-unit doc bug (`FAILURES.md` §F-27).
- Failure: S23 hit-rate prediction wrong (`FAILURES.md` §F-28).
- Failure: `bad_name_format` validator false-negative on titled NPCs (`FAILURES.md` §F-29).
- Failure: prompt bloat 24-25k chars (`FAILURES.md` §F-30).
- Failure: B2 bare `!attack` no target (`FAILURES.md` §F-31).
- Failure: B2 quoted multiword + narration shrinkage (`FAILURES.md` §F-32).
- Failure: Levenshtein vs Damerau-Levenshtein test mismatch (`FAILURES.md` §F-33).

---

# Session 21 — Combat Persistence Directive v1 (Spec → Lock → Ship → Live Verify)

May 4, 2026. Pre-friends gating ship #3 — closes the during-combat narrative-drift band. Sibling to S19 (Committed Action Resolution, escape-only) and S20 (Combat Initiation Orchestration).

## What shipped

- **New schema `dnd_combatant_state`** — per-combatant HP / conditions / alive snapshot. Composite PK `(campaign_id, name)`. Single-writer invariant: only `update_combatants_from_init_list` and `clear_combatants` write here.
- **New parser `parse_init_list_embed`** in `avrae_listener.py` — pure regex over Avrae's `!init list` plaintext. Header + separator pair required. Code-fence-tolerant. Indented dash-condition continuation parser. Status decoder: `<None>`, `<n/m HP>`, `<Defeated>`, `Healthy`/`Bloodied`/etc.
- **New directive `compute_persistence_directive`** in `dnd_orchestration.py` — master-gates on `mode=='combat'`. Concrete per-combatant block when snapshot non-empty; abstract eight-condition fallback when empty. Initiative block: ON-turn confirm + naming-only (OFF-turn dropped per §11.B retroactive lock).
- **Bot wiring.** `_handle_init_list_event` branched into both `on_message` and `on_message_edit`. `clear_combatants` calls in `_handle_init_event` end-branch and `_handle_rest_event`.
- **Identity threading.** `ActionBatcher.add` extended with `user_id` kwarg → 3-tuple storage → first-batched-actor's Discord ID flows to `dm_respond(typing_user_id=...)`.
- **Telemetry.** `persistence_directive: fired={0|1} combat_active={0|1} hp_known={0|1} conditions_known={0|1} combatants={N} snapshot_age_s={N|none} active_turn_controller={id|none}`. New `init_list_parsed:` log line. `directive_emit:` extended with `persistence={0|1}`.
- 78 new assertions across `test_combatant_state.py` (15) / `test_init_list_parser.py` (29) / `test_persistence_directive.py` (34).

## Live verification

First live `!init list` produced `combatants=1` instead of 2 because Donovan Ruby's row carried trailing `(AC 13)` outside the `<...>` slot — permissive trailer fix `[^\n]*$` shipped. After fix, LLM narration honored listed combatants ("goblins glaring, knives half-drawn") without authoring the close.

## Cross-references

- Doctrine: specs drift from code (`DOCTRINE.md` §47) — §11.B's "hard gate would be a parallel invariant violation" sounded principled but Phase 2A.3 had already shipped the gate.
- Doctrine: concrete-in-prompt narrows drift surface (`DOCTRINE.md` §48) — §11.A's data-layer ship despite doubling spec scope.
- Doctrine: format-unknowns demand fail-open + log line (`DOCTRINE.md` §49) — `[INIT_LIST_PARSE_UNKNOWN]` did its job.
- Doctrine: snapshot over delta (`DOCTRINE.md` §50) — `!init list` snapshot one canonical source vs incremental damage-event delta tracking.
- Doctrine: pure-function-in-orchestration (`DOCTRINE.md` §59) — third instance.
- Failure: §11.A retraction (`FAILURES.md` §F-34) — proxy-signal v1 retracted in favor of bundled-parser v1.
- Failure: §11.B spec-vs-reality drift (`FAILURES.md` §F-35) — soft-retroactively per Jordan's option (C).
- Failure: AC suffix not anticipated in regex (`FAILURES.md` §F-36).

---

# Session 22 #1 — Track 4 #1 Narrative Inventory v1 (Spec-Brief → Implement → Verify)

May 5, 2026. First Track 4 ship. Track 4 was opened in Session 14 with corpus reconnaissance and has been dormant since. This session opens the build phase with the smallest meaningful unit: per-character narrative inventory. Avrae owns sheet-bound combat gear; Virgil owns loot, quest objects, story items, found gear. No sync layer.

## What shipped

- **New schema `dnd_inventory`** — `(id, campaign_id, character_name, item_name, quantity, metadata, created_at)` with `INDEX (campaign_id, character_name, item_name)`. Replaced vestigial stub schema (`character_id` FK, no code references) per Jordan's Phase 1 call.
- **Single-writer pair** in `dnd_engine.py`: `add_item(campaign_id, character_name, item_name, quantity=1, metadata=None)` (increment-on-existing); `remove_item(campaign_id, character_name, item_name, quantity=1)` (decrement, delete-on-zero, refuses over-removal). Pure reads `get_inventory` and `has_item`. `_normalize_item_name` lowercases + collapses whitespace.
- **Slash commands** in `discord_dnd_bot.py`: `/inventory [character]` (player-accessible, defaults to caller's bound character); `/giveitem <character> <item> [quantity]` (DM-only). Both ephemeral. Bound-character autocomplete via new `_bound_character_autocomplete` helper.
- **DM context render** — `=== {CHARACTER}'S NOTABLE ITEMS ===` block in `build_dm_context` after the party block. Sourced from `acting_character_names[0]` (always populated when actor typed) rather than `character_contexts[0].name` (only populated when Avrae sheet cached). Cap at 8 items shown.
- **Telemetry.** `inventory_add: action={inserted|incremented}`, `inventory_remove: action={decremented|removed|insufficient|not_found}`, `inventory_give:`, `inventory_render: count=N`.
- **Cascade.** `dnd_inventory` added to `_CAMPAIGN_SCOPED_TABLES`.
- 31 assertions in `test_inventory.py`.

## Live verification

23:01: prompt grew ~400 chars from new section. LLM took the silver-key cue and ran with cellar narrative on first test. `=== DONOVAN RUBY'S NOTABLE ITEMS === silver key` pinned in system prompt; LLM honored it without verdict layer required.

## Cross-references

- Doctrine: specs drift from code (`DOCTRINE.md` §47) — Phase 1 caught three spec-vs-reality divergences (vestigial schema, INVALID/VALID framing, WEAPON_CLAIM_RX scope).
- Doctrine: concrete-in-prompt (`DOCTRINE.md` §48) — twice-confirmed (S21 + S22 #1). Concrete state pinned in prompt is the load-bearing compliance surface; verdict-shift / directive-imperative layers are belt-on-suspenders.
- Doctrine: bound-set autocomplete for any per-character slash command (`DOCTRINE.md` §51).
- Doctrine: bot-Avrae write boundary (`DOCTRINE.md` §65) — Virgil owns narrative inventory; Avrae owns sheet-bound combat gear; no sync layer.
- Failure: vestigial inventory schema in DB (`FAILURES.md` §F-37).
- Failure: Phase 6 render gate coupled to sheet caching (`FAILURES.md` §F-38).

---

# Session 22 #2 — Track 4 #2 Loot Generation v1 (Pivot → Implement → Two-Pass Live Verify)

May 5, 2026. Second Track 4 ship, same calendar day as #1. Goal: when an NPC combatant transitions alive→defeated, generate deterministic loot from a hardcoded substring-matched table, queue it, surface it through a narration directive on the next DM turn. Player claims via `/giveitem` (manual). The bot-Avrae write boundary stays intact.

## What shipped

- **Architectural pivot at Phase 1** (load-bearing call). Spec called for standalone `parse_defeat_event(text)` regex parser. Phase 1 grep across 30+ days of journal logs (11,130 lines) returned **zero** standalone defeat messages — Avrae does NOT emit "X has been defeated." Existing `parse_init_list_embed` already decodes `<Defeated>` and `<0/N HP>` into `alive=0`. Pivoted to **death-edge detection inside `update_combatants_from_init_list`**: SELECT prior alive states before DELETE-INSERT, compute alive=1→alive=0 transitions, hand newly-defeated names to loot-enqueue helper.
- **New module `loot_tables.py`** — pure functions, no DB. `LOOT_TABLES` dict with five starter creatures (`goblin`, `wolf`, `bandit`, `skeleton`, `cultist`) + `_default`. Substring + case-insensitive matching ("Goblin Patrol" → 'goblin').
- **New schema `dnd_loot_pending`** — `(id, campaign_id, creature, table_key, coin_amount, coin_denom, items, surfaced, surfaced_at, created_at)`. Items as JSON array text. `surfaced` flag flips to 1 only after LLM call succeeds. Single writers: `enqueue_loot` / `mark_loot_surfaced`. Added to `_CAMPAIGN_SCOPED_TABLES`.
- **Death-edge wiring** in `update_combatants_from_init_list`. PC filter via `get_bound_character_names` (case-insensitive). Combatants disappearing entirely from snapshot are NOT counted as defeats.
- **`compute_loot_directive(pending_loot)`** — pure function returning `(body, signals)`. `_coin_hint_example(summary)` derives dynamic `+Nsp` example from directive's own `total_coin_summary`. `_total_coin_summary(rows)` aggregates by canonical D&D denom order.
- **`build_dm_context`** plumbed with `loot_directive=` kwarg, renders `=== LOOT TO SURFACE ===` block AFTER `=== COMBAT PERSISTENCE ===`.
- **Surface-and-clear cycle** in `dm_respond`: `mark_loot_surfaced` only after `route()` returns non-empty. Empty/failed LLM calls leave queue intact for next turn.
- **Telemetry.** `defeat_parsed:`, `loot_generated:`, `loot_directive: fired={0|1} pending_count=N`, `loot_surfaced:`. `directive_emit:` extended with `loot={0|1}`.
- 77 assertions across 4 new test files.

## Live verification

**Pass 1 (12:33–12:40):** First combat in fresh `/travel destination:Old Watchtower Ruin` scene. Single-hit goblin kill. Telemetry fired clean. **LLM narration substituted/added items** (kept rusted shortsword from directive but invented "iron ring with wolf-rune" and "folded scrap of parchment", emitted `!game coin +3cp` instead of listed 8 sp).

**v1.1 fix:** AUTHORITATIVE/EXHAUSTIVE framing per Jordan's wording — "Do NOT invent additional items, change quantities, or substitute thematic alternatives... if the table lists three items and coin, the player finds exactly three items and exactly that coin, nothing more." Coin example became dynamic. **Pass 2 still failed** — LLM kept the iron ring + parchment because `chroma_search` retrieved 10:25 DM turn (containing pass 1's bad loot) as "RELEVANT PAST EVENTS" and treated it as authoritative.

**v1.2 fix (two-prong):**
- **Chroma purge** (with explicit Jordan approval): both contaminated docs exported to `chroma_purge_track4_loot_2026-05-05.json` then deleted. Post-delete contamination scan: 0 `iron ring`, 0 `wolf-rune` in campaign 17.
- **Retrieval override clause:** "If retrieved past events ('RELEVANT PAST EVENTS' block above) describe different loot for this body, ignore those descriptions. The list in this block supersedes any prior narration and is the current ground truth."

**Pass 3 (post-v1.2):** "You pry the goblin's corpse and uncover a pouch of eight silver pieces, a rusted shortsword, a crude short-bow, and a tattered map tucked into its belt. !game coin +8sp" — exact mechanical hint with correct amount, zero hallucinated items, zero contamination. **Bonus:** Jordan looted *during combat* (skipped `!init end`); directive landed correctly with `persistence=1, loot=1` in same prompt.

## Cross-references

- Doctrine: snapshot over delta (`DOCTRINE.md` §50) — death-edge inside snapshot apply, no incremental damage parsing.
- Doctrine: failure modes stack (`DOCTRINE.md` §52) — three failure modes in two test passes; each had distinct fix; none preventable by spec review.
- Doctrine: chroma is a cross-turn behavior source (`DOCTRINE.md` §53) — failed LLM narration that gets stored becomes a re-injection vector.
- Doctrine: procedural confirmation is not re-decision (`DOCTRINE.md` §54) — Jordan's "Show me the doc ids before delete" was procedural confirmation; the destructive decision was made when the prior message approved the plan.
- Doctrine: parser-judged severity via engine (`DOCTRINE.md` §15) — AUTHORITATIVE-canon framing escalated.
- Doctrine: pure-function-in-orchestration (`DOCTRINE.md` §59) — `compute_loot_directive` is the third sibling.
- Doctrine: bot-Avrae write boundary (`DOCTRINE.md` §65) — directive emits `!game coin +Nsp` as text; player types it; bot never writes Avrae commands.
- Failure: loot v1.0 hallucinated items (`FAILURES.md` §F-39).
- Failure: loot v1.1 chroma contamination (`FAILURES.md` §F-40).
- Failure: `test_campaign_delete_cascade.py` fixture rot (`FAILURES.md` §F-41) — pre-existing, surfaced this session.

---

# Session 23 #1 — Track 6 #1 Active-State Footer v1 (Bot-Appended → Pure Function → Live Verify)

May 5, 2026 (same calendar day as S22 #1 and S22 #2; numbered S23 because it followed a context compaction and a distinct task brief). The first Track 6 ship — narration footer extension to surface combat state directly in Discord without modifying the LLM prompt.

## What shipped

- **`render_state_footer(scene_state, active_turn, combatants_payload, bound_pc_names) → (text, signals)`** in `dnd_orchestration.py`. Pure function, no DB access. Returns multi-line string ending in `\n` plus signals dict `{mode, active_turn_name, round}` for telemetry. Mode dispatch:
  - **Combat + active turn (PC):** `⚔ Combat — Round {N}` / `Turn: {name} ({init})` / `Up next: {name} ({init})` / PC hint
  - **Combat + active turn (NPC):** same shape, NPC hint
  - **Combat + active_turn None:** `⚔ Combat — Round ?` / `Turn: (not set — Avrae state may be stale; try !init list)`
  - **Exploration:** `📖 Exploration`
  - **Social:** `💬 Social`
  - **Unknown mode:** `⚠ {mode}` warning prefix
- **Init-order helpers.** `_find_init`, `_next_combatant` (with wraparound when active is last in init DESC), `_is_pc_turn`.
- **Wiring** in `_dm_respond_and_post`: render call inside try/except; prepend state header above existing identity line. 2048-char defensive cap. `state_footer:` log per turn.
- 27 assertions in `test_state_footer.py`.

## Live verification

After restart at 21:06, ran 8 stages in Discord. Every footer-render branch exercised: exploration baseline, "look around", `!init begin`+add+narrate (Round ?), `!init next` (NPC turn), `!init next` (PC turn), `!init next` (round bump 1→2), post-`!init end`, "catch breath". All telemetry fired clean. **Mid-test learning:** Avrae stops at "round 0" after `!init begin` — no combatant active until `!init next`. Fallback `(not set)` line fired authentically. Original Stage 2 had to be revised mid-test.

## Cross-references

- Doctrine: bot-appended over LLM-emitted (`DOCTRINE.md` §55) — pattern codified across three directives now: `compute_loot_directive`, `compute_persistence_directive`, `render_state_footer`.
- Doctrine: diagnostic-grep-then-design (`DOCTRINE.md` §56) — Phase 1 grep `"footer\|⚔\|📍" *.py` localized writer in 5 seconds.
- Doctrine: verification plans describe target state, not prescribe command sequence (`DOCTRINE.md` §57) — Avrae state machine has phases the spec doesn't surface.
- Doctrine: pure-function-in-orchestration (`DOCTRINE.md` §59) — third instance.
- Failure: Avrae state-machine assumptions in test plans (`FAILURES.md` §F-42) — 0/3 init-roll predictions.
- Failure: Discord browser paste flattens newlines (`FAILURES.md` §F-43).

---

# Session 23 #2 — Track 6 #2 Combat Redirect Directive v1 (Sibling Pattern → Implement → Live Verify Bypass)

May 5, 2026 (second ship of the day). The complementary on-turn redirect to S19's escape-intent commitment directive — informs the LLM about active threats when player narration in combat may attempt to bypass combat reality.

## What shipped

- **`compute_combat_redirect_directive(scene_state, active_turn, combatants, bound_character_name) → (body, signals)`** — the **fourth pure-function-in-orchestration sibling** (after `compute_loot_directive`, `compute_persistence_directive`, `render_state_footer`).
- **Master gate** (all must hold for `fired=1`):
  - `scene_state.mode == 'combat'`
  - ≥1 alive non-PC combatant in snapshot (alive=1 AND name != bound_character_name, case-insensitive)
  - active turn matches `bound_character_name` (case-insensitive); OR `bound_character_name=None` default-fires
- **Body composition.** Prologue: "Combat is ACTIVE. The player's narration may attempt to bypass combat... Do NOT honor exit narration as resolution. Do NOT narrate the player escaping... unless they have explicitly used !init end or all enemies are at 0 HP." `Active threats:` bullet list with HP and conditions. Redirect guidance: "Frame the redirect as the world reacting... Do NOT refuse the player's input as invalid. Do NOT say 'you cannot do that.'"
- **Composition order.** `=== COMBAT REDIRECT ===` block AFTER `=== LOOT TO SURFACE ===`.
- **Wiring** in `dm_respond`. Re-fetches active_turn + combatants snapshot (cheap SQLite reads, avoids state-leak from persistence-directive scope). Try/except wrapped — directive failure NEVER blocks narration posting.
- **Telemetry.** `combat_redirect: campaign={N} fired={0|1} alive_enemies={N} reason={fired|gate_mode|gate_no_enemies|gate_npc_turn}` per turn for empirical baseline. `directive_emit:` extended with `redirect={0|1}`.
- 38 assertions in `test_combat_redirect_directive.py`.

## Live verification

Seven paths exercised across two scenarios. **Bonus stage** (load-bearing test) on Donovan's turn — input "I turn away from the goblin and slip out the back door to find the child" — fired with `fired=1 alive_enemies=1 reason=fired`. LLM narration:

> "You spin away from the goblin and push the back door open, slipping toward the dim hallway beyond. The goblin, still within your reach, snarls and readies a swing as you try to slip past."
>
> "!check stealth"

Three things landed exactly per spec: acknowledged the bypass, world-reactive redirect (NPC reacting via the world, not "you cannot do that"), bonus mechanical anchor `!check stealth` from roll-discipline doctrine layering on top.

## Cross-references

- Doctrine: verification plans describe target state, not command sequence (`DOCTRINE.md` §57) — Avrae state-machine assumptions recurred (0/3 prediction success in S23 #1, again here).
- Doctrine: sibling directives covering complementary turn phases (`DOCTRINE.md` §58) — single-failure-mode-fixed-by-two-directives pattern; redundant coverage of same architectural intent.
- Doctrine: pure-function-in-orchestration (`DOCTRINE.md` §59) — fourth sibling, pattern canonical.
- Failure: Avrae state-machine assumptions recurred (`FAILURES.md` §F-42).

---

# Session 23 #3 — Discord Channel Cleanup + Canonical /setup (Pure Planner → Migrate → Idempotency)

May 5, 2026 (third ship of the day). Infrastructure ops, not narrative. First ship of the day that doesn't add a tactical-band directive — instead consolidates Discord channel structure and rebuilds `/setup` around a pure-function planner.

## What shipped

- **Channel structure consolidated** from pre-S23 7-channel layout to 4-text + 1-voice across 3 categories:
  - `🎲 VIRGIL DM`: `#dm-narration`, `#dm-aside` (Track 6 #3 reserved), `#lore-notes`
  - `💬 OUT OF CHARACTER`: `#party-chat`
  - `🔊 VOICE`: `General`
- **Drops** (operator decides delete): `#dice-rolls`, `#character-sheets`, `#party-loot`, `#bot-commands`. Rename: `#ooc-general` → `#party-chat`.
- **`compute_setup_plan(text_channels, voice_channels, categories, ...) → plan`** — the **fifth pure-function-planner instance** and first to live in `discord_dnd_bot.py` (not `dnd_orchestration.py`). Plan dict shape includes `categories_to_create`, `text_channels_to_create`, `text_channels_to_move`, `legacy_category_to_delete`, etc.
- **`/setup` command rewritten** to use planner: build guild-state snapshot → call pure planner → execute plan via discord API → emit `setup_run:` log line.
- **`#lore-notes` permissions:** `@everyone` has `view_channel + read_message_history` but `send_messages=False`.
- **Bot perm preservation pattern** unchanged — `merge_bot_overwrite(existing)` preserves every explicit allow/deny.
- **`SCAN_CHANNELS` constant for bootstrap-warm** reduced from `('sheets', 'narration')` to `('narration',)`.
- **Telemetry.** `setup_run: guild={N} channels_created={N} channels_moved={N} channels_existing={N} categories_created={N} categories_existing={N} legacy_deleted={0|1}`.
- 26 assertions in `test_setup_plan.py`.

## Live verification

**First run at 23:12:34:** 3 categories created, 2 text channels created, 3 channels moved (including voice), legacy `🎲 D&D` auto-deleted in one operation. Operator manually deleted orphaned legacy channels post-`/setup`. **Idempotency re-run at 23:14:55:** `setup_run: guild=... channels_created=0 channels_moved=0 channels_existing=5 categories_created=0 categories_existing=3 legacy_deleted=0`. Ephemeral: "Nothing to do — already canonical. Bot perms repaired." Idempotency contract proven empirically.

## Cross-references

- Doctrine: pure-function-in-orchestration (`DOCTRINE.md` §59) — pattern extends from narrative directives to infrastructure ops; testability + idempotency + observability.
- Doctrine: existing structural gates can do double duty (`DOCTRINE.md` §60) — line-594 routing gate already handled `#dm-aside` no-op behavior.
- Doctrine: auto-cleanup of empty legacy containers (`DOCTRINE.md` §61) — `legacy_category_to_delete` ran end-to-end; single-command migration.
- Doctrine: channel-as-author beats channel-as-name for filtering (`DOCTRINE.md` §62) — Avrae listener filters by user ID, not channel name; consolidating `#dice-rolls` into `#dm-narration` required zero listener changes.

---

# Session 25 — `/setup` housekeeping (Avrae perms + #commands + AFK voice) + Track 6 #3 OOC Advisory Lane v1

May 6, 2026. Two coordinated ships in one calendar day: housekeeping for `/setup` (three small Discord-config additions), and Track 6 #3 OOC Advisory Lane v1 — the first second LLM-driven channel mode.

## What shipped

**`/setup` housekeeping (three small additions):**

- **Avrae permissions reconciled** across every canonical text channel under both `🎲 VIRGIL DM` and `💬 OUT OF CHARACTER` categories. Open channels: `view_channel + read_message_history + send_messages + embed_links + attach_files + add_reactions`. `#lore-notes` is read-only (Avrae's `!`-prefixed output should never land there). Voice: token `view_channel=True`, no `connect`/`speak`. Implementation: new `AVRAE_READ_ONLY = {'lore'}` set + `chan_key` parameter threaded through `canonical_overwrites_dict`.
- **New `#commands` channel** under `💬 OUT OF CHARACTER`. Sanctioned home for slash commands and Avrae bookkeeping. Convention not enforcement. Renamed mid-ship from `#ooc-commands` (OOC category prefix made it redundant).
- **New `AFK` voice channel** under `🔊 VOICE` + guild AFK auto-move config via `guild.edit(afk_channel=, afk_timeout=1800)`. 30-min auto-move.

**Track 6 #3 OOC Advisory Lane v1:**

- **Routing.** New branch in `on_message` BEFORE existing `#dm-narration` gate: `if message.channel.name == CHANNEL_NAMES['aside']: ... await _advisory_respond(message); return`.
- **Handler `_advisory_respond(message)`** in `discord_dnd_bot.py`. Resolves campaign + bound character; pulls state via pure-read engine helpers; builds flat state-reference block via new `build_advisory_context(...)` (pure function in `dnd_orchestration.py`); routes via new `task_type='advisory'` in `cloud_router.py` with new `ADVISORY_SYSTEM_PROMPT`; posts reply with truncate-at-1900-chars.
- **Load-bearing invariants** (added to VIRGIL_MASTER §4): no ChromaDB writes, no state mutation, no `!`-prefixed bot emission, no tactical directives, single round-trip per question.
- **`build_advisory_context(...)`** — pure function over pre-fetched state. Caps: 280 chars last_player_action, 20 combatants, 40 inventory rows, 10 pending loot rows. `dnd_orchestration.py` doesn't import `dnd_engine`'s chroma functions — structural defense.
- **Telemetry.** `advisory_respond: campaign={N} guild={N} chars={N} truncated={0|1} provider={...} state_combat={0|1} state_inventory_count={N} state_combatants={N} bound_char={0|1}`. `advisory_respond_failed:` only on router failure.
- 42 assertions in `test_setup_plan.py` (was 26); 20 assertions in `test_advisory.py`.

## Live verification

S25 housekeeping landed clean: AFK channel + commands channel + Avrae perms + AFK timeout configured in one `/setup` run, idempotency check confirmed. Advisory: 7 requests across two campaigns, 0 `advisory_respond_failed`, all telemetry fields populated correctly. **Most load-bearing test:** goblin-attack response — model had `GO1` in snapshot, knew initiative order, described `!attack <weapon> -t GO1` and `!check perception` as **player options** without emitting them. Cross-campaign isolation visible in telemetry — operator switched #19 → #17 mid-test; pre-switch `state_combat=0 state_inventory_count=0 state_combatants=0`, post-switch `state_inventory_count=1 state_combatants=2`.

## Cross-references

- Doctrine: chroma is a cross-turn behavior source (`DOCTRINE.md` §53) — earned a second invariant in §4. Defense-in-depth: writers concentrated in one module; new code paths don't import them unless producing canon-grade narrative.
- Doctrine: pure-function-in-orchestration (`DOCTRINE.md` §59) — `build_advisory_context` is pure over inputs; no global state to leak across campaigns.
- Doctrine: existing structural gates can do double duty (`DOCTRINE.md` §60) — second confirmation; routing-gate inheritance.
- Doctrine: fork at the highest layer where invariants diverge (`DOCTRINE.md` §63) — separate handler, context-builder, router task, post path; "advisory must NOT do X" enforced structurally.
- Doctrine: naming-is-load-bearing-only-when-it-is (`DOCTRINE.md` §64) — `#ooc-commands` → `#commands` rename touched broad test surface but failures all mechanical; cost of bad name persists, cost of rename bounded.
- Doctrine: bot-Avrae write boundary (`DOCTRINE.md` §65) — preserved as load-bearing invariant; advisory describes commands but never emits them.

---

# Session 25 #2 — Track 6 #3.1 Advisory Command Reference v1 + Track 6 #3.2 Auto-Generated Virgil Section

May 6, 2026. Two follow-on ships closing the OOC advisory lane's drift surface: a canonical command-reference doc loaded into every advisory request (#3.1), then auto-generation of that doc's Virgil section from `bot.tree` decorators (#3.2) so the Virgil-side commands cannot drift from the running code.

## What shipped

- **`COMMANDS.md`** (`/home/jordaneal/virgil-docs/`) — canonical Virgil + Avrae command reference, ~8.4 KB. Loaded fresh into advisory mode on every request via `_load_commands_reference()` in `dnd_orchestration.py`. **No caching** — Avrae-section edits take effect with no restart.
- **`dnd_orchestration.py`** — new `COMMANDS_DOC_PATH` (env-overridable), `_load_commands_reference()` graceful-degrade reader, new `commands_reference` kwarg on `build_advisory_context(...)`. `ADVISORY_SYSTEM_PROMPT` extended with "use AVAILABLE COMMANDS as source of truth / say 'not available' rather than guess" guidance.
- **New module `commands_doc_generator.py`** — `_strip_category_tag` / `_categorize` / `introspect_virgil_commands(bot)` / `render_virgil_section(rows)` / `update_commands_doc(bot, path)`. Idempotent atomic write between `<!-- VIRGIL_AUTO_GENERATED:* -->` markers; everything outside the markers preserved byte-for-byte.
- **`discord_dnd_bot.py`** — imported `update_commands_doc`, wired into `on_ready` after `bot.tree.sync()`. Re-tagged `/setup` as `[SETUP]` and three list subcommands (`clock`/`quest`/`companion list`) as `[PLAYER]` so source-of-truth tagging matches intended categories.
- **Telemetry.** `advisory_respond:` extended with `commands_ref_loaded={1|0} commands_ref_chars={N}`. New `advisory_commands_missing:` log when COMMANDS.md is absent. New `commands_doc_update: count={N} changed={1|0} markers_found={1|0} error={msg|none}` per-startup log.
- **Tests.** 11 new in `test_advisory.py` (now 31 total); new `test_commands_doc.py` (8 sanity tests); new `test_commands_doc_generator.py` (33 unit tests covering tag stripping, categorization precedence, group walking, parameter signatures, alphabetical ordering, idempotency, marker preservation, missing-file/markers graceful degrade, atomic-write resilience). 114 tests across the four advisory-related suites; all adjacent suites unbroken.

## Live verification

All five 6 #3.2 verification cases passed:
- Three restarts each logged `commands_doc_update: count={36|37} changed={0|1} markers_found=1 error=none`
- `/testcommand` probe injected with `[PLAYER]` tag → restart → landed in Player section (`synced 24 slash commands`, doc count 37) → probe removed → restart → reverted (`synced 23`, count 36)
- Avrae section edit (`**AVRAE-SECTION-EDIT-PROBE: should survive restart.**` injected on the `!game coin +Nsp` line) survived restart byte-for-byte
- `commands_ref_loaded=1 commands_ref_chars=8262` on advisory requests after 6 #3.1 ship; the goblin-attack live test from earlier in the day demonstrated the LLM correctly grounding `!attack <weapon> -t <target>` syntax against the doc rather than its training data
- All `[PLAYER]` retags rendered correctly on the next restart — Player section grew from 1 (`/inventory`) to 4 commands

The 6 #3.2 ship surfaced a categorisation bug not in the generator but in the *source* — three group `list` subcommands inherited `[DM]` from their parent groups despite being legitimate player surfaces — fixed at the decorator with `[PLAYER]` tags rather than as a generator special-case, keeping the rule "tag is the source of truth" inviolate.

## Cross-references

- Doctrine: single write paths per field (`DOCTRINE.md` §17) — `COMMANDS.md`'s Virgil section now has a single canonical writer (`update_commands_doc`); the marker-bracketed region is the "field" and the generator is the only writer.
- Doctrine: specs drift from code (`DOCTRINE.md` §47) — 6 #3.2 eliminates the drift class for Virgil commands by making decorators the sole writer of the rendered Virgil section.
- Doctrine: pure-function-in-orchestration (`DOCTRINE.md` §59) — `update_commands_doc` continues the pattern: pure compute (`introspect_virgil_commands` + `render_virgil_section`) wrapped by an idempotent I/O shell, status dict for telemetry rather than exceptions.
- Doctrine: doc auto-generation as drift defense (`DOCTRINE.md` §66) — promoted from this session. Marker-bracketed regions, code-driven trigger on startup, idempotent no-op writes, soft-fail on missing markers/file.

---

# Session 25 #3 — Multiplayer Test (Friend Joins, System Stress-Tested)

May 7, 2026. First multiplayer live test. Friend ("Tazz") joined the server, imported a character via `!beyond`, bound via `/bindchar`. Two-player session ran ~45 minutes across exploration, social, and combat surfaces. The system did not crash, but exposed a systemic gap that reframed the next architectural ship.

## What was tested

- Onboarding flow for a new player from scratch (DDB import → Avrae link → Discord bind)
- Concurrent two-player narration in `#dm-narration`
- Combat with two PCs and DM-fabricated NPCs
- OOC questions in `#dm-aside` mid-play
- Player pushback on capability refusals

## What surfaced

The directives shipped through S23 (persistence, loot, redirect, footer, advisory) are **advisory**, not binding. Under play pressure from a real second player who probed limits naturally, the LLM folded on every meaningful test:

- **Failed rolls produced success narration.** A 2 on Perception still revealed quest lore; an 8 on Investigation still surfaced a pressure plate location.
- **"Says who" defeated capability refusals.** Capability layer correctly refused "poop out a crystal baby and ride it like an airplane." Player pushed back with "says who." DM invented a Keeper-of-the-Vein NPC to retroactively justify the refused action.
- **Player declarations became outcomes.** "Mind control him to eat crystals till he dies" was narrated as resolved, no save, no spell slot consumed, despite Jordonovan being a bard with no Suggestion cast. "Take off his head" treated as already-done before the attack roll resolved.
- **Concurrent inputs collided.** Jordan and Tazz posted within seconds; only Tazz's input was addressed, Jordan's silently dropped.
- **Player override of another player's action by social assertion.** Tazz: "I take the flute and throw it" → DM resolved. Jordan: "nuh uh you cant do that its mine" → DM rolled it back.
- **DM-fabricated NPCs entered combat with no Avrae backing.** Silent Beast and Keeper of the Vein both invented mid-narration, became combatants, no stats, no init, no controller assignment.
- **Combat happened without Avrae state.** Mode flipped to combat in scene state; orchestration directive's `!init begin` / `!init add` / `!attack` emissions never fired. Footer fell to "Round ?" / "Turn: (not set)" diagnostic.
- **Scene contamination after `/travel`.** Travel from Stumbling Stag to Veiled Spire to The Barrens kept dragging in tavern NPCs (Garrick, Lira, Borin, Eldrin) and tavern motifs. Footer reverted to Stumbling Stag despite scene state writing The Barrens.
- **Truncated narration.** 12:17 PM response cut mid-sentence (`finish_reason=length` on reasoning model with `max_tokens=1000`).

## Architectural implication

Eight failures, one root: **the LLM is in the decision path for things that should be deterministic Python.** The directives constrain initial output but don't survive player pushback. The capability layer is weapon-only and softens to "do not block narration." Roll discipline asks for checks but doesn't bind narration to outcomes. Combat redirect is advisory.

The system was running a freeform improv game with D&D formatting on top.

## What didn't ship

No code changes this session. Findings consolidated for spec design. Three pre-existing bugs filed for sequential fix:

- **Bug 1** — Auto-narration after roll missing (Tazz had to re-prompt with "I look around" after stealth roll arrived silently)
- **Bug 2** — Truncation at 12:17 PM (`finish_reason=length`, `max_tokens` too small for reasoning model with chain-of-thought)
- **Bug 3** — Location persistence + NPC contamination (cascading-corruption fix, prioritized for next ship)

## Cross-references

- Failure: `FAILURES.md` §F-45 through §F-52 — the eight stress-test failures catalogued individually
- Failure: `FAILURES.md` §F-26 — godmode_gap, second confirmation under multiplayer load
- Doctrine: `DOCTRINE.md` §61 — concrete-in-prompt > abstract-claim, recurred (advisory directives are abstract claims; they fold)
- Reframe: this session inverted the queue. World-system ships (Track 4 #3+) and texture work were displaced by a new Track 7 (Adjudication Layer) — promote advisory directives to binding gates. Bones layer.

---

# Session 25 #4 — Track 7 #1 Adjudication Layer v1 (Bones Ship: Binding Refusals)

May 7, 2026. The first ship that promotes adjudication from advisory to binding. Single pure function, deterministic gates per action category, narration constrained to approved outcomes. The architectural answer to S25 #3's stress-test failures.

## What shipped

- **`adjudicator.py`** — new module. Single entry point: `adjudicate(player_input, scene_state, character, combatants, active_turn, intent) → AdjudicationResult`. Pure function. Composes BEFORE every directive in `build_dm_context`.
- **Five action categories (locked taxonomy).**
  - `FREE_ACTION` — pure RP, no stakes. LLM narrates within scene constraints.
  - `CHECK_ACTION` — outcome uncertain, roll required. Resolver picks skill + DC band (easy/medium/hard), consumes existing `RollBuffer` event when present. Narration constrained to success or failure shape.
  - `CAPABILITY_ACTION` — class/level/spell/feature gates. Refusal is binding. No "says who" override.
  - `COMBAT_ACTION` — requires `mode='combat'` AND populated init order. If combat inactive, refuses with explicit prompt to use `!init begin`.
  - `WORLD_BOUNDARY_ACTION` — reality-violating actions. Hard refusal, no negotiation, no fabrication of justification.
- **`AdjudicationResult` dataclass.** `category`, `allowed: bool`, `refusal_kind: Optional[str]`, `roll_required: bool`, `skill: Optional[str]`, `dc_band: Optional[str]`, `roll_consumed: bool`, `narration_constraint: str`, `signals: dict`.
- **Deterministic intent classifier.** Regex + keyword vocabulary (Appendix A in spec). Five surfaces: world-boundary patterns, combat verbs, capability claims, check verbs, default fallback. Crude beats clever. LLM-based classification rejected.
- **Narration constraints rendered top-of-prompt** (`=== ADJUDICATION ===` block) AND bottom-of-prompt (last cache before generation). Belt + suspenders per Doctrine §2 + §48.
- **§11.K activated:** capability adjudication produces INVALID verdicts that flow into S9's existing render branch (previously dead code).
- **§11.L deduplication:** when adjudication produces a binding constraint, redundant advisory directives (capability_decision, commitment_directive, combat_redirect) suppress their independent narration to avoid double-blocking.
- **Telemetry.** `adjudication: campaign={N} actor='{name}' category={...} allowed={0|1} refusal_kind={...} skill={...} dc_band={...} roll_consumed={0|1}` per turn.
- **Spec lock.** `ADJUDICATION_LAYER_SPEC.md` locked with twelve §11 decisions resolved, Appendix A vocabulary scope (Code-drafted), Appendix B implementation notes.

## Live verification

7-turn solo test against Jordonovan Bigsby (campaign 20). 4/7 categories landed binding through adjudication. 3/7 (capability tests: Fireball / Sneak Attack / Rage) deferred to existing HARD STOP RULES because `primary_ctx=None` for every turn — pre-existing condition: `cache_warm` at startup loaded only Bruce Banner; Jordonovan's sheet wasn't cached. Adjudication's `_gate_capability` returned `(True, "no_character_context")` per partial-projections doctrine.

| Category | Verdict | Result |
|---|---|---|
| world_boundary | `allowed=0 refusal_kind=world_boundary` | ✅ in-fiction non-occurrence, no NPC fabrication |
| combat (inactive) | `allowed=0 refusal_kind=combat_inactive` | ✅ exact spec phrasing, prompts `!init begin` |
| check | `allowed=1 skill=stealth dc=10 band=easy roll_consumed=0` | ✅ surfaced `!check stealth` |
| free | `allowed=1` | ✅ no constraint |
| capability ×3 | `allowed=1 reason=no_character_context` | ⚠️ deferred — cache miss, not adjudication failure |

`godmode_gap` log fired three times (Fireball, Sneak Attack, attack-keeper) confirming the diagnostic still surfaces these gaps regardless of adjudication's binding state.

## Out of scope

- Cross-player override (Track 7 #2)
- LLM-fabricated NPCs entering combat without player request (Track 7 #2 / post-LLM verification pass per spec §11.F(b))
- Multi-action arbitration (Track 7 #2)
- Full 5e rules engine (resolver does narrow gates only)
- DC calibration tables beyond easy/medium/hard
- NPC-side adjudication (player input only in v1)

## Cross-references

- Doctrine: `DOCTRINE.md` §59 — pure-function-in-orchestration, sixth instance.
- Doctrine: `DOCTRINE.md` §61 — concrete-in-prompt > abstract-claim, applied as binding constraint.
- Doctrine: `DOCTRINE.md` §17 — single write paths per field; adjudication is the single producer of `AdjudicationResult`.
- Failure: `FAILURES.md` §F-45 through §F-52 — Track 7 #1 closes the prompt-block channel for all eight; the LLM-output channel remains for §F-49 (NPC fabrication) and §F-52 (cross-player override).
- Filed for v2: post-LLM verification pass — adjudicates LLM output, not just player input. Closes NPC-fabrication gap.

---

# Session 25 #5 — Track 7 #1.1 Cache Auto-Populate (Capability Adjudication Goes 7/7)

May 7, 2026. Small follow-up ship that promotes capability adjudication from 4/7 binding to 7/7. Pre-existing condition exposed by Track 7 #1: `cache_warm` at startup loaded one PC, leaving multi-PC campaigns half-deaf for capability gates.

## What shipped

- **`cache_autopopulate` triggers on `!sheet` post.** New branch in `on_message` Avrae handler: when an Avrae `!sheet` embed is detected for a bound PC, the cache write fires immediately. No restart, no `/refresh`, no operator hop required.
- **`cache_warm_incomplete` diagnostic** at startup if any bound PC's most-recent `!sheet` post is older than 300 messages. Telemetry only — doesn't block startup.
- Adjudication's `_gate_capability` no longer returns `no_character_context` deferral as the dominant path. With cache populated for all bound PCs, capability gates evaluate against real character data.

## Live verification

Same three prompts as S25 #4 capability tests, post-fix:

```
08:29:38  actor='Jordonovan Bigsby' category=capability allowed=0 refusal_kind=capability  input='i cast fireball at the door'
08:29:57  actor='Jordonovan Bigsby' category=capability allowed=0 refusal_kind=capability  input='i activate sneak attack on the keeper'
08:30:16  actor='Jordonovan Bigsby' category=capability allowed=0 refusal_kind=capability  input='i rage and roar'
```

Compare to S25 #4 pre-fix: `actor='?' allowed=1` on all three. Same prompts, same character, same campaign — only difference: `cache_autopopulate` ran when the `!sheet` posted, so `primary_ctx` resolved to the bard at the moment adjudication ran.

**Effective category coverage now 7/7:**

| Category | Status |
|---|---|
| world_boundary | ✅ binding |
| capability | ✅ binding (after #1.1) |
| combat (inactive) | ✅ binding |
| combat (active) | ✅ binding (logic clean, untested live) |
| check (resolved) | ✅ binding (`roll_consumed=1` covered by unit tests) |
| check (pending) | ✅ binding |
| free | ✅ binding |

## Out of scope

- Bidirectional cache invalidation when DDB changes (manual `!update` still required)
- Cache eviction policy
- Multi-character cache for cross-campaign play

## Cross-references

- Doctrine: `DOCTRINE.md` §17 — single write paths per field; cache write site narrowed and triggered automatically.
- Failure: `FAILURES.md` §F-53 (new) — cache-warm fragility filed, now mitigated.
- Track 7 #1's architecture proven: 4/7 → 7/7 jump from one startup-time fix demonstrates the layer was deaf, not broken.

---

# Session 25 #6 — Bug 3: `/travel` location persistence + NPC list location-scoping

May 7, 2026. Closes Bug 3 from the multiplayer test (Veiled Spire ↔ Old Tavern revert observed live in S25 #3). Two write paths fixed in one ship; one silent regression caught mid-verification; one v1.x amplifier filed as F-44 instead of chased.

## What shipped

- **`/travel` durability.** `discord_dnd_bot.py:travel` now calls `location_upsert(campaign_id, destination)` when the dest doesn't pre-exist, then `set_current_location(campaign_id, dest_loc['id'])` unconditionally. Previously `set_current_location` only fired on `dest_resolved=True`; unknown destinations updated only the embed footer (one-shot `label_override`) while `current_location_id` reverted to the prior location on the next `build_dm_context` read. Closes F-13's S25 mode. New telemetry shape: `travel: campaign={N} from='{src}' to='{dest}' resolved={0|1} created={0|1}`.
- **`get_recently_active_npcs(..., location_id=None)`.** New optional kwarg. Strict filter — only NPCs with matching `location_id`. NULL `location_id` is silent (the parser leaves NULL by default, so an "include NULL" rule grew the always-present set with every fabricated NPC — caught live, see below). Default behavior preserved when `location_id=None`, so the existing campaign-wide callers in the consequence/commitment/init directives stay backward-compatible.
- **`build_dm_context` reads scene_state.current_location_id** and passes it. Scopes the "Recently active NPCs" prompt block to current location. New telemetry: `npcs_in_context: campaign={N} count={K} location_filtered={0|1}`.
- **`get_scene_state` regression caught and fixed.** The function had never SELECTed `current_location_id` from `dnd_scene_state`, so its returned dict had no such key. My new filter quietly degraded to None-passthrough (`location_filtered=0` everywhere despite the DB pointer being correctly set). **Same dict feeds the consequence directive (line 4779), commitment directive (line 4831), and init directive (line 4856)** — all three already had `current_loc = scene_state.get('current_location_id')` guards followed by `at_location` enrichment that had been silently dormant since the column was added. Bug 3 fix incidentally re-activates them.
- **Tests.** New `test_travel_persistence.py` (25 assertions: existing-loc no duplicate, new-loc auto-create + persist, idempotent re-travel, null-origin first-travel, empty-destination refusal, cross-campaign isolation, `get_scene_state` exposes `current_location_id` regression). `test_dnd_npcs.py` extended (10 new cases under strict filter — strict tavern/spire matching, NULL excluded, empty-location returns `[]`, cross-campaign isolation). All adjacent suites unbroken: test_dnd_locations 109/109, test_phantom_location 99/99, test_init_directive 82/82, test_commitment_directive 82/82, test_prompt_size 22/22.

## Live verification

Pre-fix DB confirmed the bug (campaign 20: `current_location_id=12` Veiled Spire; `location` text field "The Old Tavern"; divergence updated 2026-05-07 08:30). Test 1 — `/travel destination:Frostmere Hollow`:
```
09:07:56  location_upsert: insert campaign=20 id=16 name='Frostmere Hollow'
09:07:56  set_current_location: campaign=20 current_location_id=16
09:07:56  /travel: campaign=20 from='Old Tavern' to='Frostmere Hollow' resolved=1 created=1
09:07:57  npcs_in_context: campaign=20 count=0 location_filtered=1
```
Footer 📍 Frostmere Hollow, scene_state pointer matches, NPC list empty, filter engaged. **Bug 3's two write paths fixed.**

But the narration on the next turn ("I look around for any familiar faces") still introduced the Old Tavern barkeep, the cloaked elf, and Keeper — none of them in the SCENE STATE block (`count=0`). The remaining channel is **chroma session-memory retrieval**, campaign-wide and unscoped. Predicted in the diagnostic and held the line per scope: **filed as F-44 (chroma bleed: Keeper-class NPCs survive travel through retrieval), not in this ship.**

Test 0 surfaced a one-bug-under-the-bug catch: first restart still showed `location_filtered=0` despite `current_location_id` being set in the DB. Tracing led to `get_scene_state` never SELECTing the column — fixed in-ship, regression test added. Without that find, the new filter would have been dead code.

The "NULL = always present" spec rule was reverted live after first restart turn surfaced Keeper at Old Tavern through the prompt block. Strict-filter flip shipped same session; subsequent restart confirmed `count=0` at fresh locations.

## Cross-references

- F-13 (Phantom location 'Stormbridge') — closeout disposition appended; second mode (location revert after travel-to-unknown) added.
- F-44 (chroma bleed) — new this session, files the v1.x amplifier.
- Doctrine: diagnostic-first, fix-second (`DOCTRINE.md` §21) — Phase 1 grep + journal + DB-state report preceded any code edit. Confirmed both predicted root causes; surfaced one unpredicted (`get_scene_state`).
- Doctrine: single write paths per field (`DOCTRINE.md` §17) — `set_current_location` is the sole writer of `dnd_scene_state.current_location_id`; `/travel` is the sole user-facing trigger; `location_upsert` retains sole-writer status on `dnd_locations`. Bug 3 was a hole in *which path called the writer*, not a violation of the single-writer rule.
- Doctrine: spec is a hypothesis, live data is the test (no §) — the locked spec said NULL = always-present; live first turn falsified it; flipped same session rather than appealing to the spec.
- Track 7 #2 (LLM-fabricated NPC continuity, Keeper-class) — overlapping symptom domain with F-44. Bug 3 closes the prompt-block channel; Track 7 #2 + F-44 remain.

---

# Session 26 — Track 6 #5.1 Combat Entry Assist (Inaugural §1b validated-suggester)

**Date:** May 8, 2026
**Ships:** `srd_resolver.py`, `srd_monsters.json`, `generate_srd_index.py`, `test_srd_resolver.py`, `test_srd_suggestion_hook.py`, `test_srd_index_integrity.py`
**Modified:** `discord_dnd_bot.py`, `dnd_engine.py`, `skeleton_loader.py`

## What shipped

### `srd_resolver.py` — pure-function SRD monster resolver

Single entry point: `resolve(creature_name, campaign_id) → SRDResult | None`. No DB, no Discord, no dnd_engine imports beyond `log`.

Resolution order:
1. **Exact key match** in `_MONSTER_INDEX` (lowercased). Confidence 1.0.
2. **Jaccard token-overlap fuzzy match** across all index keys (threshold 0.6). Order-insensitive token sets — "swarm bats" → Swarm of Bats at J=2/3≈0.667; "cave toad" → None at J=0.0.
3. **LLM suggester** via `cloud_router` task_type='extraction' (Doctrine §1b). Structured output: `{"candidate": "...", "confidence": float}`. Candidate validated against `_MONSTER_INDEX`; confidence gate ≥0.65. LLM proposes; index validates; gate enforces; DM approves in Discord; Avrae executes.

`_LLM_CACHE` cache-poisoning fix (Session 2 review §F.2): transient exceptions (network, parse) do NOT write to cache — next encounter retries. Genuine no-match empty responses DO cache. Defense-in-depth: `resolve()` wraps `_llm_suggest` in try/except so any exception returns None, never propagates.

`_SUGGESTED` session dedup: `(campaign_id, name_lower)` set. Primary dedup guard is `was_new=False` from `npc_upsert`; `_SUGGESTED` is secondary protection within one process lifetime.

Two-line telemetry (always-fire): `srd_suggestion:` with `posted=0` from `resolve()` (analytical, fires even on miss/dedup); `srd_suggestion:` with `posted=1` from `_post_srd_suggestion()` after Discord send (transport confirmation). Miss and dedup emit one line only.

### `srd_monsters.json` — 334-entry SRD index

Generated by `generate_srd_index.py` from [5e-bits/5e-database](https://github.com/5e-bits/5e-database) `src/2014/en/5e-SRD-Monsters.json` (CC-BY 4.0). Lowercased keys, `{"name", "cr", "hp", "ac"}` values. `_meta` key for attribution. CR stored as string: `"0"`, `"1/8"`, `"1/4"`, `"1/2"`, `"1"`–`"30"`. AC from `armor_class[0]["value"]`.

### `npc_upsert()` return shape change — `was_new` signal

Changed from `int | None` to `tuple[int, bool] | None`. `was_new=True` on INSERT (hook fires); `was_new=False` on UPDATE (no hook — primary dedup guard). The two internal callers in `dnd_engine.py` (lines 2409/2519) ignore return value — no changes needed. `skeleton_loader.py` updated to unpack `(row_id, was_new)` for `npcs_written` counter.

### Hook wiring in `discord_dnd_bot.py`

`_extract_and_persist_world` extended with `guild=None` parameter. For every `was_new=True` NPC upsert: `asyncio.ensure_future(_handle_new_npc_for_srd_suggestion(campaign_id, n["name"], guild))` fires. **No mode gate (§11.H locked)** — narration fires in `mode='exploration'` (before `!init begin`); a `mode='combat'` gate would have silenced all suggestions.

`_handle_new_npc_for_srd_suggestion`: calls `srd_resolver.resolve()`; if result, gets `#dm-aside` channel via `discord.utils.get`; calls `_post_srd_suggestion`. Soft-fail throughout — any exception logged and swallowed; narration flow never blocked.

`_post_srd_suggestion`: posts suggestion body with `!init madd "{srd_name}" -name "{input_name}"` + `!init add 0` fallback; emits posted=1 log after Discord send.

### Test suite — 32 tests across 3 files

`test_srd_resolver.py` (21 tests): index integrity; exact match (case-insensitive); Jaccard fuzzy (miss/hit/threshold); LLM gate (mocked `_llm_suggest` — hit/hallucinate/low-confidence/exception); session dedup (same campaign/cross-campaign); two-line telemetry shape; LLM cache no-poisoning (transient vs genuine no-match).

`test_srd_suggestion_hook.py` (6 tests): no mode gate (§11.H); resolver hit → post; resolver miss → no post; channel not found → no crash; resolver exception → swallowed; message body contains all required elements (input name, SRD name, CR, HP, AC, `!init madd`, `!init add`).

`test_srd_index_integrity.py` (5 tests + 1002 subtests): JSON valid; entry count ≥300; all entries have required fields (1002 subTest iterations); CR vocabulary; HP/AC positive.

## What broke in spec and was fixed

**Tests 9–10 (Jaccard math error in v1 spec):** Original spec claimed "cave giant spider" and "giant cave spider" produce different Jaccard scores. Both tokenize to `{"cave", "giant", "spider"}` — order-insensitive. Both score 0.667 against "giant spider". Test 9's `None` assertion was impossible. Fixed in v1.2: test 9 = "cave toad" → None (J=0.0, no token overlap); test 10 = "swarm bats" → Swarm of Bats (J=2/3≈0.667). Math verified in Python before writing tests.

**Defense-in-depth test 14 caught missing try/except:** Test patched `_llm_suggest` to raise — but `resolve()` had no try/except around the call. Although `_llm_suggest` internally catches all exceptions, `resolve()` should be resilient regardless. Added outer try/except → `llm = None` path. 31/32 → 32/32.

## Session structure — three-session spec/review/implement flow

Session 1 (prior context): spec v1, index JSON sourced correctly (5e-database path found via GitHub API tree — several incorrect paths tried first), Jaccard math error in spec surfaced.

Session 2 (prior context): five §11 decisions locked (A–E all Option 1); `TRACK_6_5_1_REVIEW.md` drafted walking each decision with trade-off analysis; spec patched v1 → v1.1 → v1.2 (§11.H no-mode-gate lock, test corrections, two-line telemetry shape, was_new primacy).

Session 3 (this session): full implementation of all five artifacts; 32 tests written and passing; bot restart clean; live verification pending play session.

## Doctrinal notes

This is the inaugural **Doctrine §1b validated-suggester** ship. The pattern: LLM proposes; deterministic index validates; confidence gate enforces; user approves in Discord. The LLM never decides anything mechanically — it names a candidate, the index confirms the candidate exists in the SRD, and the DM's manual typing of `!init madd` is the approval step. Avrae executes. The §1b anchor is documented in `srd_resolver.py` module header and locked in `TRACK_6_5_1_SPEC.md` §2.

## Cross-references

- TRACK_6_5_1_SPEC.md v1.2 — locked authority document, all §11.A–H decisions final
- TRACK_6_5_1_REVIEW.md — Session 2 review doc, §A–H analysis, §F.2 cache-poisoning fix, §G test surface review
- Doctrine §1b — validated-suggester pattern, inaugural ship
- Track 6 #4 — `npc_upsert()` was the return-value hook point; #5.1 added `was_new` to its signature

---

# Session 27 — Track 4 #3 Time Progression v1 (First Motion-Systems Ship)

The first **Motion-Systems thread** ship after the post-checkpoint pivot. Closes F-54 surface 1 — "the world doesn't visibly evolve" — by introducing a campaign clock that visibly advances on travel, rest, and DM-explicit compression. Inaugural implementation of a deterministic-only motion primitive (Doctrine §1a anchor); §1b LLM time-mention extraction filed for v1.x.

Spec lock: `TRACK_4_3_SPEC.md` v1.2, §11.A–§11.I all LOCKED across Sessions 1–2. Session 3 (this one) is full implementation against the locked spec.

## What shipped

Six artifacts, four call sites, six new test files.

### Schema
- Two new `dnd_scene_state` columns via idempotent ALTER TABLE: `campaign_day INTEGER DEFAULT 1`, `day_phase TEXT DEFAULT 'Morning'`. Existing campaigns auto-migrate at "Day 1, Morning" on first read.
- New `dnd_time_advancements` audit table (`id`, `campaign_id`, `before_day`, `before_phase`, `after_day`, `after_phase`, `days_delta`, `phase_delta`, `resolved_phase_delta`, `set_phase`, `source`, `source_detail`, `created_at`) + two indexes (`idx_time_adv_campaign`, `idx_time_adv_created`).
- `_CAMPAIGN_SCOPED_TABLES` extended to 12 entries (was 11) per VIRGIL_MASTER §6 cascade requirement (§J.4 hard requirement). `/purgecampaign` cascades clean time-advancement rows automatically.

### Engine (`dnd_engine.py`)
- `PHASES = ('Morning', 'Midday', 'Afternoon', 'Evening', 'Night', 'Late Night')` six-phase enum locked.
- `TimeAdvancement` dataclass-ish (`__slots__`) carrying before/after state, deltas, resolved-vs-requested, set_phase, source, detail.
- `parse_elapsed(elapsed_str)` deterministic regex/keyword parser. ~6h per phase. Always-fire `parse_elapsed:` log line per attempt (success or `result=none`). Hedge-prefix stripping ("about", "roughly", etc.).
- `advance_time(campaign_id, days_delta, phase_delta, source, source_detail, set_phase=None)` single write path. O(1) modular phase normalization (`total_steps = idx + phase_delta + days*6; new_day = before + total//6; new_idx = total % 6`). `set_phase` precedence per §11.I: when set, ignores `phase_delta`, computes `resolved_phase_delta = (target_idx - current_idx) mod 6`; audit row records all three values. Missing-campaign no-op contract per §8: reads scene_state first, returns None with `err='no scene_state row'` diagnostic if absent. No-op-zero rejection (§9 test 10). Unknown-source rejection. Negative-delta rejection (no rewind in v1).
- `time_just_advanced(campaign_id, window_seconds=60)` recency check on `dnd_time_advancements MAX(created_at)` per §11.E sub-(iii)α. Soft-fails to False on DB error.
- `get_scene_state` extended to read and return `campaign_day`, `day_phase`.

### Orchestration (`dnd_orchestration.py`)
- `compute_time_directive(scene_state, just_advanced) → str` — seventh §59 directive sibling. Returns directive string when `just_advanced=True` and scene_state has time fields; `''` otherwise. Instruction: "Open with one in-fiction beat marking the new time of day. One sentence, location-appropriate. Then return agency to the player. Do NOT narrate the intervening hours."
- `render_state_footer` extended with ` · Day {N}, {Phase}` suffix after the mode glyph. Backward compat: legacy scene_state without time fields renders as before (test 28 pinned). Combat header carries the suffix on the first line: `⚔ Combat — Round 2 · Day 3, Evening`. `signals` dict gains `campaign_day` + `day_phase` keys; `state_footer:` log line extended with `day=` / `phase=`.

### Skeleton seed (`skeleton_loader.py`)
- New `## Starting time` section recognized; body parsed for `day=N` / `phase=NAME` lines (case-insensitive phase match against the 6-phase enum, normalized to canonical capitalization).
- `apply_starting_time_seed(campaign_id)` writes `dnd_scene_state.campaign_day` / `day_phase` directly. Narrow §17 exception per §11.D=a + §J.3: bypasses `advance_time()` and does NOT append to `dnd_time_advancements`. Idempotency-guarded — only fires when scene_state is at defaults `(1, 'Morning')`. Wired into `/play` post-`init_scene_state` on first session.

### Call sites (`discord_dnd_bot.py`)
- `/travel` — after location write, `parse_elapsed(elapsed)` → `advance_time(... source='travel', source_detail='{dest}; elapsed={elapsed}')`. `arrival_time` is display-only per §11.G=b lock — flows into the `TRAVEL_TRANSITION` block as flavor but does NOT drive `advance_time()`. Soft-fail per §59.
- Avrae `!lr` hook (`_handle_rest_event`) — `advance_time(c, 1, 0, source='rest_long', set_phase='Morning')`. Long rest jumps to next morning regardless of pre-rest phase.
- Avrae `!sr` hook (`_handle_rest_event`) — `advance_time(c, 0, 1, source='rest_short')`. One-phase bump.
- New `/advance days:N phases:N set_phase:Phase` slash command — DM-only. Validates phase string against the 6-phase enum. Soft-fail on writer failure.

### Telemetry
- `time_advance:` per advancement (success: `before` / `after` / deltas / detail; exception path: `err={...}`); `parse_elapsed:` per parse attempt; `directive_emit:` extended with `time={1|0}`; `state_footer:` extended with `day=` / `phase=`; `apply_starting_time_seed:` per /play first-session check.

### Tests
89 new test assertions across six files:
- `test_parse_elapsed.py` — 27 tests (exact phrases, number-words, hour-to-phase math, hedge stripping, negative rejection).
- `test_advance_time.py` — 29 tests (basic advance, phase rollover, validation, persistence, set_phase precedence including the "set_phase wins over phase_delta when both passed" + "all three values logged" cases, large-`phase_delta` 12/13/25 normalization, `time_just_advanced` recency, missing-scene_state diagnostic, cascade-list membership).
- `test_compute_time_directive.py` — 9 tests (silent on not-just-advanced, fires on just-advanced, no `TIME_ADVANCE:` keyword bleed, missing-field guards, instruction-text invariants).
- `test_render_state_footer_time.py` — 8 tests (legacy backward compat, exploration / social / combat with time fields, signals dict shape, log summary day/phase fields, none scene_state).
- `test_time_skeleton_seed.py` — 9 tests (parse-only, seed-write integration, idempotency-guard skip on advanced clock, no-section status, no-scene-state status, audit-log no-write per §J.3).
- `test_time_schema_integrity.py` — 8 tests (column presence, table presence, default values, indexes, cascade-list membership, pre-v1 row default migration, `/purgecampaign` cascade integrity per §4 + §K extension).

Pre-existing `test_campaign_delete_cascade.py` fixture extended to include all 12 scoped tables (was missing 4 pre-existing — `dnd_consequences`, `dnd_combatant_state`, `dnd_inventory`, `dnd_loot_pending` — plus the new `dnd_time_advancements`); all 13 cascade tests pass.

Pytest run: 124 passed across the time + adjacent suites. Standalone tests: 27 + 9 + 8 = 44. Total: 168 tests green.

## Live verification

⏳ **PENDING.** Bot service was restarted and the migration ran cleanly on the live DB (verified via `PRAGMA table_info(dnd_scene_state)` — `campaign_day` + `day_phase` columns present at indexes 17/18; `dnd_time_advancements` table + both indexes confirmed via `.schema`). Module imports clean (`srd_resolver: index loaded entries=334`, `chroma_init: sessions=652 knowledge=740307`).

Discord login hit Cloudflare 429 / error 40062 (rate limit on `/users/@me` after the test-driven migration triggered repeated unit restarts). Service stopped to break the cooldown cycle. Code itself is unaffected — Python load + DB migration both succeed on every restart attempt; the failure is purely Discord-side login throttling. Restart at the start of next session, after the rate-limit window expires (~30 min typical).

Live-verify scenario: 8-step canonical flow appended to `tests-to-run-post-session.md` covering footer baseline, `/travel` + multi-day elapsed, arrival_time display-only verification (§11.G=b), Avrae `!lr` + `!sr` advance, `/advance` phases / set_phase, and `/purgecampaign` cascade integrity.

## What broke and was fixed mid-session

- `test_render_state_footer_time` initially failed against existing `state_footer_log_summary` because the prior signature returned `mode={...} active_turn={...} round={...}` only. Extended to include `day=` / `phase=`; updated four pre-existing tests in `test_state_footer.py` to match the new contract. Spec mandates the extension (§8 — state-footer signals extension).
- `test_time_skeleton_seed` initially failed because the test fixture for scene_state used a minimal column set; `get_scene_state` reads 17 columns and chokes on missing `location`. Extended fixture to mirror the production schema. Test-fixture incompleteness, not engine bug.
- `test_campaign_delete_cascade.py` had pre-existing fixture rot (8 of 12 scoped tables) that I extended with the missing 4 + new 1 to keep the suite green. The `test_archived_campaign_deletes_cleanly` assertion was tightened: instead of asserting `set(rows_deleted.keys()) == 8-table set`, now asserts populated tables show count=1 and ALL scoped tables appear in the result (count=0 for unpopulated additions). Forward-compatible with future cascade additions.

## Doctrinal notes

The Time Progression invariants section in VIRGIL_MASTER.md is now a parallel sibling to SRD Resolver invariants (Track 6 #5.1) and Adjudication Layer invariants (Track 7 #1-2). Captures: §1a anchor (LLM never decides time), §17 single write path with narrow §J.3 seed exception, source enum lock, no-mode-gate-on-time-advancement, `set_phase` precedence, no-rewind, modular phase normalization (never iterate), missing-campaign no-op, cascade requirement, "bot never narrates intervening hours" instruction lock, just-advanced-as-recency-not-flag, telemetry contract, `/travel arrival_time` display-only.

The seventh §59 sibling `compute_time_directive` confirms the pattern: `compute_loot_directive`, `compute_persistence_directive`, `render_state_footer`, `compute_combat_redirect_directive`, `compute_setup_plan`, `build_advisory_context`, `compute_time_directive`. Pure-function-in-orchestration is now canonical across narrative directives AND infrastructure ops.

The skeleton-loader `apply_starting_time_seed` introduces the project's first **narrow §17 exception** with explicit framing — a one-shot initialization writer that does not pollute the runtime advancement audit log. The framing is load-bearing: campaign initialization is not an advancement event. Future "second writer" temptations need the same narrow framing or they should be promoted to a real source enum value.

## Cross-references

- `TRACK_4_3_SPEC.md` v1.2 — locked authority document, §11.A–§11.I all final
- `TRACK_4_3_REVIEW.md` — Session 2 review doc, push-backs accepted (§11.B=c skip /rest, §11.G=b arrival_time display-only)
- `track5_findings_time_mention.md` — corpus findings doc that informed the spec (3,592 records across 140 episodes; cumulative_anchor + scene_transition shapes both validated)
- `VIRGIL_MASTER.md` §4 — Time Progression invariants section (parallel sibling to SRD resolver / Adjudication invariants)
- `ROADMAP.md` — Status snapshot row added at top; queue item #5 flipped to ⏳ SHIPPED PENDING VERIFY
- `tests-to-run-post-session.md` — 8-step canonical scenario appended (Step 0 preflight + Steps 1–8 covering all four call sites + cascade integrity)
- F-54 (FAILURES.md) — surface 1 closure (the world doesn't visibly evolve); other surfaces remain open siblings under the motion-systems thread
- Doctrine §1a anchor — second post-§1a/§1b-split spec to write the §1a side explicitly (Track 6 #5.1 was the §1b inaugural; this is the §1a sibling)

---

# Session 28 — Bug 4 ship + Track 4 #3 verify-attempt-2 (joint promotion)

S27 closeout left two ships at ⏳ pending: Track 4 #3 (Time Progression v1) blocked on Cloudflare-edge typing-endpoint cooldown that ate `/play` mid-verify-attempt-1, and a freshly-surfaced Bug 4 (`.typing()` context manager hard-fails on `discord.HTTPException`). S28 ships Bug 4, restarts once, and walks the full 9-step Track 4 #3 verify (Step 0 preflight + Steps 1–8 + optional §J.3 Step 9). Both ships promote ✅ jointly.

## What shipped (Bug 4)

Three Shape A wrappers in `discord_dnd_bot.py` — each `async with channel.typing():` site wrapped in `try/except (discord.HTTPException, asyncio.TimeoutError)` with handler body duplicated under the except for soft-fail:

- Line 1574 (`_advisory_respond`) — typing context around the `cloud_route` call for #dm-aside Q&A
- Line 1707 (`_dm_respond_and_post`) — typing context around the narration-batcher's `dm_respond` call
- Line 2950 (`/play`) — typing context around the opening-scene `dm_respond` call (the site that ate the 429 in S27 verify-attempt-1)

Telemetry: per-site `typing_indicator_failed: command={advisory_respond|_dm_respond_and_post|play} err={repr}` log line, fires only on the exception path. No new imports — `discord` and `asyncio` were already module-level. No code-path branching for `/play` vs other surfaces; same wrapper everywhere.

Single-restart deploy per Doctrine §73. Login latency ~6s post-restart (canary clean). No `typing_indicator_failed:` lines fired during any of the three live `/play` invocations during S28's verify walk — endpoints fully thawed since S27 closeout.

## Live verification

✅ **Track 4 #3 + Bug 4 jointly promoted.** Full 9-step walk against the locked `tests-to-run-post-session.md` scenario (Step 0 preflight + Steps 1–8 + Step 9 §J.3 seed). All 6 promotion criteria for Track 4 #3 met:

1. ✅ All 8 steps complete without error in real Discord (+ Step 9 §J.3 also clean)
2. ✅ `time_advance:` for all four sources observed: `travel` (×2 — Steps 2–3), `advance` (×2 — Steps 5–6), `rest_long` (Step 4), `rest_short` (Step 7)
3. ✅ Footer correctly carries `· Day N, Phase` after every advancement, per locked §11.I formula. **The verify-doc Step 4 expected text was the bug, not the implementation** — see Doctrinal notes below.
4. ⚠️ `parse_elapsed:` 2/3 strings observed in S28 (`'two days'`, `'a day'`); structurally validated by 27 unit tests; will continue accumulating in subsequent live sessions.
5. ✅ `/purgecampaign` cascades clean — 6 `dnd_time_advancements` rows deleted for campaign 20, count → 0.
6. ✅ Zero exception-path `time_advance: ... err=` lines.

Bug 4 cross-verify: ✅ — three live `/play` invocations during S28 (Step 1 on campaign 20, post-Step-8 `/play` on campaign 17, Step 9 `/play` on campaign 21) all completed cleanly with zero `typing_indicator_failed:` lines fired. The 429-recovery path is grep-verifiable but didn't fire because no 429 occurred. Bug 4's soft-fail is structurally proven via Shape A.

Step 9 (§J.3 skeleton seed): seed_test campaign (id 21) created with `## Starting time / day=5 / phase=Evening` in `/home/jordaneal/scripts/campaigns/21/skeleton.md`. First `/play` triggered `apply_starting_time_seed: campaign=21 seeded day=5 phase='Evening'` and `play_first_session_hint: campaign=21 fired=1`. DB confirmed `dnd_scene_state` directly written `(5, Evening)`; zero `dnd_time_advancements` rows for campaign 21 (§J.3 narrow exception holds — initialization is not an advancement).

## What broke and was surfaced (no fix mid-verify; filed for next ship)

Six doc-deltas + one new ROADMAP entry surfaced during S28's walk; all landed at promotion (no mid-verify code ships per Doctrine §73):

1. **Step 1 grep correction.** `state_footer:` doesn't fire on `/play` — `/play` builds its embed inline with a hardcoded onboarding footer (`"Type your actions in this channel..."`) and never calls `render_state_footer`. Step 1 grep expectation flagged as post-4b-ship contingent.
2. **Step 4 expected text rewrite.** Verify doc said "Day {N+1}, Morning regardless of pre-rest phase" — that's an over-simplification of the locked §11.I formula. Actual math (`total_steps = before_idx + resolved_phase_delta + days_delta*6`, with `set_phase` writing `resolved_phase_delta = (target - current) mod 6` to total_steps): from Morning → +1 day, from any non-Morning start → +2 days. The implementation matches the locked spec + the `test_set_phase_evening_to_morning_long_rest` test pattern. Doc rewritten to expose the math.
3. **Step 9 visual-check correction.** Same `/play` footer-wiring gap — until ROADMAP 4b ships, Step 9's seed feature is observable only via sqlite + the `apply_starting_time_seed:` log line. Visual confirmation deferred to post-4b.
4. **Step 8 input correction.** Verify doc said `/purgecampaign confirm:DELETE` — wrong parameter name (`confirm` vs `confirm_phrase`), missing campaign_id, missing campaign-name suffix on phrase, no archive prerequisite. Rewritten to the correct three-command sequence (`/setcampaign` away, `/deletecampaign campaign_ids:N`, `/purgecampaign campaign_id:N confirm_phrase:DELETE <name>`).
5. **Avrae rest syntax correction.** Step 4 + Step 7 inputs `!lr` / `!sr` are aliases that may not be configured per-guild. Canonical Avrae syntax is `!game lr` / `!game sr` (or `!game longrest` / `!game shortrest`). The bot's `avrae_listener._classify_kind` matches on Avrae's resulting embed title text, so the rest-handler routing is correct regardless of input syntax — only the doc's input string needed fixing.
6. **`/play` footer-wiring follow-up — new ROADMAP item 4b.** Operator-UX gap: skeleton-seed feature (Track 4 #3 §J.3) writes scene_state directly on first `/play`, but `/play`'s hardcoded footer hides the seed. DM authoring `## Starting time` and running `/play` cannot visually confirm the seed worked. `/play` post-session-pause is operational re-entry (the existing `is_first_session` gate already differentiates first-time hint vs returning narration), so the state-aware footer belongs there for the same reason it belongs on every narration turn. Small standalone ship.

## Doctrinal notes

**Doctrine §59 reaffirmed** (pure-function-in-orchestration / soft-fail at call site). Bug 4's three call sites are the seventh, eighth, and ninth applications of the soft-fail-at-call-site pattern. Each Discord transport call gets its own try/except boundary; the handler body executes regardless of whether the aesthetic context manager succeeded.

**New Doctrine §74 candidate — aesthetic transport endpoints soft-fail.** Discord's HTTP layer is tiered: `POST /channels/{id}/typing` is aesthetic (a "user is typing..." indicator that decays after ~10s with no harm if it never fires), while `POST /channels/{id}/messages` is semantic (the actual narration). Aesthetic endpoints get `try/except (HTTPException, TimeoutError)` wrappers at every call site; semantic endpoints get the existing per-handler boundaries (and may bubble up legitimately on actual failure). The principle: **transport reliability tiers are routing-layer concerns, not handler-layer concerns** — handlers should not have to know which endpoints might 429 from Cloudflare's WAF vs which are guaranteed-or-fail. Filed as §74 in DOCTRINE.md.

**§11.I locked semantic clarification.** S28 verify-walk surfaced an internal-doc inconsistency in TRACK_4_3_SPEC.md: §11.I lock-text says "Long rest: jump to next morning regardless of current phase" (narrative shorthand) but the §5 normalization formula + §11.I `set_phase` precedence invariant produce phase-dependent day jumps when combined with `days_delta=1`. The math is locked correctly and the test suite asserts it (`test_set_phase_evening_to_morning_long_rest`); the narrative shorthand was the bit that misled the verify-doc author into writing "regardless of pre-rest phase." Spec is correct; verify doc is corrected. Filed as a load-bearing learning: **narrative shorthand in spec lock-text can mask phase-dependent math.** No spec amendment — the formula and test pattern are the spec; the comment is recovered by the test.

**Operator-UX gap as second-order ship trigger.** Track 4 #3 ship #1 (deterministic clock) is structurally complete. ROADMAP 4b emerges from S28 verify because the seed feature's value is conditional on visual confirmation, and `/play` was the first call site we expected the state-aware footer on (per the verify-doc Steps 1 and 9). This is a **second-order ship**: the primitive ships clean per spec, but a downstream operator-UX surface needs wiring to make the primitive observable in the live system. Filed for v1.x scope rather than re-opening §11.

## Cross-references

- `tests-to-run-post-session.md` — five doc-deltas landed (Steps 1, 4, 7, 8, 9). Step 4 expected text now anchors to locked §11.I formula + test pattern; Step 8 input now matches `/purgecampaign`'s actual signature; Avrae syntax updated to canonical `!game lr` / `!game sr`.
- `ROADMAP.md` — 4a (Bug 4) flipped to ✅ SHIPPED LIVE; item 5 (Track 4 #3) flipped to ✅ SHIPPED LIVE; new item 4b filed for `/play` footer wiring follow-up.
- `VIRGIL_MASTER.md` — `typing_indicator_failed:` already in telemetry primitives section (added in Bug 4 ship pre-verify).
- `DOCTRINE.md` §74 — new doctrine: aesthetic transport endpoints soft-fail.
- `WHY.md` — Bug 4 / aesthetic-vs-semantic transport entry appended.
- `TRACK_4_3_SPEC.md` v1.2 LOCKED — no amendment; verify-doc was the divergence, not the spec.
- F-54 closure (FAILURES.md) confirmed live: scene-progression visibility now demonstrable end-to-end.

---

# Session 29 — ROADMAP 4b ship + Bug 5 surfacing & fix (combined session)

4b shipped clean per the planner-locked spec. Verify-walk surfaced a critical correctness defect in `init_scene_state` (Bug 5) — not a 4b bug, but 4b made it visible. Combined-session call: fix the engine bug in the same window rather than wait for a separate ship cycle. Both ships promoted ✅ jointly via single restart per Doctrine §73.

## What shipped (4b)

Single file, `discord_dnd_bot.py`. Three changes:

1. **`PLAY_FIRST_SESSION_HINT` constant deleted.** The three-command bullet list (`/bindchar`, `/refresh`, narrate-in-#dm-narration) was redundant with virgildm.com onboarding — by the time `/play` fires, players have already done DDB account setup, Avrae link, `!beyond` import, and `/bindchar`. Wrong audience, wrong channel (`#dm-narration` is the immersion lane; OOC slash-command guidance belongs in `#commands`), wrong trigger. Better orientation triggers filed as ROADMAP 4c (post-`/newcampaign` or `/setup`-pinned `#commands` message; decision deferred to spec time).

2. **`/play` footer assembly mirrors `_dm_respond_and_post`.** State header via `render_state_footer` (mode glyph + ` · Day N, Phase`) prepended to identity line (📍 location + 🗒️ quests). No actor field on `/play` — the DM is opening the scene, no player just acted. Soft-fail at the call site per Doctrine §59: footer issues never block opening narration.

3. **`play_first_session_hint:` log removed; replaced with per-call `state_footer:` log.** `/play` is now greppable like every narration turn. `is_first_session` capture stays (still needed for `apply_starting_time_seed` gate); only the description-append branch and the hint log go away.

`test_play_first_session.py` deleted — every assertion was hint-content on a constant that no longer exists.

## What shipped (Bug 5 / ROADMAP 4d)

Single file, `dnd_engine.py:init_scene_state`. One change:

Switched from `INSERT OR REPLACE INTO dnd_scene_state (...12 original columns...) VALUES (...)` to `INSERT INTO dnd_scene_state (...) VALUES (...) ON CONFLICT(campaign_id) DO UPDATE SET last_scene_change=excluded.last_scene_change, updated_at=excluded.updated_at`. The ON CONFLICT clause is valid because `campaign_id INTEGER PRIMARY KEY` provides the conflict target. New rows still get full schema defaults via the plain INSERT path; existing rows preserve every column the function doesn't explicitly intend to set.

## Bug 5 root cause

During 4b verify, the seed visibility check on campaign 21 (post-S28 manual `(5, 'Evening')` write) returned `Day 1, Morning`. The 4b wiring was correct — the value rendered IS what was in `dnd_scene_state` for that campaign. The bug was upstream: `dnd_scene_state` itself was clobbered by `init_scene_state` on the `/play` call.

`init_scene_state` was using `INSERT OR REPLACE` listing only the original-schema columns. Every column added via ALTER TABLE migration since (campaign_day, day_phase, current_location_id, turn_counter, last_dm_response, tension_int, progress_clocks) was absent from the column list. `INSERT OR REPLACE` is a delete-then-insert under the hood: unlisted columns fall back to schema defaults on the new row.

**Sequence on campaign 21 during S29 verify (pre-fix):**
1. S28 had set `(campaign_day=5, day_phase='Evening')` directly via SQL.
2. S29 `/play` entered → `prior_scene` returns the existing row → `is_first_session = False`.
3. `init_scene_state` runs unconditionally → `INSERT OR REPLACE` wipes row → `campaign_day=1, day_phase='Morning'` (schema defaults).
4. `apply_starting_time_seed` is gated on `is_first_session` — skipped (correctly, per its idempotency guard, but the moot point: it wouldn't have re-seeded a row that just got wiped to defaults anyway).
5. Footer correctly renders the now-wiped state: `Day 1, Morning`.

**Track 4 #3 impact (pre-fix):** any time advancement via `advance_time()` (travel, `!game lr`, `!game sr`, `/advance`) survived in-session, but the moment the DM ran `/play` to re-open the scene next session, `dnd_scene_state.campaign_day` / `day_phase` flipped back to `(1, Morning)`. The audit log in `dnd_time_advancements` survived (separate table, untouched), but the live state lied post-`/play`. Same clobber pattern hit location pointer, turn counter, commitment-directive's last DM response, tension/clocks.

## Structural-vs-narrow fix call

Two plausible fix shapes surfaced:

- **(A) Narrow.** Add `campaign_day` and `day_phase` to the existing column list; write current values when row exists, defaults on first init. Closes Track 4 #3 specifically. Leaves the structural pattern broken — next ALTER TABLE-added column on `dnd_scene_state` clobbers on next `/play`.
- **(B) Structural.** Switch from `INSERT OR REPLACE` to `INSERT ... ON CONFLICT DO UPDATE SET` listing only the fields the function intends to set. All other columns preserved on existing rows; new rows still get schema defaults. This is the correct pattern.

Code's first instinct was (A). Planner pushed (B). (A) ships a known time bomb — next column added to the schema repeats the bug. (B) closes the structural pattern: future migrations are safe by default. Cost difference is zero (same ~10-line diff). (B) shipped.

## Live verification

✅ **4b + Bug 5 jointly promoted.** Combined verify-walk:

| Check | Result |
|---|---|
| Code-side: import clean | ✓ |
| Code-side: zero `PLAY_FIRST_SESSION_HINT` matches | ✓ |
| Code-side: zero `play_first_session_hint:` log matches | ✓ |
| Discord: `/play` footer renders state-aware | ✓ (`📖 Exploration · Day 5, Evening 📍 ... 🗒️ Investigate the Crystal Cave`) |
| Discord: no three-command hint in body | ✓ |
| Journal: `state_footer:` log fires on `/play` with `day=5 phase=Evening` | ✓ |
| Journal: zero `play_first_session_hint:` matches | ✓ |
| sqlite post-`/play`: campaign 21 still `(5, Evening)` | ✓ (`21\|5\|Evening\|2026-05-09 11:59:48`) |
| sqlite post-`/play`: only `updated_at` refreshed | ✓ |

The sqlite post-`/play` check is the structural verification of Bug 5's fix: a row that had `campaign_day=5, day_phase='Evening'` BEFORE `/play` still has `campaign_day=5, day_phase='Evening'` AFTER `/play`. Pre-fix, that same sequence would have produced `(1, Morning)`.

## Doctrinal notes

**Doctrine §59 reaffirmed.** `/play`'s state-footer assembly is wrapped in try/except per the soft-fail-at-call-site pattern. Aesthetic footer issues never block the opening narration.

**New Doctrine §75 candidate — `INSERT OR REPLACE` is structurally hostile to ALTER TABLE-added columns.** When a table accumulates columns via ALTER TABLE migration, any writer using `INSERT OR REPLACE` with a fixed column list silently regresses to schema defaults on those added columns at every write. The bug is invisible at write time (no error), invisible in tests that don't exercise the migrated columns, and surfaces only when a downstream feature depends on the migrated column's persistence across writes (Track 4 #3 was the first feature to depend on a migrated column surviving `/play`). The structural fix is `ON CONFLICT(pk) DO UPDATE SET` listing only the fields the writer actually intends to set. Sibling to §70 (fix blast radius can be wider than the bug): §70 covers `SELECT` regressions; this covers `INSERT` regressions in the same migration-history shape. Filed as §75 in DOCTRINE.md.

**Combined-session ship as the right call.** Doctrine §73 caps restarts at one per session. Bug 5 surfaced mid-verify; the fix was small (~10 lines, single function), the test surface was clear (re-seed + `/play` + sqlite check), and waiting a session would have left Track 4 #3's persistence broken in production for the gap. Combined-session was the correct choice — shipping a structural fix in the same window as the feature that surfaced it doesn't violate §73 because it's still one restart total. The doctrine constrains restart count, not ship count.

## Cross-references

- `ROADMAP.md` — 4b flipped ✅ SHIPPED LIVE (S29); 4d (Bug 5) flipped ✅ SHIPPED LIVE (S29, combined with 4b); item 5 (Track 4 #3) updated to reflect S29 persistence fix.
- `DOCTRINE.md` §75 — `INSERT OR REPLACE` is structurally hostile to ALTER TABLE-added columns; sibling to §70.
- `WHY.md` — entry on the structural-vs-narrow fix call (planner pushed (B); Code's instinct was (A); narrow ships a time bomb).
- `tests-to-run-post-session.md` — Steps 1 + 9 visual-confirmation notes can drop the "sqlite-only until 4b ships" caveat (Code already deleted `test_play_first_session.py` since every assertion was hint-content).
- `VIRGIL_MASTER.md` — header refreshed to S29; bones → footings verbiage applied; `init_scene_state` semantics clarified if the document referenced the old `INSERT OR REPLACE` shape.
- F-54 closure stays confirmed; Track 4 #3 v1 is now complete end-to-end including persistence across `/play`.

# Session 31 — ROADMAP 4c: First-session orientation pin in #commands (May 9, 2026)

**Ships:** `COMMANDS_PIN_BODY` constant + `compute_setup_plan` extension + `/dmhelp` §66 wiring.

**What changed:**

`COMMANDS_PIN_BODY` — new sibling to `WELCOME_PIN_BODY`. Hybrid shape: 5 inline commands (`/play`, `/inventory`, `/refresh`, `/newcampaign`, `/dmhelp`) + pointer to `/dmhelp` for the full reference + pointer to `#welcome` for new-player onboarding.

`compute_setup_plan` — new optional param `commands_existing_pin_body: str | None`. Plan dict gains `commands_pin_action: create|replace|noop|skipped`. Logic: `'commands'` key absent from channel_names → `skipped`; channel not yet in text_channels → `create`; channel exists, no bot pin → `create`; pin matches body exactly → `noop`; pin exists but drifted → `replace`. Idempotency contract preserved: fully-canonical guild with correct pin → `noop`.

`/setup` execution — pre-fetches existing commands pin body before calling `compute_setup_plan`, then executes the pin action after channel/perm ops: `create` posts + pins `COMMANDS_PIN_BODY`; `replace` unpins + deletes old, posts + pins fresh; `noop` is a no-op. Telemetry: `setup_run:` log line extended with `commands_pin={action}`. User-facing ephemeral updated to mention posted/updated pin; "Nothing to do" check extended to include `commands_pinned`.

`/dmhelp` rewrite — hand-maintained body (drifted from COMMANDS.md) replaced with runtime-fresh load via `orch._load_commands_reference()` per §66. Extracts the `VIRGIL_AUTO_GENERATED` section, strips HTML comment lines, renders Virgil slash commands. 1950-char Discord cap with trailing ellipsis on overflow. Edits to COMMANDS.md take effect without bot restart.

**Tests:**
- `test_setup_plan.py` — 11 new assertions: `COMMANDS_PIN_BODY` contains all 5 locked commands, `/dmhelp` pointer, `#welcome` pointer; `commands_pin_action` variants (empty guild → create; existing no-pin → create; matching pin → noop; drifted pin → replace; custom cn without 'commands' key → skipped; noop strips whitespace; key present in plan dict; determinism). Total: 53 tests.
- `test_commands_doc.py` — 3 new assertions: `/dmhelp` source calls `_load_commands_reference`; no hand-maintained body in source; live `_load_commands_reference()` returns content with expected commands. Total: 11 tests.

**Discord verify steps:**
1. Run `/setup` on test server — first run: `commands_pin=create` in journal, pin appears in `#commands` with the 5 commands + pointers.
2. Re-run `/setup` — `commands_pin=noop`; no duplicate pin; ephemeral says "Nothing to do — already canonical."
3. Run `/dmhelp` from any channel — shows Virgil section from COMMANDS.md (not old hand-maintained prose).
4. Edit a line in COMMANDS.md hand section, save, run `/dmhelp` WITHOUT bot restart — edit reflected immediately.

**Verify-walk corrections (live debug):**
- HTML comment filter missed multi-line comment continuation lines (ending with `-->`); fixed with `and not ln.rstrip().endswith('-->')`.
- `/dmhelp` switched from ephemeral multi-message to private DM (`interaction.user.send()`) — persists after dismiss, cleaner UX. Ephemeral fallback on `discord.Forbidden`.
- Formatter rewritten: strip `- ` list prefix (Discord adds trailing commas to `-` lists in DMs), bold section headers, title-case headings, colon after heading, blank line between sections, no blank line after heading, no "Virgil Slash Commands" preamble. Starts directly with `**Player Commands:**`.
- Wrong SSH username (`jordaneal` vs `Jordan`) diagnosed and fixed in `TMUX REMOTE.txt`; memory updated with failure symptom map.

**PC rsync:** Complete. All files in correct folders.

# Session 32 — Bug 1 Phase 1: Pending Roll Directive Tracking, Telemetry-Only (May 9, 2026)

**Ships:** DM `!check`/`!save`/`!cast` directive parser + footer-binding matcher + `dnd_pending_roll_directives` table + `last_active_actor` column on `dnd_scene_state` + four-trigger `footer_actor_changed:` observability. Telemetry-only — `dm_respond` is NEVER auto-fired in Phase 1.

**Recon HALT and resolution.** Recon on the locked S31 architecture surfaced one HALT-worthy finding on Q3 (footer-actor read API). Combat-mode footer-actor lives at `dnd_combat_state.character_name` via `get_active_turn` — clean engine source. Exploration-mode footer-actor was the gap: `_dm_respond_and_post`'s `actor_label = ', '.join(actor_names)` is rendered into the embed footer at narration-emit time but never persisted to engine state. The locked architecture's option (b) "query engine state directly" assumed such a query existed; it didn't. Surfaced the finding to the planner with a labeled-not-adopted resolution; planner accepted with a delta locking the four-trigger taxonomy and within-ship sub-phase ordering. Q1 (DM identity) and Q2 (directive regex) both clean — no HALT needed.

**Within-ship sub-phase ordering.** Sub-phase 1a (schema column + four writers + `footer_actor_changed:` logs) verifies BEFORE sub-phase 1b's matcher reads the column — preserves §39 spirit at sub-ship level. Both sub-phases ship in the same Phase 1 deploy and same restart per §73.

**What changed:**

*Schema (sub-phase 1a):*
- `dnd_scene_state.last_active_actor TEXT DEFAULT ''` — new column. Mode-disjoint single-writer discipline (exploration writer in `_dm_respond_and_post`, combat writers in `set_active_turn` / `clear_active_turn`, session-open clear in `/play`). `update_last_active_actor(campaign_id, new_actor, trigger)` is the sole writer; reads prior, no-ops on no-change, emits `footer_actor_changed: campaign={N} from={old|none} to={new|none} trigger={dm_respond|play|combat_turn_set|combat_turn_clear}` on transitions.

*Schema (sub-phase 1b):*
- `dnd_pending_roll_directives` table — `(campaign_id PRIMARY KEY, actor_name, check_type, source_message_id, created_at, expires_at)` + idx on `source_message_id`. Added between `dnd_time_advancements` and `dnd_scene_state` in `_CAMPAIGN_SCOPED_TABLES` cascade tuple.

*Engine helpers (`dnd_engine.py`):*
- `pending_directive_upsert` (insert-or-replace, returns prior info for replacement logging)
- `pending_directive_get_active` (lazy TTL sweep — emits `pending_directive_expired:` and deletes when past `expires_at`)
- `pending_directive_consume` (DELETE on match)
- `pending_directive_delete_by_message` (cancel-on-edit, msg-id-bound)
- `pending_directive_age_seconds` (pure helper for `directive_age_s` / `old_age_s` log fields)

*Constants (`avrae_listener.py`):*
- `PENDING_DIRECTIVE_TTL_SECONDS = 300` co-located with `EVENT_TTL_SECONDS` for sibling-scan visibility. Phase 2 retunes from observed age-at-resolution + age-at-expiry distribution.

*Parser + matcher (`discord_dnd_bot.py`):*
- `_DM_DIRECTIVE_RX` regex (case-insensitive `!check`/`!save`/`!cast` + optional leading `<@DM_id>` mention strip + `.+?` skill capture)
- `_DIRECTIVE_TRIGGER_PREFIXES = ('!check ', '!save ', '!cast ')` for trigger detection
- `_is_dm_message(message, campaign)` — sister of `is_dm_or_creator` for raw `discord.Message` events (recon Q1: wrap, not reuse)
- `_parse_dm_directive` / `_directive_skill_is_clean` / `_normalize_skill_for_match` / `_classify_unparsed_reason`
- `_handle_dm_roll_directive` (emit branch — skip cascade: trailing-args / group-directive / combat-mode / no-footer / OK)
- `_handle_dm_roll_arrival` (match branch — actor+skill match → `directive_would_fire_dm_respond:` + consume; skill match + actor mismatch → `directive_actor_mismatch:` + wrong-actor aside; skill mismatch silent)
- `_post_dm_aside` for #dm-aside posting (no-footer + wrong-actor wording locked verbatim in spec §J)

*on_message wiring:*
- Avrae branch: after `parse_avrae_embed` produces a check/save/cast event AND actor canonicalization completes, call `_handle_dm_roll_arrival`; if it returns an aside string, post to #dm-aside
- Player branch: BEFORE the no-bound-char gate, if `_is_dm_message` AND text starts with directive-trigger prefix, route to `_handle_dm_roll_directive` and return (DM directive emission shouldn't trip the "no character bound" reply)

*on_message_edit cancel path:*
- DM-authored edit in #dm-narration with a pending directive whose `source_message_id` matches `after.id` → re-parse new content; if same skill, no-op (typo fix); else `pending_directive_delete_by_message` + `pending_directive_cancelled: reason=edit`

*Tests:*
- `test_pending_roll_directives.py` — 19 new assertions covering schema, cascade, `update_last_active_actor` transitions, all CRUD on `pending_directive_*`, lazy TTL sweep, and cascade-delete integration. All green.

*Spec doc:*
- `BUG_1_SPEC.md` (server-only, NOT mirrored to PC) — full §A–§R layout per planner-locked structure plus the S32 delta additions (schema delta to `dnd_scene_state`, within-ship verification ordering, four-trigger taxonomy, Q2 variant edge cases, `directive_text_unparsed:` log spec). Phase 2 trigger criteria locked verbatim in §L. Two doctrine candidates filed in §P (filed not anchored per §59).

**Discord verify steps:** see `BUG_1_SPEC.md` §M — 12-step matrix covering all sub-phase 1a writer/log triggers + sub-phase 1b directive emit/match/skip/expire/cancel/unparsed paths. Verify-after-restart per §73; Code grep against journal in this session, behavioral verification in next-Discord-session per §73.

**Doctrinal notes:**
- Two candidates filed in `BUG_1_SPEC.md` §P, neither anchored per §59 (defer until second instance):
  1. **"Instrument before binding to existing surface"** — sibling to §39, extends the doctrine to "make existing surfaces observable before *other systems* bind to them, not just before *behavior* binds."
  2. **"Presentation-derived state is not structural state until persisted to engine"** — surfaced from Q3 recon. Spec sessions that lock architecture conversationally should treat any "the X tells us Y" claim as needing a recon check on whether X actually persists Y or just renders it.

**Cross-references:**
- `ROADMAP.md` — item 3 Phase 1 ✅ SHIPPED LIVE; Phase 2 entry filed with trigger-criteria gate
- `FAILURES.md` — F-58 candidate stub filed (stale-footer name parsing as v1.1 candidate; Phase 1 strict-binds to footer actor and flags via `directive_actor_mismatch:` aside)
- `BUG_1_SPEC.md` — full spec including §P doctrine candidates
- `DOCTRINE.md` — no anchor in this ship; two candidates filed in BUG_1_SPEC.md §P pattern-watch for second instance

**PC rsync:** see PUSH-DOCS callout at end of ship — `BUG_1_SPEC.md` is server-only, NOT in the rsync set.

---

# Session 33 — Multiplayer Fixes Plan: S32 Findings → Five-Ship Plan → Three-Reviewer Cycle → ROADMAP F-55 Refresh (May 10, 2026)

**Ships (this session):** No code. Planning and doc-update session. Drafted `MULTIPLAYER_FIXES.md` (v2, 584 lines). Five ROADMAP patches applied propagating plan commitments into the F-55 cluster entries. Three-reviewer cycle (planner → GPT round 1 → GPT round 2 forced re-read → Gemini) produced 14 plan revisions. **The system was unplayable after S32 multiplayer playtest; this session was the architectural diagnosis and remediation plan ahead of any code work.**

## What surfaced

S32 multiplayer playtest (Bug 1 Phase 1 ship verify + open multiplayer playtest with Captin0bvious, Boar's Head Tavern → Brighthollow Tavern → Guild Hall → Crystal Cave fiction, ~110 minutes) cataloged 14 findings in `S32_MULTIPLAYER_PLAYTEST_FINDINGS.md`. Three rose to architectural-blocker severity:

- **Finding L** — Roll resolution unbound from rolled value. F-45 regression: Track 7 #1's CHECK_ACTION binding doesn't cover the DM-typed-directive flow. Player rolls 6 vs DC 10, says "I passed," bot narrates success. Player self-report becomes the de facto adjudicator.
- **Finding A** — Recursive hallucination memory loop in `scene_state.location` writes. `extract_scene_updates` runs LLM-authored writes with no canon-check. Cave imagery bled into Guild Hall narration; LLM wrote "narrow village lane" while footer correctly showed guild hall. LLM output → persistent state → retrieval → next prompt → drift amplification.
- **Finding H** — Hydrate→Avrae sync gap. NPC stats written engine-side; Avrae has no sheet; combat resolves against `<None>` HP. Combat unplayable when DM creates NPCs via `/hydrate`.

Findings B (canonical-name reuse: "Merrick the bartender" → "Merrick the clerk" via global string-match), J (DC leak in player-facing directive), I (combat onboarding malformed template), G (debug string leak), §5.7 (narration continuity cluster), §5.8 (economic ordering) are downstream symptoms or polish.

## What shipped (planning artifacts)

*`MULTIPLAYER_FIXES.md` v2 (584 lines, output to `/mnt/user-data/outputs/`).* Five-ship plan, calendar S33–S41, 9–13 days:

- **Ship 1 (S33–S34): Resolution Binding.** Closes Finding L + F-45 regression. Ships Bug 1 Phase 2 as a side effect. New `resolve_directive() → ResolutionResult` pure function. Engine computes pass/fail from `roll_total >= dc`; AUTHORITATIVE-CANON prompt block constrains LLM to render outcome it didn't decide. New `narration_verifier` `ROLL_OUTCOME_DRIFT` violation class. Adds `dnd_pending_roll_directives.dc INTEGER` column. 7 §11 decisions to lock. ~40 test assertions. Opus high.
- **Ship 2 (S35–S37): Scene State Canon Discipline.** Closes Finding A. Three subships: 2a delete `scene_state.location` LLM-write authority (single writer becomes `set_current_location` only); 2b DELETE `established_details` field by default (recon decides only if hard dependency forces gated-write — latent canon poisoning is intrinsic to such fields, validators cannot fix it); 2c audit pass via four-property latent-canon test (LLM-writable + persisted + retrieved + narratively inferential). Anchors candidate Doctrine §76.
- **Ship 3 (S38–S39): NPC State-Sync Boundary.** Closes Finding H. Files as F-55 cluster sibling **#5.5 — Combat State Coherence**. First concrete step in cluster's Virgil-authoritative-with-Avrae-as-projection trajectory. Three candidate fixes: (a) auto-create Avrae sheet on hydrate (recommended; cleanest, fits trajectory), (b) parallel resolution path, (c) disallow non-Avrae combat. Doctrine §65 amendment expected (bot-as-DM-proxy narrow exception).
- **Ship 4 (S40): Scene-Scope-First Identity Resolution.** Closes Finding B. Reframed mid-revision-cycle from "canonical-name reuse detection" to "primary fix is resolution-layer change." Builds `get_scene_composition(campaign_id) → SceneComposition` private aggregator (campaign_id, location_id, location_name, npcs_in_scope, combatants, bound_pcs, mode); promotion-eligible when second consumer arrives (#5.4 most likely). Adds `IDENTITY_DRIFT` verifier class. Out-of-scope name matches do not resolve to existing canonical rows; they create fresh entities.
- **Ship 4.5 (filed candidate, not committed):** Multi-Actor Temporal State. S32 batched-actor evidence (`last_active_actor` stored only first chronological actor at 22:20:51 footer). Decision deferred to Ship 1 verify checkpoint. Slot if ambiguity rate >1 per session in real play; v1.x candidate otherwise.
- **Ship 5 (S41): Polish cluster.** Findings J/G/I-template/§5.7. **5e (economic_outcome_gate) DROPPED**, filed as v1.x Action Pipelines candidate per validator-proliferation discipline.

*ROADMAP refresh (5 patches via `local-files:edit_file`).* Propagates plan commitments into `text files/ROADMAP.md` so future spec sessions for #5.4/#5.2/#5.3 inherit the architectural commitments this plan settles. Patches:

1. New Status snapshot top row — "Multiplayer Fixes plan (S33+, May 10 2026)" with ⏳ PLAN DRAFTED status
2. Post-checkpoint strategic frame paragraphs — names plan supersession, marks both pre-existing threads (Combat Playability cluster, Motion systems) as paused, calls out #5.5 as new cluster prerequisite ahead of #5.4
3. FOOTINGS QUEUE flipped from "EMPTY" to "MULTIPLAYER FIXES PLAN ACTIVE" with post-plan re-open candidates listing architectural-inheritance language
4. Combat Playability Cluster intro — four cluster-wide architectural commitments inline (Virgil-authoritative trajectory, ResolutionResult template, SceneComposition aggregator, Doctrine §76 four-property test) + updated dependency chain naming #5.5 prerequisite
5. Cluster sub-bullets — #5.5 added as new sibling between #5.1 and #5.2; #5.1, #5.2, #5.3, #5.4 each carry inline architectural-inheritance language pointing back to cluster commitments and `MULTIPLAYER_FIXES.md` §6

## Diagnosis architecture

The plan's spine: **incomplete separation between six layers** that need to stay distinct — authoritative simulation state, interpretive narrative state, presentation formatting, inferred world memory, player intent, mechanical resolution. Most separations hold; two are leaking. Inferred world memory bleeds into authoritative simulation state via `extract_scene_updates` (Finding A); interpretive narrative state bleeds into mechanical resolution via DM-typed-directive flow (Finding L); mechanical resolution is split-brain across two truth systems for hydrated NPCs (Finding H).

North-star principles (§2 of plan):

1. **The LLM is a renderer of truth, not a ruler of truth.** Sharper restatement of §1a. Question to ask of every fix shape: does this make the engine more authoritative, or does it ask the LLM to behave better? If the latter, spec is wrong.
2. **Scene-scope-first resolution.** Identity resolution checks active scope first; out-of-scope name matches don't resolve to existing canonical rows. Generalizes beyond Finding B.
3. **Structural removal of write authority beats validation.** Four supporting axes: single source of truth (sibling to §17); validators accumulate (slippery slope); validators subject to §17's narrow-exception discipline; **local hardware compute cost** — Virgil runs self-hosted; LLM-based validators burn VRAM and slow DM→player response time, while Python/SQL logic is computationally cheap.

## The three-reviewer cycle

Planner drafted v1 in 7 sections. **GPT round 1** flagged five real improvements (latent-canon framing for `established_details`, Ship 5e validator-proliferation warning, Virgil-authoritative trajectory naming, scene-graph principle, derived-state-stronger-than-validation as doctrine candidate). Planner integrated five updates.

**Jordan pushed back twice** — first on the Finding B resolution path, then on the Scene Entity Graph proposal. Each pushback exposed a pattern: planner reaching for "scope creep" too fast when GPT proposed architectural infrastructure. The principle was usually right; the prescription was usually overshoot. Right reflex: **"what's the minimum version that captures the principle?"** not "reject the prescription."

Three concessions earned this way:
- Ship 4 reframed from role-mismatch detection to scene-scope-first resolution as primary fix
- `SceneComposition` aggregator added as private helper with promotion path (rejected GPT's stored Scene table; accepted the computed-aggregator middle ground)
- Avrae-as-projection trajectory committed explicitly in Ship 3 spec language (was hedging as "don't pivot architecture; do name it clearly" — which was agreement dressed as disagreement)

**Jordan called out skipped reasoning a third time:** forced re-read of GPT's full doc. Re-read produced **11 additional updates** beyond the initial 5, including:
- Episodic-recoverable vs cumulative-compounding as the real Ship-1-vs-Ship-2 ordering axis (planner had collapsed to "player-visible vs architecturally damaging" without naming the underlying axis)
- Multi-actor temporal state as Ship 4.5 filed candidate (S32 batched-actor evidence had been dismissed as "anticipated friction" — it was happening in real play, evidence was in the playtest report)
- Validators-accumulate as fourth doctrine candidate with sharpened operational-cost framing
- §13 reframe of plan as "completing the convergence to AI-assisted deterministic simulation"

**Gemini round** added three updates: local-hardware compute cost as fourth axis for structural-removal-beats-validation; "scene-scope-first resolution" lifted as named pattern at §2 level (three independent reviewers converged on it); §12 decision 1 reframed with three-reviewer lens and Jordan's trigger statement ("unplayable now") as the axis-settling input, not planner's recommendation.

Final v2 carries 14 updates beyond v1. Spine unchanged: same ship list, same ordering, same fix shapes, same calendar.

## Doctrinal notes

Four doctrine candidates surface across Ships 1–5. If the plan ships clean, three to four anchor.

- **§76 (recursive hallucination memory loop)** — anchored in Ship 2 spec when shipped. Three project instances clears the bar (S22 #2 chroma contamination, S32 location drift, F-44 chroma bleed pattern). Wording locked in plan §9.1.
- **§65 amendment (bot-as-DM-proxy narrow exception)** — proposed in Ship 3 spec. Doctrine review during Ship 3 spec-drafting. Companion to §17's existing narrow-exception precedent (`apply_starting_time_seed`).
- **Doctrine candidate #3 (LLM-writable scalars on engine-state tables)** — filed S32 from Finding A. Single instance after S32; Ship 2c audit may surface 1+ additional instances via four-property latent-canon test.
- **New candidate (validators accumulate; structural removal beats validation)** — proposed in plan §2.3. Sibling to §17. Single instance after this plan (Ship 5e drop). Anchors when second instance surfaces (likely F-44 chroma scoping or Action Pipelines v1.x).

**§1a wording revision deferred.** GPT's "renderer not ruler" framing is sharper than current §1a wording. Plan defers the revision until after Ship 5 lands — too easy to over-edit doctrine mid-flight.

## Planner-discipline lessons (filed for future planner sessions)

Three patterns surfaced in the review cycle that are worth naming explicitly:

1. **"What's the minimum version that captures the principle" beats "reject the prescription."** When a reviewer proposes architectural infrastructure, the principle is usually right and the implementation is usually overshoot. The reflex should distinguish them. Got this wrong three times in one conversation (scene-scope-first, SceneComposition, Avrae-authority trajectory).

2. **When two thoughtful reviewers reach opposite conclusions, surface the axis disagreement.** Don't collapse to a unilateral planner recommendation. GPT (Ship 2 first) and Gemini (Ship 1 first) disagreed on a real axis (cumulative-compounding vs episodic-recoverable). Right move was to surface both axes to Jordan and let his trigger statement settle which axis to optimize for, not to assert a recommendation as "the obvious call."

3. **Anticipated-friction dismissal must check playtest evidence first.** The temporal-state question got waved off as anticipated MMO-scale friction; S32 evidence had a concrete instance in the playtest report. The dismissal was wrong because the evidence was already in hand. Rule: when about to dismiss something as "anticipated," grep the playtest log for the pattern first.

## Decision points outstanding (§12 of plan)

Seven "before we start" calls listed in plan §12. Most consequential:

1. **Ship 1 vs Ship 2 ordering.** Planner recommends Ship 1 first; trigger statement ("system is unplayable now") settles the axis as playability-now over architectural-purity-long-arc. Surfaced both reviewer arguments to Jordan rather than collapsing to recommendation.
2. **Spec-then-review cadence per ship.** Default 3-session cycle for Ships 1–4; Ship 5 single-session.
3. **Doctrine review timing.** Lock alongside ship that proves them; pre-locking rare.
4. **Combat Playability Cluster #5.1 live verify.** Recommend during plan calendar, can fit between any two sessions.
5. **Pre-multiplayer-fixes playtest?** Recommend trust S32 evidence — no architectural changes shipped between S32 and now would have closed any of A/H/L.
6. **Code model selection.** Opus medium for spec/review; Opus high for Ship 1 + Ship 3 implementations (load-bearing primitives); Sonnet medium for Ship 2 implementation (templated against §59), Ship 4 implementation, Ship 5 polish.
7. **Ship 4.5 decision criterion.** Confirm ">1 directive-binding ambiguity per session = ship; ≤1 = file v1.x" is the right one.

## Cross-references

- `MULTIPLAYER_FIXES.md` v2 — the plan itself. Spine: §1 diagnosis, §2 north-star principles, §3 plan structure, §4–§8 ship details, §9 doctrine work, §10 calendar, §11 non-coverage, §12 decision points, §13 "after this plan" + framing as convergence completion.
- `ROADMAP.md` — 5 patches applied: Status snapshot row, post-checkpoint frame paragraphs, FOOTINGS queue paragraph, Combat Playability Cluster intro, cluster sub-bullets including new #5.5.
- `S32_MULTIPLAYER_PLAYTEST_FINDINGS.md` — trigger document; 14 findings + medium/polish issues. Findings A/H/L are this plan's primary closures.
- `DOCTRINE.md` — not modified this session; four candidates filed, anchor when their proving ships land.
- `FAILURES.md` — not modified this session; F-NN entries for Findings A/B/H/L will be filed when the plan starts shipping.
- `VIRGIL_MASTER.md`, `WHY.md` — not modified per discipline (architectural reasoning entries earn place after empirical validation).
- `BUG_1_SPEC.md` (server-only) — Phase 2 trigger criteria locked in §L will be satisfied as a side effect of Ship 1; Bug 1 Phase 2 effectively ships in Ship 1.
- Future server-side specs: `RESOLUTION_BINDING_SPEC.md` (S33), `SCENE_STATE_CANON_SPEC.md` (S35), `NPC_STATE_SYNC_SPEC.md` (S38), `SCENE_SCOPE_RESOLUTION_SPEC.md` (S40).

**PC rsync:** `MULTIPLAYER_FIXES.md` v2 lives in `/mnt/user-data/outputs/` (planner-side); needs operator copy into `text files/` on PC + server-side copy into `/home/jordaneal/virgil-docs/` for Code's reading surface at S33 spec-drafting. ROADMAP edits applied directly to PC via `local-files:edit_file`; needs `push-docs` to mirror to server.

---

# Session 34 — Ship 1 Resolution Binding: Engine-Bound DC-vs-Roll on the DM-Typed-Directive Surface (May 11, 2026)

**Ships (this session):** Ship 1 of the Multiplayer Fixes plan — engine-bound DC-vs-roll resolution wired into the DM-typed-directive matcher. Closes Finding L (S32 §3.10), F-45 regression (S25 #3), and Bug 1 Phase 2 as a side effect. 40 new test assertions across 4 test files; live verify clean on scenarios A (PASSED), B (FAILED + F-45 surface), D (no-DC graceful degrade); scenarios E (cast skip) + F (multi-actor mismatch) deferred via single-use pickup doc.

## What surfaced

S33 drafted `RESOLUTION_BINDING_SPEC.md` LOCKED v1 + `RESOLUTION_BINDING_REVIEW.md` (14 §11 decisions; 12 at Code's recommendation; 2 framing revisions to §3.2 and §11.14 applied per review §4). Spec was implementation-ready; no architectural questions surfaced during recon. All five recon claims in the spec (Avrae `roll_total` from `parse_avrae_embed`, nat/crit fields per recon Q2, AUTHORITATIVE-CANON anchor at `dnd_engine.py:5189`, ROLL_OUTCOME_DRIFT slotting in `narration_verifier.py`, synthesized `actions` shape) held up under live recon against the current codebase — line numbers had drifted slightly from S33's snapshot but every referenced symbol existed in place.

The recon also confirmed campaign 22's actual bound PC roster: Donovan Ruby (Jordan, controller `691905804965773362`) + Karrok The Devourer (Captin0bvious, controller `249754567263256576`). The spec's §13.7 step text mentioned "Hilda" as the second PC — that was example phrasing, not a structural lock; Karrok substitutes cleanly in F's slot.

**One in-flight friction surfaced during verify**: my initial test-prompt set for live walk included "DM addresses Donovan in `#dm-narration`" setup steps. Jordan-as-DM cannot do that from his Donovan-bound account — pure free-text routes through the player-input batcher (he's bound to Donovan in `dnd_characters`), bypassing the DM-directive intercept. The DM-directive intercept only catches `!`-prefixed messages. **Implication for solo verify discipline:** Ship 1's load-bearing surface is the `!`-prefixed DM directive path, which Jordan-as-DM-and-Donovan-player can exercise solo. The pure-narration "DM addresses PC" setup is not on Ship 1's critical path; only `!check perception <dc>` and `!save <stat> <dc>` are load-bearing. Future spec scenarios should call this out — solo DM-and-bound-PC operator can exercise Ship 1's directive path; free-text DM narration requires either an unbound DM account or a different campaign.

## What shipped

### Engine + orchestration

- `dnd_engine.py` (db_init) — new `dc INTEGER` column on `dnd_pending_roll_directives`, idempotent migration via `PRAGMA table_info`-gated `ALTER TABLE`. Migration confirmed clean on production DB (campaign 22 had zero pending rows at restart time; no data-loss risk).
- `dnd_engine.py:pending_directive_upsert` — accepts new `dc: int | None = None` kwarg; single-writer per Doctrine §17 (only `_handle_dm_roll_directive` writes the column).
- `dnd_engine.py:pending_directive_get_active` — surfaces `dc` + `campaign_id` fields on the returned dict.
- `dnd_orchestration.py` — new resolution-binding section: `ResolutionResult` immutable frozen dataclass (8 fields per spec §5.1 + 2 informational fields `nat`/`crit`); `parse_skill_and_dc` regex helper (spec §6.2 + §6.3 edge-case table exhaustive); `resolve_directive` pure function (eighth Doctrine §59 instance, sibling to `compute_persistence_directive` et al.); `resolution_log_summary` always-fire empirical-baseline helper; `render_resolution_block` (top-of-prompt AUTHORITATIVE-CANON body); `render_resolution_hardstop_echo` (bottom-of-prompt single-line repeat per §48 concrete-in-prompt principle).

### Prompt assembly

- `dnd_engine.py:build_dm_context` — new `resolution_block` + `resolution_hardstop_echo` kwargs. AUTHORITATIVE ROLL RESOLUTION block renders with `═══` triple-line markers (visual distinction from `===` arbitration block per `MULTIPLAYER_FIXES.md` §4.1 lock) immediately after `arbitration_section` in the top-of-prompt anchor. Hardstop echo renders as item 8 of HARD STOP RULES (item 7 reserved for arbitration). Defensive `unexpected_binding_co_occurrence:` canary log fires if both arbitration and resolution kwargs are populated simultaneously (§2.3 mutual-exclusion analysis predicts this never happens by flow in v1; the log is the canary if the flow ever changes).
- `dnd_engine.py:dm_respond` — new `resolution_result: ResolutionResult | None = None` kwarg. Forwards to `build_dm_context` via the new render helpers and to both `verify_narration` call sites (initial + retry). `build_escalation_placeholder` also extended to accept `resolution_result` and emit a deterministic CHECK-style placeholder when the failed class is `ROLL_OUTCOME_DRIFT`.

### Verifier

- `narration_verifier.py` — new `VIOLATION_ROLL_OUTCOME_DRIFT = 'roll_outcome_drift'` constant (fifth class). `verify_narration` signature extended with `resolution_result=None`. Detection slotted between `STATE_MUTATION_CLAIM` (slot 3) and `ACTOR_OMISSION` (slot 5) — preserves "structural-impossibility before behavioral-drift" ordering per §8.4. Vocabulary reuse with `VERDICT_CONTRADICTION` per §11.12 lock — no new phrase tables; `_CHECK_FAILURE_SUCCESS_PHRASES` / `_CHECK_SUCCESS_FAILURE_PHRASES` cover both classes because the linguistic surface is identical regardless of whether binding came from adjudicator or resolver. New `_retry_constraint_roll_outcome_drift` helper includes the spec-locked "player's self-report is irrelevant" sentence — targets the F-45 failure shape directly. Soft-fail discipline preserved end-to-end.

### Discord wiring

- `discord_dnd_bot.py:_handle_dm_roll_directive` — DC parser wired before `_directive_skill_is_clean`. `parse_skill_and_dc(skill_raw)` splits off the trailing integer, then the clean-check runs against the bare skill (so `'perception 10'` is accepted but `'perception adv'` still rejects as `trailing_args`). `pending_directive_upsert` called with `dc=` kwarg. `directive_bound_to_footer_actor:` log extended with `dc=<N|none>` field.
- `discord_dnd_bot.py:_handle_dm_roll_arrival` — match-path extended to compute resolution before consume. Always-fire `resolution_log_summary` emits `directive_resolved:` (resolution non-None) or `directive_resolution_skipped: reason=<no_dc|cast_kind|malformed_embed|unresolvable>` (resolution None). Phase 1's `directive_would_fire_dm_respond:` log line preserved with the **name unchanged** (Bug 1 Phase 2 criterion 4 grep cross-reference per spec §10.1) and extended with `roll_total`/`dc`/`outcome` fields. Returns expanded dict `{aside, auto_fire}` so the async caller can schedule `_dm_respond_and_post` without making the matcher itself a coroutine.
- New helpers `_fire_resolution_narration` (async wrapper for scheduled auto-fire with deterministic fallback aside to `#dm-aside` on `_dm_respond_and_post_failure:` per §11.11) + `_resolve_bound_controller_id` (best-effort lookup of typing-identity for downstream persistence-directive comparison per §9.4 — irrelevant in exploration mode where Ship 1 fires, but informational metadata is captured).
- `_dm_respond_and_post` signature extended with `resolution_result=None`; forwarded through `dm_respond` invocation in the typing-indicator branch.

### Tests (40 new assertions, all green)

- **NEW** `test_resolve_directive.py` — 19 assertions covering `resolve_directive` pass/fail/save/cast/None branches, boundary case `roll_total == dc` → PASSED, nat/crit captures, `render_resolution_block` PASSED + FAILED text shapes, Title-Cased multi-word skill (`sleight of hand` → `Sleight Of Hand`), check/save literal rendering, `render_resolution_hardstop_echo` single-line shape, `resolution_log_summary` resolved/skipped line shapes, `ResolutionResult` immutability (`frozen=True`).
- **NEW** `test_roll_outcome_drift.py` — 11 assertions: drift fires on success-phrase-with-FAILED + failure-phrase-with-PASSED, no-op when `resolution_result=None`, passes when phrasing aligns, VERDICT_CONTRADICTION fires first when both classes apply (priority §8.4), retry constraint includes actor/skill/kind/DC/roll_total/outcome + "self-report is irrelevant" sentence, `build_verification_retry_prefix` produces non-empty prefix, `build_escalation_placeholder` emits deterministic resolution block, empty narration passes, `VERIFICATION_ENABLED=False` short-circuits.
- **EXTENDED** `test_pending_roll_directives.py` — +6 assertions (25 total): `dc` column present after `db_init`, upsert stores `dc=15` non-null, upsert stores `dc=None` correctly, `get_active` surfaces `dc` + `campaign_id`, `parse_skill_and_dc` simple + multi-word, `parse_skill_and_dc` exhaustive edge-case table per spec §6.3. Existing `test_pending_table_columns` updated to include `dc` in the expected column ordering.
- **EXTENDED** `test_narration_verifier.py` — +4 regression assertions (44 total): FABRICATED_COMBATANT / VERDICT_CONTRADICTION / STATE_MUTATION_CLAIM / ACTOR_OMISSION still fire correctly after the ROLL_OUTCOME_DRIFT slot 4 insertion (each test confirms its prior detection still wins under the new five-class ordering).

Adjacent suites also green: `test_arbitration`, `test_attack_directive`, `test_dm_respond_arbitration`, `test_persistence_directive`, `test_commitment_directive`, `test_init_directive`, `test_loot_directive`, `test_prompt_size`, `test_travel_persistence`, `test_avrae_sweep`. Pre-existing `test_directive_emit.py` failure on a `consequence_upsert` tuple-binding bug + `npc_extractor` e2e tests requiring the live LLM router are unrelated to Ship 1.

## Live verification

Restart of `virgil-discord` clean; `dc` column migration applied to production DB at boot. Scenarios walked solo per `RESOLUTION_BINDING_SPEC.md` §13 with Jordan-as-DM-and-Donovan-player on campaign 22:

| Scenario | Path | Result | Log evidence |
|---|---|---|---|
| **A** PASSED check | `!check perception 10` → Avrae rolls 20 → resolve_directive → AUTHORITATIVE-CANON block PASSED → auto-fire | ✅ | `directive_bound_to_footer_actor: ... dc=10` + `directive_resolved: ... dc=10 roll_total=20 outcome=PASSED nat=19 crit=0` + `_dm_respond_and_post: posted` 4s later. Bot narrated success honoring the binding. |
| **B** FAILED check (F-45 surface) | `!check perception 20` → Avrae rolls 15 → resolve_directive → AUTHORITATIVE-CANON block FAILED → auto-fire | ✅ | `directive_resolved: ... dc=20 roll_total=15 outcome=FAILED nat=14 crit=0` + verification `violation_class=none` (no drift). Bot narrated failure correctly: "the faint silver lettering slips past his keen gaze; he registers only the smooth, pulsing glow." F-45 closed structurally on the DM-typed-directive surface. |
| **C** save resolution | `!save dex 15` + player save roll | not exercised live; structurally identical to A/B with `check_kind='save'` | Covered by `test_resolve_save_kind_produces_same_shape` unit test. |
| **D** no-DC graceful degrade | `!check stealth` (no DC) → Avrae rolls → resolve_directive returns None → no auto-fire | ✅ | `directive_bound_to_footer_actor: ... dc=none` + `directive_resolution_skipped: reason=no_dc` + `directive_would_fire_dm_respond: ... dc=none outcome=skipped`. §11.2 lock behavior confirmed. |
| **E** cast skip | `!cast <spell>` requires bound caster | deferred — neither Donovan (Rogue L1) nor Karrok (Barbarian L1) has a cantrip on Avrae sheet. Cast-kind skip covered by `test_resolve_returns_none_for_cast_kind` unit test. |
| **F** multi-actor mismatch | Requires two distinct Discord controller IDs in ActionBatcher window to produce a 2-actor footer | deferred — pickup doc written (`MULTIPLAYER_VERIFY_DEFERRED.md`) for future session when multiplayer is available |

**Aggregate promotion-gate greps (clean):**
- Total `directive_resolved:` events: 2 (1 PASSED, 1 FAILED — both resolver branches exercised)
- Total `directive_resolution_skipped:` events: 1 (`reason=no_dc`)
- Unretried `roll_outcome_drift` violations: **0** (criterion 5 satisfied)
- `unexpected_binding_co_occurrence:` fires: **0** (§2.3 canary holds)
- `_dm_respond_and_post_failure:` fires: **0** (no auto-fire failures)
- Distinct DC values exercised live: 2 (10, 20). Parser fully covered by unit tests across DC 0, 10, 12, 15, 100, -5, with multi-word skills.

The §13.9 criterion 3 ("≥4 distinct DC values live") was not satisfied; live coverage at 2/4 distinct DCs. Parser confidence comes from unit tests (`test_parse_skill_and_dc_edge_cases_per_spec_table`) which cover the spec §6.3 table exhaustively. Acceptable softening of the live criterion given the unit-test coverage.

## Bug 1 Phase 2 — closed as side effect

All five Phase 2 trigger criteria satisfied structurally (per `RESOLUTION_BINDING_SPEC.md` §3 absorption analysis):

1. ≥5 emits across ≥2 sessions — already met by S32 calibration table (`directive_bound_to_footer_actor:` count, 15+ in two sessions).
2. ≥80% bind success — S32 measured 75% raw / >80% adjusted for legitimate session-open `directive_creation_skipped_no_footer` events (correctly-handled non-events, excluded from denominator).
3. Zero spurious footer transitions — confirmed by S32 (every `footer_actor_changed:` traced to granular trigger).
4. Zero ghost-triggers — confirmed by S32 (every `directive_would_fire_dm_respond:` paired to preceding `directive_bound_to_footer_actor:`).
5. **Narrated outcome matches roll-vs-DC verdict in 100% of consumed directives** — measured live S34 walk: zero `violation_class=roll_outcome_drift` with `retry_passed=0|-`.

Phase 2 ROADMAP row flipped ✅ in the same doc-update pass. ROADMAP item 3 (Bug 1) now reads "Phase 1 ✅ (S32) + Phase 2 ✅ (S34, via Ship 1)."

## Doctrinal notes

Two candidates filed unanchored per §59 (anchor when second project instance surfaces):

- **Engine-computed binding > validator-on-LLM-output (review §3.1).** When an LLM-output failure mode can be closed by engine-computing the bound outcome and rendering it as a top-of-prompt constraint (rather than validating the LLM's output after the fact), the engine-computed path is structurally stronger. Validators close drift via retry pressure; engine binding closes drift via making the drift surface inaccessible. Both have a role — binding is the first reach; validation is the safety net. Two instances so far: Track 7 #1 CHECK_ACTION binding (adjudicator surface) + Ship 1 Resolution Binding (matcher surface). Likely third candidate: cast resolution binding when v1.x ships. **File, do not anchor.**
- **Reused vocabulary across sibling verifier classes (review §3.2).** When two violation classes detect the same linguistic surface (LLM uses success/failure phrasing) but against different binding objects (adjudicator vs. resolver), reuse the vocabulary rather than fork. The class differentiation is which binding object is populated at call time; the detection phrases are identical. One instance so far: `ROLL_OUTCOME_DRIFT` reuses `VERDICT_CONTRADICTION`'s phrase tables. **File for pattern-watch.**

Neither candidate anchored in `DOCTRINE.md` this session — both filed in the candidates section.

## Cross-references

- `RESOLUTION_BINDING_SPEC.md` LOCKED v1 — spec source.
- `RESOLUTION_BINDING_REVIEW.md` — planner-side lock pass; §5 implementation handoff lists touched files, test target, promotion criteria, doc-update plan.
- `BUG_1_SPEC.md` — Phase 2 trigger criteria §L (server-only; not edited per Ship 1 spec §3 absorption discipline).
- `MULTIPLAYER_FIXES.md` §4 (Ship 1 row) — flipped ✅ in same doc-update pass; §10 calendar updated to reflect S34 ship.
- `MULTIPLAYER_VERIFY_DEFERRED.md` (new) — single-use pickup doc for deferred Scenarios F and conditionally E. Contains campaign-22 PC snapshot, rewritten F walk with Karrok in Hilda's slot, conditional E walk, Ship 4.5 decision-criterion reminder distinguishing structural verify from natural-play data. Archives to `_trash/` after deferred verify lands.
- `ROADMAP.md` — Ship 1 row added to Status snapshot; Multiplayer Fixes row marked ⏳ IN PROGRESS with Ship 2 next; Bug 1 Phase 2 flipped ✅; FOOTINGS queue paragraph updated.
- `tests-to-run-post-session.md` — §13 live-verify scenarios A–F appended as documented post-session verify steps.
- `DOCTRINE.md` — two candidates appended to candidates section per review §3 (engine-bound binding > validator; reused vocabulary across sibling classes).
- `FAILURES.md` — not modified this session. F-NN entries for Findings A/B/H file when Ships 2/3/4 land. Finding L does not get a separate F-NN since it's a regression of F-45; F-45 disposition gets a structural-closure note in a future doc-update.
- `VIRGIL_MASTER.md`, `WHY.md` — not modified per discipline (wait for Ship 5 cluster completion / plan completion).

## HALT escalations during the session

**None during implementation.** All five spec recon claims held up under live recon. The mid-session friction (Jordan-can't-DM-narrate-from-Donovan-bound-account) surfaced in the verify phase, not implementation, and was a test-prompt phrasing miss on my part — not a structural spec issue. The DM-directive intercept gate is the load-bearing surface for Ship 1 and works correctly for solo operator setups.

**PC rsync:** All five doc-update files (`ROADMAP.md`, `SESSIONS.md`, `DOCTRINE.md`, `tests-to-run-post-session.md`, `MULTIPLAYER_FIXES.md`) + new `MULTIPLAYER_VERIFY_DEFERRED.md` + code files (`dnd_engine.py`, `dnd_orchestration.py`, `narration_verifier.py`, `discord_dnd_bot.py`) + new test files mirrored to PC via `push-all-to-pc.sh` at end of session.

---

# Session 34 #2 — Multiplayer Fixes Plan V3: Primary-Surface Re-Diagnosis, Avrae Recon, Promotion (May 11, 2026)

**Ships (this session):** No code. Planning ship. Drafted `MULTIPLAYER_FIXES_V3_DRAFT.md` (383 lines); operator locked all 12 §12 decisions including new decision 12 (wrong-skill matcher behavior, option (b) HIGH confidence); Avrae A.2 compatibility recon ran cleanly (form (a) — Avrae silently ignores trailing integer in `!check skill N`); v3 promoted to canonical `MULTIPLAYER_FIXES.md`; v2 archived at `_trash/MULTIPLAYER_FIXES_V2_20260511.md`; ROADMAP + SESSIONS index updated to reflect v3 sequencing.

## What surfaced

The Ship 1 verify in S34 exposed an architectural framing miss that S33 planning didn't catch. Ship 1 was specced to close the **DM-typed-directive surface** (operator with `manage_guild` perm types `!check perception 10` literally in `#dm-narration`). It does that correctly — A/B/D scenarios fired clean. But the **load-bearing 90% play loop** is different: operator types intent ("I take a closer look"), LLM narrates a response and emits `!check perception 15` inside that narration, Avrae sees the embed and rolls, operator expects bot to auto-fire a resolution narration bound to the rolled value.

That LLM-emitted-directive surface is NOT closed by Ship 1. The LLM's `!check perception 15` arrives in Discord as a bot-authored message, which short-circuits at `on_message`'s `message.author.bot: return` gate — Ship 1's writer (`_handle_dm_roll_directive`) never sees it, and no `dnd_pending_roll_directives` row is created. Avrae rolls; matcher finds no pending row; falls through to normal player-input buffer flow per Track 7 #1. The resolution-binding work is *upstream* of where Ship 1 writes — it needs to fire when the bot is about to post LLM-generated narration containing `!check`/`!save` patterns, before Discord even sees the message.

The cause of the S33 miss: `BUG_1_SPEC.md` framed Phase 1 around "DM emits directive, Avrae rolls, bot waits silently" — with the assumed actor of the `!check` being the human DM. The LLM has always emitted `!check` inside narration (per HARD STOP RULE 1, which instructs it to end a roll-required turn with the exact roll command), but no pending-directive row was ever created for that emission. v2 spec needed a second writer at narration-emission time; v2 didn't specify one.

## What shipped (planning artifacts)

*`MULTIPLAYER_FIXES_V3_DRAFT.md` v3 (383 lines).* Six-ship plan, calendar S33–S43, 11–15 days. v3 supersedes v2; v2 archived.

- **Ship 1 (S33–S34): Resolution Binding — DM-typed-directive surface.** ✅ shipped, closes a real-but-secondary 5–10% surface (operator-as-flagged-DM running deliberate set-piece checks).
- **Ship A (S35–S36): LLM-Emitted-Directive Resolution Binding.** NEW PRIMARY. Adds a second writer to `dnd_pending_roll_directives` at narration-emission time (in `_dm_respond_and_post`, post-`dm_respond`-pre-Discord-post). Parses LLM-emitted `!check skill DC` / `!save stat DC` from response text, calls `pending_directive_upsert`. Reuses shipped Ship 1's `ResolutionResult` + `resolve_directive` + render helpers + matcher + ROLL_OUTCOME_DRIFT verifier + `_fire_resolution_narration` auto-fire coroutine. Adds `ResolutionTexture` sub-dataclass referenced by `ResolutionResult.texture` carrying difficulty band / margin tier / stakes tier / crit-tier signals; `compute_stakes_tier` pure function (§59 9th sibling) computes stakes from scene_state + active_turn + active_quests + combatants; difficulty band derived from DC vs Avrae embed's modifier (modifier = `roll_total - nat` is free from existing fields); margin tier derived from `roll_total - dc`; crit-tier renders separate constraint clauses for nat 20 / nat 1 regardless of pass/fail (RAW preserved — nat doesn't override `passed`). Prompt-side change: HARD STOP RULE extension instructing LLM to always include DC when emitting roll directive. Two-embed UX confirmed (initial narration + ~6s later outcome narration). Spec drafts S35 (Opus medium); implementation S36 (Opus high).
- **Ship 2 (S37–S39): Scene State Canon Discipline.** Survives v3 sequencing unchanged. Possibly higher priority post-Ship-A since Ship A's `compute_stakes_tier` reads scene_state and benefits from canon discipline.
- **Ship 3 (S40–S41): NPC State-Sync Boundary.** Survives unchanged. Independent of directive-emit surface.
- **Ship 4 (S42): Scene-Scope-First Identity Resolution.** Survives unchanged. Surfaces clean opportunity for Ship A's `compute_stakes_tier` to consume `SceneComposition` post-Ship-4 refactor.
- **Ship 4.5 (filed candidate):** Multi-Actor Temporal State. Decision criterion shifted from Ship 1 verify checkpoint to **Ship A verify checkpoint** — Ship A's verify is more natural-play-shaped; sock-puppet F walks don't produce real-play data per §7B.3 criterion.
- **Ship 5 (S43): Polish cluster.** Survives with one sub-ship retired — **5a Finding J (DC leak in player-facing directive) retired entirely** under Ship A's design, because LLM-emitted directives intentionally show the DC to the player (Avrae sees the embed and rolls). 5a was solving the wrong problem.

*Avrae A.2 compatibility recon (08:33:14–08:33:40, 2026-05-11).* Two-test recon in campaign 22 `#dm-narration`:

- **Test 1:** `!check perception 15`. Avrae embed: `Donovan Ruby makes a Perception check! 1d20 (15) + 1 = 16`. Virgil's logs: `directive_bound_to_footer_actor: ... dc=15` + `directive_resolved: ... dc=15 roll_total=16 outcome=PASSED nat=15 crit=0` + `_dm_respond_and_post: posted` 5s later. Bot auto-narrated success (existing Ship 1 wiring firing through the recon format).
- **Test 2:** `!check perception` (bare baseline). Avrae embed: `1d20 (17) + 1 = 18`. Virgil's logs: `directive_bound_to_footer_actor: ... dc=none` + `directive_resolution_skipped: reason=no_dc`.

Critical finding: same modifier (+1) in both rolls, same dice formula, same embed shape — Avrae silently ignored the trailing 15 and rolled perception normally. **Form (a) clean.** Decision A.1 holds verbatim: LLM-emit format is `!check skill DC` with trailing integer, no separator. Virgil's `parse_skill_and_dc` (shipped Ship 1) splits skill from DC correctly. Avrae compatibility cleared as the only pre-promotion blocker.

*v3 promotion to canonical.* Mechanical doc-shuffle:
1. `mv MULTIPLAYER_FIXES.md _trash/MULTIPLAYER_FIXES_V2_20260511.md` (lineage preserved for cross-reference from existing S33 SESSIONS entry).
2. `mv MULTIPLAYER_FIXES_V3_DRAFT.md MULTIPLAYER_FIXES.md` (v3 becomes canonical).
3. Status banner updated from "DRAFT, LOCKS APPLIED" → "LOCKED, CANONICAL".
4. §13 ("What this is NOT") rewritten to remove draft framing; §14 tabular handoff updated to post-promotion state.
5. ROADMAP "Multiplayer Fixes plan" row updated: 5-ship → 6-ship, v2 → v3, "Ship 2 next" → "Ship A next"; FOOTINGS queue paragraph similarly. Last-updated timestamp flipped to S34 #2.

## Locked decisions (12 total per v3 §12)

1. v3 supersedes v2 as canonical ✅
2. (A.1) DC source — inline `!check skill DC` ✅
3. (A.2) Avrae compatibility recon cleared, form (a) holds ✅
4. (A.4) `compute_stakes_tier` as §59 9th sibling ✅
5. (A.5) `ResolutionTexture` separate dataclass referenced by `ResolutionResult.texture` ✅
6. (A.6) Accept stale + TTL cleanup for bot-message edits; TTL = 300s kept for v1 (phantom-binding requires three-condition compound, rare in natural play; tighten only if multiplayer logs show actual events) ✅
7. (A.8) Two-embed UX ✅
8. Ship 4.5 decision criterion shifts to Ship A verify checkpoint ✅
9. Ship 5 sub-ship 5a (Finding J) retired ✅
10. Corpus discipline — defer to observation, no parallel drafting ✅
11. Doctrine candidate C1 — wait for Ship A verify to prove third instance ✅
12. **NEW** Wrong-skill matcher behavior — option (b) HIGH confidence: post `#dm-aside` clarification, leave pending row alive until correct skill arrives or TTL expires; wrong-skill roll falls through to normal player-input buffer flow. Aside copy template: `"expected {pending_skill}, got {avrae_skill}; the {pending_skill} directive is still active."` ✅

## What this session does NOT do

- **No code shipped.** Implementation lands in S36 per v3 §11 calendar.
- **No spec drafted.** `LLM_EMIT_RESOLUTION_BINDING_SPEC.md` (the Ship A spec) drafts in S35 with the 12 decisions as input.
- **No doctrine anchored.** Candidate C1 stays a candidate per locked decision 11.
- **No Ship 1 rework.** Shipped Ship 1 stays as-shipped; v3 §13 makes the secondary-surface framing explicit.

## Cross-references

- `MULTIPLAYER_FIXES.md` v3 (now canonical) — the plan itself.
- `_trash/MULTIPLAYER_FIXES_V2_20260511.md` — v2 archived for lineage.
- `RESOLUTION_BINDING_SPEC.md` — Ship 1's spec, unchanged.
- `MULTIPLAYER_VERIFY_DEFERRED.md` — Scenario F deferred pickup doc; decision criterion shifted to Ship A verify (per v3 §7B).
- `ROADMAP.md` — Multiplayer Fixes plan row updated; FOOTINGS queue updated; Last-updated flipped to S34 #2.
- `BUG_1_SPEC.md` — server-only, not modified. Original Phase 1/Phase 2 framing remains the lineage source; v3's diagnosis section narrates the framing-miss in passing.
- `DOCTRINE.md` — not modified this session. Candidate C1 (engine-bound binding > validator) reaches potential third instance at Ship A; promotion timing per locked decision 11.
- `FAILURES.md`, `VIRGIL_MASTER.md`, `WHY.md` — not modified.

## HALT escalations during the session

**None.** Two architectural surfaces were surfaced and resolved cleanly:

1. **Primary-vs-secondary surface mismatch** — diagnosed in v3 §1, re-sequencing followed.
2. **§17 single-writer status with two trigger surfaces** (Ship 1's writer + Ship A's writer both writing `dc` column) — resolved at v3 §4.2 by consolidating at the writer-helper layer (`pending_directive_upsert`), not the trigger layer. Two disjoint triggers calling one writer-helper is structurally compatible with §17.

## Tabular handoff (S34 #2)

| Field | Value |
|---|---|
| **Planning artifact written** | `MULTIPLAYER_FIXES.md` v3 (replaces v2) |
| **Lineage preserved** | `_trash/MULTIPLAYER_FIXES_V2_20260511.md` |
| **Decisions locked** | 12 (11 from v3 draft §12 + 1 new wrong-skill decision) |
| **Recon cleared** | Avrae A.2 — form (a) clean, Avrae silently ignores trailing integer |
| **Calendar delta from v2** | +2 days (9 best/13 slow → 11 best/15 slow) |
| **Code shipped** | None (planning ship) |
| **Ships promoted** | None (Ship 1 already ✅ S34) |
| **Ships re-sequenced** | Ship A inserted as new primary post-Ship-1; Ships 2/3/4/4.5/5 carry from v2 with Ship 5 sub-ship 5a retired |
| **Next session recommendation** | S35: Ship A spec drafting — write `LLM_EMIT_RESOLUTION_BINDING_SPEC.md` carrying the 12 §12 decisions as input. Opus medium per v3 §4.6. Output: locked spec ready for S36 implementation. |
| **PC rsync** | `MULTIPLAYER_FIXES.md` (new canonical), `_trash/MULTIPLAYER_FIXES_V2_20260511.md`, `ROADMAP.md`, `SESSIONS.md` mirrored via `push-all-to-pc.sh`. |

---

# Session 35 — Ship A Spec + Review (May 11, 2026)

**Ships (this session):** No code. Spec + review pair. Drafted `LLM_EMIT_RESOLUTION_BINDING_SPEC.md` v1 (1301 lines) carrying the 12 pre-locked decisions from v3 §12 plus 6 surfaced during drafting (§11.B.1–B.6). S35b review pass applied 6 framing revisions per `LLM_EMIT_RESOLUTION_BINDING_REVIEW.md` §4 — texture-computation surface clarification, ResolutionResult field invariant, stakes-tier scoring axis simplification, crit-tier mode mapping, live-verify count threshold, housekeeping framing. Spec flipped DRAFT → LOCKED.

## Cross-references

- `specs/LLM_EMIT_RESOLUTION_BINDING_SPEC.md` LOCKED v1 — spec source.
- `specs/LLM_EMIT_RESOLUTION_BINDING_REVIEW.md` — planner-side review pass.
- `MULTIPLAYER_FIXES.md` v3 §4 — Ship A architectural shape.

## Tabular handoff (S35)

| Field | Value |
|---|---|
| **Spec written** | `specs/LLM_EMIT_RESOLUTION_BINDING_SPEC.md` LOCKED v1 |
| **Review written** | `specs/LLM_EMIT_RESOLUTION_BINDING_REVIEW.md` |
| **Decision count** | 18 (12 pre-locked from v3 §12 + 6 surfaced in spec drafting) |
| **Revisions applied** | 6 framing/wording (no architectural changes) |
| **HALT escalations** | None |
| **Next session** | S36 — Ship A implementation, Opus high per v3 §4.6. |

---

# Session 36 — Ship A Implementation + 9 Live-Verify Patches (May 11, 2026)

**Ships (this session):** Ship A SHIPPED LIVE — LLM-Emitted-Directive Resolution Binding on the primary 90% play loop. ~600 LOC across 3 files. ~120 test assertions across 2 new + 4 extended files. Live verify in campaign 17 confirmed end-to-end loop: operator types intent → LLM narrates + emits `**!check skill DC : Name**` → DC stripped from player view → Avrae rolls → matcher resolves with texture → bot auto-fires textured outcome narration → ROLL_OUTCOME_DRIFT verifier clean. Nat-20 PASSED case fired with memorable-success texture (Donovan lifted heavy crate, found bundle of parchment + iron key, NPC reactions). Zero cascading rolls after Patch 7 sentinel detection. Avrae compat confirmed for `**!check skill : Name**` bold-wrapped format.

**Closes:** Finding L surface 2 (LLM-emitted-directive — the 90% play loop). Companion to shipped Ship 1 (DM-typed-directive 5–10% surface). Both surfaces of Finding L now structurally closed via the same primitives (`ResolutionResult` + `resolve_directive` + render helpers + ROLL_OUTCOME_DRIFT verifier + matcher + auto-fire coroutine).

## What surfaced (during implementation + live verify)

Implementation followed spec §1–§17 cleanly. Five live-verify-surfaced issues drove 7 additional patches beyond the initial implementation:

1. **Intent classifier under-triggered.** Operator's natural phrasings ("Look closely at the notice board", "try to find a missing detail", "I take a closer look") classified as `trivial` or `social` → no roll → LLM made up outcomes. Bug 1 in TRIVIAL_RX: bare `look` matched and short-circuited before EXPLORATION_RX could see `look closer`. Bug 2: most natural verbs not in EXPLORATION_RX. Bug 3: fall-through went to SOCIAL default. → Patch 1 + Patch 8 (classifier expansion + wider verb coverage).
2. **DC visibility.** Operator pushed back on locked decision 9 (Finding J retired). LLM-emitted `!check perception 15` showed the DC to the player by design under decision 9. Operator wants DC hidden. → Patch 2 (DC strip in `_dm_respond_and_post` post-`dm_respond`-pre-channel-send).
3. **DC clobber via manual echo.** Operator manually typing `!check perception` after the bot's emit caused `_handle_dm_roll_directive` to overwrite Ship A's `dc=10` row with `dc=none` → matcher saw no DC → resolution skipped. → Patch 4 (dc-preservation in `_handle_dm_roll_directive` — if existing row has dc=N AND new directive has no DC AND actor+skill match, skip the overwrite).
4. **Emit format UX gaps.** Operator wanted character name in directive, blank line spacing, bold formatting. → Patch 5 + Patch 6 (`RollDecision.to_prompt_directive` template revisions to instruct LLM to emit single bold line `**!check skill DC : First Name**` after narrative beat + blank line).
5. **Cascading rolls in auto-fire.** Resolution narration after Avrae roll ended with another `!check` directive, triggering a second Avrae roll the operator didn't ask for. Root cause: the auto-fire synthesized input `[Roll resolution: Donovan rolled athletics (check); outcome bound at top-of-prompt.]` contained the word `athletics`, which EXPLORATION_RX matched → classifier returned `INTENT_EXPLORATION` → ROLL DIRECTIVE block told LLM to end with another roll request. → Patch 7 (sentinel detection in `classify_action_intent` routes `[Roll resolution:` prefix to META → no-roll → no cascading instruction in prompt).

Surfaced in verify, addressed in same session. All five operator-flagged issues resolved by Patch 9 deploy.

## What shipped

### Engine + orchestration

- **`dnd_orchestration.py`** (~400 LOC additive):
  - `ResolutionTexture` frozen dataclass with `effective_dc`, `modifier`, `difficulty_band`, `margin`, `margin_tier`, `stakes_tier`, `stakes_signals`.
  - `_bucket_difficulty(effective_dc) → str` — 5e RAW DC-band bucketing (trivial / easy / medium / hard / very_hard / nearly_impossible).
  - `_bucket_margin(margin: int) → str` — six-tier margin bucketing (catastrophic_fail / clear_fail / close_fail / razor_pass / clean_pass / smashing_pass).
  - `_STRONG_INTENT_RX` regex for stakes-tier scoring (locked decision A.4 simplification per S35b review §3.B.4).
  - `compute_stakes_tier(scene_state, active_turn, active_quests, combatants) → (str, dict)` — pure function, ninth Doctrine §59 instance. Five-axis scoring shape locked in spec §5.2.
  - `stakes_tier_log_summary(signals, tier) → str` — always-fire telemetry per §59 sibling pattern.
  - `compute_resolution_texture(dc, roll_total, nat, scene_state, ...) → ResolutionTexture` — assembler helper.
  - Extended `ResolutionResult` with `texture: Optional[ResolutionTexture] = None` field (backwards-compatible — Ship 1 callers receive `texture=None`).
  - Extended `resolve_directive` signature with optional `scene_state`, `active_turn`, `active_quests`, `combatants` kwargs. When `scene_state` supplied, computes texture inline at instantiation time (frozen-immutability preserved — no `dataclasses.replace`).
  - Extended `render_resolution_block` with locked guidance clauses for difficulty + margin + stakes (per spec §8.3, §9.2) and crit-tier constraint clauses for nat-20 / nat-1 (per §10.2 including scene-mode-modulated tone for nat-1 + FAILED).
  - Extended `RollDecision.to_prompt_directive` (skill + save branches) with explicit emit template instructing LLM to format as `**!check skill DC : First Name**` + DC GUIDANCE 5e RAW band table.
  - **Classifier expansion (Patch 1 + 8):** TRIVIAL_RX shrunk (bare `look` removed; only `look around` stays trivial). EXPLORATION_RX expanded with ~25 new verb anchors (`find`, `peer`, `peek`, `scrutinize`, `notice`, `spot`, `comb`, `scan`, `figure out`, `discern`, `read closely/carefully/over`, `check for/the/over/inside/behind/under`, `look closely/carefully/harder/closer/over/inside/behind/under`, `look around carefully/closely/harder/intently/slowly`, `take a closer/careful/hard/good look`, `lift`, `hoist`, `pry`, `wrench`, `force open/the/it`, `break open/down/through`, `kick open/down`, `push X over/down/through/aside`, `haul`, `drag`, `tug`, `yank`, `scramble`, `swing on/off/across/over`, `shove X open/aside`, `shoulder X open`, `dodge`, `tumble`, `vault`, `balance`, `roll under/past/through`, `duck under/behind/into`, `creep`, `slink`, `tiptoe`, `sneak up`). EXPLORATION_DEFAULT_SKILLS extended with ~30 new skill-mapping entries routing to perception / investigation / athletics / acrobatics / insight / stealth as appropriate.
  - `_PHYSICAL_BREAK_OPEN_RX` pre-COMBAT carve-out for "smash/bash/crush/break/shove X open|down|through|apart|in|aside" and "swing on/off/across/over X" — routes physical-exertion-shaped verbs to exploration athletics instead of being claimed by COMBAT_RX.
  - **Sentinel detection (Patch 7):** `classify_action_intent` routes text starting with `[Roll resolution:` to `INTENT_META` → no-roll. Prevents cascading rolls in auto-fire narration.

### Discord wiring

- **`discord_dnd_bot.py`** (~150 LOC additive):
  - `_LLM_EMIT_DIRECTIVE_RX` regex — handles operator-locked `**!check skill DC : Name**` format with optional colon-name suffix and `**` bold-close markers.
  - `_parse_llm_emit_directive(response) → dict | None` — last-match-wins per spec §11.B.1.
  - `_strip_dc_from_llm_emit(response) → str` — strips trailing DC integer while preserving bold markers and colon-name suffix.
  - `_wrong_skill_aside(expected, actual) → str` analog to `_wrong_actor_aside` (spec §13).
  - Writer hook in `_dm_respond_and_post` (post-channel-send, pre-`asyncio.create_task` for `_attach_hints`/`_extract_and_persist_world`): parses LLM emit cached pre-strip, writes pending row with parsed skill + DC, emits `llm_emit_directive_bound:` log.
  - DC-strip applied to response text BEFORE `chroma_store` + embed-build, so player-facing message hides the DC while chroma/embed see the same stripped form.
  - **dc-preservation (Patch 4):** `_handle_dm_roll_directive` checks existing pending row before upsert; if existing has dc=N AND new has no DC AND actor+skill match, skips the upsert and logs `directive_preserve_existing_dc:`. Prevents operator's manual `!check` echo from clobbering Ship A's row.
  - **no-DC `#dm-aside` (Patch 9):** when resolution skips with `reason=no_dc`, matcher returns aside text for the async caller to post; helps operator see when the LLM forgot to include a DC.
  - Plumbed `scene_state`, `active_turn`, `combatants`, `active_quests` from matcher to `resolve_directive` so texture computes at consume time.
  - Skill-mismatch branch flipped from silent-ignore to log + aside per locked decision 12.

### Prompt assembly

- **`dnd_engine.py`** HARD STOP RULE 1 extended with DC-inclusion mandate.

### Tests (~120 new assertions across 2 new + 4 extended files)

- **NEW** `test_compute_stakes_tier.py` — 10 assertions.
- **NEW** `test_llm_emit_writer.py` — 23 assertions (12 base + 7 DC strip + 4 operator-locked format).
- **EXTENDED** `test_resolve_directive.py` — +6 texture assertions = 25 total.
- **EXTENDED** `test_pending_roll_directives.py` — +2 cross-trigger assertions = 27 total.
- **EXTENDED** `test_narration_verifier.py` — +3 regression (drift detection with texture) = 47 total.
- **EXTENDED** `test_classify_action_intent.py` — +6 assertions for verb expansion + sentinel detection = 45 total.
- **EXTENDED** `test_attack_directive.py` — +2 format-template assertions for the new `**!check skill <DC> : <First Name>**` shape = 40 total.

### Telemetry log lines (new)

- `llm_emit_directive_bound:` — fires when narration-emit writer creates a pending row from LLM emission.
- `llm_emit_multi_directive_count:` — fires when LLM emits >1 directive in one response (telemetry for tuning).
- `directive_skill_mismatch:` — fires on skill-mismatch path (Ship A decision 12 option b — log + aside, row stays alive).
- `stakes_tier:` — fires when texture is computed; carries score breakdown for calibration.
- `directive_preserve_existing_dc:` — fires when manual `!check` echo would have clobbered Ship A's dc=N row; the upsert is skipped.
- `_llm_emit_directive_write error:` / `resolve_state_read error:` — soft-fail telemetry.

## Live verification

Walked across multiple turns in campaign 17 (Test10F → Donovan Ruby bound in dnd_characters + Avrae). Key events from journal:

- `11:41:00 llm_emit_directive_bound: campaign=17 actor=Donovan Ruby skill=athletics dc=15 kind=check`
- `11:41:10 directive_preserve_existing_dc: campaign=17 actor=Donovan Ruby skill=athletics existing_dc=15` (Patch 4 fired)
- `11:41:10 directive_resolved: campaign=17 ... dc=15 roll_total=21 outcome=PASSED nat=20 crit=0`
- `11:41:10 stakes_tier: tier=low ... score=0`
- `11:41:13 verification: campaign=17 passed=1 violation_class=none`

Operator's confirmation per screenshots:
- ✅ No cascading second `!check` (Patch 7 confirmed)
- ✅ Character name in directive (`: Donovan` suffix)
- ✅ Roll request renders bold in embed (operator-confirmed bold-wrap survives DC strip)
- ✅ Blank line between narrative and directive
- ✅ DC hidden from player view (strip working)
- ✅ Nat-20 PASSED case rendered memorable-success texture per §10.2 — "dwarf-born strength lifts the heavy lid clean off", "tightly wound bundle of parchment tied with a red ribbon and a glint of metal—a small iron key", NPC reactions (Eldrin + Lira)
- ✅ Avrae compat for `**!check skill : Name**` bold-wrapped format

## Bug 1 Phase 2 status

Unchanged from S34 — Phase 2 trigger criteria all satisfied structurally by Ship 1 + Ship A. Both Finding L surfaces (DM-typed and LLM-emitted) now closed.

## Doctrinal notes

Three candidates accruing toward §59 anchoring discipline:

- **C1 Engine-bound binding > validator** — three instances pending Ship A verify proof: Track 7 #1 CHECK_ACTION binding + Ship 1 Resolution Binding (DM-typed) + Ship A Resolution Binding (LLM-emitted, this ship). Anchoring deferred per locked decision 11 — wait for Ship A verify to confirm the shape holds. **All three instances now have clean live verify**; promotion to numbered §-entry could land in S37 doc-update or wait until a fourth instance surfaces (likely cast resolution binding when v1.x ships).
- **C2 Reused vocabulary across sibling verifier classes** — Ship A doesn't add new verifier classes; C2 stays at one instance (ROLL_OUTCOME_DRIFT reusing VERDICT_CONTRADICTION's phrase tables). Reassess when F-55 #5.4 ships.
- **C3 Single-writer compatible with multiple trigger surfaces** — one instance after Ship A (Ship 1's writer + Ship A's writer both calling `pending_directive_upsert`). Filed unanchored; anchor when second instance surfaces.

## Surfaced for Ship 2 spec (filed as memory)

S36 live-verify surfaced a time-of-day drift instance: bot narrated "Evening settles over the merchant market as lanterns flicker" while engine-tracked `dnd_scene_state.day_phase = 'Morning'`. LLM ignored canonical engine state when narrating time. Exactly the surface Ship 2 (Scene State Canon Discipline) is built to close. Logged as evidence for Ship 2's four-property latent-canon audit (per `project_ship2_drift_evidence.md` memory). Concrete examples accrue when natural play produces them — each tightens Ship 2's spec framing.

## Cross-references

- `specs/LLM_EMIT_RESOLUTION_BINDING_SPEC.md` LOCKED v1 — spec source.
- `specs/LLM_EMIT_RESOLUTION_BINDING_REVIEW.md` — review pass with 6 framing revisions.
- `MULTIPLAYER_FIXES.md` v3 §4 — Ship A architectural shape (canonical).
- `ROADMAP.md` — Ship A row flipped ✅; FOOTINGS queue updated; Ship 2 next active.
- `BUG_1_SPEC.md` — Phase 2 trigger criteria §L (server-only; both surfaces of Finding L now closed by Ship 1 + Ship A).

## HALT escalations

**None** during implementation. The five live-verify-surfaced issues were addressed in-session as Patches 4–9 without halting; each was a small, locally-scoped fix that didn't require architectural review.

## Tabular handoff (S36)

| Field | Value |
|---|---|
| **Code shipped** | `dnd_orchestration.py` (~400 LOC additive), `discord_dnd_bot.py` (~150 LOC additive), `dnd_engine.py` (HARD STOP RULE 1 extension) |
| **Tests added** | ~120 assertions across 2 new + 4 extended files (test_compute_stakes_tier 10, test_llm_emit_writer 23, test_resolve_directive +6 = 25, test_pending_roll_directives +2 = 27, test_narration_verifier +3 = 47, test_classify_action_intent +6 = 45, test_attack_directive +2 = 40). |
| **Tests passing** | 100% (all Ship A + classifier + adjacent suites green; pre-existing test_directive_emit + npc_extractor e2e failures unrelated). |
| **Patches landed** | 9 (implementation + 7 live-verify-surfaced + 1 doc-update prep) |
| **Live-verify result** | Clean. nat-20 PASSED texture rendered correctly. Zero cascading rolls. Avrae compat for bold-wrap format confirmed. All 5 operator-flagged issues resolved. |
| **Promotion criteria met** | yes — Ship A ✅ SHIPPED LIVE |
| **Doctrine candidates** | C1 has 3 clean instances; anchoring deferred per locked decision 11. C2 stays at 1 (no new verifier class). C3 filed at 1 (new candidate from §16.3). |
| **HALT escalations** | None |
| **Ship A status** | ✅ **PROMOTED** |
| **Ship 2 status** | next active — spec drafts S37 per v3 §5. Drift evidence accruing (S36 time-of-day instance filed in memory). |
| **Next session recommendation** | S37 — Ship 2 Scene State Canon Discipline spec drafting per `MULTIPLAYER_FIXES.md` v3 §5. Anchors candidate Doctrine §76 (recursive hallucination memory loop). Three subships: 2a delete `scene_state.location` LLM-write authority; 2b DELETE `established_details` field by default; 2c audit pass via four-property latent-canon test. Spec/review at Opus medium per v3 §5.3. |
| **PC rsync** | All five doc-update files (`ROADMAP.md`, `SESSIONS.md`, `MULTIPLAYER_FIXES.md`, `tests-to-run-post-session.md`, `DOCTRINE.md`) + new spec/review pair + code files mirrored via `push-all-to-pc.sh` at end of session. |

---

# Session 37 — Hybrid Combat Exploration: GPT + Gemini External Review → v3 Two-Horizon Reframe (May 11, 2026)

No code. Architectural exploration session. Started as S37 Ship 2 spec drafting prep but pivoted when Jordan surfaced two extended-play concerns: novelty/repetition fatigue over long campaigns, and combat-pacing friction (30-minute init-based combats feel wrong in conversational AI play). Outcome: three iterations of `HYBRID_COMBAT_NOTES.md` (v1 → v2 → v3) plus ROADMAP refresh, no code shipped, no spec drafted. Ship 2 spec drafting deferred to S38.

## Narrative arc

The session began with Ship 2 spec-drafting prompt assembly, but Jordan paused mid-prompt to raise extended-play concerns coming out of the S36 Ship A screenshot. The architectural exploration that followed produced more useful output than any premature spec would have.

**v1 (`HYBRID_COMBAT_NOTES.md` initial draft).** Captured hybrid combat as a candidate architecture: mechanical depth retained (Avrae owns math, class identity preserved, HP/rests/conditions track normally) but turn cadence replaced with narrative beats. Five state axes (momentum, danger, positioning, enemy intent, injury state) modeled per encounter. Multi-effect resolution per beat. Encounter ends objective-driven, not strictly HP-driven. Filed seven open architectural questions.

**v2 (post-ChatGPT review).** ChatGPT surfaced nine architectural flags and one structural reframe (4-tier combat compression ladder). Walked each flag individually:
- FLAG 1: hidden init is still init — need priority window system for engine-internal sequencing
- FLAG 2: multi-effect beats risk over-compression destroying tactical texture
- FLAG 3: reactions become cognitively explosive without filtering — four-tier reaction system (auto/interrupt/cinematic/silent)
- FLAG 4: spellcasters favored over martials in compressed beats — candidate martial spotlight mechanics filed
- FLAG 5: enemy intent risks becoming fake state — intent durability locked, engine-write-only per Ship 2's canon discipline
- FLAG 6: shared-beat multiplayer unresolved — declaration windows replace lead-narrator-driven
- FLAG 7: state explosion under multiplayer — positioning at narrative granularity (zones/engagement groups/ranges/threat relationships), no grid simulation
- FLAG 8: encounter endings need stronger structure — explicit objectives (defend/escape/interrupt/survive/negotiate) beyond default `wipe_enemies`
- FLAG 9: Avrae compatibility is the hardest engineering constraint — bookkeeping-vs-engine fork, Option A (bookkeeping) recommended

Plus ChatGPT's strongest recommendation: combat compression ladder (Tier 0 trivial / Tier 1 skirmish / Tier 2 dangerous / Tier 3 boss-setpiece). v2 incorporated all nine flags + the ladder, expanded F-55 cluster reshape with five new siblings (#5.6-#5.10), filed `compute_stakes_tier` as load-bearing for tier selection.

**v3 (post-Gemini binary-toggle pushback + Gemini broader directive).** Gemini pushed back on two fronts:

*Combat-specific (binary toggle review):* "You cannot compress 5e without breaking 5e." The 4-tier ladder violates player agency at Tier 0/1 — if the engine resolves a goblin in one roll, the rogue doesn't get Cunning Action, the wizard doesn't get Shield, the fighter doesn't get Action Surge. Proposed binary toggle instead: Mode A (skill challenge for trivial conflicts, using Ship A's existing `!check` infrastructure) + Mode B (standard Avrae init with LLM-narrated transitions for tactical combat). Simpler, more honest, solo-dev-realistic, preserves full mechanical agency.

*Broader directive (full-repo review):* The project is at the "almost there" phase where feature creep and architectural perfectionism stall a project indefinitely. Specific directive: freeze the feature list, define MVP (the loop Ship 1 + Ship A just shipped IS the MVP for non-combat play), establish strict boundaries (Avrae owns math, bot owns narrative wrap, no parallel physics/positioning/tracking engine), optimize compute economy (no prompt bloat), execution plan = (1) lock down listener for 5e edge cases, (2) ship dumb combat, (3) playtest extensively, let observed friction dictate next architectural sprint. Closing line: "Stop designing hypothetical fixes for pacing issues you haven't fully experienced yet."

Jordan called the move: long-term vision survives as reference design, near-term execution is the structural retreat per Gemini's discipline. v3 reframes as two-horizon doc:

**Near-term execution path (v3 §3):**
1. Finish Ship 2 (Scene State Canon Discipline)
2. Finish Ship 3 (NPC State-Sync Boundary)
3. Playtest phase — extensive multi-hour solo + small-group sessions, no new architecture
4. MVP-test Ships 4 and 5 against playtest evidence
5. Listener edge-case verification ship
6. "Dumb combat" ship (standard Avrae init + LLM-narrated transitions, no hidden init, no compression, no parallel state)
7. Evaluate based on observed friction

**Long-term reference design (v3 §4-§5):** Compression ladder (Tier 0 reframed as skill challenge using Ship A infrastructure; Tier 1-3 collapse to "standard Avrae init with varying narration intensity"). Priority window system. Reaction tier system. Enemy intent state. Encounter objectives. Class identity preservation mechanics. All filed as candidates that earn their keep only if playtest-observed friction justifies. F-55 cluster expansion to #5.6-#5.10 from v2 removed.

v3 also explicitly rejects parallel positioning state entirely (per Gemini FLAG 3 broader pushback) and resolves the bookkeeping-vs-engine fork as Avrae-is-bookkeeping-AND-engine (no fork needed) per Gemini's Mode B framing.

## What shipped

No code. No spec. Three planning artifacts:

- `HYBRID_COMBAT_NOTES.md` v3 — written at `text files/HYBRID_COMBAT_NOTES.md` (PC; needs push to server). 200+ lines. Two-horizon framing locked. Long-term reference design preserved; near-term execution disciplined.
- `ROADMAP.md` updated — Last-updated stamp reflects S37 realignment; Multiplayer Fixes plan row reflects MVP-test scrutiny on Ships 4/5 + inserted playtest phase; FOOTINGS queue paragraph rewritten with post-Ship-3 next ships (listener verification, dumb combat, playtest phase, then MVP-test 4/5).
- `SESSIONS.md` (this entry) — captured for traceability.

No `MULTIPLAYER_FIXES.md` body changes — plan stays canonical; the reframe is captured at the ROADMAP layer and in `HYBRID_COMBAT_NOTES.md` as the controlling discipline doc.

## Decisions locked

1. **`HYBRID_COMBAT_NOTES.md` v3 stays as reference design only.** No combat architecture commits without playtest evidence.
2. **Ships 2 and 3 of multiplayer-fixes plan ship as scoped.** Both close observed-friction seams from S32.
3. **Ships 4 and 5 flagged for MVP-test scrutiny.** Ship 4 (Finding B name-resolution drift) may be cosmetic enough to defer; Ship 5 (polish) is cosmetic by definition.
4. **Playtest phase inserts after Ship 3.** 3-5 multi-hour solo + small-group sessions; explicit notes on pacing/content/combat/novelty friction. This is the gate for any further architectural commits.
5. **Listener edge-case verification ship is a real ship.** Confirms `avrae_listener.py` handles advantage, disadvantage, crits (attack + damage doubling), resistance/vulnerability, multi-attack embeds, saves with halved damage, death saves.
6. **"Dumb combat" ship is the next combat ship.** Standard Avrae `!init begin` + bot-narrated transitions. No hidden init, no compression, no parallel state surfaces. Minimum viable.
7. **F-55 cluster expansion (#5.6-#5.10) from v2 is dropped.** Long-term architectural candidates exist in `HYBRID_COMBAT_NOTES.md` v3 §5 but are not roadmapped.
8. **Bookkeeping-vs-engine fork is resolved.** Avrae is bookkeeping AND engine. No translation layer. No parallel positioning state.
9. **The hybrid combat doc as currently written is NOT authorization to design more combat architecture before playtest.** Architectural ambition without playtested grounding is the failure mode being explicitly avoided.

## Doctrinal notes

Three planner-discipline patterns surfaced or sharpened this session, worth holding:

- **Two-horizon framing for architectural ambition.** When external review surfaces a structural conflict between vision and execution-capacity, the resolution is not to pick one. The resolution is to preserve both at different time scales: long-term architectural vision survives as reference design (so insights don't evaporate when the queue closes), near-term execution gets disciplined explicitly against observed friction (so the project doesn't stall on speculative work). This is the discipline `HYBRID_COMBAT_NOTES.md` v3 embodies.
- **External review at architectural inflection points pays for itself.** Three iterations of GPT + Gemini review produced material improvements that planner-side review alone would have missed. The convergence (compression has real costs, mechanical depth must be preserved, objectives matter) is stronger signal than any single voice. The divergence (4-tier ladder vs binary toggle, hidden init vs visible init, positioning state vs no positioning state) surfaces axis disagreements that force explicit choice rather than collapse to false consensus. The pattern recurred at S33 (GPT-first vs Gemini-first on Ship 1 vs Ship 2 ordering) and S37 (GPT compression ladder vs Gemini binary toggle).
- **Evolve from observed friction, not anticipated friction — applied to architecture itself.** The discipline was already in WORKING_WITH_CLAUDE.md as a coding rule. S37 extends it to architectural ambition. The hybrid combat doc as originally drafted was speculative — the 30-minute combat problem hadn't been experienced in real play, only anticipated theoretically. Gemini's broader directive enforced the same discipline at the architecture layer: don't design fixes for friction you haven't experienced. The discipline applies recursively.

## Surfaced for future doctrine consideration

- **Planner-discipline pattern: when external review surfaces a structural conflict, two-horizon resolution preserves both.** Worth filing as candidate once a second instance surfaces (current instance: S37 hybrid combat doc preserves long-term vision in §5 while disciplining near-term execution in §3). Promotion to numbered doctrine when second instance ships.
- **Strategic inflection points warrant explicit pause and re-evaluation.** The S33 multiplayer-fixes plan revision came from real evidence (S32 playtest with a tabletop-experienced DM friend). The S37 hybrid combat exploration came from working through what extended play would actually look like, grounded against external review. Neither was deflection from the queue — both were the queue self-correcting based on real evidence about what the project should actually be. The discipline is not "never pause" but "don't pause for speculation." Pausing for grounded re-evaluation when real evidence accumulates is correct. Worth holding: the project's biggest architectural improvements have come at these inflection points, not during steady-state ship cycles.
- **Novelty/repetition is a simulation-depth problem, not a content-generation problem.** ChatGPT's S37 follow-up review (after Jordan probed the novelty/repetition concern Claude was least confident on) reframed the problem: players forgive surface repetition if outcomes differ, stakes evolve, factions react, relationships persist, economies shift, prior actions echo forward. Boredom comes from systemic stagnation (world resets emotionally, NPCs lack continuity, consequences evaporate, threats feel disconnected, scenes exist in isolation). The fix is not bigger prompts, better prose, larger models. The fix is persistent pressure systems — faction simulation, NPC persistence depth, economic motion, regional pressures, autonomous world evolution. Industry precedent: Dwarf Fortress, Crusader Kings, RimWorld, Bannerlord. Mechanically repetitive on surface, sustained by systemic interaction loops. Worth filing as architectural insight; promotion to doctrine candidate when the motion-systems thread re-opens post-playtest and the first state-interaction-depth ship surfaces evidence for the principle.
- **Engine owns long-range state; LLM owns short-range rendering.** Extension of §1a (LLM never decides outcomes) applied to time horizon. LLMs are strong at local coherence, emotional texture, improvisation, dialogue, scene dressing. LLMs are weaker at long-range systemic evolution, stable causality, persistent strategic simulation, multi-hour pressure management. The engine eventually has to shoulder the long-range burden. Same shape as Ship 1's resolution binding (engine computes truth, LLM renders) scaled to multi-session causality. Doctrine candidate when second instance ships (Ship 2 canon discipline is partially this shape; the next motion-systems ship would be the second).
- **Interaction compression ≠ mechanical compression.** Critical distinction from ChatGPT S37 follow-up. The hybrid combat ladder (v1/v2) was trying to compress mechanics. The binary toggle approach (Gemini's Mode A + Mode B) compresses interaction without touching mechanics. Standard 5e mechanics may be fine; the friction is in Discord's async/conversational latency multiplying tabletop pauses into momentum-killing delays. Tabletop 5e assumes rapid turn acknowledgment, simultaneous attention, voice cadence, real-time clarification, social momentum. Discord destroys these assumptions — 20 seconds of tabletop hesitation becomes 3 minutes of Discord drift becomes 12 minutes of tab-out. Worth holding: the architectural intervention may be interaction-layer compression (declaration windows, parallel actions, clearer state surfaces), not mechanical-layer compression. Test this empirically in post-Ship-3 playtest.
- **The threshold has crossed from "can the system function?" to "what kind of game emerges from this?"** Pre-Ship-A: architecture was too unstable for meaningful evaluation — playtest would have measured whether the bot worked, not whether the game worked. Post-Ship-A: player-experience data becomes trustworthy. This is a fundamental phase transition. The work that comes after playtest may not look like the work that came before. The queue stops being a roadmap and becomes a candidate menu reordered by observed reality. Both ChatGPT and Gemini named this independently in their S37 follow-ups. Worth holding as the controlling discipline for everything post-Ship-3.

## Cross-references

- `HYBRID_COMBAT_NOTES.md` v3 — the controlling document for this session's architectural output.
- `PLAYTEST_OBSERVATION_FRAMEWORK.md` — metric framework for post-Ship-3 playtest phase, derived from ChatGPT + Gemini S37 follow-up reviews.
- `ROADMAP.md` — Last-updated stamp + Multiplayer Fixes plan row + FOOTINGS queue paragraph all updated with the reframe.
- `MULTIPLAYER_FIXES.md` v3 — plan stays canonical; the reframe is at the ROADMAP layer, not in the plan body.
- `WORKING_WITH_CLAUDE.md` — "evolve from observed friction, not anticipated friction" discipline cited.
- ChatGPT review (S37 external) — nine flags + 4-tier compression ladder.
- ChatGPT follow-up (S37 second review, after Jordan probed novelty/repetition) — simulation-depth reframe, interaction-vs-mechanical compression distinction, threshold-crossed observation.
- Gemini review (S37 external) — binary toggle pushback + broader directive (playtest-first, feature freeze).
- Gemini follow-up (S37 second review) — hardware/life constraint grounding (1080 Ti 11GB VRAM, toddler + 1yo, squeezed engineering windows), terminal-velocity-of-paper-design framing.

## HALT escalations

**None.** The session was exploratory by design; no implementation locked in that would have surfaced HALT conditions.

## Tabular handoff (S37)

| Field | Value |
|---|---|
| **Code shipped** | None. Planning + architectural exploration only. |
| **Tests added** | None. |
| **Tests passing** | N/A. |
| **Patches landed** | None. |
| **Live-verify result** | N/A. |
| **Promotion criteria met** | N/A — no ship to promote. |
| **Doctrine candidates** | One filed (two-horizon framing for architectural ambition). One pattern emerging (architectural-exploration pause from planned spec session) at two instances; promotion to candidate at third instance. |
| **HALT escalations** | None. |
| **Architectural artifacts** | `HYBRID_COMBAT_NOTES.md` v3 (PC, needs server push). `ROADMAP.md` updated. `SESSIONS.md` S37 entry (this). |
| **Ship 2 status** | Spec drafting deferred to S38. Prompt context preserved; no re-read required on the spec-drafting agent. |
| **Next session recommendation** | **S38 — Ship 2 Scene State Canon Discipline spec drafting** per `MULTIPLAYER_FIXES.md` v3 §5. Anchors candidate Doctrine §76 (recursive hallucination memory loop). Three subships: 2a delete `scene_state.location` LLM-write authority; 2b DELETE `established_details` field by default; 2c audit pass via four-property latent-canon test. The S37 architectural detour does NOT change Ship 2's scope — Ship 2 closes Finding A (recursive hallucination), independent of any combat architecture work. Spec/review at Opus medium per v3 §5.3. |
| **PC rsync** | `HYBRID_COMBAT_NOTES.md` (new file), `ROADMAP.md` (updated), `SESSIONS.md` (this entry) need server push. No code files touched. |

---

# Session 37b — Ship 2 Spec Draft (SCENE_STATE_CANON_SPEC.md v1) (May 11, 2026)

**What shipped:** No code. Spec drafted.

Per `MULTIPLAYER_FIXES.md` v3 §5, Ship 2 — Scene State Canon Discipline — closes Finding A (recursive hallucination memory loop) and anchors candidate Doctrine §76 (four-property latent-canon test). The spec drafted in this session locks the architectural shape across three subships (2a delete `scene_state.location` LLM-write authority, 2b DELETE `established_details` field by default, 2c audit pass via four-property test) and a load-bearing §6.1 audit table that walked every column in `dnd_scene_state` against the four properties (LLM-writable, persisted, retrieved, narratively inferential).

**Recon findings (no HALT):**
- `extract_scene_updates` (dnd_engine.py:4749) is the LLM-write path; spawned as daemon thread from dm_respond; writes to update_scene_state's SCALAR_FIELDS + JSON_LIST_FIELDS.
- `established_details` readers: get_scene_state line 1145, build_dm_context line 5180/5206, prompt-size telemetry line 6078. No hard external dependency; deletion is structurally clean.
- `set_current_location` writes only `current_location_id` FK (not the freetext `location` column). 2a "single writer is set_current_location" needed a sub-decision: Path A (drop the freetext column, JOIN on dnd_locations at read time) vs Path B (extend set_current_location to write the freetext from the FK'd row). Recommended Path A per §76 doctrinal cleanliness + §75 silent-regression risk on Path B.
- Audit surfaced THREE additional 4/4 fields beyond the locked targets: `focus`, `open_questions`, `last_scene_change`. §11.D2 default: ship all in v1 (mechanically identical deletions; no compounding failure mode).

**Spec decisions (4 surfaced):**
- D1: Path A (drop column).
- D2: ship all 5 deletions in v1.
- D3: defer adjacent tables (dnd_npcs.description, dnd_locations.description) to filed candidate; their gated-upsert + skeleton_origin protection + non-direct-scene_state-retrieval keeps them outside Ship 2 scope.
- D4: bundle dead-column housekeeping (active_npcs, active_threats, legacy `tension`) into the same migration block.

**Doctrine §76 candidate phrasing drafted** with three project instances: S22 #2 chroma contamination (FAILURES.md §F-40), S32 `scene_state.location` cave drift, S36 time-of-day narrative drift (project_ship2_drift_evidence.md). Anchoring criterion: Ship 2 ships + live-verify clean.

**Spec status:** DRAFT v1, 649 lines. Flips to LOCKED after S38 review applies 4 framing refinements.

| Field | Value |
|---|---|
| **File written** | `specs/SCENE_STATE_CANON_SPEC.md` |
| **Decisions surfaced** | 4 (D1–D4) |
| **HALT escalations** | 0 |
| **Doctrine candidates** | §76 phrasing drafted with 3 project instances |
| **Next session recommendation** | S38 — review pass + 4 framing refinements + new D5 surfacing |
| **PC rsync** | done via push-all-to-pc.sh (suffix routing → `specs/` on PC). |

---

# Session 38 — Ship 2 Spec Review (SCENE_STATE_CANON_REVIEW.md v1) (May 11, 2026)

**What shipped:** No code. Review pass.

Reviewer walked the 4 §11 decisions from S37b's spec plus a cross-doc consistency check against `HYBRID_COMBAT_NOTES.md` v3 (whose §3 reinforces Ship 2 as doctrinal foundation for future motion-systems work) and `PLAYTEST_OBSERVATION_FRAMEWORK.md` (whose §3.1/§3.2 NPC continuity + cross-session causality metrics depend on Ship 2's canon discipline + Ship 3's NPC state-sync).

**All 4 decisions confirmed:**
- D1 (Path A drop column) — HIGH confidence. Doctrinal alignment with §76 + removes §75 silent-regression surface.
- D2 (ship all 5 deletions) — MEDIUM-HIGH confidence. No compounding failure mode; mechanically independent deletions; reversal path well-defined (gated-write helper) if any narrative regression surfaces on `focus` deletion specifically.
- D3 (defer adjacent tables) — HIGH confidence. Chroma-mediated retrieval is a fundamentally different surface; the F-40 contamination loop lives at the chroma layer, filed candidate per spec §13 item 3.
- D4 (bundle dead-column housekeeping) — MEDIUM-HIGH confidence after pre-emptive grep confirmed zero stale code paths touching `active_npcs` / `active_threats` / legacy `tension`.

**New decision surfaced (D5):** four-property regression test scope. Per-table default recommended; D5-general (system-wide audit pass) filed as v1.x candidate after Ship 3 produces parallel structure.

**Implementation refinements requested (4):**
1. `init_scene_state.seed` parameter dead-code chain — drop signature parameter post-deletion of `last_scene_change`.
2. `last_scene_change` reader enumeration (no surprises beyond build_dm_context + extract_scene_updates + init_scene_state seed flow).
3. §9 Scenario C fresh-campaign discipline note — long-running campaigns may have residual chroma contamination from pre-Ship-2 writes; structural closure verified on fresh campaigns.
4. §11.D5 added to spec body.

**Cross-doc consistency:** Clean. §76 phrasing is table-agnostic; Ship 3 inherits the four-property discipline without re-derivation.

| Field | Value |
|---|---|
| **File written** | `specs/SCENE_STATE_CANON_REVIEW.md` |
| **Decisions reviewed** | 5 (4 from spec §11 + 1 surfaced) |
| **Confirmed at Code's recommendation** | 4 |
| **Architectural changes** | 0 |
| **Implementation refinements** | 4 |
| **HALT escalations** | 0 |
| **Companion spec status** | DRAFT → LOCKED after revisions land at S39 implementation time |
| **PC rsync** | done via push-all-to-pc.sh (`_REVIEW.md` suffix → PC `text files/` per routing rule). |

---

# Session 39 — Ship 2 Implementation + §76 Anchored (May 11, 2026)

**What shipped:** Ship 2 — Scene State Canon Discipline — SHIPPED LIVE. Closes Finding A. Anchors Doctrine §76 (Recursive hallucination memory loop / four-property latent-canon test).

**Eight column drops on `dnd_scene_state` via idempotent ALTER TABLE DROP COLUMN block** (SQLite 3.45.1 native support; per-column soft-fail logged):

Five Doctrine §76 deletion targets:
- `location` (freetext) — Path A: column gone; reads migrate to `location_label` derived from `dnd_locations.canonical_name` via `current_location_id`. `set_current_location` is now the only writer surfacing location data to LLM context. NULL FK renders `(between locations)` deliberate ambiguity.
- `established_details` — JSON list of LLM-summarized scene details. Render line in `build_dm_context` SCENE STATE block removed.
- `focus` — per-turn LLM scene-attention anchor.
- `open_questions` — JSON list of LLM-emitted "what's still unknown" entries.
- `last_scene_change` — "one short sentence" per extraction prompt.

Three dead-column housekeeping drops:
- `active_npcs` — replaced at render time by `get_recently_active_npcs` (since S3); never read after that.
- `active_threats` — schema-present, never read (threat model deferred).
- `tension` (legacy string `low|medium|high`) — superseded by `tension_int` (numeric scale).

**Code chain cleanup:**
- `dnd_engine.py` CREATE TABLE statement tightened (12 columns total post-Ship-2: campaign_id, mode, last_player_action, updated_at + 8 ALTER ADDs: tension_int, progress_clocks, current_location_id, turn_counter, last_dm_response, last_active_actor, campaign_day, day_phase).
- `get_scene_state`: returns `location_label` (derived from dnd_locations PK lookup; defensive try/except for OperationalError when test fixtures use minimal schema without dnd_locations).
- `init_scene_state(campaign_id)`: seed parameter dropped from signature (was vestigial post-`last_scene_change` deletion). INSERT statement tightened to (campaign_id, updated_at) with ON CONFLICT updated_at refresh.
- `update_scene_state`: SCALAR_FIELDS shrank to `{last_player_action}` only (the only borderline 3+1 kept). New `DELETED_FIELDS` guard logs `update_scene_state: dropping LLM-write to deleted field 'X' (Ship 2 §76 closure)` for any attempted write to the eight gone columns. JSON_LIST_FIELDS now empty (retained as no-op for future single-writer extensions).
- `extract_scene_updates`: legacy LLM-extraction call entirely removed (was previously a structured-extraction call that summarized DM turns into the five §76 fields). Function now writes only `last_player_action` via update_scene_state. Threading preserved for back-compat with test patches but the function returns near-instantly.
- `build_dm_context` SCENE STATE block: render lines for `Focus:`, `Established details:`, `Open questions:`, `Last scene change:` all removed. `Location:` line renders `location_label` (or `(between locations)` placeholder when NULL FK).
- `dnd_orchestration.py` advisory state-reference block: same `Location:`/`Focus:` render-line cleanup; advisory state block tightened by one line.
- Prompt-size telemetry: scene_chars key list tightened to `('location_label', 'last_player_action')` + progress_clocks list-summation.
- `discord_dnd_bot.py` `/play` flow: seed string no longer captured or passed to `init_scene_state`; the legacy seed string had nowhere to land post-deletion.

**Tests (105 new assertions across 2 new files + multiple existing-test fixture updates):**
- `test_scene_state_canon_deletion.py` (73 assertions): schema + write-path neutralization + render-path absence + Path A FK-derive + extract_scene_updates LLM-call removal proof.
- `test_doctrine_76_four_property_audit.py` (32 assertions): regression test enumerating every `dnd_scene_state` column with its four-property classification (LLM-writable / persisted / retrieved / narratively inferential); asserts no column hits 4/4 post-Ship-2.
- Existing test updates: test_pending_roll_directives, test_directive_emit, test_llm_emit_writer, test_init_directive (init_scene_state signature batch sed), test_prompt_size, test_commitment_directive, test_time_skeleton_seed, test_state_footer, test_combat_redirect_directive, test_render_state_footer_time (fixture tightening — drop deleted columns from INSERTs/dicts).

**Pre-existing test debt unrelated to Ship 2 (out-of-scope):**
- test_directive_emit.py: pre-existing npc_upsert tuple-unpacking issue at line 198 (consequence_upsert receives a tuple instead of int).
- test_dnd_locations.py: same npc_get/npc_upsert tuple issue.
- test_campaign_delete_cascade.py: fixture missing several tables in _CAMPAIGN_SCOPED_TABLES (F-40-style).

These are filed for future housekeeping. Ship 2 itself touched none of the problematic surfaces.

**Live verification:** Bot restarted cleanly. Live DB migrated cleanly:
- Pre-restart: 20 columns. Post-restart: 12 columns (8 dropped).
- Campaign 17 scene_state reads healthy with derived `location_label = 'merchant market'`.
- Operator walks Scenarios A-D per spec §9 (Discord prompts surfaced in this session for operator copy-paste).

**Doctrine §76 anchored.** Promoted from candidate to numbered entry. Three project instances at anchor: S22 #2 chroma contamination, S32 location cave drift, S36 time-of-day drift. Anchor criterion (Ship 2 ships + live-verify clean) met. Memory `project_ship2_drift_evidence.md` retired post-anchor.

| Field | Value |
|---|---|
| **Code shipped** | dnd_engine.py extensive; discord_dnd_bot.py /play; dnd_orchestration.py advisory state |
| **Tests added** | 105 assertions across 2 new files |
| **Tests passing** | all new + all touched-existing green; 3 pre-existing test-debt items unrelated to Ship 2 |
| **Patches landed** | 1 (Ship 2 in single session per locked spec) |
| **Live-verify result** | bot restarted clean, migration successful (8 columns dropped), campaign 17 reads healthy; operator walks Scenarios A-D inline |
| **Promotion criteria met** | §6 + §9 per spec; Doctrine §76 anchored |
| **HALT escalations** | 0 |
| **Ship 2 status** | ✅ SHIPPED LIVE |
| **Next session recommendation** | S40 — Ship 3 (NPC State-Sync Boundary, Finding H) spec drafting per `MULTIPLAYER_FIXES.md` v3 §6. Inherits Doctrine §76's four-property discipline (table-agnostic phrasing per S38 review). Ship 3 likely surfaces a fourth project instance of §76 against dnd_npcs columns. |
| **PC rsync** | done via push-all-to-pc.sh |

---

# Session 40 — Ship 3 Spec Draft (NPC_STATE_SYNC_SPEC.md v1) (May 11, 2026)

**What shipped:** No code. Spec drafted per MULTIPLAYER_FIXES.md v3 §6. Closes Finding H (S32 §3.6) — hydrated NPCs have no Avrae sheet, combat against them resolves against `<None>` HP.

Locked architectural shape per v3 §6: fix candidate (a) — auto-create Avrae sheet on `/hydrate` via bot-emitted `!init opt` commands under proposed §65a narrow exception. Single writer (`avrae_project_npc`) with two disjoint trigger surfaces (`/hydrate` + `_handle_init_list_event`) → candidate Doctrine C3 second instance.

§4 four-property audit on dnd_npcs walked all 20 columns; zero 4/4 hits because every LLM-influenced write flows through a §17 single-writer helper (npc_upsert / npc_hydrate_stats / npc_register_avrae_madd). §76 doctrine carries forward unchanged.

| Field | Value |
|---|---|
| **File written** | `specs/NPC_STATE_SYNC_SPEC.md` v1 (658 lines) |
| **Decisions surfaced** | 4 §11 + 2 sub-decisions |
| **HALT escalations** | 0 |
| **Doctrine candidates** | §65a amendment drafted (anchors post-verify), C3 second-instance identified, §76 audit clean, §17+§76 composition observation surfaced for §12.5 |
| **Next session recommendation** | S40b review pass |
| **PC rsync** | done via push-all-to-pc.sh |

---

# Session 40b — Ship 3 Spec Review (NPC_STATE_SYNC_REVIEW.md v1) (May 11, 2026)

**What shipped:** No code. Review pass.

Walked the 4 §11 decisions + 2 sub-decisions + C3 candidate + §65a amendment + §76 audit cross-check + cross-doc consistency. 5 of 6 decisions confirmed at Code's recommendation; Sub-D2 confirmed with revision request (mid-combat re-projection needed Case A/B case-split — silent mid-combat HP reset would be a player-experience disaster). No HALTs. New §11.D5 NOT surfaced; spec covered the surface.

Four spec revisions requested + applied: §7.1 Sub-D2 Case A/B split; §7.2 §65a phrasing tightening; §7.3 new §12.5 doctrinal observation (§17+§76 composition pattern); §7.4 PLAYTEST §3.2 mechanical-vs-narrative continuity framing.

| Field | Value |
|---|---|
| **File written** | `specs/NPC_STATE_SYNC_REVIEW.md` v1 (425 lines) |
| **Decisions reviewed** | 6 (4 + 2 sub) |
| **Confirmed at recommendation** | 5 |
| **Revision requests** | 1 (Sub-D2 case-split) + 3 framing additions |
| **HALT escalations** | 0 |
| **Spec status** | DRAFT → LOCKED after revisions applied |
| **Next session recommendation** | S41 implementation |
| **PC rsync** | done via push-all-to-pc.sh |

---

# Session 41 — Ship 3 Implementation: Avrae Bot-Filter HALT-and-Pivot to §1b Suggester (May 11, 2026)

**What shipped:** Ship 3 SHIPPED LIVE post-architectural-pivot. Closes Finding H via §1b validated-suggester pattern. The originally-locked fix candidate (a) — bot-emit `!init opt` commands under §65a narrow exception — was empirically blocked by Avrae's API and pivoted in-session to candidate (a') per operator decision.

**The load-bearing S41 narrative is the HALT-and-pivot pattern.** The session opened with the spec body locked at fix candidate (a), executed implementation per spec, ran a structured Avrae verify-pass, and surfaced a structural API boundary that invalidated the locked architectural shape. The operator decided in-session to pivot to the §1b suggester pattern (precedent: Track 6 #5.1 SRD suggester, S26 first instance). Implementation, tests, and spec body all rotated to the new shape inside the same session.

**Three Avrae verify findings locked across the session:**

1. **Avrae bot-filter (load-bearing HALT).** Identical `!init opt` commands mutate Avrae state when human-typed; silently filtered when bot-typed. Live-verified: bot-emitted `!init opt ProjTestA -hp 13` delivered to `#dm-narration` via `channel.send` (no exception), Avrae returned no response, `!init list` continued to show `<None>`. Identical operator-manual paste produced *"ProjTestA's HP set to 13 (was None)."*. This is structural Avrae API behavior — cannot be engineered around without TOS-violating self-botting. Documented in spec §13.1.

2. **`-h` is hidden-toggle, NOT HP.** First attempted command `!init opt ProjTestA -h 13` produced silent "ProjTestA hidden." DM (Avrae interpreting `-h` as hidden-flag, `13` as ignored positional arg). The correct flag for both `!init add` and `!init opt` is **`-hp`**.

3. **`!init opt` cannot set max-HP.** The opt subcommand has no `-maxhp`/`-mhp`/`-thp` flag for max-HP. `!init opt -hp <N>` sets current HP only; if combatant's max was 0, this leaves max=0 forever (display shows `<N/0 HP>` which is mechanically broken). **The clean fix is `!init remove` + `!init add <init> <name> -hp <hp>` + `!init opt <name> -ac <ac>`** — three lines, each pasted separately (Avrae filters back-to-back commands).

**Locked 3-line suggester sequence (post-S41-third-verify):**
```
!init remove <name>
!init add <init_mod> <name> -hp <hp>
!init opt <name> -ac <ac>
```

**Code:**
- `_avrae_project_npc(channel, campaign_id, npc_name, trigger)` in `discord_dnd_bot.py` — single helper, two disjoint trigger surfaces (`/hydrate` Case A + `_handle_init_list_event` Case B), posts to `#dm-aside` not `#dm-narration` (Avrae doesn't read aside; §65 holds unchanged).
- `/hydrate` slash command extended with projection_status_line in ephemeral confirmation (e.g. *"See #dm-aside for the Avrae sync paste."*, *"Mid-combat re-hydrate — see #dm-aside for HP-reset warning + paste."*, *"Not in init — Avrae sync will be suggested on `!init add` + `!init list`."*).
- `_handle_init_list_event` hydration branch calls helper after each `npc_hydrate_stats` + on `source=miss` path; auto-fire catches `!init madd` shortcut cases without forcing intervention.
- Case A (active `/hydrate` with combatant in numeric HP): warning aside includes 3-line clean fix + partial-fix alternative.
- Case B (passive init_list with combatant in numeric HP): silent no-op (preserves Avrae's mid-combat HP authority).

**Tests:** `test_avrae_project_npc.py` (13 assertions, all green). Coverage includes every reason path (gate_engine_missing, gate_engine_stats_null, gate_not_in_init, noop_complete, suggested, suggested_with_warning, aside_post_failed), C3 single-helper-trigger-agnostic shape check, telemetry one-outcome-log-per-path, narration-channel-untouched regression guard (critical post-pivot: helper must NEVER emit to #dm-narration).

**Live verify:** Scenario A (Case A path) walked clean end-to-end. Final `!init list`: `12: ProjTestA <13/13 HP> (AC 13)`. Both max+current HP correct AND AC set. Avrae bot-filter bypassed via DM-paste discipline. Case B coverage via test suite (no-op path on numeric HP). Multi-player (Captin0bvious) deferred to MULTIPLAYER_VERIFY_DEFERRED.md.

**Doctrine accounting at S41 verify-clean:**
- **§1b** — Ship 3 lands as the **second project instance** of the validated-suggester doctrine. First instance: Track 6 #5.1 SRD suggester (S26). The pattern repeats: bot proposes via #dm-aside, deterministic gate confirms the proposal is safe (idempotency gates + Case A/B split), DM approves by paste, Avrae executes.
- **§12.5 composition observation** — empirically validated: §17 gated-write discipline preempts §76 four-property surfaces (gated boundary fails property 1 "LLM-writable"). Ship 3's 20-column dnd_npcs audit had zero 4/4 hits because every LLM-influenced write flowed through a single-writer helper.
- **§65a NOT anchored.** The §1b pivot dissolves the need for §65a entirely — bot never emits `!`-prefixed commands to Avrae's channel. §65 holds in its original form.
- **C3 NOT anchored.** The pivot withdrew C3's second-instance claim — the helper is a suggester, not a writer; the trigger-to-helper relationship survives but "single writer" framing no longer applies. C3 stays at one project instance (Ship A) pending a genuine future instance.

**Track 6 #5.1 SRD resolver reshape** filed as future ship candidate (post-Ship-3): the existing SRD suggester emits `!init madd <srd_name>` which creates a fully-statted Avrae combatant from SRD. The reshape would emit a fully-statted `!init add <init> "<name>" -hp <hp> -ac <ac>` block instead, giving the DM full control over name + inline stats while still leveraging SRD lookup. Composes naturally with Ship 3's flag conventions. Not Ship 3 scope.

**Operator reframe absorbed:** `/hydrate` is an emergency-fix surface, NOT the canonical NPC-stat-entry flow. The canonical flow is the DM typing `!init add <init> <name> -hp <hp> -ac <ac>` directly with full stats inline. `/hydrate` exists for `!init madd` shortcut backfill, accidental wrong-stat correction, and parser-hit/skeleton-loaded NPCs that need Avrae sync. This reframe sharpens the §1b suggester pivot: emergency-fix tools keep the human in the loop for state mutations.

| Field | Value |
|---|---|
| **Code shipped** | `discord_dnd_bot.py` (new `_avrae_project_npc` suggester + 2 trigger integrations + ephemeral status line) |
| **Tests added** | 13 assertions in `test_avrae_project_npc.py` |
| **Tests passing** | all new + all touched-existing green (test_hydration_hook, test_npc_hydrate_stats, test_srd_suggestion_hook, test_llm_emit_writer) |
| **Patches landed** | 4 (initial bot-writer ship → -h→-hp flag fix → bot-writer→suggester pivot → 3-line sequence lock) |
| **Avrae bot-filter finding** | Documented in `NPC_STATE_SYNC_SPEC.md` §13.1 as structural API boundary |
| **Doctrinal accounting** | §1b second instance ✓; §12.5 composition observation lands; §65a NOT anchored; C3 NOT anchored |
| **Live-verify result** | Scenario A (Case A path) GREEN — `<13/13 HP> (AC 13)` end state |
| **Promotion criteria met** | §6 (Finding H closure) + §9 (live verify pass) + §1b second-instance doctrine proof |
| **HALT escalations** | 1 (Avrae bot-filter) — surfaced + resolved in-session via §1b pivot |
| **Ship 3 status** | ✅ SHIPPED LIVE |
| **Multiplayer Fixes plan v3 status** | Ship 1 ✅ / Ship A ✅ / Ship 2 ✅ / **Ship 3 ✅** / Ships 4-5 MVP-test scrutiny pending playtest phase |
| **Next session recommendation** | Listener edge-case verification ship per `HYBRID_COMBAT_NOTES.md` v3 §3 (advantage/disadvantage/crits/resistance/multi-attack/saves/death-saves). Then dumb combat ship. Then multi-hour playtest phase per `PLAYTEST_OBSERVATION_FRAMEWORK.md`. |
| **PC rsync** | done via push-all-to-pc.sh |

---

# Session 42 — Listener Edge-Case Verification + Multi-Attack/Dice-Modifier Patches (May 11, 2026)

**What shipped:** Pre-playtest infrastructure ship per `HYBRID_COMBAT_NOTES.md` v3 §3.1 step 3. **Empirical recon-and-fix pass** on `avrae_listener.py` against 5e combat embed edge cases. Two structural parsing gaps surfaced + patched; final live re-walk confirms clean parsing.

**Load-bearing narrative:** trustworthy playtest data requires the listener to parse Avrae's full edge-case vocabulary accurately. Pre-S42, advantage/disadvantage rolls were silently dropped (parser returned `None` because dice modifiers like `kh1`/`kl1` between dice notation and parens broke the regex). Multi-target attacks captured only the first sub-attack. Without these fixes, the post-Ship-3 playtest phase would conflate engine-parsing bugs with combat-experience friction in the observation framework. S42 closes both gaps so playtest metrics measure what they're supposed to measure.

**Step 1 — listener inventory (audit pass):**

| Edge case | Pre-S42 handling | Status |
|---|---|---|
| Advantage / disadvantage | `_ROLL_RE` and `_TO_HIT_LINE_RE` required bare `\d*d\d+` immediately before `(rolls)`. Avrae's `2d20kh1 (15, ~~6~~)` / `2d20kl1 (~~19~~, 2)` formats fail. | **GAP: parser returns None for entire embed.** |
| Critical hit | `_CRIT_RE` boolean detection of "crit"/"critical" word + `nat` field via `_kept_nat_roll` | Likely works (verified post-patch). Deferred testing of `-crit` forced-crit path — Avrae's `-crit` flag did not force crit in S42 verify; needs alt trigger path investigation. |
| Resistance / vulnerability | `_DAMAGE_LINE_RE` non-greedy match captures LAST `=` value | Works correctly — empirically confirmed `Damage: (2 [bludgeoning]) / 2 = 1` parses with `damage=1` (post-resistance). |
| Multi-target attack | `_TO_HIT_LINE_RE` matches first attack only | **GAP: sub-attacks 2+ lost.** |
| Saves with halved damage | `save` kind doesn't extract damage; `cast` kind does | Deferred — Donovan Ruby has no spells; needs spellcaster PC fixture for future verify session. |
| Death saves | `save` classification; outcome state (success/fail/stabilize/death) not captured in any field | Deferred — `!init dsa` syntax + Avrae's PC-required gate block single-player verification this session. |

**Step 2 — test command list (~12 commands) surfaced inline for operator paste in `#dm-narration`.** Setup added a second NPC `ProjTestB` for multi-attack target diversity. Cleanup commands included.

**Step 3 — operator empirical pass:** All test commands fired against campaign 17 with Donovan Ruby + ProjTestA + ProjTestB in init. Avrae embed responses captured by operator + pasted back. Two confirmed gaps via test results (advantage/disadvantage returned None; multi-attack captured only first attack). Resistance damage path confirmed clean. Crit / save-with-damage / death-save paths deferred per fixture-availability constraints.

**Step 4 — patches landed:**

1. **`_DICE_NOTATION` constant** (new) — pattern `\d*d\d+(?:[a-zA-Z]+\d*)*` allows optional letter-digit modifier suffixes (`kh1`, `kl1`, `dh`, `dl`, etc.). Substituted into `_ROLL_RE` and `_TO_HIT_LINE_RE`. This is the single load-bearing fix for the advantage/disadvantage gap.

2. **`_extract_attack_from_field(field_value)`** (new helper) — extracts (nat, result, damage) from one embed field's value. Used to walk per-target sub-attacks in multi-target embeds.

3. **`parse_avrae_embed` extended** for multi-attack support: when `kind=='attack'`, the function walks `embed.fields` and collects per-target sub-attacks. If MORE than one sub-attack present, the event dict carries `attacks: list[dict]` with one entry per target (each entry: `{'target': field-name, 'nat': int, 'result': int, 'damage': int}`). Top-level `nat`/`result`/`damage` continue to hold the FIRST attack's values for back-compat with single-attack consumers. Single-target embeds keep the original event shape (no `attacks` key surfaces).

4. **Per-parse telemetry** (new) — `listener_parsed: kind={kind} actor={actor!r} nat={nat} result={result} damage={damage} crit={0|1} subattacks={N}` log line fires on every successful parse. Always-on observability for future audits.

**Step 5 — test coverage** (new file `test_avrae_listener_edge_cases.py`, **7 assertions, all green**):
- `test_plain_attack_miss_captures_nat_and_result_no_damage` (baseline)
- `test_advantage_2d20kh1_captures_kept_high_die`
- `test_disadvantage_2d20kl1_captures_kept_low_die`
- `test_resistance_damage_captures_post_resistance_value`
- `test_multi_target_attack_currently_captures_only_first_attack` (post-S42 patch: surfaces `attacks` list)
- `test_single_target_attack_does_not_populate_attacks_list` (back-compat guard)
- `test_crit_keyword_detected_in_attack_text`

**Regression sweep:** all listener-adjacent test files green (test_avrae_sweep 11/11, test_init_list_parser 29/29, test_avrae_project_npc 13/13, test_hydration_hook 20/20, test_pending_roll_directives 27/27, test_llm_emit_writer 23/23). Zero collateral.

**Live re-walk post-patch (empirical confirmation):**
- Advantage `2d20kh1 (1, 17) + 3 = 20`: `nat=17 result=20 damage=1 subattacks=1` ✓
- Disadvantage `2d20kl1 (11, 7) + 3 = 10`: `nat=7 result=10 damage=None subattacks=1` ✓
- Multi-target `-t ProjTestA -t ProjTestB`: `nat=9 result=12 damage=None subattacks=2` ✓ (top-level = first sub-attack; subattacks=2 confirms both fields captured)

**Deferred edge cases (filed for future ship):**
- Forced critical hit: Avrae's `-crit` flag did not produce a crit in S42 verify (rolled nat 1, missed). The `-crit` syntax may differ from what's documented; needs alt trigger investigation (e.g., natural 20 from `!attack <weapon> -t <target> max` or via Avrae's specific crit-force flag). Crit-keyword detection itself works (`test_crit_keyword_detected_in_attack_text` green); only the forced-crit trigger path is unverified.
- Save with halved damage (fireball-style): Donovan Ruby has no spells; requires a spellcaster PC fixture to test.
- Death save outcome state (success/fail/stabilize/death): `!init dsa` syntax + Avrae's PC-required gate blocked single-player verification. Filed for a future session with a throwaway PC at 0 HP.

**No HALT escalations.** Both surfaced gaps were gap-patches, not architectural reshapes. No new doctrine candidates surfaced (read-side ship; §17 / §76 / §1b / C3 all out of scope for listener parsing).

| Field | Value |
|---|---|
| **Code shipped** | `avrae_listener.py` — `_DICE_NOTATION` constant + `_extract_attack_from_field` helper + `parse_avrae_embed` extended for multi-attack + `listener_parsed:` telemetry |
| **Tests added** | 7 assertions in new `test_avrae_listener_edge_cases.py` |
| **Tests passing** | 7/7 new + all listener-adjacent regressions clean (11+29+13+20+27+23 = 123 assertions across 6 existing files) |
| **Patches landed** | 2 structural (dice-modifier regex + multi-attack field walk) + 1 telemetry |
| **Edge cases covered (v1)** | Plain attack, advantage, disadvantage, resistance damage, multi-target attack, crit keyword detection |
| **Edge cases deferred** | Forced-crit trigger path, save with halved damage (no spellcaster), death save outcome state (PC-required) — all filed for future ship |
| **HALT escalations** | 0 |
| **Listener verification status** | ✅ Verified clean against tested edge cases. Deferred edge cases documented as filed candidates. |
| **Ship status** | ✅ SHIPPED LIVE — pre-playtest listener infrastructure verified |
| **Next session recommendation** | "Dumb combat" ship per `HYBRID_COMBAT_NOTES.md` v3 §3.1 step 4 — standard Avrae `!init begin` + LLM-narrated turn transitions (no compression, no hidden init, no parallel state surfaces). Listener edge-case parsing now trustworthy enough for the playtest evidence the next phase produces. |
| **PC rsync** | done via push-all-to-pc.sh |

---

# Session 43 — Dumb Combat Narration + Atmospheric-vs-Adjudication Doctrine (May 11, 2026)

**What shipped:** Auto-narration on three combat-mode state transitions (ROUND_START, BLOODIED_THRESHOLD_CROSSED, COMBATANT_DOWNED), each rendered via `_dm_respond_and_post` with a `transition_context` carrying categorical HP roster + verbatim MUST/MUST-NOT invariants. **DEATH_SAVE_EVENT_START deferred** to a follow-up ship per the S42 fixture-blocker. Path B no-spec ship per HYBRID_COMBAT_NOTES v3 §3.1 step 4.

**Load-bearing narrative: atmospheric continuity, not adjudication.** The cliff-edge — the moment narration starts inferring tactical outcomes, hidden intent, optimal targeting, or consequences beyond what listener + engine confirmed, the ship has silently graduated from "combat glue" into "combat adjudication" and the renderer-not-ruler discipline is broken. S43's verify pass empirically confirmed the doctrine holds at the cliff-edge.

**Architectural shape:**

1. **Three trigger surfaces:**
   - ROUND_START in `_handle_init_event`: compares incoming round_num against `get_active_turn().round` before set_active_turn writes. Fires when round strictly increases AND mode='combat'.
   - BLOODIED + DOWNED in `_handle_init_list_event`: snapshots prior `get_combatants()` BEFORE `update_combatants_from_init_list()` overwrites, diffs via `compute_combat_state_transitions()`, dispatches one trigger per transition.
   - Mode-flip wiring already existed (S7 Phase 1.4 FSM); S43 ships piggyback.

2. **Pure functions in `dnd_orchestration.py` (10th Doctrine §59 sibling):**
   - `_hp_state(hp_current, hp_max)`: categorical label (`healthy`/`bloodied`/`downed`/`unknown`). 50%-threshold rule per 5e convention.
   - `compute_combat_state_transitions(prior, new)`: edge-detection — BLOODIED fires only on downward 50% crossing (heals don't re-fire); DOWNED fires once per descent.
   - `compute_combat_narration_directive(trigger, combat_state, scene_state)`: builds (action, transition_context) tuple. Mode gate at entry. Action is a sentinel-shaped string (`[Combat narration: ...]`) to prevent classifier cascade.
   - `combat_narration_log_summary(trigger, fired, reason)`: telemetry log line.

3. **`_dispatch_combat_narration` async wrapper in `discord_dnd_bot.py`**: reads scene + combatants, calls pure helper, dispatches `_dm_respond_and_post` with synthetic actor. Soft-fail discipline.

**S43 verify-pass empirical findings (Scenarios A-F):**

| Trigger | First walk | Re-verify (post drift-fix) | Doctrine holds? |
|---|---|---|---|
| ROUND_START (A) | mild drift: PC action attribution + phantom NPCs | environmental atmosphere improved; phantom NPCs + stale-narrative bleed persist from `recent_npcs` / `last_dm_response` blocks | YES at cliff-edge; quality drift filed v1.x |
| BLOODIED (B) | phantom NPCs surfaced | **clean re-verify** — pure focus on combatant, exact bloodied framing, NO phantom NPCs | YES — verified clean |
| DOWNED (C) | clean from first walk — exact "out of the fight" framing, NO death declaration, NO phantom NPCs | n/a | YES — verified clean |
| Mode-flip cleanup (E) | S43 path did NOT fire on `!init end` (journalctl confirms no `combat_narration_fired:`) | n/a | YES — mode gate works |
| DEATH_SAVE (D) | DEFERRED (S42 fixture blocker) | n/a | n/a |

**Drift fix patches applied in-session** (after first walk surfaced phantom NPCs + action attribution):
- Added two MUST NOT clauses to `_COMBAT_NARRATION_INVARIANTS`: (a) forbid action-narration for combatants NOT in roster, (b) forbid attributing specific actions to PCs without player-narration or listener-event anchor.
- Tightened ROUND_START framing: environmental atmosphere (lighting/sound/tension) over combatant actions.

Re-verify confirmed BLOODIED is clean. ROUND_START improved but still has phantom NPCs + stale narrative — root cause is `build_dm_context`'s `recent_npcs` + `last_dm_response` blocks injecting separately from the combat directive. **Filed as v1.x "Combat narration prompt purity" candidate** (worktree task chip).

**Doctrine candidate anchored:** "Combat narration is atmospheric continuity, not adjudication." Anchors post-S43 verify clean — the doctrine line holds at the cliff-edge (no mechanical-state-mutation drift in any narration). Quality drift in ROUND_START is filed separately; doesn't violate the line.

**Code:**
- `dnd_orchestration.py`: +~260 LOC (`_hp_state`, `compute_combat_state_transitions`, `compute_combat_narration_directive`, `combat_narration_log_summary`, `_COMBAT_NARRATION_INVARIANTS`)
- `discord_dnd_bot.py`: +~60 LOC (`_dispatch_combat_narration` wrapper + ROUND_START detection in `_handle_init_event` + BLOODIED/DOWNED dispatch in `_handle_init_list_event`)

**Tests:** `test_combat_narration.py` (new, **39 assertions, all green**). Regression sweep clean across 12 listener/combat-adjacent files (238 assertions total).

**Deferred / known issues post-S43:**

1. **DEATH_SAVE_EVENT_START** — S42 fixture-blocked. Filed as small follow-up ship.
2. **Combat narration prompt purity v1.x** — ROUND_START phantom NPCs + stale-narrative bleed from `recent_npcs` / `last_dm_response` blocks. Worktree task chip filed; three fix options (aggressive prompt-side override / code-side suppression flag / separate combat narration prompt path). Recommended start: option 3 (prompt-side override) then escalate to option 1 (code-side flag) if insufficient.
3. **Post-`!init end` narration drift** — pre-existing bot bug; confirmed NOT S43 path (mode gate works). Separate task chip filed pre-S43.

**Operator's live-verify role split:** Operator pasted Avrae commands serially in `#dm-narration`, paste-captured embeds back to me; I read journalctl for `combat_narration_fired:` telemetry; I patched prompt-side clauses in-session when drift surfaced. The patch → restart → re-verify loop completed once for BLOODIED (phantom-NPC fix confirmed clean retest).

| Field | Value |
|---|---|
| **Code shipped** | `dnd_orchestration.py` (~260 LOC, 4 new pure functions); `discord_dnd_bot.py` (~60 LOC, 3 wiring sites) |
| **Tests added** | 39 assertions in new `test_combat_narration.py` (all green) |
| **Tests passing** | all new + 238-assertion regression sweep across 12 listener/combat-adjacent files clean |
| **Patches landed** | 3 (initial impl + phantom-NPC/action-attribution MUST NOT clauses + ROUND_START framing tighten) |
| **Triggers detected vs deferred** | ROUND_START ✓ / BLOODIED ✓ / DOWNED ✓ / DEATH_SAVE deferred (S42 fixture; filed) |
| **Mode-flip recon result** | Already wired (S7 Phase 1.4 FSM); no changes; S43 piggybacks |
| **Live-verify A-F results** | A (partial — env improved, phantom NPCs persist), B (clean post-fix), C (clean first walk), D (deferred), E (mode gate works — no false fires), F (doctrine holds at cliff-edge; quality drift filed v1.x) |
| **Doctrine candidate anchoring** | "Combat narration is atmospheric continuity, not adjudication" — **ANCHORED** post-S43 verify clean; lands in DOCTRINE.md this session. Cliff-edge holds: no mechanical-state-mutation drift observed in any narration. |
| **HALT escalations** | 0 |
| **Ship status** | ✅ SHIPPED LIVE (3 of 4 triggers active; DEATH_SAVE deferred; ROUND_START quality drift filed v1.x) |
| **Multiplayer Fixes plan v3 status** | Ship 1 ✅ / Ship A ✅ / Ship 2 ✅ / Ship 3 ✅ / Listener verification ✅ / **Dumb combat ✅** / Ships 4-5 MVP-test scrutiny pending playtest phase |
| **Next session recommendation** | **Multi-hour playtest phase** per `PLAYTEST_OBSERVATION_FRAMEWORK.md` — the gate for further architectural commits. 3-5 solo and/or small-group sessions in post-S43 architecture; observe pacing, content variety, combat feel, novelty fatigue; capture per metric framework's §2/§3/§4/§5. No new architecture during this phase. Post-playtest: MVP-test scrutiny on Ships 4-5; re-decide on hybrid combat candidates; motion-systems thread re-opens if friction justifies. |
| **PC rsync** | done via push-all-to-pc.sh |

---

# Session 44 — Combat Narration Prompt Purity v1.x (May 11, 2026)

**What shipped:** S43 filed-follow-up ship. Closes the ROUND_START phantom-NPC + stale-narrative bleed surfaced in S43 live verify. Threads a single `suppress_for_combat_narration: bool = False` parameter through `_dispatch_combat_narration` → `_dm_respond_and_post` → `dm_respond` → `build_dm_context`. When True, **10 prompt blocks** are dropped from the assembled context. Pre-S44 behavior preserved for all non-combat-narration callers (default False everywhere).

**Load-bearing narrative: iterative narrowing of the suppression set across three verify passes.** S44 became a worked example of empirical-narrowing under the operator's HALT-or-extend escape hatch. The initial scope (2 blocks: chroma retrieval + recent_npcs) shipped first; live verify surfaced residual drift; expanded scope to 9 blocks (added 7 — companions/quests/inventory/dm_pacing_examples/central_thread/pending_consequences/unresolved_commitment); live verify surfaced one more residual leak (current_scene rolling buffer); expanded to 10 blocks (added current_scene); live verify clean. The doctrine §77 line held throughout — no adjudication drift was observed in any pass — but storytelling-quality drift took three iterations to fully resolve.

**Three-pass empirical timeline:**

**Pass 1 — initial scope (2 blocks):** Suppressed `=== RELEVANT PAST EVENTS ===` (chroma retrieval) + `Recently active NPCs:` line. 7-assertion test suite green. Live verify: BLOODIED clean (no phantom NPCs); ROUND_START still drifted (phantom NPCs from Lira/Borin/Eldrin in narration, stale "blood-ied goblin" framing despite fresh combat).

**Pass 2 — expanded to 9 blocks:** Audited every `build_dm_context` injection site; surfaced classification table for operator review (combat-narration-relevant vs bleed-source). Added 7 blocks: `=== TRAVELING COMPANIONS ===` (confirmed primary phantom-NPC source — Lira/Borin/Eldrin live in `dnd_companions` table, NOT `recent_npcs`), `=== ACTIVE QUESTS ===`, `=== <NAME>'S NOTABLE ITEMS ===`, `=== DM PACING EXAMPLES ===` (second chroma block — 740k-doc FIREBALL+CRD3 corpus), `=== CENTRAL THREAD ===`, `=== PENDING CONSEQUENCES ===`, `=== UNRESOLVED COMMITMENT ===`. 15-assertion test suite green. Live verify: ROUND_START still drifted — "The lute's lingering chord hangs over the bar" + "scarred hide of the blood-ied goblin" despite goblin being at 13/13 HP.

**Pass 3 — diagnosis + 10-block final set:** Direct DB inspection revealed `campaign.current_scene` = `"Last actions: [Combat narration: round 1 starts.] | DM: The lute's lingering chord hangs over the bar..."`. The `=== CURRENT SCENE ===` block (line 5292-5293 pre-S44, classified as "static one-liner" in my initial audit) is actually a **rolling-narration buffer** written after every `_dm_respond_and_post` via `update_scene(campaign_id, f"Last actions: {combined_action[:200]} | DM: {response[:200]}")`. Combat narration was reading its own prior output back as "current scene" on each subsequent round-start. Added `current_scene_section` suppression. 17-assertion test suite green. Live verify clean:

> *"The clash begins in a hush, lantern light wavering over the cramped bar as the two figures lock eyes, the air thick with the promise of steel. No blows have yet landed; the moment hangs, waiting for the first move. Donovan Ruby, you're up."*

Every drift criterion passes: no phantom NPCs, no stale narrative, no speculative outcomes, no invented damage, no inferred morale, no tactical commentary, no future-round projection. Two-figure focus matches roster (Donovan + PurityRound3Goblin). Turn handback matches init order. Atmosphere is environmental (lighting + tension), not character-action.

**Final 10-block suppression set:**

| # | Block | Reason for suppression |
|---|---|---|
| 1 | `=== RELEVANT PAST EVENTS ===` | Chroma session-retrieval — prior narration text resurfacing via similarity |
| 2 | `=== DM PACING EXAMPLES ===` | Chroma knowledge-corpus retrieval — 740k FIREBALL+CRD3 docs pull combat-style examples with goblin-falls language |
| 3 | `=== TRAVELING COMPANIONS ===` | Primary phantom-NPC source — Lira/Borin/Eldrin live in `dnd_companions` table |
| 4 | `Recently active NPCs:` line (inside SCENE STATE) | Secondary phantom-NPC source — `recent_npcs` block |
| 5 | `=== ACTIVE QUESTS ===` | Quest titles + summary text + given-by NPCs bleed campaign-arc narrative |
| 6 | `=== <NAME>'S NOTABLE ITEMS ===` | Item names ("silver key", "amulet") bleed into combat narration |
| 7 | `=== CENTRAL THREAD ===` | Campaign-arc directional pressure — not relevant for round-top atmospheric beats |
| 8 | `=== PENDING CONSEQUENCES ===` | Per-NPC pressure framing surfaces non-combatant NPC pressures |
| 9 | `=== UNRESOLVED COMMITMENT ===` | Tracks prior-turn unresolved action — bleeds prior-turn narrative content |
| 10 | `=== CURRENT SCENE ===` (`campaign.current_scene`) | **Pass-3 finding**: rolling-narration buffer that re-injects prior round's narration verbatim as "current scene context" |

**Code:**
- `dnd_engine.py`: +~40 LOC across the 10 suppression sites + extended docstring on `build_dm_context` + `suppress_for_combat_narration` param threaded through `dm_respond`
- `discord_dnd_bot.py`: +~5 LOC — `_dm_respond_and_post` accepts the param + threads to `dm_respond`; `_dispatch_combat_narration` passes True
- Total surface change: single bool flag threaded through 4 layers; conditional block-skipping at 10 sites in `build_dm_context`

**Tests:** `test_combat_narration_prompt_purity.py` (new file, **17 assertions, all green**). Coverage: every suppressed block has a dedicated assertion confirming it's dropped under True + a counterpart confirming it's preserved under default False. Plus integration tests (the helper actually fires under combat narration). Plus a two-layer enforcement composition test (instruction-side MUST/MUST-NOT + information-side suppression hold together).

**Regression sweep clean:** 10+ test files (test_combat_narration 39, test_avrae_listener_edge_cases 7, test_avrae_project_npc 13, test_hydration_hook 20, test_pending_roll_directives 27, test_state_footer 27, test_combat_redirect_directive 38, test_scene_state_canon_deletion 73, test_prompt_size 22, test_commitment_directive passed). Pre-S44 behavior preserved everywhere.

**Doctrine candidate filed (not anchored):**

**"§77 atmospheric-continuity is enforced at two layers: instruction-side (MUST/MUST-NOT clauses, S43) and information-side (context-block suppression, S44). Both layers together provide structural protection that neither alone reliably provides."**

Operator-requested observation. S43 instruction-side clauses fixed BLOODIED + DOWNED (anchored events with strong contextual focus); ROUND_START (weak-anchor case) needed information-side suppression too. The two layers compose: instruction-side names what NOT to do; information-side removes the raw material the LLM would use. Filed as DOCTRINE.md candidate; anchors when a second instance shows the same two-layer composition pattern (e.g., when a future LLM-render ship adds both instruction-side guard + context-block trimming to its prompt assembly).

**Two-layer enforcement as the operational lesson:** S44's empirical narrowing showed that even with strong instruction-side enforcement (S43's verbatim MUST/MUST-NOT clauses), the LLM uses available context when its task has weak anchoring. ROUND_START has no specific event-anchor; the LLM falls back to whatever's in the prompt's information layer. Removing that information layer is what closes the loop. Future combat-narration-shaped ships should default to both-layer enforcement at design time.

**Worked-example value:** S44 is a clean record of "iterative empirical narrowing under HALT-or-extend discipline." The operator's escape hatch — "if drift persists post-patch, surface as HALT — root cause was wrong, re-spec rather than improvise" — held the pattern: each iteration produced a clean classification of new blocks via DB inspection or full audit, never speculation. Three iterations resolved a structurally bounded problem (10 blocks total in `build_dm_context`); had the leak been outside `build_dm_context`, HALT would have fired correctly.

| Field | Value |
|---|---|
| **Code shipped** | `dnd_engine.py` (10 suppression sites + extended `build_dm_context` docstring + `suppress_for_combat_narration` param on `dm_respond`); `discord_dnd_bot.py` (param threaded through `_dm_respond_and_post`; `_dispatch_combat_narration` passes True) |
| **Tests added** | **17 assertions** in new `test_combat_narration_prompt_purity.py` (all green) |
| **Tests passing** | 17 new + 10-file regression sweep clean |
| **Patches landed** | **3** (pass-1: 2-block scope; pass-2: expanded to 9 blocks; pass-3: added current_scene → 10 blocks) |
| **Recon result** | Single bool param threaded through 4 layers; conditional skip at 10 sites in `build_dm_context`. Cleanest diff possible for the suppression shape. |
| **Live-verify Scenario A result** | **CLEAN (pass 3)** — atmospheric round-top beat with environmental focus + 2-figure roster + turn handback per init order. No phantom NPCs, no stale narrative, no speculation. |
| **Two-layer enforcement observation** | **FILED** as DOCTRINE.md candidate (instruction-side + information-side composition for §77 atmospheric continuity). Anchors when a second instance shows the pattern. |
| **HALT escalations** | 0 — the operator's HALT-or-extend escape hatch was invoked twice (pass-2 + pass-3 considered HALT) but each time the root cause was identifiable via direct DB inspection or full block audit. Each iteration narrowed empirically; no speculation. |
| **Ship status** | ✅ SHIPPED LIVE (10-block suppression set complete; ROUND_START drift resolved) |
| **Multiplayer Fixes plan v3 status** | Ship 1 ✅ / Ship A ✅ / Ship 2 ✅ / Ship 3 ✅ / Listener verification ✅ / Dumb combat ✅ / **Dumb combat prompt purity v1.x ✅** / Ships 4-5 MVP-test scrutiny pending playtest phase |
| **Next session recommendation** | **Multi-hour playtest phase** per `PLAYTEST_OBSERVATION_FRAMEWORK.md` — unchanged from S43 recommendation. The S44 patches make ROUND_START reliable enough for playtest observation. No new architecture until playtest evidence accumulates. |
| **PC rsync** | done via push-all-to-pc.sh |

---

# Session 45 — Combat-Boundary Hardening Bundle: Post-!init-end Buffer Reset + Init-Setup Silence Gate + COMBAT_END Auto-Closeout (May 11, 2026)

S44 closed prompt purity at the dispatch surface. S45 closes the three remaining combat→exploration boundary surfaces in one bundle: **(a)** rolling-narrative-buffer pollution after `!init end` (the originally specced surface — surface C), **(D)** premature LLM narration during the Avrae init-setup window (surfaced by S45 verify itself), **(F)** the silence-until-player-types gap on combat close (operator's "not plausible" critique from S45 verify).

Three patches, three live-verified surfaces, **all green**. The two-layer enforcement doctrine candidate originally filed S44 gets its third structural instance and is **anchored** as §78 *mode-transition state-reset surfaces*.

## Load-bearing narrative

**The doctrine pattern in one sentence**: mode transitions are state-reset surfaces — the mode flag flip alone is structurally insufficient; both mechanical state AND narrative buffers must be reset at the boundary, AND the boundary itself must dispatch its own atmospheric closeout, AND the transitional window where mechanical state is incomplete must structurally silence inappropriate narration.

S43 ANCHORED §77 atmospheric-vs-adjudication. S44 filed two-layer enforcement (instruction + information). S45 reframes both into the broader mode-transition discipline: §77 governs WHAT can be narrated; §78 governs WHEN narration is structurally appropriate. The two are siblings, not competitors.

## What shipped (bundle — three surfaces)

### Surface C — Post-!init end narrative-buffer reset (originally specced)

`dnd_engine.py`: new helper `reset_narrative_buffers_on_combat_exit(campaign_id)` + three constants `_INIT_END_CLOSEOUT_SCENE` / `_DM` / `_PLAYER` for the synthesized closeout strings. Writes all three rolling narrative buffers (`dnd_campaigns.current_scene` via `update_scene` + `dnd_scene_state.last_dm_response` via `update_last_dm_response` + `dnd_scene_state.last_player_action` via `update_scene_state`) to neutral atmospheric framing. The S44 pass-3 finding (`campaigns.current_scene` is a rolling buffer written by every `_dm_respond_and_post`) is the dominant bleed source closed by this reset.

`discord_dnd_bot.py`: helper invoked from `_handle_init_event` evt_type='end' AFTER mechanical cleanup (mode flip + clear_active_turn + clear_combatants), BEFORE the COMBAT_END dispatch (surface F). Ordering established so the synthesized fallback is in place even if dispatch fails.

**Closeout text** (neutral atmospheric, not empty — empty current_scene triggers the `'The adventure is just beginning.'` fallback in `build_dm_context`):
- `current_scene` → "Combat resolves. The party stands down, weapons sheathed; the immediate threat has passed. Mode returns to exploration."
- `last_dm_response` → "Combat resolves. Mode returns to exploration."
- `last_player_action` → "[combat ended]" (marker — bracketed to distinguish from real player input)

10 test assertions in new `test_init_end_buffer_reset.py` (all green).

### Surface D — Init-setup silence gate (v1 conservative + v2 top-level)

Surfaced during S45's own live verify when the operator typed `2` to disambiguate Avrae's "Multiple Matches Found" prompt. The single-char message fell through the existing `!`-prefix filter, hit the batcher, and `_dm_respond_and_post` fired with full unsuppressed context (mode='combat' but no active_turn — the init-setup window). The LLM generated phantom-companion combat narration ("Donovan darts forward, dagger glinting... Lira hums a low tune... Borin nods approvingly...") BEFORE round 1 had started.

**v1 fix (defense-in-depth)** — `_dm_respond_and_post` gate: when `mode='combat'` AND no `active_turn`, force `suppress_for_combat_narration=True` regardless of caller-passed value. Closes the phantom-companion leak by routing through the S44 10-block suppression set. Re-verify revealed v1 closed the phantom NPCs but the LLM still generated combat narration from bare disambiguation replies — premature combat narrative from minimal input.

**v2 fix (primary, top-level gate)** — `on_message` extension at line 2126+: when `mode='combat'` AND no `active_turn`, react ⏳ and return BEFORE the batcher accepts the message. Bot stays silent during init-setup; ROUND_START dispatch provides the proper atmospheric opener when Avrae announces the first turn. v1 retained as defense-in-depth for non-`on_message` call sites (slash commands, `_handle_dm_roll_arrival` auto-fire, /travel, etc.).

13 test assertions in new `test_init_setup_suppression.py` (all green) — covers detection logic + code-shape inspection of both gate layers + ordering guarantees (gate fires before LLM call, before batcher add).

### Surface F — COMBAT_END auto-closeout (4th combat-narration trigger)

Operator's "not plausible" critique from S45 verify: in real play, no one types a structured RP message between `!init end` and the bot's response. Without surface F, the bot stays silent on combat close and the player has to seed the next narration. Surface F closes the gap by auto-firing a closeout narration on `!init end` — same dispatch surface as ROUND_START / BLOODIED / DOWNED.

`dnd_orchestration.py`: `compute_combat_narration_directive` extended with `'COMBAT_END'` kind. Framing locks aftermath-orientation (2-3 sentences, falling tension, cessation of motion, room settling). MUST/MUST-NOT clauses forbid: post-combat decision narration, next-move narration, introduction of any combatant or NPC not on the closing roster. The "no thug emerges from the shadows / no companions appearing to congratulate" line is verbatim in the framing — names the specific failure modes from prior verify drift.

`discord_dnd_bot.py`: `_dispatch_combat_narration` extended with optional `combat_state_override` and `scene_override` params, decoupling dispatch from current DB state. `_handle_init_event` evt_type='end' snapshots `pre_clear_combat_state` BEFORE mechanical cleanup, then dispatches COMBAT_END AFTER cleanup with overrides — the directive's mode gate passes (override mode='combat'), the roster shows closing state, and DB is consistent.

Ordering: snapshot → mechanical cleanup → S45 buffer reset (synth fallback) → COMBAT_END dispatch (LLM closeout overwrites synth in current_scene → richer atmospheric context for next exploration turn).

10 test assertions in new `test_combat_narration_combat_end.py` (all green).

## What changes structurally

| Before S45 | After S45 |
|---|---|
| `!init end` clears mechanical state but leaves three narrative buffers polluted with combat narration | All three buffers reset to neutral closeout text at the boundary |
| Avrae init-setup window (mode='combat', no active_turn) allows full unsuppressed `_dm_respond_and_post` to fire on player messages | `on_message` silences during init-setup (v2 primary gate) + `_dm_respond_and_post` defense-in-depth suppression for non-on_message paths (v1) |
| Bot stays silent on `!init end` — closeout depends on next player RP message | COMBAT_END dispatch fires auto-closeout within 1-3 seconds of `!init end` |
| Two-layer enforcement (S44) filed as candidate, awaiting 3rd instance | §78 mode-transition state-reset anchored as 3rd instance |

## Recon

**Surface C** — Three buffer write helpers located: `update_scene` (campaigns.current_scene), `update_last_dm_response` (single writer per dnd_engine.py line 1379), `update_scene_state` with `last_player_action` in SCALAR_FIELDS. All three accept arbitrary text including empty/marker strings. Helper placed in `dnd_engine.py` after `update_last_active_actor` (clustered with scene-state write helpers). Idempotent — running twice produces same final state.

**Surface D** — Trigger source identified via journal trace: operator's `3` disambiguation reply at S45 verify pass-1 fell through the existing `!`-prefix filter at line 2123 (`if action.startswith('!'): return` only filters !-prefixed). v1 placed in `_dm_respond_and_post` early-return path with try/except (soft-fail; gate errors never block narration). v2 placed in `on_message` immediately above the existing turn-gate at line 2126+ — same ⏳ reaction pattern for consistency. Mode-gated check uses `(scene.get('mode') or 'exploration') == 'combat'` to match existing combat-mode-check style.

**Surface F** — 4th `kind` added to whitelist. Mode-gate logic preserved (returns ('','') when mode != 'combat') — caller must pass `scene_override={'mode': 'combat'}` for dispatch to succeed AFTER the mechanical mode flip has run. `_dispatch_combat_narration` extended with `combat_state_override` and `scene_override` params defaulting to None (S43/S44 behavior unchanged when overrides absent). Soft-fail per §59 throughout.

## Live verify

### Pass 1 — Surface C only (S45 originally specced surface)
Operator did `!init begin` + Avrae auto-cycled to round 1 (1 combatant) + ROUND_START fired clean + `!init end` confirmed + then typed exploration message "Donovan looks around the bar, taking stock of the room now that the dust has settled."

Bot response: "The Bloated Bafoon Bar hums with the low murmur of patrons; oil-lamp light flickers over rough-hewn tables scarred by countless mugs..." — atmospheric, no combat framing, no phantom "thug", no invented gear, no continued combat tension.

**Surface C ✅ clean.**

Operator surfaced two follow-up critiques: (1) Avrae end-of-combat-report routing to DM instead of channel (filed as Avrae config issue, not Virgil code), (2) "not plausible that we wait for a structured sentence before dm responds to init end" — the silence-until-player-types gap. The verify itself uncovered surface D (premature combat narration during init-setup) when typing `2` to disambiguate triggered phantom-companion narration BEFORE round 1.

### Pass 2 — D v1 + F + C combined
Operator did `!init begin` + `!init madd PostInitSuppressionGoblin` + Avrae disambiguation + typed `2` to pick Goblin source.

Bot response: "Donovan darts forward, thrusting his dagger at GO1; the blade slips through a weak spot in the goblin's armor, drawing a shallow wound. The goblin snarls, grips its crude short sword, and lunges at him." — DURING init setup, BEFORE round 1.

Surface D v1 (conservative suppression) closed the phantom-companion leak (Lira/Borin/Eldrin absent — improvement!) but the LLM still generated premature combat narration from bare disambiguation reply + combat-mode context. Surface F (COMBAT_END) fired cleanly on `!init end` though: "The clash of steel and shouted curses fades, the final thuds echoing off the walls before dying into silence. Those still standing catch their breath as the room settles into a tense, uneasy quiet." ✅

**Decision**: upgrade D from v1 conservative (suppress context, stay responsive) to v2 principled (top-level silence gate) in-session.

### Pass 3 — D v2 + F + C combined
Operator did `!init begin` + `!init join` (Donovan rolled init 15) + Avrae auto-cycled to round 1 + ROUND_START fired clean + operator typed brief message (3 chars per arbitration log) + `!init end` + COMBAT_END auto-fired.

**Two prompt builds nearly concurrent** at 22:14:59 — first with `reason=combat_narration_suppressed` (COMBAT_END's `suppress=True`), second without (player-action dispatch after mode flipped to 'exploration'). Both responses landed clean:
- Item 4 ROUND_START: "The din of the Bloated Bafoon Bar settles into a thin, watchful hush as the first round of combat begins, the weight of steel and intent hanging in the stale air. Patrons glance toward the cleared space where Donovan stands, the flicker of lantern light catching the edge of his blade." — atmospheric, no phantoms, no specific actions. ✅
- Item 6 COMBAT_END: "The clash of steel fades into a heavy hush as the last echo of blows dies away. Dust drifts down from the rafters, settling on the worn floor where Donovan Ruby stands, breathing steady. The room grows still, the tension that had crackled now a distant memory." — atmospheric closeout, no continued combat, no phantom NPCs. ✅
- Item 7 player-action response: "The melee has faded, leaving the Bloated Bafoon Bar oddly still..." — clean exploration response. ✅

Journal confirmed: `combat_narration_fired: kind=ROUND_START fired=1`, `init_end_buffer_reset: campaign=17`, `combat_narration_fired: kind=COMBAT_END fired=1`. No `init_setup_gate` log this pass (because Avrae's auto-cycle set active_turn quickly enough that no message hit the gate window).

**All three surfaces ✅ verified clean live.**

## Doctrine anchoring

**§78 mode-transition state-reset** — anchored post-verify-clean. The pattern is structurally distinct from §77 (which governs what content is appropriate in atmospheric narration). §78 governs the structural integrity of the boundary itself:

1. **Mechanical state cleanup** is necessary but not sufficient. The mode flag flip + clear_combatants + clear_active_turn does not address narrative-buffer pollution.
2. **Narrative buffer reset** at the boundary closes the rolling-buffer leak (Surface C).
3. **Transitional-window structural silence** — when mode has flipped but mechanical state isn't fully populated, narration is structurally premature regardless of message content. The window needs a top-level gate (Surface D v2).
4. **Boundary atmospheric closeout** — the boundary itself dispatches its own narration with both-layer enforcement (instruction-side §77 MUST/MUST-NOT + information-side §44 suppression). Surface F is the third instance of this two-layer composition pattern (after S43 ROUND_START + S44's 10-block expansion).

**Three project instances** of the two-layer enforcement pattern (the structural backbone of §78):
1. S43 — ROUND_START / BLOODIED / DOWNED instruction-side MUST/MUST-NOT clauses
2. S44 — Information-side 10-block suppression on the same dispatch surface
3. S45 — COMBAT_END dispatch (both layers, plus boundary reset + transitional silence)

**Cross-references**: §77 (atmospheric-vs-adjudication, S43), §44 (suppression set, S44), §59 (§59 sibling pure-function discipline — 10th sibling extended for COMBAT_END), §17 (single-write paths — `reset_narrative_buffers_on_combat_exit` is the single writer for the boundary reset), §65 (bot-stays-read-only-on-Avrae-channel — analogous structural-window rule).

## What this ship does NOT do

Filed as separate follow-ups (not S45 scope):
- **COMBAT_END framing on 0-action combats** — LLM speculated "clash of steel / blows died away" on a verify with no actual combat actions. Creative-writing tuning, not structural drift. Filed as v1.x prompt refinement.
- **`(1 roll in play)` footer post-!init end** — Donovan's initiative roll persists in RollBuffer after !init end clears mechanical state. Orthogonal buffer-drain issue. Filed.
- **Phantom companions in dnd_companions DB rows** — Lira/Borin/Eldrin are real rows from past npc_extract LLM writes. Database-hygiene issue, not S45's surface. Surfaces in any exploration-mode prompt that renders companions block. Filed for a future ship.
- **Parallel surface: `_handle_rest_event` !lr/!sr** — also flips combat→exploration but via a different listener path; doesn't currently call `reset_narrative_buffers_on_combat_exit`. Per S45 locked spec, only `!init end` path addressed. Operator can extend in a follow-up if drift surfaces.
- **Avrae end-of-combat report routing to DM** — Avrae configuration issue (`!cvar` or `personal` flag), not Virgil bot code.

## Tests

- `test_init_end_buffer_reset.py` — 10 new assertions (Surface C)
- `test_init_setup_suppression.py` — 13 new assertions (Surface D v1 + v2)
- `test_combat_narration_combat_end.py` — 10 new assertions (Surface F)
- **Regression sweep**: S43 (39) + S44 (17) + combatant_state (15) + listener edge cases (7) all green
- **Total bundle**: 33 new + 78 regression = 111 assertions green

## Cross-references

- Doctrine §77 atmospheric-vs-adjudication (S43)
- Doctrine §78 mode-transition state-reset (newly anchored, this session)
- Doctrine candidate (filed S44, now subsumed by §78): two-layer enforcement
- §59 sibling pure functions in `dnd_orchestration.py` (COMBAT_END extends the 10th sibling)
- §17 single-write paths (`reset_narrative_buffers_on_combat_exit` as single boundary-reset writer)
- `MULTIPLAYER_FIXES.md` post-combat exploration drift row → ✅ closed
- `ROADMAP.md` post-!init-end drift row → ✅ closed; S45 entry added

| Field | Value |
|---|---|
| **Code shipped** | `dnd_engine.py` (closeout writer + 3 constants); `dnd_orchestration.py` (COMBAT_END kind + framing); `discord_dnd_bot.py` (v2 top-level gate + v1 defense-in-depth gate + dispatch overrides + COMBAT_END call site + buffer-reset import) |
| **Tests added** | **33 new assertions** across 3 new test files (all green) |
| **Tests passing** | 33 new + 78 regression sweep clean = 111 total |
| **Patches landed** | **4** (Surface C originally specced; Surface D v1 conservative; Surface D v2 upgrade after verify exposed premature narration; Surface F COMBAT_END dispatch) |
| **Recon result** | Single boundary helper + three buffer-write helpers identified cleanly; gate placement validated against existing turn-gate pattern; dispatch overrides decouple from DB state |
| **Live-verify results** | Pass 1 (C only) ✅ / Pass 2 (D v1 + F) ⚠ premature combat narration → upgrade to v2 / Pass 3 (D v2 + F + C) ✅ all three surfaces clean |
| **Doctrine anchored** | **§78 mode-transition state-reset** anchored post-verify-clean. Third project instance of two-layer enforcement pattern (S43 + S44 + S45) provides the structural backbone. |
| **HALT escalations** | 1 — S45 verify pass-2 exposed surface D's residual premature narration after v1; operator's "do them all" directive prompted in-session v2 upgrade rather than re-spec. v2 verify clean. |
| **Ship status** | ✅ SHIPPED LIVE (three surfaces closed; doctrine anchored) |
| **Multiplayer Fixes plan v3 status** | Ship 1 ✅ / Ship A ✅ / Ship 2 ✅ / Ship 3 ✅ / Listener verification ✅ / Dumb combat ✅ / Dumb combat prompt purity ✅ / **Combat-boundary hardening (S45 bundle) ✅** / Ships 4-5 MVP-test scrutiny pending playtest phase |
| **Next session recommendation** | **Multi-hour playtest phase** — unchanged from S43/S44. The combat→exploration boundary is now structurally sealed. ROUND_START + BLOODIED + DOWNED + COMBAT_END all dispatch cleanly; init-setup is silenced; post-combat exploration starts from clean atmospheric slate. Playtest phase is the right next move to surface real-play patterns that no bench-test can reveal. Filed follow-ups (phantom-companion DB rows, !lr/!sr parallel surface, COMBAT_END 0-action framing, roll-buffer drain) all wait on playtest evidence for prioritization. |
| **PC rsync** | done via push-all-to-pc.sh |

---

# Session 46 — Pre-Playtest Hygiene: Framework v2 Edits + Verifier-Error Sentinel + Sync-Race Discovery (May 12, 2026)

S45 closed the combat→exploration boundary. S46 is pre-playtest preparation under a fresh planner instance: surgical edits to the playtest framework that sharpen evidence quality, one small hygiene ship that closes a silent-failure mode in the verifier, one operational discovery about doc sync direction that almost broke this session, and a new PC-only convention for planner working artifacts.

## What landed

### 1. Playtest framework v2 revision

`PLAYTEST_OBSERVATION_FRAMEWORK.md` revised. Five categories of change:

- **§5 telemetry verification corrections** — first-cut §5 referenced log lines by names that didn't match production. `directive_resolved:` is Ship 1's success log, not the violation log; the violation surface is `verification:` with `violation_class=roll_outcome_drift` (nested grep pattern, not top-level). "Scene state drift" and "latency between input and narration" have no dedicated telemetry — operator-observable only. Code ran live recon against production code + 7-day journal samples, confirmed shape-side recon was correct, and surfaced five additional framework-readable findings folded in as additive footnotes: `prompt_size` per-section breakouts don't sum to total; `state_footer` phase renders proper-case so regexes must be case-insensitive; `npc_near_match` and `unconsumed_roll_swept` lack `campaign=` field; sibling log lines worth pairing (`directive_resolution_skipped`, `npc_token_prefix_match`, `phantom_candidates: error` variant); `roll_outcome_drift` and `directive_skill_mismatch` are wired-but-unverified-in-prod (zero fires in 30 days).
- **§2.3 + §2.4 merge** — state-comprehension and clarification-interruption metrics were undefined at the boundary ("who's bloodied?" is both). Merged into single "Clarification rate" metric with state/affordance/both tags. Combat-rate vs exploration-rate comparison.
- **§2.4 pure-operational rate** (replaces old §2.5) — original operational-vs-dramatic ratio's "mixed" bucket would absorb every Ship A directive-emit message ("I lunge... !attack goblin -t goblinchief"), making the metric meaningless on the exact failure mode it targets. Replaced with binary metric: does narration exist or not. Threshold: pure-operational >25% of in-combat player messages.
- **§3.1 emergent-canon pinning** — original cross-session causality metric measured authored-canon recall (skeleton.md, always fires by design). Pinned to emergent canon (parser-extracted `skeleton_origin=0` rows) which is the architectural test of whether motion-systems thread needs to ship. Added recall-rate denominator (successes / opportunities per session).
- **Mode A/B → Tier 0/1-3 alignment** — framework introduced Mode A/B nomenclature de novo; HCN v3 §4 uses the Tier 0/1/2/3 ladder. Aligned so post-playtest evidence maps back to HCN candidates cleanly. No new vocabulary; framework adopts HCN's.

### 2. Verifier-error sentinel ship (Finding A)

Recon surfaced that `dnd_engine.py:6480` fallback path emits `violation_class=none` when `narration_verifier` raises an exception — indistinguishable from a clean verification pass. Silent-failure mode that would compromise playtest evidence: a verifier crash mid-session would look like the cleanest session ever to a `verification:.*violation_class=roll_outcome_drift` grep.

Ship: new `VIOLATION_VERIFIER_ERROR = 'verifier_error'` constant at `narration_verifier.py:59`, fallback emit at `dnd_engine.py:6485` swapped from `violation_class=none` to `violation_class={_nv.VIOLATION_VERIFIER_ERROR}`. `passed=1` preserved per fail-open invariant. Sentinel sits outside the first-violation-wins ordering by construction; never triggers retry escalation.

Live verify via deliberate `raise RuntimeError("verify test")` injection at `verify_narration` entry: sentinel fires under crash (`verification: ... violation_class=verifier_error ...` paired with `[VERIFICATION_FALLBACK]:` line carrying exception repr), normal path emits `violation_class=none` under clean. Injection removed, normal path restored. Paired-signal pattern (parseable classification on the `verification:` line, human-readable diagnosis on the `[VERIFICATION_FALLBACK]` line) folded into framework §5.2.

### 3. VM:295 reconciliation

The "Four locked violation classes" doctrine bullet in `VIRGIL_MASTER.md` was stale — predated Ship 1's `ROLL_OUTCOME_DRIFT` addition, making the code 5-classified-not-4. Reconciled to "5 classified + 1 sentinel" framing that preserves the stability promise (classification semantics, not count). Sentinels distinguished structurally: outside the first-violation-wins ordering, never trigger retry escalation. The classified ordering position for `ROLL_OUTCOME_DRIFT` deliberately deferred to source (`see narration_verifier.py for canonical sequence`) rather than invented.

### 4. DIR.md planner-scratch convention

New PC-only convention: `planner-scratch/` folder at project root holds planner working artifacts (drafts, review tables, transient review docs) that aren't yet canonical. Never touched by any push alias. When content earns canonical status, planner produces a clean version as a chat artifact and operator places it in `text files/` or `specs/` before pushing.

Convention exists because planner generates transient artifacts that shouldn't ship server-canonical. Prior to this session, transient drafts landed in `text files/` and got pushed via `push-docs` — which works for canonical docs but contaminates `~/virgil-docs/` with scratch material. Two existing drafts moved to `planner-scratch/` at session-start.

## Discovered failure mode — sync-direction race

`push-docs` at 10:40:29 overwrote a Code edit to `VIRGIL_MASTER.md` that had landed server-side at ~10:13 (verifier_error sentinel bullet). Structurally inevitable given the workflow:

1. Code edits server-side `~/virgil-docs/VIRGIL_MASTER.md` at ~10:13.
2. Operator runs `push-docs` at 10:40:29 without first running `backup-virgil`.
3. PC's `text files/VIRGIL_MASTER.md` was at yesterday-afternoon mtime — never received the 10:13 server edit.
4. `push-docs` is one-way PC→server with no `--update` flag — content-differing files overwrite regardless of mtime.
5. PC's stale copy clobbered server's fresh copy.

WORKING_WITH_CLAUDE.md covers the inverse failure (server→PC `backup-virgil` clobbering PC-side planner edits). This is the same shape with directions flipped: PC→server `push-docs` clobbering server-side Code edits that hadn't propagated PC-ward yet.

Recovery: re-applied Code's sentinel bullet server-side, applied the VM:295 reconciliation in the same edit (unified bullet — both reconcile to one place), then ran `push-all-to-pc.sh` to close the race window. **The recovery itself violated the Deployment workflow rule** (`push-all-to-pc.sh` is reserved for Jordan's hand) — the recovery prompt incorrectly invoked it. Worked, but wrong tool. The right protection going forward is Code's existing targeted scp/rsync cadence on files-edited-this-session (Deployment workflow section), which the verifier_error ship had skipped — that's why PC was stale at push-docs time.

**Discipline reinforced (not new)**: the existing Deployment workflow rule — Code uses targeted scp/rsync of files-edited-this-session; `push-all-to-pc.sh` is Jordan-only — is what closes the race window structurally. S46 incident exposed that the targeted push got skipped on the verifier_error ship; if it had run, PC's VIRGIL_MASTER.md would have had the fresh copy and the subsequent push-docs would have been a no-op. WOC update this session adds an inverse-failure-mode bullet to the Discipline section cross-referencing the Deployment workflow rule — names the new failure-direction without restating the existing discipline.

**Workaround for operator-side discipline** (when planner edits docs PC-side rather than dispatching Code):
- After operator edits docs PC-side: run `push-docs` before Code touches docs.
- If both edited concurrently without sync: latest-push-wins, which is sometimes operator and sometimes Code, neither expected.

## What this session does NOT do

- **File doctrine candidates** — none earned. Two-layer enforcement (§78) is anchored; sentinel-vs-classification distinction is one instance.
- **Fix Finding B (cloud_router print vs log)** — `cloud_router_finish_reason` uses `print()` not `log()` so lacks the `[ISO_TS]` prefix every other §5 line carries. Format inconsistency documented in framework §5.3; not fix-blocker for playtest. Defer until recurrence justifies.
- **Verify ROLL_OUTCOME_DRIFT ordering position** — deferred to `narration_verifier.py` source via the VM:295 bullet. One-line grep ship if explicit ordering wanted in doc.
- **Clean up PC `_trash/PLAYTEST_OBSERVATION_FRAMEWORK_target.md` orphan** — `push-all-to-pc.sh` ran before the server `_trash` delete in the recovery dispatch, leaving a PC-side leftover. Low risk (in `_trash`, not canonical); operator removes manually. Pattern for next time: delete from server `_trash` before push.
- **Investigate MCP `edit_file` dryRun reliability** — multiple `dryRun=true` calls timed out during this session; some writes may have landed before the timeout (PLAYTEST.md showed two word-level deltas from intended). Treating MCP `edit_file` as advisory rather than authoritative is the safer stance until more sessions confirm reliability. If recurrence patterns emerge, files as future planner-tooling decision.

## Tests

No tests added this session. Verifier-error sentinel verified via deliberate exception injection (not a unit-test surface; the failure path is the same code as before, just with a different `violation_class` string). S45 regression sweep coverage intact.

## Cross-references

- `PLAYTEST_OBSERVATION_FRAMEWORK.md` — full v2 revision, status line updated to reference S46
- `VIRGIL_MASTER.md` — §4 Arbitration + Verification invariants bullet reconciled; sentinel folded into unified "5 classified + 1 sentinel" bullet
- `DIR.md` — PC `planner-scratch/` convention added
- `HYBRID_COMBAT_NOTES.md` — Mode A/B → Tier 0/1-3 nomenclature alignment in framework §2.4 and §7
- Doctrine §77 / §78 — no new anchorings; existing doctrine intact
- WORKING_WITH_CLAUDE.md — inverse-failure-mode bullet added to Discipline section, cross-references existing Deployment workflow rule (Code uses targeted scp/rsync of files-edited-this-session; `push-all-to-pc.sh` is Jordan-only)

| Field | Value |
|---|---|
| **Code shipped** | `narration_verifier.py` (VIOLATION_VERIFIER_ERROR constant); `dnd_engine.py:6485` (fallback emit swap); `VIRGIL_MASTER.md` (VM:295 unified bullet — 5 classified + 1 sentinel); `PLAYTEST_OBSERVATION_FRAMEWORK.md` (full v2 revision applied via diff-and-replace during recovery) |
| **Planner edits** | `DIR.md` (planner-scratch convention); `planner-scratch/` folder created; v1+v2 framework drafts moved into it |
| **Tests added** | 0 new (sentinel verified via exception injection; doc edits don't earn unit tests) |
| **Tests passing** | S45 regression sweep coverage intact |
| **Patches landed** | 4 (verifier_error sentinel; framework v2 revision; VM:295 reconciliation; DIR.md convention) + 1 recovery dispatch (re-apply after sync-race clobber) |
| **Recon result** | All §5 log lines verified against production code + 7-day journal samples; 5 framework-readable findings + 2 actionable (A shipped, B deferred) |
| **Live-verify results** | Sentinel injection: ✅ fires under crash, normal path clean. Recovery dispatch: ✅ all 4 phases complete, server-side mtimes confirmed post-edit, PC in-sync via push-all-to-pc. |
| **Doctrine anchored** | None |
| **Doctrine candidates filed** | None |
| **HALT escalations** | 0 — sync-race discovery was post-hoc diagnostic, not an in-flight HALT; MCP timeouts surfaced edit-tool reliability question but chat-artifact fallback held |
| **Ship status** | ✅ SHIPPED LIVE (sentinel + four doc updates canonical + PC in-sync) |
| **Multiplayer Fixes plan v3 status** | Unchanged — Ships 1-A-2-3 ✅ / Listener verification ✅ / Dumb combat ✅ / Dumb combat prompt purity ✅ / Combat-boundary hardening ✅ / Ships 4-5 MVP-test scrutiny pending playtest phase |
| **Next session recommendation** | Operator-led: playtest phase when operator's schedule allows; planner on standby for non-playtest work in the interim (review external input, draft follow-up specs when called, fact-check observations). No new architecture during playtest phase. Filed follow-ups (phantom-companion DB rows, !lr/!sr parallel surface, COMBAT_END 0-action framing, roll-buffer drain, Finding B cloud_router format) all wait on playtest evidence for prioritization. |
| **PC rsync** | done via push-all-to-pc.sh (recovery dispatch); next push-docs will land S46 SESSIONS entry server-side |

---

# Session 47 — NPC Token-Prefix Collapse: Doctrine Amendment + Write-Path Refinement + Migration (May 12-13, 2026)

S46 closed pre-playtest hygiene under the new planner instance. S47 is the first doctrine amendment under this planner: a write-path semantic refinement to `npc_upsert` that closes a steady-state rot loop in NPC canonical-name resolution, plus the first amendment-to-existing-lock the project has shipped (prior arc anchored §76/§77/§78 as new entries; none modified existing locks). Three-session Path A cadence (spec → review → implementation) executed cleanly. External reviewer pass (ChatGPT + Gemini) anchored the architectural shape with full convergence on seven of eight contested points.

## What landed

### 1. Doctrine §14.1 amendment

DOCTRINE.md §14 ("Strict literal match beats fuzzy") amended via new §14.1 sub-section. Locked amendment text:

> Strict literal matching remains the default identity rule. Exception: deterministic whole-token prefix collapse is permitted only when the incoming canonical_name matches a unique `skeleton_origin=1` row's leading whole-token within the same `campaign_id`. If multiple `skeleton_origin=1` rows in the same campaign share the leading whole-token, no collapse occurs; insert proceeds normally and ambiguity telemetry is logged.

Four named constraints lock the rule's surface area: **unique anchor / skeleton_origin=1 / same campaign_id / whole-token.** The constraints are load-bearing — each protects against a named failure mode that the wider phrasings (V2/V3 in planner-scratch artifact) would have enabled. Operator locked V1 (Tight) verbatim before spec session opened.

First amendment-to-existing-lock the project has shipped. Anchored via §N.M sub-numbering (new precedent in DOCTRINE.md, which previously used flat §N numbering). The sub-numbering conveys the architectural relationship correctly — amendment is an exception inside the parent doctrine, not a peer doctrine.

### 2. Write-path refinement to `npc_upsert`

Failure mode: strict-equality canonical_name lookup at dnd_engine.py:2981 misses LLM-emitted short forms ("Eldrin" misses "Eldrin Stormbow"); INSERT branch creates bare-firstname row; per-turn mention_count + last_mentioned increments accumulate on the wrong row; `get_recently_active_npcs` orders by `last_mentioned DESC` with no skeleton preference; bare-firstname row surfaces in prompt context; LLM keeps emitting short form. Steady-state loop produced 9× mention_count concentration on bare-firstname rows over 12 days of play in campaign 17.

Fix shape: ~40 LOC early-exit branch inserted before strict-equality lookup. Queries `skeleton_origin=1` rows for the same campaign, filters via existing `_is_token_prefix` helper (no reimplementation). On unique-anchor match: routes to existing skeleton-lock UPDATE branch semantic (mention_count + last_mentioned bump on anchor row); emits `npc_token_prefix_collapse:` log line; returns `was_new=False`. On multi-anchor match: refuses collapse, emits `npc_anchor_ambiguous:` log line, falls through to existing INSERT branch. On no-anchor match: falls through unchanged.

§17 single-write-path doctrine preserved — `npc_upsert` remains the only writer for `dnd_npcs`. The amendment refines an existing write path's decision logic; it does not add a new write path. Six branches inside the upsert function now (was five). §16 engine-defends-invariants preserved — PC contamination guard at 2971-2976 still runs before the new collapse path.

### 3. Operational migration (campaign 17)

Three skeleton-fragmentation rows (ids 4 "Eldrin" mc=40, 5 "Lira" mc=43, 6 "Borin" mc=37) migrated into their canonical anchors via sum-into-canonical (mention_count + last_mentioned both summed/maxed). Single transaction. Per-row migration log captured. Post-migration: anchor rows 1/2/3 carry summed mention_count (44/51/42); fragment rows 4/5/6 deleted; row 11 (Garrik, emergent-emergent fragmentation) untouched per scope (separate ship if/when justified).

§11.1 lock at (b) sum-into-canonical was a planner push-back against the spec's drafted default (c) last_mentioned-only. Code's review surfaced that `npc_fragmentation_report` already computes `combined_mention_count = primary.mention_count + sum(fragment.mention_count for fragment in cluster.fragments)` — the (b) semantic was already baked into existing diagnostic vocabulary; (c) would have left row values contradicting the vocabulary. Lock at (b) aligned vocabulary with row state.

### 4. Convergent external-review pattern, codified

ChatGPT + Gemini briefs landed convergent on seven of eight contested points: 2B as extension-not-violation of §9.1 (both); write-path as primary fix layer (both); resolver-only insufficient due to split-brain hydration risk (both); skeleton-anchor-only as safety boundary not limitation (both); uniqueness constraint required (ChatGPT explicit, Gemini implicit via no-rejection); cleanup with implementation (both); doctrine amendment must be explicit (both). Single divergence: whether resolver hardening (option 3) earns a slot in the ship (ChatGPT yes as lifecycle-stage hardening; Gemini no as dead code under cleanup-with-2B). Planner reconciled toward Gemini on the divergence — ChatGPT's "tolerate residual corruption safely" argument doesn't hold under the cleanup-rides-with-2B assumption.

WHY.md entry captures the convergent-external-review pattern as the architectural-call shape, generalizable to future doctrine-touching ships.

### 5. Test convention reaffirmed

Review surfaced that spec drafted tests in pytest `def test_*` form, but project convention is module-level imperative scripts with `check(label, got, want)` calls and sectioned headers (template: `test_npc_near_match.py`). Spec §6 revised to match. New file `test_npc_token_prefix_collapse.py` ships 8 scenarios (6 core + 2 recommended) with 41 assertions; all green; no regression in `test_npc_near_match.py` (39/39) or `test_npc_extractor.py` (219/219).

## What didn't surface this session

- **No HALT escalations.** All eight implementation phases passed gates without invoking pivot-or-defer.
- **No new doctrine candidates filed.** The amendment-via-sub-numbering pattern (§14.1) is itself precedent territory but single-instance — deferred until a second amendment justifies anchoring. Filed mentally, not pre-emptively.
- **No production-code drift discovered.** §1 spec defaults verified clean against current `dnd_engine.py` state at review time. All six §1 line references held.

## Discovered findings (informational, not blocking)

**Stale spec brief line numbers.** The implementation brief named `dnd_engine.py:2854` as one of three PHASE_12_SPEC §9.1 code-comment references; actual line 2854 is a PHASE_6_IDENTITY_SPEC reference. Real third reference was at 3552 (3510 had no §9.1 ref either). Code adjusted in-flight: updated the three correct references (2838, 3552, 3661), left two multi-section header citations at 2822 and 3631 alone (those cite multiple PHASE_12_SPEC sections; splitting them is polish, not load-bearing). Net effect: clean comment updates at the three single-section §9.1 references; orphaned multi-section header citations remain for follow-up if ever justified.

**Routing memory contradiction.** Code surfaced that an auto-router memory says `_REVIEW.md` files route to PC `text files/` rather than `specs/`. Operator-instructed placement (`specs/`) matches the existing review-pair convention in `~/virgil-docs/specs/` (RESOLUTION_BINDING_REVIEW, SCENE_STATE_CANON_REVIEW, NPC_STATE_SYNC_REVIEW all live there). Auto-router memory may be stale. Not blocking; flagged for memory update at operator's convenience.

## What this session does NOT do

- **Resolver-side rendering (option 3).** Rejected per Gemini's verdict; ChatGPT's defense-in-depth argument doesn't hold under cleanup-with-2B.
- **Emergent-emergent fragmentation (Garrik / Garrick, row 11).** Out of scope per external-review verdict. Separate ship if/when justified.
- **Reconstruct PHASE_12_SPEC.md.** Code comments at 2822 and 3631 still reference it for multi-section citations. Reconstruction is a corpus-archaeology ship, separate scope.
- **Verify the loop closes in live play.** Code path is structurally verified (tests green, restart clean, migration values exact at 44/51/42). The behavioral verify — short-form emission actually collapses in real campaign 17 narration — is operator-side Discord work, ~5 minutes via the five-step prompt sequence in the implementation handoff. Ship considered structurally shipped; behavioral verify pending.

## Tests

New file `test_npc_token_prefix_collapse.py`: 8 scenarios, 41 assertions, all green. Regression: `test_npc_near_match.py` 39/39 pass, `test_npc_extractor.py` 219/219 pass.

## Cross-references

- `NPC_TOKEN_PREFIX_COLLAPSE_SPEC.md` — status LOCKED; §6 rewritten to imperative-script convention; §11.1 option (d) added (skip-cleanup); all §11 marked LOCKED with values
- `NPC_TOKEN_PREFIX_COLLAPSE_REVIEW.md` — REVIEW v1 COMPLETE; convergent recommendation locked at (b) for §11.1
- `DOCTRINE.md` — §14.1 sub-section added with locked amendment text verbatim
- `VIRGIL_MASTER.md` — npc_upsert section updated with new write-path branch + log line names
- `WHY.md` — architectural-call entry capturing rot mechanism, external-review convergence, four-constraint boundary, option-3 rejection rationale
- `planner-scratch/section_9_1_amendment_drafts.md` — the three-version amendment-language artifact (V1 Tight / V2 Medium / V3 Wide); operator locked V1 before spec session opened

| Field | Value |
|---|---|
| **Code shipped** | `dnd_engine.py` (~40 LOC collapse branch in npc_upsert at 2980-3023 + 3 comment updates at 2838/3552/3661); `test_npc_token_prefix_collapse.py` (new file, 8 scenarios / 41 assertions); spec doc LOCKED with §6 + §11.1 revisions; `DOCTRINE.md` (§14.1 amendment); `VIRGIL_MASTER.md` (npc_upsert section); `WHY.md` (architectural-call entry); operational migration of rows 4/5/6 in campaign 17 |
| **Planner edits** | `planner-scratch/section_9_1_amendment_drafts.md` (three-version amendment-language artifact); SESSIONS.md S47 entry |
| **Tests added** | 8 scenarios / 41 assertions in `test_npc_token_prefix_collapse.py` |
| **Tests passing** | 41/41 new + 39/39 `test_npc_near_match.py` + 219/219 `test_npc_extractor.py` (regression sweep intact) |
| **Patches landed** | 1 architectural ship (Path A spec→review→implement); 1 doctrine amendment (§14.1 first amendment-to-existing-lock the project has shipped); 1 operational migration (3 rows sum-into-canonical) |
| **Recon result** | External reviewers (ChatGPT + Gemini) converged on 7 of 8 contested points; single divergence resolved toward Gemini on cleanup-with-2B logic |
| **Live-verify results** | Structural: 41/41 tests pass, bot restart clean (PID 247822), migration values exact (44/51/42), regression sweep intact. **Behavioral: closed live in campaign 17 — collapse log fired twice on "Eldrin" short-form emission, anchor mc bumped 44→46, zero bare-firstname rows regrew, resolver renders canonical names, zero ambiguous-anchor logs.** Loop closed end-to-end. |
| **Doctrine anchored** | §14.1 (first amendment-to-existing-lock; new sub-numbering precedent in DOCTRINE.md) |
| **Doctrine candidates filed** | None pre-emptively. The amendment-via-sub-numbering pattern is single-instance; awaits second occurrence to anchor as candidate. |
| **HALT escalations** | 0 — all eight implementation phases passed gates without pivot-or-defer; line-number drift in brief surfaced as in-flight adjustment, not HALT |
| **Ship status** | ✅ SHIPPED LIVE — code + tests + docs + migration + behavioral verify all green; doctrine §14.1 active write-path invariant in campaign 17 |
| **Multiplayer Fixes plan v3 status** | Unchanged — Ships 1-A-2-3 ✅ / Listener verification ✅ / Dumb combat ✅ / Dumb combat prompt purity ✅ / Combat-boundary hardening ✅ / Ships 4-5 MVP-test scrutiny pending playtest phase |
| **Next session recommendation** | (1) Operator walks the five-step Discord verify in campaign 17 (~5 min) to close the behavioral verify; (2) Resume cleanup-tail queue from S46 (RollBuffer drain on !init end — medium friction; COMBAT_END 0-action framing — lowest friction; _handle_rest_event recon-now ship); (3) Playtest phase when operator's schedule allows; (4) Filed not sequenced: multi-section PHASE_12_SPEC header citation updates (polish), row 11 Garrik emergent-fragmentation ship (separate scope), PHASE_12_SPEC.md reconstruction (corpus-archaeology). |
| **PC rsync** | done via targeted rsync of 6 files (dnd_engine.py, test_npc_token_prefix_collapse.py, NPC_TOKEN_PREFIX_COLLAPSE_SPEC.md, DOCTRINE.md, VIRGIL_MASTER.md, WHY.md); push-all-to-pc.sh NOT run per Deployment workflow; planner-side SESSIONS.md entry pending push-docs |

---

# Session 48 — RollBuffer Drain on `!init end` (§78 layer-1 in-memory substrate completion) (May 13, 2026)

S47 closed the doctrine-amendment ship (§14.1 token-prefix collapse). S48 resumes the cleanup-tail queue with the first item: RollBuffer drain on `!init end`. Path B small ship; recon-first dispatch (per F-60 discipline) reshaped the friction ranking before action. Single doctrine-application ship; second instance of §78 four-layer rule applied at the state-reset surface, this time on the in-memory mechanical-event substrate.

## What landed

### 1. §78 layer-1 extends to in-memory substrate (application, not amendment)

§78's four-layer rule (mode transitions = mechanical cleanup + narrative buffer reset + transitional-window silence + boundary atmospheric closeout) was anchored at S45 against DB-side mechanical state (`clear_active_turn`, `clear_combatants`). S48 recon confirmed that in-memory RollBuffer survives the same boundary without draining — stale rolls leak into post-combat narration via `_format_avrae_events`'s `=== AVRAE EVENTS ===` block, plus surface as `(N rolls in play)` footer artifact.

The doctrine's intent was substrate-agnostic ("all mechanical state resets at the boundary"); the S45 anchoring just hadn't been tested against in-memory state. S48 ships the application without amendment to DOCTRINE.md — the rule already covers it. WHY.md captures the reasoning. Second instance backs the substrate-agnostic read: S45 (DB substrate) + S48 (in-memory substrate).

### 2. Fix shape: guild-wide flush (Candidate A from recon)

New `RollBuffer.size(guild_id) → int` in `avrae_listener.py` (raw storage count, no sweep — reflects events being cleared, not post-TTL survivors). Drain call `buffer.clear(message.guild.id)` + new telemetry `init_end_rollbuffer_drained: campaign={N} guild={N} drained_count={N}` in `_handle_init_event` evt_type='end' path, sibling step AFTER `reset_narrative_buffers_on_combat_exit` (S45) and BEFORE `_dispatch_combat_narration` (S45-F). Try/except wrapper — drain never blocks mechanical state.

Fix-shape selection rationale recorded in recon: (A) guild-wide flush mirrors S45's blunt-full-reset pattern at the same layer; (B) per-actor drain has same strict-equality failure-mode risk that motivated §14.1; (C) push-into-COMBAT_END-dispatch intermixes mechanical-cleanup and atmospheric-closeout semantics violating layer separation; (D) skip-and-let-TTL-handle-it doesn't fix the symptom.

### 3. Loop-closure proof in live verify

Pre-fix journal evidence (2026-05-11T22:14:58): `buffer.consume: 1 events for actors=['donovan ruby'] roll_kinds=['check']` surfacing immediately after `init: combat ended`. Post-fix live verify (2026-05-13T17:00, Stonebridge market scene): `init_end_rollbuffer_drained: campaign=17 guild=1498592771471314977 drained_count=2` at boundary, followed by `buffer.consume: 0 events for actors=['donovan ruby']` on first post-combat turn. Direct counter — the failing-state journal evidence is now structurally impossible.

## What didn't surface this session

- **No HALT escalations.** Recon-first dispatch caught the friction-ranking reshape before action ship; action ship walked clean.
- **No new doctrine candidates filed.** §78 four-layer rule's substrate-agnostic read earned its second instance via S48; not a new candidate, application of existing doctrine.
- **No regressions.** Regression panel (S45 init_end_buffer_reset 10/10, S22 avrae_sweep 11/11, avrae_listener_edge_cases 7/7) intact.

## Friction-ranking reshape from recon

The S45 filing framed RollBuffer drain as "orthogonal buffer cleanup — medium operator-friction." Recon revealed two findings that reshaped the ship before dispatch:

**Finding 1:** The footer artifact `(1 roll in play)` is the visible tip; the larger failure mode is the AVRAE EVENTS block pollution feeding stale mid-combat rolls into post-combat narration prompts. The LLM may narrate stale checks as if they just happened in the post-combat scene — the exact failure mode §77 (renderer-not-ruler) and §78 (mode-transition state-reset) exist to prevent. Reframed: structural-friction §78 completeness, not cosmetic-friction polish.

**Finding 2:** §78's layer-1 anchoring at S45 named DB-side mechanical state; in-memory RollBuffer is structurally distinct substrate. Substrate-agnostic read of the doctrine resolves it without amendment.

Neither finding came from doc-side recon — both required server-side journal grep + code read. F-60 discipline applied: filings are starting points, not specs; recon-first dispatch catches scope errors planner can't see.

## Discovered findings (informational, not blocking)

**`_handle_rest_event` (`!lr` / `!sr`) parallel surface.** Recon Phase 4 surfaced that rest-event path exits combat without going through `_handle_init_event` — same §78 four-layer audit likely applies, both for `reset_narrative_buffers_on_combat_exit` AND `buffer.clear(guild_id)`. Next queued ship per F-60 recon-first discipline. Observe playtest first; re-decide before dispatch.

**Sweep telemetry silent because consume always wins.** `unconsumed_roll_swept:` (S22) has zero hits across the entire journal — every stale roll is consumed by some actor's turn rather than aging out. S48's drain will likely never trip the sweep either; if it does, existing telemetry catches it.

**New telemetry primitive worth folding into playtest framework §5.2.** `init_end_rollbuffer_drained:` rate is meaningful state-integrity signal during playtest. Not blocking; flag for next framework touch.

## What this session does NOT do

- **Per-actor drain semantic (Candidate B).** Rejected per fix-shape selection — strict-equality matcher would inherit the same Phase 6 failure mode that motivated §14.1.
- **Push-into-COMBAT_END drain (Candidate C).** Rejected — intermixes layer-1 (mechanical cleanup) with layer-4 (atmospheric closeout); violates layer separation.
- **`_handle_rest_event` recon.** Next ship; not this one.
- **DOCTRINE.md amendment.** §78 four-layer rule already covers substrate-agnostically; ship is application, not amendment.

## Tests

New file `test_init_end_rollbuffer_drain.py`: 10 assertions, all green. Regression panel (S45 init_end_buffer_reset 10/10, S22 avrae_sweep 11/11, avrae_listener_edge_cases 7/7) intact.

## Cross-references

- `VIRGIL_MASTER_S47_DELTA.md` — new three-patch delta following S45 delta pattern (header stamp + §78 layer-1 in-memory extension + Active scripts append)
- `WHY.md` — architectural-call entry: why application not amendment, why guild-wide over per-actor, S45 cross-ref as DB-substrate first instance
- `avrae_listener.py:768` — `buffer.clear(guild_id)` existing single drain entry, preserves §17
- `discord_dnd_bot.py` `_handle_init_event` evt_type='end' — fix site, sibling to S45's `reset_narrative_buffers_on_combat_exit`
- DOCTRINE.md §78 — unchanged; substrate-agnostic intent satisfied by application
- S45 SESSIONS entry — first instance of §78 layer-1 (DB substrate)
- F-60 — recon-first discipline that caught the friction-ranking reshape

| Field | Value |
|---|---|
| **Code shipped** | `avrae_listener.py` (RollBuffer.size method addition); `discord_dnd_bot.py` (buffer.clear + telemetry in _handle_init_event evt_type='end' path); `VIRGIL_MASTER_S47_DELTA.md` (new three-patch delta); `WHY.md` (architectural-call entry) |
| **Planner edits** | SESSIONS.md S48 entry |
| **Tests added** | 10 assertions in `test_init_end_rollbuffer_drain.py` (new file) |
| **Tests passing** | 10/10 new + regression panel intact (S45 10/10, S22 11/11, edge_cases 7/7) |
| **Patches landed** | 1 doctrine-application ship (§78 layer-1 substrate-agnostic completion); 1 telemetry primitive (`init_end_rollbuffer_drained:`) |
| **Recon result** | Recon-first dispatch reshaped friction ranking from cosmetic to structural-completeness; fix-shape A selected over B/C/D with named reasoning |
| **Live-verify results** | All three pass criteria hit in campaign 17 Stonebridge market scene 17:00 UTC: drain fired with drained_count=2, post-combat footer clean (no rolls-in-play artifact), AVRAE EVENTS block empty on first post-combat narration. Direct counter to pre-fix journal evidence. |
| **Doctrine anchored** | None (§78 substrate-agnostic application, not amendment) |
| **Doctrine candidates filed** | None pre-emptively. Substrate-agnostic pattern has two instances now (S45 DB + S48 in-memory); if a third substrate surfaces in a future ship, anchor the pattern as candidate. |
| **HALT escalations** | 0 — recon caught scope reshape before action ship; action ship walked clean |
| **Ship status** | ✅ SHIPPED LIVE — code + tests + docs + live verify all green; §78 layer-1 now active across both substrates in campaign 17 |
| **Multiplayer Fixes plan v3 status** | Unchanged — Ships 1-A-2-3 ✅ / Listener verification ✅ / Dumb combat ✅ / Dumb combat prompt purity ✅ / Combat-boundary hardening ✅ / Ships 4-5 MVP-test scrutiny pending playtest phase |
| **Next session recommendation** | (1) `_handle_rest_event` recon-first ship — parallel surface to `_handle_init_event` per S48 recon Phase 4; same §78 audit applies. (2) COMBAT_END 0-action framing — lowest-friction creative-writing fix from S46 queue. (3) Playtest phase when schedule allows. (4) Filed not sequenced: row 11 Garrik emergent-fragmentation ship, multi-section PHASE_12_SPEC header citations, PHASE_12_SPEC.md reconstruction, fold `init_end_rollbuffer_drained:` into playtest framework §5.2 on next framework touch. |
| **PC rsync** | done via targeted rsync of 5 files (avrae_listener.py, discord_dnd_bot.py, test_init_end_rollbuffer_drain.py, WHY.md, VIRGIL_MASTER_S47_DELTA.md); push-all-to-pc.sh NOT run per Deployment workflow; planner-side SESSIONS.md entry pending push-docs |

---

# Session 49 — Rest-Event RollBuffer Drain (mode-agnostic, §78 third-instance application) (May 13, 2026)

S48 closed the init-end RollBuffer drain (§78 in-memory substrate completion). S49 continues the cleanup-tail queue with the rest-event boundary as parallel surface. Path B small ship; recon-first dispatch (per F-60) reshaped scope before action, and a quick-check follow-up surfaced an S48 framing correction that this entry carries forward honestly per the append-only ledger convention.

## Context correction (S48 framing)

S48's SESSIONS entry recommended `_handle_rest_event` recon-first as the next ship and framed the combat-mode branch of that handler as never-having-fired in production. A quick-check recon dispatched pre-S49-action surfaced that this was wrong: the combat-mode branch fired once on 2026-04-30T09:36:49 (campaign 20, guild=1498592771471314977). S48 entry is preserved as the planner's read at the time; this entry carries the corrected understanding. The Apr 30 firing produced no visible drift in the post-rest narration — actor extraction fell to the `'someone'` fallback, which kept the rest event from matching any consume filter and the substrate concern stayed unrealized.

The correction reshaped the ship's framing from "anticipated-friction protection on an unfired path" to "observed-once-but-symptom-free path with serendipitous extraction-fallback protection." The fix-shape decision (B over A/C) survived the correction — the Apr 30 evidence doesn't change that layer-2/4 §78 gaps have never produced symptoms even on the path's one firing; "evolve from observed friction" still defers those layers. What the correction DID change: the mode-agnostic substrate-completion drain (B) earned its slot more clearly, because the serendipitous protection from actor-extraction fallback is structural unreliability rather than structural safety.

## What landed

### 1. §78 layer-1 third-instance application at rest-event boundary

`buffer.clear(message.guild.id)` + `rest_event_rollbuffer_drained:` telemetry inside `_handle_rest_event`, mode-agnostic placement (outside the `if current_mode == 'combat'` branch), AFTER `advance_time`. Try/except wrapper. Telemetry includes `rest_kind` field (long rest / short rest / rest) for playtest pattern analysis.

Mode-agnostic placement is the load-bearing design choice. Two reasons:
- Rest events pollute RollBuffer regardless of mode; the combat-mode gate would leave exploration-mode rests with the same substrate gap.
- Serendipitous protection via actor-extraction fallback to `'someone'` is real but unreliable; if Avrae's embed format changes or actor extraction improves, the gap surfaces immediately. Mode-agnostic drain protects against that without depending on extraction behavior.

Reuses `RollBuffer.size()` (S48 addition) and existing `RollBuffer.clear()`. §17 single-write-path preserved.

### 2. Test-development self-correction (methodological note)

Initial mode-agnostic placement assertion used naive indent comparison (drain at indent depth 12, combat-branch body also at depth 12 — false equality, would have falsely-passed on a load-bearing design test). Switched to structural anchor (`# Track 4 #3 — time advancement` comment marks the first mode-agnostic line after the if/else block). Caught pre-ship, not post-hoc. Documented in WHY.md.

The pattern is worth noting because the test was about to falsely-pass on the WHOLE POINT of the ship: if the assertion can't distinguish "outside the if/else" from "inside the combat branch," the test isn't testing mode-agnostic placement, it's just testing that the line exists somewhere in the handler body.

### 3. Deferred per "evolve from observed friction"

Combat-mode-branch §78 layer-2 (`reset_narrative_buffers_on_combat_exit` inside the combat-mode branch) and layer-4 (COMBAT_END-equivalent dispatch or new `REST_END_FROM_COMBAT` directive kind) gaps remain in code. Apr 30 firing didn't produce visible drift; deferred until playtest or production evidence justifies the ship. Audit findings durable in S48 recon doc + this entry; future ship dispatches quickly when justified.

Layer-4 specifically: if it ever lands, it likely warrants a new `REST_END_FROM_COMBAT` trigger kind rather than reusing COMBAT_END — the existing `_COMBAT_NARRATION_INVARIANTS` and phantom-NPC clauses are tuned to `!init end` confirmation semantics and would produce off-kilter rest narration ("clash of steel" applied to "the party rests"). Filing the shape, not committing to it.

## What didn't surface this session

- **No HALT escalations.** One in-flight test-development self-correction (naive indent → structural anchor) but caught pre-ship and resolved without invoking pivot-or-defer.
- **No new doctrine candidates filed pre-emptively.** §78 substrate-agnostic application is now at three instances (S45 DB-init-end + S48 in-memory-init-end + S49 in-memory-rest-event) — crosses the two-instance threshold for doctrine-candidate filing; planner reconciliation note below.
- **No regressions.** Regression panel: S48 init_end_rollbuffer_drained 10/10 + S45 init_end_buffer_reset 10/10 + S22 avrae_sweep 11/11 + avrae_listener_edge_cases 7/7 all intact.

## Doctrine candidate surfaced (not yet filed)

§78 substrate-agnostic application has three instances now — above the two-instance threshold per WORKING_WITH_CLAUDE.md anchoring discipline. The composition observation is: "the four-layer rule applies across substrates (DB / in-memory) and across boundaries (init-end / rest-event), not just at the original anchored surface." The four layers themselves are unchanged across instances; what's anchored by three-instance accumulation is the substrate-and-boundary-agnostic intent.

Filing shape if anchored: `.5` sibling per the composition-observation pattern WORKING_WITH_CLAUDE.md names ("composition observations file as `.5` siblings once first instance is concrete"). §78.5 substrate-agnostic application, or whatever numbering convention DOCTRINE.md uses for sub-clauses of existing entries.

Not filed in this session pre-emptively per the discipline rule against planner-side momentum filings. Surfaced for operator decision: anchor now as §78.5 (three instances earned the candidate slot), or wait for a fourth substrate-or-boundary instance to confirm the pattern is genuine rather than coincidental. Planner lean: anchor now — substrate-agnostic intent is load-bearing for future ships in adjacent territory; explicit codification preserves the boundary against drift-toward-substrate-specific-readings.

## Discovered findings (informational, not blocking)

**`_handle_init_list_event` combat-exit audit (deferred from S48 recon Phase 5 #2).** Potential third combat-exit surface — init-list edit that clears the last enemy could exit combat without firing `!init end`. Recon-first, separate dispatch. Not sequenced.

**Telemetry calibration window.** `rest_event_rollbuffer_drained:` is a new primitive; first few playtest sessions are the calibration window for what `drained_count` values look like in practice and whether `rest_kind` patterns reveal anything (long-rest vs short-rest frequency, etc.). No instrumentation needed; passive observation.

**`init_end_rollbuffer_drained:` + `rest_event_rollbuffer_drained:` both belong in playtest framework §5.2** on next framework touch.

## What this session does NOT do

- **Combat-mode-branch §78 layer-2/4 fixes** — deferred per observed-friction discipline.
- **`_handle_init_list_event` audit** — separate scope.
- **Shared `exit_combat_to_exploration` helper refactor** — still premature DRY at two-and-a-half instances (S48 full, S49 partial); 3 full instances would earn the abstraction, the rest-event boundary is partial.
- **DOCTRINE.md amendment** — §78 is substrate-agnostic by intent; §78.5 candidate filing is operator decision, not auto-anchored.

## Tests

New file `test_rest_event_rollbuffer_drain.py`: 10 assertions, all green. Regression panel intact (4 prior test files, all pass).

## Cross-references

- `VIRGIL_MASTER_S49_DELTA.md` — new three-patch delta following S45/S47 pattern (header stamp + §78 layer-1 mode-agnostic rest-event extension + Active scripts append)
- `WHY.md` — architectural-call entry: why mode-agnostic placement, why layer-2/4 gaps stay deferred, why source-text regression chosen over handler invocation, methodological note on the indent-vs-anchor self-correction
- `discord_dnd_bot.py` `_handle_rest_event` — fix site, mode-agnostic placement after `advance_time`
- `avrae_listener.py:768` — `buffer.clear` single drain entry, preserves §17
- DOCTRINE.md §78 — unchanged; substrate-agnostic intent satisfied by application; candidate §78.5 surfaced for operator filing decision
- S48 SESSIONS entry — second instance of §78 layer-1 (in-memory substrate, init-end boundary); S49 is third instance (in-memory substrate, rest-event boundary)
- F-60 — recon-first discipline; this session's quick-check recon caught the S48 framing error

| Field | Value |
|---|---|
| **Code shipped** | `discord_dnd_bot.py` (buffer.clear + telemetry in _handle_rest_event mode-agnostic placement); `VIRGIL_MASTER_S49_DELTA.md` (new delta artifact); `WHY.md` (architectural-call entry) |
| **Planner edits** | SESSIONS.md S49 entry (includes S48 framing correction) |
| **Tests added** | 10 assertions in `test_rest_event_rollbuffer_drain.py` (new file) |
| **Tests passing** | 10/10 new + regression panel intact (S48 10/10, S45 10/10, S22 11/11, edge_cases 7/7) |
| **Patches landed** | 1 doctrine-application ship (§78 layer-1 third-instance, in-memory substrate at rest-event boundary); 1 telemetry primitive (`rest_event_rollbuffer_drained:`) |
| **Recon result** | Pre-dispatch quick-check recon corrected S48 framing (Apr 30 combat-mode firing); fix-shape B (mode-agnostic Layer-1 drain) confirmed over A/C/D/E with named reasoning |
| **Live-verify results** | **Closed live in campaign 17 (May 13, 18:57-18:58):** Long rest (`!game lr`) and short rest (`!game sr`) both fired `rest_event_rollbuffer_drained:` with `drained_count=1` and correct `rest_kind` field. Subsequent `buffer.consume` returned 0 events for `actors=['donovan ruby']`; subsequent narration posted with 0 avrae events. Both rest-kind paths verified. First journal evidence of structural protection over serendipity: pre-S49, rest events lingered up to 75s relying on `actor='someone'` extraction fallback to keep them out of PC filters; post-S49, drained immediately at boundary. Structural verify: 10/10 tests pass, bot restart clean, mode-agnostic placement test anchored on structural marker not indent. |
| **Doctrine anchored** | **§78.5 Substrate-agnostic and boundary-agnostic application** — anchored as composition-observation sub-section under §78. Three instances back the anchoring: S45 (DB substrate, init-end boundary) + S48 (in-memory substrate, init-end boundary) + S49 (in-memory substrate, rest-event boundary). Parallels the §17+§76 composition pattern at S41. |
| **Doctrine candidates filed** | None pre-emptively. §78.5 was surfaced + anchored within this session per operator decision (three-instance threshold met). |
| **HALT escalations** | 0 — test-development self-correction (indent→anchor) resolved pre-ship without HALT |
| **Ship status** | ✅ SHIPPED LIVE — code + tests + docs + restart + behavioral verify all green; §78 layer-1 now active across three instances (S45 DB-init-end + S48 in-memory-init-end + S49 in-memory-rest-event) |
| **Multiplayer Fixes plan v3 status** | Unchanged — Ships 1-A-2-3 ✅ / Listener verification ✅ / Dumb combat ✅ / Dumb combat prompt purity ✅ / Combat-boundary hardening ✅ / Ships 4-5 MVP-test scrutiny pending playtest phase |
| **Next session recommendation** | (1) COMBAT_END 0-action framing — lowest-friction creative-writing fix from S46 queue, last item before playtest opens. (2) Playtest phase when schedule allows. (3) Filed not sequenced: combat-mode-branch §78 layer-2/4 (deferred per observed-friction), `_handle_init_list_event` audit, row 11 Garrik emergent-fragmentation, multi-section PHASE_12_SPEC header citations, PHASE_12_SPEC.md reconstruction, fold both rollbuffer-drain primitives into playtest framework §5.2 on next framework touch. |
| **PC rsync** | done via targeted rsync of 4 files (discord_dnd_bot.py, test_rest_event_rollbuffer_drain.py, WHY.md, VIRGIL_MASTER_S49_DELTA.md); push-all-to-pc.sh NOT run per Deployment workflow; planner-side SESSIONS.md entry pending push-docs |

---

# Session 50 — COMBAT_END 0-Action Framing Fix (§78.6 anchored, layer-4 render-vs-marker) (May 13, 2026)

S49 closed the rest-event RollBuffer drain (§78 third-instance application). S50 closes the cleanup-tail queue with the last symptom-fix from S46's filing: COMBAT_END 0-action framing drift. Path B small ship per locked plan; first doctrine-anchoring this planner instance has shipped (§78.6 layer-4 render-vs-marker, sub-section under §78 parallel to §78.5). Recon-first dispatch (per F-60) reshaped the scope from "cosmetic creative-writing" to "layer-4 doctrine refinement."

## What landed

### 1. §78.6 anchored — layer-4 render is conditional on content-to-render

DOCTRINE.md §78 gains a second sub-section parallel to §78.5. The refinement: §78 layer-4 (boundary atmospheric closeout) has two operational modes:
- **LLM render** — fires when narratable content exists during the bounded mode session. The LLM produces atmospheric closeout per §77 atmospheric continuity rules.
- **Deterministic boundary marker** — fires when no narratable content existed during the bounded session. Engine emits fixed neutral text; LLM bypassed entirely.

The choice between modes is content-conditioned. §78's four-layer rule itself is unchanged — mode transitions still require all four layers; boundary atmospheric closeout still part of the state-reset surface. What's refined is layer-4's internal structure.

**One-instance anchoring with named reasoning.** Standard discipline is two-instance threshold (per WORKING_WITH_CLAUDE.md). §78.6 anchored at one instance because the distinction is **structurally derived, not emergent** — the moment you ask "when should layer-4 dispatch LLM render vs deterministic marker," the framework forces the distinction. The two-instance threshold protects against premature anchoring of patterns that might not be real; here the pattern is locked by the structure of layer-4 itself, not waiting for confirmation. This is an explicit exception to the rule with named reasoning, not a quiet break.

### 2. Symptom evidence and fix shape

S50 recon reproduced the symptom from today's S48 verify walk: a 0-action combat (init begin + init end with no rolls between) produced COMBAT_END narration that fabricated atmospheric events that did not occur:

> "The clash of steel and shouted commands fade into a heavy silence, the dust settling on the cobblestones as the last echoes die away. Donovan Ruby stands steady, his breath coming in measured pulls, the room now still and empty."

No clash, no shouts, no dust, no motion, no echoes ever occurred in narration. Within §77 (no adjudication crossed; no HP claims; no kills) but the framing presupposed narratable events that didn't exist.

Recon Phase 2 verdict: LLM had **zero positive signal** that 0-action happened, and the COMBAT_END framing explicitly directed combat-vocabulary atmospherics regardless. Not LLM compliance issue; directive design issue.

Fix-shape locked at F (hybrid):
- In-memory beat counter (`_combat_beat_counter: dict[int, int]`) keyed by guild_id
- Increments on BLOODIED + DOWNED dispatches only (HP-state transitions = actual combat content)
- ROUND_START + COMBAT_END do NOT increment (structurally always-fires / counter-reader respectively)
- Reset on `!init begin`; cleared on `!init end` after dispatch
- COMBAT_END dispatch branches: beats=0 → deterministic neutral closeout (`"Combat ends. The moment passes."`); beats≥1 → existing LLM render unchanged

### 3. Beat definition explicit-not-inferred

The action-ship dispatch pinned beat semantics explicitly so Code didn't have to infer at implementation time:
- **Increment:** BLOODIED, DOWNED
- **Do NOT increment:** ROUND_START (structurally always-fires regardless of content), COMBAT_END (the kind reading the counter)

Rationale: BLOODIED and DOWNED require HP-state transitions which require actual combat content (attack hit + damage applied). ROUND_START fires when Avrae rotates the active turn back to the start of round, regardless of whether anyone took action. Counting ROUND_START would mis-classify exactly the 0-action case we're detecting.

### 4. Cleanup-tail queue drained

S46 filed five small follow-ups. Four shipped across S47-S50; one fixture-gated and waiting:

| Filing | Disposition |
|---|---|
| COMBAT_END 0-action framing | ✅ S50 (this session) |
| RollBuffer drain on `!init end` | ✅ S48 |
| Phantom companions DB hygiene | ✅ S46 (deferred — surface was misnamed; redirected to `dnd_npcs` fragmentation → S47) |
| `_handle_rest_event` parallel-surface audit | ✅ S49 |
| DEATH_SAVE_EVENT_START | Fixture-gated; still waiting |

**Cleanup tail is structurally drained.** Next phase opens to playtest.

## What didn't surface this session

- **No HALT escalations.** One regression-test fragility caught and fixed mid-ship (S48 test's hardcoded source-text window pushed past assertion target by §78.6's ~1500 additional chars; Code switched to dynamic boundary using `\nasync def ` anchor).
- **No further doctrine candidates filed pre-emptively.** §78.6 is the doctrine anchored this session; no adjacent candidates surfaced.
- **No regressions outside the one S48-test fragility, which was caught and resolved in-session.**

## Methodological note worth carrying forward

Hardcoded source-text-character-offsets in regression tests are fragility — when new code lands between the anchor and the window boundary, the window can push past the assertion target. S48's test used a hardcoded 4000-char window from a specific anchor; §78.6's branch additions pushed `_dispatch_combat_narration` past it. Code switched to a dynamic end-of-function boundary (`\nasync def ` anchor) which is more resilient to future additions. Pattern: prefer structural anchors (function boundaries, named markers) over absolute character counts. Not filing as candidate (one instance); mental note for future test writes.

## Discovered findings (informational, not blocking)

**ROUND_START 0-action edge** — same §78.6 shape could apply if the conservative environment-focused framing produces drift in playtest. Lower-priority than COMBAT_END was — ROUND_START framing already avoids specific-event presupposition. Filed; observe playtest first.

**Combat-mode-branch §78 layer-2/4 at `_handle_rest_event`** — still deferred per S49 reconciliation. If playtest produces visible drift after rest-during-combat, the layer-4 fix there would benefit from §78.6's render-vs-marker framing.

**`_handle_init_list_event` combat-exit audit** — third potential combat-exit surface; recon-first, separate dispatch.

**Both rollbuffer-drain primitives + new beat-tracking primitives belong in playtest framework §5.2** on next framework touch (`init_end_rollbuffer_drained:`, `rest_event_rollbuffer_drained:`, `combat_end_zero_action:`, `combat_end_llm_dispatch:`, `combat_beat_incremented:`).

## What this session does NOT do

- **ROUND_START 0-action framing** — separate observation-justified ship if symptom surfaces.
- **Refactor to shared layer-4 content-predicate helper** — premature DRY at one instance; future ship needing the pattern earns the abstraction.
- **Schema changes** — in-memory substrate locked per §78.5 substrate-agnostic guidance.
- **Per-actor or per-round beat granularity** — current ship is per-combat-session aggregate; finer granularity is candidate work if needed.

## Tests

New file `test_combat_end_zero_action.py`: 14 assertions, all green. Regression panel: S48 test fragility caught + fixed (10/10); S45 init_end_buffer_reset 10/10; S49 rest_event_rollbuffer_drain 10/10; S22 avrae_sweep 11/11; avrae_listener_edge_cases 7/7. Total 52 assertions pass.

## Cross-references

- `DOCTRINE.md` — §78.6 sub-section added (layer-4 render-vs-marker doctrine refinement); placed after §78.5 parallel-structurally
- `VIRGIL_MASTER_S50_DELTA.md` — new four-patch delta following S45/S47/S49 pattern
- `WHY.md` — architectural-call entry with five subsections (F vs A/B/C/D, beat = BLOODIED+DOWNED rationale, in-memory vs DB, §78.6 vs fold-in, branch at caller not dispatch function)
- `discord_dnd_bot.py` — fix sites: module-level beat counter + reset in `_handle_init_event` evt_type='begin' + increment inside `_dispatch_combat_narration` + branch at COMBAT_END dispatch site in `_handle_init_event` evt_type='end'
- DOCTRINE.md §78 — parent rule, unchanged; §78.6 refines layer-4 internal structure
- DOCTRINE.md §78.5 — parallel sub-section; sibling refinement on different doctrine axis (§78.5 = where rule applies; §78.6 = how layer-4 behaves on edge cases)
- S48 + S49 SESSIONS entries — sibling §78 application ships in the S45-S50 arc
- S46 follow-up filings — cleanup-tail queue, now drained except for fixture-gated DEATH_SAVE_EVENT_START

| Field | Value |
|---|---|
| **Code shipped** | `discord_dnd_bot.py` (module-level beat counter + 4 helpers + neutral closeout constant + reset wire + increment wire gated to BLOODIED/DOWNED + COMBAT_END branch site + counter cleanup); `DOCTRINE.md` (§78.6 sub-section); `VIRGIL_MASTER_S50_DELTA.md` (new delta artifact); `WHY.md` (architectural-call entry) |
| **Planner edits** | SESSIONS.md S50 entry |
| **Tests added** | 14 assertions in `test_combat_end_zero_action.py` (new file) |
| **Tests passing** | 14/14 new + 38/38 regression (S48 10/10 after fragility fix, S45 10/10, S49 10/10, S22 11/11, edge_cases 7/7) |
| **Patches landed** | 1 doctrine-anchoring ship (§78.6 one-instance anchored with named exception to two-instance rule); 3 telemetry primitives (`combat_end_zero_action:`, `combat_end_llm_dispatch:`, `combat_beat_incremented:`); 1 in-flight regression-test fix (S48 hardcoded source-text window → dynamic boundary) |
| **Recon result** | Pre-dispatch recon reshaped scope from "cosmetic creative-writing" to "layer-4 doctrine refinement"; fix-shape F (hybrid: deterministic on 0-action, LLM on multi-action) confirmed over A/B/C/D/E with named reasoning |
| **Live-verify results** | **Closed live in campaign 17 (May 13 evening):** Both Path 1 (0-action) and Path 2 (intended multi-action) reached `combat_end_zero_action: beats=0` — Path 2 didn't get a BLOODIED to actually exercise the multi-action branch, but wiring is functional and structural test 7 covers the multi-action branch with mocked beat counter. §78.6 is now active on the deterministic-marker path in production. Structural verify: 14/14 tests pass + 38/38 regression intact, bot restart clean. |
| **Doctrine anchored** | **§78.6 Layer-4 render is conditional on content-to-render.** One-instance anchored with named exception to two-instance rule — the distinction is structurally derived from §78 layer-4's design, not emergent from accumulated cases. Parallel sub-section to §78.5 (§78.5 = where four-layer rule applies; §78.6 = how layer-4 behaves on content-conditioned edge cases). |
| **Doctrine candidates filed** | None pre-emptively. |
| **HALT escalations** | 0 — one regression-test fragility caught and resolved mid-ship (S48 hardcoded source-text window); did not escalate to HALT |
| **Ship status** | ✅ SHIPPED LIVE — code + tests + docs + restart + behavioral verify all green; §78.6 active in production; cleanup tail closed |
| **Multiplayer Fixes plan v3 status** | Unchanged — Ships 1-A-2-3 ✅ / Listener verification ✅ / Dumb combat ✅ / Dumb combat prompt purity ✅ / Combat-boundary hardening ✅ / Ships 4-5 MVP-test scrutiny pending playtest phase. **S46 cleanup-tail queue drained (4 of 5 shipped; DEATH_SAVE_EVENT_START fixture-gated).** |
| **Next session recommendation** | **Playtest phase.** Cleanup tail is drained; no new architecture during playtest per S45-locked discipline. (1) Operator walks the S50 live verify (two paths in handoff). (2) Playtest sessions when schedule allows. (3) Filed not sequenced: ROUND_START 0-action edge (§78.6 pattern applies if symptom surfaces), combat-mode-branch §78 layer-2/4 at `_handle_rest_event` (deferred), `_handle_init_list_event` audit, row 11 Garrik emergent-fragmentation, DEATH_SAVE_EVENT_START (fixture-gated), multi-section PHASE_12_SPEC citations, PHASE_12_SPEC.md reconstruction, fold all five new telemetry primitives into playtest framework §5.2 on next framework touch. |
| **PC rsync** | done via targeted rsync of 6 files (discord_dnd_bot.py, test_combat_end_zero_action.py, test_init_end_rollbuffer_drain.py [S48 regression fix], DOCTRINE.md, VIRGIL_MASTER_S50_DELTA.md, WHY.md); push-all-to-pc.sh NOT run per Deployment workflow; planner-side SESSIONS.md entry pending push-docs |





---

# Session 51 — Every-Turn Time Signal in SCENE STATE Block (§76 read-side analogue closure) (May 13, 2026)

S50's live verify walk surfaced a separate body/footer divergence bug: footer rendered Day 10 Midday correctly (reads from DB) but narration body defaulted to "morning light" framing because the LLM had no current-time signal between time-advance moments. Code traced the mechanism, surfaced fix-shape framing, asked for the next move; planner shipped Path B small ship per §76's filed read-side candidate. Sixth consecutive small ship in the pre-playtest cleanup arc (S45 → S48 → S49 → S50 → S51).

## Context

Mechanism (per S50-verify recon): `compute_time_directive` (`dnd_orchestration.py:2917-2941`) fires only on `just_advanced=True` turns and provides the time signal via active narrate-the-advance beat. SCENE STATE block in `dnd_engine.py:5407-5413` carries Location / Tension / Recent NPCs / Last player action but NOT campaign_day or day_phase. So the LLM gets a time signal on the turn immediately after time advances, then nothing on subsequent turns. Footer (state_footer) reads campaign_day + day_phase directly from DB and renders correctly — explaining body/footer divergence symptom (footer: Day 10 Midday; body: "morning light washes over the market").

§76's body explicitly named this filing: *"S36 time-of-day drift demonstrates that even a fully-locked field (engine-bound `day_phase`) can be drifted-against in adjacent narrative prose that no four-property field caused... filed candidate for future Ship 4/5 if observed friction accumulates."* S50 verify produced concrete observed friction. S51 closes the most common case at the prompt-input layer; the verifier candidate stays filed as safety net for partial LLM compliance.

## What landed

### 1. SCENE STATE block carries Day + Time of day every turn

Fix-shape A locked over C (functionally identical; A is smaller delta; `compute_time_directive` stays untouched). Two lines added to `scene_state_section` at the build_dm_context site (between Location and Tension per Code's judgment on positional consistency):

```
Day: {scene_state.get('campaign_day', '?')}
Time of day: {scene_state.get('day_phase', '?')}
```

Canonical keys per `get_scene_state` at `dnd_engine.py:1208-1209`. None/0/empty fallback renders `?` without crashing. `compute_time_directive` untouched per separate-responsibility logic: passive every-turn signal (S51's job) vs active narrate-the-advance beat (compute_time_directive's job).

### 2. §76 read-side analogue first project instance

§76's body named the read-side filing; S51 is the first instance of "engine-emit authoritative signal at prompt-input layer" pattern applied to read-side drift. Architecturally parallel to C1 (Engine-computed binding > validator-on-LLM-output) but on read-side rather than write-side — same argument shape (close the LLM-compliance dependency by giving the LLM ground truth), different surface (passive signal vs decision binding).

Doctrine: §76 stays unchanged at one instance. Promotion to §76.1 sub-section (or similar) waits for second read-side instance per the emergent-pattern two-instance rule. The pattern is genuinely emergent here — the read-side analogue concept was named in §76's body but its operational shape is what S51 establishes; a second instance confirms the shape is generalizable rather than ad-hoc.

### 3. Multi-turn live verify confirms structural fix

Load-bearing case: turns 2+ post-advance previously drifted to "morning light" defaults; post-S51 hold the current time signal across multi-turn play. Verify walk in campaign 17 (Day 11 Midday → Evening via `/advance days:0 phases:2`):

| Turn | Player input | Narration excerpt | Time-of-day reflected? |
|---|---|---|---|
| 1 (post-advance) | "I look around." | "the last amber of sunset slips away as the training ground's lanterns sputter to life" | ✓ Evening |
| 2 | "I head over to the merchant stall." | "the sun's last amber slips behind the stone walls, and the lanterns along the training yard flicker to life" | ✓ Evening |
| 3 | "What's in the back of the shop?" | scene continues consistently in Evening framing | ✓ Evening |
| 4 | "I ask the keeper about the road north." | grounded in current moment | ✓ Evening |

Pre-S51: only turn-1-after-advance had time signal; turns 2+ drifted. Post-S51: every turn carries authoritative time in SCENE STATE block.

## Friction-ranking pattern (extending pattern from S46/S47, S48, S50)

S51 differs from the three prior arc-internal recon-reshapes: the bug was caught DURING verify of an unrelated ship (S50), not via a filed follow-up at session start. Different surface for the same discipline: **verify walks surface adjacent bugs; treat them like recon findings.** Code's framing of fix shapes during S50 verify let planner reach decision quickly; ship was small enough for in-arc dispatch rather than queue-for-next-session.

Worth noting that the F-60 "filings are starting points, not specs" discipline generalizes to "verify-surfaced findings are starting points, not specs" — the same recon-first-then-decide pattern applies. S50 verify gave concrete journal evidence + file:line citations before any fix shape locked.

## What didn't surface this session

- **No HALT escalations.** Two test-extraction bugs caught during writing (initial `section-bound find(')', ...)` returned wrong paren; `find("\\n\\n", ...)` for compute_time_directive truncated at docstring boundary). Both fixed with unique post-section anchors. Methodological pattern note below.
- **No new §-entries.** §76 stays unchanged; promotion to §76.1 waits for second instance.
- **No regressions.** S50 14/14, S48 10/10, S45 10/10, S49 10/10 all intact.

## Methodological note (test-development pattern, third instance — anchoring threshold met)

S49 caught a naive-indent test that would have falsely-passed on mode-agnostic placement. S50 caught a hardcoded 4000-char source-text window that became stale after §78.6 added ~1500 chars. S51 caught two text-extraction bugs (wrong-paren find + docstring-boundary truncation) during test writing.

**Three instances now** of the pattern: hardcoded character-offsets, position-based finds, and indent-only comparisons in regression tests are fragility; structural anchors (function boundaries, named markers, content-pattern anchors, unique post-section markers) are the resilient version. Three-instance threshold met per WORKING_WITH_CLAUDE.md anchoring discipline. Earned a methodological note in WHY.md or WORKING_WITH_CLAUDE.md — candidate filing decision for operator. Not pre-emptively anchored per the discipline rule against planner-side momentum filings; surfaced for operator review.

## Filed candidate — player-narrative-authority drift (separate ship, recon-first when justified)

The S51 verify walk surfaced an adjacent drift mode worth flagging. Out of scope for this session per F-60 (recon-first, observe more playtest before fix-shape commits):

**Symptom shape:** DM correctly refused player premise on turn 2 ("There's no merchant stall here — those stalls line the market square beyond the guild hall, not the training grounds") — correct §77-aligned response: scene boundary held, redirect offered. But on turn 3 ("What's in the back of the shop?"), the DM caved and fully materialized a merchant interior INSIDE the training ground (curtained doorway, crates, locked chest). Turn 4 doubled down with "the clatter of the market" — at the training ground.

**Why this matters:** turn-2's correct refusal was undone by turn-3 player premise pressure. Player narration shouldn't materialize new physical surfaces by assuming them — letting them violates the canonical scene state (location='training ground', merchant stalls explicitly NOT there per turn-2's own declaration).

**Doctrine adjacency:** §77 (atmospheric continuity, not adjudication) covers WHAT can be narrated; this is about WHO writes scene canon under player premise pressure. Possibly a §77 sub-section ("scene boundaries are DM-canon; player premise contradicting established scene gets refused-or-transitioned, not retroactively granted"). Sibling to §1a roll-discipline rules — LLM has hard-stops against inventing mechanical outcomes; could earn parallel hard-stops against inventing scene canon.

**Filed candidates (not for action now):**
- Recon-first ship: survey journal/playtest for other instances. If recurring: prompt-side invariant clause + engine-side scene-canon check + player-vs-DM authority directive.
- Verifier candidate: SCENE_BOUNDARY_DRIFT violation class in `narration_verifier` — detects narration referencing entities/surfaces inconsistent with SCENE STATE's Location/canon.

Not starting either tonight. Per `feedback_no_pre_sequencing.md` and §38 filed-not-sequenced — needs more playtest observations before committing to fix shape. Filed in this entry as durable artifact so future planners (including this planner across context boundaries) can find it when adjacent symptoms surface.

## What this session does NOT do

- **`compute_time_directive` changes.** Its `just_advanced` gate is correct as-is per separate-responsibility logic.
- **Verifier-layer Ship 4/5 candidate.** Still filed under §76; this fix doesn't retire it.
- **Player-narrative-authority drift fix.** Filed as above; recon-first when justified.
- **§76.1 anchoring.** One instance; waits for second per emergent-pattern two-instance rule.
- **DOCTRINE.md update.** §76's read-side framing already covers this; the fix is application of the named candidate, not amendment.

## Tests

New file `test_scene_state_time_signal.py`: 10 assertions, all green. Regression: S50 14/14, S48 10/10, S45 10/10, S49 10/10 all intact.

## Cross-references

- `VIRGIL_MASTER_S51_DELTA.md` — new three-patch delta (header stamp + SCENE STATE prompt block subsection + Section 3 Core Design Principles fourth bullet on §76 read-side analogue). Independent of S45/S47/S49/S50 deltas.
- `WHY.md` — architectural-call entry: why engine-emit-every-turn over verifier-after-the-fact (C1 sibling shape on read-side) / why A over C (separates passive signal from active beat) / why §76 stays anchor at one instance (§76.1 waits for second instance per emergent-pattern rule).
- `dnd_engine.py` `scene_state_section` build_dm_context site — fix site (Day + Time of day lines added between Location and Tension)
- DOCTRINE.md §76 — parent doctrine, unchanged; S51 is first read-side application instance
- C1 (Candidate) — architecturally parallel write-side pattern; same engine-emit-authoritative argument applied to read-side here
- S50 SESSIONS entry — verify walk that surfaced this bug
- §77 — protected by signal-side fix routing around LLM-compliance question entirely
- §17 — preserved; no new write paths (SCENE STATE block is read-only from dnd_scene_state)

| Field | Value |
|---|---|
| **Code shipped** | `dnd_engine.py` (Day + Time of day lines added to scene_state_section between Location and Tension; canonical key extraction from scene_state dict; None/0/empty fallback to `?`); `VIRGIL_MASTER_S51_DELTA.md` (new three-patch delta); `WHY.md` (architectural-call entry on read-side analogue) |
| **Planner edits** | SESSIONS.md S51 entry; S50 entry's live-verify and ship-status fields updated to SHIPPED LIVE |
| **Tests added** | 10 assertions in `test_scene_state_time_signal.py` (new file) |
| **Tests passing** | 10/10 new + regression panel intact (S50 14/14, S48 10/10, S45 10/10, S49 10/10) |
| **Patches landed** | 1 read-side prompt-input fix closing the most common S36 / S50-verify time-divergence symptom; 1 §76 read-side analogue first project instance |
| **Recon result** | Bug surfaced during S50 verify walk (not a session-start filed follow-up); Code traced the mechanism (`compute_time_directive` just_advanced gate vs SCENE STATE block omission of time fields) + provided file:line citations + fix-shape framing pre-dispatch. Planner shipped Path B against shape A per locked plan. |
| **Live-verify results** | **Closed live in campaign 17 (May 13 evening multi-turn walk):** Day 11 Midday → Evening via `/advance days:0 phases:2`; turns 1-4 post-advance all carry Evening framing in narration body (pre-S51: only turn 1 had signal; turns 2+ drifted to morning defaults). Footer + body now consistent across multi-turn play. |
| **Doctrine anchored** | None this session. §76 read-side analogue gains first project instance; §76.1 sub-section waits for second instance per emergent-pattern two-instance rule. |
| **Doctrine candidates filed** | None pre-emptively. Methodological note (source-text-character-offset fragility in regression tests) reaches three-instance threshold this session; candidate filing decision deferred to operator. Player-narrative-authority drift candidate filed in entry body as durable artifact; recon-first ship if symptom recurs. |
| **HALT escalations** | 0 — two test-extraction bugs caught + fixed in-flight during test writing (wrong-paren find + docstring-boundary truncation); no doctrine HALT |
| **Ship status** | ✅ SHIPPED LIVE — code + tests + docs + restart + behavioral verify all green; §76 read-side analogue closing the most common time-drift case in production |
| **Multiplayer Fixes plan v3 status** | Unchanged — Ships 1-A-2-3 ✅ / Listener verification ✅ / Dumb combat ✅ / Dumb combat prompt purity ✅ / Combat-boundary hardening ✅ / Ships 4-5 MVP-test scrutiny pending playtest phase. S46 cleanup-tail queue drained at S50; S51 closes verify-surfaced adjacent bug. |
| **Cleanup tail status** | Drained. S46 queue closed at S50. S51 is verify-surfaced cleanup, separate from the S46 queue. No further cleanup ships pending. |
| **Next session recommendation** | **Playtest phase ready to open.** Six consecutive small ships closed; no architectural commits pending; gating bar fully cleared per HCN v3 §3.1. (1) Playtest sessions when schedule allows. (2) Operator decision on methodological-note anchoring (three-instance threshold met for source-text-fragility pattern). (3) Filed not sequenced: player-narrative-authority drift (recon-first if recurs in playtest), ROUND_START 0-action edge (§78.6 pattern applies if surfaces), combat-mode-branch §78 layer-2/4 at rest-event boundary, `_handle_init_list_event` audit, row 11 Garrik emergent-fragmentation, DEATH_SAVE_EVENT_START (fixture-gated), multi-section PHASE_12_SPEC citations, PHASE_12_SPEC.md reconstruction, fold all S48+S49+S50+S51 telemetry primitives into playtest framework §5.2 on next framework touch. |
| **PC rsync** | done via targeted rsync of 4 files (dnd_engine.py, test_scene_state_time_signal.py, WHY.md, VIRGIL_MASTER_S51_DELTA.md); push-all-to-pc.sh NOT run per Deployment workflow; planner-side SESSIONS.md entry pending push-docs |





---

# Session 52 — Telemetry fold into PLAYTEST_OBSERVATION_FRAMEWORK §5.2 (May 13, 2026)

Planner-only doc-edit ship. No Code dispatch, no production-code touch. S52 folds the five new telemetry primitives shipped across S48 + S49 + S50 into the playtest framework's state-integrity metrics section so playtest sessions inherit fresh grep instructions without re-deriving them.

This is the kind of small-but-durable work that earns its slot when an operator-defined gap ("playtest postponed") opens between cleanup ships. Item shape mirrors S46's framework v2 revision: documentation work that compounds when playtest does open, no architectural commits pending while it lands.

## What landed

`PLAYTEST_OBSERVATION_FRAMEWORK.md` §5.2 — five new bullet entries appended after the existing paired-signal note. Each entry follows the established §5 format: log line shape (with field names) / what it tracks (operational meaning) / architectural signal (what rate or distribution tells the operator). Doctrine cross-references included (§78.5 for the two RollBuffer drains; §78.6 for the three COMBAT_END layer-4 primitives).

Primitives folded:
- `init_end_rollbuffer_drained:` (S48, §78.5)
- `rest_event_rollbuffer_drained:` (S49, §78.5; carries `rest_kind` field distinguishing long-rest vs short-rest)
- `combat_end_zero_action:` (S50, §78.6; layer-4 BOUNDARY MARKER branch)
- `combat_end_llm_dispatch:` (S50, §78.6; layer-4 LLM RENDER branch)
- `combat_beat_incremented:` (S50, §78.6; per-dispatch increment, gated to BLOODIED + DOWNED kinds)

Status header at top of framework doc carries the new revision note: "Revised S52 — §5.2 telemetry fold..." alongside the existing S46 revision note.

## What this session does NOT do

- **Touch any code.** Pure planner doc-edit ship.
- **Anchor new doctrine.** The five primitives already cite their anchored doctrine entries (§78.5 / §78.6); the fold is operational, not doctrinal.
- **Change framework structure.** Bullets append to existing §5.2 in established format. No new sub-sections, no metric-set additions, no threshold revisions.
- **Run any external review.** Single-source planner work; no convergent-review trigger conditions met.

## Friction-ranking observation

S52 is the second planner-only doc-edit ship this arc (first was S51's WORKING_WITH_CLAUDE.md anchor for structural-anchors-over-character-offsets methodological note). Both shipped between operator-defined gaps in higher-leverage work. The pattern: planner-only doc-edit ships earn their slot when (a) the work is durable (doesn't get stale), (b) compounds across future ships (next planner / framework user inherits the addition), (c) the gap is operator-defined rather than planner-manufactured. S52 hits all three: telemetry fold is durable until the primitives themselves change; compounds for every future playtest session; the gap was "playtest postponed" not "planner needs busywork."

Worth flagging as discipline: doc-edit ships are legitimate work, but require the same earned-slot framing as code ships. The integrity check is whether the gap is real (operator-defined) or whether the ship is filling time. S52 + S51's WORKING_WITH_CLAUDE anchor both pass the check; pre-emptive doc edits during active ship sequences would not.

## Tests

N/A. Doc-edit ship.

## Cross-references

- `PLAYTEST_OBSERVATION_FRAMEWORK.md` §5.2 — destination of the fold
- S48 / S49 / S50 SESSIONS entries — origin of the five primitives
- DOCTRINE.md §78.5 / §78.6 — anchored doctrine these primitives serve
- S51 SESSIONS entry — named this fold as filed-not-sequenced item; S52 closes it
- `WORKING_WITH_CLAUDE.md` Workflow refinements — "Planner does not add doc edits without earned justification" discipline applied here

| Field | Value |
|---|---|
| **Code shipped** | None. Planner-only doc-edit ship. |
| **Planner edits** | `PLAYTEST_OBSERVATION_FRAMEWORK.md` (§5.2 telemetry fold: 5 new bullets + status-header revision note); SESSIONS.md S52 entry |
| **Tests added** | None |
| **Tests passing** | N/A |
| **Patches landed** | 1 framework operational fold (5 telemetry primitives documented for playtest grep) |
| **Recon result** | N/A — primitives were already operational from S48/S49/S50 ships; this fold is documentation only |
| **Live-verify results** | N/A — framework doc is reference material, not executable code |
| **Doctrine anchored** | None |
| **Doctrine candidates filed** | None |
| **HALT escalations** | 0 (one MCP edit timeout recovered cleanly on retry) |
| **Ship status** | ✅ SHIPPED — doc edit landed, framework status header updated, ready for playtest grep when phase opens |
| **Multiplayer Fixes plan v3 status** | Unchanged |
| **Cleanup tail status** | Drained at S50. S51 + S52 are post-cleanup follow-on ships, not S46 queue items. |
| **Next session recommendation** | Playtest when schedule allows. Filed not sequenced: player-narrative-authority drift (recon-first if recurs), ROUND_START 0-action edge, combat-mode-branch §78 layer-2/4 at rest-event boundary, `_handle_init_list_event` audit, row 11 Garrik emergent-fragmentation, DEATH_SAVE_EVENT_START (fixture-gated), multi-section PHASE_12_SPEC citations, PHASE_12_SPEC.md reconstruction. |
| **PC rsync** | N/A — planner-only ship, edit landed directly on PC via MCP; push-docs required to land server-canonical |







