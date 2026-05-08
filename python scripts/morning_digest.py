#!/usr/bin/env python3
"""
Morning Digest for Virgil - Local Server Edition
Fetches calendar, weather, news, golf windows and sends Telegram message.
"""

import os
import sys
import datetime
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv('/home/jordaneal/scripts/.env')

DIGEST_DIR = Path("/mnt/virgil_storage/digest")
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
WEATHER_CITY = "Chehalis,WA,US"
LOG_FILE = DIGEST_DIR / "morning_digest.log"


def log(msg):
    line = f"[{datetime.datetime.now().isoformat(timespec='seconds')}] {msg}"
    print(line)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, 'a') as f:
            f.write(line + '\n')
    except Exception:
        pass


# Chehalis, WA coordinates (static — no geo API call needed)
LAT, LON = 46.6621, -122.9647


def get_onecall(api_key, lat, lon):
    try:
        return requests.get(
            f"https://api.openweathermap.org/data/3.0/onecall?lat={lat}&lon={lon}&units=imperial&exclude=minutely,alerts&appid={api_key}",
            timeout=10
        ).json()
    except Exception as e:
        log(f"get_onecall error: {e}")
        return None


def format_weather(data):
    try:
        current = data['current']
        current_temp = int(current['temp'])
        feels_like = int(current['feels_like'])
        description = current['weather'][0]['description'].title()
        high = int(data['daily'][0]['temp']['max'])
        low = int(data['daily'][0]['temp']['min'])
        rain_chance = data['daily'][0].get('pop', 0) * 100
        wind_speed = current.get('wind_speed', 0)

        if rain_chance >= 20 or 'rain' in description.lower():
            emoji = "🌧️"
        elif wind_speed > 10 or 'wind' in description.lower():
            emoji = "💨"
        elif 'clear' in description.lower():
            emoji = "☀️"
        elif 'cloud' in description.lower():
            emoji = "☁️"
        else:
            emoji = "🌤️"

        return f"Current: {current_temp}°F (feels like {feels_like}°F)\nHigh: {high}°F | Low: {low}°F\n{emoji} {description}"
    except Exception as e:
        return f"Error formatting weather: {e}"


def get_calendar_events():
    try:
        import pytz
        pacific = pytz.timezone('America/Los_Angeles')
        now = datetime.datetime.now(pacific)
        today = now.date()

        cache_file = DIGEST_DIR / "calendar_all.txt"
        if not cache_file.exists():
            return "⚠️ Calendar cache not found."

        lines = cache_file.read_text().strip().split('\n')
        events_by_date = {today + datetime.timedelta(days=i): [] for i in range(3)}

        for line in lines:
            if line.startswith('CALENDAR') or not line.strip():
                continue
            parts = line.split('\t')
            if len(parts) < 5:
                continue
            try:
                summary = parts[4].strip()
                start_str = parts[2].strip()
                end_str = parts[3].strip()

                if 'T' in start_str:
                    start_dt = datetime.datetime.fromisoformat(start_str.replace('Z', '+00:00')).astimezone(pacific)
                    start_date = start_dt.date()
                    h, m = start_dt.hour, start_dt.minute
                    period = 'AM' if h < 12 else 'PM'
                    h = h if h <= 12 else h - 12
                    h = h or 12
                    time_str = f"{h}:{m:02d} {period}"
                else:
                    start_date = datetime.date.fromisoformat(start_str)
                    time_str = "All day"

                if 'T' in end_str:
                    end_dt = datetime.datetime.fromisoformat(end_str.replace('Z', '+00:00')).astimezone(pacific)
                    end_date = end_dt.date()
                else:
                    end_date = datetime.date.fromisoformat(end_str)

                for target_date in events_by_date:
                    in_range = (start_date <= target_date <= end_date) if 'T' in start_str else (start_date <= target_date < end_date)
                    if in_range:
                        if start_date < target_date and target_date == end_date and 'T' in end_str:
                            eh, em = end_dt.hour, end_dt.minute
                            ep = 'AM' if eh < 12 else 'PM'
                            eh = eh if eh <= 12 else eh - 12
                            eh = eh or 12
                            events_by_date[target_date].append(f"Ends {eh}:{em:02d} {ep} - {summary}")
                        elif start_date == target_date:
                            events_by_date[target_date].append(f"{time_str} - {summary}")
                        else:
                            events_by_date[target_date].append(f"All day - {summary}")
            except Exception:
                continue

        result = []
        for i, (date, events) in enumerate(sorted(events_by_date.items())):
            if not events:
                continue
            label = "Today" if i == 0 else "Tomorrow" if i == 1 else date.strftime('%A')
            result.append(f"<b>{label}:</b>")
            result.extend(f"  {e}" for e in events)

        return "\n".join(result) if result else "No upcoming events."

    except Exception as e:
        return f"Error loading calendar: {e}"


def get_golf_forecast(data):
    """
    Build golf section using LLM analysis of hourly + daily forecast data.
    No hardcoded thresholds — LLM reasons about conditions naturally.
    Weather data already fetched once in main(), passed in here.
    """
    try:
        import pytz
        pacific = pytz.timezone('America/Los_Angeles')
        now = datetime.datetime.now(pacific)
        today = now.date()

        if not data or not data.get('hourly') or not data.get('daily'):
            return ""

        # Build today's hourly summary (9am-7pm only)
        hourly_lines = []
        for h in data['hourly'][:24]:
            hour_dt = datetime.datetime.fromtimestamp(h['dt'], tz=pacific)
            if hour_dt.date() != today or hour_dt.hour < 9 or hour_dt.hour > 19:
                continue
            rain_pct = int(h.get('pop', 0) * 100)
            wind = round(h.get('wind_speed', 0), 1)
            temp = round(h['temp'], 1)
            desc = h['weather'][0]['description']
            hourly_lines.append(
                f"  {hour_dt.strftime('%-I %p')}: {temp}°F, {rain_pct}% rain, {wind}mph wind, {desc}"
            )

        # Build upcoming days summary (next 7 days)
        # Load calendar to note busy days
        busy_dates = set()
        cache_file = DIGEST_DIR / "calendar_all.txt"
        if cache_file.exists():
            for line in cache_file.read_text().strip().split('\n'):
                if line.startswith('CALENDAR'):
                    continue
                parts = line.split('\t')
                if len(parts) >= 5:
                    try:
                        start_str = parts[2].strip()
                        if 'T' in start_str:
                            event_dt = datetime.datetime.fromisoformat(
                                start_str.replace('Z', '+00:00')
                            ).astimezone(pacific)
                            busy_dates.add(event_dt.date())
                    except Exception:
                        continue

        daily_lines = []
        for day in data['daily'][1:8]:
            forecast_date = datetime.datetime.fromtimestamp(day['dt'], tz=pacific).date()
            busy = " (busy)" if forecast_date in busy_dates else ""
            rain_pct = int(day.get('pop', 0) * 100)
            wind = round(day.get('wind_speed', 0), 1)
            high = round(day['temp']['max'], 1)
            low = round(day['temp']['min'], 1)
            desc = day['weather'][0]['description']
            daily_lines.append(
                f"  {forecast_date.strftime('%A %b %d')}{busy}: high {high}°F / low {low}°F, {rain_pct}% rain, {wind}mph wind, {desc}"
            )

        if not hourly_lines and not daily_lines:
            return ""

        prompt = f"""You are analyzing golf conditions for Jordan Neal in Chehalis, WA.
Current time: {now.strftime('%I:%M %p')} on {today.strftime('%A, %B %d')}

Today's hourly forecast (9am-7pm):
{chr(10).join(hourly_lines) if hourly_lines else "  No daytime hours remaining today"}

Upcoming days:
{chr(10).join(daily_lines)}

Provide a concise golf forecast in two parts:
1. Today's golf windows — specific time ranges that are good or bad, with brief reasoning. Be direct.
2. Best days this week — only mention days that are genuinely good for golf (skip busy days). Max 3 days.

Output MUST follow this exact template, no deviations:

<b>⛳️ Today's Golf Windows:</b>
[✅ or ❌] [weather emoji] [time range]: [brief note, no parentheses]
[✅ or ❌] [weather emoji] [time range]: [brief note, no parentheses]

<b>🏌️ Ideal Days This Week:</b>
[weather emoji] [Day Mon DD]: [commentary]
[weather emoji] [Day Mon DD]: [commentary]

Rules:
- No parentheses anywhere
- Bold only on the two section headers shown above
- Weather emoji immediately after ✅/❌ in windows section
- Ideal days: weather emoji first, then date colon, then commentary. No dashes.
- HTML-safe text only"""

        sys.path.insert(0, '/home/jordaneal/scripts')
        from cloud_router import route
        result, _ = route(
            messages=[{"role": "user", "content": prompt}],
            task_type="digest",
            system_prompt="You are a concise golf weather analyst. Return only the formatted forecast, no preamble."
        )

        return result.strip()

    except Exception as e:
        log(f"Golf forecast error: {e}")
        return ""


def get_news():
    try:
        api_key = os.getenv('NEWS_API_KEY')
        if not api_key:
            return "⚠️ News API key not configured."
        data = requests.get(
            f"https://newsapi.org/v2/top-headlines?country=us&pageSize=5&apiKey={api_key}",
            timeout=10
        ).json()
        if data.get('articles'):
            return "\n".join(
                f"{i}. {a.get('title', 'No title')}\n   {a.get('url', '')}\n"
                for i, a in enumerate(data['articles'][:5], 1)
            )
        return "No news available."
    except Exception as e:
        return f"Error fetching news: {e}"


def get_joke():
    try:
        data = requests.get("https://v2.jokeapi.dev/joke/Any?safe-mode", timeout=10).json()
        if data.get('joke'):
            return data['joke']
        if data.get('setup') and data.get('delivery'):
            return f"{data['setup']}\n{data['delivery']}"
    except Exception:
        pass
    return "Why don't scientists trust atoms? Because they make up everything!"


def get_daily_commentary(weather, calendar, golf):
    try:
        sys.path.insert(0, '/home/jordaneal/scripts')
        from cloud_router import route
        context = f"Weather: {weather}\nCalendar: {calendar}\nGolf windows: {golf}"
        result, _ = route(
            messages=[{"role": "user", "content": f"Write ONE dry witty sentence (max 15 words) as a morning commentary for this day. No emojis, no fluff:\n{context}"}],
            task_type="digest",
            system_prompt="You are Virgil, a dry witty AI assistant for Jordan Neal in Chehalis WA. One sentence only. Be specific to the data."
        )
        return result.strip()
    except Exception as e:
        log(f"Commentary error: {e}")
        return ""


def send_telegram_message(text):
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={'chat_id': TELEGRAM_CHAT_ID, 'text': text, 'parse_mode': 'HTML'},
            timeout=10
        )
        return response.status_code == 200
    except Exception as e:
        log(f"Telegram error: {e}")
        return False


def main():
    DIGEST_DIR.mkdir(parents=True, exist_ok=True)
    log("Morning digest starting")

    # Fetch weather coords and data once — reused by both weather and golf
    api_key = os.getenv('OPENWEATHER_API_KEY')
    weather_data = None
    if api_key:
        log("Fetching weather...")
        weather_data = get_onecall(api_key, LAT, LON)

    weather = format_weather(weather_data) if weather_data else "⚠️ Weather unavailable."
    (DIGEST_DIR / "weather.txt").write_text(weather)

    log("Fetching calendar...")
    calendar = get_calendar_events()
    (DIGEST_DIR / "calendar.txt").write_text(calendar)

    log("Analyzing golf forecast...")
    golf = get_golf_forecast(weather_data)

    log("Fetching news...")
    news = get_news()
    (DIGEST_DIR / "news.txt").write_text(news)

    log("Getting joke...")
    joke = get_joke()
    (DIGEST_DIR / "joke.txt").write_text(joke)

    log("Getting commentary...")
    commentary = get_daily_commentary(weather, calendar, golf)

    now = datetime.datetime.now()
    date_str = now.strftime('%A, %B %d, %Y')

    message = f"""<b>☀️ Morning Digest - {date_str}</b>
<i>{commentary}</i>

<b>😄 Today's Joke</b>
{joke}

<b>🌤️ Weather</b>
{weather}

<b>📅 Calendar</b>
{calendar}

{golf if golf else ""}

<b>📰 Top News</b>
{news}

<i>Generated at {now.strftime('%I:%M %p PST')}</i>
"""

    log("Sending Telegram message...")
    if send_telegram_message(message):
        log(f"Morning digest complete: {now.strftime('%Y-%m-%d')}")
    else:
        log("Telegram send failed, files are saved.")


if __name__ == "__main__":
    main()
