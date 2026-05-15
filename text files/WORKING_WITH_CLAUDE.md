

---

## Doc-currency discipline (filed post-Inversion-sketch, S70-equivalent planner correction)

**The lapse:** SESSIONS.md drifted twelve sessions out of date (last entry S52 while project state was at Inversion sketch). ROADMAP, FAILURES, DOCTRINE, WHY, VIRGIL_MASTER all carried pre-mandate state. External reviewers (Oracle, GPT, Gemini) read canonical docs as authoritative source; reasoning ran against stale ground truth. Oracle drift in convergent-review "fire S65" instruction was downstream of this — docs Oracle reads named S52 as recent.

**Root cause:** Doc updates kept losing to higher-friction surfaces. Every session had something more urgent — a HALT to walk, a dispatch to draft, a review to weigh. Doc updates are durable but non-urgent. Without discipline they get squeezed out indefinitely. Each individual skip was defensible; the cumulative skip wasn't.

**Standing practice from this point forward (three discipline rules):**

### Rule 1 — Doc updates land same-turn as Code handoff

When a Code session lands and planner writes the post-session response, doc updates fire in the same response. Not "later," not "when there's a gap." Same turn.

Minimum updates per ship:
- **SESSIONS.md** — one entry per shipped session (compact: scope, ship status, doctrine impact, cross-references)
- **FAILURES.md** — only if a doctrine candidate moved status (new instance, anchored, refined)
- **ROADMAP.md** — only if §11 lock changed priority queue or filed-forward state
- **DOCTRINE.md** — only if anchored doctrine moved (new §-entry, instance-list update, candidate filed)
- **WHY.md** — only if architectural reasoning would compound across future sessions
- **VIRGIL_MASTER.md** — only if state snapshot changed materially

Most sessions touch SESSIONS + zero or one other doc. Total append cost: 5-15 minutes of writes per session.

### Rule 2 — Staleness flag on external-review dispatches

When operator says "ask GPT," "Oracle response below," "Gemini's take," or otherwise dispatches a review against the canonical docs, planner checks doc currency before drafting the prompt.

Three states:
- **Current** — docs reflect last shipped session. Dispatch as-is.
- **Stale** — docs lag ≤1 session behind shipped state. Planner names the staleness explicitly in the dispatch ("note: SESSIONS.md hasn't received the S68 entry yet; that ship covered N-4 pronoun lock + N-3 HALT to multi-spec").
- **Significantly stale** — docs lag ≥2 sessions. Halt dispatch, fire doc updates first, then dispatch with current docs.

Reviewer drift downstream of stale docs is a planner failure, not a reviewer failure. Naming the staleness costs one paragraph; updating before dispatch costs 10 minutes; both are cheaper than a review pass reasoning against wrong ground truth.

### Rule 3 — Session-start self-check on doc currency

At session start (operator sends "go," shares a Code handoff, poses a planning question), planner reads SESSIONS.md tail before architecture work resumes. If last entry doesn't match last known shipped session, doc updates fire first.

One tool call per session start. Catches drift before it compounds.

### What this discipline does not do

- Doesn't catch every architectural-reasoning failure. Drift in non-doc surfaces (operator confidence, planner self-assessment, doctrine pattern recognition) requires different discipline.
- Doesn't replace the existing end-of-session handoff format. Handoff stays; doc updates are additional, not substitute.
- Doesn't apply to planner-scratch files. Those are workshop, not canon. Currency expectation lower.
- Doesn't apply to specs/ files individually — specs land at lock time per Path A cadence and don't need session-by-session updates after lock.

### The meta-observation that earned this discipline

Planner optimizes for next architectural move and treats operational hygiene as overhead. This bias produces good architecture sketches and stale docs. The corrective is treating doc updates as part of the ship, not as work that happens between ships. The discipline is mechanical (rules above), not motivational (try harder).

Operator named this lapse twice in one conversation arc — first slash sprawl, then doc lag. Both were real failures planner should have flagged before operator did. Pattern noted; standing practice above is the structural response, not a one-time fix.
