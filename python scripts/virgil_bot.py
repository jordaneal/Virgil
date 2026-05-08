#!/usr/bin/env python3
"""
Virgil Bot - Single entry point for all Telegram interaction.
Replaces OpenClaw. Deterministic routing, Python tools, SQLite memory.
"""

import os
import re
import sys
import time
import json
import sqlite3
import datetime
import subprocess
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv('/home/jordaneal/scripts/.env')

sys.path.insert(0, '/home/jordaneal/scripts')
from cloud_router import route

BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ALLOWED_CHAT_IDS = {str(os.getenv('TELEGRAM_CHAT_ID'))}

DB_PATH = Path('/mnt/virgil_storage/virgil.db')
LOG_PATH = Path('/mnt/virgil_storage/digest/virgil_bot.log')

GOG = '/home/linuxbrew/.linuxbrew/bin/gog'
PERSONAL_CAL = 'jordaneal@gmail.com'
FAMILY_CAL = 'family17072034232008398967@group.calendar.google.com'

CONTEXT_WINDOW = 10

MONTHS = {
    'january': 1, 'jan': 1, 'february': 2, 'feb': 2,
    'march': 3, 'mar': 3, 'april': 4, 'apr': 4,
    'may': 5, 'june': 6, 'jun': 6, 'july': 7, 'jul': 7,
    'august': 8, 'aug': 8, 'september': 9, 'sep': 9, 'sept': 9,
    'october': 10, 'oct': 10, 'november': 11, 'nov': 11,
    'december': 12, 'dec': 12
}

DAYS = {
    'monday': 0, 'mon': 0, 'tuesday': 1, 'tue': 1, 'tues': 1,
    'wednesday': 2, 'wed': 2, 'thursday': 3, 'thu': 3, 'thur': 3,
    'friday': 4, 'fri': 4, 'saturday': 5, 'sat': 5, 'sunday': 6, 'sun': 6
}

SYSTEM_PROMPT = """You are Virgil, an AI assistant for Jordan Neal in Chehalis WA running on his local server.

Rules:
- Be direct and concise. No filler words, no sycophancy.
- Never tell Jordan to do something himself if you can just answer it.
- Never deflect. Never say "I can't" unless it is literally impossible.
- Do not be a smart ass. Do not be lazy.
- If you don't know something, say so plainly and try anyway.
- Calendar actions use /cal commands. If Jordan asks about calendar and you cannot handle it in chat, tell him what info is missing (e.g. "need a new time to move that"). Never say "say X" or "type X" - just tell him what is missing or needed.

About Jordan: golfer, dad, bowls Wednesdays, PSMF diet. Favorite shows: Demon Slayer, JJK, Solo Leveling, SAO, Naruto, Black Clover, Vinland Saga, FMAB, HxH, Chainsaw Man."""

# ─────────────────────────────────────────────────────────
# Pending state store (in-memory cache, persisted in DB)
# ─────────────────────────────────────────────────────────
PENDING = {}  # chat_id -> action dict
PENDING_TTL = 20 * 60  # 20 minutes in seconds
START_TIME = None  # set in main()

# ─────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────

def log(msg):
    timestamp = datetime.datetime.now().isoformat(timespec='seconds')
    line = f"[{timestamp}] {msg}"
    print(line, flush=True)
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_PATH, 'a') as f:
            f.write(line + '\n')
    except Exception:
        pass

def event_log(event_type, chat_id, **fields):
    """Write a structured JSON log line for operational observability."""
    record = {
        "ts": datetime.datetime.now().isoformat(timespec='seconds'),
        "type": event_type,
        "chat": str(chat_id) if chat_id else None
    }
    record.update(fields)
    line = json.dumps(record)
    print(line, flush=True)
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_PATH, 'a') as f:
            f.write(line + '\n')
    except Exception:
        pass

# ─────────────────────────────────────────────────────────
# SQLite memory (per chat_id)
# ─────────────────────────────────────────────────────────

def db_init():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            route TEXT,
            provider TEXT,
            ts TEXT NOT NULL
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS facts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT NOT NULL UNIQUE,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS pending (
            chat_id TEXT PRIMARY KEY,
            data TEXT NOT NULL,
            ts TEXT NOT NULL
        )
    ''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_chat_ts ON messages(chat_id, ts)')
    conn.commit()
    conn.close()

    # Load any existing pending actions into memory on startup
    load_pending()
    cleanup_pending()

def db_log(chat_id, role, content, route_type=None, provider=None):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            'INSERT INTO messages (chat_id, role, content, route, provider, ts) VALUES (?, ?, ?, ?, ?, ?)',
            (str(chat_id), role, content, route_type, provider,
             datetime.datetime.now().isoformat(timespec='seconds'))
        )
        conn.commit()
        conn.close()
    except Exception as e:
        log(f"db_log error: {e}")


def db_history(chat_id, n=CONTEXT_WINDOW):
    try:
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute(
            "SELECT role, content FROM messages "
            "WHERE chat_id = ? AND role IN ('user','assistant') "
            "ORDER BY id DESC LIMIT ?",
            (str(chat_id), n * 2)
        ).fetchall()
        conn.close()
        return [{'role': r, 'content': c} for r, c in reversed(rows)]
    except Exception as e:
        log(f"db_history error: {e}")
        return []


def db_save_fact(key, value):
    """Save or update a fact about Jordan."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            '''INSERT INTO facts (key, value, updated_at) VALUES (?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at''',
            (key.lower().strip(), value.strip(),
             datetime.datetime.now().isoformat(timespec='seconds'))
        )
        conn.commit()
        conn.close()
    except Exception as e:
        log(f"db_save_fact error: {e}")


def db_get_facts():
    """Return all facts as a formatted string for injection into system prompt."""
    try:
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute(
            'SELECT key, value FROM facts ORDER BY updated_at DESC'
        ).fetchall()
        conn.close()
        if not rows:
            return ""
        lines = [f"- {r[0]}: {r[1]}" for r in rows]
        return "Known facts about Jordan:\n" + "\n".join(lines)
    except Exception as e:
        log(f"db_get_facts error: {e}")
        return ""

# ─────────────────────────────────────────────────────────
# Pending persistence helpers
# ─────────────────────────────────────────────────────────

def is_pending_expired(ts):
    """Return True if the epoch timestamp is older than PENDING_TTL seconds."""
    return time.time() - ts > PENDING_TTL

def save_pending(chat_id, action):
    """Save pending action to DB (authoritative) and update memory cache.
    Injects `_ts` into the in‑memory action for TTL checks, but
    strips it before writing to DB – the `ts` column is the sole authority."""
    now = time.time()
    # Create a copy so we don't mutate the caller's dict
    action_copy = dict(action)
    action_copy['_ts'] = now
    PENDING[chat_id] = action_copy

    # DB version: the original action, untouched
    db_action = dict(action)

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "INSERT OR REPLACE INTO pending (chat_id, data, ts) VALUES (?, ?, ?)",
            (chat_id, json.dumps(db_action), str(now))
        )
        conn.commit()
        conn.close()
    except Exception as e:
        log(f"save_pending error: {e}")

def get_pending(chat_id):
    """Return the pending action dict if valid and non‑expired.
    Cache‑first, then DB. Never deletes rows. Stale cache entries are purged."""
    cached = PENDING.get(chat_id)
    if cached is not None:
        if not is_pending_expired(cached.get('_ts', 0)):
            return cached
        # Stale cache – purge it and fall through to DB
        PENDING.pop(chat_id, None)

    try:
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute(
            "SELECT data, ts FROM pending WHERE chat_id = ?", (chat_id,)
        ).fetchone()
        conn.close()
        if row:
            ts = float(row[1]) if row[1] else 0
            if is_pending_expired(ts):
                return None
            action = json.loads(row[0])
            action['_ts'] = ts               # keep cache in sync
            PENDING[chat_id] = action
            return action
    except Exception as e:
        log(f"get_pending error: {e}")
    return None

def load_pending():
    """Populate in-memory cache with all non-expired pending actions from DB."""
    try:
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute("SELECT chat_id, data, ts FROM pending").fetchall()
        conn.close()
        for chat_id, data, ts_str in rows:
            try:
                ts = float(ts_str) if ts_str else 0
                if is_pending_expired(ts):
                    continue   # skip expired; will be removed by cleanup
                action = json.loads(data)
                action['_ts'] = ts
                PENDING[chat_id] = action
                log(f"loaded pending for {chat_id}")
            except Exception as e:
                log(f"corrupt pending row for {chat_id}: {e}")
    except Exception as e:
        log(f"load_pending error: {e}")

def delete_pending(chat_id):
    """Delete pending action from DB and remove from cache (if present)."""
    PENDING.pop(chat_id, None)
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("DELETE FROM pending WHERE chat_id = ?", (chat_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        log(f"delete_pending error: {e}")

def cleanup_pending():
    """Delete all expired pending rows from the DB. Called once at startup."""
    try:
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute("SELECT chat_id, ts FROM pending").fetchall()
        expired = []
        for chat_id, ts_str in rows:
            ts = float(ts_str) if ts_str else 0
            if is_pending_expired(ts):
                expired.append(chat_id)
        for chat_id in expired:
            conn.execute("DELETE FROM pending WHERE chat_id = ?", (chat_id,))
            # Also purge from cache just in case
            PENDING.pop(chat_id, None)
            log(f"cleanup_pending: removed expired for {chat_id}")
        conn.commit()
        conn.close()
    except Exception as e:
        log(f"cleanup_pending error: {e}")

# ─────────────────────────────────────────────────────────
# Fact extraction (unchanged)
# ─────────────────────────────────────────────────────────

FACT_EXTRACT_SYSTEM = """You are a fact extractor. Given a message from Jordan, extract any personal facts worth remembering long-term.

Return ONLY a JSON object in this exact format:
{"facts": [{"key": "short label", "value": "what to remember"}]}

Return {"facts": []} if there is nothing worth saving.

Guidelines:
- Extract: preferences, habits, relationships, places, health, goals, interests, purchases, life events
- Skip: questions, commands, one-off tasks, anything already obvious from context
- Keys should be short and reusable (e.g. "favorite restaurant", "kids names", "current show")
- Values should be concise but complete
- Do not extract: passwords, SSNs, financial account numbers, addresses

Examples:
  "just started watching Shogun" -> {"facts": [{"key": "currently watching", "value": "Shogun"}]}
  "my daughter is named Emma" -> {"facts": [{"key": "daughter name", "value": "Emma"}]}
  "what time is it" -> {"facts": []}
  "add dentist tuesday" -> {"facts": []}"""


def _thread_log(msg):
    """Direct file log for use inside daemon threads."""
    try:
        timestamp = datetime.datetime.now().isoformat(timespec='seconds')
        line = f"[{timestamp}] {msg}\n"
        with open(LOG_PATH, 'a') as f:
            f.write(line)
    except Exception:
        pass


def _extract_facts_async(text, chat_id):
    """Run LLM fact extraction in background thread. Saves any facts found."""
    try:
        from cloud_router import PROVIDERS, call_provider as _call_provider
        provider = next(p for p in PROVIDERS if p["name"] == "cerebras")
        msgs = [{"role": "user", "content": text}]
        success, response, code = _call_provider(
            provider, msgs, system_prompt=FACT_EXTRACT_SYSTEM, max_tokens=300
        )
        if not success:
            _thread_log(f"_extract_facts_async: cerebras failed ({code})")
            return
        clean = response.strip()
        clean = re.sub(r"^```[\w]*\n?", "", clean, flags=re.MULTILINE)
        clean = re.sub(r"```$", "", clean.strip(), flags=re.MULTILINE).strip()
        data = json.loads(clean)
        facts = data.get("facts", [])
        _thread_log(f"_extract_facts_async: got {len(facts)} facts")
        for fact in facts:
            key = fact.get("key", "").strip()
            value = fact.get("value", "").strip()
            if key and value:
                db_save_fact(key, value)
                _thread_log(f"fact saved (llm): {key} = {value}")
    except Exception as e:
        _thread_log(f"_extract_facts_async error: {e}")


def extract_facts_from_message(text, chat_id=None):
    """
    LLM-based fact extraction. Runs in background thread — no latency impact.
    Short messages and sensitive content are skipped.
    """
    if len(text.strip()) < 20:
        return
    t = text.lower()
    if any(w in t for w in ["password", "social security", "credit card", "ssn"]):
        return
    import threading
    log(f"extract_facts: starting thread for: {text[:50]}")
    threading.Thread(target=_extract_facts_async, args=(text, chat_id), daemon=True).start()


# ─────────────────────────────────────────────────────────
# Telegram I/O
# ─────────────────────────────────────────────────────────

def tg_send(chat_id, text):
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML',
                  'disable_web_page_preview': True},
            timeout=10
        )
    except Exception as e:
        log(f"tg_send error: {e}")


def tg_typing(chat_id):
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendChatAction",
            json={'chat_id': chat_id, 'action': 'typing'},
            timeout=5
        )
    except Exception:
        pass


def tg_get_updates(offset=None):
    params = {'timeout': 30}
    if offset is not None:
        params['offset'] = offset
    try:
        r = requests.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates",
            params=params, timeout=35
        )
        return r.json()
    except Exception as e:
        log(f"tg_get_updates error: {e}")
        return {'result': []}


# ─────────────────────────────────────────────────────────
# Date/time parsing (unchanged)
# ─────────────────────────────────────────────────────────

def parse_time(text):
    t = text.lower()
    m = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)', t)
    if m:
        h = int(m.group(1))
        mn = int(m.group(2)) if m.group(2) else 0
        period = m.group(3)
        if period == 'pm' and h != 12:
            h += 12
        elif period == 'am' and h == 12:
            h = 0
        return h, mn
    m = re.search(r'\b(\d{2}):(\d{2})\b', t)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None, None


def parse_date(text):
    t = text.lower()
    today = datetime.date.today()
    if 'today' in t:
        return today
    if 'tomorrow' in t:
        return today + datetime.timedelta(days=1)
    for day_name, day_num in DAYS.items():
        if re.search(r'\b' + day_name + r'\b', t):
            delta = day_num - today.weekday()
            if delta <= 0 or 'next' in t:
                delta += 7
            return today + datetime.timedelta(days=delta)
    for month_name, month_num in MONTHS.items():
        if re.search(r'\b' + month_name + r'\b', t):
            m = re.search(r'(\d{1,2})', t)
            if m:
                day = int(m.group(1))
                year = today.year
                try:
                    d = datetime.date(year, month_num, day)
                    if d < today:
                        d = datetime.date(year + 1, month_num, day)
                    return d
                except ValueError:
                    pass
    return None


def is_allday(text):
    t = text.lower()
    return any(w in t for w in ['all day', 'all-day', 'allday', 'whole day', 'full day'])


def parse_end_date(text):
    t = text.lower()
    for sep in [' to ', ' through ', ' - ', '-']:
        if sep in t:
            parts = t.split(sep, 1)
            if len(parts) == 2:
                d = parse_date(parts[1])
                if d:
                    return d
    return None


def clean_title(text):
    title = text
    for w in ['add ', 'schedule ', 'create ', 'delete ', 'remove ', 'cancel ',
              'edit ', 'move ', 'reschedule ', 'change ']:
        if title.lower().startswith(w):
            title = title[len(w):]
            break
    title = re.sub(r'\b(next\s+)?(monday|tuesday|wednesday|thursday|friday|saturday|sunday|mon|tue|tues|wed|thu|thur|fri|sat|sun)\b', '', title, flags=re.I)
    title = re.sub(r'\b(today|tomorrow)\b', '', title, flags=re.I)
    title = re.sub(r'\b(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)\b', '', title, flags=re.I)
    title = re.sub(r'\d{1,2}(:\d{2})?\s*(am|pm)', '', title, flags=re.I)
    title = re.sub(r'\d{1,2}:\d{2}', '', title)
    title = re.sub(r'\b(at|on|to|the|family|personal|calendar|from)\b', '', title, flags=re.I)
    title = re.sub(r'\b\d+\b', '', title)
    title = re.sub(r'@\S+', '', title)
    title = re.sub(r'\b(all day|all-day|allday|whole day|full day)\b', '', title, flags=re.I)
    title = re.sub(r'\s+', ' ', title).strip()
    return title


def pacific_offset():
    try:
        import pytz
        tz = pytz.timezone('America/Los_Angeles')
        off = datetime.datetime.now(tz).strftime('%z')
        return f"{off[:3]}:{off[3:]}"
    except Exception:
        return "-07:00"


def fmt_time(h, m):
    period = 'AM' if h < 12 else 'PM'
    hh = h if h <= 12 else h - 12
    if hh == 0:
        hh = 12
    return f"{hh}:{m:02d} {period}"


# ─────────────────────────────────────────────────────────
# Calendar tools (unchanged gog calls)
# ─────────────────────────────────────────────────────────

def gog_run(args):
    env = os.environ.copy()
    env['GOG_KEYRING_PASSWORD'] = ''
    try:
        r = subprocess.run(
            [GOG] + args + ['--account', PERSONAL_CAL],
            capture_output=True, text=True, env=env, timeout=30
        )
        output = r.stdout + r.stderr
        if r.returncode != 0:
            log(f"gog FAIL: args={args} rc={r.returncode}")
            log(f"gog stderr: {r.stderr}")
            log(f"gog stdout: {r.stdout}")
        return r.returncode == 0, output
    except Exception as e:
        log(f"gog EXCEPTION: {e} args={args}")
        return False, str(e)


def cal_list(date):
    try:
        import pytz
        pacific = pytz.timezone('America/Los_Angeles')
        start_dt = pacific.localize(datetime.datetime(date.year, date.month, date.day, 0, 0, 0))
        end_dt = pacific.localize(datetime.datetime(date.year, date.month, date.day, 23, 59, 59))
        from_str = start_dt.isoformat()
        to_str = end_dt.isoformat()
    except Exception:
        from_str = str(date)
        to_str = str(date + datetime.timedelta(days=1))
    ok, out = gog_run(['cal', 'list', '--all', '--from', from_str, '--to', to_str, '-p'])
    events = []
    if not ok:
        return events
    for line in out.strip().split('\n'):
        if line.startswith('CALENDAR') or not line.strip():
            continue
        parts = line.split('\t')
        if len(parts) >= 5:
            time_str = ""
            try:
                import pytz
                pacific = pytz.timezone('America/Los_Angeles')
                start_raw = parts[2].strip()
                if 'T' in start_raw:
                    start_dt = datetime.datetime.fromisoformat(start_raw.replace('Z', '+00:00')).astimezone(pacific)
                    h, m = start_dt.hour, start_dt.minute
                    period = 'AM' if h < 12 else 'PM'
                    h = h if h <= 12 else h - 12
                    h = h or 12
                    time_str = f"{h}:{m:02d} {period}"
                else:
                    time_str = "All day"
            except Exception:
                time_str = ""
            events.append({
                'cal_id': parts[0].strip(),
                'event_id': parts[1].strip(),
                'summary': parts[4].strip(),
                'time': time_str
            })
    return events


def cal_create(title, date, hour, minute, calendar_id):
    off = pacific_offset()
    start = f"{date}T{hour:02d}:{minute:02d}:00{off}"
    end_dt = datetime.datetime(date.year, date.month, date.day, hour, minute) + datetime.timedelta(hours=1)
    end = f"{end_dt.strftime('%Y-%m-%d')}T{end_dt.strftime('%H:%M')}:00{off}"
    return gog_run([
        'cal', 'create', calendar_id,
        '--summary', title,
        '--from', start, '--to', end,
        '--force', '--no-input'
    ])


def cal_create_allday(title, start_date, end_date, calendar_id):
    exclusive_end = (end_date + datetime.timedelta(days=1)) if end_date else (start_date + datetime.timedelta(days=1))
    return gog_run([
        'cal', 'create', calendar_id,
        '--summary', title,
        '--from', str(start_date),
        '--to', str(exclusive_end),
        '--all-day', '--force', '--no-input'
    ])


def cal_delete(event_id, calendar_id):
    return gog_run(['cal', 'delete', calendar_id, event_id, '--force', '--no-input'])


# ─────────────────────────────────────────────────────────
# Verification helpers
# ─────────────────────────────────────────────────────────

def verify_exists(title, date, cal_id):
    """Check that an event with this title exists on the given date/cal."""
    events = cal_list(date)
    for e in events:
        if e['summary'].strip().lower() == title.strip().lower() and e['cal_id'] == cal_id:
            return True
    return False


def verify_gone(event_id, date):
    """Check that an event_id is absent on the given date."""
    events = cal_list(date)
    for e in events:
        if e['event_id'] == event_id:
            return False
    return True


# ─────────────────────────────────────────────────────────
# Non-blocking calendar handlers
# ─────────────────────────────────────────────────────────

def handle_add(chat_id, text):
    date = parse_date(text)
    hour, minute = parse_time(text)
    title = clean_title(text)
    cal_id = FAMILY_CAL if 'family' in text.lower() else PERSONAL_CAL
    allday = is_allday(text)
    end_date = parse_end_date(text)

    if not date:
        tg_send(chat_id, "❌ No date found. Try: 'add dentist Tuesday at 2pm'")
        return
    if hour is None and not allday:
        tg_send(chat_id, "❌ No time found. Try: 'add dentist Tuesday at 2pm' or include 'all day' for all-day events.")
        return
    if not title:
        tg_send(chat_id, "❌ No event title found.")
        return

    cal_name = "Family" if cal_id == FAMILY_CAL else "Personal"

    if allday:
        end_display = f" - {end_date.strftime('%B %d')}" if end_date else ""
        msg = (f"Adding: <b>{title}</b>\n📅 {date.strftime('%A, %B %d')}{end_display} (all day)\n"
               f"📆 {cal_name} calendar\n\nReply 'yes' to confirm.")
    else:
        msg = (f"Adding: <b>{title}</b>\n📅 {date.strftime('%A, %B %d')}\n"
               f"⏰ {fmt_time(hour, minute)}\n📆 {cal_name} calendar\n\nReply 'yes' to confirm.")

    # Store pending confirmation (persisted)
    save_pending(str(chat_id), {
        'type': 'confirm_add',
        'title': title,
        'date': str(date),
        'hour': hour,
        'minute': minute,
        'cal_id': cal_id,
        'allday': allday,
        'end_date': str(end_date) if end_date else None,
        'ts': time.time()
    })
    tg_send(chat_id, msg)


def handle_delete(chat_id, text):
    date = parse_date(text)
    hint = clean_title(text)

    if not date:
        tg_send(chat_id, "❌ No date found. Try: 'delete dentist Tuesday'")
        return

    events = cal_list(date)
    if not events:
        tg_send(chat_id, f"No events found on {date.strftime('%A, %B %d')}.")
        return

    matches = [e for e in events if hint.lower() in e['summary'].lower()] if hint else events
    if not matches:
        matches = events

    if len(matches) == 1:
        ev = matches[0]
        save_pending(str(chat_id), {
            'type': 'confirm_delete',
            'event_id': ev['event_id'],
            'cal_id': ev['cal_id'],
            'summary': ev['summary'],
            'date': str(date),
            'ts': time.time()
        })
        tg_send(chat_id, f"Delete <b>{ev['summary']}</b> on {date.strftime('%A, %B %d')}?\n\nReply 'yes' to confirm.")
    else:
        save_pending(str(chat_id), {
            'type': 'waiting_delete_select',
            'matches': matches,
            'date': str(date),
            'ts': time.time()
        })
        lines = [f"Multiple events on {date.strftime('%A, %B %d')}:"]
        for i, e in enumerate(matches, 1):
            lines.append(f"{i}. {e['summary']}")
        lines.append("\nReply with the number to select.")
        tg_send(chat_id, "\n".join(lines))


def handle_move(chat_id, text):
    date = parse_date(text)
    new_hour, new_minute = parse_time(text)
    hint = clean_title(text)

    if not date:
        tg_send(chat_id, "❌ What date is the event on?")
        return
    if new_hour is None:
        tg_send(chat_id, "❌ New time not found. Add the new time (e.g., 'move dentist Tue to 3pm').")
        return

    events = cal_list(date)
    if not events:
        tg_send(chat_id, f"No events found on {date.strftime('%A, %B %d')}.")
        return

    matches = [e for e in events if hint.lower() in e['summary'].lower()] if hint else events
    if not matches:
        matches = events

    if len(matches) == 1:
        ev = matches[0]
        save_pending(str(chat_id), {
            'type': 'confirm_move',
            'event_id': ev['event_id'],
            'cal_id': ev['cal_id'],
            'summary': ev['summary'],
            'date': str(date),
            'new_hour': new_hour,
            'new_minute': new_minute,
            'ts': time.time()
        })
        tg_send(chat_id, f"Move <b>{ev['summary']}</b> to {fmt_time(new_hour, new_minute)} on {date.strftime('%A, %B %d')}?\n\nReply 'yes' to confirm.")
    else:
        save_pending(str(chat_id), {
            'type': 'waiting_move_select',
            'matches': matches,
            'date': str(date),
            'new_hour': new_hour,
            'new_minute': new_minute,
            'ts': time.time()
        })
        lines = [f"Multiple events on {date.strftime('%A, %B %d')}:"]
        for i, e in enumerate(matches, 1):
            lines.append(f"{i}. {e['summary']}")
        lines.append("\nReply with the number to select.")
        tg_send(chat_id, "\n".join(lines))


def handle_list(chat_id, text):
    date = parse_date(text) or datetime.date.today()
    events = cal_list(date)
    if not events:
        msg = f"No events on {date.strftime('%A, %B %d')}."
    else:
        lines = [f"<b>Events on {date.strftime('%A, %B %d')}:</b>"]
        for e in events:
            time_prefix = f"{e['time']} — " if e.get('time') and e['time'] != 'All day' else ""
            all_day = " (all day)" if e.get('time') == 'All day' else ""
            lines.append(f"• {time_prefix}{e['summary']}{all_day}")
        msg = "\n".join(lines)
    tg_send(chat_id, msg)
    db_log(chat_id, 'assistant', msg, route_type='tool', provider='gog')


# ─────────────────────────────────────────────────────────
# Pending state machine
# ─────────────────────────────────────────────────────────

def handle_pending(chat_id, text, offset):
    """Process a reply to a pending calendar action. Called instead of normal classify."""
    action = get_pending(str(chat_id))
    if not action:
        return offset

    reply = text.strip().lower()

    # ── Delete select ──
    if action['type'] == 'waiting_delete_select':
        if reply.isdigit():
            idx = int(reply) - 1
            matches = action['matches']
            if 0 <= idx < len(matches):
                ev = matches[idx]
                save_pending(str(chat_id), {
                    'type': 'confirm_delete',
                    'event_id': ev['event_id'],
                    'cal_id': ev['cal_id'],
                    'summary': ev['summary'],
                    'date': action['date'],
                    'ts': time.time()
                })
                tg_send(chat_id, f"Delete <b>{ev['summary']}</b>?\n\nReply 'yes' to confirm.")
                return offset
        delete_pending(str(chat_id))
        tg_send(chat_id, "Cancelled.")
        return offset

    # ── Move select ──
    if action['type'] == 'waiting_move_select':
        if reply.isdigit():
            idx = int(reply) - 1
            matches = action['matches']
            if 0 <= idx < len(matches):
                ev = matches[idx]
                save_pending(str(chat_id), {
                    'type': 'confirm_move',
                    'event_id': ev['event_id'],
                    'cal_id': ev['cal_id'],
                    'summary': ev['summary'],
                    'date': action['date'],
                    'new_hour': action['new_hour'],
                    'new_minute': action['new_minute'],
                    'ts': time.time()
                })
                tg_send(chat_id, f"Move <b>{ev['summary']}</b> to {fmt_time(action['new_hour'], action['new_minute'])}?\n\nReply 'yes' to confirm.")
                return offset
        delete_pending(str(chat_id))
        tg_send(chat_id, "Cancelled.")
        return offset

    # Non-yes cancels
    if reply not in ('yes', 'y', 'yeah', 'yep', 'confirm', 'ok', 'sure'):
        delete_pending(str(chat_id))
        tg_send(chat_id, "Cancelled.")
        return offset

    # ── Confirm add ──
    if action['type'] == 'confirm_add':
        title = action['title']
        date = datetime.date.fromisoformat(action['date'])
        cal_id = action['cal_id']
        allday = action['allday']
        cal_name = "Family" if cal_id == FAMILY_CAL else "Personal"

        if allday:
            end_date = datetime.date.fromisoformat(action['end_date']) if action['end_date'] else None
            ok, out = cal_create_allday(title, date, end_date, cal_id)
            date_str = date.strftime("%B %d")
            if end_date:
                date_str += f" - {end_date.strftime('%B %d')}"
            if ok:
                if verify_exists(title, date, cal_id):
                    msg = f"✅ <b>{title}</b> added to {cal_name} calendar ({date_str}, all day)"
                else:
                    msg = f"⚠️ Created but couldn't verify. Check calendar for <b>{title}</b> on {date_str}."
            else:
                msg = f"❌ Failed to create event.\nError: {out[:200]}"
        else:
            hour = action['hour']
            minute = action['minute']
            ok, out = cal_create(title, date, hour, minute, cal_id)
            if ok:
                if verify_exists(title, date, cal_id):
                    msg = f"✅ <b>{title}</b> added to {cal_name} calendar on {date.strftime('%A, %B %d')} at {fmt_time(hour, minute)}"
                else:
                    msg = f"⚠️ Created but couldn't verify. Check <b>{title}</b> on {date.strftime('%A, %B %d')}."
            else:
                msg = f"❌ Failed to create event.\nError: {out[:200]}"

        delete_pending(str(chat_id))
        tg_send(chat_id, msg)
        event_log("calendar_action", chat_id, action=action['type'], outcome="success" if "✅" in msg else "unverified" if "⚠️" in msg else "fail",
                  summary=msg[:150])
        db_log(chat_id, 'assistant', msg, route_type='tool', provider='gog')
        return offset

    # ── Confirm delete ──
    if action['type'] == 'confirm_delete':
        ev_id = action['event_id']
        cal_id = action['cal_id']
        summary = action['summary']
        date = datetime.date.fromisoformat(action['date'])

        ok, out = cal_delete(ev_id, cal_id)
        if ok:
            if verify_gone(ev_id, date):
                msg = f"✅ <b>{summary}</b> deleted."
            else:
                msg = f"⚠️ Deletion command succeeded but event still shows. Check <b>{summary}</b> on {date.strftime('%A, %B %d')}."
        else:
            msg = f"❌ Failed to delete.\nError: {out[:200]}"

        delete_pending(str(chat_id))
        tg_send(chat_id, msg)
        event_log("calendar_action", chat_id, action=action['type'], outcome="success" if "✅" in msg else "unverified" if "⚠️" in msg else "fail",
                  summary=msg[:150])
        db_log(chat_id, 'assistant', msg, route_type='tool', provider='gog')
        return offset

    # ── Confirm move ──
    if action['type'] == 'confirm_move':
        ev_id = action['event_id']
        cal_id = action['cal_id']
        summary = action['summary']
        date = datetime.date.fromisoformat(action['date'])
        new_h = action['new_hour']
        new_m = action['new_minute']

        ok_del, out_del = cal_delete(ev_id, cal_id)
        if not ok_del:
            delete_pending(str(chat_id))
            tg_send(chat_id, f"❌ Failed to delete old event.\nError: {out_del[:200]}")
            return offset

        ok_add, out_add = cal_create(summary, date, new_h, new_m, cal_id)
        if ok_add:
            if verify_exists(summary, date, cal_id):
                msg = f"✅ <b>{summary}</b> moved to {fmt_time(new_h, new_m)} on {date.strftime('%A, %B %d')}"
            else:
                msg = f"⚠️ Moved but couldn't verify new event. Check <b>{summary}</b> on {date.strftime('%A, %B %d')}."
        else:
            msg = f"❌ Old event deleted but failed to recreate.\nError: {out_add[:200]}"

        delete_pending(str(chat_id))
        event_log("calendar_action", chat_id, action="move", outcome="fail", error=out_del[:200])
        tg_send(chat_id, msg)
        event_log("calendar_action", chat_id, action=action['type'], outcome="success" if "✅" in msg else "unverified" if "⚠️" in msg else "fail",
                  summary=msg[:150])
        db_log(chat_id, 'assistant', msg, route_type='tool', provider='gog')
        return offset

    # ── Confirm patch ──
    if action['type'] == 'confirm_patch':
        if text.strip().lower() in ('yes', 'y', 'yeah', 'yep', 'confirm', 'ok', 'sure'):
            delete_pending(str(chat_id))
            apply_patch(chat_id)
        else:
            delete_pending(str(chat_id))
            staging = Path(action.get('staging_path', ''))
            staging.unlink(missing_ok=True)
            tg_send(chat_id, "Patch discarded.")
        return offset

    return offset


# ─────────────────────────────────────────────────────────
# Classifier (unchanged)
# ─────────────────────────────────────────────────────────

def classify_regex(text):
    """Original regex-based classifier. Used as fallback if LLM classifier fails."""
    t = text.lower().strip()

    if t in ['/start', '/help']:
        return 'help'
    if t == '/usage':
        return 'usage'
    if t == '/reset':
        return 'reset'
    if t == '/stats':
        return 'stats'
    if t == '/memory':
        return 'memory'
    if t.startswith('/remember '):
        return 'remember'

    if t.startswith('/cal '):
        body = t[5:].strip()
        if any(body.startswith(w) for w in ['delete ', 'remove ', 'cancel ']):
            return 'cal_delete'
        if any(body.startswith(w) for w in ['move ', 'reschedule ', 'change ', 'edit ']):
            return 'cal_move'
        if any(body.startswith(w) for w in ['list', 'show', 'what']):
            return 'cal_list'
        return 'cal_add'
    if t == '/cal':
        return 'cal_list'

    if t.startswith('/run'):
        return 'run'

    if any(t.startswith(w) for w in ['delete ', 'remove ', 'cancel ']):
        if 'event' in t or parse_date(t) is not None:
            return 'cal_delete'

    if any(t.startswith(w) for w in ['edit ', 'move ', 'reschedule ', 'change ']):
        if parse_date(t) is not None and parse_time(t)[0] is not None:
            return 'cal_move'

    if any(t.startswith(w) for w in ['add ', 'schedule ', 'create ']):
        if parse_date(t) is not None:
            return 'cal_add'

    if parse_date(t) is not None and parse_time(t)[0] is not None:
        if any(w in t for w in ['add', 'schedule', 'book', 'put', 'set up', 'create', 'make', 'block']):
            return 'cal_add'

    if parse_date(t) is not None and is_allday(t):
        if any(w in t for w in ['add', 'schedule', 'book', 'put', 'create', 'make']):
            return 'cal_add'

    if any(w in t for w in ["what's on", "whats on", "list events", "show calendar",
                             "what's my", "what do i have", "what on", "show me",
                             "what's tomorrow", "whats tomorrow", "calendar for",
                             "schedule for", "what's today", "whats today"]):
        return 'cal_list'

    if t.startswith('/run'):
        return 'run'

    return 'chat'


VALID_NL_INTENTS = {'cal_add', 'cal_delete', 'cal_move', 'cal_list', 'chat', 'search'}

CLASSIFY_SYSTEM = """You are an intent classifier for a personal assistant bot. Reply with exactly one word.

Valid intents:
- cal_add: user wants to add, schedule, or create a calendar event
- cal_delete: user wants to delete, remove, or cancel a calendar event
- cal_move: user wants to move, reschedule, or change the time of a calendar event
- cal_list: user wants to see, list, or check calendar events
- search: user wants real-time info (sports scores, news, weather, current events, prices, anything that changes day to day)
- chat: everything else (questions, conversation, tasks, calculations, opinions, general knowledge)

Reply with only the intent word. No punctuation, no explanation."""


def classify_llm(text):
    """LLM-based intent classifier for natural language messages.
    Returns an intent string or None on failure."""
    try:
        from cloud_router import call_provider, PROVIDERS
        provider = next(p for p in PROVIDERS if p["name"] == "groq")
        msgs = [{"role": "user", "content": text}]
        success, response, code = call_provider(
            provider, msgs, system_prompt=CLASSIFY_SYSTEM
        )
        if not success:
            return None
        intent = response.strip().lower().split()[0] if response.strip() else None
        if intent in VALID_NL_INTENTS:
            return intent
        return None
    except Exception as e:
        log(f"classify_llm error: {e}")
        return None


def classify(text):
    """
    Intent classifier. Slash commands are handled deterministically.
    Natural language goes to LLM classifier with regex fallback.
    """
    t = text.lower().strip()

    # ── Slash commands: always deterministic ──────────────
    if t in ['/start', '/help']:
        return 'help'
    if t == '/usage':
        return 'usage'
    if t == '/reset':
        return 'reset'
    if t == '/stats':
        return 'stats'
    if t == '/memory':
        return 'memory'
    if t.startswith('/remember '):
        return 'remember'
    if t.startswith('/run'):
        return 'run'
    if t.startswith('/patch'):
        return 'patch'
    if t.startswith('/search'):
        return 'search'
    if t.startswith('/cal'):
        return classify_regex(text)

    # ── Natural language: LLM first, regex fallback ───────
    intent = classify_llm(text)
    if intent:
        log(f"classify_llm: {intent}")
        return intent

    log("classify_llm failed, falling back to regex")
    return classify_regex(text)


# ─────────────────────────────────────────────────────────
# Chat handler (unchanged)
# ─────────────────────────────────────────────────────────

def get_today_context():
    try:
        import pytz
        pacific = pytz.timezone('America/Los_Angeles')
        now = datetime.datetime.now(pacific)
        today = now.date()
        tomorrow = today + datetime.timedelta(days=1)

        cache = Path('/mnt/virgil_storage/digest/calendar_all.txt')
        if not cache.exists():
            return ""

        events_today = []
        events_tomorrow = []

        for line in cache.read_text().split('\n'):
            if line.startswith('CALENDAR') or not line.strip():
                continue
            parts = line.split('\t')
            if len(parts) < 5:
                continue
            try:
                summary = parts[4].strip()
                start_str = parts[2].strip()
                if 'T' in start_str:
                    dt = datetime.datetime.fromisoformat(start_str.replace('Z', '+00:00')).astimezone(pacific)
                    if dt.date() == today:
                        events_today.append(f"{dt.strftime('%I:%M %p').lstrip('0')} {summary}")
                    elif dt.date() == tomorrow:
                        events_tomorrow.append(f"{dt.strftime('%I:%M %p').lstrip('0')} {summary}")
                else:
                    d = datetime.date.fromisoformat(start_str)
                    end_str = parts[3].strip()
                    end_d = datetime.date.fromisoformat(end_str) if 'T' not in end_str else None
                    if d <= today < (end_d or d + datetime.timedelta(days=1)):
                        events_today.append(f"All day: {summary}")
                    elif d <= tomorrow < (end_d or d + datetime.timedelta(days=1)):
                        events_tomorrow.append(f"All day: {summary}")
            except Exception:
                continue

        parts = [f"Today is {today.strftime('%A, %B %d, %Y')}. Current time is {now.strftime('%I:%M %p')} Pacific."]
        if events_today:
            parts.append(f"Today's calendar: {', '.join(events_today)}")
        else:
            parts.append("Nothing on the calendar today.")
        if events_tomorrow:
            parts.append(f"Tomorrow's calendar: {', '.join(events_tomorrow)}")

        return " ".join(parts)
    except Exception:
        return ""


def handle_chat(chat_id, text):
    history = db_history(chat_id, n=CONTEXT_WINDOW)
    today_context = get_today_context()
    facts = db_get_facts()

    system = SYSTEM_PROMPT
    extras = []
    if today_context:
        extras.append(today_context)
    if facts:
        extras.append(facts)
    if extras:
        system = SYSTEM_PROMPT + "\n\n" + "\n\n".join(extras)

    extract_facts_from_message(text, chat_id)

    messages = history + [{'role': 'user', 'content': text}]

    t = text.lower()
    if any(w in t for w in ['password', 'social security', 'credit card', 'ssn', 'my address']):
        task = 'personal'
    elif any(w in t for w in ['code', 'python', 'bash', 'script', 'bug', 'debug', 'error', 'traceback']):
        task = 'code'
    elif any(w in t for w in ['analyze', 'compare', 'explain why', 'pros and cons', 'research', 'plan ']):
        task = 'reasoning'
    else:
        task = 'general'

    log(f"chat: task={task} len={len(text)}")
    start_ts = time.time()
    provider_used = None
    try:
        response, provider_used = route(messages=messages, task_type=task, system_prompt=system)
    except Exception as e:
        log(f"route error: {e}")
        response = f"Error calling router: {e}"

    if not response or response.startswith("All providers exhausted"):
        response = "All cloud providers unavailable. Try again in a bit."

    tg_send(chat_id, response)
    db_log(chat_id, 'assistant', response, route_type='chat', provider=provider_used or task)


# ─────────────────────────────────────────────────────────
# System command handlers (unchanged)
# ─────────────────────────────────────────────────────────

def handle_help(chat_id):
    msg = (
        "🦞 <b>Virgil</b>\n\n"
        "<b>Calendar:</b>\n"
        "• /cal [event] [date] [time]\n"
        "• /cal [event] [date] all day\n"
        "• /cal delete [event] [date]\n"
        "• /cal move [event] [date] to [new time]\n"
        "• /cal list [date]\n\n"
        "<b>System:</b>\n"
        "• /run [task] — run Python code\n"
        "• /search [query] — search the web\n"
        "• /patch [description] — modify bot code\n"
        "• /stats — bot uptime and today's activity\n"
        "• /usage — cloud API usage today\n"
        "• /remember [key]: [value] — save a fact\n"
        "• /memory — show what I know about you\n"
        "• /reset — clear conversation memory\n"
        "• /help — this message"
    )
    tg_send(chat_id, msg)


def handle_usage(chat_id):
    try:
        from cloud_router import get_usage_report
        tg_send(chat_id, f"<pre>{get_usage_report()}</pre>")
    except Exception as e:
        tg_send(chat_id, f"Error getting usage: {e}")

def handle_stats(chat_id):
    """Show bot uptime, today's message count, and recent errors."""
    try:
        # Uptime
        uptime_sec = int(time.time() - START_TIME) if START_TIME else 0
        h, m = divmod(uptime_sec // 60, 60)
        uptime_str = f"{h}h {m}m" if h else f"{m}m"

        # Today's message count
        today = datetime.date.today().isoformat()
        conn = sqlite3.connect(DB_PATH)
        total = conn.execute(
            "SELECT COUNT(*) FROM messages WHERE ts LIKE ?", (f"{today}%",)
        ).fetchone()[0]
        by_role = conn.execute(
            "SELECT role, COUNT(*) FROM messages WHERE ts LIKE ? GROUP BY role",
            (f"{today}%",)
        ).fetchall()
        conn.close()
        role_counts = {r: c for r, c in by_role}

        # Error count from structured log (today)
        error_count = 0
        if LOG_PATH.exists():
            for line in LOG_PATH.read_text().splitlines():
                if line.startswith('{') and today in line:
                    try:
                        ev = json.loads(line)
                        if ev.get("type", "").endswith("_error"):
                            error_count += 1
                    except Exception:
                        pass
        # Top actual cloud providers (exclude task-type fallback values)
        conn = sqlite3.connect(DB_PATH)
        providers = conn.execute(
            "SELECT provider, COUNT(*) as cnt FROM messages "
            "WHERE ts LIKE ? AND route='chat' "
            "AND provider NOT IN ('general','code','reasoning','personal','digest','analysis','agentic') "
            "GROUP BY provider ORDER BY cnt DESC LIMIT 3",
            (f"{today}%",)
        ).fetchall()
        conn.close()


        lines = [
            "📊 <b>Virgil Stats</b>",
            f"⏱ Uptime: {uptime_str}",
            f"💬 Today's messages: {total}",
            f"   User: {role_counts.get('user', 0)} | Assistant: {role_counts.get('assistant', 0)}",
            f"❌ Errors today: {error_count}",
        ]
        if providers:
            lines.append("☁️ Top providers:")
            for name, cnt in providers:
                lines.append(f"   {name}: {cnt}")

        tg_send(chat_id, "\n".join(lines))
    except Exception as e:
        log(f"handle_stats error: {e}")
        tg_send(chat_id, f"Error getting stats: {e}")

def handle_code(chat_id, text):
    from cloud_router import PROVIDERS, call_provider, increment_usage, load_usage
    prompt = text[6:].strip()
    if not prompt:
        tg_send(chat_id, 'Usage: /code [question]')
        return
    CODE_ORDER = ['mistral','groq_heavy','cerebras','groq','openrouter','local']
    RESERVES = {'mistral':20,'groq_heavy':20,'cerebras':20,'groq':20,'openrouter':20,'local':0}
    usage = load_usage()
    counts = usage.get('counts', {})
    system = "You are a coding assistant. Return ONLY the code. No explanation, no prose, no usage examples. Code only."
    messages = [{'role': 'user', 'content': prompt}]
    tg_typing(chat_id)
    for pname in CODE_ORDER:
        provider = next((p for p in PROVIDERS if p['name'] == pname), None)
        if not provider:
            continue
        current = counts.get(pname, 0)
        limit = provider['daily_limit']
        reserve = RESERVES.get(pname, 20)
        if current >= (limit - reserve):
            continue
        success, response, code = call_provider(provider, messages, system_prompt=system)
        if success:
            increment_usage(pname)
            tg_send(chat_id, response)
            db_log(chat_id, 'assistant', response, route_type='code', provider=pname)
            return
    tg_send(chat_id, 'All code providers exhausted. Try again tomorrow.')


def handle_remember(chat_id, text):
    parts = text[10:].strip()
    if ':' in parts:
        key, value = parts.split(':', 1)
        db_save_fact(key.strip(), value.strip())
        tg_send(chat_id, f"✅ Saved: <b>{key.strip()}</b> = {value.strip()}")
    else:
        db_save_fact("note", parts)
        tg_send(chat_id, f"✅ Saved note: {parts}")


def handle_memory(chat_id):
    facts = db_get_facts()
    if not facts:
        tg_send(chat_id, "No facts saved yet.")
    else:
        tg_send(chat_id, f"<b>What I know about you:</b>\n<pre>{facts}</pre>")



# ─────────────────────────────────────────────────────────
# /run — sandboxed Python execution
# ─────────────────────────────────────────────────────────

BLOCKED_IMPORTS = {
    'os', 'sys', 'subprocess', 'socket', 'shutil', 'pathlib',
    'importlib', 'builtins', 'ctypes', 'multiprocessing',
    'threading', 'signal', 'pty', 'tty', 'termios',
    'resource', 'pwd', 'grp', 'fcntl', 'mmap',
}

RUN_WRAPPER_TMPL = """
import sys, resource, builtins, io, traceback

try:
    resource.setrlimit(resource.RLIMIT_AS, (64 * 1024 * 1024, 64 * 1024 * 1024))
except Exception:
    pass

_real_import = builtins.__import__
_BLOCKED = BLOCKED_PLACEHOLDER
def _safe_import(name, *args, **kwargs):
    base = name.split('.')[0]
    if base in _BLOCKED:
        raise ImportError(f"Import of '{name}' is not allowed in /run")
    return _real_import(name, *args, **kwargs)
builtins.__import__ = _safe_import

_out = io.StringIO()
sys.stdout = _out
sys.stderr = _out

try:
    exec(compile(CODE_PLACEHOLDER, '<run>', 'exec'), {})
except Exception:
    traceback.print_exc()

sys.stdout = sys.__stdout__
print(_out.getvalue(), end='')
"""

def run_sandboxed(code):
    """Execute code in a restricted subprocess. Returns (output, error_flag)."""
    import subprocess, tempfile, os

    wrapper = RUN_WRAPPER_TMPL.replace(
        'BLOCKED_PLACEHOLDER', repr(BLOCKED_IMPORTS)
    ).replace(
        'CODE_PLACEHOLDER', repr(code)
    )

    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(wrapper)
        tmp = f.name

    try:
        result = subprocess.run(
            ['/usr/bin/python3', tmp],
            capture_output=True,
            text=True,
            timeout=5,
        )
        output = (result.stdout + result.stderr).strip()
        if not output:
            output = "(no output)"
        if len(output) > 2000:
            output = output[:2000] + "\n... (truncated)"
        return output, result.returncode != 0
    except subprocess.TimeoutExpired:
        return "Timed out (5s limit)", True
    except Exception as e:
        return f"Runner error: {e}", True
    finally:
        try:
            os.unlink(tmp)
        except Exception:
            pass


def handle_run(chat_id, text):
    """Handle /run — LLM writes code, sandbox executes it, result sent back."""
    prompt = text[4:].strip()
    if not prompt:
        tg_send(chat_id, "Usage: /run [what you want to compute]\nExample: /run fibonacci up to 100")
        return

    tg_typing(chat_id)

    code_system = (
        "You are a Python code generator. "
        "Return ONLY raw executable Python code with no markdown, no backticks, no explanation. "
        "The code must print its result to stdout. "
        "No file I/O, no network calls, no os/sys/subprocess imports."
    )

    try:
        code_resp, provider = route(
            messages=[{"role": "user", "content": f"Write Python code to: {prompt}"}],
            task_type="code",
            system_prompt=code_system
        )
    except Exception as e:
        tg_send(chat_id, f"LLM error: {e}")
        return

    # Strip accidental markdown fences
    code = re.sub(r"^```[\w]*\n?", "", code_resp.strip(), flags=re.MULTILINE)
    code = re.sub(r"```$", "", code.strip(), flags=re.MULTILINE).strip()

    log(f"run: {len(code)} chars via {provider}")
    output, had_error = run_sandboxed(code)

    icon = "❌" if had_error else "✅"
    msg = f"{icon} <b>/run result:</b>\n<pre>{output}</pre>"
    tg_send(chat_id, msg)
    db_log(chat_id, 'assistant', msg, route_type='run', provider=provider)



# ─────────────────────────────────────────────────────────
# /patch — self-modification workflow
# ─────────────────────────────────────────────────────────

BOT_PATH = Path('/home/jordaneal/scripts/virgil_bot.py')
STAGING_PATH = Path('/home/jordaneal/scripts/virgil_bot.staging.py')
DIFF_CHAR_LIMIT = 500

PATCH_SYSTEM = """You are a Python function editor. The user will give you a single Python function and a description of a change to make.
Return only the modified function and nothing else.
No markdown, no backticks, no explanation. Just the raw Python function definition."""


def extract_function(source, func_name):
    """
    Extract a top-level function by name from source code.
    Returns (func_source, start_line, end_line) or (None, None, None).
    """
    import ast
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None, None, None

    lines = source.splitlines(keepends=True)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            start = node.lineno - 1  # 0-indexed
            end = node.end_lineno    # 0-indexed exclusive
            func_source = ''.join(lines[start:end])
            return func_source, start, end

    return None, None, None


def splice_function(source, new_func, start, end):
    """Replace lines [start:end] in source with new_func."""
    lines = source.splitlines(keepends=True)
    new_lines = new_func.splitlines(keepends=True)
    if not new_lines[-1].endswith('\n'):
        new_lines[-1] += '\n'
    return ''.join(lines[:start] + new_lines + lines[end:])


def generate_diff(original, modified):
    """Return a unified diff string between original and modified."""
    import difflib
    orig_lines = original.splitlines(keepends=True)
    mod_lines = modified.splitlines(keepends=True)
    diff = difflib.unified_diff(orig_lines, mod_lines, fromfile='current', tofile='patched', n=3)
    return ''.join(diff)


def handle_patch(chat_id, text):
    """
    /patch [function_name]: [description]
    Extracts the named function, sends it to LLM with description,
    splices result back in, diffs, confirms, restarts.
    """
    body = text[6:].strip()
    if not body or ':' not in body:
        tg_send(chat_id, "Usage: /patch [function]: [description]\nExample: /patch handle_chat: make responses more concise")
        return

    func_name, description = body.split(':', 1)
    func_name = func_name.strip()
    description = description.strip()

    if not BOT_PATH.exists():
        tg_send(chat_id, "❌ Bot file not found.")
        return

    current_code = BOT_PATH.read_text()

    # Extract the target function
    func_source, start, end = extract_function(current_code, func_name)
    if func_source is None:
        tg_send(chat_id, f"❌ Function '{func_name}' not found in bot file.")
        return

    tg_send(chat_id, f"🔧 Patching {func_name} ({end - start} lines)...")
    tg_typing(chat_id)

    try:
        from cloud_router import PROVIDERS, call_provider as _call_provider
        msgs = [
            {"role": "system", "content": PATCH_SYSTEM},
            {"role": "user", "content": f"Here is the function:\n\n{func_source}\n\nChange to make: {description}"}
        ]
        new_func = None
        provider = "none"
        for pname in ["groq", "mistral", "cerebras", "gemini"]:
            p = next((x for x in PROVIDERS if x["name"] == pname), None)
            if not p:
                continue
            log(f"patch: trying {pname}")
            success, response, code = _call_provider(p, msgs, max_tokens=2000)
            if success:
                new_func = response
                provider = pname
                break
            log(f"patch: {pname} failed ({code})")
        if not new_func:
            tg_send(chat_id, "❌ All patch providers failed.")
            return
    except Exception as e:
        tg_send(chat_id, f"❌ LLM error: {e}")
        return

    # Strip accidental markdown fences
    new_func = re.sub(r"^```[\w]*\n?", "", new_func.strip(), flags=re.MULTILINE)
    new_func = re.sub(r"```$", "", new_func.strip(), flags=re.MULTILINE).strip()

    # Splice into full source
    modified_code = splice_function(current_code, new_func, start, end)

    # Syntax check full file
    try:
        import ast
        ast.parse(modified_code)
    except SyntaxError as e:
        tg_send(chat_id, f"❌ Syntax error after patch: {e}\nAborted.")
        return

    # Generate diff
    diff = generate_diff(current_code, modified_code)
    if not diff:
        tg_send(chat_id, "No changes detected.")
        return

    if len(diff) > DIFF_CHAR_LIMIT:
        remaining = len(diff) - DIFF_CHAR_LIMIT
        diff_display = f"{diff[:DIFF_CHAR_LIMIT]}\n... ({remaining} more chars)"
    else:
        diff_display = diff

    STAGING_PATH.write_text(modified_code)

    msg = f"📋 <b>Patch: {func_name}</b> (via {provider}):\n<pre>{diff_display}</pre>\n\nReply 'yes' to deploy or anything else to discard."
    tg_send(chat_id, msg)

    save_pending(str(chat_id), {
        'type': 'confirm_patch',
        'staging_path': str(STAGING_PATH),
        'ts': time.time()
    })


def apply_patch(chat_id):
    """Syntax-check staging file, atomic swap, restart."""
    import ast

    if not STAGING_PATH.exists():
        tg_send(chat_id, "❌ Staging file missing. Patch aborted.")
        return

    staged_code = STAGING_PATH.read_text()

    # Final syntax check
    try:
        ast.parse(staged_code)
    except SyntaxError as e:
        tg_send(chat_id, f"❌ Syntax error in staged file: {e}\nPatch aborted.")
        STAGING_PATH.unlink(missing_ok=True)
        return

    # Atomic swap
    try:
        import os
        BOT_PATH.write_text(staged_code)
        STAGING_PATH.unlink(missing_ok=True)
    except Exception as e:
        tg_send(chat_id, f"❌ Failed to write file: {e}")
        return

    tg_send(chat_id, "✅ Patch applied. Restarting...")
    log("apply_patch: restarting via os.execv")

    # Clear pending before restart so the replayed 'yes' doesn't re-trigger
    delete_pending(str(chat_id))

    import os
    os.execv(sys.executable, [sys.executable] + sys.argv)



# ─────────────────────────────────────────────────────────
# Web search via Brave Search API
# ─────────────────────────────────────────────────────────

BRAVE_API_KEY = os.getenv('BRAVE_API_KEY')


def web_search(query, count=5):
    """Search the web via Brave. Returns list of {title, url, description} dicts."""
    if not BRAVE_API_KEY:
        return []
    try:
        resp = requests.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": BRAVE_API_KEY
            },
            params={"q": query, "count": count},
            timeout=10
        )
        if resp.status_code != 200:
            log(f"web_search: Brave returned {resp.status_code}")
            return []
        results = []
        for r in resp.json().get("web", {}).get("results", [])[:count]:
            results.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "description": r.get("description", "")
            })
        return results
    except Exception as e:
        log(f"web_search error: {e}")
        return []


def handle_search(chat_id, text):
    """Handle real-time queries via Brave Search + LLM synthesis."""
    tg_typing(chat_id)
    log(f"web_search: query={text[:80]}")

    results = web_search(text)
    if not results:
        tg_send(chat_id, "Search unavailable right now.")
        return

    results_text = "\n\n".join(
        f"[{r['title']}]\n{r['description']}\nSource: {r['url']}"
        for r in results
    )

    search_system = (
        "You are Virgil, a direct personal assistant. "
        "Answer the user's question using the search results provided. "
        "Be concise and direct. Cite sources naturally if relevant. "
        "If the results don't contain the answer, say so plainly."
    )

    try:
        response, provider = route(
            messages=[{"role": "user", "content": f"Question: {text}\n\nSearch results:\n{results_text}"}],
            task_type="fast",
            system_prompt=search_system
        )
    except Exception as e:
        tg_send(chat_id, f"Error: {e}")
        return

    tg_send(chat_id, response)
    db_log(chat_id, 'assistant', response, route_type='search', provider=provider)


def handle_reset(chat_id):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute('DELETE FROM messages WHERE chat_id = ?', (str(chat_id),))
        conn.commit()
        conn.close()
        tg_send(chat_id, "🧹 Memory cleared.")
    except Exception as e:
        tg_send(chat_id, f"Error resetting: {e}")


# ─────────────────────────────────────────────────────────
# Main loop
# ─────────────────────────────────────────────────────────

def process_message(update, offset):
    msg = update.get('message', {})
    chat_id = str(msg.get('chat', {}).get('id', ''))
    text = msg.get('text', '')

    if chat_id not in ALLOWED_CHAT_IDS:
        log(f"ignored: chat_id {chat_id} not allowed")
        return offset
    if not text:
        return offset

    db_log(chat_id, 'user', text)
    log(f"msg from {chat_id}: {text[:80]}")
    tg_typing(chat_id)

    # If there's a pending calendar action for this chat, handle it FIRST
    if get_pending(chat_id):
        return handle_pending(chat_id, text, offset)

    # Drop bare confirmation words with no pending action — likely a restart replay
    if text.strip().lower() in ('yes', 'y', 'yep', 'yeah', 'confirm', 'ok', 'sure', 'no', 'n', 'cancel'):
        log(f"dropped bare confirmation '{text}' with no pending action")
        return offset

    route_type = classify(text)
    log(f"classified: {route_type}")

    # Strip /cal prefix before passing to calendar handlers
    cal_text = re.sub(r'^/cal\s+', '', text, flags=re.I).strip()

    try:
        if route_type == 'help':
            handle_help(chat_id)
        elif route_type == 'stats':
            handle_stats(chat_id)
        elif route_type == 'usage':
            handle_usage(chat_id)
        elif route_type == 'reset':
            handle_reset(chat_id)
        elif route_type == 'memory':
            handle_memory(chat_id)
        elif route_type == 'remember':
            handle_remember(chat_id, text)
        elif route_type == 'code':
            handle_code(chat_id, text)
        elif route_type == 'run':
            handle_run(chat_id, text)
        elif route_type == 'patch':
            handle_patch(chat_id, text)
        elif route_type == 'search':
            handle_search(chat_id, text)
        elif route_type == 'cal_add':
            handle_add(chat_id, cal_text)
        elif route_type == 'cal_delete':
            handle_delete(chat_id, cal_text)
        elif route_type == 'cal_move':
            handle_move(chat_id, cal_text)
        elif route_type == 'cal_list':
            handle_list(chat_id, cal_text)
        else:
            handle_chat(chat_id, text)
    except Exception as e:
        event_log("handler_error", chat_id, route=route_type, error=str(e)[:200])
        log(f"handler error ({route_type}): {e}")
        tg_send(chat_id, f"❌ Error: {str(e)[:200]}")
    return offset


OFFSET_FILE = Path('/mnt/virgil_storage/last_update_id.txt')


def load_offset():
    """Load last processed update_id from disk to skip replays on restart."""
    try:
        if OFFSET_FILE.exists():
            val = OFFSET_FILE.read_text().strip()
            if val.isdigit():
                return int(val)
    except Exception:
        pass
    return None


def save_offset(offset):
    """Persist current offset to disk."""
    try:
        OFFSET_FILE.write_text(str(offset))
    except Exception as e:
        log(f"save_offset error: {e}")


def main():
    if not BOT_TOKEN:
        log("FATAL: TELEGRAM_BOT_TOKEN not set")
        sys.exit(1)

    db_init()
    global START_TIME
    START_TIME = time.time()
    log("Virgil bot starting")
    import random
    STARTUP_QUIPS = [
        "Coffee's on you.",
        "Don't ask what happened.",
        "Bathroom garbages aren't going to track themselves.",
        "Par or bogey today?",
        "Wednesday bowling doesn't schedule itself.",
        "PSMF isn't going to track itself either.",
        "The garage server lives another day.",
        "What did I miss?",
        "Try not to break anything this time.",
        "Fairways are wet, probably.",
        "Dad stuff first, cool stuff second.",
        "Qwen says hi.",
        "Let's get something done.",
        "The anime queue isn't getting shorter.",
        "All systems nominal. Probably.",
        "Hit me.",
        "Groq's fast today. Enjoy it.",
        "Still cheaper than a secretary.",
        "What's the damage?",
        "Server's cold but I'm not.",
        "Wednesday bowling form still needs work.",
        "Making garage servers great again.",
        "Qwen warmed up, cloud on standby.",
        "The kids asleep?",
        "Let's see what breaks today.",
    ]
    quip = random.choice(STARTUP_QUIPS)
    for cid in ALLOWED_CHAT_IDS:
        tg_send(cid, f"\U0001f9be\U0001f3db\ufe0f {quip}")

    offset = load_offset()
    if offset:
        log(f"resuming from offset {offset}")

    while True:
        try:
            updates = tg_get_updates(offset)
            for u in updates.get('result', []):
                offset = u['update_id'] + 1
                save_offset(offset)
                offset = process_message(u, offset) or offset
        except KeyboardInterrupt:
            log("Shutting down")
            break
        except Exception as e:
            log(f"main loop error: {e}")
            time.sleep(5)


if __name__ == '__main__':
    main()
