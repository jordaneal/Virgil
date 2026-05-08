# Track 4 #3 — Time Progression — Session 2 Review

**Spec version reviewed:** TRACK_4_3_SPEC.md v1.1 (post-merge — §11.E now combines former §11.E + §11.F into one nested decision; §11.I added for `advance_time()` signature shape).
**Review date:** 2026-05-08
**Status:** Pre-lock — §11.A through §11.I need Jordan's call. §J surfaces additions Code noticed during review; §K/§L cover test surface and scope honesty.

---

## §A — §11.A: Time granularity

**Question:** Day + 6-phase enum (a), Day + 4-phase (b), Day + hours (c), Day + minutes (d), or abstract beats (e)?

**Trade-offs:**

Option (d) is dominated. Minute-level precision is invisible at any normal play surface — the corpus shows skilled DMs almost never use minute anchors at the campaign-clock level (they use "minutes" only inside `in_scene_compression`, which is intra-scene texture, not clock advance). Carrying 1,440 distinct values per day buys nothing the player or DM ever sees.

Option (e) is the F-54 minimum — Day N alone, no time-of-day. It addresses "the world doesn't visibly evolve" only at the day-cadence; loses the diurnal texture that the corpus findings document at 22.1% `days` granularity AND 12.2% `hours` AND 16.0% `minutes`. THE_GOAL's "world should breathe" reads as diurnal rhythm, not just day numbers — (e) closes too narrow a slice of F-54.

Option (c) — hours — is the closest defensible alternative. Maps to D&D mechanical timings (long rest = 8h, spell durations in hours), which has surface appeal. The cost: hours forces a translation layer between mechanical time and narrative texture. Is 18:30 "evening" or "late afternoon"? The DM and the LLM will disagree. The corpus's `cumulative_anchor` phrasing ("late afternoon," "pushing past one or two in the morning") shows skilled DMs verbally compress hours into phase-language anyway. Encoding hours but presenting phases means the storage/display ratio is lossy — every read of "current time" is a phase-bucketed lookup off an integer that the DM never types directly. The D&D mechanical clock is Avrae's job (spell duration tracking); v1 isn't building that.

Option (b) — 4 phases — and option (a) — 6 phases — differ by Late Night and Midday. The corpus directly justifies these two extras: T13 ("It's now pushing past maybe one or two in the morning") is a Late-Night anchor that would round to "Night" under (b); T9 and T2 reference "around noon" / "late afternoon" anchors that compress under (b). With 4 phases, the DM and LLM lose two of the most observed cumulative-anchor patterns. With 6, the narrative vocabulary maps 1:1 with what the corpus shows.

**Recommendation: Option (a). Confidence: high.** The 6-phase enum is the smallest representation that captures Matt's observed cumulative-anchor vocabulary without forcing mechanical-clock math. (e) is too narrow for F-54 closure; (c) trades narrative texture for mechanical precision the system doesn't need; (b) loses two of the corpus's most-cited phase patterns; (d) is overkill.

**Condition to reconsider:** if v1 logs show DMs frequently typing arrival_time strings that don't map cleanly to any of the 6 phases (e.g. "an hour before sunrise"), the granularity is too coarse — but the v1.x response is to add phase aliases to the parser, not to switch granularity tier. Switching from (a) to (c) post-ship would be a schema change; switching from (a) to (b) is a config change. (a) is the lowest-regret choice.

---

## §B — §11.B: Who advances time

**Question:** Travel + Avrae rests + /advance + /rest (a), Travel + Avrae rests only (b), or Travel + Avrae rests + /advance, skip /rest (c)?

**Trade-offs:**

Option (b) leaves no clean DM-explicit narrative-compression surface. "Skip three days of downtime" requires either (i) a `/travel` to nowhere (semantically wrong — no travel happened) or (ii) editing the DB. (b) closes too few real DM surfaces.

Option (a) ships /rest alongside /advance. The pull for /rest is solo-DM-without-Avrae play. Currently every Virgil session uses Avrae actively for rolls and combat — `_handle_rest_event` already observes `!lr`/`!sr`. A new `/rest` is a parallel surface to an already-working signal; it solves a hypothetical (offline-Avrae play) rather than an observed friction. Doctrine §6 (evolve from observed friction, not anticipated) and the "Don't add features beyond what the task requires" baseline both push against shipping it.

Option (c) keeps /advance (real DM-explicit narrative-compression surface, no Avrae alternative) and skips /rest. If observed sessions show DMs taking narrative rests outside Avrae, /rest ships in v1.x — the existing `transition_context` plumbing already supports it (line 2961 of `discord_dnd_bot.py` lists `/rest` as a planned future sibling, so the v1.x ship is well-staged).

**Recommendation: Option (c). Confidence: medium.** Push back on the spec's lean of (a). Surface-area minimization wins under §6 + "don't ship for hypothetical needs." The /advance surface covers the genuine DM-compression gap; /rest can land later if a rest-without-Avrae session pattern actually shows up in logs. Adding a slash command is cheap; removing one once shipped is sticky.

**Condition to reconsider:** if Jordan plans imminent solo-no-Avrae sessions, the offline use case is observed-not-anticipated and (a) is the right call. If the next 5 sessions all run Avrae, (c) is right and `/rest` stays filed in §12.

---

## §C — §11.C: Schema location

**Question:** Column on `dnd_scene_state` + `dnd_time_advancements` log table (a, both), column-only (b), log-table-only (c), or column + in-memory log (d)?

**Trade-offs:**

Option (d) is dominated. In-memory log loses durability on restart — the entire diagnostic value of the log evaporates. Doctrine §39 (pure-observability first) wants durable per-event records; in-memory state contradicts that.

Option (c) is event-sourcing-clean — current state is `MAX(created_at)` over the log table — and matches §17 single-source-of-truth most purely. The cost: every per-turn read of "current time" (footer renders ~once per turn; directive renders on advancement turns) becomes a SELECT-with-ORDER-BY-DESC-LIMIT-1 instead of a single column read. SQLite handles this trivially at session scale. The bigger pull: scene_state row updates currently include all scene fields atomically; splitting time off into a separate table breaks the "one row per campaign" mental model that the rest of `dnd_scene_state` follows.

Option (b) is the smallest-spec fit. The `time_advance:` log line is durable in `dnd.log` (mid-rotation, but recoverable). The lost capability: structured queries over advancement history. Six months in, "how many times did the clock advance via /advance vs Avrae rest events?" requires `grep | awk` on log files rather than a SQL query. Tractable but uglier.

Option (a) is column-for-cheap-reads + log-table-for-durable-audit. Two write surfaces, one writer (`advance_time()` writes both inside one transaction, satisfying §17). The schema cost is small — two columns + one new table + one cascade entry (§J.4). The diagnostic value is real for the six-month-campaign goal that motivated the spec.

**Recommendation: Option (a). Confidence: high.** Validates the spec's lean. The column gives cheap per-turn reads (footer fires every turn); the log table gives durable advancement history without grep. The single-writer discipline is preserved because both writes happen inside `advance_time()`'s one transaction.

**Condition to reconsider:** if Jordan finds the dual-write footprint architecturally noisy (vs. event-sourcing's purity), (c) is the close runner-up. The migration cost between (a) and (c) post-ship is moderate — one schema change + footer/directive read-path change.

---

## §D — §11.D: Skeleton starting-time field

**Question:** Optional skeleton field (a), no field — defaults only (b), or required field (c, rejected)?

**Trade-offs:**

Option (c) is rejected by the spec — would break every existing campaign on next `/play`. Correct rejection.

Option (b) is the surface-minimization read: every campaign starts at `(1, 'Morning')`; if the DM wants a different starting state, type `/advance` after `/play`. Adds one DM step per non-default campaign start. Cleaner skeleton parser surface. The drag: solo DMs may want their starting state declared in the campaign skeleton alongside other authored canon; making them re-declare via /advance every reload is friction.

Option (a) is one optional skeleton section, falls back to defaults. Loader reads `## Starting time` if present and applies on first scene_state seed; absent, applies the column DEFAULTs. Existing campaigns auto-default; new campaigns have a clean declarative surface for non-default starts. Skeleton-as-config is already established for other fields (locations, NPCs, hooks); adding time fits the existing pattern.

The genuine concern with (a) is the seed-write path's interaction with §11.C — see §J.3. Resolving that is a v1 implementation detail that doesn't change which option ships.

**Recommendation: Option (a). Confidence: high.** Validates the spec's lean. Optional field is the smallest skeleton-shape addition that gives campaigns choice without breaking compat. The seed timing question (§J.3) is real but resolvable.

**Condition to reconsider:** none specific to this decision; the seed-timing implementation choice in §J.3 affects how (a) is implemented, not whether to choose (a) over (b).

---

## §E — §11.E: Surface architecture, timing, and `just_advanced` mechanic

**Question (combined, three nested sub-questions):** how does the prompt see the clock; when does the directive fire; how is "just advanced" detected? The choices nest — locking sub-(i)β moots (ii) and (iii); locking sub-(ii)β moots (iii). Recommend a combined lock.

### (i) Surfaces — footer / directive / both / both-with-restate

(δ) directive every turn risks F-30 prompt bloat AND F-52-adjacent compulsive re-mention (THE_GOAL: "memorable details should recur intentionally, not compulsively"). Adding another always-on directive block to a prompt that already carries pacing/central_thread/consequence/commitment/capability/init/loot/redirect is real cost; the corpus doesn't show Matt restating time-of-day every turn — it shows him stating it once at scene transitions. (δ) is a bad fit empirically.

(γ) directive only — no footer — saves ~25 chars per turn but loses the player's ambient signal. The footer extension is cheap (one line in `render_state_footer`); skipping it gives nothing meaningful in return.

(β) footer only is the conservative read — never asks the LLM to do anything time-aware; relies on the LLM picking up texture from the footer prelude. Smallest LLM-cooperation surface. The cost: clock advances feel mechanical rather than narrative — the corpus shows Matt does an in-fiction beat on advancement (`scene_transition` 17.7% + `cumulative_anchor` 10.4% are exactly these beats), and (β) declines to ask the LLM for that beat. Players see the footer flip from "Day 3, Evening" to "Day 5, Morning" with no narrative bridge.

(α) footer always + directive on just-advanced is the corpus-validated shape. Footer carries ambient signal; directive ties the structural advance to one narrative beat. Both surfaces are cheap; both are empirically motivated.

### (ii) Directive timing — only meaningful under (i)α or (i)γ

(β) every-turn replicates (i)δ's compulsion risk under a different surface — same problem.

(γ) phase-bordering-turns only is structurally identical to (α) under §17 single-writer discipline (the only way phase changes is through `advance_time()`); (γ) only differs from (α) if the just-advanced detection mechanism (iii) loses the flag, in which case (γ) is a fallback heuristic.

(α) just-advanced-only is the corpus-validated cadence — one beat per advance.

### (iii) `just_advanced` mechanic — only meaningful under (ii)α

(β) process-memory flag is clean — set-and-clear semantics, immune to long-turn windowing. The cost is restart-loss: a bot crash between `advance_time()` write and the consuming `dm_respond` consume drops the flag; the first post-restart turn won't see the just-advanced signal even though the log row exists. The symptom is mild (a missed in-fiction beat, not a correctness bug), but it's real.

(γ) per-process counter is durable across long turns within a process but has the same restart-loss as (β). Buys nothing over (β) at v1's surface.

(α) recency check on `dnd_time_advancements` reads `MAX(created_at)` per turn within a tunable window (~60s starting). The log table is the audit anyway, so the read is "free" infrastructure. Survives bot restart — if the campaign advanced 30 seconds before a crash, the post-restart turn within window still sees the just-advanced signal. The risk is long-turn windowing — multi-actor arbitration plus chained narration could exceed 60s, in which case the directive fails to fire on the next turn. Symptom is the same as (β)'s restart-loss (a missed in-fiction beat, not corruption); window is tunable from telemetry.

### Combined recommendation

**Recommendation: (i)α + (ii)α + (iii)α — footer always + directive on just-advanced + log-recency check. Confidence: high.**

The combined lock follows the corpus empirics (Matt does both surfaces, both timings) and lands on the most-debuggable just-advanced mechanic (the log table is already the audit; the recency window is tunable from production telemetry). All three sub-locks reinforce each other: (i)α requires (ii) to be defined; (ii)α requires (iii) to be defined; (iii)α leverages (i)+(ii)'s required infrastructure (the log table from §11.C lock).

**Condition to reconsider sub-(iii):** if `directive_emit:.*time=1` correlations against `time_advance:` show >5% missed-fires after window tuning to 120s, switch to (iii)β process-memory flag and accept restart-loss as the simpler trade. Don't pre-tune; ship at 60s; observe.

**Condition to reconsider the whole combined lock:** if v1 ships and the in-fiction beat is consistently ignored by the LLM (despite the directive), retreat to (i)β footer-only and remove the directive surface — at which point (ii) and (iii) become moot. Watch for "directive fires but narration doesn't reflect a time transition" patterns in the first 3 sessions.

---

## §F — §11.F: §1b LLM time-mention extraction in v1 vs v1.x

**Question:** Defer to v1.x (a), ship in v1 (b), or build-but-gate-off (c)?

**Trade-offs:**

(c) builds the suggester, doesn't fire it. Doctrinal cost: feature flag for hypothetical future use — the project's "Don't add features… for hypothetical future requirements" guidance pushes against it. Architectural cost: code path that's never exercised in production accrues bit rot.

(b) ships the §1b suggester alongside the §1a primitives. Doctrinally appealing — same spec carries both halves of the split. The risk is empirical: v1's primitives are unproven (no live-session telemetry yet). Pairing them with the §1b extractor means v1 logs blend three failure modes — primitive-write bugs, parse-and-validate bugs, suggester-tuning misses. Attribution gets harder; iteration gets slower.

(a) defers to v1.x. v1 ships the deterministic primitives clean; logs accumulate over a few sessions; the §1b suggester then ships against a known-good baseline (Track 6 #5.1 followed exactly this pattern — primitives first, observed signal, then build on it). The §1b ship arrives faster overall because each layer's failure modes are isolated.

Track 6 #5.1's §1b implementation is the precedent — `srd_resolver.py` shipped as a dedicated §1b ship after the upstream NPC-extractor primitives were stable. Doing the same here mirrors the proven discipline.

**Recommendation: Option (a). Confidence: high.** Validates the spec's lean. Same shape as #5.1's pattern; defers the §1b layer until the §1a primitives are observable.

**Condition to reconsider:** if Jordan wants a §1a/§1b paired-ship as a doctrine demonstration, (b) is defensible. The cost is real but contained — the suggester surface is small and resembles `srd_resolver.py`'s shape.

---

## §G — §11.G: `/travel` `elapsed` and `arrival_time` reconciliation

**Question:** parse `elapsed` + `arrival_time` as phase override (a), `elapsed` only + `arrival_time` display-only (b), restructured `/travel` deprecating `elapsed` (c, rejected by §47), or parse both with conflict telemetry (d)?

**Trade-offs:**

(c) is correctly rejected — §47 (specs respect the live surface) rules out breaking the existing `elapsed` parameter.

The choice between (a)/(d) and (b) hinges on a hidden default: `arrival_time: str = 'evening'`. Every existing `/travel` call without an explicit `arrival_time` argument receives the literal string `'evening'`. Under (a)/(d), the phase mapper sees `'evening'` and sets `day_phase='Evening'` regardless of pre-call phase. Concrete consequence: a /travel from `Day 1, Morning` with `elapsed='two days'` and no explicit `arrival_time` → `Day 3, Evening` (parsed elapsed says +2 days; arrival_time default override says Evening). The DM did not pass `arrival_time` deliberately; the function-signature default did.

This is a real surprise. DMs who currently use `/travel destination:X elapsed:'two days'` and expect "two days later, same time of day" will silently always land in Evening. The default surface-area exists pre-v1; v1 just wires it to a persisted side effect.

Option (b) — display-only — preserves the pre-v1 semantics of `arrival_time`: it goes into the prompt block (LLM sees it as flavor), doesn't write the clock. /travel's clock writes come purely from `elapsed`'s parse. DMs who want explicit phase control use `/advance` post-travel. Surface minimal; no default-surprise.

Option (a)/(d) is doctrinally appealing — every `/travel` parameter has a structural meaning — but requires fixing the default trap. The cleanest fix is changing `arrival_time`'s default from `'evening'` to `None`, then "if None → don't override; else → parse and override." But this changes the prompt-block content (TRAVEL_TRANSITION currently always carries `arrival_time={value}` text). Either the prompt block omits the line when `arrival_time` is None, or it falls back to the post-elapsed-parse phase as text. Either way, the patch is non-trivial and changes DM-visible behavior at the existing `/travel` surface.

(d) over (a) just adds conflict telemetry — a `time_advance: conflict=elapsed_vs_arrival_time ...` log line on disagreement. Useful diagnostic; doesn't address the default-surprise unless the default-fix lands too.

**Recommendation: Option (b). Confidence: medium.** Push back on the spec's lean of (d). Surface-minimization wins given the default-trap and the v1.x escape: if observed friction shows DMs typing `arrival_time='midnight'` and confused that the clock didn't reflect midnight, the v1.x fix is exactly (a)/(d) with the default flipped to None. /travel keeps writing the clock from `elapsed`; `arrival_time` keeps its current display-only role; no behavior surprise for existing campaigns. **If Jordan prefers (d)**, the lock should also change `arrival_time`'s default to `None` — that's a v1 prerequisite, not implementation-phase, because it changes the live `/travel` contract.

**Condition to reconsider:** if Jordan finds `arrival_time` actively used in current play (vs. defaulted), the default-trap is smaller — most calls will be explicit, and (d) is right. Worth grepping `dnd.log` for actual `/travel` invocations to measure default-vs-explicit usage before locking.

---

## §H — §11.H: Multiplayer time-sharing

**Question:** Campaign-wide (a), per-party-instance (b), or per-character (c)?

**Trade-offs:**

(c) is doctrinally wrong — the world has one clock; storing it per-character means two characters in the same room could disagree on what time it is. Reject.

(b) per-party-instance is structurally sensible only when "split the party" is a live UX concern. Today, Virgil has no party-instance dimension on any per-campaign table; adding `party_instance_id` to time alone (and not to scene_state, NPCs, locations, etc.) creates partial state-sharding that's worse than either pure choice. If multi-party becomes real, it's a campaign-wide architectural shift, not a time-progression-only feature.

(a) campaign-wide is the v1 default everywhere else in the schema — all per-campaign tables are keyed by `campaign_id` only. Time matches.

**Recommendation: Option (a). Confidence: high.** Validates the spec's lean. The choice is structural and worth Jordan's explicit acknowledgment, but there is no defensible alternative for v1.

**Condition to reconsider:** if multi-party support becomes a target, the time clock would shard alongside scene_state, active NPCs, and active threats — not as a standalone feature. Filed §12.

---

## §I — §11.I: `advance_time()` signature

**Question:** `set_phase: str | None = None` parameter (a), sibling `advance_time_to_phase()` helper (b), or caller-side modular math (c)?

**Trade-offs:**

The spec's "six v1 call sites" framing slightly overcounts — under realistic locks the count is 4–5: /travel always; Avrae `!lr` and `!sr` hooks always; /advance always; /rest only if §11.B locks (a) (this review pushes (c)); skeleton-loader seed only if §11.D locks (a) AND seed routes through `advance_time()` (this review pushes seed to bypass — see §J.3). Walk by site:

| Site | Calls advance_time? | Needs set-phase semantics? |
|------|---|---|
| `/travel` | yes | conditional (§11.G lock dependent — under (b) no, under (a)/(d) yes) |
| `/rest` long (if shipped) | yes | yes — wakes to Morning |
| `/rest` short (if shipped) | yes | no — +1 phase |
| `/advance` | yes | optional — DM may pass target_phase or just deltas |
| Avrae `!lr` hook | yes | yes — wakes to Morning |
| Avrae `!sr` hook | yes | no — +1 phase |
| Skeleton seed (if §11.D=a) | per §J.3 — bypass recommended | n/a |

So under realistic locks: 4 sites if /rest defers (§11.B=c), 6 sites if /rest ships. Of those, half need set-phase semantics. Not "all six" — but enough that signature-leakage matters.

Option (c) — caller-side math — forces 3 of those sites to compute `(target_idx - current_idx) % 6` after reading scene_state. Code is identical at three sites. Doctrine §17 (single-write-path) wants the writer to own the field semantics; spreading the modular-delta math across three call sites is the exact shape §17 was named to prevent.

Option (b) — sibling `advance_time_to_phase()` helper — names the set-phase semantics in the API. Per-call-site readability improves: long rest reads "advance time to Morning" rather than "advance time with set_phase=Morning." Two helpers, one writer underneath; §17 preserved. The cost is minor — one extra discoverable function name — and the readability gain is real.

Option (a) — single helper with optional `set_phase` parameter — is the minimal-API choice. Readability is fine; one path of execution; the audit-log row carries both requested and resolved forms. Keyword-argument call sites read clearly. But: when set-phase is the intent, option (b)'s helper names the intent in the call (`advance_time_to_phase(c, 1, 'Morning', 'rest_long')`); option (a) requires reading the keyword to discover it (`advance_time(c, 1, 0, source='rest_long', set_phase='Morning')`).

**Recommendation: Option (a). Confidence: medium-high.** Validates the spec's lean, but acknowledge (b) as the close runner-up. The deciding factor is signature-stability: an optional keyword argument is the smallest patch into a writer that may grow more parameters later (e.g. v1.x might add a `narration_hint` parameter for the §1b suggester to pass approved phrasing through). Two named helpers double the surface that has to absorb future parameters. (a) is the lower-regret choice.

The set-phase + phase_delta interaction needs an explicit invariant — see §J.2.

**Condition to reconsider:** if implementation in Session 3 reveals call-site readability is materially worse with (a) vs (b) — specifically if `set_phase='Morning'` keeps tripping reviewers asking "wait, what does that override?" — switch to (b). Both options preserve §17 and produce identical telemetry; the choice is API-readability only.

---

## §J — Surfaced additions

### §J.1 — Phase rollover normalization for large `phase_delta`

**Concern:** Spec §5 covers `phase_delta=+1`, `+6` (wraps to next day, same phase), and `+7` (next day, midday). It does not cover `phase_delta=+12` from any phase — which should normalize to (`+2 days`, same phase). The writer's internal math must handle arbitrary `phase_delta` magnitudes via floor-div and modulus: `total_steps = current_phase_idx + phase_delta + days_delta * 6; new_day_offset = total_steps // 6; new_phase_idx = total_steps % 6`. If implemented naively as a six-iteration loop, it works for any non-negative input but is slow at large values. If implemented as direct modular math, the writer must validate `phase_delta` is non-negative integer (already specced as a v1 invariant).

**Assessment:** The math is straightforward but currently un-named in the spec. A test pinning `phase_delta=12` from `Morning` → unchanged phase, `+2 days` makes the invariant explicit and protects against future "I'll just iterate by +1 phase 12 times" implementations. Equally, `phase_delta=13` from `Morning` → `Midday`, `+2 days`.

**Recommendation: Address in v1 — add §5 normalization formula and a test.** The patch is one paragraph in §5 (state the formula) plus one test (test 7+ extension: `phase_delta=12, 13, 25` cases). Cost: minimal; clarity benefit: real.

---

### §J.2 — `set_phase` precedence over `phase_delta` (only if §11.I=a)

**Concern:** Under §11.I option (a), the signature is `advance_time(campaign_id, days_delta, phase_delta, source, source_detail, set_phase=None)`. What happens when a caller passes `phase_delta=2` AND `set_phase='Evening'`? The spec implies `set_phase` wins ("When set, overrides `phase_delta`"), but this is a load-bearing invariant that should be explicit and tested.

**Assessment:** The cleanest contract: when `set_phase is not None`, the writer ignores `phase_delta` entirely and computes `resolved_phase_delta = (target_idx - current_idx) mod 6`. The audit-log row records both — `set_phase='Evening'` (caller's request), `phase_delta=2` (caller's also-passed but-ignored value), `resolved_phase_delta=4` (actual delta written). This makes call-site bugs visible in the log without crashing the writer.

Alternative: raise on conflicting arguments. Doctrine §16 (engine defends its own invariants) supports this — passing both is a caller bug, not the writer's job to silently disambiguate.

**Recommendation: Address in v1 — define precedence in §11.I lock, add test.** Lean: writer logs the conflict and `set_phase` wins (soft-handle). Don't raise — the soft-fail discipline (§59) means a caller mistake shouldn't kill the write path. Test cases: `set_phase` only; `phase_delta` only; both together (verify `set_phase` wins, audit log carries both).

---

### §J.3 — Skeleton-loader seed timing under §11.D=a × §11.C=a

**Concern:** If §11.D locks (a) — optional skeleton starting-time field — and §11.C locks (a) — column + log table — the loader needs a path to seed scene_state with the declared starting day/phase. Two implementations are not equivalent:

- **(i) Loader calls `advance_time(c, 0, 0, source='seed', set_phase=skeleton_phase)`.** Writes a row to `dnd_time_advancements`. Pollutes the event log with a non-event (campaign initialization isn't an "advancement" — nothing advanced). Log queries that count advancement frequency would have to filter `source != 'seed'`. The log enum grows by one symbol that doesn't represent an advancement.
- **(ii) Loader directly INSERTs/UPDATEs `dnd_scene_state` with the starting values.** Bypasses `advance_time()` for the seed write only. No log row written — campaign initialization isn't a tracked event. The §17 single-write-path discipline gets a documented exception: "scene_state.campaign_day/day_phase has one runtime writer (`advance_time`) plus one initialization writer (skeleton loader's seed path)."

**Assessment:** (ii) is cleaner doctrinally — the log is for advancement events, not initialization. The §17 exception is documented and narrow (initialization-only, runs at most once per campaign per process restart, idempotent because skeleton seed only fires when scene_state row is fresh). The alternative (i) requires a sentinel `source='seed'` that downstream queries always filter out — same data quality problem with extra ceremony.

The cleanest §17 framing: "`advance_time()` is the sole writer for runtime time advancement. Campaign initialization has a separate one-shot writer in the skeleton loader, scoped to the first scene_state seed only." Treat seed as analogous to `CREATE` vs `UPDATE` — different kind of write, different writer.

**Recommendation: Address in v1 — pick (ii), document §17 exception in §11.D and §6.** If §11.D locks (b) — defaults only, no skeleton field — this whole concern is moot because there's no seed path needing a writer choice. Verify §11.D lock first; if (a), apply (ii).

---

### §J.4 — `dnd_time_advancements` cascade — must add to `_CAMPAIGN_SCOPED_TABLES`

**Concern:** VIRGIL_MASTER §6 (line 199) is explicit: *"When you add a new per-campaign table, append it to `_CAMPAIGN_SCOPED_TABLES` in the same patch or campaign purges silently leave orphan rows."* The spec proposes `dnd_time_advancements` (a per-campaign table) but does not mention adding it to `_CAMPAIGN_SCOPED_TABLES`. The constant currently holds 8 tables; v1 needs to extend to 9 and verify the cascade test passes.

**Assessment:** This is a hard requirement, not optional. `/purgecampaign` and `/purgeallcampaigns` flow through the cascade; missing the new table means a purged campaign leaves rows in `dnd_time_advancements` indefinitely. The Track 4 #2 loot ship (`dnd_loot_pending`) added to `_CAMPAIGN_SCOPED_TABLES` correctly per VIRGIL_MASTER's record — same discipline applies here.

The `dnd_scene_state` column additions (`campaign_day`, `day_phase`) don't need cascade work — `dnd_scene_state` is already in `_CAMPAIGN_SCOPED_TABLES`, and column-level additions inherit the row-level cascade.

**Recommendation: Address in v1 — hard requirement.** Add `'dnd_time_advancements'` to `_CAMPAIGN_SCOPED_TABLES` in the same patch as the table creation. Add a cascade-integrity test (alongside §11.C's schema tests): create a campaign, advance time, run `/purgecampaign`, verify `dnd_time_advancements` row count for that campaign is 0. See §K test surface review.

---

### §J.5 — Telemetry on `advance_time()` no-op (campaign_id mismatch)

**Concern:** Spec §8 covers the exception path (`time_advance: campaign={N} source=... err={repr}`) and the success path (`time_advance: campaign={N} source=... before=... after=...`), but not the case where the writer is called with valid arguments and the DB UPDATE returns 0 rows. This happens if `campaign_id` doesn't exist in `dnd_scene_state` — the UPDATE silently affects zero rows, the INSERT into `dnd_time_advancements` may succeed (no foreign-key constraint), and the writer returns... what? The spec is silent.

**Assessment:** Two failure modes blend here: (i) caller bug (passes a stale or fake campaign_id), (ii) race condition (campaign was purged between scene_state read and time write). Under (i), the writer should detect and refuse — return None, log a distinct diagnostic. Under (ii), same outcome — no advancement happened, telemetry surfaces the no-op.

The cleanest contract: `advance_time()` reads current scene_state row first; if row absent, return None and log `time_advance: campaign={N} source=... err='no scene_state row'`. Don't INSERT into the log table without a corresponding scene_state UPDATE. Keeps the column-and-log invariant atomic.

**Recommendation: Address in v1 — small writer-contract patch.** Add a `SELECT campaign_day, day_phase FROM dnd_scene_state WHERE campaign_id=?` as the writer's first read; if no row, return None with the diagnostic log line. Test case in §9 list (extends test 11): missing-campaign call returns None and writes neither table.

---

### §J.6 — `/travel` `arrival_time='evening'` default trap (cross-ref §G)

**Concern:** Already raised in §G — the existing `arrival_time: str = 'evening'` default means every `/travel` call without explicit `arrival_time` would land in Evening if §11.G locks (a)/(d). Repeated here for completeness because the surface reaches across both decisions: §11.G is the policy lock, but the default-fix is the implementation-phase patch that makes the policy honest.

**Recommendation:** see §G — lean (b) display-only avoids this entirely; if Jordan locks (d), pre-condition on changing `arrival_time` default to `None`. This is a v1 prerequisite, not implementation-phase.

---

### §J.7 — §12 cross-reference bug

**Concern:** Spec §12 line `**Multi-party split-clock.** Per §11.I option (b).` is wrong — multi-party is §11.H option (b), not §11.I. §11.I option (b) is the sibling-helper signature alternative. Stale cross-ref from the v1.1 patch.

**Recommendation: Address in v1 — one-line spec fix.** Trivial. Rewrite the §12 entry to point at §11.H option (b).

---

## §K — Test surface review

**Coverage:** Spec §9 lists 41 tests across 6 files. Roughly proportional to the spec's surface — single-writer engine layer (15 tests), parser (9), pure-function directive (3), footer extension (4), command integration (6 across travel + rest), schema integrity (4). Comparable to Track 6 #5.1's 30-test footprint adjusted for the broader runtime surface (multiple commands + Avrae hooks vs. #5.1's single hook + resolver).

**Concern 1 — `test_advance_time.py` doesn't cover §11.I=a `set_phase` semantics.**

If §11.I locks (a), the writer's `set_phase` parameter is load-bearing for 3-of-6 call sites' correctness. Tests 1–15 cover delta-only paths exhaustively but say nothing about set-phase override. Missing test cases:

- `advance_time(c, 1, 0, set_phase='Morning')` from `(1, 'Evening')` → `(2, 'Morning')`; audit log carries both `set_phase='Morning'` and resolved `phase_delta=4`.
- `advance_time(c, 1, 2, set_phase='Morning')` from `(1, 'Evening')` → `(2, 'Morning')`; verify `set_phase` wins over `phase_delta=2` (per §J.2 invariant).
- `advance_time(c, 0, 0, set_phase='Late Night')` from `(3, 'Morning')` → `(3, 'Late Night')`; verify same-day phase set works.
- `advance_time(c, 1, 0, set_phase='InvalidPhase')` → returns None, logs validation failure.

**Action in Session 3:** add 4 set_phase tests under `test_advance_time.py` (becomes 19 tests in that file). Conditional on §11.I=(a) locking; if (b) locks, replace with sibling-helper tests for `advance_time_to_phase`.

**Concern 2 — No cascade-integrity test.**

§J.4 surfaces the `_CAMPAIGN_SCOPED_TABLES` requirement. The test suite doesn't currently include a cascade-integrity check for the new table. Track 6 #4 / Track 4 #2 added similar tests when shipping new per-campaign tables — same discipline applies here.

Suggested test: `test_time_schema_integrity.py` extension —

- Create campaign N, call `advance_time(N, 1, 0, ...)` twice → 2 rows in `dnd_time_advancements`.
- Call `purge_campaign(N)`.
- Assert `dnd_time_advancements` row count for campaign N is 0.

**Action in Session 3:** add 1 test under `test_time_schema_integrity.py` (becomes 5 tests in that file). Hard requirement per §J.4.

**Concern 3 — No phase_delta normalization test for large values.**

§J.1 surfaces the `phase_delta=+12` case. Tests 6 and 7 cover `+1` rollover and `+3` rollover; nothing covers `+12`, `+13`, `+25`. The normalization formula should be pinned with explicit large-input tests so that an implementation that breaks at >6 phases (e.g. via a six-iteration loop with off-by-one) fails loudly.

Suggested: extend test 7 with `phase_delta=12 from Morning → +2 days, Morning`; `phase_delta=13 from Morning → +2 days, Midday`; `phase_delta=25 from Morning → +4 days, Midday`.

**Action in Session 3:** add 3 tests under `test_advance_time.py` (becomes 18 with concern 1's 4 + concern 3's 3 = 22).

**Concern 4 — Skeleton-seed test missing if §11.D=a × §J.3 lock.**

Per §J.3, if §11.D locks (a) and seed bypasses `advance_time()`, there should be a test: `skeleton_loader_seed_writes_scene_state_but_not_log` — verify the loader's seed path writes the scene_state row with the declared starting values AND does NOT add a row to `dnd_time_advancements`. Pins the §17 exception explicitly.

**Action in Session 3:** add 1 test, conditional on §11.D=a lock. Skip if §11.D=b (defaults only — no seed path).

**Concern 5 — `/travel` arrival_time test conditional on §11.G lock.**

Test 34 says "/travel with an `arrival_time` argument that conflicts with parsed phase — behavior matches the §11.G lock." Under §G recommendation (lean (b) display-only), test 34 becomes "verify `arrival_time` does NOT modify scene_state phase, only flows into TRAVEL_TRANSITION text." Under (d), test 34 becomes "verify explicit `arrival_time` overrides parsed phase; verify default `arrival_time='evening'` does NOT override (after default-fix to None)."

**Action in Session 3:** rewrite test 34 once §11.G is locked. Under (b), the test asserts behavioral non-effect; under (d), the test asserts explicit-vs-default detection. Don't pre-write before lock.

**Total post-review test count:** 41 → ~50 conditional on §11 locks. Still proportional.

---

## §L — Scope honesty review (Doctrine §45)

**§1 item 5 — F-54 closure proof:** the spec correctly scopes v1 to "the world doesn't visibly evolve" only, with explicit "other F-54 symptoms (scene immortality, motif compulsion F-52, advancement starvation, equal-weight narration) are sibling ships under the motion-systems thread, not promised by v1." This is honest — F-54 is the umbrella; v1 closes one symptom.

**§2 THE_GOAL alignment claims:**

- *"Six months feel like six months"* — claimed via "visible, advancing campaign clock is the simplest possible surface for cross-session continuity." Honest: explicitly scoped as "the cheapest and most legible," not the only signal. NPC arcs and faction shifts are correctly noted as adjacent signals.
- *"World should breathe"* — corpus-validated; the directive's "one in-fiction beat per advancement" matches the corpus's discrete-cut shape. Honest.
- *"Memorable details should recur intentionally, not compulsively"* — the §11.E lean (directive only on just-advanced turns, not every turn) directly honors this. Honest.

**§2 "What v1 is NOT" caveats:** explicit, accurate. "Not a calendar," "not a weather system," "not NPC-schedule-aware," "not a scene-lifecycle solution," "not a §1b time-mention extractor" — all correctly scoped out. No overclaim.

**§3 architecture honesty about pre-existing surface:** correct framing. "The reconciliation (§11.G) is genuinely a §11 decision because two architectures are defensible" — the spec acknowledges uncertainty in the live-surface area, surfaces it as §11, doesn't pre-lock. Honest scope discipline.

**§5 "six v1 call sites" claim in §11.I context:** as noted in §I above, this is an upper bound — under realistic locks (this review pushes §11.B=c and §J.3 seed-bypass), the count is 4–5. Not an overclaim per se — the math doesn't hinge on the exact count — but the spec should reflect the locked count once §11.B and §11.D land. **Minor clean-up:** post-§11 lock, update §5 / §11.I to state the actual call-site count rather than the "if everything ships" upper bound.

**§10 limitations:** all honest. "v1 has no detector for [LLM contradicting the clock] — the §1b time-mention extractor (deferred to v1.x — §11.F) would surface these as a side effect" correctly defers and names the v1.x ship. No overclaim.

**§11.I "ripples into all six v1 call sites":** as noted above, "all six" is the upper-bound count. Recommend tightening to "ripples into 4–6 call sites depending on §11.B and §11.D locks" once those decisions land.

**§12 cross-reference bug** (§J.7) — minor accuracy fix, not a scope-honesty concern.

**Overall scope discipline:** strong. The spec consistently anchors v1 to the deterministic primitive surface, names motion-system siblings as future-work-not-promises, and acknowledges where v1's closure is partial. The one accuracy clean-up (§11.I call-site count post-lock) is minor.

---

## Summary of Jordan's calls

| Decision | Recommended option | Confidence | Notes |
|----------|--------------------|------------|-------|
| §11.A Granularity | (a) Day + 6-phase enum | High | Validates spec lean. Corpus empirics support 6 phases over 4. |
| §11.B Who advances | **(c) Travel + Avrae rests + /advance, skip /rest** | Medium | **Push back on spec's lean of (a).** /rest is speculative; observe before shipping. |
| §11.C Schema | (a) Column + log table | High | Validates spec lean. Audit value > schema cost. |
| §11.D Skeleton field | (a) Optional starting-time field | High | Validates spec lean. Pair with §J.3 seed-bypass implementation. |
| §11.E Surface + timing + just_advanced | (i)α + (ii)α + (iii)α — combined | High | Validates spec lean. Three-way combined lock. |
| §11.F §1b extractor | (a) Defer to v1.x | High | Validates spec lean. #5.1 precedent. |
| §11.G /travel reconciliation | **(b) `arrival_time` display-only** | Medium | **Push back on spec's lean of (d).** Avoids `arrival_time='evening'` default trap. |
| §11.H Multiplayer | (a) Campaign-wide | High | Validates spec lean. No defensible alternative for v1. |
| §11.I Signature | (a) `set_phase` parameter | Medium-high | Validates spec lean; (b) sibling helper is close runner-up. Pair with §J.2 precedence invariant. |

---

## Session 3 pre-conditions (implementation gates)

Before Session 3 begins:

1. §11.A through §11.I locked by Jordan (this review).
2. §J.1 phase_delta normalization formula added to spec §5 (one paragraph).
3. §J.2 set_phase × phase_delta precedence invariant added to §11.I lock (one paragraph + log shape).
4. §J.3 skeleton-seed bypass documented if §11.D=a locks — §17 exception narrowly defined (one paragraph in §11.D and §6).
5. §J.4 `dnd_time_advancements` added to `_CAMPAIGN_SCOPED_TABLES` — explicit spec note in §4.
6. §J.5 no-op-on-missing-campaign telemetry shape added to §8.
7. §J.6 `/travel` `arrival_time` default-trap — if §11.G locks (d), pre-condition on changing `arrival_time` default to `None`; if (b), no change needed.
8. §J.7 §12 cross-reference bug fixed (`§11.I option (b)` → `§11.H option (b)`).
9. Test surface extended per §K concerns 1–4 (set_phase tests, cascade test, large-phase_delta tests, skeleton-seed test).
10. §11.I "six v1 call sites" claim updated to reflect locked count (post-§11.B and §11.D lock).

Pre-conditions 2–8 are spec-text patches, not code; expected scope is one editing pass before Session 3 implementation begins.

---

*Review drafted: 2026-05-08. Required reading complete: TRACK_4_3_SPEC.md v1.1, track5_findings_time_mention.md, THE_GOAL.md ("world should breathe" / "recur intentionally not compulsively"), FAILURES.md §F-54, DOCTRINE.md §1a/§17/§38/§45/§47/§59, VIRGIL_MASTER.md §6 (`_CAMPAIGN_SCOPED_TABLES` discipline), TRACK_6_5_1_REVIEW.md (cadence model). Diagnostic-grep verified `arrival_time` default surface (`discord_dnd_bot.py:2972`).*
