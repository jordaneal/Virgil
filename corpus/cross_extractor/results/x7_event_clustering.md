# X7: Event Clustering Across All Four Sources

**Question:** Do events from EC, TM, LR, CC cluster temporally within episodes, or distribute independently?

**Scope:** 80 episodes (all-four intersection)

**Cluster definition:** ≥3 events from ≥2 different sources within a 15-turn window

**Independence test:** 100 source-label permutations (seed=42)

**Date:** 2026-05-13

---

## Key Findings

- Total clusters observed: **109**
- Mean clusters per episode: **1.36** (median 1, max 7)
- Episodes with zero clusters: **27**
- Permutation baseline: 108.2 (±6.1)
- Excess vs. independence: **+0.8** clusters (Z=0.13)
- 4-source clusters: **0**
- Most common co-clustering pair: **CC+TM** (64 clusters)

---

## Per-Episode Cluster Count Distribution

| Clusters/episode | Episodes |
|------------------|----------|
| 0 | 27 |
| 1 | 27 |
| 2 | 10 |
| 3 | 8 |
| 4 | 5 |
| 5 | 1 |
| 6 | 1 |
| 7 | 1 |

---

## Source-Pair Participation Matrix

Count = clusters containing events from both listed sources.

| | EC | TM | LR | CC |
|---|---|---|---|---|
| **EC** | — | 5 | 0 | 1 |
| **TM** | 5 | — | 43 | 64 |
| **LR** | 0 | 43 | — | 6 |
| **CC** | 1 | 64 | 6 | — |

---

## Top 10 Strongest Clusters

| Rank | Episode | Turn window | Size | Sources | n-sources |
|------|---------|-------------|------|---------|----------|
| 1 | C1E102 | 874–888 | 6 | LR+TM | 2 |
| 2 | C1E049 | 2591–2605 | 6 | CC+TM | 2 |
| 3 | C1E094 | 2734–2748 | 6 | CC+TM | 2 |
| 4 | C1E113 | 2869–2883 | 6 | LR+TM | 2 |
| 5 | C2E036 | 1551–1565 | 5 | CC+LR+TM | 3 |
| 6 | C1E019 | 1963–1977 | 5 | CC+LR+TM | 3 |
| 7 | C1E039 | 68–82 | 5 | EC+TM | 2 |
| 8 | C1E049 | 826–840 | 5 | LR+TM | 2 |
| 9 | C2E026 | 1710–1724 | 5 | CC+TM | 2 |
| 10 | C1E094 | 1919–1933 | 5 | CC+TM | 2 |

---

## Independence Test

Method: shuffle source labels within each episode (100 permutations). Preserves event timing; destroys multi-source co-occurrence signal. Compares observed multi-source cluster count to permuted mean.

| Metric | Value |
|--------|-------|
| Observed clusters | 109 |
| Permutation mean | 108.2 |
| Permutation std | 6.1 |
| Excess | 0.8 |
| Z-score | 0.13 |

---

## Spot-Check Results

Top 5 clusters verified against stream files.

    ep=C1E102 t=874-888 size=6 sources=['LR', 'TM'] verified=6/6 events=[LR/MECHANICAL_GRANT+TM/scene_transition+TM/scene_transition+LR/MECHANICAL_GRANT+TM/scene_transition+TM/UNK]
    ep=C1E049 t=2591-2605 size=6 sources=['CC', 'TM'] verified=6/6 events=[TM/in_scene_compression+TM/UNK+CC/TEMPORAL_MONTAGE+TM/UNK+CC/TEMPORAL_MONTAGE+TM/UNK]
    ep=C1E094 t=2734-2748 size=6 sources=['CC', 'TM'] verified=6/6 events=[CC/NPC_DEPARTURE+CC/TEMPORAL_MONTAGE+TM/scene_transition+CC/TEMPORAL_MONTAGE+TM/scene_transition+TM/scene_transition]
    ep=C1E113 t=2869-2883 size=6 sources=['LR', 'TM'] verified=6/6 events=[TM/in_scene_compression+LR/MECHANICAL_GRANT+TM/scene_transition+LR/MECHANICAL_GRANT+LR/MECHANICAL_GRANT+TM/scene_transition]
    ep=C2E036 t=1551-1565 size=5 sources=['CC', 'LR', 'TM'] verified=5/5 events=[TM/scene_transition+LR/NPC_FAVOR_GRATITUDE+TM/UNK+CC/TEMPORAL_MONTAGE+TM/UNK]

All spot-checked cluster events confirmed in stream.

---

## N-Source Distribution

| Sources in cluster | Count |
|--------------------|-------|
| 2 | 104 |
| 3 | 5 |

---

## Corpus-Level Summary

| Metric | Value |
|--------|-------|
| Episodes in scope | 80 |
| Total clusters | 109 |
| Mean clusters/ep | 1.36 |
| Max clusters/ep | 7 |
| Zero-cluster episodes | 27 |
| Permutation baseline | 108.2 (±6.1) |
| Excess vs independence | +0.8 (Z=0.13) |
| 4-source clusters | 0 |
