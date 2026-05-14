# QUEST_LAYER_V0_SPEC.md

**Status:** LOCKED (v0.1 patched May 13, 2026) — Phase 3 implementation shipped + Phase 3 v0.1 UX patch applied. All 14 decisions (12 §11 + §1.B sub-decision + §11.5 v0 scope) locked per `QUEST_LAYER_V0_REVIEW.md`. Four amendments applied:

1. **§1.B alias→migrate** (S56 ship). R4 evidence (campaign 17 zero rows) reduces migration cost to near-zero. Status enum becomes the five-status set canonically. One-line `UPDATE dnd_quests SET status='in-progress' WHERE status='active'; UPDATE dnd_quests SET status='delivered' WHERE status='completed';` runs at engine init before any v0 helper fires.
2. **§1.C idempotent clause refinement** (S56 ship). Edit-hook-title mid-campaign produces an orphan `skeleton_origin=1` row after re-seed. Operator cleans up via `/quest delete <id>`. Documented in `/quest seed-skeleton` docstring + this spec's §1.C clause.
3. **§1.E + §11.7 + §11.12 — REVISED v0.1 patch S57 (Reading-3 → Reading-2).** Original lock chose Reading-3 (canonical `/quest accept <id>` slash + auxiliary cosine-similarity paste-detection). Live verify surfaced UX friction: in-character offer dialogue rendered into `#dm-aside` reads as "RP in the operational channel" — a category mismatch operator named as "too mechanical, not free flowing enough." Patched to **Reading-2**: canonical-slash is the ONLY acceptance trigger. The `#dm-aside` card becomes pure operational suggestion (structured info + action prompts), no in-character dialogue. The LLM renders the offer scene organically in the next narration turn once `/quest accept <id>` flips the quest to in-progress and the active-quest directive surfaces it. Suggester captures the proposal moment by writing `offer_npc_id` + `offered_turn` at card-post time (audit-trail preservation). All cosine-similarity wiring removed: `_check_quest_offer_paste_match`, `_QUEST_PASTE_SIMILARITY_THRESHOLD`, `_quest_offer_proposal` cache, `quest_offer_paste_matched:` telemetry. Live-verify scenario 4 (Scenario 4 paste-detection) removed.
4. **`/quest seed-skeleton` Discord global-slash propagation lag** (S57 observation). New subcommands take 5–60 minutes to appear in Discord client autocomplete after bot sync. Mitigation: hard-reload Discord client (Ctrl+R / Cmd+R) post-restart. Documented in deploy notes; no code change.

**Session:** S54 Path A Phase 1 spec drafting against `planner-scratch/quest_layer_v0_sketch.md` (May 13, 2026)
**Ship:** Motion Systems Track — Quest Layer v0 (piece 2 of 3 in operator mandate: Scene Lifecycle ✅ shipped + verified, Quest Layer = this spec, Composition Layer = piece 3)
**Addresses:** "The party has nothing structurally pulling them forward" — the adjacent F-54 symptom Scene Lifecycle didn't address. Surfaces skeleton-authored quests as NPC-voiced offers + tracks accepted quests as state.
**Precedent specs:** `SCENE_LIFECYCLE_V1_SPEC.md` (§59 sibling shape, S52), `NPC_STATE_SYNC_SPEC.md` (§1b second-instance precedent, S41), `CONSEQUENCE_SURFACING_SPEC.md` (S16, adjacent ledger pattern).

---

## §1. Proposed decisions

These are Code's recommendations for decisions the spec makes. NOT locks. Each goes to operator + planner review in Session 2 before any implementation opens.

---

### §1.A — Extend existing `dnd_quests`, do NOT create new table

**Recommendation: extend the existing schema with the columns v0 needs; do NOT add a parallel `dnd_quests_v0` table or rename the existing one.**

The existing `dnd_quests` table (R2 evidence) has 9 columns, 5 single-writer helpers (`quest_add` / `quest_set_status` / `quest_delete` / `get_active_quests` / `get_all_quests`), 5 `/quest` slash commands, footer-render, and prompt-block render. The schema is thin (no FK, no reward, no audit timestamps), but the surface is already integrated. Extending preserves backward compatibility (existing `given_by` TEXT field is a soft analog of `offer_npc_id` — keep it for back-compat, add the FK alongside).

Specifically: add `offer_npc_id INTEGER`, `offered_turn INTEGER`, `accepted_turn INTEGER`, `delivered_turn INTEGER`, `reward_summary TEXT DEFAULT ''`, `skeleton_origin INTEGER DEFAULT 0`. Status enum expands per §1.B.

**Reasoning:** Parallel table multiplies write paths, breaks footer/prompt-block, requires migration of campaign 17 (currently 0 rows; trivial but other campaigns may have content). Extension is additive; existing `quest_add` etc. continue to work with NULLs in the new columns. v0.x can then introduce `quest_offer` / `quest_accept` etc. as new single-writer helpers that ALSO write the new columns.

---

### §1.B — Status enum: extend from 3 to 5

**Recommendation: extend `VALID_QUEST_STATUSES` from `{'active', 'completed', 'failed'}` to `{'offered', 'in-progress', 'completed', 'failed', 'abandoned'}`. Map: existing `'active'` semantically becomes `'in-progress'`; keep `'active'` as a valid status (alias) for back-compat OR migrate existing rows.**

The sketch §5 proposes five statuses: offered / in-progress / delivered / failed / abandoned. Existing has three: active / completed / failed. Semantic mapping:
- `active` ↔ `in-progress` (post-acceptance, on the active list)
- `completed` ↔ `delivered` (resolved with reward)
- `failed` ↔ `failed` (resolved without reward)
- Missing: `offered` (pre-acceptance) and `abandoned` (walked away)

**Sub-decision (§11.B):** alias `active` to `in-progress` (keep both valid, render both as "in-progress" in directive block) OR migrate existing rows + drop `active` from the enum. Recommendation: alias, because it's cheaper (no migration), back-compat is clean, and existing `/quest add` semantics ("creates active quest") still work — it just writes `status='in-progress'` going forward.

**Reasoning:** The five-status machine is load-bearing for v0's lifecycle (NPC offers a quest → party accepts → quest delivers OR fails OR is abandoned). Three statuses don't carry the `offered` state, which is the surface NPC-voiced offers need. Five-status is also forward-compat with v1.x auto-transitions (sketch §5, deferred).

---

### §1.C — Skeleton-quest seeding: explicit `/quest seed-skeleton` command, NOT auto-seed on first /play

**Recommendation: skeleton hooks are NOT auto-inserted as `dnd_quests` rows. Instead, ship `/quest seed-skeleton` (DM-only, idempotent) that parses `skeleton.md`'s `## Major hooks` section and inserts a row per hook at `status='offered'` with `skeleton_origin=1`.**

R4 surfaced that campaign 17 has zero `dnd_quests` rows despite three skeleton hooks in the skeleton.md file. The hooks live ONLY in the skeleton text block prepended to prompts. v0 needs them in the DB to surface them as NPC-voiced offers.

**Reasoning for explicit-not-auto:** Auto-seeding on first `/play` couples campaign initialization (one-shot, idempotent, §17 narrow exception per S27 pattern) with quest schema, expanding the narrow-exception surface. Explicit `/quest seed-skeleton` keeps the initialization path narrow and lets the operator opt in. Idempotent (skips hooks already in DB by title+skeleton_origin=1 match).

**Alternative considered:** auto-seed in skeleton_loader on first `/play`. Rejected because skeleton_loader's `apply_starting_time_seed` is the project's only S27 narrow exception; widening it for quests is exactly the temptation §17's narrow-exception framing warns against. v0 ships `/quest seed-skeleton` as a separate operator-driven command; v1.x can consider auto-seed once seed-skeleton has live signal.

---

### §1.D — NPC-voicer selection: skeleton-authored mapping (priority A), priority-rule fallback (priority B)

**Recommendation: (a) optional skeleton-authored explicit mapping `quest → NPC` parsed from skeleton.md (new `## Quest hooks` structured section, format below); (b) when no explicit mapping exists, fall back to priority rule: skeleton_origin=1 NPC at current location with highest `mention_count`.**

Skeleton.md format extension (additive, optional):
```
## Quest hooks
- Escort the merchant caravan to Redhaven (voicer: Eldrin Stormbow, reward: 50gp + Guild reputation)
- Investigate the goblin-ravaged farmstead (voicer: Eldrin Stormbow, reward: 75gp + Guild favor)
- Survey the lost mine near the Crystal Caves (voicer: Borin Ironhand, reward: 100gp + relic share)
```

Parser extracts `(title, voicer, reward)` per hook. `voicer` is matched against `dnd_npcs.canonical_name` at seed-skeleton time; on no-match, log `quest_seed_voicer_unresolved:` and store `offer_npc_id=NULL` (NPC-voicer falls back to priority rule at offer-suggester time).

**Reasoning:** Operator authority is the source of canonical campaign content; skeleton.md is the existing authoring surface. Explicit per-quest voicer matches the LR 36.8% pattern (Matt explicitly voices specific NPCs for specific quests). Priority-rule fallback covers the gap when operator doesn't author voicer. Auto-fire suggester (§11.3) then proposes through this voicer.

---

### §1.E — `compute_quest_offer_suggester`: §1b validated-suggester pattern, third project instance

**Recommendation: §59 sibling 12th instance. Pure function `compute_quest_offer_suggester(scene_state, canonical_npcs_at_location, active_quests, offerable_quests) → (proposal | None, signals)`. On proposal, dispatch as `#dm-aside` suggester card (Track 6 #5.1 + S41 NPC State-Sync precedent). Operator pastes dialogue → engine writes `status='offered'` row.**

Architectural shape:
- Suggester reads: `mode`, `current_location_id`, `dnd_npcs WHERE location_id=current AND skeleton_origin=1`, `dnd_quests WHERE status IN ('offered','in-progress')`, `dnd_quests WHERE skeleton_origin=1 AND status NOT IN ('offered','in-progress','completed','delivered','failed','abandoned')` (i.e. unoffered seeded hooks).
- Fire predicate: `mode in {'social','exploration'}` AND `current NPC matches an unoffered quest's voicer (or priority-rule fallback)` AND cooldown predicate (§11.3 candidate).
- On proposal, emit structured dict: `{npc_id, npc_name, quest_id, quest_title, reward_summary, offer_dialogue_seed}`.

Dispatch site (call site in `discord_dnd_bot.py` `_dm_respond_and_post`): post suggester card to `#dm-aside` via `_post_dm_aside()` helper. Card format per §4 below. Operator pastes the offer dialogue into `#dm-narration` (or types `/quest offer accept <id>` shorthand — §11.4 decision).

**Suggester does NOT write `dnd_quests`.** The state mutation fires on operator paste detection OR on explicit `/quest offer accept <id>`. The §1b sequence is preserved: bot proposes → operator approves → engine writes.

**Reasoning:** Third project instance of §1b's suggester pattern after Track 6 #5.1 SRD suggester (S26) and S41 NPC State-Sync. Same architectural shape — bot via `#dm-aside`, deterministic gate (suggester's predicate + match logic), DM approves by paste, engine executes (here: SQLite write, not Avrae). The shape is now mature; no architectural surprises expected. See §11.12.

---

### §1.F — `compute_active_quest_directive`: §59 sibling 13th instance, REPLACES existing `quests_to_prompt_block`

**Recommendation: introduce `compute_active_quest_directive(active_quests, scene_state) → (body, signals)` and migrate the existing `quests_to_prompt_block` call site to use it.**

Pure function over `dnd_quests WHERE status='in-progress'` (alias active). Returns:
- `('', {fired: 0, active_count: 0})` when zero in-progress quests
- Block with header `=== ACTIVE QUESTS ===`, max 3 lines (severity-then-recency ordering per consequence S16 precedent), capped at 300 chars
- Always-fire log: `quest_directive: campaign=N count=N fired=0|1 chars=N`

**Sub-decision (§11.8):** placement in `build_dm_context`. Current `quests_section` lands very early (after `scene_state_section`, before `char_ctx_section`). The sketch's §11.8 lean is to move it AFTER consequence_block, BEFORE scene_lifecycle_block — tactical-band placement same tier as consequences. Recommendation: lean (a) of sketch §11.8 — relocate to tactical band. Existing footer 🗒️ render stays for ambient awareness.

**Reasoning:** Existing `quests_to_prompt_block` is a thin string-formatter, not a §59 sibling — no signals dict, no telemetry, no soft-fail at call site. v0 promotes it to §59 sibling pattern, inherits per-turn telemetry for free, and migrates placement to tactical band where active-quest pressure belongs (alongside consequence pressure).

---

### §1.G — Reward delivery: `quest deliver` posts to `#dm-aside` for operator-paste, NOT auto-narration

**Recommendation: `/quest deliver <id>` action triggers (a) `#dm-aside` post with reward summary for operator paste, (b) inventory-side auto-add via existing `add_item` if reward includes parseable items. No LLM auto-render of the reward scene.**

When `/quest deliver <id>` fires:
1. `quest_set_status(id, 'delivered')` writes the state transition (§17 single writer extended)
2. Engine parses `reward_summary` for structured items (gp amount, named items, faction reputation tokens) per a strict regex
3. `#dm-aside` post: `[REWARD READY] Quest #N delivered: <title>. Reward: <reward_summary>. Suggested narration: "<NPC voicer> hands you the <reward> ..."`
4. Auto-applies inventory deltas via `add_item` if gp/items parsed cleanly
5. Operator pastes the suggested narration into `#dm-narration` to render the reward scene

**Reasoning:** Avoids the F-39 loot-hallucination drift that auto-LLM-render of rewards historically caused. Same architectural shape as Track 4 #2 loot v1.2 (deterministic engine writes inventory; LLM narrates the moment but the structural mutation is engine-side). Operator controls the scene-authoring moment.

---

### §1.H — Acceptance semantics: explicit slash, NOT implicit narration parser

**Recommendation: operator types `/quest offer accept <id>` after in-fiction acceptance scene resolves. No advisory parser detecting "we'll take the job" in player text at v0.**

Same architectural decision and reasoning as Scene Lifecycle T2 deferral (§11.N of SCENE_LIFECYCLE_V1_SPEC.md): phrase-vocabulary detection on player text is a false-positive risk surface without corpus-grounded precision data. Defer to v1.x once `/quest offer accept` log shows whether operator-typed friction is acute.

**Slash commands shipping at v0:**
- `/quest seed-skeleton` (§1.C)
- `/quest offer accept <id>` — transitions offered → in-progress, sets `accepted_turn`
- `/quest offer decline <id>` — transitions offered → abandoned, no penalty
- `/quest deliver <id>` — transitions in-progress → completed (delivered), fires reward dispatch (§1.G)
- `/quest fail <id>` — already exists; extended to set `delivered_turn=NULL` (failed quests have no delivery)
- `/quest abandon <id>` — transitions in-progress → abandoned (new)

Existing `/quest add`, `/quest list`, `/quest complete`, `/quest delete` continue to work. `/quest add` writes `status='in-progress'` (operator-created quests skip the offered state).

---

### §1.I — Reward magnitude calibration: skeleton-authored at v0 (operator-locked)

**Recommendation: v0 renders `reward_summary` as authored in skeleton.md. No auto-calibration against DMG-by-level or LR-X4 corpus at v0. Calibration becomes a §11.5 decision when emergent quests (v1.x) need machine-generated rewards.**

Per session brief refinement: §11.5 narrows from "DMG vs LR-X4 for all rewards" to "DMG vs LR-X4 for emergent-quest rewards in v1.x." Skeleton-authored quests carry operator's reward decisions verbatim. Operator + Oracle still walks DMG vs LR-X4 for the eventual auto-calibration ship.

**Reasoning:** v0's scope is skeleton-authored quests only (§1.C). Skeleton hooks already carry reward intent (campaign 17's "the guild is offering 50 gold to anyone willing to clear it out" — see skeleton.md L34). The auto-calibration question is real but defers cleanly until emergent-quest generation lands.

---

### §1.J — Offer cooldown: per-NPC, K turns since last offer-card to that NPC

**Recommendation: cooldown predicate on `compute_quest_offer_suggester` — do NOT propose an offer voiced by the same NPC within K turns of the previous offer-card to that NPC. Threshold `_QUEST_OFFER_COOLDOWN = 6` (named constant, calibrate from `quest_offer_proposed:` telemetry).**

K=6 starting value chosen to align with `_STALE_HARD_THRESHOLD` (Scene Lifecycle v1) — i.e. an offer should be "stale-rare" relative to the same NPC. Cooldown is per-NPC, not global, so two different NPCs can offer in adjacent turns if both predicates match.

**Reasoning:** Floods `#dm-aside` with offer-cards is the failure mode the cooldown closes. Per-NPC scope preserves multi-NPC-at-location scenarios (Eldrin AND Borin both have unoffered hooks for the party; either can speak first, but not the same one twice in 6 turns).

---

### §1.K — §76 four-property audit: new fields all clear

**Recommendation: all six new `dnd_quests` columns (`offer_npc_id`, `offered_turn`, `accepted_turn`, `delivered_turn`, `reward_summary`, `skeleton_origin`) pass §76's four-property audit at column-add time. None hit 4/4.**

See §7 below for the full audit. Summary: `reward_summary` is the only ambiguous case (LLM-writable? No — operator-authored or extracted via S27-style narrow-exception parser; persisted? Yes; retrieved? Yes via directive block; narratively inferential? Borderline — a reward string like "50gp + Guild reputation" is enumerable, not narratively inferential). Passes audit with 2/4. Others are 0/4 (FKs, integers, fixed-enum) or 1/4 (`skeleton_origin` is integer flag).

---

### §1.L — Composition-layer forward compatibility: silent at v0

**Recommendation: no schema fields anticipating composition layer at v0.** Per operator discipline note in sketch §6. The `dnd_quests` extension is composition-extensible (FK to NPC, status enum, audit timestamps are load-bearing primitives composition will read from), but v0 does NOT write any composition-anticipating field (`current_act_id`, `act_ordering`, `composition_anchor_id`).

**Reasoning:** Composition layer (piece 3 of mandate) will surface its own schema needs when its spec opens. Speculating on its shape now risks v0 carrying dead columns or, worse, misaligned columns that composition spec has to rename.

---

## §2. Problem statement

**Mandate framing (operator, May 2026):** quest layer is piece 2 of 3 — Scene Lifecycle closed scene immortality (F-54 stagnation drift, S52); quest layer closes "the party has nothing structurally pulling them forward"; composition layer (piece 3) anchors scenes to quest acts. Together they form the motion-systems trio.

**The gap quest layer addresses.** Scene Lifecycle's directive can press the LLM to compress a stale scene — and live verify (S53) shows it works once the LLM-padding perverse-incentive is closed (v1.x patch). But compressing a scene assumes there is somewhere to compress *to*. Without quests, the party has no structural pull forward: every compressed scene resolves into ambient exploration of whatever location they're in. The skeleton hooks (campaign 17: escort caravan / farmstead / lost mine) exist only as static text in the skeleton block; they have no offer-surface, no acceptance state, no delivery resolution.

**LR 36.8% empirical anchor.** Track 5's corpus findings measured that 36.8% of CRD3 reward-bearing surfaces route through NPC dialogue — Matt voices a specific NPC offering a quest, paying for completion, or expressing gratitude. This is the dominant pattern for quest-related social surfaces in real DM corpus. Quest layer v0 ports this pattern: skeleton-authored quests are offered through NPC voicers via the §1b suggester surface, not through Matt's DM narration directly.

**Adjacent-ledger position.** Quest layer sits alongside the consequence layer (S16) — both are ledger-shaped, both track "stakes the world remembers." Consequences track grievances/alliances/debts; quests track outstanding work the world expects of the party. The architectural patterns reuse heavily (single-writer §17, severity/priority caps, AUTHORITATIVE framing, async background writes). The state machine and NPC-voicer routing fork.

**Current gap (R4 evidence):** campaign 17 has zero rows in `dnd_quests` despite three skeleton hooks. The footer's 🗒️ field renders nothing. The `=== ACTIVE QUESTS ===` prompt block renders nothing. Quest layer v0 closes this gap by seeding skeleton hooks into the DB and surfacing them as NPC-voiced offers.

---

## §3. Architectural shape

Quest Layer v0 is a **pair of §59 pure-function-in-orchestration siblings** — 12th and 13th instances after Scene Lifecycle v1's 11th.

```
dnd_orchestration.py:
  compute_quest_offer_suggester(
      scene_state: dict,
      canonical_npcs_at_location: list,
      active_quests: list,            # status='offered' or 'in-progress'
      offerable_quests: list,         # skeleton_origin=1 with status NOT IN (offered, in-progress, completed, failed, abandoned)
      turns_since_last_offer_per_npc: dict[int, int],   # cooldown signal
  ) → (proposal: dict | None, signals: dict)

  compute_active_quest_directive(
      active_quests: list,            # status='in-progress' rows
      scene_state: dict,
  ) → (body: str, signals: dict)
```

**Suggester call site:** `_dm_respond_and_post` in `discord_dnd_bot.py`, AFTER narration posts (sibling to scene_lifecycle counter update). If proposal returned, dispatches `#dm-aside` card via `_post_dm_aside`. Suggester does NOT write `dnd_quests`. Always-fire log: `quest_offer_proposed: campaign=N voicer_npc=N quest_id=N proposed=0|1 reason=...`.

**Directive call site:** `dm_respond` in `dnd_engine.py`, AFTER consequence directive (per §1.F placement decision), passes directive body to `build_dm_context` as new param. Always-fire log: `quest_directive: campaign=N active_count=N fired=0|1 chars=N`.

**State writes** are §17-disciplined single-writer helpers extending the existing trio:
- `quest_offer(campaign_id, quest_id, offer_npc_id, offer_turn) → bool` — transitions any → offered, sets `offer_npc_id` + `offered_turn`. Fires from operator paste detection OR `/quest offer accept` (which then immediately transitions to in-progress).
- `quest_accept(campaign_id, quest_id, accept_turn) → bool` — transitions offered → in-progress, sets `accepted_turn`.
- `quest_deliver(campaign_id, quest_id, deliver_turn) → bool` — transitions in-progress → completed (delivered), sets `delivered_turn`.
- `quest_abandon(campaign_id, quest_id) → bool` — transitions offered|in-progress → abandoned.
- Existing `quest_set_status` continues to work for `quest_fail` (no new audit column needed).

**Operator-paste detection.** When operator pastes the suggester's proposed dialogue into `#dm-narration`, the engine detects the paste (signature: text matches the proposed `offer_dialogue_seed` within a fuzziness tolerance, OR explicit `/quest offer accept <id>` slash command was issued). Detection writes `quest_offer` then immediately `quest_accept` (two-step audit; paste detection is treated as both offer and acceptance — the in-fiction offer-and-immediate-acceptance pattern Matt uses 36.8% of the time per LR findings).

Actually — re-thinking. The cleaner model: paste-detection writes only `quest_offer` (offered_turn set, status='offered'). The operator then types `/quest offer accept <id>` after the party commits in-character. This preserves the two-state lifecycle visibly. Pure-paste-as-acceptance collapses the lifecycle and loses the structural commitment moment. **Locked recommendation: paste detection → `quest_offer`; explicit `/quest offer accept` → `quest_accept`.** Per §11.4 if operator chooses the auto-accept-on-paste option, the spec walks that.

**State machine** (engine-deterministic, §1a-aligned, LLM never writes status):
```
                                  /quest offer decline
                                       ↓
                            (no-op / row stays at default 'in-progress' if was '/quest add')
                                       ↑
(skeleton hook in DB at offered) → /quest seed-skeleton
                ↓
            offered → /quest offer accept → in-progress
                ↓                              ↓
            abandoned                    /quest deliver → completed (delivered)
                ↓                              ↓
                                            failed (via /quest fail)
                                            abandoned (via /quest abandon)
```

LLM reads `status='in-progress'` quests via the active-quest directive. LLM never sees offered/completed/failed/abandoned quests in prompt context. State transitions surface to the LLM only via the next turn's directive shift (an accepted quest appears in the directive block; a completed quest disappears from it).

---

## §4. NPC-voiced offer shape (LR 36.8% port)

The `compute_quest_offer_suggester` emits a structured proposal dict; the dispatch site renders it as the `#dm-aside` suggester card. Card format:

```
[QUEST OFFER PROPOSED]
NPC voicer: Eldrin Stormbow (skeleton_origin=1, at Stoneforge Guild Hall)
Quest #2: Investigate the goblin-ravaged farmstead
Reward: 75gp + Guild favor
Suggested offer dialogue:
"Eldrin scans the brush ahead, then turns back to you: 'There's a farmstead two leagues east, off the Trade Road. Goblin sign all around it. Guild's offering seventy-five gold to anyone willing to clear it out. You'd be doing the road a favor.'"

[Actions]
- Paste the dialogue above into #dm-narration to render the offer in scene (engine logs offer-card-rendered).
- Type `/quest offer accept 2` after the party commits to the quest in-character.
- Type `/quest offer decline 2` to dismiss without offering.
```

**Where the offer dialogue comes from:** §11.10 decision. Three candidates:
- **(a) static skeleton-authored** — operator writes the dialogue in skeleton.md alongside the quest hook. Predictable, zero LLM cost, zero hallucination risk. Cost: operator writes ~3 sentences per quest hook.
- **(b) LLM-generated at suggester time** — small advisory-parser-style call to a fast model with the quest title + voicer name + reward + scene context → emits proposed dialogue. Reusable across quests. Cost: per-suggester LLM call (~500ms, ~$0.001).
- **(c) hybrid** — skeleton-authored dialogue is the source-of-truth; LLM-generated fallback when skeleton lacks dialogue. Inherits both costs and both benefits.

**Recommendation: (c) hybrid.** Operator-authored dialogue is canonical when present; LLM fallback covers the v1.x emergent-quest case automatically. Skeleton.md parser extracts optional `offer_dialogue` field per quest hook. If absent, suggester emits LLM-generated dialogue (with the AUTHORITATIVE framing pattern from S22 #2 to prevent drift).

**§1a-aligned.** The state mutation (insert at `status='offered'`) happens on operator paste detection — not on LLM dialogue narration. LLM-as-NPC voices the offer; engine writes the row. Standard §1b suggester pattern.

---

## §5. State machine — engine-deterministic only

Five statuses lock the lifecycle (extending the existing enum per §1.B):
- `offered` — Virgil-as-DM has proposed; party has not yet committed. Quest is visible in `/quest list` but NOT in active-quest directive.
- `in-progress` (alias `active` for back-compat) — operator confirmed acceptance; quest is on the active-quest list. **The only status the LLM sees in directive context.**
- `completed` (alias `delivered`) — operator confirmed completion; reward dispatch fires; quest exits active list. Visible in `/quest list status:completed`.
- `failed` — operator confirmed failure; reward NOT dispatched. Visible in `/quest list status:failed`.
- `abandoned` — operator confirmed walked-away OR offer declined. No reward. Visible in `/quest list status:abandoned`.

**Transition writers are §17-disciplined.** Single function per transition; all transitions write the appropriate timestamp column (`offered_turn`, `accepted_turn`, `delivered_turn`). No `dnd_quests_audit` separate table at v0 — the timestamp columns ARE the audit trail (cleaner than the S27 `dnd_time_advancements` pattern since each transition is exactly one row update on the existing row, not an append-only event log). If v1.x adds auto-transitions (sketch §5 candidate), `dnd_quests_audit` becomes the natural extension at that time.

**LLM never writes status, but reads `status='in-progress'` rows.** Other statuses are invisible to prompt context. The active-quest directive renders ONLY `in-progress` (with the `active` alias mapped at render time).

**Engine-deterministic auto-transitions deferred to v1.x:** none at v0. Candidates: `delivered` auto-fires when a `dnd_consequences` row with `kind='quest_outcome'` upserts (cross-ledger coupling); `abandoned` auto-fires after N session-days with no engagement signal. Both require corpus-grounded threshold calibration. v0 is operator-driven only.

---

## §6. Recon findings

Six items, evidence-backed against the live codebase (May 13, 2026).

---

### R1. `/quest` slash-command surface — five commands, one autocomplete helper, fully integrated

**Evidence:** `discord_dnd_bot.py:5095-5260`.

**Commands shipped:**
| Command | Gate | Calls engine | Purpose |
|---|---|---|---|
| `/quest add <title> [summary] [priority] [given_by]` | DM | `quest_add()` | Insert new active quest |
| `/quest list [status]` | PLAYER | `get_all_quests()` | Display quests (filterable) |
| `/quest complete <quest_id>` | DM | `quest_set_status('completed')` | Mark complete |
| `/quest fail <quest_id>` | DM | `quest_set_status('failed')` | Mark failed |
| `/quest delete <quest_id>` | DM | `quest_delete()` | Hard delete row |

`quest_id_autocomplete` helper (`discord_dnd_bot.py:5100`): returns `#{id} [{status}] {title}` choices.

**v0 delta (per §1.H):** ADD `/quest seed-skeleton`, `/quest offer accept <id>`, `/quest offer decline <id>`, `/quest deliver <id>`, `/quest abandon <id>`. KEEP existing five. Total post-v0: 10 commands.

**Finding:** existing surface is integrated but thin (no offered-status path, no NPC-voicer surface). Extension preserves back-compat.

---

### R2. `dnd_quests` schema — 9 columns, 3-status enum, §17-compliant single writers

**Evidence:** `dnd_engine.py:422-432` (CREATE TABLE), `dnd_engine.py:2586-2671` (write paths).

**Current schema:**
```sql
CREATE TABLE dnd_quests (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id  INTEGER NOT NULL,
    title        TEXT    NOT NULL,
    summary      TEXT    DEFAULT '',
    status       TEXT    DEFAULT 'active',
    priority     TEXT    DEFAULT 'normal',
    given_by     TEXT    DEFAULT '',
    created_at   TEXT    NOT NULL,
    updated_at   TEXT    NOT NULL
);
CREATE INDEX idx_quests_campaign_status ON dnd_quests(campaign_id, status);
```

`VALID_QUEST_STATUSES = {'active', 'completed', 'failed'}` (line 2586).
`VALID_QUEST_PRIORITIES = {'low', 'normal', 'urgent'}` (line 2587).

**Single-writer compliance per §17:** ✅. Writes flow through `quest_add` / `quest_set_status` / `quest_delete`. No parallel writers. Status enum validated at `quest_set_status` boundary (§16 compliant).

**Status enum compatibility audit (per session brief refinement):**
- Existing: 3 statuses (`active`, `completed`, `failed`)
- Sketch §5: 5 statuses (`offered`, `in-progress`, `delivered`, `failed`, `abandoned`)
- **Semantic mapping:** `active` ↔ `in-progress`; `completed` ↔ `delivered`; `failed` ↔ `failed`. Missing: `offered`, `abandoned`.
- **Migration constraint:** existing rows in other campaigns (if any — campaign 17 has 0; full audit at extension time) carry `active|completed|failed`. v0 extends the enum additively (per §1.B alias path), preserving back-compat.

**Missing fields per sketch §2:** `offer_npc_id` (FK), `offered_turn`, `accepted_turn`, `delivered_turn`, `reward_summary`, `skeleton_origin`. All six are additive (NULL defaults preserve existing row validity).

**Finding:** existing schema is thin but well-disciplined. Extension is clean. Sketch's "new table vs extend" §11.2 decision lands on extend (§1.A).

---

### R3. Active-quest prompt-render — two surfaces (footer + prompt block); zero §59 telemetry

**Evidence:**
- **Prompt block:** `dnd_engine.py:2674` `quests_to_prompt_block(quests, max_shown=5)`. Returns `=== ACTIVE QUESTS ===` block. Active-only filter. Priority-ordered (urgent > normal > low). Capped at 5 quests rendered with overflow notice. Format: `- {title} (given by X, urgent): {summary}`.
- **Block injection:** `dnd_engine.py:5449-5453`. `quests_section = "\n\n" + quest_block`. Injected at `dnd_engine.py:5495` as `{quests_section}` — placement is BEFORE most directives (mode_block, scene_state_section, then quests_section, then char_ctx_section). NOT in the tactical band.
- **Block suppression:** `if not suppress_for_combat_narration` (line 5450). Suppressed in combat.
- **Footer surface:** `discord_dnd_bot.py:3108-3118` (`_dm_respond_and_post`) and `4530-4538` (`/play` opening). Renders `🗒️ {title1}, {title2}, …` line, capped at 200 chars. Active-only. Soft-fail.
- **State-aware footer integration:** `dnd_orchestration.py:3268, 3377, 3448` — `active_quests` is a parameter threaded through `render_state_footer` (Track 6 #1 §59 sibling).

**Finding:** Two render surfaces are integrated. Prompt block is a thin string-formatter (no `(body, signals)`, no telemetry, no soft-fail at call site). v0 promotes prompt block to §59 sibling pattern (`compute_active_quest_directive`) per §1.F. Footer surface stays as-is (already integrated cleanly via `render_state_footer`'s active_quests param).

**Placement decision (§11.8):** existing prompt-block placement is non-tactical (high in prompt). Move to tactical band, AFTER consequence_block, BEFORE scene_lifecycle_block. Tactical-band placement aligns quest pressure with consequence pressure and follows the established "tactical = immediate-stakes directives" ordering.

---

### R4. Skeleton-quest mapping in campaign 17 — ZERO DB rows; skeleton text is the only canon source

**Evidence (live DB query, May 13 2026):**
```sql
SELECT id, title, summary, status, priority, given_by, created_at
  FROM dnd_quests WHERE campaign_id=17 ORDER BY id ASC;
-- (0 rows)

SELECT COUNT(*) AS total_rows, SUM(CASE WHEN status='active' THEN 1 ELSE 0 END) AS active_rows
  FROM dnd_quests WHERE campaign_id=17;
-- 0|<null>  (zero rows total, zero active)
```

**Skeleton.md content (campaign 17, `/home/jordaneal/scripts/campaigns/17/skeleton.md:9-12`):**
```
## Major hooks
- Escort the merchant caravan from Stonebridge to Redhaven by dawn
- Investigate the goblin-ravaged farmstead on the road
- Survey the lost mine near the Crystal Caves
```

**The three hooks reach the LLM only via the skeleton prompt block prepended by `get_skeleton_prompt_block()`.** There is no `skeleton_origin=1` quest row, no NPC-voicer mapping, no offered-state surface. The footer's 🗒️ field renders empty. The `=== ACTIVE QUESTS ===` prompt block is suppressed (no active rows).

**Finding:** v0 needs `/quest seed-skeleton` (§1.C) to bridge skeleton hooks into the DB. Without it, the suggester surface has nothing to offer (`offerable_quests` would always be empty). Seed-skeleton is a v0 prerequisite, not a v1.x candidate.

---

### R5. Consequence layer pattern — six reusable patterns, three forks for quest layer

**Reusable for quest layer:**

1. **Single-writer §17 helpers.** `consequence_upsert`, `consequence_emit_surface`, `maybe_promote_consequences` (`dnd_engine.py:4363, 4493, 4542`). Quest layer extends with `quest_offer`, `quest_accept`, `quest_deliver`, `quest_abandon`.

2. **Severity/priority cap-3 with priority-then-recency ordering.** `compute_consequence_directive` (`dnd_orchestration.py:1571-1668`). Sort: `severity DESC, last_surfaced_turn DESC NULLS LAST, id ASC`. Cap at 3 rendered rows. Quest layer adopts: cap at 3 in-progress quests rendered, priority DESC, accepted_turn DESC, id ASC.

3. **AUTHORITATIVE/EXHAUSTIVE framing pattern.** Inherited from S22 #2 loot v1.1 ("supersedes any prior narration"). Quest directive adopts: `=== ACTIVE QUESTS (AUTHORITATIVE — these are the outstanding commitments) ===`. Block tells the LLM these quests are real commitments, not optional flavor.

4. **Read-only `/consequence list` debug command pattern.** `dnd_engine.py:4612` `consequence_list_for_command`. No add/remove (validator-contract preservation per WHY.md L518-523). Quest layer: existing `/quest list` already matches this; `/quest delete` is the documented exception. KEEP `/quest delete` since the v0-introduced operator-side write surface (`/quest add`, `/quest offer accept`, etc.) is broader than consequence layer's pure-parser source — operators need an "undo" lever.

5. **Async background `_extract_and_persist_world` thread pattern.** `discord_dnd_bot.py:3128` `asyncio.create_task(_extract_and_persist_world(...))`. v0 does NOT add quest extraction (per §1.C: skeleton hooks only at v0). v1.x emergent-quest extraction adopts this thread (per §12.2).

6. **Promotion-with-distribution-check (three-axis: count, age, distinct turns).** `maybe_promote_consequences` (`dnd_engine.py:4542`). Quest layer adopts the pattern conceptually for v1.x auto-transitions (`delivered` auto-fires when quest's outcome-consequence promotes), not at v0.

**Forks (quest-specific, no consequence-layer analog):**

1. **State machine — five statuses with lifecycle transitions.** Consequences are capture-only with promote-to-trait. Quests have a directional lifecycle (offered → in-progress → delivered/failed/abandoned). Different state-transition discipline.

2. **NPC-voicer routing.** Consequences emerge from narration without a designated voicer. Quests have a voicer-of-record (`offer_npc_id`). LR 36.8% port surfaces in offer dialogue.

3. **`#dm-aside` suggester card dispatch.** Consequence layer renders directly into the prompt; no suggester surface. Quest layer adopts the §1b suggester pattern (Track 6 #5.1 + S41 precedent), routing offers through operator approval before any state writes.

---

### R6. Prompt-size baseline post-Scene-Lifecycle v1 live

**Evidence (live, May 13 2026, post-Scene-Lifecycle v1 verified at 12:22):**

Sample window: 11:39–12:28, 30 exploration turns, campaign 17.
- **Total prompt:** 24,563 – 27,982 chars (mean ≈25,400). Median ≈25,300.
- **Directives component:** 5,538 – 6,475 chars (mean ≈5,640). 80% of turns at 5,538 (baseline) — Scene Lifecycle's threshold-fired directive adds ~937 chars when it fires (tier=strong observed at 12:22:30).
- **Retrieval component:** 414 – 1,454 chars. High variance, scene-dependent.
- **System (base):** 20,539 – 23,518 chars (mean ≈21,700). Skeleton block, scene state, persistent context.

**Quest layer v0 projected delta:**
- **Active-quest directive:** ~300-500 chars when firing (1-3 quests rendered, ~100 chars per quest with reward + given-by annotations + framing). Below firing threshold (zero in-progress quests): 0 chars. Net: same selective-fire shape as Scene Lifecycle.
- **Suggester card:** 0 prompt chars (posts to `#dm-aside`, not into the LLM prompt). Adds zero prompt-budget pressure.
- **Skeleton-block delta from `## Quest hooks` section addition:** ~200-400 chars (3 hooks × ~80 chars each, plus voicer + reward metadata). One-time addition to skeleton prompt block; recurring per turn at zero variable cost.

**Net projected total post-v0:** mean ≈25,800-26,000 chars (a ~1-2% increase). Well within prompt-size headroom. No optimization pressure.

**Finding:** quest layer is prompt-budget-cheap. Baseline numbers confirm the sketch's §8 estimate (~300-500 chars directive). No architectural change needed for budget reasons.

---

## §7. §76 four-property latent-canon audit

New `dnd_quests` columns added by v0, each scored against the four properties per Doctrine §76:

| New column | LLM-writable? | Persisted? | Retrieved? | Narratively inferential? | Score | Verdict |
|---|---|---|---|---|---|---|
| `offer_npc_id` | No (FK; §17 helper writes) | Yes | Yes (resolved via JOIN for directive render) | No (integer FK, not text) | 1/4 | Safe |
| `offered_turn` | No (§17 helper writes timestamp) | Yes | No (not retrieved into prompt at v0) | No (integer) | 1/4 | Safe |
| `accepted_turn` | No (§17 helper writes timestamp) | Yes | No (not retrieved into prompt at v0) | No (integer) | 1/4 | Safe |
| `delivered_turn` | No (§17 helper writes timestamp) | Yes | No (not retrieved into prompt at v0) | No (integer) | 1/4 | Safe |
| `reward_summary` | Mixed (skeleton-authored OR operator-typed at v0; LLM-extracted only via narrow-exception v1.x parser when emergent quests land) | Yes | Yes (rendered in directive block) | **Borderline** (a string like "50gp + Guild reputation" is enumerable; a string like "the deepest gratitude of the Hollowmoor villagers" is narratively inferential) | 2-3/4 | Audit-watch |
| `skeleton_origin` | No (§17 helper writes flag at seed-skeleton time) | Yes | No (used for filter, not rendered into prompt) | No (integer flag) | 1/4 | Safe |

**`reward_summary` audit notes:** At v0, the column is operator-authored (via `/quest add`'s `summary` field for emergent operator-quests, OR skeleton.md's `reward:` field for skeleton-authored quests). Both are non-LLM-writable. The directive renders it in the active-quest block, which is retrieved property = Yes. Narrative-inference risk depends on operator's authoring discipline — a structured "50gp + Guild reputation" is enumerable; a freetext "their lasting gratitude" invites narrative elaboration.

**Operational mitigation:** §11.K candidate — recommend skeleton.md `reward:` field uses a structured-vocabulary convention ("Ngp" / "<faction> reputation" / "<faction> favor" / "named item"). Free-text reward summaries are allowed but flagged in logs as `reward_summary_freetext: campaign=N quest_id=N` for audit-trail visibility. If v1.x emergent-quest extraction lands, the parser MUST use structured-vocabulary output to keep `reward_summary` out of 4/4 audit territory.

**Status enum extension:** `offered` and `abandoned` are new enum values, not new columns. §76 doesn't apply to enum extensions (the column itself was already audited at original add-time and remains 0/4 — fixed-enum, deterministic writes).

---

## §8. Test plan sketch

Test surface for v0 implementation:

**Engine tests (`test_quest_layer.py`):**
1. `quest_offer` writes `status='offered'`, `offer_npc_id`, `offered_turn` — single-call test.
2. `quest_accept` requires prior `status='offered'`, refuses from other statuses (engine-defends-its-own-invariants per §16).
3. `quest_deliver` requires prior `status='in-progress'`.
4. `quest_abandon` accepts offered OR in-progress; refuses delivered/failed/abandoned (idempotent).
5. Status enum extension: `quest_set_status` accepts new values, refuses bogus ones.
6. `quest_set_status` aliases `active` ↔ `in-progress` correctly (per §1.B).
7. `skeleton_origin=1` rows aren't deleted by `quest_delete` without operator confirmation (§19 destructive-gate pattern; one-line refusal at write boundary).

**Orchestration tests (`test_quest_directive.py`):**
8. `compute_quest_offer_suggester` returns None when zero offerable quests.
9. Returns proposal when one offerable quest matches voicer at current location.
10. Returns None when cooldown is active (turns_since_last_offer < `_QUEST_OFFER_COOLDOWN`).
11. Returns None when mode='combat'.
12. Priority-rule fallback fires when no skeleton-authored voicer mapping exists.
13. `compute_active_quest_directive` returns `('', signals)` when zero in-progress quests.
14. Returns block with up to 3 quests when more exist; priority-ordered.
15. AUTHORITATIVE framing string present.
16. Signals dict contains: `fired`, `active_count`, `tier` (always 'auto' at v0).

**Integration tests (`test_quest_integration.py`):**
17. `/quest seed-skeleton` is idempotent (running twice doesn't duplicate).
18. `/quest seed-skeleton` parses campaign 17's skeleton.md correctly (3 rows inserted, voicer FKs resolved or NULL-logged).
19. Operator paste detection: a paste matching the proposer's `offer_dialogue_seed` writes `quest_offer` row (fuzziness tolerance test).
20. Active-quest directive renders after `/quest offer accept` and disappears after `/quest deliver`.

**Regression sweep:** existing `test_*.py` test suite passes after `dnd_quests` schema extension (additive columns; existing rows + helpers unaffected).

---

## §9. Live-verify scenarios

Six scenarios for post-implementation Discord live verify (deferred to operator).

1. **`/quest seed-skeleton` cold:** campaign 17 has 0 quests → run command → 3 rows at `status='offered'`, `skeleton_origin=1`, voicer FKs resolved (Eldrin/Borin per §1.D if skeleton.md is extended; NULL otherwise). Log: `quest_seed: campaign=17 inserted=3 voicer_resolved=N voicer_unresolved=N`.
2. **Suggester proposes during exploration:** party is at Stoneforge Guild Hall with Eldrin (skeleton_origin=1). After N turns, `#dm-aside` receives a `[QUEST OFFER PROPOSED]` card for one of the unoffered hooks. Log: `quest_offer_proposed: ...`.
3. **Operator paste triggers offer state:** operator copies the proposed dialogue, pastes into `#dm-narration`. Engine writes `status='offered'` (turn captured). Log: `quest_offer: campaign=17 quest_id=N offer_npc_id=N offered_turn=N`.
4. **Explicit `/quest offer accept`:** operator types `/quest offer accept <id>`. Engine writes `status='in-progress'`. Next turn's prompt shows the quest in the `=== ACTIVE QUESTS ===` block. Log: `quest_accept: campaign=17 quest_id=N accepted_turn=N`.
5. **Active-quest directive fires:** with one in-progress quest, every exploration turn's prompt includes the active-quest block. Log: `quest_directive: campaign=17 active_count=1 fired=1 chars=N`.
6. **`/quest deliver` dispatches reward and clears active list:** operator types `/quest deliver <id>`. `#dm-aside` receives reward summary post (per §1.G). Inventory auto-add fires if reward parses cleanly. Quest exits active list. Log: `quest_deliver: campaign=17 quest_id=N delivered_turn=N reward_parsed=1|0`.

---

## §10. Telemetry

Always-fire log lines (per §59 contract — log on every turn evaluated, even when nothing fires):

- `quest_directive: campaign=N active_count=N fired=0|1 chars=N` — every `_dm_respond_and_post` exploration/social turn.
- `quest_offer_proposed: campaign=N voicer_npc_id=N voicer_npc_name='X' quest_id=N quest_title='X' proposed=0|1 reason=...` — every suggester invocation. `reason` populated when proposed=0 (`mode_gate` / `no_offerable` / `cooldown` / `no_voicer_match`).

Per-event log lines (fire only on the event):

- `quest_seed: campaign=N inserted=N voicer_resolved=N voicer_unresolved=N` — `/quest seed-skeleton` invocation.
- `quest_offer: campaign=N quest_id=N offer_npc_id=N offered_turn=N source=paste|slash` — `quest_offer` write.
- `quest_accept: campaign=N quest_id=N accepted_turn=N` — `quest_accept` write.
- `quest_deliver: campaign=N quest_id=N delivered_turn=N reward_parsed=0|1 reward_summary='X'` — `quest_deliver` write.
- `quest_abandon: campaign=N quest_id=N source=decline|abandon` — `quest_abandon` write.
- `quest_paste_match: campaign=N quest_id=N similarity=0.NN matched=0|1` — paste-detection invocation (per turn that matches; fuzziness tolerance per §11.7).

Calibration targets (post-v0 live):
- Suggester noise rate: proposed-rejected fraction (operator declines or ignores the card).
- Acceptance latency: turns between `quest_offer` and `quest_accept`.
- Delivery latency: turns between `quest_accept` and `quest_deliver`.
- Cooldown saturation: percentage of suggester invocations rejected by cooldown.

---

## §11. Decision points — operator's call required

Twelve decisions for operator lock before implementation opens (Session 2 review). Code's leans noted; genuine uncertainty flagged.

### §11.1 — Quest source taxonomy at v0

**Question:** Skeleton-authored only? Operator `/quest add` retained? Advisory-parser extraction?

**Candidates:** (a) skeleton-authored + operator `/quest add` (existing path retained); (b) (a) + advisory-parser-extracted from narration; (c) skeleton-authored only (drop `/quest add` until v1.x).

**Recommendation: (a).** v0 ships skeleton-authored + operator-added (existing `/quest add` continues to work). Advisory-parser extraction is v1.x once seed-skeleton's offer-suggester signal is grounded.

**Confidence: HIGH.** Mirrors consequence layer's structural-first-extraction-later discipline (S16 precedent).

---

### §11.2 — `dnd_quests` schema shape: extend vs new table

**Question:** Add columns to existing `dnd_quests`, or create new `dnd_quests_v0` parallel?

**Candidates:** (a) extend additive columns; (b) parallel new table; (c) extend `dnd_consequences` with `kind='quest'`.

**Recommendation: (a).** Existing surface is integrated (5 slash commands, footer, prompt block). Additive columns preserve back-compat. Parallel table multiplies write paths and requires migration. Consequence-kind reuse muddies both ledgers' semantics (different state machines, different prompt shapes).

**Confidence: HIGH.** Per §1.A reasoning.

---

### §11.3 — Offer-trigger predicate

**Question:** When does `compute_quest_offer_suggester` fire?

**Candidates:** (a) every turn with `mode in {social, exploration}` AND `skeleton_origin=1 NPC at location` AND unoffered-quest mapping; (b) (a) + cooldown N turns since last offer-card; (c) operator-initiated only via `/quest suggest`; (d) advisory-parser-extracted ("LLM proposes 'this scene feels like a quest moment'").

**Recommendation: (b) — auto-fire with cooldown.** (a) without cooldown floods `#dm-aside`. (c) puts work on operator; defeats the §1b suggester pattern's value. (d) requires v1.x infrastructure.

**Confidence: MEDIUM.** Cooldown threshold `_QUEST_OFFER_COOLDOWN = 6` is calibration-from-telemetry. Tune from `quest_offer_proposed:` log signal post-ship.

---

### §11.4 — Acceptance semantics

**Question:** How does an offered quest transition to in-progress?

**Candidates:** (a) explicit `/quest offer accept <id>` slash only; (b) implicit detection from player text ("we'll take the job"); (c) operator paste of offer-dialogue auto-accepts (collapsing offered→in-progress on single paste).

**Recommendation: (a) explicit slash.** Same architectural call as Scene Lifecycle T2 deferral (`SCENE_LIFECYCLE_V1_SPEC.md` §11.N): phrase-vocabulary detection on player text is a false-positive risk. (c) collapses the two-state lifecycle and loses the structural commitment moment.

**Confidence: HIGH.** Per §1.H reasoning.

---

### §11.5 — Reward magnitude calibration source

**Question (per session brief refinement):** At v0 — skeleton-authored only. At v1.x emergent quests — DMG-by-level vs LR-X4?

**Candidates:**
- **(a) DMG-by-level baseline** (DMG p.133 treasure tables — published 5e mechanical balance)
- **(b) LR-X4 corpus pull** (CRD3 reward-magnitude data — empirical real-DM cadence)
- **(c) operator-locked-per-quest via skeleton.md** (v0 scope; skeleton.md `reward:` field carries operator's call)

**Recommendation at v0: (c).** Skeleton-authored quests carry operator's intent verbatim. No auto-calibration at v0. Auto-calibration (a) vs (b) is a §11.5 decision deferred until emergent-quest extraction lands (v1.x).

**Confidence: HIGH at v0; (a) vs (b) is operator + Oracle when emergent quests ship.**

**Operator + Oracle walk required for v1.x.** Source must be named in spec when emergent quests ship; do not bury in constants.

---

### §11.6 — Reward delivery surface

**Question:** When `/quest deliver` fires, what surfaces?

**Candidates:** (a) auto-LLM-render of reward scene; (b) `#dm-aside` post with reward summary for operator paste; (c) auto-add reward items to inventory via existing `add_item`; (d) combination of (b) + (c).

**Recommendation: (d) hybrid.** (b) keeps narration operator-controlled. (c) reuses inventory primitives, avoids reward hallucination drift (F-39 precedent). (a) auto-LLM-render is the historical loot-hallucination failure mode.

**Confidence: HIGH.** Per §1.G reasoning. Inherits Track 4 #2 loot v1.2 lessons.

---

### §11.7 — Operator paste-detection fuzziness tolerance

**Question:** When operator pastes the suggester's proposed dialogue, what's the match threshold for triggering `quest_offer` write?

**Candidates:** (a) exact match (entire `offer_dialogue_seed` must appear verbatim in `#dm-narration`); (b) cosine-similarity above threshold (e.g. ≥0.85); (c) prefix match (first 50 chars match); (d) tag-based — paste includes an embedded `[QUEST_OFFER:<id>]` token.

**Recommendation: (b) cosine-similarity ≥0.85.** Operator may edit the proposed dialogue lightly before pasting; (a) exact match breaks on whitespace edits. (d) requires operator to type a hidden token, defeating the §1b "paste-the-dialogue-as-rendered" UX. (c) prefix-match handles light edits cleanly but breaks on intro tweaks.

**Confidence: MEDIUM.** Threshold 0.85 is a starting point; calibrate from `quest_paste_match:` telemetry. Fallback: explicit `/quest offer accept <id>` is always available regardless of paste-detection outcome.

---

### §11.8 — Active-quest directive prompt placement

**Question:** Where in `build_dm_context` does the directive render?

**Candidates:** (a) AFTER consequence_block, BEFORE persistence_block (tactical band, same tier as consequences); (b) keep existing early placement (after scene_state_section); (c) both (existing block stays + new directive renders in tactical band).

**Recommendation: (a) relocate to tactical band.** Tactical band carries immediate-stakes directives (consequence pressure, scene lifecycle). Quests are outstanding commitments — tactical-band pressure aligns. Early placement is appropriate for scene-state framing, not for "the world expects work from you" pressure.

**Confidence: MEDIUM.** Footer 🗒️ stays as ambient surface regardless.

---

### §11.9 — Quest auto-render cooldown vs every-turn

**Question:** Does `compute_active_quest_directive` fire on every exploration/social turn, or cooldown-gated?

**Candidates:** (a) every turn with one concise block (no cooldown); (b) cooldown N turns between fires; (c) tier-escalation — quiet fire for stable in-progress quests, strong fire for newly-accepted or aging-without-progress.

**Recommendation: (a) every turn, one concise block.** Quest pressure is ambient — the LLM should always know what's outstanding. Block stays small (3-line cap). Tier-escalation (c) is v1.x once "aging without progress" has corpus-grounded thresholds.

**Confidence: HIGH.** Same shape as consequence directive (every-turn, severity-capped).

---

### §11.10 — Offer-dialogue source

**Question:** Where does the suggester's proposed dialogue text come from?

**Candidates:** (a) static skeleton-authored only (no LLM call at suggester time); (b) LLM-generated at suggester time (advisory-parser-style call); (c) hybrid — skeleton-authored when available, LLM-generated fallback.

**Recommendation: (c) hybrid.** Operator-authored dialogue is canonical when present. LLM fallback covers operator-doesn't-author-every-line case AND v1.x emergent-quest dialogue. AUTHORITATIVE framing on the LLM fallback prevents drift.

**Confidence: MEDIUM.** LLM-fallback noise rate (does the LLM produce off-tone offer dialogue?) is unknown until live. If high noise, fall back to (a) and require skeleton.md dialogue.

---

### §11.11 — `/quest abandon` access — DM-only or player-accessible

**Question:** Who can abandon a quest?

**Candidates:** (a) DM-only (matches `/quest add`, `/quest deliver`, `/quest fail`); (b) player-accessible (player declares "we abandon the lost mine quest" in-character → `/quest abandon` available to them).

**Recommendation: (a) DM-only.** Quest abandonment is a DM-narrative-authority decision (cf. Scene Lifecycle §11.F `/compress` DM-only). Players signal abandonment intent through normal in-character speech; operator decides whether to honor it.

**Confidence: HIGH.** Mirrors Scene Lifecycle §11.F.

---

### §11.12 — §1a / §1b auto-suggester scrutiny — flag as §1b third project instance

**Question (per session brief flag):** Quest offer suggester fires automatically when predicate matches. Is this the §1a concern Scene Lifecycle's §11.M raised, or a clean §1b instance?

**Recommendation: §1b clean.** Joins Track 6 #5.1 SRD suggester (S26) + S41 NPC State-Sync as the THIRD project instance of §1b's suggester pattern. The architectural shape:

- **Bot proposes via `#dm-aside`** — `compute_quest_offer_suggester` emits, dispatch posts card. No bot-emitted Avrae command. No engine state mutation at this step.
- **Deterministic gate confirms safe to suggest** — predicate (mode, voicer match, cooldown, unoffered quest) gates the proposal. Suggester does NOT write `dnd_quests`.
- **DM approves by pasting (or `/quest offer accept`)** — operator decides whether to render the offer in scene.
- **Engine executes** — operator paste detection OR explicit slash triggers `quest_offer` write. Status mutation is engine-deterministic.

The architectural distinction from Scene Lifecycle's §11.M concern: there, the auto-fired directive constrains LLM narration directly (instruction-side enforcement). Here, the suggester routes through operator approval BEFORE any state change. The LLM-as-NPC voices the offer ON operator paste (a narration moment the operator initiated), not a state-changing decision the auto-fire injects into the prompt.

**Expected: clean §1b at spec review.** No operator + Oracle ambiguity expected. Walk surfaces the pattern's third instance, which the doctrine is already mature enough to absorb. If Session 2 review surfaces an unexpected §1a concern, falls back to the Shape B1 / B2 patterns (`SCENE_LIFECYCLE_V1_SPEC.md` §3.M, adapted): B1 = suggester proposes only at "soft" predicate (e.g. operator-typed `/quest suggest` only); B2 = `#dm-aside` post requires explicit `/quest offer accept` and never auto-fires the LLM narration. Both shapes are available if needed.

**Confidence: HIGH on the §1b lean; MEDIUM on "no ambiguity expected" — Session 2 review walks to confirm.**

---

## §12. Open questions filed forward — out of v0 scope

These surface during recon or are implied by v0 decisions but are not v0 work.

**§12.1 — Advisory-parser-extracted quest generation.**
Per §1.C scope: skeleton-authored only at v0. v1.x ship: small advisory parser reads narration for "quest-like moments" (the LLM narrates an NPC requesting help, party agrees in-character) → proposes new `dnd_quests` row via the §1b suggester surface. Requires phrase-vocabulary work for trigger detection + corpus grounding for false-positive rates. File: `quest_extractor.py` candidate. Same shape as `consequence_extractor.py`.

**§12.2 — Faction integration.**
Skeleton.md campaign 17 references Stoneforge Guild as the quest-source faction. v0 does NOT model factions as schema entities — `reward_summary` carries "Guild reputation" as a freetext string. v1.x ship: `dnd_factions` table + `dnd_npcs.faction_id` FK + faction-reputation ledger. Quest rewards reference faction IDs; reputation deltas apply on `quest_deliver`.

**§12.3 — NPC-to-NPC quest hand-off.**
"Eldrin says you should talk to the mayor about the goblins" — the offerer NPC redirects to a different NPC for the quest acceptance / delivery. v0 has one `offer_npc_id` per quest. v1.x extension: `accept_npc_id` and `deliver_npc_id` separately addressable. Same shape as commitment-directive's target-hint set.

**§12.4 — Composition-layer coupling.**
Silent per discipline note. Composition layer (piece 3 of mandate) will surface its own schema requirements. v0 schema is composition-extensible (FK to NPC, status enum, audit timestamps) without writing composition fields. Composition spec writes them when it ships.

**§12.5 — Auto-transition: `delivered` from consequence-of-kind='quest_outcome'.**
Cross-ledger coupling (sketch §5). When a `dnd_consequences` row of `kind='quest_outcome'` upserts with high confidence, the linked quest auto-transitions to `delivered`. Requires `consequence_extractor.py` extension to detect quest-outcome moments. v1.x ship; v0 is operator-driven only.

**§12.6 — Auto-transition: `abandoned` from N-session-days-of-no-engagement.**
Timeout-based auto-abandon. Requires session-day delta tracking against `dnd_time_advancements`. Threshold calibration from log signal (how long do real campaigns leave quests in-progress before they're effectively dead?). v1.x ship.

**§12.7 — Emergent quest reward magnitude calibration.**
§11.5 v1.x sub-decision. DMG-by-level vs LR-X4. Operator + Oracle walk required when emergent quest extraction lands.

**§12.8 — LLM-generated offer dialogue noise rate.**
§11.10 (c) hybrid. If LLM fallback produces off-tone dialogue at high rate, fall back to skeleton-authored-only. Calibrate from operator-rejection signal on suggester cards (operator declines vs accepts the proposed dialogue).

**§12.9 — Skeleton.md `## Quest hooks` parser.**
§1.D structured-section parser for `(title, voicer, reward, offer_dialogue)` per hook. Live skeleton.md format extension: backward-compatible additive (existing `## Major hooks` unstructured list continues to work; structured `## Quest hooks` is opt-in).

**§12.10 — `dnd_quests_audit` separate table.**
v0 uses timestamp columns for state-transition audit (cleaner than a separate audit table for v0 scope). v1.x if auto-transitions (§12.5, §12.6) need an audit log that records the trigger reason, not just the timestamp.

---

## §13. Out of scope — v0 explicitly does not

- LLM-classified intent feeding `dnd_quests.status` mutations (§1a: state machine is engine-deterministic).
- LLM-extracted reward summary for emergent quests at v0 (§1.C: skeleton-authored only).
- Faction modeling, faction reputation deltas (filed §12.2).
- Quest hand-off / NPC-to-NPC quest transfer (filed §12.3).
- Composition-layer schema coupling (filed §12.4).
- Auto-transition heuristics (filed §12.5, §12.6).
- Combat-mode quest offers (mode gate excludes combat).
- Player-typed in-character acceptance detection (`SCENE_LIFECYCLE_V1_SPEC.md` §11.N pattern, deferred per §1.H).
- Bot-emitted Avrae commands of any kind (§F-59 + §65 bot-Avrae write-boundary invariant).
- Any modification to `avrae_listener.py` parsing surface.
- Any modification to the adjudication layer.

---

## §14. Handoff

| Field | Value |
|---|---|
| **Spec status** | DRAFT — Phase 1 spec drafting complete (May 13, 2026). Session 2 = review pass (Opus medium per cadence table). |
| **Spec file** | `/home/jordaneal/virgil-docs/specs/QUEST_LAYER_V0_SPEC.md` |
| **§1 decisions** | 12 proposed decisions (§1.A–§1.L), all with recommendation + reasoning |
| **§11 count** | 12 decisions (§11.1–§11.12) require operator lock before Phase 3 implementation. 7 HIGH confidence, 4 MEDIUM, 1 §1b walk-to-confirm (§11.12). |
| **§12 count** | 10 open questions filed forward (§12.1–§12.10) |
| **HALT escalations** | 0 — required reading `planner-scratch/quest_layer_v0_sketch.md` was missing locally; retrieved from PC via rsync (placed at `/home/jordaneal/virgil-docs/planner-scratch/quest_layer_v0_sketch.md`) before recon opened. No content-level HALT. |
| **Recon findings** | R1: existing `/quest` surface = 5 commands, well-integrated, thin schema. R2: 3-status enum (active/completed/failed), §17-compliant, missing offered/abandoned + audit columns. R3: two render surfaces (footer 🗒️ + `=== ACTIVE QUESTS ===` block), non-tactical placement, zero §59 telemetry. **R4 CRITICAL: campaign 17 has zero `dnd_quests` rows** — skeleton hooks live only as prompt-block text. R5: 6 reusable consequence patterns + 3 forks. R6: prompt-size baseline mean ≈25,400 chars total / ≈5,640 directives; quest layer projected +300-500 chars when active. |
| **Architectural recommendation** | Extend existing `dnd_quests` (§1.A) — additive columns + enum extension. Skeleton-hook seeding via explicit `/quest seed-skeleton` command (§1.C). §1b suggester pattern third project instance (§1.E + §11.12). Operator-paste-detection with cosine-similarity tolerance for offer state-write trigger. |
| **Next session** | Session 2 = review pass. Opus medium per cadence (mature §59 sibling pattern with two existing precedents in motion-systems track, mature §1b suggester pattern with two existing precedents, clean recon finding set with one critical discovery (R4 zero-rows). Review walks §11.1–§11.12 with operator, locks decisions, spec flips DRAFT → LOCKED. Session 3 = implementation. |

---
