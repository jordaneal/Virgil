# S78 Phase 3b — Recon Phase A Report

**Status:** Recon-first per F-60 + dispatch. Three architectural questions resolved.
**Date:** 2026-05-16
**Output authority:** recon-only. R3 resolution offered for operator + Oracle confirmation; implementation gated.

---

## R1 — `_COIN_TRANSACTION_VERBS` inventory

**Status:** CLEAN with drift surfaced.

Current state of `mechanical_hints.py:106` `_COIN_TRANSACTION_VERBS` frozenset (post-baker-scenario S65.1 hardening):

```python
{
  'paid', 'pays', 'paying', 'pay',
  'handed', 'handing',                              # 'hands' EXCLUDED
  'gave', 'gives', 'giving',
  'passed', 'passes', 'passing',
  'slid', 'slides', 'sliding',
  'dropped', 'drops', 'dropping',
  'tossed', 'tosses', 'tossing',
  'flipped', 'flips', 'flipping',
  'exchanged', 'exchanges', 'exchanging',
  'pocketed', 'pockets', 'pocketing',
  'accepted', 'accepts', 'accepting',
  'received', 'receives', 'receiving',
  'took', 'takes', 'taking',
  'placed', 'placing',                              # 'places' EXCLUDED
  'spent', 'spending', 'spends',
  'transferred', 'transfers',
  'counted', 'counts', 'counting',
}
```

**Count: 47 verbs.** S74 recon documentation cited 18. The vocabulary has expanded since S74 — the S65.1 baker-scenario hardening added many tense variants (pocketed/pockets/pocketing; received/receives/receiving; exchanged/exchanges/exchanging; etc.) to match LLM 3rd-person paraphrase coverage per S73.1 lesson. Two noun-overlap traps explicitly excluded: `'hands'` (body part) and `'places'` (locations).

**Drift impact:** S78 dispatch's "18-verb overlap" framing is stale; correct overlap is 47 verbs. Does not change R3 resolution structure — vocabulary OVERLAPS, not vocabulary identity, is what matters.

---

## R2 — N-1 downstream consumers

**Status:** CLEAN. Single consumer, isolated surface.

**Sole consumer:** `discord_dnd_bot.py:2806` `_attach_hints()` background task, invoked from `_dm_respond_and_post` at `:4251` (post-LLM, after DM narration posts).

**Operator-visible behavior:** N-1 fires AFTER the DM narration embed has been posted; it then edits the embed in place to append a bullet list of validated Avrae bookkeeping commands:

```
- `!game coin -5gp`
- `!game shortrest`
```

Appended to the embed description in `#dm-narration` channel. Soft-fail (timeout 5s, silent on errors).

**Mechanism (verified):**
- Stage 0: `parse_mechanical_hints(narration, campaign_id)` makes an LLM call via `cloud_router.route(task_type='extraction')` — this is N-1's classification mechanism.
- Stage 1: LLM-emitted candidates pass through schema `_validate()` whitelist (`!game coin ±Ngp`, `!game longrest`, `!game shortrest`).
- Stage 2: **transaction-verb gate** (the `_COIN_TRANSACTION_VERBS` frozenset). Coin hints survive only if narration contains at least one verb from the set. Rest hints are NOT gated this way (LLM prompt's rest examples gate them upstream).
- Stage 3: cross-turn dedup (process-local 12-entry LRU per campaign).
- Stage 4: per-fire telemetry (`hint_extractor_emitted` / `hint_extractor_suppressed`).

**Key architectural observation:** N-1 uses the verb frozenset as a **suppression gate**, NOT as the detection mechanism. Detection is an LLM call (which would violate §1a.x prerequisite #1 if N-1 were doctrinally framed as a §1a.x parser — it is not; N-1 predates §1a.x and is doctrinally framed as Phase 11.1 advisory parser with whitelist-validated output, NOT structural-state mutation).

**Test coverage:** `test_mechanical_hints.py` (mocks `cloud_router.route`, exercises validator + parser + verb gate end-to-end). File pre-existed S78; pre-existing failures observed at S77 sweep (4 e2e tests) are due to test code expecting `mocked` LLM outputs that no longer parse cleanly — unrelated to S78 changes.

**Other call sites:** `calibrate_mechanical_hints.py` (offline calibration script, not in production hot path).

---

## R3 — N-1 vs transaction-completion-parser resolution

**Code's recommendation: (c) Surface-separated.**

**Reasoning:**

The two systems do **functionally different work** that happens to overlap in vocabulary:

| Property | N-1 (existing) | transaction_completion (S78) |
|---|---|---|
| Detection mechanism | LLM call (cloud_router extraction) | Closed-vocab + structural co-occurrence (§1a.x clean) |
| Verb set role | Suppression gate (subtractive) | Detection trigger (additive) |
| Output | Pasteable Avrae commands (`!game coin -5gp`) | `ParserResult` for §1b.1 aggregator routing |
| Consumer surface | `#dm-narration` embed edit (bullet bookkeeping) | §1b.1 aggregator → SINGLE_DOMAIN_CLEAR / IN_FICTION_CLARIFICATION / LAYER_A/B |
| Doctrinal frame | Phase 11.1 advisory parser (pre-§1a.x) | §1a.x narration-detection parser |
| LLM dependency | Required (extraction call) | Forbidden (§1a.x prereq #1) |
| Output scope | Avrae mechanical bookkeeping (currency + rest) | Engine writes via §17 paths (transaction-completion: writes to engine state via existing /coin slash on operator paste; loot-drop: writes via existing /loot claim) |

The vocabulary overlap is incidental — the SAME utterance can fire both because both look for the same surface-level signal (transaction-shaped verbs). But the downstream pipelines are non-overlapping:

- **N-1's output** lands in the DM narration embed as `- `!game coin -5gp`` for operator Avrae bookkeeping.
- **transaction_completion's output** lands in `#dm-aside` as either a quest-acceptance-style suggester card (SINGLE_DOMAIN_CLEAR / HIGH) OR as a pending_clarification engine flag (IN_FICTION_CLARIFICATION / M-DELAYED) OR as a Layer A multi-paste card (cross-domain ambiguity).

**Risk assessment under (c):**

The overlap shows up only when both fire simultaneously. Operator's view:
- DM narrates "Garrick pockets the coin" → N-1 appends `- !game coin -5gp` to the narration embed.
- Same turn: transaction_completion parser fires HIGH on the same narration → posts a Phase-3a-style suggester card to `#dm-aside`.

These are **complementary**, not duplicative — N-1 surfaces Avrae bookkeeping (currency arithmetic outside engine state), transaction_completion surfaces engine-state writes (the engine's record of the transaction). Operator pastes the relevant slash in each channel; both fire cleanly.

The "double-firing" concern in dispatch option (a) is real but it's the desired shape: each surface has a distinct operator action.

**Resolution choice: (c) surface-separated. N-1 stays unchanged; transaction_completion parser fires alongside; consumer surfaces don't overlap.**

**Resolution rejected: (b) subsume.** N-1 is doctrinally pre-§1a.x and shouldn't be retrofitted into §1a.x framing. Retiring N-1's transaction verbs would also retire its Avrae-bookkeeping output (the operator-friendly `- !game coin -5gp` bullet) — losing operational value. (b) would be a regression of S65.1 work, not a clean subsume.

**Resolution rejected: (a) coexist with documented overlap concern.** Same effective behavior as (c) at v0 (both fire), but (a) framing treats the overlap as a problem to monitor rather than the architecture's intended shape. (c) names the architecture: two systems, two consumer surfaces, parallel operation.

**Compounding leverage:** (c) preserves S65.1 baker-scenario hardening unchanged AND establishes the doctrinal precedent that §1a.x parsers can run alongside pre-§1a.x advisory parsers without retrofit churn. Future workloads (butler, web) inherit the cleanly-separated pattern.

**Operator + Oracle gate:** R3 resolution open for confirmation. Code proceeds with (c) at implementation unless operator overrides.

---

## R4 — Narration locus per parser surface

**Status:** IMPEDANCE-SURFACED. Post-LLM aggregator surface needed; clean integration point identified.

**Verified state of `_run_inversion_aggregator`:** Single hook at `discord_dnd_bot.py:2727`, fires inside `on_message` from `action = message.content.strip()` — **PRE-LLM only**. Wraps quest_accept parser. Post-LLM aggregation surface does NOT currently exist.

**Per-parser locus map:**

| Parser | Player narrative (pre-LLM) | LLM completion (post-LLM) |
|---|---|---|
| quest_accept | ✓ canonical surface (verb in player input) | — (S73.1 moved it OUT of post-LLM after live verify confirmed LLM-paraphrase missed) |
| transaction_completion | ✓ "I pay Garrick 5gp" | ✓ "Garrick pockets the gold" (LLM paraphrase) |
| loot_drop | ✓ "I grab the sword" (player intent) | ✓ "the chest reveals a longsword" (LLM reveal) |

Both transaction_completion and loot_drop need BOTH surfaces. Without the post-LLM surface, the LLM-side completion shape (which IS the canonical scene-shape for most transactions and reveals) is silent — primitive would fire only on operator's pre-LLM narration, missing the majority of cases.

**Clean integration point identified:** `_dm_respond_and_post` at `discord_dnd_bot.py:4251` (post-LLM, after embed posts) — currently launches:

```python
asyncio.create_task(_attach_hints(msg, embed, response, campaign["id"]))
asyncio.create_task(_extract_and_persist_world(
    campaign["id"], response, guild, guild_id_int=_sl_guild_id_int
))
```

Adding `_run_inversion_aggregator_post_llm(campaign_id, response, guild, ...)` alongside these is structurally analogous to `_attach_hints` (both are post-LLM advisory background tasks running on the same `response` text).

**Hook details:**
- `response` parameter is the DM narration text (post-LLM).
- `campaign["id"]` and `guild` are available in scope.
- `controller_id` for Layer B listener is NOT directly available post-LLM (the LLM completion has no specific operator-action context); falls back to "any active controller in scene" or skip-Layer-B for post-LLM fires.

**Resolution:** Add a post-LLM aggregator surface. Layer B listener attribution falls back to scene's active actor's controller_id; if not resolvable, post-LLM-Layer-B fires fall through to SILENT_LOG rather than blocking on listener filter ambiguity. (Pragmatic v0; future ships may refine controller-attribution heuristic.)

---

## R5 — Structural-signal accessor verification

**Status:** CLEAN. All accessors exist with stable signatures.

**Verified:**

- `get_recently_active_npcs(campaign_id, limit=6, location_id=None) -> list[str]` — `dnd_engine.py:4706`. Returns canonical names. Location-scoped or campaign-wide.
- `get_pending_loot(campaign_id) -> list[dict]` — `dnd_engine.py:3057`. Returns list of pending loot dicts with fields `{id, creature, table_key, coin, coin_amount, coin_denom, items}`. Items is decoded JSON list.
- `get_inventory(campaign_id, character_name) -> list[dict]` — `dnd_engine.py:2945`. Returns inventory rows for a bound character.

Currency regex: `\d+\s*(gp|sp|cp|ep|pp|gold|silver|copper|platinum|electrum)` — standard pattern; parsers will own a per-parser version of this regex (no shared module needed at v0).

NPC name matching: whole-word lowercase token match against `canonical_name` strings returned by `get_recently_active_npcs`. Tokens stopword-filtered per `quest_acceptance_parser._title_tokens` precedent (excludes 'a', 'an', 'the', 'of', 'and', 'to', 'in', 'for', 'on').

---

## Resolution summary

| ID | Finding | Status |
|---|---|---|
| R1 | `_COIN_TRANSACTION_VERBS` is 47 verbs (S74 doc cited 18 — stale) | CLEAN with documented drift |
| R2 | N-1 sole consumer is `_attach_hints` (post-LLM embed edit); isolated surface | CLEAN |
| R3 | Code recommends (c) surface-separated — N-1 stays, transaction_completion fires alongside; consumers don't overlap | RECOMMENDATION; operator + Oracle confirm |
| R4 | Post-LLM aggregator surface needed; clean integration point at `_dm_respond_and_post:4251` alongside `_attach_hints` | IMPEDANCE → resolved with implementation plan |
| R5 | All structural-signal accessors stable; currency regex parser-local | CLEAN |

**No HALT-class architectural impedance.** R4's post-LLM surface is incremental new code with a clean integration point; R3's resolution preserves N-1 unchanged.

---

## Implementation plan (post-recon)

1. **transaction_completion_parser.py** (NEW) — closed-vocab + structured signals + 3-tier confidence + dedup. Verb set excludes the §1a.x-violating LLM-classification-suppression-gate role N-1 plays; parser is detection-only. Vocabulary overlaps with N-1 by design (R3 (c) lock).

2. **loot_drop_parser.py** (NEW) — same shape. Player-intent verbs + LLM-reveal verbs. Two registration entries against aggregator (`loot_drop_player` pre-LLM + `loot_drop_llm` post-LLM).

3. **discord_dnd_bot.py** — extend `_run_inversion_aggregator` to call all three parsers (quest_accept + transaction_completion + loot_drop_player) on pre-LLM hook. Add NEW `_run_inversion_aggregator_post_llm` at `_dm_respond_and_post:4251` calling (transaction_completion + loot_drop_llm) on post-LLM hook. Stage 1 routing inherited from existing `clarification_handshake.aggregate_parser_outputs` — no aggregator-side changes needed (per S77 lock).

4. **N-1 unchanged per R3 (c) lock.** `mechanical_hints.py` and `_attach_hints` continue operating as today.

5. **Telemetry** — parser fires extend existing `parser_calibration_snapshot`. Per-parser fire telemetry adds `parser_domain` disambiguation + `surface` ('pre_llm' / 'post_llm') field.

6. **Tests** — 3 new test files per dispatch.

7. **Live verify Scenarios A + C + E + F** — first M-DELAYED firing instance documented to DOCTRINE.md §1b.1.

**Implementation phase proceeds same session unless operator gates R3 resolution. Pre-ship backup before code changes land.**
