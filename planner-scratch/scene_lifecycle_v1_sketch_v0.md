# Scene Lifecycle v1 — Architectural Sketch (v0)

**Status:** v0 sketch — pre-spec. Not §11 decisions. Open architectural questions surfaced for operator review before any spec session opens.
**Date:** May 13, 2026
**Mandate (Prompt 1):** DM-initiated compression directive. First of three architectural pieces; quest layer follows, then composition layer.

---

## 1. What this is

Scene Lifecycle v1 is the operator-facing surface for *"this scene closes — render the boundary and move on."* It fills the scene-closure space between Avrae rest events (`!lr` / `!sr`) and `/travel`, which already cover the two heaviest compression shapes in the corpus (CC OVERNIGHT_REST at 39.2%, the travel subset of TEMPORAL_MONTAGE at part of 26.0%).

The corpus says non-travel, non-rest scene closures are real and frequent — LOCATION_DEPARTURE 18.9%, NPC_DEPARTURE 9.3%, INVESTIGATIVE_CLOSURE 3.6%, SCENE_CUT 2.7%, plus the non-travel portion of TEMPORAL_MONTAGE. Combined: roughly a third of Matt's compressions across CRD3. v1 covers the operator-initiated form of these.

**The LLM never decides whether to compress.** That's a §1a binding-decision — compression is a structural choice about scene state, not a narrative call. The operator types a command; the engine runs §78-shaped state-reset; the LLM renders the atmospheric closeout if there's narratable content, or the engine emits a deterministic boundary marker if there isn't (§78.6 render-vs-marker).

---

## 2. What surfaces it extends, what's new

**Reuses (no schema change):**
- `dnd_scene_state.mode` — unchanged. v1 fires in exploration/social only (see §6 question 6).
- `dnd_scene_state.current_location_id` — may or may not change at compression time (§6 question 7).
- `dnd_scene_state.last_player_action`, `last_dm_response`, `dnd_campaigns.current_scene` — the three rolling narrative buffers. v1 resets these via the existing S45 single-writer.
- `dnd_time_advancements` audit log — v1 does NOT advance time directly; `/travel`, `!lr`, `!sr`, `/advance` remain the four locked sources per §17 narrow-exception (§6 question 7).

**Proposed new:**
- Slash command — likely `/scene compress` shape, signature open (§6 question 1).
- One telemetry primitive: `scene_compressed: campaign={N} type={...} marker_or_render={marker|render} buffers_reset={1}` — fold into PLAYTEST_OBSERVATION_FRAMEWORK §5.2 alongside the S48–S50 primitives at next framework touch.
- Possibly one new column on `dnd_scene_state` (`last_compression_at`) for an anti-staleness signal analogous to S51's Day + Time of day fold. Currently leaning defer (§6 question 8).

**Not new:**
- No new table. No new ChromaDB collection. No NPC- or location-canon mutation triggered by compression.

---

## 3. The directive shape

Compression as Virgil sees it is a **two-part operation**: the state-reset (deterministic Python) and the closeout (LLM render or deterministic marker, per §78.6).

**State-reset is not a directive — it's a slash-command handler** that runs the §78 four-layer sequence:

1. **Mechanical state cleanup** — minimal for non-combat boundaries. Probably no-op at v1 (no per-scene mechanical state currently tracked outside combat).
2. **Narrative buffer reset** — invoke the S45 helper or a generalized sibling (§6 question 5).
3. **Transitional-window silence** — turn-gate considerations during the boundary dispatch. Likely simpler than combat-init-setup because no `active_turn`-not-set ambiguity exists outside combat.
4. **Boundary atmospheric closeout** — dispatch a single narration call, structurally mirroring S45's COMBAT_END dispatch (separate `_dm_respond_and_post`, not a directive piggybacking on the next normal turn).

**Closeout dispatch** is where the §59 pure-function sibling pattern kicks in:

```
compute_scene_closeout_directive(
    compression_type,     # taxonomy TBD per §6 question 2
    scene_state,          # for location_label, day_phase, mode
    beat_counter,         # per-scene narratable-beat count (§78.6 predicate)
    bound_pc_names,
    ...
) → (body, signals)
```

`body` is the prompt block (`=== SCENE CLOSEOUT ===` framing + §77 atmospheric-continuity invariants verbatim). `signals` carries `{fired, marker_or_render, type, beats}` for telemetry. Soft-fail at call site.

**LLM job:** render atmospheric closeout per §77 — describe the scene's fade-out, the moment passing, hand back implicit agency to the player. Forbidden: invented NPCs, mechanical-outcome inference, next-scene authoring, anticipating the next location or beat.

**Engine job:** branch per §78.6 — `beats >= 1` during the closing scene → dispatch LLM render with the framing block; `beats == 0` → emit deterministic marker (`"The scene draws to a close. The moment passes."` or similar, exact wording open). LLM bypassed entirely in the marker branch.

This is the 11th §59 sibling. Pattern is mature.

---

## 4. Where it sits relative to §78

Two reads, operator + Oracle call. Planner frames cleanly without leading the lean.

**Read A — §78-shaped pattern-reuse, not fourth instance.** §78.5's three anchored instances all involve external boundary signals: mode-flag flip driven by Avrae-announced events (`!init end` × 2 substrates, `!lr`/`!sr` × 1). Scene Lifecycle v1 is DM-elected with no external trigger — operator types a slash command, no upstream system announces a boundary. Structurally that's a different shape. Anchoring v1 as the fourth instance stretches "boundary" to "any state-reset surface regardless of trigger origin," which dilutes §78's original framing as Avrae-event-coupled state-reset. Under this read, v1 reuses the four-layer pattern as architectural template without extending the doctrine. §78.5's fourth-instance-promotion check stays open for a future case with a non-Avrae *external* boundary event.

**Read B — fourth instance, §78.5's intent generalizes past Avrae coupling.** §78.5's locked text reads "substrate-and-boundary-agnostic application" and names "any other mode-transition surface" as the candidate space. Read literally, that's permissive enough to cover DM-elected boundaries that exhibit the same state-leak failure mode — narrative buffers carrying prior-scene content into the next scene. The failure mode is what §78 prevents; trigger origin (Avrae vs operator) is incidental to that prevention. Under this read, v1 is the fourth instance and operator-elected triggering is a new surface variant of the same doctrine.

Either read produces the same v1 implementation — the four-layer machinery applies. The difference is doctrinal accounting: whether v1 anchors as the fourth project instance or stays at three pending a non-Avrae external boundary case. Flagged as §11 (§6 question 3).

§78.6 (layer-4 render-vs-marker) applies unmodified — content-conditioned predicate, branched at dispatch time, deterministic marker for 0-beat scenes.

---

## 5. The 86% quiet baseline

X2 in the cross-extractor findings: 86% of CC scene-exits are followed by 30+ turns of zero extractor signal. The pipeline doesn't see them not because of a gap — what fills those 30 turns (Matt-narrated frame-set, player turns, NPC dialogue) isn't extractor-targeted.

**Operational consequence for v1:** the directive does *nothing* after dispatching the closeout. No next-scene authoring. No coordination with quest firings, time mentions, or anything else (X7 null result: events don't cluster at 15-turn scale; designing for coordination is a design error against the corpus).

The directive's whole job is the boundary. The next turn proceeds via the normal `dm_respond` path; the scene rebuilds organically through player input + LLM response. This is exactly the post-combat-exit shape under §78 today; v1 generalizes it to non-Avrae boundaries.

For the 14% that does fire something within 30 turns (X2's "compression begets compression" — 10.7% being more compression-flavored events): the directive doesn't try to anticipate. If the operator triggers another compression shortly after the first, it runs through the same surface independently. No coupling.

For the 10.6% of CC zero-compression episodes (cluster with high-tension content — C1E114 finale, C1E076, C1E108): Scene Lifecycle v1 should *not* nudge the operator toward more compression. The corpus baseline is ~3 compressions/episode with high variance and legitimate zero-compression episodes for climactic-hold content. **No auto-suggester at v1.** Pure operator-initiated.

---

## 6. Architectural questions for §11 decisions

Surfaced for operator lock before any spec session opens. Leans named where I have them.

1. **Operator surface shape.** `/scene compress [type]` slash command with a type enum? `/scene compress` with optional free-text intent? Two commands? *No confident lean.* Trade: enum forces consistency but locks taxonomy early; free-text matches Matt's varied vocabulary but loses telemetry shape.

2. **Compression-type taxonomy at v1.** Adopt CC's six minus OVERNIGHT_REST and TEMPORAL_MONTAGE-travel-subset? Or generic "scene closes" with no type, type added v1.x if friction surfaces? *Lean: generic at v1.* Trade: type-aware closeout framing is richer, but CC's category boundaries are precision-brittle (OVERNIGHT_REST polysemy at 48.6% strict, LOCATION_DEPARTURE micro-motion FPs at 54.5%). Inheriting that brittleness into v1 prompt-framing seems premature.

3. **§78 instance vs §78-shaped.** Per §4 above. *Lean: §78 fourth instance.* Doctrinal call — Oracle territory.

4. **Layer-4 content predicate (or sidestep).** §78.6 used BLOODIED + DOWNED beats as combat-side predicate. Two paths:
   - (a) Define an automatic predicate analog for non-combat scenes — candidates: turn-count since scene-open, distinct PC actions in scene, presence of substantive LLM narration vs pure list-of-rolls, NPC dialogue events.
   - (b) Operator decides marker-vs-render explicitly at command time — `/scene compress` defaults to render, `/scene compress --quiet` (or `/scene cut` as a sibling command) emits the deterministic marker.
   
   *Lean: path (b) at v1.* Sidesteps the predicate-definition problem; predicate question reopens if/when auto-firing surfaces as a v1.x candidate. §78.6's combat-side predicate took a real beat-tracking primitive to nail; deferring that work behind operator agency is the lighter v1 and §1a-aligned (operator decides structural state, not LLM).

5. **Buffer-reset writer.** Generalize `reset_narrative_buffers_on_combat_exit` to a `reset_narrative_buffers(scope, reason)` writer? Or fork `reset_narrative_buffers_on_scene_compression`? *Genuine uncertainty.* Trade: generalize is cleaner under §17, but the rest-event combat-mode-branch deferral from S49 suggests reset semantics may diverge per surface; if they diverge, the fork pays off.

6. **Mode coupling.** v1 fires in exploration/social only? Or also during combat ("compress to morning even though there are 2 goblins still in init")? *Lean: exploration/social only at v1.* Combat-mode scene compression is a much deeper architectural question with no corpus signal coverage; file forward.

7. **Time-progression coupling.** Does any compression type call `advance_time()` directly? If yes, with what `source` enum value? (Current §17 narrow-exception lock has four sources: `travel`, `rest_long`, `rest_short`, `advance`. A fifth requires spec amendment.) *Lean: v1 does NOT auto-advance time.* Operator types `/advance` separately when needed; auto-coupling is filed v1.x once observed friction justifies the spec amendment.

8. **§76 read-side anti-staleness signal.** S51 added Day + Time of day to SCENE STATE every turn. Should v1 add an "elapsed since last scene compression" signal for similar reasons? *Lean: defer.* The symptom that motivated S51 (multi-turn time drift) doesn't have an obvious analog for scene compression; surfacing it pre-emptively is the planner-momentum filing pattern WORKING_WITH_CLAUDE warns against.

9. **Telemetry shape.** Single `scene_compressed:` log line? Or split per §78 layer (S45/S48/S49's pattern)? *Lean: single line at v1, per-layer if drift surfaces.* The §59 sibling pattern favors single-line; per-layer fires only on the boundary-event surface (S45 had three because three distinct surfaces, not three layers).

10. **Composition-layer forward compatibility.** The third architectural piece anchors scenes to quest acts. Does v1 reserve a `current_act_id` field on `dnd_scene_state` for the composition layer? *Lean: silent.* Premature coupling. Composition spec will surface its own schema needs.

---

## 7. Operational warnings for Phase 1 recon

Two operational warnings the spec session's Phase 1 recon should carry. Neither is a §11 lock — both are discipline notes that shape what recon needs to produce.

**§17 amendment-pressure on the buffer-reset writer.** §6 question 5 (generalize vs fork the S45 buffer-reset helper) is exactly the §17 trap: branching inside an existing single-writer is fine; forking a new sibling writer that touches the same three buffer fields (`dnd_campaigns.current_scene`, `dnd_scene_state.last_dm_response`, `dnd_scene_state.last_player_action`) is a §17 violation unless framed as a narrow exception with explicit guards (S27's `apply_starting_time_seed` precedent — one-shot, idempotent, separate audit channel). Default should be generalize: extend `reset_narrative_buffers_on_combat_exit` to `reset_narrative_buffers(scope, reason)`, keep single writer. Fork only if a concrete invariant divergence between combat-exit and scene-compression reset semantics surfaces during recon — and if so, the fork ships with narrow-exception framing in the spec, not as a silent sibling. Phase 1 recon should produce the audit that decides which path the spec proposes.

**Prompt-size budget.** Bloat threshold (~18k chars per WHY.md S18) and empty-narration ceiling (~26k per S26 ROADMAP note) are real failure surfaces. The closeout block is small in isolation (500–700 chars plausible) but Scene Lifecycle v1 is the first of three architectural pieces in the mandate — quest layer adds active-quest rendering (NPC-voice routing per LR's 36.8% finding), composition layer adds act-anchoring metadata. Three shipped sequentially without measurement will accumulate. v1 should ship with `prompt_size:` telemetry inspection on closeout-fire turns and baseline comparison against pre-ship sizes. If closeout pushes typical exploration prompts past ~22k chars, shrink the framing; don't balloon and ship. Phase 1 recon should produce baseline prompt-size measurements on current exploration turns so the v1 delta is measurable at verify.

---

## 8. What this sketch does NOT do

- Lock §11 decisions. Those go in the spec doc, after this sketch is reviewed and the spec session opens.
- Propose implementation. That's the implementation prompt, three sessions out per Path A.
- Address quest layer or composition layer beyond §6 question 10 on forward compatibility.
- Pre-commit to type taxonomy or operator-surface shape.
- Address combat-mode scene compression. Filed forward; corpus signal doesn't cover it and the mode-coupling question alone warrants its own scope.
- Survey the existing slash-command surface, audit `reset_narrative_buffers_on_combat_exit`'s shape, or grep CC taxonomy categories against Avrae/`travel` coverage. Those are spec-session-Phase-1 recon, not v0 sketch work.

---

## 9. Next move if shape passes review

Path A three-session cadence: spec → review → implement. Spec session opens with Phase 1 recon — grep the existing slash-command surface, audit S45 buffer-reset for generalization, confirm which CC categories aren't already covered, verify §78.5's text supports the fourth-instance reading. Phase 2 walks §11 decisions for operator lock. Phase 3 produces locked spec doc + open-question parking lot.

If shape doesn't pass review, the rework is cheap — the sketch is the artifact, not the spec.
