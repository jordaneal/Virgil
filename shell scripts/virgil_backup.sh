#!/usr/bin/env bash
# virgil_backup.sh
#
# S67 Fix 1B — nightly DB snapshot with 30-day retention.
#
# Schedule via systemd timer (~/.config/systemd/user/virgil-backup.timer).
# Run manually for verification:
#     bash /home/jordaneal/scripts/virgil_backup.sh
#
# Uses `sqlite3 .backup` (online backup API) which works safely against a
# live DB in WAL mode — no exclusive lock; readers/writers continue while
# the backup runs.
#
# After snapshot success, kicks off push-all-to-pc.sh so PC mirror receives
# the archive within the same 24h window. Push runs in background; backup
# script returns as soon as the snapshot itself is durable.

set -uo pipefail

DB_PATH="/mnt/virgil_storage/virgil.db"
ARCHIVE_DIR="/mnt/virgil_storage/archive"
DATE_TAG="$(date +%Y%m%d_%H%M%S)"
SNAPSHOT_PATH="${ARCHIVE_DIR}/virgil_nightly_${DATE_TAG}.db"
LOG_PATH="/mnt/virgil_storage/digest/virgil_backup.log"
RETENTION_DAYS=30

# Ensure archive dir exists.
mkdir -p "${ARCHIVE_DIR}"
mkdir -p "$(dirname "${LOG_PATH}")"

log() {
  echo "[$(date -Iseconds)] $*" | tee -a "${LOG_PATH}"
}

log "virgil_backup: starting snapshot of ${DB_PATH} → ${SNAPSHOT_PATH}"

if [ ! -f "${DB_PATH}" ]; then
  log "virgil_backup: ERROR DB not found at ${DB_PATH}"
  exit 1
fi

# sqlite3 .backup is safe against a live DB (online backup API).
if sqlite3 "${DB_PATH}" ".backup ${SNAPSHOT_PATH}" 2>>"${LOG_PATH}"; then
  SIZE="$(stat -c%s "${SNAPSHOT_PATH}" 2>/dev/null || echo 0)"
  log "virgil_backup: snapshot OK size=${SIZE} bytes"
else
  log "virgil_backup: ERROR .backup command failed"
  exit 2
fi

# Sanity: integrity check on the snapshot (cheap, ~seconds for 20MB).
INTEGRITY="$(sqlite3 "${SNAPSHOT_PATH}" 'PRAGMA integrity_check;' 2>&1 | head -1)"
if [ "${INTEGRITY}" != "ok" ]; then
  log "virgil_backup: WARNING integrity_check failed: ${INTEGRITY}"
  # Don't delete the bad snapshot — keep it for diagnostics. But exit
  # non-zero so the timer flags this as a problem.
  exit 3
fi
log "virgil_backup: integrity_check=ok"

# Retention: rolling delete of snapshots older than RETENTION_DAYS.
# Match only the nightly snapshots (preserve session preship snapshots
# like virgil_S65_preship.db which don't carry the nightly prefix).
DELETED_COUNT=0
while IFS= read -r OLD; do
  rm -f "${OLD}" && DELETED_COUNT=$((DELETED_COUNT + 1))
  log "virgil_backup: retention removed ${OLD}"
done < <(find "${ARCHIVE_DIR}" -maxdepth 1 -name 'virgil_nightly_*.db' \
         -mtime "+${RETENTION_DAYS}" -type f 2>/dev/null)
log "virgil_backup: retention sweep removed=${DELETED_COUNT} (older than ${RETENTION_DAYS}d)"

# Trigger PC push in background so the snapshot reaches the tailnet mirror.
# Don't block backup exit on push — push has its own retry semantics.
if [ -x /home/jordaneal/scripts/push-all-to-pc.sh ]; then
  log "virgil_backup: triggering push-all-to-pc.sh (background)"
  nohup bash /home/jordaneal/scripts/push-all-to-pc.sh \
    >> "${LOG_PATH}" 2>&1 &
  log "virgil_backup: push pid=$!"
else
  log "virgil_backup: WARNING push-all-to-pc.sh not executable"
fi

log "virgil_backup: done"
exit 0
