#!/bin/bash
# Comprehensive data cache for Virgil
# Runs every hour to keep fresh data available

CACHE_DIR="/mnt/virgil_storage/digest"
mkdir -p "$CACHE_DIR"

echo "=== Data Cache Update: $(date) ===" >> /tmp/data_cache.log

# Calculate date range
START_DATE=$(date -d 'yesterday' +%Y-%m-%d)
END_DATE=$(date -d '+30 days' +%Y-%m-%d)

# Set keyring password to empty for non-interactive access
export GOG_KEYRING_PASSWORD=""

# 1. All Calendars - 30 days forward
echo "Fetching all calendars..." >> /tmp/data_cache.log
/home/linuxbrew/.linuxbrew/bin/gog --account jordaneal@gmail.com cal list \
  --all \
  --from "$START_DATE" \
  --to "$END_DATE" \
  -p > "$CACHE_DIR/calendar_all.txt" 2>&1

# 2. Emails - Last 7 days
echo "Fetching recent emails..." >> /tmp/data_cache.log
/home/linuxbrew/.linuxbrew/bin/gog --account jordaneal@gmail.com gmail search "newer_than:7d -category:promotions -category:social" \
  --max 100 \
  -p > "$CACHE_DIR/emails_recent.txt" 2>&1

echo "Cache update complete." >> /tmp/data_cache.log
