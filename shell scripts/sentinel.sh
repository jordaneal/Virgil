#!/bin/bash
# Virgil Sentinel - Hardened System Health Monitor
# Runs every 30 min, alerts via Telegram only on failures
# Hardened: validates metric results, degrades gracefully, flags unknowns

source /home/jordaneal/scripts/.env 2>/dev/null || true

ALERT_FILE="/tmp/sentinel_last_alert.txt"
LOG_FILE="/tmp/sentinel.log"
PROBLEMS=""
WARNINGS=""

# ─────────────────────────────────────────────────────────
# Safe logging - guards against disk/permission failures
# ─────────────────────────────────────────────────────────
sentinel_log() {
    local msg="$(date): $1"
    echo "$msg" >> "$LOG_FILE" 2>/dev/null || true
    echo "$msg"
}

# ─────────────────────────────────────────────────────────
# 1. Disk space
# ─────────────────────────────────────────────────────────
{
    DISK_USAGE=$(df / --output=pcent 2>/dev/null | tail -1 | tr -d ' %')
    if [[ "$DISK_USAGE" =~ ^[0-9]+$ ]]; then
        if [ "$DISK_USAGE" -gt 85 ]; then
            PROBLEMS="${PROBLEMS}🔴 Disk usage at ${DISK_USAGE}%\n"
        fi
    else
        WARNINGS="${WARNINGS}⚠️ Disk usage check returned invalid value: '${DISK_USAGE}'\n"
    fi
} || WARNINGS="${WARNINGS}⚠️ Disk usage check failed\n"

# ─────────────────────────────────────────────────────────
# 2. Ollama service
# ─────────────────────────────────────────────────────────
{
    if ! systemctl is-active --quiet ollama 2>/dev/null; then
        PROBLEMS="${PROBLEMS}🔴 Ollama is not running\n"
    else
        # Validate Ollama actually responds - running doesn't mean healthy
        OLLAMA_RESP=$(curl -s --max-time 5 http://localhost:11434/api/tags 2>/dev/null)
        if [ -z "$OLLAMA_RESP" ]; then
            PROBLEMS="${PROBLEMS}🔴 Ollama running but not responding to API\n"
        fi
    fi
} || WARNINGS="${WARNINGS}⚠️ Ollama check failed unexpectedly\n"

# ─────────────────────────────────────────────────────────
# 3. Virgil bot service
# ─────────────────────────────────────────────────────────
{
    if ! XDG_RUNTIME_DIR=/run/user/$(id -u) systemctl --user is-active --quiet virgil-bot 2>/dev/null; then
        PROBLEMS="${PROBLEMS}🔴 Virgil bot is not running\n"
    fi
} || WARNINGS="${WARNINGS}⚠️ Virgil bot check failed unexpectedly\n"

# ─────────────────────────────────────────────────────────
# 3b. Virgil Discord bot service
# ─────────────────────────────────────────────────────────
{
    if ! XDG_RUNTIME_DIR=/run/user/$(id -u) systemctl --user is-active --quiet virgil-discord 2>/dev/null; then
        PROBLEMS="${PROBLEMS}🔴 Virgil Discord bot is not running\n"
    fi
} || WARNINGS="${WARNINGS}⚠️ Virgil Discord bot check failed unexpectedly\n"

# ─────────────────────────────────────────────────────────
# 4. Morning digest ran today (only check after 8 AM)
# ─────────────────────────────────────────────────────────
{
    HOUR=$(date +%H)
    if [ "$HOUR" -ge 8 ]; then
        TODAY=$(date +%Y-%m-%d)
        DIGEST_LOG="/mnt/virgil_storage/digest/morning_digest.log"
        if [ ! -f "$DIGEST_LOG" ]; then
            WARNINGS="${WARNINGS}⚠️ Morning digest log missing\n"
        elif ! grep -q "$TODAY" "$DIGEST_LOG" 2>/dev/null; then
            PROBLEMS="${PROBLEMS}🟠 Morning digest did not run today\n"
        fi
    fi
} || WARNINGS="${WARNINGS}⚠️ Morning digest check failed\n"

# ─────────────────────────────────────────────────────────
# 5. Calendar cache freshness and validity
# ─────────────────────────────────────────────────────────
{
    CACHE_FILE="/mnt/virgil_storage/digest/calendar_all.txt"
    if [ ! -f "$CACHE_FILE" ]; then
        PROBLEMS="${PROBLEMS}🔴 Calendar cache file missing\n"
    else
        # Validate age
        CACHE_MTIME=$(stat -c %Y "$CACHE_FILE" 2>/dev/null)
        NOW=$(date +%s)
        if [[ "$CACHE_MTIME" =~ ^[0-9]+$ ]] && [[ "$NOW" =~ ^[0-9]+$ ]]; then
            CACHE_AGE=$(( (NOW - CACHE_MTIME) / 3600 ))
            if [ "$CACHE_AGE" -gt 2 ]; then
                WARNINGS="${WARNINGS}🟠 Calendar cache is ${CACHE_AGE} hours old\n"
            fi
        else
            WARNINGS="${WARNINGS}⚠️ Could not determine calendar cache age\n"
        fi

        # Validate content - not just auth errors but also empty/corrupt
        if grep -q "KeyUnwrap\|integrity check failed\|no TTY" "$CACHE_FILE" 2>/dev/null; then
            PROBLEMS="${PROBLEMS}🔴 Calendar cache contains auth errors\n"
        fi

        LINE_COUNT=$(wc -l < "$CACHE_FILE" 2>/dev/null)
        if [[ "$LINE_COUNT" =~ ^[0-9]+$ ]] && [ "$LINE_COUNT" -lt 2 ]; then
            WARNINGS="${WARNINGS}⚠️ Calendar cache appears empty (${LINE_COUNT} lines)\n"
        fi
    fi
} || WARNINGS="${WARNINGS}⚠️ Calendar cache check failed\n"

# ─────────────────────────────────────────────────────────
# 6. API keys present
# ─────────────────────────────────────────────────────────
{
    [ -z "$OPENWEATHER_API_KEY" ] && PROBLEMS="${PROBLEMS}🔴 OpenWeather API key not set\n"
    [ -z "$NEWS_API_KEY" ]        && PROBLEMS="${PROBLEMS}🔴 News API key not set\n"
    [ -z "$TELEGRAM_BOT_TOKEN" ]  && PROBLEMS="${PROBLEMS}🔴 Telegram bot token not set\n"
    [ -z "$GROQ_API_KEY" ]        && WARNINGS="${WARNINGS}⚠️ Groq API key not set\n"
    [ -z "$GEMINI_API_KEY" ]      && WARNINGS="${WARNINGS}⚠️ Gemini API key not set\n"
}

# ─────────────────────────────────────────────────────────
# 7. GPU temperature - hardened with explicit validation
# ─────────────────────────────────────────────────────────
if command -v nvidia-smi &>/dev/null; then
    {
        GPU_TEMP=$(nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader,nounits 2>/dev/null)
        GPU_EXIT=$?

        if [ $GPU_EXIT -ne 0 ]; then
            WARNINGS="${WARNINGS}⚠️ nvidia-smi exited with error (${GPU_EXIT})\n"
        elif [ -z "$GPU_TEMP" ]; then
            WARNINGS="${WARNINGS}⚠️ GPU temperature returned empty - treating as UNKNOWN\n"
        elif ! [[ "$GPU_TEMP" =~ ^[0-9]+$ ]]; then
            # Not a valid integer - could be "N/A", "[Not Supported]", etc.
            WARNINGS="${WARNINGS}⚠️ GPU temperature invalid value: '${GPU_TEMP}' - treating as UNKNOWN\n"
        elif [ "$GPU_TEMP" -eq 0 ]; then
            # 0°C is physically implausible in a running system - likely a read failure
            WARNINGS="${WARNINGS}⚠️ GPU temperature reads 0°C - likely sensor failure, treating as UNKNOWN\n"
        elif [ "$GPU_TEMP" -gt 85 ]; then
            PROBLEMS="${PROBLEMS}🔴 GPU temperature critical: ${GPU_TEMP}°C\n"
        elif [ "$GPU_TEMP" -gt 75 ]; then
            WARNINGS="${WARNINGS}🟠 GPU temperature elevated: ${GPU_TEMP}°C\n"
        fi

        # Also validate GPU utilization isn't reporting impossibly
        GPU_UTIL=$(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits 2>/dev/null)
        if [ -n "$GPU_UTIL" ] && [[ "$GPU_UTIL" =~ ^[0-9]+$ ]]; then
            if [ "$GPU_UTIL" -gt 100 ]; then
                WARNINGS="${WARNINGS}⚠️ GPU utilization reports ${GPU_UTIL}% - invalid reading\n"
            fi
        fi
    } || WARNINGS="${WARNINGS}⚠️ GPU check failed unexpectedly - skipping\n"
fi

# ─────────────────────────────────────────────────────────
# 8. Virgil bot log activity check
# ─────────────────────────────────────────────────────────
{
    VIRGIL_LOG="/mnt/virgil_storage/digest/virgil_bot.log"
    if [ -f "$VIRGIL_LOG" ]; then
        LOG_MTIME=$(stat -c %Y "$VIRGIL_LOG" 2>/dev/null)
        NOW=$(date +%s)
        if [[ "$LOG_MTIME" =~ ^[0-9]+$ ]]; then
            LOG_AGE=$(( (NOW - LOG_MTIME) / 3600 ))
            # Only warn if log is stale AND we're past noon (so not just early morning idle)
            HOUR=$(date +%H)
            if [ "$LOG_AGE" -gt 6 ] && [ "$HOUR" -ge 12 ]; then
                WARNINGS="${WARNINGS}🟠 Virgil bot log has had no activity for ${LOG_AGE} hours\n"
            fi
        fi
    fi
} || true

# ─────────────────────────────────────────────────────────
# Alert logic - send if problems exist, throttle to 1hr
# ─────────────────────────────────────────────────────────
FULL_MESSAGE=""
[ -n "$PROBLEMS" ] && FULL_MESSAGE="${PROBLEMS}"
[ -n "$WARNINGS" ] && FULL_MESSAGE="${FULL_MESSAGE}${WARNINGS}"

if [ -n "$PROBLEMS" ]; then
    SHOULD_ALERT=true

    if [ -f "$ALERT_FILE" ]; then
        LAST_ALERT=$(cat "$ALERT_FILE" 2>/dev/null)
        CURRENT_TIME=$(date +%s)
        if [[ "$LAST_ALERT" =~ ^[0-9]+$ ]]; then
            TIME_DIFF=$(( CURRENT_TIME - LAST_ALERT ))
            if [ "$TIME_DIFF" -lt 3600 ]; then
                SHOULD_ALERT=false
            fi
        fi
    fi

    if [ "$SHOULD_ALERT" = true ]; then
        ALERT_BODY="🚨 <b>Virgil Sentinel Alert</b>\n\n${FULL_MESSAGE}\n<i>$(date '+%I:%M %p %Z')</i>"
        curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            -d chat_id="${TELEGRAM_CHAT_ID}" \
            -d text="$(echo -e "$ALERT_BODY")" \
            -d parse_mode="HTML" > /dev/null 2>&1
        date +%s > "$ALERT_FILE"
        sentinel_log "ALERT SENT - ${PROBLEMS}"
    else
        sentinel_log "Problems exist but throttled - ${PROBLEMS}"
    fi
elif [ -n "$WARNINGS" ]; then
    # Warnings only - log but don't alert
    sentinel_log "Warnings only: ${WARNINGS}"
else
    sentinel_log "All systems healthy"
fi
