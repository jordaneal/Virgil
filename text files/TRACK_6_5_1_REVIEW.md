# Track 6 #5.1 — Combat Entry Assist — Session 2 Review
**Spec version reviewed:** TRACK_6_5_1_SPEC.md v1.1 (post-§11.H lock)
**Review date:** 2026-05-08
**Status:** Pre-lock — §11.A–§11.E need Jordan's call. §§F–H surface implementation-phase concerns for Session 3 awareness.

---

## §A — §11.A: Hook point

**Question:** NPC extractor post-upsert (Option 1), `!init add` raw-message intercept (Option 2), or both (Option 3)?

**Trade-offs:**

Option 1 fires at narration time — when "Spiny Toad" appears in the DM's narration, `npc_upsert` creates the row, and the suggestion posts immediately to `#dm-aside`. With the §11.H lock (no mode gate), this fires regardless of scene mode, so the DM sees the suggestion while the narrative is still fresh, before they've typed any `!init` command. This is the widest coverage at the lowest coupling cost. The gap — DMs who skip narration and type `!init add` cold — is small and surfaced by a low `posted=1` rate in logs.

Option 2 intercepts `!init add` on `on_message`. The suggestion arrives at the same moment Avrae is already processing the command. The DM sees the suggestion after the no-stats combatant is already in the tracker; recovering requires `!init remove` + re-add. Net effect: a suggestion that arrives too late to be acted on without friction.

Option 3 is Option 1 + the `!init add` intercept filed as v1.x — which is exactly what the spec already does. The spec's §12 files the intercept as a future fallback trigger.

**Recommendation: Option 1. Confidence: high.** The §11.H lock makes Option 1 the unambiguous winner on UX timing. Option 2 is strictly worse for the primary case; Option 3 collapses into Option 1 given the v1.x filing in §12.

**Condition to reconsider:** if session logs show consistently low `posted=1` rate with `method=miss` being rare (suggesting the resolver IS finding matches but the DM never sees the suggestion), the gap is narration-skip behavior — file the `!init add` intercept then.

---

## §B — §11.B: SRD index source and CC-BY 4.0 licensing

**Question:** 5e-database (Option 1), Open5e dump (Option 2), or live API (Option 3)?

**Trade-offs:**

Option 3 (live API) is dead on arrival. The §1 decision 2 lock explicitly requires a local deterministic validator. A runtime network call for validation introduces latency, failure modes, and dependency — all against the invariant.

Option 2 (Open5e) and Option 1 (5e-database) contain equivalent SRD content under the same CC-BY 4.0 license. The only meaningful difference is the JSON structure and the SRD-filter field. 5e-database uses `document__slug == "wotc-srd"` for a clean extraction; Open5e requires a different filter. Both are actively maintained; both are standard practice in tabletop tooling.

CC-BY 4.0 requires attribution (author + title + URL + license reference) in the bundled file or accompanying documentation. The SRD 5.1 is released by Wizards of the Coast under CC-BY 4.0 specifically for tool projects like this. Bundling `srd_monsters.json` with a comment block citing the source is sufficient and standard.

**Recommendation: Option 1 (5e-database). Confidence: high.** Jordan's only call here is confirming CC-BY 4.0 bundling is acceptable — which it is for any tool project and requires only an attribution comment in the generated JSON. If there's a preference for Open5e (e.g., Jordan already has a relationship with that project), the format is identical; swap the source in `generate_srd_index.py`.

**Condition to reconsider:** if 5e-database's SRD filter produces incorrect results (non-SRD monsters included, or SRD monsters excluded), switch to Open5e dump before Session 3. Verify by comparing the generated count against the known ~330 SRD monster list.

---

## §C — §11.C: LLM model selection

**Question:** `cloud_router`/Qwen 14B via `task_type="extraction"` (Option 1), local model (Option 2), or skip LLM / Python-only (Option 3)?

**Trade-offs:**

Option 3 (skip LLM) misses the primary use case. The whole F-55 surface 1 motivating example — "Spiny Toad" → "Giant Frog" — is a semantic match that Jaccard token-overlap cannot reach. "Spiny Toad" scores 0.0 against "Giant Frog" on Jaccard. Removing the LLM step reduces #5.1 from a combat-entry assist to a narrow creature-alias look-up with limited DM benefit.

Option 2 (local model) is an operational lever, not a default. If cloud cost or latency is a concern, it's available. Process-lifetime `_LLM_CACHE` means the cost per unique creature name is one call per bot restart — at session scale this is negligible.

Option 1 follows the established `mechanical_hints.py` pattern exactly: `route(messages=[...], task_type="extraction", system_prompt=...)`. The `mechanical_hints.py` pattern is the proven §12 advisory parser shape in this codebase. No new infrastructure required.

**Recommendation: Option 1. Confidence: high.** Consistent with the codebase's established extraction path; low cost per unique name; proven architecture.

**Condition to reconsider:** if session logs show `_llm_suggest` latency exceeding ~2s consistently (visible in telemetry if latency is added to the log line — not currently specced), and the suggestion arrives after the DM has already typed `!init add`, Option 2 becomes worth evaluating. Not a v1 concern.

**Cache poisoning note (see §F):** the `_LLM_CACHE` design stores `None` on exceptions, which poisons the cache for transient failures. This is a v1 fix candidate, not an Option 1 vs Option 2 concern — it applies regardless of model choice.

---

## §D — §11.D: Multi-monster plural handling

**Question:** Defer to v1.x (Option 1), or include in v1 (Option 2)?

**Trade-offs:**

Option 2 adds non-trivial scope: count detection, plural-to-singular normalization, command repetition in the suggestion, count-sanity validation. Each of these is a small spec-level decision that compounds. Session logs will tell us whether DMs narrate plural creatures frequently enough to justify that scope.

Option 1 is the §34 pattern. Ship single-creature; observe. The miss path for "3 goblins" logs `method=miss posted=0` — if this fires constantly, that's the signal to ship plural handling.

**Recommendation: Option 1 (defer). Confidence: high.** This is not a trade-off call; it's the standard single-v1-observe discipline applied correctly.

---

## §E — §11.E: Suggestion UI

**Question:** Informational text only (Option 1), react-emoji approval (Option 2), or Discord interaction button (Option 3)?

**Trade-offs:**

Option 3 (interaction button) is dead on arrival under Track 6 #4 §11.D (permanent lock): the bot cannot autonomously emit `!` commands. An "Apply to combat" button would require the bot to emit `!init madd` on the DM's behalf — a direct §11.D violation and a Doctrine §65 violation. Not a trade-off; a hard reject.

Option 2 (react-emoji ✅/❌) adds ceremony. Under §11.D, a ✅ react cannot cause the bot to emit the command. The DM still has to type the command after reacting. Option 2 = Option 1 + an extra step. The only motivation for Option 2 would be if DMs miss suggestions in `#dm-aside` scroll — but a ✅ react doesn't solve visibility, it only confirms the DM saw the suggestion before manually typing. Net value: zero over Option 1 at the cost of a react handler.

Option 1 is correct. The DM typing the suggested `!init madd` command is the §1b "user approves" step. The §1b chain requires explicit user action before mechanical state changes; a typed command is exactly that explicit action. The code block format makes the command one-line-copy-able from Discord's mobile and desktop clients.

**Recommendation: Option 1. Confidence: high.** No architectural ambiguity; this is the §1b-compliant UI for a validated-suggester in a bot-never-emits context. If DMs report not noticing suggestions, the v1.x response is a persistent suggestion format or periodic re-remind — not a react flow.

---

## §F — Surfaced additions

### §F.1 — Campaign ID in suggestion text (multi-campaign guilds)

**Concern:** If one bot instance serves multiple campaigns in the same guild, the suggestion posts to `#dm-aside` (a single guild channel) without identifying which campaign it belongs to. DMs running two campaigns in one guild would see interleaved suggestions with no source label.

**Assessment:** The suggestion message already includes `input_name` (the narrated creature name) which is campaign-contextual. The `campaign_id` is in the log line but not the suggestion text. Multi-campaign-same-guild is an uncommon configuration given Virgil's current scope. The telemetry log is sufficient for post-hoc attribution.

**Recommendation: Defer to v1.x.** If multi-campaign guilds become a live configuration, add `campaign_id` as a footer line in the suggestion message. One-line change in `_post_srd_suggestion`. No v1 action needed.

---

### §F.2 — `_LLM_CACHE` cache poisoning on transient failure *(v1 fix candidate)*

**Concern:** `_llm_suggest` stores `result = None` in `_LLM_CACHE` on ANY exception — including transient network errors, timeouts, and API rate limits. A one-time hiccup permanently disables LLM resolution for that creature name until bot restart. If "Spiny Toad" mis-fires on its first session appearance due to a 500ms timeout, every subsequent encounter returns cached `None`, and the session-dedup is irrelevant — `resolve()` will permanently fall through to `miss` for that creature.

**Current code:**
```python
except Exception:
    result = None
_LLM_CACHE[key] = result  # ← always writes, including on exception
```

**Proposed fix:** distinguish genuine no-match (LLM returned `{"candidate": "", "confidence": 0.0}`) from transient failure (exception raised). Only cache on LLM response; on exception, skip caching and return None without poison:

```python
try:
    # ... LLM call and parse ...
    result = (candidate, confidence) if candidate else None
    _LLM_CACHE[key] = result  # cache definitive response only
    return result
except Exception:
    return None  # transient failure — don't cache, allow retry next encounter
```

**Recommendation: Address in v1.** The fix is two lines. The behavioral difference matters: a genuine LLM no-match is safe to cache (same LLM won't match the same creature next time); a transient failure is not.

---

### §F.3 — Process-lifetime `_SUGGESTED` dedup and bot restart mid-combat

**Concern:** Bot restart clears `_SUGGESTED`. If the bot restarts mid-combat, a creature that was already suggested may generate a duplicate suggestion.

**Assessment:** This is a non-issue given the `was_new` signal (§11.G). `npc_upsert()` for an already-existing `dnd_npcs` row returns `was_new=False`, so the hook does not fire regardless of `_SUGGESTED` state. The dedup set is secondary protection, not the primary gate. Bot restart mid-combat produces no duplicate suggestions because the `was_new` guard catches re-encounters at the upsert level.

**Recommendation: No action.** Add a spec note in §6 or §10 clarifying that `_SUGGESTED` is secondary to `was_new=False` for restart safety. The spec currently implies the dedup is the primary guard; the `was_new` check is the correct primary.

---

### §F.4 — `narration_verifier` cross-reference claim (spec §10)

**Concern:** Spec §10 claims: "The registered row prevents false `FABRICATED_COMBATANT` violations for this creature." Verification that this claim holds against `narration_verifier.verify_narration()`'s `npcs_canonical` check.

**Assessment:** The claim is correct via two paths:
1. **NPC extractor path (primary):** `npc_upsert()` fires at narration time, creating the `dnd_npcs` row before any `!init` command is issued. By the time the DM types `!init madd` and Avrae responds with an init-list event, the row already exists in `dnd_npcs`. `narration_verifier` finds it there.
2. **`!init madd` cold path (DM skips narration):** `npc_register_avrae_madd()` creates the `dnd_npcs` row from the Avrae init-list event. This fires before the next DM narration turn — `narration_verifier` runs after LLM narration, which is after the Avrae init-list response. Row exists by verification time.

The timing is safe in both paths. The spec's §10 claim holds.

**Recommendation: No action.** Claim verified. If Track 7 #2's `npcs_canonical` query shape changes (e.g., adds a `is_canonical=True` filter), revisit this — but that's a Track 7 #2 concern, not a #5.1 concern.

---

## §G — Test surface review

**Coverage:** 30 tests across 3 files. Proportional to a pure-function resolver (19 tests) + hook integration (6 tests) + data quality (5 tests). No obvious gaps in category coverage.

**Concern 1 — Tests 9 and 10 are mathematically inconsistent and need redesign:**

The spec claims:
- Test 9: `_fuzzy_match("cave giant spider")` → `None` with "Jaccard with 'Giant Spider' = 0.5"
- Test 10: `_fuzzy_match("giant cave spider")` → entry for "Giant Spider" at Jaccard = 0.67

Jaccard token overlap is order-insensitive. Both inputs tokenize to the identical set `{"cave", "giant", "spider"}`. Against "giant spider" = `{"giant", "spider"}`: intersection = 2, union = 3, Jaccard = 2/3 ≈ **0.67** — not 0.5. Both inputs produce the same result: Giant Spider at 0.67, which is above the 0.6 threshold. Test 9's `None` assertion is wrong; both inputs would return Giant Spider.

The spec likely intended to demonstrate a true Jaccard miss (below 0.6). A valid example: `_fuzzy_match("cave toad")` vs "Giant Frog" — tokens `{"cave", "toad"}` ∩ `{"giant", "frog"}` = 0, Jaccard = 0.0, correct miss. Or `_fuzzy_match("dark winged shadow")` — no SRD entry with token overlap > 0.6. Tests 9 and 10 need to be replaced with inputs that actually demonstrate the below-threshold and above-threshold cases as distinct token sets.

**Action in Session 3:** replace tests 9 and 10 with valid examples before implementation. The Jaccard math must be verified against real SRD index entries.

**Concern 2 — Double-log on the success path:**

`resolve()` spec says "always-fire `srd_suggestion:` log line per call." `_build_and_mark()` "emits the telemetry log." `_post_srd_suggestion()` also emits a `srd_suggestion:` log line with `posted=1`. For the success path, this produces two log lines per creature: one from `_build_and_mark` (at which point `posted` status is unknown) and one from `_post_srd_suggestion` (when posting succeeds). The spec's §8 telemetry shape implies a single line per call with a definitive `posted={0|1}` value.

**Action in Session 3:** decide which component owns the success log. Cleanest split: `resolve()` logs `method=exact/fuzzy/llm` with `posted=0` (resolver doesn't know if posting will succeed); `_post_srd_suggestion()` logs `posted=1` when the Discord send completes. Miss and dedup paths log from inside `resolve()` as specced. Two log lines per success, one per miss/dedup. Document the two-line shape in §8.

**Concern 3 — Test 24 (channel not found) doesn't test the log output:**

Test 24: "`#dm-aside` channel not found → hook swallows exception gracefully, no crash." The soft-fail behavior is correct to test, but the test should also assert that the exception is logged (or that no exception propagates from the hook when `dm_aside` is None). As specced, the test only confirms no crash; it doesn't verify the quiet-fail discipline. Minor — the soft-fail is in a try/except block, so "no crash" is always satisfied. Worth adding: assert the function returns without raising when `dm_aside is None`.

---

## §H — Scope honesty review (Doctrine §45)

**§2 "Surface 1 partial closure" language (post-v1.1 patch):** correct and honest. The 6→2-step claim is now qualified as "SRD-match best case, not the average." The homebrew-miss fallback path is explicitly documented. No overclaim here.

**§3 precedence diagram and §7 suggestion text design (three DM choices):** the "Target DM flow" in §2 correctly shows the suggestion as step 2 for an already-in-progress combat. It does not address the new-combat case where the DM still needs to type `!init begin` before `!init madd` makes sense. The `!init begin` reminder is filed in §12 as future work — this is correctly scoped out. However, the §2 flow could note: "assumes `!init begin` already fired; new-combat flow still requires DM to type `!init begin` before the suggested `!init madd`." Not a spec fix — the §12 file is sufficient — but session reviewers should be aware that the 2-step target flow assumes ongoing combat, not fresh combat initiation.

**§10 "Both suggestion AND hydration could fire" edge case:** correctly resolved. Mutual exclusivity at the `status_token` routing level is sound. No overclaim.

**Independence from #5.4 claim:** correct. #5.1 has no runtime dependency on the intent-to-Avrae resolver. It introduces a resolver pattern (`srd_resolver.py`) but is not consumed by #5.4. The claim holds.

**One remaining overclaim candidate — §2 "inaugural §1b implementation":** the v1.1 patch already addressed this, correctly stating "first §1b-explicit implementation written after the §1a/§1b doctrine split" rather than "first §1b ship." The current spec text is accurate. `mechanical_hints.py`, `npc_extractor.py`, `consequence_extractor.py`, and `dnd_knowledge_import.py` are correctly cited as prior §1b canonical instances. No action needed.

---

## Summary of Jordan's calls

| Decision | Recommended option | Confidence | Action |
|----------|--------------------|------------|--------|
| §11.A Hook point | Option 1 (NPC extractor post-upsert) | High | Confirm |
| §11.B SRD index + CC-BY | Option 1 (5e-database, CC-BY attribution in file) | High | Confirm CC-BY bundling acceptable |
| §11.C LLM model | Option 1 (cloud_router / `task_type="extraction"`) | High | Confirm |
| §11.D Multi-monster | Option 1 (defer to v1.x) | High | Confirm |
| §11.E Suggestion UI | Option 1 (informational text, no react/button) | High | Confirm |

## Session 3 pre-conditions (implementation gates)

Before Session 3 begins:
1. §11.A–§11.E locked by Jordan (this review)
2. `srd_monsters.json` generated by running `generate_srd_index.py` against 5e-database (one-time, not runtime)
3. Tests 9 and 10 replaced with valid Jaccard examples (§G concern 1 — fix before writing implementation tests)
4. `_LLM_CACHE` cache-on-exception behavior fixed (§F.2 — v1 fix, small change)
5. Double-log surface documented in §8 (§G concern 2 — spec clarification only, no code)

---

*Review drafted: 2026-05-08. Required reading complete: DOCTRINE.md §1a/§1b/§12/§32/§45/§59, FAILURES.md §F-55/§F-49, TRACK_6_4_SPEC.md §11.D, mechanical_hints.py.*
