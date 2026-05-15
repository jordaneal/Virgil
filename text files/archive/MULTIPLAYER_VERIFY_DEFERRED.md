# Multiplayer-Required Live-Verify — Deferred from Ship 1 (S34)

**Status:** Single-use pickup doc. Created S34 alongside Ship 1 promotion. Archive to `_trash/` or move under a `_done/` folder once the deferred verify lands and the corresponding ROADMAP / SESSIONS entries are written.

**Purpose:** Capture the live-verify scenarios from `RESOLUTION_BINDING_SPEC.md` §13 that could NOT be walked solo during S34's Ship 1 verify pass, so a future Code session can pick them up when a real second-controller Discord account is available without re-doing recon or re-deriving step inputs.

**Not a spec edit.** `RESOLUTION_BINDING_SPEC.md` §13 stays as authored. This is a companion verify-pickup doc, single-use.

---

## §1. Context

**What landed in S34:** Ship 1 (Resolution Binding) — engine-bound DC-vs-roll resolution wired into the DM-typed-directive matcher path. Closes Finding L + F-45 regression + Bug 1 Phase 2. Code shipped per `RESOLUTION_BINDING_SPEC.md`, ~40 test assertions green, virgil-discord restarted on the new code.

**What got walked in S34 solo:** Scenarios A, B, C, D from §13. All use Donovan Ruby (the PC bound to Jordan's Discord account) and only require one Discord identity in the loop. Sock-puppet from Jordan's account is faithful to the spec scenarios because the matcher binds on Avrae embed actor name, not Discord user ID.

**What got deferred:** Scenario F (multi-actor mismatch). Possibly Scenario E (cast skip), depending on Avrae sheet contents — see §4 below.

**Why F is deferred:** §13.7 requires two distinct Discord user IDs to type inside the ActionBatcher window so the bot's response carries a 2-actor footer. Jordan typing pure narration about "both PCs" routes through his own player-input path (he's bound to Donovan in `dnd_characters`), so it batches as Donovan only — single-actor footer, no mismatch surface to test.

---

## §2. Campaign state snapshot (S34, 2026-05-11)

**Campaign 22** — `T&J` — guild `1498592771471314977` — status `active`.

Bound PCs (`dnd_characters` where `campaign_id=22 AND alive=1`):

| name | race | class | controller (Discord user id) |
|---|---|---|---|
| Donovan Ruby | Dwarf | Rogue (L1) | `691905804965773362` (Jordan) |
| Karrok The Devourer | Half-Orc | Barbarian (L1) | `249754567263256576` (Captin0bvious per S32 §3.10 evidence) |

**Re-recon before walking F:** PC state can drift (a new binding lands, a PC dies, the campaign archives). Before starting the walkthrough below, run:

```bash
sqlite3 /mnt/virgil_storage/virgil.db \
  "SELECT id, name, race, class, level, alive, controller FROM dnd_characters WHERE campaign_id=22 ORDER BY id;"
```

Expect: two alive rows matching the table above. If either Donovan or Karrok is missing / dead / has a different controller ID, halt and re-recon. If the campaign 22 itself has archived, identify the new active campaign and adjust the scenario to use whoever's currently bound.

**Avrae binding sanity check:** the live walk also depends on Avrae having `Donovan Ruby` and `Karrok The Devourer` bound to their respective Discord accounts in this guild (Avrae owns that mapping separately from Virgil's `dnd_characters.controller`). If Avrae's binding has drifted (`!bindchar` was re-run, character was deleted from D&D Beyond, etc.), the player typing `!check perception` will produce an Avrae embed with a different `actor` field and the matcher won't bind. Standard `!ra perception` or `!s` from each character should produce embeds named with the canonical PC name on the first line — verify before walking.

---

## §3. Scenario F — Multi-actor mismatch (rewritten for real bound PCs)

Spec source: `RESOLUTION_BINDING_SPEC.md` §13.7. Spec body says "Donovan and Hilda" as example phrasing inside the step text; Hilda isn't bound to campaign 22, so use Karrok in her slot. The structural shape of the scenario is unchanged; only the second-PC name differs.

### §3.1 Steps

| # | Who | Step | Input / action |
|---|-----|------|---|
| 1 | Both players | Sign in to their respective Discord accounts | Jordan on his account (Donovan), Captin0bvious on his (Karrok). Both must be present in the campaign 22 guild and in `#dm-narration`. |
| 2 | DM (Jordan) | Continue the current campaign | `/play` if not already in session. Ensure scene mode is `exploration` (not `combat` — combat-mode skips directive creation per BUG_1_SPEC.md §F.1). |
| 3 | Both players | Type their narration in the same batch window | Donovan player (Jordan): `Donovan sweeps the left side of the room, looking for anything out of place.` Karrok player (Captin): `Karrok checks the right side, scanning the walls.` Both should land within ~5–10 seconds of each other so ActionBatcher pools them. |
| 4 | Bot | Auto-response with multi-actor footer | Bot narrates both PCs' sweep beats. Footer should read `⚔ Donovan Ruby, Karrok The Devourer` (or similar; both names visible). |
| 5 | DM (Jordan) | Emit directive | `!check perception 12` |
| 6 | Karrok (Captin) | Roll (the wrong actor — directive bound to Donovan, who was first chronological in the batch) | `!check perception` |
| 7 | Verify | Wrong-actor aside fires; row stays alive; no resolution-binding narration fires for Karrok | (see greps below) |

### §3.2 Expected behavior

- Wrong-actor aside posts to `#dm-aside` with the locked wording from `_wrong_actor_aside()` (`discord_dnd_bot.py:331`) — text like *"Roll directive bound to Donovan Ruby — that roll is not consumed. Wait for Donovan Ruby to roll, or address Karrok The Devourer first."*
- The `dnd_pending_roll_directives` row for campaign 22 stays alive (not consumed; matcher per §9.2 only consumes on actor match).
- No `_dm_respond_and_post` auto-fire on the Karrok roll. No `directive_resolved:` log line for this event.
- Optional follow-up: Donovan rolls `!check perception` — at this point the directive should match, consume, resolve, and auto-fire narration normally (validates that the row truly stayed alive for the correct actor).

### §3.3 Greps to confirm

After step 6:

```bash
journalctl --user -u virgil-discord | grep "directive_actor_mismatch:" | tail -1
# Expect: campaign=22 expected_actor=Donovan Ruby actual_actor=Karrok The Devourer skill=perception

journalctl --user -u virgil-discord | grep "directive_would_fire_dm_respond:" | tail -1
# Expect: the LATEST line is from a PRIOR scenario walk, NOT a new one for Karrok's roll
# (because actor-mismatch path doesn't emit this log line — only match path does)

journalctl --user -u virgil-discord | grep "directive_resolved:" | tail -1
# Expect: also a PRIOR scenario walk; no new line for Karrok's mismatched roll
```

If a fresh `directive_would_fire_dm_respond:` or `directive_resolved:` line appears with `actor=Karrok` for this scenario's timestamp window, that's a structural regression — the mismatch path is incorrectly consuming the row. HALT.

After optional follow-up (Donovan rolls):

```bash
journalctl --user -u virgil-discord | grep "directive_resolved:" | tail -1
# Expect: actor=Donovan Ruby skill=perception check_kind=check dc=12 roll_total=<n> outcome=PASSED|FAILED

journalctl --user -u virgil-discord | grep "directive_actor_mismatch:" | tail -3
# Expect: the Karrok mismatch from step 6 is in the log, no fresh mismatch for Donovan
```

### §3.4 Failure modes to watch

- **No multi-actor footer in step 4.** ActionBatcher window may be too narrow to catch both messages, or one player's text triggered a separate response. Retry — both players type closer together, or check `batcher` window setting in `discord_dnd_bot.py`. If the footer never reads multi-actor even on retry, the batching itself may have regressed (separate investigation, file as HALT).
- **Bot auto-fires narration for Karrok's roll.** That would mean the matcher is consuming on actor-mismatch — direct violation of Phase 1 invariant. HALT, surface to planner; this is a regression in `_handle_dm_roll_arrival`, not a Ship 4.5 calibration data point.
- **The mismatch aside posts to `#dm-narration` instead of `#dm-aside`.** Regression in `_post_dm_aside` channel routing. File as bug.

---

## §4. Scenario E — Cast skip (conditional)

Spec source: `RESOLUTION_BINDING_SPEC.md` §13.6.

### §4.1 Why this is conditional

Scenario E requires the rolling player's Avrae sheet to actually have a cast-able spell or cantrip. Campaign 22's bound PCs are:

- **Donovan Ruby** — Dwarf Rogue L1. Vanilla rogues get no cantrips/spells at L1 (Arcane Trickster archetype unlocks at L3 and not until L3 specifically). Unlikely to have cast surface.
- **Karrok The Devourer** — Half-Orc Barbarian L1. Vanilla barbarians never get spells. No cast surface.

**Inspect Avrae sheets before deciding:** in `#dm-narration`, have each player run `!cantrips` / `!spellbook` to confirm. If either has a usable cantrip (e.g. from a racial feat, dragonmark, or homebrew sheet edit), E is runnable using that PC + spell.

If neither sheet has a cantrip:

- **Skip E for live-verify.** The cast-kind skip path is structurally covered by `test_resolve_directive.py::test_resolve_returns_none_for_cast_kind` (unit-level assertion that `resolve_directive` returns `None` for `kind='cast'`). The live-verify of this path is empirical confirmation of the `§10.3` log-line shape (`directive_resolution_skipped: reason=cast_kind`), not promotion-gating.
- **Defer E indefinitely.** When a future campaign or PC binding produces a cast-capable character, the walk takes 2 minutes and the log-line shape can be confirmed inline. Until then the unit test carries the load.

### §4.2 Steps (if a caster is bound)

| # | Step | Input |
|---|------|-------|
| 1 | DM emits cast directive | `!cast guidance` (substitute any cantrip the rolling player actually has) |
| 2 | Player casts | `!cast guidance` (same spell name; Avrae uses the bound sheet) |
| 3 | Verify skip path | (greps below) |

### §4.3 Greps

```bash
journalctl --user -u virgil-discord | grep "directive_resolution_skipped:" | grep "reason=cast_kind" | tail -1
# Expect: campaign=22 reason=cast_kind

journalctl --user -u virgil-discord | grep "directive_resolved:" | tail -1
# Expect: PRIOR resolved line, no new resolved line for the cast event
```

### §4.4 Expected behavior

No bot auto-narration on the cast event (resolution_result is None for cast_kind). Existing cast narration flow proceeds when the player follows up with action text. Phase 1's `directive_would_fire_dm_respond:` still fires (matcher consumed the row) but `directive_resolved:` does NOT — the empirical-baseline log line `directive_resolution_skipped: reason=cast_kind` is the structural confirmation.

---

## §5. Promotion-gate impact

What each deferred scenario feeds, per `RESOLUTION_BINDING_SPEC.md` §13.9 + Ship 1 promotion criteria:

| Scenario | Feeds | Load-bearing for Ship 1 promotion? |
|---|---|---|
| **F (mismatch)** | §13.9 criterion 4 — "Mismatch rate observable for Ship 4.5 decision" | **No.** Ship 1 ✅ regardless. F's structural verify confirms Phase 1 mismatch path didn't regress; the Ship 4.5 calibration data point (does multi-actor mismatch happen often enough to fix?) is independent of Ship 1 promotion. |
| **E (cast skip)** | §10.3 log-line shape empirical confirmation | **No.** Structurally covered by `test_resolve_directive.py::test_resolve_returns_none_for_cast_kind`. Live-verify is nice-to-have. |

Ship 1 promoted ✅ at end of S34 on A–D clean walks + zero unretried ROLL_OUTCOME_DRIFT violations + zero `unexpected_binding_co_occurrence:` fires. Neither deferred scenario blocks anything downstream.

---

## §6. Ship 4.5 decision criterion — two purposes, distinguish them

Scenario F has two distinct verification values:

### §6.1 Structural verify (what this scenario walk covers)

Confirm that when a multi-actor batched turn precedes a directive emit, and a non-first-chronological actor rolls, the matcher fires `directive_actor_mismatch:` and the wrong-actor aside instead of auto-resolving against the wrong actor. This is a Ship 1 regression check on Phase 1 behavior — the matcher must NOT have started consuming on mismatch.

A sock-puppet walk (two browser tabs / two devices, one human controlling both) is fine for this purpose. The matcher doesn't care that both controller IDs trace back to one human; it cares that two distinct controller IDs appear in the batcher and produce a multi-actor footer.

### §6.2 Ship 4.5 slot decision (what this scenario walk does NOT cover)

Per `MULTIPLAYER_FIXES.md` §7B.3: *"This ship slots if Ship 1's live verify shows multi-actor batches produce >1 directive-binding ambiguity per session in **real play**. If frequency is ≤1 per session, file v1.x. Decide at Ship 1 verify checkpoint."*

The criterion explicitly says **real play**. A scripted scenario walk where Jordan and Captin (or a sock-puppet pair) deliberately produce a multi-actor batched turn followed by a directive is **test behavior, not natural-play data**. The S32 §4.5 evidence is also called out in `RESOLUTION_BINDING_SPEC.md` §11.14 as "test behavior, not natural play cadence."

**Implication:** running scenario F sock-puppeted confirms the mismatch surface works, but it does NOT produce the data Ship 4.5 needs to slot. The Ship 4.5 decision waits for ≥1 multiplayer play session of natural play with the new resolution-binding wiring in place, then counts how many times multi-actor batches produced directive-binding ambiguity. That's a calendar-bound observation, not a scenario walk.

**Recommended language for the SESSIONS / ROADMAP entry after F lands:**

> Scenario F walked with sock-puppet pair (Jordan + secondary account). Structural confirm: mismatch path fires correctly, no regression in Phase 1 behavior. Ship 4.5 slot decision NOT made by this walk; waits for natural-play observations. File a `tests-to-run-post-session.md` entry: "After any multiplayer play session with ≥1 batched multi-actor turn, grep `directive_actor_mismatch:` count and decide Ship 4.5 if rate > 1 per session."

---

## §7. Aggregate end-of-session grep block

Run after walking F (and optionally E) to confirm the deferred-verify data lands cleanly. Mirrors §13.9 but scoped to the deferred work + Ship 4.5 calibration shape.

```bash
# Total resolutions since service restart (sanity — should be growing)
journalctl --user -u virgil-discord --since "today" | grep -c "directive_resolved:"

# Resolutions that skipped, with reason breakdown
journalctl --user -u virgil-discord --since "today" | grep "directive_resolution_skipped:" | sed 's/.*reason=\([^ ]*\).*/\1/' | sort | uniq -c

# Mismatch count (Ship 4.5 calibration — count for this session)
journalctl --user -u virgil-discord --since "today" | grep -c "directive_actor_mismatch:"

# Unretried drift violations (criterion 5 — must remain 0)
journalctl --user -u virgil-discord --since "today" | grep "violation_class=roll_outcome_drift" | grep "retry_passed=0\|retry_passed=-" | wc -l

# Unexpected co-occurrence (must remain 0 — §2.3 mutual-exclusion canary)
journalctl --user -u virgil-discord --since "today" | grep -c "unexpected_binding_co_occurrence:"
```

If the unretried-drift count moves above 0 during deferred verify, that's a Ship 1 regression — surface as HALT, the bot lost binding fidelity somewhere. If `unexpected_binding_co_occurrence:` fires, the flow-mutual-exclusion analysis in §2.3 has a counterexample — investigate which call site populated both kwargs.

---

## §8. Pickup instructions (what to do when this doc is opened after `/clear`)

Self-contained walkthrough — no need to re-read `RESOLUTION_BINDING_SPEC.md` §13 to execute.

1. **Confirm campaign 22 state matches the §2 snapshot.** Run the sqlite grep in §2. If Donovan + Karrok are both alive=1 with controller IDs matching, proceed. Otherwise re-recon and adjust the scenarios to use whoever's currently bound.

2. **Confirm both players are available.** F needs two real Discord identities online. Sock-puppet works if Jordan has access to both accounts; coordinated walk with Captin0bvious is the natural-play shape.

3. **Walk Scenario F per §3.** Greps in §3.3 confirm. HALT if any of the failure modes in §3.4 surface.

4. **Decide Scenario E per §4.** Check sheets via `!cantrips` / `!spellbook`. Walk if either PC has a cantrip; skip otherwise.

5. **Run aggregate greps per §7.** Capture the mismatch count + zero-fire confirmations.

6. **Report results + update docs.** Doc-update touches:
   - `text files/ROADMAP.md` — note Ship 4.5 decision (slot vs v1.x) IFF natural-play observations accumulated enough to decide; otherwise leave Ship 4.5 status as "calibration in progress."
   - `text files/SESSIONS.md` — entry for the deferred-verify session, distinguishing structural verify result (passed/failed) from Ship 4.5 calibration data point (count + decision OR "calibration deferred to next session").
   - `text files/tests-to-run-post-session.md` — append the §7 grep block as a recurring post-play check, so Ship 4.5 calibration data accumulates naturally over future play sessions without needing another scripted walk.

7. **Do NOT re-walk A–D.** Those landed clean in S34. Re-walking is wasted time unless a Ship 1 regression is suspected for a separate reason.

8. **Archive this doc when done.** Move to `_trash/MULTIPLAYER_VERIFY_DEFERRED_<date>.md` or a `_done/` subfolder. Its purpose was single-use pickup; once the deferred verify lands, the SESSIONS entry carries the result and this companion doc is no longer load-bearing.

---

## §9. Cross-references

- `RESOLUTION_BINDING_SPEC.md` §13 — spec source for all six scenarios
- `RESOLUTION_BINDING_SPEC.md` §13.9 — aggregate verify criteria
- `RESOLUTION_BINDING_SPEC.md` §11.4 — multi-actor mismatch decision lock (Phase 1 behavior preserved)
- `RESOLUTION_BINDING_SPEC.md` §11.14 — debounce/rapid-fire decision (test-vs-play distinction)
- `MULTIPLAYER_FIXES.md` §7B — Ship 4.5 filed candidate + §7B.3 slot decision criterion
- `BUG_1_SPEC.md` §F.1 — combat-mode skip gate (relevant to F's exploration-mode precondition)
- `S32_MULTIPLAYER_PLAYTEST_FINDINGS.md` §3.10, §4.3 — original multi-actor evidence that motivated Ship 4.5
- `discord_dnd_bot.py:331` — `_wrong_actor_aside` text source
- `discord_dnd_bot.py:_handle_dm_roll_arrival` — matcher behavior for mismatch path (post-Ship-1)
