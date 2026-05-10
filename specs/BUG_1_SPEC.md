# BUG_1_SPEC.md — Pending Roll Directive Tracking

**Server-side spec. NOT mirrored to PC.**

Bug 1 — Auto-narration after roll. When the DM emits `!check stealth` in
#dm-narration, Avrae rolls, prior bot behavior was to wait silently for the
next player input. Goal post-Track-7: auto-fire `dm_respond` once the matched
roll arrives, scoped to the rolling actor.

This spec covers **Phase 1 — telemetry-only**. Phase 1 ships the parser, the
matcher, the pending-directive table, and footer-transition observability.
The matcher logs would-fire decisions but does NOT auto-fire `dm_respond`.
Phase 2 binds auto-narration to the verified Phase 1 layer.

Doctrine alignment: §39 (pure-observability first), §17 (single write paths
per field), §1a/§1b (LLM never decides; deterministic engine writes), §47
(spec-drift discipline — recon-first, lock against real code), §73 (single
restart per session, Discord verification is human-in-the-loop), §59
(pure-function-in-orchestration as soft-fail wrapper pattern).

---

## §A. Schema

### §A.1. New table — `dnd_pending_roll_directives`

Per-campaign pending row representing the most recent DM `!check`/`!save`/
`!cast` directive that hasn't yet matched an Avrae roll. UNIQUE constraint
on `campaign_id` means one pending directive per campaign max — later
directives REPLACE prior unresolved ones.

```sql
CREATE TABLE IF NOT EXISTS dnd_pending_roll_directives (
    campaign_id        INTEGER PRIMARY KEY,
    actor_name         TEXT    NOT NULL,
    check_type         TEXT    NOT NULL,
    source_message_id  TEXT    NOT NULL,
    created_at         TEXT    NOT NULL,
    expires_at         TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_pending_directive_msg
    ON dnd_pending_roll_directives(source_message_id);
```

Defined in `dnd_engine.py:db_init()` adjacent to `dnd_time_advancements`.
Added to `_CAMPAIGN_SCOPED_TABLES` between `dnd_time_advancements` and
`dnd_scene_state` (delete order: child rows first, scene_state last).

### §A.2. Schema delta to `dnd_scene_state` — `last_active_actor`

The locked S31 architecture's "footer is becoming load-bearing structural
state" clause was forward-looking. Recon (Q3) revealed exploration-mode
footer-actor was rendered-but-not-persisted — `actor_label = ', '.join(actor_names)`
in `_dm_respond_and_post` is computed at narration-emit time and never
written to engine state. Phase 1 has to **make** the footer-actor structural
before the matcher can deterministically read it; pure observation isn't
enough.

```sql
ALTER TABLE dnd_scene_state
    ADD COLUMN last_active_actor TEXT DEFAULT '';
```

Defined in `dnd_engine.py:db_init()` ALTER TABLE branch (idempotent — gated
by `PRAGMA table_info(dnd_scene_state)` membership check).

`get_scene_state()` extends its SELECT and return dict to include
`last_active_actor`. Empty string `''` = "no active actor in footer yet."

---

## §B. Single writer

### §B.1. `dnd_pending_roll_directives`

Sole writer is the matcher in `discord_dnd_bot.py` via the engine helpers:

- `pending_directive_upsert(campaign_id, actor_name, check_type, source_message_id, ttl_seconds) → {replaced, prior}` — INSERT OR REPLACE; returns prior row info so the matcher can log `pending_directive_replaced` before the swap
- `pending_directive_get_active(campaign_id) → row | None` — read with **lazy TTL sweep**: if `expires_at` has passed, deletes the row, emits `pending_directive_expired`, returns `None`
- `pending_directive_consume(campaign_id) → bool` — DELETE on match
- `pending_directive_delete_by_message(campaign_id, source_message_id) → row | None` — DELETE only when the source message matches; used by the on_message_edit cancel path
- `pending_directive_age_seconds(created_at_iso) → int` — pure helper for log-line `directive_age_s` / `old_age_s` fields

Per §1a/§1b: no LLM in the directive emission, matching, or consumption
paths. The matcher is purely deterministic.

### §B.2. `dnd_scene_state.last_active_actor`

Sole writer is `update_last_active_actor(campaign_id, new_actor, trigger)`
in `dnd_engine.py`. **Mode-disjoint single-writer discipline** — same shape
as the Bug 5 narrow-exception framing for `init_scene_state`. Three callers,
mode-disjoint:

- **Exploration mode write** — `_dm_respond_and_post` after
  `actor_names_canonical` is computed; trigger=`dm_respond`
- **Combat mode set** — `set_active_turn` after the combat-state row is
  written; trigger=`combat_turn_set`
- **Combat mode clear** — `clear_active_turn` after the combat-state row is
  deleted; trigger=`combat_turn_clear`
- **Session open clear** — `/play` after `init_scene_state`;
  trigger=`play`

The writer reads prior value, no-ops on no-change (no log, no UPDATE), and
emits `footer_actor_changed` on transitions. Per §17, no parallel writers
add to this column without the same narrow-framing test.

---

## §C. DM identity gate (Q1 answer)

**Helper:** `is_dm_or_creator(interaction: discord.Interaction) → bool` at
`discord_dnd_bot.py:226`. Two qualifying paths: `manage_guild` perm OR the
user created the active campaign (solo-as-DM friction fix).

**Decision: wrap, not reuse directly.** New sister helper
`_is_dm_message(message, campaign) → bool` mirrors the same two-path check
against `discord.Message`'s `author`/`guild` fields. Reusing
`is_dm_or_creator` directly would require synthesizing an `Interaction`
object from a `Message` — wrapping keeps the existing helper untouched and
the surface clean.

`_is_dm_message` lives in `discord_dnd_bot.py` adjacent to the directive
parser helpers.

---

## §D. Directive parser regex (Q2 answers)

### §D.1. Final patterns

Single regex with kind-alternation captures the three Phase 1 directives:

```python
_DM_DIRECTIVE_RX = re.compile(
    r"^\s*(?:<@!?\d+>\s*)?"            # optional leading @-mention
    r"!(?P<kind>check|save|cast)\s+"   # !check / !save / !cast
    r"(?P<skill>.+?)\s*$",
    re.IGNORECASE,
)
```

Trigger surface: literal `!check ` / `!save ` / `!cast ` (trailing space).
Detection happens against `action.lower().startswith(_DIRECTIVE_TRIGGER_PREFIXES)`.
The `\s+` after the kind requires at least one whitespace; `.+?` requires
≥1 character in the captured skill. So `!check` (no skill) / `!check  `
(empty after whitespace) parse to None.

`!attack` is **excluded** from Phase 1 — combat-mode directive tracking is
out of scope per the spec's "Combat-mode → log `directive_creation_skipped:
reason=combat_mode`, no row created" branch. Phase 2 retunes if observed
play data justifies attack-directive tracking.

### §D.2. Skill normalization path

Phase 1 stores the DM-typed skill verbatim (preserves casing for human-
readable logs). At Avrae roll arrival, the matcher canonicalizes both
sides via `_normalize_skill_for_match(s) = ' '.join(s.lower().split())`
and compares.

**No alias map in Phase 1.** Aliases like `sneak`↔`stealth` will silently
miss in Phase 1 — observable via `pending_directive_expired` log entries
that name a non-Avrae-canonical skill. Phase 2 designs alias handling
from the observed miss rate. Doctrine §14 (strict literal match +
telemetry > fuzzy match) endorses this stance.

The matcher does NOT delegate to `avrae_listener._extract_detail` for
DM-input parsing — `_extract_detail` operates on Avrae's roll-embed output,
not on DM-typed text. There's no shared canonical-skill vocabulary at
directive-emit time; that's an alignment Phase 2 may add.

### §D.3. Variant edge cases (Phase 2 calibration candidates)

These currently miss the bare-skill regex AND/OR fail the post-parse
clean-validation:

- `!check stealth adv` — trailing modifier word; skill captured as
  "stealth adv"; `_directive_skill_is_clean` returns
  `(False, 'trailing_args')`
- `!check stealth -dc 15` — flag-shaped trailing argument; clean check
  returns `(False, 'trailing_args')`
- `!check stealth #disarm trap` — comment; clean check returns
  `(False, 'comment')`
- `!check perception everyone` — group-directive keyword in skill; clean
  check returns `(False, 'group_directive')` → routes to
  `directive_creation_skipped: reason=group_directive`
- `!c stealth` — Avrae shorthand; trigger detection requires literal
  `!check ` / `!save ` / `!cast ` with trailing space, so `!c` never
  enters the matcher path. Filed for Phase 2.
- `!checkpoint advance` — `!check` substring without trailing space;
  trigger detection rejects. No false positive.

Filed as Phase 2 calibration candidates per Doctrine §14 (strict literal
match + telemetry > fuzzy). Phase 1 logs miss-rate; Phase 2 picks alias
shape from observed signal.

---

## §E. Footer-actor read path (Q3 answer + HALT resolution)

### §E.1. Recon finding

Combat-mode footer-actor: clean source — `dnd_combat_state.character_name`
via `get_active_turn(campaign_id)` in `dnd_engine.py:1681`.

Exploration-mode footer-actor: NO clean engine source pre-Phase 1. The
`⚔ {actor_label}` rendered in the footer at `discord_dnd_bot.py:1773-1774`
came from `actor_names = ', '.join(...)` computed at `_dm_respond_and_post`
time and never persisted to DB. Locked option (b) "query engine state
directly" assumed such state existed; it didn't.

### §E.2. HALT resolution (S32 planner delta)

Add `last_active_actor TEXT DEFAULT ''` column to `dnd_scene_state` —
mode-disjoint single-writer discipline. The matcher reads via
`get_scene_state(campaign_id)['last_active_actor']`. Combat-mode override
via `dnd_combat_state.character_name` is moot in v1 (matcher short-circuits
combat) but documented for Phase 2 forward-reference: when Phase 2 broadens
to combat, `set_active_turn`'s combat-side write to `last_active_actor`
already keeps the column consistent.

### §E.3. Source-of-truth file

`dnd_engine.py` holds the column definition (db_init), the SELECT
projection (`get_scene_state`), and the writer (`update_last_active_actor`).
All read paths go through `get_scene_state`.

---

## §F. Matcher state machine

The matcher is two branches plus an edit-cancel branch:

### §F.1. Directive emit (DM types `!check`/`!save`/`!cast`)

Triggered from `on_message` when:
- Author is DM (`_is_dm_message`)
- Channel is `#dm-narration`
- Action starts with one of `('!check ', '!save ', '!cast ')`

Skip-cascade:

1. **Trailing-args / comment / group / shorthand** (clean-validation fail):
   - `reason=group_directive` → log `directive_creation_skipped:
     campaign={N} reason=group_directive`, no row
   - All others → log `directive_text_unparsed: campaign={N} raw={text}
     reason={trailing_args|comment|other}`, no row
2. **Combat mode** (`scene_state.mode == 'combat'`) → log
   `directive_creation_skipped: campaign={N} reason=combat_mode`, no row
3. **No footer-actor** (`last_active_actor == ''`) → log
   `directive_creation_skipped_no_footer: campaign={N} skill={skill}
   reason=no_active_actor`, post no-footer aside, no row

If none of the skip conditions hold:
- `pending_directive_upsert` writes the row
- If `replaced=True`: log `pending_directive_replaced: campaign={N}
  old_actor={X} old_skill={Y} new_actor={A} new_skill={B} old_age_s={N}`
- Always log `directive_bound_to_footer_actor: campaign={N} actor={name}
  skill={skill} directive_age_s=0`

### §F.2. Avrae roll embed arrival

Triggered from `on_message` Avrae branch after `parse_avrae_embed` produces
an event AND actor canonicalization completes (so `event['actor']` is the
canonical form).

- `event['kind']` ∉ {check, save, cast} → silent ignore (attack/damage/rest/
  roll never match a Phase 1 directive)
- `pending_directive_get_active` returns None → silent ignore (no pending
  directive, or sweep just expired one and emitted `pending_directive_expired`)
- Skill mismatch (any actor) → silent ignore per spec
- Skill match + actor match → log `directive_would_fire_dm_respond:
  campaign={N} actor={name} skill={skill} directive_age_s={N}`, consume
  row (`pending_directive_consume`). **DO NOT auto-fire `dm_respond`.**
- Skill match + actor mismatch → log `directive_actor_mismatch:
  campaign={N} expected_actor={X} actual_actor={Y} skill={skill}`, post
  wrong-actor aside. **Do not consume the row.**

### §F.3. TTL expiry (lazy sweep)

`pending_directive_get_active` checks `expires_at` against UTC now on every
read. When expired:
- Compute `age_s = utcnow() - created_at`
- DELETE row
- Log `pending_directive_expired: campaign={N} actor={name} skill={skill}
  age_s={N}`
- Return `None`

No background sweeper. Sweep-on-access is the only expiry path; rows that
sit in the table without read-traffic eventually get swept the next time
the campaign sees an Avrae roll or a new directive.

### §F.4. DM message edit (cancel path)

Triggered from `on_message_edit` when:
- Channel is `#dm-narration`
- Author is the DM (`_is_dm_message`)
- A pending directive exists for the campaign with
  `source_message_id == after.id`

Re-parses the new content. If the new content still parses to the SAME
skill (case-insensitive), no-op (typo-fix or cosmetic edit). Otherwise:
- `pending_directive_delete_by_message(campaign_id, after.id)`
- Log `pending_directive_cancelled: campaign={N} reason=edit`

---

## §G. Trigger taxonomy (S32 planner delta)

`footer_actor_changed: campaign={N} from={old_actor|none} to={new_actor|none}
trigger={dm_respond|play|combat_turn_set|combat_turn_clear}` fires at every
write site on actor transition (no-op on no-change). Four triggers, granular
not coarse — Phase 2 trigger criterion 3 and the ghost-trigger
cross-reference depend on the granularity.

| Trigger              | Write site                         | File / function                                           |
|----------------------|------------------------------------|-----------------------------------------------------------|
| `dm_respond`         | Exploration narration response     | `discord_dnd_bot.py:_dm_respond_and_post`                 |
| `play`               | Session open (clear)               | `discord_dnd_bot.py` `/play` handler                      |
| `combat_turn_set`    | Combat turn announcement           | `dnd_engine.py:set_active_turn`                           |
| `combat_turn_clear`  | Combat end / clear                 | `dnd_engine.py:clear_active_turn`                         |

**`state_footer_render` from the original prompt is dropped.**
`render_state_footer` is a pure read; not a write site.

---

## §H. Within-ship verification ordering

Sub-phase 1a verifies BEFORE sub-phase 1b's matcher code reads the column.
This preserves §39's spirit at the sub-ship level even though both
sub-phases ship in the same restart.

**Sub-phase 1a:** `last_active_actor` column + four writers + four
`footer_actor_changed` triggers wired. Verify by emitting `dm_respond`
turns + `set_active_turn` / `clear_active_turn` cycles + a `/play`,
confirm log lines fire with correct from/to/trigger fields, confirm column
reflects current actor.

**Sub-phase 1b:** `dnd_pending_roll_directives` table + parser + matcher
+ telemetry. Reads `last_active_actor` from the verified 1a layer. Verify
via the §M test scenarios end-to-end.

Both sub-phases ship in the same Phase 1 deploy and same restart per §73.
Sub-phase ordering is verification sequencing within the ship, not
separate restarts.

---

## §I. Telemetry log line specs (verbatim)

### §I.1. `footer_actor_changed`

```
footer_actor_changed: campaign={N} from={old_actor|none} to={new_actor|none} trigger={dm_respond|play|combat_turn_set|combat_turn_clear}
```

Fires at every footer-actor write site on transition (no-op on no-change).
- `from=` is the prior `last_active_actor` value, or `none` when empty
- `to=` is the new `last_active_actor` value, or `none` when empty
- `trigger=` is one of four values per §G

### §I.2. `directive_bound_to_footer_actor`

```
directive_bound_to_footer_actor: campaign={N} actor={name} skill={skill} directive_age_s=0
```

Fires when a pending directive successfully binds at directive-emit time.
`directive_age_s` is always `0` here by definition.

### §I.3. `directive_creation_skipped`

```
directive_creation_skipped: campaign={N} reason={combat_mode|group_directive}
```

Fires when the directive emission is skipped for a structural reason that
isn't no-footer (which has its own log). Two reasons in v1.

### §I.4. `directive_creation_skipped_no_footer`

```
directive_creation_skipped_no_footer: campaign={N} skill={skill} reason=no_active_actor
```

Fires when the matcher has a clean directive but `last_active_actor == ''`.
Dedicated log line so Phase 2 trigger criterion 2 (≥80% successful binds)
can grep cleanly.

### §I.5. `pending_directive_replaced`

```
pending_directive_replaced: campaign={N} old_actor={X} old_skill={Y} new_actor={A} new_skill={B} old_age_s={N}
```

Fires when a new directive replaces an existing pending row.
`old_age_s` is computed against the prior row's `created_at`.

### §I.6. `directive_would_fire_dm_respond`

```
directive_would_fire_dm_respond: campaign={N} actor={name} skill={skill} directive_age_s={N}
```

Fires when an Avrae roll matches a pending directive on actor + skill.
Phase 1 does NOT auto-fire `dm_respond`. The row is consumed (deleted).
Phase 2 trigger criterion 4 cross-references each entry against a
preceding `directive_bound_to_footer_actor` for the same actor+skill
within TTL.

### §I.7. `directive_actor_mismatch`

```
directive_actor_mismatch: campaign={N} expected_actor={X} actual_actor={Y} skill={skill}
```

Fires when an Avrae roll matches the pending skill but the rolling actor
differs from the directive's bound actor. Row remains; aside is posted.

### §I.8. `pending_directive_expired`

```
pending_directive_expired: campaign={N} actor={name} skill={skill} age_s={N}
```

Fires lazily inside `pending_directive_get_active` when the existing row's
`expires_at` is in the past.

### §I.9. `pending_directive_cancelled`

```
pending_directive_cancelled: campaign={N} reason=edit
```

Fires from `on_message_edit` when the DM edits a directive's source
message and the new content no longer matches the same kind+skill.

### §I.10. `directive_text_unparsed` (S32 planner delta)

```
directive_text_unparsed: campaign={N} raw={text} reason={trailing_args|shorthand|comment|other}
```

Fires when DM-authored text in #dm-narration starts with `!check`/`!save`/
`!cast` but fails the bare-skill regex (or fails the post-parse
clean-validation for trailing args / comments). `reason=` is best-effort
classification per `_classify_unparsed_reason` and
`_directive_skill_is_clean`. Phase 2 calibration uses this miss surface to
decide alias / variant handling.

---

## §J. Aside wording (verbatim, locked)

Operational tone, not error tone. Posted to `#dm-aside`.

**No-footer skip:**

> Roll directive not tracked: no active actor in footer yet. Address a
> player before issuing a directed check.

**Wrong-actor skip:**

> Roll directive bound to {expected_actor} — that roll is not consumed.
> Wait for {expected_actor} to roll, or address {actual_actor} first.

---

## §K. Phase 1 vs Phase 2 scope split

### §K.1. Phase 1 (this ship)

- DM directive parser
- Pending-directive table + cascade
- Matcher with telemetry-only behavior
- Footer-transition observability (`footer_actor_changed` at four trigger
  sites)
- New `last_active_actor` column on `dnd_scene_state`
- Asides posted on no-footer skip and wrong-actor mismatch

### §K.2. Phase 2 (future ship)

Phase 2 binds auto-narration on top of the verified Phase 1 layer:

- Replace `directive_would_fire_dm_respond` log emission with an actual
  `_dm_respond_and_post` invocation scoped to the directive's actor
- Tune TTL based on observed age-at-resolution + age-at-expiry
  distribution (Phase 1's 300s default is a placeholder)
- Optional alias map for skill normalization driven by Phase 1 miss data
- Optional combat-mode directive handling (currently skipped)
- Optional late-roll retroactive consumption (filed below as v1.x)
- Optional stale-footer name parsing (filed as F-58 candidate)

---

## §L. Phase 2 trigger criteria (verbatim — deterministic gate, not judgment)

Phase 2 ships only after ALL FOUR criteria are answerable yes against
the Phase 1 log set:

1. **≥ 5 directive-emit events observed in real play across ≥ 2 sessions**
   — grep `directive_bound_to_footer_actor:` count, distinct session days
2. **≥ 80% of directives bind successfully to footer actor** — ratio of
   `directive_bound_to_footer_actor` to `directive_bound_to_footer_actor +
   directive_creation_skipped_no_footer` ≥ 0.8
3. **Zero observed cases of `footer_actor_changed` firing without a
   corresponding orchestration event** — every `footer_actor_changed`
   line must trace to a preceding `_dm_respond_and_post`,
   `set_active_turn`, `clear_active_turn`, or `/play` event in the same
   journal window. Granular trigger field (§G) makes this grep-evaluable.
4. **Zero observed ghost-trigger candidates** — every
   `directive_would_fire_dm_respond` must cross-reference a preceding
   `directive_bound_to_footer_actor` for the same actor+skill within TTL

Each criterion answers yes/no by greppable journal pattern. No subjective
quality assessment.

---

## §M. Verification (Phase 1)

Sub-phase 1a (writer + log verification) before 1b matcher reads. One
restart total at deploy.

| # | Step | Expected log shape |
|---|------|--------------------|
| 1 | `/play` opens new campaign | `state_footer:` + (if prior actor) `footer_actor_changed: from={X} to=none trigger=play` |
| 2 | Player narrates → bot responds | `footer_actor_changed: from=none to={display_name} trigger=dm_respond` |
| 3 | `!init begin` + `!init add` cycle to a turn | `set_active_turn: ...` + `footer_actor_changed: from={prior} to={turn_actor} trigger=combat_turn_set` |
| 4 | `!init end` | `clear_active_turn: ...` + `footer_actor_changed: from={turn_actor} to=none trigger=combat_turn_clear` |
| 5 | DM types `!check stealth` after at least one player turn | `directive_bound_to_footer_actor: campaign={N} actor={display} skill=stealth directive_age_s=0` |
| 6 | DM types `!check stealth` from non-DM account | no log (parser path is gated on `_is_dm_message`); existing player flow runs |
| 7 | DM types `!check stealth` after `/play`, before any player turn | `directive_creation_skipped_no_footer:` + no-footer aside posted |
| 8 | Avrae roll-embed for matching actor + skill arrives | `directive_would_fire_dm_respond:` + row consumed; **`dm_respond` NOT fired** |
| 9 | Avrae roll-embed arrives for wrong actor (skill matches) | `directive_actor_mismatch:` + wrong-actor aside posted; row remains |
| 10 | DM edits the directive message, removing `!check` | `pending_directive_cancelled: reason=edit` |
| 11 | DM emits directive then waits 5+ minutes; Avrae roll arrives | `pending_directive_expired:` + silent ignore on roll |
| 12 | DM types `!check stealth adv` | `directive_text_unparsed: ... reason=trailing_args` |

Phase 2 trigger criteria are evaluable against this log set as designed
(each of the four criteria can be answered yes/no by grepping).

---

## §N. v1.x candidates filed

- **Late-roll retroactive consumption** — when an Avrae roll arrives more
  than TTL seconds after the directive emit, can the matcher still
  retroactively consume? File only if Phase 1 logs show the pattern.
- **Stale-footer name parsing — F-58 candidate** — DM types `!check
  stealth` meaning Hilda when footer shows Donovan; v1 strict-binds to
  Donovan's actor and `directive_actor_mismatch` flags. File F-58 in
  FAILURES.md as the v1.1 candidate for explicit-name parse from the
  surrounding text (e.g. "Hilda, !check stealth").
- **Group-roll natural-language parsing** — DM says "everyone roll
  perception" without `!`-prefix; Phase 1 doesn't detect this surface
  at all. File only if Phase 1 logs show the pattern.
- **Skill alias map (sneak↔stealth, etc.)** — file only if Phase 1
  miss-via-expiry rate exceeds threshold.
- **Avrae shorthand (`!c`, `!s`, `!ca`)** — Phase 1 doesn't trigger on
  shorthand prefixes. Trivial to add when Phase 2 designs alias surface.

---

## §O. TTL rationale

`PENDING_DIRECTIVE_TTL_SECONDS = 300` (5 min) as the Phase 1 default.
Defined in `avrae_listener.py` adjacent to `EVENT_TTL_SECONDS` for
sibling-scan visibility.

5 min is a deliberate over-estimate — most directed checks resolve in
seconds (DM types `!check stealth`, addressed player rolls). Setting it
high in v1 maximizes the chance of seeing both endpoints of the
distribution: most rows expire well within TTL via consumption, the rare
row that genuinely sits unmatched expires explicitly. Phase 2 retunes
from the observed age-at-resolution + age-at-expiry distribution.

---

## §P. Doctrine candidates (filed, not anchored)

Two candidates surfaced, both sibling to §39. Per §59 (don't anchor a new
doctrine until a second instance shows the pattern), neither is anchored
yet.

### §P.1. "Instrument before binding to existing surface"

Originally proposed by the planner. Make existing surfaces observable
before *other systems* bind to them, not just before *behavior* binds.
§39 covers behavior-before-instrumentation; this candidate extends to
sibling systems binding to existing surfaces.

### §P.2. "Presentation-derived state is not structural state until
persisted to engine"

Surfaced from Q3 recon. The S31 spec conflated rendered output
(`actor_label` in the embed footer) with structural state — they look
identical from outside the running system, but the binding test ("can a
downstream system query it deterministically?") reveals the gap. Spec
sessions that lock architecture conversationally should treat any "the
X tells us Y" claim as needing a recon check on whether X actually
persists Y or just renders it.

Both candidates pattern-watch for second instance per §59.

---

## §Q. Files touched

- `dnd_engine.py` — schema (table + ALTER TABLE), `_CAMPAIGN_SCOPED_TABLES`,
  `update_last_active_actor`, `pending_directive_*` engine helpers, get_scene_state
  SELECT projection, set_active_turn / clear_active_turn writer hooks
- `avrae_listener.py` — `PENDING_DIRECTIVE_TTL_SECONDS = 300`
- `discord_dnd_bot.py` — directive parser regex + helpers,
  `_handle_dm_roll_directive` (emit branch), `_handle_dm_roll_arrival`
  (match branch), `_post_dm_aside`, on_message wiring (DM directive
  branch + Avrae roll-arrival match), on_message_edit cancel path,
  `_dm_respond_and_post` writer wiring, `/play` writer wiring
- `test_pending_roll_directives.py` — 19 engine-layer assertions

---

## §R. Out of scope (Phase 1)

- Auto-firing `dm_respond` (Phase 2)
- Slash command for directive cancellation (edit-detection is the only
  cancel path in v1)
- Late-roll retroactive consumption (v1.1 candidate per §N)
- Stale-footer name-parsing fallback (v1.1 candidate; F-58)
- Combat-mode directive handling beyond the telemetry-skip
- Group-roll detection beyond the telemetry-skip
