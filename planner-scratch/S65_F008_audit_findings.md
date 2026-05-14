# S65 — F-008 AUTO_EXECUTE Audit Findings

**Session:** S65 Tier 1 Cleanup, Batch 1
**Date:** 2026-05-14
**Status:** PHASE A COMPLETE → PHASE B = HALT (defer close to S65.1)

---

## Phase A — Downstream-Reader Inventory

### Emit site (1 site)
- `dnd_engine.py:6447–6519` (`build_dm_context` prompt body) — instructs the LLM
  to append `AUTO_EXECUTE_BEGIN`…`AUTO_EXECUTE_END` tail with `QUEST_ADD|<title>`,
  `CLOCK_TICK|<name>|<n>`, `MODE|<mode>` lines. The "AUTO-EXECUTE (TIER 1
  STRUCTURAL CHANGES)" section is a load-bearing prompt section, sibling to
  "PLAYER UI SUGGESTIONS (DERIVED ONLY, OPTIONAL)" which references it.

### Consumer sites (2 production + 7 test)
Classification per S65 plan: (a) LLM-emit path, (b) operator-facing slash,
(c) external script or test harness, (d) other.

| Site | File:Line | Class | Notes |
|---|---|---|---|
| `parse_auto_execute(response)` | `dnd_engine.py:6521` | (a) | Pure parser. Single production call site at line 7633 (`dm_respond`). |
| `execute_auto_actions(cid, actions)` | `dnd_engine.py:6585` | (a) | State-write executor. Single production call site at line 7636 (`dm_respond`). |
| `test_dnd_npcs.py:442` | test harness | **(c)** | Tests QUEST_ADD identical-title dedup. |
| `test_dnd_npcs.py:449` | test harness | **(c)** | Tests QUEST_ADD case-insensitive dedup. |
| `test_dnd_npcs.py:455` | test harness | **(c)** | Tests QUEST_ADD whitespace-normalized dedup. |
| `test_dnd_npcs.py:461` | test harness | **(c)** | Tests completed-quest unblocks new add. |
| `test_dnd_npcs.py:467` | test harness | **(c)** | Tests cross-campaign isolation. |
| `test_dnd_npcs.py:484` | test harness | **(c)** | Tests additional QUEST_ADD scenarios. |
| `test_dnd_npcs.py:491` | test harness | **(c)** | OTHER_QD_CAMP cross-campaign verify. |

**Count per class:**
- (a) LLM-emit path consumers: **2** (parse_auto_execute, execute_auto_actions)
- (b) operator-facing slash: **0**
- (c) test harness: **7** call sites in `test_dnd_npcs.py` (lines 442, 449, 455, 461, 467, 484, 491)
- (d) other: **0**

### Production logs that reference AUTO_EXECUTE
- `auto_execute_attempted` (line 7635)
- `auto_execute_success cmd={QUEST_ADD|CLOCK_TICK|MODE}` (lines 6618, 6635, 6648)
- `auto_execute_rejected reason={bad_format|invalid_mode|unknown_command|duplicate_quest|unknown_clock|clock_tick_error}` (lines 6553, 6559, 6565, 6571, 6576, 6611, 6626, 6630)
- `auto_execute_error cmd=...` (line 6652)
- `parse_auto_execute error` (line 6579)

### Doc + spec references (informational, no code dependency)
- `ROADMAP.md:198,199,373` — S6/S7 ship notes (MODE undo line, QUEST_ADD dedup).
- `PROJECT_LONG_HORIZON_REVIEW.md` F-008, F-022, F-023, F-025, F-081, F-082, F-086 — all reference AUTO_EXECUTE; some prescribe its closure.

---

## Phase B — Ship-or-HALT Decision: **HALT**

### Why HALT (per S65 plan criteria)

The S65 plan's HALT criteria:
> HALT immediately if any consumer is class (b), (c), or (d), OR if the close
> requires touching `adjudicator.py`, `build_dm_context` beyond directive
> emission, or any subsystem outside the Quest module.

**Two HALT criteria fire:**

1. **Class (c) consumers exist.** `test_dnd_npcs.py` exercises
   `execute_auto_actions` directly across 7 call sites for QUEST_ADD dedup
   verification (the S7 ship's behavior contract). Gutting `execute_auto_actions`
   would break these tests, requiring test-rewrite work that exceeds Quest-module
   scope.

2. **Closure touches `build_dm_context` beyond directive emission.** The AUTO_EXECUTE
   prompt block at `dnd_engine.py:6447–6519` is ~70 lines of prompt body, sibling
   to "PLAYER UI SUGGESTIONS (DERIVED ONLY, OPTIONAL)" which explicitly references
   the AUTO_EXECUTE tail ("/quest, /clock tick, or /mode … are Tier 1 and belong
   in the AUTO-EXECUTE tail"). Removing AUTO_EXECUTE requires rewriting the
   "PLAYER UI SUGGESTIONS" section's framing in tandem — both touch `build_dm_context`
   beyond a single directive's emission point.

### Additional structural concerns (defer-rationale)

3. **MODE writer redundancy.** `dnd_scene_state.mode` currently has three writers:
   (i) Avrae `!init` listener (`_handle_init_event` → `set_scene_mode`), (ii)
   `/mode` slash command, (iii) AUTO_EXECUTE MODE branch. Removing (iii) is the
   §17 cleanup but leaves a UX gap: today the LLM auto-flips mode on narrative
   transitions ("the bandits draw their blades, combat begins"). Without that
   path, mode flips depend entirely on Avrae `!init begin` (mechanical) or DM
   `/mode` (manual). A replacement deterministic mode-flip-on-COMBAT-intent
   surface is already filed (per F-008 spec note + PROJECT_LONG_HORIZON_REVIEW
   §F-008's recommendation: "MODE writer collision … deterministic Python layer
   validates the output before anything mechanically binds"). Closing AUTO_EXECUTE
   MODE without that replacement degrades UX even though it closes the §76 surface.

4. **QUEST_ADD has §1b suggester replacement** (per QUEST_LAYER_V0_SPEC `compute_quest_offer_suggester`),
   so the QUEST_ADD path is genuinely deprecate-ready — but the close still
   touches the test-harness contract.

5. **CLOCK_TICK has no current §1b replacement.** A "filled-clock auto-trigger" /
   "intent-driven clock-tick" surface is filed (F-077 in PROJECT_LONG_HORIZON_REVIEW
   §F-077) but unbuilt. Removing AUTO_EXECUTE CLOCK_TICK leaves clock advancement
   to the DM via `/clock tick` only — defensible, but a UX regression worth
   sequencing with a §1b replacement.

### Recommended S65.1 close shape

A clean F-008 close requires the following work, scoped beyond S65's batch-1
discipline:

1. **Test-harness migration.** Convert `test_dnd_npcs.py:442–491` from
   `execute_auto_actions` direct calls to `quest_add` direct calls. Dedup
   behavior moves into `quest_add` (or a new `quest_add_with_dedup` variant
   that QUEST_LAYER_V0's slash command also wraps).

2. **Prompt-section surgery.** Remove the "AUTO-EXECUTE" section from
   `build_dm_context`. Rewrite "PLAYER UI SUGGESTIONS" framing to drop
   AUTO_EXECUTE references. Re-test combat narration purity (S44 §77 invariants
   may interact with the section boundaries).

3. **MODE-flip replacement** (optional pre-close gate): land a deterministic
   `compute_mode_flip_directive` §59 sibling that fires on intent transitions
   (combat-intent in non-combat mode → suggest `/mode combat` or auto-flip with
   gates). This is the F-077-shape clock fix applied to mode.

4. **CLOCK_TICK replacement** (optional pre-close gate): filled-clock
   auto-trigger per F-077, OR accept the UX regression (DM types `/clock tick`
   manually).

5. **Gut `parse_auto_execute` + `execute_auto_actions`** behind a feature flag:
   ```
   AUTO_EXECUTE_ENABLED = False  # S65.1+
   # When False, parse_auto_execute strips the tail (still cleans up if the LLM
   # emits one) but execute_auto_actions is a no-op. Rollback = flip flag to True.
   ```
   This preserves rollback path per S65's "feature-disable switches for new
   always-on behavior" discipline.

6. **Adversarial verify** (per S65 plan) on the closed path: emit a payload
   resembling `AUTO_EXECUTE_BEGIN QUEST_ADD|fake_quest AUTO_EXECUTE_END` from
   LLM narration in a test fixture; assert no quest row written, no clock tick
   fires, no mode change happens.

### Doctrinal status

Per S65 plan: "§1b third-instance anchor (Quest Layer v0.1) sits on a
contaminated substrate until F-008 closes. If HALT fires, the doctrinal anchor
is provisional pending S65.1 close."

**Status:** §1b third-instance anchor (Quest Layer v0.1) is **PROVISIONAL**
pending S65.1 F-008 close.

The §76 four-property test verdict on AUTO_EXECUTE QUEST_ADD's `dnd_quests`
column is still 4/4 (LLM-writable via auto-execute parse, persisted in dnd_quests,
retrieved via compute_active_quest_directive, narratively inferential — quest
titles re-prompt narration). This is exactly the failure mode §76 was created
to close; closure defers to S65.1.

### Operator action required

Decision: confirm HALT and authorize S65.1 to ship the test-harness migration
+ prompt-section surgery + (optional) MODE/CLOCK_TICK replacements.

Until S65.1 ships:
- AUTO_EXECUTE remains operational.
- The doctrinal anchor stays provisional.
- F-008 remains open in the long-horizon review's Tier 1 list.

No code changes from this audit. S65 continues with Fix 3 (DC-less roll) and
Fix 4 (#dm-aside role confusion) per the original batch.
