# NPC Token-Prefix Collapse — Design Review v1

**Status:** REVIEW v1. Companion to `NPC_TOKEN_PREFIX_COLLAPSE_SPEC.md` v1 (DRAFT). Walks the six §11 decisions, cross-references §1 defaults against current code, audits §6 test conventions and §10 LOC estimates, surfaces drafting gaps. Output of this doc is the lock pass — SPEC updates from DRAFT to LOCKED after Code applies the surfaced revisions in §4.

**Pattern:** Standard spec-then-review-then-implement cadence per `WORKING_WITH_CLAUDE.md`. Spec drafted in session 1; this is session 2 (review); implementation lands in session 3.

**Track:** Doctrine amendment to PHASE_12_SPEC §9.1 strict-literal-matching rule. Convergent external review (ChatGPT + Gemini, S46 brief) anchors the architectural shape; this review walks the operator-decision surface.

---

## Review summary

| Field | Value |
|---|---|
| §11 decisions reviewed | 6 (§11.1 through §11.6) |
| Sub-decisions reviewed | 3 (§11.2a/b/c) + 1 (§11.5.1) = 4 |
| Decisions locked at Code's recommendation | 4 (§11.2a, §11.2b, §11.2c, §11.3) |
| Decisions locked with revision request | 1 (§11.5 — confirm with sub-decision lock for §11.5.1) |
| Decisions pushed back | 1 (§11.1 — recommend (b) over Code's (c); surface (d) as new sub-option) |
| Decisions deferring with caveat | 1 (§11.6 — confirm (b) but note window) |
| New §11 decisions surfaced by review | 0 — spec covered the surface (§11.4 confirmed empty) |
| HALT escalations | 0 |
| Architectural shape changes | 0 — locked amendment text holds verbatim |
| §1 drift check | Clean — all six §1 defaults verified against current dnd_engine.py |
| §6 test convention check | **Divergence flagged** — spec used pytest function-name convention; actual project convention is imperative `check()`-style scripts. Revision request in §4. |
| §10 LOC estimate check | Plausible (likely lands 20–30 LOC for dnd_engine.py change; spec's 15–45 range holds) |
| Spec revisions to apply | 2 (test-convention rewrite in §6; migration option (d) added under §11.1) |
| Cross-doc consistency | Clean against DOCTRINE.md §14, VIRGIL_MASTER, WHY conventions |
| Ready-for-implementation status | Yes, after Code applies the 2 §4 revisions and operator locks §11.1 / §11.5 / §11.6 in chat |
| Implementation session | Session 3 (Sx) |

---

## §1. How to read this review

For each §11 decision in `NPC_TOKEN_PREFIX_COLLAPSE_SPEC.md`, this doc records:

1. **The question** (one-line restatement)
2. **Code's lock recommendation** (verbatim or summarized from spec)
3. **Planner review** — confirm, push back, or revise — with confidence level (HIGH / MEDIUM / LOW)
4. **Lock outcome** — what stands after revisions are applied

The review also walks the cross-cutting tasks (§1 drift check, §6 test conventions, §10 LOC estimates, drafting gaps) in §3. Spec revisions to apply land in §4. Final lock summary table in §5.

---

## §2. Decision walks

### §2.1 — §11.1 Mention-count migration policy

**Question:** When the three skeleton-fragmentation rows (ids 4, 5, 6 in campaign 17) are deleted in §5 cleanup, what happens to their `mention_count` and `last_mentioned` values?

**Code's lock:** Option (c) — DELETE + migrate `last_mentioned` only; do NOT migrate `mention_count`. Anchor row's `mention_count` stays at its skeleton-only value (4/8/5). Reasoning: protects resolver recency without distorting `npc_fragmentation_report` baseline.

**Planner review:** **Push back. Recommend (b) — DELETE + sum-into-canonical for both fields.** Also surface a new option (d) the spec drafted past.

The spec's framing of (b)'s "distortion" concern is real but bounded. Walking through it carefully:

- The distortion is **one-shot, not ongoing.** Pre-migration: anchor mc=4, fragment mc=40. Post-migration (b): anchor mc=44, fragment row deleted. Post-deployment: subsequent short-form mentions correctly route to anchor and bump its mc to 45, 46, etc. The "sudden burst" appearance is a single jump on migration day, after which growth is correctly attributed. Time-series readings of mention_count rate-of-change show one spike; absolute readings show "44" instead of "4."
- The post-doctrine semantic of `mention_count` is "how many times this entity appeared in narration." Under the locked amendment, short-form mentions ARE the canonical entity's mentions — that's the entire point of the collapse. Option (c) cherry-picks `last_mentioned` (the resolver-relevant signal) but discards `mention_count` (the diagnostic signal). That cherry-pick is inconsistent: either both signals belong to the canonical entity, or neither does.
- **Existing tooling already understands the (b) semantic.** `npc_fragmentation_report` at dnd_engine.py:3507 computes `combined_mention_count = primary.mention_count + sum(fragment.mention_count for fragment in cluster.fragments)`. Post-(b) migration, the canonical row's `mention_count` IS the combined count — `npc_fragmentation_report` becomes trivially correct without needing to keep its fragments-sum logic. The migration just bakes the truth in.
- (c)'s concern about `npc_health` baseline distortion has weak evidence: the metric defines a phantom as `skeleton_origin=0 AND mention_count=1`, which applies to fragment rows, not anchors. Migrating mention_count to skeleton-origin=1 anchors does not affect phantom detection at all. The "baseline" concern is general but not operationally load-bearing.

**Surfaced new option (d): Skip cleanup entirely; let bare-firstname rows age out naturally.**

The spec presented §5 cleanup as required pre-deployment work, but the code change alone is sufficient to stop the rot. Under (d):
- No migration runs. Bare-firstname rows (ids 4, 5, 6) remain in `dnd_npcs` with their current mention_count and last_mentioned values.
- Post-deployment, the new collapse path routes short-form emissions to the anchor row. Bare rows stop growing.
- The bare rows still surface in `get_recently_active_npcs` until their `last_mentioned` ages out of the resolver's LIMIT window. Given typical activity rates, this is hours-to-days.
- Eventually, the anchor row's last_mentioned dominates, and the bare rows fall out of the prompt context entirely. They persist in `dnd_npcs` but are operationally invisible.

(d)'s appeal: zero migration risk, no transaction, no manual rollback surface. The cost: persistent fragmentation rows visible in `npc_fragmentation_report`, hydration of bare-firstname rows still possible via `npc_get_by_name("Eldrin")` until aged-out cleanup is performed.

(d) is consistent with the doctrine §14 "telemetry tells us if drift is bounded" — under the new code path, drift is structurally bounded (no new fragmentation rows), so the existing fragments become bounded technical debt rather than ongoing rot.

**Recommendation: (b) + sum-into-canonical, with (d) as a fallback if operator wants the lighter-touch path.**

Confidence: MEDIUM-HIGH for (b). The semantic-alignment argument is strong, but the operator may legitimately value (c)'s baseline-cleanliness or (d)'s zero-risk-cleanup over the diagnostic-vocabulary fit. This is a value-call on what `mention_count` means going forward, and the operator owns that.

**Lock outcome:** Surface (d) as a new sub-option in spec §11.1. Operator picks among (a)/(b)/(c)/(d) in chat. Planner recommends (b); spec's (c) is acceptable but suboptimal under the existing diagnostic vocabulary.

---

### §2.2 — §11.2 Whole-token tokenization edge cases

#### §2.2a — Apostrophes (`D'Argent`, `O'Brien`)

**Question:** Treat apostrophes as part of the token or as a token boundary?

**Code's lock:** Part-of-token. `D'Argent` is one whole-token; `D` alone would not match an `D'Argent Vance` anchor because `D'Argent` is the anchor's leading whole-token, not `D`.

**Planner review:** **Confirm.**

The alternative (split on apostrophe) has no real motivation. Apostrophe-bearing names fall into two categories:
- **Atomic-identity tokens** (D'Argent, O'Brien, M'Lady) — splitting destroys the identity. `D` alone would never match a real NPC.
- **Possessives** (Donovan's Coinpurse) — these are objects, not persons, and would be filtered by the extractor stoplist or `_NAME_RE` before reaching upsert. Doesn't reach the comparison layer.

The drafting concern about `D` alone potentially matching was addressed by the existing `_NAME_RE` floor (requires `[A-Z][\w'-]+` — single-letter names typically fail regex character-class boundaries in practice; even if they pass, no operator would author a `D` skeleton NPC).

Confidence: HIGH.

**Lock outcome:** Confirm. Spec stays as written.

#### §2.2b — Hyphens (`Mary-Anne`, `Jean-Luc`)

**Question:** Treat hyphens as part of the token or as a token boundary?

**Code's lock:** Part-of-token. Matches `str.split()` default behavior.

**Planner review:** **Confirm.**

Splitting on hyphens has a stronger surface argument than apostrophes (Mary-Anne *could* be read as a compound of Mary and Anne) but a weaker doctrinal one. The names are identity-bearing as a unit:
- `Mary-Anne Tellwood` and `Mary Williams` are distinct NPCs. Splitting `Mary-Anne` → `Mary` + `Anne` would mean a short-form `Mary` collapses into `Mary-Anne Tellwood`. That's a silent false merge.
- The operator's authoring intent when typing `Mary-Anne` is to disambiguate from `Mary` — hyphens are an explicit identity-distinction signal. Splitting reverses that intent.
- Default `str.split()` semantic is what `_is_token_prefix` (dnd_engine.py:3469) already uses for the existing `names_overlap` PC-contamination check. Consistency wins.

Confidence: HIGH.

**Lock outcome:** Confirm. Spec stays as written.

#### §2.2c — Case sensitivity at leading-token comparison

**Question:** Compare incoming canonical's leading token to anchor canonicals' leading tokens as case-sensitive (matches existing strict-literal doctrine) or case-insensitive (catches lowercase emissions)?

**Code's lock:** Case-sensitive. Matches `canonicalize_name` doctrine (dnd_engine.py:2836–2840, "PRESERVE capitalization") and PHASE_12_SPEC §9.1 strict-literal anti-fuzzy stance.

**Planner review:** **Confirm.**

The operator's review brief surfaced a real-sounding concern: LLM occasionally lowercases names mid-prose ("as eldrin pointed out"), and case-sensitive comparison would miss this and create a `eldrin` (lowercase-e) fragment row.

**However: this concern is preempted by defense-in-depth at the extractor layer.** Walking the pipeline:

```
LLM narration: "...as eldrin pointed out..."
    ↓
npc_extractor → parse_npcs
    ↓
_normalize_npc → canonicalize_name("eldrin") → "eldrin" (capitalization preserved)
    ↓
_validate_npc → _NAME_RE check
    ↓
_NAME_RE = r"^[A-Z][\w'-]+..." → FAILS (first character must be [A-Z])
    ↓
Drop with drop_reason='bad_name_format'
    ↓
NEVER reaches npc_upsert
```

The validator's regex floor at npc_extractor.py:56–64 explicitly requires `[A-Z]` as the first character. Lowercase-leading emissions are rejected at the extractor before reaching the comparison surface where case-insensitive matching would help. The lowercase-fragment hypothetical doesn't exist under the current pipeline.

The argument FOR case-insensitive collapse only has weight if we expect the extractor's `_NAME_RE` to relax or if some other write path emits lowercase names directly to upsert. Neither is on the roadmap. Adding case-insensitive collapse here would solve a problem that doesn't occur.

The argument AGAINST case-insensitive is the doctrinal slope: PHASE_12_SPEC §9.1 explicitly chose strict-literal-with-telemetry-and-future-merge-tool over fuzzy matching, and DOCTRINE.md §14 codifies this. Any loosening of literal comparison is a slope toward "but what about McGregor vs Mcgregor? what about diacritics?" The clean boundary is the doctrine's lock; the locked amendment respects it.

Confidence: HIGH.

**Lock outcome:** Confirm. Spec stays as written.

---

### §2.3 — §11.3 Ambiguous-anchor telemetry frequency

**Question:** When multi-anchor refusal fires, log `npc_anchor_ambiguous:` per-occurrence (every turn) or one-shot (first time only, suppressed thereafter)?

**Code's lock:** (a) per-occurrence.

**Planner review:** **Confirm.**

Two reasons (a) is correct, beyond the spec's noise-is-bounded argument:

1. **The recurring log signal IS the operator's actionable indicator.** When two skeleton NPCs share a leading firstname and the LLM keeps emitting the bare form, the operator's natural next step is to disambiguate by renaming one anchor. A one-shot log fires once and disappears; the operator may not act on it in time. A per-occurrence log shows up in every journal grep until the ambiguity is resolved — that's the right pressure shape.
2. **In-process dedup state is operationally fragile.** Option (b) would require either an in-memory set (lost on process restart) or a persistent dedup table (adds schema surface for marginal value). Both fight the spec's other locked decisions (no schema changes, no new state surface). Option (a) is stateless and matches existing log-line conventions (`npc_near_match:`, `npc_token_prefix_match:` both fire per-occurrence).

Confidence: HIGH.

**Lock outcome:** Confirm. Spec stays as written.

---

### §2.4 — §11.4 Catch-all

**Question:** Did the spec drafting miss any load-bearing decision?

**Code's lock:** "None additional from this draft."

**Planner review:** **Confirm. §11.4 stays empty.** Review surfaced three observations during the cross-cutting audit that are NOT load-bearing decisions but worth recording in the spec as implementation notes:

1. **PC contamination guard ordering** (npc_upsert:2971–2976) runs BEFORE the new collapse path under §1 default #2. This is correct: PC names take precedence over skeleton-anchor collapse, preserving the §16 invariant ("Engine defends its own invariants"). Spec §6 unit test #8 (`test_pc_contamination_still_refused`) verifies this. **No spec revision needed; note for implementer.**
2. **location_id behavior under collapse.** The collapse routes to the existing skeleton-lock UPDATE branch at dnd_engine.py:3041–3045, which is recency-only — it does NOT update location_id. This means short-form "Eldrin" mentioned at a different location than the anchor's skeleton-authored location_id will NOT move the anchor. This is consistent with §14 doctrine (skeleton canon never overwritten by parser) and is the correct behavior. **Worth one sentence in spec §3 to make this explicit; no decision needed.**
3. **SRD suggestion path interaction.** `_handle_new_npc_for_srd_suggestion` (discord_dnd_bot.py:2407–2412) fires only on `was_new=True`. The collapse path returns `(anchor_id, was_new=False)`, so SRD suggestion will not fire for short-form mentions that collapse to an anchor. This is correct — short-form mention of an existing NPC isn't introducing new canon. **No spec revision; note for implementer.**

None of these are §11.4-shaped decisions. Spec covered the load-bearing surface.

Confidence: HIGH that §11.4 is correctly empty.

**Lock outcome:** Confirm §11.4 empty. Optional spec revision: add observations 1–3 as implementation notes under §3 or §10 (not strictly required for ship).

---

### §2.5 — §11.5 Doctrine doc target

**Question:** Where does the locked amendment text land in the doctrine docs?

**Code's lock:** Option (a) — append as `### §14.1 Exception: unique skeleton anchor collapse` under DOCTRINE.md §14.

**Planner review:** **Confirm (a).**

(a) is correct because the amendment is explicitly an exception to the strict-literal doctrine, not a peer doctrine:
- (b) (new top-level §N entry) treats the amendment as coequal with §14, which mis-represents the relationship. The amendment doesn't replace strict-literal — it carves a narrow exception inside it. Sub-section placement preserves that semantic.
- (c) (reconstruct PHASE_12_SPEC.md) is heavyweight for the carrier ship and orthogonal to the architectural change. It's worth doing eventually if the orphaned references at dnd_engine.py:2838/2854/3510 deserve a server-side home, but it's not gated on this ship.

DOCTRINE.md doesn't currently use `### §N.M` sub-numbering, but adding it is mechanically trivial and the precedent is small. Other doctrine docs (e.g. WHY.md append-only) already vary in numbering conventions; the doctrinal doc family tolerates new sub-numbering.

Confidence: HIGH for (a).

#### §2.5.1 — §11.5.1 Orphaned PHASE_12_SPEC.md code-comment references

**Question:** What to do about the code comments at dnd_engine.py:2838, 2854, 3510 that point at `PHASE_12_SPEC §9.1` — a doc that doesn't exist server-side?

**Code's lock (spec sub-decision):** Three options surfaced:
- (i) Leave code comments as-is
- (ii) Update code comments to point at the new doctrine target (DOCTRINE.md §14.1) as part of the implementation ship
- (iii) Reconstruct PHASE_12_SPEC.md as a separate ship and update comments to keep pointing there

**Planner review:** **Lock (ii).**

(ii) is the right call for three reasons:

1. **Implementation ship is the natural carrier.** The ship is already touching the upsert function and adjacent comments. Updating three comments to point at the new doctrine target is a trivial pass — file-level grep + sed-equivalent, ~3 line changes. Adding it to the implementation ship's scope adds minutes, not a session.
2. **(i) leaves broken references.** Code comments referencing a doc that doesn't exist server-side are stale — they mislead the next reader (whether that's Code in a future session or the operator). Stale references are technical debt; the implementation ship is the only ship in the queue that touches this surface, so it's the cheap moment to clean them up.
3. **(iii) is a separate ship's worth of work.** Reconstructing PHASE_12_SPEC.md means: trace all `§9.x` references in code, infer the original spec structure, write it. That's a corpus-archaeology ship, not an inline cleanup. If the operator wants PHASE_12_SPEC.md reconstructed eventually, it can be its own ship; but the implementation ship shouldn't block on it.

The mechanical pass for (ii): update three code comments to read `# See DOCTRINE.md §14.1` (or `§14` if §14.1 is rolled up — whichever §11.5 locks). The amendment text itself lives in DOCTRINE.md per §11.5; the code comments are just navigation pointers.

Confidence: HIGH for (ii).

**Lock outcome:** Confirm (a) for §11.5 main. Lock (ii) for §11.5.1. Implementation ship adds a 3-comment-update pass to its scope; no separate ship.

---

### §2.6 — §11.6 Implementation-session migration sequencing

**Question:** Order of operations between code deploy and §5 data migration?

**Code's lock:** (b) — deploy code first, then migrate.

**Planner review:** **Confirm (b), with caveat on the brief window.**

(b) is correct because the code change is safe and additive (no callers need updating; existing branches preserved under no-anchor and ambiguous cases). The intermediate state — code deployed but bare-firstname rows still in DB — is well-behaved:
- The write path: short-form emissions correctly route to anchor row. Rot is halted immediately.
- The read path: `get_recently_active_npcs` still surfaces bare-firstname rows in the prompt context, because they exist with recent `last_mentioned`. The LLM continues seeing "Eldrin" in context for a few turns.

**Caveat:** The intermediate state has a soft inconsistency — the LLM sees `Eldrin` in the prompt context (sourced from the bare row), but new emissions of `Eldrin` route to the anchor row's mention_count. The bare row's `last_mentioned` stops getting bumped; the anchor's starts getting bumped. Within ~10-30 turns (depends on activity rate), the anchor's `last_mentioned` overtakes the bare's, and the resolver shifts to rendering "Eldrin Stormbow" in the prompt.

Under §11.1 option (d) (no migration), this is the steady-state behavior — the bare row ages out naturally over hours-to-days. Under §11.1 option (b) or (c), the migration runs minutes after deploy and the bare rows are deleted, shortcutting the natural aging-out. Either way, (b) sequencing is fine.

The alternative sequencing options:
- (a) migrate first: actively creates a fresh-fragmentation window between migration and deploy. Strictly worse than (b).
- (c) atomic with service down: zero-window but operational cost is disproportionate for a personal-Discord-bot context. The intermediate state under (b) is not user-facing in a way that matters; the operator owns deploy timing and can schedule both within minutes.

Confidence: HIGH for (b). The caveat is informational, not blocking.

**Lock outcome:** Confirm (b). Note the intermediate-state caveat in spec §3 or §5 for the implementer's awareness.

---

## §3. Cross-cutting tasks

### §3.1 — §1 default drift check

**Task:** Re-verify each §1 default against current `dnd_engine.py` state. Flag any drift between spec drafting and review.

Verification reads (line numbers from current `dnd_engine.py`, ~5500 LOC):

| §1 default | Spec citation | Current verification | Status |
|---|---|---|---|
| #1 — Implementation in `npc_upsert` | dnd_engine.py:2942 | Function `npc_upsert` defined at 2942, body 2942–3103 | ✓ Confirmed |
| #2 — Anchor lookup BEFORE strict-equality at 2981 | dnd_engine.py:2981 | `existing = conn.execute(...)` at 2981 with `canonical_name=?` strict lookup; correct insertion point is between 2978 and 2981 | ✓ Confirmed |
| #3 — Anchor row's skeleton_origin preserved on collapse | dnd_engine.py:3041–3045 | Skeleton-lock branch at 3041–3045 confirmed: `mention_count + last_mentioned` only on `ex_skeleton_origin == 1 and not skeleton_origin` | ✓ Confirmed |
| #4 — Existing `npc_token_prefix_match:` log kept | dnd_engine.py:3001–3017 | Token-prefix observability block at 3001–3017 still present, advisory only ("Pure observability — no merge") | ✓ Confirmed |
| #5 — Whitespace tokenization via `str.split()` | (semantic, no specific line) | Matches `_is_token_prefix` (dnd_engine.py:3469) `split()` usage | ✓ Confirmed |
| #6 — Reuse `_is_token_prefix` helper | dnd_engine.py:3469 | Function defined at 3469 with whole-token-prefix semantics; equal-length names rejected (line 3475–3477) | ✓ Confirmed |

**No drift detected.** All six §1 defaults are accurate against current code. No revision needed.

### §3.2 — §6 test convention audit

**Task:** Confirm test file naming, fixture patterns, and assertion shapes match project convention.

**Finding: divergence flagged.**

Spec §6 names six tests in pytest function-name form (e.g. `test_bare_firstname_collapses_to_unique_anchor`). Actual project convention is **imperative scripts** with module-level `check(label, got, want)` calls, sectioned `# ─── Test N: ... ───` headers, and a custom PASS/FAIL counter. Evidence from `test_npc_near_match.py` (most-similar shape):

```python
# ──────────────────────────────────────────────────────────
# Test 3: npc distance-1 fires (Donavan vs Donovan)
# ──────────────────────────────────────────────────────────

captured.clear()
npc_upsert(CAMP_A, 'Donavan')   # new name; Donovan already exists in CAMP_A

nm = near_match_logs()
check('dist1: exactly one near_match log', len(nm), 1)
check_truthy('dist1: new name in log',      "new='Donavan'" in nm[0])
```

The spec's pytest-style function names would not run under the project's existing test harness (which counts `grep -c "^def test_" → 0` across `test_npc_near_match.py`, `test_phase_6_identity.py`, `test_npc_extractor.py`). The implementer would either need to invent a new test convention for this file or translate the spec's test names to inline `check()` scenarios.

**Test file naming is correct** (`test_npc_token_prefix_collapse.py`). **Test count is correct** (6 core + 2 recommended = 8 scenarios). **Per-test shape needs revision** to match project convention.

**Revision request:** Spec §6 should rewrite each test name as an inline scenario. The label string in `check(...)` carries what the spec's function name conveyed; the scenario header is the `# ─── Test N: ... ───` comment. LOC estimate for the test file drops correspondingly — likely 100–150 LOC (not 150–200) under the inline convention.

### §3.3 — §10 LOC estimate plausibility

**Task:** Confirm spec's +15 to +45 LOC estimate for the dnd_engine.py change is reasonable.

Walking the implementation surface:
- Candidate-set query (skeleton_origin=1 rows for this campaign): ~3 LOC (SELECT + fetchall).
- Filter to anchors via `_is_token_prefix`: ~3 LOC (list comprehension or loop).
- Branch on candidate count (0 / 1 / ≥2): ~3–5 LOC (if/elif/else).
- Collapse UPDATE branch — can call into existing skeleton-lock semantic at lines 3041–3045 directly, or inline the two-line update. ~5–10 LOC.
- Two log lines (`npc_token_prefix_collapse:` on collapse; `npc_anchor_ambiguous:` on multi-anchor): ~3 LOC each = 6 LOC.
- Helper factoring (optional, per §1 default #6): ~0 LOC if inlined; ~15–20 LOC if factored into `_find_unique_skeleton_anchor`.

**Inline total: ~20–27 LOC. Helper-factored total: ~30–40 LOC.** Both inside the spec's 15–45 range.

The spec's range holds. No flag.

### §3.4 — Drafting gap audit

**Task:** Read §2–§10 critically; surface anything the implementation will hit that isn't covered.

Three observations surfaced (already enumerated in §2.4 — §11.4 catch-all):

1. **PC contamination ordering** — confirmed correct (PC guard at 2971–2976 runs before new collapse path), already tested in spec §6 #8.
2. **location_id under collapse** — recency-only, not moved by parser hits. Worth one explicit sentence in spec §3 ("collapse routes to existing skeleton-lock branch — recency only; location_id of anchor not modified by short-form mentions").
3. **SRD suggestion on collapse** — returns `was_new=False`, so suggestion path does not fire. Correct behavior; worth a brief note in spec §10's "Files NOT touched" section to confirm `discord_dnd_bot.py` SRD path remains unmodified.

None of these are decision points. They're spec-clarity refinements.

**Optional spec revision** (not required for ship): add one paragraph to spec §3 covering observations 1–3 as implementation notes. The implementer can derive these from §1 + §6 + the existing code, so omission is not a blocker.

---

## §4. Spec revisions to apply

Code applies these before SPEC moves from DRAFT to LOCKED:

| # | Section | Revision | Rationale |
|---|---|---|---|
| 1 | §6 | Rewrite test descriptions to match project convention (imperative `check(label, got, want)` scenarios with sectioned `# ─── Test N: ... ───` headers, NOT pytest `def test_*` function names). LOC estimate drops to 100–150 (from 150–200). | Project convention divergence flagged in §3.2; current convention is module-level imperative scripts. |
| 2 | §11.1 | Add option (d): "Skip cleanup entirely; let bare-firstname rows age out naturally via the resolver's recent-NPCs LIMIT window. Zero migration risk, persistent fragmentation rows in DB until aged out." Note planner recommendation: (b) sum-into-canonical, with (d) as the lighter-touch alternative. | Spec drafted past this option; surfaced in §2.1 walk. |

**Optional revisions (not blocking ship):**

| # | Section | Revision | Rationale |
|---|---|---|---|
| 3 | §3 (new sentence) | Add: "Collapse routes to the existing skeleton-lock branch at dnd_engine.py:3041–3045 — recency only. The anchor row's `location_id` is NOT moved by short-form mentions, consistent with §14 doctrine (parser cannot overwrite skeleton-authored fields)." | §3.4 observation #2 — explicit clarity for implementer. |
| 4 | §10 ("Files NOT touched") | Add bullet: "`discord_dnd_bot.py` SRD suggestion path (`_handle_new_npc_for_srd_suggestion`, line 2407–2412) — fires only on `was_new=True`. Collapse path returns `was_new=False`, so SRD suggestion does not fire for short-form mentions of existing anchors. Correct behavior; no change needed." | §3.4 observation #3 — explicit clarity for implementer. |

---

## §5. Lock outcome summary

After Code applies §4 revisions, the locked decision matrix is:

| Decision | Locked value | Locked by | Confidence |
|---|---|---|---|
| §11.1 (migration policy) | **Operator decision pending** — planner recommends (b) sum-into-canonical; spec's (c) acceptable; new (d) skip-cleanup surfaced | Operator (review session chat) | MEDIUM-HIGH for (b) |
| §11.2a (apostrophes) | (default) part-of-token | Confirmed by planner | HIGH |
| §11.2b (hyphens) | (default) part-of-token | Confirmed by planner | HIGH |
| §11.2c (case sensitivity) | (default) case-sensitive | Confirmed by planner | HIGH |
| §11.3 (telemetry frequency) | (default) per-occurrence | Confirmed by planner | HIGH |
| §11.4 (catch-all) | Empty — spec covered the surface | Confirmed by planner | HIGH |
| §11.5 (doctrine doc target) | (default) (a) — §14.1 sub-section under DOCTRINE.md §14 | Confirmed by planner | HIGH |
| §11.5.1 (orphaned code comments) | (ii) update comments to new target as part of implementation ship | Locked by planner | HIGH |
| §11.6 (deploy/migrate sequencing) | (default) (b) deploy code first, then migrate | Confirmed by planner with intermediate-state caveat | HIGH |

**Outstanding operator decisions before implementation ship:** one (§11.1).

**Ready-for-implementation status:** Yes, conditional on §11.1 lock. After operator picks among (a)/(b)/(c)/(d), Code revises spec §5 (cleanup migration) to reflect the chosen policy, then implementation session can proceed.

**Implementation session scope (Sx):**
1. Add collapse branch to `npc_upsert` (dnd_engine.py, ~20–30 LOC).
2. Add unit tests in `test_npc_token_prefix_collapse.py` (project-convention inline scripts, ~100–150 LOC).
3. Run §5 cleanup migration per locked §11.1 policy (single SQL transaction, runs once on virgil-server).
4. Update DOCTRINE.md §14.1 sub-section with locked amendment text.
5. Update VIRGIL_MASTER.md npc_upsert section.
6. Append WHY.md entry on the architectural call.
7. Update three code comments (dnd_engine.py:2838, 2854, 3510) to point at DOCTRINE.md §14.1 per §11.5.1.
8. Live verify per spec §7 (Discord scenario sequence in campaign 17).

Total estimated implementation-session work: ~3–4 hours including verify and docs. No HALT escalations expected; code path is well-bounded and existing test infrastructure supports the convention without modification.

---

## Review status

**REVIEW v1 COMPLETE.** Lock pass output is the §4 revision list (2 required, 2 optional) plus the §5 decision matrix (8 confirmed at default / planner-revised, 1 pending operator lock — §11.1).

After Code applies §4 revisions and operator locks §11.1 in chat, SPEC moves from DRAFT to LOCKED and implementation session is unblocked.
