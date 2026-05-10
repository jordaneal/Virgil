# Committed Action Resolution — Design Spec v1 (DRAFT)

**Status:** SPEC ONLY — pre-review. §1 lists *proposed* decisions, NOT locked. §11 surfaces decision points needing Jordan's call before any code lands.
**Pattern:** Tactical directive layer (same shape as pacing, central thread, consequence)
**Track:** Track 3 (directive layer) — addresses the "godmode" failure mode Jordan flagged Session 16
**Failure mode this targets:** A player commits to an action with weight (drawing a weapon, attacking an NPC, fleeing), then the next turn types an unrelated action (leaving the scene, helping someone else), and the DM accepts the new action without resolving the prior commitment. The world doesn't insist on resolution. The committed action evaporates as if it never happened.

---

## 1. Proposed decisions (NOT yet locked — see §11)

These are what I'd propose if the spec went straight to implementation. Every one is up for change in review.

1. **Detection is signal-based, not LLM-judged.** Combine three deterministic signals:
   - Prior turn's `intent` classification (already computed via `classify_action_intent`)
   - Avrae RollBuffer state between prior turn and now (was a mechanical action resolved?)
   - Current turn's `intent` classification (does it shift scene/context?)
   No second LLM call to "judge" whether an action is open. Cheap, fast, debuggable.

2. **Resolution is directive-layer, not refusal.** When the godmode pattern is detected, the system emits a tactical directive into the prompt that says the LLM must either (a) narrate the prior commitment's consequence first, (b) require a roll for the new action that implies disengagement, or (c) refuse the disengagement attempt explicitly. The LLM owns the prose; the directive owns the constraint. Same architectural shape as pacing/central-thread/consequence.

3. **Single committed-intent scope in v1: COMBAT.** Detect open COMBAT-intent commitments only. RISKY and CONTESTED commitments (e.g. "I pickpocket the merchant" then next turn "I leave the marketplace") are real but harder to disambiguate; defer until COMBAT case is proven.

4. **Resolution signals: Avrae mechanical events OR DM narration with target reaction.** The mechanical signal (Avrae attack/save/check between prior and current turn) is the strongest — if Avrae fired, the action resolved. The narrative signal (DM's prior response contained target NPC's name + reaction-bearing verb like "dodges, blocks, falls, retreats, retaliates") is weaker but catches the case where the DM resolved narratively without a roll. v1 uses BOTH — if EITHER signal fires, the commitment is considered resolved.

5. **No new schema.** Detection reads from existing state: `RollBuffer` (in-memory), prior DM response (held in conversation history), prior `intent` (re-computable from prior `last_player_action` in `dnd_scene_state`). No `dnd_open_commitments` table, no migrations.

6. **Directive sits in tactical band.** Renders AFTER consequence directive, BEFORE end of system prompt. Same composition rule as the rest of Track 3 — frames the move, doesn't replace philosophy.

7. **Diagnostic ships first (already shipped Session 16).** `godmode_gap` log line emits when COMBAT intent fires in a non-combat mode, surfacing the gap empirically before the constraint layer ships. Lets Jordan see how often the pattern fires in real play before deciding directive strength.

8. **No deterministic mode flip on COMBAT intent in v1.** A sibling architectural option (force `set_scene_mode('combat')` whenever intent=COMBAT in non-combat mode) is filed but NOT proposed for v1 — it changes the behavior of every COMBAT-intent action, not just godmode escapes. Filed for separate review.

9. **PC commitment scope only.** Detect commitments the player makes. NPC-side committed actions (an NPC vows revenge, then the player leaves) are out of scope — that's consequence-surfacing v2 territory.

10. **Single-turn lookback in v1.** Detection compares current turn against the immediately preceding turn. Multi-turn commitment chains (player attacks turn N, deflects turn N+1, leaves turn N+2) are out of scope until the single-turn case is proven.

---

## 2. Goal — which THE_GOAL bullets this serves

Direct hits on the failure-mode list:

- ✅ **"Player agency has to survive the AI."** Inverse case: when the player's *committed* agency is silently undone by the AI (the LLM accepting a scene shift that erases the prior action), agency is degraded too. The system should hold the player to what they declared, not let the AI quietly soften the world.
- ✅ **"Failure should create story, not dead ends."** When a committed combat action goes unresolved, the failure-as-story option (you swung, missed, the barkeep retaliates, you're now in a fight whether you wanted one or not) is foreclosed. The DM accepting the scene shift is the dead-end pattern.
- ✅ **"Choices should matter later, not just in the moment."** A choice that doesn't matter in the *very next moment* won't matter later either. Committed-action resolution is the immediate-stakes layer of the same principle consequence-surfacing handles for accumulated stakes.
- ✅ **"If players come up with a creative solution and the system forces them back to the 'right' path, we've failed."** Tension here, important to call out: this spec is explicitly NOT about forcing the player onto a "right" path. It's about resolving what the player *already committed to*. A player who says "I draw my dagger, then think better of it and sheath it" is making a creative narrative choice — the spec must allow that. A player who says "I swing my dagger at the barkeep" then "I help a child outside" is creating narrative incoherence the system should refuse to render. Distinction: explicit retraction vs implicit ignore.

Indirect hits:
- **"I want combat to be fun. I want to feel something when I kill an enemy."** Combat that can be trivially abandoned has no weight. Forcing resolution makes commitment costly, which makes commitment meaningful.
- **"NPCs we wronged should still be wronged."** Adjacent: NPCs we wronged AND failed to resolve should react in the moment, not just in remembered consequence form. Committed-action resolution is the same-turn version of consequence surfacing.

Bullets v1 explicitly does NOT serve:
- "If failed rolls just stop play instead of changing the situation, we've failed." This spec is about resolution, not failure-handling. Adjacent but different.
- "The world should reward curiosity." Different mechanism (knowledge tier).

---

## 3. Architecture pattern

### Where it sits

```
                    Player message arrives
                            │
                            ▼
             scene_state = get_scene_state(campaign_id)
                            │
                            ▼
             intent_current = classify_action_intent(text, mode)
                            │
                            ▼
             intent_prior   = classify_action_intent(
                                  scene_state.last_player_action, mode
                              )
                            │
                            ▼
             ┌──────────────────────────────────────────┐
             │  compute_commitment_directive(           │
             │      intent_prior, intent_current,       │
             │      avrae_buffer_drained_since_prior,   │
             │      prior_dm_response, prior_npcs       │
             │  ) -> str                                │
             └──────────────────────────────────────────┘
                            │
                            ▼
             pass to build_dm_context as new
             commitment_directive=... kwarg
                            │
                            ▼
                     LLM narration
```

### What's new

- One new directive function in `dnd_orchestration.py`: `compute_commitment_directive(...)`.
- One new helper to detect "scene shift" intent in current turn (regex set, similar to existing intent regexes).
- One new helper to detect "target NPC reaction" in prior DM response (regex over prior_dm_response with current NPC list).
- One new kwarg in `build_dm_context`: `commitment_directive=""`.
- One new render block: `=== UNRESOLVED COMMITMENT ===`.
- Telemetry: `commitment_directive:` log line on every emit, `godmode_gap` already in place.

### What's reused

- `classify_action_intent` — the intent classifier. Used twice per turn (current + prior).
- `RollBuffer.recent` — already exists; checks for Avrae events by actor in a time window.
- `scene_state.last_player_action` — written by extraction thread on every turn, available on this turn.
- The directive composition pattern (`build_dm_context`).

### What's NOT changed

- `set_scene_mode` behavior — mode is still authoritative from Avrae init events / `/mode` / AUTO_EXECUTE. No deterministic mode flip on COMBAT intent in v1.
- Any existing intent classification regex — `INTENT_COMBAT` matching is unchanged.
- `dm_respond` flow — adds the directive computation, doesn't restructure.

---

## 4. Data model

**No new schema.** Detection reads from existing state:
- `dnd_scene_state.last_player_action` (already written by extraction thread)
- `RollBuffer` (in-memory per-guild, 75s TTL — sufficient for between-turn scope)
- The conversation's prior DM response (passed via `relevant_history` or held in caller)

If the prior DM response isn't available in the engine context, the spec needs to thread it. v1 simplifying assumption: `last_player_action` and the directive's evaluation of "did the DM narrate a reaction?" are sufficient signals; the prior DM response is optional context.

(Alternative if v1 needs more state: persist `last_player_intent` in `dnd_scene_state`. One column add. Idempotent migration. Filed as §11 decision.)

---

## 5. Detection layer

### 5.1 Trigger

`compute_commitment_directive` runs at the START of `dm_respond` after `scene_state` is loaded and current intent is classified. It runs BEFORE the prompt is built, so the directive can be passed via `build_dm_context`.

### 5.2 Detection logic (proposed v1)

```python
def compute_commitment_directive(
    intent_prior: str,
    intent_current: str,
    avrae_resolved_since_prior: bool,
    prior_dm_response: str,
    prior_target_hints: list[str],  # NPC names in prior DM response
) -> str:
    # Only fire on COMBAT-intent commitments in v1.
    if intent_prior != INTENT_COMBAT:
        return ''

    # If Avrae mechanical event happened between prior and current turn,
    # the action resolved.
    if avrae_resolved_since_prior:
        return ''

    # If prior DM response contained the target's name + a reaction verb,
    # narrative resolution likely happened.
    if prior_target_hints and _has_reaction_verbs(prior_dm_response, prior_target_hints):
        return ''

    # Current turn intent must be a scene-shift to fire the directive.
    # (If player is following up with another combat-intent action, that's a
    # continuation, not a godmode escape.)
    if intent_current != INTENT_SCENE_SHIFT:
        return ''

    # All gates passed: we have an unresolved combat commitment + a scene shift.
    return _COMMITMENT_DIRECTIVE_BODY
```

### 5.3 New regex: SCENE_SHIFT_RX

Matches verbs that indicate the player is moving away from the current scene/context:

```
\b(leave|exit|depart|head\s+(?:to|toward|out)|walk\s+(?:away|out|back)|
   go\s+(?:outside|inside|to|back)|move\s+on|continue\s+(?:on|forward)|
   travel|return\s+to|step\s+out|walk\s+off|disengage)\b
```

Validated against false positives in tests (e.g., "leave the door open" should NOT match, "head into the cave" SHOULD match). Iterate based on observed misclassifications.

### 5.4 Avrae buffer drain check

```python
def avrae_resolved_since_prior(buffer, actor_name, prior_turn_ts):
    """Return True if any combat event for this actor landed since prior turn."""
    events = buffer.recent(actor_name)
    return any(
        ev.get('kind') in ('attack', 'cast', 'damage')
        and ev.get('ts', 0) > prior_turn_ts
        for ev in events
    )
```

### 5.5 Reaction-verb check (heuristic)

```python
_REACTION_VERBS = re.compile(
    r'\b(dodges?|blocks?|parries|deflects?|falls?|crumples?|reels?|'
    r'staggers?|retreats?|backs?\s+away|laughs?|sneers?|snarls?|'
    r'roars?|charges?|swings?\s+back|retaliates?|counters?|'
    r'slumps?|collapses?|drops?\s+(?:to|the))\b',
    re.IGNORECASE,
)

def _has_reaction_verbs(dm_text, target_names):
    if not dm_text or not target_names:
        return False
    for name in target_names:
        # Look for target name within ~120 chars of a reaction verb.
        for match in _REACTION_VERBS.finditer(dm_text):
            window_start = max(0, match.start() - 120)
            window_end = min(len(dm_text), match.end() + 120)
            if name.lower() in dm_text[window_start:window_end].lower():
                return True
    return False
```

Heuristic — false positives possible (DM mentions reaction-verbs unrelated to the target). v1 acceptance criteria: the heuristic ERRS toward "resolved" (false negatives on detection are worse for godmode prevention than false positives).

---

## 6. Resolution / directive layer

### 6.1 Directive body (proposed)

```
=== UNRESOLVED COMMITMENT ===
The player has committed to an action this turn that was not resolved last turn:
  Prior action: {prior_action_text}
  Current action: {current_action_text}

The current action implies a scene shift away from the prior commitment. The world cannot honor both. Choose ONE this turn:
  (a) Narrate the prior action's consequence first — what the target did in response, what landed or didn't, who reacted how. Then handle the new action's consequence (it may or may not be possible, given the prior outcome).
  (b) Refuse the new action explicitly through an in-fiction beat — the prior commitment has the floor (e.g., the target retaliates before the player can leave, the bouncers move to block the exit, the player is mid-swing and can't pivot mid-combat).
  (c) Require a roll for the new action that costs the player something (e.g., disengage check at disadvantage, opportunity attack from the target, stealth roll to leave unnoticed).

Do NOT silently accept both as if no contradiction exists. The player's prior commitment is the one with weight; the current action is being attempted in its shadow.
```

### 6.2 Composition order

Renders AFTER consequence directive, BEFORE end of system prompt. In `build_dm_context`:

```
{...}{consequence_block}{commitment_block}
```

Reasoning: commitment is the most immediate-stakes directive — it constrains *this exact turn's* shape. Consequence surfacing colors NPC posture; commitment dictates what kinds of moves are even allowed. Cleanest as the final tactical band.

### 6.3 Update on emit

No state mutation on emit. The directive is purely advisory — it shapes the LLM's response but doesn't write anything. Logging only:

```
commitment_directive: campaign={X} prior_intent={Y} current_intent={Z}
                       reason=unresolved_combat npcs={[...]}
```

---

## 7. Failure modes + mitigations

1. **False positives on legitimate scene shifts.** Player narrates "I draw my dagger" purely for atmosphere ("I draw my dagger and sit by the fire"), then next turn "I head to the inn" — the directive fires inappropriately.
   *Mitigation:* COMBAT_RX requires concrete attack verbs (`attack`, `swing`, `strike`, `stab`, `cast`, `hit`), not just `draw`. "I draw my dagger and sit" → INTENT_SOCIAL or INTENT_TRIVIAL, not COMBAT. Directive doesn't fire.

2. **False negatives — DM narration that resolved without using reaction verbs.** Reaction-verb regex misses subtle resolutions ("Garrick's eyes flash but he holds his ground").
   *Mitigation:* False negatives are tolerated in v1 because they err toward letting things through. Pattern-tune regex from log analysis. Eventual v2 could LLM-judge resolution, but that's a 2x cost not worth paying for v1 precision.

3. **Player explicitly retracts prior action.** "Wait, never mind, I sheathe my blade and step back."
   *Mitigation:* The current turn's intent classifier should pick this up as INTENT_TRIVIAL or INTENT_SOCIAL, not INTENT_SCENE_SHIFT. If SCENE_SHIFT_RX matches falsely, that's a regex bug to fix. Generally: explicit retraction language ("never mind", "I change my mind", "actually") could be added to a dedicated retraction regex that suppresses the directive.

4. **Multi-actor scenarios.** Player A swings at NPC, Player B then says "I leave." The directive shouldn't fire on B's action because A's commitment is A's, not B's.
   *Mitigation:* In v1, scope the prior-intent check to the SAME actor. RollBuffer is per-actor; intent classification is per-message. Multi-actor solo case is the only one v1 handles cleanly; multi-actor multiplayer requires actor binding (Phase 6 — already shipped, can be reused).

5. **Avrae lag.** Avrae's roll arrives slightly after the player's "I leave" turn, making the buffer-drain check return False even though resolution is in flight.
   *Mitigation:* `RollBuffer` has 75s TTL; if Avrae responded within that window, the event is in the buffer when we check. If Avrae genuinely didn't respond, that's the godmode case the spec is meant to catch. Acceptable.

6. **Directive over-fires across turns.** The commitment was acknowledged turn N+1, but turn N+2 still classifies turn N's action as unresolved.
   *Mitigation:* The directive only looks at the IMMEDIATELY PRIOR turn (`scene_state.last_player_action`), so once turn N+1 happens, turn N is no longer the comparison target. Single-turn lookback is the simplification that prevents this.

7. **Mode-flip race.** Player swings dagger at barkeep, AUTO_EXECUTE emits MODE|combat in the same turn, mode flips to combat AFTER the directive computation. Next turn, mode is combat but the directive still wants to fire on the prior commitment.
   *Mitigation:* If mode is now combat and the player is taking another COMBAT-intent action, that's a continuation, not a godmode escape. Directive only fires when current intent is SCENE_SHIFT. If mode is combat and current intent is SCENE_SHIFT, the directive should still fire (combat shouldn't allow free disengagement). The spec's directive body addresses this case.

---

## 8. Test plan (proposed)

### 8.1 Engine layer (`test_commitment_directive.py`)

- No prior intent (first turn) → returns `''`.
- Prior intent = COMBAT, current = SCENE_SHIFT, no Avrae event, no reaction verbs → directive fires.
- Prior intent = COMBAT, current = SCENE_SHIFT, Avrae event in buffer → returns `''`.
- Prior intent = COMBAT, current = SCENE_SHIFT, prior DM response has reaction verb near target name → returns `''`.
- Prior intent = COMBAT, current = COMBAT (continuation) → returns `''`.
- Prior intent = COMBAT, current = SOCIAL → returns `''` (only SCENE_SHIFT triggers).
- Prior intent = SOCIAL, current = SCENE_SHIFT → returns `''` (only COMBAT prior triggers in v1).
- SCENE_SHIFT regex: positive cases ("I leave", "I head to the inn", "I walk away") and negative cases ("leave the door open", "head off the spear", "I head into the conversation").
- Reaction-verb proximity check: target name within 120 chars of reaction verb returns True; outside window returns False.

### 8.2 Integration test (light)

- Synthetic state: `scene_state.last_player_action = "I swing my dagger at Garrick"`, current player text = "I head outside to help the child", empty Avrae buffer for Donovan, prior DM response empty. Directive fires, log line emits.

### 8.3 Live verification

After v1 ships, replay Jordan's exact godmode test (swing at barkeep → next turn help child outside). Expected: `godmode_gap` log fires (already in place), `commitment_directive: ...` log fires, narration shows DM resolving the prior swing OR refusing the disengagement.

---

## 9. Migration impact

**Schema changes:** None in v1.

**Code additions:**
- New regex constant `SCENE_SHIFT_RX` and `_REACTION_VERBS` in `dnd_orchestration.py`.
- New constant `INTENT_SCENE_SHIFT` if not already present (or add a `is_scene_shift_intent(text)` boolean helper).
- New function `compute_commitment_directive(...)` in `dnd_orchestration.py`.
- New helper `avrae_resolved_since_prior(buffer, actor_name, ts)`.
- New helper `_has_reaction_verbs(dm_text, target_names)`.
- New `commitment_directive=""` kwarg in `build_dm_context`.
- New `=== UNRESOLVED COMMITMENT ===` block render in `build_dm_context`.
- New `commitment_directive:` log line in `dm_respond`.

**Cross-version safety:** No schema = no migration risk. Old code without the new directive renders the prompt without the block (block is empty when unset). Forward-only.

---

## 10. Out of scope (separate specs / separate layers)

- **RISKY/CONTESTED commitment resolution.** Pickpocket then leave; intimidate then walk away. Real cases but harder to detect. v2.
- **Multi-turn commitment chains.** Player swings turn N, says "wait, let me think" turn N+1, "I leave" turn N+2. Single-turn lookback won't catch this. v2 if observed in logs.
- **NPC-side commitment resolution.** NPC vows revenge in DM narration; player ignores it. Different shape — captured by consequence surfacing, not committed-action resolution.
- **Deterministic mode flip on COMBAT intent.** Sister architecture decision. Filed for separate review (§11.4). If we adopted it, the commitment directive's COMBAT-prior check would be partially redundant (mode would already be combat, and the mode-driven constraint could fire).
- **LLM-judged resolution detection.** A second LLM call to read the prior DM response and decide "did this resolve the player's prior commitment?" Higher precision than regex, higher cost. Defer to v2 if regex precision is insufficient in observed logs.
- **Player-side retraction grammar.** Detect "wait, never mind" / "I change my mind" / "actually..." as explicit suppressions of the directive. Could be a small regex addition; filed for v1 polish.
- **Turn-counter integration.** The consequence layer's `turn_counter` could be used here to bound "prior turn" temporally. v1 uses `last_player_action` (single-step lookback) without explicit turn numbering.

---

## 11. Decision points needing review

These are the surfaces where Jordan's call shapes the spec. I'd lean toward the proposal in §1 for each, but flagging explicitly so nothing ships on my unilateral choice.

1. **Scope: COMBAT only, or include RISKY/CONTESTED?** v1 proposed: COMBAT only. Open: should "I pickpocket the merchant" then "I leave the marketplace" also fire the directive? Cost: more false positives (legitimate stealth/social plays look like commitments). Benefit: broader godmode coverage.

2. **Resolution-verb heuristic OR LLM-judged?** v1 proposed: regex-based reaction verbs. Open: the regex will have false negatives (DM resolves subtly without listed verbs). Is that acceptable, or should we pay for a second LLM call to judge resolution?

3. **Schema: persist `last_player_intent` in `dnd_scene_state`, or recompute from `last_player_action` each turn?** v1 proposed: recompute (no schema change). Open: re-running the classifier is cheap but adds a re-derivation step; a persisted column is cleaner for debugging. Trade-off small either way.

4. **Sister decision: deterministic mode flip on COMBAT intent.** Out of scope for THIS spec, but the godmode failure mode is partially the consequence of NOT having this. If we add deterministic mode flip, mode='combat' becomes a structural barrier to scene shifts — which is its own design choice (Avrae's `!init begin` is currently the canonical combat-mode trigger; auto-flipping on player intent would diverge). Worth deciding alongside this spec.

5. **Directive strength: "must" vs "should consider".** v1 proposed: "must choose one of (a)/(b)/(c), do NOT silently accept both." Open: aggressive phrasing risks the LLM mechanically refusing reasonable plays. Softer phrasing risks the LLM ignoring the directive. Same calibration problem as pacing/central-thread initial wording.

6. **Single-turn vs multi-turn lookback.** v1 proposed: single-turn (only the immediately prior turn). Open: multi-turn would catch slower escapes ("I attack, I think, I leave") but adds complexity. Defer to v2 unless observed friction shows the single-turn case is insufficient.

7. **Where does `prior_dm_response` come from?** The reaction-verb heuristic needs the prior DM response text. `dm_respond` doesn't currently hold this; it'd need to be passed in or pulled from chroma. Implementation detail but worth surfacing — if the answer is "we don't have it cleanly," then resolution detection falls back to Avrae-event-only, which weakens v1 coverage.

8. **Composition order: after consequence, before philosophy?** v1 proposed: same band as pacing/central-thread/consequence (after consequence, before any philosophy interpretation). Open: should commitment directive come BEFORE consequence (commitment is more immediate) or AFTER (consequence is broader context for the move)?

If §1's proposed decisions need to change, that's a higher-order revision — surface those first before working through the open questions.

---

## Appendix — relationship to other layers

- **Consequence surfacing (Session 16, shipped).** Adjacent. Consequence surfacing handles accumulated weight across turns ("the world remembers what you did"). Committed-action resolution handles immediate-turn stakes ("the world demands resolution of what you just committed to"). Both target THE_GOAL "choices should matter" — different temporal scopes.
- **Phase 4 — Narrative state consistency repair.** This spec is one slice of Phase 4. Narrative consistency repair was always going to need both forward-looking (this spec) and backward-looking (retroactive repair when LLM commits a fictional fact) layers. Forward is easier and ships first.
- **Reputation / faction layer.** Group-level memory, separate concern. Does not interact directly.
- **Curiosity reward layer.** Separate mechanism (knowledge tier). Does not interact directly.
- **Memory tiering / arc summarization (Phase 4).** Larger Phase 4 scope. The committed-action layer's signals (intent, commitment, resolution) could feed the summarization layer's "what mattered this session?" pass. Filed for v2 of memory tiering.

**Filed, not sequenced** — per `feedback_no_pre_sequencing.md`. This spec is one of multiple candidate next layers; ordering is re-decided after each ship's logs accumulate enough signal to inform the next pick.
