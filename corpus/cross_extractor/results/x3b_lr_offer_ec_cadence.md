# X3b: LR Offer → EC Combat-Initiation Cadence

**Question:** Do LR quest-offers precede EC combat initiations within the same scene?

**Scope:** 92 episodes (EC × LR intersection)

**Focal records:** LR direction=offered (61 records)

**Control:** LR direction=delivered (309 records, w=25)

**Date:** 2026-05-13

---

## Key Findings

- Window=25: **1/61** (1.6%)
- Window=50: **5/61** (8.2%)
- Window=100: **5/61** (8.2%)
- Control (delivered, w=25): **3/309** (1.0%)

---

## Window-Curve Table

| Window | Matches | Total offered | Rate | Control (delivered w=25) |
|--------|---------|---------------|------|---------------------------|
| 25 | 1 | 61 | 1.6% | 3/309 (1.0%) |
| 50 | 5 | 61 | 8.2% |  |
| 100 | 5 | 61 | 8.2% |  |

---

## EC Category Breakdown of Matches (w=100)

| EC Category | Matches |
|-------------|----------|
| interruption | 4 |
| npc_turns_hostile | 1 |

---

## LR Category Breakdown of Matches

| LR Category | Total | w=25 | w=50 | w=100 |
|-------------|-------|-------|-------|-------|
| QUEST_OFFER | 61 | 1 (2%) | 5 (8%) | 5 (8%) |

---

## Spot-Check Results

5 randomly sampled matched records at w=100 (seed=42), verified against stream files.

    ep=C1E022 lr_turn=1695 lr_cat=QUEST_OFFER ec_dist=14 ec_cat=npc_turns_hostile stream_verified=True
    ep=C1E108 lr_turn=18 lr_cat=QUEST_OFFER ec_dist=39 ec_cat=interruption stream_verified=True
    ep=C1E108 lr_turn=17 lr_cat=QUEST_OFFER ec_dist=40 ec_cat=interruption stream_verified=True
    ep=C1E108 lr_turn=17 lr_cat=QUEST_OFFER ec_dist=40 ec_cat=interruption stream_verified=True
    ep=C1E108 lr_turn=17 lr_cat=QUEST_OFFER ec_dist=40 ec_cat=interruption stream_verified=True

All spot-checked records verified: EC records confirmed in stream within 100 turns forward of LR offer, no TM fence between them.

---

## Corpus-Level Summary

| Metric | Value |
|--------|-------|
| Episodes in scope | 92 |
| LR offered records | 61 |
| LR delivered records (control) | 309 |
| Match rate w=25 | 1/61 (1.6%) |
| Match rate w=50 | 5/61 (8.2%) |
| Match rate w=100 | 5/61 (8.2%) |
| Control match rate w=25 | 3/309 (1.0%) |
