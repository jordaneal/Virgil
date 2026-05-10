# Compression Cadence — Full Corpus Parse Stats

**Extractor version:** compression_cadence_v1p4  
**Parse date:** 2026-05-09  
**Source:** CRD3 c=2 alignment, MATT turns only  
**Pool:** full CRD3 minus 10 handsample minus 7 recon = 123 episodes  

---

## 5.1 Episodes and records

| Metric | Value |
|--------|-------|
| Episodes parsed | 123 (80 C1, 43 C2) |
| Total records emitted | 365 |

---

## 5.2 Per-category breakdown

| Category | Records | % of total |
|----------|---------|------------|
| OVERNIGHT_REST | 143 | 39.2% |
| TEMPORAL_MONTAGE | 95 | 26.0% |
| LOCATION_DEPARTURE | 69 | 18.9% |
| NPC_DEPARTURE | 34 | 9.3% |
| INVESTIGATIVE_CLOSURE | 13 | 3.6% |
| SCENE_CUT | 10 | 2.7% |
| STALE_HOLD_CANDIDATE | 1 | 0.3% |
| **Total** | **365** | |

---

## 5.3 Per-episode record count distribution

Statistics computed over all 123 pool episodes (including 13 zero-record episodes).

| Metric | Value |
|--------|-------|
| Mean | 2.97 |
| Median | 3.0 |
| Max | 13 (C2E016) |
| Episodes at 0 records | 13 |
| Episodes at ≥1 record | 110 |

**Zero-record episodes (13):**  
C1E003, C1E006, C1E033, C1E040, C1E046, C1E073, C1E076, C1E085, C1E108,  
C2E010, C2E015, C2E034, C2E040

**Top 5 episodes by record count:**

| Rank | Episode | Records |
|------|---------|---------|
| 1 | C2E016 | 13 |
| 2 | C2E036 | 8 |
| 3 | C1E032 | 7 |
| 4 | C1E091 | 7 |
| 5 | C1E094 | 7 |

**Bottom 5 nonzero episodes (tied at 1 record each — showing 5 representative):**  
C1E002, C1E008, C1E010, C1E021, C1E035  
(21 episodes total at exactly 1 record)

---

## 5.4 Time-Mention overlap rate

| Metric | Value |
|--------|-------|
| Records with `extracted_time_mention_overlap=True` | 178 |
| Total records | 365 |
| TM overlap rate | 48.8% |

---

## 5.5 Episode-position distribution by campaign × phase third

Phase-third boundaries per spec §3:  
- C1 early: E001–E034 | C1 mid: E035–E075 | C1 late: E076–E115  
- C2 early: E001–E015 | C2 mid: E016–E030 | C2 late: E031–E046  

| Stratum | Pool episodes | Records | Records/episode |
|---------|--------------|---------|----------------|
| C1_early | 27 | 82 | 3.04 |
| C1_mid | 27 | 64 | 2.37 |
| C1_late | 26 | 63 | 2.42 |
| C2_early | 14 | 38 | 2.71 |
| C2_mid | 14 | 73 | 5.21 |
| C2_late | 15 | 45 | 3.00 |
| **Total** | **123** | **365** | **2.97** |

---

## 5.6 C1 vs C2 records-per-episode

| Campaign | Pool episodes | Records | Records/episode |
|----------|--------------|---------|----------------|
| C1 | 80 | 209 | 2.61 |
| C2 | 43 | 156 | 3.63 |

---

## 5.7 Stage 0 filter counts

Captured by re-running extractor on pool with module-level logs intact.  
D4 (recap-state) is a turn-level skip applied before phrase collection; no per-phrase log entry is generated.

### D-rule legend

Spec §6 defines D1–D4. D5–D7 were added during Phase 3 calibration. Canonical
definitions (source: `extractors/compression_cadence.py` + spec §6):

| Rule | Origin | Scope | Definition |
|------|--------|-------|------------|
| D1 | Spec §6; extended Patch 3 + Patch 4 | Any category | OOC scheduling and production language: end-of-episode scheduling ("next week", "pick this up next time"), sponsor/convention mentions, audience-address vocabulary ("Geek and Sundry", "live-tweeting"). Patch 3 added episode-end broadcast-close patterns ("that's where we'll end", "tonight's game"). Patch 4 added stream-meta vocabulary ("Q and A", "Wendy Sullivan"). Position-agnostic. |
| D2 | Spec §6 | Any category | Trigger phrase located inside NPC quoted speech (not Matt's narration). Detected by: open-quote count before phrase start (odd = inside quotes), or NPC voicing tag ("he says", "she goes", Named-NPC "says/tells") in the same sentence preceding the phrase. |
| D3 | Spec §6 | LOCATION_DEPARTURE only | In-scene micro-motion: physical navigation within the current scene to a sub-location (room, floor, door, other side). Regex: "make your way across/up to/to the far corner", "head down the stairs/hallway", "climb the ladder", "approach the door/bar". Does not fire on city/region/ship departures. |
| D4 | Spec §6 | Any category | Recap-state episode opening: turn at position ≤3% of episode with RECAP_VOCAB in a 15-turn lookback ("last week", "previously on", "picking up where", "rejoining our heroes"). Whole-turn skip before phrase collection — no per-phrase log entry. |
| D5 | Phase 3 Patch 1 | OVERNIGHT_REST only | Condition-recovery polysemy: "come to consciousness / awareness / your senses" variants that describe a PC waking from being knocked out (combat) or abducted/transported — not from overnight rest. Requires both (a) consciousness-variant phrase in turn and (b) combat/abduction/HP signal in turn + preceding 3 turns (e.g., "knocked out", "tentacles", "tied tightly", "on the back of a horse"). |
| D6 | Phase 3 Patch 2 | Any category | Within-turn same-family dedup: when two trigger phrases of the same category have start positions within 200 characters of each other in the same turn, emit only the first. Prevents double-counting when a single compression event is described with two near-synonymous trigger phrases in the same narration block. |
| D7 | Phase 3 Patch 4 | Any category | Spell/rules-mechanic reject: trigger phrase embedded in a spell-duration sentence ("imbue [spell] for the next N hours", "the spell lasts for", "concentration for N minutes") or spell-prep directive ("choose your spells", "prepare your spells"). Rules-procedure language, not in-fiction time compression. |

### Filter counts (full 123-episode pool)

| Filter rule | Count |
|-------------|-------|
| D1 — OOC/production language | 18 |
| D2 — trigger phrase inside NPC speech | 13 |
| D3 — in-scene micro-motion (LOCATION_DEPARTURE only) | 4 |
| D4 — recap-state turn-level skip | not logged (turn-level skip before phrase collection) |
| D5 — condition-recovery polysemy (OVERNIGHT_REST only) | 8 |
| D6 — within-turn same-family dedup | 21 |
| D7 — spell/rules-mechanic | 0 |
| **Total filtered** | **64** |

D6 breakdown: 19 OVERNIGHT_REST, 1 SCENE_CUT, 1 TEMPORAL_MONTAGE.
