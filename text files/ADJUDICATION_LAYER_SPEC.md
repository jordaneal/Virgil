# Adjudication Layer — Design Spec v1 (DRAFT)

**Status:** LOCKED — review complete. §1 decisions and §11 decision points (A–L) are locked as proposed. Implementation may proceed.
**Pattern:** Pure-function-in-orchestration sibling (Doctrine §59) — but composes BEFORE the sibling directive band rather than alongside it. New root layer that the existing directives become consumers of.
**Track:** Track 7 #1 (binding adjudication) — promotes mechanical authority from advisory text to structural gate.
**Failure mode this targets:** S25 multiplayer test exposed that Virgil treats player input as narrative *suggestion*, not mechanically validated *intent*. Failed rolls don't fail. Capability refusals fold under "says who." Combat narrates without Avrae. Players override each other through social assertion. Fabricated NPCs enter combat with no stats. The architectural diagnosis: the LLM is in the decision path for things that should be deterministic Python. Existing layers (S19 commitment, S9 capability, S23 #2 redirect, S21 persistence) are advisory — the LLM is asked to honor them but isn't structurally bound. This spec promotes adjudication from advisory to binding: a single pure function classifies intent into one of five action categories, applies deterministic gates, and emits narration constraints that the LLM can shape into prose but not negotiate around.

---

## 1. Proposed decisions (NOT yet locked — see §11)

These are what I'd propose if the spec went straight to implementation. Every one is up for change in review.

1. **New module `adjudicator.py`.** Not folded into `dnd_orchestration.py`. Rationale: orchestration is now ~2900 lines covering intent classification, roll discipline, capability grounding, six sibling directives, and weapon schema re-exports. Adjudication is the *root* layer that other directives consume — separating it physically makes the dependency direction visible (orchestration consumers import from adjudicator; adjudicator imports nothing from orchestration except the existing `classify_action_intent` for fallback).

2. **Single pure entry point `adjudicate(player_input, scene_state, character, combatants, active_turn) -> AdjudicationResult`.** Same `(body, signals)` contract as the rest of the sibling family, except the structured `AdjudicationResult` IS the body shape — narration constraints are derived deterministically from it, signals telemetry-only.

3. **Five action categories (locked taxonomy from prompt).**
   - `FREE_ACTION` — pure RP, no stakes, no roll, no resource cost. Tavern conversation, looking around casually, sitting, dancing. LLM narrates freely within scene constraints.
   - `CHECK_ACTION` — outcome uncertain, roll required. Stealth, Perception, Persuasion, Investigation, Athletics. Resolver decides skill, DC band, consumes existing roll if buffered. Narration constrained by success/failure.
   - `CAPABILITY_ACTION` — class/level/spell/feature gates apply. Casting spells, class features, racial abilities, special movement. Resolver checks character sheet (class, level, spells known, slots, features). Refusal is binding — no "says who" override.
   - `COMBAT_ACTION` — anything hostile (attack, damage, restrain, kill, hostile mind-control). Resolver requires `dnd_scene_state.mode='combat'` AND populated `dnd_combat_state` init order. If combat isn't active, resolver either initiates orchestration (Track 6 / S20 path) or refuses with "you can't attack — combat isn't active."
   - `WORLD_BOUNDARY_ACTION` — reality-violating actions ("spawn 100k crystals," "become god," "poop out a crystal baby"). Hard refusal, no negotiation, narration is "that does not occur" or equivalent. No fabricated justification.
   - Internal sixth value `FALLBACK` — produced only when classification errors or input is unclassifiable. Defaults to CHECK_ACTION resolution (default-to-roll posture). Never defaults to FREE (would re-open godmode).

4. **Composes BEFORE all sibling directives in `dm_respond`.** Adjudication runs first thing after `scene_state` is loaded, before `classify_action_intent`, before `should_call_roll`, before every existing directive. Each downstream consumer receives the `AdjudicationResult` and either honors it (capability_directive: silent on adjudication-handled refusals; combat_redirect: silent when adjudication already refused) or composes around it. The intent classifier becomes a *fallback* for cases adjudication can't categorize, not the primary signal.

5. **Narration binding via top-of-prompt block (sibling pattern, position elevated).** A new `=== ADJUDICATION RESULT ===` block renders FIRST in the system prompt, above DM philosophy. Body shape encodes the resolver's verdict imperatively: `"This action is REFUSED. Narrate the world's response — the player's intent does not occur. Do not negotiate, do not ask 'are you sure'."` for refusals; `"This action requires a Stealth check at DC 15. The player rolled 8 — narrate the failure."` for resolved checks. The LLM is constrained to the verdict; prose is its job. Same pattern as existing concrete-in-prompt §48.

6. **Resolver is deterministic Python, not a second LLM.** Per Doctrine §1 (prompt is tone, structure is the game) and the explicit rejection of probabilistic adjudication in `WHY.md`/`WORKING_WITH_CLAUDE.md`. Intent classification reuses the regex/keyword shape proven in `WEAPON_CLAIM_RX` + `_NOUN_TO_CATEGORY` (`dnd_orchestration.py:883`). World-boundary detection is a curated phrase list — explicit enumeration, not LLM judgment.

7. **DC bands: three tiers (easy / medium / hard) with hardcoded thresholds.** Easy=10, Medium=15, Hard=20. Resolver picks band per action class (sneak past sleeping guard=easy, persuade hostile noble=hard). Full 5e DC calibration tables out of scope. v2 if observed friction.

8. **Roll consumption from RollBuffer.** When CHECK_ACTION fires and a recent unconsumed Avrae roll matches the actor + skill, adjudication consumes it and binds the verdict to the actual result. When no roll is buffered, adjudication emits a `[CHECK_REQUIRED]` directive that names the specific `!check <skill>` the player must run, and the LLM narration block is suppressed until the roll lands. This closes the "narrate without rolling" failure from S25 #4.

9. **Player-side scope only in v1.** NPC actions are LLM-narrated within combat orchestration — no adjudication path for "the goblin attacks Donovan." That's what Avrae's `!attack` is for. Player-side is where the godmode failures live; NPC-side is where the existing rules engine already adjudicates.

10. **Telemetry: per-turn `adjudication:` log line.** Always-fire (empirical baseline like every other sibling). Shape: `category={free|check|capability|combat|world_boundary|fallback} allowed={1|0} reason={...} skill={...} dc={...} roll_consumed={1|0}`. Drives empirical category distribution, refusal frequency, and roll-discipline coverage.

---

## 2. Goal — which THE_GOAL bullets this serves

Direct hits on the failure-mode list:

- ✅ **"Player agency has to survive the AI."** Inverse case here: when one player's social assertion ("I tell him to stand down — he stands down") overrides another player's rolled action by LLM acquiescence, the *first* player's agency was undone by the AI rendering the second player's words as fact. Adjudication binds the resolution — no player can mechanically reverse a rolled outcome by talking past it.
- ✅ **"If failed rolls just stop play instead of changing the situation, we've failed."** Inverted by the multiplayer test: failed rolls *don't* change the situation today — they're narrated as ambiguous, partial, or simply ignored. Adjudication makes failure deterministic and forces narration to render the consequence, which is the precondition for failure-becomes-story.
- ✅ **"Choices should matter later, not just in the moment."** A choice that fails to resolve mechanically in the moment will not matter later. Binding adjudication is the floor under which "matters later" can stack. S19 commitment surfaces unresolved commitments after the turn; this layer prevents the unresolved state from being created in the first place when the resolver had a clean answer.
- ✅ **"NPCs we wronged should still be wronged."** Players currently fabricate NPC compliance ("the bartender goes upstairs") and the LLM renders it. Adjudication routes hostile/coercive actions against NPCs through CAPABILITY/COMBAT/CHECK paths — fabricated submission has no resolver verdict to lean on.
- ✅ **"I want combat to be fun. I want to feel something when I kill an enemy."** Combat that narrates without Avrae is combat with no kinetic floor — every hit is rhetorical. Adjudication's COMBAT_ACTION gate forces the Avrae channel before the LLM can render a hit.

Indirect hits:
- **"The world should reward curiosity."** Different mechanism (knowledge tier), but adjudication's CHECK_ACTION default-to-roll posture means curiosity actions ("I search the cellar") consistently produce roll outcomes the world can react to — rather than the LLM occasionally narrating finds without a roll.
- **"If players come up with a creative solution and the system forces them back to the 'right' path, we've failed."** Tension acknowledged: adjudication MUST permit creative solutions that pass capability/world-boundary gates. The category split makes this explicit — FREE_ACTION carries no resolver opinion; CHECK_ACTION can be at any DC but the *attempt* is always allowed; only WORLD_BOUNDARY_ACTION refuses outright. CAPABILITY_ACTION refuses on character grounds (you don't have the spell), not creativity grounds.

Bullets v1 explicitly does NOT serve:
- "Failure should create story, not dead ends." Adjacent — adjudication creates the conditions for failure-as-story (deterministic failure outcomes), but the *narrative shape* of the failure is still LLM-generated. v1 binds the verdict; it does not curate the prose.

---

## 3. Architecture pattern

### Where it sits

```
                    Player message arrives
                            │
                            ▼
             scene_state = get_scene_state(campaign_id)
             character   = primary_ctx (cached)
             combatants  = get_combatants(campaign_id)
             active_turn = get_active_turn(campaign_id)
                            │
                            ▼
             ┌────────────────────────────────────────┐
             │  result = adjudicate(                  │
             │      player_input=text,                │
             │      scene_state=scene_state,          │
             │      character=character,              │
             │      combatants=combatants,            │
             │      active_turn=active_turn,          │
             │  )                                     │
             │  → AdjudicationResult(                 │
             │       category, allowed, skill, dc,    │
             │       roll_consumed, refusal_kind,     │
             │       narration_constraint, signals)   │
             └────────────────────────────────────────┘
                            │
                            ▼
             Existing classify_action_intent / should_call_roll
             still run — but they read from result.category
             when result is non-FALLBACK; otherwise fall back to
             the existing regex path.
                            │
                            ▼
             Existing sibling directives compose AS CONSUMERS:
              - capability_decision: silent if adjudication
                already CAPABILITY-refused
              - combat_redirect: silent if adjudication
                already COMBAT-refused
              - commitment_directive: composes as before
                (it operates on cross-turn signals adjudication
                doesn't see)
                            │
                            ▼
             build_dm_context renders =====
             === ADJUDICATION RESULT === FIRST,
             above philosophy block.
                            │
                            ▼
                     LLM narration
```

### What's new

- New module `adjudicator.py`.
- New dataclass `AdjudicationResult` with structured fields for category, allowed/refused, narration constraint string, roll handling, refusal kind, signals.
- Five category constants `FREE_ACTION`, `CHECK_ACTION`, `CAPABILITY_ACTION`, `COMBAT_ACTION`, `WORLD_BOUNDARY_ACTION`, plus `FALLBACK`.
- Six classification regexes (one per category + fallback router) modeled on `WEAPON_CLAIM_RX` shape — verb+noun proximity, article/possessive tolerance, curated vocabulary.
- `_WORLD_BOUNDARY_PHRASES` curated list — reality-violating action phrases (spawn N of X, become god, conjure infinite Y, poop out Z, ascend to plane, vanish from existence, etc.).
- `_CAPABILITY_GATE_TABLE` — class/level/spell-slot/feature lookups against `CharacterContext.attacks`, `narrative_tags`, `char_class`, `level`. v1 covers spellcasting (slot ≥1) and class-feature claims; weapon claims continue to delegate to `check_action_capability`.
- One new kwarg in `build_dm_context`: `adjudication_block=""`.
- One new render block: `=== ADJUDICATION RESULT ===` (rendered FIRST in prompt, before philosophy).
- Telemetry: `adjudication:` log line on every turn.
- One new helper `consume_recent_check(buffer, actor_name, skill, since_ts)` — RollBuffer query for adjudication's CHECK_ACTION resolution.

### What's reused

- `classify_action_intent` — used as the FALLBACK classifier. Adjudicator's primary classifier is finer-grained (5 categories vs 7 intents), but the existing regex set is sound enough to backstop unmatched cases.
- `check_action_capability` (S9) — adjudicator delegates weapon-shape capability claims to it, then *binds* the verdict (CONFIRMED → allow, VALID_BUT_UNCONFIGURED → allow with annotation, INVALID → REFUSE). The S9 advisory shape stays; adjudication chooses how to act on it.
- `RollBuffer` — existing per-guild, 75s TTL. Used by `consume_recent_check`.
- `CharacterContext` — adjudicator reads `char_class`, `level`, `attacks`, `narrative_tags`, `skills`, `saves` for capability gating.
- `dnd_combat_state` (combatants table) — adjudicator reads init order to gate COMBAT_ACTION.
- `dnd_scene_state.mode` — master gate for COMBAT_ACTION ("combat isn't active" refusal path).
- The `(body, signals)` pure-function pattern (Doctrine §59).

### What's NOT changed

- `Avrae` write boundary (Doctrine §65). Adjudicator never emits `!`-prefixed commands; the `[CHECK_REQUIRED]` directive *describes* the command for the LLM to surface to the player.
- `update_combatants_from_init_list` and the rest of S21's combatants pipeline — still the single write path for `dnd_combat_state`.
- Existing intent tags. `INTENT_COMBAT`/`INTENT_RISKY`/etc. continue to exist; they map deterministically to adjudication categories under FALLBACK.
- The S19 commitment directive — operates on cross-turn signals (prior intent, scene-shift detection) that adjudication doesn't see in single-turn scope. Stays.
- `should_call_roll` — keeps current shape; under adjudication, its output is a CONSUMER of `AdjudicationResult.skill` and `.dc` rather than an independent signal. (Belt-on-suspenders for FALLBACK turns.)

---

## 4. Data model

### `AdjudicationResult` (new dataclass)

```python
@dataclass
class AdjudicationResult:
    category: str            # one of: free | check | capability | combat | world_boundary | fallback
    allowed: bool            # True iff the action proceeds; False = refused outright
    refusal_kind: str        # '' when allowed; otherwise: 'capability' | 'combat_inactive' | 'world_boundary' | 'check_failed'
    skill: str               # populated for CHECK_ACTION; '' otherwise
    dc: int | None           # populated for CHECK_ACTION; None otherwise
    dc_band: str             # 'easy' | 'medium' | 'hard' | '' — human-readable band
    roll_consumed: bool      # True iff a buffered Avrae roll was consumed inline
    roll_value: int | None   # the consumed roll value, if any
    success: bool | None     # CHECK outcome when resolved this turn; None when pending
    narration_constraint: str  # imperative directive body for the prompt
    signals: dict            # telemetry-only; flattened for the log line
```

### No new schema

Detection reads from existing state:
- `CharacterContext` (Avrae sheet cache, in-process)
- `dnd_scene_state.mode`
- `dnd_combat_state` combatants snapshot
- `dnd_combat_state` active_turn row
- `RollBuffer` per-guild deque

Roll consumption mutates `RollBuffer` (mark consumed) — same pattern as existing `consume_check` flows. No new persistence.

If v1 needs cross-turn adjudication memory (e.g., "this player attempted X last turn, second attempt now is harder DC"), filed as v2 under §10.

---

## 5. Detection / classification layer

### 5.1 Trigger

`adjudicate(...)` runs as the FIRST orchestration step in `dm_respond` after `scene_state` is loaded, before `classify_action_intent` (which is preserved as the FALLBACK classifier). All downstream directives compose around the result.

### 5.2 Classification flow (proposed v1)

```
INPUT: player_input

1. WORLD_BOUNDARY check (highest priority — reality-violation)
   - Match against curated _WORLD_BOUNDARY_PHRASES (regex set).
   - Hits include: spawn|conjure|create N of X (where N >= 100), 
     become (god|deity|immortal), ascend to (plane|godhood), 
     vanish from existence, poop out, birth (a|the) X, etc.
   - On hit → REFUSE outright. No further classification.
   - Output: category=world_boundary, allowed=False, refusal_kind='world_boundary',
     narration_constraint="Refuse the action. The world does not bend that way. 
     Narrate the action's non-occurrence in-fiction (the air ripples and reasserts; 
     the ritual fails; the player's voice doesn't carry that authority). Do NOT 
     fabricate an in-fiction agent that grants the impossible request."

2. COMBAT intent check (existing COMBAT_RX from orchestration)
   - On hit → COMBAT_ACTION classification.
   - Sub-gate: scene_state.mode == 'combat' AND combatants snapshot has 
     ≥1 alive entry AND active_turn populated.
     - If gate passes → allowed=True, narration_constraint="Combat action 
       is valid. Surface the appropriate Avrae command (!attack <weapon> -t 
       <target>) to the player. Do NOT narrate the hit/miss outcome — 
       that's Avrae's verdict to deliver."
     - If gate fails (combat not active) → allowed=False, 
       refusal_kind='combat_inactive', narration_constraint="Combat is not 
       active. The player cannot attack. Narrate the world's response 
       (intended target sees the threat, draws weapon, calls for guards) 
       and prompt the player to confirm intent so combat can be initiated 
       via !init begin (Track 6 / S20 path)."
   - This subsumes the S20 combat-initiation orchestration for player-typed 
     combat intent in non-combat mode. Composition order ensures S23 #2 
     combat_redirect is silent when adjudication has already handled it.

3. CAPABILITY check (class/level/spell/feature gates)
   - Match against _CAPABILITY_INVOCATION_PHRASES (cast/invoke/channel/use 
     + feature-noun list).
   - On hit → look up character.char_class, character.level, 
     character.narrative_tags, character.attacks for the claimed capability.
     - Spell claim ("I cast Fireball") → check char_class is caster, 
       check level is sufficient (3rd-level slot for Fireball), check 
       spell-name in known-spell list (skeleton hint or cached spellbook).
     - Class feature claim ("I rage") → check char_class includes 'barbarian' 
       AND level ≥ 1.
     - Racial ability claim ("I use Darkvision") → check 
       narrative_tags has 'darkvision'.
     - On match → allowed=True, narration_constraint="The character has the 
       claimed capability ({capability}). Narrate the use; surface mechanical 
       command if appropriate (!cast <spell> for spells, !ability <feature> 
       for features)."
     - On miss → allowed=False, refusal_kind='capability', 
       narration_constraint="The character does not have the claimed 
       capability ({capability}). Refuse in-fiction — the gesture fails, 
       the words don't carry, the rage doesn't come. Do NOT negotiate. 
       Do NOT narrate it as if it worked. Do NOT fabricate justification 
       (no NPC arrives to grant the spell, no scroll appears, no latent 
       ability awakens)."
   - Weapon claims continue to route through check_action_capability(); 
     adjudicator binds its 3-state verdict: CONFIRMED→allow, INVALID→refuse, 
     VALID_BUT_UNCONFIGURED→allow with soft annotation (current S9 behavior preserved).

4. CHECK intent check (existing EXPLORATION_RX, RISKY_RX, CONTESTED_RX)
   - On hit → CHECK_ACTION classification.
   - Skill mapping: reuse _pick_skill() from orchestration (EXPLORATION_DEFAULT_SKILLS, 
     CONTESTED_DEFAULT_SKILLS), default per category.
   - DC band: scene-state-aware lookup (low-tension exploration=easy, 
     contested social vs hostile actor=hard, default=medium).
   - Roll consumption: query RollBuffer for actor+skill within last 75s.
     - If found → AdjudicationResult.roll_value=N, success=N≥dc, 
       narration_constraint="The player rolled {N} against DC {dc} ({band}). 
       This is a {success|failure}. Narrate the {success|failure} outcome only — 
       do not narrate ambiguity, do not narrate partial success unless 
       severity='meaningful' AND roll within 2 of DC."
     - If not found → narration_constraint="This action requires a {skill} 
       check at DC {dc} ({band}). Surface !check {skill} to the player and 
       narrate ONLY the moment of attempt — do not narrate outcome. 
       Outcome lands when the roll arrives." (CHECK_REQUIRED directive.)

5. FREE_ACTION fallback (default for unclassified — see §11.E below 
   for proposal that this should default to CHECK instead)
   - SOCIAL_RX, TRIVIAL_RX, or fully unmatched → FREE_ACTION.
   - allowed=True, narration_constraint="" (no constraint — LLM narrates 
     freely within scene constraints).

6. FALLBACK (unrecoverable classification error or empty input)
   - category=fallback, allowed=True, narration_constraint="Adjudicator 
     could not classify this action. Treat as CHECK_ACTION default — if 
     the action has any uncertain outcome, ask for the most relevant 
     skill check before narrating resolution."
   - Logs [ADJUDICATOR_FALLBACK] line.
```

### 5.3 World-boundary phrase list (initial)

Curated, not learned. Expand from observed friction.

```python
_WORLD_BOUNDARY_PATTERNS = [
    r'\bspawn\s+\d{3,}\b',                    # "spawn 100 crystals"
    r'\bconjure\s+(?:a\s+)?(?:thousand|million|infinite|endless)\b',
    r'\bcreate\s+\d{3,}\b',
    r'\bbecome\s+(?:a\s+)?(?:god|deity|immortal|omnipotent)\b',
    r'\bascend\s+to\s+(?:godhood|divinity|the\s+heavens)\b',
    r'\bbirth\s+(?:a|the)\s+\w+',             # the "crystal baby" case
    r'\bpoop\s+out\b',
    r'\bvanish\s+from\s+existence\b',
    r'\bbreak\s+(?:the|this)\s+(?:reality|simulation)\b',
    r'\bend\s+(?:the\s+)?(?:world|universe|campaign)\b',
    r'\brewrite\s+(?:the\s+)?(?:rules|reality)\b',
    r'\bi\s+(?:am|become)\s+(?:the\s+)?dm\b',
]
```

### 5.4 DC band thresholds (proposed)

```
easy   = 10
medium = 15
hard   = 20
```

Band selection:
- EXPLORATION_RX hit + scene_state.mode in (exploration, downtime) → easy or medium
- EXPLORATION_RX hit + scene_state.mode == combat → medium or hard
- CONTESTED_RX hit vs willing actor → easy
- CONTESTED_RX hit vs hostile actor → hard
- RISKY_RX hit + low tension → medium
- RISKY_RX hit + high tension → hard
- Default (anything else categorized CHECK) → medium

DC tables not loaded from data — band selection lives in the resolver function. Per-action overrides filed for v2 (§10).

---

## 6. Resolution / narration constraint shape

### 6.1 Adjudication block in `build_dm_context`

Renders FIRST in the system prompt, above philosophy block. Composition order in `build_dm_context`:

```
{adjudication_block}{philosophy_block}{tone}{...all existing blocks...}
```

Reasoning: adjudication is the RULES LAYER; philosophy is HOW-TO-INTERPRET-THE-RULES. Rules come first, then interpretation. Concrete-in-prompt §48: the verdict is the most concrete fact this turn; it should sit at the top so the LLM never re-reads its own narration upstream of it.

### 6.2 Narration constraint phrasing

Imperative, mode-specific, NEVER hedging. Examples per category:

**Refused (capability):**
```
=== ADJUDICATION RESULT ===
The player has claimed a capability ({Fireball}) the character does not have ({Donovan, Rogue 4}). REFUSE the action in-fiction.

The character is a Rogue. Rogues do not have spell slots. The words do not carry. The gesture fails. The intended effect does not occur.

Do NOT:
  - narrate the spell working
  - introduce a scroll, wand, or item that grants the spell
  - have an NPC interrupt with "you don't have that" (4th-wall break)
  - negotiate ("are you sure?", "do you mean...")

DO:
  - narrate the moment of attempted invocation and its quiet failure
  - surface the in-fiction reason if natural (no formal training, no slot, no source)
```

**Refused (combat inactive):**
```
=== ADJUDICATION RESULT ===
The player has declared a combat action ("I attack the bartender") in non-combat mode. Combat is not active in this scene.

Do NOT narrate the attack landing.
Do NOT narrate the target taking damage.

DO narrate the world's response: the bartender sees the move, others react, the room shifts. Then PROMPT the player: "Combat hasn't started yet — do you want to commit, in which case roll initiative (!init begin)?"

If the player confirms, S20 / Track 6 combat-initiation orchestration takes over from here.
```

**Refused (world boundary):**
```
=== ADJUDICATION RESULT ===
The player has declared an action that exceeds the world's reality ("I spawn 100,000 crystals"). REFUSE.

Narrate the non-occurrence:
  - the air ripples and reasserts
  - the ritual fails for reasons even the character doesn't understand
  - the words don't catch — as if the world refuses them

Do NOT:
  - introduce an NPC who grants the request (no Keeper-of-the-Vein appears)
  - narrate it working at smaller scale ("1 crystal appears")
  - explain the metaphysical reason
  - negotiate ("perhaps you mean...")

This is a hard boundary. The action does not occur.
```

**Allowed with check (roll consumed):**
```
=== ADJUDICATION RESULT ===
The player attempted a Stealth check (DC 15, hard band). Avrae rolled 8.

This is a FAILURE. Narrate the failure outcome only.

The player is detected, the noise carries, the lookout turns. Do NOT narrate ambiguity ("you think they might have heard you"). Do NOT narrate partial success. Roll < DC means the attempt failed cleanly.
```

**Allowed with check (roll pending):**
```
=== ADJUDICATION RESULT ===
The player attempted an action requiring a Perception check (DC 15, medium band). No roll has landed yet.

Surface the command: "Roll !check perception."

Narrate ONLY the moment of attempt (Donovan crouches, listens, scans the dim room). Do NOT narrate outcome — what they hear or don't hear arrives when the roll lands.
```

**Allowed (free):**

No `=== ADJUDICATION RESULT ===` block rendered. Empty narration_constraint omits the entire section. Same pattern as silent directives elsewhere (capability CONFIRMED → empty, persistence non-combat → empty).

### 6.3 Update on emit

No DB writes. RollBuffer mutation when roll consumed (mark consumed flag). Logging only:

```
adjudication: campaign={X} actor={Y} category={CAT} allowed={1|0} 
              refusal_kind={...} skill={...} dc={N} band={easy|medium|hard|}
              roll_consumed={1|0} roll_value={N|-} success={1|0|-}
              input={first_140_chars!r}
```

---

## 7. Failure modes + mitigations

1. **Over-refusal — adjudicator blocks legitimate creative play.** Player tries a creative non-standard action, regex misclassifies as world_boundary or capability refusal.
   *Mitigation:* `_WORLD_BOUNDARY_PATTERNS` is curated, narrow, and explicit. Capability gates only refuse on explicit positive claims (cast/invoke/channel verbs + named feature). Anything ambiguous falls through to FREE or CHECK, never refusal. Logs every refusal so over-refusal patterns are observable and the patterns can be tightened.

2. **Under-refusal — adjudicator allows fabricated action through.** Player phrases the godmode action in language that doesn't hit any regex.
   *Mitigation:* Default-to-roll posture for unclassified actions (§11.E). Even when adjudication can't categorize positively, it doesn't default to FREE; CHECK_ACTION is the safer fallback because it forces a roll surface, which is itself a constraint. World-boundary phrase list is observability-driven — when a fabrication slips through, the log line surfaces the input string and the pattern list extends.

3. **Roll consumption double-counting.** RollBuffer `consume_check` runs both in the existing `should_call_roll` path AND in adjudication.
   *Mitigation:* Adjudication's roll consumption is the canonical path under v1; `should_call_roll` becomes a passthrough when adjudication has already produced a verdict. Single-write-path §17 — adjudication owns the consume mark, downstream consumers read.

4. **Capability false-negative — character has the spell but skeleton/sheet doesn't show it.** Spell-known list is incomplete; legitimate cast attempt refuses.
   *Mitigation:* Mirror the S9 partial-projections doctrine — when capability source is incomplete, default to ALLOW with annotation, not REFUSE. Refusal only on EXPLICIT contradiction (skeleton-deny, or sheet-class-explicitly-non-caster + spell-name attempted). VALID_BUT_UNCONFIGURED stays the path for soft cases. INVALID is reserved for hard contradictions only.

5. **Mode-flip race — combat starts mid-turn after adjudication ran.** Adjudication classified the action under non-combat mode, mode flipped during LLM call.
   *Mitigation:* Adjudication reads scene_state at function entry — mid-turn flips are by-design ignored. The next turn's adjudication picks up the new mode. Acceptable: combat init takes a turn to settle; the action that started it is the action being adjudicated this turn.

6. **NPC actions slip through.** Player narrates "the goblin hits me" — adjudicator classifies as COMBAT_ACTION on player-side.
   *Mitigation:* Adjudication is player-action only by definition. If the player NARRATES an NPC action, the LLM has always had latitude to refuse that as 4th-wall — adjudication doesn't change this. Filed for v2: detect player-narrating-NPC and refuse as a separate refusal_kind (but observed friction first).

7. **Resolver throws / returns malformed result.** Bug in adjudicator code, partial state, or unexpected input.
   *Mitigation:* Caller wraps in try/except (Doctrine §59 soft-fail). On exception → AdjudicationResult(category=FALLBACK, allowed=True, narration_constraint="") — fail-OPEN, never block narration entirely. Log `[ADJUDICATOR_FALLBACK]` with the exception. Filed under §11.G.

8. **LLM ignores the binding directive.** Even with "this action is REFUSED" at the top of the prompt, the LLM narrates around it.
   *Mitigation:* Same calibration problem as every existing directive (commitment, redirect, capability). v1 leans on Doctrine §25 (directives-as-imperatives) + §2 (hard-stops at end) + concrete-in-prompt §48. If empirical leakage is high in logs, §11.F escalation: post-LLM verification pass that re-runs narration when the response contradicts the verdict. Filed as v2 contingency.

9. **Multi-actor / single-message decomposition.** "I draw my dagger and step toward the door" — adjudicator picks one category for the whole input.
   *Mitigation:* v1 single-composite per §11.D. Multi-action arbitration is Track 7 #2.

10. **Discord client cache / format-unknown.** Adjudicator receives unexpected input shape (image, attachment, malformed text).
    *Mitigation:* Format-unknowns fail-open §49. Empty/malformed input → FALLBACK → no constraint. Acceptable.

---

## 8. Test plan (proposed)

### 8.1 Engine layer (`test_adjudicator.py`)

**Classification correctness:**
- World-boundary inputs across the curated phrase list → category=world_boundary, allowed=False
- "I cast Fireball" with rogue character → category=capability, allowed=False
- "I cast Fireball" with wizard 5+ → category=capability, allowed=True
- "I attack the bartender" in non-combat mode → category=combat, allowed=False, refusal_kind=combat_inactive
- "I attack GO1" in combat mode with combatants populated and active turn = bound PC → category=combat, allowed=True
- "I attack the goblin" in combat mode but combatants empty → category=combat, allowed=False, refusal_kind=combat_inactive (snapshot stale path)
- "I sneak past the guard" → category=check, skill=stealth, dc per band rules
- "I order an ale" → category=free, allowed=True, narration_constraint=""
- Empty input → category=fallback, allowed=True

**Roll consumption:**
- CHECK_ACTION + buffered Avrae !check stealth roll for actor → roll_consumed=True, success per roll vs dc
- CHECK_ACTION + no buffered roll → roll_consumed=False, narration_constraint contains "!check {skill}"
- CHECK_ACTION + buffered roll for DIFFERENT actor → not consumed
- CHECK_ACTION + buffered roll older than 75s → not consumed (TTL)

**DC band logic:**
- Stealth in combat mode → hard
- Persuasion vs willing NPC → easy
- Athletics in low tension → medium

**Refusal narration shape:**
- Capability refusal includes character class+level + claimed capability
- World-boundary refusal includes "in-fiction non-occurrence" framing
- Combat-inactive refusal includes !init begin prompt

**S9 INVALID code path activation:**
- Adjudication CAPABILITY refusal exercises the S9 INVALID render branch for the first time (currently dead code — no v1 producer exists pre-adjudication).
- Test asserts: when adjudicator refuses on capability grounds, S9's `to_prompt_directive()` INVALID branch renders without crashing, and its output is correctly suppressed by §11.L deduplication (adjudication's narration_constraint replaces it).
- Test confirms `CapabilityVerdict.INVALID` enum slot, render branch, and consumer-side rendering integrate without latent bugs from years of unreached code.

### 8.2 Composition test (`test_adjudication_composition.py`)

- `build_dm_context` renders adjudication_block FIRST when populated, OMITS section when empty
- capability_decision rendering is silent when adjudication already refused capability (no double-block)
- combat_redirect rendering is silent when adjudication already refused combat
- commitment_directive renders independently (different signal scope)

### 8.3 Live verification

After v1 ships, replay the S25 multiplayer test scenarios:
- Failed roll narrated as success → expect narration_constraint binding produces failure prose
- Capability refusal under "says who" → expect "the words don't carry" instead of LLM negotiation
- Combat narrated without Avrae → expect refusal + Avrae command surface
- Player-fabricated NPC entering combat → expect combat-inactive refusal (no init slot)
- Player social-asserts another player's action result → expect adjudicator's verdict on the *original* action stays binding (the second player's narration of "he stands down" doesn't override a Persuasion failure)

Each scenario gets its own line in `tests-to-run-post-session.md`.

---

## 9. Migration impact

**Schema changes:** None in v1.

**Code additions:**
- New module `/home/jordaneal/scripts/adjudicator.py` (~600–800 lines projected)
- New `AdjudicationResult` dataclass
- Five category constants + FALLBACK
- Six classification regexes + curated `_WORLD_BOUNDARY_PATTERNS` list
- New `_CAPABILITY_GATE_TABLE` (spell, class-feature, racial-ability lookups)
- New `consume_recent_check(buffer, actor_name, skill, since_ts)` helper
- New `adjudication_block=""` kwarg in `build_dm_context`
- New `=== ADJUDICATION RESULT ===` block render in `build_dm_context` (rendered FIRST)
- New `adjudicate(...)` call site in `dm_respond` (pre-existing intent classification)
- New `adjudication:` log line in `dm_respond`

**Code modifications (low-risk):**
- `capability_decision` renderer: silent when `AdjudicationResult.refusal_kind == 'capability'`
- `combat_redirect` renderer: silent when `AdjudicationResult.refusal_kind == 'combat_inactive'`
- `should_call_roll`: passthrough mode when AdjudicationResult provides skill+dc

**Cross-version safety:** No schema = no migration risk. Old code without adjudicator runs the existing intent/roll/capability pipeline unmodified. Adjudicator is additive — when its module is absent or the function errors, fallback path produces no constraint and existing behavior is preserved. Forward-only.

**Rollback:** Single feature flag `ADJUDICATION_ENABLED = True/False` at module top of `adjudicator.py`. When False, `adjudicate(...)` returns FALLBACK immediately. Composition layer treats FALLBACK as no-op (existing siblings fire as today). Run-time toggle covers fast revert if a category misclassifies in production.

---

## 10. Out of scope (separate specs / future)

- **Multi-action arbitration across players (Track 7 #2).** Two players type simultaneously, conflicting actions, ordering matters. Filed.
- **Full 5e rules engine.** Adjudicator does narrow gates (capability presence, combat mode, world-boundary), not full simulation (action economy, reaction timing, opportunity attacks, concentration breaks, save modifiers). Avrae remains the rules engine for everything mechanical past the gate.
- **DC calibration tables.** v1 uses three-band hardcoded thresholds. Per-action DC tables, situational modifiers, advantage/disadvantage propagation → v2.
- **Adjudication for NPC actions.** NPCs are LLM-narrated within combat orchestration. Player-side adjudication is the v1 scope; NPC-side requires a different model (the rules engine already adjudicates NPC mechanics via Avrae's automation).
- **Magic item / cursed item / spell-effect modifiers.** v1 ignores. A character under Suggestion isn't gate-checked differently.
- **Group checks, contested rolls, opposed rolls.** v1 single-actor only.
- **Adjudication of Avrae mechanical commands** (`!attack`, `!cast`). Avrae mechanically resolves these; adjudication runs on natural-language intent only. Player typing `!cast fireball` directly bypasses adjudication and goes straight to Avrae.
- **Cross-turn adjudication memory.** "Player tried this last turn — second attempt is harder DC." Filed for v2 if observed friction shows it.
- **Player-narrated NPC actions.** Player types "the goblin attacks me" — should refuse as 4th-wall, but that's a separate refusal_kind. Filed.
- **Post-LLM verification pass.** §11.F (b) — re-run when narration violates verdict. v2 contingency only if (a) leaks empirically.

---

## 11. Decision points needing review

These are the surfaces where Jordan's call shapes the spec. Eight surfaced in the prompt + two more from the diagnostic. Numbered to match the prompt's letter scheme where applicable.

### §11.A — Capability vs Combat composition

"I cast Suggestion on him" is both capability (slot, components) and combat (target legality, save). Does the resolver compose both gates, or does one supersede?

- **Recommend:** composed. Capability gate runs FIRST (do you have the means — spell known, slot available); combat gate runs SECOND (is the target valid in current state — is combat active, is the target in init order). On capability failure, refusal_kind='capability' (no slot, no spell) and combat gate doesn't run. On capability success, combat gate runs and may add an Avrae-command surface (`!cast suggestion -t TARGET`) or refuse (combat inactive, target not in scene).
- **Trade-off:** simpler — one supersedes — would let CAPABILITY-only checks short-circuit faster, but leaves a gap when player has the spell and combat-mode is the actual blocker.

### §11.B — Free vs Check context-sensitivity

"I look around" is FREE in a tavern, CHECK in a crypt. How does the resolver disambiguate?

- **Recommend:** scene-state context-sensitive with optional player-verb override. `scene_state.tension_int` and `scene_state.mode` drive the default — high tension or exploration mode in dangerous location → CHECK; low tension social mode → FREE. Player verbs override: "I cautiously search," "I stealthily peek," "I investigate" → always CHECK regardless of state. Default action verbs ("look," "see," "watch") inherit state context.
- **Trade-off:** state-driven defaults can misfire when scene_state lags reality (player in dangerous spot, scene_state still in exploration). Verb override is the player's escape hatch.

### §11.C — World-boundary granularity

"I jump 20 feet" depends on character (Athletics modifier, monk levels). "I fly" depends on class (spell, racial). "I become a god" is universal refusal. Where's the line between WORLD_BOUNDARY (refused outright) and CAPABILITY (refused by character, allowed by another)?

- **Recommend:** WORLD_BOUNDARY is reality-violating regardless of any character ("become a god," "spawn 100,000 X," "rewrite reality"). CAPABILITY is character-limited (Fireball without spell slots, rage without barbarian levels, fly without spell/racial). The split is whether ANY character could legitimately do this — if yes, CAPABILITY; if no, WORLD_BOUNDARY.
- **Trade-off:** "I jump 20 feet" is CAPABILITY (a high-Athletics monk can plausibly approach this) — adjudicator would route to CHECK with a hard DC for normal characters, allow with low DC for monks. World-boundary stays narrow and curated.

### §11.D — Multi-intent decomposition

"I draw my dagger and step toward the door" — single composite or two intents?

- **Recommend:** single composite for v1. Adjudicator picks the highest-precedence category that matches (WORLD_BOUNDARY > COMBAT > CAPABILITY > CHECK > FREE). "I draw my dagger and step toward the door" → CHECK or FREE depending on context-sensitivity rule (§11.B). Multi-action arbitration filed as Track 7 #2.
- **Trade-off:** misses cases where a player legitimately combines a CAPABILITY use with a CHECK action ("I cast Mage Hand to lift the latch and stealth past"). v1 picks the higher precedence (CAPABILITY) and the LLM narrates around the CHECK part. Acceptable until observed friction.

### §11.E — Intent classifier shape

Crude regex/keyword vs LLM-based intent classification vs hybrid.

- **Recommend:** regex/keyword (curated vocabulary), with FALLBACK as a 6th outcome that defaults to CHECK_ACTION (default-to-roll posture). LLM classifier explicitly REJECTED — that's another hallucination layer, contradicts Doctrine §1, and matches the explicit rejection in `WHY.md`/`WORKING_WITH_CLAUDE.md`. Hybrid (LLM as fallback for unmatched) also rejected for the same reason.
- **Trade-off:** regex misses subtler cases. Mitigated by default-to-CHECK posture (rollable failure is the safe default, not free narration).

### §11.F — Narration constraint shape

How does adjudication output bind narration? Two paths:
- (a) hard prompt block at top of context ("ADJUDICATION RESULT: failure. Narrate failure only.")
- (b) post-LLM verification that re-runs if narration violates result

- **Recommend:** (a) for v1 — same pattern as every existing directive, proven to work for capability/combat-redirect/persistence/commitment. (b) is v2 if (a) leaks empirically (per Doctrine §39 — observe before treating).
- **Trade-off:** (a) leaks at the LLM's discretion; (b) is 2x latency/cost per turn. v1 starts with (a) and instruments leakage rate; (b) becomes justifiable only if logs show frequent verdict violation.

### §11.G — Failure mode when adjudication errors

Resolver throws, returns malformed result, or hits ambiguous input.

- **Recommend:** fall back to CHECK_ACTION (default-to-roll posture) with `[ADJUDICATOR_FALLBACK]` log line. Never block narration entirely; never default to FREE (would re-open godmode). Default-to-CHECK is the safest fail-mode because rollable resolution is itself a constraint.
- **Trade-off:** a turn that should have been FREE gets a roll surfaced — minor friction, recoverable. A turn that should have been REFUSED falls through to CHECK — the player rolls, may succeed, and the action proceeds. Observable in logs; tighten the regex set when this fires on real godmode-shaped inputs.

### §11.H — Composition order in `build_dm_context`

Adjudication must come BEFORE directive composition. Where exactly?

- **Recommend:** first thing after scene state read in `dm_respond` (before `classify_action_intent`, before `should_call_roll`, before any directive call). In `build_dm_context`, the `=== ADJUDICATION RESULT ===` block renders FIRST in the system prompt — above DM philosophy, above tone, above past events. Concrete-in-prompt §48: the verdict is the single most concrete fact this turn; nothing should sit above it that could re-frame or soften it.
- **Trade-off:** rendering at top of prompt risks "the model forgets it by the end" in long contexts. Mitigation: hard-stop directives at the END of prompt (Doctrine §2) reinforce the verdict — the existing HARD STOP RULES block can echo "The adjudication verdict above is BINDING. Do not narrate around it." Belt-on-suspenders shape, same as combat redirect today.
- **Rationale for double-render:** the prompt opens with the concrete verdict (§48 concrete-in-prompt) so the LLM frames its response from the verdict outward, and closes with the imperative restatement (§2 hard-stop-at-end) so the verdict is the last constraint in cache before token generation begins. One placement is for framing; the other is for the moment of generation. Same shape Avrae's roll directives already use successfully — the redundancy is the mechanism, not waste.

### §11.I — Telemetry shape

Per-turn `adjudication:` log line. Empirical baseline for category distribution and refusal frequency.

- **Recommend:**
  ```
  adjudication: campaign={X} actor={Y} category={free|check|capability|combat|world_boundary|fallback}
                allowed={1|0} refusal_kind={...} skill={...} dc={N|-} band={easy|medium|hard|}
                roll_consumed={1|0} roll_value={N|-} success={1|0|-}
                input={first_140_chars!r}
  ```
- **Trade-off:** input echo risks leaking long player text into logs. 140-char cap matches the existing `godmode_gap` log shape. No PII concerns (D&D narrative input only).

### §11.J — Player-facing transparency

Does the player see "your action requires a Stealth check" before the roll, or just the narration outcome?

- **Recommend:** roll discipline already surfaces the check command in narration (`!check stealth`), and the adjudication CHECK_REQUIRED constraint reinforces it ("Surface !check stealth to the player and narrate ONLY the moment of attempt"). No additional surface in v1 — transparency exists naturally through the directive's instruction to the LLM. If players express surprise about which skill or DC, file for v2 (player-facing adjudication transparency surface — possibly ephemeral message in `#dm-aside`).
- **Trade-off:** opaque DC means the player doesn't know whether a 12 was good or bad until the LLM narrates. Acceptable — the DM has always been the abstraction over DC; surfacing it to the player breaks the mystique (and is a separate UX choice).

### §11.K — Capability gate scope (NEW — surfaced from diagnostic)

S9's `check_action_capability` is weapon-only and three-state (CONFIRMED / VALID_BUT_UNCONFIGURED / INVALID), with no v1 producer for INVALID. Adjudication's CAPABILITY_ACTION needs to refuse on class/level/spell/feature grounds — NOT just weapon grounds.

- **Recommend:** adjudicator's capability gate is a SUPERSET of S9. For weapon claims, delegate to existing `check_action_capability` and bind: CONFIRMED → allow, VALID_BUT_UNCONFIGURED → allow with annotation, INVALID → REFUSE (becomes the first INVALID producer — the adjudication context). For non-weapon capability claims (spells, class features, racial abilities), adjudicator owns the gate logic against `CharacterContext.{char_class, level, narrative_tags, attacks}`. No S9 modification — adjudicator wraps it.
- **Trade-off:** CAPABILITY_ACTION refusal becomes the first place where INVALID verdicts actually fire — exposes whatever calibration assumptions S9 made on the consumer side. Likely surfaces small bugs in S9's INVALID-rendering directive (currently dead code path). Acceptable; will be caught by tests.

### §11.L — Existing directive deduplication (NEW — surfaced from diagnostic)

S19 commitment_directive, S23 #2 combat_redirect, S9 capability_decision all currently emit independent advisory blocks. With adjudication binding, several of these become duplicative (or contradictory) when adjudication has already issued a verdict.

- **Recommend:**
  - `capability_decision`: silent when `AdjudicationResult.refusal_kind == 'capability'` (adjudication's narration constraint replaces S9's soft annotation).
  - `combat_redirect`: silent when `AdjudicationResult.refusal_kind == 'combat_inactive'` OR when adjudication has already issued a COMBAT_ACTION verdict (allow OR refuse).
  - `commitment_directive`: KEEP — operates on cross-turn signals (prior-intent / scene-shift) that adjudication doesn't see in single-turn scope. No conflict.
  - `persistence_directive`: KEEP — concrete combatants block, orthogonal to adjudication.
  - `loot_directive`: KEEP — orthogonal.
  - `pacing_directive` / `central_thread`: KEEP — orthogonal.
- **Trade-off:** silencing existing directives changes their fire-rate logs (they'll fire less often now). Documented in v1 ship; tests assert silence-when-superseded; baseline `directive_emit:` line accounts for the new dependency.

---

## 12. Open implementation question (filed, not blocking review)

The S25 #4 multiplayer test scenarios reference behaviors that span more than the single-actor, single-turn scope adjudication targets. Two specific patterns:

- **Cross-player override:** Player A rolls Persuasion, fails. Player B then narrates "he agrees with us" and the LLM renders compliance. Adjudication binds A's failure on A's turn; whether B's social assertion can override A's bound result requires multi-actor turn-arbitration logic that is Track 7 #2 territory, not Track 7 #1. v1 recommendation: A's narration_constraint persists in `dnd_scene_state.last_dm_response` so adjudication on B's turn can read it and refuse contradiction. But that's a thin patch — full coverage is Track 7 #2.

- **Fabricated NPC entering combat:** Player names an NPC that doesn't exist in `dnd_npcs` or `dnd_combat_state`, then attempts to attack/persuade/coerce. Adjudication's COMBAT_ACTION gate refuses (no init slot), but CHECK_ACTION against a fabricated target ("I persuade Krelthor") slips through. Filed as a separate `target_existence_check` gate, possibly extending S9's capability layer to "target capability" (does this NPC actually exist in canon). Out of scope for Track 7 #1; called out so it isn't lost.

Both are noted here so they don't get re-discovered as fresh gaps.

---

## Appendix A — v1 vocabulary scope (Code-drafted)

The specific verb/noun coverage of each classification regex is implementation detail, not architecture. Code drafts the vocabulary at implementation time and lands it inline with the module:

- `_WORLD_BOUNDARY_PATTERNS` — full curated list (§5.3 shows initial seeds; final list expands during implementation)
- `_CAPABILITY_INVOCATION_VERBS` + `_CAPABILITY_FEATURE_NOUNS` — spell/feature/racial-ability detection vocabulary
- `_FREE_ACTION_VERBS` / `_CHECK_ACTION_VERBS` — category routing (largely re-exports the existing `EXPLORATION_RX` / `RISKY_RX` / `CONTESTED_RX` / `SOCIAL_RX` / `TRIVIAL_RX` from `dnd_orchestration.py`)
- `_COMBAT_VERB_OVERRIDES` — anything that should escalate from CHECK to COMBAT regardless of mode (already covered by existing `COMBAT_RX`; no expected expansion)

Vocabulary is observable in logs (the `adjudication:` line echoes the input), so misses surface empirically and the lists tighten from observed friction (Doctrine §6 — evolve from observed, not anticipated). Vocabulary is NOT a review surface; spec review is for taxonomy/composition/gates only.

---

## Appendix B — relationship to other layers

- **S9 capability grounding (Session 13).** Adjudication SUPERSETS S9. S9 stays as the weapon-claim sub-gate; adjudication adds class/level/spell/feature gates and binds the verdict (S9 alone is advisory; adjudication makes the same data load-bearing).
- **S19 committed-action resolution (Session 19).** Adjacent. S19 operates on cross-turn signals (prior-intent → current-intent transition); adjudication operates on single-turn classification. Both fire; neither subsumes the other.
- **S20 combat initiation orchestration (Session 20).** Adjudication's combat-inactive refusal IS the entry point to S20 — when COMBAT_ACTION is declared in non-combat mode, the adjudication directive prompts initiative roll, and S20's existing orchestration takes over from there.
- **S21 combat persistence (Session 21).** Orthogonal. Persistence renders state-into-prompt; adjudication binds intent-against-state. Both render in the same turn.
- **S23 #2 combat redirect (Session 23).** Becomes silent when adjudication has already issued a COMBAT verdict (allowed or refused). Stays for the gap cases adjudication doesn't cover (player on-turn combat narration that's neither a refused intent nor an allowed action — e.g., scene description while combat is paused mid-turn).
- **S25 OOC advisory lane (Session 25).** Orthogonal. Advisory channel is a separate router; adjudication only runs on `#dm-narration` inputs.
- **Track 7 #2 multi-action arbitration.** Filed sibling. Single-action adjudication ships first; multi-action arbitration ships when adjudication's empirical category distribution is known.

**Filed, not sequenced** — per `feedback_no_pre_sequencing.md`. This spec is one of multiple candidate next layers; ordering is re-decided after each ship's logs accumulate enough signal to inform the next pick.
