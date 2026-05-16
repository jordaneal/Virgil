# VIRGIL_MASTER.md — S45 Delta Patches

**These are the three targeted updates to merge into the existing canonical VIRGIL_MASTER.md.** The bulk of the doc (system environment, SQLite schema, design tracks, phase status table, architectural invariants 95% unchanged, etc.) did not change in the S33-S45 arc. Only the items below need editing.

Apply by editing the existing file in place — do NOT replace the whole file.

---

## PATCH 1 — Header stamp refresh

**Find this block (lines ~1-3):**

```
# VIRGIL MASTER

**Current System State and Architecture**
Last updated: May 9, 2026 (S31 — ROADMAP 4c ships: `COMMANDS_PIN_BODY` pinned in `#commands` via `/setup`; `/dmhelp` rewired to runtime-fresh COMMANDS.md read per §66 — no more hand-maintained drift. Bug 1 architecture locked through spec discussion: footer-as-orchestration-state shift identified, phase-1/phase-2 telemetry-first split agreed, three new `footer_actor_changed` / `directive_bound_to_footer_actor` / `directive_creation_skipped_no_footer` log lines candidate. S30 — small-items batch shipped (Bug 2 max_tokens, F-29 titled-NPC, S26 commitment+empty diagnostic, npc_token_prefix_match) and Doc-catalog trim (ROADMAP −40KB, FAILURES −7KB, DOCTRINE −1KB). Footings queue EMPTY.)
```

**Replace with:**

```
# VIRGIL MASTER

**Current System State and Architecture**
Last updated: May 11, 2026 (S45 — multiplayer-fixes plan v3 functionally complete. Seven ships closed across S33-S45 arc: Ship 1 + Ship A resolution binding, Ship 2 scene canon (§76 anchored), Ship 3 NPC state-sync via §1b suggester pivot post-Avrae-bot-filter HALT, S42 listener edge-case verification, S43 dumb combat (§77 anchored — atmospheric continuity not adjudication), S44 combat narration prompt purity 10-block suppression set, S45 combat-boundary hardening bundle (§78 anchored — mode-transition state-reset surfaces, four-layer rule: mechanical cleanup + narrative buffer reset + transitional silence + boundary atmospheric closeout). Four doctrines anchored, two-layer enforcement composition (instruction-side + information-side) structurally embedded in §78 layer 4. Per HYBRID_COMBAT_NOTES.md v3 §3.1, next phase is multi-hour playtest per PLAYTEST_OBSERVATION_FRAMEWORK.md — the gate for any further architectural commits.)
```

---

## PATCH 2 — Add S43-S45 entries to Active scripts code-block + new subsection

**Find this code block in Section 2 (Virgil DM Discord, "Active scripts"):**

```
dnd_engine.py              narrative core, scene state, prompt construction,
                            canonical NPC/location accessors (Phase 12)
dnd_orchestration.py       character context + roll discipline rules engine
avrae_listener.py          Avrae embed parser + RollBuffer
discord_dnd_bot.py         Discord transport layer
```

**Replace with:**

```
dnd_engine.py              narrative core, scene state, prompt construction,
                            canonical NPC/location accessors (Phase 12);
                            S43-S45 combat narration suppression flag +
                            S45 reset_narrative_buffers_on_combat_exit helper
dnd_orchestration.py       character context + roll discipline rules engine;
                            S43-S45 10th §59 sibling cluster: _hp_state +
                            compute_combat_state_transitions +
                            compute_combat_narration_directive (4 kinds:
                            ROUND_START / BLOODIED / DOWNED / COMBAT_END) +
                            _COMBAT_NARRATION_INVARIANTS constant
avrae_listener.py          Avrae embed parser + RollBuffer;
                            S42 _DICE_NOTATION constant (kh1/kl1 modifiers) +
                            per-target sub-attack walker
discord_dnd_bot.py         Discord transport layer;
                            S43-S45 _dispatch_combat_narration async wrapper +
                            ROUND_START + BLOODIED + DOWNED + COMBAT_END
                            trigger sites + v1+v2 init-setup silence gates
```

**Then immediately after the closing `` ``` `` of that Active scripts block, INSERT this new subsection** (before the `---` separator and `## 3. Core Design Principles` header):

```markdown

### Combat narration dispatch (S43-S45)

The dumb-combat narration system in `discord_dnd_bot.py` + `dnd_orchestration.py` is the 10th §59 sibling cluster. Triggers on four combat-mode state transitions: `ROUND_START` (Avrae round-transition embed), `BLOODIED_THRESHOLD_CROSSED` (combatant HP crosses 50%), `COMBATANT_DOWNED` (HP → 0), `COMBAT_END` (boundary closeout from `!init end`). Fifth trigger `DEATH_SAVE_EVENT_START` filed v1.x pending PC-fixture availability. Each trigger dispatches `_dispatch_combat_narration` → `compute_combat_narration_directive` → `_dm_respond_and_post` with `suppress_for_combat_narration=True`.

**Two-layer enforcement (§77 cliff-edge protection):**
- **Instruction-side (S43):** `_COMBAT_NARRATION_INVARIANTS` constant injected into prompt body — MUST/MUST-NOT clauses prevent narration from establishing new mechanical state, declaring kills/unconsciousness before listener confirms, inventing damage, inferring morale or tactical intent. COMBAT_END kind carries additional verbatim phantom-NPC negative clauses ("no thug emerges from the shadows / no companions appearing to congratulate") naming specific prior verify drift modes.
- **Information-side (S44):** `suppress_for_combat_narration: bool` param threaded through `_dispatch_combat_narration` → `_dm_respond_and_post` → `dm_respond` → `build_dm_context`. When True, 10 context blocks skip assembly: chroma session retrieval, chroma knowledge corpus, companions, recent_npcs_line, quests, inventory, central_thread, pending_consequences, unresolved_commitment, current_scene.

**Boundary state-reset (S45, §78 layer 1+2+3+4):**
- **Layer 1 (mechanical cleanup):** existing `set_scene_mode('exploration')` + `clear_active_turn` + `clear_combatants` in `_handle_init_event` evt_type='end'.
- **Layer 2 (narrative buffer reset):** new `reset_narrative_buffers_on_combat_exit(campaign_id)` helper in `dnd_engine.py` — single writer for boundary reset, §17-compatible. Writes synthesized neutral closeout to `campaigns.current_scene` + `dnd_scene_state.last_dm_response` + `dnd_scene_state.last_player_action` after mechanical cleanup. Idempotent.
- **Layer 3 (transitional silence):** v2 primary gate in `on_message` (`if mode='combat' AND no active_turn: react ⏳ and return`) + v1 defense-in-depth gate inside `_dm_respond_and_post` (force `suppress_for_combat_narration=True` under same condition) for non-`on_message` call sites. Closes premature combat narration from bare Avrae disambiguation replies during init-setup.
- **Layer 4 (boundary atmospheric closeout):** COMBAT_END as 4th kind in `compute_combat_narration_directive`; dispatched from `_handle_init_event` evt_type='end' with `combat_state_override` + `scene_override` decoupling dispatch from post-cleanup DB state. Carries both §77 instruction-side MUST/MUST-NOT clauses + S44 information-side 10-block suppression.

Mode-flip wired via existing S7 Phase 1.4 FSM. Doctrine §77 governs WHAT can be narrated (atmospheric continuity, not adjudication); §78 governs WHEN narration is structurally appropriate (mode-transition state-reset). Future F-55 combat ships (#5.2 NPC Turn Automation, #5.3 Combat Cockpit, #5.4 Intent-to-Avrae Resolver) inherit both lines. `_handle_rest_event` (!lr/!sr) is a filed §78 parallel-surface candidate — same four-layer audit applies if drift surfaces in playtest.
```

---

## PATCH 3 — Authority invariant S41 reinforcement clause

**In Section 4 — Architectural Invariants, find the "Authority invariants" subsection, specifically this bullet:**

```
- **The bot does not emit `!`-prefixed commands to Avrae.** Only the LLM emits Avrae commands, and only via its narration response on the player-facing channel. The bot itself is read-only on the Avrae channel — no `bot.send("!attack ...")`, no programmatic `!init list` refresh, no bot-driven `!`-commands of any shape. New mechanical-command surfaces are added to the LLM's emission repertoire (e.g. Shape B init orchestration in S20), never as new bot→Avrae write paths. **This invariant constrains bot-side Avrae writes only.** It does NOT constrain transport-layer input filtering on the player-narration channel (e.g. Phase 2A.3's off-turn ⏳ drop, which is a routing decision the transport layer is allowed to make).
```

**Replace with:**

```
- **The bot does not emit `!`-prefixed commands to Avrae.** Only the LLM emits Avrae commands, and only via its narration response on the player-facing channel. The bot itself is read-only on the Avrae channel — no `bot.send("!attack ...")`, no programmatic `!init list` refresh, no bot-driven `!`-commands of any shape. New mechanical-command surfaces are added to the LLM's emission repertoire (e.g. Shape B init orchestration in S20), never as new bot→Avrae write paths. **This invariant constrains bot-side Avrae writes only.** It does NOT constrain transport-layer input filtering on the player-narration channel (e.g. Phase 2A.3's off-turn ⏳ drop, which is a routing decision the transport layer is allowed to make). **S41 empirical reinforcement:** Avrae structurally filters bot-emitted `!`-commands at its parser — identical commands mutate state when human-typed, silently filtered when bot-typed. Confirmed via live verify. Project-side proposal of mechanical state mutation routes through the §1b validated-suggester pattern (Ship 3 NPC state-sync is the second project instance after Track 6 #5.1 SRD resolver).
```

---

## PATCH 4 — Add S45 boundary writer to Single write paths list

**In Section 4 — State integrity invariants, find the "Single write paths per field" bulleted list. After the existing last entry (`npc_register_avrae_madd()`), add:**

```
  - `reset_narrative_buffers_on_combat_exit()` (S45) — sole writer of the synthesized neutral closeout to `campaigns.current_scene` + `dnd_scene_state.last_dm_response` + `dnd_scene_state.last_player_action` at combat-end boundary. §78 layer 2 implementation. Idempotent.
```

---

## PATCH 5 — Extend Section 3 Core Design Principles with §77 + §78

**In Section 3 — Core Design Principles (non-negotiable), find the last bullet:**

```
- Canonical world state (NPCs, locations) is authoritative; retrieval is not.
```

**Add these two bullets immediately after it:**

```
- Combat narration is atmospheric continuity, not adjudication (§77).
- Mode transitions are state-reset surfaces; mode-flag-only transitions are structurally incomplete (§78).
```

---

## Notes on this delta artifact

- All five patches together represent the complete S33-S45 changes to VIRGIL_MASTER.md.
- The bulk of the file (System Environment, SQLite Schema, Phase Status, Design Tracks, all OOC/SRD/Time/Adjudication/Arbitration invariants) did not change in this arc and should NOT be touched.
- Patch 2 has the most weight — it adds the new "Combat narration dispatch (S43-S45)" subsection to Section 2 documenting the 10th §59 sibling cluster.
- After Jordan applies these patches to the canonical server file at `/home/jordaneal/virgil-docs/VIRGIL_MASTER.md`, the next `push-all-to-pc.sh` will sync to PC.
- This artifact persists in the chat history as durable backup if sync gets clobbered again — re-apply from chat if needed.
