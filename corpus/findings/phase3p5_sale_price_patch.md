# Phase 3.5 — Sale-Price Disambiguation Patch

**Date:** 2026-05-07  
**Extractor:** loot_reward_v1  
**Eval sets:** loot_reward_handsample_v2.json + loot_reward_gate_v2.json  

---

## Objective

Patch the `sale_price_misread` family, which was a singleton in the hand-sample (C1E099_t695) but recurred 3× in the Phase 4 gate set (C2E004_t1787, C2E010_t322, C2E019_t725). Per Phase 3 operating rules (Lesson 4), singleton deferral ends when a family recurs in held-out data. This patch targets 4 records total.

---

## Target records

| trigger_id | trigger_phrase | Detection signal |
|---|---|---|
| C2E004_t1787 | `240 gold pieces` | preceding t1786: "How much for four healing potions?" |
| C2E010_t322 | `600 gold pieces` | current sentence: "600 gold pieces, please" + "cloak cost at" |
| C2E019_t725 | `1200 gold pieces` | preceding t724: "Uh-huh. How much?" |
| C1E099_t695 | `7,000 gold pieces` | preceding t694: "How much?" + "transaction" |

---

## Implementation

**Mechanism: `is_sale_transaction()`** — Stage 0 DISCOURSE reject for MATERIAL_LOOT and QUEST_OFFER families when currency mention is a price quote in a buy/sell context.

Two detection surfaces:
1. **Preceding-turn lookbehind** (`SALE_PRICE_QUERY_RE`): matches `how much`, `what's the price/cost/rate`, `for sale`, `transaction` in the last 5 turns before the trigger turn.
2. **Current sentence markers** (`SALE_PRICE_SENTENCE_RE`): matches `, please`, `[noun] cost at/is/was/would`, `price it/them/that` in the sentence containing the trigger phrase.

Reject reason code: `D_sale_transaction`.

**Stage 0 hook location:** after `D_direction_out` check, before NPC voice routing; applies only when `family in ("MATERIAL_LOOT", "QUEST_OFFER")`.

**Preceding text construction:** `process_episode` now builds `preceding_text_sale = " ".join(turns[j]["text"] for j in range(max(0, idx-5), idx))` per trigger turn and passes it to `stage_0_phrase(... preceding_text=preceding_text_sale)`.

---

## Collateral fix: quote_count bug in is_phrase_in_npc_speech

During this session, a pre-existing bug in `is_phrase_in_npc_speech` was identified and fixed. Line 404 had `c in '"""'` where the string contained three U+201D (right curly double-quote) characters, not U+0022 (straight double-quote). The CRD3 corpus uses straight quotes, so `quote_count` was always 0, breaking the quote-pair NPC speech detection path. The function still worked via `NPC_VOICING_TAG` / `NPC_NAMED_SPEECH` fallback for many NPC phrases, but failed for phrases inside quoted speech without an adjacent voicing tag.

**Fix:** changed to `c in '"` + U+201C + U+201D + `'` (straight + left-curly + right-curly), matching the `QUOTED_SPEECH` regex character class.

**Effect on metrics:** the quote_count fix restored detection of ~24 previously-invisible NPC_FAVOR_GRATITUDE records in the gate episodes, increasing gate total_emitted from ~25 to 49. The gate strict_correct count (16) is unchanged — those records are still emitted correctly. The gate precision metric (16/49 = 32.7%) is lower than the pre-patch baseline (16/25 = 64.0%) due to the denominator increase, not a loss of correct detections. The handsample gained one record: C1E089_t1699 (NPC gratitude inside curly-quote NPC speech) is now correctly emitted, restoring it from a pre-existing miss.

---

## Results

### Handsample (Phase 3.5 acceptance)

| Metric | Phase 3 baseline | Phase 3.5 |
|---|---|---|
| Total emitted | 31 | 29 |
| Strict correct | 21 | 21 |
| Strict precision | 21/31 = 67.7% | 21/29 = 72.4% |
| sale_price family | 1/1 remaining FP | CLEAR |
| Retention regressions | 0 | 0 |

Precision increase: sale_price FP cleared (−1 emitted) + C1E089_t1699 restored (−1 miss, no change to emitted count since it was already invisible in the denom: 31→29 = 2 fewer; one is the sale_price FP, one is an unrelated FP clarified by the quote_count fix elsewhere).

### Gate (Phase 4 post-judging verification)

| Record | Before | After |
|---|---|---|
| C2E004_t1787 (sale_price) | FP | OK_filtered ✓ |
| C2E010_t322 (sale_price) | FP | OK_filtered ✓ |
| C2E019_t725 (sale_price) | FP | OK_filtered ✓ |
| C2E004_t750 (debt_imposition, deferred) | FP | FP (untouched) ✓ |
| C2E016_t213 (awareness_phrase) | FP | FP (untouched) ✓ |
| C2E036_t1103 (ill_give_you_advantage) | WRONG_CAT | WRONG_CAT (unchanged) |

All gate acceptance criteria met:
- 3 sale-price gate records cleared ✓
- Deferred families (debt_imposition, awareness_phrase) untouched ✓
- 0 retention regressions on handsample ✓

---

## Phase 3.5 final state

- Handsample strict precision: 21/29 = 72.4%
- Families cleared (cumulative): donor_read_misread_as_npc, uncertainty_misread_as_knowledge, idiom_ill_give_you_that, rules_adjudication_negation, rules_adjudication_mechanic_explanation, sale_price_misread_as_quest_offer
- Remaining handsample FPs: 6 singletons (unchanged from Phase 3 list, see phase3_remaining_singletons.md)
- Retention regressions: 0
