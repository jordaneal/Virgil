# VIRGIL_MASTER.md — S51 Delta Patches

**Targeted update to merge into the existing canonical VIRGIL_MASTER.md.** Single ship (every-turn time signal in SCENE STATE block). §76 read-side analogue closed at the prompt-input layer.

Apply by editing the existing file in place — do NOT replace the whole file. This delta is independent of the S45/S47/S49/S50 delta patches.

---

## PATCH 1 — Header stamp refresh

**Find this block (lines ~1-3):**

```
# VIRGIL MASTER

**Current System State and Architecture**
Last updated: May 12, 2026 (S50 — pre-playtest cleanup ship: COMBAT_END 0-action framing fix ...)
```

(Whatever header the canonical file currently carries.)

**Replace with:**

```
# VIRGIL MASTER

**Current System State and Architecture**
Last updated: May 12, 2026 (S51 — every-turn time signal in SCENE STATE block. §76 read-side analogue closed at the prompt-input layer. S50 verify surfaced body/footer divergence: state_footer (Discord embed) showed correct day/phase from DB; narration body defaulted to "morning light" framing on non-advance turns because the LLM had no current-time signal between time-advance moments. `compute_time_directive` only fires on `just_advanced=True`; SCENE STATE (authoritative) block carried Location/Tension/Recent NPCs/Last player action but NOT campaign_day or day_phase. Surgical fix: `Day: {N}` + `Time of day: {phase}` lines added to `scene_state_section` at `dnd_engine.py:5407`, between Location and Tension. LLM gets ground-truth time on every turn; `compute_time_directive` unchanged (its just-advanced gate is correct for its purpose — narrate-the-advance beat). §76 verifier candidate stays filed as safety net for any remaining LLM-compliance-partial drift. Tests: `test_scene_state_time_signal.py` (10 assertions).)
```

---

## PATCH 2 — SCENE STATE block update note

**This patch lands a new note in Section 2 — preferably near the existing scene-state / footer documentation. If no existing scene-state subsection exists, add it as a small standalone subsection near the Combat narration dispatch subsection (since it borrows similar architectural framing).**

```markdown

### SCENE STATE prompt block (S51 — time-signal completion)

The `=== SCENE STATE (authoritative) ===` block in `dnd_engine.py` `build_dm_context` is the LLM-facing snapshot of canonical scene fields, separate from the Discord embed footer (`render_state_footer` in `dnd_orchestration.py`). Both pull from the same `dnd_scene_state` row; the footer is the display surface for operator visibility, the prompt block is the LLM's authoritative ground-truth read.

Pre-S51 the block carried Location, Tension, Recently active NPCs, Last player action. **S51 added `Day: {N}` and `Time of day: {phase}` lines between Location and Tension** so the LLM has continuous time-of-day ground truth (not just the one turn after time advances, which is what `compute_time_directive` covers). This closes the §76 read-side analogue at the prompt-input layer.

The two surfaces stay separate by responsibility: SCENE STATE block is passive every-turn ground truth (LLM reads it for context); `compute_time_directive` is active narrate-the-advance beat (instructs the LLM to open with an in-fiction time marker on the turn immediately following an advancement). Both pull from the same scene_state dict; the just-advanced gate stays on the directive only.

§76 verifier candidate (TIME_DRIFT class for narration_verifier) stays filed as safety net for any residual LLM-compliance-partial drift after S51's signal-side fix lands.
```

---

## PATCH 3 — Add bullet to Section 3 Core Design Principles

**In Section 3 — Core Design Principles, find the bullet S50 delta added (post-S50-delta state):**

```
- Layer-4 boundary atmospheric closeout renders only when there is content to render; 0-action sessions fall back to a deterministic neutral marker (§78.6).
```

**Add a fourth bullet immediately after it:**

```
- Authoritative engine state (time-of-day, day count, location, tension) must reach the LLM as every-turn ground-truth signal — not just on the turn immediately after the field changes (§76 read-side analogue).
```

---

## Notes on this delta artifact

- Independent of S45/S47/S49/S50 deltas; apply in any order.
- No DOCTRINE.md update — §76 already covers the read-side framing; this fix is application of the named candidate, not amendment.
- Tests: `test_scene_state_time_signal.py` (10 assertions) covers source-text wiring guards (Day/Time-of-day lines present + canonical key extraction + None/0/empty fallback + ordering Location→Day→Time-of-day→Tension), production-fallback-logic simulation, regression guard that `compute_time_directive`'s `just_advanced` gate stays intact (separate responsibility), and import smoke check.
- Symptom evidence: tonight's S50 verify produced concrete body/footer divergence — footer showed Day 10/11 Midday; LLM defaulted to morning framing because no time signal reached the prompt. Post-S51 the SCENE STATE block carries authoritative time on every turn.
- This artifact persists in the chat history as durable backup if sync gets clobbered — re-apply from chat if needed.
