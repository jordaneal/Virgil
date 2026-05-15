# S32 Multiplayer Playtest — Findings Report

**Date:** 2026-05-09 21:00 – 22:44 PDT
**Session:** S32 (Bug 1 Phase 1 ship verification + open multiplayer playtest)
**Players:** Jordan (DM + Donovan Ruby), Captin0bvious (Karrok The Devourer)
**Campaign:** 22 (Boar's Head Tavern → Brighthollow Tavern → Guild Hall → Crystal Cave fiction)
**Bot version:** post-S32 restart (Bug 1 Phase 1 telemetry-only matcher live)

This is an **observation report**, not a fix-spec. Findings are labeled as **candidates** for the planner to anchor via F-NN entries in `FAILURES.md` if/when they're confirmed and prioritized. Evidence is cited inline; full journal log slices available via `journalctl --user -u virgil-discord --since "2026-05-09 21:00:00"` for any follow-up.

**Document status:** planner-merged + late-canon-read correction pass. Original authored by Code (server-side observation pass). Planner first-pass additions: §3.6–§3.9 (Findings H–K), §5.7–§5.8 (narration/bookkeeping clusters), §9 (player design feedback), and merge notes appended to §6 and §8. Code's findings A–G and §1 wins are preserved verbatim.

**Late-canon-read correction (post-first-merge):** Planner's first pass operated without reading actual canon (DOCTRINE.md, FAILURES.md). Three corrections applied in this pass:
1. **Finding L added (CRITICAL)** — covers the roll-resolution-unbound failure mode (DC announced, roll lands, narrative outcome driven by player self-report not roll-vs-DC). Framed as **F-45 regression** rather than new failure mode — F-45 ("failed rolls produce success narration") was supposedly closed by Track 7 #1 CHECK_ACTION binding in S25 #4; multiplayer playtest shows it back. Architectural diagnosis included.
2. **F-55 umbrella relationship acknowledged** — Findings H (hydrate→Avrae sync gap), I (combat onboarding), K (roll-gating inconsistency), and §9 (Thomas's looser-narrative-combat suggestion) all cluster under existing F-55 (combat playability collapse) and the Combat Playability Cluster (Track 6 #5.1/5.2/5.3/5.4) already filed in ROADMAP. They are not new failure modes; they are new instances strengthening F-55's case.
3. **§59 doctrine references corrected** — first pass cited §59 multiple times for "wait-for-second-instance before anchoring doctrine candidate" discipline. §59 is actually the pure-function-in-orchestration template. The candidate-anchoring practice is informal project pattern, not numbered doctrine. References struck.

Jordan (DM/architect) holds final F-NN assignment authority. Proposed next number: **F-59** for next candidate fix that anchors as a real failure mode.

---

## §1. Wins to call out (don't get lost in the bug list)

These are working-as-designed observations that are load-bearing for the playtest's positive signal:

- **Bug 1 Phase 1 matcher fired correctly through the entire run.** Every directive bound + matched + consumed cleanly. Zero false positives. Zero missed legit DM-typed directives. All four `footer_actor_changed:` triggers fired (`dm_respond`, `play`, `combat_turn_set`, `combat_turn_clear`).
- **Track 7 #2 multi-actor arbitration handled up to 3 concurrent inputs across 2 actors cleanly** (22:23:42 — Captin × 2 messages + Jordan × 1, all narrated correctly, verification passed). F-48 (concurrent player input collision) closure is holding.
- **F-46 ("says who" defeats refusals) holding the line.** At 10:18-10:20 Jordan asserted "i gain the keepers favor and he blesses me" — bot REFUSED to fabricate a Keeper, narrating "the chamber holds no keeper—only the distant echo of his earlier words." At 10:39-10:40 Jordan asserted "give us the 150gp you agreed to" — bot held the line at the actual offered price. Track 7 #1 capability + arbitration is doing real work.
- **Verifier escalation flag fires honestly.** When retry can't recover the LLM's actor focus, escalation flips and the system posts a "verification anomaly" notice rather than silently suppressing. Failure modes are **visible**, not hidden.
- **`/setup` channel routing + Avrae bookkeeping prompts work.** Bot's `!game coin +120gp` / `+30gp` hints in narration drove Avrae state correctly when the player typed them.
- **Bug 3 NPC location filter (`npcs_in_context: count=0 location_filtered=1`)** fired correctly throughout — chroma-bled NPCs stayed out of the prompt's NPC list block.
- **F-58 (stale-footer name parsing) live-fired and self-resolved per spec.** First in-the-wild instance at 22:37:10 (Karrok-bound directive, Donovan rolled → `directive_actor_mismatch:` logged, wrong-actor aside posted). Then 212s later at 22:40:42 the stale row got replaced via `pending_directive_replaced:` rather than expiring — exactly the architecture the F-58 stub anticipated.
- **Bug 1 `pending_directive_replaced` path live-fired** for the first time (22:40:42). Spec'd dead-code path proved load-bearing under real play.

---

## §2. Critical findings (production state corruption happening every multi-turn session)

### §2.1. **Finding A (CRITICAL): scene_state.location LLM-write without canon-check**

**Severity:** CRITICAL — silent canonical-state corruption every multi-turn session
**Tie-back:** F-44 (chroma bleed) is the input channel; this is the **persistence-side amplifier** that makes the bleed self-reinforcing. **F-44 alone doesn't capture this.**

**Evidence trail:**

```
sqlite> SELECT location, current_location_id FROM dnd_scene_state WHERE campaign_id=22;
narrow village lane | 23           ← current state at end of run

dnd_locations row 23 = 'guild hall'  ← what the footer correctly displays
```

`location` (LLM-owned scalar) drifted across the run independent of `current_location_id` (canonical FK):

| Time | scene_state.location | scene context |
|------|----------------------|---------------|
| 21:38 PM | `guild hall` | `/travel` set canon |
| 22:02 PM | `shadowed nook of stone hall` | LLM bled cave imagery from chroma |
| 22:12 PM | `shallow alcove` | LLM continued cave fiction |
| 22:20 PM | `next room` | LLM "transition" between rooms |
| 22:35 PM | `narrow village lane` | LLM teleported to village |

**Footer correctly displayed `📍 guild hall` throughout** (because that's derived from `current_location_id` → `dnd_locations.canonical_name`). But the **prompt fed to the LLM** carries `scene_state.location` as input each turn (see `dnd_engine.py:5161`, `f"Location: {scene_state.get('location') or '(not yet set)'}\n"`). Once poisoned, the bleed self-reinforces.

`established_details` (LLM-owned 20-slot list) was also fully colonized by cave-fiction details:
```
["resonant tone", "harsh light", "tense posture", "hot stream", "darkened vein",
 "cold metallic flavor", "thrumming vibration", "pulsing surface", "strange light",
 "thin line of flesh", "small wound", "narrow crack", "dust-caked fragments",
 "copper necklace", "late-afternoon sun", "jeweller", "startled gasp",
 "faint chime", "fair price", "discretion deal"]
```

The 20-item cap (`existing = existing[-20:]` in `update_scene_state`) means accurate Guild Hall details aged out as cave details accumulated. By end of run, **zero Guild Hall details** survived.

**Code path:** `dnd_engine.py:4731 extract_scene_updates` runs after every DM turn → LLM extracts `location` / `focus` / `new_established_details` from the (chroma-poisoned) narration → `update_scene_state` writes to `dnd_scene_state` with **no canon-check** on these LLM-owned fields. Direct §1a/§1b violation: LLM output binds to canonical state with no deterministic Python validator.

**Three candidate fixes** (file all, pick one at spec time):
- **(a) Strict canon-check on location write:** `update_scene_state` rejects `location` writes that don't match `dnd_locations.canonical_name` for the current `current_location_id` (case-insensitive). Logs `scene_location_drift_rejected:` and skips. Telemetry-first per §39.
- **(b) Drop the field, derive from canon:** stop storing `location` as LLM-writable scalar; read it derived from `current_location_id` → `dnd_locations.canonical_name` at prompt-build time. Single source of truth per §17.
- **(c) Snapshot on `/travel`:** `set_current_location` clears `scene_state.location` + `established_details` to canonical defaults from `dnd_locations` row. Resets the bucket per travel.

**Recommended:** **(b)** — cleanest §17-shape (single writer = canonical location row, derived projection in prompt). (a) is the §39 path. (c) is partial mitigation only.

**Bonus impact:** prompt size hit 25203 chars at 22:19:39 — F-30 (prompt bloat) territory. F-60's drift creates retrieval-block growth as cave fiction accumulates in chroma, which then feeds back. This is also why Phase 2 trigger criterion 4 (zero spurious footer transitions) needs the F-A fix landed first.

---

### §2.2. **Finding B (HIGH): canonical-name reuse / in-scene identity collapse**

**Severity:** HIGH — poisons canonical NPC consequences
**Tie-back:** F-49 (LLM-fabricated NPCs) sibling but inverted shape. Fabrication detection won't catch this because the NPC IS canonical — just not the right NPC.

**Evidence:**

```
9:40 PM bot: "a stout clerk, Merrick, eyes you from behind a cluttered desk"  (Guild Hall)
9:46 PM bot: "the nearest merchant, a wiry man polishing a steel gauntlet"   (separate NPC, no name)
9:49 PM bot: "Merrick gives a brief, grateful nod, then lowers his voice"    (← THE MERCHANT being narrated as Merrick)

sqlite> SELECT id, canonical_name, role FROM dnd_npcs WHERE campaign_id=22;
22 | Merric  | bartender  ← Boar's Head, S31
23 | Talin   |            ← combatant, 9:08
24 | Merrick | clerk      ← Guild Hall clerk

sqlite> dnd_consequences row 9: kind=promise summary='Merrick warns of danger at dusk' status=promoted
```

The merchant's "watch the cliffs at dusk" warning was LLM-attributed to Merrick (clerk) in narration. `consequence_extractor` parsed `Merrick warns of danger at dusk` and bound it to `npc_id=24` (Merrick the clerk). **Canonical state now reflects a consequence on the wrong NPC.**

**Why narration_verifier missed:** verifier asks "does this NPC exist canonically?" — Merrick exists. Verifier doesn't ask "is the LLM using this name for the right canonical entity?" That requires per-scene scope tracking that doesn't exist.

**Filing recommendation:** new failure mode. Distinct from F-49 (fabrication of new NPCs) and F-44 (chroma-driven NPC bleed across scenes). This is **in-scene name substitution onto a fresh NPC** — LLM reused an existing canonical name for a new fictional NPC because the canonical name is in retrieval / context bias.

**Suggested mitigation paths** (file as v1.x):
- Per-turn NPC context filtering: when narration introduces a new NPC role (merchant, clerk, etc.) that doesn't match an existing canonical NPC's role, log a `npc_role_mismatch:` candidate and prompt operator to clarify.
- Stricter narration verifier: track which canonical NPCs are EXPECTED in scope (location_filtered list) and flag when narration uses a canonical NPC name that's not in the expected list.

---

## §3. Medium findings (reproducible, observable, calibration-worthy)

### §3.1. **Finding C: Adjudicator combat verdict ignores target animacy**

**Severity:** medium — disrupts narrative flow with bogus init prompts on object-interaction
**Tie-back:** F-17 / F-18 family revisiting at the adjudicator layer (post-Track 7 #1)

**Evidence (3 false positives, 1 true positive — pattern is sharpened):**

| Time | Input | Verdict | Outcome |
|------|-------|---------|---------|
| 22:00:32 | "I stab the crystal as hard as I can" | **combat** (false) | init_directive fired against inanimate target |
| 22:19:39 | "I ride the crystal... drop kick the crystal into the indentation" | **combat** (false) | init_directive fired |
| 22:28:03 | "I hit the shard with my maul" | **combat** (false) | init_directive fired |
| 22:26:30 | "I take out my maul and charge in, not stopping until I find something to hit" | **combat** (TRUE) | correctly fired init_directive |

Pattern: **violent verb + named inanimate target → false positive.** **Violent verb + abstract target ("something to hit") → true positive.**

**Filing recommendation:** new failure mode (sibling to F-17/F-18). Adjudicator should refuse `verdicts=combat` when the targeted object is a known inanimate canonical entity. Possibly via target-animacy lookup against `dnd_locations` features OR via a structured "target classification" stage before verdict assignment.

Doctrine §26 (ever-growing exception lists mean fix is wrong) applies — don't whack-a-mole-list the verbs. The fix is target-side, not verb-side.

---

### §3.2. **Finding D: Verification retry fails when prior context biases wrong actor**

**Severity:** medium — 4/8 verdict=check turns escalated past retry (50% retry-fail rate)
**Tie-back:** Track 7 #2 retry mechanism calibration

**Evidence (escalations across the run):**

| Time | Actor | Prior context bias | Result |
|------|-------|-------------------|--------|
| 22:18:43 | Donovan (verdict=check) | Karrok-weighted (multi-turn) | escalated |
| 22:22:20 | Karrok (verdict=check, listening) | Donovan-weighted (recent fart turn) | escalated |
| 22:36:50 | Donovan (verdict=check, persuasion) | Karrok-weighted | escalated |
| 22:40:30 | Donovan (verdict=check, intimidation) | Karrok-weighted | escalated |

Pattern: **after a long string of turns focusing on PC-A, when PC-B suddenly takes a check action, the LLM's attention bias toward PC-A defeats verification retry.** Retry's correction power is bounded by recency/chroma weighting.

Single-actor turns and lower-pressure verdicts (free) verified clean. Failures concentrated in actor-switch + check-verdict cases.

**Filing recommendation:** new failure mode under Track 7 #2 calibration. Possible mitigations:
- **Retry prompt sharpening:** when retry fires after actor_omission, prepend the retry prompt with `"YOU MUST USE THE NAME '{actor_name}' AT LEAST ONCE IN YOUR NARRATION"` as a hard-stop rule per §2.
- **Attention-rebalance directive:** when arbitration's `primary_actor` differs from `last_active_actor`, emit a directive in the prompt naming the new actor explicitly as the focus.

Sample size growing — confirmed reproducible 4 times.

---

### §3.3. **Finding E: LLM silently reinterprets player intent for plot advancement / content sanitization**

**Severity:** medium — verifier doesn't validate narration matches stated player action
**Tie-back:** F-46 / F-47 family but inverted (LLM rejects player intent rather than accepting it)

**Evidence (2 instances):**

```
10:24 PM Jordan: "I know what to do. Roll in it"   (context: poop pool established)
10:24 PM bot: "Donovan spots a loose slab... nudges it... sends it rolling into the shallow indentation"
              ← LLM substituted "roll a slab" for "roll in poop"

10:28 PM Jordan: "Piss myself in fear"
10:28 PM bot: "Donovan winces... clutching at his own front"
              ← LLM euphemized to "clutching at front"
```

In both cases: `verdicts=free`, `verification: passed=1`. The verifier had no objection because:
- Donovan IS named in the narration
- No NPCs were fabricated
- Bot didn't refuse the action

But the narration substituted alternative interpretations of the player's stated action. **Verifier checks NPC/actor presence and fabrication, not whether narrated action verbs correspond to stated player verbs.**

**In playful contexts this is tolerable.** But the same mechanism could silently reinterpret a serious player intent ("I betray my party" → "Donovan considers betrayal but stays loyal") which would be a gameplay-breaking bug. The pattern doesn't distinguish playful-sanitization from serious-override.

**Filing recommendation:** new failure mode. v1.x candidate fix shape: verification class `INTENT_DRIFT` comparing narrated action verbs against player-stated action verbs. **Tuning is hard** — paraphrasing is desirable for narrative quality, false positives would be costly. File as candidate, watch for repeats in actual gameplay (not just goofing around).

---

### §3.4. **Finding F: Case-sensitivity phantom locations**

**Severity:** medium — silent corruption that grows over time
**Tie-back:** F-13 driver-variant (phantom locations from typos → here from case-mismatch)

**Evidence:**

```
sqlite> SELECT id, canonical_name FROM dnd_locations WHERE campaign_id=22;
22 | Greymoor's Pass
23 | guild hall          ← /travel target (lowercase as DM typed)
24 | Guild Hall          ← LLM narration extraction (Title Case)

journal:
21:38:08 /travel: from='an unknown place' to='guild hall' resolved=1 created=1   → id=23
21:38:08 set_current_location: campaign=22 current_location_id=23
21:38:11 loc_extract: validated=['Guild Hall']
21:38:11 location_upsert: insert campaign=22 id=24 name='Guild Hall'             ← phantom, 3s after canonical
```

`/travel` writes lowercase; bot's `/play` narration uses Title Case ("Guild Hall"); `loc_extract` parses the capitalized version; `location_upsert` doesn't match against id=23 because `canonicalize_name` preserves case per §14. So a phantom row appears 3 seconds after the canonical one. Both rows describe the same conceptual place.

**Phantom location candidates heuristic** (Ship 4 telemetry: `skeleton_origin=0 AND mention_count=1`) **wouldn't catch this** because both rows have `mention_count >= 1`.

**Filing recommendation:** F-13 sibling or extension. Three candidate fixes:
- **(a)** `location_upsert` casefold-collision check before insert; on hit, log `location_case_collision:` and reuse existing id (telemetry-first)
- **(b)** Casefold canonical names at write time (loses DM display casing; risks §14 spirit)
- **(c)** `/travel` writes both casings as aliases on the canonical row

(a) is the §39-shape — observe before binding to a fix.

---

### §3.5. **Finding G: Verifier escalation message exposes internal debug strings to user**

**Severity:** low-medium — UX/polish issue but visibly broken to end-users
**Tie-back:** narration_verifier.py escalation path

**Evidence (10:36 PM in Discord):**

```
"Karrok The Devourer's action passes without resolution.
 (See logs: [VERIFICATION_ANOMALY] — escalation reached FREE verdict class=actor_omission)"
```

Source: `narration_verifier.py:633-635`:
```python
f"{actor_name}'s action passes without resolution. "
f"(See logs: [VERIFICATION_ANOMALY] — "
f"escalation reached FREE verdict class={failed_violation_class})"
```

The literal `[VERIFICATION_ANOMALY]` token and `verdict class=actor_omission` field are internal classification names leaking into player-facing narration. The user sees ALL CAPS DEBUG STRINGS in the middle of fantasy prose.

**Filing recommendation:** narrow polish fix. Two options:
- **(a)** Replace technical text with operational copy: e.g. *"The action's resolution doesn't fully resolve in the moment — the moment passes without clear effect."*
- **(b)** Drop the user-facing message entirely; log the anomaly server-side only. The user sees nothing extra; the bot just posts the LLM's escalated narration without commentary.

(b) is the cleanest §59-shape — escalation as silent fail-open, anomaly visible only to operator via journal.

---

### §3.6. **Finding H (HIGH): `hydrate` writes DM-side NPC stats without syncing to Avrae sheet — combat with hydrated NPCs is unplayable**

**Severity:** HIGH — single-writer split across mechanically-coupled state domains; combat against hydrated NPCs has no mechanical resolution
**Tie-back:** Sibling architectural concern to Finding A and to doctrine candidate #2. Different specifics — two writers maintaining separate state for what should be one canonical NPC.

**Evidence (live-play, 9:31 PM Discord):**

```
Jordan /hydrate: Stats already complete for `Talin` at CR 1/4 — no fields updated.
                 Current: HP 13, AC 13, Atk +3, Dmg 1d8.
Jordan /refresh: No Avrae sheet for `Talin` found in this channel.
                 Have the player run `!sheet` here, then try `/refresh` again.
```

`hydrate` populated the engine-side NPC row with combat stats. `/refresh` confirmed no corresponding Avrae sheet exists. Combat then proceeded with broken resolution:

```
9:28 PM Avrae: Karrok unarmed strike → Talin: To Hit 13, Damage 5
              Talin: <None>: Dealt 5 damage!     ← <None> HP, no resolution
9:21 PM Avrae: Donovan unarmed strike → Talin (selected target)
              Karrok The Devourer: <13/15 HP> (-2 HP)   ← landed on Karrok mechanically
              [DM narration] "Your unarmed strike lands solidly on Talin's face..."
                                                        ← narrated as hitting Talin
```

The narration layer thinks it's resolving combat against Talin; Avrae has no Talin to resolve against; HP, AC, and damage have no canonical landing point. Result: bot reports both `<None>` HP outcomes (mechanically null) and narrated outcomes (semantically against Talin), with attacks sometimes landing on the wrong target mechanically while being narrated against the intended target.

**Architectural shape:** dm-aside NPC creation (via `hydrate`) writes to engine state. Avrae sheet creation is a separate writer triggered by player `!sheet` commands. There is no bridge between the two for NPCs. Combat resolution depends on Avrae sheets. Therefore any NPC created via dm-aside is mechanically unresolvable in combat.

This is a single-writer split across mechanically-coupled domains. Compare to the Q3 footer-actor resolution: there, the fix was making one canonical writer authoritative across modes. Here, the analogous fix is either pushing hydrated stats to Avrae automatically (single-writer-with-projection), or providing a separate combat resolution path for dm-aside NPCs that doesn't depend on Avrae.

**Three candidate fixes** (file all, pick one at spec time):
- **(a)** Auto-create Avrae sheet on hydrate via Avrae monster-add or similar; keep stats synchronized on subsequent hydrate calls
- **(b)** Combat resolution layer detects "this NPC has dm-aside stats but no Avrae sheet" and resolves against engine-side stats directly, bypassing Avrae for that entity
- **(c)** Disallow combat against non-Avrae-sheeted entities entirely; force player to manually create sheets before combat

**(a)** is the cleanest user experience but most coupling work. **(b)** decouples but introduces a parallel combat resolution path. **(c)** is brutal but defensible per §17 (single source of truth, even if inconvenient).

**Filing recommendation:** new failure mode. Distinct from F-39/F-40 (loot fabrication) and F-49 (NPC fabrication). This is the **state-sync gap** between two legitimate writers of NPC state. v1 priority.

---

### §3.7. **Finding I: Combat onboarding dumps malformed mechanics syntax instead of DM walkthrough**

**Severity:** medium — UX/onboarding, but the message is also visibly broken
**Tie-back:** F-17/F-18 family + escalation/copy issue similar to Finding G

**Evidence (9:17 PM Discord):**

```
Captin0bvious: I punch him in his face. Hard.
Virgil DM: Karrok The Devourer attempts a The player has declared a combat action in
           non-combat mode. . Combat is not active. Use !init begin to start combat,
           then surface the action through Avrae.
```

Two issues compounded:
1. **Malformed message body** — looks like a template string with an unfilled error variable: `"attempts a {error_message} ."` Resolves to `"attempts a The player has declared a combat action in non-combat mode. ."`
2. **Raw mechanics directive in narration** — the operational message tells the player to type `!init begin`. The DM should be narrating the moment in-fiction (escalation cue, opponent stance, weapons drawn) and either auto-firing init or prompting the DM to escalate, not handing the player raw bot-command syntax.

**Filing recommendation:** narrow polish + adjudicator-copy fix. Compare to Finding G which has the same shape (debug strings leaking into narration). Two tiers:
- **Immediate:** fix the malformed template + replace raw `!init begin` instruction with operational DM prose
- **Architectural:** when adjudicator returns `verdict=combat` from non-combat mode, auto-trigger init flow rather than asking the player to do it manually (Track 6 #5 territory, combat orchestration ownership)

Related to Finding C (combat verdict false-positives) — the verdict layer's calibration affects how often this onboarding moment fires, and on what grounds.

---

### §3.8. **Finding J: DC values exposed to players in directive emit messages**

**Severity:** medium — meta-information leak (player sees difficulty threshold before rolling)
**Tie-back:** Phase 1 directive emit format

**Evidence (multiple instances throughout the run):**

```
9:36 PM: Karrok The Devourer — Perception check at DC 10. Roll pending.
9:41 PM: Donovan Ruby — Perception check at DC 10. Roll pending.
9:42 PM: Donovan Ruby — Investigation check at DC 10. Roll pending.
10:16 PM: Karrok The Devourer — Athletics check at DC 15. Roll pending.
10:36 PM: Donovan Ruby — Persuasion check at DC 10. Roll pending.
10:40 PM: Donovan Ruby — Intimidation check at DC 20. Roll pending.
```

D&D table convention: DCs are DM-private. Player rolls; DM resolves against the threshold; player learns the result, not the threshold. Surfacing the DC pre-roll lets the player meta-game ("I rolled a 9 against DC 10, so the DM's narrative resolution should reflect just-missing").

**Filing recommendation:** copy fix on directive emit format. Drop the DC from the player-facing directive message; log it server-side only for DM and audit reference. The pending-directive row already stores it (or could); no canonical info is lost.

This is independent from Finding C/I and trivial to ship — a single-line change in the directive emit template should resolve.

---

### §3.9. **Finding K: Roll-gating inconsistency — similar action shapes resolve sometimes with rolls, sometimes without**

**Severity:** medium — affects perceived fairness and player understanding of resolution rules
**Tie-back:** Track 7 #1 adjudicator calibration; possibly downstream of Finding C target-animacy

**Evidence (action-shape pairs from the run):**

| Action | Got a check | Action | Resolved without roll |
|--------|-------------|--------|----------------------|
| "I look around the tavern" | Perception DC 10 | "I take the tube" | resolved as flat success |
| "investigate with Karrok" | Investigation DC 10 | "I keep stabbing the crystal until something happens" | resolved as flat success (panel opened) |
| "I jump up on the crystal and ride it" | Athletics DC 15 | "I break open the panel" | resolved as flat success |
| "I use my persuasion to cut a deal" | Persuasion DC 10 | "I harness the power of the shard and fly into the sun" | resolved as failure narratively (no roll) |

Pattern is unclear. Some actions get auto-emitted directives (perception/investigation/athletics/persuasion), others resolve as flat successes or failures. No consistent rule for which physical/manipulation actions require checks versus which get narrative-resolved.

This affects player trust in the resolution layer — players who try the same action twice with different results (rolls one time, no roll another) lose confidence the system is consistent.

**Possible upstream causes:**
- Adjudicator's verdict layer is inconsistent on similar action shapes
- Adjudicator is consistent but matcher only fires when DM auto-types `!check`; some adjudicator outputs don't include a directive emission

**Filing recommendation:** Track 7 #1 calibration sample collection. Capture verdict-layer outputs across the cases above; identify which had `verdict=check` and which had `verdict=free`; determine whether the inconsistency is at verdict-assignment or directive-emission. Possibly related to Finding C (target-animacy) — destruction/manipulation of inanimate objects sometimes flagged as `verdict=free` for non-canonical reasons.

---

### §3.10. **Finding L (CRITICAL): Roll resolution is unbound from rolled value — F-45 regression in multiplayer / DM-typed-directive flow**

**Severity:** CRITICAL — the entire roll-based resolution layer is non-functional in this flow. DC announcements are theater. Player honor system is the de facto adjudicator.
**Tie-back:** **F-45 regression.** F-45 ("failed rolls produce success narration") was filed S25 #3 multiplayer test and disposition recorded as *"Closed structurally by Track 7 #1 CHECK_ACTION binding (S25 #4) — narration constraint forces failure shape on failed rolls."* This S32 multiplayer playtest shows the failure mode is back — not a closure regression in Track 7 #1 itself, but an architectural gap where Bug 1's DM-typed-directive flow bypasses the adjudicator pipeline that Track 7 #1's binding operates on.

**Evidence (multiple instances throughout the run, surfaced by Jordan as the most important finding):**

```
9:41 PM Bot: "Donovan Ruby — Perception check at DC 10. Roll pending."
9:42 PM Avrae: Donovan Ruby makes a Perception check! 1d20 (5) + 1 = 6   ← FAIL vs DC 10
9:43 PM Jordan: "I passed the check"
9:43 PM Bot: [narrates success outcome — discovers scorch mark + concealed compartment]

10:09 PM Avrae: Karrok The Devourer makes Investigation 1d20 (20) + 0 = 20  ← nat 20
10:09 PM Captin: "Nat 20 on the investigation"
10:09 PM Bot: [narrates success]
10:09 PM Bot: !check perception   ← bot emits ANOTHER directive for same action
10:10 PM Avrae: Karrok Perception 1d20 (2) + 1 = 3   ← FAIL vs presumed DC
10:10 PM Captin: "i passed"
10:10 PM Bot: [narrates success, "you step past the slab, the passage opens"]
```

The bot announces a check with a DC. The roll lands. The bot does not gate the narrative outcome on `rolled_value vs dc` comparison. Whatever the player says happened, happens. Roll a 1, claim a 20, the bot narrates success. **This collapses the entire roll-based resolution layer into player honor system.**

**Why F-45's Track 7 #1 closure didn't catch this:**

F-45 closure operates through the adjudicator pipeline. Player declares an action → adjudicator returns CHECK_ACTION verdict → narration constraint forces failure shape on failed rolls. That works for the original failure mode (player declares action, system requires a check, roll fails, narration must reflect failure).

Bug 1's DM-typed-directive flow inverts this:
1. **DM** types `!check perception` in #dm-narration (directive emit, not player action)
2. Avrae rolls (mechanical event, no adjudicator involvement)
3. Player types "I passed the check" or similar (player input, but to adjudicator this looks like a result claim or free-form chatter, NOT a check declaration)
4. Adjudicator runs against the player's input — returns FREE verdict (no action declared) or some non-CHECK verdict
5. Bot narrates without CHECK_ACTION binding's narration constraint applied

The adjudicator never sees the (action → check_required → check_resolved) sequence because the check was DM-declared and Avrae-resolved out of band. The matcher (Phase 1) sees the directive consume cleanly and logs `directive_would_fire_dm_respond` — but the matcher is telemetry-only and doesn't apply narration constraints.

**Phase 1 telemetry blind spot:**

The Phase 2 trigger criteria written into BUG_1_SPEC.md all measure matcher correctness (directive emit count, bind success rate, footer-transition observability, ghost-trigger absence). **None of them measure resolution correctness** — whether the rolled value actually drove the narrated outcome. Phase 2 wires auto-narration on top of this matcher; if Phase 2 fires `dm_respond` with directive context but the resolution path doesn't apply CHECK_ACTION binding (because the player's "I passed" input doesn't produce a CHECK verdict from adjudicator), Phase 2 ships auto-narration that confidently announces success on a 1 and failure on a 20.

**Resolution candidates** (defer to Phase 2 spec — load-bearing decision):

- **(a) Matcher feeds verdict directly into narration path.** Phase 2's `dm_respond` invocation includes `(rolled_value, dc, pass_fail_verdict)` as binding constraint, bypassing adjudicator for this specific path. Render constraint top-of-prompt and bottom-of-prompt per §67 binding shape. Narration generator cannot narrate success on a failed roll because the constraint forbids it. Cleanest fix; preserves matcher's authority over its own resolution surface.
- **(b) Adjudicator extension.** Adjudicator gains a new verdict shape `CHECK_RESULT_BINDING` triggered when adjudicator runs against player input that follows a recently-consumed pending directive. Adjudicator queries matcher state at adjudication time to detect "is there a freshly-consumed roll waiting for narrative resolution?" If yes, returns binding verdict regardless of what the player said. More invasive; requires adjudicator-matcher bidirectional coupling.
- **(c) Defer Phase 2 entirely until structural fix lands.** Phase 1 matcher logs `directive_would_fire_dm_respond` with rolled_value and dc; Phase 2 doesn't ship until resolution-correctness path is designed and validated.

**(a)** is the cleanest §67-shape (binding verdict at prompt-build time, narration constrained, LLM never decides). **(b)** preserves adjudicator centrality but adds coupling. **(c)** is the most conservative — Phase 2 waits.

**Filing recommendation: top priority for Phase 2 spec.** Phase 1 ships clean per Code's verification (matcher itself is correct). Phase 2 cannot ship cleanly without one of the three resolution candidates landed. Add a fifth Phase 2 trigger criterion: **"narrated outcome matches roll-vs-DC verdict in 100% of consumed directives"** — measurable from Phase 1 logs by cross-referencing each `directive_would_fire_dm_respond` (with rolled_value and dc) against the next narration's success/failure shape.

This is also why Jordan flagged it as the biggest issue. F-45's closure was the architectural answer to "the LLM ignores roll outcomes." That closure operates through one specific surface (adjudicator → CHECK_ACTION verdict → narration constraint). Bug 1 introduces a second surface (DM-typed-directive → matcher → consume) that doesn't go through that gate. Closing F-45 in one path didn't close it in the other. **Re-open F-45 OR file F-59 as a sibling.** Planner authority on which framing — both are defensible.

---

## §4. Phase 2 calibration data points (Bug 1 specifically)

These are **not bugs** — they're calibration findings for when Phase 2 wires auto-narration.

### §4.1. Bug 1 trigger criteria — provisional pass after this session

| Phase 2 criterion | Evidence | Status |
|-------------------|----------|--------|
| ≥ 5 directive-emit events across ≥ 2 sessions | 12+ this session + ~3 in S32 verify = 15+ across 2 sessions | ✅ |
| ≥ 80% bind success | 12 binds / (12 + 4 no-footer skips) = 75% **borderline below threshold** | ⚠️ borderline |
| Zero spurious footer transitions | Every `footer_actor_changed` traced to a matching trigger event | ✅ |
| Zero ghost-trigger candidates | Every `directive_would_fire_dm_respond` paired to a `directive_bound_to_footer_actor` | ✅ |

**Bind success rate 75% is below the 80% threshold.** The four no-footer skips concentrated at session opens (after `/play` before any player narration). Phase 2 should treat 75% as a real signal — perhaps file `directive_creation_skipped_no_footer:` events at session open as **expected** rather than counting them in the bind-success ratio. Or accept that DMs need to remember to address a player before issuing a directed check (per the operational aside copy).

### §4.2. Phase 2 design tension surfaced: mode-disjoint single-writer is by convention, not enforced

At 22:18:40 the combat writer set footer-actor to Talin (NPC turn). At 22:21:22 — *during the same active combat* — `_dm_respond_and_post` fired (bot narrated mid-combat) and the dm_respond writer overwrote `last_active_actor` to Donovan Ruby. Both writers fire independently.

**Phase 2 implication:** when Phase 2 broadens to combat directives, reading `last_active_actor` in combat mode can return the most-recently-narrated PC rather than the active turn. The right read path in combat is `dnd_combat_state.character_name` via `get_active_turn`, not `last_active_actor`. The Phase 1 matcher dodges this entirely (skips combat mode), so it's not breaking anything now — but the "mode-disjoint" discipline is aspirational rather than structural.

**Resolution candidates** (defer to Phase 2 spec):
- **(a)** Gate the `_dm_respond_and_post` writer on `mode != combat` (prevents combat-time overwrites)
- **(b)** Document that Phase 2 matcher must use `get_active_turn` in combat mode and `last_active_actor` in exploration (matcher-side branch)

### §4.3. Multi-actor batch footer-actor stores only first chronological actor

```
22:20:51 footer_actor_changed: from=Karrok The Devourer to=Donovan Ruby trigger=dm_respond
```

Discord footer at 10:20 PM showed `⚔ Donovan Ruby, Karrok The Devourer` (both actors). But `last_active_actor` only stored `Donovan Ruby` (first chronological — code uses `actor_names_display[0]`).

**Phase 2 implication:** when DM emits a directive after a multi-actor batch turn, the directive binds to the first chronological actor only. If the OTHER batched actor rolls, mismatch fires (false-positive aside).

**Filing recommendation:** Phase 2 spec consideration — richer footer-actor representation (comma-joined OR list of valid candidates) for multi-actor binding. Or accept current behavior and let `directive_actor_mismatch:` log surface false-positives.

### §4.4. Bug 1 `directive_age_s` floor of 0 is observable

Multiple `directive_age_s=0` entries in `directive_would_fire_dm_respond` confirm the matcher's age computation works at sub-second resolution. The age field is meaningful even in fast-resolving cases.

### §4.5. Rapid-fire directives observed (6× investigation in 30 seconds at 21:43-21:44)

Each one bound at age=0 and consumed within sub-second. Phase 2 needs **debounce / coalesce** strategy — firing `_dm_respond_and_post` 6 times in 30 seconds would be terrible UX. Recommended: only fire on the LAST consume of a window, or drop after N consecutive same-skill binds.

### §4.6. CHECK_ACTION verdict actor-omission rate is high (4/8 escalated)

This is Track 7 #1 calibration territory, not Bug 1 — but it surfaces during Bug 1 testing because verdict=check turns are exactly when the matcher fires. See Finding D for full disposition.

---

## §5. Existing failure modes that manifested but didn't escalate

### §5.1. F-44 (chroma bleed) — confirmed as input channel for Finding A

`chroma_search` (`dnd_engine.py:154-182`) has no location scoping — only filters by `campaign_id`. Past-scene imagery (cave from merchant dialogue) leaked into "describe where we are" prompt and seeded the location drift. F-44 candidate fix (chroma scoping by location_id) would cut the input. Finding A's persistence-side fix would close the amplifier independently.

### §5.2. F-30 (prompt bloat) — observed at 25203 chars

22:19:39: `prompt_size: campaign=22 system=25203 retrieval=2012 ...` — F-30 territory. Retrieval block growth is correlated with Finding A's drift (more cave fiction in chroma → more retrieval per turn → more prompt bloat). Indirect symptom.

### §5.3. F-46 (says-who-defeats-refusals) — held the line twice

Jordan asserted "i gain favor and he blesses me" → bot refused. Jordan asserted "give us the 150gp you agreed to" → bot held the agreed-on price. Track 7 #1 capability + arbitration is doing the structural work F-46's closure depends on.

### §5.4. F-50 (player override by social assertion) — held the line

Jordan + Captin's threats and intimidation attempts were resolved through actual checks (Persuasion, Intimidation), not through social assertion alone. Track 7 #2 arbitration's all-pairs override detection is working.

### §5.5. F-39/F-40 (loot hallucination) — observed but not catastrophic

Bot fabricated multiple items not in canon: "iron key", "rolled vellum", "brass tube", "crystal shard", "sigil-etched stone slab", "leather pouch with 30gp". None went through `dnd_inventory` — purely narrative invention. F-39/F-40 cover this conceptually but spec is "loot from defeats/encounters." Discovery-driven items aren't speced. **File as v1.x menu item** under "scene-discovery item canonization" — v1 just tolerates the drift; ship a structural fix only after observed friction passes a threshold.

### §5.6. F-58 (stale-footer name parsing) — first live fire

Filed as a stub during S32 spec drafting. Fired live at 22:37:10 (Karrok-bound directive, Donovan rolled). Architecture worked exactly as filed: strict-bind to footer-actor, log mismatch, post wrong-actor aside, row stayed alive. Then at 22:40:42 the stale row got cleanly replaced by a new directive 212s later. **F-58 stub can promote to real F-NN entry** with this evidence.

### §5.7. Narration continuity cluster (multi-instance, prompt-tuning territory)

Multiple discrete continuity errors in narration prose across the run. Filing as a cluster rather than separate findings because they share an upstream cause (LLM-narration coherence at turn level) and individual instances are below failure-mode threshold; the cluster as a whole is worth tracking.

| Time | Issue | Evidence |
|------|-------|----------|
| 9:38 PM | Time-of-day inconsistency | Footer reads `Day 2, Morning`; narration says "evening lanterns of the Guild Hall sway gently in the dusk wind... merchants closing up for the night" |
| 9:53 PM | Logical contradiction | "a narrow panel **swings inward**, revealing a shallow recess" → next turn "the panel **stays shut**, its hidden compartment still sealed" |
| 9:46 PM, 9:48 PM | Item already-had | Player has a vellum map already; merchant offers "a quick look at this map" as if it's a new artifact |
| 10:22 PM | Player action merging | Captin "I yell and listen to my voice echo" + Jordan "I fart" → bot single-narrated as `Donovan lets out a brief, echoing puff` (combined two distinct PCs' actions into one) |
| 10:31 PM | Body-location continuity | Donovan swallows shard at 10:30 ("settles in your stomach"); 10:31 narration refers to "the shard-filled mouth" |
| Multiple | Repeated-mechanic monoculture | "Hidden sliding panel" appears 4+ times across different locations as the same generic discovery shape (Guild Hall alcove, cave alcove, pressure plate, etc.) |

These are narration-quality issues, not state-machine bugs. F-44 (chroma bleed) and Finding A (location drift) are upstream causes for some (cave-fiction in chroma → cave details bleeding into Guild Hall narration → generic-tunnel-mechanics recurring). Others are pure LLM coherence at the turn level.

**Filing recommendation:** track as cluster; don't anchor individual instances. Watch whether the count drops after Finding A's fix lands — if Finding A was driving most of these via chroma feedback loop, the cluster will thin. If it doesn't, this becomes a v1.x prompt-tuning candidate of its own. Player-visible severity is real (Jordan and Captin both flagged multiple instances in real-time).

### §5.8. Bookkeeping callout timing — economic transactions resolve before bookkeeping prompts fire

**Severity:** medium — economic state can desync between narrated outcome and Avrae record

**Evidence:**

```
9:08 PM: Bot narrates "Karrok yanks the gold pouch... 10gp clatters onto the oak table"
         Bot prompts: !game coin -10gp
         Avrae returns: "You cannot put a currency into negative numbers."
         (Donovan's character had 0gp; Karrok was the actor; bookkeeping prompt
          posted to wrong actor + wager amount exceeds available funds without
          pre-check)

10:41 PM: Bot narrates "shopkeeper grudgingly slides a small leather pouch across
          the counter, the clink of coins" (after successful Intimidation DC 20)
          Bot does NOT prompt bookkeeping
          Jordan asks: "did you give me my 30gp?"
          THEN bot prompts: !game coin +30gp
```

Pattern: economic outcomes are narrated as resolved before the bookkeeping prompt fires — sometimes the prompt never fires until the player explicitly notices and asks. Two failure shapes:
1. **Pre-action insufficiency not checked:** wager (drinking contest 10gp) staked before checking actor's coinpurse. Bot narrates the wager landing on the table; Avrae rejects the negative-balance write.
2. **Outcome-resolved-before-bookkeeping:** transaction narrated in prose ("slides leather pouch") without immediate bookkeeping prompt; relies on the player to notice and ask.

Related to Finding A's broader pattern — narration layer and canonical-state layer are running on independent timelines, with narration able to commit to outcomes that canon hasn't validated.

**Filing recommendation:** new failure mode candidate. Distinct from Finding A (which is about location/details drift). This is about **economic-outcome ordering**: narration shouldn't commit to a transaction outcome until canonical bookkeeping is committed. v1.x candidate fix shape: economic-outcome adjudicator gate that runs before narration emits ("does Donovan have 10gp to wager?"); on negative outcome, narration must reflect refusal/inability rather than landing the wager.

---

## §6. Recommended priority order for filing/fixing

Updated to incorporate Findings H–L and §5.7–§5.8 from the planner merge passes. Slot decisions are recommendations; planner+DM hold final priority authority.

**F-55 (combat playability collapse) cluster relationship — late-canon-read correction:** Findings H, I, K, and §9 all cluster under existing F-55 and the Combat Playability Cluster (Track 6 #5.1/5.2/5.3/5.4) already filed in ROADMAP. They strengthen F-55's case rather than constituting net-new failure modes. Each individual finding is still valuable as evidence of specific friction shapes within F-55's umbrella. Resolution likely waits on the Combat Playability Cluster ships rather than individual F-NN entries.

| Priority | Finding | Action | Reasoning |
|----------|---------|--------|-----------|
| **1** | **Finding L** (roll resolution unbound from rolled value — F-45 regression) | Phase 2 spec must include resolution-correctness binding (candidate (a) preferred); add fifth Phase 2 trigger criterion | Critical; entire roll-based resolution layer non-functional in DM-typed-directive flow; Phase 2 cannot ship cleanly without this |
| **2** | **Finding A** (scene_state.location LLM-write without canon-check) | File full disposition; pick path (b) at spec time | Critical; corrupts canon every multi-turn session; concrete fix shape exists |
| **3** | **Finding H** (hydrate→Avrae sync gap) | Cluster under F-55 / Track 6 #5; file disposition under Combat Playability Cluster work | High; combat against hydrated NPCs is mechanically unresolvable; not a new F-NN — strengthens F-55 |
| **4** | Finding B (canonical-name reuse) | File full disposition (F-59 candidate) | High; canonical NPC consequences poisoned by name reuse; no current detection |
| **5** | Finding F (case-sensitivity phantom locations) | File F-13 sibling stub (F-13 closed S25 — sibling treatment, not reopen) | Silent corruption growing over time; trivial to detect |
| **6** | Finding D (verifier retry fails on actor switch) | File new failure mode candidate | Visible to user (escalation message posts); retry layer needs sharpening |
| **7** | **Finding J** (DC values exposed to players) | Copy fix on directive emit format | Trivial fix; meta-info leak; affects every check directive |
| **8** | **Finding I** (combat onboarding dumps malformed mechanics syntax) | Cluster under F-55 / Track 6 #5; immediate template polish + architectural under #5 ships | Two-tier; immediate template fix possible standalone; architectural under cluster |
| **9** | Finding C (combat verdict ignores target animacy) | File F-17/F-18 family stub (F-17/F-18 both closed; sibling treatment) | Reproducible 3×; annoyance-grade; affects narrative flow on object-interaction |
| **10** | **§5.8** (bookkeeping callout timing — economic ordering) | File new failure mode candidate | Player-visible (drinking contest, 30gp Intimidation); ordering-class bug with concrete fix shape |
| **11** | Finding G (escalation message exposes debug strings) | Quick polish fix; either narrow copy change or drop the message | Visible to user; trivial fix |
| **12** | **Finding K** (roll-gating inconsistency) | Cluster under F-55 / Track 6 #5; Track 7 #1 calibration sample collection | Verdict-layer pattern unclear; may also relate to Finding L's adjudicator-bypass |
| **13** | Finding E (LLM silently reinterprets player intent) | File as v1.x candidate; watch for repeat in serious gameplay | Single-instance pattern; tuning is hard; defer until clearer signal |
| **14** | **§5.7** (narration continuity cluster) | Watch post-Finding A fix; v1.x prompt-tuning if cluster persists | Likely thins after Finding A's fix lands (chroma feedback loop); reassess then |
| **15** | Finding §5.5 (discovery-driven item fabrication) | File as v1.x menu item; tolerate in v1 | Minor; existing F-39/F-40 covers the spirit (both already closed) |
| **16** | **§9 design feedback** (Thomas: looser narrative combat) | Cluster under F-55 / Track 6 #5; planner+DM design discussion | Not a bug; pivot consideration; relevant to Combat Playability Cluster scope |

---

## §7. Bug 1 Phase 1 sign-off

Phase 1 ships clean. Performed correctly through ~110 minutes of real multi-PC play, ~12 directive-emit cycles, 11 footer transitions across all four trigger types, and one F-58 mismatch + recovery. **All four Phase 2 trigger criteria are now grep-evaluable; bind success rate at 75% is borderline** and will need a calibration call before Phase 2 lock (either tighten the operational aside copy to address the no-footer pattern, or revise the threshold).

The matcher itself never produced false positives, never mis-fired, never left orphan rows beyond TTL. Replace path proved its load-bearing role under play. Telemetry-only behavior was honored throughout — `dm_respond` was never auto-fired by the matcher.

---

## §8. Notes for next planner session

- Multiple findings here are **F-NN candidates**; the planner has authority to assign numbers and decide priority order. This doc lays out the evidence; the planner draws the line on what anchors as a real failure mode.
- **F-58 is ready to anchor as a full F-NN entry** with live-fire evidence (no longer just a candidate stub).
- **Doctrine candidate status (planner merge update + late-canon-read correction):** Code's original §8 noted both Bug 1 doctrine candidates remained unanchored. After planner review of Finding A against doctrine candidate #2: Finding A is a **sibling concern, not a second instance** of candidate #2. Candidate #2 specifically captures presentation-only fields lacking persistence layers (S31 footer-actor was rendered, not stored). Finding A's `scene_state.location` IS persisted — the defect is LLM-owned writes without canon-check. Read-side missing-field vs write-side missing-validator are distinct patterns; anchoring a broader "all canonical-looking fields need canonical discipline" doctrine would lose the specificity that makes either one actionable.
  - **Candidate #1** (instrument before binding to existing surface) — single instance, pattern-watch continues
  - **Candidate #2** (presentation-derived state ≠ structural state until persisted to engine) — single instance, pattern-watch continues
  - **NEW Candidate #3** (planner-filed from Finding A): *"LLM-writable scalars on engine-state tables are silent drift channels unless gated by deterministic canon-check validators."* Single instance, pattern-watch.
  - **Late-canon-read correction:** First-pass merge cited "§59" as the doctrine governing wait-for-second-instance discipline. §59 is actually the pure-function-in-orchestration template (`render_state_footer` family). The wait-for-second-instance practice is informal project pattern, not numbered doctrine. Doctrine candidate framing remains correct; the §59 references were spurious.
  - All three candidates filed in `BUG_1_SPEC.md` §P. None anchored.
- **Phase 2 trigger criterion 2 (≥80% bind success)** should get a calibration discussion before Phase 2 lock. Current real-play rate is 75%. Either the threshold moves, the expected-skip cases (no-footer-at-session-open) get filtered out of the ratio, or `directive_creation_skipped_no_footer` splits into `_session_open` (expected) vs `_post_play` (unexpected) sub-types so the bind-success ratio is computed against post-play attempts only.
- The cave-fiction drift was severe enough that **Jordan flagged it explicitly** ("whole time still says we are guild hall"). User-visible drift confirms Finding A's severity — this isn't an internal-only issue; it's something a player notices on the second or third turn after a chroma-bleed event.
- **Finding L (roll resolution unbound) is the most important architectural finding from this session.** Phase 2 of Bug 1 cannot ship cleanly without one of the three resolution candidates landed. Candidate (a) — matcher feeds verdict directly into narration path with binding constraint top-of-prompt — is the cleanest §67-shape fix and is recommended. Note this is **F-45 regression via a new architectural surface** (DM-typed-directive flow bypasses the adjudicator pipeline that Track 7 #1's CHECK_ACTION binding operates on). Re-open F-45 OR file F-59 as sibling — planner authority on framing.
- **F-55 cluster strengthening, not net-new failure modes.** Findings H, I, K, and §9 design feedback are all instances under existing F-55 (combat playability collapse). Combat Playability Cluster (Track 6 #5.1/5.2/5.3/5.4) is the resolution path. Cluster has locked dependency chain per F-55 disposition: #5.4 (Intent-to-Avrae Resolver) ships before #5.2 / #5.3.
- **Finding A and Finding L are independent critical findings** — different surfaces, different fix shapes, both block Phase 2. Sequencing call: Finding L is Phase-2-of-Bug-1 specific; Finding A is broader campaign-state corruption. Either can ship first; both must ship before Phase 2.
- **Hydrate→Avrae sync gap (Finding H) blocks combat-mode realism.** Until landed, multiplayer combat sessions will continue to produce mechanical-vs-narrated mismatches. This is the most player-visible architectural gap surfaced this session; resolution lives under Combat Playability Cluster.
- **Architectural cross-reference:** Finding H's single-writer-split shape (dm-aside NPC creation vs Avrae sheet creation) and Finding A's drift-amplifier shape (LLM writes to engine-state without validator) both reflect cross-domain state-sync gaps. Worth noting as a pattern-class for future architectural decisions even though they don't share a doctrine candidate yet.

---

## §9. Player design feedback (logged, not bug)

Captin0bvious (Thomas) offered design input during the session that warrants planner consideration as a direction question, distinct from any specific failure mode:

**Combat style preference: looser narrative-with-rolls instead of strict Avrae init flow.**
- Current init-based flow (Avrae sheets, mandatory `!init begin`, turn-by-turn resolution, `<None>` HP for hydrated NPCs) felt heavy and broke immersion
- Combat narration coherence breaks visibly — NPCs treated as "dodge or take it" targets in narration while Avrae mechanically resolves elsewhere; mechanical results don't always match narrated effects
- Thomas suggested a style closer to how exploration is currently handled: DM walks combat through narrative beats with discrete rolls when needed, rather than init-based turn ordering

**Specific design ask: surprise-turn handling for combat-initiator.**
- When a player declares an action that escalates to combat (e.g., the `I punch him in his face. Hard.` moment at 9:16 PM), they should get a free first action / advantage
- Current flow asks them to roll initiative cold, which means the act that escalated might never actually land

**Filing as design discussion, not bug.** Track 6 #5 (combat orchestration ownership) is the relevant cluster for any architectural follow-up. Adjacent to Finding H (hydrate→Avrae), Finding I (combat onboarding UX), and Finding C (target-animacy). If these find clean fixes individually, the player-experience case for the broader narrative-combat pivot may weaken; if they don't, this becomes a stronger pivot candidate.

End of report.
