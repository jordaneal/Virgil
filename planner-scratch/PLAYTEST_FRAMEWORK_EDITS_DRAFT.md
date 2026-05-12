# Playtest Framework — Three Edits + §5 Verification

Draft for review. Verified against `VIRGIL_MASTER.md` §4 telemetry primitives + ROADMAP entries. Live journal-grep verification is a Code-side check; this doc covers shape-only confirmation.

---

## 1. §5 telemetry verification

Walked each named log line / metric in §5.1–§5.3 against documented shape in `VIRGIL_MASTER.md` and ROADMAP.

### §5.1 Hallucination rate

| Item in framework | Status | Notes |
|---|---|---|
| `directive_resolved:` violations | **MISNAMED** | `directive_resolved:` is the *success* log line from Ship 1 (S34) — fires when binding lands. The violation surface is `verification:` with `violation_class=roll_outcome_drift` from `narration_verifier.py` (Track 7 #2 + Ship 1). What §5.1 likely means: "post-Ship-A, zero `verification:.*violation_class=roll_outcome_drift`". |
| `phantom_candidates:` | ✅ exists | Ship 4 (S13). Per-turn count, not a violation — interpret as rate, not threshold. |
| `npc_near_match:` | ✅ exists | S23. Fires only on insert, distance ≤2. |
| "Scene state drift (day_phase mismatches, location flips, time-of-day inconsistencies)" | **NO DEDICATED TELEMETRY** | None of these are auto-detected. Day_phase narrative drift, location flips in narration vs `current_location_id`, time-of-day inconsistencies — all require operator observation or post-hoc cross-reference against scene_state. Framework should mark this bullet as qualitative-capture only, not a journal grep. |

### §5.2 State integrity

| Item | Status | Notes |
|---|---|---|
| `unconsumed_roll_swept:` | ✅ exists | S22, `avrae_listener.RollBuffer._sweep()`. |
| `unexpected_binding_co_occurrence:` | ✅ exists | Ship 1 (S34) canary in `build_dm_context`. |
| `roll_outcome_drift:` | **NESTED, NOT TOP-LEVEL** | Lives inside `verification:` log line as `violation_class=roll_outcome_drift`. Grep pattern is `verification:.*roll_outcome_drift`, not bare `roll_outcome_drift:`. |
| `directive_skill_mismatch:` | ✅ exists | Ship A (S36). |
| `state_footer:` rendering correctness | ✅ exists, but "correctness" is interpretive | `state_footer:` log fires every turn with mode / active_turn / round / day / phase. Log shows fields but doesn't validate them — operator checks correctness by comparing to expected state. Anomaly grep: `state_footer:` with `active_turn=none` while `mode=combat` (the S23 fallback case — fine in init-setup but smell otherwise). |

### §5.3 Performance

| Item | Status | Notes |
|---|---|---|
| `prompt_size:` | ✅ exists | S24. The 25k-correlation-with-empty-narration heuristic is documented; companion `dm_respond: EMPTY response ... prompt_chars=N` confirms correlation post-hoc. |
| `cloud_router_finish_reason:` | ✅ exists | Bug 2 / S30. Fires every cloud call. `finish_reason=length` indicates truncation. |
| "Latency between player input and bot narration" | **NO DEDICATED TELEMETRY** | Derivable from timestamps but no log line emits the delta. Operator-observable; not a journal grep. |

### §5.4 Inference economy

Clean. 11GB VRAM ceiling + cloud-calls-per-turn are configuration, not log-grep telemetry.

### Recommended §5 edits

- §5.1 first bullet: change `directive_resolved violations` → `verification: violation_class=roll_outcome_drift events (post-Ship-A, expect zero)`
- §5.1 last bullet: mark `Scene state drift` explicitly as **qualitative capture, no dedicated telemetry** — operator observation only
- §5.2 third bullet: change `roll_outcome_drift:` → `verification: violation_class=roll_outcome_drift` (nested, not top-level log line)
- §5.2 last bullet: clarify `state_footer:` is a journal grep for *anomaly patterns* (e.g. `active_turn=none` with `mode=combat` outside init-setup), not a correctness checker
- §5.3 last bullet: mark `Latency` as **derivable from timestamps, no dedicated log line** — post-hoc only

---

## 2. Three sharpening edits — drafted

Picked the three with highest leverage on evidence quality. Each is a section-replacement.

### Edit A — §2.3 + §2.4 merge into single "Clarification rate" metric

**Why load-bearing:** clarification is the core combat-friction signal. As written, the state-question vs affordance-question split is undefined at the boundary ("wait, who's bloodied?" is both), so observers will bucket inconsistently and we lose cross-session comparability on the metric most likely to surface dumb-combat friction.

**Current §2.3 + §2.4 (replace both):**

```
### §2.3 Clarification rate (merged from prior §2.3 + §2.4)

**What:** How often players have to stop the flow to ask about state ("who's bloodied?", "is the archer still up?") or affordances ("can I do X?", "what's my AC again?"). Both signal that the state surface and/or affordance surface isn't carrying.

**Capture:** Count clarification messages per combat scene. Tag each with one of:
- `state` — question about current state (HP, conditions, turn order, location)
- `affordance` — question about available action or rule applicability
- `both` — question that spans state and affordance (default this tag when uncertain; the boundary is fuzzy by design)

Compare combat-scene rate to exploration-scene rate.

**Threshold of concern:** Combat clarification rate >1 per scene, or combat rate ≥3× exploration rate.

**Architectural implication if observed:**
- High `state` tag share — footer + Avrae embeds insufficient; consider Beat Card / Turn Card surface (HCN §5 candidate).
- High `affordance` tag share — LLM narration is unclear about what player can do; prompt-side fix likely.
- High `both` — interaction compression may be needed (HCN §5 candidates earn closer look).
```

---

### Edit B — §2.5 replace ratio with pure-operational count

**Why load-bearing:** the original metric's "mixed" bucket is the escape valve and absorbs every message produced when Ship A's `!check` template fires inside narration ("I lunge... !check perception 15"). The directive-emit-shaping-behavior failure mode is what the metric actually targets; the unsigned ratio doesn't measure it.

**Current §2.5 (replace):**

```
### §2.5 Pure-operational message rate

**What:** Fraction of in-character player messages that are pure-operational — mechanical commands or templates with no narration ("I attack with my sword, +5 vs AC 14" or just "!attack goblin -t goblinchief"). The failure mode this targets: Ship A's directive-emit shaping players toward dice-rolling behavior at the cost of dramatic agency.

**Capture:** Sample 20 player messages mid-combat. Tag each as:
- `pure-operational` — mechanical content only, no narration
- `narrative-bearing` — any narration present (mixed messages count here; the metric is binary on "does narration exist")

**Threshold of concern:** Pure-operational rate >25% of in-combat player messages.

**Architectural implication if observed:** Ship A's emit template is shaping behavior — players are bypassing narration to type the command directly. Possible levers: prompt-side encouragement, B2.1-style narration mandate strengthening, or accept the shape (some players prefer mechanical voice).
```

---

### Edit C — §3.1 pin "unprompted" + add denominator

**Why load-bearing:** as written, the metric counts authored canon (`skeleton.md`) recall, which always fires by design and isn't causality. The architecturally interesting case is emergent canon (parser-extracted) recall — that's the signal for whether motion-systems thread needs to ship. Without the pin, the metric pre-determines its outcome.

**Current §3.1 (replace):**

```
### §3.1 Cross-session causality echoes

**What:** Do events from session N affect session N+1+? Specifically: does the bot surface emergent canon (parser-extracted NPCs, locations, consequences) from prior sessions without operator re-mention?

**Capture:** For each scene, count:
- Recall opportunities (NPC re-encounters, location revisits, faction references, prior-decision callbacks) where the operator did NOT mention the entity/event in current scene input
- Recall successes — bot surfaced the prior-session detail unprompted
- Recall failures — opportunity passed unnoticed

Distinguish two sources:
- **Authored canon** (skeleton.md, `skeleton_origin=1` rows) — surfacing is by design; not the load-bearing signal
- **Emergent canon** (parser-extracted, `skeleton_origin=0` rows) — surfacing is the architectural test of cross-session causality

Report emergent-canon recall rate (successes / opportunities) per session.

**Threshold of concern:** Emergent recall rate <30% across sessions where opportunities exist. Indicates parser-emergent canon isn't carrying — retrieval, scene-state, or prompt-context layers aren't surfacing the right rows.

**Architectural implication if observed:** Motion-systems thread (F-54) becomes load-bearing for emergent-canon persistence depth. NPC state-sync (Ship 3) extension to relationship/attitude state, consequence layer deepening, or scene-state retrieval tuning.
```

---

## 3. Mode A/B → Tier 0 / Tier 1-3 alignment

`HYBRID_COMBAT_NOTES.md` v3 §4 uses the Tier 0/1/2/3 ladder; framework introduces Mode A/B de novo as a coarser collapse. Aligning lets post-playtest evidence map back to HCN candidates cleanly.

**Mapping:**
- Mode A (skill challenge for trivial conflicts) = HCN Tier 0
- Mode B (standard Avrae init + LLM narration) = HCN Tiers 1-3 collapsed (the differences between 1/2/3 are narration intensity, not mechanical surface — per HCN §4.2)

**Find/replace edits:**

| Location | Current | Replacement |
|---|---|---|
| §2.5 architectural implication | "Mode A (skill challenge) probably produces more dramatic; Mode B (standard init) probably produces more operational. Goal is roughly balanced." | "Tier 0 (skill challenge) probably produces more dramatic; Tiers 1-3 (standard init) probably produces more operational. Goal is roughly balanced." |
| §7 Combat layer questions | "Does Mode B (standard Avrae init + LLM narration) feel functional in conversational multiplayer?" | "Does dumb combat (HCN Tier 1-3 — standard Avrae init + LLM narration) feel functional in conversational multiplayer?" |
| §7 Combat layer questions | "Does Mode A (skill challenge for trivial conflicts) earn its keep?" | "Does Tier 0 (skill challenge for trivial conflicts, per HCN §4.1) earn its keep?" |

No new terminology introduced — the framework just adopts HCN v3's existing vocabulary. Post-playtest analysis correlates back to HCN §4-§5 candidates without translation.

---

## Notes on what I did NOT touch

Per Jordan's direction, skipped the rest of the §2-§3 flags from the prior review (§2.1 meaningful-decision definition, §2.2 voice-channel scope, §2.6 momentum collapse anchor, §3.2 NPC continuity drift categorization, §3.3 faction motion reframe, §3.4 long-arc deferral, §3.5 fatigue separation, cross-cutting capture friction). Those stand as filed but not drafted.
