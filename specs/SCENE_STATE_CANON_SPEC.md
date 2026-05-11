# SCENE_STATE_CANON_SPEC.md

**Status:** v1 draft (S37). Companion review doc `SCENE_STATE_CANON_REVIEW.md` lands in S37b.

**Owner:** Ship 2 — Scene State Canon Discipline, per `MULTIPLAYER_FIXES.md` v3 §5.

**Closes:** Finding A (recursive hallucination memory loop). Anchors Doctrine §76 candidate (Recursive hallucination memory loop / four-property latent-canon test).

**Architectural shape:** Locked in v3 §5. Three subships (2a / 2b / 2c). Recon surfaced no break of the locked shape — three §11 decisions instead.

---

## §1. Problem statement

### §1.1 Finding A recapped

Per `MULTIPLAYER_FIXES.md` Findings, Finding A is the **recursive hallucination memory loop**: the LLM writes a narrative claim into a persisted scene_state field (e.g. `scene_state.location`); the next turn's prompt reads that field back as authoritative context; the LLM treats its own prior fabrication as established canon and elaborates on it; the elaboration writes again. The loop tightens each turn — fabricated detail becomes increasingly load-bearing, and validators downstream cannot distinguish "real" canon (operator-authored skeleton, /travel anchors, deterministic engine state) from LLM-fabricated canon embedded in the same field.

The contamination is **structural**, not behavioral. No prompt-side instruction ("only write what you observed") closes the loop, because the LLM has no read-side handle on which fields are authoritative vs. LLM-laundered. The only durable fix is to remove the LLM's write authority on the field, so the recursion has no surface to write back into.

### §1.2 Three project instances ground Doctrine §76

The four-property test (§3) earns its operational definition from three accumulated project instances:

**Instance 1 — S22 #2 chroma contamination** (`FAILURES.md` §F-40, surfaced live verification pass).
The loot v1.1 directive was emitted into narration, then chroma-indexed alongside DM journals. On the next retrieval, the directive's "AUTHORITATIVE and EXHAUSTIVE" framing returned as context — but **superseded by stale prior loot narration that chroma had already indexed**. The LLM read its own laundered prior loot lines as canonical, ignored the freshest engine-emitted directive, and re-narrated the stale loot. Chroma was acting as the persistence-layer; retrieval was the readback; narrative inference was the LLM's elaboration; loot lines were the LLM-writable surface. Four properties hit. Fix shipped via chroma purge of contaminated docs + AUTHORITATIVE/EXHAUSTIVE override clause. Behavioral fix worked for that incident but did not close the structural loop — it only purged the existing contamination.

**Instance 2 — S32 `scene_state.location` drift** (Finding A's named example).
Operator narrated a Guild Hall scene; subsequent turns drifted into cave imagery, then into a recursive layered cave hallucination. The drift originated in `scene_state.location` — LLM wrote "stone passage" or similar; readback elaborated to "dripping cave"; next readback elaborated to "deeper cavern"; within 3-4 turns the Guild Hall was buried under multiple cave layers. Same four-property loop: location field is LLM-writable (via `extract_scene_updates`), persisted (`dnd_scene_state.location`), retrieved (`build_dm_context` line 5203 renders `Location: ...` in the SCENE STATE block), and narratively inferential (a one-line phrase that the LLM elaborates from at every turn).

**Instance 3 — S36 time-of-day drift** (`project_ship2_drift_evidence.md`, 2026-05-11).
During Ship A live-verify on campaign 17, bot narrated "Evening settles over the merchant market as lanterns flicker..." while engine footer rendered `Exploration · Day 2, Morning`. The narration contradicted authoritative engine state (`dnd_scene_state.day_phase = 'Morning'`, written deterministically via `advance_time()`). The narrative time-of-day did NOT come from a four-property field — `day_phase` is LOCKED against LLM-write — but the **narrative drift was indistinguishable from a four-property leak**. Operator flagged but didn't block testing. The instance demonstrates the cost of leaving narratively-inferential surfaces ungated even when the underlying scalar is engine-bound: the LLM can drift narratively in adjacent prose that no scalar field constrains. This is the read-side analogue of the four-property loop — and tightens the case for structural removal over validator add-ons.

### §1.3 Why structural removal beats validation

A narrative-content validator on LLM output ("does the narration's time-of-day match `day_phase`?") could in principle catch Instance 3. But the validator faces three intrinsic limits:

1. **Surface enumeration**: every narratively-inferential field needs its own detector. Time-of-day has many surface forms (lantern light, dawn chill, twilight, dusk, midnight bell). Location has thousands. Established details has no finite surface.
2. **False-positive calibration**: the validator must distinguish "evening" appearing as flavor text describing a memory or NPC speech vs. "evening" asserting current time-of-day. The line is fuzzy.
3. **Drift accumulation between catches**: even a validator with 95% recall lets 5% of drift through per turn. The loop's compounding nature means 5% drift per turn becomes load-bearing within 10-15 turns.

Structural removal closes the loop at the write side: if the LLM cannot write into a four-property field, the loop has no surface to recurse on. The deletion is one-time, doctrinally clean, and doesn't accumulate residual drift over time.

This is the §76-candidate framing: **when a field hits all four properties of the latent-canon test, structural removal beats validator-on-LLM-output**. The doctrine is the operational definition of "what fields need deleting."

---

## §2. Architectural shape (locked per v3 §5)

Three subships:

### 2a — Delete LLM-write authority on `scene_state.location`

**What:** `extract_scene_updates` no longer writes `location`. The freetext `location` column either drops entirely (reads migrate to JOIN on `dnd_locations.canonical_name` via `current_location_id`) OR survives as a derived/cached field with `set_current_location` extended to write it from the FK'd row. Decision in §11.D1.

**Single writer becomes** `set_current_location` (or location-derived read-time renderer; see D1). LLM cannot write the field directly.

**Effect:** Closes the S32 cave-drift loop structurally. The location surface the LLM reads at prompt-assembly time is bound to authored canon (`dnd_locations` rows, skeleton-origin or operator-curated) or NULL ("between locations" — the LLM is told the party is in transit/wilderness, not given fabricated landmarks to elaborate from).

### 2b — DELETE `established_details` field by default

**What:** Drop the `established_details` column from `dnd_scene_state`. Remove writes in `extract_scene_updates` and `update_scene_state.JSON_LIST_FIELDS`. Remove reads in `build_dm_context` (the `Established details: ...` line in the SCENE STATE block) and the prompt-size telemetry (line 6078 in dnd_engine.py).

**Why deletion not validation:** `established_details` is a pure four-property field — LLM-writable, persisted, retrieved (prominently — the SCENE STATE block renders it as `Established details: <comma-list>`), and narratively inferential (each item is a one-to-six-word phrase that the LLM reads back and elaborates from). There is no narrow surface to validate; the field IS the surface. Validation cannot fix it.

**Exception path:** If recon surfaces a hard dependency that cannot be removed (e.g. retrieval relies on the column for some downstream system that 2c hasn't surfaced), convert to gated-write (Python helper writer, no LLM authority). Recon found NO hard dependency — the column's only readers are `build_dm_context` and the telemetry block, both removable cleanly. **Default path: full deletion.**

### 2c — Audit pass via four-property latent-canon test

**What:** Audit every persisted scalar in `dnd_scene_state` (and adjacent tables flagged in recon, see §1.4) against the four-property test:

1. LLM-writable
2. Persisted
3. Retrieved (read back into LLM prompt context)
4. Narratively inferential

Any field hitting all four is a deletion candidate (or gated-write if hard-dependency, exception path).

**Output:** §6 audit table. Each persisted scalar gets a row with the four properties as columns + a recommendation.

**Scope:** This spec audits `dnd_scene_state` exhaustively. Adjacent tables (`dnd_npcs.description`, `dnd_locations.description`) are flagged as out-of-scope per recon (§13) — they have parser-side writes through gated upsert helpers with skeleton_origin protection AND are not currently pulled into prompt context, so they fail property 1 (LLM-writable via a non-gated path) and property 3 (retrieved into prompt). They surface as filed candidates for a future Ship 3/4/5 audit pass if drift evidence accrues against them.

### §1.4 Locked-shape recon delta

Recon found **no break** of the locked shape. Three sub-decisions surface for §11:

- **D1**: 2a path (freetext-column drop vs. set_current_location-extended writer)
- **D2**: 2c scope (which audit recommendations ship in v1 vs. defer to filed candidates)
- **D3**: adjacent-table audit boundary (in-scope for this ship vs. filed for future)

These are sub-decisions within the locked shape, not architectural alternatives.

---

## §3. Doctrine §76 anchoring

### §3.1 §76 phrasing

**§76. Recursive hallucination memory loop — the four-property latent-canon test**

**Trigger:** Session 32 surfaced `scene_state.location` cave-drift recursion. Session 22 #2 (chroma contamination) and Session 36 (time-of-day narrative drift) were retrospectively identified as instances of the same loop. The pattern earned the test: a persisted scalar field is a latent-canon contamination surface iff it hits all four of:

1. **LLM-writable** — the LLM has a non-gated write path into the field (direct prompt-emitted writes, structured-extraction writes, or laundered through any non-helper write surface).
2. **Persisted** — the field outlives the turn it was written on (stored in a table, not just in-memory turn state).
3. **Retrieved** — the field is read back into a subsequent turn's LLM prompt context (in the system prompt, the user prompt, or retrieval-injected context).
4. **Narratively inferential** — the field's rendered value invites narrative elaboration by the LLM. A one-line phrase ("dripping cave passages"), a comma-list ("torch on the wall, bloodstain by the door"), or a free-text scene change ("the merchants grew suspicious") all qualify. Numeric, mechanical, or strictly tokenized values (HP, mode='combat', day_phase='Morning' as a fixed-enum value rendered into a fixed-template footer) do NOT — they offer no surface for narrative elaboration.

When a field hits all four properties, **structural removal beats validator-on-LLM-output**. Validators have intrinsic limits (surface enumeration, false-positive calibration, drift accumulation between catches). Removing the LLM's write authority closes the loop at the source — the recursion has no surface to feed back into.

### §3.2 Project instances

1. **S22 #2 chroma contamination** (FAILURES.md §F-40) — loot narration laundered through chroma. Four properties: directive-narrated loot lines were LLM-writable (narration), persisted (chroma index), retrieved (per-turn chroma query), narratively inferential (the LLM elaborated loot-related context from indexed prior narration).
2. **S32 `scene_state.location` cave drift** — Guild Hall buried under cave-imagery recursion. Same four properties at the schema layer.
3. **S36 time-of-day drift** (project_ship2_drift_evidence.md) — narrative time-of-day contradicted engine `day_phase`. The narrative drift was indistinguishable from a four-property leak even though the underlying scalar was deterministic. **Third instance**: the read-side analogue tightens the case for structural removal over read-side validators.

### §3.3 Sibling principles

- **§17** — Single write paths per field. §76 generalizes §17's structural-discipline framing to *which fields should have any LLM write path at all*. §17 says "if a field has writes, route them through a helper." §76 says "if a field hits the four-property test, it should not have an LLM write path period."
- **§1a** — LLM never decides mechanical outcomes. §76 extends to narrative canon: the LLM never decides what is established in the world.
- **§2.3** (MULTIPLAYER_FIXES.md) — Structural removal beats validation. §76 is the operational test for which fields qualify.
- **§70** — Fix blast radius can be wider than the bug. §76's deletion is wider than any single drift instance — it pre-empts all future drift on the deleted field.

### §3.4 Anchoring vs. filing

Per §34 (no pre-sequencing) and the existing C1/C2/C3 candidates pattern (DOCTRINE.md tail), §76 lands as a CANDIDATE in the Candidates section when this spec drafts, then promotes to a numbered §76 entry when Ship 2 ships and the structural fix lands. The S36 third instance is the anchoring evidence; Ship 2's shipping is the structural confirmation.

**Drafting note**: §76 candidate text (above) and the three-instance roster get appended to DOCTRINE.md's Candidates section at S37 spec-lock. Anchoring to a numbered §76 entry happens during Ship 2's doc-update pass after live-verify clean.

---

## §4. Ship 2a — Location LLM-write authority deletion

### §4.1 Current state

**Schema:** `dnd_scene_state.location TEXT DEFAULT ''` (dnd_engine.py:327). Schema-level companion: `dnd_scene_state.current_location_id INTEGER DEFAULT NULL` (line 567), FK to `dnd_locations.id`.

**Writers:**
- `extract_scene_updates` (dnd_engine.py:4806-4807): writes from LLM extraction JSON `data.get('location')`.
- `update_scene_state` SCALAR_FIELDS includes `'location'` (line 4705) — admits the write.
- `init_scene_state` (line 1173-1182) seeds `''` on row creation; ON CONFLICT clause preserves existing.

**Readers:**
- `get_scene_state` (line 1128, 1142) — selects and surfaces in dict.
- `build_dm_context` (line 5203) — renders `Location: {scene_state.get('location') or '(not yet set)'}` in SCENE STATE block.
- Prompt-size telemetry (line 6075) — counts char length.
- `test_prompt_size.py:106` — explicitly writes to location in fixture.

**Independent field:** `dnd_scene_state.current_location_id` is a separate column with its own single-writer (`set_current_location`, dnd_engine.py:3826). It is NOT a freetext narrative claim — it's an FK pointer. The current_location_id system is ALREADY single-writer-disciplined; it is the freetext `location` column that has the LLM-write authority.

### §4.2 Path decision (§11.D1)

Two paths preserve the locked shape ("single writer is set_current_location"):

**Path A — Drop the freetext `location` column.** Reads migrate to JOIN on `dnd_locations.canonical_name` via `current_location_id`. `build_dm_context` renders the location label from the joined row. When `current_location_id IS NULL`, the LLM is told the party is "between locations" / "in transit" — a deliberate ambiguity that gives the LLM nothing to elaborate from.

**Path B — Keep the column, extend `set_current_location` to write it.** `set_current_location(campaign_id, location_id)` ALSO writes `dnd_scene_state.location` to the canonical name of the FK'd row (or `''` when location_id is NULL). LLM-write deleted from `update_scene_state.SCALAR_FIELDS`.

**Trade-offs (decision in §11.D1):**

| Concern | Path A (drop column) | Path B (keep, extend writer) |
|---|---|---|
| Schema purity | Column gone — no latent surface | Column survives — small future drift surface if extended-writer regresses |
| Read-site complexity | Adds JOIN to `get_scene_state` / `build_dm_context` | No read-site change — column already present |
| Migration cost | Column-drop migration | One ALTER-statement no-op (column persists), Python helper edit |
| Backward compat with tests | `test_prompt_size.py` fixture write breaks (intentional — its writes are no longer valid) | Same break (the SCALAR_FIELDS removal blocks LLM-write path) |
| Doctrine alignment | Cleaner — §76 says "delete LLM-writable field"; Path A deletes the field itself | Slightly looser — field survives but write authority moves to `set_current_location` (a §17 single-writer) |
| Future risk | None — column doesn't exist | Risk of a future patch re-admitting `location` to SCALAR_FIELDS by mistake |

**Recommended default: Path A (drop column).** Doctrinally cleaner per §76. The read-site JOIN cost is small (one query, already campaign-scoped). The "future regression risk" of Path B (re-admitting `location` to SCALAR_FIELDS) is a real §75-pattern (silent regression on migrated schemas). Confidence: high.

**Surfaced additions during recon:** None beyond D1.

### §4.3 Implementation surface (Path A draft — flip to Path B in S37b if review reverses)

**Code changes:**

1. **`dnd_engine.py` schema migration** (line 325 CREATE TABLE block): drop `location TEXT DEFAULT ''` from new-table schema. Add ALTER TABLE migration to drop the column on existing DBs (SQLite 3.35+ supports `ALTER TABLE ... DROP COLUMN`).
2. **`update_scene_state`** (line 4705): remove `'location'` from `SCALAR_FIELDS`. LLM extraction writes that target `location` are silently dropped (with a log line: `update_scene_state: dropping LLM-write to deleted field 'location'`).
3. **`extract_scene_updates`** (line 4806-4807 + line 4769-4773): remove the `location` field from the extraction prompt schema and the post-extraction `update_kwargs` assignment.
4. **`get_scene_state`** (line 1128, 1142): drop `location` from SELECT and return dict. Add a derived `location_label` field that JOINs `dnd_locations.canonical_name` on `current_location_id`. Return `''` when FK is NULL.
5. **`build_dm_context`** (line 5203): read `scene_state.get('location_label')` instead of `scene_state.get('location')`. Render `'between locations'` (or similar deliberate ambiguity) when empty.
6. **Prompt-size telemetry** (line 6075): swap key from `location` to `location_label`.
7. **`init_scene_state`** (line 1173-1182): drop `location` from INSERT column list.
8. **Tests** (test_prompt_size.py:106, test_commitment_directive.py:307-318): drop `location` from fixture writes. Migrate to `set_current_location(campaign_id, location_id)` for tests that need location context.

**Renaming note:** consider renaming the derived read-time field from `location` to `location_label` to make it grep-distinct from the deleted column. Decision filed in §11.D1 sub-decision (low-cost cosmetic).

### §4.4 Migration path

- Drop column via ALTER TABLE (SQLite 3.35+). For older SQLite, fall back to the table-rebuild pattern (CREATE TABLE _new, INSERT SELECT, DROP, RENAME) — added to migration block.
- Drop happens in the schema-init function alongside the existing ALTER ADD COLUMN migrations.
- No data loss concern: the freetext `location` content is by definition contaminated (the loop's whole problem). Authored location names live in `dnd_locations`.

### §4.5 Test surfaces

- `test_dnd_locations.py` — existing tests on `set_current_location` still pass (it doesn't touch the freetext column either way).
- `test_prompt_size.py` — update fixture to not write `location`; use `set_current_location` for location context.
- `test_commitment_directive.py` — same fixture migration.
- New tests:
  - **test_scene_state_location_deletion.py** — assert `update_scene_state(campaign_id, location='X')` no-ops (log line confirms drop). Assert `get_scene_state` returns no `location` key (or asserts `location_label` is the joined value).
  - **test_extract_scene_updates_drops_location.py** — patch the LLM call to return `{"location": "X"}`, assert no `dnd_scene_state.location` row mutation.

---

## §5. Ship 2b — `established_details` deletion (default path)

### §5.1 Current state

**Schema:** `dnd_scene_state.established_details TEXT DEFAULT '[]'` (dnd_engine.py:330). Stored as JSON list of strings.

**Writers:**
- `extract_scene_updates` (line 4812-4813): appends `data.get('new_established_details')` to the existing list via `update_scene_state`.
- `update_scene_state` JSON_LIST_FIELDS includes `'established_details'` (line 4704) — admits and de-dupes against existing entries, caps at 20.

**Readers:**
- `get_scene_state` (line 1145): parses JSON, surfaces as list.
- `build_dm_context` (line 5180, 5206): `details = scene_state.get('established_details') or []`; renders as `Established details: {', '.join(details) if details else '(none yet)'}` in SCENE STATE block.
- Prompt-size telemetry (line 6078): sums char length of list items.
- `init_scene_state` (line 1174-1177): seeds `'[]'`.

**Test references:**
- `test_commitment_directive.py:308,317` — fixture writes (drop column-name from list).
- `test_time_skeleton_seed.py:33` — column in test schema (mirror schema change).
- `test_prompt_size.py:107` — fixture write of `established_details=?` value.

### §5.2 Decision: deletion vs. gated-write

The Ship 2 prompt locks the default to deletion. Recon evaluated whether a hard dependency forces gated-write — none found. **Confirmed: deletion is the default path.**

The field is a textbook four-property hit: LLM-writable (append path through extract), persisted (column), retrieved (rendered prominently in SCENE STATE block), narratively inferential (one-to-six-word phrases the LLM elaborates from).

No reader requires the column for non-narrative purposes. The build_dm_context line is the sole readback site. Telemetry counts chars (will count 0 after deletion). No downstream system depends on it.

### §5.3 Implementation surface

1. **`dnd_engine.py` schema** (line 330): drop `established_details TEXT DEFAULT '[]'` from CREATE TABLE.
2. **ALTER TABLE migration**: DROP COLUMN `established_details` (or table-rebuild fallback for older SQLite).
3. **`update_scene_state`** (line 4704): remove `'established_details'` from `JSON_LIST_FIELDS`. Add to a deletion-log table (silent drop with log line: `update_scene_state: dropping LLM-write to deleted field 'established_details'`).
4. **`extract_scene_updates`** (line 4766, 4771, 4812-4813): drop the `established_details` context line from the extraction prompt; drop `new_established_details` from the JSON schema; drop the post-extraction assignment.
5. **`get_scene_state`** (line 1128, 1145): drop from SELECT and return dict.
6. **`build_dm_context`** (line 5180, 5206): drop the `details = ...` assignment and the `Established details: ...` rendered line. The SCENE STATE block tightens by one line.
7. **Prompt-size telemetry** (line 6078): drop the established_details summation.
8. **`init_scene_state`** (line 1174-1177): drop from INSERT column list.
9. **Tests**: drop the column from `test_commitment_directive.py:308,317`, `test_time_skeleton_seed.py:33`, `test_prompt_size.py:107`. New test asserts no write path lands content into a persisted store.

### §5.4 What replaces the function the field served

`established_details` was meant to give the LLM a memory anchor — "here are the details we agreed exist in this scene." Removing it means the LLM has no per-turn list of canonical scene details.

**Replacement strategies (read-side, not new fields):**
1. **Skeleton-loaded details** — authored canonical details live in `dnd_locations.description` and skeleton-origin NPC descriptions; these flow into build_dm_context already through location-scoped retrieval.
2. **Recent narration window** — `last_dm_response` (single-writer-disciplined) gives the LLM its own prior turn's narration verbatim; that's the actual memory of "what we just established."
3. **Operator authority** — when a detail needs to persist, operator adds it to a skeleton or uses a future "/canonize" command (filed candidate; not Ship 2 scope).

The deletion accepts that per-turn LLM-summarized scene details were the contamination surface. The legitimate canon flows in via skeleton + recent-narration paths that have single-writer discipline.

### §5.5 Test surfaces

- Existing scene_state tests update column lists.
- New test: `test_established_details_deletion.py` — assert column absent from schema, assert LLM-write path no-ops, assert `build_dm_context` output does NOT contain the string `"Established details:"` line.

---

## §6. Ship 2c — Audit pass via four-property latent-canon test

### §6.1 Audit table (load-bearing artifact)

Every persisted scalar in `dnd_scene_state` is audited below. Adjacent tables are flagged at §6.3.

**Legend:**
- ✅ = property hits
- ❌ = property does not hit
- ⚠️ = property partially or contextually hits — see notes
- **4/4** = full four-property hit, deletion candidate
- **3+1** = three hard hits + one borderline; flagged for §11 decision

| # | Column | LLM-writable | Persisted | Retrieved | Narratively inferential | Hits | Recommendation |
|---|--------|:---:|:---:|:---:|:---:|:---:|---|
| 1 | `campaign_id` | ❌ | ✅ | ✅ | ❌ | 2/4 | KEEP (key, not narrative) |
| 2 | `location` (freetext) | ✅ via extract | ✅ | ✅ (line 5203) | ✅ | **4/4** | **DELETE — Ship 2a target** |
| 3 | `mode` | ❌ LOCKED | ✅ | ✅ (line 2622, 5562) | ❌ (mechanical enum) | 2/4 | KEEP |
| 4 | `focus` | ✅ via extract | ✅ | ✅ (line 5204) | ✅ | **4/4** | **DELETE — surfaced by audit; §11.D2** |
| 5 | `established_details` | ✅ via extract append | ✅ | ✅ (line 5180,5206) | ✅ | **4/4** | **DELETE — Ship 2b target** |
| 6 | `active_npcs` | ❌ LOCKED | ✅ (dead) | ❌ (deprecated, line 5182 derives from dnd_npcs.last_mentioned) | n/a | dead column | DROP DEAD COLUMN (separate housekeeping) |
| 7 | `active_threats` | ❌ LOCKED | ✅ (dead) | ❌ (line 5185: "schema column kept; defer until threat model exists") | n/a | dead column | DROP DEAD COLUMN (separate housekeeping) |
| 8 | `open_questions` | ✅ via extract append | ✅ | ✅ (line 5208) | ✅ | **4/4** | **DELETE — surfaced by audit; §11.D2** |
| 9 | `tension` (legacy string) | ❌ LOCKED (deterministic) | ✅ (dead) | ❌ (replaced by tension_int in line 5205) | ❌ | dead column | DROP DEAD COLUMN (separate housekeeping) |
| 10 | `last_player_action` | ⚠️ always-set by extract, content = verbatim player input | ✅ | ✅ (line 5209) | ⚠️ — content is player's own words, not LLM-inferred narrative claim | **3+1** | KEEP — write is laundered-through-LLM but content is verbatim player input (not narratively inferred); the contamination loop requires LLM-inferred narrative content, not player-typed input |
| 11 | `last_scene_change` | ✅ via extract | ✅ | ✅ (line 5210) | ✅ ("one short sentence" per extract prompt line 4773) | **4/4** | **DELETE — surfaced by audit; §11.D2** |
| 12 | `updated_at` | ❌ helper | ✅ | ❌ | ❌ | 1/4 | KEEP (metadata) |
| 13 | `tension_int` | ❌ LOCKED (set_tension etc.) | ✅ | ✅ (line 5205) | ❌ (integer) | 2/4 | KEEP |
| 14 | `progress_clocks` | ❌ LOCKED (set_clocks) | ✅ | ✅ (line 5212) | ❌ (structured JSON, mechanical) | 2/4 | KEEP |
| 15 | `current_location_id` | ❌ LOCKED (set_current_location) | ✅ | ✅ (line 5190) | ❌ (FK integer) | 2/4 | KEEP |
| 16 | `turn_counter` | ❌ LOCKED (increment_turn_counter) | ✅ | ✅ | ❌ | 2/4 | KEEP |
| 17 | `last_dm_response` | ⚠️ content = LLM narration verbatim, but write path is deterministic (update_last_dm_response single-writer); read-side is for commitment-directive matching, not narrative elaboration | ✅ | ✅ (commitment) | ⚠️ — content originated as LLM, but readback is for deterministic verb-heuristic matching not narrative inference | **3+1** | KEEP — single-writer-disciplined, readback target is the commitment-directive deterministic matcher not the narrative-elaboration LLM call |
| 18 | `last_active_actor` | ❌ LOCKED (update_last_active_actor) | ✅ | ✅ | ❌ (actor name from canonical store) | 2/4 | KEEP |
| 19 | `campaign_day` | ❌ LOCKED (advance_time) | ✅ | ✅ (line 2629) | ❌ (integer) | 2/4 | KEEP |
| 20 | `day_phase` | ❌ LOCKED (advance_time) | ✅ | ✅ (line 2630) | ❌ (fixed enum: Morning/Midday/Evening/Night/Late Night) | 2/4 | KEEP (but see §6.2 read-side analogue note) |

### §6.2 Read-side analogue note: S36 time-of-day drift

S36's drift instance (project_ship2_drift_evidence.md) demonstrates that even a fully-locked field (`day_phase`) can be drifted-against in narrative prose adjacent to its rendered value. The four-property test catches the **write-side loop**; the time-of-day drift is a **read-side narrative drift** that no four-property field caused.

This is intentionally OUT-OF-SCOPE for Ship 2 (which is structural-write-side discipline). The S36 drift evidence supports the §76 doctrine framing (validators have intrinsic limits even on read-side prose) but does not surface a new field deletion target. Future Ship 4/5 (narrative verifier on time/place adjacency) could close the read-side analogue; filed candidate, not committed.

### §6.3 Adjacent tables (recon-flagged, scoped OUT of this ship)

**`dnd_npcs.description`** (TEXT DEFAULT ''):
- Written by `npc_upsert` (dnd_engine.py:2909-2985) with skeleton_origin protection (skeleton_origin=1 rows never overwritten by parser hits).
- Parser-side writes happen via deterministic regex extraction in the NPC mention parser; not LLM-rephrased.
- Currently NOT read into build_dm_context's scene_state section (line 5191-5200 surfaces only NPC NAMES via `get_recently_active_npcs`, not descriptions).
- **Four-property hits: write=⚠️ (gated upsert with skeleton protection), persisted=✅, retrieved=❌ (not in prompt), narrative=✅.** Fails property 3.
- Recommendation: **OUT OF SCOPE for Ship 2.** Filed as candidate for future audit if drift evidence accrues against NPC descriptions surfacing in narration.

**`dnd_npcs.origin_excerpt`** (TEXT DEFAULT ''):
- Capped at 100 chars (line 2916). Set on first mention; one-shot context anchor.
- Not currently in scene-state-section retrieval.
- Same OUT-OF-SCOPE recommendation; filed candidate.

**`dnd_locations.description`** (TEXT DEFAULT ''):
- Written by `location_upsert` (dnd_engine.py:3561) with skeleton_origin protection.
- Parser-side writes deterministic.
- Retrieved into prompt context via location-scoped chroma retrieval, not via scene_state direct read.
- **Indirect retrieval path** — chroma-mediated, not scene_state-direct. Filed candidate; out of scope.

**`dnd_locations.origin_excerpt`** (TEXT DEFAULT ''):
- Same shape as NPC origin_excerpt. Out of scope.

**Other tables surveyed** (`dnd_consequences`, `dnd_inventory`, `dnd_loot_pending`, `dnd_quests`, `dnd_combat_state`, `dnd_combatant_state`, `dnd_pending_roll_directives`, `dnd_time_advancements`): all have gated single-writer helpers per §17 with parser-side or operator-side write paths. None hit all four properties. No deletion candidates.

### §6.4 Audit summary

**Ship 2 v1 deletion targets** (4/4 hits):
- `location` (2a — already locked)
- `established_details` (2b — already locked)
- `focus` (surfaced by audit — §11.D2 decision: ship in v1 or defer)
- `open_questions` (surfaced by audit — §11.D2)
- `last_scene_change` (surfaced by audit — §11.D2)

**Dead column housekeeping** (out of Ship 2 scope but flagged for ROADMAP filing):
- `active_npcs`, `active_threats`, `tension` — schema-present, never read, deprecated by replacement fields or by render-time derivation.

**Borderline 3+1 hits — keep with rationale documented in audit table**:
- `last_player_action` (verbatim player input, not LLM-narrative)
- `last_dm_response` (single-writer, deterministic readback)

**Out-of-scope adjacent surfaces** (filed candidates for future ships):
- `dnd_npcs.description`, `dnd_npcs.origin_excerpt`, `dnd_locations.description`, `dnd_locations.origin_excerpt`

---

## §7. Migration path

### §7.1 Column drops (default Path A for 2a + 2b + §11.D2-yes for focus/open_questions/last_scene_change)

Targeted columns to DROP from `dnd_scene_state`:

| Column | Ship | SQLite drop strategy |
|---|---|---|
| `location` | 2a | ALTER TABLE ... DROP COLUMN (3.35+) or table-rebuild fallback |
| `established_details` | 2b | Same |
| `focus` | 2c (D2) | Same |
| `open_questions` | 2c (D2) | Same |
| `last_scene_change` | 2c (D2) | Same |
| `active_npcs` | housekeeping (filed; not Ship 2) | Same |
| `active_threats` | housekeeping (filed; not Ship 2) | Same |
| `tension` (legacy) | housekeeping (filed; not Ship 2) | Same |

Drops happen in a single migration block at module init, alongside existing ALTER ADD COLUMN migrations. The migration is idempotent — checks `PRAGMA table_info` before issuing DROP.

### §7.2 Code removals

`dnd_engine.py`:
- Line 325-338 CREATE TABLE block: tighten to keep only non-deleted columns.
- Line 1120-1162 `get_scene_state`: tighten SELECT list and return dict.
- Line 1165-1185 `init_scene_state`: tighten INSERT column list.
- Line 4692-4746 `update_scene_state`: shrink SCALAR_FIELDS and JSON_LIST_FIELDS.
- Line 4749-4818 `extract_scene_updates`: tighten extraction prompt schema, tighten post-extraction `update_kwargs`.
- Line 5180-5215 `build_dm_context` scene_state_section: drop deleted-field rendering lines.
- Line 6075-6083 prompt-size telemetry: tighten key list.

### §7.3 Test updates

- `test_commitment_directive.py:307-318` — fixture INSERTs: drop deleted columns from VALUES tuple.
- `test_time_skeleton_seed.py:33` — schema declaration: drop deleted columns.
- `test_prompt_size.py:106-107` — fixture UPDATE: drop deleted columns from SET clause.
- `test_dm_respond_arbitration.py:97,105` — patches assume `extract_scene_updates` and `get_scene_state` exist; signatures unchanged so patches still work, but assertion structure may need light updates if it inspects extracted fields.

### §7.4 Compatibility considerations

- **No backward-compatibility shim needed**: per CLAUDE.md guidance + §62 (no half-finished implementations), the deletion is structural. Existing campaigns lose the columns; their stale narrative content is by definition contaminated (the loop's whole problem).
- **No re-render path**: deleted columns' content is not recoverable, but also not desired — the contamination was the content.
- **Skeleton-loaded canon preserved**: `dnd_locations.description`, skeleton-origin NPC descriptions, operator-authored quest summaries — these are out-of-scope and untouched. The legitimate canon flows through these channels.

---

## §8. Test plan

### §8.1 New tests

**`test_scene_state_canon_deletion.py`** — primary 2a/2b/2c integration test:
- Schema assertion: after init, deleted columns absent from `PRAGMA table_info(dnd_scene_state)`.
- Write-path assertion: `update_scene_state(campaign_id, location='X', established_details=['Y'], focus='Z', open_questions=['W'], last_scene_change='V')` no-ops on all deleted fields; log lines confirm drops.
- Read-path assertion: `get_scene_state(campaign_id)` returned dict does not contain any of the deleted keys. Renders `location_label` (Path A) derived from `current_location_id`.
- `build_dm_context` output assertion: SCENE STATE block does NOT contain `'Location:'` (Path A renames to `'Location:'` rendered from FK-joined label, OR the SCENE STATE block deliberately omits the line when `current_location_id` is NULL). Does NOT contain `'Established details:'`, `'Focus:'`, `'Open questions:'`, `'Last scene change:'`.

**`test_extract_scene_updates_canon_deletion.py`**:
- Patch the `route` function to return a JSON body containing all deleted-field keys (`location`, `focus`, `new_established_details`, `new_open_questions`, `last_scene_change`).
- Call `extract_scene_updates(campaign_id, player_action, dm_response)`.
- Assert `dnd_scene_state` row has no mutation in deleted fields (none exist post-deletion; PRAGMA query confirms).
- Assert log line `update_scene_state: dropping LLM-write to deleted field` fires for each attempt.

**`test_doctrine_76_four_property_audit.py`** (audit-pass regression test):
- Programmatically enumerate every column in `dnd_scene_state` (PRAGMA), every writer, every reader.
- Assert no column hits all four properties post-Ship-2 (i.e., the audit is "clean" at shipped state).
- If a future ALTER TABLE adds a new column that hits 4/4, this test fails loud, forcing operator to decide deletion vs. gated-write at add-time.
- Strategy: lookup writers by `_LLM_WRITABLE_COLUMNS` constant (added to dnd_engine.py at Ship 2 ship); lookup readers by grep against build_dm_context output.

### §8.2 Existing test updates

- `test_commitment_directive.py` — fixture column list shrinks.
- `test_time_skeleton_seed.py` — fixture schema shrinks.
- `test_prompt_size.py` — fixture UPDATE column list shrinks.
- `test_dnd_locations.py` — no changes needed; already exercises set_current_location only.
- `test_travel_persistence.py` — no changes needed.

### §8.3 Regression suite assertion

Post-Ship-2 full-suite pass: all existing scene_state tests pass after fixture updates; new tests pass; no flake.

---

## §9. Live-verify scenarios

### Scenario A — Location LLM-write attempt no-ops (2a)
**Setup**: campaign with `set_current_location` set to authored `'The Guild Hall'` (FK).
**Action**: operator types `"I look around the Guild Hall"`.
**Expected (post-Ship-2)**:
- LLM narrates Guild Hall scene.
- `extract_scene_updates` thread fires post-turn; its prompt no longer requests `location` updates.
- Even if the LLM hallucinates a `"location": "stone passage"` write, `update_scene_state` drops it; log line confirms.
- `dnd_scene_state.current_location_id` unchanged (FK to Guild Hall row).
- Next turn's prompt renders `Location: The Guild Hall` (from FK JOIN, Path A) — NOT `stone passage`.
- Cave drift is structurally impossible: there is no LLM-writable freetext location surface to recurse on.

### Scenario B — `established_details` LLM-write attempt no-ops (2b)
**Setup**: campaign at fresh scene.
**Action**: operator types `"I examine the room carefully"`. LLM narrates "the room has a torch on the wall, a bloodstain by the door, and an open chest."
**Expected**:
- `extract_scene_updates` runs; its prompt no longer requests `new_established_details`.
- Even if LLM emits `["torch on the wall", "bloodstain by the door", "open chest"]`, `update_scene_state` drops the write; log confirms.
- Next turn's prompt's SCENE STATE block does NOT contain `'Established details:'` line.
- LLM's memory of the scene relies on `last_dm_response` (verbatim prior narration) and skeleton-loaded canon, not laundered self-summary.

### Scenario C — Cross-turn drift resistance (combined 2a+2b)
**Setup**: 5-turn play sequence with operator-narrated Guild Hall + several elaborated details.
**Action**: 5 turns of action; each turn the LLM is free to elaborate.
**Expected**:
- Each turn's SCENE STATE block renders identical authored canon (`Location: The Guild Hall` from FK; no `Established details` line).
- LLM does NOT recursively elaborate on prior-turn fabrications because no scene_state field stores LLM-summarized prior fabrications.
- Drift detection: grep narration across the 5 turns for cave-imagery / contradictory-location phrases. None expected. (Note: read-side adjacent narrative drift like S36 time-of-day is OUT OF SCOPE — closed by future Ship 4/5 narrative verifier.)

### Scenario D — /travel-only authority on location (2a)
**Setup**: campaign at Guild Hall.
**Action**: operator types `/travel "Rusty Anchor"` (assuming canonical location exists).
**Expected**:
- `set_current_location` writes new FK.
- Next turn's prompt renders `Location: The Rusty Anchor`.
- LLM-emit writes to `location` field still no-op (gone or gated).
- The /travel command is the operator-driven write path.

### Scenario E — `focus`/`open_questions`/`last_scene_change` deletion (2c if D2-yes)
**Setup**: campaign with active narrative.
**Action**: operator plays through a scene-change moment.
**Expected (if D2-yes)**:
- SCENE STATE block omits `Focus:`, `Open questions:`, `Last scene change:` lines.
- LLM's narrative continuity relies on `last_dm_response` and recent turn-window in chat context, not laundered scene-state summaries.
- Drift on these surfaces: structurally impossible post-deletion.
**Expected (if D2-defer)**:
- Lines persist; drift may continue on these surfaces. Filed for Ship 3/4/5.

### Scenario F — Four-property audit test (2c regression)
**Setup**: developer runs `test_doctrine_76_four_property_audit.py` regression test.
**Expected**:
- Test enumerates all `dnd_scene_state` columns.
- For each column, asserts at least one of the four properties FAILS.
- Test passes (no 4/4 hits remain).
- If a future schema migration re-introduces a 4/4 column, test fails loud at the migration's commit.

---

## §10. Telemetry

### §10.1 New log lines

- `scene_canon: dropped LLM-write to deleted field '<field>'` — fires from `update_scene_state` per drop. Diagnostic for confirming LLM emissions are being neutralized.
- `scene_canon: schema audit clean (post-Ship-2)` — fires once at module init after migration completes; structural confirmation log.

### §10.2 Removed log lines

- `scene state updated: ['established_details', 'focus', ...]` (dnd_engine.py:4818) — narrows to remaining writable fields only.
- Prompt-size telemetry per-field `scene_chars` accounting (line 6075-6083): drops removed-column keys.

### §10.3 Metrics to watch post-ship

- **Drift incidents**: zero on `location` and `established_details` surfaces in 30 turns of natural play (vs. S32's 3-4 turn cave-drift accrual baseline).
- **Prompt size**: SCENE STATE block char count drops by the removed lines' average length (rough estimate: 80-200 chars per turn).
- **Log volume**: `scene_canon: dropped` log lines fire roughly equal to pre-ship `scene state updated` per-turn frequency. If LLM stops attempting writes (because the extraction prompt no longer requests them), counts trend toward zero — desired.

---

## §11. Decision points

Decisions surfaced by recon. Each gets: question, options, recommended default, confidence, trade-offs.

### §11.D1 — Path for 2a location-column treatment

**Question:** Drop the freetext `location` column entirely (Path A) or keep it and extend `set_current_location` to write it from the FK (Path B)?

**Options:**
- A: Drop column; reads JOIN on `dnd_locations.canonical_name` via `current_location_id`.
- B: Keep column; `set_current_location` becomes its single writer, derives value from FK'd row.

**Recommended default:** **Path A (drop column).**

**Confidence:** High.

**Trade-offs:**
- A is doctrinally cleaner (§76 says delete the field, not just gate it).
- A removes a future regression surface (no risk of `location` re-entering SCALAR_FIELDS by mistake — the §75 pattern).
- B has cheaper read-site migration (no JOIN added) but higher migration cost (extend writer + edge cases on NULL FK).
- A's read-site JOIN cost is minor (single campaign-scoped query, already cached in `get_scene_state` shape).

**Sub-decision:** rename the derived read-side field from `location` to `location_label` (grep-distinct from deleted column). Recommended yes; low-cost cosmetic; confidence high.

### §11.D2 — Scope of 2c deletions: ship in v1 or defer

**Question:** The 2c audit surfaced THREE additional 4/4 hits beyond `established_details`: `focus`, `open_questions`, `last_scene_change`. Ship all in v1, ship some, or defer all to filed candidates?

**Options:**
- D2-all: Ship all three in v1. Spec scope is now Ship 2 = 5 column deletions total (location + established_details + focus + open_questions + last_scene_change).
- D2-some: Ship one or two (e.g., the most evidently-drifted; recon found no specific drift evidence on the three; equal priority).
- D2-defer: Ship only the locked-shape targets (location, established_details); defer focus/open_questions/last_scene_change to filed candidates pending drift evidence.

**Recommended default:** **D2-all (ship all five deletions in v1).**

**Confidence:** Medium-high.

**Trade-offs:**
- D2-all is structurally consistent with §76: if a field hits 4/4, structural removal beats validation. The audit produces the recommendation; the audit's job is to surface candidates. Deferring known-4/4 hits weakens the doctrine's operational definition.
- D2-defer is the conservative path — wait for drift evidence per S22/S32/S36 precedent before deleting. But the §76 doctrine itself argues this is the validator's-limit trap: drift accumulates between detections. Pre-emptive deletion of audited 4/4 fields is the structural play.
- D2-some splits the difference and surfaces a hard-to-justify ordering question (which of three equally-rated fields ships first).
- D2-all increases the live-verify burden (5 deletions to walk through) but the deletions are mechanically identical — same migration shape, same write-path neutralization, same readback removal.
- **Reversibility:** if D2-all causes a regression (e.g., LLM narration coherence degrades because `last_scene_change` was a meaningful continuity anchor and `last_dm_response` doesn't fill the gap), reverse by re-introducing the field via ALTER ADD with deterministic single-writer (operator-driven /canonize, /focus, /scenechange commands; not LLM-write). The reversal does NOT restore LLM-write authority — it converts the field to gated-write.

**Sub-decision considerations:**
- The `focus` field's read site (`Focus: ...` line in SCENE STATE block) is currently used by the LLM as a "what is the party paying attention to right now" anchor. If deleted, the LLM relies on `last_dm_response` and the player's recent action. Operator may want to evaluate whether the loss is meaningful in live-verify.
- The `open_questions` field renders as a JSON list; same elaboration surface as `established_details`. Strongest 4/4 case after `established_details` itself.
- The `last_scene_change` field renders as "one short sentence" per extraction prompt — pure narrative inference surface. Strong 4/4 case.

### §11.D3 — Adjacent-table audit boundary

**Question:** Should the 2c audit pass include `dnd_npcs.description`, `dnd_npcs.origin_excerpt`, `dnd_locations.description`, `dnd_locations.origin_excerpt` in this ship, or defer to future filed candidates?

**Options:**
- D3-include: extend audit to adjacent tables; ship deletions/gates if any hit 4/4.
- D3-defer: keep adjacent tables OUT of Ship 2 scope; file as candidates for future audit if drift evidence accrues.

**Recommended default:** **D3-defer.**

**Confidence:** High.

**Trade-offs:**
- D3-defer is the locked-shape default per the Ship 2 prompt ("Audit every persisted scalar in dnd_scene_state and adjacent tables" — adjacent tables flagged at §6.3 fail at least one property, primarily retrieval-into-prompt).
- The NPC/location description fields go through gated upsert helpers with skeleton_origin protection — they have partial gating already. Full LLM-write authority is NOT present.
- Their content is NOT pulled into the SCENE STATE block; chroma-mediated retrieval is the indirect path.
- D3-include expands Ship 2 significantly without clear evidence accrual. Per §34 (no pre-sequencing), file as candidate; re-decide after Ship 2 ships and any natural-play drift on those surfaces is logged.

### §11.D4 — Dead-column housekeeping bundling

**Question:** Ship the dead-column drops (`active_npcs`, `active_threats`, `tension` legacy) bundled with Ship 2, or file separately?

**Options:**
- D4-bundle: drop the dead columns alongside Ship 2 deletions. Same migration block, same review burden.
- D4-separate: file as a housekeeping ROADMAP item; ship separately.

**Recommended default:** **D4-bundle** (low marginal cost; same migration shape).

**Confidence:** Medium.

**Trade-offs:**
- D4-bundle adds 3 trivial column drops to the same migration; review burden is minimal.
- D4-separate keeps Ship 2 doctrinally pure (only four-property deletions, not housekeeping mixed in). Doctrinal-cleanliness optic.
- The bundling decision is purely cosmetic — both options ship the same deletions.

---

## §12. Doctrine candidates filed / anchored

### §12.1 §76 candidate filed (this spec)

**Recursive hallucination memory loop / four-property latent-canon test.** Drafted phrasing in §3.1; three project instances (S22 #2 / S32 / S36) in §3.2. Status at S37 spec lock: FILED CANDIDATE in DOCTRINE.md Candidates section. Anchors to numbered §76 entry when Ship 2 ships and live-verify confirms structural closure.

### §12.2 Sibling candidate updates

**C1 (Engine-computed binding > validator-on-LLM-output)** — Ship 2 does NOT add a fourth instance to C1 directly (Ship 2 is write-side structural deletion, not engine-computed binding). However, §76's framing reinforces C1's underlying principle (structural fix over validator). Cross-reference C1 ↔ §76 added in DOCTRINE update.

**C3 (Single-writer compatible with multiple disjoint trigger surfaces)** — Ship 2a Path A removes the freetext `location` column entirely; the "single writer" framing collapses to "no writer needed, derived field." Ship 2a Path B would surface a second C3 instance (set_current_location as single writer, /travel and skeleton-loader as disjoint trigger surfaces — already true today; Path B keeps the shape). Recommended Path A means C3 does not gain a Ship 2 instance.

### §12.3 No new candidates filed

Ship 2 does not surface new candidate doctrines beyond §76. The work is structural-deletion application of §76, not architectural novelty.

---

## §13. Out-of-scope

Explicitly excluded from Ship 2:

1. **Read-side narrative drift (S36 time-of-day type)**: closed by future Ship 4/5 narrative verifier, not by structural deletion. Filed candidate.
2. **Adjacent tables** (`dnd_npcs.description`, `dnd_npcs.origin_excerpt`, `dnd_locations.description`, `dnd_locations.origin_excerpt`): partial gating already; not retrieved into SCENE STATE block; filed candidate per §11.D3.
3. **Chroma layer audit**: S22 #2's instance was at the chroma indexing layer. Chroma-side hygiene is its own ship (`F-40` close was partial — chroma purge + AUTHORITATIVE clause). Filed candidate.
4. **`/canonize`-style operator-driven write commands**: replacing `established_details` LLM-write with operator-curated detail entries. Useful future surface; out of Ship 2 scope.
5. **Skeleton-loader expansion**: increasing the canonical detail coverage in skeleton files to reduce reliance on per-turn scene_state details. Out of scope.
6. **Ship 3 (NPC State-Sync Boundary)** and **Ship 4/5 (further multiplayer fixes)**: separate shipping cycles, separate specs.
7. **Backward-compatibility shims** for old campaign data: per CLAUDE.md, no shims. Deleted columns' content is by definition contaminated; not recoverable, not desired.
8. **Read-time JOIN performance optimization**: Path A adds one campaign-scoped JOIN to `get_scene_state`. Performance is not load-bearing at current scale; optimization filed as candidate if logs surface latency.

---

## Tabular handoff (S37)

| Item | Status |
|---|---|
| Spec file | `/home/jordaneal/virgil-docs/specs/SCENE_STATE_CANON_SPEC.md` |
| Spec version | v1 draft (S37) |
| Companion review | `SCENE_STATE_CANON_REVIEW.md` to draft in S37b |
| Decisions surfaced | 4 (§11.D1, D2, D3, D4) |
| Recon HALT escalations | 0 |
| Doctrine candidates | §76 filed (3 project instances; anchors when Ship 2 ships) |
| Subships planned | 2a (location deletion), 2b (established_details deletion), 2c (audit pass — D2 surfaces 3 additional 4/4 fields) |
| Out-of-scope filed | 8 items (§13) |
| Load-bearing artifact | §6.1 four-property audit table (20 rows, 5 hits, 3 dead-column housekeeping) |
| Ready for review | YES — S37b can proceed |
| Code changes in this session | NONE (spec only per locked operator pattern) |

**Confidence on shipping shape:** high. The locked architectural shape held under recon; the four-property test produced clear deletion recommendations; the §11 decisions are well-bounded sub-questions with recommended defaults.

**Next session:** S37b review pass on this spec, then S38 implementation of Ship 2 (subship ordering: 2a → 2b → 2c-bundle, or all-at-once per D4 bundling recommendation).
