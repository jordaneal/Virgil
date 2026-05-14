# SCENE_LIFECYCLE_V1_REVIEW.md

**Status:** REVIEW — Phase 2 (Path A review pass). Walks all 14 §11 decisions with trade-offs + recommended defaults + confidence levels. Not a lock. Operator reads, locks decisions, spec flips DRAFT → LOCKED before Session 3.

**Session:** S52 Phase 2 review pass, May 13, 2026
**Spec reviewed:** `/home/jordaneal/virgil-docs/SCENE_LIFECYCLE_V1_SPEC.md` (DRAFT, v0.1 reconciliation complete)
**Basis:** v0.1 sketch (`planner-scratch/scene_lifecycle_v1_sketch_v0_1.md`), DOCTRINE §1a/§1b/§17/§59/§76/§77/§78/§78.5/§78.6, CC corpus findings, cross-extractor findings X2/X4/X7

**Format per decision:** question restatement → trade-offs table → recommended default + confidence → open axis (MEDIUM/LOW only).

---

## §1. Inventory note before walking

**§11.C and §11.N are in tension.** §11.C's spec recommendation is (b) "T1+T2 ship." §11.N was added by v0.1 reconciliation to re-open the T2 question. These two decision slots address the same axis from different angles — §11.N supersedes §11.C for the T2 question. **Operator must resolve §11.N; §11.C's recommendation then follows automatically.** If §11.N resolves as "defer T2," §11.C defaults to (a) T1-only. If §11.N resolves as "ship T2," §11.C defaults to (b). Do not lock §11.C independently of §11.N.

**§11.L gap noticed on walk.** The (a) minimal signal set includes "`_combat_beats > 0` in last N turns." But `_combat_beats` is CLEARED after `!init end` dispatch (S50 §78.6 pattern). Post-COMBAT_END, `_combat_beats[guild_id] = 0` always — the BLOODIED+DOWNED signal is unavailable in post-combat exploration, which is exactly the phase where climactic-hold suppression matters. The (a) predicate's practical effect is therefore: `active_commitment_directive → suppress`. The "recent BLOODIED or DOWNED beat" arm of (a) only fires DURING combat mode, which §11.A's mode gate already handles. The review walk surfaces this gap explicitly; see §3.L.

**No HALT triggered.** No decision walk surfaced a finding that invalidates v0.1's architectural shape. Inventory observation (§11.C/§11.N tension) is a spec-level clarification, not an architectural contradiction.

---

## §2. Summary table

| Decision | Question | Recommended | Confidence | Notes |
|---|---|---|---|---|
| §11.A | Mode scope | (b) exploration+social | MEDIUM | Social mode unvalidated; can expand post-playtest |
| §11.B | Rest-event suppression | (b) natural via advance_time | HIGH | |
| §11.C | T1 only vs T1+T2 | **Deferred to §11.N** | — | §11.N supersedes; see §3.C |
| §11.D | Threshold values | (b) named constants in code | HIGH | |
| §11.E | Activity signal scope | (a) §1.F signals only | HIGH | |
| §11.F | /compress access | (a) DM-only | HIGH | |
| §11.G | Counter overflow | (b) accumulate | MEDIUM | Backoff (c) is v1.x if over-fire observed |
| §11.H | Cliff-edge enforcement | (a) instruction-side only | MEDIUM | (b) two-layer is v1.x if drift surfaces |
| §11.I | Combat mode counter | (b) reset on combat start | HIGH | |
| §11.J | /compress counter reset | (a) reset to 0 | HIGH | |
| §11.K | Counter visibility | (a) invisible | HIGH | §76 supports strongly |
| §11.L | Climactic-hold predicate | (a) modified — commitment + combat-exit window | MEDIUM | (a) as written has gap; see §3.L |
| §11.M | §1a auto-fire scrutiny | **DECLINED TO LEAN** | — | Operator + Oracle required |
| §11.N | T2 deferral | Defer to v1.x | MEDIUM | Review recommends defer; operator confirms |

---

## §3. Full decision walk

---

### §3.A — Trigger mode scope: exploration-only vs multi-mode

**Question:** Should the stale-scene directive fire in exploration only, exploration+social, or all non-combat modes?

**Candidates:** (a) exploration only · (b) exploration+social · (c) all non-combat

| Candidate | Pros | Cons | Risk |
|---|---|---|---|
| (a) Exploration only | Simplest gate; zero false-positive in social; minimal surface area | Misses NPC linger in social scenes, which is a primary F-54 symptom | Leaves social-mode stagnation unaddressed until v1.x expansion |
| **(b) Exploration+social** | Covers NPC linger (F-52 downstream); social is adjacent to exploration in practice; easy gate (`mode in {'exploration', 'social'}`) | Social mode stagnation not corpus-validated (no CC record set for social-only scenes) | False-positive compression during meaningful social scenes (player NPC dialogue that isn't stale) |
| (c) All non-combat | Broadest coverage; future-proof for travel/downtime | Travel is time-compressed by `/travel` (noise); downtime mode doesn't exist | Fires during travel transitions where compression is already handled externally |

**Recommended default:** **(b) exploration+social.**

**Reasoning:** Social mode is where NPC linger accumulates most acutely — NPCs who have served their purpose but remain attached to the party's current location. CC corpus grounding is indirect but supportive: NPC_DEPARTURE (9.3%) is a recognized compression category, and social scenes are the context where NPCs establish, maintain, and over-stay their presence. Travel is gated by `/travel` which already handles its compression cadence; adding stale-counter pressure during travel would double-signal. Downtime mode doesn't exist yet.

**Confidence: MEDIUM.** Social mode coverage is not directly corpus-validated. The open axis: if v1 playtest shows false-positive compressions in social mode (meaningful NPC conversations getting compressed before their arc resolves), restrict to (a). Log signal that would justify (a): `scene_lifecycle: mode=social tier=strong fired=1` entries correlating with turns where the DM did NOT subsequently compress and /compress was not issued — false fires in social mode observable from journal.

---

### §3.B — Explicit rest-event suppression or natural counter reset

**Question:** When `!game lr` / `!game sr` fires, should the stale counter be explicitly reset or reset via the `advance_time` activity signal (§1.F)?

**Candidates:** (a) explicit reset in `_handle_rest_event` · (b) natural reset via advance_time signal

| Candidate | Pros | Cons | Risk |
|---|---|---|---|
| (a) Explicit reset | Defensive redundancy; guaranteed no false-fire post-rest regardless of §1.F wiring | Requires touching `_handle_rest_event`; adds new call site; duplicates what §1.F should handle | Adds complexity that §1.F makes unnecessary |
| **(b) Natural reset** | Clean; no new code path; self-documenting via §1.F signal taxonomy; consistent with how `/travel` resets | Requires §1.F to correctly detect `advance_time` call during rest events | If §1.F detection of advance_time call fails (e.g., if advance_time is called in a path the activity-signal hook doesn't cover), stale counter carries across a rest event |

**Recommended default:** **(b) natural reset.**

**Reasoning:** §1.F explicitly names `advance_time` as an activity signal. Rest events call `advance_time()` as part of their mechanical path. If §1.F is correctly wired (the activity-signal check fires in `on_message` after `advance_time` executes, or immediately on the rest-event path), the counter resets without explicit handling. This is the same path `/travel` uses — if `/travel` resets correctly via (b), rest events do too.

**Confidence: HIGH.** Implementation note for Session 3: verify that the `advance_time` signal detection fires on the rest-event path (not just player turns). If the activity-signal hook only runs in `on_message`, a rest event triggered from `_handle_rest_event` (Avrae event listener path) may not route through `on_message` and could miss the hook. This is a wiring detail, not a spec question; flag for Session 3 implementation.

---

### §3.C — T1 only vs T1+T2

**Question:** Ship T1 (turn count) only, or T1+T2 (player closure intent)?

**Note:** §11.N supersedes this decision for the T2 question. This slot's recommendation follows §11.N's resolution:
- If §11.N resolves as "defer": §11.C defaults to **(a) T1 only**
- If §11.N resolves as "ship T2": §11.C defaults to **(b) T1+T2**

**See §3.N for the full walk of the T2 decision.** Do not lock §11.C independently.

---

### §3.D — Threshold values: locked in spec vs named constants in code

**Question:** Should `_STALE_SOFT_THRESHOLD` and `_STALE_HARD_THRESHOLD` be locked in the spec (3 and 6) or remain as tunable constants in code?

**Candidates:** (a) locked in spec · (b) named constants in code

| Candidate | Pros | Cons | Risk |
|---|---|---|---|
| (a) Locked in spec | Explicit commitment; easier to reference in discussion; values are part of the behavioral spec | Spec amendment required to tune; adds process friction to calibration | Over-tightens the spec on numbers that are explicitly calibration guesses |
| **(b) Named constants in code** | Operator tunes from telemetry without reopening spec; consistent with every other calibration parameter in the system | Values not guaranteed to be doc-visible without reading code | No risk — this is standard project pattern |

**Recommended default:** **(b) named constants in code.**

**Reasoning:** The 3/6 starting values are explicitly calibration guesses; CC corpus baseline (2.97 compressions/episode) doesn't directly map to a Virgil threshold. Named constants in `dnd_orchestration.py` follow the project pattern established for every other tunable parameter (`_STALE_SOFT_THRESHOLD = 3`, `_STALE_HARD_THRESHOLD = 6` as initial values). Telemetry from `scene_lifecycle:` always-fire log line surfaces calibration signal without requiring a spec amendment to change the numbers.

**Confidence: HIGH.**

---

### §3.E — Activity signal scope

**Question:** Which events reset the stale counter? §1.F events only, or broader?

**Candidates:** (a) §1.F signals only (location change, Avrae roll, NPC new upsert, advance_time, consequence upsert, explicit compress) · (b) §1.F + new NPC dialogue detection · (c) any non-empty DM narration

| Candidate | Pros | Cons | Risk |
|---|---|---|---|
| **(a) §1.F signals only** | Strict detection; counter reaches threshold only on genuinely stale turns; no detection architecture needed beyond event hooks | May miss some scene-advancement signals (e.g., DM introduces a new plot element via narration without any of the §1.F events) | Counter might fire too early if some advancement signals are excluded |
| (b) §1.F + NPC dialogue detection | Catches narrative advancement that doesn't produce a mechanical event | Requires novelty-detection on NPC dialogue (cross-turn NPC-mention diff) — new detection architecture | High false-positive risk; "new NPC name mentioned" is unreliable as novelty signal |
| (c) Any DM narration | Simplest | Defeats stale detection — DM narrates every turn, counter never reaches threshold | Structurally self-defeating |

**Recommended default:** **(a) §1.F signals only.**

**Reasoning:** (c) is self-defeating. (b) requires detection architecture that (1) has no corpus grounding for precision, (2) adds a new complexity surface, and (3) conflates "new content" with "new signal" in ways that would need extensive calibration. (a) is the strictest defensible set — the §1.F events correspond to genuine world-state changes (location changed, mechanical roll consumed, new canonical NPC appeared, time advanced, consequence upserted, explicit compress dispatched). A scene where none of these fire IS stale by the operative definition.

**Confidence: HIGH.**

---

### §3.F — `/compress` access: DM-only vs player-accessible

**Question:** Should `/compress` be gated to DM (Jordan) only, or accessible to any player?

**Candidates:** (a) DM-only · (b) player-accessible

| Candidate | Pros | Cons | Risk |
|---|---|---|---|
| **(a) DM-only** | Preserves DM narrative authority; consistent with `/play`, `/advance`, `/mode`; CC Q3: Matt-initiated compression is dominant norm | Players cannot directly request scene compression | Players who want to signal departure must do so in character (T2 handles this in v1.x; until then, DM uses `/compress`) |
| (b) Player-accessible | Lets players explicitly trigger compression | Players can force scene transitions the DM didn't intend; violates DM narrative authority | A player in a scene they're bored with compresses a scene the DM intends to resolve differently |

**Recommended default:** **(a) DM-only.**

**Reasoning:** Scene compression is a DM narrative authority decision — the DM decides when a scene has run its course. The CC Q3 finding (DM-initiated `matt_initiated` compressions dominant) empirically validates DM authority over compression cadence. Player closure intent has a structural path (T2 in v1.x; for now, player says "we leave" and the DM uses `/compress` or waits for T1). DM-only gate is consistent with every other DM authority command.

**Confidence: HIGH.**

---

### §3.G — Stale counter bounds and overflow behavior

**Question:** Does the counter cap at `_STALE_HARD_THRESHOLD` or accumulate indefinitely?

**Candidates:** (a) cap at hard threshold · (b) accumulate indefinitely · (c) cap with backoff

| Candidate | Pros | Cons | Risk |
|---|---|---|---|
| (a) Cap at threshold | Bounded counter value; simpler to reason about | No telemetry value above threshold (can't measure how long past threshold a scene stayed) | Loses measurement signal for scenes that persist despite strong directive |
| **(b) Accumulate** | Full telemetry value preserved; behavioral effect identical to (a) for directive tier (strong fires every turn above threshold) | Counter climbs indefinitely; large values have no semantic meaning beyond "past threshold" | Strong directive fires on every exploration turn indefinitely until reset — could create prompt noise if the directive text is injected repeatedly |
| (c) Backoff | Reduces repeated strong-directive injection; less prompt noise | Adds complexity; hides the signal that the DM LLM is ignoring the directive | Suppression during backoff may mask a real problem (LLM non-compliance with strong directive) |

**Recommended default:** **(b) accumulate.**

**Reasoning:** Telemetry value justifies accumulation — the number of turns a scene persisted PAST the hard threshold is meaningful calibration data. Behavioral effect is identical to (a) for the directive tier decision. (c) adds architectural complexity for an uncertain benefit; if strong directive fires repeatedly without compression, that IS the signal worth measuring, not suppressing.

**Open axis for (c):** if playtest shows strong directives firing 10+ times per session without compression, and the DM experience is degraded (noisy prompts), (c) backoff of K=3 turns is the adjustment. Log signal: `scene_lifecycle: tier=strong fired=1` counts per session > 6 (the hard threshold value); if routine, add backoff.

**Confidence: MEDIUM.** Accumulate is the right call for v1 telemetry purposes, but repeated strong-directive injection could degrade DM prompt quality in ways not visible at spec time.

---

### §3.H — Cliff-edge enforcement: instruction-side only or both layers?

**Question:** Should the directive use instruction-side enforcement only (MUST-NOT clauses in text), or also information-side suppression (block specific context blocks during compression turns)?

**Candidates:** (a) instruction-side only · (b) both layers (instruction + information)

| Candidate | Pros | Cons | Risk |
|---|---|---|---|
| **(a) Instruction-side only** | Simpler implementation; consistent with pacing/consequence directives which use instruction-side only; strong anchor (threshold reached IS a structural signal) | Relies on LLM compliance with MUST-NOT clauses; if LLM ignores the directive, no backup | §77 two-layer was needed for ROUND_START specifically because ROUND_START had weak event anchoring; scene lifecycle at strong threshold has strong anchoring, so instruction-side may be sufficient |
| (b) Both layers | Defense-in-depth per established §77+§78 pattern; structurally prevents bleed-source content from polluting the compression narration | Requires identifying which prompt blocks to suppress during compression turns (empirical audit, S44 pattern) | Over-engineering for v1; adds complexity that S44 took three verify passes to establish |

**Recommended default:** **(a) instruction-side only for v1.**

**Reasoning:** The §77 two-layer enforcement was necessary for ROUND_START because it has weak event anchoring — with no specific combat event to narrate, the LLM falls back to available context and produces phantom NPCs, stale framing, etc. Scene lifecycle at the strong threshold has much stronger anchoring: the directive says "COMPRESS THIS SCENE NOW" with a specific task framing that gives the LLM clear behavioral direction. The soft-nudge tier says "consider compressing" which is lighter but still explicit. Neither is the weak-anchor case that necessitated information-side suppression in S44.

**Open axis for (b):** if v1 playtest shows the LLM generating new story content under strong directive (new NPCs introduced, new plot threads opened, scene extended despite COMPRESS NOW), that is the S44 symptom and information-side suppression is the response. Log signal: manual review of post-compression narrations shows content that violates the MUST-NOT clauses (new NPC threads, extended location narration, etc.). Identifiable without a verifier via spot-check of `last_dm_response` in journal.

**Confidence: MEDIUM.** The weak-anchor concern is real for soft-nudge tier specifically — the LLM at soft threshold may ignore the suggestion and elaborate instead. If soft-nudge shows drift, information-side suppression may be needed at strong-tier only while soft-tier remains instruction-only.

---

### §3.I — Combat mode counter behavior

**Question:** When mode='combat', does the stale counter freeze or reset?

**Candidates:** (a) freeze during combat · (b) reset on combat start (`!init begin`) · (c) reset on combat end (`!init end`)

| Candidate | Pros | Cons | Risk |
|---|---|---|---|
| (a) Freeze | Pre-combat stale value preserved; if scene was stale before combat, it's still stale after | Post-combat: party emerges at stale=N with immediate strong directive — COMBAT_END narration just happened; counter at high value is semantically wrong | Immediate strong directive post-combat is exactly what climactic-hold suppression is trying to prevent; freeze + high stale value = high-priority anti-pattern |
| **(b) Reset on combat start** | Combat is an activity signal by definition; mode flip to combat is a scene-defining event; post-combat exploration starts fresh | Requires that `!init begin` activity signal wiring fires the counter reset | Counter reset requires the mode-flip to be detectable as an activity signal; Session 3 wiring detail |
| (c) Reset on combat end | Same behavioral result as (b) | Requires explicit reset hook in `_handle_init_event` evt_type='end' | Adds a dedicated code path where the (b) activity signal avoids it |

**Recommended default:** **(b) reset on combat start via activity signal.**

**Reasoning:** Combat entry is an activity signal by definition — mode flip from exploration to combat IS a new scene-defining event. Post-combat exploration starting at stale=0 is semantically correct: the COMBAT_END narration just fired, the scene is not stale, the party is at a meaningful moment. (a) freeze produces the exact anti-pattern the climactic-hold rule is trying to prevent. (c) achieves the same result as (b) but requires a dedicated hook; (b) is self-consistent if the activity-signal system is wired correctly.

**Confidence: HIGH.**

---

### §3.J — `/compress` counter reset

**Question:** Should `/compress` reset the stale counter to 0 or leave it at current value?

**Candidates:** (a) reset to 0 · (b) leave counter at current value

| Candidate | Pros | Cons | Risk |
|---|---|---|---|
| **(a) Reset to 0** | Explicit compression is a successful transition; start fresh; trusts DM intent | If compression narration failed (LLM ignored it), counter at 0 means no auto-fire on next turn | DM can use `/compress` again if needed; counter rebuilds if scene is still stale |
| (b) Leave counter | If compression was ineffective, auto-fire continues immediately | On first post-compress turn, strong directive fires again — conflicts with just-posted compression narration | Contradicts the narrative continuity of the compression turn; DM just compressed, strong directive immediately refires |

**Recommended default:** **(a) reset to 0.**

**Reasoning:** `/compress` is a DM intent signal that the DM wants the scene to move forward. Resetting to 0 trusts that the explicit compression landed. If it didn't land, the counter rebuilds and the directive fires again after N stale turns. (b) would cause the strong directive to fire on the very next turn after compression, conflicting with the just-dispatched compression narration and creating a contradictory prompt context.

**Confidence: HIGH.**

---

### §3.K — Stale counter visibility to LLM

**Question:** Should the stale counter appear in the DM prompt, or remain invisible?

**Candidates:** (a) invisible · (b) scene footer · (c) scene_state block

| Candidate | Pros | Cons | Risk |
|---|---|---|---|
| **(a) Invisible** | Counter is internal machinery, not world-state fact; §76 risk avoided entirely; LLM's signal is the directive text | LLM has no ambient awareness of scene age | No meaningful con — the directive IS the awareness signal |
| (b) Scene footer | LLM sees turn count as a scene-footer field like `mode` | Exposes a meta-textual number; §76 audit: retrieved=yes, narratively inferential=yes (LLM could narrate "the scene has stretched on for N turns") | §76 risk surface — the counter exposed in a retrieved field invites narrative elaboration |
| (c) Scene_state block | — | Same §76 risk as (b), worse: scene_state block has higher LLM attention weight | Highest §76 risk; counter would be treated as a world-state fact |

**Recommended default:** **(a) invisible.**

**Reasoning:** The stale counter is a calibration primitive, not a world-state fact. The LLM's signal is the directive text when it fires — that IS the scene-age awareness the LLM should receive. Exposing the counter in a retrieved field (b) or (c) hits §76 property 3 (retrieved) and property 4 (narratively inferential — "the scene has lasted N turns" is exactly the kind of elaboration the LLM would produce). §76 audit: in-memory counter hits 0/4 properties by design; exposing it would push toward 2/4 or 3/4. Keep it invisible.

**Confidence: HIGH.** §76 support is strong for this recommendation.

---

### §3.L — Climactic-hold predicate definition

**Question:** What signal set triggers climactic-hold suppression (§5.7)?

**Candidates:**
- **(a) Minimal:** `_combat_beats > 0` in last N turns + active commitment_directive firing on current turn
- **(b) Extended:** (a) plus DOWNED beats specifically in last M turns + recent combat exit within K turns of `!init end`
- **(c) Minimal + DM override:** (a) set plus `/force-compress` command that bypasses suppression

**Gap surfaced during walk:** `_combat_beats` is CLEARED at `!init end` dispatch (S50 §78.6 pattern). In post-COMBAT_END exploration phase — the primary context where climactic-hold matters — `_combat_beats[guild_id] = 0` always. The (a) predicate's `_combat_beats > 0` arm therefore never fires in post-combat exploration; it only fires during combat mode, which §11.A's mode gate already suppresses. The practical (a) predicate is: **`active_commitment_directive → suppress`** plus the dead (but harmless) `_combat_beats > 0` check.

**Trade-offs:**

| Candidate | Pros | Cons | Risk |
|---|---|---|---|
| (a) as written | No new state surfaces; reuses `_combat_beats`; minimal implementation | `_combat_beats > 0` arm is dead in post-combat (where it matters most); effective predicate is only `commitment_directive active` | Climactic-hold suppression works only via commitment_directive signal, not beat history; zero-compression episodes after intense combats NOT caught |
| (a) modified + combat-exit window | Closes post-combat gap; one small in-memory addition (`_last_combat_end: dict[int, int]`, one write at `_handle_init_event`); still simpler than full (b) | Slightly more state than "minimal"; requires setting `_last_combat_end[guild_id] = turn_counter` at COMBAT_END | Low risk; bounded state (one per guild); single write point |
| **(b) Extended** | Most faithful to CC X4 R1/R2 (BLOODIED+DOWNED+recent-combat predicate); catches post-intense-combat scenes | Requires new in-memory tracker for turns-since-DOWNED (DOWNED specifically in last M turns is not preserved post-combat-end); `_last_combat_end` is needed regardless | (b) full implementation is more complex but provides the strongest empirical grounding |
| (c) Minimal + override | DM can always override false-positive suppression | Adds `/force-compress` command (new slash command surface); complicates the suppression architecture | New command surface for a low-frequency edge case |

**Synthesis:**

CC X4 R1/R2 finding: the zero-compression cluster (10.6% of episodes) correlates with combats where BLOODIED + DOWNED events occurred (C1E114 finale, C1E076, C1E108). The post-combat period immediately after intense fights is when climactic-hold suppression should fire. This empirically grounds (b)'s "recent combat exit + DOWNED beats" predicate.

However, tracking "DOWNED beats specifically in last M turns" post-COMBAT_END requires either: (1) a separate counter cleared on a different cadence from `_combat_beats`, or (2) a `_last_combat_had_downed: dict[int, bool]` flag set at `!init end`. The latter is simpler: at COMBAT_END, set `_last_combat_had_downed[guild_id] = (combat_beats > 0)` BEFORE clearing `_combat_beats`. This preserves the beat signal across the mode boundary.

**Recommended default:** **(a) modified — commitment_directive + combat-exit window + last-combat-had-beats flag.**

Concretely: at COMBAT_END dispatch, BEFORE clearing `_combat_beats`, capture `_last_combat_had_beats[guild_id] = (_combat_beats.get(guild_id, 0) > 0)`. Also set `_last_combat_end_turn[guild_id] = current_turn_counter`. At fire-time: suppress if (`turn_counter - _last_combat_end_turn.get(guild_id, -inf) < K` AND `_last_combat_had_beats.get(guild_id, False)`) OR (`active_commitment_directive`). Two new in-memory dicts; two write points (both at `_handle_init_event` evt_type='end').

This is (a) modified — simpler than full (b) (no "DOWNED specifically" tracking, no DOWNED-beat memory), but closes the post-combat gap that (a) as written misses.

**Log signal that would justify full (b) as v1.x extension:** `scene_lifecycle: fired=0 reason=climactic_hold_suppressed predicate=none` — suppression NOT triggered despite post-intense-combat context — correlating with turns where the DM force-compressed or the session ended with 0 compressions post-intense-combat. If the modified (a) misses real climactic-hold events, the log evidence will surface it.

**Confidence: MEDIUM.** The gap was identified during this walk; the (a) modified shape is cleaner than full (b) but not yet validated against the codebase implementation path. Session 3 should confirm the `_handle_init_event` capture point is correct before finalizing.

**OPEN — operator's call. This walk provides the architectural analysis; operator locks the predicate signal set.**

---

### §3.M — §1a auto-fire scrutiny

**Question:** Is the auto-fire scene lifecycle directive comfortable under §1a ("LLM never decides mechanical outcomes")?

**This decision requires operator + Oracle. Code declines to lean. The review surfaces both reads and concrete implementation shapes if (b).**

**Two reads:**

**Read (a) — §1a holds; compression is atmospheric guidance.**

§1a's "mechanical outcomes" refers to adjudicator-bound events: HP, hit/miss resolution, saves, conditions, resource expenditure. Scene compression produces none of these. The LLM's job as DM is to narrate the world moving forward — scene closure is narrative movement, not mechanical adjudication. The directive is a structural constraint on WHEN and HOW the LLM advances the narrative, not a decision about game-mechanical truth.

Doctrinal support: §77 defines "atmospheric continuity, not adjudication" — the allowed/forbidden list covers mechanical-state inference. Scene compression is explicitly in the "allowed" category: narrating a scene conclusion, handing agency back to players in a new context. The pacing directive (which says "be intense/quiet") and commitment directive (which says "don't change your stated action") both constrain LLM behavior within the narrative without touching §1a. Scene lifecycle is in the same class.

**Read (b) — §1a is uncomfortable; directive is a state-change request.**

The scene lifecycle directive is structurally heavier than pacing/commitment. Pacing constrains tone; commitment constrains within-turn action; scene lifecycle instructs the LLM to CONCLUDE a scene segment — a move with narrative permanence. There is no `ROLL_OUTCOME_DRIFT` verifier or `VERDICT_CONTRADICTION` checker for scene compression. If the LLM auto-fires at turn 6 and the scene was not genuinely stale (false positive — the stale counter reached threshold during a tense but narratively active scene), the compression narration becomes part of the game record with no architectural recovery path.

The auto-fire mechanism amplifies this: the engine is ordering the LLM to make a structural narrative decision every few turns. §1a's spirit is "move decisions out of the prompt and into structure." Scene lifecycle moves a DIFFERENT decision (when to end a scene) from DM judgment into engine automation. Whether this is desirable depends on whether the operator trusts the stale counter's signal quality — which is unvalidated at v1 launch.

**Implementation shapes if (b) resolves the question:**

**Shape B1 — Soft-tier auto-fire only; strong tier requires explicit `/compress`.**
Auto-fire fires only the soft-nudge directive (tier 1). Strong directive ("COMPRESS THIS SCENE NOW") is only reachable via explicit `/compress` command. The engine SUGGESTS compression to the LLM at soft threshold; the DM CONFIRMS compression by typing `/compress`. This is a §1b validated-suggester pattern in spirit: system proposes (soft nudge at turn N_soft), operator approves (explicit `/compress`), system executes (strong directive fires).

Implementation delta from specced v1:
- `compute_scene_lifecycle_directive` at hard threshold returns `('', {fired: 0, tier: 'none', reason: 'hard_threshold_requires_explicit'})` for auto-fire calls
- `/compress` is the ONLY path to strong directive
- `_STALE_HARD_THRESHOLD` effectively becomes a DM-reminder threshold, not a force threshold
- Telemetry: `scene_lifecycle: tier=soft fired=1` is the auto-fire max; `/compress` is always the strong-tier gate

**Shape B2 — §1b validated-suggester via #dm-aside.**
At hard threshold, engine posts a compression suggestion to `#dm-aside` rather than injecting into the DM prompt: "Scene lifecycle: this scene has been active N turns. Type `/compress` to compress or continue narrating." DM approves by typing `/compress`. LLM never receives the strong directive automatically.

Implementation delta:
- At hard threshold, `compute_scene_lifecycle_directive` returns `('', {fired: 0, tier: 'none', suggest_compress: True})`
- Call site in `build_dm_context` checks `suggest_compress` and dispatches an aside post
- All §59 sibling contract preserved; soft-nudge auto-fire unchanged
- New `#dm-aside` post type (compression suggestion format)

**B1 is the simpler implementation.** B2 is purer §1b but requires a new aside-post format and operator-acknowledgment loop. If (b) resolves, recommend B1 as the initial shape.

**Operator + Oracle walk required before Session 3. No lean from this review.**

---

### §3.N — T2 deferral confirmation

**Question:** Ship T2 (player closure intent detection) in v1, or defer to v1.x?

**Ship case (Code's prior Phase 1 lean):**

T2 is architecturally thin — a phrase-vocabulary check on player text, identical in shape to the commitment directive's retraction-grammar filter (S19 precedent). The retraction filter ships with a small fixed vocabulary; T2 would be the same pattern. CC SCENE_CUT (2.7%) + LOCATION_DEPARTURE assist (18.9%) are real coverage surfaces. Adding T2 closes the player-initiated immediate scene-close gap without new infrastructure.

**Defer case (v0.1 lean):**

T2 phrase vocabulary lacks CC precision grounding. The CC findings measure LOCATION_DEPARTURE at 54.5% precision in the CRD3 corpus — meaning 45.5% of CC-labeled LOCATION_DEPARTURE records are misclassified or borderline. `/travel` already handles explicit player departure commands. T2 would catch player text like "we head out" — but the CC corpus doesn't provide a precision measurement for this specific phrase subset. Without a precision floor, false-positive risk is real: a player who says "let's go" to an NPC (in-character, not meaning to trigger scene compression) activates T2 and auto-fires compression.

The S19 retraction-grammar filter cited as precedent is NOT perfectly analogous: retraction detection fires on specific grammatical patterns ("actually, I'll...", "wait, I change my...") that are unambiguous within the commitment-directive context. Player closure intent phrases ("we head out," "let's go," "time to move") are high-frequency general English that appear in non-departure contexts regularly.

**Trade-offs:**

| Option | Pros | Cons | Risk |
|---|---|---|---|
| Ship T2 | Closes player-initiated scene-close gap immediately; thin implementation; covers SCENE_CUT + LOCATION_DEPARTURE assist | Phrase vocabulary precision unvalidated; false-positive compression risk; retraction-filter precedent is imperfect analogy | Player says "let's go" in-character mid-scene; compression fires; session disruption without DM intent |
| **Defer T2** | Avoids false-positive risk; T1 covers same events at delay; DM uses `/compress` for immediate scene-close; clean v1 scope | Player-initiated immediate scene-close is a UX gap (N stale turns delayed); T2 not available until corpus grounding exists | Gap is UX, not coverage — events eventually handled via T1; low impact |

**Recommended default: defer T2 to v1.x.**

**Reasoning:** The false-positive risk for T2 is higher than the retraction-filter analogy suggests. "Let's go" is a high-frequency, context-dependent phrase; the commitment directive's retraction patterns are syntactically distinctive. Without corpus precision grounding for closure-intent phrase detection specifically, shipping T2 risks scene compression firing on in-character player dialogue that happened to use a departure phrase. T1 catches all the same events at a stale-turn delay — the gap is responsive immediacy, not coverage. The DM has `/compress` for immediate scene close when the player signals intent. V1's scope is already well-defined with T1 + `/compress`; T2 can be added after T1 logs show whether player-side missed compressions surface as friction.

**Log signal that would justify shipping T2 in v1.x:** post-v1 playtest shows: (a) DM uses `/compress` repeatedly within 1-2 turns of player departure statements (suggesting T2 would have fired before DM intervention), AND (b) no false-positive compressions would have been introduced by the phrase vocabulary used. Both signals are extractable from journal: `journalctl | grep "scene_lifecycle_reset.*explicit_compress"` correlated with the `last_player_action` field on the preceding turn.

**Confidence: MEDIUM.** The "thin" implementation case for shipping is real; if the phrase vocabulary can be tightly scoped to avoid false positives (e.g., only fire on "we head out," "let's leave," "we're done here" + explicit movement verbs toward a destination), the risk drops significantly. Operator judgment on acceptable false-positive rate for scene compression is the deciding factor here.

---

### §3.O — NEW: `/play` command and stale counter reset

**Surfaced during walk.** §11.J addresses `/compress` resetting the counter. But `/play` (session-opening command, DM-initiated) is not addressed in §1.F or §11.J through §11.N. `/play` signals a new session start with an opening narration — the stale counter should reset to 0 at `/play` invocation. Without an explicit decision, the implementation may:
- Leave the counter at its prior value (carry-across from previous session) → immediate directive on first player turn of a new session
- Not initialize the counter (dict miss → counter reads as 0 by default) → correct behavior by accident if the dict uses `defaultdict(int)` or `.get(guild_id, 0)`

**Candidates:**
- **(a) Explicit reset at `/play`** — `/play` handler resets `_scene_stale_turns[guild_id] = 0`
- **(b) Implicit reset via defaultdict** — in-memory dict initialized as `defaultdict(int)` or all reads use `.get(guild_id, 0)`; `/play` doesn't need to touch it because the counter is 0 on first access if never incremented
- **(c) Reset via activity signal** — `/play` fires a "scene opened" event that counts as an activity signal; counter resets via the same mechanism as location_change/advance_time

**Recommended: (a) explicit reset at `/play`**, with (b) as implementation safety net.

**Reasoning:** `/play` is a session-demarcation command. Making the stale counter reset at `/play` explicit (one line in the `/play` handler) is clearer than relying on dict initialization behavior. (b) is correct as a safety net (the counter should use `.get(guild_id, 0)` everywhere), but the explicit reset in `/play` makes the intention documented in code. (c) adds complexity for a simple case. Session 3 implementation: add `_scene_stale_turns[guild_id] = 0` (or `_scene_stale_turns.pop(guild_id, None)` for defaultdict) to the `/play` handler alongside the existing scene-setup calls.

**Confidence: HIGH.** This is a discovered gap; the fix is a one-line implementation detail, but worth naming as §11.O so Session 3 doesn't miss it.

---

## §4. Decisions requiring operator + Oracle

**§11.M is operator + Oracle territory.** Per v0.1 §8 explicit framing. Two reads surface cleanly:

- Read (a): Compression is atmospheric guidance under §1a; narrative advancement is the LLM's job; the directive constrains WHEN/HOW not WHETHER narrative outcomes bind. Proceeds as specced.
- Read (b): Strong auto-fire directive is a state-change request with no mechanical verifier; the engine is automating DM judgment; uncomfortable if stale counter produces false positives. Implementation shape: B1 (soft-tier auto-fire only, strong requires explicit `/compress`).

**Operator + Oracle walk this together before Session 3 opens.** The review provides both reads and both implementation shapes; the architectural call belongs with the operator.

---

## §5. Summary of recommended defaults

| Decision | Recommended | Confidence |
|---|---|---|
| §11.A Mode scope | (b) exploration+social | MEDIUM |
| §11.B Rest-event suppression | (b) natural via advance_time | HIGH |
| §11.C T1 vs T1+T2 | **Follows §11.N** | — |
| §11.D Threshold values | (b) named constants in code | HIGH |
| §11.E Activity signals | (a) §1.F signals only | HIGH |
| §11.F /compress access | (a) DM-only | HIGH |
| §11.G Counter overflow | (b) accumulate | MEDIUM |
| §11.H Cliff-edge enforcement | (a) instruction-side only | MEDIUM |
| §11.I Combat mode counter | (b) reset on combat start | HIGH |
| §11.J /compress counter reset | (a) reset to 0 | HIGH |
| §11.K Counter visibility | (a) invisible | HIGH |
| §11.L Climactic-hold predicate | (a) modified: commitment + combat-exit window + last-combat-had-beats flag | MEDIUM |
| §11.M §1a auto-fire scrutiny | **DECLINED TO LEAN — operator + Oracle** | — |
| §11.N T2 deferral | Defer T2 to v1.x | MEDIUM |
| §11.O /play counter reset | (a) explicit reset at /play | HIGH |

**HIGH confidence (no synthesis pressure, proceed with recommended):** §11.B, §11.D, §11.E, §11.F, §11.I, §11.J, §11.K, §11.O (8 decisions)

**MEDIUM confidence (operator attention helpful, open axis named):** §11.A, §11.G, §11.H, §11.L, §11.N (5 decisions)

**Operator + Oracle required (no lean):** §11.M (1 decision)

**Follows other decision:** §11.C follows §11.N (1 decision)

---

## §6. Handoff

| Field | Value |
|---|---|
| **Review doc** | `/home/jordaneal/virgil-docs/SCENE_LIFECYCLE_V1_REVIEW.md` |
| **Decisions walked** | 14 (§11.A–§11.N) + 1 discovered (§11.O) = 15 total |
| **HIGH confidence decisions** | 8 (§11.B, §11.D, §11.E, §11.F, §11.I, §11.J, §11.K, §11.O) |
| **MEDIUM confidence decisions** | 5 (§11.A, §11.G, §11.H, §11.L, §11.N) |
| **Operator + Oracle required** | §11.M (no lean; see §3.M for both reads and implementation shapes) |
| **Follows other decision** | §11.C follows §11.N resolution |
| **HALT escalations** | 0 |
| **Inventory note** | §11.L gap surfaced: `_combat_beats` cleared at COMBAT_END, so (a) minimal as written doesn't fire in post-combat exploration. (a) modified with `_last_combat_had_beats` + `_last_combat_end_turn` dicts closes the gap. |
| **New §11.O discovered** | `/play` command stale counter reset — not addressed in spec; one-line implementation at `/play` handler |

**Next session:** Session 3 = implementation. Operator resolves §11.M (with Oracle), confirms §11.N, locks remaining decisions. Spec flips DRAFT → LOCKED. Session 3 opens against locked spec.

**Session 3 model recommendation:** Sonnet medium per WORKING_WITH_CLAUDE.md cadence table ("templated implementation ship against §59 sibling pattern with clear precedent"). Code has 10 §59 sibling instances to reference; the pattern is mature. Implementation checklist: `compute_scene_lifecycle_directive` in `dnd_orchestration.py`, `_scene_stale_turns` dict in `discord_dnd_bot.py`, activity-signal wiring in `on_message` and event handlers, `/compress` slash command, test suite per §8 sketch. HALT points for Session 3: if §78.5 promotion check reopens during implementation (any mode-write surface appears that wasn't in the spec), pause and escalate.
