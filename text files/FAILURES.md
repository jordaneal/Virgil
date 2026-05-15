

---

## §F-64 candidate — Instance-count update (post-S68)

Original F-64 candidate filing (above) named two instances: S53 wired+dropped (NPC was_new) and S63 specced+never-wired+formally-dropped (consequence upsert DM-side).

Post-S68: five instances on the board, all closed.

1. S53 §1.F.c NPC was_new — wired and dropped (perverse-incentive surface)
2. S63 §1.F.e consequence-DM-side — specced never wired, formally dropped (preventive)
3. S66 F-031 quest delivery silent inventory fail — narration claimed reward delivered, engine never wrote inventory (cascade: `add_item(campaign, '', ...)` returned `'invalid'` silently)
4. S66 F-035 loot evaporation — narration described loot, engine never auto-claimed (operator burden translated to slash-typing)
5. S68 N-4 NPC pronoun drift — narration referenced NPCs with pronouns; no engine-side pronoun anchor → LLM re-rolled fresh per turn

Pattern shared across all five: **narration claims a state change; engine does not enforce the state change; the state drifts.** Five-instance cluster names the candidate as architecturally real, not coincidental.

**Sixth instance outstanding:** N-3.1 commitment-tracking multi-spec (HALTed at S68 Phase A; no `dnd_scene_log` indexed by NPC+item; clean fix requires schema work). Filed as the load-bearing candidate ship that may host the formal F-XX anchoring walk. The N-3.1 spec session is the right surface to anchor the doctrine because the architecture being designed IS the structural rule the candidate names.

**Recommended doctrine anchor candidate name (post-anchoring):** *"Narration-commit gap as systemic contamination surface — when narration claims a state mutation that the engine does not deterministically enforce, the claimed state drifts across turns. Engine must enforce state mutations either at narration-detection time (deterministic parser feeding single-writer) or via operator-driven slash gate; LLM narration alone is not a structural state-mutation signal."*

**Architectural relationship to existing doctrine:**
- Sister to §F-08 (Layer 2 narration drift — NPCs never commit). §F-08 names the inverse: LLMs fail to advance scenes. F-64 names the parallel: LLMs claim advancement that didn't structurally happen. Both load-bearing observations land at the same architectural rule: LLM narration alone is not a state-mutation signal.
- Sister to §76 (LLM-writable persisted state contamination). §76 closes the case where LLM narration writes persisted state and re-reads it as canon. F-64 closes the case where LLM narration claims persisted state without writing it.
- Cousin to §1a (binding-decision restriction). §1a says LLM never decides binding state. F-64 says LLM narration claiming a binding state change is structurally insufficient without engine enforcement.

Anchoring waits for N-3.1 ship (operator approval surface for the doctrine framing alongside the architectural primitive that addresses it).
