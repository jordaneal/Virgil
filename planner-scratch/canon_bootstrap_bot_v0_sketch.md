# Canon Bootstrap Bot v0 — Architectural Sketch

**Status:** v0 sketch — pre-spec. §11 candidates surfaced not locked.
**Date:** 2026-05-14
**Authorized:** Post-Tier-1-close priority shift. Operator confirmed option-3 authoring (premise-only) — every downstream architecture ship gates on this existing.

---

## 1. What this is

Canon Bootstrap Bot v0 (N-10) is the authoring tool that closes the load-bearing project gap: operator confirmed no manual canon writing, every architectural layer (Quest Layer dispatchers, Composition Layer acts, Causality Engine factions) depends on authored canon existing, and the gap was being filled by nothing.

The bot consumes a 2-3 sentence premise from operator and produces enough structured canon for the architecture to bite into — dispatcher NPCs, starter quests, quest acts, location entries, faction/pressure threads. Each element proposed via `#dm-aside` card, operator approves with slash, engine writes to canonical tables via existing single-writers and to skeleton.md as side effect.

The operator never opens skeleton.md.

**Architectural placement.** Sits between campaign creation (`/createcampaign`) and active play. Runs once at campaign start (v0) — v1.x considers re-bootstrap on premise update or mid-campaign expansion. The structured canon it produces is the substrate every motion-system layer reads from.

**What v0 is NOT.** Not a runtime co-author (does not propose during play — that's Quest Layer offer suggester / Composition Layer act suggester territory). Not a faction-evolution engine (that's Causality Engine). Not an arc-shape extractor from CRD3 corpus (v1.x if needed). Not a mid-campaign canon expander (v1.x). Single-shot bootstrap from premise seed.

---

## 2. What surfaces it extends, what's new

**Reuses (no schema change):**
- `dnd_campaigns` — premise stored in existing skeleton-pointer or new column (§11 decision).
- `dnd_npcs` — bot proposes new NPCs; operator approves; existing `npc_upsert` writes per §17.
- `dnd_quests`, `dnd_quest_acts` — bot proposes; operator approves; existing single-writers from Quest Layer v0 and Composition Layer v0.
- `dnd_locations` — same pattern.
- skeleton.md file — bot writes structured markdown on per-element approval; same file format as hand-authored.
- §1b validated-suggester pattern — fourth-instance precedent (Quest Layer v0.1, Composition Layer v0) is the architectural template.
- `#dm-aside` channel — proposal surface, same as existing suggesters.

**Proposed new:**
- One slash command — `/bootstrap` (DM-only, runs after `/createcampaign`, takes premise as input or surfaces premise prompt). Exact shape §11.
- One in-memory state surface — `_bootstrap_session: dict[campaign_id, BootstrapState]` holding the active card sequence, pending approvals, premise context. Same pattern as `_combat_beats` / `_scene_stale_turns`.
- One advisory directive — `compute_bootstrap_card_directive(state, card_type, campaign_data) → (card_body, signals)`. §59 sibling #16, generates the next card proposal based on bootstrap state.
- New skeleton.md writer — `skeleton_md_append_element(campaign_id, element_type, content)`. Single writer per §17. Appends per-element to the file in structured-markdown shape. Idempotent on (element_type, element_name).
- New telemetry primitives — `bootstrap_card_proposed:`, `bootstrap_card_approved:`, `bootstrap_card_rejected:`, `bootstrap_session_completed:`.

**Not new:**
- No new ChromaDB collection.
- No bot→Avrae writes.
- No LLM classification feeding binding state transitions (per §1a — operator slash is the binding decision; bot proposes via deterministic directive).
- No new write paths to canonical tables; bot drafts go through the existing single-writers on operator approval.

---

## 3. The bootstrap flow shape

**Trigger:** Operator runs `/bootstrap` after `/createcampaign`. Premise input shape is §11 (single-shot prompt, multi-prompt clarification, or operator-types-into-modal).

**Premise capture:** 2-3 sentence prose stored on `dnd_campaigns` (new column `premise TEXT DEFAULT ''` OR existing skeleton-pointer field — §11 decision). Examples:
- "High-fantasy elven coastal town, my character is a bard, festival of dawn approaches."
- "Grimdark frontier mining town, hexcrawl, the mine collapsed and something climbed out."

**Card sequence (proposed v0 order):**
1. **Faction / world-pressure threads** (1-2 cards) — what's pressuring the world. Anchors offscreen stakes. Required for Causality Engine to operate downstream.
2. **Dispatcher NPCs** (2-3 cards) — quest-givers, faction representatives, town authorities. Closes the gap S62's companion filter surfaced.
3. **Starter quests** (3 cards) — initial offerable quests tied to dispatcher NPCs and faction threads. Includes reward magnitudes per skeleton-authored canon (§11.5 Quest Layer locked path c).
4. **Quest acts** (per starter quest, 2-4 cards each) — Composition Layer act decomposition per §6 of Composition spec.
5. **Locations** (2-3 cards) — beyond starting location. Anchors travel destinations and quest sites.

Sequence order is §11 — could be premise-first → factions → NPCs → quests → acts → locations, or could be NPC-first then quests anchor to them. Lean: factions/pressures first, because everything else hangs off them.

**Per-card mechanics:**
- Bot proposes element via `#dm-aside` card (formatted markdown with element preview)
- Operator approves via `/bootstrap accept` slash, skips via `/bootstrap skip`, requests re-roll via `/bootstrap reroll`
- Re-roll uses same premise + prior-approved context, generates alternative draft
- Skip moves to next card; rejected elements not written
- Approval triggers element write to canonical table + skeleton.md append
- Telemetry per action

**Session completion:** When card sequence exhausts (or operator runs `/bootstrap end`), session writes a `bootstrap_session_completed:` log line and clears in-memory state. Skeleton.md is now populated; campaign is bootstrap-complete.

**Idempotency:** `/bootstrap` re-run on a bootstrap-complete campaign either (a) errors out, (b) opens an "expansion" mode that proposes additional elements without touching prior canon, or (c) full re-run with confirmation prompt. Lean (a) at v0; (b) is v1.x candidate.

---

## 4. The card directive shape

**§59 sibling #16.** `compute_bootstrap_card_directive(bootstrap_state, card_type, campaign_data) → (card_body, signals)`.

Inputs:
- `bootstrap_state` — premise prose, prior-approved elements (so the bot doesn't propose duplicates and can build on what landed)
- `card_type` — one of {faction, npc_dispatcher, quest, quest_act, location}
- `campaign_data` — campaign id, party from `dnd_companions`, current location if any, time setting

Output:
- `card_body` — structured markdown block for `#dm-aside`. Includes element type, proposed name, proposed fields, brief justification ("This NPC is the festival organizer, fits the bard-narrator premise"), action prompts.
- `signals` — `{card_type, element_proposed, approved_count, remaining_in_sequence}` for telemetry and downstream composition.

**Per-card-type field requirements:**

**Faction card** — name, goal (1 sentence), pressure-shape (clock-style N-of-M progress?), engagement signals (what causes ticks?). Causality Engine substrate; v0 stores the structured fields, runtime tick is Causality Engine's job.

**Dispatcher NPC card** — canonical_name, role, pronouns (this is the N-4 surface; pronouns get authored at bootstrap, anti-drift rail in N-4 ships separately), description, location (where the party meets them), associated faction (FK or null), quest-offer mapping (which quests they dispatch).

**Quest card** — title, summary, offer NPC (must be a prior-approved dispatcher), reward summary (operator-locked-per-quest per §11.5 lock), associated faction (optional FK).

**Quest act card** — quest FK, act_index, act_title, act_description, optional transition_predicate_json per §11.7 Composition lock (narrow vocabulary: scene_count + location_id).

**Location card** — canonical name, description, parent_location_id (optional, for hierarchical maps like town > tavern), starting_location flag.

---

## 5. Doctrinal compliance audit

**§1a binding decisions.** Bot proposes; operator approves via canonical slash gate; engine writes via existing single-writers. No LLM-decided binding state changes. §1a clean.

**§1b validated-suggester pattern.** Same shape as Quest Layer v0.1 / Composition Layer v0 / NPC State-Sync / Track 6 #5.1 SRD suggester. Sixth project instance candidate. No calibration-bound auxiliary (cosine-similarity precedent rejected; explicit slash is the canonical gate).

**§17 single-writer per field.** All canonical-table writes go through existing single-writers (`npc_upsert`, `quest_upsert`, `quest_act_upsert`, `location_upsert`). Bot doesn't fork sibling writers. Skeleton.md gets a new single-writer (`skeleton_md_append_element`) but it's not a sibling of an existing writer — it's first-of-its-kind for that file.

**§59 sibling pattern.** One new sibling (`compute_bootstrap_card_directive`). Pattern is mature at 15 instances.

**§76 four-property test on new fields:**

- `dnd_campaigns.premise` (new column): Operator-written, persisted, retrieved by bot only (not by main LLM prompt context — TBD per §11), structured-prose-shape. If retrieved by main prompt, 4/4. If retrieved only by bot directive, 3/4. **§11 decision: where does premise render?**
- Bot draft state (in-memory): LLM-writable, not persisted (in-memory only), not retrieved across sessions. Not a §76 surface.
- Approved canonical-table writes: same §76 status as existing — operator-authored content via bot proposal flows through existing fields with existing §76 status. Bot doesn't worsen §76 surface; it expands the authored-canon volume that the existing §76 hygiene protects.

**§77 atmospheric continuity.** Bot output is structured cards for operator approval, not narration. §77 doesn't apply directly. The downstream content (NPCs the bot creates) becomes substrate for §77-compliant narration at play time.

---

## 6. Composition with downstream architecture

**Quest Layer v0 / v0.1 reads bot output.** Dispatcher NPCs authored by bot become valid `voicer_npc_id` candidates for offer suggester. Quests authored by bot enter `dnd_quests` with `status='offered'`. Active-quest directive surfaces them.

**Composition Layer v0 reads bot output.** Acts authored by bot fill `dnd_quest_acts`. Composition directive surfaces current act. Suggester predicate matches against authored predicates.

**Scene Lifecycle v1 unaffected.** Bot doesn't touch scene-stale counter or compression directive. Existing stagnation-drift detection operates on bot-authored canon same as hand-authored canon.

**Causality Engine v0 (S69, post-N-10) reads bot output.** Faction/pressure threads authored by bot become the substrate Causality Engine ticks against. **N-10 IS the load-bearing prerequisite for Causality Engine to do anything meaningful.**

**N-3 + N-4 (S68, post-N-10) operates on bot output.** Pronoun lock fires on bot-authored NPCs (pronouns captured at bootstrap card approval per §4 NPC card shape). Prior-price-check rail operates on actual NPC commitments once bot has created NPCs to commit.

---

## 7. Architectural questions for §11 decisions

Surfaced for operator lock before spec drafting. Leans named where confident.

1. **Premise input shape.** Single-shot prompt at `/bootstrap` invocation? Multi-card clarification dialogue ("what's the antagonist energy?" / "what's the genre?")? Modal text input via Discord? *Lean: single-shot prompt at `/bootstrap` invocation.* Multi-card clarification adds 2-3 turns of setup friction before the bot does work. Operator confirmed willingness for 2-3 sentences once; more than that compounds against the option-3 constraint.

2. **Card sequence order.** Factions → NPCs → Quests → Acts → Locations? Or NPC-first then quests anchor to them? *Lean: factions first.* Everything else hangs off pressure threads; if the operator skips faction cards, the bot can still produce useful canon, but faction-first surfaces the load-bearing question before the operator commits to lower-level details.

3. **Number of elements per card-type at v0.** Faction (1-2), NPC (2-3), Quest (3), Acts per quest (2-4), Locations (2-3)? *Lean: per above defaults*, tunable post-playtest.

4. **Re-roll semantics.** Hard re-roll (regenerates from scratch)? Soft re-roll (re-prompts LLM with "operator wants different shape" hint)? Maximum re-rolls per card before forcing accept/skip? *Lean: soft re-roll, unlimited.* Re-rolls are cheap LLM calls; forcing accept/skip is its own friction. If operator re-rolls 10 times on one NPC, that's a signal the premise + bot pairing isn't producing what they want — surface as a card-level escape hatch (`/bootstrap manual <field> <value>` to override).

5. **Idempotency on re-run.** Error / expansion mode / full re-run with confirmation? *Lean: error at v0.* Expansion mode is v1.x candidate when observed friction surfaces. Full re-run is dangerous because operator-approved canon shouldn't be silently overwritten.

6. **Premise rendering in main prompt.** Does the 2-3 sentence premise get rendered into `build_dm_context` as standing campaign-level framing? *Lean: yes, at low-tactical-band placement.* If premise is "grimdark frontier mining town, the mine collapsed and something climbed out," that should inform every narration call, not just bootstrap. §11 decision on render position and whether the premise gets §76-treated (it's operator-written so 3/4 max — not LLM-writable).

7. **Skeleton.md write shape.** Structured markdown per existing patterns? YAML embedded blocks? Schema-formal format? *Lean: structured markdown per existing patterns.* Matches Composition Layer §6 skeleton.md authoring shape. Existing `/quest seed-skeleton` parser already handles this format.

8. **Re-bootstrap on premise update.** Operator wants to change campaign tone mid-bootstrap or post-bootstrap. Drop and restart? Append-only? Confirmation gate? *Lean: error at v0; expansion-mode v1.x.* Premise updates are a real authoring axis but v0 should ship the cleanest first-time-bootstrap shape, not the full lifecycle.

9. **Operator field-override.** During card proposal, can operator type `/bootstrap manual name:"Eldrin Stormbow" role:"village herald"` to override bot's draft on specific fields? *Lean: yes at v0.* Cheap to implement; high value for the case where operator wants 90% of bot output but specific named NPC. Slash-with-field-args pattern is standard project surface.

10. **§1b sixth-instance anchoring.** Does this anchor the §1b pattern for the fourth time, or does it constitute meaningfully-new architectural shape? *Lean: sixth-instance anchors cleanly.* Canonical operator slash gate + deterministic-validator (file-write + schema integrity) + per-element cards. Same architectural shape as Quest Layer v0.1 / Composition Layer v0. No calibration-bound auxiliary (cosine-similarity precedent rejected; explicit slash only).

11. **Skeleton.md as source-of-truth vs DB-as-source-of-truth.** Bot writes to both on approval. If they diverge later (operator hand-edits skeleton.md, or DB row deleted), which wins? *No confident lean.* This is a longer-term canon-management question that v0 should not lock. Filed for v1.x or for a later canon-sync spec.

12. **Telemetry verbosity.** Per-card telemetry (`bootstrap_card_proposed`, etc.) vs session-level summary only. *Lean: per-card.* Standard project pattern; playtest observability requires per-event signal.

---

## 8. Operational concerns for Phase 1 recon

**Existing `/createcampaign` flow audit.** Phase 1 must inventory: what runs on `/createcampaign` today, what state lands in `dnd_campaigns`, whether premise field can fold into existing column or requires new. Bot must integrate cleanly with existing flow without forcing operator into a brittle command sequence.

**Skeleton.md current state across campaigns.** Audit: do all active campaigns have skeleton.md files? What format? Does `/quest seed-skeleton` parser expect a specific structure that bot output must match? If parser is strict, bot output is constrained; if parser is permissive, bot has freedom.

**Card UI shape in Discord.** Discord `#dm-aside` posts have practical character limits (~2000 per message; can use embeds for ~6000). Card content must fit. Per-card formatting recon required.

**Prompt size budget at bootstrap time.** Bot's directive call needs context: premise + prior-approved elements + card-type spec + corpus signal (LR for reward magnitudes, EC for cadence). Estimate prompt size pre-spec. Current baseline ~25k chars (per S66 prompt-size budget audit); bootstrap directive likely sub-1k per card. Budget-safe.

**Corpus signal integration.** Bot uses existing five findings docs (LR, CC, TM, EC, cross-extractor) as substrate for proposal quality. No fresh corpus pass at v0. Where in the bot's prompt does this signal get injected? Spec-time question.

---

## 9. What this sketch does NOT do

- Lock §11 decisions. Spec doc handles.
- Address mid-campaign canon expansion (filed v1.x).
- Address skeleton.md ↔ DB divergence reconciliation (filed for v1.x or later spec).
- Address arc-shape extraction from CRD3 corpus (v1.x if friction surfaces).
- Address bot-curated-skeleton-mirror-of-play (the earlier `/seed_create` filing). N-10 is single-shot bootstrap; mid-play curation is a different ship.
- Address faction runtime evolution (Causality Engine S69 territory).
- Address narrative-loot extraction (N-5 territory).
- Pre-commit corpus extraction shape or per-card LLM call shape (Phase 1 recon territory).

---

## 10. Next move

Path A three-session cadence: spec → review → implement.

**Phase 1 recon scope:**
1. `/createcampaign` flow audit — what runs today, integration shape for `/bootstrap`
2. Skeleton.md format current state across campaigns — what `/quest seed-skeleton` parser expects
3. Discord `#dm-aside` card character-limit + formatting recon
4. Prompt-size baseline at bootstrap time — estimate bot directive size
5. Corpus findings docs review — confirm which signals inform which card types

**Phase 2 walks §11.1 through §11.12 with operator.** Most have leans; §11.11 (skeleton-vs-DB source-of-truth) is no-confident-lean territory.

**Phase 3 ships locked spec.**

After v0 ships and the operator uses it on a new test campaign, observed friction tells us which v1.x candidates earn slots (expansion mode, re-bootstrap, mid-play curation, arc-shape corpus extraction).

**This is the load-bearing ship.** Tier 1 cleanup arc closed; the architecture is structurally sound; the project's playability gate is now authored-canon volume. N-10 closes that gate.
