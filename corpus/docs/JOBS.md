# corpus_builder — active jobs

No active jobs.

---

## Past jobs

### encounter_cadence — full parse
- Status: DONE
- Started: 2026-05-05T19:54:00Z
- Completed: 2026-05-05T19:54:22Z
- Duration: ~3 seconds (deterministic regex; ran much faster than the <10-min estimate)
- tmux session: corpus_encounter (exited cleanly; can be killed with `tmux kill-session -t corpus_encounter`)
- PID file: locks/encounter_cadence.pid (process exited before PID could be captured)
- Log file: logs/encounter_cadence_full.log
- Exit code: 0 (in logs/encounter_cadence_exit_code)
- Completion signal: `EXTRACTOR_COMPLETE: episodes_processed=140 records=243`
- `[EXTRACTOR_UNKNOWN]` count: 0
- Output: 140 per-episode JSON files at output/encounter_cadence/
- Stats: findings/encounter_cadence_full_parse_stats.md

---

When a `--full` parse is launched, append a new section above per `CORPUS_BUILDER.md` Parallel-Job Protocol. New Code sessions read this file BEFORE acting in `corpus_builder/` to avoid restarting a running parse.

Format for new entries:

```
## <extractor_name> — full parse
- Status: RUNNING | DONE | CRASHED
- Started: <UTC timestamp>
- PID file: locks/<extractor_name>.pid
- Log file: logs/<extractor_name>_full.log
- Expected duration: ~Nh
- Completion signal: log line `EXTRACTOR_COMPLETE: episodes_processed={N}`
- DO NOT RESTART. Check status before any action that touches corpus_builder/.
```
