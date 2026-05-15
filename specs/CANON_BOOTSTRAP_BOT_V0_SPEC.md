# CANON_BOOTSTRAP_BOT_V0_SPEC.md

**Status:** LOCKED (May 14, 2026) — all 12 §11 decisions locked per `CANON_BOOTSTRAP_BOT_V0_REVIEW.md`. Phase 3 implementation opens. Recommended defaults locked across the board; §11.12 locks (c) defer per Code's lean (canon-sync spec opens when observed divergence friction surfaces). Forward-coupling notes travel to S68/N-4 (prose-folded pronouns as expected starting state) and S69/Causality Engine v0 (faction prose-extraction pattern at table-introduction time).
**Session:** N-10 Path A Phase 1 spec drafting against `planner-scratch/canon_bootstrap_bot_v0_sketch.md`.
**Ship:** Canon Bootstrap Bot v0 — load-bearing prerequisite for S68 (NPC commitment rails) and S69 (Causality Engine v0). The architecture has no authored canon to bite into without this; option-3 authoring (premise-only) means the operator will not hand-write skeleton.md.
**Addresses:** "The downstream architecture is structurally hollow without authored content." Post-Tier-1-close, every motion-system layer (Quest Layer dispatchers, Composition Layer acts, Causality Engine factions) reads from authored canon; the canon does not exist; the gap was being filled by nothing.
**Precedent specs:** `QUEST_LAYER_V0_SPEC.md` LOCKED + v0.1 patch (§1b third-instance precedent), `COMPOSITION_LAYER_V0_SPEC.md` LOCKED + v0.x patch (§1b fourth-instance precedent, cosine-similarity-drop confirmed), `NPC_STATE_SYNC_SPEC.md` LOCKED (§1b second-instance precedent), `TRACK_6_5_1_SPEC.md` LOCKED (§1b first-instance precedent — SRD suggester).

---

## §1. Proposed decisions

Code's recommendations for decisions the spec makes. NOT locks. Each goes to operator + planner review in Session 2 before implementation opens.

---

### §1.A — Premise stored in new column `dnd_campaigns.premise` (additive, NULL-default)

**Recommendation: add `premise TEXT DEFAULT ''` column to `dnd_campaigns`; do NOT fold into existing `world_notes` or `current_scene`.**

R1 confirms `dnd_campaigns` has 9 columns including `world_notes` (TEXT DEFAULT '', currently unused per its naming convention) and `current_scene` (just retired in S67 F-016 closure — write paths gone, column orphaned). Folding premise into either is muddier than additive: `world_notes` semantics are not specified; `current_scene` is now-vestigial post-S67. New column makes the field's purpose explicit and keeps the §76 audit clean.

**Schema delta:** `ALTER TABLE dnd_campaigns ADD COLUMN premise TEXT DEFAULT '';`. Additive; existing rows unaffected. Migration runs at engine init alongside the existing fk_cascade_init and wal_init blocks.

**Reasoning:** Operator authors premise once at `/bootstrap`; bot reads it for every card directive call; main prompt reads it for standing campaign framing (§1.E + §11.6). Explicit column makes the read path clean and the §76 audit deterministic.

---

### §1.B — `/bootstrap` is a NEW slash command, runs AFTER `/newcampaign`, NOT folded in

**Recommendation: ship `/bootstrap` as a separate DM-only slash command. Prerequisite check: active campaign exists for this guild. Operator runs `/newcampaign` first; then `/bootstrap`.**

Folding bootstrap into `/newcampaign` would tightly couple campaign creation with a multi-card authoring session. Operators may want a campaign row without immediately bootstrapping (e.g., importing skeleton from a prior project, or hand-authoring). Separate command preserves opt-in semantics.

**Slash surface:**
- `/bootstrap` — start a bootstrap session for the active campaign. Optional `premise` argument; if omitted, opens a modal-style prompt (§1.C decides exact mechanism).
- `/bootstrap accept` — approve current card, write to canonical table + skeleton.md, advance to next card.
- `/bootstrap skip` — drop current card, advance to next.
- `/bootstrap reroll` — soft-reroll current card with the same premise + prior-approved context (§11.4).
- `/bootstrap manual <field>:<value>` — operator override on specific field of the current card (§11.9).
- `/bootstrap end` — terminate session early (writes session_completed log, clears in-memory state).
- `/bootstrap status` — show current card sequence + approved-so-far count (operator visibility).

**Reasoning:** R1 confirms `/newcampaign` writes a minimal row and returns immediately. `/bootstrap` becomes the authoring-session driver, called as the next operator step. Idempotency on re-run is §11.5.

---

### §1.C — Premise input: single-shot prompt at `/bootstrap` invocation, NOT multi-card clarification

**Recommendation: single-shot. Operator passes premise as the slash command's `premise` argument (up to 1000 chars).**

Per sketch §11.1 lean. Multi-card clarification ("what's the antagonist energy?" / "what's the genre?") adds 2-3 turns of friction before bot does productive work. Option-3 constraint says operator will provide 2-3 sentences once; more compounds.

**Slash signature:**
```python
@app_commands.describe(
    premise='2-3 sentences describing the campaign premise '
            '(genre, setting, character role, what\'s pressuring the world).'
)
async def bootstrap(interaction, premise: str):
```

If `premise` is empty/whitespace, command errors with usage hint: "Premise required. Example: `/bootstrap premise:\"High-fantasy elven coastal town, my character is a bard, festival of dawn approaches.\"`"

**Reasoning:** Slash arg is the lightest-weight path; Discord Modal would also work but adds complexity. Per HIGH-confidence sketch §11.1 lean.

---

### §1.D — Card sequence order: FACTIONS → NPCs → QUESTS → ACTS → LOCATIONS

**Recommendation: factions first, then dispatcher NPCs, then quests anchored to NPCs, then quest acts under each quest, then locations.**

Per sketch §11.2 lean. Factions establish offscreen pressure (the world's stakes); NPCs voice those pressures; quests express NPC asks; acts decompose quests; locations anchor everything spatially.

If operator skips faction cards, the bot can still produce useful canon (NPCs + quests work without explicit factions). But faction-first surfaces the load-bearing question — "what's pressuring the world?" — before operator commits to lower-level details.

**Card counts (per sketch §11.3):**
| Card type | Count proposed | Tunable post-playtest |
|---|---|---|
| Faction | 1-2 | per-campaign threshold |
| Dispatcher NPC | 2-3 | |
| Quest | 3 | one per dispatcher typical |
| Quest Act | 2-4 per quest | per-quest |
| Location | 2-3 | beyond starting location |

Total cards per bootstrap session: 8-14. Operator can skip any to shorten.

**Reasoning:** Mirror the §17/§59 dependency graph downstream. Causality Engine reads factions; Quest Layer reads dispatcher NPCs + factions; Composition Layer reads quests + acts; Scene Lifecycle reads locations. Building canon in dependency order keeps FK relationships valid as each element approves.

---

### §1.E — Premise renders in main prompt at low-tactical-band placement

**Recommendation: add `compute_premise_directive(campaign) → (body, signals)` as §59 sibling #17. Renders premise at low-tactical-band, BELOW SETTING & TONE but ABOVE the main directive stack.**

Per sketch §11.6 lean. Premise is standing campaign-level framing (not turn-specific pressure); rendering at low-tactical-band makes it consistent context every narration call.

**Block shape:**
```
=== CAMPAIGN PREMISE ===
{premise_text}
```

Empty when premise is NULL/empty. Always-fire telemetry: `premise_directive: campaign=N chars=N fired=0|1`.

**§76 audit (per §7 below):** Premise is operator-written (3/4 max; not LLM-writable). Safe at 3/4.

**Reasoning:** Without main-prompt rendering, premise becomes dead state — it'd only be read by the bot directive call, never reach narration. Operator wrote it to frame the campaign; it should frame every narration call.

---

### §1.F — `compute_bootstrap_card_directive` is §59 sibling #18 (engine-deterministic predicate; LLM call for content)

**Recommendation: pure function over `(bootstrap_state, card_type, campaign_data) → (proposal | None, signals)`. The DETERMINISTIC part decides which card type fires next (sequence pointer) and assembles the LLM prompt. The LLM call generates the proposal content.**

Inputs:
- `bootstrap_state`: `{premise, sequence_pointer, prior_approved_elements: list[dict]}`
- `card_type`: enum from `{faction, npc_dispatcher, quest, quest_act, location}`
- `campaign_data`: campaign id, party (from `dnd_companions`), starting location if set

Output:
- `proposal`: `{card_type, element_name, fields: dict, justification: str}` — the proposed element draft
- `signals`: `{card_type, sequence_index, approved_count, remaining_in_sequence, llm_latency_ms}` for telemetry

LLM call: small targeted prompt (~2-3k chars per R4) to extraction-tier model (route='extraction' per cloud_router). Output: JSON shape matching `proposal` schema. Deterministic validator confirms required fields present + within bounds before card-post.

Architectural shape: same as `consequence_extractor` / `npc_extractor` / `mechanical_hints` — bounded structured-output LLM call, deterministic post-validator, suggestion-only (the §1b validated-suggester pattern, sixth project instance per §1.K).

**Reasoning:** §1a clean — bot proposes, operator approves via slash, engine writes via existing single-writers. No LLM-decided binding state changes. §1b sixth project instance.

---

### §1.G — Skeleton.md writer: new single-writer `skeleton_md_append_element`

**Recommendation: new function `skeleton_md_append_element(campaign_id, element_type, element_data) → bool`. Single-writer for skeleton.md file appends.**

Element types: `faction`, `npc`, `quest`, `quest_act`, `location`. Per-type renderer translates structured `element_data` dict into the markdown shape `parse_skeleton_file` expects (R2 evidence).

Idempotent on `(element_type, element_name)`: re-appending an existing element updates the prose under the H3 entry in place rather than duplicating. **NEW H2 section gets created if not present in file** (e.g., bootstrap's first faction card creates the `## Factions` section).

**Soft-fail:** writer errors must not block bot's session state — the canonical table write (e.g., `npc_upsert`) is the authoritative side; skeleton.md append is the secondary side-effect. If file write fails, log `skeleton_md_append: campaign=N element_type=X error=...` and continue.

**§17 compliance:** first-of-its-kind writer for that file path. Not a sibling of an existing writer (skeleton.md was previously hand-authored, no engine writer existed). §17 narrow-exception not invoked because there is no prior writer to be a parallel to.

**Reasoning:** The operator never opens skeleton.md (load-bearing sketch §1). Bot must write the file directly. Single-writer keeps the §17 invariant clean.

---

### §1.H — Faction storage at v0: skeleton.md ONLY (no `dnd_factions` table)

**Recommendation: v0 factions live in skeleton.md `## Factions` section only. The bot creates the section + H3 entries via `skeleton_md_append_element`. NO `dnd_factions` table at v0.**

R6 evidence: `dnd_factions` table does NOT exist. The skeleton parser produces `result['factions']` but `apply_skeleton` never persists them. Quest Layer v0 §12.2 explicitly filed faction modeling as v1.x.

**Two paths considered:**
- (a) Skeleton-only at v0 — bot writes faction H3 entries to skeleton.md; downstream architecture reads via `parse_skeleton_file` until Causality Engine v0 (S69) introduces `dnd_factions`.
- (b) Bootstrap ships `dnd_factions` table as v0 prerequisite — adds schema work to N-10's scope; expands bootstrap from authoring tool into a schema-introducer.

**Lean (a).** Schema introduction is a separate concern; v0 should ship the authoring surface, not the substrate. Causality Engine v0 (S69) will introduce `dnd_factions` and migrate from skeleton-parsed factions into DB rows at that ship.

**Reasoning:** Keeps v0 scope tight (no schema migration risk). Skeleton.md is already a parsed-and-loaded surface; downstream architecture can read factions from `parse_skeleton_file`'s `result['factions']` list during the v0-to-S69 gap.

---

### §1.I — NPC pronouns at v0: folded into `description` prose (deferred to N-4)

**Recommendation: v0 NPC card produces description prose that includes pronoun information naturally ("She watches the road..." or "they-them pronouns"). NO new `dnd_npcs.pronouns` column at v0.**

R6 evidence: `dnd_npcs.pronouns` column does NOT exist. S67 §76 audit confirmed dnd_npcs schema has no pronoun field. N-4 (S68 candidate) ships the column + anti-drift rail.

Per sketch §4: "this is the N-4 surface; pronouns get authored at bootstrap, anti-drift rail in N-4 ships separately."

**Bot output discipline:** NPC card prose must include at least one pronoun reference in the first sentence so N-4's later extraction pass can recover the canonical pronouns when the column ships.

**Reasoning:** Avoids schema coupling between N-10 and N-4. N-4 ships the column and a one-shot migration extracts pronouns from existing NPC descriptions. N-10 just needs to produce description prose that contains the pronoun signal.

---

### §1.J — Idempotency on re-run: error at v0 (no expansion mode)

**Recommendation: `/bootstrap` on a bootstrap-complete campaign errors with usage hint. Expansion mode is v1.x candidate.**

Per sketch §11.5 lean. Operator-approved canon should not be silently overwritten; full re-run is dangerous. Expansion mode (add new elements without touching prior canon) is a real authoring axis but v0 ships the cleanest first-time-bootstrap shape.

**Detection:** A campaign is "bootstrap-complete" if either:
- `dnd_campaigns.premise IS NOT NULL AND premise != ''` AND there are any `skeleton_origin=1` rows in `dnd_npcs`, `dnd_quests`, `dnd_locations`, or `dnd_quest_acts` for this campaign.
- OR `bootstrap_session_completed:` log entry exists for this campaign.

Either signal trips. Operator sees: "Campaign already bootstrapped (premise set, N skeleton-origin elements exist). Re-bootstrap is not supported at v0; file v1.x expansion-mode candidate after live signal."

**Reasoning:** Maximum safety at v0; observed-friction signal informs whether expansion mode earns a v1.x ship.

---

### §1.K — §1b sixth project instance

**Recommendation: Canon Bootstrap Bot v0 anchors the §1b validated-suggester pattern's sixth project instance.**

Architectural shape:
- **Bot proposes via `#dm-aside`** — `compute_bootstrap_card_directive` emits, dispatch posts card. No bot-emitted Avrae command. No engine state mutation at this step.
- **Deterministic validator** — Python post-processes the LLM JSON output: required fields present? Names canonicalized? FKs (offer_npc_id, parent_location_id, quest_id) resolve against approved-so-far context?
- **DM approves by slash** — `/bootstrap accept` triggers the canonical-table write + skeleton.md append.
- **Engine executes** — existing `npc_upsert` / `quest_add` / `quest_act_upsert` / `location_upsert` write per §17.

Joins:
1. Track 6 #5.1 SRD suggester (S26) — first instance.
2. NPC State-Sync suggester (S41 post-pivot) — second instance.
3. Quest Layer v0.1 offer suggester (S57 post-patch, Reading-2 canonical-slash-only) — third instance.
4. Composition Layer v0 quest-act suggester (S60) — fourth instance.
5. (Reserved per §1b running-list footnote — Track 6 v0.x SRD card revival if it lands.)
6. **Canon Bootstrap Bot v0 — this spec — sixth instance.**

**Deterministic-only validator throughout.** Cosine-similarity precedent (rejected at Quest Layer v0.1 S57) applies — keep gates deterministic. The LLM call output is validated by required-field presence + FK existence checks + bounded-string-length, not by similarity scoring.

**Reasoning:** Pattern is mature at five prior instances. Sixth instance anchors cleanly with no calibration-bound auxiliary. Confidence HIGH.

---

### §1.L — Bot directive: extraction-tier LLM call, NOT main-narration model

**Recommendation: `compute_bootstrap_card_directive` calls the cloud_router with `task_type='extraction'` (per existing precedent in mechanical_hints, consequence_extractor, npc_extractor).**

Extraction tier routes to a fast model (likely Cerebras qwen-3-235b per cloud_router's PROVIDERS config). The bot directive's job is to produce structured JSON, not narrative prose; extraction-tier is the right routing.

**Why not main-narration model:** main-narration tier is tuned for atmospheric continuity (S43 §77 doctrine). Bootstrap cards are structured-data output, not narrative — different optimization target. Extraction-tier is faster + cheaper + more compliant on JSON-shape constraints.

**Reasoning:** Established pattern (Doctrine §12 advisory parser; §1b validated suggesters). No deviation from existing tier routing.

---

## §2. Problem statement

The Virgil project's downstream motion-system architecture (Quest Layer v0.1, Composition Layer v0, Scene Lifecycle v1, Causality Engine v0 [pending], NPC commitment rails N-3/N-4 [pending]) reads from authored canon — NPCs in `dnd_npcs`, quests in `dnd_quests`, quest acts in `dnd_quest_acts`, locations in `dnd_locations`, factions in skeleton.md. **The architecture has nothing to bite into without that canon existing.**

Three constraints make this load-bearing post-Tier-1:

1. **Option-3 authoring constraint.** Operator has confirmed they will NOT hand-write skeleton.md or hand-create NPCs/quests/locations via slash commands. Without an authoring tool, skeleton.md stays empty per new campaign, downstream architecture has no inputs, and the project is structurally hollow.

2. **S68 + S69 gate on N-10.** S68 (NPC commitment rails — N-3 pricing math + N-4 pronoun lock) requires NPCs to commit against; S69 (Causality Engine v0) requires factions to tick. Both ships are scheduled but neither has canon to operate on until N-10 ships.

3. **Tier 1 arc closed.** S65 → S65.1 → S66 → S67 closed six P0 fixes and tightened the structural floor. The next priority is **making the project playable**, which means closing the load-bearing canon-volume gap.

The sketch (`planner-scratch/canon_bootstrap_bot_v0_sketch.md`) lays out the bootstrap-bot architectural shape: operator provides 2-3 sentence premise; bot proposes structured canon elements via `#dm-aside` cards; operator approves via slash; engine writes via existing single-writers. This spec walks the sketch through Phase 1 recon + decision-locking surface.

---

## §3. Bootstrap flow shape

### §3.1 — Trigger

Operator runs `/newcampaign name:"X" tone:"Y"` (R1 — existing path, unchanged). Campaign row inserts at `status='active'`.

Operator runs `/bootstrap premise:"2-3 sentences..."`. Handler:
1. Validates active campaign exists for guild.
2. Validates premise non-empty.
3. Validates campaign is NOT bootstrap-complete (per §1.J).
4. Writes premise to `dnd_campaigns.premise` via `update_campaign_premise(campaign_id, premise)` (new single-writer, §17 narrow).
5. Initializes in-memory `_bootstrap_session[campaign_id] = BootstrapState(...)`.
6. Triggers first card proposal (faction card per §1.D sequence).

### §3.2 — In-memory session state

```python
@dataclass
class BootstrapState:
    campaign_id: int
    premise: str
    sequence_pointer: int             # index into the card sequence
    sequence_plan: list[str]          # ['faction', 'faction', 'npc_dispatcher', ...]
    approved_elements: list[dict]     # what's been written so far (per-card snapshot)
    current_proposal: dict | None     # the pending proposal awaiting operator action
    rerolls_for_current: int          # count of reroll uses on this card
    started_at: str                   # ISO timestamp
```

Stored in process-local `_bootstrap_session: dict[int, BootstrapState]`. Cleared on `/bootstrap end`, `/bootstrap accept` of the final card, or process restart. NOT persisted to DB (per sketch §2 "not new ChromaDB collection ... no LLM classification feeding binding state transitions").

### §3.3 — Card cycle (per card)

1. **Propose.** `compute_bootstrap_card_directive(state, card_type, campaign_data)` invokes the LLM, validates output, populates `state.current_proposal`.
2. **Dispatch.** `_post_dm_aside(guild, _format_bootstrap_card(state.current_proposal))` posts the card.
3. **Wait.** Operator inspects, runs one of:
   - `/bootstrap accept` → write to canonical table + skeleton.md, advance sequence, propose next card.
   - `/bootstrap skip` → drop proposal, advance sequence, propose next card.
   - `/bootstrap reroll` → re-invoke LLM with prior-rejected hint; increment `rerolls_for_current`. NO MAX at v0 per §11.4 (soft-reroll).
   - `/bootstrap manual <field>:<value>` → override field in `state.current_proposal`, re-post card; operator can chain multiple overrides before `/bootstrap accept`.

### §3.4 — Session completion

When `sequence_pointer == len(sequence_plan)`, session is complete:
- Engine writes `bootstrap_session_completed: campaign=N elements_approved=N elements_skipped=N session_duration_ms=N` log line.
- Clears `_bootstrap_session[campaign_id]`.
- Operator sees: "Bootstrap complete. {N} elements written to skeleton.md and canonical tables. Run `/play` to begin the campaign."

Operator can also run `/bootstrap end` mid-session to terminate early.

---

## §4. Card directive shape (§59 sibling #18)

`compute_bootstrap_card_directive(bootstrap_state, card_type, campaign_data) → (proposal | None, signals)`.

### §4.1 — LLM call shape

Prompt assembly (deterministic, Python-side):
```
=== CAMPAIGN PREMISE ===
{premise}

=== APPROVED CANON SO FAR ===
Factions: {comma-separated names, or "(none)"}
NPCs: {comma-separated "name (role)" entries, or "(none)"}
Quests: {comma-separated titles with offer-NPC, or "(none)"}
Acts: {per-quest "Quest X — Act N: title" entries, or "(none)"}
Locations: {comma-separated names, or "(none)"}

=== CORPUS SIGNAL ===
{static signal substrate per card type — see §5 below}

=== CARD TYPE ===
{card_type}

=== TASK ===
Propose ONE {card_type} element consistent with the premise and prior-approved canon.
Output JSON matching the schema:
{schema_block per card_type — see §5}

=== HARD CONSTRAINTS ===
- Element name must NOT duplicate any prior-approved name (case-insensitive).
- All FK references must match prior-approved canon (e.g., quest's offer_npc must be a prior-approved NPC).
- Fields are operator-readable; use plain prose, no Markdown decoration inside field values.
- Justification field: ONE sentence explaining how this element fits the premise.
```

LLM call: `cloud_router.route(messages=[...], task_type='extraction', system_prompt=BOOTSTRAP_SYSTEM_PROMPT)`. Timeout 10s per card. Soft-fail: on LLM error or schema-validation failure, post `[BOOTSTRAP CARD ERROR]` to `#dm-aside` with retry guidance; do NOT advance sequence pointer.

### §4.2 — Card format (per `#dm-aside` post)

Per R3 — plain Discord message, ~500-1500 chars typical, ≤2000 char hard cap.

```
**[BOOTSTRAP — {card_type} CARD {sequence_index}/{total}]**
Proposed: **{element_name}**

{per-card-type field summary — see §5 below}

_Justification:_ {one-sentence explanation}

— `/bootstrap accept` to write this element + advance
— `/bootstrap skip` to drop it + advance
— `/bootstrap reroll` to regenerate with same premise + context
— `/bootstrap manual <field>:<value>` to override a field then accept
```

### §4.3 — Signals dict

```python
signals = {
    'card_type': str,
    'sequence_index': int,
    'sequence_total': int,
    'approved_count': int,
    'remaining_in_sequence': int,
    'llm_latency_ms': int,
    'fired': bool,           # True iff proposal generated; False on LLM error
    'reroll_count': int,     # rerolls used on this card so far
}
```

Always-fire telemetry: `bootstrap_card_directive: campaign=N card_type=X sequence_index=N fired=0|1 chars=N latency_ms=N`.

---

## §5. Per-card-type field requirements

### §5.1 — Faction card

**Fields:**
- `name` (str, required, ≤80 chars) — canonical name.
- `goal` (str, required, one sentence ≤200 chars) — what the faction wants.
- `pressure_shape` (str, required, ≤120 chars) — what's pushing them (urgency / desire / fear).
- `engagement_signals` (str, required, ≤200 chars) — what causes the faction to act/escalate.

**Storage at v0 (per §1.H):** skeleton.md `## Factions` H2 section, `### {name} ({type-hint})` H3 entry, prose body containing goal + pressure_shape + engagement_signals.

**Corpus signal substrate (per R5):**
- TM (Time-Mention findings): "festival of dawn approaches" / "by week's end" — temporal pressure framings inform `pressure_shape`.
- EC (Encounter Cadence findings): NPC-hostility triggers as faction-action expressions.
- CC (Compression Cadence findings): scene-departure cues correlated with faction-state shifts.

**Card example:**
```
**[BOOTSTRAP — FACTION CARD 1/8]**
Proposed: **The Stonehold Merchants' Guild**

Goal: Preserve the trade road from Stoneforge to Redhaven before the autumn harvest tariffs hit.
Pressure: Bandit raids climbing in frequency; one more attack and Redhaven mayor revokes the guild charter.
Engagement signals: Caravan raids; merchant defections; Stonehold scout reports.

_Justification:_ The trade-road premise needs a stake-bearing faction whose pressures generate quest hooks.

— `/bootstrap accept` to write + advance
— `/bootstrap skip` / `/bootstrap reroll` / `/bootstrap manual <field>:<value>`
```

### §5.2 — Dispatcher NPC card

**Fields:**
- `canonical_name` (str, required, ≤80 chars).
- `role` (str, required, ≤60 chars) — concise role label (e.g., "merchant guild master", "village herald").
- `pronouns` (str, required, ≤30 chars) — folded into description prose per §1.I (e.g., "she/her").
- `description` (str, required, ≤500 chars) — appearance + voice + relevant background; MUST include pronouns in first sentence per §1.I.
- `location_name` (str, optional, ≤80 chars) — where the party meets them; if specified, must match a prior-approved location OR is held as a hint for later location authoring.
- `associated_faction_name` (str, optional, ≤80 chars) — must match a prior-approved faction OR null.

**Storage at v0:**
- Canonical: `npc_upsert(campaign_id, name=canonical_name, role=role, description=description, skeleton_origin=True)`. Pronouns ride in `description` prose until N-4 ships the column.
- skeleton.md `## Primary NPCs` H2 section, `### {canonical_name} ({role}, {location_hint})` H3 entry per R2 parser format.
- `location_name` matches a `dnd_locations` row via `canonicalize_location_name`; on no-match, stored in description as `(seen at: {location_name})` and resolved later when location card approves.
- `associated_faction_name` annotated in description as `Faction: {name}` (no FK at v0 per §1.H).

**Corpus signal substrate (per R5):**
- LR (Loot/Reward findings): NPC-voice routing 36.8% — NPCs voice quest offers + favor/gratitude. Bot prompts informed by "this NPC will likely be a quest voicer."

### §5.3 — Quest card

**Fields:**
- `title` (str, required, ≤100 chars).
- `summary` (str, required, ≤500 chars) — what the quest is about, in DM-prose.
- `offer_npc_name` (str, required, ≤80 chars) — must match a prior-approved NPC name.
- `reward_summary` (str, required, ≤200 chars) — structured per Quest Layer v0 §7 vocabulary ("Ngp" / "<faction> reputation" / "<faction> favor" / "named item").
- `associated_faction_name` (str, optional, ≤80 chars) — must match prior-approved faction OR null.

**Storage at v0:**
- Canonical: `quest_add(campaign_id, title=title, summary=summary, given_by=offer_npc_name, reward_summary=reward_summary, skeleton_origin=1)`. Status defaults to `'offered'` (Quest Layer v0 default).
- Optional follow-up: `quest_offer(campaign_id, quest_id, offer_npc_id=resolved_npc_id)` to populate the offer_npc_id FK at write time.
- skeleton.md `## Major hooks` H2 section, `### {title}` H3 entry, prose body with summary + offer-NPC reference + reward.

**Corpus signal substrate (per R5):**
- LR (Loot/Reward findings): reward magnitude calibration — typical gp scale by quest scope (LR's per-quest distributions inform the LLM's reward magnitude choices).
- LR: NPC-voice routing — quest offers are NPC-voiced events.

### §5.4 — Quest Act card

**Fields:**
- `quest_title` (str, required, ≤100 chars) — must match a prior-approved quest title.
- `act_index` (int, required, 1-based, sequential within a quest).
- `act_title` (str, required, ≤100 chars).
- `act_description` (str, required, ≤500 chars) — what this act covers narratively.
- `transition_predicate` (dict, optional) — narrow vocabulary per Composition Layer v0 §11.7 lock: `{'scene_count_threshold': int}` and/or `{'location_name': str}`.

**Storage at v0:**
- Canonical: `quest_act_upsert(campaign_id, quest_id=resolved_quest_id, act_index, act_title, act_description, transition_predicate_json=json.dumps(transition_predicate), skeleton_origin=1)`.
- skeleton.md `## Major hooks` H2 section, under the quest's H3, `#### Acts` H4 subsection with numbered list per R2 parser format.

**Corpus signal substrate (per R5):**
- EC (Encounter Cadence findings): combat-encounter cadence per quest arc — acts often align with encounter beats.
- CC (Compression Cadence findings): scene-departure cues that mark act boundaries (per Composition Layer v0 §1.E precedent).

### §5.5 — Location card

**Fields:**
- `canonical_name` (str, required, ≤80 chars).
- `type` (str, optional, ≤60 chars) — e.g., "town", "tavern", "forest", "ruin".
- `parent_location_name` (str, optional, ≤80 chars) — for hierarchical maps (e.g., "The Stumbling Stag" parent = "Stonebridge"); must match prior-approved location OR null.
- `description` (str, required, ≤500 chars) — sensory + atmospheric prose; sets the tone-of-place.
- `starting_location` (bool, optional, default False) — if True, this is where the party begins. At most one location per bootstrap session can carry `starting_location=True`.

**Storage at v0:**
- Canonical: `location_upsert(campaign_id, name=canonical_name, type=type, parent_location_id=resolved_parent_id, description=description, skeleton_origin=True)`.
- If `starting_location=True`: `set_current_location(campaign_id, location_id)` fires alongside `location_upsert`.
- skeleton.md `## Key locations` H2 section, `### {canonical_name} ({type})` H3 entry per R2 parser format.

**Corpus signal substrate (per R5):**
- TM (Time-Mention findings): time-of-day setting flavor ("amber lanterns of evening" / "morning mist") — informs description-prose tonal choices.

---

## §6. Recon findings

Six items, evidence-backed against the live codebase (May 14, 2026).

---

### R1. `/newcampaign` flow audit — minimal row insert, no skeleton.md path attached

**Evidence:**
- Slash command: `discord_dnd_bot.py:4316–4331` (`@bot.tree.command(name='newcampaign', ...)`).
- Handler signature: `async def newcampaign(interaction, name: str, tone: str = '')`. DM-only gate (`is_dm_or_creator`).
- Engine writer: `dnd_engine.py:1051–1066` (`create_campaign(guild_id, name, tone, creator_user_id)`).

**Behavior:**
1. Soft-retires any prior active campaign for this guild (`UPDATE dnd_campaigns SET status='inactive' WHERE status='active' AND guild_id=?`).
2. INSERTs new row with: `name`, `created_at` (ISO timestamp), `status='active'`, `guild_id`, `tone`, `created_by_user_id`.
3. Returns `campaign_id` (lastrowid).
4. Slash response: confirmation message with binding instructions ("Players: use `/bindchar` to join.").

**Schema (live DB):**
```sql
CREATE TABLE dnd_campaigns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    created_at TEXT,
    status TEXT DEFAULT 'active',
    world_notes TEXT DEFAULT '',
    current_scene TEXT DEFAULT '',     -- orphaned post-S67 F-016 closure
    guild_id TEXT DEFAULT '',
    tone TEXT DEFAULT '',
    created_by_user_id TEXT DEFAULT ''
);
```

**Critical finding:** **No `premise` column. No skeleton.md path attached.** Skeleton lives at `/home/jordaneal/scripts/campaigns/{campaign_id}/skeleton.md` — file path is derived from `campaign_id`, not stored anywhere. Per §1.A: add `premise TEXT DEFAULT ''` column.

**Integration shape for `/bootstrap`:**
- Separate slash command, runs AFTER `/newcampaign`.
- Prerequisite: `get_active_campaign(guild_id)` returns non-None.
- Initial state: premise empty, no skeleton_origin elements present. Idempotency-on-rerun gate per §1.J keys on these two signals.

**No HALT.** `/newcampaign` flow is clean and additive-extension-friendly.

---

### R2. Skeleton.md format — semi-strict parser, additive H2 sections, strict H3 placement

**Evidence:**
- Parser: `skeleton_loader.py:194–539` (`_parse_skeleton_text` + `parse_skeleton_file`).
- Section vocabulary (skeleton_loader.py:115–127):
  - NPC sections: `{"primary npcs", "npcs", "characters"}`
  - Location sections: `{"key locations", "locations", "places"}`
  - Factions: `{"factions"}` (exact)
  - Player capabilities: `{"player capabilities", "character capabilities", "capabilities"}`
  - Starting time: `{"starting time", "start time", "starting clock"}`
  - Central conflict: `{"central conflict"}` (exact)
  - Major hooks: `{"major hooks", "hooks"}`

**Strictness profile:**
- **H1:** `# Campaign: <name>` (prefix optional but recommended).
- **H2:** Must be from the recognized vocabulary OR captured in `unknown_sections` list (additive — non-fatal).
- **H3 inside section:** Format `### {name} ({kind}, {parent_hint})` for NPCs/locations/factions. **STRICT: H3 outside a recognized section RAISES `SkeletonParseError`.**
- **H4 "Acts":** Inside a quest's H3 under `## Major hooks`, enables Composition Layer v0 quest-act parsing (numbered "1. Title" entries).
- **Body text:** Free-form prose under each H3 entry — permissive.

**Reference template (campaign 17, `/home/jordaneal/scripts/campaigns/17/skeleton.md`):**
```markdown
# Campaign: Stoneforge Guild

## Central conflict
A lone rogue named Donovan Ruby has joined the Stoneforge Guild...

## Major hooks
- Escort the merchant caravan from Stonebridge to Redhaven by dawn
- Investigate the goblin-ravaged farmstead on the road
- Survey the lost mine near the Crystal Caves

## Primary NPCs
### Eldrin Stormbow (ranger, Stonebridge)
A half-elf ranger of the Stoneforge Guild...

## Key locations
### Stonebridge (town)
A market town spanning the River Wynd...

## Factions
### Stoneforge Guild (adventuring guild)
The guild that posts quests on the notice board...
```

**Finding:** Parser shape is fully compatible with bot output. Bot must emit:
- One H1 with `Campaign: ` prefix.
- H2 sections from the recognized vocabulary (or accept that unknown H2s land in `unknown_sections`).
- H3 entries with `### Name (kind, parent_hint)` shape inside known sections.
- Free-form prose under each H3.
- For quest-with-acts: H3 quest title under `## Major hooks`, then `#### Acts` subsection with numbered list.

**No HALT.** Parser is bot-output-friendly. The strictness is appropriate guardrails (H3 outside section is structural malformation; bot should never produce this).

---

### R3. `#dm-aside` card format — plain text, ≤2000 chars, three precedent shapes

**Evidence:**
- Posting helper: `discord_dnd_bot.py:418–431` (`_post_dm_aside(guild, text)`). Uses `ch.send(text)` — plain Discord message, NOT an embed. **Hard limit: 2000 chars per Discord message API.**
- Precedent card formats (live, May 14, 2026):

**Pattern 1: Quest Layer v0.1 offer suggester** (`_format_quest_offer_card`, line 536-554):
```
**[QUEST OFFER PROPOSED]**
NPC voicer: **Eldrin Stormbow** (at current location)
Quest #3: **Investigate the goblin-ravaged farmstead**
_Summary:_ Patrol the farmstead and report what they find.
Reward: 50gp + Guild reputation

_Run `/quest accept 3` when the party commits in-character ..._
```
Typical size: ~400 chars.

**Pattern 2: Composition Layer v0 act suggester** (`_format_quest_act_card`, line 680-689):
```
**[QUEST ACT TRANSITION PROPOSED]**
Quest #3
Current: **Act 1 — Approach the farmstead**
Proposed: **Act 2 — Search the burned barn**
_Next act:_ Detailed clues hidden in the wreckage...
Predicate reason: scene_count_threshold reached (4 scenes)

_Run `/quest act advance 3` to confirm ..._
```
Typical size: ~350 chars.

**Pattern 3: Quest delivery reward dispatch** (line 5841+):
```
**[REWARD READY]** Quest #3 delivered: **Investigate the goblin-ravaged farmstead**.
Reward: 50gp + Guild reputation

**Auto-added to party stash:**
+ gp ×50 → party stash (inserted)

Suggested narration: "The quest has been seen through to its end..."
```
Typical size: ~300 chars.

**Bootstrap card budget:** Target 500-1500 chars per card. Comfortably within the 2000-char limit. Card shape per §4.2.

**No HALT.** Format pattern is well-established; bootstrap cards inherit the shape cleanly.

---

### R4. Prompt-size baseline at bootstrap time — off-play, generous budget

**Main-play prompt baseline (per S67 audit, post-F-016 closure):** ~25-26k chars mean exploration-turn prompt. Heavy: knowledge guidance + skeleton block + scene state + 15+ directives.

**Bootstrap directive call prompt — projected:**

| Component | Size estimate |
|---|---|
| Premise context | ~300-500 chars (operator's 2-3 sentences with framing) |
| Prior-approved elements summary | ~50 chars/element × max ~14 elements at end of session = ~700 chars |
| Card-type schema spec | ~400 chars |
| Corpus signal substrate (constants per card type) | ~300-500 chars |
| Hard constraints + format instructions | ~600 chars |
| System prompt (extraction-tier framing) | ~400 chars |
| **Total per bootstrap card directive call** | **~2,700-3,100 chars** |

**Comparison:** ~12% of main-play prompt size. Cheap.

**Why this matters:**
1. Bootstrap fires OFF-PLAY (no LLM-emit binding state; no `_dm_respond_and_post` interaction). The directive's prompt budget is independent of main-play budget — no pressure to optimize.
2. Each card directive call is a SEPARATE LLM round-trip (`task_type='extraction'` per §1.L). 8-14 calls per bootstrap session typical.
3. Per-card latency: ~500-1500ms (extraction-tier router; per existing `consequence_extractor` / `npc_extractor` patterns). Total bootstrap session: ~10-25 seconds of LLM time spread across operator approval cadence.

**Finding:** Prompt-size is non-binding for v0. No optimization pressure.

---

### R5. Corpus findings signal mapping — fixed-constant prompt substrate per card type

**Mapping table (corpus findings → card types):**

| Card type | Finding source | Signal use |
|---|---|---|
| **Faction** | TM (Time-Mention) | Temporal-pressure framings inform `pressure_shape` ("by week's end", "festival approaches"). |
| **Faction** | EC (Encounter Cadence) | NPC-hostility triggers as faction-action manifestations (factions ESCALATE via combat events). |
| **Faction** | CC (Compression Cadence) | Scene-departure cues correlated with faction-state shifts (factions move the world between scenes). |
| **Dispatcher NPC** | LR (Loot/Reward) | NPC-voice routing pattern (36.8%) — NPCs are the primary quest-offer voicers. Informs NPC card's "this NPC will be a quest voicer" framing. |
| **Quest** | LR (Loot/Reward) | Reward magnitude distributions by quest scope. Informs `reward_summary` calibration ("typical patrol quest: 25-50gp + reputation token"). |
| **Quest** | LR (Loot/Reward) | Rewards-after-tension pacing. Informs quest-summary framing ("the quest's payoff arrives after risk"). |
| **Quest Act** | EC (Encounter Cadence) | Combat-cadence per quest arc — acts often align with encounter beats. Informs act decomposition into combat-bearing vs. non-combat scenes. |
| **Quest Act** | CC (Compression Cadence) | Scene-departure cues that mark act boundaries (per Composition Layer v0 §1.E precedent — act-boundary ≈ compression-boundary). |
| **Location** | TM (Time-Mention) | Time-of-day setting flavor ("amber lanterns of evening", "morning mist"). Informs description-prose tonal choices. |

**Implementation shape:**
- A single Python module `bootstrap_corpus_signal.py` exports fixed-string constants:
  - `FACTION_SIGNAL_TM = "..."` (300-500 chars distilled from `track5_findings_time_mention.md`)
  - `FACTION_SIGNAL_EC = "..."` (similar)
  - `FACTION_SIGNAL_CC = "..."` 
  - `NPC_SIGNAL_LR = "..."`
  - `QUEST_SIGNAL_LR = "..."`
  - `QUEST_ACT_SIGNAL_EC = "..."`
  - `QUEST_ACT_SIGNAL_CC = "..."`
  - `LOCATION_SIGNAL_TM = "..."`
- `compute_bootstrap_card_directive` selects the appropriate signal constants for the card type and concatenates them into the LLM prompt's `=== CORPUS SIGNAL ===` block.

**NO LIVE CORPUS PULL at v0.** No chroma query; no findings-doc parse at runtime. Constants are extracted ONCE at module-load time from the findings markdown. Implementation phase (Session 3) hand-curates the constant strings from the findings docs.

**Finding:** Corpus integration is prompt-prelude only at v0. Cheap and deterministic.

---

### R6. Existing single-writers — four match, two GAPS

**Evidence (live, May 14, 2026):**

**Matches (existing single-writers accept proposed field shapes):**

1. **`npc_upsert(campaign_id, name, role='', location_id=None, description='', origin_excerpt='', skeleton_origin=False) → tuple[int, bool] | None`** (`dnd_engine.py:3884`). Accepts NPC card fields. PC-contamination guard at write boundary (per §15 invariant). `tuple[int, bool] | None` return shape required per S65.1 fix.
2. **`quest_add(campaign_id, title, summary='', priority='normal', given_by='', reward_summary='', skeleton_origin=0) → int`** (`dnd_engine.py:2854`). Accepts Quest card fields. Optional `quest_offer(campaign_id, quest_id, offer_npc_id=resolved)` follow-up for FK population.
3. **`quest_act_upsert(campaign_id, quest_id, act_index, act_title, act_description='', transition_predicate_json='{}', skeleton_origin=0) → tuple[int, bool]`** (`dnd_engine.py:3384`). Accepts Quest Act card fields. Cross-campaign validation per §16.
4. **`location_upsert(campaign_id, name, type='', parent_location_id=None, description='', origin_excerpt='', skeleton_origin=False) → int | None`** (`dnd_engine.py:4659`). Accepts Location card fields. Five-branch behavior matrix per skeleton-vs-parser write discipline.

**GAPS (contradictions with sketch §4 card field requirements):**

**GAP 1 — `dnd_factions` table DOES NOT EXIST.**
- `grep -n "CREATE TABLE.*factions\|dnd_factions\|faction_upsert" dnd_engine.py` → ZERO HITS.
- The skeleton parser parses `## Factions` H2 sections and produces `result['factions']` list, but `apply_skeleton` does NOT persist them. Quest Layer v0 §12.2 explicitly filed faction modeling as v1.x.
- Sketch §4 Faction card has structured fields (name, goal, pressure_shape, engagement_signals) with no DB target.

**Resolution (per §1.H):** v0 factions live in skeleton.md ONLY. Bot calls `skeleton_md_append_element(campaign_id, 'faction', ...)`. Causality Engine v0 (S69) introduces `dnd_factions` table and migrates from skeleton-parsed factions at that ship.

**GAP 2 — `dnd_npcs.pronouns` column DOES NOT EXIST.**
- S67 §76 audit confirmed: dnd_npcs schema has columns `{id, campaign_id, canonical_name, aliases, role, location_id, description, skeleton_origin, mention_count, origin_excerpt, first_mentioned, last_mentioned, hp_max, ac, attack_bonus, damage_dice, save_bonus, init_mod, cr_str, avrae_source}`. No pronouns / gender field.
- Sketch §4 NPC card lists `pronouns` as a separate field, acknowledging N-4 ships the column separately.

**Resolution (per §1.I):** v0 NPC card produces description prose that includes pronoun references in the first sentence ("She watches the road..." / "Their forge-stained apron..."). N-4 (S68 candidate) introduces `dnd_npcs.pronouns` column + one-shot migration pass that extracts pronouns from existing descriptions.

**No HALT for either gap.** Both are surfaced as §11 decisions with workarounds that preserve v0 scope discipline. Sketch §1 explicitly anticipated N-4 separately and framed factions as Causality Engine substrate.

---

## §7. §76 four-property latent-canon audit

New fields and surfaces introduced by v0, each scored against §76's four properties.

| Surface | LLM-writable? | Persisted? | Retrieved? | Narratively inferential? | Score | Verdict |
|---|---|---|---|---|---|---|
| `dnd_campaigns.premise` | **No** (operator-written via `/bootstrap` slash; single-writer `update_campaign_premise`) | Yes | Yes (per §1.E — rendered in main prompt at low-tactical-band) | Yes (prose-shape, framing for narration) | **3/4** | Safe — operator-authored, §17-disciplined |
| `_bootstrap_session` (in-memory dict) | Yes (LLM populates `current_proposal`) | **No** (process-local; not in DB) | No (consumed by bot directive only, never reaches main prompt) | No (structured-JSON, not prose-rendered) | **1/4** | Safe — in-memory only |
| Bot-proposed faction fields (skeleton.md only at v0) | Yes (LLM extracts) | Yes (skeleton.md file) | Yes (parsed at `apply_skeleton`; surfaced via skeleton prompt block) | Yes (faction prose feeds narration) | **3/4** | Safe — operator approves via `/bootstrap accept` gate; LLM-write is gated through `#dm-aside` + slash approval (the §1b validated-suggester pattern's deterministic gate, equivalent to §17 single-writer for LLM-writability property) |
| Bot-proposed NPC fields → `dnd_npcs` | Yes (LLM extracts) | Yes | Yes | Yes | **3/4** | Safe — same gate as above; `npc_upsert` is the §17 single writer; bot's LLM-output passes through operator approval + `npc_upsert` validators |
| Bot-proposed Quest fields → `dnd_quests` | Yes (LLM extracts) | Yes | Yes (active-quest directive renders `summary`/`reward_summary`) | Yes | **3/4** | Safe — same gate; `quest_add` + `quest_offer` are §17 single writers |
| Bot-proposed Quest Act fields → `dnd_quest_acts` | Yes (LLM extracts) | Yes | Yes (composition directive renders `act_title`/`act_description`) | Yes | **3/4** | Safe — same gate; `quest_act_upsert` is the §17 single writer |
| Bot-proposed Location fields → `dnd_locations` | Yes (LLM extracts) | Yes | Yes (location prompt block) | Yes | **3/4** | Safe — same gate; `location_upsert` is the §17 single writer |

**§17 + §1b composition note (per Doctrine §76 footnote at S41):** Each "Bot-proposed X → existing table" row is 3/4 — NOT 4/4 — because the LLM-writable property fails at the GATE level. The operator approves via `/bootstrap accept` slash before any canonical-table write happens; the existing single-writers (`npc_upsert`, `quest_add`, etc.) are the actual write surface; the LLM's output is validated by deterministic Python (required-field presence, FK existence, length caps) before reaching the writer. **This is exactly the §76 footnote case from S41: where an LLM-influenced write flows through a §17-disciplined helper, the column does not structurally become a 4/4 contamination surface.**

**Operational discipline:** Bootstrap-time LLM proposals share the same §1b validated-suggester gate as Quest Layer v0 offers + NPC State-Sync + Composition Layer act suggesters. No new §76 surface introduced. Existing §76 hygiene protects bootstrap-authored canon the same way it protects hand-authored canon.

**Verdict:** Zero new 4/4 §76 surfaces. v0 expands the AUTHORED-CANON VOLUME (which the existing §76 hygiene already protects); it does NOT expand the LLM-WRITABLE SURFACE AREA at the column level.

---

## §8. §1b sixth-instance anchoring

Per §1.K — Canon Bootstrap Bot v0 anchors as the SIXTH project instance of the §1b validated-suggester pattern.

**Architectural shape (verbatim per §1.K + §1b Doctrine):**
- Bot proposes via `#dm-aside` — `compute_bootstrap_card_directive` emits a structured proposal; `_post_dm_aside` posts the card.
- Deterministic gate confirms the proposal is safe — Python post-validates required fields + FK existence + length caps.
- DM approves by slash — `/bootstrap accept` is the canonical approval gate.
- Engine executes — existing §17-disciplined single-writers (`npc_upsert` / `quest_add` / `quest_act_upsert` / `location_upsert`) perform the canonical write.

**Joins:**

| # | Instance | Anchored in | Pattern shape |
|---|---|---|---|
| 1 | Track 6 #5.1 SRD suggester | S26 | LLM proposes monster name + confidence; SRD index validates; DM pastes `!init madd` |
| 2 | NPC State-Sync suggester | S41 post-pivot | Engine proposes 3-line block; idempotency gate; DM pastes 3 commands |
| 3 | Quest Layer v0.1 offer suggester | S57 Reading-2 patch | Predicate-gated proposal; DM `/quest accept` slash |
| 4 | Composition Layer v0 act suggester | S60 | Predicate-gated proposal; DM `/quest act advance` slash |
| 5 | (Reserved per §1b running-list footnote — for Track 6 v0.x SRD card revival if it lands.) | — | — |
| 6 | **Canon Bootstrap Bot v0** (this spec) | S68+ implementation | Premise + sequence-pointer-gated proposal; DM `/bootstrap accept` slash |

**Deterministic-only validator throughout.** Cosine-similarity precedent (rejected at Quest Layer v0.1 S57; re-confirmed at Composition Layer v0 with the "Reading-2 direct" framing) is honored: no calibration-bound auxiliary at v0. The validator is required-field + FK + length-cap checking; the operator slash is the canonical approval gate.

**Doctrinal compliance summary:**
- §1a clean: no LLM-decided binding state mutations.
- §1b sixth-instance anchor.
- §17 clean: all canonical-table writes via existing single-writers. `skeleton_md_append_element` is a new first-of-its-kind writer (no §17 narrow-exception invoked because no prior writer existed for skeleton.md).
- §59 sibling pattern: `compute_bootstrap_card_directive` is sibling #18; `compute_premise_directive` is sibling #17.
- §76 clean: zero new 4/4 surfaces (per §7 above).
- §77 N/A: bootstrap cards are operator-facing structured suggestions, not narration.

**Expected at Session 2 review:** clean §1b sixth-instance walk. Pattern mature at five prior instances. If Session 2 surfaces unexpected §1a concern, fallback shapes per Quest Layer v0 §11.12 framework (Shape B1 / B2) are available — but the architectural distance from §1a's adjudication-layer concern is clear (bot proposes structured authoring elements; operator approves before any state change; engine writes via §17-disciplined helpers).

---

## §9. Test plan sketch

Test surface for v0 implementation (Session 3):

**Engine tests (`test_canon_bootstrap_engine.py`):**
1. `update_campaign_premise` writes premise via single writer; refuses cross-campaign writes (§16).
2. `update_campaign_premise` accepts empty premise (clearing case).
3. `skeleton_md_append_element` creates `## Factions` section if missing.
4. `skeleton_md_append_element` is idempotent on (element_type, element_name) — re-append updates in place.
5. `skeleton_md_append_element` produces valid markdown — round-trip via `parse_skeleton_file` returns the element.
6. `skeleton_md_append_element` soft-fails on file-write error (doesn't raise).

**Orchestration tests (`test_bootstrap_directive.py`):**
7. `compute_bootstrap_card_directive` builds correct prompt for each card type (5 card types × prompt-content assertions).
8. Validator rejects missing required fields.
9. Validator rejects duplicate element names (case-insensitive).
10. Validator rejects FK references that don't match prior-approved canon.
11. Returns `(None, signals)` on LLM error; signals include `fired=False`.
12. Per-card-type schema enforcement: faction has goal+pressure+engagement; NPC has pronouns+description; etc.

**Integration tests (`test_bootstrap_integration.py`):**
13. Full bootstrap flow from `/bootstrap premise:"..."` through 8-card sequence with all `/bootstrap accept`. Final state: skeleton.md populated; canonical tables have skeleton_origin=1 rows; `bootstrap_session_completed:` log fires.
14. `/bootstrap skip` advances sequence without writing.
15. `/bootstrap reroll` re-invokes LLM with prior-rejected hint; sequence pointer unchanged.
16. `/bootstrap manual name:"Eldrin"` overrides field; subsequent `/bootstrap accept` writes overridden value.
17. `/bootstrap end` mid-session clears state; partial canon persists.
18. Idempotency-on-rerun: second `/bootstrap` on bootstrap-complete campaign errors with helpful message.
19. Round-trip: after bootstrap, `parse_skeleton_file(campaign_id)` returns all approved elements correctly structured.

**Regression sweep:** existing test_*.py suite passes after `dnd_campaigns.premise` schema extension (additive; no existing-row migration).

---

## §10. Live-verify scenarios

Six scenarios for post-implementation Discord live verify (deferred to operator).

1. **Fresh campaign bootstrap — happy path.**
   ```
   /newcampaign name:"The Hollow Crown" tone:"grimdark frontier"
   /bootstrap premise:"Grimdark frontier mining town, hexcrawl, the mine collapsed and something climbed out."
   ```
   Expected: 8-14 cards proposed in sequence (factions → NPCs → quests → acts → locations); operator approves each; final `bootstrap_session_completed:` log fires; `/play` opens a scene anchored on the approved canon.

2. **Bootstrap with skip + reroll mix.**
   Operator approves first faction card, skips second faction card, rerolls first NPC card twice before accepting. Expected: sequence advances correctly; rerolls don't advance sequence; skipped element not written; final state reflects accepted-only canon.

3. **Manual field override.**
   On NPC card, operator runs `/bootstrap manual canonical_name:"Eldrin Stormbow"`. Expected: card re-posts with the overridden name; subsequent `/bootstrap accept` writes "Eldrin Stormbow" to `dnd_npcs.canonical_name`.

4. **Empty premise error.**
   Operator runs `/bootstrap` with no premise argument. Expected: helpful usage hint; no state change.

5. **Idempotency on re-bootstrap.**
   Operator completes a bootstrap session, then runs `/bootstrap premise:"different premise"` on the same campaign. Expected: error message with bootstrap-complete signals (premise set + N skeleton_origin elements); no state change.

6. **`/bootstrap end` mid-session.**
   Operator approves 3 cards, then runs `/bootstrap end`. Expected: session closes; partial canon persists; `bootstrap_session_completed: elements_approved=3 elements_skipped=0 ...` log fires; operator can run `/play` immediately with the partial canon.

---

## §11. Decision points — operator's call required

Twelve decisions for operator lock before implementation opens (Session 2 review). Code's leans noted; genuine uncertainty flagged.

---

### §11.1 — Premise storage column

**Question:** Add new `premise` column or fold into existing `world_notes`?

**Candidates:** (a) new `premise TEXT DEFAULT ''`; (b) fold into existing `world_notes`; (c) fold into orphaned `current_scene` (post-S67 vestigial column).

**Recommendation: (a) new column.** `world_notes` semantics are not specified; `current_scene` is orphaned-vestigial post-S67. New column makes the field's purpose explicit and keeps the §76 audit clean.

**Confidence: HIGH.** Per §1.A reasoning.

---

### §11.2 — Bootstrap command integration

**Question:** `/bootstrap` separate from `/newcampaign`, or folded in?

**Candidates:** (a) separate `/bootstrap` slash; (b) `/newcampaign` triggers bootstrap automatically; (c) `/newcampaign --bootstrap` flag.

**Recommendation: (a) separate.** Folding tightly couples campaign creation with multi-card authoring; operators may want campaign-without-bootstrap (e.g., importing prior skeleton). Separate command preserves opt-in.

**Confidence: HIGH.** Per §1.B reasoning.

---

### §11.3 — Premise input shape

**Question:** Single-shot slash arg, multi-card clarification dialogue, or Discord Modal?

**Candidates:** (a) single-shot slash arg; (b) multi-card clarification ("what's the antagonist energy?" → "what's the genre?"); (c) Discord Modal text input.

**Recommendation: (a) single-shot slash arg.** Option-3 authoring constraint: operator provides premise once; more compounds friction.

**Confidence: HIGH.** Per §1.C reasoning + sketch §11.1 HIGH-confidence lean.

---

### §11.4 — Re-roll semantics

**Question:** Soft-reroll (LLM call with prior-rejected hint) or hard-reroll (fresh from scratch)? Max rerolls per card?

**Candidates:** (a) soft-reroll, unlimited; (b) hard-reroll, unlimited; (c) soft-reroll capped at N; (d) hard-reroll capped at N.

**Recommendation: (a) soft-reroll, unlimited.** Rerolls are cheap (~1s LLM call, extraction-tier). Capped reroll forces accept/skip when operator wants different shape — friction. If operator rerolls 10+ times, that's a signal the premise + bot pairing isn't producing what they want; surface via `/bootstrap manual <field>:<value>` escape hatch (§11.9).

**Confidence: MEDIUM.** Per sketch §11.4. Live-verify signal will tell us if unlimited rerolls produce loop pathology (operator stuck on one card). If observed, fall to (c) with N=5.

---

### §11.5 — Idempotency on re-run

**Question:** Error / expansion mode / full re-run with confirmation?

**Candidates:** (a) error at v0 (no re-bootstrap supported); (b) expansion mode (add new elements without touching prior canon); (c) full re-run with explicit confirmation.

**Recommendation: (a) error at v0.** Expansion mode is v1.x candidate when observed friction surfaces. Full re-run risks silent overwrite of operator-approved canon.

**Confidence: HIGH.** Per §1.J + sketch §11.5 lean.

---

### §11.6 — Premise rendering in main prompt

**Question:** Does premise render in `build_dm_context` as standing campaign-level framing?

**Candidates:** (a) yes, low-tactical-band placement; (b) yes, very early (with SETTING & TONE); (c) no (premise read only by bootstrap bot).

**Recommendation: (a) yes, low-tactical-band.** Premise is operator's standing intent for the campaign; every narration call should be framed by it. Low-tactical-band placement (between SETTING & TONE and the per-turn directives) keeps it consistent context.

**Confidence: MEDIUM.** Per §1.E + sketch §11.6 lean. Tactical-band vs. SETTING-adjacent placement could shift after Session 2 walks the prompt-structure recon. Either works doctrinally; the call is purely positional.

---

### §11.7 — Skeleton.md write shape

**Question:** Structured markdown per existing patterns? YAML embedded blocks? Schema-formal format?

**Candidates:** (a) structured markdown per R2 parser format; (b) YAML front-matter blocks under each H3; (c) schema-formal JSON sidecar file.

**Recommendation: (a) structured markdown.** Matches existing `parse_skeleton_file` parser; existing hand-authored skeleton.md remains compatible; bot output is human-readable for operator inspection.

**Confidence: HIGH.** Per §1.G + sketch §11.7 lean. R2 confirms the parser is bot-output-friendly.

---

### §11.8 — Faction storage at v0

**Question:** Skeleton.md only, ship `dnd_factions` table, or defer faction cards entirely?

**Candidates:** (a) skeleton.md only at v0 (no DB table); (b) ship `dnd_factions` table as v0 prerequisite; (c) defer faction cards entirely to v1.x.

**Recommendation: (a) skeleton.md only.** Causality Engine v0 (S69) will introduce `dnd_factions` and migrate from skeleton-parsed factions. Bootstrap-as-authoring-tool should not introduce schema; that's a separate ship.

**Confidence: HIGH.** Per §1.H. R6 evidence confirms `dnd_factions` does not exist; Quest Layer v0 §12.2 deferred faction modeling to v1.x.

**Operator decision dependency:** if operator wants `dnd_factions` shipped earlier (e.g., to unblock S69), this flips to (b) and S69 inherits N-10's table.

---

### §11.9 — NPC pronouns at v0

**Question:** Folded into description prose, or new `dnd_npcs.pronouns` column?

**Candidates:** (a) folded into description prose (deferred to N-4); (b) ship `dnd_npcs.pronouns` column as v0 prerequisite; (c) defer NPC cards entirely until N-4 ships pronouns column.

**Recommendation: (a) folded into description prose.** N-4 (S68 candidate) ships the column + anti-drift rail; v0 just needs description prose containing pronoun signals.

**Confidence: HIGH.** Per §1.I + sketch §4 NPC card explicit deferral note. N-4's one-shot migration pass extracts pronouns from existing descriptions at column-add time.

---

### §11.10 — Operator field-override semantics

**Question:** Slash-with-args (`/bootstrap manual name:"X"`) or chained-per-field commands?

**Candidates:** (a) `/bootstrap manual <field>:<value>` for any single field override per invocation; (b) `/bootstrap manual` opens an interactive Modal with all field inputs; (c) operator types JSON.

**Recommendation: (a) `/bootstrap manual <field>:<value>`.** Standard slash-arg shape; operator can chain multiple overrides before `/bootstrap accept`.

**Confidence: HIGH.** Per sketch §11.9 lean.

---

### §11.11 — Sequence order

**Question:** Factions → NPCs → Quests → Acts → Locations? Or NPC-first then quests anchor to them?

**Candidates:** (a) factions first; (b) NPCs first; (c) quests first; (d) operator-selected order.

**Recommendation: (a) factions first.** Everything else hangs off pressure threads; faction-first surfaces the load-bearing question before lower-level details lock in. NPC-first or quest-first would require post-hoc faction-fit, generating contradictions.

**Confidence: MEDIUM.** Per sketch §11.2 lean. Operator may have a different ordering preference based on how they think about world-building; live signal informs.

---

### §11.12 — Skeleton.md vs. DB source-of-truth on divergence

**Question:** If skeleton.md and canonical tables diverge later (operator hand-edits skeleton.md, or DB row deleted), which wins?

**Candidates:** (a) skeleton.md wins (re-parse and overwrite DB on next `/play`); (b) DB wins (skeleton.md becomes stale prose); (c) divergence flagged but neither auto-wins (operator resolves manually); (d) no policy at v0.

**Recommendation: (d) no policy at v0.** Skeleton.md ↔ DB divergence is a longer-term canon-management question. v0 ships single-shot bootstrap that writes both in lockstep at approval-time. Divergence-resolution is filed for v1.x or for a separate canon-sync spec.

**Confidence: LOW — genuine uncertainty.** Per sketch §11.11 explicit "no confident lean." Surfaces as v1.x candidate alongside expansion-mode and re-bootstrap. Operator + Code walk required when divergence becomes observed friction.

---

## §12. Open questions filed forward — out of v0 scope

These surface during recon or are implied by v0 decisions but are not v0 work.

**§12.1 — Mid-campaign expansion mode.**
Per §1.J + sketch §1: v0 is single-shot bootstrap. Operator wanting to add new factions/NPCs/quests mid-campaign hits the idempotency error. v1.x expansion mode: re-run `/bootstrap` proposes ONLY new elements (no touching prior canon), advances sequence pointer past already-approved card types when nothing new is proposed. Requires §11.5 lock to flip from (a) to (b).

**§12.2 — Re-bootstrap on premise update.**
Operator wants to change campaign tone or pivot premise mid-campaign. v0 errors. v1.x options: drop and restart (with confirmation), append-only update, or premise-only update (keep canon, refresh premise rendering). Filed alongside §12.1.

**§12.3 — Skeleton.md ↔ DB divergence reconciliation.**
Per §11.12. Filed for v1.x or separate spec when divergence becomes observed friction.

**§12.4 — Arc-shape extraction from CRD3 corpus.**
Sketch §1 notes "Not an arc-shape extractor from CRD3 corpus (v1.x if needed)." v0 uses corpus findings as fixed-constant prompt substrate (§5 + R5); v1.x could pull live arc-shape patterns from the corpus to inform act-decomposition card proposals.

**§12.5 — Faction modeling promotion to DB (`dnd_factions` table).**
Per §11.8 — v0 keeps factions in skeleton.md. Causality Engine v0 (S69) introduces `dnd_factions` table; migration from skeleton-parsed factions at that ship.

**§12.6 — NPC pronouns column (`dnd_npcs.pronouns`).**
Per §11.9 — v0 folds pronouns into description prose. N-4 (S68 candidate) introduces the column + anti-drift rail + one-shot migration pass extracting pronouns from existing descriptions.

**§12.7 — Bot-curated skeleton mirror of ongoing play.**
Per sketch §9 — earlier `/seed_create` filing concept (bot updates skeleton.md as the campaign progresses based on observed play). Different ship from v0's single-shot bootstrap; filed as future authoring-tool extension.

**§12.8 — LLM-noise rate on bootstrap card content.**
The bot's directive call uses extraction-tier LLM (per §1.L). Noise rate (does Llama-3.3-70b produce off-tone faction goals? Wrong-tone NPC descriptions?) is unknown until live signal. Calibrate from operator-skip/reroll telemetry post-ship. If high noise rate, fall back to stronger system prompt or main-narration-tier routing.

**§12.9 — Reward-magnitude calibration for bootstrap quests.**
Per Quest Layer v0 §11.5 — emergent-quest reward calibration is DMG-by-level vs. LR-X4 vs. operator-locked. v0 bootstrap quests use LR signal (§5.3) as the LLM's reward-magnitude prior. If observed rewards drift from operator intent, surface for the Quest Layer v0 §11.5 operator + Oracle walk.

**§12.10 — Multi-quest cross-NPC dispatcher.**
Sketch §6 + Quest Layer v0 §12.3: an NPC dispatching multiple quests, or quests with separate accept-NPC vs. deliver-NPC. v0 has one `offer_npc_id` per quest; if operator authors a "two quests from same NPC" pattern, v0 handles by writing each quest with the same `given_by`. Cross-NPC quest hand-off (mayor accepts, sheriff delivers) is v1.x Quest Layer extension.

**§12.11 — Bootstrap-time chroma seeding.**
v0 does NOT seed chroma with bootstrap-authored prose. First chroma writes happen at `/play` per existing path. v1.x could pre-seed chroma with bootstrap descriptions for "relevant past events" anchoring on turn 1. Filed if turn-1 retrieval emptiness becomes observed friction.

**§12.12 — Bot directive prompt-budget optimization.**
Per R4, per-card directive prompt is ~2-3k chars at v0. If a future bot extension (per-card sub-suggestions, multi-element chains) pushes this past extraction-tier context limits, file optimization candidate. Not v0 work.

---

## §13. Out of scope — v0 explicitly does not

- Mid-campaign canon expansion (filed §12.1).
- Re-bootstrap on premise update (filed §12.2).
- Skeleton.md ↔ DB divergence reconciliation (filed §12.3).
- Arc-shape extraction from CRD3 corpus (filed §12.4).
- `dnd_factions` table creation (filed §12.5; deferred to Causality Engine v0 / S69).
- `dnd_npcs.pronouns` column (filed §12.6; deferred to N-4).
- Bot-curated skeleton mirror of ongoing play (filed §12.7).
- Faction runtime evolution / tick rules (Causality Engine v0 / S69 territory).
- Narrative-loot extraction (N-5 territory, filed in `S66_followups.md`).
- NPC commitment-tracking + pricing-math anti-gaslight rail (N-3 territory, S68).
- NPC pronoun-lock anti-drift rail (N-4 territory, S68).
- LLM-classified intent feeding canonical-table writes (§1a — bot is suggestion-only).
- Bot-emitted Avrae commands of any kind (§65 bot-Avrae write-boundary invariant).
- Any modification to adjudication / verifier / arbitration layer.
- Any modification to active-narration LLM call path.

---

## §14. Handoff

| Field | Value |
|---|---|
| **Spec status** | DRAFT — Phase 1 spec drafting complete (May 14, 2026). Session 2 = review pass (Opus medium per cadence table). Session 3 = implementation. |
| **Spec file** | `/home/jordaneal/virgil-docs/specs/CANON_BOOTSTRAP_BOT_V0_SPEC.md` |
| **§1 decisions** | 12 proposed decisions (§1.A–§1.L), all with recommendation + reasoning. |
| **§11 count** | 12 decisions (§11.1–§11.12) require operator lock before Phase 3. 7 HIGH confidence, 4 MEDIUM, 1 LOW (§11.12 skeleton-vs-DB divergence — genuine uncertainty per sketch §11.11). |
| **§12 count** | 12 open questions filed forward (§12.1–§12.12). |
| **HALT escalations** | 0. Required reading `planner-scratch/canon_bootstrap_bot_v0_sketch.md` was missing locally; retrieved from PC via rsync before recon opened. Two recon contradictions surfaced as §11 decisions (NOT HALT): (a) `dnd_factions` table doesn't exist → §11.8 routes faction cards to skeleton.md only at v0; (b) `dnd_npcs.pronouns` column doesn't exist → §11.9 folds pronouns into description prose, deferring column to N-4. Both have clean workarounds preserving v0 scope. |
| **Recon findings** | R1: `/newcampaign` (NOT `/createcampaign`) — minimal row insert, no skeleton path attached, premise needs new column. R2: skeleton parser is semi-strict (H2 vocab known, H3 placement enforced, H4 acts subsection per Composition Layer v0). R3: `_post_dm_aside` plain Discord message ≤2000 chars, three precedent card shapes (Quest offer / Quest act / Reward ready). R4: bootstrap prompt budget ~2-3k chars per card, ~12% of main-play prompt — cheap. R5: corpus findings (LR/EC/TM/CC) map cleanly to card types as fixed-constant prompt substrate. R6: four single-writers match cleanly (npc_upsert / quest_add / quest_act_upsert / location_upsert); two GAPS surfaced (`dnd_factions` table missing, `dnd_npcs.pronouns` column missing) — both routed to §11 decisions. |
| **Architectural recommendation** | Bootstrap is a separate `/bootstrap` slash (NOT folded into `/newcampaign`). Premise stored in new `dnd_campaigns.premise` column. `compute_bootstrap_card_directive` is §59 sibling #18 (extraction-tier LLM call with deterministic post-validator). `compute_premise_directive` is §59 sibling #17 (renders premise in main prompt at low-tactical-band). Factions stay in skeleton.md only at v0 (Causality Engine S69 introduces `dnd_factions`). Pronouns folded into description prose at v0 (N-4 / S68 introduces column). §1b sixth-instance anchor, deterministic-only validator throughout (cosine-similarity precedent honored). |
| **Next session** | Session 2 = review pass. Opus medium per cadence (mature §59 sibling pattern with 17 prior instances, mature §1b suggester pattern with 4 explicit prior instances + 1 reserved). Two §11 decisions surface schema-coupling questions (§11.8 dnd_factions, §11.9 dnd_npcs.pronouns) that operator may want to flip the v0 routing on — surface clearly at walk-time. Session 3 = implementation (estimated ~3-4 days for engine + orchestration + 7 slash commands + 19 test surface). |

---
