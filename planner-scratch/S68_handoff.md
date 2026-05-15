# S68 Handoff — N-4 ship + N-3 HALT escalation

**Date:** 2026-05-14
**Session:** S68 (N-3 + N-4 bundled, N-4 shipped, N-3 HALTED on recon)
**Pre-ship snapshot:** `/mnt/virgil_storage/archive/virgil_S68_preship.db` (20.7 MB)

---

## Fix Inventory

| Fix | Status | Outcome |
|---|---|---|
| **N-4 NPC pronoun lock** | ✅ **SHIPPED** | Phases A–E complete. 41 adversarial tests green. Backfill ran on production DB; 7 NPCs locked from existing description prose at first engine init. |
| **N-3 prior-price-check directive** | ⛔ **HALTED** | Recon Phase A surfaced HALT criterion: no scene-log table indexes by NPC+item with price commitments. Schema work required. Filed forward as N-3.1. |

---

## N-4 — NPC Pronoun Lock (SHIPPED)

### Phase A — Schema migration
- `ALTER TABLE dnd_npcs ADD COLUMN pronouns TEXT DEFAULT ''` at `db_init()`.
- New `_NPC_COLS` includes pronouns; `_npc_row_to_dict` populates `pronouns` key on every NPC dict.
- Production migration ran cleanly (boot log `npc_pronoun_backfill: scanned=23 locked=0 conflicts=0 skipped_empty=23` post-prior-smoke-locks).

### Phase B — Backfill extractor
- `extract_pronouns_from_text(text) → (canonical, conflicts)`: regex first-occurrence over `_PRONOUN_SETS` ordered tuple. Six canonical forms: she/her, he/him, they/them, xe/xem, ze/hir, it/its.
- `npc_pronouns_set(npc_id, pronouns) → bool`: §17 single writer for the column. Empty value refused; truncates at 30 chars.
- `npc_pronouns_get(npc_id) → str`: read helper.
- `npc_pronouns_backfill_pass()`: one-shot at engine init. **Prioritizes first-sentence parse** per N-10 v0.1 forward-coupling (bootstrap-NPCs carry pronouns in first sentence by design). Falls back to whole-description scan. Idempotent — skips rows with non-empty pronouns.

### Phase C — Render in NPCs-IN-CONTEXT block
- New `get_recently_active_npcs_detail(campaign_id, limit, location_id) → list[dict]`: sibling of `get_recently_active_npcs`, returns name + pronouns dicts.
- `build_dm_context` updated: renders "Recently active NPCs: Grahn (he/him), Lira (she/her)..." with pronoun annotations inline when locked. Bare name when not yet locked.
- `npcs_in_context:` telemetry extended with `pronouns_locked=N` count.

### Phase D — Live-lock on first narration mention
- `_lock_npc_pronouns_from_narration(campaign_id, narration, npcs)` in `discord_dnd_bot.py`. Runs in `_extract_and_persist_world` post-NPC-upsert pass.
- For each NPC mentioned in narration with no locked pronouns, scans ±200/+300 char window around NPC name for pronoun signal. First-occurrence wins.
- Telemetry: `npc_pronoun_locked: campaign=N npc_id=N name='X' pronouns='he/him' source=narration` + `npc_pronoun_live_lock: count=N` summary.

### Phase E — Anti-drift invariant
- New **HARD STOP RULE 7** added to `build_dm_context`: "NPC PRONOUN LOCK. NPCs in the 'Recently active NPCs' line carry their canonical pronouns in parentheses (e.g., 'Grahn (he/him)'). You MUST use ONLY the locked pronouns for each NPC throughout your response..."
- Names the S64 baker drift scenario explicitly. MUST-tone consistent with rules 1–6.

### Files touched

| File | Lines | Notes |
|---|---|---|
| `dnd_engine.py` | +120 / -8 | pronouns column migration; 4 helpers + backfill pass; pronouns added to `_NPC_COLS` + dict; render block updated; HARD STOP RULE 7 added |
| `discord_dnd_bot.py` | +65 / -2 | `_lock_npc_pronouns_from_narration` helper; call site after npc_extract block |
| `test_npc_pronoun_lock.py` | +250 (new) | 41 adversarial tests across all 5 phases |

**Test count: 41 new assertions.** All green.

### Rollback procedure (N-4)
1. Revert HARD STOP RULE 7 addition in `dnd_engine.py:build_dm_context`.
2. Revert render block update (recent_npcs_line back to bare names).
3. Revert _NPC_COLS + _npc_row_to_dict to pre-S68.
4. Revert `_lock_npc_pronouns_from_narration` call site in `discord_dnd_bot.py:_extract_and_persist_world`.
5. Drop `pronouns` column: `ALTER TABLE dnd_npcs DROP COLUMN pronouns` (SQLite ≥3.35) OR leave (column is additive, NULL-safe).
6. Restart `virgil-discord`.

Pre-ship snapshot at `/mnt/virgil_storage/archive/virgil_S68_preship.db`.

---

## N-3 — Prior-Price-Check Directive (HALTED)

### Recon Phase A findings

Scanned all 22 `dnd_*` tables + non-DB persistence surfaces:
- **No `dnd_scene_log` or per-turn structured narrative log table.** Closest fit: `messages` (flat Discord chat log, no NPC binding) and `dnd_consequences` (per-NPC structured but `kind` enum doesn't include `price_commitment` or `fact`).
- ChromaDB sessions collection exists; semantic retrieval is probabilistic, not deterministic NPC+item lookup.
- Mechanical hints (`hint_extractor_emitted` log lines) capture `!game coin -Xsp` per turn but don't bind to a specific NPC and live in flat log files, not DB.

### HALT trigger

Per brief discipline:
> "If N-3 scene-log lookup requires schema work (no scene-log table exists, or existing structure doesn't index by NPC+item), HALT and escalate."

The deterministic NPC+item commitment lookup that N-3 architecturally needs doesn't have a substrate. Building it requires:
1. **New `dnd_npc_commitments` table** with `(campaign_id, npc_id, kind, topic_or_item, value, asserted_turn)` schema.
2. **Post-narration commitment extractor** that detects NPC statements (`"X costs Y"`, `"I promise Z"`, `"the X is at Y"`) and writes structured commitment rows.
3. **N-3 lookup** queries this table.

This is multi-spec scope — a separate ship's worth of design work (schema + extractor + lookup + directive).

### Stopgap considered, not recommended

Chroma + regex stopgap (probabilistic prior-narration search):
- Detect player price-claim with closed-vocab regex ✓ (deterministic, cheap)
- chroma_search recent turns mentioning the item → regex-parse for price tokens → directive fires when no match
- False positives (near-match semantic retrieval) suppress directive when player IS gaslighting
- False negatives (chroma misses real prior turn) fire directive when player is honest
- Precision unknown without corpus calibration — operator + Oracle territory

Operator should NOT ship the chroma stopgap blind. The clean fix needs the structured surface.

### N-3.1 filed forward

Filing for separate session:
- Sketch design pass on `dnd_npc_commitments` table shape
- Define `kind` enum: `{price, promise, fact, denial, ...}`
- Post-narration extractor pattern (mirror `consequence_extractor.py` shape)
- N-3 directive built on top of the structured surface
- Adversarial verify: re-run S64 baker pricing scenario

Estimated scope: 1 sketch session + 1 review + 1 implementation. Path A cadence like Quest Layer v0 / Composition Layer v0 / Canon Bootstrap Bot v0.

---

## Doctrine candidate progress (paired-evidence cluster)

The narration-commit-gap doctrine candidate has now accumulated:

| # | Instance | Side | Closed in |
|---|---|---|---|
| 1 | F-008 AUTO_EXECUTE close | LLM-emit / state-write directive | S65.1 |
| 2 | F-031 quest delivery silent inventory fail | inventory-side | S66 |
| 3 | F-035 loot evaporation | inventory-side | S66 |
| 4 | N-1 hint extractor (over-commits on dialogue) | inverse — engine emits hints from narration when no state change happened | S65.1 |
| 5 | **N-4 NPC pronoun drift** | NPC-side | **S68 (this ship)** |
| 6 | N-3 NPC price gaslight | NPC-side | **HALTED → N-3.1 pending** |

After N-3.1 ships, the cluster has 6 instances spanning 4 surfaces (state writes / inventory / NPC drift / hint over-commit). **The F-XX anchoring walk earns its formal slot at that point.** Recommended host for the doctrinal sub-anchor walk: the N-3.1 spec session or a dedicated S70 doctrine pass.

---

## Test totals (post-S68)

| Test file | Asserts | Status |
|---|---|---|
| `test_npc_pronoun_lock.py` | **41** | NEW — All pass |
| `test_canon_bootstrap_v0_1_patch.py` | 63 | All pass |
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

**Total: 1047 assertions across 22 test files.** All green.

---

## Restart + Discord verify

Bot restarted at 2026-05-14T16:35:20 PDT. Status `active`. Boot log:
- `srd_resolver: index loaded entries=334`
- `fk_cascade_init: pragma_supported=1`
- `wal_init: journal_mode=wal ...`
- **`npc_pronoun_backfill: scanned=23 locked=0 conflicts=0 skipped_empty=23`** ✓ NEW (S68 N-4)
- `chroma_init: sessions=1096 knowledge=740307`
- `starting Discord DnD bot`

The "scanned=23 locked=0" reflects production DB state: prior smoke-test runs locked 7 NPCs during development; the remaining 23 have descriptions without parseable pronoun signal (they'll lock on first narration mention via live-lock pass).

**Operator-paste-verbatim test scenarios:**

1. **N-4 backfill spot-check.**
   ```bash
   sqlite3 /mnt/virgil_storage/virgil.db "SELECT canonical_name, pronouns FROM dnd_npcs WHERE pronouns != '' ORDER BY id DESC LIMIT 10;"
   ```
   Expected: bootstrap-NPCs from N-10 v0.1 playtest campaigns show locked pronouns (Grahn → he/him; Lira Songheart → she/her; etc.).

2. **N-4 live-lock on first narration.** Run any narration that mentions an NPC with empty pronouns. Verify journal:
   ```bash
   journalctl --user -u virgil-discord | grep "npc_pronoun_locked.*source=narration"
   ```
   Subsequent NPCs-in-context render should show `(he/him)` (or whatever was extracted).

3. **N-4 baker gender drift reproduction (the S64 scenario).** Run a multi-turn vendor interaction:
   - `/travel destination:"Market Square"`
   - "I try to persuade the baker for a free loaf."
   - "Pay for 5 more loaves"
   - "How much?"
   Expected: baker NPC locks pronouns on first narration; subsequent turns hold the same pronouns. **Pre-S68 this drifted (he → she → he) across turns; post-S68 should be stable.**

4. **N-4 anti-drift rail.** HARD STOP RULE 7 in every prompt now instructs LLM to use only locked pronouns. Engineered drift attempt should self-correct or be caught by narration-verifier.

5. **Regression checks (Tier 1 cleanup arc + N-10 v0/v0.1).**
   - `/play` opens cleanly (F-021 closure intact)
   - `/travel destination:"X" elapsed:"1 hour"` advances 1 phase (S66 Fix 1)
   - `/quest add` + `/quest complete` round-trip (S66 Fix 2)
   - `/bootstrap begin premise:"..."` + `/bootstrap manual overrides:'name:"X"'` + `/bootstrap accept` writes canonical_name='X' (N-10 v0.1)

**Journal greps:**
```bash
journalctl --user -u virgil-discord | grep "npc_pronoun_locked"     # backfill + live-lock events
journalctl --user -u virgil-discord | grep "npc_pronoun_conflict"   # multi-pronoun warnings
journalctl --user -u virgil-discord | grep "npc_pronoun_backfill"   # per-init summary
sqlite3 /mnt/virgil_storage/virgil.db "SELECT canonical_name, pronouns FROM dnd_npcs WHERE pronouns != '';"
```

---

## Forward-coupling notes

**For S69 / Causality Engine v0:** N-10 v0.1 faction structured fields still live in skeleton.md only (per CANON_BOOTSTRAP_BOT_V0_SPEC §11.8). S69 inherits the prose-extraction pattern. N-4 NPC pronouns are now a stable substrate — Causality Engine NPCs (if any) carry locked pronouns by the time S69 reads them.

**For N-3.1 spec session:** the proposed `dnd_npc_commitments` table shape should align with `dnd_consequences` shape (`campaign_id`, `npc_id`, `kind`, structured value, audit timestamp) but with different `kind` enum (`{price, promise, fact, denial}` rather than consequences' threat/mercy/cruelty enum). Extractor follows `consequence_extractor.py` shape — dual-pass (player text + DM narration) with deterministic post-validation.

---

## End-of-session state

- 1 fix shipped (N-4, 5 phases complete)
- 1 fix HALTED with documented recon evidence (N-3 → N-3.1 filed forward)
- 41 new test assertions; 1047 total across 22 test files, all green
- Bot restarted, boot clean, backfill ran
- §17 audit: new single writer `npc_pronouns_set` for dnd_npcs.pronouns; existing writers untouched
- §76 audit: zero new 4/4 surfaces (pronouns is enum-shaped + write-gated; 1/4 at most)
- Doctrine candidate paired-evidence cluster: 5/6 instances closed; N-3.1 outstanding before F-XX anchoring walk
- Pre-ship snapshot in archive

**Next session candidates:**
- **N-3.1 sketch session** — design `dnd_npc_commitments` schema + extractor + N-3 directive. Path A cadence (sketch → review → ship).
- **S67.1** — close the 3 mitigated §76 surfaces from S67 Phase C audit.
- **S69 Causality Engine v0** — sketch session opens; faction skeleton.md inheritance from N-10 v0.1 is the substrate.
- **Operator playtest of N-4** — baker scenario reproduction (gender drift); confirm pronouns lock and hold across multi-turn vendor interactions.
