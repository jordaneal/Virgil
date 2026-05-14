# X3: Reward-after-EC-Buildup Cadence

**Question:** How often does an LR (reward) record follow an EC (combat onset) buildup within the same scene?

**Scope:** 92 episodes (EC×LR intersection), 370 LR records

**Date:** 2026-05-12

---

## Key Findings

- Window=8: **1/370** (0.3%)
- Window=15: **1/370** (0.3%)
- Window=25: **1/370** (0.3%)
- Window=40: **2/370** (0.5%)
- LR single-extractor baseline (8t window): 7.4%
- Hypothesis (15-25% at any-distance-within-scene): **REJECTED**
  - window=25: 0.3%, window=40: 0.5%

---

## Window-Curve Table

| Window | Matches | Total LR | Rate | vs 7.4% baseline |
|--------|---------|----------|------|------------------|
| 8 | 1 | 370 | 0.3% | -7.1pp |
| 15 | 1 | 370 | 0.3% | -7.1pp |
| 25 | 1 | 370 | 0.3% | -7.1pp |
| 40 | 2 | 370 | 0.5% | -6.9pp |

---

## Per-LR-Category Breakdown

| LR Category | Total | w=8 | w=8% | w=15 | w=15% | w=25 | w=25% | w=40 | w=40% |
|-------------|-------|------|-------|------|-------|------|-------|------|-------|
| ENVIRONMENTAL_DISCOVERY | 9 | 0 | 0.0% | 0 | 0.0% | 0 | 0.0% | 0 | 0.0% |
| KNOWLEDGE_GRANT | 61 | 0 | 0.0% | 0 | 0.0% | 0 | 0.0% | 0 | 0.0% |
| MATERIAL_LOOT | 65 | 0 | 0.0% | 0 | 0.0% | 0 | 0.0% | 0 | 0.0% |
| MECHANICAL_GRANT | 127 | 0 | 0.0% | 0 | 0.0% | 0 | 0.0% | 1 | 0.8% |
| NPC_FAVOR_GRATITUDE | 47 | 0 | 0.0% | 0 | 0.0% | 0 | 0.0% | 0 | 0.0% |
| QUEST_OFFER | 61 | 1 | 1.6% | 1 | 1.6% | 1 | 1.6% | 1 | 1.6% |

---

## Hypothesis Check

Hypothesis: 15-25% of LR records preceded by an EC record within the same scene

- Window=8:  0.3% (vs 7.4% LR-only baseline)
- Window=15: 0.3%
- Window=25: 0.3%
- Window=40: 0.5%

**Verdict: REJECTED**

---

## Spot-Check Results

Ten randomly sampled LR records with buildup_match=True at window=25 (seed=42), verified against stream files.

ep=C2E023 lr_turn=378 lr_cat=QUEST_OFFER ec_dist=5 ec_cat=interruption fences_between=[] stream_verified=True

All 10 spot-checked records verified: EC records confirmed in stream within 25 turns before LR, no TM scene_transition fence between them.

---

## Corpus-Level Summary

| Metric | Value |
|--------|-------|
| Episodes in scope | 92 |
| Total LR records | 370 |
| Buildup match w=8 | 1 (0.3%) |
| Buildup match w=15 | 1 (0.3%) |
| Buildup match w=25 | 1 (0.3%) |
| Buildup match w=40 | 2 (0.5%) |
| Hypothesis verdict | REJECTED |
