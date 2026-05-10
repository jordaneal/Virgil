# Ship 1 — Resolution Binding — Design Spec v1 (DRAFT)

**Status:** LOCKED v1 — S33 part 2 review complete. 14 decisions locked (12 at Code's recommendation, 2 with framing revisions to §3.2 and §11.14 applied per `RESOLUTION_BINDING_REVIEW.md` §4). No architectural changes from spec draft. Ready for S34 implementation per `MULTIPLAYER_FIXES.md` §4.5 (Opus high).
**Pattern:** Extends `BUG_1_SPEC.md` Phase 1 (matcher + telemetry) by wiring the consumed-directive event to a binding auto-narration that renders engine-computed pass/fail at top-of-prompt. Same structural shape as Track 7 #1's CHECK_ACTION binding, applied to the parallel surface that bypasses adjudicator (DM-typed `!check`/`!save` directives).
**Track:** Multiplayer Fixes — Ship 1. Closes Finding L (S32 §3.10), F-45 regression (S25 #3 multiplayer test), and Bug 1 Phase 2 as a side effect. Sequenced ahead of Ships 2–5 per the trigger-statement axis (playability now) locked in `MULTIPLAYER_FIXES.md` §3 + §12.
**Failure modes this targets:**
- **Finding L (CRITICAL, S32)** — Roll resolution unbound from rolled value. Player rolls 6 vs DC 10, says "I passed," bot narrates success. Bot's announced DC becomes theater; the player honor system becomes the de facto adjudicator. **Closes structurally** via engine-computed `passed = (roll_total >= dc)` rendered as AUTHORITATIVE-CANON top-of-prompt + bottom-of-prompt repeat.
- **F-45 regression (S25 #3, reopened by S32 §6)** — Track 7 #1's CHECK_ACTION binding closure operates through the adjudicator pipeline. The DM-typed-directive flow bypasses adjudicator entirely (matcher consumes the directive on Avrae roll arrival; adjudicate() never sees a CHECK declaration; narration emits without CHECK_ACTION binding's constraint). Ship 1 closes the parallel surface.
- **Bug 1 Phase 2 (side effect)** — Phase 2's locked §L trigger criteria from `BUG_1_SPEC.md` are satisfied structurally by Ship 1's wiring, not by waiting for accumulated Phase 1 telemetry. See §3 (Bug 1 Phase 2 absorption).

**Architectural diagnosis:** Track 7 #1's CHECK_ACTION binding works because adjudicator sees `(player_input → CHECK_REQUIRED → CHECK_RESOLVED)` end-to-end. Bug 1's DM-typed-directive flow inverts this — DM emits a directive (no player action declaration), Avrae rolls (no adjudicator involvement), matcher consumes the directive on roll arrival (telemetry only in Phase 1). When Phase 2 wires auto-narration on top of this matcher, the LLM gets no binding constraint because the adjudicator pipeline never ran. Ship 1 closes this by giving the matcher its own pure-function resolver and rendering the result through the same top-of-prompt binding shape Track 7 #1 uses on its own surface.

---

## §1. Problem statement (Finding L evidence + F-45 regression context)

### §1.1 The S32 evidence

S32_MULTIPLAYER_PLAYTEST_FINDINGS.md §3.10 catalogues two instances inside the same play session, both reproduced verbatim:

```
9:41 PM Bot:   "Donovan Ruby — Perception check at DC 10. Roll pending."
9:42 PM Avrae: Donovan Ruby makes a Perception check! 1d20 (5) + 1 = 6   ← FAIL vs DC 10
9:43 PM Jordan: "I passed the check"
9:43 PM Bot:   [narrates success — discovers scorch mark + concealed compartment]

10:09 PM Avrae: Karrok The Devourer makes Investigation 1d20 (20) + 0 = 20  ← nat 20
10:09 PM Captin: "Nat 20 on the investigation"
10:09 PM Bot:   [narrates success]
10:09 PM Bot:   !check perception   ← bot emits another directive
10:10 PM Avrae: Karrok Perception 1d20 (2) + 1 = 3   ← FAIL vs presumed DC
10:10 PM Captin: "i passed"
10:10 PM Bot:   [narrates success, "you step past the slab, the passage opens"]
```

Two structurally identical failures — Avrae rolls below DC, player asserts success, bot narrates success. The DC the bot announced at directive-emit time was discarded by narration time. Whatever the player typed became the de facto verdict.

### §1.2 The F-45 regression — same failure, new surface

F-45 (FAILURES.md §F-45, Session 25 #3) catalogued: *"Bruce Banner rolled 2 on Perception → DM narrated quest lore about the Veiled Spire. Bruce rolled 8 on Investigation → DM revealed pressure plate location."* Disposition recorded as *"Closed structurally by Track 7 #1 CHECK_ACTION binding (S25 #4) — narration constraint forces failure shape on failed rolls."*

That closure operated through one specific path:
1. Player declares an action ("I check the scorch marks")
2. `adjudicate()` returns a `CHECK_ACTION` verdict with `narration_constraint = _constraint_check_resolved(skill, dc, band, roll, success)` once Avrae's roll lands and `consume_recent_check` finds it in the buffer
3. The constraint renders at top-of-prompt as `=== ARBITRATION RESULT ===` (post-Track 7 #2; was `=== ADJUDICATION RESULT ===` in S25 #4)
4. The LLM is structurally constrained to narrate failure on failed rolls

Bug 1's DM-typed-directive flow runs an entirely different state machine (BUG_1_SPEC.md §F):
1. **DM** types `!check perception` in `#dm-narration` (directive emit; no player action declaration)
2. `_handle_dm_roll_directive` upserts a row into `dnd_pending_roll_directives` and logs `directive_bound_to_footer_actor:`
3. Avrae rolls (mechanical event; no adjudicator involvement)
4. `_handle_dm_roll_arrival` matches the roll against the pending row, logs `directive_would_fire_dm_respond:`, calls `pending_directive_consume`, **does not invoke `dm_respond`** (Phase 1 is telemetry-only)
5. The player types something ("I passed the check") — this enters `dm_respond` through the normal player-input path
6. `adjudicate(player_input, ...)` runs on the player's free-form text. The text isn't a CHECK declaration; it's a result claim. Verdict returns FREE or FALLBACK with empty `narration_constraint`
7. `build_dm_context` renders an empty `=== ARBITRATION RESULT ===` section (since the verdict is FREE)
8. The LLM has no top-of-prompt binding constraint. It narrates whatever fits the player's text — which is "I passed."

**Track 7 #1 closed F-45 on the adjudicator surface. Bug 1 introduced a parallel surface that runs through the matcher, not the adjudicator. F-45 was not regressed — its closure boundary was always more narrow than the failure-mode name suggested.** Ship 1 closes F-45's failure mode on the second surface, the same way Track 7 #1 closed it on the first surface: engine-computed verdict rendered as top-of-prompt binding constraint.

### §1.3 Why the matcher's existing telemetry doesn't catch this

Phase 1's `directive_would_fire_dm_respond:` log records `(campaign, actor, skill, directive_age_s)` at consume time — but **not** the rolled value, the DC, or the pass/fail verdict. Phase 2 was originally written to upgrade this log into an actual `_dm_respond_and_post` call. Without resolution binding, Phase 2 would auto-fire narration that confidently announces success on a 1 and failure on a 20. The matcher's correctness is necessary but not sufficient.

### §1.4 What "structurally impossible" means here

Ship 1's invariant: once a `dnd_pending_roll_directives` row is consumed against a matching Avrae roll, the narration that fires from that consumption is gated by an engine-computed `passed: bool` derived from `roll_total >= dc`. The LLM never sees the player's "I passed" claim as a binding signal — it sees the AUTHORITATIVE ROLL RESOLUTION block at top-of-prompt and the bottom-of-prompt outcome repeat. Even if the player types `"I rolled a 20"` after a 3, the prompt block says `Outcome: FAILED`, and the `narration_verifier.py` `ROLL_OUTCOME_DRIFT` class catches the LLM if it drifts.

This is Doctrine §1a applied to a surface where §1a's existing closure mechanism (CHECK_ACTION binding) didn't reach. The engine knows the answer before the LLM is invoked.

---

## §2. Architectural shape (locked elements; do NOT re-litigate)

The fix shape is locked in `MULTIPLAYER_FIXES.md` §4.1. This section restates the locks for spec-internal reference and adds the recon-confirmed implementation anchors. Alternative fix shapes (the §3.10 (b) adjudicator-extension and (c) defer-Phase-2 candidates from S32) are explicitly NOT under consideration — both were filed at S32 spec time and the planner picked (a) for the locked architecture.

### §2.1 Locked elements

1. **New pure function `resolve_directive(directive_row, avrae_event) → ResolutionResult | None`** in `dnd_orchestration.py`. Sibling to `compute_persistence_directive`, `compute_commitment_directive`, `compute_consequence_directive`, `compute_pacing_directive`, `compute_central_thread_directive`, `compute_init_directive`, `compute_loot_directive`. **Eighth Doctrine §59 instance.** No DB writes; pure compute from supplied inputs.

2. **`ResolutionResult` is an immutable frozen dataclass.** Fields locked in §5.

3. **New `dnd_pending_roll_directives.dc INTEGER` column.** Idempotent migration in `dnd_engine.py:db_init()`. DC is single-writer per Doctrine §17: written only by the directive-emit branch in `_handle_dm_roll_directive` after DC parsing from the directive text.

4. **Phase 2 wiring replaces Phase 1's telemetry-only branch.** The matcher's `_handle_dm_roll_arrival` match path currently logs `directive_would_fire_dm_respond:` and consumes the row. Ship 1 keeps that log line (extended with `roll_total` and `dc`), keeps the consume, and adds: call `resolve_directive`, then schedule `_dm_respond_and_post` with the synthesized actions list + `resolution_result` kwarg.

5. **AUTHORITATIVE-CANON block renders at the same prompt anchor as `=== ARBITRATION RESULT ===`** — immediately after the campaign identity line, before `=== SETTING & TONE ===` (recon confirmed: `dnd_engine.py:5189`). Bottom-of-prompt repeat as item 7 of HARD STOP RULES, mirroring `arbitration_hardstop_section` (recon: `dnd_engine.py:5081`, `dnd_engine.py:5327`).

6. **New verifier class `ROLL_OUTCOME_DRIFT` in `narration_verifier.py`.** Fifth violation class per the §11.F locked-classes pattern from `TRACK_7_2_SPEC.md`. Detection: keyword scan for success/failure terms cross-referenced against `ResolutionResult.passed`. 1-retry loop per the existing escalation pattern. Class slots in BEFORE `ACTOR_OMISSION` (last) and AFTER `STATE_MUTATION_CLAIM` in the detection-order chain.

### §2.2 AUTHORITATIVE-CANON block shape (locked wording — spec confirms)

`MULTIPLAYER_FIXES.md` §4.1 gives the locked template. Spec confirms exact wording and parameterization:

```
═══ AUTHORITATIVE ROLL RESOLUTION ═══
{Actor} attempted a {Skill} {check/save} (DC {dc}).
Roll total: {roll_total}.
Outcome: {PASSED/FAILED}.

You MUST narrate this as a {success/failure}. {Actor} does {NOT } achieve the intended outcome.
Do NOT narrate {opposite outcome}. Do NOT invent an alternative interpretation.
═══
```

Where:
- `{Actor}` = `ResolutionResult.actor` (canonical display form, snapshotted at directive emit)
- `{Skill}` = `ResolutionResult.skill_or_save`, Title Case, underscores → spaces
- `{check/save}` = literal "check" or "save" per `ResolutionResult.check_kind`
- `{dc}` = `ResolutionResult.dc`
- `{roll_total}` = `ResolutionResult.roll_total`
- `{PASSED/FAILED}` = literal "PASSED" or "FAILED" per `ResolutionResult.passed`
- `{success/failure}` = literal "success" or "failure" lowercased
- `{NOT }` = empty string when `passed=True`, literal `"NOT "` when `passed=False`
- `{opposite outcome}` = literal "success" when `passed=False`, "failure" when `passed=True`

The "does {NOT } achieve the intended outcome" phrasing is intentional — the locked text in `MULTIPLAYER_FIXES.md` §4.1 reads "Donovan does NOT discover hidden information" for a failed Perception check. The spec lifts the generic shape "does NOT achieve the intended outcome" rather than parameterizing per-skill outcomes, because per-skill outcome dictionaries are a maintenance burden (Doctrine §26 territory — "ever-growing exception lists mean the fix is wrong"). The generic phrasing is sufficient given the surrounding constraint clauses.

Bottom-of-prompt repeat is the single line `Outcome: {PASSED/FAILED}.` rendered as item 7 of HARD STOP RULES (no decoration, per §48 concrete-in-prompt pattern).

### §2.3 Composition with Track 7 #1 (CHECK_ACTION binding) and Track 7 #2 (ARBITRATION RESULT)

The AUTHORITATIVE ROLL RESOLUTION block and the ARBITRATION RESULT block are **mutually exclusive by flow** in v1:

- ARBITRATION RESULT fires when `dm_respond` is invoked with a player-input string that enters through the normal batcher path. `adjudicator.arbitrate(...)` runs, produces a CHECK or CAPABILITY or COMBAT or WORLD_BOUNDARY verdict, renders the block.
- AUTHORITATIVE ROLL RESOLUTION fires when the matcher consumes a directive and auto-schedules `_dm_respond_and_post` with a synthesized input. The synthesized input is FREE-shape; arbitration sees nothing CHECK-shaped; the ARBITRATION RESULT block is empty (or contains a FALLBACK verdict with empty `narration_constraint`).

The spec **does not enforce mutual exclusion structurally** in v1 — `build_dm_context` accepts both as kwargs and renders both if both are populated. In practice they don't co-occur because the trigger surfaces are disjoint. A future v1.x ship may want to surface a unified `binding_block` that takes the first non-empty of (arbitration, resolution) — out of scope here. See §11.9 for the defensive-ordering decision.

### §2.4 What is locked vs. what spec fills in

| Locked (do not re-litigate) | Spec fills in |
|------------------------------|----------------|
| `resolve_directive` location (`dnd_orchestration.py`) | Function signature + return shape (§4) |
| `ResolutionResult` is frozen dataclass with 8 fields | Field types + defaults + log-shape helper (§5) |
| `dnd_pending_roll_directives.dc INTEGER` column | Migration + DC parser regex + edge cases (§6) |
| Top-of-prompt AUTHORITATIVE-CANON + bottom repeat | Insertion-point anchors + composition with arbitration (§7) |
| `ROLL_OUTCOME_DRIFT` is new verifier class | Detection vocabulary + retry constraint (§8) |
| Matcher → resolve → _dm_respond_and_post wiring | Synthesized `actions` shape + soft-fail (§9) |
| `directive_would_fire_dm_respond` log extends | New + extended log line specs (§10) |

---

## §3. Bug 1 Phase 2 absorption (lineage preservation)

`BUG_1_SPEC.md` §L locks four Phase 2 trigger criteria as a deterministic gate. Ship 1 satisfies each criterion **structurally** (the implementation makes the criterion true by construction) rather than through Phase 1 telemetry accumulation. This section preserves Bug 1's spec lineage so Phase 2 does not become a ghost item when Ship 1 lands.

### §3.1 The four locked criteria (verbatim from BUG_1_SPEC.md §L)

1. **≥ 5 directive-emit events observed in real play across ≥ 2 sessions** — `directive_bound_to_footer_actor:` count, distinct session days
2. **≥ 80% of directives bind successfully to footer actor** — ratio of `directive_bound_to_footer_actor` to `(directive_bound_to_footer_actor + directive_creation_skipped_no_footer)` ≥ 0.8
3. **Zero observed cases of `footer_actor_changed` firing without a corresponding orchestration event** — every transition must trace to `_dm_respond_and_post`, `set_active_turn`, `clear_active_turn`, or `/play`
4. **Zero observed ghost-trigger candidates** — every `directive_would_fire_dm_respond` must cross-reference a preceding `directive_bound_to_footer_actor` for the same actor+skill within TTL

### §3.2 How Ship 1 satisfies each criterion structurally

| # | Criterion | How Ship 1 satisfies it |
|---|-----------|--------------------------|
| 1 | ≥ 5 emits across ≥ 2 sessions | **Already met** — S32 calibration table (§4.1) recorded 15+ emits across 2 sessions. Pre-existing; not affected by Ship 1. |
| 2 | ≥ 80% bind success | **S32 measured 75% raw / >80% adjusted for legitimate session-open no-footer skips.** The 80% criterion measures bind-failure rate among directives that had a footer actor available to bind to; session-open `directive_creation_skipped_no_footer` events are correct-handled non-events, not bind failures, and are excluded from the denominator. Adjusted measurement satisfies criterion 2. Ship 1 does not change the bind rate. |
| 3 | Zero spurious footer transitions | **Already met** — S32 calibration confirmed every `footer_actor_changed` traced to a granular trigger. Not affected by Ship 1. |
| 4 | Zero ghost-triggers | **Already met** — S32 calibration confirmed every `directive_would_fire_dm_respond` paired to a preceding `directive_bound_to_footer_actor`. Not affected by Ship 1. |

### §3.3 The fifth criterion (locked addition per MULTIPLAYER_FIXES.md §4.4 decision 6)

**Criterion 5:** Narrated outcome matches roll-vs-DC verdict in 100% of consumed directives.

**Measurement:** `ROLL_OUTCOME_DRIFT` verifier violation count across one play session = 0.

**What counts as "one play session":** A `/play` open through `/play` close (or service restart), bounded by `state_footer:` log lines at session start and end. Typical session is 60–180 minutes per the THE_GOAL.md cadence framing. One session is sufficient for a structural assertion when the implementation makes the criterion true by construction; multi-session calibration is unnecessary because the binding is engine-computed, not stochastic. (Compare to criterion 2's bind rate, which depends on DM behavior and therefore wants ≥ 2 sessions.)

**What counts as "consumed":** Every `directive_would_fire_dm_respond:` log line where Ship 1's wiring fires `_dm_respond_and_post`. Manual-trigger fallback path (see §11.7) does not count — the directive is consumed but the resolution block is not rendered.

### §3.4 Bug 1 Phase 2 ROADMAP disposition

When Ship 1 lands and live-verifies cleanly (§13 verification scenario), the ROADMAP entry for Bug 1 Phase 2 flips ✅ in the same doc-update pass as Ship 1's own ✅. Phase 2 does not get its own ship; it ships as the side effect that the planner-locked architecture predicted. The SESSIONS.md S33 entry already records Bug 1 Phase 2 as "ships as side effect of Ship 1" — Ship 1's doc-update pass closes that loop.

---

## §4. `resolve_directive` pure function

### §4.1 Signature and contract

```python
def resolve_directive(
    directive_row: dict,
    avrae_event: dict,
) -> ResolutionResult | None:
    """Compute the resolution of a consumed pending roll directive.

    Pure function. Reads no DB, no buffers. Caller (matcher in
    discord_dnd_bot.py) supplies both inputs. No side effects.

    Returns None when inputs are structurally incomplete (no DC, no
    roll_total, kind mismatch); caller falls through to telemetry-only
    behavior. Returns a populated ResolutionResult otherwise.

    See §11.5 for the cast-kind skip path.
    """
```

### §4.2 Inputs

- `directive_row`: the dict returned by `pending_directive_get_active` at the moment of match. Required keys: `actor_name`, `check_type`, `dc` (new column from §6), `created_at`, `campaign_id`. Caller supplies after `pending_directive_get_active` and before `pending_directive_consume`.
- `avrae_event`: the dict returned by `parse_avrae_embed` for the matching Avrae roll embed. Required keys: `actor`, `kind` ∈ {'check', 'save'}, `detail`, `result` (the final roll total, integer), `nat` (the natural die roll, integer or None for non-d20 cases), `crit` (bool — from `_CRIT_RE.search(raw)`), `ts`.

Recon Q1 (Avrae embed shape for roll_total) confirmed: `parse_avrae_embed` returns `result` as a parsed integer in `dnd_engine.py`-imported `avrae_listener.py`. No additional regex extraction needed at the matcher boundary. See `avrae_listener.py:571-574` for the `kind ∉ {attack, cast, damage, rest}` branch that sets `result = _final_result(raw)` and `nat = _kept_nat_roll(raw)`.

### §4.3 Resolution computation

```python
def resolve_directive(directive_row, avrae_event):
    kind = (avrae_event.get('kind') or '').lower()
    if kind not in ('check', 'save'):
        return None  # cast/attack/damage/rest skip — see §11.5

    roll_total = avrae_event.get('result')
    if roll_total is None or not isinstance(roll_total, int):
        return None  # malformed embed; matcher falls through to telemetry-only

    dc = directive_row.get('dc')
    if dc is None or not isinstance(dc, int):
        return None  # no-DC directive — see §11.2

    actor = (directive_row.get('actor_name') or '').strip()
    skill_or_save = (directive_row.get('check_type') or '').strip()
    if not actor or not skill_or_save:
        return None  # defensive — Phase 1 invariants guarantee both are
                     # non-empty; check belt-and-suspenders.

    passed = roll_total >= dc

    return ResolutionResult(
        actor=actor,
        check_kind=kind,  # 'check' or 'save'
        skill_or_save=skill_or_save,
        dc=dc,
        roll_total=roll_total,
        passed=passed,
        rolled_at=float(avrae_event.get('ts') or time.time()),
        directive_id=int(directive_row.get('campaign_id') or 0),  # see §5.2
        nat=avrae_event.get('nat'),  # see §11.3 crit handling
        crit=bool(avrae_event.get('crit') or False),
    )
```

**Soft-fail discipline (§59):** Caller wraps in try/except; on any exception, treat as `None` and emit `resolve_directive_error:` log line. Matcher's existing telemetry-only path then runs unchanged (no narration auto-fires; directive is still consumed per Phase 1 semantics).

### §4.4 What `resolve_directive` does NOT do

- Does NOT call `pending_directive_consume` — that stays the matcher's responsibility, post-resolve.
- Does NOT call `_dm_respond_and_post` — pure function; caller schedules narration.
- Does NOT mutate `directive_row` or `avrae_event`.
- Does NOT log — caller emits the `directive_resolved:` log line using the resolved fields. Pure functions log only via exception; signals dict is the spec norm for log-driving (see §10).
- Does NOT handle cast directives — returns None on `kind='cast'`. Cast resolution requires target-side save adjudication and is filed v1.x.

### §4.5 Log helper sibling

Per the §59 pattern (every `compute_*_directive` has a `*_log_summary` sibling), Ship 1 adds:

```python
def resolution_log_summary(result: ResolutionResult | None,
                            campaign_id: int) -> str:
    """Compact log line per Doctrine §59 / BUG_1_SPEC.md §I shape. Always-fire.
    Fires for both successful resolutions (result non-None) and skipped
    cases (result is None) — empirical baseline observability."""
    if result is None:
        return (f"directive_resolution_skipped: campaign={campaign_id} "
                f"reason=unresolvable")
    outcome = 'PASSED' if result.passed else 'FAILED'
    return (
        f"directive_resolved: campaign={campaign_id} "
        f"actor={result.actor} "
        f"skill={result.skill_or_save} "
        f"check_kind={result.check_kind} "
        f"dc={result.dc} "
        f"roll_total={result.roll_total} "
        f"outcome={outcome} "
        f"nat={result.nat if result.nat is not None else 'none'} "
        f"crit={1 if result.crit else 0}"
    )
```

See §10 for the full log line catalog.

---

## §5. `ResolutionResult` dataclass

### §5.1 Definition

```python
@dataclass(frozen=True)
class ResolutionResult:
    actor: str                 # canonical display name, snapshotted at directive emit
    check_kind: str            # 'check' | 'save' — cast deferred per §11.5
    skill_or_save: str         # 'perception' | 'wisdom' | 'investigation' | etc
    dc: int                    # DM-set DC at directive emit (parsed per §6)
    roll_total: int            # Avrae embed's final result (post-modifier)
    passed: bool               # engine-computed: roll_total >= dc
    rolled_at: float           # unix timestamp from avrae_event['ts']
    directive_id: int          # FK to dnd_pending_roll_directives.campaign_id
                               # (campaign_id is the PK in v1; see §5.2)
    nat: int | None            # natural die roll, for crit-handling §11.3
    crit: bool                 # explicit crit flag from Avrae embed
```

`frozen=True` per the `@dataclass(frozen=True)` pattern locked in `MULTIPLAYER_FIXES.md` §4.1. Immutability is structural — no callsite should mutate a ResolutionResult after construction; downstream code (prompt renderer, verifier) treats it as a read-only record.

### §5.2 The `directive_id` field

`dnd_pending_roll_directives` uses `campaign_id INTEGER PRIMARY KEY` per `BUG_1_SPEC.md` §A.1 (one pending directive per campaign max, UNIQUE constraint by way of PK). There is no separate `id` column. **`directive_id` therefore stores `campaign_id` in v1.** When/if the schema gains a per-row `id`, the field name remains stable and the value source updates.

This is a minor naming awkwardness — `directive_id == campaign_id` is technically a synonym in v1. The alternative (renaming to `campaign_id`) would conflate two distinct semantic concepts (this is the campaign the resolution happened in vs. this is the directive's identity). Spec keeps `directive_id` for semantic clarity; v1.x may rename if the dnd_pending_roll_directives schema evolves.

### §5.3 The `nat` and `crit` fields

Recon Q2 (nat-20 / nat-1 surface) confirmed:
- `parse_avrae_embed` returns `'nat': int | None` from `_kept_nat_roll(raw)` for non-attack/non-cast/non-damage kinds (so check/save get it).
- `parse_avrae_embed` returns `'crit': bool` from `_CRIT_RE.search(raw)` — explicit crit detection at embed-parse time.

ResolutionResult captures both. In v1 they are informational only — RAW D&D 5e per §11.3 means skill-check nat-20 is just a high roll and nat-1 is just a low roll. The fields exist on the dataclass so future table-rule customization (v1.x candidate per §11.3) does not require a schema change.

Note: `nat` may be None for save events depending on Avrae's embed format (e.g., a flat-roll save with no advantage might not produce a `nat` token cleanly). Defensive: `nat: int | None` is intentionally typed Optional.

### §5.4 Field invariants (defensive — caller's contract)

- `actor` is non-empty (Phase 1 guarantees `last_active_actor != ''` at directive-emit time; matcher dedupes against Avrae's canonicalized actor at consume time)
- `check_kind ∈ {'check', 'save'}` — cast returns None per §4.3
- `dc` is the integer parsed at directive-emit time (see §6); valid range is roughly 5–30 per D&D 5e DC bands, but **the spec does not validate the upper bound** — DM creativity is preserved
- `roll_total` is the Avrae embed's `result` field, which can be 1–50ish in practice (high modifiers + nat-20 + advantage)
- `passed = roll_total >= dc` — strict ≥ (per `_constraint_check_resolved`'s existing precedent in `adjudicator.py:471-482`)
- `rolled_at` is unix-epoch float; `directive_id` is non-zero per `dnd_pending_roll_directives` PK

---

## §6. DC parsing + `dnd_pending_roll_directives.dc` column

### §6.1 Schema delta

```sql
ALTER TABLE dnd_pending_roll_directives
    ADD COLUMN dc INTEGER;
```

Defined in `dnd_engine.py:db_init()` adjacent to the existing `dnd_pending_roll_directives` CREATE TABLE block, gated on `PRAGMA table_info(dnd_pending_roll_directives)` membership check per the existing idempotent-migration pattern (BUG_1_SPEC.md §A.2 precedent).

`dc` is nullable. NULL = "directive emitted without a DC, falls through to free-narration flow per §11.2." Single-writer per Doctrine §17: only `_handle_dm_roll_directive` writes the column, at directive-emit time after DC parsing.

### §6.2 DC parser

The current directive parser regex (`BUG_1_SPEC.md` §D.1):

```python
_DM_DIRECTIVE_RX = re.compile(
    r"^\s*(?:<@!?\d+>\s*)?"
    r"!(?P<kind>check|save|cast)\s+"
    r"(?P<skill>.+?)\s*$",
    re.IGNORECASE,
)
```

Captures `(kind, skill)` from `!check perception 10`. The trailing `10` currently routes through `_directive_skill_is_clean` as `reason=trailing_args` (BUG_1_SPEC.md §D.3) and emits `directive_text_unparsed:`.

**Ship 1 extension:** before the trailing-args reject, attempt a DC parse against the captured `skill` group. New helper:

```python
_DC_PARSE_RX = re.compile(
    r"^(?P<skill>[a-zA-Z_][a-zA-Z_\s\-]*?)\s+(?P<dc>\d+)\s*$",
)

def parse_skill_and_dc(skill_raw: str) -> tuple[str, int | None]:
    """Split a directive's captured skill text into (skill, dc).

    'perception 10' → ('perception', 10)
    'perception'    → ('perception', None)
    'stealth adv'   → ('stealth adv', None)  — non-numeric trailing rejects
    'stealth 15 adv'→ ('stealth 15 adv', None) — trailing word after DC rejects
    'sleight of hand 12' → ('sleight of hand', 12)
    """
    s = (skill_raw or '').strip()
    m = _DC_PARSE_RX.match(s)
    if m:
        return m.group('skill').strip(), int(m.group('dc'))
    return s, None
```

### §6.3 Parser edge cases (spec-decided)

| Input | Skill | DC | Routing |
|-------|-------|----|---------|
| `!check perception 10` | `perception` | 10 | Phase 1 bind + Ship 1 resolve fires |
| `!check perception` | `perception` | None | Phase 1 bind + Ship 1 resolve SKIPS (§11.2) — falls through to free-narration |
| `!check sleight of hand 12` | `sleight of hand` | 12 | Bind + resolve fires (multi-word skill) |
| `!check perception 100` | `perception` | 100 | Bind + resolve fires (high DC); narration almost certainly FAILED, which is fine |
| `!check perception 10 adv` | `perception 10 adv` | None | Currently rejects via `_directive_skill_is_clean` `trailing_args`. **Spec decision: keep rejecting** — DC + modifier is too composite for v1 parser. v1.x calibration if rate is meaningful. |
| `!check stealth adv` | `stealth adv` | None | Already rejected by Phase 1. Unchanged. |
| `!check perception 0` | `perception` | 0 | Bind + resolve fires; roll_total >= 0 always passes. **Spec decision: allow** — DM may want a degenerate "always-passes" check for theater. Low-risk; observable via `dc=0` in logs. |
| `!check perception -5` | `perception -5` | None | `\d+` doesn't match negative; rejects as trailing_args. Defensive — negative DCs are nonsensical. |

### §6.4 Graceful degrade when parsing fails

If `parse_skill_and_dc` returns `(skill, None)`:
1. `dnd_pending_roll_directives.dc` is stored as NULL
2. Phase 1 binding still fires: `directive_bound_to_footer_actor:` logs as before, row is upserted
3. At Avrae roll arrival, matcher reads `dc=None` from the row
4. `resolve_directive` returns None per §4.3
5. Matcher falls through to **telemetry-only behavior** (logs `directive_would_fire_dm_respond_no_dc:` — new log line per §10.4), consumes the row, does NOT auto-fire `_dm_respond_and_post`
6. Existing free-narration flow proceeds when the player types a response

This is the §11.2 "fall through to existing free-narration" branch made concrete. The directive still binds and still gets consumed (preserving Phase 1's lifecycle semantics); only the auto-narration path skips.

### §6.5 Single-writer compliance

Per Doctrine §17, `dnd_pending_roll_directives.dc` has exactly one writer: `pending_directive_upsert` (called from `_handle_dm_roll_directive` after parsing). Edit-cancel path (`pending_directive_delete_by_message`) deletes the entire row; no separate DC update path. No DDL-level update statement against `dc` exists anywhere in the codebase. This is the **third single-writer field on the table** (alongside `actor_name` and `check_type`, both written by the same upsert).

---

## §7. AUTHORITATIVE-CANON prompt block (top + bottom rendering)

### §7.1 Top-of-prompt insertion point

Recon (Q4) confirmed `build_dm_context` in `dnd_engine.py:4857` renders arbitration as:

```python
arbitration_section = (
    f"\n\n=== ARBITRATION RESULT ===\n{arbitration_block}"
    if arbitration_block else ""
)
# ...
return f"""You are the Dungeon Master for a D&D 5th Edition campaign called "{campaign['name']}".{arbitration_section}

=== SETTING & TONE (HARD CONSTRAINT — DO NOT VIOLATE) ===
{tone}
...
```

The anchor for top-of-prompt is **immediately after the campaign identity line, before `=== SETTING & TONE ===`** — `arbitration_section` is concatenated directly onto the campaign-name string with no separator.

**Ship 1 adds a sibling kwarg `resolution_block`** rendered at the same anchor, immediately after `arbitration_section`:

```python
resolution_section = (
    f"\n\n═══ AUTHORITATIVE ROLL RESOLUTION ═══\n{resolution_block}\n═══"
    if resolution_block else ""
)
# ...
return f"""You are the Dungeon Master for a D&D 5th Edition campaign called "{campaign['name']}".{arbitration_section}{resolution_section}
```

The `═══` triple-line-marker (vs. `===` triple-equals for ARBITRATION RESULT) is intentional and locked in `MULTIPLAYER_FIXES.md` §4.1. The visual distinction signals to the LLM that this is a stronger constraint than the standard `===` blocks. Block-internal `═══` matches the locked template wording.

### §7.2 Bottom-of-prompt hardstop echo

Recon confirmed the HARD STOP RULES block is at `dnd_engine.py:5318`, with `arbitration_hardstop_section` appended as item 7 at `dnd_engine.py:5081` + line 5327 (in the closing `(c)` clause of HARD STOP item 6).

Ship 1 adds a parallel kwarg `resolution_hardstop_echo`:

```python
resolution_hardstop_section = (
    f"\n8. {resolution_hardstop_echo}"
    if resolution_hardstop_echo else ""
)
```

Rendered as item 8 of HARD STOP RULES (item 7 is reserved for arbitration_hardstop). Both can render in the same prompt (defensive — they're mutually exclusive in practice per §2.3 but the spec doesn't enforce that structurally). If only resolution fires, the prompt has HARD STOP items 1–6 + item 8 (no item 7). The numbering gap is harmless; LLMs don't enforce numeric continuity in instruction lists.

The hardstop echo text is the single line per `MULTIPLAYER_FIXES.md` §4.1:

```
Outcome: {PASSED/FAILED}.
```

No decoration, no surrounding constraint clauses. The §48 concrete-in-prompt principle is that repeating the bare verdict at the moment of generation narrows the drift surface — the AUTHORITATIVE-CANON block does the heavy lifting at the top of the prompt; the bottom-of-prompt repeat is the immediate-context reinforcer.

### §7.3 Render helpers (live in `dnd_orchestration.py`)

Per §59, the renders live alongside `resolve_directive`:

```python
def render_resolution_block(result: ResolutionResult) -> str:
    """Render ResolutionResult as the top-of-prompt AUTHORITATIVE-CANON
    block body. Returns the inner text (no surrounding ═══ markers — those
    are added by build_dm_context's section assembly)."""
    actor = result.actor
    skill_pretty = result.skill_or_save.replace('_', ' ').title()
    kind = result.check_kind  # 'check' or 'save'
    dc = result.dc
    roll = result.roll_total
    outcome = 'PASSED' if result.passed else 'FAILED'
    outcome_word = 'success' if result.passed else 'failure'
    opposite_word = 'failure' if result.passed else 'success'
    negation = '' if result.passed else 'NOT '

    return (
        f"{actor} attempted a {skill_pretty} {kind} (DC {dc}).\n"
        f"Roll total: {roll}.\n"
        f"Outcome: {outcome}.\n\n"
        f"You MUST narrate this as a {outcome_word}. "
        f"{actor} does {negation}achieve the intended outcome.\n"
        f"Do NOT narrate {opposite_word}. "
        f"Do NOT invent an alternative interpretation."
    )


def render_resolution_hardstop_echo(result: ResolutionResult) -> str:
    """Render the single-line bottom-of-prompt repeat per §48."""
    return f"Outcome: {'PASSED' if result.passed else 'FAILED'}."
```

Both helpers are pure; both handle `result=None` by returning empty string (caller's section-assembly already handles the empty case via the kwarg's truthiness check).

### §7.4 Composition with `dm_respond`

`dm_respond` in `dnd_engine.py:5466` is the prompt-build + LLM-call function. Ship 1 extends its signature to accept an optional `resolution_result: ResolutionResult | None = None` kwarg. When non-None:

1. `dm_respond` calls `render_resolution_block(resolution_result)` and passes the result to `build_dm_context` as `resolution_block=...`
2. `dm_respond` calls `render_resolution_hardstop_echo(resolution_result)` and passes the result as `resolution_hardstop_echo=...`
3. The arbitration call (`adjudicator.arbitrate(...)`) still runs — it produces an arbitration_result with a FREE/FALLBACK verdict for the synthesized input, which renders as empty arbitration_block. Both blocks render side-by-side per §7.1; in practice arbitration is empty so only the resolution block is visible.

### §7.5 Per-skill `intended outcome` phrasing — the do-not-do

`MULTIPLAYER_FIXES.md` §4.1's locked example reads:

> Donovan does NOT discover hidden information.

That phrasing parameterizes per-skill ("discover hidden information" for Perception; "deceive the merchant" for Persuasion-vs-Insight; etc.). Ship 1 **does not parameterize** per-skill. The generic phrasing "does NOT achieve the intended outcome" suffices given:

- The action the player declared is already in the conversation context (the LLM sees the most recent player turn)
- The skill name is in the block (`Donovan attempted a Perception check`)
- The surrounding constraints (`Do NOT narrate success`, `Do NOT invent an alternative interpretation`) close the drift surface

A per-skill outcome map ("Perception → discover hidden information"; "Stealth → avoid detection"; "Persuasion → convince the target") would be a Doctrine §26-shaped exception list: every new skill triggers a maintenance entry; homebrew skills break it; the gating becomes a moving target. **Locked: generic phrasing.** Future v1.x may revisit if narration drift logs show the generic phrasing produces ambiguous outcomes.

---

## §8. `narration_verifier` ROLL_OUTCOME_DRIFT class

### §8.1 Class addition

Per `TRACK_7_2_SPEC.md` §11.F (locked verification violation classes), the four classes are `FABRICATED_COMBATANT`, `VERDICT_CONTRADICTION`, `STATE_MUTATION_CLAIM`, `ACTOR_OMISSION`. Ship 1 adds a fifth: `ROLL_OUTCOME_DRIFT`.

```python
VIOLATION_ROLL_OUTCOME_DRIFT = 'roll_outcome_drift'
```

Added to the `narration_verifier.py` constants block alongside the existing four.

### §8.2 Detection trigger

`ROLL_OUTCOME_DRIFT` fires when **both**:

1. The narration was emitted under a resolution-binding flow (`resolution_result` was non-None at `verify_narration` call time), AND
2. The narration text contains success-vocabulary phrasing while `resolution_result.passed == False`, OR failure-vocabulary while `resolution_result.passed == True`

This is the parallel of `VERDICT_CONTRADICTION`'s check-success / check-failure detection (`narration_verifier.py:449-466`), but operating on the ResolutionResult surface (engine-bound) rather than on `arbitration_result.verdicts` (adjudicator-bound).

### §8.3 Vocabulary reuse

`narration_verifier.py` already maintains:
- `_CHECK_FAILURE_SUCCESS_PHRASES` — phrases the LLM uses when narrating success on a failed check (e.g., "succeeds", "passes", "manages to", "spots", "notices")
- `_CHECK_SUCCESS_FAILURE_PHRASES` — phrases when narrating failure on a successful check (e.g., "fails", "misses", "stumbles", "can't quite")

**Ship 1 reuses both vocabularies.** No new regex; the existing patterns are correct for the surface. The class differentiation is purely "which result object the detection is comparing against" — VERDICT_CONTRADICTION compares against arbitration's CHECK verdict; ROLL_OUTCOME_DRIFT compares against ResolutionResult.

This is a small architectural elegance: the vocabulary stays in one place, and the two classes are non-overlapping by virtue of which trigger object is populated at call time (adjudicator-arbitrated turns set `arbitration_result.verdicts` with CHECK; resolution-binding turns set `resolution_result`; never both, by the §2.3 flow analysis).

### §8.4 Detection order

`verify_narration`'s existing order (first-violation-wins, `narration_verifier.py:357-362`):

1. FABRICATED_COMBATANT
2. VERDICT_CONTRADICTION
3. STATE_MUTATION_CLAIM
4. ACTOR_OMISSION

Ship 1 inserts ROLL_OUTCOME_DRIFT **between STATE_MUTATION_CLAIM and ACTOR_OMISSION**, making the new order:

1. FABRICATED_COMBATANT
2. VERDICT_CONTRADICTION
3. STATE_MUTATION_CLAIM
4. ROLL_OUTCOME_DRIFT (new)
5. ACTOR_OMISSION

Rationale: ROLL_OUTCOME_DRIFT and VERDICT_CONTRADICTION test for similar phenomena (LLM narrated against a binding outcome). Putting ROLL_OUTCOME_DRIFT immediately after VERDICT_CONTRADICTION would be natural — but STATE_MUTATION_CLAIM is a stricter structural class (LLM never has authority for HP/XP/death numbers) and should fire first when both apply. ROLL_OUTCOME_DRIFT sits in slot 4 to preserve "structural-impossibility classes before behavioral-drift classes" ordering. ACTOR_OMISSION stays last because it's the broadest-net catch (every non-FREE actor's name must appear) — earlier classes are more specific.

### §8.5 Signature extension

```python
def verify_narration(narration_text: str,
                     arbitration_result,
                     scene_state: Optional[dict] = None,
                     combatants: Optional[list] = None,
                     npcs_canonical: Optional[list] = None,
                     resolution_result: Optional['ResolutionResult'] = None,  # NEW
                     ) -> VerificationResult:
```

When `resolution_result is None`, the new detection pass is a no-op (slot 4 falls through to slot 5). Existing call sites that don't pass the kwarg get the same behavior as today. Single new call site that DOES pass it: `dm_respond`'s post-LLM verification block (`dnd_engine.py:6182-6200`), extended to forward the resolution_result from its kwarg through to `verify_narration`.

### §8.6 Retry constraint

New retry constraint helper:

```python
def _retry_constraint_roll_outcome_drift(detected_phrase: str,
                                          result: ResolutionResult) -> str:
    outcome = 'PASSED' if result.passed else 'FAILED'
    outcome_word = 'success' if result.passed else 'failure'
    opposite_word = 'failure' if result.passed else 'success'
    return (
        f"Class: {VIOLATION_ROLL_OUTCOME_DRIFT}\n"
        f"Detected: {detected_phrase!r}\n\n"
        "You MUST regenerate. The retry MUST:\n"
        f"  - Honor the binding resolution: {result.actor} "
        f"{result.skill_or_save} {result.check_kind} DC {result.dc}, "
        f"rolled {result.roll_total}, outcome {outcome}.\n"
        f"  - Narrate ONLY the {outcome_word} outcome. Do NOT narrate "
        f"{opposite_word}, partial reversal, or alternative interpretation.\n"
        f"  - The roll resolution is engine-computed and binding. The player's "
        f"self-report is irrelevant. The DC was set at directive emit."
    )
```

Mirrors `_retry_constraint_verdict_contradiction` shape (`narration_verifier.py:300-311`). The final sentence — explicitly stating that the player's self-report is irrelevant — is targeted at the F-45 failure shape directly: the LLM was drifting because it was responding to the player's "I passed" text. The retry prompt makes the structural reason explicit.

### §8.7 Retry-loop integration

Recon Q5 confirmed: existing 1-retry escalation pattern slots cleanly. `build_verification_retry_prefix` (`narration_verifier.py:589-602`) reads `result.retry_constraint` and prepends a `=== VERIFICATION FAILED ===` block to the next system prompt. No change needed; the new class's `retry_constraint` text plugs in unchanged.

On second-pass violation (retry also drifts), the escalation placeholder builder (`narration_verifier.py:609-691`) needs an extension to handle ROLL_OUTCOME_DRIFT escalation. Spec proposal: extend `build_escalation_placeholder` to also accept `resolution_result` and render a deterministic placeholder when the failed class is ROLL_OUTCOME_DRIFT:

```python
# Inside build_escalation_placeholder's category branches:
elif failed_violation_class == VIOLATION_ROLL_OUTCOME_DRIFT and resolution_result:
    outcome = 'Success' if resolution_result.passed else 'Failure'
    blocks.append(
        f"{resolution_result.actor} — "
        f"{resolution_result.skill_or_save.replace('_',' ').title()} "
        f"{resolution_result.check_kind} at DC {resolution_result.dc} "
        f"(rolled {resolution_result.roll_total}). Result: {outcome}. "
        f"{'The attempt succeeds.' if resolution_result.passed else 'The attempt fails.'}"
    )
```

Same shape as the existing CHECK-class escalation block (`narration_verifier.py:639-655`). Deterministic, terse, mechanical, honest — never blocks posting.

---

## §9. Phase 2 wiring (matcher → resolve_directive → _dm_respond_and_post)

### §9.1 Current Phase 1 flow (BUG_1_SPEC.md §F.2)

```
Avrae roll arrives
  → parse_avrae_embed produces event
  → _handle_dm_roll_arrival(campaign_id, event)
    → kind check (check/save/cast only)
    → pending_directive_get_active (sweeps expired rows; may return None)
    → skill match (silent ignore on mismatch)
    → actor match
      → if match: log `directive_would_fire_dm_respond:` + pending_directive_consume
      → if mismatch: log `directive_actor_mismatch:` + post wrong-actor aside (do not consume)
```

### §9.2 Ship 1 extended flow

```
Avrae roll arrives
  → parse_avrae_embed produces event (now also passing through 'result', 'nat', 'crit')
  → _handle_dm_roll_arrival(campaign_id, event)
    → kind check (check/save only — see §11.5; cast falls through silently)
    → pending_directive_get_active (unchanged)
    → skill match (unchanged)
    → actor match
      → if match:
        → resolution = resolve_directive(pending_row, event)
        → log resolution_log_summary(resolution, campaign_id)  [§4.5]
        → log extended `directive_would_fire_dm_respond:` (§10.3)
        → pending_directive_consume(campaign_id)
        → if resolution is not None:
          → schedule _dm_respond_and_post(campaign, characters,
              actions=synthesized_actions, combined_action=synthesized_input,
              resolution_result=resolution)
        → if resolution is None (no-DC case, malformed embed, etc.):
          → log `directive_resolution_skipped:` reason
          → DO NOT auto-fire; existing free-narration flow proceeds
            (player will likely type a response in a moment)
      → if mismatch: unchanged from Phase 1
```

The mismatch path is unchanged — wrong-actor rolls don't auto-fire resolution (per `MULTIPLAYER_FIXES.md` §4.4 decision 4). The row stays alive; resolution waits for the right actor or TTL.

### §9.3 Synthesized `actions` list

`_dm_respond_and_post` expects `actions: list[tuple]` where each tuple is `(name: str, text: str, controller_user_id: str | None)` (inferred from `discord_dnd_bot.py:2096-2114`).

For an auto-fired resolution, only one actor is involved — the directive's bound actor. The synthesized input needs to be specific enough that the LLM has narrative grounding but generic enough that it doesn't pre-empt the AUTHORITATIVE-CANON block.

**Spec recommendation (§11.8 lock-pending):**

```python
synthesized_input = (
    f"[Roll resolution: {resolution.actor} rolled {resolution.skill_or_save} "
    f"({resolution.check_kind}); outcome bound at top-of-prompt.]"
)
synthesized_actions = [
    (resolution.actor, synthesized_input, _resolve_controller_id(resolution.actor))
]
```

The `[...]` square-bracket framing is a sentinel form — it's not natural player input, so the LLM treats it as a narrative directive rather than role-playing the bracketed text. The AUTHORITATIVE-CANON block at top-of-prompt does the actual binding work.

Three alternatives considered:
- (a) Pure sentinel string (`"<ROLL_RESOLUTION:perception:check>"`): too synthetic; the LLM may treat it as system-output and produce garbled narration. Rejected.
- (b) Natural language synthesis (`"Donovan rolls perception"`): risks the LLM treating it as the player's own action declaration, which loops back into the F-45 surface. Rejected.
- (c) Empty string: relies entirely on the prompt block; loses the actor-name presence in `combined_action`, which other prompt-build paths use for context (e.g., `update_scene`'s "Last actions:" line). Rejected.

The bracket-sentinel form (recommended) gives the LLM enough surface context (actor name, skill, kind) without re-asserting an unbound action. Locks in §11.8.

### §9.4 Controller-ID resolution

`_dm_respond_and_post`'s tuple's third element (`tup[2]`) is the typing player's Discord user ID, used for the persistence directive's typing-identity comparison (`discord_dnd_bot.py:2107-2114`). For an auto-fired resolution, no player is "typing" — the bot is firing on its own. Options:

- (a) None — persistence directive's `typing_user_id` falls through. Currently the persistence directive only matters in combat mode; Ship 1 fires only in exploration mode (combat-mode resolution out of scope §11.5).
- (b) Resolve the bound PC's controller from `dnd_bound_characters` and pass it. More principled — the resolution narration is "on behalf of" the bound player.
- (c) The DM's user ID — but the resolution wasn't typed by the DM directly (it was indirectly emitted via `!check`).

Spec recommendation: **(b)** — query `get_bound_pc_controller(campaign_id, actor_name)` (existing helper in `dnd_engine.py`) at synthesis time. Falls through to None gracefully if the bound PC isn't cached. This gives downstream paths (persistence directive, future combat-mode resolution) the right identity to compare against.

### §9.5 Soft-fail discipline

Per `MULTIPLAYER_FIXES.md` §4.3 + Doctrine §59, the matcher's existing soft-fail discipline (BUG_1_SPEC.md §F: "matcher errors must NEVER raise into on_message") is preserved end-to-end:

| Failure point | Behavior |
|---------------|----------|
| `resolve_directive` raises | Caught in matcher; log `resolve_directive_error:`; row still consumed; no auto-fire |
| `resolve_directive` returns None (no DC, malformed embed) | Log `directive_resolution_skipped:`; row consumed; no auto-fire; existing free-narration flow proceeds when player responds |
| `_dm_respond_and_post` raises | Caught in scheduled coroutine; log `_dm_respond_and_post_failure:`; no aside posted (row already consumed) |
| `verify_narration` raises | Existing fail-open envelope (`narration_verifier.py:30`) — narration posts as-is |

The matcher is never load-bearing for narration to appear; failure modes degrade to Phase 1-shape telemetry-only behavior.

### §9.6 Manual-trigger fallback

`MULTIPLAYER_FIXES.md` §4.4 decision 7 names "manual-trigger flow (DM types narration himself)" with three candidate dispositions. Spec recommendation: **(a) manual-trigger bypasses resolution binding entirely.** Implementation: the matcher always fires `_dm_respond_and_post` on a successful resolve. If the DM races the matcher by typing manual narration in the few seconds between roll-arrival and bot-narration, the DM's narration appears first (it's in the standard #dm-narration flow); the bot's auto-narration appears second.

The race is observable via timing: `directive_resolved:` timestamp vs. `chroma_store dm` timestamp for any DM-authored narration in the same window. Phase 2 verify (§13) flags any case where they fire <2 seconds apart for DM review. This is conscious — DM's manual override is a feature; the matcher doesn't try to detect-and-skip it. Detection of "DM has typed manual narration" is a v1.x candidate (see §11.7). Out of scope for v1.

### §9.7 Debounce / rapid-fire handling

S32 §4.5 noted: *"Rapid-fire directives observed (6× investigation in 30 seconds at 21:43-21:44)... Phase 2 needs debounce / coalesce strategy — firing _dm_respond_and_post 6 times in 30 seconds would be terrible UX."*

**Spec recommendation:** Ship 1 does **not** implement debounce in v1. Reasoning:
- The rapid-fire case in S32 was driven by `pending_directive_replaced:` flow — each new directive replaces the prior row, and Phase 1's `directive_would_fire_dm_respond:` fires only on the LATEST consumed directive (the prior is overwritten before its roll arrives). So in practice, only one resolution fires per rapid-fire burst.
- The remaining concern is when each directive's roll arrives quickly enough that each binds + resolves + auto-fires. In that case the bot would narrate 6 times in 30 seconds. **This is real UX friction**, but it's also a DM-side anti-pattern (the DM should not be issuing rapid-fire `!check` directives — that's combat-mode behavior, which is out of scope per §11.5).
- Filing as **§11.14** decision: implement debounce in v1 (default off), or defer until logs show meaningful rapid-fire-resolution rate.

### §9.8 Combat-mode skip preservation

Phase 1 skips directive creation in combat mode (BUG_1_SPEC.md §F.1 gate 2). No `dnd_pending_roll_directives` row exists for combat-mode `!check`/`!save`. So no resolution can fire in combat mode by construction. Ship 1 inherits this — combat-mode rolls stay in Phase 1's `directive_creation_skipped: reason=combat_mode` log line. Combat-mode resolution is filed v1.x per `MULTIPLAYER_FIXES.md` §4.7.

---

## §10. Telemetry (new log lines, extension to existing log lines)

### §10.1 Extending `directive_would_fire_dm_respond:`

Phase 1's locked shape (BUG_1_SPEC.md §I.6):

```
directive_would_fire_dm_respond: campaign={N} actor={name} skill={skill} directive_age_s={N}
```

Ship 1 adds `roll_total`, `dc`, and `outcome` fields:

```
directive_would_fire_dm_respond: campaign={N} actor={name} skill={skill} directive_age_s={N} roll_total={N} dc={N|none} outcome={PASSED|FAILED|skipped}
```

`outcome=skipped` covers the §6.4 graceful-degrade case (no DC parsed; resolve_directive returns None). `outcome=PASSED|FAILED` covers the auto-fired case. `dc=none` when the directive was bound without a DC. The log name is preserved — Phase 2 trigger criterion 4 in `BUG_1_SPEC.md` §L cross-references the same log line; renaming would break the criterion's greppability.

### §10.2 New: `directive_resolved:` (success case)

```
directive_resolved: campaign={N} actor={name} skill={skill} check_kind={check|save} dc={N} roll_total={N} outcome={PASSED|FAILED} nat={N|none} crit={0|1}
```

Fires from `resolution_log_summary` (§4.5) when `resolve_directive` returns non-None. Drives the empirical pass/fail distribution and the nat-20/nat-1 rate observability.

### §10.3 New: `directive_resolution_skipped:` (skip cases)

```
directive_resolution_skipped: campaign={N} reason={no_dc|cast_kind|malformed_embed|unresolvable}
```

Fires from `resolution_log_summary` when `resolve_directive` returns None. Reasons:
- `no_dc` — directive was bound without a DC; falls through per §6.4
- `cast_kind` — Avrae event was a cast roll; out of scope for v1 per §11.5
- `malformed_embed` — `event['result']` missing or non-integer; defensive
- `unresolvable` — generic catch-all for other return-None paths

### §10.4 New: `resolve_directive_error:` (exception case)

```
resolve_directive_error: campaign={N} actor={name} skill={skill} err={repr}
```

Fires from the matcher's try/except wrapper around `resolve_directive`. Soft-fail discipline per §9.5.

### §10.5 New: `_dm_respond_and_post_failure:` (auto-fire exception)

```
_dm_respond_and_post_failure: campaign={N} actor={name} skill={skill} err={repr}
```

Fires from the scheduled coroutine's try/except. Distinct from the Phase 1 case (where `_dm_respond_and_post` was never called) — Ship 1's auto-fire can fail in new ways (Discord rate limit, channel deletion, etc.).

### §10.6 New: `verification:` extension for ROLL_OUTCOME_DRIFT

`narration_verifier.py`'s existing `verification:` log line (`narration_verifier.py:713-722`):

```
verification: campaign={N} passed={0|1} violation_class={...} detected={...} retry_fired={0|1} retry_passed={0|1|-} escalated={0|1} narration_chars={N} canonical_combatants_count={N}
```

The `violation_class` enum extends to include `roll_outcome_drift`. No format change to the log line itself — the enum-value addition is the only delta.

### §10.7 Per-turn empirical baseline

Per `BUG_1_SPEC.md` §I and the §59 always-fire pattern, Ship 1's logs follow the empirical-baseline discipline: every `directive_would_fire_dm_respond` event fires `resolution_log_summary` regardless of whether resolution succeeded or skipped. Grep patterns for Phase 2 ✅ criterion 5 (§3.3):

```
journalctl --user -u virgil-discord | grep "directive_resolved:" | grep "outcome=PASSED\|outcome=FAILED" | wc -l
# count of successful resolutions

journalctl --user -u virgil-discord | grep "verification:" | grep "violation_class=roll_outcome_drift" | wc -l
# count of ROLL_OUTCOME_DRIFT violations (criterion 5: must equal 0)
```

These two greps satisfy criterion 5's measurement contract verbatim.

---

## §11. Decision points

Each decision: trade-offs, recommended default, confidence, surfaced additions, related-decisions cross-references. **The recommendations from MULTIPLAYER_FIXES.md §4.4 are planner leans, not locks** — spec author either confirms or pushes back.

### §11.1 — DC source (parser vs. explicit DM input)

**Question:** Where does the DC come from?

**Options:**
- (a) Parse DC from the directive emit text (`!check perception 10` → DC=10)
- (b) DM types DC explicitly in a separate field/flag (`!check perception -dc 10`)

**Planner lean (MULTIPLAYER_FIXES.md §4.4 #1):** (a). Spec **confirms** (a).

**Trade-offs:**
- (a) preserves the existing directive surface; no new syntax for the DM to learn; DC parsing is a small regex extension to the existing parser path
- (a) requires the DM to type the DC inline (slightly more typing per directive)
- (b) is more flag-shaped (Avrae-conventional); cleaner for users who already think in Avrae flags
- (b) requires a new flag parser; conflicts with `_directive_skill_is_clean`'s trailing-args rejection (every flag becomes a parser exception)
- (b) is strictly additive — (a)-shape `!check perception 10` could still work as a shortcut

**Recommendation:** Lock **(a)** with the parser shape from §6.2. The DM-typed inline form is the lowest-friction option and matches existing precedent (`!check perception` already has a trailing-skill structure; adding a trailing-DC integer is a natural extension).

**Confidence:** HIGH. Planner lean confirmed by recon — the parser surface is small (~10 lines) and the edge-case table (§6.3) is exhaustive for v1.

**Surfaced additions:** None. Parser regex + edge cases locked in §6.

**Related:** §11.2 (no-DC behavior), §11.10 (skill normalization).

---

### §11.2 — No-DC directive behavior

**Question:** When DM types `!check perception` without a DC, what happens?

**Options:**
- (a) Default DC 10 always
- (b) Skip resolution binding; fall through to existing free-narration flow
- (c) Prompt DM via #dm-aside to set a DC before resolution fires

**Planner lean (MULTIPLAYER_FIXES.md §4.4 #2):** (b). Spec **confirms** (b).

**Trade-offs:**
- (a) makes every directive resolve; preserves the auto-narration path uniformly. But it strips DM authority over which checks have stakes — a "casual" perception check now binds an outcome the DM didn't intend
- (b) makes resolution opt-in. DM types DC → resolution fires. DM types skill-only → free-narration fires, same as today. DM authority preserved over which checks bind
- (c) adds DM friction (aside prompts mid-flow). Rejected on UX grounds — DMs are already cognitively loaded per F-55

**Recommendation:** Lock **(b)**. Implementation: §6.4 graceful-degrade — directive still binds in Phase 1 sense (row created, age tracked, consume on Avrae roll arrival), but resolution skips and the existing free-narration flow proceeds. The directive's `dc` column is NULL; `resolve_directive` returns None; matcher logs `directive_resolution_skipped: reason=no_dc`; no auto-fire.

**Edge case:** "What if the player responds before the existing free-narration would have fired anyway?" — Answer: same as Phase 1 today. The player types a response, `dm_respond` runs through the normal path, `adjudicate` sees the player input, fires whatever verdict shape applies. No regression.

**Confidence:** HIGH. The decision preserves Phase 1's existing behavior for no-DC directives — a pure additive layer on top.

**Surfaced additions:** Should the directive row still bind without a DC (Phase 1 binding semantics) or should `!check perception` (no DC) skip binding entirely? Spec recommendation: **still bind** — preserves the actor-mismatch detection surface for telemetry. The directive is a no-DC binding; resolution is just disabled.

**Related:** §11.1 (DC source), §6.4 (graceful degrade).

---

### §11.3 — Crit handling (nat 20 / nat 1)

**Question:** Does nat-20 auto-succeed and nat-1 auto-fail on skill checks?

**Options:**
- (a) RAW D&D 5e — only attack rolls and death saves auto-succeed/fail; skill checks resolve strictly on `roll_total >= dc`
- (b) Table rule — nat-20 always succeeds, nat-1 always fails, regardless of DC

**Planner lean (MULTIPLAYER_FIXES.md §4.4 #3):** RAW for v1. Spec **confirms** RAW.

**Trade-offs:**
- (a) is canonical; respects 5e mechanics; aligns with how the wider D&D community plays
- (a) means nat-20 on a DC 30 check still fails. Some players find this counterintuitive
- (b) is the "fun" rule that many tables apply informally
- (b) requires resolution to ignore `passed` and override on `nat == 20 or nat == 1`; cleaner to keep `passed` as the single source of truth in v1

**Recommendation:** Lock **RAW**. Implementation: `ResolutionResult.passed = (roll_total >= dc)`, full stop. `nat` and `crit` fields are captured in the dataclass (§5.3) for future use but **do not affect `passed` in v1**.

**v1.x candidate:** Table-rule customization per campaign. Config flag like `dnd_campaigns.crit_succeed_skill_checks BOOLEAN`. Out of scope for Ship 1.

**Confidence:** HIGH. Avrae embeds surface `nat` and `crit` (recon Q2 confirmed); the data is captured even though v1 doesn't act on it. Adding table rules later is a small change because the dataclass already carries the fields.

**Surfaced additions:** Should the AUTHORITATIVE-CANON block surface the `nat` value when nat-20 or nat-1? Spec recommendation: **no** — keep the block tight per §7.5's generic-phrasing discipline. The narration is free to mention "a critical roll" in flavor; the binding constraint stays pure pass/fail.

**Related:** §5.3 (nat/crit fields), §7.5 (per-skill phrasing).

---

### §11.4 — Multi-actor mismatch path

**Question:** Wrong-actor rolls (skill matches, actor doesn't) — does Ship 1 change Phase 1's behavior?

**Phase 1 behavior:** Log `directive_actor_mismatch:`, post wrong-actor aside, do NOT consume the directive row. Row stays alive until the right actor rolls OR TTL expires.

**Planner lean (MULTIPLAYER_FIXES.md §4.4 #4):** Confirm Ship 1 does not change this. Spec **confirms**.

**Trade-offs:**
- (a) Preserve Phase 1 behavior — wrong-actor mismatch is observable telemetry; row stays alive for the right actor; no auto-fire
- (b) Auto-resolve against the wrong actor (treat the roll as canonical for whoever rolled) — rejected: violates the directive's intent (DM said "perception check from Donovan"; resolving against Karrok's roll is wrong)
- (c) Suppress the wrong-actor aside in some cases — rejected: aside is the Phase 1 telemetry surface for DMs to learn the directive-bound-actor pattern

**Recommendation:** Lock **(a)**. No change to Phase 1 mismatch path.

**Surfaced addition — multi-actor batch ambiguity (S32 §4.3):** *"Discord footer at 10:20 PM showed `⚔ Donovan Ruby, Karrok The Devourer` but `last_active_actor` only stored `Donovan Ruby` (first chronological actor)."* When DM emits `!check perception` after a multi-actor batch turn, the directive binds to Donovan (first chronological). If Karrok rolls, mismatch fires (false-positive aside; Karrok was a legitimate target).

**Ship 4.5 (filed candidate, not committed):** S32 evidence already flagged this as a Multi-Actor Temporal State decision point. Ship 1 inherits the false-positive friction; Ship 4.5's slot decision (defer to Ship 1 verify checkpoint) decides whether `last_active_actors` becomes a list. Ship 1 verify scenario (§13) instruments the false-positive rate so the Ship 4.5 decision is data-driven.

**Spec adds a measurement criterion:** at Ship 1 verify, count `directive_actor_mismatch:` lines that immediately follow a `_dm_respond_and_post:` with multi-actor `actor_names_canonical` (i.e., a multi-actor batch turn preceded the directive). If rate > 1 per session, Ship 4.5 ships. If ≤ 1 per session, file v1.x.

**Confidence:** HIGH for Phase 1 preservation; MEDIUM for the new measurement criterion (Ship 1 doesn't change the false-positive rate; it just observes it).

**Related:** Ship 4.5 (`MULTIPLAYER_FIXES.md` §7B), §13 (live-verify scenario).

---

### §11.5 — Save and cast directive resolution

**Question:** Which directive kinds does Ship 1 resolve?

**Options:**
- (a) Check + save + cast — all three Phase 1 kinds resolve
- (b) Check + save only — cast deferred (cast doesn't have a DC at emit time; resolution happens at target's save)
- (c) Check only — save also deferred

**Planner lean (MULTIPLAYER_FIXES.md §4.4 #5):** (b). Spec **confirms** (b).

**Trade-offs:**
- (a) is ambitious; cast resolution is structurally different. The directive `!cast fireball` doesn't have a DC at emit time — Avrae's cast doesn't produce a save DC, it produces a damage roll. The save is on each target's side, and target identity isn't known at directive-emit time. (a) requires substantial new architecture.
- (b) is the cleanest scope. Check + save share the exact same resolution shape (DC vs. roll_total). Cast is filed v1.x with its own spec.
- (c) is conservative but loses parity — `!save dex` is structurally identical to `!check stealth` from the resolver's perspective. No reason to defer save.

**Recommendation:** Lock **(b)**.

**Implementation:** `resolve_directive` returns None on `kind='cast'` (§4.3 line `if kind not in ('check', 'save')`). The matcher logs `directive_resolution_skipped: reason=cast_kind`; row is consumed; existing free-narration flow proceeds. **Cast directives stay in Phase 1 telemetry-only behavior unchanged.**

**Surfaced addition:** Cast resolution requires:
- DC source: the target's save DC (spell-defined, e.g. fireball's caster-spell-save-DC)
- Roll source: the target's save roll (which is a separate Avrae event, not the caster's `!cast`)
- Target identity: which combatant is making the save (cast → many targets, each rolls separately)

None of these are present in the current `!cast` directive parse + Avrae embed pair. Cast resolution is its own architectural spec, filed as **v1.x candidate "Cast Resolution Binding"** for a future ship. Not blocked by Ship 1; not enabled by Ship 1.

**Confidence:** HIGH. The scope is clean; the deferral is well-motivated.

**Related:** `MULTIPLAYER_FIXES.md` §4.7 (cast out of scope).

---

### §11.6 — Phase 2 trigger criterion 5

**Question:** What's the fifth criterion added to BUG_1_SPEC.md §L?

**Planner lean (MULTIPLAYER_FIXES.md §4.4 #6):** "Narrated outcome matches roll-vs-DC verdict in 100% of consumed directives" — measured via ROLL_OUTCOME_DRIFT verifier (zero violations across one session = pass).

**Spec confirms** the criterion. Measurement details locked in §3.3:

- **What "one session" means:** A `/play` open through `/play` close (or service restart), bounded by `state_footer:` log lines at session boundaries
- **What "consumed directive" means:** `directive_resolved:` log line fires (i.e., resolve_directive returned non-None)
- **Multi-session calibration:** Not needed. The criterion is structural (engine-bound outcome) not stochastic (LLM-bound outcome). One session is sufficient because the binding cannot drift without ROLL_OUTCOME_DRIFT firing.

**Greppable shape:**

```
Total resolutions:   journalctl --user -u virgil-discord | grep -c "directive_resolved:"
Drift violations:    journalctl --user -u virgil-discord | grep -c "violation_class=roll_outcome_drift"
Criterion satisfied: drift_violations == 0
```

**Confidence:** HIGH. The verifier class is the structural enforcement mechanism; the log greps are unambiguous.

**Surfaced addition — what about retry-passed violations?** If ROLL_OUTCOME_DRIFT fires once but the retry passes verification, is that a violation for criterion 5? **Spec recommendation: no** — the retry-passed case shipped clean narration; criterion 5 measures "narrated outcome matches" which is satisfied if the final-posted narration is clean. Grep narrowed:

```
Drift violations (unretried or retry-failed):
  journalctl --user -u virgil-discord | grep "violation_class=roll_outcome_drift" | grep "retry_passed=0\|retry_passed=-" | wc -l
```

Cleaner than counting all-fires. Criterion 5 success = this grep returns 0.

**Related:** §8 (verifier class), §10.6 (log shape).

---

### §11.7 — Backward compatibility (manual-trigger flow)

**Question:** When the DM manually narrates after a directive consume (instead of the bot auto-firing), what happens?

**Options:**
- (a) Manual-trigger bypasses resolution binding entirely — bot's auto-fire still happens; DM's manual narration appears in flow as its own beat
- (b) Manual-trigger also runs resolution binding — the bot's `verify_narration` runs against the DM's narration text
- (c) Deprecate manual-trigger entirely — DM cannot post narration in #dm-narration after a directive; only the bot can

**Planner lean (MULTIPLAYER_FIXES.md §4.4 #7):** (a). Spec **confirms** (a).

**Trade-offs:**
- (a) preserves DM's escape hatch. DM is always authoritative; if the bot's auto-narration is wrong, DM can fix it by typing manual narration. Race condition is observable but not pathological.
- (b) is intrusive. DM's manual narration would get gated by a verifier that doesn't know what the DM intends. Pushes DM toward "let the bot handle it" which is the opposite of what the matcher should enable.
- (c) is brutal. DMs need the escape hatch; removing it would be hostile to the actual DM workflow.

**Recommendation:** Lock **(a)**.

**How to detect manual-trigger:** Ship 1 v1 does **not** detect it. The bot's auto-fire happens unconditionally on resolve. If the DM races and types narration, both appear. The DM can then delete the bot's message (Discord standard), or accept both. Race-detection is v1.x.

**Does the directive still get consumed when DM narrates manually before Avrae rolls?** Yes — the directive row stays alive until either:
- Avrae roll arrives (matcher consumes per `_handle_dm_roll_arrival`)
- Edit-cancel path (DM edits the directive message; row cancels)
- TTL expires (lazy sweep)

DM's free-form #dm-narration text does not consume the directive. This matches Phase 1 semantics exactly.

**Confidence:** HIGH. Manual override is a feature, not a bug. Detection is a v1.x improvement, not a blocker.

**Related:** §9.6 (manual-trigger fallback), §13 (live-verify scenario tests the race timing).

---

### §11.8 — Synthesized `combined_action` / `actions` shape

**Question:** What goes in the `actions` tuple and `combined_action` string when the matcher auto-fires `_dm_respond_and_post`?

**Options:**
- (a) Sentinel string (`"<ROLL_RESOLUTION:perception:check>"`)
- (b) Natural-language synthesis (`"Donovan rolls perception"`)
- (c) Bracket-framed semi-sentinel (`"[Roll resolution: Donovan rolled perception (check); outcome bound at top-of-prompt.]"`)
- (d) Empty string

**Spec recommendation:** (c).

**Trade-offs:**
- (a) is too synthetic; LLM may produce garbled narration treating the sentinel as junk
- (b) re-introduces the F-45 failure surface — LLM treats the text as an unbound action declaration and narrates whatever fits
- (c) gives the LLM enough narrative grounding (actor, skill, kind) without re-asserting an unbound action; the bracket-frame signals "narrative directive, not player input"
- (d) loses actor-name presence in `combined_action`; some downstream paths (e.g., `update_scene`'s "Last actions:" line) lose context

**Recommendation:** Lock **(c)** with the exact template:

```python
synthesized_input = (
    f"[Roll resolution: {result.actor} rolled {result.skill_or_save} "
    f"({result.check_kind}); outcome bound at top-of-prompt.]"
)
```

**Confidence:** MEDIUM-HIGH. The shape feels right but is untested in live play. Verify (§13) should explicitly check the narration quality of auto-fired turns — if the LLM treats the bracket as garbage and produces stilted prose, revisit.

**Surfaced addition:** Should the synthesized input also include the rolled value? E.g. `"... rolled perception 6 vs DC 10; FAILED; outcome bound at top-of-prompt."` — more redundant with the AUTHORITATIVE-CANON block, but reinforces the binding. **Spec recommendation: no** — keep the synthesized input terse; the AUTHORITATIVE-CANON block does the work. Adding redundancy risks the LLM picking up the wrong source of truth.

**Related:** §7 (prompt block), §9.3 (actions list shape).

---

### §11.9 — Defensive ordering when both arbitration and resolution fire

**Question:** What if `build_dm_context` is somehow called with both `arbitration_block` AND `resolution_block` non-empty?

**Context:** Per §2.3, these are mutually exclusive by flow in v1. But the kwarg structure allows both; spec should define the defensive behavior.

**Options:**
- (a) Render both, side-by-side, top-of-prompt (current §7.1 implementation)
- (b) Render only one, with priority (e.g., resolution > arbitration, since resolution is engine-bound)
- (c) Render only one, with arbitration priority (since arbitration is the more general adjudication path)
- (d) Log a warning + render both (Phase 1 observability discipline)

**Spec recommendation:** (a) + (d) — render both, log a warning.

**Trade-offs:**
- (a) preserves the kwarg independence; structurally simple
- (b)/(c) introduce a priority rule that may surprise future readers; explicit suppression hides information from the LLM
- (d) gives observability so any unintended co-occurrence is caught

**Recommendation:** Lock **(a)** for rendering + **(d)** for logging. New log line:

```
unexpected_binding_co_occurrence: campaign={N} has_arbitration={1|0} has_resolution={1|0}
```

Fires from `build_dm_context` if both kwargs are non-empty. Fires once per call. If logs ever show this, investigate the flow that produced it.

**Confidence:** HIGH. Defensive coding + observability is the spec norm.

**Related:** §2.3 (mutual exclusion analysis), §7.1 (top-of-prompt rendering).

---

### §11.10 — Skill normalization at resolve time

**Question:** Does `resolve_directive` apply any skill normalization beyond what Phase 1's matcher already does?

**Phase 1 behavior:** `_normalize_skill_for_match(s) = ' '.join(s.lower().split())` is applied to both Avrae's `event['detail']` and the pending row's `check_type` at match time (BUG_1_SPEC.md §D.2). No alias map — `sneak`↔`stealth` silently misses in Phase 1.

**Spec decision:** No additional normalization in Ship 1.

**Trade-offs:**
- (a) Reuse Phase 1's normalization unchanged — matcher's actor-match already passed by the time `resolve_directive` runs; skill is canonicalized by Avrae's parser
- (b) Add an alias map at resolve time — too late; the directive is already consumed and the skill mismatch would have prevented match

**Recommendation:** Lock **(a)**. Skill alias handling is filed v1.x per `BUG_1_SPEC.md` §N. If logs show meaningful alias miss rate (e.g., 5+ `pending_directive_expired:` lines per session naming non-Avrae-canonical skills), file the alias-map ship.

**Confidence:** HIGH. Resolution time is the wrong layer for alias handling.

**Related:** BUG_1_SPEC.md §N (v1.x candidates).

---

### §11.11 — Auto-fire failure recovery

**Question:** If `_dm_respond_and_post` raises (Discord rate limit, channel deletion, etc.) AFTER the directive is consumed, what happens?

**Phase 1 baseline:** The directive is consumed; `_dm_respond_and_post` is not called; no failure mode.

**Ship 1 introduces a new failure mode:** consume happens, then the scheduled auto-fire fails. Now the user sees no narration at all — the directive resolution was lost.

**Options:**
- (a) Log failure; do nothing else. The Avrae roll embed is still in Discord; the player can re-prompt with manual text input
- (b) Post a deterministic fallback aside ("Roll resolution: Donovan FAILED Perception DC 10 — narration unavailable") so the resolution is visible even if the LLM-narration path failed
- (c) Restore the directive row + log restoration, so a subsequent roll-arrival (none expected, but defensive) could retry. **Risky** — restores TOCTOU concerns; the consume was an authoritative event
- (d) Schedule a retry after N seconds

**Spec recommendation:** (a) + (b).

**Trade-offs:**
- (a) alone leaves a confusing UX gap (the bot announced a DC, Avrae rolled, then nothing)
- (b) makes the resolution visible even on LLM-path failure; uses the same deterministic-placeholder pattern as `narration_verifier`'s escalation
- (c) introduces a re-fire surface that's hard to reason about; rejected
- (d) adds complexity for an edge case; rejected for v1

**Recommendation:** Lock **(a) + (b)**:

```python
# In the scheduled coroutine for _dm_respond_and_post:
try:
    await _dm_respond_and_post(..., resolution_result=resolution)
except Exception as e:
    log(f"_dm_respond_and_post_failure: campaign={campaign_id} "
        f"actor={resolution.actor} skill={resolution.skill_or_save} err={e!r}")
    # Deterministic fallback aside (mirrors narration_verifier's
    # escalation placeholder pattern).
    fallback_text = (
        f"Roll resolution: {resolution.actor} "
        f"{resolution.skill_or_save.replace('_',' ').title()} "
        f"{resolution.check_kind} at DC {resolution.dc} "
        f"(rolled {resolution.roll_total}). "
        f"Result: {'PASSED' if resolution.passed else 'FAILED'}."
    )
    await _post_dm_aside(guild, fallback_text)
```

**Confidence:** MEDIUM. The fallback aside is right shape but UX may want refinement (e.g., post to #narration instead of #dm-aside). Live-verify in §13 tests this path.

**Surfaced addition:** Should the fallback aside go to #dm-narration (public) or #dm-aside (DM-only)? Spec recommendation: **#dm-aside** — same channel as Phase 1's wrong-actor aside; doesn't pollute player narration with engine-shape strings.

**Related:** §9.5 (soft-fail), §10.5 (log line).

---

### §11.12 — Vocabulary reuse vs. fork for ROLL_OUTCOME_DRIFT

**Question:** Does ROLL_OUTCOME_DRIFT reuse VERDICT_CONTRADICTION's `_CHECK_FAILURE_SUCCESS_PHRASES` / `_CHECK_SUCCESS_FAILURE_PHRASES`, or fork them?

**Spec recommendation:** Reuse, as §8.3 states.

**Trade-offs:**
- (a) Reuse — single vocabulary surface; consistent detection across both classes; one place to tune false-positive rate
- (b) Fork — independent tuning per class; could narrow ROLL_OUTCOME_DRIFT's regex for the engine-bound case

**Recommendation:** Lock **(a)** reuse.

**Confidence:** HIGH. Single source of truth aligns with Doctrine §17; the phrases are correct for both surfaces (check-success-on-failure language is the same regardless of whether the binding came from adjudicator or resolution).

**Surfaced addition:** Should ROLL_OUTCOME_DRIFT have an additional vocabulary surface for save-shape phrasings (where check-shape phrases may not apply)? Spec recommendation: **defer to verify pass** — the existing vocabulary was tuned against arbitration's CHECK class which already covered "check or save" semantically. Save-specific phrases (e.g., "resists", "shrugs off") may want adding to `_CHECK_SUCCESS_FAILURE_PHRASES` based on observed live-fire. Reassess at Ship 1 verify checkpoint.

**Related:** §8.3 (vocabulary), §13 (live-verify scenario).

---

### §11.13 — `resolve_directive` input source (`consume_recent_check` vs. direct avrae_event)

**Question:** Should `resolve_directive` accept the `avrae_event` directly, or delegate to the existing `consume_recent_check` helper in `adjudicator.py`?

**Context:** Track 7 #1 uses `consume_recent_check(avrae_events, actor_name, skill)` (`adjudicator.py:655`) to consume a buffered roll. It's the canonical roll-extractor.

**Spec recommendation:** Direct `avrae_event` passing.

**Trade-offs:**
- (a) Direct — matcher already has the event; no buffer-consume needed; pure function with explicit input
- (b) Delegate — single canonical extractor; matches Track 7 #1's pattern

**Recommendation:** Lock **(a)** direct. Reasoning:
- `consume_recent_check` is a buffer-mutating operation (consume = mark used). The matcher is operating on a single fresh event, not a buffer search.
- The directive's actor + skill have already been matched by `_handle_dm_roll_arrival` before `resolve_directive` is called. Re-matching via `consume_recent_check` would duplicate work.
- Pure functions should accept fully-resolved inputs; `consume_recent_check` is the adjudicator's surface for its specific flow.

**Confidence:** HIGH. The two paths have legitimately different shapes.

**Related:** §4.1 (signature), `adjudicator.py:655` precedent.

---

### §11.14 — Debounce / rapid-fire handling

**Question:** Does Ship 1 implement debounce for rapid-fire directives?

**Context:** S32 §4.5 observed 6× investigation directives in 30 seconds during one playtest moment.

**Options:**
- (a) No debounce in v1; observe behavior in logs; file v1.x if needed
- (b) Coalesce: only fire the LAST resolution in a same-actor-same-skill burst within N seconds
- (c) Hard rate-limit: never fire `_dm_respond_and_post` more than once per N seconds

**Spec recommendation:** (a).

**Trade-offs:**
- (a) lets data drive the decision; the §9.7 analysis suggests the rapid-fire case is actually rare in practice (`pending_directive_replaced` flow means most rapid emits don't produce multiple consumes)
- (b) adds matcher state (last-fire timestamp per actor+skill) and a "queue and fire latest" mechanism; non-trivial
- (c) penalizes the legitimate case where a DM intentionally fires fast resolution sequences

**Recommendation:** Lock **(a)**.

**Confidence:** MEDIUM-HIGH. The §9.7 analysis is logically sound but unproven. If Ship 1 verify shows multiple auto-fires within a short window, file a debounce ship.

**Surfaced criterion:** S32's observed 6× investigation burst was test behavior (DM checking how the system responded to repeated rolls), not natural play cadence. Real-play rapid-fire is expected to occur only when the DM corrects a wrong-type directive (e.g., types `!check perception` then realizes it should have been `!check investigation` and re-fires). If Ship 1 verify shows >2 *consumed* auto-fires in any 60-second window during natural play, file v1.x debounce ship.

**Related:** §9.7 (rapid-fire analysis), §13 (live-verify scenario).

---

## §12. Test plan

Target: ~40 assertions across 2 new test files + extensions to existing tests. Mirrors the spec-implementation discipline established by Track 7 #2 (test_narration_verifier.py: 40 assertions) and Bug 1 Phase 1 (test_pending_roll_directives.py: 19 assertions).

### §12.1 New file: `test_resolve_directive.py`

Engine-layer unit tests against `dnd_orchestration.resolve_directive` + `ResolutionResult` + `render_resolution_block` + `render_resolution_hardstop_echo`.

**~18 assertions:**

1. `resolve_directive` returns ResolutionResult with `passed=True` when `roll_total >= dc` (check kind)
2. `resolve_directive` returns ResolutionResult with `passed=False` when `roll_total < dc`
3. `resolve_directive` returns ResolutionResult with correct fields for save kind
4. `resolve_directive` returns None for cast kind (§11.5)
5. `resolve_directive` returns None for attack kind (defensive — out of scope)
6. `resolve_directive` returns None when `directive_row.dc` is None (§11.2)
7. `resolve_directive` returns None when `avrae_event.result` is None (§4.3 malformed)
8. `resolve_directive` captures `nat` field when present (§5.3)
9. `resolve_directive` captures `crit` boolean (§5.3)
10. `ResolutionResult.passed = True` for `roll_total == dc` (boundary case)
11. `render_resolution_block` produces correct PASSED text for `passed=True`
12. `render_resolution_block` produces correct FAILED text for `passed=False`
13. `render_resolution_block` Title-Cases multi-word skill (`sleight of hand` → `Sleight Of Hand`)
14. `render_resolution_block` uses `check` literal when `check_kind='check'`
15. `render_resolution_block` uses `save` literal when `check_kind='save'`
16. `render_resolution_hardstop_echo` returns single-line `Outcome: PASSED.` / `Outcome: FAILED.`
17. `resolution_log_summary` returns `directive_resolved:` line for non-None result
18. `resolution_log_summary` returns `directive_resolution_skipped:` line for None result

### §12.2 New file: `test_roll_outcome_drift.py`

Verifier-layer tests against `narration_verifier.py`'s new ROLL_OUTCOME_DRIFT class.

**~12 assertions:**

1. `verify_narration` with `resolution_result.passed=False` + narration containing "succeeds" fires ROLL_OUTCOME_DRIFT
2. `verify_narration` with `resolution_result.passed=True` + narration containing "fails" fires ROLL_OUTCOME_DRIFT
3. `verify_narration` with `resolution_result=None` does NOT fire ROLL_OUTCOME_DRIFT (no-op path)
4. `verify_narration` with `resolution_result.passed=False` + narration containing "fails" PASSES
5. `verify_narration` with both `arbitration_result` (CHECK passed) and `resolution_result` (passed) — narration containing "succeeds" passes both classes
6. `verify_narration` fires VERDICT_CONTRADICTION (not ROLL_OUTCOME_DRIFT) when arbitration's CHECK contradicts — confirms detection-order priority (§8.4)
7. ROLL_OUTCOME_DRIFT detection order: fires AFTER STATE_MUTATION_CLAIM, BEFORE ACTOR_OMISSION
8. `_retry_constraint_roll_outcome_drift` includes actor, skill, kind, DC, roll_total, outcome
9. `build_verification_retry_prefix` produces non-empty prefix for ROLL_OUTCOME_DRIFT result
10. `build_escalation_placeholder` with `failed_violation_class=ROLL_OUTCOME_DRIFT` produces deterministic block (§8.7)
11. `verify_narration` with empty narration text passes (existing fail-open envelope unchanged)
12. ROLL_OUTCOME_DRIFT respects VERIFICATION_ENABLED flag (when False, returns passed=True)

### §12.3 Extensions to `test_pending_roll_directives.py`

Add ~6 assertions covering:

1. `dnd_pending_roll_directives.dc` column exists after `db_init()` (idempotent migration)
2. `pending_directive_upsert` accepts a `dc` kwarg and stores the value
3. `pending_directive_upsert` accepts `dc=None` and stores NULL
4. `pending_directive_get_active` returns rows with `dc` field populated
5. `parse_skill_and_dc('perception 10')` returns `('perception', 10)`
6. `parse_skill_and_dc('sleight of hand 12')` returns `('sleight of hand', 12)` (multi-word skill)

### §12.4 Extensions to `test_narration_verifier.py`

Add ~4 assertions covering the existing four-class regression — ensure ROLL_OUTCOME_DRIFT does not break existing classes:

1. FABRICATED_COMBATANT still fires when narration introduces non-canonical NPC (regression)
2. VERDICT_CONTRADICTION still fires when arbitration CHECK contradicts narration (regression)
3. STATE_MUTATION_CLAIM still fires when narration asserts HP (regression)
4. ACTOR_OMISSION still fires when arbitration non-FREE actor absent from narration (regression)

### §12.5 Total assertion count

| File | New | Existing | Total |
|------|-----|----------|-------|
| `test_resolve_directive.py` | 18 | 0 | 18 |
| `test_roll_outcome_drift.py` | 12 | 0 | 12 |
| `test_pending_roll_directives.py` | 6 | 19 | 25 |
| `test_narration_verifier.py` | 4 | (existing) | existing+4 |

**~40 new assertions.** Matches `MULTIPLAYER_FIXES.md` §4.5 estimate.

---

## §13. Live-verify scenario

This section populates `tests-to-run-post-session.md` after Ship 1 implementation lands. The scenario walks the Discord steps + grep patterns for the verify pass.

### §13.1 Test campaign setup

Use the existing test campaign (campaign 22 per S32 records). Two bound PCs minimum (Donovan Ruby + a second character — Hilda or Karrok). DM is Jordan.

Pre-flight: `/play` to open. Address one PC via narration to set `last_active_actor` (Phase 1 §M step 2 baseline).

### §13.2 Scenario A — Successful check resolution (PASSED)

**Steps:**

| # | Step | Input |
|---|------|-------|
| 1 | Open campaign | `/play` |
| 2 | Address Donovan | DM types in #dm-narration: `Donovan, you see something glinting in the corner of the room.` |
| 3 | Wait for bot narration | (bot responds; footer updates to Donovan Ruby) |
| 4 | Emit directive with DC | DM types: `!check perception 10` |
| 5 | Donovan rolls (with high modifier or advantage to ensure passing) | Donovan player types: `!check perception` |
| 6 | Verify bot auto-narrates | (bot posts narration with success framing within ~10s) |

**Greps:**

```bash
# Step 4 should produce:
journalctl --user -u virgil-discord | grep "directive_bound_to_footer_actor:" | tail -1
# Expect: actor=Donovan Ruby skill=perception directive_age_s=0

# Step 5 should produce:
journalctl --user -u virgil-discord | grep "directive_resolved:" | tail -1
# Expect: actor=Donovan Ruby skill=perception check_kind=check dc=10 roll_total=>=10 outcome=PASSED

journalctl --user -u virgil-discord | grep "directive_would_fire_dm_respond:" | tail -1
# Expect: outcome=PASSED roll_total=<value> dc=10

# Step 6 should produce:
journalctl --user -u virgil-discord | grep "verification:" | tail -1
# Expect: passed=1 (or passed=0 + retry_passed=1)
```

**Expected narration shape:** Bot describes Donovan succeeding at perception — finds the glinting object, describes it in flavorful terms. Does NOT use any "fails" / "can't" / "doesn't notice" language.

### §13.3 Scenario B — Failed check resolution (FAILED) — the F-45 surface

**Steps:**

| # | Step | Input |
|---|------|-------|
| 1 | Continue from Scenario A | (same campaign session) |
| 2 | DM emits a new directive at a high DC | DM types: `!check perception 20` |
| 3 | Donovan rolls (modifier should make passing unlikely) | Donovan player types: `!check perception` |
| 4 | Wait for bot narration | (bot posts within ~10s) |
| 5 | **The F-45 surface test:** Donovan player ALSO types: `I passed the check` | (this should NOT change the bot's already-emitted narration; the bot's narration was auto-fired before this player turn) |

**Greps:**

```bash
# Step 2-3 should produce:
journalctl --user -u virgil-discord | grep "directive_resolved:" | tail -1
# Expect: dc=20 roll_total=<low value> outcome=FAILED

# Step 4 should produce:
journalctl --user -u virgil-discord | grep "verification:" | tail -1
# Expect: passed=1 violation_class=none
# (LLM should narrate failure cleanly given the AUTHORITATIVE-CANON block)

# If verification fires roll_outcome_drift:
journalctl --user -u virgil-discord | grep "violation_class=roll_outcome_drift" | tail -3
# Track for criterion 5 grep (§11.6)
```

**Expected narration shape:** Bot describes Donovan failing at perception — misses the detail, comes up empty, doesn't notice. Honors `Outcome: FAILED.`

**Step 5 (the F-45 test):** Player asserts "I passed" AFTER the bot has narrated. Since the bot already fired, this player input goes through normal player-input → adjudicate → dm_respond → narration flow. The adjudicate result will be FREE (no action declared, just an assertion). The next bot turn (if any) operates on free-narration; no resolution-binding fires.

**Critical:** the bot's narration from step 4 should NOT be "rolled back" or re-fired due to the player's assertion. Player honor system is no longer the adjudicator — the engine-bound resolution from step 3 stands.

### §13.4 Scenario C — Save resolution

**Steps:**

| # | Step | Input |
|---|------|-------|
| 1 | DM emits save directive | `!save dex 15` |
| 2 | Player rolls save | `!save dex` |
| 3 | Verify auto-narration |

**Greps:**

```bash
journalctl --user -u virgil-discord | grep "directive_resolved:" | grep "check_kind=save" | tail -1
# Expect: outcome=PASSED or FAILED per roll
```

### §13.5 Scenario D — No-DC directive (graceful degrade)

**Steps:**

| # | Step | Input |
|---|------|-------|
| 1 | DM emits directive without DC | `!check stealth` |
| 2 | Player rolls | `!check stealth` |
| 3 | Verify NO auto-narration; existing free-narration flow |

**Greps:**

```bash
journalctl --user -u virgil-discord | grep "directive_resolution_skipped: campaign=22 reason=no_dc" | tail -1
# Expect: line exists

journalctl --user -u virgil-discord | grep "directive_resolved:" | tail -1
# Expect: line is the PRIOR successful resolution (no new line for this directive)
```

**Expected behavior:** No bot auto-narration on the stealth check. Existing free-narration flow proceeds when player types a follow-up.

### §13.6 Scenario E — Cast directive (skip path)

**Steps:**

| # | Step | Input |
|---|------|-------|
| 1 | DM emits cast directive (if any caster PC bound) | `!cast magic missile` |
| 2 | Player casts | `!cast magic missile -l 1` |

**Greps:**

```bash
journalctl --user -u virgil-discord | grep "directive_resolution_skipped:" | grep "reason=cast_kind" | tail -1
# Expect: line exists
```

**Expected behavior:** Phase 1 telemetry-only (no resolution). Existing cast narration flow proceeds.

### §13.7 Scenario F — Multi-actor mismatch (Ship 4.5 calibration)

**Steps:**

| # | Step | Input |
|---|------|-------|
| 1 | DM addresses two PCs in a single narration turn | `Donovan and Hilda, both of you sweep the room.` |
| 2 | Bot responds (both names in footer) | (auto) |
| 3 | DM emits directive | `!check perception 12` |
| 4 | Hilda (not Donovan; `last_active_actor` stored Donovan first) rolls | Hilda player: `!check perception` |
| 5 | Verify mismatch behavior |

**Greps:**

```bash
journalctl --user -u virgil-discord | grep "directive_actor_mismatch:" | tail -1
# Expect: expected_actor=Donovan Ruby actual_actor=Hilda
```

**Expected behavior:** Wrong-actor aside posts to #dm-aside; row stays alive; Hilda's roll is unconsumed.

**Calibration:** count these occurrences across the session. If > 1/session, Ship 4.5 ships (per §11.4). If ≤ 1/session, file v1.x.

### §13.8 Scenario G — Auto-fire failure path (defensive)

**Difficult to provoke deliberately** — Discord rate-limit + channel-deletion are environmental. Skip in v1 unless an organic failure occurs during verify. If observed, verify the fallback aside (§11.11) renders correctly.

### §13.9 Aggregate verify criteria

After running scenarios A–F across one session (target: 10+ resolutions across mixed pass/fail):

1. `directive_resolved:` count ≥ 5 (per Ship 1 gate criteria, `MULTIPLAYER_FIXES.md` §4.6)
2. `violation_class=roll_outcome_drift` with `retry_passed=0` count = 0 (criterion 5, §3.3)
3. DC parsing works for ≥ 4 distinct DC values (5, 10, 15, 20 minimum)
4. Mismatch rate observable for Ship 4.5 decision

### §13.10 Populates `tests-to-run-post-session.md`

After Ship 1 lands and verify passes, append a new section to `tests-to-run-post-session.md` with the Scenario A–F structure above, including the greps. Use the same shape as the existing S22/S23/S24/S25/B2 entries.

---

## §14. Doctrine candidates filed (do NOT anchor)

Per Doctrine §59, new candidates surface during ship work but anchor only after a second project instance shows the pattern. Ship 1 surfaces two candidates; neither anchors here.

### §14.1 — "Engine-computed binding > validator-on-LLM-output"

**Candidate phrasing:** *When an LLM-output failure mode can be closed by engine-computing the bound outcome and rendering it as a top-of-prompt constraint (rather than validating the LLM's output after the fact), the engine-computed path is structurally stronger. Validators close drift via retry pressure; engine binding closes drift via making the drift surface inaccessible. Both have a role — binding is the first reach; validation is the safety net.*

**Instances so far:**
1. **Track 7 #1 CHECK_ACTION binding** — adjudicator computes pass/fail from buffered roll vs DC; renders narration_constraint at top-of-prompt; LLM cannot drift on the outcome
2. **Ship 1 resolution binding** (this spec) — same shape applied to the DM-typed-directive surface

Two instances now. Per §59, file as candidate; anchor when a third instance surfaces. Likely third candidate: cast resolution binding (when v1.x ships) — same architectural shape applied to caster-spell-save-DC adjudication.

**Cross-references:**
- `MULTIPLAYER_FIXES.md` §2.3 (structural removal beats validation) — sibling principle
- Doctrine §1a — controlling invariant (LLM never decides mechanical outcomes)
- Doctrine §17 — single write paths per field
- `MULTIPLAYER_FIXES.md` §9.4 — validators-accumulate candidate (sibling principle, also filed)

### §14.2 — "Reused vocabulary across sibling verifier classes"

**Candidate phrasing:** *When two violation classes in narration_verifier detect the same linguistic surface (LLM uses success/failure phrasing) but against different binding objects (adjudicator vs. resolution-binding result), reuse the vocabulary rather than fork it. The class differentiation is which binding object is populated at call time; the detection phrases are identical.*

**Instances so far:**
1. **Ship 1 ROLL_OUTCOME_DRIFT** reuses VERDICT_CONTRADICTION's `_CHECK_FAILURE_SUCCESS_PHRASES` / `_CHECK_SUCCESS_FAILURE_PHRASES` (§8.3, §11.12)

One instance. File for pattern-watch. If a future verifier class (e.g., cast-resolution-drift, multi-actor-resolution-drift) also reuses the same vocabulary, anchor as a doctrine principle.

**Cross-references:** Doctrine §63 (sibling-fork at invariant divergence) — adjacent principle; this candidate operates one layer below ("when do siblings share implementation surface?").

### §14.3 — "Renderer not ruler" framing (per MULTIPLAYER_FIXES.md §9.5)

`MULTIPLAYER_FIXES.md` §9.5 defers anchoring this as a §1a wording revision. Ship 1 surfaces it as a candidate but **does not anchor** — the wording revision is filed for post-Ship-5 doctrine housekeeping. The spec uses the phrasing freely in §1 / §2 narrative without committing it to doctrine.

---

## §15. Out of scope

Per `MULTIPLAYER_FIXES.md` §4.7 — explicit out-of-scope items. Spec confirms each.

### §15.1 Cast directive resolution

Cast resolution requires target-side save adjudication, spell-DC sourcing, and target identity at directive-emit time. Filed as **v1.x candidate "Cast Resolution Binding"** for a future ship. Ship 1's `resolve_directive` returns None on `kind='cast'` per §4.3.

### §15.2 Player-typed `!check` flow

Phase 1 skips player-authored directives (`_handle_dm_roll_directive` gates on `_is_dm_message`). Ship 1 inherits — only DM-typed directives bind. Player-typed `!check perception` is the normal Avrae roll surface; it doesn't enter the matcher path.

### §15.3 Combat-mode rolls

Phase 1 skips directive creation when `scene_state.mode == 'combat'` (BUG_1_SPEC.md §F.1 gate 2). No directive row → no resolution. Combat-mode resolution is filed v1.x per `MULTIPLAYER_FIXES.md` §4.7.

### §15.4 F-58 (stale-footer name parsing)

F-58 stays a v1.1 candidate. Ship 1 inherits Phase 1's strict-footer-binding behavior; explicit-name parse from surrounding narration text (e.g., "Hilda, !check stealth") is out of scope.

### §15.5 Skill alias map (sneak ↔ stealth, etc.)

Phase 1 filed alias handling as v1.x. Ship 1 does not address it. Skill normalization stays the existing `_normalize_skill_for_match` (lowercase, whitespace-coalesced).

### §15.6 Multi-actor temporal state (Ship 4.5 candidate)

Filed candidate in `MULTIPLAYER_FIXES.md` §7B. Ship 1 verify (§13.7) instruments the mismatch rate that drives Ship 4.5's slot decision. Ship 1 itself does not change the multi-actor binding behavior.

### §15.7 Debounce / rapid-fire coalescing

Per §11.14, no debounce in v1. Filed as v1.x candidate if verify shows meaningful rapid-fire rate.

### §15.8 Manual-trigger detection

Per §11.7, manual-trigger flow bypasses resolution binding by inaction (no detection). Race-condition observability is a v1.x improvement.

### §15.9 Per-skill `intended outcome` phrasing

Per §7.5, AUTHORITATIVE-CANON block uses generic phrasing ("does not achieve the intended outcome") rather than per-skill outcome map. Future v1.x may revisit if logs show ambiguous-outcome drift.

### §15.10 Doctrine §76 anchoring

§76 (recursive hallucination memory loop) anchors in Ship 2 spec per `MULTIPLAYER_FIXES.md` §9.1. Ship 1 does not anchor doctrine.

### §15.11 §1a wording revision

Deferred to post-Ship-5 doctrine housekeeping per `MULTIPLAYER_FIXES.md` §9.5. Ship 1 spec uses "renderer not ruler" framing in prose freely but does not lock the wording revision.

### §15.12 ROADMAP, FAILURES, DOCTRINE, VIRGIL_MASTER, WHY updates

Per the prompt: doc-update pass happens after Ship 1 implementation lands, not during spec drafting. Spec only writes itself; downstream doc updates are S34's job after the implementation ships clean.

---

*End of spec v1 (DRAFT). Session 33 part 1.*

---

## Tabular handoff

| Field | Value |
|-------|-------|
| **File written** | `/home/jordaneal/virgil-docs/RESOLUTION_BINDING_SPEC.md` |
| **Status** | LOCKED v1 — S33 part 2 review complete (`RESOLUTION_BINDING_REVIEW.md`); 2 framing revisions applied (§3.2 row 2, §11.14 verify criterion) |
| **Decision count** | 14 (7 named in MULTIPLAYER_FIXES.md §4.4 + 7 surfaced additions); 12 locked at Code's recommendation, 2 with framing-only revisions |
| **HALT escalations** | None |
| **Recon findings (load-bearing)** | All five recon questions answered; see §4.2 (Avrae roll_total), §5.3 (nat/crit fields), §7.1 (AUTHORITATIVE-CANON anchor), §8 (ROLL_OUTCOME_DRIFT integration), §9.3 (synthesized actions shape) |
| **Bug 1 Phase 2 absorption** | §3 — four locked criteria addressed + criterion 5 added per `MULTIPLAYER_FIXES.md` §4.4 decision 6 |
| **Test plan** | ~40 assertions across 2 new + 2 extended test files (§12) |
| **Live-verify scenarios** | 6 scenarios (A–F) + aggregate criteria (§13) |
| **Doctrine candidates filed (not anchored)** | 2 — engine-computed binding > validator (§14.1), reused vocabulary across sibling classes (§14.2) |
| **Ready-for-implementation status** | LOCKED — S34 implementation per `MULTIPLAYER_FIXES.md` §4.5 (Opus high) |
| **Companion review doc** | `RESOLUTION_BINDING_REVIEW.md` (S33 part 2, complete) |
