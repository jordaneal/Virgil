# COMPOSITION_LAYER_V0_SPEC.md

**Status:** LOCKED (v0.x patched S61, May 13 2026). All 13 decisions (12 §11 + §11.13 NEW) locked per `COMPOSITION_LAYER_V0_REVIEW.md`. Three amendments applied at lock + one v0.x UX patch:

**S61 v0.x UX patch (post-live-verify operator feedback):**
- Status enum canonical value flipped: `delivered` → `completed` (operator preference for plain-English; `delivered` retained as alias mapping to canonical). Engine helper name `quest_deliver` preserved for code-side back-compat. Engine init runs additive `UPDATE dnd_quests SET status='completed' WHERE status='delivered'` migration alongside the existing `active→in-progress` migration.
- Slash surface trimmed from 14 commands to 9. Dropped: `/quest offer` (manual suggester fire unused — auto-fire via compression-coupled path covers practical surface), `/quest deliver` (canonical is now `/quest complete`), `/quest act set` (non-sequential jump unused), `/quest act list` (use `/quest list` then inspect via SQL or composition directive), `/quest act delete` (rare orphan cleanup; sqlite-direct available). Renamed: `/quest seed-skeleton` → `/quest seed`.
- Patch driver: operator-feedback confusion + "extra commands we don't use" / "naming is redundant just shorten it." No architectural change; UX trim only.

**Original lock amendments (S60):**

1. **§11.13 ON DELETE CASCADE on `dnd_quest_acts.quest_id`** — schema-level FK enforcement; parent quest deletion auto-removes child acts. Matches Quest Layer v0 Finding 3 orphan-cleanup workflow.
2. **§11.13 `PRAGMA foreign_keys=ON` verified at engine init** — SQLite requires explicit PRAGMA per connection for FK enforcement. Engine init confirms ON and logs the verification.
3. **§11.12 footnote observation in DOCTRINE §1b** — running-list footnote (not formal sub-anchor) noting that four §1b instances now share the deterministic-validator shape; calibration-bound validators (cosine-similarity) have not anchored cleanly (Reading-3 dropped at Quest Layer v0.1 S57). Surfacing-only; doctrine sub-pattern not formalized.

**Session:** S58 Path A Phase 1 spec drafting against `planner-scratch/composition_layer_v0_sketch.md` (May 13, 2026)
**Ship:** Motion Systems Track — Composition Layer v0 (piece 3 of 3 in operator mandate: Scene Lifecycle v1 ✅ + Quest Layer v0 ✅ + Composition Layer = this spec)
**Addresses:** "Where are we in the bigger picture?" — the engine-answerable narrative-position primitive. Quest Layer surfaces active quests; Composition surfaces *which phase of which quest the party is in*.
**Precedent specs:** `QUEST_LAYER_V0_SPEC.md` LOCKED + v0.1 patch (S56/S57), `SCENE_LIFECYCLE_V1_SPEC.md` LOCKED + v1.x patch (S52/S53).

---

## §1. Proposed decisions

§1.A and §1.B carry **locked pre-decisions** per operator framing. Remaining §1 items are Code's recommendations for Session 2 review.

---

### §1.A — Read B locked: acts are skeleton-authored phases within `in-progress`, not 1:1 with quest statuses

**LOCKED per operator pre-decision.** Acts are narrative phases inside a quest's `status='in-progress'` lifecycle. A quest with three acts has all three sitting under one `in-progress` status row in `dnd_quests`. Read A (status-as-act) was rejected pre-spec — produces a composition layer that doesn't actually compose (one act per quest is degenerate).

**Granularity:** an act covers 5-15 scenes typical; multiple compressions can fire within a single act; act transitions are coarser than scene transitions.

---

### §1.B — (γ) hybrid trigger model locked: canonical slash + auxiliary engine-deterministic suggester

**LOCKED per operator pre-decision.** Act transitions write through one of:
- `/quest act advance <id>` — canonical operator slash, deterministic gate
- `/quest act set <id> --act <N>` — operator override for non-sequential jumps
- `compute_quest_act_suggester` — auxiliary §1b suggester via `#dm-aside`, engine-deterministic predicate (NOT calibration-bound). Operator approves by slash.

**§1b fourth project instance candidate** — joins Track 6 #5.1 SRD suggester (S26), S41 NPC State-Sync (post-pivot), Quest Layer v0.1 (post-S57 patch, Reading-2 canonical-slash-only with cosine-similarity dropped). Composition Layer v0 anchors as fourth instance if the suggester→slash gate holds with deterministic-only validators throughout (cosine-similarity precedent applies — keep gates deterministic).

---

### §1.C — `dnd_quest_acts` new table, NOT extension to `dnd_quests`

**Recommendation: new `dnd_quest_acts` table with FK to `dnd_quests.id`.**

Acts have per-row state (`act_title`, `act_description`, `transition_predicate_json`, audit history) that doesn't compress into a JSON column on the parent quest cleanly. R2 confirms `dnd_quests` post-v0 has 15 columns; adding nested act data into the existing row (as JSON or as positional columns) would either bloat the row or require schema gymnastics. The new-table shape mirrors `dnd_quests` (FK to parent, single-writer, shared audit table).

**Reasoning:** Same reasoning Quest Layer v0 used for its own table (vs extending `dnd_consequences` with `kind='quest_offer'`). State machines with distinct lifecycles deserve distinct tables. Acts have their own lifecycle (transition history, ordering, predicate config); separating from `dnd_quests` keeps both clean.

---

### §1.D — `dnd_scene_state.current_act_id` additive column; single writer `set_current_act` mirrors `set_current_location`

**Recommendation: add `current_act_id INTEGER` to `dnd_scene_state` (NULLable, default NULL). FK semantically to `dnd_quest_acts.id`. Single writer `set_current_act(campaign_id, act_id) → bool` mirrors `set_current_location`.**

R1 confirms `dnd_scene_state` has zero act-adjacent columns. Clean additive. R7 confirms the single-writer pattern folds into the established `set_current_location` shape — no §17 amendment, no new sibling pattern. Writer validates `act_id` exists AND parent `quest_id` is in the same campaign (two-step FK validation per §16 engine-defends-invariants).

NULL semantics: no quest's `in-progress` act applies right now. Default when between quests, during pure exploration, during downtime.

---

### §1.E — Anchor persists across Scene Lifecycle v1 compression

**Recommendation: `current_act_id` is NOT touched by Scene Lifecycle compression machinery. Acts persist across scene compression by construction.**

R6 confirms compression's write surface is in-memory only (`_scene_stale_turns` counter); compression's directive injection prompts the LLM but does NOT write any `dnd_scene_state` column. `reset_narrative_buffers_on_combat_exit` writes only the three rolling narrative buffers (`current_scene`, `last_dm_response`, `last_player_action`) — none of `dnd_scene_state`'s structural columns. **Composition's act anchor is preserved by structural inheritance**; no special preservation code needed.

This is load-bearing: acts are coarser than scenes (1 act = 5-15 scenes typical), so scene-boundary ≠ act-boundary by default. Compression closes a scene; next scene inherits the act anchor unless explicit `/quest act advance` or `/quest act set` fires.

---

### §1.F — `compute_quest_act_suggester` is the 14th §59 sibling (auxiliary suggester)

**Recommendation: 14th §59 instance — pure function reading `(scene_state, current_act, candidate_next_act, predicate_signals) → (proposal | None, signals)`. No DB writes. Always-fire telemetry.**

Predicate signals derive from `dnd_quest_acts.transition_predicate_json`. v0 narrow predicate vocabulary (scene_count, location_id match per §1.K lean) — engine reads scene_state + dnd_scene_history (or equivalent — see §11 walks) and computes whether the predicate matches.

On predicate match: emits proposal dict `{quest_id, current_act_index, proposed_next_act_index, next_act_title, predicate_reason}`. Caller (bot side) posts to `#dm-aside` as suggester card; operator approves via `/quest act advance <id>` slash.

---

### §1.G — `compute_composition_directive` is the 15th §59 sibling (active-quest directive extension or sibling)

**Recommendation: 15th §59 instance, extending the active-quest directive block per sketch §11.4 lean (a).**

Per R4 evidence: the existing active-quest directive (`compute_active_quest_directive`, 13th sibling) renders at tactical band with `=== ACTIVE QUESTS (AUTHORITATIVE — outstanding commitments) ===` framing. Extension path: for each in-progress quest with a current act, append an `Act N of M: <title>` line below the quest line. Body shape per spec §5 (sketch reference) — ~150-200 chars added per act-bearing quest.

Implementation choice (Session 3 detail): extend `compute_active_quest_directive` to take the current_act_id + quest_act dict in its signature; OR build `compute_composition_directive` as a sibling and concatenate at the call site. The §11.4 lean is "single block, single call" — extend the existing function. Decision deferred to implementation phase; either path is doctrinally equivalent.

---

### §1.H — Audit extension: `dnd_quests_audit` extends with act-transition source values + new column `to_act_index`

**Recommendation: extend the existing `dnd_quests_audit` table (one audit surface per quest preserves query shape "all changes to quest N"). Add `to_act_index INTEGER` nullable column. Use existing `source` field with new enum values: `act_advance`, `act_set`, `act_override`, `act_propose` (suggester-card-posted).**

R2b shows `dnd_quests_audit` has 10 columns including `from_status`, `to_status`, `source`, `detail`, `actor_npc_id`, `turn_counter`. Sketch §11.8 leans extend over new audit table. R2b confirms the schema is additive-friendly. One new column (`to_act_index`) + new `source` enum values covers act transitions without introducing a parallel audit surface.

**Reasoning:** Acts are tightly coupled to quests. One audit surface preserves the query shape ("all changes to quest N"). Source enum is the discriminator between status-transition and act-transition rows. `from_status` / `to_status` stay NULL on act-transition rows (they're status writers); `to_act_index` carries the act number on act-transition rows.

---

### §1.I — Skeleton.md authoring extension: optional `#### Acts` subsection under each `### Quest hook`

**Recommendation: extend skeleton.md authoring per sketch §6 shape. `## Major hooks` flat-bullet format remains valid; operator opts INTO act decomposition by promoting a hook to an `### <Quest title>` heading with optional `#### Acts` subsection.**

R3 confirms campaign 17's three skeleton hooks are flat one-line bullets with zero act decomposition. v0 introduces the structure cleanly — no migration of implicit structure required. The authoring extension is:

```markdown
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
```

**Backward-compat:** Quest Layer v0's flat-bullet hooks remain valid. Quests without acts have NULL `current_act_id` even when `in-progress`. Operator promotes hook-to-quest-with-acts per quest; not all-or-nothing.

---

### §1.J — Single-active-act at v0 (not multi-active)

**Recommendation: `dnd_scene_state.current_act_id` is a single column, not a list. Concurrent in-progress quests don't carry concurrent acts; only one is "current."**

Per sketch §4 framing. Multi-active-act (one act per active quest) is filed §12.x candidate if observed friction shows operator wants concurrent act states. v0 ships single-active-act because it matches the "where are we in the bigger picture" framing — the answer is one act-string, not a list.

Operator switches between in-progress quests' acts via `/quest act set <new_quest_id>` or `/quest accept` (re-anchor to new quest's Act 1).

---

### §1.K — Predicate vocabulary at v0: narrow rule set (scene_count + location_id) only

**Recommendation: `transition_predicate_json` carries a narrow rule set at v0 — `scene_count_threshold INTEGER`, `location_id INTEGER`. Engine reads these; suggester fires when predicate matches.**

Sketch §11.7 lean (a). Expansion (npc_interaction, consequence_kind, custom rules) is v0.x once observed friction surfaces. Matches the v1-then-v1.x narrowing discipline from Scene Lifecycle's tier-soft and §1.F.c patches (S52 + S53).

**JSON shape:**
```json
{"scene_count_threshold": 2, "location_id": 17}
```

Either field optional; both NULL = no auto-suggester, operator-only.

---

### §1.L — `/play` resume renders the composition directive

**Recommendation: yes. Resume turn renders the composition directive same as `current_location_label`.**

Sketch §11.10. Resume is the operator's "where are we?" moment by definition; the act anchor is exactly what answers it. Same render path as `current_location_id` resume seed.

---

### §1.M — Composition forward-compatibility silent (no pre-coupling for v1.x candidates)

**Recommendation: v0 schema does NOT pre-couple emergent-act-detection (LLM-extracted acts), quest-arc-spanning-multiple-quests, or beat-tracker primitives.**

Sketch §11.11 + same discipline Quest Layer v0 followed re composition. Future v1.x ships surface their own schema needs when their specs open.

---

## §2. Problem statement

**Mandate framing (operator, May 2026):** composition layer is piece 3 of 3 — Scene Lifecycle v1 closed scene immortality (F-54 stagnation drift, S52); Quest Layer v0 surfaced quests as `dnd_quests` rows with NPC-voiced offer suggesters (S56/S57); Composition layer closes "where are we in the bigger picture" by introducing acts as engine-readable narrative phases within `in-progress` quests.

**The gap composition addresses.** Quest Layer v0 surfaces what the party is working on (1+ quests at `status='in-progress'`). It doesn't surface *where in that work the party is*. For a 3-act quest like "Investigate the farmstead" (Act 1 approach → Act 2 engage → Act 3 resolve), Quest Layer renders only the title and reward summary. The LLM has no engine-side signal for "we're in the middle act, the combat phase, don't pre-empt the resolution by narrating survivors."

**Why acts are the right granularity.** Scenes (5-15 per act) are too fine — operator doesn't want to author per-scene structure. Quest statuses (offered/in-progress/delivered/failed/abandoned) are too coarse — one row carries the entire mid-game span. Acts (3-5 typical per quest) match how DMs actually structure quests: opening / engagement / resolution. The granularity is what the mandate's "bigger picture" answer requires.

**LLM job per act.** Honor act boundaries as soft pacing pressure. Act 2 narration should support the engage-the-goblins phase without pre-empting Act 3 (don't narrate survivors during combat). Act boundaries are engine-decided (operator slash or auxiliary suggester); LLM never writes act state.

**Architectural placement.** Sits downstream of Quest Layer (provides the rows acts attach to) and Scene Lifecycle (provides the scene boundary primitive acts get anchored across). Composition reads from both; writes to its own table (`dnd_quest_acts`) + one new column on `dnd_scene_state` (`current_act_id`).

---

## §3. Architectural shape

Composition Layer v0 introduces **two §59 pure-function-in-orchestration siblings** — 14th and 15th instances after Quest Layer v0's 12th and 13th.

```
dnd_orchestration.py:
  compute_quest_act_suggester(
      scene_state: dict,
      current_act: dict | None,        # row from dnd_quest_acts at current_act_id, or None
      candidate_next_act: dict | None, # next act in sequence, or None at last act
      scene_count_at_current_act: int, # derived from scene-history at current act
      current_location_id: int | None,
  ) → (proposal: dict | None, signals: dict)

  compute_composition_directive(
      active_quests: list,            # rows where status='in-progress'
      current_act: dict | None,        # row from dnd_quest_acts at current_act_id
  ) → (body: str, signals: dict)
```

**Suggester call site (`discord_dnd_bot.py`):** fires only on Scene Lifecycle compression turn per §11.9 lean (sketch). Compression is the natural narrative-pause where act-transition questions surface. If proposal returned, dispatches `#dm-aside` card via `_post_dm_aside`. Suggester does NOT write `dnd_quest_acts` or `dnd_scene_state`. Always-fire log: `quest_act_suggester: campaign=N quest_id=N current_act=N proposed_act=N fired=0|1 reason=...`.

**Directive call site (`dnd_engine.py:dm_respond`):** AFTER active-quest directive (extends the same `=== ACTIVE QUESTS ===` block per §1.G). Always-fire log: `composition_directive: campaign=N current_act=N act_count=N fired=0|1 chars=N`.

**State writes** are §17-disciplined single-writer helpers extending the existing pattern:
- `quest_act_upsert(campaign_id, quest_id, act_index, title, description, predicate_json, skeleton_origin) → int` — upsert by `(quest_id, act_index)` key. Inserts new act or updates existing in place. Mirrors `npc_upsert` shape.
- `quest_act_advance(campaign_id, quest_id, current_turn) → dict | None` — fires from `/quest act advance` slash. Reads scene_state.current_act_id, computes next act in sequence, writes `current_act_id` via `set_current_act` + audit row in `dnd_quests_audit` with `source='act_advance'`, `to_act_index=N+1`. Returns next-act dict on success.
- `quest_act_set(campaign_id, quest_id, act_index, source='act_set') → bool` — fires from `/quest act set` slash. Non-sequential jump. Writes `current_act_id` + audit row with `source='act_set'` or `'act_override'`. Returns bool.
- `set_current_act(campaign_id, act_id | None) → bool` — single writer for `dnd_scene_state.current_act_id`. Mirrors `set_current_location`. Validates FK existence (act exists AND parent quest is in same campaign). Returns bool.
- `quest_act_seed_from_skeleton(campaign_id, quest_id, parsed_acts) → dict` — idempotent skeleton-act seeder, fires from `/quest seed-skeleton` (extended). Match key: `(quest_id, act_index)`. Idempotency rule per Quest Layer v0 precedent.

**Anchor write triggers (per sketch §4):**
1. `/quest accept <id>` — engine sets `current_act_id` to Act 1 of that quest if acts exist, NULL otherwise
2. `/quest act advance <id>` — next act in sequence
3. `/quest act set <id> --act <N>` — non-sequential jump (operator override)
4. `/quest deliver|fail|abandon` — engine sets `current_act_id` to NULL on quest exit (if the abandoned/delivered/failed quest was the current-act-bearing quest)
5. Scene Lifecycle compression — anchor PERSISTS (no write)
6. `/play` resume — last `current_act_id` is the seed (engine canon persists)

---

## §4. Compression-coupled suggester fire cadence (§11.9 lean)

Per sketch §11.9 lean: `compute_quest_act_suggester` fires ONLY on Scene Lifecycle compression turn (not every-turn evaluation, not slash-trigger-only).

**Why compression-coupled:**
- Compression is the natural narrative-pause moment in the existing motion-systems track
- Compression already fires its own directive (Scene Lifecycle v1's soft/strong tier) when a scene has gone stale — by definition the right moment to ask "does this act transition next?"
- Every-turn evaluation produces directive noise (the suggester would fire on every exploration turn)
- Slash-trigger-only requires operator to know when to ask, which defeats the auxiliary suggester's value

**Implementation shape:** in `discord_dnd_bot.py`, after Scene Lifecycle directive fires `tier=soft` or `tier=strong`, call `_dispatch_quest_act_suggester` (sibling of `_dispatch_quest_offer_suggester` from Quest Layer v0). The dispatcher reads current_act, candidate next_act, scene_count, current_location_id, runs `compute_quest_act_suggester`, posts card to `#dm-aside` if proposal returned. Soft-fail throughout per §59 contract.

**Suggester returns None when:**
- No quest is in-progress
- Current quest has no acts authored (NULL current_act_id semantic)
- Current act is the last act (no `candidate_next_act`)
- Predicate fails (scene_count below threshold AND/OR location_id mismatch — depending on which predicate fields are non-NULL in JSON)
- Operator-only mode (predicate JSON is empty `{}`)

**Predicate evaluation logic:**
- If `scene_count_threshold` is set: predicate fires when `scene_count_at_current_act >= threshold`
- If `location_id` is set: predicate fires when `scene_state.current_location_id == location_id`
- If both set: AND-combined (both must match)
- If neither set: no auto-suggester for this act

---

## §5. Scene→act anchor persistence model

`dnd_scene_state.current_act_id` is the engine-side scene→act anchor. NULL when no quest's `in-progress` act applies.

**Persistence under Scene Lifecycle compression (R6 confirmed):**
- Compression machinery does NOT touch `dnd_scene_state.current_act_id`
- Compression writes only the in-memory `_scene_stale_turns` counter (resets to 0 on activity signal)
- LLM-side compression narration writes the three rolling buffers (current_scene, last_dm_response, last_player_action) but not structural columns
- `reset_narrative_buffers_on_combat_exit` (combat→exploration) writes the same three buffers + nothing else
- **Net result: act anchor persists by structural inheritance**

**Quest exit clears the anchor:**
- `/quest deliver`, `/quest fail`, `/quest abandon` fire `set_current_act(campaign_id, None)` if the exiting quest was the current-act-bearing quest. (If the operator was on a different quest's act, that anchor stays untouched.)

**`/play` resume:**
- `dnd_scene_state.current_act_id` is read at session-open and the active-quest directive renders the current act in the opening prompt
- Same resume semantic as `current_location_id` (already in production)

**Multi-quest active state:**
- Single-active-act at v0 per §1.J lock
- If party is on quest A act 2 and operator types `/quest accept B`, engine re-anchors `current_act_id` to quest B's Act 1
- Operator-driven re-anchor; engine never auto-flips between quests' acts

---

## §6. Recon findings

Seven items, evidence-backed against the live codebase + DB (May 13, 2026 post-Quest-Layer-v0.1).

---

### R1. `dnd_scene_state` schema — zero act-adjacent columns. Clean additive for `current_act_id`.

**Evidence (live `PRAGMA table_info(dnd_scene_state)`):** 12 columns — `campaign_id`, `mode`, `last_player_action`, `updated_at`, `tension_int`, `progress_clocks`, `current_location_id`, `turn_counter`, `last_dm_response`, `campaign_day`, `day_phase`, `last_active_actor`. No `current_act_id`, `current_arc_id`, `current_phase`, `current_quest_act`, or similar.

**Finding:** clean additive. Proposed `current_act_id INTEGER NULL DEFAULT NULL` lands as 13th column; no conflict with existing semantics.

---

### R2. `dnd_quests` post-v0/v0.1 — 15 columns, no act-related. `dnd_quest_acts` is clean new table.

**Evidence:** `PRAGMA table_info(dnd_quests)` returns 15 columns: `id`, `campaign_id`, `title`, `summary`, `status`, `priority`, `given_by`, `created_at`, `updated_at`, `offer_npc_id`, `offered_turn`, `accepted_turn`, `delivered_turn`, `reward_summary`, `skeleton_origin`. Zero act-related columns.

`PRAGMA table_info(dnd_quests_audit)` returns 10 columns: `id`, `campaign_id`, `quest_id`, `from_status`, `to_status`, `source`, `actor_npc_id`, `turn_counter`, `detail`, `created_at`. Extension-friendly — adding `to_act_index INTEGER` is one ALTER TABLE additive column.

**Finding:** no conflicts. Composition v0's new table + new column on dnd_quests_audit lands cleanly.

---

### R3. Skeleton.md (campaign 17) — flat-bullet hooks, zero act decomposition

**Evidence:** `/home/jordaneal/scripts/campaigns/17/skeleton.md` `## Major hooks` section contains three one-line bullets:
```
- Escort the merchant caravan from Stonebridge to Redhaven by dawn
- Investigate the goblin-ravaged farmstead on the road
- Survey the lost mine near the Crystal Caves
```

No numbered sub-bullets, no prose phases, no implicit act structure.

**Finding:** v0 introduces act structure cleanly via the `#### Acts` subsection extension (§1.I). No implicit-structure migration needed. Operator authors acts from scratch in skeleton.md per quest, then runs `/quest seed-skeleton` (extended) to land acts into `dnd_quest_acts`.

---

### R4. Active-quest directive — tactical-band, cap-at-3, AUTHORITATIVE framing. Extension path clean.

**Evidence:**
- `compute_active_quest_directive` at `dnd_orchestration.py:4353`. `_ACTIVE_QUEST_CAP = 3`. Priority-then-recency sort.
- Render block: `=== ACTIVE QUESTS (AUTHORITATIVE — outstanding commitments) ===`. Position in `build_dm_context` prompt assembly: between `consequence_block` and `commitment_block` (tactical band).
- Live telemetry (May 13 post-ship): firing with 1 in-progress quest produces 199-char body; firing with 0 quests produces 0-char body (selective-fire).

**Finding:** extension path (a) per sketch §11.4 is structurally clean. The directive function can take an additional `current_act` parameter; when present, render an extra `Act N of M: <title>` line below each quest's line. ~150 chars added per act-bearing quest. Or build `compute_composition_directive` as a sibling and concatenate at the call site; doctrinally equivalent.

---

### R5. Prompt-size baseline post-Quest-Layer-v0/v0.1 — ~25,500 chars / 5,538 directives stable

**Evidence (live, May 13, 2026, post-Quest-Layer-v0.1 ship):**

Sample window: 50 exploration turns, campaign 17.
- **Total prompt:** 24,621 – 26,790 chars (mean ≈25,500). Median ≈25,400.
- **Directives:** 5,538 chars stable baseline (one outlier 6,475 — Scene Lifecycle strong-tier fire). 
- **Retrieval:** 414 – 1,454 (high variance, scene-dependent).
- **System (base):** ~21,000-22,400 chars.
- **active_quest directive:** 199 chars when firing with 1 in-progress quest; 0 chars below threshold.

**Composition delta projected:**
- **Composition directive:** ~150-300 chars when firing (1 act-bearing quest, 1 current_act render).
- **Suggester card:** 0 prompt chars (posts to `#dm-aside`).
- **`#### Acts` skeleton block addition:** ~300-500 chars/campaign (one-time per skeleton-quest with acts).

**Net projected total:** mean ≈25,700-26,000 chars (~1-2% increase). Well within prompt-size headroom. No optimization pressure.

---

### R6. Scene Lifecycle compression preserves `current_act_id` — LOAD-BEARING, **NO HALT**

**Evidence:**
- `compute_scene_lifecycle_directive` at `dnd_orchestration.py:4104` — pure function. Returns `(body, signals)`. **Writes no DB columns.**
- Bot-side dispatcher writes only `_scene_stale_turns` (in-memory dict, line 1011) on activity signals + counter increment/reset. Not a column.
- Compression's directive injection lands in the prompt via `build_dm_context`; the LLM's response narration is posted via `_dm_respond_and_post`, which calls `update_scene` (campaign current_scene buffer) + `update_last_dm_response` (scene_state.last_dm_response buffer) + `update_scene_state(last_player_action=...)`. None of these touch `current_act_id` or any other scene_state structural column.
- `reset_narrative_buffers_on_combat_exit` (`dnd_engine.py:1531`) — called on combat→exploration via `_handle_init_event` evt_type='end'. Writes ONLY:
  - `update_scene(campaign_id, _INIT_END_CLOSEOUT_SCENE)`
  - `update_last_dm_response(campaign_id, _INIT_END_CLOSEOUT_DM)`
  - `update_scene_state(campaign_id, last_player_action=_INIT_END_CLOSEOUT_PLAYER)`
  
  All three are rolling narrative buffers. **None of `dnd_scene_state`'s structural columns are touched.**

**Finding: composition's act anchor (`current_act_id`) is preserved across compression and across combat→exploration mode flips by structural inheritance.** Sketch §4 #5 assumption ("compression itself does NOT advance the act") holds with no additional preservation code needed.

**HALT status: not triggered.** R6 was the foundational risk surface; recon confirms the architectural shape is sound.

---

### R7. `set_current_act` folds into existing single-writer pattern — no §17 amendment

**Evidence (live `set_current_location` shape, `dnd_engine.py:4446`):**
```python
def set_current_location(campaign_id: int, location_id) -> bool:
    """SINGLE WRITE PATH per §9.9. ... Refuses cross-campaign and stale IDs
    at the engine boundary."""
    # Validates FK exists in same campaign
    # UPDATE dnd_scene_state SET current_location_id=?, updated_at=?
    # Returns bool
```

`set_current_act` mirrors this shape with two-step FK validation (act_id exists AND parent quest_id is in same campaign) per §16 engine-defends-invariants. **One UPDATE statement, one writer, no parallel paths.**

**§1.F.c precedent applies:** Scene Lifecycle's v1.x patch dropped NPC was_new from activity signal set because LLM-extracted signals create perverse-incentive surfaces. For Composition v0:
- `current_act_id` writes come from: operator slashes (`/quest accept`, `/quest act advance`, `/quest act set`), engine-deterministic event handlers (`/quest deliver|fail|abandon` clear to NULL).
- ZERO LLM-extracted signals feed `current_act_id`.

**Finding:** §17 single-writer pattern is preserved cleanly. No amendment to VIRGIL_MASTER §4 authority invariant. No LLM-write-path risk. Pattern mirrors `set_current_location` exactly; no new architectural surface introduced.

---

## §7. §76 four-property latent-canon audit

New columns added by Composition v0, each scored against the four properties per Doctrine §76:

| New column | LLM-writable? | Persisted? | Retrieved? | Narratively inferential? | Score | Verdict |
|---|---|---|---|---|---|---|
| `dnd_scene_state.current_act_id` | No (§17 single writer `set_current_act`; gates: operator slash, engine event) | Yes | Indirectly via JOIN to render current-act title in directive | No (integer FK, not narrative text) | 1/4 | Safe |
| `dnd_quest_acts.act_index` | No (§17 helper write) | Yes | Indirectly via JOIN | No (integer ordinal) | 1/4 | Safe |
| `dnd_quest_acts.act_title` | No (operator-authored in skeleton.md at v0; helper-writes only) | Yes | Yes (rendered in directive body) | **Borderline** — a short phrase like "Engage the goblins" is enumerable; a longer phrase invites elaboration | 2/4 | Audit-watch |
| `dnd_quest_acts.act_description` | No (operator-authored at v0; helper-writes only) | Yes | Yes (rendered in directive body, 100-200 chars) | **Yes** — multi-sentence prose IS narratively inferential | **3/4** | **Audit-watch (highest risk)** |
| `dnd_quest_acts.transition_predicate_json` | No (operator-authored at v0; not LLM-extracted) | Yes | No (read by suggester compute, not rendered into LLM prompt) | No (structured JSON) | 1/4 | Safe |
| `dnd_quest_acts.skeleton_origin` | No (helper writes at seed time) | Yes | No (filter only) | No (integer flag) | 1/4 | Safe |
| `dnd_quests_audit.to_act_index` | No (helper writes) | Yes | No (audit log not rendered into prompt) | No (integer) | 1/4 | Safe |

**`act_description` is the highest-risk surface (3/4).** Mitigation per the same operational discipline `reward_summary` got in Quest Layer v0 §7:
- v0 ships with operator-authored only (no LLM-extracted acts)
- v1.x emergent-act-detection (LLM proposes acts from narration) must use §1b suggester pattern + operator approval before any `act_description` lands in `dnd_quest_acts`
- §76 property 1 (LLM-writable) stays closed at v0 because every write flows through `quest_act_upsert` with operator-driven sources

**Operational rule for v0.x emergent-act-detection (filed as §12.x):** if LLM-extraction lands, it MUST flow through validated-suggester (`#dm-aside` card + operator slash to confirm) — same architectural shape as Quest Layer v0.1's Reading-2 framing. Cosine-similarity gates rejected per S57 patch.

**Status enum extension (sketch §1.H lean):** adding `act_advance`, `act_set`, `act_override`, `act_propose` to the `source` enum on `dnd_quests_audit` is an enum extension, not a new column. §76 doesn't apply (the column was already audited at original-add time).

---

## §8. Test plan sketch

Test surface for v0 implementation:

**Engine tests (`test_composition_layer_v0.py`):**
1. `quest_act_upsert` inserts new act with correct fields.
2. `quest_act_upsert` updates existing act in place when `(quest_id, act_index)` matches.
3. `quest_act_upsert` refuses cross-campaign quest_id at engine boundary.
4. `set_current_act` writes `dnd_scene_state.current_act_id` correctly.
5. `set_current_act(None)` clears the column.
6. `set_current_act` refuses non-existent act_id.
7. `set_current_act` refuses cross-campaign act_id.
8. `quest_act_advance` transitions current act to next in sequence.
9. `quest_act_advance` refuses when current act is last act.
10. `quest_act_advance` writes audit row with `source='act_advance'`, `to_act_index=N+1`.
11. `quest_act_set` allows non-sequential jumps; writes audit with `source='act_set'`.
12. `quest_act_seed_from_skeleton` idempotency: re-seeding skips matching (quest_id, act_index).
13. `quest_accept` sets `current_act_id` to Act 1 when acts exist; NULL when no acts.
14. `quest_deliver` / `quest_fail` / `quest_abandon` clear `current_act_id` if the exiting quest was current-act-bearing.

**Orchestration tests:**
15. `compute_quest_act_suggester` returns None when no current_act.
16. Returns None when current_act is last act.
17. Returns None when predicate JSON is empty.
18. Returns proposal when scene_count_threshold matches.
19. Returns proposal when location_id matches.
20. Returns proposal when both scene_count AND location_id match.
21. Returns None when scene_count matches but location_id doesn't (AND-combined).
22. `compute_composition_directive` returns empty when current_act_id is NULL.
23. Returns body with `Act N of M: <title>` line when current_act is set.
24. Body honors AUTHORITATIVE/EXHAUSTIVE framing (extends existing active-quest block).

**Integration tests (`test_composition_layer_integration.py`):**
25. Compression-coupled suggester: scene lifecycle tier=soft fires → quest_act_suggester evaluates.
26. Compression-coupled suggester: scene lifecycle tier=strong fires → quest_act_suggester evaluates.
27. Compression-coupled suggester: scene lifecycle not firing → suggester does NOT evaluate.
28. `/quest accept` seeds `current_act_id` correctly with skeleton-authored acts present.
29. `/quest accept` leaves `current_act_id` NULL when no skeleton acts authored.
30. `/quest act advance` slash → state transition + directive render reflects on next turn.
31. `/quest seed-skeleton` (extended) seeds acts alongside quests; idempotent.

**Regression sweep:** existing test_*.py files pass after schema extension + new helpers + directive integration.

---

## §9. Live-verify scenarios

Seven scenarios for post-implementation Discord live verify (deferred to operator).

1. **Skeleton act seed:** author `#### Acts` in skeleton.md for one campaign 17 quest. `/quest seed-skeleton`. Confirm `dnd_quest_acts` rows inserted with correct `act_index`, `act_title`, `act_description`, `skeleton_origin=1`. Re-run: no duplicates.

2. **Accept seeds Act 1:** `/quest accept <id>` of a quest with skeleton-authored acts. Confirm `dnd_scene_state.current_act_id` is set to Act 1 row. Next prompt shows `Act 1 of N: <title>` in active-quest block.

3. **Accept with no acts → NULL current_act_id:** `/quest accept <id>` of a flat-bullet quest. Confirm `current_act_id` stays NULL. Directive renders quest without act line.

4. **Manual advance:** `/quest act advance <id>`. Confirm state transition. Audit row with `source='act_advance'`, `to_act_index=2`. Directive on next turn shows Act 2.

5. **Suggester fires on compression:** stale scene reaches soft tier, predicate (e.g., scene_count_threshold=2) matches. `#dm-aside` posts QUEST ACT PROPOSED card with current act + proposed next act + predicate reason.

6. **Suggester silent off-compression:** non-compression turn — no quest_act_suggester fire. `quest_act_suggester:` log shows fired=0.

7. **Anchor preservation:** quest at Act 2, stale scene fires compression (soft or strong), LLM compresses scene narratively. Confirm `current_act_id` stays at Act 2 across the compression turn (not advanced silently).

---

## §10. Telemetry

Always-fire log lines (per §59 contract):

- `composition_directive: campaign=N current_act_id=N fired=0|1 chars=N` — every `dm_respond` exploration/social turn.
- `quest_act_suggester: campaign=N quest_id=N current_act=N candidate_next=N proposed=0|1 reason=...` — every compression-fire turn. `reason` populated when proposed=0 (`no_current_act` / `last_act` / `predicate_no_match` / `predicate_empty` / `quest_not_in_progress`).

Per-event log lines:
- `quest_act_seed: campaign=N quest_id=N inserted=N skipped=N` — `/quest seed-skeleton` for acts.
- `quest_act_transition: campaign=N quest_id=N from_act=N to_act=N source=advance|set|override` — every `set_current_act` write.
- `quest_act_anchor_cleared: campaign=N quest_id=N reason=deliver|fail|abandon` — quest exit clears the anchor.

Calibration targets (post-v0 live):
- Suggester noise rate: proposed-rejected fraction (operator declines or ignores the card).
- Advance latency: turns between suggester proposal and `/quest act advance`.
- Predicate accuracy: scene_count vs location_id which fires more often, which gets accepted.

---

## §11. Decision points — operator's call required

12 decisions for operator lock before implementation opens (Session 2 review). §11.1 and §11.2 carry locked pre-decisions from operator framing. Code's leans noted on the other 10; genuine uncertainty flagged.

### §11.1 — Read A vs Read B

**LOCKED Read B per operator pre-decision.** Acts are skeleton-authored phases within `in-progress`, not 1:1 with quest statuses. Surfaced for spec lock; no walk required.

**Confidence: LOCKED.**

---

### §11.2 — Act-transition trigger model: (α) / (β) / (γ)

**LOCKED (γ) hybrid per operator pre-decision.** Canonical operator slash + auxiliary engine-deterministic predicate suggester via `#dm-aside`. §1b fourth project instance candidate.

**Confidence: LOCKED.**

---

### §11.3 — Schema shape: new `dnd_quest_acts` vs extend `dnd_quests` JSON vs scene_state column only

**Recommendation: (a) new `dnd_quest_acts` table.** Mirrors `dnd_quests` shape; cleaner state machine; per-row audit history.

**Confidence: HIGH.** R2 confirms no conflicts; sketch §11.3 lean aligned.

---

### §11.4 — Composition-directive prompt position

**Recommendation: (a) extend `compute_active_quest_directive`'s tactical-band block (acts render inside the active-quest block).**

**Confidence: MEDIUM.** Sketch lean (a). Walk if Session 2 surfaces prompt-position constraints not visible at sketch time. (b) standalone sibling adds redundant render surface; (c) higher framing loses tactical-pressure coupling.

---

### §11.5 — Concurrent active acts: single-active vs multi-active

**Recommendation: (a) single-active-act at v0.**

**Confidence: MEDIUM.** Matches "where are we in the bigger picture" framing. Multi-active-act (one per in-progress quest) is v1.x candidate if operator wants concurrent act states.

---

### §11.6 — Skeleton.md acts authoring shape: structured markdown vs YAML-block-embedded vs freeform-with-markers

**Recommendation: (a) structured markdown per §1.I + sketch §6 shape.**

**Confidence: HIGH.** Matches existing skeleton.md patterns (NPCs, locations, hooks all use heading-based structure).

---

### §11.7 — Transition predicate vocabulary at v0: narrow vs full vs none

**Recommendation: (a) narrow rule set (scene_count_threshold + location_id only) at v0.**

**Confidence: MEDIUM.** Expanded v0.x once observed friction. Matches the v1-then-v1.x narrowing discipline from Scene Lifecycle (S52→S53) and Quest Layer (v0→v0.1).

---

### §11.8 — Audit table: extend `dnd_quests_audit` vs new `dnd_quest_acts_audit`

**Recommendation: (a) extend `dnd_quests_audit`** — add `to_act_index INTEGER` nullable column + new `source` enum values (`act_advance`, `act_set`, `act_override`, `act_propose`).

**Confidence: HIGH.** R2b confirms additive-friendly schema. One audit surface preserves query shape "all changes to quest N."

---

### §11.9 — Suggester fire predicate: every-turn vs compression-coupled vs slash-trigger

**Recommendation: (b) compression-coupled — fire only on Scene Lifecycle tier=soft or tier=strong turn.**

**Confidence: HIGH.** Compression is the natural narrative-pause moment. Sketch §11.9 lean aligned.

---

### §11.10 — `/play` resume renders composition directive

**Recommendation: (a) yes.** Resume is the operator's "where are we?" moment by definition.

**Confidence: HIGH.** Same render-on-resume semantic as `current_location_label`.

---

### §11.11 — Composition forward-compat: silent or pre-couple emergent-act-detection / multi-quest-arc / beat-tracker

**Recommendation: (a) silent.** v0 schema does not pre-couple v1.x candidates.

**Confidence: HIGH.** Same discipline Quest Layer v0 followed re composition. Filed §12.x candidates without schema coupling.

---

### §11.12 — §1a/§1b scrutiny on auxiliary suggester — fourth project instance anchoring

**Recommendation: §1b fourth project instance clean. Canonical gate is operator slash; auxiliary predicate is suggester-only with deterministic rule-match (scene_count + location_id, no calibration-bound logic).**

The architectural shape:
- **Bot proposes** via `#dm-aside` post (non-Avrae operational channel)
- **Deterministic Python gate** validates proposal: predicate match against operator-authored JSON (scene_count threshold, location_id match) — strictly deterministic, no calibration drift
- **DM approves by slash** (`/quest act advance <id>` canonical gate)
- **Engine executes** SQLite write via `set_current_act` + audit row

**Distinction from Quest Layer v0.1 (S57 patched):** Quest Layer v0.1 originally landed at Reading-3 (canonical slash + auxiliary cosine-similarity paste-detection), then patched to Reading-2 (slash-only) per S57 UX finding. Composition v0 ships **Reading-2 directly** — no cosine-similarity / paste-detection auxiliary layer at any point. The auxiliary suggester proposes via card; operator approves via slash. No string-matching gate, no calibration-bound logic anywhere.

**Fourth-instance anchoring expectation: clean at Session 2 walk.** No operator + Oracle ambiguity expected. If review surfaces an unexpected §1a concern, fallback options are slash-only mode (drop the suggester entirely) or operator-typed-trigger-only (suggester fires only on `/quest act suggest`).

**Confidence: MEDIUM (walk-to-confirm at Session 2).** Operator confirms the fourth-instance anchoring framing; alternative if rejected is dropping the auxiliary suggester layer entirely. Both shapes are implementable; operator's call.

---

## §12. Open questions filed forward — out of v0 scope

**§12.1 — Emergent-act-detection (LLM-extracted acts from narration).**
v1.x. LLM proposes new act boundaries from narration cues; validated-suggester pattern (`#dm-aside` card + operator slash to confirm). Must inherit Reading-2 framing from Quest Layer v0.1 — no cosine-similarity gates. `act_description` §76 audit-watch (3/4) applies.

**§12.2 — Multi-quest-arc primitive ("the Stoneforge campaign arc").**
v1.x. Quest-arc-spanning-multiple-quests primitive. Requires new schema (`dnd_quest_arcs`?) + scene_state coupling. Composition v0 stays single-quest-act-scoped.

**§12.3 — Beat-tracker primitive (finer than act).**
v1.x. Acts are coarse (5-15 scenes per act); beats are individual moments. Composition layer operates at act granularity; beat-tracker is a separate ship if observed friction shows operators want it.

**§12.4 — Auto-decompose: engine proposes act structure given a quest description.**
v1.x. LLM proposes Act 1/2/3 decomposition from quest title + summary. Operator-validated. Speeds up skeleton authoring.

**§12.5 — Composition-layer-queries beyond prompt-render.**
v1.x candidate. Operator-facing `/quest act list <quest_id>` exists at v0 (basic). Richer queries ("which quests are stuck mid-act for >N turns?") are v1.x if observed friction shows operator wants narrative-position queries.

**§12.6 — Multi-active-act (concurrent in-progress quest acts).**
v1.x. Single-active-act at v0 per §1.J. Multi-active-act surfaces if operator wants engine-canonical "we're on quest A act 2 AND quest B act 1" without re-anchor friction.

**§12.7 — Predicate vocabulary expansion (npc_interaction, consequence_kind, custom rules).**
v0.x once observed friction. Narrow at v0 (scene_count + location_id only).

**§12.8 — Suggester fire cadence expansion (every-turn evaluation if compression-coupled produces under-coverage).**
v0.x candidate if compression-coupled fire rate misses real act-transition moments. Predicate evaluation is cheap; cadence change is a one-line patch if needed.

**§12.9 — `act_description` §76 audit-watch (3/4) hardening.**
v0.x candidate if `act_description` rendered text drifts narratively. Mitigation paths: (a) structured-vocabulary convention (1-line; no prose), (b) render only `act_title` not description, (c) cap render at first sentence.

**§12.10 — Composition-of-composition (campaign-level narrative position beyond quest-act).**
v1.x. The mandate's "bigger picture" framing at quest-act level lands at v0; campaign-arc-level framing is the next abstraction up. Out of scope for v0.

---

## §13. Out of scope — v0 explicitly does not

- LLM-decided act transitions (per Oracle pre-frame: act boundaries are engine-decided, structural choice not narrative call).
- LLM-extracted act decomposition from narration (filed §12.1).
- Quest-arc-spanning-multiple-quests primitive (filed §12.2).
- Beat-tracker primitive (filed §12.3).
- Auto-decompose from quest title + summary (filed §12.4).
- Cosine-similarity / fuzzy-match gates anywhere (Reading-2 framing — Quest Layer v0.1 S57 patch precedent).
- Bot-emitted Avrae commands (§F-59 + §65 invariant).
- Multi-active-act / concurrent acts (filed §12.6).
- Predicate vocabulary expansion beyond scene_count + location_id (filed §12.7).
- Combat-mode act transitions (mode gate — suggester checks `mode in {social, exploration}`).
- Any modification to adjudication layer, narration verifier, or `avrae_listener.py`.

---

## §14. Handoff

| Field | Value |
|---|---|
| **Spec status** | DRAFT — Phase 1 spec drafting complete (May 13, 2026). §11.1 + §11.2 carry locked pre-decisions; Session 2 walks the other 10. |
| **Spec file** | `/home/jordaneal/virgil-docs/specs/COMPOSITION_LAYER_V0_SPEC.md` |
| **§1 decisions** | 13 proposed decisions (§1.A–§1.M), §1.A + §1.B locked pre-decisions; §1.C–§1.M recommendations |
| **§11 count** | 12 decisions (§11.1–§11.12). 2 LOCKED pre-decision (§11.1, §11.2). 7 HIGH confidence, 3 MEDIUM. |
| **§12 count** | 10 open questions filed forward (§12.1–§12.10) |
| **HALT escalations** | 0 — **R6 confirmed Scene Lifecycle compression preserves `current_act_id` by structural inheritance.** No write surface in compression machinery touches scene_state structural columns. Foundational assumption holds. |
| **Recon findings** | R1: zero act-adjacent columns in `dnd_scene_state` — clean additive. R2: `dnd_quests` post-v0 has 15 columns, no act-related; `dnd_quests_audit` additive-friendly. R3: campaign 17 skeleton.md has flat-bullet hooks, zero act decomposition — v0 introduces structure cleanly. R4: active-quest directive extension path (a) clean; tactical-band, cap-at-3, ~199 chars firing. R5: prompt baseline ~25,500 chars / 5,538 directives stable; composition delta ~150-300 chars when firing. **R6: NO HALT — compression preserves `current_act_id` by construction.** R7: `set_current_act` folds into existing `set_current_location` single-writer pattern; no §17 amendment. |
| **Architectural recommendation** | New `dnd_quest_acts` table + 1 column on `dnd_scene_state` + 1 column on `dnd_quests_audit` + 4 new source enum values. Two new §59 siblings (14th + 15th instances). §1b fourth project instance candidate via auxiliary engine-deterministic suggester (no calibration-bound gates). Reading-2 framing direct — no cosine-similarity layer ever. |
| **§76 audit summary** | 7 new columns audited. Highest risk: `dnd_quest_acts.act_description` (3/4 — multi-sentence prose IS narratively inferential). Mitigation: operator-authored only at v0; §1b suggester pattern mandatory for v1.x emergent-act-detection. |
| **Next session** | Session 2 = review pass. Opus medium per WWC cadence (mature §59 sibling pattern with three precedents in motion-systems track; mature §1b suggester pattern with three precedents). Walk §11.3–§11.12 with operator; §11.1 + §11.2 LOCKED pre-decisions carry forward. Spec flips DRAFT → LOCKED. Session 3 = implementation. |

---
