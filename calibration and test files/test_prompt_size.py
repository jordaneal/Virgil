"""S24 — per-turn prompt size telemetry.

Verifies that dm_respond emits a prompt_size: log line with sensible byte
counts for each major section after build_dm_context returns.

Log shape:
    prompt_size: campaign={N} system={chars} retrieval={chars} party={chars}
                 scene={chars} directives={chars} total={chars}

'system' = build_dm_context output before skeleton/transition prepend.
'total'  = final prompt size after all prepends.
Section sizes come from the input variables feeding each prompt block.

The test uses a real temp DB + synthetic campaign/scene state. The LLM
route() call is monkey-patched to return a fixed string so no network call
is needed. The prompt_size log fires before route(), so even a mocked
error-returning route would not prevent it.

Run: python3 test_prompt_size.py
"""

import os
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, '/home/jordaneal/scripts')

# ── Temp DB setup (must happen before db_init) ──

_tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_tmp.close()
TEST_DB = Path(_tmp.name)

import dnd_engine
dnd_engine.DB_PATH = TEST_DB

# Capture logs; suppress noisy chroma/init lines
captured = []
_orig_log = dnd_engine.log


def _capture(msg):
    captured.append(msg)


dnd_engine.log = _capture

# Mock the LLM route so no network call is made
import cloud_router as _router
_orig_route = dnd_engine.route
dnd_engine.route = lambda messages, task_type, system_prompt: ("The tavern is quiet.", "mock")

dnd_engine.db_init()

from dnd_engine import (
    create_campaign, bind_character,
    init_scene_state, get_active_campaign, get_characters,
    dm_respond,
)

# ── Harness ──

PASS = 0
FAIL = 0
FAILURES = []


def check(label, got, want):
    global PASS, FAIL
    if got == want:
        PASS += 1
    else:
        FAIL += 1
        FAILURES.append(f"  {label}: got={got!r} want={want!r}")


def check_truthy(label, got):
    global PASS, FAIL
    if got:
        PASS += 1
    else:
        FAIL += 1
        FAILURES.append(f"  {label}: expected truthy, got={got!r}")


def prompt_size_lines():
    return [m for m in captured if 'prompt_size:' in m]


# ──────────────────────────────────────────────────────────────────────────────
# Setup: campaign + scene state + character
# ──────────────────────────────────────────────────────────────────────────────

GUILD = 'guild-prompt-size-test'
camp_id = create_campaign(GUILD, 'Prompt Size Test Campaign')
init_scene_state(camp_id)

# Update scene with real values so scene_chars > 0. Ship 2 (S39) shrank the
# LLM-writable scene_state surface to last_player_action only (the other
# four-property fields were §76 deletions). Setting last_player_action is
# sufficient to drive scene_chars > 0 for the assertion below.
import sqlite3

conn = sqlite3.connect(TEST_DB)
conn.execute(
    "UPDATE dnd_scene_state SET last_player_action=? WHERE campaign_id=?",
    ('I look around the room.', camp_id)
)
conn.commit()
conn.close()

bind_character(camp_id, '111111111111111111', 'Donovan Ruby',
               race='Dwarf', char_class='Rogue', level=1)

campaign = get_active_campaign(GUILD)
characters = get_characters(camp_id)

check_truthy('setup: campaign found', campaign is not None)
check_truthy('setup: characters present', len(characters) > 0)

# ──────────────────────────────────────────────────────────────────────────────
# Run dm_respond and capture prompt_size: log line
# ──────────────────────────────────────────────────────────────────────────────

captured.clear()
dm_respond(campaign, characters, 'I look around the tavern for trouble.')

ps_lines = prompt_size_lines()

# ── Assertion 1: exactly one prompt_size line emitted per turn ──
check('prompt_size: exactly one line emitted', len(ps_lines), 1)

if not ps_lines:
    print("\nFATAL: no prompt_size line found — remaining assertions skipped")
    print(f"\n{PASS} passed, {FAIL} failed")
    try:
        os.unlink(TEST_DB)
    except OSError:
        pass
    sys.exit(1)

line = ps_lines[0]

# ── Assertion 2: all expected keys present ──
for key in ('system=', 'retrieval=', 'party=', 'scene=', 'directives=', 'total='):
    check_truthy(f'prompt_size: key {key!r} present', key in line)

# ── Parse all integer values from the log line ──
# Format: "prompt_size: campaign=N system=N retrieval=N party=N scene=N directives=N total=N"
vals = {}
for m in re.finditer(r'(\w+)=(\d+)', line):
    vals[m.group(1)] = int(m.group(2))

required_keys = ('campaign', 'system', 'retrieval', 'party', 'scene', 'directives', 'total')
for k in required_keys:
    check_truthy(f'prompt_size: {k} parseable as int', k in vals)

# ── Assertion 3: system > 0 (build_dm_context always returns non-empty) ──
check_truthy('prompt_size: system > 0', vals.get('system', 0) > 0)

# ── Assertion 4: total >= system (prepends can only grow the prompt) ──
check_truthy('prompt_size: total >= system',
             vals.get('total', 0) >= vals.get('system', 0))

# ── Assertion 5: total > 0 ──
check_truthy('prompt_size: total > 0', vals.get('total', 0) > 0)

# ── Assertion 6: scene > 0 (last_player_action populated; Ship 2 S39
#    eliminated the other LLM-writable scene scalars via §76 deletion) ──
check_truthy('prompt_size: scene > 0 when scene state populated',
             vals.get('scene', 0) > 0)

# ── Assertion 7: campaign matches the actual campaign id ──
check('prompt_size: campaign id correct', vals.get('campaign'), camp_id)

# ── Assertion 8: second call also emits prompt_size (fires every turn) ──
captured.clear()
dm_respond(campaign, characters, 'I approach the barkeep.')
check('prompt_size: fires again on second turn', len(prompt_size_lines()), 1)

# ──────────────────────────────────────────────────────────────────────────────
# Cleanup
# ──────────────────────────────────────────────────────────────────────────────

dnd_engine.route = _orig_route
dnd_engine.log = _orig_log

try:
    os.unlink(TEST_DB)
except OSError:
    pass

print(f"\n{PASS} passed, {FAIL} failed")
if FAILURES:
    print("\nFAILURES:")
    for f in FAILURES:
        print(f)
    sys.exit(1)
sys.exit(0)
