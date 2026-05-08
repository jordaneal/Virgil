# Consequence Surfacing Directive — Design Spec v2

**Status:** ✅ SHIPPED Session 16 (May 3, 2026) — v1 live in `dnd_engine.py`, `consequence_extractor.py`, `dnd_orchestration.py`, `discord_dnd_bot.py`. 249 new test assertions across `test_dnd_consequences.py`, `test_consequence_extractor.py`, `test_consequence_directive.py`, `test_consequence_command.py` — all green. This document remains the design reference; tuning surfaces (promotion thresholds, parser precision) are calibrated against logs going forward.
**Pattern:** Advisory parser (capture, dual-pass) + directive composition (surfacing)
**Track:** Track 3 (directive layer) — Session 16 design pass, post-Phase 6, post-THE_GOAL.md
**Review:** Session 16 review pass locked all §1 decisions and resolved every open question. See §13 for the decision log.

---

## 1. Locked decisions (post-review)

These define the shape of v1. Anything below this section is implementation detail consistent with these decisions.

1. **NPC-bound consequences only.** Faction-bound, location-bound, and item-meaningfulness consequences are filed for separate specs and not blended into v1.

2. **Capture is dual-pass, not single-blended.** Two parsers run sequentially, each on a separate text window:
   - **Player pass** reads `player_text`. Captures commitments, actions, and social acts the player initiates.
   - **DM pass** reads `dm_text`. Captures world reactions, fallout, and environmental shifts the DM narrates.

   Both use the same kind taxonomy. Each capture is tagged at ingestion with its source channel (`player` or `dm`). A single blended parser is explicitly rejected — it creates self-reinforcing hallucination loops where a player commitment, a DM narration of that commitment landing, and the parser then re-capturing the same event inflate one act into multiple consequences. Channel separation preserves the mechanics-vs-narrative invariant from `VIRGIL_MASTER.md`.

3. **Kind taxonomy locked at six. Definitions are load-bearing — implementations and parser prompts must use these definitions verbatim:**
   - **threat** → credible future harm or pressure (not executed action)
   - **mercy** → restraint when harm was available
   - **cruelty** → harm exceeding necessity
   - **betrayal** → violation of trust/expectation
   - **promise** → explicit commitment affecting future state
   - **alliance** → mutual alignment / shared objective formation

   These six are the floor, not a starting point. Don't expand. Don't merge `cruelty` and `betrayal` — they produce different NPC reactions (gratuitous harm vs. trust violation). `debt` is NOT a kind — it is a derived state from `promise` + `alliance` + `betrayal` history. If `debt` becomes load-bearing later, build it as a derived metric over these six, not as a captured kind.

4. **Severity is a 1–3 numeric tag emitted by the parser at capture.** Every consequence has a severity. The numeric meaning is parser-judged, not code-baked, so it stays tunable from logs without source changes:
   - 1 — minor / implied / scene-bound
   - 2 — notable / direct / scene-shifting
   - 3 — major / paradigm-shifting / plot-defining

   These are descriptive anchors for the parser prompt, not enforced thresholds in code. The validator only enforces the `[1,2,3]` range.

5. **Surfacing is directive layer, not narrative injection.** The directive emits imperative pressure surfacing latent consequences; the LLM owns the prose. Same architectural pattern as the pacing and central-thread directives.

6. **Multi-fire ordering: severity (descending) then recency (descending), capped at 3.** When more than three active consequences are relevant in a turn, drop lowest-severity rows first; ties broken by older `last_surfaced_turn`. Six in one block is too many — the LLM weights one and skims the rest. Three preserves narrative weight per consequence.

7. **Promotion thresholds are AND-ed across three axes:**
   - `surface_count >= 3` — the LLM has had it surfaced at least three times
   - `distinct_surface_turns >= 2` — those surfacings span at least two distinct turns
   - `(current_turn - first_seen_turn) >= 10` — at least ten turns of campaign time have passed since first capture

   The distinct-turns axis prevents one heated multi-emit conversation from falsely promoting a fresh consequence.

8. **Promotion graduates the consequence into the NPC's `notable_traits` field.** v1 ships with the consequence remaining in BOTH the table (`status='promoted'`) AND the prompt via the NPC block. This is acknowledged double-encoding — see §7.5 for the v2 architectural direction (`DB is source of truth, prompt is projection`).

9. **Strict canonical resolution at capture.** A consequence whose target cannot be resolved to a `dnd_npcs.id` is rejected with a log line. No substring fallback. No fuzzy matching. Same rule as Phase 6.

10. **Single-write-path invariant holds.** Only the validator writes capture data. The directive layer writes only `surface_count` / `last_surfaced_*` / `last_seen_turn` / `distinct_surface_turns` on emit. The promotion job writes only `status='promoted'`, `promoted_at`, and the trait append. No other code path mutates `dnd_consequences`.

11. **No retroactive capture in v1.** Forward-only. Past consequences in conversation history are not back-filled.

12. **Last-write-wins per `(campaign_id, npc_id, kind)`.** A second capture of the same consequence updates the existing row: severity goes to MAX(existing, new), `sources` accumulates the new channel, `summary` and `captured_*` last-write-wins, `first_seen_turn` is immutable. Promoted rows reject re-capture (logged, no write).

13. **PC contamination guard reused.** Consequences targeting a bound PC are refused at the validator (same `names_overlap` check used in `npc_upsert`).

14. **Composition order in `build_dm_context`:** consequence directive is placed AFTER central thread, BEFORE philosophy. It is a tactical directive (constraints on this turn's narrative move based on accumulated history); belongs with the tactical band, not above the philosophy frame.

15. **Debug surface (v1 minimal):** one read-only command — `/consequence list [npc]`. No add, remove, trace, or inspect commands in v1. (See §11.)

---

## 2. Goal — which THE_GOAL bullets this serves

Direct hits on the failure-mode list:

- ✅ **"NPCs we wronged should still be wronged."** Central failure mode v1 targets. The NPC row currently carries description but no captured-event memory. The directive surfaces what the player did, not just who the NPC is.
- ✅ **"Choices should matter later, not just in the moment."** Consequences are queued at capture time and surface 0–N future turns later. The "later" is structural, not LLM-attentional.
- ✅ **"If the world reacts the same to mercy as it does to slaughter, we've failed."** v1 captures both axes (mercy and cruelty are separate kinds with distinct definitions); the directive emits distinct posture pressure for each.
- ✅ **"Failure should create story, not dead ends."** Failed actions that produce consequences (a botched intimidation that becomes a grudge, a failed promise that becomes betrayal) get captured and surface as future texture.
- ✅ **"The session three weeks from now should remember what happened tonight."** Consequences live in canonical SQLite, not in conversation history. They survive context resets.

Indirect hits:
- **"Player agency has to survive the AI."** Player threats become structurally weighted by writing them into canonical state and surfacing them later.
- **"Multiplayer should feel collaborative."** Conflicting per-player commitments to the same NPC (one threatened, one negotiated) are captured separately by the player parser and both surface; the NPC reacts to the *party*, not the most recent speaker.

Bullets v1 explicitly does NOT serve (filed for separate specs):
- "Hidden lore... an NPC who lied weeks ago, secrets pieced together over months." — needs a contradiction/lie tracking layer.
- "Reputations should form" — needs faction rollup.
- "Off-combat skills to matter." — capability layer (S9) territory.

---

## 3. Architecture pattern

### Where it sits

```
                    Player message arrives
                            │
                            ▼
             [DM narration generated, posted to Discord]
                            │
                            ▼
             ┌──────────────────────────────────────┐
             │  POST-NARRATION INGESTION            │
             │                                      │
             │   extract_scene_updates  (existing)  │
             │   npc_extractor          (existing)  │
             │ + extract_consequences_player  (NEW) │  ← reads player_text
             │ + extract_consequences_dm      (NEW) │  ← reads dm_text
             └──────────────────────────────────────┘
                            │
                            ▼
                     Canonical SQLite
                  (dnd_consequences row(s))
                            │
                            ▼
                    [next turn begins]
                            │
                            ▼
             ┌──────────────────────────────────────┐
             │  build_dm_context                    │
             │  (prompt assembly)                   │
             │                                      │
             │   compute_pacing_directive  (existing)│
             │   compute_central_thread    (existing)│
             │ + compute_consequence_directive  (NEW)│
             │   apply_philosophy_layer    (existing)│
             └──────────────────────────────────────┘
                            │
                            ▼
                       LLM narration
```

### What's new

- One new SQLite table: `dnd_consequences`.
- Two parser instances of the advisory pattern:
  - `extract_consequences_player(player_text, ...)` — bound parser focused on player intent/action.
  - `extract_consequences_dm(dm_text, ...)` — bound parser focused on world reactions/fallout.
- One new directive function: `compute_consequence_directive(active_consequences, recent_npcs, current_location_id)`.
- Validator helpers: `consequence_upsert`, `consequence_promote`, `consequence_promotion_eligible`.
- Engine queries: `get_active_consequences(campaign_id, npc_ids=None, limit=None)`, `consequence_list_for_command(campaign_id, npc_canonical=None)`.
- One Discord command: `/consequence list [npc]`.

### What's reused

- LLM call infrastructure (`cloud_router`).
- `dnd_npcs.id` resolution via `canonicalize_name` (Phase 6 work).
- `names_overlap` helper for the PC contamination guard.
- Directive composition site (`build_dm_context`) — adds one block, no structural change.
- Pacing-style log line conventions (`consequence_captured:`, `consequence_directive:`, `consequence_rejected:`, `consequence_promoted:`).

### What's NOT changed

- `dnd_npcs` schema — no new columns. (Promotion writes into the existing `notable_traits` field with a bracketed prefix.)
- `extract_scene_updates` — separate concern.
- Skeleton/canon authoring path — skeleton.md cannot pre-author consequences in v1.

### Why dual-pass and not single blended

A single parser reading both `player_text` and `dm_text` simultaneously creates a hallucination loop:

1. Player says "I threaten Reginald."
2. DM narrates "Reginald goes pale and steps back."
3. Single parser reads both windows together, sees the threat *and* the visible fallout, and may capture two events: one from the player text, one from the DM narration. Or it may capture one with inflated severity because both windows reinforce each other.

Dual-pass with separated windows means each parser only sees its own channel. The player parser sees the threat once. The DM parser sees the fallout (which may be a different consequence, e.g., the DM narrates Reginald committing to compliance — the system can capture that as a `promise` made by the NPC if/when v2 extends the schema for NPC-side commitments; v1 captures only player-side rows but the dual channel separation is established now to avoid retrofit later).

The architectural benefit even where v1 produces overlapping captures: the `sources` field tracks ingestion provenance, so we can debug "was this consequence player-attested, DM-attested, or both?" without reading conversation history.

---

## 4. Data model

### `dnd_consequences` table

```sql
CREATE TABLE IF NOT EXISTS dnd_consequences (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id              INTEGER NOT NULL,
    npc_id                   INTEGER NOT NULL,
    kind                     TEXT    NOT NULL,    -- one of the 6 locked kinds (§1.3)
    summary                  TEXT    NOT NULL,    -- imperative phrase, ≤120 chars
    severity                 INTEGER NOT NULL,    -- 1, 2, or 3 (parser-judged, MAX on upsert)
    sources                  TEXT    NOT NULL,    -- comma-separated, sorted: 'player' | 'dm' | 'dm,player'
    captured_at              TEXT    NOT NULL,    -- ISO timestamp, last-write-wins on upsert
    captured_turn            INTEGER NOT NULL,    -- last-write-wins on upsert
    first_seen_turn          INTEGER NOT NULL,    -- IMMUTABLE after insert (for arc reconstruction)
    last_seen_turn           INTEGER NOT NULL,    -- max(captured_turn, last_surfaced_turn) — most recent activity
    last_surfaced_at         TEXT,
    last_surfaced_turn       INTEGER,
    surface_count            INTEGER NOT NULL DEFAULT 0,
    distinct_surface_turns   INTEGER NOT NULL DEFAULT 0,
    status                   TEXT    NOT NULL DEFAULT 'active',   -- active | promoted
    promoted_at              TEXT,
    UNIQUE(campaign_id, npc_id, kind)
);
CREATE INDEX idx_consequences_campaign ON dnd_consequences(campaign_id);
CREATE INDEX idx_consequences_active ON dnd_consequences(campaign_id, status);
CREATE INDEX idx_consequences_npc ON dnd_consequences(campaign_id, npc_id);
```

### Field rationale

- **`kind`** — closed set of 6, validator rejects any other value.
- **`summary`** — short directive-ready phrase (e.g., `"player threatened to burn the inn down"`). 120-char cap prevents prompt bloat.
- **`severity`** — parser judgment, MAX-on-upsert. Sort key for the multi-fire cap.
- **`sources`** — comma-separated, sorted alphabetically for determinism. Upsert appends if the new channel isn't already present. Format examples: `'player'`, `'dm'`, `'dm,player'`.
- **`captured_at` / `captured_turn`** — last-write-wins. Reflect the most recent capture event.
- **`first_seen_turn`** — immutable. Set on first INSERT, never updated. Forward-compatible for arc reconstruction, memory tiering, and decay analysis even though v1 logic only reads it for the promotion threshold.
- **`last_seen_turn`** — `max(captured_turn, last_surfaced_turn)`. Single field for "when was this consequence last active?" — convenient for the debug command and future memory tiering.
- **`distinct_surface_turns`** — supports the promotion distribution check (§7.1). Increment only when a surface emit happens on a turn different from `last_surfaced_turn`.
- **`status`** — `'active'` writes through the directive; `'promoted'` is terminal. v1 has no `'expired'`.
- **`UNIQUE(campaign_id, npc_id, kind)`** — enforces last-write-wins per kind+target. Prevents directive bloat from repeated commitments.

### Why no `target_kind` discriminator

v1 is NPC-only (locked decision §1.1). When faction-bound and location-bound consequences are added later, the choice is between (a) a separate table per target type or (b) a polymorphic refactor with migration. That decision belongs to the next spec, not this one.

### Turn counter

The promotion math depends on a per-campaign monotonic turn counter. Add a `turn_counter` column to `dnd_scene_state` if not already present (idempotent ALTER, default 0). Increment in `_dm_respond_and_post` after a successful narration.

---

## 5. Capture layer

### 5.1 Trigger

After narration completes, `_dm_respond_and_post` calls (in order):
1. `extract_scene_updates` (existing)
2. `npc_extractor` (existing)
3. `extract_consequences_player(player_text, campaign_id, recent_npcs, current_turn)`  — NEW
4. `extract_consequences_dm(dm_text, campaign_id, recent_npcs, current_turn)`  — NEW
5. `_dnd_increment_turn_counter(campaign_id)`  — NEW (advances `dnd_scene_state.turn_counter`)

Both consequence parsers fire AFTER scene-state and NPC extraction (so canonical NPC IDs are populated for resolution) and BEFORE the next turn's `build_dm_context` (so directives see fresh consequences immediately on the next turn).

### 5.2 Kind taxonomy

The six kinds with their locked definitions (§1.3 — must be embedded verbatim in both parser prompts):

| kind        | definition                                                        |
|-------------|-------------------------------------------------------------------|
| `threat`    | credible future harm or pressure (not executed action)            |
| `mercy`     | restraint when harm was available                                 |
| `cruelty`   | harm exceeding necessity                                          |
| `betrayal`  | violation of trust/expectation                                    |
| `promise`   | explicit commitment affecting future state                        |
| `alliance`  | mutual alignment / shared objective formation                     |

The parser prompt instructs: *if no clear consequence per these definitions, return empty array.* High precision over recall. Most turns produce zero consequences.

### 5.3 Player-pass parser (`extract_consequences_player`)

**Input window:** the player's last message only (`player_text`).
**Parser focus:** the player's commitments, social acts, and acts initiated against an NPC.
**Source tag at capture:** `'player'`.

**Output schema (LLM):**
```json
{
  "consequences": [
    {
      "target": "Reginald the Innkeeper",
      "kind": "threat",
      "severity": 2,
      "summary": "player threatened to burn the inn down if Reginald spoke of their visit"
    }
  ]
}
```

### 5.4 DM-pass parser (`extract_consequences_dm`)

**Input window:** the DM's last narration (`dm_text`).
**Parser focus:** world reactions, fallout, and environmental shifts the DM narrated. Examples:
- DM narrates an NPC granting trust the player did not explicitly request → `alliance` (severity 1–2, source `dm`)
- DM narrates an NPC being broken/cowed by what the player did → `cruelty` (severity 2–3, source `dm`) — even if the player parser missed it
- DM narrates an NPC swearing revenge → `threat` from the NPC's side (recorded under same kind taxonomy because the directive surfaces *consequence weight*, not directional intent — the NPC's threat is functionally equivalent for what should color future scenes)

**Source tag at capture:** `'dm'`.

The DM-pass parser prompt explicitly instructs: *do NOT re-capture events the player initiated; capture only consequences emergent from the DM's narration of world response.* This is the hallucination-loop guard. Validation cannot fully enforce it (the parser is an LLM with judgment) but the prompt biases against re-capture.

### 5.5 Validator

For each proposed consequence (from either parser):

1. **Resolve target** via strict canonical lookup against `recent_npcs` and `dnd_npcs`. No substring fallback.
2. **Reject** with a log line if any of the following:
   - Target unresolvable → `consequence_rejected reason=unresolved_target target='X' source={player|dm}`
   - Target overlaps a bound PC → `consequence_rejected reason=pc_match target='X' source=...`
   - `kind` not in the closed set → `consequence_rejected reason=invalid_kind kind='X' source=...`
   - `severity` not in `{1, 2, 3}` → `consequence_rejected reason=severity_out_of_range severity=N source=...`
   - `summary` length > 120 → `consequence_rejected reason=summary_too_long len=N source=...`
   - `summary` empty after strip → `consequence_rejected reason=summary_empty source=...`
3. **Upsert** via `consequence_upsert(campaign_id, npc_id, kind, summary, severity, source, current_turn)`:
   - If `(campaign_id, npc_id, kind)` exists with `status='active'`:
     - `summary` ← new value
     - `severity` ← `MAX(existing, new)`
     - `sources` ← sorted-merge of existing + new channel
     - `captured_at` ← now
     - `captured_turn` ← `current_turn`
     - `last_seen_turn` ← `MAX(captured_turn, last_surfaced_turn or 0)`
     - `first_seen_turn` UNCHANGED
   - Else if exists with `status='promoted'` → log `consequence_rejected reason=already_promoted` and SKIP.
   - Else INSERT a fresh row:
     - `first_seen_turn = captured_turn = last_seen_turn = current_turn`
     - `sources = source`
     - `surface_count = 0`, `distinct_surface_turns = 0`
4. **Log success:** `consequence_captured campaign={X} npc_id={Y} kind={K} severity={S} source={src} summary_len={N}`

### 5.6 Cross-campaign isolation

All queries scope `WHERE campaign_id = ?`. Tested same as `dnd_npcs` cross-campaign tests.

---

## 6. Surfacing layer

### 6.1 Function signature

```python
def compute_consequence_directive(
    active_consequences: list[dict],
    recent_npcs: list[dict],
    current_location_id: int | None = None,
) -> str:
    """Return imperative consequence directive text, or '' when silent.

    Filters to consequences whose npc_id is in recent_npcs OR whose target
    NPC has location_id == current_location_id. Sorts by severity desc
    then last_surfaced_turn desc. Caps at 3. Returns '' when none qualify.
    """
```

### 6.2 Relevance filter

A consequence fires in the directive only when:
- Its `npc_id` matches an NPC in `recent_npcs` (the S3 "Recently active NPCs" list, derived from `dnd_npcs.last_mentioned`), OR
- Its `npc_id` matches an NPC at `current_location_id` (NPC has `location_id == current_location_id`).

Off-screen consequences accumulate silently until the relevant NPC re-enters the scene.

### 6.3 Multi-fire ordering and cap

Among relevant active consequences:
1. Sort `severity` descending (3 first).
2. Tie-break by `last_surfaced_turn` descending (most-recently-emitted first; NULL treated as oldest).
3. Take the top **3**.

Cap of 3 is a locked decision (§1.6) — six in one block dilutes the LLM's attention; three preserves narrative weight.

### 6.4 Output format

```
=== PENDING CONSEQUENCES ===
The following weight what the named NPCs feel and how they posture:
  - Reginald the Innkeeper [threat, sev 2]: player threatened to burn the inn down if he spoke of their visit
  - Lira [mercy, sev 3]: player spared her life despite her betrayal at the bridge
  - Thorne [betrayal, sev 1]: player accepted his coin then left without delivering the package
Let these color the scene through NPC posture, dialog, and choices. Do not have the DM narrator restate them as "remembered consequences" — manifest them. An NPC who was threatened is wary, watches the door, speaks carefully. An NPC shown mercy may show quiet recognition, may extend trust, may be unable to meet the player's eye. An NPC betrayed remembers the betrayal in tone, in the held grudge, in what they no longer offer.
```

The `[kind, sev N]` tags are present in the directive text so the LLM has a structured cue per row, not just prose.

### 6.5 Composition order in `build_dm_context`

Locked at §1.14. Final prompt order around the new directive:

1. Scene state (existing)
2. Recently active NPCs (S3, existing)
3. Active quests (existing)
4. Capability verdicts (existing)
5. Roll directive (existing)
6. Pacing directive (existing)
7. Central thread (existing)
8. **Consequence directive (NEW)**
9. Philosophy (existing)

Rationale: consequences are *operational* like pacing and central thread — they constrain what's true *this turn*. Philosophy frames *how* the LLM should write — it interprets the operational directives. Consequences before philosophy means the philosophy frame applies to consequence integration.

### 6.6 Update on emit

When the directive includes a row, the writer also:
- `surface_count += 1`
- `last_surfaced_at` ← now
- `last_surfaced_turn` ← `current_turn`
- `last_seen_turn` ← `MAX(captured_turn, last_surfaced_turn)` — i.e., always advances to current_turn during emit since current_turn is the surface
- `distinct_surface_turns += 1` IF and only if `current_turn != previous_last_surfaced_turn`

Log line: `consequence_directive: emitted={N} kinds=[K1,K2,K3] severities=[S1,S2,S3] npcs=[id1,id2,id3]`.

---

## 7. Promotion (graduation to traits)

### 7.1 Thresholds

A consequence promotes from `active` → `promoted` when ALL three hold (§1.7):
- `surface_count >= 3`
- `distinct_surface_turns >= 2`
- `(current_turn - first_seen_turn) >= 10`

The distinct-turns axis prevents premature promotion from one heated multi-emit conversation.

### 7.2 Promotion runner

`maybe_promote_consequences(campaign_id, current_turn)` runs at the start of every `compute_consequence_directive` call, BEFORE the relevance filter. Promoted rows therefore never appear in the directive after they cross the threshold.

### 7.3 Promotion side effects

For each promoted row:
1. UPDATE `dnd_consequences` SET `status='promoted'`, `promoted_at=now()`.
2. APPEND to the target NPC's `notable_traits` field with a bracketed prefix, format:
   `"[promoted: {kind}] {summary}"`
   The bracketed prefix is parseable in case future code wants to mine promoted-from-consequence traits.
3. Log line: `consequence_promoted campaign={X} npc_id={Y} kind={K} surface_count={N} distinct_turns={D} age_turns={T}`.

### 7.4 Why graduate instead of expire-silent

A graduated consequence is folded into the NPC's *prose memory*. The NPC block is already in the prompt as canonical context, so the consequence's weight survives even after the structured directive stops firing it. Expiry-silent would feel like the NPC "forgot" once thresholds passed.

### 7.5 Double-encoding architectural note (v2 direction)

v1 ships with a known double-encoding: a promoted consequence lives in BOTH the `dnd_consequences` table (`status='promoted'`) AND the NPC's `notable_traits` field (which gets rendered into the prompt as part of the NPC block). This means the same fact can echo through the prompt via two paths.

The intended steady state for v2 is **DB is source of truth, prompt is projection**: the prompt block renders its content from the DB at build time rather than storing a separate denormalized representation. Future memory tiering (the deferred Phase 4 spec) will need to address this — most likely by deriving `notable_traits`-equivalent prompt content from a join of `dnd_npcs` + `dnd_consequences (status='promoted')` at render time, eliminating the static `notable_traits` text field as a parallel store.

This is filed, not solved, in v1. v1 ships with the double-encoding because the alternative (rebuilding the NPC block render path before any consequence layer can ship) is out of scope. Flagging the future direction here so the next spec touching memory tiering inherits the principle.

### 7.6 Threshold tunability

3 / 2 / 10 are intuition-calibrated, same regime as pacing tier thresholds. Tunable from logs. If observed friction shows promotion is too aggressive, raise; if consequences spam the prompt indefinitely, lower. The tuning surface is `consequence_promoted` log lines after several solo sessions.

---

## 8. Test plan

### 8.1 Engine layer (`test_dnd_consequences.py`)

- `consequence_upsert` insert path — fresh row, every field correct.
- Update path — same `(campaign, npc, kind)` updates `summary`, `captured_at`, `captured_turn`, `last_seen_turn`; `first_seen_turn` is unchanged.
- Severity MAX semantics — capture (sev=1), then capture (sev=3), severity is 3 after; capture (sev=2) afterward, severity stays 3.
- `sources` accumulation — first capture writes `'player'`; second capture from DM writes `'dm,player'` (sorted). Third capture from player keeps `'dm,player'`.
- Promoted row rejects re-capture — second capture returns sentinel, no write, log emitted.
- `get_active_consequences` excludes promoted and (future) expired rows.
- `get_active_consequences(npc_ids=[...])` filter.
- Cross-campaign isolation.
- `maybe_promote_consequences` promotes only rows meeting all three thresholds.
- **Distribution check:** 3 surfacings on the SAME turn do NOT promote (`distinct_surface_turns=1`).
- **Distribution check:** 3 surfacings spanning 2+ turns DO promote (when surface_count and age also satisfy).
- **Age check:** thresholds met but `current_turn - first_seen_turn < 10` does NOT promote.
- Promotion writes correct prefix format into `notable_traits`.
- Promotion is idempotent — running twice on already-promoted rows is a no-op.
- `first_seen_turn` is immutable across upserts.
- `last_seen_turn` is `max(captured_turn, last_surfaced_turn)` after upsert and after surface.

### 8.2 Validator (`test_consequence_extractor.py`)

- Player parser emits structured proposal → resolved → upserted with `source='player'`.
- DM parser emits structured proposal → resolved → upserted with `source='dm'`.
- Both parsers fire on the same `(npc, kind)` → single row, `sources='dm,player'`, severity is MAX of the two emits.
- Unresolved target → rejected with `unresolved_target`, no write.
- Invalid kind → rejected with `invalid_kind`.
- Severity out of `[1,2,3]` → rejected with `severity_out_of_range`.
- Summary > 120 chars → rejected with `summary_too_long`.
- Empty summary → rejected with `summary_empty`.
- PC name as target → rejected with `pc_match`.
- Multiple proposals in one parse — all valid ones written, invalid ones logged individually, no abort.

### 8.3 Directive (`test_consequence_directive.py`)

- No active consequences → returns `''`.
- Active consequence, NPC not in recent and not at current location → returns `''` (relevance filter).
- Active consequence, NPC in recent → directive includes that consequence's row.
- 4 relevant active consequences, severities [3,3,2,1] → directive includes top 3, drops the sev-1 row.
- 3 relevant rows all sev 2 → tie-breaks by `last_surfaced_turn` desc.
- Output format includes `[kind, sev N]` tag per row.
- Surface emit increments `surface_count`, `last_surfaced_at`, `last_surfaced_turn`, `last_seen_turn`.
- `distinct_surface_turns` increments only when current turn ≠ previous `last_surfaced_turn`.
- Promoted consequences excluded from directive.

### 8.4 Debug command (`test_consequence_command.py`)

- `/consequence list` returns all active and promoted rows for the current campaign, formatted per row spec.
- `/consequence list <npc>` filters to that canonical NPC's consequences.
- Empty result → user-facing "no consequences yet" message.
- Cross-campaign isolation — other campaigns' rows not shown.

### 8.5 Integration (light)

End-to-end: simulate a turn where the player parser captures a `threat`, the DM parser captures an `alliance` from the same NPC's response, the next turn's `build_dm_context` includes both rows in the consequence directive block.

### 8.6 Live verification

Solo test: contrive a consequence-bearing moment ("I tell Reginald I'll burn his inn down if he speaks of us"), verify `consequence_captured source=player` log line, advance one turn, verify `consequence_directive: emitted=...` log line includes Reginald's threat row, verify Reginald's posture in subsequent narration shifts.

Multiplayer verification deferred until the multiplayer table reaches that state (same gate pattern as Phase 6 §5).

---

## 9. Failure modes + mitigations

1. **Parser fabricates consequences from idle banter.** *Mitigation:* high-precision parser prompts (each pass tells the LLM "if uncertain, return empty"). Validator rejects unresolved targets — most fabrications won't resolve to canonical NPCs. `consequence_rejected reason=unresolved_target` log lines surface over-firing patterns for calibration.

2. **Directive over-fires — every scene reminds of every grudge.** *Mitigation:* relevance filter (NPC in recent OR present at current location) + cap-at-3 (§1.6) + promotion-graduation pulls stable consequences out of the directive band. If still heavy in observed logs, raise the relevance bar (e.g., NPC must be in recent-active within last N turns).

3. **Player roleplay-threats captured as real threats.** *Mitigation:* acknowledged risk. v1 trusts parser judgment per the locked definitions. If observed friction shows roleplay false-positives, future v2 may add a parser-side filter on canonical mode (skip capture during a flagged in-character roleplay state, if such a state is added).

4. **DM-pass parser re-captures events the player parser already wrote.** *Mitigation:* the DM-pass parser prompt explicitly forbids re-capture. The `sources` field accumulates so genuine multi-channel agreement just merges into one row (UNIQUE constraint on `(campaign, npc, kind)` enforces this). False multi-capture is the failure mode; it is logged via `consequence_captured source=dm` lines that can be cross-referenced against `source=player` lines in the same turn for calibration.

5. **NPC dies after a consequence is captured.** *Mitigation:* `get_active_consequences` LEFT JOINs `dnd_npcs` and skips rows where the NPC row is gone. Locked default — simpler than cascade-delete and avoids touching FK semantics.

6. **Prompt bloat from many active consequences.** *Mitigation:* relevance filter + cap-at-3 (§1.6). Hard architectural ceiling: directive emits at most 3 consequences per turn.

7. **Migration breaks on existing campaigns.** *Mitigation:* `CREATE TABLE IF NOT EXISTS` is idempotent. `dnd_scene_state.turn_counter` ALTER uses the PRAGMA-check + ALTER pattern from Phase 6. No data backfill — `turn_counter` defaults to 0; existing campaigns get zero historical consequences but new turns are captured immediately.

8. **Directive content escapes into player-visible narration.** *Mitigation:* same as central-thread — explicit phrasing in the directive text saying "do not have the DM narrator restate these as 'remembered consequences'". If observed friction shows the LLM regurgitating directive text verbatim, harden the philosophy doc with a "directive blocks are constraints, not script" line.

9. **Promotion thresholds incorrectly tuned.** *Mitigation:* tunable from logs (§7.6). 3 / 2 / 10 is the v1 calibration; raise or lower without code-shape changes.

10. **`distinct_surface_turns` ledger drifts from reality.** *Mitigation:* the increment-only-when-different logic in §6.6 is the single update path. Unit tests cover the boundaries. If drift surfaces, add a `consequence_health` log line that compares `distinct_surface_turns` against an audit query of distinct turns per row.

---

## 10. Migration impact

**Schema changes:**
- New table `dnd_consequences` (idempotent CREATE TABLE IF NOT EXISTS).
- `dnd_scene_state` gains `turn_counter` column if not present (PRAGMA-check + ALTER pattern from Phase 6).

**No data backfill.** Existing campaigns start with empty `dnd_consequences` and `turn_counter=0`. Forward-only.

**No removed code paths.** All additions are additive — advisory parsers, directive function, debug command, engine helpers.

**Cross-version safety.** Old code without the consequence directive can read the table (it just won't write). Old data without consequences runs through new code unchanged (empty queries return empty lists, directive returns `''`).

---

## 11. Debug surface (v1 minimal)

### 11.1 Command

```
/consequence list [npc]
```

Read-only. Optional positional argument `npc` filters to that canonical NPC. With no argument, lists every consequence (active and promoted) for the current campaign.

### 11.2 Output format

One row per consequence, sorted by `first_seen_turn` ascending (oldest first). Each row displays:

- **first_seen_turn** (the source turn — when the consequence was first captured)
- **kind**
- **canonical NPC name** (resolved from `npc_id`)
- **severity** (1–3)
- **summary** (the directive-ready phrase)

Plus structural columns useful for tuning:
- **status** (`active` | `promoted`)
- **sources** (`player` | `dm` | `dm,player`)
- **surface_count**

Example output (Discord embed or formatted block):
```
Campaign 17 — consequences (12 active, 3 promoted):

T05  threat    Reginald the Innkeeper  sev 2  active     [player]      surf 2
T07  mercy     Lira                    sev 3  active     [dm,player]   surf 4
T11  betrayal  Thorne the Fence        sev 1  active     [player]      surf 1
T18  cruelty   Kael the Captain        sev 3  promoted   [player]      surf 3
...
```

### 11.3 What the command does NOT do

- No `/consequence add` — captures must come from the parser, not from operator entry. (If we add manual entry later, the LLM stops being the only proposer and the validator's contract changes.)
- No `/consequence remove` — too destructive for a system whose capture quality hasn't proven itself in logs. If a bad row is captured, the operator can confirm it via `list` and a fix at the parser level (not row-level deletion) is the right response.
- No `/consequence inspect` or `/consequence trace` — `list` with the `npc` filter shows everything those would show.

### 11.4 Permissions

Same scoping as `/scenestate` and other DM peek commands — bound to the campaign's owner / operator. No special new permission model.

### 11.5 Why minimal

Debug commands are a tax: every command needs a help string, error handling, parsing, and a contract that's hard to break later. v1 ships the minimum that lets the operator answer "is the parser capturing the right things?" — that's the only question worth answering before the system has logs to study. If a richer surface is needed later, add then.

---

## 12. Out of scope (separate specs / separate layers)

These are deliberately NOT in v1.

- **Faction-bound consequences.** Wronging a member of the Red Sash thieves' guild should propagate to the guild, not just the individual. Needs `dnd_factions` table + faction membership + faction-scoped surfacing.
- **Location-bound consequences.** Returning to a village where the players slaughtered the militia should change reception. Needs location-as-target on consequences + location-aware surfacing.
- **Item-bound meaningfulness.** Lira's signet ring should feel different from a +1 ring of protection. Items meaningfulness layer.
- **Curiosity-reward layer.** Hidden lore, attentiveness rewards, lies-pieced-together. Different mechanism (knowledge tier).
- **Skeleton-pre-authored consequences.** Allowing skeleton.md to declare initial consequence state at session 0.
- **`/consequence remove` / `/consequence add`.** Operator-side mutation. v1 has only `list`.
- **Cross-campaign telemetry / shared learning.** No.
- **DM-side commitments.** v1's DM-pass captures consequences targeting the player's relationship with NPCs, but does not (yet) capture commitments NPCs make in DM narration to a separate `npc_promises` ledger. v2 may extend.

---

## 13. Decisions log (Session 16 review)

The original spec surfaced six open questions and 8 locked decisions. Review pass resolved every open item; the resolutions are reflected in the body sections referenced below.

| Original question / decision | Resolution                                                             | Spec section |
|------------------------------|------------------------------------------------------------------------|--------------|
| Kind taxonomy count          | Locked at 6, definitions verbatim                                      | §1.3, §5.2   |
| Kind taxonomy expansion      | No expansion. `debt` is derived, not captured                          | §1.3         |
| Promotion thresholds         | 3 surfacings + 10 turns + distribution check (≥2 distinct turns)        | §1.7, §7.1   |
| Multi-fire ordering          | Severity desc, then recency desc, capped at 3                          | §1.6, §6.3   |
| Severity baked vs parser     | Parser-judged 1–3, MAX-on-upsert                                       | §1.4, §4     |
| DM-narrated capture          | Dual-pass with separated channels (player + dm), tagged at ingestion   | §1.2, §3, §5 |
| Debug surface                | `/consequence list [npc]` only — read-only, minimal                    | §1.15, §11   |
| Composition order            | After central thread, before philosophy                                | §1.14, §6.5  |
| `first_seen_turn`/`last_seen_turn` | Added to schema (forward-compatible for memory tiering)          | §4           |
| Double-memory encoding       | Acknowledged in v1; flagged as `DB is source of truth, prompt is projection` for v2 | §1.8, §7.5 |

The original "Decision points needing review" section is retired — every point is now resolved and folded into §1.

---

## Appendix — relationship to other unspeced layers

This spec is one of multiple candidate layers addressing THE_GOAL's "no current lever" failure modes (as filtered through `feedback_no_playtest_gate.md`). The others currently filed:

- **Reputation / faction layer** — group-level memory, not just individuals.
- **Curiosity reward layer** — hidden lore, attentiveness rewards, lies-pieced-together.
- **Item meaningfulness layer** — unique items feel meaningful, not interchangeable with statline gear.
- **Memory tiering / arc summarization** — the deferred Phase 4 spec; needs the above to know what's load-bearing.

**Filed, not sequenced.** Per `feedback_no_pre_sequencing.md`: this list is a menu of candidates. Ordering between them will be re-decided after this spec ships v1 and the parser's behavior in logs (especially the dual-pass channel separation and capture quality across the six kinds) tells us which layer has earned next priority. Sequence proposals across unbuilt specs are dependency trees, not commitments.
