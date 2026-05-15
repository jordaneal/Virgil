# VIRGIL_MASTER.md — S49 Delta Patches

**Targeted update to merge into the existing canonical VIRGIL_MASTER.md.** Single ship (RollBuffer drain at rest-event boundary, mode-agnostic) — §78 layer-1 third-instance application, sibling pattern to S48 init-end drain on the rest-event substrate.

Apply by editing the existing file in place — do NOT replace the whole file. This delta is independent of the S45 and S47 delta patches (those can be applied first or in parallel).

---

## PATCH 1 — Header stamp refresh

**Find this block (lines ~1-3):**

```
# VIRGIL MASTER

**Current System State and Architecture**
Last updated: May 12, 2026 (S47-arc — pre-playtest cleanup ship: RollBuffer drain on `!init end`. ...)
```

(Whatever header the canonical file currently carries — S47 delta will have refreshed it if applied; otherwise it's the older S45 or S31 stamp.)

**Replace with:**

```
# VIRGIL MASTER

**Current System State and Architecture**
Last updated: May 12, 2026 (S49 — pre-playtest cleanup ship: RollBuffer drain at rest-event boundary (mode-agnostic). §78 layer-1 third-instance application after S45 (DB-side narrative buffer reset at `!init end`) and S48 (in-memory RollBuffer drain at `!init end`). `buffer.clear(message.guild.id)` called unconditionally in `_handle_rest_event` after `advance_time`, regardless of current mode — closes the mode-agnostic substrate-completion gap surfaced by S48 recon Phase 5 #1. Recon-side evidence: 6 production `_handle_rest_event` firings across the journal, all extracted actor to `'someone'` fallback, zero observed `buffer.consume` hits on `roll_kinds=['rest']`. Current serendipity-protection (Avrae's `!lr`/`!sr` embed format not parsing to real PC names) is structural unreliability, not safety — drain fires unconditionally before the serendipity breaks. Combat-mode-branch §78 layer-2/4 audit gaps remain deferred per planner reconciliation; layers 2/4 wait until playtest produces visible symptom. Tests: `test_rest_event_rollbuffer_drain.py` (10 assertions). No new doctrine — §78 four-layer rule covers substrate-agnostically.)
```

---

## PATCH 2 — Extend the §78 layer-1 description in the Combat narration dispatch subsection

**This patch applies AFTER S45 delta PATCH 2 AND S47 delta PATCH 2 have landed** (it further amends the "Layer 1 (mechanical cleanup)" bullet introduced by S45 and extended by S47). If those deltas have not yet been applied, this patch should be inserted into the canonical file in the same section S45 PATCH 2 creates.

**In Section 2 — "Combat narration dispatch (S43-S45)" subsection, find the "Layer 1 (mechanical cleanup)" bullet (post-S47-delta state):**

```
- **Layer 1 (mechanical cleanup):** DB-side state: `set_scene_mode('exploration')` + `clear_active_turn` + `clear_combatants` in `_handle_init_event` evt_type='end'. **In-memory state (S47-arc):** `buffer.clear(guild_id)` drains the in-memory `RollBuffer` of stale combat-mechanical events (check/save/attack/cast/damage/roll) sibling to the S45 narrative buffer reset. ... Telemetry log line: `init_end_rollbuffer_drained: ...`.
```

**Replace with:**

```
- **Layer 1 (mechanical cleanup):** DB-side state: `set_scene_mode('exploration')` + `clear_active_turn` + `clear_combatants` in `_handle_init_event` evt_type='end'. **In-memory state at `!init end` (S47-arc):** `buffer.clear(guild_id)` drains the in-memory `RollBuffer` of stale combat-mechanical events (check/save/attack/cast/damage/roll) sibling to the S45 narrative buffer reset. Without this drain, mid-combat rolls persist across the boundary and surface on the next matching-actor turn — both in the `(N rolls in play)` footer artifact AND in the LLM prompt's `=== AVRAE EVENTS ===` block via `_format_avrae_events`. Telemetry log line: `init_end_rollbuffer_drained: campaign={N} guild={N} drained_count={N}`. **In-memory state at rest-event boundary (S49):** `buffer.clear(guild_id)` ALSO drains the buffer at the end of `_handle_rest_event` (after `advance_time`), unconditionally regardless of current mode. Every Avrae `!lr` / `!sr` lands in RollBuffer via `buffer.add` with `kind='rest'`; current serendipity-protection (actor-extraction fallback to `'someone'` at `avrae_listener.py:186`) keeps these entries from matching PC-actor consume filters, but that's structural unreliability not safety — if a future embed parses to a real PC name, the rest event would surface in the next matching-actor turn. Mode-agnostic placement closes the gap before the serendipity breaks. Telemetry log line: `rest_event_rollbuffer_drained: campaign={N} guild={N} drained_count={N} rest_kind={long rest|short rest|rest}`. `RollBuffer.size(guild_id)` (S47-arc addition) is the supporting accessor used by both drain sites — single accessor, single drain method, §17 single-write-path preserved on RollBuffer.
```

---

## PATCH 3 — Active scripts code-block update

**This patch applies AFTER S45 delta PATCH 2 AND S47 delta PATCH 3 have landed** (it further amends the `discord_dnd_bot.py` entry).

**Find the `discord_dnd_bot.py` entry (post-S47-delta state):**

```
discord_dnd_bot.py         Discord transport layer;
                            S43-S45 _dispatch_combat_narration async wrapper +
                            ROUND_START + BLOODIED + DOWNED + COMBAT_END
                            trigger sites + v1+v2 init-setup silence gates;
                            S47-arc RollBuffer drain in _handle_init_event
                            evt_type='end' (§78 layer-1 in-memory substrate)
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
                            _handle_rest_event (§78 layer-1 at rest boundary)
```

---

## Notes on this delta artifact

- This delta is independent of the S45 and S47 delta patches — apply in any order. PATCH 1 (header stamp) is standalone. PATCH 2 + PATCH 3 reference the subsection / code-block that S45's PATCH 2 introduces and S47's PATCH 2/3 extend; apply prior deltas first if all are pending.
- No new doctrine — §78's four-layer rule is substrate-agnostic; this is third-instance application (S45 DB-init-end → S48 in-memory-init-end → S49 in-memory-rest-event).
- Tests: `test_rest_event_rollbuffer_drain.py` (10 assertions) covers RollBuffer drain unit behavior + source-text regression guards for mode-agnostic placement + ordering after `advance_time` + telemetry log format guard.
- **Deferred follow-up:** combat-mode-branch §78 layer-2 (`reset_narrative_buffers_on_combat_exit` call inside `_handle_rest_event` combat branch) and layer-4 (`COMBAT_END`-or-equivalent dispatch) gaps surfaced by S48-arc recon remain unfilled. Decision: evolve from observed friction — the one Apr 30 09:36:49 combat-mode-branch firing produced no visible drift; future ship dispatches quickly if playtest surfaces it. Layer-4 may warrant a new `REST_END_FROM_COMBAT` directive kind with its own invariants rather than reusing `COMBAT_END` (different semantics: rest implies recovery, not combat resolution).
- **Recon side-finding:** `_handle_init_list_event` (`discord_dnd_bot.py:1809-1815`) is a candidate third combat-exit surface if a future init-list edit clears the last enemy without firing `!init end`. Out of scope for S49; filed for future audit pass.
- This artifact persists in the chat history as durable backup if sync gets clobbered — re-apply from chat if needed.
