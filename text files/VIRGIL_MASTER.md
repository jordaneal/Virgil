# VIRGIL MASTER

**Current System State and Architecture**
Last updated: May 9, 2026 (S31 — ROADMAP 4c ships: `COMMANDS_PIN_BODY` pinned in `#commands` via `/setup`; `/dmhelp` rewired to runtime-fresh COMMANDS.md read per §66 — no more hand-maintained drift. Bug 1 architecture locked through spec discussion: footer-as-orchestration-state shift identified, phase-1/phase-2 telemetry-first split agreed, three new `footer_actor_changed` / `directive_bound_to_footer_actor` / `directive_creation_skipped_no_footer` log lines candidate. S30 — small-items batch shipped (Bug 2 max_tokens, F-29 titled-NPC, S26 commitment+empty diagnostic, npc_token_prefix_match) and Doc-catalog trim (ROADMAP −40KB, FAILURES −7KB, DOCTRINE −1KB). Footings queue EMPTY.)

This is the "what is the system today" reference. It does NOT contain:
- Working preferences → `WORKING_WITH_CLAUDE.md`
- Roadmap, status, next priorities → `ROADMAP.md`
- Architectural reasoning archive → `WHY.md`
- Per-session lessons → `sessions/SESSION_NN_*.md`

If a fact about the system isn't here, in WHY.md, or in a session file, it didn't happen.

---

## 1. System Environment

### Host
- Ubuntu Server 24.04 LTS (headless)
- Location: Chehalis, WA (garage deployment)
- Remote access via SSH over Tailscale VPN

### Hardware
- CPU: Intel i3-9100F
- GPU: NVIDIA GTX 1080 Ti (11GB VRAM, Ollama inference)
- RAM: 16GB
- Storage:
  - 111GB SSD (OS)
  - 1.8TB SSD mounted at `/mnt/virgil_storage` (primary)
  - 931GB HDD mounted at `/mnt/backup` (nightly rsync at 3 AM)

### Networking
- Tailscale VPN (secure remote access)
- SSH: `jordaneal@100.122.110.119`
- SSH key-based auth only (password login disabled)
- UFW firewall, Fail2ban active

### Core services
| Service | Type | Purpose |
|---|---|---|
| Ollama | system | Local LLM inference (Qwen 14B) |
| virgil-bot | user systemd | Telegram personal assistant |
| virgil-discord | user systemd | Discord DnD bot (Avrae co-DM) |
| Sentinel | cron 30min | Health monitoring |
| data_cache | cron 6:55 AM/PM | Calendar + email cache |
| morning_digest | cron 7am | Telegram digest |

`virgil-dnd` (Telegram DnD bot) was retired in Session 5. Archived at `/mnt/virgil_storage/archive/avrae_pivot_20260428/`.

### Key paths
```
/home/jordaneal/scripts/                 core Python scripts
/home/jordaneal/scripts/campaigns/       per-campaign skeleton.md files
/home/jordaneal/scripts/dm_philosophy.md DM philosophy directive (global, Track 3)
/home/jordaneal/scripts/.env             API keys (chmod 600)
/mnt/virgil_storage/virgil.db            SQLite database (THIS is the DB path)
/mnt/virgil_storage/digest/              cached data + logs (incl. corpus_inventory_report.md)
/mnt/virgil_storage/chroma/              personal Virgil ChromaDB
/mnt/virgil_storage/chroma_dnd/          DnD ChromaDB (sessions + 740k knowledge)
/mnt/virgil_storage/dnd_datasets/        raw CRD3 + FIREBALL source data
/mnt/virgil_storage/archive/             retired files
/mnt/backup/                             HDD backup target
```

### Service commands
```
systemctl --user restart virgil-bot       # or virgil-discord
journalctl --user -u virgil-bot -n 50 --no-pager
```

Bot tokens in `.env`: `TELEGRAM_BOT_TOKEN`, `DISCORD_BOT_TOKEN`. Avrae user ID: `261302296103747584` (override via `AVRAE_USER_ID`).

---

## 2. System Overview

Two active bots sharing one SQLite DB and the cloud router.

### Virgil (`virgil_bot.py`) — Telegram personal assistant
- Calendar (gog), email cache, web search (Brave), chat
- `/run` sandboxed Python, `/patch` self-modification, `/deploy`
- ChromaDB at `/mnt/virgil_storage/chroma/` — personal conversations
- SQLite `virgil.db` — messages, facts, pending state, calendar context

### Virgil DM Discord — D&D 5e narrative co-DM with Avrae as rules engine
Files: `discord_dnd_bot.py` + `dnd_engine.py` + `avrae_listener.py` + `dnd_orchestration.py` + advisory parsers (`mechanical_hints.py`, `npc_extractor.py`, `location_extractor.py`) + canon loader (`skeleton_loader.py`).

- **Avrae** handles ALL mechanics (rolls, sheets, HP, attacks, spells, saves, initiative, conditions, D&D Beyond integration).
- **Virgil DM** handles narration, NPC voice, world reactions, scene state, character-aware narration.
- **dnd_orchestration.py** is the structured gameplay layer — character context cache + roll discipline rules engine.
- Channel structure (canonical, post-S23 #3 + S23 #4 + S25 housekeeping + Track 6 #3): `🎲 VIRGIL DM` category contains `#dm-narration` (gameplay: narration + Avrae rolls + init + attacks + loot), `#dm-aside` (Track 6 #3 OOC advisory lane — read-only Q&A, **wired live**), `#lore-notes` (DM write, players read; Avrae read-only). `💬 OUT OF CHARACTER` category contains `#welcome` (S23 #4 onboarding pin pointing at virgildm.com), `#commands` (sanctioned home for slash commands and Avrae bookkeeping; convention not enforcement), `#party-chat` (player banter, bot-blind). `🔊 VOICE` category contains voice channels `General` + `AFK` (S25; guild AFK auto-move configured at 1800s timeout via `guild.edit(afk_channel=, afk_timeout=)`). Pre-S23-#3 layout (`#dice-rolls`, `#character-sheets`, `#party-loot`, `#bot-commands`, `#ooc-general`, `🎲 D&D` category) consolidated by `/setup`'s pure-function planner — Avrae rolls land in `#dm-narration` regardless of channel (listener filters by author, not channel); slash commands work anywhere; DDB owns sheets. Avrae permissions: full read+send on every canonical text channel **except** `#lore-notes` (read-only — DM-only write surface, contamination defense for the bot/DM private notes lane); skipped on voice (token view-only so Avrae appears in member list).
- ChromaDB at `/mnt/virgil_storage/chroma_dnd/`:
  - `dnd_sessions` — campaign history (grows with play)
  - `dnd_knowledge` — 740,307 documents (CRD3 Mercer turns + FIREBALL DM exemplars)

### Active scripts
```
virgil_bot.py              personal assistant (~1900+ lines)
cloud_router.py            multi-provider LLM routing
morning_digest.py          daily digest
sentinel.sh                health monitor (NOT yet checking virgil-discord)
data_cache.sh              calendar + email cache
dnd_engine.py              narrative core, scene state, prompt construction,
                            canonical NPC/location accessors (Phase 12)
dnd_orchestration.py       character context + roll discipline rules engine
avrae_listener.py          Avrae embed parser + RollBuffer
discord_dnd_bot.py         Discord transport layer
mechanical_hints.py        advisory parser — Avrae bookkeeping (Phase 11.1)
npc_extractor.py           advisory parser — narrative NPC extraction (Phase 12A)
location_extractor.py      advisory parser — narrative location extraction (Phase 12B)
skeleton_loader.py         authored canon loader — skeleton.md → DB (Phase 12C)
dnd_knowledge_import.py    CRD3/FIREBALL importer (incremental, run once)
consequence_extractor.py   advisory parser — dual-pass consequence capture (Session 16)
adjudicator.py             adjudication + arbitration layer (Track 7 #1/#2):
                            adjudicate() per-actor, arbitrate() multi-actor
narration_verifier.py      post-LLM narration verification (Track 7 #2)
npc_hydrator.py            NPC stat hydration — CR-band lookup (Track 6 #4)
srd_resolver.py            SRD monster resolver — exact/fuzzy/LLM-gated (Track 6 #5.1)
generate_srd_index.py      one-time script: 5e-database → srd_monsters.json (Track 6 #5.1)
srd_monsters.json          334-entry SRD index, CC-BY 4.0 (Track 6 #5.1)
```

---

## 3. Core Design Principles (non-negotiable)

- No LLM in execution path for critical actions (calendar, file writes, restarts).
- All system mutations require explicit user approval.
- Local routing for private data (calendar, email, memory, personal).
- Deterministic logic over probabilistic behavior for tools.
- Syntax check is mandatory before any file swap.
- Never let a bad patch touch the live file.
- For D&D: Avrae owns mechanics, Virgil owns narrative. Never blur the line.
- Roll discipline is a rules engine, not prompt seasoning.
- Scene state is authoritative; the prompt restates state, never invents it.
- Canonical world state (NPCs, locations) is authoritative; retrieval is not.

---

## 4. Architectural Invariants

Invariants vs guardrails: guardrails stop mistakes; invariants preserve identity. These are the load-bearing properties of the system. **If a proposed change would violate one of these, the change is wrong even if it appears to work** — fix the design, not the bypass.

### Authority invariants
- **Avrae is the sole authority for mechanics.** HP, dice, attacks, spells, saves, conditions, sheets. Virgil never re-implements any of these, even partially.
- **The bot does not emit `!`-prefixed commands to Avrae.** Only the LLM emits Avrae commands, and only via its narration response on the player-facing channel. The bot itself is read-only on the Avrae channel — no `bot.send("!attack ...")`, no programmatic `!init list` refresh, no bot-driven `!`-commands of any shape. New mechanical-command surfaces are added to the LLM's emission repertoire (e.g. Shape B init orchestration in S20), never as new bot→Avrae write paths. **This invariant constrains bot-side Avrae writes only.** It does NOT constrain transport-layer input filtering on the player-narration channel (e.g. Phase 2A.3's off-turn ⏳ drop, which is a routing decision the transport layer is allowed to make).
- **SQLite is the authoritative structured state store.** Anything referenced as "state" reads from or writes to SQLite, never from in-memory shadows that drift.
- **The cloud router is the only path for LLM calls.** Direct provider calls bypass routing intelligence and break the latency feedback loop.
- **One authority per concern** (Phase 12 reinforcement):
  - Mechanics → Avrae
  - Canonical entities → SQLite via single-writer functions
  - Campaign intent → `skeleton.md` (authored canon)
  - Rules gating → orchestration
  - Retrieval/context → ChromaDB
  - Narration → DM LLM

### State integrity invariants
- **LLMs NEVER directly mutate structural state.** The extraction thread is gated by `LOCKED_FIELDS` at the write boundary. New structural fields must be added to `LOCKED_FIELDS` by the same patch that introduces them.
- **Single write paths per field**, no exceptions:
  - `set_scene_mode()` — mode
  - `update_tension()` — tension_int
  - `set_clocks()` / `clock_*()` — progress_clocks
  - `set_current_location()` — current_location_id
  - `npc_upsert()` — dnd_npcs
  - `location_upsert()` — dnd_locations
  - `campaign_set_status()` — dnd_campaigns.status (outside `create_campaign`)
  - `campaign_delete_cascade()` — sole hard-delete path; refuses on active campaign at the engine layer.
  - `consequence_upsert()` — dnd_consequences (capture path; last-write-wins per `(campaign, npc, kind)`).
  - `consequence_emit_surface()` — dnd_consequences surface counters (directive-emit path).
  - `maybe_promote_consequences()` — sole writer of `status='promoted'` and the bracketed-prefix append into `dnd_npcs.description`.
  - `increment_turn_counter()` — `dnd_scene_state.turn_counter` (per-campaign monotonic axis used by promotion thresholds).
  - `npc_hydrate_stats()` — stat columns on `dnd_npcs` (hp_max, ac, attack_bonus, damage_dice, save_bonus, init_mod, cr_str). Source-based fill rule: hook sources use idempotent NULL-fill; `explicit_hydrate` always-overwrites. No other path may write these columns.
  - `npc_register_avrae_madd()` — `avrae_source` column on `dnd_npcs` for `!init madd` creatures. Idempotent (no-op if already set).

### Telemetry primitives (Session 16 autonomous block + Session 18 observability batch)

**S22 (Session 18):** `unconsumed_roll_swept` log line — emitted from `RollBuffer._sweep()` in `avrae_listener.py` for every event that ages past `EVENT_TTL_SECONDS` (75s) without being consumed. Format: `unconsumed_roll_swept: actor='{actor}' action='{action}' age_s={age}`. Pure visibility — does not change sweep behavior. `avrae_listener.log` is now a module-level function (mockable in tests). Tests: `test_avrae_sweep.py` (11 assertions).

**S23 (Session 18):** `npc_near_match` / `location_near_match` log lines — emitted from the INSERT branch of `npc_upsert` and `location_upsert` in `dnd_engine.py` when a new canonical name lands within Levenshtein distance ≤ 2 of any existing canonical name in the same campaign. Format: `npc_near_match: new='{name}' existing='{name}' distance={N}` (and `location_near_match` analog). `levenshtein_distance(a, b)` helper added to `dnd_engine.py` near the canonicalization helpers. Pure observability — does NOT change matching behavior or the Phase 6 strict-equality identity rule. Only fires on insert (not update). Cross-campaign isolated (query scoped to campaign_id). Tests: `test_npc_near_match.py` (26 assertions).

**S24 (Session 18):** `prompt_size:` log line — emitted from `dm_respond` in `dnd_engine.py` after `build_dm_context` returns and all prepends (skeleton block, transition context) are applied. Format: `prompt_size: campaign={N} system={chars} retrieval={chars} party={chars} scene={chars} directives={chars} total={chars}`. `system` = `build_dm_context` output before skeleton/transition prepend; `total` = final prompt size. Section sizes computed from the input variables feeding each block: retrieval = `relevant + guidance`; party = `character_contexts` rendered; scene = `scene_state` field values; directives = pacing + central_thread + consequence + philosophy. Pure measurement — no optimization, no truncation. Tests: `test_prompt_size.py` (22 assertions).

**S25 (Session 18, updated Session 19):** `directive_emit:` log line — emitted from `dm_respond` in `dnd_engine.py` once per turn, after `prompt_size:`. Aggregates which directives fired with non-empty content into a single per-turn signal for threshold calibration. Format: `directive_emit: campaign={N} pacing={tier|none} central_thread={1|0} philosophy={chars} consequence={count} capability={verdict|none} commitment={1|0}`. `pacing` emits the tier name (`low`/`medium`/`high`/`climax`) from `_pacing_tier()` when the pacing directive has content, otherwise `none`. `consequence` is the count of surfaced consequences passed to the directive. `capability` emits the verdict name when `needs_check=True`, otherwise `none`. `commitment` flips between `0` and `1` based on whether the commitment directive's gates all passed (Session 19 escape-only v1; was hardcoded `0` placeholder Session 18). Tests: `test_directive_emit.py` (23 assertions).

**Session 19 commitment telemetry:** Two additional log lines emit from `dm_respond`:
- `commitment_directive: campaign={N} fired={1|0} prior_intent= current_intent= is_scene_shift= avrae_drained= reaction_verbs= retraction_filtered=` — every turn, regardless of fire. Empirical baseline of gate hit rates.
- `commitment_retraction_filtered: campaign={N} text='{first 80}'` — only when retraction grammar suppressed an otherwise-firing directive. Measures false-positive rate of the suppression filter for future tuning.

**Track 6 #4 hydration telemetry:** Two log lines emitted from the hydration layer:
- `hydration: campaign={N} npc='{name}' source={source} stats_filled={fields|none} cr={cr_str|none} status_token={token}` — emitted from `npc_hydrate_stats()` and `npc_register_avrae_madd()` on every invocation. `source` is one of `hook`, `skeleton`, `adhoc`, `generic_fallback`, `explicit_hydrate`, `avrae_madd`, `miss`, `bound_pc_skip`. `stats_filled` lists field names written (`hp,ac,atk,dmg,save,init`) or `none`. Always-fires for routing visibility — miss and skip paths emit with `stats_filled=none`.
- `hydration_manual: campaign={N} npc='{name}' cr={cr_str} stats_written={0|1} fields_updated={fields|none}` — emitted from the `/hydrate` slash command handler in `discord_dnd_bot.py` per invocation. Distinct from the engine log line; `stats_written=0` when NPC already at full stats for the given CR (no-op path). `fields_updated` mirrors the engine's `stats_filled` when writes occurred.
- `directive_emit:` extended with `hydration_write_fired={0|1}` — reads `_hydration_wrote_this_turn` from `dnd_engine.py` (module-level boolean set by `npc_hydrate_stats` when writes occur, reset by `dm_respond` after read). Per-turn aggregate signal for the hydration layer.

- `consequence_health_report(campaign_id)` — pure read. Returns `{active, promoted, never_surfaced, by_kind, by_source}` for the consequence layer. Composed into `world_health_report` (adds `cons_active`, `cons_promoted`, `cons_never_surfaced` to the aggregate). Per-turn `world_health:` log line extended.
- `godmode_gap` log line — emitted from `dm_respond` when `intent=COMBAT` fires in a non-combat mode. Surfaces the gap empirically before any constraint layer (see `COMMITTED_ACTION_RESOLUTION_SPEC.md`) ships.
- `dm_respond: EMPTY response` and `dm_respond: cleaned response too short to narrate` — diagnostic log lines for the LLM-returned-empty failure mode Jordan saw at 20:41 May 3 (footer-only embed with no narration).
- `extract_scene_updates` task_type fix — was `task_type="dnd"`, now `task_type="extraction"`. Removes redundant heavy-model calls per turn and stops the JSON-extraction call from competing with the actual narration call for groq_heavy. Matches every other advisory-parser routing.
- `consequence_ooc_filtered` log line — emitted from `parse_consequences_player` when the player's text starts with a known OOC marker (`((`, `[OOC]`, `OOC:`, `//`). Short-circuits the parser before the LLM call. Player-channel only — DM parser stays unfiltered (LLM-emitted text is a different attack surface). Format: `consequence_ooc_filtered: campaign={N} reason={paren|bracket|colon|slash} text={first 80}`.
- `typing_indicator_failed` log line — emitted from each `async with channel.typing()` call site in `discord_dnd_bot.py` when the typing context manager raises `discord.HTTPException` or `asyncio.TimeoutError`. Format: `typing_indicator_failed: command={advisory_respond|_dm_respond_and_post|play} err={repr}`. Three call sites wrapped (Bug 4 fix, post-S27): `_advisory_respond` (line 1574), `_dm_respond_and_post` (line 1707), `/play` opening (line 2950). On exception path, the handler body re-runs without the typing context — typing indicators are aesthetic, never block narration. Soft-fail per Doctrine §59. Fires only on the exception path.
- **Per-campaign data is enumerated explicitly** (Session 13). The `_CAMPAIGN_SCOPED_TABLES` constant in `dnd_engine.py` lists every per-campaign table that the cascade must clear. **When you add a new per-campaign table, append it to `_CAMPAIGN_SCOPED_TABLES` in the same patch or campaign purges silently leave orphan rows.** Currently 8 tables: `dnd_consequences` (Session 16, child of dnd_npcs — listed first so deletion cascades before parent), `dnd_npcs`, `dnd_locations`, `dnd_quests`, `dnd_companions`, `dnd_combat_state`, `dnd_scene_state`, `dnd_characters`. The `dnd_campaigns` row is deleted explicitly in the cascade after the per-campaign rows.
- **Two independent gates before destruction** (Session 13). Hard-delete commands require BOTH structural state (archived) AND human confirmation (typed phrase). Active campaigns cannot be hit by `/purgeallcampaigns` even with the right phrase because they are not archived. Single-id `/purgecampaign` cannot fire on active campaigns even with the right phrase because the slash command verifies status before passing to the engine. Either gate alone is insufficient.
- **Prompts cannot become authoritative state.** If the LLM "knows" a fact only because the prompt told it, that fact does not exist in the system.
- **Scene extraction is advisory, never structural.** Can suggest narrative details (location, focus, established_details, open_questions); cannot drive mechanics or pacing.
- **`skeleton_origin=1` rows are authored canon.** Parsers cannot overwrite authored fields, only bump `mention_count`/`last_mentioned`. Promotion (parser → skeleton) is manual only.
- **Retrieval is not canon.** Chroma answers "what feels semantically related?" — canonical state answers "what is actually true in this world?" Never blur.
- **Partial projections principle (S9).** Avrae attacks, skeleton.md, and DDB are all PARTIAL projections of character truth. Absence of data in any one source is NOT evidence of absence. The bot must never treat missing data as a contradiction. INVALID verdicts are reserved exclusively for explicit contradictions from authoritative sources, never inferred from gaps. Validators check current claims; they do NOT retroactively repair narrative history committed by the LLM.

### Boundary invariants
- **Discord transport (`discord_dnd_bot.py`)** is a thin shell. Routes events to the engine and renders responses. Does NOT own gameplay logic, classification, or state.
- **Orchestration (`dnd_orchestration.py`)** owns rules-engine logic (intent classification, roll decisions, character cache). Does NOT touch the database directly or call the LLM.
- **Engine (`dnd_engine.py`)** owns SQLite, prompt assembly, and the LLM call. Does NOT know about Discord.
- **Listener (`avrae_listener.py`)** owns Avrae message parsing. Pure parser: in = Discord message, out = structured event. No side effects, no DB writes, no LLM calls.

### Dual-channel invariant (Avrae-specific)
Avrae uses message edits as state transitions, not just sends. Any new Avrae integration MUST wire BOTH `on_message` AND `on_message_edit`. Single-channel listeners silently miss state transitions. (The `!init end` fix in Session 7.)

### OOC Advisory Lane invariants (Track 6 #3, `#dm-aside`)
Read-only Q&A surface for players. Same LLM, different system prompt (`ADVISORY_SYSTEM_PROMPT` in `dnd_orchestration.py`), different router task (`'advisory'` in `cloud_router.py` — same provider pool as `chat`/`general`, no DnD anti-repetition penalties). The `_advisory_respond` handler in `discord_dnd_bot.py` branches off `on_message` BEFORE the `#dm-narration` gate so advisory traffic never touches the narration path. **Load-bearing invariants — do not relax without spec change:**

- **No ChromaDB writes from the advisory path.** No `chroma_store`, no `chroma_search`. Track 4 #2 v1.2 contamination lesson: chroma is a cross-turn behavior source — what gets stored gets re-injected on similar future turns. OOC Q&A noise leaking into chroma would surface as narrative grounding on later turns. Structural defense: `dnd_orchestration.py` doesn't import `dnd_engine`'s chroma functions, and `_advisory_respond` only calls pure-read helpers (`get_scene_state`, `get_active_turn`, `get_combatants`, `get_inventory`, `get_pending_loot`).
- **No state mutation.** Advisory does NOT call any `set_*`, `update_*`, `clear_*`, `_upsert`, `enqueue_loot`, `add_item`, `mark_loot_surfaced`, or any other writer. Test enforces this structurally (`test_advisory.test_build_context_does_not_call_engine_writers` patches every writer in `dnd_engine` and asserts zero calls).
- **No `!`-prefixed Avrae emission.** Bot-Avrae write boundary preserved per the existing core invariant. Advisory describes Avrae commands as PLAYER options ("type `!attack <weapon> -t goblin`"), never emits them itself.
- **No tactical directives.** Pacing, persistence, loot, redirect, footer, capability-decision, roll-decision — none compose for advisory. Those exist for narrative pressure and don't belong in OOC support. Advisory's system context is just the `ADVISORY_SYSTEM_PROMPT` + a flat state-reference block from `build_advisory_context(...)`.
- **Single round-trip per question, truncate-with-pointer at 1900 chars.** No conversation threading in v1; no multi-message split. Failures fall back to a generic "try again" message + `advisory_respond_failed:` log line — empty/exhausted-providers responses ALSO trigger the fallback so a silent router degradation never lands as a blank message.
- Telemetry: `advisory_respond: campaign={N} guild={N} chars={N} truncated={0|1} provider={...} state_combat={0|1} state_inventory_count={N} state_combatants={N} bound_char={0|1}` per request. Empirical baseline for usage frequency, response length, and state-context shape.

### NPC stat hydration invariants (Track 6 #4)

The hydration layer provides deterministic stat assignment for NPCs entering init. It is read-only with respect to Avrae — stats are stored in SQLite for prompt context only; Avrae mechanics are never driven from these values. **Load-bearing invariants:**

- **Single hook, Hook 2 only.** `_handle_init_list_event` (init-list parse in `discord_dnd_bot.py`) is the sole hydration trigger for auto-hydration. Hook 1 (`!init add` eager hydration) is disabled in v1 — status_token is unavailable at add-time, making classification impossible. No dual-hook paths.
- **Status_token classification is post-state, not command-inference.** `<None>` tokens (no HP backing) route to the hydration path; non-`<None>` tokens (`<Healthy>`, `<Bloodied>`, `<Critical>`, `<Dead>`, numeric HP) route to `npc_register_avrae_madd()`. Classification reads from the init-list embed, not by inferring whether `!init add` vs `!init madd` was typed. This makes routing immune to command-syntax variation.
- **Source-based fill rule.** Hook sources (`hook`, `skeleton`, `adhoc`, `generic_fallback`) use idempotent NULL-fill: `WHERE col IS NULL`. Never overwrite a DM-authored value. `/hydrate` (`explicit_hydrate`) always-overwrites all 6 stat fields — DM's correction is authoritative. No source may relax this without spec amendment.
- **`generic_fallback` deliberately leaves `hp_max` NULL.** When CR is unknown, partial stats (ac/attack_bonus/damage_dice/save_bonus/init_mod) are written using CR-1/4 defaults. `hp_max` is never estimated — HP unknown-to-DM is modeled as NULL, not as a guess. Doctrine §1 (no fabricated mechanics).
- **Engine NEVER resolves `cr_str=None` for non-generic_fallback sources.** The caller (`_handle_init_list_event`) decides whether CR is known before calling `npc_hydrate_stats`. The engine does not infer CR. Caller-side decision per §11.L.
- **`avrae_madd` creatures defer all mechanics to Avrae.** `npc_register_avrae_madd()` creates a row for tracking/context purposes only, with all stat columns NULL. No hydration fires for these creatures. Avrae's `!init madd` data is authoritative.
- **No sync hints to Avrae.** `/hydrate` response and all hydration log lines NEVER emit `!init modify` or any `!`-prefixed suggestion. SQLite stats are for the DM's prompt context, not Avrae state sync. The two data stores are intentionally divergent.

### SRD resolver invariants (Track 6 #5.1, `srd_resolver.py`)

The resolver is a pure-function module: no DB, no Discord, no dnd_engine imports beyond `log`. It implements the inaugural Doctrine §1b validated-suggester pattern. **Load-bearing invariants:**

- **LLM proposes; index validates; gate enforces; DM approves; Avrae executes.** The LLM never decides anything mechanically. Its candidate is gated through `_MONSTER_INDEX` (exists check) and `_CONFIDENCE_THRESHOLD` (≥0.65). DM typing `!init madd` IS the §1b approval step.
- **`_LLM_CACHE` never caches transient failures.** Network errors, parse errors, and exceptions do NOT write `None` to cache — next encounter retries. Only definitive LLM responses (including genuine no-match empty strings) are cached. Cache-poisoning prevention (§F.2 lock from review doc).
- **`resolve()` never propagates exceptions.** Defense-in-depth try/except wraps `_llm_suggest` call in `resolve()`, even though `_llm_suggest` already catches internally. Any exception → `llm = None` → miss path.
- **No mode gate (§11.H locked).** Hook fires on every `was_new=True` NPC upsert regardless of scene mode. Narration fires in `mode='exploration'` (before `!init begin`); a mode gate would have silenced all suggestions.
- **`was_new=False` is the primary dedup guard.** `_SUGGESTED` in-process set is secondary protection. `npc_upsert()` is the definitive INSERT/UPDATE signal — `was_new=False` (UPDATE) means the NPC already existed and no suggestion should fire.
- **Two-line telemetry shape (§8 lock).** `resolve()` emits `srd_suggestion:` with `posted=0`. `_post_srd_suggestion()` emits with `posted=1` after Discord send. Miss and dedup emit one line only. The resolver never emits `posted=1` — that belongs exclusively to the transport function.
- **Bot never emits `!`-prefixed Avrae commands.** The suggestion body contains `!init madd` as a code block for the DM to copy-paste. The bot does not send the command to Discord; the DM does.

### Time Progression invariants (Track 4 #3, `dnd_engine.advance_time` + `compute_time_directive`)

The campaign clock is a deterministic-only surface. The LLM never decides when time advances or by how much. **Load-bearing invariants — do not relax without spec change:**

- **§1a anchor.** Every time-field write originates from a `/`-command handler, an Avrae-event listener, or a deterministic parser of structured DM input — never from LLM narration parsing. The LLM may *narrate the consequence* of an advancement that already happened deterministically ("the sun sets," "you wake at first light") — that is allowed and expected, but the write happened first. §1b LLM time-mention extraction is filed for v1.x per §11.F=a lock.
- **§17 single write path.** All runtime writes to `dnd_scene_state.campaign_day` / `day_phase` and all rows in `dnd_time_advancements` flow through one engine helper: `advance_time(campaign_id, days_delta, phase_delta, source, source_detail, set_phase=None) → TimeAdvancement | None`. The four v1 call sites are `/travel`, Avrae `!lr` hook, Avrae `!sr` hook, and `/advance`. New surfaces must call this writer; they do not introduce parallel writers.
- **Narrow §J.3 seed-write exception.** Campaign initialization is not an advancement event. `skeleton_loader.apply_starting_time_seed(campaign_id)` writes `dnd_scene_state.campaign_day` / `day_phase` directly during the first `/play` of a campaign, bypasses `advance_time()`, and does NOT append a row to `dnd_time_advancements`. Idempotency-guarded — only fires when scene_state is at defaults `(1, 'Morning')`. The narrow framing: *"`advance_time()` is the sole writer for runtime time advancement. Campaign initialization has a separate one-shot writer in the skeleton loader, scoped to the first-scene_state seed only, idempotent because the seed only fires when defaults are intact."* Any third writer requires spec amendment.
- **Source enum lock (§5).** `source` is one of `'travel' | 'rest_long' | 'rest_short' | 'advance'`. `'narration_suggester'` is reserved for the v1.x §1b ship; v1 rejects it. Adding a fifth source requires spec amendment, not inline addition.
- **No mode gate on time advancement.** `advance_time()` does not check `scene_state.mode`. Time can advance during combat (a multi-round chase that crosses a phase boundary), during exploration, during social. Mode is independent of time. The footer renders `⚔ Combat — Round N · Day 3, Evening` correctly during combat.
- **`set_phase` precedence invariant (§11.I).** When `set_phase` is not None, the writer ignores the caller's `phase_delta` and computes `resolved_phase_delta = (target_idx - current_idx) mod 6`. The audit log row records all three values: `set_phase` (caller's declared target), `phase_delta` (caller's also-passed-but-ignored delta), `resolved_phase_delta` (the actual delta written). Soft-handle per §59: do not raise on conflicting arguments; `set_phase` wins, `phase_delta` is recorded for diagnostic.
- **No-rewind invariant (§5).** `days_delta < 0` and `phase_delta < 0` are both rejected with a logged diagnostic. Time only moves forward in v1. Time-rewind is filed §12 if ever needed.
- **Modular phase normalization, never iterate (§5).** `total_steps = current_idx + phase_delta + days*6; new_day = before + total//6; new_idx = total % 6`. The writer never iterates phase-by-phase. Tests pin the formula at `phase_delta=12, 13, 25` to protect against future "iterate +1 phase N times" implementations.
- **Missing-campaign no-op contract (§8).** `advance_time()` reads scene_state first via `SELECT campaign_day, day_phase FROM dnd_scene_state WHERE campaign_id=?`. If no row exists, returns `None` and emits `time_advance: campaign={N} source={...} err='no scene_state row'` without writing the audit log. Atomicity: column-and-log writes happen inside one transaction — either both succeed or neither does.
- **Cascade requirement (§4 + VIRGIL_MASTER §6).** `dnd_time_advancements` MUST be in `_CAMPAIGN_SCOPED_TABLES`. `/purgecampaign` cascades wipe time-advancement rows for the deleted campaign. Pinned by test `test_purgecampaign_cleans_time_advancements` in `test_time_schema_integrity.py`.
- **Bot never narrates intervening hours.** The `compute_time_directive` instruction text is locked to "Open with one in-fiction beat marking the new time of day. One sentence, location-appropriate. Then return agency to the player. Do NOT narrate the intervening hours." This prevents the LLM from filling in road descriptions / journey beats that `/travel` was specifically built to compress.
- **Just-advanced is recency, not flag (§11.E sub-(iii)α).** `time_just_advanced(campaign_id, window_seconds=60)` queries `dnd_time_advancements MAX(created_at)` per turn. The window is tunable from telemetry — re-decide to (iii)β process-memory flag only if `directive_emit:.*time=1` correlations against `time_advance:` show >5% missed-fires after window tuning to 120s.
- **Telemetry contract (§8).** Always-fire log lines: `time_advance:` per advancement (success and exception paths); `parse_elapsed:` per parse attempt (success or fail); `directive_emit:` extended with `time={1|0}`; `state_footer:` extended with `day=` / `phase=`. The `dnd_time_advancements` log is the durable audit; `dnd.log` lines are the transient signal.
- **`/travel arrival_time` is display-only (§11.G=b).** `arrival_time` flows into the `TRAVEL_TRANSITION` prompt block as flavor text but does NOT drive `advance_time()`. The clock is written purely from `parse_elapsed(elapsed)`. Avoids the live `arrival_time='evening'` default trap. DMs who want explicit phase control after travel use `/advance phases:N` or `/advance set_phase=Evening`.

### Adjudication Layer invariants (Track 7 #1-2, `adjudicator.py` + `narration_verifier.py`)

The adjudication layer is the binding gate between player intent and DM narration. It promoted directives from advisory to binding — what the LLM was previously asked to honor is now structurally enforced before narration generates. **Load-bearing invariants — do not relax without spec change:**

- **Narration describes reality, doesn't create it.** This is the architectural shift Track 7 #1 makes structural. Player input describes attempts; the resolver decides outcomes; the narrator is constrained to narrate the approved outcome only. The LLM never decides whether a roll succeeded, whether a capability applies, whether combat is active, or whether reality bends. Those decisions live in deterministic Python, and narration follows.
- **Five locked action categories.** `FREE_ACTION` (pure RP, no stakes); `CHECK_ACTION` (outcome uncertain, roll required, narration constrained to success/failure shape); `CAPABILITY_ACTION` (class/level/spell/feature gates — refusal binding, no "says who" override); `COMBAT_ACTION` (requires `mode='combat'` AND populated init order); `WORLD_BOUNDARY_ACTION` (reality-violating actions — hard refusal, no in-fiction workaround). Adding a sixth category requires spec amendment, not inline addition.
- **Single entry point.** `adjudicate(player_input, scene_state, character, combatants, active_turn, intent) → AdjudicationResult` in `adjudicator.py`. Pure function. Composes BEFORE every directive in `build_dm_context`. Extending adjudication means extending this function or the categories below it, not adding parallel resolvers.
- **Deterministic intent classifier, not LLM-based.** Regex + keyword vocabulary (Appendix A in `ADJUDICATION_LAYER_SPEC.md`). Crude beats clever. LLM-based classification would be another hallucination layer; rejected by spec lock.
- **Narration constraints render top-of-prompt AND bottom-of-prompt.** `=== ADJUDICATION ===` block at top for response framing (Doctrine §48); same constraint repeated at bottom as last cache before generation (Doctrine §2). Belt + suspenders. Both renders required — single-render leaks under prompt drift.
- **Refusals do not invent in-fiction workarounds.** WORLD_BOUNDARY refusals must produce non-occurrence narration ("words dissolve before they can shape crystal"), never fabricated NPC justification (no Keeper-of-the-Vein-appears workaround for refused absurd actions). CAPABILITY refusals describe what the character cannot do, never invent a reason it suddenly can.
- **Capability adjudication uses real character context or defers safely.** When `primary_ctx=None` (cache miss), `_gate_capability` returns `(True, "no_character_context")` per partial-projections doctrine. Defers to existing HARD STOP RULES rather than producing a false-binding refusal. Track 7 #1.1's `cache_autopopulate` minimizes this deferral path.
- **§11.K activation:** capability adjudication is the first INVALID producer for S9's `CapabilityVerdict`. Previously dead code path now reachable.
- **§11.L deduplication:** when adjudication produces a binding constraint, redundant advisory directives (capability_decision, commitment_directive, combat_redirect) suppress their independent narration to avoid double-blocking. Adjudication is the senior layer; siblings defer.
- **Adjudicates player input AND LLM output.** Track 7 #1 adjudicates player input before narration generates. Track 7 #2 adds two further layers: `arbitrate()` merges concurrent multi-actor inputs into one structured constraint block before `build_dm_context`; `narration_verifier.py` adjudicates the LLM's narration before it posts. Together the three-layer stack closes all S25 #3 multiplayer failure modes.
- Telemetry: `adjudication: campaign={N} actor='{name}' category={...} allowed={0|1} refusal_kind={...} skill={...} dc_band={...} roll_consumed={0|1}` per turn (Track 7 #1, per actor). `arbitration: campaign={N} actors={N} primary='{name}' merge_plan={sequence|override} overridden={N}` per turn (Track 7 #2, always-fire). `verification: campaign={N} passed={0|1} violation_class={...} retry_fired={0|1} escalated={0|1}` per turn (Track 7 #2, always-fire).

### Arbitration + Verification invariants (Track 7 #2)

- **All-pairs conflict detection, not adjacent-only (§11.R).** Every pair (i,j) of verdicts is scanned. With N actors, this is N(N-1)/2 comparisons. `overridden_actors` is a list, not singular — multiple actors can be overridden by the same high-priority verdict.
- **Text-aware contradiction detection.** A FREE verdict overrides a binding verdict only when the FREE actor's text explicitly asserts an opposing outcome. "I help him" alongside a CHECK success is compatible — no override. "He agrees with us" alongside a CHECK failure is contradictory — override fires. Four targeted regex patterns gate each contradiction class (CHECK_fail, CHECK_success, CAPABILITY_refused, COMBAT_inactive).
- **`actor_order` stores character names, not Discord usernames (§11.Q).** `actor_order: list[str]` contains "Donovan", "Bruce" — not "@jordaneal", "@tazzplays". Character names are stable canonical identifiers; Discord usernames are transport noise.
- **Cache-miss actors get `no_character_context` refusal, not a hard error (§11.P).** `arbitrate()` degrades gracefully — unknown actors receive a `no_character_context` verdict and are excluded from ACTOR_OMISSION checks. The fallback preserves the known-actor verdicts.
- **`ARBITRATION_ENABLED` short-circuits to first-actor-only.** When False, `arbitrate()` returns a degenerate single-actor result identical to Track 7 #1 behavior. No caller change required.
- **`narration_verifier.py` is a parallel sibling, not an extension of `adjudicator.py` (§11.J, Doctrine §63).** Fork at the module level. Verification logic does not import arbitration logic. The fork point is architectural, not incidental — the two modules have different inputs, different detection surfaces, and different failure modes.
- **ACTOR_OMISSION is structural, not observational (§11.M).** When an arbitrated actor is wholly absent from the narration, the response is wrong by construction — not merely suboptimal. ACTOR_OMISSION triggers the retry loop, not just a log entry.
- **Four locked violation classes (§11.F): `FABRICATED_COMBATANT`, `VERDICT_CONTRADICTION`, `STATE_MUTATION_CLAIM`, `ACTOR_OMISSION`.** Adding a fifth requires spec amendment. First-violation-wins ordering is locked: FABRICATED_COMBATANT → VERDICT_CONTRADICTION → STATE_MUTATION_CLAIM → ACTOR_OMISSION.
- **Verification fails open (`VERIFICATION_ENABLED` flag).** When disabled or when `verify_narration()` raises, the narration posts as-is. Verifier failure is never a blocking error.
- **Retry loop: 1 retry max.** On second violation → deterministic escalation placeholder via `build_escalation_placeholder()`. The LLM gets one correction opportunity; the placeholder is the guaranteed fallback.
- **`build_dm_context` kwarg is `arbitration_block`, not `adjudication_block` (§11.N rename lock).** Block header is `=== ARBITRATION RESULT ===`. These renames are permanent; callers must not use the old names.

If an invariant feels constraining, that's the feature.

---

## 5. Design Tracks (build in this order)

Virgil is a persistent campaign engine whose narration layer is powered by LLMs. Each track's quality ceiling depends on the layer below being stable.

### Track 1 — Canonical World State
Stable narrative identity. NPCs, locations, campaign skeletons, faction identity, world facts. **Phase 12 shipped this track.**

### Track 2 — Mechanical Authority
Narrative grounded against actual rules and character capability. Avrae owns mechanics; Virgil must CONSULT them, not narrate around them. "I draw my sword" verifies equipped state. **S9 (equipment grounding) shipped Session 13** as the entry point — 3-state CapabilityVerdict over Avrae attacks ∪ skeleton-declared capabilities. Do NOT solve rules grounding through prompting alone.

### Track 3 — Narrative Simulation
World evolves coherently over long campaigns: faction agendas, relationship evolution, emotional continuity, arcs. **DO NOT build until tracks 1+2 stabilize.** No relationship system matters if NPC identity is noisy.

### Six-question evaluation checklist for any proposed feature
1. What subsystem owns this truth?
2. Is this authoritative or advisory?
3. Can this be inspected/debugged later?
4. Is this canon or retrieval?
5. Does this reduce improvisational drift or merely mask it?
6. Would this still work after 20 sessions?

If a proposed feature can't answer all six cleanly, it isn't ready to build.

---

## 6. Architecture

### Virgil bot message flow (Telegram)
```
Telegram → process_message()
             ├── offset persistence
             ├── bare confirmation drop (10s startup window)
             ├── pending state machine (calendar/patch confirmations)
             ├── classify() → LLM intent (groq) with regex fallback
             └── handler dispatch
                   ├── cal_add / cal_delete / cal_move / cal_list (gog CLI)
                   ├── search (Brave Search API → LLM synthesis)
                   ├── chat (cloud_router → LLM, complexity-aware)
                   ├── /run (LLM generates code → subprocess sandbox)
                   ├── /patch (LLM modifies function → diff → confirm → restart)
                   ├── /deploy (paste function → diff → confirm → restart)
                   └── /stats /usage /memory /remember /reset /help
```

### Virgil DM Discord message flow
```
on_message →
  ├── Avrae embed/plaintext? → avrae_listener parses → RollBuffer.add (75s TTL)
  └── Player text in #dm-narration → ActionBatcher.add → _dm_respond_and_post →
        ├── RollBuffer.consume(guild, actor_names)
        └── dm_respond(...)
```

### DM response pipeline
```
player_action
  ↓
scene_state = get_scene_state(campaign_id)
  fields: mode, tension_int, progress_clocks, current_location_id (P12),
          + narrative fields written by extraction thread
  ↓
mode = scene_state['mode']               AUTHORITATIVE; never recomputed
  ↓
character_ctx = orch.get_cached_context(actor)
  ↓
intent = orch.classify_action_intent(text, mode=mode)
  Regex-based, mode-aware. Order shifts per mode:
    social/downtime: SOCIAL, CONTESTED, EXPLORATION, RISKY, TRIVIAL
    travel:          TRIVIAL, CONTESTED, EXPLORATION, RISKY, SOCIAL (TRIVIAL default)
    combat/expl:     CONTESTED, EXPLORATION, RISKY, SOCIAL, TRIVIAL (SOCIAL default)
  META and COMBAT always win regardless of mode.
  RISKY_RX uses negative lookaheads on `steal`/`sneak` for idiomatic uses.
  ↓
roll_decision = orch.should_call_roll(intent, mode, text, ctx)
  Returns RollDecision(needs_roll, skill, save, category, severity, reason).
  Prompt RESTATES the decision — never decides on its own.
  For category='attack' (combat intent), to_prompt_directive() emits a
  fill-in template `!attack <weapon-name> -t <target>` (or `!cast
  <spell-name> -t <target>` for spells) — NO quotes around multi-word
  names (Avrae uses positional parsing, same convention as
  `!check sleight of hand`). The directive includes an explicit narration
  mandate: "Your message MUST narrate the player's attempt BEFORE the
  command — a response that is ONLY the command is INSUFFICIENT." HARD
  STOP RULE 5 carve-out tells the LLM to fill placeholders rather than
  emit them literally and forbids quoting multi-word names. Pre-Session-18,
  the attack path emitted bare `!roll` in the directive while the reason
  field said "use !attack/!cast" — the LLM freelanced bare `!attack` and
  Avrae rolled against `<No Target>`, silently discarding the attack
  effect. NOTE: even with B2/B2.1 fixed, Avrae can still report
  `<None>: Dealt N damage!` if the target isn't in an active initiative
  tracker — that's the godmode/committed-action layer (separate spec),
  not an orchestration-layer bug.
  ↓
new_tension = calculate_tension_shift(...)
  Pure function. Damage → +N, nat 1 → +10, short rest → −40,
  long rest → 0, no-damage → −3. Clamped 0-100.
  → update_tension() if changed
  ↓
relevant = chroma_search(campaign, action)        per-campaign history
guidance = multi_query_knowledge_search(...)      740k DM exemplars
  ↓
system = build_dm_context(...)
  Blocks: SETTING & TONE, PARTY, CURRENT SCENE, CURRENT MODE + tonal directive,
  SCENE STATE (incl. tension label + clocks), ACTING CHARACTER, AVRAE EVENTS,
  ROLL DIRECTIVE
  ↓
PHASE 12C — skeleton_loader.get_skeleton_prompt_block(campaign_id)
  if non-empty: prepend authored-canon block to system prompt
  ↓
PHASE 12 / Ship 1 — transition_context (if /travel or future /rest, etc.)
  if set: prepend authoritative scene-transition block, highest priority
  ↓
response = route(task_type="dnd", system=system)
  ↓
threading.Thread(extract_scene_updates)             async narrative-fields-only
asyncio.create_task(_attach_hints)                  Phase 11.1 mechanical hints
asyncio.create_task(_extract_and_persist_world)     Phase 12B NPC + location +
                                                     FK resolution + telemetry
  ↓
return response
```

### Combat mode FSM
```
Avrae !init begin (plaintext) → on_message → parse_init_event →
                               _handle_init_event → set_scene_mode('combat')
Avrae !init end + yes confirm  → message EDIT → on_message_edit →
                               parse_init_event → _handle_init_event →
                               set_scene_mode('exploration')
Manual override                → /mode <choice> → set_scene_mode(...)
```

### Tension thermometer
- 0-100 integer in `dnd_scene_state.tension_int`
- Coarse label at prompt-render: `tension_label()` — Calm (0-25), Mounting (26-60), Dangerous (61-85), Climax (86-100)
- `calculate_tension_shift()` is pure (no I/O), runs in `dm_respond` BEFORE `build_dm_context`
- Skips target attribution intentionally (Avrae embeds don't reliably distinguish PC vs monster damage)

### Progress clocks
- JSON list on `dnd_scene_state.progress_clocks`: `[{"name": "Alarm Level", "capacity": 6, "ticks": 2}, ...]`
- DM-managed via `/clock` command group: create, tick, untick, list, reset, delete
- Autocomplete on `name` parameter
- Capacity 2-12, names case-insensitive
- Manual-only by design — no auto-spawn

### Character context cache (`dnd_orchestration.py`)
- In-process dict, keyed by character name
- Built from Avrae `!sheet`/`!beyond` embed by `parse_avrae_sheet_embed()`
- Static identity only: race, class, level, AC, HP_max, init, passive perception, saves, skills, attacks, resistances, narrative_tags
- Volatile state (current HP, slots, conditions) stays Avrae's job
- `narrative_tags` inferred from class+race+skills+attacks: darkvision, lockpicker, stealth_specialist, frontliner, arcane_caster, divine_caster, healer, social_specialist, ranged_combatant
- Invalidation triggers: `/refresh`, `/bindchar`, bot restart

### Persistence layer (Phase 12)

**Tables:**
- `dnd_npcs` — canonical narrative entities. FK `location_id` → `dnd_locations`.
- `dnd_locations` — canonical world geography. Self-FK `parent_location_id`.
- Both keyed unique on `(campaign_id, canonical_name)`.
- Both have `skeleton_origin INTEGER DEFAULT 0`, `mention_count INTEGER DEFAULT 0`, `aliases TEXT` (JSON), `description`, `origin_excerpt`, `first_mentioned`, `last_mentioned`.

**Single write paths:**
- `npc_upsert()` — only writer for `dnd_npcs`. Five branches: insert / parser×parser / parser→skeleton promotion / skeleton×skeleton reload / skeleton lock.
- `location_upsert()` — only writer for `dnd_locations`. Same five-branch matrix.
- `set_current_location(campaign_id, location_id|None)` — only writer of `dnd_scene_state.current_location_id`. Validates FK existence in campaign before writing. `None` clears (wilderness/transitional).

**Identity normalization (deterministic):**
- `canonicalize_name(s)` — NPCs. Whitespace strip + collapse + curly-quote ASCII + leading-honorific strip (whole-word, iterative, never consumes last token). "Sir Aldric" → "Aldric".
- `canonicalize_location_name(s)` — locations. Same + leading-article strip (the/a/an). "The Rusty Anchor" → "Rusty Anchor".
- "Theramore", "Lordran", "Anvilrest" stay intact — article/honorific must be a whitespace-separated token.

**Authority lock:**
- `skeleton_origin=1` rows: parser hits NEVER overwrite authored fields, only bump `mention_count`/`last_mentioned`.
- `skeleton_origin=0` rows: skeleton load can promote, taking authored fields as authoritative.
- Promotion is manual only. Auto-promotion never happens.
- Strict literal match — `Eldrin Stormbow` and `Eldrin` are two separate rows. `npc_health` fragmentation telemetry measures the drift; no automatic merging.

**Advisory parsers** (`npc_extractor.py`, `location_extractor.py`):
- Narration-only input. Never see player intent.
- Strict whitelist on output (regex + stoplist + length caps + bad-char refusal).
- LLM-emitted JSON, parsed defensively, normalized + validated + deduplicated before write.
- Fire-and-forget background tasks — never block narration.

**Authored canon loader (`skeleton_loader.py`):**
- Per-campaign markdown at `/home/jordaneal/scripts/campaigns/<id>/skeleton.md`.
- `parse_skeleton_file()` — strict parser, mtime-cached. Raises `SkeletonParseError` on malformed structure.
- `apply_skeleton(campaign_id)` — idempotent. Two-pass: insert all rows, then backfill `parent_location_id` and NPC `location_id` via FK resolution.
- `get_skeleton_prompt_block(campaign_id, max_chars=6000)` — prepended to `dm_respond` system prompt every turn, sub-millisecond on cache hit.
- `/skeleton load` and `/skeleton status` Discord commands (DM-only).

**Movement primitive (Ship 1):**
- `/travel <destination> [elapsed] [arrival_time]` — soft-skip with authoritative `TRAVEL_TRANSITION:` directive. Sets `current_location_id` if destination resolves; otherwise footer-override surfaces intended location for the transition turn.
- `transition_context` plumbing reusable for future `/rest`, `/camp`, `/downtime`, `/fastforward`.

**NPC stat hydration (Track 6 #4):**
- `/hydrate <npc> <cr>` (DM-only) — DM's authoritative stat-correction path. Validates CR via `normalize_cr()`, calls `npc_hydrate_stats(source='explicit_hydrate')` (always-overwrite — §11.H lock), returns ephemeral confirmation with stat block. No sync hint to Avrae (§11.D). Valid CRs: 0, 1/8, 1/4, 1/2, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12.
- `npc_hydrator.py` — pure-function module. `hydrate_npc_stats(cr_str) → dict` (16 bands, Doctrine §1: no LLM in CR path). `normalize_cr(raw)` handles decimals, fractions, unicode, spelled-out forms. `fallback_stats()` returns CR-1/4 dict.
- `npc_hydrate_stats(campaign_id, name, cr_str, source) → (bool, dict)` — single write path for stat hydration. Source-based fill rule: hook sources (skeleton/hook/adhoc/generic_fallback) use idempotent NULL-fill (WHERE col IS NULL); `explicit_hydrate` (/hydrate slash command) always-overwrites all 6 stat fields. `generic_fallback` writes all stats EXCEPT `hp_max` (§1 decision 7 — leaves HP unknown until DM provides real CR). Engine NEVER resolves `cr_str=None` for non-generic_fallback sources (§11.L caller-side decision).
- `npc_register_avrae_madd(campaign_id, name) → (bool, dict)` — registers `!init madd` creatures in `dnd_npcs` with `avrae_source='avrae_madd'`; leaves all stat columns NULL (Avrae owns mechanics for these creatures). Idempotent.
- `stat_incomplete(npc) → bool` — True if any of {hp_max, ac, attack_bonus} is NULL. Init-list hook hydration trigger.

**Telemetry (Phase 12 + Ship 4):**
- `npc_fragmentation_report(campaign_id)` — measurement primitive, greedy clustering by token-prefix. Logs every turn as `npc_health: campaign=N entities=X rows=Y fragmentation_rate=Z%`.
- `phantom_location_candidates(campaign_id, threshold=3)` (Ship 4) — surfaces parser-origin rows (`skeleton_origin=0 AND mention_count=1`) that haven't been re-mentioned while N other distinct locations have been touched since. Turn proxy: count of OTHER `dnd_locations` rows in the same campaign with `last_mentioned > candidate.first_mentioned`. Distinct, not chattiness — schema is one-row-per-location with last_mentioned bumped in place. Pure read, no mutations. Logs every turn as `phantom_candidates: campaign=N count=K threshold=3 candidates=[id=X/Name/turns=Y, ...]`. **Phantom vs emergent indistinguishability is intentional** — the metric flags candidates, the human distinguishes typo phantoms from real geography that hasn't yet earned a re-mention.
- `world_health_report(campaign_id, phantom_threshold=3)` (Ship 4) — aggregate composing `npc_fragmentation_report` + `phantom_location_candidates` + a single-query skeleton coverage count. Returns four independent numbers (npc_total, npc_distinct, npc_fragmentation_rate, loc_total, loc_skeleton, loc_skeleton_coverage, loc_phantoms, phantom_threshold). **Deliberately not a composite 0-100 score** — weighting fragmentation against coverage against phantom count is unjustified speculation; a single number hides the underlying signal. Logs every turn as `world_health: campaign=N npc_frag=X% npc_rows=Y loc_skel_cov=Z% loc_phantoms=K loc_total=T`.
- All three log lines fire on every extraction turn (including empty turns) for continuous time-series coverage. Granular `npc_health` and `phantom_candidates` keep firing alongside `world_health` — the aggregate composes, doesn't replace.

### Campaign management (Session 13)

The campaign lifecycle has a complete user-facing surface backed by single-write-path engine primitives.

**Engine primitives (`dnd_engine.py`):**
- `_VALID_CAMPAIGN_STATUSES = ('active', 'inactive', 'archived')` — enumerated in code, not as DB CHECK constraint.
- `campaign_set_status(campaign_id, status)` — single transaction. Setting `'active'` demotes any sibling active in the same guild AND un-archives if the row was archived (per design — switching IS the act of un-archiving). Cross-guild isolated. Refuses on missing campaign or invalid status.
- `_CAMPAIGN_SCOPED_TABLES` — canonical 7-table list (above). Source of truth for the cascade.
- `campaign_delete_cascade(campaign_id)` — hard delete across 8 tables (the 7 per-campaign tables + `dnd_campaigns`). Single transaction with rollback on error. Returns per-table `rows_deleted` dict for verification. Refuses on active campaign at the engine layer (engine defends invariant, callers trust the engine).

**Discord commands (`discord_dnd_bot.py`):**
- `/setcampaign <id>` — switch active. Verifies campaign exists in this guild. Confirmation message shows new active + previous active demoted + un-archive note when applicable.
- `/deletecampaign <ids>` — soft-delete (status → archived). Accepts comma-separated list (`5,6,7,8`). Atomic batch — any conflict (not in this server, currently active, already archived, unparseable) refuses the whole batch with all problems listed. Reversible via `/setcampaign`.
- `/campaigns` — lists active + inactive only. No flags. Pointer to `/archived` if there's nothing to show.
- `/archived` — separate command for archived campaigns. Footer reminds of restore + permanent-delete options.
- `/purgecampaign <id> <confirm_phrase>` — hard delete. Three independent gates: archived-only structurally (refuses active or inactive), exact phrase `DELETE <name>` (whitespace-normalized for Discord client artifacts), engine-layer cascade refusal as defense-in-depth.
- `/purgeallcampaigns <confirm_phrase>` — bulk hard delete. Two independent gates: phrase `DELETE ALL ARCHIVED` exact, and only iterates over `status='archived'` rows. Active and inactive campaigns are structurally untouchable. Reports per-campaign success and aggregate row counts.

### S9 — Equipment grounding (Session 13)

Track 2 entry point shipped. Constraint-aware narration safety layer over partial projections — NOT a truth engine.

**Architectural framing (locked):**
- **Avrae attacks** = combat configuration subset (NOT ownership truth)
- **skeleton.md** = author-declared capability HINT layer (additive, never contradicts)
- **DDB** = external visual truth, DM-visible, NOT ingested by bot
- All three are partial projections. **Absence of data is NOT evidence of absence.**

**Three-state verdict (`CapabilityVerdict` enum, module scope in `dnd_orchestration`):**
- `CONFIRMED` — claim matches an Avrae attack OR a skeleton-declared specific item
- `VALID_BUT_UNCONFIGURED` — claim detected; no source confirms; no source contradicts. Default for unmatched claims under partial projections.
- `INVALID` — explicit contradiction from an authoritative source. **No producer in v1** — reserved for future DDB ingestion or DM-override layer that explicitly disallows.

**Matching rules (strict, table-driven):**
- All matching is exact full-string equality, lowercased on both sides.
- No substring, no token, no regex inference, no partial matching.
- Player generic noun (key in `WEAPON_CAPABILITIES`) → expand to alias list, exact-equality against attacks/skeleton.
- Player specific noun → match only that exact noun in attacks/skeleton.
- Skeleton entries are specific-item-only at the matching layer; authors may write either generic or specific (both validated).
- "If anything doesn't match cleanly, the fix is data (aliases), not logic."

**Skeleton schema extension (Phase 12C → S9):**
- New `## Player Capabilities` section in skeleton.md
- One bullet per character: `- Donovan Ruby: shortsword, shortbow, dagger`
- Parser produces `dict[str, set[str]]` (character display name → set of weapon family/item names)
- `get_player_capabilities(campaign_id)` accessor in `skeleton_loader` validates against `WEAPON_CAPABILITIES`, drops unknowns with greppable warning log
- Character-name lookup is case+whitespace-normalized

**Directive shapes (`CapabilityDecision.to_prompt_directive()`):**
- `CONFIRMED` → silent (empty string, no prompt addition)
- `VALID_BUT_UNCONFIGURED` → soft annotation: `"Mark this item as UNVERIFIED... do not treat the item as established equipment in subsequent narration. Do not reference it as if previously confirmed."`
- `INVALID` → anti-fabrication directive (renderer present, producer absent in v1)

**Wired into `dm_respond` next to `should_call_roll`. Logging policy:**
- Logs every non-no-claim outcome: `capability_check: actor=X claim='Y' verdict=Z source=avrae|skeleton matched='M'` for CONFIRMED, full attacks+skeleton context for VALID_BUT_UNCONFIGURED
- No-claim turns silent (regex didn't match)

**Scope boundaries (NOT in S9):**
- Spells, items beyond weapons, inventory bookkeeping → S9.x / S20 / future
- Cross-actor capability ("I borrow Borin's sword") → deferred until multiplayer
- Mode-independence — capability claims happen in any mode; check doesn't read mode
- **Narrative-history repair** (LLM committed fictional gear in prior turns) → Phase 4, separate subsystem. S9 explicitly does not retroactively repair.

**Live verification:** Donovan Ruby (Dwarf Rogue 1, Avrae attacks=[Unarmed Strike]) tested. Dagger claim → VALID_BUT_UNCONFIGURED with UNVERIFIED directive. Adding `Donovan Ruby: shortsword, shortbow, dagger` to skeleton_17.md upgrades same claim to CONFIRMED via skeleton.

### Track 3 — Directive layer (Session 14)

The architectural shift from declarative state to operational directives. Phase 1/12 solved "what is true?" / "what exists?" / "what can the player do?". Track 3 solves "what narrative move should happen next?". Three composable directive layers ship together; each reads existing state and renders an imperative (not descriptive) constraint into the prompt.

**Architectural pattern:** Same advisory shape as roll_directive and capability_directive. Each directive is a pure function in `dnd_orchestration.py` that reads state and returns a string (empty = silent). `build_dm_context` accepts each as a keyword parameter and renders only when non-empty. `dm_respond` computes each before the build call and logs every non-silent emission.

**Imperative-not-descriptive rule:** "Force a decision" beats "the air feels tense." "An NPC must commit to a course of action this turn" beats "describe urgency." The first changes pacing; the second is flavor text. This distinction is the entire difference between Track 3 working and not.

**Pacing directive (`compute_pacing_directive(scene_state)`):**
- Reads `tension_int` (0-100) and `progress_clocks`
- Tier thresholds match `tension_label()` boundaries: ≤25 silent, 26-60 mounting, 61-85 dangerous, 86+ climax
- Urgent-clock callout fires independently when any clock ≥80% filled (`PACING_URGENT_CLOCK_THRESHOLD`)
- Tier directives: mounting = "Don't let the scene settle without cost" / dangerous = "Escalate consequences this turn" / climax = "Something concrete must shift this turn"
- `pacing_log_summary()` produces compact log line: `tier=X tension=N clocks=[(name:ticks/cap:pct%), ...]`
- Renders as `=== PACING DIRECTIVE ===` block

**Central thread directive (`compute_central_thread_directive(hooks)`):**
- Reads `parsed_skel['hooks']` from skeleton_loader (first bullet under `## Major hooks`)
- Surfaces hooks[0] as the campaign's gravitational pull
- Phrasing explicitly forbids literal restatement — guards against keyword-stuffing the hook into every response. The directive instructs: indirect signals only (NPC behavior, environmental detail, time pressure, consequence shape); don't name or restate the thread unless the scene already calls for it directly
- Composes with pacing: pacing pressures FOR a decision, central thread pressures TOWARD which direction
- Renders as `=== CENTRAL THREAD ===` block
- Logged as `central_thread: hook='<text>' (1 of N)`

**DM philosophy layer (`dm_philosophy_loader.py` + `dm_philosophy.md`):**
- Single global file at `/home/jordaneal/scripts/dm_philosophy.md` (NOT per-campaign)
- Mirrors skeleton_loader's mtime-cache pattern but globally keyed (no campaign_id)
- File body injected verbatim, capped at 6000 chars (`PHILOSOPHY_MAX_CHARS`)
- Empty/missing file suppresses block entirely
- Living artifact authored by Jordan, reload is automatic on file change
- Sits HIGH in prompt template (after canonical state blocks, before tactical directives) — frames how all subsequent directives are interpreted. State outranks policy; policy outranks individual move directives
- Renders as `=== DM PHILOSOPHY ===` block
- Logged as `dm_philosophy: loaded (N chars)`

**Prompt template ordering (build_dm_context):**
1. Setting & tone (HARD CONSTRAINT)
2. Party
3. Current scene + mode_block
4. Scene state section (LOCKED_FIELDS canonical, includes Recently active NPCs derived from `last_mentioned`)
5. Quests / character contexts / relevant history (state)
6. **Philosophy block (interpretation policy)**
7. Guidance / Avrae events / roll directive / capability directive
8. **Pacing directive / central thread / consequence directive / commitment directive (tactical move pressure)**

**Composability:** All four tactical layers can be tuned independently. Pacing thresholds via constants. Central thread via skeleton authoring. Philosophy via doc edits. Commitment via the Session 19 helpers (`SCENE_SHIFT_RX`, `_REACTION_VERBS`, `_RETRACTION_RX`). None of them know about each other; the LLM weights all of them against scene state and player input.

### Track 3 — Consequence surfacing (Session 16)

The fourth tactical directive. Reads accumulated consequences against canonical NPCs and surfaces imperative pressure on what the world remembers. Targets `THE_GOAL.md` failure modes "NPCs we wronged should still be wronged" and "if the world reacts the same to mercy as it does to slaughter, we've failed." See `CONSEQUENCE_SURFACING_SPEC.md` for the locked design.

**Schema additions:**
- `dnd_consequences` — new table (id, campaign_id, npc_id, kind, summary, severity, sources, captured_at, captured_turn, first_seen_turn, last_seen_turn, last_surfaced_at, last_surfaced_turn, surface_count, distinct_surface_turns, status, promoted_at). UNIQUE on `(campaign_id, npc_id, kind)`.
- `dnd_scene_state.turn_counter` — per-campaign monotonic axis added via idempotent ALTER. Single writer is `increment_turn_counter()`, called at the END of every successful `dm_respond` turn.

**Locked taxonomy (6 kinds, definitions verbatim — must not be paraphrased in code or prompts):**
- `threat` — credible future harm or pressure (not executed action)
- `mercy` — restraint when harm was available
- `cruelty` — harm exceeding necessity
- `betrayal` — violation of trust/expectation
- `promise` — explicit commitment affecting future state
- `alliance` — mutual alignment / shared objective formation

`debt` is explicitly NOT a kind — it is a derived state from promise/alliance/betrayal history. Future derivation, not capture.

**Capture is dual-pass, not single-blended.** Two parsers in `consequence_extractor.py`, each reading ONE channel only:
- `parse_consequences_player(player_text, campaign_id=None)` → captures player commitments, social acts, acts initiated against NPCs. **OOC contamination guard (S21):** leading-marker filter (`((`, `[OOC]`, `OOC:`, `//`) short-circuits before any LLM call; emits `consequence_ooc_filtered` diagnostic.
- `parse_consequences_dm(dm_text)` → captures world reactions, fallout, NPC-side commitments emergent from DM narration. No OOC filter — the DM channel is LLM-emitted, not player-typed.

A single blended parser is architecturally rejected — it creates self-reinforcing hallucination loops where one event (player's threat → DM narrates landing → parser captures both) inflates into multiple consequences. Channel separation preserves the mechanics-vs-narrative invariant. Both parsers use the same 6-kind taxonomy; the source tag (`'player'` or `'dm'`) accumulates per-row in the `sources` field via comma-merge on upsert.

**Severity** is parser-judged 1–3. Validator only enforces the range; the numeric meaning is descriptive in the parser prompt (1=minor, 2=notable, 3=major) but not code-baked. MAX-on-upsert: a higher-severity capture wins.

**Surfacing** (`compute_consequence_directive(active_consequences, in_scope_npc_ids)`): filters to consequences whose `npc_id` is in scope (recently active NPCs ∪ NPCs at current location), sorts by severity DESC then `last_surfaced_turn` DESC (NULLs last) then `id` ASC, **caps at 3**. Six-in-prompt is too many; three preserves narrative weight per row. Renders as `=== PENDING CONSEQUENCES ===` block with `[kind, sev N]` tags per row plus a manifestation-not-restate guard.

**Promotion to NPC traits** (`maybe_promote_consequences`) requires ALL three thresholds:
- `surface_count >= 3`
- `distinct_surface_turns >= 2` (distribution check — prevents 3-emit single-turn conversations from false-promoting)
- `(current_turn - first_seen_turn) >= 10`

Graduated rows append `[promoted: kind] {summary}` to the target NPC's `description` and flip `status='promoted'`. Promoted rows reject re-capture (logged, no write) and never appear in the directive. v1 ships with acknowledged double-encoding (DB row stays + prompt block carries the prose memory via NPC description); v2 direction is `DB is source of truth, prompt is projection` for the memory tiering spec to inherit.

**Wiring (`dm_respond`):**
1. Read `current_turn = get_turn_counter(campaign_id)` at start.
2. `maybe_promote_consequences(campaign_id, current_turn)` BEFORE directive composition.
3. Build in-scope ids = `get_recently_active_npc_ids(campaign_id, limit=6)` ∪ `get_npc_ids_at_location(campaign_id, current_location_id)`.
4. `get_active_consequences(campaign_id, npc_ids=...)` → `compute_consequence_directive` → text + surfaced rows.
5. `consequence_emit_surface(c['id'], current_turn)` for each emitted row.
6. Pass directive text to `build_dm_context(consequence_directive=...)`.
7. After narration: spawn `parse_consequences_player` and `parse_consequences_dm` as background threads, each calling `apply_consequence_proposals(campaign_id, ..., source=..., current_turn=current_turn)`.
8. `increment_turn_counter(campaign_id)` at the END of the successful turn (capture threads hold `current_turn` via closure).

**Composition order** in `build_dm_context`: consequence directive renders AFTER pacing and central thread, in the same tactical band (`{pacing_directive_block}{central_thread_block}{consequence_block}`). Philosophy stays high in the prompt as the framing layer; consequences are tactical, below that frame.

**Debug surface (v1 minimal):** `/consequence list [npc]` — read-only ephemeral. Displays per-row first_seen_turn, kind, canonical NPC, severity, status, sources, surface_count, summary. Truncates with note when output exceeds Discord's char limit. NO add/remove/inspect commands in v1 — captures must come from the parser, not from operator entry; the operator inspects what was written.

**Live verification deferred:** v1 ships, log lines (`consequence_captured`, `consequence_directive`, `consequence_promoted`, `consequence_rejected`) drive parser tuning. Multiplayer verification waits for the multiplayer table.

### Track 3 — Committed-action resolution (Session 19, escape-only v1)

The fifth tactical directive. Closes the **escape-half** of the godmode failure mode: a player commits to violence (turn N), next turn types an unrelated action (turn N+1), the DM accepts the new action and the prior commitment evaporates. See `COMMITTED_ACTION_RESOLUTION_SPEC.md` and the locked `COMMITTED_ACTION_RESOLUTION_REVIEW.md` for the design.

**Schema additions:**
- `dnd_scene_state.last_dm_response TEXT DEFAULT ''` — most recent DM narration, tail-keep last 4000 chars. Single writer is `update_last_dm_response(campaign_id, text)`, called between cleaned narration emission and turn-counter increment so the next turn's directive reads "the prior turn's DM response" cleanly. Idempotent ALTER, same shape as `last_player_action`.

**Detection (`compute_commitment_directive(...)` in `dnd_orchestration.py`):** pure function with five gates, all of which must hold for the directive to fire:
1. `intent_prior == INTENT_COMBAT` — locked §11.1 (COMBAT-only scope; RISKY/CONTESTED godmode is conjectural until logs prove otherwise)
2. `avrae_resolved_since_prior` is False — no `attack`/`cast`/`damage` event for this turn (mechanical resolution = commitment landed)
3. `_has_reaction_verbs(prior_dm_response, target_hints)` is False — regex resolution check, locked §11.2 (no second LLM call)
4. `is_scene_shift_intent(current_action_text)` is True — scene shift, not continuation
5. `_is_retracting(current_action_text)` is False — locked §11.D (explicit retraction is a creative narrative choice the spec must allow)

**Target hints (`prior_target_hints`):** `get_recently_active_npcs(campaign_id, limit=6)` ∪ `get_npc_names_at_location(campaign_id, current_location_id)`. Same scoping rule as the consequence directive (locked §11.B).

**Directive body:** imperative three-option text (a) narrate prior consequence first, (b) refuse new action through in-fiction beat, (c) require a roll for the new action with a cost — plus the B2.1 narration mandate ("Your narration MUST address the prior commitment before any new content; a response that ignores the prior commitment is INSUFFICIENT and breaks the table"). Renders as `=== UNRESOLVED COMMITMENT ===` block.

**Composition order:** AFTER consequence in the tactical band of `build_dm_context` (locked §11.8). Matches the `commitment=` slot reserved Session 18 in the `directive_emit` log shape.

**Telemetry:**
- `commitment_directive: campaign={N} fired={1|0} prior_intent={intent} current_intent={intent} is_scene_shift={1|0} avrae_drained={1|0} reaction_verbs={1|0} retraction_filtered={1|0}` — emitted EVERY turn (regardless of whether the directive fires) so the empirical baseline of gate hit rates is observable. Same diagnostic-baseline doctrine as `godmode_gap`.
- `commitment_retraction_filtered: campaign={N} text={first 80 chars}` — emitted only when retraction grammar suppressed an otherwise-firing directive. Per §11.D fix-and-diagnostic doctrine.
- `directive_emit: ... commitment={1|0}` — promoted from the `commitment=0` Session 18 placeholder to a real per-turn fire indicator.

**Out of scope (filed for sibling specs):**
- Layer-3 (Avrae init binding) and layer-4 (deterministic mode flip) of the four-layer attack chain — Combat Initiation Orchestration spec, see ROADMAP pre-friends gating ship #2.
- RISKY / CONTESTED godmode (pickpocket-then-leave, intimidate-then-walk-away) — locked §11.1 (COMBAT-only scope earns its turn from observed signal).
- Multi-turn lookback — locked §11.6 (single-turn covers the load-bearing case; multi-turn earns from observed misses).

### Track 4 — Corpus reconnaissance (Session 14, data only)

Inventory pass produced concrete metrics on `/mnt/virgil_storage/dnd_datasets`. Report at `/mnt/virgil_storage/digest/corpus_inventory_report.md` (markdown) + `.json` (sidecar). No extraction yet, no chroma writes — pure read.

**CRD3 (889MB, 1140 files):** 2.94M turns. **355,892 substantive Matt Mercer DM turns** (≥15 words). 53.8% average alternation rate. 29,850 multi-turn sequences (≥10 turns/chunk). Episodes are ~2,500 turns each, full sessions. Viable for beat extraction; extraction taxonomy is the hard part.

**FIREBALL (2.0GB, 1471 files):** 153,829 records, 78.3% with before_utterances. **Zero multi-utterance records ≥10 turns.** Each record is a moment, not a sequence. Useful for single-action context patterns; not for sequence learning. ChatGPT's beat-extraction vision assumed FIREBALL would carry sequence weight — it doesn't. CRD3 does.

**Strategic implication:** Track 4 is now scopable. Right next move (when prioritized) is hand-extraction from a 10-episode CRD3 slice to discover useful beat categories *before* building the extractor. Without a real taxonomy from data, an extraction engine is design-by-vibes.

### Routing (`cloud_router`)
- DnD task → `groq_heavy` (`gpt-oss-120b`) primary, scoped priority override bypasses score-sort. Reason: gpt-oss respects HARD STOP rules and sampling penalties; Llama-3.3-70b doesn't.
- Trivial → local Qwen via Ollama `/api/chat`.
- Reasoning-heavy → `groq_heavy`.
- `extraction` task type — bounded structured-output for advisory parsers.
- Default → groq.

Reason codes: `DND_PRIORITY_OVERRIDE` (DnD task, candidate ordering wins) / `SCORE_SORT` (other tasks, latency-based).

DnD-only sampling penalties: `frequency_penalty=0.5`, `presence_penalty=0.4`. Effective on gpt-oss; Llama largely ignored them.

### `/patch` and `/deploy` (Virgil self-mod)
- `/patch [function_name]: [description]` — sends function only, fits in context. Syntax check → diff → confirm → atomic swap → `os.execv` restart.
- `/deploy` — paste function directly, no LLM. Same diff/confirm/restart.

### Calendar (Virgil)
- All operations via gog CLI (`/home/linuxbrew/.linuxbrew/bin/gog`).
- Personal cal: `jordaneal@gmail.com`
- Family cal: `family17072034232008398967@group.calendar.google.com`

---

## 7. SQLite Schema

Shared `virgil.db` at `/mnt/virgil_storage/virgil.db`.

```sql
-- Virgil personal assistant
messages         (id, chat_id, role, content, route, provider, ts)
facts            (id, key, value, updated_at)
pending          (chat_id, data, ts)

-- DnD core (Sessions 5-8)
dnd_campaigns    (id, name, created_at, status, world_notes, current_scene,
                  guild_id, tone, created_by_user_id)
dnd_characters   (id, campaign_id, name, race, class, level, controller,
                  alive, ...)  -- legacy mechanical cols, no longer authoritative
dnd_scene_state  (campaign_id PK,
                  -- narrative (LLM extraction writes):
                  location, focus, established_details, active_npcs,
                  active_threats, open_questions, last_player_action,
                  last_scene_change, updated_at,
                  -- authoritative (deterministic writes only):
                  mode, tension_int, progress_clocks,
                  current_location_id,                 -- Phase 12B
                  turn_counter,                        -- Session 16
                  last_dm_response,                    -- Session 19
                  -- legacy:
                  tension)
dnd_combat_state (campaign_id PK, controller_id, character_name, round,
                  updated_at)                          -- Phase 2A
dnd_quests       (id, campaign_id, title, summary, status, priority,
                  given_by, created_at, updated_at)    -- Phase 2C.2
dnd_companions   (id, campaign_id, name, persona, created_at, updated_at)
                                                       -- Phase 2C.3

-- DnD persistence (Phase 12)
dnd_npcs         (id, campaign_id, canonical_name, aliases, role,
                  location_id, description, skeleton_origin,
                  mention_count, origin_excerpt,
                  first_mentioned, last_mentioned,
                  -- Track 6 #4 stat hydration columns (all nullable):
                  hp_max, ac, attack_bonus, damage_dice,
                  save_bonus, init_mod, cr_str, avrae_source)
dnd_locations    (id, campaign_id, canonical_name, aliases, type,
                  parent_location_id, description, skeleton_origin,
                  mention_count, origin_excerpt,
                  first_mentioned, last_mentioned)

-- DnD consequence ledger (Session 16)
dnd_consequences (id, campaign_id, npc_id, kind, summary,
                  severity, sources,
                  captured_at, captured_turn,
                  first_seen_turn, last_seen_turn,
                  last_surfaced_at, last_surfaced_turn,
                  surface_count, distinct_surface_turns,
                  status, promoted_at)
                 -- UNIQUE(campaign_id, npc_id, kind)
                 -- status: 'active' | 'promoted'
                 -- sources: comma-merged 'player' | 'dm' | 'dm,player'

-- Combat persistence (Session 21)
dnd_combatant_state (campaign_id, name, init,
                     hp_current, hp_max, conditions,
                     alive, side, updated_at)
                    -- PRIMARY KEY (campaign_id, name)
                    -- Replace-in-place per !init list snapshot.
                    -- Single writers: update_combatants_from_init_list /
                    -- clear_combatants. side defaults 'unknown' in v1.

-- Narrative inventory (Track 4 #1, Session 22)
dnd_inventory    (id, campaign_id, character_name,
                  item_name, quantity, metadata, created_at)
                 -- INDEX (campaign_id, character_name, item_name)
                 -- item_name stored lowercase + whitespace-collapsed;
                 -- lookup case-insensitive. Single writers: add_item /
                 -- remove_item. Distinct from Avrae sheet-bound combat
                 -- gear — Virgil holds narrative items only.

-- Pending loot queue (Track 4 #2, Session 22)
dnd_loot_pending (id, campaign_id, creature, table_key,
                  coin_amount, coin_denom, items,
                  surfaced, surfaced_at, created_at)
                 -- INDEX (campaign_id, surfaced)
                 -- items stored as JSON array text.
                 -- Populated by update_combatants_from_init_list
                 -- when alive=1 -> alive=0 transitions; PCs filtered
                 -- via get_bound_character_names. Surface-and-clear:
                 -- compute_loot_directive renders pending rows;
                 -- dm_respond marks surfaced AFTER LLM call succeeds.
                 -- Single writers: enqueue_loot / mark_loot_surfaced.
                 -- Loot tables in loot_tables.py (substring + case-
                 -- insensitive match against creature name).

-- Cold storage
dnd_srd          (kept for reference, no longer queried)
```

`LOCKED_FIELDS = {'mode', 'tension', 'active_npcs', 'active_threats'}` enforced at `update_scene_state()` boundary. Add new structural fields to LOCKED_FIELDS in the same patch that introduces them.

Migrations are idempotent via `PRAGMA table_info` check before `ALTER TABLE`. Pattern is established in `db_init()`. Safe to re-run.

---

## 8. Phase Status (one-line summary; details in ROADMAP.md and session files)

| Phase | Description | Status |
|---|---|---|
| Phase 1 | Roll Discipline + Sheet + Scene + Modes | ✅ COMPLETE |
| Phase 2 | Combat / Observability / Narrative Fidelity | ✅ COMPLETE |
| Phase 3 | Suggestion + Auto-Execute | ✅ VALIDATED LIVE |
| Phase 10 | Model swap, coverage audit, perm unlock | ✅ COMPLETE |
| Phase 11.1 | Mechanical Hints (advisory parser) | ✅ SHIPPED LIVE |
| Phase 12 | Persistent canon (NPCs, locations, skeleton) | ✅ SHIPPED LIVE |
| Ship 1 | `/travel` + location surfacing | ✅ SHIPPED LIVE |
| Ship 2 | Companion autocomplete + quest reminders | ✅ SHIPPED LIVE |
| Ship 4 | Phantom-location telemetry + `world_health` aggregate | ✅ SHIPPED LIVE |
| Campaign management | `/setcampaign`, `/deletecampaign` (batch), `/archived`, `/purgecampaign`, `/purgeallcampaigns` | ✅ SHIPPED LIVE |
| Roll discipline drift fix | Mode-aware `classify_action_intent` + RISKY_RX negative lookaheads | ✅ SHIPPED LIVE |
| S9 — Equipment grounding (v1) | 3-state CapabilityVerdict + skeleton hint layer + UNVERIFIED narration directive | ✅ SHIPPED LIVE |
| Bot startup auto-cache (S14) | `_warm_character_cache_on_startup` scans recent history for Avrae sheets | ✅ SHIPPED LIVE |
| `virgil-discord` sentinel monitoring | Added to `sentinel.sh` health checks | ✅ SHIPPED LIVE |
| COMBAT_RX false-positive cleanup | Dropped `fire`/`shoot`/`loose` from combat verb list | ✅ SHIPPED LIVE |
| Track 3 — Pacing directive | tension/clocks → imperative narrative-move constraints | ✅ SHIPPED LIVE |
| Track 3 — Central thread directive | First skeleton hook → directional pressure (gravity-not-refrain) | ✅ SHIPPED LIVE |
| Track 3 — DM philosophy layer | Authored doc, mtime-cached, frames directive interpretation | ✅ SHIPPED LIVE |
| Phase 6 — Actor name reconciliation (S15) | Strict-only canonical/alias resolution, dual-pass cache warming | ✅ SHIPPED LIVE |
| PC contamination guard (S15) | Two-layer defense: `npc_extractor.pc_match` filter + engine `npc_upsert` refusal | ✅ SHIPPED LIVE |
| Track 3 — Consequence surfacing v1 (S16) | `dnd_consequences` ledger + dual-pass parsers + cap-at-3 directive + promotion to NPC traits + `/consequence list` debug | ✅ SHIPPED LIVE |
| Track 3 — Committed-action resolution v1 (S19, escape-only) | `compute_commitment_directive` + 5-gate filter (COMBAT prior, scene-shift current, Avrae undrained, no reaction verbs, no retraction) + B2.1 narration mandate. New `last_dm_response` column on `dnd_scene_state`. `commitment_directive:` per-turn aggregate + `commitment_retraction_filtered:` diagnostics. Layer-3/4 deferred to Combat Initiation Orchestration spec. | ✅ SHIPPED |
| Track 3 — Combat Persistence Directive v1 (S21) | New `dnd_combatant_state` schema fed by `parse_init_list_embed` (deterministic regex over Avrae `!init list` plaintext, replace-in-place per snapshot). `compute_persistence_directive` master-gates on `mode=='combat'`, renders concrete per-combatant block (HP, conditions, alive/dead) + ON-turn confirm / naming-only initiative block. OFF-turn rendering dropped — Phase 2A.3 `on_message` gate is the architectural prior. `init_list_parsed:` and `persistence_directive:` per-turn telemetry. `directive_emit: persistence={0\|1}` slot. | ✅ SHIPPED LIVE |
| Track 4 — Narrative Inventory v1 (S22) | New `dnd_inventory` schema (`id`, `campaign_id`, `character_name`, `item_name`, `quantity`, `metadata`, `created_at`; INDEX on lookup triple). Item names stored lowercase + whitespace-collapsed; lookup case-insensitive. Single writers `add_item` / `remove_item` (replace-in-place increment / decrement; refuses non-positive quantities, refuses over-removal); pure reads `get_inventory` / `has_item`. `/inventory [character]` (player-accessible, defaults to caller's bound character) + `/giveitem <character> <item> [quantity]` (DM-only) slash commands with bound-character autocomplete. `=== {CHARACTER}'S NOTABLE ITEMS ===` block in `build_dm_context` after the party block, sourced from `acting_character_names[0]` so render works without cached Avrae sheet. Capped at 8 items shown with `... +N more` truncation. Telemetry: `inventory_add` / `inventory_remove` / `inventory_give` / `inventory_render`. Item-claim capability integration (verdict shift `VALID_BUT_UNCONFIGURED → CONFIRMED`) deferred to v1.x — needs ITEM_CLAIM_RX design pass (verb taxonomy + preposition handling + false-positive guards). v1's load-bearing surface is the prompt-context render: LLM sees the inventory and narration honors it. Distinct from Avrae sheet-bound combat gear (weapons / armor); no sync layer. 31 assertions in `test_inventory.py`. | ✅ SHIPPED LIVE |
| Track 4 — Loot Generation v1 (S22 #2) | New `loot_tables.py` (pure, no DB) with five starter creatures (`goblin`, `wolf`, `bandit`, `skeleton`, `cultist`) + `_default` fall-through; substring + case-insensitive name match; dice-coin rolls (`2d6 sp` etc); `generate_loot()` returns `{creature, table_key, coin, items}`. New `dnd_loot_pending` schema (`id`, `campaign_id`, `creature`, `table_key`, `coin_amount`, `coin_denom`, `items` JSON, `surfaced`, `surfaced_at`, `created_at`; INDEX on `(campaign_id, surfaced)`). **Architectural pivot** from spec — no standalone defeat-event parser; instead, death-edge detection inside `update_combatants_from_init_list` (SELECT prior alive states before DELETE-INSERT, compute alive=1 → alive=0 transitions, filter PCs via `get_bound_character_names`, hand to `enqueue_loot_for_defeats`). Phase 1 grep across 30+ days of journal logs proved Avrae does NOT emit standalone defeat messages — defeat surfaces only inside `!init list` snapshots; the existing S21 init_list parser already decodes `<0/N HP>` and `<Defeated>` to `alive=0`. Pivot meant zero new wiring in `discord_dnd_bot.py` (S21's dual-channel `_handle_init_list_event` already covers both `on_message` and `on_message_edit`). New `compute_loot_directive(pending_loot)` in `dnd_orchestration.py`: pure function, returns `(body, signals)`. Body uses AUTHORITATIVE/EXHAUSTIVE framing ("These items are AUTHORITATIVE and EXHAUSTIVE — they are everything the bodies carry. Do NOT invent additional items, change quantities, or substitute thematic alternatives. Narrate the discovery of THESE specific items only — if the table lists three items and coin, the player finds exactly three items and exactly that coin, nothing more.") + retrieval override clause ("If retrieved past events ('RELEVANT PAST EVENTS' block above) describe different loot for this body, ignore those descriptions. The list in this block supersedes any prior narration and is the current ground truth.") + dynamic coin example anchored to the directive's own `total_coin_summary` (e.g. `!game coin +12sp for the 12 sp listed above` — never a static placeholder). `build_dm_context` plumbed with `loot_directive=`, renders `=== LOOT TO SURFACE ===` block AFTER `=== COMBAT PERSISTENCE ===`. `dm_respond` surface-and-clear cycle: `get_pending_loot` → `compute_loot_directive` BEFORE `build_dm_context`; `mark_loot_surfaced` per row AFTER `route()` returns non-empty (failed/empty calls leave queue intact for re-fire). Telemetry: `defeat_parsed`, `loot_generated`, `loot_directive` (per turn, every turn), `loot_surfaced` (per directive landing); `directive_emit:` extended with `loot={0\|1}`. Added to `_CAMPAIGN_SCOPED_TABLES`. **v1 surface contract**: loot is generated and surfaced for player to claim — NOT auto-added to inventory. Player uses `/giveitem` or claims through narration. Coin emitted as inline `!game coin +Nsp` mechanical hint (LLM-emitted; bot-Avrae write boundary intact). 77 new assertions across `test_loot_tables.py` (20) / `test_loot_pending.py` (19) / `test_loot_directive.py` (24) / `test_loot_defeat_edge.py` (14). **Live verified S22 12:39** after two-pass live-test iteration (v1 → v1.1 directive tightening for substitution+addition → v1.2 retrieval-override clause + chroma purge of two contaminated DM turns from prior failed passes). Final pass narration matched directive line-for-line: 8 sp → "eight silver pieces", rusty shortsword → "rusted shortsword", crude bow → "crude short-bow", tattered map exact, `!game coin +8sp` exact mechanical hint, zero hallucinated items, zero retrieval contamination. Worked correctly even when looted *during* combat (persistence directive + loot directive in same prompt, both honored). | ✅ SHIPPED LIVE |
| Track 6 — Active-State Footer v1 (S23) | Bot-appended state header in `_dm_respond_and_post` extends the existing `⚔ {actor} 📍 {location} 🗒️ {quests}` embed footer with mode/turn/up-next/action-hint lines above it. New `render_state_footer(scene_state, active_turn, combatants_payload, bound_pc_names) → (text, signals)` in `dnd_orchestration.py` — pure function, no DB, follows the `compute_loot_directive` / `compute_persistence_directive` pattern (third instance). Combat mode renders `⚔ Combat — Round {N}` / `Turn: {name} ({init})` / `Up next: {name} ({init})` / `Your turn — narrate your action, or use !attack / !cast / !check.` (PC) or `NPC turn — wait for resolution, or !init next to skip ahead.` (NPC); fallback line `Turn: (not set — Avrae state may be stale; try !init list)` when `mode=='combat'` but `get_active_turn` returns None (Avrae's pre-`!init next` round-0 state). Exploration mode renders `📖 Exploration`; social mode `💬 Social`; unknown mode `⚠ {mode}` warning prefix. Init-order wraparound for "Up next" (last-in-init wraps back to top of init). PC detection is case-insensitive against `get_bound_character_names`. Soft-fail wrapped at call site — any exception in render or DB reads logs and returns `''` so footer errors NEVER block narration posting. 2048-char defensive cap (Discord embed footer limit). New `state_footer: campaign={N} mode={...} active_turn={name|none} round={N|none}` per-turn telemetry. 27 assertions in `test_state_footer.py` covering all modes (combat PC/NPC/no-active-turn, exploration, social, unknown) + graceful-degrade (None scene_state, None payload, empty combatants, name mismatch with snapshot, single combatant, init wraparound, mid-init "Up next") + determinism + no-input-mutation + PC-detection variants (list/set/None/empty) + telemetry helper edge cases + trailing-newline contract. **Live verified S23 21:23** across 5 stages: exploration baseline (`📖 Exploration`) → `!init begin` + add combatants (combat fallback path: round=`?` + "(not set)" turn line, since Avrae's round 0 has no active actor yet) → `!init next` round 1 (NPC GO1 active, "NPC turn — wait" hint) → `!init next` (PC Donovan active, "Your turn" hint, "Up next" wraps to GO1 at top of init) → `!init next` round 2 (round bump confirmed, NPC hint) → `!init end` (back to `📖 Exploration`). All 8 `state_footer:` log lines clean. | ✅ SHIPPED LIVE |
| Discord channel cleanup + canonical `/setup` (S23 #3) | Consolidated 7-channel pre-S23 layout (`dm-narration`, `dice-rolls`, `character-sheets`, `party-loot`, `lore-notes`, `ooc-general`, `bot-commands`) into 4 canonical text channels (`dm-narration`, `dm-aside`, `lore-notes`, `party-chat`) + 1 voice (`General`) across 3 categories (`🎲 VIRGIL DM`, `💬 OUT OF CHARACTER`, `🔊 VOICE`). Adds `dm-aside` for Track 6 #3 advisory mode. New `compute_setup_plan(...)` in `discord_dnd_bot.py` — fifth pure-function-planner instance. Returns plan dict with create / move / existing / legacy-delete buckets. `/setup` rewritten: builds guild snapshot, calls planner, executes via discord API. `#lore-notes` permissions: @everyone read but not send. Idempotency contract: re-running on canonical guild produces "Nothing to do" ephemeral. Soft-fail throughout. New per-execution `setup_run:` telemetry. 26 assertions in `test_setup_plan.py`. **Live verified S23 23:12 + idempotency check 23:14**. | ✅ SHIPPED LIVE |
| Track 6 — Combat Redirect Directive v1 (S23 #2) | New `compute_combat_redirect_directive(...)` in `dnd_orchestration.py` — fourth pure-function-in-orchestration sibling. Adds informational redirect pressure when player on-turn narration in active combat may attempt to bypass combat reality. Companion to S19's `compute_commitment_directive`; broader scope here. Master gate: `scene_state.mode == 'combat'` AND ≥1 alive non-PC combatant AND active turn matches bound character. Body: `=== COMBAT REDIRECT ===` block AFTER `=== LOOT TO SURFACE ===`. Architecturally explanatory by design — hard refusal lives in 2A.3 (off-turn drop). Soft-fail wrapped in `dm_respond`. New `combat_redirect:` per-turn telemetry; `directive_emit:` extended with `redirect={0\|1}`. 38 assertions in `test_combat_redirect_directive.py`. **Live verified S23 22:35** across 7 paths. | ✅ SHIPPED LIVE |
| Track 6 — Active-State Footer v1 / Combat Redirect v1 / Channel cleanup (S23) | (See three rows above) | ✅ SHIPPED LIVE |
| `/setup` housekeeping (S25) | Three small additions: Avrae permissions reconciled across canonical text channels (`view_channel + read_message_history + send_messages + embed_links + attach_files + add_reactions` on open channels; `#lore-notes` is read-only — Avrae's `!`-prefixed output should never land there); new `#commands` channel under `💬 OUT OF CHARACTER` (sanctioned home for slash commands and Avrae bookkeeping; convention not enforcement; renamed mid-ship from `#ooc-commands` since OOC category prefix made it redundant); new `AFK` voice channel under `🔊 VOICE` + guild AFK auto-move config via `guild.edit(afk_channel=, afk_timeout=1800)` (30-min auto-move). Implementation: new `AVRAE_READ_ONLY = {'lore'}` set + `chan_key` parameter threaded through `canonical_overwrites_dict`. 42 assertions in `test_setup_plan.py` (was 26). | ✅ SHIPPED LIVE |
| Track 6 #3 — OOC Advisory Lane v1 (S25) | New routing branch in `on_message` BEFORE existing `#dm-narration` gate: `if message.channel.name == CHANNEL_NAMES['aside']: ... await _advisory_respond(message); return`. New handler `_advisory_respond(message)` in `discord_dnd_bot.py` — resolves campaign + bound character; pulls state via pure-read engine helpers; builds flat state-reference block via new `build_advisory_context(...)` (pure function in `dnd_orchestration.py`); routes via new `task_type='advisory'` in `cloud_router.py` with new `ADVISORY_SYSTEM_PROMPT`; posts reply with truncate-at-1900-chars. **Load-bearing invariants** (in §4 boundary invariants): no `chroma_store` / no `chroma_search` (Track 4 #2 v1.2 contamination lesson), no scene/combat/inventory/loot writers, no `!`-prefixed bot emission (bot-Avrae write boundary preserved), no tactical directives. `build_advisory_context` is pure over pre-fetched state with caps (280 chars last_player_action, 20 combatants, 40 inventory rows, 10 pending loot rows); `dnd_orchestration.py` doesn't import `dnd_engine`'s chroma functions — structural defense. Telemetry: `advisory_respond: campaign={N} guild={N} chars={N} truncated={0\|1} provider={...} state_combat={0\|1} state_inventory_count={N} state_combatants={N} bound_char={0\|1}`. `advisory_respond_failed:` only on router failure. 20 assertions in `test_advisory.py`. **Live verified S25 09:17–09:20** across 7 advisory requests in two campaigns; load-bearing test was the goblin-attack response — model had `GO1` in snapshot, knew initiative order, described `!attack <weapon> -t GO1` and `!check perception` as **player options** without emitting them. | ✅ SHIPPED LIVE |
| Track 6 #3.1 — Advisory Command Reference v1 (S25 #2) | New `COMMANDS.md` at `/home/jordaneal/virgil-docs/` (~8.4KB canonical Virgil + Avrae command reference). Loaded fresh into advisory mode on every request via `_load_commands_reference()` in `dnd_orchestration.py`. **No caching** — Avrae-section edits take effect with no restart. New `COMMANDS_DOC_PATH` (env-overridable), `_load_commands_reference()` graceful-degrade reader, new `commands_reference` kwarg on `build_advisory_context(...)`. `ADVISORY_SYSTEM_PROMPT` extended with "use AVAILABLE COMMANDS as source of truth / say 'not available' rather than guess". `advisory_respond:` extended with `commands_ref_loaded={0\|1} commands_ref_chars={N}`. 11 new tests in `test_advisory.py` (now 31 total); new `test_commands_doc.py` (8 sanity tests). | ✅ SHIPPED LIVE |
| Track 6 #3.2 — Auto-Generated Virgil Section (S25 #2) | New module `commands_doc_generator.py` — `_strip_category_tag` / `_categorize` / `introspect_virgil_commands(bot)` / `render_virgil_section(rows)` / `update_commands_doc(bot, path)`. Idempotent atomic write between `<!-- VIRGIL_AUTO_GENERATED:* -->` markers in `COMMANDS.md`; everything outside the markers preserved byte-for-byte. Wired into `on_ready` after `bot.tree.sync()`. Re-tagged `/setup` as `[SETUP]` and three list subcommands (`clock`/`quest`/`companion list`) as `[PLAYER]` so source-of-truth tagging matches intended categories — pattern locked: tag is the source of truth, generator just renders. New `commands_doc_update: count={N} changed={0\|1} markers_found={0\|1} error={msg\|none}` per-startup log. 33 unit tests in `test_commands_doc_generator.py` covering tag stripping, categorization precedence, group walking, parameter signatures, alphabetical ordering, idempotency, marker preservation, missing-file/markers graceful degrade, atomic-write resilience. **Live verified S25 #2** with all five test cases (probe injection lifecycle, doc count delta on retag, Avrae section byte-preservation across restarts, `commands_ref_loaded=1` post-restart). | ✅ SHIPPED LIVE |
| Track 7 #1 — Adjudication Layer v1 (S25 #4) | New `adjudicator.py` module. Single entry point: `adjudicate(player_input, scene_state, character, combatants, active_turn, intent) → AdjudicationResult`. Pure function. Composes BEFORE every directive in `build_dm_context`. Five locked action categories: `FREE_ACTION` (pure RP, no stakes); `CHECK_ACTION` (outcome uncertain — resolver picks skill + DC band easy/medium/hard, consumes `RollBuffer` event when present, narration constrained to success/failure shape); `CAPABILITY_ACTION` (class/level/spell/feature gates — refusal is binding, no "says who" override); `COMBAT_ACTION` (requires `mode='combat'` AND populated init order; refuses with explicit prompt to use `!init begin` if combat inactive); `WORLD_BOUNDARY_ACTION` (reality-violating actions — hard refusal, no negotiation, no fabrication of justification). `AdjudicationResult` dataclass: `category`, `allowed: bool`, `refusal_kind: Optional[str]`, `roll_required: bool`, `skill: Optional[str]`, `dc_band: Optional[str]`, `roll_consumed: bool`, `narration_constraint: str`, `signals: dict`. Deterministic intent classifier (regex + keyword vocabulary, Appendix A in spec) — five surfaces: world-boundary patterns, combat verbs, capability claims, check verbs, default fallback. Crude beats clever — LLM-based classification rejected. **Narration constraints rendered top-of-prompt** (`=== ADJUDICATION ===` block) AND bottom-of-prompt (last cache before generation) — belt + suspenders per Doctrine §2 + §48. **§11.K activated:** capability adjudication produces INVALID verdicts that flow into S9's existing render branch (previously dead code). **§11.L deduplication:** when adjudication produces a binding constraint, redundant advisory directives suppress their independent narration. New per-turn `adjudication: campaign={N} actor='{name}' category={...} allowed={0\|1} refusal_kind={...} skill={...} dc_band={...} roll_consumed={0\|1}` telemetry. Spec lock at `/home/jordaneal/virgil-docs/specs/ADJUDICATION_LAYER_SPEC.md` with twelve §11 decisions resolved, Appendix A vocabulary scope, Appendix B implementation notes. **Live verified S25 #4** — 4/7 categories binding live (world_boundary, combat-inactive, check, free); 3/7 capability tests deferred to existing HARD STOP RULES due to pre-existing `cache_warm` not loading second bound PC. Architecture proven sound; cache fix shipped as #1.1. | ✅ SHIPPED LIVE |
| Track 7 #1.1 — Cache Auto-Populate (S25 #5) | `cache_autopopulate` triggers on `!sheet` post in Avrae handler — when an Avrae `!sheet` embed is detected for a bound PC, the cache write fires immediately. No restart, no `/refresh`, no operator hop required. New `cache_warm_incomplete` diagnostic at startup if any bound PC's most-recent `!sheet` post is older than 300 messages (telemetry only — doesn't block startup). Adjudication's `_gate_capability` no longer returns `no_character_context` deferral as the dominant path. **Live verified S25 #5** — same three prompts as Track 7 #1 capability tests (Fireball, Sneak Attack, Rage) post-fix all logged `actor='Jordonovan Bigsby' category=capability allowed=0 refusal_kind=capability`; pre-fix all three had `actor='?' allowed=1`. **Effective category coverage now 7/7 binding.** Track 7 #1's architecture proven: 4/7 → 7/7 jump from one startup-time fix demonstrates the layer was deaf, not broken. | ✅ SHIPPED LIVE |
| Track 7 #2 — Multi-actor Arbitration + Narration Verification (S25 #7) | `arbitrate(actions, ...) → ArbitrationResult` in `adjudicator.py`. All-pairs conflict detection (§11.R); text-aware contradiction detection (FREE overrides binding only on explicit opposing assertion); per-actor sibling deduplication (§11.O); cache-miss fallback (§11.P). `ArbitrationResult` dataclass: `verdicts: list[AdjudicationResult]`, `actor_order: list[str]` (character names, §11.Q), `merge_plan: 'sequence'\|'override'`, `primary_actor`, `combined_constraint`, `overridden_actors: list[str]`, `signals`. New `narration_verifier.py` — parallel sibling per Doctrine §63. `verify_narration(...) → VerificationResult`. Four violation classes: `FABRICATED_COMBATANT` (closes F-49), `VERDICT_CONTRADICTION`, `STATE_MUTATION_CLAIM`, `ACTOR_OMISSION` (closes F-48). 1-retry; second failure → escalation placeholder. Feature flags: `ARBITRATION_ENABLED`, `VERIFICATION_ENABLED`. Always-fire log lines: `arbitration:` and `verification:`. `build_dm_context` kwarg `adjudication_block` → `arbitration_block` (§11.N). New tests: `test_arbitration.py` (21), `test_narration_verifier.py` (40), `test_dm_respond_arbitration.py` (9). **Closes F-48, F-49, F-50.** | ✅ SHIPPED LIVE |
| Bug 3 — `/travel` durability + NPC list location-scoping (S25 #6) | **`/travel` durability**: `discord_dnd_bot.py:travel` now calls `location_upsert(campaign_id, destination)` when dest doesn't pre-exist, then `set_current_location(campaign_id, dest_loc['id'])` unconditionally. Previously `set_current_location` only fired on `dest_resolved=True`; unknown destinations updated only the embed footer (one-shot `label_override`) while `current_location_id` reverted to the prior location on the next `build_dm_context` read. New telemetry shape: `travel: campaign={N} from='{src}' to='{dest}' resolved={0\|1} created={0\|1}`. **`get_recently_active_npcs(..., location_id=None)`**: new optional kwarg. Strict filter — only NPCs with matching `location_id`. NULL `location_id` is silent (parser leaves NULL by default; "include NULL" rule grew the always-present set with every fabricated NPC — caught live). Default behavior preserved when `location_id=None`. **`build_dm_context` reads scene_state.current_location_id** and passes it. Scopes the "Recently active NPCs" prompt block to current location. New telemetry: `npcs_in_context: campaign={N} count={K} location_filtered={0\|1}`. **`get_scene_state` regression caught and fixed mid-ship**: function had never SELECTed `current_location_id` from `dnd_scene_state`, so its returned dict had no such key. New filter quietly degraded to None-passthrough (`location_filtered=0` everywhere despite the DB pointer being correctly set). Same dict feeds the consequence directive (line 4779), commitment directive (line 4831), and init directive (line 4856) — all three already had `current_loc = scene_state.get('current_location_id')` guards followed by `at_location` enrichment that had been silently dormant since the column was added. Bug 3 fix incidentally re-activates them. New `test_travel_persistence.py` (25 assertions); `test_dnd_npcs.py` extended (10 new strict-filter cases). **Live verified S25 #6 09:07–09:08**. **Filed v1.x**: chroma bleed (F-44) — past Stumbling Stag turns can still surface as RELEVANT PAST EVENTS even after travel; Bug 3 closed the prompt-block channel, chroma is the remaining channel. | ✅ SHIPPED LIVE |
| Discord channel cleanup + canonical `/setup` (S23 #3) | Consolidated 7-channel pre-S23 layout (`dm-narration`, `dice-rolls`, `character-sheets`, `party-loot`, `lore-notes`, `ooc-general`, `bot-commands`) into 4 canonical text channels (`dm-narration`, `dm-aside`, `lore-notes`, `party-chat`) + 1 voice (`General`) across 3 categories (`🎲 VIRGIL DM`, `💬 OUT OF CHARACTER`, `🔊 VOICE`). Drops: rolls (Avrae rolls land in `#dm-narration`; listener filters by author not channel — works for free), sheets (DDB owns sheets), loot (loot narrated in `#dm-narration`), commands (slash commands work anywhere). Renames `ooc-general` → `party-chat` (canonical name in code; operator renames in Discord manually). Adds `dm-aside` for Track 6 #3 advisory mode (channel reserved with full bot perms, routing not yet wired — existing line-594 routing gate already silently ignores non-narration text channels). New `compute_setup_plan(text_channels, voice_channels, categories, ...)` in `discord_dnd_bot.py` — fifth pure-function-planner instance (after the four narrative-directive siblings); pattern now codified across narrative directives AND infrastructure ops. Returns plan dict with `categories_to_create`, `text_channels_to_create`, `voice_channels_to_create`, `text_channels_to_move`, `voice_channels_to_move`, `text_channels_existing`, `voice_channels_existing`, `categories_existing`, `legacy_category_to_delete`. `/setup` rewritten: builds guild snapshot (existing categories, text channels by name → category, voice channels by name → category), calls planner, executes via discord API (create categories first, create channels in canonical categories, move existing canonical channels to canonical categories, repair bot perms, delete empty legacy `🎲 D&D` category if no channels remain in it post-move). `#lore-notes` permissions: @everyone has `view_channel + read_message_history` but `send_messages=False` (DM/admins write via Discord's manage-channels override; bot keeps full perms). Idempotency contract: re-running on a fully-canonical guild produces a plan with all empty action-lists and full existing-lists; user-facing ephemeral renders "Nothing to do — already canonical. Bot perms repaired." Soft-fail throughout — exceptions in any channel/category op are logged but don't abort the rest of the plan execution. New per-execution `setup_run: guild={N} channels_created={N} channels_moved={N} channels_existing={N} categories_created={N} categories_existing={N} legacy_deleted={0\|1}` log line. `SCAN_CHANNELS` constant for bootstrap-warm reduced from `('sheets', 'narration')` to `('narration',)` since sheets are no longer canonical (legacy `#character-sheets` if present is harmless — `get_channel` soft-fails). Channel topic strings updated for consolidated structure. 26 assertions in `test_setup_plan.py` covering: constant-shape contracts (CHANNEL_NAMES / CATEGORY_NAMES / CHANNEL_CATEGORY / VOICE_CHANNELS / dropped-keys); empty guild creates everything; already-canonical no-op; mixed state (some canonical, some legacy) creates missing only and moves existing; legacy category deletion logic (deleted when emptied / preserved when non-canonical channels remain text or voice / handled when absent); top-level channel placement; voice channel move/create/existing; idempotency; determinism + no-input-mutation; telemetry helper edge cases. All 35 prior test files green (assertion counts unchanged). **Live verified S23 23:12 + idempotency check 23:14**: first run created 3 categories + 2 text channels (`dm-aside`, `party-chat`) + moved 3 (dm-narration, lore-notes, voice General) + auto-deleted empty `🎲 D&D` legacy category in one operation; idempotency re-run logged `channels_created=0 channels_moved=0 channels_existing=5 categories_created=0 categories_existing=3 legacy_deleted=0` with "Nothing to do — already canonical" ephemeral. Operator manually deleted orphaned legacy channels (`#dice-rolls`, etc.) post-`/setup` per spec — destructive moves are operator decision, not bot. | ✅ SHIPPED LIVE |
| Track 6 — Combat Redirect Directive v1 (S23 #2) | New `compute_combat_redirect_directive(scene_state, active_turn, combatants, bound_character_name) → (body, signals)` in `dnd_orchestration.py` — fourth pure-function-in-orchestration sibling (after `compute_persistence_directive`, `compute_loot_directive`, `render_state_footer`). Adds informational redirect pressure when player on-turn narration in active combat may attempt to bypass combat reality (escape, ignore threats, treat combat as resolved). Companion to S19's `compute_commitment_directive` (escape-intent transitions only); broader scope here — fires on every PC on-turn narration in combat with at least one alive enemy, regardless of intent classification. Master gate (all must hold): `scene_state.mode == 'combat'` AND ≥1 alive non-PC combatant AND active turn matches `bound_character_name` (case-insensitive; or `bound_character_name=None` default-fires since 2A.3 has already dropped any off-turn input). Body composition: prologue ("Combat is ACTIVE. The player's narration may attempt to bypass... Do NOT honor exit narration as resolution"), `Active threats:` bullet list with HP / "HP unknown" / conditions per alive enemy, redirect guidance ("redirect their narration toward the active threat... Frame the redirect as the world reacting... Do NOT refuse the player's input as invalid... Do NOT say 'you cannot do that'... Inform the player about the world state through narration of the threat's response. The player can end combat with !init end if combat should be over"). Architecturally explanatory by design — hard refusal lives in 2A.3 (off-turn drop with ⏳ reaction); this is the complementary on-turn pressure. Renders `=== COMBAT REDIRECT ===` block AFTER `=== LOOT TO SURFACE ===` (matches tactical-band ordering: persistence → loot → redirect). Soft-fail wrapped in `dm_respond` with `[REDIRECT_FAILED]` traceback log on exception — directive failure NEVER blocks narration posting. New per-turn `combat_redirect: campaign={N} fired={0\|1} alive_enemies={N} reason={fired\|gate_mode\|gate_no_enemies\|gate_npc_turn}` telemetry; `directive_emit:` extended with `redirect={0\|1}`; `_directive_chars` in `prompt_size:` extended with `len(redirect_text)`. 38 assertions in `test_combat_redirect_directive.py` covering all 4 reason variants × master-gate paths (scene_state None/missing-mode/exploration/social, no combatants, all-dead, all-PC, NPC turn, PC turn fires, case-insensitive PC match, bound_character_name=None default-fires) + body content (authoritative framing, threat list with HP known/unknown/conditions, dead-enemy omission, PC omission, multi-enemy rendering, redirect guidance, no-tactical-coaching invariants) + signals (threat_summary list, alive_enemies count) + graceful-degrade (missing alive key, invalid alive value, empty name, non-dict combatant in list) + determinism + no-input-mutation + cross-campaign isolation + telemetry helper edge cases. All 35 adjacent test files green (assertion counts unchanged from Track 6 #1 baseline). **Live verified S23 22:35** across 7 paths (4 gate variants + fired path twice — once with thin input where directive landed but LLM had nothing to redirect, once with adversarial PC-turn bypass where LLM emitted exact spec narration: "You spin away from the goblin... The goblin, still within your reach, snarls and readies a swing as you try to slip past. !check stealth" — world-reactive redirect + bonus mechanical anchor surfacing skill check as resolution path). **Two-directive cooperation surfaced**: when a bypass attempt lands on the NPC turn (Avrae auto-advanced past PC turn between LLM responses), persistence directive + NPC-turn narration pressure produces the redirect behavior even without combat_redirect firing — bypass coverage works regardless of which side of init the bypass narration lands on. | ✅ SHIPPED LIVE |
| S21 — OOC contamination guard (S17) | Leading-marker filter on `parse_consequences_player` short-circuits OOC chatter before the LLM call. Player-channel only. `consequence_ooc_filtered` diagnostic. | ✅ SHIPPED LIVE |
| Track 6 #4 — NPC Stat Hydration at Init-Add (S25 #8) | New `npc_hydrator.py` — 16-band CR table, `hydrate_npc_stats()`, `fallback_stats()`, `normalize_cr()` (with fraction/decimal/unicode aliases). `dnd_engine.py`: 8-column schema migration on `dnd_npcs` (hp_max, ac, attack_bonus, damage_dice, save_bonus, init_mod, cr_str, avrae_source); new `stat_incomplete()`, `npc_hydrate_stats()` (source-based fill rule; explicit_hydrate always-overwrites; generic_fallback leaves hp_max NULL), `npc_register_avrae_madd()`; `_hydration_wrote_this_turn` module flag; `directive_emit:` extended with `hydration_write_fired={0\|1}`. `avrae_listener.py`: `status_token` field added to each combatant in `parse_init_list_embed` (`<None>` for !init add, non-None for !init madd). `discord_dnd_bot.py`: `_pending_hydration` set (per-session deduplication); `_post_hydration_prompt()` helper posts CR prompt to `#dm-aside`; `_handle_init_list_event` step 2.5 runs classification scan (bound_pc_skip / avrae_madd / miss / generic_fallback / hook/skeleton); `/hydrate` DM-only slash command (explicit_hydrate, always-overwrite, clears pending entry, ephemeral stat-block response). 80 new assertions across 5 test files: `test_npc_hydrator.py` (24), `test_npc_hydrate_stats.py` (17), `test_npc_register_avrae_madd.py` (7), `test_hydration_hook.py` (20), `test_slash_hydrate.py` (12). **Closes bones queue.** | ✅ SHIPPED LIVE |
| Track 4 — Corpus inventory | CRD3 + FIREBALL reconnaissance complete | ✅ DATA COLLECTED |

See `ROADMAP.md` for next priorities, deferred phases, and small wins.

---

## 9. The biggest long-term threat

Not LLM quality. Not hardware. Not vector DB scaling.

**Orchestration entropy** — every successful feature encourages the next one, every layer increases coupling, and orchestration becomes implicit instead of explicit.

Watch for:
- Giant branching conditionals where there used to be one decision
- Hidden side effects (a function that secretly mutates DB state)
- Duplicated state logic (two functions that decide the same thing slightly differently)
- Prompt logic leaking back into orchestration (the rules engine starting to "know" what tone the LLM should use)
- Orchestration leaking into Discord transport (slash commands that do gameplay work instead of routing it)
- "Temporary" exceptions becoming permanent (any if-block with a TODO that survived more than one session)

The architecture is currently clean enough that you can FEEL the boundaries when a change crosses them. Protect that. When a patch feels like it's reaching across modules, stop and refactor before shipping. The boundaries from Section 4 (Architectural Invariants) are the load-bearing walls — don't drill through them, even temporarily.

The pattern that protects this: **incremental, single-responsibility patches. One step at a time. Live-verify each one. Refuse to batch "while we're here" changes into a step that wasn't designed for them.** Phase 1.4 stayed clean because every step was scoped to one concept. Phase 12 stayed clean because we held that line.
