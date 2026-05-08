# TRACK_6_4_REVIEW.md — Session 2 walk-through

Companion to `TRACK_6_4_SPEC.md` (post-amendment). Walks the still-OPEN §11 decisions (§11.A–§11.G) plus two newly-surfaced implementation-blocking gaps (§11.K, §11.L). Pre-locked items — §11.H, §11.I, §11.J — are referenced as locked and not re-walked.

The review's job: make Session 2 fast. Each block is a trade-off restatement + recommended default + (where applicable) surfaced addition + Session-3 implementation risk.

---

### Locked items — not re-walked

**§11.H** (LOCKED): `/hydrate` uses `source='explicit_hydrate'`; always-overwrites all six stat fields. `generic_fallback` stats are placeholders, not authority.

**§11.I** (LOCKED): `bound_pc_skip` always-fire log line per Doctrine §59. Permanent.

**§11.J** (LOCKED): Hook 1 (`_handle_init_add_event`) + Hook 2 (`_handle_init_list_event`). Belt-and-suspenders. Race window closed.

---

### §11.A — Which shapes ship in v1?

**Trade-off.** Option 1 ((b)+(c) via hook points) defers skeleton stat hints — the DM sees a CR prompt on every ad-hoc NPC's first combat appearance per session. Option 2 (adds shape (a) in v1) requires touching `skeleton_loader.py` in the same ship; more scope, but reduces the DM-prompt burden for pre-planned NPCs immediately.

**Recommended default.** Option 1 ((b)+(c)). **Confidence: medium.** The prompt path is low-friction enough to validate the pipeline; `source=generic_fallback` frequency in the first few sessions is the pull-forward signal for (a). If the same named NPCs keep triggering prompts, that's when skeleton hints earn their keep.

**Surfaced addition.** `source=generic_fallback` vs. `source=miss` ratio is the observable signal for this decision. Recommend Session 3 adds a `grep generic_fallback` note to `SESSIONS.md` or equivalent so it's easy to check after the first play session.

**Session-3 risk.** Low. Shape (a) is cleanly separable — `skeleton_loader.py` extension is independently testable and doesn't touch the hook paths.

---

### §11.B — CR estimation source

**Trade-off.** Not a live trade-off. Option 3 (LLM-inferred CR) is hard-rejected by Doctrine §1. Option 2 (skeleton `CR:` hint) is deferred to v1.x per §11.A. Option 1 (DM `/hydrate`) is the only in-scope path.

**Recommended default.** Option 1. **Confidence: high.**

**Surfaced addition.** None — Doctrine §1 resolves this.

**Session-3 risk.** Low.

---

### §11.C — Failure mode when CR unknown

**Trade-off.** Option 3 (partial CR-1/4 fallback + DM prompt in `#dm-aside`) is correct on strategy — keeps combat moving while surfacing the gap explicitly. The live question is the fallback CR tier: CR 1/4 is conservative (3 HP, AC 13); most encounter-worthy ad-hoc NPCs run CR 1/2–2. Wrong fallback shows as undersized AC/attack context in the persistence directive.

**Recommended default.** Option 3 (strategy). CR 1/4 as fallback tier. **Confidence: high on strategy; medium on the CR tier.** File CR 1/4 as the starting point; if `source=generic_fallback` telemetry reveals the DM correcting to CR 1+ consistently, raise the default tier.

**Surfaced addition.** `_pending_hydration` is module-level in-memory state. If the bot restarts mid-combat, pending prompts are lost — but `stat_incomplete()` still returns True (hp_max NULL), so the next `!init list` parse re-fires the prompt. This is benign; worth confirming it's intentional behavior and not a state-recovery requirement.

**Session-3 risk.** Low on strategy. Low-medium on the restart path: benign but worth a note in test coverage that re-prompt-after-restart is the intended behavior, not a bug.

---

### §11.D — Where hydration writes

**Trade-off.** Option 1 (`dnd_npcs` only, sync hint in `#dm-aside`) preserves the VIRGIL_MASTER §4 bot→Avrae write boundary — hydration never autonomously emits `!init modify`. Cost: the persistence directive (HP source = Avrae tracker) still shows "HP unknown" until the DM manually runs the sync hint. Option 2 closes that gap but autonomously modifies live initiative-tracker state; wrong HP during combat is a high-severity failure.

**Recommended default.** Option 1. **Confidence: high.**

**Surfaced addition.** The sync hint (`!init modify {canonical_name} -hp {hp_max}`) must use Avrae's actual command syntax. Avrae's `!init modify` syntax varies by version and subcommand; if the hint string is wrong, the DM copies it into Discord and gets an Avrae error at exactly the worst moment (combat start). Verify live syntax before Session 3 ships the hint string.

**Session-3 risk.** Low on the architectural call. **Medium on the hint syntax**: a wrong `!init modify` string is a live DM friction point. Treat hint-string verification as a first-step Session 3 task alongside the Avrae add-confirmation format check (§11.K).

---

### §11.E — Controller authority

**Trade-off.** Not a live trade-off. Option 2 (bot claims controller post-hydration) requires a bot→Avrae write boundary larger than §11.D Option 2, depends on v2 AI attack infrastructure not yet built, and is explicitly out of v1 scope. This is a v1/v2 boundary call, not a decision with alternatives.

**Recommended default.** Option 1 (unchanged). **Confidence: high.**

**Surfaced addition.** None.

**Session-3 risk.** Zero. If implementation attempts NPC turn routing through the adjudication pipeline, that is a spec violation, not a risk to manage.

---

### §11.F — Telemetry shape

**Trade-off.** Per-combatant per-parse (Option 1) produces N log lines per `!init list` parse (N = combatant count, typically 2–8). Per-parse summary (Option 2) is terser but loses the per-NPC signal that identifies "which NPCs are prompting CR prompts most often." Volume is negligible at session-scale turn rate.

**Recommended default.** Option 1. **Confidence: high.**

**Surfaced addition.** The `directive_emit: hydrated={0|1}` field (§8) is a session-turn-level binary: it is `1` if any hydration WRITE occurred this turn, and `0` even when all NPCs are already hydrated (all `source=miss`). A reader scanning `hydrated=0` might infer "no NPCs needed hydration" rather than "no new writes — NPCs may already be hydrated." Recommend renaming to `hydration_write_fired={0|1}` or adding a docstring clarification at implementation time. No spec amendment needed; surfaced as a Session 3 naming note.

**Session-3 risk.** Low. Field-naming; doesn't affect write logic.

---

### §11.G — Backwards compatibility: skeleton-origin NPCs with NULL stats

**Trade-off.** Hydrating skeleton-origin NPCs normally is correct — `skeleton_origin=1` is a narrative-provenance flag, not a combat-stats authority signal. The only experiential cost: the DM authored this NPC and may find a CR prompt surprising ("Virgil doesn't know Garrik's stats?"). The prompt explains the gap and the DM resolves it in 3 seconds.

**Recommended default.** Hydrate normally. **Confidence: high.**

**Surfaced addition.** In v1, `source='skeleton'` only fires when `cr_str` was written by the skeleton loader (v1.x feature, not in scope). A skeleton-origin NPC with `cr_str` populated by a prior `/hydrate` call logs as `source='hook'`, not `source='skeleton'` — technically correct (CR came from `/hydrate`, not the loader) but could confuse session log analysis. No spec change needed; surfaced as a Session 3 implementation note for the telemetry reader.

**Session-3 risk.** Low. Telemetry source distinction doesn't affect write logic.

---

### §11.K — Avrae `!init add` confirmation message format (NEWLY SURFACED — pre-implementation gate)

**Context.** Hook 1 (`_handle_init_add_event`) must detect Avrae's `!init add <name>` confirmation message to extract the combatant name. The spec names a candidate regex (`r"(.+?) was added to combat"`) and explicitly flags the format as unverified: "must be confirmed against live Avrae output before Session 3 implementation locks the regex."

**Trade-off.** Verify format before Session 3 starts (30-second `/travel` Discord test) vs. implement against the candidate regex and fix it if wrong. If the regex is wrong, Hook 1 NEVER fires — silently. Hook 2 still provides catch-up coverage, so the system remains functional, but the race window that §11.J was locked to close is re-opened. Additional risk: if Avrae's confirmation is an embed edit rather than a new message, the `on_message` branch won't see it at all and Hook 1 requires a different detection approach.

**Recommended default.** Treat this as a first-step Session 3 verification gate — run `!init add <test-npc>` in Discord and confirm the exact message text before writing the handler. **Confidence: high on the process; not determinable on the format.**

**Session-3 risk.** **HIGH if skipped.** A wrong regex means Hook 1 is permanently dark with no error signal. The race window is open, the telemetry shows nothing wrong, and the belt-and-suspenders architecture degrades to suspenders-only without anyone knowing. This is the highest-risk open item in this review.

---

### §11.L — cr_str=None routing: caller-side decision or engine-side? (NEWLY SURFACED — spec inconsistency)

**Context.** §3 (architecture diagram), §7 (Path 1 code), and §6 (step 4 implementation outline) are inconsistent about where the "CR is unknown → post prompt → call generic_fallback" routing decision happens.

- **§3 diagram** shows: caller checks cr_str, THEN posts prompt to `#dm-aside`, THEN calls `npc_hydrate_stats(source='generic_fallback')`. Caller-side decision.
- **§7 Path 1 code** shows: caller calls `npc_hydrate_stats(cr_str=None, source='adhoc')`, THEN checks return signals (`not sigs.get('cr_str_written')`) to decide if prompt fires. Engine-side signal.
- **§6 step 4 outline** shows: `if cr_str is None and source != 'generic_fallback': cr_str = _FALLBACK_CR`. This means the engine resolves None→CR-1/4 for `source='adhoc'` — so `cr_str_written` would always be True for adhoc NPCs, and the §7 prompt check `if not ok and not sigs.get('cr_str_written')` would **never fire**. Ad-hoc NPCs with unknown CR would silently get full CR-1/4 stats (including hp_max) with no DM prompt. Contradicts §3.

**Trade-off.**
- **Option 1 (caller-side, per §3):** Caller checks `cr_hint` before calling the engine. If None: post prompt to `#dm-aside`, then call `npc_hydrate_stats(cr_str=None, source='generic_fallback')`. Engine sees `source='generic_fallback'` → partial fill, no hp_max, no internal CR resolution. Clean separation: Discord I/O stays in the caller; engine only writes.
- **Option 2 (engine-side, per §7):** Engine helper detects `cr_str=None` internally and emits a signal. Caller reacts to signal. Requires removing the `cr_str=None → _FALLBACK_CR` resolution from step 4 for non-generic_fallback sources — which contradicts the step 4 logic as written.

**Recommended default.** Option 1 (caller-side). §3 is the authoritative architecture view; §7's code sample is a draft and should match §3. The engine helper should never branch on "should I prompt the DM?" — that is Discord I/O, caller territory only. **Confidence: high.**

**Implementation consequence:** The §7 Path 1 code sample ships wrong. Session 3 should implement the §3 flow: caller checks `cr_hint is None`, posts prompt, calls `npc_hydrate_stats(cr_str=None, source='generic_fallback')`. The `if not ok and not sigs.get('cr_str_written')` pattern from §7 is dead — remove it.

**Session-3 risk.** **HIGH if ambiguous.** Implementation will pick one of the two patterns. Option 2 silently gives all ad-hoc NPCs full CR-1/4 fills (including hp_max) with no DM prompt — the entire explicit-prompt path from §3 never fires. Session 3 must implement Option 1 and the test cases for §9 test 30 ("CR-None ad-hoc NPC: `_post_hydration_prompt` called") will be the gate.

---

## Summary — items requiring Jordan's call this session

| Item | Recommended | Confidence | Session-3 risk if ambiguous |
|---|---|---|---|
| §11.A shapes in v1 | (b)+(c), skeleton hints v1.x | medium | low |
| §11.B CR source | DM /hydrate | high | low |
| §11.C failure mode | Option 3, CR-1/4 fallback | high / medium on tier | low-medium |
| §11.D write boundary | dnd_npcs only | high | low |
| §11.E controller authority | unchanged (v1/v2 boundary) | high | zero |
| §11.F telemetry shape | per-combatant per-parse | high | low |
| §11.G skeleton-origin NPCs | hydrate normally | high | low |
| **§11.K Avrae format verify** | **verify before impl — first Session 3 step** | **high on process** | **HIGH** |
| **§11.L cr_str=None routing** | **caller-side (Option 1, per §3)** | **high** | **HIGH** |

§11.K and §11.L are the two HIGH-risk items. §11.K is a pre-implementation verification gate (30 seconds in Discord); §11.L is a spec inconsistency that, if left to the implementer to resolve, will silently remove the DM prompt path for ad-hoc NPCs.

All §11.A–§11.G items have spec-stated recommendations with confidence sufficient to lock with light Jordan touch. §11.B and §11.E are effectively pre-decided (Doctrine §1 and v1/v2 boundary, respectively).
