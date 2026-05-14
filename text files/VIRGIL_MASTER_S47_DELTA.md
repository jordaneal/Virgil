# VIRGIL_MASTER.md — S47-arc Delta Patches

**Targeted update to merge into the existing canonical VIRGIL_MASTER.md.** Single ship (RollBuffer drain on `!init end`) — §78 layer-1 completion on the in-memory mechanical-event substrate, sibling to S45's DB-side narrative buffer reset.

Apply by editing the existing file in place — do NOT replace the whole file. This delta is independent of the S45 delta patches (those can be applied first or in parallel).

---

## PATCH 1 — Header stamp refresh

**Find this block (lines ~1-3):**

```
# VIRGIL MASTER

**Current System State and Architecture**
Last updated: May 11, 2026 (S45 — multiplayer-fixes plan v3 functionally complete. ...)
```

(Whatever header the canonical file currently carries — S45 delta will have refreshed it if applied; otherwise it's the older S31 stamp.)

**Replace with:**

```
# VIRGIL MASTER

**Current System State and Architecture**
Last updated: May 12, 2026 (S47-arc — pre-playtest cleanup ship: RollBuffer drain on `!init end`. §78 layer-1 second-instance, applying the four-layer rule to the in-memory mechanical-event substrate (sibling to S45's DB-side narrative buffer reset). `RollBuffer.size()` added for drain telemetry; `buffer.clear(guild_id)` called as sibling step to `reset_narrative_buffers_on_combat_exit` in `_handle_init_event` evt_type='end' path. Closes the symptom filed in S45 verify — Donovan's mid-combat check roll persisting across the boundary and surfacing in both the `(N rolls in play)` footer artifact AND the LLM prompt's `=== AVRAE EVENTS ===` block on the next matching-actor turn. Tests: `test_init_end_rollbuffer_drain.py` (10 assertions). No new doctrine — §78's four-layer rule covers it. `_handle_rest_event` (`!lr` / `!sr`) remains the filed parallel-surface candidate per S45 deferral note.)
```

---

## PATCH 2 — Extend the §78 layer-1 description in the Combat narration dispatch subsection

**This patch applies AFTER S45 delta PATCH 2 has landed** (it amends the new subsection that S45's PATCH 2 introduces). If the S45 delta has not yet been applied, this patch should be inserted into the canonical file in the same section S45 PATCH 2 creates.

**In Section 2 — "Combat narration dispatch (S43-S45)" subsection, find the "Layer 1 (mechanical cleanup)" bullet:**

```
- **Layer 1 (mechanical cleanup):** existing `set_scene_mode('exploration')` + `clear_active_turn` + `clear_combatants` in `_handle_init_event` evt_type='end'.
```

**Replace with:**

```
- **Layer 1 (mechanical cleanup):** DB-side state: `set_scene_mode('exploration')` + `clear_active_turn` + `clear_combatants` in `_handle_init_event` evt_type='end'. **In-memory state (S47-arc):** `buffer.clear(guild_id)` drains the in-memory `RollBuffer` of stale combat-mechanical events (check/save/attack/cast/damage/roll) sibling to the S45 narrative buffer reset. Without this drain, mid-combat rolls persist across the boundary and surface on the next matching-actor turn — both in the `(N rolls in play)` footer artifact AND in the LLM prompt's `=== AVRAE EVENTS ===` block via `_format_avrae_events` (the larger failure mode: post-combat narration treats stale rolls as freshly-happened, violating §77 renderer-not-ruler discipline). Telemetry log line: `init_end_rollbuffer_drained: campaign={N} guild={N} drained_count={N}`. `RollBuffer.size(guild_id)` is the supporting accessor — raw storage count (no sweep) used so telemetry reflects events being cleared, not post-TTL survivors.
```

---

## PATCH 3 — Active scripts code-block update

**This patch applies AFTER S45 delta PATCH 2 has landed** (it amends the avrae_listener.py + discord_dnd_bot.py entries S45 PATCH 2 introduces).

**Find the `avrae_listener.py` and `discord_dnd_bot.py` entries (post-S45-delta state):**

```
avrae_listener.py          Avrae embed parser + RollBuffer;
                            S42 _DICE_NOTATION constant (kh1/kl1 modifiers) +
                            per-target sub-attack walker
discord_dnd_bot.py         Discord transport layer;
                            S43-S45 _dispatch_combat_narration async wrapper +
                            ROUND_START + BLOODIED + DOWNED + COMBAT_END
                            trigger sites + v1+v2 init-setup silence gates
```

**Replace with:**

```
avrae_listener.py          Avrae embed parser + RollBuffer;
                            S42 _DICE_NOTATION constant (kh1/kl1 modifiers) +
                            per-target sub-attack walker;
                            S47-arc RollBuffer.size() accessor for drain telemetry
discord_dnd_bot.py         Discord transport layer;
                            S43-S45 _dispatch_combat_narration async wrapper +
                            ROUND_START + BLOODIED + DOWNED + COMBAT_END
                            trigger sites + v1+v2 init-setup silence gates;
                            S47-arc RollBuffer drain in _handle_init_event
                            evt_type='end' (§78 layer-1 in-memory substrate)
```

---

## Notes on this delta artifact

- This delta is independent of the S45 delta patches — apply in either order. PATCH 1 (header stamp) is standalone; PATCH 2 + PATCH 3 reference the subsection / code-block that S45's PATCH 2 introduces, so apply S45 first if both deltas are pending.
- No new doctrine — §78's four-layer rule already covers this; the ship is application, not amendment.
- Tests: `test_init_end_rollbuffer_drain.py` (10 assertions) covers RollBuffer drain unit behavior + source-order regression guards + telemetry log format guard.
- Filed parallel-surface follow-up: `_handle_rest_event` (Avrae `!lr` / `!sr`) — same §78 four-layer audit applies if drift surfaces in playtest. Already noted in S45 deferral; S47-arc does not change this.
- This artifact persists in the chat history as durable backup if sync gets clobbered — re-apply from chat if needed.
