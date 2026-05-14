# Tier 1 Cleanup Arc — Triage Plan

**Status:** Plan. Operator review before dispatch.
**Date:** May 14, 2026
**Triggered by:** S64 live playtest + Horizon Review (Claude Opus 4.7, May 14)
**Cadence:** Multi-fix batched Code sessions. Three large ships instead of nine small ones.

---

## Severity-ranked findings

**P0 confirmed live (playtest-verified):**
- **F-021 `/play` NameError** — campaign-opener crashes; you bootstrapped via plain message at 1:05 AM. Every new campaign attempt hits Discord 3-second timeout.
- **`/travel` duration ignored** — Shape A confirmed via Midday → Afternoon screenshot. `/travel duration:"1 hour"` produces one full phase advancement (~4 hours in-fiction). Cosmetic field misleads.
- **DC-less roll requests** — fired twice in S64 (persuasion, investigation). Engine-side adjudication skipped; LLM free-narrates outcome. Track 7's mechanical-narrative boundary bypassed.
- **`#dm-aside` role confusion** — bot at 1:14 AM told you how to ask "your DM" to use correct pronouns. Virgil-as-bot doesn't know Virgil-as-DM is the same entity.

**P0 verified empirically by horizon reviewer (not yet playtest-confirmed):**
- **F-031 quest delivery silent inventory fail** — `add_item(campaign, '', ...)` returns `'invalid'` silently; `#dm-aside` reports success regardless. Every Quest Layer v0/v0.1 reward has been vapor.
- **F-035 loot evaporation** — combat loot surfaces in narration, never auto-claims; players must `/giveitem` manually each item.
- **F-026 no WAL mode, no scheduled backup** — single-mount failure loses campaign. 16-day-old snapshot. THE_GOAL's six-month vision is structurally fragile.

**P0 doctrinal (load-bearing architecture):**
- **F-016 `dnd_campaigns.current_scene` uncovered §76 loop** — Ship 2 (S39) closed §76 surfaces on `dnd_scene_state` but missed `dnd_campaigns.current_scene`. Four-property test passes 4/4. Exploration-mode scenes drift through prior-narration self-summarization.
- **F-008 AUTO_EXECUTE makes LLM the writer** — `QUEST_ADD|<title>`, `CLOCK_TICK`, `MODE` tail emissions write directly to `dnd_quests` / `clocks` / `dnd_scene_state`. §1a + §17 violation. If still firing in parallel with Quest Layer v0.1's §1b suggester, the third-instance anchor sits on a contaminated substrate.

**P1 file-forward (not in this arc):**
- F-006 multiplayer turn-gating — v1.x when friends join
- F-013 Chroma retention policy — observed-friction-gated
- F-056 `_open_db` helper — structural refactor after Tier 1 closes
- F-046 prompt injection guard — pre-non-friend-multiplayer
- F-022 / X-001 directive registry — premature consolidation
- F-068 character death — operator-managed by design

---

## Ship plan — three batched Code sessions

Path B cleanup-arc cadence (per S46-S52 precedent). Each session bundles related work into single dispatch. Live verify per session. No new architecture between sessions until Tier 1 closes.

### S65 — Front-door bugs + initialization layer

**Scope:**
- F-021 `/play` NameError fix (`{seed}` → `{scene or ''}` at lines 4870, 4876)
- F-008 AUTO_EXECUTE audit + close — grep for `AUTO_EXECUTE` emit sites, confirm whether `QUEST_ADD` / `CLOCK_TICK` / `MODE` still fire in parallel with Quest Layer §1b suggester. If yes, close the §1a-violating bypass (the proper fix depends on what's actually live; HALT-and-escalate to operator if the close is non-trivial).
- DC-less roll request fix — audit roll-request directive computation, surface why DC isn't attaching to roll proposals, fix the directive shape so engine-bound adjudication doesn't skip
- `#dm-aside` role-confusion fix — Virgil-as-bot needs to know it IS the DM when operator messages it in `#dm-aside` (current behavior treats operator-DM communication as third-party). Recon may surface this as a prompt-layer fix or a system-prompt augmentation for `#dm-aside` channel responses

**Rationale for bundling:** All four are front-door / initialization-layer bugs. F-021 breaks `/play` init; F-008 bypasses the §1b state-write gate that opens the campaign correctly; DC-less rolls bypass adjudication initialization per roll; role confusion bypasses Virgil's self-knowledge. Same architectural neighborhood (campaign and turn initialization correctness).

**Model:** Sonnet medium for F-021 + DC-less + role-confusion. Bump to Opus medium for F-008 if recon surfaces real architectural ambiguity about how to close the bypass without breaking Quest Layer's existing `/quest add` slash surface.

**Verify scenarios for operator post-restart:**
1. `/play` on existing campaign completes without spin
2. `/play` on test campaign opens scene cleanly
3. Skill check during play — bot proposes roll, Avrae rolls, engine-bound resolution renders (no "DC-less / skipped" log)
4. `#dm-aside` message about character pronouns — bot responds AS the DM, not as a third-party advisor
5. Grep `AUTO_EXECUTE` patterns post-patch — no `QUEST_ADD` / `CLOCK_TICK` / `MODE` writes via LLM emit path

---

### S66 — Time, travel, item delivery (the world-responds layer)

**Scope:**
- `/travel` duration → phase_delta translator. Operator-stated duration parses to in-fiction hours; floor-at-one-phase rule (any travel advances at least one phase; longer durations round to nearest phase). Preserves §17 four-source lock; fixes Shape A.
- F-031 quest delivery silent inventory fail — pass first-bound-character name (or party-stash sentinel) to `add_item`; check return value; surface `action='invalid'` honestly in `#dm-aside` instead of false-success
- F-035 loot auto-claim with refusal — `mark_loot_surfaced` also writes items to first-bound player's inventory; `/loot drop <id>` for explicit drop; narration surfaces "added to inventory" with refusal pointer

**Rationale for bundling:** All three are world-state-responds-to-action fixes. `/travel` makes time progression honor duration; F-031 makes quest delivery honor reward narration; F-035 makes combat loot honor item narration. The common pattern: the *engine* must do what the *narration* claimed. All three are the kind of bug where the bot lies about state.

**Model:** Sonnet medium throughout. Three clean fixes; no architectural ambiguity expected after recon.

**Verify scenarios:**
1. `/travel destination:"X" duration:"4 hours"` — confirm one phase advancement; `duration:"12 hours"` — confirm three phases; `duration:"1 hour"` — still one phase (floor); duration-field reflects actual delta in `#dm-aside`
2. `/quest deliver <id>` — items land in `dnd_inventory`; `/inventory` shows them; `#dm-aside` truthful
3. Combat ends with loot → next narration → `/inventory` shows loot items by default; `/loot drop <id>` works for explicit refusal

---

### S67 — Durability + §76 loop closure (the keep-the-campaign layer)

**Scope:**
- F-026 WAL mode + scheduled backup + automated PC push. Three composable changes per reviewer's §XIV patch:
  - `PRAGMA journal_mode=WAL` in `db_init()` and connection helper
  - Nightly cron: `sqlite3 virgil.db ".backup /mnt/virgil_storage/archive/virgil_$(date +%Y%m%d).db"` + 30-day retention
  - Automated post-snapshot `push-all-to-pc.sh` invocation for off-host durability
- F-016 §76 closure on `dnd_campaigns.current_scene` — Ship 2-style structural cut. Stop writing to `current_scene` from `_dm_respond_and_post`. Replacement substrate (`last_dm_response` on `dnd_scene_state`) already handles combat narration's chroma-bypass path; extend to exploration mode. Read-side: either delete the read or split `current_scene` into DM-authored field vs engine-only.

**Rationale for bundling:** Both are durability/integrity fixes. F-026 protects the campaign from physical loss; F-016 protects the campaign from doctrinal contamination (LLM self-summarization corrupting scene canon over time). Both are Ship 2-class structural work — small surface, large risk reduction, one-shot ships.

**Model:** Sonnet medium for F-026 (configuration + cron). Opus medium for F-016 if recon surfaces ambiguity about whether the `current_scene` read should be deleted entirely or split — Ship 2 made the parallel call for `dnd_scene_state` columns and the precedent applies, but `dnd_campaigns.current_scene` has different downstream readers worth confirming.

**Verify scenarios:**
1. `PRAGMA journal_mode;` returns `wal` post-patch
2. Cron job runs overnight; verify snapshot lands in `/mnt/virgil_storage/archive/`
3. Verify push-all-to-pc.sh runs post-snapshot; archive lands PC-side within 24h
4. Play through 5-turn exploration scene; observe that scene details (location specifics, NPC mentions) don't drift through prior-narration paraphrase across turns

---

## What's NOT in this arc

- Composition Layer v0.x patches if any (S62 was the last; nothing filed since)
- Quest Layer v1.x emergent-quest spec (filed forward; opens when authoring-friction surfaces)
- Scene Lifecycle Finding 2 soft-tier compliance (waits for hard-tier data accumulation)
- F-006 multiplayer two-tier banter buffer (v1.x candidate when friends join)
- X-001 directive registry refactor (premature; §59 pattern still mature at 15 instances)
- F-056 `_open_db` helper consolidation (real structural fix, but earns slot AFTER Tier 1 closes — folds into post-Tier-1 cleanup arc)

---

## Why this shape

S65, S66, S67 each batch four-to-three related fixes into one Code session. Trade-off: longer Code sessions vs operator/planner round-trips. The cost of round-trips (context reset, dispatch overhead, narrow per-session scope) was visible in S46-S52 cadence; bundling related fixes per architectural layer (init / world-responds / durability) reduces handoff cost.

Each session is independent. If S65 surfaces unexpected scope (F-008 audit larger than expected, role-confusion fix requires architectural change), S65 ships what it can and the rest defers to S65.1.

Live verify per session before next session dispatches. Discord verify is operator-side after restart; journal greps and DB queries support.

After Tier 1 closes: filed-forward Tier 2 (F-056, F-013, F-046, F-088) opens. Tier 2 is the structural cleanup arc post-bug-fix.

---

## Recommended next move

Dispatch S65 now. Three answers I need first:

1. **For F-008 AUTO_EXECUTE close:** if Code's audit shows `AUTO_EXECUTE QUEST_ADD` is still wired and bypassing Quest Layer §1b, do I HALT and escalate, or does S65 ship the close immediately as part of the bundle? My lean: ship the close if recon surfaces a clean fix; HALT if the close requires breaking changes to other features that consume the AUTO_EXECUTE pathway.

2. **For DC-less rolls:** is this a known feature (roll-without-DC is an intentional case for free-narrated outcomes) or a regression? If feature, the fix is different (surface DC at suggestion time so user knows it's free-narrated by design). If regression, the fix is at the directive-computation layer.

3. **For role-confusion:** is `#dm-aside` currently using the same system prompt as `#dm-narration`, or does it have a different prompt? Recon will surface this, but operator may know.

Answer or say "fire away" and I'll let Code's recon answer them.
