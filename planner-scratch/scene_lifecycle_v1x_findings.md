# Scene Lifecycle v1.x — Findings from S53 Live Verify

**Status:** Filed v1.x candidates. Surfaced during S53 live verify of Scene Lifecycle v1.
**Date:** May 13, 2026
**Parent ship:** Scene Lifecycle v1 (S52)

---

## Finding 1 — LLM-extracted signals as perverse-incentive activity surfaces

**Surfaced:** S53 live verify. Counter never reached hard threshold despite 27-turn stale exploration scene. Trace: stale=3 → soft directive fired → LLM invented "Marla" innkeeper to fill scene → `npc_extractor` caught `was_new=True` → §1.F.c activity signal → counter reset to 0. Soft directive's text ("lean toward compression unless tension warrants") gave the LLM permission to elaborate; elaboration produced a new NPC; new NPC reset the very counter measuring scene staleness.

**Failure mode:** §1.F locks six activity signals. Two are LLM-extracted from narration: **NPC was_new (§1.F.c)** AND **consequence upsert DM-side (§1.F.e)**. Both are forgeable by an LLM elaborating into a stale scene. The third LLM-extracted signal (player closure intent T2) was deferred at §11.N — that deferral was directionally right but didn't generalize the rule.

The architectural rule v1's design missed: **§1.F signals derived from LLM-extracted narration are perverse-incentive surfaces in a stagnation-detection context.** Operator/Avrae-driven signals (location_change, avrae_roll, advance_time, explicit_compress) are not forgeable — they require operator typing or Avrae rolling. LLM-extracted signals are exactly the elaboration the directive is trying to suppress, scored as activity that suppresses the directive.

**Architectural relationship:**
- Distinct from §76 (LLM-writable persisted state). LLM-extracted signals don't write persisted state directly; they write counter resets on a deterministic counter. §76 four-property test passes (the counter is not persisted, not retrieved). The failure is at a different surface: signal-source provenance, not state contamination.
- Sister failure to §F-08 (Layer 2 narration drift — NPCs never commit). §F-08 is about LLMs not advancing scenes; this is the inverse — LLMs *appearing* to advance via narration elaboration that registers as world progression. Same load-bearing observation: LLM narration alone isn't a structural advancement signal.

**Candidate fixes:**

(a) **Drop both LLM-extracted signals from §1.F.** §1.F shrinks from 6 signals to 4: location_change, avrae_roll, advance_time, explicit_compress. Cleanest cut. Cost: legitimate world progression via NPC introduction or consequence assignment no longer resets the counter — but these are arguably scene-padding not progression, so the cost may be illusory.

(b) **Require corroboration for LLM-extracted signals.** NPC was_new resets counter only if co-occurring with location_change OR avrae_roll OR advance_time in the same turn. Same for consequence upsert. Catches "LLM introduces NPC during scene with mechanical action" (real progression) but suppresses "LLM introduces NPC into a stale scene" (padding). More complex; introduces same-turn signal-pairing logic.

(c) **Tier the signals.** LLM-extracted signals reset to soft floor (e.g., stale_turns = N_soft - 1) rather than to 0. Soft directive keeps firing if counter was already past threshold; LLM-elaboration produces a "soft-tier rest, not full reset" semantic. Adds complexity; behavioral effect unvalidated.

**Lean: (a).** Simplest cut, matches the architectural rule's framing. (b) and (c) add complexity to defend signals whose provenance is already suspect. v1.x ships (a) as observed-friction response; if log evidence shows legitimate NPC introductions are getting missed as activity signals, revisit.

**Spec impact:** §1.F amendment dropping signals (c) and (e). §11.E lock revisited — currently (a) "§1.F signals only" still holds, but the §1.F set changes. Re-affirms (a)-class restriction at the structural level rather than the signal level.

---

## Finding 2 — Soft-tier compliance unmeasured

**Surfaced:** S53 live verify. Soft directive fired twice (stale=3, stale=4) and counter reset before reaching hard threshold. LLM-visible behavior post-soft-fire: no compression. But this is not yet evidence of soft-tier toothlessness — counter never reached stale=6, so hard-tier never got a chance to either compress cleanly or also fail.

**Failure mode (provisional):** Soft directive's framing ("lean toward compression unless tension warrants") may be too permissive. The escape clause may be reading as primary rather than as exception. Or soft framing is too soft and needs structural pressure equivalent to commitment directive's three-option framing.

**Defer architectural response until hard-tier observed.** Post-Finding-1 patch and rerun should produce stale=6 events. If hard-tier compresses cleanly: soft just needs stronger framing or earlier escalation (N_soft drop from 3 to 2). If hard-tier also drifts: §11.H reopens (instruction-side enforcement insufficient; information-side suppression candidate per S44 pattern).

**Candidate fixes (after hard-tier data):**

- Soft framing tightening — drop escape clause; replace with "consider transitioning the party"; let LLM choose elaboration vs transition without the directive's implicit permission to elaborate
- N_soft drop — soft fires at stale=2; one earlier turn of pressure before hard-tier escalates
- Skip soft entirely — single-tier hard directive at stale=4 or stale=5; simpler, removes the soft-tier compliance question entirely

**Lean: wait for hard-tier data before picking.** Premature.

---

## Filing summary

Finding 1 ships as v1.x patch in S53. Architectural rule named: LLM-extracted signals are perverse-incentive surfaces in stagnation-detection context.

Finding 2 stays open pending S53-post-patch live-verify data showing hard-tier behavior.

Both findings cross-reference to FAILURES.md as new entries when anchored — Finding 1 likely as F-64 (LLM-extracted activity signal as scene-padding loophole), Finding 2 conditional on hard-tier data.

---

## Finding 1 update — S63 proactive patch (May 2026)

**Inventory-before-patch surfaced doc-vs-code mismatch.** S63 opened to drop §1.F.e (consequence upsert DM-side) per identical-shape rule to S53's §1.F.c drop. Recon found §1.F.e was specced in v1 but **never wired** in the S56 Quest Layer implementation:

- `discord_dnd_bot.py` `_reset_scene_stale` has 6 call sites: combat-start (§11.I), rest event (§1.F.d), Avrae roll consumed (§1.F.b), `/play` (§11.O), `/compress` (§11.J), `/travel` (§1.F.a/d).
- Zero call sites in the consequence-extraction path (`_extract_and_persist_world` → `apply_consequence_proposals` → `consequence_upsert`).
- Zero direct touches of `_scene_stale_turns` dict outside the three helper functions.
- Conclusion: §1.F.e was a spec lock the implementation never picked up. The bot has been running on §1.F (a)/(b)/(d) only since v1 ship.

**Patch shape adjusted.** Since no code change exists to make, S63 is a doc-only patch:
- Spec amendment: strike §1.F.e from locked list + new footnote naming the never-wired finding + §12.10 update
- planner-scratch update: this entry
- FAILURES.md: F-64 candidate filed
- No code change, no test flip (no test was written for the non-existent reset)

**F-64 second-instance trigger met.** Two project instances of the failure mode now established:
- §1.F.c (NPC was_new) — wired in S56, observed failing in S53 live verify, dropped via S53 patch
- §1.F.e (consequence upsert DM-side) — specced in v1, never wired in S56, formally dropped via S63 doc-only patch

The pattern crystallizes: when v1 specs an LLM-extracted activity signal in a stagnation-detection context, two outcomes have emerged — either the implementation wires it and the live-verify perverse-incentive surfaces (S53), or the implementation skips it and the spec drifts (S63). Both outcomes argue the same architectural rule: **LLM-extracted signals don't belong in §1.F.** Anchored as v1 doctrine in spec §12.10. F-64 candidate filing pending operator confirmation.

**Corroborated-signal pattern still on file as v1.x candidate.** Same shape preserved (NPC was_new AND same-turn non-LLM signal); only v1's blanket inclusion of LLM-extracted signals is closed.
