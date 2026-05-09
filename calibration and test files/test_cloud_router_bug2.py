"""S30 Ship 1 — Bug 2 tests: max_tokens=3000 on DnD path, finish_reason log shape.

Tests:
  1. DnD task → max_tokens >= 3000 passed to call_provider
  2. Non-DnD task (extraction) → max_tokens stays at 1000
  3. finish_reason log line contains all four named fields on success
  4. finish_reason log line carries correct provider/task/finish_reason values
  5. prompt_chars computed correctly from messages list
  6. response_chars correct for normal response

No actual network calls — mock at the requests.post boundary.

Run: python3 test_cloud_router_bug2.py
"""

import sys
import types
import json
import io

sys.path.insert(0, '/home/jordaneal/scripts')

# ── stub dotenv / requests before importing cloud_router ──
from unittest.mock import patch, MagicMock

PASS = 0
FAIL = 0
FAILURES = []


def check(label, got, want):
    global PASS, FAIL
    if got == want:
        PASS += 1
        print(f"  PASS  {label}")
    else:
        FAIL += 1
        FAILURES.append(f"  {label}: got={got!r} want={want!r}")
        print(f"  FAIL  {label}: got={got!r} want={want!r}")


def check_true(label, cond):
    check(label, bool(cond), True)


def check_in(label, substring, text):
    if substring in text:
        global PASS
        PASS += 1
        print(f"  PASS  {label}")
    else:
        global FAIL
        FAIL += 1
        FAILURES.append(f"  {label}: {substring!r} not in {text!r}")
        print(f"  FAIL  {label}: {substring!r} not in output")


def _make_groq_response(content="narration text", finish_reason="stop"):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "choices": [{"message": {"content": content}, "finish_reason": finish_reason}]
    }
    return resp


def _make_length_response(content="cut mid"):
    return _make_groq_response(content=content, finish_reason="length")


# ─────────────────────────────────────────────────────────
# Test 1+2: max_tokens value per task_type
# ─────────────────────────────────────────────────────────
print("\n── max_tokens per task_type ──")

captured_max_tokens = []

def _mock_post_capture_max_tokens(url, headers, json, timeout):
    captured_max_tokens.append(json.get("max_tokens"))
    return _make_groq_response()

import cloud_router

with patch("cloud_router.requests.post", side_effect=_mock_post_capture_max_tokens):
    with patch("cloud_router.is_exhausted", return_value=False):
        with patch("cloud_router.is_cooling_down", return_value=False):
            with patch("cloud_router.increment_usage"):
                with patch("cloud_router.record_success"):
                    with patch("cloud_router.load_usage", return_value={"date": "2026-05-09", "counts": {}, "perf": {}}):
                        with patch("cloud_router.save_usage"):
                            captured_max_tokens.clear()
                            cloud_router.route(
                                messages=[{"role": "user", "content": "attack the goblin"}],
                                task_type="dnd",
                            )
                            check("dnd task max_tokens >= 3000",
                                  captured_max_tokens[0] >= 3000, True)
                            check("dnd task max_tokens == 3000",
                                  captured_max_tokens[0], 3000)

                            captured_max_tokens.clear()
                            cloud_router.route(
                                messages=[{"role": "user", "content": "extract facts"}],
                                task_type="extraction",
                            )
                            check("extraction task max_tokens == 1000",
                                  captured_max_tokens[0], 1000)


# ─────────────────────────────────────────────────────────
# Test 3+4+5+6: finish_reason log line shape
# ─────────────────────────────────────────────────────────
print("\n── finish_reason log shape ──")

import io
import contextlib

def _run_call_provider_capture_stdout(provider, messages, system_prompt=None,
                                      max_tokens=1000, task_type=None,
                                      finish_reason="stop", content="hello"):
    """Call call_provider with a mocked requests.post, capture stdout."""
    buf = io.StringIO()
    with patch("cloud_router.requests.post",
               return_value=_make_groq_response(content=content, finish_reason=finish_reason)):
        with patch("cloud_router.increment_usage"):
            with patch("cloud_router.record_success"):
                with contextlib.redirect_stdout(buf):
                    cloud_router.call_provider(
                        provider,
                        messages,
                        system_prompt=system_prompt,
                        max_tokens=max_tokens,
                        task_type=task_type,
                    )
    return buf.getvalue()


_test_provider = {
    "name": "groq_heavy",
    "url": "https://api.groq.com/openai/v1/chat/completions",
    "key": "fake-key",
    "model": "openai/gpt-oss-120b",
    "daily_limit": 10000,
}

_test_msgs = [{"role": "user", "content": "attack the goblin"}]

output = _run_call_provider_capture_stdout(
    _test_provider, _test_msgs, task_type="dnd", finish_reason="stop", content="narration here"
)

check_in("finish_reason log contains 'cloud_router_finish_reason'",
         "cloud_router_finish_reason", output)
check_in("finish_reason log contains 'provider='", "provider=", output)
check_in("finish_reason log contains 'task='", "task=", output)
check_in("finish_reason log contains 'finish_reason='", "finish_reason=", output)
check_in("finish_reason log contains 'prompt_chars='", "prompt_chars=", output)
check_in("finish_reason log contains 'response_chars='", "response_chars=", output)
check_in("finish_reason log: provider name", "groq_heavy", output)
check_in("finish_reason log: task type", "dnd", output)
check_in("finish_reason log: stop", "stop", output)

output_length = _run_call_provider_capture_stdout(
    _test_provider, _test_msgs, task_type="dnd", finish_reason="length", content="cut mid"
)
check_in("finish_reason=length surfaces as 'length'", "length", output_length)

# prompt_chars correctness
_msg_with_system = [{"role": "system", "content": "sys prompt"}, {"role": "user", "content": "user text"}]
output_chars = _run_call_provider_capture_stdout(
    _test_provider, _msg_with_system, system_prompt=None, task_type="dnd",
    finish_reason="stop", content="resp"
)
# prompt_chars should be len("sys prompt") + len("user text") = 10 + 9 = 19
# (system_prompt=None so only the two messages count)
check_in("prompt_chars=19 in output (10+9)", "prompt_chars=19", output_chars)
check_in("response_chars=4 in output (len('resp'))", "response_chars=4", output_chars)

# ─────────────────────────────────────────────────────────
print(f"\n{'='*50}")
print(f"S30 Bug 2: {PASS} passed, {FAIL} failed")
if FAILURES:
    for f in FAILURES:
        print(f)
    sys.exit(1)
else:
    print("All tests passed.")
