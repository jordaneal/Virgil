# §9.1 Amendment Language — Three Phrasings for Operator Lock

Draft for Jordan to lock the doctrine language before Code's spec session opens. After lock, the chosen phrasing becomes the load-bearing protected text — spec session converges on it, implementation enforces it, future external reviews cite it.

Convention: each phrasing is the exact text that would amend §9.1's lock statement. §9.1's current strict-literal lock + the anti-pattern catalog references stay unchanged. The amendment is additive — naming the bounded exception that 2B introduces.

Context for each: what's protected, what's permitted, what failure modes each constraint guards against.

---

## Version 1 — Tight

> Strict literal matching remains the default identity rule. Exception: deterministic whole-token prefix collapse is permitted only when the incoming canonical_name matches a unique `skeleton_origin=1` row's leading whole-token within the same `campaign_id`. If multiple `skeleton_origin=1` rows in the same campaign share the leading whole-token, no collapse occurs; insert proceeds normally and ambiguity telemetry is logged.

### What this forbids
- Edit-distance / Levenshtein collapse (Garrik ↔ Garrick) — preserved from §9.1 base lock
- Embedding-based identity (semantic similarity collapse)
- Probabilistic / statistical equivalence inference
- Token-prefix collapse against `skeleton_origin=0` rows (no emergent ↔ emergent reconciliation)
- Token-prefix collapse against `skeleton_origin=1` rows when multiple anchors share the leading token (ambiguous case)
- Cross-campaign token-prefix collapse (Eldrin Stormbow in campaign 17 cannot anchor "Eldrin" mentions in campaign 18)
- Partial-token or substring prefix (only whole-token matches; "Eldr" does not match "Eldrin Stormbow")

### What this permits
- "Eldrin" → "Eldrin Stormbow" when exactly one `skeleton_origin=1` row in the same campaign has leading whole-token "Eldrin"

### Failure modes each constraint protects against
- **"unique" constraint** — protects against fuzzy-identity creep via the "Eldrin Stormbow / Eldrin Brightwater" case. If two skeleton-anchored NPCs in the same campaign share a leading token, the system has no deterministic way to choose between them. Allowing collapse anyway requires a tiebreaker (recency? mention_count? first-authored?), and every tiebreaker is a probabilistic equivalence dressed as deterministic logic. The uniqueness refusal preserves the strict boundary.
- **"`skeleton_origin=1`" constraint** — protects against emergent-emergent reconciliation slipping back in. The skeleton-anchor is the bright-line that distinguishes "deterministic shorthand against declared canon" from "probabilistic equivalence between two parser-extracted rows." Without this constraint, the slope from Eldrin → Eldrin Stormbow to Garrik → Garrick collapses immediately and the anti-pattern returns.
- **"same `campaign_id`" constraint** — protects against cross-campaign contamination. Campaign isolation is a load-bearing project invariant — every campaign-scoped table partitions on `campaign_id` for a reason. NPCs are campaign-scoped canon; an "Eldrin" mention in a different campaign must resolve against THAT campaign's skeleton, not bleed across boundaries.
- **"whole-token" constraint** — protects against substring drift. Without it, "Eldr" or "El" or "E" matches "Eldrin Stormbow" and the rule degenerates to arbitrary-prefix matching. Whole-token is the deterministic primitive; sub-token is the door to fuzzy.

### Where this lands operationally
Implementation in `npc_upsert` does a unique-anchor lookup before the strict-equality lookup. If unique-anchor match found, route to canonical row's UPDATE branch. If multiple anchors match, refuse collapse, insert normally, log `npc_anchor_ambiguous:` telemetry.

---

## Version 2 — Medium (drops `same campaign_id` constraint)

> Strict literal matching remains the default identity rule. Exception: deterministic whole-token prefix collapse is permitted only when the incoming canonical_name matches a unique `skeleton_origin=1` row's leading whole-token. If multiple `skeleton_origin=1` rows share the leading whole-token, no collapse occurs; insert proceeds normally and ambiguity telemetry is logged.

### What changes vs Version 1
The same-campaign constraint is dropped. Token-prefix uniqueness is evaluated globally across all `skeleton_origin=1` rows, not within-campaign.

### What this additionally permits
- Cross-campaign collapse: if campaign 17 has "Eldrin Stormbow" and campaign 18 has no Eldrin-anchor, an "Eldrin" mention in campaign 18 would collapse to campaign 17's row. *(But wait — campaign isolation is a project invariant; this would actually break under the existing campaign-scoped read/write discipline. So this version is incoherent without ALSO loosening the campaign-scoping discipline elsewhere, which is a much bigger change. Functionally this version doesn't behave differently from Version 1 because no upsert in the codebase reads across campaigns.)*

### What this additionally forbids
- Nothing new vs Version 1.

### Failure modes the dropped constraint protected against
- **Cross-campaign contamination** — Version 1 protects against this explicitly; Version 2 relies on implicit protection via existing campaign-scoping discipline at the upsert call sites.

### Why this version exists in the option set
Surface-level it looks like a simplification. In practice it's a foot-gun: the doctrine reads more permissive than the implementation can deliver, which means future contributors might attempt cross-campaign reasoning thinking the doctrine permits it and discover the code path doesn't exist. Better to keep the constraint explicit in the lock text even if implementation already enforces it elsewhere.

### Recommendation against
This is genuinely worse than Version 1 — pure docstring drift waiting to happen. Included in the option set per Jordan's framing request, but I'd flag this one as the wrong direction.

---

## Version 3 — Wide (drops both `same campaign_id` AND `unique` constraints)

> Strict literal matching remains the default identity rule. Exception: deterministic whole-token prefix collapse is permitted when the incoming canonical_name matches any `skeleton_origin=1` row's leading whole-token. On collision (multiple matching anchors), the most-recently-mentioned anchor wins; ambiguity telemetry is logged.

### What changes vs Version 1
- Same-campaign constraint dropped (same caveat as Version 2)
- Uniqueness constraint dropped
- Collision tiebreaker added (most-recently-mentioned wins)

### What this additionally permits
- Collapse when multiple `skeleton_origin=1` anchors match. "Eldrin" in campaign 17 with both "Eldrin Stormbow" and "Eldrin Brightwater" as authored canon would route to whichever was mentioned more recently.

### What the wider rule enables that the tight rule doesn't
- Handles the "two-Eldrins" edge case without surfacing it to the operator. Tight version refuses collapse and lets the bare-firstname row insert; wide version forces a resolution.

### Failure modes each dropped constraint enables
- **Same-campaign drop** — see Version 2; functionally inert today, but doctrine-drift risk.
- **Unique drop** — this is the load-bearing change. Recency-based tiebreaker is exactly the probabilistic equivalence that the anti-pattern catalog rejects, dressed as deterministic logic. "Most-recently-mentioned" is a statistical-popularity rule. Once this lands, the next external review proposing fuzzy-identity has a precedent to cite: "the doctrine already permits recency-based identity resolution between ambiguous anchors; here's a small extension..."

### Why this version exists in the option set
This is what the doctrine would look like if we prioritized "no operator-facing ambiguity" over "no probabilistic equivalence." It surfaces the tradeoff directly: tight version pushes ambiguity to the operator (refuses collapse, logs, lets bare-firstname row exist); wide version absorbs ambiguity into the system (auto-resolves via recency).

### Recommendation against
Strong recommend against. This version functionally reopens the fuzzy-identity door. The "two-Eldrins" case is rare enough that operator-facing ambiguity is the correct response — the operator can resolve the ambiguity by renaming one of the skeleton NPCs to be more distinct, which is the architecturally clean fix. Automating the resolution via recency is the failure mode §9.1 exists to prevent.

---

## Recommendation

**Version 1 (Tight) is the right lock.**

Reasoning:
- The same-campaign constraint is load-bearing in the doctrine even if the current implementation can't violate it — explicit > implicit, per ChatGPT and Gemini's convergent point on codifying exception classes.
- The uniqueness constraint is the load-bearing safety boundary that distinguishes "deterministic shorthand against declared canon" from "probabilistic equivalence between candidate anchors." Dropping it reopens the door to fuzzy-identity creep.
- The whole-token constraint isn't surfaced as a tradeoff in any version because dropping it (allowing substring) would obviously degenerate the rule. Worth keeping in the text anyway because future contributors will ask "why not substring?" and the answer should be in the lock.

The cost of Version 1: when a future campaign authors two skeleton NPCs sharing a leading token, the system refuses collapse and bare-firstname mentions create fragment rows. The operator either renames one of the skeleton NPCs to be more distinct (the architecturally clean fix) or accepts that this specific campaign has token-collision and lives with the fragmentation. The cost is operator-surface ambiguity in a rare case; the benefit is no fuzzy-identity backdoor in the doctrine.

## What's NOT in any version

A few things I considered and explicitly didn't surface as alternative phrasings, because they'd be architecturally wrong:

- **"Whole-token prefix at any position, not just leading"** — would match "Eldrin" against "Stormbow Eldrin" if such a row existed. Reverses natural-language convention (first names lead). Rejected.
- **"Suffix collapse as well as prefix"** — would match "Stormbow" against "Eldrin Stormbow." Architecturally symmetric to prefix but linguistically incorrect (English NPCs are addressed by first name, not last). Rejected unless project moves to a culture/setting where last-name address is canonical, which is a separate architectural question.
- **"Multi-token collapse"** — "Eldrin Storm" → "Eldrin Stormbow." Adds combinatorial ambiguity; not what we're observing in practice (LLM emits bare firstname or full name, rarely partial multi-token). Rejected as unnecessary scope.

These are deliberate omissions, not oversights.

## Implementation implications by version

| Constraint | Version 1 | Version 2 | Version 3 |
|---|---|---|---|
| Lookup scope | within same campaign | global (functionally same-campaign by call site) | global (with tiebreaker) |
| Collision behavior | refuse collapse, log, insert normally | refuse collapse, log, insert normally | auto-resolve via recency, log |
| Telemetry log line | `npc_anchor_ambiguous:` on multi-match | `npc_anchor_ambiguous:` on multi-match | `npc_anchor_collision_resolved:` on multi-match |
| Operator-surface behavior | bare-firstname row appears on multi-match (operator decides) | same as V1 | system silently picks (operator unaware unless they grep telemetry) |
| `skeleton_origin=0` rows | untouched (no token-prefix collapse for emergent canon) | untouched | untouched |

## Lock decision

Pick one. After lock, I draft the spec dispatch for Code with the locked language pre-loaded so Code converges on the locked text rather than drafting alternatives.
