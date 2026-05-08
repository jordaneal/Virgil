#!/bin/bash
# Avrae pivot cleanup. Run this on the server AFTER the new files are in place
# and you've confirmed the Discord bot still starts. Conservative: archives
# rather than deletes, leaves SQLite tables alone.
#
# Rollback: every archive step has a one-liner above it — paste it in if
# something goes sideways.

set -e

ARCHIVE_DIR="/mnt/virgil_storage/archive/avrae_pivot_$(date +%Y%m%d)"
SCRIPTS_DIR="/home/jordaneal/scripts"

mkdir -p "$ARCHIVE_DIR"
echo "Archive: $ARCHIVE_DIR"
echo

# 1. Stop and disable the Telegram DnD bot service ---------------------
# Rollback: systemctl --user enable virgil-dnd && systemctl --user start virgil-dnd
if systemctl --user is-enabled virgil-dnd 2>/dev/null | grep -q enabled; then
    echo "[1/4] Stopping + disabling virgil-dnd service..."
    systemctl --user stop virgil-dnd || true
    systemctl --user disable virgil-dnd || true
else
    echo "[1/4] virgil-dnd already stopped or never installed — skipping."
fi

# Move the unit file out of the way (don't delete — easy revert)
USER_UNITS="$HOME/.config/systemd/user"
if [ -f "$USER_UNITS/virgil-dnd.service" ]; then
    mv "$USER_UNITS/virgil-dnd.service" "$ARCHIVE_DIR/virgil-dnd.service"
    echo "       moved $USER_UNITS/virgil-dnd.service → $ARCHIVE_DIR"
fi

systemctl --user daemon-reload || true
echo

# 2. Archive obsolete scripts ------------------------------------------
# Rollback: cp $ARCHIVE_DIR/dnd_bot.py $SCRIPTS_DIR/
echo "[2/4] Archiving obsolete scripts..."
for f in dnd_bot.py dnd_import.py; do
    if [ -f "$SCRIPTS_DIR/$f" ]; then
        mv "$SCRIPTS_DIR/$f" "$ARCHIVE_DIR/$f"
        echo "       $f → $ARCHIVE_DIR"
    fi
done
echo

# 3. Verify new files are in place -------------------------------------
echo "[3/4] Verifying new files..."
ALL_OK=true
for f in dnd_engine.py avrae_listener.py discord_dnd_bot.py; do
    if [ -f "$SCRIPTS_DIR/$f" ]; then
        # Syntax check
        if python3 -c "import ast; ast.parse(open('$SCRIPTS_DIR/$f').read())" 2>/dev/null; then
            echo "       OK   $f"
        else
            echo "       FAIL $f (syntax error)"
            ALL_OK=false
        fi
    else
        echo "       MISSING $f"
        ALL_OK=false
    fi
done

if [ "$ALL_OK" = false ]; then
    echo
    echo "Aborting before restart — fix the missing/broken files first."
    exit 1
fi
echo

# 4. Restart the Discord bot to pick up the new code -------------------
echo "[4/4] Restarting virgil-discord..."
systemctl --user restart virgil-discord
sleep 2
if systemctl --user is-active --quiet virgil-discord; then
    echo "       virgil-discord is active."
else
    echo "       virgil-discord failed to start. Check:"
    echo "         journalctl --user -u virgil-discord -n 50 --no-pager"
    exit 1
fi

echo
echo "Done."
echo
echo "What changed:"
echo "  - virgil-dnd Telegram bot is stopped, disabled, unit file archived"
echo "  - dnd_bot.py, dnd_import.py archived to $ARCHIVE_DIR"
echo "  - dnd_engine.py + avrae_listener.py + new discord_dnd_bot.py are live"
echo "  - dnd_srd SQLite table left in place (cold storage, no harm)"
echo "  - dnd_knowledge_import.py left in place (still useful for future imports)"
echo
echo "Next: in Discord, run /setup, then invite Avrae from https://avrae.io,"
echo "then /newcampaign, then players /bindchar, then DM /play."
