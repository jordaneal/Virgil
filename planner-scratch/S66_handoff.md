# S66 Handoff — Tier 1 Cleanup, Batch 2

**Date:** 2026-05-14
**Session:** S66 (world-state-responds-to-narration layer)
**Pre-ship snapshot:** `/mnt/virgil_storage/archive/virgil_S66_preship.db` (20.7 MB, 2026-05-14T12:48 PDT)
**Discipline:** pre-ship snapshot + per-fix rollback notes + feature-disable readiness (carries from S65/S65.1).

---

## Fix Inventory (3 planned, 3 SHIPPED)

| Fix | Status | Outcome |
|---|---|---|
| Fix 1 — `/travel` duration floor + truthful embed | ✅ SHIPPED | Floor-at-1-phase rule applied at handler; truthful embed reports actual `(before → after)` phase delta; 52 adversarial tests green. |
| Fix 2 — F-031 quest delivery silent fail close | ✅ SHIPPED | `PARTY_STASH_BUCKET = '__party__'` sentinel introduced; `_do_quest_deliver` writes to it; truthful `#dm-aside` separates inserted/failed; `/inventory` surfaces party stash; 28 adversarial tests green. |
| Fix 3 — F-035 loot auto-claim with refusal | ✅ SHIPPED | Combat loot auto-claims to party stash at `mark_loot_surfaced` time; `/loot drop <item>` refusal slash; `compute_loot_directive` narration updated; 26 adversarial tests green. |

---

## Files Touched, LOC Delta Per Fix

| Fix | File | Lines changed | Notes |
|---|---|---|---|
| Fix 1 | `discord_dnd_bot.py` | +35 / -10 | `/travel` handler floor-at-1-phase logic; truthful embed with `(before_phase → after_phase)`; capture `TimeAdvancement` result. |
| Fix 1 | `test_travel_duration_floor.py` | +220 (new) | 52 adversarial tests: parse_elapsed canonical cases, floor logic, advance_time integration, sequential travel. |
| Fix 2 | `dnd_engine.py` | +10 / -0 | `PARTY_STASH_BUCKET = '__party__'` module-level constant; updated `add_item` docstring. |
| Fix 2 | `discord_dnd_bot.py` | +50 / -15 | Import `PARTY_STASH_BUCKET` + `remove_item`; `_do_quest_deliver` writes to party stash with truthful `inv_lines`/`inv_failed` split; `/inventory` surfaces party stash. |
| Fix 2 | `test_quest_delivery_party_stash.py` | +220 (new) | 28 adversarial tests across 8 categories. |
| Fix 3 | `dnd_engine.py` | +35 / -10 | At `mark_loot_surfaced` time, auto-claim each row's items into PARTY_STASH_BUCKET via `add_item`; `loot_auto_claimed` telemetry per fire. |
| Fix 3 | `dnd_orchestration.py` | +6 / -3 | `compute_loot_directive` narration rewritten: "items auto-claimed; use /loot drop to refuse." |
| Fix 3 | `discord_dnd_bot.py` | +95 / -0 | `/loot drop <item>` slash command with autocomplete; `_party_stash_autocomplete` helper. |
| Fix 3 | `test_loot_auto_claim.py` | +220 (new) | 26 adversarial tests across 8 categories. |

**Total new test assertions: 106** (52 + 28 + 26) across 3 new files.

---

## Fix 1 — `/travel` Duration Floor + Truthful Embed

### Phase A — Recon findings

- **Phase constant.** `PHASES = ('Morning', 'Midday', 'Afternoon', 'Evening', 'Night', 'Late Night')` — 6 phases per day, ~4 hours each. Confirmed at `dnd_engine.py:1697`.
- **`advance_time` callers.** 4 production sites: `/travel` (subject), `/advance` slash, Avrae long rest (1d, set_phase='Morning'), Avrae short rest (0,1). Only `/travel` needed the fix; the others use deterministic hardcoded deltas already.
- **Pre-existing parser.** `parse_elapsed(elapsed_str)` already handles canonical cases correctly: `'1 hour' → (0,1)`, `'4 hours' → (0,1)`, `'8 hours' → (0,2)`, `'1 day' → (1,0)`. The parser was fine; the call site was the gap.
- **Pre-S66 gap.** Call site: `if parsed is not None and parsed != (0, 0): advance_time(...)`. Sub-phase durations (`'5 minutes'` → `(0,0)`) and unparseable strings (`'banana'` → `None`) silently skipped `advance_time`. Net: `duration:"5 minutes"` produced zero advancement, contradicting tabletop intuition that travel always passes some time.
- **Cosmetic disconnect.** Pre-S66 embed echoed `(elapsed)` raw input but never showed the actual phase delta. S64 playtest example: `/travel duration:"1 hour"` produced Midday → Afternoon (correctly 1 phase) but operator couldn't see that the parser had translated correctly — felt like a bug. Truthfulness gap, not a math bug.

### Phase B — Floor-at-1-phase rule

Patch shape (at `discord_dnd_bot.py:travel` handler):
```python
parsed = parse_elapsed(elapsed) or (0, 0)
days_d, phase_d = parsed
floor_applied = False
if days_d == 0 and phase_d == 0:
    days_d, phase_d = 0, 1
    floor_applied = True
    log(f"/travel: floor-at-1-phase applied campaign={...} elapsed={elapsed!r}")
ta = advance_time(campaign['id'], days_d, phase_d, source='travel', ...)
```

Covers: empty string, `'banana'`, `'5 minutes'`, `'a moment'`, etc.

### Phase C — Truthful embed

Post-S66 embed:
```
Travel: <origin> → <destination> (input: `1 hour`) — advanced 1 phase (Morning → Midday). The DM is opening the arrival scene...
```

Shows: input verbatim, actual phase delta, before/after phase names. Floor note appended when applicable: `— defaulted to 1 phase`.

### Rollback procedure

Revert `discord_dnd_bot.py:travel` lines 5177-5210 to pre-S66 shape (revert the floor block + revert the embed assembly to single-line). No other code touched.

---

## Fix 2 — F-031 Quest Delivery Silent Inventory Fail

### Phase A — Recon findings

- **Bug confirmed.** `_do_quest_deliver` (line 5773) called `add_item(campaign['id'], '', item['name'], item['quantity'])` at line 5795. Empty character_name hit `add_item`'s validator (`if not character_name: return action='invalid'`), silently returning `'invalid'` with quantity_now=None. Handler ignored the return value.
- **Other `add_item` callers.** Verified all other callers pass non-empty character names (giveitem_cmd validates, etc.). Quest delivery was the lone vapor path.
- **Multiplayer concern.** Per GPT 1/3 review note: "first-bound player" approach for party rewards arbitrarily favors whoever bound first; party-stash sentinel is cleaner from day one.

### Phase B — Party-stash sentinel + truthful aside

1. **`PARTY_STASH_BUCKET = '__party__'`** constant added to `dnd_engine.py`. Module-level. Double-underscore prefix prevents PC-name collision.
2. **`_do_quest_deliver` patch:** pass `PARTY_STASH_BUCKET` instead of empty string. Capture `add_item` return. Two-track aside output:
   - `inv_lines` — successful adds: `+ silver dagger ×1 → party stash (inserted)`
   - `inv_failed` — failures: `! item ×qty (add_item returned action=invalid)` with a follow-up `_(Check add_item logs; reward may need manual /giveitem.)_`
3. **Truthful telemetry.** `quest_delivered: campaign=N quest_id=K item='...' qty=N party_stash=true add_item_result={inserted|incremented|invalid}` per item.

### Phase C — `/inventory` surfacing

`/inventory` handler appends a `**Party stash** (quest rewards + loot):` section when `PARTY_STASH_BUCKET` has rows. Visible in same view as the character's own inventory. Renders "(empty)" placeholder if character has no items but party stash does, and merged "_Empty._ (Party stash also empty.)" when both are empty.

### Rollback procedure

1. Revert `dnd_engine.py` lines 2447-2480 (remove PARTY_STASH_BUCKET constant + docstring note).
2. Revert `discord_dnd_bot.py:_do_quest_deliver` to pre-S66 (single-loop, single `inv_lines`, no `inv_failed`).
3. Revert `discord_dnd_bot.py:inventory_cmd` to pre-S66 (no party stash section).
4. Revert import in discord_dnd_bot.py line 73 to drop `PARTY_STASH_BUCKET, remove_item`.

Behavior reverts: quest delivery again writes to empty bucket → silent invalid → vapor. /inventory hides party stash.

---

## Fix 3 — F-035 Loot Auto-Claim with Refusal

### Phase A — Recon findings

- **Loot pipeline (Track 4 #2).** `update_combatants_from_init_list` detects alive=1→0 transition → `enqueue_loot_for_defeats` → writes structured rows to `dnd_loot_pending` with `coin` (amount+denom) and `items` (JSON list of strings) → `compute_loot_directive` renders directive into next narration → `mark_loot_surfaced(id)` flips `surfaced=1` after LLM call succeeds.
- **The gap.** Items are already structured in `dnd_loot_pending`. The directive narration explicitly said *"Do NOT auto-add items to inventory ... the player will use /giveitem or claim narratively."* So even though the engine had structured item names ready, it actively told the LLM to NOT auto-add. Players had to remember to `/giveitem` for each, which they rarely did.
- **Hook point.** `mark_loot_surfaced` already fires at the right moment (after a successful LLM call). Adding `add_item(PARTY_STASH_BUCKET, ...)` per item in the same loop is the cleanest auto-claim point.
- **Coin separation.** Coin (gp/sp/cp) is NOT added to inventory — it stays in mechanical_hints.py's domain via `!game coin +Nxx` hints (Avrae handles coin state). Inventory is for ITEMS only.
- **Possession-transfer-verb extraction.** The S66 plan also called for LLM-narration item extraction (e.g., "you find a tattered map in the chest" → auto-claim). This deferred — the structured combat-loot path is the F-035 core; ad-hoc narrative-loot extraction is filed as a follow-up (`S66_followups.md` §N-5).

### Phase B — Auto-claim at surface-and-clear

Patch shape (`dnd_engine.py:dm_respond` ~line 7575+):
```python
for _row in pending_loot_rows:
    rid = _row.get('id')
    if rid is not None:
        mark_loot_surfaced(rid)
    for item_name in (_row.get('items') or []):
        add_res = add_item(campaign['id'], PARTY_STASH_BUCKET,
                           item_name.strip(), 1)
        log(f"loot_auto_claimed: campaign={...} creature={...} "
            f"item={item_name!r} qty=1 add_item_result={...}")
```

`compute_loot_directive` narration rewritten:
- Pre-S66: *"Do NOT auto-add items to inventory. Surface them for the player to claim or leave — the player will use /giveitem or claim narratively."*
- Post-S66: *"S66 Fix 3 — these items are AUTO-CLAIMED into the party stash by the engine after this narration is posted. Narrate the discovery naturally. Do NOT instruct the player to /giveitem — items already land in the party stash; the operator uses `/loot drop <item>` to refuse anything the party doesn't want."*

### Phase C — `/loot drop` refusal surface

New slash command. DM-only. Autocompletes from current party stash items. Uses `remove_item(PARTY_STASH_BUCKET, item, qty)`. Four-branch response: `removed` (last one), `decremented` (some left), `not_found`, `insufficient`.

### Possession-transfer verb extraction (deferred)

The plan's Phase B mentioned LLM-narration extraction for ad-hoc loot (chest contents, found items without combat-end trigger). This is a separate layer from the structured-combat path. Filed as **N-5** in `S66_followups.md` — uses the N-1 hint-extractor pattern (closed verb vocab + post-extraction validator). Estimated ~1-2 days when prioritized. F-035 core (combat loot) is fully closed without this.

### Rollback procedure

1. Revert `dnd_engine.py:dm_respond` surface-and-clear block (drop the auto-claim loop, restore the original 5-line surface-only block).
2. Revert `dnd_orchestration.py:compute_loot_directive` body string (restore pre-S66 narrative instruction).
3. Revert `discord_dnd_bot.py` — drop `loot_drop_cmd`, `_party_stash_autocomplete`, and `remove_item` from the import.

Behavior reverts: loot directive again says "use /giveitem"; combat items go un-claimed; `/loot drop` no longer exists.

---

## Test Counts (S66 contribution)

| Test File | New | Status |
|---|---|---|
| `test_travel_duration_floor.py` | 52 | All pass |
| `test_quest_delivery_party_stash.py` | 28 | All pass |
| `test_loot_auto_claim.py` | 26 | All pass |

**Plus S65 + S65.1 inheritance:** test_play_smoke (6), test_dc_less_roll_closure (25), test_dm_aside_role_closure (13), test_format_unification_closure (23), test_attack_directive (50), test_advisory (31), test_auto_execute_closed (21), test_hint_extractor_baker (26), test_dnd_npcs (163), test_dnd_locations (109), test_dnd_consequences (142), test_consequence_command (26), test_directive_emit (23), test_inventory (31), test_advance_time (29).

**Total assertion count (S65 + S65.1 + S66): 824 across 18 test files.** All green.

---

## §17 Single-Writer Audit

All three fixes preserve the single-writer discipline:

| Surface | Writer | Confirmed unchanged |
|---|---|---|
| `dnd_scene_state.day_phase / campaign_day` | `advance_time` only | ✓ (Fix 1 only changes the caller's delta computation; `advance_time` still validates and writes) |
| `dnd_inventory` (insert/increment) | `add_item` only | ✓ (Fix 2/3 add new callers but no other writer) |
| `dnd_inventory` (decrement/delete) | `remove_item` only | ✓ (Fix 3 adds `/loot drop` caller) |
| `dnd_loot_pending.surfaced` | `mark_loot_surfaced` only | ✓ (Fix 3 keeps same single writer; just adds inventory side-effect in the surrounding block) |
| `dnd_quests` (status transitions) | `quest_deliver`, `quest_set_status`, `quest_abandon`, etc. | ✓ (Fix 2 changes the post-quest-deliver inventory side-effect, not the quest state machine) |

---

## Recon Findings: Possession-Transfer Verb Vocabulary (deferred to N-5)

For the future LLM-narration loot extractor (filed as N-5 in `S66_followups.md`), the closed vocabulary candidates from the plan + verb hardening done for N-1 hints:

**Possession-transfer verbs (player ACQUIRES):**
- find, found, finds, finding
- claim, claimed, claims, claiming
- loot, looted, loots, looting
- scavenge, scavenged, scavenges, scavenging
- pick up, picks up, picked up, picking up
- gather, gathered, gathers, gathering
- retrieve, retrieved, retrieves, retrieving
- pocket, pocketed, pockets, pocketing (overlap with N-1 coin vocab — OK, same direction)
- take, took, takes, taking (ambiguous — also "takes ten minutes"; N-1 ruled it KEEP)

**Location-only mentions (NO transfer — bare item mention guard):**
- gleams, glints, rests, lies, hangs, sits, stands
- catches the eye, catches the light, attracts attention

Apply same pattern as N-1: closed vocab + whole-word match, excluding noun-overlap traps. The N-5 spec should also note: bare item mentions ("a silver dagger gleams on the wall") MUST NOT trigger auto-claim — possession-transfer signal required.

---

## Standing-Practice Adoption Confirmation

1. ✅ **Pre-ship DB snapshot:** `cp virgil.db archive/virgil_S66_preship.db` at 2026-05-14T12:48 PDT. 20.7 MB.
2. ✅ **Rollback procedure per fix:** see Fix 1/2/3 sections above.
3. ✅ **Sequential commits + atomic test verify:** Fix 1 → tests green (52) → Fix 2 → tests green (28) → Fix 3 → tests green (26) → full regression sweep (824 across 18 files) → bot restart → boot clean.
4. ✅ **Feature-disable readiness:** the loot auto-claim block in `dm_respond` is wrapped in `try/except`; failure short-circuits to a log line and leaves loot un-claimed (so existing players' rewards aren't lost on error). PARTY_STASH_BUCKET sentinel is a regular string column — no schema migration needed.

---

## Doctrine Candidate Progress (Note for F-XX Anchoring Walk)

F-031 and F-035 close two **inventory-side instances** of "narration-commit gap as systemic contamination surface":
- F-031: `add_item('', ...)` returns 'invalid' silently while caller reports success — narration says "reward given," engine writes nothing.
- F-035: loot surfaces in narration, marked surfaced, but no inventory write — narration says "you scavenge the bodies," engine writes nothing.

Both are the **same architectural pattern** as the N-1/N-2 baker-pricing surface: narration asserts state change, engine doesn't enact it. S65.1 N-1 (hint extractor) addressed the inverse problem (engine emits hints from narration mentions, even when narration doesn't represent state change). S66 F-031/F-035 address the original direction (narration represents state change, engine fails to commit it).

Two more inventory-side instances would complete a pattern triangle: NPC commitments (N-3 pricing math) + NPC pronouns (N-4 gender drift) are the NPC-side analogues. Combined, S66 + post-S68 ship of N-3+N-4 would earn an F-XX **"narration-commit gap as systemic contamination surface"** doctrinal anchor.

For the long-horizon review's Section II X-findings: this pattern would map to a new X-finding around "narration as a state-change vector" — currently dispersed across F-008, F-031, F-035, N-1 through N-4.

---

## Restart + Discord Verify

Bot restarted at 2026-05-14T12:59 PDT. Status `active`. Boot clean.

**Operator-paste-verbatim test scenarios per S66 plan:**

1. **`/travel duration:"1 hour"`** — embed reports `advanced 1 phase (X → Y)`.
2. **`/travel duration:"8 hours"`** — embed reports `advanced 2 phases (X → Y)`.
3. **`/travel duration:"banana"`** — embed reports `advanced 1 phase (X → Y) — defaulted to 1 phase`. Journal: `parse_elapsed: input='banana' result=none` + `/travel: floor-at-1-phase applied`.
4. **`/quest add title:"S66 reward test" reward_summary:"silver dagger and a healing potion"`** then **`/quest complete <id>`** — `#dm-aside` shows `+ silver dagger × 1 → party stash (inserted)`; `/inventory` shows party stash section with the items. Journal: `quest_delivered: ... party_stash=true add_item_result=inserted`.
5. **Combat with structured loot** — fight a creature with a known loot table. Confirm narration mentions the loot AND `/inventory` shows party stash with items. Journal: `loot_auto_claimed: ... add_item_result=inserted`.
6. **`/loot drop item:"silver dagger"`** — removes from stash; `/inventory` no longer shows it.
7. **N-1 baker scenario regression** — re-run the baker pricing scenario from S65.1; confirm hint extractor still fires exactly once per real transaction (no S66 regression on S65.1 work).

**Journal greps for operator verify:**
```bash
journalctl --user -u virgil-discord | grep "floor-at-1-phase"     # /travel default-case fires
journalctl --user -u virgil-discord | grep "quest_delivered"      # quest reward writes
journalctl --user -u virgil-discord | grep "loot_auto_claimed"    # combat loot writes
journalctl --user -u virgil-discord | grep "loot_dropped"         # /loot drop fires
journalctl --user -u virgil-discord | grep "add_item.*invalid"    # should be zero on quest-delivery path
```

---

## End-of-Session State

- 3 fixes shipped (Fix 1 /travel floor, Fix 2 F-031 close, Fix 3 F-035 close).
- 0 HALT escalations.
- F-031 CLOSED (long-horizon Tier 1 P0).
- F-035 CLOSED (long-horizon Tier 1 P0).
- N-5 (LLM narrative-loot extraction) filed to `S66_followups.md`.
- Pre-ship snapshot in archive.
- Standing-practice adoption: confirmed.
- Total test count: 824 across 18 files.
