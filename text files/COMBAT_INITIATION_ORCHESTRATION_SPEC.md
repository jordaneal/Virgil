# Combat Initiation Orchestration — Design Spec v1 (DRAFT)

**Status:** DECISIONS LOCKED Session 20 — implementation-ready. §1 records locked decisions; §11 records the trade-off rationale per locked choice. See `COMBAT_INITIATION_ORCHESTRATION_REVIEW.md` for full review trade-offs and architectural-pattern citations.
**Pattern:** Bridge layer (same shape as committed-action) + potential command-emission boundary crossing (NEW architectural surface)
**Track:** Track 3 / four-layer attack chain — addresses **layer 3** (Avrae `-t TARGET` binds to `<None>` when no active init tracker) and **layer 4** (combat mode lags player commitment)
**Sibling spec:** `COMMITTED_ACTION_RESOLUTION_SPEC.md` — committed-action handles the *escape* failure mode (turn N commits, turn N+1 escapes). This spec handles the *binding* failure mode on the commit turn itself.
**Failure mode this targets:**
1. Player types "I attack the barkeep with my dagger." Mode is `exploration`. No active initiative tracker. The B2.1-fixed attack template fires correctly — LLM narrates, then emits `!attack dagger -t Garrick`. Avrae receives the command, looks for "Garrick" in the (nonexistent) init tracker, binds `-t` to `<None>`, rolls against AC 10 default, and emits `<None>: Dealt 6 damage!`. The attack vanishes. No NPC took damage. No consequence captured. No scene-state update reflected the violence.
2. Same turn: Avrae never received an `!init begin`, so `_handle_init_event` never fires `set_scene_mode('combat')`. The next turn's mode is still `exploration`, the combat-mode prompt directive ("be terse and kinetic") never engages, and the LLM keeps narrating in exploration register through ongoing violence.

---

## 1. Locked decisions (Session 20)

All decisions below are LOCKED per Session 20 review-and-lock pass. Each entry corresponds to a §11 decision in this doc and a §1 entry in `COMBAT_INITIATION_ORCHESTRATION_REVIEW.md` where trade-offs and confidence were recorded.

1. **Resolution shape: Shape B — LLM-emits init commands via directive.** Extend the existing attack-template directive (the B2.1 fix in `RollDecision.to_prompt_directive()`) to instruct the LLM to emit `!init begin` and `!init add <target>` BEFORE its `!attack <weapon> -t <target>` when (a) intent classifies as COMBAT and (b) scene mode is not currently `combat`. Reuses the B2.1 narration-mandate pattern. No new bot→Avrae write boundary. The bot remains read-only on the Avrae channel; only the LLM (via the player-facing narration channel) emits `!`-prefixed commands, exactly as it already does for `!attack`/`!cast`.

2. **No deterministic mode flip on COMBAT intent in v1.** Mode flip continues to flow through `_handle_init_event` when Avrae's plaintext "Awaiting combatants… Everyone roll for initiative!" message arrives in response to the `!init begin` the LLM emitted. The existing path is the canonical mechanical signal; the LLM-emitted command triggers it without the bot needing a parallel write path. Layer 4 is closed AS A SIDE EFFECT of layer 3's resolution, not by a separate intent-flip mechanism.

3. **New tactical-band directive: `init_directive`.** Computed in `dnd_orchestration.compute_init_directive(...)`, rendered in `build_dm_context` AS PART OF the existing `=== ROLL DIRECTIVE ===` block (not a new band). Composes with the attack template — when the gate fires, the attack template grows two new lines (begin + add) before the existing `!attack` line, plus an explicit narration-preservation mandate carrying B2.1 doctrine forward.

4. **Detection: signal-based, deterministic.** Three signals AND'd:
   - `intent_current == INTENT_COMBAT` (already computed via `classify_action_intent`)
   - `mode != 'combat'` (read from scene_state, authoritative)
   - No active init tracker — proxy: `get_active_turn(campaign_id)` returns None (the bot's only durable signal that Avrae has init running for this campaign)
   No second LLM call. Cheap, fast, debuggable. Same shape as commitment-directive's gate stack.

5. **Target hint resolution: reuse consequence/commitment scoping.** `recently_active_npcs ∪ get_npc_names_at_location(current_loc)` — the same set used by the just-shipped commitment directive (locked §11.B). Empty-set fallback: emit `!init begin` only, omit `!init add`, surface a note in narration ("the world hesitates as you commit — name your target so the world can answer") so the LLM is guided to make the target explicit. Loud-failure-recoverable per B2.1 doctrine.

6. **Avrae rejection handling: defer to existing failure modes.** Shape B means the LLM emits the commands. Avrae's responses (or rejections) flow through the existing `_handle_init_event` parser. If Avrae rejects (e.g. init already running), the `!init begin` is a no-op — Avrae's response is captured by the listener but doesn't break anything. If `!init add Garrick` fails because Garrick isn't a known combatant, Avrae responds with an error message; the LLM sees the error in next turn's context (chroma_search recall) and can correct in narration. Same loud-failure-recoverable path as B2.1's wrong-target case.

7. **Mid-combat new-target handling: out of scope.** The directive only fires when `mode != 'combat'` AND `get_active_turn` is None. Once init is running, the existing `!attack -t <target>` template handles new targets via Avrae's combatant lookup. If the player attacks an NPC not in the init tracker mid-combat, Avrae's existing `<None>` failure mode applies — that's a LIVE TEST observation file, not a v1 directive case. Filed for v2 / sibling spec.

8. **Stale Avrae state cleanup: out of scope.** The "throx" stale-state observation from Session 18 is real but orthogonal — that's an Avrae-side cleanup question, not a Virgil-side orchestration question. v1 doesn't auto-fire `!init end` on bot startup, campaign load, or session start. Filed as a candidate hygiene ship per WHY's "Companion observation: Avrae state from prior sessions can leak."

9. **Single-turn scope: v1 fires only on the turn the player commits.** No multi-turn lookback. If the player commits on turn N without active init, the directive fires on turn N. If turn N+1 the player keeps attacking (now in combat mode after Avrae confirmed `!init begin`), the directive does NOT fire (gate 2 fails: mode is now combat). Same single-turn discipline as commitment.

10. **PC-only scope. NPC-side combat initiation (NPCs deciding to attack the player first) is OUT.** The bot does not generate hostile NPC actions; the LLM does that via narration, and the player's reactive attack triggers the same directive. NPC-initiated combat is filed for "encounter framing" v2 or post-friends work.

11. **Telemetry first.** A new `init_directive:` log line on every turn (silent-when-empty signals included) so the empirical rate of "commit turn without init" surfaces immediately. Companion to `godmode_gap` / `commitment_directive` log shape. Lets calibration ride on observed rate, not pre-design.

---

## 2. Goal — which THE_GOAL bullets this serves

Direct hits:

- ✅ **"I want combat to be fun. I want to feel something when I kill an enemy."** Today, when the player commits to violence in exploration mode, the attack rolls against `<None>` and silently vanishes. The kill — and the enemy — never happens. Combat-as-spectacle is impossible when mechanical resolution silently fails.
- ✅ **"Failure should create story, not dead ends."** A `<None>: Dealt 6 damage!` line in the Avrae embed is the dead-end pattern made literal — failure creates literally nothing. The directive ensures Avrae has a real combatant to bind, so failure (miss, crit-miss, opportunity attack) becomes a real event with real consequences.
- ✅ **"Player agency has to survive the AI."** Inverse case: when the player's *committed* agency dissolves into `<None>` because the system didn't initialize the mechanical context the action requires, agency is degraded by infrastructure. The system should resolve what the player declared, not let infrastructure failures erase it.
- ✅ **"Choices should matter later, not just in the moment."** A choice that doesn't even resolve in *this* moment can't matter later — there's no `dnd_consequences` row written for an attack against `<None>`, no NPC HP delta, no scene-state mutation. Closing the binding gap is the prerequisite for "choices matter later."

Indirect hits:
- **"NPCs we wronged should still be wronged."** Adjacent: NPCs we attempted-to-wrong but who never registered the attack mechanically can't be wronged. Init binding is the mechanical floor that makes the wronging stick.

Bullets v1 explicitly does NOT serve:
- "If players come up with a creative solution and the system forces them back to the 'right' path, we've failed." This spec is explicitly NOT about forcing the player onto a "right" path. It's about ensuring the mechanical infrastructure is in place to RESOLVE whatever path the player chose. Tension to call out: the directive's strength must not crowd narration into command-only output (B2.1 lesson). See §6.
- "If failed rolls just stop play instead of changing the situation, we've failed." Different layer (failure-handling, not initiation). Adjacent.

---

## 3. Architecture pattern

### Where it sits

```
                Player message arrives in #dm-narration
                              │
                              ▼
              scene_state = get_scene_state(campaign_id)
                              │
                              ▼
              intent = classify_action_intent(text, mode)
                              │
                              ▼
              roll_decision = should_call_roll(intent, mode, ctx)
                              │
                              ▼
              ┌─────────────────────────────────────────┐
              │  compute_init_directive(                │
              │      intent, mode,                      │
              │      active_turn=get_active_turn(...),  │
              │      target_hints=[...]                 │
              │  ) -> (str, signals_dict)               │
              └─────────────────────────────────────────┘
                              │
                              ▼
              pass into RollDecision.to_prompt_directive()
              OR build_dm_context as new init_directive=
                              │
                              ▼
                       LLM narration
                              │
                              ▼
              LLM emits: narration + !init begin + !init add <t> + !attack -t <t>
                              │
                              ▼
              Avrae receives commands, fires init events,
              _handle_init_event flips mode to combat,
              !attack now binds -t correctly
                              │
                              ▼
              Next turn: mode=combat, init active, normal flow
```

### Architectural surface name (NEW)

**Bridge layer + LLM command-emission extension.** The committed-action directive was pure bridge (LLM picks the move). This spec extends bridge into **LLM-as-mechanical-command-emitter** territory. The LLM has been emitting `!attack`/`!cast` commands since B2.1. This spec adds `!init begin` / `!init add` to the LLM's emission repertoire. The bot itself remains read-only on the Avrae channel; only the LLM's narration channel emission of `!`-prefixed text is parsed by Avrae as commands. **No new bot→Avrae write boundary.**

(If Jordan locks Shape A or C in §11.1, the architectural surface name CHANGES to "bot→Avrae direct command emission." Currently the bot has zero outbound `!`-prefixed messages — every `channel.send` / `narration_ch.send` is either narration text or an embed. Crossing that boundary is non-trivial and is named explicitly in §11.1.)

### What's new

- One new directive function in `dnd_orchestration.py`: `compute_init_directive(intent, mode, has_active_turn, target_hints) -> (str, signals_dict)`.
- One new signals helper: `init_log_summary(signals)` (mirrors `commitment_log_summary`).
- An EXTENSION (not replacement) of `RollDecision.to_prompt_directive()` for the COMBAT branch — when the init directive is non-empty, the attack-template lines grow to include `!init begin` and `!init add <target>` directives BEFORE the existing `!attack` template.
- One new kwarg on `build_dm_context`: `init_directive=""` — purely advisory if Shape B is locked (used to render the prefix lines into the ROLL DIRECTIVE block); could be standalone if Shape A is locked.
- Telemetry: `init_directive:` log line on every COMBAT-intent turn.
- Test file: `test_init_directive.py` — gate-isolation + composition tests + the LLM-emission ordering case.

### What's reused

- `classify_action_intent(...)` — already runs once per turn.
- `should_call_roll(...)` — already runs once per turn for COMBAT intent.
- `get_active_turn(campaign_id)` — already deterministic, returns None when no `!init turn` has fired since last `!init end`.
- `get_recently_active_npcs(...) ∪ get_npc_names_at_location(...)` — same scoping rule the commitment directive shipped with.
- `_handle_init_event` for mode flip on Avrae's response — no change needed.
- The B2.1 attack template + narration mandate — extended, not replaced.

### What's NOT changed

- `set_scene_mode` semantics — mode still flips ONLY on Avrae's `!init begin` response (or `/mode`, or rest events). No intent-driven flip.
- Existing `discord_dnd_bot.on_message` flow — no new outbound `channel.send` of `!`-prefixed text.
- `dnd_combat_state` schema — read-only from the new directive's perspective.
- The committed-action directive — runs unchanged on subsequent turns.

---

## 4. Data model

**No new schema.** Detection reads from existing state:
- `dnd_scene_state.mode` (already authoritative)
- `dnd_combat_state.character_name` (read via `get_active_turn` to detect "is init active?")
- `dnd_npcs` via `get_recently_active_npcs` + `get_npc_names_at_location` (already wired)
- `intent_current` (computed from `classify_action_intent` — already runs once per turn)

The "is init active?" detection is a proxy: `get_active_turn(campaign_id) is None` → no `!init turn` has fired since the last `clear_active_turn`. This is NOT 100% accurate (a freshly-issued `!init begin` followed by `!init add` produces no `turn` event until the round starts), but for v1 the detection is "best signal we have without Avrae state probes" and good enough for the load-bearing case (player attacks in pure exploration with zero prior init activity).

(Alternative: persist `init_active_at: TIMESTAMP` updated on `!init begin` parse, cleared on `!init end`. One-column ALTER on `dnd_combat_state`. Idempotent. Filed as §11 decision — alternative signal source.)

---

## 5. Detection layer

### 5.1 Trigger

`compute_init_directive` runs at the START of `dm_respond` after `scene_state` is loaded, intent is classified, and `roll_decision` is computed (so the directive can be threaded through the existing `RollDecision.to_prompt_directive()` extension OR rendered as a sibling block, depending on §11.8).

### 5.2 Detection logic (proposed v1, Shape B)

```python
def compute_init_directive(
    intent_current: str,
    mode: str,
    has_active_turn: bool,
    target_hints: list[str],
) -> tuple[str, dict]:
    signals = {
        'fired': 0,
        'intent_current': intent_current or 'unknown',
        'mode': mode or 'unknown',
        'has_active_turn': 1 if has_active_turn else 0,
        'target_hint_count': len(target_hints or []),
    }
    # Gate 1: COMBAT intent (locked §11.4 — same scope as godmode_gap).
    if intent_current != INTENT_COMBAT:
        return '', signals
    # Gate 2: mode is not already combat.
    if mode == 'combat':
        return '', signals
    # Gate 3: no active init tracker (proxy via get_active_turn).
    if has_active_turn:
        return '', signals
    # All gates passed — emit the directive.
    body = _INIT_DIRECTIVE_BODY.format(
        target_hint_block=_render_target_hint_block(target_hints),
    )
    signals['fired'] = 1
    return body, signals
```

### 5.3 No new regex

This spec re-uses `INTENT_COMBAT` from the existing `classify_action_intent` taxonomy. No new intent tag. No SCENE_SHIFT-style helper.

### 5.4 Signal source: `get_active_turn`

The bot's only durable "is init active?" signal is `dnd_combat_state` rows, written from parsed `!init turn` events. Edge cases:

- **`!init begin` fired but no `!init turn` yet**: `get_active_turn` returns None even though init IS active. Directive could over-fire here — the LLM would emit `!init begin` again, Avrae responds with "combat is already active in this channel" or similar. Recoverable. Filed for log analysis post-ship.
- **`!init end` fired but `clear_active_turn` not yet called**: should not happen — `_handle_init_event` calls `clear_active_turn` synchronously on `init_event=='end'`.
- **Bot restart**: in-memory state lost, but `dnd_combat_state` persists. Directive correctly does NOT fire if a turn was active at restart.

The proxy is "best signal without an Avrae state probe." The alternative (persist `init_active_at` timestamp on Avrae's `begin` event) is filed as §11.6.

---

## 6. Resolution / directive layer

### 6.1 Directive body (proposed, Shape B — extends the attack template)

When the gate fires, the existing `RollDecision.to_prompt_directive()` for COMBAT intent grows from this:

```
=== ROLL DIRECTIVE ===
You are about to resolve a combat attack. Avrae handles attack rolls via !attack / !cast.
Quote the EXACT command: !attack <weapon-name> -t <target>
EXCEPTION FOR ATTACKS: when ROLL DIRECTIVE is an attack roll, the quoted command is a TEMPLATE...
[B2.1 narration mandate]
```

…to this (additions in CAPS for visibility, not literal):

```
=== ROLL DIRECTIVE ===
You are about to resolve a combat attack. Avrae handles attack rolls via !attack / !cast.

INIT NOT YET ACTIVE — INITIATIVE TRACKER MUST START THIS TURN.
The world has not yet entered combat mechanically. Before your attack command, you MUST
emit two preparatory commands so Avrae can bind the attack to a real combatant:

  !init begin
  !init add <target>

Only THEN emit:

  !attack <weapon-name> -t <target>

(Three commands total, one per line, in this exact order. Replace <target> with the
NPC the player has committed to attacking. Candidate names: <target_hint_block>.)

EXCEPTION FOR ATTACKS: ... [existing carve-out]

YOUR NARRATION MUST come BEFORE all three commands — describe the player's draw,
the room's reaction, the target's posture. A response that is ONLY commands is
INSUFFICIENT and breaks the table. The narration is the player's experience;
the commands are the world's mechanical bookkeeping. Both must appear.

[B2.1 narration mandate, extended.]
```

When the gate does NOT fire, the existing template renders unchanged.

### 6.2 Composition order (proposed, Shape B)

Renders INSIDE the ROLL DIRECTIVE block, BEFORE the existing `!attack` template. Same band as the COMBAT roll directive. The init directive is conceptually a PRECONDITION on the attack — it's the lines that must precede `!attack` to make the binding work. Putting it inline keeps the ordered-list semantics tight ("emit these lines IN THIS ORDER").

If Shape A or C is locked, composition order changes — see §11.8.

### 6.3 Update on emit

No state mutation on emit. The directive is purely advisory.

Logging:
```
init_directive: campaign={X} fired={0|1} intent_current={Y} mode={Z}
                has_active_turn={0|1} target_hint_count={N}
```

The `init_directive:` line fires on EVERY turn (not just when the directive emits) so the empirical baseline of gate signals is observable. Same shape as `commitment_directive:` and `consequence_directive:`.

---

## 7. Failure modes + mitigations

1. **LLM refuses to emit `!init begin`.** Pre-B2.1, LLMs would silently elide commands when directives competed; post-B2.1, the narration mandate keeps the surrounding prose alive but the COMMAND emission discipline depends on the directive's strength. With THREE commands in order, the LLM might emit only the `!attack` (the most familiar) and skip the two new ones.
   *Mitigation:* The B2.1 narration mandate is preserved AND extended explicitly to "narration FIRST, then ALL THREE commands." Live verify after ship — if LLM compliance is lower than B2.1's `!attack` rate, file as v2 strength-tuning.

2. **LLM picks wrong target name in `!init add`.** The target hint set may include NPCs the player isn't actually attacking. The LLM picks one, Avrae adds the wrong NPC to combat, then `!attack -t Wrong_NPC` binds against an NPC the player didn't intend.
   *Mitigation:* Loud-failure-recoverable per B2.1 doctrine. The wrong NPC takes damage in the embed, Jordan / DM corrects in next turn. Worse failure is silent `<None>` (today's state); this trades that for "wrong NPC" which is recoverable. Future: tighten target hint set via prior_action_text parsing (filed v2).

3. **No NPCs in scope (target_hints is empty).** Player attacks before any NPC is named or located. The directive emits `!init begin` but cannot suggest `!init add <target>`.
   *Mitigation:* Emit `!init begin` only, omit `!init add`, and surface narration guidance: "name the target so the world can answer." LLM produces narration that names the target (because the directive says it must), the LLM can THEN emit `!init add <name>` from its own narration. Less precise than scope-driven hint, but functional.

4. **Avrae rejects `!init begin` because init is already running.** The proxy (`get_active_turn is None`) says no, but Avrae has a half-state from a prior session (the "throx" stale-state observation).
   *Mitigation:* Avrae's response ("combat is already active in this channel") is captured by the listener but doesn't break anything. The `!init add Garrick` proceeds against the existing tracker. The `!attack` binds. Recoverable. Filed observation.

5. **Avrae rejects `!init add Garrick` because Garrick isn't a known combatant.** Avrae responds with an error embed.
   *Mitigation:* The LLM-emitted `!attack` STILL fires and binds against the active combatant — if Garrick isn't added, `-t Garrick` falls back to `<None>` again. This is the original failure mode partially restored. Mitigation depth-2: the LLM should follow Avrae's error with `!init add` retry next turn; or post-ship analysis surfaces this as the dominant failure mode and we widen Shape B with a probe step.

6. **Mode flip lag — Avrae's `!init begin` response message arrives AFTER the LLM emits `!attack`.** Race condition: bot reads attack from Avrae's `!attack` echo before Avrae processes `!init begin` and emits the begin message.
   *Mitigation:* The LLM emits `!init begin` BEFORE `!init add` BEFORE `!attack` in the same Discord message. Avrae processes them in order. By the time `!attack` is parsed, the init tracker exists. The mode flip arrives in the next tick — too late for THIS turn's `_format_avrae_events` but in time for the NEXT turn's mode assertion. Acceptable: this turn's narration is the commit-turn, NEXT turn is the first "true combat" turn, mode flip arrives between.

7. **The directive over-fires and the LLM emits `!init begin` when init IS active (proxy false-negative).** Avrae rejects, no harm.
   *Mitigation:* Filed as observable via `init_directive: fired=1` plus Avrae's parsed-but-untouched begin-error response. Log analysis post-ship.

8. **Multi-actor combat initiation.** Player A says "I attack Garrick." Player B same batch says "I attack Tavern Bouncer." Both want init. The directive fires on the first message processed; the LLM batches both into one response.
   *Mitigation:* The LLM, told "init must start," emits `!init begin` once + `!init add Garrick` + `!init add Tavern Bouncer` + `!attack` for each actor. Avrae handles multi-add. Filed for live verify.

9. **The directive crowds out the commitment directive on rare overlap turns.** A player might commit on turn N (init directive fires) and immediately try to escape on turn N+1 (commitment directive fires). Different turns, no overlap. But on turn N alone: if the player's text is BOTH a commit AND a scene shift ("I swing my dagger and run for the door"), the init directive fires (intent=COMBAT) and the commitment directive does NOT fire (intent_prior is whatever last turn was; the conjoined commit-and-flee is a single-turn problem).
   *Mitigation:* This is a legitimate gap — single-turn commit+escape isn't handled by either spec. Filed as a v2 case for either spec to absorb later.

---

## 8. Test plan (proposed)

### 8.1 Engine layer (`test_init_directive.py`)

- No COMBAT intent (intent=SOCIAL/EXPLORATION/etc.) → returns `''` with `fired=0`.
- COMBAT intent + mode='combat' → returns `''` with `fired=0` (gate 2).
- COMBAT intent + mode='exploration' + active_turn exists → returns `''` with `fired=0` (gate 3).
- COMBAT intent + mode='exploration' + no active_turn + target hints exist → directive fires; body contains `!init begin`, `!init add`, target hint names.
- COMBAT intent + mode='exploration' + no active_turn + EMPTY target hints → directive fires; body contains `!init begin` only, with the "name the target" narration guidance.
- Composition: when directive fires, it appears INSIDE `RollDecision.to_prompt_directive()` for COMBAT, BEFORE the existing `!attack` template line.
- Idempotency: directive computation is pure (no side effects).
- Cross-campaign isolation: same shape as commitment-directive tests.
- B2.1 mandate preserved: directive body contains the "narration MUST come BEFORE commands" mandate.

### 8.2 Integration test (light)

- Synthetic scene_state with mode='exploration', no active_turn, current player text "I attack Garrick with my dagger." Build full `dm_respond` prompt; verify the resulting prompt contains the three-command sequence in order AND the `init_directive:` log line.
- Negative integration: same scene with mode='combat' and active_turn set — verify the three-command sequence is NOT in the prompt.

### 8.3 Live verification

After v1 ships, replay the canonical Session 18 scenario:
- Restart bot, ensure no active init.
- Player types: "I swing my dagger at Garrick the barkeep."
- Expected: bot's narration response contains `!init begin` + `!init add Garrick` + `!attack dagger -t Garrick` (or similar) in order, with a narrative paragraph BEFORE all three commands.
- Expected log lines: `init_directive: ... fired=1`, `directive_emit: ... pacing=... central_thread=... consequence=... commitment=0 init=1`, `set_scene_mode: combat` (from `_handle_init_event` after Avrae's begin response).
- Expected Avrae embed: `Garrick: Hit! Dealt N damage!` (or miss) — NOT `<None>: Dealt N damage!`.

If the LLM ignores the directive (emits `!attack` only), that's a strength-tuning question to file, not a blocker. Same disposition as Session 19's empty-narration on commitment-fire turn.

---

## 9. Migration impact

**Schema changes:** None in v1.

**Code additions:**
- New `compute_init_directive(...)` in `dnd_orchestration.py`.
- New `init_log_summary(signals)` in `dnd_orchestration.py`.
- Extension of `RollDecision.to_prompt_directive()` for COMBAT branch (3-line prefix + extended narration mandate).
- New `init_directive=""` kwarg on `build_dm_context` (advisory, may be unused if Shape B inlines into roll-directive — see §11.8).
- New `init_directive:` log line in `dm_respond` after the directive computation.
- New `init={0|1}` field appended to the per-turn `directive_emit:` log line.
- New `test_init_directive.py` test file.

**Cross-version safety:** No schema = no migration risk. Old code without the new directive renders the prompt without the prefix lines (gate doesn't fire = template unchanged). Forward-only.

---

## 10. Out of scope (separate specs / separate layers)

- **Combat persistence.** "Combat keeps going while creatures have HP" — bridge-layer pressure to prevent the LLM narratively wrapping a fight before mechanical resolution. Pre-friends gating ship #3, sibling spec.
- **Encounter framing / NPC-initiated combat.** NPCs deciding to attack first — that's a generation problem (when does the LLM-narration introduce hostile intent?) not an initiation problem. Separate concern; post-friends.
- **Stale Avrae state cleanup.** "throx" observation. Hygiene ship. Filed.
- **Mid-combat new-target handling.** Player attacks an NPC not in the active init tracker. Different gate (init IS active, but `-t` still fails). Filed.
- **Multi-target attacks (`!init attack` with multiple `-t`).** v1 emits one `!init add` per attack. Multi-target is a future refinement.
- **Combat condition awareness.** "Player attacks while prone" — bridge-layer pressure on action economy. Different layer; far-future spec.
- **Direct bot→Avrae command emission.** Shape A/C territory. v1 keeps the boundary read-only. If §11.1 locks Shape A or C, this spec scope grows materially — see §11 for trade-offs.
- **Mode flip via intent inference (auto-flip to combat without `!init begin`).** Filed for review in `COMMITTED_ACTION_RESOLUTION_REVIEW.md` §11.4 — explicitly deferred. v1 retains "Avrae owns mode authority" doctrine.
- **Single-turn commit+escape.** Player commits AND scene-shifts in the same message. Neither this spec nor the commitment spec fires correctly. Filed as v2 case.

---

## 11. Decision record (LOCKED Session 20)

All nine decisions LOCKED Session 20. Each entry below records the locked choice, restates the question, and notes the rationale recap; full trade-off analysis lives in `COMBAT_INITIATION_ORCHESTRATION_REVIEW.md` §1.

### §11.1 — Resolution shape: A (bot direct), B (LLM directive), or C (hybrid)?
**LOCKED: Shape B (LLM-emits via directive).**

**Restate.** Where does `!init begin` come from? Three plausible shapes:
- **A.** Bot directly emits `!init begin` and `!init add <target>` to #dm-narration channel before the player's turn resolves. Tight coupling, removes LLM as variable. Bot owns the decision; LLM can't refuse. **Crosses a NEW write boundary** — currently the bot has zero outbound `!`-prefixed messages.
- **B (proposed).** Directive instructs the LLM to emit `!init begin` and `!init add <target>` in narration alongside its `!attack`. Reuses the B2.1 attack-template pattern. LLM picks target. Failure mode: LLM might forget or skip a command.
- **C.** Hybrid. Bot emits `!init begin` deterministically; LLM emits `!init add <target>` and `!attack`.

The architectural surface name in §3 changes per choice. v1 proposes B. Open: does Jordan want the bot to directly cross the Avrae-write boundary now, file it for later, or stay at LLM-emission?

### §11.2 — Mode auto-flip on COMBAT intent: same spec, separate spec, or never?
**LOCKED: reactive flip via existing `_handle_init_event` path. No new intent-driven flip path.**

**Restate.** The committed-action review §11.4 deferred deterministic mode flip "ADOPT in concert with this spec, but only if §11.A also lands." This IS §11.A in spec form. Should mode flip become PART OF this spec, stay separate, or be rejected as a doctrine departure (Avrae owns mode authority)?

If part: where does `set_scene_mode('combat')` fire — before `!init begin` (forces mode flip on intent), after Avrae's begin response (current behavior, no change), or in parallel with `!init begin` emission?

v1 proposes "no change to mode-flip semantics" — Avrae's begin response remains the canonical trigger. Open: should we add an intent-driven flip as belt-and-suspenders, or trust the response path?

### §11.3 — Target name resolution: inherit committed-action's `recently_active_npcs ∪ at_location`?
**LOCKED: inherit `recently_active_npcs ∪ get_npc_names_at_location(current_loc)` scoping pattern.**

**Restate.** Same question that §11.B in the committed-action review answered. Reuse the consequence-layer scoping pattern, or pick a different shape (parse `player_action` text directly for explicit `at <name>` markers; LLM-extract; trust LLM to name the target without any hint)?

v1 proposes reuse. Open: are there layer-3-specific considerations (e.g., this NPC is brand-new and not yet in `dnd_npcs` because the consequence_race shape hasn't seen this turn yet) that would weaken the reuse default?

### §11.4 — Detection signal: `get_active_turn is None`, or persist `init_active_at` timestamp?
**LOCKED: proxy via `get_active_turn(campaign_id) is None`. Zero schema change.**

**Restate.** The proxy "no active turn" misses the edge case "init_begin fired but no turn yet." Persisting an explicit `init_active_at` timestamp on Avrae's begin event would close that gap.

Trade-offs:
- **Proxy (`get_active_turn`):** zero schema change, "good enough" for the load-bearing case (player attacks in pure exploration with zero prior init activity). Edge cases over-fire (LLM emits redundant `!init begin`, Avrae rejects, no harm).
- **Persist:** one-column ALTER on `dnd_combat_state` (or a new column on `dnd_scene_state`). Idempotent migration. Single-write-path: `_handle_init_event` writes on `init_event=='begin'`, clears on `'end'`. Tighter signal, no over-fire.

v1 proposes proxy. Open: is the over-fire annoying enough in observed logs to justify the schema add?

### §11.5 — Avrae rejection handling: defer to existing failure modes, or add a probe / retry / surface-to-player?
**LOCKED: defer. Avrae's rejection responses are captured by the listener; recovery is the LLM/Jordan correcting next turn. v2 escalation only if observed log rate justifies.**

**Restate.** If `!init begin` fails because init is already running, or `!init add Garrick` fails because Garrick isn't a known combatant, what happens?

Options:
- **Defer (proposed):** Avrae's response is captured by the listener but doesn't break anything. Recoverable. The LLM emits `!attack` regardless; if `-t Garrick` doesn't bind, we get the original `<None>` failure restored.
- **Probe:** before emitting `!init begin`, query Avrae state via `!init list` or similar. Adds round-trip latency.
- **Retry:** bot-side state machine to retry on Avrae's rejection response. New layer.
- **Surface to player:** "couldn't start init — please run !init begin manually." Loud, recoverable, breaks immersion.

v1 proposes defer. Open: if log analysis shows Avrae rejection is the dominant post-ship failure mode, does it warrant probe/retry?

### §11.6 — Single-turn vs multi-turn coverage
**LOCKED: single-turn (commit turn only). Multi-turn earns expansion from observed misses post-ship.**

**Restate.** v1 fires only on the COMMIT turn. If the player's commit turn correctly emits `!init begin + !init add` but Avrae responds slowly and the next turn the LLM gets a STALE `mode='exploration'` snapshot, does the directive re-fire spuriously?

Trade-offs:
- **Single-turn (proposed):** commit-turn-only; subsequent turns rely on `mode='combat'` plus `get_active_turn` to suppress.
- **Multi-turn (defer):** track an `init_intent_pending` state for ~1-2 turns to bridge race conditions.

v1 proposes single-turn (filed-not-sequenced + diagnostic-first). Multi-turn earns its expansion from observed misses.

### §11.7 — Stale Avrae state cleanup as part of this spec, or filed?
**LOCKED: file. Slash-command pattern (`/init_reset` or similar) when revisited — sidesteps the bot→Avrae direct-emission boundary.**

**Restate.** Should v1 ship an automatic `!init end` on bot startup or campaign load (clearing pre-existing throx-like contamination), or stay file-only?

Trade-offs:
- **Ship in v1:** small additional code (`!init end` emission on `on_ready` or `/play`). Requires the bot to emit a `!`-prefixed command — DEPENDS on §11.1 resolution. If §11.1 locks Shape B (LLM-emits), then v1 cannot deterministically clean up at startup without crossing the bot→Avrae boundary anyway.
- **File:** keep v1 pure to initiation, address contamination as a separate hygiene ship.

v1 proposes file. Open: is the throx case observable enough that Jordan wants this in v1?

### §11.8 — Composition order: inside ROLL DIRECTIVE block, or new tactical-band block?
**LOCKED: inside ROLL DIRECTIVE. Init prefix is a precondition on the attack template, not narrative pressure — keeps command-emission discipline together with B2.1's narration mandate.**

**Restate.** Where do the `!init begin` / `!init add` directive lines render?

- **Inside ROLL DIRECTIVE (proposed):** they're a precondition on the attack template. Tightly bound to the existing B2.1 attack-template. Cleaner ordering semantics.
- **New tactical-band block:** `=== INITIATIVE START ===` block sibling to consequence/commitment, preceding ROLL DIRECTIVE. Decoupled from the attack template.
- **After ROLL DIRECTIVE:** strange ordering; LLM would see `!attack` template before the precondition.

v1 proposes inside ROLL DIRECTIVE. Open: does the band-consistency rule (every Track-3 directive gets its own `===` block) outweigh the "init is precondition on attack" framing?

### §11.9 (NEW) — Directive strength on three-command emission
**LOCKED: imperative + extended B2.1 narration mandate + at least one positive example showing all three commands in order. Calibrate from observed compliance post-ship.**

**Restate.** B2.1 had to add a narration mandate because a single attack-template directive crowded narration. This spec stacks THREE commands in order. What's the calibration shape?

Trade-offs:
- Imperative ("emit ALL THREE in ORDER, narration FIRST"): risks pushing LLM into command-only output mode (B2.1 lesson). Same shape as B2 → B2.1.
- Softer ("consider emitting `!init begin` if no init"): risks LLM ignoring the directive (returns to today's failure mode).
- Imperative + B2.1 narration mandate (proposed): explicit "narration BEFORE all three commands" with positive/negative examples.

v1 proposes imperative + extended B2.1 narration mandate. Confidence depends on observed compliance rate post-ship.

---

All §11 decisions LOCKED. Implementation session ready; see review §3 for scope estimate (3-5h Sonnet, Shape B + §1 defaults).

---

## Appendix — relationship to other layers

- **Committed action resolution (Session 19, shipped).** Sibling spec. Commitment handles the *escape* failure mode (turn N+1 ignores turn N's commitment). Init orchestration handles the *binding* failure mode on turn N itself. The two together close all four layers of the attack chain documented in WHY's `Why the post-B2.1 attack still showed <None>: Dealt 2 damage!`.
- **Combat persistence (filed, pre-friends ship #3).** Bridge-layer pressure once init IS active. Different concern: keeping combat going, not starting it. Sibling.
- **B2.1 attack template doctrine.** Direct reuse — this spec extends the attack template to include init-prefix commands and carries the narration mandate forward explicitly.
- **Three-layer 5e doctrine (WHY, Session 19 block).** This spec lives on the BRIDGE layer (sub-layer 3 of the four-layer attack chain). Mechanical layer (Avrae's roll resolution, target binding logic) remains untouched. Narrative coherence layer (capability grounding) is informed but not the focus.
- **Phase 6 strict-equality identity.** Target hints rely on canonicalized NPC names from `dnd_npcs`. The hint set includes names already canonicalized; the LLM emits `!init add <canonical_name>` matching the form Avrae will see in subsequent embed parsing.
- **Asymmetric trust.** Same shape as B2.1: trust the LLM with command emission within a strict template, fail loudly on miss, recover next turn. The bot does not trust itself to write `!`-prefixed text directly (Shape A would change this; Shape B preserves it).

**Filed, not sequenced** — per `feedback_no_pre_sequencing.md`. Pre-friends gating ship #2. Order of #2 vs #3 (combat persistence) is re-decided after this ship's logs accumulate signal.
