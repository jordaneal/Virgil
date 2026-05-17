# §1b.1 Clarification Handshake Primitive — v0 Phase 2 Review

**Status:** Phase 2 review against S75 sketch + S74.5 locks + council pre-locks + macro-doctrine constraint.
**Date:** 2026-05-16
**Dispatch:** Path A Phase 2; Opus medium per WWC cadence.
**Output authority:** review-not-spec. Surfaces convergence + divergence; operator + Oracle locks at three explicit candidates pre-Phase-3.

---

## §1 — Phase 2 review summary

**Confidence split across 12 candidates walked:**

| Tier | Count | Candidates |
|---|---|---|
| HIGH | 8 | §11.1, §11.4 (council pre-lock), §11.6, §11.8, §11.9, §11.10, §11.11, §11.12 |
| MEDIUM-HIGH | 1 | §11.2 |
| MEDIUM | 1 | §11.3 |
| LOW | 2 | §11.5, §11.13 |

**Macro-doctrine review.** 10 of 12 candidates PASS the Inversion direction-lock litmus cleanly at sketch leans. §11.5 (predicate sharpness) and §11.13 (M-immediate vs M-delayed) are macro-doctrine-load-bearing — both explicitly operator + Oracle territory. **No HALT-class architectural impedance.** S74.5 locks + council pre-locks at §11.7 / §11.4 carry forward to operator-confirmation; neither surfaced friction at walk.

---

## §2 — §11 candidate walk

Per-candidate format: **Walk outcome** · **Three tests** (§F-59 / §1a / Inversion litmus) · **Implementation impact** · **Lock authority** · **Confidence**.

### §11.1 — Stage 1 routing placement

**Lean held.** Post-parser aggregation in new `clarification_handshake.py` module; bot integration is one call replacement at :2727. Living in new module (not in `discord_dnd_bot.py`) preserves separation of concerns. **Tests:** PASS/PASS/PASS — aggregation invisible to operator. **Impact:** none beyond Phase 3 scope. **Lock:** planner-level. **Confidence: HIGH.**

### §11.2 — Clarification Session State persistence

**Lean refined.** Restart-loss IS macro-doctrine-violating if silent (registered-then-dropped). Refinement: in-memory at v0 + **startup-side aside notification** on `on_ready` — "Active clarifications cleared by restart; please re-narrate." Preserves macro-doctrine without DB cost. DB-backed persistence revisits at v0.1 if restart-loss materializes as frequent friction. **Tests:** PASS/PASS/PASS-with-startup-notification (FAIL without). **Impact:** Phase 3 spec includes `on_ready` aside emission for any inflight sessions cleared by restart. **Lock:** planner-level with the refinement. **Confidence: MEDIUM-HIGH** — production may surface restart-loss frequency higher than expected.

### §11.3 — Multi-domain threshold

**Lean held but operator + Oracle territory.** ≥2 domains at ≥MEDIUM is **the primary metastasis defense at Stage 1**. Too loose → routine fires → operator trains command-shaped narration. Too strict → silent miss. Alternatives walked: ≥2 at ≥HIGH (stricter; misses MEDIUM×MEDIUM-real cases); ≥2 at ≥LOW (catastrophic). ≥2 at ≥MEDIUM defensible at v0 but production telemetry must gate v0.x re-tuning (paste-rate vs ignore-rate per fire). **Tests:** PASS/PASS/**planner-uncertain** — depends on production fire rate. **Impact:** module-level constant for v0.x tunability. **Lock:** **OPERATOR + ORACLE** — empirical-tuning sensitivity. **Confidence: MEDIUM.**

### §11.4 — Layer A vs Layer B routing

**Council pre-lock confirmed by sample-walk.** Rule B.3/B.4 (bounded-resolvability):

- "I'll take it" (3 candidates) → **Layer A multi-paste** ✓
- "I hand 5gp to Garrick" (1 candidate + markers + OOV verb) → **Layer A "did you mean transaction?"** framing variance ✓
- "Something weird happened" (no candidates, no markers) → **silent log** ✓
- "Garrick mumbles something and gestures" (no candidates, ambiguous markers) → **depends on §11.5 predicate**: if predicate requires ≥2 markers AND ≥1 structured-state marker, 1 NPC-name alone fails predicate → silent log; if loose-predicate, triggers → Layer B

**Tests:** PASS/PASS/PASS — rule is sharp; metastasis-control delegated to §11.5 predicate, not §11.4 boundary. **Impact:** Phase 3 encodes `if 1 <= len(candidates) <= 4: A; elif markers_present and no_candidates: B; else silent`. **Lock:** council pre-lock; **operator confirmation at Phase 2 lock**. **Confidence: HIGH** (pending operator confirm).

### §11.5 — Structural-markers detector predicate

**The sharpest metastasis-defense surface.** Loose → constant Layer A on every NPC-mention turn → catastrophic. Tight → silent-log on intended cases → primitive fails to land. **Planner-recommended predicate:** `has_structural_markers(narration_tokens, campaign_id) -> dict[str, bool]` over `{npc, currency, item, location}`. Trigger requires **(a) ≥2 markers AND (b) ≥1 structured-state marker** (currency-regex OR `get_pending_loot` match OR `get_offered_quests` title match — NPC-name and location-name alone are too common in flavor prose). Co-occurrence with out-of-vocab verb already locked at S74.5. **Tests:** PASS/PASS/**depends on sharpness lock** — recommended predicate passes; loose alternatives fail. **Impact:** Phase 3 implements predicate + per-marker telemetry (which marker types fired) for v0.x tuning. **Lock:** **OPERATOR + ORACLE** — macro-doctrine load-bearing. **Confidence: LOW** at planner level.

### §11.6 — Timeout default

**Lean refined.** 5min v0 + telemetry on `clarification_expired` rate. Pending-state has no ambient effects (listener doesn't gate other behaviors per R2) — longer timeouts are "free" except for occupying session-cap slots (§11.8). If expired-rate > 30% in production, shorten to 2-3min at v0.x. **Tests:** PASS/PASS/PASS — silent expiry preserves macro-experience. **Impact:** module-level constant `_CLARIFICATION_TIMEOUT_SECONDS = 300`. **Lock:** planner-level. **Confidence: HIGH.**

### §11.8 — Per-scene active-session cap

**Lean held.** 3 concurrent; cap-hit silent-logs + telemetry. Production likely surfaces 1 ambiguity at a time as typical; 3+ rare. Operator-notification at cap-hit ("tracking too many ambiguities") would violate flow — explicit reject. **Tests:** PASS/PASS/PASS. **Impact:** module-level constant. **Lock:** planner-level. **Confidence: HIGH.**

### §11.9 — Recursion handling

**Lean refined on framing language.** Iteration 2 framed as *narrowing* not *escalating*: "I'm narrowing this down — is it [A] `/quest accept 7` or [B] `/inventory add healing_potion 1`? Or 'skip'." Iteration 3 manual-decision card explicit-but-terse: "Pick one and paste, or 'skip'." **Tests:** PASS/PASS/PASS — framing tweaks; recursion itself rare. **Impact:** card-renderer language locked at Phase 3. **Lock:** planner-level. **Confidence: HIGH.**

### §11.10 — Phase 3b parser integration

**Lean held.** Phase 3b's transaction-completion + loot-drop parsers return per-domain confidences; aggregator routes ambiguities via Rule B.3/B.4. Phase 3b code stays scope-bounded (parser implementations only; no clarification logic). Phase 3b dispatch references §1b.1 as already-shipped infrastructure. **Tests:** PASS/PASS/PASS — Phase 3b inherits §1b.1 transparently; fire rate governed by §11.5 sharpness. **Impact:** Phase 3b's parser-set registry includes transaction + loot-drop at ship. **Lock:** planner-level. **Confidence: HIGH.**

### §11.11 — Card anchor drift handling

**Planner discipline rule.** S75 surfaced S70-R4 anchors stale (:548/:684/:5917/:6440/:6512 → actuals :540/:671/:3080/:6545). Standing rule: dispatches name **structural property** ("card-precedent surface"), never cite line numbers verbatim from prior dispatches. File as WORKING_WITH_CLAUDE.md amendment at §1b.1 anchoring time. **Tests:** N/A (planner discipline). **Impact:** WWC amendment at Phase 3 close. **Lock:** planner-level. **Confidence: HIGH.**

### §11.12 — `bot.wait_for` first-use precedent

**Pattern review clean.** (a) TimeoutError handling via try/except. (b) Concurrent message-handler conflicts: filter scopes prevent (channel + author + timestamp + !bot). (c) Restart-state: in-memory dies (mitigated by §11.2 startup notification). (d) During message-handler latency: asyncio-based, non-blocking. (e) Filter correctness: tests cover spoofing (operator-impersonating, bot's own messages). **Tests:** PASS/PASS/PASS — listener doesn't make bot unresponsive. **Impact:** Phase 3 test coverage on filter correctness, timeout, concurrent-handler non-blocking, restart-side state-loss notification. **Lock:** planner-level. **Confidence: HIGH.**

### §11.13 — Layer A immediate-fire vs delay-by-one-turn (NEW)

**Two shapes:**

- **Shape M-immediate** (sketch baseline): Layer A fires on first detection of 1-candidate-with-markers ambiguity.
- **Shape M-delayed** (Gemini): parser detects → engine flags LLM → LLM narrates in-fiction continuation inviting clarification → second parser pass → IF still ambiguous → Layer A fires.

**Doctrinal cleanliness.** Both PASS §1a (engine informs LLM; LLM doesn't decide), §F-59 (paste/OOC-reply still required), §76 (engine→LLM directive, not LLM→state). Shape M-delayed introduces **F-64 mitigation requirement** (LLM MUST NOT narrate transaction as completed; only Garrick's waiting/acknowledging behavior) — empirical LLM-compliance risk.

**Inversion litmus.** M-delayed passes more aggressively (in-fiction clarification first; OOC handshake only on failure). M-immediate passes IF §11.5 predicate is sharp enough to keep fire-rate low.

**Risks.**
- **M-immediate:** OOC interrupts at every 1-candidate-with-markers fire; metastasis if §11.5 loose.
- **M-delayed:** LLM-compliance with "don't narrate as committed" is empirical; player-comprehension that in-fiction signal IS a clarification cue is empirical; 2-turn latency before OOC interrupt feels different than 1-OOC-interrupt.

**Planner lean.** **Shape M-immediate v0 + sharp §11.5 + production telemetry gates v0.x walk of M-delayed.** Reasoning: M-delayed is interesting but adds LLM-prompting complexity and unverified player-comprehension at v0 ship. M-immediate ships clean with metastasis-defense delegated to §11.5 predicate sharpness. IF production telemetry shows ignore-rate > 30% on 1-candidate-with-markers fires OR operator narration patterns shift, v0.x earns M-delayed walk.

**Tests:** Both PASS §F-59 and §1a; Inversion litmus M-immediate-CONDITIONAL on §11.5 / M-delayed-CLEANER-BUT-COMPLEX. **Impact:** M-immediate ships at sketch baseline; M-delayed requires Phase 3 spec expansion (context-flag protocol + LLM-prompting language). **Lock:** **OPERATOR + ORACLE** — highest-stakes macro-doctrine choice at v0. **Confidence: LOW** at planner level.

---

## §3 — R-finding integration check

| R | S75 status | S76 confirm |
|---|---|---|
| R1 — parser return shape | CLEAN | CLEAN |
| R2 — `_post_dm_aside` × `wait_for` | CLEAN | CLEAN |
| R3 — discord.py TimeoutError | CLEAN | CLEAN |
| R4 — telemetry schema extension | CLEAN | CLEAN |
| R5 — structural-markers predicate | CANDIDATE | **RESOLVED at §11.5** (planner recommendation; awaits operator + Oracle lock) |
| R6 — pre-LLM hook aggregator integration | CLEAN | CLEAN |

**No drift surfaced between S75 sketch and S76 review.** R5 graduates to operator + Oracle territory at §11.5 with planner-recommended sharpness.

---

## §4 — Macro-doctrine review summary

**Inversion direction-lock litmus pass-rate across 12 candidates:**

| Result | Count | Candidates |
|---|---|---|
| PASS (unconditional) | 8 | §11.1, §11.2 (with startup notification), §11.4, §11.6, §11.8, §11.9, §11.10, §11.12 |
| PASS (conditional on operator+Oracle lock) | 2 | §11.3, §11.13 |
| DEPENDS on lock | 1 | §11.5 (sharp passes; loose fails) |
| N/A | 1 | §11.11 (planner discipline) |

**Three macro-doctrine load-bearing candidates** govern metastasis vs rare-and-clean:

1. **§11.5 predicate sharpness** — sharpest metastasis defense. Planner-recommended (≥2 markers + ≥1 structured-state) defensible but unverified.
2. **§11.3 multi-domain threshold** — secondary metastasis defense. ≥2 at ≥MEDIUM defensible at v0; tunable at v0.x.
3. **§11.13 M-immediate vs M-delayed** — highest-stakes architectural choice. M-immediate ships clean if §11.5 sharp; M-delayed preserves Inversion direction-lock more aggressively but adds complexity.

**Convergence shape.** If operator + Oracle locks M-immediate + sharp §11.5 + ≥2-at-≥MEDIUM §11.3, primitive ships at sketch baseline with macro-doctrine preserved via predicate sharpness. If operator + Oracle locks M-delayed, Phase 3 dispatch shape expands materially.

---

## §5 — Operator + Oracle escalation list

**Three candidates remain OPEN for operator + Oracle convergence pre-Phase-3-dispatch:**

| § | Decision | Planner lean | Why operator + Oracle |
|---|---|---|---|
| **§11.3** | Multi-domain threshold | ≥2 domains at ≥MEDIUM | Production-tuning sensitivity; planner can't validate empirically |
| **§11.5** | Structural-markers predicate sharpness | ≥2 markers + ≥1 structured-state marker | Sharpest metastasis defense; macro-doctrine load-bearing |
| **§11.13** | Layer A immediate vs delayed | M-immediate v0 + sharp §11.5 + v0.x telemetry-gated M-delayed walk | Highest-stakes architectural choice |

**Council pre-lock operator-confirmation status:**

| § | Council pre-lock | Operator-confirmation |
|---|---|---|
| **§11.7** | Shape A.2 (one-paste; OOC reply IS gate) | Walk surfaced no friction; awaits operator confirmation |
| **§11.4** | Rule B.3/B.4 (bounded-resolvability) | Sample-walk validated; awaits operator confirmation |

---

## §6 — Recommended Phase 3 implementation sequencing

**Single-arc ship: Layer A + Layer B in same Phase 3 dispatch.** S74.5 locked single-arc; review surfaces no impedance forcing split. Both layers share aggregator + session-state primitives in `clarification_handshake.py`; splitting duplicates scaffolding cost.

**Sequencing within Phase 3 implementation:**

1. `clarification_handshake.py` module scaffolding — dataclass, state dicts, predicate, routing rules, card renderers, listener wrapper, telemetry hooks. Pure-function or async-leaf surface; testable in isolation.
2. Aggregator integration at pre-LLM hook (:2727) — replace single `_run_quest_acceptance_detection` task with `_run_inversion_aggregator`.
3. Layer A card-renderer + post path — multi-paste card via existing `_post_dm_aside` (:422).
4. Layer B listener + reply handler — `bot.wait_for` wrapper + on_message intercept for PENDING-session replies.
5. Telemetry extension — new event types + payload fields per §5 of sketch.
6. Startup-side `on_ready` aside notification for restart-cleared sessions (per §11.2).
7. Test coverage per S75 test-file list + §11.12 filter-correctness/spoofing additions.

**Model tier recommendation for Phase 3 dispatch:** Sonnet medium per Phase 3a precedent IF operator + Oracle locks M-immediate at §11.13. **Bump to Opus medium IF operator + Oracle locks M-delayed at §11.13** — context-flag protocol + LLM-prompting language is synthesis-heavy.

---

## End-of-review summary

- **Review covers §1–§6 per dispatch.** Length: ~14k chars (within 10-15k target after compression pass).
- **12 candidates walked** + R-finding integration confirm + macro-doctrine pass-rate analysis.
- **No HALT-class impedance.** S74.5 + council pre-locks survive.
- **3 candidates OPEN for operator + Oracle:** §11.3 / §11.5 / §11.13 — all macro-doctrine load-bearing.
- **2 council pre-locks await operator confirmation:** §11.7 / §11.4.
- **Macro-doctrine constraint operationalized.** 10 of 12 PASS unconditionally; 2 conditional on operator + Oracle locks; 1 dependent on lock direction.

**Next session.** S77 Phase 3 implementation. Sonnet medium per WWC default; Opus medium conditional bump if §11.13 locks M-delayed. Operator + Oracle resolution on §11.3 / §11.5 / §11.13 + council pre-lock confirmation on §11.4 / §11.7 gates Phase 3 dispatch.
