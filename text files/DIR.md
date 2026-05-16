# Directory Layout — Virgil Project

Both ends of the tailnet sync. PC is the archive/work surface; server is the canonical runtime. This doc captures the layout on both sides and the routing between them. Verified May 11, 2026 (post-reorg).

---

## Server (`virgil-server`, `jordaneal@100.122.110.119`)

```
/home/jordaneal/
├── scripts/                          # production runtime — code Virgil actually runs
│   ├── *.py                          # bot modules (discord_dnd_bot, dnd_engine, dnd_orchestration,
│   │                                 #   adjudicator, avrae_listener, cloud_router, npc_extractor,
│   │                                 #   location_extractor, skeleton_loader, mechanical_hints,
│   │                                 #   commands_doc_generator, consequence_extractor,
│   │                                 #   loot_tables, weapon_schema, virgil_bot, morning_digest,
│   │                                 #   corpus_inventory, dm_philosophy_loader, dnd_knowledge_import)
│   ├── *.sh                          # ops scripts (push-all-to-pc.sh, sentinel.sh, deploy.sh,
│   │                                 #   data_cache.sh, cleanup_for_avrae.sh)
│   ├── test_*.py / calibrate_*.py    # green-test + calibration files (~40 files)
│   │                                 # (DM_PHILOSOPHY.md formerly lived here; moved to ../virgil-docs/ at S73.5 so it roundtrips via push-docs like every other canon doc)
│   ├── campaigns/<id>/skeleton.md    # per-campaign authored canon
│   └── .env                          # secrets — NEVER push, NEVER commit
│
├── virgil-docs/                      # all .md project docs
│   ├── (root .md)                    # canon + active cycle + server-only (BUG_1_SPEC):
│   │                                 #   THE_GOAL, WORKING_WITH_CLAUDE, VIRGIL_MASTER, DOCTRINE,
│   │                                 #   FAILURES, ROADMAP, SESSIONS, WHY, COMMANDS, DIR (this file),
│   │                                 #   DM_PHILOSOPHY.md (canonical here as of S73.5 — loader reads from virgil-docs/),
│   │                                 #   tests-to-run-post-session.md, MULTIPLAYER_FIXES.md (active plan),
│   │                                 #   S32_MULTIPLAYER_PLAYTEST_FINDINGS.md (active evidence),
│   │                                 #   RESOLUTION_BINDING_SPEC.md (current ship, locked),
│   │                                 #   MULTIPLAYER_VERIFY_DEFERRED.md (pickup doc, status TBD),
│   │                                 #   BUG_1_SPEC.md (server-only convention)
│   ├── specs/                        # locked-and-shipped specs and their review companions:
│   │                                 #   *_SPEC.md + *_REVIEW.md for completed tracks
│   │                                 #   (ADJUDICATION_LAYER, COMBAT_INITIATION_ORCHESTRATION,
│   │                                 #   COMBAT_PERSISTENCE_DIRECTIVE, COMMITTED_ACTION_RESOLUTION,
│   │                                 #   CONSEQUENCE_SURFACING, ENCOUNTER_CADENCE_V1, PHASE_6_IDENTITY,
│   │                                 #   TIME_MENTION_V1, TRACK_4_3, TRACK_6_4, TRACK_6_5_1, TRACK_7_2,
│   │                                 #   RESOLUTION_BINDING_REVIEW)
│   ├── research/                     # one-off research outputs (not load-bearing canon):
│   │                                 #   CORPUS_BUILDER.md, track5_findings_loot_reward.md, website.md
│   ├── _trash/                       # soft-deleted planner-to-Code prompts (recoverable):
│   │                                 #   SHIP_1_SPEC_PROMPT.md, SHIP_1_IMPLEMENTATION_PROMPT.md
│   └── refs/                         # reference material (Avrae Command List, etc.)
│
├── corpus_builder/                   # Track 5 — production-isolated from scripts/
│   ├── extractors/                   # corpus_*.py extractor scripts
│   ├── eval_sets/                    # *_eval_set_*.json test fixtures
│   ├── findings/                     # *_findings.md, *_validation*.md, parse stats,
│   │                                 #   track5_findings_*.md (production-side narrative summaries)
│   ├── samples/ / output/ / docs/
│   ├── locks/ / logs/                # runtime state — never sync to PC
│   ├── JOBS.md / README.md
│
└── .claude/projects/-home-jordaneal/memory/   # Code's auto-memory (persists across sessions)
    ├── MEMORY.md                     # index — first thing loaded each session
    └── *.md                          # individual memories (user/feedback/project/reference)
```

**Notes:**
- `virgil-docs/DM_PHILOSOPHY.md` is the canonical source — loaded by `dm_philosophy_loader.py` at every DM turn (mtime-cached). It roundtrips through `push-all-to-pc.sh` step 3 (downward) and `push-docs` (upward) like every other canon doc. No symlink, no special-case routing. (Originally `dm_philosophy.md` at `~/scripts/`; renamed ALL CAPS at S73.4; relocated to `~/virgil-docs/` at S73.5 to retire the cross-folder hybrid.)
- `~/.env` and any campaign skeleton secrets must never be pushed via bulk sync. `push-all-to-pc.sh` routes by file pattern and doesn't touch `.env`.
- `corpus_builder/locks/` and `corpus_builder/logs/` are server-side runtime state. `pull-corpus` excludes them.
- `BUG_1_SPEC.md` is server-only by convention — it doesn't have a PC counterpart and isn't pushed.
- `MULTIPLAYER_VERIFY_DEFERRED.md` is at server root; its lifecycle status (still active vs. served-its-purpose) was not classified during the reorg and is pending decision.

---

## PC (`Jordan@100.93.209.31`, `C:\Users\Jordan\Documents\Virgil Project\`)

```
Virgil Project/
├── python scripts/                   # mirror of server ~/scripts/*.py (excl. test_/calibrate_)
├── shell scripts/                    # mirror of server ~/scripts/*.sh
├── text files/                       # canon + active cycle + server-only .md from ~/virgil-docs/ root
│   │                                 #   (THE_GOAL, WORKING_WITH_CLAUDE, VIRGIL_MASTER, DOCTRINE,
│   │                                 #   FAILURES, ROADMAP, SESSIONS, WHY, COMMANDS, DIR,
│   │                                 #   DM_PHILOSOPHY.md, tests-to-run-post-session.md,
│   │                                 #   MULTIPLAYER_FIXES.md, S32_MULTIPLAYER_PLAYTEST_FINDINGS.md,
│   │                                 #   MULTIPLAYER_VERIFY_DEFERRED.md)
│   └── refs/                         # mirror of ~/virgil-docs/refs/
├── specs/                            # *_SPEC.md + *_REVIEW.md for shipped tracks (currently
│   │                                 #   populated via push-all-to-pc.sh's suffix-based rule
│   │                                 #   from ~/virgil-docs/ root). PLUS PC-only historical
│   │                                 #   specs that don't exist server-side: PHASE_11_1_SPEC,
│   │                                 #   PHASE_12_SPEC, skeleton_17.md. PLUS RESOLUTION_BINDING_SPEC
│   │                                 #   (current ship — kept here on PC, lives at ~/virgil-docs/ root
│   │                                 #   on server because it's an active cycle artifact).
├── calibration and test files/       # mirror of server test_*.py + calibrate_*.py
│                                     #   (Jordan archives green tests here manually)
├── campaigns/<id>/skeleton.md        # mirror of server campaigns/
├── corpus/                           # mirror of server ~/corpus_builder/
│   ├── extractors/ / eval_sets/ / findings/ / samples/ / output/ / docs/
│   ├── specs/                        # PC-authored corpus-scoped SPEC files (NOT pushed to server —
│   │                                 #   excluded by push-corpus to avoid race with push-all-to-pc.sh)
│   └── README.md
├── research/                         # one-off research scratch (CORPUS_BUILDER.md,
│   │                                 #   track5_findings_loot_reward.md, website.md doc,
│   │                                 #   deep-research-report.md — last one is PC-authored)
├── website/                          # virgildm.com source (index.html, website.md source —
│   │                                 #   distinct from research/website.md, which is the
│   │                                 #   project doc describing the site)
├── media/                            # assets — don't touch unless asked
├── patches/                          # legacy patch scripts (archived; don't touch)
├── planner-scratch/                  # planner working artifacts — drafts, review tables,
│                                     #   transient review docs. PC-only; never pushed.
│                                     #   Promoted to text files/ or specs/ via chat artifact
│                                     #   when content earns canonical status.
└── _trash/                           # soft-delete bin (SHIP_1_SPEC_PROMPT.md,
                                      #   SHIP_1_IMPLEMENTATION_PROMPT.md, Testing.txt)
```

**Notes:**
- PC `specs/` holds two file populations: server-mirrored `*_SPEC.md` / `*_REVIEW.md` (kept in sync via `push-all-to-pc.sh`'s suffix-based rule from `~/virgil-docs/` ROOT) and PC-only historical files (`PHASE_NN_SPEC.md`, `skeleton_NN.md`). `push-all-to-pc.sh` is additive — never deletes PC-side files that aren't on the server.
- `_REVIEW.md` files route to `specs/` alongside their paired `_SPEC.md` — review docs and spec docs live together.
- `corpus/specs/` is PC-only; corpus-scoped SPECs don't flow back up.
- **`planner-scratch/` is PC-only** by convention. Holds planner working artifacts (drafts, review tables, transient review docs) that aren't yet canonical. Never touched by any push alias. When content earns canonical status, planner produces a clean version as a chat artifact and Jordan places it in `text files/` or `specs/` as appropriate before pushing.
- **PC vs server `research/` superset:** PC `research/` is a superset of server `research/`. Server holds `CORPUS_BUILDER.md`, `track5_findings_loot_reward.md`, `website.md`; PC mirrors those (via step 3d) AND keeps the PC-authored `deep-research-report.md`. The downward rsync is additive (no `--delete`), so PC-authored files in `research/` are preserved across syncs but don't flow upward. If you want a PC-authored research doc to live on the server too, use `push-docs` from PC or copy it manually.
- **PC vs server `_trash/` superset:** same pattern. PC `_trash/` holds server-synced trashed items (via step 3e) plus any PC-side trash (e.g., `Testing.txt`). Additive; no upward sync.
- **PC vs server `text files/` // `~/virgil-docs/` root divergence:** `RESOLUTION_BINDING_SPEC.md` lives at server `~/virgil-docs/` root (active cycle, current ship) but at PC `specs/` (because `push-all-to-pc.sh` step 3b routes everything matching `*_SPEC.md` from the server root to PC `specs/`). This is a known asymmetry: while the spec is active, it sits in the canon-active bucket on server but flows into the archival specs bucket on PC. When the ship completes, the server-side file should be moved to `~/virgil-docs/specs/` to match.

---

## Routing between them

### Server → PC (downward sync)

| Trigger | Mechanism | Routing |
|---|---|---|
| `backup-virgil` (PC alias) | SSH runs `~/scripts/push-all-to-pc.sh` on server | Mirrors `~/scripts/` and `~/virgil-docs/` to PC subfolders by file pattern |
| `pull-corpus` (PC alias) | rsync from PC | server `~/corpus_builder/` → PC `corpus/` (excl. `locks/`, `logs/`) |

`push-all-to-pc.sh` routing (mixed suffix-based at root + whole-folder for post-reorg subfolders):
- `~/scripts/*.py` (excl. test_/calibrate_) → `python scripts/`
- `~/scripts/*.sh` → `shell scripts/`
- `~/scripts/test_*.py` + `calibrate_*.py` → `calibration and test files/`
- `~/scripts/campaigns/` → `campaigns/`
- `~/virgil-docs/*.md` (root-level, excl. *_SPEC.md, *_REVIEW.md) → `text files/`  (step 3 — includes DM_PHILOSOPHY.md as of S73.5)
- `~/virgil-docs/*_SPEC.md` + `*_REVIEW.md` (root-level only) → `specs/`  (step 3b — picks up BUG_1_SPEC.md and any active-ship SPEC like RESOLUTION_BINDING_SPEC.md)
- `~/virgil-docs/specs/` → `specs/`  (step 3c — shipped specs and their REVIEW companions, post-May-11 reorg)
- `~/virgil-docs/research/` → `research/`  (step 3d — one-off research outputs)
- `~/virgil-docs/_trash/` → `_trash/`  (step 3e — soft-deleted docs)
- `~/virgil-docs/refs/` → `text files/refs/`  (step 4)
- **No corpus routing** — `~/corpus_builder/` is intentionally untouched by the bulk script (production-isolation rule).
- Steps 3c–3e are guarded with `if [ -d ... ]` so the script is forward-compatible with hosts where these subfolders haven't been created yet.

### PC → Server (upward sync)

| Trigger | Mechanism | Routing |
|---|---|---|
| `push-docs` (PC alias) | rsync from PC | PC `text files/` → server `~/virgil-docs/` (DM_PHILOSOPHY.md included as of S73.5 — no special exclude needed) |
| `push-corpus` (PC alias) | rsync from PC | PC `corpus/` → server `~/corpus_builder/` (excl. `specs/`) |

PC has no per-file push aliases anymore; bulk sync via `push-docs` / `push-corpus`, or single-file rsync for ad-hoc pushes.

---

## Working command patterns (for future Code)

**`scp` does NOT work** for any remote path containing the space in `Virgil Project/` under PC's Windows OpenSSH — argument-splitting on the remote shell drops everything after the space. Verified May 7, 2026 across three quoting strategies. **Always use rsync with `--protect-args`** for any single-file push to PC:

```bash
rsync -avzL --no-perms --no-owner --no-group --protect-args \
  --rsync-path=C:/cygwin64/bin/rsync.exe \
  /path/to/local/file.ext \
  "Jordan@100.93.209.31:/cygdrive/c/Users/Jordan/Documents/Virgil Project/<subfolder>/"
```

**Remote `ls` on PC** — Windows cmd doesn't have `ls`; SSH-launched bash has a broken PATH. Use cygwin's binary directly:

```bash
ssh Jordan@100.93.209.31 'C:/cygwin64/bin/ls.exe "/cygdrive/c/Users/Jordan/Documents/Virgil Project/<subfolder>/"'
```

Avoid pipes (`|`, `&&`) inside the SSH-quoted command unless wrapped in `bash -c`; Windows cmd interprets them and breaks.

---

## Cross-references

- `push-all-to-pc.sh` — `~/scripts/push-all-to-pc.sh` (the source of truth for downward routing)
- `feedback_corpus_routing.md` — Code memory; corpus-specific routing detail
- `reference_pc_tailscale.md` — Code memory; SSH target + cygwin command patterns
- `research/CORPUS_BUILDER.md` — Track 5 production-isolation rationale
