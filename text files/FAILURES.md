# Virgil Failure Catalog

Filed failure modes — things tried that didn't work, things rejected after consideration, things that surfaced and got pushed to future work.

Each entry: when it surfaced, what was attempted, why it didn't work, disposition.

## Index

- [§F-01. Silent module-state regression (`chroma_init` missing `global`)](#f-01-silent-module-state-regression)
- [§F-02. Discord channel-level permission overrides silently denied](#f-02-discord-channel-level-permission-overrides)
- [§F-03. Multi-line regex patches failing silently on whitespace mismatch](#f-03-multi-line-regex-patches-failing-silently)
- [§F-04. `!init end` matched as new send instead of edit](#f-04-init-end-matched-as-new-send)
- [§F-05. Stale combatant `throx` from prior sessions in init tracker](#f-05-stale-combatant-throx)
- [§F-06. Actor name mismatch (Avrae vs bound name vs cache key)](#f-06-actor-name-mismatch)
- [§F-07. Hallucinated slash commands (`/tension`, `/scenestate`) in prompt](#f-07-hallucinated-slash-commands)
- [§F-08. Layer 2 narration drift — NPCs never commit](#f-08-layer-2-narration-drift)
- [§F-09. Routing pipeline reorder hidden by sort_by_score](#f-09-routing-pipeline-reorder)
- [§F-10. `USE_KNOWLEDGE_GUIDANCE = False` without user buy-in](#f-10-use-knowledge-guidance-without-buy-in)
- [§F-11. Avrae `!coin` syntax wrong on first whitelist](#f-11-avrae-coin-syntax-wrong)
- [§F-12. Single-file 146KB master rewrite overengineered](#f-12-single-file-master-rewrite)
- [§F-13. Phantom location 'Stormbridge' / `/travel` location revert](#f-13-phantom-location-stormbridge)
- [§F-14. Test files only ran in sandbox, not on server](#f-14-tests-sandbox-only)
- [§F-15. Re-staging from `/mnt/project/` instead of `/mnt/user-data/outputs/`](#f-15-re-staging-from-session-start-snapshot)
- [§F-16. Pushed fix while diagnostic still pending](#f-16-pushed-fix-while-diagnostic-pending)
- [§F-17. COMBAT_RX false positives on `\bfire\b` (noun, not verb)](#f-17-combat-rx-false-positives)
- [§F-18. Clever-not-reliable COMBAT_RX lookbehind whack-a-mole](#f-18-clever-not-reliable-lookbehind)
- [§F-19. Tested against unrestarted bot](#f-19-tested-against-unrestarted-bot)
- [§F-20. PC contamination: address-name fix EXPANDED the bug](#f-20-address-name-fix-expanded-pc-contamination)
- [§F-21. `test_check_action_capability` binary-vs-verdict drift](#f-21-test-capability-binary-vs-verdict-drift)
- [§F-22. Autonomous block first-turn reading-and-planning no-op](#f-22-autonomous-first-turn-no-op)
- [§F-23. First spec proposed sequenced "next 4 layers" appendix](#f-23-spec-proposed-sequenced-appendix)
- [§F-24. Race condition: npc_extractor vs apply_consequence_proposals](#f-24-race-npc-extractor-vs-consequence)
- [§F-25. Empty-narration diagnostic unverified live](#f-25-empty-narration-diagnostic-unverified)
- [§F-26. Combat input bypass via Avrae mechanical commands (godmode_gap)](#f-26-godmode-gap)
- [§F-27. `journalctl -u virgil-discord` (system) vs `--user -u` (silent empty grep)](#f-27-journalctl-user-unit)
- [§F-28. S23 hit-rate prediction wrong (typos auto-corrected)](#f-28-s23-hit-rate-prediction-wrong)
- [§F-29. `bad_name_format` validator false-negative on titled NPCs](#f-29-bad-name-format-validator-false-negative)
- [§F-30. Prompt bloat 24-25k char prompts (no auto-trim)](#f-30-prompt-bloat)
- [§F-31. B2 first ship: bare `!attack` → `<No Target>: Dealt 2 damage`](#f-31-b2-bare-attack-no-target)
- [§F-32. B2 spec convention violation (quoted multi-word names)](#f-32-b2-quoted-multiword)
- [§F-33. Levenshtein vs Damerau-Levenshtein test assumption](#f-33-levenshtein-vs-damerau)
- [§F-34. §11.A retraction (proxy-signal v1 vs bundled-parser v1)](#f-34-11a-retraction)
- [§F-35. §11.B spec-vs-reality drift on bot-stays-read-only](#f-35-11b-spec-vs-reality-drift)
- [§F-36. AC suffix in `!init list` not anticipated](#f-36-ac-suffix-not-anticipated)
- [§F-37. Vestigial `dnd_inventory` schema undocumented in DB](#f-37-vestigial-inventory-schema)
- [§F-38. Phase 6 render gate coupled inventory to sheet caching](#f-38-phase-6-render-gate-coupled-to-sheet)
- [§F-39. Loot v1.0 hallucinated items (loose directive language)](#f-39-loot-v10-hallucinated-items)
- [§F-40. Loot v1.1 chroma contamination (retrieved past polluted current)](#f-40-loot-v11-chroma-contamination)
- [§F-41. `test_campaign_delete_cascade.py` fixture rot](#f-41-cascade-fixture-rot)
- [§F-42. Avrae state-machine assumptions in verification plans](#f-42-avrae-state-machine-assumptions)
- [§F-43. Discord browser paste flattens newlines](#f-43-discord-browser-paste-newlines)
- [§F-44. Chroma bleed: Keeper-class NPCs survive travel through retrieval](#f-44-chroma-bleed-keeper-class-npcs-survive-travel-through-retrieval)
- [§F-56. Avrae embed format fragility](#f-56-avrae-embed-format-fragility)
- [§F-57. Capability gate fail-open on unknown spells/features](#f-57-capability-gate-fail-open-on-unknown-spellsfeatures)

---

## §F-01. Silent module-state regression

**Surfaced:** Session 5
**Context:** 740k knowledge base. `_knowledge_collection` was assigned in `chroma_init()` without a `global` declaration, so the assignment created a local that vanished on function exit.
**Failure mode:** Every `knowledge_search()` call returned empty silently. Six sessions of "DM uses CRD3 exemplars" was actually the DM running with no knowledge guidance at all.
**Disposition:** Fixed in S5. Doctrine: when adding new module-level state, audit every function that mutates it (precursor to §16, §17 single-write-paths).

## §F-02. Discord channel-level permission overrides

**Surfaced:** Session 5
**Context:** Discord channel-level permission overrides silently denied the bot `read_message_history` even though the bot's role had it globally. Manifested as `/bindchar` autocomplete returning empty.
**Failure mode:** First `/setup` patch overwrote Jordan's manual fix back to defaults (compounding the bug).
**Disposition:** Fixed in S5 with `merge_bot_overwrite()` that preserves existing perms. Doctrine: never blindly overwrite permission overrides on existing channels — always merge. Carried forward through S23 #3 / S25.

## §F-03. Multi-line regex patches failing silently

**Surfaced:** Session 5 (and recurred S6)
**Context:** Regex-based patch scripts where whitespace between blocks didn't match the file. Script reported `[ok]` for each step but the actual replacement never happened.
**Failure mode:** Silent no-op on patch application; subsequent commands ran against unpatched code.
**Disposition:** Eventually replaced patch scripts with direct heredoc patches on the server. Doctrine: always verify the change landed (grep) before declaring success.

## §F-04. `!init end` matched as new send

**Surfaced:** Session 7
**Context:** Initial `!init end` regex matched only "combat ended"; Avrae's actual end-of-combat message is "End of combat report: ..."
**Failure mode:** Three reviewers (DeepSeek, Gemini, ChatGPT) all proposed regex fixes; none would have worked because the actual issue was that the message was an EDIT, not a new send. `discord.py`'s `on_message` doesn't fire on edits.
**Disposition:** Fixed in S7 with `on_message_edit` handler — Avrae's dual-channel (message + mutation) shape now correctly modeled. Pattern recurs for any future Avrae integration.

## §F-05. Stale combatant 'throx'

**Surfaced:** Session 8 (initially), re-surfaced Session 18
**Context:** S8 buffer.consume diagnostic showed actor name mismatch. S18 post-B2.1 attack embed showed stale combatant `throx` from a prior session's init tracker.
**Failure mode:** Avrae state contamination across sessions. With no `!init begin` (godmode lets attack happen in exploration mode), targets bind to whatever stale tracker rows exist.
**Disposition:** **Filed for committed-action spec** (`COMMITTED_ACTION_RESOLUTION_SPEC.md`). Both issues downstream of orchestration layer; both addressed by full attack-resolution chain. Filed as a candidate hygiene ship: `/init end` automation at session start (only worth doing if recurrence is high).
**Related:** §F-06 (same family), §F-26 godmode_gap.

## §F-06. Actor name mismatch

**Surfaced:** Session 8 (via 2B.1 buffer.consume diagnostic)
**Context:**
- Avrae says: `'throx'` (lowercased character name)
- Virgil batches as: `'Donovan Ruby'` (bound character display name)
- Cache keyed by: depends on Avrae sheet embed
**Failure mode:** Three names for one entity. `Buffer.consume(actors=['Donovan Ruby'])` pulls 0 events because the buffer holds 'throx' events.
**Disposition:** Filed as the actor-name-reconciliation problem (Phase 6). Not fixed in S8 (out of scope). Defer until 2+ characters bound and rolling.
**Related:** Donovan/Ruby address-name fix in S15 (different layer — surface address vs reconciliation).

## §F-07. Hallucinated slash commands

**Surfaced:** Session 9
**Context:** First Phase 3.0 prompt allowed-list included `/tension` (engine function only) and `/scenestate` (does not exist). Hallucination from prior session memory leaking into the prompt.
**Failure mode:** Live test produced Suggested Actions block with the ghosts.
**Disposition:** Fixed mid-S9. Doctrine: grep the actual slash command surface (`discord_dnd_bot.py`) before listing commands in a prompt — the surface is not the master.

## §F-08. Layer 2 narration drift

**Surfaced:** Session 9
**Context:** Across four consecutive turns with explicit player commitments ("we'll go deeper and grab the chest contents", "let's move", "I am one of the best rogues to live"), the goblin chief never agreed, never refused, never let the party pass. Every NPC stayed ambiguous. Every scene stalled. Phase 3 auto-execute can't commit state when narration doesn't enact change.
**Failure mode:** Architectural: Phase 3 was scoped on the assumption that the friction was "I have to type slash commands." Actual friction was one layer deeper: the narration model wasn't committing to outcomes.
**Disposition:** Resolved in S10 by **model swap** to `groq_heavy` (gpt-oss-120b). Llama-3.3-70b had hit its instruction-following ceiling; gpt-oss followed rules 1-3 alone where Llama needed nine cumulative rules and still wasn't reliable. Validated §9 (don't engineer against model limits).

## §F-09. Routing pipeline reorder

**Surfaced:** Session 10
**Context:** First model-swap patch put `groq_heavy` at the head of the candidate list.
**Failure mode:** Silent no-effect — `sort_by_score` reorders by latency. Patch shipped buggy and was already being demonstrated to Jordan as if it would work.
**Disposition:** Fixed in S10 with scoped override + reason-code logging. Doctrine: when patching a system with multiple sorting/filtering passes, trace the full pipeline before declaring done (§10).

## §F-10. USE_KNOWLEDGE_GUIDANCE without buy-in

**Surfaced:** Session 10
**Context:** Set `USE_KNOWLEDGE_GUIDANCE = False` against Jordan's stated preference ("I really want the DM to use as much of the chromaDB data as possible").
**Failure mode:** Architectural decision made unilaterally without user buy-in.
**Disposition:** Reverted same session. Doctrine: design preferences are not technical decisions Claude makes alone (§11). Formalized as `feedback_escalation_points.md` in S15.

## §F-11. Avrae `!coin` syntax wrong

**Surfaced:** Session 11
**Context:** First Phase 11.1 whitelist drafted with bare `!coin -1gp`. Avrae's actual command is `!game coin +-Ngp`.
**Failure mode:** Whitelist regex didn't match real Avrae output.
**Disposition:** Fixed in S11 after first live test. Doctrine reinforced from S7: capture real Avrae output, don't trust docs (§3).

## §F-12. Single-file master rewrite

**Surfaced:** Session 12
**Context:** Tried to consolidate all 146KB `VIRGIL_MASTER.txt` into a single new master in one pass.
**Failure mode:** Failed mid-write with context exhausted, leaving Jordan with a half-written file.
**Disposition:** Pivoted to four-file split (`VIRGIL_MASTER.md`, `ROADMAP.md`, `WORKING_WITH_CLAUDE.md`, `WHY.md`). Should have been the first proposal, not the second. Doctrine: lighter version is usually right (§7).

## §F-13. Phantom location Stormbridge

**Surfaced:** Session 12; recurred S25 multiplayer test as `/travel` location revert.
**Context:** LLM typo'd "Stonebridge" as "Stormbridge" once; parser dutifully wrote it as a new canonical location. S25 surfaced a second mode of the same family: `/travel` to a destination that didn't already exist in `dnd_locations` left `dnd_scene_state.current_location_id` pointing at the prior location forever — only the embed footer was overridden one-shot. The location_extractor would later create the destination row from LLM narration, but never write the scene_state pointer (single-write-path rule). Result: footer drifts to new location, mention bumps fire on new rows, but the canonical pointer reverts on every `build_dm_context` read.
**Failure mode:** Phantom canonical entries from typos AND silent location reverts after travel to unknown destinations. Structurally identical to legitimate emergent canon — Phase 12B's parser can't distinguish.
**Disposition (S13):** Filed for telemetry detection (Ship 4: `phantom_location_candidates` surfaces `skeleton_origin=0 AND mention_count=1` rows that haven't aged past N other distinct locations). No auto-purge — strict literal match + telemetry + future merge tool > fuzzy match (§14).
**Disposition (S25 — closed):** `/travel` now calls `location_upsert` for unknown destinations, then `set_current_location` unconditionally. Three sibling holes fixed in the same ship:
- `get_scene_state` was missing `current_location_id` from its SELECT — silently broke the at-location enrichment in the consequence/commitment/init directives, dormant since the column was added (regression caught live, not by spec).
- `get_recently_active_npcs` gained a `location_id` filter; `build_dm_context` now passes `current_location_id`. NPC list scoped to current location; live test confirms `npcs_in_context: count=N location_filtered=1`.
- Spec for "NULL location_id = always present" reverted live — parser leaves NULL by default, so the always-present set grew with every fabricated NPC. Strict filter (location_id match only) shipped after S25 turn 1 surfaced Keeper at the wrong location through the prompt block. Followup channel — chroma — broke out as §F-44.

## §F-14. Tests sandbox only

**Surfaced:** Session 13
**Context:** Steps 1-3 of Ship 4 declared "tests passing" while only ever running them in Claude's container. Server-side execution — the actual deployment target — never saw them.
**Failure mode:** Calibration in the sandbox is a fitness check, not a deployment check.
**Disposition:** Workflow corrected mid-session: tests now ride to the server alongside code, run there, archive locally only after green.

## §F-15. Re-staging from session-start snapshot

**Surfaced:** Session 13 (and recurred Session 15 — second instance same ship)
**Context:** Patched `discord_dnd_bot.py` against the wrong base mid-session — would have erased earlier step's changes if Jordan hadn't caught it. Recurred in S15 when copying `dnd_engine.py` from `/mnt/project/` overwrote in-progress engine work.
**Failure mode:** `/mnt/project/` is the SESSION-START snapshot; mid-session work needs the latest output, not the snapshot. Subsequent edits layered on the broken base; the server LOST `phantom_location_candidates`, `world_health_report`, `campaign_delete_cascade`, `campaign_set_status` until recovery.
**Disposition:** Recovery in both sessions worked (cascade and set_status reinserted from chat history; 138/138 tests green on recovered engine in S15). Doctrine §22 documented; carried forward to Claude Code era as "always re-read disk before editing."

## §F-16. Pushed fix while diagnostic pending

**Surfaced:** Session 13
**Context:** When `/purgecampaign` rejected a correct-looking phrase, asked Jordan to run a Python codepoint diagnostic, then immediately built and shipped a whitespace-normalization patch before the diagnostic returned.
**Failure mode:** Confident-hallucination pattern — the patch turned out to be right, but shipping before evidence is exactly what `WORKING_WITH_CLAUDE.md` warns against.
**Disposition:** Doctrine §21 (diagnostic-before-treatment); the diagnostic IS the architecture step.

## §F-17. COMBAT_RX false positives

**Surfaced:** Session 13 (filed) / Session 14 (resolved)
**Context:** `\bfire\b` matches the noun "fire" as well as the spell verb. "Around the fire" classifies as INTENT_COMBAT.
**Failure mode:** False-positive combat classification on common fantasy nouns.
**Disposition:** Out of scope for S13 capability fix; resolved in S14 by **dropping** `fire`, `shoot`, `loose` from COMBAT_RX entirely. Cost: "I fire my bow" no longer auto-prompts the Avrae nudge. Benefit: zero false positives, ever. Replaced earlier whack-a-mole approach (see §F-18).

## §F-18. Clever-not-reliable lookbehind

**Surfaced:** Session 14
**Context:** First-pass fix for COMBAT_RX false positives was a wall of fixed-width negative lookbehinds (`(?<!\bthe\s)(?<!\ba\s)(?<!\ban\s)(?<!\bmy\s)(?<!\byour\s)...`).
**Failure mode:** Passed the test cases I enumerated, but every new false positive ("smoke rose from fire") would require another lookbehind. Whack-a-mole.
**Disposition:** Replaced with the dumber, smaller list — drop the verbs entirely (§F-17). Doctrine §26: when a fix's design depends on an ever-growing exception list, the fix is wrong.

## §F-19. Tested against unrestarted bot

**Surfaced:** Session 15
**Context:** First Donovan/Ruby fix went out, asked Jordan to test in Discord, he reported the bug still happening.
**Failure mode:** The fix HAD landed on disk but the running process (PID 1640406) was still the pre-fix one. Restart was a separate step, easy to miss in a multi-bullet "verification block."
**Disposition:** Fix verified live AFTER explicit restart. Doctrine §31: always verify the running process. Practice: give the restart command first AND make it clear the test won't see the fix until it runs.

## §F-20. Address-name fix expanded contamination

**Surfaced:** Session 15
**Context:** Donovan/Ruby fix changed narration from mostly "Donovan Ruby" → mostly "Donovan" alone. The npc_extractor faithfully wrote a new row for "Donovan" in addition to the pre-existing "Donovan Ruby" row.
**Failure mode:** A fix that changes narration patterns can expose latent extraction bugs. Pre-fix, narration's "Donovan Ruby" produced one contamination form; post-fix, narration's "Donovan" produced a SECOND contamination row. The address fix EXPANDED the bug.
**Disposition:** Fixed same session via two-layer defense (extractor filter + engine refusal — §28) plus DB cleanup of the contamination rows. Doctrine §29: cleanup ships with the fix. Doctrine §30: PC-vs-NPC identity is structure, not prompt.

## §F-21. test_capability binary vs verdict drift

**Surfaced:** Session 15 (recovered S15 second autonomous block)
**Context:** S9 architectural pivot in S13 replaced binary `has_capability` with the 3-state `verdict` enum on `CapabilityDecision`. Tests weren't updated in the same patch.
**Failure mode:** 23 pre-existing failing assertions in `test_check_action_capability.py`. Code correct, tests stale.
**Disposition:** Fixed in S15 second autonomous block: 52/52 tests pass (was 29/52). Doctrine: when an architectural pivot changes a dataclass shape, audit every test in the same patch.

## §F-22. Autonomous first-turn no-op

**Surfaced:** Session 15 (and recurred Session 18)
**Context:** First attempts at autonomous blocks spent the entire opening turn reading files and planning before being interrupted. No code shipped, no tests written.
**Failure mode:** "Reading-and-planning pass" framing burned the budget without producing anything.
**Disposition:** Time-box dropped both times; work proceeded normally afterward. Doctrine: the opening turn of an autonomous block should ship a smallest-shippable-thing, not a reading-and-planning pass. The reading happens incrementally, in service of the next edit, not as a separate phase.

## §F-23. Spec proposed sequenced appendix

**Surfaced:** Session 16
**Context:** Initial draft of CONSEQUENCE_SURFACING_SPEC.md proposed a sequenced "next 4 layers" appendix — `consequence surfacing → reputation/faction → curiosity reward → memory tiering`.
**Failure mode:** Lock-step multi-spec sequence reads as commitments, not candidates. The reframe applies broadly to how candidate next layers should be presented.
**Disposition:** Saved as `feedback_no_pre_sequencing.md`. Doctrine §34: ship one v1, observe, re-decide next; candidate layers are a menu, not a roadmap.

## §F-24. Race npc_extractor vs consequence

**Surfaced:** Session 16
**Context:** When a brand-new NPC is introduced in the same turn as a consequence-bearing player action, the consequence parser may run before the NPC parser writes the row.
**Failure mode:** `unresolved_target` rejection on the consequence proposal; the consequence will fire correctly on the NEXT turn when the NPC re-appears, but the immediate emission misses.
**Disposition:** **Tolerated in v1.** Filed in spec; no action.

## §F-25. Empty-narration diagnostic unverified

**Surfaced:** Session 16 second autonomous block
**Context:** Added two log lines (`dm_respond: EMPTY response from LLM`, `dm_respond: cleaned response too short to narrate`) to surface the "footer-only with no narration" failure mode Jordan saw at 20:41 May 3.
**Failure mode:** Hadn't seen them fire on a real turn yet at session end. The 20:41 turn pre-dates the diagnostic.
**Disposition:** Will fire (or not) on the next session that hits the failure mode. Filed in `tests-to-run-post-session.md`.

## §F-26. godmode_gap

**Surfaced:** Session 16 (diagnostic shipped) / Session 18 (live data accumulating)
**Context:** Jordan: "if I enter combat like swinging my dagger at the barkeep, I just type, 'I go outside and help a child under a wagon' and the DM allows it, so god mode is still very real." The `intent=COMBAT` classifier fires, but `mode=exploration` allows the action through without combat-mode constraints.
**Failure mode:** Player narration bypasses combat mechanical reality entirely.
**Disposition:** **Diagnostic-first** (§39). Shipped `godmode_gap` log line in S16 — fires when `intent=COMBAT` is classified in a non-combat mode. No behavior change. Behavior fix filed in `COMMITTED_ACTION_RESOLUTION_SPEC.md` as a candidate next layer (not committed). S18 B2 attack-template directive partially addresses one symptom (the bare-`!attack` syntax loss), but the godmode root cause stays open.
**Related:** §F-05 (stale combatant binding is a downstream effect), §F-31 (B2 fixes attack syntax not godmode).

## §F-27. journalctl user unit

**Surfaced:** Session 18 live verification
**Context:** `journalctl -u virgil-discord` returned nothing. `virgil-discord.service` is a USER unit (`~/.config/systemd/user/`); `--user -u` is required for the user journal.
**Failure mode:** Silent empty output. Looked identical to "the log didn't fire." Wasted ~2 minutes on the wrong hypothesis (was the bot deployed? was the code right?). Affected all 6 grep examples in `tests-to-run-post-session.md`.
**Disposition:** Fixed all 6 invocations in one sed pass. Doctrine §41: every verification command needs a positive-confirmation test before trusted as a diagnostic.

## §F-28. S23 hit-rate prediction wrong

**Surfaced:** Session 18 live verification
**Context:** S23 (npc_near_match) was designed to catch typo-driven canonical-name fragmentation. Live data showed three independent reasons fragmentation is rare in normal play:
1. DM auto-correction swallows player typos before the parser sees them
2. `bad_name_format` validator (§F-29) drops legitimately-titled characters before INSERT branch
3. New canonical names usually don't sit within distance ≤2 of existing canon
**Failure mode:** Calibration miss in design rationale: "fragmentation will be common because typos are common" missed the LLM's auto-correction loop.
**Disposition:** Diagnostic still earns its keep when it does fire (S18 second test pass: "Garrik" near-match against "Garrick" at distance 1 fired correctly). Doctrine: separate "diagnostic correctly designed" from "diagnostic will fire often" — first is architectural, second is empirical hypothesis to update against first real session of data.
**Related:** §F-29 surfaced as bonus finding from S23 verification.

## §F-29. bad_name_format validator false-negative

**Surfaced:** Session 18
**Context:** `_NAME_RE = ^[A-Z][\w'\-]+(\s+[A-Z][\w'\-]+){0,2}$` requires every word capitalized. "Garrik the Younger" extracted by the parser was rejected by the validator before reaching `npc_upsert`.
**Failure mode:** Real false-negative pattern for legitimately-titled characters (Garrik the Younger, Hilda the Brewer, John of Stonebridge).
**Disposition:** **Filed as ROADMAP candidate.** Fix is a small regex extension (allow lowercase connector tokens between capitalized parts) but touches noise-rejection territory load-bearing for keeping junk like "the merchant" out of the NPC table. Don't ship without thinking through the connector-list scope.

## §F-30. Prompt bloat

**Surfaced:** Session 18 live verification
**Context:** S24 `prompt_size` telemetry showed every turn in campaign 17 measuring **24-25k chars** total prompt size. Empty-narration failure mode at 11:44 had `prompt_chars=23789` — within the same range as turns that narrated successfully.
**Failure mode:** Bloat is variance-driven, not threshold-driven. Biggest single block in the directive stack is the philosophy doc at 3,343 chars (33% of `directives=`).
**Disposition:** **No auto-trim in v1** — log measures, doesn't shrink. Filed: data accumulates; trimming waits for a clear bloat-source pattern. Cutoff is architecture territory.

## §F-31. B2 bare attack no target

**Surfaced:** Session 18 live verification (mid-S22 verification window)
**Context:** Jordan typed "I attack the bartender with an unarmed attack". The pre-fix `to_prompt_directive()` had no `category=='attack'` branch, fell through to generic `else`, emitted `cmd='!roll'` as the quoted command. The `reason` field told the LLM to use `!attack`. LLM resolved the contradiction by emitting bare `!attack` with no target argument.
**Failure mode:** Avrae picked the character-sheet default (Unarmed Strike) and rolled against `<No Target>` — a complete state-write loss masquerading as a successful roll.
**Disposition:** Fixed in S18 with B2 attack-template directive (`!attack "<weapon-name>" -t <target>`). HARD STOP RULE 5 carve-out for attack templates. 30 assertions in `test_attack_directive.py`.
**Related:** Introduced §F-32 in the fix.

## §F-32. B2 quoted multiword

**Surfaced:** Session 18 second test pass (B2 → B2.1)
**Context:** B2 spec added quotes for multi-word names because that's how external CLI conventions work (argparse positional with quoted multi-word args). The codebase's `!check sleight of hand` path was right there in the same file, unquoted.
**Failure mode:** First B2 test produced `!attack "unarmed strike" -t Garrick` — quotes mismatch Avrae's positional parsing. Plus zero narration before the command (directive's prescriptive language pushed LLM into compliance-only output). Net change: one failure mode swapped for another.
**Disposition:** Fixed in B2.1 single Edit — dropped quotes, added explicit narration mandate. Doctrine §43: codebase conventions outrank external knowledge. Doctrine §44: run a SECOND live test for trade-off-instead-of-fix.

## §F-33. Levenshtein vs Damerau

**Surfaced:** Session 18 (during S23 test development)
**Context:** Test pair `levenshtein('Tavren', 'Tavern')` is 2, not 1 — adjacent-character transpositions cost two operations in standard Levenshtein (delete + insert), not one (which would be Damerau-Levenshtein).
**Failure mode:** Test failed `loc_dist1: distance=1`.
**Disposition:** Fixed by changing the test pair to `'Cavern'/'Tavern'` (single substitution = distance 1). Doctrine: when picking test inputs for an edit-distance metric, verify the metric variant.

## §F-34. §11.A retraction

**Surfaced:** Session 21
**Context:** Original §11.A recommendation for combat persistence was directive-only with abstract claims ("Avrae has the data, honor it"). Bundled-parser v1 added a parser-side data layer rendering "Garrick — HP unknown", "Donovan Ruby — HP 11/11" directly in the prompt.
**Failure mode:** Abstract directive without concrete state — LLM compliance was a hypothesis. Original recommendation was retracted in favor of doubling spec scope to ship the data layer.
**Disposition:** Retroactively the right call — LLM narration honored the listed combatants ("goblins glaring, knives half-drawn") on first test. Doctrine §48: concrete-in-prompt narrows the LLM's drift surface.

## §F-35. §11.B spec-vs-reality drift

**Surfaced:** Session 21
**Context:** §11.B's wording ("hard gate would be a parallel invariant violation") sounded principled in spec review. But Phase 2A.3 had already shipped exactly the gate it framed as off-limits, at `discord_dnd_bot.py:565`.
**Failure mode:** Spec was written in isolation from existing on_message hard-gate code path. Two architectural layers of the same system were the gap.
**Disposition:** Three-option escalation: (a) remove gate, (b) ship as-spec'd with dead OFF-turn paths, (c) retroactively soften §11.B. Jordan picked (c). Avoided destroying shipped multi-account UX or shipping unreachable directive code. Doctrine §47: specs drift from code; grep before locking.

## §F-36. AC suffix not anticipated

**Surfaced:** Session 21 first live test
**Context:** Spec carried Phase 1 format-unknowns flagged for real-combat fixtures. First live test produced `combatants=1` instead of `combatants=2` because Donovan Ruby's row carried a trailing `(AC 13)` outside the `<...>` slot. Test fixtures hadn't exercised hypothetical-trailing-content cases.
**Failure mode:** Format-unknowns called out in spec; fixtures didn't generate at-least-one-permissive-fixture for them.
**Disposition:** Permissive trailer fix `[^\n]*$` (instead of `\s*$`) absorbs this and any future trailing surfaces. Format LOCKED in spec §5.6. Doctrine §49: format-unknowns demand fail-open path AND parse-unknown log line.

## §F-37. Vestigial inventory schema

**Surfaced:** Session 22 #1 Phase 1 diagnostic
**Context:** `grep "dnd_inventory" *.py` returned no Python references. But the schema-existence check (`sqlite3 .tables`) caught a vestigial `dnd_inventory` schema in the live DB — different shape (`character_id` FK, no code references, undocumented in §7).
**Failure mode:** Initial Phase 1 grep undercounted prior art — would have written the new schema with a name collision against the existing one.
**Disposition:** Replaced with new shape `(campaign_id, character_name)` matching the rest of the project's pattern. Doctrine: when speccing a new schema, always check the live DB schema list, not just code references.

## §F-38. Phase 6 render gate coupled to sheet

**Surfaced:** Session 22 #1 first live test
**Context:** Phase 6's render gate was `len(character_contexts) == 1`, but `character_contexts` only populates when the Avrae sheet has been parsed and cached. Donovan's hadn't been at the time of test.
**Failure mode:** Inventory rendered cleanly via `inventory_add` log, but no `inventory_render` log line — silent failure mode where feature reads "the active character" from a conditional source.
**Disposition:** Fixed in S22 #1: thread `acting_character_names` through `dm_respond → build_dm_context` as a new kwarg, source actor identity from `acting_character_names[0]` first, fall back to `character_contexts[0].name` second. Doctrine: when a feature reads "the active character," check whether the source is universal or conditional.

## §F-39. Loot v1.0 hallucinated items

**Surfaced:** Session 22 #2 first live verification pass
**Context:** v1 directive language was too soft: "Narrate the discovery naturally — what's on the bodies, what's worth taking. For coin pickup, surface a mechanical hint inline like: `!game coin +3sp`."
**Failure mode:** Two failure modes hit at once:
- "Narrate the discovery naturally" read as editorial latitude. LLM heard "improvise based on vibes" and substituted thematic alternatives ("iron ring with wolf-rune" replacing "rusty shortsword")
- Static `+3sp` example masqueraded as data. LLM treated it as the actual coin amount and emitted `!game coin +3cp` for a 12-sp drop. Classic prompt-engineering failure: the example became the ground truth.
**Disposition:** Fixed in v1.1 — "AUTHORITATIVE and EXHAUSTIVE" framing per Jordan's wording; coin example became dynamic via `_coin_hint_example(summary)`. **Failed again** — see §F-40.

## §F-40. Loot v1.1 chroma contamination

**Surfaced:** Session 22 #2 second live verification pass
**Context:** v1.1's tighter directive STILL lost. Pass-2 narration kept the iron ring + parchment + copper coins from the prior failed turn. Diagnosis: `chroma_search(campaign_id, 'loot the goblin')` retrieved the 10:25:51 DM turn (containing the bad loot text from pass 1), formatted it as `Relevant past events: ...`, and `build_dm_context` placed it BEFORE the tactical-band loot directive. Attention bias favors the earlier block.
**Failure mode:** Chroma stored failed narration → retrieved it next turn → LLM treated it as authoritative scene context. Contamination compounds across turns. The directive's "AUTHORITATIVE" framing competed with retrieval and lost on placement alone.
**Disposition:** Two-prong fix in v1.2:
- **Chroma purge** (destructive, with explicit Jordan approval) — both contaminated docs exported to `/mnt/virgil_storage/digest/chroma_purge_track4_loot_2026-05-05.json` then deleted. Post-delete contamination scan: 0 `iron ring`, 0 `wolf-rune` in campaign 17.
- **Retrieval override clause** in the directive: "If retrieved past events ('RELEVANT PAST EVENTS' block above) describe different loot for this body, ignore those descriptions. The list in this block supersedes any prior narration and is the current ground truth."
Doctrines: §52 (failure modes stack), §53 (chroma is a cross-turn behavior source), §54 (procedural confirmation ≠ re-decision — Jordan's call on the export-then-delete pattern).

## §F-41. Cascade fixture rot

**Surfaced:** Session 22 #2 (pre-existing)
**Context:** `test_campaign_delete_cascade.py` fixture creates only 7 of the 10 tables `_CAMPAIGN_SCOPED_TABLES` references (missing `dnd_consequences` from S16, `dnd_combatant_state` from S21, `dnd_inventory` from S22 #1, and now `dnd_loot_pending` from S22 #2).
**Failure mode:** 9 of 13 tests fail with `sqlite3.OperationalError: no such table: dnd_consequences`.
**Disposition:** Not caused by Track 4 #2 — pre-existing fixture rot. Flagged via `mcp__ccd_session__spawn_task` for cleanup in a separate session (refresh fixture to mirror current cascade tuple, or refactor to iterate `_CAMPAIGN_SCOPED_TABLES` and create matching tables programmatically).

## §F-42. Avrae state-machine assumptions

**Surfaced:** Session 23 #1 (Stage 2) and reinforced Session 23 #2 (bonus stage)
**Context:** S23 #1 Stage 2 had `!init begin` + add combatants + narrate, expecting the combat-with-active-turn footer. Avrae stops at "round 0" after `!init begin` — no combatant is activated until you run `!init next`. So the bot saw `mode=combat` but `get_active_turn` was None, and the fallback `(not set)` line fired. S23 #2 had two consecutive predictions ("GO1 will be active first") miss — Avrae landed on Donovan both times, then GO1 only on the third.
**Failure mode:** Test plan assumed states Avrae doesn't actually produce. Three Avrae init rolls, predictions 0/3.
**Disposition:** Doctrine §57: verification plans for external state machines describe target state ("on Donovan's turn, type a bypass"), don't prescribe command sequence ("Stage 3 = !init next then narrate"). Stage assignments conditional on Avrae state, not numerical.

## §F-43. Discord browser paste newlines

**Surfaced:** Session 23 #1 live verification
**Context:** Jordan's first paste of the multi-line embed footer text showed everything on one line, raising concern that `\n` separators weren't rendering.
**Failure mode:** Browser-side flattening of newlines into spaces during paste; the actual Discord client rendering was correct.
**Disposition:** Fixed by screenshot confirmation. Doctrine: when verifying multi-line UI rendering, ask for a screenshot or visual description, not just the pasted text.

## §F-44. Chroma bleed: Keeper-class NPCs survive travel through retrieval

**Surfaced:** Session 25 post-Bug-3 verification, Frostmere Hollow turn.
**Context:** With Bug 3's NPC-list location filter shipped and confirmed clean (`npcs_in_context: count=0 location_filtered=1`), the LLM still narrated Keeper into Frostmere Hollow on the very first "look around for any familiar faces" turn. The SCENE STATE prompt block was empty of Keeper; the channel was `RELEVANT PAST EVENTS`, served by chroma session-memory retrieval. Chroma is campaign-wide and returns past turns by semantic similarity, so any prompt with words like "tavern," "look around," "familiar" pulls Old Tavern + Veiled Spire transcripts back into context regardless of where the party physically is. The LLM faithfully wove the retrieved cast into the new arrival narration — Keeper's voice, the scarred barkeep, the cloaked elf — and even attached Keeper's archaic-snarl pattern to the local barkeep with a pronoun flip.
**Failure mode:** Two distinct sub-failures share this channel:
1. **Location bleed** — past-turn scenes from prior locations resurface as if present, defeating travel.
2. **Identity bleed (Keeper-class)** — fabricated NPCs from prior turns get re-summoned by retrieval and the LLM is instructed to treat them as on-screen. Worse than location bleed because identity carries voice and motive, which the model fuses with whatever local NPC has the lowest narrative friction.
**Disposition:** **Filed v1.x — not in Bug 3 ship** (predicted in the diagnostic; held the line per task scope). Two candidate fixes, neither blocking:
- *Chroma scoping:* tag stored turns with `location_id` at ingest, filter retrievals to current `location_id` ∪ explicit-recall queries. Cheap if the embedding records support metadata filters; needs a backfill plan for turns already stored.
- *NPC retrieval gate:* before injecting `RELEVANT PAST EVENTS` into the prompt, strip lines naming NPCs whose `location_id` doesn't match the current scene. Coarser, but doesn't require chroma schema changes.
**Related:** §F-13 (Bug 3 closed the prompt-block channel; this is the remaining channel). Track 7 #2 (LLM-fabricated NPC continuity, Keeper-class) overlaps — same NPC, different surface.

## §F-45. Failed rolls produce success narration

**Surfaced:** Session 25 #3 (Multiplayer Test).
**Context:** Bruce Banner rolled 2 on Perception → DM narrated quest lore about the Veiled Spire. Bruce rolled 8 on Investigation → DM revealed pressure plate location.
**Failure mode:** Roll discipline (S6) asks for checks but doesn't bind narration to outcome. The roll value is in context as flavor, not as a constraint. LLM treats low and high rolls as approximately equivalent.
**Disposition:** Closed structurally by Track 7 #1 CHECK_ACTION binding (S25 #4) — narration constraint forces failure shape on failed rolls.

## §F-46. "Says who" defeats capability refusals

**Surfaced:** Session 25 #3.
**Context:** Player asked "poop out a crystal baby and ride it like an airplane." Capability layer correctly refused. Player pushed back with "says who." DM invented a Keeper of the Vein NPC to retroactively justify the refused action.
**Failure mode:** Capability grounding (S9) softens to "soft annotation, do not block narration." Refusals were advisory — LLM could be socially pressured into reversing them via fabricating in-fiction justification.
**Disposition:** Closed structurally by Track 7 #1 WORLD_BOUNDARY_ACTION + CAPABILITY_ACTION binding refusal kinds (S25 #4) and Track 7 #1.1 (S25 #5). Refusal shape includes "do not invent in-fiction workaround."

## §F-47. Player declarations narrated as outcomes

**Surfaced:** Session 25 #3.
**Context:** "Mind control him to eat crystals till he dies" narrated as resolved with no save, no spell slot, no class capability check (Jordonovan is a bard but Suggestion was never cast). "Take off his head" treated as already-done before the attack roll resolved.
**Failure mode:** No mechanical layer between intent and outcome. LLM accepts player intent as outcome and elaborates.
**Disposition:** Closed structurally by Track 7 #1 CAPABILITY_ACTION + COMBAT_ACTION binding (S25 #4) — capability gate refuses spells without slots; combat gate requires Avrae state for resolution.

## §F-48. Concurrent player input collision

**Surfaced:** Session 25 #3.
**Context:** Jordan: "try to steal some of those crystals" + Tazz: "Hit one with my axe" posted within seconds. DM only addressed Tazz. Jordan's input was silently dropped.
**Failure mode:** No multi-action turn handling. Latest message wins; prior concurrent inputs absorbed without resolution.
**Disposition:** Closed by Track 7 #2 (S25 #7). Two structural mechanisms: (1) `arbitrate()` in `adjudicator.py` resolves N concurrent player inputs into structured intents (`actor_order: list[str]`, `verdicts: list[AdjudicationResult]`, `merge_plan: 'sequence'|'override'`) — both actors enter the prompt as binding constraints rather than only the latest. (2) `ACTOR_OMISSION` violation class in `narration_verifier.py` provides output-layer enforcement: if an arbitrated non-cache-miss actor is wholly absent from the LLM's narration, verification fails and triggers retry. Input-layer + output-layer closure means "Jordan's input silently dropped" cannot recur for bound actors. Cache-miss actors (`no_character_context` refusal_kind) are excluded from ACTOR_OMISSION checks per §11.P.

## §F-49. LLM-fabricated NPCs entering combat with no Avrae backing

**Surfaced:** Session 25 #3.
**Context:** Silent Beast and Keeper of the Vein both invented mid-narration. Both became combatants. Neither had stats, attacks, controller assignment, or init entry. Combat existed narratively but Avrae was dormant for ~6 turns. Footer fell to "Round ?" / "Turn: (not set)" diagnostic across the entire combat sequence.
**Failure mode:** LLM fabricates NPCs at narration time. Combat state flips internally but `!init begin` / `!init add` / `!attack` emissions don't fire because the combatant doesn't exist mechanically. The combat-init orchestration directive (S20) only fires when player intent matches its trigger pattern; fabricated-creature combat bypasses it entirely.
**Disposition:** Closed by Track 7 #2 (S25 #7) for the named-fabrication channel. New `narration_verifier.py` module — pure-function sibling to `adjudicator.py` per Doctrine §63 fork. `verify_narration(narration_text, arbitration_result, scene_state, combatants, npcs_canonical) → VerificationResult` runs after the LLM emits narration but before the bot posts. `FABRICATED_COMBATANT` violation class (one of four locked classes per §11.F) detects NPC names in narration that aren't in combatants / bound-PCs / canonical NPC table / skeleton-declared. First violation wins, 1-retry loop, escalation placeholder per §6.3 per-category branches on second failure. Closes the Silent Beast / Keeper-of-the-Vein channel structurally — fabricated NPCs can't reach the post step. **Anonymous-shape combatants** ("a hulking shadow lunges") are filed v2 — out of scope for v1 detection. **NPC stat hydration (Track 6 #4, S25 #8)** closes the operational complement: verification refuses fabrication; hydration enables legitimate addition. When a DM legitimately adds `!init add 0 goblin`, the NPC enters the canonical table and `narration_verifier.py` finds it there — fabrication detection and stat hydration are now both live. The two ships are architecturally paired: without hydration, every legitimately-added NPC without a `dnd_npcs` row would trip the verifier as a false fabrication; without verification, fabricated NPCs bypass the canonical table entirely. Both ships required; both now live.

## §F-50. Player override of another player's action by social assertion

**Surfaced:** Session 25 #3.
**Context:** Tazz: "I take the flute from Jordonovan and throw it" → DM resolved. Jordan: "nuh uh you cant do that its mine" → DM rolled it back, gave Jordonovan the fragments. No contested check, no resolution mechanic.
**Failure mode:** Players overriding each other's actions through social assertion alone. DM accommodates whichever player asserts loudest.
**Disposition:** Closed by Track 7 #2 (S25 #7) as a structural side effect of arbitration. `arbitrate()` performs all-pairs conflict detection (§11.R — every pair (i,j), not adjacent-only) with text-aware contradiction detection: a FREE verdict overrides a binding verdict only when the free text explicitly asserts an opposing outcome ("he agrees with us" vs CHECK fail; "the room ignites" vs CAPABILITY refusal). When override fires, `merge_plan='override'`, `overridden_actors: list[str]` enumerates each overridden actor, and `combined_constraint` renders the override as reaction-not-outcome ("Jordan asserts ownership; Tazz reacts to the assertion — outcome resolves through dice or DM ruling, not declaration"). All-pairs-not-adjacent matters: priority ranking is not transitivity, so a social override that slips through a middle non-contradictory action would have escaped adjacent-only detection — which is exactly the Tazz-Jordan flute scenario. Locked priority rule from §11.C: binding categories outrank FREE; explicit-contradiction FREE overrides require dice or DM ruling rather than narrative accommodation.

## §F-51. Combat narration without Avrae state

**Surfaced:** Session 25 #3.
**Context:** Multiple combat sequences ran with `mode='combat'` flagged in scene state but `get_active_turn` returning None. Players narrated attacks; DM narrated outcomes; Avrae's `!init` tracker stayed empty for ~6 turns.
**Failure mode:** Mode-flip path bypasses orchestration directive. Combat exists in narrative but not mechanically.
**Disposition:** Closed structurally by Track 7 #1 COMBAT_ACTION binding (S25 #4) — combat narration refused when Avrae state isn't populated; player prompted to use `!init begin`.

## §F-52. DM motif drift / vivid recent detail looping

**Surfaced:** Session 25 #3.
**Context:** DM looped on lute/flute motif across multiple turns even when player actions had nothing to do with music. Item identity drift: lute became "silver flute" mid-conversation. Crystal hum mentioned in five consecutive turns regardless of relevance.
**Failure mode:** LLM anchors on recent vivid details and re-injects them as flavor. Chroma retrieval surfaces past-vivid scenes; prompt context bias amplifies.
**Disposition:** Filed for v1.x. Not architecturally addressable without prompt-engineering pass. THE_GOAL.md updated with "Memorable details should recur intentionally, not compulsively" as a goal-level constraint. Behavior-level fix is system-prompt tuning post-Track-7 #1.

## §F-53. Cache-warm fragility (multi-PC capability adjudication half-deaf)

**Surfaced:** Session 25 #4 (Track 7 #1 live test).
**Context:** Track 7 #1 capability gate returned `(True, "no_character_context")` for all three Jordonovan capability tests because `cache_warm` at startup loaded only Bruce Banner. Same campaign, two bound PCs, only one cached. Capability adjudication was half-deaf: 4/7 categories binding, 3/7 deferred via cache miss.
**Failure mode:** Pre-existing — adjudication just made it observable. `cache_warm` startup logic loaded one PC per campaign at boot; subsequent bound PCs depended on operator-triggered `/refresh` to populate.
**Disposition:** Closed by Track 7 #1.1 (S25 #5) — `cache_autopopulate` fires on `!sheet` post via `on_message` Avrae handler. `cache_warm_incomplete` diagnostic surfaces stale sheets at startup. Capability adjudication promoted from 4/7 to 7/7 binding.

## §F-54. Stagnation drift

**Surfaced:** External LLM review (May 2026), generalizing observed Session 25 patterns into a named failure mode. The diagnostic was sharp; the prescriptive six-ship pivot was rejected (pre-sequenced multi-spec roadmap, anti-pattern per `feedback_no_pre_sequencing.md`). Diagnostic kept; prescription discarded.
**Context:** The architecture-vs-experience gap. The system correctly persists world state, NPCs, locations, combat, and consequences — but does not visibly evolve over a session. Sessions feel good for ~30-60 minutes then drift over longer arcs. Symptoms: scenes don't retire when objectives complete; NPCs linger past their narrative purpose; descriptors recur compulsively (the lute problem, F-52); equal narrative weight on every moment regardless of stakes; absence of visible advancement signals. "Endless present tense" — the world persists but does not move.
**Failure mode:** The architectural floor (Track 7 adjudication, Track 6 directives, persistence, canonical state) ensures the world is internally consistent, but consistency is not the same as motion. The LLM treats every detail as potentially permanent; without explicit motion-system pressure, scenes become immortal, motifs become compulsions, and the campaign loses momentum even when every individual mechanism works correctly. Players forgive a shocking amount if they feel "we are going somewhere"; absence of that feeling is the failure.
**Architectural relationship:** Sits downstream of the structural floor (which Track 7 closes) and upstream of the experience texture (the 15 ChatGPT-S25 #3 texture items filed for finishes-queue). It is the parent failure mode under which scene immortality, motif compulsion (F-52), advancement starvation, and equal-weight narration are subordinate symptoms. Subsumes F-52 as a granular instance — F-52 stays in the catalog for traceability; F-54 is the umbrella diagnostic.
**Disposition:** Filed as the post-footings-queue strategic frontier. Addressing stagnation drift requires motion-system ships (scene lifecycle, time progression, advancement surfacing, compression cadence, motif decay) rather than additional structural primitives. The footings queue closes after Track 7 #2 + Track 6 #4 ship — that checkpoint pivots the work into motion-system territory. Track 4 #3 Time Progression (informed by locked Time-Mention corpus findings doc) is the first post-checkpoint pick; Scene Lifecycle v1 is filed as the second post-checkpoint candidate; subsequent picks re-decide from logs. Cross-references THE_GOAL.md "the world should breathe" and "memorable details should recur intentionally, not compulsively" as authoritative goal-level framing.

## §F-55. Combat playability collapse (solo-DM friction stacking)

**Surfaced:** Post-Track-6-#4 user analysis (May 2026). DM identified combat as functionally unplayable in current state. Three friction surfaces stack: combat entry (DM remembers `!init begin`, players `!init join`, DM adds vague monster groups, picks CR per monster, runs hydrate prompt response), enemy turn (DM picks NPC target and attack, types Avrae syntax, narrates), player turn (DM-as-player remembers own attacks, weapons, spell slots, syntax, applies Avrae commands). Combination breaks the experience even when each individual mechanism works correctly.
**Context:** Track 6 #4 closed the operational stat-hydration gap but exposed the broader combat UX problem — hydration alone makes individual NPCs combat-ready but does not address the cognitive load of running combat solo. The DM is performing four jobs simultaneously: narrative author, mechanical adjudicator, NPC controller, and player. Each command-typing interruption is a cognitive context-switch from narrative flow to mechanical execution. The result: DMs avoid combat (filed as observed), or combat sessions stall mid-fight (filed as observed in S25 #3 multiplayer test where Avrae state desynced from narrative state for ~6 turns).
**Failure mode:** Architecture is correct (three-layer doctrine: Avrae mechanics, Virgil bridge, LLM narrative); UX is collapsed. Mechanical truth lives in Avrae but is not surfaced at decision time. Player character data is cached (post-Track-7-#1.1) but not presented as actionable options on player turns. NPC data is hydrated (post-Track-6-#4) but the bot does not act on it to drive enemy turns. The three layers exist; the connective UX tissue between them does not. Combat plays out as a series of memory-and-syntax exercises rather than a narrative event with mechanical backing.
**Architectural relationship:** F-55 is a UX failure mode at the intersection of three architectural surfaces. Each surface has its own ship in the Combat Playability Cluster (Track 6 #5.1 / 5.2 / 5.3). Closes structurally only when all three cluster ships land — partial closure (e.g., 5.1 shipped, 5.2 and 5.3 deferred) reduces but does not eliminate F-55. Distinct from F-54 (stagnation drift, cross-session pacing) — F-55 is per-fight friction, F-54 is per-session arc decay. They are independent but both filed as post-checkpoint priority candidates.
**Disposition:** Filed as Combat Playability Cluster (Track 6 #5.1 / 5.2 / 5.3 / 5.4) in ROADMAP under Candidate next layers. **Doctrinal pivot locked:** the cluster represents an intentional shift from CLI-faithful Avrae orchestration (player constructs commands) to structured tactical interface (player selects intent; system constructs commands). Doctrine §1 (Avrae owns mechanics) is preserved unchanged — what shifts is the player's surface. Future spec sessions must not drift back toward "let the player type more freely." Cluster has a locked dependency chain: #5.1 (Combat Entry Assist) is independent and ships first if entry-friction is the immediate priority; #5.4 (Intent-to-Avrae Resolver) is the load-bearing primitive that #5.2 (NPC Turn Automation) and #5.3 (Combat Cockpit / Turn Card) both consume; #5.4 must ship before either downstream ship. #5.2 and #5.3 are interchangeable in order once #5.4 lands. Cluster runs in parallel to motion-system thread (Track 4 #3 Time Progression, Scene Lifecycle v1) — neither thread blocks the other. **Affordances-only constraint locked cluster-wide:** Turn Card and resolver list options, never recommend tactical choices. Recommending moves would remove player agency and turn combat into watching the bot play; listing options preserves the tactical decision-making that is the gameplay.

## §F-56. Avrae embed format fragility

**Surfaced:** External architecture review (Gemini, May 2026).
**Context:** `avrae_listener.py` parses third-party Discord embed markdown using regex (e.g., stripping strikethroughs from dropped dice in advantage rolls, extracting combatant HP-status tokens like `<None>` / `<Healthy>`, capturing damage-applied messages). The parser is highly tailored to Avrae's current output format.
**Failure mode:** If Avrae tweaks a single markdown character — adds a separator, moves a field, changes the dice-strikethrough format, alters the init-list embed structure — the parser silently breaks. State sync drops without an error signal. Symptoms surface downstream as "the bot isn't responding to combat" or "init-list isn't classifying correctly" without an obvious cause.
**Architectural relationship:** Distinct from F-49 (LLM-fabricated NPCs) and F-55 (combat playability collapse). This is a third-party-contract fragility — Avrae's output format is not a stable contract, and the parser depends on it as if it were. The Track 6 #4 `status_token` classification rule (§11.M) is particularly exposed: if Avrae changes the `<None>` / `<Healthy>` format, the entire hydration vs `avrae_madd` routing breaks silently.
**Disposition:** Filed for awareness. No fix imminent — current parser works against current Avrae output. Two candidate v1.x mitigations: (1) defensive parsing with multiple format-version checks and a `format_drift_detected` diagnostic log when none match; (2) Avrae-format pinning by version-detecting Avrae's bot version on startup and selecting a parser variant. Neither ships now. Planner-side note: when Avrae ships a major version update, regenerate test fixtures from live output and re-validate all parser paths.

## §F-57. Capability gate fail-open on unknown spells/features

**Surfaced:** External architecture review (Gemini, May 2026), in context of Doctrine §26 ("ever-growing exception lists mean the fix is wrong"). Gemini's prescription (replace regex with LLM-classified intent) was rejected as it would re-introduce the LLM-in-decision-path failure class Track 7 was built to close. The diagnosis was correct; the prescription was wrong. The actual fix is fail-closed gating, not LLM classification.
**Context:** `adjudicator.py`'s `_gate_capability` uses hardcoded keyword sets (`_SPELL_NAMES`, `_CLASS_FEATURES`) to identify spell casts and class-feature invocations for capability gating. The sets are exhaustive for SRD content but do not cover homebrew spells, custom items, or new content not in the keyword lists.
**Failure mode:** An unknown spell name (homebrew, custom item, new published content not yet in the keyword set) falls through the keyword match and is NOT gated by `CAPABILITY_ACTION`. The action is treated as an unrecognized verb and may flow through as a `FREE_ACTION` or a regex fallback. Effectively fail-open: "we don't know what this is, so it's allowed." A player typing "I cast Spirit Surge" (a homebrew spell their character doesn't have) bypasses the capability gate.
**Architectural relationship:** Doctrine §26 names the failure mode — ever-growing exception lists mean the fix is wrong. The capability gate is operating exactly that way: every new content release requires updating the keyword lists, and any gap creates a bypass channel. Doctrine §1a/§1b split (this filing pass) is relevant: §1a forbids LLM in the binding decision, but §1b would permit an LLM-suggester for capability classification IF a deterministic validator gates the output. However, the cleaner architectural fix is fail-closed gating — unknown spell/feature names defer with `refusal_kind='capability_unknown'` instead of falling through.
**Disposition:** Filed for v1.x. Two candidate fixes: (1) Fail-closed gate — when intent is "spell cast" or "feature use" and the named spell/feature is not in the character's cached known list (from Avrae sheet), return INVALID with `refusal_kind='capability_unknown'`; DM can approve via explicit override (analogous to `/setcr` for hydration — DM authority resolves ambiguity). (2) §1b validated-suggester — small LLM call classifies "is this a spell cast?" with structured output; deterministic check against character's spell list validates; if no match, defer with the same `capability_unknown` verdict. Path (1) is the doctrinally cleanest fix (no LLM addition, closes the bypass channel structurally). Path (2) is a fallback if path (1) produces too many false-positive defers under play pressure. Filed as F-57 with both candidate fixes; pick the path at spec time when this becomes a ship.

---

*F-NN numbers are append-only and stable for cross-reference from SESSIONS.md. New failures get added at the end of the list.*
