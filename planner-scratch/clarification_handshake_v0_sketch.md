# §1b.1 Clarification Handshake Primitive — v0 Architectural Sketch

**Status:** Phase 1 sketch — pre-spec. §11 candidates surfaced, not locked.
**Date:** 2026-05-16
**Dispatch:** Path A Phase 1 per S74.5 operator-lock; single architectural arc shipping Layer A + Layer B in v0.

---

## §1 — Primitive's place in architecture

§1b.1 sits between §1a.x's *parser fires* and §1b's *operator pastes*. When a closed-vocab parser produces an **ambiguous structured signal** (multi-domain match, cross-domain semantic equivalence, or vocab near-miss with structural markers), §1b.1 inserts an **operator-disambiguation step** before §1b's validated-suggester gate fires.

**Load-bearing claim.** Closed-vocab parsers will always have ambiguity surfaces. §1b.1 surfaces ambiguity to the operator OOC rather than: (a) expanding vocabulary indefinitely (violates §1a.x prerequisite #1); or (b) silently committing to one interpretation (wrong-state writes; violates THE_GOAL.md operator-agency commitment).

**Doctrinal composition.** §1a (no LLM-decided binding state) — unchanged; §1b.1's operator-disambiguation IS the binding-decision step. §1a.x (closed-vocab parser as deterministic gate) — input to §1b.1 is parser output; §1b.1 routes, does not classify. §1b (validated-suggester) — Layer A is §1b card-content extension; Layer B is a new §1b instance shape. §F-59 (bot never auto-emits) — holds throughout (see §11.7 for the strict-vs-direct-write resolution).

DOCTRINE §1b §45's "sub-anchor question returns at Phase 3c" — answered one ship earlier and structurally: §1b.1 is formal sub-clause; §1b retains running-list of instance shapes. §1b instance count unaffected (§1b.1 composes ACROSS instances, doesn't add one).

---

## §2 — Two-layer architecture concrete shape

### Layer A — Richer suggester cards (card-content surface only)

**Mechanism.** No new infrastructure. Card body lists multiple candidate domains/records, each with its own pasteable slash. Operator pastes the correct one (or none). Existing §1b validation fires on paste.

**Canonical S74 example — "I'll take it":**

```
**[OPERATOR DISAMBIGUATION — multiple actions detected]**
Narration: _"I'll take it"_
Candidates:

A) Quest acceptance — Quest #7 "Stoneforge's Errand"
   `/quest accept 7`

B) Transaction completion — purchase from Brak (5gp · healing potion)
   `/inventory add healing_potion 1; /coin deduct 5gp`

C) Loot drop pickup — silver dagger (pending)
   `/loot claim silver_dagger`

_Paste the correct slash, or ignore if none apply._
```

**Renderer:** new helper `_format_clarification_card_layer_a(candidates)` in `clarification_handshake.py`, sibling to `_format_quest_offer_card` (:540), `_format_quest_act_card` (:671), `_format_quest_acceptance_suggester_card` (:3080), `_format_bootstrap_card` (:6545). Reuses `_post_dm_aside` (:422).

### Layer B — Bidirectional OOC handshake

**Mechanism.** Truly ambiguous case; structural markers don't enumerate candidates. Bot posts free-text question to #dm-aside; enters listening state via `bot.wait_for('message', check=..., timeout=300)`; operator replies free-text OOC; bot integrates reply into structured proposal and writes (resolution surface per §11.7 lock).

**Example — out-of-vocab verb + structural markers:**

```
**[OPERATOR CLARIFICATION REQUEST]**
Narration: _"He extends a small leather pouch"_
Detected: out-of-vocab verb + structural markers
(NPC: Brak · currency: 5gp · item-like: leather pouch · location: Westmarket Inn).

Reply with one of:
  "transaction" — record purchase/sale
  "loot" — record item pickup
  "npc offer" — record NPC giving party an item
  "skip" — no engine write

(5-minute window; clarification expires silently after.)
```

**Async listener shape:**

```python
def _check(m: discord.Message) -> bool:
    return (m.channel.id == aside_channel.id
            and m.author.id == controller_id
            and m.id > trigger_message_id
            and not m.author.bot)
try:
    reply = await bot.wait_for('message', check=_check, timeout=300)
except asyncio.TimeoutError:
    # silent fallback per S74.5 lock; clear pending state; telemetry expired
```

**Non-interference guarantee.** Filter scopes to `(channel, controller, post-timestamp, !bot)`. Concurrent suggester-card posts from other domains don't match (bot is author). No conflict.

---

## §3 — Clarification Session State

```python
@dataclass
class ClarificationSession:
    campaign_id: int
    controller_id: str            # Discord user ID
    trigger_event_id: str         # parser-emitted dedup key
    candidates: list | str        # list of dicts (A) | free-text question (B)
    layer: Literal["A", "B"]
    status: Literal["PENDING", "RESOLVED", "EXPIRED"]
    iteration: int                # for 2-iteration recursion cap
    created_at: float
    timeout_at: float
```

**Storage lean:** in-memory module-level dict keyed by `(campaign_id, controller_id)` in `clarification_handshake.py`. Sessions are 5-min ephemeral; restart-resilience adds complexity without v0 payoff. Persistence revisit at v0.1 if production data shows restart-loss is material.

**Per-scene cap.** Module-level counter `(campaign_id, scene_id) → int`. ≥3 active → trigger silent-log + `clarification_fatigue_capped` telemetry. Releases on RESOLVED / EXPIRED.

---

## §4 — Trigger routing (Stage 1 domain + Stage 2 within-domain)

### Stage 1 — Domain routing (NEW)

| Condition | Route |
|---|---|
| Exactly 1 domain at ≥MEDIUM | Stage 2 (existing §1a.x tiers fire) |
| ≥2 domains at ≥MEDIUM | **Layer A** (multi-domain match) |
| Same verb fires ≥2 domains with distinct structured signals | **Layer A** (cross-domain equivalence) |
| 0 domains, ≥2 structural markers + out-of-vocab verb | **Layer A** if markers enumerate ≤4 candidates; **Layer B** if open-ended |
| 0 domains, no structural markers | silent log |

### Stage 2 — Within-domain confidence (UNCHANGED §1a.x)

HIGH / MEDIUM-with-offered / MEDIUM-no-offered / LOW — Phase 3a tiers fire normally on Stage 1's single-domain-clear route.

### Stage 1 placement

**Lean: post-parser aggregation.** Per-domain parsers stay independent pure-function leaves. New aggregator runs all v0 parsers in parallel at pre-LLM hook (currently quest_accept at :2727; Phase 3b adds transaction + loot_drop alongside), collects `dict[domain, ParseResult]`, then `evaluate_routing()` decides Layer A / B / single-domain pass-through / silent. Pre-parser orchestration was considered and rejected: would couple every new parser ship to the orchestrator. Post-parser keeps parsers drop-in.

---

## §5 — Implementation surface targets

### New module: `clarification_handshake.py`

| Symbol | Role |
|---|---|
| `ClarificationSession` | dataclass per §3 |
| `_ACTIVE_SESSIONS`, `_SCENE_SESSION_COUNTS` | module-level state |
| `evaluate_routing(per_domain_results, structural_markers, ...)` | Stage 1 decision |
| `format_layer_a_card(candidates)` | card renderer |
| `format_layer_b_question(domain_hint, markers)` | free-text renderer |
| `await_clarification_reply(bot, guild, controller_id, timeout=300)` | `bot.wait_for` wrapper |
| `has_structural_markers(narration_tokens, campaign_id)` | predicate (R5) |
| `resolve_session(session, operator_reply_or_paste)` | recursion cap + RESOLVED |

### `discord_dnd_bot.py` integration

- Replace single `_run_quest_acceptance_detection` task at :2727 with `_run_inversion_aggregator(campaign_id, action, message.guild, controller_id)` running all v0 parsers in parallel + routing via `evaluate_routing()`.
- Add clarification-reply intercept at top of `on_message`: if PENDING session exists for `(campaign_id, message.author.id)` and `channel == aside`, route to `resolve_session()` and short-circuit normal narration routing.
- No new `_format_*` insertions here — renderers live in `clarification_handshake.py`, deliver via existing `_post_dm_aside` (:422).

### `inversion_telemetry.py` extension

New event types: `clarification_fired`, `clarification_resolved`, `clarification_expired`, `clarification_recursion_escalated`, `clarification_fatigue_capped`. New payload fields: `layer`, `iteration`, `resolution_mode` (`paste`/`freetext`/`timeout`/`recursion`), `candidate_count`. Fits existing `emit(event, domain, payload)` shape — no schema bump.

### `dnd_engine.py`

No schema changes anticipated. Stage 1 reads each parser's existing return dict. Phase 3b parsers ship with same shape per §1a.x prerequisite #3.

### NEW test files

`test_clarification_handshake_layer_a.py`, `test_clarification_handshake_layer_b.py`, `test_clarification_session_state.py`, `test_clarification_trigger_routing.py`.

---

## §6 — Failure modes tracked empirically

1. **Clarification fatigue.** Per-scene cap = 3 active sessions; excess silent-log + telemetry.
2. **Trust erosion (false positives).** Telemetry: `operator_paste_rate` vs `operator_ignore_rate` per Layer A card; > 30% ignore-rate → re-tighten Stage 1 trigger for that domain. Structural-markers-carve-out boundary is load-bearing.
3. **GUI-via-text drift.** Watch operator narration patterns; if narrations adapt to trigger clarification system, primitive failed, threshold tightens.
4. **Prompt contamination.** Verify at implementation: clarification text MUST NOT leak into LLM context. S65 separation (`#dm-aside` quarantined from prompt) holds for Layer A by inheritance; Layer B free-text posts MUST inherit same separation. Verify at `build_dm_context` (dnd_engine:6226) at Phase 3 review.
5. **Doctrine fragmentation.** Scope to parser-input ambiguity. NOT generalized to "ask operator anything." Phase 2 spec language locks this.

---

## §7 — Recon-first items for Phase 2 (R1–R6 status)

| ID | Item | Status | Notes |
|---|---|---|---|
| **R1** | Parser return shape | **CLEAN** | `parse_quest_acceptance` returns `fired`/`confidence`/`matched_verb`/`matched_quest_id`/`matched_quest_title`/`dedup_suppressed`/`feature_disabled`. Aggregator reads directly. Phase 3b parsers inherit shape per §1a.x prereq #3. |
| **R2** | `_post_dm_aside` × Layer B listener | **CLEAN** | Filter `(channel, author, timestamp, !bot)`; concurrent bot posts don't match (bot is author). |
| **R3** | Discord `wait_for` timeout | **CLEAN** | discord.py raises `asyncio.TimeoutError` on timeout. `bot = commands.Bot(...)` confirmed at :1136. |
| **R4** | Telemetry event-taxonomy extension | **CLEAN** | `emit(event, domain, payload)` accepts arbitrary payload dict; new events fit; no schema bump. |
| **R5** | Structural markers detector | **CANDIDATE** | Available accessors: `get_recently_active_npcs` (dnd_engine:4694), `get_pending_loot` (:3045), `get_inventory` (:2933), `get_offered_quests`; currency regex per S74 proposal. Combine into `has_structural_markers(narration_tokens, campaign_id) -> dict[str, bool]` over `{npc, currency, item, location}`. ≥2 True + out-of-vocab verb = Layer A/B candidate. Predicate spec at Phase 2. |
| **R6** | Multi-domain aggregation site | **CLEAN** | Pre-LLM hook at :2727 currently fires single async task. Replace with `_run_inversion_aggregator` (parallel parser fan-out + aggregation). Phase 3b folds in via parser-set registry without on_message wiring changes. |

### Architectural-impedance findings (no HALT escalations)

- **Dispatch's R4 anchor lines stale.** Dispatch cites `:548, :684, :5917, :6440, :6512` as five card precedents from S70. Verified actual precedents at **`:540, :671, :3080, :6545`** (4 instances, not 5). `:5917`/`:6440`/`:6512` are slash-handler error replies, command-tree-registration, and a constants dict — not cards. **S73.1 lesson re-applies.** Surfaces as §11.10.
- **`bot.wait_for` is a NEW pattern in discord_dnd_bot.py.** No prior usage (all three `wait_for` greps are `asyncio.wait_for`, different API). Layer B is first user. Risk: discord.py version + filter correctness at Phase 3. Surfaces as §11.11.
- **No HALT-class items.** All S74.5 locks survive recon.

---

## §8 — §11 candidates for Phase 2 lock

| # | Candidate | Code lean |
|---|---|---|
| **§11.1** | Stage 1 routing placement | **post-parser aggregation** (preserves parser purity; pre-parser orchestration would couple new parsers to orchestrator) |
| **§11.2** | Session state persistence | **in-memory dict** (5-min ephemeral; revisit at v0.1) |
| **§11.3** | Multi-domain match threshold | **≥2 domains at ≥MEDIUM** (HIGH-only is strict-but-misses; operator dismissal is cheap) |
| **§11.4** | Layer A vs Layer B routing | **≤4 enumerable candidates → A; open-ended → B**. Edge: 1-domain inferred from markers + out-of-vocab verb → Layer A with single candidate + "skip" (markers narrow domain) |
| **§11.5** | Timeout default | **5 min, operator-configurable per campaign** |
| **§11.6** | Per-scene cap | **3 concurrent** (operator-tunable; telemetry tracks fatigue) |
| **§11.7** | Layer B post-resolution write surface | **TWO LEANS — operator + Oracle call.** (a) Strict §F-59: free-text reply triggers a final pasteable-slash card; operator paste of THAT slash fires §17 writer (two-paste shape). (b) Pragmatic: free-text reply IS approval at disambiguation level; bot writes via §17 directly (one-paste shape). Lean (a) preserves §F-59 strict reading; lean (b) is faster UX. **Open for Phase 2 walk.** |
| **§11.8** | Operator-reply ambiguity (recursion) | **iter 2 = explicit binary forced-choice card; iter 3 = manual-decision card + escalation telemetry** (2-iter cap from S74.5 lock; iter-3 is Layer A at maximum constraint) |
| **§11.9** | Phase 3b parser integration | **Phase 3b parsers ship through §1b.1 aggregator from day one**; multi-paste cards surface naturally on first multi-domain fire |
| **§11.10** | Card precedent anchor drift (NEW from sketch) | **use verified anchors :540, :671, :3080, :6545**. Dispatch R4 lines stale (S73.1 lesson); Phase 2 spec uses verified set |
| **§11.11** | `bot.wait_for` as new codebase pattern (NEW) | **add as first-use precedent; test coverage at Phase 3**; discord.py version + filter correctness verified at implementation |
| **§11.12** | Layer A/B edge case rule (NEW) | **1-candidate-with-markers → Layer A + skip option**, not Layer B (markers narrow to one domain; Layer B reserved for genuinely open-ended). Tightens §11.4 boundary |

---

## §9 — Doctrinal anchoring at Phase 3 ship

**§1b.1 anchor instance language (drafted for Phase 3 close, NOT this phase):**

> **§1b.1 — Operator-disambiguation primitive (anchored at S[Phase 3 ship session]).**
>
> Anchored at first firing instance: campaign [X], utterance _"[Y]"_, Layer [A|B] fired first in production. Two-layer architecture (Layer A multi-paste suggester-card extension + Layer B bidirectional OOC handshake via `bot.wait_for`) per `clarification_handshake.py` + Stage 1 aggregation at pre-LLM hook + §17-disciplined writers downstream.
>
> §1b instance lineage at §1b.1 ship: Phase 3a quest-acceptance (6th) routes through §1b.1 from this Phase 3 close onward; Phase 3b transaction-completion (7th) + loot-drop (8th) inherit §1b.1's clarification surface from their Phase 3b ship time.
>
> Sub-clause status: §1b.1 formally anchored as sub-clause per §76.1/.2 sub-numbering precedent. Authority claim is **operator-disambiguated parser output**; the §1b validated-suggester gate fires on the disambiguated proposal.
>
> §F-59 holds throughout — Layer A is paste-only; Layer B's resolution surface per §11.7 lock.

**Sub-anchor question (DOCTRINE §1b §45) RESOLVED.** §1b.1 is formal sub-clause; §1b retains running-list of instance shapes. Both compositions hold.

---

## End-of-sketch summary

- **Sketch covers §1–§9 per dispatch.** Length: ~12k chars.
- **12 §11 candidates surfaced** — 9 from dispatch §8 + 3 sketch-new (§11.10 anchor drift, §11.11 `wait_for` precedent, §11.12 Layer A/B edge).
- **R1–R6 status:** 5 CLEAN, 1 CANDIDATE (R5 structural-markers predicate — accessors confirmed, predicate spec at Phase 2).
- **2 architectural-impedance findings** surfaced to Phase 2 (NEITHER is HALT-class): stale dispatch anchors (S73.1 lesson) and `bot.wait_for` new-pattern risk.
- **No code, no DOCTRINE/SESSIONS/VIRGIL_MASTER amendments** at sketch phase. Phase 3 close lands amendments per per-checkpoint timing lock (S72).
- **Phase 2 convergence-heavy stops:** §11.7 (Layer B write surface — strict-§F-59 vs faster-direct-write) and §11.4 (Layer A/B edge cases) — both reserved for operator + Oracle.

**Next session.** S76 Phase 2 review pass — Opus medium per WWC cadence.
