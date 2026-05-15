# N-10 v0.1 Handoff — Same-Session Live-Verify Patch

**Date:** 2026-05-14
**Session:** N-10 v0.1 (same-session patch from operator playtest)
**Trigger:** Live-verify Grahn scenario surfaced cascade bug — `/bootstrap manual name:"Grahn"` on NPC card produced `dnd_npcs.canonical_name='Gundrik Ironfist'` (LLM's untouched draft) instead of operator's override
**Pre-ship snapshot:** `/mnt/virgil_storage/archive/virgil_N10_v0_1_preship.db` (20.7 MB)

---

## Fixes Shipped

| Fix | Status | Files |
|---|---|---|
| Fix 1 — Per-card-type field-key normalization in `/bootstrap manual` | ✅ | `discord_dnd_bot.py` |
| Fix 2 — Prose-residual warning on name-class overrides | ✅ | `discord_dnd_bot.py` |
| Fix 3 — Reroll directive archetype-diversity hint | ✅ | `dnd_orchestration.py`, `discord_dnd_bot.py` |

---

## Fix 1 — Field-key normalization

**Root cause.** Operator-friendly aliases (`name`, `title`) didn't map to canonical field per card type. Overrides stored under the operator's typed key (`fields['name']='Grahn'`); commit-time `_commit_proposal` read from the actual canonical key (`fields.get('canonical_name')`); override silently ignored.

**Cascade observed.** NPC writes with LLM's untouched name → quest's `offer_npc_name` ('Grahn') fails to resolve via `_resolve_npc_id_for_quest` → `npc_id is None` → `quest_offer(...)` never fires → quest stays at default `status='in-progress'` instead of transitioning to `offered`, and `offer_npc_id` stays NULL.

**Patch shape (`discord_dnd_bot.py`):**
- `_BOOTSTRAP_FIELD_ALIASES` map: per-card-type alias→canonical lookup.
- `_normalize_bootstrap_field_key(card_type, key)` helper; unknown keys pass through unchanged.
- `bootstrap_manual_cmd` applies normalization before storing into `fields` dict.
- New telemetry: `bootstrap_manual_override: campaign=N card_type=X original_key='name' normalized_key='canonical_name' value='Grahn'`.

**Normalization table:**

| Card type | Operator alias | Canonical |
|---|---|---|
| faction | `name` | `name` (identity) |
| npc_dispatcher | `name`, `canonical_name` | `canonical_name` |
| location | `name`, `canonical_name` | `canonical_name` |
| quest | `name`, `title` | `title` |
| quest_act | `name`, `title`, `act_title` | `act_title` |

---

## Fix 2 — Prose-residual warning

**Surface.** Even with Fix 1 working, the LLM-generated `description` and `justification` retain the prior name. Operator who overrides name without rerolling sees inconsistent prose at the canonical-table level.

**Patch shape.**
- `_BOOTSTRAP_NAME_CLASS_CANONICAL` map: which canonical field is the "name" for each card type.
- After applying overrides, `bootstrap_manual_cmd` detects if any override touched a name-class canonical field.
- If yes: append `"⚠ Description and justification may still reference the prior name. Run /bootstrap reroll if you want the prose regenerated with the new name."` to the ephemeral response.
- Soft warning only — operator decides whether to reroll.

---

## Fix 3 — Reroll archetype-diversity hint

**Surface.** Playtest showed three rerolls all produced the same dwarf-miner archetype with mild name variation (Gorin → Gorm → Gundrik). Reroll prompt didn't anchor "do something meaningfully different."

**Patch shape (`dnd_orchestration.py`):**
- New helper `_extract_prior_archetype_hint(prior_proposal, card_type)`: cheap heuristic pulls role / type / title from the prior draft and constructs a hint asking for a different archetype/role/cultural origin.
- `compute_bootstrap_card_directive` takes new optional `prior_proposal` param.
- Reroll-block prompt now includes the archetype hint when prior_proposal is supplied.
- New signal `prior_archetype_hint: bool` in signals dict; surfaced in `bootstrap_card_log_summary` telemetry.

**Patch shape (`discord_dnd_bot.py`):**
- `_dispatch_bootstrap_card` passes `state.current_proposal` as `prior_proposal` when `state.rerolls_for_current > 0`.
- `bootstrap_card_proposed:` log line extended with `reroll_count` + `prior_archetype_hint` flags.

**Archetype extraction heuristics per card type:**
- **NPC**: pulls `role` + `canonical_name`; asks for different role + cultural origin / species.
- **Faction**: pulls `type` + `name`; asks for different type + goal-flavor + cultural axis.
- **Quest**: pulls `title`; asks for different verb / stakes scale / solution path.
- **Quest_act**: pulls `act_title`; asks for different mode / escalation.
- **Location**: pulls `type` + `canonical_name`; asks for different scale + cultural context.

---

## Files Touched (LOC delta)

| File | Lines | Notes |
|---|---|---|
| `discord_dnd_bot.py` | +60 / -8 | Alias map (~30 LOC); helper (~10 LOC); manual_cmd override logic (~15 LOC); dispatch threading (~5 LOC); log line extended |
| `dnd_orchestration.py` | +75 / -8 | `_extract_prior_archetype_hint` helper (~55 LOC); reroll-block injection (~5 LOC); `compute_bootstrap_card_directive` signature (~3 LOC); `bootstrap_card_log_summary` signal exposure (~2 LOC) |
| `test_canon_bootstrap_v0_1_patch.py` | +325 (new) | 63 unit + integration assertions across 4 sections |

**Total new test assertions: 63.** All green.

---

## Test Counts (post-v0.1)

| Test file | Asserts | Status |
|---|---|---|
| `test_canon_bootstrap_v0_1_patch.py` | **63** | NEW — All pass |
| `test_canon_bootstrap_bot_v0.py` | 89 | All pass |
| `test_dnd_npcs.py` | 163 | All pass |
| `test_dnd_locations.py` | 109 | All pass |
| `test_dnd_consequences.py` | 142 | All pass |
| `test_consequence_command.py` | 26 | All pass |
| `test_directive_emit.py` | 23 | All pass |
| `test_play_smoke.py` | 6 | All pass |
| `test_dc_less_roll_closure.py` | 25 | All pass |
| `test_dm_aside_role_closure.py` | 13 | All pass |
| `test_format_unification_closure.py` | 23 | All pass |
| `test_attack_directive.py` | 50 | All pass |
| `test_advisory.py` | 31 | All pass |
| `test_auto_execute_closed.py` | 21 | All pass |
| `test_hint_extractor_baker.py` | 26 | All pass |
| `test_travel_duration_floor.py` | 52 | All pass |
| `test_quest_delivery_party_stash.py` | 28 | All pass |
| `test_loot_auto_claim.py` | 26 | All pass |
| `test_inventory.py` | 31 | All pass |
| `test_current_scene_closure.py` | 15 | All pass |
| `test_advance_time.py` (pytest) | 29 | All pass |

**Total: 1006 assertions across 21 test files.** All green.

---

## Restart + Discord verify

Bot restarted at 2026-05-14T16:06:28 PDT. Status `active`. Boot clean (wal_init + chroma_init + slash sync expected on connect).

**Operator-paste-verbatim verify scenarios:**

1. **Grahn reproduction (the bug we fixed):**
   ```
   /newcampaign name:"V0.1 Grahn Test"
   /bootstrap begin premise:"Grimdark frontier mining town, mine collapse..."
   /bootstrap accept   # accept faction
   ```
   Wait for NPC card; bot proposes e.g. "Gundrik Ironfist".
   ```
   /bootstrap manual overrides:'name:"Grahn"'
   /bootstrap accept
   ```
   Verify:
   - Ephemeral response includes `name→canonical_name` normalization note + prose-residual warning.
   - `sqlite3 ... "SELECT canonical_name FROM dnd_npcs WHERE skeleton_origin=1 ORDER BY id DESC LIMIT 1;"` returns 'Grahn' (NOT 'Gundrik Ironfist').
   - Subsequent quest cards resolve `offer_npc_name:"Grahn"` correctly via `_resolve_npc_id_for_quest`.

2. **Quest title alias:** On a quest card, `/bootstrap manual overrides:'title:"The Cursed Shaft"'` then `/bootstrap accept`. Verify `dnd_quests.title = 'The Cursed Shaft'`.

3. **Quest_act alias:** On a quest_act card, `/bootstrap manual overrides:'name:"Approach"'` (operator typed `name`; normalizes to `act_title`).

4. **Faction name passthrough:** On a faction card, `/bootstrap manual overrides:'name:"Black Vein Cartel"'`. Verify skeleton.md has `### Black Vein Cartel (...)` H3.

5. **Reroll archetype diversity:**
   ```
   /bootstrap reroll
   /bootstrap reroll
   /bootstrap reroll
   ```
   Verify each reroll produces a different archetype (different role, different species/culture). Journal: `journalctl --user -u virgil-discord | grep "bootstrap_card_proposed" | grep "prior_archetype_hint=1"` confirms hint fired.

**Journal greps:**
```bash
journalctl --user -u virgil-discord | grep "bootstrap_manual_override"        # normalization visible
journalctl --user -u virgil-discord | grep "bootstrap_card_proposed" | grep "reroll_count"
sqlite3 /mnt/virgil_storage/virgil.db "SELECT canonical_name FROM dnd_npcs WHERE skeleton_origin=1 ORDER BY id DESC LIMIT 5;"
```

---

## Rollback procedure

1. Revert the three edit blocks in `discord_dnd_bot.py`:
   - Remove `_BOOTSTRAP_FIELD_ALIASES` + `_BOOTSTRAP_NAME_CLASS_CANONICAL` + `_normalize_bootstrap_field_key`.
   - Restore original `bootstrap_manual_cmd` override loop.
   - Revert `_dispatch_bootstrap_card` to pre-v0.1 signature (drop `prior_proposal_for_hint` threading).
2. Revert `dnd_orchestration.py`:
   - Drop `_extract_prior_archetype_hint`.
   - Revert `compute_bootstrap_card_directive` signature to pre-v0.1 (drop `prior_proposal` param).
   - Revert reroll-block construction to pre-v0.1.
   - Revert `bootstrap_card_log_summary` signal exposure.
3. Restart `virgil-discord`.

Pre-ship snapshot: `/mnt/virgil_storage/archive/virgil_N10_v0_1_preship.db`. Pre-v0.1 ship state preserved.

---

## End-of-session state

- 3 fixes shipped from observed-friction playtest evidence
- 63 new test assertions; 1006 total across 21 test files, all green
- Bot restarted, boot clean
- Pre-ship snapshot in archive
- §1b sixth-instance gate preserved (no changes to canonical-write path)
- §17 single-writers untouched
- §76 audit unchanged (no new persisted surfaces; in-memory state only)

**Next session candidates:**
- **S68 — N-3 + N-4 NPC commitment rails** (pricing math + pronoun lock) — load-bearing for the architecture; N-10 now produces canon with predictable pronoun signal in first sentence of description per §11.9 lock + Fix 3 archetype-diversity hint helps N-4 migration recon.
- **S67.1 — close the 3 mitigated §76 surfaces** from S67 Phase C audit.
- **Operator playtest of N-10 v0.1** — Grahn scenario reproduction + reroll-diversity inspection on a fresh campaign.
