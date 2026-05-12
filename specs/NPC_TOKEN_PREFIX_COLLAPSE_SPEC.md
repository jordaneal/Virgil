# NPC Token-Prefix Collapse Against Unique Skeleton Anchors — Design Spec v1 (LOCKED)

**Status:** LOCKED v1 — review complete (NPC_TOKEN_PREFIX_COLLAPSE_REVIEW.md). §11 decisions locked in this header pass. Implementation ship (Sx) in flight.
**Pattern:** Write-path identity refinement (single-write-path doctrine §17 preserved — the amendment refines the existing upsert decision, doesn't add a new write path)
**Track:** Doctrine amendment to PHASE_12_SPEC §9.1 strict-literal-matching rule
**Failure mode this targets:** LLM narration emits short-form names ("Eldrin" instead of "Eldrin Stormbow"); strict-equality `WHERE canonical_name=?` lookup misses the canonical row; INSERT branch creates a bare-firstname row; per-turn `mention_count + last_mentioned` increments accumulate on the wrong row; `get_recently_active_npcs` (ORDER BY `last_mentioned DESC`) surfaces the bare-firstname row to the prompt; LLM keeps emitting short form → ~9× concentration over 12 days of play in campaign 17 (S46 recon).
**External review convergence:** ChatGPT + Gemini (S46 brief) both landed on this fix-shape with skeleton-anchor-only constraint as the safety boundary.

---

## Locked doctrine amendment (V1, operator-locked verbatim — spec converges on this)

> Strict literal matching remains the default identity rule. Exception: deterministic whole-token prefix collapse is permitted only when the incoming canonical_name matches a unique `skeleton_origin=1` row's leading whole-token within the same `campaign_id`. If multiple `skeleton_origin=1` rows in the same campaign share the leading whole-token, no collapse occurs; insert proceeds normally and ambiguity telemetry is logged.

Four named constraints lock the rule's surface area: **unique anchor / skeleton_origin=1 / same campaign_id / whole-token.** Spec must not broaden or weaken any of the four. Any drafting case where the locked language seems insufficient is escalated as HALT, not paraphrased.

---

## 1. Decisions Code locks confidently (no operator review needed)

These are defaults Code commits to without review surface. Each is a direct consequence of the locked amendment + existing engine doctrine (single write path §17, parser-can't-overwrite-skeleton §14) and has no plausible alternative that doesn't violate one of those.

1. **Implementation location: inside `npc_upsert` at `dnd_engine.py`.** The amendment refines the write path; it does not add a new one. PHASE_12_SPEC §17 (single write paths per field) is preserved. No new public function, no new caller.

2. **Lookup ordering: unique-skeleton-anchor lookup runs BEFORE existing strict-equality lookup at line 2981.** Early-exit semantics — if a unique skeleton anchor matches, route directly to that row's UPDATE branch (parser×skeleton skeleton-lock path at lines 3041–3045) and do not fall through to the existing INSERT branch. If no anchor matches OR the anchor is ambiguous, fall through unchanged — existing strict-equality lookup at 2981 runs as today, and existing INSERT/UPDATE branches behave identically to current code.

3. **skeleton_origin preservation on collapse.** The canonical (skeleton_origin=1) row's `skeleton_origin` flag is never touched on a token-prefix-collapse update. Only `mention_count` (incremented by 1) and `last_mentioned` (set to current timestamp) are written. This is identical to the existing skeleton×parser branch at 3041–3045 — collapse just makes that branch reachable for short-form mentions, not a new write semantic.

4. **Existing `npc_token_prefix_match:` observability log is kept.** It now fires alongside the new path, not in place of it. The advisory log retains value for the cases the collapse does NOT cover: emergent×emergent token-prefix relationships (e.g. id 11 "Garrik" vs id 9 "Garrick" in campaign 17) and parser-vs-parser short forms with no skeleton anchor present. The log line shape and call site are unchanged.

5. **Whitespace tokenization: split on whitespace runs (`str.split()` with no args).** Leading whole-token is `tokens[0]`. The amendment's "leading whole-token" phrase resolves to the entire first whitespace-delimited token of the incoming canonical_name, after `canonicalize_name()` normalization (which already collapses internal whitespace runs at dnd_engine.py:2848). This is the same rule the existing `_is_token_prefix` helper at line 3469 uses — reused, not reimplemented.

6. **Reuse `_is_token_prefix` (dnd_engine.py:3469).** Already implemented with exactly the semantics the amendment needs: whole-token boundary, equal-length names never qualify, strict prefix on tokenized form. The new code path becomes a small wrapper that runs a candidate-set query then applies `_is_token_prefix` for the per-row check.

---

## 2. Whole-token tokenization rule

The amendment names "leading whole-token" as the comparison unit. Concretely:

```
incoming canonical_name (already normalized via canonicalize_name)
    → split on whitespace runs → tokens
    → tokens[0] is the "leading whole-token"
    → compare against tokens[0] of each candidate row's canonical_name
```

Comparison is exact string equality on `tokens[0]` (no fuzzy, no lowercase — see §11.2 for the case-sensitivity decision). This matches the existing `_is_token_prefix` semantics: incoming token sequence must be a strict prefix of the candidate's token sequence, with equal-length sequences explicitly rejected (so "Eldrin Stormbow" does not "prefix-collapse" into itself).

**Edge cases drafting defaults (operator decision in §11.2):**

- **Apostrophes** (`D'Argent`, `O'Brien`): treated as part of the token (no internal split). Default: `D'Argent` is one whole-token; collapse fires if incoming `D'Argent` matches a `D'Argent Vance` anchor exactly. `D` alone would NOT match because `_NAME_RE` (npc_extractor.py:56) requires the first token to be `[A-Z][\w'-]+` — single letter probably passes regex but is filtered by name length conventions in practice. Worth confirming under §11.2.
- **Hyphenated firstnames** (`Mary-Anne`, `Jean-Luc`): default treated as one whole-token because `str.split()` does not split on hyphens. `Mary-Anne` collapses to a `Mary-Anne Tellwood` anchor; `Mary` alone does NOT collapse (it is not the leading whole-token of the anchor — `Mary-Anne` is).
- **Unicode whitespace**: `canonicalize_name` at dnd_engine.py:2848 collapses on Python's default `str.split()`, which already handles unicode whitespace (` ` no-break space, ` ` thin space, etc.) as separators. No additional normalization needed.
- **Case-sensitivity:** `canonicalize_name` preserves capitalization explicitly (PHASE_12_SPEC §9.1 anti-fuzzy doctrine, dnd_engine.py:2836). Default: case-sensitive comparison. `eldrin` would NOT collapse to `Eldrin Stormbow`. Rationale: the parser only emits proper nouns (capitalized); a lowercase emission is either parser garbage or a different intent and should not silently merge. Operator decision in §11.2.

---

## 3. Multi-anchor refusal path

The amendment's safety clause: "If multiple `skeleton_origin=1` rows in the same campaign share the leading whole-token, no collapse occurs; insert proceeds normally and ambiguity telemetry is logged."

**Flow on multi-anchor match:**

```
1. Compute leading_token = incoming.canonical_name.split()[0]
2. Query: SELECT id, canonical_name FROM dnd_npcs
          WHERE campaign_id=? AND skeleton_origin=1
3. Filter candidates: keep rows where _is_token_prefix(incoming, row.canonical_name)
4. Branch on candidate count:
     0 → no collapse; fall through to existing strict-equality lookup at line 2981
     1 → COLLAPSE: route to skeleton-lock UPDATE branch (mention_count + last_mentioned bump on the matched row); return (matched.id, was_new=False)
     ≥2 → no collapse; log npc_anchor_ambiguous; fall through to existing lookup
```

**Per-occurrence vs one-shot logging** — see §11.3. **LOCKED: per-occurrence** (every turn the ambiguity surfaces). Rationale: log noise is bounded by the campaign's anchor count, and a recurring ambiguity is itself a signal the operator needs (two skeleton NPCs share a firstname; the LLM is repeatedly emitting the bare form; operator may want to disambiguate by renaming one anchor).

**On fall-through under ambiguity**, the existing INSERT branch runs unchanged — the bare-firstname row is created or its mention_count is bumped, exactly as today. The amendment's design choice: under ambiguity, prefer the strict-literal default (insert a new row) over guessing the wrong anchor. The bare-firstname row stays in `dnd_npcs`, surfaces in `npc_fragmentation_report`, and `npc_anchor_ambiguous` tells the operator why.

**Implementation-note clarity** (review §3.4 observation #2): collapse routes to the existing skeleton-lock UPDATE branch at dnd_engine.py:3041–3045 — recency-only. The anchor row's `location_id` is NOT moved by short-form mentions, consistent with §14 doctrine (skeleton canon never overwritten by parser).

---

## 4. Telemetry log shape

Two log lines. Both follow the existing `npc_*` log convention (key=value, campaign-scoped, single line, prefixed by the event verb).

**On successful collapse** (single-anchor match):

```
npc_token_prefix_collapse: campaign={campaign_id} incoming='{canonical}' anchor_id={id} anchor_name='{canonical_name}' (mention_count_bumped)
```

This is a new log line. Distinct from the existing advisory `npc_token_prefix_match:` because that one still fires for the cases collapse does NOT catch (no skeleton anchor; emergent×emergent; ambiguous). Operators reading the journal need to distinguish "saw fragmentation shape, did nothing" from "saw fragmentation shape, collapsed into anchor."

**On multi-anchor refusal** (≥2 anchors match):

```
npc_anchor_ambiguous: campaign={campaign_id} incoming='{canonical}' anchors=[id={id1} name='{n1}', id={id2} name='{n2}', ...] (no_collapse)
```

Anchors list is materialized inline (kept short — practical cap is the campaign's skeleton NPC count for a single first-name; in practice 2–3). Both log lines emit via the existing `log()` function in dnd_engine.py, identical convention to `npc_near_match:` and `npc_token_prefix_match:`.

---

## 5. Cleanup operational migration (rows 4, 5, 6 in campaign 17)

Three rows to migrate as part of the implementation ship — pre-deployment data migration so the live state matches the post-deployment write-path semantic. (Row 11 "Garrik" is emergent×emergent, out of scope for this ship per external review verdict.)

**Per-row state at migration time** (current values from S46 recon, may drift slightly by deployment day):

| id | canonical_name | mention_count | anchor (row id, name) |
|---|---|---|---|
| 4 | Eldrin | 40 | 1, Eldrin Stormbow (skeleton, mention_count=4) |
| 5 | Lira | 43 | 2, Lira Songheart (skeleton, mention_count=8) |
| 6 | Borin | 37 | 3, Borin Ironhand (skeleton, mention_count=5) |

**Migration shape per row:**

```
1. Snapshot the bare-firstname row's mention_count and last_mentioned values.
2. Update the anchor row: apply mention_count migration policy (§11.1 decision).
3. DELETE the bare-firstname row.
4. Log per-row migration: row id, mention_count source/dest, last_mentioned source/dest.
```

**Mention-count migration policy** is the consequential §11 decision (see §11.1). Three viable options:

- **(a) DELETE only.** Anchor row's mention_count and last_mentioned remain at their current values (4/8/5 for mc, last_mentioned May 12 04:52 for two of the three). Cleanest baseline for `npc_health` / `phantom_candidates` metrics, but anchor row's recency signal stays stale until the next organic mention. Risk: post-deployment, the LLM emits "Eldrin" → collapses to anchor row → bumps last_mentioned. Within a turn or two, recency restores naturally. So the stale window is small.
- **(b) DELETE + sum-into-canonical.** Anchor row's mention_count = anchor.mention_count + bare.mention_count (4+40=44 for Eldrin); last_mentioned = max(anchor.last_mentioned, bare.last_mentioned). Preserves the historical recency and frequency signals. Distorts `npc_health` baseline (the canonical row's mention_count jumps post-migration, looking like a sudden burst). Distorts `phantom_candidates` because the metric defines a phantom as `skeleton_origin=0 AND mention_count=1` — anchor rows are skeleton_origin=1, so they don't show up as phantoms regardless, so this concern is theoretical for this specific metric. The concern is more general: time-series readings of mention_count would show an unexplained jump.
- **(c) DELETE + canonical-row-baseline-only (last_mentioned migrated, mention_count NOT migrated).** Anchor row gets `last_mentioned = max(anchor.last_mentioned, bare.last_mentioned)` so it surfaces correctly in `get_recently_active_npcs` post-migration; mention_count stays at its small skeleton-only value. Splits the difference: preserves recency signal (the operationally important one for the resolver) without distorting frequency baselines.

Code drafted default: **(c)**. Rationale: `last_mentioned` is what the resolver actually reads (ORDER BY `last_mentioned DESC`), so migrating it prevents a transient gap where the anchor row exists but is invisible to recent-NPC rendering for the next several turns. `mention_count` doesn't gate any read path; it's a diagnostic and a fragmentation signal. Migrating it would distort that diagnostic for no read-path benefit. Operator confirms or overrides in §11.1.

**Migration runs as part of the implementation ship**, in the same session, before the code change is deployed. Single transaction wrapping the three row updates + three deletes. Logged per-row.

---

## 6. Test surface

Eight scenarios in `test_npc_token_prefix_collapse.py` (new file). Project convention is **imperative scripts** with module-level `check(label, got, want)` calls and sectioned `# ─── Test N: ... ───` headers — see `test_npc_near_match.py` for the template shape. The eight scenarios below describe what each test block does; the file structures them as sequential numbered sections, not pytest function definitions.

**Core scenarios (six):**

1. **Bare-firstname collapses to unique anchor.** Setup: one skeleton row "Eldrin Stormbow", `skeleton_origin=1`, `mention_count=4`. Action: `npc_upsert(campaign_id, "Eldrin", skeleton_origin=False)`. Checks: anchor row's `mention_count` is now 5; `last_mentioned` updated; no new row inserted; total row count for the campaign unchanged; exactly one `npc_token_prefix_collapse:` log line emitted naming the anchor.
2. **Multi-anchor refuses collapse and logs.** Setup: two skeleton rows "Eldrin Stormbow" and "Eldrin Brightwater", both `skeleton_origin=1`, same campaign. Action: `npc_upsert(campaign_id, "Eldrin", skeleton_origin=False)`. Checks: a new row "Eldrin" was inserted (existing behavior preserved); one `npc_anchor_ambiguous:` log line emitted naming both anchor ids/names; neither anchor's `mention_count` changed; zero `npc_token_prefix_collapse:` lines emitted.
3. **Emergent row does not anchor collapse.** Setup: one row "Eldrin Stormbow" with `skeleton_origin=0` (emergent, not skeleton). Action: `npc_upsert(campaign_id, "Eldrin", skeleton_origin=False)`. Checks: a new row "Eldrin" was inserted; the existing emergent row's `mention_count` unchanged. (Verifies the `skeleton_origin=1` constraint is strict — emergent rows are not anchors.)
4. **Cross-campaign isolation preserved.** Setup: skeleton row "Eldrin Stormbow" in campaign A, `skeleton_origin=1`. Action: `npc_upsert(campaign_id=B, "Eldrin", skeleton_origin=False)` (different campaign). Checks: a new "Eldrin" row inserted in campaign B; campaign A's anchor untouched; zero collapse logs for A.
5. **Whole-token rule rejects substring matches.** Setup: skeleton row "Mira Wells", `skeleton_origin=1`. Actions: (i) `npc_upsert(campaign_id, "Mir", skeleton_origin=False)`, (ii) `npc_upsert(campaign_id, "Miranda", skeleton_origin=False)`. Checks: neither collapsed; two new rows inserted ("Mir" and "Miranda"); the anchor "Mira Wells" untouched. (Verifies `_is_token_prefix`'s whole-token semantics — not character-substring.)
6. **Idempotency on repeated short-form mention.** Setup: skeleton row "Eldrin Stormbow", `skeleton_origin=1`, `mention_count=4`. Action: `npc_upsert(campaign_id, "Eldrin", skeleton_origin=False)` called 5 times in a row. Checks: anchor row's `mention_count` is now 9; total row count for the campaign unchanged across all 5 calls; exactly 5 `npc_token_prefix_collapse:` log lines emitted.

**Recommended scenarios (two — ship with v1):**

7. **Skeleton-skeleton re-load collision not affected.** Setup: skeleton row "Eldrin Stormbow", `skeleton_origin=1`. Action: `npc_upsert(campaign_id, "Eldrin Stormbow", skeleton_origin=True)` (skeleton re-load). Checks: existing skeleton×skeleton re-load branch fires (lines 3059–3071); no mention bump; no collapse path entered (zero `npc_token_prefix_collapse:` lines). Confirms the new path doesn't interfere with skeleton-reload semantics.
8. **PC contamination still refused.** Setup: bound PC "Eldrin", skeleton row "Eldrin Stormbow" with `skeleton_origin=1`. Action: `npc_upsert(campaign_id, "Eldrin", skeleton_origin=False)`. Checks: PC-contamination guard fires FIRST (lines 2971–2976); returns None; no collapse; no insert; zero collapse or ambiguity logs. (Verifies ordering: PC-contamination check sits above the new collapse path.)

**LOC estimate**: ~100–150 LOC under the imperative convention (less boilerplate than pytest function-per-test shape).

---

## 7. Live verify plan

Discord scenario sequence after deployment to virgil-server, in campaign 17 (post-cleanup state from §5):

**Step 0** — `/travel Whispering Woods` (or any unrelated location command to clear the prompt cache; standard verify-pass clean-room setup per feedback_discord_test_prompts.md).

**Step 1** — Player free-form action that elicits an Eldrin mention. Example prompt:
```
I look around for Eldrin.
```
Expected: DM narration mentions Eldrin Stormbow by short or full form. The narration extraction pass runs.

**Step 2** — Tail the journal for the collapse log:
```bash
grep "npc_token_prefix_collapse" /mnt/virgil_storage/virgil.log | tail
```
Expected: one or more `npc_token_prefix_collapse:` log lines naming `incoming='Eldrin'` and `anchor_name='Eldrin Stormbow'` if the LLM emitted the short form.

**Step 3** — Confirm DB state did NOT regrow a bare-firstname row:
```bash
sqlite3 /mnt/virgil_storage/virgil.db "SELECT id, canonical_name, skeleton_origin, mention_count FROM dnd_npcs WHERE campaign_id=17 AND canonical_name IN ('Eldrin','Lira','Borin');"
```
Expected: zero rows. The anchor rows (ids 1, 2, 3) show incremented mention_count if short forms fired.

**Step 4** — Confirm the resolver renders the canonical name in the next exploration prompt. After another player action:
```
Where are we?
```
Expected: `Recently active NPCs:` line in the prompt contains `Eldrin Stormbow` (the anchor row's canonical_name), not `Eldrin` (the now-deleted bare-firstname row). Verify via `grep "Recently active NPCs" /mnt/virgil_storage/virgil.log | tail -1`.

**Step 5** — Run `npc_fragmentation_report` for campaign 17 and confirm the skeleton-fragmentation cluster size drops from 3 to 0 (Eldrin, Lira, Borin clusters all collapsed). Garrick × Garrik cluster (out-of-scope emergent-emergent) remains as documented.

Pass criteria: §5 log line fires on short-form emission AND no bare-firstname row regrows in `dnd_npcs` AND resolver renders canonical names in the prompt. Any of those three failing is a HALT — diagnose before iterating.

---

## 8. Doc update list

Three docs to update, all in `/home/jordaneal/virgil-docs/`:

1. **DOCTRINE.md** — amend the strict-literal-matching entry (currently `## §14. Strict literal match beats fuzzy`, dnd_engine.py:198–203). Add the locked amendment text from the header above. Format: new sub-section `### §14.1 Exception: unique skeleton anchor collapse` under §14, with the amendment language verbatim plus a one-line "Applied in: Sx implementation ship." (See §11.5 — DOCTRINE.md doesn't currently use `§N.M` sub-numbering, and the operator's brief named "§9.1" which doesn't exist in DOCTRINE.md. The amendment text is authoritative; the doc-target needs operator confirmation.)

2. **VIRGIL_MASTER.md** — add an entry under the npc_upsert section noting the new write-path branch (token-prefix collapse against unique skeleton anchor). One-line description, file:line citation, log-line names. Same format as existing entries for npc_near_match and npc_token_prefix_match.

3. **WHY.md** — append-only architectural reasoning. One entry on the call: why collapse-on-write (vs resolver-side rendering or DB-cleanup-only). Captures the external review convergence (ChatGPT + Gemini) and the four-constraint safety boundary as the doctrinal lock. Three to five sentences. Pattern: existing WHY entries are short, concrete, and name the architectural alternatives that were rejected.

PHASE_12_SPEC.md is referenced in code comments (dnd_engine.py:2838, 2854, 3510) but does not exist in `/home/jordaneal/virgil-docs/`. Either the spec lives elsewhere or has not been migrated. Out-of-scope to chase down for this ship — code-comment §9.1 references continue pointing at the named amendment text in DOCTRINE.md §14.1 (or wherever §11.5 lands).

---

## 9. Rollback plan

The implementation is additive: it adds an early-exit branch above the existing strict-equality lookup, and preserves all existing branches unchanged. Rollback shape:

- **Code rollback:** revert the npc_upsert function to its pre-change form (single file, dnd_engine.py). Git revert one commit. No downstream code touches the new branch; no callers need updating.
- **DB rollback:** the three deleted rows (ids 4, 5, 6) cannot be restored without a pre-migration snapshot. Take a snapshot of `dnd_companions`-style `(id, canonical_name, mention_count, last_mentioned)` for the three rows immediately before §5 migration, persisted to a journal line or a sidecar file. If rollback is required, re-INSERT the three rows with original values.
- **Telemetry rollback:** the two new log lines (`npc_token_prefix_collapse:`, `npc_anchor_ambiguous:`) stop firing on code rollback. No persistent state from telemetry.

**Failure modes that would trigger rollback:**
- False merge in production (a legitimate emergent NPC gets folded into a skeleton anchor that shares its firstname — should never happen under the four-constraint rule, but a coding error in the collapse query could miss the skeleton_origin=1 filter).
- Performance regression (the new candidate-set query per upsert call adds one indexed SELECT; should be sub-millisecond; rollback if it isn't).
- Unexpected interaction with PC contamination guard, skeleton-reload branch, or hydration path — covered by §6 unit tests 7 and 8, should not survive to production.

Pre-deployment gate: §6 unit tests green + §7 live verify pass criteria met. Rollback is a known-safe revert, not a recovery operation.

---

## 10. Code surfaces touched

| File | Lines (approx) | Change shape | LOC delta |
|---|---|---|---|
| dnd_engine.py | 2942–3103 (npc_upsert body) | Insert ~15 LOC early-exit block before line 2981 strict-equality lookup. Uses existing `_is_token_prefix` (line 3469) and existing `log()`. | +15 to +25 |
| dnd_engine.py | (new helper, optional) | Optional: factor the candidate-set query + filter into a `_find_unique_skeleton_anchor(conn, campaign_id, canonical)` helper for testability. If inlined: 0 LOC for helper. If factored: +20 LOC helper. | 0 or +20 |
| test_npc_token_prefix_collapse.py | (new file) | Six unit tests (§6 list 1–6) + two recommended (§6 list 7–8). | +150 to +200 |
| (data migration, runs once) | dnd_npcs rows 4, 5, 6 in campaign 17 | Single-transaction migration per §5. Not a persistent code change; lives as a one-shot SQL block run on virgil-server before code rollout. | 0 (operational, not code) |
| DOCTRINE.md | §14 section | Append `### §14.1` sub-section with locked amendment text. | +6 to +10 |
| VIRGIL_MASTER.md | npc_upsert entry | One-line addition referencing new write-path branch + log lines. | +2 to +4 |
| WHY.md | (append-only) | One new entry on the architectural call. | +5 to +8 |

**Total**: ~175–275 LOC including tests and docs. Production code surface (dnd_engine.py): +15 to +45 LOC. No new file in production code (test file is the only new file).

**Files NOT touched** (explicit out-of-scope):
- npc_extractor.py — no extractor-side change; the locked design is upsert-side, not extractor-side. `canonicalize_name` and `_strip_honorific` behavior unchanged.
- dnd_orchestration.py — no orchestration-side change; the resolver is not modified per external-review verdict (option 3 explicitly rejected).
- discord_dnd_bot.py — no Discord-side change; callers of npc_upsert are unaffected (return shape unchanged).
- skeleton_loader.py — no skeleton-loader change; skeleton_origin=True path through npc_upsert is unaffected.
- get_recently_active_npcs (dnd_engine.py:3343–3363) — no resolver change. Resolver becomes correct by virtue of the bare-firstname rows no longer existing.
- discord_dnd_bot.py SRD suggestion path (`_handle_new_npc_for_srd_suggestion`, ~line 2407–2412) — fires only on `was_new=True`. Collapse path returns `was_new=False`, so SRD suggestion does not fire for short-form mentions of existing anchors. Correct by construction; no change needed.

---

## 11. Decision points requiring operator lock

Six decisions surfaced. Code drafts a recommended default for each with reasoning visible; operator confirms or overrides in the review session.

### §11.1 — Mention-count migration policy on §5 cleanup

**LOCKED: (b) DELETE + sum-into-canonical for BOTH `mention_count` and `last_mentioned`.**

Four options were on the table at review:

- **(a) DELETE only.** Anchor row's `mention_count` and `last_mentioned` remain at their pre-migration values. Cleanest baseline; brief resolver-recency gap until next organic mention.
- **(b) DELETE + sum-into-canonical** *(locked)*. Anchor row's `mention_count = anchor.mention_count + bare.mention_count`; `last_mentioned = max(anchor.last_mentioned, bare.last_mentioned)`. Preserves full historical signal; one-time time-series spike on migration day.
- **(c) DELETE + last_mentioned-migrated-only.** Mid-position — resolver-correct but discards `mention_count` signal.
- **(d) Skip cleanup entirely.** Let bare-firstname rows age out naturally via the resolver's recent-NPCs LIMIT window. Zero migration risk, persistent fragmentation rows in DB until aged out.

Locked at (b) — review §2.1: post-doctrine semantic of `mention_count` is "how many times this entity appeared in narration"; under the locked amendment, short-form mentions ARE the canonical entity's mentions, so sum-into-canonical is the semantically-aligned migration. Existing `npc_fragmentation_report` tooling already understands the summed-into-canonical shape (its `combined_mention_count` field computes exactly this).

### §11.2 — Whole-token tokenization edge cases

**LOCKED:**
- **§11.2a Apostrophes** — part-of-token (no internal split on `'`). `D'Argent` is one whole-token.
- **§11.2b Hyphens** — part-of-token (matches `str.split()` default). `Mary-Anne` is one whole-token.
- **§11.2c Case sensitivity** — case-sensitive. Matches `canonicalize_name` doctrine at dnd_engine.py:2836–2840 ("PRESERVE capitalization") and PHASE_12_SPEC §9.1 strict-literal stance. Lowercase emissions are preempted at the extractor layer by `_NAME_RE` (npc_extractor.py:56, requires `[A-Z]` first char) — they never reach upsert.

All three locks reflect the existing doctrine (strict-literal anti-fuzzy stance, DOCTRINE.md §14) extended to the new comparison surface. Review §2.2 walked each: apostrophe and hyphen splits would silently merge distinct identities; case-insensitive solves a problem the extractor already prevents.

### §11.3 — Ambiguous-anchor telemetry frequency

**LOCKED: (a) per-occurrence.** Every turn the ambiguity surfaces, log `npc_anchor_ambiguous:` again.

Rationale: log noise is bounded (campaign-scoped skeleton NPC count is small; leading-token collisions are rarer still). The recurring log signal IS the operator's actionable indicator — when two skeleton NPCs share a firstname and the LLM keeps emitting the bare form, the operator may want to disambiguate by renaming one anchor. A one-shot log fires once and disappears; per-occurrence stays visible in journal greps until the ambiguity is resolved. Matches existing convention (`npc_near_match:`, `npc_token_prefix_match:` both fire per-occurrence). No in-process dedup state to maintain.

### §11.4 — Catch-all: any drafting-surfaced decision

**LOCKED: empty (confirmed by review §2.4).** Spec covered the load-bearing surface. Review surfaced three non-decision implementer-clarity items (PC contamination ordering, location_id under collapse, SRD suggestion interaction) — all addressed inline in §3 and §10. If implementation surfaces a sub-decision not covered by the locked §11 list, it escalates as HALT per Path A protocol.

### §11.5 — Doctrine doc target

**LOCKED: (a) — append as `### §14.1 Exception: unique skeleton anchor collapse` under DOCTRINE.md §14 ("Strict literal match beats fuzzy").**

Rationale: the amendment is explicitly an exception to the strict-literal rule; sub-section placement preserves that semantic. Peer-doctrine treatment (option b) would mis-represent the relationship; reconstructing PHASE_12_SPEC.md (option c) is heavyweight for the carrier ship and is filed as a potential separate corpus-archaeology ship.

#### §11.5.1 — Orphaned PHASE_12_SPEC.md code-comment references

**LOCKED: (ii) — update three code comments to point at new doctrine target as part of this implementation ship.**

The comments at `dnd_engine.py:2838`, `dnd_engine.py:2854`, `dnd_engine.py:3510` reference `PHASE_12_SPEC §9.1` (doc that does not exist server-side). All three update to reference `DOCTRINE.md §14.1` as part of this ship's Phase 3 — trivial three-line pass, no separate ship needed. Reconstructing PHASE_12_SPEC.md remains filed as potential future work.

### §11.6 — Implementation-session migration sequencing

**LOCKED: (b) — deploy code first, then migrate.**

Rationale: the code change is safe and additive (early-exit; existing strict-equality path preserved under no-anchor and ambiguous-anchor cases). Deploying first halts rot accumulation immediately; migration runs after as a one-shot historical cleanup. (a) actively creates a fresh-fragmentation window; (c) atomic with service down is operationally disproportionate for the personal-bot context.

**Caveat for the intermediate state** (review §2.6): between deploy and migration, bare-firstname rows still exist in `dnd_npcs` and still surface in `get_recently_active_npcs`. The LLM continues seeing short forms in prompt context for the few-turn window until migration runs. Write-side is correct immediately; read-side aligns post-migration. Window is minutes when operator scripts both in one session.

---

## Spec status

**LOCKED v1.** All §11 decisions locked. Review companion: `NPC_TOKEN_PREFIX_COLLAPSE_REVIEW.md` (REVIEW v1 COMPLETE). Implementation ship (Sx) executes in session 3 of the three-session cadence: spec revisions → code → tests → docs → restart → verify prompts → DB migration → deploy.
