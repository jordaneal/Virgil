# X6: Campaign Density Delta Across All Four Sources

**Question:** Which extractor's record counts drive the C2 density delta over C1?

**Scope:** 140 episodes (full corpus)

**Date:** 2026-05-13

---

## Key Findings

- Largest absolute delta: **TM** (+2.74 records/ep)
- EC: C1=1.63/ep → C2=2.16/ep (ratio 1.32×)
- TM: C1=24.76/ep → C2=27.50/ep (ratio 1.11×)
- LR: C1=3.91/ep → C2=4.53/ep (ratio 1.16×)
- CC: C1=3.14/ep → C2=4.12/ep (ratio 1.31×)
- CC delta cross-check: 31.1% (original finding: 39%; scope now 126 episodes)

---

## Per-Source C1 vs C2 Records/Episode

| Source | C1 records | C1 eps | C1 rec/ep | C2 records | C2 eps | C2 rec/ep | C2/C1 ratio |
|--------|------------|--------|-----------|------------|--------|-----------|-------------|
| EC | 103 | 63 | 1.63 | 67 | 31 | 2.16 | 1.32× |
| TM | 2327 | 94 | 24.76 | 1265 | 46 | 27.50 | 1.11× |
| LR | 348 | 89 | 3.91 | 204 | 45 | 4.53 | 1.16× |
| CC | 264 | 84 | 3.14 | 173 | 42 | 4.12 | 1.31× |

---

## TM Category Breakdown (C1 vs C2)

| Category | C1 recs | C1 eps | C1/ep | C2 recs | C2 eps | C2/ep | C2/C1 |
|----------|---------|--------|-------|---------|--------|-------|-------|
| TM_UNKNOWN | 1368 | 94 | 14.55 | 723 | 46 | 15.72 | 1.08× |
| scene_transition | 392 | 92 | 4.26 | 243 | 46 | 5.28 | 1.24× |
| cumulative_anchor | 235 | 85 | 2.76 | 138 | 41 | 3.37 | 1.22× |
| travel_duration | 137 | 60 | 2.28 | 72 | 30 | 2.40 | 1.05× |
| in_scene_compression | 195 | 78 | 2.50 | 89 | 40 | 2.23 | 0.89× |

---

## CC Delta Cross-Check

Original finding (Compression Cadence findings §5 Q5): 39% delta (C1=2.61/ep, C2=3.63/ep, 123-episode pool).

Cross-check with merged 140-episode set:
- C1: 3.14/ep (264 records, 84 episodes)
- C2: 4.12/ep (173 records, 42 episodes)
- Delta: 31.1%

---

## Corpus-Level Summary

| Metric | Value |
|--------|-------|
| Total episodes | 140 |
| EC C2/C1 ratio | 1.32× |
| TM C2/C1 ratio | 1.11× |
| LR C2/C1 ratio | 1.16× |
| CC C2/C1 ratio | 1.31× |
| Largest delta source | TM (+2.74 rec/ep) |
