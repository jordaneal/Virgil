# VIRGIL_MASTER.md — S50 Delta Patches

**Targeted update to merge into the existing canonical VIRGIL_MASTER.md.** Single ship (COMBAT_END 0-action framing fix, §78.6 layer-4 render-vs-marker anchoring). First doctrine-touching ship in the S45→S48→S49→S50 arc — new sub-section §78.6 added to DOCTRINE.md.

Apply by editing the existing file in place — do NOT replace the whole file. This delta is independent of the S45/S47/S49 delta patches (those can be applied first or in parallel).

---

## PATCH 1 — Header stamp refresh

**Find this block (lines ~1-3):**

```
# VIRGIL MASTER

**Current System State and Architecture**
Last updated: May 12, 2026 (S49 — pre-playtest cleanup ship: RollBuffer drain at rest-event boundary ...)
```

(Whatever header the canonical file currently carries.)

**Replace with:**

```
# VIRGIL MASTER

**Current System State and Architecture**
Last updated: May 12, 2026 (S50 — pre-playtest cleanup ship: COMBAT_END 0-action framing fix. §78.6 anchored as layer-4 render-vs-marker sub-section under §78. Per-guild beat counter (in-memory dict keyed by guild_id) tracks BLOODIED_THRESHOLD_CROSSED + COMBATANT_DOWNED dispatches during combat; ROUND_START + COMBAT_END do not increment. At !init end, COMBAT_END dispatch branches on beat count: 0 → deterministic neutral closeout ("Combat ends. The moment passes.") posted directly to #dm-narration; ≥1 → existing S45-F LLM dispatch unchanged. Closes the symptom from S48 verify walk where the LLM produced "clash of steel and shouted commands fade into a heavy silence" on a 0-action combat where no clash or shouts occurred. Telemetry primitives: `combat_end_zero_action:` and `combat_end_llm_dispatch:` + `combat_beat_incremented:`. Tests: `test_combat_end_zero_action.py` (14 assertions). Doctrine refinement, not amendment — §78's four-layer rule is unchanged; §78.6 refines layer-4's internal structure (render-mode vs marker-mode is content-conditioned within layer 4, not a layer-4 elision).)
```

---

## PATCH 2 — Add §78.6 reference to Section 3 Core Design Principles

**In Section 3 — Core Design Principles, find the bullet pair S45 delta added (post-S45-delta state):**

```
- Combat narration is atmospheric continuity, not adjudication (§77).
- Mode transitions are state-reset surfaces; mode-flag-only transitions are structurally incomplete (§78).
```

**Add a third bullet immediately after them:**

```
- Layer-4 boundary atmospheric closeout renders only when there is content to render; 0-action sessions fall back to a deterministic neutral marker (§78.6).
```

---

## PATCH 3 — Extend the §78 layer-4 description in the Combat narration dispatch subsection

**This patch applies AFTER S45 delta PATCH 2 has landed** (it amends the "Layer 4 (boundary atmospheric closeout)" bullet S45 introduced).

**In Section 2 — "Combat narration dispatch (S43-S45)" subsection, find the "Layer 4 (boundary atmospheric closeout)" bullet:**

```
- **Layer 4 (boundary atmospheric closeout):** COMBAT_END as 4th kind in `compute_combat_narration_directive`; dispatched from `_handle_init_event` evt_type='end' with `combat_state_override` + `scene_override` decoupling dispatch from post-cleanup DB state. Carries both §77 instruction-side MUST/MUST-NOT clauses + S44 information-side 10-block suppression.
```

**Replace with:**

```
- **Layer 4 (boundary atmospheric closeout):** COMBAT_END as 4th kind in `compute_combat_narration_directive`; dispatched from `_handle_init_event` evt_type='end' with `combat_state_override` + `scene_override` decoupling dispatch from post-cleanup DB state. Carries both §77 instruction-side MUST/MUST-NOT clauses + S44 information-side 10-block suppression. **§78.6 render-vs-marker branching (S50):** layer-4's LLM render is conditional on content-to-render; the boundary marker itself is unconditional. Per-guild beat counter (`_combat_beat_counter` dict in `discord_dnd_bot.py`) increments on BLOODIED_THRESHOLD_CROSSED + COMBATANT_DOWNED dispatches during combat (ROUND_START does not increment; COMBAT_END reads and branches). At COMBAT_END dispatch time: 0 beats → deterministic neutral closeout (`_COMBAT_END_NEUTRAL_CLOSEOUT = "Combat ends. The moment passes."`) posted directly to #dm-narration; ≥1 beats → existing S45-F LLM dispatch unchanged. Counter reset on `!init begin`, cleared after dispatch. Telemetry: `combat_end_zero_action:` and `combat_end_llm_dispatch:` distinguish the two paths; `combat_beat_incremented:` traces each per-beat fire.
```

---

## PATCH 4 — Active scripts code-block update

**This patch applies AFTER S45 delta PATCH 2 AND S47 delta PATCH 3 AND S49 delta PATCH 3 have landed** (it further amends the `discord_dnd_bot.py` entry).

**Find the `discord_dnd_bot.py` entry (post-S49-delta state):**

```
discord_dnd_bot.py         Discord transport layer;
                            S43-S45 _dispatch_combat_narration async wrapper +
                            ROUND_START + BLOODIED + DOWNED + COMBAT_END
                            trigger sites + v1+v2 init-setup silence gates;
                            S47-arc RollBuffer drain in _handle_init_event
                            evt_type='end' (§78 layer-1 in-memory substrate);
                            S49 mode-agnostic RollBuffer drain in
                            _handle_rest_event (§78 layer-1 at rest boundary)
```

**Replace with:**

```
discord_dnd_bot.py         Discord transport layer;
                            S43-S45 _dispatch_combat_narration async wrapper +
                            ROUND_START + BLOODIED + DOWNED + COMBAT_END
                            trigger sites + v1+v2 init-setup silence gates;
                            S47-arc RollBuffer drain in _handle_init_event
                            evt_type='end' (§78 layer-1 in-memory substrate);
                            S49 mode-agnostic RollBuffer drain in
                            _handle_rest_event (§78 layer-1 at rest boundary);
                            S50 per-guild combat beat counter + COMBAT_END
                            0-action neutral closeout branch (§78.6 layer-4
                            render-vs-marker)
```

---

## Notes on this delta artifact

- This delta is independent of the S45/S47/S49 delta patches — apply in any order. PATCH 1 (header stamp) is standalone. PATCH 2 is a fresh insertion (no dependency). PATCH 3 + PATCH 4 reference subsections / code-blocks introduced/extended by prior deltas; apply prior deltas first if all are pending.
- **First doctrine-touching ship in the S45→S50 arc.** S45 anchored §78 + the four-layer rule; S48 + S49 promoted §78.5 (substrate-agnostic application) without changing the rule itself; S50 promotes §78.6 (layer-4 render-vs-marker) as the second sub-section. The four-layer rule remains unchanged at the §78 root.
- Tests: `test_combat_end_zero_action.py` (14 assertions) covers beat counter unit behavior + guild isolation + neutral closeout constant validation + source-text regression guards on the wiring (reset on begin / increment gated to BLOODIED+DOWNED / branch at COMBAT_END / cleanup after) + full lifecycle simulation.
- **Symptom evidence:** `dnd_engine.log` 2026-05-12T17:00:11 `combat_narration_fired: kind=COMBAT_END fired=1` corresponds to the S48 verify walk's COMBAT_END narration. That walk produced "The clash of steel and shouted commands fade into a heavy silence, the dust settling on the cobblestones as the last echoes die away. Donovan Ruby stands steady, his breath coming in measured pulls, the room now still and empty." — vivid framing drift on a 0-action combat (Donovan rolled `!init join` + `!check perception` then `!init end`, with no attacks, no clashes, no shouts, no dust). Post-S50: same walk would post the deterministic neutral closeout instead.
- **Deferred follow-up surfaces** (filed per §78.6 v1.x candidate, observe playtest first per F-60): ROUND_START on 0-action rounds (currently uses conservative environment-focused framing — less drift-prone but same shape applies); future mode-transition surfaces (exploration→travel, downtime→exploration, social→combat) when those land.
- This artifact persists in the chat history as durable backup if sync gets clobbered — re-apply from chat if needed.
