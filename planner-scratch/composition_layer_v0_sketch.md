# Composition Layer v0 — Architectural Sketch

**Status:** v0 sketch — pre-spec. Not §11 decisions. Open architectural questions surfaced for operator review before Phase 1 recon opens.
**Date:** May 13, 2026
**Mandate (Prompt 1):** Composition layer is piece 3 of 3 — scenes anchor to quest acts. Final mandate ship.

---

## 1. What this is

Composition layer v0 introduces **quest acts** as engine-readable narrative phases within a quest's `in-progress` lifecycle, and **scene→act anchoring** as the structural primitive that makes "where are we in the bigger picture" engine-answerable.

Concretely, for campaign 17's farmstead quest (currently a single `dnd_quests` row with `status='in-progress'`), an authored act decomposition might look like:

- Act 1: "Approach the farmstead" — opening phase, characterizing the scene
- Act 2: "Engage the goblins" — combat or social confrontation
- Act 3: "Clear the farmstead, find the survivors" — resolution and consequence

Scenes that play out in the campaign anchor to one of these acts. Scene Lifecycle v1's compression closes a scene; the next scene that opens carries (or transitions) the act anchor. When the operator queries the system or the engine renders narrative context, "where are we in the farmstead quest" returns "Act 2 — Engage the goblins" rather than "in-progress."

**Read B locked.** Per operator decision: acts are skeleton-authored narrative phases within `in-progress`, not 1:1 with quest statuses. Read A (status-as-act) was rejected as architecturally hollow — produces a composition layer that doesn't compose. Read B's granularity is what the mandate's "bigger picture" answer requires.

**Architectural placement.** Sits downstream of Quest Layer v0 (which provides the `dnd_quests` rows acts attach to) and Scene Lifecycle v1 (which provides the scene-boundary primitive acts get anchored across). v0's load-bearing job: turn the existing quest-state machine + scene-compression mechanics into a composition primitive that downstream features (recap on resume, pacing pressure, narrative queries) can read.

**What v0 is NOT.** Not an auto-decomposer (acts are skeleton-authored, not LLM-extracted). Not a quest-arc-spanning-multiple-quests primitive (filed v1.x). Not a beat-tracker (acts are coarser than beats — a single act may contain 5-15 scenes). Not a campaign-arc-tracker (campaigns aren't arcs; quests are — multi-quest arc spans filed v1.x).

---

## 2. What surfaces it extends, what's new

**Reuses (no schema change in scope):**
- `dnd_quests` — quest rows carrying `status='in-progress'` are the only acts-bearing rows at v0. Other statuses don't surface acts (offered = pre-commitment; delivered/failed/abandoned = post-resolution).
- `dnd_scene_state` — scene state carries the act anchor. Single-writer per §17; `set_current_act` mirrors `set_current_location`.
- `dnd_quests_audit` — extends to carry act-transition records, same shape as status-transition records (per Quest Layer v0 audit pattern).
- Active-quest directive (§59 sibling #13 from Quest Layer v0) — extends to render the current act, not just the quest title.
- Scene Lifecycle v1's compression machinery — acts persist across compression; the next scene inherits the act anchor unless transition fires.

**Proposed new:**
- `dnd_quest_acts` table — `id`, `quest_id` (FK to `dnd_quests.id`), `act_index` (1, 2, 3...), `act_title`, `act_description`, `transition_predicate_json` (per-act predicate config for engine-deterministic auxiliary detection), `skeleton_origin`, `created_at`, `updated_at`. Single-writer pattern (`quest_act_upsert`).
- `dnd_scene_state.current_act_id` — FK to `dnd_quest_acts.id`, NULL when no act is active. Mirrors `current_location_id` shape.
- `compute_quest_act_suggester` — engine-deterministic auxiliary predicate that proposes act transitions; routes through `#dm-aside` per §1b pattern (suggester proposes, operator pastes/slashes to approve, engine writes act transition). Same §1b shape as Quest Layer v0.1.
- `compute_composition_directive` — §59 sibling #14, renders current-act context in prompt. Extends or sits alongside `compute_active_quest_directive` per §11.4.
- Skeleton.md authoring extension — quest definitions carry optional act decomposition per §11.6.
- New slash subcommands — `/quest act advance <id>`, `/quest act set <id>`, `/quest act list <quest_id>`. v0 surface; minimal but complete.
- Telemetry primitives — `quest_act_transition:` per-transition, `composition_directive:` per-render, `quest_act_suggester:` per-suggestion fire.

**Not new:**
- No new ChromaDB collection. Acts are structured ledger state, not retrieval surface (§76-aligned).
- No bot→Avrae writes.
- No LLM-decided act transitions (per Oracle pre-frame: act boundaries are engine-decided, structural choice not narrative call).
- No auto-extraction of acts from narration (v1.x territory if observed friction justifies).

---

## 3. Act-transition trigger model — (γ) hybrid canonical-slash + auxiliary suggester

Three candidates per operator's surface:

- **(α) Engine-deterministic predicates only.** Acts auto-advance when authored predicates match (scene count, location entry, NPC interaction, consequence promotion). Operationally light; doctrinal risk if predicate calibration drifts.
- **(β) Operator-driven only.** Acts advance only via `/quest act advance <id>` slash. Maximum operator control; loses the auto-suggester ergonomics that Quest Layer v0.1 demonstrated work cleanly under §1b.
- **(γ) Hybrid — canonical slash + auxiliary suggester.** Operator slash is the canonical deterministic gate; engine-deterministic predicate fires an auxiliary suggester to `#dm-aside` proposing "this looks like an Act 2 → Act 3 transition." Operator approves by slash. Same architectural shape as Quest Layer v0.1's anchored §1b pattern.

**(γ) locked at v0 per operator lean.** Doctrinally compliant (canonical gate is operator slash; auxiliary predicate is suggester-only, never writes), operationally lighter than (β), no calibration drift since predicates are operator-authored in skeleton.md per-act rather than auto-extracted from corpus.

**§1b fourth project instance candidate.** Joins Track 6 #5.1 + S41 NPC State-Sync + Quest Layer v0.1. Fourth-instance anchoring stands cleanly if the suggester→slash gate holds with no calibration-bound validator anywhere (cosine-similarity v0.1 drop precedent applies — keep gates deterministic).

**Predicate authoring shape — §11 decision.** Per-act predicate config lives in `transition_predicate_json` (column on `dnd_quest_acts`). Candidates: (a) structured rule schema (scene_count threshold, location_id match, npc_interaction, consequence_kind), (b) freeform tags operator references (predicate fires when operator-authored hint matches scene-state), (c) no predicate at v0 (suggester only fires when operator pre-flags an act as "next-transition-eligible"). *Lean: (a) at v0 with narrow rule set (scene_count + location_id match only)*, expanded in v0.x once observed friction surfaces.

---

## 4. Scene→act anchor write path

**v0 model:** `dnd_scene_state.current_act_id` is the engine-side scene→act anchor. NULL when no quest's `in-progress` act applies (between quests, during pure exploration, during downtime).

**Anchor write triggers:**
1. **Quest accept** — when `/quest accept <id>` fires (status `offered → in-progress`), engine sets `current_act_id` to Act 1 of that quest if acts exist, NULL otherwise. Same write-path discipline as `set_current_location` on `/travel`.
2. **Act transition** — when `/quest act advance <id>` fires, engine writes new `current_act_id` to next act in sequence. Audit row in `dnd_quests_audit` per Quest Layer v0 pattern.
3. **Operator override** — `/quest act set <id> --act <N>` for non-sequential jumps (e.g., party skipped Act 2 entirely). Audit row carries `set_by='operator_override'` for visibility.
4. **Quest deliver/fail/abandon** — engine sets `current_act_id` to NULL on quest exit.
5. **Scene compression (Scene Lifecycle v1) — anchor persists.** Compression closes a scene; next scene inherits the act anchor. The compression itself does NOT advance the act. This is load-bearing: acts are coarser than scenes (1 act = N scenes typical), so scene-boundary ≠ act-boundary by default.

**`/play` resume seed.** When operator resumes a session via `/play`, the last `current_act_id` from `dnd_scene_state` is the seed. Same as `current_location_id` resume behavior — engine canon persists.

**Multi-quest active state.** If multiple quests are `in-progress` simultaneously, only one `current_act_id` is set on `dnd_scene_state` — the *currently-active* act. Switching between quests' acts requires `/quest act set` or `/quest accept` (re-anchor). Filed forward (§11.5): whether v0 supports concurrent active acts (one per active quest) or single-active-act (current model). Lean single-active-act at v0 — simpler, matches the "where are we in the bigger picture" framing better than a list. Multi-active-act is v1.x.

---

## 5. Composition directive — prompt-render shape

`compute_composition_directive(active_quests, current_act_id, scene_state) → (body, signals)` is §59 sibling #14.

**Body shape (when current_act_id is NOT NULL):**
```
=== CURRENT ACT ===
Quest: Investigate the goblin-ravaged farmstead
Act 2 of 3: Engage the goblins
Description: The party has reached the farmstead and goblin sign is everywhere. 
This act covers the confrontation — combat, negotiation, or stealth approach.
```

Cap-at-one-act (the current). Description rendered verbatim from skeleton-authored text. ~200-300 chars when firing.

**When current_act_id IS NULL:** returns `('', {})`. Below-threshold quiet baseline per Scene Lifecycle v1 §5 precedent — the directive is silent most of the time, by design.

**LLM job:** keep current act in narrative awareness; let scenes reference it when relevant; honor act boundaries as soft pacing pressure (Act 2 narration should support the engage-the-goblins phase, not pre-empt Act 3 by narrating survivors). Forbidden: inventing acts; declaring act transitions; describing future acts as having occurred.

**Position in prompt — §11 decision.** Candidates: (a) extends `compute_active_quest_directive`'s tactical-band block (acts render inside the active-quest block, same position); (b) new sibling directive in tactical band immediately after active-quest directive; (c) higher in prompt as framing (before tactical band, alongside `current_location_label`). *Lean: (a).* Extends existing block with one act-line per active quest; minimal new render surface, prompt-size budget delta minimal (~150 chars). (b) doubles directive emission for related content. (c) loses the tactical-pressure coupling that makes acts useful.

---

## 6. Skeleton.md authoring extension

Acts are skeleton-authored at v0. Skeleton.md gains an optional `### Acts` subsection under each `## Major hooks` entry:

```
## Major hooks

### Investigate the goblin-ravaged farmstead
A farmstead two leagues east of the Old Trade Road has been ravaged by goblins. 
Survivors may yet be inside.

Reward: 50gp + Stoneforge Guild reputation
Offer NPC: Eldrin Stormbow

#### Acts
1. Approach the farmstead
   The party travels to the farmstead, characterizing terrain and approach. 
   Scene count threshold: 2.
2. Engage the goblins
   Combat or social confrontation with the goblin band. 
   Location: farmstead grounds.
3. Clear the farmstead, find the survivors
   Resolution — survivors revealed, payments rendered, scene closes.
   Consequence kind: quest_outcome.
```

**Per-act fields:**
- Required: `act_index`, `act_title`, `act_description`
- Optional: `transition_predicate` — operator-authored hint that engine reads into `transition_predicate_json`

**Quests without acts.** v0 supports quests with no `#### Acts` subsection — those quests have NULL `current_act_id` even when `in-progress`. Backward-compatible with Quest Layer v0's existing skeleton-authored quests; operator opts into acts per quest.

**Re-seed safety.** `/quest seed-skeleton` extends to seed acts. Idempotency rule: re-seed creates missing acts, doesn't duplicate existing acts (match on `quest_id + act_index`). Same orphan-row pattern as Quest Layer v0 (operator-side cleanup via `/quest act delete` for orphans from edited skeleton.md).

---

## 7. Architectural questions for §11 decisions

Surfaced for operator lock before any spec session opens. Leans named where I have them; genuine uncertainty flagged.

1. **Read A vs Read B.** **Locked Read B** per operator pre-decision. Acts are skeleton-authored phases within `in-progress`, not 1:1 with quest statuses. Surfaced here for spec to carry the lock formally; no walk required.

2. **Act-transition trigger model.** **Locked (γ) hybrid** per operator pre-decision. Canonical operator slash + auxiliary engine-deterministic predicate suggester via `#dm-aside`. §1b fourth project instance candidate. Surfaced for spec lock; walk required only if suggester predicate calibration surfaces friction during Phase 1 recon (low probability).

3. **Schema shape — new `dnd_quest_acts` table vs extension to `dnd_quests` JSON column vs scene_state new column only.** *Lean: new `dnd_quest_acts` table.* Acts have per-row state (per-act description, predicate, audit history) that doesn't compress into a JSON column cleanly. Mirrors `dnd_quests` shape (FK to parent, single-writer, audit table). Phase 1 recon confirms no existing acts surface to conflict with.

4. **Composition-directive position.** Three candidates (extend active-quest block / new sibling directive / higher framing). *Lean: extend active-quest block (path a).* Walk only if Phase 1 recon surfaces prompt-position constraints not visible at sketch time.

5. **Concurrent active acts (multi-quest in-progress).** Single-active-act at v0 vs multi-active-act (list). *Lean: single-active-act at v0.* Matches "where are we in the bigger picture" framing; multi-active-act is v1.x candidate if observed friction shows operator wants concurrent act states.

6. **Skeleton.md acts authoring shape.** Structured markdown (proposed §6 shape) vs YAML-block-embedded vs freeform-with-markers. *Lean: structured markdown per §6.* Matches existing skeleton.md authoring patterns (NPCs, locations, hooks all use heading-based structure).

7. **Transition predicate vocabulary at v0.** Narrow rule set (scene_count, location_id) vs full rule set (scene_count + location_id + npc_interaction + consequence_kind) vs no predicates (suggester fires manually). *Lean: narrow rule set (scene_count + location_id only) at v0.* Expanded v0.x once observed friction surfaces; matches the v1-then-v1.x narrowing discipline from Scene Lifecycle's tier-soft and §1.F.c patches.

8. **Audit table — extend `dnd_quests_audit` vs new `dnd_quest_acts_audit`.** *Lean: extend `dnd_quests_audit`.* Acts are tightly coupled to quests; one audit surface preserves the query shape "all changes to quest N." Audit row carries `kind='act_transition'` to distinguish from status transitions.

9. **Suggester fire predicate — every-turn evaluation vs only on Scene Lifecycle compression turn vs only on slash-trigger.** *Lean: only on Scene Lifecycle compression turn.* Compression is the natural narrative-pause where act-transition questions surface. Every-turn evaluation produces directive noise; slash-trigger requires operator to know when to ask. Compression-coupled is the cleanest cadence.

10. **`/play` resume rendering — does composition directive fire on the resume turn?** *Lean: yes.* Resume is the operator's "where are we?" moment by definition; the act anchor is exactly what answers it. Same as `current_location_label` rendering on resume.

11. **Composition-layer-of-composition-layer forward compatibility — silent.** Per discipline note: v0 schema does NOT pre-couple emergent-act-detection (LLM-extracted acts from narration), quest-arc-spanning-multiple-quests, or beat-tracker primitives. Composition v1.x will surface its own schema needs.

12. **§1a/§1b scrutiny on auxiliary suggester.** Same shape as Quest Layer v0.1's §11.12 walk. *Lean: §1b fourth project instance clean.* Canonical gate is operator slash; auxiliary predicate is suggester-only with deterministic rule-match (not calibration-bound). Expected clean per v0.1 precedent.

---

## 8. Operational warnings for Phase 1 recon

**Existing `current_act_id`-like surface audit.** Phase 1 must inventory: does `dnd_scene_state` already have a column resembling an act anchor (`current_arc_id`, `current_phase`, etc.)? If so, what schema, what write paths, what render surfaces. v0 drafts against actual surface, not against the mandate alone. Per Quest Layer v0 precedent — R4 surfaced campaign 17 had zero `dnd_quests` rows despite three skeleton hooks, which changed the architectural shape.

**Prompt-size budget.** Per Scene Lifecycle v1 + Quest Layer v0 baselines (~25,400 chars / ~5,640 directives mean post-ship), composition directive adds ~150-300 chars when firing. Budget-safe at fire rate, but composition is the mandate's third architectural piece — the three mandates together pressure prompt-size upward. Phase 1 should re-baseline post-Quest-Layer-v0 live numbers; composition delta measured against this floor.

**Skeleton.md re-authoring workflow.** Acts are operator-authored in skeleton.md; the operator workflow for adding acts to existing skeleton-authored quests should be considered at spec time. Edit-skeleton → re-seed → orphan-row-cleanup is the established Quest Layer v0 pattern. Phase 1 recon confirms `/quest seed-skeleton` extension shape preserves this.

---

## 9. What this sketch does NOT do

- Lock §11 decisions. Spec doc handles, with §11.1 and §11.2 carrying operator pre-decisions forward.
- Address emergent-act-detection (LLM-extracted acts from narration). v1.x territory.
- Address quest-arc-spanning-multiple-quests ("the Stoneforge campaign arc"). v1.x territory.
- Address beat-tracker primitives. Composition layer operates at act granularity, not beat.
- Survey existing scene-state or quest schema for act-adjacent fields. Phase 1 recon.
- Address auto-decompose (engine proposes act structure given a quest description). v1.x.
- Address composition-layer queries beyond the prompt-render surface (operator-facing "show me where each quest stands" command). v1.x candidate.

---

## 10. Next move

Path A three-session cadence: spec → review → implement. Phase 1 recon scope:

1. Existing `dnd_scene_state` schema audit — any act-adjacent columns? Any existing act-anchor surface?
2. Existing `dnd_quests` schema audit (post-v0/v0.1) — confirm no act-related columns landed in Quest Layer v0 that conflict with proposed v0 schema
3. Skeleton.md current-state audit — campaign 17's three skeleton-authored quests; do they already carry act-decomposition (even informally)?
4. Active-quest directive render surface audit — confirm extension path (a) is structurally clean for composition directive
5. Prompt-size baseline re-measurement post-Quest-Layer-v0 live
6. Scene Lifecycle v1 compression coupling — confirm compression machinery preserves `current_act_id` across compression turns (it should by default since acts live on `dnd_scene_state` and compression doesn't write that column; verify)

Phase 2 walks §11.3 through §11.12 with operator (§11.1, §11.2 carry locked pre-decisions). Phase 3 ships locked spec.

If shape passes review, Phase 1 dispatch follows. If shape doesn't pass, rework cheap — sketch is the artifact.
