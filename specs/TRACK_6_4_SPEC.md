# Track 6 #4 — NPC Stat Hydration at Init-Add — Design Spec v1 (DRAFT)

**Status:** SPEC COMPLETE — Amendment pass #3 applied (2026-05-07). §11.A–§11.M are LOCKED. All three pre-Session-3 Avrae verification gates RESOLVED: §11.K (VERIFIED), §11.D sync-hint DROPPED (architectural decision), §11.M HP-status-token rule LOCKED. Single-hook architecture (Hook 2 only). Session 3 implementation may begin.
**Pattern:** New pure-function hydration module (`npc_hydrator.py`), nullable stat columns on `dnd_npcs`, hook integration into the existing init-list parse path, one new DM-facing slash command. Doctrine §59 sibling of the directive family.
**Track:** Track 6 #4 — the final bone before the post-checkpoint pivot to motion-system ships (F-54 stagnation drift territory).
**Failure mode this closes:**
- **F-49 (operational channel)** — LLM-fabricated NPCs entering combat with no Avrae backing. Track 7 #2 (`narration_verifier.py`, SHIPPED) closes the *fabrication* channel — narration that introduces non-canonical combatants is refused before posting. Track 6 #4 closes the *operational gap*: legitimate NPCs that the DM intentionally adds via `!init add` enter the initiative tracker with default HP/AC and no attacks. The DM currently resolves this with a manual, syntax-heavy flow in `#dm-aside` + `#dm-narration`. Hydration automates that flow.

---

## 1. Proposed decisions (NOT yet locked — see §11)

1. **v1 shipping shape is (b)+(c) via a single hook (§11.J revised).** `_handle_init_list_event` fires on every `!init list` parse — the HP-status token in each combatant's embed line classifies routing: `<None>` → hydrate (NPC needs Virgil-managed stats); non-`<None>` → `npc_register_avrae_madd()` (Avrae owns the mechanics). NPCs that are stat-incomplete (shape b: row exists, stats NULL) or absent entirely (shape c: no row) trigger hydration. Shape (a) skeleton stat hints ships as v1.x. A small race window remains (player narrates after `!init next` but before `!init list`); accepted as v1 risk per §11.J.

2. **CR estimation source for v1: DM-provided via `/hydrate npc:<name> cr:<band>`.** When hydration fires on an NPC with no CR hint, the bot sends a one-shot message to `#dm-aside` prompting the DM for CR. If no reply arrives before the next `!init list` parse, fallback to CR 1/4 with `source=generic_fallback` in telemetry (see decision 7). LLM-inferred CR is not a valid source: LLM in the mechanical estimation path violates Doctrine §1. Skeleton-declared CR hints (v1.x) will supersede the prompt once Shape (a) ships.

3. **Default stat block source: 5e SRD CR-band tables, embedded in `npc_hydrator.py` as a lookup dict.** CR band string → `(hp_max, ac, attack_bonus, damage_dice, save_bonus, init_mod)`. No external lookup, no API call, no LLM involvement. See Appendix A for the full table.

4. **Hydration writes to `dnd_npcs` only. No new bot→Avrae write boundary. No sync hint.** Hydration populates the bridge layer's canonical store (new stat columns on `dnd_npcs`). Avrae's tracker remains Avrae's responsibility. The bot does not surface an Avrae sync hint — `!init modify` does not exist as an Avrae subcommand (verified), and the sync-hint feature is dropped on architectural grounds: Virgil's bridge layer reads Avrae state, never writes to it (§11.D).

5. **The hook path uses idempotent NULL-fill; `/hydrate` is authoritative-replace.** Hook-sourced hydration (`_handle_init_list_event`) writes only to NULL stat fields — DM-authored values and prior hydration results are always preserved. Re-running the hook on a fully-hydrated NPC is a no-op (`source=miss`). The `generic_fallback` hook path deliberately leaves `hp_max` NULL so a subsequent `/hydrate` with the real CR can fill it. Exception: the `/hydrate` slash command (`source='explicit_hydrate'`) always overwrites all six stat fields — it is the DM's authoritative correction path and treats generic_fallback placeholders as non-authoritative (§11.H lock).

6. **Controller authority is unchanged.** The player who fires `!init add` retains Avrae controller authority over the NPC. Hydration provides stat backing in the bridge layer; it does not reassign controller. AI-driven NPC attacks (the payload use case for the stat block) are explicitly v2.

7. **Failure mode when CR is unknown: prompt DM in `#dm-aside`, fall back to CR 1/4 without writing `hp_max`.** Three-part behavior: (a) bot posts to `#dm-aside`: "Hydration needed: `{name}` just entered initiative with no stats. What CR? `/hydrate npc:{name} cr:N`"; (b) writes CR-band defaults for `ac`, `attack_bonus`, `damage_dice`, `save_bonus`, `init_mod` using CR 1/4; (c) deliberately leaves `hp_max` NULL so a subsequent `/hydrate` with the real CR can fill it correctly. Telemetry: `source=generic_fallback`. This keeps combat moving while surfacing the gap to the DM explicitly.

8. **New stat columns on `dnd_npcs` are nullable ALTER TABLE additions.** Seven columns: `hp_max INTEGER`, `ac INTEGER`, `attack_bonus INTEGER`, `damage_dice TEXT`, `save_bonus INTEGER`, `init_mod INTEGER`, `cr_str TEXT`. All nullable. Migration block follows the existing `PRAGMA table_info` + `ALTER TABLE ADD COLUMN` pattern in `ensure_tables()`. No existing rows are affected; hydration fills them on first encounter.

9. **Pure-function signature: `hydrate_npc_stats(cr_str: str) → dict`.** New module `npc_hydrator.py`. Returns `{'hp_max': int, 'ac': int, 'attack_bonus': int, 'damage_dice': str, 'save_bonus': int, 'init_mod': int}`. Raises `ValueError` on unrecognized CR. Caller (`npc_hydrate_stats()` engine helper) performs the DB write after applying the idempotent fill rule.

10. **Telemetry: always-fire log line per Doctrine §59.** `hydration: campaign={N} npc='{name}' source={skeleton|hook|adhoc|miss|generic_fallback} stats_filled={hp,ac,atk,dmg,save,init|none} cr={...|none}`. Fires once per combatant on every `!init list` parse — even when `source=miss` (no write needed). Empirical baseline for fill-path vs. miss-path frequency.

---

## 2. Goal and context

### The split with Track 7 #2

F-49 has two channels:

- **Fabrication channel (CLOSED by Track 7 #2).** The LLM invents NPCs (Silent Beast, Keeper of the Vein) inside narration. `narration_verifier.py` detects non-canonical names in combat-active narration and refuses the post. The LLM cannot narrate fabricated combatants.

- **Operational gap (this spec).** The DM legitimately types `!init add Garrik`. Garrik exists mechanically in Avrae's tracker with default HP/AC. No attacks. The persistence directive shows "Garrik — HP unknown." The combat experience is degraded. When the player who triggered init tries to drive Garrik's attacks (controller authority), there are no stat expressions to drive them from. Track 6 #4 automates the stat generation that the DM currently performs manually.

The disposition line from F-49: *"verification refuses fabrication; hydration enables legitimate addition."* The two ships are complementary.

### Why this is a bone, not clothes

Post-Track-7, `adjudicator._gate_combat` requires `mode='combat'` AND `combatants snapshot non-empty` AND `active_turn populated`. The gate passes when Garrik is in the tracker — but the persistence directive and combat redirect directive both see "HP unknown" for all stat-incomplete NPCs. With no stats, Garrik is mechanically present but narratively hollow. Hydration makes him narratively complete.

### THE_GOAL alignment

- *"I want combat to be fun. I want to feel something when I kill an enemy."* — An enemy with known HP, AC, and real attack expressions is emotionally different from a placeholder. Stats give the persistence directive concrete material.
- *"NPCs we wronged should still be wronged."* — An NPC with stats has a presence the world can model. The AI attack path (v2) depends on this infrastructure.

---

## 3. Architecture pattern

### Where hydration sits in the call stack

Single hook — `_handle_init_list_event` — per §11.J revised:

```
DM types: !init add Garrik  (or !init madd Goblin -name "Garrik")
               │
               ▼
    Avrae updates initiative tracker
               │
               ▼
    DM (or Avrae auto-posts): !init list
               │
               ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │  HOOK — _handle_init_list_event() in discord_dnd_bot.py        │
    │                                                    (EXISTING)  │
    │  parse_init_list_embed() → combatants list                     │
    │    each row includes: name, hp_current, hp_max, status_token   │
    │  update_combatants_from_init_list() → dnd_combatant_state      │
    │                                                                │
    │  step 2.5 — hydration + classification scan (NEW):             │
    │  for each combatant:                                           │
    │    bound PC?                 → source=bound_pc_skip, skip      │
    │    status_token == '<None>'  → hydration path (below)  (§11.M)│
    │    status_token != '<None>'  → npc_register_avrae_madd()       │
    │                                source=avrae_madd, skip (§11.M)│
    │                                                                │
    │  log: init_list_parsed: ...                                    │
    └─────────────────────────────────────────────────────────────────┘
               │
               ▼ (§11.L lock: caller-side cr_str=None decision)
    For each <None>-status NPC needing hydration:
    ┌─────────────────────────────────────────────────────────────────┐
    │    npc = npc_get_by_name(campaign_id, name)  (None → ad-hoc)  │
    │    if fully hydrated → log source=miss, skip                   │
    │    cr_hint = npc['cr_str'] if npc else None                    │
    │                                                                │
    │  cr_hint known? ──yes──► npc_hydrate_stats(..., source='hook') │
    │  cr_hint None?  ──────► CALLER posts to #dm-aside: CR prompt  │
    │                          THEN calls npc_hydrate_stats(...,     │
    │                              source='generic_fallback')        │
    │                          (partial fill — no hp_max written)   │
    └─────────────────────────────────────────────────────────────────┘
               │
               ▼
    npc_hydrate_stats() in dnd_engine.py              (NEW — engine helper)
      hydrate_npc_stats(cr_str) → stats_dict          (PURE — npc_hydrator.py)
      read NPC row; apply source-based fill rule:
        hook sources → WHERE col IS NULL (idempotent fill)
        explicit_hydrate (/hydrate cmd) → full overwrite (§11.H lock)
      engine never resolves cr_str=None → _FALLBACK_CR (§11.L lock)
      log: hydration: campaign={N} npc='{name}' source=... status_token=...
               │
               ▼
    Next player narration:
    persistence directive reads dnd_combatant_state.hp_current/hp_max  (Avrae-sourced)
    advisory context reads dnd_npcs.ac, attack_bonus, damage_dice      (hydration-sourced)
    advisory context for avrae_madd NPCs: "(mechanics: Avrae monster entry)" (§11.M)
    LLM prompt context: "Garrik — HP unknown (AC 13)"  [AC now hydrated; HP still Avrae's]
```

### What's new

| Artifact | Location | Purpose |
|----------|----------|---------|
| `npc_hydrator.py` | new module | Pure function `hydrate_npc_stats(cr_str) → dict`; CR-band table; `normalize_cr()`; `fallback_stats()` |
| `npc_hydrate_stats()` | `dnd_engine.py` | Single write path for stat hydration; source-based fill (idempotent for hooks, always-overwrite for `/hydrate`); calls `npc_hydrator` |
| `stat_incomplete()` | `dnd_engine.py` | Predicate: True if any of `{hp_max, ac, attack_bonus}` is NULL |
| Nullable stat columns | `dnd_npcs` | `hp_max`, `ac`, `attack_bonus`, `damage_dice`, `save_bonus`, `init_mod`, `cr_str` |
| `npc_register_avrae_madd()` | `dnd_engine.py` | Creates/confirms `dnd_npcs` row for `!init madd` creatures; sets `avrae_source='avrae_madd'`; leaves stat columns NULL (§11.M) |
| `/hydrate` slash command | `discord_dnd_bot.py` | DM-facing; `npc: str`, `cr: str`; always-overwrite path (§11.H lock); triggers `npc_hydrate_stats(source='explicit_hydrate')` |

### What doesn't change

- `dnd_combatant_state` — no new columns. The HP display in the persistence directive reads from Avrae's tracker; hydration doesn't touch Avrae's table.
- `npc_upsert()` — no changes. Hydration goes through its own `npc_hydrate_stats()` helper; the two write paths are independent.
- `compute_persistence_directive()` — no changes. It already reads the combatants snapshot (HP/AC from Avrae); the hydrated stat columns in `dnd_npcs` are supplemental context for v2 AI attacks, not a replacement for Avrae's ground truth.
- Bot→Avrae write boundary — unchanged. The bot does not autonomously emit `!` commands. No sync hint is surfaced (§11.D: sync-hint feature dropped).
- `compute_init_directive()` — no changes. The init directive (S20) shapes LLM output toward correct `!init begin` / `!init add` syntax; hydration ensures the added combatant has stat backing. They are siblings, not a dependency chain.

---

## 4. Schema changes

### New nullable columns on `dnd_npcs`

```sql
-- hp_max: maximum hit points (midpoint from CR band, or DM-authored)
ALTER TABLE dnd_npcs ADD COLUMN hp_max       INTEGER;
-- ac: armor class
ALTER TABLE dnd_npcs ADD COLUMN ac           INTEGER;
-- attack_bonus: to-hit modifier (e.g. +4 → stored as 4)
ALTER TABLE dnd_npcs ADD COLUMN attack_bonus INTEGER;
-- damage_dice: dice notation string (e.g. "1d8+2")
ALTER TABLE dnd_npcs ADD COLUMN damage_dice  TEXT;
-- save_bonus: flat save modifier (average across saves — single column in v1)
ALTER TABLE dnd_npcs ADD COLUMN save_bonus   INTEGER;
-- init_mod: initiative modifier (Dex-derived approximation from CR band)
ALTER TABLE dnd_npcs ADD COLUMN init_mod     INTEGER;
-- cr_str: CR as string key: "0","1/8","1/4","1/2","1","2",...
--         NULL until DM provides CR or skeleton hint sets it
ALTER TABLE dnd_npcs ADD COLUMN cr_str       TEXT;
-- avrae_source: set to 'avrae_madd' when NPC was added via !init madd
--               NULL for all other NPCs. Prevents hydration from firing on
--               Avrae-managed creatures with canonical monster-manual stats.
ALTER TABLE dnd_npcs ADD COLUMN avrae_source TEXT;
```

### Migration block in `ensure_tables()`

Follows the existing `PRAGMA table_info` + conditional `ALTER TABLE` pattern established for `dnd_campaigns`, `dnd_characters`, and `dnd_scene_state`:

```python
npc_cols = {row[1] for row in conn.execute("PRAGMA table_info(dnd_npcs)").fetchall()}
for col, ctype in [
    ('hp_max',       'INTEGER'),
    ('ac',           'INTEGER'),
    ('attack_bonus', 'INTEGER'),
    ('damage_dice',  'TEXT'),
    ('save_bonus',   'INTEGER'),
    ('init_mod',     'INTEGER'),
    ('cr_str',       'TEXT'),
    ('avrae_source', 'TEXT'),
]:
    if col not in npc_cols:
        conn.execute(f"ALTER TABLE dnd_npcs ADD COLUMN {col} {ctype}")
```

### `_NPC_COLS` update

Current:
```python
_NPC_COLS = ("id, campaign_id, canonical_name, aliases, role, location_id, "
             "description, skeleton_origin, mention_count, origin_excerpt, "
             "first_mentioned, last_mentioned")
```

After Track 6 #4:
```python
_NPC_COLS = ("id, campaign_id, canonical_name, aliases, role, location_id, "
             "description, skeleton_origin, mention_count, origin_excerpt, "
             "first_mentioned, last_mentioned, "
             "hp_max, ac, attack_bonus, damage_dice, save_bonus, init_mod, cr_str, avrae_source")
```

Callers that unpack `_NPC_COLS` into positional tuples (row indices) will need to be audited and updated — this is an implementation-phase task, not a spec decision. All callers should migrate to dict-based access (`row['hp_max']`) once the new columns land.

### `stat_incomplete()` predicate

```python
def stat_incomplete(npc: dict) -> bool:
    """True if the NPC is missing the minimum viable combat stat trio.

    The gate is hp_max + ac + attack_bonus. damage_dice / save_bonus /
    init_mod are filled from the same CR-band call; they don't need
    independent gatekeeping.
    """
    return any(npc.get(k) is None for k in ('hp_max', 'ac', 'attack_bonus'))
```

This is the hook-path hydration trigger: if any of the three core combat stats is NULL, the hook fires hydration. The `explicit_hydrate` path (from `/hydrate` slash command) bypasses this check and writes unconditionally — see §11.H. The invariant is that if `hp_max` is NULL, all six stat columns should also be NULL (the hook-path idempotent fill rule maintains this — hooks either fill all six or fill none, modulo the `generic_fallback` hp_max exclusion). The `stat_incomplete` check is therefore equivalent to `npc.get('hp_max') is None`, but checking all three is safer against partial-write failures.

---

## 5. Stat-source hierarchy

When hydration fires for an NPC, the source for each stat field is chosen in this order (first non-NULL source wins per field):

1. **DM-authored value already in `dnd_npcs`** — any column already populated is left unchanged **by the hook paths** (idempotent NULL-fill). This covers: DM-edited rows, skeleton stat hints (v1.x), and prior hook-sourced hydration runs. The hook fill rule: `UPDATE dnd_npcs SET col=? WHERE id=? AND col IS NULL`. Exception: the `/hydrate` slash command (`source='explicit_hydrate'`) is an authoritative replace — it overwrites all six stat fields unconditionally, including any previously written by `generic_fallback`. See §11.H lock.

2. **Skeleton `cr_str` hint (v1.x, see §12)** — when `dnd_npcs.cr_str` is already populated (from a prior skeleton load that parsed a `CR:` line), `npc_hydrate_stats()` uses it to produce the band defaults. No DM prompt needed. This is the pre-emptive path.

3. **DM-provided CR at `/hydrate` time** — the DM issues `/hydrate npc:Garrik cr:1/2`. The slash command calls `npc_hydrate_stats(campaign_id, canonical_name, cr_str='1/2', source='adhoc')`. The `cr_str` is written to `dnd_npcs.cr_str` as part of the hydration write, so future re-hydration runs have a source.

4. **CR-1/4 generic fallback** — fires when CR is None after the DM prompt (or when no `/hydrate` reply arrives). Writes all stat columns EXCEPT `hp_max` (see §1 decision 7 and §11.H for the rationale). Logged as `source=generic_fallback`.

This hierarchy is enforced inside `npc_hydrate_stats()` — the caller passes `cr_str_hint` (may be None) and the helper resolves the source. Callers do not implement the hierarchy themselves.

---

## 6. Hydration function

### `npc_hydrator.py` (new module — pure function core)

```python
"""NPC stat hydration — Track 6 #4.

Pure-function core. No DB access, no Discord, no dnd_engine imports.
Single consumer: npc_hydrate_stats() in dnd_engine.py.

Doctrine §1 anchor: LLM is not in the CR estimation path. All stat
derivation is deterministic lookup against the embedded CR-band table.
"""

# 5e SRD CR-band defaults (DMG Table 5 — Monster Statistics by Challenge
# Rating). Values: (hp_max, ac, attack_bonus, damage_dice, save_bonus, init_mod).
# Damage dice are representative midpoint expressions per CR band.
_CR_BANDS: dict[str, tuple] = {
    '0':   (3,   10, 2, '1d4',    0, 0),
    '1/8': (9,   12, 3, '1d6',    2, 1),
    '1/4': (13,  13, 3, '1d8',    2, 1),
    '1/2': (22,  13, 4, '1d8+2',  2, 1),
    '1':   (35,  13, 5, '2d6+3',  2, 2),
    '2':   (52,  13, 5, '2d8+3',  2, 2),
    '3':   (70,  13, 5, '2d8+4',  3, 2),
    '4':   (85,  14, 6, '2d10+4', 3, 2),
    '5':   (115, 15, 7, '3d8+5',  3, 3),
    '6':   (140, 15, 7, '3d10+5', 3, 3),
    '7':   (155, 15, 7, '4d8+5',  3, 3),
    '8':   (180, 16, 7, '4d10+5', 3, 3),
    '9':   (195, 16, 8, '4d10+6', 4, 3),
    '10':  (200, 17, 8, '4d12+6', 4, 4),
    '11':  (225, 17, 8, '4d12+7', 4, 4),
    '12':  (240, 17, 8, '5d10+7', 4, 4),
}

_CR_KEYS = ('hp_max', 'ac', 'attack_bonus', 'damage_dice', 'save_bonus', 'init_mod')
_FALLBACK_CR = '1/4'


def hydrate_npc_stats(cr_str: str) -> dict:
    """Return a stat dict for the given CR band.

    Raises ValueError for unrecognized CR strings. Callers validate
    before calling (via normalize_cr). Pure: no side effects.
    """
    row = _CR_BANDS.get(cr_str)
    if row is None:
        raise ValueError(f"unrecognized CR band: {cr_str!r}")
    return dict(zip(_CR_KEYS, row))


def fallback_stats() -> dict:
    """Return CR-1/4 defaults for use when CR is unknown.

    Note: the fallback path deliberately omits hp_max from the write
    (see npc_hydrate_stats source='generic_fallback' branch). This
    function returns the full dict; the write-path caller selects which
    fields to apply.
    """
    return hydrate_npc_stats(_FALLBACK_CR)


def normalize_cr(raw: str) -> str | None:
    """Normalize a user-supplied CR string to a _CR_BANDS key.

    Returns None if the input is unrecognized. Handles common
    alternate forms (decimals, spelled-out fractions).
    """
    s = raw.strip().lower()
    _aliases = {
        '0.125': '1/8', '.125': '1/8', 'eighth': '1/8', '⅛': '1/8',
        '0.25':  '1/4', '.25':  '1/4', 'quarter': '1/4', '¼': '1/4',
        '0.5':   '1/2', '.5':   '1/2', 'half': '1/2', '½': '1/2',
    }
    s = _aliases.get(s, s)
    return s if s in _CR_BANDS else None
```

### `npc_hydrate_stats()` in `dnd_engine.py` (new engine helper — single write path)

```python
def npc_hydrate_stats(campaign_id: int,
                      name: str,
                      cr_str: str | None,
                      source: str) -> tuple[bool, dict]:
    """Hydrate stat fields on a dnd_npcs row.

    source: 'skeleton' | 'hook' | 'adhoc' | 'generic_fallback'
            | 'explicit_hydrate'

    Returns (wrote_anything: bool, signals: dict).

    Fill rule depends on source (§11.H lock):
    - Hook sources ('skeleton', 'hook', 'adhoc', 'generic_fallback'):
        idempotent NULL-fill. UPDATE ... SET col=? WHERE col IS NULL.
        DM-authored values and prior hydration values are preserved.
    - Explicit source ('explicit_hydrate' — from /hydrate slash cmd):
        always-overwrite. UPDATE ... SET col=? WHERE id=?. No NULL guard.
        Treats the DM's explicit CR as authoritative correction.
        Re-running /hydrate on any NPC writes all six stat columns.

    For source='generic_fallback': hook-path rules apply (NULL-fill),
    but hp_max is excluded from the write — left NULL so a subsequent
    /hydrate can fill it with the correct CR.

    For source='adhoc': creates a minimal dnd_npcs row first if none
    exists (via npc_upsert with skeleton_origin=False), then hydrates.
    """
    ...
    # Implementation outline (not locked — Session 3):
    # 1. If source == 'adhoc': npc_upsert(campaign_id, name, skeleton_origin=False)
    #    to ensure a row exists. npc_upsert is idempotent on canonical_name.
    # 2. npc = npc_get_by_name(campaign_id, name)
    #    if npc is None: return (False, signals | {'error': 'row_not_found'})
    # 3. source == 'explicit_hydrate'?
    #    YES → skip stat_incomplete check; always write all six columns
    #    NO  → if stat_incomplete(npc) is False: return (False, signals | source='miss')
    # 4. Resolve cr_str:
    #    - use cr_str as provided. Callers are responsible for resolving
    #      cr_str=None to generic_fallback BEFORE calling this helper (§11.L lock:
    #      caller-side decision). The engine helper never internally promotes
    #      None → _FALLBACK_CR for any source.
    #    - For source='generic_fallback': cr_str is None; use fallback_stats()
    #      directly (bypasses the None→key lookup).
    # 5. stats = npc_hydrator.hydrate_npc_stats(cr_str)  [or fallback_stats() for generic_fallback]
    # 6. Build SET clause:
    #    - explicit_hydrate: all six stat cols unconditionally
    #    - generic_fallback: all six EXCEPT hp_max, WHERE col IS NULL
    #    - all other hook sources: all six WHERE col IS NULL
    # 7. Execute UPDATE. Record which columns were written in signals['stats_filled'].
    # 8. Write cr_str to dnd_npcs.cr_str:
    #    - explicit_hydrate: unconditionally
    #    - hooks: WHERE cr_str IS NULL
    # 9. log(f"hydration: campaign={campaign_id} npc='{name}' source={source} ...")
    # 10. Return (True, signals).
```

The engine helper is the **only** write path for stat hydration. The `/hydrate` slash command calls it. The init-list hook calls it. `skeleton_loader.py` (v1.x) will call it. No direct DB writes from callers.

### `npc_register_avrae_madd()` in `dnd_engine.py` (new engine helper — §11.M)

```python
def npc_register_avrae_madd(campaign_id: int, name: str) -> bool:
    """Register an !init madd creature in dnd_npcs without hydrating it.

    Creates a minimal dnd_npcs row (if none exists) with avrae_source='avrae_madd'.
    Leaves all stat columns NULL — Avrae owns the mechanics for these creatures.
    Returns True if a row was created or updated, False if already registered.
    Idempotent: safe to call multiple times for the same NPC.
    """
    ...
    # Implementation outline (Session 3):
    # 1. npc_upsert(campaign_id, name, skeleton_origin=False) — idempotent row create
    # 2. UPDATE dnd_npcs SET avrae_source='avrae_madd'
    #    WHERE campaign_id=? AND canonical_name=? AND avrae_source IS NULL
    # 3. log: hydration: campaign={N} npc='{name}' source=avrae_madd
    #         stats_filled=none cr=none
    # 4. Return True if UPDATE changed a row, False otherwise.
```

---

## 7. Hook integration

### Path 1 — Init-list trigger (single hook — §11.J revised)

`_handle_init_list_event()` in `discord_dnd_bot.py` currently:
1. Calls `parse_init_list_embed()` → structured combatant list
2. Calls `update_combatants_from_init_list()` → writes to `dnd_combatant_state`
3. Logs `init_list_parsed: ...`

Track 6 #4 adds step 2.5 between steps 2 and 3:

```python
# After update_combatants_from_init_list(), before the init_list_parsed log:
# §11.M lock: HP-status token classifies !init add vs !init madd routing.
# §11.L lock: caller checks cr_hint FIRST; if None, posts prompt FIRST,
# then calls engine with source='generic_fallback'. Engine never resolves
# None → CR-1/4 internally.
#
# NOTE: parse_init_list_embed() must extract status_token per combatant row.
# Verify at Session 3 start that the field is populated (§11.M gate).
bound_names = {n.lower() for n in get_bound_character_names(campaign_id)}
for row in parsed_combatants:
    name = row['name']
    status_token = row.get('status_token', '<None>')  # e.g. '<None>', '<Healthy>', '<Bloodied>'
    if name.lower() in bound_names:
        log(f"hydration: campaign={campaign_id} npc='{name}' source=bound_pc_skip "
            f"stats_filled=none cr=none status_token={status_token}")
        continue
    if status_token != '<None>':
        # §11.M: Avrae-backed combatant (!init madd) — register, skip hydration
        npc_register_avrae_madd(campaign_id, name)
        # npc_register_avrae_madd emits source=avrae_madd log line
        continue
    # status_token == '<None>': DM-added NPC (!init add) — hydration path
    npc = npc_get_by_name(campaign_id, name)
    if npc is not None and not stat_incomplete(npc):
        # Already fully hydrated (e.g. from a prior /hydrate)
        log(f"hydration: ... source=miss status_token={status_token}")
        continue
    cr_hint = npc.get('cr_str') if npc else None
    if cr_hint is None:
        # §11.L / §3: caller-side decision — post prompt BEFORE engine call
        await _post_hydration_prompt(channel, campaign_id, name)
        src = 'generic_fallback'
    else:
        src = 'skeleton' if (npc and npc.get('skeleton_origin') and cr_hint) else 'hook'
    npc_hydrate_stats(campaign_id, name, cr_str=cr_hint, source=src,
                      status_token=status_token)
```

`_post_hydration_prompt()` in `discord_dnd_bot.py` (new async helper):
- Looks up `#dm-aside` channel in the guild
- Posts: `"Hydration needed: \`{name}\` just entered initiative with no stats. What CR? \`/hydrate npc:{name} cr:N\`"`
- Registers `(campaign_id, canonical_name)` in `_pending_hydration: dict` (module-level, for `/hydrate` to clear)
- Soft-fails silently if `#dm-aside` is not found (stat remains NULL; `source=generic_fallback` will fire on the next init-list parse)

### Path 2 — `/hydrate` slash command (DM-facing, also the `/hydrate` response handler)

```
/hydrate npc:<name> cr:<band>
```

Implementation steps:
1. `normalize_cr(cr)` → validated CR string, or ephemeral error "Invalid CR. Valid bands: 0, 1/8, 1/4, 1/2, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12"
2. `npc_get_by_name(campaign_id, name)` — case-insensitive, alias lookup. If None: ephemeral error "NPC `{name}` not found in this campaign. Add them first via `!init add` or ask Virgil."
3. `npc_hydrate_stats(campaign_id, canonical_name, cr_str=validated_cr, source='explicit_hydrate')` — **always-overwrite** all stat fields regardless of NULL status (§11.H lock: explicit DM action is authoritative replace)
4. Clear `_pending_hydration` entry for this name if present
5. Post ephemeral: "Hydrated `{canonical_name}` at CR {cr}: HP {hp_max}, AC {ac}, Atk +{attack_bonus}, Dmg {damage_dice}."

The `/hydrate` command is the DM's authoritative stat-correction path AND the response to the `#dm-aside` CR prompt. It can also be used proactively before combat starts. Unlike the hook path, `/hydrate` fully replaces all stat fields — including any previously written by `generic_fallback` — because explicit DM action is authoritative (§11.H). No sync hint is emitted — Avrae's tracker remains Avrae's responsibility (§11.D).

### Sequencing relative to COMBAT_ACTION gate

Timeline in a typical combat initiation:

```
1. DM: !init begin → Avrae posts tracker → _handle_init_event → mode flip to 'combat'
2. DM: !init add Garrik (or !init madd Goblin -name "Garrik")
   → Avrae updates tracker (no bot action at add-time in v1)
3. DM: !init list (or Avrae auto-posts) → _handle_init_list_event
   → HYDRATION + CLASSIFICATION SCAN (single hook, all combatants)   ← NEW
     Garrik status_token='<None>' → hydration fires → source=hook or generic_fallback
     [any !init madd creature] status_token='<Healthy>' → npc_register_avrae_madd
4. DM: !init next → first combatant activates
5. Player narrates action → adjudicator.adjudicate() → _gate_combat checks
   (mode='combat' ✓, combatants non-empty ✓, active_turn ✓) → PASSES
   persistence directive → reads dnd_combatant_state.hp (from Avrae)
   advisory context → reads dnd_npcs.ac, attack_bonus, damage_dice (hydration-sourced)
```

A small race window remains: if a player narrates after step 2 (`!init add`) but before step 3 (`!init list`), stats are still NULL. Accepted as v1 risk per §11.J revised — `!init list` typically follows within seconds and DMs run it explicitly. If session logs show real friction, Hook 1 re-introduction is v1.x (§12).

---

## 8. Telemetry

### Primary log line (always-fire, per combatant per init-list parse)

```
hydration: campaign={N} npc='{name}'
           source={skeleton|hook|adhoc|miss|generic_fallback|bound_pc_skip|explicit_hydrate|avrae_madd}
           stats_filled={hp,ac,atk,dmg,save,init|none} cr={...|none}
           status_token={<None>|<Healthy>|<Bloodied>|<Critical>|<Dead>|n/a}
```

**Source semantics:**

| Source | Meaning |
|--------|---------|
| `skeleton` | CR came from `dnd_npcs.cr_str` set by skeleton loader (v1.x). NPC row had `skeleton_origin=1` and `cr_str` populated. |
| `hook` | NPC row existed with `cr_str` populated (from prior `/hydrate` or generic_fallback partial write). Stats filled from the known CR. |
| `adhoc` | No prior row. Row created by `npc_upsert`, then hydrated. CR came from `/hydrate` reply or was NULL (→ generic_fallback branch). |
| `miss` | NPC was already fully hydrated. No write. |
| `generic_fallback` | CR was NULL, DM prompt sent to `#dm-aside`, CR-1/4 used for partial fill (no `hp_max` written). |
| `bound_pc_skip` | Combatant name matched a bound PC. Hydration skipped entirely. `stats_filled=none cr=none`. Fires per bound PC per parse (always-fire per Doctrine §59 — see §11.I lock). |
| `explicit_hydrate` | `/hydrate` slash command fired. Always-overwrite path (§11.H lock). All six stat fields written unconditionally. |
| `avrae_madd` | Combatant's HP-status token was non-`<None>` (§11.M classification rule). `npc_register_avrae_madd()` called — `dnd_npcs` row created/confirmed, all stat columns left NULL, `avrae_source='avrae_madd'` written. No hydration write. `status_token` field shows the observed token. |

**Session-log interpretation note (§11.G surfaced addition):** In v1, `source='skeleton'` only fires when `cr_str` was set by the skeleton loader (v1.x, not yet shipped). A skeleton-origin NPC with `cr_str` populated by a prior `/hydrate` call logs `source='hook'` — technically correct (CR source was the DM's slash command), but may be surprising when reading session logs. Once v1.x skeleton loader ships, pre-hydrated skeleton NPCs will shift from `hook` to `skeleton` when their `cr_str` originates from `apply_skeleton()`.

**`stats_filled` semantics:** comma-separated list of column shortnames written in this call (`hp`, `ac`, `atk`, `dmg`, `save`, `init`), or `none` if source=`miss`. For `generic_fallback`, omits `hp` from the list.

### Secondary log line for `/hydrate` slash command

```
hydration_manual: campaign={N} npc='{name}' cr={...} stats_written={0|1}
                  fields_updated={hp,ac,atk,dmg,save,init|none}
```

### `directive_emit:` extension

The existing `directive_emit:` log line (which tracks which directives fired per turn) gains a new `hydration_write_fired={0|1}` field representing whether ANY NPC in the current init-list parse had stats newly written this turn. This is a session-turn-level binary — `1` if any hydration WRITE occurred, `0` even when all NPCs are already hydrated (all `source=miss`). It does NOT mean "no NPCs needed hydration"; it means "no new writes this turn." See §11.F surfaced addition for naming rationale.

---

## 9. Test surface

### `test_npc_hydrator.py` (pure function tests — no DB)

1. `hydrate_npc_stats('1/4')` returns correct band values (hp=13, ac=13, attack_bonus=3, damage_dice='1d8', save_bonus=2, init_mod=1)
2. All 16 CR bands return non-None dicts with the correct six keys
3. `hydrate_npc_stats('99')` raises `ValueError`
4. `hydrate_npc_stats` for unknown string `'cr5'` raises `ValueError`
5. `fallback_stats()` returns CR-1/4 values
6. `normalize_cr('0.25')` → `'1/4'`
7. `normalize_cr('half')` → `'1/2'`
8. `normalize_cr('1/8')` → `'1/8'`
9. `normalize_cr('12')` → `'12'`
10. `normalize_cr('99')` → `None`
11. `normalize_cr('quarter')` → `'1/4'`
12. `hydrate_npc_stats` is deterministic: two calls with same CR return equal dicts
13. `hydrate_npc_stats` does not mutate any module-level state (pure function)

### `test_npc_hydrate_stats.py` (engine helper tests — in-memory DB)

14. NPC with all-NULL stat columns: `npc_hydrate_stats` writes all seven columns
15. NPC with `hp_max` already populated: hydration does NOT overwrite `hp_max`
16. NPC with `hp_max` + `ac` populated, `attack_bonus` NULL: hydration writes only `attack_bonus`, `damage_dice`, `save_bonus`, `init_mod`
17. Fully hydrated NPC: `npc_hydrate_stats` returns `(False, signals)` with `stats_filled='none'`
18. `source='skeleton'` signals logged correctly
19. `source='adhoc'` creates a new `dnd_npcs` row when NPC doesn't exist, then hydrates
20. `source='generic_fallback'` writes `ac`, `attack_bonus`, `damage_dice`, `save_bonus`, `init_mod` using CR-1/4 but leaves `hp_max` NULL
21. Two consecutive calls with same inputs on the same NPC: second call returns `(False, signals)` — idempotent
22. `cr_str='1/2'` → correct values: hp_max=22, ac=13, attack_bonus=4, damage_dice='1d8+2'
23. `npc_hydrate_stats` called with `cr_str=None, source='generic_fallback'`: calls `fallback_stats()` and writes CR-1/4 band minus `hp_max` (§11.L: caller is responsible for resolving None — engine does not internally promote None to _FALLBACK_CR for other sources)
24. After hydration, `dnd_npcs.cr_str` is populated (for non-generic_fallback sources)

### `test_npc_hydrate_stats.py` additions (§11.H always-overwrite, in-memory DB)

20b. `source='explicit_hydrate'` on NPC with all stats populated: all six fields overwritten with new CR-band values (no NULL guard)
20c. `source='explicit_hydrate'` on NPC after `generic_fallback`: all six fields replaced with correct CR-band values — no mixed stat block

### `test_hydration_hook.py` (init-list hook + classification)

25. Combatant with `status_token='<None>'` and no `dnd_npcs` row → hydration fires with `source='adhoc'`
26. Combatant with `status_token='<None>'` and row + NULL `hp_max` → hydration fires with `source='hook'`
27. Combatant with `status_token='<None>'` and fully hydrated row → `source='miss'`, no DB write
28. Combatant name matches a bound character name (case-insensitive) → `source='bound_pc_skip'` log line, no write (status_token irrelevant — bound-PC check runs first)
29. Multiple combatants in one init-list with mixed paths: each routes independently
30. CR-None ad-hoc NPC (`status_token='<None>'`, no cr_str): `_post_hydration_prompt` called before engine invocation; generic_fallback stats written (no hp_max)
31. `_pending_hydration` dict cleared correctly when `/hydrate` fires
32. Combatant with `status_token='<Healthy>'` → `npc_register_avrae_madd()` called, no hydration write, `source=avrae_madd` log line
33. Combatant with `status_token='<Bloodied>'` → `npc_register_avrae_madd()` called (non-`<None>` → avrae_madd path)
34. Combatant with `status_token='<Critical>'` → avrae_madd path
35. Combatant with `status_token='<Dead>'` → avrae_madd path
36. `npc_register_avrae_madd(campaign_id, 'Goblin')` creates a `dnd_npcs` row with `avrae_source='avrae_madd'` and all stat columns NULL; calling again on same NPC is a no-op
37. Mixed init-list: one `<None>` combatant (hydrated) + one `<Healthy>` combatant (avrae_madd) → both log lines emitted correctly, no cross-contamination
38. `parse_init_list_embed()` correctly extracts `status_token` field for each combatant row (parser smoke test — verify at Session 3 start)

### `test_slash_hydrate.py` (slash command)

39. `/hydrate npc:Garrik cr:1/2` → hydration writes correct stats, returns ephemeral confirmation with hydrated stat block (no sync hint — §11.D)
40. `/hydrate` with unknown npc name → ephemeral error "NPC not found"
41. `/hydrate` with invalid CR (e.g., `cr:99`) → ephemeral error with valid band list
42. `/hydrate` on fully hydrated NPC → ephemeral "already complete — no fields updated"
43. `/hydrate` when `_pending_hydration` has an entry for the npc → entry cleared after call

### Adjacent test files (no assertion-count changes expected, green required)

- `test_combatant_state.py` — `dnd_npcs` migration adds columns; existing `npc_upsert` / `npc_get_by_name` tests must still pass
- `test_init_list_parser.py` — parser unchanged; assertions unchanged
- `test_persistence_directive.py` — directive unchanged; assertions unchanged
- `test_campaign_delete_cascade.py` — `dnd_npcs` rows (including new stat columns) must be cascade-deleted with campaign; fixture needs `dnd_npcs` rows with stat columns in at least one test case

---

## 10. Edge cases and integration

### PC exclusion

Bound characters appear in the `!init list` snapshot alongside NPCs. Hydration must skip them. Gate: `get_bound_character_names(campaign_id)` → case-insensitive set membership check per combatant. If a combatant name matches any bound PC name, hydration is skipped for that row and emits `hydration: ... source=bound_pc_skip stats_filled=none cr=none` per §11.I lock.

Summoned creatures (e.g., "Giant Rat", "Spirit Wolf") are treated as ad-hoc NPCs and hydrated normally. They are not in `get_bound_character_names`, so the exclusion gate does not fire.

### Avrae-managed creatures (!init madd — §11.M)

When a combatant's HP-status token is non-`<None>`, the init-list hook routes to `npc_register_avrae_madd()` instead of the hydration path. All stat columns are left NULL by design — Avrae's monster manual is the canonical stat source. The advisory context build path must not pass NULL stat columns to the LLM as if the NPC is stat-incomplete; instead, it renders `"(mechanics: Avrae monster entry)"` as a marker in place of the stat block. HP reads from `dnd_combatant_state` as always (Avrae-sourced via the persistence directive's existing path). This is a small branch in the advisory context builder: if `npc.get('avrae_source') == 'avrae_madd'`, emit the marker rather than the NULL-column placeholder.

**GO1 identity-drift (known DM-education point):** When the DM uses `!init madd Goblin` without the `-name` flag, Avrae assigns a generated name (`GO1`, `GO2`, etc.) to the combatant. Virgil records what Avrae provides — the `dnd_npcs` row will use "GO1" as `canonical_name`. If the DM later refers to this creature by a narrative name ("the Goblin Skirmisher"), the alias lookup will not resolve because the row has no such alias. The correct DM workflow is `!init madd Goblin -name "Goblin Skirmisher"` — confirmed working in live verification. This is a DM-education point, not a Virgil bug. File as a v1.x candidate (§12) if session logs show DMs routinely forget the `-name` flag.

### Name matching between init list and dnd_npcs

`npc_get_by_name()` uses canonical-name lookup with alias fallback. If the DM typed `!init add "Garrik"` but the canonical row in `dnd_npcs` is `"Garrik the Smith"` (with alias `"Garrik"`), the alias lookup resolves correctly and hydration fires on the canonical row. If no alias match, the combatant name is used as-is for the new row (ad-hoc path, `npc_upsert` with the raw init-list name as `canonical_name`).

### Multiple `!init list` parses within one combat

`!init list` re-fires after each `!init add` and after each `!init next`. The idempotent fill rule makes repeated hydration checks on the same NPC cheap (`stat_incomplete()` returns False → `source=miss` log → no DB write). Performance impact: N DB reads per parse, where N is combatant count (typically 2–8 per encounter). Acceptable at session-scale turn rate.

### DM runs `/hydrate` after `generic_fallback` partial fill

If `generic_fallback` fired (ac/attack_bonus/etc. written at CR-1/4, hp_max left NULL), a subsequent `/hydrate npc:Garrik cr:2` fully replaces all stat fields — including `ac` and `attack_bonus` already written by generic_fallback — with CR-2 band values. Per §11.H (LOCKED): the `/hydrate` slash command uses `source='explicit_hydrate'` which bypasses the `WHERE col IS NULL` guard and writes all six stat columns unconditionally. The DM's explicit CR correction is treated as authoritative; generic_fallback stats are placeholders, not authority. Result: full CR-2 stat block (`hp_max=52, ac=13, attack_bonus=5, ...`). No mixed block. `cr_str` updated to `'2'`.

### Backwards compatibility with existing canonical NPCs

Existing `dnd_npcs` rows with `skeleton_origin=1` and DM-authored descriptions have no stat columns (all NULL after migration). Hydration will fire on any such NPC that appears in `!init list` — which is correct behavior. The DM-authored description, role, location, and `skeleton_origin` flag are untouched (only the new stat columns are affected by hydration writes). The `WHERE col IS NULL` guard in the UPDATE statement enforces this structurally.

### Integration with init_directive (S20)

The init_directive fires when `intent=COMBAT` AND `mode != 'combat'` AND no active turn. It directs the LLM to emit `!init begin` + `!init add <target>`. After the DM follows the directive:
1. `!init begin` → mode flip → `_handle_init_event`
2. `!init add <target>` → Avrae adds combatant
3. `!init list` → `_handle_init_list_event` → hydration fires

The init_directive and hydration are independent siblings. The directive shapes LLM output toward the correct command syntax; hydration ensures the resulting combatant has stat backing. Neither depends on the other.

### Integration with persistence directive (Track 3, Session 21)

The persistence directive displays combatant HP from `dnd_combatant_state.hp_current / hp_max` (Avrae's tracker values, parsed from `!init list` embeds). It does NOT currently read from `dnd_npcs` stat columns.

**Important distinction:**
- `dnd_combatant_state.hp_current / hp_max` — HP in Avrae's tracker. Populated when the DM uses `!init add <name> -hp N`. Shows actual in-combat HP. This is what the persistence directive uses for "HP 22/22" vs "HP unknown."
- `dnd_npcs.hp_max` — HP from the hydration stat block. Available for the AI attack path (v2) and for advisory context. NOT the same source.

**Avrae-gap:** After hydration, the persistence directive still shows "HP unknown" because Avrae's tracker still has the default HP. No sync hint is emitted (§11.D: sync-hint dropped — `!init modify` does not exist as an Avrae subcommand). The hydrated `hp_max` in `dnd_npcs` is available to the advisory context and v2 AI attack path. This is the accepted limitation of the single-boundary architecture: Avrae's tracker is Avrae's responsibility.

### Integration with narration_verifier (Track 7 #2)

`narration_verifier.verify_narration()` checks NPC names against `npcs_canonical` (the current canonical NPC list). After Track 6 #4 ships, any ad-hoc NPC hydrated via the init-list trigger will have a `dnd_npcs` row (created by `npc_upsert` in the `source='adhoc'` path). This means the NPC name is in `npcs_canonical` and will NOT trigger `FABRICATED_COMBATANT` violations — the two tracks are correctly complementary. Verified via the disposition line in F-49: "verification refuses fabrication; hydration enables legitimate addition." An ad-hoc NPC that legitimately enters init via `!init add` gets a dnd_npcs row from hydration; verification then treats that name as canonical. The fabrication gate closes the channel where the LLM invents the name; the hydration path creates the row that prevents false positives on legitimate init-adds.

---

## 11. Decision points needing Jordan's call

### §11.A — Which shapes ship in v1? (LOCKED)

**LOCKED: Option 1.** v1 ships shapes (b)+(c) via the two hook points; skeleton stat hints (shape a) defer to v1.x, with `source=generic_fallback` frequency as the pull-forward signal.

**Options:**
- **Option 1 (recommended):** (b)+(c) via init-list trigger. Skeleton stat hints (a) file as v1.x.
- **Option 2:** (a)+(b)+(c) — skeleton stat hints AND init-list trigger all in v1.
- **Option 3:** (c) ad-hoc only — (b) is implicit in (c)'s "look up row first" path, so this is actually the same as Option 1 at the code level.

**Recommended:** Option 1. The primary friction at init-add time is the missing stats for ANY NPC, whether skeletonized or ad-hoc. The v1 init-list trigger addresses this without requiring DM changes to `skeleton.md`. Skeleton stat hints (a) are an optimization — they reduce the CR-prompt frequency for pre-planned encounters — but the prompt path is low-friction enough to ship first. Build the init-list trigger, validate it under play pressure, then add skeleton hints in v1.x after the fill-path vs. miss-path telemetry reveals how often the DM is prompted.

**Trade-off:** Deferring (a) means the DM will be prompted for CR on every non-skeletonized NPC's first init-add (per session — the CR is stored in `cr_str` after the first `/hydrate`, so repeat appearances don't re-prompt). If play patterns show the DM frequently running `!init add` for NPCs they've pre-planned, the prompt friction will surface in `source=generic_fallback` frequency and motivate (a) sooner.

**Confidence:** medium — depends on play patterns not yet observable at spec time.

---

### §11.B — CR estimation source: which path is primary in v1? (LOCKED)

**LOCKED: Option 1.** CR estimation source is DM-provided via `/hydrate npc:<name> cr:<band>`; LLM inference rejected per Doctrine §1; skeleton hints deferred to v1.x per §11.A.

**Options:**
- **Option 1 (recommended):** DM-provided at `/hydrate npc:<name> cr:<band>` time. Explicit, low-friction, keeps LLM out of the estimation path.
- **Option 2:** Skeleton-declared `CR:` hint (v1.x only — not in v1 scope per §11.A Option 1).
- **Option 3:** LLM-inferred from narrative context. **Rejected.** LLM in the mechanical stat-generation path violates Doctrine §1 ("LLM never decides stats").

**Recommended:** Option 1. The DM knows the intended CR for any NPC they're adding to combat — they're the encounter author. A one-shot `/hydrate npc:Garrik cr:1/2` takes 3 seconds. It also creates a traceable, auditable CR record in `dnd_npcs.cr_str` for future sessions.

**Confidence:** high.

---

### §11.C — Failure mode when CR is unknown at hydration time (LOCKED)

**LOCKED: Option 3.** CR-unknown failure mode is partial CR-1/4 fallback (no `hp_max` written) plus explicit DM prompt in `#dm-aside`; fallback tier is CR 1/4. `_pending_hydration` re-fires on bot restart (benign — `stat_incomplete()` returns True until real CR provided).

**Options:**
- **Option 1:** Refuse hydration. Leave stats NULL. Player must wait for `/hydrate` before any stat context is available.
- **Option 2:** Silent CR-1/4 fallback. Write all stats including `hp_max`. No DM notification.
- **Option 3 (recommended):** CR-1/4 partial fallback (no `hp_max`) + explicit DM prompt in `#dm-aside`.

**Recommended:** Option 3. Option 1 blocks combat context while the DM responds; the persistence directive sees "HP unknown" indefinitely. Option 2 is silent — the DM won't know the stats are wrong unless they check logs. Option 3 keeps combat moving (fallback stats provide ac/attack context) while surfacing the gap explicitly to the DM via `#dm-aside` (the channel designed for advisory exchange). Leaving `hp_max` NULL is honest: the LLM sees "HP unknown" for this NPC until the DM provides CR, which is accurate.

**On the fallback CR choice:** CR 1/4 is conservative (most encounter-worthy NPCs are CR 1/2–2). The DM can always `/hydrate` to correct. File CR 1/4 as the starting point and revisit if `source=generic_fallback` telemetry shows it's producing obviously undersized combatants.

**Confidence:** high on Option 3 as the strategy; medium on CR 1/4 as the fallback tier.

---

### §11.D — Where hydration writes: `dnd_npcs` only, or also Avrae-facing commands? (LOCKED)

**LOCKED: Sync-hint feature DROPPED. `dnd_npcs` only. No sync hint of any kind.**

**Verification result:** `!init modify` does not exist as an Avrae subcommand ("Command 'init' has no subcommand named modify"). The sync-hint string drafted in prior passes would have produced a live Discord error during combat. Gate RESOLVED by removal.

**Architectural rationale (permanent, not deferred):** The sync-hint implied Virgil is responsible for mechanical synchronization between `dnd_npcs` and Avrae's tracker. The three-layer doctrine explicitly forbids this — Avrae owns mechanics, Virgil's bridge layer reads Avrae state, never writes to it. The sync-hint was a UX convenience layered on top of a doctrinal boundary; the doctrinal boundary takes precedence.

**Consequence:** After hydration fires, the persistence directive still shows "HP unknown" for the hydrated NPC because Avrae's tracker has the default HP. This is the existing pre-Track-6-#4 behavior — no regression. The hydrated `hp_max` in `dnd_npcs` is available to the advisory context and v2 AI attack path. The DM manages Avrae's tracker however they normally do.

**Options (resolved — not live):**
- ~~Option 1: `dnd_npcs` only + informational sync hint.~~ Dropped — `!init modify` does not exist; sync-hint feature removed.
- **Option 2:** Autonomous `!init modify` emission. **Rejected** — bot→Avrae write boundary, higher failure-mode severity than the Avrae-gap.
- **Effective result:** `dnd_npcs` only. No hint. No emission.

---

### §11.E — Controller authority: unchanged or reassigned after hydration? (LOCKED)

**LOCKED: Option 1.** Controller authority unchanged; v1/v2 boundary; AI-driven NPC attacks are explicitly v2 and depend on infrastructure not yet built.

**Options:**
- **Option 1 (recommended):** Controller authority unchanged. Player who fired `!init add` retains Avrae controller. Hydration provides stat context only.
- **Option 2:** Bot claims controller authority post-hydration to enable AI-driven attacks.

**Recommended:** Option 1 unambiguously. Controller authority is an Avrae-level construct. Reassigning it requires a bot→Avrae interaction to change the controller field in Avrae's tracker — which is an even larger new write boundary than §11.D Option 2. AI-driven NPC attacks are the payload use case for hydration's stat block, but they are explicitly v2 and filed in §12.

**Confidence:** high. Not a trade-off — this is a v1/v2 boundary.

---

### §11.F — Telemetry shape: per-combatant per-parse, or per-parse summary? (LOCKED)

**LOCKED: Option 1.** Per-combatant per-parse. `directive_emit` session-turn field renamed `hydration_write_fired={0|1}` (was `hydrated={0|1}`) per review-doc surfaced addition — the new name makes clear it reflects writes, not hydration need.

**Options:**
- **Option 1 (recommended):** Per-combatant per-parse. One `hydration:` log line per combatant per `!init list` parse.
- **Option 2:** Per-parse summary. One line per parse with aggregate counts.

**Recommended:** Option 1. Per-combatant lines allow grep-based queries by NPC name — matching the existing `init_list_parsed:` empirical-baseline shape and Doctrine §59's "observable per-unit" posture. Summary lines aggregate away the per-NPC signal that tells you "which NPCs are prompting the DM for CR frequently." Log volume is bounded by session-scale combatant counts (2–8 per encounter).

**Confidence:** high.

---

### §11.G — Backwards compatibility: what happens when a partially-authored NPC (skeleton_origin=1, no stats) enters init? (LOCKED)

**LOCKED:** Hydrate skeleton-origin NPCs normally. `skeleton_origin=1` is a narrative-provenance flag, not a combat-stats authority signal. See §8 source semantics note for skeleton-vs-hook telemetry distinction.

**Context:** Some `dnd_npcs` rows are DM-authored via `skeleton.md` with rich description/role/voice data but no `CR:` line (since v1 skeleton.md has no stat-hint syntax). These rows have `skeleton_origin=1` and NULL stat columns. When they appear in `!init list`, hydration will fire (`stat_incomplete()` returns True).

**Decision point:** Should skeleton-origin NPCs with NULL stats be hydrated from the CR-band fallback, or should hydration refuse them and require an explicit `/hydrate`?

**Recommended:** Hydrate them like any other NPC. `skeleton_origin=1` means the DM authored the narrative shape (description, role, voice); it says nothing about combat stats. The stat columns are a separate concern. Hydration fires, DM prompt goes to `#dm-aside`, DM provides CR or accepts CR-1/4 fallback. The `skeleton_origin` flag is not a combat-stats authority signal.

**Confidence:** high.

---

### §11.H — Mid-combat hydration update: DM provides real CR after generic_fallback fired

**LOCKED: Option 2.**

**Context:** `generic_fallback` fired (ac/attack_bonus/etc. written at CR-1/4, `hp_max` left NULL). DM later runs `/hydrate npc:Garrik cr:2`. Under the idempotent fill rule (Option 1), `hp_max` would fill to 52 but `ac` and `attack_bonus` would stay at CR-1/4 values — the stat block ends up incoherent.

**Lock rationale:** Doctrine treats the DM as the authoritative encounter author. A late `/hydrate` with real CR is a correction, not an addition — the DM is saying "I now know what this NPC's CR is." Accepting half the correction (fill `hp_max` but preserve CR-1/4 `ac`/`attack_bonus`) is incoherent: it trusts the DM's CR judgment for HP and simultaneously overrides it for everything else. Trust the DM fully. Late CR fully replaces fallback stats.

The architectural distinction is between the **hook path** (passive, additive) and the **slash command path** (explicit DM action, authoritative):
- Init-list hook (`_handle_init_list_event`) — idempotent NULL-fill. Never overwrites populated fields. DM-authored values are always preserved.
- `/hydrate` slash command — always-overwrite for all stat fields with the CR-band values for the provided CR, regardless of NULL status. Explicit DM action is authoritative replace, not additive fill.

**Implementation note for Session 3:** `npc_hydrate_stats()` needs a source-based branch:
- Hook sources (`'skeleton'`, `'hook'`, `'adhoc'`, `'generic_fallback'`): apply `WHERE col IS NULL` guard. Idempotent fill.
- Explicit DM source (`'explicit_hydrate'`): apply full overwrite — `UPDATE dnd_npcs SET hp_max=?, ac=?, attack_bonus=?, damage_dice=?, save_bonus=?, init_mod=?, cr_str=? WHERE id=?` with no NULL condition. The `/hydrate` slash command passes `source='explicit_hydrate'`.

This cleanly encodes the invariant: passive hooks are additive; DM commands are authoritative.

---

### §11.I — PC exclusion: logged or silent skip?

**LOCKED: Option 2, permanently.**

Bound PCs in the init list emit:
```
hydration: campaign={N} npc='{name}' source=bound_pc_skip stats_filled=none cr=none
```
One line per PC per `!init list` parse. Confirms the filter fires; gives grep coverage for "Donovan Ruby was correctly skipped this session."

**Lock rationale:** The empirical-baseline always-fire posture (Doctrine §59) applies to filters as much as to fills. Silent skips are invisible — if the exclusion gate misfires (PC gets hydrated, or an NPC is silently dropped), there's no signal. The `bound_pc_skip` line costs nothing at session-scale combatant counts and is the only way to confirm the gate is correct without a live-test exercise. This is permanent, not a diagnostic aid to remove later.

---

### §11.J — Hydration hook point: init-list only, or also init-add? (REVISED)

**LOCKED: Single hook (Hook 2 / init-list only). Race window accepted as v1 risk.**

**Original lock (amendment pass #1):** Belt-and-suspenders — Hook 1 on `!init add` confirmation + Hook 2 on `!init list` parse.

**Revised lock rationale:** The §11.M classification rule requires the HP-status token from the init-list embed. Hook 1 fires on the `!init add` confirmation message — which precedes the init-list parse and therefore has no access to the classification signal. If Hook 1 hydrated eagerly, it would sometimes hydrate a combatant that Hook 2 later classifies as `avrae_madd`, requiring a corrective overwrite (two writes per combatant, the second undoing the first). Single-hook is architecturally cleaner: one classification signal, one routing decision, one write.

**Why single hook:**
- `!init list` hook: contains the HP-status token needed for `!init add` vs `!init madd` classification. One event, correct routing.
- Hook 1 (`!init add` eager hydration): cannot classify at add-time. Disabled in v1.

**Race window acceptance:** A small window remains where a player could narrate after `!init add` but before `!init list` posts. In practice, `!init list` follows within seconds and DMs almost always run it explicitly. The window is theoretical, not observed in play. If session logs show real friction, Hook 1 can be re-introduced in v1.x — the §11.K regex and the classification rule together give Hook 1 a viable path at that point. Filed in §12.

**§11.K regex status:** The locked regex `r"^(.+?) was added to combat with initiative"` is confirmed accurate (§11.K). It is no longer used for hydration routing in v1 (Hook 1 disabled). Code may keep it as an observability-only log line (`init_add_observed: name='{name}' ts={...}`) to surface add-time signals for future v1.x Hook 1 work, or strike it entirely from v1. Code's call — either is spec-compliant.

**Cross-reference §7:** Architecture diagram updated to single-hook flow. Sequencing timeline updated with race-window acceptance note.

---

### §11.K — Avrae `!init add` confirmation message format (LOCKED)

**LOCKED.** Live verification complete.

**Confirmed Avrae message format:**
```
"{name} was added to combat with initiative 1d20 (N) + M = TOTAL."
```
Plain-text new message. NOT an embed edit. The existing `on_message` Avrae-author filter sees it cleanly.

**Locked regex:** `r"^(.+?) was added to combat with initiative"` — anchored to start-of-message; requires "with initiative" suffix to avoid matching error messages or unrelated Avrae output.

**Multi-word names:** Non-greedy match stops at " was added" — "Garrik the Smith" extracts correctly. Covered by §9 test 34.

**Fat-finger error resilience:** If the DM omits the modifier (`!init add Garrik` instead of `!init add 0 Garrik`), Avrae posts an int-conversion error that does NOT match this regex. Hook 1 stays silent — correct behavior, no add occurred.

**Session-3 status:** Gate VERIFIED. Hook 1 is disabled in v1 (§11.J revised) — the regex is no longer used for hydration routing. Code may keep it as an observability log line or strike it from v1 implementation. Either is spec-compliant.

---

### §11.L — cr_str=None routing: caller-side decision (LOCKED)

**LOCKED: Option 1 (caller-side, per §3).**

The "CR is unknown → post prompt to `#dm-aside` → call `npc_hydrate_stats(source='generic_fallback')`" decision is made at the **caller** level, not inside the engine helper.

**What changed:**

- **§6 step 4 removed:** The implementation outline line `"if cr_str is None and source != 'generic_fallback': cr_str = _FALLBACK_CR"` is removed. The engine helper never internally resolves `None → CR-1/4` for any source. For `source='generic_fallback'`, the engine calls `fallback_stats()` directly.
- **§7 Path 1 code rewritten:** The `if not ok and not sigs.get('cr_str_written')` signal-check pattern is removed. Replaced with the §3 flow: caller checks `cr_hint is None` first, posts prompt first, then calls engine with `source='generic_fallback'`.
- **§3 is the authoritative view.** Any future implementation that re-introduces engine-side CR resolution for non-generic_fallback sources is a spec violation.

**Why this matters:** Under the removed engine-side pattern, `source='adhoc'` with `cr_str=None` would have silently resolved to CR-1/4 full fill (including `hp_max`) with no DM prompt. The DM prompt path from §3 would never fire for ad-hoc NPCs.

**Session-3 gate:** §9 test 30 ("CR-None ad-hoc NPC: `_post_hydration_prompt` called before engine invocation") must pass. The test verifies the caller-side prompt fires before — not after — `npc_hydrate_stats()` is called.

---

### §11.M — `!init madd` routing (LOCKED)

**LOCKED: Option C — skip hydration, defer to Avrae.**

**Context:** Avrae's `!init madd` command adds a 5e monster from Avrae's monster manual with full canonical stats (HP, AC, attacks, saves, special abilities). The DM optionally renames via `-name "Narrative Name"`. Hydration must NOT fire on these creatures — Avrae owns the mechanics; CR-band fallback stats would contradict the real monster data.

**Lock rationale:** Hydration is the fallback for entities Avrae cannot mechanically represent (DM homebrew, plot-bosses, ad-hoc NPCs). For `!init madd` creatures, Avrae IS the canonical source. Admitting this explicitly is correct per the three-layer doctrine: Avrae owns mechanics; the bridge layer defers when Avrae is the authority rather than substituting inferior estimates.

**Classification rule (LOCKED — empirical, from live verification):**

The init-list embed includes an HP-status token after each combatant's name. Observed tokens:

| Token | Meaning | Routing |
|-------|---------|---------|
| `<None>` | No Avrae HP backing — `!init add` path | Hydration path |
| `<Healthy>` | Avrae HP backing present — `!init madd` path | `npc_register_avrae_madd()` |
| `<Bloodied>` | Avrae-backed, mid-combat HP state | `npc_register_avrae_madd()` |
| `<Critical>` | Avrae-backed, mid-combat HP state | `npc_register_avrae_madd()` |
| `<Dead>` | Avrae-backed, defeated | `npc_register_avrae_madd()` |

**Rule:** any non-`<None>` token indicates Avrae-backed mechanics. The token IS the routing signal. No plausibility check, no HP-threshold, no command inference.

**Live verification results:**
- `!init add 0 testdummy` → "testdummy `<None>`" in init list (no Avrae backing → hydration)
- `!init madd Goblin` → "GO1 `<Healthy>`" (Avrae monster-manual stats → avrae_madd)
- `!init madd Goblin -name "Test Thug"` → "Test Thug `<Healthy>`" (-name flag works; narrative-name workflow confirmed)

**Architecture (single hook — §11.J revised):**

- Hook 2 (`_handle_init_list_event`) reads `status_token` from each combatant row in the parsed embed.
- `status_token == '<None>'` → standard hydration path (DM added NPC via `!init add`).
- `status_token != '<None>'` → `npc_register_avrae_madd(campaign_id, name)`. Creates/confirms `dnd_npcs` row with `avrae_source='avrae_madd'`; leaves all stat columns NULL.
- Advisory context: if `npc.get('avrae_source') == 'avrae_madd'`, renders `"(mechanics: Avrae monster entry)"` instead of NULL-column placeholder. HP reads from `dnd_combatant_state` as always.

**Session-3 implementation gate:** Verify that `parse_init_list_embed()` extracts `status_token` per combatant row. If the field is not currently parsed, this is a small parser extension. Treat as a first-step verification at Session 3 start (§9 test 38).

**GO1 identity-drift (DM-education point):** `!init madd Goblin` without `-name` assigns Avrae's generated name ("GO1"). Virgil records what Avrae provides. The correct workflow is `!init madd Goblin -name "Narrative Name"`. See §10 for full note.

**Out of scope for v1.x:** Avrae monster-data mirror (parsing Avrae's embed to populate stat columns). Filed in §12 as v2.

**Test coverage:** §9 tests 32–38.

---

## 12. Future work (out of scope — file but don't expand)

- **AI-driven NPC attacks (v2).** The primary payload use case for the stat block. Requires controller-authority reassignment from Avrae (new bot→Avrae interaction surface) and a turn-routing path in `dm_respond` to drive NPC initiative turns. Explicitly depends on Track 6 #4 stat hydration as infrastructure.

- **Shape (a) — Skeleton stat hints (v1.x).** Extend `skeleton_loader.py` to parse `CR:` lines in NPC entries. Write `cr_str` to `dnd_npcs` at session start. Reduces DM CR-prompt frequency for pre-planned encounters. See Appendix B for proposed syntax.

- **Hook 1 — `!init add` eager hydration (v1.x).** Re-introduce `_handle_init_add_event` if session logs show the race window (player narrates after `!init add` but before `!init list`) causes real friction in v1. At that point, the §11.K regex and the §11.M status_token rule together give Hook 1 a viable path: add-confirmation message fires → extract name → skip classification (no status_token available) → tentative hydration → if Hook 2 later sees `<Healthy>`, `npc_register_avrae_madd()` overwrites the tentative write. Deferred per §11.J: single-hook is cleaner for v1.

- **DM-rename guidance (v1.x).** If session logs show DMs routinely using `!init madd Goblin` without `-name`, the GO1 identity-drift creates orphaned `dnd_npcs` rows that don't match narrative names. A UI-level reminder (ephemeral prompt after detecting an auto-named combatant) or a `/rename-npc` slash command could surface the correct workflow. Deferred pending observed friction.

- **Encounter balance warnings (separate track).** CR-vs-party-level advisory ("Garrik at CR 2 vs. a level-1 party"). Track 4 #4+ territory. Hydration writes `cr_str` to `dnd_npcs`, which is available to future encounter-balance logic.

- **Loot tables via CR (separate track).** CR-appropriate loot generation is loot-side (Track 4 territory). The `cr_str` column is the hook.

- **Anonymous-shape combatants.** "A hulking shadow enters the fray." No proper-noun candidate for `npc_get_by_name`. Not addressable in v1 without entity-tracking at the narration layer.

- **Cross-session hydration persistence.** Hydrated stats survive in `dnd_npcs` across sessions. An NPC encountered in Session 17 and re-encountered in Session 18 carries their stats forward. This is the intended behavior; it hasn't been stress-tested and may require a "reset for new encounter" path if an NPC's role changes significantly between sessions.

- **Per-save granularity on save_bonus.** v1 stores a single `save_bonus` (average approximation). D&D 5e has six saves; v2 may expand to `str_save`, `dex_save`, `con_save`, `int_save`, `wis_save`, `cha_save` columns.

- **Avrae monster-data mirror (v2, `!init madd` creatures).** After `!init madd`, Avrae's embed contains the full monster stat block (HP, AC, attacks, saves). A v2 path could parse that embed and populate `dnd_npcs` stat columns from the monster entry, giving the LLM the same rich stat context it gets for hydrated NPCs. Requires parsing Avrae's embed format (which may change across Avrae versions) and deciding whether the mirror should overwrite or supplement the `avrae_source='avrae_madd'` marker. Deferred per §11.M — the `"(mechanics: Avrae monster entry)"` advisory marker is sufficient for v1 LLM context.

---

## Appendix A — CR-band default stat tables

Source: DMG Table 5 "Monster Statistics by Challenge Rating." HP values are midpoints of the CR-band HP ranges. Damage dice are representative expressions that produce the midpoint of the expected damage-per-round range for that band. AC reflects typical unarmored or lightly armored combatants; named NPCs with explicit armor or magical resistance use DM-provided values.

| CR  | HP  | AC | Atk Bonus | Damage Dice  | Save Bonus | Init Mod |
|-----|-----|----|-----------|--------------|------------|----------|
| 0   | 3   | 10 | +2        | 1d4          | +0         | +0       |
| 1/8 | 9   | 12 | +3        | 1d6          | +2         | +1       |
| 1/4 | 13  | 13 | +3        | 1d8          | +2         | +1       |
| 1/2 | 22  | 13 | +4        | 1d8+2        | +2         | +1       |
| 1   | 35  | 13 | +5        | 2d6+3        | +2         | +2       |
| 2   | 52  | 13 | +5        | 2d8+3        | +2         | +2       |
| 3   | 70  | 13 | +5        | 2d8+4        | +3         | +2       |
| 4   | 85  | 14 | +6        | 2d10+4       | +3         | +2       |
| 5   | 115 | 15 | +7        | 3d8+5        | +3         | +3       |
| 6   | 140 | 15 | +7        | 3d10+5       | +3         | +3       |
| 7   | 155 | 15 | +7        | 4d8+5        | +3         | +3       |
| 8   | 180 | 16 | +7        | 4d10+5       | +3         | +3       |
| 9   | 195 | 16 | +8        | 4d10+6       | +4         | +3       |
| 10  | 200 | 17 | +8        | 4d12+6       | +4         | +4       |
| 11  | 225 | 17 | +8        | 4d12+7       | +4         | +4       |
| 12  | 240 | 17 | +8        | 5d10+7       | +4         | +4       |

**Notes:**

- **HP:** Midpoint of the CR-band HP range from DMG Table 5. Callers may apply ±20% variance at v1.x for encounter diversity; v1 uses midpoints for determinism (Doctrine §1 — deterministic, not LLM-generated).
- **AC:** Reflects typical unarmored to lightly-armored combatants. An NPC in plate armor should have DM-provided AC, not the band default — the band default is a fallback for "we don't know."
- **Damage dice:** Representative expressions that produce approximately the midpoint of the expected damage-per-round range for that CR. They are not the canonical "this NPC uses a longsword" — they are a generic expression adequate for persistence-directive context and v2 AI attack resolution.
- **Save bonus:** Average approximation (proficiency bonus + typical Constitution modifier for that tier). v2 may expand to per-save granularity.
- **Init mod:** Derived from typical Dexterity for the CR tier. Low-AC combatants (unarmored) tend to have higher Dex; high-AC combatants (heavily armored) tend to have lower Dex. The values here use AC as a proxy: AC 10–13 → Dex ~+0–+1 → init_mod 0–1; AC 14–15 → Dex ~+2 → init_mod 2; AC 16+ → heavy armor, Dex +2 cap unless DM specifies otherwise.

---

## Appendix B — Skeleton stat-hint syntax (v1.x, NOT in v1 scope)

When Shape (a) ships in v1.x, `skeleton.md` NPC entries gain an optional `CR:` line. The skeleton parser reads it as a combat-stats hint, populates `dnd_npcs.cr_str`, and triggers pre-emptive hydration at session start.

### Proposed minimal syntax (v1.x)

```markdown
## Primary NPCs

### Garrik the Smith (blacksmith, Redhaven)
Motivation: Protect his community and family at all costs.
Voice: Gruff and direct. Reluctant to trust strangers.
CR: 1/2
```

The `CR:` line is:
- Case-insensitive (`cr:`, `CR:`, `Cr:` all parsed)
- Parsed by `normalize_cr()` — same validation as `/hydrate`
- Raises `SkeletonParseError` on invalid CR (strict, since skeleton.md is human-authored — fail loud)
- Stored in the NPC entry dict alongside `name`, `role`, `location_hint`, `description`
- Written to `dnd_npcs.cr_str` by `apply_skeleton()` via `npc_hydrate_stats(source='skeleton')`

### Optional full-stat override syntax (v1.x, for named antagonists)

For NPCs where the DM wants precise stat control (boss encounters, recurring antagonists):

```markdown
### Valdris Kaine (warlord, Kaine's Camp)
Motivation: Reunify the northern territories under his banner.
Voice: Measured, deliberate. Never raises his voice.
CR: 5
HP: 120
AC: 17
Attack: +9, 2d6+6 slashing
```

`HP:`, `AC:`, `Attack:` lines are parsed as direct column values and written by `apply_skeleton()` via individual `npc_hydrate_stats()` field overrides — bypassing the CR-band lookup for any explicitly provided field. These are `skeleton_origin=1` values and follow the "skeleton wins over parser" rule — they will not be overwritten by hydration.

### Rationale for v1.x deferral

The init-list trigger (v1) provides the same stat population as skeleton hints, via the DM-prompt path instead of pre-authoring. Skeleton hints are a pre-emptive optimization: DMs who plan encounters ahead of time can avoid CR prompts entirely. But the prompt path is low-friction enough to validate the hydration pipeline without requiring any `skeleton.md` authoring changes. Ship v1 first; if `source=generic_fallback` frequency is high in the first few sessions, skeleton hints are the lever to pull.

---

*Spec drafted: 2026-05-07, Session 1. Amendment pass #1: §11.H, §11.I, §11.J locked. Amendment pass #2: §11.A–§11.M locked; single-hook architecture; avrae_source column; §11.L caller-side routing; telemetry renamed. Amendment pass #3: §11.D sync-hint DROPPED (architectural; !init modify does not exist in Avrae); §11.J REVISED to single hook (Hook 2 only; race window accepted); §11.M LOCKED to HP-status-token classification rule (empirical, live-verified); §9 tests rewritten for token-based routing; GO1 identity-drift documented; §12 Hook-1 v1.x and DM-rename items added. All three pre-Session-3 gates RESOLVED. SPEC COMPLETE — Session 3 implementation may begin.*
