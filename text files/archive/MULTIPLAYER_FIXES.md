# Multiplayer Fixes Plan v3 — LOCKED, CANONICAL (S34, May 11, 2026)

**Status:** v3 LOCKED and promoted to canonical (May 11, 2026, post-Ship-1). Replaces v2; v2 archived at `_trash/MULTIPLAYER_FIXES_V2_20260511.md` for lineage. All 12 §12 decisions locked by operator review; Avrae A.2 recon cleared cleanly (form (a) — Avrae silently ignores trailing integer in `!check skill N`, modifier/roll/embed identical to bare-form baseline; Virgil's `parse_skill_and_dc` splits skill from DC correctly; shipped Ship 1's DM-typed-directive surface fired end-to-end through this format at 08:33:14–20 on 2026-05-11). Next active ship: **Ship A — LLM-Emitted-Directive Resolution Binding** (S35 spec drafting, S36 implementation).

**Trigger for re-plan:** Ship 1 (S34) promoted clean, but the verify walk surfaced a primary-surface mismatch that wasn't caught in S33 planning. Ship 1 closed the **DM-typed-directive surface** (operator with manage_guild perm types `!check perception 10` literally). The **load-bearing play loop** is different: operator types intent ("I take a closer look"), LLM narrates and emits `!check perception` inside the narration, Avrae rolls in response to the bot's emission, bot needs to auto-fire resolution narration bound to the rolled value.

Shipped Ship 1 stays as-shipped — it closes a real-but-secondary surface (the operator-as-flagged-DM case, which happens in walkthroughs and verify work). It does NOT close the primary play loop.

**Plan delta from v2:** insert a new ship (Ship A — LLM-Emitted-Directive Resolution Binding) at the front of the queue, ahead of the existing Ship 2. Shipped Ship 1's infrastructure (`ResolutionResult`, `resolve_directive`, `render_resolution_block`, ROLL_OUTCOME_DRIFT verifier, AUTHORITATIVE-CANON prompt block, `dnd_pending_roll_directives.dc` column) is fully reusable; Ship A is additive at the matcher's input surface, not a rewrite. Ships 2/3/4/5 survive sequencing — each closes a surface that is independent of which actor emits the directive.

---

## §1. The diagnosis (revised from v2 §1)

The play loop has **four canonical actors** in the directive→roll→narration cycle, not two. v2 implicitly addressed only the (DM-types-directive, player-rolls) case:

| # | Who emits the directive | Who rolls | Surface | v1 status | Ship 1 (S34) status |
|---|------------------------|-----------|---------|-----------|---------------------|
| 1 | DM types `!check perception 10` in `#dm-narration` (operator flagged as DM/creator) | Player rolls `!check perception` | DM-typed-directive → player-rolls (the published "Bug 1 Phase 1" surface) | telemetry-only until S32 ship | ✅ **closed by Ship 1 (S34)** — resolution binds; bot auto-fires |
| 2 | **LLM emits `!check perception` inside bot narration** (the load-bearing case) | Player rolls `!check perception` | **LLM-emitted-directive → player-rolls (the primary play loop)** | Track 7 #1 binds on the NEXT player turn via adjudicator's `consume_recent_check`; no immediate auto-fire | **NOT closed** — Ship 1's matcher only fires when a pending directive row exists; LLM emission doesn't write a row |
| 3 | Player types `!check perception` directly (no DM directive preceding) | Same player rolls | Player-initiated roll (no narrative pause) | Avrae rolls; bot consumes via buffer on next player text; no immediate auto-fire | RESOLUTION_BINDING_SPEC.md §15.2 — explicitly out of scope |
| 4 | DM types `!check perception 10` (no DC) | Player rolls | Graceful degrade | falls through to free-narration; no auto-fire | ✅ shipped per §11.2 (`reason=no_dc`) |

**The primary play loop is row #2.** Solo: operator-as-player types intent → LLM narrates + emits → Avrae rolls → operator wants to see the outcome narration *now*, not after typing "what happens?". Multiplayer: same loop, just with a different player rolling.

Ship 1's published surface (row #1) is real — it covers operator-as-flagged-DM running deliberate set-piece checks ("I'm setting up the spike trap, Donovan rolls perception DC 15"). But that's a 5-10% case at best. The 90% case is row #2, which Ship 1 does not address.

The cause of the misalignment: BUG_1_SPEC.md framed the problem as "DM emits `!check`, Avrae rolls, bot waits silently for next player input" — and the assumed actor of the `!check` was the human DM. The LLM has always emitted `!check` inside narration (Track 7 #1's HARD STOP RULES instruct it to), but that emission never created a `dnd_pending_roll_directives` row because the `_handle_dm_roll_directive` writer is triggered from `on_message`, which short-circuits on `message.author.bot` for the bot's own posts. The plan needed to specify a second writer at narration-emission time; v2 did not.

The diagnosis carries forward unchanged for Findings A (recursive hallucination), H (NPC state-sync), and B (canonical-name reuse). Only Finding L's closure shape changes — the resolution-binding work needs a primary-surface writer.

---

## §2. North-star principles

Unchanged from v2 §2. Both principles point at the new primary ship as well as the original ones:

1. **The LLM is a renderer of truth, not a ruler of truth.** Ship A keeps this: the LLM may *choose the DC* (a DM decision input that the LLM is licensed to make), but the engine computes `passed = roll_total >= dc` and binds the narration to that outcome. The LLM never decides whether the roll passed.
2. **Scene-scope-first resolution.** Carries; Ship 4 still ships.
3. **Structural removal of write authority beats validation.** Carries; Ship A keeps the AUTHORITATIVE-CANON binding-block approach over a post-hoc validator. ROLL_OUTCOME_DRIFT remains the safety net, not the primary closure mechanism.

---

## §3. Plan structure (re-sequenced)

Five ships post-Ship-1, with Ship A inserted as new primary. Sequencing axis: **playability-now** (per S33 trigger statement). Ship A closes the 90% surface; Ships 2/3/4/5 close remaining architectural seams.

| # | Name | Closes | Calendar |
|---|------|--------|----------|
| 1 ✅ | Resolution Binding (DM-typed directive) | Finding L surface 1, F-45 regression on DM-typed path, Bug 1 Phase 2 | shipped S34 |
| **A** (new) | **LLM-Emitted-Directive Resolution Binding** | **Finding L surface 2 (primary play loop), F-45 regression on LLM-emitted path** | **S35–S36 (spec + impl)** |
| 2 ✅ | Scene State Canon Discipline | Finding A, anchors Doctrine §76 | shipped S39 |
| 3 ✅ | NPC State-Sync Boundary | Finding H, files as F-55 cluster sibling #5.5 | shipped S41 (via in-session pivot to §1b suggester) |
| 4 | Scene-Scope-First Identity Resolution | Finding B, builds SceneComposition aggregator | S42 |
| 4.5 | Multi-Actor Temporal State | (filed candidate, decision at Ship A verify checkpoint, not Ship 1's) | S42b if slotted |
| 5 | Polish cluster | Findings J/G/I-template/§5.7, including J reconsidered against Ship A | S43 |

Calendar drift from v2: +2 calendar days (Ship A insertion). v2's "9 days best case, 13 slow case" becomes **11 best / 15 slow**. Acceptable; Ship A's primary-surface closure dwarfs the calendar cost.

---

## §4. Ship A — LLM-Emitted-Directive Resolution Binding ✅ SHIPPED LIVE (S36, May 11, 2026)

**Closes:** Finding L on the **primary play loop** (LLM emits directive → Avrae rolls → bot auto-fires resolution narration). Companion to shipped Ship 1, which closes the same finding on the DM-typed-directive secondary surface.
**Goal:** When the LLM emits `!check perception <DC>` inside narration, the bot writes a pending directive row at narration-emission time so the matcher will resolve the subsequent Avrae roll and auto-fire outcome narration bound to the rolled value.
**Status (S36):** Implementation + 9 patches landed in S36 (initial implementation + 8 live-verify-surfaced refinements). ~120 test assertions across 2 new + 4 extended files. Live verify clean: nat-20 PASSED case rendered memorable-success texture; zero cascading rolls (Patch 7 sentinel detection); Avrae compat confirmed for `**!check skill : Name**` bold-wrapped format. Both surfaces of Finding L now structurally closed (Ship 1 DM-typed + Ship A LLM-emitted via same primitives). C1 doctrine candidate has 3 clean instances pending anchor per locked decision 11. C3 (single-writer compatible with multiple trigger surfaces) filed at 1 instance. New telemetry: `llm_emit_directive_bound:`, `stakes_tier:`, `directive_preserve_existing_dc:`, `directive_skill_mismatch:`, `llm_emit_multi_directive_count:`. Operator-flagged issues all resolved (cascading rolls, DC visibility, character name, bold formatting, blank line spacing, manual `!check` echo clobber, intent classifier under-triggering for natural language).

### §4.1 Architectural shape (additive to shipped Ship 1)

The shipped Ship 1 infrastructure is fully reusable:

- `dnd_pending_roll_directives` table + `dc INTEGER` column — unchanged
- `pending_directive_upsert` / `_get_active` / `_consume` — unchanged
- `ResolutionResult` dataclass — extended (see §4.3, §4.4) but field-additive
- `resolve_directive` pure function — unchanged
- `_handle_dm_roll_arrival` matcher — unchanged (consumes any pending row regardless of who wrote it)
- AUTHORITATIVE-CANON prompt block + render helpers — extended (see §4.3, §4.4) but additive
- ROLL_OUTCOME_DRIFT verifier class — unchanged
- `_fire_resolution_narration` coroutine + fallback aside — unchanged

What Ship A adds:

- **New writer to `dnd_pending_roll_directives`** at narration-emission time. Trigger: `_dm_respond_and_post` post-`dm_respond`-pre-Discord-post. Parses the LLM's narration text for `!check <skill>[ <dc>]` / `!save <stat>[ <dc>]` patterns. On match, calls `pending_directive_upsert(actor_name=acting_character, check_type=skill, dc=parsed_or_default, source_message_id=<bot-message-id-after-post>)` AFTER the embed is posted (so source_message_id is available).
- **Prompt-side change** instructing the LLM to include a DC when emitting a roll directive. Locked DC band table in the prompt for guidance (5/10/15/20/25/30 ↔ very-easy/easy/medium/hard/very-hard/nearly-impossible). DM-philosophy block extension. The DC the LLM emits is the DC the engine binds.
- **Skill normalization fix** at LLM-emit time. The LLM may emit `!check Sleight of Hand` or `!check stealth` — the parser must handle both. Reuses Phase 1's `_normalize_skill_for_match`.
- **Difficulty band + margin + stakes + crit-tier rendering** in the AUTHORITATIVE-CANON block. See §4.3 and §4.4 for the sub-features.

### §4.2 Composition with shipped Ship 1 (single-writer status of `dc`)

Doctrine §17 says single write paths per field. Ship 1's spec §6.5 declared `dc` single-writer via `_handle_dm_roll_directive`. Ship A adds a second trigger surface (LLM narration emit) writing the same column.

**Recommendation: consolidate at the writer-helper layer, not the trigger layer.** Both trigger surfaces call the same `pending_directive_upsert(... dc=...)` helper; that's the single writer in the §17 sense. Two trigger surfaces calling one helper is structurally distinct from "two writers contending on a column."

The triggers are disjoint by surface (human-typed `!`-prefix in `on_message` vs bot-narration-text scan in `_dm_respond_and_post`); they don't race. Phase 1's `pending_directive_replaced` semantics already handle the case where two upserts land back-to-back (the later one wins; both events are logged).

**Surfaced decision:** if §17 review judges this insufficient, alternative is to fork the table by trigger source (`dnd_pending_roll_directives` for DM-typed, `dnd_llm_emitted_directives` for LLM-emitted, each with their own writer). I don't recommend this — it doubles the matcher complexity for a write-time concern. But it's the formal §17-compliant alternative.

### §4.3 Difficulty / margin / stakes scaling (sub-feature, NOT a separate ship)

Currently `ResolutionResult` carries only `passed: bool` for binding. The operator wants narration *texture* to scale with three additional dimensions:

1. **Difficulty band** — derived from DC vs actor's modifier on the relevant skill. Bands: `trivial | easy | medium | hard | very_hard | nearly_impossible`. Mapping: effective DC (DC - modifier) buckets at 5/10/15/20/25/30 boundaries per 5e RAW DC bands.
2. **Margin** — `roll_total - dc`. Tiers: `catastrophic_fail (≤-10) | clear_fail (-9..-5) | close_fail (-4..-1) | razor_pass (0) | clean_pass (1..9) | smashing_pass (≥10)`.
3. **Stakes tier** — derived from scene context: `low | medium | high`. Pure function `compute_stakes_tier(scene_state, active_turn, active_quests, combatants) → str`. Inputs: scene mode (combat weighted highest), tension level, urgent clocks (≥1 urgent → +1 tier), recent committed action (yes → +1 tier), alive enemies in scene (yes → +1 tier). Bucket to low/medium/high.

These three signals extend `ResolutionResult`:

```python
@dataclass(frozen=True)
class ResolutionResult:
    # ... existing fields ...
    difficulty_band: str    # 'trivial' | ... | 'nearly_impossible'
    margin: int             # roll_total - dc (signed)
    margin_tier: str        # 'catastrophic_fail' | ... | 'smashing_pass'
    stakes_tier: str        # 'low' | 'medium' | 'high'
```

Or — if §17 prefers — they live on a separate `ResolutionTexture` dataclass referenced by `ResolutionResult.texture: ResolutionTexture | None`. Decision in §4.5.

`render_resolution_block` is extended to include the texture cells in the AUTHORITATIVE-CANON block:

```
═══ AUTHORITATIVE ROLL RESOLUTION ═══
{Actor} attempted a {Skill} {check/save} (DC {dc}).
Roll total: {roll_total}.
Outcome: {PASSED/FAILED}.

Difficulty: {band} (effective DC {effective_dc} after actor modifier {mod}).
Margin: {margin_signed} ({margin_tier}).
Stakes: {stakes_tier}.

You MUST narrate this as a {success/failure}. {Actor} does {NOT } achieve the intended outcome.
The texture of the narration must reflect:
  - Difficulty: {one-line guidance per band}
  - Margin: {one-line guidance per margin tier}
  - Stakes: {one-line guidance per stakes tier}
Do NOT narrate {opposite outcome}. Do NOT invent an alternative interpretation.
═══
```

**The block stays internal.** Player sees only the resulting narration. The mechanical breakdown is for the LLM's constraint surface, never rendered to the chat.

Guidance examples (locked in spec §4.5 decision):
- `difficulty=hard`: "This was a hard check. Narrate the effort or close-quartered nature of the attempt; don't make it look easy."
- `margin=razor_pass`: "Margin of zero — narration should convey the just-barely quality; one detail, one moment of doubt before success."
- `margin=smashing_pass`: "Margin ≥10 — narrate flair, control, perhaps an unintended bonus detail surfaced."
- `stakes=high`: "Active urgent clocks or combat pressure — narration must feel weighty; consequences land harder."

### §4.4 Crit-tier rendering (sub-feature)

Per RESOLUTION_BINDING_SPEC.md §11.3 RAW: nat 20 does NOT auto-PASS on skill checks and nat 1 does NOT auto-FAIL. `passed` stays strictly `roll_total >= dc`. But the nat 20 / nat 1 signal is narratively load-bearing independent of pass/fail — it gives the LLM permission to render a memorable beat.

Ship 1 already captures `nat: int | None` and `crit: bool` on `ResolutionResult` (§5.3). Ship A wires these into the AUTHORITATIVE-CANON block as a **separate constraint clause** that fires only when `nat == 20` or `nat == 1`:

- **Nat 20 (regardless of pass/fail):** Block carries a `Critical signal: NAT 20.` line. Constraint clause: "This was a critical natural-20 roll. Narrate a memorable element — extra reward, lore drop, NPC reaction, an unintended bonus detail, or a moment of unusual confidence/grace. If the outcome was FAILED (nat 20 + high DC + low modifier), the memorable element is the *near-miss quality* — they did everything right but the goal was beyond reach. Lean into the tension between the spectacular roll and the still-thwarted attempt."
- **Nat 1 (regardless of pass/fail):** Block carries a `Critical signal: NAT 1.` line. Constraint clause: "This was a critical natural-1 roll. Narrate a memorable element — comic moment, catastrophic side-effect, or a single beat of bad luck. Scene tone dictates whether the memorable element is funny or grim. If the outcome was PASSED (nat 1 + very low DC + high modifier), the memorable element is the *graceless quality* of the success — they got there, but the path was awkward."

Edge case captured explicitly: **nat 20 + FAILED** and **nat 1 + PASSED** are the most narratively interesting cells. The clauses above lock the texture for those cells so the LLM doesn't drift into "but I rolled a 20, the bot must narrate success."

Tabletop variant flag (v1.x candidate, not Ship A): per `dnd_campaigns.crit_succeed_skill_checks BOOLEAN` config, the binding `passed` could override on `nat == 20` / `nat == 1`. Ship A keeps RAW; flag stays a future ship.

### §4.5 Decisions to lock in spec

**(A.1) DC source for LLM-emitted directives.** Options:
- (a) LLM emits inline DC: `!check perception 15`. Prompt-side change instructs the LLM to always include a DC in the emission. Parser splits skill from DC (reuses `parse_skill_and_dc` shipped in Ship 1).
- (b) Bot computes DC from action-difficulty inference. Deterministic. Requires building a DC computer with scene context. Risky: shifts "DM choice" responsibility from LLM to a heuristic function.
- (c) Hybrid: LLM emits a difficulty band (`!check perception medium`), bot maps band to DC. Risk: yet another LLM-emit format to validate.

**Recommendation: (a).** The LLM choosing the DC is a *DM decision*, which the LLM is licensed to make under "renderer not ruler" — the engine binds the *outcome*, not the *difficulty input*. Prompt-side change is small (single HARD STOP RULE extension + a one-paragraph DC-band reference table inserted ahead of HARD STOP RULES). Avrae compatibility: needs recon — `!check perception 15` may interpret the 15 as something unintended. If Avrae chokes, fall to (a') where the parser accepts both `!check perception 15` and `!check perception -dc 15` and the LLM is prompted toward the form Avrae tolerates.

**(A.2) Avrae compatibility for trailing-integer `!check skill N` format.** Recon required before spec lock. If Avrae interprets the trailing integer as a re-roll count or modifier, the LLM-emit format must use a different separator (`!check perception | DC 15` parsed by Virgil; Avrae sees only `!check perception` if the pipe stops Avrae's parse). The bot's narration parser handles either format; Avrae sees the first whitespace-delimited token after the skill.

**(A.3) Narration-emission write timing.** Two options:
- (a) Write the pending row BEFORE posting the bot's message to Discord. Race window: Avrae may roll before the bot's post completes. Unlikely (Discord post is sub-second) but possible.
- (b) Write the pending row AFTER posting, using the posted message's ID as `source_message_id`. Race window: Avrae may roll after the bot's post but before the write completes.

**Recommendation: (b).** The `source_message_id` field is load-bearing for the edit-cancel path (`pending_directive_delete_by_message`); needing the actual Discord message ID forces post-then-write. The matcher's `pending_directive_get_active` is sub-millisecond; Avrae's roll-trip is multi-second. Window is structurally safe even though it's not zero.

**(A.4) Stakes tier computation surface.** Pure function `compute_stakes_tier` lives in `dnd_orchestration.py` as a 9th `compute_*` sibling per Doctrine §59, OR is inlined into `resolve_directive`'s caller. Recommendation: separate pure function (`compute_stakes_tier`), §59 sibling, testable in isolation. Caller (matcher or `_dm_respond_and_post`) computes once and passes to `resolve_directive` or attaches to `ResolutionResult.texture`.

**(A.5) Texture fields on `ResolutionResult` vs separate `ResolutionTexture`.** Per §17, fields on a dataclass should be cohesive. Texture is purely about narrative rendering; resolution is purely about pass/fail. Recommendation: separate `ResolutionTexture` dataclass referenced by `ResolutionResult.texture: ResolutionTexture | None = None` — keeps the core resolution shape narrow, lets texture compose without re-tooling existing callers (which receive `texture=None` and degrade to current behavior).

**(A.6) Same-message edit-cancel path.** If the LLM emits `!check perception 15` and the bot's response gets edited (e.g. by a re-fire on verification retry), does the old pending row get cancelled? Current behavior: yes, via `pending_directive_delete_by_message` triggered from `on_message_edit`. But that handler is gated on `_is_dm_message` for human DM-typed messages; the bot's own message edits don't trigger it. **Decision needed:** extend the cancel path to also fire on bot-message edits OR accept that retried narrations can leave stale pending rows (TTL sweep cleans them up within `PENDING_DIRECTIVE_TTL_SECONDS`).

**(A.7) Player-typed `!check` flow.** Still out of scope per RESOLUTION_BINDING_SPEC.md §15.2. When a player (not the DM, not the LLM) types `!check perception` directly with no preceding directive, no pending row exists, matcher returns silent, Avrae's roll is buffered for next-player-turn consumption per Track 7 #1. Ship A does not change this. (Could be a v1.x candidate — player-initiated check binds against the player's stated intent in the prior turn — but adds intent-classification complexity that doesn't earn its keep.)

**(A.8) Two-embed UX.** Ship A produces two Discord embeds in quick succession for each LLM-emitted-roll cycle: (1) immediate narration ending in `!check perception 15`, (2) ~6s later the AUTHORITATIVE-CANON-bound outcome narration. **Confirm operator wants two embeds.** Alternative is to suppress the first embed and post only the unified outcome embed (~6-10s after the player's input); cleaner UX but requires buffering the intent narration mid-flight. Recommendation: ship two-embed for v1 (matches Ship 1's existing pattern); v1.x candidate for unified-embed if friction surfaces.

**(A.9) Cast directives.** Per RESOLUTION_BINDING_SPEC.md §11.5, cast resolution is deferred to v1.x. Ship A inherits — LLM-emitted `!cast fireball` does NOT write a pending row (or writes one that resolves to None). Same scope.

### §4.6 Work breakdown

| Session | Scope | Model |
|---------|-------|-------|
| S35 | Recon + spec drafting. Confirm Avrae compatibility of `!check skill N` format (decision A.2). Spec §11 decisions A.1–A.9. Lock difficulty band / margin tier / stakes tier mappings + nat-20/nat-1 constraint clauses. `LLM_EMIT_RESOLUTION_BINDING_SPEC.md`. | Opus medium |
| S35b | Review pass (planner-side). Flag any architectural surprises; lock framing revisions. | Opus medium |
| S36 | Implementation. New writer hook in `_dm_respond_and_post`. Prompt-side change in `build_dm_context` / `dm_philosophy.md`. `ResolutionTexture` dataclass + `compute_stakes_tier` pure function (§59 9th sibling). Difficulty-band / margin-tier / stakes-tier / crit-tier render extensions to `render_resolution_block`. ~25 new test assertions across 2 new + 1 extended file (`test_compute_stakes_tier.py`, `test_llm_emit_writer.py`, `test_resolve_directive.py` extended for texture fields). Live verify on solo play loop. | Opus high |

Implementation is materially lighter than shipped Ship 1 because the load-bearing primitives (`ResolutionResult`, `resolve_directive`, render helpers, ROLL_OUTCOME_DRIFT verifier, prompt block anchor) are already in place. Ship A is mostly a new writer + a sub-dataclass + extended render.

### §4.7 Gate criteria

- ≥25 new test assertions green
- Live verify on solo play loop: operator types intent → bot narrates + emits `!check skill <DC>` → Avrae rolls → bot auto-fires outcome narration with difficulty/margin/stakes/crit-textured block at ≤10s latency
- ≥3 LLM-emitted resolutions across a session, mixed pass/fail, all narrated correctly per `passed`
- Zero unretried `roll_outcome_drift` violations (criterion 5 from Ship 1, unchanged)
- Zero `unexpected_binding_co_occurrence:` (defensive canary still holds for combined arbitration+resolution kwargs)
- At least one nat-20 OR nat-1 event verified live; texture clause rendered correctly
- At least one stakes=high event verified live (combat or active urgent clock); texture clause rendered correctly

Two live-side gates softened against unit-test coverage if natural play doesn't produce the right cells in the verify window. Documented in spec §4.7.

### §4.8 What Ship A does NOT fix

- Cast directive resolution (inherited from Ship 1's deferral)
- Player-typed `!check` flow (inherited from §15.2)
- Combat-mode auto-init when LLM emits `!check` in combat (Phase 1's combat-mode skip preserved; resolution-binding only fires in exploration mode where Ship 1 already operates)
- F-55 #5.4 Intent-to-Avrae Resolver (separate ship — Ship A handles skill+save; #5.4 handles attack target disambiguation + spell selection)
- Stale-footer name parsing (F-58 stays v1.1)
- Skill alias map (`sneak` ↔ `stealth`, inherited from BUG_1_SPEC.md §N v1.x)

---

## §5. Ship 2 — Scene State Canon Discipline ✅ SHIPPED LIVE (S39, May 11, 2026)

**Closes Finding A** (recursive hallucination memory loop). **Doctrine §76 anchored** (Recursive hallucination memory loop / four-property latent-canon test) — promoted from candidate to numbered DOCTRINE entry on Ship 2 ship-and-verify-clean.

**Status (S39):** Eight column drops on `dnd_scene_state` via idempotent ALTER TABLE DROP COLUMN block (SQLite 3.45.1 native support). Live DB migrated cleanly. Bot restarted clean.

Five §76 deletion targets:
- `location` (freetext) — Path A taken (drop column). Reads migrate to `location_label` derived from `dnd_locations.canonical_name` via `current_location_id`. `set_current_location` is now the only writer surfacing location data to LLM context. NULL FK renders `(between locations)` deliberate ambiguity.
- `established_details` — JSON list of LLM-summarized scene details. Render line removed.
- `focus` — per-turn LLM scene-attention anchor.
- `open_questions` — JSON list of LLM-emitted "what's still unknown" entries.
- `last_scene_change` — "one short sentence" per legacy extraction prompt.

Three dead-column housekeeping drops bundled (per S38 D4 lock; pre-emptive grep confirmed zero active readers):
- `active_npcs` (S3 superseded by `get_recently_active_npcs` render-time derivation)
- `active_threats` (never read; threat model deferred)
- `tension` (legacy string `low|medium|high`; superseded by `tension_int` numeric scale)

**Code-chain cleanup:**
- `init_scene_state(campaign_id)` signature dropped seed parameter (vestigial post-`last_scene_change` deletion).
- `extract_scene_updates` legacy structured-extraction LLM call entirely removed; function writes only `last_player_action` via update_scene_state.
- `update_scene_state` shrank SCALAR_FIELDS to `{last_player_action}` only; new `DELETED_FIELDS` guard logs `update_scene_state: dropping LLM-write to deleted field '<X>' (Ship 2 §76 closure)` as defense-in-depth.
- `build_dm_context` SCENE STATE block render-line cleanup (Focus / Established details / Open questions / Last scene change all removed; Location reads from `location_label`).
- `discord_dnd_bot.py /play` stops capturing or passing seed string.
- `dnd_orchestration.py` advisory state-reference block updated to read `location_label`.

**Tests:** 105 new assertions across 2 new files — `test_scene_state_canon_deletion.py` (73) and `test_doctrine_76_four_property_audit.py` (32). Multiple existing-test fixture updates (init_scene_state signature batch sed + drop-deleted-columns from INSERTs/dicts).

**Spec:** `specs/SCENE_STATE_CANON_SPEC.md` LOCKED v1 (649 lines). **Review:** `specs/SCENE_STATE_CANON_REVIEW.md`.

**Memory:** `project_ship2_drift_evidence.md` retired post-anchor (evidence consumed by §76 instance roster).

---

## §6. Ship 3 — NPC State-Sync Boundary ✅ SHIPPED LIVE (S41, May 11, 2026, post-in-session-pivot)

**Closes Finding H** (S32 §3.6) — hydrated NPCs have no Avrae sheet, combat against them resolves against `<None>` HP / wrong-target damage. Ship 3 closes the state-sync gap via the §1b validated-suggester pattern.

**Architectural pivot in-session (S41):** The originally locked v3 §6 shape — fix candidate (a), bot-as-DM-proxy emitting `!init opt` commands under proposed §65a narrow exception — was HALTed by the Avrae bot-filter empirical finding (identical commands mutate state when human-typed, silently filtered when bot-typed; structural API boundary). Pivoted per operator decision in-session to fix candidate (a'): bot posts copy-paste sync block to `#dm-aside`; DM pastes; Avrae responds to human-typed input. §65 holds unchanged (no §65a amendment needed).

**Locked 3-line suggester sequence** (per S41 verify pass — `!init opt -h` is Avrae's hidden-toggle, NOT HP; `-hp` is the working flag at both `!init add` and `!init opt`; `!init opt` cannot set max-HP):
```
!init remove <name>
!init add <init_mod> <name> -hp <hp>
!init opt <name> -ac <ac>
```
Each pasted as a separate Discord message — Avrae filters back-to-back commands.

**Single helper** `_avrae_project_npc` in `discord_dnd_bot.py` called from two disjoint trigger surfaces:
- `/hydrate` slash command — Case A (active operator trigger).
- `_handle_init_list_event` hydration branch — Case B (passive trigger on `!init list` parse).

**Case A/B idempotency split:** Case A posts the sync suggestion (with warning text when combatant has numeric HP — mid-combat re-hydrate would lose combat state via remove+re-add). Case B silently no-ops when combatant has numeric HP (Avrae's mid-combat state is authoritative).

**`/hydrate` reframed** (operator clarification S41): emergency-fix surface for `!init madd` shortcut backfill, accidental wrong-stat correction, or parser-hit/skeleton-loaded NPCs that need Avrae sync. **NOT** the canonical NPC-stat-entry flow — the canonical path is the DM typing `!init add <init> <name> -hp <hp> -ac <ac>` directly with full stats inline.

**Doctrine accounting at S41 verify-clean:**
- **§1b second project instance proven** — Ship 3 joins Track 6 #5.1 SRD suggester. The pattern repeats: bot proposes via `#dm-aside`, deterministic gate validates the proposal is safe, DM approves by paste, Avrae executes.
- **§12.5 composition observation lands** — §17 gated-write discipline preempts §76 four-property contamination surfaces (gated boundary fails property 1 "LLM-writable"). Empirically validated by Ship 3's 20-column dnd_npcs audit having zero 4/4 hits.
- **§65a NOT anchored** — the §1b pivot dissolved the need; bot never emits `!`-commands to Avrae's channel.
- **C3 NOT anchored** — second-instance claim withdrawn; the helper is a suggester, not a writer.

**Tests:** 13 new assertions in `test_avrae_project_npc.py`. Coverage: every reason path (gate_engine_missing, gate_engine_stats_null, gate_not_in_init, noop_complete, suggested, suggested_with_warning, aside_post_failed), trigger-agnostic helper shape, telemetry one-outcome-per-path, narration-channel-untouched regression guard (post-pivot must NEVER emit to `#dm-narration`).

**Live verify Scenario A (Case A path) GREEN:** end state `!init list` shows `<13/13 HP> (AC 13)`. Both max+current HP correct AND AC set. Avrae bot-filter bypassed via DM-paste discipline. Multi-player coverage deferred to `MULTIPLAYER_VERIFY_DEFERRED.md` (Captin0bvious unavailable at verify).

**Spec:** `specs/NPC_STATE_SYNC_SPEC.md` LOCKED v1.1 (in-session pivot annotated; pre-pivot v1 language preserved in `[PRE-PIVOT]` callouts; §13.1 documents the Avrae bot-filter as structural API boundary). **Review:** `specs/NPC_STATE_SYNC_REVIEW.md`.

**Future ship candidate filed:** Track 6 #5.1 SRD resolver reshape — the existing SRD suggester emits `!init madd <srd_name>` (creates fully-statted combatant from SRD). Reshape would emit a fully-statted `!init add <init> "<name>" -hp <hp> -ac <ac>` block instead, leveraging Ship 3's flag conventions. Filed post-Ship-3 in ROADMAP candidate-next-layers as #5.1.1.

---

## §7. Ship 4 — Scene-Scope-First Identity Resolution (carries from v2 §7)

**Survives sequencing unchanged. Composes with Ship A's stakes computation.**

Finding B — canonical-name reuse, out-of-scope name matches resolving to existing canonical rows — is independent of directive-emit surface. The fix shape (build `SceneComposition` aggregator, gate identity resolution on scene scope) closes a name-resolution seam at the reference-resolution layer.

**Coupling to Ship A:** the `SceneComposition` aggregator gives Ship A's `compute_stakes_tier` cleaner inputs (combatants_in_scope, NPCs_in_scope, mode). Ship A can call `compute_stakes_tier(scene_composition, ...)` instead of plumbing four separate parameters. **Surfaced opportunity:** if Ship 4 ships first, Ship A's stakes function consumes `SceneComposition` directly. If Ship A ships first (the current sequencing), Ship A uses raw inputs and refactors to consume `SceneComposition` post-Ship-4. Either order works; this sequencing has Ship A first because playability-now outranks composition cleanliness.

**Confirm v2 work breakdown unchanged.** Adds `IDENTITY_DRIFT` verifier class.

### §7B. Ship 4.5 — Multi-Actor Temporal State (filed candidate, decision deferred to **Ship A verify checkpoint**, not Ship 1's)

Original v2 §7B.3: "Decide at Ship 1 verify checkpoint."

**Revision per S34:** Ship 1 verify ran solo; multi-actor mismatch (Scenario F) was deferred to `MULTIPLAYER_VERIFY_DEFERRED.md`. Sock-puppet F walks confirm structural verify (mismatch path doesn't regress) but do NOT produce real-play data that §7B.3 requires (">1 directive-binding ambiguity per session in **real play**").

**Decision shifted to Ship A verify checkpoint.** Ship A's verify is more natural-play-shaped (operator types intent, LLM narrates, etc.) — multi-actor batches are more likely to arise organically in a Ship A verify session than a Ship 1 verify session. If Ship A's natural-play verify produces >1 multi-actor directive-binding ambiguity, Ship 4.5 slots between Ship 4 and Ship 5 (calendar S42b). If ≤1, file v1.x.

`MULTIPLAYER_VERIFY_DEFERRED.md` Scenario F still has structural-verify value — it confirms Phase 1 mismatch path didn't regress — but is decoupled from the Ship 4.5 slot decision per S33 review §3.2 framing.

---

## §8. Ship 5 — Polish cluster (carries from v2 §8 with one reconsideration)

**Survives sequencing with one item to reconsider.**

### §8.1 Subships re-examined against Ship A primary surface

- **5a — Finding J (DC leak in player-facing directive).** Now MORE complicated. With Ship A landing, the LLM is emitting `!check perception 15` directly to `#dm-narration` — that's the player-visible directive. The DC IS visible to the player by design, because Avrae sees the embed and rolls. So "DC leak" is no longer a leak; it's intended. **Recommendation:** retire 5a or redefine it as "DC formatting consistency — when LLM emits, format should be standard `!check perception 15`, not `!check perception (DC 15)`." Decision needed.
- **5b — Finding G (debug-string leak in escalation).** Unchanged by re-plan. Still recommend silent log-only.
- **5c — Finding I template (`Karrok attempts a {error_message} .`).** Unchanged.
- **5d — §5.7 narration continuity cluster.** Probably *helped* by Ship A — the auto-fired outcome narration after a roll gives the LLM more structured constraint (the AUTHORITATIVE-CANON block) which should reduce narration-continuity drift. Reassess at end of plan.

### §8.2 Surfaced sub-ship — corpus discipline check-in

Operator considered drafting a rolling corpus (real DM responses across difficulty × stakes × margin × crit cells) in parallel with Ship A implementation.

**Recommendation: do NOT corpus-draft in parallel with Ship A.** Close the structural loop first (Ship A in S35-S36). Observe the auto-fired narration's feel across whichever cells naturally surface in S35-S36's live verify. The 24-cell matrix (4 difficulty × 3 stakes × 2 passed) is probably overshot — most cells won't have meaningful texture distinction at the LLM's current output quality. Better discipline: ship structural binding, observe which cells produce flat/wrong-feeling narration in actual play, draft corpus *for those specific cells*.

**Exception worth considering:** the four crit-tier cells (nat-20-passed, nat-20-failed, nat-1-passed, nat-1-failed) are rare (~5% of rolls) but carry outsized narrative weight. Pre-corpus work on those cells specifically may earn its keep — when one fires in live play, the LLM's first attempt sets the tone for an entire campaign. Operator-side decision: lock 4-8 exemplar narrations for crit-tier cells during Ship A spec, OR defer to post-Ship-A observation. Recommend defer-to-observation; nat-20-failed and nat-1-passed are the most interesting cells and predicting their texture without observing the LLM's first attempt is hard.

The general principle (close structural loop, observe, corpus-draft against observed friction) holds.

---

## §9. F-55 cluster sequencing concerns

The F-55 cluster ships (#5.4 Intent-to-Avrae Resolver, #5.2 NPC Turn Automation, #5.3 Combat Cockpit, #5.5 NPC State-Sync = current Ship 3) sit downstream of the multiplayer-fixes plan and inherit architectural commitments.

**Re-examined against Ship A primary surface:**

- **#5.4 Intent-to-Avrae Resolver.** v2 framing: "unlocks #5.2 + #5.3 downstream; inherits ResolutionResult binding template + SceneComposition aggregator." Now needs to be more precise. Ship A *is* a primitive form of intent-to-Avrae resolution: operator types intent → LLM resolves to `!check skill DC`. That's the skill-check / save branch. #5.4 extends to the **attack / cast** branches (target disambiguation across multiple init-list combatants, weapon selection from multi-attack PCs, spell selection from multi-spell casters). Ship A is a structural prerequisite for #5.4 in the sense that the binding-block pattern is established; #5.4 applies the same shape to attack/cast directives. **No re-sequencing within F-55 cluster** — #5.4 still ships after the multiplayer-fixes plan completes.
- **#5.2 NPC Turn Automation.** Unchanged. Builds on #5.4.
- **#5.3 Combat Cockpit.** Unchanged. Builds on #5.4.
- **#5.5 (= current Ship 3).** Unchanged — ships in multiplayer-fixes plan.
- **#5.1 Combat Entry Assist.** Pending live verify; can fit between any two sessions. Independent of Ship A.

**Surfaced architectural lineage:** Ship A's AUTHORITATIVE-CANON block with difficulty/margin/stakes/crit-tier scaling is a **richer binding-block template** than shipped Ship 1's basic pass/fail block. The richer template carries downstream into #5.4's attack-resolution binding (margin → hit/miss + damage-roll texture; stakes → "this was the final boss" weight; crit-tier → existing crit-hit mechanic preserved + textured). Ship A is upstream of #5.4 in two senses: shipped binding-block pattern + the richer texture template that #5.4 inherits.

---

## §10. Doctrine candidates

Carries from v2 §9 plus two surfaced in S34:

- **§76 Recursive hallucination memory loop** — **ANCHORED S39** (Ship 2 verify clean; three project instances: S22 #2 chroma contamination, S32 location drift, S36 time-of-day drift).
- **§65 amendment (bot-as-DM-proxy narrow exception)** — **NOT ANCHORED.** S41 in-session pivot to §1b suggester pattern dissolved the need; §65 holds in its original form (bot does NOT emit `!`-prefixed commands to Avrae's channel). The pivot was forced by the Avrae bot-filter empirical finding (identical commands mutate state when human-typed, silently filtered when bot-typed — structural API boundary documented in `NPC_STATE_SYNC_SPEC.md` §13.1).
- **§1b validated-suggester pattern second instance** — **NEW filed S41** post-pivot. Ship 3's `_avrae_project_npc` suggester joins Track 6 #5.1 SRD suggester as §1b's second project instance. Pattern: bot proposes via `#dm-aside`, deterministic gate validates the proposal is safe, DM approves by paste, Avrae executes. Lands in DOCTRINE.md §1b's instances list.
- **§77 Combat narration is atmospheric continuity, not adjudication** — **ANCHORED S43** (Dumb combat ship verify clean). The cliff-edge for any LLM-driven combat render layer: combat narration is allowed to describe scene state per listener-confirmed events; it is NOT allowed to infer tactical outcomes / hidden intent / optimal targeting / consequences beyond listener+engine. The S43 prompt-side enforcement (`_COMBAT_NARRATION_INVARIANTS` constant in `dnd_orchestration.py`) is the runtime guard; verified live across BLOODIED + DOWNED + mode-flip-cleanup. **S44 added information-side enforcement** (`suppress_for_combat_narration` flag suppressing 10 `build_dm_context` blocks during combat narration); the two layers compose. Future F-55 combat ships (#5.2 NPC Turn Automation, #5.3 Combat Cockpit, #5.4 Intent-to-Avrae Resolver) inherit the line — any that would cross requires re-spec.
- **§77 two-layer enforcement composition** — **PROMOTED to §78 mode-transition state-reset surfaces, ANCHORED S45.** What was filed at S44 as a candidate two-layer composition pattern (instruction-side + information-side) gained its third structural instance at S45 (COMBAT_END dispatch carries both layers, AND the surrounding boundary infrastructure of mechanical cleanup + narrative buffer reset + transitional-window silence). The broader pattern surfaces: mode transitions are state-reset surfaces requiring four coordinated layers — mechanical cleanup, narrative-buffer reset, transitional-window structural silence, boundary atmospheric closeout (with both-layer enforcement). §77 governs WHAT can be narrated; §78 governs WHEN narration is structurally appropriate.
- **§78 Mode-transition state-reset surfaces** — **NEW ANCHORED S45** (Combat-Boundary Hardening Bundle verify clean). Three project instances of the two-layer enforcement pattern (S43 instruction-side + S44 information-side + S45 boundary closeout carrying both) provide the structural backbone. Operational discipline: any handler that flips `dnd_scene_state.mode` MUST reset narrative buffers at the boundary, MUST gate the transitional window where mechanical state isn't fully populated, and SHOULD dispatch a boundary atmospheric closeout for the prior mode. Future mode-transition handlers (rest-event !lr/!sr parallel surface, exploration→travel, downtime transitions) inherit the four-layer audit at design time.
- **§17+§76 composition observation** — **FILED S41 per Ship 3 audit** (lands in DOCTRINE.md as §76 sibling note): §17 gated-write discipline preempts §76 four-property surfaces (gated boundary fails property 1). Operational consequence: route new persisted scalar columns through single-writer helpers with appropriate gates at design time, and the four-property audit becomes a regression guard rather than a deletion-finding tool.
- **Engine-bound binding > validator** (filed S34 as DOCTRINE.md candidate C1; three instances now after Ship A = Track 7 #1 + Ship 1 + Ship A). Anchoring deferred to a future doc-update pass per locked decision 11 + S41 review; promotion to numbered §-entry when operator and planner agree it's time. Fourth instance candidate: cast resolution binding (v1.x).
- **Reused vocabulary across sibling verifier classes** (filed S34 as DOCTRINE.md candidate C2; one instance — Ship 1's `ROLL_OUTCOME_DRIFT` reuses `VERDICT_CONTRADICTION`'s phrase tables). Anchor when second sibling class reuses the same vocabulary tables.
- **Single-writer compatible with multiple disjoint trigger surfaces** (filed S36 as DOCTRINE.md candidate C3; one instance — Ship A's `dnd_pending_roll_directives.dc` column). **NOT promoted by Ship 3** — the §1b pivot dissolved Ship 3's second-instance candidacy (helper is a suggester, not a writer). C3 stays at one project instance pending genuine future second instance.

---

## §11. Calendar estimate (revised)

Best case 11 days / slow case 15. v2 was 9/13; +2 from Ship A insertion.

| Session | Calendar day (best) | Calendar day (slow) | Status |
|---------|---|---|---|
| S33 (Ship 1 spec + review) | day 1 | day 1-2 | ✅ DONE |
| S34 (Ship 1 implementation) | day 2 | day 3 | ✅ DONE |
| S35 (Ship A spec + review) | day 3 | day 4-5 | ✅ DONE (May 11, 2026 — spec LOCKED v1 + review applied) |
| S36 (Ship A implementation) | day 4 | day 6 | ✅ DONE (May 11, 2026 — Ship A ✅ SHIPPED LIVE; 9 patches; ~120 test assertions; live verify clean) |
| S37b (Ship 2 spec draft) | day 5 | day 7 | ✅ DONE (May 11, 2026) |
| S38 (Ship 2 spec review) | day 5 | day 7 | ✅ DONE (May 11, 2026) |
| **S39 (Ship 2 implementation + §76 anchored)** | **day 5** | **day 7-8** | **✅ DONE (May 11, 2026)** |
| S40 (Ship 3 spec draft) | day 5 | day 7 | ✅ DONE (May 11, 2026) |
| S40b (Ship 3 spec review) | day 5 | day 7 | ✅ DONE (May 11, 2026) |
| **S41 (Ship 3 implementation + in-session pivot to §1b suggester)** | **day 5** | **day 7-8** | **✅ DONE (May 11, 2026)** |
| S42 (Ship 4 spec + review + implementation) | day 10 | day 14-15 | pending |
| S42b (Ship 4.5 if slotted at Ship A verify) | day 10.5 | day 15.5 | conditional |
| S43 (Ship 5 polish) | day 11 | day 15 | pending |

---

## §12. Locked decisions (operator review, May 11, 2026)

All 11 §12 decisions from the original v3 draft + one new decision (12, wrong-skill behavior) locked by operator. Listed verbatim below with lock outcomes. Spec drafting at S35 carries these forward as input; spec body adds any sub-decisions surfaced during recon.

1. **Approve the re-sequence.** v3 supersedes v2 as canonical plan post-recon. ✅ LOCKED.
2. **DC source for LLM emit (A.1).** Inline `!check skill DC` per recommendation (a). Prompt-side change instructs LLM to always include a DC in the emission. ✅ LOCKED. Pending Avrae compatibility recon (A.2).
3. **Avrae compatibility recon (A.2).** Quick test in `#dm-narration` from a fresh test campaign: type `!check perception 15`, observe Avrae's behavior. Result must land before S35 spec drafting. If Avrae rolls perception normally → form (a) holds. If Avrae chokes or interprets the 15 semantically → fall to (a') with pipe/flag separator (parser-side adaptation). ⏳ **PENDING — pre-spec-promotion blocker.**
4. **Stakes computation surface (A.4).** `compute_stakes_tier` as §59 9th sibling pure function in `dnd_orchestration.py`. ✅ LOCKED.
5. **Texture dataclass shape (A.5).** Separate `ResolutionTexture` dataclass referenced by `ResolutionResult.texture: ResolutionTexture | None = None`. ✅ LOCKED. Keeps core resolution shape narrow; texture composes additively without re-tooling existing callers.
6. **Edit-cancel path on bot messages (A.6).** Accept stale rows + TTL cleanup; do NOT extend cancel-on-edit to bot-message edits. ✅ LOCKED. **TTL = 300s (5 min), set in `avrae_listener.py:28`.** Operator asked: is 300s long enough for phantom-binding risk? **Planner assessment: KEEP 300s for v1.** Phantom binding requires (long gap) AND (LLM re-emit during gap) AND (Avrae roll arriving in stale-row TTL window) — three-condition compound, structurally rare in natural play. Operator's natural cycle is ~25s (intent → narrate → roll → outcome); 300s gives 12x headroom for AFK gaps. If multiplayer logs show actual phantom binding, tighten to 60-90s in v1.x. No v1 tightening required.
7. **Two-embed UX (A.8).** Two embeds confirmed (initial narration + outcome narration). ✅ LOCKED. Matches Ship 1's existing pattern; unified-embed delayed post stays v1.x candidate if friction surfaces.
8. **Ship 4.5 decision criterion (revised §7B).** Shifts from Ship 1 verify checkpoint to Ship A verify checkpoint. ✅ LOCKED. Sock-puppet F walks confirm structural verify but don't produce real-play data per §7B.3 criterion ">1 directive-binding ambiguity per session in real play"; Ship A verify is more natural-play-shaped.
9. **Ship 5 sub-ship 5a (Finding J / DC leak) reconsidered.** Retire 5a entirely. ✅ LOCKED. Finding J ceases to be a leak under Ship A's design — LLM-emitted directive shows the DC to the player by design because Avrae sees the embed and rolls. The DC was always going to be visible; v2 Ship 5a was solving the wrong problem.
10. **Corpus discipline.** Defer to observation. No parallel corpus drafting during Ship A implementation. ✅ LOCKED. Discipline: close structural loop in S35-S36, observe S36-verify cells, draft corpus *for those specific cells* post-verify if texture friction surfaces. Crit-tier exception note in §8.2 stands but defaults to defer-to-observation.
11. **Doctrine candidate C1 promotion timing.** Wait for Ship A verify to confirm third instance proves out. Don't pre-commit to anchoring. ✅ LOCKED. C1 stays a DOCTRINE.md candidate; promotion to numbered §-entry happens after Ship A's live verify if-and-only-if the engine-bound binding > validator shape holds across all three instances cleanly.
12. **Wrong-skill matcher behavior (NEW — Ship A spec §11 candidate 12).** When matcher receives a roll whose actor matches but skill does NOT match the pending directive: **option (b) — post #dm-aside clarification + leave pending directive row alive until correct skill arrives or TTL expires; wrong-skill roll falls through to normal player-input buffer flow.** ✅ LOCKED at HIGH confidence per operator. Aside copy template: `"expected {pending_skill}, got {avrae_skill}; the {pending_skill} directive is still active."` Variants (a) silent and (c) auto-fire-against-wrong-skill rejected: (a) leaves players confused with no signal, (c) violates the DM's skill choice. The aside surfaces the mismatch without overriding the DM's directive. Spec adds as `_wrong_skill_aside` analog to `_wrong_actor_aside` shipped Ship 1 §K; matcher's skill-mismatch branch flips from silent-ignore to log+aside.

---

## §13. What this plan is NOT

- Not a code change. Planning artifact. Code lands in S36 (Ship A implementation) per §11 calendar; Ship 1 (DM-typed-directive surface) already shipped in S34.
- Not a Ship 1 rework. Shipped Ship 1 stays as-shipped — its surface (DM-typed directive) is real, just secondary. Ship A's matcher composes with Ship 1's writer (both call `pending_directive_upsert`, both trigger the same `_handle_dm_roll_arrival` consumer).
- Not a single canonical-plan-forever — when Ship A's verify exposes architectural surprises, the plan adapts. Ship 4.5's slot decision in particular waits for empirical signal at Ship A verify per locked decision 8.

---

## §14. Tabular handoff (post-lock state)

| Field | Value |
|-------|-------|
| **Doc** | `/home/jordaneal/virgil-docs/MULTIPLAYER_FIXES_V3_DRAFT.md` |
| **Status** | DRAFT, all 12 §12 decisions LOCKED (operator review May 11, 2026). Promotion to canonical pending Avrae A.2 recon results. |
| **Primary insertion** | Ship A — LLM-Emitted-Directive Resolution Binding — at front of post-Ship-1 queue. |
| **Ships surviving v2 sequencing** | Ships 2, 3, 4, 4.5, 5 — all confirmed; Ship 5 sub-ship 5a retired (Finding J no longer a leak). |
| **Calendar delta** | +2 days (v2 9 best / 13 slow → v3 11 best / 15 slow). |
| **Ship 1 status** | shipped, lineage preserved, surface confirmed as secondary not primary. |
| **Decisions locked** | 12 total. 11 from original draft §12 + 1 new (decision 12 wrong-skill matcher behavior, HIGH confidence option (b) post-aside-leave-row-alive). |
| **PENDING_DIRECTIVE_TTL_SECONDS** | 300s (5 min); kept for v1. Phantom binding requires three-condition compound (long gap + LLM re-emit + roll arriving in stale window); rare in natural play. v1.x tighten only if multiplayer logs show actual events. |
| **Pre-promotion blocker** | Avrae A.2 recon: type `!check perception 15` in a fresh test campaign's `#dm-narration`, observe Avrae behavior. If clean → form (a) holds → promotion. If chokes → fall to (a') with parser-side separator adaptation → minor decision revision before promotion. |
| **Doctrine candidates** | C1 wait for Ship A verify before anchoring (locked decision 11). C2 reassess at Ship A. New candidate (single-writer compatible with multiple trigger surfaces) filed at Ship A. |
| **Architectural lineage** | Ship A extends shipped Ship 1's infrastructure (ResolutionResult, resolve_directive, render_resolution_block, ROLL_OUTCOME_DRIFT, `_fire_resolution_narration`) with `ResolutionTexture` sub-dataclass + `compute_stakes_tier` §59 sibling + LLM-emit writer hook in `_dm_respond_and_post`. Richer binding-block template carries downstream to F-55 #5.4. |
| **Out-of-scope confirmed** | Cast resolution (v1.x), player-typed `!check` (§15.2), combat-mode auto-init (F-55 cluster), F-58 stale-footer, skill alias map. |
| **Next action** | Operator runs Avrae A.2 recon test. Result lands → planner reviews → v3 promotes to replace v2 → S35 Ship A spec drafting begins with all 12 decisions as input. |
