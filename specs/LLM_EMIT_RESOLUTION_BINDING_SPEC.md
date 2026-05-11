# Ship A — LLM-Emitted-Directive Resolution Binding — Design Spec v1

**Status:** LOCKED v1 — S35b review complete (`LLM_EMIT_RESOLUTION_BINDING_REVIEW.md`). 18 decisions reviewed (12 pre-locked from `MULTIPLAYER_FIXES.md` v3 §12 operator review + 6 surfaced in spec §11.B.1–B.6). 16 decisions confirmed at Code's recommendation; 2 with framing revisions applied per review §4. No architectural changes from spec draft. Six revisions landed at §4.2, §5.2, §5.4, §5.5, §10.2, §11.B.2, §11.B.6, §15.9 (line-level wording, no section rewrites). Ready for S36 implementation per v3 §4.6 (Opus high).
**Pattern:** Closes Finding L on the primary play loop. Companion to shipped Ship 1 (`RESOLUTION_BINDING_SPEC.md` LOCKED v1, S33–S34) which closes the same finding on the secondary DM-typed-directive surface. Ship A is **architecturally additive** to Ship 1 — reuses every primitive Ship 1 introduced (`ResolutionResult`, `resolve_directive`, render helpers, ROLL_OUTCOME_DRIFT verifier, `_handle_dm_roll_arrival` matcher, `_fire_resolution_narration` auto-fire coroutine, AUTHORITATIVE-CANON prompt block, `dnd_pending_roll_directives.dc` column) and adds (a) a second writer at narration-emission time, (b) a `ResolutionTexture` sub-dataclass + `compute_stakes_tier` pure function for difficulty/margin/stakes scaling, (c) crit-tier rendering for nat-20/nat-1 narrative texture, (d) a prompt-side change instructing the LLM to include a DC when emitting a roll directive, (e) a wrong-skill aside.
**Track:** Multiplayer Fixes — Ship A. Closes Finding L surface 2 (primary play loop, ~90% of natural play) per `MULTIPLAYER_FIXES.md` v3 §1 row 2. Sequenced ahead of Ships 2–5 per the trigger-statement axis (playability now) locked in v3 §3.
**Failure mode this targets:**
- **Finding L on the LLM-emitted-directive surface.** Operator types intent ("I take a closer look"); LLM narrates a response and emits `!check perception 15` inside the narration; Avrae sees the embed and rolls; bot does NOTHING because the LLM's emission never created a `dnd_pending_roll_directives` row (the `_handle_dm_roll_directive` writer is triggered from `on_message`, which short-circuits on `message.author.bot`). Resolution-binding misses entirely on this surface. Track 7 #1's CHECK_ACTION binding catches it ONE TURN LATER via adjudicator's `consume_recent_check` when the operator types the next player text — but the operator wants the outcome NOW, not after typing "what happens?". Ship A closes the immediacy gap.

**Architectural diagnosis:** Ship 1 closed the matcher → resolve → render → auto-fire pipeline. The pending-row WRITE was assumed to come from `_handle_dm_roll_directive` on a human DM's `!`-prefixed message. The 90% case has a different writer trigger (bot is about to post LLM-generated narration containing a directive). Ship A adds the missing writer.

---

## §1. Problem statement (LLM-emitted-directive surface)

### §1.1 The play loop

Solo natural play, Donovan-bound DM operator on campaign 22:

```
12:55 Operator: "I take a closer look at the glinting object."
12:55 Bot (LLM): "Donovan leans closer, his fingertips tracing the slick surface..."
                  ... + LLM-emitted `!check perception 15` at end of narration
12:55 Avrae: "Donovan Ruby makes a Perception check! 1d20 (14) + 1 = 15"
12:55 Operator: (waits)
12:56 Bot: SILENT — no auto-fire on Avrae embed arrival
12:57 Operator: "Well? What do I find?"
12:57 Bot (LLM): "Your sharp eyes catch a barely perceptible line of silver lettering..."
                  ← Track 7 #1's CHECK_ACTION binding fires here via consume_recent_check;
                    the buffered Avrae roll feeds the adjudicator; narration is constrained
                    to honor `success = (15 >= 15)` = True.
```

The narrative pause at 12:56–12:57 is the friction Ship A closes. Operator wants the outcome narration to auto-fire within ~10s of the Avrae embed landing, not after they type a follow-up.

### §1.2 Why Ship 1's matcher doesn't fire on this surface

Ship 1's matcher (`_handle_dm_roll_arrival`) is correct — it consumes any pending directive row when an Avrae roll matches actor+skill. The gap is that **no row exists** for LLM-emitted directives. Trace:

1. Bot's `dm_respond` produces response text containing `!check perception 15` at the end.
2. Bot posts the response as a Discord embed via `channel.send(embed=embed)`.
3. Discord delivers the embed; Avrae sees it; Avrae rolls perception for the bound character.
4. Avrae's roll embed posts to `#dm-narration`.
5. Virgil's `on_message` fires for Avrae's embed → `_handle_dm_roll_arrival(campaign_id, event)`.
6. **`pending_directive_get_active(campaign_id)` returns None.** No row was ever written.
7. Matcher returns `{aside: None, auto_fire: None}` and falls through.
8. Avrae roll is buffered for next-player-turn consumption per Track 7 #1.

Steps 5–7 are the gap. The missing write is in steps 1–2 — when the bot has the response text in hand and is about to post it.

### §1.3 Why pure prompt-side fixes don't close this

Track 7 #1's HARD STOP RULES instruct the LLM to "end your message with the roll request and NOTHING ELSE" — so the LLM's `!check` emission is intentional and structural. But Track 7 #1's binding fires on the NEXT player turn through the adjudicator, not on Avrae roll arrival.

Adding a prompt-side instruction "and please wait for the roll before continuing" doesn't help — the wait happens in operator time (between turns), not in bot code. The structural fix is: bot writes a pending directive row at emission time, matcher consumes it on Avrae roll arrival, auto-fire fires the outcome narration.

### §1.4 What "structurally closed" means here

Ship A's invariant: once the bot posts narration containing `!check <skill> <DC>` or `!save <stat> <DC>`, the bot has ALSO written a pending directive row keyed by the current acting character + parsed skill + parsed DC. On Avrae's roll arrival, the matcher consumes that row, computes `passed = roll_total >= dc`, and `_fire_resolution_narration` schedules `_dm_respond_and_post(resolution_result=…)` with the AUTHORITATIVE-CANON block (now extended with difficulty/margin/stakes/crit-tier texture) rendered at top-of-prompt. The auto-fired second narration honors the binding; ROLL_OUTCOME_DRIFT verifier is the safety net.

This is the same closure shape Ship 1 used on the DM-typed-directive surface, applied to the LLM-emitted surface via a different trigger.

---

## §2. Architectural shape (locked elements; do NOT re-litigate)

The fix shape is locked in `MULTIPLAYER_FIXES.md` v3 §4. This section restates the locks for spec-internal reference and records the recon-confirmed implementation anchors.

### §2.1 Locked elements (verbatim from v3)

1. **New writer at narration-emission time** in `_dm_respond_and_post`, post-`dm_respond`-pre-Discord-post. Parses LLM's narration text for `!check <skill>[ <dc>]` / `!save <stat>[ <dc>]` patterns; on match, calls `pending_directive_upsert(... dc=parsed)`. Implementation insertion point: AFTER `msg = await channel.send(embed=embed)` (line 2359 in current `discord_dnd_bot.py`), BEFORE the asyncio.create_task calls for `_attach_hints` and `_extract_and_persist_world`. Source_message_id = `str(msg.id)` (the bot's posted message).
2. **Prompt-side change** instructing the LLM to include a DC when emitting a roll directive. RollDecision.to_prompt_directive's skill/save branches gain a `<DC>` placeholder; HARD STOP RULE 1 gains a sentence requiring the DC; HARD STOP RULE 5 stays-as-is (its `!`-prefix scope is unchanged).
3. **`ResolutionTexture` sub-dataclass** referenced by `ResolutionResult.texture: ResolutionTexture | None = None`. Field-additive; existing callers receive `texture=None` and degrade to current behavior. Carries `difficulty_band`, `margin`, `margin_tier`, `stakes_tier`, plus `effective_dc`, `modifier`.
4. **`compute_stakes_tier` pure function** in `dnd_orchestration.py` as ninth Doctrine §59 instance. Sibling to `compute_persistence_directive`, `compute_commitment_directive`, etc. No DB writes; pure compute from supplied inputs.
5. **Difficulty-band + margin-tier + crit-tier render extensions** in `render_resolution_block`. AUTHORITATIVE-CANON block stays internal (player never sees the breakdown); only the LLM consumes it as constraint. Crit-tier clauses fire as a separate signal independent of pass/fail per §11.3 RAW (nat does NOT override `passed`).
6. **`_wrong_skill_aside` helper** analog to `_wrong_actor_aside`. Matcher's current silent-ignore-on-skill-mismatch branch flips to log + aside.
7. **Composition with Ship 1's writer**: both trigger surfaces call the same `pending_directive_upsert` helper. §17 single-writer status preserved at the helper layer; two disjoint trigger surfaces calling one writer is structurally compatible.

### §2.2 What is reused unchanged

| Primitive | Module | Status |
|---|---|---|
| `dnd_pending_roll_directives` table + `dc INTEGER` column | `dnd_engine.py` | unchanged |
| `pending_directive_upsert` / `_get_active` / `_consume` / `_delete_by_message` / `_age_seconds` | `dnd_engine.py` | unchanged |
| `_handle_dm_roll_arrival` matcher | `discord_dnd_bot.py` | unchanged (consumes any pending row regardless of who wrote it) |
| `resolve_directive` pure function | `dnd_orchestration.py` | unchanged signature; called with row containing dc parsed from LLM emission instead of DM emission |
| `render_resolution_block` / `render_resolution_hardstop_echo` | `dnd_orchestration.py` | extended (additive — texture rendered when `result.texture is not None`) |
| ROLL_OUTCOME_DRIFT verifier class | `narration_verifier.py` | unchanged |
| `_fire_resolution_narration` coroutine + fallback aside | `discord_dnd_bot.py` | unchanged |
| AUTHORITATIVE-CANON top-of-prompt block + HARD STOP item 8 echo | `dnd_engine.py:build_dm_context` | unchanged structurally; block body extended via `render_resolution_block` (above) |
| `parse_skill_and_dc` helper | `dnd_orchestration.py` | unchanged — already handles trailing-DC integer per Ship 1 §6.2 |
| `unexpected_binding_co_occurrence:` canary log | `dnd_engine.py:build_dm_context` | unchanged |

### §2.3 What Ship A adds

| Element | Module | Lines (estimate) |
|---|---|---|
| `ResolutionTexture` dataclass | `dnd_orchestration.py` | ~25 |
| Extended `ResolutionResult` (one optional field) | `dnd_orchestration.py` | +2 |
| `compute_stakes_tier` pure function + `stakes_tier_log_summary` | `dnd_orchestration.py` | ~80 |
| `compute_resolution_texture` helper (assembles all three tiers from inputs) | `dnd_orchestration.py` | ~40 |
| Extended `render_resolution_block` (texture + crit-tier rendering) | `dnd_orchestration.py` | +60 |
| `_LLM_EMIT_DIRECTIVE_RX` regex + `parse_llm_emit_directive` helper | `discord_dnd_bot.py` | ~40 |
| New writer hook in `_dm_respond_and_post` | `discord_dnd_bot.py` | ~30 |
| Extended `RollDecision.to_prompt_directive` (DC placeholder + band reference) | `dnd_orchestration.py` | ~20 |
| Extended HARD STOP RULE 1 in `build_dm_context` | `dnd_engine.py` | +1 sentence |
| `_wrong_skill_aside` helper + matcher branch flip | `discord_dnd_bot.py` | ~30 |
| Telemetry log lines (new + extensions) | (various) | ~20 |

**Total estimated implementation: ~350 LOC** across 3 files, mostly orchestration. Half of that is the texture/stakes computation surface; the other half is the writer hook + parser + wrong-skill aside.

### §2.4 What spec fills in vs. what is locked

| Locked (do not re-litigate) | Spec fills in |
|---|---|
| Writer hook location (post-Discord-post in `_dm_respond_and_post`) | Hook signature, parser regex, log lines (§6) |
| Inline-DC format `!check skill DC` per A.1 + A.2 recon clean | Exact regex shape, multi-word skill handling (§7) |
| `ResolutionTexture` separate dataclass | Full field list, default values, render helper signatures (§4) |
| `compute_stakes_tier` as §59 9th sibling | Signal inputs, tier-bucket boundaries, signals_dict shape (§5) |
| Difficulty-band + margin-tier in texture | Bucket boundaries (§8, §9) |
| Crit-tier rendered as separate constraint clauses | Vocabulary text per cell, especially nat-20-FAILED and nat-1-PASSED (§10) |
| Wrong-skill aside (decision 12 option b) | Aside copy template, matcher branch shape (§13) |
| Two-embed UX per A.8 | (no spec fill-in needed; orchestration unchanged) |
| TTL=300s per A.6 | (no spec fill-in needed; constant unchanged) |

---

## §3. Composition with Ship 1 (single-writer status of `dc`)

### §3.1 Two writers, one helper

Ship 1's `dc` column has had a documented single-writer status per Doctrine §17 since Ship 1 §6.5: `_handle_dm_roll_directive` writes via `pending_directive_upsert(... dc=...)`. Ship A adds a second trigger surface (the new writer hook in `_dm_respond_and_post`).

**Resolution: both triggers call `pending_directive_upsert`.** That helper is the single writer; the triggers are disjoint surfaces both invoking it. Structurally compatible with §17.

```
Surface A: human DM types `!check perception 10` in #dm-narration
  → on_message → _is_dm_message gate → _handle_dm_roll_directive
  → parse_skill_and_dc → pending_directive_upsert(... dc=10)

Surface B (NEW): bot's response text contains "!check perception 15"
  → _dm_respond_and_post post-channel.send hook → _parse_llm_emit_directive
  → parse_skill_and_dc → pending_directive_upsert(... dc=15, source_message_id=str(msg.id))
```

Both surfaces converge on `pending_directive_upsert`. The helper has been Ship 1's writer-of-record since S34; Ship A doesn't fork it.

### §3.2 Disjoint trigger surfaces

The two trigger surfaces are mutually exclusive by author identity:

- Surface A fires when `message.author` is the DM/creator. Bot messages get short-circuited at the `message.author.bot: return` gate; LLM emissions never reach `_handle_dm_roll_directive`.
- Surface B fires when the bot itself is about to post LLM-generated narration. Human DM messages never reach `_dm_respond_and_post`'s post-channel-send hook.

The trigger surfaces never produce contending writes against the same row at the same time. Each surface's emission is its own pending row (with `pending_directive_replaced` semantics handling sequential upserts).

### §3.3 Race window with Avrae's roll

Surface B's hook fires AFTER `channel.send(embed=embed)` completes. Avrae sees the embed and may roll before the upsert completes. Timing analysis:

- `channel.send(...)` completes → returns `msg` (Discord API response is sub-second)
- Bot's upsert: `pending_directive_upsert(... dc=15, source_message_id=str(msg.id))` — sqlite write is ms
- Avrae's roll: Avrae bot reads the embed, dispatches a roll, posts a roll embed back — typically 2–4 seconds in observation
- Virgil's on_message fires for Avrae's roll → matcher → `pending_directive_get_active`

The upsert lands well before Avrae's roll embed arrives. Race window is structurally safe but not zero. If a race ever fires (operator's network is fast enough that Avrae's response arrives before our upsert completes — unrealistic for Discord+Avrae but defensively considered), the matcher returns None (no pending row), Avrae roll lands in the buffer per Track 7 #1, and the operator gets the outcome narration on their next player turn via the adjudicator path. **Degradation is graceful**; the race produces "no Ship A auto-fire this turn, Track 7 #1 catches it next turn" rather than corruption.

### §3.4 Edit-cancel path scope (locked decision A.6)

Ship 1's edit-cancel path (`pending_directive_delete_by_message`) fires on `on_message_edit` for human DM messages. Bot-message edits do NOT trigger this handler per A.6 lock. Implications for Ship A:

- If `_dm_respond_and_post` is re-invoked (e.g. via verification retry per Track 7 #2), and the retry's response contains a different directive than the original, the original pending row may stay alive until TTL expiry while the retry's row replaces it via `pending_directive_replaced` upsert.
- TTL = 300s (5 minutes). Phantom-binding risk requires a compound condition (operator AFK + LLM re-emit + Avrae roll all inside the 300s window matching the stale row's actor+skill). Rare in natural play; v1.x candidate if multiplayer logs show actual events.

---

## §4. `ResolutionTexture` dataclass (decision A.5 lock)

### §4.1 Definition

```python
@dataclass(frozen=True)
class ResolutionTexture:
    """Narrative-texture signals attached to a ResolutionResult.

    Internal scaffolding for the AUTHORITATIVE-CANON prompt block — player
    never sees these fields directly; the LLM consumes them as constraint
    on narration shape. Ship A adds; Ship 1's pass/fail core unchanged.
    """
    # Derived from DC vs actor modifier:
    effective_dc:   int     # dc - modifier (rounded toward 0 for negatives)
    modifier:       int     # roll_total - nat (Avrae's bound-character modifier)
    difficulty_band: str    # 'trivial' | 'easy' | 'medium' | 'hard' | 'very_hard' | 'nearly_impossible'

    # Derived from roll_total vs dc:
    margin:         int     # roll_total - dc (signed)
    margin_tier:    str     # 'catastrophic_fail' | 'clear_fail' | 'close_fail'
                            # | 'razor_pass' | 'clean_pass' | 'smashing_pass'

    # Derived from scene state at consume time:
    stakes_tier:    str     # 'low' | 'medium' | 'high'
    stakes_signals: dict    # {mode, tension, urgent_clocks, strong_intent, combat_active, score}
                            # — for log telemetry; not consumed by render
```

`frozen=True` per Ship 1 §5.1 immutability precedent. `stakes_signals` is a dict because it's purely log-telemetry; render does not consume it.

### §4.2 ResolutionResult extension

```python
@dataclass(frozen=True)
class ResolutionResult:
    # ... existing Ship 1 fields ...
    texture: ResolutionTexture | None = None  # NEW
```

Default `None` makes the field non-breaking for existing callers (Ship 1's `resolve_directive` returns `ResolutionResult(... texture=None)`; render helpers degrade to existing behavior).

**Field invariant:** `resolve_directive` produces non-None `texture` when scene_state kwarg is supplied; None otherwise. Both writer surfaces (Ship 1 DM-typed and Ship A LLM-emitted) can supply scene_state if they want texture rendering. In S36 implementation, BOTH surfaces' matcher invocations pass scene_state — so Ship 1's resolutions also get textured rendering as a beneficial side effect (per §17.10). The pre-Ship-A behavior (Ship 1's pass-through `resolve_directive(directive_row, avrae_event)` call without scene_state) continues to work and produces `texture=None` — backwards-compatible.

### §4.3 Why a separate dataclass instead of flat fields on ResolutionResult

Per locked decision A.5 + §17 cohesion. Three benefits:

1. **Existing callers unbroken.** ResolutionResult instances created without `texture` get `None` and render the Ship 1 block. No call-site refactor.
2. **Render helpers branch cleanly.** `render_resolution_block(result)` checks `result.texture` and emits the v1 block OR the v1+texture block. No conditional field-by-field rendering.
3. **Composition with future ships.** If F-55 #5.4 (Intent-to-Avrae Resolver) wants to attach different texture fields for attack/cast resolution, it can introduce a parallel `AttackResolutionTexture` without polluting ResolutionResult's signature.

### §4.4 Field invariants

- `effective_dc`: integer, may be negative (DC 5 - modifier +10 = -5). Negative effective DCs map to `trivial`; spec §8 §8.2 covers edge.
- `modifier`: integer, derived from `roll_total - nat`. Always defined when `nat is not None`; when `nat is None` (which v1 only sees for some save events per Ship 1 §5.3), modifier defaults to 0 and difficulty_band is computed from raw DC.
- `margin`: signed integer. Can be very large (smashing_pass on a low-DC trivial check with +10 modifier and nat 18 = margin ~+23).
- `stakes_tier`: always one of 'low' | 'medium' | 'high' (no None). Default 'low' when scene_state is None or empty.
- `stakes_signals`: log-telemetry only. Keys: `mode`, `tension`, `urgent_clocks`, `recent_commitment`, `combat_active`. Always populated.

---

## §5. `compute_stakes_tier` pure function (decision A.4 lock — §59 9th sibling)

### §5.1 Signature

```python
def compute_stakes_tier(
    scene_state: dict | None,
    active_turn: dict | None = None,
    active_quests: list | None = None,
    combatants: list | None = None,
) -> tuple[str, dict]:
    """Compute the stakes-tier signal for narrative texture scaling.

    Pure function. Reads no DB; caller supplies all inputs. No side effects.

    Returns (stakes_tier, signals_dict) per §59 sibling pattern:
      - stakes_tier ∈ {'low', 'medium', 'high'}
      - signals_dict carries the per-input contributions for log telemetry
    """
```

Caller (`compute_resolution_texture` or matcher direct, per §5.3) supplies all four inputs. The function reads `scene_state.mode`, `scene_state.tension_int`, `scene_state.progress_clocks`, `scene_state.last_player_action`, plus active_turn presence + combatants alive-count. Pure — no DB, no Avrae, no LLM.

### §5.2 Scoring shape

Stakes tier is computed via additive scoring across five inputs, then bucketed:

```
score = 0
if mode == 'combat':                   score += 2
elif mode == 'social':                 score += 1
elif mode == 'exploration':            score += 0
elif mode == 'travel':                 score += 0
elif mode == 'downtime':               score -= 1  # explicit low-stakes mode

if tension_int >= 70:                  score += 2
elif tension_int >= 40:                score += 1

if urgent_clocks_present:              score += 1   # any progress_clock with urgency_int >= 7
if strong_intent_in_last_action:       score += 1   # last_player_action matches imperative-verb regex
if combat_active and alive_enemies:    score += 1   # combatants list has alive=1 enemy
```

**`strong_intent_in_last_action` derivation:** matches `\b(?:attack|threaten|demand|refuse|accept|commit|leave|enter|attempt|charge|cast|strike|defy|swear|insist|interrupt)\b` (case-insensitive) against `scene_state.last_player_action`. Purely engine-bound (player text + regex); no LLM-touched field reads, no re-invocation of `compute_commitment_directive`. The simplification avoids re-running commitment-grammar detection in the matcher path (which doesn't have `commitment_signals` available — those are produced once per turn inside `dm_respond`). The regex list is locked v1; tunable v1.x if logs show false-positive or miss patterns vs. the canonical `compute_commitment_directive`'s output.

Bucket:

```
if score >= 4:   tier = 'high'
elif score >= 2: tier = 'medium'
else:            tier = 'low'
```

### §5.3 Why this scoring and not LLM-derived

Deterministic scoring keeps stakes_tier engine-bound. LLM-derived stakes would put the LLM in the position of judging its own narrative texture — a renderer-ruler loop. Per North-Star §2.1 ("LLM is renderer of truth, not ruler"): engine computes stakes tier, LLM renders texture honoring it.

The five inputs are all already engine-bound:
- `scene_state.mode` — single-writer per Ship 1's existing mode-disjoint discipline + scene_state mutations
- `scene_state.tension_int` — bot-appended numeric per Track 3 pacing-directive lineage
- `scene_state.progress_clocks` — slash-command-only writer
- `scene_state.last_player_action` — set by `_dm_respond_and_post` after every player turn
- `combatants` — `dnd_combat_state` snapshot from `get_combatants` (single-writer via `!init list`)

No LLM-touched fields. Stakes is purely a state read.

### §5.4 What `compute_stakes_tier` does NOT do

- Does NOT predict NARRATIVE stakes (the LLM may judge a scene as climactic; that judgment shapes prose, not the tier signal).
- Does NOT incorporate past-turn narration ("the LLM said this was a hard moment" — that's renderer territory).
- Does NOT distinguish per-actor stakes (the same tier applies whether Donovan or Karrok is the acting character). Per-actor stakes is a v1.x candidate if logs show meaningful divergence.

### §5.5 `stakes_tier_log_summary` always-fire helper

Per §59 pattern (every `compute_*` has a `*_log_summary` sibling), Ship A adds:

```python
def stakes_tier_log_summary(signals: dict, tier: str) -> str:
    """Compact log line per §59 / spec §10.4 shape. Always-fire."""
    return (
        f"stakes_tier: tier={tier} "
        f"mode={signals.get('mode', 'unknown')} "
        f"tension={signals.get('tension', 0)} "
        f"urgent_clocks={signals.get('urgent_clocks', 0)} "
        f"strong_intent={signals.get('strong_intent', 0)} "
        f"combat_active={signals.get('combat_active', 0)} "
        f"score={signals.get('score', 0)}"
    )
```

Fires once per Ship A resolution (i.e., once per LLM-emit auto-fire). The score breakdown lets calibration sessions tune the bucket thresholds without re-running play.

### §5.6 `compute_resolution_texture` orchestration helper

Helper that assembles all three texture tiers from inputs, called by the matcher (or by `_dm_respond_and_post`'s hook — see §6.4 for decision):

```python
def compute_resolution_texture(
    dc: int,
    roll_total: int,
    nat: int | None,
    scene_state: dict | None,
    active_turn: dict | None = None,
    active_quests: list | None = None,
    combatants: list | None = None,
) -> ResolutionTexture:
    """Assemble difficulty + margin + stakes tiers into a ResolutionTexture.

    Pure. No DB. Caller supplies all inputs."""
    modifier = (roll_total - nat) if isinstance(nat, int) else 0
    effective_dc = dc - modifier
    difficulty_band = _bucket_difficulty(effective_dc)  # §8
    margin = roll_total - dc
    margin_tier = _bucket_margin(margin)               # §9
    stakes_tier, stakes_signals = compute_stakes_tier(
        scene_state, active_turn, active_quests, combatants
    )
    return ResolutionTexture(
        effective_dc=effective_dc,
        modifier=modifier,
        difficulty_band=difficulty_band,
        margin=margin,
        margin_tier=margin_tier,
        stakes_tier=stakes_tier,
        stakes_signals=stakes_signals,
    )
```

This is a tenth §59-shape function but it's a thin assembler over `compute_stakes_tier`, not a peer-class compute — files as helper, not §59 sibling.

---

## §6. New writer hook in `_dm_respond_and_post`

### §6.1 Insertion point (recon-confirmed)

`discord_dnd_bot.py:2359` — `msg = await channel.send(embed=embed)`. The writer hook fires AFTER this line (msg.id available for `source_message_id`) and BEFORE the asyncio.create_task() calls for `_attach_hints` and `_extract_and_persist_world` at lines 2361–2362.

### §6.2 Hook shape

```python
# Ship A — write LLM-emitted-directive pending row at narration-emission time.
# Soft-fail end-to-end: parser failure or upsert failure must NEVER raise into
# _dm_respond_and_post's outer try/except envelope.
try:
    emit_directive = _parse_llm_emit_directive(response)
    if emit_directive is not None:
        primary_actor = (actor_names_display[0]
                          if actor_names_display else '')
        if primary_actor:
            skill, dc = orch.parse_skill_and_dc(emit_directive['skill_raw'])
            pending_directive_upsert(
                campaign_id=campaign['id'],
                actor_name=primary_actor,
                check_type=skill,
                source_message_id=str(msg.id),
                ttl_seconds=al.PENDING_DIRECTIVE_TTL_SECONDS,
                dc=dc,
            )
            dc_str = str(dc) if dc is not None else 'none'
            log(f"llm_emit_directive_bound: campaign={campaign['id']} "
                f"actor={primary_actor} skill={skill} dc={dc_str} "
                f"kind={emit_directive['kind']} "
                f"source_message_id={msg.id}")
except Exception as e:
    log(f"_llm_emit_directive_write error: {e!r}")
```

### §6.3 Why post-channel-send and not pre-channel-send

Decision A.3 lock: post-channel-send. Reasoning per v3 §4.5:

- Pre-send: no `msg.id` yet → either two-write pattern (write placeholder, then update with msg.id) or fork the source_message_id semantics. Both complicate the edit-cancel path.
- Post-send: `msg.id` immediately available → single write. Race window with Avrae's roll arrival is structurally safe (sub-ms upsert vs. multi-second Avrae round-trip).

### §6.4 Texture computation timing

The texture (difficulty + margin + stakes) needs `roll_total` and `nat` from the Avrae embed — neither is available at narration-emission time. Texture computation therefore lives in the **matcher path** (`_handle_dm_roll_arrival`), not the writer hook. The writer hook only seeds the pending row with `actor + skill + dc`; the matcher fills in `roll_total + nat` from the Avrae event, computes texture, attaches to ResolutionResult.

This means `resolve_directive` (Ship 1's pure function) gets a new optional `scene_state` parameter for stakes computation, OR a downstream caller computes the texture and patches it onto the returned ResolutionResult. Decision §11.B.4 (surfaced below) settles which.

### §6.5 Telemetry log line

New line `llm_emit_directive_bound:` per §6.2 hook. Fires on every successful LLM-emit writer fire. Always-fire empirical-baseline discipline per Doctrine §59.

```
llm_emit_directive_bound: campaign={N} actor={name} skill={skill} dc={N|none} kind={check|save|cast} source_message_id={N}
```

Distinct from Phase 1's `directive_bound_to_footer_actor:` (which fires from `_handle_dm_roll_directive` for the DM-typed surface). Two log lines, two trigger surfaces, both feeding the same downstream matcher.

### §6.6 What the hook does NOT do

- Does NOT parse the entire response. Only scans for `!check`/`!save`/`!cast` patterns at the end of narration (per regex shape in §7).
- Does NOT compute resolution. Resolution fires later in the matcher.
- Does NOT auto-fire narration. Auto-fire fires later via `_fire_resolution_narration` on Avrae roll arrival.
- Does NOT block the post. The hook is post-post; if it fails, the narration is already in Discord and player-visible. Soft-fail discipline.

---

## §7. Narration-text directive parser

### §7.1 The regex

Distinct from Ship 1's `_DM_DIRECTIVE_RX` which assumes the directive is the WHOLE message (`^...$` anchors). LLM emissions are embedded inside narration prose, typically at the end.

```python
_LLM_EMIT_DIRECTIVE_RX = re.compile(
    r"!(?P<kind>check|save|cast)\s+(?P<skill_raw>[^\n!]+?)\s*(?=\n|$)",
    re.IGNORECASE,
)
```

Match shape:
- `!check|save|cast` — directive prefix
- `\s+` — at least one space separator
- `[^\n!]+?` — non-newline, non-`!` greedy-minimal capture of skill+optional-DC text
- `\s*(?=\n|$)` — trailing whitespace until newline or end-of-string (lookahead, doesn't consume)

The `[^\n!]` exclusion prevents the regex from spanning multiple directives if the LLM emits more than one (e.g., `!check perception !check insight` would split cleanly at the second `!`).

### §7.2 Multi-emit handling (surfaced decision §11.B.1)

If the LLM emits multiple directives (rare but possible per HARD STOP RULE 5's enforcement of one-command-per-response — the LLM may still mis-emit), spec recommendation: **take the LAST occurrence.**

```python
def _parse_llm_emit_directive(response: str) -> dict | None:
    """Find the last !check/!save/!cast directive in the response text.

    Returns {'kind': str, 'skill_raw': str} on match (post-parse_skill_and_dc
    callable on skill_raw to extract DC).

    Returns None when no directive is present.
    """
    matches = list(_LLM_EMIT_DIRECTIVE_RX.finditer(response))
    if not matches:
        return None
    m = matches[-1]
    return {
        'kind': m.group('kind').lower(),
        'skill_raw': m.group('skill_raw').strip(),
    }
```

Rationale: LLM's last emission is typically the operative one. If the LLM emits a directive mid-narration then revises at the end (rare in observation), the revision wins.

### §7.3 Edge cases

| Response text | Parser output | Notes |
|---|---|---|
| `Donovan leans closer. !check perception 15` | `kind=check, skill_raw='perception 15'` → `parse_skill_and_dc → ('perception', 15)` | Happy path |
| `Donovan leans closer. !check perception` | `kind=check, skill_raw='perception'` → `('perception', None)` | No-DC; resolution skipped per §11.2 inherited from Ship 1 |
| `Donovan leans closer. !check sleight of hand 12` | `kind=check, skill_raw='sleight of hand 12'` → `('sleight of hand', 12)` | Multi-word skill; parser_skill_and_dc handles via Ship 1 §6.2 |
| `Donovan tries! "!check perception 15".` | `kind=check, skill_raw='perception 15".'` → `parse_skill_and_dc('perception 15".')` → `('perception 15".', None)` | Quoted/punctuated emission — DC parse fails because `15".` doesn't match `\d+\s*$`. Falls through to no-DC graceful degrade. **Acceptable v1 behavior.** LLM prompt-side instructs against quoting. |
| `... !check perception 15\n!save dex 14` | `kind=save, skill_raw='dex 14'` → `('dex', 14)` | LAST emission wins; perception emit discarded |
| `Donovan succeeds!` (no directive at all) | `None` | No row written; no auto-fire. Track 7 #1 still binds on next player turn if Avrae rolls. |
| `!cast fireball 20` | `kind=cast, skill_raw='fireball 20'` → `('fireball', 20)`, but resolve_directive returns None on cast → row written, matcher skipped per §11.5 inherited from Ship 1 | Cast resolution stays v1.x |

### §7.4 Why not parse the entire response for any roll command

Avrae also accepts `!attack`, `!roll`, `!init`, `!hp`, `!coin`, etc. These are out of scope for Ship A — only `!check`/`!save`/`!cast` produce skill-check / save-shape rolls that benefit from resolution binding. Attack resolution is F-55 #5.4 territory (different binding shape — to-hit + damage instead of DC vs roll_total).

### §7.5 Composition with shipped Ship 1's bot-skip logic

The bot's own message (this very response) passes through `on_message` after Discord echoes it back. `on_message` short-circuits on `message.author.bot: return` (line 1518 in current `discord_dnd_bot.py`). So Avrae and other bots see the LLM-emitted directive; Virgil's `on_message` does NOT re-process it. Ship A's writer hook is the ONLY path that writes a pending row for the LLM emission. No double-write.

---

## §8. Difficulty-band derivation

### §8.1 Bands and boundaries (5e RAW + DM convention)

```python
def _bucket_difficulty(effective_dc: int) -> str:
    if effective_dc <= 5:    return 'trivial'
    if effective_dc <= 10:   return 'easy'
    if effective_dc <= 15:   return 'medium'
    if effective_dc <= 20:   return 'hard'
    if effective_dc <= 25:   return 'very_hard'
    return 'nearly_impossible'
```

Aligned to 5e DC bands. `effective_dc = dc - modifier`. The DM-set DC adjusted by the actor's known skill modifier gives the actual difficulty *for that actor*. DC 15 perception for a +5 perception PC is `effective_dc = 10` (easy); same DC for a +0 PC is `effective_dc = 15` (medium).

### §8.2 Edge cases

| Case | Behavior |
|---|---|
| `nat is None` (modifier unknown — happens for some save embeds per Ship 1 §5.3) | `modifier = 0` → effective_dc = raw dc. Band derived from raw DC. Slight inaccuracy but defensible. |
| Modifier > +20 (homebrew or very high-level PC) | effective_dc may go negative. Maps to `trivial` band. Correct behavior — the check is trivial for this actor. |
| Modifier negative (rare — disability, debuff, untrained skill on a low-modifier stat) | effective_dc > raw_dc. Bucket per normal. |
| DC < 5 (DM picks 0 or negative for theater per Ship 1 §6.3) | `_bucket_difficulty` returns `trivial`. The block carries the message; the LLM renders a no-effort success. |
| DC > 30 | Maps to `nearly_impossible`. No issue. |

### §8.3 Render text for each band

The AUTHORITATIVE-CANON block extends with a guidance clause per band (rendered in §10's full block shape). Locked phrasing:

- `trivial`: *"This was a trivial check. Narrate the outcome with confidence and zero friction; the actor's skill leaves no doubt."*
- `easy`: *"This was an easy check. Narrate efficient execution; minor competence on display."*
- `medium`: *"This was a medium check. Narrate appropriate effort; the outcome reflects steady skill, not chance."*
- `hard`: *"This was a hard check. Narrate visible effort or close-quarters tension; the success or failure feels earned."*
- `very_hard`: *"This was a very hard check. Narrate strain, focus, or near-impossibility; outcomes carry weight regardless of pass/fail."*
- `nearly_impossible`: *"This was a nearly-impossible check. Narrate the attempt as exceptional regardless of outcome; success is heroic, failure is honorable."*

Phrasing locked; tuning at Ship A verify checkpoint if logs show LLM ignoring or contradicting the guidance.

---

## §9. Margin-tier bucket boundaries

### §9.1 Tiers and boundaries

```python
def _bucket_margin(margin: int) -> str:
    if margin <= -10:  return 'catastrophic_fail'
    if margin <= -5:   return 'clear_fail'
    if margin <= -1:   return 'close_fail'
    if margin == 0:    return 'razor_pass'    # exact-tie = pass per Ship 1 §5.4 strict ≥
    if margin <= 9:    return 'clean_pass'
    return 'smashing_pass'
```

Boundary at 0 is locked: `razor_pass` is the single-value bucket for exact-tie passes. This matches Ship 1's `passed = (roll_total >= dc)` strict precedent and gives the LLM a dedicated texture cell for the "just barely made it" beat.

### §9.2 Render text per tier

- `catastrophic_fail` (margin ≤ −10): *"Margin ≤ −10. Narrate a substantial failure — the gap between attempt and outcome is wide; render visible cost or consequence."*
- `clear_fail` (margin −5 to −9): *"Margin −5 to −9. Narrate a clear failure; the actor knows they fell short but the gap was not catastrophic."*
- `close_fail` (margin −1 to −4): *"Margin −1 to −4. Narrate a near-miss; one detail short of success, render the moment of falling just-shy."*
- `razor_pass` (margin = 0): *"Margin = 0 (exact tie). Narrate the razor-thin quality; one moment of doubt before barely-succeeding."*
- `clean_pass` (margin +1 to +9): *"Margin +1 to +9. Narrate competent success; render control without flourish."*
- `smashing_pass` (margin ≥ +10): *"Margin ≥ +10. Narrate exceptional success; render flair, an unintended bonus detail, or a confident extra beat."*

### §9.3 Composition with difficulty band

The two tiers compose multiplicatively in narration shape, not arithmetically. Example combinations:

| Difficulty | Margin | Texture intent |
|---|---|---|
| `trivial` + `smashing_pass` | child's-play success with style — overflow flair |
| `trivial` + `razor_pass` | unusual moment of distraction; success but with a hint of "that should have been easier" |
| `hard` + `clean_pass` | competent skill against real difficulty — confident render |
| `hard` + `catastrophic_fail` | hard task + wide miss — visible cost, possible consequence |
| `nearly_impossible` + `smashing_pass` | heroic moment; render the impossibility being overcome |
| `nearly_impossible` + `catastrophic_fail` | predictable failure but with notable detail; honor the attempt |

These combinations are NOT pre-rendered as exhaustive text — the LLM renders each combination at narration time given the bound constraints. The 6×6 matrix produces 36 cells but most cells share texture (a `medium`+`clean_pass` and `hard`+`clean_pass` differ in difficulty signal only).

---

## §10. Crit-tier constraint clauses (decision §11.3 RAW preserved)

### §10.1 When crit-tier fires

Per Ship 1 §11.3 lock: nat 20 does NOT auto-PASS, nat 1 does NOT auto-FAIL. `passed` stays strictly `roll_total >= dc`. But the nat 20 / nat 1 signal is narratively load-bearing INDEPENDENT of pass/fail.

Crit-tier renders as a **separate constraint clause** in the AUTHORITATIVE-CANON block, fired by `nat == 20` or `nat == 1` regardless of `passed`. The clause is rendered ADDITIVELY — it appears alongside the difficulty + margin + pass/fail constraints, not instead of them.

### §10.2 The four cells

| `nat` | `passed` | Cell | Locked clause |
|---|---|---|---|
| 20 | True | nat-20 + PASSED (common; high modifier or low DC means a nat 20 sails through) | *"Critical signal: NAT 20. The roll was spectacular and the outcome cleared the DC. Narrate a memorable success — extra detail, a lore drop, an NPC reaction, an unintended bonus, or future-scene advantage. Render the spectacular quality of the moment."* |
| 20 | False | nat-20 + FAILED (rare but interesting; very high DC, low modifier) | *"Critical signal: NAT 20 with FAILED outcome. The roll was spectacular but the goal was beyond reach. Narrate the near-miss as memorable — the actor did everything right, the situation was just impossible. Lean into the tension between the spectacular roll and the still-thwarted attempt; render the actor's competence visible even in failure."* |
| 1 | True | nat-1 + PASSED (rare but interesting; very low DC, high modifier) | *"Critical signal: NAT 1 with PASSED outcome. The natural roll was catastrophic but the actor's skill carried them through. Narrate the graceless quality of the success — they got there, but the path was awkward, fumbled, or pure-luck. Render the success as honest but ugly; the actor noticed how close it was to going wrong."* |
| 1 | False | nat-1 + FAILED (common; low modifier or high DC compounds the nat 1) | *"Critical signal: NAT 1. The roll was catastrophic and the outcome failed. Narrate a memorable failure — comic, dramatic, or both depending on scene tone. Scene mode dictates whether the memorable beat is funny (downtime/travel — low-stakes contexts where comedy fits), grim (combat/social — high-stakes contexts where comedy breaks immersion), or either (exploration — LLM judges based on scene tone). Render bad luck visibly."* |

Tonal modulation: nat 1 fail texture is **scene-mode-dependent**. Combat mode → grim (death by comedy breaks immersion when characters are at risk). Social mode → grim (NPCs reading the failed attempt may shift stance). Downtime / travel → comic (low-stakes contexts where bad-luck humor lands). Exploration → either tone (LLM judges based on scene tone — investigation in a haunted ruin should stay grim; bantering perception check at a fair can be comic). The mode signal is in `stakes_signals['mode']` per §5.5; the render helper consults it.

### §10.3 Render integration

The crit clause appears in the block AFTER difficulty + margin + stakes lines and BEFORE the closing "Do NOT narrate {opposite outcome}" lines:

```
═══ AUTHORITATIVE ROLL RESOLUTION ═══
{Actor} attempted a {Skill} {check/save} (DC {dc}).
Roll total: {roll_total}.
Outcome: {PASSED/FAILED}.

Difficulty: {band} (effective DC {effective_dc} after actor modifier {sign-mod}).
Margin: {signed-margin} ({margin_tier}).
Stakes: {stakes_tier}.
{Critical signal: NAT 20.|Critical signal: NAT 1.|<empty>}

You MUST narrate this as a {success/failure}. {Actor} does {NOT } achieve the intended outcome.
The texture of the narration must reflect:
  - Difficulty: {one-line guidance per band, §8.3}
  - Margin: {one-line guidance per margin tier, §9.2}
  - Stakes: {one-line guidance per stakes tier, §5.2-derived}
{If crit fires: full clause from §10.2}
Do NOT narrate {opposite outcome}. Do NOT invent an alternative interpretation.
═══
```

When neither nat 20 nor nat 1 fires, the crit signal line and clause are both omitted entirely (no "Critical signal: none" placeholder — empty advisory sections lie per feedback `no_placeholder_for_advisory`).

### §10.4 Hardstop echo (bottom of HARD STOP RULES)

Unchanged from Ship 1 §7.2. The hardstop echo at HARD STOP item 8 stays the single-line `Outcome: PASSED|FAILED.` Crit-tier texture does not echo at the bottom — only the bound pass/fail. The crit constraint lives only at top-of-prompt; bottom-of-prompt is the immediate-context reinforcer of pass/fail.

---

## §11. Decision points

12 decisions pre-locked from `MULTIPLAYER_FIXES.md` v3 §12 (operator review May 11, 2026); recorded here for spec-internal cross-reference + 6 additional decisions surfaced during spec drafting.

### Pre-locked from v3 §12

For each pre-locked decision: outcome verbatim + spec §-pointer to where the implementation detail lives.

| # | v3 §12 | Outcome | Where implemented in this spec |
|---|---|---|---|
| 1 | v3 supersedes v2 | ✅ | (planning lock — no spec implementation) |
| 2 | A.1 DC source — inline `!check skill DC` | ✅ | §7.1 regex, §12 prompt-side change |
| 3 | A.2 Avrae recon — form (a) clean | ✅ | §2.1 (locked); §7.3 edge-case table for `15` ignored by Avrae |
| 4 | A.4 `compute_stakes_tier` as §59 9th sibling | ✅ | §5 in full |
| 5 | A.5 Separate `ResolutionTexture` | ✅ | §4 in full |
| 6 | A.6 Accept stale + TTL=300s | ✅ | §3.4 |
| 7 | A.8 Two-embed UX | ✅ | (operationally unchanged from Ship 1; §6.4 confirms no orchestration shift) |
| 8 | Ship 4.5 criterion shifts to Ship A verify | ✅ | §15 live-verify scenarios — multi-actor mismatch observation captured |
| 9 | Ship 5 5a (Finding J) retired | ✅ | (planning lock — Ship 5 spec inherits) |
| 10 | Corpus discipline — defer to observation | ✅ | §15 live-verify mentions; no parallel corpus drafting in this spec |
| 11 | C1 doctrine timing — wait for verify | ✅ | §16 doctrine candidates |
| 12 | Wrong-skill behavior — option (b) aside + row stays alive | ✅ | §13 in full |

### Surfaced during spec drafting

Six new decisions raised by the drafting process. Each gets full Ship-1-shape treatment: trade-offs, recommendation, confidence, surfaced additions, cross-references.

---

### §11.B.1 — Multi-emit parser behavior (last-match vs first-match)

**Question:** If the LLM emits more than one `!check`/`!save`/`!cast` directive in a single response (rare but possible despite HARD STOP RULE 5's enforcement), which one does the writer hook bind?

**Options:**
- (a) First match
- (b) Last match
- (c) All matches (write multiple rows — conflicts with single-row-per-campaign invariant)
- (d) Error out (refuse to write any row)

**Spec recommendation:** **(b) last match.**

**Trade-offs:**
- (a) First-match could pick up an early directive the LLM later revised in narration. Less likely to match operator intent.
- (b) Last-match treats the LLM's final emission as the operative one. Matches HARD STOP RULE 1's "your reply MUST end with the roll request" framing.
- (c) Multi-row breaks Ship 1's `campaign_id INTEGER PRIMARY KEY` single-row invariant. Rejected.
- (d) Refuse-to-write produces a silent no-fire; operator gets the Track 7 #1 path on next turn. Acceptable degradation but worse UX than (b).

**Recommendation:** Lock **(b)**. Implementation in `_parse_llm_emit_directive` per §7.2.

**Confidence:** HIGH. Multi-emit is rare; last-match matches the prompt-side framing.

**Surfaced addition:** Log line `llm_emit_multi_directive_count: campaign={N} count={N}` fires when `len(matches) > 1`. Empirical-baseline observability; tune prompt or refine parser if rate is meaningful.

**Related:** §7.2 implementation; §11.B.5 below (multi-emit when only some have DCs).

---

### §11.B.2 — Texture computation surface (matcher vs resolve_directive)

**Question:** Where does `compute_resolution_texture` get called — in the matcher (`_handle_dm_roll_arrival`) or inside the existing `resolve_directive` pure function?

**Options:**
- (a) Inside `resolve_directive` — pass scene_state + active_turn + active_quests + combatants as new optional kwargs; resolve_directive returns ResolutionResult with non-None `texture`
- (b) In the matcher — matcher calls `resolve_directive` (unchanged) to get the core ResolutionResult, then calls `compute_resolution_texture` separately, then patches `texture` onto the result (requires removing `frozen=True` or using `dataclasses.replace`)
- (c) In `_dm_respond_and_post`'s scheduled coroutine — the auto-fire path computes texture from scene state at fire time, not at resolve time

**Spec recommendation:** **(a) inside resolve_directive, new optional kwargs.** Texture is constructed at ResolutionResult instantiation time inside `resolve_directive`. ResolutionResult stays `frozen=True`; `dataclasses.replace` is unnecessary and rejected — texture is computed before the instance is created, not patched after.

**Trade-offs:**
- (a) keeps texture co-located with resolution; one function call surface. Caller provides scene_state; texture computed inline before ResolutionResult instantiation.
- (b) preserves resolve_directive's existing signature but requires un-freezing OR `replace()`-shaped reconstruction. Both are rejected — un-freezing breaks Ship 1's immutability discipline; `replace()` adds construction-time complexity for no benefit since texture is known at consume time.
- (c) defers texture to fire-time — texture reflects scene state AT FIRE TIME, not at consume time. Possible race: scene state changes between consume (matcher) and fire (auto-fire coroutine, ~6s later). Unlikely (operator rarely changes scene mid-roll) but a real timing surface.

**Recommendation:** Lock **(a)**. Texture computed at consume time (in matcher → resolve_directive → assembled ResolutionResult); scene_state read once, frozen into texture, rendered downstream. Implementation: extend `resolve_directive` signature with `scene_state`, `active_turn`, `active_quests`, `combatants` as optional kwargs (default None); when supplied AND `dc is not None`, compute texture and embed in the returned ResolutionResult.

**Confidence:** HIGH. Texture-at-consume matches the engine-bound discipline (state at the moment the roll is resolved is the canonical state).

**Surfaced addition:** Ship 1's `resolve_directive(directive_row, avrae_event)` signature is preserved as-is (no required-kwarg break). Texture-aware callers (Ship A's matcher) pass the optional kwargs; texture-unaware callers (Ship 1's existing tests, hypothetical future callers) get `texture=None`.

**Related:** §4.2 ResolutionResult extension; §5.6 compute_resolution_texture helper signature.

---

### §11.B.3 — DC band reference table location (prompt-side)

**Question:** Where does the LLM see guidance on which DC to emit for a roll?

**Options:**
- (a) Inside the ROLL DIRECTIVE block (`RollDecision.to_prompt_directive` output extension)
- (b) Inside HARD STOP RULE 1 as part of the DC-inclusion mandate
- (c) Inside dm_philosophy.md (separate prompt-tuning surface)
- (d) Recommended-DC value pre-computed by orchestration and surfaced inline (`Recommended DC: 15 (medium)`)

**Spec recommendation:** **(a)** ROLL DIRECTIVE block extension, no recommended-DC pre-computation.

**Trade-offs:**
- (a) Co-locates the guidance with the roll directive; LLM sees the band table immediately above the `!check skill <DC>` template. Single read-and-pick flow.
- (b) HARD STOP RULES are "obey absolutely" framing; embedding a DC selection guide there over-emphasizes the choice as a hard rule.
- (c) dm_philosophy.md is too far from the directive emission surface; the LLM may not consult it at every roll-required turn.
- (d) Recommended-DC adds engine authority over a decision Ship A locks to the LLM (per A.1). Risks shifting decision authority back; v1.x candidate if logs show LLM picking systematically bad DCs.

**Recommendation:** Lock **(a)**. Extend `RollDecision.to_prompt_directive`'s skill/save branches to append a band reference:

```
ROLL DECISION: Perception check required (medium). End your message asking the player to roll: `!check perception <DC>`. Reason: Investigating non-obvious detail.

DC GUIDANCE: pick a DC from the 5e RAW bands:
  5  = trivial (the actor would succeed on instinct)
  10 = easy (routine for a competent character)
  15 = medium (real friction, default for most uncertain attempts)
  20 = hard (visible effort or skill required)
  25 = very hard (extraordinary attempt; only experts succeed)
  30 = nearly impossible (heroic stakes; success is rare)
The DC is what the engine binds the outcome to. The narration after the roll is auto-generated bound to the rolled value vs the DC you picked.
```

**Confidence:** HIGH. Co-located guidance is the natural placement.

**Surfaced addition:** The band guidance is rendered ONLY when `RollDecision.needs_roll == True` AND the category is skill or save (NOT attack — attacks don't have DCs). Attack branch's existing template stays unchanged per Ship A's §17 out-of-scope (cast resolution is v1.x; attack resolution is F-55 #5.4).

**Related:** §12 HARD STOP RULE 1 extension; §17.1 cast out-of-scope.

---

### §11.B.4 — Stakes-tier inputs scope

**Question:** Which scene_state fields does `compute_stakes_tier` read?

**Options:**
- (a) Minimal: mode + tension only
- (b) Recommended: mode + tension + urgent_clocks + recent_commitment + combat_active (the §5.2 scoring shape)
- (c) Expanded: above + active quests + NPCs in scope + last DM response keywords (more input → richer stakes signal but more state-coupling)

**Spec recommendation:** **(b) recommended scope per §5.2.**

**Trade-offs:**
- (a) misses the commitment/combat/clock signals that distinguish high-stakes from medium-stakes moments. Under-segments.
- (b) covers the five most meaningful axes. Engine-bound. Tunable bucket thresholds.
- (c) couples stakes to active_quests + NPC scope + LLM-touched fields (last_dm_response). Last-DM-response is LLM-authored — including it imports the recursive-hallucination loop §76 candidate into stakes. Rejected.

**Recommendation:** Lock **(b)** verbatim per §5.2 scoring shape.

**Confidence:** HIGH. The five axes are all engine-bound state; tuning happens at bucket thresholds, not at axis inclusion.

**Surfaced addition:** If Ship A verify shows stakes tier producing systematically wrong signals (e.g., medium-tier scenes feeling more like high-tier), tune the bucket thresholds (`score >= 4 → high`, `score >= 2 → medium`) rather than adding new axes. Axis count stays at 5; threshold tuning is the v1.x dial.

**Related:** §5.2 scoring shape; §5.5 stakes_tier_log_summary for tuning telemetry.

---

### §11.B.5 — Mixed-DC multi-emit (LLM emits multiple directives, only some with DCs)

**Question:** What if the LLM emits `!check perception 15` AND `!save dex` in the same response (one has DC, one doesn't)?

**Spec recommendation:** Last-match per §11.B.1 applies — whichever directive is last is the operative one. If the last is no-DC, the no-DC path fires (resolution skipped, §11.2 inherited from Ship 1). If the last is DC, the texture path fires.

**Trade-offs:** Combining both directives into multiple pending rows is rejected per §11.B.1(c) — single-row invariant holds.

**Recommendation:** Lock last-match per §11.B.1.

**Confidence:** HIGH.

**Related:** §11.B.1; §6 writer hook log line.

---

### §11.B.6 — Spec-location convention

**Question:** Where does this spec live on the server? Most existing specs are in `/home/jordaneal/virgil-docs/specs/`; two recent specs (`RESOLUTION_BINDING_SPEC.md`, `BUG_1_SPEC.md`) landed flat at `/home/jordaneal/virgil-docs/`.

**Spec recommendation:** **`/home/jordaneal/virgil-docs/specs/LLM_EMIT_RESOLUTION_BINDING_SPEC.md`** per dominant convention + operator instruction.

**Trade-offs:** Flat location matches RESOLUTION_BINDING_SPEC.md's pattern but is the outlier (2 of ~19 specs). specs/ subdir matches the dominant convention (17 of ~19).

**Recommendation:** Lock specs/. Surface as v1.x housekeeping: should RESOLUTION_BINDING_SPEC.md + BUG_1_SPEC.md move into specs/ for consistency? Low-risk doc move; no code references break (cross-references in SESSIONS / ROADMAP cite filename only, not path).

**Confidence:** HIGH for new spec location; MEDIUM-confidence v1.x recommendation for consolidating existing flat specs into specs/.

**Surfaced addition:** v1.x housekeeping candidate (low priority): move `RESOLUTION_BINDING_SPEC.md` + `BUG_1_SPEC.md` from flat `/home/jordaneal/virgil-docs/` to `/home/jordaneal/virgil-docs/specs/` per dominant convention. **Defer indefinitely** unless a future ship requires consistent spec path discovery (e.g., a `/spec-load` slash command or a doc-search tool that assumes specs/ as root). Cosmetic-only; not a v1.x ticket worth scheduling.

**Related:** Operator instruction in S35 prompt; review §3.B.6 framing revision.

---

## §12. Prompt-side HARD STOP RULE extension

### §12.1 The change

Current HARD STOP RULE 1 (verbatim per recon `dnd_engine.py:5361`):

> "1. If the ROLL DIRECTIVE above said a specific roll is required, your reply MUST end with the roll request and NOTHING ELSE. Do not narrate the outcome. Do not describe the chest opening. Do not invent loot. STOP after the roll request."

Ship A extends with one sentence appended:

> "1. If the ROLL DIRECTIVE above said a specific roll is required, your reply MUST end with the roll request and NOTHING ELSE. Do not narrate the outcome. Do not describe the chest opening. Do not invent loot. STOP after the roll request. **The roll request MUST include a DC: `!check <skill> <DC>` or `!save <stat> <DC>` (e.g. `!check perception 15`, `!save dex 12`). The DC is what the engine binds the outcome to; choose from the 5e DC bands listed in the ROLL DIRECTIVE block. A roll request without a DC falls through to a free-narration flow on the next turn instead of an immediate bound outcome.**"

HARD STOP RULE 5 (the `!`-prefix scope rule) stays unchanged — Ship A's extension lives in RULE 1 because RULE 1 already governs roll-request shape; RULE 5 governs which `!`-commands may appear at all.

### §12.2 ROLL DIRECTIVE block extension

`RollDecision.to_prompt_directive`'s skill/save branches gain the DC placeholder + band reference per §11.B.3:

```python
# Skill branch (current):
return (
    f"ROLL DECISION: {label} required ({self.severity}). "
    f"End your message asking the player to roll: `{cmd}`. "
    f"Reason: {self.reason}"
)
# Skill branch (Ship A extension):
return (
    f"ROLL DECISION: {label} required ({self.severity}). "
    f"End your message asking the player to roll: `{cmd} <DC>`. "
    f"Reason: {self.reason}\n\n"
    f"DC GUIDANCE: pick a DC from the 5e RAW bands:\n"
    f"  5  = trivial (the actor would succeed on instinct)\n"
    f"  10 = easy (routine for a competent character)\n"
    f"  15 = medium (real friction, default for most uncertain attempts)\n"
    f"  20 = hard (visible effort or skill required)\n"
    f"  25 = very hard (extraordinary attempt; only experts succeed)\n"
    f"  30 = nearly impossible (heroic stakes; success is rare)\n"
    f"The DC is what the engine binds the outcome to. The narration after "
    f"the roll is auto-generated bound to the rolled value vs the DC you "
    f"picked."
)
```

Save branch gets the same extension with `!save <stat>` template. Attack branch unchanged (no DC; attack resolution is F-55 #5.4).

### §12.3 Why HARD STOP RULE 1 and not RULE 5

RULE 5 ("NO UNAUTHORIZED MECHANICAL COMMANDS") governs WHICH `!`-commands the LLM may emit. RULE 1 governs the SHAPE of the roll request when one is required. The DC inclusion is about shape, not authorization — RULE 1 is the natural home.

### §12.4 Phrasing rationale

The "falls through to a free-narration flow" tail clause is intentional: it tells the LLM that omitting the DC is not catastrophic, just less-bound. This avoids the LLM panicking about DC choice and emitting bad DCs to comply with a "mandatory" instruction. Per `feedback_compounding_leverage`: the band guidance + "DC is binding" + "no-DC degrades gracefully" framing gives the LLM a confident-but-not-pressured stance toward DC selection.

---

## §13. Wrong-skill aside helper (decision 12 lock)

### §13.1 Current matcher behavior (Ship 1 + Bug 1 Phase 1)

```python
# discord_dnd_bot.py:_handle_dm_roll_arrival current behavior:
avrae_skill = _normalize_skill_for_match(event.get('detail') or '')
pending_skill = _normalize_skill_for_match(pending.get('check_type') or '')
if not avrae_skill or not pending_skill or avrae_skill != pending_skill:
    # Skill mismatch (any actor) → silent ignore per spec.
    return out
```

Skill mismatch silent-ignores. Ship A changes this branch to log + aside + leave row alive.

### §13.2 Ship A extension

```python
# Skill mismatch → log + aside, do NOT consume.
log(f"directive_skill_mismatch: campaign={campaign_id} "
    f"expected_skill={pending.get('check_type', '')} "
    f"actual_skill={event.get('detail', '')} "
    f"actor={event.get('actor', '')}")
out['aside'] = _wrong_skill_aside(
    expected_skill=pending.get('check_type', ''),
    actual_skill=event.get('detail', ''),
)
return out
```

Pending row stays alive (no `pending_directive_consume` call); wrong-skill roll falls through to normal player-input buffer per Track 7 #1.

### §13.3 Aside helper

```python
def _wrong_skill_aside(expected_skill: str, actual_skill: str) -> str:
    return (
        f"Roll directive bound to {expected_skill} — "
        f"that {actual_skill} roll is not consumed. "
        f"Wait for a {expected_skill} roll, or revise the directive."
    )
```

Analog to `_wrong_actor_aside` (Bug 1 §K shipped Ship 1). Posted to `#dm-aside` via `_post_dm_aside`. Soft-fail per existing aside-post discipline.

### §13.4 Why option (b) and not silent

Per locked decision 12: silent-ignore (a) leaves operator confused with no signal; auto-fire-against-wrong-skill (c) violates the DM/LLM's skill choice; aside (b) surfaces the mismatch without overriding. Operator decides whether to roll the right skill or cancel the directive (edit-message cancel path) or wait for TTL.

### §13.5 What does NOT change

- Wrong-actor branch (existing `_wrong_actor_aside` from Bug 1 §K) unchanged.
- Skill alias map remains v1.x candidate per Ship 1 §11.10 + §15.5. Ship A inherits — `_normalize_skill_for_match` stays whitespace + case normalization only.
- Same-skill same-actor match unchanged — fires the existing resolution path.

### §13.6 Telemetry

New log line `directive_skill_mismatch:` per §13.2. Always-fire on every skill mismatch event. Distinct from existing `directive_actor_mismatch:` (skill matches, actor doesn't).

---

## §14. Test plan

Target: ~25–30 new assertions across 2 new + 2 extended test files. Aligns with v3 §4.6.

### §14.1 New file: `test_compute_stakes_tier.py`

Pure-function tests against `compute_stakes_tier`.

**~10 assertions:**

1. `compute_stakes_tier(None)` returns `('low', signals)` (no scene state → low)
2. Empty scene_state returns 'low'
3. Combat mode alone returns 'medium' (score=2)
4. Exploration mode + tension 75 returns 'medium' (score=2)
5. Combat mode + tension 75 returns 'high' (score=4)
6. Downtime mode returns 'low' (score=-1)
7. Urgent clock alone in exploration returns 'low' (score=1)
8. Recent commitment + tension 50 + combat returns 'high' (score=4: 2+1+1)
9. `stakes_tier_log_summary` produces `stakes_tier: tier={X} mode={M} ...` shape
10. Mode classification handles unknown mode strings without raising

### §14.2 New file: `test_llm_emit_writer.py`

Parser regex + writer hook composition tests.

**~12 assertions:**

1. `_parse_llm_emit_directive("text\n!check perception 15")` returns `{kind: 'check', skill_raw: 'perception 15'}`
2. `_parse_llm_emit_directive("text")` returns None (no directive)
3. `_parse_llm_emit_directive("!check perception\n")` returns `{kind: 'check', skill_raw: 'perception'}` (no DC)
4. Multi-emit returns LAST match per §11.B.1 (`"!check x 10\n!save y 12"` → `{kind: 'save', skill_raw: 'y 12'}`)
5. Multi-word skill (`!check sleight of hand 12`) parses cleanly
6. Punctuated emission (`!check perception 15.`) parses skill_raw including trailing punct → `parse_skill_and_dc` falls through to no-DC
7. Multiple `!check` mid-sentence does not break the regex (Avrae would still see only the last; parser confirms)
8. Empty response string returns None
9. `parse_skill_and_dc('perception 15')` returns `('perception', 15)` (regression — Ship 1 helper)
10. `parse_skill_and_dc('sleight of hand 12')` returns `('sleight of hand', 12)` (regression)
11. End-to-end: parser output + parse_skill_and_dc + pending_directive_upsert produces a row with `dc=15` (uses in-memory test DB per Ship 1's test pattern)
12. Cast-kind directive (`!cast fireball 14`) writes a row but `resolve_directive` returns None (regression — Ship 1 §11.5 inheritance)

### §14.3 Extension: `test_resolve_directive.py`

Existing 19 assertions + new texture-aware assertions.

**~6 new assertions (25 total):**

1. `resolve_directive` with `scene_state=None` returns ResolutionResult with `texture=None` (Ship 1 backwards compat)
2. `resolve_directive` with full kwargs returns ResolutionResult with non-None `texture` (ResolutionTexture instance)
3. `texture.difficulty_band` derived from effective_dc per §8 boundaries (parametrize across band boundaries)
4. `texture.margin_tier` derived from margin per §9 boundaries (parametrize including margin=0 → razor_pass)
5. `texture.stakes_tier` propagates from compute_stakes_tier output
6. `ResolutionTexture` is immutable (frozen=True; mutation raises)

### §14.4 Extension: `test_pending_roll_directives.py`

Existing 25 assertions + new writer-source-message-id assertions.

**~2 new assertions (27 total):**

1. `pending_directive_upsert(... source_message_id='bot-msg-id-1', dc=15)` writes a row with `dc=15` retrievable via `get_active` (regression with new Ship A trigger source)
2. Two upserts from disjoint trigger surfaces (simulated: one with `source_message_id='human-msg-id'`, one with `source_message_id='bot-msg-id'`) produce `pending_directive_replaced` log on the second (verifies both Ship 1 + Ship A surfaces share the helper)

### §14.5 Extension: `test_narration_verifier.py`

Regression that ROLL_OUTCOME_DRIFT still fires correctly when ResolutionResult carries texture.

**~3 new assertions (47 total):**

1. ROLL_OUTCOME_DRIFT fires on success-phrase + texture-bearing FAILED ResolutionResult (verifies texture doesn't accidentally suppress drift detection)
2. ROLL_OUTCOME_DRIFT does NOT fire on aligned narration with texture-bearing PASSED ResolutionResult (regression)
3. `build_escalation_placeholder` with ROLL_OUTCOME_DRIFT class + texture-bearing result renders the deterministic block per Ship 1 §8.7 (regression — extension should still produce the simple block; texture lines optional in escalation)

### §14.6 Total assertion count

| File | New | Existing | Total |
|---|---|---|---|
| `test_compute_stakes_tier.py` | 10 | 0 | 10 |
| `test_llm_emit_writer.py` | 12 | 0 | 12 |
| `test_resolve_directive.py` | 6 | 19 | 25 |
| `test_pending_roll_directives.py` | 2 | 25 | 27 |
| `test_narration_verifier.py` | 3 | 44 | 47 |

**~33 new assertions across 2 new + 3 extended files.** Matches v3 §4.6's ~25 estimate within rounding (extra ones surfaced during plan).

---

## §15. Live-verify scenarios

Walks in `#dm-narration` on campaign 22 (or fresh test campaign). Verifies the primary play loop (LLM-emitted-directive → Avrae roll → bot auto-fires textured outcome). Solo-operator runnable per the Ship 1 verify discipline; Scenario F-equivalent (multi-actor) deferred to multiplayer per `MULTIPLAYER_VERIFY_DEFERRED.md`.

### §15.1 Test campaign setup

Use campaign 22 ("T&J") or a fresh test campaign. One bound caster (for §15.6 nat-tier observation, if available) is nice-to-have but not required for the load-bearing scenarios.

Pre-flight: `/play` to open. Confirm scene mode is `exploration` (Ship A inherits combat-mode skip from Ship 1 §15.3).

### §15.2 Scenario A1 — LLM-emitted PASSED resolution (primary loop)

**Steps:**

| # | Step | Input |
|---|---|---|
| 1 | Operator types intent in #dm-narration | `I take a closer look at the room.` |
| 2 | Bot narrates response + emits `!check perception <DC>` at end | (LLM picks DC; expect DC 10–15 for "closer look" intent) |
| 3 | Avrae rolls perception | (auto, in response to bot's `!check perception N`) |
| 4 | If `roll_total >= dc`: bot auto-fires textured outcome within ~6s | (bot's second embed shows success narration with margin/difficulty/stakes texture) |

**Greps:**

```bash
# Step 2 should produce:
journalctl --user -u virgil-discord --since "5 minutes ago" | grep "llm_emit_directive_bound:" | tail -1
# Expect: actor=Donovan Ruby skill=perception dc=<N> kind=check source_message_id=<bot-msg-id>

# Steps 3-4 should produce:
journalctl --user -u virgil-discord --since "5 minutes ago" | grep "directive_resolved:" | tail -1
# Expect: outcome=PASSED with full resolution shape

# Step 4 should produce:
journalctl --user -u virgil-discord --since "5 minutes ago" | grep "stakes_tier:" | tail -1
# Expect: tier=low|medium|high with score breakdown

journalctl --user -u virgil-discord --since "5 minutes ago" | grep "verification:" | tail -1
# Expect: passed=1 violation_class=none
```

**Expected narration shape:** Bot's second embed describes Donovan succeeding at perception with texture appropriate to difficulty + margin + stakes. Difficulty=medium + margin=clean_pass + stakes=low → competent execution, no flair. Difficulty=hard + margin=smashing_pass + stakes=high → exceptional success with extra detail.

### §15.3 Scenario A2 — LLM-emitted FAILED resolution

Same intent shape, but bot picks a DC the operator's modifier can't reliably hit (e.g., `I try to disarm the trap` → LLM picks DC 20 for hard).

**Steps:** Same as A1, but expect `roll_total < dc`.

**Expected:** Bot narrates failure honoring binding. Texture should reflect difficulty (hard → visible effort) + margin (e.g., close_fail → near-miss) + stakes.

**Greps:** Same as A1 but `outcome=FAILED`; verification line should show `violation_class=none` (no drift).

### §15.4 Scenario B — No-DC LLM emission (graceful degrade per Ship 1 §11.2)

If the LLM mis-emits `!check perception` without a DC:

**Greps:**

```bash
journalctl --user -u virgil-discord --since "5 minutes ago" | grep "llm_emit_directive_bound:" | grep "dc=none" | tail -1
# Expect: row written with dc=none

journalctl --user -u virgil-discord --since "5 minutes ago" | grep "directive_resolution_skipped:" | grep "reason=no_dc" | tail -1
# Expect: skip line fires
```

**Expected behavior:** No bot auto-fire on the Avrae roll. Existing Track 7 #1 path fires on next player turn. **This is acceptable v1 behavior** but expected to be RARE in natural play (prompt-side instruction should produce DC in >95% of emissions). If logs show high no-DC rate, surface for prompt tuning.

### §15.5 Scenario C — Wrong-skill aside (decision 12)

LLM emits `!check perception 15`; operator manually types `!check insight` instead (rare but possible — operator absent-minded or wants to roll something different):

**Greps:**

```bash
journalctl --user -u virgil-discord --since "5 minutes ago" | grep "directive_skill_mismatch:" | tail -1
# Expect: expected_skill=perception actual_skill=insight actor=...
```

**Expected:** Wrong-skill aside posts to `#dm-aside` with copy template per §13.3. Pending row stays alive; operator can roll perception next to consume it OR wait for TTL.

### §15.6 Scenario D — Nat-20 / Nat-1 texture (deferred until natural play surfaces)

Nat-20 and nat-1 are rare (~5% each of d20 rolls × frequency-of-PASSED-vs-FAILED). Live-verify cannot reliably force these in a short window. Defer empirical observation to natural play. When a nat-20 or nat-1 fires during Ship A use:

**Greps:**

```bash
# Nat-20 case:
journalctl --user -u virgil-discord --since "1 hour ago" | grep "directive_resolved:" | grep "nat=20" | tail -1
# Expect: Critical signal: NAT 20 line in the rendered block (verify by reading the bot's narration response)

# Nat-1 case:
journalctl --user -u virgil-discord --since "1 hour ago" | grep "directive_resolved:" | grep "nat=1 " | tail -1
# Expect: Critical signal: NAT 1 line + scene-mode-appropriate texture (grim if combat, comic if exploration/downtime)
```

If during natural Ship A play, a nat-20-FAILED or nat-1-PASSED cell surfaces, the operator should screenshot the bot's narration to confirm the texture clauses landed cleanly — those are the two most narratively interesting cells per §10.2.

### §15.7 Scenario E — High-stakes texture

Set up a high-stakes context: enter combat mode (`!init begin`), have a tension level above 70, with at least one urgent clock. Then trigger a check.

**Greps:**

```bash
journalctl --user -u virgil-discord --since "5 minutes ago" | grep "stakes_tier:" | grep "tier=high" | tail -1
# Expect: high tier with score breakdown showing combat + tension + urgent_clock contributions

journalctl --user -u virgil-discord --since "5 minutes ago" | grep "directive_resolved:" | tail -1
# Expect: resolution fires; narration should reflect high stakes (weighty tone, visible consequence)
```

### §15.8 Scenario F — Composition with Ship 1 (DM-typed directive still works)

Verify that Ship A's writer doesn't break Ship 1's path. Operator types `!check perception 10` directly:

**Greps:**

```bash
journalctl --user -u virgil-discord --since "5 minutes ago" | grep "directive_bound_to_footer_actor:" | tail -1
# Expect: Ship 1's writer fires (NOT llm_emit_directive_bound)

journalctl --user -u virgil-discord --since "5 minutes ago" | grep "directive_resolved:" | tail -1
# Expect: resolution fires per Ship 1 path with texture (Ship A's matcher-side texture computation applies to BOTH writers' rows)
```

**Important:** Ship 1's writer doesn't produce LLM-emit hook fire. But the matcher computes texture for BOTH surfaces' rows when scene state is available. Ship 1's resolutions get textured rendering retroactively as a side effect of Ship A landing.

### §15.9 Aggregate verify criteria (mirrors Ship 1 §13.9 + Ship A additions)

After running scenarios A1, A2, C, F across one session (target: 5+ LLM-emit resolutions across mixed pass/fail):

1. `llm_emit_directive_bound:` count ≥ 3 (per Ship A gate criteria, v3 §4.7 "≥3 LLM-emitted resolutions across a session, mixed pass/fail")
2. `violation_class=roll_outcome_drift` with `retry_passed=0|-` count = 0 (criterion 5 from Ship 1, unchanged)
3. `unexpected_binding_co_occurrence:` count = 0 (§2.3 defensive canary)
4. `_dm_respond_and_post_failure:` count = 0 (auto-fire reliability)
5. `directive_skill_mismatch:` count observable (Scenario C target ≥ 1 if walked)
6. `stakes_tier:` distribution observable across low/medium/high cells (calibration data)

**Texture-cell coverage check (qualitative):** at least one resolution should fire in each of the 6 difficulty bands × 6 margin tiers × 3 stakes tiers as natural play surfaces them. Full 108-cell coverage is unrealistic in one session; **aim for ≥ 5 distinct cells observed**, with priority on the high-stakes and crit-tier cells for narrative texture confirmation.

### §15.10 Ship 4.5 calibration data (decision 8)

Per locked decision 8, Ship 4.5's slot decision criterion shifts to **Ship A verify checkpoint**. During Ship A verify, count any multi-actor batched turns that produced directive-binding ambiguity:

```bash
# Multi-actor batched turn count (footer shows ≥2 actors):
journalctl --user -u virgil-discord --since "today" | grep "state_footer:" | grep -E "actor_names_canonical=\[.+,.+\]" | wc -l

# Cross-reference with directive_actor_mismatch events:
journalctl --user -u virgil-discord --since "today" | grep -c "directive_actor_mismatch:"
```

**Criterion:** >1 multi-actor directive-binding ambiguity per session in **natural play** → Ship 4.5 slots. ≤1 → file v1.x per §7B.3 lock. Sock-puppet F walks don't count.

### §15.11 Populates `tests-to-run-post-session.md`

After Ship A lands and verify passes, append a new section to `tests-to-run-post-session.md` with the scenarios A1/A2/B/C/D/E/F structure, including the greps. Use the same shape as Ship 1's appended section (already in tests-to-run-post-session.md per S34 doc-update).

---

## §16. Doctrine candidates filed (do NOT anchor mid-flight per decision 11)

Per Doctrine §59, candidates surface during ship work but anchor only after the proving ship lands cleanly. Decision 11 explicitly defers C1 promotion to post-Ship-A-verify — don't pre-commit to anchoring during spec drafting.

### §16.1 — C1: Engine-computed binding > validator-on-LLM-output

**Wording (per `DOCTRINE.md` Candidates section C1):** *"When an LLM-output failure mode can be closed by engine-computing the bound outcome and rendering it as a top-of-prompt constraint (rather than validating the LLM's output after the fact), the engine-computed path is structurally stronger."*

**Project instances if Ship A ships clean:**
1. Track 7 #1 CHECK_ACTION binding (S25 #4)
2. Ship 1 Resolution Binding on DM-typed surface (S34)
3. **Ship A Resolution Binding on LLM-emitted surface (this ship)** — third instance

Three instances clears the §59 anchoring bar. **Decision 11 lock: wait for Ship A verify to confirm the shape holds across all three instances before anchoring.** Promotion timing — post-verify, post-doc-update pass.

### §16.2 — C2: Reused vocabulary across sibling verifier classes

**Wording (per `DOCTRINE.md` Candidates C2):** *"When two violation classes in `narration_verifier` detect the same linguistic surface (LLM uses success/failure phrasing) but against different binding objects (adjudicator vs. resolver vs. future binding surfaces), reuse the vocabulary tables rather than fork them."*

**Project instances:**
1. Ship 1 ROLL_OUTCOME_DRIFT reuses VERDICT_CONTRADICTION's `_CHECK_FAILURE_SUCCESS_PHRASES` / `_CHECK_SUCCESS_FAILURE_PHRASES`

Ship A does NOT add new verifier classes. The crit-tier render adds constraint clauses but does NOT add new detection vocabulary. **C2 stays at one instance after Ship A; reassess when F-55 #5.4's attack-resolution verifier class lands (if it surfaces).**

### §16.3 — Surfaced this spec: "Single-writer compatible with multiple trigger surfaces"

**Candidate phrasing:** *"When a §17 single-writer field has two or more disjoint trigger surfaces, consolidate via one writer-helper rather than fork the field. The helper is the single writer; the triggers are surfaces invoking it. Disjoint-trigger compatibility preserves §17 status."*

**Project instances if Ship A ships clean:**
1. Ship A — `dnd_pending_roll_directives.dc` written by both `_handle_dm_roll_directive` (human DM trigger) and the new `_dm_respond_and_post` hook (LLM-emit trigger), both calling `pending_directive_upsert`.

One instance. **File as candidate; do NOT anchor.** Anchor when second instance surfaces (likely candidates: F-55 #5.4's intent-resolution writer surfaces, Ship 2's scene_state writers post-canon-discipline, or any future ship that adds a second trigger to an existing single-writer field.)

**Cross-references:** §17 (single write paths) — sibling principle; this candidate operates one layer below ("when do you need to fork the writer vs. just add a trigger?").

### §16.4 — Spec discipline observation (not a doctrine candidate yet, but worth recording)

Ship A's spec re-used Ship 1's primitives extensively — `ResolutionResult`, `resolve_directive`, render helpers, ROLL_OUTCOME_DRIFT, AUTHORITATIVE-CANON block, `_fire_resolution_narration`, `pending_directive_upsert`. The cost-per-additional-shape was small (~350 LOC for a second primary-surface closure) because Ship 1 specced the primitives generically rather than tied them to the DM-typed trigger.

**Observation worth flagging in S35b review:** the spec-then-review-then-ship discipline at Ship 1 produced primitives that compose at the right granularity. If F-55 #5.4 (Intent-to-Avrae Resolver) inherits the same pattern, it should consume Ship A's `ResolutionTexture` template for attack/cast resolution texture — third reuse instance, strengthens C1 + the "primitives compose" architectural lineage.

---

## §17. Out of scope

Per `MULTIPLAYER_FIXES.md` v3 §4.8 + Ship 1 §15. Spec confirms each.

### §17.1 Cast directive resolution

Cast resolution requires target-side save adjudication. `resolve_directive` returns None on `kind='cast'` per Ship 1 §11.5; Ship A inherits. LLM emissions of `!cast fireball 14` produce a row with `dc=14` but the matcher's `resolve_directive` returns None and the matcher logs `directive_resolution_skipped: reason=cast_kind`. **Cast resolution stays v1.x candidate "Cast Resolution Binding"** for a future ship.

### §17.2 Player-typed `!check` flow (without DM directive)

Player rolling `!check perception` directly (no DM/LLM-emitted directive preceding) is the normal Avrae roll surface; per RESOLUTION_BINDING_SPEC.md §15.2 it doesn't enter the matcher path. Ship A inherits. Track 7 #1's CHECK_ACTION binding catches this surface on the next player turn via adjudicator's `consume_recent_check`.

### §17.3 Combat-mode rolls

Phase 1 skips directive creation in combat mode (BUG_1_SPEC.md §F.1 gate 2). No `dnd_pending_roll_directives` row exists for combat-mode `!check`/`!save`. Both writer surfaces (Ship 1 and Ship A) inherit this gate — Ship A's LLM-emit hook does NOT write a row in combat mode (gate check at hook entry). Combat-mode resolution is filed v1.x per v3 §4.8.

### §17.4 F-58 (stale-footer name parsing)

F-58 stays a v1.1 candidate per Ship 1 §15.4.

### §17.5 Skill alias map (sneak ↔ stealth, etc.)

Ship 1 §11.10 + §15.5 deferral inherited. Skill normalization stays `_normalize_skill_for_match` (lowercase + whitespace coalesce). Wrong-skill aside per §13 surfaces alias-shaped friction; if observed rate is meaningful, file alias-map ship in v1.x.

### §17.6 Multi-actor temporal state (Ship 4.5)

Filed candidate per `MULTIPLAYER_FIXES.md` v3 §7B. Decision criterion shifted to Ship A verify checkpoint per locked decision 8. Ship A itself does NOT change multi-actor binding behavior; the §15.10 calibration data drives the slot decision.

### §17.7 Debounce / rapid-fire coalescing

Per Ship 1 §11.14 + v3 §4.8, no debounce in v1. Ship A inherits — if Ship A's auto-fire produces meaningful rapid-fire issues (multiple LLM-emits in quick succession + Avrae rolling all of them quickly + matcher firing multiple auto-fires within 30s), file debounce as v1.x.

### §17.8 Per-skill `intended outcome` phrasing

Per Ship 1 §7.5, AUTHORITATIVE-CANON block uses generic "does not achieve the intended outcome" phrasing rather than per-skill outcome map. Ship A inherits. Per-skill mapping is a Doctrine §26-shaped exception list; stays out of scope.

### §17.9 Texture vocabulary tuning

Difficulty + margin guidance text (§8.3, §9.2, §10.2) is locked in v1. Tuning at Ship A verify checkpoint if logs show LLM ignoring or contradicting guidance. Corpus drafting against observed friction is the v1.x path per locked decision 10.

### §17.10 Texture rendering for Ship 1 (DM-typed-directive) surface

When Ship A lands, the matcher path computes texture for ANY pending row consume (regardless of writer surface). Ship 1's resolutions (DM-typed directives) will get textured rendering retroactively as a side effect. This is intentional — the texture is per-roll, not per-trigger-surface. **Not out of scope; documented as a beneficial side effect.**

### §17.11 ROADMAP / SESSIONS / DOCTRINE / FAILURES / VIRGIL_MASTER / WHY doc updates

Doc-update pass happens after Ship A implementation lands and verify is clean (S36+). Spec only writes itself; downstream doc updates are S36's job after the implementation ships.

---

*End of spec v1 (DRAFT). Session 35.*

---

## Tabular handoff

| Field | Value |
|---|---|
| **File written** | `/home/jordaneal/virgil-docs/specs/LLM_EMIT_RESOLUTION_BINDING_SPEC.md` |
| **Status** | LOCKED v1 — S35b review complete; 6 framing revisions applied per `LLM_EMIT_RESOLUTION_BINDING_REVIEW.md` §4 |
| **Spec sections** | §1–§17 (17 sections + tabular handoff). §11 carries 12 pre-locked decisions from v3 §12 + 6 surfaced in drafting (B.1–B.6). Total: 18 decision points. |
| **Recon findings** | Q1 insertion point confirmed (`discord_dnd_bot.py:2359` post-channel-send). Q2 HARD STOP RULE 1 text captured verbatim. Q3 multi-word skill compat HIGH-confidence based on existing prompt-side documentation of Avrae's positional parsing; full live confirmation deferred to S36 implementation. Q4 ResolutionResult `frozen=True` extension confirmed safe (default-Optional field, identical pattern to existing `nat` field). |
| **HALT escalations** | None — recon held; no architectural surprises. |
| **Decision count** | 18 (12 pre-locked from v3 §12, 6 surfaced in spec drafting per §11.B.1–B.6) |
| **Test plan** | ~33 new assertions across 2 new + 3 extended test files (§14) |
| **Live-verify scenarios** | 8 scenarios (A1, A2, B, C, D, E, F, plus §15.10 Ship 4.5 calibration) + aggregate criteria (§15) |
| **Doctrine candidates** | C1 promotion pending Ship A verify (decision 11). C2 stays at one instance. New candidate "single-writer compatible with multiple trigger surfaces" filed at §16.3 (one instance). Total: 3 candidates with various status. |
| **Architectural lineage** | Ship A is additive on Ship 1 — reuses every primitive Ship 1 introduced, adds ResolutionTexture sub-dataclass + compute_stakes_tier §59 9th sibling + new writer hook + wrong-skill aside + prompt-side HARD STOP extension. Estimated ~350 LOC across `dnd_orchestration.py`, `discord_dnd_bot.py`, `dnd_engine.py`. |
| **Out of scope** | Cast resolution, player-typed `!check` (no preceding directive), combat-mode rolls, F-58, skill alias map, multi-actor temporal state (Ship 4.5), debounce, per-skill outcome map, texture vocabulary tuning post-verify, doc-update pass. |
| **Surfaced v1.x ticket** | Move `RESOLUTION_BINDING_SPEC.md` + `BUG_1_SPEC.md` from flat `/home/jordaneal/virgil-docs/` to `/home/jordaneal/virgil-docs/specs/` per dominant convention. Cosmetic; no code references break. |
| **Ready-for-implementation status** | Yes. Six framing revisions applied per review §4 (§11.B.2, §4.2, §5.2/§5.4/§5.5, §10.2, §15.9, §11.B.6). Spec LOCKED. |
| **Next session** | S36 implementation per v3 §11 calendar — Opus high. Targets: writer hook in `_dm_respond_and_post`, ResolutionTexture dataclass, compute_stakes_tier §59 9th sibling, render extensions, wrong-skill aside, HARD STOP RULE 1 + ROLL DIRECTIVE block extensions. ~350 LOC across 3 files; ~33 new test assertions; live verify per §15. |
