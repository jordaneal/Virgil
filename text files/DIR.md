# Directory Layout — Virgil Project

Both ends of the tailnet sync. PC is the archive/work surface; server is the canonical runtime. This doc captures the layout on both sides and the routing between them. Verified May 7, 2026.

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
│   ├── dm_philosophy.md              # canonical source — symlinked from ../virgil-docs/
│   ├── campaigns/<id>/skeleton.md    # per-campaign authored canon
│   └── .env                          # secrets — NEVER push, NEVER commit
│
├── virgil-docs/                      # all .md project docs
│   ├── *_SPEC.md                     # locked specs (ADJUDICATION_LAYER, COMBAT_PERSISTENCE,
│   │                                 #   COMBAT_INITIATION_ORCHESTRATION, COMMITTED_ACTION_RESOLUTION,
│   │                                 #   CONSEQUENCE_SURFACING, ENCOUNTER_CADENCE_V1, PHASE_6_IDENTITY,
│   │                                 #   TIME_MENTION_V1, TRACK_7_2)
│   ├── *_REVIEW.md                   # spec review notes — siblings to _SPEC.md, route together to PC specs/
│   ├── ROADMAP.md / VIRGIL_MASTER.md / DOCTRINE.md / FAILURES.md / SESSIONS.md / WHY.md
│   ├── THE_GOAL.md / WORKING_WITH_CLAUDE.md / COMMANDS.md / CORPUS_BUILDER.md
│   ├── tests-to-run-post-session.md / website.md / DIR.md (this file)
│   ├── dm_philosophy.md → ../scripts/dm_philosophy.md   # SYMLINK
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
- `scripts/dm_philosophy.md` is the canonical source; `virgil-docs/dm_philosophy.md` is a symlink. PC has a regular-file copy in `text files/` which `push-docs` excludes (otherwise the symlink gets clobbered).
- `~/.env` and any campaign skeleton secrets must never be pushed via bulk sync. `push-all-to-pc.sh` routes by file pattern and doesn't touch `.env`.
- `corpus_builder/locks/` and `corpus_builder/logs/` are server-side runtime state. `pull-corpus` excludes them.

---

## PC (`Jordan@100.93.209.31`, `C:\Users\Jordan\Documents\Virgil Project\`)

```
Virgil Project/
├── python scripts/                   # mirror of server ~/scripts/*.py (excl. test_/calibrate_)
├── shell scripts/                    # mirror of server ~/scripts/*.sh
├── text files/                       # mirror of server ~/virgil-docs/ (non-spec .md)
│   └── refs/                         # mirror of ~/virgil-docs/refs/
├── specs/                            # mirror of server *_SPEC.md from ~/virgil-docs/
│   │                                 #   PLUS PC-authored historical specs (PHASE_11_1_SPEC,
│   │                                 #   PHASE_12_SPEC, skeleton_17.md) that live PC-only
├── calibration and test files/       # mirror of server test_*.py + calibrate_*.py
│                                     #   (Jordan archives green tests here manually)
├── campaigns/<id>/skeleton.md        # mirror of server campaigns/
├── corpus/                           # mirror of server ~/corpus_builder/
│   ├── extractors/ / eval_sets/ / findings/ / samples/ / output/ / docs/
│   ├── specs/                        # PC-authored corpus-scoped SPEC files (NOT pushed to server —
│   │                                 #   excluded by push-corpus to avoid race with push-all-to-pc.sh)
│   └── README.md
├── research/                         # PC-authored research scratch (deep-research-report.md)
├── website/                          # virgildm.com source (index.html, website.md)
├── media/                            # assets — don't touch unless asked
├── patches/                          # legacy patch scripts (archived; don't touch)
└── _trash/                           # PC-only soft-delete bin — files staged for manual deletion
```

**Notes:**
- PC `specs/` holds two file populations: server-mirrored `*_SPEC.md` (kept in sync via `push-all-to-pc.sh`) and PC-only historical files (`PHASE_NN_SPEC.md`, `skeleton_NN.md`). `push-all-to-pc.sh` is additive — never deletes PC-side files that aren't on the server.
- `_REVIEW.md` files route to `specs/` alongside their paired `_SPEC.md` — review docs and spec docs live together.
- `corpus/specs/` is PC-only; corpus-scoped SPECs don't flow back up.

---

## Routing between them

### Server → PC (downward sync)

| Trigger | Mechanism | Routing |
|---|---|---|
| `backup-virgil` (PC alias) | SSH runs `~/scripts/push-all-to-pc.sh` on server | Mirrors `~/scripts/` and `~/virgil-docs/` to PC subfolders by file pattern |
| `pull-corpus` (PC alias) | rsync from PC | server `~/corpus_builder/` → PC `corpus/` (excl. `locks/`, `logs/`) |

`push-all-to-pc.sh` routing (suffix-based):
- `~/scripts/*.py` (excl. test_/calibrate_) → `python scripts/`
- `~/scripts/*.sh` → `shell scripts/`
- `~/scripts/test_*.py` + `calibrate_*.py` → `calibration and test files/`
- `~/scripts/dm_philosophy.md` → `text files/`
- `~/scripts/campaigns/` → `campaigns/`
- `~/virgil-docs/*_SPEC.md` → `specs/`
- `~/virgil-docs/*_REVIEW.md` → `specs/`
- `~/virgil-docs/*.md` (non-spec, non-review) → `text files/`
- `~/virgil-docs/refs/` → `text files/refs/`
- **No corpus routing** — `~/corpus_builder/` is intentionally untouched by the bulk script (production-isolation rule).

### PC → Server (upward sync)

| Trigger | Mechanism | Routing |
|---|---|---|
| `push-docs` (PC alias) | rsync from PC | PC `text files/` → server `~/virgil-docs/` (excl. `dm_philosophy.md`) |
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
- `CORPUS_BUILDER.md` — Track 5 production-isolation rationale
