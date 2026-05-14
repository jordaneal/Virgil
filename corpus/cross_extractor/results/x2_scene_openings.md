# X2: Compression → Next-Scene-Opening Classification

**Question:** When Matt compresses with scope=scene_exit, what kind of context opens the next scene?

**Scope:** 126 episodes (TM × CC intersection), 292 CC scene_exit records

**Date:** 2026-05-13

---

## Key Findings

- quiet_extended_scene: **251/292** (86.0%)
- in_scene_compression: **13/292** (4.5%)
- time_anchor_set: **11/292** (3.8%)
- Boundary co-occurrence (TM scene_transition within 10t): 12/292 (4.1%)

**Limitation:** Cross-extractor signal cannot observe player turns or NPC dialogue directly. Opening shape is inferred from which extractor fires first after CC. `quiet_extended_scene` includes scenes where Matt sets context without any extractor firing.

---

## Per-Opening-Type Frequency

| Opening Type | Count | % |
|--------------|-------|---|
| quest_offer | 1 | 0.3% |
| reward_delivery | 8 | 2.7% |
| combat_initiation | 1 | 0.3% |
| time_anchor_set | 11 | 3.8% |
| travel_montage | 7 | 2.4% |
| in_scene_compression | 13 | 4.5% |
| quiet_extended_scene | 251 | 86.0% |
| **Total** | **292** | |

---

## CC Category × Opening Type Cross-Tab

| CC Category | Total | quest_offer | reward_delivery | combat_initiation | time_anchor_set | travel_montage | in_scene_compression | quiet_extended_scene |
|-------------|-------|------|------|------|------|------|------|------|
| OVERNIGHT_REST | 165 | 1 (1%) | 3 (2%) | 1 (1%) | 9 (5%) | 3 (2%) | 5 (3%) | 143 (87%) |
| TEMPORAL_MONTAGE | 32 | 0 (0%) | 0 (0%) | 0 (0%) | 0 (0%) | 0 (0%) | 4 (12%) | 28 (88%) |
| LOCATION_DEPARTURE | 81 | 0 (0%) | 5 (6%) | 0 (0%) | 2 (2%) | 3 (4%) | 3 (4%) | 68 (84%) |
| SCENE_CUT | 14 | 0 (0%) | 0 (0%) | 0 (0%) | 0 (0%) | 1 (7%) | 1 (7%) | 12 (86%) |

---

## Spot-Check Results

10 randomly sampled records (seed=42), verified against stream files.

    ep=C1E031 t=109 cc_cat=SCENE_CUT opening=quiet_extended_scene first_event=None stream_verified=True
    ep=C1E009 t=409 cc_cat=OVERNIGHT_REST opening=quiet_extended_scene first_event=None stream_verified=True
    ep=C1E095 t=783 cc_cat=LOCATION_DEPARTURE opening=quiet_extended_scene first_event=None stream_verified=True
    ep=C1E088 t=4378 cc_cat=OVERNIGHT_REST opening=quiet_extended_scene first_event=None stream_verified=True
    ep=C1E064 t=1459 cc_cat=OVERNIGHT_REST opening=quiet_extended_scene first_event=None stream_verified=True
    ep=C1E039 t=1919 cc_cat=OVERNIGHT_REST opening=quiet_extended_scene first_event=None stream_verified=True
    ep=C1E029 t=610 cc_cat=OVERNIGHT_REST opening=quiet_extended_scene first_event=None stream_verified=True
    ep=C2E038 t=710 cc_cat=SCENE_CUT opening=travel_montage first_event=TM/travel_duration stream_verified=True
    ep=C1E027 t=32 cc_cat=TEMPORAL_MONTAGE opening=quiet_extended_scene first_event=None stream_verified=True
    ep=C2E018 t=1825 cc_cat=OVERNIGHT_REST opening=quiet_extended_scene first_event=None stream_verified=True

All spot-checked records verified in stream.

---

## Corpus-Level Summary

| Metric | Value |
|--------|-------|
| Episodes in scope | 126 |
| CC scene_exit records | 292 |
| quest_offer | 1 (0.3%) |
| reward_delivery | 8 (2.7%) |
| combat_initiation | 1 (0.3%) |
| time_anchor_set | 11 (3.8%) |
| travel_montage | 7 (2.4%) |
| in_scene_compression | 13 (4.5%) |
| quiet_extended_scene | 251 (86.0%) |
| Boundary co-occurrence | 12 (4.1%) |
