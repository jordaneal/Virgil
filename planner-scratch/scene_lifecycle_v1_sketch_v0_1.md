# Scene Lifecycle v1 — Architectural Sketch (v0.1)

**Status:** v0.1 sketch — supersedes v0. Reconciliation pass after Phase 1 spec drafted divergent shape against ROADMAP. v0 was operator-initiated boundary tool; v0.1 ratifies the auto-fire stagnation-detection framing and folds in v0's load-bearing observations that the spec missed.
**Date:** May 13, 2026
**Mandate (Prompt 1, corrected):** Virgil-as-DM auto-detects scene staleness and signals compression. F-54 stagnation drift is the parent failure; scene immortality is the named symptom. Per ROADMAP §Scene-Lifecycle-v1 and FAILURES.md §F-54.

---

## 1. What this is

Scene Lifecycle v1 is the **motion-system primitive that closes scene immortality** — the F-54 symptom where exploration/social scenes accumulate turn-count without resolving, NPCs linger past purpose, motifs repeat compulsively (F-52), and the campaign loses the feeling of motion even when every individual mechanism works correctly.

**Trigger model is auto-fire, not operator-initiated.** Virgil is the DM (per Prompt 1 mandate, corrected reading); Virgil detects stale-scene state via deterministic counter and signals compression to the LLM as a directive. Operator `/compress` ships as one trigger surface among several, not the primary mechanism. This matches the CC corpus baseline — Matt-initiated compressions are the dominant signal (`matt_initiated` buildup at ~3 per episode), and the Virgil-as-DM equivalent is engine-detected.

**Architectural placement.** Sits downstream of the structural floor (Track 7 adjudication closed it), upstream of experience texture (faction/reputation/curiosity layers). Couples to Track 4 #3 Time Progression (already shipped) — Time Progression closed "the world doesn't visibly evolve" by making the calendar advance; Scene Lifecycle closes the adjacent symptom: scenes within a day phase don't close on their own.

---

## 2. What surfaces it extends, what's new

**Reuses (no schema change):**
- `dnd_scene_state.mode` — read for gate (exploration/social fire; combat does not per §11.A scope). v1 does NOT write mode.
- `dnd_scene_state.turn_counter` — read-only reference for threshold calibration.
- `dnd_scene_state.current_location_id`, `last_dm_response`, `last_player_action`, `dnd_campaigns.current_scene` — read for directive context; written via existing single-writers (no new write paths).
- Existing `_combat_beats` substrate pattern (S43/§78.6) — template for in-memory stale-turn counter.

**Proposed new:**
- One §59 sibling — `compute_scene_lifecycle_directive(scene_state, stale_turns, trigger_kind) → (body, signals)`. 11th sibling, pattern is mature.
- One in-memory state surface — `_scene_stale_turns: dict[int, int]` keyed by guild_id, owned by `discord_dnd_bot.py`. Same substrate as `_combat_beats`.
- One slash command — `/compress [reason: optional]`, DM-only, fires the directive at strong-tier directly with stale counter reset.
- Telemetry primitives — `scene_lifecycle:` per-turn (always-fire baseline), `scene_lifecycle_reset:` on activity-signal reset (which signal fired), `directive_emit:` extended with `scene_lifecycle={none|soft|strong}` field.

**Not new:**
- No new table. No new persisted column. No ChromaDB collection.
- No mode write. No `advance_time` write. No NPC- or location-canon mutation.
- No LLM classification feeding a binding decision (the counter is deterministic; the directive is a constraint to the LLM, not a decision the LLM makes).

---

## 3. The directive shape

**§59 sibling pattern, every-turn evaluation.** `compute_scene_lifecycle_directive` reads scene_state + stale counter + trigger_kind, returns directive body + signals dict. Three tiers branch in the function body:

- **Below soft threshold** (counter < N_soft) → returns `('', {fired: 0, tier: 'none'})`. Empty body is the "skip" signal per §59 contract; no prompt block emitted. This is the 86% quiet case (see §5).
- **Soft tier** (counter ≥ N_soft, < N_hard) → returns soft-nudge body (~150 chars). Directive tells LLM the scene is getting thin; suggests transitioning; explicitly allows escalation-instead-of-compression for high-tension content.
- **Strong tier** (counter ≥ N_hard, or trigger_kind='explicit') → returns strong directive body (~300 chars). Directive tells LLM to compress this scene NOW; close any open beats in one sentence; move party toward next meaningful event; do not extend the current location or NPC interaction further.

`signals` carries `{fired, tier, stale_turns, threats_active}` for telemetry and downstream composition. Soft-fail at call site — directive errors never block narration.

**Stale counter mechanics.** Counter is incremented in `discord_dnd_bot.py` on `on_message` player turns that produce no activity signal. Reset to 0 on activity-signal events (see §11.E for the locked signal set discussion). Bounded behavior: accumulate without cap (telemetry value), strong directive fires every turn at or past N_hard until reset.

**LLM job.** Render the compression per §77 — atmospheric continuity, not adjudication. Forbidden: invented NPCs (§77 + §F-49 binding), mechanical-outcome inference (§77), next-scene authoring (sketch §5 finding), narrating the player's characters' actions during compression (player retains agency).

**Engine job.** Maintain the counter. Decide tier. Inject directive at the right placement in `build_dm_context` (per Code's §1.I, after commitment directive — last-instruction-wins per §2). Soft-fail throughout.

**This is the 11th §59 sibling. Pattern is mature.**

---

## 4. Where it sits relative to §78

**v1 is pattern-reuse, not §78 fourth instance.** §78's three anchored instances all involve external boundary signals (Avrae mode-flip events). Scene Lifecycle v1 fires on internal accumulation state (stale counter), not external trigger. Anchoring as §78 fourth instance stretches "boundary" to "any state-reset surface regardless of trigger origin" — operator's correction from v0 stands.

What this means concretely: v1 borrows §78's discipline (mechanical cleanup pattern, narrative buffer reset pattern, soft-fail throughout) as architectural template, but does NOT extend the §78 doctrine. The four-layer state-reset machinery doesn't apply because v1 isn't a state-reset — it's a directive injection. The LLM's compression *response* changes scene state; the directive itself doesn't.

§78.5's fourth-instance-promotion check stays open for a future case with a non-Avrae *external* boundary event. v1 doesn't close it.

§78.6 (layer-4 render-vs-marker, content-conditioned) **does not apply** at v1. Per §11.D below, the marker-vs-render decision is sidestepped via tiered directive (soft vs strong) plus operator `/compress` for explicit cases. The render-vs-marker question reopens only if v1.x adds auto-firing without tier escalation.

---

## 5. The 86% quiet baseline as architectural reality

**X2 in the cross-extractor findings:** 86% of CC scene-exits are followed by 30+ turns of zero extractor signal. What fills those 30 turns (player turns, NPC dialogue, DM narration) isn't extractor-targeted — the pipeline isn't blind, it's correctly silent.

**Operational consequence for v1.** The directive's threshold-fired evaluation IS the 86% quiet baseline in implementation form. Below soft threshold, the function returns empty body — no prompt block, no LLM constraint, no architecture-side noise. The directive is structurally quiet most of the time, by design, mirroring the corpus finding.

The directive does NOT attempt next-scene authoring after compression fires. After the LLM compresses and posts, the next turn proceeds via normal `dm_respond` path; the new scene rebuilds organically through player input + LLM response. This matches CC's X7 finding: events don't cluster at 15-turn scale, so designing for post-compression coordination is a design error against the corpus.

**This is the load-bearing observation v0 surfaced and the spec needs to carry explicit.** A threshold-fired directive IS quiet most of the time, but the spec must state this as the design intent so future ships don't try to fill the 86%. If v1.x adds quest layer or composition layer, both must respect the same quiet baseline — neither layer interferes with the post-compression 30-turn window.

---

## 6. X7 single-source detection rule

**Cross-extractor finding X7:** No reliable cross-extractor agreement at 15-turn scale. CC, TM, LR, EC don't co-fire as coordinated signals; each fires on its own surface. Designing for "all four extractors agreed → compress now" is structurally unsupported by the corpus.

**Consequence for v1.** The stale counter is the single detection source for auto-fire. No cross-extractor join, no co-fire threshold, no "compress if EC reset AND TM stale AND LR pending." Counter fires on its own signal.

Future motion-system ships (quest layer, composition layer, encounter cadence v1) operate on their own detection surfaces. v1's stale counter doesn't read their signals; their signals don't read v1's counter. This is filed forward as the **single-source detection rule** for the motion-system thread — each ship's detection surface is independent until empirical evidence justifies coupling.

This also rules out a v1.x temptation to "improve" the counter by joining with `consequence_promoted` rate or `npc_register_avrae_madd` rate. Per X7, those joins won't produce reliable signal at the 15-turn scale. Stay single-source.

---

## 7. Climactic-hold suppression rule (X4 R1/R2 port)

**Cross-extractor findings X4 R1/R2:** Climactic-hold pattern in CC corpus — 10.6% of episodes produce zero compressions, clustering with finales / high-tension content (C1E114 finale, C1E076, C1E108). Predicate: BLOODIED + DOWNED beats present, recent combat, hard-stakes signals → Matt resists compression rather than honoring it.

**Port for v1 fits Code's auto-fire shape directly as a suppression rule, not as state.** The counter accumulates normally. At directive-fire time (soft or strong threshold reached), engine checks for climactic-hold signal:

- Active combat (mode='combat') — already suppressed by §11.A mode gate, free for v1
- Recent BLOODIED or DOWNED beat — read `_combat_beats` counter; if any in last N turns, suppress
- Recent combat exit (within M turns of `!init end`) — read `dnd_scene_state.last_active_actor` transition log or fold into the recent-beat check
- Unresolved commitment directive firing — already in signals from S19 commitment_directive log

If climactic-hold predicate matches: directive returns empty body regardless of counter value. Telemetry: `scene_lifecycle: ... fired=0 reason=climactic_hold_suppressed predicate={beats|combat_recent|commitment_open}`.

This is structurally clean — suppression rule, not state-machine branch. Counter keeps accumulating; suppression is a fire-time check; if the climactic content resolves and the predicate clears, the directive fires on the next turn normally. Matches CC's pattern: Matt doesn't reset his internal stale-tracker during finales, he just doesn't act on it.

**Climactic-hold predicate definition is a §11 decision.** Listed below in §11.L. Counter-side suppression is the architectural shape; the exact signal set is operator's call.

---

## 8. Architectural questions for §11 decisions

Refined from Code's §11.A-K against the v0 sketch's surfaced concerns. Leans named where I have them; genuine uncertainty flagged.

**Code's §11.A through §11.K stand mostly intact** under the corrected mandate framing. The questions worth flagging as gaps or refinements:

- **§11.A (trigger mode scope).** Code recommended exploration+social (b). Lean concur. Travel is already time-compressed; downtime mode doesn't exist; combat is gated.
- **§11.B (rest-event suppression).** Code recommended natural reset via activity signal (b). Lean concur. Defensive redundancy not needed.
- **§11.C (T1 only vs T1+T2 player closure).** Code recommended T1+T2 (b). **Lean defer T2 to v1.x.** T2 introduces phrase-vocabulary detection on player text — a new detection surface with false-positive risk that v0's CC findings didn't directly support. CC's `matt_initiated` dominance suggests engine-side detection is the primary surface; player-side closure-intent is a smaller fraction. T2 phrase vocabulary needs corpus grounding (which phrases reliably indicate scene-close intent in the CRD3 player corpus, if any) before shipping. Shippable as v1.x once T1 logs show whether player-side false positives or player-side missed compressions surface as friction.
- **§11.D (threshold values).** Code recommended named constants tunable in code (b). Lean concur. Standard project pattern.
- **§11.E (activity signal definition).** Code recommended §1.F-listed signals only (a). Lean concur. Strict signal set defensible.
- **§11.F (`/compress` DM-only vs player-accessible).** Code recommended DM-only (a). Lean concur. Player-accessible would let players force scene transitions DM didn't intend.
- **§11.G (counter overflow behavior).** Code recommended accumulate (b). Lean concur. Telemetry value; same behavioral effect as cap.
- **§11.H (cliff-edge enforcement layers).** Code recommended instruction-side only (a) for v1. Lean concur. §78's two-layer pattern is for mode-transition surfaces; v1 isn't one. Information-side suppression is v1.x if drift surfaces.
- **§11.I (combat mode counter reset on entry).** Code recommended reset at `!init begin` via activity signal (b). Lean concur.
- **§11.J (counter reset on explicit `/compress`).** Code recommended reset to 0 (a). Lean concur.
- **§11.K (counter visibility to LLM).** Code recommended invisible (a). Lean concur. §76-aligned (the counter is a calibration primitive, not a world-state fact).

**New §11 decisions surfaced by v0.1 reconciliation:**

- **§11.L — Climactic-hold predicate definition.** Per §7 above. Suppression rule shape is architectural; the exact signal set is operator's call. Candidates: (a) `_combat_beats > 0` in last N turns + active commitment_directive, (b) extended set including DOWNED beats specifically + recent BLOODIED + recent combat exit, (c) operator-driven minimal set with v1.x expansion. *Lean: (a) at v1.* Smaller signal set, fewer false-positive suppressions. v1.x extends if log evidence shows compressions fired during high-tension turns despite suppression.

- **§11.M — §1a auto-fire scrutiny.** Every-turn injection at threshold is structurally heavier than pacing/consequence/commitment directives. Pacing nudges narrative tone; consequence surfaces existing canon; commitment narrows player-action latitude. Compression directive instructs the LLM to *end a scene* — a structural state change downstream. **The directive doesn't write the structural change itself** (no mode write, no buffer reset, no scene_state mutation), but its purpose is to cause the LLM's narration to do so. Code's §1.A framed this as "atmospheric guidance, not binding decision" because the LLM's narration is what writes the change. Defensible under §1a (LLM never decides binding mechanical outcomes — scene compression isn't a mechanical outcome, it's a narrative move). But the directive is heavier than pacing precedent; spec should walk this explicitly rather than inherit-by-pattern. **No confident lean.** Two valid reads: (a) §1a holds — narrative compression is exactly the LLM's job under §1a, the engine just nudges it; (b) §1a is uncomfortable here — the directive is structurally a state-change request, even if writes happen via narration. Operator + Oracle territory. Sketch frames cleanly; spec session must walk.

- **§11.N — T2 deferral confirmation.** Per refinement above. Lean defer; spec session confirms.

---

## 9. Operational warnings for Phase 2 review (Session 2 cadence)

**§17 amendment-pressure on the buffer-reset writer.** Code's spec §1.G correctly identified v1 does NOT generalize `reset_narrative_buffers_on_combat_exit` — the buffers self-update via `_dm_respond_and_post`'s normal writers; v1 has no boundary to reset. Phase 2 review should confirm this read holds (audit that buffers don't drift pollute the post-compression scene without explicit reset). If audit surfaces drift, fork-vs-generalize question reopens with the v0 sketch's narrow-exception framing as the doctrinal lock.

**Prompt-size budget.** Code's spec §1.C measured baseline ~25k chars, +300 chars at strong threshold (+1.2%). Budget-safe at fire rate, but Scene Lifecycle is piece 1 of 3 in the mandate. Quest layer adds active-quest rendering (NPC-voice routing per LR 36.8% finding). Composition layer adds act-anchoring metadata. Phase 2 review should set the baseline measurement that quest layer and composition layer ship against — v1 establishes the floor, downstream ships measure delta.

**Test coverage shape.** Code's §8 sketches unit + integration + regression. Phase 2 should confirm: (a) climactic-hold predicate test cases (one per signal in the predicate set), (b) §11.M §1a-scrutiny answer affects what tests need to verify (if the operator answers (a), tests assert directive injection at threshold; if (b), tests need to verify directive doesn't structurally write the compression).

---

## 10. What this sketch does NOT do

- Lock §11.A through §11.N. Those go in Session 2 review against the spec, then operator's call.
- Address quest layer or composition layer beyond §6 single-source detection rule.
- Address combat-mode scene compression. Filed forward; no corpus signal coverage.
- Pre-commit to climactic-hold predicate signal set (§11.L) or T2 vocabulary (§11.N).
- Survey Code's recon findings R1-R6 — those stand, ratified by reading the spec.
- Resolve §11.M §1a auto-fire scrutiny. Operator + Oracle.

---

## 11. Next move

Session 2 dispatches against the existing spec (`specs/SCENE_LIFECYCLE_V1_SPEC.md`) with this v0.1 sketch as the reconciled foundation. Session 2 cadence: review pass, Opus medium, produces `SCENE_LIFECYCLE_V1_REVIEW.md` walking each §11.A through §11.N with trade-offs + recommended defaults + confidence levels. Operator reviews and locks. Spec flips DRAFT → LOCKED. Session 3 = implementation (Sonnet medium, templated against §59 sibling pattern).

Oracle-review of this sketch happens before Session 2 dispatches per operator instruction.
