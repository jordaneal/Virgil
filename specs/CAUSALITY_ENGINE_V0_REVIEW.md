# CAUSALITY_ENGINE_V0_REVIEW.md

**Status:** REVIEW — Phase 2 (Path A review pass). Walks all 12 active §11 decisions + framing note on §11.13 long-horizon lifecycle + one surfaced addition (§11.14 faction deletion at v0). Not a lock. Operator reads, locks decisions, spec flips DRAFT → LOCKED before Session 3.

**Session:** S69 Path A Phase 2, May 14, 2026
**Spec reviewed:** `/home/jordaneal/virgil-docs/specs/CAUSALITY_ENGINE_V0_SPEC.md` (DRAFT)
**Basis:** `planner-scratch/causality_engine_v0_sketch.md`, DOCTRINE §1a/§1b/§17/§59/§76, `CANON_BOOTSTRAP_BOT_V0_SPEC.md` LOCKED §11.8 (forward-coupling), `QUEST_LAYER_V0_SPEC.md` LOCKED + v0.1 patch (§1.C Finding 3 rename precedent), `COMPOSITION_LAYER_V0_SPEC.md` LOCKED + v0.x patch (§11.7 narrow predicate vocabulary precedent), `SCENE_LIFECYCLE_V1_SPEC.md` LOCKED (§11.D hard-tier compression integration), six R-findings from Phase 1 recon.

**Format per decision:** question restatement → candidates → trade-offs table (pros / cons / risk per candidate) → recommended default + confidence → open axis named (MEDIUM/LOW only).

---

## §1. Inventory note before walking

**No HALT triggered.** No decision walk surfaced a finding that invalidates v0 architectural shape. Spec drafting integrated all six recon findings cleanly; §4 R-finding integration check below confirms each finding maps to a §11 decision or §1 lock.

**One §11.14 surfaced.** Walking §11.5 (`/faction seed` rename handling per Quest Layer Finding 3 precedent) surfaced a downstream dependency: operator needs `/faction delete` to clean up rename orphans. Spec §1.K lists 7 slashes without `/faction delete`. Surfacing as §11.14 for operator lock. See §3.14.

**Sub-decision sweep.** No §1-level sub-decisions analogous to Quest Layer's §1.B alias-vs-migrate or Composition Layer's §11.13 cascade-delete surfaced beyond the §11.14 deletion question above. The spec's §1.A through §1.L recommendations all stand at REVIEW; no walk pressure to flip a §1 lean.

**Forward-coupling notes carried from spec:**
- §1.A (schema delta) ships FK columns on `dnd_quests` and `dnd_npcs` — Quest Layer v0 §12.2 (faction modeling deferred to v1.x) is closed at S69 ship.
- §1.H stage-prose authoring is `default-then-edit` at v0; N-10 v0.2 bootstrap-card-extension filed as §12.2 forward.
- Scene Lifecycle v1 compression-fire path needs new hook for `event_source='scene_compress'` per §1.C (S69 implementation owns the hook).

**External review refinement #2 lock check.** Spec §1.D + §4.3 + §5.3 locks predicate vocabulary to four keys with structured-FK-lookup engagement signals only (no LLM extraction). §11.4 walk confirms preservation of determinism without breaking authoring expressiveness for v0 needs.

**External review refinement #3 (long-horizon lifecycle).** §11.13 framing note included in this review per brief explicit instruction — surfaces the concept space (dormant / stabilized / simmering / cyclical faction states) for v1.x doctrinal awareness without proposing v0 implementation. Not a walk with candidates.

---

## §2. Summary table

| Decision | Question | Recommended | Confidence | Notes |
|---|---|---|---|---|
| §11.1 | Schema scope | (a) minimum-plus-FKs | HIGH | R4 makes (b) untenable; (c) is v2+ |
| §11.2 | **Hard-progression at v0** | (a) capability ships, opt-in default | HIGH | Schema additive; opt-in friction makes intent explicit — see §3.2 |
| §11.3 | Tick trigger event set | (a) five sources | MEDIUM | Tick density tunable per faction via cooldown — open axis |
| §11.4 | Predicate vocabulary | (a) narrow 4-key | HIGH | Composition v0 §11.7 precedent; external review #2 lock |
| §11.5 | **`/faction seed` rename handling** | (a) new row + orphan (mirror Quest Layer Finding 3) | HIGH | Surfaces §11.14 dependency — see §3.5 |
| §11.6 | **Stage-prose authoring at v0** | (a) default-then-edit | HIGH | (b) chains S69 to N-10 v0.2 unnecessarily — see §3.6 |
| §11.7 | Operator override gates | (a) confirmation required for hard-progression `/faction reset` | HIGH | §19 two-gate destruction precedent |
| §11.8 | Faction → consequence integration | (a) render directly via pressure directive | MEDIUM | (c) hybrid is v1.x candidate — open axis |
| §11.9 | Visibility transition thresholds | (a) default 1=unknown, 2=rumored, 3+=known, final=resolved | HIGH | Simple deterministic rule; operator override available |
| §11.10 | §1b suggester at v0 | (a) NO at v0 | HIGH | Engine-deterministic ticks; `/faction hold` is escape hatch |
| §11.11 | Forward-compatibility | (a) silent (no schema stubs) | HIGH | Composition v0 §11.11 precedent |
| §11.12 | N-10 faction card count | (a) keep at 1-2 per bootstrap | MEDIUM | Observed-friction tuning post-S69 |
| §11.13 | Long-horizon lifecycle | **(framing note only — filed v1.x)** | — | Per external review refinement #3; not a v0 lock |
| **§11.14** | **Faction deletion at v0 — NEW** | **(c) ship `/faction delete` with FK dependent-cleanup** | **HIGH** | Required for §11.5 (a) orphan cleanup — see §3.14 |

**Split:** 9 HIGH · 3 MEDIUM · 0 LOW · 0 operator+Oracle required at v0 · §11.13 filed framing-only · §11.14 newly surfaced.

---

## §3. Full decision walk

---

### §3.1 — Schema scope: minimum-plus-FKs

**Question:** Ship `dnd_factions` + `dnd_faction_audit` only, or add FK columns on `dnd_quests` + `dnd_npcs`, or extend further (relationships, NPC rosters)?

**Candidates:**
- **(a) Minimum-plus-FKs** — `dnd_factions` + `dnd_faction_audit` + additive `dnd_quests.associated_faction_id` + `dnd_npcs.affiliated_faction_id`.
- (b) Faction tables only — defer FKs to v1.x.
- (c) Extended schema — include relationship matrix, NPC member roster, faction-to-faction reactions.

| Candidate | Pros | Cons | Risk |
|---|---|---|---|
| **(a) Minimum-plus-FKs** | Makes engagement-signal predicate vocabulary functional (per §1.D and R4); Quest Layer v0 §12.2 closure at S69 ship; additive columns preserve back-compat | Schema delta is wider than just `dnd_factions` (3 tables + 2 column adds) | Low — one DDL pass at engine init; all additive; NULL defaults preserve existing rows |
| (b) Tables only | Tightest v0 schema delta | Predicate vocabulary collapses to operator-commands-only without FKs (R4 evidence) — defeats "inaction becomes observable" product delta | High — locks v0 into operator-driven ticks only; engagement-signal predicates ineffective until later schema delta |
| (c) Extended | Forward-compatible with relationship matrices and member rosters | v2+ temptation per sketch §11.1; schema bloat at v0; columns rot if v1.x design diverges | High — over-commits at v0; schema decisions for relationship semantics belong in their own spec |

**Recommended default: (a) minimum-plus-FKs.**

**Reasoning:** Per spec §1.A. R4 evidence confirms 3 of 4 engagement-signal sources have schema gaps; only ships at (a) makes the load-bearing predicate vocabulary functional. (b) defeats the product delta. (c) is v2+ temptation.

**Confidence: HIGH.** Spec lean confirmed.

---

### §3.2 — Hard-progression at v0 (DEEP SYNTHESIS PER BRIEF)

**Question:** Does S69 v0 ship hard-progression capability (with opt-in default), or defer entirely to v1.x?

**Candidates:**
- **(a) Capability ships, default protect-solo** — `pressure_kind` column accepts both `'atmospheric'` and `'hard_progression'`; defaults to atmospheric; operator opts in per faction via `/faction set kind:hard_progression`.
- (b) Defer entirely to v1.x — v0 schema doesn't include `pressure_kind` column; atmospheric-only at v0; v1.x adds capability + schema migration.

| Candidate | Pros | Cons | Risk |
|---|---|---|---|
| **(a) Capability ships, opt-in default** | Schema is one column-value at v0; no v1.x schema migration to add hard-progression later; confirmation gate on `/faction reset` already part of §11.7 lock; atmospheric default protects solo per §1.B; `pressure_kind` doubles as a `total_stages` and visibility-priority signal (hard-progression renders first per §6.2 cap-priority) | Adds a v0 capability that may not be exercised in early playtests; opt-in path is still v0 surface | Low — schema is additive enum; opt-in friction (per-faction `/faction set kind:hard_progression`) is the explicit-acknowledgment gate |
| (b) Defer to v1.x | Tighter v0 scope (purely atmospheric); hard-progression decision can be informed by observed play; "ship-and-watch" discipline | v1.x adds `pressure_kind` column via schema migration AND adds the per-faction opt-in surface; doubles ship cost; revisiting `dnd_factions` post-ship re-engages §76 audit and changes the §6 pressure directive cap-priority logic | Medium — chains two ships; v1.x re-touches v0 schema |

**Synthesis (per brief — forward-compatibility benefit vs scope-discipline concern):**

The architectural intuition behind (a) is **schema forward-compatibility at minimal v0 cost**. The `pressure_kind` column is a single TEXT enum default `'atmospheric'`. The opt-in path (`/faction set kind:hard_progression`) is the explicit-acknowledgment gate that doctrinally rejects accidental campaign-state destruction. Solo-bard protection ships via atmospheric-bias defaults regardless of (a) or (b); they're orthogonal.

The cost of (b) is **doubled schema work**. At v1.x, adding `pressure_kind` means:
1. New `ALTER TABLE` migration at engine init.
2. New §76 audit pass on the column.
3. New `/faction set kind:hard_progression` slash (delta to v0's `/faction set`).
4. New §6 pressure directive cap-priority logic (currently sorts atmospheric-only).
5. Re-engagement with the operator on what hard-progression means.

The cost of (a) is **a column-value default that may not be exercised**. If no operator opts in across early playtests, the column sits as `'atmospheric'` for every faction. That's not scope creep — it's reserved capacity.

**Scope-discipline concern check:** does shipping hard-progression-capability invite scope creep into v0? Specifically, does `/faction set kind:hard_progression` lead to operator authoring elaborate hard-progression factions before observed friction informs how that should look?

Yes, partially — but the opt-in friction (typing the kind change explicitly + the confirmation gate on subsequent `/faction reset`) is the discipline rail. An operator who opts in is making an explicit campaign-stakes decision. v0 ships the rails; observed friction tunes whether the rails need tightening.

**Solo-bard protection check:** does (a) risk solo-player campaign-state destruction? No, because atmospheric is the default. Hard-progression requires an explicit operator action per faction. The "default protect-solo" framing is the load-bearing safety rail.

**Recommended default: (a) capability ships with opt-in default.**

**Reasoning:** Forward-compatibility benefit is real (no v1.x schema migration); scope-discipline concern is mitigated by opt-in friction and confirmation gates on destructive operations. Atmospheric default preserves solo-bard immersion architecture per external review framing #1. The `pressure_kind` column has clear semantic distinct from `total_stages`/`visibility`/`current_stage` — not a duplicated surface.

**Confidence: HIGH.** Spec lean confirmed. The scope-discipline concern is real but already mitigated structurally (opt-in friction + confirmation gates). Operator may want stricter (b) defer — that's a campaign-stakes preference axis, not a doctrinal one. Walk surfaces both for operator decision.

---

### §3.3 — Tick trigger event set

**Question:** Which engine events fire faction tick evaluation?

**Candidates:**
- **(a) Five sources** — `travel`, `rest_long`, `advance`, `scene_compress`, `manual_tick`.
- (b) Three sources — `rest_long`, `scene_compress`, `manual_tick` (drop `travel` + `advance` as too frequent).
- (c) Single source — `manual_tick` only (operator-driven entirely).

| Candidate | Pros | Cons | Risk |
|---|---|---|---|
| **(a) Five sources** | Engine-recognized story-scale events trigger world motion; per-faction `min_turns_since_last_advance` cooldown tunes density; covers reasonable session pacing (travels + rests + compressions + occasional manual override) | Tick density per session could exceed target (1-3 advancements across factions) if multiple `/travel` calls + rests fire | Medium — cooldown is the throttle; default `min_turns_since_last_advance` needs sensible value (operator-tunable per faction) |
| (b) Three sources | Tighter density at v0; `travel` removal eliminates short-trip overcounting | Drops `travel` as tick source = world doesn't advance when party travels between locations (counterintuitive); `/advance` removal eliminates explicit operator pacing | Medium — operator-feedback may reveal that travel-driven world advancement IS expected behavior; restoring later requires §11 revisit |
| (c) Single source | Fully operator-driven; no engine-mediated advancement | Defeats "inaction becomes observable" — manual_tick requires operator-typed action; without engine ticks, faction state stays static when party does nothing | High — defeats load-bearing product delta |

**Recommended default: (a) five sources.**

**Reasoning:** Per spec §1.C. Story-scale temporal events (rests + travels + compressions + operator advances) are the right granularity. Per-faction cooldown is the density-management knob. Operator can tune cooldown to taste.

**Confidence: MEDIUM.** Open axis: **observed tick density in live signal.** If post-S69 playtests show >5 ticks/session across all factions, recommend operator tuning default `min_turns_since_last_advance` upward or considering (b) — drop `travel` as trigger. Tunable post-ship via per-faction predicate or via the slash that updates default predicates for new factions.

---

### §3.4 — Predicate vocabulary breadth (narrow at v0)

**Question:** Which keys does `tick_predicate_json` accept?

**Candidates:**
- **(a) Narrow 4 keys** — `min_turns_since_last_advance`, `event_source_required`, `engagement_signal_required`, `engagement_signal_blocks`.
- (b) Broader — add `npc_interaction`, `consequence_kind`, `location_visit`, `combat_outcome`.
- (c) Open vocab — arbitrary keys parsed at evaluation time.

| Candidate | Pros | Cons | Risk |
|---|---|---|---|
| **(a) Narrow 4 keys** | Composition Layer v0 §11.7 precedent (narrow vocabulary ships first); external review refinement #2 explicit lock (structured FK lookups only, no LLM extraction); deterministic + §1a clean; operator authoring scope tight | Cannot express "ticks faster on NPC death" or "ticks on location visit" at v0; some operator-authoring patterns blocked | Low — observed-friction post-S69 informs whether vocabulary expansion is needed; v1.x extension is additive (new keys; existing predicates still parse) |
| (b) Broader | Richer predicate expressiveness at v0 | Each additional key needs structured-surface lookup logic; without `dnd_consequences.npc_id` indexing or `dnd_locations.last_visited_turn` columns, some keys fire on non-structured data → §1a concern | Medium — each broader key opens an evaluation surface that needs §1a audit |
| (c) Open vocab | Maximum flexibility | LLM-extracted keys become possible (operator authors `"npc_betrayed_party": true` predicate from prose); breaks external review refinement #2 lock | High — defeats determinism guarantee; ships with arbitrary semantic inference surfaces |

**Tightening preservation check (per brief explicit attention):**

The 4-key narrow vocabulary expresses:
- "Cooldown N turns" → `min_turns_since_last_advance: 12` ✓
- "Only ticks on long rest" → `event_source_required: "rest_long"` ✓
- "Doesn't tick when party engages with Crystal Cave quest" → `engagement_signal_blocks: "quest:Investigate Crystal Cave"` ✓
- "Ticks ONLY when party engages with Iron Vein investigation" → `engagement_signal_required: "quest:Investigate Iron Vein"` ✓

CANNOT be expressed at v0:
- "Ticks faster when an affiliated NPC has been killed" — no NPC-death key
- "Ticks on location visit" — no location-visit key
- "Ticks on consequence-of-kind" — no consequence-coupling
- "Ticks when party engages with multiple quests" — no multi-quest AND-logic

All four blocked patterns are §12 forward-files. The narrow vocabulary IS sufficient for the load-bearing v0 mechanism (engagement-signal-blocks for solo protection + cooldown + event-source filter). v1.x extension is additive — new keys are recognized at evaluation time; existing predicates with old keys continue to parse correctly.

**Determinism preservation check:**
- All four keys evaluate against deterministic SQL queries (cooldown vs `last_advanced_at` int compare; `event_source_required` vs `_VALID_TIME_SOURCES` enum compare; engagement signals via `dnd_quests` / `dnd_npcs` FK lookups).
- Zero LLM calls in predicate evaluation. Zero semantic inference. Zero phrase-vocabulary matching.

**§1a clean:** engine writes faction state; LLM only reads. No LLM-decided binding state transitions.

**Recommended default: (a) narrow 4 keys.**

**Reasoning:** Spec §1.D + Composition v0 §11.7 precedent. External review refinement #2 lock preserved. v0 ships sufficient expressiveness for load-bearing solo-protection mechanism; v1.x extension is additive without breaking existing predicates.

**Confidence: HIGH.** Spec lean confirmed; tightening preserves determinism without breaking authoring expressiveness for v0 needs.

---

### §3.5 — `/faction seed` rename handling (DEEP SYNTHESIS PER BRIEF)

**Question:** When operator renames a faction in skeleton.md mid-campaign and re-runs `/faction seed`, what happens to the original-name `dnd_factions` row?

**Candidates:**
- **(a) New row + orphan old row** — renamed faction inserts as new `dnd_factions` row with `skeleton_origin=1`; original-name row persists with `skeleton_origin=1`; operator cleans up via `/faction delete <old_id>` (mirrors Quest Layer Finding 3 precedent).
- (b) UPDATE on FK match — engine detects rename via fuzzy matching (or via FK references from other tables) and updates the existing row's `name`; no orphan accumulates.
- (c) Error requiring operator manual `/faction reset` — engine refuses to insert because original-name still exists; operator must explicitly resolve the rename.

| Candidate | Pros | Cons | Risk |
|---|---|---|---|
| **(a) New row + orphan** | Matches Quest Layer Finding 3 precedent (mature operator-side cleanup); preserves audit history of the original faction; operator decides whether the rename is rename-as-restructure or rename-as-replacement; deterministic insert behavior | Operator must clean up orphans via `/faction delete` (introduces §11.14 dependency — see below); `/faction list` shows stale entries until cleanup; FK references on `dnd_quests`/`dnd_npcs` may still point to original-id (operator must update or accept dangling) | Low — precedent is mature; FK-cleanup story is §11.14 (newly surfaced) |
| (b) UPDATE on FK match | No orphans accumulate; renames are seamless | Requires reliable rename-vs-new detection (fuzzy matching has FP risk); conflates rename with mid-campaign restructure (operator renaming "Iron Vein Cartel" → "Crystal Vein Cartel" — is this a rename or a new faction with similar name?); no precedent in project | High — fuzzy-matching infrastructure doesn't exist; FP risk corrupts faction state silently |
| (c) Error requiring manual resolution | Explicit operator decision per case | Friction on every skeleton.md edit; operator must inspect diffs and act before re-seeding; defeats `/faction seed` idempotency | Medium — adds friction without compensating gain; operator-feedback would likely shift to (a) within first playtest |

**Synthesis (per brief — consistency-with-precedent vs UX of automated handling):**

The architectural intuition behind (a) is **consistency with Quest Layer v0 Finding 3 precedent**. Quest Layer locked (a) — rename-as-new-row with orphan persistence — and the precedent is mature post-v0.1. Operator-side cleanup via `/quest delete <old_id>` is well-understood and documented in `/quest seed-skeleton` docstring.

(b) UPDATE on FK match has no precedent infrastructure. Fuzzy-matching skeleton.md names against existing rows would require:
1. Levenshtein or similar string-distance metric.
2. Threshold tuning (per Quest Layer v0.1 S57 patch which DROPPED cosine-similarity precedent for similar reasons).
3. False-positive recovery (operator must un-do an incorrect rename match).

The S57 cosine-similarity drop is direct precedent — calibration-bound fuzzy matching was rejected for Quest Layer v0.1 because deterministic-only validators are the doctrinal pattern. (b) would re-introduce that pattern at v0.

(c) explicit-resolution adds friction without compensating gain. Quest Layer's `/quest seed-skeleton` ships as idempotent-with-orphan-acknowledgment; operator-feedback affirmed this pattern.

**Surfaced dependency:** (a) requires `/faction delete <id>` for orphan cleanup. Spec §1.K lists 7 slashes; `/faction delete` is NOT among them. **This surfaces §11.14 below** — operator needs faction-deletion at v0 to complete the §11.5 (a) loop.

**Recommended default: (a) new row + orphan.**

**Reasoning:** Quest Layer Finding 3 precedent is mature. Cosine-similarity precedent (S57) doctrinally rejects (b). (c) adds friction. Operator-side cleanup is the right surface for ambiguous renames.

**Confidence: HIGH.** Spec lean confirmed; §11.14 dependency surfaced for separate decision.

---

### §3.6 — Stage prose authoring at v0 (DEEP SYNTHESIS PER BRIEF)

**Question:** How does `current_stage_description` get authored per stage at v0?

**Candidates:**
- **(a) Default-placeholder with operator-edit affordance** — migration default copies `goal` to `current_stage_description`; operator edits via `/faction set stage_description:"<text>" <faction_id> <stage>` slash command per stage.
- (b) N-10 v0.2 coupling — S69 ship gates on N-10 v0.2 spec/implementation that adds bootstrap-card per-stage prose authoring.
- (c) Defer stage-prose entirely — `current_stage_description` is empty at v0; pressure directive renders only faction name + visibility + stage number ("Iron Vein Cartel (rumored, Stage 2)").

| Candidate | Pros | Cons | Risk |
|---|---|---|---|
| **(a) Default-then-edit** | Ships v0 atomically with no N-10 dependency; operator authoring flow via slash is explicit; migration default = `goal` copy makes first-stage render meaningful immediately; operator-author later when narrative warrants per-stage divergence; same shape as Composition Layer §1.D `set_current_act` operator surface | Stages 2-4 are placeholder text (= goal text) until operator authors per-stage divergence; pressure directive output may feel thin in newly-bootstrapped campaigns until operator edits | Medium — operator may not edit per-stage prose; default placeholder yields generic-feeling pressure renders for staged-but-undifferentiated factions |
| (b) N-10 v0.2 coupling | Stages authored at bootstrap time = best UX; pressure directive output rich from session 1 | Chains two ships — N-10 v0.2 spec + implementation must ship before S69; N-10 v0.2 bootstrap-card complexity expands (4 per-stage prose inputs per faction × 4 stages = 16 fields); couples S69 timing to N-10 schedule | Medium — chains ship dependencies; N-10 v0.2 may surface its own §11 decisions; S69 timing slips |
| (c) Defer stage-prose | Thinnest v0; less ship surface | Pressure directive renders fall back to faction-name-and-stage-number only; defeats the per-stage architectural distinction (atmospheric pressure is supposed to evolve in narrated tone, not just numeric stage); §6.2 body example becomes infeasible | High — defeats load-bearing pressure-directive expressiveness |

**Synthesis (per brief — atomic v0 ship vs chained ships vs thin output):**

The architectural intuition behind (a) is **atomic v0 ship with operator-authoring affordance**. S69 ships independently; the operator-author flow is one slash command (`/faction set stage_description`) that's part of the v0 slash surface. The migration default copy of `goal` ensures pressure directive renders are immediately meaningful (Stage 1 narration = "The Iron Vein Cartel is consolidating its hold on the eastern shipping lanes" = the authored goal text). Operator edits per-stage divergence when narrative requires it.

(b) N-10 v0.2 coupling is **schedule entanglement**. N-10 ships first → N-10 v0.2 ships second → S69 ships third. The N-10 v0.2 bootstrap card asks operator for per-stage prose at faction-card-approval-time = 4+ additional prose fields per faction. That's significant bootstrap UX expansion, and N-10 v0.2 has its own spec/review cycle. S69 ship slips by ~2 spec cycles minimum.

(c) defer is **pressure-directive output collapse**. The whole point of staged factions is that the world's pressure evolves in narrated tone — "rumors are starting to spread" → "the harbor watch is on high alert" → "the cartel openly controls the docks." Without per-stage prose, the LLM renders only "Iron Vein Cartel (rumored, Stage 2)" — the LLM has no anchor for what Stage 2 vs Stage 3 means narratively. The pressure directive becomes a numeric indicator, not an atmospheric texture.

**Operator-edit-flow concerns (per brief):**
- Does operator actually want to edit per-stage prose post-migration? Possible operator-feedback signal post-S69: many operators leave Stages 2-4 as placeholder (= goal text). Mitigation: operator can author per-stage prose during the same session they review `/faction list` post-bootstrap; not a separate authoring pass.
- Is the slash command UX usable? `/faction set stage_description:"<text>" <faction_id> <stage>` is straightforward; same shape as `/quest add summary:"..."`.

**Pressure-directive thinness concern (per brief):**
- (a) Stage 1 renders meaningful (default = goal copy).
- Stages 2-4 render with default-placeholder until edited. Pressure-directive body still renders something (placeholder text), not nothing.
- Observed-friction signal post-S69: are operators editing per-stage prose, or leaving placeholders?

**Recommended default: (a) default-then-edit.**

**Reasoning:** Per spec §1.H. Atomic v0 ship; no N-10 v0.2 chain; operator-author affordance is one slash command. (b) chains ships unnecessarily; observed-friction post-S69 informs whether N-10 v0.2 coupling is worth doing. (c) defeats the per-stage architectural distinction.

**Confidence: HIGH.** Spec lean confirmed. Walk did not surface operator-edit-flow concerns that argue for (b). N-10 v0.2 stage-authoring extension is filed §12.2 forward.

---

### §3.7 — Operator override gates for hard-progression

**Question:** Does `/faction reset` on a hard-progression faction require confirmation?

**Candidates:**
- **(a) Confirmation required** — two-gate destruction per §19 doctrine; `/faction reset` on `pressure_kind='hard_progression'` faction prompts ephemeral confirmation before write.
- (b) No confirmation — operator authority is sufficient.
- (c) Confirmation required only when stage decreases (not when increases).

| Candidate | Pros | Cons | Risk |
|---|---|---|---|
| **(a) Confirmation required** | §19 two-gate destruction precedent; hard-progression is irreversible-by-definition; confirmation gate makes operator intent explicit; precedent across project (`/quest delete`, `/purgecampaign`) | Operator types confirmation slash twice for routine narrative-driven hard-progression resets | Low — confirmation friction is exactly the right gate for irreversible operations |
| (b) No confirmation | Lower friction | Accidental campaign-state mutation risk; hard-progression irreversibility means an unintended reset has narrative consequences | High — single-gate destruction is the failure mode §19 was created to close |
| (c) Confirmation only on decrease | Smart gate (only the truly destructive direction needs confirmation) | Stage increases on hard-progression factions are also irreversible-by-progression; the "decrease" framing doesn't match hard-progression semantics (where forward IS destruction) | Medium — confuses operator intent gating |

**Recommended default: (a) confirmation required.**

**Reasoning:** Per spec §1.K + §19 doctrine. Hard-progression by definition is irreversible. Mirrors `/quest delete`, `/purgecampaign` two-gate precedent. Confirmation friction is appropriate at this surface.

**Confidence: HIGH.**

---

### §3.8 — Faction → consequence ledger integration

**Question:** Does atmospheric pressure write to `dnd_consequences` ledger on stage advance, or render directly via pressure directive only?

**Candidates:**
- **(a) Render directly via pressure directive** — no consequence ledger write on faction advance.
- (b) Write consequence row on every faction advance — feeds NPC-side visibility (NPCs can reference faction state shifts in conversation).
- (c) Hybrid — write consequence row only on visibility transition (unknown→rumored, rumored→known, known→resolved).

| Candidate | Pros | Cons | Risk |
|---|---|---|---|
| **(a) Render directly** | Cleaner separation of surfaces; consequence ledger stays focused on direct NPC interactions; pressure directive is the dedicated faction-render surface | NPCs in conversation don't reference faction state changes (faction context invisible at NPC level); operator may want faction-state-shift to feel like it lands at NPC interactions | Low — operator can author NPC dialogue references manually via `/npc set description` if needed |
| (b) Consequence-on-every-tick | Maximum NPC-side visibility | Floods consequence ledger with faction noise; consequence directive cap (3 lines) competes with faction count; conflates two distinct ledger semantics | High — consequence directive degrades from "direct NPC interactions" to "world-state changes including faction ticks" |
| (c) Hybrid (visibility-transition only) | NPCs reference visibility transitions (~3 per faction lifecycle); consequence ledger noise is bounded | Adds coupling complexity at v0; v0 ships with two render surfaces (pressure directive + consequence ledger) both touching faction state | Medium — coupling adds §17 audit overhead; visibility transitions are sparse (3 per faction) but coupling is permanent |

**Recommended default: (a) render directly via pressure directive.**

**Reasoning:** Per spec §1.J + sketch §11.6. Cleaner separation of surfaces at v0; consequence ledger stays focused on direct NPC interactions. (c) is an interesting v1.x candidate — making faction visibility transitions visible at the NPC level — but adds coupling complexity at v0.

**Confidence: MEDIUM.** Open axis: **operator desire for NPC-side faction visibility.** If operator-feedback post-S69 shows NPCs feel disconnected from faction state (e.g., NPCs continue acting as if the cartel isn't escalating even though pressure directive renders Stage 3), recommend (c) hybrid for v1.x — visibility transitions write `kind='faction_state_shift'` consequence rows so NPCs reference the world's changing pressure during conversations.

---

### §3.9 — Visibility transition thresholds

**Question:** Stage thresholds for auto-visibility transitions?

**Candidates:**
- **(a) Default thresholds** — Stage 1=unknown, Stage 2=rumored, Stage 3+=known, Final=resolved.
- (b) Configurable per faction via `tick_predicate_json.visibility_thresholds`.
- (c) Manual only — engine never auto-transitions visibility.

| Candidate | Pros | Cons | Risk |
|---|---|---|---|
| **(a) Default thresholds** | Simple deterministic rule; operator override via `/faction visibility` available for narrative reasons; preserves visibility-gating-as-immersion-architecture (sketch §7) | Some campaigns may want different thresholds (e.g., long arc where Stage 3 should still feel rumored) | Low — operator override is available per faction; default suits 80% of operator authoring intent |
| (b) Per-faction configurable | Maximum flexibility | Adds vocabulary to `tick_predicate_json` (predicate gets visibility-rule-mixed-into-tick-rule semantics); breaks separation of tick-evaluation from visibility-transition | Medium — semantic overload of `tick_predicate_json`; predicate vocabulary expands beyond the 4-key §11.4 lock |
| (c) Manual only | Maximum operator control | Operator must remember to transition visibility per faction advance; defeats automated immersion-architecture; observability friction (operator must inspect each faction's stage to decide visibility) | Medium — operator-authoring friction; defeats the auto-flow design |

**Recommended default: (a) default thresholds.**

**Reasoning:** Per spec §1.F. Simple deterministic rule. Operator override available per faction via `/faction visibility`. Configurable thresholds (b) is v1.x if observed friction surfaces — but it overlaps `tick_predicate_json` semantics and probably wants its own visibility-config column rather than predicate-key extension.

**Confidence: HIGH.**

---

### §3.10 — §1b suggester pattern: NO at v0

**Question:** Should faction ticks fire via `#dm-aside` suggester ("Iron Vein Cartel is eligible to advance — approve with /faction tick?")?

**Candidates:**
- **(a) NO at v0** — engine-deterministic ticks; operator escape hatch is `/faction hold`.
- (b) YES — suggester for every tick proposal.
- (c) Hybrid — suggester for hard-progression ticks only.

| Candidate | Pros | Cons | Risk |
|---|---|---|---|
| **(a) NO at v0** | Tick events already operator-driven (rests, travel, compression); engine-determinism preserved; `/faction hold` is the precision escape hatch (per-faction pause) | Operator doesn't get visibility into each tick before it fires; quick session-pacing changes may surprise operator | Low — telemetry (`faction_advanced:` log) gives operator post-tick visibility; `/faction hold` covers pre-tick pause |
| (b) YES (every tick) | Maximum operator visibility into pending state changes | Adds approval gate per tick; multiple ticks per session = multiple confirmation actions; defeats engine-determinism + adds friction at high-frequency surface | High — operator UX degrades; pattern collapses ticks into operator-typed sequences |
| (c) Hybrid (hard-progression only) | Hard-progression ticks get visibility (irreversible state mutations) without flooding the surface for atmospheric ticks | Adds branching to tick-evaluation flow; hard-progression already has §11.7 confirmation gate at reset — adding pre-tick confirmation duplicates the gate | Medium — overlapping gates create confusion; operator already confirms hard-progression at opt-in time and at reset time; adding tick-time confirmation is third gate |

**Recommended default: (a) NO at v0.**

**Reasoning:** Per spec §1.J + sketch §11.10. Tick events are already operator-driven at the trigger layer (rests, travel, compression). `/faction hold` covers pause needs. (b) and (c) add gates without commensurate gain.

**Confidence: HIGH.**

**Walk-to-confirm:** if operator wants notification visibility (not approval gate) post-tick, that's a different shape than §1b suggester — file as v1.x notification-card candidate (`§12.12` already filed for this).

---

### §3.11 — Composition forward-compatibility: silent

**Question:** Does S69 schema pre-couple to v1.x candidates (relationships, NPC rosters, resource sim)?

**Candidates:**
- **(a) Silent — no pre-coupling at schema layer.**
- (b) Stub columns for v1.x — `relationship_matrix_json`, `member_npc_ids`, etc.

| Candidate | Pros | Cons | Risk |
|---|---|---|---|
| **(a) Silent** | Composition v0 §11.11 precedent; schema doesn't pre-commit; observed-friction drives what ships next | Schema migration needed for each v1.x feature that adds a column | Low — additive migrations are routine (every prior schema delta in the project has been additive) |
| (b) Stub columns | Forward-compat at schema layer | Stub columns rot; v1.x design diverges from anticipated shape; columns become dead weight | High — over-commits at v0; column semantics get locked before they're understood |

**Recommended default: (a) silent.**

**Reasoning:** Per spec §1.L + Composition v0 §11.11 precedent. Stub columns rot. Observed friction post-S69 drives what ships next.

**Confidence: HIGH.**

---

### §3.12 — Initial faction count at N-10 bootstrap

**Question:** Should N-10's faction card count change with S69 ship?

**Candidates:**
- **(a) Keep at 1-2 factions per bootstrap** — current N-10 v0/v0.1 default.
- (b) Bump to 2-3 — encourage more factions per campaign.
- (c) Make operator-configurable at bootstrap time.

| Candidate | Pros | Cons | Risk |
|---|---|---|---|
| **(a) Keep at 1-2** | No N-10 change required at S69 ship; observed-friction tunes whether more factions per campaign useful | May feel sparse for campaigns where multiple factions are desired | Low — operator can author additional factions in skeleton.md OR via `/faction add` slash post-bootstrap |
| (b) Bump to 2-3 | More factions = more pressure variety from session 1 | Requires N-10 change (card sequence + faction-card count update); operator may not want 3 factions at session 1 (overwhelming) | Medium — N-10 change couples S69 to bootstrap card UX; tuning is observed-friction territory |
| (c) Operator-configurable | Maximum operator control at bootstrap time | Adds bootstrap UX surface (per-card-type count input); operator may not have intuition about right count at premise-only authoring time | Medium — adds operator burden at the load-bearing N-10 friction point (sketch §1.D framing) |

**Recommended default: (a) keep at 1-2.**

**Reasoning:** Per spec §1.L + sketch §11.12. Observed-friction reveals whether more factions per campaign useful. v0 ships with current N-10 default; tuning is v0.x patch territory.

**Confidence: MEDIUM.** Open axis: **observed faction-volume preference in post-S69 playtests.** If operators routinely author additional factions via `/faction add` post-bootstrap (especially in first sessions), recommend bumping N-10 default to (b).

---

### §3.13 — Long-horizon faction lifecycle (FRAMING NOTE — FILED, NOT WALKED)

**Per external review refinement #3 + spec §11.13:** filed-not-sequenced.

**Concept space for v1.x doctrinal awareness:**

With v0's pure sequential advancement, factions reach a terminal `resolved` state and stay there forever. Long-horizon campaigns accumulate frozen `resolved` factions as historical records in `dnd_factions` table. The world's pressure inventory grows monotonically; no faction state ever recycles.

Concept candidates for v1.x exploration (NOT v0 decisions):
- **Dormant** — `resolved` factions can re-enter active state on narrative trigger (operator-driven via `/faction reset` to a new starting stage, or engine-driven via a new "wake" condition predicate).
- **Stabilized** — `resolved` factions stay quiescent indefinitely but operator can re-activate via slash; visible in `/faction list` as historical.
- **Simmering** — sub-resolved state where pressure is low but non-zero; visible in pressure directive at minimal cadence.
- **Cyclical** — pressure builds → resolves → re-builds with seasonal or session-cadence patterns.
- **Pressure-recycling** — resolved faction's pressure feeds a successor faction; old pressure becomes new pressure substrate.

These are NOT v0 ship requirements. v0 ships with pure sequential advancement and `resolved` as terminal stage. Long-horizon entropy is acknowledged structurally; the design choice of which lifecycle shape (above) earns priority is observed-friction-gated to post-S69 play.

**Recommendation: defer to v1.x.** No spec lock required at v0 review.

**Walk-to-confirm:** operator confirms (e) — `resolved` factions persist as historical record at v0 — is acceptable. v1.x lifecycle design pass owns the long-horizon choice when observed friction surfaces.

---

### §3.14 — Faction deletion at v0 (NEW — surfaced during §11.5 walk)

**Question:** Does S69 v0 ship a `/faction delete <id>` slash command for orphan cleanup and operator-driven removal?

**Background:** §11.5 (a) lean — `/faction seed` rename produces an orphan `dnd_factions` row that operator must clean up. Quest Layer Finding 3 precedent uses `/quest delete <old_id>` for this. Spec §1.K lists 7 slashes (`list`, `seed`, `tick`, `hold`, `reset`, `set`, `visibility`) — **`/faction delete` is NOT among them.**

Without `/faction delete`, §11.5 (a) operator cleanup requires SQL direct against `dnd_factions`. That's friction operator shouldn't carry.

**Candidates:**
- (a) Ship `/faction delete <id>` at v0 with NO FK cleanup — operator manually unlinks dependent quests/NPCs first or accepts dangling FKs.
- (b) Ship `/faction delete <id>` at v0 with FK refusal — refuse delete if dependent `dnd_quests.associated_faction_id` or `dnd_npcs.affiliated_faction_id` rows exist; operator must unlink first.
- **(c) Ship `/faction delete <id>` with FK dependent-cleanup** — on delete, `UPDATE dnd_quests SET associated_faction_id=NULL WHERE associated_faction_id=?` + same for `dnd_npcs`; faction row deleted cleanly; audit row written.
- (d) No deletion at v0 — operator uses SQL or marks faction `visibility='resolved'` as soft removal.

| Candidate | Pros | Cons | Risk |
|---|---|---|---|
| (a) Delete without FK cleanup | Simplest implementation | Dangling FKs on dependent quests/NPCs; soft-FK helpers must handle None-target gracefully; operator burden | Medium — silent dangling state |
| (b) Delete with FK refusal | Forces operator to unlink dependents first | Operator gets FK-error message; must run multiple slashes to clean up before deletion completes | Medium — multi-step deletion is friction |
| **(c) Delete with FK dependent-cleanup** | Atomic operation; no dangling state; mirrors Composition v0 §11.13 cascade-delete pattern (parent quest → acts); operator sees one slash success | Quests/NPCs lose their faction association silently; operator may not realize dependents were affected | Low — telemetry surfaces `faction_delete: campaign=N faction_id=N dependent_quests=N dependent_npcs=N`; operator post-delete visibility is preserved |
| (d) No deletion at v0 | Tightest v0 surface | §11.5 (a) operator cleanup is broken (orphans accumulate forever or require SQL); `/faction list` shows stale entries permanently | High — §11.5 (a) lean has no completion path |

**Recommended default: (c) ship `/faction delete <id>` with FK dependent-cleanup.**

**Reasoning:**
- Required by §11.5 (a) for orphan cleanup.
- FK dependent-cleanup is the right semantic — quest's `associated_faction_id` becoming NULL means "quest no longer tied to a faction" which is a coherent state (quests with NULL FK already existed pre-S69).
- Atomic operation matches Composition v0 §11.13 cascade-delete precedent (parent → dependents handled in one transaction).
- §19 two-gate destruction: confirmation gate on `/faction delete` required for `pressure_kind='hard_progression'` factions (mirroring §11.7 reset confirmation).
- Telemetry: `faction_delete: campaign=N faction_id=N name='X' pressure_kind='atmospheric|hard_progression' dependent_quests=N dependent_npcs=N`. Operator visibility preserved.

**Confidence: HIGH.** Surfaced as direct dependency on §11.5 (a) lean. Pattern mature.

**Spec amendment implied at lock:** §1.K slash surface expands from 7 to 8 — adds `/faction delete <id>`. Confirmation gate for `pressure_kind='hard_progression'` per §11.7 + §19. FK dependent-cleanup logic part of `faction_delete` single writer.

---

## §4. R-finding integration check

Per brief — confirm each recon finding maps cleanly to spec decisions.

| R-finding | Spec decision | Integration status |
|---|---|---|
| **R1** N-10 prose format (labeled lines, no per-stage) | §11.6 / §1.H stage-prose authoring | ✅ Direct integration. §11.6 (a) default-then-edit acknowledges R1 evidence; §1.H migration default copies `goal` to `current_stage_description`; operator edits stages 2-4 post-migration. |
| **R2** Zero faction-adjacent state exists | §11.1 / §1.A schema scope | ✅ Direct integration. §1.A ships `dnd_factions` + `dnd_faction_audit` + additive FKs as single coherent schema delta. Quest Layer v0 §12.2 closure at S69 ship. |
| **R3** `advance_time` clean 4-enum + scene-compression separate hook | §11.3 / §1.C tick trigger event set | ✅ Direct integration. §1.C ships five sources (4 from `_VALID_TIME_SOURCES` ∪ `'scene_compress'` ∪ `'manual_tick'`); compression-fire-path needs new hook (S69 implementation owns); `event_source_required` predicate evaluates against the 4-enum + scene_compress. |
| **R4** 3 of 4 engagement-signal sources have schema gaps | §11.4 / §1.D + §1.A predicate vocabulary | ✅ Direct integration. §1.A ships FK columns (resolves gaps for sources (a) and (b)); §1.D + §5.3 evaluates engagement signals via structured FK lookup only; scene-faction tagging (c) defers to v1.x per §12.3. |
| **R5** Prompt-size baseline ~20-22k; pressure directive ~300-500 chars | §6 pressure directive sizing | ✅ Direct integration. §6.4 signals dict carries `chars` per-fire telemetry; render cap at 3 factions per turn keeps budget bounded. |
| **R6** `/quest seed-skeleton` precedent works | §11.5 / §1.G `/faction seed` shape | ✅ Direct integration. §1.G mirrors Quest Layer pattern; §11.5 (a) lean adopts Finding 3 precedent. **Surfaced dependency:** §11.14 `/faction delete` for orphan cleanup (newly added). |

**No R-finding integration inconsistency surfaced.** Spec drafting integrated each finding into the right §11 walk or §1 lock cleanly.

---

## §5. Operator + Oracle decisions

**At v0:** none required at lock-time for the recommended defaults.

**Walk-to-confirm at Session 2:**
- **§11.2 hard-progression at v0** — Code recommends (a) capability ships with opt-in default. Operator may prefer stricter (b) defer-entirely if they want absolute atmospheric-only at v0. Decision is a campaign-stakes preference axis, not doctrinal.
- **§11.6 stage-prose authoring** — Code recommends (a) default-then-edit. Operator may prefer (b) N-10 v0.2 coupling if they want stage prose authored at bootstrap time. Decision trades atomic-v0-ship vs chained-ships.
- **§11.14 faction deletion** — Code recommends (c) ship `/faction delete` with FK dependent-cleanup. Operator may want (b) refuse-with-FK-error if they want explicit unlinking before deletion. Decision is operator UX preference.

**Deferred to v1.x / v0.x:**
- §11.3 tick trigger event set (`min_turns_since_last_advance` defaults — calibrate from telemetry).
- §11.8 faction → consequence integration ((c) hybrid as observed-friction-gated v1.x).
- §11.12 N-10 faction card count tuning.
- §11.13 long-horizon faction lifecycle (filed for v1.x doctrinal pass per external review).
- §12 forward-files (13 candidates).

**No Oracle decision required at v0.** All architectural decisions sit cleanly within precedent specs' patterns:
- §59 sibling #20 + #21 (mature pattern at 19 prior instances + S69's 2 new).
- §17 single-writer per field for new `dnd_factions` columns.
- §1b suggester pattern NOT applied at v0 per §11.10 + sketch §11.10.
- §76 audit shows zero new 4/4 surfaces (per spec §10).

---

## §6. Summary of recommended defaults

| Decision | Recommended | Confidence | Spec implication |
|---|---|---|---|
| §11.1 | (a) minimum-plus-FKs schema | HIGH | Spec §1.A confirmed |
| §11.2 | **(a) hard-progression capability + opt-in default** | HIGH | Spec §1.B confirmed; deep synthesis at §3.2 |
| §11.3 | (a) five tick sources | MEDIUM | Spec §1.C confirmed; cooldown is density throttle |
| §11.4 | (a) narrow 4-key predicate vocabulary | HIGH | Spec §1.D confirmed; external review #2 lock preserved |
| §11.5 | **(a) new row + orphan (Quest Layer Finding 3 precedent)** | HIGH | Spec §1.G confirmed; surfaces §11.14 dependency |
| §11.6 | **(a) default-then-edit stage prose** | HIGH | Spec §1.H confirmed; N-10 v0.2 coupling filed §12.2 forward |
| §11.7 | (a) confirmation gate on hard-progression `/faction reset` | HIGH | Spec §1.K confirmed; §19 two-gate destruction |
| §11.8 | (a) render directly via pressure directive (no consequence write) | MEDIUM | Spec §1.J + sketch §11.6 confirmed; (c) hybrid v1.x candidate |
| §11.9 | (a) default visibility thresholds (1=unknown, 2=rumored, 3+=known, final=resolved) | HIGH | Spec §1.F confirmed |
| §11.10 | (a) NO §1b suggester at v0 | HIGH | Spec §1.J confirmed |
| §11.11 | (a) silent forward-compat (no schema stubs) | HIGH | Spec §1.L confirmed |
| §11.12 | (a) keep N-10 default at 1-2 factions per bootstrap | MEDIUM | Spec §1.L confirmed; observed-friction tuning |
| **§11.13** | **Framing note only — filed v1.x** | — | Per external review refinement #3; no v0 lock |
| **§11.14 NEW** | **(c) ship `/faction delete` with FK dependent-cleanup** | HIGH | Spec amendment at lock — §1.K slash surface expands to 8 |

**Confidence split:** 9 HIGH · 3 MEDIUM · 0 LOW · §11.13 filed framing-only · §11.14 newly surfaced.

**HIGH (no synthesis pressure):** §11.1, §11.2, §11.4, §11.5, §11.6, §11.7, §11.9, §11.10, §11.11, §11.14 — **10 decisions.**

**MEDIUM (operator attention helpful, open axis named):** §11.3, §11.8, §11.12 — **3 decisions.**

**LOW:** none. The §11.13 long-horizon question was filed-not-walked per external review; not a confidence level.

---

## §7. Surface additions

**One §11.14 surfaced:** faction deletion at v0 — see §3.14 walk. Required for §11.5 (a) lean orphan-cleanup loop.

**No other gaps identified during walk.** The spec's §1 through §13 sections cover all architectural decisions cleanly. Edge cases sweeped during walk (filed §12 forward-notes per spec):
- LLM-extracted faction stages from goal text (§12.1)
- N-10 v0.2 bootstrap-time per-stage authoring (§12.2)
- Scene-faction tagging (§12.3)
- Faction-to-faction relationships (§12.4)
- NPC member rosters per faction (§12.5)
- Resource simulation (§12.6)
- Hierarchical planning trees (§12.7)
- Adaptive challenge orchestration (§12.8)
- Multi-faction interactions (§12.9)
- Emergent faction detection from narration (§12.10)
- Faction visibility-transition consequence-ledger writes (§12.11)
- Faction notification cards non-approval (§12.12)
- Long-horizon faction lifecycle (§12.13)

All thirteen are documented in spec §12 with proper "v1.x candidate" tagging.

---

## §8. Handoff

| Field | Value |
|---|---|
| **Review doc status** | REVIEW — Phase 2 walk complete (May 14, 2026). Operator reviews and locks decisions; spec flips DRAFT → LOCKED before Session 3 implementation opens. |
| **Review doc file** | `/home/jordaneal/virgil-docs/specs/CAUSALITY_ENGINE_V0_REVIEW.md` |
| **Decisions walked** | **12 active + 1 framing (§11.13) + 1 newly surfaced (§11.14) = 14 total.** |
| **Confidence split** | **10 HIGH · 3 MEDIUM · 0 LOW.** §11.13 framing-note only; §11.14 newly surfaced at HIGH. |
| **§11.14 surfaced** | **YES — faction deletion at v0.** Required for §11.5 (a) orphan cleanup loop. Spec §1.K slash surface expands from 7 to 8 (`/faction delete <id>` with FK dependent-cleanup + confirmation gate on hard-progression). |
| **R-finding integration** | All six R-findings integrate cleanly into §11 decisions or §1 locks per §4. No integration inconsistency surfaced. |
| **HALT escalations** | 0. Walk surfaced no finding that invalidates v0 architectural shape. Three deeper-synthesis walks (§11.2, §11.5, §11.6) confirmed Code's leans hold under analysis. |
| **Operator escalation points** | §11.2 (hard-progression at v0 — Code's (a) is HIGH; operator may prefer stricter (b) defer-entirely). §11.6 (stage-prose authoring — Code's (a) is HIGH; operator may prefer (b) N-10 v0.2 coupling). §11.14 (faction deletion — Code's (c) is HIGH; operator may prefer (b) FK-refusal for explicit unlink discipline). |
| **Forward-coupling notes** | §11.6 → N-10 v0.2 bootstrap-card per-stage authoring (filed §12.2). §11.14 → §1.K slash surface update at lock. §11.13 → v1.x doctrinal pass for faction lifecycle. §11.3 → cooldown default tuning v0.x patch from telemetry. |
| **Next session** | **Session 3 = implementation.** Sonnet medium per WWC cadence — mature §59 sibling pattern (19 prior + S69's 2 new = 21); mature §1b discipline (sixth-instance-anchored at N-10; explicitly NOT applied at S69 per §11.10); mature §17 single-writer per field; mature §76 audit (zero new 4/4 surfaces per spec §10). Estimated ~3-4 days for schema delta + 2 §59 siblings + 8 slash commands + 25-30 test surface. |

**Recommended pre-Session-3 operator action sequence:**

1. Review this doc (Session 2 framing).
2. Lock §11.1, §11.4, §11.7, §11.9, §11.10, §11.11 to recommended defaults if no objections (HIGH confidence, standard walks).
3. Lock §11.2 to (a) capability + opt-in OR (b) defer-entirely — campaign-stakes preference.
4. Lock §11.5 to (a) Quest Layer Finding 3 precedent.
5. Lock §11.6 to (a) default-then-edit OR (b) N-10 v0.2 coupling — atomic-ship vs chained-ships preference.
6. Confirm §11.3 cooldown default value (12 turns) for `min_turns_since_last_advance`.
7. Confirm §11.8 (a) at v0; flag (c) hybrid as v1.x observed-friction candidate.
8. Confirm §11.12 (a) at v0.
9. **Lock §11.14 to (c) ship `/faction delete` with FK dependent-cleanup** (required by §11.5 (a)).
10. Confirm §11.13 framing-note acceptance (no v0 lock required).
11. Update spec status header: DRAFT → LOCKED with date + decision-lock summary + §11.14 amendment + §1.K slash surface update (7 → 8).
12. Session 3 opens with locked spec.
