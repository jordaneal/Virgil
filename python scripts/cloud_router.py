#!/usr/bin/env python3
"""
Virgil Cloud Router - Smart routing across free tier AI providers
with automatic failover, rate limit tracking, latency tracking,
failure cooldowns, and dynamic provider scoring.
Never sends personal/private data to cloud.
"""

import os
import time
import json
import datetime
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv('/home/jordaneal/scripts/.env')

USAGE_FILE = Path('/mnt/virgil_storage/digest/cloud_usage.json')

LATENCY_WINDOW = 10
FAILURE_THRESHOLD = 2
COOLDOWN_SECONDS = 600
FAILURE_PENALTY = 5.0

PROVIDERS = [
    {
        "name": "groq",
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "key": os.getenv('GROQ_API_KEY'),
        "model": "llama-3.3-70b-versatile",
        "daily_limit": 10000,
        "best_for": ["chat", "dnd", "fast", "general"]
    },
    {
        "name": "groq_heavy",
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "key": os.getenv('GROQ_API_KEY'),
        "model": "openai/gpt-oss-120b",
        "daily_limit": 10000,
        "best_for": ["reasoning", "complex", "tools"]
    },
    {
        "name": "cerebras",
        "url": "https://api.cerebras.ai/v1/chat/completions",
        "key": os.getenv('CEREBRAS_API_KEY'),
        "model": "qwen-3-235b-a22b-instruct-2507",
        "daily_limit": 250,
        "best_for": ["batch", "volume", "fallback"]
    },
    {
        "name": "mistral",
        "url": "https://api.mistral.ai/v1/chat/completions",
        "key": os.getenv('MISTRAL_API_KEY'),
        "model": "mistral-large-latest",
        "daily_limit": 99999,
        "best_for": ["code", "debugging"]
    },
    {
        "name": "gemini",
        "url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        "key": os.getenv('GEMINI_API_KEY'),
        "model": "gemini-2.5-flash",
        "daily_limit": 250,
        "best_for": ["digest", "analysis", "reasoning"]
    },
    {
        "name": "openrouter",
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "key": os.getenv('OPENROUTER_API_KEY'),
        "model": "openai/gpt-oss-120b:free",
        "daily_limit": 1000,
        "best_for": ["fallback"]
    },
    {
        "name": "local",
        "url": "http://localhost:11434/v1/chat/completions",
        "key": "ollama",
        "model": "qwen2.5:14b",
        "daily_limit": 999999,
        "best_for": ["private", "personal", "always"]
    }
]

PRIVATE_TASKS = ["calendar", "email", "memory", "personal", "private"]


def load_usage():
    today = datetime.date.today().isoformat()
    if USAGE_FILE.exists():
        try:
            data = json.loads(USAGE_FILE.read_text())
            if data.get("date") != today:
                return {"date": today, "counts": {}, "perf": data.get("perf", {})}
            return data
        except Exception:
            pass
    return {"date": today, "counts": {}, "perf": {}}


def save_usage(usage):
    USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    USAGE_FILE.write_text(json.dumps(usage, indent=2))


def increment_usage(provider_name):
    usage = load_usage()
    counts = usage.get("counts", {})
    counts[provider_name] = counts.get(provider_name, 0) + 1
    usage["counts"] = counts
    save_usage(usage)


def is_exhausted(provider):
    usage = load_usage()
    count = usage.get("counts", {}).get(provider["name"], 0)
    return count >= provider["daily_limit"]


def record_success(provider_name, latency):
    usage = load_usage()
    perf = usage.setdefault("perf", {})
    p = perf.setdefault(provider_name, {"latencies": [], "failures": 0, "cooldown_until": None})
    lats = p.get("latencies", [])
    lats.append(round(latency, 3))
    p["latencies"] = lats[-LATENCY_WINDOW:]
    p["failures"] = 0
    p["cooldown_until"] = None
    perf[provider_name] = p
    usage["perf"] = perf
    save_usage(usage)


def record_failure(provider_name):
    usage = load_usage()
    perf = usage.setdefault("perf", {})
    p = perf.setdefault(provider_name, {"latencies": [], "failures": 0, "cooldown_until": None})
    p["failures"] = p.get("failures", 0) + 1
    if p["failures"] >= FAILURE_THRESHOLD:
        p["cooldown_until"] = time.time() + COOLDOWN_SECONDS
        print(f"[router] {provider_name} on cooldown for {COOLDOWN_SECONDS}s after {p['failures']} failures")
    perf[provider_name] = p
    usage["perf"] = perf
    save_usage(usage)


def is_cooling_down(provider_name):
    usage = load_usage()
    p = usage.get("perf", {}).get(provider_name, {})
    cooldown_until = p.get("cooldown_until")
    if cooldown_until and time.time() < cooldown_until:
        remaining = int(cooldown_until - time.time())
        print(f"[router] {provider_name} cooling down ({remaining}s remaining)")
        return True
    return False


def provider_score(provider_name):
    usage = load_usage()
    p = usage.get("perf", {}).get(provider_name, {})
    lats = p.get("latencies", [])
    avg_lat = sum(lats) / len(lats) if lats else 3.0
    failures = p.get("failures", 0)
    return avg_lat + (failures * FAILURE_PENALTY)


def sort_by_score(provider_names):
    return sorted(provider_names, key=provider_score)


def call_provider(provider, messages, system_prompt=None, max_tokens=1000, task_type=None):
    msgs = []
    if system_prompt:
        msgs.append({"role": "system", "content": system_prompt})
    msgs.extend(messages)

    if provider["name"] == "local":
        try:
            t0 = time.time()
            payload = {"model": provider["model"], "messages": msgs, "stream": False}
            response = requests.post("http://localhost:11434/api/chat", json=payload, timeout=60)
            if response.status_code == 200:
                text = response.json()["message"]["content"]
                record_success("local", time.time() - t0)
                return True, text, 200
            record_failure("local")
            return False, f"Error {response.status_code}", response.status_code
        except Exception as e:
            record_failure("local")
            return False, str(e), 0

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {provider['key']}"
    }
    payload = {"model": provider["model"], "messages": msgs, "max_tokens": max_tokens}

    # Anti-repetition penalties for DnD narration. Targets the chronic
    # phrase-recycling observed in narration drift (Session 9-10): same
    # atmospheric couplets ("gentle whir", "soft glow", "cool leather")
    # showing up turn-over-turn. Penalties only apply to OpenAI-compatible
    # providers; Ollama /api/chat handles repetition via its own params.
    if task_type == "dnd":
        payload["frequency_penalty"] = 0.5
        payload["presence_penalty"] = 0.4
        print(f"[router] dnd penalties applied: freq=0.5 pres=0.4 provider={provider['name']}")

    try:
        t0 = time.time()
        response = requests.post(provider["url"], headers=headers, json=payload, timeout=30)

        if response.status_code == 429:
            usage = load_usage()
            usage["counts"][provider["name"]] = provider["daily_limit"]
            save_usage(usage)
            record_failure(provider["name"])
            return False, "Rate limited", 429

        if response.status_code in [401, 403]:
            record_failure(provider["name"])
            return False, f"Auth error: {response.status_code}", response.status_code

        if response.status_code == 200:
            data = response.json()
            text = data["choices"][0]["message"]["content"]
            finish_reason = data["choices"][0].get("finish_reason", "unknown")
            prompt_chars = sum(len(m.get("content") or "") for m in msgs)
            print(f"cloud_router_finish_reason: provider={provider['name']} "
                  f"task={task_type} finish_reason={finish_reason} "
                  f"prompt_chars={prompt_chars} response_chars={len(text or '')}")
            latency = time.time() - t0
            increment_usage(provider["name"])
            record_success(provider["name"], latency)
            return True, text, 200

        record_failure(provider["name"])
        return False, f"Error {response.status_code}", response.status_code

    except Exception as e:
        record_failure(provider["name"])
        return False, str(e), 0


def route(messages, task_type="general", system_prompt=None, force_local=False):
    """
    Route to best available provider. Returns (response_text, provider_name).
    Static lists define eligibility per task type.
    Dynamic scoring sorts within the eligible pool.
    """
    # DnD narration gets a larger budget: reasoning tokens on Groq count against
    # the same max_tokens window as output tokens, and narration regularly hits
    # 1000-token truncation (Bug 2, S25 #3). All other task types keep the 1000
    # default — bumping across the board would just burn tokens on extraction /
    # advisory / chat calls that don't need the headroom.
    max_tokens = 3000 if task_type == "dnd" else 1000

    if force_local or task_type in PRIVATE_TASKS:
        provider = next(p for p in PROVIDERS if p["name"] == "local")
        success, text, code = call_provider(provider, messages, system_prompt, task_type=task_type)
        return (text if success else "Error: local model unavailable"), "local"

    if task_type == "dnd":
        # DnD prefers gpt-oss-120b (groq_heavy) for stronger negative-instruction
        # following — Llama-3.3-70b ignored HARD STOP rules + sampling penalties
        # in Session 10 testing. groq stays as fallback.
        candidates = ["groq_heavy", "groq", "cerebras", "openrouter", "local"]
    elif task_type in ["fast", "chat", "general"]:
        candidates = ["groq", "cerebras", "openrouter", "local"]
    elif task_type == "advisory":
        # Track 6 #3 — OOC advisory lane (#dm-aside). Player Q&A about scene,
        # inventory, options. Factual reference, not narration — skip the DnD
        # anti-repetition penalties (those target atmospheric drift, not Q&A).
        # Same provider pool as chat/general.
        candidates = ["groq", "cerebras", "openrouter", "local"]
    elif task_type in ["reasoning", "complex", "agentic"]:
        candidates = ["groq_heavy", "groq", "cerebras", "local"]
    elif task_type in ["code", "debugging"]:
        candidates = ["mistral", "groq_heavy", "groq", "local"]
    elif task_type in ["digest", "analysis"]:
        candidates = ["gemini", "groq_heavy", "groq", "local"]
    elif task_type == "extraction":
        # Bounded structured-output tasks (fact extraction, mechanical hints).
        # Cerebras qwen-3-235b is fast + has plenty of RPD for low-volume use.
        # groq llama-3.3-70b as fallback. Skip groq_heavy — reserve for DnD.
        candidates = ["cerebras", "groq", "local"]
    else:
        candidates = ["groq", "cerebras", "gemini", "openrouter", "local"]

    # Routing policy: DnD uses scoped priority override (deterministic candidate
    # order; latency irrelevant when instruction-following is the constraint).
    # All other tasks use score-sort (reorder by recent latency + failure cost).
    # Reason code is logged so the router decision is auditable from journalctl.
    if task_type == "dnd":
        ordered = list(candidates)
        routing_reason = "DND_PRIORITY_OVERRIDE"
    else:
        non_local = [c for c in candidates if c != "local"]
        ordered = sort_by_score(non_local)
        if "local" in candidates:
            ordered.append("local")
        routing_reason = "SCORE_SORT"

    print(f"[router] routing={routing_reason} order={ordered}")

    for provider_name in ordered:
        provider = next((p for p in PROVIDERS if p["name"] == provider_name), None)
        if not provider:
            continue
        if is_exhausted(provider):
            print(f"[router] {provider_name} exhausted, skipping...")
            continue
        if provider_name != "local" and is_cooling_down(provider_name):
            continue

        print(f"[router] Trying {provider_name} (reason={routing_reason}, score={provider_score(provider_name):.2f})...")
        success, text, code = call_provider(provider, messages, system_prompt,
                                             max_tokens=max_tokens, task_type=task_type)

        if success:
            print(f"[router] Success via {provider_name}")
            return text, provider_name

        print(f"[router] {provider_name} failed ({code}), trying next...")

    return "All providers exhausted or unavailable.", "none"


def get_usage_report():
    usage = load_usage()
    counts = usage.get("counts", {})
    perf = usage.get("perf", {})
    lines = [f"📊 Cloud API Usage ({usage['date']})"]

    for provider in PROVIDERS:
        name = provider["name"]
        if name == "local":
            continue
        count = counts.get(name, 0)
        limit = provider["daily_limit"]
        pct = int(count / limit * 100) if limit < 99999 else 0
        bar = "█" * (pct // 10) + "░" * (10 - pct // 10)

        p = perf.get(name, {})
        lats = p.get("latencies", [])
        avg_lat = f"{sum(lats)/len(lats):.1f}s" if lats else "n/a"
        failures = p.get("failures", 0)
        cooling = " ❄️" if is_cooling_down(name) else ""
        fail_str = f" ⚠️{failures}f" if failures > 0 else ""

        lines.append(f"{name:12} {bar} {count}/{limit}  {avg_lat}{fail_str}{cooling}")

    return "\n".join(lines)


if __name__ == "__main__":
    print("Testing cloud router...\n")
    test_messages = [{"role": "user", "content": "Say 'OK' and nothing else."}]
    for provider in PROVIDERS:
        if provider["name"] == "local":
            continue
        print(f"Testing {provider['name']}...", end=" ", flush=True)
        success, text, code = call_provider(provider, test_messages)
        status = "✅" if success else f"❌ ({code})"
        print(f"{status} {text[:50] if success else text}")
    print("\n" + get_usage_report())
