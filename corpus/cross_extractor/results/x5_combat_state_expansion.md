# X5: TM Combat-State Expansion via EC Join

**Question:** How much does EC proximity expand the TM is_combat_state signal?

**Scope:** 94 episodes (EC×TM intersection), 2408 TM records

**Date:** 2026-05-12

---

## Key Findings

- TM baseline is_combat_state: **12** records (0.5%)
- TM expanded (±25 turns EC join): **52** records (2.2%)
- Expansion delta: **+40 records** (+1.7pp)
- Top TM category for expansion: **TM_UNKNOWN** (27 flips)
- All 10 spot-checked flip records verified against stream files

---

## Per-TM-Category Breakdown

| TM Category | Total | Baseline combat | Baseline % | Expanded combat | Expanded % | Flips |
|-------------|-------|-----------------|------------|-----------------|------------|-------|
| TM_UNKNOWN | 1428 | 7 | 0.5% | 34 | 2.4% | 27 |
| cumulative_anchor | 214 | 2 | 0.9% | 5 | 2.3% | 3 |
| in_scene_compression | 175 | 0 | 0.0% | 3 | 1.7% | 3 |
| scene_transition | 443 | 3 | 0.7% | 7 | 1.6% | 4 |
| travel_duration | 148 | 0 | 0.0% | 3 | 2.0% | 3 |

---

## Spot-Check Results

Ten randomly sampled TM records that flipped from baseline=False to expanded=True (seed=42), verified against stream files.

ep=C1E027 tm_turn=70 tm_cat=TM_UNKNOWN nearest_ec_dist=13 ec_cat=interruption stream_verified=True (ec_records_in_window=1)
ep=C1E019 tm_turn=838 tm_cat=TM_UNKNOWN nearest_ec_dist=13 ec_cat=npc_turns_hostile stream_verified=True (ec_records_in_window=1)
ep=C1E058 tm_turn=79 tm_cat=in_scene_compression nearest_ec_dist=25 ec_cat=interruption stream_verified=True (ec_records_in_window=1)
ep=C1E039 tm_turn=2170 tm_cat=TM_UNKNOWN nearest_ec_dist=21 ec_cat=npc_turns_hostile stream_verified=True (ec_records_in_window=1)
ep=C1E039 tm_turn=2167 tm_cat=TM_UNKNOWN nearest_ec_dist=24 ec_cat=npc_turns_hostile stream_verified=True (ec_records_in_window=1)
ep=C1E032 tm_turn=673 tm_cat=TM_UNKNOWN nearest_ec_dist=0 ec_cat=npc_turns_hostile stream_verified=True (ec_records_in_window=1)
ep=C1E025 tm_turn=1375 tm_cat=TM_UNKNOWN nearest_ec_dist=8 ec_cat=interruption stream_verified=True (ec_records_in_window=1)
ep=C1E022 tm_turn=1702 tm_cat=TM_UNKNOWN nearest_ec_dist=7 ec_cat=npc_turns_hostile stream_verified=True (ec_records_in_window=1)
ep=C2E005 tm_turn=993 tm_cat=travel_duration nearest_ec_dist=20 ec_cat=interruption stream_verified=True (ec_records_in_window=1)
ep=C2E041 tm_turn=793 tm_cat=in_scene_compression nearest_ec_dist=25 ec_cat=npc_turns_hostile stream_verified=True (ec_records_in_window=1)

All 10 spot-checked records verified: EC records confirmed present in stream within 25 turns of the TM record.

---

## Corpus-Level Summary

| Metric | Value |
|--------|-------|
| Episodes in scope | 94 |
| Total TM records | 2408 |
| Baseline is_combat_state=True | 12 (0.5%) |
| Expanded is_combat_state=True | 52 (2.2%) |
| Flipped (baseline=F, expanded=T) | 40 (+1.7pp) |
