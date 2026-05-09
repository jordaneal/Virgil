# WHY THINGS ARE THE WAY THEY ARE

Architectural reasoning archive. **Append-only.** When a decision is made that will be hard to remember the reasoning for in 6 months, capture it here.

Organized by topic, not chronology. New entries can land anywhere a topic fits.

---

## Calendar and Virgil personal-assistant side

### Why gog instead of Google Calendar API directly
gog was already set up from the Hostinger era. Google Calendar API requires OAuth token management. gog handles auth via keyring. Pragmatic continuity.

### Why the architecture is deterministic Python for tools (not LLM tool-calling)
Entire first session spent trying to get a 14B model to execute gog commands via OpenClaw's tool-calling system. It consistently hallucinated success. Same with Gemini. OpenClaw dropped entirely. **Hard learned lesson.**

### Why `virgil_bot.py` is a single file
Originally separate `calendar_bot.py`. Merged when OpenClaw was dropped. Simpler, easier to debug, no inter-process communication.

### Why Ollama uses `/api/chat` not `/v1/chat/completions`
Ollama has two endpoints. `/v1/` was causing empty responses. `/api/chat` works reliably. **Do not change this.**

### Why `cloud_router.route()` returns a tuple
Originally returned just text. Updated to return `(text, provider_name)` for `/stats` and usage reporting. ALL callers must unpack.

### Why `route()` does NOT take `max_tokens`
`max_tokens` is plumbed through `call_provider`, not `route`. Adding it to the `route()` signature breaks `dm_respond`. Found the hard way mid-Phase 1.3.

### Why `data_cache` runs at 6:55 not on the hour
Race condition — cache and digest both ran at :00. Digest read empty cache. Cache moved to :55 to guarantee completion before 7 AM digest.

### Why `/patch` is function-scoped not whole-file
Full file (~1900 lines) exceeded free-tier context windows. Function-scoped (50-200 lines) works reliably. Never attempt whole-file rewrites via `/patch`.

### Why both `ssh-virgil` AND `virgil-ssh` aliases exist
Jordan's fingers picked one, Claude's documentation used the other. Both point at the same SSH command. Easier than fighting muscle memory.

---

## D&D — overall architecture decisions

### Why Telegram DnD bot was retired (Session 5)
Friends migrated to Discord. Maintaining two interfaces over one engine doubled the surface area for no real benefit. Discord has dropdowns, modals, slash commands, threading. Telegram couldn't compete on UX for multiplayer D&D.

### Why Avrae instead of building our own rules engine
Avrae has 7+ years of dev, 2M+ users, every 5e edge case handled, D&D Beyond integration, character sheet import. We were building a worse version of all of it AND asking the LLM to do math + state tracking it can't reliably do. CALYPSO research (AAAI 2023, 71 D&D players) confirms LLMs work as co-DMs, not DMs. Friends & Fables (the leading commercial product) reached the same conclusion and rebuilt their engine to separate AI persona from structured campaign engine. We arrived at the right architecture by hitting the same walls they did.

### Why CRD3 import filtered to MATT turns only
All 1140 files would have taken 30+ hours. Player turns don't improve DM behavior. Matt Mercer (DM) turns are the high-value data. 740k documents from MATT turns + FIREBALL filtered utterances is more than sufficient.

### Why `_knowledge_collection` had a missing global declaration
`chroma_init()` declared `global _chroma_client, _chroma_collection` but not `_knowledge_collection`. The assignment created a local that vanished on function exit. `knowledge_search()` returned empty for the entire history of the bot. Fixed Session 5. **Lesson: when adding new module-level state, audit every function that references it for `global`.**

### Why `narrative_tags` instead of full inventory parsing
Inventory parsing is a rabbit hole — torch counts, weight, ammo, consumables. None of it improves narration quality at the level we need. Tags ("darkvision", "lockpicker", "stealth_specialist") are inferred from class + race + skills + attacks, render compactly, and give the DM all the awareness it needs.

### Why `CharacterContext` is in-memory not persistent
Cache is presentation context, not authoritative game state. Avrae is the source of truth. Persisting Virgil's cache would create sync problems (stale tags, out-of-date level after `!beyond` updates) without solving any real problem. Bot restart = fresh cache, `/refresh` forces a rebuild.

### Why scene state is authoritative but lives in SQLite
Survives bot restarts (campaigns can span days). One row per campaign so the lookup is constant time. JSON list fields are easy to dedupe and cap. Not Chroma — scene state is structured, not narrative.

### Why scene update extraction runs in a daemon thread
Two reasons: (1) the extraction LLM call adds latency we don't want blocking the next player turn; (2) scene state is authoritative for the NEXT turn, not the current one. Async update is the correct pattern.

### Why the DM prompt restates roll decisions instead of making them
LLMs are bad at consistent gating. Same input gets different roll decisions on different runs. Moving the decision to a deterministic rules engine made roll discipline immediately consistent. **The prompt becomes "tone, pacing, voice" only — its actual job.**

### Why Avrae roll syntax is `!check sleight of hand` (spaces, no quotes)
Avrae's actual parser. Quoted form ALSO works but isn't required. Tried underscores first (`!check sleight_of_hand`) — works in some cases but not all. Spaces with no quotes is the canonical form.

### Why `/setup` uses `merge_bot_overwrite()`
First version of `/setup` overwrote channel permissions wholesale, wiping Jordan's manual fix to `#bot-commands`. Now `/setup` MERGES — preserves existing explicit allows, only adds the bot's required perms. Safe to re-run forever.

---

## Phase 1.4 — Combat mode FSM (Session 7)

### Why the extraction LLM thread can no longer write mode/tension/active_npcs/active_threats
These four fields are STRUCTURAL — they drive FSM transitions, prompt branching, and rules-engine decisions. Letting a hallucinating background LLM thread author them means every downstream system inherits the drift. `update_scene_state()` now enforces `LOCKED_FIELDS` at the write boundary; the extraction thread can still touch `established_details` and `open_questions` (genuine narrative-extraction work). Both DeepSeek and Gemini independently flagged this as the #1 architectural vulnerability; the fix was ten lines.

### Why `dm_respond` reads `scene_state['mode']` instead of recomputing it
Pre-Session-7, `dm_respond` inferred mode per turn by scanning Avrae events from the last 75 seconds. Combat without damage in that window = exploration. First swing of combat = exploration. Tactics-discussion mid-fight = exploration. Worst of both worlds. Now mode is stored, deterministically written by `set_scene_mode()`, read as authoritative.

### Why Avrae `!init` events are parsed as PLAINTEXT, not embeds
Both review docs assumed Avrae sends initiative events as embeds with titles like "Begins Combat" / "Ends Combat". They don't. We added a temporary `[INIT_CAPTURE]` dump that ran on every Avrae message and discovered every `!init` message is plain text in `message.content`. `parse_init_event()` runs against plaintext via regex before `parse_avrae_embed`'s no-embed-bail. **Rule for the future: never write Avrae parsers from documentation; always capture real samples.**

### Why combat-end requires `on_message_edit`
When the DM types "yes" to confirm `!init end`, Avrae EDITS the existing "Are you sure?" message in place to "End of combat report:". No new message is sent. discord.py's `on_message` does not fire on edits. **Architectural takeaway: Avrae's messages are not events, they are state. Treat Avrae as dual-channel — message + mutation.** This pattern repeats for any future Avrae integration.

### Why we deferred the L4D AI Director tension model
Gemini's research proposed a sinusoidal Build/Peak/Relax curve with a scaled trigger table. DeepSeek correctly punctured it: social tension has no triggers (every entry requires `severity == 'dire'` which is combat-only), healing has no spec, "miss" detection requires AC we don't get from Avrae embeds, and damage attribution to PC vs monster is unreliable from current parser output. The pragmatic version is DeepSeek's "danger thermometer" — damage events +N, nat-1 +10, short rest -40, long rest 0, per-turn decay -3. Coarse Calm/Mounting/Dangerous/Climax label at prompt-render time so the LLM doesn't over-index on a 54→56 shift.

### Why progress clocks are MANUAL-create-only
Gemini's research describes elegant auto-spawning patterns. They're correct in principle but blocked: we have no encounter designer that knows when to spawn one. DM types `/clock create "Alarm Level" 6`, orchestrator advances clocks deterministically based on roll outcomes. After the manual pattern proves itself in real play, we add auto-spawn rules for cases that recur.

### Why we're NOT building vector-tone metadata filtering
Gemini's research proposes tagging all 740k CRD3 + FIREBALL docs with `setting_type` / `tone_profile`. Cost: re-classify 740k documents, likely with another LLM pass, with reliability problems. Benefit: solves tone bleed, which we already have a kill switch for (`USE_KNOWLEDGE_GUIDANCE`). The kill switch is binary and works today.

### Why mode-aware classifier reordering instead of new intent regexes
When "I steal a glance" was misfiring as INTENT_RISKY in social mode, the cleaner fix was twofold: reorder evaluation by mode + add negative lookaheads to RISKY_RX itself for "steal a glance/look/peek/glimpse" and "sneak a look/peek/glance/glimpse". **Lesson: when a regex misfires, ask whether the pattern is wrong or whether the evaluation order is wrong. Often it's both.**

### Why `/clock` has autocomplete on the name parameter
Initial `/clock` commands required typing the clock name verbatim, which Jordan correctly flagged as bad UX during gameplay. Discord's `app_commands.autocomplete` decorator solves this in ~20 lines. The pattern is reusable for any future slash command that references a named DB entity. (Reused in Ship 2 for `/companion add` pulling from `dnd_npcs`.)

### Why DB_PATH points at `/mnt/virgil_storage/virgil.db`, not the scripts dir
Easy mistake: when running `PRAGMA table_info` or any sqlite3 query manually, point at `/mnt/virgil_storage/virgil.db`, NOT `/home/jordaneal/scripts/virgil.db`. The latter doesn't exist; it's where you'd LOOK if you assumed local-relative paths. `dnd_engine.py` hardcodes the absolute path because the database lives on persistent storage, not in the codebase.

### Why `_now()` and `import json` must be present in `dnd_engine.py`
`set_clocks()`, `update_tension()`, `npc_upsert()`, `location_upsert()` all call `_now()` for timestamps and `json.dumps()` for serializing list fields. They're file-level dependencies. When adding new functions, always grep for the helpers they use FIRST: `grep -n "^def _now\|^import json" /path/to/file`.

### Why no `combat_session_id`
External advice (ChatGPT) suggested adding a `session_id` field that binds init events to a specific combat run, defending against cross-combat contamination. We don't need it. One campaign per guild, one combat at a time, and `scene_state.mode == 'combat'` already serves as the session marker. `_handle_init_event` guards on current_mode before flipping. Adding session_id would solve a problem we don't have.

### Why `/mode` exists as a manual override
Avrae only owns combat-vs-not. Social, travel, and downtime have no Avrae trigger. `/mode` covers those modes today and acts as a safety valve if Avrae's tracker desyncs. **Manual override is a non-negotiable fallback, not a workaround.**

### Why `pull-dnd` is the right pre-session command
Covers all four DnD-related files in one shortcut: `dnd_engine.py`, `avrae_listener.py`, `discord_dnd_bot.py`, `dnd_orchestration.py`. Running it before starting a Claude session ensures project files match the live server. Without it, Claude patches against stale code.

### Why `push-X` commands and server commands MUST NOT be chained
`push-X` aliases run from MINGW64 (Windows local), executing scp. systemctl/journalctl run from SSH (server). Different machines. Never write `push-X && systemctl ...`. Workflow: (1) MINGW64 push, (2) switch to SSH, (3) restart, (4) verify.

---

## Phase 2 — Combat stabilization, observability, narrative fidelity (Session 8)

### Why multiplayer is first-class, not deferred
Original plan had multiplayer as "deferred until solo play is solid." Jordan clarified: solo and multiplayer are equally important, and multiplayer may be more important. Features built solo-only and retrofitted for multiplayer tend to break. Features built with both in mind from the start tend to work. Phase 2A (combat stabilization) is the concrete consequence: it's not a nice-to-have, it's a prerequisite for inviting friends.

### Why combat coordination state lives in a separate table
ChatGPT's analysis identified a subtle but important boundary: initiative runtime state (whose turn, who's the active controller) is combat coordination state, not narrative scene state. `dnd_scene_state` is narratively scoped — it tracks what the world looks like, not who's allowed to talk. Adding `active_turn_controller` to `dnd_scene_state` would violate the architectural invariant that scene state is narratively scoped and corrupt the LOCKED_FIELDS separation. Solution: dedicated `dnd_combat_state` table that owns coordination state cleanly, gets cleared when combat ends.

### Why exploration batching does NOT apply during combat
The 15-second cooperative batching window exists because in exploration mode, multiple players acting simultaneously produces better narration. In combat, pacing is highly sensitive to latency. Avrae has already decided whose turn it is. Batching non-active combatants into the same response window produces narration that contradicts Avrae's authoritative initiative order. Immediate (1-2s debounce max) response in combat mode; cooperative batching in exploration/social.

### Why consume diagnostics come before Phase 2C (2B before 2C)
Multi-actor context (2C) depends on actor matching working correctly. Actor matching is currently silent — failures produce no log output. If we ship 2C before 2B, we'll ship multi-actor context support and have no way to tell whether it's actually resolving actors correctly. **Diagnostics first, features second.**

### Why companion fields collapsed to a single persona
First draft of `dnd_companions` had three text columns: archetype, voice, perspective. Splitting felt structured — each field had a clear role. Pushback from review (correct): three fields invites the DM to think about the schema rather than the character. "Cautious scholar who speaks in measured sentences and pushes for careful planning" is one thought, not three. Schema discipline loses; UX wins. **Same lesson as clock autocomplete in Session 7 — the one that makes the system actually usable, not the one that satisfies the type system.**

### Why `/encounter` is one command not a subgroup
Subcommand groups (`/encounter stealth`, `/encounter social`, `/encounter trap`) would have given each preset its own argparse path and three handlers. Single command with a Choice parameter compresses this to one handler reading from one ENCOUNTER_PRESETS dict. **Architectural framing: orchestration commands declare INTENT ("start a stealth encounter"), they don't navigate a subsystem.**

### Why `/encounter` is strictly idempotent
First draft of `/encounter` would have set mode unconditionally, called `clock_create` unconditionally (catching duplicate errors), and bumped tension every time. Pushback (correct): re-running `/encounter stealth` twice should not double-bump tension or spam errors. Final rule: ensure mode (set only if different), create missing clocks (never mutate existing), shift tension only if mode changed OR at least one clock was created. Pure no-op re-runs are silent.

### Why the cloud router quotas were miscalibrated
Daily limits in PROVIDERS were set when the project started and never re-checked. Cerebras was the worst case: capped at 1700 requests/day, but Cerebras enforces 1M tokens/day, not requests. At ~3500 tokens per call, 1M tokens ≈ 285 requests, not 1700. **Lesson: provider limits drift — don't trust the constant from the day you wrote it. Re-verify quarterly.**

---

## Phase 3 — Suggestion + auto-execute (Sessions 9-10)

### Why Phase 3 is a suggestion layer, not auto-extraction
After 2C.4 shipped, the obvious move would be Phase 3 = inventory tracking or better memory tiering (the old roadmap). Real-world feedback overrode that. Session 8 ended with Jordan pointing out that he doesn't want to type slash commands during play.

First reframe: Phase 3 = auto-extraction with a proposal queue and per-feature extraction threads. That plan was sketched and discarded within the same session as premature abstraction. It was building the back half of a problem we hadn't validated.

The actual friction is not "I have to type slash commands." It is "I don't know what the system thinks should happen next." Auto-execution solves the first; suggestions solve the second. The second is what's real.

The deeper lesson — there are three layers of cognition in this system, and Phase 2 only built two of them:
- Layer 1: Reality (Avrae + scene state + clocks)
- Layer 2: Interpretation (dm_respond narrating that reality)
- Layer 3: Meta-awareness (what the system thinks matters next)

Phase 3 is Layer 3. It's not a feature; it's a cognitive overlay on the DM.

### The system evolves from observed friction, not anticipated friction
This is a governance rule, not a feature decision. When real friction surfaces, the response is: ship the smallest possible change that makes the friction observable, watch usage, let real data drive what comes next. NOT: design the full infrastructure that would solve every variant of the friction.

The Phase 3 proposal queue (`dnd_proposals` table, lifecycle states, accept/reject persistence, multi-thread extraction writers) was specifically rejected even though it was internally consistent and would have worked. It would have built authority infrastructure before validating that authority delegation was the right answer.

---

## Session 10 — model swap and routing

### Why DnD uses gpt-oss-120b instead of llama-3.3-70b
Phase 1 attempted to fix narration drift with HARD STOP rules and sampling penalties. Both shipped, both confirmed firing in diagnostics, both visibly ineffective on Llama. Test sequence: "I flip the car over with ease" / "I dig under the building easily" / "I fly into the air" — Llama narrated all of them as fact despite rules 1-6. Same prompt on gpt-oss-120b refused meteor swarm, refused king's throne (scene contradiction), refused oak-table-through-wall, demanded a roll on "behead the clerk with ease" (and narrated failure on roll=3). **Model class is the ceiling on negative-instruction following.** Penalties at 0.5/0.4 are meaningful on GPT-class models, largely ignored by Llama.

### Why DnD uses scoped priority override instead of skipping sort entirely
First DnD-routing patch put `groq_heavy` at the head of the candidate list and trusted `route()` to honor the order. It didn't — `sort_by_score` reorders by recorded latency, and `groq_heavy` with no latency data defaults to 3.00 (high), so groq's 0.9 latency won and the override silently failed. Fix: for `task_type=='dnd'`, skip score-sort entirely AND log `routing=DND_PRIORITY_OVERRIDE` so the decision is auditable. ChatGPT review pushed back on "skip sort entirely" as introducing non-determinism via list-order trust; counterargument is that the candidate list IS the priority list at this scope. The reason-code logging insight was correct and adopted.

### Why corpus retrieval is genre-locked
CRD3 + FIREBALL are 100% fantasy. Cyberpunk campaigns query the embedding index and get 3 short exemplars at ~125 chars each, often semantically marginal. Fantasy campaigns get 5 exemplars at ~300 chars each, tonally aligned. Considered tagging the corpus with `setting_type` metadata — still deferred. `USE_KNOWLEDGE_GUIDANCE = True` is the right default; per-campaign override possible if needed.

### Why `is_dm_or_creator` instead of just `manage_guild`
In a multiplayer Discord guild, `manage_guild` correctly identifies the human DM running the table. In solo play with Virgil-as-DM, Jordan IS the player AND has manage_guild AND is the campaign creator — but the gates labeled [DM] forced him to mentally hat-switch every time he wanted to run `/encounter` or `/quest add` mid-roleplay. Adding `created_by_user_id` to `dnd_campaigns` and letting the campaign creator pass the gate solves the solo friction without weakening multiplayer security: in multiplayer, the DM creates the campaign and IS the creator, so behavior is unchanged. The relaxed gate only matters when the creator is a non-DM player — solo case. Defense-in-depth preserved by `/setup` keeping its `manage_channels` gate (channels are guild-level, not campaign-level).

### Why mechanical hints are an advisory parser, not engine writes
Tempting design: "let Virgil send Avrae commands when narration implies them." Rejected. The moment a parser auto-fires, hallucinations become state corruption — wrong currency denomination, phantom items, miscounted HP. Avrae is the source of truth for mechanical state; no other system writes to it. **Mechanical hints surface SUGGESTIONS for the player to verify and type. Suggestion-only is the architectural invariant, not a guideline.**

### The advisory parser pattern (named in Session 10)
Recurring architectural shape now appearing in five places:
1. `extract_scene_updates()` — narrative LLM thread proposes scene_state updates, bounded to LOCKED_FIELDS-respecting writes.
2. Phase 3 auto-execute — model emits AUTO_EXECUTE tail, parser validates against Tier 1 allowlist, executes through existing primitives.
3. Phase 11 mechanical hints — model parses generated narration, emits Avrae command suggestions, validator drops anything outside the whitelist.
4. Phase 12A NPC extractor — narration → strict regex/stoplist validation → `npc_upsert`.
5. Phase 12B location extractor — same shape for places.

Common pattern: bounded text input → small LLM call → strict structured output → deterministic validator → whitelist-restricted side effect. **The LLM proposes; the validator disposes.**

---

## Phase 12 — canonical world state (Session 12)

### Why "strict literal match + telemetry + future merge tool" beats "fuzzy matching"
Phase 12 deliberately chose strict matching with `npc_health` fragmentation reporting. Fuzzy collapse risks false-positive identity merges — if "Mira" and "Miranda" become the same row, real campaign canon corrupts. Cost of strict: occasional duplicate rows for short-form re-mentions ("Eldrin" vs "Eldrin Stormbow"). Benefit: no silently-wrong merges. The fragmentation telemetry measures whether drift is bounded (it is, ~50% on campaign 17 with no growth pattern) or exponential (would justify merge tooling).

### Why identity normalization is canonicalization, not fuzzy matching
`canonicalize_name()` and `canonicalize_location_name()` strip whitespace, normalize curly quotes, and remove leading honorifics/articles deterministically. "The Rusty Anchor" and "Rusty Anchor" should collapse to one row — same place, definite article is grammatical noise. "Mira" and "Miranda" should NOT — different identity, prefix overlap is coincidence. The line is whole-token boundary: the article/honorific must be a separate whitespace-separated token, never consume the last token. "Theramore" / "Lordran" / "Anvilrest" stay intact.

### Why the architecture absorbs probabilistic parser variance
When the parser emits the same NPC with two role guesses (innkeeper vs bartender), the engine's parser×parser conflict branch keeps the existing value and logs the conflict. **That's healthy system behavior — variability happens upstream, doesn't propagate downstream.** The deterministic engine semantics are how we tolerate noisy LLM output without polluting canonical state.

### Why `set_current_location` validates FK existence
The engine defends its own invariants. `set_current_location(campaign_id, location_id)` checks that `location_id` exists in `dnd_locations` for the given campaign before writing. Callers (`/travel`, future scene-transition detector, skeleton loader) trust the engine to refuse bad writes. Cost: one extra SELECT per transition. Benefit: no orphan FK state ever.

### Why footer overrides are UI-only and database stays authoritative
Ship 1's transition-turn override for unresolved destinations: when `/travel Hollowmoor` is called and Hollowmoor isn't in `dnd_locations` yet, `current_location_id` does NOT get auto-written. Instead, the embed footer for that one transition turn shows the intended destination via `location_label_override`. Subsequent narration mentions Hollowmoor → parser writes the row → next turn's footer reflects DB truth. **Where DB truth and UI truth diverge, the override is local and short-lived, never propagates to schema.** Don't pollute the data model to fix a UX gap.

### Why authored canon (skeleton.md) gets prepended to the system prompt every turn
The DM LLM has no memory of previous turns beyond what we put in context. Skeleton entities (Eldrin Stormbow, his motivations, his voice) need to be in the prompt or the LLM fabricates around them. mtime-cached so per-turn cost is sub-millisecond on the happy path. The `═══` framing is intentional — explicit "AUTHORITATIVE CANON" framing cues the LLM to honor names verbatim.

### Why skeleton load is idempotent and re-runnable
Authored canon evolves. You add a new NPC to `skeleton.md`, save, re-run `/skeleton load` → new rows written, existing rows refreshed against the file, parser-detected duplicates left untouched. Idempotence + the skeleton authority lock means re-running can't corrupt anything. Two-pass load (locations first, then NPC location_id resolution against the same-batch rows) handles forward references in the file.

### Why the transition_context primitive is generic, not `/travel`-specific
`transition_context` is a `dm_respond` parameter, not a `/travel` parameter. Future commands — `/rest`, `/camp`, `/downtime`, `/fastforward` — will all build their own transition blocks and reuse the same plumbing. Engine prepends with `═══` framing as a one-shot directive (NOT persisted, NOT retrieved next turn). The durable consequences (e.g. `current_location_id` change for `/travel`, mode change for `/camp`) are written by the issuing command BEFORE `dm_respond` is called. **Transition is a wire format; durable state is database.**

### Why companion-add autocomplete is a quiet typo-canonicalization layer
Pre-Ship-2, you'd type "Eldrin Stormbrew" into `/companion add` (typo), and the parser would meanwhile correctly write "Eldrin Stormbow" to `dnd_npcs` from narration. Two systems, two spellings, no reconciliation. With autocomplete pulling from `dnd_npcs`, you pick "Eldrin Stormbow" from the dropdown — spelling carries across, drift class disappears. **The autocomplete isn't just convenience; it's a named-canon-bridge between two write paths.**

### Why phantom locations are tolerated, not deleted
Row 5 in campaign 17 is "Stormbridge" — the LLM's typo of "Stonebridge", written by the parser when it appeared in narration. We could delete it. We don't. Two reasons: (1) the parser was doing its job correctly given what was in the narration; (2) phantom rows are the dataset that informs Ship 4 phantom-detection telemetry. Real geography (River Wynd) and phantom geography (Stormbridge) currently look identical structurally — `skeleton_origin=0, mention_count=1`. Telemetry will tell us how to distinguish them empirically. Deleting Stormbridge by hand would destroy the example.

---

## Working with Claude — meta-lessons

### Why design preferences are constraints not suggestions
Late in Session 10, Claude set `USE_KNOWLEDGE_GUIDANCE = False` based on diagnostic data showing the corpus was contributing little to narration quality. Jordan stated separately that corpus integration was a load-bearing design choice. Reverted same session. **When the user has stated a preference about how something should work, that's not a technical decision Claude makes alone. Document the trade-off, surface it, wait for the call.**

### Why drift discipline matters
Multiple times in Session 10, sequential failures looked urgent, leading Claude to invent rules 5 and 6 and pivot to a model swap before completing the planned 1G step. Some interventions were genuinely valuable (rule 6 caught real outcome dictation); others would have been better deferred. **When in doubt: finish the current planned step, observe, decide.**

### Why "I don't know, let's check" beats confident hallucination
Session 12 footer-bug diagnostic detour: Claude reasoned over a stale `current_location_id=2` SQL output for several turns before realizing the value had been changing under subsequent travel commands. Cost: minutes of misdirected analysis. The right move would have been to ask for fresh data after each travel rather than building reasoning on top of a frozen snapshot. **Always ask for current data before prescribing.**

### Why exhaust available retrieval before requesting upload
Session 9: Claude looked at `/mnt/project/`, didn't see a file listed, and asked Jordan to upload it. The file WAS in project knowledge — searchable via project_knowledge_search, just not listed as a filesystem path. Wasted a turn, broke trust briefly. **A file not appearing in `ls /mnt/project/` does not mean it isn't in project knowledge. Always run project_knowledge_search before declaring a file unavailable.**

### Why one problem at a time matters
Phase 12 stayed clean across 12A.1 through 12C.3 because each step was scoped to one concept and live-verified before the next started. Session 12 layered Ships 1 and 2 on top via the same discipline. Phase 1.4 and Phase 2 stayed clean through the same pattern. **The architecture's load-bearing walls survive only if patches are incremental and single-responsibility. Refuse to batch "while we're here" changes.**

---

## Documentation system (Session 12)

### Why the master got split into four files
Single 146KB master became unmaintainable. Claude couldn't reliably write a complete fresh copy in one shot. Jordan couldn't easily navigate it for the parts he needed. Each session adds more.

Split by purpose, not chronology:
- `WORKING_WITH_CLAUDE.md` — preferences and procedures. Small, rarely changes, paste this first into new chats.
- `VIRGIL_MASTER.md` — current system state and architecture. Grows slowly, kept tight.
- `ROADMAP.md` — living document, mutates every session that ships.
- `WHY.md` — append-only architectural reasoning archive.
- `sessions/SESSION_NN_*.md` — historical session lessons, never changed after the next session.

New chats: paste WORKING_WITH_CLAUDE first, MASTER second, ROADMAP third. ~50KB total instead of 146KB. Claude inherits everything that matters for the active work without paying the cost of re-loading every historical session.

### Why session files aren't migrated yet
Old master Sections 9-14 contain Session 5-10 lessons. They're already written. Migrating them to `sessions/` directory is a nice-to-have, not blocking. New session lessons (11, 12+) get their own files going forward. Cleanup of legacy session content can happen anytime without affecting active work.


---

## Ship 4 — phantom telemetry + world_health (Session 13)

### Why the turn proxy counts distinct other locations, not raw last_mentioned bumps
Phase 12 surfaced two structurally identical rows on campaign 17: Stormbridge (typo phantom) and River Wynd (emergent geography that earned its place). Both `skeleton_origin=0, mention_count=1`. The only thing that distinguishes them empirically is time-without-re-mention.

Schema has wall-clock TEXT timestamps (`first_mentioned`, `last_mentioned`) but no per-campaign turn counter. Three turn-proxy options were considered:

1. **Wall-clock seconds elapsed since `first_mentioned`.** Couples to session pacing — long pauses false-flag, fast bursts miss. Rejected.
2. **A new per-campaign turn counter on `dnd_scene_state`.** Cleanest semantically but requires schema migration + plumbing into the response path. Cost too high for value.
3. **Count of OTHER campaign locations with `last_mentioned > candidate.first_mentioned`.** No schema change. Defensible semantics: "the world has moved on" measured as breadth of other geography touched since the candidate appeared. Shipped.

Jordan's design refinement: **count distinct other locations, not chattiness on existing places.** A heavily re-parsed town is still ONE row in `dnd_locations` (last_mentioned is updated in place on re-mention), so SQL `COUNT(*)` over rows with newer last_mentioned naturally counts distinct, not bumps. The schema shape already satisfied the constraint. Same query, different framing.

### Why the metric does not distinguish phantom from emergent
Stormbridge and River Wynd both flag at threshold=3. That's correct — separating them requires human judgment that no SQL query can supply. Tuning the threshold higher reduces false positives on slow-emerging real geography but slows phantom detection. **The metric surfaces candidates; the human distinguishes phantom from emergent.** River Wynd-class rows will eventually accumulate mention_count>1 if they're real; Stormbridge-class rows won't. The metric is observation, not adjudication.

### Why no composite world_health score
Weighting NPC fragmentation against location skeleton coverage against phantom count is unjustified speculation. A single number hides the underlying signal. The four-number aggregate surfaces components; the human reads them as components, not as a verdict. Composite scores are how you find out a year later that fragmentation drift was getting worse but you didn't notice because phantom count happened to drop. Keep signals independent.

### Why phantom and world_health emit on every extraction turn (including empty)
Continuous time-series coverage. Fragmentation can rise without writes (e.g. when a row's relative position shifts among existing rows). Phantom-candidate count is a function of time-since-mention, which advances every turn regardless of writes. If you only emit on extraction-with-results, you get gappy data and can't reconstruct trends. Cost per empty-turn emit is one indexed SELECT per metric — sub-millisecond.

---

## Campaign management — destruction safety (Session 13)

### Why hard-delete requires two independent gates
Active state is structural protection: the engine refuses to delete an active campaign at the lowest layer (`campaign_delete_cascade`). The typed phrase is human protection: even if the user is in the right state to issue a destructive command, they have to deliberately type the magic words. **Either gate alone is insufficient.**

`/purgeallcampaigns DELETE ALL ARCHIVED` cannot hit the active campaign even with the right phrase, because archived-only is structural. `/purgecampaign 17 DELETE Test10F` cannot fire on the active campaign even with the right phrase, because the slash command verifies status before passing to the engine.

Two independent actions required to destroy data: (1) `/deletecampaign N` to flip the row to archived, (2) `/purgecampaign N DELETE <name>` (or bulk variant). Belt-and-suspenders is the design, not the bureaucracy.

### Why archive is soft-delete by default and hard-delete is explicit
Default to reversibility. Soft-delete satisfies the stated need ("can't delete them") with a trivial undo path (`/setcampaign N` un-archives). Hard-delete is permanent and gets the friction it deserves: a typed phrase per name, or a guild-wide "DELETE ALL ARCHIVED" for bulk. The cost of keeping abandoned campaign data in SQLite is essentially zero; the cost of accidentally purging Donovan Ruby's Stonebridge canon is months of play.

### Why `/setcampaign` un-archives implicitly instead of requiring `/restore`
Two-step un-archive ("you must `/restore` first, then `/setcampaign`") was considered and rejected. Rationale: switching to a campaign IS the act of un-archiving it. The user's intent is "I want to play this." The status flag is a UI hint, not an immutable life-stage. Composing the actions into one command beats forcing a redundant ceremony for the common case.

This applies because archive is a low-cost soft-delete, not an audit-trail "you intentionally retired this and signed off" step. If archive ever becomes the latter, this design changes. For now: switching un-archives.

### Why the cascade primitive enumerates tables instead of reading PRAGMA foreign_keys
Two reasons. First, SQLite doesn't enforce foreign keys without `PRAGMA foreign_keys=ON`, which the engine doesn't currently set — relying on FK cascade would require a global state change with broad implications. Second, even with FK cascade enabled, an explicit table list is grep-able and forces the discipline of "when you add a new per-campaign table, you append it to `_CAMPAIGN_SCOPED_TABLES` or the cascade misses it." Implicit cascade hides that obligation; explicit cascade makes it impossible to ignore.

Comment in the engine names the obligation: *"When new per-campaign tables are added, append them here."* Future drift surfaces as "campaign purge left rows behind" — easy to spot, easy to fix.

### Why batch `/deletecampaign` is atomic, not partial
"Fail the whole thing don't pass" — Jordan's call. Three options were considered:

1. **Refuse the whole batch on any conflict.** User fixes the list and retries.
2. **Skip conflicts, archive the rest.** Tolerant; user gets summary.
3. **Process in order, abort at first failure.** Partial state, order-dependent outcomes.

Option 3 is the worst — partial deletion means the user doesn't know what happened without reading the message carefully, and re-running the same command produces different results.

Option 1 vs option 2 was the real choice. Tolerant batch (option 2) is more user-friendly for typos: pasting `5,17,6` when 17 is the active campaign should "just work" by skipping 17. Atomic batch (option 1) is safer because `/deletecampaign 5,17,6` might be exactly what the user meant — including 17 deliberately because they thought it was archived. Refusing the whole batch forces a deliberate retry, which surfaces the misunderstanding instead of silently skipping it.

Atomic won. The user can fix and retry in one paste; the cost of the failed attempt is one extra command, no data loss, no surprises.

### Why `/campaigns` and `/archived` are separate commands instead of a parameter
Initial design had `/campaigns show_archived: true` as a boolean flag. Rejected after live use: typing `show_archived: true` to see archived campaigns is redundant — the desire to see archived campaigns IS the question, not a modifier on a different question. Two commands, two questions, no flag. Each command has one job.

This is a small UX call but it generalizes: **boolean flags often hide a missing command.** When the flag value almost always matters in one direction (you don't want archived in the daily list, you do want them on the rare archived-management trip), splitting beats flagging.


---

## Roll discipline drift fix (Session 13)

### Why the classifier dropped `in_combat` instead of keeping it alongside `mode`
The literal master signature claim was `(text, in_combat, mode)` — three parameters. Two reasonable interpretations of why both might exist:

1. **Forward-compat:** keep `in_combat` in case a future case wants combat-shape detection independent of declared mode (e.g. an attack-shaped action arrives the turn before init flips the mode).
2. **Belt-and-suspenders:** redundant signal lets the classifier confirm combat detection two ways.

Both rejected. `in_combat` is structurally misleading because the combinations `mode='combat', in_combat=False` and `mode='social', in_combat=True` are logical contradictions unless the classifier invents extra semantics — at which point the orchestration boundary starts leaking. Future contributors would face: "which is authoritative? should I check both? what if they disagree?" That ambiguity is exactly the orchestration entropy WHY/MASTER warns against.

The fix: derive any combat semantics exclusively from `mode == 'combat'`. One signal, one source of truth. The `in_combat` parameter is removed entirely (passing it raises TypeError) so the dead state can't reintroduce itself accidentally.

### Why mode-awareness lives in the classifier AND in `should_call_roll`
At first glance this looks like duplicated authority — two functions that both know about mode. But the responsibilities are separate:

- **Classifier mode-awareness = ordering and ambiguity resolution.** Travel mode prefers TRIVIAL because casual movement during travel shouldn't compete with stealth detection. Social mode prefers SOCIAL+CONTESTED before RISKY because idioms in social contexts shouldn't fall through to risky verbs. The classifier still produces an INTENT_RISKY tag when the text genuinely matches stealth — mode just changes the *order* of checks.
- **`should_call_roll` mode-awareness = rules arbitration.** Given an intent and a mode, decide if a roll is required, what skill, what severity. Downtime → no rolls regardless of intent. Combat-mode CONTESTED → severity='dire' instead of 'meaningful'. Auto-success short-circuits based on character context.

These don't overlap. The classifier doesn't decide whether to roll; it tags. `should_call_roll` doesn't tag; it arbitrates. Mode informs both for different reasons. The architectural boundary is: **classifier never returns a RollDecision; `should_call_roll` never modifies the intent.** As long as that holds, mode-awareness in both places is one concern split correctly across two functions, not duplicated authority.

### Why the negative lookaheads enumerate idiom nouns explicitly
The lookahead is `steal(?!\s+a\s+(?:glance|peek|look|sip|taste|bite|kiss|moment|breath|nap|hug))` — explicit list, not a generic pattern like "any non-physical-object noun." Three reasons:

1. **Defensible scope.** A generic "non-physical noun" rule would require part-of-speech tagging or a hand-curated word list either way. Better to admit it's a list and keep the list visible.
2. **No false negatives.** "I steal a gem" — "gem" isn't in the idiom list, lookahead doesn't fire, RISKY matches. "I steal a kiss" — "kiss" IS in the idiom list, lookahead fires, RISKY skipped. Predictable outcomes.
3. **Future expansion is one-line edits.** New idiom observed in play? Append it to the list, ship the patch. The architecture absorbs the change without restructuring.

### Why over-specified test expectations caught their own form of drift
The first calibration set expected `INTENT_TRIVIAL` for "I steal a glance." The function returns `INTENT_SOCIAL` by fallthrough (no regex matches, default in non-travel modes is INTENT_SOCIAL). Both produce no-roll downstream — functionally equivalent.

So why did the test fail matter? Because it surfaced a gap between what I *thought* the function should return and what it was *designed* to return. The expectation reflected my mental model; the function reflected the spec. When they disagreed, the right move was to check which one was actually correct (it was the function), then update the test.

This is a smaller version of the master/code drift the whole session was fixing. **Mental-model drift is a thing too.** Calibration tests are not just functional regression catchers — they're the explicit-vs-implicit gap detector. Writing them out forces you to commit to a specific expectation, which surfaces over-specification before the code ships.


---

## S9 — Equipment grounding (Session 13)

### Why S9 is a constraint-aware narration safety layer, not a truth engine
First implementation treated `CharacterContext.attacks` as ownership truth and produced binary CONFIRMED/CONTRADICTED verdicts. This produced false positives on every Donovan-class case where Avrae's attacks subset doesn't reflect actual DDB inventory. The fix wasn't "improve the data source" — it was reframing what the system is.

S9 is **not deciding truth**. S9 is deciding: *"what can I safely assume without inventing state?"* The truth lives across three partial projections:
1. Avrae attacks (combat configuration subset)
2. Skeleton.md (author-declared hint layer)
3. DDB (external visual truth, not ingested)

Because all three are partial projections of character truth, **absence of data in any one source is never evidence of absence overall.** This is the load-bearing principle. Any system that violated it would inevitably produce false-INVALID verdicts on real-world cases like Donovan's.

### Why INVALID is reserved for explicit contradiction only
The 3-state verdict (CONFIRMED / VALID_BUT_UNCONFIGURED / INVALID) was initially proposed with INVALID as "no Avrae match AND no skeleton match." That made INVALID the default for unmatched claims. Jordan caught the bug:

> "Absence of data is not evidence of absence in a system where all sources are partial projections."

INVALID semantics were rewritten: **INVALID is only produced by explicit contradiction from an authoritative source.** Skeleton.md doesn't contradict — it only confirms. Avrae's missing attacks doesn't contradict — it just means the weapon isn't combat-configured. The default for unmatched claims must be VALID_BUT_UNCONFIGURED (the bot doesn't know, defers to DM external view), never INVALID.

This means INVALID has NO producer in v1. The enum slot exists so future authoritative-contradiction sources (DDB ingestion that returns no inventory match, DM-override deny lists) can populate it without restructuring. Reserving the slot now keeps the consumer surface (directive renderer, dm_respond wiring, tests) stable for future producers.

### Why skeleton hints can only CONFIRM, never CONTRADICT
The natural extension of "skeleton is a truth source" would be: a character with a skeleton entry that doesn't list weapon X has weapon X explicitly contradicted. Rejected because it makes skeleton.md into a partial DDB mirror — and then the system has the same "absence as evidence" bug at a different layer.

Skeleton stays a HINT layer: declarations upgrade verdict confidence from VALID_BUT_UNCONFIGURED to CONFIRMED, but a missing declaration leaves verdict at VALID_BUT_UNCONFIGURED. This means skeleton authoring is opt-in and unrestrictive: the author can declare what they care about without worrying about completeness. Authoring half a character's gear is safe; the un-authored items remain in the same VALID_BUT_UNCONFIGURED state they'd be in without any skeleton at all.

The architectural rule: **skeleton increases confidence, never decreases ambiguity.**

### Why matching is strict full-string equality, not substring or token-based
Earlier rounds proposed substring matching (player "sword" matches Avrae "Shortsword"), token-set membership (player "crossbow" matches Avrae "Light Crossbow" via tokenization), and family-level grounding (player "greatsword" matches if character has any sword). All produce false positives:

- Substring: "bow" matches "Crossbow" (wrong — crossbow isn't a bow)
- Token-set: same problem on edge cases, plus encourages adding ad-hoc normalization
- Family-grounding: "I draw my greatsword" with character owning Shortsword → false-CONFIRMED

The locked rule: **strict full-string equality, lowercased on both sides. No substring, no token, no regex inference, no partial matching.** A two-layer model handles legitimate generic claims:

- Layer 1 (truth): specific items only (shortsword, shortbow, dagger)
- Layer 2 (convenience): WEAPON_CAPABILITIES family table expands generic player nouns ("sword") to specific aliases for matching

A claim is CONFIRMED only if it matches a specific item, not a category expansion. So:
- "draw my shortsword" → CONFIRMED if shortsword in attacks/skeleton
- "draw my greatsword" → VALID_BUT_UNCONFIGURED unless greatsword specifically declared
- "draw my sword" → CONFIRMED if any specific sword (longsword, shortsword, greatsword, etc.) is in attacks/skeleton; VALID_BUT_UNCONFIGURED otherwise

The locked spec dictum: **"if anything doesn't match cleanly under this system, the fix is data (aliases), not logic."** When real-world friction surfaces (a weapon name we didn't anticipate), the fix is appending an alias to WEAPON_CAPABILITIES, not adding a new matching heuristic.

### Why S9 does not retroactively repair narrative history
The most visible failure mode during live verification: the LLM previously committed a fictional mace into narrative on Turn N, then on Turn N+1 the player's "draw both of my maces" claim got correctly classified VALID_BUT_UNCONFIGURED with the UNVERIFIED directive — but the LLM continued narrating from contaminated history ("the iron-head mace from earlier..."). The mace is now part of the fictional world from the LLM's POV, and the validator can't undo that.

This is **state contamination in narrative memory**, not a grounding failure. Trying to use S9 as a history sanitizer would expand its scope to:
- Hallucination detection layer (scan DM responses for fictional gear claims)
- Retroactive world correction (rewrite or contradict prior narration)
- Conversation-wide contradiction scanning (cross-reference all turns)

Each of these is a separate subsystem. Folding them into S9 would make S9 a god-module. Architectural rule (locked): **S9 must never expand to do narrative-history work, no matter how loudly the symptom shows up there.** Narrative state consistency repair is Phase 4 (separate ship, separate scope) and only built when observed friction surfaces a clear pattern requiring it.

### Why the UNVERIFIED directive language matters
Initial VALID_BUT_UNCONFIGURED directive said: "Not present in Avrae attacks; no contradiction detected. Do not block narration. DDB visibility not ingested."

This was technically correct but ineffective at preventing the LLM from carrying unverified items forward as established fact. Jordan tightened the directive to explicitly mark items as UNVERIFIED and instruct the DM not to treat them as established equipment in subsequent narration.

The behavioral difference: the original wording told the DM what NOT to do (don't block) but didn't tell the DM how to handle the unverified status going forward. The UNVERIFIED framing gives the DM a concrete handle for treating the item differently in future turns — without S9 needing to scan or repair history. This is the right shape: a current-turn directive that constrains future narration via labeling, not via retroactive intervention.

### Why character-name matching is whitespace+case-normalized
Avrae's display name and skeleton's authored name are both human-typed and prone to drift (capitalization, trailing spaces, double spaces). Strict equality lookup would silently miss skeleton declarations on capitalization typos, and those misses would manifest as "Claude inconsistency" rather than "string mismatch in lookup."

The lookup is `' '.join(name.split()).lower()` on both sides — collapses internal whitespace runs, strips ends, lowercases. Authoritative items inside skeleton (the weapon-family names) use strict equality because they're validated against a known finite set. Character names use normalized equality because they're free-form strings.

### Why bot startup auto-cache is filed for later, not solved now
The cache miss problem (`_CHARACTER_CACHE` is in-memory, dies on bot restart, requires manual `/refresh` to repopulate) became visible during S9 live verification. Three reasonable fixes (auto-scan channel history on startup; persist cache to SQLite; passive `on_message` listener for sheet embeds), but solving it during S9 would scope-creep S9 into infrastructure work it doesn't need.

The fix is a separate ship. S9 inherits the cache problem but doesn't depend on it being fixed — when cache is empty, S9 returns `needs_check=False` (no data to check against) and the bot continues operating without S9 directives. Acceptable degradation, not a hard failure.

---

## Consequence surfacing (Session 16)

### Why the parser is dual-pass instead of single-blended
A single parser reading both `player_text` and `dm_text` simultaneously creates a self-reinforcing hallucination loop. Sequence: player threatens Reginald → DM narrates Reginald's pale reaction → single parser sees both, captures the threat from the player text AND captures it again as fallout from the DM narration → one event becomes two consequences (or one with inflated severity because both windows reinforced each other). Same root cause as the LLM contamination patterns in narrative history: data flows in a loop, the loop amplifies itself.

Two parsers each on its own channel, with `sources` accumulating per-row via comma-merge, keeps ingestion provenance pure. Player parser's job: capture player commitments / social acts / acts initiated against an NPC. DM parser's job: capture world reactions / fallout / NPC-side commitments emergent from DM narration. Both use the same 6-kind taxonomy but read different windows and bias against re-capturing each other's events (the DM prompt explicitly forbids re-capture). The architectural rule is the same as `mechanics-vs-narrative` separation in `VIRGIL_MASTER.md` Section 4 — keep the channels distinct at the layer where ambiguity would compound.

### Why severity is parser-judged 1-3 instead of code-baked thresholds
Hardcoding "threat = sev 2; cruelty = sev 3; mercy = sev 2" or weighting one DM's intuition into the source ties calibration to a single moment in time. Severity is highly context-dependent — a player's "I'll kill you if you keep talking" can be sev 1 (banter in social mode) or sev 3 (mid-combat declaration). Code can't read that distinction; the parser has the surrounding context.

The validator only enforces the `[1, 2, 3]` range. The descriptive anchors live in the parser prompt (1 = minor / implied / scene-bound; 2 = notable / direct / scene-shifting; 3 = major / paradigm-shifting / plot-defining), but they're guidance for the LLM, not enforced thresholds. Tunable from `consequence_captured` logs without a code change. Same calibration model as pacing tier thresholds and the new promotion thresholds — intuition-calibrated, log-tunable.

### Why the kind taxonomy is locked at 6 with verbatim definitions
Six kinds (threat, mercy, cruelty, betrayal, promise, alliance) cover the consequence space `THE_GOAL.md` describes without overspecification. The temptation to add `debt` was rejected: debt is a derived state from `promise + alliance + betrayal` history, not a separate captured kind. If debt becomes load-bearing later, build it as a derived metric over the six kinds, not as a seventh row type.

The verbatim-definitions rule is load-bearing. Definitions are embedded in both parser prompts as a single block (`KIND_DEFINITIONS_BLOCK` in `consequence_extractor.py`). Paraphrasing in code or in prompts opens parser drift between the two passes — the player parser starts treating "threat" slightly differently than the DM parser, and the merge semantics get noisy. **Definitions are infrastructure; treat them like API contracts, not docstrings.**

The merge-versus-distinguish question on `cruelty` and `betrayal` was raised in review: they sometimes look similar narratively. They were kept distinct because they produce different NPC reactions — gratuitous harm produces wariness and physical recoil; trust violation produces emotional withdrawal and reduced offers. Collapsing them would lose that signal. **When two kinds produce different downstream behavior, keep them separate even when they look similar at capture time.**

### Why promotion has a distribution check on top of count + age
Initial spec proposed promotion at `surface_count >= 3 AND age_turns >= 10`. The hole: three rapid-fire emits in one heated conversation (single turn or two adjacent turns) hit count=3 trivially. A consequence captured at turn 5, surfaced 3 times in turn 14, would promote at turn 15 — but it's been "active" for one heated conversation, not an established part of the campaign's texture.

Adding `distinct_surface_turns >= 2` as a third axis means the row needs to have surfaced across at least two distinct turns in addition to count and age. The increment-only-when-different logic in `consequence_emit_surface` enforces the axis cleanly. Same intent as the four-number `world_health` aggregate (Session 13): when one signal is easy to game, add an independent signal that's harder.

Three thresholds: 3 surfacings, 2 distinct turns, 10 turns age. All three must hold. Tunable from logs. The distribution check costs one extra column (`distinct_surface_turns`) and one extra integer comparison per promotion run — cheap, defensible.

### Why the directive caps at 3 emits, not 6
First spec considered 6. Jordan locked 3. Reasoning: a prompt block with six bullet rows dilutes the LLM's attention. The model weights one or two and skims the rest. Three rows preserve narrative weight per row — each one has a real chance of shaping the next narration beat.

The relevance filter (NPC must be in scope = recently active ∪ at current location) typically caps emits under 3 anyway in practice. The explicit cap is defensive against future scope creep — when the system has 50 active consequences and 8 NPCs in scene, the cap protects the prompt from becoming a memorial wall.

Sort order is severity DESC → last_surfaced_turn DESC (NULLs last) → id ASC for determinism. Severity wins because high-severity consequences shape behavior more than recent low-severity ones. NULL-last on last_surfaced_turn ensures never-surfaced rows don't get surfaced before previously-surfaced rows at the same severity (ties go to recency).

### Why graduated consequences fold into NPC description (not a new column)
v1 acknowledges double-encoding: a promoted consequence lives in BOTH the `dnd_consequences` table (`status='promoted'`) AND the NPC's `description` field via the bracketed `[promoted: kind] {summary}` append. The same fact echoes through the prompt via two paths.

The choice was between:
1. Add a new `dnd_npcs.notable_traits` column, populate on promotion. Clean separation, but adds schema. Same double-encoding problem at a smaller cost.
2. Append to existing `description` field with bracketed prefix. v1 chose this — no new column, the existing prompt rendering of NPC description carries the prose memory.
3. Don't fold at all; the directive just stops emitting promoted rows. Cleanest, but the LLM "forgets" the NPC's history once the directive is silent.

Option 3 was rejected because the goal is durable memory — the NPC should still feel weighted by past consequences after the directive stops actively reminding the LLM. The folded prose (in description) does that work.

The architectural direction for v2 is filed: **DB is source of truth, prompt is projection.** Future memory tiering (Phase 4) should derive NPC description from a JOIN of `dnd_npcs` + `dnd_consequences (status='promoted')` at render time, eliminating the static append. Until that lands, v1 carries the double-encoding as known technical debt.

### Why `_CAMPAIGN_SCOPED_TABLES` lists `dnd_consequences` first
Listed BEFORE `dnd_npcs` in the cascade tuple. SQLite doesn't enforce FK constraints by default, but the deletion order should respect the parent-child relationship for clarity — and for the future case where `PRAGMA foreign_keys=ON` is flipped, child rows must delete first or the cascade aborts.

`dnd_consequences.npc_id` references `dnd_npcs.id`. If `dnd_npcs` is deleted first, `dnd_consequences` rows would either orphan (FK off) or refuse-to-delete (FK on). Putting `dnd_consequences` first avoids both. Same convention as `dnd_locations` parent-child rules under `dnd_npcs.location_id` — parent table `dnd_npcs` last among the FK chain, children first.

Catching this drift in the doc-update sweep is the lesson: **the doc rule from Session 13 ("when you add a new per-campaign table, append it to `_CAMPAIGN_SCOPED_TABLES` in the same patch") got missed during the implementation pass, and the doc-update sweep surfaced it.** Documentation is a code-review pass.

### Why the directive sits with tactical band, not above philosophy
The spec's first draft said "consequence directive is placed AFTER central thread, BEFORE philosophy." That was based on the spec author's mental model where philosophy is the LAST directive in the prompt. The actual implementation has philosophy HIGH in the prompt (after canonical state, before tactical directives) — philosophy frames how the tactical directives are interpreted.

The correct placement: consequence directive is tactical (constrains *this turn's* narrative move based on accumulated history), so it sits with pacing and central thread in the tactical band, AFTER all of them in render order. Philosophy stays where it is (high in prompt as the framing layer).

The spec text was updated post-review to reflect this, but the implementation followed the spirit (tactical-band placement) regardless of the literal wording. **When a spec contradicts the existing prompt layout, follow the spirit and update the spec — don't move the existing prompt structure to match a misread spec.** Phase 12C and Track 3 directives both established philosophy-as-frame ordering; consequence directive inherits that.

### Why the debug command is `/consequence list [npc]` only — no add, no remove
v1 ships read-only. The reasoning is the validator contract: the parser is the only proposer of consequence captures, and the validator (`apply_consequence_proposals`) is the only writer. If `/consequence add` lands, the validator now has two callers with different shapes — the parser (which guarantees a 4-key dict shape) and the operator (whose typed input the validator must additionally sanitize). The contract gets messier, the test surface doubles, and the system has a path where operator typos can become canonical state.

`/consequence remove` is even more dangerous. The parser has unverified precision in v1; the obvious response to a false-positive capture is "let me delete it." But row-level deletion masks the underlying parser problem — if the parser captures wrong things often enough that the operator wants to delete rows, the fix is at the parser layer (prompt tightening, validator hardening), not at the row layer. **Remove commands enable patches that should be parser fixes.**

`/consequence list [npc]` is sufficient to answer the only question worth asking before the system has live data: "is the parser capturing the right things?" If a richer surface is needed later (e.g., once promotion is tuned and operators want to retroactively override), it gets built then. **Debug commands accumulate; minimal v1 is the discipline.**

### Why turn counter increments at the END of dm_respond, not the START
Two equivalent placements considered. Start-of-turn means `current_turn` advances before any work, so all writes within the turn (capture, surface, promotion checks) tag the new turn. End-of-turn means writes within the turn tag the OLD turn (the one being narrated), and the increment prepares for the NEXT turn.

End-of-turn won because:
1. Capture threads spawned post-narration hold `current_turn` via closure. Their writes (which run async, possibly after the increment) target the turn the player JUST played, not the turn the system is moving into.
2. Promotion runs at the START of `dm_respond` against `current_turn`. End-of-turn increment means the next call sees a turn one higher; the age check becomes correct.
3. If `dm_respond` errors mid-turn, the increment doesn't fire, and the next successful call sees the same turn number. Resilient against partial failures.

The first-capture-on-turn-N and first-surface-on-turn-N+1 invariant follows from this: capture writes `first_seen_turn = current_turn = N`; the next turn starts, increments to N+1, builds the directive at N+1, surfaces with `last_surfaced_turn = N+1`. Distance check (`current_turn - first_seen_turn`) becomes natural over turns.

### Why captures fire as background threads, not synchronously
Two reasons matching the existing pattern:
1. The post-narration LLM call (parser) adds latency we don't want blocking the next player turn. Same as `extract_scene_updates` (Session 6) — the extraction runs async because the next turn starts before the previous extraction needs to be visible.
2. Consequence capture is per-narration, not per-turn-state. The writes don't race with anything that the next turn needs (the next turn's directive reads `dnd_consequences` rows; if the previous turn's capture is still mid-flight, the directive just doesn't see the new row yet — correct degradation, no broken invariant).

The threads hold `current_turn` via closure, so even if they complete after `increment_turn_counter` runs, the writes target the right turn. **Async extraction is the right pattern when (a) latency matters and (b) the write doesn't need to be visible to the next turn that started since the call.**

---

## Operating model (Session 16)

### Why "build to a bar" replaces "wait for friction"
Original operating model was inherited from Session 9: "the system evolves from observed friction, not anticipated friction." That was correct for tuning parameters within already-built layers. It was the wrong frame for whether-to-build-the-layer-at-all decisions.

Jordan's Session 16 reframe: "I'm not playtesting until the system feels ready, so 'wait for observed friction' isn't a viable gate for me. The work is to build the system to a bar I'll trust with friends."

The split:
- **Tuning within an already-built layer** → defer until logs accumulate. Pacing thresholds 25/60/85, consequence promotion 3/2/10, parser precision tuning. These need real data.
- **Whether to build a not-yet-built layer** → spec it now, review it now, ship it now. Reputation/faction layer, curiosity reward layer, item meaningfulness layer, memory tiering. These don't need play data because their design is informed by `THE_GOAL.md` failure modes, not by friction patterns.

`feedback_no_playtest_gate.md` formalizes this. Suggestions like "play a few sessions to surface what's wrong" are dead-on-arrival when the user won't produce that signal. The right path is: structured spec-only passes → user review → implementation → log-driven tuning. Architecture risk is reviewed before code; tuning risk is reviewed at code; play comes after a coherent stack exists.

### Why sequence proposals across unbuilt specs are dependency trees, not commitments
The first draft of `CONSEQUENCE_SURFACING_SPEC.md` had an appendix that proposed "Recommended sequence for spec-only passes: THIS → reputation/faction → curiosity reward → memory tiering." Jordan struck it explicitly: "Sequence note: don't propose the next spec yet. Ship consequence surfacing v1, run it for a couple of solo sessions, see what the capture looks like in the logs (especially the dual-pass channel separation behavior). THEN decide whether reputation/faction is the right next ship or whether something else has earned priority. Sequence proposals are dependency trees, not commitments."

`feedback_no_pre_sequencing.md` formalizes this. The reasoning: each layer's behavior in logs informs which layer is the right next priority. Locking the sequence before any of them ship pre-commits the project to an order that may be wrong. **Filed-not-sequenced is the correct framing.** Candidate next layers are listed; ordering is re-decided after the immediate ship's logs accumulate.

This is distinct from the "no playtest gate" rule. That rule says don't gate WHETHER to build a layer on play data Jordan won't produce. THIS rule says don't pre-commit the ORDER of building unbuilt layers — even though each layer's go/no-go isn't gated on play data, the *sequence* between them is informed by what the previously shipped layer surfaces.

### Why the spec is the speedup, not the slowdown
Three consecutive ships that worked because the spec was real:
- Phase 6 (Session 15): spec, review, ship in same session.
- Phase 12 (Session 12): canonical world state spec'd before any rows landed.
- Track 3 (Session 14): pacing + central thread + philosophy spec'd as imperative-not-descriptive directives, then implemented.
- Track 3 — Consequence surfacing (Session 16): same pattern at v2 spec quality.

In each case, the spec ate the cost of decision-making. When implementation surfaced ambiguity, the spec answered. Architectural dead-ends never made it to code because the review pass caught them in spec.

The naive read is "specs add overhead." The actual data: a session that spends 30 minutes in spec → 30 minutes in review → 90 minutes in implementation ships in 2.5 hours and lands clean. A session that skips the spec spends 90 minutes in implementation, 60 minutes reversing wrong calls, and ships at 2.5 hours with technical debt. **Speccing trades certainty cost up-front for not-having-to-undo-things later.**

The corollary: when a feature is small enough that the design space is trivial (a one-line config tweak, a typo fix), skip the spec. When the design space has architectural choices (where does it sit in the prompt? what's the schema? how does it fail?), spec first.

---

## Diagnostic-first discipline (Session 16 autonomous block)

### Why `godmode_gap` ships before any constraint layer
When Jordan flagged that "I swing my dagger at the barkeep" → next turn → "I help a child outside" gets accepted by the DM with no resolution, the obvious move was "fix it." That's wrong. Two reasons:

1. **The fix is architectural, requiring user review.** Forcing mode flip on COMBAT intent, OR adding a pre-narration commitment ledger, OR firing a tactical directive — each is a different shape with different failure modes. Picking unilaterally would burn Jordan's trust in the autonomous-block model.

2. **The pattern's frequency is unknown.** Maybe it fires once every twenty turns; maybe once every two. The right constraint layer's design depends on the actual rate. A heavy constraint that fires reliably is fine if godmode is rare; the same constraint becomes annoying if godmode happens routinely. Without baseline data, the spec is design-by-guess.

The `godmode_gap` log line costs nothing to ship, breaks nothing, and lets the eventual spec be calibrated against real data instead of intuition. Same shape as Session 13's "diagnostic before treatment" rule applied to architectural decisions, not just fixes.

**Reusable structure:** when Jordan flags a failure mode that needs architectural design, the autonomous response is: (a) ship the diagnostic now, (b) draft the spec pre-review, (c) DEFER the constraint until reviewed. Three steps, in order. Anything else is overreach.

### Why the spec lands as a candidate, not a "next"
`COMMITTED_ACTION_RESOLUTION_SPEC.md` is filed alongside reputation/faction, curiosity reward, item meaningfulness, and memory tiering as candidate next layers. NOT sequenced. Per `feedback_no_pre_sequencing.md`, ordering is re-decided after each ship's logs accumulate signal. The committed-action spec might be next; might not be. The next pick comes from observed signal in `godmode_gap` logs, `consequence_captured` patterns, and whatever else surfaces from real play.

The temptation to sequence ("we should do A before B because B depends on A") is real and usually wrong — most layer dependencies are weaker than they look at design time. Filed-not-sequenced is the discipline that prevents pre-commitment to wrong orderings.

---

## Routing discipline (Session 16 autonomous block)

### Why `extract_scene_updates` should never have been `task_type="dnd"`
Pre-Session-16, the scene-update extractor used `task_type="dnd"`, routing through `groq_heavy` (gpt-oss-120b) with DND_PRIORITY_OVERRIDE. The function does bounded JSON extraction — same shape as `parse_npcs`, `parse_locations`, `parse_consequences_player`, `parse_consequences_dm`, all of which use `task_type="extraction"` (cerebras/groq fallback, explicitly skipping groq_heavy "reserve for DnD" per the router's comment).

The cost of the misrouting:
1. **Wasteful model usage.** The extraction prompt is 200 chars; the response is a small JSON object. Burning the heavy model on this is per-turn overhead.
2. **Latency contention with the actual narration call.** Both the DM narration and the scene-update extraction land on `groq_heavy` at roughly the same time. They serialize, slowing the next-turn cycle.
3. **DND_PRIORITY_OVERRIDE log noise.** Every turn emitted *two* `Trying groq_heavy (reason=DND_PRIORITY_OVERRIDE)` log lines. Made the routing log harder to read at a glance.

The fix is one line. Caught by the doc-update sweep — looking at "what telemetry should the per-turn `world_health` log include?" surfaced the duplicate routing entries as anomalous, which traced to the misclassification. **The discovery wasn't via search-for-bug; it was via system-overview during documentation work.**

**Doctrine:** any structured-JSON-output advisory parser uses `task_type="extraction"`. The DnD task type is reserved for narration generation only. New extraction-style code paths (a future "extract_combat_summary," a "summarize_arc_so_far") inherit the same rule.

### Why doc-update sweeps are code-review passes
Two consecutive sessions where doc-update sweeps surfaced real code drift:
- **Session 16 (consequence ledger ship):** `_CAMPAIGN_SCOPED_TABLES` was missing `dnd_consequences`. Caught while updating VIRGIL_MASTER.md's invariants section.
- **Session 16 autonomous (telemetry composition):** `extract_scene_updates` task_type misroute. Caught while looking at per-turn telemetry log lines for the per-turn world_health emission.

The pattern: implementation passes have narrow attention (focused on the immediate change). Documentation passes have system-level attention (looking at how the change fits the whole). The two attentional shapes catch different drift. Running both as routine session steps is the discipline. The doc pass isn't busywork; it's a second look at the system from a different vantage.

**Future application:** end-of-ship doc updates aren't just for writing things down — they're for re-reading the system at a level that surfaces what the implementation pass missed. Treat the doc update as a code review.

### Why `consequence_race` ships diagnostic-only first (second instance of the doctrine)
Same shape as `godmode_gap` (Session 16 autonomous block), now applied to a different layer. Jordan flagged: when a brand-new NPC is introduced in the same turn as a consequence-bearing action, `apply_consequence_proposals` rejects with `unresolved_target` because the NPC isn't in `dnd_npcs` yet — the consequence is silently lost on the introduction turn. The obvious move was "fix the race." Wrong, for the same reasons:

1. **The fix is architectural, requiring user review.** Three plausible shapes — queue-and-retry rejected proposals after `npc_extractor` completes, thread in-flight new NPCs from `npc_extractor` into `apply_consequence_proposals`, sequence the post-narration extraction order — each has different complexity costs and failure modes. Picking unilaterally is overreach.

2. **The pattern's frequency is unknown.** If introduction-races fire once per session, the loss is acceptable and the fix isn't worth the complexity. If they fire several times per session, queue-and-retry is justified. The data informs the choice; the diagnostic generates the data.

The `consequence_race` log line costs nothing to ship, breaks nothing, and lets the eventual fix be calibrated against real frequencies. Distinguishing the introduction-race subset from the generic unresolved-target reject (whole-word match against the same-turn DM narration) means we can grep one without the other.

**The doctrine, restated:** when Jordan flags a failure mode that needs architectural design, the autonomous response is (a) ship the diagnostic now, (b) draft the spec OR file a one-line ROADMAP entry pre-review, (c) DEFER the fix until reviewed. Two consecutive sessions have applied this template (`godmode_gap`, `consequence_race`) — the structure is now a pattern, not a one-off. The pattern works because it preserves Jordan's escalation rules (architecture decisions need user input) while still moving forward (observability ships, baseline data accumulates, the eventual fix is informed by real signal).

**Filed-not-spec'd corollary:** when the design space is small and the fix shapes obvious (`consequence_race` has three plausible fixes, each ~50 lines), a one-line ROADMAP candidate entry suffices — no full spec doc needed. When the design space is larger and decisions branch (`COMMITTED_ACTION_RESOLUTION_SPEC` had 8 §11 decision points), the spec is the proportionate response. Match the artifact size to the design surface.

### Why OOC contamination filtering is parser-side, not engine-side (S21)
Players sometimes type out-of-character chatter into `#dm-narration` — table-talk about the next combat round, bio-break notes, meta-commentary. The dual-pass parser's player prompt is tuned to find promises/threats/alliances; OOC text often hits exactly that surface ("I promise I'll heal you next turn" as next-round table-talk) and gets ingested as a binding promise consequence bound to whoever was being addressed. Silent canon corruption.

The fix is a leading-marker filter in `consequence_extractor.parse_consequences_player`: messages starting with `((`, `[OOC]`, `OOC:`, or `//` (case-insensitive where it matters, leading whitespace allowed) short-circuit the parser — no LLM call, returns []. The diagnostic line `consequence_ooc_filtered: campaign={N} reason={paren|bracket|colon|slash} text={first 80}` records which marker shape fires, so log analysis tells us which conventions Jordan's table actually uses.

**Why the filter is parser-side, not engine-side:** OOC text is a player-input concern (a social-channel boundary), not a canonical-state concern (a write-validation boundary). Filtering at the parser stops the bad input from reaching the LLM call entirely, which (a) saves the token cost on confirmed OOC text, (b) prevents any extracted-then-rejected loop where the engine would still write a `consequence_rejected` log for content that should never have been parsed, (c) keeps the diagnostic crisp — `consequence_ooc_filtered` is one signal, distinct from `consequence_rejected reason=...` which is canon-validation territory. Engine-side rejection would be redundant; the validator's job is to enforce shape and resolve targets, not to second-guess the parser's input gating.

**Architectural twin: PC contamination guard (Session 15).** Same shape applied to a different vector — `npc_extractor.pc_match` filters PC names out before the `npc_upsert` call, defense-in-depth alongside the engine's own refusal. The pattern: when bad input has a recognizable shape and the parser is the input boundary, filter at the parser. The PC guard is two-layer (extractor + engine refusal) because PC contamination affects canon and the engine is the load-bearing defense; the OOC guard is single-layer (parser-only) because OOC text never reaches a canonical-state write — the validator already rejects unresolved targets, so engine-side OOC checking would be redundant.

**Why the filter is leading-position only (not span-stripping):** Mid-message OOC like "I attack the goblin ((wait BRB)) and swing twice" requires span-stripping rather than message-skipping — different shape, different complexity. We don't yet know whether mid-message OOC happens often enough in real play to justify span work; the leading-marker filter catches the common case (OOC typed at the start of a message), and `consequence_ooc_filtered` log volume per marker will eventually inform whether mid-message stripping is needed. Filed for v2 if logs show a real miss pattern.

**Why the filter is player-channel only (not DM-channel):** `dm_text` comes from the LLM, not from players. OOC contamination there would be the LLM violating its own role — a different problem class than this filter solves. Applying the same leading-marker filter to `parse_consequences_dm` would be cargo-cult: defending against an attack vector that isn't there. The DM parser stays unfiltered.

### Why this ship is fix+diagnostic together (departure from diagnostic-first)
`godmode_gap` and `consequence_race` shipped diagnostic-only because their fix shapes were architectural: multiple plausible designs, each with different failure modes, requiring user review of the proposed shape before code lands. The OOC filter is the opposite: the failure mode (OOC text → false promise/threat capture) is silent and corrupts canon, the fix shape is obvious (regex-match on leading position), the cost is cheap (~30 lines + tests), and the design surface is small enough that there's no architecture choice to escalate. Diagnostic-first is justified when the *fix* is the unknown; here the fix is known and the *frequency* is the unknown — so ship the fix immediately and let the diagnostic log measure how often it fires for future tuning. **Doctrine refinement:** diagnostic-first applies when fix shape is contested; fix+diagnostic applies when the fix is obvious and only its hit rate is unknown.

## Observability batch (Session 18)

### Why four observability items ship as a batch, not as four separate ships
Single log-line ships are too small to justify per-ship doc-update overhead — a one-line code change forces a full ROADMAP edit, a VIRGIL_MASTER telemetry entry, a tests-to-run companion section, and a backup. Four times. Bundling four coherent observability items into one batch amortizes the bookkeeping (one ROADMAP edit, one MASTER edit, one tests-to-run section per item but one file, two backups bracketing the batch). The batch is also semantically coherent: each item closes a different blind spot in the same observability layer (S22 transport, S23 persistence, S24 prompt assembly, S25 directive emission), so the architecture-as-a-whole gets visibility in one pass rather than fragmented over weeks. **Doctrine:** observability is its own ship class, and it earns batching when items share a layer; do not batch across layers (a transport-log + an architectural-spec + a refactor would dilute the batch's coherence).

### Why S23 logs near-matches but does not auto-merge canonical names
The Phase 6 strict-equality identity rule (`PHASE_6_IDENTITY_SPEC.md`) is load-bearing precisely because it's strict. Auto-merging "Donavan" into "Donovan" hides the disagreement instead of surfacing it — the canonical-state layer would absorb a parser stumble silently, and the next time the LLM emits "Donavan" it would write to the merged row without anyone knowing the names diverged. The near-match log surfaces the divergence and lets a human or a future spec resolve it (rename one row, alias the other, or accept that they're different entities). Pure observability preserves the architectural authority for resolution — Jordan or a reviewed spec, never the upsert path. The same reasoning applies to `location_near_match`: locations have weaker identity (a room vs a building vs a neighborhood) but the merge call is still architectural, not a write-time heuristic.

### Why the all-empty test for `directive_emit` must mock the philosophy loader, not just leave the campaign empty
The philosophy directive's source is `dm_philosophy.md` on disk, not campaign state. An "all-empty campaign" still has access to the global philosophy doc, so `philosophy=` will be non-zero whenever the file exists with content. The test's all-empty framing was wrong — it conflated "no campaign-specific signal" with "no global signal." The fix is to monkey-patch `dm_philosophy_loader.get_philosophy_block = lambda: ''` at test setup so all four cases see philosophy=0. **Doctrine:** when a directive's source is global rather than campaign-scoped, the all-empty test must mock the global, not just leave the campaign empty. Same shape will apply to any future global-source directive (a hypothetical `dm_house_rules.md`, a `dm_session_zero_recap.md`).

### Why `directive_emit` is a per-turn aggregate alongside the existing per-directive logs (not instead of them)
The per-directive logs (`pacing_directive:`, `central_thread:`, `dm_philosophy:`, `consequence_directive:`, `capability_check:`) emit when *that specific directive* fires with content. They're high-detail, per-component signals — useful when investigating "why did the pacing directive say climax this turn?" The per-turn `directive_emit:` is a summary signal — useful when investigating "what was the directive stack on turn 47?" or "across this 200-turn session, how often does the philosophy directive carry >2k chars?" The two layers serve different analysis questions. Removing the per-directive logs would lose component-level introspection; removing the per-turn aggregate would force grep-and-correlate across five log streams to reconstruct one turn's directive shape. They're complementary, not redundant. **Doctrine:** observability often wants both granularities — per-component logs for debugging, per-turn aggregates for tuning. Ship both when the cost is one extra log line per turn.

### Why `prompt_size: directives=` is computed from input variables, not from the assembled prompt
`build_dm_context` returns one concatenated string; section boundaries aren't preserved in the output. Two ways to recover section sizes: parse the output string for section markers (fragile — every format change breaks the parse), or measure the input variables before they're concatenated (robust — section sizes match what the assembly pass actually fed in). S24 uses the second approach: `directives = len(pacing_directive_text) + len(central_thread_text) + len(consequence_text) + len(philosophy_text)`. **Doctrine:** when measuring a composite output, prefer measuring the inputs over re-parsing the output — the inputs are the ground truth and the parse is a copy. The same reasoning will apply to any future `prompt_size`-style measurement (a hypothetical `journal_size`, `summary_size`).

### Why `commitment=0` is hardcoded in `directive_emit` instead of omitted
Reserving the field in the log shape now means adding the commitment directive later doesn't break grep patterns — anyone scripting against `directive_emit` log lines today can write `grep 'commitment='` knowing the field is always present. Omitting the field would force every consumer to handle "field present sometimes, absent sometimes" branching. The cost of the placeholder is one literal character in the log line; the cost of the schema break is every grep pattern in the system. **Doctrine:** when a log shape will gain fields in a known direction, reserve the fields with placeholder values rather than adding them lazily. Same reasoning applied to consequence surfacing's `surf_count=0` initial value, central thread's `1|0` boolean shape, etc.

### Why `tests-to-run-post-session.md` is a standing artifact, not a one-off
Every observability ship needs a "how do I verify this fired in production?" companion: the exact Discord input that triggers the log, the journalctl grep that surfaces it, the field-shape expectations. Embedding those instructions in a doc that lives alongside ROADMAP/MASTER means the next session (or Jordan, post-session) can run the verification without re-deriving the trigger conditions from the code. Future single-line observability ships should append a section to this file rather than landing without verification instructions. **Doctrine:** observability ships have a verification artifact requirement — without it, the log line lands but nobody knows whether it actually fires.

### Why the post-session journalctl greps need `--user -u`, not `-u`
`virgil-discord.service` is a user-level systemd unit (lives in `~/.config/systemd/user/`), started under the user's session bus, not the system bus. `journalctl -u virgil-discord` queries the system journal — for a user unit it returns nothing. The correct invocation is `journalctl --user -u virgil-discord`. The original tests-to-run doc shipped with `-u` only; live testing in Session 18 surfaced the silent-empty-output bug when S22's `unconsumed_roll_swept` had actually fired but the grep showed nothing. **Doctrine:** when documenting journalctl invocations, always specify `--user` for user units up front — the failure mode is silent empty output, which is the worst possible failure mode for a verification command (looks like the log didn't fire when it actually did).

## Attack-directive template (Session 18 B2 fix)

### Why bare `!attack` was a silent state-loss bug
`should_call_roll` for `INTENT_COMBAT` returned `RollDecision(needs_roll=True, category='attack', skill='', save='')`. The pre-fix `to_prompt_directive()` had no branch for `category='attack'` — it fell through to the generic `else` branch and emitted `cmd='!roll'` as the quoted command. But the `reason` field (visible to the LLM) said "Avrae handles attack rolls via !attack / !cast", so the LLM ignored the `!roll` quote and freelanced bare `!attack`. The HARD STOP RULE 5 said "the only Avrae command that may appear is the exact command quoted" — but no `!attack` was quoted, so the LLM was technically violating the rule, except the rule's enforcement comes from the LLM following directions, which broke the moment two parts of the directive contradicted each other.

The downstream cost: Avrae received bare `!attack`, picked the character-sheet default attack (Unarmed Strike for Donovan), rolled normally, and emitted `<No Target>: Dealt 2 damage!`. **The attack vanished — no NPC took damage, no consequence captured, no scene-state update reflected the violence.** A complete state-write loss masquerading as a successful roll. Caught only because Jordan noticed "<No Target>" in Discord and asked.

### Why the fix is a fill-in template (option B), not target resolution in the orchestrator (option A) or a post-processor (option C)
Three plausible fix shapes were considered:

- **A.** Resolve target in `should_call_roll` and quote a complete `!attack <name> -t <target>` command. Cost: medium — needs NPC name extraction against player text plus the character's available attack list (which the orchestrator doesn't currently have access to). Risk: orchestrator picks wrong target → wrong NPC takes damage. Bigger blast radius than the silent-loss bug it fixes.
- **B.** Stricter `to_prompt_directive` template that tells the LLM exactly the syntax `!attack "<weapon-name>" -t <target>` and requires it. Cost: low — prompt-engineering only. Risk: LLM still picks the target name itself; if it picks wrong, Jordan can correct in the next turn (better than silent loss).
- **C.** Auto-execute post-processor on the message pipeline that detects bare `!attack` in narration, parses the player text for target, and appends `-t <target>` before relaying to Avrae. Cost: high — new layer with natural-language target extraction under message-pipeline time pressure. Risk: target ambiguity in player text means an NL-extraction call that the system doesn't have a budget for.

B was picked because (a) the cheapest fix removes the silent-state-loss class entirely, (b) the LLM still picks the target so the player can correct in the next turn, (c) no new orchestration coupling. The committed-action spec (`COMMITTED_ACTION_RESOLUTION_SPEC.md`) addresses the deeper "godmode allowed the attack at all" issue, which is a separate ship. **Doctrine:** when a silent state-loss bug surfaces, the cheapest fix that eliminates the silent-loss class beats the more correct fix that takes longer to ship. Loud failure (wrong target) is recoverable; silent failure (no target) is not.

### Why the HARD STOP RULE 5 needed a carve-out for the attack template
The pre-fix HARD STOP RULE 5 said: "the ONLY Avrae command that may appear in your response is the exact command quoted in the ROLL DIRECTIVE." For `!check` and `!save`, the quoted command is literal and the LLM copies it verbatim. For `!attack`, the quoted command is now a template `!attack "<weapon-name>" -t <target>` with `<>` placeholders the LLM must substitute. Without a carve-out, the LLM might either (a) emit the literal placeholder text `!attack "<weapon-name>" -t <target>` (which Avrae would parse as a malformed command), or (b) treat the template as not-quoted-verbatim and refuse to emit `!attack` at all (returning to the bare-`!roll` failure mode).

The carve-out is a single appended sentence: "EXCEPTION FOR ATTACKS: when ROLL DIRECTIVE is an attack roll, the quoted command is a TEMPLATE with `<weapon-name>`, `<spell-name>`, and `<target>` placeholders. Replace EVERY `<...>` placeholder with the appropriate value..." Minimal language change, preserves the rule's strictness for non-attack commands. **Doctrine:** when a constraint rule starts conflicting with a new directive shape, carve out the exception explicitly in the rule itself rather than weakening the general rule. The carve-out makes the special case visible; weakening the rule hides it.

### Why both `!attack` and `!cast` are covered in one directive
The combat intent in `should_call_roll` returns the same `RollDecision` for both weapon attacks and spell attacks. The `reason` field mentions both explicitly. The pre-fix bug applied equally to spells — "I cast fireball at the goblin" would have produced bare `!cast fireball` (or worse, just `!cast`), and Avrae would have prompted for a target. The template covers both forms: `!attack <weapon-name> -t <target>` for weapons, `!cast <spell-name> -t <target>` for spells. The LLM picks based on the player's action shape. **Doctrine:** when fixing a silent failure mode in one code path, scan adjacent paths for the same failure pattern. Combat intent is one mode; weapon attack and spell cast are two shapes that share the same directive — fixing one without the other would leave the spell case broken in production.

### Why B2 needed a B2.1 follow-up: prescriptive directives can crowd out narration
First B2 ship landed the syntax fix and verified live: `!attack "unarmed strike" -t Garrick` was emitted correctly. But the LLM produced a 35-char total response — JUST the command, no narration before it. Two issues surfaced:

1. **Quotes around multi-word weapon names are wrong.** Avrae uses positional parsing — `!attack unarmed strike -t Garrick` is correct, matching the existing convention of `!check sleight of hand` in the skill path. The codebase had this convention; the B2 attack template broke it. Caught by Jordan in live testing — he knows Avrae's syntax better than the spec did.
2. **The directive's strong language ("REQUIRED — Avrae will roll `<No Target>` if `-t` is omitted") plus the long template-filling instructions pushed the LLM into compliance-only output mode.** The LLM read the directive and produced exactly what was asked for: the templated command. Not the narration. Not the attempt description. Just the command. Pre-fix the attack went through with bare `!attack` + narration; post-fix the attack went through with correct syntax + no narration. Net change: traded one failure mode for another.

The B2.1 fix removed quotes from the template (matching codebase convention) and added an explicit narration mandate: "Your message MUST narrate the player's attempt BEFORE the command — a response that is ONLY the command is INSUFFICIENT and breaks the table." Plus a positive example (`!attack unarmed strike -t Garrick` is correct) and a negative example (`!attack "unarmed strike" -t Garrick` is wrong).

**Doctrine:** prescriptive directives shaping a small piece of output (a single command line) can inadvertently shrink the surrounding output too. When adding rigid requirements to a directive, also explicitly preserve the surrounding context the directive is supposed to embed in. The narration-before-command pattern was implicit in the skill/save path because their directives were short and didn't crowd attention; the attack template was long enough that the implicit pattern broke. **Add explicit narration mandates to any directive that's structurally larger than the existing skill/save baseline.**

### Why the post-B2.1 attack still showed `<None>: Dealt 2 damage!` (Avrae layer, not LLM layer)
Layer-by-layer breakdown of the full attack failure mode chain:

1. **LLM emits narration before the command.** Pre-B2.1: failed (35-char command-only). Post-B2.1: works (full attempt narration + command).
2. **LLM emits correct Avrae syntax (`-t TARGET`, no quotes, real target name).** Pre-B2: failed (bare `!attack`). Pre-B2.1: failed (quoted weapon name). Post-B2.1: works (`!attack unarmed strike -t Garrick`).
3. **Avrae binds `-t TARGET` to a real combatant.** REQUIRES initiative tracker (`!init begin` + `!init add Garrick`). Without active initiative, Avrae's target binding fails and the attack rolls against `<None>`. Not addressable from our orchestration layer.
4. **Combat mode auto-flips when player commits violence.** REQUIRES the committed-action spec (`COMMITTED_ACTION_RESOLUTION_SPEC.md`) which orchestrates init management + mode flip + target tracker insertion + attack resolution.

Layers 1-2 are the LLM/orchestration layer (now fixed end-to-end). Layers 3-4 are the Avrae state layer (not addressable from the bot's narration directive — requires either active player init management or the committed-action spec to take over). **Doctrine:** when verifying a fix, separate "the layer we control is correct" from "the end-to-end behavior in the user's view is correct." B2/B2.1 makes our layer correct; the user-visible attack-vanishes mode persists at the Avrae binding layer until the committed-action spec ships. This is honest scope discipline — fix what we can fix, file what we can't.

**Companion observation:** Avrae state from prior sessions can leak. During testing, Avrae attached the attack to a stale combatant `throx` (from some prior session's init tracker) instead of cleanly reporting "no such combatant." This stale-state contamination is its own failure mode — worth a `/init end` cleanup at session start, or eventually an automatic Avrae state reset on campaign load. Filed for next session.


## Three-layer 5e doctrine (Session 19 spec-review block)

### Why architectural decisions land against three layers, not "5e knowledge"

Virgil's architecture treats 5e knowledge as three distinct layers, not one. Conflating them is the most common shape of architectural drift; naming the layer turns the question sharp.

1. **Mechanical layer (Avrae owns).** Attack rolls, damage, saves, skill checks, initiative, conditions, HP, AC, spell slots. Virgil never implements these. Locked since Session 5 (`Why Avrae instead of building our own rules engine`). Any proposal to compute or override mechanics is rejected at the architectural boundary.

2. **Bridge layer (directive layer enforces).** Narrative honors what Avrae knows mechanically. Combat persists while creatures have HP. Initiative order matters. Action economy shapes what's possible per turn. Player commitments to violence trigger combat mode. This is where the committed-action spec lives. Same shape as pacing/central-thread/consequence: convert mechanical state into operational pressure on the LLM's narrative move.

3. **Narrative coherence layer (capability grounding informs).** Prevents the LLM from making things up that contradict 5e's class/level structure. Level 3 fighter doesn't have spells. Rogue's sneak attack requires advantage or ally adjacent. S9 capability grounding is the seed; future expansion extends it.

**Test for any future architectural decision: which layer does this proposal touch?**
- Mechanical → reject (Avrae's domain).
- Bridge → directive shape (Track 3 pattern).
- Narrative coherence → grounding shape (S9 pattern).

The doctrine prevents accidental rebuild of mechanical resolution under the guise of "narrative consistency." The four-layer attack chain in `Why the post-B2.1 attack still showed <None>: Dealt 2 damage!` is the load-bearing failure mode it explains: layers 1-2 are bridge work (LLM directive shape, B2.1-fixed); layers 3-4 are bridge work too (Avrae state orchestration — init binding, mode flip), still UNFIXED. Virgil never rolls the attack. The temptation to "fix it in Virgil" by computing damage or resolving targets ourselves is the rebuild-mechanics-by-accident anti-pattern this doctrine forbids. Bridge-layer fixes are the correct answer; the question is which sub-layer of the bridge.

### Why `last_dm_response` lives in `dnd_scene_state`, not threaded through callers

Session 19's committed-action directive needs the prior turn's DM narration to run its reaction-verb resolution check. The §11 review identified four candidate sources: caller-thread (`discord_dnd_bot.on_message` passes the prior message into `dm_respond`), persist-as-column (one-row migration on `dnd_scene_state`), pull-from-chroma (similarity search), or skip-it-and-rely-on-Avrae-only (weakens detection). Persist-as-column won.

The reasoning is architectural symmetry. `last_player_action` already lives on `dnd_scene_state` and is read by directive functions for the same conceptual reason — "the prior turn's player input is load-bearing context for this turn's narrative move." `last_dm_response` is the symmetric primitive on the DM side. Putting them in the same table, written by the same shape of single-writer helper (`update_last_dm_response` mirrors `update_tension`, `set_scene_mode`, etc.), keeps the data layer narratively scoped and avoids a new caller-coupling. Caller-threading would have made `dm_respond` depend on whichever layer above it remembers to plumb the prior message — multi-actor batches, transition contexts, retry paths, and the Discord-vs-test-harness fork all become surfaces where the wrong message could leak in.

The single-writer rule keeps the column auditable. There's exactly one place that writes `last_dm_response` (between cleaned narration emission and turn-counter increment in `dm_respond`), exactly mirroring how `last_player_action` is the LLM-extraction-thread's responsibility. When the next session reads "what was the prior DM response?" the answer comes from the same place every time.

The downstream payoff is multi-turn lookback (filed §11.6, v2). When that ships, the read path is already in `get_scene_state`; only the write path needs to extend (e.g. ring-buffer the last N responses instead of overwriting). The v1 design didn't pre-build for this, but the schema choice doesn't block it either — overwrite-style storage is the simplest fit for single-turn lookback and the column can grow into a JSON list when v2 demands it. Reverses the spec's §1 "no schema" framing in favor of the cleaner data path; the §11.7 review made the call explicit so the doctrine drift is visible.


## Track 7 — Adjudication Layer (Sessions 25 #4-5)

### Why advisory-to-binding is the load-bearing pattern shift

The directives shipped through S23 (persistence, loot, redirect, footer) and S25 (advisory) all share an architectural shape: **pure-function compute → prompt block → LLM honors at narration time**. That shape is the right shape — it composes cleanly, it's deterministic on the Python side, it scales — but the contract with the LLM is *advisory*. The LLM is asked to honor the directive. Under solo play with a disciplined player, it does. Under multiplayer play where a real second player probes limits naturally (S25 #3), it folds.

S25 #3 multiplayer test exposed eight failures (F-45 through F-52) that all share one root: **the LLM is in the decision path for things that should be deterministic Python.** Failed rolls produced success narration because the roll value was prompt-flavor not constraint. "Says who" defeated capability refusals because the refusal was advisory ("do not block narration"). Player declarations became outcomes because no mechanical layer gated intent. Combat narrated without Avrae state because the combat-mode flip didn't require Avrae backing. Fabricated NPCs entered combat because nothing checked NPC stat existence before resolution.

Track 7 #1 doesn't add a new directive. It promotes adjudication from advisory to binding: **the resolver decides outcomes; the narrator is constrained to narrate the approved outcome only**. The architectural shift is small in code (one new module, one new entry point in `build_dm_context`) but large in contract — what the LLM was previously asked to honor is now structurally enforced before narration generates. Directive siblings (capability_decision, commitment_directive, combat_redirect) deduplicate against adjudication output (§11.L) so they don't double-block; they become consumers of adjudication's verdict instead of independent advisors.

### Why deterministic regex over LLM-based intent classification

Spec §11.E surfaced the choice: classify player input via regex+keyword vocabulary, or via an LLM call that returns an intent category. LLM-based classification was rejected. **Doctrine: an LLM evaluator of LLM input is another hallucination layer.** The S25 #3 failures were specifically caused by the LLM's willingness to be socially pressured; building a separate LLM call to classify intent before narration just adds a second LLM with the same fragility, plus latency, plus cost. Crude regex with bounded action vocabulary (Appendix A in `ADJUDICATION_LAYER_SPEC.md`) is the right shape — it fails closed (unclassified → CHECK_ACTION default) instead of failing open (LLM agrees with the player). Crude beats clever here.

### Why narration constraint renders top AND bottom of prompt

§11.F locked: render `=== ADJUDICATION ===` block at top of prompt for response framing (Doctrine §48 — frame the response shape early), AND repeat the constraint at the bottom (Doctrine §2 — last cache before generation matters). Belt + suspenders. Both renders are required because either alone leaks under prompt drift: top-only fades over long context windows; bottom-only doesn't frame the model's planning. The doubled rendering is the same shape Avrae roll directives use — it's a known pattern, not a novel hack.

### Why §11.K activates S9's previously-dead INVALID code path

S9 (Session 13 equipment grounding) shipped a 3-state `CapabilityVerdict`: CONFIRMED / VALID_BUT_UNCONFIGURED / INVALID. INVALID had no producer in v1 — every refusal softened to VALID_BUT_UNCONFIGURED with "do not block narration" advisory. The code path for rendering an INVALID verdict existed but was never reached. Track 7 #1's `_gate_capability` becomes the first INVALID producer: when the player claims a class capability the character demonstrably lacks (level-3 fighter casting Fireball, bard activating Sneak Attack), adjudication produces INVALID and S9's render branch fires. The dead code wakes up; the architecture S9 prepared for now has its first real consumer.

### Why cache_warm fragility was the limiting factor (Track 7 #1.1)

Track 7 #1's live test produced 4/7 binding categories instead of 7/7. The three capability tests deferred via `_gate_capability` returning `(True, "no_character_context")` because `primary_ctx=None` for every Jordonovan turn — pre-existing condition: `cache_warm` at startup loaded only Bruce Banner. Same campaign, two bound PCs, only one cached. **Adjudication didn't fail; it deferred per the partial-projections doctrine** — INVALID verdicts only fire on EXPLICIT contradiction from authoritative data, never inferred from gaps. Without Jordonovan's sheet, `_gate_capability` had no authoritative source to contradict against.

The fix was small (S25 #5): trigger `cache_autopopulate` when an Avrae `!sheet` embed is detected via `on_message`. No restart, no `/refresh`, no operator hop. Capability adjudication promoted from 4/7 to 7/7 binding with one startup-time fix. **The architecture was deaf, not broken.** This is worth remembering for future ships: when a layer appears to under-perform, before redesigning it, check whether its inputs are populated. Track 7 #1's design was sound; its dependency was incomplete.

### Why post-LLM verification is filed for v2, not shipped in v1

Track 7 #1 adjudicates **player input**. The LLM-output channel — fabricated NPCs entering narration without player input (Silent Beast, Keeper of the Vein), motif drift, item identity flips — is a different surface. Spec §11.F(b) and §12 file post-LLM verification as the v2 contingency: adjudicate the LLM's narration before posting it; if it asserts state that contradicts authoritative data (NPC not in combatants list, item not in inventory, location not at current scene), refuse and re-roll. Track 7 #2 territory.

The reason to ship #1 without #2: player-side adjudication closes ~70% of S25 #3 failures structurally. LLM-side adjudication closes the remainder, but it's a more complex ship (post-generation parse, verification logic, retry policy). Sequencing #1 first lets us measure empirically how much #2 still needs to do; the `godmode_gap` log line continues firing on failures #1 doesn't catch, giving us baseline data for #2's spec.

### Doctrine: narration describes reality, doesn't create it

This is the experience-level phrasing of the architectural shift. THE_GOAL.md was updated S25 #4 to add this as a load-bearing principle. The AI does not decide reality on its own; world state, combat outcomes, character capabilities, and persistent facts must exist outside the narration layer. The DM's job is to describe what happens — not to invent it on the fly when a player pushes back. Track 7 #1 is the structural enforcement of this principle; the goal-doc update is the experience-level commitment.

## Track 7 #2 — Multi-actor Arbitration + Narration Verification (S25 #7)

### Why all-pairs conflict detection, not adjacent-only (§11.R)

The obvious implementation scans verdict pairs in priority order and stops when a conflict is found — effectively comparing each verdict only to its immediate neighbor. That's adjacent-only: with verdicts A, B, C sorted by priority, it checks (A,B) and (B,C) but never (A,C). The spec locks all-pairs (every pair (i,j)) for a real reason: **priority ranking is not transitivity**. B may be compatible with A, and C may be compatible with B, but C can still directly contradict A. The concrete case: A=CHECK_fail, B=COMBAT_action (compatible with both — combat is orthogonal to social outcome), C=FREE_action that says "he agrees with us." Adjacent-only produces `merge_plan='sequence'` because B doesn't contradict A and C doesn't contradict B. All-pairs catches the (A,C) contradiction and correctly produces `merge_plan='override'` with C overridden. Missing a social-override that slips through a middle action is exactly the cross-player-override failure mode (F-50) that Track 7 #2 was built to close.

### Why fork not parameterize for the verification module (§11.J, Doctrine §63)

The first instinct is to add a `mode='verify_output'` flag to `adjudicate()` and extend the existing adjudicator to handle LLM-output verification. This feels DRY — one module, one entry point, shared vocabulary. The spec rejects it. The surfaces are structurally incompatible: `adjudicate()` takes player input text (free-form), a `scene_state`, and a `character` context, then classifies intent via regex. `verify_narration()` takes LLM-generated narration text, an `ArbitrationResult` (the already-resolved binding constraint), and a canonical entity set, then checks for violations. Different inputs. Different detection logic. Different failure modes. Different callers. The only thing shared is "both look at text and return a verdict-shaped result." Doctrine §63 calls this the fork trigger: when the inputs and detection surfaces differ enough that parameterizing would require the caller to pre-condition inputs and the function to branch on mode, the right move is a sibling module. The fork is the DRY point — `VerificationResult` is a sibling to `AdjudicationResult` in the same way `_advisory_respond` is a sibling to `dm_respond`. Coupling them through adjudicator.py would make adjudicator.py the wrong thing to grow when either detection surface needs to change independently.

### Why ACTOR_OMISSION promotes from observability to structural (§11.M)

Track 7 #1's observability layer had a `godmode_gap` log line that fired when the LLM appeared to narrate outcomes inconsistent with adjudication verdicts. This was observational — it recorded the failure but couldn't prevent it. The S25 #3 F-48 failure mode was Jordan's concurrent input silently dropped: two players posted, the LLM addressed only one, and the system logged nothing. Track 7 #2 changes the contract. Once `arbitrate()` resolves N actors into an `ArbitrationResult` with an `actor_order` list, the downstream narration is structurally required to address all N actors. If a bound, resolved actor is wholly absent from the narration, that's not a subtle quality issue — it's a wrong response by construction. A response that mentions Tazz but says nothing about Jordan is not a response to the arbitrated intent; it's a partial response that silently dropped half the input. ACTOR_OMISSION promotes from "we should observe this" to "we must refuse and retry this" for the same reason CHECK_ACTION promotes from advisory to binding in Track 7 #1: the failure mode is deterministic enough that the cost of a retry is always less than the cost of posting a wrong response. The exception is cache-miss actors (`no_character_context` refusal_kind) — ACTOR_OMISSION skips those, because they were never resolved into a binding constraint to begin with.

## Bug 3 — `/travel` durability + NPC list location-scoping (Session 25 #6)

### Why `/travel` not persisting on `dest_resolved=False` was the upstream cause

The S25 #3 multiplayer test surfaced location revert (Veiled Spire ↔ Old Tavern, persisting across restarts). Diagnostic traced to `discord_dnd_bot.py:travel`: `set_current_location()` was only called when the destination resolved to an existing `dnd_locations` row. With `dest_resolved=False` (unknown destination, e.g. fresh travel to a brand-new place), the code path updated only the embed footer via one-shot `label_override`. `dnd_scene_state.current_location_id` stayed pointing at the prior location's row — never updated.

The fix was to call `location_upsert(campaign_id, dest)` first if no match (creating the row), then call `set_current_location(campaign_id, dest_loc['id'])` unconditionally. Single durable write. The `label_override` one-shot becomes a fallback for unparseable destinations only.

### Why the strict NPC location filter (NULL = silent) was the right v1 call

The spec's locked rule was "NULL `location_id` = always-present" — the intuition being narrators, deities, party-wide entities should surface regardless of where the party is. But the data model didn't match the intuition: `npc_extractor` leaves `location_id NULL` by default for any NPC it can't location-pin, which means NULL became "fabricated junk drawer" not "always-present set." With every fabricated NPC the always-present set grew, and post-Bug-3 testing showed Keeper of the Vein still surfacing at Frostmere Hollow because Keeper had `location_id IS NULL`.

Strict filter (`WHERE location_id = ?`) is the right v1 call. NPCs with NULL location are silent until something attributes them. The "always-present" set comes back later with a dedicated `is_omnipresent` flag column when there's actually a use for it (deity, narrator, party patron). Until then, the column doesn't exist and the strict filter holds.

This is a doctrine pattern: **when a spec rule depends on data semantics that don't yet exist, the rule produces failure modes proportional to the data drift**. The "NULL = always-present" rule was correct in principle (about narrators) but wrong against the data model (which uses NULL as "unattributed"). Locking the rule before the data model existed pre-committed the drift. The right discipline is: when a spec rule depends on a column meaning, verify the column actually carries that meaning. If it doesn't, either add a column that does (deferred — `is_omnipresent`) or use the strict interpretation that matches the data (shipped — NULL = silent).

### Why `get_scene_state` regression was a productive catch

Mid-Bug-3 verification, the new filter quietly degraded to None-passthrough (`location_filtered=0` everywhere despite `current_location_id` being correctly set in DB). Tracing led to `get_scene_state` having never SELECTed `current_location_id` from `dnd_scene_state` — the function's returned dict had no such key, so the new filter hit `scene_state.get('current_location_id')` → None → no filter applied.

Fixing the SELECT incidentally re-activated three other directives' location-enrichment paths. The consequence directive (line 4779), commitment directive (line 4831), and init directive (line 4856) all had `current_loc = scene_state.get('current_location_id')` guards followed by `at_location` enrichment that had been silently dormant since the column was added. Bug 3's fix didn't just close the visible bug — it woke up dormant code paths that had been stale for sessions.

This is a recurring pattern worth filing: **when a SELECT regression silently degrades a feature, fixing it can incidentally fix unrelated features that depended on the same SELECT**. The discipline is to verify after fixing what else is reading from the same well. Don't assume the fix's blast radius is local.


## Track 6 #4 — NPC stat hydration at init-add

### Why post-state classification beats command inference

The original instinct was to listen for `!init add` vs `!init madd` commands in `on_message` and classify from the verb. The problem: command interception is fragile (edit events, aliases, autocomplete variants, DM shortcuts), introduces a second listen surface alongside the existing init-list parser, and — critically — produces race conditions when the init-list snapshot arrives before the hydration decision is ready.

Post-state classification reads the init-list embed Avrae already produces: `<None>` means the combatant has no HP backing (added via `!init add`); any other token (`<Healthy>`, `<Bloodied>`, numeric HP) means Avrae owns the HP (added via `!init madd`). This is a single parse of a single embed. No second listener. No race. Classification fires once per snapshot, on already-available data. The distinction "does this NPC have Avrae-managed HP?" is read directly from state, not inferred from command history.

Durable lesson: **if Avrae publishes the post-state distinction you need, read the post-state**. Command interception is complexity without benefit when the state machine already serializes the outcome you care about.

### Why the sync-hint rule is architectural, not Avrae-syntax

Early spec drafts proposed having `/hydrate` emit `!init modify <npc> -hp <N> -ac <N>` so Avrae and SQLite stayed in sync. This was rejected on three architectural grounds.

First, Doctrine §1: stats in SQLite are for the DM's narration context, not for re-implementing mechanics. Syncing SQLite→Avrae inverts the authority model — Avrae is the authority for combat mechanics, and the direction of truth flows Avrae→SQLite (via init-list parsing), never the reverse.

Second, the bot-Avrae write boundary: the bot is read-only on Avrae. Emitting `!init modify` from a slash command handler is a bot→Avrae write, which violates the invariant. Only LLM narration may emit `!`-prefixed commands.

Third, operational fragility: `!init modify` requires the NPC to be in active combat at the time of the call; `/hydrate` is useful before and after combat. Coupling the two operations means `/hydrate` silently fails its Avrae half whenever init is not active — which is most of the time.

The correct model: SQLite carries the DM's working stats for prompt context; Avrae carries the live combat state. The two are intentionally separate. The DM-to-Avrae channel is the DM typing `!init madd` or `!monster` with the right values.

### Why single-hook over belt-and-suspenders

The spec considered two hooks: Hook 1 fires at `!init add` time (eager, before the init list exists); Hook 2 fires on every init-list parse (post-state, classification-ready). Belt-and-suspenders reasoning says: fire both, deduplicate with `_pending_hydration`.

The problem with Hook 1: at `!init add` time, the status_token doesn't exist yet — Avrae hasn't posted the init list. Hook 1 cannot classify. It would have to assume the combatant is a `<None>` (non-Avrae-backed) NPC and fire hydration — then get overridden or deduplicated when Hook 2 fires seconds later after the list appears. This produces a guaranteed false-positive on every `!init madd` NPC that also appears in `!init add` (they don't, but the sequencing between add and madd embed is non-deterministic).

Hook 2 alone is sufficient: every `!init add` and `!init madd` produces an init-list update, which triggers the `_handle_init_list_event` parse path. The single hook gets all new combatants at classification time.

Durable lesson: **don't add hooks for eager delivery when the deferred hook gets the same data with better classification signal**. Eagerness is a cost, not a feature, when it forces you to operate on incomplete state.

### Why `generic_fallback` deliberately leaves `hp_max` NULL

When a DM adds an NPC with `!init add 0 goblin` and hasn't provided a CR via `/hydrate`, the system knows the NPC exists but not its HP. Three options:

1. Guess: pick a CR-1/4 HP value and fill it. Doctrine §1 forbids fabricated mechanics. Out.
2. Leave everything NULL: no stats written, NPC is invisible to prompt context. Wastes the opportunity to give the DM partially-useful context (AC, attacks).
3. Fill partial stats, leave HP NULL: AC, attack_bonus, damage_dice, save_bonus, init_mod written at CR-1/4 defaults; hp_max stays NULL.

Option 3 is the right call. The DM can immediately see in the prompt block that this NPC has AC 13 and a d8 attack, which is usable context for narrating the encounter. The NULL hp_max is a visible signal: "I don't know this NPC's HP yet — use `/hydrate` to provide the real CR." The gap in the data communicates uncertainty rather than hiding it behind a fabricated number.

Durable lesson: **model uncertainty as NULL, not as a default value**. A NULL tells every reader downstream "we don't know this." A default value hides uncertainty behind apparent knowledge.


## Track 5 — Corpus extraction methodology

For corpus-extraction methodology and durable lessons, see
`corpus_builder/corpus_builder_lessons_v2.md` (current lessons doc — Lessons 1–11,
covering Ships 1 and 2). v2 supersedes v1.

---

## Track 4 #3 + Bug 4 (Sessions 27–28)

### Why `.typing()` context managers wrap with try/except in three places (Bug 4, S28)

Discord's HTTP layer is tiered. `POST /channels/{id}/typing` is aesthetic (a "user is typing..." indicator that decays after ~10s and produces no narrative consequence if it never fires). `POST /channels/{id}/messages` is semantic (the actual narration that the player reads). S27 verify-attempt-1 ate a Cloudflare-edge 429 on the typing endpoint mid-`/play`, the `discord.HTTPException` propagated up through `app_commands._do_call` → `CommandInvokeError`, and the slash command hung silently with no narration posted. The user sees "spinning slash command, no reply" — narratively indistinguishable from a hard crash. **Aesthetic transport must never block semantic transport.** The Shape A wrapper (try/except around the typing context, with handler body duplicated under except) makes the soft-fail explicit at every site where Virgil opens a typing indicator. Per-site `typing_indicator_failed:` telemetry surfaces transport-tier degradation without requiring handler-layer awareness of WAF behavior.

### Why Track 4 #3's `set_phase` semantic combines with `days_delta` rather than replacing it

§11.I of TRACK_4_3_SPEC.md locks Option (a): `set_phase: str | None = None` parameter on `advance_time()`. When set, the writer ignores `phase_delta` and computes `resolved_phase_delta = (target_idx - current_idx) mod 6`. The locked §5 normalization formula is `total_steps = before_idx + resolved_phase_delta + days_delta*6`, with new_day = before_day + total_steps // 6. This means `set_phase='Morning'` from a non-Morning start with `days_delta=1` (the long-rest call shape) produces +2 days, not +1 — the modular forward-distance from current phase to target Morning crosses a day boundary that combines with the explicit `days_delta=1` to produce a two-day jump.

The lock-text comment "Long rest: jump to next morning regardless of current phase" is **narrative shorthand** that S28 verify-attempt-2 surfaced as misleading — the verify doc's "Day {N+1}, Morning regardless of pre-rest phase" expected text was built from the comment, not from the formula. The test suite (`test_set_phase_evening_to_morning_long_rest`) asserts the formula explicitly: from Day 1, Evening, long rest lands at Day 3, Morning (+2 days), with `resolved_phase_delta=3`. The math is the spec; the comment is recovered by the test.

**Why we kept this semantic rather than re-locking §11.I:** `set_phase` semantics that "set absolutely without interacting with days_delta" would require either (a) callers to track day rollovers themselves (Doctrine §17 violation — multiple sites reproducing modular phase math), or (b) the writer to special-case `set_phase` differently from `phase_delta` (breaks the §5 normalization formula's uniformity). Both create more complexity than the comment-vs-test divergence the verify doc had. The locked semantic is also operator-meaningful: long rest from Late Night IS narratively a "next day" event (you went to bed at 2am, woke up at dawn the next day), so the +2-day jump from non-Morning starts has internal consistency even if it surprises a reader of the lock-text alone.

### Why `/play`'s footer is hardcoded onboarding text rather than the state-aware operational footer (S28-surfaced; ROADMAP 4b filed)

`/play` predates the state-aware footer system. When `render_state_footer` was extended in Track 4 #3 to carry `· Day N, Phase`, only the narration-batcher path (`_dm_respond_and_post`) was wired. `/play` constructs its embed inline at lines 2965–2974 of `discord_dnd_bot.py` with `embed.set_footer(text="Type your actions in this channel. Roll with Avrae (!check, !save, !attack, !cast).")` — a canned onboarding hint. The hint was right for first-session UX (S23 #4) but wrong for operational re-entry (every subsequent `/play` after a session pause). The existing `is_first_session` gate at `/play` already differentiates first-time-onboarding (append the three-command hint to the body) from returning-narration; the footer should follow the same gate, OR — cleaner — the state-aware footer should always render and the onboarding hint should land in the body rather than the footer.

**Why this is a v1.x ship rather than part of Track 4 #3:** Track 4 #3 v1's promotion criteria key off "footer carries `· Day N, Phase` after every advancement," not "after every embed post." `/play` is initialization, not advancement. The narration-batcher path verifies the footer-wiring contract correctly. The skeleton-seed feature (§J.3) does have an operator-UX gap — the seed write is observable via sqlite + the `apply_starting_time_seed:` log line, but a DM authoring `## Starting time` and running `/play` cannot visually confirm the seed worked because of `/play`'s canned footer. That gap is what motivates ROADMAP 4b as a small standalone follow-up rather than scope-creeping into Track 4 #3 v1.

### Why Step 8's `/purgecampaign` requires three commands rather than one

The verify doc's `/purgecampaign confirm:DELETE` was a five-way wrong: the parameter name is `confirm_phrase` (not `confirm`), the format is `DELETE <campaign_name>` (not bare `DELETE`), the campaign must be archived first (`/deletecampaign campaign_ids:N` flips status), the active campaign cannot be purged (must `/setcampaign` away first), and the doc didn't carry the campaign-name dependency at all. **The two independent gates before destruction** (archive state + typed phrase) are the design — neither alone is sufficient, and `/setcampaign` away is the third practical prerequisite because no one wants to purge the campaign they're actively playing on. The doc was over-condensed; correcting it to the three-command sequence makes the gates visible to operators reading the verify scenario.

## Track 4 #3 + Bug 5 — Structural-vs-narrow fix call (Session 29)

### Why we shipped the structural fix instead of the narrow one

S29's 4b verify surfaced Bug 5: `init_scene_state` in `dnd_engine.py` was using `INSERT OR REPLACE` listing only the original-schema columns. Every column added via ALTER TABLE migration since (`campaign_day`, `day_phase`, `current_location_id`, `turn_counter`, `last_dm_response`, `tension_int`, `progress_clocks`) was being clobbered to schema defaults on every `/play`. Track 4 #3's day/phase persistence broke across `/play` invocations — `advance_time()` writes survived in-session but evaporated the moment the DM re-opened the scene next session.

Two fix shapes were on the table:

- **(A) Narrow.** Add `campaign_day` and `day_phase` to the existing `INSERT OR REPLACE` column list. Closes Track 4 #3 specifically. Same line count as (B).
- **(B) Structural.** Switch from `INSERT OR REPLACE` to `INSERT ... ON CONFLICT(campaign_id) DO UPDATE SET` listing only the fields the writer intends to set. All other columns preserved on existing rows; new rows still get schema defaults via plain INSERT path. Same line count as (A).

Code's first instinct was (A) — the narrow read of "the bug is `campaign_day` and `day_phase` aren't in the column list, so add them." That's true but incomplete. The bug isn't about which two columns are missing; it's about the writer's column list being a fixed snapshot of the schema at authoring time, which silently regresses every time the schema gains a column. (A) closes the immediate bug and ships a time bomb: the next ALTER TABLE-added column on `dnd_scene_state` repeats the failure on whatever future feature depends on its persistence.

**Planner pushed (B).** The reasoning was simple: if (A) and (B) are the same line count, and (B) closes the structural pattern while (A) leaves it open, (B) is free risk reduction. The narrow fix earns its keep only when it's measurably cheaper or the structural alternative is materially riskier. Neither was true here.

The structural fix means the writer says: "I intend to set `last_scene_change` and `updated_at`; everything else, leave alone." That's the correct contract for an `init_scene_state` writer — the function's job is to ensure a row exists with a fresh seed timestamp, not to ground-truth every other column. The new contract survives migrations because it doesn't enumerate them.

### Why this isn't an audit-everything-now moment

Doctrine §75 (filed S29) notes that other writers in the codebase using `INSERT OR REPLACE` against migrated tables should be reviewed at the next opportunity. The deliberate choice was NOT to chase down every such writer right now. Reasons:

1. **No user-visible regression surfaces from the unaudited writers yet.** The pattern is silent until a feature depends on a migrated column's persistence across writes. Track 4 #3 was the first such feature; that's why it surfaced. If another feature surfaces a similar dependency, the audit can be done then with the actual failure mode in hand rather than as a speculative sweep.
2. **Doctrine §74 sweep would be premature.** Reviewing every `INSERT OR REPLACE` writer for migration-safety without a forcing function risks burning effort on writers that don't need to change — e.g. writers that genuinely intend to reset all columns on conflict (rare, but legitimate). Speculative audit produces false positives.
3. **The doctrine is now documented.** Future writers will use `ON CONFLICT DO UPDATE SET` by default per §75, so the population of vulnerable writers is bounded by what was authored before S29. Pre-S29 writers stay on `INSERT OR REPLACE` until something forces an audit.

The principle: catch the structural defect when it surfaces, fix it structurally, document the doctrine, move on. Don't preemptively rewrite working code on the basis of a pattern that hasn't yet failed elsewhere. Sibling to the project's broader "observed friction informs, not anticipated friction" rule.

### Why combined-session shipping was the right call

Doctrine §73 caps restarts at one per session. Bug 5 surfaced mid-verify of 4b; the natural reading of §73 might be "file Bug 5, ship next session." That reading is wrong. §73 constrains restart count, not ship count. Bug 5's fix was small (~10 lines, single function), the test surface was clear (re-seed + `/play` + sqlite check), and waiting a session would have left Track 4 #3's persistence broken in production for the gap.

The combined-session ship still hit one restart total: 4b's restart was Code's deploy step, the engine fix landed before the restart, and the verify-walk covered both ships. §73's discipline is preserved — restart count is one, not two. Shipping a structural fix in the same window as the feature that surfaced it is the correct application of §73, not a violation.

**General rule:** when a verify-walk surfaces a fix that's small, well-scoped, and blocks the feature's full correctness claim, the combined-session ship is preferred over file-and-defer. The forcing function is whether the deferred fix would leave the feature claiming ✅ SHIPPED LIVE while a known correctness gap exists — if yes, ship combined; if no (e.g. the surfaced bug is in adjacent territory and doesn't affect the feature's contract), file and defer.

