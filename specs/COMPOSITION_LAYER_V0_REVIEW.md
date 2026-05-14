# COMPOSITION_LAYER_V0_REVIEW.md

**Status:** REVIEW — Phase 2 (Path A review pass). Walks the 10 unlocked §11 decisions (§11.3–§11.12). §11.1 (Read B) and §11.2 (γ hybrid) carry locked pre-decisions, surfaced in §0 framing but not re-walked. Not a lock. Operator reads, locks remaining decisions, spec flips DRAFT → LOCKED before Session 3.

**Session:** S59 Phase 2 review pass, May 13, 2026
**Spec reviewed:** `/home/jordaneal/virgil-docs/specs/COMPOSITION_LAYER_V0_SPEC.md` (DRAFT)
**Basis:** `planner-scratch/composition_layer_v0_sketch.md`, DOCTRINE §1a/§1b/§17/§59/§76, three §1b prior instances (Track 6 #5.1 SRD suggester S26, S41 NPC State-Sync, Quest Layer v0.1 post-S57), Scene Lifecycle v1 + v1.x compression precedent.

**Format per decision:** question restatement → trade-offs table → recommended default + confidence → open axis named (MEDIUM/LOW only).

---

## §0. Locked pre-decisions surfaced

**§11.1 — Read B locked.** Acts are skeleton-authored narrative phases within `status='in-progress'`, not 1:1 with quest statuses. Per operator pre-framing; no Session 2 walk.

**§11.2 — (γ) hybrid locked.** Act transitions write through one of: canonical operator slash (`/quest act advance`, `/quest act set`); engine-deterministic auxiliary predicate suggester via `#dm-aside` (operator approves by slash). §1b fourth project instance candidate — see §3.M walk for anchoring evaluation. Per operator pre-framing; trigger model not re-walked.

---

## §1. Inventory note before walking

**Spec §1.I authoring example self-consistency check.** The spec's §1.I example skeleton.md authoring for the farmstead quest's three acts lists ONLY narrow-vocabulary predicate hints (scene_count + location). The sketch §6 example included `Consequence kind: quest_outcome` for Act 3. The spec correctly dropped that line to match the locked-narrow-at-v0 lean (§11.7). No spec inconsistency; flag noted for operator awareness if they have the sketch open alongside.

**No HALT triggered.** No decision walk surfaced a finding that invalidates v0 architectural shape. R6 (compression preservation) was the foundational risk surface; recon already confirmed clean. R6 forward-compat check below confirms spec §4 + §5 honor the preservation correctly.

---

## §2. Summary table

| Decision | Question | Recommended | Confidence | Notes |
|---|---|---|---|---|
| **§11.1** | Read A vs Read B | **LOCKED Read B** | — | Pre-decision; not walked |
| **§11.2** | Trigger model α/β/γ | **LOCKED (γ) hybrid** | — | Pre-decision; not walked |
| §11.3 | Schema: new table vs JSON vs scene_state only | (a) new `dnd_quest_acts` table | HIGH | R2 evidence; mirrors Quest Layer v0 pattern |
| §11.4 | Composition-directive position | (a) extend active-quest block | MEDIUM | R4 clean extension path; open axis: standalone-sibling if operator wants separation |
| §11.5 | Single-active vs multi-active | (a) single-active at v0 | MEDIUM | Open axis: concurrent-act friction surfaces in playtest |
| §11.6 | Skeleton authoring shape | (a) structured markdown | HIGH | Matches existing skeleton patterns |
| §11.7 | Predicate vocabulary | (a) narrow (scene_count + location_id) | HIGH | Synthesis below; graceful degradation to operator-only for non-fitting predicates |
| §11.8 | Audit: extend vs new table | (a) extend `dnd_quests_audit` + `to_act_index` col | HIGH | R2b additive-friendly; one-surface query shape preserved |
| §11.9 | Suggester fire cadence | (b) compression-coupled | HIGH | Natural narrative-pause moment |
| §11.10 | `/play` resume rendering | (a) yes | HIGH | Mirrors `current_location_label` precedent |
| §11.11 | Composition forward-compat | (a) silent | HIGH | Quest Layer v0 discipline mirror |
| §11.12 | §1b fourth-instance anchoring | Stands as 4th instance; sub-pattern observation surfaced | MEDIUM | Walk-to-confirm; sub-pattern naming is operator + Oracle |
| **§11.13 (NEW)** | Cascade delete: parent quest → acts | (a) ON DELETE CASCADE | HIGH | Surfaced during walk; see §3.N |

**Split:** 7 HIGH · 4 MEDIUM · 0 LOW · 1 NEW (§11.13) · 2 LOCKED pre-decision.

---

## §3. Full decision walk

---

### §3.3 — Schema shape: new `dnd_quest_acts` vs JSON column vs scene_state-only

**Question:** Add a new `dnd_quest_acts` table with FK to `dnd_quests.id`, extend `dnd_quests` with a JSON column for per-act data, or store only the current_act surface on scene_state (no acts table at all)?

**Candidates:** (a) new `dnd_quest_acts` table; (b) JSON column on `dnd_quests`; (c) scene_state-only (acts inline in act_id semantics, no persisted per-act metadata).

| Candidate | Pros | Cons | Risk |
|---|---|---|---|
| **(a) New table** | Per-row state cleanly; FK + audit history mirrors `dnd_quests` shape; one `quest_act_upsert` single-writer per §17 | One new table to migrate + maintain | Low — R2 confirms additive lands cleanly |
| (b) JSON column on `dnd_quests` | No new table | Querying JSON-shaped per-act state is awkward; per-act audit history doesn't map cleanly; bloats row size | Medium — query complexity grows; per-act updates require row rewrite |
| (c) scene_state-only | Lightest schema | No per-act `title` / `description` / `predicate_json` persistence; cannot render Act 2 of 3 in the directive without metadata; fundamentally incomplete | High — the title and description are load-bearing for the composition directive; can't omit |

**Recommended default: (a) new `dnd_quest_acts` table.**

**Reasoning:** Per §1.C reasoning. Acts have distinct lifecycle (transition history, ordering, predicate config); separating from `dnd_quests` keeps both clean. Same reasoning Quest Layer v0 used vs extending `dnd_consequences`. R2 evidence confirms no conflicts.

**Confidence: HIGH.** Spec lean confirmed.

---

### §3.4 — Composition-directive prompt position

**Question:** Where in `build_dm_context` does the act render?

**Candidates:** (a) extend `compute_active_quest_directive`'s tactical-band block (act renders inside the active-quest block, same position); (b) new sibling directive in tactical band immediately after active-quest directive; (c) higher framing (before tactical band, alongside `current_location_label`).

| Candidate | Pros | Cons | Risk |
|---|---|---|---|
| **(a) Extend active-quest block** | Single render block, single call; aligned tactical-pressure coupling; ~150-200 chars added per act-bearing quest; minimal new render surface | Couples two §59 sibling functions' outputs at the call site (concat) OR requires `compute_active_quest_directive` signature to take current_act | Low — both implementation shapes are doctrinally equivalent; choose at implementation time |
| (b) New sibling directive | Cleaner separation between active-quest and current-act render paths; independent fire signals | Doubles directive emission for related content; two adjacent `=== ACTIVE QUESTS ===` / `=== CURRENT ACT ===` blocks for the same quest | Medium — render redundancy; visual clutter in the prompt |
| (c) Higher framing | Acts framed as scene-state-anchor (alongside `current_location_label`); foregrounds "where we are" | Loses tactical-pressure coupling (acts as immediate-stakes pressure same tier as consequence + commitment); framing-band placement is for context, not pressure | Medium — semantic mismatch; acts are immediate stakes, not scene framing |

**Recommended default: (a) extend active-quest block.**

**Reasoning:** Per §1.G. Tactical-band placement aligns act pressure with consequence pressure (both are "stakes the world tracks"). Render lives next to the quest title; the LLM reads them as a unit. Implementation choice (extend function signature vs concat at call site) is doctrinally equivalent — defer to Session 3.

**Confidence: MEDIUM.** Open axis: if operator wants visual/structural separation between active-quest list (quest titles) and current-act render (phase title + description), (b) standalone-sibling is the cleaner shape. Walk if Session 2 surfaces that preference; otherwise (a) holds.

---

### §3.5 — Concurrent active acts: single-active vs multi-active

**Question:** Does `dnd_scene_state.current_act_id` hold one act at a time, or a list of acts (one per in-progress quest)?

**Candidates:** (a) single-active-act (one column on scene_state); (b) multi-active-act (list / join table with one row per in-progress quest's current act).

| Candidate | Pros | Cons | Risk |
|---|---|---|---|
| **(a) Single-active-act** | Mirrors `current_location_id` shape (single column); matches "where are we in the bigger picture" framing (one answer); simpler render (cap-1 act in directive); operator-driven re-anchor via `/quest accept` or `/quest act set` | Switching between quests' acts requires explicit slash; no engine-canonical "we're on quest A act 2 AND quest B act 1" simultaneously | Low — slash re-anchor is operator's authority surface; mirrors existing patterns |
| (b) Multi-active-act | Engine-canonical concurrent state; party multi-tracking a quest A + quest B without slash friction | New join table or JSON-list-on-scene_state column; render complexity (which act surfaces in the prompt? all? priority-sorted? operator-pinned?); §11.4 prompt position decision multiplies | Medium — concurrent-act render produces directive bloat; "current act" semantic becomes plural |

**Recommended default: (a) single-active-act at v0.**

**Reasoning:** Per §1.J. Matches the mandate's "bigger picture" framing — the answer is one act-string, not a list. Multi-active is v1.x candidate if observed friction shows operator wants concurrent state. The Quest Layer v0 precedent: ship the simpler shape, observe friction, expand if log signal justifies.

**Confidence: MEDIUM.** Open axis: if playtest shows operator frequently switches between in-progress quests' acts via slash and the friction is real, (b) multi-active is the v1.x path. Log signal: `quest_act_anchor_re_anchored:` count + operator-typed `/quest act set` frequency against same-session in-progress quests.

---

### §3.6 — Skeleton authoring shape: structured markdown vs YAML-embedded vs freeform-with-markers

**Question:** How does operator author acts in skeleton.md?

**Candidates:** (a) structured markdown per spec §1.I (heading-based `#### Acts` subsection with numbered bullets + indented predicate hint lines); (b) YAML-block-embedded (`---` fence with structured YAML); (c) freeform-with-markers (operator writes prose; parser extracts via regex markers).

| Candidate | Pros | Cons | Risk |
|---|---|---|---|
| **(a) Structured markdown** | Matches existing skeleton patterns (NPCs, locations, hooks all use heading-based structure); operator-readable as plain markdown; renders cleanly when skeleton is opened in any editor | Parser must handle markdown nuances (bullet styles, indent levels) | Low — existing skeleton parser handles similar shapes; well-trodden territory |
| (b) YAML-block-embedded | Strictest format; trivial parser | Breaks skeleton.md's "human-writable narrative document" character; YAML inside markdown reads oddly; operator hates editing YAML inline | Medium — authoring friction; operator preference doesn't favor YAML |
| (c) Freeform + markers | Most flexible operator authoring | Parser regex fragility; "freeform" invites operator-typed variance that breaks predicate extraction; debugging surface grows | High — variance + extraction fragility kills idempotent re-seed |

**Recommended default: (a) structured markdown.**

**Reasoning:** Per §1.I. Matches existing skeleton.md conventions; operator-readable; parser shape is tractable. Backward-compat: existing flat-bullet `## Major hooks` remains valid; operator opts INTO act decomposition by promoting a hook to `### <Quest title>` with `#### Acts` subsection.

**Confidence: HIGH.** Spec lean confirmed.

---

### §3.7 — Transition predicate vocabulary at v0 (DEEP SYNTHESIS PER BRIEF)

**Question:** What predicate rules does `transition_predicate_json` carry at v0?

**Candidates:** (a) narrow: `scene_count_threshold` + `location_id`; (b) full: + `npc_interaction` + `consequence_kind`; (c) none (suggester fires only on manual `/quest act suggest` slash).

#### Trade-off table

| Candidate | Pros | Cons | Risk |
|---|---|---|---|
| **(a) Narrow** | Smallest authoring surface; engine-side detection logic minimal (scene_count derived from audit, location_id from scene_state); covers the highest-value auto-suggester moment (Act 1 → Act 2 mid-quest transition) | Acts whose natural predicate doesn't fit narrow vocabulary fall through to operator-only mode | Low — graceful degradation; operator slash is always available |
| (b) Full | Wider auto-suggester coverage (Act 2 → Act 3 via consequence_kind, NPC-departure transitions via npc_interaction) | Larger authoring surface; engine-side detection logic for npc_interaction + consequence_kind requires new helper code; calibration risk if predicate vocabulary grows opaque to operator | Medium — premature expansion; same v1-then-v1.x pattern Scene Lifecycle and Quest Layer settled |
| (c) None | Zero auto-suggester surface; operator authority pure | Loses the §1b suggester pattern's value entirely; pattern degenerates to operator-typed-`/quest act suggest` which is just a query, not a suggester | High — defeats the (γ) hybrid lock from §11.2 |

#### Synthesis: predicate-fit check against campaign 17 farmstead quest

The campaign 17 farmstead quest (skeleton-authored per spec §1.I example):
- **Act 1 — Approach the farmstead.** Natural predicate: scene_count threshold (party has explored the road for 2-3 scenes before reaching the farmstead). ✅ Narrow vocabulary fits cleanly.
- **Act 2 — Engage the goblins.** Natural predicate: location_id match (party has entered the farmstead grounds location). ✅ Narrow vocabulary fits cleanly.
- **Act 3 — Clear the farmstead, find the survivors.** Natural predicate per sketch §6: `consequence_kind=quest_outcome` (combat resolves, consequence promotes). ⚠️ NOT in narrow vocabulary.

**Is Act 3's gap a real architectural problem?**

The Act 2 → Act 3 transition coincides with combat-end / social-resolution — a moment that already has operator authority via Scene Lifecycle compression machinery + `/init end` + the operator's natural decision to wrap the scene. Operator-typed `/quest act advance 11` on the resolution turn is natural workflow, not friction.

Auto-suggester value is highest at MID-act transitions where the operator might miss the moment (party's been exploring the road for 4 scenes, hasn't reached the farmstead yet — auto-suggester nudges Act 1→Act 2 location-entry). The resolution moment (Act 2→Act 3) is rarely "missed" by an attentive operator — by definition the operator is engaged because combat is resolving.

**The natural authoring degradation:** Act 3 of farmstead has empty predicate JSON (`{}`), suggester returns `reason=predicate_empty`, operator advances via slash. This is operator-only mode for Act 3 — graceful, not gapped.

**Comparison with sketch §6 example:**
- Sketch authored Act 3 with `Consequence kind: quest_outcome`
- Spec §1.I dropped that line (matching narrow lean)
- Review confirms: dropping is correct at v0; the natural predicate for Act 3 is the operator's resolution-moment authority, not engine auto-detection

**v0.x expansion path filed §12.7:** if log signal shows operators routinely missing Act N→N+1 transitions where the predicate would naturally be `consequence_kind` (i.e., they advance via slash but only after several stale turns post-combat-end), expand narrow to include `consequence_kind`. Authoring extension; no schema change required (the JSON column already supports arbitrary fields).

**Recommended default: (a) narrow (scene_count + location_id).**

**Confidence: HIGH.** Synthesis confirms narrow vocabulary covers the high-value auto-suggester moments (mid-act transitions) and gracefully degrades to operator-only for resolution-moment transitions. No structural gap; documentation is internally consistent (spec §1.I example correctly omits `consequence_kind` per narrow lean).

---

### §3.8 — Audit table: extend `dnd_quests_audit` vs new `dnd_quest_acts_audit`

**Question:** Where do act-transition audit rows land?

**Candidates:** (a) extend `dnd_quests_audit` (add `to_act_index INTEGER` nullable + new `source` enum values); (b) new `dnd_quest_acts_audit` table; (c) no audit at v0.

| Candidate | Pros | Cons | Risk |
|---|---|---|---|
| **(a) Extend** | One audit surface preserves "all changes to quest N" query shape; one ALTER TABLE additive column; new source enum values mirror Quest Layer v0 pattern | Audit row semantics carry two row-shape variants (status-transition with `from_status`/`to_status`; act-transition with `to_act_index`); reader must discriminate by source | Low — discriminator-by-source is the established pattern; reader handles by enum branch |
| (b) New table | Cleaner per-table semantic (one shape per audit table) | Doubles audit surface; "all changes to quest N" requires UNION; per-quest debug command needs two queries | Medium — query-shape penalty; little structural gain |
| (c) No audit | Lightest | Loses transition history; debugging surface drops; `/quest act list <quest_id>` cannot show "this act fired at turn N" | High — debugging surface loss; future v0.x calibration loses signal |

**Recommended default: (a) extend `dnd_quests_audit`.**

**Reasoning:** Per §1.H. Acts are tightly coupled to quests; one audit surface preserves query shape. R2b confirms additive-friendly schema. Source enum discriminator is the established Quest Layer v0 pattern.

**Confidence: HIGH.** Spec lean confirmed.

---

### §3.9 — Suggester fire cadence

**Question:** When does `compute_quest_act_suggester` fire?

**Candidates:** (a) every-turn evaluation; (b) compression-coupled (Scene Lifecycle tier=soft/strong turn); (c) slash-trigger only (operator types `/quest act suggest`).

| Candidate | Pros | Cons | Risk |
|---|---|---|---|
| (a) Every-turn | Maximum coverage; never miss a transition moment | Directive noise — predicate evaluation runs every exploration turn; cooldown gate needed | Medium — `#dm-aside` card spam if predicate matches across turns |
| **(b) Compression-coupled** | Natural narrative-pause moment; compression cadence (soft at stale=3, strong at stale=6) provides natural rate-limiting; aligned with Scene Lifecycle precedent | Misses transition moments where compression doesn't fire (e.g., rapid-fire engagement scenes that never go stale) | Low — operator slash `/quest act advance` always available as fallback |
| (c) Slash-trigger | Zero spam; operator authority pure | Defeats the auto-suggester's value (operator has to know when to ask); pattern degenerates to query, not suggestion | High — same defeat as §11.7 (c) "none" |

**Recommended default: (b) compression-coupled.**

**Reasoning:** Per §1.G + sketch §11.9 lean. Compression is the natural narrative-pause moment. Stale-counter cadence (soft at 3, strong at 6 turns) provides natural rate-limiting; auto-suggester fires only when the scene has gone stale anyway. Aligns with the motion-systems track's existing compression-as-decision-moment pattern.

**Confidence: HIGH.** Spec lean confirmed.

---

### §3.10 — `/play` resume renders composition directive

**Question:** When operator resumes via `/play`, does the composition directive fire on the resume turn?

**Candidates:** (a) yes; (b) no (silent on resume, fires only on subsequent turns).

| Candidate | Pros | Cons | Risk |
|---|---|---|---|
| **(a) Yes** | Resume is the operator's "where are we?" moment by definition; mirrors `current_location_label` resume semantic | Adds ~150-300 chars to the opening prompt | Low — prompt-size budget safe per R5 |
| (b) No | Cleaner resume framing (location only, acts surface on next turn) | Operator-facing "what was happening?" answer is delayed by one turn | Medium — delayed orientation; resume is exactly the moment to answer this |

**Recommended default: (a) yes.**

**Reasoning:** Per §1.L. Resume is the operator's orientation moment; the act anchor is exactly what answers "where are we in the bigger picture." Same semantic as `current_location_label` (production behavior already).

**Confidence: HIGH.** Spec lean confirmed.

---

### §3.11 — Composition forward-compatibility silent

**Question:** Does v0 schema pre-couple v1.x candidates (emergent-act-detection, multi-quest-arc, beat-tracker)?

**Candidates:** (a) silent (no pre-coupling); (b) pre-couple at least one v1.x candidate.

| Candidate | Pros | Cons | Risk |
|---|---|---|---|
| **(a) Silent** | Quest Layer v0 discipline mirror; future v1.x ships surface their own schema needs; no dead columns at v0 | None — v1.x extensions are additive | Low — no risk |
| (b) Pre-couple | Forward-compat columns ready when v1.x ships | Speculation surface; columns may misalign with what v1.x actually needs (Quest Layer v0 precedent: sketch's composition coupling was avoided, and Composition v0 now lands cleanly without it) | Medium — premature schema commitment |

**Recommended default: (a) silent.**

**Reasoning:** Per §1.M. Same discipline Quest Layer v0 followed; same result expected (cleaner v1.x landing when its spec opens). Filed §12.1, §12.2, §12.3, §12.4 carry v1.x candidates without schema coupling.

**Confidence: HIGH.** Spec lean confirmed.

---

### §3.M (§11.12) — §1b fourth-instance anchoring (DEEP SYNTHESIS PER BRIEF)

**Question (per session brief):** (a) Does composition suggester match the §1b anchored pattern across all three prior instances? (b) Confirm Reading-2 direct framing (no cosine-similarity / no calibration-bound validator). (c) Does fourth-instance anchoring formalize a §1b sub-pattern ("deterministic-validator suggester")?

#### §3.M.a — Architectural shape match across four instances

**Reference pattern (anchored across three prior instances):**

| Instance | Bot proposes via | Deterministic validator | Operator approves by | Authority executes |
|---|---|---|---|---|
| Track 6 #5.1 SRD suggester (S26) | `#dm-aside` card | SRD index lookup (strict string-key match) | Paste `!init madd` into `#dm-narration` | Avrae state mutation |
| S41 NPC State-Sync (post-pivot) | `#dm-aside` 3-line block | `gate_*` paths + Case A/B mid-combat split | Paste `!init remove`/`!init add`/`!init opt` into `#dm-narration` | Avrae state mutation |
| Quest Layer v0.1 (post-S57 patch) | `#dm-aside` card (pure operational) | Explicit `/quest accept <id>` slash command | Slash | Engine SQLite mutation |
| **Composition Layer v0 (proposed)** | `#dm-aside` card (pure operational) | Explicit `/quest act advance <id>` slash command + predicate match against operator-authored JSON (deterministic rule eval) | Slash | Engine SQLite mutation |

**Shape match: ✅ clean.** All four share:
- Non-Avrae channel for bot proposal (`#dm-aside`)
- Strictly deterministic validator (no calibration parameters, no threshold-bound logic, no fuzzy match)
- Operator approval as the canonical gate (paste-then-Avrae OR direct slash-then-engine)
- Mechanical authority (Avrae or SQLite) executes

The executor identity (Avrae vs SQLite) is incidental to the doctrine per §1b's wording ("mechanical authority (Avrae or SQLite) executes the validated decision").

#### §3.M.b — Reading-2 direct framing confirmation

Composition Layer v0 ships **Reading-2 from the outset** — no Reading-3 detour through cosine-similarity / paste-detection. The S57 patch precedent (Quest Layer v0.1 dropping cosine-similarity after live verify surfaced "RP-in-operational-channel" UX friction) is honored at spec time, not as a post-ship patch.

**Composition suggester card format** is pure operational suggestion per spec §3:
```
[QUEST ACT PROPOSED]
Quest #11: Investigate the goblin-ravaged farmstead
Current: Act 1 of 3 (Approach the farmstead)
Proposed: Act 2 of 3 (Engage the goblins)
Predicate reason: scene_count_threshold=2 reached AND location_id matches farmstead grounds

[Run /quest act advance 11 to confirm, or /quest act set 11 --act <N> for non-sequential jump.]
```

No in-character dialogue. No quoted NPC speech. No "paste this into narration" hint. The LLM renders the act transition organically on the next narration turn once `/quest act advance` flips `current_act_id`.

**Verdict: Reading-2 direct framing confirmed.** No cosine-similarity wiring exists in the spec. The lesson from Quest Layer v0.1 S57 patch crystallizes into v0 design: deterministic gates throughout, no calibration-bound auxiliary.

#### §3.M.c — Sub-pattern naming question

**Observation:** Four §1b instances now share a converging pattern. The validators across all four are strictly deterministic:
- SRD suggester: index lookup
- NPC State-Sync: gate predicates + state preconditions
- Quest Layer v0.1: slash command (with cosine-similarity dropped per S57)
- Composition Layer v0: slash command + JSON-rule eval (proposed)

Calibration-bound validators (cosine-similarity, fuzzy match, LLM-classified intent) are explicitly **excluded** from all four. The S57 patch lesson is becoming infrastructural: §1b's "deterministic Python layer validates" clause is being interpreted strictly across project instances.

**Candidate sub-pattern naming:** "**§1b deterministic-validator suggester**" — the canonical §1b shape where the validator is strictly deterministic, with no calibration parameters, no threshold-bound logic, no fuzzy match. Distinct from a hypothetical "§1b calibrated-validator suggester" which would require additional safeguards (operator double-confirmation, calibration drift monitoring, etc.).

**Should the sub-pattern be formally anchored?**

Three options for operator + Oracle:

- **(A) Anchor as §1b sub-pattern in doctrine.** Add a "Deterministic-validator suggester" sub-clause to §1b's Doctrine block. Future ships defaulting to this sub-pattern inherit the discipline. Calibrated validators require explicit doctrine-amendment justification.
- **(B) Surface as observational running list.** §1b doctrine already maintains a "project instances of §1b's suggester pattern" running list. Add Composition v0 as fourth instance + a footnote observation: "Four instances share the deterministic-validator shape; calibration-bound validators have not anchored cleanly (Reading-3 cosine-similarity dropped at Quest Layer v0.1 S57)." No formal sub-pattern, but the pattern is named where future Code sessions will see it.
- **(C) No sub-pattern yet.** Four instances isn't enough to formalize. Wait for a fifth instance to confirm the pattern; running-list footnote only.

**Code recommendation: (B) surface as observational running-list entry, no formal sub-pattern anchoring.**

**Reasoning:** Operator + Oracle decisions about doctrine anchoring are higher-stakes than spec-side recommendations. Four instances is suggestive but not definitive — a fifth instance (or a deliberate calibrated-validator attempt that surfaces friction) would strengthen the case. Surfacing in the running-list footnote captures the observation for future Code sessions to read without committing the doctrine to a sub-clause prematurely.

#### §3.M verdict

**Fourth-instance anchoring: stands cleanly.** Composition Layer v0's auxiliary suggester matches the established §1b shape; deterministic-validator throughout; Reading-2 direct (no cosine-similarity). Spec is doctrinally compliant.

**Sub-pattern naming: operator + Oracle to decide.** Code surfaces option (B) running-list footnote as the lean. (A) formal anchor and (C) no-pattern are also implementable. Decision sits with operator after Session 2 review.

**Confidence: MEDIUM walk-to-confirm.** Operator confirms (or escalates to Oracle) on the sub-pattern naming question. The fourth-instance anchoring itself is clean — confidence on that is HIGH; the MEDIUM tag is specifically for the sub-pattern question.

---

### §3.N (§11.13 — NEW) — Cascade delete: parent quest → acts

**Surfaced during walk.** Spec §3 lists `quest_delete` as the operator orphan-cleanup tool (preserved from Quest Layer v0 for Finding 3 orphan handling). But the spec doesn't address: when a quest with acts is deleted, what happens to the FK-related `dnd_quest_acts` rows?

**Candidates:**
- **(a) ON DELETE CASCADE** — deleting a quest auto-deletes its acts. Cleanest FK semantic; matches "quest is gone, its acts are meaningless."
- **(b) Explicit cleanup in `quest_delete` helper** — `quest_delete` first deletes the acts (with audit rows), then deletes the quest. More verbose; same end-state.
- **(c) Stranded acts** — acts persist after quest deletion; no FK cleanup. `dnd_quest_acts.quest_id` becomes a dead reference.

| Candidate | Pros | Cons | Risk |
|---|---|---|---|
| **(a) ON DELETE CASCADE** | Schema-level enforcement; FK semantic clean; one DDL flag | SQLite ON DELETE CASCADE requires PRAGMA foreign_keys=ON (may need engine init); audit rows for the deleted acts are lost (cascade doesn't fire helper-side audit) | Low — straightforward; audit-loss for cascade-deleted acts is acceptable given quest-deletion audit row remains |
| (b) Explicit cleanup | Helper-driven; preserves per-act audit rows for the deletion | Verbose; `quest_delete` becomes a multi-step transaction | Low — implementation complexity |
| (c) Stranded acts | Lightest schema | Orphan rows accumulate; FK integrity broken; debugging surface gets noisy | High — schema rot; orphan rows in `dnd_quest_acts.quest_id` pointing to deleted quests |

**Recommended default: (a) ON DELETE CASCADE.**

**Reasoning:** Quest Layer v0's `quest_delete` is explicitly the operator orphan-cleanup tool (Finding 3 — operator runs `/quest delete <id>` to remove an orphan row produced by skeleton.md hook-title rename). At Composition v0, a "delete with orphan acts" scenario is identical — operator runs `/quest delete <id>` and wants the whole subtree gone. Cascade is the right semantic.

Audit-row loss for cascade-deleted acts is acceptable because the parent quest's `quest_delete` audit row carries the deletion event; per-act audit rows during a quest-delete are noise.

**Confidence: HIGH.** Schema-level FK semantic matches operator intent.

**Spec amendment implied at lock:** `dnd_quest_acts.quest_id INTEGER NOT NULL REFERENCES dnd_quests(id) ON DELETE CASCADE` + ensure `PRAGMA foreign_keys=ON` runs at engine init (verify in Session 3).

---

## §4. R6 forward-compat check on spec §4 + §5

**Per session brief:** confirm spec §5 (scene→act anchor persistence model) and §4 (compression-coupled suggester fire cadence) honor the R6 preservation finding correctly.

**Spec §5 audit:**
- §5 explicitly states: "Compression machinery does NOT touch `dnd_scene_state.current_act_id`. Compression writes only the in-memory `_scene_stale_turns` counter."
- §5 lists the five anchor-write triggers (accept / advance / set / deliver/fail/abandon / `/play` resume) and explicitly notes "Scene Lifecycle compression — anchor PERSISTS (no write)."
- ✅ Honors R6 finding correctly. No silent mutation surface.

**Spec §4 audit:**
- §4 fires `_dispatch_quest_act_suggester` AFTER Scene Lifecycle directive fires `tier=soft` or `tier=strong`. The dispatcher reads current state and proposes; it does NOT write.
- §4 implementation shape: "Soft-fail throughout per §59 contract."
- The suggester returning a proposal does NOT cause an act transition. Transition requires operator slash (`/quest act advance` or `/quest act set`).
- ✅ Honors R6 finding correctly. The suggester is read-only at the engine layer.

**Subtle gap check — what if the operator slashes `/quest act advance` IMMEDIATELY after suggester proposal posts to #dm-aside, on the same compression turn?**

This is fine. The suggester proposes on compression turn N; operator can slash on the same turn (treated as an immediate operator decision); engine writes `current_act_id` via `set_current_act` on turn N+1 (or same turn if slash fires before next prompt assembly). The compression machinery has already completed its writes (in-memory counter); the new `current_act_id` write doesn't conflict with compression because they're on different state surfaces.

**No R6 violation found.** Spec §4 + §5 are consistent with the recon evidence.

---

## §5. Operator + Oracle decisions

**At v0:** none required at lock-time for the recommended defaults.

**Walk-to-confirm:** §11.12 §1b fourth-instance anchoring — Code recommends (B) running-list footnote sub-pattern observation, NOT formal sub-pattern anchoring. Operator confirms or escalates to Oracle if they want (A) formal anchor or (C) no-pattern.

**Deferred to v0.x:** §11.7 predicate vocabulary expansion (to include `consequence_kind` or `npc_interaction`) if log signal shows operators routinely missing Act N→N+1 transitions at narrow vocabulary.

---

## §6. Summary of recommended defaults

| Decision | Recommended | Confidence | Spec implication |
|---|---|---|---|
| §11.1 | LOCKED Read B | — | Pre-decision, no walk |
| §11.2 | LOCKED (γ) hybrid | — | Pre-decision, no walk |
| §11.3 | (a) new `dnd_quest_acts` table | HIGH | Spec lean confirmed |
| §11.4 | (a) extend active-quest block | MEDIUM | Walk if operator wants visual separation |
| §11.5 | (a) single-active-act at v0 | MEDIUM | v1.x multi-active if friction surfaces |
| §11.6 | (a) structured markdown | HIGH | Spec lean confirmed |
| §11.7 | (a) narrow (scene_count + location_id) | HIGH | Synthesis confirms; Act 3 graceful degradation to operator-only |
| §11.8 | (a) extend `dnd_quests_audit` | HIGH | Spec lean confirmed |
| §11.9 | (b) compression-coupled | HIGH | Spec lean confirmed |
| §11.10 | (a) yes, render on resume | HIGH | Spec lean confirmed |
| §11.11 | (a) silent forward-compat | HIGH | Spec lean confirmed |
| §11.12 | Fourth-instance stands; (B) sub-pattern observation | MEDIUM | Walk-to-confirm; operator on sub-pattern naming |
| **§11.13 NEW** | (a) ON DELETE CASCADE | HIGH | Spec amendment at lock |

**HIGH (no synthesis pressure, proceed with recommended):** §11.3, §11.6, §11.7, §11.8, §11.9, §11.10, §11.11, §11.13 (8 decisions)
**MEDIUM (operator attention helpful, open axis named):** §11.4, §11.5, §11.12 (3 decisions)
**LOW:** 0
**LOCKED pre-decision:** §11.1, §11.2 (2 decisions)
**Walk-to-confirm:** §11.12 (sub-pattern naming)
**Spec amendments implied at lock:** §11.13 ON DELETE CASCADE on `dnd_quest_acts.quest_id` FK + ensure `PRAGMA foreign_keys=ON` at engine init

---

## §7. Surface additions

**§11.13 surfaced — Cascade delete: parent quest → acts.** Real gap. Quest Layer v0 precedent (Finding 3 orphan-cleanup via `/quest delete`) extends naturally; cascade is the right semantic. See §3.N walk.

**Spec refinements (not new §11 decisions):**
- §3 + §1.C add `quest_id INTEGER NOT NULL REFERENCES dnd_quests(id) ON DELETE CASCADE` to `dnd_quest_acts` schema definition
- Confirm `PRAGMA foreign_keys=ON` is set at engine init (may already be — Session 3 verifies)

**No §11.14+ surfaced.** Walking the 10 unlocked decisions did not expose additional unaddressed questions.

---

## §8. Handoff

| Field | Value |
|---|---|
| **Review doc** | `/home/jordaneal/virgil-docs/specs/COMPOSITION_LAYER_V0_REVIEW.md` |
| **PC mirror** | `/cygdrive/c/Users/Jordan/Documents/Virgil Project/specs/COMPOSITION_LAYER_V0_REVIEW.md` (push at session end) |
| **Decisions walked** | 10 unlocked (§11.3–§11.12) + 1 NEW (§11.13) = 11 walks; §11.1 + §11.2 LOCKED pre-decisions surfaced not walked |
| **HIGH confidence** | 8 (§11.3, §11.6, §11.7, §11.8, §11.9, §11.10, §11.11, §11.13) |
| **MEDIUM confidence** | 3 (§11.4, §11.5, §11.12) |
| **LOW confidence** | 0 |
| **LOCKED pre-decision** | 2 (§11.1 Read B, §11.2 γ hybrid) |
| **Walk-to-confirm** | 1 — §11.12 sub-pattern naming question (operator decides between (A) formal anchor / (B) running-list footnote observation / (C) no pattern). Code recommends (B). |
| **Operator + Oracle at v0** | 0 required at lock time |
| **§11.13 surfaced** | 1 NEW (cascade delete: parent quest → acts) |
| **R6 forward-compat finding** | Clean — spec §4 + §5 honor the R6 preservation evidence correctly; no silent mutation surface; suggester is read-only at engine layer |
| **Spec amendments implied at lock** | §11.13 ON DELETE CASCADE on `dnd_quest_acts.quest_id` FK; confirm `PRAGMA foreign_keys=ON` at engine init (Session 3 verify) |
| **HALT escalations** | 0 |
| **Next session** | Session 3 = implementation. Sonnet medium per WWC cadence (templated implementation against mature §59 sibling pattern with three precedents + mature §1b suggester pattern with three precedents). Operator confirms §11.12 (sub-pattern observation surfacing), locks all MEDIUM decisions per recommended default (or specifies override). Spec flips DRAFT → LOCKED with §11.13 amendment. |

---
