# corpus_builder — PC mirror

Track 5 research tooling. Offline extractors that mine CRD3 + FIREBALL for structured DM-behavior data. Output is JSON timeline records used to inform Track 4 spec design.

This folder is a **read-only mirror** of `/home/jordaneal/corpus_builder/` on the linux server, plus the spec docs that live in `/home/jordaneal/virgil-docs/`. Files arrive here via single-file `scp` over Tailscale (per the Track-5 routing rule). **Do not edit files here** — edits made on the PC won't propagate back to the server.

Architecture reference: `/home/jordaneal/virgil-docs/CORPUS_BUILDER.md` (server side). Cross-extractor architectural lessons: `docs/corpus_builder_lessons_v1.md`.

## Directory layout

- `docs/` — durable methodology docs (lessons doc, candidates, JOBS)
- `eval_sets/` — test fixtures for regression runners (calibration, gate-set, validation-set)
- `extractors/` — extractor source + regression test runners
- `findings/` — per-extractor findings docs, validation reports, session logs, full-parse stats
- `output/` — full-parse JSON output (mining residue, NOT runtime data — see WHY.md)
- `samples/` — hand-sample outputs from each extractor's Phase 2
- `specs/` — Phase 1 spec docs

## What lives where (cheat sheet)

- "Where's the latest lessons doc?" → `docs/corpus_builder_lessons_v1.md`
- "Where are the eval sets the regression runner reads?" → `eval_sets/`
- "Where are the findings I'd hand to Track 4?" → `findings/<extractor>_findings.md`
- "Where's the actual mined corpus data?" → `output/<extractor>/<episode>.json`

## Read order for a new extractor

1. `docs/corpus_builder_lessons_v1.md` — durable principles (Stage 0, FP-family taxonomy, dual held-out sets, no-default-catchall).
2. `CORPUS_BUILDER.md` (server) — project structure, output contract, parallel-job protocol.
3. The most-recent prior extractor's `findings/` and `specs/` files — pattern reference.
4. The new extractor's spec at `specs/` — current decisions and open questions.

## Run commands (server-side reference only)

These commands live on the linux server, not the PC:

```bash
# Hand-sample (always first)
cd /home/jordaneal/corpus_builder
python3 extractors/<extractor_name>.py --sample
# writes samples/<extractor_name>_sample.json

# Full parse (after sign-off only, detached)
nohup python3 extractors/<extractor_name>.py --full > logs/<extractor_name>_full.log 2>&1 &
echo $! > locks/<extractor_name>.pid
# update docs/JOBS.md per the Parallel-Job Protocol
```

## Active queue

| # | Extractor | Source | Status |
|---|-----------|--------|--------|
| 1 | Encounter Cadence | CRD3 | SHIPPED v1.3 — see `findings/encounter_cadence_findings.md` |
| 2 | Time-Mention | CRD3 | Phase 1 spec drafted — see `specs/TIME_MENTION_V1_SPEC.md`; awaiting Jordan's §11 lock |
| 3 | Loot/Reward | CRD3 + FIREBALL | NOT STARTED |
| 4 | Faction-Reference | CRD3 | NOT STARTED |
