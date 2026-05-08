# Encounter Cadence v1.1 — Calibration Patch Validation Report

**Run date:** 2026-05-05
**Extractor version:** `encounter_cadence_v1_1`
**Source dir:** `/mnt/virgil_storage/dnd_datasets/crd3/data/aligned data/c=2`
**Sample episodes (10):** C1E001, C1E020, C1E030, C1E049, C1E060, C1E095, C2E001, C2E020, C2E030, C2E045
**v1.1 sample output:** `samples/encounter_cadence_sample_v1_1.json`
**v1 sample output (preserved):** `samples/encounter_cadence_sample.json`
**Eval set:** `findings/encounter_cadence_eval_set_v1.json`
**Regression test:** `extractors/test_encounter_cadence_eval.py`
**`[EXTRACTOR_UNKNOWN]` count:** 0

---

## 1. Headline result

**Eval-set precision: 13/14 = 92.9%.** Above the 70% acceptance threshold.

All five v1-correct records still classify correctly. Seven of the eight v1-wrong records now classify correctly. One v1-wrong record (C2E045 t2529) still fails — see §5.

| | v1 | v1.1 |
|---|---:|---:|
| Records emitted | 14 | 14 |
| Eval-set passes | 5/14 (35.7%) | 13/14 (92.9%) |
| Wave subtypes seen | 2 | 3 (full set) |
| `trap_activation` records | 0 | 1 |

---

## 2. Per-record comparison (v1 → v1.1)

`*` = classification changed. `OK` = matches eval expectation. `FAIL` = mismatch.

| Trigger | v1 | v1.1 | Verdict |
|---|---|---|---|
| C1E001 t1573 | environmental_materialization | environmental_materialization | OK |
| **C1E020 t986** | interruption | **player_action_escalation** | OK ← fixed by patch 1 |
| **C1E020 t993** | npc_turns_hostile | **interruption** | OK ← fixed by patch 4 |
| C1E030 t379 | environmental_materialization | environmental_materialization | OK |
| C1E030 t517 | wave_or_phase_shift / party_join | wave_or_phase_shift / party_join | OK |
| **C1E049 t535** | npc_turns_hostile | **player_action_escalation** | OK ← fixed by patch 1 |
| C1E049 t2434 | npc_turns_hostile | npc_turns_hostile | OK |
| C1E049 t2812 | wave_or_phase_shift / phase_shift | wave_or_phase_shift / phase_shift | OK |
| **C2E001 t1136** | interruption | **npc_turns_hostile** | OK ← fixed by patch 6 |
| C2E020 t967 | interruption | interruption | OK |
| **C2E045 t2014** | environmental_materialization | **trap_activation** | OK ← fixed by patch 3 |
| C2E045 t2529 | player_action_escalation | player_action_escalation | **FAIL** (expected `npc_turns_hostile`) — see §5 |
| **C2E045 t2568** | interruption | **wave_or_phase_shift / reinforcement** | OK ← fixed by patch 2 |
| **C2E045 t2678** | interruption | **wave_or_phase_shift / party_join** | OK ← fixed by patch 2 |

---

## 3. Patch attribution

| Patch | Targeted records | Outcome |
|---|---|---|
| 1 — broaden `player_action_escalation` (drop literal-phrase trigger gate, use `MATT_REACTION_VERBS` + `kicked in` strong-positive) | t986, t535 | Both fixed. |
| 2 — semantic wave detection (init-active state + new-combatant shape + summon language) | t2568, t2678 | Both fixed; subtypes `reinforcement` and `party_join` correct. |
| 3 — widen trap detection to full `preceding_turns` window | t2014 | Fixed. The 1500-char preceding context already spans 25 turns for this trigger (turn 1989-2013), covering the player interaction at 1997 and the mechanism narration at 1998. |
| 4 — drop bare `goes` from `NPC_VOICING` (was matching "he goes [physical motion]") | t993 | Fixed. |
| 5 — proximity-based player-vs-NPC tiebreaker | t2529 | **Did not fix** — see §5. |
| 6 — widen `npc_turns_hostile` with transformation/reveal vocabulary | t1136 | Fixed. |

---

## 4. Field distributions

- **Categories:** `wave_or_phase_shift`=4, `player_action_escalation`=3, `environmental_materialization`=2, `interruption`=2, `npc_turns_hostile`=2, `trap_activation`=1.
- **`is_fresh_encounter`:** True=10, False=4. Wave records (4) are all `False`; everything else is `True`.
- **Wave subtypes:** `party_join`=2, `phase_shift`=1, `reinforcement`=1. Full subtype-set populated for the first time.
- **`player_action_caused`:** True=4 (all three `player_action_escalation` records + the `trap_activation`), False=10.
- **`narration_buildup_chars`:** min=95, median=893 (unchanged from v1 — this field is purely a function of source data).
- **`preceding_context_chars`:** min=344, median=1429.
- **`extracted_at`:** single ISO-UTC stamp shared across all records of the run.
- **Idempotency:** verified by re-running and comparing event-content fields — byte-identical except `extracted_at`.

---

## 5. C2E045 t2529 — patch 5 limitation surfaced for review

**Trigger:** "Well, let's roll initiative first." at turn 2529.

**Eval expectation:** `npc_turns_hostile`, `is_fresh_encounter=true`, `player_action_caused=false`.

**v1.1 result:** `player_action_escalation`, `is_fresh_encounter=true`, `player_action_caused=true`.

**Why patch 5 didn't fix it.** Patch 5's literal text:
- "If NPC dialogue is in the immediately-preceding MATT turn, classify `npc_turns_hostile`"
- "If player action is in the immediately-preceding non-MATT turn, classify `player_action_escalation`"

For t2529:
- The immediately-preceding turn (2528) is LAURA: `"Okay. The minute he rears up, I'm going to Invoke Duplicity again."` — non-MATT, action declaration.
- The immediately-preceding MATT turn (2527) is `"And the dragon is right there."` — no quoted speech, no NPC voicing patterns, no transformation vocab.
- Patch 5 second condition fires → classify `player_action_escalation`.
- Closest NPC dialogue in the preceding window is the dragon-aligned NPC at turn 2512 (`"I appreciate the offer, but I tend to work solo and let's be honest, I'm hungry"`) — 17 turns away from the trigger.
- Closest player action is at turn 2528, 1 turn away.
- Proximity tiebreaker also picks player action (closer).

**To classify t2529 as `npc_turns_hostile` would require one of:**
1. Treating "rears up", "wings up in the air", "looms" — physical-threat-revelation narration in turn 2519 — as transformation/reveal vocab. Not currently in patch 6's list.
2. Excluding "reactive" player actions (LAURA's "Invoke Duplicity again" with `again` implying continuation) from the player-action signal. Not deterministically detectable.
3. Reordering: making `npc_turns_hostile` widened detection (priority 5) fire BEFORE patch 5's immediate-predecessor override. Would shift other records' classifications.

**Recommendation.** Surface for your decision. Three options:
- (a) Accept t2529 as a known limitation; ship at 92.9%.
- (b) Add a "physical-threat-revelation" vocab list (`rears up`, `wings up in the air`, `looms over`, `bares fangs`, `roars`, etc.) to patch 6's transformation list. Would need to verify against the eval set's NPC-dialogue cases (t2434 sphinx — already passes via QUOTED_SPEECH, no risk; t1136 — already passes via transformation vocab, no risk).
- (c) Reorder priorities so widened-`npc_turns_hostile` (closest-3 MATT dialogue / transformation) fires before the patch 5 override. Risk: t1136 already passes, but other records relying on patch 5's player-action override might shift.

I am not authorized by the Phase 2.5 prompt to extend the patches. Holding here.

---

## 6. Anomalies and observations during patch implementation

1. **Patch 3 effective window vs. literal "last 15 turns".** The patch text said "last 15 turns" but t2014 needs ~17 turns of lookback (player interaction at index 1997, mechanism at 1998, trigger at 2014). The 1500-char `preceding_turns` already provides 25 turns for this case, so the patch was implementable by searching the existing `preceding_turns` window rather than a separate 15-turn raw-index walk. The 15-turn window is a *floor*, not a ceiling — `preceding_turns` is wider. Doc'd in the extractor's comments.

2. **`init_active` is set AFTER classification, not before.** Patch 2 says the first init in an episode cannot be a wave — this is enforced by setting `init_active=True` only after a fresh-start classification. The first init candidate in any episode is evaluated with `init_active=False`, so its trigger text would have to match a literal wave phrase to be tagged a wave. This handles edge cases where a "Roll initiative for X" could appear at episode start (rare but possible).

3. **Patch 4 chose the simpler approach** (drop `goes` from `NPC_VOICING` entirely). The alternative — require quoted-speech follow-up within ~80 chars — would also have caught the false positive but might miss other legitimate "he goes, '...'" speech where the quote uses different punctuation. Dropping `goes` is safer because true speech-act `goes` always has a quote that matches `QUOTED_SPEECH` anyway.

4. **`TRANSFORMATION_VOCAB` matched `t1136` cleanly** on `body stops quaking` + `flesh now` + `eyes blood-red` + `lips curled` (four hits in the trigger text alone). No collateral matches in the other records' triggers or recent context.

5. **`WAVE_NEW_COMBATANT_SHAPE` carried `t2678`** ("Both of you roll initiative") and **`WAVE_SUMMON_LANGUAGE` carried `t2568`** ("Roll initiative for the elemental"). Sub-type assignment passed by routing summon-language through `reinforcement` first (priority over party-shape).

6. **`MATT_REACTION_VERBS` carried `t986`** via `Frustrated`, `Nothing happens`, `continues to run` (three matches in the trigger). For `t535`, the strong-positive `kicked in` path fired before the reaction-verb gate even mattered.

7. **Idempotency confirmed** — back-to-back `--sample` runs produce byte-identical event-content fields. Only `extracted_at` differs (metadata-only, exempt per Design Constraint #4).

---

## 7. Acceptance criteria check

| Criterion | Status |
|---|---|
| All 5 v1-correct records still correct | ✓ |
| ≥ 4 of 8 v1-wrong records now correct | ✓ (7 fixed) |
| Total eval-set precision ≥ 70% | ✓ (92.9%) |
| Defensible record (10 — C2E020 t967) stays as `interruption` | ✓ |
| Record 9 (transformation, t1136) explicitly fixed | ✓ via patch 6 |
| Record 14 (party falling, t2678) explicitly fixed | ✓ via patch 2 |

---

## 8. What this report does NOT do

This report is a calibration validation. The recall / precision / taxonomy questions in `CORPUS_BUILDER.md` Hand-Sample Validation Protocol — particularly *recall on the corpus as a whole* — are not answered here. The eval set covers the 14 init-events the v1 extractor surfaced from the 10 sample episodes; it does not catch init-events the v1 extractor missed. A wider recall audit is appropriate before the full parse runs (filed for Jordan's call).

The full parse (`--full`) is **not** scheduled. It will not run until:
1. The t2529 limitation in §5 is resolved or accepted.
2. Recall is independently checked against a sample (or accepted as-is).
3. Jordan signs off on shipping v1.1 to the corpus.
