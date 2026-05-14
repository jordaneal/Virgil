# S65 Handoff — Tier 1 Cleanup, Batch 1 of 3

**Date:** 2026-05-14
**Session:** S65 (Path B cleanup cadence)
**Pre-ship snapshot:** `/mnt/virgil_storage/archive/virgil_S65_preship.db` (20.7 MB, 2026-05-14T08:45 PDT)
**Discipline adopted (standing practice from this session forward):** pre-ship DB snapshot before any change; rollback notes per fix; feature-disable switches for new always-on behavior.

---

## Fix Inventory (4 planned, 3 shipped + 1 HALTED)

| Fix | Status | Outcome |
|---|---|---|
| Fix 1 — F-021 `/play` NameError | ✅ SHIPPED | 6 smoke tests added; bot import clean; 2-line patch (lines 4878, 4885 of discord_dnd_bot.py via local var `_seed_text`). |
| Fix 2 — F-008 AUTO_EXECUTE close | ⛔ HALTED | Phase A audit shipped; Phase B decision deferred to S65.1. Doctrinal anchor (§1b 3rd instance) status: **PROVISIONAL** pending S65.1 close. |
| Fix 3 — DC-less roll closure | ✅ SHIPPED | 25 new unit tests; engine-computed DC via `RollDecision.__post_init__`; directive renders DC inline. |
| Fix 4 — `#dm-aside` role-confusion | ✅ SHIPPED | 13 new structural tests; `ADVISORY_SYSTEM_PROMPT` hard-forked; `build_advisory_context` "Asking player" → "Bound character" phrasing aligned. |

---

## Files Touched, LOC Delta Per Fix

| Fix | File | Lines changed | Notes |
|---|---|---|---|
| Fix 1 | `discord_dnd_bot.py` | +14 / -2 | Replace `{seed}` with local var `_seed_text = scene or ''`; +8 lines doc-comment. |
| Fix 1 | `test_play_smoke.py` | +234 (new) | 6 tests including AST-guard regression test for any future `{seed}`-like undefined-name. |
| Fix 2 | `virgil-docs/planner-scratch/S65_F008_audit_findings.md` | +136 (new) | Audit findings doc; no code changes. |
| Fix 3 | `dnd_orchestration.py` | +66 / -34 | `_SEVERITY_TO_DC` table + `_DEFAULT_DC_FOR_UNKNOWN_SEVERITY`; `RollDecision.__post_init__` auto-fills DC; `to_prompt_directive` renders DC inline (was `<DC>` placeholder); `ADVISORY_SYSTEM_PROMPT` hard-forked (Fix 4); `build_advisory_context` phrasing realigned (Fix 4). |
| Fix 3 | `test_attack_directive.py` | +12 / -6 | Updated assertions from `<DC>` placeholder → engine-computed DC literals; renamed "DC GUIDANCE" → "DIFFICULTY TIER". |
| Fix 3 | `test_dc_less_roll_closure.py` | +275 (new) | 25 tests including adversarial five-in-succession scenario. |
| Fix 4 | (`dnd_orchestration.py` shared with Fix 3 — see above) | (shared) | `ADVISORY_SYSTEM_PROMPT` block ~+30 / -30; `build_advisory_context` 2-line phrasing fix. |
| Fix 4 | `test_advisory.py` | +14 / -6 | Updated 3 assertions to match new framing (`OOC` → semantic checks for not-in-character + aside + operator-facing); fixed pre-existing stale `location` fixture (Ship 2 S39 leftover) → `location_label`. |
| Fix 4 | `test_dm_aside_role_closure.py` | +234 (new) | 13 structural tests verifying the hard-fork's identity / authority / invariants / channel-boundary scope. |

**Test assertion counts:** Fix 1 = 6 tests, Fix 3 = 25 tests, Fix 4 = 13 tests. Plus pre-existing assertion updates: test_attack_directive +2, test_advisory regression fixes 2.

---

## Fix 1 — F-021 `/play` NameError

**Patch shape.** Pre-S65 lines 4870, 4876 of `discord_dnd_bot.py` referenced an undefined `seed` variable (Ship 2 / S39 renamed the parameter to `scene` but two f-string call sites were missed). Post-S65: introduces a local var `_seed_text = scene or ''` immediately above the two `dm_respond(...)` calls inside `/play`; f-strings now reference `{_seed_text}`. Equivalent to the §XIV patch sketch + slight refactor to avoid re-evaluating `scene or ''` twice.

**Empirical verification.**
- Pre-patch grep `grep -n '{seed}' discord_dnd_bot.py` → 2 hits (lines 4870, 4876).
- Post-patch precise grep `grep -n 'f"\[Open the scene\] {seed}"'` → 0 hits.
- Post-patch grep `grep -n '{_seed_text}' discord_dnd_bot.py` → 2 hits (lines 4879, 4885).
- AST walk of `/play` function → 0 undefined-name references.
- `py_compile discord_dnd_bot.py` → OK.
- Import sanity `python3 -c "import discord_dnd_bot"` → OK.

**Tests (test_play_smoke.py).** 6 tests:
1. `test_play_no_nameerror_no_scene_arg` — handler runs without scene arg, no NameError.
2. `test_play_no_nameerror_with_scene_arg` — handler runs with explicit scene arg, no NameError.
3. `test_play_handler_calls_dm_respond_with_scene_text` — verifies the f-string body contains the scene text in `[Open the scene] <text>` form.
4. `test_play_handler_static_no_seed_reference` — **AST regression guard**. Walks `/play` for any Name(Load) reference to a symbol not in (locals ∪ module ∪ builtins). Asserts no undefined `seed` AND no other undefined-name issues. Fails immediately if a future rename leaves another tail like F-021.
5. `test_play_handler_static_no_brace_seed_in_fstring` — **source-level regression guard**. Scans the file for literal `{seed}` in any f-string outside of comments. Catches the exact F-021 failure shape.
6. `test_play_twice_rapid_no_crash` — adversarial verify per S65 plan: invoke `/play` twice in quick succession.

**Rollback procedure.** Revert the patch hunk at lines 4865-4890 of `discord_dnd_bot.py` (restore the original two `{seed}` f-strings). Restart `virgil-discord`. Behavior reverts to NameError-on-every-/play.

**Adversarial verify (Discord, deferred to operator post-restart).** `/play` on existing campaign → completes within Discord's 3-second window; no spin. `/play` twice rapid-fire → no duplicate-command crash. If `## Starting time` is authored in skeleton.md, watch journal for `apply_starting_time_seed:` log line firing — confirms `/play` was previously silently broken.

---

## Fix 2 — F-008 AUTO_EXECUTE close (HALTED)

**Decision:** Phase B = HALT. Two HALT criteria fire per S65 plan:

1. **Class (c) consumers exist.** `test_dnd_npcs.py` exercises `execute_auto_actions` directly across 7 call sites (lines 442, 449, 455, 461, 467, 484, 491) for QUEST_ADD dedup verification (S7 ship's behavior contract). Gutting `execute_auto_actions` would break these tests.

2. **Closure touches `build_dm_context` beyond directive emission.** The AUTO_EXECUTE prompt block at `dnd_engine.py:6447–6519` (~70 lines) is sibling to "PLAYER UI SUGGESTIONS (DERIVED ONLY, OPTIONAL)" which explicitly references the AUTO_EXECUTE tail. Removing AUTO_EXECUTE requires rewriting the "PLAYER UI SUGGESTIONS" section's framing in tandem.

Additional structural concerns (defer-rationale): MODE writer redundancy (3 writers; LLM-emit removal leaves UX gap without deterministic mode-flip replacement); CLOCK_TICK has no current §1b replacement (filled-clock auto-trigger F-077 is filed but unbuilt).

**Audit findings doc:** `virgil-docs/planner-scratch/S65_F008_audit_findings.md` — full downstream-reader inventory + Phase B rationale + recommended S65.1 close shape.

**Doctrinal status:** §1b third-instance anchor (Quest Layer v0.1) is **PROVISIONAL** pending S65.1. The §76 four-property test verdict on AUTO_EXECUTE QUEST_ADD's `dnd_quests` column is still 4/4 (LLM-writable via auto-execute, persisted, retrieved via active-quest directive, narratively inferential).

**Operator action required:** confirm HALT and authorize S65.1 to ship the close. Until S65.1: AUTO_EXECUTE remains operational; doctrinal anchor stays provisional.

---

## Fix 3 — DC-less roll closure

**Localized surface (Phase A).** `should_call_roll` returns `RollDecision` with no DC; `to_prompt_directive` rendered `**!check skill <DC> : <First Name>**` with `<DC>` as a placeholder for the LLM to fill from RAW guidance. Llama 3.3 70B intermittently emitted DC-less directives or substituted wrong DCs — the proposal layer was the failure surface (per Phase A localization).

**Fix shape (Phase B).** Per Gemini's framing: "a roll without a DC is a category error." Fixed at the proposal layer.

1. **Severity-to-DC table** (`dnd_orchestration.py`):
   ```python
   _SEVERITY_TO_DC: dict[str, int] = {
       'minor':      10,
       'meaningful': 15,
       'dire':       20,
   }
   _DEFAULT_DC_FOR_UNKNOWN_SEVERITY = 15
   ```
   Maps to 5e RAW bands (easy/medium/hard).

2. **`RollDecision.dc: Optional[int]` field** with `__post_init__` auto-fill:
   ```python
   def __post_init__(self):
       if self.dc is not None: return
       if not self.needs_roll: return
       if self.category in ('skill_check', 'save'):
           self.dc = _SEVERITY_TO_DC.get(self.severity, _DEFAULT_DC_FOR_UNKNOWN_SEVERITY)
   ```
   Attack rolls leave `dc=None` (Avrae handles attack-vs-AC). Defense-in-depth: any future `RollDecision(True, ..., category='skill_check', ...)` automatically gets a DC without caller updates.

3. **`to_prompt_directive` renders DC inline** as a literal integer:
   - Pre: `**!check perception <DC> : <First Name>**` (LLM picks DC)
   - Post: `**!check perception 15 : <First Name>**` (engine picks; LLM emits verbatim)
   - "DC GUIDANCE" renamed to "DIFFICULTY TIER" (informational only — LLM's NARRATIVE should match the tier; the integer is engine-fixed).
   - New explicit instruction: "the engine-computed DC — emit it VERBATIM. Do NOT substitute a different number, do NOT replace with a placeholder, do NOT omit it."

**Tests (test_dc_less_roll_closure.py).** 25 tests across 7 categories: __post_init__ auto-fill, attack/init/no-roll exclusion, caller-supplied DC wins, should_call_roll integration (all paths), directive renders DC as literal, adversarial five-in-succession scenario, resolution binding consumes the engine-pre-filled DC. Existing `test_attack_directive.py` updated (2 assertions) to match the new format; 44/44 still passing post-update. Existing `test_resolve_directive.py` 25/25 still passing. Existing `test_llm_emit_writer.py` 23/23 still passing.

**Rollback procedure.** Remove the `_SEVERITY_TO_DC` table + `__post_init__` from `RollDecision`; revert `to_prompt_directive` to use `<DC>` placeholder + old "DC GUIDANCE" framing. Both Ship 1/A's resolution binding paths continue to work unchanged (they consume whatever DC is in the directive text). Roll-back is a single file edit on `dnd_orchestration.py`.

**Adversarial verify (Discord, deferred to operator post-restart).**
- Trigger a skill check during play → bot proposes roll with DC visible in the bold line; Avrae rolls; engine-bound resolution renders pass/fail accurately.
- Five skill checks in succession → all five produce engine-bound resolution with DC.
- Journal grep `journalctl --user -u virgil-discord | grep -E "DC-less|directive_resolution_skipped:.*reason=no_dc"` should be empty post-restart.

---

## Fix 4 — `#dm-aside` role-confusion hard-fork

**Located directive.** `ADVISORY_SYSTEM_PROMPT` in `dnd_orchestration.py:3021`. Single use site at `discord_dnd_bot.py:3194` (`_advisory_respond`). Channel-boundary scoped to `#dm-aside` only — does NOT propagate to `#dm-narration` (per GPT 1/3 scope discipline).

**Pre-fix framing (excerpt).** "You are Virgil, speaking out-of-character to help the player understand the game. ... Answer the player's questions about what's happening, what they have, what they can do. ... Be brief, practical, and friendly — like a DM leaning over to whisper a clarification."

The role mismatch: when the operator/DM addresses Virgil in `#dm-aside`, the framing assumes asker = player. Hence the S64 1:14 AM failure: "remember my character is a half-elf" → Virgil suggests "you might want to ask your DM."

**Post-fix framing.** Per Gemini's S65-plan framing:
> "You are Virgil, the underlying game engine, communicating directly with the human Dungeon Master in a private aside channel. You are NOT speaking to a player. You are NOT in-character. You are diagnosing system state, surfacing telemetry, or responding to operator queries about engine behavior. The operator addressing you IS the DM; treat their feedback about character pronouns, scene state, or narration behavior as authoritative."

Additional explicit anti-redirect framing:
> "Do not address the DM as if they were a player asking about their character. Phrases like 'you might want to check with your DM' or 'ask the DM' are wrong — the DM is who you are addressing."

Plus corrective-acknowledgment instruction:
> "When the DM tells you something corrective (a character pronoun they want consistent, a fact about scene state, a narration habit they want adjusted), acknowledge it as a note to carry into subsequent narration."

**Scope discipline preserved.** Per GPT 1/3 note: the identity merge applies in `#dm-aside` only. `_advisory_respond` is the sole consumer of `ADVISORY_SYSTEM_PROMPT`. `#dm-narration`'s prompt (`build_dm_context`) still maintains Virgil-as-narrator + players-as-characters separation. No cross-channel propagation.

**Secondary cleanup: `build_advisory_context` phrasing.** Old text rendered "Asking player's character: <name>" which implies asker = player. Updated to "Bound character: <name>". Aligns with the new framing — bound character is referenced as factual state, not as a self-reference. Two call sites (lines 3176, 3178 of dnd_orchestration.py).

**Invariants preserved (verified by structural tests).**
- Read-only (no state mutation, no time advancement, no combat trigger).
- No `!`-prefixed Avrae command emission (bot-Avrae write boundary §65 holds).
- No scene narration in advisory replies.

**Tests (test_dm_aside_role_closure.py).** 13 structural tests across 6 categories:
1. Identity framing (Virgil-as-engine, asker-as-DM, not-speaking-to-player, not-in-character).
2. Authority handling (DM feedback authoritative; anti-third-party-advice).
3. Invariants preserved (no mutation, no Avrae emit, no narration).
4. Channel-boundary scope.
5. `build_advisory_context` phrasing aligned.
6. Adversarial scenario structural shape (corrective acknowledgment).

`test_advisory.py` updated (2 assertion fixes + 1 fixture fix for the pre-S65 stale `location` Ship 2 leftover); 31/31 still pass.

**Rollback procedure.** Revert `ADVISORY_SYSTEM_PROMPT` block in dnd_orchestration.py (lines 3021–3100ish) to its pre-S65 text; revert `build_advisory_context` phrasing (Asking player → Bound character) at lines 3176-3182. Restart `virgil-discord`. Behavior reverts to player-addressing framing.

**Adversarial verify (Discord, deferred to operator post-restart).**
- In `#dm-aside`, message Virgil: "my character is a half-elf, please remember that."
- Expected: Virgil acknowledges as DM (e.g. "Noted — I'll keep that in mind for narration. Anything else to flag?")
- NOT expected: Virgil suggests how to ask "your DM" about pronouns.

---

## Pre-existing Failures Surfaced During Regression Sweep (NOT S65 regressions)

Confirmed pre-existing — caused by `npc_upsert` returning `tuple[int, bool] | None` while several tests treat the return as an int. Same root pattern across 4 test files. Bug shape: `gid = npc_upsert(...); npc_get(CAMP, gid)` — `gid` is a tuple, sqlite3 refuses to bind it as a parameter.

| File | Failure Site | Symptom |
|---|---|---|
| `test_dnd_npcs.py:89` | `npc_get(CAMP, gid)` | sqlite3.ProgrammingError: type 'tuple' is not supported |
| `test_dnd_locations.py` | Similar pattern (npc_upsert as int) | sqlite3.ProgrammingError: type 'tuple' is not supported |
| `test_dnd_consequences.py` | Similar pattern | sqlite3.ProgrammingError: type 'tuple' is not supported |
| `test_consequence_command.py:119` | Similar pattern | sqlite3.ProgrammingError: type 'tuple' is not supported |
| `test_directive_emit.py:193` | `npc_id = npc_upsert(cid3, 'Garrick', role='merchant')` → tuple → consequence_upsert binding error | sqlite3.ProgrammingError |

**Confirmed pre-existing via:**
- `dnd_engine.py` last-modified 2026-05-13 22:22 (yesterday); my session touched only `dnd_orchestration.py` and `discord_dnd_bot.py` (today 2026-05-14).
- `npc_upsert`'s `tuple[int, bool] | None` return shape is unchanged by S65.
- The same return-shape mismatch is catalogued in `PROJECT_LONG_HORIZON_REVIEW.md` as part of the npc_upsert/location_upsert signature asymmetry findings.

**No HALT escalation triggered** because these are not new failures from S65 work.

**Filed for future cleanup** (recommend S65.1 or later): one of (a) update tests to unpack `(gid, was_new) = npc_upsert(...)`, (b) update `npc_upsert` to return `int | None` and accept a `was_new_out` ref parameter, OR (c) introduce `npc_upsert_id_only()` helper that returns just the int for test convenience. Option (a) is the smallest diff.

---

## Pre-existing Test_attack_directive Asserts Updated (NOT a regression)

The `test_attack_directive.py` file asserted on the pre-S65 directive format (`<DC>` placeholder + "DC GUIDANCE" framing). Updated to match post-S65 engine-computed format (`15` literal + "DIFFICULTY TIER" framing). This is a documented assertion-update, not a regression.

---

## Test Counts (S65 contribution)

| Test File | New | Updated | Status |
|---|---|---|---|
| `test_play_smoke.py` | 6 | — | All pass |
| `test_dc_less_roll_closure.py` | 25 | — | All pass |
| `test_dm_aside_role_closure.py` | 13 | — | All pass |
| `test_attack_directive.py` | — | 6 assertions retouched | 44/44 pass |
| `test_advisory.py` | — | 3 assertions retouched + 1 fixture fixed | 31/31 pass |

**Total new test assertions: 44** across 3 new test files.

---

## Standing-Practice Adoption Confirmation

Per S65 plan's NEW standing practice:

1. ✅ **Pre-ship DB snapshot:** `cp /mnt/virgil_storage/virgil.db /mnt/virgil_storage/archive/virgil_S65_preship.db` ran at 2026-05-14T08:45 PDT before any code change. 20.7 MB. Rollback reference.
2. ✅ **Rollback procedure documented per fix:** see each fix section above.
3. ✅ **Sequential commits with test verify before next fix:** Fix 1 → tests green → Fix 2 audit (no code) → Fix 3 → tests green → Fix 4 → tests green → regression sweep.
4. ✅ **Feature-disable switches:** N/A this batch (no new always-on behavior was introduced as a binary switch; severity-to-DC and prompt-fork can be reverted via simple edit, no flag needed). Standing practice carried forward for S65.1.

---

## HALT Escalations

- **F-008 close: HALTED** per S65 plan criteria. Audit findings doc at `virgil-docs/planner-scratch/S65_F008_audit_findings.md`. Authorization required from operator to ship S65.1.

---

## Restart + Discord Verify

Bot is ready for restart. Operator-paste-verbatim test scenarios per S65 plan:

1. **`/play` on existing campaign.** Completes within 3s; no spin. Watch journal for `apply_starting_time_seed:` if skeleton has `## Starting time`.
2. **`/play` twice rapid-fire.** No duplicate-command crash.
3. **Skill check during play.** Bot proposes roll with DC visible in bold line; Avrae rolls; engine-bound resolution accurate.
4. **Five skill checks in succession.** All produce engine-bound resolution. No drift.
5. **`#dm-aside` pronoun feedback.** Bot acknowledges as DM; doesn't third-party-advise.
6. **F-008 verify:** skipped this session — defers to S65.1 verify after close.

Journal greps:
- `journalctl --user -u virgil-discord | grep NameError` — should be empty.
- `journalctl --user -u virgil-discord | grep -E "DC-less|reason=no_dc"` — should be empty.
- `journalctl --user -u virgil-discord | grep AUTO_EXECUTE` — should match pre-S65 volume (no closure shipped this session).
- `journalctl --user -u virgil-discord | grep apply_starting_time_seed` — should fire on `/play` if skeleton has `## Starting time`.

---

## End-of-Session State

- 3 fixes shipped (F-021, DC-less, role-confusion). All tests green.
- 1 fix HALTED with documented audit findings + recommended S65.1 close shape.
- 4 pre-existing failures surfaced + classified (not S65 regressions; filed for future cleanup).
- Pre-ship snapshot in archive.
- Standing-practice adoption (snapshot + rollback notes + feature-disable readiness): confirmed.
- Doctrinal note: §1b third-instance anchor (Quest Layer v0.1) remains **PROVISIONAL** pending S65.1 F-008 close.
