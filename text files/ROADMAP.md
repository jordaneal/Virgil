

---

## Mandate status (post-S68, post-convergent-review)

### Three-piece mandate — SHIPPED

All three pieces of the Prompt 1 mandate landed across S52-S62.

1. **Scene Lifecycle v1** (S52 spec, S53 v1.x patch, S63 v1.x doc-only patch) — motion cadence primitive closing F-54 stagnation drift. §59 sibling pattern instance 11. Hard-tier compression directive fires on stale=6 with operator-driven and Avrae-driven activity-signal resets (§1.F.a/b/d after F-64 candidate-driven restrictions in S53 + S63).

2. **Quest Layer v0 + v0.1** (S54-S57) — commitment spine. `dnd_quests` schema with 5-status state machine, `dnd_quests_audit` log, NPC-voiced offer cards via `#dm-aside`, operator-slash approval. §59 siblings 12 + 13. §1b third project instance ANCHORED at v0.1 cosine-similarity drop.

3. **Composition Layer v0 + v0.x** (S58-S62) — where-are-we anchoring. `dnd_quest_acts` table + `current_act_id` on `dnd_scene_state`. Engine-deterministic act transitions. §59 siblings 14 + 15. §1b fourth project instance ANCHORED via Reading-3-direct.

### Tier 1 cleanup arc — CLOSED at S67

S65 + S65.1 + S66 + S67 batched 11 fixes across front-door bugs, world-state-responds, durability + §76 audit. Standing practices adopted from S65 onward: pre-ship snapshot, per-fix rollback notes, sequential commits with atomic test verify, feature-disable switches.

### Authoring-canon-volume ship — SHIPPED at N-10

N-10 Canon Bootstrap Bot v0 + v0.1 (post-S68). `/bootstrap premise:"..."` flow with per-element `#dm-aside` cards. §1b sixth project instance ANCHORED. Authored-canon volume gap closed for operator option-3 authoring (premise-only, no manual skeleton.md editing).

### Doctrine candidates outstanding

- **F-64** *LLM-extracted activity signals as perverse-incentive surfaces in stagnation-detection contexts* — 5 instances catalogued (S53 NPC was_new, S63 consequence-DM-side, S66 F-031, S66 F-035, S68 N-4). Formal F-XX anchoring walk pending — recommended host: N-3.1 spec session (or Inversion v0 lock if N-3.1 folds per §11.4).

- **§1b "deterministic-validator suggester" sub-pattern** — six instances now (Track 6 #5.1, S41 NPC State-Sync, Quest Layer v0.1, Composition Layer v0, N-10, plus reserved Inversion sixth-instance candidate). Filed as running-list observation in DOCTRINE.md instance list per S67 audit recommendation. Formal sub-anchor pending.

- **§76 four-property test refinement** — S67 audit proposed two new doctrinal property candidates (rate-unlimited write, verbatim re-injection). 3 mitigated 4/4 surfaces filed for S67.1 post-Tier-1 hygiene close.

---

## Architectural direction-lock (post-convergent-review)

Three-way external review (planner + GPT + Gemini) locked direction post-S68 + S69-pause:

**Conversational-Runtime Inversion** as next architectural arc. Largest doctrinal direction-lock since "controlled canonization of stochastic generation."

**Load-bearing framing:**
- **Commands are BIOS** — session-zero/structural slashes (5-ish surfaces stay)
- **Engine is OS** — deterministic state machinery, §1a + §17 + §76 + §59 all hold
- **Conversation is UI** — narration-detection feeds engine via deterministic parsers; LLM still never decides binding state

**Litmus test:** *"Would a good human DM stop the session to operate software for this?"* — applied symmetrically to player-burden and DM-burden surfaces. Generalizes to butler ("would a good personal assistant make you type slash commands?") and other Virgil workloads at their architectural ships per VIRGIL_MASTER §2.2.

**§1a survives via inverted surface.** Narration-detection IS the deterministic gate (parser + structured signals + engine writer). Doctrinal extension shape is §11.2 candidate at Inversion spec time (Code's lean (iii) §1a.x sub-numbering; operator + Oracle territory).

**Slash sprawl correction.** Project accumulated 47 slash commands across 7 groups per S70 Inversion Phase 1 recon (R2). Inversion v0 first-migration set: transaction + quest-acceptance + loot-drop. Subsequent migrations in observed-friction order. Tier 1 BIOS slashes remain; Tier 3 pacing/play surfaces invert.

---

## Current priority queue (no timelines, sequence only)

| # | Status | Ship | Rationale |
|---|---|---|---|
| 1 | ✅ SHIPPED | Conversational-Runtime Inversion v0 Phase 1 (S70) | Spec drafted (42k chars, §1-§14). Six recon items clean, no HALTs. |
| 2 | ✅ SHIPPED | Inversion v0 Phase 2 review pass (S71) | 12 §11 decisions walked. Confidence: 8 HIGH / 1 MEDIUM-HIGH / 1 MEDIUM / 1 LOW. |
| 3 | ✅ SHIPPED | Inversion v0 Phase 3a (S73) | Closed-vocab quest-acceptance parser + suggester card + telemetry + 141 tests. §1a.x ANCHORED. |
| 4 | ✅ SHIPPED | §1b.1 Clarification Handshake Primitive v0 (S75 sketch → S76 review → S77 implementation) | Aggregator + M-DELAYED in-fiction primary + Layer A/B fallback + 112 new tests. §1b.1 ANCHORED. M-IMMEDIATE rejected with reasoning record. |
| 5 | ✅ SHIPPED | Inversion v0 Phase 3b (S78) | `transaction_completion_parser` + `loot_drop_parser` register against §1b.1 aggregator. 5 narration-detection surfaces total (quest_accept + tx pre/post + loot player/LLM). M-DELAYED primary path empirically activated. F-64 sixth instance candidate produced. |
| 6 | ✅ SHIPPED | §F-64 anchoring walk + council + implementation (S79+S80+S81) | F-64 ANCHORED at S81 with 7-instance cluster. §82 CANDIDATE filed (2 instances; deferred). Compliance-failure telemetry instrumented (`directive_compliance_failure` generic event + 2 detector surfaces). Doctrine-graph-proliferation-watch in WWC. |
| 7 | 📋 next | **Operator-decision** — pick next priority from candidates below | Filed S81 handoff. Four candidates roughly equal-weight: Phase 3c (NPC-commitment-utterance + N-3.1 fold-in); S69 Causality Engine Path A Phase 3; N-4 v1.x (descriptor→name pronoun gap); §F-44 NPC-axis closure (Bishop's bakery). |
| 7a | 📋 candidate | Inversion v0 Phase 3c — NPC-commitment-utterance + N-3.1 fold-in | Original Phase 3c surface. F-64 instance #7 (LLM price invention) would close at this ship (commitment-tracking is the architectural primitive). |
| 7b | 📋 candidate | S69 Causality Engine Path A Phase 3 implementation | Locked spec amends in-place per Inversion §11.6 lean (a) at Inversion ship. Phase 3 dispatches against amended locked spec. Atmospheric pressure / rumor system; large ship. |
| 7c | 📋 candidate | N-4 v1.x descriptor→name pronoun gap | Closes F-64 instance #6 (baker pronoun flip). Small scoped fix; ~1-2 sessions. |
| 7d | 📋 candidate | §F-44 NPC-axis closure | Bishop's bakery instance compounds existing §F-44 cluster. Location-scoped chroma retrieval + NPC extractor location-aware matching. Two-axis fix; medium scope. |
| 8 | 🔭 | S67.1 §76 hygiene closures | 3 mitigated 4/4 surfaces (consequences.summary, npcs.description fold, chroma DM-stores). Post-arc cleanup. |
| 9 | 🔭 filed | N-5 narrative-loot, N-6 §1b non-execution, N-7 unidentified-loot, N-8/N-9 channel/Chroma recon | Observed-friction-gated. |
| 10 | 🧊 parked | N-2 NPC commitment-tracking full scope | Deprioritized if N-3.1 closes pattern (it does, per §11.4 fold-in). |

---

## Honest project-state read

The F-54 motion-system stack ships and operates end-to-end. The architecture's structural foundation (§1a binding restriction, §17 single-writer, §76 LLM-write-authority limits, §59 pure-function sibling pattern, §F-59 bot→Avrae prohibition) holds across 17 §59 sibling instances, 6 anchored §1b instances, and the Tier 1 + N-10 + S68 cleanup work.

The game is not yet fun. Operator's S64 playtest disengaged at 20 minutes — bug-discovery cycle, not enjoyment. Tier 1 closed the surfaced bugs but didn't change the felt-experience floor.

The two remaining architectural ships before observed-friction-driven work resumes:

1. **Conversational-Runtime Inversion** (this arc) — converts UX direction from slash-primary to narration-primary. Closes the slash sprawl problem structurally. Phase 1 + Phase 2 shipped (S70 + S71); Phase 3 implementation next.

2. **S69 Causality Engine implementation** — converts the foundation into a campaign engine where inaction becomes observable. Atmospheric pressure (rumors, NPC mood shifts, faction tick) operates whether party engages or not. Will ship post-Inversion under the inverted slash discipline (3 slashes instead of 8) per §11.6 amend-in-place lock.

The architectural argument for both: foundation is structurally sound; the remaining work is shipping the surface that makes the foundation perceptible during play. Whether this produces fun specifically for solo-bard-LLM-DM play is an open question only sustained playtest answers.

Honest confidence read (per planner self-assessment): closed-vocabulary detection works (~80%), operator UX delta is real (~60%), §1a doctrinal extension survives implementation contact (~50%), Inversion-before-S69 sequencing is correct vs S69-first (~50/50). Convergent review locked the sequence; operator carries override authority if friction surfaces that argues for re-order.
