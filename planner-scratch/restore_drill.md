# Virgil DB Restore Drill — S67 Fix 1C

**Purpose.** One-shot ops doc for restoring the Virgil DB from a nightly
snapshot. Verified 2026-05-14 against `virgil_nightly_20260514_131216.db`.

**Snapshot pipeline (S67 Fix 1B):**
- Source: `/mnt/virgil_storage/virgil.db`
- Archive dir: `/mnt/virgil_storage/archive/`
- Naming: `virgil_nightly_YYYYMMDD_HHMMSS.db`
- Trigger: `virgil-backup.timer` (`~/.config/systemd/user/virgil-backup.timer`)
  - Schedule: `OnCalendar=*-*-* 03:30:00`
  - `Persistent=true` (catches up missed runs after reboot)
- Retention: 30-day rolling; older nightlies auto-deleted.
- Post-snapshot: `push-all-to-pc.sh` triggered in background.

---

## Restore procedure

### 1. Stop the bot

```bash
systemctl --user stop virgil-discord
```

### 2. Pick a snapshot

List recent nightly snapshots, ordered newest first:
```bash
ls -lt /mnt/virgil_storage/archive/virgil_nightly_*.db | head -10
```

For a session pre-ship snapshot (named `virgil_S65_preship.db`, etc.):
```bash
ls -lt /mnt/virgil_storage/archive/virgil_S*_preship.db
```

### 3. Verify the snapshot is healthy

```bash
SNAPSHOT="/mnt/virgil_storage/archive/virgil_nightly_YYYYMMDD_HHMMSS.db"
sqlite3 "$SNAPSHOT" "PRAGMA integrity_check;"
# Expected output: ok
```

If `integrity_check` returns anything other than `ok`, pick an older snapshot.

### 4. Spot-check the data

```bash
sqlite3 -header "$SNAPSHOT" \
  "SELECT id, name, status FROM dnd_campaigns ORDER BY id DESC LIMIT 5;"
sqlite3 -header "$SNAPSHOT" \
  "SELECT id, title, status FROM dnd_quests ORDER BY id DESC LIMIT 5;"
sqlite3 -header "$SNAPSHOT" \
  "SELECT campaign_id, mode, campaign_day, day_phase
   FROM dnd_scene_state ORDER BY campaign_id DESC LIMIT 5;"
```

Confirm the rows match your last-known good state.

### 5. Back up the current corrupt/stale DB (safety net)

```bash
mv /mnt/virgil_storage/virgil.db /mnt/virgil_storage/virgil.db.before-restore
```

Don't delete — if the restore is wrong, you can swap back.

### 6. Copy the snapshot into place

```bash
cp "$SNAPSHOT" /mnt/virgil_storage/virgil.db
chmod 644 /mnt/virgil_storage/virgil.db
chown jordaneal:jordaneal /mnt/virgil_storage/virgil.db
```

### 7. Confirm WAL mode persists

```bash
sqlite3 /mnt/virgil_storage/virgil.db "PRAGMA journal_mode;"
# Expected: wal
```

If the result is `delete`, re-apply:
```bash
sqlite3 /mnt/virgil_storage/virgil.db "PRAGMA journal_mode=WAL; PRAGMA wal_autocheckpoint=1000; PRAGMA synchronous=NORMAL;"
```

(The bot also re-applies these at startup via `db_init`, so this is belt-and-suspenders.)

### 8. Restart the bot

```bash
systemctl --user start virgil-discord
sleep 4
systemctl --user is-active virgil-discord
journalctl --user -u virgil-discord -n 20 --no-pager
```

Look for boot lines:
- `srd_resolver: index loaded entries=...`
- `fk_cascade_init: pragma_supported=1`
- `wal_init: journal_mode=wal ...`
- `chroma_init: sessions=... knowledge=...`
- `starting Discord DnD bot`

If boot fails, the snapshot's schema is older than the running code — fall back:
```bash
mv /mnt/virgil_storage/virgil.db.before-restore /mnt/virgil_storage/virgil.db
systemctl --user start virgil-discord
```

Then dig into the schema mismatch (likely a missing migration column added in a recent ship).

### 9. Verify in Discord

Run `/play` on the active campaign. Confirm the scene opens at the expected state. If nothing looks wrong, delete the safety-net copy:
```bash
rm /mnt/virgil_storage/virgil.db.before-restore
```

---

## Drill verification (2026-05-14)

Performed at S67 Fix 1C ship time:
- Snapshot: `virgil_nightly_20260514_131216.db` (20.7 MB)
- integrity_check: **ok** ✓
- Schema: 25 tables present (all expected core tables)
- Spot-check `dnd_campaigns`: 5 most recent rows readable (test campaigns 52-56 from S66 test runs)
- Spot-check `dnd_quests`: 5 most recent rows readable (S65.1 Test Quest #27 + later test quests)
- Spot-check `dnd_scene_state`: 3 most recent rows readable (modes/days/phases intact)

**Drill outcome: PASS.** Restore from a recent nightly snapshot produces a fully readable DB with correct schema and recent state.

---

## Operational notes

**WAL mode + .backup**: The `sqlite3 .backup` command uses SQLite's online backup API. It's safe against a live WAL-mode DB — readers and writers continue uninterrupted. The snapshot is internally consistent (no torn writes).

**WAL files in archive**: `.backup` produces a clean single-file `.db` — no `-wal` or `-shm` sidecar files in the archive. Restoring is a single-file copy.

**Snapshot size**: ~20-30 MB typical for a v0.x project. Compression not applied (storage is cheap; faster restore matters more).

**Retention**: 30 days × ~20 MB = ~600 MB max in `/mnt/virgil_storage/archive/`. The retention sweep at the end of each backup keeps this bounded.

**PC mirror**: `push-all-to-pc.sh` runs in background after each snapshot. PC archive at `Virgil Project/archive/` (or wherever push-all routes it) receives the new snapshot within minutes. Tailnet-mirrored, no cloud dependency (per memory: "no internet/GitHub backup").
