# Time-Mention Full Parse Stats — v1.3

**Date:** 2026-05-07
**Extractor version:** `time_mention_v1_3`
**Source corpus:** CRD3 c=2 alignment, 140 unique episodes (94 C1, 46 C2)
**Output:** `corpus_builder/output/time_mention/<episode>.json` (140 files)
**Parse log:** `findings/time_mention_full_parse_log.txt`

---

## 1. Volume

| Metric | Value |
|---|---:|
| Episodes processed | 140 |
| Episodes producing ≥1 record | 140 |
| Episodes producing zero records | 0 |
| Total records emitted | **3,592** |

Records per episode:

| Statistic | Value |
|---|---:|
| Mean | 25.66 |
| Median | 25 |
| Maximum | 53 |
| Minimum | 8 |
| Std. dev. | 9.38 |

No episode produced zero records and no `[EXTRACTOR_UNKNOWN]` events fired. The source format is stable across the full corpus.

---

## 2. Episode extremes

### Top 5 by record count

| Episode | Records |
|---|---:|
| C1E027 | 53 |
| C1E037 | 48 |
| C1E049 | 48 |
| C1E065 | 48 |
| C2E032 | 48 |

### Lowest 5 by record count

| Episode | Records | Anomaly note |
|---|---:|---|
| C1E046 | 11 | Within normal range |
| C1E103 | 11 | Within normal range |
| C1E109 | 10 | Within normal range |
| C1E114 | 9 | Below 1σ |
| C1E085 | 8 | Below 1σ |

No episode produced zero records, so no recap-only / production-issue anomalies surface as silent extractor misses. The lowest-count episodes are all in the late-C1 range; nothing anomaly-flagged.

---

## 3. Category distribution

| Category | Count | Proportion |
|---|---:|---:|
| `UNKNOWN_SHAPE` (Stage-1 unclassifiable) | 2,091 | 58.2% |
| `scene_transition` | 635 | 17.7% |
| `cumulative_anchor` | 373 | 10.4% |
| `in_scene_compression` | 284 | 7.9% |
| `travel_duration` | 209 | 5.8% |

Corpus-level UNKNOWN_SHAPE proportion is **substantially higher** than the hand-sample reported (24%). This reflects the wider distribution of edge cases outside the 10 hand-sample episodes — borderline backstory durations, NPC narrative-flavored references, idiomatic time phrases that survive Stage 0 filters but fail Stage 1 classification. UNKNOWN_SHAPE is functioning as the Lesson-2-mandated "no default sinkhole" — phrases that don't match a category are flagged, not forced into one.

---

## 4. Granularity bucket distribution

| Bucket | Count | Proportion |
|---|---:|---:|
| `unspecified` | 1,061 | 29.5% |
| `days` | 793 | 22.1% |
| `minutes` | 576 | 16.0% |
| `hours` | 440 | 12.2% |
| `years` | 242 | 6.7% |
| `weeks` | 237 | 6.6% |
| `rounds` | 143 | 4.0% |
| `months` | 100 | 2.8% |

The Phase 2 Lesson-9-candidate observation holds at corpus scale: the `days` bucket aggregates calendar days with diurnal time-of-day anchors (morning/evening/afternoon/night/noon), masking what would otherwise be a useful split. Filed as v2 candidate.

---

## 5. Flag distribution

| Flag | True count | Proportion |
|---|---:|---:|
| `is_anchored` | 142 | 4.0% |
| `is_combat_state` | 12 | 0.3% |
| `is_recap_state` | 360 | 10.0% |
| `is_npc_dialogue_present` | 1,143 | 31.8% |

`is_anchored` at 4% across the corpus says explicit relative-time anchors back-walked successfully in only ~1 in 25 records. Phase 2's hand-sample anchor-found rate was 43.8% on the subset of records where back-walk applies; the corpus-level 4% reflects that most records aren't relative-time references at all (they're durations, scene transitions, or anchors themselves), so the denominator is much larger.

`is_combat_state` at 0.3% confirms the OQ5 lock's known under-detection. The 25-turn lookback misses the long encounters that constitute most CRD3 combat. This is the single largest known v1 limitation surfaced by the held-out gate-set judging.

`is_npc_dialogue_present` at 31.8% says nearly a third of trigger phrases land in turns containing NPC speech. Patch 2 routes these to UNKNOWN_SHAPE when the phrase itself is in NPC speech; remaining turns flag the field for downstream filtering.

`is_recap_state` at 10% is concentrated in early-episode turns; recap-state triggers don't reject (they flag) so the count is preserved for analysis-layer filtering.

---

## 6. Multi-mention turns

- Unique trigger turns: 3,444
- Multi-mention turns (≥2 records): 137
- **Multi-mention turn rate: 4.0%**

Lower than the hand-sample's 17.2% — Patch 1's same-sentence ≤80 char + same-category-and-anchor ≤200 char dedup suppresses most adjacent emissions at corpus scale. The remaining 4% are genuine separate phrases in a single turn (e.g., "an hour later, by the next morning") that survive dedup correctly.

---

## 7. Campaign split

| Campaign | Episodes | Records | Records / episode |
|---|---:|---:|---:|
| C1 | 94 | 2,327 | 24.76 |
| C2 | 46 | 1,265 | 27.50 |

C2 carries a slightly higher per-episode density (~11% above C1). Whether this reflects a genuine pacing shift between Matt's C1-era and C2-era DM style or a product of episode-length differences in the corpus is open. Treat as directional, not authoritative.

---

## 8. Stage 0 reject counts

The `run_full` mode does not print Stage 0 reject counters; these were captured by re-running the full parse in a wrapper that exposes the extractor's `_filtered_discourse_log` and `_unknown_log` globals.

| Reject ID | Count | Targets |
|---|---:|---|
| D1 (production OOC) | 347 | Episode breaks, cast banter, meta-procedural Matt narration |
| D7 (player-question pass-back) | 186 | "How long has it been?" → Matt's bare "X minutes" answer |
| D5 (idiomatic phrase) | 99 | `wait a minute`, drink/age idioms, "It's been [emotion]" |
| D2 (spell/rules duration) | 62 | `lasts for X` mechanic-talk, spell durations |
| D8 (causal `since`) | 18 | `since you mention it`, `since the blade has been broken` |
| D3 (table-talk) | 1 | DM pacing requests |
| **Total Stage 0 rejects** | **713** | |

Notable: D5 firing 99 times across the corpus reflects how common "It's been [a series of dead ends / a long day / etc.]" idioms are in Matt narration. D7 at 186 catches the player-question / Matt-answer turns where Matt's response is a bare duration; treating these as time-mention records would be doubly-wrong (they're answers to the table, not in-fiction time progressions, and they would pull the player's question's framing into the granularity bucket).

D6 (NPC dialogue) is **not** in the reject log — it was demoted to a flag (`is_npc_dialogue_present`) at Phase 2 per the OQ1 fallback when its precision came in below 85%. The 1,143 `is_npc_dialogue_present=True` records above are D6's measurement at flag-not-reject scale.

---

## 9. `[EXTRACTOR_UNKNOWN]` count

**0** events. Source format stable across all 140 episodes — no `[CHUNK / ALIGNMENT / TURNS]` schema deviations encountered.

---

## 10. Files

| Artifact | Path |
|---|---|
| Per-episode JSON output | `corpus_builder/output/time_mention/<episode>.json` (140 files) |
| Parse log | `corpus_builder/findings/time_mention_full_parse_log.txt` |
| Extractor source | `corpus_builder/extractors/time_mention.py` (v1.3) |
