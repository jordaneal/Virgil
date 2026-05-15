# Tests to Run Post-Session — Observability Batch S22–S25 + B2 Attack Fix

Session 18 | May 4, 2026 (live-verified)

Each section gives the exact Discord input to type in **#dm-narration** and the
exact journalctl grep to verify the log fired. Run in order — S22 first because
it needs a fresh roll event to sit in the buffer long enough to expire.

**IMPORTANT — `--user` is required.** `virgil-discord.service` is a USER-level
systemd unit. The grep `journalctl -u virgil-discord` (without `--user`)
queries the system journal and returns NOTHING — even when the log fired
correctly. Always use `journalctl --user -u virgil-discord`. Silent empty
output looks identical to "the log didn't fire" — when in doubt, test the
grep against a known-firing log line first (e.g. `prompt_size`, which fires
every turn) to confirm your grep actually works.

**Live verification status (Session 18, campaign 17):**
- S22 ✅ verified live (`age_s=188.7` on 11:44 sweep)
- S23 ✅ verified live on second pass (`new='Garrik' existing='Garrick' distance=1`, NPC id=11) — first pass missed because DM auto-corrects player typos
- S24 ✅ verified every turn (24-25k char prompts surfaced bloat pattern; correlates with empty-narration failure mode)
- S25 ✅ verified every turn (stable shape across 5 turns)
- B2 ✅ verified live (correct Avrae syntax + `-t TARGET`)
- B2.1 ✅ verified live (no quotes around multi-word names + narration before command)
- **Avrae-binding layer** (`<None>: Dealt N damage!`) ❌ filed for next session — downstream of godmode, addressed by `COMMITTED_ACTION_RESOLUTION_SPEC.md`. NOT a B2/B2.1 failure even when it appears alongside correct orchestration output.

---

## S22 — unconsumed_roll_swept (avrae_listener.py)

**What it logs:** Any Avrae roll event that aged past the 75-second TTL without
being consumed by a DM narration turn.

**How to trigger:**
1. In #dm-narration, have Avrae run a roll command (e.g. `!a` or `!check`) so a
   roll embed appears.
2. **Do NOT type any player action for at least 90 seconds.** Let the event sit.
3. After 90s, type any player action in #dm-narration to trigger a DM turn. The
   DM turn calls `_sweep()` before consuming, so the expired event is logged
   before it's discarded.

Alternatively, trigger directly by typing in #dm-narration right after a roll
that was already more than 75s old (e.g. a roll from a previous session that
never got a narration response).

**Exact Discord input (after letting a roll sit 90+ seconds):**
```
I look around the tavern.
```

**Exact journalctl grep:**
```bash
journalctl --user -u virgil-discord --since "5 minutes ago" | grep unconsumed_roll_swept
```

**Expected output shape:**
```
unconsumed_roll_swept: actor='Donovan Ruby' action='attack' age_s=127.3
```

Fields to verify:
- `actor=` shows the character name from the Avrae embed
- `action=` shows the roll kind (attack, check, save, cast, roll, rest, damage)
- `age_s=` shows a positive float greater than 75.0

**What a clean (no-sweep) turn looks like:** No `unconsumed_roll_swept` lines
appear when you type a player action within 75 seconds of a roll — the roll is
consumed normally and the event is removed without logging.

---

## S23 — npc_near_match / location_near_match (dnd_engine.py)

**What it logs:** When a new NPC or location canonical name is inserted and any
existing name in the same campaign is within Levenshtein edit distance ≤ 2.

**How to trigger — NPC near-match:**

Make sure your active campaign already has an NPC named "Donovan" in `dnd_npcs`.
Then play a turn that causes the parser to extract a slightly different spelling:

**Exact Discord input:**
```
I ask Donavan about the theft.
```
_(note: "Donavan" not "Donovan" — one character different)_

If the parser picks up "Donavan" as a new NPC name and inserts it as a new
canonical row, the near-match log fires.

**Exact journalctl grep:**
```bash
journalctl --user -u virgil-discord --since "2 minutes ago" | grep npc_near_match
```

**Expected output shape:**
```
npc_near_match: new='Donavan' existing='Donovan' distance=1
```

**How to trigger — location near-match:**

Play a turn that introduces a new location name similar to an existing one:
```
We head to the Cavern to regroup.
```
_(if "Tavern" already exists in the campaign's dnd_locations)_

**Exact journalctl grep:**
```bash
journalctl --user -u virgil-discord --since "2 minutes ago" | grep location_near_match
```

**Expected output shape:**
```
location_near_match: new='Cavern' existing='Tavern' distance=1
```

**What no-fire looks like:** No `npc_near_match` or `location_near_match` lines
when the name is either (a) an exact match (hits update branch), (b) distance > 2
from all existing names, or (c) in a different campaign.

**Live verification gotchas (Session 18 findings):**

The diagnostic is correct but rarely fires in normal play. Three reasons:

1. **DM auto-corrects player typos** in narration before the parser sees the text.
   Player typing "Garric" → DM narrates "Garrick" → parser extracts canonical name →
   `npc_upsert` hits update branch (no INSERT, no near-match log). The strict-equality
   identity rule survives in practice partly because the LLM does soft matching itself.
2. **`bad_name_format` validator** in `npc_extractor.py` (regex
   `^[A-Z][\w'\-]+(\s+[A-Z][\w'\-]+){0,2}$`) requires every word capitalized.
   "Garrik the Younger" / "Hilda the Brewer" / "John of Stonebridge" all fail
   and are silently dropped before reaching `npc_upsert` — INSERT branch never
   runs, no near-match log fires.
3. **Real new canonical names** are usually distance > 2 from existing canon.

**To force-fire S23 for verification:** introduce a brand-new NPC with a
single-word capitalized name very close to an existing one, e.g. if `Garrick`
exists, type `I notice a stranger named Garrik enter the room.` (no descriptor —
single capitalized word, passes the validator). The DM may still correct it,
but if it echoes "Garrik" as a separate person, the log fires.

---

## S24 — prompt_size (dnd_engine.py)

**What it logs:** Every DM narration turn emits one line measuring the size of
the assembled system prompt by section.

**How to trigger:** Any player action that goes through `dm_respond` fires it.
No special setup needed.

**Exact Discord input:**
```
I look around the room.
```
_(any player action — this log fires on every single DM turn)_

**Exact journalctl grep:**
```bash
journalctl --user -u virgil-discord --since "2 minutes ago" | grep prompt_size
```

**Expected output shape:**
```
prompt_size: campaign=17 system=14823 retrieval=0 party=312 scene=87 directives=1240 total=14823
```

Fields to verify:
- `campaign=` matches your active campaign id (check `/campaigns` to confirm)
- `system=` — build_dm_context output in chars before skeleton prepend; expect 8000–20000 on a normal turn
- `retrieval=` — chroma history + pacing examples in chars; 0 on turns with no relevant history
- `party=` — character context block in chars; > 0 when a character is cached via `/refresh`; 0 on cache miss
- `scene=` — scene state field values in chars; > 0 after `/play` initializes a scene
- `directives=` — pacing + central thread + consequence + philosophy in chars; 0 if all directives are silent
- `total=` — final prompt size after all prepends; equals `system` when no skeleton block is loaded

**Key observations to note at the table:**
- If `total` is regularly > 18000 chars: the prompt is long enough that HARD STOP
  RULES at the bottom may be getting buried. Worth investigating which section is large.
- If `directives` is regularly > 3000: the directive stack is consuming significant
  context. Check `pacing_directive:` and `consequence_directive:` logs for what's firing.
- If `party` is 0 on a normal turn: the character cache missed — run `/refresh`.

---

## S25 — directive_emit (dnd_engine.py)

**What it logs:** One line per DM turn summarising which directives fired with non-empty content — the single per-turn signal for threshold calibration.

**How to trigger:** Any player action that goes through `dm_respond`. No special setup needed.

**Exact Discord input:**
```
I look around the room.
```

**Exact journalctl grep:**
```bash
journalctl --user -u virgil-discord --since "2 minutes ago" | grep directive_emit
```

**Expected output shape:**
```
directive_emit: campaign=17 pacing=none central_thread=0 philosophy=3200 consequence=0 capability=none commitment=0
```
or (during high-tension encounter):
```
directive_emit: campaign=17 pacing=climax central_thread=1 philosophy=3200 consequence=2 capability=CONFIRMED commitment=0
```

Fields to verify:
- `pacing=` — tier name (`low`/`medium`/`high`/`climax`) when pacing directive has content, `none` when silent
- `central_thread=` — `1` when first skeleton hook fired, `0` when no hooks wired
- `philosophy=` — char count of the philosophy block; expect > 0 whenever `dm_philosophy.md` exists
- `consequence=` — count of surfaced consequences for this turn (0–3)
- `capability=` — verdict name (`CONFIRMED`, `VALID_BUT_UNCONFIGURED`, `UNVERIFIED`) when a capability claim was flagged, `none` when no check
- `commitment=0` — always 0 until the commitment directive is wired

**Key cross-check with prompt_size:** `directives=` in `prompt_size:` should roughly match the sum of active directive text lengths visible in `directive_emit:`. Both lines fire on the same turn — grep for both to compare.

---

## B2 / B2.1 — `!attack` template directive verification (dnd_orchestration.py)

**What it changes:** Pre-fix, `RollDecision(category='attack')` produced bare
`!roll` in the quoted command while telling the LLM (in `reason`) to use
`!attack`. The LLM freelanced bare `!attack`, Avrae rolled against
`<No Target>`, and the attack vanished. Post-B2 the directive emits a
fill-in template; post-B2.1 the template uses Avrae's positional syntax
(no quotes around multi-word names) and includes an explicit narration
mandate so the LLM doesn't produce a command-only response.

**How to trigger:** Any combat-intent player action.

**Exact Discord input:**
```
I attack Garrick with my unarmed strike.
```
or
```
I cast eldritch blast at the goblin.
```

**What to look for in Discord (THREE verification surfaces — all three must pass):**

1. **Narration before the command.** The bot's response must include several
   sentences describing the player's attempt — the swing, lunge, aim, or cast,
   and the target's brief brace or dodge. A response that is ONLY the templated
   command (no narrative body) is a B2.1 regression — the directive's narration
   mandate isn't holding.

2. **Correct unquoted Avrae syntax.** The bot's narration should END with:
   ```
   !attack unarmed strike -t Garrick
   ```
   or for spells:
   ```
   !cast eldritch blast -t the goblin
   ```
   - NO quotes around `unarmed strike` or `eldritch blast` — Avrae uses
     positional parsing. `!attack "unarmed strike" -t Garrick` is WRONG (B2.1
     regression).
   - `-t TARGET` is mandatory. Bare `!attack` is the original B2 failure mode.
   - `TARGET` should be the canonical NPC name (`Garrick`), not a descriptor
     (`the bartender`).

3. **Avrae embed that follows: `-t TARGET` should bind to a real combatant.**
   This is the deepest verification surface. If the Avrae embed shows
   `<None>: Dealt N damage!`, the LLM emitted correct syntax but Avrae couldn't
   bind `-t TARGET` to a combatant in initiative. **This is NOT a B2/B2.1
   failure** — it's the Avrae-binding-layer issue downstream of godmode.
   Addressed by `COMMITTED_ACTION_RESOLUTION_SPEC.md` (initialize combat,
   add target to init tracker, then attack). Until that spec ships, expect
   `<None>` even when our orchestration is correct.

**Failure-mode triage:**

| What you see in Discord | Where the failure is | Action |
|---|---|---|
| Bare `!attack` (no weapon, no target) | LLM ignored the directive | B2 regression — escalate to option A or C per WHY.md |
| `!attack "weapon" -t Garrick` (with quotes) | LLM followed an obsolete template | B2.1 regression — verify directive shipped |
| Command-only response, no narration | LLM crowded out narration | B2.1 regression — verify narration mandate is in directive |
| Correct `!attack weapon -t Garrick` + narration + `<None>` from Avrae | Avrae binding layer | NOT a B2 issue — committed-action spec territory |
| Correct everything, Avrae targets Garrick by name | All four layers working | ✅ Done |

**Avrae stale-state cleanup (recommended at session start):**
Avrae's init tracker can carry combatants across sessions. If you see weird
target names like `throx` in Avrae embeds, they may be stale. Run
`!init end` (Avrae command in the channel) to clear the tracker before
the first combat-intent test of a session.

**Exact journalctl grep:**
```bash
journalctl --user -u virgil-discord --since "2 minutes ago" | grep -iE "godmode_gap|posted for guild|consequence_directive|prompt_size|directive_emit"
```

**No-fire (correct) for non-combat:** Skill checks, saves, social, exploration
all use the existing `!check`/`!save`/`!roll` quoted-literal directive — the
attack template doesn't apply and nothing about the existing flow changed.

---

## Quick reference — all S22–S25 greps in one block

```bash
journalctl --user -u virgil-discord --since "10 minutes ago" | grep -E "unconsumed_roll_swept|npc_near_match|location_near_match|prompt_size|directive_emit"
```

**Also useful — every per-turn signal in one block:**

```bash
journalctl --user -u virgil-discord --since "10 minutes ago" | grep -E "prompt_size|directive_emit|godmode_gap|consequence_directive|EMPTY response|too short to narrate|world_health"
```

This gives the per-turn shape (prompt size, directive emission summary), the
godmode-gap diagnostic (combat intent in non-combat mode), the consequence
directive surfacing, the empty-narration failure modes, and the world health
aggregate — five distinct signals on one screen for quick eyeballing of a
testing pass.

---

## Session 19 — Committed Action Resolution v1 (escape-only)

### What shipped

`compute_commitment_directive` in `dnd_orchestration.py`. New `last_dm_response`
column on `dnd_scene_state`. Three new diagnostic log lines emitted from
`dm_respond`: `commitment_directive:` (every turn), `commitment_retraction_filtered:`
(only on retraction), `directive_emit: commitment={1|0}` (promoted from `0`
placeholder). New prompt block `=== UNRESOLVED COMMITMENT ===` rendering
after `=== PENDING CONSEQUENCES ===`.

Locked decisions (from `COMMITTED_ACTION_RESOLUTION_REVIEW.md`): COMBAT-only
scope, regex resolution check, recompute prior intent, single-turn lookback,
post-consequence composition, B2.1 narration mandate baked in, retraction
grammar in v1 with diagnostic, layer-3 init orchestration deferred to sibling
spec.

### Canonical scenario — directive should fire

In `#dm-narration` of campaign 17, with no active init tracker:

| Turn | Player typed | Expected behavior |
|---|---|---|
| 1 | `I swing my dagger at Garrick` | DM narrates the swing; Avrae rolls (`!attack unarmed strike -t Garrick` per B2.1). May produce `<None>: Dealt N damage!` per the still-open layer-3 binding gap. Either way, `last_dm_response` is now persisted. |
| 2 | `I head outside to help the child` | **Directive should fire.** DM narration must address the prior commitment first (resolve / refuse / charge for the new action). LLM must NOT silently accept the disengagement. |

**Expected log lines after turn 2:**

```bash
journalctl --user -u virgil-discord --since "2 minutes ago" | grep -E "commitment_directive|directive_emit|godmode_gap"
```

Should show:
- `godmode_gap: campaign=17 mode=exploration intent=combat ...` (turn 1; pre-existing diagnostic)
- `commitment_directive: campaign=17 fired=1 prior_intent=combat current_intent=trivial is_scene_shift=1 avrae_drained=0 reaction_verbs=0 retraction_filtered=0` (turn 2; **fired=1 is the success signal**)
- `directive_emit: ... commitment=1` (turn 2)

If `fired=0` on turn 2, look at the gate signals to see which one blocked
(reaction_verbs likely candidate if Avrae or the LLM narrated a reaction;
avrae_drained=1 if `!attack` did fire; is_scene_shift=0 if the regex didn't
catch the phrasing).

If `fired=1` but the LLM ignores the directive in narration, that is a
strength-tuning question (file in ROADMAP for `#11.5` follow-up), NOT a
shipping blocker. Verify narration content shows one of the three options
(prior consequence first / refuse / charge).

### Retraction scenario — directive should suppress

| Turn | Player typed | Expected behavior |
|---|---|---|
| 1 | `I swing my dagger at Garrick` | Same as above. |
| 2 | `Wait, never mind, I sheath my dagger and step back` | **Directive should NOT fire.** Retraction grammar suppresses. |

**Expected log lines after turn 2:**

- `commitment_directive: ... fired=0 ... retraction_filtered=1`
- `commitment_retraction_filtered: campaign=17 text='Wait, never mind, I sheath my dagger and step back'`
- `directive_emit: ... commitment=0`

### No-fire scenario — combat continuation with reaction verbs

| Turn | Player typed | Expected behavior |
|---|---|---|
| 1 | `I swing my dagger at Garrick` | DM narrates "Garrick recoils, gasping" or similar (reaction-verb proximity to the target). |
| 2 | `I press the attack` | **Directive should NOT fire.** Multiple gates block: `is_scene_shift=0` (continuation, not a shift) AND `reaction_verbs=1` (DM narrated resolution). |

**Expected log line after turn 2:**

- `commitment_directive: ... fired=0 prior_intent=combat current_intent=combat is_scene_shift=0 reaction_verbs=1`

### Quick grep — all commitment signals in one block

```bash
journalctl --user -u virgil-discord --since "10 minutes ago" | grep -E "commitment_directive|commitment_retraction_filtered|godmode_gap|directive_emit"
```

### Schema sanity check

```bash
python3 -c "
import sys; sys.path.insert(0, '/home/jordaneal/scripts')
import dnd_engine, sqlite3
conn = sqlite3.connect(dnd_engine.DB_PATH)
cols = sorted(r[1] for r in conn.execute('PRAGMA table_info(dnd_scene_state)'))
conn.close()
print('last_dm_response present:', 'last_dm_response' in cols)
"
```

### Test suite

```bash
python3 test_commitment_directive.py
```

82 assertions, exit 0 expected. Adjacent test files
(`test_consequence_directive.py`, `test_directive_emit.py`,
`test_attack_directive.py`, `test_classify_action_intent.py`,
`test_check_action_capability.py`, `test_avrae_sweep.py`) should also remain
green — verify after pulling.

---

## Pre-session setup prerequisites — Combat Persistence Directive v1 (filed pending ship)

Forward-looking — applies when `COMBAT_PERSISTENCE_DIRECTIVE_SPEC.md` v1 ships. Listed here so the prereq is captured alongside the rest of the post-session checklist.

### Stale-combatant carry-over check (§12 of the spec)

The persistence directive renders concrete per-combatant state (HP, conditions, alive/dead) from a parsed `!init list` snapshot. If a previous session ended without `!init end` (bot crash, Discord disconnect, abrupt stop), Avrae remembers those combatants. The next `!init list` will surface them and the parser will write them into `dnd_combatant_state`, contaminating the next encounter's directive output.

**Run at session start, before any `!init begin`:**
```
!init end
```

If Avrae replies "There is no combat in this server," carry-over is clean — proceed. If Avrae prompts "Are you sure you want to end combat?" — confirm `yes`. The bot's `_handle_init_event` will fire on the end, calling `clear_active_turn` and (post-v1-ship) `clear_combatants`.

**Diagnostic — verify `dnd_combatant_state` is empty before the first new `!init begin`:**

```bash
sqlite3 /home/jordaneal/scripts/dnd_engine.sqlite \
  "SELECT campaign_id, name, hp_current, hp_max, conditions, updated_at
   FROM dnd_combatant_state ORDER BY campaign_id, init DESC;"
```

Expected output: empty (or rows from completed prior combats that should have been cleared by `_handle_init_event`). If rows exist for the active campaign, run `!init end` again or manually clear via a `/reset_combatants` slash command (filed for v1 if friction is observed).

**Why this matters:** the directive renders whatever it sees. A stale row for "Goblin1 — HP 22/22" from last session's un-ended combat would appear in the directive body for the next encounter's first turn, pressuring the LLM to honor a creature that isn't actually present.

Filed v1.x candidate ships if the prerequisite is forgotten too often:
- `/reset_combatants` slash command for explicit cleanup.
- Auto-clear on bot startup if `dnd_scene_state.mode != 'combat'` (would risk clearing data mid-combat after a restart, needs careful design).

---

## Track 4 #1 — Narrative Inventory v1 (Session 22, shipped live)

**What it does:** per-character narrative inventory (loot, quest objects, story items). Distinct from Avrae sheet-bound combat gear. Renders into the DM system prompt as `=== {CHARACTER}'S NOTABLE ITEMS ===` block so the LLM sees what the player is carrying without a verdict-shift layer.

### Live verification flow

1. **Add an item.** Pick a bound character via the autocomplete dropdown:
   ```
   /giveitem character:Donovan Ruby item:silver key
   ```
   Expected ephemeral reply: `Added: **Donovan Ruby** — silver key`. Expected logs:
   ```
   inventory_add: campaign={N} character='Donovan Ruby' item='silver key' qty=1 action=inserted
   inventory_give: campaign={N} character='Donovan Ruby' item='silver key' qty=1 action=inserted
   ```

2. **Read inventory.** Defaults to caller's bound character:
   ```
   /inventory
   ```
   Expected ephemeral reply: `**Donovan Ruby**'s inventory:\n- silver key`.

3. **Verify prompt-context render.** Type any normal action in `#dm-narration`:
   ```
   I look around
   ```
   Expected log line on the `dm_respond` turn:
   ```
   inventory_render: campaign={N} character='Donovan Ruby' count=1
   ```
   `prompt_size: ... system={N}` should grow by ~50-100 chars vs a turn with empty inventory.

4. **Verify LLM honors the item.** Type a use action:
   ```
   I try the silver key on the cellar door
   ```
   Expected behavior: LLM narration references the silver key explicitly (turning it in the lock, hearing the click, etc.) — load-bearing test of the prompt-context surface.

5. **Verify persistence across restart.**
   ```bash
   systemctl --user restart virgil-discord
   ```
   Then `/inventory` — silver key still listed (SQLite-persistent, not in-memory).

### Increment + decrement coverage (optional, not required for sign-off)

- `/giveitem character:Donovan Ruby item:silver key` again → `action=incremented` (quantity now 2 because case-insensitive merge).
- `/giveitem character:Donovan Ruby item:Silver Key` (capitalized) → also `action=incremented` (normalization collapses case).
- Manual remove via Python REPL: `from dnd_engine import remove_item; remove_item({campaign_id}, 'Donovan Ruby', 'silver key', quantity=2)` → `action=removed`, row deleted.

### Diagnostic queries

```bash
sqlite3 /mnt/virgil_storage/virgil.db \
  "SELECT campaign_id, character_name, item_name, quantity, created_at
   FROM dnd_inventory ORDER BY campaign_id, character_name, item_name;"
```

Expected columns + lowercase `item_name` storage.

### Test suite

```bash
cd /home/jordaneal/scripts && python3 test_inventory.py
```

31 assertions, exit 0 expected.

---

## Track 7 #2 — Multi-actor Arbitration + Narration Verification (S25 #7)

All verifications use `journalctl --user -u virgil-discord -n 200 --no-pager` (without `--user` returns nothing — user unit). The two new always-fire log lines appear on every `dm_respond` turn after restart. Run `/travel` first as Step 0 (clean-room retrieval per session start protocol).

---

### F-48 — Concurrent two-actor input (arbitration: line, two-actor sequence)

**What it verifies:** Two players posting in close succession produces an `arbitration:` log with `actors=2`, both verdicts resolved, `merge_plan=sequence` (when non-contradictory).

**How to trigger:**
1. Have two bound characters in the campaign (`/setcharacter` for each).
2. Quickly post (or have Tazz post) two actions in `#dm-narration`:
   ```
   I look around the room carefully
   ```
   Then (second player, or simulate by posting fast):
   ```
   I keep my hand on my sword and watch the door
   ```
3. Wait for `dm_respond` to fire.

**Expected log line:**
```
arbitration: campaign={N} actors=2 primary='<name>' merge_plan=sequence overridden=0
```
Fields to verify: `actors=2`, `merge_plan=sequence`, `overridden=0` (non-contradictory inputs don't produce override).

**Expected narration:** Both actors mentioned in the response — one looking around, one watching the door.

**Grep:**
```bash
journalctl --user -u virgil-discord -n 200 --no-pager | grep "arbitration:"
```

---

### F-49 — Fabricated combatant (verification: violation_class=fabricated_combatant)

**What it verifies:** If the LLM invents an NPC name in its narration that isn't in the combatants list or canonical NPC table, `verify_narration()` catches it, retries, and logs the violation.

**How to trigger (outside combat):**
1. Type a player action that might invite NPC invention:
   ```
   I call out — is anyone else here?
   ```
2. If the LLM response mentions a named NPC not previously established (e.g. "The Watcher steps forward..."), the verifier should fire.

**Expected log line (if violation caught):**
```
verification: campaign={N} passed=0 violation_class=fabricated_combatant retry_fired=1 escalated=0
```
Or if retry succeeds:
```
verification: campaign={N} passed=0 violation_class=fabricated_combatant retry_fired=1 escalated=0
```
If no violation this turn:
```
verification: campaign={N} passed=1 violation_class=none retry_fired=0 escalated=0
```

**Note:** This test may not fire on the first try if the LLM doesn't fabricate. The key verification is that `verification:` always-fires (even `passed=1`) — that confirms the layer is running.

**Grep:**
```bash
journalctl --user -u virgil-discord -n 200 --no-pager | grep "verification:"
```

---

### F-50 — Arbitration override (social override across players)

**What it verifies:** When one actor's FREE action asserts an outcome that contradicts another actor's binding CHECK result, `merge_plan=override` fires and the overriding actor appears in `overridden`.

**How to trigger (requires a CHECK scenario + second actor asserting override):**
1. Type an action that classifies as CHECK:
   ```
   I try to persuade the guard to let us through
   ```
2. Immediately type (or have Tazz type) a FREE action that explicitly claims success:
   ```
   He agrees with us and opens the gate
   ```
3. Wait for `dm_respond`.

**Expected log line:**
```
arbitration: campaign={N} actors=2 primary='<first actor>' merge_plan=override overridden=1
```
`overridden=1` means one actor was overridden (the FREE actor asserting "he agrees with us" contradicts the CHECK result's constraint).

**Grep:**
```bash
journalctl --user -u virgil-discord -n 200 --no-pager | grep "arbitration:"
```

---

### Two-actor non-contradictory (sequence, no override)

**What it verifies:** Compatible actions from two actors produce `merge_plan=sequence`, both actors present in narration, no override.

**How to trigger:**
1. Two bound characters, post two compatible actions:
   ```
   I attack the goblin with my sword
   ```
   ```
   I cast Cure Wounds on Donovan
   ```
2. Wait for `dm_respond`.

**Expected:** `arbitration: campaign={N} actors=2 merge_plan=sequence overridden=0`. Both actors' actions narrated. `verification: passed=1 violation_class=none`.

---

### Baseline always-fire check (both log lines every turn)

After restart, type any single-player action:
```
I look at the map on the wall
```

**Expected:** Both log lines present in the same turn's output:
```
arbitration: campaign={N} actors=1 primary='...' merge_plan=sequence overridden=0
verification: campaign={N} passed=1 violation_class=none retry_fired=0 escalated=0
```
If either line is missing, the feature flag may be False or the code path didn't reach the logging call. Check `ARBITRATION_ENABLED` and `VERIFICATION_ENABLED` in `adjudicator.py` and `narration_verifier.py`.

---

### Test suites

```bash
cd /home/jordaneal/scripts && python3 test_arbitration.py && python3 test_narration_verifier.py && python3 test_dm_respond_arbitration.py
```

Expected: 21 + 40 + 9 = 70 assertions, all exit 0.

---

## Track 6 #4 — NPC Stat Hydration at Init-Add (S25 #8)

### 1. Bound-PC skip

**What it verifies:** Bound PCs are skipped by the hydration scan with `source=bound_pc_skip`.

**How to trigger:**
1. `/travel` to any location to ensure clean scene state.
2. Type:
   ```
   !init begin
   ```
3. Add your bound PC to init (Avrae will auto-add on their turn, or use `!init add 10 Donovan`).
4. Type `!init list`.

**Expected grep:**
```
hydration: campaign=... npc='Donovan' source=bound_pc_skip stats_filled=none cr=none
```
No `npc_upsert` firing for the PC name. `dnd_npcs` table does NOT get a row for Donovan from hydration.

---

### 2. `!init add` NPC → generic_fallback + CR prompt

**What it verifies:** `<None>`-token NPC with no `cr_str` fires `generic_fallback` and posts a CR prompt to `#dm-aside`.

**How to trigger:**
1. In `#dm-narration`:
   ```
   !init add 0 testdummy
   ```
2. Wait for Avrae's init-list embed, then:
   ```
   !init list
   ```

**Expected:**
- `#dm-aside` receives a CR prompt: "What CR is **testdummy**? Reply `/hydrate npc:testdummy cr:<CR>`"
- Log:
  ```
  hydration: campaign=... npc='testdummy' source=generic_fallback stats_filled=ac,atk,dmg,save,init cr=none
  ```
  (Note: `hp_max` NOT in `stats_filled` — left NULL intentionally.)

---

### 3. `/hydrate` fills stats + subsequent `!init list` routes to miss

**What it verifies:** `/hydrate` writes stats; second init-list parse skips the same NPC as `source=miss`.

**How to trigger (DM-only slash command):**
1. After the testdummy is in init (from test 2 above):
   ```
   /hydrate npc:testdummy cr:1/2
   ```
2. Check ephemeral response — should contain:
   ```
   Hydrated `testdummy` at CR 1/2: HP 22, AC 13, Atk +4, Dmg 1d8+2.
   ```
3. Trigger another init-list parse:
   ```
   !init list
   ```

**Expected logs:**
```
hydration_manual: campaign=... npc='testdummy' cr=1/2 stats_written=1 fields_updated=hp,ac,atk,dmg,save,init
hydration: campaign=... npc='testdummy' source=miss stats_filled=none cr=1/2
```
No `!init modify` anywhere in logs. No sync hint in ephemeral response.

---

### 4. `!init madd` NPC → avrae_madd (non-None status_token)

**What it verifies:** `!init madd` combatants (with HP-backed tokens) route to `npc_register_avrae_madd`.

**How to trigger:**
1. With init active:
   ```
   !init madd Goblin -name "TestThug"
   ```
2. Type `!init list`.

**Expected log:**
```
hydration: campaign=... npc='TestThug' source=avrae_madd stats_filled=none status_token=<Healthy>
```
`dnd_npcs` row created with `avrae_source='avrae_madd'`, all stat columns NULL.

---

### 5. `/hydrate` with invalid CR → ephemeral error

**What it verifies:** Bad CR string returns error, no DB write.

**How to trigger:**
```
/hydrate npc:testdummy cr:99
```

**Expected:** Ephemeral response: `Invalid CR '99'.` No log line for `hydration_manual:`.

---

### 6. Cleanup

```
!init end
```

**Expected:** Init ends cleanly. `state_footer:` log line shows `mode=exploration`.

---

### Test suites

```bash
cd /home/jordaneal/scripts && python3 test_npc_hydrator.py && python3 test_npc_hydrate_stats.py && python3 test_npc_register_avrae_madd.py && python3 test_hydration_hook.py && python3 test_slash_hydrate.py
```

Expected: 24 + 17 + 7 + 20 + 12 = 80 assertions, all exit 0.

---

## Track 6 #5.1 — Combat Entry Assist (May 8, 2026)

**What it does:** When a new NPC is upserted (`was_new=True`), `srd_resolver.resolve()` runs immediately. If a confident SRD match is found, a suggestion is posted to `#dm-aside` with the `!init madd` command pre-filled.

**Verify startup (no Discord interaction needed):**
```bash
journalctl --user -u virgil-discord -n 50 --no-pager | grep srd_resolver
```
Expected: `srd_resolver: index loaded entries=334 path=.../srd_monsters.json`

---

### 1. Exact-match suggestion (SRD-named NPC in narration)

**How to trigger:** Type in `#dm-narration`:
```
A Goblin steps out from the shadows.
```

**Watch `#dm-aside`** for the suggestion embed:
```
🎯 **SRD match for "Goblin":** Goblin (CR 1/4, HP 7, AC 15)
To add with Avrae's full stat block, type:
!init madd "Goblin" -name "Goblin"
*(Or `!init add 0 "Goblin"` — Virgil will ask for CR.)*
```

**Exact journalctl greps:**
```bash
journalctl --user -u virgil-discord --since "2 minutes ago" | grep "srd_suggestion:"
```

Expected two-line shape:
```
srd_suggestion: campaign=20 input='Goblin' candidate='Goblin' cr='1/4' confidence=1.00 method=exact posted=0
srd_suggestion: campaign=20 input='Goblin' candidate='Goblin' cr='1/4' confidence=1.00 method=exact posted=1
```

Fields to verify:
- `method=exact` for an SRD-named creature
- `posted=0` line emitted by `resolve()` before Discord send
- `posted=1` line emitted by `_post_srd_suggestion()` after Discord send
- `confidence=1.00` for exact matches

---

### 2. Miss → no suggestion (non-SRD creature, no fuzzy/LLM match)

**How to trigger:**
```
A mysterious figure named Xorgath steps forward.
```

**`#dm-aside`** should receive NO suggestion card for "Xorgath".

**Exact journalctl grep:**
```bash
journalctl --user -u virgil-discord --since "2 minutes ago" | grep "method=miss"
```

Expected:
```
srd_suggestion: campaign=20 input='Xorgath' candidate=none cr=none confidence=none method=miss posted=0
```

Only one log line (no `posted=1`) — confirms the two-line shape fires both on hit and only the first line on miss.

---

### 3. Session dedup — second narration of same creature

**How to trigger:** After step 1 fired for "Goblin", type in `#dm-narration`:
```
Another Goblin appears.
```

**`#dm-aside`** should NOT receive a second suggestion card for "Goblin".

**Exact journalctl grep:**
```bash
journalctl --user -u virgil-discord --since "5 minutes ago" | grep "method=dedup"
```

Expected:
```
srd_suggestion: campaign=20 input='Goblin' candidate=none cr=none confidence=none method=dedup posted=0
```

Dedup is per-campaign, per-process-lifetime. Restart clears it (see note below).

---

### 4. Two-line telemetry shape (combined verification)

**One grep to confirm all three paths fired:**
```bash
journalctl --user -u virgil-discord --since "10 minutes ago" | grep "srd_suggestion:"
```

Expected output (after tests 1–3):
```
srd_suggestion: ... method=exact posted=0
srd_suggestion: ... method=exact posted=1
srd_suggestion: ... method=miss posted=0
srd_suggestion: ... method=dedup posted=0
```

Two lines on hit (posted=0 then posted=1), one line on miss or dedup. This is the §8 two-line shape documented in `srd_resolver.py` module header.

---

### 5. Track 6 #4 avrae_madd path still fires (regression check)

After the #5.1 hook ships, verify the existing hydration hook is unbroken:
```
!init begin
!init madd Goblin -name "TestGoblin"
!init list
```

**Expected log:**
```
hydration: campaign=... npc='TestGoblin' source=avrae_madd stats_filled=none status_token=<Healthy>
```

No regression in the `was_new` flag change to `npc_upsert()` — skeleton_loader calls still accumulate `npcs_written`.

---

### Note on LLM-gated fuzzy suggestions

The LLM path fires when exact and Jaccard fuzzy both miss and a `cloud_router` `extraction` call succeeds. In production this requires an active LLM session. To verify the path is wired correctly (without a live LLM call), check test 11–14 in `test_srd_resolver.py` — all four LLM-gate scenarios are covered with mocks.

If you want to force a live LLM suggestion in Discord, narrate a creature with a clear 5e analog that isn't SRD-named:
```
A Spiny Toad lunges from the swamp.
```

The fuzzy match won't hit (no "toad" key in the SRD index). The LLM should suggest `Giant Frog` at ~0.75 confidence. Watch `#dm-aside` for the suggestion and grep for `method=llm` in the logs.

---

### Test suites

```bash
cd /home/jordaneal/scripts && python3 -m pytest test_srd_resolver.py test_srd_suggestion_hook.py test_srd_index_integrity.py -v
```

Expected: 32 passed (21 + 6 + 5 + 1002 subtests), 0 failed.

---

## Track 4 #3 — Time Progression v1 (Session 27, ⏳ live verify pending)

**Spec:** `/home/jordaneal/virgil-docs/specs/TRACK_4_3_SPEC.md` v1.2 LOCKED. New deterministic time-advancement primitive (`advance_time` in `dnd_engine.py`), pure-function directive sibling (`compute_time_directive` in `dnd_orchestration.py`), `render_state_footer` extension, four call sites (`/travel`, Avrae `!lr` hook, Avrae `!sr` hook, new `/advance` slash command), skeleton-loader `## Starting time` seed.

**S27 verify-attempt-1 outcome:** BLOCKED by unrelated bug. `/play` hung with no response because `async with narration_ch.typing():` raised `HTTPException: 429 (40062)` from Cloudflare's residual cooldown earlier in the session, and the exception propagated up through `app_commands._do_call` → user saw a spinning command. Track 4 #3 code did NOT error — `scene state initialized for campaign 20` fired at 14:47:58, the 429 came at 14:48:13 on the typing endpoint after the time-progression code path had already completed. **Precondition for verify-attempt-2:** ship Bug 4 (typing soft-fail, ROADMAP queue item 4a) FIRST so a residual rate limit on the typing endpoint can no longer block command execution. With Bug 4 in place, the 8-step scenario below can run cleanly. Confirm Cloudflare cooldown has decayed (login latency back to seconds in the journal — see Doctrine §73 canary signal) before retrying.

### What shipped

Two new `dnd_scene_state` columns (`campaign_day`, `day_phase`); new `dnd_time_advancements` audit log table appended to `_CAMPAIGN_SCOPED_TABLES`; six-phase enum `Morning / Midday / Afternoon / Evening / Night / Late Night`; modular phase normalization (O(1)); `set_phase` precedence invariant per §11.I; missing-campaign no-op contract per §8; soft-fail at every call site per §59.

Footer is bot-appended: `📖 Exploration · Day 3, Evening` (always-on once scene_state has time fields). Time directive fires only on the turn immediately following an advancement (recency check on `dnd_time_advancements MAX(created_at)` within 60s window).

### Canonical 8-step live-verify scenario

Run these in a clean test campaign (e.g. `/setcampaign` to a freshly created one). Each step is copy-pasteable.

**Step 0 (preflight):** Confirm migration ran on the live DB:

```bash
sqlite3 /mnt/virgil_storage/virgil.db "PRAGMA table_info(dnd_scene_state)" | grep -E "campaign_day|day_phase"
sqlite3 /mnt/virgil_storage/virgil.db ".schema dnd_time_advancements"
```

Expected: both columns present; `dnd_time_advancements` table + two indexes exist.

**Step 1 — bot restart + footer baseline.**

**Bug 4 cross-verify:** Step 1's `/play` incidentally verifies Bug 4 — a clean response with no `typing_indicator_failed:` line in the journal means both ships are live.

Restart bot, then in #dm-narration:

```
/play
```

**Footer note (S28 verify-surfaced — pending `/play` footer-wiring follow-up, ROADMAP item 4b):** `/play`'s opening embed currently renders a hardcoded onboarding footer (`"Type your actions in this channel. Roll with Avrae (!check, !save, !attack, !cast)."`) rather than `render_state_footer`. The state-aware footer + `state_footer:` log line do NOT fire on `/play`; they fire on the next narration turn (the `_dm_respond_and_post` path). Until 4b ships, this step verifies only the `is_first_session` gate + opening narration. The state-aware `· Day 1, Morning` footer is verified in Step 2 onward.

Expected (post-4b ship): footer line in the opening narration embed reads `📖 Exploration · Day 1, Morning`.

Grep (post-4b ship):

```
journalctl --user -u virgil-discord --since "5 minutes ago" --no-pager | grep "state_footer:" | tail -3
```

Should show `day=1 phase=Morning`.

**Step 2 — `/travel` with multi-day elapsed.**

```
/travel destination:Redhaven elapsed:two days
```

Expected: footer advances to `📖 Exploration · Day 3, Morning`.

Grep:

```
journalctl --user -u virgil-discord --since "2 minutes ago" --no-pager | grep -E "parse_elapsed:|time_advance:" | tail -5
```

Should show `parse_elapsed: input='two days' result=2,0` and `time_advance: campaign={N} source=travel before=1,Morning after=3,Morning days_delta=2 phase_delta=0 detail='Redhaven; elapsed=two days'`.

**Step 3 — `/travel arrival_time` is display-only (§11.G=b).**

```
/travel destination:Old Tavern elapsed:a day arrival_time:midnight
```

Expected: footer advances by +1 day; phase remains the same as input (does NOT jump to Late Night even though `arrival_time:midnight` was passed). The `arrival_time` text appears in the LLM's narration block (TRAVEL_TRANSITION) but does not write the clock.

Grep:

```
journalctl --user -u virgil-discord --since "2 minutes ago" --no-pager | grep "time_advance:" | tail -1
```

Should show `phase_delta=0` (NOT a Late-Night jump).

**Step 4 — Avrae long rest advances per locked §11.I math (set_phase + days_delta).**

Stage some non-Morning phase first (e.g. via Step 5 below) then trigger an Avrae long rest (any user types):

```
!game lr
```

(`!lr` shortcut may not be aliased on every guild; `!game lr` is canonical Avrae syntax. `!game longrest` also works.)

**Expected math (locked §11.I + §5 normalization formula):** `total_steps = before_idx + resolved_phase_delta + days_delta*6`. `_handle_rest_event` calls `advance_time(c, days_delta=1, phase_delta=0, set_phase='Morning')`. The writer ignores `phase_delta`, computes `resolved_phase_delta = (Morning_idx - before_idx) mod 6`, and adds it to `total_steps` along with `days_delta*6`. **Day count is therefore phase-dependent:**

- From Morning (idx 0): `total_steps = 0 + 0 + 6 = 6` → `+1 day`. Land at `Day N+1, Morning`.
- From Midday (idx 1): `total_steps = 1 + 5 + 6 = 12` → `+2 days`. Land at `Day N+2, Morning`.
- From Evening (idx 3): `total_steps = 3 + 3 + 6 = 12` → `+2 days`. Land at `Day N+2, Morning`.
- From Late Night (idx 5): `total_steps = 5 + 1 + 6 = 12` → `+2 days`. Land at `Day N+2, Morning`.

This matches the locked test pattern at `test_advance_time.py:test_set_phase_evening_to_morning_long_rest` (Evening start → +2 days). The narrative shorthand "long rest jumps to next morning" is over-simplified — the math captures `set_phase` as modular forward-distance from current phase, which crosses a day boundary for any non-Morning start, and `days_delta=1` adds another full day on top. **Phase always resolves to Morning regardless of pre-rest phase; day count varies.**

Grep:

```
journalctl --user -u virgil-discord --since "2 minutes ago" --no-pager | grep "time_advance:.*rest_long" | tail -1
```

Should show `source=rest_long ... set_phase=Morning resolved_phase_delta={N}` where `{N}` is `(0 - before_idx) mod 6` — i.e. 0 from Morning, 5 from Midday, 4 from Afternoon, 3 from Evening, 2 from Night, 1 from Late Night.

**Step 5 — `/advance` phase bump.**

```
/advance phases:1
```

Expected: footer phase rolls forward one slot (e.g. Morning → Midday, Late Night → next-day Morning).

Grep:

```
journalctl --user -u virgil-discord --since "1 minute ago" --no-pager | grep "time_advance:.*advance" | tail -1
```

Should show `source=advance ... phase_delta=1`.

**Step 6 — `/advance set_phase` jump (§11.I precedence).**

```
/advance set_phase:Evening
```

Expected: footer phase jumps to `Evening` regardless of current phase. Audit log carries `set_phase=Evening` and `resolved_phase_delta` matching the modular distance.

Grep:

```
journalctl --user -u virgil-discord --since "1 minute ago" --no-pager | grep "time_advance:.*set_phase=Evening" | tail -1
```

Should show all three values: `phase_delta=0 resolved_phase_delta={N} set_phase=Evening`.

**Step 7 — `/advance` short rest equivalent.**

```
!game sr
```

(`!sr` shortcut may not be aliased on every guild; `!game sr` is canonical Avrae syntax. `!game shortrest` also works.)

Expected: footer phase rolls forward one slot via the Avrae short-rest path. No Discord-side clock confirmation message — Avrae rest events update state silently; the footer surfaces on the next narration turn.

Grep:

```
journalctl --user -u virgil-discord --since "1 minute ago" --no-pager | grep "time_advance:.*rest_short" | tail -1
```

**Step 8 — `/purgecampaign` cascade integrity.**

`/purgecampaign` is gated on TWO independent prerequisites: the target campaign must be archived (status flipped via `/deletecampaign`), and the active campaign cannot be purged (must `/setcampaign` away first). The confirmation phrase format is `DELETE <campaign_name>` typed exactly, case-sensitive — not just `DELETE`. Three-command sequence:

**Step 8a — switch off the test campaign:**

```
/setcampaign id:{some-other-campaign-id}
```

(Or `/newcampaign name:scratch` to create + auto-activate one if no other campaign exists on this guild.)

**Step 8b — archive the test campaign:**

```
/deletecampaign campaign_ids:{test-campaign-id}
```

Soft-deletes / archives. Reversible.

**Step 8c — purge the test campaign:**

```
/purgecampaign campaign_id:{test-campaign-id} confirm_phrase:DELETE {test-campaign-name}
```

The `confirm_phrase` must match the canonical campaign name exactly (e.g. `DELETE Thomas`).

Expected: `dnd_time_advancements` rows for the purged campaign drop to 0; cascade summary embed lists per-table counts.

Grep:

```
sqlite3 /mnt/virgil_storage/virgil.db "SELECT COUNT(*) FROM dnd_time_advancements WHERE campaign_id={ID}"
```

Should return 0. Also check the cascade log:

```
journalctl --user -u virgil-discord --since "1 minute ago" --no-pager | grep "campaign_delete_cascade" | tail -1
```

Should include `'dnd_time_advancements': {N>=1}` in the `rows_deleted` dict.

**Step 9 (optional — §J.3 skeleton seed end-to-end coverage).**

Steps 1–8 verify the runtime advance path (`advance_time()` writes both columns + audit log). Step 9 covers the *initialization-only* seed-write — `skeleton_loader.apply_starting_time_seed()` writes `dnd_scene_state.campaign_day` / `day_phase` directly during first `/play`, bypasses `advance_time()`, and does NOT append a row to `dnd_time_advancements` per §11.D=a + §J.3 narrow exception. Not gating for v1 promotion; run if you want full coverage of both writers.

**Setup:** Pick or create a test campaign whose `dnd_scene_state` is at defaults (`campaign_day=1`, `day_phase='Morning'`). The idempotency guard only fires when defaults are intact. Verify before starting:

```
sqlite3 /mnt/virgil_storage/virgil.db "SELECT campaign_day, day_phase FROM dnd_scene_state WHERE campaign_id={N}"
```

Should return `1|Morning`. If not, pick a different campaign or run `/purgecampaign` and recreate.

Edit the campaign's `skeleton.md` at `/home/jordaneal/scripts/campaigns/{N}/skeleton.md` to include a non-default `## Starting time` section:

```
## Starting time

day=5
phase=Evening
```

**Trigger:** in #dm-narration:

```
/setcampaign id:{N}
/play
```

**Expected (DB-truth verification — load-bearing):** `dnd_scene_state` is written directly to `(campaign_day=5, day_phase='Evening')`, bypassing `advance_time()`.

```
sqlite3 /mnt/virgil_storage/virgil.db "SELECT campaign_day, day_phase FROM dnd_scene_state WHERE campaign_id={N}"
```

Expected: `5|Evening`.

**Visual footer note (S28 verify-surfaced — pending `/play` footer-wiring follow-up, ROADMAP item 4b):** `/play`'s opening embed currently renders the hardcoded onboarding footer, not the state-aware footer. The seed write IS load-bearing for visual confirmation of the seed feature, but until item 4b ships, the seed is observable only via sqlite + the `apply_starting_time_seed:` log line. **Once 4b ships, the visual check will read** `📖 Exploration · Day 5, Evening`.

Journal grep:

```
journalctl --user -u virgil-discord --since "2 minutes ago" --no-pager | grep -E "apply_starting_time_seed:|play_first_session_hint" | tail -5
```

Should show:
- `apply_starting_time_seed: campaign={N} seeded day=5 phase='Evening'` (the seed fired)
- `play_first_session_hint: campaign={N} fired=1` (confirms `is_first_session=True` gate opened)

**Verify §J.3 audit-log no-write:**

```
sqlite3 /mnt/virgil_storage/virgil.db "SELECT COUNT(*) FROM dnd_time_advancements WHERE campaign_id={N}"
```

Expected: `0`. The seed write does NOT append to the advancement audit log — that's the §J.3 narrow framing (campaign initialization is not an advancement event).

**Idempotency-guard check:** advance the clock with a real call, then re-trigger the seed code path and confirm it does NOT re-fire.

```
/advance phases:1
```

Then exit and re-`/play`:

```
/play
```

Grep:

```
journalctl --user -u virgil-discord --since "1 minute ago" --no-pager | grep "apply_starting_time_seed:" | tail -1
```

The seed line should indicate skipped / no-op (the contract is "seed write does NOT fire when scene_state is past defaults"). Footer should reflect the post-`/advance` state, NOT re-seed back to Day 5, Evening.

**If Step 9 fails:** the bug is in `skeleton_loader.apply_starting_time_seed()`, not in `advance_time()`. Steps 1–8 isolate the runtime writer; Step 9 isolates the seed writer.

### Quick grep — all time signals in one block

```bash
journalctl --user -u virgil-discord --since "10 minutes ago" --no-pager | grep -E "time_advance:|parse_elapsed:|state_footer:.*day=|directive_emit:.*time=1"
```

Should show every advancement, every parse attempt, every footer with day/phase, and every turn where the time directive fired non-empty.

### Test suites (offline)

```bash
cd /home/jordaneal/scripts && python3 -m pytest test_advance_time.py test_time_skeleton_seed.py test_time_schema_integrity.py test_state_footer.py test_render_state_footer_time.py -v
cd /home/jordaneal/scripts && python3 test_parse_elapsed.py
cd /home/jordaneal/scripts && python3 test_compute_time_directive.py
```

Expected: 89 pytest-runnable + 27 + 9 standalone = 125 (a subset; others run via the broader sweep).

### Promotion criteria — flip ROADMAP entry to ✅ SHIPPED LIVE when:

1. All 8 steps above complete without error in real Discord.
2. `time_advance:` log lines emit for `source=travel`, `source=rest_long`, `source=rest_short`, and `source=advance` (all four sources observed).
3. Footer correctly carries `· Day N, Phase` after every advancement.
4. `parse_elapsed:` handles at least three observed-during-play strings cleanly (no `result=none` for common DM phrases).
5. `/purgecampaign` cascades clean `dnd_time_advancements` rows for the test campaign.
6. No exception-path `time_advance: ... err=` lines in the logs from the verify pass.

---

## §S30 — Small-items batch (May 9, 2026)

Four new log-line shapes landed in this session. All four can be verified in one short Discord narration turn (one `/play` + one player action).

### Ship 1 — Bug 2: `cloud_router_finish_reason`

**Shape:**
```
cloud_router_finish_reason: provider={name} task={type} finish_reason={value} prompt_chars={N} response_chars={N}
```

**Fires:** Every successful cloud-provider call (not local Ollama). Fires on the happy path, not just on errors.

**Verify grep:**
```bash
journalctl --user -u virgil-discord --since "5 minutes ago" --no-pager | grep "cloud_router_finish_reason"
```

**Expected fields:** `provider=groq_heavy` (or whichever wins the DND priority override), `task=dnd`, `finish_reason=stop` on normal turns. `finish_reason=length` is the failure-mode signal — if it appears, the narration was truncated.

**Also verify:** max_tokens bump is active — DnD path no longer cuts at 1000 tokens. If `finish_reason=stop` is now seen where it used to be `length`, the fix is working.

---

### Ship 2 — F-29: titled-NPC regex

**What changed:** `_NAME_RE` in `npc_extractor.py` now passes "Garrik the Younger", "John of Stonebridge", "Marcus von Helder". No new log line — verify by introducing a titled NPC in narration and checking `npc_upsert: insert` fires (not `bad_name_format` rejection).

**Verify grep:**
```bash
journalctl --user -u virgil-discord --since "10 minutes ago" --no-pager | grep -E "npc_upsert: insert|bad_name_format"
```

**Expected:** Named NPCs with lowercase connectors (`the`, `of`, `von`, `de`, `da`, `der`) now reach `npc_upsert: insert`. `bad_name_format` rejections no longer appear for titled names.

---

### Ship 3 — S26 follow-up: `commitment_empty_response`

**Shape:**
```
commitment_empty_response: campaign={N} prompt_chars={N} fired=1 directive_chars={N}
```

**Fires:** Only when BOTH conditions hold in the same turn: (1) LLM returned empty/too-short narration (`dm_respond: EMPTY response from LLM` fires first), AND (2) commitment directive also fired that turn (`commitment_directive: ... fired=1`). Silent on non-empty turns and when commitment didn't fire.

**Verify grep (runs passively — fires only on the failure mode):**
```bash
journalctl --user -u virgil-discord --since "1 hour ago" --no-pager | grep "commitment_empty_response"
```

**Signal interpretation:** If this fires → commitment directive contributed to prompt bloat on an empty-narration turn. High rate over multiple sessions → investigate commitment directive prompt compression as the fix. Low/zero rate → empty narration has a different root cause.

---

### Ship 4 — Token-prefix fragmentation: `npc_token_prefix_match`

**Shape:**
```
npc_token_prefix_match: campaign={N} new='{new}' existing='{existing}' relation={prefix_to_full|full_to_prefix}
```

**Fires:** Only on `npc_upsert` INSERT branch, when the new canonical name and an existing canonical name are related by token-prefix: either the new name's full string equals the existing name's first token (`prefix_to_full`, e.g. new="Lira" existing="Lira Songheart"), or the new name's first token equals the existing name's full string (`full_to_prefix`, e.g. new="Lira Songheart" existing="Lira"). Silent on update branch. Silent when no token-prefix relationship exists.

**Verify grep:**
```bash
journalctl --user -u virgil-discord --since "1 session ago" --no-pager | grep "npc_token_prefix_match"
```

**Signal interpretation:** If this fires → bare-name vs full-name NPC fragmentation is occurring in the campaign. `prefix_to_full` = the bare form just got inserted alongside the full form; `full_to_prefix` = the full form just got inserted alongside the bare form. Human review: are these the same character? If yes, future auto-merge ship has real data to calibrate against.

---

### Verify 5 — Phantom-location channel: CLOSED

**Result (S30):** `set_current_location` has exactly one runtime caller in production code (`discord_dnd_bot.py:3123`, inside `/travel`). Journal from May 7–9 (since Track 7 #2 ship): every `set_current_location:` line is paired with a `/travel:` line — zero orphaned location writes. §17 single-write-path holds. ROADMAP item 11 dropped.

**No ongoing verification needed.** Channel is structurally closed.

---

### Quick S30 sweep grep

```bash
journalctl --user -u virgil-discord --since "30 minutes ago" --no-pager | grep -E "cloud_router_finish_reason|commitment_empty_response|npc_token_prefix_match|npc_upsert: insert"
```

---

## §S31 — ROADMAP 4c: First-session orientation pin in #commands

### Verify 1 — `/setup` posts the orientation pin (first run)

Run `/setup` in the test server. Check journal:

```bash
journalctl --user -u virgil-discord --since "5 minutes ago" --no-pager | grep "commands_pin\|setup_run"
```

**Expected:** `setup_run: ... commands_pin=create ...` and `setup: posted + pinned commands pin in #commands`. Pin appears in `#commands` with the five locked commands (`/play`, `/inventory`, `/refresh`, `/newcampaign`, `/dmhelp`) and the `#welcome` pointer.

---

### Verify 2 — `/setup` re-run is a no-op for the pin

Re-run `/setup` immediately. Check journal:

```bash
journalctl --user -u virgil-discord --since "2 minutes ago" --no-pager | grep "commands_pin\|setup_run"
```

**Expected:** `setup_run: ... commands_pin=noop ...`. No duplicate pin in `#commands`. Ephemeral says "Nothing to do — already canonical."

---

### Verify 3 — `/dmhelp` reads from COMMANDS.md (not hand-maintained prose)

Run `/dmhelp` from any channel. Confirm the response:
- Shows the Virgil slash commands section from COMMANDS.md
- Does NOT show the old "First-time player setup" / "DM commands" / "During play" prose headers from the replaced hand-maintained body

```bash
journalctl --user -u virgil-discord --since "2 minutes ago" --no-pager | grep "dmhelp\|commands_ref"
```

---

### Verify 4 — `/dmhelp` reflects live COMMANDS.md edits without restart

1. Edit any line in the Avrae section of `/home/jordaneal/virgil-docs/COMMANDS.md` (add a trailing comment or tweak a description)
2. Run `/dmhelp` WITHOUT restarting the bot
3. Confirm the edit is visible in the response

**Expected:** edit reflected immediately — no stale cache.

---

### S31 grep patterns

```bash
# One sweep for all S31 signals
journalctl --user -u virgil-discord --since "1 hour ago" --no-pager | grep -E "commands_pin|setup: posted|setup: replaced|setup: commands pin"
```

---

## Ship 1 — Resolution Binding (S34, May 11, 2026) — promotion verify

Spec source: `RESOLUTION_BINDING_SPEC.md` §13. Engine-bound DC-vs-roll resolution on the DM-typed-directive surface. Six scenarios A–F; A/B/D walked solo S34 and logged clean; C/E/F deferred per session notes (C is structurally identical to A/B via unit test, E requires a bound caster, F requires multiplayer — captured in `MULTIPLAYER_VERIFY_DEFERRED.md`).

**Solo-operator caveat:** Ship 1's load-bearing surface is the `!`-prefixed DM directive path. The directive intercept in `discord_dnd_bot.py:on_message` catches `!check`/`!save`/`!cast` from any DM-or-creator account BEFORE the player-bound-character check. Pure narration ("Donovan, you see...") from a Donovan-bound DM account does NOT route through the DM-directive path — it batches as the bound PC's player input. Only the `!`-prefixed flows exercise Ship 1's wiring.

### Verify A — Successful check resolution (PASSED branch)

In `#dm-narration`, DM types:

```
!check perception 10
```

Player (can be the same account if account is Avrae-bound to the rolling PC) types:

```
!check perception
```

**Expected:** bot auto-narrates within ~10s with success framing. Should NOT use "fails" / "can't" / "doesn't notice" / "stumble" language.

```bash
journalctl --user -u virgil-discord --since "5 minutes ago" | grep "directive_bound_to_footer_actor:" | tail -1
# Expect: ... skill=perception dc=10 directive_age_s=0

journalctl --user -u virgil-discord --since "5 minutes ago" | grep "directive_resolved:" | tail -1
# Expect: ... check_kind=check dc=10 roll_total=>=10 outcome=PASSED nat=<N> crit=0

journalctl --user -u virgil-discord --since "5 minutes ago" | grep "directive_would_fire_dm_respond:" | tail -1
# Expect: ... roll_total=<N> dc=10 outcome=PASSED

journalctl --user -u virgil-discord --since "5 minutes ago" | grep "verification:" | tail -1
# Expect: passed=1 violation_class=none (or passed=0 + retry_passed=1 if a retry was triggered)
```

### Verify B — Failed check resolution (FAILED branch + F-45 surface)

DM types:

```
!check perception 20
```

Player rolls:

```
!check perception
```

Wait for bot's failure narration. Then player optionally types:

```
I passed the check
```

**Expected:** bot's auto-narration narrates failure based on the AUTHORITATIVE-CANON block. The "I passed" follow-up message lands AFTER the auto-fired narration and goes through the normal player-input flow — the auto-fired narration is structurally committed and does NOT get rolled back. F-45 closed on the DM-typed-directive surface.

```bash
journalctl --user -u virgil-discord --since "5 minutes ago" | grep "directive_resolved:" | tail -1
# Expect: dc=20 roll_total=<low value> outcome=FAILED

journalctl --user -u virgil-discord --since "5 minutes ago" | grep "verification:" | tail -2
# Expect: violation_class=none (no ROLL_OUTCOME_DRIFT) for the auto-fired narration

journalctl --user -u virgil-discord --since "5 minutes ago" | grep "violation_class=roll_outcome_drift" | tail -3
# Expect: empty — zero drift violations for Ship 1's verify session
```

### Verify C — Save resolution (deferred unless live walk is desired)

DM:

```
!save dex 15
```

Player:

```
!save dex
```

```bash
journalctl --user -u virgil-discord --since "5 minutes ago" | grep "directive_resolved:" | grep "check_kind=save" | tail -1
# Expect: ... check_kind=save dc=15 outcome=PASSED|FAILED
```

Structurally identical to A/B with `check_kind='save'` instead of `'check'`. Covered at unit level by `test_resolve_save_kind_produces_same_shape`.

### Verify D — No-DC directive (graceful degrade per §11.2)

DM:

```
!check stealth
```

Player:

```
!check stealth
```

**Expected:** NO bot auto-narration on the stealth check. Existing free-narration flow proceeds when player types a follow-up action. The §11.2 lock behavior: no-DC directive skips resolution binding but still binds in Phase 1's sense (row created, age tracked, consumed on Avrae roll arrival).

```bash
journalctl --user -u virgil-discord --since "5 minutes ago" | grep "directive_resolution_skipped:" | grep "reason=no_dc" | tail -1
# Expect: campaign=<N> reason=no_dc

journalctl --user -u virgil-discord --since "5 minutes ago" | grep "directive_would_fire_dm_respond:" | tail -1
# Expect: ... dc=none outcome=skipped
```

### Verify E — Cast skip (deferred unless a bound caster is available)

Requires the rolling player's Avrae sheet to have an actually-castable cantrip or spell. Campaign 22's bound PCs (Dwarf Rogue + Half-Orc Barbarian) don't have cantrips at L1 — skip. When/if a caster gets bound, walk:

DM:

```
!cast guidance
```

Player:

```
!cast guidance
```

```bash
journalctl --user -u virgil-discord --since "5 minutes ago" | grep "directive_resolution_skipped:" | grep "reason=cast_kind" | tail -1
# Expect: campaign=<N> reason=cast_kind
```

Until then, unit test `test_resolve_returns_none_for_cast_kind` carries the structural coverage.

### Verify F — Multi-actor mismatch (deferred — needs multiplayer)

Requires two distinct Discord controller IDs typing inside the ActionBatcher window to produce a 2-actor footer. Solo-operator cannot exercise this surface from one account because pure narration from a PC-bound DM account routes to that PC's player flow (single-actor batch). Full walk specification + greps + failure modes captured in `MULTIPLAYER_VERIFY_DEFERRED.md`. When multiplayer is available, run that doc's §3 walkthrough and the aggregate greps in §7.

### Aggregate end-of-session sanity (post any Ship 1 verify pass)

```bash
SINCE="5 minutes ago"

echo "Resolved events:"
journalctl --user -u virgil-discord --since "$SINCE" | grep -c "directive_resolved:"

echo "Skip-reason breakdown:"
journalctl --user -u virgil-discord --since "$SINCE" | grep "directive_resolution_skipped:" | sed 's/.*reason=\([a-z_]*\).*/\1/' | sort | uniq -c

echo "Unretried drift violations (criterion 5 — must be 0):"
journalctl --user -u virgil-discord --since "$SINCE" | grep "violation_class=roll_outcome_drift" | grep "retry_passed=0\|retry_passed=-" | wc -l

echo "Unexpected co-occurrence (§2.3 canary — must be 0):"
journalctl --user -u virgil-discord --since "$SINCE" | grep -c "unexpected_binding_co_occurrence:"

echo "Auto-fire failures (must be 0):"
journalctl --user -u virgil-discord --since "$SINCE" | grep -c "_dm_respond_and_post_failure:"
```

If any of the last three counts move above 0, the promotion gate is breached — surface as HALT, investigate via the relevant module (`narration_verifier.py` for drift, `dnd_engine.py:build_dm_context` for co-occurrence, `discord_dnd_bot.py:_fire_resolution_narration` for auto-fire failures).

---

## Ship A — LLM-Emitted-Directive Resolution Binding (S36, May 11, 2026) — promotion verify

Spec source: `specs/LLM_EMIT_RESOLUTION_BINDING_SPEC.md` LOCKED v1. Engine-bound DC-vs-roll resolution on the **LLM-emitted-directive** surface (the primary 90% play loop). Ship 1 (S34) covered the DM-typed-directive secondary surface; Ship A closes the load-bearing case where the LLM emits `**!check skill DC : Name**` inside narration.

**Verify the primary play loop end-to-end:**

### Verify A — Natural-language intent triggers a roll

Operator types intent in #dm-narration (any of these; each routes to a different skill):

```
I look closely at the merchants
```
```
I try to find a missing detail
```
```
I lift the heavy crate
```
```
I dodge the falling rock
```
```
I creep up the stairs
```
```
I take a closer look at the room
```

**Expected:** Bot's narration ends with a single bold line `**!check <skill> : <First Name>**` — no DC visible to player.

Greps:
```bash
journalctl --user -u virgil-discord --since "5 minutes ago" | grep "llm_emit_directive_bound:" | tail -1
# Expect: campaign={N} actor={Donovan Ruby} skill={skill} dc={N} kind=check source_message_id={msg.id}
```

### Verify B — Avrae rolls; auto-fire fires textured outcome

After the bot's emit, Avrae rolls. Within ~6s, bot posts a second embed with the resolution narration — texture-scaled per difficulty, margin, stakes, and crit signal.

Greps:
```bash
journalctl --user -u virgil-discord --since "5 minutes ago" | grep "directive_resolved:" | tail -1
# Expect: outcome={PASSED|FAILED}, nat captured, crit flag captured

journalctl --user -u virgil-discord --since "5 minutes ago" | grep "stakes_tier:" | tail -1
# Expect: tier=low|medium|high with score breakdown

journalctl --user -u virgil-discord --since "5 minutes ago" | grep "verification:" | tail -1
# Expect: passed=1 violation_class=none
```

**Expected narration shape:** describes the actor's attempt, the outcome, and texture-appropriate detail (difficulty, margin, stakes). Nat 20 or nat 1 → memorable-element clause per §10.2.

### Verify C — Cascading-roll prevention

After auto-fire resolution narration posts, the bot should NOT emit another `!check` directive. The narration should end naturally without a new roll request. Next action waits for the operator's input.

If a second `!check` appears in the resolution narration, Patch 7 (sentinel detection) has regressed. HALT and investigate:
```bash
journalctl --user -u virgil-discord --since "5 minutes ago" | grep "directive_emit:" | tail -2
# The resolution-fire turn should show intent=meta or trivial in the prompt's classification (not exploration/combat/etc.)
```

### Verify D — DC preservation (manual !check echo)

If the operator manually types `!check perception` after the bot's emit (e.g. confused or habituated to manual rolls), the existing pending row's dc=N should NOT be clobbered to dc=none.

Grep:
```bash
journalctl --user -u virgil-discord --since "5 minutes ago" | grep "directive_preserve_existing_dc:" | tail -1
# Expect: campaign={N} actor={X} skill={Y} existing_dc={N}
```

If this log fires, Patch 4 worked — the manual `!check` echo was correctly recognized as a manual roll completing the auto-emit cycle (not a new directive replacement).

### Verify E — No-DC fall-through aside

If the LLM mis-emits `!check skill` without a DC, the matcher skips resolution and posts a `#dm-aside` to the operator.

Grep:
```bash
journalctl --user -u virgil-discord --since "5 minutes ago" | grep "directive_resolution_skipped:" | grep "reason=no_dc" | tail -1
# Expect: campaign={N} reason=no_dc
```

Operator sees `#dm-aside` text: `"Bot's roll request had no DC — resolution skipped. The outcome will be free-narrated on your next action..."`. Useful diagnostic when the LLM occasionally forgets to include a DC.

### Verify F — Format check (operator-confirmed S36)

Bot's emit format should be:
- Narrative beat (1-2 sentences) describing the actor's attempt
- Blank line
- `**!check skill DC : First Name**` — single bold line; DC stripped from player view; character first name after colon

Avrae rolls cleanly off the bold-wrapped form (confirmed S36 live walk). If Avrae stops rolling on bold-wrapped commands, fall back is post-emit unwrap (not Ship A's job — surface as v1.x ticket).

### Aggregate end-of-session sanity (post Ship A verify)

```bash
SINCE="20 minutes ago"

echo "Total LLM-emit binds:"
journalctl --user -u virgil-discord --since "$SINCE" | grep -c "llm_emit_directive_bound:"

echo "Total resolutions:"
journalctl --user -u virgil-discord --since "$SINCE" | grep -c "directive_resolved:"

echo "Outcomes:"
journalctl --user -u virgil-discord --since "$SINCE" | grep "directive_resolved:" | sed 's/.*outcome=\([A-Z]*\).*/\1/' | sort | uniq -c

echo "Stakes tier distribution:"
journalctl --user -u virgil-discord --since "$SINCE" | grep "stakes_tier:" | sed 's/.*tier=\([a-z]*\).*/\1/' | sort | uniq -c

echo "DC preservation events:"
journalctl --user -u virgil-discord --since "$SINCE" | grep -c "directive_preserve_existing_dc:"

echo "No-DC skips:"
journalctl --user -u virgil-discord --since "$SINCE" | grep "directive_resolution_skipped:" | grep "reason=no_dc" | wc -l

echo "Drift violations (must be 0 — criterion 5):"
journalctl --user -u virgil-discord --since "$SINCE" | grep "violation_class=roll_outcome_drift" | grep "retry_passed=0\|retry_passed=-" | wc -l

echo "Auto-fire failures (must be 0):"
journalctl --user -u virgil-discord --since "$SINCE" | grep -c "_dm_respond_and_post_failure:"
```

Promotion criteria per spec §15.9: ≥3 resolutions with mixed pass/fail, zero unretried drift violations, zero auto-fire failures, observable stakes-tier distribution.

### Solo-operator caveat for Ship A verify

Operator on a campaign where their Avrae binding matches the Virgil-side bound PC in `dnd_characters` (e.g., campaign 17 with Donovan Ruby in both). If Avrae rolls for Character X but Virgil's footer-actor is Character Y, the matcher's actor-mismatch path fires `_wrong_actor_aside` and the resolution doesn't fire. Operational fix: align Avrae binding via `!bindchar` OR switch to a campaign where the bindings agree.

---

## Ship 2 — Scene State Canon Discipline (S39, May 11 2026)

**Status:** SHIPPED LIVE. Live-verify scenarios A-D walk Doctrine §76 closure on the primary surface — `dnd_scene_state` LLM-write authority deleted on five §76 four-property fields + three dead-column housekeeping drops.

**Setup:** Run in any active campaign. Campaign 17 (Donovan Ruby) is the working solo campaign.

**Pre-walk discipline (per S38 review §4.3):** test against a **fresh campaign** (no pre-Ship-2 narration). Long-running campaigns may surface false-positive drift via residual chroma contamination from pre-Ship-2 LLM writes; that's an F-40-pattern artifact, closed only by a future chroma-layer audit ship.

### Scenario A — Location LLM-write attempt no-ops (Ship 2a, Path A)

**Discord prompt:**
```
I look around the merchant market carefully, taking in the stalls and faces.
```

**Expected:** bot narrates rich scene detail. No `scene_state.location` write fires (the column is gone). Next turn's prompt SCENE STATE block renders `Location: merchant market` (derived from `dnd_locations.canonical_name` via `current_location_id` FK). Cave-imagery drift is structurally impossible — there is no LLM-writable freetext location surface to recurse on.

**Failure signal:** location label flips to something invented or unrelated; or any subsequent narration introduces a location not in `dnd_locations`.

**Grep:**
```bash
grep -E "schema_migration: dropped dnd_scene_state\.|dropping LLM-write to deleted field 'location'" /mnt/virgil_storage/digest/dnd_engine.log | tail -10
```

### Scenario B — established_details / focus / open_questions / last_scene_change LLM-write no-ops (Ship 2b, 2c)

**Discord prompt:**
```
I scan the market for anyone watching, and note who's selling weapons versus food.
```

**Expected:** bot narrates observed details freely (whatever it wants — texture is fine). Subsequent turn's SCENE STATE block contains NO render lines for `Focus:`, `Established details:`, `Open questions:`, or `Last scene change:`. The LLM's memory of the scene flows from `last_dm_response` (verbatim prior narration) and skeleton-loaded canon, not laundered per-turn self-summary.

**Failure signal:** any of those four line prefixes appearing in the rendered SCENE STATE block.

**Grep:**
```bash
grep -E "dropping LLM-write to deleted field '(focus|established_details|open_questions|last_scene_change)'" /mnt/virgil_storage/digest/dnd_engine.log | head -10
```

### Scenario C — Cross-turn drift resistance (combined 2a+2b)

**Discord prompts (run 3 more freeform turns after A+B):**
```
I approach the weapons stall and ask about prices.
```
```
I check the alley between the stalls for shadows.
```
```
I weave back into the crowd, keeping my head down.
```

**Expected:** every turn renders SCENE STATE block with identical authored canon (`Location: merchant market`; no laundered-detail lines). LLM does not recursively elaborate on prior-turn fabrications because no scene_state field stores LLM-summarized prior fabrications.

**Failure signal:** in journal scroll-back across the 5 turns (A+B+3), any cave-imagery or contradictory-location phrase appears; OR any prior-narration detail elevates to "established canon" tone.

**Grep (post-walk):**
```bash
grep -E "Location: merchant market|Location: \(between locations\)" /mnt/virgil_storage/digest/dnd_engine.log | tail -10
```

### Scenario D — /travel-only authority on location (Ship 2a)

**Discord prompt:**
```
/travel
```

Pick a different known canonical location (e.g., one of `/locations list` entries).

**Expected:** `set_current_location` writes the new FK. Next turn's narration renders `Location: <new_location_label>`. LLM cannot bleed old location into new narration as "established" canon. The /travel command is the operator-driven write path.

**Failure signal:** old location name appears in new narration as canonical, OR location_label derive fails (renders `(between locations)` when FK is set).

**Grep:**
```bash
grep -E "set_current_location: campaign=" /mnt/virgil_storage/digest/dnd_engine.log | tail -5
```

### Scenario E — Schema migration idempotency (S38 D4 sanity, post-restart)

**Verify locally (no Discord needed):**
```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('/mnt/virgil_storage/virgil.db')
cols = sorted(row[1] for row in conn.execute('PRAGMA table_info(dnd_scene_state)'))
print('cols:', cols)
deleted = ['location', 'established_details', 'focus', 'open_questions', 'last_scene_change', 'active_npcs', 'active_threats', 'tension']
for c in deleted:
    assert c not in cols, f'{c} still present'
print('post-Ship-2 schema clean')
conn.close()
"
```

**Expected:** clean output listing the 12 post-Ship-2 columns; no AssertionError.

### Scenario F — Doctrine §76 four-property regression test (S38 D5 default)

**Verify locally:**
```bash
cd /home/jordaneal/scripts && python3 test_doctrine_76_four_property_audit.py
```

**Expected:** `32 passed, 0 failed`. Asserts (a) every `dnd_scene_state` column is classified in the test's `EXPECTED_CLASSIFICATION` table, (b) no column hits 4/4 properties post-Ship-2, (c) all 8 deleted columns are absent. If a future ALTER ADD introduces a 4/4 column, this test fails loud at commit time.

---

## Ship 3 — NPC State-Sync Boundary (S41, May 11 2026, post-in-session pivot to §1b suggester)

**Status:** SHIPPED LIVE post-pivot. Live-verify Scenario A walked clean (Case A path). Walking these post-session validates the projection helper's gates + telemetry + suggestion text format.

**Architectural context (S41 in-session pivot):** The originally-locked fix shape (bot-emit `!init opt` under proposed §65a narrow exception) was empirically blocked by Avrae's bot-filter — identical commands mutate state when human-typed and are silently filtered when bot-typed. Pivoted to §1b validated-suggester pattern: bot posts copy-paste block to `#dm-aside`; DM pastes; Avrae executes. The locked 3-line sequence is `!init remove <name>` + `!init add <init_mod> <name> -hp <hp>` + `!init opt <name> -ac <ac>` — `!init opt` cannot set max-HP, so the rebuild path is the only mechanically-complete fix.

**Setup:** Run in any active campaign with combat started (`!init begin`). Pick a fresh test NPC name with no prior history.

### Scenario A — Happy path (combatant added via `!init add` without stats, then `/hydrate` to suggest sync)

**Discord prompts:**
```
!init remove Test3A
!init add 5 Test3A
/hydrate npc:Test3A cr:1/4
```

**Expected:**
- Slash ephemeral: `"Hydrated Test3A at CR 1/4: HP 13, AC 13, Atk +3, Dmg 1d8. See #dm-aside for the Avrae sync paste."` (OR "Mid-combat re-hydrate — see #dm-aside for HP-reset warning + paste." if Test3A had numeric HP at the time).
- `#dm-aside` posts 3-line code block with `!init remove Test3A`, `!init add 1 Test3A -hp 13`, `!init opt Test3A -ac 13`.
- DM pastes each line separately in `#dm-narration`.
- Avrae responds: "removed", "added with initiative 1d20 + 1 = N", "AC set to 13".
- `!init list` shows `Test3A <13/13 HP> (AC 13)`.

**Failure signal:** `<None>` or `<N/0 HP>` (max-HP not set); AC shows 0; bot emits commands to `#dm-narration` instead of `#dm-aside`.

**Grep:**
```bash
grep -E "avrae_projection_(attempted|succeeded|skipped|failed)" /mnt/virgil_storage/digest/dnd_engine.log | tail -20
```

### Scenario B — Multi-player (deferred to `MULTIPLAYER_VERIFY_DEFERRED.md` if Captin0bvious unavailable)

Same flow as A, but Captin0bvious attacks the hydrated Test3A from their PC. Verify Avrae resolves both PCs' attacks against the same combatant with full HP tracking.

### Scenario C — Idempotency (re-/hydrate already-synced NPC)

After Scenario A with Test3A at `<13/13>`:
```
/hydrate npc:Test3A cr:1/4
```

**Expected:** Ephemeral confirms "Mid-combat re-hydrate — see #dm-aside for HP-reset warning + paste." `#dm-aside` posts the WARNING variant with combat-state-loss explicit + 3-line rebuild + partial-fix alternative. DM can choose to paste or ignore.

**Failure signal:** Bot silently re-projects without warning; Avrae state changes without DM consent.

### Scenario D — Case B passive trigger preserves mid-combat HP

With Test3A at `<13/13>`, damage:
```
!init hp Test3A -3
```
Triggers Avrae `!init list` event implicitly (or run `!init list` explicitly). `_handle_init_list_event` parses; finds Test3A at numeric HP; trigger='init_list' (passive). 

**Expected:** NO `#dm-aside` suggestion posted. Avrae's `<10/13 HP>` mid-combat state preserved. Journal log: `avrae_projection_skipped: ... reason=noop_complete`.

**Failure signal:** Bot posts re-projection suggestion despite Avrae having authoritative mid-combat state.

**Grep:**
```bash
grep "reason=noop_complete" /mnt/virgil_storage/digest/dnd_engine.log | tail -5
```

### Scenario E — Engineer-only failure path (optional)

Disable `#dm-aside` (rename or permissions) and run `/hydrate`. Bot should log `avrae_projection_failed: ... reason=aside_post_failed`. Engine row stays canonical. Re-enable channel; next trigger retries.

### Scenario F — Schema regression (no Ship 3 schema changes, but verify dnd_npcs audit clean)

```bash
cd /home/jordaneal/scripts && python3 test_avrae_project_npc.py
```
**Expected:** `13 tests passed.`

### Cleanup

```
!init remove Test3A
!init end
```

---

## S42 — Listener Edge-Case Verification (May 11, 2026)

**Status:** SHIPPED LIVE. Pre-playtest infrastructure ship; `avrae_listener.py` audited and two structural parsing gaps patched. Walking these post-session validates the listener still parses Avrae's combat embed vocabulary correctly.

### Unit-test coverage

```bash
cd /home/jordaneal/scripts && python3 test_avrae_listener_edge_cases.py
```

**Expected:** `7 tests passed.` Covers plain attack baseline + advantage (`2d20kh1`) + disadvantage (`2d20kl1`) + resistance damage (`(N [type]) / 2 = K` shape) + multi-target attack (per-target `attacks` list surfacing) + single-target back-compat guard + crit keyword detection.

### Listener-adjacent regression sweep

```bash
for t in test_avrae_sweep test_init_list_parser test_avrae_project_npc test_hydration_hook test_pending_roll_directives test_llm_emit_writer; do
  python3 "$t.py" 2>&1 | grep -E "passed|failed" | tail -1
done
```

**Expected:** all green (11 + 29 + 13 + 20 + 27 + 23 = 123 assertions across 6 files).

### Live verify (optional) — exercise the patched paths against live Avrae

Run in any campaign with combat active (`!init begin`). Add two NPCs for multi-attack target diversity:

```
!init add 5 TestA -hp 13
!init opt TestA -ac 13
!init add 8 TestB -hp 13
!init opt TestB -ac 11
```

Then walk:

```
!attack unarmed strike -t TestA adv
```
**Expected log:** `listener_parsed: kind=attack ... nat=<kept-high> result=<final> ... subattacks=1`

```
!attack unarmed strike -t TestA dis
```
**Expected log:** `listener_parsed: ... nat=<kept-low>` (lower of the two dice).

```
!attack unarmed strike -t TestA -t TestB
```
**Expected log:** `listener_parsed: ... subattacks=2` — confirms both target fields captured.

**Grep:**
```bash
grep "listener_parsed:" /mnt/virgil_storage/digest/dnd_engine.log | tail -10
```

### Deferred edge cases (filed for future ship)

These require fixtures S42 didn't have available:
- **Forced critical hit:** Avrae's `-crit` flag did NOT force a crit in S42 verify (rolled nat 1, missed). Needs alt trigger path investigation OR natural-20-from-many-rolls approach.
- **Save with halved damage** (fireball-style): requires a spellcaster PC fixture (Donovan Ruby has no spells in test campaign).
- **Death save outcome state** (success/fail/stabilize/death): `!init dsa` syntax + Avrae's PC-required gate blocked single-player verification. Requires throwaway PC at 0 HP.

Crit keyword detection (`_CRIT_RE`) itself is verified clean via the unit test; only the forced-crit-trigger path is unverified. When fixtures become available, file a small follow-up ship to close these.

### Cleanup

```
!init remove TestA
!init remove TestB
!init end
```

---

## S43 — Dumb Combat Narration (May 11, 2026)

**Status:** SHIPPED LIVE. Auto-narration on three combat-mode state transitions (ROUND_START + BLOODIED_THRESHOLD_CROSSED + COMBATANT_DOWNED) via `_dm_respond_and_post`'s `transition_context`. Atmospheric-vs-adjudication doctrine (§77) anchored. Walking these post-session re-verifies the cliff-edge holds + telemetry fires.

### Unit-test coverage

```bash
cd /home/jordaneal/scripts && python3 test_combat_narration.py
```

**Expected:** `39 tests passed.` Covers `_hp_state` boundaries, `compute_combat_state_transitions` edges, `compute_combat_narration_directive` mode-gate + sentinel action + categorical labels + MUST/MUST-NOT invariants verbatim + trigger-specific framing, `combat_narration_log_summary` telemetry shape.

### Combat-adjacent regression sweep

```bash
for t in test_avrae_listener_edge_cases test_avrae_project_npc test_avrae_sweep test_init_list_parser test_hydration_hook test_pending_roll_directives test_llm_emit_writer test_compute_stakes_tier test_resolve_directive test_state_footer test_combat_redirect_directive test_render_state_footer_time; do
  python3 "$t.py" 2>&1 | grep -E "passed|failed" | tail -1
done
```

**Expected:** all green (~238 assertions across 12 files).

### Live verify (in any campaign)

Setup:
```
!init begin
!init add 3 TestS43 -hp 13
!init opt TestS43 -ac 11
!init join
!init next
```

**Watch for:** auto-narration in `#dm-narration` after `!init next` triggers round 1. Look for environmental atmosphere (lighting/sound/tension), NOT specific PC actions. Journal: `combat_narration_fired: kind=ROUND_START fired=1`.

Then bloodied:
```
!init hp TestS43 -7
```
**Watch for:** auto-narration with combatant faltering / staggering framing. NO phantom NPCs from `recent_npcs`. NO "about-to-fall" language. Journal: `combat_narration_fired: kind=BLOODIED_THRESHOLD_CROSSED name='TestS43' fired=1`.

Then downed:
```
!init hp TestS43 -10
```
**Watch for:** auto-narration with "out of the fight" / "unconscious" framing. NO death declaration. Journal: `combat_narration_fired: kind=COMBATANT_DOWNED name='TestS43' fired=1`.

Cleanup:
```
!init end
```

**Critical cliff-edge check (the doctrine line):** scrutinize all three narrations for ANY of:
- Speculative outcomes ("about to fall", "near death", "doomed")
- Invented damage numbers / attack outcomes
- Inferred enemy morale ("the goblin's resolve breaks")
- Tactical commentary ("a clear opening", "the best target")
- Declaring death without listener confirmation
- Narrating action that didn't happen this round
- Future-round projection ("next round will be brutal")

If ANY surface, the §77 doctrine line is failing — file as priority bug.

### Known v1.x candidate: ROUND_START prompt purity

ROUND_START narrations may surface phantom NPCs (from `recent_npcs` block) and stale-narrative bleed (from `last_dm_response` block). These are storytelling-quality drift, NOT doctrine drift (§77 holds — no mechanical-state-mutation inference). Filed as worktree task chip; three fix options under evaluation.

**Grep for combat-narration telemetry:**
```bash
grep "combat_narration_fired:" /mnt/virgil_storage/digest/dnd_engine.log | tail -10
```

### Deferred trigger: DEATH_SAVE_EVENT_START

Filed as small follow-up ship; v1 ships with three active triggers. S42 fixture blocker (`!init dsa` syntax + Avrae's PC-required gate) prevents single-player verification. When a throwaway PC at 0 HP fixture becomes available, follow-up ship adds the trigger via the parse path S42's deferred work would have established.

---

## S44 — Combat Narration Prompt Purity v1.x (May 11, 2026)

**Status:** SHIPPED LIVE. S43 filed-follow-up. Information-side suppression of 10 prompt blocks during combat narration. Walking these post-session re-verifies the suppression set holds + telemetry fires.

### Unit-test coverage

```bash
cd /home/jordaneal/scripts && python3 test_combat_narration_prompt_purity.py
```

**Expected:** `17 tests passed.` Covers each of the 10 suppressed blocks (drops under True, preserves under default False) + scene-state-preserved + combat-directive-blocks-preserved + two-layer enforcement composition.

### Live verify (in any campaign)

Setup:
```
!init begin
!init add 3 TestS44Goblin -hp 13
!init opt TestS44Goblin -ac 11
!init join
!init next
```

**Watch for:** auto-narration after `!init next` triggers round 1. Expected output shape:
- Atmospheric round-top beat (environment / lighting / sound / tension)
- Two-figure roster focus (PC + the single test goblin)
- NO phantom NPCs (Lira / Borin / Eldrin / etc. — even if they exist in the campaign companions table, they MUST NOT appear)
- NO stale narrative bleed (no references to prior combats; no carry-over prose from `campaign.current_scene` rolling buffer)
- Turn handback per init order

**Critical regression checks (failure signals):**
- ANY phantom NPC name in the narration → companions / recent_npcs suppression failed
- ANY mention of prior turn's narrative content → current_scene rolling buffer suppression failed
- ANY combat-style language from FIREBALL/CRD3 corpus (specific monsters not in this game's roster) → chroma blocks suppression failed
- ANY quest title or campaign-arc reference → quests / central_thread suppression failed

**Journalctl signals:**
```bash
grep "reason=combat_narration_suppressed" /mnt/virgil_storage/digest/dnd_engine.log | tail -5
```

This `npcs_in_context: ... reason=combat_narration_suppressed` log line fires once per dispatch when the suppression branch is taken. If absent, the dispatch isn't passing True (wiring bug).

### Default-path regression sweep

Non-combat callers (exploration narration, /travel, resolution-binding narration, etc.) must continue to receive ALL 10 blocks. Walk:

```
/travel
```

Pick any location. Then any non-combat narration turn (player narrates an action in `#dm-narration`):

```
I look around the tavern.
```

**Expected:** standard non-combat narration with full context — recent NPCs may appear, prior narrative context flows naturally, quests/inventory/etc. all present. If non-combat narration also drops these blocks, the S44 wiring is over-suppressing.

### Doctrine candidate observation

S44 filed `§77 two-layer enforcement composition` as a doctrine candidate (instruction-side MUST/MUST-NOT + information-side context-block suppression). Anchors on second instance. **S45 promoted this to §78 mode-transition state-reset surfaces** (third project instance: S43 + S44 + S45). The pattern is now anchored; future ships in the F-55 cluster (#5.2 NPC Turn Automation, #5.4 Intent-to-Avrae Resolver) and any other mode-transition handler inherit the four-layer audit at design time.

---

## S45 — Combat-Boundary Hardening Bundle (post-`!init end` buffer reset + init-setup silence gate + COMBAT_END auto-closeout) ✅

**Scope:** Three-surface boundary closure shipped May 11, 2026.

### Test files added (33 new assertions across 3 files)

```bash
cd /home/jordaneal/scripts
python3 test_init_end_buffer_reset.py          # 10 assertions (Surface C)
python3 test_init_setup_suppression.py         # 13 assertions (Surface D v1 + v2)
python3 test_combat_narration_combat_end.py    # 10 assertions (Surface F)
```

All must report `All N assertions pass.`

### Full S43/S44/S45 regression sweep

```bash
cd /home/jordaneal/scripts
for f in test_combat_narration.py test_combat_narration_prompt_purity.py \
         test_init_end_buffer_reset.py test_combat_narration_combat_end.py \
         test_init_setup_suppression.py test_combatant_state.py \
         test_avrae_listener_edge_cases.py; do
  echo "=== $f ==="
  python3 "$f" 2>&1 | tail -2
done
```

Expected totals: 39 + 17 + 10 + 10 + 13 + 15 + 7 = **111 assertions green**.

### Surface C verify (post-!init end exploration)

In a clean test campaign with combat active:

```
!init end
```

After Avrae confirms, send any RP message:

```
Donovan looks around the room.
```

**Expected:** atmospheric exploration narration starting from clean slate. No combat framing, no phantom combatants from prior init list, no continued tension. Journal: `init_end_buffer_reset: campaign=N`.

### Surface D v2 verify (init-setup silence)

Start combat with a monster-add that triggers Avrae's disambiguation prompt:

```
!init begin
```

```
!init madd SomeAmbiguousMonsterName -hp 12 -ac 13
```

When Avrae's "Multiple Matches Found" prompt appears (in DM), reply in #dm-narration with the disambiguation number:

```
2
```

**Expected:** ⏳ reaction on the `2` message, NO Virgil DM narration during init setup, journal log `init_setup_gate: dropped msg from <user_id> (mode=combat, no active_turn — Avrae setup phase)`.

### Surface F verify (COMBAT_END auto-closeout)

After running at least one round of combat, end:

```
!init end
```

**Expected within 1-3 seconds:** Virgil auto-fires a 2-3 sentence atmospheric closeout. Journal: `combat_narration_fired: kind=COMBAT_END fired=1`. Closeout must NOT introduce new combatants/NPCs not on the closing roster, must NOT narrate post-combat decisions, must NOT preview next moves.

### Integration verify (C+D+F arc)

Full combat lifecycle:

```
!init begin
```

```
!init join
```

```
!init next
```

(ROUND_START should fire — clean atmospheric hush)

```
!init end
```

(COMBAT_END should auto-fire — clean closeout)

```
Donovan takes a long pull from his ale.
```

(Clean exploration response — no combat framing, atmospheric exploration tone)

All three narrations atmospheric, no phantoms, no continued combat.

### Drift signals to grep

```bash
journalctl --user -u virgil-discord --since "5 minutes ago" -o cat | \
  grep -E "init_end_buffer_reset|init_setup_gate|init_setup_suppression|combat_narration_fired"
```

Expected log sequence on a full combat cycle:
```
combat_narration_fired: kind=ROUND_START fired=1
init_end_buffer_reset: campaign=N
init: combat ended (guild=...) → mode='exploration', combat state cleared
combat_narration_fired: kind=COMBAT_END fired=1
```

### Failure modes from S45 verify history

- **v1 fix only (suppress context but stay responsive)** — phantom companions absent but bot still generates premature combat narrative from bare disambiguation reply. Requires v2 top-level gate.
- **No buffer reset** — next exploration message reads polluted `current_scene` rolling buffer, model generates locally-coherent combat continuation ("the thug snarls" appearing in an exploration scene).
- **No COMBAT_END dispatch** — bot stays silent on !init end; play flow breaks because player must seed next narration before any DM voice surfaces.
- **Mode-gate failure on COMBAT_END** — without `scene_override={'mode': 'combat'}`, dispatch fires AFTER mechanical mode flip to 'exploration', mode gate in `compute_combat_narration_directive` rejects with empty action+context.

### Filed follow-ups (not S45 scope — surface for future ships)

- **COMBAT_END framing on 0-action combats** — LLM speculated "clash of steel / blows died away" on a verify with no actual combat actions. Creative-writing tuning, not structural drift.
- **`(1 roll in play)` footer post-!init end** — Donovan's initiative roll persists in RollBuffer after `!init end` clears mechanical state. Orthogonal buffer-drain.
- **Phantom companions in `dnd_companions` DB rows** — Lira/Borin/Eldrin are real rows from past `npc_extract` LLM writes. Database-hygiene issue, surfaces in any exploration-mode prompt that renders the companions block.
- **`_handle_rest_event` !lr/!sr parallel surface** — also flips combat→exploration but via a different listener path; doesn't currently call `reset_narrative_buffers_on_combat_exit`. Per §78 layer audit, this surface is structurally incomplete.
- **Avrae end-of-combat report routing to DM instead of channel** — Avrae config (`!cvar` or `personal` flag), not Virgil bot code.
