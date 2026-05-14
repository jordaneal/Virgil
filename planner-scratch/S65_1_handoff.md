# S65.1 Handoff — Tier 1 Cleanup, Batch 1 Follow-up

**Date:** 2026-05-14
**Session:** S65.1 (Path B cleanup cadence, S65 carryover)
**Pre-ship snapshot:** `/mnt/virgil_storage/archive/virgil_S65_1_preship.db` (20.7 MB, 2026-05-14T10:23 PDT)
**Discipline:** pre-ship snapshot, rollback notes per fix, feature-disable switches.

---

## Fix Inventory (3 planned, 3 SHIPPED)

| Fix | Status | Outcome |
|---|---|---|
| Fix 1 — C-2 npc_upsert tuple unpacking | ✅ SHIPPED | 5 test files updated to unpack `(gid, _) = npc_upsert(...) or (None, False)`. 463 prior-failing assertions now green. |
| Fix 2 — C-1 F-008 AUTO_EXECUTE close | ✅ SHIPPED | Test-harness migrated to `quest_add_with_dedup`; AUTO-EXECUTE prompt section removed; `AUTO_EXECUTE_ENABLED = False` feature flag; 21 adversarial tests green. §1b 3rd-instance anchor (Quest Layer v0.1): **PROVISIONAL → ANCHORED**. |
| Fix 3 — N-1 Hint extractor tightening | ✅ SHIPPED | Transaction-verb gate + cross-turn dedup + telemetry; 26 baker-scenario tests green. |

---

## Files Touched, LOC Delta Per Fix

| Fix | File | Lines changed | Notes |
|---|---|---|---|
| Fix 1 | `test_dnd_npcs.py` | +10 / -10 | 10 sites — uniform `var, _ = npc_upsert(...) or (None, False)` pattern. |
| Fix 1 | `test_dnd_locations.py` | +1 / -1 | 1 site. |
| Fix 1 | `test_dnd_consequences.py` | +5 / -5 | 5 sites. |
| Fix 1 | `test_consequence_command.py` | +3 / -3 | 3 sites. |
| Fix 1 | `test_directive_emit.py` | +1 / -1 | 1 site. |
| Fix 2 | `dnd_engine.py` | +60 / -45 | New `quest_add_with_dedup` (~30 LOC); `AUTO_EXECUTE_ENABLED` feature flag (~10 LOC); `execute_auto_actions` early-return when disabled (~5 LOC); removed AUTO-EXECUTE prompt block (~24 LOC); rewrote PLAYER UI SUGGESTIONS framing (~10 LOC). |
| Fix 2 | `test_dnd_npcs.py` | +20 / -25 | S7 dedup section migrated from `execute_auto_actions` to `quest_add_with_dedup` (8 → 7 sites; one new `was_new` assertion). |
| Fix 2 | `test_auto_execute_closed.py` | +175 (new) | 21 adversarial verify tests across 7 categories. |
| Fix 3 | `mechanical_hints.py` | +110 / -10 | Transaction-verb closed vocab + gate function (~50 LOC); process-local cross-turn dedup (~30 LOC); enriched system prompt with dispute/quote/question examples (~25 LOC); per-fire and per-suppression telemetry (~5 LOC); new `campaign_id` parameter to `parse_mechanical_hints`. |
| Fix 3 | `discord_dnd_bot.py` | +5 / -3 | Thread `campaign_id` through `_attach_hints` → `parse_mechanical_hints`. |
| Fix 3 | `test_hint_extractor_baker.py` | +240 (new) | 26 tests across 4 categories. |

**Total new test assertions: 47** (21 + 26) across 2 new files.

---

## Fix 1 — C-2 npc_upsert tuple unpacking

**Pre-S65.1.** `npc_upsert` returns `tuple[int, bool] | None` (the `bool` is `was_new`). Five test files treated the return as raw int, causing `sqlite3.ProgrammingError: type 'tuple' is not supported` at collection time when the tuple was bound as a SQL parameter.

**Patch shape.** Uniform `var, _ = npc_upsert(...) or (None, False)` per call site. Single-line transformation handles both success (returns tuple) and refusal (returns None) paths.

**Files + sites.**
- `test_dnd_npcs.py`: 10 sites (gid, gid2, gid3, mid, sid, pid, gid_other, loc_npc1-3, oid)
- `test_dnd_locations.py`: 1 site (npc_id)
- `test_dnd_consequences.py`: 5 sites (reginald_id, lira_id, thorne_id, kael_id, other_npc)
- `test_consequence_command.py`: 3 sites (reginald, lira, thorne)
- `test_directive_emit.py`: 1 site (npc_id)

**Empirical verification.** Pre-patch: 5 collection errors. Post-patch: 463 assertions green.

**Rollback procedure.** Revert each test file's `var, _ = ... or (None, False)` patterns back to `var = npc_upsert(...)`. Tests will re-error on tuple binding. No rollback risk to production code.

---

## Fix 2 — C-1 F-008 AUTO_EXECUTE Close

Operator-authorized steps 1, 2, 5, 6 from `S65_F008_audit_findings.md` §"Recommended S65.1 close shape." Steps 3 (MODE replacement) and 4 (CLOCK_TICK replacement) NOT in scope — accepted UX regression: operator types `/mode`/`/clock tick` manually until §1b replacements ship.

### Phase A (Step 1) — Test-harness migration

**New function `quest_add_with_dedup` in `dnd_engine.py`:**
```python
def quest_add_with_dedup(campaign_id: int, title: str) -> tuple[int, bool] | None:
    """Returns (quest_id, True) on insert, None on dedup against active quests.
    Manual /quest add (raw quest_add) remains unrestricted."""
```

Dedup logic moved verbatim from `execute_auto_actions` QUEST_ADD branch: case-insensitive, whitespace-collapsed title comparison against `get_active_quests` result.

**Test sites migrated (test_dnd_npcs.py:432–494).** All 7 prior call sites converted from `execute_auto_actions(QD_CAMP, [{'cmd': 'QUEST_ADD', 'args': ['title']}])` to `quest_add_with_dedup(QD_CAMP, 'title')`. Behavior contract preserved (identical-title, case-insensitive, whitespace-normalized, completed-quest-unblocks, cross-campaign isolation).

**`/quest add` slash command unchanged** — still uses raw `quest_add` per "manual remains unrestricted" rule.

### Phase B (Step 2) — Prompt-section surgery

**Removed from `build_dm_context` (dnd_engine.py:6474–6497):** the full `=== AUTO-EXECUTE (TIER 1 STRUCTURAL CHANGES) ===` block (24 lines). LLM no longer instructed to emit `AUTO_EXECUTE_BEGIN`…`AUTO_EXECUTE_END` tails.

**Rewrote `=== PLAYER UI SUGGESTIONS ===` framing:**
- Removed cross-reference to "AUTO-EXECUTE tail above"
- Removed "Tier 1 / belong in the AUTO-EXECUTE tail" sentence
- Replaced with: "DO NOT include /quest, /clock tick, or /mode in this block. Those are state writes the DM types directly when the narrative warrants — they are not LLM-emit surfaces."

### Phase C (Step 5) — Feature flag

**`AUTO_EXECUTE_ENABLED = False`** constant in `dnd_engine.py`:
- Documented at module top alongside `USE_KNOWLEDGE_GUIDANCE`.
- `execute_auto_actions` early-returns `[]` when False, logging `auto_execute_disabled campaign_id=N would_have_executed=K actions` for observability.
- `parse_auto_execute` STILL strips any stale LLM-emitted tail (defense-in-depth — if the LLM spontaneously emits, the display is still clean).
- Rollback = flip flag to True. Note: also requires restoring the AUTO-EXECUTE prompt section if the LLM is to be re-instructed to emit tails.

### Phase D (Step 6) — Adversarial verify

**`test_auto_execute_closed.py`** — 21 tests across 7 categories:
1. Feature flag is False (the close shipped).
2. `parse_auto_execute` still strips a tail (display cleanup preserved).
3. Parsed actions still returned (parser operational; no state mutation at parse time anyway).
4. `execute_auto_actions` returns [] when disabled — NO state write (verified: no new quest row, mode unchanged, clock unchanged).
5. `quest_add_with_dedup` works normally for the test-harness path.
6. Raw `quest_add` slash path continues unrestricted (allows duplicate titles).
7. Empty actions + no-tail responses handled silently.

**Adversarial scenario (per S65 plan):** `AUTO_EXECUTE_BEGIN QUEST_ADD|fake_quest CLOCK_TICK|Detection|2 MODE|combat AUTO_EXECUTE_END` injected as LLM narration; asserted no quest row, no clock tick, no mode change. ✓

**Doctrinal status:** §1b third-instance anchor (Quest Layer v0.1) transitions **PROVISIONAL → ANCHORED** as of S65.1 ship.

**Rollback procedure.**
1. Flip `AUTO_EXECUTE_ENABLED = True` in `dnd_engine.py`.
2. Restore the `=== AUTO-EXECUTE (TIER 1 STRUCTURAL CHANGES) ===` prompt section (24 lines, see git diff for verbatim text).
3. Revert PLAYER UI SUGGESTIONS framing rewrite.
4. Revert test_dnd_npcs.py S7 section back to `execute_auto_actions` calls (or keep migrated tests — `quest_add_with_dedup` works either way).
5. Restart `virgil-discord`.
Behavior reverts: LLM re-instructed to emit AUTO_EXECUTE tails; parser parses; executor mutates state.

---

## Fix 3 — N-1 Hint Extractor Tightening

**Pre-S65.1 failure shape (from 2026-05-14T09:47-09:49 baker playtest):**
- 9:47 "pay for 5 loaves" (actual purchase) → no hint (LLM didn't extract)
- 9:48 "how much?" (question) → `!game coin -5sp` (false fire)
- 9:49 "50c each before" (dispute) → `!game coin -1sp` (false fire)
- 9:49 "yeah but I wanted 5" (continuation) → `!game coin -5sp` (duplicate)

**Patch shape (4 stages):**

### Stage 1 — Tightened SYSTEM_PROMPT
Added 3 negative examples to `mechanical_hints.py:SYSTEM_PROMPT`:
- **Quote-only narration** ("Five silver pieces for the five loaves") → `[]`
- **Dispute narration** ("I'm still charging a silver a loaf") → `[]`
- **Request-payment narration** ("Hand them over and they're yours") → `[]`

Plus explicit rules: "Bare price quotes are NOT transactions" / "Questions about price are NOT transactions" / "Disputes about price are NOT transactions."

### Stage 2 — Transaction-verb gate
Closed-vocabulary frozenset `_COIN_TRANSACTION_VERBS` (~30 forms). Whole-word case-insensitive match. Pure dialogue narrations with no transaction verb → hints dropped with reason `no_transaction_verb`.

**Noun-overlap traps excluded:** `'hands'` (body part), `'places'` (locations). These were the highest-frequency false positives in fantasy narration.

**Verbs kept include both bare and -ed/-ing forms:** paid/pays/paying, handed/handing, gave/gives/giving, slid/slides/sliding, dropped/drops/dropping, pocketed/pockets/pocketing, accepted/accepts/accepting, etc.

### Stage 3 — Cross-turn dedup
Process-local LRU `_RECENT_HINTS_PER_CAMPAIGN: dict[int, deque]`. Bounded to 12 entries per campaign (~3–4 turns of hints). New parameter `campaign_id` on `parse_mechanical_hints`. Identical hints emitted in the last ~12 entries for the same campaign are suppressed with reason `recent_duplicate`. Cross-campaign isolation preserved.

### Stage 4 — Telemetry
- `hint_extractor_emitted campaign_id=N hint='!game coin -5sp' transaction_verb_present=True/False` — per fire
- `hint_extractor_suppressed campaign_id=N hint='!game coin -5sp' reason={no_transaction_verb|recent_duplicate}` — per suppression
- Existing `hint_parse:` summary line retained at function exit.

**Caller change.** `discord_dnd_bot.py:_attach_hints` and `_dm_respond_and_post` thread `campaign["id"]` to `parse_mechanical_hints`. Without `campaign_id`, dedup is disabled but the verb-gate still fires.

**Tests (`test_hint_extractor_baker.py`).** 26 tests across 4 categories:
1. `_narration_has_transaction_verb` — closed-vocab surface check, 8 cases.
2. Cross-turn dedup — bounded LRU, cross-campaign isolation, FIFO eviction.
3. `parse_mechanical_hints` integration — verb gate + dedup interaction with stubbed LLM router.
4. Baker scenario adversarial — 3 dispute/quote/request turns from live playtest, all assert verb-gate fires False (hints suppressed).

**Acceptable coarse-grained limits documented in tests:**
- Body-language verbs ("slides a loaf", "pockets handkerchief") that ALSO appear in transaction prose cannot be distinguished by surface check alone. Acceptable: prompt-side dispute examples drive the LLM to emit `[]` for those narrations; verb-gate is defense-in-depth.
- "Hands" as noun (body part) is excluded from the vocab; loss is "the merchant hands you the coin" wouldn't fire from "hands" alone — but "gives", "passes", "slides", "drops", "tosses" all cover that case.

**Rollback procedure.**
1. Revert `mechanical_hints.py`:
   - Restore original SYSTEM_PROMPT (remove dispute/quote/request examples).
   - Remove `_COIN_TRANSACTION_VERBS`, `_narration_has_transaction_verb`, `_RECENT_HINTS_PER_CAMPAIGN`, `_get_recent_hints`, `_record_recent_hints`.
   - Revert `parse_mechanical_hints` signature to single-arg.
   - Remove verb-gate and dedup stages (back to single-pass validation).
2. Revert `discord_dnd_bot.py:_attach_hints` to single-arg `(message, embed, narration)` and call site at 3580 to pass only 3 args.
3. Restart `virgil-discord`.
Behavior reverts: hint extractor fires on any LLM-extracted candidate that passes schema validation, regardless of transaction context.

---

## Test Counts (S65.1 contribution)

| Test File | New | Migrated | Status |
|---|---|---|---|
| `test_dnd_npcs.py` | — | S7 section (8→7 sites + 1 new assertion) | 163/163 pass |
| `test_dnd_locations.py` | — | tuple unpack | 109/109 pass |
| `test_dnd_consequences.py` | — | tuple unpack | 142/142 pass |
| `test_consequence_command.py` | — | tuple unpack | 26/26 pass |
| `test_directive_emit.py` | — | tuple unpack | 23/23 pass |
| `test_auto_execute_closed.py` | 21 | — | 21/21 pass |
| `test_hint_extractor_baker.py` | 26 | — | 26/26 pass |

**Plus S65 inheritance (unchanged):** test_play_smoke (6), test_dc_less_roll_closure (25), test_dm_aside_role_closure (13), test_format_unification_closure (23), test_attack_directive (50), test_advisory (31).

**Total assertion count (S65 + S65.1):** 658 across 13 test files.

---

## C-2 prior-failing-tests now green confirmation

| File | Pre-S65.1 | Post-S65.1 |
|---|---|---|
| test_dnd_npcs.py | sqlite3.ProgrammingError @ collection | 163/163 pass |
| test_dnd_locations.py | sqlite3.ProgrammingError @ collection | 109/109 pass |
| test_dnd_consequences.py | sqlite3.ProgrammingError @ collection | 142/142 pass |
| test_consequence_command.py | sqlite3.ProgrammingError @ collection | 26/26 pass |
| test_directive_emit.py | sqlite3.ProgrammingError @ collection | 23/23 pass |

C-2 confirmed CLOSED.

---

## §1b 3rd-instance Anchor Transition

| State | Pre-S65 | Post-S65 | Post-S65.1 |
|---|---|---|---|
| Quest Layer v0.1 (§1b 3rd-instance) | TENTATIVE | PROVISIONAL (HALT on F-008 close) | **ANCHORED** ✓ |
| F-008 status | OPEN (P0 in long-horizon) | OPEN (audit phase complete, close deferred) | **CLOSED** ✓ |
| §76 four-property test on AUTO_EXECUTE QUEST_ADD | 4/4 (failing — LLM-writable surface) | 4/4 | **Removed surface** (LLM no longer instructed to emit; executor gated to no-op) |

---

## Standing-Practice Adoption Confirmation

1. ✅ **Pre-ship DB snapshot:** `cp virgil.db archive/virgil_S65_1_preship.db` at 2026-05-14T10:23 PDT. 20.7 MB. Rollback reference.
2. ✅ **Rollback procedure documented per fix:** see Fix 1/2/3 sections above.
3. ✅ **Sequential commits w/ test verify before next fix:** Fix 1 → tests green (462 prior failures closed) → Fix 2A test migration → Fix 2B prompt surgery → Fix 2C feature flag → Fix 2D adversarial verify (21 green) → Fix 3 → tests green (26 new + 658 total) → full regression sweep → bot restart → boot clean.
4. ✅ **Feature-disable switches:** `AUTO_EXECUTE_ENABLED = False` is a true binary flag; flip to True restores prior behavior (with prompt restoration also required). N-1 hint-extractor changes are NOT behind a flag — they're a tightening of an existing surface; rollback = revert the code edit.

---

## N-2 Filed to Long-Horizon Backlog (No Spec Work)

**N-2 NPC commitment-tracking layer** — out of S65.1 scope per operator authorization. Filed as multi-spec candidate alongside F-077 filled-clock auto-trigger and the larger NPC-memory thread. See `S65_1_candidates.md` §N-2 for the failure shape (Issues 1/3/4 from baker playtest: free→half-price retcon, hallucinated history confirmation, inconsistent totals across dispute turns).

**Next-step decision deferred** — should NOT be bundled into S66 without dedicated spec design. Multi-system surface (schema + extraction + retrieval + arbitration).

---

## Pre-existing Failures Status

All pre-existing tuple-binding failures CLOSED by Fix 1. No new pre-existing failures surfaced during S65.1.

---

## HALT Escalations

**None.** All three fixes shipped within scope. F-008 closed per operator authorization (steps 1/2/5/6 only — MODE/CLOCK_TICK replacements deferred per operator decision).

---

## Restart + Discord Verify

Bot restarted at 2026-05-14T10:39 PDT. Status `active`. Boot log clean (srd_resolver loaded, fk_cascade_init OK, chroma_init OK, Discord DnD bot starting).

**Operator-paste-verbatim test scenarios per S65.1 plan:**

1. **Quest add via slash.**
   ```
   /quest add title:"Test S65.1 Quest"
   ```
   Expected: quest row created with status='in-progress', no AUTO_EXECUTE log line. Re-run with same title: second row also created (manual is unrestricted).

2. **AUTO_EXECUTE-dead path.**
   Engineer a scenario likely to produce LLM AUTO_EXECUTE_BEGIN emission (combat-start narrative, "the bandits attack" → mode flip would have fired pre-close). Expected: no quest row written, no mode change, journal shows zero `auto_execute_attempted` lines (the parser still strips but executor is no-op).

3. **MODE manual flip post-close.**
   Trigger combat narration: "the bandits draw blades, the air thrums with violence." Expected: mode remains 'exploration' (no auto-flip). Operator runs `/mode combat`; mode flips correctly.

4. **N-1 baker scenario.**
   Travel to a market location and run the verbatim sequence:
   ```
   /play
   I try to persuade the baker for a free loaf.
   pay for 5 loaves
   how much?
   they were 50c each before have prices gone up or are you mistaken
   yeah but I wanted 5
   ```
   Expected: hint fires exactly once on the actual purchase narration (the LLM produces a transaction-completion verb), zero hints on subsequent dispute/quote/question turns. Journal shows `hint_extractor_suppressed` lines for the dispute turns with reason `no_transaction_verb`.

5. **Persuasion check format (S65.A regression check).**
   ```
   /play
   I try to persuade the merchant for a discount
   ```
   Expected: render shows `<Actor>:` (bold, outside box) + `!check persuasion <DC>` (in backticked box). No `**!check**` legacy wrap.

**Journal greps for operator verify:**
```bash
journalctl --user -u virgil-discord | grep "auto_execute_attempted"     # should be zero post-restart
journalctl --user -u virgil-discord | grep "auto_execute_disabled"      # should fire if LLM spontaneously emitted a tail
journalctl --user -u virgil-discord | grep "hint_extractor_emitted"     # should fire on real transactions only
journalctl --user -u virgil-discord | grep "hint_extractor_suppressed"  # should fire on dispute/quote turns
journalctl --user -u virgil-discord | grep "quest_add_with_dedup"       # should fire if test harness path runs
```

---

## End-of-Session State

- 3 fixes shipped (C-2, C-1, N-1). All tests green.
- 0 HALT escalations.
- §1b 3rd-instance anchor ANCHORED (Quest Layer v0.1 on clean substrate).
- F-008 CLOSED (the largest open P0 from long-horizon review's Tier 1 list).
- Pre-ship snapshot in archive.
- Standing-practice adoption: confirmed.
- N-2 (NPC commitment-tracking) filed to backlog for separate multi-spec arc.
