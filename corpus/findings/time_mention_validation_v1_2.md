# Time-Mention Extractor v1.2 — Validation Report

**Phase:** Track 5 Ship 2, Phase 3 — five-patch calibration with hard ship gates.
**Extractor version:** `time_mention_v1_2`
**Hand-sample episodes (OQ7 lock):** C1E003, C1E024, C1E047, C1E057, C1E085, C1E101, C2E002, C2E018, C2E024, C2E031.
**Eval set:** `findings/time_mention_eval_set_v2.json` (321 calibration records, Jordan + Claude blind verdicts).
**Date:** 2026-05-06

---

## STOP-AND-REPORT — three of four ship gates fail

| Gate | Target | v1 baseline | v1.2 measured | Status |
|---|---:|---:|---:|---|
| Strict precision | ≥ 80% | 55.5% | **73.8%** | **FAIL** by 6.2pp |
| FP rate | ≤ 5% | 11.2% | **3.4%** | **PASS** |
| Duplicate rate | ≤ 3% | 16.8% | **3.4%** | **FAIL** by 0.4pp |
| No-regression retention | ≥ 95% | n/a | **85.4%** | **FAIL** by 9.6pp |

Per the Phase 3 prompt's explicit stop-and-report rule: **all five patches applied, three gates miss, no escalation to v1.3 without Jordan's review.**

The FP rate gate passed cleanly. The other three gates landed close on duplicate (0.4pp short) and substantially short on precision and retention. v1.2 is a real improvement over v1 (precision 55.5 → 73.8; FP 11.2 → 3.4; dup 16.8 → 3.4) but the targets are tight.

---

## 1. Run shape

| Metric | v1 | v1.2 | Δ |
|---|---:|---:|---:|
| Records emitted | 321 | 234 | -87 (-27%) |
| `[FILTERED_DISCOURSE]` rejects | 50 | 89 | +39 |
| `[UNKNOWN_SHAPE]` flag count | 78 | 136 | +58 |
| Distinct turns | 262 | ~199 | -63 |
| Multi-mention extra records | 59 | 35 | -24 |

The drop in records mostly reflects: (a) 43 DUPLICATE records suppressed by the Patch 1 dedup pass, (b) 14 phrases dropped by the new D8 causal-since filter, (c) 25-30 turns now Stage-0-rejected by widened D1/D5 patterns.

### Per-episode counts (v1.2)

| Episode | v1 records | v1.2 records | Δ |
|---|---:|---:|---:|
| C1E003 | 13 | 12 | -1 |
| C1E024 | 66 | 47 | -19 |
| C1E047 | 34 | 23 | -11 |
| C1E057 | 26 | 26 | 0 |
| C1E085 | 10 | 9 | -1 |
| C1E101 | 20 | 18 | -2 |
| C2E002 | 21 | 16 | -5 |
| C2E018 | 43 | 29 | -14 |
| C2E024 | 48 | 29 | -19 |
| C2E031 | 40 | 30 | -10 |

The C1E024 / C2E018 / C2E024 drops are concentrated in NPC-dialogue-heavy turns where Patch 2 (NPC routing → UNKNOWN_SHAPE) caught what previously emitted as cumulative_anchor or in_scene_compression. Combined with Patch 1 dedup these turns shed 50% of their record count.

### Category distribution before/after

| Category | v1 expected | v1.2 emitted |
|---|---:|---:|
| `UNKNOWN_SHAPE` | 124 | 123 |
| `scene_transition` | 39 | 45 |
| `cumulative_anchor` | 24 | 39 |
| `in_scene_compression` | 33 | 21 |
| `travel_duration` | 1 | 6 |
| `NOT_TIME_MENTION` (eval marker) | 36 | 0 emitted as TM |
| `DUPLICATE` (eval marker) | 54 | 0 second-emit |
| `is_combat_state_required` (eval marker) | 10 | 0 carry combat flag |

`scene_transition`, `cumulative_anchor`, `travel_duration` all over-emit relative to expected. `in_scene_compression` under-emits (33 → 21). The over-emission concentrates in Patch-3-tightened cumulative_anchor and travel_duration boundaries.

---

## 2. Patch-by-patch effect

### Patch 1 — multi-mention turn-level dedup
**Target:** 54 DUPLICATE records suppressed.
**Achieved:** 43/54 = 79.6% suppression (11 dup-emit failures remain).
**Status:** Partial. Duplicate rate 3.4% vs target 3%.

The dedup pass uses two grouping rules: same-sentence within 80 chars OR same-category-and-anchor within 200 chars. The 11 misses fall in three shapes:
- **Same turn, different sentences, same category, gap >200 chars.** Long Matt narration with two well-separated time phrases describing the same fictional moment but the rule's 200-char cap is too tight. Examples: C1E047_t554, C1E101_t1069.
- **First-record-also-marked-DUPLICATE.** Eval set marks `#0` as DUPLICATE (e.g., C2E002_t858#0, C2E024_t79#1) — these mean the v1 first-record itself was a duplicate of a different prior record (cross-turn dedup). Patch 1 only does within-turn dedup.
- **Different category, same fictional moment.** Eval marks two records on a turn as the same fictional moment; v1.2 keeps both because they have different categories. Examples: C2E018_t1932#1, C2E024_t2371#1.

To pass the 3% gate, dedup needs a 200 → 400 char window OR cross-turn dedup. Both flagged as v1.3 candidates.

### Patch 2 — NPC-dialogue → UNKNOWN_SHAPE phrase-span routing
**Target:** ~25-30 NPC-misclassified records → UNKNOWN_SHAPE.
**Achieved:** ~30 records re-routed (UNKNOWN_SHAPE went 124-eval-expected to 123 emitted, but 30+ NPC-flagged records that previously classified as scene_transition / cumulative_anchor now emit as UNKNOWN_SHAPE).
**Status:** Working as designed. The phrase-span detection (quote-mark counting + same-sentence NPC voicing tags) catches the obvious cases.

The Patch 2 design confirms the candidate Lesson 9 from Phase 2's filed insight: **phrase-span Stage 0 / Stage 2 routing is the right architecture for densely-mixed-narration domains**. Future extractors (Loot/Reward, Faction-Reference) should design phrase-span-aware filters from Phase 1.

### Patch 3 — cumulative_anchor temporal-context check + D8 causal-since
**Target:** ~15-20 cumulative_anchor over-fires routed to UNKNOWN_SHAPE.
**Achieved:** Mixed. cumulative_anchor expected count 24, v1.2 emits 39 — still over-emitting by ~15. D8 causal-since fired on 4 phrases.
**Status:** Direction correct, magnitude insufficient.

The temporal-context check (`CUMULATIVE_TIME_VOCAB | CUMULATIVE_TIME_STATE | CUMULATIVE_BACKWARD_TEMPORAL | CUMULATIVE_CAMPAIGN_CLOCK`) lets through cases like:
- "It's been a while since-- a giant's face" (C2E018_t158) — `since`, fragmented.
- "It has been" bare 2-word answer (C2E018_t875) — Patch tightened D7 to require temporal vocab; this case still slips because "It has been" preceding a recap-position turn isn't a Q&A.
- "since the chamber" / "since the blade" — D8 patterns don't catch these specific reason-noun forms.
- Backstory reveal "since you've been here" — the backward-temporal pattern matches "since you've been" generically, fires false-positive cumulative_anchor.

A v1.3 tightening would require the time vocab to be specifically time-of-day or duration (not just any time-noun), and would extend D8 with more reason-noun forms.

### Patch 4 — D1 production OOC extensions
**Target:** 10-15 of 36 FPs filtered.
**Achieved:** ~13 FPs filtered (FP rate 11.2 → 3.4).
**Status:** Working. Initial Patch 4 had a regex bug (`we're going to` not matching due to required whitespace between "we" and "'re"); fixed mid-session.

The break-announcement and meta-procedural patterns (`discuss this over the next week if you want`, `we don't need to decide right now`) catch the clearest cases. Cast-banter patterns (`headshot... ten years ago`) are harder to catch generically — the C2E031_t69 "Marisha headshot ten years ago" case relies on proximity tokens (`headshot`, `photo`, `shoot`) within 100 chars of the duration phrase. Weak signal, occasional false-negative.

### Patch 5 — D5 idiomatic phrase filters
**Target:** 10-15 remaining FPs filtered.
**Achieved:** ~10 FPs filtered.
**Status:** Working. The "it's been [emotion]" / "it's been [past-participle state]" / "wait a minute" / drinks-round patterns catch the obvious cases.

The `it's getting [non-temporal]` rule lists explicit non-temporal adjectives (`thick`, `frustrated`, `crowded`, etc.). If a real time-state-shift uses an adjective not in the list, the rule won't fire. Similar narrowness for "let me get loose for a minute" — only catches `loose|comfortable|settled|going`.

---

## 3. No-regression retention (gate 4 fail)

v1 had 178 records marked `verdict_at_v1: "correct"`. v1.2 retains **152/178 = 85.4%** (target ≥95%, miss by 9.6pp).

26 broken records, by failure shape:
- **15 records "now missing"** — turn previously emitted records, now Stage-0-rejected entirely or D8-filtered. Most are valid UNKNOWN_SHAPE that v1 surfaced and v1.2 swallowed via tightened patterns. Examples: C1E024_t957, C1E024_t1284 (`a few minutes` task), C2E024_t517 (`Once a week`), C2E024_t1958, C2E024_t2057, C2E031_t603/605/719/878 — all NPC-dialogue UNKNOWN_SHAPEs that were emitted in v1 but now drop because of stricter Stage 0 + Patch 2 routing combined with dedup.
- **6 records reclassified** — pattern shifts moved them between categories. C1E047_t593 (scene_transition → cumulative_anchor), C1E047_t1081 (in_scene_compression → travel_duration), C1E057_t1303 (in_scene_compression → UNKNOWN_SHAPE), etc.
- **3 combat-state losses** — these were `is_combat_state_required` records v1 emitted without the combat flag. v1.2 still doesn't fire combat-state on them (OQ5 lock unchanged). Counted as broken because v1's record-as-emitted is now suppressed by Patch 1 dedup or Patch 2 routing.

The retention shortfall is concentrated in: turns where v1 emitted a real UNKNOWN_SHAPE that v1.2 now silently drops. Patch 1's dedup is sometimes over-aggressive when same-category records sit close together; Patch 2's NPC routing turns some legitimate Matt-narration phrases into UNKNOWN_SHAPE that then dedup against an earlier UNKNOWN_SHAPE on the same turn.

A v1.3 tightening would tune Patch 1's window-size or add cross-turn dedup so within-turn UNKNOWN_SHAPEs that legitimately differ aren't collapsed.

---

## 4. is_combat_state_required (still 0 hits)

10/10 records expected to carry `is_combat_state: true` still don't. The OQ5 lock's 25-turn lookback misses long encounters where the init call sits 30-50+ turns before the time-mention. v1.2 did not modify OQ5; the 9 misses + 1 retained-as-non-issue are unchanged from v1.

Per Phase 2's known-limitation note: a v1.3 patch could either widen lookback (out-of-OQ5-lock, requires Jordan's signoff) or add a damage-narration backup signal to detect ongoing combat.

---

## 5. Discourse-reject distribution (89 total)

D1 production OOC dominates the new rejects (most prefix tokens above are D1-shape: `welcome`, `we'll`, `back`, `take`, etc.). D2 spell duration (`Disguise`, `Beast`, `stays`, `for the duration`) catches ~6. D5 idioms catch ~12. D7 Q&A pass-back catches ~5. D8 causal-since catches 4.

The 89 total represents real Stage 0 work — 30+ records that v1 emitted are now correctly filtered. The cost is the retention shortfall (§3): some of the now-rejected turns were real UNKNOWN_SHAPE in v1.

---

## 6. Stop-and-report decision

Per Phase 3 prompt's explicit triggers:

> Stop and report (do NOT escalate to v1.3 patches):
> - Any of the four ship gates miss after all five patches applied
> - A patch causes regression on previously-correct records that can't be resolved within the patch
> - The phrase-span-aware D6 (patch 2) reveals that turn-level Stage 0 has structural issues that aren't fixable in v1.2

All three triggers fire:
1. **Three gates miss** (precision 73.8% / retention 85.4% / dup 3.4%).
2. **Retention shortfall is structural, not tunable.** Patch 1 dedup interacts with Patch 2 NPC routing in ways that drop UNKNOWN_SHAPEs Jordan wanted captured. Tightening one patch loosens the other.
3. **Phrase-span Stage 0 confirmed as architecturally correct** — Patch 2 working as designed validates the candidate Lesson 9. But its interaction with dedup needs Phase 4-style architectural review, not regex patches.

**Recommendation for Jordan's review:**
- Accept v1.2 as a real improvement over v1 (FP rate halved twice over, dup rate 5x improvement).
- Three v1.3-candidate decisions to lock before next phase:
  1. Widen Patch 1 dedup char window (200 → 400) and/or add cross-turn dedup.
  2. Refine Patch 3 cumulative_anchor temporal-context to require time-of-day or duration vocab specifically (not just `since\s+\w+`).
  3. Decide on combat-state OQ5 lock — keep 25-turn lookback (accept ~3% miss as known limitation) or widen to 50 turns + damage-narration backup.

If Jordan green-lights v1.3, the same calibration cycle re-runs against eval v2. If Jordan accepts v1.2 as good-enough for Track 4 informational use, proceed to Phase 4 gate-set construction with v1.2's 73.8% precision as the published number.

---

## 7. Files

| Artifact | Path |
|---|---|
| Extractor source (v1.2) | `extractors/time_mention.py` |
| Hand-sample (v1.2) | `samples/time_mention_sample_v1_2.json` (234 records) |
| Hand-sample (v1, preserved) | `samples/time_mention_sample_v1_1.json` (321 records) |
| Eval set v2 (calibration) | `findings/time_mention_eval_set_v2.json` |
| Regression runner | `extractors/test_time_mention_eval_v2.py` |
| Validation v1 | `findings/time_mention_validation_v1.md` |
| Validation v1.2 | this file |
| Boundary stability v1 | `findings/time_mention_boundary_stability_v1.json` (Jordan's review TBD) |
| D6 precision v1 | `findings/time_mention_d6_precision_v1.json` (Jordan's review TBD) |
| Cross-extractor lessons | `corpus_builder_lessons_v1.md` |
