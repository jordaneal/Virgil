# N-10 Handoff — Canon Bootstrap Bot v0 (Path A Phase 3 ship)

**Date:** 2026-05-14
**Session:** N-10 Path A Phase 3 implementation
**Pre-ship snapshot:** `/mnt/virgil_storage/archive/virgil_N10_preship.db` (20.7 MB)
**Discipline:** pre-ship snapshot ✓ · per-commit test verify ✓ · §17 single-writers preserved ✓ · §1b validated-suggester gate preserved ✓.

---

## Spec status

| File | Status |
|---|---|
| `specs/CANON_BOOTSTRAP_BOT_V0_SPEC.md` | **LOCKED** (DRAFT → LOCKED at session open) |
| `specs/CANON_BOOTSTRAP_BOT_V0_REVIEW.md` | REVIEW (operator-walked, leans locked) |

All 12 §11 decisions locked per `CANON_BOOTSTRAP_BOT_V0_REVIEW.md` recommended defaults:
- §11.1–§11.7, §11.10 (HIGH confidence): locked to (a) — recommended defaults
- §11.4, §11.6, §11.11 (MEDIUM): locked to (a)
- §11.8 (HIGH): (a) skeleton.md only at v0; S69 introduces `dnd_factions`
- §11.9 (HIGH): (a) prose-fold pronouns; S68/N-4 introduces `dnd_npcs.pronouns` column
- §11.12 (LOW): (c) defer to v1.x canon-sync spec

---

## Files Touched

| File | LOC delta | Notes |
|---|---|---|
| `dnd_engine.py` | +75 / -7 | premise column migration; `update_campaign_premise` single-writer; `is_bootstrap_complete` helper; premise rendering in `build_dm_context` at low-tactical-band; `get_active_campaign` returns premise key |
| `dnd_orchestration.py` | +480 / 0 | `compute_bootstrap_sequence_directive` (§59 #16); `compute_bootstrap_card_directive` (§59 #17); deterministic validator; corpus signal substrate (5 fixed-constant strings per R5); telemetry helpers |
| `discord_dnd_bot.py` | +570 / -3 | `BootstrapState` dataclass + `_bootstrap_session: dict` process-local state; `_format_bootstrap_card` (≤2000 chars per R3); `_dispatch_bootstrap_card` async helper; `_commit_proposal` writes via existing single-writers + `skeleton_md_append_element`; `bootstrap_group` with 7 commands (begin/accept/skip/reroll/manual/status/end); dataclass import added |
| `skeleton_writer.py` | +345 (new) | NEW file. `skeleton_md_append_element` single-writer for skeleton.md; idempotent on (element_type, element_name); creates H2 sections if missing; handles 5 element types (faction/npc/quest/quest_act/location); soft-fail on file errors |
| `test_canon_bootstrap_bot_v0.py` | +355 (new) | 89 unit + integration assertions across 9 categories |

**Total new test assertions: 89.** All green.

---

## Doctrinal status

### §1b sixth-instance — ANCHORED ON SHIP

Joins the project's running list of §1b validated-suggester pattern instances:

| # | Instance | Anchored | Pattern shape |
|---|---|---|---|
| 1 | Track 6 #5.1 SRD suggester | S26 | LLM proposes + SRD validator + DM paste `!init madd` |
| 2 | NPC State-Sync suggester | S41 post-pivot | Engine proposes 3-line block + DM pastes commands |
| 3 | Quest Layer v0.1 offer suggester | S57 Reading-2 | Predicate-gated + DM `/quest accept` slash |
| 4 | Composition Layer v0 act suggester | S60 | Predicate-gated + DM `/quest act advance` slash |
| 5 | (Reserved — running-list footnote) | — | — |
| **6** | **Canon Bootstrap Bot v0** | **N-10 (this ship)** | **Premise + sequence-pointer-gated + DM `/bootstrap accept` slash** |

Deterministic-only validator throughout. Cosine-similarity precedent honored (none used). Bot proposes via `#dm-aside`; engine writes via existing §17 single-writers on operator approval.

### §59 sibling count: 17 → 19

Two new pure-function-in-orchestration siblings:
- **#18 — `compute_bootstrap_sequence_directive`**: pointer-driven; pure; no LLM call; decides next card type from `BOOTSTRAP_CARD_SEQUENCE_V0`.
- **#19 — `compute_bootstrap_card_directive`**: extraction-tier LLM call with deterministic post-validator; soft-fail on LLM error per §59 contract; per-fire telemetry.

(Note: the implementation prompt referenced "16th + 17th" but spec §1.E+§1.F call out #17+#18; project-wide canonical count after Composition Layer v0 = 15, so these become 16 and 17 if you count from the last formal anchor, OR #18 and #19 if you include all named siblings. I've used #18 + #19 in code comments per spec §1.E/§1.F.)

### §17 single-writer audit (post-ship)

| Field | Writer | Status |
|---|---|---|
| `dnd_campaigns.premise` | `update_campaign_premise` only | ✓ new writer |
| skeleton.md file | `skeleton_md_append_element` only (engine-side); operator hand-edits remain outside engine scope per §11.12 (c) defer | ✓ new writer (first-of-its-kind for this file) |
| `dnd_npcs` (bootstrap path) | `npc_upsert` (existing) | ✓ unchanged |
| `dnd_quests` (bootstrap path) | `quest_add` + optional `quest_offer` (existing) | ✓ unchanged |
| `dnd_quest_acts` (bootstrap path) | `quest_act_upsert` (existing) | ✓ unchanged |
| `dnd_locations` (bootstrap path) | `location_upsert` (existing) | ✓ unchanged |

No §17 violations. Bot proposes; operator approves via slash; engine writes via existing helpers. Bot's draft state (`_bootstrap_session`) is in-memory only — never canon.

### §76 audit on new fields

| Surface | LLM-writable | Persisted | Retrieved | Narratively inferential | Verdict |
|---|---|---|---|---|---|
| `dnd_campaigns.premise` | **No** (operator-only) | Yes | Yes (build_dm_context low-tactical-band) | Yes (prose) | **3/4 safe** |
| `_bootstrap_session` (in-memory) | Yes | **No** (process-local) | No | No | 1/4 safe |
| Bot-proposed faction → skeleton.md | Yes (LLM) | Yes (file) | Yes (skeleton parser → prompt) | Yes | **3/4 safe — §1b gate is §17-equivalent** |
| Bot-proposed NPC → dnd_npcs | Yes (LLM) | Yes | Yes | Yes | **3/4 safe — same gate** |
| Bot-proposed Quest → dnd_quests | Yes (LLM) | Yes | Yes | Yes | **3/4 safe — same gate** |
| Bot-proposed Quest Act → dnd_quest_acts | Yes (LLM) | Yes | Yes | Yes | **3/4 safe — same gate** |
| Bot-proposed Location → dnd_locations | Yes (LLM) | Yes | Yes | Yes | **3/4 safe — same gate** |

Per S41 §76 footnote: where an LLM-influenced write flows through a §17-disciplined helper, the column does NOT structurally become a 4/4 contamination surface. The `/bootstrap accept` slash is the deterministic gate equivalent of §17 — it's required before any canonical write, and the validator's reject path falls through cleanly.

**Zero new 4/4 §76 surfaces.** Authored-canon volume expands without expanding LLM-writable column surface.

---

## Test counts (post-ship total)

| Test file | Asserts | Status |
|---|---|---|
| `test_canon_bootstrap_bot_v0.py` | **89** | New — All pass |
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

**Total: 943 assertions across 20 test files.** All green.

---

## Migration verification

```
$ sqlite3 /mnt/virgil_storage/virgil.db "PRAGMA table_info(dnd_campaigns);"
0|id|INTEGER|0||1
...
8|created_by_user_id|TEXT|0|''|0
9|premise|TEXT|0|''|0     ← N-10 migration applied
```

Migration ran cleanly at engine init. Existing rows have `premise=''` default (NULL-safe; no row corruption).

---

## Inventory-before-patch — schema recon contradiction surfaced + resolved

During implementation testing, `is_bootstrap_complete` SQL failed with `no such column: campaign_id` on `dnd_quest_acts`. **`dnd_quest_acts` has NO `campaign_id` column** — per Composition Layer v0 §1.C lock, acts join to campaign via `quest_id → dnd_quests.campaign_id`.

**Resolution (without silent revision):** dropped `dnd_quest_acts` from `is_bootstrap_complete`'s OR list. Bootstrap-complete detection now checks NPC + quest + location skeleton_origin=1 counts. Acts always anchor to a parent quest with `skeleton_origin=1`, so the parent signal covers acts implicitly. Documented inline in `dnd_engine.py`.

**No HALT triggered.** Recon contradiction resolved with named workaround per Composition Layer v0 §1.C invariant.

---

## §1b sixth-instance — anchoring evidence

The architectural shape held cleanly:
1. **Bot proposes via `#dm-aside`.** `compute_bootstrap_card_directive` produces a structured proposal via extraction-tier LLM call. Output validated by deterministic Python (`_validate_proposal`) before card-post.
2. **Deterministic gate confirms safety.** Required fields, length caps, name-uniqueness (case-insensitive), FK existence checks. Cosine-similarity NOT used (precedent honored).
3. **DM approves by slash.** `/bootstrap accept` is the canonical approval gate. Per-card; no bulk-approve at v0.
4. **Engine executes.** Existing §17 single-writers (`npc_upsert`, `quest_add`, `quest_act_upsert`, `location_upsert`) perform the canonical write. New first-of-its-kind writer (`skeleton_md_append_element`) handles skeleton.md file appends.

**No §1a leak.** Bot's draft state (`current_proposal`) never enters canon without slash approval. Draft state is in-memory only, cleared on process restart, never persisted to DB.

---

## Forward-coupling reminders

**For S68 / N-4 (NPC commitment + pronouns):**
- Bootstrap-origin NPCs (`skeleton_origin=1`) carry pronouns in the FIRST SENTENCE of their description, per spec §11.9 lock and `_BOOTSTRAP_SIGNAL_NPC` corpus signal substrate.
- N-4's pronoun-column migration extractor should treat this as the EXPECTED starting state, NOT edge case. Three NPC classes per Review §3.9 forward-coupling:
  - Bootstrap-origin (skeleton_origin=1, post-N-10): pronouns in first sentence, predictable shape.
  - Parser-extracted (skeleton_origin=0): pronouns scattered, may be missing.
  - Hand-authored pre-N-10 (skeleton_origin=1): operator-author-dependent.

**For S69 / Causality Engine v0 (factions):**
- Faction structured fields (goal, pressure_shape, engagement_signals) are stored as labeled prose under faction H3 entries in skeleton.md `## Factions` section. Example rendered shape:
  ```
  ### Stonehold Guild (merchants)
  A merchant alliance based in Stonehold.
  Goal: Keep the trade road open.
  Pressure: Bandit raids climbing.
  Engagement signals: Caravan raid reports.
  ```
- S69 introduces `dnd_factions` table and migrates from `parse_skeleton_file(campaign_id)['factions']`. Migration extracts goal/pressure/engagement from the prose labels above (clean prefix shape).
- S69 spec must decide: promote factions to DB at S69 ship (clean migration), or continue parsing skeleton.md per turn (no schema migration). Lean: promote at ship; mirrors Quest Layer v0's skeleton-extends-DB pattern.

---

## Restart + Discord verify

Bot restarted at 2026-05-14T15:26:41 PDT. Status `active`. Boot log:
- `srd_resolver: index loaded entries=334`
- `fk_cascade_init: pragma_supported=1`
- `wal_init: journal_mode=wal wal_autocheckpoint=1000 synchronous=NORMAL`
- `chroma_init: sessions=1096 knowledge=740307`
- `starting Discord DnD bot`
- `synced 28 slash commands` (was 27 pre-N-10; +1 for /bootstrap group)
- `commands_doc_update: count=51 changed=1` (was 44; +7 bootstrap subcommands)

**Operator-paste-verbatim Discord verify scenarios (per spec §10):**

1. **End-to-end bootstrap on fresh campaign:**
   ```
   /newcampaign name:"Bootstrap Test"
   /bootstrap begin premise:"Grimdark frontier mining town, hexcrawl, the mine collapsed and something climbed out. My character is a fighter."
   ```
   Then walk the cards: `/bootstrap accept` on faction, `/bootstrap reroll` on first NPC, `/bootstrap accept` on second NPC card, etc. After session completes, verify:
   - `/quest list` shows starter quests with `skeleton_origin=1`.
   - `sqlite3 ... "SELECT canonical_name, role FROM dnd_npcs WHERE campaign_id=N AND skeleton_origin=1;"` lists bootstrap NPCs.
   - `cat scripts/campaigns/N/skeleton.md` shows H1+premise+factions+NPCs+quests+locations sections.
   - `dnd_campaigns.premise` non-empty.

2. **Prerequisite check on bootstrap-complete campaign:**
   On the campaign from (1): `/bootstrap begin premise:"different"`. Expected: error per §11.5 ("already bootstrap-complete").

3. **Field override:**
   On a new test campaign during NPC card:
   ```
   /bootstrap manual overrides:'canonical_name:"Eldrin Stormbow" role:"village herald"'
   ```
   Expected: card re-posts to `#dm-aside` with overrides applied; subsequent `/bootstrap accept` writes those values.

4. **Skip + soft-reroll:**
   On a new campaign during faction card: `/bootstrap skip` → next card fires. During NPC card: `/bootstrap reroll` ×3 → each reroll produces a different draft (LLM gets the reroll hint).

5. **Mid-session abort:**
   On a new campaign mid-session: `/bootstrap end`. Expected: canonical state preserves whatever was approved; campaign is bootstrap-complete (premise + at least one skeleton_origin=1 row).

6. **Skeleton.md inspection:**
   On the campaign from (1): `cat scripts/campaigns/N/skeleton.md`. Expected: structured markdown matching the existing parser format (H1+H2s+H3s per R2), `## Factions` / `## Primary NPCs` / `## Major hooks` / `## Key locations` sections.

7. **Regression checks:**
   On the bootstrap-completed campaign, run scenarios from S66 + S67:
   ```
   /travel destination:"<location>" elapsed:"1 hour"
   /quest complete <quest_id>
   ```
   Expected: no regressions on prior closed work.

**Journal greps for operator verify:**
```bash
journalctl --user -u virgil-discord | grep "bootstrap_card_proposed"     # per-card fires
journalctl --user -u virgil-discord | grep "bootstrap_card_approved"     # operator approvals
journalctl --user -u virgil-discord | grep "bootstrap_card_skipped"      # skip events
journalctl --user -u virgil-discord | grep "bootstrap_card_reroll"       # reroll counts
journalctl --user -u virgil-discord | grep "bootstrap_session_opened"    # session start
journalctl --user -u virgil-discord | grep "bootstrap_session_completed" # session end
journalctl --user -u virgil-discord | grep "skeleton_md_append"          # file writes
journalctl --user -u virgil-discord | grep "campaign_premise_set"        # premise writes
```

```bash
sqlite3 /mnt/virgil_storage/virgil.db "SELECT id, name, premise FROM dnd_campaigns WHERE premise != '';"
sqlite3 /mnt/virgil_storage/virgil.db "SELECT COUNT(*) FROM dnd_npcs WHERE skeleton_origin=1;"
sqlite3 /mnt/virgil_storage/virgil.db "SELECT COUNT(*) FROM dnd_quests WHERE skeleton_origin=1;"
```

---

## Rollback procedure

1. Disable bootstrap_group: comment out `bot.tree.add_command(bootstrap_group)` in `discord_dnd_bot.py`.
2. (Optional) Drop premise column — not required, but if rolling back fully:
   ```sql
   ALTER TABLE dnd_campaigns DROP COLUMN premise;  -- SQLite ≥3.35
   ```
   Or just leave the column unused.
3. Revert imports for `update_campaign_premise`, `is_bootstrap_complete`, `skeleton_md_append_element` in `discord_dnd_bot.py`.
4. Premise rendering in `build_dm_context` is gated on `campaign.get('premise')` non-empty; if column is dropped, this gracefully evaluates to empty and renders nothing.
5. Restart `virgil-discord`.

Pre-ship snapshot: `/mnt/virgil_storage/archive/virgil_N10_preship.db` (20.7 MB).

---

## End-of-session state

- 4 files touched (3 modified, 1 new): `dnd_engine.py`, `dnd_orchestration.py`, `discord_dnd_bot.py`, `skeleton_writer.py` (new).
- 1 spec locked: `CANON_BOOTSTRAP_BOT_V0_SPEC.md` (DRAFT → LOCKED).
- 1 review doc already shipped pre-session: `CANON_BOOTSTRAP_BOT_V0_REVIEW.md`.
- 1 handoff doc: this file.
- 7 new slash commands (`/bootstrap` group with begin/accept/skip/reroll/manual/status/end).
- 2 new §59 siblings (#18 + #19, depending on count anchor).
- §1b sixth-instance ANCHORED.
- 89 new test assertions; 943 total assertions across 20 test files, all green.
- Bot restarted, boot clean, 28 slash commands synced (51 individual commands).
- Pre-ship snapshot in archive.
- §17/§76/§1a/§1b doctrinal audits all clean.
- Forward-coupling notes filed for S68/N-4 and S69.

**Next session candidates:**
- **S68 — N-3 + N-4 NPC commitment rails** (pricing math + pronoun lock). N-10 produces the substrate; N-4's migration treats bootstrap-origin NPCs as expected starting state.
- **S67.1 — close the 3 mitigated §76 surfaces from S67 Phase C audit.**
- **Operator playtest of N-10** — bootstrap a fresh campaign end-to-end; verify card UX, prompt quality, skeleton.md output shape. Live signal informs v0.1 patches.
