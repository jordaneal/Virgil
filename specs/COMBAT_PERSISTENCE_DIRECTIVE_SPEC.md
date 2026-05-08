# Combat Persistence Directive — Design Spec v1 (DRAFT)

**Status:** SPEC ONLY — pre-review. §1 lists *proposed* decisions; §11.A LOCKED to option (ii) per Jordan's call (2026-05-04 review session) — full per-combatant data layer fed by `!init list` parsing. Other §11 points still open. §12 added for stale-combatant disposition.
**Pattern:** Tactical directive layer — same shape as pacing, central thread, consequence, commitment, init.
**Track:** Track 3 (directive layer) / pre-friends gating ship #3 — addresses three combat-side bridge-layer failure modes Jordan flagged across recent play.
**Sibling specs:** `COMMITTED_ACTION_RESOLUTION_SPEC.md` (escape failure mode, shipped S19), `COMBAT_INITIATION_ORCHESTRATION_SPEC.md` (binding failure mode, shipped S20). Together with this spec, the three siblings close all four sub-layers of the bridge between Avrae mechanics and LLM narration on combat-adjacent turns.
**Failure modes this targets (three bundled concerns, single directive):**
1. **Enemy persistence.** The LLM narrates a fight as resolved while Avrae shows combatants alive. "The bandits scatter into the night" lands while `!init list` shows them at full HP. Combat dismissed by narrative declaration; mechanical state still wants resolution.
2. **Condition awareness.** The LLM narrates around an active condition. Player is mid-combat with a `frightened` token; LLM narrates a confident rallying cry. Avrae knows the condition; the prompt-side state doesn't surface it; narration drifts from mechanical truth.
3. **Initiative-order enforcement.** Avrae has an active turn controller; player B (whose turn it is NOT) types an action; the LLM narrates B's action as occurring in-sequence. Turn order — the most immediate "choice matters now" lever 5e gives — silently dissolves.

These three failures share a common shape: **mode=='combat', mechanical state is authoritative, narration drifted away from it.** They share a single directive at the bridge layer.

---

## 1. Proposed decisions (NOT yet locked — see §11)

These are what I'd propose if the spec went straight to implementation. Every one is up for change in review.

1. **Single directive, three composable sub-pressures.** `compute_persistence_directive(...)` returns one combined constraint string covering enemy persistence + condition awareness + initiative-order enforcement. NOT three separate directives. Same advisory shape as commitment/init/consequence — single block, sub-paragraphs as the gates fire.

2. **`mode == 'combat'` is the master gate.** When mode is exploration / social / travel / downtime / unset, directive returns `''`. Explored alternatives (firing on `intent_current == COMBAT` even outside combat mode) overlap with the init directive's territory and would double-fire on commit turns. Persistence is the *during-combat* layer; commit-turn binding stays with the init directive.

3. **Three sub-pressures, composed independently when mode='combat':**
   - **Enemy persistence.** Always fires when mode='combat'. Body: "Avrae owns HP. Combat is active. Do NOT narrate the encounter wrapped, the enemies fled, or the fight resolved — fights end via `!init end`, never via narrative declaration. If you believe the encounter is resolving, surface that posture (enemies broken, surrendering, etc.) and stop short of authoring the close." NO per-creature HP tracking in v1.
   - **Condition awareness.** Always fires when mode='combat'. Body: "Avrae shows active conditions in `!init list` and `!status` outputs. Honor any condition currently visible — frightened cannot rally, grappled cannot move, paralyzed cannot act, etc. Do not narrate around or through a condition the mechanical state has set." Generic — does NOT enumerate per-creature conditions because v1 does not extract them (see §11.A).
   - **Initiative-order enforcement.** Fires when mode='combat' AND `get_active_turn(...)` is populated AND the typing player's identifier is known. Body: "It is currently {character_name}'s turn (Discord controller {controller_id}, round {round}). The current message comes from {typing_actor}. {Acknowledgment vs off-turn pressure depending on match.}" When typing matches controller: confirm-only flavor ("narrate from {character_name}'s frame"). When typing differs: imperative ("acknowledge the turn order; do not author the off-turn action as if it were occurring in-sequence — name the wait, the cue, or the held action").

4. **Directive-only, no hard gates at message-receive.** Bot stays read-only on Avrae channel and stays narration-only on `#dm-narration`. No on_message dropping of off-turn input, no rejecting messages from non-active controllers. If Jordan wants a hard gate later, that's a separate slash-command or bot-side ship under a separate spec.

5. **Active turn controller comparison is multiplayer-aware.** `controller_id` is a Discord user ID (string). The caller (`dm_respond`) passes the typing user's Discord ID + their resolved character name (already done upstream via Phase 6 `resolve_actor`). The directive compares `message.author.id` to `controller_id`. Solo case: always equal, turn-order pressure becomes confirm-only flavor. Multi-PC case: comparison is meaningful.

6. **Failure mode for missing inputs: silent skip per sub-pressure.** If `scene_state` is None: full-silent. If mode is not 'combat': full-silent. If mode='combat' but `active_turn` is None (init begin fired, no turn cycle yet): enemy-persistence + condition pieces fire; turn-order piece silent. If active_turn is populated but the caller didn't pass typing_actor info: emit turn-order naming the active controller without the comparison clause.

7. **NEW SCHEMA — `dnd_combatant_state` table.** Per-combatant HP / conditions / alive state, replace-in-place per `!init list` snapshot. Read by directive, written by a new parser branch on `!init list` plaintext. Existing reads (`scene_state.mode`, `get_active_turn`, caller-provided typing identity) all retained. Schema definition in §4; parser detection in §5.6; write path in §5.7. See §11.A for the data-source decision (LOCKED to option (ii) — full data layer).

8. **Composition order: AFTER commitment, last in tactical band.** Renders as `=== COMBAT PERSISTENCE ===` block. Same band as pacing/central_thread/consequence/commitment. Persistence is the most-immediate-stakes constraint when in combat — anchors the end of the band, last impression before HARD STOP RULES. Mirrors the directive_emit reserved-field convention from S18 (commitment) → S20 (init).

9. **Telemetry shape.** Single per-turn aggregate `persistence_directive:` log line, fires every turn (regardless of fire status, regardless of mode), for empirical baseline. Fields:
   - `campaign={N}`
   - `combat_active={1|0}` — `1` iff mode=='combat'
   - `hp_known={1|0}` — `1` iff `dnd_combatant_state` has any rows for this campaign with non-null `hp_max`
   - `conditions_known={1|0}` — `1` iff `dnd_combatant_state` has any rows for this campaign with non-empty `conditions`
   - `combatants={N}` — count of rows in `dnd_combatant_state` for this campaign
   - `snapshot_age_s={N|none}` — seconds since last `updated_at` across `dnd_combatant_state` rows; `none` if no rows. Surfaces stale-snapshot risk (§12)
   - `active_turn_controller={controller_id|none}` — Discord user ID of active controller, or `none` when no active turn
   - `fired={1|0}` — `1` iff any sub-pressure rendered text
   Mirrors `commitment_directive:` and `init_directive:` shapes. `hp_known` / `conditions_known` are now live signals (option (ii) lock) — the reserved-field placeholder pattern would have applied if v1 had stayed at directive-only (the original §1.7); with the data layer landing in v1 they ship as observable telemetry from day one.

10. **`directive_emit:` extension.** Add `persistence={1|0}` to the existing per-turn aggregate. Slot ordering becomes `pacing=... central_thread=... philosophy=... consequence=... capability=... commitment=... init=... persistence=...`. Reserved slot for future-v2 numeric fields stays separate (`persistence_directive:` line is the tunable surface, not `directive_emit:`).

11. **PC-only scope.** "Enforce turn order on PC actions." The bot only reads PC messages from `#dm-narration`. NPC turns (Avrae-controlled, narrated by the LLM) have no player-typed message to gate. NPC-side turn order pressure (do not narrate the goblin acting before the goblin's initiative slot) is filed for a future ship, not v1.

---

## 2. Goal — which THE_GOAL bullets this serves

Direct hits:

- ✅ **"I want combat to be fun. I want to feel something when I kill an enemy."** Combat that gets dismissed by narrative declaration ("the bandits flee into the night" while Avrae shows them at 22/22 HP) makes the kill weightless. Persistence pressure forces the LLM to honor what's mechanically alive — which is the precondition for any "I just killed something" moment to land.
- ✅ **"Failure should create story, not dead ends."** When the LLM narrates an unresolved fight as wrapped, the failure-as-story option (you tried to rally but conditions held; you tried to leave but the bandit's turn came up) is foreclosed. The encounter just disappears. Persistence pressure keeps the unresolved possibilities live.
- ✅ **"Choices should matter later, not just in the moment."** Turn order is the most immediate "in the moment" mattering 5e gives. The action you take *during your turn*, in the order initiative dictates, is THE place choice has weight. Ignoring it makes commitment costless.
- ✅ **"Player agency has to survive the AI."** Inverse case: when Player B types an off-turn action and the LLM narrates it as in-sequence, Player A's *committed* turn-order priority is silently undone. Agency degraded by infrastructure.
- ✅ **"NPCs we wronged should still be wronged."** Adjacent: NPCs who are mechanically alive (Avrae shows them at 1/22 HP, prone, frightened) still have presence the world should honor. Narration that wraps the encounter erases that presence.

Indirect hits:

- **"If failed rolls just stop play instead of changing the situation, we've failed."** Adjacent. A failed save against a `frightened` condition is not a dead end if narration honors the condition; it's a story. The condition-awareness sub-pressure exists exactly to keep that loop closed.

Bullets v1 explicitly does NOT serve:

- **"If players come up with a creative solution and the system forces them back to the 'right' path, we've failed."** TENSION. The directive must NOT prevent players from creative responses to their turn ("I throw my dagger into the river," "I try to talk the bandit down mid-fight"). The directive's strength is on **dismissing** combat narratively, **honoring** conditions, and **respecting** turn order — not on dictating WHAT the player does on their turn. §11.D and §6.1's body wording carry the calibration weight.
- **"The world should reward curiosity."** Different mechanism (knowledge tier).

---

## 3. Architecture pattern

### Where it sits

```
                Player message arrives in #dm-narration
                              │
                              ▼
              scene_state = get_scene_state(campaign_id)
                              │
                              ▼
              intent = classify_action_intent(text, mode)
                              │
                              ▼
              roll_decision = should_call_roll(intent, mode, ctx)
                              │
                              ▼
              [pacing / central_thread / consequence / commitment / init
               directives compute as today]
                              │
                              ▼
              ┌──────────────────────────────────────────────┐
              │  compute_persistence_directive(              │
              │      mode=scene_state['mode'],               │
              │      active_turn=get_active_turn(camp_id),   │
              │      typing_user_id=...,                     │
              │      typing_character_name=...,              │
              │  ) -> (str, signals_dict)                    │
              └──────────────────────────────────────────────┘
                              │
                              ▼
              pass into build_dm_context as new
              persistence_directive=... kwarg
                              │
                              ▼
              renders as === COMBAT PERSISTENCE === block,
              AFTER === UNRESOLVED COMMITMENT === in tactical band
                              │
                              ▼
                       LLM narration
```

### What's new

- **New schema:** `dnd_combatant_state` table (per-combatant HP / conditions / alive). Definition in §4. Migration is forward-only (CREATE TABLE IF NOT EXISTS).
- **New parser branch in `avrae_listener.py`:** `parse_init_list_embed(text) -> dict | None`. Pure regex, no LLM. Detection in §5.6.
- **New write path in `dnd_engine.py`:** `update_combatants_from_init_list(campaign_id, parsed)` (REPLACE-style; clears old rows for campaign, writes parsed rows in one transaction) and `clear_combatants(campaign_id)` (called from `_handle_init_event` on `init_event=='end'`). Single-writer invariant — only the listener calls these. §5.7.
- **New read helper in `dnd_engine.py`:** `get_combatants(campaign_id) -> list[dict]` — returns rows ordered by `init` desc, plus latest `updated_at`. Read-only; consumed by directive.
- **One new directive function** in `dnd_orchestration.py`: `compute_persistence_directive(...) -> (str, signals_dict)`. Now consumes `combatants` list from the read helper.
- **One new helper:** `persistence_log_summary(signals)` — mirrors `commitment_log_summary` and `init_log_summary`.
- **One new kwarg** on `build_dm_context`: `persistence_directive=""`.
- **One new render block:** `=== COMBAT PERSISTENCE ===`.
- **One new per-turn log line:** `persistence_directive:` (always-fires diagnostic, mirrors `commitment_directive:` shape).
- **One new field** on the existing `directive_emit:` line: `persistence={1|0}`.
- **New test file:** `test_persistence_directive.py` — gate-isolation + composition + multi-PC turn-order cases.
- **New test file:** `test_init_list_parser.py` — parser fixtures (the `<None>` shape we have samples for; format-unknown cases will be added when real-combat samples surface, see §5.6).
- **New test file:** `test_combatant_state.py` — schema + write-path + read-helper + clear-on-end behavior.

### What's reused

- `scene_state.mode` — already authoritative, already read by every directive in the band.
- `get_active_turn(campaign_id)` — already deterministic, returns `None` when no `!init turn` event has fired since the last `clear_active_turn`. Same accessor the init directive uses.
- The directive composition pattern (`build_dm_context` kwarg + render block + `directive_emit:` slot).
- Phase 6 actor resolution — `dm_respond`'s caller (or `dm_respond` itself, per §11.F) supplies the typing user's Discord ID and resolved character name. Already wired in `discord_dnd_bot.on_message` for actor-resolution writes; this spec consumes the same data.
- `_handle_init_event` mode-flip + `clear_active_turn` cleanup — when `!init end` fires, mode flips to exploration AND active_turn clears, directive silently skips next turn. No new cleanup needed (see §11.G).

### What's NOT changed

- `set_scene_mode` semantics — mode still flips ONLY on Avrae's deterministic events (init begin/end, rest), `/mode`, `/play` preset, AUTO_EXECUTE.
- `dnd_combat_state` schema — read-only from this directive's perspective. No new columns. (The new `dnd_combatant_state` table is a separate, sibling table; existing combat-state semantics untouched.)
- The init directive — operates on commit-turn, doesn't overlap with this directive's during-combat scope.
- The commitment directive — operates on escape-turn, doesn't overlap.
- HARD STOP RULES — persistence directive lives in tactical band, hard stops still rule above it.
- Avrae's existing parsed event types (`begin`, `add`, `turn`, `end_prompt`, `end`, plus rest events) — `parse_init_event` keeps its current contract. The new `parse_init_list_embed` is a SEPARATE function with a different return shape; it does NOT replace or extend `parse_init_event`.

---

## 4. Data model

### 4.1 Existing reads (unchanged)

- `dnd_scene_state.mode` — master gate.
- `dnd_combat_state` (via `get_active_turn(campaign_id)`) — single-row query returns `{controller_id, character_name, round, updated_at}` or `None`. Authoritative for "whose turn is it."
- Caller-supplied `typing_user_id` (string, Discord user ID) and `typing_character_name` (canonical PC name resolved upstream). Both already known at the `dm_respond` call boundary.

### 4.2 New schema — `dnd_combatant_state`

```sql
CREATE TABLE IF NOT EXISTS dnd_combatant_state (
    campaign_id   INTEGER NOT NULL,   -- FK conceptually to dnd_campaigns.id (no enforced FK; matches existing tables)
    name          TEXT    NOT NULL,   -- canonical name from !init list, exact case preserved
    init          INTEGER NOT NULL,   -- initiative value
    hp_current    INTEGER,            -- nullable — null when Avrae renders <None>
    hp_max        INTEGER,            -- nullable — null when Avrae renders <None>
    conditions    TEXT    DEFAULT '', -- comma-separated; '' when no conditions parsed
    alive         INTEGER NOT NULL DEFAULT 1,  -- 0 if defeated marker parsed, else 1
    side          TEXT    NOT NULL DEFAULT 'unknown',  -- 'player' | 'enemy' | 'unknown'; v1 always 'unknown' (see §4.4)
    updated_at    TEXT    NOT NULL,   -- ISO8601
    PRIMARY KEY (campaign_id, name)
);
CREATE INDEX IF NOT EXISTS idx_combatant_campaign
    ON dnd_combatant_state(campaign_id);
```

**Position in `init_db`:** sits next to `dnd_combat_state` (`dnd_engine.py:337`). Same separation invariant — only deterministic systems write here, LLM extraction never touches.

**Reset list registration:** added to `dnd_engine.py`'s reset table list (`dnd_engine.py:758`) so `/reset_campaign` clears combatants alongside other per-campaign state.

### 4.3 Write paths (single-writer invariant)

Only two functions write to `dnd_combatant_state`. Both live in `dnd_engine.py`:

```python
def update_combatants_from_init_list(campaign_id: int, parsed: dict) -> int:
    """Replace-in-place. Wraps in one transaction:
       1. DELETE FROM dnd_combatant_state WHERE campaign_id=?
       2. INSERT row per combatant in parsed['combatants']
       3. updated_at = utcnow ISO8601 for every row
    Returns count of inserted rows. Idempotent across snapshots —
    each !init list seen overwrites the prior snapshot.
    """

def clear_combatants(campaign_id: int) -> None:
    """DELETE FROM dnd_combatant_state WHERE campaign_id=?.
    Called from _handle_init_event on init_event=='end' and from
    _handle_rest_event when current mode == 'combat'."""
```

`update_combatants_from_init_list` is called only from `avrae_listener` (or its caller in `discord_dnd_bot._handle_init_list_event`) — see §5.7. `clear_combatants` is called only from the existing `_handle_init_event` / `_handle_rest_event` branches, alongside the existing `clear_active_turn` calls.

**Why DELETE-then-INSERT instead of UPSERT per row:** an `!init list` snapshot is the canonical full state at a moment in time. UPSERT-per-row would leave stale rows for combatants that were removed (`!init remove`, defeated and pruned, etc.) since the last snapshot. Replace-in-place keeps the table consistent with the most recent snapshot. Cost: one extra DELETE per snapshot; combatant counts in this layer are ≤ ~10 typically — negligible.

### 4.4 Read path

```python
def get_combatants(campaign_id: int) -> dict:
    """Returns {
        'combatants': [{name, init, hp_current, hp_max, conditions, alive, side}, ...]
                       ordered by init DESC, then by name ASC for ties,
        'snapshot_age_s': float | None,  # seconds since latest updated_at, None if no rows
    }"""
```

Pure read, no side effects. Consumed by `compute_persistence_directive` (§5) and by the telemetry helper in §6.3.

### 4.5 What's NOT in the data model

- **Damage / defeated / status embed parsing.** The original §11.A option (ii) framing was incremental damage-event tracking. The locked option (ii) is `!init list` snapshot parsing instead — a single deterministic source rather than reconstruction from delta events. Damage embeds remain consumed only by the existing roll-buffer flow.
- **Per-combatant controller_id / side enrichment.** `!init list` plaintext does NOT include `<@discord_id>` mentions per combatant — that surface is only on the per-turn header (already parsed in `parse_init_event`). For v1, `side` defaults to `'unknown'` for every row. Future enrichment: cross-reference `controller_id` from the most recent `!init turn` event against combatants whose `name` matches `dnd_combat_state.character_name` to flag `side='player'`. Filed as a v1.x or v2 ship.
- **History / audit trail.** Only the latest snapshot is retained. No per-turn HP history, no defeated-when timestamps. If observed friction asks for it, file separately — the load-bearing case is "what is true RIGHT NOW," and replacement is the cheapest path.
- **Combatant identity reconciliation across renames.** If a player runs `!init opt <name> -name <new_name>`, the next snapshot writes a new row under `<new_name>` and the prior `<name>` row is dropped on DELETE. No alias mapping. Acceptable for v1.

---

## 5. Detection layer

### 5.1 Trigger

`compute_persistence_directive(...)` runs in `dm_respond` after `scene_state` is loaded and `get_active_turn` is queried (which the init directive already does on the same turn — share the lookup). Runs BEFORE `build_dm_context` so the directive can be passed via the kwarg.

### 5.2 Detection logic (proposed v1)

```python
def compute_persistence_directive(
    mode: str,
    active_turn: dict | None,
    combatants_snapshot: dict | None = None,    # from get_combatants(campaign_id)
    typing_user_id: str | None = None,
    typing_character_name: str | None = None,
) -> tuple[str, dict]:
    signals = {
        'fired': 0,
        'combat_active': 0,
        'hp_known': 0,
        'conditions_known': 0,
        'combatants': 0,
        'snapshot_age_s': None,
        'active_turn_controller': 'none',
    }

    # Master gate: mode must be combat. All sub-pressures gate off this.
    if mode != 'combat':
        return '', signals
    signals['combat_active'] = 1

    # Snapshot-derived signals
    combatants = (combatants_snapshot or {}).get('combatants') or []
    snapshot_age = (combatants_snapshot or {}).get('snapshot_age_s')
    signals['combatants'] = len(combatants)
    signals['snapshot_age_s'] = snapshot_age
    signals['hp_known'] = 1 if any(c.get('hp_max') is not None for c in combatants) else 0
    signals['conditions_known'] = 1 if any((c.get('conditions') or '').strip() for c in combatants) else 0

    # Sub-pressure 1+2: enemy persistence + condition awareness — fire as ONE
    # concrete combatants-block when mode=combat. When combatants is empty,
    # falls back to the abstract-claim wording (we know combat is active but
    # have no snapshot yet).
    if combatants:
        sections = [_render_combatants_block(combatants, snapshot_age)]
    else:
        sections = [_PERSISTENCE_ABSTRACT_FALLBACK_BODY]

    # Sub-pressure 3: initiative-order enforcement — fires when active_turn populated.
    # Per §11.B retroactive lock: 2A.3 drops OFF-turn messages upstream, so v1
    # only renders ON-turn confirm + naming-only. If typing_user_id is supplied
    # and DOESN'T match the controller, the message would have been gated; we
    # treat that branch as defensive-only (still renders naming-only, no false
    # OFF-turn pressure).
    if active_turn:
        controller = active_turn.get('controller_id')
        char_name = active_turn.get('character_name', '')
        round_num = active_turn.get('round', 0)
        signals['active_turn_controller'] = str(controller) if controller else 'none'

        on_turn = bool(
            typing_user_id is not None
            and controller
            and str(typing_user_id) == str(controller)
        )
        if on_turn:
            sections.append(_render_turn_order_on_turn_block(
                char_name=char_name,
                controller=controller,
                round_num=round_num,
                typing_actor=typing_character_name or 'the typing player',
            ))
        else:
            # No identity, identity mismatch (defensive — 2A.3 should have
            # caught it), or active_turn populated but no controller string:
            # emit naming-only.
            sections.append(_render_turn_order_naming_only(
                char_name=char_name,
                controller=controller,
                round_num=round_num,
            ))

    body = "\n\n".join(sections)
    signals['fired'] = 1
    return body, signals
```

### 5.3 New regex (one parser branch, deterministic)

Adds one new function in `avrae_listener.py` — `parse_init_list_embed(text)`. Detection is regex over plaintext, no LLM, mirrors the existing `parse_init_event` shape. Patterns described in §5.6.

### 5.4 Signal source: `get_active_turn`

The bot's only durable "is init active?" signal is `dnd_combat_state` rows. Edge cases (carried over from the init spec's analysis):

- **`!init begin` fired but no `!init turn` yet**: `get_active_turn` returns `None`. Directive correctly skips turn-order sub-pressure. Enemy-persistence + condition pieces still fire (mode='combat' is set when `begin` fires).
- **`!init end` fired**: `clear_active_turn` runs synchronously, `set_scene_mode('exploration')` runs immediately after. Both fire from `_handle_init_event`. Next turn's directive: master gate fails, full-silent. Correct.
- **Bot restart mid-combat**: in-memory state lost, but `dnd_combat_state` persists in SQLite, mode persists in `dnd_scene_state`. Directive correctly continues firing on restart.
- **`/mode <not-combat>` while active_turn is set**: master gate fails (mode is no longer combat), directive full-silent. Stale `active_turn` row persists but unused. Filed as a hygiene-ship candidate; doesn't affect v1.

### 5.5 Caller-side data passing

`dm_respond` needs `typing_user_id` and `typing_character_name`. The first is `message.author.id` cast to string; the second is the resolved canonical character name (already computed upstream via Phase 6 `resolve_actor` for the actor-resolution write paths).

For multi-actor batches (ActionBatcher coalesces multiple player messages into one DM call), the directive reads the FIRST batched actor's identity — same scoping shape ActionBatcher uses for `actor` in the LLM call. Multi-actor turn-order tension is filed for the multiplayer table, not v1.

If the caller can't supply typing info (test paths, edge cases), the directive falls back to naming-only (§5.2 else branch).

### 5.6 `parse_init_list_embed` — parser shape

Lives in `avrae_listener.py` next to `parse_init_event` (`avrae_listener.py:253`).

```python
def parse_init_list_embed(text: str) -> Optional[Dict[str, Any]]:
    """Parse Avrae !init list plaintext output into a structured snapshot.
    Returns None if text doesn't match the !init list format.
    Returns dict on match:
      {
        'round': int,
        'current_init': int,
        'combatants': [
          {
            'init': int,
            'name': str,
            'active': bool,           # True if line had # marker
            'hp_current': int|None,
            'hp_max': int|None,
            'conditions': str,        # comma-joined; '' if none
            'alive': int,             # 0/1; 0 if defeated marker parsed
          },
          ...
        ],
      }
    """
```

**Detection regex (header + separator):**

```python
_INIT_LIST_HEADER_RE = re.compile(
    r"^Current initiative:\s*(?P<current_init>-?\d+)\s*\(round\s+(?P<round>\d+)\)\s*$",
    re.MULTILINE,
)
_INIT_LIST_SEPARATOR_RE = re.compile(r"^={3,}\s*$", re.MULTILINE)
```

A message qualifies as an `!init list` output iff `_INIT_LIST_HEADER_RE` matches AND `_INIT_LIST_SEPARATOR_RE` matches in the same payload. Both required — guards against narrative messages that happen to mention "Current initiative."

**Combatant row regex (the load-bearing one):**

The user-supplied sample format is:
```
  29: Garrick <None>
# 25: throx <None>
  13: Donovan <None>
```

```python
# Permissive: optional '#' marker, init value, name (any chars except '<'),
# status (anything inside <>), trailing whitespace.
_INIT_LIST_ROW_RE = re.compile(
    r"^(?P<marker>[# ])\s*(?P<init>-?\d+):\s*"
    r"(?P<name>[^<]+?)\s*"
    r"<(?P<status>[^>]*)>\s*$",
    re.MULTILINE,
)
```

**Status field decoding** (the part with high format-uncertainty — see Phase 1 unknowns below):

| Observed status text | Decoding (v1) |
|---|---|
| `None` | `hp_current=None, hp_max=None, alive=1` |
| `{n}/{m} HP` | `hp_current=n, hp_max=m, alive=(1 if n>0 else 0)` (UNCONFIRMED — needs real-combat fixture) |
| `Healthy` / `Bloodied` / `Wounded` (private mode) | `hp_current=None, hp_max=None`, parse `alive=0` only on explicit defeated marker (UNCONFIRMED) |
| `defeated` / `KO'd` / similar | `hp_current=0, hp_max=None, alive=0` (UNCONFIRMED) |
| Anything else | `hp_current=None, hp_max=None, alive=1` (fail-open, log a `[INIT_LIST_PARSE_UNKNOWN]` line for empirical follow-up) |

**Conditions field** (FORMAT UNCONFIRMED — needs real-combat fixture):

The user-supplied sample shows the status field is `<None>` only — conditions don't appear in the same `<...>` slot. Avrae's typical `!init list` rendering puts conditions on indented continuation lines under each combatant, like:

```
   29: Garrick <22/22 HP>
        - Concentrating
        - Frightened
```

The parser treats any line beginning with whitespace + `-` (or `*`) as a condition continuation tied to the most recent combatant row. If the actual rendering differs (e.g., conditions inline in the `<...>` field after a separator), the regex needs updating once we have a sample.

```python
_INIT_LIST_CONDITION_RE = re.compile(
    r"^\s+[-*]\s+(?P<condition>.+?)\s*$",
    re.MULTILINE,
)
```

**Group / monster-pack rendering** (FORMAT UNCONFIRMED): Avrae's `!init madd <monster> -group "<group>"` produces a group header with member rows indented underneath. v1 parser does NOT special-case groups — it parses each member row as a flat combatant. If group headers cause parse confusion, file as a known limitation; otherwise the v1 behavior degrades gracefully.

**Phase 1 format unknowns** — partially LOCKED post-ship from real-combat samples:

1. ✅ **HP rendering with sheet-bound characters: `<{cur}/{max} HP>` with optional ` (AC {N})` trailing suffix.** LOCKED 2026-05-04 from live sample (`init_list_parsed: campaign=17 ... combatants=2 hp_present=...`). Avrae renders sheet-bound combatants (those joined via `!init join`) with HP in `<n/m HP>` form and an unbracketed `(AC N)` suffix outside the `<...>` slot. The row regex's permissive trailer (`[^\n]*$` after `>`) absorbs the suffix without dropping the row. Future renderers may add more trailing surfaces; permissive trailer keeps parse working.
2. **Private-mode HP rendering** — UNCONFIRMED. Avrae's `!init opt <name> -h` toggles private HP. Decoding rule (any non-numeric, non-defeated, non-None status → alive=1, HP unknown) is the conservative fallback.
3. **Defeated marker** — UNCONFIRMED. `<defeated>`, `<KO>`, `<0/X HP>`, or some other surface — needs a live KO sample to lock.
4. **Condition rendering shape** — UNCONFIRMED. Indented dash-continuation parser is in place but no real-combat conditions rendered yet (combat hasn't carried conditions in any captured sample).
5. **Group/monster-pack header rendering** — UNCONFIRMED. Treated as flat combatants in v1.

**Real-combat sample (locked):**

```
Current initiative: 0 (round 0)
===============================
  18: Garrick <None>
  14: Donovan Ruby <11/11 HP> (AC 13)
```

This sample is captured as `REAL_COMBAT_SAMPLE` in `test_init_list_parser.py`. As more formats surface live, expand the fixture set there.

**Mitigation:** parser fails open (returns `None` cleanly when format is fully unrecognizable; emits parse-unknown logs for partial matches). Real-combat fixtures gate calibration. Acceptance for v1 is "parses the sample format Jordan supplied + degrades gracefully on richer formats." Format-locking happens post-real-combat.

### 5.7 Write trigger — when `parse_init_list_embed` runs

`avrae_listener.parse_init_list_embed` is invoked in the `on_message` (and `on_message_edit` for edited list outputs) Avrae branch in `discord_dnd_bot.py` (`discord_dnd_bot.py:474`). New handler `_handle_init_list_event` mirrors `_handle_init_event`:

```python
async def _handle_init_list_event(message, parsed):
    """parsed = parse_init_list_embed(message.content)
    Writes via update_combatants_from_init_list(campaign_id, parsed).
    Pure mechanical mapping, no LLM."""
```

Wired in `on_message`:

```python
if al.is_avrae(message):
    init_evt = al.parse_init_event(message)
    if init_evt:
        await _handle_init_event(message, init_evt)
    # NEW: also try !init list parse — independent of init_event matching.
    list_parsed = al.parse_init_list_embed((message.content or '').strip())
    if list_parsed:
        await _handle_init_list_event(message, list_parsed)
    # ... existing parse_avrae_embed path unchanged ...
```

**Trigger frequency.** The listener writes on EVERY `!init list` Avrae plaintext seen. The DM (or a player) types `!init list` to refresh the snapshot. v1 does NOT proactively request `!init list` — that would cross the bot-stays-read-only invariant. Stale-snapshot risk is documented in §12.

**Idempotency.** Replace-in-place: each snapshot DELETEs prior rows and writes fresh ones. Two `!init list` outputs back-to-back result in the same final state.

**Cross-channel scoping.** The listener already scopes Avrae messages by `message.guild.id → get_active_campaign(guild_id) → campaign['id']`. `_handle_init_list_event` uses the same path. No new scoping logic.

**Edit handling.** `on_message_edit` fires when Avrae edits an existing list message (the `!init list` button-driven refresh, or the end-of-combat replacement). Add a parallel `parse_init_list_embed` branch to `on_message_edit` so refreshed lists are picked up.

---

## 6. Resolution / directive layer

### 6.1 Directive body (proposed)

The body is now CONCRETE — rendered from `dnd_combatant_state` rows. Two layout shapes: one when combatants snapshot is non-empty (the load-bearing path), one fallback when no snapshot exists yet.

**Concrete combatants block** — `_render_combatants_block(combatants, snapshot_age_s)`:

```
=== COMBAT PERSISTENCE ===
COMBAT IS ACTIVE — AVRAE HOLDS THE MECHANICAL STATE.

Last !init list snapshot ({snapshot_age_s}s ago):
  {init:>3}: {name} — HP {hp_current}/{hp_max}{conditions_clause}{active_marker}
  {init:>3}: {name} — HP unknown{conditions_clause}{active_marker}
  {init:>3}: {name} — DEFEATED
  ...

Combat ends ONLY when `!init end` fires. Do NOT narrate the encounter as wrapped,
the enemies fled, or the fight resolved while combatants above show HP > 0 (or
HP unknown — assume alive until proven otherwise). If the encounter feels like
it's resolving, surface that posture (enemies broken, surrendering, regrouping)
and stop short of authoring the close — leave the resolution for `!init end`
to confirm.

Honor any condition listed above per its 5e rules — a frightened combatant
cannot rally, a grappled one cannot move, a paralyzed one cannot act. Do not
narrate around or through a condition this snapshot has set.
```

Per-row decoding rules:
- `{conditions_clause}` is `, conditions: {comma-list}` when `conditions != ''`, else empty.
- `{active_marker}` is `  ← active turn` when the row's `active=True`, else empty.
- `HP unknown` substitutes when `hp_max is None` (Avrae rendered `<None>` or private mode).
- `DEFEATED` substitutes when `alive=0` — replaces the entire HP/conditions clause.
- Rows ordered by `init DESC` to match `!init list` rendering.
- Snapshot-age string is `{int_seconds}s` or `>{N}min` if older than 60s.

**Abstract fallback** (when `combatants` list is empty — `!init begin` fired but no `!init list` parsed yet):

```
=== COMBAT PERSISTENCE ===
COMBAT IS ACTIVE — AVRAE HOLDS THE MECHANICAL STATE.

No !init list snapshot has been parsed yet this combat. Avrae owns HP and
conditions. Combat ends ONLY when `!init end` fires, NEVER via narrative
declaration. Do NOT narrate the encounter as wrapped, the enemies fled, or
the fight resolved. If conditions are in play (frightened, grappled, paralyzed,
prone, restrained, stunned, unconscious, etc.), honor whatever Avrae shows in
`!init list` / `!status` outputs.

(Tip: type `!init list` to surface the current combatant state.)
```

**Initiative block** (appended after either body when `active_turn` is populated):

Per §11.B retroactive lock: 2A.3 already drops OFF-turn messages at `on_message`, so the directive's OFF-turn rendering never fires in production. v1 ships only ON-turn confirm + naming-only.

ON-TURN (typing user matches active controller):
```
INITIATIVE: round {round}, {character_name}'s turn (Discord {controller}).
The current message is from {typing_actor} — ON-TURN. Narrate from
{character_name}'s frame. Resolve their declared action; the next initiative
slot belongs to whoever is next in Avrae's order, not whoever types next.
```

Naming-only (active_turn populated but typing identity missing — test paths and edge cases):
```
INITIATIVE: round {round}, {character_name}'s turn (Discord {controller}).
Narrate from {character_name}'s frame; the next initiative slot belongs to
whoever is next in Avrae's order.
```

When `active_turn is None` (init begin fired, no turn cycle yet): initiative block omitted entirely. Body is concrete combatants block (or abstract fallback) without trailing initiative.

### 6.2 Composition order

Renders LAST in the tactical band, AFTER commitment. In `build_dm_context`:

```
{...}{consequence_block}{commitment_block}{persistence_block}
```

Reasoning: persistence is the most-immediate-stakes constraint when in combat. It anchors the band by stating what is mechanically true RIGHT NOW. Pacing/central-thread/consequence color the world's posture; commitment dictates what the player owes from prior turns; persistence dictates what the LLM cannot do given current mechanical state. Mirrors the directive_emit reserved-field convention from S18→S19→S20 — new tactical directives slot at the end.

### 6.3 Update on emit

No state mutation on emit. The directive is purely advisory.

Logging:

```
persistence_directive: campaign={X} fired={0|1} combat_active={0|1}
                        hp_known={0|1} conditions_known={0|1}
                        combatants={N} snapshot_age_s={N|none}
                        active_turn_controller={controller_id|none}
```

The line fires on EVERY turn (not just when the directive emits) so the empirical baseline of gate signals is observable. `hp_known` and `conditions_known` are now LIVE signals — `1` when the snapshot has any rows with non-null `hp_max` or non-empty `conditions` respectively. `combatants={N}` and `snapshot_age_s={N|none}` are new fields giving the snapshot's size and freshness; `snapshot_age_s` is the load-bearing telemetry surface for §12 stale-snapshot disposition.

Additional listener-side log line — fires on every successful `!init list` parse:

```
init_list_parsed: campaign={X} round={R} current_init={I} combatants={N}
                  hp_present={0|1} conditions_present={0|1}
```

Lets us correlate "DM/player typed `!init list`" → snapshot freshness on the next directive fire.

`directive_emit:` line gets a new field:

```
directive_emit: campaign={X} pacing={tier|none} central_thread={1|0} ...
                commitment={1|0} init={1|0} persistence={1|0}
```

`persistence={1|0}` slot fires when the directive returned non-empty text.

---

## 7. Failure modes + mitigations

1. **LLM hallucinates HP from prompt context.** The directive states "Avrae owns HP" but the LLM may still confidently narrate "the bandit clutches his side, blood soaking through" implying low HP without mechanical grounding.
   *Mitigation:* The directive's enemy-persistence body explicitly forbids narrating the encounter as resolved; it does NOT forbid posture descriptions (enemies looking hurt, breathing hard, etc.). The line is between describing visible state vs. authoring a HP-driven outcome. Same calibration shape as B2.1's narration-vs-command line. Tunable post-ship from observed false-positives.

2. **Solo case turns initiative pressure into noise.** Solo player on their own turn — turn-order sub-pressure renders as "ON-turn" confirmation flavor, which is just verbose padding for a solo context.
   *Mitigation:* The ON-turn body is short ("Narrate from X's frame; the next slot belongs to whoever's next in Avrae's order"). Compact relative to the OFF-turn body. If verbose padding becomes a calibration concern, the ON-turn block could be SUPPRESSED entirely in solo (single bound character) campaigns — filed in §11.F as multiplayer-shape decision.

3. **Multiplayer typing bleed.** Player A's character is on-turn but Player A is AFK; Player B types a message intending to coordinate ("I'll help A flank"). Directive fires OFF-turn against Player B. False positive — B is collaborating, not godmode-acting.
   *Mitigation:* Loud-failure-recoverable per B2.1 doctrine. The OFF-turn body says "options: name the wait, name the held action, ready an action." All three options are LLM-narratable for collaborative coordination ("Player B watches Player A, ready to flank when their slot comes"). Acceptable. If observed in logs frequently, file directive softening as v1.x.

4. **Stale `active_turn` row after `/mode exploration` manual override.** Master gate (mode != 'combat') makes directive silent, so no incorrect fire. But if Jordan does `/mode combat` manually without re-firing init, `active_turn` may be stale.
   *Mitigation:* Files `/mode` to clear `active_turn` whenever mode flips to non-combat. Out of scope for this spec — small hygiene ship. Tracked in §11.G.

5. **Avrae's `!init turn` event arrives between `dm_respond` start and `get_active_turn` query within the same turn.** Race: directive reads stale or missing active_turn while Avrae has already moved.
   *Mitigation:* Same race profile as init directive's `get_active_turn` proxy. Acceptable — the next turn's directive reads correct state. Filed for log analysis if observed.

6. **Bot restart mid-combat with `dnd_combat_state` persisting.** Directive correctly continues firing because mode and active_turn are SQLite-stored. Edge case: bot restart between Avrae's `!init end` plaintext message and `_handle_init_event` running → mode and active_turn may be stale-combat. Next Avrae event will reconcile.
   *Mitigation:* Master gate ensures the failure mode is "directive over-fires while bot is catching up" rather than "directive never fires." Recoverable. Same shape as init directive's restart edge.

7. **The "encounter is resolving" boundary is fuzzy.** When the last bandit is at 1 HP and prone, narration that says "the bandit slumps in defeat" is reasonable color; narration that says "you've won, the bandits scatter" is the failure mode.
   *Mitigation:* The directive's body distinguishes "surface posture" (allowed) from "author the close" (forbidden). LLM judgment will produce false positives and false negatives at the edge. Calibration loop is observed-emission analysis post-ship, same as every other Track 3 directive.

8. **Condition-awareness sub-pressure has per-creature data when snapshot is fresh, abstract claim when not.** With option (ii) lock, the directive renders concrete `Garrick — HP 22/22, conditions: Frightened` when a snapshot exists. When the snapshot is empty (init begin fired, no `!init list` parsed yet), it falls back to the abstract claim with the eight-condition reminder. The previously-acknowledged "v1 has no per-creature data" limitation is RESOLVED for the snapshot-fresh path; the abstract-fallback path remains as a graceful degrade.

8a. **Stale snapshot — combatants block reflects state that's no longer accurate.** Players take damage, conditions resolve, HP changes between the last `!init list` and the current turn. Directive renders the stale row.
   *Mitigation:* `snapshot_age_s` is surfaced both in telemetry AND in the rendered body ("Last !init list snapshot ({N}s ago)") — the LLM is told how stale the data is. When the staleness is high, the LLM's prior shifts toward "data may be out of date, posture should reflect possible drift." The `(Tip: type !init list to refresh)` line in the abstract fallback is the standing nudge to keep snapshots fresh. Long-term mitigation lives in §12 + a future v1.x where the bot proactively requests `!init list` (filed, not v1).

9. **Multi-actor batch where typing_actor is neither the active controller nor a clear PC.** ActionBatcher batches multiple players; first-actor scoping per §5.5.
   *Mitigation:* Filed per multi-PC table. Single-PC cases (the dominant load-bearing path for solo testing) work cleanly under this spec. Multi-PC turn-order edge cases earn refinement post-friends.

---

## 8. Test plan (proposed)

### 8.1 Engine layer (`test_persistence_directive.py`)

- `mode='exploration'` + active_turn None → returns `''` with `fired=0`, `combat_active=0`.
- `mode='social'` / `'travel'` / `'downtime'` / `''` / None → all return `''` with `fired=0`.
- `mode='combat'` + active_turn None + typing info absent → returns enemy-persistence + conditions, NO turn-order block. `fired=1`, `combat_active=1`, `active_turn_controller='none'`.
- `mode='combat'` + active_turn populated + typing_user_id == controller_id → returns full body, ON-turn block. Body contains `character_name`, `round`, `Discord controller`, "ON-TURN".
- `mode='combat'` + active_turn populated + typing_user_id != controller_id → returns full body, OFF-turn block. Body contains "OFF-TURN" and acknowledgment options.
- `mode='combat'` + active_turn populated + typing info missing → returns enemy-persistence + conditions + naming-only turn-order block (no comparison clause).
- Body contains both `Avrae owns HP` and the conditions reference (frightened/grappled/paralyzed/prone/restrained/stunned/unconscious enumeration).
- Body forbids "narrate the encounter as wrapped" / "fights end via `!init end`".
- Cross-campaign isolation: same shape as commitment/init tests.
- Idempotency: pure function, no side effects.
- Signal log summary: `persistence_log_summary(signals)` returns the field-list string for the per-turn log line.

### 8.2 Integration test (light)

- Synthetic state: `scene_state.mode='combat'`, `dnd_combat_state` row set via `set_active_turn`, `typing_user_id` matches controller. Build full `dm_respond` prompt; verify `=== COMBAT PERSISTENCE ===` block appears AFTER `=== UNRESOLVED COMMITMENT ===`, contains the ON-turn body, and the `persistence_directive: ... fired=1 combat_active=1` log line emits.
- Negative integration: same scene with mode='exploration' — verify the block is absent and `persistence_directive: ... fired=0 combat_active=0` emits.

### 8.3 Live verification

After v1 ships, run two solo scenarios:

**Scenario A (combat persistence):**
1. Start a fresh scene, `/mode combat` manually OR force `!init begin` via Avrae.
2. After init is set up, type a non-resolving action ("I look around for cover").
3. Expected: response contains a posture description but does NOT narrate the encounter as wrapped. `persistence_directive: ... fired=1 combat_active=1` log line emits.

**Scenario B (turn-order, solo so always ON-turn):**
1. Type an action on Donovan's turn.
2. Expected: directive includes `INITIATIVE: round X, Donovan Ruby's turn (Discord ...). The current message is from Donovan Ruby — ON-TURN.`
3. `persistence_directive: ... active_turn_controller=<discord_id>` log line emits.

**Scenario C (off-turn pressure, requires multi-PC — defer if solo only):**
1. Multiplayer test with two PCs in init. NPC turn is active OR PC2's turn is active.
2. PC1's player types a message during PC2's turn.
3. Expected: directive renders OFF-turn body, names PC2 as active and PC1 as typing. LLM narration acknowledges turn order rather than authoring PC1's action in-sequence.
4. `persistence_directive: ... active_turn_controller=<PC2_discord_id>` log line emits.

If LLM compliance is poor on Scenario C, file as strength-tuning per §11.D. Solo Scenarios A+B are the v1 acceptance path; C is the multiplayer-readiness check.

---

## 9. Migration impact

**Schema changes:**
- New `dnd_combatant_state` table (§4.2). Forward-only via `CREATE TABLE IF NOT EXISTS` in `init_db()`.
- New entry in the reset table list (`dnd_engine.py:758` neighborhood) so `/reset_campaign` clears combatants.

**Code additions:**
- `dnd_engine.py`: `update_combatants_from_init_list`, `clear_combatants`, `get_combatants` (§4.3, §4.4). `clear_combatants(campaign_id)` invocation added to `_handle_init_event` (`init_event=='end'` branch) and `_handle_rest_event` (mode=='combat' branch) alongside the existing `clear_active_turn` calls.
- `avrae_listener.py`: `parse_init_list_embed`, plus the three regexes in §5.6.
- `discord_dnd_bot.py`: new `_handle_init_list_event` handler; new branch in `on_message` and `on_message_edit` (§5.7).
- `dnd_orchestration.py`: `compute_persistence_directive(...)`, `persistence_log_summary(signals)`, `_render_combatants_block(...)`, `_render_turn_order_block(...)`, `_render_turn_order_naming_only(...)`, plus `_PERSISTENCE_ABSTRACT_FALLBACK_BODY` constant.
- `build_dm_context`: new `persistence_directive=""` kwarg; new `=== COMBAT PERSISTENCE ===` render block AFTER the commitment block.
- `dm_respond`: passes `typing_user_id` + `typing_character_name` + the read result of `get_combatants(campaign_id)` into `compute_persistence_directive`. Emits the new `persistence_directive:` log line and adds `persistence={0|1}` to `directive_emit:`.
- New test files:
  - `test_persistence_directive.py` — gate-isolation, composition, multi-PC turn-order cases, stale-snapshot rendering.
  - `test_init_list_parser.py` — fixtures from the user-supplied sample (the `<None>` shape we have); placeholder fixtures for HP / private / defeated / conditions / groups marked TODO until real-combat samples land.
  - `test_combatant_state.py` — write-path replace-in-place semantics, `clear_combatants` on `init_event=='end'`, `get_combatants` ordering and snapshot age.

**Cross-version safety:** Schema is forward-only (`CREATE TABLE IF NOT EXISTS`). Old code without the new directive renders the prompt without the block. If the bot starts before the first `!init list` is parsed, `get_combatants` returns the empty-snapshot shape and the abstract-fallback body renders correctly.

**Read-after-write coherence:** `_handle_init_list_event` runs synchronously in the listener (same task that processes the message). The next turn's `dm_respond` reads the just-written rows. No async lag concern within the v1 single-process bot.

**ActionBatcher interaction:** persistence directive consumes first-batched actor's typing identity for multi-actor calls (§5.5). No structural change to batching.

---

## 10. Out of scope (separate specs / separate layers)

- **Damage-event-driven HP tracking.** Parser-side delta ship over Avrae damage embeds (subtract HP per attack/cast) was the original §11.A option (ii) framing. Locked v1 uses `!init list` snapshots instead — single source of truth, no delta reconstruction. Damage-event tracking would let the directive react between manual `!init list` refreshes; filed as a v1.x candidate IF observed staleness friction is high.
- **Bot-driven proactive `!init list` request.** v1 relies on DM/players typing `!init list` to refresh the snapshot. A future ship could have the bot send `!init list` itself when the snapshot ages past a threshold. Crosses the bot-stays-read-only invariant — bot would be writing to `#avrae` / `#dm-narration`. Earns its own spec.
- **Per-combatant `side='player'|'enemy'` enrichment.** v1 always writes `side='unknown'`. Cross-referencing `dnd_combat_state.character_name` (set by `!init turn` parser) against `dnd_combatant_state.name` would let the directive flag PCs vs NPCs. Not blocking.
- ~~Hard-gating off-turn input at message receive.~~ **Already shipped via Phase 2A.3** (`discord_dnd_bot.py:565-581`). The persistence directive composes downstream of 2A.3, not in opposition to it. See §11.B for the retroactive lock disposition.
- **NPC-side turn-order pressure.** "Do not narrate the goblin acting before the goblin's slot." NPCs are LLM-narrated, not player-typed; the gate shape is different (LLM-self-policing rather than player-input scoping). Filed as future ship.
- **Combat-mode pacing tier shift.** Existing pacing directive handles tension; not this spec's concern. Existing pacing tiers (low/medium/high/climax) are tension-driven and orthogonal to combat presence.
- **Action economy / reaction enforcement.** "Player attacks while prone is at disadvantage" — bridge-layer pressure on action economy. Different layer; far-future spec. Mechanical handling is Avrae's; this directive only requires the LLM to honor what Avrae shows.
- **Encounter framing / NPC initiation.** "When does the LLM-narration introduce hostile intent?" Generation problem, not persistence. Post-friends.
- **Stale `active_turn` cleanup on `/mode <not-combat>`.** Hygiene ship. Filed (§11.G).
- **Full 5e condition catalog enumeration.** With option (ii) lock, conditions are named per-creature from the snapshot — no enumeration needed in the load-bearing path. The abstract-fallback body retains a brief eight-condition reminder for the snapshot-empty case (§11.D).
- **Multi-actor turn-order detection.** First-actor scoping in v1 per §5.5. Multi-PC table earns refinement post-friends.
- **Combatant identity reconciliation.** Renames via `!init opt -name` produce a new row under the new name; old row dropped on next snapshot DELETE. v1 acceptable per §4.5.

---

## 11. Decision points needing review

These are the surfaces where Jordan's call shapes the spec. I'd lean toward the proposal in §1 for each, but flagging explicitly so nothing ships on my unilateral choice.

### §11.A — Data source for HP / conditions / turn-order — LOCKED to option (ii) (2026-05-04)

**Status:** LOCKED to option (ii) per Jordan's call (2026-05-04 review session). This subsection is preserved in its original four-option form below for traceability; the lock and retraction reasoning are at the top.

**Lock summary.** v1 ships with a parser-side data layer fed by `!init list` snapshot parsing. The directive renders concrete per-combatant state ("Garrick — HP 22/22, conditions: Frightened") rather than abstract claims ("Avrae has the data, honor it"). The new `dnd_combatant_state` table (§4.2), `parse_init_list_embed` (§5.6), and write paths (§5.7) are all in scope for v1. The form of the lock is closer to a unified version of original options (ii)+(iii) than to either alone — `!init list` is the canonical full-state source, so HP and conditions land on the same parsing path.

**Why option (i) was retracted.** The original recommendation (i) — directive-only with abstract claims — leaned on "ship the shape, watch the data" doctrine. Jordan's call cites the immersion doctrine: a directive that says "Avrae has the data, honor it" is a directive that depends on the LLM both (a) believing the data exists in some unspecified place and (b) inferring the right response without grounding. That's exactly the shape that makes capability-grounding directives drift in practice — the LLM hallucinates around abstract pressure where it would honor concrete pressure. Combat narration is the place where mechanical truth must be most legible; abstract claims read as advisory padding rather than constraint. Option (i) traded shipping speed for the immersion that the spec exists to defend; trade rejected.

**Why `!init list` parsing rather than damage-event tracking.** The original option (ii) framing was incremental damage-event tracking (parse damage embeds, subtract from HP). Locked option (ii) uses `!init list` snapshots — one canonical source, replace-in-place, no delta reconstruction. Trade-offs:
- Damage-event tracking would auto-refresh between manual `!init list` calls. `!init list` snapshots require the DM/player to type the command, so the data can go stale (§12).
- Damage-event tracking has ~10 distinct embed shapes to parse correctly (attack, cast, damage, heal, temp HP, defeated, etc.) and to compose without drift. `!init list` is one parse path with one data shape.
- `!init list` mechanism is the canonical "what does Avrae think is true RIGHT NOW" surface — no inferred composition. Lower implementation risk; cheaper to verify.
- Delta tracking remains filed (§10) as a v1.x candidate if staleness friction is high.

**Confidence on the lock:** HIGH. Decision was bounded — Jordan reviewed the four options, named the immersion-doctrine concern with (i), accepted the staleness trade with snapshot-vs-delta, called for spec expansion. This subsection is no longer an open question.

---

**Original four-option framing (preserved for traceability):**

Phase 1 diagnostic showed three different data states for the three sub-pressures:
- **Turn order**: authoritative state in `dnd_combat_state.character_name + controller_id`. We have it.
- **HP**: Avrae owns it; we don't extract it from embeds. We don't have it.
- **Conditions**: Zero parsing. We don't have it.

Four options for v1:
- **(i)** Directive-only with proxy signals (mode + active_turn). LLM is told "Avrae owns HP and conditions; honor them." Zero parser-side ship. Smallest delta. **RETRACTED — see immersion-doctrine reasoning above.**
- **(ii)** Spec a parser-side ship for HP tracking AS PART OF v1. Original framing: parse damage / defeated / status embeds → write. Locked-v1 framing: parse `!init list` snapshot → REPLACE-style write. **LOCKED.**
- **(iii)** Spec a parser-side ship for condition tracking AS PART OF v1. Subsumed under locked-(ii) — `!init list` carries both HP and conditions in the same snapshot.
- **(iv)** Both (ii) and (iii). Effectively redundant under the snapshot-parsing approach; subsumed.

### §11.B — Initiative-order enforcement scope — LOCKED, retroactively softened (2026-05-04)

**Status:** LOCKED to "directive supplements existing 2A.3 gate, not directive-only." The original recommendation (directive-only with bot-stays-read-only invariant) was written without acknowledging that Phase 2A.3 (`SESSIONS.md:171`, `discord_dnd_bot.py:565-581`) had already shipped the hard gate it framed as a future "separate spec." 2A.3 IS the hard gate, treated as architectural prior; not an invariant violation.

**Lock summary.** The persistence directive composes DOWNSTREAM of 2A.3. In normal Discord flow:
- `mode='combat'` + `active_turn` populated + author ≠ controller → 2A.3 drops the message with ⏳, `dm_respond` is never called, directive never runs.
- `mode='combat'` + `active_turn` populated + author == controller → 2A.3 passes, directive renders ON-turn block.
- `mode='combat'` + `active_turn=None` → 2A.3 passes (its rule is permissive when no turn is recorded), directive renders naming-only block.
- `mode != 'combat'` → 2A.3 passes, directive returns `''` per master gate.

**Implication for §6.1 / §5.2.** The directive's OFF-turn rendering branch is dropped from v1. It would never fire in production because 2A.3 catches off-turn messages first. Two render shapes survive:
- **ON-turn confirm** (typing user matches active controller — the dominant load-bearing case).
- **Naming-only** (active_turn populated but no typing identity, or active_turn=None — falls out of the same code path that previously emitted the abstract turn-order block).

The OFF-turn block stays out of the directive entirely. If a future ship retracts 2A.3 (multiplayer disposition change, slash-command opt-in, etc.), the OFF-turn render shape can be added back at that time.

**Confidence:** HIGH on the retroactive softening. The 2A.3 ship is older, load-bearing for multi-account play, and aligns with the spec's actual locked behavior even though the spec wording originally framed it as an invariant violation.

---

**Original two-option framing (preserved for traceability):**

Two architectural options for off-turn input were considered:
- **Directive-only (originally proposed):** LLM is told the turn order; it decides how to honor it. Bot stays read-only on Avrae channel and narration-only on `#dm-narration`. **RETRACTED — 2A.3 is the actual shipped behavior; the framing was wrong, not the ship.**
- **Hard gate:** Bot's `on_message` checks `message.author.id` against `get_active_turn().controller_id`; if mismatch, the message is dropped (with a ⏳ reaction). **THIS IS WHAT SHIPPED in 2A.3.** Treated as architectural prior, not invariant violation.

### §11.C — Failure mode when mechanical state is stale or unavailable

**Restate.** Three options for when inputs are missing or stale:
- **(i) Silent skip per sub-pressure (proposed):** mode!=combat → full silent. mode=combat + active_turn None → enemy-persistence + conditions fire, turn-order silent. mode=combat + active_turn populated + typing info missing → naming-only block.
- **(ii) Surface telemetry only:** log `persistence_directive: fired=0` regardless of state, never render directive text. Good observability, zero LLM steering.
- **(iii) Default-to-narrative-freedom:** when state is stale, emit a softer "be cautious about resolving combat" reminder. Fail-open, not fail-silent.

**Recommendation:** **(i) — silent skip per sub-pressure.** Cites:
- **convention over novelty** — every other Track 3 directive returns `''` when its gates fail. Persistence returning `''` for non-combat turns is the same shape.
- **per-turn telemetry survives regardless** — the `persistence_directive:` log line ALWAYS fires, so observability is intact even when the directive is silent.
- **fail-open risks LLM compliance erosion** — option (iii) emits a directive that says "maybe consider being careful," which both Track 3 doctrine and B2.1 calibration treat as worse than imperative-or-silent.

**Confidence:** HIGH.

### §11.D — Condition list: full 5e catalog or pragmatic subset? — NEAR-MOOT after §11.A lock

**Status:** NEAR-MOOT post-lock. Conditions are now named per-creature from the parsed snapshot (§6.1's concrete combatants block), not enumerated abstractly. The eight-condition reminder survives only in the abstract-fallback body (§6.1) — the snapshot-empty path.

**What's left to decide:** whether the abstract-fallback body uses the eight-condition pragmatic subset (original recommendation) or drops to a single sentence ("honor any condition Avrae shows in `!init list`"). This is now low-blast-radius — the fallback fires only when init has just begun and no `!init list` has been parsed yet, a narrow window in any combat.

**Recommendation:** **Keep the eight-condition pragmatic subset in the abstract-fallback body**, drop it from the snapshot-fresh body. Cites:
- **Snapshot-fresh path is the dominant load-bearing case** — once `!init list` has been parsed once, the directive renders concrete per-creature conditions and the eight-condition reminder is redundant.
- **Abstract-fallback path benefits from the reminder** — the LLM sees "no snapshot yet" + "(Tip: type !init list)" and the eight-condition list is a hint about what the reminder is asking the LLM to honor.
- **Prompt-budget discipline** — keeping the list off the snapshot-fresh path saves tokens on every combat turn that has a snapshot. The fallback path renders only on the narrow init-begin window.

The eight: **frightened, grappled, paralyzed, poisoned, prone, stunned, unconscious, restrained.** Same set as the original recommendation, applied only to the fallback body.

**Confidence:** HIGH. Calibration risk is now one-step-removed — the load-bearing path doesn't depend on this choice. If observed friction shows the abstract-fallback wording is wrong, tuning that body is cheap.

**Out of scope, filed (was previously surfaced under this section):** condition-name normalization across Avrae renderings (e.g., `Frightened` vs `frightened` vs `Frightened (DC 14)`). v1 stores conditions verbatim from the snapshot. If observed friction shows variant casing or DC-suffixes confusing LLM compliance, file as a normalization v1.x ship.

### §11.E — Composition order in `build_dm_context`

**Restate.** Three options for where the persistence block renders in the tactical band:
- **(i) AFTER commitment, last in band (proposed):** `{...}{consequence_block}{commitment_block}{persistence_block}`.
- **(ii) BEFORE commitment, last-but-one in band:** `{...}{consequence_block}{persistence_block}{commitment_block}`.
- **(iii) Side-by-side with commitment (somehow merged):** structurally awkward; not recommended.

**Recommendation:** **(i) — last in band.** Cites:
- **reserved-fields placeholder doctrine** (S18→S19→S20) — every new tactical directive slots at the end. The `directive_emit:` line's slot ordering already implies this.
- **most-immediate-stakes ordering** — persistence operates on RIGHT-NOW mechanical state; commitment on prior-turn state; consequence on accumulated state. Most-immediate goes last for last-impression weight.
- **convention symmetry** — commitment landed AFTER consequence by the same reasoning; persistence inherits the convention.

**Confidence:** HIGH.

### §11.F — Multiplayer interaction: does this layer also need per-controller actor binding, or is that strictly the actor-name reconciliation work that's filed?

**Restate.** The turn-order sub-pressure compares `typing_user_id` against `controller_id`. For multiplayer, this needs:
- (a) The bot to pass through which Discord user typed which message.
- (b) The bot to resolve that Discord user → canonical PC name.
- (c) The bot to handle multi-actor batches (ActionBatcher coalesces messages).

(a) is trivial — `message.author.id` is in scope at `on_message`. (b) is partially done — Phase 6 `resolve_actor` resolves from message text, but the *typing user → bound character* mapping is what we need, which exists in the character-binding system (`/bindchar`) and is already cached in `CharacterContext`. (c) is filed for the multiplayer table.

Two options for v1:
- **(i) Inherit from the existing actor-name reconciliation work (proposed):** the bot already binds Discord users to canonical PC names via `/bindchar`. The directive consumes `(typing_user_id, typing_character_name)` from the caller; if the binding is missing, the directive falls back to naming-only (§5.2 else branch).
- **(ii) Spec the actor-binding work AS PART OF this directive:** rolls actor-binding completeness into v1's scope. Doubles work.

**Recommendation:** **(i) — inherit.** The actor-binding system is already in place (`/bindchar` was the multiplayer-readiness work from earlier sessions). For solo play, binding is trivial (single PC). For multiplayer, the binding work is gated separately. The directive consumes whatever the caller can supply; falls back gracefully when missing.

**Confidence:** HIGH for solo-case. MEDIUM for multiplayer — depends on actor-binding completeness, which is filed but may not have shipped fully. The directive's fallback path (naming-only block) handles the gap without breaking.

### §11.G — Cleanup hooks: what fires this directive off?

**Restate.** Cleanup is the question of "when does the directive go silent?" Phase 1 surfaced existing cleanup paths:
- **`!init end` (Avrae)** → `_handle_init_event` clears `active_turn`, sets mode='exploration'. Master gate fails next turn. Directive silent. ✅
- **Avrae rest event** → `_handle_rest_event` clears `active_turn`, sets mode='exploration'. Same. ✅
- **`/mode <not-combat>`** → `set_scene_mode` runs but does NOT call `clear_active_turn`. Master gate still fails (mode != 'combat'), so directive silent. Stale `active_turn` row persists but unused. ⚠️
- **`/play <preset>`** → can flip mode via preset. Same disposition as `/mode`.
- **AUTO_EXECUTE in extraction thread** → can flip mode. Same disposition.
- **Bot restart** → SQLite-stored state survives. Directive correctly resumes firing if mode is still combat.

Three options:
- **(i) Status quo (proposed):** rely on existing cleanup paths. Stale `active_turn` after `/mode` is a non-issue because mode-master-gate makes the directive silent regardless.
- **(ii) Add `clear_active_turn` to `set_scene_mode` when mode flips to non-combat:** small hygiene fix, slightly tighter state. New write coupling.
- **(iii) File the hygiene fix as a separate ship:** no v1 change.

**Recommendation:** **(i) status quo for v1, file (ii) as a candidate hygiene ship.** The persistence directive is correct under status quo; (ii) would tighten state for downstream consumers (e.g. future `/turnorder` slash command, `/init list` Discord wrappers) but isn't blocking.

**Confidence:** HIGH.

### §11.H (NEW, surfaced from §6.1 body wording) — Directive strength on the three sub-pressures

**Restate.** Persistence stacks THREE imperative sub-pressures. B2.1 surfaced that prescriptive directives can crowd narration; the init directive (§11.9 there) had the same calibration. What's the strength shape?

Trade-offs:
- **Imperative on all three (proposed):** "Do NOT narrate the encounter as wrapped." "Honor any condition currently in play." "Do NOT author the off-turn action as if it were occurring in-sequence." Same imperative shape as commitment/init.
- **Tiered strength:** imperative on enemy-persistence (the dominant failure mode), softer on condition-awareness (advisory because abstract), imperative on turn-order. Two imperative + one advisory.
- **All advisory:** "Consider whether the encounter is wrapping" / "consider any active conditions" / "consider the turn order." Risks LLM ignoring; same shape as pre-B2.1 bare `!attack`.

**Recommendation:** **Imperative on all three, with B2.1-style narration-preservation language baked in.** Body wording in §6.1 already drafts this. Refinements:
- Enemy-persistence body distinguishes "describe posture" (allowed) from "author the close" (forbidden) — explicit license for visible-state description.
- Condition-awareness body enumerates the eight conditions inline (per §11.D) so the LLM has concrete handles even without per-creature data.
- Turn-order body offers explicit options for OFF-turn ("name the wait, name the held action, ready an action") so the LLM has positive-shape narration paths beyond "refuse the action."

Cites **Why B2 needed a B2.1 follow-up** — explicit positive-shape language alongside imperative restrictions is the calibration fix. The persistence directive is structurally larger than commitment/init combined (three sub-pressures, multiple branches per sub-pressure); the positive-shape language is more important here than in the smaller sibling directives.

**Confidence:** MEDIUM. Imperative is the right starting point per the band's existing convention; calibration is observed-emission-driven post-ship. Same shape as B2.1.

### §11.I (NEW, surfaced from §11.A) — Should v1 ship a single combined directive, or split into three sibling directives?

**Restate.** §1.1 proposes a single `compute_persistence_directive` returning one combined block. Alternative: three separate directives (`compute_enemy_persistence_directive`, `compute_condition_awareness_directive`, `compute_turn_order_directive`), each with its own block, kwarg, and `directive_emit:` slot.

Trade-offs:
- **Single (proposed):** one `=== COMBAT PERSISTENCE ===` block. Three sub-pressures share telemetry (`hp_known`, `conditions_known`, `active_turn_controller` all in one log line). Smaller surface in `build_dm_context` and `directive_emit:`. Tighter coupling — tuning one sub-pressure tunes all three.
- **Split:** three blocks, three kwargs, three `directive_emit:` slots, three log lines. Larger surface; more independent tuning. Closer to the existing band's pattern (each layer = own block).

**Recommendation:** **Single combined directive.** Cites:
- **Three concerns share a master gate** — all three fail-silent when mode != 'combat'. Three separate directives would each have to read mode independently and short-circuit.
- **Prompt-budget discipline** — three `=== HEADER ===` blocks each render the section delimiter; one combined block has one delimiter and three sub-paragraphs.
- **Telemetry coherence** — `persistence_directive:` line aggregates the three signals; future v2 (HP/condition extraction) lands as field promotions on the same line, not three new lines.
- **Mirror of `consequence_directive`** — consequence handles 6 kinds of consequence in ONE block with the directive's body branching by kind. Persistence handling 3 sub-pressures in one block is the same shape.

The split variant earns its turn only if observed friction shows the three sub-pressures need independent strength tuning. Calibration data drives that decision, not pre-design.

**Confidence:** HIGH.

---

If §1's proposed decisions need to change, that's a higher-order revision — surface those first before working through the open questions.

---

## 12. Stale-combatant disposition (carry-over state from prior combats)

**Concern.** `!init list` parsing writes to `dnd_combatant_state` whenever Avrae renders a list. If Avrae has carry-over combatants from a prior combat that wasn't cleanly ended (`!init begin` fired without a matching `!init end`), running `!init list` will surface those carry-over names — and the parser will write them, and the directive will render them as if they were the current encounter.

**v1 acceptance.** Run `!init end` at the start of a fresh campaign session before the first `!init begin`. This clears Avrae-side combat state. The bot's `dnd_combatant_state` will already be empty (cleared by `_handle_init_event` on the prior session's end, or pre-existing from a fresh database). The directive will read empty until the first new `!init list` lands.

**v1 known degraded-state behaviors.**
- **Stale combatant carry-over from un-ended Avrae combat.** If the previous campaign session ended without `!init end` (bot crashed mid-combat, Discord disconnect, etc.), Avrae remembers the combatants. Next `!init list` writes those rows. Directive renders stale names with stale HP. Mitigation: setup prerequisite (run `!init end` at session start). Diagnostic: `init_list_parsed:` log line surfaces unexpected combatant counts.
- **Snapshot staleness within an active combat.** Players take damage, conditions resolve, HP changes. Directive renders the rows from the most recent `!init list`. `snapshot_age_s` field in both telemetry and the rendered body lets the LLM (and observers) see how stale the data is. Mitigation: type `!init list` to refresh; long-term, file a v1.x ship for bot-driven proactive refresh (§10).
- **Combatants pruned manually via `!init remove`.** The pruned combatant remains in `dnd_combatant_state` until the next `!init list` is parsed (DELETE-then-INSERT will drop them). One snapshot-cycle of staleness.
- **`!init opt -name <new>` rename.** Old name persists until the next snapshot writes the new name. One snapshot-cycle of staleness.

**Setup prerequisite to add to `tests-to-run-post-session.md`:** verify `!init end` is run at session start before any `!init begin`. Add the verification step to the post-session checklist so playtest sessions don't surface this as a false-positive directive failure.

**Filed as v1.x candidates IF observed friction is high:**
- Bot-driven `!init list` refresh (proactive snapshot maintenance).
- Hook for `!init remove` parser (incremental row delete).
- Damage-event delta tracking (auto-decrement HP between snapshots).

**Why these are filed not blocking:** the v1 directive is correct under "stale snapshot" — it renders what was last seen, surfaces the staleness, and asks for `!init list` refresh. The LLM has the staleness signal explicit in the prompt. Calibration data (post-ship `snapshot_age_s` distributions, observed false-positives) drives whether v1.x ships earn priority.

---

## Appendix — relationship to other layers

- **Committed-action resolution (Session 19, shipped).** Sibling. Commitment handles the *escape* failure mode (turn N+1 ignores turn N's commitment). Persistence handles the *during-combat* failure modes once init is running. The two operate on different temporal scopes (cross-turn vs intra-turn). No overlap; no shared signals beyond `mode`.
- **Combat initiation orchestration (Session 20, shipped).** Sibling. Init handles the *binding* failure mode on the commit turn (LLM emits `!init begin + !init add + !attack` to make Avrae's `-t TARGET` resolve). Persistence handles the post-init pressure on subsequent turns. The two operate on different turns of the same combat sequence (commit vs during).
- **Pacing directive (Session 14, shipped).** Tension-driven, mode-agnostic. Pacing applies to combat AND non-combat scenes via tension. Persistence applies only to combat. They compose — pacing pressures *how hard*, persistence pressures *what's mechanically true right now*.
- **Consequence directive (Session 16, shipped).** Reads accumulated NPC consequences. Mode-agnostic. Compose with persistence — consequence colors NPC posture, persistence dictates whether the encounter can wrap.
- **Three-layer 5e doctrine (S19 WHY entry).** This spec lives on the BRIDGE layer. Mechanical layer (Avrae's HP, conditions, init order) remains untouched. Narrative coherence layer (capability grounding) is informed but not the focus.
- **Asymmetric trust.** Same shape as commitment/init — trust the LLM with narrative output within strict template, fail loudly on miss, recover next turn. The bot does not gate input or modify Avrae state directly. Bot-stays-read-only invariant preserved.
- **Phase 6 strict-equality identity.** Turn-order sub-pressure relies on `controller_id` as Discord user ID (string equality, not name fuzzy-match). Character names from `dnd_combat_state.character_name` are written by `_handle_init_event` from Avrae's parsed plaintext, already canonicalized at parse time.
- **Phase 12 canonical world state.** Uninvolved. This directive operates on `dnd_scene_state` and `dnd_combat_state` only; doesn't touch NPC/location canon.
- **B2.1 attack template doctrine.** Indirect reuse — the strength calibration approach (imperative + positive-shape language + observed-emission tuning) inherits from B2.1's lessons.

**Filed, not sequenced** — per `feedback_no_pre_sequencing.md`. Pre-friends gating ship #3. Order of #2 vs #3 was re-decided after init's logs accumulated; same disposition for v2 candidates (HP-tracking parser, condition-tracking parser) — they earn their turn from this ship's observed misses, not pre-design.
