#!/usr/bin/env python3
"""Corpus inventory pass — Track 4 reconnaissance.

Walks the two known D&D corpora living under /mnt/virgil_storage/dnd_datasets:
  - CRD3   (Critical Role transcripts, JSON with TURNS arrays)
  - FIREBALL (D&D play logs, line-delimited JSON with before_utterances)

Produces a markdown report with concrete metrics for orchestration-value
assessment: turn counts, speaker distribution, sequence integrity,
length distributions, alternation rates.

This is reconnaissance, not extraction. Reads files, counts, computes
statistics. Does NOT write to ChromaDB. Does NOT mutate anything.

Output: /mnt/virgil_storage/digest/corpus_inventory_report.md
        /mnt/virgil_storage/digest/corpus_inventory_report.json (sidecar)

Run as a one-off:
    python3 /home/jordaneal/scripts/corpus_inventory.py
"""

import json
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


CORPUS_ROOT = Path("/mnt/virgil_storage/dnd_datasets")
CRD3_DIR = CORPUS_ROOT / "crd3"
FIREBALL_DIR = CORPUS_ROOT / "fireball"

REPORT_DIR = Path("/mnt/virgil_storage/digest")
REPORT_MD = REPORT_DIR / "corpus_inventory_report.md"
REPORT_JSON = REPORT_DIR / "corpus_inventory_report.json"

# Heuristic thresholds.
# - DM_TURN_MIN_WORDS: under this counts as "fragment" not a real DM beat
# - SEQUENCE_MIN_TURNS: minimum turn count to call a record a "sequence"
# - DM_NAME_TOKENS: matches Matt Mercer in CRD3 (case-insensitive)
DM_TURN_MIN_WORDS = 15
SEQUENCE_MIN_TURNS = 10
DM_NAME_TOKENS = {"MATT", "MATTHEW"}


def log(msg: str):
    """Stderr progress so the report file stays clean."""
    print(f"[{datetime.now().isoformat(timespec='seconds')}] {msg}",
          file=sys.stderr, flush=True)


def words(text: str) -> int:
    return len(text.split()) if text else 0


def percentiles(values: list, ps=(50, 90, 99)) -> dict:
    """Compute percentiles. Returns {p: value} dict; empty input -> all 0."""
    if not values:
        return {p: 0 for p in ps}
    s = sorted(values)
    out = {}
    for p in ps:
        idx = max(0, min(len(s) - 1, int(len(s) * p / 100)))
        out[p] = s[idx]
    return out


# ─────────────────────────────────────────────────────────────────────
# CRD3 inventory
# ─────────────────────────────────────────────────────────────────────

def inventory_crd3(crd3_dir: Path) -> dict:
    """Walk CRD3 JSON files, count turns and analyze structure."""
    log(f"Scanning CRD3 at {crd3_dir}")

    aligned = crd3_dir / "data" / "aligned data"
    if aligned.exists():
        files = sorted(aligned.rglob("*.json"))
    else:
        files = sorted(crd3_dir.rglob("*.json"))

    if not files:
        log("CRD3: no files found")
        return {'present': False}

    log(f"CRD3: {len(files)} JSON files found")

    # Aggregates
    total_chunks = 0
    total_turns = 0
    speaker_counter = Counter()
    speaker_word_total = Counter()
    dm_turn_lengths = []          # word counts of DM (Matt) turns
    chunk_summary_lengths = []    # word counts of CHUNK summaries
    episode_turn_counts = []      # per-episode turn counts
    episode_dm_turn_counts = []   # per-episode DM-turn counts
    episode_word_counts = []      # per-episode total words across turns
    alternation_scores = []       # per-episode DM↔player alternation rate
    dm_short_turns = 0            # DM turns under DM_TURN_MIN_WORDS
    dm_long_turns = 0             # DM turns at or above threshold
    parse_errors = 0
    multi_turn_sequences = 0      # chunks with ≥ SEQUENCE_MIN_TURNS turns

    for fi, fpath in enumerate(files, 1):
        if fi % 100 == 0:
            log(f"  CRD3: processed {fi}/{len(files)}")
        try:
            records = json.loads(fpath.read_text(encoding='utf-8'))
        except Exception as e:
            parse_errors += 1
            continue
        if not isinstance(records, list):
            records = [records]

        ep_turns = 0
        ep_dm_turns = 0
        ep_words = 0
        last_was_dm = None
        alternations = 0
        transitions = 0

        for rec in records:
            total_chunks += 1
            chunk_summary = rec.get('CHUNK', '') or ''
            if chunk_summary:
                chunk_summary_lengths.append(words(chunk_summary))

            turns = rec.get('TURNS', []) or []
            if len(turns) >= SEQUENCE_MIN_TURNS:
                multi_turn_sequences += 1

            for turn in turns:
                names = turn.get('NAMES', []) or []
                utters = turn.get('UTTERANCES', []) or []
                if isinstance(utters, list):
                    text = ' '.join(str(u) for u in utters)
                else:
                    text = str(utters)
                speaker = (names[0] if names else 'Unknown').strip()
                speaker_upper = speaker.upper()
                w = words(text)

                total_turns += 1
                ep_turns += 1
                ep_words += w
                speaker_counter[speaker] += 1
                speaker_word_total[speaker] += w

                is_dm = speaker_upper in DM_NAME_TOKENS
                if is_dm:
                    ep_dm_turns += 1
                    dm_turn_lengths.append(w)
                    if w < DM_TURN_MIN_WORDS:
                        dm_short_turns += 1
                    else:
                        dm_long_turns += 1

                # Alternation tracking
                if last_was_dm is not None:
                    transitions += 1
                    if last_was_dm != is_dm:
                        alternations += 1
                last_was_dm = is_dm

        if ep_turns:
            episode_turn_counts.append(ep_turns)
            episode_dm_turn_counts.append(ep_dm_turns)
            episode_word_counts.append(ep_words)
            if transitions:
                alternation_scores.append(alternations / transitions)

    log(f"CRD3 done: {total_turns:,} turns across {len(files)} files")

    return {
        'present': True,
        'file_count': len(files),
        'parse_errors': parse_errors,
        'total_chunks': total_chunks,
        'total_turns': total_turns,
        'multi_turn_sequences': multi_turn_sequences,
        'speakers': {
            'unique_count': len(speaker_counter),
            'top_10': speaker_counter.most_common(10),
        },
        'dm_turns': {
            'total': len(dm_turn_lengths),
            'long_count': dm_long_turns,
            'short_count': dm_short_turns,
            'short_pct': (100 * dm_short_turns / len(dm_turn_lengths)
                          if dm_turn_lengths else 0),
            'word_count_total': sum(dm_turn_lengths),
            'word_count_p50': percentiles(dm_turn_lengths)[50],
            'word_count_p90': percentiles(dm_turn_lengths)[90],
            'word_count_max': max(dm_turn_lengths) if dm_turn_lengths else 0,
        },
        'chunks': {
            'summary_count': len(chunk_summary_lengths),
            'summary_word_p50': percentiles(chunk_summary_lengths)[50],
            'summary_word_p90': percentiles(chunk_summary_lengths)[90],
        },
        'episodes': {
            'count': len(episode_turn_counts),
            'turns_p50': percentiles(episode_turn_counts)[50],
            'turns_p90': percentiles(episode_turn_counts)[90],
            'turns_max': max(episode_turn_counts) if episode_turn_counts else 0,
            'words_p50': percentiles(episode_word_counts)[50],
            'words_p90': percentiles(episode_word_counts)[90],
            'dm_turn_share_avg': (
                statistics.mean(
                    [d / t for d, t in zip(episode_dm_turn_counts, episode_turn_counts) if t]
                ) if episode_turn_counts else 0
            ),
            'alternation_rate_avg': (
                statistics.mean(alternation_scores) if alternation_scores else 0
            ),
        },
    }


# ─────────────────────────────────────────────────────────────────────
# FIREBALL inventory
# ─────────────────────────────────────────────────────────────────────

def inventory_fireball(fb_dir: Path) -> dict:
    """Walk FIREBALL .jsonl files, count records and analyze utterances."""
    log(f"Scanning FIREBALL at {fb_dir}")

    files = sorted(fb_dir.rglob("*filtered*.jsonl"))
    if not files:
        files = sorted(fb_dir.rglob("*.jsonl"))

    if not files:
        log("FIREBALL: no files found")
        return {'present': False}

    log(f"FIREBALL: {len(files)} jsonl files found")

    total_records = 0
    parse_errors = 0
    records_with_before = 0
    records_no_before = 0
    before_utterance_counts = []   # number of utterances per record
    before_word_counts = []        # total words per record's utterances
    before_individual_words = []   # per-utterance word counts
    command_dominant = 0           # records where most utterances start with !
    dice_dominant = 0              # records where utterances are mostly dice notation
    multi_turn_records = 0         # records with ≥ SEQUENCE_MIN_TURNS utterances
    short_records = 0              # records under 40 chars total (importer's filter)
    file_record_counts = []        # records per file

    for fi, fpath in enumerate(files, 1):
        if fi % 5 == 0:
            log(f"  FIREBALL: processed {fi}/{len(files)}")
        rcount = 0
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    rcount += 1
                    total_records += 1
                    try:
                        rec = json.loads(line)
                    except Exception:
                        parse_errors += 1
                        continue

                    before = rec.get('before_utterances') or []
                    if not before:
                        records_no_before += 1
                        continue
                    records_with_before += 1

                    # Per-record stats
                    before_utterance_counts.append(len(before))
                    if len(before) >= SEQUENCE_MIN_TURNS:
                        multi_turn_records += 1

                    record_words = 0
                    cmd_count = 0
                    dice_count = 0
                    for u in before:
                        s = str(u).strip()
                        w = words(s)
                        before_individual_words.append(w)
                        record_words += w
                        if s.startswith('!'):
                            cmd_count += 1
                        # Cheap dice heuristic: short string heavy on 'd' chars
                        # (e.g., "1d20+5", "2d6", "3d8 fire damage")
                        if 0 < len(s) < 100 and s.lower().count('d') >= 2 and any(
                                c.isdigit() for c in s):
                            dice_count += 1
                    before_word_counts.append(record_words)

                    if len(before):
                        if cmd_count / len(before) > 0.5:
                            command_dominant += 1
                        if dice_count / len(before) > 0.5:
                            dice_dominant += 1
                    if record_words < 8:
                        short_records += 1
        except Exception as e:
            log(f"  FIREBALL: error on {fpath.name}: {e}")
            continue

        file_record_counts.append(rcount)

    log(f"FIREBALL done: {total_records:,} records across {len(files)} files")

    return {
        'present': True,
        'file_count': len(files),
        'parse_errors': parse_errors,
        'total_records': total_records,
        'records_with_before_utterances': records_with_before,
        'records_no_before_utterances': records_no_before,
        'records_pct_with_before': (
            100 * records_with_before / total_records if total_records else 0
        ),
        'multi_turn_records': multi_turn_records,
        'multi_turn_pct': (
            100 * multi_turn_records / records_with_before
            if records_with_before else 0
        ),
        'command_dominant_records': command_dominant,
        'dice_dominant_records': dice_dominant,
        'short_records': short_records,
        'utterances_per_record': {
            'p50': percentiles(before_utterance_counts)[50],
            'p90': percentiles(before_utterance_counts)[90],
            'max': max(before_utterance_counts) if before_utterance_counts else 0,
        },
        'words_per_record': {
            'p50': percentiles(before_word_counts)[50],
            'p90': percentiles(before_word_counts)[90],
        },
        'words_per_utterance': {
            'p50': percentiles(before_individual_words)[50],
            'p90': percentiles(before_individual_words)[90],
        },
        'records_per_file': {
            'p50': percentiles(file_record_counts)[50],
            'p90': percentiles(file_record_counts)[90],
            'max': max(file_record_counts) if file_record_counts else 0,
        },
    }


# ─────────────────────────────────────────────────────────────────────
# Report rendering
# ─────────────────────────────────────────────────────────────────────

def render_report(crd3: dict, fb: dict) -> str:
    """Render the inventory dicts to a markdown report."""
    out = []
    out.append("# Corpus Inventory Report")
    out.append("")
    out.append(f"Generated: {datetime.now().isoformat(timespec='seconds')}")
    out.append(f"Corpus root: `{CORPUS_ROOT}`")
    out.append("")
    out.append("## Summary")
    out.append("")
    if crd3.get('present'):
        out.append(f"- **CRD3**: {crd3['file_count']:,} files, "
                   f"{crd3['total_chunks']:,} chunks, "
                   f"{crd3['total_turns']:,} turns")
    else:
        out.append("- **CRD3**: NOT FOUND")
    if fb.get('present'):
        out.append(f"- **FIREBALL**: {fb['file_count']:,} files, "
                   f"{fb['total_records']:,} records, "
                   f"{fb['records_with_before_utterances']:,} with "
                   f"before_utterances ({fb['records_pct_with_before']:.1f}%)")
    else:
        out.append("- **FIREBALL**: NOT FOUND")
    out.append("")

    # ── CRD3 ──────────────────────────────────────────────────────
    if crd3.get('present'):
        out.append("## CRD3 (Critical Role)")
        out.append("")
        out.append(f"- Files: {crd3['file_count']:,}  ")
        out.append(f"- Parse errors: {crd3['parse_errors']:,}  ")
        out.append(f"- Total chunks: {crd3['total_chunks']:,}  ")
        out.append(f"- Total turns: {crd3['total_turns']:,}  ")
        out.append(f"- Multi-turn sequences (≥{SEQUENCE_MIN_TURNS} turns "
                   f"in one chunk): {crd3['multi_turn_sequences']:,}")
        out.append("")
        out.append("### Speaker distribution")
        out.append("")
        out.append(f"- Unique speakers: {crd3['speakers']['unique_count']}  ")
        out.append("- Top 10:")
        for name, count in crd3['speakers']['top_10']:
            out.append(f"  - **{name}**: {count:,} turns")
        out.append("")
        out.append("### DM (Matt Mercer) turns — the load-bearing data")
        out.append("")
        dm = crd3['dm_turns']
        out.append(f"- Total DM turns: {dm['total']:,}  ")
        out.append(f"- Substantive (≥{DM_TURN_MIN_WORDS} words): "
                   f"{dm['long_count']:,}  ")
        out.append(f"- Fragments (<{DM_TURN_MIN_WORDS} words): "
                   f"{dm['short_count']:,} ({dm['short_pct']:.1f}%)  ")
        out.append(f"- Total DM words: {dm['word_count_total']:,}  ")
        out.append(f"- DM turn length p50: {dm['word_count_p50']} words  ")
        out.append(f"- DM turn length p90: {dm['word_count_p90']} words  ")
        out.append(f"- DM turn length max: {dm['word_count_max']:,} words")
        out.append("")
        out.append("### Episode shape")
        out.append("")
        ep = crd3['episodes']
        out.append(f"- Episode count: {ep['count']:,}  ")
        out.append(f"- Turns per episode p50: {ep['turns_p50']:,}  ")
        out.append(f"- Turns per episode p90: {ep['turns_p90']:,}  ")
        out.append(f"- Turns per episode max: {ep['turns_max']:,}  ")
        out.append(f"- Words per episode p50: {ep['words_p50']:,}  ")
        out.append(f"- Words per episode p90: {ep['words_p90']:,}  ")
        out.append(f"- Avg DM-turn share: "
                   f"{ep['dm_turn_share_avg']*100:.1f}% of turns are DM  ")
        out.append(f"- Avg alternation rate: "
                   f"{ep['alternation_rate_avg']*100:.1f}% of "
                   f"transitions cross DM↔player  ")
        out.append("")
        out.append("### Chunk summaries (CHUNK field)")
        out.append("")
        ch = crd3['chunks']
        out.append(f"- Summary count: {ch['summary_count']:,}  ")
        out.append(f"- Summary length p50: {ch['summary_word_p50']} words  ")
        out.append(f"- Summary length p90: {ch['summary_word_p90']} words")
        out.append("")

    # ── FIREBALL ──────────────────────────────────────────────────
    if fb.get('present'):
        out.append("## FIREBALL")
        out.append("")
        out.append(f"- Files: {fb['file_count']:,}  ")
        out.append(f"- Parse errors: {fb['parse_errors']:,}  ")
        out.append(f"- Total records: {fb['total_records']:,}  ")
        out.append(f"- Records with before_utterances: "
                   f"{fb['records_with_before_utterances']:,} "
                   f"({fb['records_pct_with_before']:.1f}%)  ")
        out.append(f"- Records with no before_utterances: "
                   f"{fb['records_no_before_utterances']:,}")
        out.append("")
        out.append("### Sequence value")
        out.append("")
        out.append(f"- Multi-utterance records "
                   f"(≥{SEQUENCE_MIN_TURNS} utterances): "
                   f"{fb['multi_turn_records']:,} "
                   f"({fb['multi_turn_pct']:.1f}% of records-with-before)  ")
        out.append(f"- Utterances per record p50: "
                   f"{fb['utterances_per_record']['p50']}  ")
        out.append(f"- Utterances per record p90: "
                   f"{fb['utterances_per_record']['p90']}  ")
        out.append(f"- Utterances per record max: "
                   f"{fb['utterances_per_record']['max']:,}")
        out.append("")
        out.append("### Noise filtering")
        out.append("")
        out.append(f"- Command-dominant records (>50% utterances start "
                   f"with `!`): {fb['command_dominant_records']:,}  ")
        out.append(f"- Dice-dominant records (>50% are dice notation): "
                   f"{fb['dice_dominant_records']:,}  ")
        out.append(f"- Short records (<8 words total): "
                   f"{fb['short_records']:,}")
        out.append("")
        out.append("### Length distribution")
        out.append("")
        out.append(f"- Words per record p50: {fb['words_per_record']['p50']}  ")
        out.append(f"- Words per record p90: {fb['words_per_record']['p90']}  ")
        out.append(f"- Words per single utterance p50: "
                   f"{fb['words_per_utterance']['p50']}  ")
        out.append(f"- Words per single utterance p90: "
                   f"{fb['words_per_utterance']['p90']}")
        out.append("")
        out.append("### Per-file shape")
        out.append("")
        out.append(f"- Records per file p50: {fb['records_per_file']['p50']:,}  ")
        out.append(f"- Records per file p90: {fb['records_per_file']['p90']:,}  ")
        out.append(f"- Records per file max: {fb['records_per_file']['max']:,}")
        out.append("")

    # ── Cross-corpus interpretation ───────────────────────────────
    out.append("## Interpretation guide")
    out.append("")
    out.append("**For orchestration learning, the load-bearing numbers are:**")
    out.append("")
    out.append("- CRD3 *substantive DM turns* — the count of DM utterances "
               f"≥{DM_TURN_MIN_WORDS} words. Each is a candidate dramatic "
               "move (scene set, NPC response, consequence framing).")
    out.append("- CRD3 *episode alternation rate* — high alternation means "
               "DM is in genuine back-and-forth dialogue with players "
               "(orchestration material). Low alternation means monologue "
               "blocks (less useful for move extraction).")
    out.append("- FIREBALL *multi-utterance records* — these contain "
               "actual conversational sequences. Single-utterance records "
               "are isolated snippets, much weaker for sequence learning.")
    out.append("")
    out.append("**Decision points:**")
    out.append("")
    out.append("- If CRD3 substantive DM turn count is in tens of thousands "
               "and alternation rate >40%, beat extraction is viable.")
    out.append("- If FIREBALL multi-utterance percentage is >20%, "
               "sequence-aware retrieval is viable.")
    out.append("- If both are low, the right next move is authored "
               "directives (philosophy, beat libraries) rather than "
               "extraction.")
    out.append("")
    return "\n".join(out)


# ─────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────

def main():
    t0 = time.time()
    log("=" * 60)
    log("Corpus inventory pass")
    log("=" * 60)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    crd3 = inventory_crd3(CRD3_DIR) if CRD3_DIR.exists() else {'present': False}
    fb = inventory_fireball(FIREBALL_DIR) if FIREBALL_DIR.exists() else {'present': False}

    md = render_report(crd3, fb)
    REPORT_MD.write_text(md, encoding='utf-8')

    sidecar = {
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'corpus_root': str(CORPUS_ROOT),
        'crd3': crd3,
        'fireball': fb,
        'elapsed_seconds': round(time.time() - t0, 1),
    }
    REPORT_JSON.write_text(json.dumps(sidecar, indent=2, default=str),
                           encoding='utf-8')

    log(f"Report written to {REPORT_MD}")
    log(f"Sidecar JSON at  {REPORT_JSON}")
    log(f"Elapsed: {time.time() - t0:.1f}s")


if __name__ == '__main__':
    main()
