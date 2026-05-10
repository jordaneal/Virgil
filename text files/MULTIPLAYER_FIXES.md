# Multiplayer Fixes — Strategic Plan

**Status:** PLANNER v2 — post-GPT review (round 2) and Gemini review
**Authored:** Session 33, May 10 2026 (planner: Claude; DM/architect: Jordan)
**Revision history:** v1 drafted post-S32; GPT round-1 review integrated five updates (Ship 5e dropped, Ship 4 scene-scope-first resolution, SceneComposition aggregator, Ship 3 Virgil-authoritative trajectory, doctrine candidate "remove write authority over validation"). v2 incorporates a forced re-read of GPT round-2 plus Gemini review — fourteen updates total spanning argument structure, axis-of-disagreement framing, and named-pattern lifting. Spine unchanged: same ship list, same ship ordering, same fix shapes, same calendar.
**Triggered by:** S32 multiplayer playtest. The system is unplayable in current state. Findings A, B, H, L plus a cluster of medium-severity findings stack into a coherent architectural diagnosis.
**Priority frame:** Pivots ahead of the existing roadmap queue. Roadmap items currently in-flight (Bug 1 Phase 2, Combat Playability Cluster #5.1 verify, Scene Lifecycle v1, motion-systems thread) are paused until this plan completes.
**Calendar estimate:** 9–13 days, 5–9 sessions.
**Cross-references:** `S32_MULTIPLAYER_PLAYTEST_FINDINGS.md`, `THE_GOAL.md`, `DOCTRINE.md` §1a/§1b, `FAILURES.md` F-45, F-54, F-55.

---

## §1. The diagnosis in one sentence

**Three closures that were supposed to hold (F-45, §1a write-side, narration-doesn't-create-state) are leaking through architectural seams the original closures didn't cover, and the multiplayer playtest exposed all three at once.**

This is not a "the LLM is bad" problem. The LLM is doing exactly what it was given. The problem is that the system has **incomplete separation between six layers** that need to stay distinct: authoritative simulation state, interpretive narrative state, presentation formatting, inferred world memory, player intent, and mechanical resolution. Most of those separations hold today; two are leaking, and the leaks are where Findings A, H, and L live:

- **Inferred world memory** is bleeding into authoritative simulation state via `extract_scene_updates`'s LLM-authored writes (Finding A, recursive hallucination memory loop)
- **Interpretive narrative state** is bleeding into mechanical resolution via the DM-typed-directive flow that bypasses Track 7 #1's CHECK_ACTION binding (Finding L, F-45 regression)
- **Mechanical resolution** is split-brain across two truth systems for hydrated NPCs (Finding H, engine knows the NPC, Avrae doesn't)

Findings B (canonical-name reuse), J (DC leak), I (combat onboarding template), G (debug strings), §5.7 (narration continuity), §5.8 (economic ordering) are downstream symptoms or polish — they cluster under the three architectural closures above or under existing F-55 (Combat Playability Cluster) and resolve there.

---

## §2. North-star principles

Three principles govern every ship in this plan. The first is the controlling one; the other two are siblings that fall out of it.

### §2.1 The LLM is a renderer of truth, not a ruler of truth

This is restating Doctrine §1a in sharper language. Every ship in this plan closes one specific surface where the LLM is currently authoring truth and replaces it with engine-authored truth that the LLM only renders.

The question to ask of every fix shape: *does this ship make the engine more authoritative, or does it ask the LLM to behave better?* If the answer is "asks the LLM to behave better," the spec is wrong. Reject the spec, find the engine-authoritative version.

This principle has historical weight in the project. Past sessions have reached for prompt escalation (HARD STOP RULES), retry loops (Track 7 #2 verifier retry), and verifier proliferation candidates as the response to drift. Those are all "ask the LLM to behave better" moves. The principle codifies the opposite reflex.

### §2.2 Scene-scope-first resolution

When the LLM names an entity, the system resolves identity by checking what's in scope right now — not by global string match against the entire database. NPCs, combatants, and items are resolved against the active scene's entity composition first. Out-of-scope name matches do not resolve to existing canonical rows; they create fresh entities or get rejected.

This applies at extraction time (`npc_extractor`), at verification time (`narration_verifier` IDENTITY_DRIFT class proposed in Ship 4), and at retrieval time (F-44 chroma-scoping candidate). The principle is the same across all three: presence in active scope is the gate; name match is the lookup *within* scope only.

Three reviewers (the planner, the GPT review, the Gemini review) independently converged on this as the right resolution discipline after the canonical-name-reuse evidence in Finding B. The pattern earns naming because it generalizes — every future identity-drift mode is closed by the same query shape.

### §2.3 Structural removal of write authority beats validation

When a field exhibits drift, removing the LLM's write authority is structurally stronger than adding a validator. Validation is a band-aid; derived state or no-LLM-writer is the structural fix.

This principle has four supporting axes:

1. **Single source of truth** (sibling to Doctrine §17). One canonical writer is easier to reason about than one writer plus N validators verifying the writer's output.
2. **Validators accumulate.** Once you start adding them, you keep adding them. The validation layer becomes its own maintenance burden that crowds out the primary work — same slippery-slope shape as Doctrine §26 (ever-growing exception lists).
3. **Validators are subject to §17's narrow-exception discipline.** Broad validators are smell. New validators require explicit narrow scope, just like second writers.
4. **Local hardware compute cost.** Virgil runs on self-hosted hardware. Every LLM-based validation loop or retry prompt burns local resources, eats VRAM, and slows DM-to-player response time. Standard Python/SQL logic is computationally cheap; LLM validators are not. Structural removal of write authority is not just architecturally cleaner — it is materially faster on the hardware Virgil actually runs on.
---

## §3. Plan structure

Three primary architectural ships (Ships 1–3), each gated by a spec-then-review-then-implement cycle per `WORKING_WITH_CLAUDE.md` cadence. Two follow-up ships (Ships 4–5) close the canonical-name reuse channel and the polish cluster. One filed candidate (Ship 4.5) decides at Ship 1 verify checkpoint.

| Ship | Goal | Closes | Sessions | Status |
|------|------|--------|----------|--------|
| 1 | Resolution Binding | Finding L, F-45 regression, Bug 1 Phase 2 (side effect) | S33–S34 | committed |
| 2 | Scene State Canon Discipline | Finding A, anchors candidate Doctrine §76 | S35–S37 | committed |
| 3 | NPC State-Sync Boundary | Finding H, files as F-55 cluster sibling #5.5 | S38–S39 | committed |
| 4 | Scene-Scope-First Identity Resolution | Finding B, builds SceneComposition aggregator | S40 | committed |
| 4.5 | Multi-Actor Temporal State | S32 batched-actor evidence | S40b or v1.x | **filed candidate** |
| 5 | Polish cluster | Findings J, G, I (template only), §5.7 | S41 | committed (5e dropped) |

**Ordering for Ships 1–3 follows from the trigger-statement axis** (see §12 decision 1 for full reasoning). Ship 1 first because the trigger statement names "playability now" as the optimization axis, and Ship 1 closes the failure most directly blocking playability. Ship 2 second because cumulative-compounding canon corruption is the next-most-fatal failure mode. Ship 3 third because it requires F-55 cluster scaffolding context.

Each ship's spec lives at `/home/jordaneal/virgil-docs/<SHIP_NAME>_SPEC.md` (server-only) and review at `<SHIP_NAME>_REVIEW.md`, per the established cadence.

After Ship 5 lands, **return to ROADMAP**: F-55 #5.4 Resolver becomes next-pick if not deferred to Combat Playability Cluster sequencing. Bug 1 Phase 2 already shipped as side effect of Ship 1.
---

## §4. Ship 1 — Resolution Binding

**Closes:** Finding L (roll resolution unbound from rolled value), F-45 regression. Ships Bug 1 Phase 2 as a side effect.
**Goal:** When Avrae rolls against a pending directive, the rolled value vs DC determines the narrative outcome. Player self-report is irrelevant. Engine knows the answer before the LLM is invoked.

### §4.1 Fix shape

Pure function `resolve_directive(directive_row, avrae_event) → ResolutionResult` lives in `dnd_orchestration.py` (sibling to `compute_persistence_directive` etc per Doctrine §59). No DB writes; pure compute.

`ResolutionResult` is an immutable frozen dataclass:

```
actor: str           # canonical name, snapshotted at directive emit
check_kind: str      # 'check' | 'save'  (cast deferred — see §4.4)
skill_or_save: str   # 'perception' | 'wisdom' | etc
dc: int              # DM-set DC at directive emit
roll_total: int      # final value from Avrae embed
passed: bool         # roll_total >= dc, computed engine-side
rolled_at: float     # unix timestamp
directive_id: int    # FK to dnd_pending_roll_directives
```

Phase 2 wiring: when matcher consumes a directive, it calls `resolve_directive`, then auto-fires `_dm_respond_and_post` with the `ResolutionResult` rendered as a §15-shape AUTHORITATIVE-CANON block at top-of-prompt:

```
═══ AUTHORITATIVE ROLL RESOLUTION ═══
Donovan Ruby attempted a Perception check (DC 10).
Roll total: 6.
Outcome: FAILED.

You MUST narrate this as a failure. Donovan does NOT discover hidden information.
Do NOT narrate success. Do NOT invent an alternative interpretation.
═══
```

Bottom-of-prompt repeat of "Outcome: FAILED" per §48 (concrete-in-prompt narrows drift).

### §4.2 Verifier extension

New violation class in `narration_verifier.py` per the §11.F locked-classes pattern:

**`ROLL_OUTCOME_DRIFT`** — narration claims success on `passed=False` ResolutionResult OR claims failure on `passed=True`. Detection: keyword scan for success/failure terms cross-referenced against the resolution. 1-retry loop per existing verifier escalation.

### §4.3 Why this works

- Rolled value vs DC computed engine-side, never inferred from text
- Player self-report ("I passed") is no longer the input — Avrae's `roll_total` is
- LLM is constrained to render an outcome it didn't decide
- Pattern composes cleanly with Track 7 #1's existing CHECK_ACTION binding (same shape, different surface)
- ROLL_OUTCOME_DRIFT verifier provides retry pressure when LLM drifts

### §4.4 Decisions to lock in spec

1. **DC source.** Two options: (a) parse DC from the directive emit text and store on `dnd_pending_roll_directives` row; (b) DM types DC explicitly in directive (`!check perception 10`). **Recommend (a)** — preserves existing flow, no Avrae compatibility break.
2. **No-DC directives.** When DM types `!check perception` without a DC, what's the resolution shape? **Recommend skip resolution binding** — fall through to existing free-narration flow. Preserves DM authority over which checks have stakes.
3. **Crit handling.** Nat 20 / nat 1 — D&D 5e RAW: only attack rolls and death saves auto-succeed/fail. **Recommend RAW** for v1; v1.x candidate for table-rule customization.
4. **Multi-actor mismatch path.** Wrong-actor rolls don't trigger resolution (Phase 1 behavior). **Confirm Ship 1 does not change this.**
5. **Save and cast directive resolution.** Saves: same shape as check. Cast: subtler — spell-casts don't have a DC at emit time; resolution happens at target's save. **Recommend Ship 1 covers check + save only**; cast directives stay in Phase 1 telemetry-only behavior; cast resolution gets its own spec.
6. **Phase 2 trigger criterion 5.** Add: "narrated outcome matches roll-vs-DC verdict in 100% of consumed directives." Measured via ROLL_OUTCOME_DRIFT verifier (zero violations across one session = pass).
7. **Backward compatibility.** Manual-trigger flow (DM types narration himself) bypasses resolution binding. **Recommend (a)** — manual-trigger is the DM's escape hatch.

### §4.5 Work breakdown

| Session | Scope | Model |
|---------|-------|-------|
| S33 part 1 | Spec drafting (`RESOLUTION_BINDING_SPEC.md`). 7 §11 decisions. Recon: existing `dnd_pending_roll_directives` schema, `parse_avrae_embed`, `narration_verifier.py` violation-class pattern, Track 7 #1 CHECK_ACTION rendering. | Opus medium |
| S33 part 2 | Review doc (`RESOLUTION_BINDING_REVIEW.md`). Walk 7 decisions. Jordan locks. | Opus medium |
| S34 | Implementation. New `dnd_pending_roll_directives.dc INTEGER` column (idempotent migration). DC parser extension. `resolve_directive` pure function. `ResolutionResult` dataclass. ROLL_OUTCOME_DRIFT verifier class. Phase 2 wiring (replaces `directive_would_fire_dm_respond:` log with `_dm_respond_and_post` call). ~40 test assertions across 2 new files + extensions. | Opus high |

### §4.6 Gate criteria

- 32+ test assertions green
- Live verify: at least 3 check-resolution events across one play session, all narrated correctly per `passed` value
- Zero `ROLL_OUTCOME_DRIFT` verifier violations in one full play session
- DC parsing works for at least 4 distinct DC values

### §4.7 What Ship 1 does NOT fix

- Combat-mode rolls (Phase 1 skips combat-mode directives; Ship 1 inherits)
- Cast directive resolution (deferred — needs target-side save adjudication)
- Player-typed `!check` flow (Phase 1 skips player-authored; Ship 1 inherits)
- Stale-footer name parsing (F-58 stays v1.1 candidate)
---

## §5. Ship 2 — Scene State Canon Discipline

**Closes:** Finding A (scene_state.location LLM-write without canon-check). Anchors candidate Doctrine §76 (recursive hallucination memory loop). Likely thins narration continuity cluster (§5.7) as a side effect.
**Goal:** The LLM never writes to `scene_state.location` or `scene_state.established_details`. Both fields become read-only-by-LLM. Location is derived from canonical `current_location_id`; established_details either gets dropped entirely or moves behind a deterministic write path.

### §5.1 Fix shape

This is GPT's "absolutely derived state" call applied properly. Validation (canon-check on writes) was the Plan B from S32 findings; recon confirmed derived state is stronger structurally per Doctrine §17 (single write paths per field).

**Three subships, lockable independently:**

#### Ship 2a — Drop `scene_state.location` as LLM-writable scalar

- Remove `location` from `extract_scene_updates`'s LLM extraction set
- Remove `location` from `update_scene_state`'s write path
- Update `build_dm_context` to read location from `dnd_locations.canonical_name` joined on `current_location_id` at prompt-build time (already partially done per Bug 3's S25 fix)
- Single writer becomes `set_current_location` (already exists, called from `/travel` only — already correct per F-13 disposition)

Failure mode this closes: the recursive hallucination memory loop. LLM cannot drift on what it cannot write.

#### Ship 2b — Delete `established_details`

**Default disposition: delete the field.** Not constrain it. Not validator-gate it. Delete it.

The reasoning: `established_details` is the textbook latent-canon channel. It's LLM-writable, persisted to `dnd_scene_state`, fed back into retrieval, and carries narrative-inferential weight — every property of a recursive hallucination memory loop. The defect shape is intrinsic to having such a field at all, not to how the field is validated. Worked example: LLM narrates "the barkeep nervously wipes blood from the counter" → stored in `established_details` → three scenes later, retrieval surfaces "blood on counter" → LLM infers murder happened → NPC dialogue references murder → extraction stores "town fearful after killing." Emergent false history, recursively reinforced by retrieval. Validators cannot fix this; the field's existence is the failure mode.

Recon decides only one question: is there a hard structural dependency that forces (b-ii) gated-write instead of (b-i) delete? Examples of hard dependencies that would force gated-write: prompt sections that explicitly reference established_details with no alternative source; downstream code paths that fail when the field is empty. Examples that do NOT force gated-write: narrative-flavor LLM directives that can be dropped without behavior loss; aesthetic prompt richness that can be replaced with structured projections from canonical sources.

Three candidate dispositions, in priority order:

- **(b-i) DELETE the field.** Default. Recon must produce evidence to override.
- **(b-ii) Gated-write only on canonical events.** Forced disposition only if recon shows hard structural dependency. Writers: `set_current_location` clears it; structured triggers (combat start, NPC spawn from skeleton, scene_lifecycle compress) write to it. LLM never writes.
- **(b-iii) Validator-gated LLM writes.** Rejected by §2.3. Only considered if (b-i) and (b-ii) both fail recon, which is unlikely.

Failure mode this closes: the recursive hallucination memory loop, in its purest form. If something matters narratively, it should become structured state (its own table, its own writers). If it doesn't matter narratively, it should remain ephemeral prose (in the LLM's output for that turn only, not persisted). Middle-ground memory fields are AI poison.

#### Ship 2c — `extract_scene_updates` audit pass

Inventory every field `extract_scene_updates` writes. For each, apply the **four-property latent-canon test**:

1. Is the field LLM-writable?
2. Is the field persisted (survives turn boundary)?
3. Is the field retrieved (fed into future prompts, directly or via chroma)?
4. Is the field narratively inferential (the LLM treats it as canonical context that other inferences build on)?

**Any field with all four properties is a pseudo-memory channel and should be removed, not validated.** `established_details` was the canonical instance Ship 2b addresses; Ship 2c finds the others.

For each field that scores 4/4, classify the disposition: structural (must persist as canon) → move to its own table with deterministic writer; flavor (can drop) → remove the persistence write entirely, allow the LLM to use it in narration without storing; derived (read from canonical source instead) → replace LLM-write path with canonical read path at prompt-build time.

This is the meta-pattern. Ships 2a and 2b are specific instances; Ship 2c is the structural audit that ensures no other field has the same defect shape. The four-property test becomes the project-level audit tool for any future "should this be LLM-writable" question.

### §5.2 Decisions to lock in spec

1. **`location` field disposition.** Keep column (engine-only writer) or drop column (schema migration). **Recommend drop column** — single-writer is achieved by removing the writer entirely. Any caller that reads `scene_state.location` migrates to `dnd_locations.canonical_name`.
2. **`established_details` disposition.** (b-i), (b-ii), or (b-iii). Recon required before locking. **Recommend (b-i) pending recon.**
3. **Doctrine candidate #3 anchoring** ("LLM-writable scalars on engine-state tables are silent drift channels unless gated by deterministic canon-check validators"). Single instance after S32; Ship 2c audit may surface 1+ additional instances. Lock anchoring decision after Ship 2c completes.
4. **Doctrine §76 anchor.** "LLM output → persistent state → retrieval context → future LLM output is a drift-amplification loop. The fix is removing the LLM's write authority on the persistent surface, not validating the writes." Three project instances now (S22 #2 chroma contamination, S32 location drift, F-44 chroma bleed pattern) — clears the bar. **Anchor in Ship 2 spec.**
5. **Migration strategy.** Existing campaigns have non-empty `scene_state.location` strings. **Recommend keep column read-only**, ignore on read, log `legacy_location_field_present:` on every campaign with non-empty value for cleanup pass. Non-destructive, observable.
6. **`extract_scene_updates` task_type review.** Currently `task_type='extraction'`. Does extraction need to change task type or model after the writable surface shrinks? Recon-decide.

### §5.3 Work breakdown

| Session | Scope | Model |
|---------|-------|-------|
| S35 part 1 | Recon pass: `established_details` use audit, `extract_scene_updates` field inventory, `scene_state.location` reader audit. Output: `SCENE_STATE_CANON_RECON.md` (data, not decisions). | Sonnet medium |
| S35 part 2 | Spec drafting (`SCENE_STATE_CANON_SPEC.md`) gating on recon. 6 §11 decisions. | Opus medium |
| S35 part 3 | Review doc + lock pass. | Opus medium |
| S36 | Implementation Ship 2a (drop location LLM write) + Ship 2c audit findings. | Opus medium |
| S37 (if needed) | Implementation Ship 2b (established_details disposition). May fold into S36 if (b-i) "drop" wins. | Sonnet medium |

### §5.4 Gate criteria

- `extract_scene_updates` writes zero fields the LLM has authored without canonical validation
- Live verify: location field stays accurate across 10+ multi-turn turns including chroma-relevant retrieval
- Doctrine §76 anchored
- Zero `legacy_location_field_present:` log lines after migration cleanup pass

### §5.5 What Ship 2 does NOT fix

- Chroma scoping by location (F-44 stays v1.x — different channel; Ship 2 closes the *write* side, F-44 closes the *retrieval* side)
- Finding B (canonical-name reuse) — different fix shape; Ship 4
- Narration continuity cluster (§5.7) — likely thins as side effect, not directly fixed
---

## §6. Ship 3 — NPC State-Sync Boundary

**Closes:** Finding H (hydrate→Avrae sync gap). Files as F-55 cluster sibling **#5.5 — Combat State Coherence**.
**Goal:** When the DM creates an NPC via `hydrate`, that NPC has consistent state across the dm-aside engine domain AND the Avrae mechanical-resolution domain. Combat against hydrated NPCs resolves correctly.

### §6.1 Fix shape

The single-writer-split problem: `hydrate` writes engine state; Avrae sheet creation is a separate writer triggered by player `!sheet`. Combat resolution depends on Avrae sheets. Therefore any NPC created via dm-aside is mechanically unresolvable in combat.

**This ship is the first concrete step in a longer architectural trajectory: Virgil-authoritative-with-Avrae-as-projection.**

Virgil already authoritatively owns world state, scene state, NPCs, locations, consequences, inventory, combat snapshots, and (post-Ship-2) scene_state.location. Avrae owns dice resolution, character sheet rendering, and the Discord-side init UI. The hybrid "two truth systems with synchronization seams" framing is no longer accurate; Virgil is already authoritative on everything that matters. Ship 3 makes that partition explicit by adding a deterministic projection from engine state to Avrae for hydrated NPCs, closing the last meaningful seam where Avrae held authority Virgil should own.

Future Combat Playability Cluster ships continue this trajectory: F-55 #5.4 Resolver translates player intent into Avrae commands, with Virgil owning the intent-to-command translation. F-55 #5.2 NPC Turn Automation has Virgil drive enemy turns deterministically, with Avrae executing the resulting commands. F-55 #5.3 Combat Cockpit renders Virgil-owned affordances. Each ship reduces the surface area where Avrae acts as authority and grows the surface area where Avrae acts as projection.

**Three candidate fixes filed in S32 findings; pick at spec time. Recon-blocked** — the right answer depends on what Avrae's API surface actually permits.

- **(a) Auto-create Avrae sheet on hydrate.** Bot emits `!init madd <stats>` on the DM's behalf when `/hydrate` is invoked.
- **(b) Combat resolution layer detects "this NPC has dm-aside stats but no Avrae sheet"** and resolves against engine-side stats directly, bypassing Avrae for that entity.
- **(c) Disallow combat against non-Avrae-sheeted entities entirely;** force player to manually create sheets before combat.

(a) is cleanest UX and most aligned with the Virgil-authoritative trajectory — engine writes, Avrae projects. (b) decouples but introduces parallel combat resolution paths, fighting the trajectory. (c) is brutal but defensible per §17.

### §6.2 Recon questions (must answer before spec)

1. Can the bot programmatically create an Avrae NPC sheet from hydrated stats? (e.g. `!init madd <name>` on Avrae's side via bot-emitted command)
2. If yes — does that violate Doctrine §65 (bot never emits `!`-commands)? Or does it fall under a narrow exception (bot-as-DM-proxy when DM has explicitly invoked `/hydrate`)?
3. If no — what's the fallback combat-resolution path for non-Avrae-sheeted entities?
4. How does Track 6 #5.1 (Combat Entry Assist) currently bridge this? It already posts `!init madd` cards to `#dm-aside` for DM approval — does that path cover hydrate too, or is hydrate a separate flow?

### §6.3 Coupling to F-55 cluster

Ship 3 lands before the rest of F-55's Combat Playability Cluster (#5.4 Resolver, #5.2 NPC Turn Automation, #5.3 Combat Cockpit). Without state-sync, those cluster ships can't trust the data they're built on. **Ship 3 is filed as F-55 #5.5 — Combat State Coherence,** a new cluster sibling.

**Ordering:** Ship 3 first because #5.4 builds commands that resolve against Avrae state — broken state breaks every command. After Ship 3 lands clean, return to ROADMAP with #5.4 unblocked.

### §6.4 Decisions to lock in spec

1. **Bot-as-DM-proxy exception to §65.** Does §65 allow the bot to emit `!init madd <hydrated-stats>` on the DM's behalf when DM has explicitly invoked `/hydrate`? Likely framing: §17 narrow-exception territory (single-writer-with-projection: hydrate is the writer, Avrae sheet is the projection). Doctrine review required.
2. **Sync direction.** Hydrate writes engine first then projects to Avrae? Or hydrate writes Avrae first then engine projects from Avrae's response? **Recommend engine-first** — engine is the authoritative source per §1a.
3. **Sheet-already-exists handling.** If `/refresh` shows an Avrae sheet already exists for the NPC name: (a) reject — DM must use Avrae's normal sheet flow; (b) overwrite; (c) merge. **Recommend (a)** — DM has chosen to use Avrae for that NPC; respect that choice.
4. **Combat resolution path for non-Avrae-sheeted entities.** Three sub-cases, each gets a disposition:
   - (i) anonymous-shape combatants ("a hulking shadow") — out of scope, v2 candidate
   - (ii) PCs from non-DDB sources (manual stat entry) — out of scope, user-error
   - (iii) failed-projection NPCs (hydrate ran, Avrae sheet creation failed) — Ship 3 concern: `hydrate_avrae_sync_failed:` log + DM-aside escalation message + combat blocked until resolved
5. **Doctrine §65 amendment.** Lock language: §65 amendment allowing bot-as-DM-proxy emission for hydrate/Avrae-sync flow only, scoped narrowly per §17 narrow-exception framing. Companion to §17's existing narrow-exception precedent (`apply_starting_time_seed`).
6. **Telemetry.** New log lines: `hydrate_avrae_sync: campaign={N} npc={name} action={created|skipped|failed} reason={...}`. Log every hydrate path including no-op cases.

### §6.5 Work breakdown

| Session | Scope | Model |
|---------|-------|-------|
| S38 part 1 | Recon pass: Avrae API surface for programmatic NPC creation, current `/hydrate` flow inventory, current `_handle_init_list_event` interaction with hydrate. Output: recon doc. | Sonnet medium |
| S38 part 2 | Spec drafting (`NPC_STATE_SYNC_SPEC.md`) gating on recon. 6 §11 decisions including Doctrine §65 amendment proposal. | Opus medium |
| S38 part 3 | Review doc + lock pass. Doctrine review on §65 amendment. | Opus medium |
| S39 | Implementation. | Opus high |

### §6.6 Gate criteria

- Live verify: hydrate an NPC, run `/refresh`, see Avrae sheet exists. Initiate combat with that NPC. Roll attack against NPC; HP reduces correctly. Roll save by NPC; CR-band stat used.
- Zero `<None>` HP outcomes during combat against hydrated NPCs across one session
- §65 amendment doctrine-locked OR Ship 3 ships within existing §65 boundaries

### §6.7 What Ship 3 does NOT fix

- Combat onboarding UX (Finding I template polish) — addressed in Ship 5
- Surprise-turn handling for combat-initiator (Thomas's design ask) — F-55 #5.4 territory or new sub-spec
- Anonymous-shape combatants — v2 candidate
---

## §7. Ship 4 — Scene-Scope-First Identity Resolution

**Closes:** Finding B (canonical-name reuse / in-scene identity collapse). Builds `get_scene_composition` aggregator as private helper, with promotion path to shared infrastructure once second consumer surfaces.
**Goal:** The npc_extractor (and any future entity-resolution path) checks active-scene scope first, and only resolves names against existing canonical rows that are *in scope*. Out-of-scope name matches do not resolve to existing rows; they create fresh entities. This closes the "Merrick the bartender → Merrick the clerk" failure mode structurally rather than via per-symptom validation.

### §7.1 Fix shape

The defect Finding B exposes is at the resolution layer, not the data model layer. NPC IDs already exist as primary keys; consequences and locations already FK to them; the data model is correct. What's wrong is that the npc_extractor's resolution path matches names *globally* against `dnd_npcs.canonical_name` within the campaign, with no scope filter. So when the LLM narrates "Merrick" in the Guild Hall scene and Merrick-the-bartender exists from a different scene entirely, the global string-match resolves to him and the consequence binds to the wrong canonical row.

The fix is a query-shape change: resolve scene-scope-first.

**Resolution order becomes:**

1. Compute active scene composition (canonical NPCs at `current_location_id`, active combatants if mode=combat, recently-narrated entities)
2. Within that scope, name-string-match resolves to existing canonical row's ID
3. Outside that scope, no resolution — the name is treated as a fresh entity, gets a new ID, gets a new canonical row

This is the right scope for the defect. GPT proposed a stored Scene table as a foundational system; that's overshoot — it would add new writer surfaces, lifecycle semantics, and synchronization problems with existing tables. The minimum version that captures the principle is a **computed aggregator**, not a stored entity.

### §7.2 SceneComposition aggregator

Build a pure-function aggregator alongside Ship 4's resolution refactor:

```
@dataclass(frozen=True)
class SceneComposition:
    campaign_id: int
    location_id: int | None
    location_name: str | None       # joined from dnd_locations
    npcs_in_scope: list[NpcRow]     # dnd_npcs WHERE location_id = current_location_id
    combatants: list[CombatantRow]  # from dnd_combatant_state if mode=combat
    bound_pcs: list[CharacterRow]   # active controllers
    mode: str                       # exploration | combat | social
    rolled_at: float                # snapshot timestamp
```

`get_scene_composition(campaign_id) → SceneComposition` lives in `dnd_orchestration.py` per Doctrine §59 (pure function, no DB writes, signals dict pattern).

In v1, the aggregator is **private to npc_extractor** — used only by Ship 4's resolution refactor. It is documented as a **promotion candidate** for shared infrastructure when a second consumer arrives. Likely future consumers: F-44 chroma scoping, F-55 #5.4 Intent-to-Avrae Resolver target disambiguation, Scene Lifecycle v1 compression triggers. The pattern is correct architecture; pre-promoting it before a second consumer exists violates §6 (evolve from observed friction, not anticipated).

Drop GPT's `active_objects[]` and `environmental_state` fields — they have no canonical sources today, so materializing them would import the same latent-canon problem Ship 2 closes for `established_details`. If they ever need to exist, they earn their own structured tables first; SceneComposition projects from those tables when they exist.

### §7.3 Verifier extension

Sibling to the resolution-layer fix: new violation class in `narration_verifier.py`:

**`IDENTITY_DRIFT`** — narration uses a canonical NPC's name in a context that contradicts the NPC's canonical scene scope (location mismatch, role mismatch, or both). Detection: scan narration for canonical-NPC names; if the named NPC's `location_id` doesn't match `SceneComposition.location_id` OR the role keywords in narration don't match the canonical NPC's stored role, fire violation. 1-retry loop per existing verifier escalation.

This is the narration-time defense; the resolution-layer fix is the extraction-time defense. Together they close the channel both ways: (a) catches extraction-time canon poisoning even if narration slips through; (b) catches narration-time violation and retries before extraction runs.

### §7.4 Decisions to lock in spec

1. **Scene-scope definition.** What counts as "in scope"? Three candidates: (a) `current_location_id` only — strictest, matches existing `get_recently_active_npcs` filter; (b) `current_location_id` + recent-narration-mention window (last N turns); (c) `current_location_id` + active combatants regardless of `location_id`. **Recommend (a) for v1** — strict matches existing patterns; (b) and (c) earn additions if logs show false-fresh-creation cases.
2. **Out-of-scope name match handling.** When extractor sees a name matching an out-of-scope canonical NPC, three options: (a) create fresh row anyway, log `npc_out_of_scope_create:` for diagnostic; (b) skip extraction silently, log `npc_out_of_scope_skip:`; (c) flag DM via #dm-aside. **Recommend (a)** — preserves canon integrity, observable.
3. **Role-keyword matching for IDENTITY_DRIFT.** Strict role-string match? Substring match? LLM-judged similarity? **Recommend substring + canonical role keywords list per NPC** — e.g. canonical role "bartender" matches narration roles {"bartender", "barkeep", "innkeeper"}. Reject LLM-judged per §2.3 (validators accumulate; structural removal stronger).
4. **SceneComposition promotion gate.** When does the aggregator move from private to shared? **Lock criterion: when a second consumer's spec needs it.** Until then, it's an npc_extractor implementation detail. F-44 chroma scoping is the most-likely first consumer — when that ships, promote.
5. **Retroactive cleanup.** Forward-only or audit existing canonical-state poisoning from past sessions? **Recommend forward-only** — past consequences may already be acted on; rewriting them risks more harm than help.

### §7.5 Work breakdown

| Session | Scope | Model |
|---------|-------|-------|
| S40 part 1 | Spec + review combined session (smaller architectural surface than Ships 1-3, but the resolution refactor is real work). | Opus medium |
| S40 part 2 | Implementation. `get_scene_composition` aggregator, npc_extractor resolution refactor, IDENTITY_DRIFT verifier class. ~30 test assertions. | Opus medium |

S40 may share session with Ship 5 (polish cluster) if both small enough. Spec session may extend to 1.5x of typical scope due to the resolution refactor; the aggregator itself is templated against §59 pattern.

### §7.6 Gate criteria

- Live verify: introduce a fresh NPC in an established scene with a canonical-name conflict; verify `npc_out_of_scope_create:` log fires and consequence does not bind to the wrong canonical entity
- IDENTITY_DRIFT verifier fires at least once across one play session OR confirmed-zero by audit (either result is signal)

### §7.7 What Ship 4 does NOT fix

- F-49 fabricated combatants (already closed by Track 7 #2)
- F-44 chroma bleed across scenes — different channel; SceneComposition aggregator is the load-bearing primitive when F-44 ships, but Ship 4 doesn't ship F-44 itself
- Genuine in-fiction reuse (a different character also named Merrick) — out of scope; separate doctrine call
- Multi-actor temporal state collisions — see Ship 4.5 below

---

---

## §7B. Ship 4.5 — Multi-Actor Temporal State (filed candidate, not committed)

**Closes:** Concrete S32 evidence — `last_active_actor` stored only first chronological actor in batched multi-actor turn (Discord footer at 22:20:51 showed `⚔ Donovan Ruby, Karrok The Devourer` but `last_active_actor` stored `Donovan Ruby` only). Phase 2 spec criterion 4 cannot answer cleanly without resolution.
**Goal:** When Phase 2 narration fires after a multi-actor batched turn, the directive-binding logic correctly identifies which of the batched actors is the resolution target — instead of always binding to the first chronological actor.
**Status:** **Filed candidate, not committed.** Decide at end of Ship 4 whether this earns a slot before Ship 5 polish, ships in parallel with Ship 5, or files as v1.x candidate.

### §7B.1 Why this exists at all

GPT's first review raised "temporal inconsistency" as a future risk. Planner first-pass dismissed it as anticipated friction (engineer-against-friction-not-anticipation, §6). Re-reading evidence: the S32 multiplayer playtest produced a concrete temporal-state-collision instance — `last_active_actor` is a scalar, but the footer rendered two actors, and the matcher's directive-binding logic only sees the scalar. That's not anticipated friction; it's documented S32 friction the first-pass plan filed under "Phase 2 calibration data points" without slotting a fix.

The full transactional-scene-updates prescription GPT proposed is overshoot — Discord is naturally serializing, multi-actor batches are rare, MMO-scale lock systems would torch velocity. But the underlying point that multi-actor state needs explicit handling is correct.

### §7B.2 Candidate fix shapes

Three candidates, decide at spec time:

- **(a) Batched-actor list field.** `last_active_actor` becomes `last_active_actors TEXT` (JSON list). Matcher's directive-binding checks against the list; if any batched actor matches, bind. Footer rendering uses list-or-scalar branch.
- **(b) Resolution-time disambiguation.** When matcher fires resolution and the directive's snapshotted actor was part of a batch, prompt DM via #dm-aside to confirm target. Adds DM friction but avoids guessing.
- **(c) Strict first-chronological binding.** Document current behavior as intentional; multi-actor batches always bind to first chronological. DM works around by addressing single actor at a time when directive emit matters.

**Lean: (a)** — minimum structural change, no new DM friction, scales cleanly. (c) is cheapest but pushes problem onto DM. (b) is most correct but adds friction.

### §7B.3 Decision criterion

This ship slots if Ship 1's live verify shows multi-actor batches produce >1 directive-binding ambiguity per session in real play. If frequency is ≤1 per session, file v1.x. Decide at Ship 1 verify checkpoint.

---

## §8. Ship 5 — Polish cluster

**Closes:** Findings J (DC leak), G (debug strings), I (combat onboarding template only — not architectural). Tunes §5.7 (narration continuity) and §5.8 (economic ordering).
**Goal:** Player-visible UX issues from S32 that don't require architectural specs. Single session of small fixes.

### §8.1 Subships

- **5a — Finding J:** drop DC from player-facing directive emit message. Single-line copy change. Server logs DC for audit.
- **5b — Finding G:** replace `[VERIFICATION_ANOMALY]` debug-string-leak in escalation message with operational copy OR drop the message entirely (silent log-only). **Recommend silent.**
- **5c — Finding I template polish:** fix the `"Karrok attempts a {error_message} ."` malformed template in combat-mode adjudicator copy. Replace raw `!init begin` instruction with operational DM prose. Architectural fix (auto-init) waits on F-55 #5.4.
- **5d — §5.7 narration continuity cluster:** prompt-tuning pass on `dm_philosophy.md` for "memorable details should recur intentionally, not compulsively" + body-location continuity invariants. May thin organically after Ship 2 lands; reassess.
- ~~**5e — §5.8 economic ordering**~~ — **DROPPED from Ship 5.** Originally proposed an `economic_outcome_gate` validator. Per §2.3 (validators accumulate; structural removal stronger): a per-domain validator gate is a symptom fix that starts the project on the validator-proliferation slope. The structural fix is **authoritative action resolution pipelines** — `attempt_wager(actor, amount)` validates funds, reserves currency, emits resolution; narration never invents wager success because the engine emits valid outcomes only. That's a v1.x candidate ship of its own ("Action Pipelines"), not a Ship 5 polish item. §5.8 stays filed in S32_FINDINGS as a documented failure mode awaiting Action Pipelines architecture.

### §8.2 Work breakdown

| Session | Scope | Model |
|---------|-------|-------|
| S41 | Four subships in single session. 5a/5b/5c are minutes; 5d is a prompt-tuning experiment with reassessment. | Sonnet medium |

### §8.3 Gate criteria

- Live verify: no DC leak in directive emit, no debug-string leak in escalation, combat onboarding template parses correctly
- §5.7 cluster monitoring continues; reassess at next playtest

### §8.4 What Ship 5 does NOT fix

- Combat onboarding architectural rework (waits on F-55 #5.4)
- Combat-mode auto-init flow (waits on F-55 cluster)
- §5.8 economic ordering (waits on Action Pipelines v1.x)
---

## §9. Doctrine work in this plan

Four doctrine candidates surface across Ships 1-5. If the plan ships clean, three to four of them anchor — substantial doctrinal accretion.

### §9.1 §76 — Recursive hallucination memory loop

**Anchored in Ship 2 spec.** Three project instances clears the bar (S22 #2 chroma contamination, S32 location drift, F-44 chroma bleed pattern).

Proposed wording: *"LLM output → persistent state → retrieval context → future LLM output is a drift-amplification loop. Once any LLM-writable narrative-flavor field is persisted and retrieved, the system becomes self-confirming — past hallucinations become statistical anchors that future inferences treat as canon. Validators cannot break this loop; they slow it. The structural fix is removing the LLM's write authority on the persistent surface, not validating the writes."*

Cross-references: §1a (LLM never decides mechanical outcomes), §17 (single write paths), Doctrine candidate from §9.4 below (validators accumulate).

### §9.2 §65 amendment — bot-as-DM-proxy narrow exception

**Proposed in Ship 3.** Doctrine review required during Ship 3 spec. Lock language: §65 amendment allowing bot-as-DM-proxy `!`-command emission for hydrate/Avrae-sync flow only, scoped narrowly per §17 narrow-exception framing. Companion to §17's existing narrow-exception precedent (`apply_starting_time_seed`).

### §9.3 Doctrine candidate #3 — LLM-writable scalars on engine-state tables

**Filed S32 from Finding A.** Single instance after S32; Ship 2c audit may surface 1+ additional instances via the four-property latent-canon test. Lock anchoring decision after Ship 2c completes. If 2+ additional instances surface, anchors as a sibling to §76 with sharper specificity ("scalars on engine-state tables are particularly dangerous because they project authoritatively into prompt-build paths").

### §9.4 New doctrine candidate — Validators accumulate; structural removal beats validation

**Proposed in plan §2.3, anchor decision deferred.** Sibling to §17 (single write paths) but addresses a different failure mode: §17 says "one writer," this candidate says "the writer must not be the LLM if the field is canonical, and validators cannot substitute for that."

Proposed wording: *"When a field exhibits drift, removing the LLM's write authority is structurally stronger than adding a validator. Four supporting axes: (1) single source of truth; (2) validators accumulate — once added, they multiply, becoming their own maintenance burden; (3) validators are subject to §17's narrow-exception discipline — broad validators are smell; (4) on self-hosted hardware, validators carry compute cost that structural removal does not."*

Single instance after this plan (Ship 5e drop). Anchors when a second project instance surfaces. Likely candidates: F-44 chroma scoping (when shipped, the question "validate retrieval outputs vs scope retrieval inputs" recapitulates this pattern), Action Pipelines v1.x (when shipped, the question "validate economic outcomes vs route them through canonical pipelines" recapitulates).

### §9.5 §1a wording revision deferred

GPT's "renderer not ruler" framing from S32 review is sharper than current §1a wording. **Defer the revision** until after this plan completes — too easy to over-edit doctrine mid-flight. Note as a doctrine-housekeeping candidate post-Ship 5.

---

## §10. Calendar estimate

Assumes Code-and-planner cadence per `WORKING_WITH_CLAUDE.md`. Spec sessions and review sessions can run same-day if Jordan's review is fast; otherwise next-day.

| Session | Calendar day (best case) | Calendar day (slow review) |
|---------|--------------------------|----------------------------|
| S33 (Ship 1 spec + review) | day 1 | day 1-2 |
| S34 (Ship 1 implementation) | day 2 | day 3 |
| S35 (Ship 2 recon + spec + review) | day 3 | day 4-5 |
| S36 (Ship 2a + 2c implementation) | day 4 | day 6 |
| S37 (Ship 2b implementation if needed) | day 5 | day 7 |
| S38 (Ship 3 recon + spec + review) | day 6 | day 8-9 |
| S39 (Ship 3 implementation) | day 7 | day 10 |
| S40 (Ship 4 spec + review + implementation) | day 8 | day 11-12 |
| S40b (Ship 4.5 if slotted at Ship 1 verify) | day 8.5 | day 12.5 |
| S41 (Ship 5 polish cluster) | day 9 | day 13 |

**Best case: 9 days of work** (Ship 4.5 not slotted; v1.x candidate). **Slow case: 13 days.** Add ~0.5 day if Ship 4.5 slots at Ship 1 verify checkpoint.

---

## §11. What this plan does NOT cover

- **F-44 chroma bleed location-scoping** — different channel from Ship 2's write-side fix. Stays v1.x candidate.
- **F-58 stale-footer name parsing** — v1.1 candidate; not blocking play.
- **F-54 stagnation drift** — separate thread; motion-system territory; ships post-multiplayer-fixes.
- **F-55 cluster ships #5.2, #5.3, #5.4** — sequenced after this plan completes; #5.5 (state-sync) ships in Ship 3 above.
- **Track 5 corpus extraction** — background research thread; not affected.
- **15 ChatGPT texture items** (ROADMAP finishes #8) — defer until after Ship 5.
- **Combat Playability Cluster #5.1 live verify** — already pending; can fit between any two sessions of this plan, recommend during S33 part 2 review interval.

---

## §12. Decision points for Jordan before kickoff

These are the "before we start" calls. Recommend a quick session before S33 to lock these:

1. **Ship ordering — Ship 1 (Resolution Binding) vs Ship 2 (Scene State Canon Discipline) first.**

   Three reviewers gave three lenses on this question. Worth surfacing all three rather than collapsing to a single recommendation:

   - **Planner (operational leverage):** Ship 1 first because it collapses Bug 1 Phase 2 as a side effect — ships two things at once. Ship 2 needs a recon pass for `established_details` and `extract_scene_updates` audit; Ship 1 has tighter spec scope.
   - **GPT (failure-mode recoverability):** Ship 2 first because recursive state poisoning is *more fatal* than failed-roll narration. Roll-resolution failures are episodic — each turn is a fresh chance to get it right after Ship 1 lands. State poisoning failures are cumulative — every turn that ships without Ship 2 adds drift to the persistent record, and even after Ship 2 lands, existing campaigns carry contaminated rows.
   - **Gemini (pragmatic development path):** Ship 1 first because broken dice mechanics make the game immediately unplayable for tonight's session. Architecturally Ship 2 is more dangerous; practically a player playing tonight cannot access month three. Restoring player trust unblocks the session that matters today; canon protection unblocks the session that matters in October.

   The axis of disagreement is **episodic-recoverable failure vs cumulative-compounding failure**. Both are real; neither is reducible to the other. The trigger statement settles which axis to optimize for: "the system is unplayable in current state... I don't care if it takes a week, we need to figure this out immediately." Jordan is optimizing for **playability now**, not architectural purity over the long arc.

   **Planner recommendation: Ship 1 first.** The trigger statement names the optimization axis; Ship 1 first follows directly. Ship 2 ships immediately after — calendar gap between them is one session of recon work.

2. **Spec-then-review cadence.** Does each ship get the full three-session cycle, or should some compress? Ship 5 is single-session; Ships 1-4 default to three-session; Ship 4.5 (if slotted) is single-session. Confirm or adjust.
3. **Doctrine review timing.** Anchor §76 in Ship 2 spec, or wait until Ship 2 ships clean? Anchor §65 amendment before Ship 3 implementation, or in Ship 3 implementation? Generally doctrine anchors lock alongside the ship that proves them; pre-locking is rare. **Recommend lock alongside ship.**
4. **Pause-before-resume on existing roadmap.** Combat Playability Cluster #5.1 is awaiting live-verify. Does that verify happen during this plan's calendar, or strictly after? **Recommend during** — #5.1 verify is a 5-step Discord scenario; can fit between any two sessions of this plan.
5. **Pre-multiplayer-fixes playtest?** Should we run another short playtest before S33 to confirm Findings A/H/L are still reproducible (no silent recovery between S32 and now), or trust the S32 evidence? **Recommend trust S32 evidence** — no architectural changes shipped between S32 and now that would have closed any of the three.
6. **Code model selection.** Plan defaults to Opus medium for spec/review work and Opus high for Ship 1 + Ship 3 implementations (load-bearing primitives). Sonnet medium for Ship 2 implementation (templated against Doctrine §59 pattern), Ship 4 implementation, Ship 5 polish. Confirm or adjust per session.
7. **Ship 4.5 decision.** Filed candidate, decision deferred to Ship 1 verify checkpoint. Confirm the criterion (>1 directive-binding ambiguity per session = ship; ≤1 = file v1.x) is the right one.

---

## §13. After this plan — and what this plan actually is

After Ship 5 lands, return to ROADMAP:

- **F-55 #5.4 Resolver becomes next-pick** if not deferred to Combat Playability Cluster sequencing
- **Bug 1 Phase 2 already shipped** as side effect of Ship 1
- **Motion-systems thread (Scene Lifecycle v1)** is the parallel candidate
- **Ship a real friends-playtest** to validate the multiplayer fixes held under play pressure — that playtest's findings inform whether F-55 #5.4 or Scene Lifecycle ships first

The friends-playtest is the gate: if multiplayer feels playable after Ship 5, the plan worked. If new failure modes surface, file them as F-NN candidates and re-prioritize.

### §13.1 What this plan is, framed honestly

The plan reads as "close three architectural leaks plus polish." That framing is correct at the ship-by-ship level. At the architectural level, it is the wrong framing.

What this plan actually is: **completing the project's convergence to AI-assisted deterministic simulation.**

Virgil has been moving toward this destination since Doctrine §1a was anchored in S6. Every ship since then has either (a) reduced LLM authority on a specific surface, (b) added engine-authoritative truth where there was previously LLM-authored truth, or (c) constrained narration to render rather than rule. The first three years of the project were learning the lesson; the last six months have been compounding it. Track 7 #1 promoted advisory directives to binding directives. Track 7 #2 made narration verifiable against state. Bug 3 closed `/travel` location drift. Track 4 #3 made time deterministic.

The S32 multiplayer playtest exposed three remaining seams where the convergence was incomplete. This plan finishes the convergence:

- Ship 1 takes roll resolution out of the LLM's authority (player self-report no longer adjudicates)
- Ship 2 takes scene state out of the LLM's write authority (recursive hallucination memory loop closed at the source)
- Ship 3 takes combat state out of split-brain hybrid authority (Virgil-authoritative-with-Avrae-as-projection partition becomes explicit)
- Ship 4 takes identity resolution out of global fuzzy match (scene-scope-first as the resolution discipline)
- Ship 5 closes the player-visible UX leaks that fall out of the same architectural pattern

After this plan, the engine owns world state, mechanics, entity graphs, action legality, causality, persistence, synchronization. The LLM owns dramatic rendering, dialogue, flavor, emotional framing, scene texture. That partition is what the project has been converging toward; this plan is the last set of steps to reach it on the surfaces that matter for multiplayer.

This framing matters because future ships will face the same question: *should this be LLM-authoritative or engine-authoritative?* The answer is settled. Engine-authoritative on truth, LLM-authoritative on prose. Every ship after this plan inherits that settlement and stops re-litigating it.

---

*End of plan v2.*
