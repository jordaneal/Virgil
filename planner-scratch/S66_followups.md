# S66 — Followups Filed

**Date filed:** 2026-05-14
**Source:** S66 close + Fix 3 recon

---

## N-5 — LLM-narration loot extraction (ad-hoc / chest-contents path)

**Context.** S66 Fix 3 closed F-035 for **structured combat loot** (items already in `dnd_loot_pending`). The fix did NOT cover:
- DM-narrated chest contents ("you open the chest and find a tattered map")
- Found items not tied to a combatant-death event ("a silver dagger gleams on the altar")
- Player-claimed items from descriptive narration

These currently live as bare LLM mentions with no engine commit. The plan called for an extraction layer using closed possession-transfer-verb vocabulary, same pattern as S65.1 N-1 hint extractor.

**Recommended fix shape.**
1. **`mechanical_loot.py`** (new module, alongside `mechanical_hints.py`).
2. Function: `parse_narrative_loot(narration, campaign_id) -> list[str]`. Returns list of item names co-occurring with possession-transfer verbs.
3. **Closed vocabulary** (recon already done in S66; see `S66_handoff.md` §Recon Findings).
4. **Whole-word gate**: same approach as N-1 verb gate (exclude noun-overlap traps).
5. **Cross-turn dedup**: process-local LRU per campaign, bounded to ~12 entries.
6. Call site: `dm_respond` after the structured-loot block, before scene-extract pass. Auto-claim survivors to `PARTY_STASH_BUCKET` via `add_item`.
7. Telemetry: `narrative_loot_extracted` (per fire), `narrative_loot_suppressed` (per miss with reason).

**Adversarial scenarios:**
- "You open the chest. Inside, a tattered map and a small jade figurine." → 2 items claimed.
- "A silver dagger gleams on the wall, far above your reach." → 0 items (no transfer verb).
- "You pick up the dagger and slide it into your belt." → 1 item claimed.
- "He hands you a wrapped parcel." → 1 item claimed (the parcel).
- Re-run baker scenario from N-1: no false fires from cross-pollination with hint extractor.

**Scope.** ~1-2 days. Single-surface fix; no schema migration. Could ship in S66.1 or bundle with N-3/N-4 (NPC commitment + pronoun) as a "narration-commit gap" arc.

---

## Open Questions for Operator

1. Bundle N-5 with N-3/N-4 in a single arc (3 narration-commit closures) for the F-XX doctrinal-anchor walk? Or ship N-5 alone in S66.1 since it's the cheapest of the three?
2. Recommend a wider verb gate or stricter (require both verb AND `you`/`party`/`take` subject) — depends on Llama 3.3's false-positive rate in practice.
