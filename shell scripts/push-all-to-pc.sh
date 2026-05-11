#!/usr/bin/env bash
# push-all-to-pc.sh
#
# End-of-session backup: pushes virgil's working files to Jordan's PC
# over Tailscale. Direction is virgil -> PC (additive; never deletes
# PC-side files). Run from virgil. Requires PC reachable on tailnet
# with OpenSSH server enabled.
#
# Usage: bash /home/jordaneal/scripts/push-all-to-pc.sh

set -uo pipefail
# Note: 'set -e' is intentionally OFF. Cygwin rsync 3.2.7 on Windows has a known
# bug where it returns exit-12 on socket teardown after a successful transfer
# (https://lists.samba.org/archive/rsync/). Files land correctly but the script
# would abort. We trap exit codes per-rsync and only fail on real errors.
RSYNC_OK=true
run_rsync() {
  "$@" || {
    rc=$?
    # 12 is the socket teardown bug after successful transfer; tolerate it.
    # Any other exit is a real failure.
    if [ "$rc" -ne 12 ]; then
      echo "  ERROR: rsync failed with exit $rc" >&2
      RSYNC_OK=false
    fi
  }
}

PC_HOST="100.93.209.31"
PC_USER="Jordan"
# Cygwin path style on PC. /cygdrive/c/ maps to Windows C:\
PC_BASE="/cygdrive/c/Users/Jordan/Documents/Virgil Project"
# rsync.exe lives in Cygwin's bin; not on cmd.exe PATH so we point at it explicitly.
PC_RSYNC="C:/cygwin64/bin/rsync.exe"

SSH_TARGET="${PC_USER}@${PC_HOST}"

# rsync flags:
#   -a archive (recursive, links, times) - but we strip Windows-incompatible bits
#   -v verbose, -z compress in transit
#   --no-perms --no-owner --no-group: skip metadata Windows can't represent
#   -L follow symlinks (transform to real files at the destination)
#   --rsync-path: tells local rsync where Cygwin's rsync.exe lives on the PC
RSYNC="rsync -avzL --no-perms --no-owner --no-group --protect-args --rsync-path=${PC_RSYNC}"

# Common excludes for any virgil-side directory we sync
COMMON_EXCLUDES=(
  --exclude='__pycache__/'
  --exclude='.pytest_cache/'
  --exclude='*.pyc'
  --exclude='*.bak.*'
  --exclude='.env'
  --exclude='*.db'
  --exclude='*.tmp'
  --exclude='.DS_Store'
)

# 1a) scripts/*.py (excl. test_*/calibrate_*) -> Virgil Project/python scripts/
# dnd_knowledge_import.py is excluded — its authoritative PC location is the
# corpus/ folder (Track 5 reference copy), not python scripts/. The file still
# lives on virgil for reference but no longer roundtrips through this push.
echo "==> scripts/ python -> Virgil Project/python scripts/"
run_rsync $RSYNC \
  "${COMMON_EXCLUDES[@]}" \
  --exclude='test_*.py' \
  --exclude='calibrate_*.py' \
  --exclude='dnd_knowledge_import.py' \
  --include='*.py' \
  --include='srd_monsters.json' \
  --exclude='*' \
  /home/jordaneal/scripts/ \
  "${SSH_TARGET}:${PC_BASE}/python scripts/"

# 1b) scripts/*.sh -> Virgil Project/shell scripts/
echo "==> scripts/ shell -> Virgil Project/shell scripts/"
run_rsync $RSYNC \
  "${COMMON_EXCLUDES[@]}" \
  --include='*.sh' \
  --exclude='*' \
  /home/jordaneal/scripts/ \
  "${SSH_TARGET}:${PC_BASE}/shell scripts/"

# 1c) scripts/test_*.py + calibrate_*.py -> Virgil Project/calibration and test files/
echo "==> scripts/ tests + calibration -> Virgil Project/calibration and test files/"
run_rsync $RSYNC \
  "${COMMON_EXCLUDES[@]}" \
  --include='test_*.py' \
  --include='calibrate_*.py' \
  --exclude='*' \
  /home/jordaneal/scripts/ \
  "${SSH_TARGET}:${PC_BASE}/calibration and test files/"

# Brief pause after calibration step — Cygwin rsync 3.2.7 occasionally crashes
# with EAGAIN on the receiver; the sleep lets the PC's sshd recover before the
# next connection attempt.
sleep 2

# 1d) scripts/dm_philosophy.md -> Virgil Project/text files/
#     (Live file lives in scripts/ on virgil; on PC it groups with the other docs.)
echo "==> scripts/dm_philosophy.md -> Virgil Project/text files/"
run_rsync $RSYNC \
  "${COMMON_EXCLUDES[@]}" \
  --include='dm_philosophy.md' \
  --exclude='*' \
  /home/jordaneal/scripts/ \
  "${SSH_TARGET}:${PC_BASE}/text files/"

# 2) scripts/campaigns/ -> Virgil Project/campaigns/
#    Per-campaign skeleton.md and any other authored canon.
echo "==> scripts/campaigns/ -> Virgil Project/campaigns/"
run_rsync $RSYNC \
  "${COMMON_EXCLUDES[@]}" \
  /home/jordaneal/scripts/campaigns/ \
  "${SSH_TARGET}:${PC_BASE}/campaigns/"

# 3) virgil-docs/*.md (excluding the dm_philosophy.md symlink, already
#    covered by step 1 from its real location, AND excluding *_SPEC.md
#    and *_REVIEW.md files which route to specs/ in step 3b below)
#    -> Virgil Project/text files/
echo "==> virgil-docs/ (non-spec, non-review md) -> Virgil Project/text files/"
run_rsync $RSYNC \
  "${COMMON_EXCLUDES[@]}" \
  --exclude='dm_philosophy.md' \
  --exclude='*_SPEC.md' \
  --exclude='*_REVIEW.md' \
  --exclude='refs/' \
  --exclude='inbox/' \
  --exclude='specs/' \
  --exclude='research/' \
  --exclude='_trash/' \
  --include='*.md' \
  --exclude='*' \
  /home/jordaneal/virgil-docs/ \
  "${SSH_TARGET}:${PC_BASE}/text files/"

# 3b) virgil-docs/*_SPEC.md + *_REVIEW.md (ROOT-LEVEL) -> Virgil Project/specs/
#     Suffix-based routing. After the May 11, 2026 reorg, most shipped specs and
#     their REVIEW companions live in virgil-docs/specs/ (handled by step 3c).
#     This step still picks up any root-level SPEC/REVIEW files — currently
#     BUG_1_SPEC.md (server-only) and RESOLUTION_BINDING_SPEC.md (active ship).
echo "==> virgil-docs/*_SPEC.md + *_REVIEW.md (root) -> Virgil Project/specs/"
run_rsync $RSYNC \
  "${COMMON_EXCLUDES[@]}" \
  --exclude='specs/' \
  --exclude='research/' \
  --exclude='_trash/' \
  --include='*_SPEC.md' \
  --include='*_REVIEW.md' \
  --exclude='*' \
  /home/jordaneal/virgil-docs/ \
  "${SSH_TARGET}:${PC_BASE}/specs/"

# 3c) virgil-docs/specs/ -> Virgil Project/specs/   (post-reorg subfolder)
#     Shipped spec + review companions moved into this subfolder during the
#     May 11, 2026 reorg. Flattens into PC specs/ alongside step 3b's root-level
#     pickups; PC has no specs/specs/ — both source paths target the same dest.
if [ -d /home/jordaneal/virgil-docs/specs ]; then
  echo "==> virgil-docs/specs/ -> Virgil Project/specs/"
  run_rsync $RSYNC \
    "${COMMON_EXCLUDES[@]}" \
    /home/jordaneal/virgil-docs/specs/ \
    "${SSH_TARGET}:${PC_BASE}/specs/"
fi

# 3d) virgil-docs/research/ -> Virgil Project/research/   (post-reorg subfolder)
#     One-off research outputs (CORPUS_BUILDER, track5_findings_*, website doc).
#     PC research/ is a superset — keeps PC-authored deep-research-report.md
#     because rsync here is additive (no --delete).
if [ -d /home/jordaneal/virgil-docs/research ]; then
  echo "==> virgil-docs/research/ -> Virgil Project/research/"
  run_rsync $RSYNC \
    "${COMMON_EXCLUDES[@]}" \
    /home/jordaneal/virgil-docs/research/ \
    "${SSH_TARGET}:${PC_BASE}/research/"
fi

# 3e) virgil-docs/_trash/ -> Virgil Project/_trash/   (post-reorg subfolder)
#     Soft-deleted docs (recoverable). Additive sync; PC _trash/ keeps any
#     PC-side trashed items unaffected.
if [ -d /home/jordaneal/virgil-docs/_trash ]; then
  echo "==> virgil-docs/_trash/ -> Virgil Project/_trash/"
  run_rsync $RSYNC \
    "${COMMON_EXCLUDES[@]}" \
    /home/jordaneal/virgil-docs/_trash/ \
    "${SSH_TARGET}:${PC_BASE}/_trash/"
fi

# 4) virgil-docs/refs/ -> Virgil Project/text files/refs/
#    Reference material (Avrae Command List, etc.).
if [ -d /home/jordaneal/virgil-docs/refs ]; then
  echo "==> virgil-docs/refs/ -> Virgil Project/text files/refs/"
  run_rsync $RSYNC \
    "${COMMON_EXCLUDES[@]}" \
    /home/jordaneal/virgil-docs/refs/ \
    "${SSH_TARGET}:${PC_BASE}/text files/refs/"
fi

echo
if $RSYNC_OK; then
  echo "==> Backup complete."
else
  echo "==> Backup completed WITH ERRORS — some files may not have transferred. Check messages above." >&2
  exit 1
fi
