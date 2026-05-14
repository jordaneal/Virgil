# SCENE_LIFECYCLE_V1_SPEC.md

**Status:** LOCKED — Session 3 implementation complete (May 13, 2026). All 15 §11 decisions (§11.A–§11.O) locked. Implementation shipped: `compute_scene_lifecycle_directive` in `dnd_orchestration.py`, `build_dm_context`/`dm_respond` integration in `dnd_engine.py`, in-memory dicts + activity wiring + `/compress` in `discord_dnd_bot.py`, 28-test suite in `test_scene_lifecycle_directive.py`.

**Patched S53 — §1.F.c removed per live-verify finding.** S53 live verify (May 2026) surfaced an LLM-forgeable signal pattern: scene-padded NPC introductions resetting the stagnation counter and defeating detection. §1.F shrinks from six signals to five. §11.E lock unchanged — the "(a) §1.F signals only" restriction holds; the §1.F set changes underneath it. See §1.F footnote and §12.10 for v1.x direction. Patch ref: `planner-scratch/scene_lifecycle_v1x_findings.md` Finding 1.

**Patched S63 (proactive, doc-only) — §1.F.e removed per identical-shape rule.** S63 doc-spec alignment patch (May 2026). Identical-shape rule to §1.F.c: §1.F.e (consequence upsert DM-side) is the second LLM-extracted signal in the locked set and creates the same perverse-incentive loop. **Inventory-before-patch finding:** §1.F.e was specced but NEVER wired in the S56 Quest Layer implementation — the bot has been running on (a)/(b)/(d) only since v1 ship. This patch is retroactive doc-spec alignment, NOT a code change. The architectural harm §1.F.c surfaced was prevented for §1.F.e by implementation gap rather than deliberate design — the patch makes that prevention explicit. §1.F shrinks from five signals to four (now (a)/(b)/(d) — operator/Avrae-driven only; no LLM-extracted signals remain). F-64 candidate filed (LLM-extracted activity signals as perverse-incentive surfaces — two project instances). Patch ref: `planner-scratch/scene_lifecycle_v1x_findings.md` Finding 1 update. Prior draft was against ROADMAP alone; v0.1 sketch (`planner-scratch/scene_lifecycle_v1_sketch_v0_1.md`) supersedes and reshapes three areas: T2 deferred to v1.x, three new §11 decisions (§11.L–§11.N), three new architectural sections (86% quiet baseline, X7 single-source rule, climactic-hold suppression). §1 decisions go to operator + planner review in Session 2; §11 decisions (14 total: §11.A–§11.N) require Jordan's call before Session 3 implementation can open.

**Session:** S52 (Phase 1 spec drafting), May 13, 2026
**Ship:** Motion Systems Track — Scene Lifecycle v1
**Addresses:** F-54 stagnation drift (parent failure: scene immortality)
**Precedent specs:** `SCENE_STATE_CANON_SPEC.md`, `NPC_STATE_SYNC_SPEC.md`, `COMMITTED_ACTION_RESOLUTION_SPEC.md`

**Note on v0 sketch:** Session prompt specified the v0 sketch would be pasted/attached by the operator. No separate document was included. This spec was drafted against the ROADMAP.md §Scene-Lifecycle-v1 entry (the functional equivalent of a sketch for this ship), cross-referenced against six recon findings. If a separate v0 document exists, Session 2 review should reconcile any divergence; no architectural HALT was warranted given the ROADMAP entry's specificity.

---

## §1. Proposed decisions

These are Code's recommendations for decisions the spec makes. They are NOT locks. Each goes to operator + planner review in Session 2 before any implementation opens.

---

### §1.A — §59 pure-function shape confirmed

**Recommendation: YES — `compute_scene_lifecycle_directive` is the 11th §59 sibling.**

Scene lifecycle directive is a §59 pure-function-in-orchestration sibling: `compute_scene_lifecycle_directive(scene_state, stale_turns, trigger_kind) → (body, signals)`. Reads state, returns directive string + signals dict, writes nothing. Call site in `build_dm_context` wraps in try/except, emits always-fire log line, soft-fail so directive errors never block narration.

**Reasoning:** Zero §17 pressure (no writes). Testability + per-turn baseline telemetry inherited for free. Consistent with every directional ship since S22 #1.

---

### §1.B — In-memory stale counter per guild

**Recommendation: In-memory per-guild dict, NOT a persisted field.**

The stale turn counter (`_scene_stale_turns: dict[int, int]`, keyed by guild_id) lives in-memory in `discord_dnd_bot.py`, same substrate pattern as `_combat_beats` (§78.6 precedent, §78.5 substrate-agnostic application). Incremented on turns that carry no activity signal; reset on turns that do. Passed into `compute_scene_lifecycle_directive` from the call site.

**Reasoning:** §76 four-property audit — a persisted stale-turn counter would be: LLM-writable? No (deterministic writer). Persisted? Yes. Retrieved into prompt? Yes, if it appeared in scene_state block. Narratively inferential? Borderline (a high stale count is not "a one-line phrase" — but displaying it would invite narrative elaboration). The safest call is in-memory: avoids the persisted+retrieved properties entirely, no §76 risk. Pattern has two project instances for in-memory mode-related counters (combat beats §78.6, and the Avrae RollBuffer). §17 has no claim on in-memory state.

---

### §1.C — Directive fires selectively (threshold-conditional), not every turn

**Recommendation: Empty body return below threshold. Directive string only at or above soft threshold.**

`compute_scene_lifecycle_directive` returns `('', {})` when stale counter is below soft threshold. At soft threshold: returns soft-nudge text. At hard threshold: returns strong directive text. At call site, empty body is the "skip" signal per §59 contract.

**Reasoning:** Prompt-size budget discipline. Current directives component mean ~4,600 chars (range 3,831–6,206 across post-S45 exploration turns). Scene lifecycle at ~300 chars adds ~6.5% to mean directives. Acceptable when firing; adding it every turn on every exploration message would push toward the observed max on baseline turns. Selective fire is also more semantically honest — the directive should fire when needed, not as ambient noise.

---

### §1.D — No mode transition in v1

**Recommendation: Scene Lifecycle v1 does NOT write to `dnd_scene_state.mode`.**

The compression/retirement is narrated within the current mode. The directive instructs the LLM to transition the narrative; the system-level mode flag is untouched. If the player's response to the narrated transition triggers a mode flip (e.g., "we head out" → `/travel`), that follows existing mechanics.

**Reasoning (v0.1 §4 corrected framing):** v1 is **pattern-reuse, not a §78 fourth instance**. §78's three anchored instances all involve external boundary signals (Avrae mode-flip events: `!init end`, `!game lr`, `!game sr`). Scene Lifecycle v1 fires on internal accumulation state (stale counter), not an external mode-flip event. Anchoring v1 as a §78 fourth instance would stretch "mode-transition boundary" to "any state-reset surface regardless of trigger origin" — operator's correction from v0 sketch stands. What v1 borrows from §78 is architectural discipline (soft-fail throughout, in-memory substrate pattern, telemetry-per-invocation), not the doctrine. §78.5's fourth-instance promotion check stays open for a future non-Avrae external mode-flip boundary. §78.6 (render-vs-marker content conditional) does NOT apply at v1: the tiered directive (soft vs. strong) plus explicit `/compress` sidestep the render-vs-marker question entirely; it reopens only if v1.x adds auto-fire without tier escalation. Filing the v1.x §78 mode-flip implication explicitly in §12.4.

---

### §1.E — Directive text is DM-prompt-side only; not posted to Discord

**Recommendation: Directive string goes into `build_dm_context` output, not posted via `channel.send`.**

Consistent with all existing directives (pacing, central_thread, consequence, commitment, time, combat narration). Player sees only the LLM's narrated response to the constraint.

**Reasoning:** Players don't see directive text. The directive is an instruction to the DM LLM, not a player-facing signal. Posting it directly would break the fourth wall and violate the §1a LLM-as-constrained-narrator model.

---

### §1.F — Stale counter reset signal definition (Recommendation B: medium scope)

**Recommendation: Stale counter resets on (a) location change via `set_current_location`, (b) mechanical event (Avrae roll consumed by RollBuffer), ~~(c) NPC upsert was_new=True~~ [DROPPED S53 — see footnote], (d) `advance_time` called (rest or travel), ~~(e) consequence upsert~~ [DROPPED S63 doc-only — see footnote; never wired in S56 implementation].**

These are the "something changed in the world" events. The stale counter does NOT reset on bare player text alone (that would defeat the detection).

**Reasoning:** Narrow (location + roll + NPC only) misses consequence and time events that do advance the scene. Broad (any player turn) defeats stale detection. Medium covers the canonical "this scene has progressed" signals without opening the counter to trivial resets. The signals align with existing event telemetry and are derivable without new instrumentation.

**S53 patch footnote (May 2026):** Live verify surfaced LLM-forgeable signal pattern: scene-padded NPC introductions reset the stagnation counter, defeating detection. The LLM, when given a stale scene with no new pressure to render, invents fresh NPCs to fill the narrative space (e.g. naming an unnamed innkeeper "Marla" mid-stagnation). The NPC extractor catches these as `was_new=True` and resets the stale counter, perversely rewarding the exact behavior the directive is meant to prevent. §1.F.c dropped pending v1.x architectural revisit of LLM-extracted signal provenance. §11.E lock unchanged — "§1.F signals only" stands; the §1.F membership changes underneath it. See `planner-scratch/scene_lifecycle_v1x_findings.md` Finding 1 and §12.10 below.

**S63 patch footnote (May 2026, proactive doc-only):** Drops §1.F.e per identical-shape rule to §1.F.c. Both signals are LLM-extracted from narration; both create perverse-incentive loops in stagnation-detection contexts (LLM elaborates into stale scene → extractor catches the elaboration → counter resets). **Inventory-before-patch evidence:** §1.F.e was specced but never implemented — the S56 Quest Layer ship wired stale-counter resets on §1.F.a/b/d only. No consequence-upsert code path ever called `_reset_scene_stale`. The patch is doc-spec alignment, not a code change; the harm §1.F.c caused (S53 live verify) was prevented for §1.F.e by implementation gap. Now made explicit. Post-S63 §1.F set is (a)/(b)/(d) — operator-typed location changes, Avrae mechanical rolls, advance_time (rest/travel). The structural rule is now anchored at the v1 level: **§1.F resets fire only on operator-driven or Avrae-driven signals; no LLM-extracted signal can reset the stagnation counter.** Two project instances of the failure mode (NPC was_new wired+dropped; consequence upsert specced+never-wired+formally-dropped) trigger F-64 candidate filing in FAILURES.md.

---

### §1.G — No generalization of `reset_narrative_buffers_on_combat_exit` in v1

**Recommendation: v1 does NOT generalize or rename the existing combat-exit buffer reset function. Scene compression is not a mode transition; no buffer reset needed in v1.**

The LLM's response to a compression directive naturally overwrites the rolling buffers on the next `_dm_respond_and_post` call (because `update_scene` and `update_last_dm_response` write on every narration post). No explicit pre-reset needed.

**Reasoning:** Generalization adds complexity and a §17 amendment. The combat-exit buffer reset addresses a specific structural failure (stale combat framing polluting exploration narration across a mode boundary). Stale-within-exploration framing is a softer problem — there's no mode boundary, so the contamination is less severe and self-correcting on the next narration post. If playtesting surfaces explicit stale-buffer pollution from scene compression, generalize then with evidence. File as §12.

---

### §1.H — `/compress` DM command ships with v1

**Recommendation: YES — `/compress [reason: optional]` is a thin DM-only slash command.**

The command fires `compute_scene_lifecycle_directive` with `trigger_kind='explicit'` at the hard-threshold level, wraps in `_dm_respond_and_post`. The `reason` parameter is an optional seed that goes into the directive's scene-context block.

**Reasoning:** CC corpus finding Q3: Matt-initiated compressions are the dominant signal (`matt_initiated` buildup dominant). The DM needs a way to compress explicitly — SCENE_CUT (2.7% of CC corpus) is the real-DM equivalent. A DM-only `/compress` command is thin transport-layer wiring of the same §59 function; no new architecture. Without it, the DM can only compress by narrating it naturally, which relies on the LLM complying without a structural constraint.

---

### §1.I — `compute_scene_lifecycle_directive` placement: after commitment directive

**Recommendation: Append after commitment directive in `build_dm_context`.**

Scene lifecycle is an instructional directive (what to do with this scene), similar to commitment. Pacing is framing; consequence is context; scene lifecycle is instruction. Placement: last instructional directive, before the HARD STOP RULES block.

**Reasoning:** Consistent semantic grouping. The LLM processes last-instruction-wins per §2; instruction-side placement at the end of the directive chain is stronger than mid-chain placement. Matches the adjudication-constraint pattern (top-of-prompt + end-of-prompt per §2 doctrine).

---

### §1.J — Tiered directive (soft-nudge + strong) ships with v1

**Recommendation: Two tiers — soft at N=3 stale turns, strong at N=6. Named constants in code, not locked values in spec.**

- Soft-nudge text (~150 chars): tells DM the scene is getting thin, suggests transitioning
- Strong directive text (~300 chars): tells DM to compress this scene NOW — close loop, retire if NPC purpose done, cut if no new information possible

Named constants: `_STALE_SOFT_THRESHOLD = 3` and `_STALE_HARD_THRESHOLD = 6` in `dnd_orchestration.py`. Calibrated post-ship from `scene_lifecycle:` telemetry.

**Reasoning:** Single-tier means the directive fires full-strength on turn 6 having given no intermediate signal. Tiered gives the LLM (and DM via observe-and-adjust) an escalation arc. The calibration signal: if `soft_fire` correlates highly with fast stale-scene closures in the narration, threshold is right; if scenes persist past the soft fire for 4+ more turns before the strong fires, the soft threshold is too early. Named constants let next Code session tune without a spec amendment.

---

### §1.K — §76 audit pass: no new persisted fields require LLM-writable paths

**Recommendation: No new `dnd_scene_state` or `dnd_campaigns` columns introduced in v1 that hit 4/4 §76 properties.**

The in-memory counter (§1.B) sidesteps the persisted+retrieved properties. If v1 introduces any persisted column (e.g., for a `/compress` audit log), it must pass four-property audit at column-add time per §76 operational discipline.

**Reasoning:** §76+§17 composition observation (S41): columns with §17-disciplined single-writer helpers structurally cannot become §76 contamination surfaces — property 1 ("LLM-writable requires a non-gated write path") is closed by the helper gate.

---

## §2. Problem statement

**Parent failure: F-54 Stagnation drift.** FAILURES.md §F-54 names this as the **architecture-vs-experience gap**: the system correctly persists world state, NPCs, locations, combat, and consequences — but does not visibly evolve over a session. Sessions feel good for ~30-60 minutes then drift over longer arcs. The failure mode: "endless present tense" — the world persists but does not move. Authoritative goal-level framing: THE_GOAL.md "the world should breathe" and "memorable details should recur intentionally, not compulsively."

**F-54 symptom set (subordinate failures):** Scene immortality (the direct target of v1), F-52 motif compulsion subsumed as granular instance (F-52 stays in catalog for traceability; F-54 is the umbrella diagnostic), advancement starvation, equal-weight narration.

**Scene immortality defined:** Scenes that have run their course — NPC purpose resolved, objective achieved, player verbs repeating without escalation, no new information possible — continue indefinitely because there is no structural signal to the DM LLM that the scene should end. The LLM treats every detail as potentially permanent; without explicit motion-system pressure, scenes become immortal and the campaign loses momentum even when every individual mechanism works correctly.

**Current gap:** The pacing directive (Track 4 #1) tells the LLM how intense the scene should be, but not when to end it. The consequence directive surfaces existing canon, but not whether the current scene has exhausted its material. The commitment directive bounds player action, but not scene lifespan. No structural compression signal exists.

**Track 4 #3 Time Progression (✅ SHIPPED, S27)** closed the "the world doesn't visibly evolve" symptom of F-54 — the calendar advances, day phases cycle, travel compresses time. Scene Lifecycle v1 closes the adjacent symptom: **scenes within a day phase don't close on their own.** Sits downstream of the structural floor (Track 7 adjudication) and upstream of the experience texture layer.

---

## §3. Architectural shape

Scene Lifecycle v1 is a **§59 pure-function-in-orchestration sibling** — the 11th sibling in the established pattern.

```
dnd_orchestration.py:
  compute_scene_lifecycle_directive(
      scene_state: dict,
      stale_turns: int,
      trigger_kind: str   # 'auto_soft' | 'auto_hard' | 'explicit'
  ) → (body: str, signals: dict)
```

The `stale_turns` parameter is passed from the call site in `discord_dnd_bot.py`, which maintains the in-memory per-guild counter. The function reads scene_state for mode-gate (returns empty body if mode='combat') and NPC/location context to personalize the directive text. Returns `('', {})` below soft threshold; returns soft-nudge body at soft threshold; returns strong directive body at hard threshold.

**Call site:** `build_dm_context` in `dnd_engine.py`, after commitment directive. Call site reads `_scene_stale_turns[guild_id]` from the in-memory counter (passed as param or read via a module-level accessor — architecture detail for Session 3). Wraps in try/except. Always-fire log line: `scene_lifecycle: campaign={N} mode={mode} stale_turns={N} tier={none|soft|strong} fired={0|1}`.

**In-memory stale counter** maintained in `discord_dnd_bot.py`:
- `_scene_stale_turns: dict[int, int]` — keyed by guild_id, default 0
- Reset on activity-signal events (see §1.F)
- Incremented on `on_message` player turns that produce no activity signal
- Bounds: never goes negative; reset to 0 not decremented

**`/compress` command** in `discord_dnd_bot.py`:
- DM-only (same gate as `/play`, `/advance`)
- Reads scene_state, fires `compute_scene_lifecycle_directive` with `trigger_kind='explicit'` at hard-threshold level
- Wraps in `_dm_respond_and_post`
- Resets `_scene_stale_turns[guild_id]` to 0 after dispatch

---

## §4. Trigger taxonomy (v1)

v1 ships ONE trigger class. T2 is deferred to v1.x per v0.1 §11.N (see §11.N for the deferral confirmation decision). T3 and T4 remain v1.x candidates as before.

### Shipping in v1:

**T1 — Turn-count stale signal (covers TEMPORAL_MONTAGE 26.0%; assists INVESTIGATIVE_CLOSURE 3.6%; indirect assist for LOCATION_DEPARTURE 18.9% at delay)**
- Stale counter reaches soft or hard threshold
- Soft directive: "This scene is getting thin — consider transitioning the party. If the current location or NPC has served its purpose, compress forward. If there's unresolved tension, escalate rather than compress."
- Hard directive: "Compress this scene now. Close any open beats quickly, summarize the remaining exchange in one sentence, and move the party toward the next meaningful event. Do not extend the current location or NPC interaction further."

### v1.x candidates (not shipping):

**T2 — Player closure intent (deferred per §11.N; covers SCENE_CUT + LOCATION_DEPARTURE assists)**
- Detected in player text: phrases like "we head out", "let's go", "I leave", "we move on", "time to go"
- Fires strong scene-exit directive on detection, bypassing stale counter
- Deferred rationale: T2 introduces phrase-vocabulary detection on player text — a new detection surface with false-positive risk that CC findings don't directly ground. The CC Q3 finding shows DM-initiated compressions (`matt_initiated`) as dominant; player-side closure-intent is a minority fraction. T2 phrase vocabulary needs corpus grounding before shipping. v1.x once T1 logs show whether player-side missed compressions surface as friction. See §11.N for operator's deferral confirmation decision.
- What falls through without T2: player-initiated immediate scene close at non-stale thresholds — a **UX gap** (N more turns before auto-fire) not a **coverage gap** (same events eventually handled via T1)

**T3 — NPC purpose resolved signal (covers NPC_DEPARTURE, 9.3% of CC corpus)**
- Requires NPC state tracking ("purpose: resolved" or equivalent), which is not currently a dnd_npcs field
- Filed as v1.x requiring a dnd_npcs amendment and NPC-purpose-resolution detection ship

**T4 — Verb-repeat pattern (covers STALE_HOLD_CANDIDATE inverse detection)**
- Requires player-input history with verb lemmatization
- CC findings show 1 record in 365 for STALE_HOLD_CANDIDATE (structurally thin coverage)
- T1 covers the same territory deterministically; deferred per observed-friction discipline

---

## §5. Directive design

### Soft-nudge text (tier 1, at `_STALE_SOFT_THRESHOLD` turns)

```
SCENE LIFECYCLE — GENTLE:
This scene has been active for {N} exchanges without new information, 
objective progress, or NPC-state change. If the current situation 
has run its course, compress naturally — wrap the NPC exchange in one 
sentence, narrate the party preparing to move on, and invite the next 
player action from a fresh vantage point. If tension remains unresolved, 
escalate rather than compress. Do not force closure — but lean toward it.
```

### Strong directive text (tier 2, at `_STALE_HARD_THRESHOLD` turns)

```
SCENE LIFECYCLE — COMPRESS NOW:
This scene has been active for {N} exchanges with no forward movement.
COMPRESS THIS SCENE: close any open beats in one sentence, summarize 
the remaining situation without extending it, and move the party 
toward the next meaningful event or location. You may narrate a brief 
transition ("as the conversation wraps up..." / "with that resolved..." 
/ "the moment passes...") but DO NOT open new NPC threads, introduce 
new obstacles, or extend the current location's narration. 
Retire the scene. Hand agency back to the players in a new context.
```

### Explicit trigger text (from `/compress` command)

```
SCENE LIFECYCLE — DM-INITIATED COMPRESS:
The DM has explicitly called for a scene transition{reason_clause}.
Compress this scene now. Wrap remaining beats in one sentence and 
move forward. Do not resist or extend.
```

Where `{reason_clause}` = `: "{reason}"` if reason provided, else empty string.

### Cliff-edge note (§77 analog for scene lifecycle)

The compression directive must NOT instruct the LLM to:
- Invent consequences of the compressed scene (what happened while compressing)
- Add new NPC reactions or obstacle introductions at the close
- Narrate forward into the next scene (the directive closes this scene; the next player turn opens the next)
- Decide what the player's characters did during the compression (player retains agency)

These are the scene lifecycle analog of §77's forbidden list. MUST-NOT clauses live in the directive text itself (instruction-side enforcement per §78's two-layer composition note).

---

## §5.5 The 86% quiet baseline as architectural reality

**Source:** Cross-extractor finding X2 — 86% of CC scene-exits are followed by 30+ turns of zero extractor signal. The pipeline isn't blind during those 30 turns; it's correctly silent.

**Operational consequence for v1:** The directive's threshold-fired evaluation IS the 86% quiet baseline in implementation form. Below soft threshold, `compute_scene_lifecycle_directive` returns `('', {})` — no prompt block, no LLM constraint, no architecture-side noise. The directive is structurally quiet most of the time by design.

**What v1 does NOT do after compression fires:** The directive does not author the next scene. After the LLM compresses and posts, the next turn proceeds via normal `dm_respond` path; the new scene rebuilds organically through player input + LLM response. This matches CC's X7 finding (see §5.6): events don't cluster at 15-turn scale, so designing for post-compression coordination is a design error against the corpus.

**This is load-bearing design intent, not a side effect.** State explicitly so future ships don't try to fill the 86% post-compression window. If v1.x adds a quest layer or composition layer, both must respect the same quiet baseline — neither layer interferes with the post-compression 30-turn window.

---

## §5.6 X7 single-source detection rule

**Source:** Cross-extractor finding X7 — no reliable cross-extractor agreement at 15-turn scale. CC, TM, LR, EC don't co-fire as coordinated signals; each fires on its own surface.

**Consequence for v1:** The stale counter is the single detection source for auto-fire. No cross-extractor join, no co-fire threshold, no "compress if EC reset AND TM stale AND LR pending." Counter fires on its own signal.

**Filed forward as the motion-system single-source detection rule:** Future ships (quest layer, composition layer, encounter cadence v1) operate on their own detection surfaces. v1's stale counter doesn't read their signals; their signals don't read v1's counter. Each ship's detection surface is independent until empirical evidence justifies coupling.

**Rules out a v1.x temptation:** Do not "improve" the counter by joining with `consequence_promoted` rate or `npc_register_avrae_madd` rate. Per X7, those joins won't produce reliable signal at the 15-turn scale. Stay single-source.

---

## §5.7 Climactic-hold suppression rule

**Source:** Cross-extractor findings X4 R1/R2 — climactic-hold pattern in CC corpus: 10.6% of episodes produce zero compressions, clustering with finales and high-tension content (C1E114 finale, C1E076, C1E108). Predicate: BLOODIED + DOWNED beats present, recent combat, hard-stakes signals → Matt resists compression rather than honoring it.

**Architectural shape:** Suppression at fire-time, not state. The counter accumulates normally. At directive-fire time (soft or strong threshold reached), the engine checks for a climactic-hold signal. If the predicate matches: `compute_scene_lifecycle_directive` returns empty body regardless of counter value. Telemetry: `scene_lifecycle: ... fired=0 reason=climactic_hold_suppressed predicate={...}`.

This is structurally clean — the counter keeps accumulating; suppression is a fire-time check; if the climactic content resolves and the predicate clears, the directive fires on the next turn normally. Matches the CC pattern: Matt doesn't reset his stale-tracker during finales, he just doesn't act on it.

**Candidate predicate signals (exact set is §11.L, operator's call):**
- `_combat_beats > 0` in last N turns (BLOODIED + DOWNED dispatches)
- Recent combat exit (within M turns of `!init end`)
- Active commitment_directive firing (unresolved commitment signal in current turn)

**What this is NOT:** a state-machine branch. The suppression rule doesn't change mode or write any field. It's a predicate checked at invocation time inside `compute_scene_lifecycle_directive`. Counter-side suppression is the architectural shape; the exact signal set is §11.L.

---

## §6. Recon findings

Six items, each with evidence.

---

### R1. Slash-command surface: no `/scene` or `/compress` collision; autocomplete pattern available

**Evidence (v0.1 re-confirmed, May 13 2026):** `grep -n "@bot.tree.command" discord_dnd_bot.py` — 20 `@bot.tree.command` registrations + 3 `app_commands.Group` registrations (clock, quest, companion). Confirmed registered commands: `/refresh`, `/setup`, `/newcampaign`, `/campaigns`, `/archived`, `/setcampaign`, `/deletecampaign`, `/purgecampaign`, `/purgeallcampaigns`, `/bindchar`, `/play`, `/nudge`, `/travel`, `/advance`, `/mode`, `/encounter`, `/inventory`, `/giveitem`, `/hydrate`, `/dmhelp`. Groups: `clock`, `quest`, `companion`. No `/scene` command. No `/compress` command. No `scene` or `compress` subgroup.

**Autocomplete availability:** Five autocomplete helpers confirmed: `_bindchar_autocomplete`, `clock_name_autocomplete`, `quest_id_autocomplete`, `companion_id_autocomplete`, `companion_name_autocomplete`. Pattern: `async def _X_autocomplete(interaction, current) → list[app_commands.Choice]`. Wired via `@app_commands.autocomplete(field=helper)`. Pattern fully established for v1's `/compress` if `reason` autocomplete is needed. v1 doesn't require it; filed for v1.x polish.

**Finding:** `/compress` is available and uncontested. No collision risk. Prior R1 finding confirmed with corrected command count.

---

### R2. `reset_narrative_buffers_on_combat_exit` — buffer-drift audit for post-compression flow

**Evidence (function shape):** `dnd_engine.py:1466–1506`. Function writes three buffer fields via `update_scene()`, `update_last_dm_response()`, `update_scene_state(last_player_action=...)`. Hard-coded closeout constants. Called once from `discord_dnd_bot.py:1409` in `_handle_init_event` evt_type='end'. Docstring anticipates generalization to other mode transitions.

**Buffer-drift audit (v0.1 §9 deliverable):** Does post-compression scene narration produce buffer drift without an explicit reset?

Tracing the normal write path:
- `update_last_dm_response` — defined at `dnd_engine.py:1379`; called at `dnd_engine.py:6677` inside `dm_respond`, after auto_execute cleanup, before turn counter increment. Comment: "Written AFTER auto_execute cleanup because that's the form the player actually sees." Fires on **every successful narration turn**, including turns where a scene lifecycle directive was injected.
- `update_scene` — called at `discord_dnd_bot.py:2995` inside `_dm_respond_and_post` on every narration post: `update_scene(campaign['id'], f"Last actions: {combined_action[:200]} | DM: {response[:200]}")`.

**Finding: NO buffer drift.** After a scene lifecycle directive fires and the LLM produces compression narration, both `update_last_dm_response` (at `dnd_engine.py:6677`) and `update_scene` (at `discord_dnd_bot.py:2995`) write on the same turn. The buffers are updated with the compression narration before the next turn reads them. No gap, no stale content persisting into the post-compression scene. The LLM's next turn reads a buffer reflecting the compressed scene, which is correct.

**§1.G stands confirmed.** v1 does NOT need to generalize `reset_narrative_buffers_on_combat_exit`. Scene compression is not a mode transition; the buffers self-update via normal narration flow. v0.1 §9's "audit that buffers don't drift-pollute the post-compression scene" is cleared: no explicit reset structurally needed.

**Generalization surface for future ships:** If v1.x ships `REST_END_FROM_COMBAT` or `social→exploration` boundary, THAT ship would generalize this function. Shape if generalizing: `reset_narrative_buffers(campaign_id, scope: str, closeout_scene: str, closeout_dm: str, closeout_player: str)`. §17 amendment required at that time per S27 precedent framing. v1 does not touch it.

---

### R3. §17 amendment-pressure audit — surfaces touched by v1

**Evidence:** Architectural review of each field Scene Lifecycle v1 might write.

| Field | Current single writer | v1 touch? | §17 pressure? |
|---|---|---|---|
| `campaigns.current_scene` | `update_scene()` — called broadly (not single-writer restricted) | Indirectly via `_dm_respond_and_post` narration | None — field already has broad writer |
| `dnd_scene_state.last_dm_response` | `update_last_dm_response()` — broadly called | Indirectly via `_dm_respond_and_post` | None |
| `dnd_scene_state.last_player_action` | `update_scene_state()` — broadly called | No direct touch | None |
| `dnd_scene_state.mode` | `set_scene_mode()` — SINGLE WRITER | v1 does NOT write mode | None (§1.D decision) |
| `dnd_scene_state.turn_counter` | `increment_turn_counter()` — SINGLE WRITER | Read-only (used for threshold reference) | None (no write) |
| `dnd_npcs.*` | Multiple single writers per column | No NPC writes in v1 | None |
| `dnd_time_advancements` | `advance_time()` — SINGLE WRITER | Read-only (activity signal, not a write) | None |
| `_scene_stale_turns` (in-memory) | New — owned by `discord_dnd_bot.py` | New in-memory state | §17 applies to module-level in-memory dicts? Pattern from `_combat_beats` says: single increment site + single reset site + single clear site. v1 follows same discipline. |

**Finding: Zero §17 amendment pressure.** v1 introduces no new persisted fields. The one new state surface (`_scene_stale_turns` in-memory dict) follows the `_combat_beats` precedent and the §17 spirit (one increment site, one reset site, one clear site). No VIRGIL_MASTER §4 authority invariant is touched.

**New per-campaign table risk:** If v1 introduces a `dnd_scene_compressions` audit table, it must be added to `_CAMPAIGN_SCOPED_TABLES` in the same patch. §1.J decision defers this table to v1.x.

---

### R4. Baseline prompt-size — updated exploration-turn distribution (floor for v0.1 §9)

**Evidence:** `journalctl --user -u virgil-discord` prompt_size: entries, May 12, 2026 (10 exploration turns, party=0, campaign=17). This is the floor v0.1 §9 names for downstream ships (quest layer, composition layer) to measure deltas against.

| Component | Range | Mean (est.) |
|---|---|---|
| system | 19,446–23,301 | ~22,000 |
| retrieval | 600–2,064 | ~1,300 |
| party | 0 (solo) | 0 |
| scene | 29–63 | ~45 |
| directives | 5,538–6,153 | ~5,900 |
| **total** | **24,933–27,775** | **~26,300** |

**Update from prior spec:** Directives component has grown from prior estimate of ~4,600 to current ~5,900 (additional directive ships post-S45). Total mean updated from ~25,000 to ~26,300.

**Scene Lifecycle delta estimate (updated):**
- Soft-nudge text: ~160 chars
- Strong directive text: ~300 chars
- At mean: directives 5,900 + 300 = 6,200 (+5.1%); total 26,300 + 300 = 26,600 (+1.1%)
- At observed max (6,153 + 300 = 6,453): total pushes to ~28,100 — above the observed May 12 max of 27,775 but within prior max range (27,446)

**Finding:** Budget-safe at selective firing. The +1.1% total delta at hard threshold is within the normal turn-to-turn variance (~±1,400 chars across May 12 sample). v0.1 §9 establishes this baseline: quest layer and composition layer measure their prompt-size deltas against this floor.

**Calibration instrument:** `scene_lifecycle:` always-fire log line surfaces per-turn baseline; `directive_emit:` extended with `scene_lifecycle={none|soft|strong}` to aggregate with existing directive telemetry.

---

### R5. CC taxonomy coverage — v1 coverage without T2

**Evidence (v0.1 re-confirmed, T2 deferred):** `track5_findings_compression_cadence.md` §4 category breakdown (365 records, 123 episodes). Prior R5 showed T2 assisting LOCATION_DEPARTURE; updated for T2 deferral per §11.N.

| CC Category | Corpus % | Precision | v1 Coverage | Notes |
|---|---:|---:|---|---|
| OVERNIGHT_REST | 39.2% | 48.6% | **Out of scope** | Already handled by `!game lr`/`!game sr` → `advance_time()`. Do not duplicate. |
| TEMPORAL_MONTAGE | 26.0% | 76.9% | **v1 T1 covers** | Turn-count stale signal catches the "no forward movement" pattern |
| LOCATION_DEPARTURE | 18.9% | 54.5% | **Partially `/travel`; T1 delayed assist** | `/travel` handles explicit departures. T2 (player closure intent) deferred to v1.x. T1 covers the same events at a delay (N stale turns later); UX gap, not coverage gap. |
| NPC_DEPARTURE | 9.3% | 50% | **v1.x T3** | Requires NPC-purpose-resolution detection; deferred |
| INVESTIGATIVE_CLOSURE | 3.6% | 66.7% | **Partially T1** | Stale turn count catches "investigation exhausted" at the symptom level |
| SCENE_CUT | 2.7% | 100% | **v1 `/compress`** | Explicit DM-initiated cut |
| STALE_HOLD_CANDIDATE | 0.3% | 0% (partial) | **Implicit + §5.7 suppression** | Climactic-hold suppression rule (§5.7) addresses this directly: directive suppressed when predicate signals high-tension content |

**Finding (updated for T2 deferral):** v1 directly addresses TEMPORAL_MONTAGE (26.0%) + SCENE_CUT (2.7%) + partial INVESTIGATIVE_CLOSURE (3.6%) + partial LOCATION_DEPARTURE via T1 delay (18.9% covered at delay, not immediately). Coverage ~51% of CC corpus by volume — unchanged from prior spec. T2 deferral does not reduce coverage; it introduces a UX gap (player-initiated immediate scene close becomes delayed by N stale turns). Per CC Q3 finding (DM-initiated `matt_initiated` compressions dominant), T2's absence does not remove a primary coverage surface.

OVERNIGHT_REST (39.2%) is deliberately out of scope. Stale counter reset on `advance_time()` call (§1.F activity signal) structurally handles this — rest events reset the counter to 0.

**Calibration expectation:** CC corpus baseline at 2.97 compressions per episode (mean; 10.6% episodes produce zero). The 10.6% zero-compression episodes cluster with high-tension finales — §5.7 climactic-hold suppression addresses this structurally rather than relying on the escape clause in directive text.

---

### R6. S45 COMBAT_END dispatch pattern — structural precedent for Scene Lifecycle

**Evidence:** `discord_dnd_bot.py:1383–1474`, `_handle_init_event` evt_type='end' branch + `_dispatch_combat_narration`.

**Pattern extracted:**

1. **Pre-transition snapshot** — `pre_clear_combat_state = get_combatants(campaign['id'])` captured BEFORE cleanup. Decouples dispatch from post-cleanup DB state.
2. **Mechanical cleanup** — mode flip + clear_combatants + clear_active_turn.
3. **Buffer reset** — `reset_narrative_buffers_on_combat_exit`.
4. **In-memory substrate cleanup** — `buffer.clear(message.guild.id)`.
5. **Content-conditional dispatch** — beat counter gates LLM vs deterministic closeout (§78.6).
6. **Override params** — `combat_state_override=pre_clear_combat_state`, `scene_override={'mode': 'combat'}` let dispatch use pre-cleanup snapshot through post-cleanup DB state.
7. **Counter cleanup** — beat counter cleared after dispatch.
8. **Soft-fail throughout** — try/except wraps each phase; no phase blocks mechanical state.

**What Scene Lifecycle v1 inherits from this precedent:**

- **Snapshot before state change** — `/compress` command should snapshot current scene state before writing anything (even though v1 doesn't change mode, the pattern is good discipline)
- **Content-conditional dispatch** — tiered directive (§1.J) follows §78.6 content-conditional framing: below soft threshold = no directive; at soft = soft; at hard = strong; explicit = strong (regardless of counter)
- **Counter cleanup on dispatch** — stale counter resets to 0 after explicit compression (§1.H)
- **Soft-fail** — `compute_scene_lifecycle_directive` call site always try/except; never blocks narration

**Ordering precedent for auto-dispatch vs call-site:**
- COMBAT_END is dispatched from `_handle_init_event` (event listener), not from `build_dm_context`
- Scene Lifecycle auto-fire is different: it fires WITHIN `build_dm_context` (during a player turn's narration computation), not from an Avrae event
- This is the correct difference — combat narration responds to external mechanical events (Avrae init signals); scene lifecycle responds to accumulated turn state. Different triggers, appropriate different call sites.

---

### R7. §78.5 text re-read — fourth-instance interpretation (NEW recon item)

**Evidence:** DOCTRINE.md §78.5, full text re-read.

**The question (from v0.1 §4):** Does §78.5's "substrate-and-boundary-agnostic" language extend to non-Avrae-triggered surfaces, or does it stay anchored to Avrae-event-coupled boundaries? v0.1 §4 takes Read A (pattern-reuse, not fourth instance). Does §78.5's text support Read A?

**Load-bearing quote from §78.5:**

> "§78's four-layer rule applies **across substrates** (DB-side state, in-memory state, and any other persistence layer holding state that drove the prior mode) **and across boundaries** (`!init end`, `!lr`/`!sr` rest events, and **any other mode-transition surface**)."

**And from §78 parent:**

> "Mode transitions are **state-reset surfaces**."

**Analysis:** §78.5's "any other mode-transition surface" clause is broad, but the scope is bounded by the parent §78 framing: the rule governs **mode-transition surfaces**. Scene Lifecycle v1 does NOT flip `dnd_scene_state.mode`. It fires on internal accumulation state (stale counter); the directive instructs the LLM to narrate a transition, but no mode-flag write occurs at the engine level (§1.D). v1 is therefore not a mode-transition surface; §78 and §78.5 do not govern it by their own scope definition.

The three anchored instances (S45, S48, S49) all involve Avrae-event-coupled mode-flip boundaries (`!init end`, `!lr/!sr`). §78.5's "and any other mode-transition surface" extends to non-Avrae external mode-flip events (future `/travel`, downtime→exploration), but still requires an actual mode-flip — not merely a stale-counter-triggered directive injection.

**Finding: §78.5 text SUPPORTS Read A.** The load-bearing text is §78's parent scope clause: "mode transitions are state-reset surfaces" — v1 is not a mode transition. §78.5 is about WHERE the four-layer rule applies across substrates and boundaries; it does not extend the "mode transition" definition to include non-mode-flip internal accumulation surfaces. v0.1 §4's framing is doctrinely grounded.

**§78.5 promotion-check status:** Stays open for a future non-Avrae external mode-flip event. v1 does not close it.

**Doctrinal call status:** SURFACED, not locked. Planner presents the text; Session 2 walks with operator + Oracle per session brief discipline.

---

## §7. §76 four-property audit — new fields introduced by v1

| Field | LLM-writable? | Persisted? | Retrieved into prompt? | Narratively inferential? | Result |
|---|---|---|---|---|---|
| `_scene_stale_turns` (in-memory dict) | No — deterministic writer | No — in-memory only | No | No | CLEAR (all 4 properties fail — safe) |
| Any new `dnd_scene_state` column (if §11.D or §11.E require one) | Must use §17-gated writer | Yes | Yes (scene_state block) | Depends on field semantics | Audit at column-add time per §76 operational discipline |

**Finding:** v1 as specced (§1.B in-memory counter) introduces zero §76-risk fields. The §76+§17 composition observation (S41) applies: if v1 later needs a persisted field, the write path design time is the §76 audit time.

---

## §8. Test plan sketch

Full test plan lands in Session 3 with implementation. Outline for Session 2 review:

**Unit tests (pure function):**
- `compute_scene_lifecycle_directive` returns empty body below soft threshold
- `compute_scene_lifecycle_directive` returns soft-nudge body at soft threshold
- `compute_scene_lifecycle_directive` returns strong body at hard threshold
- `compute_scene_lifecycle_directive` returns strong body on `trigger_kind='explicit'`
- `compute_scene_lifecycle_directive` returns empty body when `scene_state.mode='combat'`
- `compute_scene_lifecycle_directive` body contains MUST-NOT clauses (cliff-edge enforcement)
- Stale counter reset on activity-signal events (location change, Avrae roll consumed, NPC new upsert, advance_time, consequence upsert)
- Stale counter increment on plain player turns with no activity signal
- Stale counter does NOT exceed hard threshold (bounded at hard_threshold or sentinel)

**Integration tests:**
- `/compress` command returns correct narration (soft vs explicit)
- Mode gate: stale counter reaching threshold during mode='combat' does not fire directive
- Counter reset on `/compress` dispatch

**Regression:**
- Existing §59 sibling tests unchanged
- `build_dm_context` prompt assembly unaffected below threshold (directive block unchanged on empty return)

---

## §9. Live-verify scenarios

To be detailed in Session 3. Placeholder outline:

1. **Stale scene auto-compress:** Play a scene, type 7 turns of "I look around" / "I wait" / non-escalating player text. Confirm soft directive fires at turn 3, strong at turn 6. Check `scene_lifecycle:` log lines, confirm directive text appears in journal's prompt capture, confirm narration shows compression.
2. **Active scene does NOT compress:** Play a scene with a new NPC encounter. Avrae roll fires (activity signal). Stale counter resets. Confirm directive never fires in the 6 turns following the roll.
3. **Rest-event suppression:** `!game lr`. Stale counter resets via `advance_time` activity signal. Confirm no directive fires on the post-rest narration turn.
4. **`/compress` explicit:** Type `/compress reason:"moving on from the market"`. Confirm strong directive fires, narration transitions scene, stale counter resets.
5. **Player closure intent T2:** Type "we head out" or "let's go". Confirm strong directive fires and narration transitions.
6. **Combat mode gate:** During combat (`mode='combat'`), let stale counter accumulate (in-memory). Confirm directive never fires. On `!init end`, confirm counter resets (combat exit clears all state).

---

## §10. Telemetry

**Always-fire log line:** `scene_lifecycle: campaign={N} guild={N} mode={mode} stale_turns={N} tier={none|soft|strong} fired={0|1} trigger_kind={auto|explicit|player_intent}`

Per §59 sibling contract: emits every turn the directive was called, whether or not it fired. Calibration instrument for threshold tuning.

**Extend `directive_emit:` log line:** add `scene_lifecycle={none|soft|strong}` field. Aggregates with existing directive telemetry.

**Counter activity log:** `scene_lifecycle_reset: campaign={N} guild={N} signal={location_change|avrae_roll|npc_new|advance_time|consequence|explicit_compress|player_intent}` — emitted each time the stale counter resets, with the reason. Calibrates which activity signals actually fire in practice (some may be rarer than expected).

---

## §11. Decision points — operator's call required before Session 3

These 11 decisions require Jordan's input. Session 2 review walks each with trade-offs. Format per project precedent: options + recommendation + confidence.

---

### §11.A — Trigger mode scope: exploration-only vs multi-mode

**Question:** Should the stale-scene directive fire in social and travel modes, or exploration only?

**Options:**
- **(a) Exploration only** — simplest; social and travel handled separately if friction surfaces
- **(b) Exploration + social** — stale NPC conversations are a real F-54 symptom; social is adjacent to exploration
- **(c) All non-combat modes** — broadest; includes travel and downtime

**Recommendation: (b).** Social mode is where NPC linger is most acute (F-52 downstream symptom). Travel is already time-compressed by `/travel`; a stale signal during travel would be noise. Downtime is a mode that doesn't exist yet. Easy to expand to (c) via constants change post-playtest.

**Confidence: MEDIUM.** Social mode coverage has not been empirically validated; could start at (a) and expand to (b) if social-mode stagnation surfaces in logs.

---

### §11.B — Explicit rest-event suppression or natural counter reset?

**Question:** When `!game lr` / `!game sr` fires, should the stale counter be explicitly reset, or does the `advance_time` activity signal (§1.F) handle it naturally?

**Options:**
- **(a) Explicit reset** — a dedicated reset call in `_handle_rest_event` alongside RollBuffer drain (§49 precedent)
- **(b) Natural reset** — `advance_time()` call counts as an activity signal; counter resets automatically

**Recommendation: (b).** If §1.F correctly identifies `advance_time` as an activity signal, rest events reset the counter via the same path as `/travel`. No special-casing needed. Explicit reset (a) is defensive redundancy — file as v1.x if (b) produces false-fires post-rest in playtest.

**Confidence: HIGH.** The activity signal design (§1.F) directly anticipates this case.

---

### §11.C — Trigger taxonomy v1 scope: narrow vs medium

**Question:** Ship T1 (turn count) only, or T1 + T2 (player closure intent)?

**Options:**
- **(a) T1 only** — simplest; stale counter is the entire detection surface
- **(b) T1 + T2** — adds player closure intent detection; covers SCENE_CUT + LOCATION_DEPARTURE assist cases

**Recommendation: (b).** T2 is thin — a phrase-vocabulary check on player text, identical in architecture to the commitment directive's retraction-grammar filter (S19 precedent). The CC Q3 finding shows player-prompted compressions are the minority (~15-20% of records); but the DM `/compress` command covers the Matt-initiated case explicitly. T2 adds the player-side surface without new architecture.

**Confidence: MEDIUM.** T2 phrase vocabulary needs assembly (Session 3 task). If phrase vocabulary is under-coverage, false-positive player-intent detection could trigger premature compression.

---

### §11.D — Threshold values: locked in spec vs named constants in code

**Question:** Should v1 lock `_STALE_SOFT_THRESHOLD` and `_STALE_HARD_THRESHOLD` values in this spec, or leave them as tunable constants?

**Options:**
- **(a) Locked in spec** — spec names 3 and 6; amendment required to change
- **(b) Named constants in code** — spec names the constants; values set in `dnd_orchestration.py`, tunable via next Code session without spec amendment

**Recommendation: (b).** The whole architecture is evolve-from-observed-friction. The 3/6 starting values are calibration guesses. CC baseline (2.97 compressions per episode) does not constrain the threshold directly — it's a corpus measure, not a Virgil-calibration target. Constants let the operator tune from telemetry without reopening the spec.

**Confidence: HIGH.** (b) is the standard project pattern for calibration parameters.

---

### §11.E — Activity signal: include or exclude bare player text

**Question:** Should any non-empty player turn count as an activity signal (reset counter), or only the specific mechanical signals from §1.F?

**Options:**
- **(a) §1.F events only** — counter only resets on location change, Avrae roll, NPC new, advance_time, consequence, explicit compress
- **(b) §1.F events + new NPC dialogue** — reset if the turn produces a new NPC response (NPC mentions a new name or fact)
- **(c) Any non-empty DM narration** — reset if DM posted a non-empty narration this turn

**Recommendation: (a).** Broad resets defeat stale detection. (c) would mean the counter never reaches threshold as long as the DM is narrating — but the DM is narrating every turn. (b) requires cross-session NPC-dialogue-novelty detection which is out of v1 scope.

**Confidence: HIGH.** (a) is the strictest defensible signal set.

---

### §11.F — `/compress` DM-only or player-accessible

**Question:** Should `/compress` be gated to DM (Jordan) only, or usable by any player?

**Options:**
- **(a) DM-only** — same gating as `/play`, `/advance`, `/mode`
- **(b) Player-accessible** — any player can request scene compression

**Recommendation: (a).** Scene compression is a DM narrative authority decision. Players can signal closure intent through normal in-character speech (T2 trigger handles this). A player-accessible `/compress` would let players force scene transitions the DM didn't intend. CC Q3 finding: Matt-initiated compression is dominant — DM authority over compression cadence is the CRD3 empirical norm.

**Confidence: HIGH.**

---

### §11.G — Stale counter in-memory bounds and overflow behavior

**Question:** What is the maximum stale counter value? Does it cap at `_STALE_HARD_THRESHOLD` or continue accumulating?

**Options:**
- **(a) Cap at hard threshold** — counter never exceeds `_STALE_HARD_THRESHOLD`; repeated strong directives fire on every subsequent turn until reset
- **(b) Accumulate indefinitely** — counter keeps climbing; strong directive fires on every turn once past hard threshold (same behavior as cap, but the counter value itself is preserved for telemetry)
- **(c) Cap with backoff** — strong directive fires at hard threshold, then is suppressed for N turns to avoid repeated firing, then re-fires

**Recommendation: (b).** Accumulate for telemetry; behavioral effect is same as (a) (strong directive fires every turn above hard threshold). (c) adds complexity for uncertain gain — if the DM LLM isn't compressing even under strong directive, that's a signal worth measuring (how long does the scene persist past hard threshold?), not suppressing.

**Confidence: MEDIUM.** If playtest shows the strong directive fires repeatedly and annoys more than it helps, (c) backoff is the fix.

---

### §11.H — Cliff-edge enforcement: instruction-side only or both layers?

**Question:** Should the scene lifecycle directive use instruction-side enforcement only (MUST/MUST-NOT clauses in the directive text), or also information-side suppression (blocking specific context blocks during compression turns)?

**Options:**
- **(a) Instruction-side only** — MUST/MUST-NOT in directive text; no context-block suppression
- **(b) Both layers** — instruction-side + information-side suppression (suppress recent_npcs, chroma retrieval, or other drift-source blocks during compression turns)

**Recommendation: (a) for v1.** The §77 two-layer enforcement was needed because ROUND_START combat narration had weak event anchoring and fell back to available context, generating drift. Scene compression has a stronger anchor (the stale counter reaching threshold is a structural signal); the COMPRESS NOW directive provides clear task framing. Information-side suppression would be appropriate if v1 shows the LLM generating new story content instead of compressing — that's a playtest observation, not a v1 spec commitment.

**Confidence: MEDIUM.** The two-layer pattern (§78) is now established as the default for mode-transition surfaces. Scene compression is not a mode transition, but if it exhibits the same drift pattern, (b) is the ready response.

---

### §11.I — Combat mode gate: counter freeze or counter reset

**Question:** When `mode='combat'`, does the stale counter freeze (hold its current value) or reset to 0?

**Options:**
- **(a) Freeze during combat** — counter holds its value; when combat ends, resumes from pre-combat stale value. Risk: if the party had a 5-turn stale scene before combat, they emerge from a 2-round combat at stale=5 and immediately get a strong directive.
- **(b) Reset on combat start** — `!init begin` resets counter to 0. Combat is not a stale scene; post-combat exploration starts fresh.
- **(c) Reset on combat end** — counter resets when `!init end` fires; post-combat exploration starts fresh regardless of pre-combat value.

**Recommendation: (b).** Combat entry is an activity signal by definition (mode flip from exploration to combat IS a new event). The counter resets at `!init begin` via the activity signal path. Post-combat exploration starts at 0, which is semantically correct — the COMBAT_END narration just happened; the post-combat moment is not stale. (c) produces the same result but requires an explicit reset hook in `_handle_init_event`, which the activity signal at (b) avoids.

**Confidence: HIGH.** Activity signal at mode='combat' trigger is clean; matches the philosophy that combat is not stagnation.

---

### §11.J — `/compress` command: reset stale counter or not?

**Question:** Should `/compress` reset the stale counter to 0 after dispatch, or leave it at its current value (so the auto-timer continues from where it was)?

**Options:**
- **(a) Reset to 0** — explicit compression is a successful scene transition; start fresh
- **(b) Leave counter at current value** — explicit compression might not have been effective; let auto-timer continue if scene is still stale

**Recommendation: (a).** Explicit compression is a DM intent signal. The DM typed `/compress` because they want to move the scene forward. Resetting to 0 trusts that the explicit compression landed. If the scene is still stale after explicit compression, the counter will rebuild naturally and the directive will fire again. (b) would immediately re-fire the strong directive on the first post-compress turn (if counter is at or above hard threshold), which would conflict with the just-posted narration.

**Confidence: HIGH.**

---

### §11.K — Stale counter visibility: scene_state block or invisible?

**Question:** Should the stale turn count appear anywhere in the DM prompt (scene_state block, scene footer, etc.), or remain invisible to the LLM?

**Options:**
- **(a) Invisible** — LLM never sees the counter; only sees the directive text when it fires
- **(b) Scene footer** — `scene_lifecycle: {N} turns at current scene` in the state footer (like `day_phase`, `mode`)
- **(c) Scene_state block** — a `stale_turns: N` field appears in the scene_state context block

**Recommendation: (a).** The counter is an internal calibration primitive, not a world-state fact. Exposing it to the LLM risks narrative inference (the LLM might narrate "the scene has been going on for 6 turns" — which is meta-textual and breaks immersion). The directive text is the LLM's signal; the counter is the trigger mechanism. §76 audit: if the counter appeared in the prompt (retrieved=Yes) and the field was narratively inferential (a number the LLM might interpret), it would approach a §76 risk surface. Keep it invisible; only the directive text appears.

**Confidence: HIGH.**

---

### §11.L — Climactic-hold predicate definition

**Question (new, per v0.1 §7):** What is the exact signal set for the climactic-hold suppression rule (§5.7)? The architectural shape is locked (fire-time predicate check; counter accumulates; suppression returns empty body + `reason=climactic_hold_suppressed`). The predicate signal set is operator's call.

**Candidate signal sets:**

- **(a) Minimal** — `_combat_beats > 0` in last N turns (BLOODIED + DOWNED beats during recent combat session) + active commitment_directive firing on current turn. Smaller set, fewer false-positive suppressions. v1.x extends if log evidence shows compressions fired during high-tension turns despite suppression.
- **(b) Extended** — (a) plus: DOWNED beats specifically in last M turns + recent combat exit (within K turns of `!init end`) tracked via a short-window in-memory counter. Closer match to CC X4 R1/R2 signal (BLOODIED + DOWNED + finale context).
- **(c) Minimal + explicit DM override** — (a) set, plus a `/force-compress` override that bypasses suppression. DM can always override climactic-hold suppression explicitly when they judge the hold wrong.

**Recommendation: (a) at v1.** Smaller signal set, fewer false-positive suppressions. v1.x extends if log evidence shows compressions fired during high-tension turns despite suppression.

**Confidence: MEDIUM.** The CC X4 R1/R2 findings ground (b) empirically, but (b)'s "recent DOWNED + recent combat exit" requires a separate in-memory tracker (turns-since-last-DOWNED, turns-since-last-COMBAT_END). (a) reuses existing `_combat_beats` tracking with no new state surface. Start minimal; extend if needed.

**OPEN — operator's call. No pre-lock.**

---

### §11.M — §1a auto-fire scrutiny

**Question (new, per v0.1 §8):** Scene Lifecycle v1's auto-fire directive instructs the LLM to *end a scene*. The directive doesn't write structural change itself (§1.D: no mode write, no buffer reset, no scene_state mutation), but its purpose is to cause the LLM's narration to do so. Is this comfortable under §1a ("LLM never decides mechanical outcomes")?

**Two valid reads:**

- **(a) §1a holds — compression is atmospheric guidance.** Scene compression is a narrative move, not a mechanical outcome. §1a's "mechanical outcomes" refers to adjudicator-bound events (CHECK_ACTION pass/fail, HP reduction, resource expenditure). Scene compression produces no such outcome — it's the LLM moving the story forward, which is exactly its job as DM. The directive is a nudge/constraint, not a binding decision. Defensible under §1a same as commitment directive (which constrains action latitude) and pacing directive (which constrains tone intensity).
- **(b) §1a is uncomfortable here — the directive is a state-change request.** Scene compression is structurally heavier than pacing/commitment. It instructs the LLM to conclude a scene segment — a move with narrative permanence. If the LLM "closes" the wrong scene at the wrong time, there's no ROLL_OUTCOME_DRIFT verifier to catch it. The auto-fire mechanism elevates this to "the engine is ordering the LLM to make a structural narrative decision every few turns."

**No lean.** Code's §1.A framed compression as "atmospheric guidance" consistent with (a). v0.1 §8 explicitly flagged this as operator + Oracle territory and declined to pre-lock. The spec session must walk this — not inherit by pattern from §59 sibling precedent alone.

**Implication for Session 3:** If operator + Oracle answer (a), implementation proceeds as specced. If (b), the directive framing needs adjustment (e.g., soft-nudge only with strong-tier requiring explicit `/compress` always; or a structured bounded surface where the LLM picks from named compression options per §1b validated-suggester pattern).

**OPEN — operator + Oracle call. No pre-lock.**

---

### §11.N — T2 deferral confirmation

**Question (new, per v0.1 §11.C refinement):** Prior Phase 1 spec recommended shipping T2 (player closure intent detection) in v1. v0.1 §8 leans defer to v1.x. Confirm deferral?

**Deferral case (v0.1 lean):** T2 introduces phrase-vocabulary detection on player text — a new detection surface with false-positive risk. CC Q3 finding shows DM-initiated compressions (`matt_initiated`) as dominant; player-side closure-intent is a minority fraction. T2 phrase vocabulary needs corpus grounding (which phrases reliably indicate scene-close intent in the CRD3 player corpus) before shipping. v1.x once T1 logs show whether player-side missed compressions surface as friction.

**Ship case (prior Code recommendation):** T2 is thin — phrase-vocabulary check identical in architecture to commitment directive's retraction-grammar filter (S19 precedent). CC SCENE_CUT (2.7%) + partial LOCATION_DEPARTURE assist (18.9%) are real coverage surfaces. Adding T2 adds the player-side surface without new architecture.

**v0.1 lean: defer.** CC finding "player-side closure intent" doesn't have a precision-measured sub-category in the CC findings doc. LOCATION_DEPARTURE at 54.5% precision is the best CC coverage, and `/travel` already handles explicit departures. T2 adds a false-positive risk without a strong corpus-grounded precision estimate. Defer to v1.x; T1 + `/compress` cover the primary surfaces first.

**OPEN — operator's confirmation of deferral.**

---

## §12. Open questions filed forward — out of v1 scope

These surface during recon or are implied by v1 decisions but are not v1 work.

**§12.1 — T3 NPC purpose resolution detection.**
Requires a new `dnd_npcs.purpose_status` or equivalent field, a NPC-purpose-resolution detection ship (advisory parser or DM command), and an NPC_DEPARTURE trigger surface. v1.x if playtest shows NPC linger as a named friction source.

**§12.2 — `reset_narrative_buffers` generalization.**
If a future ship (`REST_END_FROM_COMBAT`, `social→exploration` transition, `downtime→exploration`) requires a second scope for buffer resets, generalize `reset_narrative_buffers_on_combat_exit` per the documented shape (§R2 recon). That ship owns the §17 amendment. Not v1's job.

**§12.3 — `/compress` audit log table.**
A `dnd_scene_compressions` table recording when, why, and what was compressed would enable playback and analysis. v1.x if DM or playtest analysis reveals tracking need. If introduced, must be added to `_CAMPAIGN_SCOPED_TABLES` in the same patch.

**§12.4 — §78 four-layer audit for scene-lifecycle→mode-flip path.**
If v1.x ships a scene lifecycle trigger that changes `dnd_scene_state.mode` (e.g., compression triggers `set_scene_mode('travel')`), the §78 four-layer treatment is mandatory: mechanical cleanup + narrative buffer reset + transitional silence + boundary atmospheric closeout. The §78.6 content-conditional branch applies to the closeout. File as the scene-lifecycle→travel transition ship if playtest shows the pattern.

**§12.5 — Information-side suppression for compression turns.**
If v1 playtest shows the LLM generating new story content instead of compressing under strong directive, the §77 two-layer enforcement response is: suppress bleed-source blocks during compression-triggered narration turns. The block set would need identification via the same empirical audit S44 used (full prompt audit + direct DB inspection if drift continues past prompt audit). v1.x if the symptom surfaces.

**§12.6 — Motif decay coupling.**
F-52 (the lute problem) is downstream of scene immortality. Once Scene Lifecycle v1 is shipping and closing scenes, motif decay (decrement motif salience on scene close) could couple to the stale counter or scene close event. Filed when Scene Lifecycle v1 logs accumulate and the motif repeat pattern is empirically measurable.

**§12.7 — Cross-extractor Q4 scene-opening classification (CC-X1).**
Compression Cadence open question CC-X1: what kind of context opens the next scene after compression? The cross-extractor analysis spec (Phase 1, locked decisions pending) would answer this for CRD3 reference. For Virgil, once Scene Lifecycle v1 is running, the analogous question ("what opens the post-compression scene — player declaration, NPC arrival, environmental description?") is answerable from playtest logs.

**§12.8 — `_handle_init_list_event` third combat-exit surface.**
S49 discovered that an init-list edit clearing the last enemy could exit combat without firing `!init end`. If confirmed, this is a §78 substrate gap (combat-mode state persisting without `_handle_init_event` cleanup). Separate recon-first ship; not scene lifecycle territory.

**§12.9 — Social→exploration transition (§78 deferred candidate).**
S45 §78 filed social→exploration as a deferred §78 candidate. If Scene Lifecycle v1 ships and works well in social mode (§11.A option b), the social mode exit case (NPC conversation concludes, mode returns to exploration) may warrant a `REST_END_FROM_COMBAT`-style `SOCIAL_END` dispatch with buffer reset. Deferred per observed-friction discipline.

**§12.10 — LLM-extracted activity signals as perverse-incentive surfaces.**
S53 patch dropped §1.F.c (NPC was_new) after live verify showed scene-padded NPC introductions defeating stagnation detection. **S63 proactively dropped §1.F.e (consequence upsert DM-side) per identical-shape rule — doc-only patch since §1.F.e was specced but never wired in the S56 Quest Layer implementation. The harm was prevented by implementation gap; the patch makes that prevention explicit.** Two project instances now establish the structural rule:

**§1.F restriction to operator-driven and Avrae-driven signals only (location change, advance_time, Avrae roll) is now the anchored v1 rule.** LLM-extracted signals (NPC was_new, consequence upsert, future T2 player-closure-intent) are permanently excluded from §1.F. The architectural reasoning: LLM elaboration into a stale scene is the failure mode the directive is detecting; an extractor catching that elaboration cannot then score it as "world progression" without inverting the detection.

**F-64 candidate filed** (FAILURES.md): "LLM-extracted activity signals as perverse-incentive surfaces in stagnation-detection contexts." Anchored doctrine pending operator confirmation; failures.md entry filed as candidate. Two instances: §1.F.c S53 patch (NPC was_new wired then dropped), §1.F.e S63 patch (consequence upsert specced then never-wired then formally-dropped). Both LLM-extracted, both forgeable by elaboration, both correctly excluded.

**Corroborated-signal pattern remains a v1.x candidate** that would preserve "real new NPC introduces new activity" semantics by requiring co-occurrence with a non-LLM signal (location_change OR avrae_roll OR advance_time same-turn). `guild_id_int` param threading in `_extract_and_persist_world` is preserved for this future shape. Not v1 territory; ships only if log evidence shows legitimate world-progression NPC introductions are being missed by the current 3-signal set.

---

## §13. Out of scope — v1 explicitly does not

- Faction/reputation/relationship state changes (visible motion — v1.x after v1 log signal accumulates)
- Motif decay (F-52 downstream; couples to scene close once lifecycle is running)
- Autonomous NPC scheduling (NPCs initiating scene compression — that's active world-state generation, out of v1 scope)
- LLM-classified stale detection (§1a: classification that feeds binding decisions must be deterministic; stale counter IS deterministic)
- Combat-mode scene lifecycle (§77/§78 govern combat; scene lifecycle is exploration/social)
- Any modification to the `avrae_listener.py` parsing surface
- Any modification to the adjudication layer or narration verifier

---

## §14. Handoff

| Field | Value |
|---|---|
| **Spec status** | DRAFT — Phase 1 v0.1 reconciliation complete (May 13, 2026). Session 2 = review pass (Opus medium). |
| **Spec file** | `/home/jordaneal/virgil-docs/SCENE_LIFECYCLE_V1_SPEC.md` |
| **§11 count** | **14 decisions (§11.A–§11.N)** — 11 original + 3 new from v0.1 (§11.L climactic-hold predicate, §11.M §1a auto-fire scrutiny, §11.N T2 deferral confirmation). All require operator input. |
| **§12 count** | 9 open questions filed forward (§12.1–§12.9) |
| **§1 decisions** | 11 proposed decisions (§1.A–§1.K), all with recommendation + reasoning |
| **HALT escalations** | 0 — R2 buffer-drift audit confirms no drift (§1.G stands); R7 §78.5 text re-read confirms Read A (v0.1 §4 framing stands). No recon finding invalidates v0.1 architectural shape. |
| **v0.1 sketch** | Loaded and absorbed. Supersedes ROADMAP-only v0. Three areas reshaped: T2 deferred (§11.N), three new §11 decisions (§11.L–§11.N), three new architectural sections (§5.5–§5.7). |

**Recon findings summary (five items, v0.1 session):**
1. **Slash-command (R1 re-confirmed):** 20 `@bot.tree.command` + 3 `app_commands.Group` registrations. No `/compress` or `/scene` collision. Five autocomplete helpers available.
2. **Buffer-drift audit (R2 updated):** `update_last_dm_response` called at `dnd_engine.py:6677` on every successful narration turn. `update_scene` at `discord_dnd_bot.py:2995` same. Post-compression buffers self-update via normal narration flow; no drift window; no explicit reset needed. §1.G stands.
3. **CC coverage without T2 (R5 re-confirmed):** Coverage ~51% of CC corpus maintained. T2 deferral introduces UX gap (player-initiated immediate close → delayed by N stale turns) not coverage gap. DM-initiated compressions dominant per CC Q3; T2 absence doesn't remove primary coverage surface.
4. **Prompt-size baseline (R4 updated):** May 12, 2026, exploration turns: mean total ~26,300, directives mean ~5,900. Delta from prior spec: directives grew from ~4,600 to ~5,900 (additional directive ships post-S45). Strong directive adds ~300 chars (+1.1% total). Baseline established as the floor for downstream ships.
5. **§78.5 text re-read (R7 NEW):** Load-bearing quote: "§78's four-layer rule applies across substrates and across boundaries (`!init end`, `!lr`/`!sr` rest events, **and any other mode-transition surface**)." Parent §78: "Mode transitions are state-reset surfaces." v1 does not flip `dnd_scene_state.mode` — it is not a mode-transition surface. §78.5 text supports Read A (pattern-reuse, not fourth instance). §78.5 promotion check stays open for future non-Avrae external mode-flip event. Doctrinal call surfaced; Session 2 walks with operator + Oracle.

**Next session recommendation:** Session 2 = review pass. Opus medium per cadence table. Review doc walks each §11.A–§11.N (14 decisions) with trade-offs table, recommended defaults, confidence levels, and surfaced additions. Specifically must walk §11.M (§1a auto-fire scrutiny) with Oracle per v0.1 §8 framing — operator + Oracle, no pre-lock. Output: `SCENE_LIFECYCLE_V1_REVIEW.md`. Jordan reviews, locks. Spec flips DRAFT → LOCKED. Session 3 = implementation (Sonnet medium, templated against §59 sibling pattern).
