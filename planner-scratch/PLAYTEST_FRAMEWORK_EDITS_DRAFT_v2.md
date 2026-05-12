# Playtest Framework — Three Edits + §5 Verification (v2)

Draft for review. v2 incorporates Code's live-grep verification findings (§5 telemetry recon, completed). Items 1-5 from Code's observations folded into §5 as additive footnotes. Finding A (verifier-error fallback) shipping separately as small pre-playtest hygiene ship. Finding B (cloud_router print vs log) documented as known format inconsistency.

---

## 1. §5 telemetry verification — confirmed and refined

Live recon against production code in `~/scripts/` + 7-day `journalctl` confirmed all five original §5 corrections. Five additional refinements surfaced from Code's hands-on inspection.

### §5.1 Hallucination rate

| Item in framework | Status | Notes |
|---|---|---|
| `directive_resolved:` violations | **MISNAMED** | `directive_resolved:` is the *success* log line from Ship 1 (S34) — fires when binding lands. The violation surface is `verification:` with `violation_class=roll_outcome_drift` from `narration_verifier.py`. Sibling: `directive_resolution_skipped: reason=no_dc` fires from the same helper when DC is absent — common in normal play; framework should pair these so `no_dc` skips aren't read as anomalies. |
| `phantom_candidates:` | ✅ exists | Per-turn count, not a violation. Three sibling emission shapes: count=0 omits `candidates=[...]`; error variant `phantom_candidates: error campaign=N err=...` has no `count=`/`threshold=` fields. Grep patterns keying on `count=` will silently miss the error variant. |
| `npc_near_match:` | ✅ exists | Fires only on insert, distance ≤2. **Format omits `campaign=` field** (codebase convention inconsistency). Sibling `npc_token_prefix_match:` (with `campaign=`) catches "Lira" + "Lira Songheart" fragmentation cases that Levenshtein-distance-≤2 misses. Framework treating `npc_near_match` as the only fragmentation signal misses token-prefix cases — pair these. |
| "Scene state drift (day_phase mismatches, location flips, time-of-day inconsistencies)" | **NO DEDICATED TELEMETRY** | Qualitative capture only — operator observation against `dnd_scene_state` post-hoc. Candidate future telemetry surface if playtest shows drift is common. |

### §5.2 State integrity

| Item | Status | Notes |
|---|---|---|
| `unconsumed_roll_swept:` | ✅ exists | Per-guild sweep, not per-campaign. **Lacks `campaign=` field** (sweep is guild-scoped); actor name is lowercased. |
| `unexpected_binding_co_occurrence:` | ✅ exists | Ship 1 / S34 canary in `build_dm_context`. Zero fires in 30 days expected — canary fires only when both `arbitration_block` and `resolution_block` are non-empty (paradox state). Wrapped in `try/except: pass`. |
| `roll_outcome_drift:` | **NESTED UNDER `verification:`** | Grep pattern: `verification:.*violation_class=roll_outcome_drift`. **Wired but zero fires in 30 days.** 30-day violation_class distribution: 144 none / 16 actor_omission / 1 fabricated_combatant / 0 roll_outcome_drift. Classifier and retry-constraint helper exist and are wired into the verifier flow — treat as "wired but unverified-in-prod." Framework readers should know format is from source, not observation. |
| `directive_skill_mismatch:` | ✅ exists | Wired per Ship A §13 decision 12b (log + aside, not silent-ignore). **Zero fires in 30 days** — could mean players read directives carefully, or no mismatched roll has been issued recently, or Avrae detail field empty (falls through via `if avrae_skill and pending_skill`). Treat as wired but unverified-in-prod. |
| `state_footer:` rendering correctness | ✅ exists | All five fields present (mode, active_turn, round, day, phase). **`phase` field renders proper-case** ('Morning'), not lowercase — framework regexes must be case-insensitive. Two emission sites use same helper so format is consistent. Anomaly grep: `state_footer:` with `active_turn=none` while `mode=combat` outside init-setup (S23 fallback case). |

### §5.3 Performance

| Item | Status | Notes |
|---|---|---|
| `prompt_size:` | ✅ exists | Five per-section fields (system, retrieval, party, scene, directives) + total. **Breakouts do NOT sum to total** — `system` is a residual accumulator with overlap/inclusion logic. Framework must not claim equality of `system + retrieval + party + scene + directives = total`. |
| `cloud_router_finish_reason:` | ✅ exists, **format inconsistency** | Uses `print()` not `log()` — lacks the `[YYYY-MM-DDTHH:MM:SS]` ISO timestamp prefix every other line in §5 carries. Only the systemd journal timestamp prefixes it. **Framework parsers anchored on `[ISO_TS]` will skip this line — use a separate parser branch or grep without ISO anchor.** Format inconsistency is documented and accepted; not a fix-blocker for playtest. |
| "Latency between player input and bot narration" | **NO DEDICATED TELEMETRY** | Derivable from systemd timestamps post-hoc; no log line emits the delta. Operator-observable only. |

### §5.4 Inference economy

Clean. 11GB VRAM ceiling + cloud-calls-per-turn are configuration, not log-grep telemetry.

### Recommended §5 edits (incorporating Code's recon)

- §5.1 first bullet: change `directive_resolved violations` → `verification: violation_class=roll_outcome_drift events (post-Ship-A, expect zero — note: wired but unverified-in-prod over 30 days)`
- §5.1 second bullet: pair `phantom_candidates` count line with its error variant — note the format difference
- §5.1 third bullet: pair `npc_near_match` with `npc_token_prefix_match` — both are fragmentation signals
- §5.1 last bullet: mark `Scene state drift` explicitly as **qualitative capture, no dedicated telemetry**
- §5.2 third bullet: change `roll_outcome_drift:` → `verification: violation_class=roll_outcome_drift` (nested grep pattern; note wired-but-unverified status)
- §5.2 last bullet: clarify `state_footer:` grep is for *anomaly patterns* (e.g. `active_turn=none` with `mode=combat` outside init-setup); regexes must be case-insensitive for `phase` field
- §5.3 first bullet: add note that `prompt_size` breakouts do not sum to total
- §5.3 second bullet: add note that `cloud_router_finish_reason` lacks ISO timestamp prefix (print, not log) — parsers need separate branch
- §5.3 last bullet: mark `Latency` as **derivable from timestamps, no dedicated log line**
- §5 footnote: name `directive_resolution_skipped: reason=no_dc` as expected normal-play emission — not an anomaly

### Pre-playtest hygiene ship (Finding A, separate)

Verifier-error fallback at `dnd_engine.py:6480` emits `violation_class=none` when verifier raises an exception — indistinguishable from clean verification pass. Silent failure mode that would compromise playtest evidence: if verifier crashes mid-session, framework grep would find zero drift AND inflated "none" count, looking like cleanest session ever.

Ship: small one-line-ish change to emit `violation_class=verifier_error` sentinel instead. Prompt drafted separately. Lands before playtest evidence accumulation begins.

---

## 2. Three sharpening edits — unchanged from v1

(Section content identical to v1 draft; preserved here so the v2 doc is a single complete reference.)

### Edit A — §2.3 + §2.4 merge into single "Clarification rate" metric

**Why load-bearing:** clarification is the core combat-friction signal. As written, the state-question vs affordance-question split is undefined at the boundary ("wait, who's bloodied?" is both), so observers will bucket inconsistently and we lose cross-session comparability on the metric most likely to surface dumb-combat friction.

**Replacement (replaces both §2.3 and §2.4):**

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

### Edit B — §2.5 replace ratio with pure-operational count

**Why load-bearing:** the original metric's "mixed" bucket is the escape valve and absorbs every message produced when Ship A's `!check` template fires inside narration ("I lunge... !check perception 15"). The directive-emit-shaping-behavior failure mode is what the metric actually targets; the unsigned ratio doesn't measure it.

**Replacement (replaces §2.5):**

```
### §2.5 Pure-operational message rate

**What:** Fraction of in-character player messages that are pure-operational — mechanical commands or templates with no narration ("I attack with my sword, +5 vs AC 14" or just "!attack goblin -t goblinchief"). The failure mode this targets: Ship A's directive-emit shaping players toward dice-rolling behavior at the cost of dramatic agency.

**Capture:** Sample 20 player messages mid-combat. Tag each as:
- `pure-operational` — mechanical content only, no narration
- `narrative-bearing` — any narration present (mixed messages count here; the metric is binary on "does narration exist")

**Threshold of concern:** Pure-operational rate >25% of in-combat player messages.

**Architectural implication if observed:** Ship A's emit template is shaping behavior — players are bypassing narration to type the command directly. Possible levers: prompt-side encouragement, B2.1-style narration mandate strengthening, or accept the shape (some players prefer mechanical voice).
```

### Edit C — §3.1 pin "unprompted" + add denominator

**Why load-bearing:** as written, the metric counts authored canon (`skeleton.md`) recall, which always fires by design and isn't causality. The architecturally interesting case is emergent canon (parser-extracted) recall — that's the signal for whether motion-systems thread needs to ship. Without the pin, the metric pre-determines its outcome.

**Replacement (replaces §3.1):**

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

## 3. Mode A/B → Tier 0 / Tier 1-3 alignment — unchanged from v1

`HYBRID_COMBAT_NOTES.md` v3 §4 uses the Tier 0/1/2/3 ladder; framework introduces Mode A/B de novo as a coarser collapse. Aligning lets post-playtest evidence map back to HCN candidates cleanly.

**Mapping:**
- Mode A (skill challenge for trivial conflicts) = HCN Tier 0
- Mode B (standard Avrae init + LLM narration) = HCN Tiers 1-3 collapsed

**Find/replace edits:**

| Location | Current | Replacement |
|---|---|---|
| §2.5 architectural implication | "Mode A (skill challenge) probably produces more dramatic; Mode B (standard init) probably produces more operational. Goal is roughly balanced." | "Tier 0 (skill challenge) probably produces more dramatic; Tiers 1-3 (standard init) probably produces more operational. Goal is roughly balanced." |
| §7 Combat layer questions | "Does Mode B (standard Avrae init + LLM narration) feel functional in conversational multiplayer?" | "Does dumb combat (HCN Tier 1-3 — standard Avrae init + LLM narration) feel functional in conversational multiplayer?" |
| §7 Combat layer questions | "Does Mode A (skill challenge for trivial conflicts) earn its keep?" | "Does Tier 0 (skill challenge for trivial conflicts, per HCN §4.1) earn its keep?" |

---

## Notes on what I did NOT touch

Per Jordan's direction, skipped the rest of the §2-§3 flags from the prior review (§2.1 meaningful-decision definition, §2.2 voice-channel scope, §2.6 momentum collapse anchor, §3.2 NPC continuity drift categorization, §3.3 faction motion reframe, §3.4 long-arc deferral, §3.5 fatigue separation, cross-cutting capture friction). Those stand as filed but not drafted.

## v2 changelog

- §5 verification table refined with five additive findings from Code's live recon: roll_outcome_drift wired-but-unverified, prompt_size breakouts don't sum to total, state_footer phase proper-case, missing `campaign=` field on two log lines, sibling log lines worth pairing
- §5.3 documents `cloud_router_finish_reason` print-vs-log format inconsistency as known and accepted (Finding B, deferred)
- Pre-playtest hygiene ship called out: verifier-error sentinel class (Finding A, shipping separately)
- Sections 2 and 3 unchanged from v1
