# NPC_STATE_SYNC_SPEC.md

**Status:** v1.1 — S41 in-session pivot applied. Spec body annotated with the Avrae bot-filter empirical finding and the §1b suggester pivot per operator decision. Original v1 (S40) shape preserved in strike-through / pivot-note callouts; current behavior is the suggester pattern documented inline.

**Owner:** Ship 3 — NPC State-Sync Boundary, per `MULTIPLAYER_FIXES.md` v3 §6. Files as F-55 cluster sibling #5.5 (cluster prerequisite for #5.4 / #5.2 / #5.3).

**Closes:** Finding H (S32 §3.6) — hydrated NPCs have no Avrae sheet; combat against them resolves against `<None>` HP. Mechanical-vs-narrated mismatch (Avrae attacks land on the wrong target while narration describes hits on the intended NPC).

**Architectural shape:** Originally locked in v3 §6 as fix candidate (a): auto-create Avrae sheet via bot-emitted `!init opt` commands under §65a narrow exception. **S41 verify pass surfaced architectural HALT** — Avrae's API silently filters bot-emitted commands while accepting identical human-typed commands. Pivoted in-session to fix candidate (a') — the §1b validated-suggester pattern: bot posts copy-paste command block to `#dm-aside`; DM pastes; Avrae accepts. Engine remains authoritative. §65 holds unchanged (no §65a amendment needed). Ship 3 lands as second project instance of Doctrine §1b (first: Track 6 #5.1 SRD suggester, S26).

> **🔔 S41 in-session pivot summary.** The locked v3 §6 fix shape (a) ("auto-create Avrae sheet on hydrate via bot-emitted commands") was structurally impossible against live Avrae. Empirical: bot-emitted `!init opt ProjTestA -hp 13` delivered to `#dm-narration` (channel.send succeeded), Avrae returned no response, `!init list` still showed `<None>`. Identical command manually pasted by operator produced `"ProjTestA's HP set to 13 (was None)."`. The Avrae bot-filter is structural API behavior (cannot be engineered around without TOS-violating self-botting). Pivoted to fix candidate (a') in-session per operator decision — fully detailed in §13.1. Sections marked `[PRE-PIVOT]` retain v1 (S40) language for archaeology; current behavior is the inline suggester pattern.

---

## §1. Problem statement

### §1.1 Finding H recapped

From `S32_MULTIPLAYER_PLAYTEST_FINDINGS.md` §3.6, captured live during S32 multiplayer playtest:

```
9:31 PM /hydrate: Stats already complete for `Talin` at CR 1/4 — no fields updated.
                  Current: HP 13, AC 13, Atk +3, Dmg 1d8.
9:31 PM /refresh: No Avrae sheet for `Talin` found in this channel.
                  Have the player run `!sheet` here, then try `/refresh` again.
```

Combat then proceeded with broken resolution:

```
9:28 PM Avrae: Karrok unarmed strike → Talin: To Hit 13, Damage 5
              Talin: <None>: Dealt 5 damage!            ← <None> HP, no resolution
9:21 PM Avrae: Donovan unarmed strike → Talin (selected target)
              Karrok The Devourer: <13/15 HP> (-2 HP)   ← landed on Karrok mechanically
              [DM narration] "Your unarmed strike lands solidly on Talin's face..."
                                                       ← narrated as hitting Talin
```

**The split:** the narration layer thinks it's resolving combat against Talin; Avrae has no Talin to resolve against; HP, AC, and damage have no canonical landing point.

**Architectural shape:** `dnd_npcs` is one writer of NPC state (via `/hydrate`, `npc_upsert`, `npc_hydrate_stats`). Avrae is the other writer (via player `!sheet` for PCs, `!init madd` for SRD monsters). There is no bridge between the two writers for **hydrated NPCs** — NPCs that exist in `dnd_npcs` with full stat columns but have no Avrae sheet projection.

### §1.2 Why combat fails

5e combat resolution depends on Avrae owning HP, AC, hit-roll vs target-AC, and damage application. The bot does NOT compute these — per Doctrine §1a, Avrae is the mechanical authority. When Avrae has no sheet for the target NPC:

- `!attack <weapon> -t Talin` either errors ("target not found") or resolves against a `<None>`-HP combatant with undefined AC. Avrae's behavior here is undefined-territory; observed: damage rolls show as "Dealt N damage" but the combatant's HP never decrements (because there's no HP to decrement).
- `!check`-style rolls against the NPC's saves (e.g., a player casts a fear spell that triggers a Wisdom save on Talin) have no resolution — Avrae cannot roll for an NPC it has no sheet for.
- Initiative ordering works (Avrae tracks turn order from `!init add`), but the combatant is mechanically inert.

The mismatch surfaces narratively: the bot narrates a clean attack ("Your blade lands solidly on Talin"), but Avrae's underlying mechanical state shows either the attack landing on the wrong target or no state mutation at all.

### §1.3 Why "fix shape (a)" is the locked path

Three fix candidates were filed in S32 §3.6:
- **(a)** Auto-create Avrae sheet on hydrate via `!init` command sequence; keep stats synchronized.
- **(b)** Combat resolution layer detects "this NPC has dm-aside stats but no Avrae sheet" and resolves against engine-side stats directly, bypassing Avrae for that entity.
- **(c)** Disallow combat against non-Avrae-sheeted entities entirely; force player to manually create sheets before combat.

Per v3 §6 lock: **(a) is the recommended candidate.** Reasoning carried from S32 §3.6:
- (a) is the cleanest UX — combat "just works" once `/hydrate` has run. Operator pays no friction at combat-entry time.
- (b) decouples but introduces a parallel combat resolution path. Two resolution surfaces (Avrae for PC-vs-PC, engine for vs-hydrated-NPC) is a §17 violation — the LLM and validators would need to know which resolution path applies, and the mode-disjoint discipline that works for `last_active_actor` doesn't generalize cleanly here.
- (c) is brutally consistent but breaks the existing solo-play flow where DMs use `/hydrate` heavily.

(a) preserves the Virgil-authoritative-with-Avrae-as-projection trajectory locked across the F-55 cluster (per ROADMAP Combat Playability Cluster section). Engine owns canonical NPC state; Avrae is the projection surface where mechanics resolve. Ship 3 closes the projection seam.

---

## §2. Architectural shape (locked per v3 §6)

### §2.1 Single-writer-with-projection

`dnd_npcs` remains the canonical writer for NPC state (HP, AC, attack_bonus, damage_dice, save_bonus, init_mod, cr_str). Avrae becomes the **projection target**: the bot translates the engine row into a sequence of `!init` commands that creates a combatant Avrae will accept as a valid attack target.

The projection writer is a single helper in `discord_dnd_bot.py` (proposed name `avrae_project_npc`) called from disjoint trigger surfaces. The helper is the single writer; the triggers invoke it. This is structurally compatible with §17 (single write paths per field) per the candidate Doctrine C3 framing — Ship 3 may be C3's second project instance, promoting it to numbered doctrine. See §12.2.

### §2.2 Two disjoint trigger surfaces

**Trigger 1: `_handle_init_list_event` hydration branch.** When Avrae fires `!init list` and the parser surfaces a combatant with `status_token == '<None>'` (DM-added via `!init add` without `-h`) AND the NPC has full hydrated stats in `dnd_npcs` (via prior `/hydrate` or skeleton-driven hydration), the projection writer fires to overwrite the `<None>` HP with the engine's stats.

**Trigger 2: `/hydrate` slash command.** When the DM runs `/hydrate npc:<name> cr:<N>`, the projection writer fires post-engine-write IFF the NPC is currently in initiative (i.e., present in `dnd_combatant_state` for this campaign). If the NPC is NOT in init at hydrate time, the projection deferred to Trigger 1 (when `!init list` later fires after `!init add <NPC>`).

Both triggers converge on the same writer-helper. The triggers don't race (different code paths, no shared mutable state). Idempotency is enforced at the projection-writer layer: if the combatant is already mechanically-complete in Avrae (HP and AC both set), the writer no-ops with a log line.

### §2.3 Engine remains authoritative

Avrae is the projection surface, not the authority. If `/hydrate` is run twice with different CR values (operator corrects an earlier mistake), the engine row overwrites (always-overwrite per `explicit_hydrate` source semantics, dnd_engine.py:3146); the projection writer then re-fires `!init opt` to bring Avrae into line with the engine's new values. There is no merge logic — engine wins.

### §2.4 Bot-as-DM-proxy narrow exception

The projection writer emits `!init`-family commands as the DM. This is a narrow exception to Doctrine §65 ("Bot-Avrae write boundary" — bot does NOT emit `!`-prefixed commands). See §3 for the amendment's exact scope.

### §2.5 Recon-surfaced sub-decisions (no shape break)

- **D1**: exact Avrae command sequence (`!init add` flags vs `!init opt` follow-up vs `!init madd` with stub-monster-name → opt-edit). Recon found this is implementation-time uncertain; surfaced as §11 decision pending live verify.
- **D2**: projection trigger timing (`/hydrate` time vs `_handle_init_list_event` time vs both). Recon recommends BOTH triggers feed the single writer; idempotency guard at the writer layer prevents double-fire. Surfaced as §11 decision.
- **D3**: failure-mode handling (Avrae projection fails — engine row stays valid, projection retries on next `!init list`? Or `/hydrate` rolls back engine write?). Recon recommends engine stays as-written; projection failures log + retry on next trigger; no engine rollback. Surfaced as §11 decision.

---

## §3. Doctrine §65 amendment

### §3.1 Current §65 (DOCTRINE.md, anchored S22 #1)

> §65. Bot-Avrae write boundary
> **Doctrine:** Avrae is the sole authority for mechanics. Virgil is the mechanics-consumer, not a mechanics-mirror. The bot does NOT emit `!`-prefixed commands. LLMs can emit them (in narration responses, for the player to copy or as suggestions); the bot side never does. This is a load-bearing invariant in VIRGIL_MASTER §4.

### §3.2 [PIVOTED — §65a amendment NOT anchored]

**S41 pivot:** the §65a amendment is **no longer needed**. The pivot to the §1b suggester pattern preserves §65 in its original form — the bot does not emit `!`-prefixed commands to Avrae's channel. The suggester posts a copy-paste block to `#dm-aside`; the DM pastes the commands; Avrae responds to the human-typed input. No bot-as-DM-proxy mechanism is introduced.

The pre-pivot amendment text below is preserved for archaeology / context for any future ship that revisits the question:

> **[PRE-PIVOT, NOT ANCHORED] §65a (Ship 3 amendment, S40+). Narrow exception: bot-as-DM-proxy for NPC state projection.**
>
> The bot is licensed to emit `!init`-family commands as the DM **only** to project engine-canonical NPC state onto Avrae's combatant store so combat resolution against hydrated NPCs is mechanically valid. The exception is bounded by:
>
> 1. **Single writer surface:** `avrae_project_npc()` in `discord_dnd_bot.py` is the sole bot-emit entry point. No other code path in the bot emits `!`-prefixed commands.
> 2. **Command scope:** `!init add`, `!init opt`, and (if implementation-time recon surfaces a need) `!init madd` with stub-monster + override. NO `!attack`, NO `!cast`, NO `!check`, NO non-init-family commands.
> 3. **Trigger scope:** only from `/hydrate` (post-engine-write) and `_handle_init_list_event` (hydration branch, when status_token is `<None>` for a hydrated NPC). No other trigger surface.
> 4. **DM-authored intent preserved:** every emission corresponds to an action the DM already initiated.

**Reason §65a is moot post-pivot:** the suggester pattern routes all bot output to `#dm-aside` (a non-Avrae channel by design — Avrae doesn't listen there). The bot never emits `!`-prefixed text to a channel Avrae would parse. The original §65 doctrine ("bot does NOT emit `!`-prefixed commands") holds unchanged because the suggester's emission is a code-block render to `#dm-aside`, not a `!`-command dispatched to Avrae. **No amendment to anchor.**

### §3.3 Why this is narrow, not a hole

The §65a exception preserves §65's load-bearing property: **the bot does not make mechanical decisions.** Avrae still owns hit determination, damage application, save adjudication, condition tracking. The projection writer is a state-sync mechanism — it takes the engine's canonical NPC state and writes it into Avrae's storage so Avrae has what it needs to resolve mechanics. The bot is the courier; Avrae remains the judge.

This is the same architectural shape as Ship 1 + Ship A's resolution binding: the engine computes the canonical answer (in Ship 1/A: pass/fail; here: NPC state), and renders/projects it onto the surface that consumes it (in Ship 1/A: LLM prompt; here: Avrae combatant store). The cross-reference reinforces the cluster trajectory (Virgil-authoritative-with-Avrae-as-projection).

### §3.4 Anchoring vs. filing

The §65 amendment anchors when Ship 3 ships and live-verify is clean. It lands as a §65a subsection of the existing §65 entry in DOCTRINE.md, not a new §-number. Drafting the text now (above) so the anchor pass at Ship 3 doc-update can lift it verbatim.

---

## §4. Doctrine §76 audit on dnd_npcs

Per Doctrine §76's operational discipline ("every new persisted scalar column undergoes a manual four-property check at add time"), Ship 3 audits every persisted scalar in `dnd_npcs`. The four-property test:

1. **LLM-writable** (non-gated write path)
2. **Persisted** (outlives the turn)
3. **Retrieved** (read back into LLM prompt context)
4. **Narratively inferential** (rendered value invites narrative elaboration)

Hit-count column meanings:
- **4/4** = §76 deletion candidate (or gated-write conversion if hard-dependency)
- **3+1** = three hard hits + one borderline; flag with rationale, KEEP
- **≤ 3/4** = no action

### §4.1 dnd_npcs audit table

| # | Column | LLM-writable | Persisted | Retrieved | Narratively inferential | Hits | Recommendation |
|---|--------|:---:|:---:|:---:|:---:|:---:|---|
| 1 | `id` | ❌ | ✅ | partial (FK target) | ❌ | 1-2/4 | KEEP (PK) |
| 2 | `campaign_id` | ❌ | ✅ | partial (scoping) | ❌ | 1-2/4 | KEEP (FK) |
| 3 | `canonical_name` | ⚠️ gated via `npc_upsert` (skeleton-protect + canonicalize) | ✅ | ✅ (`get_recently_active_npcs` surfaces names) | ✅ (LLM elaborates on NPC name) | **3+1** | KEEP — non-gated property fails; write path is the §17-disciplined `npc_upsert` helper with skeleton_origin protection |
| 4 | `aliases` | ⚠️ gated via `npc_upsert` | ✅ | ❌ (not retrieved into prompt — used internally for name resolution) | ⚠️ (LLM could elaborate if retrieved) | 1-2/4 | KEEP — property 3 fails |
| 5 | `role` | ⚠️ gated via `npc_upsert` (parser hits) | ✅ | ❌ (not in build_dm_context scene-state-section; not currently surfaced in any LLM prompt block per recon) | ✅ | 2-3/4 | KEEP — property 3 fails |
| 6 | `location_id` | ❌ FK (gated via `npc_upsert` / location parser) | ✅ | partial (scopes NPC retrieval) | ❌ (FK integer) | 2/4 | KEEP |
| 7 | `description` | ⚠️ gated via `npc_upsert` with skeleton_origin protection | ✅ | ❌ (chroma-indirect only; not retrieved into SCENE STATE block) | ✅ | 2-3/4 | KEEP — chroma-side retrieval is filed candidate per Ship 2 §6.3 / §13 item 3 (chroma-layer audit), not in Ship 3 scope |
| 8 | `skeleton_origin` | ❌ (set by `npc_upsert` via `skeleton_origin=True` kwarg from `skeleton_loader.apply_skeleton`) | ✅ | ❌ | ❌ (flag) | 1/4 | KEEP |
| 9 | `mention_count` | ❌ (incremented by `npc_upsert` parser path) | ✅ | ❌ (used to rank `get_recently_active_npcs`; not surfaced to LLM directly) | ❌ (counter) | 1/4 | KEEP |
| 10 | `origin_excerpt` | ⚠️ gated via `npc_upsert`, capped at 100 chars | ✅ | ❌ (not in any current prompt block) | ✅ (free-text fragment) | 2-3/4 | KEEP — property 3 fails |
| 11 | `first_mentioned` | ❌ (set by `npc_upsert` on INSERT) | ✅ | ❌ | ❌ (timestamp) | 1/4 | KEEP |
| 12 | `last_mentioned` | ❌ (bumped by `npc_upsert` on parser hit) | ✅ | partial (sorts `get_recently_active_npcs`) | ❌ (timestamp) | 1-2/4 | KEEP |
| 13 | `hp_max` | ⚠️ gated via `npc_hydrate_stats` (sources: skeleton/hook/adhoc/generic_fallback/explicit_hydrate) | ✅ | ❌ (consumed by Ship 3's projection writer, not LLM prompt) | ❌ (integer) | 1-2/4 | KEEP — Ship 3 projection writer is the consumer; LLM doesn't read this scalar |
| 14 | `ac` | ⚠️ gated via `npc_hydrate_stats` | ✅ | ❌ (Ship 3 projection consumer) | ❌ (integer) | 1-2/4 | KEEP |
| 15 | `attack_bonus` | ⚠️ gated via `npc_hydrate_stats` | ✅ | ❌ | ❌ (integer) | 1-2/4 | KEEP |
| 16 | `damage_dice` | ⚠️ gated via `npc_hydrate_stats` | ✅ | ❌ | ❌ (mechanical dice notation) | 1-2/4 | KEEP |
| 17 | `save_bonus` | ⚠️ gated via `npc_hydrate_stats` | ✅ | ❌ | ❌ (integer) | 1-2/4 | KEEP |
| 18 | `init_mod` | ⚠️ gated via `npc_hydrate_stats` | ✅ | ❌ | ❌ (integer) | 1-2/4 | KEEP |
| 19 | `cr_str` | ⚠️ gated via `npc_hydrate_stats` | ✅ | partial (rendered to DM via /hydrate response, not into LLM prompt) | ❌ (CR-band token) | 1-2/4 | KEEP |
| 20 | `avrae_source` | ⚠️ gated via `npc_register_avrae_madd` | ✅ | ❌ | ❌ (enum-like flag: `avrae_madd` or NULL) | 1/4 | KEEP |

### §4.2 Audit summary

**No 4/4 hits on dnd_npcs.** Every column is either:
- Gated through a `§17` single-writer helper (`npc_upsert`, `npc_hydrate_stats`, `npc_register_avrae_madd`, or — newly added in Ship 3 — `avrae_project_npc`); OR
- Not narratively inferential (FK, integer, timestamp, enum-like flag).

The strongest borderline is **`canonical_name`** at 3+1: it's written via `npc_upsert` (gated with skeleton_origin protection + canonicalize_name normalization + near-match diagnostic), persisted, retrieved (`get_recently_active_npcs` returns canonical names into the SCENE STATE block recently-active-NPCs line), and narratively inferential (the LLM elaborates on NPC names). The gating makes property 1 partial; the protection regime (skeleton-origin rows never overwritten; new rows require canonicalize_name to pass; near-match diagnostic logged) is the §17 discipline at full strength. **KEEP with the gated-write-helper as the §76-compatible structure.**

The next-tier candidates (`description`, `origin_excerpt`, `role`) fail property 3 (retrieval). They could become §76 candidates IF a future ship adds a "NPC profile block" that surfaces these into LLM prompt context. Filed for future audit re-run if such a ship surfaces — same operational discipline as the spec §6.4 note from Ship 2.

### §4.3 §76 doctrine carries forward cleanly

The §76 anchored phrasing (DOCTRINE.md, anchored S39) is table-agnostic: it applies to "any persisted scalar field." Ship 3's audit confirms no refinement is needed for dnd_npcs — the four-property test produced clean classifications without ambiguity.

**No fourth project instance from Ship 3 audit.** §76's three project instances (S22 #2 chroma / S32 location / S36 time-of-day) remain canonical. Ship 3 adds operational confirmation that the doctrine generalizes, but doesn't ship a fourth schema-level deletion.

---

## §5. Avrae projection SUGGESTER (post-pivot)

### §5.1 Function signature and contract (post-pivot S41)

```python
async def _avrae_project_npc(
    channel,           # used only for guild lookup → #dm-aside resolution
    campaign_id: int,
    npc_name: str,
    trigger: str,      # 'hydrate' or 'init_list'
) -> tuple[bool, dict]:
    """Suggest the Avrae command sequence the DM needs to paste to sync
    a hydrated NPC's stats. §1b validated-suggester pattern.

    Reads dnd_npcs canonical state, queries dnd_combatant_state for
    current Avrae mirror, posts a copy-paste suggestion to #dm-aside if
    projection would be useful (and safe). DM pastes the commands manually;
    Avrae accepts (responds to human-typed commands, filters bot-typed).

    Returns (acted, signals):
      acted=True when a suggestion was posted to #dm-aside.
      signals['reason'] ∈ {
          'suggested', 'suggested_with_warning',
          'noop_complete', 'gate_not_in_init',
          'gate_engine_missing', 'gate_engine_stats_null',
          'aside_post_failed'
      }
      signals also carries 'hp', 'ac', 'commands_suggested' (list of
      strings — what the DM pastes) when reason in {'suggested',
      'suggested_with_warning'}.

    Function name preserved from the pre-pivot bot-writer shape to
    minimize call-site churn. Behavior is suggester-pattern per S41.
    """
```

### §5.2 Locked command syntax (per S41 D1 verify pass)

- **`!init opt <name> -hp <N>`** — sets max HP. `-h` is Avrae's hidden-toggle shorthand (NOT HP); emitting `-h 13` silently hides the combatant instead of setting HP (S41 verify-pass empirical finding).
- **`!init opt <name> -ac <N>`** — sets AC.

The DM pastes each command as a separate Discord message. Avrae's parser cannot consume back-to-back commands inside a single code block — the operator confirmed this empirically in the S41 D1 verify pass ("you can't do blocks").

### §5.3 Idempotency guard (gates + Case A/B split)

The helper short-circuits on each precondition before posting:

- **Case 1 — `gate_engine_missing`**: NPC absent from `dnd_npcs`. Log + no suggestion.
- **Case 2 — `gate_engine_stats_null`**: NPC exists but hp_max OR ac is NULL. Log + no suggestion (DM should `/hydrate` with a CR first).
- **Case 3 — `gate_not_in_init`**: NPC fully stat'd in engine but not in `dnd_combatant_state`. Log + no suggestion. The DM hasn't `!init add`'d this NPC; nothing to sync.
- **Case 4 (Case B) — `noop_complete`**: NPC in init with numeric HP (`<X/Y>` token), trigger='init_list' (passive). **Critical:** Avrae's mid-combat HP is authoritative; do NOT post a re-sync suggestion — that risks DM accidentally pasting and resetting hp_current.
- **Case 5 (Case A) — `suggested_with_warning`**: NPC in init with numeric HP, trigger='hydrate' (active operator re-hydrate). Post warning aside with command sequence + explicit HP-reset risk callout + alternative path (`!init remove` + re-add).
- **Case 6 (happy path) — `suggested`**: NPC in init with `<None>` status, engine fully stat'd. Post the standard sync suggestion (no warning).
- **Case 7 — `aside_post_failed`**: posting to `#dm-aside` raised an exception OR `#dm-aside` channel not found. Log + return failure. Engine row remains canonical; DM can manually sync.

### §5.4 Telemetry contract

Every invocation emits exactly one of:
- `avrae_projection_attempted: campaign={N} npc='...' trigger={...} commands=2`
- `avrae_projection_succeeded: campaign={N} npc='...' trigger={...} reason={suggested|suggested_with_warning} hp={N} ac={N} commands=2`
- `avrae_projection_failed: campaign={N} npc='...' trigger={...} reason=aside_post_failed error={...}`
- `avrae_projection_skipped: campaign={N} npc='...' trigger={...} reason={noop_complete|gate_not_in_init|gate_engine_missing|gate_engine_stats_null}`

### §5.5 What the suggester does NOT do (post-pivot)

- **Does NOT emit `!`-prefixed commands to any channel.** Suggestions are rendered as code blocks in `#dm-aside`; Avrae doesn't read `#dm-aside` and would silently filter them anyway. §65 holds unchanged.
- **Does NOT auto-retry.** If the suggestion is posted but the DM ignores it, that's a workflow signal — combat will surface the missing-sync via Avrae's `<None>` HP. Avrae's next `!init list` snapshot re-triggers the suggester via `_handle_init_list_event` (Case B no-ops if Avrae now has numeric HP; otherwise re-suggests).
- **Does NOT confirm Avrae accepted the DM's paste.** Confirmation happens at the next `!init list` event's parse, which `update_combatants_from_init_list` writes into `dnd_combatant_state`. The suggester's Case B no-op gate uses that state as the "already-synced" signal.

### §5.2 Locked command sequence (D1 decision)

**Recommended default (D1):** two-command sequence at projection time.

1. `!init opt <npc_name> -h <hp_max>` — set max HP on the existing combatant.
2. `!init opt <npc_name> -ac <ac>` — set AC.

**Why `!init opt` and not `!init add` / `!init madd`:**
- Trigger 1 (`_handle_init_list_event` hydration branch) fires AFTER the DM has already added the NPC via `!init add <init> <name>`. The combatant exists; we just need to enrich its stats. `!init opt` modifies an existing combatant.
- Trigger 2 (`/hydrate` post-write) only projects IF the NPC is currently in init (idempotency guard). Same precondition: combatant exists; `!init opt` modifies.
- `!init add` would create a duplicate combatant. `!init madd` requires an SRD monster name match; our hydrated NPCs are CR-band approximations with custom names that won't match SRD.

**Implementation uncertainty (verify-at-implementation):** `!init opt` accepts `-h` and `-ac` flags per Avrae public docs; the exact CLI syntax (e.g., whether the flags need a separator, whether multiple flags can be combined in one command) needs live verify at S41 implementation. The spec locks the architectural shape; the exact flag string is a verify-pass refinement.

**Fallback if `!init opt` doesn't carry attack stats:** Avrae resolves attacks against NPCs using either explicit attack actions on the sheet OR a default unarmed-strike fallback. CR-band hydrated NPCs use the `damage_dice` column for attack damage; this needs `!init opt <name> -attack <name>|<bonus>|<dmg>` if Avrae supports it. **Verify at implementation.** If `!init opt` cannot carry attack stats, the fallback is to accept that attack-against-NPC produces a basic to-hit roll against AC + uses Avrae's default damage; the engine row continues to be the canonical source for attack_bonus/damage_dice should a future #5.2 NPC Turn Automation ship need them.

### §5.3 Idempotency guard

Before emitting any command, the writer reads `dnd_combatant_state` for the campaign (via existing `get_combatants_snapshot` helper or direct SELECT). For the target NPC name:

- **Case 1 — NPC not in combatant_state.** Precondition fails (`gate_not_in_init`). Writer no-ops. The NPC will be picked up by Trigger 1 when next `!init list` parses.
- **Case 2 — NPC in combatant_state, `status_token == '<None>'` and `hp_max IS NULL`.** Projection target. Writer emits the locked command sequence. Logs `avrae_projection_attempted:` then `avrae_projection_succeeded:` or `avrae_projection_failed:`.
- **Case 3 — NPC in combatant_state, `hp_max IS NOT NULL` (numeric status token).** Already mechanically complete. Writer no-ops (`noop_complete`).
- **Case 4 — NPC in combatant_state but engine has NULL stats.** Precondition fails (`gate_engine_stats_null`). Cannot project what isn't there. This shouldn't happen in normal flow (hydration always runs first) but is a defensive case.

### §5.4 Failure-mode handling (D3 decision)

**Recommended default (D3):** engine write stays as-written; projection failures log and retry on next trigger.

If the Avrae emission fails (e.g., channel send raises, or Avrae returns an error embed):
- Engine row is NOT rolled back. Engine state remains canonical.
- Log line `avrae_projection_failed: campaign={N} npc='...' reason={...}`.
- On the next `!init list` event for this campaign, Trigger 1 re-fires the projection writer; the idempotency guard either skips (if a manual fix restored stats) or retries (if still `<None>`).
- The DM has visibility via `#dm-aside` — failures surface a one-line aside (`avrae_projection_failed_aside`) so the DM knows mechanical state is split and can intervene.

**Rejected alternative (D3-rollback):** rolling back engine state on Avrae projection failure couples two writers' success/failure and introduces a partial-write window where engine + Avrae are both empty. The current shape preserves engine as canonical even when projection lags — Avrae catches up on next trigger.

### §5.5 Telemetry contract

The writer always fires one of these log lines per invocation:
- `avrae_projection_attempted: campaign={N} npc='...' trigger={hydrate|init_list}`
- `avrae_projection_succeeded: campaign={N} npc='...' hp={N} ac={N} commands={count}`
- `avrae_projection_failed: campaign={N} npc='...' reason={...} error={...}`
- `avrae_projection_skipped: campaign={N} npc='...' reason={noop_complete|gate_not_in_init|gate_engine_stats_null|gate_engine_missing}`

See §10 for full telemetry contract.

---

## §6. `/hydrate` integration

### §6.1 Current state (S39 baseline)

`/hydrate npc:<name> cr:<N>` (discord_dnd_bot.py:5201):
- DM-only authority gate.
- Validates CR via `npc_hydrator.normalize_cr`.
- Calls `npc_hydrate_stats(campaign_id, canonical, cr_str=normalized, source='explicit_hydrate')` → engine writes stats (always-overwrite).
- Clears `_pending_hydration` set entry.
- Posts ephemeral confirmation to the DM with the new stats.

### §6.2 Ship 3 integration

After the engine write succeeds and before the ephemeral confirmation, the `/hydrate` handler calls:

```python
projected, projection_signals = await avrae_project_npc(
    interaction.channel,
    campaign_id,
    canonical,
)
```

The ephemeral confirmation extends to include projection status:

- `projected=True`: `"Hydrated <name> at CR <N>: HP X, AC Y, Atk +Z, Dmg D. Avrae sheet synced."`
- `projected=False, reason=noop_complete`: `"Hydrated <name> at CR <N>: HP X, AC Y, ... Avrae sheet already in sync."`
- `projected=False, reason=gate_not_in_init`: `"Hydrated <name> at CR <N>: HP X, AC Y, ... Not in init — Avrae sheet will sync on !init add."`
- `projected=False, reason=avrae_emit_failed`: `"Hydrated <name> at CR <N>: HP X, AC Y, ... Avrae sync FAILED — check #dm-aside."`

### §6.3 Channel argument

The projection writer emits to a channel where Avrae listens. Recon: Avrae listens in `#dm-narration` (the primary narration channel) per `_handle_init_event` and `_handle_init_list_event` setup. The writer should emit to `#dm-narration` (NOT `#dm-aside`, which is read-only-by-Avrae).

**Channel-resolution helper:** the existing `get_channel(interaction.guild, 'narration')` helper at discord_dnd_bot.py returns the canonical narration channel. The projection writer takes the channel as an argument (passed in by the trigger) rather than resolving internally — keeps the writer pure-ish and testable.

### §6.4 Edge cases for `/hydrate` trigger

- **NPC not in `dnd_npcs`:** existing `/hydrate` flow already errors with "NPC `<name>` not found in this campaign." No projection attempt.
- **NPC in `dnd_npcs` but stats incomplete after explicit_hydrate:** shouldn't happen (explicit_hydrate is always-overwrite); defensive `gate_engine_stats_null` covers it if it does.
- **NPC fully hydrated but not in init:** projection writer no-ops (`gate_not_in_init`); DM informed via ephemeral message.
- **NPC in init but combatant_state stale (last `!init list` was hours ago):** the writer reads `dnd_combatant_state`, which is replace-in-place per snapshot. If stale, the writer may attempt projection on a combatant Avrae no longer has. Avrae will return an error embed; the failure path catches it. Acceptable behavior; the next `!init list` snapshot refreshes state.

---

## §7. `_handle_init_list_event` hydration-branch integration

### §7.1 Current state (S39 baseline)

The hydration branch (discord_dnd_bot.py:1396-1430) currently:
1. Iterates combatants from the parsed `!init list` snapshot.
2. For each non-bound non-Avrae-tracked combatant (status_token == `<None>`):
   - If stats complete in dnd_npcs: `source=miss` log, continue.
   - If stats incomplete + no cr_hint: post hydration prompt to `#dm-aside`, then `npc_hydrate_stats` with `source=generic_fallback`.
   - If stats incomplete + cr_hint exists: `npc_hydrate_stats` with `source=skeleton` or `source=hook`.

### §7.2 Ship 3 integration

After every `npc_hydrate_stats` call AND for the `source=miss` path (already-complete), call `avrae_project_npc(channel, campaign_id, cbt_name)`.

Trigger-context: pass `trigger='init_list'` to the projection writer (vs `trigger='hydrate'` from the slash command path) for telemetry.

The projection writer's idempotency guard handles the case where Avrae already has stats (e.g., a prior `!init list` already triggered projection, the row is `<13/15>`, projection no-ops). The duplicate-trigger pattern is acceptable per the C3 candidate framing — the single writer absorbs both surfaces.

### §7.3 Why project on every parsed combatant, not just newly-hydrated ones

The `source=miss` path (NPC already fully hydrated in engine, no new write) MIGHT not have a corresponding Avrae sheet — e.g., DM ran `/hydrate` long ago, then started combat much later, NPC is in init with `<None>` HP. The hydration code-path's old behavior (S39 baseline) was to no-op on `source=miss`. Ship 3 extends this: even on miss, fire the projection writer to check if Avrae needs to catch up.

The writer's `noop_complete` path (Case 3 in §5.3) absorbs the case where Avrae is already in sync.

### §7.4 Failure handling at the init_list trigger

Same as `/hydrate`: engine row unchanged; projection failure logs + posts `#dm-aside` notification; next `!init list` retries via Trigger 1 again.

The init_list trigger fires more often than `/hydrate` — every Avrae `!init list` parse — so the retry cadence is naturally high. Most projection failures resolve on the next combat turn's `!init list` snapshot.

---

## §8. Test plan

### §8.1 New tests

**`test_avrae_project_npc.py`** (new file, ~25 assertions):
- Idempotency: project once with NPC in init, fully complete; second call returns `noop_complete`.
- Gate paths: each of `gate_not_in_init`, `gate_engine_stats_null`, `gate_engine_missing` returns the right reason + emits no commands.
- Command emission: with NPC in init at `<None>` HP and engine stats present, writer emits the locked sequence (mock the channel.send to capture emitted strings).
- Failure path: simulate channel.send raising; writer logs `avrae_projection_failed:` and returns `(False, {'reason': 'avrae_emit_failed', ...})`.
- Telemetry coverage: every code path emits exactly one log line per call.

**Test extensions:**

**`test_npc_hydrate_stats.py` (+~10 assertions):**
- Trigger sequencing: after `npc_hydrate_stats` writes, verify the projection writer is NOT auto-called from the engine layer (separation of concerns — projection is bot-layer only). This test asserts the engine helper remains pure-write with no Avrae side effects.

**`test_npc_hydrator.py` (+~5 assertions):**
- Pure-function test; no Ship 3 surface. May add an assertion that `hp_max` and `ac` are returned for every CR band (they already are; sanity check the projection-writer's inputs).

**`test_doctrine_76_dnd_npcs_audit.py`** (new file, ~15 assertions; per-table regression test sibling to Ship 2's `test_doctrine_76_four_property_audit.py`):
- Enumerate every `dnd_npcs` column.
- Classify each against the four properties using the audit table from §4.1 as the EXPECTED_CLASSIFICATION lookup.
- Assert no column hits 4/4 post-Ship-3 (matches Ship 2's discipline).
- Assert deleted-column absence (N/A here — Ship 3 doesn't delete columns; assertion is "no surprise columns added since spec").

### §8.2 Existing test fixture updates

- `test_npc_hydrate_stats.py` fixtures: no changes needed; engine helper still pure.
- `test_npc_register_avrae_madd.py` fixtures: no changes needed; `npc_register_avrae_madd` is on the !init madd path, unaffected by Ship 3.

### §8.3 Integration test (live-only)

Per §9, the trigger-integration path (`/hydrate` → projection writer → Avrae) requires Discord + Avrae running. Cannot be unit-tested at the engine layer. The live-verify scenarios in §9 are the integration coverage.

---

## §9. Live-verify scenarios

### Scenario A — Solo: `/hydrate` then `!init add` then attack (clean path)

**Setup**: a campaign with an existing NPC stub (e.g., `Talin` from S32 evidence) created by prior narration parser hit. NPC has no stats in `dnd_npcs` (hp_max IS NULL).

**Discord prompts:**
```
/hydrate npc:Talin cr:1/4
```
**Expected (post-/hydrate):**
- Ephemeral: `"Hydrated Talin at CR 1/4: HP 13, AC 13, Atk +3, Dmg 1d8. Not in init — Avrae sheet will sync on !init add."`
- Engine row: hp_max=13, ac=13, attack_bonus=3, damage_dice='1d8', save_bonus=2, init_mod=1, cr_str='1/4'.
- No Avrae emission yet.
- Log: `avrae_projection_skipped: ... reason=gate_not_in_init`.

```
!init begin
!init add 11 Talin
```
**Expected (Avrae returns confirmation, fires `!init list`):**
- `_handle_init_list_event` parses, sees `Talin` with `status_token='<None>'`.
- Engine stats present → `source=miss` (no new engine write).
- Projection writer fires: emits `!init opt Talin -h 13` then `!init opt Talin -ac 13`.
- Avrae returns updated combatant: `Talin <13/13>`.
- Next `!init list` snapshot stores numeric HP in `dnd_combatant_state`.
- Logs: `avrae_projection_attempted: ... trigger=init_list`, `avrae_projection_succeeded: ... hp=13 ac=13 commands=2`.

```
!attack unarmed strike -t Talin
```
**Expected:**
- Avrae resolves the attack against Talin (now mechanically valid).
- Hit/miss determined by to-hit roll vs ac=13.
- On hit, damage applies to Talin's HP (decrements from 13).
- Subsequent `!init list` shows Talin's reduced HP.
- The narrated bot output describes hitting Talin AND Avrae's mechanical state shows HP decrement. No mismatch.

**Failure signal:** Talin still shows `<None>` HP in `!init list` after the projection writer claims success; OR attack against Talin lands on the wrong target mechanically (Karrok or another combatant).

**Grep:**
```bash
grep "avrae_projection_" /mnt/virgil_storage/digest/dnd_engine.log | tail -10
```

### Scenario B — `/hydrate` while already in init

**Setup**: NPC already in init via `!init add 11 Goblin` (status_token=`<None>`, no engine stats yet).

**Discord prompts:**
```
/hydrate npc:Goblin cr:1/4
```
**Expected:**
- Engine writes stats.
- Projection writer detects NPC in `dnd_combatant_state` with `<None>` token.
- Emits `!init opt Goblin -h 13 -ac 13` sequence.
- Ephemeral: `"Hydrated Goblin at CR 1/4: HP 13, AC 13, Atk +3, Dmg 1d8. Avrae sheet synced."`
- Logs: `avrae_projection_attempted: ... trigger=hydrate`, `avrae_projection_succeeded: ...`.

**Failure signal:** Avrae still shows `<None>` after `/hydrate` returns.

### Scenario C — Idempotent re-hydrate

**Setup**: After Scenario A or B, NPC fully synced.

**Discord prompts:**
```
/hydrate npc:Talin cr:1
```
(Different CR than original — operator correcting an undersized NPC.)

**Expected:**
- Engine row overwrites: hp_max=35, ac=13, attack_bonus=5, damage_dice='2d6+3' (CR 1 band).
- Projection writer detects NPC in init at `<13/13>` (Case 3 might apply — but stats are now different from engine).
- **D2 sub-decision: should re-projection fire when Avrae HP and engine HP diverge?** Recommended: YES. The writer queries engine stats vs Avrae stats; on mismatch, re-emits. Refines the idempotency guard. Surfaced as §11.D2 sub-decision.
- Updated Avrae state: `Talin <35/35>` with AC 13.
- Logs: `avrae_projection_attempted: ... trigger=hydrate`, `avrae_projection_succeeded: ... hp=35 ac=13 commands=2`.

**Failure signal:** old CR-1/4 stats persist on Avrae sheet after re-hydrate.

### Scenario D — Multi-player combat with hydrated NPC (Captin0bvious available)

**Setup**: Two-PC campaign (Jordan = Donovan, Captin0bvious = Karrok). DM has `/hydrate`-d Talin via Scenario A flow. Both PCs initiated combat, Avrae rolls init for everyone.

**Discord prompts (Jordan):**
```
!attack unarmed strike -t Talin
```

**Discord prompts (Captin0bvious):**
```
!attack longsword -t Talin
```

**Expected:**
- Both attacks resolve against the same Avrae combatant (Talin with HP/AC).
- Damage applies sequentially; HP decrements; eventually Talin defeated.
- Narration describes hits on Talin consistently with Avrae's mechanical state.
- No `<None>` HP outputs. No mechanical-vs-narrated mismatch.

**Failure signal:** S32-style mismatch returns (narration describes hitting Talin, Avrae HP decrements on Karrok or shows `<None>`).

### Scenario E — Projection-writer failure path

**Setup**: Engineer-only test (intentionally trigger Avrae error). Difficult to reproduce naturally; consider deferring to engineering walk. Operator may skip this scenario unless they want belt-and-suspenders coverage.

**Trigger**: send a malformed `!init opt` (e.g., via a debug command that bypasses the projection writer's syntax assembly), confirm Avrae returns an error embed.

**Expected:**
- Log: `avrae_projection_failed: ... error=...`.
- `#dm-aside` posts: `"Avrae sync failed for <NPC>: <error summary>. Engine stats still canonical; re-trigger via next !init list."`
- Engine row unchanged.
- Next `!init list` retries; succeeds (assuming the malformed-command issue doesn't repeat).

**Failure signal:** silent failure (no log, no aside) OR engine row gets rolled back.

### Scenario F — Bound PC immunity

**Setup**: Bound PC `Donovan Ruby` is in init.

**Expected:**
- `_handle_init_list_event` already skips bound PCs via the `bound_names` check (discord_dnd_bot.py:1404). Projection writer never fires for bound PCs.
- Log: `hydration: ... source=bound_pc_skip` (existing log line).

**Failure signal:** projection writer fires for a bound PC, attempts to overwrite the PC's actual Avrae sheet with CR-band stats. **CRITICAL FAILURE if this happens** — would corrupt player sheets.

---

## §10. Telemetry

### §10.1 New log lines

- `avrae_projection_attempted: campaign={N} npc='...' trigger={hydrate|init_list}`
- `avrae_projection_succeeded: campaign={N} npc='...' hp={N} ac={N} commands={count}`
- `avrae_projection_failed: campaign={N} npc='...' reason={...} error={...}`
- `avrae_projection_skipped: campaign={N} npc='...' reason={noop_complete|gate_not_in_init|gate_engine_stats_null|gate_engine_missing}`
- `avrae_projection_aside_posted: campaign={N} npc='...'` (when failure-path posts to `#dm-aside`)

### §10.2 Removed log lines

None — Ship 3 is additive.

### §10.3 Metrics to watch post-ship

- **Mismatch rate**: ratio of `Talin: <None>` style outputs vs total hydrated-NPC combatants over a session. Expected: 0% post-ship (vs 100% pre-ship for hydrated NPCs).
- **Projection success rate**: `avrae_projection_succeeded` / `avrae_projection_attempted`. Target ≥95%; below that means Avrae's command surface diverged from the spec's assumed syntax and a verify-pass on D1 is needed.
- **Idempotency-skip ratio**: `avrae_projection_skipped` / total trigger fires. High ratio (>50%) is healthy — most triggers no-op because the NPC is already synced.

---

## §11. Decision points

Each decision: question, options, recommended default, confidence, trade-offs, surfaced additions.

### §11.D1 — Avrae command sequence [LOCKED post-pivot]

**Question:** What exact `!init`-family commands does the suggester surface to the DM?

**S41 verify-pass empirical findings (lock):**
1. `!init opt <name> -hp <N>` sets max HP. **NOT `-h`** — `-h` is Avrae's hidden-toggle shorthand; emitting `-h 13` silently hides the combatant. Confirmed live: bot-emitted `-h 13` produced "ProjTestA hidden." (DM message); operator-manual `-hp 13` produced "ProjTestA's HP set to 13 (was None)."
2. `!init opt <name> -ac <N>` sets AC.
3. Avrae's parser cannot consume back-to-back commands in a single code block (operator finding: "you can't do blocks"). DM pastes each command as a separate message.
4. **Avrae filters bot-emitted commands.** Identical commands work when human-typed, silently rejected when bot-typed. This is the load-bearing finding that forced the S41 pivot — it eliminates Options A/B/C from the pre-pivot decision tree entirely, since none of them work bot-side.

**Locked syntax (suggester content):**
- `!init opt {npc_name} -hp {hp_max}` (separate message)
- `!init opt {npc_name} -ac {ac}` (separate message)

**Sub-decision (`-controller` flag):** NOT applicable post-pivot. The DM types the commands; controller authority is whoever typed them (the DM). Filed v1.x consideration is moot.

### §11.D2 — Projection trigger timing

**Question:** Does the writer fire (a) only at `_handle_init_list_event` (passive — wait for combat), (b) only at `/hydrate` (active — sync on hydrate), or (c) both?

**Options:**
- A: Init-list only. Simpler; one trigger surface.
- B: `/hydrate` only. Doesn't catch NPCs hydrated before init.
- C: Both, with idempotency at the writer.

**Recommended default:** **C (both).** This is what makes C3 a second-instance candidate (single writer, two disjoint trigger surfaces, idempotent at writer). Covers both flows operators use: pre-combat hydration (`/hydrate` then start combat) and mid-combat fallback (operator added an NPC via `!init add` without prior `/hydrate`).

**Confidence:** HIGH.

**Sub-decision:** when engine stats change (re-hydrate with different CR), should the writer fire even if Avrae HP is already non-`<None>`? Recommended YES — engine is authoritative; Avrae mirrors. Idempotency guard refines to "no-op IFF Avrae HP matches engine `hp_max` AND Avrae AC matches engine `ac`."

### §11.D3 — Failure-mode handling

**Question:** If Avrae projection fails (channel send raises, Avrae returns error embed), does the engine row stay or roll back?

**Options:**
- A: Engine stays; projection retries on next trigger; DM notified via `#dm-aside`.
- B: Engine rolls back; user-visible failure mirrors mechanical reality.

**Recommended default:** **A.** Per §5.4 rationale: engine authority is the cluster trajectory; partial-write windows are worse than projection lag.

**Confidence:** HIGH.

### §11.D4 — Stub-monster path for non-init-resident NPCs

**Question:** If operator wants `/hydrate` to create the Avrae combatant from scratch (bypass `!init add`), should the writer fire `!init madd <stub>` directly?

**Options:**
- A: No. The writer only modifies existing combatants. Operator must `!init add` first.
- B: Yes. The writer detects "NPC not in init" and emits `!init add <init_mod> <npc-name> -h <hp>` to create the combatant.

**Recommended default:** **A.** Preserves DM authority — combat begins when the DM says so (via `!init add`). The writer's role is sync, not initiation.

**Confidence:** MEDIUM-HIGH. Option B reduces friction but conflates "stat sync" with "combatant creation" — two semantically different operations. Operator can always `!init add` after `/hydrate`; the friction is small. If post-ship live-verify surfaces "operator forgot `!init add` after `/hydrate`" as common friction, file v1.x to extend the writer.

---

## §12. Doctrine candidates filed / anchored

### §12.1 [PIVOTED — §65a amendment NOT filed]

Per §3.2 pivot note: §65a amendment is no longer needed. The §1b suggester pattern preserves §65 in its original form. The pre-pivot amendment text is preserved in §3.2 for archaeology.

### §12.2 [PIVOTED — C3 second-instance claim withdrawn]

The pre-pivot v1 spec claimed `avrae_project_npc` would be Doctrine C3's second project instance ("single-writer compatible with multiple disjoint trigger surfaces"). The pivot dissolves this claim:

- **Pre-pivot framing:** the helper was a single bot-side WRITER (emitting `!`-commands to Avrae's channel). Two trigger surfaces (`/hydrate` + `_handle_init_list_event`) called the writer. That fit C3's pattern.
- **Post-pivot framing:** the helper is a suggester, not a writer. It posts text to `#dm-aside`; the DM is the actual writer (typing the commands manually). The trigger-to-helper relationship is preserved, but the "single writer" framing no longer applies because the bot isn't writing to Avrae at all.

**C3 stays at one project instance** (Ship A's `dnd_pending_roll_directives.dc` column, S36). Ship 3 does not promote C3. Future ships may surface a genuine second instance; until then, C3 remains a filed candidate per its original framing.

### §12.3 §1b second-instance filed (NEW post-pivot)

**Doctrine §1b** (validated-suggester pattern, anchored S26 with Track 6 #5.1 SRD suggestion hook). Ship 3 lands as the **second project instance** post-pivot:

- **First instance (S26):** `_post_srd_suggestion` posts SRD monster card to `#dm-aside`; DM types the suggested `!init madd` command; Avrae executes. LLM/parser/SRD-index proposes; deterministic validator confirms (SRD index lookup); DM approves by paste; Avrae executes.
- **Second instance (S41 post-pivot):** `_avrae_project_npc` posts `!init opt -hp X` + `!init opt -ac Y` command block to `#dm-aside`; DM pastes; Avrae executes. Engine state + Avrae's `<None>` status precondition proposes; idempotency gate confirms (`gate_not_in_init` / `noop_complete` / Case A/B split); DM approves by paste; Avrae executes.

The shape repeats: **bot proposes via #dm-aside, deterministic gate confirms the proposal is safe to suggest, DM approves by pasting, Avrae executes**. Two distinct surfaces (SRD monster creation + NPC stat sync) both close their respective failure modes (F-49 fabrication, Finding H state-sync gap) via the same architectural primitive.

**Doctrine accounting:** §1b's instances list grows from one (SRD suggestion) to two (SRD suggestion + NPC state-sync). Lands in DOCTRINE.md's §1b entry at Ship 3 doc-update pass.

### §12.4 §76 doctrine carries forward (no fourth instance)

The four-property audit on `dnd_npcs` (§4.1) confirmed §76's table-agnostic phrasing applies cleanly. No 4/4 hits; no new project instance ships from this audit. §76's three project instances (S22 #2 / S32 / S36) remain canonical.

### §12.5 Doctrinal observation: §17 gated-write discipline preempts §76 four-property surfaces

(Added per S40b review §7.3.) Where a column has a §17 single-writer helper as its only write path (e.g., `npc_upsert`, `npc_hydrate_stats`, `npc_register_avrae_madd`), the column structurally cannot become a §76 four-property contamination surface — the gated-write boundary fails property 1 ("LLM-writable" requires a non-gated write path). The Ship 3 audit empirically validates this: 20 `dnd_npcs` columns audited, zero 4/4 hits, because every LLM-influenced write flows through a §17-disciplined helper.

**Operational consequence:** when designing new persisted scalar columns, the four-property audit checklist can be short-circuited at column-add time by routing the column's write path through a single-writer helper with appropriate gates (skeleton_origin protection, canonicalize_name normalization, source classification, idempotency contract). This is the §17+§76 composition pattern: §17 names the discipline; §76 names the failure mode that discipline preempts.

**Filed as doctrinal observation** (not a new candidate); lands in DOCTRINE.md at Ship 3 doc-update pass, either as a §76 sibling note or as §17 elaboration (placement decided at doc-update time).

### §12.3 §76 doctrine carries forward (no fourth instance)

The four-property audit on `dnd_npcs` (§4.1) confirmed §76's table-agnostic phrasing applies cleanly. No 4/4 hits; no new project instance ships from this audit. §76's three project instances (S22 #2 / S32 / S36) remain canonical.

### §12.4 No other new candidates filed

Ship 3 is a structural projection-layer addition; no new architectural patterns surface beyond the C3 second-instance opportunity.

---

## §13. Out-of-scope + S41 architectural finding

### §13.1 Avrae bot-filter structural API boundary (S41 verify-pass finding — LOCKED)

**Empirical finding (S41, May 11, 2026):** Avrae has a hard API boundary: identical `!init`-family commands mutate state when human-typed and are silently filtered when bot-typed. Verified live during S41 verify pass:

- **Bot-emitted:** `!init opt ProjTestA -hp 13` delivered to `#dm-narration` via `channel.send` (delivery confirmed, no exception). Avrae returned no response. `!init list` continued to show `ProjTestA <None>`. State did not mutate.
- **Operator-manual (human-typed):** identical text `!init opt ProjTestA -hp 13` pasted by operator in `#dm-narration`. Avrae responded `"ProjTestA's HP set to 13 (was None)."`. State mutated.

The bot-filter is structural Avrae API behavior. It cannot be engineered around without TOS-violating self-botting (e.g., automating a fake "user" client to type into Discord). The S40 spec's locked architectural shape (fix candidate (a) — bot-as-DM-proxy projection writer under §65a) is therefore **structurally impossible**.

**S41 in-session pivot** (operator-approved, this spec body updated accordingly):

- **Drop** fix candidate (a) entirely. The §65a amendment is no longer needed; §65 holds in its original form.
- **Adopt** fix candidate (a') — a §1b validated-suggester variant: bot posts a copy-paste command block to `#dm-aside`; DM pastes the commands; Avrae responds to the human-typed input.
- **Architectural shape:** `_avrae_project_npc` helper preserved by name (no call-site churn); behavior converted from writer to suggester. All other infrastructure (engine-side hydration, idempotency gates, Case A/B split, telemetry log lines) carries forward unchanged.
- **Doctrinal accounting:** §65a NOT anchored; C3 second-instance claim withdrawn; §1b second-instance filed (Ship 3 joins Track 6 #5.1 SRD suggester as the second project instance of the validated-suggester doctrine); §76 four-property audit on dnd_npcs holds clean; §12.5 §17+§76 composition observation lands.

**What this teaches:** spec lock at the architectural shape level does not pre-empt API surprises at the implementation level. The S40 review correctly surfaced D1 ("Avrae command sequence") as a verify-at-implementation question. The unexpected finding wasn't the syntax (which we suspected was implementation-uncertain) — it was the **bot-vs-human filter** at the Avrae layer, which the spec's recon could not have surfaced without live test. Documented as Doctrine §47 evidence (specs drift from code over time — and from external-API behavior).

**Future ships affected:** any future combat ship that imagined bot-emitted `!`-commands (F-55 #5.2 NPC Turn Automation, #5.4 Intent-to-Avrae Resolver if it considered bot-emit, etc.) must inherit this finding. The suggester pattern is the architectural default; direct bot-emit to Avrae is permanently off the table.

### §13.2 `/hydrate` role reframe (operator clarification, S41 in-session)

`/hydrate` is **NOT the canonical NPC-stat-entry flow** — it is an **emergency-fix surface** for cases where Avrae's combatant state is wrong or incomplete. Specifically:

- DM took the `!init madd` shortcut for a quick combatant add and left engine stats blank.
- DM accidentally typed `!init add 15 Goblin -h 20000` and needs to correct the HP.
- Engine row exists from a prior parser hit / skeleton load but Avrae was never synced.

**Canonical NPC entry flow:** the DM types `!init add 15 <name> -h <hp> -ac <ac>` directly in `#dm-narration` with full stats inline. Avrae creates the combatant fully mechanically valid in one human-typed message; no `/hydrate` needed; no Ship 3 suggester needed. This is the path of least friction and the one DMs use by default.

**Why this reframe sharpens the §1b suggester pivot:**

Emergency-fix tools should keep the human in the loop for state mutations — the DM sees the proposed correction and approves it by pasting, rather than the bot quietly mutating Avrae's state behind the scenes. This is exactly what §1b enforces: bot proposes, deterministic gate validates the proposal is safe (via `gate_*` + Case A/B split), DM approves by paste, Avrae executes. The architectural shape post-pivot fits the operator's mental model of `/hydrate`'s actual purpose: it's a stat-correction surface for cases the canonical path missed.

**`_handle_init_list_event` hydration branch behavior post-reframe:** keep auto-firing on `<None>` status. Auto-fire posts the sync suggestion to `#dm-aside`; the DM pastes if appropriate (e.g., they took the `!init madd` shortcut and need to backfill stats) OR ignores if intentional (they meant to leave the combatant unhydrated). The branch catches the shortcut cases without forcing intervention — the DM still has full authority over whether to apply the suggestion. The Case A/B split in §5.3 already encodes this: Case B (numeric HP) silently no-ops, so the only auto-fire posts are for genuinely-`<None>` combatants where a suggestion is useful.

### §13.3 Filed candidate (post-Ship-3): Track 6 #5.1 SRD resolver reshape

**Surfaced at S41 in-session pivot conversation.** The existing SRD suggester (Track 6 #5.1, S26 — first §1b instance) suggests `!init madd "<srd_name>" -name "<input_name>"` which creates a fully-statted Avrae combatant from the SRD bestiary. This works cleanly for DMs who want SRD-faithful stats.

**The reshape opportunity:** the SRD index already carries HP and AC for every monster. The suggester could be reshaped to suggest a fully-statted `!init add <init> "<name>" -h <hp> -ac <ac>` block instead, giving the DM full control over the name and inline stats while still leveraging the SRD lookup. This composes naturally with Ship 3's pattern (same `-hp` + `-ac` flags, same separate-message paste discipline).

**Why this is a filed candidate, not a Ship 3 deliverable:**

The existing SRD suggester already works for its current purpose. The reshape would reduce friction in the `!init add` canonical flow (DM gets a pre-filled stat block to paste from SRD instead of typing CR + HP + AC manually) but isn't required to close Finding H. Ship 3's scope is narrower — sync engine state to Avrae for `<None>` combatants — and the reshape would be its own small ship after Ship 3 verify clean.

**Files into ROADMAP candidate-next-layers** as a brief entry at Ship 3 doc-update time. Likely sequence: post-Ship-3, post-listener-edge-case-verify, post-dumb-combat, before or after the playtest phase depending on observed friction.

### §13.4 Other out-of-scope items

Explicitly excluded from Ship 3:

1. **PC sheet projection.** PCs use `!sheet` flow (player-driven). Distinct writer surface from NPC projection. Out of scope.
2. **Avrae stat-schema mismatch handling.** If Avrae's internal stat schema changes (e.g., new HP semantics), Ship 3's writer assumes current Avrae behavior. Schema-drift handling is a future maintenance ship, not Ship 3.
3. **NPC condition state projection** (e.g., poisoned, frightened). Conditions are written by Avrae during combat; Ship 3 only syncs HP/AC at projection time. Mid-combat condition application is Avrae's job. **Verify-pass note:** if conditions on hydrated NPCs surface as a play friction (e.g., DM applies a debuff narratively but Avrae doesn't know), file v1.x.
4. **`!attack` directive binding** (parallel to `!check` binding from Ship A). Ship A handles skill checks and saves; `!attack` directive binding for NPC turn automation is F-55 #5.2 territory (depends on Ship 3 to land first). Out of Ship 3 scope.
5. **NPC turn automation (#5.2).** Separate F-55 cluster ship; depends on Ship 3.
6. **Intent-to-Avrae resolver (#5.4).** Separate F-55 cluster ship; depends on Ship 3.
7. **Combat Cockpit / Turn Card (#5.3).** Separate F-55 cluster ship.
8. **NPC description / origin_excerpt audit** for §76 (adjacent surface flagged in §4.1). Not retrieved into LLM prompt context currently; filed for future audit if a "NPC profile block" ship surfaces.
9. **`dnd_npcs` schema additions** for projection metadata (e.g., last-projected timestamp). The writer uses `dnd_combatant_state` to gauge current Avrae state; no new `dnd_npcs` column required. If post-ship telemetry surfaces a need (e.g., observability gap on projection cadence), file v1.x.
10. **Backward-compat shim for pre-Ship-3 hydrated NPCs.** Any NPC hydrated before Ship 3 will naturally project on the next `!init list` event (Trigger 1). No manual migration step.

---

## Tabular handoff (S40)

| Item | Status |
|---|---|
| Spec file | `/home/jordaneal/virgil-docs/specs/NPC_STATE_SYNC_SPEC.md` |
| Spec version | v1 draft (S40) |
| Companion review | `NPC_STATE_SYNC_REVIEW.md` to draft in S40b |
| Decisions surfaced | 4 (§11.D1 command sequence, D2 trigger timing, D3 failure-mode, D4 stub-monster path) |
| Sub-decisions | 2 (D1 sub: `-controller` flag; D2 sub: re-projection on engine-vs-Avrae mismatch) |
| Recon HALT escalations | 0 |
| Doctrine candidates | §65a amendment drafted (anchors when Ship 3 ships); C3 second-instance opportunity identified (promotion to anchored doctrine pending verify) |
| §76 four-property audit | Complete (§4.1, 20 columns audited); no 4/4 hits on dnd_npcs; doctrine carries forward cleanly |
| Subships planned | Single ship (no sub-ship structure like Ship 2's 2a/2b/2c) — projection writer + two trigger integrations + tests |
| Out-of-scope filed | 10 items (§13) |
| Load-bearing artifacts | §3.2 §65a amendment text; §5 projection-writer contract; §4.1 four-property audit table |
| Ready for review | YES — S40b can proceed |
| Code changes in this session | NONE (spec only per locked operator pattern) |

**Confidence on shipping shape:** medium-high. The locked architectural shape held under recon; the §11 decisions are well-bounded; the four-property audit produced clean classifications. The MEDIUM-HIGH (vs HIGH) reflects D1's implementation-uncertainty — the exact Avrae command sequence needs live verify at S41 implementation, not just at S40b review. The spec marks D1 explicitly as "verify at implementation" rather than locking the command string in spec.

**Next session:** S40b review pass walking D1-D4, cross-doc consistency check against `HYBRID_COMBAT_NOTES.md` v3 + `PLAYTEST_OBSERVATION_FRAMEWORK.md` + (newly anchored) DOCTRINE §76, then S41 implementation of Ship 3.
