# Quest Layer v0 — Architectural Sketch

**Status:** v0 sketch — pre-spec. Not §11 decisions. Open architectural questions surfaced for operator review before Phase 1 recon opens.
**Date:** May 13, 2026
**Mandate (Prompt 1):** Quest layer is piece 2 of 3 — NPC-voiced quest offers, active-quest tracking. Composition layer (piece 3) anchors scenes to quest acts.

---

## 1. What this is

Quest layer v0 augments the existing skeleton-authored quest surface (three hooks on the campaign 17 notice board: escort caravan, investigate farmstead, survey lost mine) with two architectural primitives:

- **NPC-voiced quest offers** — Virgil-as-DM proposes a quest offer voiced by a canonical NPC; operator approves via `#dm-aside` paste; LLM-as-NPC narrates the offer in scene. Validated-suggester (§1b) pattern.
- **Active-quest tracking** — quests carry a state machine (offered → in-progress → delivered/failed/abandoned); state transitions are engine-deterministic, not LLM-decided.

What v0 is NOT: a quest *generator*. Skeleton-authored quests remain the canon source. v0 surfaces them as offers and tracks them as state. Generation of new quests during play is filed forward (§12).

**Architectural placement.** Sits alongside the consequence layer (S16) — both are ledger-shaped, both track "stakes the world remembers." Consequences track grievances/alliances/debts; quests track *outstanding work the world expects of the party*. Quest layer is the next motion-system primitive after Scene Lifecycle v1 — Scene Lifecycle closed scene immortality; quest layer closes "the party has nothing structurally pulling them forward."

**Couples to (when shipped):**
- Composition layer (piece 3 of mandate) — scenes anchor to quest acts; v0 stays silent on schema for composition forward-compat per operator discipline
- Reward magnitude calibration — DMG-by-level vs LR-X4 corpus pull; §11 decision, source named at spec time

---

## 2. What surfaces it extends, what's new

**Reuses (no schema change in scope):**
- `dnd_npcs` — NPC canonical rows; quest offers route through canonical anchors per skeleton (Eldrin, Lira, Borin in campaign 17). `skeleton_origin=1` NPCs are the priority offer-voicers.
- `dnd_consequences` — adjacent ledger pattern; quest layer borrows the severity-cap, dual-pass parser, and AUTHORITATIVE/EXHAUSTIVE framing pattern from S16 / Track 4 #2 loot v1.2.
- `dnd_scene_state.mode` — read for gate; quest offers fire in social mode primarily (NPC dialogue), exploration secondarily. Combat-mode silent.
- `dm_aside` channel — §1b suggester surface; Track 6 #5.1 SRD suggester + S41 NPC State-Sync are the established precedents.

**Proposed new:**
- `dnd_quests` table (or extension to existing quest schema — Phase 1 recon confirms) carrying `id`, `campaign_id`, `title`, `description`, `offer_npc_id` (FK to `dnd_npcs.id`), `status` enum, `offered_turn`, `accepted_turn`, `delivered_turn`, `reward_summary`, `skeleton_origin` (1 for skeleton-authored, 0 for emergent), `created_at`, `updated_at`. Single-writer pattern (`quest_upsert`, `quest_status_set` — §17 discipline).
- `#dm-aside` suggester card format for quest offers — `[QUEST OFFER PROPOSED]` block with proposed NPC voicer + quest title + reward + offer dialogue snippet. Operator pastes acceptance/rejection.
- `compute_quest_offer_suggester` advisory parser — pure function reading scene_state + canonical NPCs + active-quest-state, emits a structured offer proposal if predicate matches.
- `compute_active_quest_directive` — pure function rendering active quests as prompt context (§59 sibling, 12th instance after Scene Lifecycle v1).
- Telemetry primitives — `quest_offer_proposed:` per-suggestion, `quest_status_change:` per-state-transition, `directive_emit:` extended with `active_quests={N}`.

**Not new:**
- No new ChromaDB collection (quests are structured ledger state, not narrative retrieval surface — same §76-aligned reasoning as `dnd_consequences`).
- No bot→Avrae writes (§F-59 anchor).
- No LLM classification feeding binding state transitions (§1a — state machine is engine-deterministic).
- No mode write. No `advance_time` write. No NPC- or location-canon mutation.

---

## 3. Suggester + directive shape (split surfaces)

Two distinct §59 sibling functions, separate concerns:

**A. Offer suggester — proposes offers, doesn't bind.**

```
compute_quest_offer_suggester(scene_state, canonical_npcs, active_quests, skeleton_quests) → (proposal | None, signals)
```

Reads scene_state (current location, mode, current NPC if any), canonical NPCs (priority: `skeleton_origin=1` at current location), active quest set (must not propose an already-offered quest), skeleton quest hooks (the corpus of offerable quests). Emits structured `proposal` dict: `{npc_id, npc_name, quest_id, quest_title, reward_summary, offer_dialogue_seed}` OR returns None.

Fire predicate: scene_state.mode in {'social', 'exploration'}, current NPC is `skeleton_origin=1`, NPC has unoffered skeleton-quest mapping, recent-turn buffer not saturated with prior offer (cooldown). Predicate is operator's §11 call.

Dispatch: if proposal returned, post to `#dm-aside` as a §1b suggester card. Operator approves by pasting the offer dialogue into `#dm-narration` (or types `/quest offer <id>` shorthand — §11). LLM-as-NPC narrates the proposed offer; engine writes quest with status='offered' on operator paste, not on LLM narration.

**B. Active-quest directive — renders accepted quests for LLM context.**

```
compute_active_quest_directive(active_quests, scene_state) → (body, signals)
```

Reads `dnd_quests WHERE status='in-progress'`, returns a context block listing active quests with `(title, offer_npc, reward_summary, days_since_accepted)`. Block placed in prompt context — exact position is §11.

Below the active-quest threshold (zero in-progress quests): returns `('', {})`. Otherwise renders the block.

LLM job: keep active quests in narrative awareness; let scenes reference them when relevant ("the caravan still waits for you in Stonebridge"). Forbidden: inventing new quests in narration; declaring quests complete without engine state change; offering rewards beyond `reward_summary`.

**State-machine transitions are engine-side, not LLM-side.** Per operator's pre-frame: state mutations stay engine-deterministic.
- `offered → in-progress`: operator types `/quest accept <id>` after player commits in-character (or implicit acceptance via specific in-fiction actions — §11 decision)
- `in-progress → delivered`: operator types `/quest deliver <id>` after delivery scene resolves
- `in-progress → failed`: operator types `/quest fail <id>` after failure conditions met
- `in-progress → abandoned`: operator types `/quest abandon <id>` or via timeout-based engine logic (§11)

LLM never writes status. Per §1a, the structural state lives outside narration.

**This is the 12th and 13th §59 siblings.** Pattern is mature.

---

## 4. NPC-voiced offer shape (LR 36.8% finding port)

LR findings doc measured 36.8% of CRD3 reward-bearing surfaces routed through NPC dialogue (Matt voicing an NPC offering a quest, a payment, an item). This is the dominant pattern for quest-offer surfacing in real DM corpus.

**Port for v0:** offer suggester routes proposed offers through a canonical NPC's voice. The suggester card in `#dm-aside` includes:

```
[QUEST OFFER PROPOSED]
NPC voicer: Eldrin Stormbow
Quest: Investigate the goblin-ravaged farmstead
Reward: 50gp + Stoneforge Guild reputation
Proposed offer dialogue (LLM-narrated when you paste accept):
"Eldrin scans the brush ahead, then turns back to you: 'There's a farmstead two leagues east, off the Trade Road. Goblin sign all around it. Guild's offering fifty gold to anyone willing to clear it out. You'd be doing the road a favor.'"

[Paste this dialogue into #dm-narration to accept offer, or /quest offer reject <id> to decline]
```

NPC voicer is Virgil-as-DM voicing the NPC (Oracle's pre-frame). LLM-as-character renders the offer dialogue when operator pastes acceptance into narration channel. Per §1b: bot proposes, deterministic gate validates (`offer_npc_id` exists, quest not already offered), DM approves by paste, narration emits to chat.

**§1a-aligned.** The state mutation (quest row insert with status='offered') happens on operator paste detection in `_dm_respond_and_post` or via explicit `/quest offer accept <id>` slash command. LLM narration does not write status.

**Decision space for §11:** voicer selection (priority-rule based on NPC at current location, skeleton-origin, and quest-NPC mapping — or operator override per offer); offer dialogue seed source (LLM-generated at suggester time vs static skeleton-authored text vs hybrid).

---

## 5. State machine — engine-deterministic only

Five statuses lock the lifecycle:
- `offered` — Virgil-as-DM has proposed (via operator-pasted offer dialogue); party has not yet committed
- `in-progress` — operator confirmed acceptance; quest is on the active-quest list
- `delivered` — operator confirmed completion; reward render fires once; quest exits active list
- `failed` — operator confirmed failure (timeout, party abandoned objective, narrative loss); reward NOT rendered
- `abandoned` — operator confirmed party walked away without explicit failure; no reward; quest exits active list

**Transition writers are §17-disciplined.** Single function per transition (`quest_offer`, `quest_accept`, `quest_deliver`, `quest_fail`, `quest_abandon`). All writers append to `dnd_quests_audit` (mirror of `dnd_time_advancements` pattern, S27 precedent).

**LLM never writes status, but reads status.** The active-quest directive renders `status='in-progress'` quests only. Other statuses are invisible to prompt.

**Engine-deterministic auto-transitions (§11 candidate):** none at v0. Filed forward — possible v1.x: `delivered` auto-fires on consequence-of-kind='quest_outcome' upsert; `abandoned` auto-fires after N session-days of no engagement. Both require corpus-grounded threshold calibration. v0 is operator-driven only.

---

## 6. Composition-layer forward compatibility — silent

Per operator discipline note: do not pre-couple composition layer schema in v0.

`dnd_quests` does NOT add `current_act_id`, `act_ordering`, `composition_anchor_id`, or any schema field that anticipates composition needs. Composition layer (piece 3 of mandate) will surface its own schema requirements when its spec opens.

What v0 DOES do: ensures the `dnd_quests` schema is composition-extensible without breaking changes. Status enum, FK to `dnd_npcs`, timestamp fields — these are the load-bearing primitives composition will read from. v0 doesn't write composition fields; composition spec writes them when it ships.

---

## 7. Architectural questions for §11 decisions

Surfaced for operator lock before any spec session opens. Leans named where I have them; genuine uncertainty flagged.

1. **Quest source taxonomy.** Skeleton-authored only (campaign 17 has 3)? Operator `/quest add`? Advisory-parser-extracted from narration (LLM proposes new quest based on scene, operator validates)? *Lean: skeleton-authored + operator `/quest add` at v0; advisory-parser extraction is v1.x.* Same shape as consequence v1's parser-deferred model — ship the structural primitive first, add LLM-extraction surface once predicate is grounded.

2. **`dnd_quests` schema shape — new table vs extend `dnd_consequences`.** Consequence ledger already has `kind` enum (mercy/alliance/wronged); could add `kind='quest_offer'` and reuse the existing ledger. Trade: cleaner ledger architecture (one source of stakes) vs cleaner quest state machine (FK shape, status enum specific to quests). *Lean: new `dnd_quests` table.* Trade-off: consequence-as-quest pattern muddies the consequence ledger's narrative-pressure semantic; quests carry different lifecycle and different prompt-render shape. New table keeps both clean.

3. **Offer-trigger predicate.** When does `compute_quest_offer_suggester` fire? Candidates: (a) every social-mode turn with `skeleton_origin=1` NPC, predicate-filtered by unoffered-quest-mapping; (b) every N turns since last offer (cooldown); (c) operator-initiated only via `/quest suggest`; (d) advisory-parser-extracted from narration (LLM proposes "this scene feels like a quest moment", operator validates). *Lean: (a) + (b) hybrid at v0 — fires when predicate matches AND cooldown clears.* Pure operator-initiated (c) puts the work on you; pure auto-fire (a) without cooldown floods `#dm-aside`. Hybrid surfaces offers naturally when narrative context supports.

4. **Acceptance semantics — explicit slash vs implicit narration detection.** Operator types `/quest accept <id>` after the in-fiction acceptance scene? Or engine detects acceptance from player text ("we'll take the job") via advisory parser? *Lean: explicit slash at v0.* Implicit detection requires phrase-vocabulary on player text — same false-positive risk as Scene Lifecycle T2 (deferred per §11.N). Per consequence layer S16 precedent: ship the structural primitive first, add LLM-extraction surface in v1.x if log evidence justifies.

5. **Reward magnitude calibration source.** Two candidates per Oracle pre-frame: (a) DMG-by-level baseline (DMG p.133 treasure-by-level tables — published 5e mechanical balance); (b) LR-X4 corpus pull (CRD3 reward-magnitude data across 140 episodes — empirical real-DM cadence, may diverge from DMG baseline). *No confident lean.* Both have failure modes: DMG produces "correct 5e" rewards that may feel mismatched to Matt-cadence player expectations; LR-X4 produces "Matt-cadence" rewards that may break 5e encounter wealth assumptions. Operator + Oracle call. Source must be named in spec, not buried in constants.

6. **Reward delivery surface.** When `quest_deliver` fires, does the system: (a) auto-emit a reward narration block (LLM renders the reward delivery atmospherically — "Eldrin counts out fifty gold pieces from the guild purse"); (b) post a deterministic reward summary to `#dm-aside` for operator paste; (c) auto-add reward items to inventory (via existing Track 4 #1/#2 inventory primitives); (d) combination. *Lean: (b) + (c) hybrid.* (b) keeps narration operator-controlled (no auto-narration of reward sceneing — that's a scene-authoring move); (c) reuses the existing inventory ledger and avoids ChatGPT-style reward-detail drift via authoritative inventory writer. (a) auto-LLM-render risks the same hallucinated-item drift Loot v1.0 hit (F-39).

7. **`/quest` slash-command surface.** Existing surface (per Track 6 #1 references to `quest_id_autocomplete`, active-quest reminders in footers, `/quest add`): is it a thin existing primitive or a complete v0-replaceable surface? **Phase 1 recon required.** Spec drafts against actual surface; don't assume.

8. **Quest prompt-render shape and position.** Active-quest directive renders where in `build_dm_context`? Candidates: (a) AFTER consequence directive, BEFORE scene lifecycle (tactical-band, same tier as consequences); (b) at footer level (state-aware footer carries active quest count + names); (c) both. *Lean: (a) for narrative pressure + (b) for ambient awareness.* Footer-only (b) is too passive; directive-only (a) loses ambient awareness of quest count when no narrative pressure exists. Hybrid surfaces both.

9. **Quest auto-render-cooldown.** Active-quest directive fires every turn under (a)? Or with cooldown to prevent prompt noise? *Lean: every-turn but with a single concise block (not per-quest expansion).* Block format: one line per quest, capped at 3 quests rendered (severity-then-recency per consequence S16 precedent). Loud quests dominate the block; silent quests stay quiet.

10. **NPC-voicer selection rule.** Multiple `skeleton_origin=1` NPCs at current location, multiple unoffered quests — which NPC voices which? *No confident lean.* Candidates: (a) skeleton-authored explicit mapping (quest→NPC FK); (b) priority rule (highest mention_count NPC voices); (c) operator-selected at suggester card time. Operator's call; spec session walks.

11. **Composition-layer forward compatibility.** Silent per discipline note. v0 schema does NOT pre-couple composition fields. Composition spec surfaces its own needs.

12. **§1a/§1b auto-suggester scrutiny.** Quest offer suggester fires automatically when predicate matches. Same architectural shape as Scene Lifecycle's §11.M concern? *Lean: §1b clean.* Crucial distinction: the suggester proposes via `#dm-aside`, operator approves by paste, engine writes status. No engine→Avrae write, no LLM-decides-binding-state — same shape as S41 NPC State-Sync (anchored §1b second instance). Scene Lifecycle's §11.M concern was auto-fired prompt directive that LLM acts on directly; quest suggester routes through operator approval before any state change. Architecturally cleaner. Spec walks to confirm; no operator + Oracle ambiguity expected.

---

## 8. Operational warnings for Phase 1 recon

Two warnings, framing what recon needs to produce.

**Existing `/quest` surface audit.** ROADMAP and VIRGIL_MASTER reference `/quest add`, `quest_id_autocomplete`, and active-quest footer surfaces. Recon must inventory: (a) what `/quest` slash commands exist today and what they do; (b) what schema backs them (a `dnd_quests` table may already exist with a different shape); (c) what prompt-render surfaces exist (footer references at minimum, possibly more). v0 spec drafts against actual surface, not against the mandate alone. If existing surface is rich enough to skip schema-new and instead extend, spec session walks that path; if it's thin, v0 sketch's proposed schema lands.

**Prompt-size budget.** Per Scene Lifecycle v1 baseline (~26,300 mean total, ~5,900 directives mean), quest layer adds active-quest directive (likely ~300-500 chars depending on quest count) + suggester-card detection logic (zero prompt cost — fires only when suggester proposes, posted to `#dm-aside`). Active-quest directive is the budget pressure. Phase 1 recon should baseline current prompt-size against scene lifecycle's live numbers; quest delta measured against this.

---

## 9. What this sketch does NOT do

- Lock §11 decisions. Those go in the spec doc.
- Address composition layer schema or surface. Filed silent per discipline.
- Propose advisory-parser-extracted quest generation. v1.x territory.
- Address quest-generation-mid-play (LLM proposes new quest from narrative cues). Filed forward.
- Lock reward-magnitude calibration source. §11.5 decision, operator + Oracle.
- Survey the existing `/quest` slash-command surface or `dnd_quests` schema if it already exists. Phase 1 recon.
- Address faction integration (Stoneforge Guild as quest-source faction). Faction layer doesn't exist; quest layer doesn't depend on it.
- Address quest hand-off / NPC-to-NPC quest transfer ("Eldrin says you should talk to the mayor"). Filed v1.x.

---

## 10. Next move

Path A three-session cadence: spec → review → implement. Phase 1 recon scope:

1. Existing `/quest` slash-command surface inventory — what's there, what's missing
2. Existing `dnd_quests` schema (if exists) — column shape, write paths, FK relationships
3. Existing active-quest prompt-render audit — footer, directive, both
4. Skeleton-quest mapping audit — how the three skeleton hooks in campaign 17 are currently represented in DB and prompt
5. Consequence layer pattern review — what to reuse (severity-cap, dual-pass parser shape, AUTHORITATIVE framing) and what to fork (state machine, NPC-voicer routing)

Phase 2 walks §11.1 through §11.12 with operator. Phase 3 ships locked spec.

If shape passes review, Phase 1 recon dispatches per WWC cadence. If shape doesn't pass, rework is cheap — sketch is the artifact.
