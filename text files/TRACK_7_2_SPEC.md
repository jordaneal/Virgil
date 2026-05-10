# Track 7 #2 — Multi-Action Arbitration + Post-LLM Verification — Design Spec v1 (LOCKED)

**Status:** LOCKED — Session 2 review complete (post-review amendment pass #2). All §11 decision points are locked: §11.A–§11.J ratified at Code's recommended defaults from the review doc; §11.K, §11.L sub-item (1), §11.M–§11.P pre-locked during Session 1 amendment pass; §11.Q (actor-name source of truth) and §11.R (3+-actor override semantics, all-pairs) newly locked during Session 2 review. Three review-doc margin notes also lifted into spec proper (§4 signals key shape, §6.3 per-category placeholder branching, §8.4 two-actor live-verification). Spec enters Session 3 implementation against this lock.
**Pattern:** Extends the binding-adjudication architecture established by Track 7 #1. Two mechanisms ship together because they share a single architectural shape — **structured intent objects and structured output verdicts** — and closing the multiplayer-failure surface requires both.
**Track:** Track 7 #2 — promotes adjudication from single-actor/single-input to (a) multi-actor concurrent input arbitration and (b) LLM-output verification.
**Failure modes this targets:**
- **F-48** — Concurrent player input collision. Two players post within the coalesce window; only one is meaningfully addressed; the other is absorbed into the combined string and silently dropped. Closes through **multi-action arbitration** (input side) and **ACTOR_OMISSION verification** (output side — see §11.M).
- **F-49** — LLM-fabricated NPCs entering combat with no Avrae backing. Silent Beast and Keeper of the Vein invented mid-narration; combat narrated for ~6 turns with init tracker dormant. Closes through **post-LLM verification pass**.
- **F-50** — Player override of another player's action by social assertion. Tazz takes the flute and throws it; Jordan posts "nuh uh you cant do that its mine"; the LLM rolls back without a contested check. Closes structurally as a side effect of **arbitration's cross-player override priority rule**.

The architectural diagnosis: Track 7 #1 binds `adjudicate(player_input, ...)` per-turn against a single coalesced string. Two players' inputs are concatenated by `ActionBatcher` before adjudication runs, so the gate sees one input and chooses one verdict — whichever pattern hits first wins, the other player's intent is invisible. And the LLM's output is unadjudicated entirely — narration is the trust boundary. Adjudication closes the input side; #2 closes the input-multiplexing side and the output side.

---

## 1. Proposed decisions (NOT yet locked — see §11)

These are what I'd propose if the spec went straight to implementation. Every one is up for change in review.

1. **Two new compute surfaces, both pure functions, both Doctrine §59 siblings.**
   - `arbitrate(actions, scene_state, characters, combatants, active_turn, intent_per_actor) -> ArbitrationResult` in `adjudicator.py`. Wraps per-actor `adjudicate()` calls and resolves the verdict bundle.
   - `verify_narration(narration_text, adjudication_result, scene_state, combatants, npcs_canonical) -> VerificationResult` in a NEW module `narration_verifier.py`. Per Doctrine §63, forks at the highest layer where invariants diverge — input adjudication asks "is this attempt allowed?" while output verification asks "did the narration honor the verdict and stay in canon?". Different actors, different invariants; sibling, not extension.

2. **Single entry point preserved per direction.**
   `adjudicate(...)` stays the player-input entry. `arbitrate(...)` is its multi-actor wrapper — when only one actor is present, it short-circuits to a single `adjudicate()` call (degenerate-case fall-through, not separate code path). Solo play and single-input multi-player turns hit the same code under arbitration; the bundle just has one element.

3. **`ArbitrationResult` is an ordered list of `AdjudicationResult` plus a merge plan.**
   - `verdicts: list[AdjudicationResult]` — one per actor input, ordered per the priority rule (see decision 5).
   - `merge_plan: str` — `'sequence'` (resolve in priority order, narration honors all in turn) or `'override'` (one verdict wins, others are noted but not honored — used only when verdicts directly contradict, e.g. one CHECK passes, another player's RP claims that very outcome was reversed).
   - `combined_constraint: str` — single rendered narration constraint that the prompt-builder consumes. Encodes the priority and merge plan imperatively so the LLM cannot re-order.
   - `signals: dict` — telemetry-only, flattened for the per-turn log line.

4. **Arbitration sits ABOVE the existing combat off-turn drop (Phase 2A.3).**
   2A.3 fires at transport (`on_message`) and drops off-turn input in combat with ⏳ before anything reaches the batcher. By the time arbitration runs, combat-mode multi-actor input is already filtered to the active turn's controller. Arbitration in combat is therefore a degenerate single-actor case under v1; the multi-actor path is exercised in non-combat (exploration/social/downtime) where 2A.3 is silent. **Arbitration does NOT relax 2A.3** — combat-mode concurrency stays filtered at transport, where the existing architecture already handles it.

5. **Cross-player override priority rule (locked v1):**
   `WORLD_BOUNDARY > COMBAT > CAPABILITY > CHECK > FREE`, with ties broken by **arrival timestamp** (earlier wins). Conflict detection is **all-pairs** (per §11.R): the override scan compares every pair of verdicts (i, j), not just adjacent pairs in priority order. Override fires when ANY pair contradicts. When verdicts contradict (one's CHECK rolled and resolved, another's narration asserts the resolved outcome did not occur), the **higher-priority verdict in the contradicting pair is binding**; the lower-priority/social-assertion verdict is rendered with `merge_plan='override'` and a constraint instructing the LLM "the contradicting actor's narration asserted the binding actor's resolved outcome was reversed. The binding actor's verdict stands. Narrate the contradicting actor's reaction to the bound outcome — do not narrate the outcome itself as reversed." All overridden actors are captured in `overridden_actors: list[str]` (per §11.R). This is the structural close of F-50, and extends cleanly to 3+ actors.

6. **Post-LLM verification pass detects four classes of violation (locked taxonomy for v1):**
   - `FABRICATED_COMBATANT` — narration introduces a creature name not in `dnd_npcs` (canonical), `dnd_combat_state` (active init), or skeleton-declared NPCs, AND the narration treats the creature as a combat participant (verbs: attacks, swings, hits, charges, blocks, parries, casts at, springs from). Closes F-49.
   - `VERDICT_CONTRADICTION` — narration contradicts the binding `AdjudicationResult` of the turn (e.g., adjudication REFUSED a capability, narration describes the capability as having worked; adjudication marked a CHECK as failure, narration describes a partial-success outcome; adjudication marked combat as inactive and refused, narration narrates damage landing). Detects regressions of the very gate Track 7 #1 ships.
   - `STATE_MUTATION_CLAIM` — narration claims state mutations the LLM is structurally not allowed to make: "the goblin takes 12 damage" (HP belongs to Avrae), "you gain a level" (XP belongs to Avrae), "the door is now permanently open" (location-state belongs to canonical writers). LLM may DESCRIBE damage rhetorically ("the goblin staggers"); it may not assert mechanical numbers as state.
   - `ACTOR_OMISSION` — narration omits an actor whose verdict was non-FREE (had a binding constraint). For each actor in `arbitration_result.actor_order`, check whether the actor's name appears as a substring in the narration; if any non-FREE actor's name is missing, the violation fires. Closes the output-side of F-48 (a binding verdict that the LLM silently drops becomes a structural violation, not a telemetry-only observation). Pronoun-aware detection deferred to v1.x — see §11.M sub-decision.

7. **On detection: regenerate up to 1 retry; on second violation, hold-message with refusal narration fallback.**
   Total LLM budget per turn is bounded at 2 calls (initial + 1 retry). Retry prompt prepends a `=== VERIFICATION FAILED ===` block describing which class of violation was detected and what the retry must NOT do. Second violation → hold the LLM output, post a deterministic "the world holds its breath" placeholder narration that surfaces the adjudication verdict imperatively (`"Donovan's stealth check fails. The lookout turns toward the noise."`), and emit `verification_escalated:` log line. Never block narration entirely; never silently ship a violating narration. Filed under §11.I as the highest-confidence decision needing Jordan's call.

8. **Verification reuses adjudication's canonical-NPC sources.**
   `narration_verifier.py` reads from `dnd_npcs`, `dnd_combat_state`, and skeleton-declared NPCs to validate fabricated-combatant detection. No new schema. No new writers. Pure-read function returning `(verdict, signals)`. The detection regexes mirror `_WORLD_BOUNDARY_PATTERNS` shape from #1 — verb proximity, named-entity capture — but operate on LLM output not player input.

9. **Single feature flag per mechanism for staged rollout.**
   - `ARBITRATION_ENABLED = True/False` — when False, `arbitrate(...)` short-circuits to first-actor-only behavior (current v1 behavior preserved).
   - `VERIFICATION_ENABLED = True/False` — when False, `verify_narration(...)` returns `VerificationResult(passed=True, signals={...})` immediately and the post-LLM gate is bypassed.
   Independent flags so each mechanism can ship and revert independently if either misbehaves in production.

10. **Telemetry — two new per-turn log lines (always-fire, empirical-baseline shape per Doctrine §59).**
    - `arbitration: campaign={N} actors={N} verdicts={cat:cat:cat} merge_plan={sequence|override} priority_order={A,B,C} fired={1|0}` — fires every turn; `actors=1` is the degenerate fall-through case. Drives empirical actor-count distribution and merge-plan frequency.
    - `verification: campaign={N} passed={1|0} violation_class={fabricated_combatant|verdict_contradiction|state_mutation|actor_omission|none} retry_fired={1|0} retry_passed={1|0} escalated={1|0}` — fires every narration. Drives empirical violation rate, retry success rate, and escalation frequency. The numbers gate whether v1.x tightens regexes, expands the violation taxonomy, or extends to additional classes.

---

## 2. Goal — which THE_GOAL bullets this serves

Direct hits on the failure-mode list:

- ✅ **"Player agency has to survive the AI."** F-48 was the cleanest violation of this in S25 #3 — Jordan typed an action and the AI absorbed it without resolution. Arbitration converts every player's input into a verdict the LLM cannot drop on the **input** side; ACTOR_OMISSION verification (§11.M) enforces the same invariant on the **output** side — any non-FREE actor whose name doesn't appear in narration triggers regen. F-48's closure proof is now input-layer structural (arbitration) + output-layer structural (ACTOR_OMISSION), not input-layer structural + output-layer observability. F-50 was the inverse — one player's narration overrode another player's resolved outcome. The cross-player priority rule structurally prevents social-assertion override of mechanical resolution.
- ✅ **"NPCs we wronged should still be wronged."** F-49 is the inverse failure: NPCs we never met still walk in. Verification's fabricated-combatant gate refuses LLM narration that introduces hostile entities outside canonical sources, structurally reinforcing the "narration describes reality, doesn't create it" invariant for LLM output.
- ✅ **"If failed rolls just stop play instead of changing the situation, we've failed."** Track 7 #1 binds the verdict; #2's verification catches the cases where the LLM ignores the bound verdict mid-narration. Verdict-contradiction detection is the structural floor that prevents narration drift from re-inverting #1's gates.
- ✅ **"I want combat to be fun. I want to feel something when I kill an enemy."** Combat where the enemy didn't exist isn't combat — it's simulation theater. Verification's fabricated-combatant gate ensures every combat narration is grounded in a real init-tracker entry, which is the precondition for kills mattering.

Indirect hits:
- **"The world should reward curiosity."** Indirectly — arbitration ensures that when one player's curiosity action hits while another player is loud and combat-y, the curious action still gets resolved. The quiet player isn't drowned out by the dramatic one.
- **"Choices should matter later, not just in the moment."** Same as #1 — choices that fail to resolve in the moment can't matter later. Arbitration extends "resolves in the moment" from one actor per turn to N actors per turn.

Bullets v1 explicitly does NOT serve:
- "Memorable details should recur intentionally, not compulsively." (F-52, motif drift). Verification's taxonomy is locked to three structural classes; texture problems like motif loops are out of scope per the prompt's "out of scope" list. Filed for v1.x.

---

## 3. Architecture pattern

### Where each mechanism sits

```
                    Player messages arrive
                            │
                            ▼
              [Phase 2A.3 off-turn drop in combat]   ← unchanged; transport-level
                            │
                            ▼
                    ActionBatcher.add(...)            ← unchanged; coalesces window
                            │
                            ▼ (after window expires, callback fires once)
              _dm_respond_and_post(actions=[...])
                            │
                            ▼
                       dm_respond(...)
                            │
                            ▼
             ┌──────────────────────────────────────┐
             │ arbitration_result = arbitrate(      │  ← NEW (mechanism a)
             │    actions=[(actor, text), ...],     │
             │    scene_state, characters,          │
             │    combatants, active_turn,          │
             │ ) → ArbitrationResult(               │
             │      verdicts=[Adj, Adj, ...],       │
             │      merge_plan, combined_constraint │
             │      signals)                        │
             └──────────────────────────────────────┘
                            │
                            ▼
             build_dm_context(arbitration_block=...)  ← consumes combined_constraint
                            │
                            ▼
                       LLM call → narration
                            │
                            ▼
             ┌──────────────────────────────────────┐
             │ verification = verify_narration(     │  ← NEW (mechanism b)
             │    narration_text,                   │
             │    arbitration_result,               │
             │    scene_state, combatants,          │
             │    npcs_canonical) → VerificationResult │
             │      (passed, violation_class,       │
             │       retry_constraint, signals)     │
             └──────────────────────────────────────┘
                            │
                            ▼
             passed? ──yes──► post narration
                │
                no
                ▼
             retry_count < 1? ──yes──► re-call LLM with retry constraint, re-verify
                │
                no
                ▼
             [escalation: deterministic placeholder narration honoring verdict]
                            │
                            ▼
                       post message
```

### What's new

- **`adjudicator.arbitrate(...)`** — wraps per-actor `adjudicate()` calls; produces `ArbitrationResult`. Lives in existing module to share canonical helpers (`render_adjudication_block`, etc.) and because the verdict dataclass is the same primitive.
- **`ArbitrationResult` dataclass** — verdicts list, actor_order (character names per §11.Q), merge plan, combined constraint, `overridden_actors: list[str]` (per §11.R, list-shaped to capture multi-overridden cases under all-pairs conflict scan), signals.
- **New module `narration_verifier.py`** — `verify_narration(...)` and supporting regex/canon-lookup helpers. Forked sibling per Doctrine §63 (different actor → different invariants).
- **`VerificationResult` dataclass** — `passed: bool`, `violation_class: str`, `retry_constraint: str`, `signals: dict`.
- **`_FABRICATED_COMBATANT_VERBS`** — curated list of combat-active verbs that, when paired with a non-canonical entity name, trigger the fabricated-combatant gate.
- **`_STATE_MUTATION_PHRASES`** — curated list of LLM state-claim phrases ("takes N damage", "is now dead", "gains a level", "the door is permanently"). Detection-only; mitigation is regen.
- **`_ACTOR_OMISSION_CHECK`** — substring scan of `arbitration_result.actor_order` against narration text for non-FREE actors. Detection-only; mitigation is regen with retry constraint naming the missing actor (§11.M).
- **One new kwarg in `build_dm_context`:** `arbitration_block=""` (replacing `adjudication_block=""` from #1; old kwarg becomes a single-actor degenerate case rendered through arbitration's combined_constraint). Locked rename — see §11.N.
- **One new render block:** `=== ARBITRATION RESULT ===` (renames `=== ADJUDICATION RESULT ===` to capture the multi-actor general case; single-actor turn still renders identically to today via degenerate fall-through). Locked rename — see §11.N.
- **Retry-constraint render:** `=== VERIFICATION FAILED ===` block prepended to system prompt on retry, naming the violation class and what the retry MUST NOT do.
- **Two new log lines:** `arbitration:` and `verification:` per turn.
- **Two new feature flags:** `ARBITRATION_ENABLED`, `VERIFICATION_ENABLED`.

### What's reused

- **`adjudicate(...)`** — called per actor by `arbitrate(...)`. Unchanged signature; unchanged behavior. Reuse, not extension.
- **`AdjudicationResult`** — unchanged. ArbitrationResult composes a list of these.
- **Canonical NPC sources** — `dnd_npcs`, `dnd_combat_state`, skeleton-declared NPCs. Verification reads from same sources adjudication uses for COMBAT_ACTION gating. No new state.
- **`ActionBatcher`** — unchanged. Already produces `actions: list[(display, action, user_id)]`. Today's `combined_action: str` is concatenation of those; arbitration consumes the structured list and discards the concatenated form.
- **The `(body, signals)` pure-function pattern** (Doctrine §59).
- **Top + bottom render** (Doctrine §2 + §48) — combined_constraint renders both at top and bottom of system prompt, preserving #1's belt + suspenders shape.

### What's NOT changed

- **Phase 2A.3 off-turn drop** stays at transport. Combat concurrency is still architecturally filtered before arbitration sees it. Arbitration's multi-actor surface is non-combat.
- **`adjudicate(...)` signature.** Per-actor adjudication is unchanged. Track 7 #1's invariants stay intact.
- **`ActionBatcher`** coalesce window, key by `guild_id`, fire-once-per-window. Window duration is decision §11.A but the batcher itself is unchanged.
- **Avrae write boundary** (Doctrine §65). Verification reads from canonical state to validate narration; never emits `!`-prefixed commands. Detection-only; mitigation is regen or placeholder.
- **The single-character `primary_ctx`** assumption in `dm_respond`. Arbitration runs per-actor with each actor's cached context; the merged narration constraint resolves which character is the prompt's "primary" actor (the highest-priority verdict's actor).
- **DM philosophy block, retrieval, party block, scene block, all directive blocks.** Composed identically; arbitration's combined_constraint occupies the slot today's `adjudication_block` occupies (renamed at the variable level only).

---

## 4. Data model

### `ArbitrationResult` (new dataclass)

```python
@dataclass
class ArbitrationResult:
    verdicts: list[AdjudicationResult]   # one per actor input, ordered by priority rule
    actor_order: list[str]               # CHARACTER NAMES (e.g. "Donovan", "Bruce") in priority order,
                                         # parallel to verdicts. NOT Discord usernames. Per §11.Q —
                                         # ACTOR_OMISSION substring scan operates on these character
                                         # names. The §5.2 prompt-render shape "JORDAN (Donovan)" is
                                         # human-clarity formatting in the rendered prompt only;
                                         # the field stores character name strings.
    merge_plan: str                      # 'sequence' | 'override' — single string per turn.
                                         # 'override' fires when ANY pair of verdicts contradicts
                                         # under the §11.R all-pairs scan; the overridden actors
                                         # are captured in `overridden_actors` (list, not string).
    primary_actor: str                   # actor (character name) whose verdict drives prompt's
                                         # "primary" ctx — highest-priority verdict's actor.
    combined_constraint: str             # imperative directive for prompt; encodes order + plan.
                                         # On 'override' with multiple overridden actors, render
                                         # enumerates each overridden actor's
                                         # reaction-not-outcome constraint per actor.
    overridden_actors: list[str]         # per §11.R — empty list when merge_plan='sequence';
                                         # populated with EVERY overridden actor's character name
                                         # when merge_plan='override' (any actor whose verdict
                                         # was contradicted by a higher-priority verdict in the
                                         # all-pairs scan). Replaces the prior single-string
                                         # overridden_actor field shape.
    signals: dict                        # telemetry-only — explicit keys defined at implementation
                                         # per #1's AdjudicationResult.signals posture; not
                                         # free-form dict-flatten. The arbitration: log line draws
                                         # from named keys; new keys require spec amendment, not
                                         # inline addition (per §11.E margin note lift).
```

### `VerificationResult` (new dataclass)

```python
@dataclass
class VerificationResult:
    passed: bool
    violation_class: str        # '' | 'fabricated_combatant' | 'verdict_contradiction' | 'state_mutation_claim'
    detected_phrase: str        # first 140 chars of the offending substring
    retry_constraint: str       # imperative directive for retry prompt
    canonical_combatants: list  # populated for fabricated_combatant; the names that were canonical
    fabricated_names: list      # populated for fabricated_combatant; names detected as fabricated
    signals: dict
```

### No new schema

Arbitration reads from existing state per existing helpers (`get_scene_state`, `get_combatants`, `get_active_turn`, `_CHARACTER_CACHE`).

Verification reads from:
- `dnd_npcs` (canonical NPCs per campaign — `npc_canonical_names_for_campaign(campaign_id)` helper)
- `dnd_combat_state.combatants` (active init order)
- Skeleton-declared NPCs via `skeleton_loader.get_known_npcs(campaign_id)` (new pure-read helper if not already exposed)
- The current turn's `ArbitrationResult` (to detect verdict contradictions)

No mutations. Pure-read.

If v1 needs cross-turn verification memory ("this NPC was fabricated last turn — second appearance is auto-canon"), filed as v2 under §10.

---

## 5. Detection / classification layer

### 5.1 Arbitration trigger and flow

`arbitrate(...)` runs as the FIRST orchestration step in `dm_respond` after `scene_state`/`characters`/`combatants` are loaded, replacing the current single `adjudicate(...)` call site (line `dnd_engine.py:4667`).

```
INPUT: actions = [(actor_name, text, user_id), ...]   # from ActionBatcher

1. Per-actor adjudication
   For each (actor, text) in actions:
     # `actor` here is the CHARACTER NAME (e.g. "Donovan"), not the Discord
     # username — per §11.Q, the actor_name string written into actor_order
     # and used by ACTOR_OMISSION detection is the bound character name.
     character_ctx = orch.get_cached_context(actor)
     if character_ctx is None:
       # Cache miss — typically a new player who hasn't posted !sheet
       # yet in-session. Defer per partial-projections doctrine; per §11.P.
       verdict = AdjudicationResult(allowed=True,
                                    refusal_kind="no_character_context", ...)
     else:
       verdict = adjudicate(player_input=text, scene_state, character=character_ctx,
                            combatants, active_turn, avrae_events,
                            skeleton_capabilities)
     append (actor, verdict) to verdict_pairs

2. Priority sort
   Sort verdict_pairs by:
     primary key: category priority (WORLD_BOUNDARY=5, COMBAT=4, CAPABILITY=3, CHECK=2, FREE=1, FALLBACK=0)
     tiebreak:    arrival timestamp (earlier first)

3. Conflict detection (ALL-PAIRS per §11.R)
   For each pair (i, j) of verdicts (i ≠ j, all combinations — NOT just adjacent
   pairs in priority order), check: does the lower-priority verdict in the pair
   contradict the higher-priority verdict's bound resolution?
     - A=CHECK with success/failure bound, B=FREE that asserts opposite outcome → CONFLICT
     - A=CAPABILITY refused, B=FREE that narrates the capability working → CONFLICT
     - A=COMBAT refused, B=FREE that narrates the attack landing → CONFLICT
   Track every actor that appears as the lower-priority side of any contradicting
   pair. On any conflict → merge_plan='override', overridden_actors=<list of
   every such actor's character name, deduplicated, in priority order>.
   Otherwise → merge_plan='sequence', overridden_actors=[].

   All-pairs (not adjacent) is the locked semantics so that 3+-actor turns
   correctly capture the case where actor A's CHECK is contradicted by both
   B and C independently, or where A-vs-B is non-contradictory but A-vs-C
   contradicts. Single-actor and two-actor cases reduce naturally — for N=1
   the pair-set is empty (sequence trivially), for N=2 there is exactly one
   pair to scan.

4. Combined constraint render
   - merge_plan='sequence': constraint enumerates per-actor verdicts in priority order,
     instructs LLM to address each in turn, naming the actor explicitly.
   - merge_plan='override': constraint binds the higher-priority verdicts, then
     enumerates EACH overridden actor's reaction-not-outcome constraint per actor
     (per §11.R). Multi-overridden-actor case (N≥3 with two or more contradicting
     lower-priority actors) renders one bullet per overridden actor, each naming
     the contradicting actor and the verdict their narration cannot reverse.

5. Primary actor selection
   primary_actor = actor of the highest-priority verdict. Used as the "speaker"
   for prompt blocks that need a single character context (HARD STOP RULES,
   ACTING CHARACTER block).

6. Result
   ArbitrationResult(verdicts, actor_order, merge_plan, primary_actor,
                     combined_constraint, overridden_actors, signals)
```

### 5.2 Combined-constraint phrasing (proposed)

**Sequence merge (most common case — two players, non-contradictory actions):**
```
=== ARBITRATION RESULT ===
Two players acted this turn. Address BOTH in narration. Order is binding:

1. JORDAN (Donovan): Stealth check at DC 15. Avrae rolled 18. SUCCESS.
   Narrate the success outcome. Do NOT narrate ambiguity.

2. TAZZ (Bruce): Combat action requested in active combat. Surface
   the command (!attack greataxe -t goblin1) for Tazz to type. Do
   NOT narrate the swing landing — Avrae's verdict to deliver.

Address each player by their actor name. Both verdicts are independent —
neither constrains the other's outcome. The narration must reflect both
actors' actions in the same response, sequenced naturally.
```

**Override merge (cross-player social override — F-50):**
```
=== ARBITRATION RESULT ===
Two players acted this turn. The verdicts CONFLICT. Player A's verdict is BINDING; Player B's narration cannot reverse it.

1. TAZZ (Bruce): grappled the flute and threw it. CHECK_ACTION:
   Athletics DC 12, rolled 16. SUCCESS. The flute is thrown.

2. JORDAN (Jordonovan): asserted "you cant do that its mine." This is
   a FREE_ACTION social claim. It does NOT reverse Tazz's resolved outcome.

Narrate Tazz's resolved outcome (the flute is thrown, the fragments
land where they land). Then narrate Jordonovan's REACTION to the
outcome — protest, lunge to catch fragments, anger — but do NOT
narrate the flute as still in his possession. Tazz's verdict stands.
```

**Multi-overridden override (3+ actors, multiple contradictions — per §11.R all-pairs):**
```
=== ARBITRATION RESULT ===
Three players acted this turn. The verdicts CONFLICT. Bruce's verdict is BINDING; Jordonovan's and Wren's narrations cannot reverse it.

1. TAZZ (Bruce): CHECK_ACTION Athletics DC 12, rolled 16. SUCCESS.
   The flute is thrown.

2. JORDAN (Jordonovan): FREE_ACTION asserted "you cant do that its mine."
   This contradicts Bruce's resolved outcome.

3. CHARLIE (Wren): FREE_ACTION asserted "I catch the flute mid-air
   and pocket it." This also contradicts Bruce's resolved outcome.

Narrate Bruce's resolved outcome (the flute is thrown, fragments land
where they land). Then narrate EACH overridden actor's REACTION to
that outcome:
  - Jordonovan: protest, lunge, anger — but do NOT narrate the flute
    as still in his possession.
  - Wren: react to the throw — but do NOT narrate having caught or
    pocketed the flute. The flute was thrown; the catch did not happen.
Bruce's verdict stands. Both Jordonovan and Wren are listed in
overridden_actors.
```

**Single-actor degenerate (one player input — backward-compatible with #1):**
```
=== ARBITRATION RESULT ===
[Renders identically to today's =-== ADJUDICATION RESULT === block.
 Single-actor case is the degenerate-list-of-1 path through arbitration.]
```

### 5.3 Verification trigger and flow

`verify_narration(...)` runs AFTER the LLM returns narration text but BEFORE the bot posts to Discord. Replaces today's "post immediately" path with a "verify, retry-once-on-fail, post" path.

```
INPUT: narration_text, arbitration_result, scene_state, combatants

1. FABRICATED_COMBATANT detection
   - Tokenize narration into Capitalized-name candidates (NER-shaped: regex
     over capitalized two-or-three-word sequences, excluding sentence starts
     known to be common nouns).
   - For each candidate, check membership in:
     a) canonical NPCs: npc_canonical_names_for_campaign(campaign_id)
     b) active combatants: [c['name'] for c in combatants]
     c) skeleton-declared NPCs: get_known_npcs(campaign_id)
     d) bound PCs: get_bound_character_names(campaign_id)
   - Non-member candidates are CANDIDATE FABRICATIONS.
   - For each candidate fabrication, search for a co-occurring combat verb
     within 20 chars: _FABRICATED_COMBATANT_VERBS = (attacks, swings, hits,
     charges, blocks, parries, springs, strikes, rakes, lashes, conjures,
     casts at, fires at, slashes, lunges, rears).
   - Hit → violation_class='fabricated_combatant'.

2. VERDICT_CONTRADICTION detection
   - For each verdict in arbitration_result.verdicts:
     a) verdict.refusal_kind='capability' + narration contains success-shape
        verbs for the refused capability ("the spell takes hold", "the rage
        rises") → violation
     b) verdict.refusal_kind='combat_inactive' + narration contains
        damage/hit verbs for the refused target → violation
     c) verdict.success=False + narration contains success-shape phrases
        (lookout doesn't notice, you slip past, the lock clicks open) → violation
     d) verdict.success=True + narration contains failure-shape phrases
        (you're spotted, the lock holds) → violation
   - Heuristic: regex against per-verdict phrase lists; first match wins.

3. STATE_MUTATION_CLAIM detection
   - _STATE_MUTATION_PHRASES regex set:
     a) "(takes|deals|does)\s+\d+\s+(damage|hp)" — HP-mechanics claim
     b) "is\s+(now\s+)?(dead|killed|slain)" — death-claim (Avrae's call)
     c) "you\s+(gain|earn)\s+\d+\s+(xp|experience)" — XP claim
     d) "permanently\s+(open|closed|sealed|destroyed)" — irreversible-state
        claim outside canonical writers
   - Hit → violation_class='state_mutation_claim'.

4. ACTOR_OMISSION detection (per §11.M, on character-name strings per §11.Q)
   - actor_order entries are CHARACTER NAMES (e.g. "Donovan", "Bruce") — NOT
     Discord usernames. The substring scan operates on character names only;
     §11.Q locks this as the source of truth for ACTOR_OMISSION.
   - For each actor (character name) in arbitration_result.actor_order:
     a) Skip if verdict.category == FREE (no binding constraint to honor).
     b) Skip if verdict.refusal_kind == "no_character_context" (cache-miss
        actor — see §11.P; no binding constraint was issued).
     c) Substring search: actor_name in narration_text (case-insensitive).
     d) If actor's name is NOT a substring of narration → CANDIDATE OMISSION.
   - Any candidate omission → violation_class='actor_omission';
     detected_phrase = f"{actor_name} (verdict: {verdict.category}) absent from narration".
   - v1 detection is name-substring only. Pronoun-aware detection (e.g., second-
     person "you spin away" addressing one of two PCs) is deferred to v1.x;
     known false-positive surface logged via verification: line for tuning.

5. Result
   - All checks pass → VerificationResult(passed=True, violation_class='', signals={...})
   - First detection wins → VerificationResult(passed=False, violation_class=X,
     detected_phrase=..., retry_constraint=tailored-per-class, signals={...})
```

### 5.4 Initial detection vocabulary (Code drafts at impl time)

Same posture as #1's Appendix A — exact regex/keyword vocabulary is implementation detail, not architecture. Decision points in §11 lock the **classes** of detection and the **mitigation shape**; the vocabulary is observable in logs (every violation line echoes `detected_phrase`) and tightens from observed friction (Doctrine §6).

Initial seeds:
- `_FABRICATED_COMBATANT_VERBS` — combat-active verbs in proximity to a Capitalized-name candidate
- `_STATE_MUTATION_PHRASES` — HP/XP/death/permanent-state claim regexes
- Verdict-contradiction phrase lists are **per-verdict-category** (CAPABILITY-refused success-shapes, CHECK-failed success-shapes, etc.) — code generates them at impl time from the locked taxonomy
- `_ACTOR_OMISSION_CHECK` — substring scan over `arbitration_result.actor_order`, filtering out FREE verdicts and `no_character_context` refusals. Pure name-substring in v1; pronoun-aware extension is filed for v1.x per §11.M sub-decision

---

## 6. Resolution / narration constraint shape

### 6.1 Arbitration block in `build_dm_context`

Renders FIRST in the system prompt, replacing today's `=== ADJUDICATION RESULT ===` slot. Variable rename only at the call site:

```
{arbitration_block}{philosophy_block}{tone}{...all existing blocks...}
```

For a single-actor degenerate case, `arbitration_block` content is byte-identical to what `=== ADJUDICATION RESULT ===` would have rendered today. The rename is structural; #1's prompt shape is preserved on solo turns.

Bottom-of-prompt hard-stop echo continues per Track 7 #1 invariant — combined_constraint renders BOTH at top (framing per §48) AND bottom (last cache before generation per §2). Multi-actor turns get a multi-line echo at the bottom; single-actor turns get the same echo as today.

### 6.2 Retry-constraint phrasing

When verification fails on the first LLM call, the retry prompt prepends:

```
=== VERIFICATION FAILED ===
The previous narration violated a binding constraint:
  Class: {fabricated_combatant | verdict_contradiction | state_mutation_claim | actor_omission}
  Detected: "{first 140 chars of offending phrase}"

You MUST regenerate. The retry MUST:
  - {class-specific constraint, e.g.: "describe combat using only the
     creatures listed in === COMBAT REDIRECT === or === ARBITRATION RESULT ===.
     Do not introduce new creatures into combat."}
  - {OR: "honor the binding verdict above. The CHECK FAILED. Narrate failure
     only. Do not narrate any success-shape outcome."}
  - {OR: "describe consequences rhetorically. Do not assert mechanical
     numbers (HP, damage, XP). Avrae owns those numbers."}
  - {OR: "address {missing_actor_name} explicitly by name. Their verdict
     ({category}) is binding and must be honored in this narration. Every
     non-FREE actor in === ARBITRATION RESULT === must be named in the response."}

This is the second pass. If you violate again, your output will be replaced
with a deterministic placeholder honoring the verdict.
```

### 6.3 Escalation placeholder shape

When second pass also fails, the bot posts a deterministic narration that honors the binding verdict from `arbitration_result`. The placeholder MUST branch per `verdict.category` — `{verdict.skill}` and `{verdict.dc}` are not populated for CAPABILITY refusals or COMBAT_REDIRECT verdicts, so a single `[actor] — {skill} check at DC {dc}` template would render `None`/empty for those verdict shapes (per §11.I margin-note lift). Session 3 implements per-category branching, NOT a single template:

```
CHECK_ACTION:
  {actor} — {verdict.skill} check at DC {verdict.dc}. Result: {success|failure}.
  {terse one-line outcome statement honoring the resolved roll}

CAPABILITY_ACTION (refused):
  {actor} attempts {verdict.capability}. The capability does not apply.
  {non-occurrence outcome — e.g., "The spell does not come. The words
   don't shape. Nothing happens."}

COMBAT_ACTION (refused, combat inactive):
  {actor} attempts {verdict.action_summary}. Combat is not active.
  Use !init begin to start combat, then surface the action through Avrae.

WORLD_BOUNDARY_ACTION:
  {actor}'s attempt does not resolve.
  {non-occurrence outcome consistent with the world-boundary refusal,
   per #1's invariant: the attempted action does not happen, and the
   world-state described does not change.}

FREE_ACTION:
  Fallback should not fire — FREE has no binding constraint, so no
  verification class should escalate against it. If escalation reaches
  here, log [VERIFICATION_ANOMALY] (the gate fired against an unbound
  verdict — bug in detection) and post a single-line acknowledgment:
  "{actor}'s action passes without resolution. (See logs.)"
```

Multi-actor escalations render one block per non-FREE actor (one per binding verdict the LLM refused to honor across both passes), in priority order. Style: terse, mechanical, honest. Loses prose quality but preserves verdict integrity. Logged at `verification_escalated:` with full retry traceback so the next session can tighten regexes.

### 6.4 Update on emit

No DB writes from arbitration or verification. Logging only:

```
arbitration: campaign={N} actors={count} verdicts={cat:cat:cat}
             merge_plan={sequence|override} primary_actor={name}
             overridden_actors={A,B|-} priority_order={A,B,C}

verification: campaign={N} passed={1|0} violation_class={...}
              detected={first_140!r} retry_fired={1|0} retry_passed={1|0}
              escalated={1|0} narration_chars={N} canonical_combatants_count={N}
```

`overridden_actors` is rendered as a comma-separated list of character names (per §11.R) — `-` when `merge_plan='sequence'` (empty list); `A` for one overridden actor; `A,B` for two; etc. Replaces the prior single-string `overridden_actor` log field.

---

## 7. Failure modes + mitigations

1. **Over-flagging — verification refuses legitimate creative narration.** LLM introduces a non-combat NPC ("a barmaid wipes the counter") that's not in `dnd_npcs`. Detection regex flags as fabrication.
   *Mitigation:* The fabricated-combatant gate fires ONLY on combat-verb proximity. Non-combat introductions ("a barmaid wipes the counter") have no combat verb adjacency and pass. The narrower the verb list, the lower the false-positive rate. Logs every fabricated-combatant flag with `detected_phrase` so over-flagging surfaces empirically and the verb list tightens.

2. **Under-flagging — fabricated NPC enters combat through phrasing the regex misses.** "Suddenly a hulking shadow pivots toward you" — no proper-noun candidate, no canonical-lookup hit.
   *Mitigation:* v1 detection is tuned for the F-49 shape (named fabricated NPCs entering combat — Silent Beast, Keeper of the Vein). Anonymous-shape combatants ("a shadow," "the figure") are filed as v2 — pronoun-and-descriptor combat detection requires entity tracking we don't have yet. Logged via `verification: passed=1 narration_chars=...` with nothing to compare against; observed friction informs whether v2 ships.

3. **Verification cost / latency.** Two LLM calls instead of one when verification fails. 2x token budget.
   *Mitigation:* Verification's classifier is pure Python regex — adds tens of ms, no LLM call. The retry LLM call is the cost. Bounded at 1 retry. If logs show retry rate >10% sustained, escalation taxonomy shifts toward stronger first-pass constraints (which is the cheaper fix).

4. **Arbitration over-merge — multi-actor turn forced into single narration block when actors are doing unrelated things in different scenes.** Two players in different rooms, both post.
   *Mitigation:* Same-scene assumption is implicit in v1 — a campaign has a single `scene_state.mode` and a single `current_location_id`. Multi-scene play is filed for v2 (mod-per-actor scene tracking). v1 narrates both actions in one response; if the actions are spatially separated, the LLM is responsible for marking the narrative transitions.

5. **Cross-player override ambiguity — does Player B's "I help Player A" combine or override?**
   *Mitigation:* Combine. "Help" is a non-contradictory verdict; merge_plan='sequence', narration addresses both. Override fires only when verdict B's content directly contradicts verdict A's bound resolution. The §11.C decision point surfaces this distinction explicitly.

6. **Arbitration latency on slow per-actor adjudication.** Each `adjudicate()` call is ~ms-scale, but 4 actors × ~5ms = 20ms. Acceptable; logged as `arbitration_chars` if it ever lands above 50ms.
   *Mitigation:* Per-actor adjudication is pure Python with no I/O after the inputs are loaded. Adjudicate is bounded; arbitration is bounded. No network calls. Acceptable.

7. **Verification on retry produces a different violation class.** First pass: fabricated combatant. LLM retry produces: verdict contradiction.
   *Mitigation:* Retry budget is 1 regardless of which class the second pass violates. Second violation → escalation regardless. Logged as `verification: violation_class=... retry_fired=1 retry_passed=0 escalated=1` — the per-pass violation_class is the LATEST violation, not historical.

8. **Active-turn drift between arbitration and LLM call.** Arbitration reads active_turn at function entry; mode flips during LLM call.
   *Mitigation:* Same as #1 §7.5. Mid-turn flips by-design ignored. Verification reads `arbitration_result` for verdict contradictions, NOT a re-read of state. Stable input across the LLM call.

9. **`ArbitrationResult` malformed / arbitrate raises.** Bug in arbitrate code, partial state.
   *Mitigation:* Caller wraps in try/except (Doctrine §59 soft-fail). Falls back to first-actor-only adjudication (current Track 7 #1 path). Log `[ARBITRATION_FALLBACK]` with exception. Verification disabled on fallback turn (no arbitration_result to verify against).

10. **`narration_verifier` raises.** Bug in verify code.
    *Mitigation:* Caller wraps in try/except. On exception, treat as `passed=True` (fail-OPEN) and post original narration. Log `[VERIFICATION_FALLBACK]`. Acceptable: a missed verification is the prior state of the world; never block narration entirely.

11. **LLM retry produces empty narration.** Retry call returns empty string or "I cannot help with that."
    *Mitigation:* Empty/refusal retry → escalation path. Deterministic placeholder is the shipped narration. Never silently post empty.

12. **Discord client cache / format-unknown.** Verification receives narration with embeds, image attachments, malformed text.
    *Mitigation:* Format-unknowns fail-open §49. Verification operates on plaintext narration only. Embed/attachment paths bypass verification and follow today's posting flow (no regression).

13. **Per-actor cache miss in `arbitrate()` (§11.P).** `orch.get_cached_context(actor)` returns `None` for an actor — typically a new player who hasn't posted `!sheet` yet in-session. Track 7 #1.1's `cache_autopopulate` makes this rare for bound PCs (cache populates on first `!sheet` post in-session) but the pre-first-sheet window remains.
    *Mitigation:* Cache-missed actor's per-actor adjudicate() defers safely per the partial-projections doctrine: returns `(allowed=True, refusal_kind="no_character_context")` for that actor. Arbitration proceeds with the remaining actors; the cache-missed actor's input is rendered to the LLM without a binding constraint (LLM has narrative latitude for that actor's intent). ACTOR_OMISSION verification skips this actor (no binding constraint to honor — see §5.3 step 4 b). Same fallback shape as #1's pre-#1.1 behavior; arbitrate() does not invent character context.

14. **ACTOR_OMISSION false positive on legitimate pronoun reference.** Two-PC turn where the LLM legitimately addresses one actor by name and another by second-person pronoun ("you spin away"). v1 substring detection fires.
    *Mitigation:* v1 ships substring-only per §11.M sub-decision. False-positive rate is observable in `verification:` log line (`violation_class=actor_omission` with `retry_passed=1` is the empirical signature of "retry corrected by adding the missing name; original was likely fine via pronoun"). If observed false-positive rate is non-trivial, pronoun-aware detection ships in v1.x. Cost on FP is one extra LLM call (the retry) — bounded.

---

## 8. Test plan (proposed)

### 8.1 Engine layer (`test_arbitration.py`)

**Per-actor adjudication composition:**
- 1 actor → ArbitrationResult.verdicts has length 1, primary_actor matches actor
- 2 actors with non-contradictory verdicts → length 2, merge_plan='sequence'
- 3 actors mixed categories → priority sort works (WORLD_BOUNDARY first, FREE last)
- 2 actors same category → arrival timestamp tiebreaks

**Actor-name source of truth (§11.Q):**
- Multi-actor turn fixture (2-actor: Donovan + Bruce) → assert `actor_order ==
  ["Donovan", "Bruce"]` (CHARACTER NAMES, not Discord usernames "JORDAN"/"TAZZ").
  Locks the dataclass field semantics so ACTOR_OMISSION substring detection
  operates on the right strings.

**Cross-player override detection (all-pairs, per §11.R):**
- Actor A: CHECK Persuasion DC 15, rolled 8 (failed). Actor B: FREE narration "he agrees with us." → merge_plan='override', overridden_actors=['B'], combined_constraint binds A's failure
- Actor A: CAPABILITY refused (Fireball, rogue PC). Actor B: FREE "the room ignites." → override, overridden_actors=['B']
- Actor A: CHECK Athletics DC 12, rolled 16 (success). Actor B: FREE "I help him." → no conflict, merge_plan='sequence', overridden_actors=[]

**3-actor override (all-pairs, per §11.R):**
- A: CHECK Athletics DC 12 rolled 16 (success). B: FREE "you fail and drop it." C: FREE "I catch what you dropped and pocket it." → A-vs-B contradicts AND A-vs-C contradicts → merge_plan='override', overridden_actors=['B','C'] (dual-override)
- A: CHECK Stealth DC 15 rolled 18 (success). B: independent FREE "I sip my drink." C: FREE "the lookout spots A clearly." → A-vs-B non-contradictory; A-vs-C contradicts → merge_plan='override', overridden_actors=['C'] (B not overridden — sequence-merged alongside the override block)
- A: CAPABILITY refused. B: FREE that contradicts A. C: FREE that contradicts A independently → all-pairs scan detects A-vs-B and A-vs-C → overridden_actors=['B','C']
- 3 actors, no contradictions anywhere → merge_plan='sequence', overridden_actors=[]
- All-pairs (NOT adjacent-only) is the locked semantics — the prior wording in §1.5/§5.1 step 3 said "adjacent pairs in priority order" which would have missed A-vs-C when B sat between them in priority order.

**Single-actor fall-through:**
- 1-actor input through arbitrate → byte-identical combined_constraint to what adjudicate→render_adjudication_block produces today. Backward-compat regression test.

**Telemetry:**
- arbitration: log line shape per turn
- actors=N matches len(actions)
- verdicts list matches priority order

### 8.2 Verification layer (`test_narration_verifier.py`)

**Fabricated-combatant detection:**
- Narration introduces "Silent Beast" + verb "lunges" + non-canonical → violation
- Narration introduces "Silent Beast" + non-combat verb "watches" → no violation
- Narration mentions "Bruce Banner" (canonical PC) + combat verb → no violation
- Narration mentions "Goblin 1" (canonical combatant) + combat verb → no violation
- Narration mentions canonical NPC by name + combat verb → no violation

**Verdict-contradiction detection:**
- Adjudication CHECK failed → narration "you slip past unnoticed" → violation
- Adjudication CAPABILITY refused → narration "the spell takes hold" → violation
- Adjudication COMBAT_INACTIVE → narration "the bartender takes 8 damage" → violation
- Adjudication CHECK success → narration "the lock holds" → violation
- Adjudication FREE → any narration → no contradiction (no constraint to violate)

**State-mutation detection:**
- Narration "the goblin takes 12 damage" → violation
- Narration "the goblin staggers, blood on its tunic" → no violation (rhetorical)
- Narration "you gain 200 XP" → violation
- Narration "the door is permanently sealed" → violation

**Actor-omission detection (§11.M):**
- Two-actor arbitration (Donovan CHECK success, Bruce COMBAT_REDIRECT) → narration mentions both names → no violation
- Two-actor arbitration (Donovan CHECK success, Bruce COMBAT_REDIRECT) → narration mentions only Donovan → violation, missing_actor='Bruce'
- Two-actor arbitration where one actor's verdict is FREE → narration omits FREE actor → no violation (FREE actors are not binding)
- Two-actor arbitration where one actor's verdict is `no_character_context` (cache miss per §11.P) → narration omits that actor → no violation
- Single-actor arbitration → narration mentions actor → no violation
- Single-actor arbitration → narration omits actor (degenerate case, rare) → violation
- Known-FP scenario (filed for v1.x): two PCs, narration uses second-person "you" for the missing one → v1 fires; retry typically corrects by adding the name; logged for empirical FP-rate measurement

**Retry-constraint render:**
- Each violation class produces a class-specific retry constraint
- Constraints name the violation explicitly and the rule the retry must honor

### 8.3 End-to-end composition (`test_dm_respond_arbitration.py`)

- `dm_respond` with 1-actor input → produces same prompt shape as Track 7 #1 baseline
- `dm_respond` with 2-actor input, non-contradictory → ArbitrationResult sequence, prompt has multi-actor block, narration verified once and posted
- `dm_respond` with 2-actor input, contradictory → ArbitrationResult override, narration verified, posted
- `dm_respond` with 1-actor input, narration fabricates NPC + combat verb → verification fails, retry fires, retry succeeds, posted
- `dm_respond` with 1-actor input, both passes fail verification → escalation placeholder posted
- Feature flag `ARBITRATION_ENABLED=False` → behaves like Track 7 #1 single-actor adjudication
- Feature flag `VERIFICATION_ENABLED=False` → no post-pass; original narration posts directly

### 8.4 Live verification (post-ship)

Replay S25 #3 multiplayer scenarios:
- F-48: Jordan + Tazz concurrent input → both verdicts visible in narration, neither dropped
- F-49: LLM attempts to introduce Silent Beast in combat → verification fails, retry produces canon-bounded narration OR escalation placeholder
- F-50: Tazz throws flute, Jordan asserts it's his → arbitration override binds Tazz's resolved outcome
- F-46: "Says who" defeating capability refusal → already closed by #1; verification gate provides defense-in-depth (any LLM regression that re-introduces "Keeper of the Vein appears" gets caught)
- **Two-actor non-contradictory turn against the real LLM (per §11.B margin-note lift).** Construct a clean two-actor turn where the verdicts compose under `merge_plan='sequence'` (e.g., Donovan stealth-CHECK success + Bruce COMBAT_REDIRECT). Verify the produced narration addresses BOTH actors by character name in a single response. Failure mode = the LLM dropped one actor; ACTOR_OMISSION should fire and trigger regen. If ACTOR_OMISSION does NOT fire on a real-LLM dropped-actor case, the substring detection is wrong OR the `actor_order` field is storing the wrong string shape (per §11.Q lock — it must hold character names, not Discord usernames). This is the live-LLM check that the §11.B sequence-merge phrasing actually keeps both actors named in practice — replaces the previous "trust + telemetry-observability" stance with structural proof under real model output.

Each scenario gets a line in `tests-to-run-post-session.md`.

---

## 9. Migration impact

**Schema changes:** None.

**Code additions:**
- `adjudicator.arbitrate(...)` (~150–250 lines projected) + `ArbitrationResult` dataclass
- New module `/home/jordaneal/scripts/narration_verifier.py` (~400–600 lines projected)
- `VerificationResult` dataclass
- `_FABRICATED_COMBATANT_VERBS`, `_STATE_MUTATION_PHRASES` curated lists
- New `arbitration_block=""` kwarg in `build_dm_context` (replaces `adjudication_block`)
- New `=== ARBITRATION RESULT ===` block render (rename of `=== ADJUDICATION RESULT ===`)
- New `=== VERIFICATION FAILED ===` block render for retry path
- Two new feature flags: `ARBITRATION_ENABLED`, `VERIFICATION_ENABLED`
- Two new log lines: `arbitration:`, `verification:`

**Code modifications (low-risk):**
- `dm_respond`: arbitration call replaces single adjudicate call site (line `dnd_engine.py:4667`); verification call wraps the LLM-response → post path
- `_dm_respond_and_post`: passes structured `actions` list to `dm_respond` instead of pre-concatenated `combined_action` string
- `dm_respond` signature: takes `actions: list` in addition to `combined_action` (back-compat: when only `combined_action` is provided, arbitrate degrades to single-actor)

**Cross-version safety:** No schema = no migration risk. Feature flags allow independent rollback. When `ARBITRATION_ENABLED=False`, behavior collapses to Track 7 #1 single-actor adjudication. When `VERIFICATION_ENABLED=False`, narration posts directly with no post-pass. Both flags default to True for new installs but can be disabled per-environment for safe rollout.

**Rollback:** Both feature flags. ArbitrationResult fallback to single-verdict on error (Doctrine §59). Verification fallback to fail-open on error.

---

## 10. Out of scope (separate specs / future)

- **LLM-output adjudication for narrative texture** (motif drift F-52, lore density, tone, NPC unhelpfulness). v1 detects three structural classes; texture is clothes-queue, not bones. ChatGPT-15 texture items remain filed for post-Track-7 system-prompt tuning.
- **NPC stat hydration at init-add (Track 6 #4).** Adjacent ship, separately filed. Verification's fabricated-combatant gate REFUSES fabricated NPCs in combat; the FIX (stats for ad-hoc-added NPCs) lives in #4. v1 of #2 surfaces the gap; #4 closes the gap on the legitimate case.
- **Multi-actor adjudication for solo play.** Degenerate single-actor case is the fall-through; explicit solo-mode mechanism is unnecessary.
- **Multi-intent decomposition within a single player's message.** "I draw my dagger and step toward the door" — Track 7 #1 §11.D filed this as #2 territory. **LOCKED OUT for v1 of #2** (§11.K). Single-player multi-intent stays at #1's "highest-precedence wins" rule. Filed as candidate for v1.x or its own ship; revisit after #2 ships and observed-friction logs accumulate.
- **Anonymous-shape combatant detection.** "A figure lunges from the shadows" — no proper-noun candidate. v1 detects named fabrications only. Pronoun-and-descriptor combat verification requires entity tracking.
- **Cross-turn verification memory.** "This NPC was fabricated last turn — second appearance is auto-canon" or "this fabrication keeps recurring — maybe the LLM is signaling something the world should accept." Filed for v2 if observed friction shows it.
- **Cross-turn arbitration memory.** `last_arbitration_result` persistence in `dnd_scene_state` so next-turn arbitration reads prior verdicts. Closes the cross-turn override case (Player B's contradicting action arrives the FOLLOWING turn). **LOCKED OUT for v1** (§11.L sub-item 1). Filed as v2 candidate.
- **Multi-scene arbitration.** Two players in different rooms posting concurrent actions. v1 assumes single-scene-per-campaign. Filed.
- **Verification of OOC `#dm-aside` advisory output.** Advisory mode is read-only Q&A; no narration constraint to verify against. Out of scope.
- **Verification on Avrae embed/edit content.** Avrae messages are not narration; they're mechanical updates. Verification is narration-only.
- **Self-correcting verification (RAG over canonical NPCs to suggest replacements).** "You meant Bruce, not Silent Beast." Out of scope; v1 refuses, v2 might suggest.

---

## 11. Decision points needing review

These are the surfaces where Jordan's call shapes the spec. Letter-coded (continuing #1's scheme — A through L from #1 are taken; #2 starts fresh at A within its own document namespace).

### §11.A — Coalesce window duration (LOCKED)

**Locked:** Keep ActionBatcher's existing `ACTION_BATCH_WINDOW=15s` in non-combat and `1s` in combat. Window-fill rate is observable via the `arbitration:` log line; tighten only if logs show >90% single-actor turns.

ActionBatcher today uses `ACTION_BATCH_WINDOW=15s` in non-combat, `1s` in combat (effectively no batching). Multi-action arbitration is meaningless without a window long enough to capture concurrent input but short enough that players don't feel ignored.

- **Recommend:** keep 15s in non-combat. The batcher already operates at this window; #2 just changes how its output is consumed. 1s in combat is preserved (multi-actor is moot under 2A.3 anyway).
- **Trade-off:** 15s is slow when only one player is active (single-player solo turns wait the full window for nothing). The batcher's existing "cancel timer on each new add, restart window" pattern means a single message + no follow-up still waits ~15s. Could shorten to 5–8s, but that risks cutting off the "second player typing" case the spec is trying to capture. v1 keeps 15s; instrument `arbitration_chars`-shape window-fill rate and tighten if logs show >90% single-actor turns.
- **Confidence:** medium — the right number is empirical, not first-principles. 15s is the existing-system inertia answer.

### §11.B — Merge semantics (LOCKED)

**Locked:** Option 1 (sequence — natural-language flow, no bracketed actor headers). Trust + ACTOR_OMISSION structural gate per §11.M. If observed regen rate from ACTOR_OMISSION trends high, v1.x escalates to Option 3 (explicit bracketed actor headers). The two-actor non-contradictory live-verification test (§8.4) confirms the trust holds against the real LLM.

When two actors' verdicts compose, what does "address both in narration" mean?

- **Option 1 (sequence — recommended):** narration addresses each actor in turn, in priority order, in the same response. LLM is responsible for natural-language flow ("Donovan's footsteps fade into the rafters as Bruce's axe arcs down...").
- **Option 2 (interleave):** narration intermixes actor responses sentence-by-sentence. More cinematic but harder to constrain — LLM tends to lose track of which actor is the subject.
- **Option 3 (sequence with explicit narrative breaks):** "[Donovan] ... [Bruce] ..." style with bracketed actor headers. Clean, mechanical, but reads like a stage direction.
- **Recommend:** Option 1 (sequence, natural-language flow) for v1. Lowest LLM cognitive load, matches existing prose style. If verbal flow degrades empirically (LLM forgets the second actor mid-paragraph), v2 escalates to Option 3.
- **Trade-off:** Option 1 trusts the LLM with sequencing; verification gate catches verdict contradictions AND actor omissions (per §11.M, ACTOR_OMISSION promotes the "did the LLM forget to mention Player B" check from heuristic-telemetry to structural-regen). v1 ships with the trust + ACTOR_OMISSION gate; if observed regen rate from ACTOR_OMISSION is high, v1.x escalates to Option 3 (explicit bracketed actor headers).
- **Confidence:** medium — Option 1 is the "do the simplest thing" answer; Option 3 is the bullet-proof answer. Pick based on tolerance for early-ship friction.

### §11.C — Cross-player override priority rule (LOCKED)

**Locked:** `WORLD_BOUNDARY > COMBAT > CAPABILITY > CHECK > FREE`, ties broken by arrival timestamp (earlier wins). Higher-priority verdict in any contradicting pair is binding; lower-priority verdict renders as REACTION not OUTCOME. Conflict scan is all-pairs per §11.R. This is the structural close of F-50.

When Player A's verdict is bound (CHECK resolved, CAPABILITY refused, COMBAT-active) and Player B's narration directly contradicts the bound resolution, what's the rule?

- **Recommend:** earlier-arrival binding verdict wins; later social-assertion verdict is rendered as REACTION, not OUTCOME. Priority is `WORLD_BOUNDARY > COMBAT > CAPABILITY > CHECK > FREE` for sorting; when categories tie, arrival timestamp breaks. The override constraint instructs the LLM to narrate Player B's reaction (protest, lunge, anger) but NOT to narrate the bound outcome as reversed.
- **Alternative:** later input always wins ("most recent intent is most relevant"). Rejected — exactly the F-50 failure mode.
- **Alternative:** higher-DC verdict wins regardless of order. Rejected — encourages players to game the priority by phrasing actions as higher-stakes than they meant.
- **Trade-off:** the recommended rule means a player who types fast can lock in an outcome that another player can't reverse. This is the design intent — mechanical resolution > social assertion. But it shifts pressure to the LLM to render reactions believably; if the LLM narrates "Jordonovan shrugs" when the player typed an angry protest, that's an LLM-quality issue, not an arbitration issue.
- **Confidence:** high — this is the central design decision of the multi-action mechanism. The recommendation closes F-50 structurally. Alternatives reopen it.

### §11.D — Arbitration above or below 2A.3 off-turn drop? (LOCKED)

**Locked:** Arbitration runs BELOW 2A.3 in the call stack and does NOT relax 2A.3. Combat-mode multi-actor input stays filtered at transport. Reactions/held actions are out of scope for v1; filed for v2 alongside Avrae's reaction tracking path.

Phase 2A.3 drops off-turn input in combat at transport (`on_message`) before the batcher runs. Arbitration runs in `dm_respond`. Strictly arbitration is BELOW 2A.3 in the call stack; the question is whether arbitration should be allowed to RELAX 2A.3 (e.g., if a non-active-turn player types a CAPABILITY action that doesn't violate combat order — say, a reaction or a held action).

- **Recommend:** arbitration is BELOW 2A.3; 2A.3 stays as the architectural prior. v1 does NOT relax 2A.3. Reactions, held actions, and similar combat off-turn legitimate inputs are out of scope; players in combat use the active-turn slot Avrae already gates.
- **Trade-off:** legitimate D&D patterns (rogue's Uncanny Dodge reaction; readied actions; held spells) are not first-class in v1. The off-turn drop will silently swallow them. Filed as v2 (combat reaction handling), tied to whatever path Avrae's reaction tracking takes.
- **Confidence:** high — relaxing 2A.3 is a separate spec entirely. v1 keeps the existing architectural prior intact.

### §11.E — Arbitration telemetry shape (LOCKED)

**Locked:** Per-turn `arbitration:` log line lands the recommended fields, with `overridden_actor={name|-}` replaced by `overridden_actors={A,B|-}` (comma-list per §11.R). `signals` field of `ArbitrationResult` uses **explicit named keys** drafted at implementation time (matching #1's `AdjudicationResult.signals` posture); not free-form dict-flatten. New keys require spec amendment, not inline addition (per margin-note lift into §4 dataclass docstring).

Per-turn `arbitration:` log line. What fields land?

- **Recommend:**
  ```
  arbitration: campaign={N} actors={count} verdicts={cat:cat:cat}
               merge_plan={sequence|override} primary_actor={name!r}
               overridden_actors={A,B|-} priority_order={A,B,C}
               input_total_chars={N} input_per_actor={a:N,b:M,c:K}
  ```
- **Trade-off:** per-actor input chars adds verbosity but is the empirical baseline for "did one player drown out the other in input volume" — useful for tuning the merge plan over time. Drop if log lines blow out width.
- **Confidence:** locked. Field shape mechanical; explicit-keys posture for `signals` is locked structural choice (no free-form flatten).

### §11.F — Verification violation classes (LOCKED)

**Locked:** Four classes — `FABRICATED_COMBATANT`, `VERDICT_CONTRADICTION`, `STATE_MUTATION_CLAIM`, `ACTOR_OMISSION`. The alternatives surfaced (`PLAYER_NARRATED_NPC_ACTION`, `UNSANCTIONED_LOCATION_TRANSITION`, `UNSANCTIONED_TIME_PASSAGE`) are filed in §12 for v2 once empirical violation rates from the locked four are observable.

The taxonomy: which violations does v1 detect?

- **Recommend (locked at four — see §11.M for the fourth):**
  - `FABRICATED_COMBATANT` — closes F-49
  - `VERDICT_CONTRADICTION` — defends Track 7 #1's gates against narration drift
  - `STATE_MUTATION_CLAIM` — closes the "LLM asserts mechanical numbers" leak
  - `ACTOR_OMISSION` — closes the output side of F-48 (LLM silently dropping a non-FREE actor's binding constraint). Pre-locked by Jordan during amendment pass; see §11.M.
- **Alternatives surfaced for review:**
  - **`PLAYER_NARRATED_NPC_ACTION`** — the LLM narrates a player NARRATING an NPC's action ("Donovan says: the goblin charges at me"). 4th-wall break. Track 7 #1 §11.D.6 filed this; could ship in #2.
  - **`UNSANCTIONED_LOCATION_TRANSITION`** — narration describes the party as having moved to a location that wasn't `current_location_id` and wasn't a valid transition.
  - **`UNSANCTIONED_TIME_PASSAGE`** — narration asserts hours/days passed without a rest mechanic firing.
- **Recommend:** v1 ships the four locked classes. Remaining alternatives are filed in §12 for v2 once empirical violation rates from the first four are observable. Adding more classes upfront risks over-fitting to anticipated rather than observed leakage.
- **Trade-off:** missing a class means a real failure ships unverified. But the four locked are the ones the multiplayer test surfaced (or close adjacents — ACTOR_OMISSION is structural sibling to VERDICT_CONTRADICTION); over-fitting to anticipated failures is the §11.E "default-to-roll" mistake from #1.
- **Confidence:** high on the four locked; medium on whether to add a fifth pre-ship (probably not — file alternatives for v2).

### §11.G — On-detection mitigation: regenerate, redact, hold-message, or constrained-narration fallback? (LOCKED)

**Locked:** Option 1 (regenerate) + Option 4 (constrained-narration fallback) as escalation. ONE retry; on second failure, escalate to deterministic placeholder. Pay 2x cost on the bad case; never silently ship a violation.


- **Option 1 (regenerate — recommended):** LLM gets ONE retry with explicit failure context. Highest-fidelity narration if retry succeeds.
- **Option 2 (redact):** strip the offending phrase from narration and post the redacted version. Cheap, no retry. Risks producing nonsensical narration ("the [REDACTED] charges at you").
- **Option 3 (hold-message):** silently drop the LLM output, post nothing this turn, surface the verdict to the player as a system message. Worst player experience — feels like the bot is broken.
- **Option 4 (constrained-narration fallback):** deterministic placeholder narration honoring the verdict. Zero-fidelity but always honest.
- **Recommend:** Option 1 + Option 4 as escalation. ONE retry; on second failure, escalate to deterministic placeholder. This is the "pay 2x cost on the bad case, never silently ship a violation" balance.
- **Trade-off:** 2x LLM cost on violation turns. Mitigated by violation rate being expected to be low (single-digit percent). If logs show >20% violation rate sustained, escalate to stronger first-pass constraints (cheaper than retries).
- **Confidence:** high — Options 2 and 3 are bad enough to rule out; the question is whether to ship without retry (just escalate immediately) or with one retry. v1 ships with one retry; v1.x might tighten to zero retries if cost vs quality ratio favors immediate escalation.

### §11.H — Regen budget and retry behavior (LOCKED)

**Locked:** 1 retry. Total LLM budget is 2 calls per turn (initial + retry). Retry prompt prepends `=== VERIFICATION FAILED ===` block naming the violation class and explicit prohibitions. Retry temperature is unchanged. Tune from data (retry success rate visible in `verification:` log).

How many retries? What does the retry prompt look like?

- **Recommend:** 1 retry. Total LLM budget is 2 calls per turn (initial + retry). Retry prompt prepends a `=== VERIFICATION FAILED ===` block naming the violation class and explicit prohibitions. Retry temperature is unchanged (don't lower diversity — the LLM might just produce a different variant of the same violation).
- **Alternative:** 2 retries (3 calls total). Higher success rate but 3x cost on violation turns. Doesn't seem worth it given §11.G's escalation safety net.
- **Trade-off:** 1 retry vs 2 is a token-budget call. If empirical retry success rate is >70%, 1 is enough. If <40%, the second retry is buying meaningful additional success. v1 ships with 1; instruments retry success rate; tunes from data.
- **Confidence:** medium — the right number is empirical. 1 is the "ship it and observe" default.

### §11.I — Escalation when all retries violate (LOCKED)

**Locked:** Deterministic placeholder narration that surfaces the binding verdict imperatively, **per-category branched** (CHECK_ACTION / CAPABILITY_ACTION / COMBAT_ACTION / WORLD_BOUNDARY_ACTION / FREE_ACTION-anomaly), per the §6.3 amendment. The previous single-template `[actor] — {skill} check at DC {dc}` shape was incomplete (rendered None for CAPABILITY/COMBAT_REDIRECT verdicts); Session 3 implements per-category branches.

Both passes failed verification. What gets posted?

- **Recommend:** deterministic placeholder narration that surfaces the binding verdict imperatively. Per-actor template (§6.3) — terse, mechanical, honest. Loses prose quality but preserves verdict integrity.
- **Alternative:** post the violating LLM output anyway with a system-message footnote ("Note: the narration above may have invented a creature; please confirm with DM"). Rejected — defeats the purpose of the gate.
- **Alternative:** post nothing; let the player re-prompt. Rejected — silent failure is the worst outcome.
- **Trade-off:** the placeholder narration will feel mechanical and bot-shaped after rich LLM prose, breaking immersion. But this is the LAST RESORT — escalation rate is expected to be low (1-3% of turns based on retry success rate intuition). Worth the rare immersion break to never silently ship a violation.
- **Confidence:** high — the principle is locked; the exact placeholder phrasing is implementation detail.

### §11.J — Verification reuses adjudicate() or forks (justify against §63)? (LOCKED)

**Locked:** FORK. New module `narration_verifier.py`, parallel sibling to `adjudicator.py` per Doctrine §63. Different actor (LLM vs player), different invariants, different vocabulary surfaces, different mitigation paths. Reuse only of `AdjudicationResult` dataclass, canonical-state read helpers, and the (body, signals) pure-function shape.


- **Recommend:** FORK. New module `narration_verifier.py`, parallel sibling to `adjudicator.py`.
- **Justification per Doctrine §63 — fork at the highest layer where invariants diverge:**
  - **Different actor.** Adjudication's actor is a player; verification's actor is the LLM. Capability gates against `CharacterContext` are meaningless for LLM output (the LLM has no character sheet).
  - **Different invariants.** Adjudication asks "is this attempt allowed?" — gating intent against character/scene state. Verification asks "did the narration honor the verdict and stay in canon?" — gating output against canonical NPCs and the bound verdict from the same turn.
  - **Different vocabulary surfaces.** Adjudication's classifier is verb+noun proximity for action intent. Verification's classifier is named-entity extraction for fabrication detection, per-verdict-category contradiction phrase lists, state-mutation regex set, and (per §11.M) substring-actor-check over `arbitration_result.actor_order`. Different regex shapes, different inputs.
  - **Different mitigation paths.** Adjudication's mitigation is binding constraint into the prompt. Verification's mitigation is regen + escalation placeholder.
- **Trade-off:** forking means two modules to maintain instead of one. But forcing both into adjudicator.py would require parameterizing the function for "actor type" and dispatching — that's the abstraction premature §63 rejects. Sibling is cleaner.
- **Reuse ONLY of:** `AdjudicationResult` dataclass (verification reads verdicts from arbitration_result), canonical-state read helpers (`dnd_npcs`, `dnd_combat_state`), the (body, signals) pure-function shape.
- **Confidence:** high — §63 is explicit about this case. The instinct to parameterize adjudicate() into a more general gate is exactly the case §63 was learned from.

### §11.K — Single-player multi-intent decomposition (LOCKED OUT for v1)

#1 §11.D filed single-player composite intents ("I draw my dagger and step toward the door") as Track 7 #2 territory. The current spec scopes #2 to **multi-PLAYER multi-action**.

- **Locked decision:** OUT of scope for v1 of #2. Composite intents within a single player's message stay at #1's "highest-precedence wins" rule. Decomposition is NOT shipped in v1 of #2. Filed as candidate for v1.x or its own ship; revisit after #2 ships and observed-friction logs accumulate.
- **Trade-off:** single-player composite intents stay weakly handled (the second clause of "I draw my dagger and step toward the door" can be silently dropped). Acceptable until observed friction shows otherwise.
- **Why locked OUT pre-review:** multiplayer arbitration is the load-bearing mechanism for #2; single-player decomposition is texture. Per the prompt's "Don't add features beyond what the task requires" — multiplayer is the explicit target; single-player is a separate ship. Surfaced and locked here so Session 2 review doesn't re-walk it and Session 3 implementation doesn't re-decide live.
- **Confidence:** locked. Jordan signed off pre-review.

### §11.L — Locked-spec ambiguities surfaced from #1 reading

Two surfaced during #1 review:

(1) **§12 of #1 mentions A's narration_constraint persisting in `last_dm_response` so adjudication on B's turn can read it.** Does #2 need to extend this to a structured per-turn `last_arbitration_result` that next-turn arbitration reads? This would close the cross-TURN override case (Player B types a contradicting action on the FOLLOWING turn, after A's verdict was already rendered).

- **Locked decision:** **OUT of v1.** `last_arbitration_result` persistence in `dnd_scene_state` is NOT shipped in v1 of #2. Cross-turn override case (Player B's contradicting action arrives the FOLLOWING turn) remains a known v2 candidate.
- **Why locked OUT pre-review:** cross-turn override is a different failure shape than same-turn override; v1 closes same-turn (F-50). Cross-turn closes through the same arbitration mechanism if #2 ships a `prior_turn_verdict_check` extension; filed explicitly OUT for v2, not "filed for v2 if observed friction shows it" — Jordan locked this OUT pre-review so Session 2 doesn't re-walk and Session 3 doesn't re-decide live.
- **Confidence:** locked.

(2) **§7.6 of #1 noted "If the player NARRATES an NPC action, the LLM has always had latitude to refuse that as 4th-wall — adjudication doesn't change this."** This is a player-input issue, not LLM-output. But it's adjacent to #2's verification surface — should `PLAYER_NARRATED_NPC_ACTION` be detected at INPUT (extending adjudicate()) rather than at OUTPUT (verification)?

- **Recommend:** input-side. If #2 expands its scope to add a 4th-wall input gate, that's #1.2 territory (extension to adjudicate's category set) not #2 (which is multi-actor + output verification). File as a separate Track 7 sub-ship. Don't add it to #2's scope mid-spec.
- **Confidence:** high — out of scope is the right answer; surfacing it for visibility.

### §11.M — ACTOR_OMISSION as fourth verification class (LOCKED)

A fourth violation class joins the verification taxonomy. v1 detects FOUR classes, not three: `FABRICATED_COMBATANT`, `VERDICT_CONTRADICTION`, `STATE_MUTATION_CLAIM`, and `ACTOR_OMISSION`.

**Detection.** For each actor in `arbitration_result.actor_order`, check whether the actor's name appears as a substring in the narration text (case-insensitive). If any actor's name is missing AND that actor's verdict was non-FREE (had a binding constraint) AND the actor was not deferred via the per-§11.P cache-miss path (`refusal_kind="no_character_context"`), the violation fires. `detected_phrase` is `"{actor_name} (verdict: {category}) absent from narration"`.

**Mitigation.** Identical to the other classes — regen with retry constraint that names the missing actor explicitly and binds the LLM to honor every non-FREE actor in `=== ARBITRATION RESULT ===`. Second fail → escalate to deterministic placeholder narration that surfaces the omitted actor's verdict imperatively (per §6.3 template).

**Why this promotes from observability to structural.** Pre-amendment, §11.B's "Option 1 (sequence — recommended)" trade-off relied on telemetry (logging the per-actor verdict count vs which actor names appear in narration) as a heuristic check; if drop-rate proved non-trivial, v2 would escalate to Option 3 (explicit bracketed actor headers). ACTOR_OMISSION makes the drop-rate enforcement structural — same mechanic as the other three classes — so the LLM cannot silently drop a resolved actor without triggering regen. F-48's closure proof becomes input-layer structural (arbitration) + output-layer structural (ACTOR_OMISSION), not input-layer structural + output-layer observability.

**Sub-decision (filed v1.x, not blocking): pronoun-aware detection.** Two-PC turns where the LLM legitimately addresses one actor by name and another by second-person pronoun ("you spin away") will false-positive on substring match. v1 detection is name-substring only; pronoun-aware detection (track which PC is the "you"-addressed actor for the turn, exempt them from substring check) is deferred to v1.x if observed false-positive rate proves non-trivial. Surfaced here so Session 3 implementation does NOT trip on this and re-decide live — v1 ships substring-only; v1.x ships pronoun-aware iff logs show non-trivial FP rate. The empirical signature for FP measurement is `verification: violation_class=actor_omission retry_passed=1` (retry corrected by adding the missing name; original was likely fine via pronoun).

**Confidence:** locked. Jordan signed off pre-review during Track 7 #2 spec amendment pass. Sub-decision (pronoun-aware) deferred to v1.x — not blocking.

### §11.N — Block and kwarg rename surface change (LOCKED)

The rename `=== ADJUDICATION RESULT ===` → `=== ARBITRATION RESULT ===` in the prompt and `adjudication_block` → `arbitration_block` in `build_dm_context` is currently embedded in §1.10 ("What's new") but is surfaced here as a **locked-#2 surface change** rather than an inherited side effect.

**Justification.** The multi-actor general case warrants the rename — "arbitration" names the wrapping mechanism that resolves multiple verdicts; "adjudication" names the per-actor primitive. Single-actor turns remain the degenerate of the general case; byte-identical content is preserved for solo turns through the degenerate fall-through. Naming the prompt block and kwarg after the wrapping mechanism (not the per-actor primitive) reflects the architectural shape post-#2.

**Migration shape.** Existing call sites referencing `adjudication_block=...` in `build_dm_context` are updated to `arbitration_block=...` at the same call sites; render content for single-actor turns is unchanged byte-for-byte (degenerate fall-through). No prompt-cache invalidation beyond the variable rename.

**Confidence:** locked. Jordan signed off pre-review during Track 7 #2 spec amendment pass — surfaced here so Session 2 review doesn't re-walk it as a "is the rename worth the surface change" question, and Session 3 implementation has clear authorization to do the rename.

### §11.O — Multi-verdict sibling deduplication semantics (LOCKED PER-ACTOR)

Track 7 #1's §11.L locked sibling-advisory-directive suppression: when a verdict has a binding `capability_decision`, `commitment_directive`, or `combat_redirect`, the other advisory siblings suppress for that turn so the prompt doesn't double-render the constraint. #2's multi-verdict case requires explicit semantics for how that rule extends.

**Locked decision: per-actor scope.** When `ArbitrationResult` contains multiple verdicts, sibling advisory directives suppress **per-actor** — each verdict's binding suppresses its own siblings' contribution for THAT actor only. One actor's binding does NOT silence another actor's advisory siblings.

**Per-turn rejected.** Per-turn suppression (one actor's binding silences all advisory siblings for the whole turn, across all actors) was rejected as too coarse: two-actor turns must allow each actor's advisory context independently. Player A having a `capability_decision` binding shouldn't strip Player B's `combat_redirect` advisory contribution.

**Legacy preservation.** Single-verdict (degenerate) case preserves Track 7 #1's §11.L behavior unchanged — the per-actor scope reduces to per-turn when there's exactly one actor. Solo play is the degenerate-list-of-1 path.

**Where this lands in render.** `combined_constraint` (in `ArbitrationResult`) is built per-actor: each verdict contributes its own block (binding + non-suppressed siblings for that verdict). The combined render concatenates per-actor blocks in priority order. Solo turn = one block; #1's render is byte-equivalent.

**Confidence:** locked. Jordan signed off pre-review.

### §11.P — Per-actor cache miss fallback for arbitrate() (LOCKED)

When `arbitrate()` iterates actors and `orch.get_cached_context(actor)` returns `None` (cache miss for that actor — typically a new player who hasn't posted `!sheet` yet in-session), the per-actor `adjudicate()` call **defers safely** per the partial-projections doctrine: returns `(allowed=True, refusal_kind="no_character_context")` for that actor. Arbitration does NOT invent character context.

**Why this remains.** Track 7 #1.1's `cache_autopopulate` makes this rare for bound PCs (cache populates on first `!sheet` post in-session), but the pre-first-sheet window remains — a player who joins mid-session and posts an action before `!sheet` will hit cache miss until their first sheet post. Same fallback shape as #1's pre-#1.1 behavior.

**Behavior.**
- That actor's verdict is FREE-shaped with `refusal_kind="no_character_context"`.
- Arbitration proceeds with the remaining actors (their verdicts compose normally).
- The cache-missed actor's input is still rendered to the LLM (no binding constraint; LLM has narrative latitude for that actor's intent).
- `ACTOR_OMISSION` verification SKIPS this actor — no binding constraint was issued, so omission is not a violation (per §5.3 step 4 b).

**Documented in.** §5.1 flow (per-actor adjudication step), §7 failure modes (#13), §5.3 ACTOR_OMISSION detection skip rules.

**Confidence:** locked. Jordan signed off pre-review — surfaced here so Session 3 implementation does not re-decide live the cache-miss handling.

### §11.Q — Actor-name source of truth for ACTOR_OMISSION (LOCKED)

`ArbitrationResult.actor_order` contains **PC character names** (e.g., `"Donovan"`, `"Bruce"`), NOT Discord usernames (e.g., `"JORDAN"`, `"TAZZ"`). ACTOR_OMISSION's substring scan operates on character names only.

**Why this matters.** The §5.2 prompt-render shape `JORDAN (Donovan): Stealth check ...` is human-clarity formatting in the rendered prompt — `(Donovan)` clarifies which character the Discord user controls. The dataclass field, however, stores the **character name** as a single string per actor entry. ACTOR_OMISSION's substring scan in §5.3 step 4 needs the character name (not the username) because the LLM narrates characters, not usernames — `"the lookout turns toward Donovan as Bruce charges"` will reliably contain character names; whether it contains "JORDAN" or "TAZZ" is incidental and unreliable.

If the field stored usernames or the rendered concatenated form (`"JORDAN (Donovan)"`), the substring scan would either false-negative (scanning for "JORDAN" against narration that only mentions "Donovan") or false-positive (scanning for `"JORDAN (Donovan)"` against narration that mentions "Donovan" alone). Locking character-name semantics is the only shape that lets the substring detection work as designed.

**Documented in.** §4 `ArbitrationResult` dataclass docstring (`actor_order` field comment); §5.1 step 1 (per-actor adjudication — `actor` is character name); §5.3 step 4 (ACTOR_OMISSION detection); §8.1 test plan (multi-actor turn fixture asserts `actor_order == ["Donovan", "Bruce"]`).

**Confidence:** locked. Jordan signed off during Session 2 review — newly surfaced; locked as-is.

### §11.R — 3+-actor override semantics (LOCKED ALL-PAIRS)

When `arbitrate()` resolves N≥3 actors and the verdicts may contradict in non-adjacent priority pairs, the override scan must operate over **all pairs**, not just adjacent pairs in priority order.

**Locked decision.**
- **All-pairs scan.** For every pair (i, j) of verdicts (i ≠ j), check whether the lower-priority verdict in the pair contradicts the higher-priority verdict's bound resolution. Override fires when ANY pair contradicts.
- **`merge_plan` shape.** Stays `'sequence' | 'override'` — single string per turn. Override fires when the all-pairs scan finds any contradiction.
- **`overridden_actors: list[str]`.** Replaces the prior `overridden_actor: str` field shape. Empty list when `merge_plan='sequence'`; populated with EVERY overridden actor's character name (deduplicated, in priority order) when `merge_plan='override'`.
- **`combined_constraint` render.** Override case enumerates each overridden actor's reaction-not-outcome constraint per actor (one bullet per overridden actor), naming the contradicting actor and the verdict their narration cannot reverse. See §5.2's multi-overridden override sample.

**Why all-pairs (not adjacent-only).** Adjacent-only would silently miss the case where actor A's CHECK is contradicted by actor C while actor B (priority-sorted between A and C) is non-contradictory. Real 3-actor turns hit this shape — A succeeds at a stealth check; B sips a drink (non-contradictory); C asserts "the lookout spotted A clearly" (contradicts A directly). Adjacent-only would compare A-vs-B (no conflict) and B-vs-C (B is FREE no constraint, no conflict) and produce `merge_plan='sequence'` — the F-50-shaped failure for N=3.

**N≥1 fall-through.** All-pairs handles any N including 1: for N=1 the pair-set is empty (sequence trivially); for N=2 there is exactly one pair to scan. Single-actor and two-actor cases reduce naturally; no `ActionBatcher` behavior verification is needed.

**Documented in.** §1.5 (priority rule wording, pairwise → all-pairs); §3 ("What's new" — `overridden_actors` list-shape); §4 `ArbitrationResult` dataclass; §5.1 step 3 (conflict detection — all-pairs scan); §5.2 multi-overridden override sample; §6.4 telemetry (`overridden_actor` → `overridden_actors` comma-list); §8.1 tests (3-actor override fixtures: A-vs-B-and-A-vs-C dual-override; A-CHECK with B independent and C contradicts; etc.).

**Confidence:** locked. Jordan signed off during Session 2 review — newly surfaced; locked as-is. Replaces the implicit "adjacent pairs in priority order" wording from the Session 1 draft.

---

## 12. Out-of-scope adjacencies (filed, not blocking review)

Items adjacent to #2 that are NOT closed by this spec but should not be re-discovered as fresh gaps:

- **Cross-turn arbitration memory.** `last_arbitration_result` persisted in `dnd_scene_state` so next-turn arbitration reads prior verdicts. Closes the cross-turn override case. **LOCKED OUT for v1** (§11.L sub-item 1) — explicit-OUT, not "filed for v2 if observed friction shows it." Cross-turn override remains a known v2 candidate.
- **Anonymous-shape combatant detection.** "A figure," "the shadow," "something" — pronoun-shaped fabricated combatants. Requires entity tracking. Filed.
- **Multi-scene arbitration.** Two players in different rooms posting concurrent actions. Requires per-actor scene tracking. Filed.
- **Single-player multi-intent decomposition.** "I draw my dagger and step toward the door" as two intents. **LOCKED OUT for v1** (§11.K) — explicit-OUT, candidate for v1.x or its own ship after observed-friction logs accumulate.
- **`PLAYER_NARRATED_NPC_ACTION` 4th-wall input gate.** Filed (§11.L.2) — out of #2 scope, eligible for a Track 7 sub-ship.
- **Self-correcting verification.** RAG over canonical NPCs to suggest replacements when LLM fabricates ("you meant Bruce, not Silent Beast"). v3+. Filed.
- **Verification output gradients.** v1 binary pass/fail; v1.x might add a "soft" tier (warn but ship). Filed if observed friction shows the binary gate is too coarse.
- **Combat reaction / held-action handling.** Out of #2's 2A.3 scope per §11.D. Tied to whatever path Avrae's reaction tracking takes.
- **NPC stat hydration (Track 6 #4).** Adjacent ship; verification's fabricated-combatant gate surfaces the gap, #4 closes the legitimate-NPC-add case.
- **Texture verification (motif drift, lore density, tone).** Filed for clothes-queue post-Track-7.

---

## Appendix A — v1 vocabulary scope (Code-drafted)

The specific verb/noun coverage of each detection regex is implementation detail, not architecture. Code drafts the vocabulary at implementation time and lands it inline with the modules:

- `_FABRICATED_COMBATANT_VERBS` — combat-active verbs (attacks, swings, hits, charges, blocks, parries, springs, strikes, rakes, lashes, conjures, casts at, fires at, slashes, lunges, rears) — final list expands during implementation
- `_STATE_MUTATION_PHRASES` — HP/XP/death/permanent-state claim regex set
- Per-verdict-category contradiction phrase lists (CAPABILITY-success, CHECK-success, CHECK-failure, COMBAT-landed)
- `_PROPER_NOUN_CANDIDATE_PATTERN` — capitalized-name extraction regex (excluding sentence-start-common-noun false positives)
- `_ACTOR_OMISSION_CHECK` — substring scan over `arbitration_result.actor_order`, filtering FREE verdicts and `no_character_context` deferrals (§11.M, §11.P). Pure name-substring in v1 (case-insensitive); pronoun-aware extension is filed for v1.x — no upfront vocabulary needed beyond the actor names already present in `arbitration_result`

Vocabulary is observable in logs (`verification:` line echoes `detected_phrase`), so misses surface empirically and the lists tighten from observed friction (Doctrine §6 — evolve from observed, not anticipated). Vocabulary is NOT a review surface; spec review is for taxonomy/composition/gates only.

---

## Appendix B — Relationship to other layers

- **Track 7 #1 Adjudication Layer.** Per-actor primitive. #2 wraps `adjudicate()` in `arbitrate()` (multi-actor) and adds `verify_narration()` (output-side). #1 stays unchanged at the call site for `adjudicate()`; the call site gains a new wrapper.
- **Track 7 #1.1 Cache Auto-Populate.** Orthogonal. Cache fragility was the input-data problem; #2 addresses input-multiplexing and output-verification problems.
- **Phase 2A.3 off-turn drop.** Architectural prior. #2 does NOT relax it (§11.D). Combat-mode multi-actor is filtered at transport before #2 sees anything.
- **`ActionBatcher`.** Existing coalescer. #2 changes how its output is consumed (structured list instead of concatenated string) but NOT the coalescing mechanism itself.
- **S9 capability grounding.** Reused by #1's `_gate_capability`; #2's verification doesn't directly call S9 but reads the same canonical sources for verdict-contradiction detection.
- **S20 combat initiation orchestration.** #2's verification's fabricated-combatant gate may force more combat-initiation paths through S20 (LLM tries to introduce a new creature in combat → verification refuses → retry must use canonical → LLM is forced to surface `!init add` instead of fabricating). Filed as a side-benefit, not a load-bearing claim.
- **S21 combat persistence.** Reused — `dnd_combat_state.combatants` is one of verification's canonical sources for fabricated-combatant detection.
- **S25 OOC advisory lane.** Orthogonal. Advisory mode is read-only Q&A; no narration to verify. Out of scope.
- **Track 6 #4 NPC stat hydration.** Adjacent — verification surfaces the gap (LLM tries to introduce NPC, verification refuses); #4 closes it on the legitimate side.

**Filed, not sequenced** — per `feedback_no_pre_sequencing.md`. This spec is one of multiple candidate next layers; ordering is re-decided after each ship's logs accumulate enough signal to inform the next pick. Track 7 #2 ships when Jordan picks it; what comes next is decided after #2's logs land.
