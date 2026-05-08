# Corpus Builder — Track 5 Research Tooling

Last updated: May 5, 2026 (initial draft, pre-first-extractor)

---

## Purpose

Track 5 builds offline extractors that mine the existing CRD3 + FIREBALL corpora for structured behavioral data about skilled DM play. The output is **research artifacts** — JSON timeline records that Jordan reads to inform Track 4 spec design.

Track 5 is **not**:
- A runtime retrieval system (that would be Path B; deferred indefinitely)
- A general extraction framework (each extractor is its own ship)
- A taxonomy committee (categories are validated against hand-samples before lock)
- Tied to Track 4's shipping cadence (parses run 1-2 days; can't gate production work)

Track 5 **is**:
- Decoupled background research that runs independently of Track 4
- One narrow-scope extractor per ship
- Path A research: data informs human design decisions, then deterministic Python ships
- Findings filed for whichever Track 4 ship benefits, not pre-committed to a specific ship

---

## Operating Principle

> Observed DM behavior → human reads findings → deterministic Python rules → constrained LLM narration.

The extractor's job is to produce structured event timelines from unstructured transcript text. The human's job is to read those timelines and decide what game systems to build. The LLM's job is narration only — never decision authority over campaign structure.

**Taxonomy-before-observation is architecture cosplay.** Every extractor validates its classification scheme against a hand-sample before running the full parse. If humans can't classify the categories consistently, the categories are wrong and get redesigned before the parse runs.

---

## Source corpora — what's actually usable

The two source datasets are not equivalently useful for timeline extraction. Session 14's corpus reconnaissance (`corpus_inventory_report.md`) found:

- **CRD3** — 355k substantive Matt Mercer turns across the Critical Role episode set. 54% DM↔player alternation rate within episodes. **Viable for flow / timeline / cadence work.** Filtered to MATT turns only at import — player turns add noise without improving DM behavioral signal.
- **FIREBALL** — DM-narrated combat exemplars, but **snapshots, not flows.** No multi-turn sequences. Useful for shape-of-narration analysis but cannot carry encounter pacing, time progression, or anything that depends on event ordering across turns.

**Implication for the queue:** extractors that need temporal context (Encounter Cadence, Time-Mention) run on CRD3 only. Extractors that operate on single-turn narration shape (e.g., a future Loot/Reward extractor catching "the chest contains" patterns) can run on both. Each extractor declares its source set in its findings doc.

Source files live at `/mnt/virgil_storage/dnd_datasets/`. Read-only treatment is enforced by the production-isolation rule below.

The 740k-document chroma_dnd embedding store (`/mnt/virgil_storage/chroma_dnd/`) is a separate derivative of the same source data, used for runtime retrieval during play. Track 5's JSON timeline output is independent — same source, different lens. If a Path B retrieval need ever emerges, embeddings can be built from Track 5 JSON, but that's filed.

---

## Directory Structure

```
/home/jordaneal/corpus_builder/
├── README.md                    # quick-start and current status
├── JOBS.md                      # live state of running parses (see Parallel-Job Protocol)
├── extractors/                  # extractor scripts, one per ship
│   ├── encounter_cadence.py
│   ├── time_mentions.py
│   └── ...
├── output/                      # JSON timeline records per extractor
│   ├── encounter_cadence/
│   │   ├── episode_001.json
│   │   ├── episode_002.json
│   │   └── ...
│   └── time_mentions/
│       └── ...
├── samples/                     # hand-sample validation outputs
│   ├── encounter_cadence_sample.json
│   └── ...
├── logs/                        # detached job logs
│   └── encounter_cadence_full.log
├── locks/                       # PID files for running jobs
│   └── encounter_cadence.pid
└── findings/                    # human-written summaries from reading output
    └── encounter_cadence_findings.md
```

**Production isolation:** `corpus_builder/` is physically separate from `/home/jordaneal/scripts/`. No production code imports from here. No extractor writes to the live SQLite DB. No extractor calls the cloud router. Pure offline batch work.

---

## Output Format Contract

Each extractor outputs JSON timeline records. Records are structured event entries, **not** text chunks. Every record locates an event in temporal context.

**Required fields (all extractors):**

```json
{
  "campaign": "C2",
  "episode": 41,
  "episode_position_pct": 0.34,
  "speaker": "MATT",
  "event_type": "combat_start",
  "raw_text": "...",
  "preceding_context_chars": 500,
  "extractor_version": "encounter_cadence_v1",
  "extracted_at": "2026-05-05T15:00:00Z"
}
```

**Per-extractor fields:** Each extractor adds its own classification fields beyond the required set. Example for `encounter_cadence`:

```json
{
  "...required fields...": "...",
  "trigger_category": "environmental_ambush",
  "preceding_scene_type": "travel",
  "time_since_last_encounter_chars": 8421,
  "warning_telegraph": "soft_hint"
}
```

**Output discipline:**
- One JSON file per episode, not one giant file. Easier to spot-check, easier to re-parse selectively, gives free crash recovery (see Parallel-Job Protocol).
- Files are append-safe — re-running an extractor on the same episode overwrites that episode's file only.
- All extractor versions logged in records so old data can be filtered when extractors evolve.
- `extracted_at` is the only timestamp permitted in records and is metadata-only. Event-content fields (`raw_text`, `event_type`, classification fields) must be a pure function of the source episode + extractor code, so two runs over the same episode produce byte-identical content.

---

## Hand-Sample Validation Protocol

Before any full-corpus parse runs, every extractor validates against a hand-sample. **No exceptions.**

**Steps:**

1. Extractor runs on 10 sampled episodes (varied across CRD3 campaign phases — early, mid, late, plus a one-shot if available).
2. Output written to `samples/{extractor_name}_sample.json`.
3. Jordan reviews the sample manually — minimum 50 records spot-checked. Spot-check = open the JSON, read the `raw_text` plus the classification fields, confirm the classification matches the text. No tooling required for v1; if review volume becomes painful, build a simple browse helper as its own ship.
4. Jordan answers three questions in `findings/{extractor_name}_validation.md`:
   - Does the extractor catch what it's supposed to catch? (recall check)
   - Does the extractor avoid false positives? (precision check)
   - Are the classification categories observable and repeatable? (taxonomy check)
5. If any answer is "no," the extractor gets redesigned and re-validated before the full parse runs.
6. Only after sign-off does the full parse kick off.

The hand-sample is the diagnostic gate. It catches extractor errors before 1-2 days of compute go into bad data.

---

## Parallel-Job Protocol

Full-corpus parses run 1-2 days. Code sessions reset mid-parse. Without protocol, the next Code session might restart a running job, kill in-progress data, or duplicate work.

**Live job state lives in `corpus_builder/JOBS.md`, not in `SESSIONS.md`.** SESSIONS.md is the project-wide chronological lessons archive; long-running-job operational status is local to corpus_builder. SESSIONS.md gets at most a one-line pointer ("Started encounter_cadence full parse, see corpus_builder/JOBS.md") when a parse begins or finishes.

### When starting a job

Code runs the parse detached and records job state:

```bash
cd /home/jordaneal/corpus_builder
nohup python3 extractors/encounter_cadence.py --full > logs/encounter_cadence_full.log 2>&1 &
echo $! > locks/encounter_cadence.pid
```

Code then writes a `JOBS.md` entry **before ending the session**:

```markdown
## encounter_cadence — full parse
- Status: RUNNING
- Started: 2026-05-05 15:30 UTC
- PID file: locks/encounter_cadence.pid
- Log file: logs/encounter_cadence_full.log
- Expected duration: ~36 hours
- Completion signal: log line `EXTRACTOR_COMPLETE: episodes_processed={N}`
- DO NOT RESTART. Check status before any action that touches corpus_builder/.
```

### When a new Code session starts

Before any action in `corpus_builder/`:

1. Read `corpus_builder/JOBS.md` for active background jobs.
2. For each job marked RUNNING:
   - Check if PID is alive: `ps -p $(cat locks/encounter_cadence.pid)`.
   - If alive: job is still running. Do NOT restart. Do NOT touch its output directory. Report status to Jordan.
   - If dead and log shows `EXTRACTOR_COMPLETE`: job finished cleanly. Harvest the output, mark JOBS.md entry DONE, archive the PID file.
   - If dead and log does NOT show completion: job crashed mid-parse. Read tail of log to diagnose. Report to Jordan before retrying. Recovery is cheap — per-episode idempotency means restarting the parse re-writes completed episodes byte-identically while incomplete episodes resume.
3. Only after all active jobs are accounted for, proceed with new work.

### When ending a session with a job still running

Code MUST update `JOBS.md` with:
- Latest log tail (last 20 lines)
- Current progress estimate (e.g., "episode 47 of ~150")
- Any anomalies seen
- Reaffirmation: "DO NOT RESTART"

Jordan can check progress from his phone via Claude Code on the server using these protocols.

---

## Extractor Design Constraints

Every extractor follows these rules:

1. **Deterministic only.** Regex, pattern matching, structural parsing. **No LLM calls.** Same project doctrine as `consequence_extractor`, `npc_extractor`, etc.

2. **Read-only on the corpus.** Extractors never modify CRD3/FIREBALL source files. Source data is treated as immutable input.

3. **Fail-open on unknown formats.** When an extractor encounters input it can't classify, it logs an `[EXTRACTOR_UNKNOWN]` line with raw text and continues. Bad data does not crash the parse.

4. **Idempotent on event content.** Running an extractor twice on the same episode produces identical event-content fields. The metadata-only `extracted_at` field is exempt; it's the only timestamp permitted in output and is not consumed by analysis.

5. **Single-category per extractor.** No "general purpose" extractors. Each ship is one event type. Composability comes from running multiple extractors against the same corpus, not from one extractor doing many things.

6. **Versioned output.** Every output record carries `extractor_version`. Bump the version when classification logic, regex patterns, or output schema change — anything that could make old records and new records non-comparable. Old data stays valid for historical analysis but new analyses use only the current version.

---

## Findings Documentation

After a full parse completes and Jordan reads the output, findings get written to `findings/{extractor_name}_findings.md`. The findings doc is the **deliverable of the extractor's research cycle**.

Findings doc structure:

- **Question asked.** What did this extractor try to answer?
- **Method.** What did the extractor look for? What was the classification scheme? Which source corpora ran (CRD3, FIREBALL, both)?
- **Sample size.** How many records, across how many episodes?
- **Headline numbers.** The actual statistics (averages, distributions, percentiles).
- **Surprises.** Patterns that contradicted prior assumptions.
- **Implications for Track 4.** What ships does this data inform? What spec decisions does it sharpen?
- **Limitations.** Where the data is noisy, partial, or unreliable.
- **Files.** Paths to raw output JSON for re-analysis.

Findings docs stay tight. Written for future-Jordan and future-Claude to re-orient quickly when a Track 4 spec needs the data.

---

## Active Extractor Queue

Order is "highest research value, least risk first." Not tied to Track 4 ship cadence.

| # | Extractor | Source | Status | Feeds (eventually) |
|---|-----------|--------|--------|--------------------|
| 1 | Encounter Cadence | CRD3 | NOT STARTED | World event triggers, encounter pacing |
| 2 | Time-Mention | CRD3 | NOT STARTED | Time progression, travel compression |
| 3 | Loot/Reward | CRD3 + FIREBALL | NOT STARTED | Loot generation post-inventory |
| 4 | Faction-Reference | CRD3 | NOT STARTED | Faction ticking (later) |

Queue is open. Jordan adds new extractors as research questions emerge. Extractors are built one at a time, validated, and parsed. No batching, no parallel extractor builds.

---

## Filed deferrals

The opening "Track 5 is not" section names what Track 5's *role* isn't. The list below is filed-but-deferred features that v1 specifically chose not to build:

- **Runtime retrieval corpora.** Path B (LLM queries corpus at inference time) is deferred. Track 5 is Path A (humans read findings, write deterministic rules).
- **General taxonomy framework.** No master ontology of DM events. Each extractor's categories are local to that extractor.
- **Real-time data ingestion.** Extractors run offline against static CRD3/FIREBALL. Live game telemetry is a separate concern (post-friends, post-userbase).
- **ChromaDB collections per extractor category.** Output is JSON timeline files, not embeddings. If a Path B retrieval need emerges later, embeddings can be built from the same JSON.
- **Cross-extractor analysis pipelines.** Each extractor's output stands alone. If cross-extractor analysis is needed, that's its own ship with its own scope.
- **Automated taxonomy discovery.** No clustering, no LLM-driven category proposal. Categories come from human design + hand-sample validation.

---

## The Discipline

The temptation, every time a new extractor ships, is to expand its scope. "While we're parsing for combat starts, why not also catch combat ends, party composition, damage totals..." That breaks the single-category rule and turns each ship into a multi-week project.

Hold the line: **one extractor, one event type, one ship.** Composability comes from running many narrow extractors. Each one is small enough to validate in a hand-sample and ship in a session of build-time + a 1-2 day parse.

The cathedral gets built one stone at a time, by accident, by shipping narrow extractors that turn out to inform multiple Track 4 ships each. The cathedral does not get built by trying to build the cathedral.
