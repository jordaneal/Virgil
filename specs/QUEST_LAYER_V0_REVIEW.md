# QUEST_LAYER_V0_REVIEW.md

**Status:** REVIEW — Phase 2 (Path A review pass). Walks all 12 §11 decisions + §1.B alias-vs-migrate sub-decision with trade-offs + recommended defaults + confidence levels. Not a lock. Operator reads, locks decisions, spec flips DRAFT → LOCKED before Session 3.

**Session:** S55 Phase 2 review pass, May 13, 2026
**Spec reviewed:** `/home/jordaneal/virgil-docs/specs/QUEST_LAYER_V0_SPEC.md` (DRAFT)
**Basis:** `planner-scratch/quest_layer_v0_sketch.md`, DOCTRINE §1a/§1b/§17/§59/§76, `NPC_STATE_SYNC_SPEC.md` (§1b second instance), `TRACK_6_5_1_SPEC.md` (§1b first instance), track5_findings_loot_reward.md (LR 36.8% NPC-voice + reward-magnitude data).

**Format per decision:** question restatement → trade-offs table → recommended default + confidence → open axis named (MEDIUM/LOW only).

---

## §1. Inventory note before walking

**§11.5 scope refinement from session brief.** The spec frames §11.5 as a three-candidate decision (DMG / LR-X4 / skeleton-locked). Session brief reframes: candidate (c) — "operator-locked-per-quest via skeleton.md" — is the v0 ship. Candidates (a) and (b) define when emergent-quest auto-calibration fires in v1.x. The §11.5 walk reflects this scoping: confirms (c) at v0 (HIGH confidence), defers (a) vs (b) walk to v1.x emergent-quest spec session.

**§1.B alias-vs-migrate sub-decision.** R4 finding (campaign 17 has zero `dnd_quests` rows) reduces (b) migration cost to near-zero. This shifts the trade-off significantly from the spec's lean — see §3.0 sub-decision walk below before the main §11 walk opens.

**§1.C R4 forward-compat findings (per session brief check).** Walk surfaces one gap (skeleton.md authoring changes mid-campaign produce ghost rows on re-seed). Documented as §1.C refinement in §4 below; does NOT warrant a §11.13 surface decision because the refinement lands in §1.C's "Idempotent" clause without changing the decision space.

**No HALT triggered.** No decision walk surfaced a finding that invalidates v0 architectural shape. §11.12 §1b third-instance walk surfaces a validator-gate nuance worth naming explicitly (cosine-similarity is a UX-correlation layer atop a deterministic slash gate, not a replacement for the deterministic gate) — see §3.M.

---

## §2. Summary table

| Decision | Question | Recommended | Confidence | Notes |
|---|---|---|---|---|
| **§1.B** sub-dec | Alias vs migrate status enum | (b) clean migration | HIGH | R4 makes migration near-zero-cost; see §3.0 |
| §11.1 | Quest source taxonomy at v0 | (a) skeleton + operator /quest add | HIGH | Mirrors consequence S16 |
| §11.2 | Schema extend vs new table | (a) extend additive | HIGH | Surface integrated, additive preserves |
| §11.3 | Offer-trigger predicate | (b) auto-fire with cooldown | MEDIUM | Threshold K=6 is calibration-from-telemetry |
| §11.4 | Acceptance semantics | (a) explicit slash | HIGH | Mirrors Scene Lifecycle §11.N |
| §11.5 | Reward magnitude calibration | (c) skeleton-locked at v0 | HIGH (v0); deferred (v1.x) | v1.x DMG vs LR-X4 = operator + Oracle |
| §11.6 | Reward delivery surface | (d) hybrid #dm-aside + auto-inventory | HIGH | F-39 precedent |
| §11.7 | Paste-detection fuzziness | (b) cosine-similarity ≥0.85 | MEDIUM | Threshold tunable from telemetry |
| §11.8 | Active-quest directive placement | (a) tactical band | MEDIUM | Footer 🗒️ stays for ambient |
| §11.9 | Auto-render cooldown | (a) every turn, concise | HIGH | Same as consequence directive |
| §11.10 | Offer-dialogue source | (c) hybrid skeleton + LLM-fallback | MEDIUM | LLM noise rate unknown until live |
| §11.11 | /quest abandon access | (a) DM-only | HIGH | Mirrors Scene Lifecycle §11.F |
| §11.12 | §1b third-instance candidate | Third instance stands; walk-to-confirm | MEDIUM | Validator-gate nuance — see §3.M |

**Split:** 7 HIGH · 5 MEDIUM · 0 LOW · 0 operator+Oracle required at v0 · 1 deferred operator+Oracle (§11.5 v1.x sub-decision).

---

## §3. Full decision walk

---

### §3.0 — §1.B sub-decision: alias vs clean migration

**Question:** When extending `VALID_QUEST_STATUSES` from `{active, completed, failed}` to v0's five-status set, alias the existing values to the new ones, or migrate existing rows to the new vocabulary?

**Candidates:**
- **(a) Alias** — keep `active` as a valid status; treat as semantic equivalent of `in-progress` at render and write time. `completed` ↔ `delivered` similarly. Add `offered` + `abandoned` as new values. Existing rows unchanged.
- **(b) Clean migration** — UPDATE existing `active` rows → `in-progress`, `completed` → `delivered`. Drop `active` and `completed` from `VALID_QUEST_STATUSES`. New enum is exactly five values.

| Candidate | Pros | Cons | Risk |
|---|---|---|---|
| (a) Alias | Zero migration; back-compat preserved for any external consumer (logs, doc refs, autocomplete labels referencing 'active'); no DB write needed | Two valid names for the same status (translation layer at render and validate); future code must remember to handle both; status enum has 7 valid values not 5 | Drift: code paths handling only `'active'` continue to work, but new code paths handling only `'in-progress'` will miss aliased rows. Bug surface grows over time. |
| **(b) Clean migration** | Single coherent enum surface (exactly 5 values); no translation layer; existing autocomplete + footer + prompt block automatically render the new vocabulary | Requires one-shot migration step (one-line UPDATE per campaign); operator-facing string changes (`/quest list status:active` no longer works after migration) | Migration cost only IF rows exist. R4 finding (campaign 17 has 0 rows) is the dominant data point. Other campaigns may have rows — cross-campaign audit required at migration time. |

**R4 cost-shifting evidence:** Campaign 17 has zero `dnd_quests` rows. Cross-campaign cost ceiling: even if other campaigns each have ~5 rows, total migration is ~25 rows. SQL UPDATE statement runs in milliseconds. No live consumer of the status enum exists in the wild (this codebase is the only consumer).

**Operator-facing string change:** `/quest list status:active` becomes `/quest list status:in-progress`. The status choice enum in `quest_list_cmd` (`discord_dnd_bot.py:5156-5161`) needs the corresponding update. Code change is mechanical; documentation updates with the rename.

**Recommended default: (b) clean migration.**

**Reasoning:** The session brief surfaces R4 as cost-shifting evidence — migration cost is near-zero. The alias path's "translation layer" is a long-term tax (every status comparison must handle both names; new code paths might handle one but not the other). Single coherent enum is the cleaner long-term shape. Migration runs at the same time as the column-additive schema extension (one DDL pass).

**Confidence: HIGH.** Spec's lean was (a) primarily because of "no migration cost" framing; R4 evidence + cross-campaign audit reduces (b)'s cost to negligible. Lean shifts to (b) cleanly.

**Spec amendment implied:** §1.B locked decision flips from (a) alias to (b) migrate. §6 R2 finding updates to reflect new enum exactly. Migration step joins Session 3 implementation checklist as Task 0 (run before schema-extension DDL).

---

### §3.1 — Quest source taxonomy at v0

**Question:** Skeleton-authored only? Operator `/quest add` retained? Advisory-parser extraction?

**Candidates:** (a) skeleton-authored + operator `/quest add`; (b) (a) + advisory-parser-extracted; (c) skeleton-authored only.

| Candidate | Pros | Cons | Risk |
|---|---|---|---|
| **(a) Skeleton + operator** | Existing `/quest add` continues to work; back-compat clean; minimal new surface | Operator can author quests outside the suggester surface — they bypass the §1b pattern entirely | Low — operator-typed quests are operator-authored and don't need the validated-suggester gate; §1a holds (DM authors, engine writes, LLM reads) |
| (b) (a) + advisory-parser | Closes the "LLM proposes new quest from narrative cues" surface — emergent quests at v0 | New advisory parser to build + calibrate; false-positive risk on LLM-extracted quests; introduces a fourth source surface not anchored to a clear corpus signal | High — without corpus-grounded precision data on quest-extraction triggers, the parser ships blind. Mirrors Scene Lifecycle T2 deferral pattern. |
| (c) Skeleton only | Tightest v0 scope; zero new write surfaces | Drops the operator-authored quest path entirely (existing functionality regression); operator must edit skeleton.md to add a quest, then re-seed | High — operational regression on existing `/quest add` integration |

**Recommended default: (a) skeleton-authored + operator `/quest add`.**

**Reasoning:** Mirrors S16 consequence layer's structural-first-extraction-later discipline. Skeleton authoring + operator slash command is the structural primitive; advisory-parser extraction lands in v1.x once seed-skeleton + offer-suggester have produced live signal. Dropping `/quest add` (c) is functional regression with no compensating gain.

**Confidence: HIGH.** Spec lean confirmed. Code's §1 reasoning concurs with sketch's §11.1 lean and R5 consequence-layer pattern review.

---

### §3.2 — `dnd_quests` schema shape: extend vs new table

**Question:** Add columns additively, or create parallel `dnd_quests_v0` table, or kind-tag the consequence ledger?

**Candidates:** (a) extend additive columns; (b) parallel new table; (c) extend `dnd_consequences` with `kind='quest_offer'`.

| Candidate | Pros | Cons | Risk |
|---|---|---|---|
| **(a) Extend additive** | Existing 5 slash commands + footer + prompt block continue to work; back-compat clean; one DDL pass; §17 single-writer discipline extends naturally | New columns NULLable on existing rows (operator-added quests pre-v0 lack `offer_npc_id`, `offered_turn` etc.) | Low — NULL is correct semantic for operator-added pre-v0 quests; renders cleanly in directive block (no voicer annotation when NULL) |
| (b) Parallel new table | Cleanest schema isolation; no NULL columns; migration path explicit | Doubles write paths (`quest_add` writes one table; new `quest_offer` writes another); breaks footer + prompt-block until migration completes; cross-table FK gymnastics | High — splits the §17 single-writer discipline across two tables; reads must JOIN or UNION |
| (c) Consequence-kind reuse | Single ledger surface for "stakes the world tracks" (philosophical alignment with sketch §2 framing) | Two distinct state machines on one table (consequences are capture-only with promote; quests have offered/in-progress/delivered/failed/abandoned lifecycle); different prompt-render shapes; muddies severity vs priority semantics | High — fundamentally incompatible state machines; debuggability falls; consequence layer's audit clarity dilutes |

**Recommended default: (a) extend additive.**

**Reasoning:** Per §1.A reasoning. Existing surface is well-integrated; additive columns preserve back-compat at zero risk. Parallel table multiplies write paths. Consequence-kind reuse philosophically appealing but state-machine incompatible. NULL columns on existing rows are correctly-typed semantic (operator-added quests pre-v0 have no offer voicer or audit timestamps; NULL is true).

**Confidence: HIGH.** Spec lean confirmed.

---

### §3.3 — Offer-trigger predicate

**Question:** When does `compute_quest_offer_suggester` fire?

**Candidates:** (a) every-turn predicate match; (b) (a) + cooldown N turns; (c) operator-initiated only; (d) advisory-parser-extracted scene-classification.

| Candidate | Pros | Cons | Risk |
|---|---|---|---|
| (a) Every-turn match | Maximum surface coverage; never miss an opportunity | Floods `#dm-aside` when party stays at one location across many turns with same NPCs | High — operator-fatigue from card spam; defeats the §1b suggester's value if operator starts ignoring cards |
| **(b) (a) + cooldown** | Coverage with natural anti-spam | Cooldown threshold is calibration-from-telemetry (K=6 starting value); per-NPC scope adds minor state-tracking | Medium — wrong threshold (too high) misses real offer windows; wrong threshold (too low) still produces spam |
| (c) Operator-initiated `/quest suggest` | Zero spam; explicit operator control | Defeats the §1b suggester's value entirely — pattern becomes "operator types command → bot proposes" which is just a quest browser, not a suggester | High — operational regression from sketch's §1b vision; loses ambient quest-surfacing |
| (d) Advisory-parser scene classification | Smartest — LLM identifies "this scene feels like a quest moment" | Requires phrase-vocabulary work + corpus precision data; new advisory parser at v0; ambiguity in what "feels like a quest moment" means | High — premature complexity; mirrors Scene Lifecycle T2 false-positive risk |

**Recommended default: (b) auto-fire with cooldown.**

**Reasoning:** Per §1.J cooldown rationale. Per-NPC scope preserves multi-NPC scenarios. Threshold K=6 starting value aligns with `_STALE_HARD_THRESHOLD` semantic ("stale-rare relative to the same NPC"). Calibrate from `quest_offer_proposed:` telemetry post-ship.

**Confidence: MEDIUM.** Threshold tuning is the open axis. Log signal that would shift recommendation: if telemetry shows >30% of suggester proposals are operator-rejected (declined or ignored), threshold is too low. If telemetry shows >10% of new-quest-mapping moments fired no card, threshold is too high. Tune in v0.1 patch.

---

### §3.4 — Acceptance semantics

**Question:** How does offered → in-progress transition fire?

**Candidates:** (a) explicit `/quest offer accept <id>` only; (b) implicit player-text detection; (c) operator paste auto-accepts.

| Candidate | Pros | Cons | Risk |
|---|---|---|---|
| **(a) Explicit slash** | Deterministic; preserves two-state lifecycle visibility; same shape as Scene Lifecycle T2 deferral discipline | One additional operator action per acceptance (typing the slash after the offer scene renders) | Low — operator already types similar slashes (`/quest deliver`, `/quest fail`); operational cost minimal |
| (b) Implicit player-text | Lower operator friction; "we'll take the job" auto-accepts | Phrase-vocabulary on player text — same false-positive risk Scene Lifecycle T2 deferred; "let's go" or "we agree" out of quest context could mis-trigger | High — corpus-grounded precision data on quest-acceptance phrases doesn't exist; ships blind |
| (c) Operator paste auto-accepts | Single paste = full acceptance; minimum operator friction | Collapses offered → in-progress in one step; loses the structural commitment moment ("the offer was made" vs "the party committed"); damages the two-state lifecycle's narrative function | Medium — the two states model distinct narrative moments; collapsing makes "offered" a degenerate state that fires for one turn between paste and the next operator action |

**Recommended default: (a) explicit slash.**

**Reasoning:** Per §1.H. Mirrors Scene Lifecycle §11.N T2 deferral. Two-state lifecycle (offered → in-progress) preserves the structural commitment moment that mirrors how 5e tables actually run (DM offers a quest in scene; party deliberates; party commits — three distinct moments). v1.x can revisit (b) with corpus data if operator typing friction surfaces as real.

**Confidence: HIGH.**

---

### §3.5 — Reward magnitude calibration source (scope-refined per session brief)

**Question:** Per session brief refinement — at v0, only skeleton-authored rewards ship. The DMG-vs-LR-X4 walk applies to v1.x emergent quests, not v0.

**v0 scope:** skeleton.md's `reward:` field carries operator's calibration; engine renders verbatim.

**v1.x sub-decision (deferred):**
- **(a) DMG-by-level baseline** — DMG p.133 treasure-by-level tables; published 5e mechanical balance
- **(b) LR-X4 corpus pull** — CRD3 reward-magnitude data; empirical real-DM cadence
- (c) Already locked at v0 — operator-authored per quest

| v1.x candidate | Pros | Cons | Risk |
|---|---|---|---|
| (a) DMG-by-level | Published authority; consistent with published 5e encounter wealth assumptions; mechanically-balanced reward economy | May feel mismatched to Matt-cadence player expectations; "correct 5e" can read flat when narrative texture wants weighted moments | Medium — DMG tables assume standard adventure pacing; Matt's narrative pacing diverges from DMG assumptions in CRD3 corpus |
| (b) LR-X4 corpus pull | Empirical real-DM cadence; matches CRD3 expectations; preserves Matt-cadence player feel | May break 5e encounter wealth assumptions; calibration sample is one DM (Matt) at one campaign (CRD3) — generalization unknown | Medium — single-source corpus calibration; risk that Matt-cadence rewards over-grant or under-grant relative to other DM styles |

**Recommended default at v0: (c) skeleton-locked, HIGH confidence.**

**v1.x recommendation: deferred operator + Oracle walk when emergent-quest extraction spec opens.**

**Reasoning:** Per session brief refinement. v0 ships skeleton-authored only; auto-calibration source is moot until emergent quests need machine-generated magnitudes. The DMG-vs-LR-X4 decision matters when v1.x quest extractor proposes new quests without operator-authored reward strings — that's the moment the engine must auto-pick a magnitude. v0 doesn't ship that path; deferred walk is correct discipline.

**Confidence at v0: HIGH** (per session brief: "if confirming (c), this becomes HIGH confidence not no-lean").
**v1.x confidence: operator + Oracle when spec opens.** Both candidates have failure modes; both need separate analysis with Oracle input on which 5e-vs-Matt-cadence trade-off operator wants.

---

### §3.6 — Reward delivery surface

**Question:** When `/quest deliver <id>` fires, what surfaces appear?

**Candidates:** (a) auto-LLM-render of reward scene; (b) `#dm-aside` post with reward summary for operator paste; (c) auto-add reward items to inventory via existing `add_item`; (d) hybrid (b) + (c).

| Candidate | Pros | Cons | Risk |
|---|---|---|---|
| (a) Auto-LLM-render | Smoothest narrative experience — reward scene renders without operator action | Repeats F-39 loot-hallucination failure mode (LLM invents reward details that contradict structural canon); damages narrative authority over reward moment | High — F-39 is anchored precedent; auto-LLM-render of structural rewards historically broke at this surface |
| (b) `#dm-aside` post only | Operator-controlled narration; preserves F-39 fix discipline | Inventory not updated; operator must manually `/giveitem` for gp/items | Medium — operational friction; operator forgetting `/giveitem` produces inventory drift |
| (c) Auto-inventory only | Mechanical truth preserved automatically; `add_item` is §17-disciplined single writer | No narration prompt; operator has to author the reward scene from scratch with no `#dm-aside` reminder | Medium — operator forgets to render the reward moment in narration |
| **(d) Hybrid (b)+(c)** | Mechanical truth auto-applied + narration prompt surfaces; F-39 discipline preserved; minimum operator friction | `reward_summary` must parse cleanly for inventory auto-add; freetext reward summaries (e.g., "the deepest gratitude") get the aside but no auto-inventory | Low — `reward_parsed=0|1` log distinguishes; freetext-only rewards are still operator-aside-narrated |

**Recommended default: (d) hybrid.**

**Reasoning:** Per §1.G. F-39 precedent (loot-hallucination from auto-LLM-render of structural rewards) is anchored failure mode. Hybrid preserves both surfaces — the structural truth (inventory delta) and the narration prompt (operator pastes the suggested NPC-voicer scene). Same architectural shape as Track 4 #2 loot v1.2.

**Confidence: HIGH.**

---

### §3.7 — Paste-detection fuzziness tolerance

**Question:** When operator pastes the suggester's proposed dialogue, what's the match threshold for triggering `quest_offer` write?

**Candidates:** (a) exact match; (b) cosine-similarity ≥0.85; (c) prefix match; (d) tag-based embedded `[QUEST_OFFER:<id>]` token.

| Candidate | Pros | Cons | Risk |
|---|---|---|---|
| (a) Exact match | Zero ambiguity; deterministic | Breaks on operator editing the proposed dialogue (whitespace, punctuation tweaks, replacing a phrase) — common operator behavior | High — exact match defeats the §1b "paste-the-suggestion" UX. Operator who edits will fail detection silently and must use explicit slash. |
| **(b) Cosine-similarity ≥0.85** | Tolerates light edits; ergonomic for operator | Threshold is calibration-bound; off-tone edits could pass when they shouldn't; deterministic-validator clause (§1b) interpretation question | Medium — wrong threshold misclassifies. Calibrate from telemetry. **Validator-gate question — see §3.M for the §1b doctrine walk on this** |
| (c) Prefix match (first 50 chars) | Simple; deterministic | Operator who edits the opener tweaks ("Eldrin scans → Eldrin's eyes scan") breaks detection; opener is the highest-edit-rate section in practice | Medium — opener-edit-frequency makes prefix-match unreliable |
| (d) Tag-based `[QUEST_OFFER:<id>]` | Deterministic; zero ambiguity | Requires operator to type/paste a hidden token; defeats "paste-the-dialogue-as-rendered" UX; the token shows in narration channel which players can see | High — UX regression; token visibility breaks immersion |

**Recommended default: (b) cosine-similarity ≥0.85.**

**Reasoning:** Per §1.E. Tolerates light operator edits without breaking on tweak patterns. Explicit `/quest offer accept <id>` slash is always available as the deterministic fallback (per §11.4). Threshold tunable from `quest_paste_match:` telemetry.

**Confidence: MEDIUM.** Threshold 0.85 is a starting point; open axis is empirical tuning. Log signal that would shift: if telemetry shows >5% false-positive paste detections (operator pasted something unrelated, matched by chance), raise threshold to 0.90. If >10% false-negative (operator pasted with edits, didn't match), lower to 0.80. **See §3.M for the §1b doctrine walk on whether cosine-similarity is a deterministic-enough validator gate.**

---

### §3.8 — Active-quest directive prompt placement

**Question:** Where in `build_dm_context` does the active-quest block render?

**Candidates:** (a) tactical band (AFTER consequence_block, BEFORE scene_lifecycle_block); (b) keep existing early placement (after scene_state_section); (c) both.

| Candidate | Pros | Cons | Risk |
|---|---|---|---|
| **(a) Tactical band** | Aligns quest pressure with consequence pressure; tactical-band placement matches "immediate-stakes directives" ordering; last-instruction-wins favors tactical position | Existing prompt block placement changes; one operator-facing log delta | Low — operator-facing prompt position is internal; no live consumer of the position |
| (b) Keep existing early | No change to prompt structure | Active-quest rendered as "scene framing" context rather than "immediate-stakes pressure" — semantically incorrect | Medium — quests as scene-framing has been the current shape with zero rows rendering; behavior change at v0 is incidental either way |
| (c) Both | Maximum reinforcement | Double-rendering same content; bloats prompt; no compensating gain | High — prompt-size pressure for zero gain |

**Recommended default: (a) tactical band.**

**Reasoning:** Per §1.F. Tactical band semantically aligns with consequence directive (immediate-stakes pressure). Footer 🗒️ surface stays as ambient awareness; the prompt block is the LLM-side pressure. Last-instruction-wins per §2 doctrine favors tactical-band placement.

**Confidence: MEDIUM.** Open axis: if live verify surfaces LLM ignoring tactical-band quest directive while honoring tactical-band consequence directive, placement may need adjustment. Log signal: directive_emit shows fire counts, but narration-side honor rate isn't directly measurable without operator observation.

---

### §3.9 — Quest auto-render cooldown vs every-turn

**Question:** Does `compute_active_quest_directive` fire on every exploration/social turn?

**Candidates:** (a) every turn, one concise block; (b) cooldown N turns between fires; (c) tier-escalation (quiet for stable, strong for aging).

| Candidate | Pros | Cons | Risk |
|---|---|---|---|
| **(a) Every turn** | Ambient quest awareness on every turn; LLM never forgets outstanding commitments | Adds ~300-500 chars to every prompt where quests are in-progress | Low — prompt-budget headroom is large (R6 baseline shows headroom); selective-fire when zero active quests keeps 0-quest case at 0 cost |
| (b) Cooldown | Lower prompt-size cost when active quests exist | LLM forgets between fires; narrative continuity weakens; aging-without-progress signal lost | Medium — quest pressure is fundamentally different from offer pressure (the latter is "propose moments"; the former is "ambient awareness") |
| (c) Tier-escalation | Sophisticated — quiet for stable progress, strong when stagnating | Requires "stale-quest" tracking primitive that doesn't exist yet; v1.x territory | Medium — premature for v0; can ship as v1.x calibration if "quest staleness" surfaces as friction |

**Recommended default: (a) every turn, concise block.**

**Reasoning:** Per §1.F. Quest pressure is ambient — LLM should know what's outstanding on every turn. Cap at 3 rendered (with overflow notice) keeps the block small; selective-fire when zero active quests keeps cost at zero for the 0-quest case. Same shape as consequence directive (every-turn, severity-capped).

**Confidence: HIGH.**

---

### §3.10 — Offer-dialogue source

**Question:** Where does the suggester's proposed dialogue text come from?

**Candidates:** (a) static skeleton-authored only; (b) LLM-generated at suggester time; (c) hybrid skeleton + LLM-fallback.

| Candidate | Pros | Cons | Risk |
|---|---|---|---|
| (a) Static skeleton only | Predictable; zero LLM cost per suggester; zero hallucination risk | Operator must author dialogue for every quest hook; emergent quests (v1.x) have no path | Medium — operator authoring burden; v1.x emergent quests can't use static-only path |
| (b) LLM-generated only | Reusable across quests; no operator authoring per quest; covers v1.x emergent path | Per-suggester LLM call (~500ms, ~$0.001); off-tone risk; LLM may invent NPC behavior inconsistent with canonical NPC personality | High — quality variance; operator may reject many cards for tone mismatch |
| **(c) Hybrid** | Operator-authored canonical when present; LLM fallback for unauthored cases; v1.x emergent quests get LLM path "for free" | Both costs (LLM noise when fallback fires); branching shape | Medium — noise rate of LLM fallback is unknown until live |

**Recommended default: (c) hybrid.**

**Reasoning:** Per §1.E + §4. Skeleton-authored dialogue is canonical when present; LLM fallback covers operator-doesn't-author-every-line case AND v1.x emergent-quest dialogue. AUTHORITATIVE framing on the LLM fallback prevents drift (S22 #2 precedent).

**Confidence: MEDIUM.** Open axis: LLM fallback noise rate. Log signal that would shift to (a): if operator rejects >40% of LLM-fallback cards for tone mismatch within first 20 fires, fall back to static-only and require skeleton.md dialogue for every hook.

---

### §3.11 — `/quest abandon` access — DM-only or player-accessible

**Question:** Who can abandon a quest?

**Candidates:** (a) DM-only; (b) player-accessible.

| Candidate | Pros | Cons | Risk |
|---|---|---|---|
| **(a) DM-only** | Mirrors `/quest add`, `/quest deliver`, `/quest fail`; mirrors Scene Lifecycle `/compress`; consistent DM-narrative-authority discipline | Players who want to declare abandonment must signal in-character first | Low — players signaling abandonment intent through normal in-character speech IS the intended UX; operator decides whether to honor |
| (b) Player-accessible | Lower operator friction when player intent is clear | Players can force quest mutations the DM didn't intend; CRD3 empirical norm is Matt-controls-state | Medium — player-forced state mutation breaks the "DM authors structural state" invariant |

**Recommended default: (a) DM-only.**

**Reasoning:** Per §1.E. Mirrors Scene Lifecycle §11.F `/compress` DM-only discipline. Quest abandonment is a DM-narrative-authority decision; players signal intent through in-character speech, operator decides.

**Confidence: HIGH.**

---

### §3.M (§11.12) — §1b third-instance candidate evaluation

**Question (per session brief):** Quest suggester is proposed as §1b third project instance (joins Track 6 #5.1 SRD suggester + S41 NPC State-Sync). Walk surfaces two sub-questions:

**(a) Architectural shape match.** Does the quest suggester match the §1b anchored pattern (bot proposes via `#dm-aside` / deterministic gate validates / DM approves by paste / system executes)?

**(b) Validator-gate question.** Is paste-detection-via-cosine-similarity the right validator gate, or does it weaken the §1b "deterministic-validator" clause?

#### §3.M.a — Shape match walk

**Reference pattern (anchored Track 6 #5.1 + S41):**
- **Bot proposes** via `#dm-aside` post (non-Avrae channel by design)
- **Deterministic Python gate** validates proposal is safe to suggest BEFORE post
- **DM approves by paste** of suggested content into the appropriate destination channel
- **Executor receives human-typed input** and acts (Avrae in S26/S41; engine SQLite in this case)

**Quest suggester shape:**
- **Bot proposes** `[QUEST OFFER PROPOSED]` card to `#dm-aside` ✅
- **Deterministic gate** validates proposal BEFORE post: predicate check (mode in {social,exploration}, voicer match, cooldown clear, unoffered quest available, current NPC at location) ✅ — all checks are deterministic Python (boolean predicates over SQLite query results)
- **DM approves by paste** of offer dialogue into `#dm-narration` (or by explicit `/quest offer accept <id>` slash) ✅
- **Executor receives input:** engine SQLite write (`quest_offer` helper) — NOT Avrae ⚠️

**Executor surface difference:** S26 (SRD suggester) and S41 (NPC State-Sync) both dispatch through Avrae as executor — the paste lands in `#dm-narration`, Avrae parses the human-typed `!` command, Avrae mutates its state. Quest suggester's executor is the engine's SQLite layer — the paste lands in `#dm-narration`, the engine's paste-detection matches the dialogue against the proposed seed, the engine writes the `dnd_quests` row.

**Is the executor difference architecturally meaningful for §1b?**

DOCTRINE §1b's pattern doesn't specify Avrae as the executor — the doctrine says "mechanical authority (Avrae or SQLite) executes the validated decision." The SRD and State-Sync precedents happen to use Avrae because their state mutations target Avrae's combat state. Quest layer's state mutations target the engine's quest ledger (SQLite). Both are "mechanical authority" in the doctrine's sense.

**Shape match verdict: ✅ pattern holds.** The bot-proposes-deterministic-gate-DM-approves-executor-executes shape repeats. The executor identity (Avrae vs SQLite) is incidental to the doctrine.

#### §3.M.b — Validator-gate question walk

The §1b doctrine says: "a deterministic Python layer validates the output before anything mechanically binds." In SRD and State-Sync precedents, the validators are:
- **SRD suggester:** `srd_resolver.py` index lookup — string-key lookup against a static JSON index. Strictly deterministic.
- **NPC State-Sync:** `gate_*` paths + Case A/B mid-combat split — boolean predicates over engine state. Strictly deterministic.

**Quest suggester has TWO validators at different layers:**

1. **Pre-post validator** (matches §1b's anchored pattern): the predicate check that gates whether to post the card at all (mode, voicer match, cooldown, unoffered quest). Pure boolean. Deterministic.

2. **Post-paste validator** (the new layer): cosine-similarity match between operator paste and suggester's `offer_dialogue_seed`. This is the question.

**Is post-paste cosine-similarity a §1b-compliant gate?**

Two readings:

**Reading 1 — cosine-similarity is a deterministic gate.** Given a threshold and an input, output is binary (matched or not). The threshold itself is a deterministic decision rule. The doctrine's "deterministic Python layer" is satisfied — the layer is deterministic; what's calibration-bound is the threshold parameter, which is no different from severity caps (consequence_upsert refuses severity > 3 with a deterministic threshold). Reading-1 verdict: third-instance stands.

**Reading 2 — cosine-similarity introduces calibration-bound softness.** SRD index lookup has zero calibration surface (name is in the index or it isn't). `gate_*` paths have zero calibration surface (state is sync-ready or it isn't). Cosine-similarity at 0.85 is a tuned heuristic — wrong tune produces wrong gate. The §1b doctrine's deterministic-validator clause has stricter intent than "deterministic given parameters" — it means "deterministic given the input, with no calibration drift surface." Reading-2 verdict: third-instance candidate weakens the doctrine; file as candidate awaiting refinement.

**Cleaner framing — the explicit slash is the canonical gate:**

The quest suggester has TWO acceptance paths:
- **(i) Paste-detection → `quest_offer` write** (cosine-similarity gate)
- **(ii) Explicit `/quest offer accept <id>` slash → `quest_offer` + `quest_accept` write** (deterministic slash command)

Path (ii) is strictly deterministic — the slash command's `quest_id` argument is the gate. Path (i) is a UX-convenience layer that ALSO routes to the same engine write (via cosine-similarity match).

**If path (ii) is treated as the canonical §1b gate**, the doctrine is preserved cleanly: the deterministic gate is the slash command, and cosine-similarity is an additional ergonomic surface that surfaces the same decision via a softer signal. The §1b pattern is maintained by the slash; cosine-similarity is auxiliary.

**Reading-3 framing — canonical-slash + auxiliary-paste-detection:**
- The deterministic gate (per §1b doctrine) is `/quest offer accept <id>`.
- Cosine-similarity paste detection is an auxiliary UX surface that also triggers the same engine write — but is gated by a calibrated threshold.
- The §1b doctrine is preserved by the canonical slash; cosine-similarity is layered on top as a convenience.

**Verdict — recommend Reading-3 framing:** Third-instance anchoring stands IF the spec is amended to clarify the canonical-slash-vs-auxiliary-paste-detection distinction. The explicit slash is the deterministic gate; cosine-similarity is auxiliary ergonomics.

**Confidence: MEDIUM — walk-to-confirm.** Operator confirms Reading-3 framing, OR escalates to Oracle if §1b doctrine should not stretch to "canonical-slash + auxiliary-paste-detection" as a legitimate pattern.

**Implication if Reading-3 confirmed:** spec §11.7 walk should note that cosine-similarity is auxiliary, not the §1b gate. The deterministic gate is the explicit slash. §11.12 third-instance anchoring stands.

**Implication if Reading-3 rejected (Reading-2 holds):** drop cosine-similarity entirely; explicit slash is the only acceptance path. Spec §11.7 becomes moot; v0 ships with `/quest offer accept <id>` as the only acceptance trigger. Operator-paste-without-slash produces no state write; operator must follow paste with slash.

**Spec amendment implied (if Reading-3 confirmed):** §11.7 walk and §1.E description add the canonical-slash-vs-auxiliary clarification. §11.12 anchoring statement notes "third instance via canonical slash; cosine-similarity is auxiliary UX layer, not the §1b deterministic gate."

---

## §4. R4 forward-compat check for `/quest seed-skeleton`

**Per session brief check:** does spec's §1.C shape correctly handle (a) idempotent re-seed, (b) skeleton.md authoring changes, (c) cross-campaign safety?

**(a) Idempotent re-seed.** ✅ Spec §1.C: "Idempotent (skips hooks already in DB by title+skeleton_origin=1 match)." Dedup key: `(campaign_id, title, skeleton_origin=1)`. Re-running seed-skeleton with no skeleton.md changes is a no-op. **Clean.**

**(b) Skeleton.md authoring changes mid-campaign.** ⚠️ **Gap surfaced.** Three sub-cases:

- **Add new hook:** new title doesn't match existing dedup tuple → new row inserted. ✅ Clean.
- **Remove a hook:** existing row stays (not deleted by seed-skeleton). Quest persists in DB at whatever status. ✅ Clean — removed hooks don't disappear from quest state automatically; operator can `/quest delete` or `/quest abandon` if intended.
- **Edit existing hook title:** old row (with old title) stays as `skeleton_origin=1`. New row (with new title) inserts. **Ghost-row gap.** Operator now has two rows for the "same" quest — the old title's row at `status='offered'` and a new row also at `status='offered'`.

**Severity of (b) gap:** Medium-low. Edit-hook-title mid-campaign is a rare operator action (skeleton.md is mostly written once at campaign start). The fix path is operator `/quest delete <old_id>` after re-seed. Documentation note in seed-skeleton's success message ("if you edited an existing hook title, the old row is still present — use /quest delete to remove") closes the gap.

**(c) Cross-campaign safety.** ✅ Spec uses `WHERE campaign_id=?` in all helpers. Seed-skeleton uses `campaign_id` from `get_active_campaign(guild_id)` at invocation time. Cross-campaign isolation per §17 single-writer + scoped helpers. **Clean.**

**Surfacing:** §1.C should add the (b) edit-hook-title note to its "Idempotent" clause. Not a new §11 decision — clarification of the existing decision. Single-line spec amendment.

**Recommended §1.C amendment text:**
> Idempotent (skips hooks already in DB by `(campaign_id, title, skeleton_origin=1)` match). Edit-hook-title mid-campaign: the renamed hook inserts as a new row; the original-title row persists (operator can `/quest delete` to remove). Removed-hook-from-skeleton: existing row stays at whatever status (no auto-delete). Both cases are non-disruptive at runtime; operator-controlled cleanup.

---

## §5. Operator + Oracle decisions

**At v0:** none required. All §11.1–§11.12 decisions either land at HIGH confidence per Code's lean, or at MEDIUM with a named open axis tunable from post-ship telemetry.

**Deferred to v1.x:** §11.5 sub-decision (DMG-by-level vs LR-X4 corpus pull) is operator + Oracle when emergent-quest extraction spec opens. Not a v0 walk.

**§11.12 §1b third-instance walk:** Code recommends Reading-3 framing (canonical-slash deterministic gate + cosine-similarity auxiliary ergonomics). Operator confirmation requested — if Reading-3 rejected, Reading-2 path drops cosine-similarity entirely. Both shapes are implementable; operator's call on whether to stretch §1b doctrine to "canonical + auxiliary" framing.

---

## §6. Summary of recommended defaults

| Decision | Recommended | Confidence | Spec implication |
|---|---|---|---|
| §1.B sub-dec | (b) clean migration | HIGH | §1.B locked recommendation flips alias→migrate; Session 3 implementation Task 0 |
| §11.1 | (a) skeleton + operator /quest add | HIGH | Spec lean confirmed |
| §11.2 | (a) extend additive | HIGH | Spec lean confirmed |
| §11.3 | (b) auto-fire with cooldown K=6 | MEDIUM | Threshold tunable; calibrate from telemetry |
| §11.4 | (a) explicit slash | HIGH | Spec lean confirmed |
| §11.5 | (c) skeleton-locked at v0 | HIGH (v0) | v1.x DMG vs LR-X4 deferred to operator+Oracle when emergent ships |
| §11.6 | (d) hybrid #dm-aside + auto-inventory | HIGH | Spec lean confirmed |
| §11.7 | (b) cosine-similarity ≥0.85 (auxiliary) | MEDIUM | Threshold tunable; canonical-gate is the slash per §11.12 walk |
| §11.8 | (a) tactical band | MEDIUM | Footer 🗒️ stays for ambient |
| §11.9 | (a) every turn, concise | HIGH | Spec lean confirmed |
| §11.10 | (c) hybrid skeleton + LLM-fallback | MEDIUM | LLM noise rate is open axis |
| §11.11 | (a) DM-only | HIGH | Spec lean confirmed |
| §11.12 | Third-instance stands (Reading-3 framing) | MEDIUM | Spec amends §1.E/§11.7 to clarify canonical-slash + auxiliary-cosine |

**HIGH (no synthesis pressure, proceed with recommended):** §1.B sub-dec, §11.1, §11.2, §11.4, §11.5 v0, §11.6, §11.9, §11.11 (8 decisions)

**MEDIUM (operator attention helpful, open axis named):** §11.3, §11.7, §11.8, §11.10, §11.12 (5 decisions)

**Operator + Oracle required at v0:** 0
**Deferred operator + Oracle (v1.x):** 1 (§11.5 (a) vs (b) when emergent quests ship)
**Walk-to-confirm:** 1 (§11.12 — Reading-3 framing for §1b third-instance)
**Spec amendments implied:** §1.B (alias → migrate), §1.C (idempotent clause refinement), §1.E + §11.12 (canonical-slash + auxiliary-cosine framing)

---

## §7. Surface additions

**No §11.13 surfaced.** The 12 §11 decisions plus the §1.B sub-decision cover the v0 decision space comprehensively. Walking did not expose a 13th question the spec doesn't address.

**Spec refinements (not new §11 decisions):**
- §1.B locked recommendation update (alias → migrate)
- §1.C "Idempotent" clause refinement (edit-hook-title + remove-hook behavior)
- §1.E + §11.7 + §11.12 canonical-slash + auxiliary-cosine framing clarification

---

## §8. Handoff

| Field | Value |
|---|---|
| **Review doc** | `/home/jordaneal/virgil-docs/specs/QUEST_LAYER_V0_REVIEW.md` |
| **PC mirror** | `/cygdrive/c/Users/Jordan/Documents/Virgil Project/specs/QUEST_LAYER_V0_REVIEW.md` ✅ pushed |
| **Decisions walked** | 12 §11 (§11.1–§11.12) + 1 sub-decision (§1.B alias-vs-migrate) = 13 total |
| **HIGH confidence** | 8 (§1.B sub-dec, §11.1, §11.2, §11.4, §11.5 v0, §11.6, §11.9, §11.11) |
| **MEDIUM confidence** | 5 (§11.3, §11.7, §11.8, §11.10, §11.12) |
| **LOW confidence** | 0 |
| **Operator + Oracle at v0** | 0 |
| **Deferred operator + Oracle (v1.x)** | 1 — §11.5 (a) DMG vs (b) LR-X4 when emergent quests ship |
| **Walk-to-confirm** | 1 — §11.12 Reading-3 framing (canonical-slash + auxiliary-cosine) |
| **§11.13 surfaced** | None |
| **R4 forward-compat findings** | (a) idempotent re-seed ✅ clean; (b) skeleton.md edit-hook-title surfaces ghost-row gap (medium-low severity, documentation-only fix) → §1.C clause refinement; (c) cross-campaign safety ✅ clean |
| **Spec amendments implied (Session 3 prep)** | §1.B (alias→migrate), §1.C (idempotent clause), §1.E + §11.7 + §11.12 (canonical-slash + auxiliary-cosine framing) |
| **HALT escalations** | 0 — no walk surfaced an invalidation of v0 architectural shape |
| **Next session** | Session 3 = implementation. Operator confirms §11.12 Reading-3 (walk-to-confirm), confirms §11.5 v0 (c) skeleton-locked, locks all MEDIUM decisions per recommended default (or specifies override). Spec flips DRAFT → LOCKED with three amendments. Session 3 model recommendation: Sonnet medium (templated implementation against mature §59 sibling pattern + §1b third-instance anchored at this review). |

---
