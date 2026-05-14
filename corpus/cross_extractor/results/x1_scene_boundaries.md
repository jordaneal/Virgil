# X1: Unified Scene-Boundary Count

**Question:** How many scene boundaries per episode when EC, TM, and CC signals are merged?

**Scope:** 80 episodes (all-four-source intersection)

**Date:** 2026-05-12

---

## Key Findings

- Unified mean: **8.59** boundaries/episode (median 9, max 24)
- CC single-extractor baseline: 2.97 boundaries/ep — unified mean is higher by 5.62
- Total merged clusters: 687 across 80 episodes
- Source contribution breakdown: 1-src=604 (87.9%), 2-src=83 (12.1%), 3-src=0 (0.0%)
- EC-only: 145, TM-only: 293, CC-only: 166

---

## Per-Episode Table

| episode | merged | 1src | 2src | 3src | ec_only | tm_only | cc_only | ec_tm | ec_cc | tm_cc | ec_tm_cc |
|---------|--------|------|------|------|---------|---------|---------|------|-------|-------|----------|
| C1E001 | 8 | 7 | 1 | 0 | 1 | 2 | 4 | 0 | 0 | 1 | 0 |
| C1E002 | 6 | 6 | 0 | 0 | 1 | 4 | 1 | 0 | 0 | 0 | 0 |
| C1E004 | 7 | 5 | 2 | 0 | 1 | 3 | 1 | 0 | 0 | 2 | 0 |
| C1E005 | 9 | 7 | 2 | 0 | 2 | 2 | 3 | 0 | 0 | 2 | 0 |
| C1E007 | 9 | 9 | 0 | 0 | 3 | 4 | 2 | 0 | 0 | 0 | 0 |
| C1E008 | 3 | 3 | 0 | 0 | 1 | 1 | 1 | 0 | 0 | 0 | 0 |
| C1E009 | 10 | 8 | 2 | 0 | 2 | 5 | 1 | 0 | 0 | 2 | 0 |
| C1E010 | 6 | 6 | 0 | 0 | 2 | 3 | 1 | 0 | 0 | 0 | 0 |
| C1E011 | 4 | 4 | 0 | 0 | 1 | 0 | 3 | 0 | 0 | 0 | 0 |
| C1E013 | 5 | 5 | 0 | 0 | 1 | 1 | 3 | 0 | 0 | 0 | 0 |
| C1E016 | 10 | 9 | 1 | 0 | 1 | 7 | 1 | 0 | 0 | 1 | 0 |
| C1E017 | 9 | 8 | 1 | 0 | 4 | 2 | 2 | 0 | 0 | 1 | 0 |
| C1E019 | 10 | 10 | 0 | 0 | 2 | 6 | 2 | 0 | 0 | 0 | 0 |
| C1E020 | 7 | 7 | 0 | 0 | 2 | 2 | 3 | 0 | 0 | 0 | 0 |
| C1E021 | 5 | 5 | 0 | 0 | 2 | 2 | 1 | 0 | 0 | 0 | 0 |
| C1E022 | 13 | 11 | 2 | 0 | 1 | 7 | 3 | 0 | 0 | 2 | 0 |
| C1E023 | 9 | 7 | 2 | 0 | 2 | 4 | 1 | 0 | 0 | 2 | 0 |
| C1E025 | 6 | 5 | 1 | 0 | 4 | 1 | 0 | 0 | 0 | 1 | 0 |
| C1E027 | 10 | 9 | 1 | 0 | 2 | 3 | 4 | 0 | 0 | 1 | 0 |
| C1E028 | 13 | 13 | 0 | 0 | 1 | 7 | 5 | 0 | 0 | 0 | 0 |
| C1E029 | 9 | 8 | 1 | 0 | 2 | 4 | 2 | 0 | 0 | 1 | 0 |
| C1E030 | 6 | 5 | 1 | 0 | 2 | 0 | 3 | 0 | 0 | 1 | 0 |
| C1E031 | 10 | 9 | 1 | 0 | 3 | 3 | 3 | 0 | 0 | 1 | 0 |
| C1E032 | 12 | 10 | 2 | 0 | 2 | 4 | 4 | 0 | 0 | 2 | 0 |
| C1E034 | 9 | 9 | 0 | 0 | 1 | 5 | 3 | 0 | 0 | 0 | 0 |
| C1E035 | 6 | 6 | 0 | 0 | 1 | 4 | 1 | 0 | 0 | 0 | 0 |
| C1E037 | 8 | 7 | 1 | 0 | 1 | 6 | 0 | 0 | 0 | 1 | 0 |
| C1E039 | 8 | 8 | 0 | 0 | 2 | 2 | 4 | 0 | 0 | 0 | 0 |
| C1E042 | 9 | 7 | 2 | 0 | 1 | 5 | 1 | 0 | 0 | 2 | 0 |
| C1E043 | 5 | 5 | 0 | 0 | 1 | 2 | 2 | 0 | 0 | 0 | 0 |
| C1E049 | 14 | 14 | 0 | 0 | 3 | 7 | 4 | 0 | 0 | 0 | 0 |
| C1E052 | 6 | 6 | 0 | 0 | 1 | 4 | 1 | 0 | 0 | 0 | 0 |
| C1E055 | 7 | 6 | 1 | 0 | 2 | 4 | 0 | 0 | 0 | 1 | 0 |
| C1E058 | 6 | 5 | 1 | 0 | 1 | 3 | 1 | 0 | 0 | 1 | 0 |
| C1E062 | 4 | 4 | 0 | 0 | 1 | 2 | 1 | 0 | 0 | 0 | 0 |
| C1E063 | 8 | 5 | 3 | 0 | 1 | 4 | 0 | 0 | 0 | 3 | 0 |
| C1E068 | 5 | 4 | 1 | 0 | 4 | 0 | 0 | 0 | 0 | 1 | 0 |
| C1E071 | 9 | 9 | 0 | 0 | 3 | 2 | 4 | 0 | 0 | 0 | 0 |
| C1E086 | 6 | 5 | 1 | 0 | 2 | 2 | 1 | 0 | 0 | 1 | 0 |
| C1E087 | 9 | 9 | 0 | 0 | 1 | 6 | 2 | 0 | 0 | 0 | 0 |
| C1E092 | 4 | 3 | 1 | 0 | 1 | 2 | 0 | 0 | 0 | 1 | 0 |
| C1E093 | 5 | 4 | 1 | 0 | 3 | 1 | 0 | 0 | 0 | 1 | 0 |
| C1E094 | 11 | 7 | 4 | 0 | 1 | 4 | 2 | 0 | 0 | 4 | 0 |
| C1E097 | 9 | 7 | 2 | 0 | 1 | 3 | 3 | 0 | 0 | 2 | 0 |
| C1E098 | 5 | 5 | 0 | 0 | 1 | 3 | 1 | 0 | 0 | 0 | 0 |
| C1E099 | 9 | 7 | 2 | 0 | 2 | 3 | 2 | 0 | 0 | 2 | 0 |
| C1E100 | 6 | 5 | 1 | 0 | 1 | 2 | 2 | 0 | 0 | 1 | 0 |
| C1E102 | 3 | 3 | 0 | 0 | 1 | 1 | 1 | 0 | 0 | 0 | 0 |
| C1E105 | 6 | 5 | 1 | 0 | 1 | 3 | 1 | 0 | 0 | 1 | 0 |
| C1E107 | 5 | 5 | 0 | 0 | 1 | 2 | 2 | 0 | 0 | 0 | 0 |
| C1E110 | 9 | 9 | 0 | 0 | 2 | 6 | 1 | 0 | 0 | 0 | 0 |
| C1E111 | 8 | 8 | 0 | 0 | 2 | 4 | 2 | 0 | 0 | 0 | 0 |
| C1E113 | 10 | 8 | 2 | 0 | 2 | 4 | 2 | 0 | 0 | 2 | 0 |
| C2E001 | 9 | 8 | 1 | 0 | 1 | 4 | 3 | 0 | 0 | 1 | 0 |
| C2E003 | 12 | 10 | 2 | 0 | 3 | 4 | 3 | 0 | 0 | 2 | 0 |
| C2E005 | 11 | 10 | 1 | 0 | 2 | 5 | 3 | 0 | 0 | 1 | 0 |
| C2E006 | 7 | 7 | 0 | 0 | 2 | 3 | 2 | 0 | 0 | 0 | 0 |
| C2E007 | 14 | 14 | 0 | 0 | 4 | 8 | 2 | 0 | 0 | 0 | 0 |
| C2E012 | 12 | 10 | 2 | 0 | 2 | 6 | 2 | 0 | 0 | 2 | 0 |
| C2E016 | 24 | 22 | 2 | 0 | 1 | 12 | 9 | 0 | 0 | 2 | 0 |
| C2E017 | 6 | 5 | 1 | 0 | 2 | 2 | 1 | 0 | 0 | 1 | 0 |
| C2E019 | 11 | 11 | 0 | 0 | 3 | 4 | 4 | 0 | 0 | 0 | 0 |
| C2E020 | 6 | 2 | 4 | 0 | 1 | 0 | 1 | 0 | 0 | 4 | 0 |
| C2E021 | 10 | 7 | 3 | 0 | 2 | 2 | 3 | 0 | 0 | 3 | 0 |
| C2E022 | 9 | 6 | 3 | 0 | 2 | 2 | 2 | 0 | 0 | 3 | 0 |
| C2E023 | 12 | 9 | 3 | 0 | 1 | 4 | 4 | 0 | 0 | 3 | 0 |
| C2E025 | 10 | 9 | 1 | 0 | 1 | 6 | 2 | 0 | 0 | 1 | 0 |
| C2E026 | 12 | 11 | 1 | 0 | 3 | 6 | 2 | 0 | 0 | 1 | 0 |
| C2E028 | 8 | 8 | 0 | 0 | 1 | 5 | 2 | 0 | 0 | 0 | 0 |
| C2E029 | 11 | 10 | 1 | 0 | 4 | 4 | 2 | 0 | 0 | 1 | 0 |
| C2E032 | 15 | 12 | 3 | 0 | 1 | 9 | 2 | 0 | 0 | 3 | 0 |
| C2E036 | 12 | 9 | 3 | 0 | 1 | 3 | 5 | 0 | 0 | 3 | 0 |
| C2E038 | 9 | 7 | 2 | 0 | 1 | 3 | 3 | 0 | 0 | 2 | 0 |
| C2E039 | 13 | 13 | 0 | 0 | 3 | 8 | 2 | 0 | 0 | 0 | 0 |
| C2E041 | 7 | 7 | 0 | 0 | 2 | 4 | 1 | 0 | 0 | 0 | 0 |
| C2E042 | 8 | 8 | 0 | 0 | 2 | 4 | 2 | 0 | 0 | 0 | 0 |
| C2E043 | 12 | 8 | 4 | 0 | 1 | 5 | 2 | 0 | 0 | 4 | 0 |
| C2E044 | 5 | 4 | 1 | 0 | 3 | 1 | 0 | 0 | 0 | 1 | 0 |
| C2E045 | 6 | 6 | 0 | 0 | 3 | 1 | 2 | 0 | 0 | 0 | 0 |
| C2E046 | 11 | 10 | 1 | 0 | 3 | 5 | 2 | 0 | 0 | 1 | 0 |

---

## Spot-Check Results

Five randomly sampled merged-boundary clusters (seed=42) verified against stream files to confirm co-occurrence on genuine scene boundaries.

Episode C2E043 | turns 924-924 | sources=['CC', 'TM'] | cluster_size=2
  turn=924 src=CC cat=OVERNIGHT_REST in_stream=True
  turn=924 src=TM cat=scene_transition in_stream=True
Episode C1E022 | turns 1280-1280 | sources=['CC'] | cluster_size=1
  turn=1280 src=CC cat=LOCATION_DEPARTURE in_stream=True
Episode C1E005 | turns 1524-1524 | sources=['CC', 'TM'] | cluster_size=2
  turn=1524 src=CC cat=SCENE_CUT in_stream=True
  turn=1524 src=TM cat=scene_transition in_stream=True
Episode C1E063 | turns 905-905 | sources=['CC', 'TM'] | cluster_size=2
  turn=905 src=CC cat=TEMPORAL_MONTAGE in_stream=True
  turn=905 src=TM cat=scene_transition in_stream=True
Episode C1E049 | turns 2636-2636 | sources=['TM'] | cluster_size=1
  turn=2636 src=TM cat=scene_transition in_stream=True

All spot-checked clusters confirmed present in stream; `in_stream=True` for all candidate events.

---

## Corpus-Level Summary

| Metric | Value |
|--------|-------|
| Episodes in scope | 80 |
| Total merged boundaries | 687 |
| Mean per episode | 8.59 |
| Median per episode | 9 |
| Max per episode | 24 |
| 1-source clusters | 604 (87.9%) |
| 2-source clusters | 83 (12.1%) |
| 3-source clusters | 0 (0.0%) |
| EC only | 145 |
| TM only | 293 |
| CC only | 166 |
| EC+TM | 0 |
| EC+CC | 0 |
| TM+CC | 83 |
| EC+TM+CC | 0 |
