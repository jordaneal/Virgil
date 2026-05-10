# TRACK_7_2_REVIEW.md — Session 2 walk-through

Companion to `TRACK_7_2_SPEC.md` (post-amendment). Walks the still-OPEN §11 decisions (§11.A–§11.J) plus two newly-surfaced gaps (§11.Q, §11.R). Pre-locked items — §11.K, §11.L.1, §11.M, §11.N, §11.O, §11.P — are referenced as locked and not re-walked.

The review's job: make Session 2 fast. Each block is a trade-off restatement + recommended default + (where applicable) surfaced addition + Session-3 implementation risk.

---

### §11.A — Coalesce window duration

**Trade-off.** 15s captures concurrent multi-player input but stalls solo turns the full window when only one player is active; tighter (5–8s) cuts off the "second player typing" case the spec is built around.

**Recommended default.** Keep 15s non-combat / 1s combat (existing-system inertia). **Confidence: medium** — right number is empirical.

**Surfaced addition.** Spec proposes instrumenting `arbitration_chars`-shape window-fill rate, but doesn't define a numeric threshold for tightening. Recommend logging `single_actor_full_window=1` as a binary in the `arbitration:` line so the >90%-single-actor decision is observable without log post-processing.

**Session-3 risk.** Low. The window already exists in `ActionBatcher`; #2 just consumes its output differently. Session 3 doesn't touch the timer.

---

### §11.B — Merge semantics

**Trade-off.** Option 1 (natural-language sequence) trusts LLM with actor sequencing; Option 3 (bracketed actor headers) is bullet-proof but reads like stage direction. Option 1 + ACTOR_OMISSION gate (per §11.M) is the locked-amendment compromise — trust the LLM, catch silent drops structurally.

**Recommended default.** Option 1 (sequence, natural flow) for v1, with §11.M ACTOR_OMISSION as the structural backstop. **Confidence: medium-high** post-amendment — §11.M closes the previously soft observability claim.

**Surfaced addition.** None — §11.M's lock-in materially upgrades this from "trust + telemetry" to "trust + structural regen". The medium confidence pre-amendment is now closer to high.

**Session-3 risk.** Low-medium. Implementation risk is on the prompt phrasing of `combined_constraint` for sequence merge (§5.2 sample is generic; live LLM may need tighter binding language). Worth running 8.3's two-actor-non-contradictory test against real LLM before declaring ship-ready.

---

### §11.C — Cross-player override priority rule

**Trade-off.** Earlier-arrival binding wins → mechanical resolution beats social assertion (closes F-50 structurally). Costs: a fast-typer can lock outcomes another player can't reverse; pressure shifts to the LLM to render the loser's reaction believably.

**Recommended default.** Priority sort `WORLD_BOUNDARY > COMBAT > CAPABILITY > CHECK > FREE`, arrival timestamp tiebreak. Override constraint instructs LLM to narrate Player B's REACTION, not OUTCOME. **Confidence: high** — central design decision; alternatives reopen F-50.

**Surfaced addition.** Spec is implicit that arrival timestamp tiebreaks within-category but doesn't say where the timestamp comes from. ActionBatcher accumulates inputs in arrival order — the list order itself IS the timestamp signal. Worth making explicit: "tiebreak = list-index from ActionBatcher output, no separate timestamp field needed."

**Session-3 risk.** Low if the priority constants are pulled from a single `_CATEGORY_PRIORITY` mapping (matches #1's posture). Risk surface is the override constraint phrasing — if the LLM keeps narrating B's outcome anyway, that's a verification regen burden, not an arbitration bug.

---

### §11.D — Arbitration above or below 2A.3 off-turn drop?

**Trade-off.** Keeping arbitration BELOW 2A.3 preserves the architectural prior; v1 silently swallows legitimate D&D off-turn patterns (Uncanny Dodge, readied actions, held spells). Relaxing 2A.3 is a separate spec entirely.

**Recommended default.** Below 2A.3; do NOT relax. Reactions/holds out of scope, filed against future Avrae reaction-tracking path. **Confidence: high.**

**Session-3 risk.** Zero — Session 3 doesn't touch transport-layer code. The risk is doctrinal: if implementation tries to "be smart" about distinguishing legitimate off-turn input, it has crossed the spec boundary. Session 3 implementation must NOT add an off-turn input path.

---

### §11.E — Arbitration telemetry shape

**Trade-off.** Per-actor input chars adds verbosity but is the empirical baseline for "did one player drown out another in input volume" — useful for tuning merge plan from data.

**Recommended default.** Ship the proposed log shape. Drop `input_per_actor` if line width blows out. **Confidence: high.**

**Surfaced addition.** Spec doesn't specify what's in `ArbitrationResult.signals` (declared as `dict, telemetry-only; flattened for the log line`). Recommend the dataclass define explicit signal keys at impl time (matches #1's posture for `AdjudicationResult.signals`) so log-line render isn't a free-form dict-flatten.

**Session-3 risk.** Low. Telemetry shape is mechanical; tighten in code review. Risk is forgetting the bottom-of-prompt hard-stop echo per §6.1 (multi-actor turns get a multi-line echo, not single-line) — that's a render-not-telemetry concern but easily missed.

---

### §11.F — Verification violation classes

**Trade-off.** Four locked classes (FABRICATED_COMBATANT, VERDICT_CONTRADICTION, STATE_MUTATION_CLAIM, ACTOR_OMISSION) are the multiplayer-test-surfaced shapes. Adding a fifth pre-ship (PLAYER_NARRATED_NPC_ACTION, UNSANCTIONED_LOCATION_TRANSITION, UNSANCTIONED_TIME_PASSAGE) over-fits to anticipated rather than observed leakage — the §11.E "default-to-roll" mistake from #1.

**Recommended default.** Ship the four locked. Surfaced alternatives stay filed for v2. **Confidence: high on the four; medium on whether a fifth ships pre-v1.**

**Surfaced addition.** PLAYER_NARRATED_NPC_ACTION is the strongest fifth-class candidate because §11.L.2 explicitly recommends it as input-side (extending `adjudicate()`), not output-side verification. If Jordan considers a v1 fifth class, recommend it lands in #1's `adjudicate()` extension as a separate sub-ship, not in #2's verification taxonomy. Don't expand #2's scope mid-spec.

**Session-3 risk.** Low. Class set is locked at four. Risk is empty `_FABRICATED_COMBATANT_VERBS` or `_STATE_MUTATION_PHRASES` lists — Code drafts these per Appendix A, but Session 3 must seed them before the verifier can fire. Worth a smoke-test of seed-list coverage against the F-49 narration shapes before declaring ship-ready.

---

### §11.G — On-detection mitigation

**Trade-off.** Regenerate (Option 1) buys highest-fidelity narration on retry success at 2x token cost. Redact/hold/post-with-footnote all degrade narrative quality or defeat the gate. Option 1 + Option 4 (deterministic placeholder fallback) is the "pay 2x on bad case, never silently ship a violation" balance.

**Recommended default.** Regen-once + escalate-to-placeholder. **Confidence: high** — Options 2 and 3 rule out; the only real question is regen-once vs zero-regen.

**Session-3 risk.** Low. Risk is the retry constraint phrasing being too generic — if the retry prompt says "don't violate" without naming the specific phrase from `detected_phrase`, the LLM tends to repeat the violation in a different form. §6.2's class-specific retry constraints already address this; Session 3 must implement them per-class, not generic.

---

### §11.H — Regen budget and retry behavior

**Trade-off.** 1 retry vs 2 is a token-budget/success-rate tradeoff; right answer is empirical. Spec defaults to 1; tune from observed retry success rate.

**Recommended default.** 1 retry, total LLM budget 2 calls/turn. Temperature unchanged on retry. **Confidence: medium** — empirical question.

**Surfaced addition.** Spec says retry temperature is "unchanged" but doesn't address whether retry uses the same `system` prompt or a tightened/restructured one. Recommend retry uses the SAME system prompt with `=== VERIFICATION FAILED ===` PREPENDED — consistent with §6.2's phrasing ("retry prompt prepends"). Avoid building a fork-shaped "retry prompt" path; that's premature abstraction.

**Session-3 risk.** Low. Risk is implementation accidentally drops the original constraint blocks on retry (rendering only the verification-failed block). The retry must include the FULL original prompt + verification-failed prepend. Session 3 should test this explicitly in `test_dm_respond_arbitration.py`.

---

### §11.I — Escalation when all retries violate

**Trade-off.** Deterministic placeholder narration breaks immersion but never silently ships a violation. Alternative paths (post-with-footnote, post-nothing) defeat the gate or produce silent failure.

**Recommended default.** Deterministic placeholder per §6.3 template. **Confidence: high** — principle locked; phrasing is impl detail.

**Surfaced addition.** §6.3 template uses `{verdict.skill}` and `{verdict.dc}` — these fields are AdjudicationResult attributes. Confirm both fields are reliably populated for non-CHECK verdicts (CAPABILITY refusal, COMBAT_REDIRECT may not have skill/DC). Template needs per-category branches, not a single template. Surfaced as a §6.3 implementation note, not a spec change.

**Session-3 risk.** Low-medium. Template per-category branching is a Session 3 trap if the spec template is treated as universal. Verify each verdict.category produces a coherent placeholder before ship.

---

### §11.J — Verification reuses adjudicate() or forks?

**Trade-off.** FORK = two modules to maintain. PARAMETERIZE = one module dispatching on actor type — premature abstraction the §63 doctrine was learned from. Sibling fork is cleaner per §63 (different actor, invariants, vocabulary, mitigation paths).

**Recommended default.** FORK. New `narration_verifier.py` parallel to `adjudicator.py`. Reuse only of dataclass shapes and canonical-state read helpers. **Confidence: high** — §63 explicit on this case.

**Session-3 risk.** Low if the fork stays clean. Risk surface: if `narration_verifier.py` starts importing helpers from `adjudicator.py` beyond the documented reuse list (canonical-state reads, dataclass shape, pure-function `(body, signals)` posture), the fork has slid back toward parameterization. Session 3 should keep the verifier's only `adjudicator` imports to the four declared.

---

### §11.Q — Actor-name source of truth for ACTOR_OMISSION substring (NEWLY SURFACED)

**Trade-off.** §11.M ACTOR_OMISSION substring-scans `arbitration_result.actor_order` against narration text. But the spec doesn't say what `actor_order` contains: Discord username (Jordan/Tazz), PC character name (Donovan/Bruce), or both. §5.2 prompt sample renders `JORDAN (Donovan)` — both — but doesn't say which of the two is in `actor_order`. The substring check's correctness depends on this.

- If `actor_order = ["Donovan", "Bruce"]` (PC names): substring works against narration but breaks when Discord-username-only references appear ("Jordan, you spin away").
- If `actor_order = ["Jordan", "Tazz"]` (Discord usernames): substring fails on every PC-narration reference (LLM rarely calls characters by player name).
- If `actor_order` carries both as a tuple: substring scan needs to test BOTH and OR-combine, which is a per-actor list of substrings, not a single string.

**Recommended default.** `actor_order = [PC_character_name, ...]` (Donovan/Bruce). LLM narration overwhelmingly uses character names. ACTOR_OMISSION substring scans character names only. The §5.2 prompt-render `JORDAN (Donovan)` shape is for HUMAN clarity in the prompt; the structural data uses character name. **Confidence: medium-high** — LLM output convention strongly favors character names; pronoun-aware extension (already filed v1.x per §11.M) handles the residual.

**Session-3 risk.** HIGH if left ambiguous. The substring scan is a one-line check; getting the field wrong silently inverts the false-positive rate. Session 3 must lock the field semantics in the dataclass docstring AND ship a test where `actor_order` content is asserted byte-exact for a multi-actor turn.

---

### §11.R — 3+-actor override semantics (NEWLY SURFACED)

**Trade-off.** `merge_plan: 'sequence' | 'override'` is a single per-turn string and `overridden_actor: str` is singular. Spec §5.1 step 3 says "for each adjacent pair in priority order, check: does verdict B contradict verdict A's bound resolution?" — a pairwise scan. The 3+-actor case is unspecified:

- A=CHECK success, B=FREE-contradicts-A, C=FREE-independent → merge_plan='override' captures A vs B but where does C land?
- A=CHECK success, B=FREE-independent, C=FREE-contradicts-A → adjacent-pair scan misses A vs C entirely (B sits between).
- Two simultaneous overrides (A vs B AND A vs C both contradict) → `overridden_actor: str` can only name one.

v1 multiplayer turns are realistically 2-actor (S25 #3 evidence); 3+ actor turns are rare but not impossible. Spec's pairwise+singular shape implicitly assumes 2-actor.

**Recommended default.** Lock v1 to 2-actor arbitration explicitly (third+ actors get queued for the next turn or dropped per ActionBatcher's existing behavior — verify which). Document the 2-actor assumption in `arbitrate()` docstring. 3+-actor handling files for v1.x once 2-actor logs accumulate. **Confidence: medium** — could equally lock as "all-pairs scan, list-shaped overridden_actors" if 3+ turns prove non-rare.

**Surfaced addition.** Recommend ArbitrationResult adds an explicit `actor_count_capped: bool` signal so 3+-actor truncation is observable in logs. If logs show truncation firing, v1.x widens to all-pairs.

**Session-3 risk.** MEDIUM if left ambiguous. Pairwise+singular shape may ship and silently mis-handle a real 3+-actor turn. Session 3 should either (a) explicitly cap arbitrate() input to 2 actors with the rest queued, or (b) implement all-pairs override detection with `overridden_actors: list[str]`. Either path needs the test fixture in `test_arbitration.py` 8.1 — currently 8.1 covers 1, 2, 3 actors but only for priority sort, not for 3+-actor override.

---

## Summary — items requiring Jordan's call this session

| Item | Recommended | Confidence | Session-3 risk if ambiguous |
|---|---|---|---|
| §11.A coalesce window | 15s/1s | medium | low |
| §11.B merge semantics | sequence + §11.M backstop | medium-high | low-medium |
| §11.C override priority | category > timestamp | high | low |
| §11.D 2A.3 boundary | below, no relax | high | zero |
| §11.E telemetry shape | proposed shape, drop chars if wide | high | low |
| §11.F violation classes | four locked, no fifth | high/medium | low |
| §11.G mitigation | regen + placeholder | high | low |
| §11.H regen budget | 1 retry | medium | low |
| §11.I escalation | placeholder per §6.3 | high | low-medium |
| §11.J fork vs param | FORK | high | low |
| **§11.Q actor-name source** | **PC character name in actor_order** | **medium-high** | **HIGH** |
| **§11.R 3+-actor shape** | **cap at 2 + signal** | **medium** | **MEDIUM** |

§11.Q is the highest-risk item this session: a one-line substring-scan field-semantics question that silently inverts ACTOR_OMISSION's FP rate if undefined. Lock it before Session 3 starts.

§11.R is the next-highest: pairwise+singular spec shape doesn't cleanly extend to 3+. Decide cap vs all-pairs; either is fine, but ambiguity ships a latent 3+-actor bug.

All other items have spec-stated recommendations with confidence sufficient to lock with light Jordan touch.
