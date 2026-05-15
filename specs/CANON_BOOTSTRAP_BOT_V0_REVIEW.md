# CANON_BOOTSTRAP_BOT_V0_REVIEW.md

**Status:** REVIEW — Phase 2 (Path A review pass). Walks all 12 §11 decisions with trade-offs + recommended defaults + confidence levels. Not a lock. Operator reads, locks decisions, spec flips DRAFT → LOCKED before Session 3.

**Session:** N-10 Path A Phase 2, May 14, 2026
**Spec reviewed:** `/home/jordaneal/virgil-docs/specs/CANON_BOOTSTRAP_BOT_V0_SPEC.md` (DRAFT)
**Basis:** `planner-scratch/canon_bootstrap_bot_v0_sketch.md`, DOCTRINE §1a / §1b / §17 / §59 / §76, `QUEST_LAYER_V0_SPEC.md` LOCKED + v0.1 patch (§1b third instance), `COMPOSITION_LAYER_V0_SPEC.md` LOCKED + v0.x patch (§1b fourth instance), `NPC_STATE_SYNC_SPEC.md` LOCKED (§1b second instance), `TRACK_6_5_1_SPEC.md` LOCKED (§1b first instance), corpus findings (LR/EC/TM/CC).

**Format per decision:** question restatement → candidates → trade-offs table (pros / cons / risk per candidate) → recommended default + confidence → open axis named (MEDIUM/LOW only).

---

## §1. Inventory note before walking

**No HALT triggered.** No decision walk surfaced a finding that invalidates v0 architectural shape. Two §11 decisions (§11.8 faction storage, §11.9 NPC pronouns) carry SCHEMA-COUPLING trade-offs surfaced by Phase 1 R6 recon (gaps: `dnd_factions` table doesn't exist, `dnd_npcs.pronouns` column doesn't exist). Both have clean workarounds preserving v0 scope; operator can flip routing if they want to bundle schema work into N-10. See §3.8 + §3.9 deep walks.

**§11.12 (Skeleton ↔ DB divergence) is the only genuine no-confident-lean decision.** Spec flagged as LOW confidence; sketch had no lean. Walk surfaces (a) / (b) / (c) trade-offs explicitly. *Code's lean stays (c) defer to v1.x* unless operator has strong preference. See §3.12 deepest walk.

**No §11.13 surfaced.** Walk produced no NEW architectural decision worth a §11 slot. Three small edge cases (cross-session canonical_name collision; LLM-output-failure escape hatch; bootstrap session timeout) are minor UX details addressable in implementation phase; filed as §12 forward-files. See §7.

**Sub-decision sweep.** No §1-level sub-decisions analogous to Quest Layer's §1.B alias-vs-migrate or Composition Layer's §11.13 cascade-delete surfaced. The spec's §1.A through §1.L recommendations all stand at REVIEW; no walk pressure to flip a §1 lean.

**Forward-coupling note (per session brief).** §11.9 outcome shapes N-4 / S68 migration recon. If §11.9 locks (a) prose-fold, N-4 must treat "bootstrap-origin NPCs have pronouns in first sentence of description" as the EXPECTED starting state for the migration pass, not edge case. Surfaced in §3.9 walk.

---

## §2. Summary table

| Decision | Question | Recommended | Confidence | Notes |
|---|---|---|---|---|
| §11.1 | Premise storage column | (a) new `premise` column | HIGH | Avoids muddying `world_notes` or orphaned `current_scene` |
| §11.2 | Bootstrap command integration | (a) separate `/bootstrap` slash | HIGH | Preserves opt-in semantics |
| §11.3 | Premise input shape | (a) single-shot slash arg | HIGH | Option-3 authoring constraint |
| §11.4 | Re-roll semantics | (a) soft-reroll unlimited | MEDIUM | Loop-pathology signal would shift to (c) cap |
| §11.5 | Idempotency on re-run | (a) error at v0 | HIGH | Observed-friction gate for v1.x expansion |
| §11.6 | Premise rendering in main prompt | (a) low-tactical-band | MEDIUM | Position adjustable post-Session 2 |
| §11.7 | Skeleton.md write shape | (a) structured markdown | HIGH | Parser-compatible per R2 |
| §11.8 | **Faction storage at v0** | (a) skeleton.md only | HIGH | Authoring-runtime decoupling preserved; S69 introduces table — see §3.8 |
| §11.9 | **NPC pronouns at v0** | (a) prose-fold | HIGH | Ship-sequencing discipline; N-4 migration coupling noted — see §3.9 |
| §11.10 | Operator field-override | (a) `/bootstrap manual <field>:<value>` | HIGH | Standard slash-arg shape |
| §11.11 | Sequence order | (a) factions first | MEDIUM | Operator world-building preference could shift |
| §11.12 | **Skeleton ↔ DB SoT on divergence** | (c) defer to v1.x | LOW | Genuine uncertainty — see §3.12 |

**Split:** 7 HIGH · 4 MEDIUM · 1 LOW · 0 operator+Oracle required at v0.

---

## §3. Full decision walk

---

### §3.1 — Premise storage column

**Question:** Add new `premise` column to `dnd_campaigns`, or fold into existing `world_notes`, or fold into orphaned `current_scene`?

**Candidates:**
- **(a) New `premise TEXT DEFAULT ''`** — additive column.
- **(b) Fold into existing `world_notes`** — unused-by-spec column.
- **(c) Fold into orphaned `current_scene`** — vestigial post-S67 F-016 closure.

| Candidate | Pros | Cons | Risk |
|---|---|---|---|
| **(a) New column** | Explicit field purpose; clean §76 audit (3/4 verdict per spec §7); no semantic collision with existing fields | One ALTER TABLE migration step at engine init | Low — additive migrations are routine (S65.1 added quest tuples, S67 added WAL pragma) |
| (b) Fold into `world_notes` | Zero schema delta | `world_notes` has no documented semantics; folding muddies future use; reads currently access nothing from this column (no readers — silent dead-state surface) | Medium — semantic ambiguity; future use of `world_notes` for actual notes (DM private annotations, system-derived facts) would collide |
| (c) Fold into `current_scene` | Reuses already-orphaned column (S67 retired writes); zero schema delta | Repurposes a column whose name actively misleads (premise ≠ current scene); creates a §17 confusion if `current_scene` ever gets reactivated; the column is *vestigial*, not *available* | High — repurposing an orphan column is worse than dropping or replacing it; future engineers/agents would read `current_scene` field expecting scene content |

**Recommended default: (a) new column.**

**Reasoning:** Per spec §1.A. The premise has clear purpose and semantics; an explicit column is the cleanest representation. Folding into `world_notes` muddies future use of that column; folding into `current_scene` actively misleads. The migration cost is one DDL statement at engine init, indistinguishable from the WAL/FK pragma block already shipping.

**Confidence: HIGH.** Spec lean confirmed.

---

### §3.2 — Bootstrap command integration

**Question:** `/bootstrap` separate from `/newcampaign`, or folded in, or as a flag?

**Candidates:**
- **(a) Separate `/bootstrap` slash** — operator runs `/newcampaign` then `/bootstrap`.
- **(b) `/newcampaign` triggers bootstrap automatically** — coupled.
- **(c) `/newcampaign --bootstrap` flag** — explicit one-shot coupling.

| Candidate | Pros | Cons | Risk |
|---|---|---|---|
| **(a) Separate slash** | Preserves opt-in (operator may want campaign-without-bootstrap for imports / hand-authoring); decouples campaign-row creation from multi-card authoring session; matches how operator already runs structured workflows (`/newcampaign` → `/bindchar` → `/play`) | One additional operator step | Low — operator already chains 3+ slashes for campaign onboarding |
| (b) Auto-fire on `/newcampaign` | Single-command onboarding | Operator who has prior skeleton.md or wants to hand-author hits bootstrap unwanted; campaign-row creation becomes blocking on bootstrap completion | High — coupling makes `/newcampaign` heavyweight and unrecoverable mid-session |
| (c) `--bootstrap` flag | Explicit opt-in; saves one slash | Slash-flag pattern is uncommon in the project (Discord slash arg of type bool is awkward UX); behavior change inside `/newcampaign` based on flag adds branching | Medium — flag-based command behavior change increases handler complexity for marginal UX gain |

**Recommended default: (a) separate slash.**

**Reasoning:** Per spec §1.B. Opt-in preservation is load-bearing. The "two-step onboarding" (`/newcampaign` + `/bootstrap`) is no more friction than the existing three-step flow (`/newcampaign` + `/bindchar` + `/play`).

**Confidence: HIGH.** Spec lean confirmed.

---

### §3.3 — Premise input shape

**Question:** Single-shot slash arg, multi-card clarification dialogue, or Discord Modal?

**Candidates:**
- **(a) Single-shot slash arg** — `/bootstrap premise:"..."`.
- **(b) Multi-card clarification** — bot asks 3-4 follow-up questions before card sequence opens.
- **(c) Discord Modal** — popup form with structured input fields.

| Candidate | Pros | Cons | Risk |
|---|---|---|---|
| **(a) Single-shot** | Minimum friction; matches option-3 authoring constraint ("2-3 sentences once"); standard slash-arg shape | Premise quality depends on operator's single-shot wording; no structured prompting for genre/tone/character | Low — operator can rerun if first premise produces poor card proposals (see §11.5 idempotency walk — would require `/bootstrap end` first, but path exists) |
| (b) Multi-card clarification | Higher-quality premise capture (structured genre / tone / character / antagonist questions); bot can prompt for clarity | 2-3 turns of operator typing before any productive card output; violates option-3 framing | Medium — operator-fatigue before the actual authoring work begins; UX regression vs slash arg |
| (c) Discord Modal | Multi-field structured input in one popup; UX-rich | Modal API is heavier to implement and test; not currently used elsewhere in the project | Medium — new UI primitive for marginal UX gain; +complexity for the Session 3 implementation surface |

**Recommended default: (a) single-shot slash arg.**

**Reasoning:** Per spec §1.C + sketch §11.1 HIGH-confidence lean. Option-3 authoring constraint is binding: operator confirmed willingness for 2-3 sentences once; more compounds friction.

**Confidence: HIGH.**

---

### §3.4 — Re-roll semantics

**Question:** Soft-reroll (with prior-rejected hint) or hard-reroll (fresh)? Max rerolls per card?

**Candidates:**
- **(a) Soft-reroll, unlimited** — LLM call with `"operator rejected previous proposal; produce different shape"` hint.
- **(b) Hard-reroll, unlimited** — LLM call with same prompt; relies on temperature for variation.
- **(c) Soft-reroll capped at N** — after N rerolls, force `/bootstrap accept` or `/bootstrap skip`.
- **(d) Hard-reroll capped at N** — same cap, no rejection hint.

| Candidate | Pros | Cons | Risk |
|---|---|---|---|
| **(a) Soft-reroll, unlimited** | Bot learns from rejection (lower repeat rate); operator has full control to keep trying; uses cheap extraction-tier LLM call (~1s) | Loop pathology possible if operator keeps rejecting (rare but unbounded) | Medium — unbounded session if operator can't articulate what they want; mitigated by `/bootstrap manual` escape hatch (§11.10) and `/bootstrap skip` |
| (b) Hard-reroll, unlimited | Same as (a) without rejection-hint complexity | Repeat-output rate higher (same prompt → similar LLM output); operator wastes calls on identical proposals | Medium — UX regression vs (a) |
| (c) Soft-reroll capped | Bounds loop pathology | Cap chosen arbitrarily; operator hit-the-cap forced into accept/skip without satisfying answer | Medium — wrong cap (too low) frustrates; too high doesn't bound much |
| (d) Hard-reroll capped | Bounded, low complexity | Inherits (b)'s repeat-output issue | High — combines (b) and (c) downsides |

**Recommended default: (a) soft-reroll, unlimited.**

**Reasoning:** Per spec §1.B + sketch §11.4 MEDIUM lean. Rerolls are cheap (~1s extraction-tier LLM call). The loop-pathology risk is mitigated by two escape hatches already in scope: `/bootstrap manual <field>:<value>` (operator overrides specific field) and `/bootstrap skip` (drop card and advance). Operators who can't articulate what they want would hit either escape rather than loop.

**Confidence: MEDIUM.** Open axis: **observed loop-pathology rate in live signal.** If `reroll_count` telemetry shows >5 rerolls on a single card occurring in >10% of bootstrap sessions, flip to (c) with N=5. Tune in v0.1 patch from `bootstrap_card_directive: reroll_count=N` log.

---

### §3.5 — Idempotency on re-run

**Question:** `/bootstrap` on a bootstrap-complete campaign — error, expansion mode, or full re-run with confirmation?

**Candidates:**
- **(a) Error at v0** — block re-run; no support for expansion.
- **(b) Expansion mode** — re-run proposes only NEW elements without touching prior canon.
- **(c) Full re-run with explicit confirmation** — wipes prior bootstrap canon, starts over.

| Candidate | Pros | Cons | Risk |
|---|---|---|---|
| **(a) Error at v0** | Maximum safety; operator-approved canon never silently overwritten; expansion-mode v1.x driven by observed friction | Operator who wants to add more canon must edit skeleton.md directly OR use `/quest add` / `/npc seed` etc. slashes | Low — existing manual paths cover the gap; v1.x expansion mode is observed-friction-gated |
| (b) Expansion mode | Bot-curated mid-campaign canon expansion | Detection logic for "what's already approved" must be exact (skeleton_origin=1 rows AND skeleton.md H3 entries AND in-memory state); divergence between detection and reality risks silent overwrite | High — premature complexity; expansion mode is v1.x feature on observed signal |
| (c) Full re-run with confirmation | Operator-driven full reset for "premise changed, start over" cases | Confirmation UX is friction-heavy; if confirmation fails to convey the destructive scope, operator could accidentally wipe canon | High — destructive operation gated by Discord-slash confirmation has historical risk (cf. §19 two-gate destructive pattern; one slash isn't enough) |

**Recommended default: (a) error at v0.**

**Reasoning:** Per spec §1.J + sketch §11.5 HIGH lean. Defers the canon-management surface to v1.x with observed-friction gate.

**Confidence: HIGH.**

---

### §3.6 — Premise rendering in main prompt

**Question:** Does premise render in `build_dm_context` as standing campaign-level framing?

**Candidates:**
- **(a) Yes, low-tactical-band placement** — between SETTING & TONE and per-turn directives.
- **(b) Yes, very early (SETTING & TONE adjacent)** — high in prompt, near tone block.
- **(c) No** — premise read only by bootstrap bot; not surfaced to main narration.

| Candidate | Pros | Cons | Risk |
|---|---|---|---|
| **(a) Low-tactical-band** | Standing framing for every narration call; placed after pure framing (SETTING & TONE) but before tactical pressure (consequence / quest / scene-lifecycle directives) — semantic alignment | Adds ~300-500 chars to every prompt | Low — prompt-size headroom is generous (S67 baseline ~25k, additive ~2% increase) |
| (b) SETTING & TONE adjacent | Premise reads as part of base framing; LLM treats it as fundamental | Adjacency to tone block could blur into tone-style instructions; readers might confuse "premise: X" with tonal direction | Medium — semantic confusion between premise (what's happening) and tone (how to narrate it) |
| (c) Not rendered | Zero prompt-size delta; premise stays pure authoring substrate | Premise becomes dead state in main play; the bot has it but the narration LLM never knows; standing campaign framing is lost | High — defeats the operational purpose of capturing premise at all; "grimdark mining town, the mine collapsed" should inform every narration call |

**Recommended default: (a) low-tactical-band.**

**Reasoning:** Per spec §1.E + sketch §11.6 MEDIUM lean. Premise is operator's standing intent for the campaign; every narration call should be framed by it. Low-tactical-band placement keeps it consistent context without colliding with tone framing.

**Confidence: MEDIUM.** Open axis: **whether (a) low-tactical-band vs (b) SETTING-adjacent feels right after Session 2 walks the prompt-structure recon.** Both are positionally close; either works doctrinally. If operator-feedback at Session 2 surfaces a preference, adjust the placement at lock-time without affecting any other §1 / §11 decision.

---

### §3.7 — Skeleton.md write shape

**Question:** Structured markdown per existing patterns? YAML embedded blocks? Schema-formal JSON sidecar?

**Candidates:**
- **(a) Structured markdown per R2 parser format.**
- **(b) YAML front-matter blocks under each H3.**
- **(c) Schema-formal JSON sidecar file** (skeleton.json alongside skeleton.md).

| Candidate | Pros | Cons | Risk |
|---|---|---|---|
| **(a) Structured markdown** | Compatible with existing `parse_skeleton_file` parser (no parser changes); hand-authored skeleton.md remains valid; human-readable for operator inspection; Git-trackable as prose | Permissive parsing allows malformed entries (operator-hand-edits could break shape); bot must produce exact-shape output | Low — operator inspection catches malformed entries; bot output is templatized (predictable shape per renderer) |
| (b) YAML front-matter | Structured field extraction; per-element typed metadata | Parser changes required; mixed-format file (markdown + YAML); not human-friendly | High — new parser surface, parser-bug risk, regression on existing hand-authored skeletons |
| (c) JSON sidecar | Cleanest structured shape; type-safe | Two-file model (skeleton.md + skeleton.json); divergence-pressure between the two files; existing parser surface bypassed | High — introduces a parallel canon surface (the very thing §11.12 worries about), at file-pair level |

**Recommended default: (a) structured markdown.**

**Reasoning:** Per spec §1.G + sketch §11.7 HIGH lean. R2 confirms the existing parser is bot-output-friendly. Reusing existing parser surface is zero-risk; alternatives introduce parsing complexity for marginal gain.

**Confidence: HIGH.**

---

### §3.8 — Faction storage at v0 (DEEP SYNTHESIS PER BRIEF)

**Question:** Where do bootstrap-authored factions land? Skeleton.md only? `dnd_factions` table introduced at v0? Faction cards deferred entirely?

**Candidates:**
- **(a) Skeleton.md only at v0** — bot writes `## Factions` H2 entries; downstream reads via `parse_skeleton_file`'s `result['factions']` list; `dnd_factions` table introduced at Causality Engine v0 (S69).
- **(b) Bundle `dnd_factions` table into N-10** — N-10 introduces the table + single-writer `faction_upsert`; bot writes to both table and skeleton.md.
- **(c) Defer faction cards entirely** — N-10 ships without faction card type; factions added at S69 alongside table.

| Candidate | Pros | Cons | Risk |
|---|---|---|---|
| **(a) Skeleton.md only** | v0 scope tight (no schema migration); skeleton.md is already parsed surface; faction authoring captured at bootstrap time without committing N-10 to schema-introducer role; S69 has clean migration target (parse skeleton, insert rows) | Faction structured fields (goal, pressure_shape, engagement_signals) live in prose only — no field-level queryability; S69 must parse prose to extract structured fields | Low — prose-extraction is exactly what S69 will do at first; the skeleton already carries `result['factions']` shape with parsed `{name, type, description}` |
| (b) Bundle table into N-10 | Structured fields queryable from day one; S69 inherits ready-to-tick faction state; no skeleton-to-DB migration at S69 | N-10 scope expands from "authoring tool" to "authoring tool + schema introducer"; spec lock + implementation phase both grow; `dnd_factions` schema design is its own decision space (faction_id, parent_faction_id for sub-factions, status enum, audit table?) that should drive S69 not N-10 | Medium — schema-design coupling; if N-10 ships a schema that S69 wants to revise, migration cost lands on S69; if S69 inherits the schema verbatim, fine |
| (c) Defer faction cards entirely | Tightest N-10 scope; no faction-related design pressure at v0 | Drops a load-bearing card type from sketch §1.D sequence; downstream Causality Engine has no factions to read until S69 ships; bootstrap-as-load-bearing-prerequisite framework breaks (S69 reads from authored canon that doesn't include factions) | High — defeats N-10's purpose for the Causality Engine track; S69 would inherit empty faction surface and need to author its own |

**Synthesis (per session brief — authoring-runtime decoupling vs bundle cost):**

The architectural intuition behind (a) is **authoring-runtime decoupling**. N-10 is the AUTHORING tool; S69 is the RUNTIME engine. They're sequenced because their concerns are different — bootstrap captures the operator's structured intent; Causality Engine ticks against the runtime state. Bundling the table into N-10 collapses this decoupling: N-10 becomes a partial implementation of S69's substrate.

The cost of decoupling is **prose-extraction at S69 ship time** — S69 must parse skeleton.md's `## Factions` H2 entries and insert rows into the new `dnd_factions` table. But this is exactly the shape Quest Layer v0 already used for hooks (`/quest seed` parses skeleton hooks into `dnd_quests`). The pattern is mature; S69 inherits it cleanly.

The cost of bundling is **schema design lock-in at N-10**. Faction schema is non-trivial:
- `faction_id`, `canonical_name`, `description`, `skeleton_origin` (mirrors `dnd_npcs` shape) — fine
- Faction relationships: `parent_faction_id` for sub-factions? Faction-to-NPC association? Faction-to-quest association? Faction-to-location? These are real S69 design questions.
- Faction state machine: factions tick (S69's whole job) — status enum needed at table-introduction time.
- Faction pressure shape: `goal`, `pressure_shape`, `engagement_signals` fields from sketch §4 — but S69 may want `clock_capacity`, `clock_ticks`, `last_tick_at`, `tick_predicate_json` — different fields.

If N-10 ships table with sketch §4 shape, S69 likely revises the schema. Migration cost lands on S69 (one ALTER TABLE pass), and the operator pays twice for the schema decision.

**Recon evidence supports (a).** R6: `dnd_factions` does not exist. Quest Layer v0 §12.2 explicitly deferred faction modeling to v1.x. The skeleton parser already produces `result['factions']` with structured field extraction (name, type, description from H3 entry shape). S69 has a clean migration target.

**Hidden cost of decoupling (audit pass):**
- (i) Bot must construct skeleton.md faction H3 entries that capture goal / pressure_shape / engagement_signals in PROSE. Per R2 parser, the format is `### {name} ({type})` with free-form description. Bot's description renders the three structured fields as prose ("Goal: ... Pressure: ... Engagement signals: ..."). S69's prose extractor reads back from this shape.
- (ii) Causality Engine spec must adopt the prose-extraction pattern OR introduce a structured-format extension to skeleton.md (e.g., faction-specific YAML block or H4 sub-headers per field). This is S69's design call.
- (iii) During the v0 → S69 gap, factions are queryable only via `parse_skeleton_file(campaign_id)['factions']` — full-file parse per query, not indexed. Acceptable for the gap (no per-turn faction reads at v0 yet — Quest Layer doesn't query factions at runtime).

None of these costs invalidate (a). All are exactly what (a) is supposed to defer.

**Recommended default: (a) skeleton.md only at v0.**

**Reasoning:** Authoring-runtime decoupling preserves the project's ship-discipline. N-10 is the authoring layer; S69 is the runtime engine. Bundling schema into N-10 confuses scopes and risks S69 revising the schema later. Skeleton.md is already parsed; faction prose extraction is the same pattern Quest Layer v0 uses for hooks.

**Confidence: HIGH.** Recon evidence + project precedent (Quest Layer v0 §12.2 deferred faction modeling explicitly) both support (a). The hidden cost of decoupling (prose-extraction at S69) is bounded and well-shaped.

**Spec amendment implied at lock:** none. §1.H stands. §11.8 confirms.

**Operator escalation point:** if S69 timeline gates on having `dnd_factions` table earlier (e.g., S68 N-3 commitment rails want faction-state-derived pressure), flip to (b) and bundle the table into N-10. Operator confirms which sequencing serves the downstream architecture better.

---

### §3.9 — NPC pronouns at v0 (DEEP SYNTHESIS PER BRIEF)

**Question:** Where do bootstrap-authored NPC pronouns land? Folded into description prose at v0? `dnd_npcs.pronouns` column added at v0? NPC cards deferred until N-4 ships pronouns column?

**Candidates:**
- **(a) Prose-fold pronouns into description at v0** — bot includes pronoun reference in first sentence of NPC card's description field; N-4 (S68) introduces `dnd_npcs.pronouns` column + one-shot migration extracts pronouns from existing descriptions.
- **(b) Bundle `dnd_npcs.pronouns` column add into N-10** — N-10 introduces the column; bot writes structured pronouns at card-write time; N-4 ships the anti-drift rail on top.
- **(c) Defer NPC cards entirely** — N-10 ships without NPC card type; NPCs added at N-4 alongside pronouns column.

| Candidate | Pros | Cons | Risk |
|---|---|---|---|
| **(a) Prose-fold** | v0 scope tight (no schema change); N-4 ships pronouns column at its own pace; bot output discipline (pronoun in first sentence) is enforceable via card directive prompt; sketch §4 already anticipates this | N-4 migration pass must scan existing NPC descriptions for pronoun extraction; if bootstrap-NPC descriptions reliably carry pronouns and hand-authored NPCs don't, the migration shape gets non-uniform | Medium — see forward-coupling note below; N-4 must recon for prose-folded pronouns as EXPECTED starting state, not edge case |
| (b) Bundle column into N-10 | Structured pronouns from day one; no migration at N-4 ship; bot writes directly to the canonical field | N-10 scope expands; column schema is small but introduces design coupling with N-4 (what pronoun strings are canonical? "she/her" vs "she" vs "she/her/hers"? Free-text vs enum?); N-4's anti-drift rail design may want specific column shape | Medium — schema-design coupling between v0 N-10 and S68 N-4; if N-10 ships a shape N-4 revises, migration cost lands on N-4 |
| (c) Defer NPC cards | Tightest N-10 scope; no NPC pronoun design pressure | Drops a load-bearing card type from sequence; downstream Quest Layer / Composition Layer have no dispatcher NPCs to anchor against until N-4 ships; bootstrap-as-load-bearing-prerequisite breaks for the dispatcher path | High — defeats N-10's purpose for Quest Layer / Composition Layer downstream reads |

**Synthesis (per session brief — ship-sequencing discipline vs avoiding migration shape later):**

The architectural intuition behind (a) is **ship-sequencing discipline**. N-10 ships before N-4 because N-10 produces canon volume (the load-bearing prerequisite); N-4 ships after N-10 because N-4's anti-drift rail operates ON canon NPCs. Bundling pronouns column into N-10 inverts the dependency direction (N-10 now needs N-4's design call on canonical pronoun strings).

The cost of decoupling is **N-4 migration pass extracts pronouns from descriptions**. Per sketch §4 NPC card discipline (pronouns appear in first sentence of description), the migration's expected shape is:
- For each NPC row with `skeleton_origin=1`: scan description's first sentence for pronoun tokens (he/she/they/it + possessive variants).
- For each NPC row with `skeleton_origin=0` (parser-extracted, possibly pre-N-10): scan description for any pronoun tokens (less reliable; may extract zero or multiple).
- Hand-authored NPCs (skeleton_origin=1 from pre-N-10 hand-edits): mixed reliability; operator-author-quality-dependent.

This is a **mixed-quality migration**. Some NPCs have predictable shape (bootstrap-origin), some don't (parser-origin), some are operator-dependent (pre-N-10 hand-authored).

The cost of bundling is **N-10 commits to pronoun column shape before N-4 spec opens**. Real design questions:
- Free-text vs enum vs structured? `"she/her"` is operator-readable; `{nominative: "she", accusative: "her", possessive: "her", reflexive: "herself"}` is structured.
- What about NPCs with multiple pronoun sets (e.g., shape-shifters)? Single column or related table?
- Anti-drift rail (N-4) wants what shape for fast lookup at narration time?

These are all N-4 territory. N-10 committing first means N-4 either inherits the shape (lock-in) or revises (migration cost).

**Forward-coupling note (per session brief, surfaced explicitly):**

> If §11.9 locks (a), N-4 / S68 recon MUST treat bootstrap-origin NPCs as carrying pronouns in description first sentence — this is the EXPECTED starting state, not edge case. N-4 migration extractor needs three classes of NPC handled:
> 
> 1. **Bootstrap-origin (skeleton_origin=1, post-N-10):** pronouns in first sentence of description per §1.I card discipline. Extraction shape predictable.
> 2. **Parser-extracted (skeleton_origin=0):** pronouns scattered in description. Extraction shape variable; may be missing entirely.
> 3. **Hand-authored pre-N-10 (skeleton_origin=1, pre-N-10):** pronouns operator-author-dependent. Extraction shape mixed.
> 
> N-4 spec must address all three classes. The "predictable shape" of (1) is what N-10's §1.I card discipline buys; N-4 inherits this gain.

**Recon evidence supports (a).** R6: `dnd_npcs.pronouns` does not exist. S67 §76 audit confirmed schema has no pronoun field. Sketch §4 explicitly defers pronoun column to N-4 ("anti-drift rail in N-4 ships separately").

**Recommended default: (a) prose-fold pronouns into description at v0.**

**Reasoning:** Ship-sequencing discipline preserves the dependency direction (N-10 produces canon → N-4 protects canon). N-4 retains design authority on pronoun column shape. Bootstrap NPC card discipline (pronoun in first sentence) gives N-4 a clean extraction shape for the migration pass.

**Confidence: HIGH.** Recon evidence + sketch §4 explicit deferral + ship-sequencing discipline all support (a).

**Spec amendment implied at lock:** none. §1.I stands. §11.9 confirms. Forward-coupling note travels to N-4 / S68 spec opening as "expected starting state per N-10 §1.I" (file in `S65_1_candidates.md` N-4 entry or similar).

**Operator escalation point:** if N-4 ships before N-10 (priority shift), flip to (b) and bundle column into N-10's schema delta. Operator confirms which ship-order serves the dependency direction.

---

### §3.10 — Operator field-override semantics

**Question:** Slash-with-args (`/bootstrap manual name:"X"`) or interactive Modal or JSON paste?

**Candidates:**
- **(a) `/bootstrap manual <field>:<value>`** — operator can chain multiple overrides before `/bootstrap accept`.
- **(b) Modal popup with all card fields editable.**
- **(c) Operator types JSON** with the override fields.

| Candidate | Pros | Cons | Risk |
|---|---|---|---|
| **(a) Slash-with-args** | Standard project shape (used in `/quest add`, `/giveitem`, etc.); operator can chain `/bootstrap manual name:"Eldrin Stormbow"` → `/bootstrap manual role:"village herald"` → `/bootstrap accept`; small UX for small override | Slash arg per override (verbose for multi-field overrides) | Low — operator chains for multi-field; one slash for single-field |
| (b) Modal popup | Multi-field edit in one UI; cleanest for "override everything" case | Modal API not currently used; new UI primitive; Discord Modal field limits (5 components per modal) constrain card-with-7-fields editing | Medium — new UI surface; +complexity for Session 3 |
| (c) JSON paste | Power-user override; copy-paste-friendly | Operator types JSON in Discord (escaping, line breaks, syntax errors); poor UX | High — JSON-typing in chat is a known UX failure mode |

**Recommended default: (a) `/bootstrap manual <field>:<value>`.**

**Reasoning:** Per spec §1.B + sketch §11.9 lean. Standard project pattern; operator already familiar with slash-arg shape. Chain-for-multi-field is reasonable friction.

**Confidence: HIGH.**

---

### §3.11 — Sequence order

**Question:** Factions → NPCs → Quests → Acts → Locations? Or NPC-first then quests anchor to them?

**Candidates:**
- **(a) Factions first** — sketch §1.D order; pressure threads established before NPCs voice them.
- **(b) NPCs first** — characters established before factions or quests; quests anchor to existing NPCs.
- **(c) Quests first** — quest hooks define the story; NPCs voice the quests bot proposes.
- **(d) Operator-selected order** — `/bootstrap` accepts `sequence` arg with custom ordering.

| Candidate | Pros | Cons | Risk |
|---|---|---|---|
| **(a) Factions first** | Pressure threads establish offscreen stakes; NPCs and quests anchor to factions; matches sketch §1.D dependency-order architecture | Faction-first cards feel abstract before any concrete NPC exists; operator may not have a faction in mind until they see the world's NPCs | Medium — abstract-first ordering may produce awkward first-card UX |
| (b) NPCs first | Concrete characters first; operator can think "who's in this world" before "what's pressuring them" | Faction cards come after NPCs are written; if operator approves an NPC tied to a faction not yet authored, FK reference is awkward (faction comes later in sequence) | Medium — FK awkwardness mitigated by faction-name string reference (`associated_faction_name` field per §5.2); not blocking |
| (c) Quests first | Hooks define the campaign shape; NPCs voice them; everything else hangs off quests | Quests with no offer-NPC are degenerate at v0 (no FK to write); ordering forces NPCs to be subsequent and locked-to-quest | High — quest-with-no-voicer fails the §5.3 schema requirement; ordering creates structural bind |
| (d) Operator-selected | Flexibility | Adds slash-arg complexity; sequence-design becomes an operator decision they don't have context to make | Medium — operator burden for marginal gain |

**Recommended default: (a) factions first.**

**Reasoning:** Per spec §1.D + sketch §11.2 lean. Dependency-order architecture (factions → NPCs → quests → acts → locations) matches the downstream-read direction (Causality Engine reads factions; Quest Layer reads dispatcher NPCs + factions; Composition reads quests + acts; Scene Lifecycle reads locations). Faction-first surfaces the load-bearing question before lower-level details lock in.

**Confidence: MEDIUM.** Open axis: **operator world-building style preference.** Some operators build characters-first (write the cast, then ask what they want); others build pressure-first (establish stakes, then populate). If operator-feedback during Session 2 indicates a strong preference for NPC-first or quest-first, flip the lean.

---

### §3.12 — Skeleton.md vs DB source-of-truth on divergence (DEEPEST SYNTHESIS PER BRIEF)

**Question:** If skeleton.md and canonical tables diverge later (operator hand-edits skeleton.md, or DB row deleted via slash, or canonical table content changed by some other write path), which wins?

**Candidates:**
- **(a) Skeleton.md wins on divergence** — operator re-runs `/quest seed` (or equivalent reconciliation tool) to overwrite DB from skeleton.md content.
- **(b) DB wins on divergence** — skeleton.md becomes secondary/snapshot; regenerated from DB state on demand via a separate slash command.
- **(c) Defer to v1.x canon-sync spec** — v0 ships with both-sides-write at bot-approval time and no reconciliation policy; observed-friction signal informs v1.x design.

**Synthesis (per session brief — this is the deepest walk; only LOW-confidence decision).**

**How would divergence happen?**

Divergence vectors at v0:
1. **Operator hand-edits skeleton.md.** E.g., adds a new NPC entry to `## Primary NPCs`. DB row doesn't exist for it. Existing `/quest seed` reconciles hooks, but no equivalent for NPCs or locations or factions at v0.
2. **DB write via existing slash.** E.g., `/quest delete <id>` removes a quest row. Skeleton.md still has the H3 entry. On next `/play`, skeleton prompt block re-renders the deleted quest.
3. **DB write via parser-extracted updates.** E.g., `_extract_and_persist_world` thread upserts an NPC mention. Existing skeleton-origin=1 row description gets updated (per `npc_upsert` behavior matrix's "skeleton × parser" branch — mention bumps only, fields locked). Skeleton.md description stays in sync because authored-field-lock holds.
4. **Bot writes during bootstrap (at-write divergence).** Bot proposes element; operator approves; canonical-table write succeeds; skeleton.md append fails (filesystem error). Per spec §1.G: canonical wins, skeleton.md soft-fails. This is per-element atomicity, distinct from longer-term divergence.

The dominant divergence vectors at v0 are (1) and (2). Vector (3) is structurally protected by `npc_upsert`'s lock matrix. Vector (4) is operationally rare and per-event (not long-term drift).

**Trade-offs:**

| Candidate | Pros | Cons | Risk |
|---|---|---|---|
| (a) Skeleton.md wins | Skeleton.md remains the AUTHORING SURFACE (preserves N-10's whole point — operator's authorial intent lives in the file); operator can hand-edit and reconcile; Git-trackable canonical history if operator uses version control | Requires a "reconcile from skeleton" tool for every entity type (`/quest seed` only handles hooks; NPCs/locations/factions need analogous reconciliation slashes); DB-side slash mutations (`/quest delete`, `/npc edit`) get overwritten on reconciliation; reconciliation must be operator-explicit (auto-reconcile risks silent data loss) | Medium — substantial new code surface (reconciliation slashes per entity type); operator must remember to reconcile after hand-edits |
| (b) DB wins | Runtime authority is consistent; `/play` reads from DB; divergence in skeleton.md doesn't affect play behavior; less code surface (no reconciliation tool needed, just DB-as-truth) | Skeleton.md becomes stale unless regenerated; operator can't reliably hand-edit (their edits get overwritten on next regen); requires "regenerate skeleton.md from DB" tool — also substantial new code; weakens N-10's authoring-surface framing | Medium — skeleton.md becomes secondary; operator authoring intent gets demoted; "operator never opens skeleton.md" framing (sketch §1) gets harder if file becomes auto-regenerated |
| **(c) Defer to v1.x** | Zero new architecture at v0; v0 ships clean first-time-bootstrap shape; operator decides based on observed friction; doesn't pre-lock a longer-term canon-management question | Divergence WILL happen during v0 use (operator hand-edits, slash deletes); no guidance for resolution; ad-hoc resolution patterns may calcify before spec arrives | Medium — divergence guidance gap; operator left to resolve manually; if pattern calcifies wrong way, v1.x spec inherits the calcified shape |

**Inventory of divergence handling at adjacent specs:**

- **Quest Layer v0.1 (S57 patch):** `/quest seed-skeleton` (renamed `/quest seed` at S61) is the explicit skeleton→DB reconciliation tool for hooks. Behavior: idempotent insert; existing rows preserved. NOT a "skeleton wins" tool — it's "skeleton-extends-DB" tool (additive only).
- **Composition Layer v0:** No skeleton↔DB reconciliation slash; skeleton's `#### Acts` subsection feeds `quest_act_upsert` at `/quest seed` time; subsequent operator edits to acts go through `/quest act add` / `/quest act advance` slashes (DB-side only).
- **Skeleton loader (`apply_skeleton`):** Reads skeleton.md on `/play`; writes NPCs / locations via `npc_upsert` / `location_upsert` with `skeleton_origin=True`. This is "skeleton extends DB at /play time" — also additive, also not a true reconciliation.

**Project precedent: skeleton.md is the AUTHORING SOURCE; DB is the RUNTIME MIRROR.** Existing tools are additive (skeleton-extends-DB). No tool exists that goes the other way (DB-extends-skeleton). The conceptual architecture leans (a) skeleton.md wins, but it's never been formalized — partly because divergence has been minimal in practice (Quest Layer v0 only deals with hooks; Composition Layer keeps acts in DB-side workflows post-seed).

**For N-10:** divergence surface expands significantly. Bot writes both sides at every approval; that's the at-write atomicity surface (spec §1.G handles). But operator can hand-edit any entity-type description, or delete rows via `/quest delete` / future `/npc delete` / `/location delete`. The DB-side delete creates skeleton-side staleness; the file-side hand-edit creates DB-side staleness.

**Why (c) defer is the right v0 call:**

1. **N-10's primary contract is single-shot bootstrap.** Divergence-resolution is a longer-term canon-management concern. v0 ships the cleanest bootstrap; v1.x spec opens divergence-handling on observed friction.
2. **Operator's authoring discipline is unknown until live.** Whether operators hand-edit skeleton.md frequently, or trust DB-side slashes, or treat skeleton.md as write-once snapshot — none of these are predictable from anticipation. Observed signal informs the choice.
3. **(a) and (b) both require substantial new code.** Reconciliation tools per entity type (a) or DB-to-skeleton regeneration (b) are non-trivial implementations. v0 shouldn't ship one of these without knowing it's the right one.
4. **The (a) vs (b) decision shapes the AUTHORING-vs-RUNTIME framing.** This is doctrinal weight, not v0-implementation choice. Locking without operator + Code walk on the framing risks committing to wrong shape.

**Why operator might force (a) lock now:**

If operator strongly prefers skeleton.md as canonical authoring surface (consistent with N-10's framing) AND is comfortable with the "reconciliation tool per entity type" implementation cost being absorbed at v0.x or v1.x, locking (a) now saves a future spec session.

**Why operator might force (b) lock now:**

If operator strongly prefers DB as canonical runtime authority AND is willing to demote skeleton.md to snapshot-regenerated-from-DB, locking (b) now establishes the "DB-as-truth, skeleton-as-mirror" framing early. This contradicts the sketch §1 framing ("operator never opens skeleton.md" inverts: skeleton becomes a generated artifact, not an authoring surface) but is operationally consistent.

**Recommended default: (c) defer to v1.x.**

**Reasoning:** This is the LOW-confidence decision by design — sketch §11.11 had no confident lean. v0 ships clean first-time-bootstrap shape; divergence is observed-friction-gated for v1.x. Code's lean stays (c) unless operator has strong preference articulated at Session 2.

**Confidence: LOW.** Genuine uncertainty. Open axis: **operator's authoring-vs-runtime framing preference.** If operator articulates strong (a) preference, that's a reasonable lock; if strong (b) preference, also reasonable lock; if "let observed signal decide," (c) is the right call.

**Spec amendment implied at lock — three paths:**

- If operator locks (a): §11.12 records (a); §13 adds "skeleton-to-DB reconciliation tool per entity type" as v0.x candidate; future session opens reconciliation spec.
- If operator locks (b): §11.12 records (b); §13 adds "DB-to-skeleton regeneration slash" as v0.x candidate; sketch §1 "operator never opens skeleton.md" framing remains intact (file is generated-not-authored).
- If operator locks (c): §11.12 records (c); §13 maintains "skeleton↔DB divergence reconciliation" as v1.x candidate (already present per §12.3).

---

## §4. Forward-coupling notes

Per session brief: surface forward-coupling implications where §11 walks tie into adjacent specs.

**§11.9 → N-4 / S68 spec opening:**
- If §11.9 locks (a) prose-fold, N-4 migration extractor must handle THREE NPC classes (bootstrap-origin / parser-origin / hand-authored pre-N-10) with mixed-quality prose. Surfaced explicitly in §3.9 forward-coupling note above.
- N-4 spec must document "bootstrap-origin NPCs carry pronouns in first sentence of description per N-10 §1.I" as expected starting state.
- N-4 migration test surface includes: post-N-10 bootstrap-NPC pronoun extraction succeeds at >95%; parser-origin NPC extraction may fail or partial-extract gracefully; hand-authored NPCs treated as operator-author-dependent.

**§11.8 → S69 / Causality Engine v0 spec opening:**
- If §11.8 locks (a) skeleton.md only, S69 schema-introduction spec must include `dnd_factions` table design + migration from `parse_skeleton_file(campaign_id)['factions']` parsed shape.
- S69 inherits the per-faction prose shape from N-10 (goal / pressure_shape / engagement_signals rendered as prose under H3); structured-field extraction at S69 ship time parses these from the description.
- S69 spec must address: does S69 promote factions to its own table at S69 ship, OR continue parsing from skeleton.md indefinitely? Lean: promote at S69 ship; skeleton.md remains AUTHORING surface but faction RUNTIME state lives in DB (mirrors Quest Layer's skeleton-extends-DB pattern).

**§11.5 → v1.x expansion mode spec opening:**
- If §11.5 locks (a) error at v0, v1.x expansion-mode spec inherits "bootstrap-complete signals" (premise set + skeleton_origin=1 rows present) as the detection surface.
- Expansion mode design must address: which card types are valid for re-run? All five (factions/NPCs/quests/acts/locations) or subset? Per-campaign tracking of "what's been bootstrapped" vs "what's been hand-extended"?

**§11.6 → main-prompt architecture:**
- If §11.6 locks (a) low-tactical-band, the prompt-structure recon for any future ship that touches `build_dm_context` must account for the premise block's position. This is a minor coupling — premise block is operator-written 3/4 §76, not a 4/4 contamination surface; positional adjustments are cheap.

---

## §5. Operator + Oracle decisions

**At v0:** none required at lock-time for the recommended defaults.

**Walk-to-confirm at Session 2:**
- **§11.12 (skeleton ↔ DB SoT)** — Code recommends (c) defer; operator may have strong preference for (a) or (b) that justifies locking now. Walk surfaces all three with full trade-offs; operator's authoring-vs-runtime framing intuition is the deciding axis.
- **§11.8 (faction storage)** — Code recommends (a) skeleton.md only; operator may have S69 sequencing concerns that justify bundling table into N-10. Walk surfaces the schema-design coupling cost; operator decides whether N-10 absorbs that cost or S69 does.
- **§11.9 (NPC pronouns)** — Code recommends (a) prose-fold; operator may have N-4 timing concerns that justify bundling column into N-10. Walk surfaces the forward-coupling note for N-4 migration; operator decides whether ship-sequencing or migration-shape matters more.

**Deferred to v1.x / v0.x:**
- §11.5 expansion mode (observed-friction gate).
- §11.12 canon-sync spec (if (c) defer locks).
- §11.4 reroll cap threshold (telemetry-tunable).
- §11.6 main-prompt placement (positionally adjustable at any future ship).

**No Oracle decision required at v0.** All architectural decisions sit cleanly within precedent specs' patterns (§1b sixth-instance suggester, §59 sibling #17 + #18, §17 single-writer per field).

---

## §6. Summary of recommended defaults

| Decision | Recommended | Confidence | Spec implication |
|---|---|---|---|
| §11.1 | (a) new `premise` column | HIGH | Spec §1.A confirmed; migration runs at engine init |
| §11.2 | (a) separate `/bootstrap` slash | HIGH | Spec §1.B confirmed |
| §11.3 | (a) single-shot slash arg | HIGH | Spec §1.C confirmed |
| §11.4 | (a) soft-reroll unlimited | MEDIUM | Spec §1.B confirmed; threshold telemetry-tunable in v0.1 |
| §11.5 | (a) error at v0 | HIGH | Spec §1.J confirmed |
| §11.6 | (a) low-tactical-band | MEDIUM | Spec §1.E confirmed; position adjustable at Session 2 |
| §11.7 | (a) structured markdown | HIGH | Spec §1.G confirmed |
| §11.8 | **(a) skeleton.md only** | HIGH | Spec §1.H confirmed; S69 inherits prose-extraction shape |
| §11.9 | **(a) prose-fold** | HIGH | Spec §1.I confirmed; forward-coupling note travels to N-4 |
| §11.10 | (a) `/bootstrap manual <field>:<value>` | HIGH | Standard slash-arg shape |
| §11.11 | (a) factions first | MEDIUM | Spec §1.D confirmed; operator world-building style is open axis |
| §11.12 | **(c) defer to v1.x** | LOW | Genuine uncertainty; operator escalation point if strong (a) or (b) preference |

**Confidence split:** 7 HIGH · 4 MEDIUM · 1 LOW.

**HIGH (no synthesis pressure, proceed with recommended):** §11.1, §11.2, §11.3, §11.5, §11.7, §11.8, §11.9, §11.10 (8 decisions).

**MEDIUM (operator attention helpful, open axis named):** §11.4, §11.6, §11.11 (3 decisions).

**LOW (genuine uncertainty, operator preference deciding):** §11.12 (1 decision).

---

## §7. Surface additions

**No §11.13 surfaced.** Walk produced no NEW architectural decision worth a §11 slot.

**Edge cases sweeped during walk (filed §12 forward-files, not §11 surface):**

1. **Cross-session canonical_name collision.** Bot proposes "Eldrin Stormbow" during bootstrap; campaign already has an NPC by that name from prior parser-extraction. `npc_upsert` behavior matrix handles this cleanly: "parser × skeleton → promote to skeleton_origin=1, authored fields win." Bootstrap inherits existing canonical pattern; no §11 decision needed. Documented inline in §5.2 for clarity (or in implementation phase).

2. **LLM-output schema-validation failure repeat loop.** If LLM call fails or returns invalid JSON repeatedly, operator's escape hatches are `/bootstrap skip` (drop card and advance) or `/bootstrap manual <field>:<value>` (fill fields manually then accept). No §11 decision; UX flow is covered by existing slash surface. File as §12 forward-note: "if telemetry shows >20% LLM-output-failure rate per card type, surface for v0.1 prompt-tightening patch."

3. **Bootstrap session timeout.** Operator opens `/bootstrap` and walks away mid-session. `_bootstrap_session[campaign_id]` persists until process restart. No state corruption (in-memory only); operator can return and continue. No §11 decision; behavior is fine as-is. File as §12 forward-note: "if telemetry shows abandoned-session rate >10%, surface for v0.1 timeout-on-idle patch."

4. **Per-element write atomicity.** Per spec §1.G: canonical-table write is authoritative; skeleton.md append soft-fails on file error. The pre-§11 design choice already addresses this; not a §11 decision. Documented in spec §1.G + §3 (review's §3 walk doesn't introduce new question on this).

5. **Starting-location uniqueness enforcement.** Per §5.5: "at most one location per bootstrap session can carry `starting_location=True`." Validator must enforce; if operator approves a second location with `starting_location=True`, validator should reject or auto-clear the prior starting flag. No §11 decision; UX detail for implementation phase.

**Why no §11.13:** The walk produced clean confirmations of §1-level decisions across 8 HIGH-confidence walks and acknowledged operator-preference axes at 4 MEDIUM/LOW walks. No architectural gap surfaced that requires a NEW operator-level lock before Session 3 opens. Edge cases are implementation-phase considerations.

---

## §8. Handoff

| Field | Value |
|---|---|
| **Review doc status** | REVIEW — Phase 2 walk complete (May 14, 2026). Operator reviews and locks decisions; spec flips DRAFT → LOCKED before Session 3 implementation opens. |
| **Review doc file** | `/home/jordaneal/virgil-docs/specs/CANON_BOOTSTRAP_BOT_V0_REVIEW.md` |
| **Decisions walked** | 12 (§11.1 through §11.12). |
| **Confidence split** | 7 HIGH · 4 MEDIUM · 1 LOW (§11.12). |
| **§11.13 surfaced** | None. Walk produced no NEW architectural decision worth a §11 slot. 5 edge cases filed as §12 forward-notes or implementation-phase considerations. |
| **Operator escalation points** | §11.12 (genuine uncertainty; (c) defer is Code's lean but operator may force (a) or (b) lock if strong preference). §11.8 + §11.9 (deeper synthesis surfaced schema-coupling trade-offs; operator may flip routing if S69 / N-4 sequencing differs from Code's assumptions). |
| **Forward-coupling notes** | §11.9 → N-4 / S68 (migration extractor must handle 3 NPC classes; bootstrap-origin pronoun shape is expected starting state). §11.8 → S69 / Causality Engine v0 (faction prose-extraction pattern + table design). §11.5 → v1.x expansion mode spec opening. §11.6 → main-prompt architecture (minor positional coupling). |
| **HALT escalations** | 0. Walk surfaced no finding that invalidates v0 architectural shape. Two §11 decisions (§11.8 + §11.9) carry schema-coupling trade-offs already documented in spec §1.H + §1.I; the deeper synthesis confirms Code's leans hold under recon evidence and project precedent. |
| **Next session** | Session 3 = implementation. Sonnet medium per WWC cadence — mature §59 sibling pattern (17 prior instances + N-10's 2 new); mature §1b suggester pattern (4 explicit prior + 1 reserved + N-10's 6th anchor); recon-clean architecture; clear decision space post-lock. Estimated ~3-4 days for engine + orchestration + 7 slash commands + 19 test surface (per spec §9 test plan). |

**Recommended pre-Session-3 operator action sequence:**

1. Review this doc (Session 2 framing).
2. Lock §11.1–§11.11 to recommended defaults if no objections.
3. Lock §11.12 to one of (a) / (b) / (c) — Code's lean (c) defer; operator's preference deciding.
4. Confirm or adjust §11.8 and §11.9 schema-coupling routing (default: defer schema additions to S68/S69; flip if operator wants to bundle).
5. Update spec file's status header: DRAFT → LOCKED with date + decision-lock summary.
6. Session 3 opens with locked spec.
