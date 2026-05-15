# S67 Handoff — Tier 1 Cleanup, Batch 3 (FINAL) + Arc Closure Statement

**Date:** 2026-05-14
**Session:** S67 (durability + §76 audit pass)
**Pre-ship snapshot:** `/mnt/virgil_storage/archive/virgil_S67_preship.db` (20.7 MB, 2026-05-14T13:10 PDT)
**Discipline:** pre-ship snapshot + per-fix rollback notes + sequential commits (S65 standing practice).

---

## Fix Inventory (2 planned, 1 SHIPPED + 1 PARTIAL/HALT)

| Fix | Status | Outcome |
|---|---|---|
| Fix 1 — F-026 durability | ✅ SHIPPED | WAL pragma + scheduled backup (systemd timer) + 30-day retention + post-snapshot PC push + restore drill passed. |
| Fix 2 — F-016 §76 closure | ⚠️ **PARTIAL** | Phase A audit shipped (found 3 NEW 4/4 surfaces) → Phase C HALT per plan. Phase B (`current_scene` original target) SHIPPED. |

---

## Files Touched, LOC Delta Per Fix

| Fix | File | LOC delta | Notes |
|---|---|---|---|
| Fix 1A | `dnd_engine.py` | +18 / -0 | WAL pragma block in `db_init` (journal_mode=WAL + wal_autocheckpoint=1000 + synchronous=NORMAL) with telemetry. |
| Fix 1B | `scripts/virgil_backup.sh` | +85 (new) | Backup script: sqlite3 .backup, integrity_check, 30-day retention, background push-all trigger. |
| Fix 1B | `~/.config/systemd/user/virgil-backup.service` | +12 (new) | OneShot service definition. |
| Fix 1B | `~/.config/systemd/user/virgil-backup.timer` | +9 (new) | OnCalendar=*-*-* 03:30:00 + Persistent=true. |
| Fix 1C | `virgil-docs/planner-scratch/restore_drill.md` | +120 (new) | One-shot ops doc, restore procedure verified live. |
| Fix 2A | `virgil-docs/planner-scratch/S67_phase76_audit.md` | +220 (new) | Audit findings on 9 candidate surfaces. |
| Fix 2B | `dnd_engine.py` | +15 / -20 | Drop CURRENT SCENE block; redirect `scene_blurb` → `last_dm_response`; retire init_end_buffer_reset's `update_scene` call. |
| Fix 2B | `discord_dnd_bot.py` | +15 / -3 | Drop 2 `update_scene` write sites; drop `update_scene` from import. |
| Fix 2B | `test_play_smoke.py` | +2 / -4 | Drop the `mock.patch.object(bot_mod, 'update_scene')` patches (the symbol no longer exists on bot module). |
| Fix 2D | `test_current_scene_closure.py` | +200 (new) | 15 adversarial tests: AST sweep, source-level checks, behavioral verification, back-compat. |

**Total new test assertions: 15** (S67 contribution).

---

## Fix 1 — F-026 Durability

### Phase A — WAL mode

**`dnd_engine.py:db_init`** now sets three pragmas at engine init:
- `PRAGMA journal_mode=WAL` (database-level; persists across opens)
- `PRAGMA wal_autocheckpoint=1000` (caps WAL file growth)
- `PRAGMA synchronous=NORMAL` (recommended pairing with WAL — full safety, lower fsync cost than FULL)

Boot log: `wal_init: journal_mode=wal wal_autocheckpoint=1000 synchronous=NORMAL`. Verified post-restart at 2026-05-14T13:25 PDT.

WAL mode survives SIGKILL: the journal file replays on next open. Tested via the live setup (existing prod DB was migrated from `delete` to `wal` mode by the first db_init call; no data loss observed).

### Phase B — Scheduled backup

**`scripts/virgil_backup.sh`** (new):
- Uses `sqlite3 .backup` (online backup API, safe against live WAL DB).
- Names snapshots `virgil_nightly_YYYYMMDD_HHMMSS.db`.
- Runs `PRAGMA integrity_check` on the new snapshot; exits non-zero on corruption (preserves the bad file for diagnostics).
- 30-day rolling retention: `find ... -name 'virgil_nightly_*.db' -mtime +30 -type f | xargs rm`. Session preship snapshots (`virgil_S65_preship.db`, etc.) preserved indefinitely.
- Triggers `push-all-to-pc.sh` in background after snapshot success.

**Systemd timer:**
- `~/.config/systemd/user/virgil-backup.timer` — `OnCalendar=*-*-* 03:30:00 Persistent=true`.
- `~/.config/systemd/user/virgil-backup.service` — `Type=oneshot ExecStart=/bin/bash /home/jordaneal/scripts/virgil_backup.sh`.
- Enabled via `systemctl --user enable --now virgil-backup.timer`. Next firing scheduled for 2026-05-15 03:30 PDT.

Manual snapshot verified: ran `virgil_backup.sh` at 13:12 PDT; produced `virgil_nightly_20260514_131216.db` (20.7 MB); integrity_check=ok.

### Phase C — Restore drill

Performed at 13:12 PDT against the just-produced nightly snapshot:
- Copy to `/tmp/virgil_restore_test.db`
- `PRAGMA integrity_check` = ok ✓
- 25 expected tables present ✓
- `dnd_campaigns` recent rows readable (test campaigns 52-56) ✓
- `dnd_quests` recent rows readable (S65.1 Test Quest #27 + later) ✓
- `dnd_scene_state` recent rows readable ✓
- Temp file cleaned up post-verify.

**Drill outcome: PASS.** Documented in `planner-scratch/restore_drill.md` with full procedure (9-step recovery flow, fallback on schema mismatch, post-restore verification).

### Rollback procedure (Fix 1)

1. **WAL → rollback journal:** Run `sqlite3 virgil.db "PRAGMA journal_mode=DELETE;"`. Restart bot. (The new `wal_init` block in `db_init` will re-apply WAL on next start — if rollback is intentional, also remove the pragma block from `dnd_engine.py`.)
2. **Disable backup timer:** `systemctl --user disable --now virgil-backup.timer`. Optionally `rm ~/.config/systemd/user/virgil-backup.{service,timer}`.
3. **Remove backup script:** `rm /home/jordaneal/scripts/virgil_backup.sh`. (Existing nightly snapshots in `archive/` are preserved — they're durable artifacts, not part of the rollback.)

---

## Fix 2 — F-016 §76 Closure (PARTIAL — Phase B only, Phase C HALTED)

### Phase A audit (SHIPPED)

Applied the four-property latent-canon test to 9 candidate contamination surfaces. Findings doc: `planner-scratch/S67_phase76_audit.md`.

**Result: 3 NEW 4/4 surfaces** beyond `current_scene`:
| # | Surface | Mitigation present? |
|---|---|---|
| 2 | `dnd_consequences.summary` | YES — promotion gates (3×3×5) |
| 3 | `dnd_npcs.description` (consequence-fold) | YES — promotion gates (3×3×5) |
| 4 | Chroma "Relevant past events" | YES — distance cutoff 0.5 + S44 combat-bypass |

**Not 4/4:** dnd_quests.summary (operator-only post-S65.1), dnd_quest_acts.act_description (operator-only), suggester offer dialogue (no DB persistence), dnd_npcs.personality/appearance (no schema), dnd_scene_state.last_dm_response (signal extraction only, not prose re-injection).

### Phase C HALT decision

Per S67 plan: "If audit surfaces 3+ new contamination surfaces: HALT, push the findings doc to operator." Three new surfaces hits the HALT threshold exactly.

**Phase C deferred to S67.1.** Critical caveat surfaced in audit: all 3 new surfaces have non-trivial mitigation layers (promotion gates / similarity cutoffs) that the F-016 target lacked. The HALT preserves blast-radius budget but does NOT imply equal urgency. Recommended S67.1 priority:
1. Chroma DM-stores (highest empirical risk — every prompt touches chroma)
2. Consequence fold (Surfaces 2+3 as a unit — they're entangled)

Audit doc also proposes two **doctrinal property extensions** for §76 (5th: rate-unlimited write; 6th: verbatim re-injection) which would tighten the discrimination between OPEN and MITIGATED 4/4 surfaces. Filed as candidate for post-S68 F-XX anchoring walk.

### Phase B closure (SHIPPED — original F-016 target)

**Write paths retired (3 sites):**
- `discord_dnd_bot.py:_dm_respond_and_post` line 3451 — every-narration write of `f"Last actions: {action} | DM: {response}"`. The unmitigated 4/4 surface. **REMOVED.**
- `discord_dnd_bot.py:play` line 4915 — `/play` opening narration snapshot. **REMOVED.**
- `dnd_engine.py:init_end_buffer_reset_post_init` line 1687 — sentinel write paired with last_dm_response sentinel. **REMOVED** (redundant — last_dm_response sentinel covers the reset semantics).
- `discord_dnd_bot.py:44` — `update_scene` removed from the dnd_engine import line.

**Read paths redirected (2 sites):**
- `build_dm_context` — `=== CURRENT SCENE ===` block deleted entirely. `current_scene_section = ""` always. The S44 verify-pass-3 combat-narration suppression is generalized to all modes.
- `dm_respond:scene_blurb` line 7225 — redirected from `campaign.current_scene[:200]` to `scene_state.last_dm_response[:200]`. (This feeds `multi_query_knowledge_search` for CRD3/FIREBALL exemplar retrieval — embedding query, not prompt prose. Switching the source from self-summarized to verbatim prior narration is the §76-correct redirect.)

**Schema preserved (`current_scene` column stays):**
- Per plan: "`current_scene` column stays in schema for now; just stops being written. Cleanup deferred (post-Tier-1 schema sweep)."
- `get_active_campaign` still SELECTs the column and returns the dict key — back-compat preserved. Any external read of `campaign['current_scene']` returns the now-stale value (empty string for new campaigns; whatever was last written for pre-S67 campaigns). No production code now reads it.

**Mitigation layers carried forward:**
- Scene-detail memory now flows through:
  - `=== SCENE STATE ===` block (Ship 2 canon — structured fields: location_label, day_phase, mode, last_player_action, recent_npcs, etc.)
  - `=== RELEVANT PAST EVENTS ===` from chroma_search (distance-cutoff 0.5 mitigated, S44 combat-bypass active)
  - Skeleton-loaded authored canon (`location_get`, `npc_get` from skeleton.md imports)
  - `last_dm_response` for signal extraction (reaction-verb gates in commitment directive)

### Phase D — Adversarial verify (SHIPPED)

`test_current_scene_closure.py` — 15 tests across 7 categories:
1. **AST sweep:** zero `update_scene(...)` call sites in both `discord_dnd_bot.py` and `dnd_engine.py` (excluding the `def update_scene` definition itself).
2. **Source-level imports:** `update_scene` not in bot's import block.
3. **Source-level prompt:** `=== CURRENT SCENE ===` not in any live (non-comment) code path.
4. **Source-level reader:** `scene_blurb` pulls from `last_dm_response`, not `current_scene`.
5. **Behavioral:** fresh campaign has empty `current_scene`; even after `update_last_dm_response` writes, `current_scene` stays empty.
6. **Back-compat:** `get_active_campaign` still returns `current_scene` key (column not dropped).
7. **Regression:** S67 Fix 1A WAL init still present in db_init.

All 15 pass.

### Rollback procedure (Fix 2 Phase B)

1. Restore `update_scene` import on `discord_dnd_bot.py:44`.
2. Restore `update_scene(campaign['id'], ...)` call at `discord_dnd_bot.py:3451` (LLM-narration write).
3. Restore `update_scene(campaign['id'], opening[:500])` at `discord_dnd_bot.py:4915` (`/play` opening write).
4. Restore `update_scene(campaign_id, _INIT_END_CLOSEOUT_SCENE)` at `dnd_engine.py:1687`.
5. Restore the `=== CURRENT SCENE ===` block in `build_dm_context` (with the S44 combat-mode suppression).
6. Restore `scene_blurb = (campaign.get('current_scene') or '')[:200]` at `dnd_engine.py:7225`.
7. Restore the `mock.patch.object(bot_mod, 'update_scene')` patches in `test_play_smoke.py`.
8. Restart `virgil-discord`.

Behavior reverts: every narration turn writes a self-summarized scene blurb; next-turn prompt re-injects it; drift compounds.

---

## Test Counts (S67 contribution)

| Test File | New | Updated | Status |
|---|---|---|---|
| `test_current_scene_closure.py` | 15 | — | All pass |
| `test_play_smoke.py` | — | 2 mock-patch fixes (drop retired `update_scene` patch) | 6/6 pass |

**Total assertion count (S65 + S65.1 + S66 + S67):** **854 across 19 test files** (29 advance_time pytest + 825 inline-script asserts). All green.

---

## §17 Single-Writer Audit (S67 closure check)

| Surface | Writer | Confirmed unchanged |
|---|---|---|
| `dnd_campaigns.current_scene` | **NONE** (LLM-narration write retired) | ✓ Closed; column orphaned. |
| `dnd_scene_state.last_dm_response` | `update_last_dm_response` (single writer per S39) | ✓ Unchanged. |
| Chroma collection | `chroma_store` only | ✓ Unchanged. |
| `dnd_consequences.summary` | `consequence_upsert` only | ✓ Unchanged. |
| `dnd_npcs.description` | `npc_upsert` + `maybe_promote_consequences` (gated fold) | ✓ Unchanged. |
| WAL pragma state | `db_init` only (database-level, idempotent) | ✓ New writer. |

---

# Tier 1 Cleanup Arc — CLOSURE STATEMENT

**Arc shape:** Three sessions (S65 → S65.1 → S66 → S67), six P0 fixes, doctrine candidate evidence accumulated.

## Fixes Shipped (across the arc)

| Fix | Origin | Shipped in | Long-horizon ID |
|---|---|---|---|
| F-021 `/play` NameError | S65 plan Fix 1 | S65 | F-021 ✅ |
| DC-less roll closure | S65 plan Fix 3 | S65 | (no F-ID) |
| `#dm-aside` role-confusion | S65 plan Fix 4 | S65 | (no F-ID) |
| S65.A Format unification | Same-session followup | S65 | (no F-ID) |
| C-2 npc_upsert tuple unpacking | S65.1 plan Fix 1 | S65.1 | (test bug) |
| F-008 AUTO_EXECUTE close | S65 plan Fix 2 (HALTED) → S65.1 plan Fix 2 | S65.1 | F-008 ✅ |
| N-1 hint extractor tightening | S65.1 plan Fix 3 | S65.1 | (no F-ID) |
| `/travel` duration floor + truthful embed | S66 plan Fix 1 | S66 | (no F-ID) |
| F-031 quest delivery silent fail | S66 plan Fix 2 | S66 | F-031 ✅ |
| F-035 loot auto-claim + refusal | S66 plan Fix 3 | S66 | F-035 ✅ |
| F-026 WAL + backup + restore drill | S67 plan Fix 1 | S67 | F-026 ✅ |
| F-016 §76 closure on current_scene | S67 plan Fix 2 Phase B | S67 | F-016 ✅ |

**11 fixes shipped. 5 long-horizon F-IDs closed: F-008, F-016, F-021, F-026, F-031, F-035 (6 — undercount fixed).**

## HALTed / Deferred (filed to followup)

- **S67 Fix 2 Phase C** — 3 new 4/4 §76 surfaces (consequences.summary, npcs.description fold, chroma DM stores) found via Phase A audit. HALT per plan blast-radius budget. Filed for S67.1.
- **N-5** narrative-loot LLM extraction — F-035 core (structured combat loot) closed in S66; ad-hoc narrative loot (chest contents, found items) filed as follow-up.
- **N-2/N-3/N-4** NPC commitment + pricing math + pronoun lock — multi-spec scope, filed for S68 dedicated arc.

## Standing Practices Adopted (from S65 onward, carried through S67)

1. ✅ **Pre-ship DB snapshot** before any change — verified at S65, S65.1, S66, S67.
2. ✅ **Rollback procedure documented per fix** — every shipped fix carries verbatim revert instructions.
3. ✅ **Sequential commits with atomic test verify** — Fix N tests green before Fix N+1 starts.
4. ✅ **Feature-disable switches for new always-on behavior** — `AUTO_EXECUTE_ENABLED` flag (S65.1), upcoming N-X work to consider the same pattern.

## Doctrine Candidate Progress

Two doctrine candidates accumulated evidence across the arc:

**A. "Narration-commit gap as systemic contamination surface."** Four observed instances:
- F-008 AUTO_EXECUTE (S65.1) — narration emits state-change directive, engine doesn't gate it; LLM is the writer.
- F-031 quest delivery (S66) — narration says "reward given," engine writes nothing.
- F-035 loot evaporation (S66) — narration says "you scavenge the bodies," engine writes nothing.
- N-1 hint extractor (S65.1) — engine emits hints from narration mentions even when no state change happened (inverse of the above).

The pattern: narration assertions and engine commits drift apart. F-031 and F-035 are inventory-side; F-008 is multi-state-side; N-1 is the inverse (over-commit on narration mention). The four-property §76 test catches some of this; the broader pattern is "any narrative assertion that should be a state change OR shouldn't be one." Candidate F-XX after N-3/N-4 ships (NPC-side analogues complete the triangle).

**B. "Four-property §76 test refinement — mitigation as a separate axis."** The S67 audit found that 3 of 4 newly-identified 4/4 surfaces have mitigation layers (promotion gates, distance cutoffs) that materially slow contamination rate. The §76 test fires on raw properties; remediation urgency depends on mitigation. Proposed 5th + 6th doctrinal property candidates (rate-unlimited write, verbatim re-injection) tighten the discrimination. Filed as a §76 amendment proposal for post-S68.

## Next Session Recommendation

**S68 — NPC-side commitment rails (N-3 + N-4 + N-5 bundle).**

Per S66 doctrine note: "Two more inventory-side instances would complete a pattern triangle: NPC commitments (N-3 pricing math) + NPC pronouns (N-4 gender drift) are the NPC-side analogues."

Proposed scope:
- **N-3** — Anti-gaslight + price-history rail (engine confronts player claims about prior NPC commitments with scene-log evidence).
- **N-4** — `dnd_npcs.pronouns` column + pronoun-lock anti-drift rail.
- **N-5** — Narrative-loot LLM extraction (chest contents, ad-hoc found items).

After S68 ships, four narration-commit-gap closures across inventory + NPC + state-change-directive surfaces will sit in the long-horizon review. That's the F-XX anchoring evidence cluster.

**Alternative:** S67.1 — close the 3 mitigated §76 surfaces (Phase C of F-016). Smaller scope; relieves the §76 backlog. Could ship in 1-2 days.

Operator decision: prioritize doctrine-walk evidence (S68 path) or §76 hygiene cleanup (S67.1 path).

---

## Restart + Discord Verify (S67-specific)

Bot restarted at 2026-05-14T13:25 PDT. Status `active`. Boot log confirms:
- `srd_resolver: index loaded entries=334`
- `fk_cascade_init: pragma_supported=1`
- `wal_init: journal_mode=wal wal_autocheckpoint=1000 synchronous=NORMAL` ✓ NEW
- `chroma_init: sessions=1096 knowledge=740307`
- `starting Discord DnD bot`

**Operator-paste-verbatim test scenarios:**

1. **WAL mode confirm:**
   ```bash
   sqlite3 /mnt/virgil_storage/virgil.db "PRAGMA journal_mode;"
   ```
   Expected: `wal`.

2. **Timer confirm:**
   ```bash
   systemctl --user list-timers virgil-backup.timer
   ```
   Expected: shows the timer scheduled for tomorrow 03:30 PDT.

3. **Manual snapshot test:**
   ```bash
   bash /home/jordaneal/scripts/virgil_backup.sh
   ls -lt /mnt/virgil_storage/archive/virgil_nightly_*.db | head -3
   ```
   Expected: new snapshot lands in archive; integrity_check=ok in log; PC push fires.

4. **S64 baker-scene reproduction (current_scene drift check):**
   Re-create a multi-turn baker interaction. Watch for: vendor description drift, prior-narration paraphrase contamination. Expectation: **stable now**. Pre-S67 the LLM read its own prior summary every turn → drift. Post-S67 the LLM reads structured SCENE STATE + chroma exemplars only.

5. **5-turn exploration scene stability:** Force a long exploration scene without `/travel` or `/compress`. Track whether scene details (named NPCs, location-specific objects) paraphrase-drift. Expectation: stable.

6. **N-1 baker regression check** (S65.1): re-run the dispute scenario; confirm hint extractor still fires only on real transactions.

7. **F-031 / F-035 regression check** (S66): `/quest deliver` + combat-loot scenarios; confirm party stash still populates and `/loot drop` still works.

**Journal greps:**
```bash
journalctl --user -u virgil-discord | grep "wal_init"            # confirms WAL on every restart
journalctl --user -u virgil-discord | grep "update_scene"        # should be ZERO post-patch
journalctl --user -u virgil-discord | grep "current_scene"       # should be empty (block retired)
systemctl --user status virgil-backup.timer                       # confirms timer active
tail /mnt/virgil_storage/digest/virgil_backup.log                 # last backup outcome
```

---

## End-of-Session State

- 1 fix shipped fully (F-026 durability — WAL + backup + restore drill all live).
- 1 fix PARTIAL (F-016 Phase B current_scene closed; Phase C HALTed → S67.1 candidate).
- 0 unscheduled HALT escalations (Phase C HALT was planned criteria-driven).
- F-016 CLOSED (the named long-horizon ID is the unmitigated current_scene surface).
- F-026 CLOSED.
- Tier 1 Cleanup Arc CLOSED — 11 fixes shipped across S65/S65.1/S66/S67.
- Pre-ship snapshot in archive.
- Standing-practice adoption: confirmed across all three sessions.
- Doctrine candidate evidence accumulated; F-XX anchoring walk scheduled post-S68.
- Total test count: 854 across 19 test files. All green.
