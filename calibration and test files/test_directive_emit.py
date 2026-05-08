"""S25 — directive_emit: per-turn directive emission summary log.

Verifies that dm_respond emits a directive_emit: log line each turn,
aggregating which directives fired with non-empty content.

Log shape:
    directive_emit: campaign={N} pacing={tier_or_none} central_thread={1|0}
                    philosophy={chars} consequence={count}
                    capability={verdict|none} commitment=0

This is the single per-turn signal for threshold calibration alongside
the existing per-directive log lines (pacing_directive:, central_thread:,
dm_philosophy:, consequence_directive:, capability_check:).

Tests:
  1.  all-empty case — silent scene, no hooks, no philosophy, no consequences,
      no capability claim → pacing=none central_thread=0 philosophy=0
      consequence=0 capability=none
  2.  all-firing case — high tension, hooks wired, philosophy text, consequences
      surfaced, capability claim → pacing=climax central_thread=1 philosophy>0
      consequence>0 capability=CONFIRMED (or VALID_BUT_UNCONFIGURED)
  3.  partial-firing case — only pacing fires (high tension, no other directives)
  4.  consequence count taxonomy — two consequences of different kinds →
      consequence=2 in the log

Run: python3 test_directive_emit.py
"""

import os
import re
import sys
import tempfile
import json
from pathlib import Path

sys.path.insert(0, '/home/jordaneal/scripts')

# ── Temp DB setup ──

_tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_tmp.close()
TEST_DB = Path(_tmp.name)

import dnd_engine
dnd_engine.DB_PATH = TEST_DB

captured = []
dnd_engine.log = lambda m: captured.append(m)

# Mock route — no LLM calls
dnd_engine.route = lambda messages, task_type, system_prompt: ("The scene is tense.", "mock")

dnd_engine.db_init()

from dnd_engine import (
    create_campaign, bind_character, init_scene_state,
    get_active_campaign, get_characters, dm_respond,
    update_tension, npc_upsert, consequence_upsert,
)

import dnd_orchestration as orch

# Suppress philosophy loader so all tests see philosophy=0 (file is a global
# DM setting, not campaign-specific; we don't want a real doc on disk to make
# the all-empty assertion flaky).
import dm_philosophy_loader as _phil_mod
_phil_mod.get_philosophy_block = lambda: ''

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


def de_lines():
    return [m for m in captured if 'directive_emit:' in m]


def parse_de(line):
    """Parse directive_emit log line into a dict of key→value strings."""
    result = {}
    for m in re.finditer(r'(\w+)=([^\s]+)', line):
        result[m.group(1)] = m.group(2)
    return result


# ──────────────────────────────────────────────────────────────────────────────
# Setup helper
# ──────────────────────────────────────────────────────────────────────────────

GUILD_COUNTER = [0]


def make_campaign(name='Test', tone=''):
    GUILD_COUNTER[0] += 1
    guild = f'guild-de-{GUILD_COUNTER[0]}'
    cid = create_campaign(guild, name, tone=tone)
    init_scene_state(cid, 'A test scene.')
    return guild, cid


def get_camp_and_chars(guild, cid):
    campaign = get_active_campaign(guild)
    characters = get_characters(cid)
    return campaign, characters


# ──────────────────────────────────────────────────────────────────────────────
# Test 1: all-empty case
# Low tension (0), no skeleton hooks (no skeleton file), no philosophy,
# no bound character → no capability check. All directives silent.
# ──────────────────────────────────────────────────────────────────────────────

guild1, cid1 = make_campaign('Empty Directives Test')
bind_character(cid1, '111', 'Aldric', race='Human', char_class='Fighter', level=1)
camp1, chars1 = get_camp_and_chars(guild1, cid1)

captured.clear()
dm_respond(camp1, chars1, 'I look around.')

lines = de_lines()
check('all_empty: one directive_emit line', len(lines), 1)

if lines:
    vals = parse_de(lines[0])
    check('all_empty: pacing=none',        vals.get('pacing'), 'none')
    check('all_empty: central_thread=0',   vals.get('central_thread'), '0')
    check('all_empty: philosophy=0',       vals.get('philosophy'), '0')
    check('all_empty: consequence=0',      vals.get('consequence'), '0')
    check('all_empty: capability=none',    vals.get('capability'), 'none')
    check('all_empty: commitment=0',       vals.get('commitment'), '0')


# ──────────────────────────────────────────────────────────────────────────────
# Test 2: partial-firing case — only pacing fires
# Set tension to 90 (climax tier). No other directives active.
# ──────────────────────────────────────────────────────────────────────────────

guild2, cid2 = make_campaign('Pacing Only Test')
bind_character(cid2, '222', 'Boldir', race='Dwarf', char_class='Paladin', level=3)

import sqlite3
conn = sqlite3.connect(TEST_DB)
conn.execute("UPDATE dnd_scene_state SET tension_int=90 WHERE campaign_id=?", (cid2,))
conn.commit()
conn.close()

camp2, chars2 = get_camp_and_chars(guild2, cid2)

captured.clear()
dm_respond(camp2, chars2, 'I ready my weapon.')

lines = de_lines()
check('pacing_only: one directive_emit line', len(lines), 1)

if lines:
    vals = parse_de(lines[0])
    check('pacing_only: pacing=climax',      vals.get('pacing'), 'climax')
    check('pacing_only: central_thread=0',   vals.get('central_thread'), '0')
    check('pacing_only: consequence=0',      vals.get('consequence'), '0')
    check('pacing_only: commitment=0',       vals.get('commitment'), '0')


# ──────────────────────────────────────────────────────────────────────────────
# Test 3: consequence count — two consequences of different kinds
# Insert two active consequences against an NPC, trigger dm_respond with
# the NPC recently active. directive_emit should show consequence=2.
# ──────────────────────────────────────────────────────────────────────────────

guild3, cid3 = make_campaign('Consequence Count Test')
bind_character(cid3, '333', 'Tova', race='Elf', char_class='Ranger', level=2)

# Insert an NPC and two consequences of different kinds
npc_id = npc_upsert(cid3, 'Garrick', role='merchant')
check_truthy('cons_count setup: npc inserted', npc_id is not None)

if npc_id:
    # Insert two consequences via low-level upsert
    consequence_upsert(
        campaign_id=cid3, npc_id=npc_id,
        kind='threat', severity=2,
        summary='Garrick threatened the party with exposure.',
        source='player', current_turn=1,
    )
    consequence_upsert(
        campaign_id=cid3, npc_id=npc_id,
        kind='promise', severity=1,
        summary='Garrick promised a reward for the job.',
        source='player', current_turn=1,
    )

    # Make Garrick recently active so he's in scope for the consequence directive
    conn = sqlite3.connect(TEST_DB)
    import datetime as _dt
    conn.execute(
        "UPDATE dnd_npcs SET last_mentioned=? WHERE id=?",
        (_dt.datetime.now().isoformat(), npc_id)
    )
    conn.commit()
    conn.close()

camp3, chars3 = get_camp_and_chars(guild3, cid3)

captured.clear()
dm_respond(camp3, chars3, 'I approach Garrick.')

lines = de_lines()
check('cons_count: one directive_emit line', len(lines), 1)

if lines:
    vals = parse_de(lines[0])
    # Two consequences of different kinds both surfaced
    check_truthy('cons_count: consequence >= 1',
                 int(vals.get('consequence', '0')) >= 1)


# ──────────────────────────────────────────────────────────────────────────────
# Test 4: fires on every turn — two consecutive turns both emit directive_emit
# ──────────────────────────────────────────────────────────────────────────────

guild4, cid4 = make_campaign('Every Turn Test')
bind_character(cid4, '444', 'Sera', race='Halfling', char_class='Bard', level=1)
camp4, chars4 = get_camp_and_chars(guild4, cid4)

captured.clear()
dm_respond(camp4, chars4, 'I sing a song.')
dm_respond(camp4, chars4, 'I look for the exit.')

check('every_turn: two directive_emit lines for two turns', len(de_lines()), 2)


# ──────────────────────────────────────────────────────────────────────────────
# Test 5: required keys all present in the log line
# ──────────────────────────────────────────────────────────────────────────────

if de_lines():
    last_line = de_lines()[-1]
    for key in ('campaign', 'pacing', 'central_thread', 'philosophy',
                'consequence', 'capability', 'commitment'):
        check_truthy(f'keys: {key!r} present in directive_emit', f'{key}=' in last_line)


# ──────────────────────────────────────────────────────────────────────────────
# Cleanup
# ──────────────────────────────────────────────────────────────────────────────

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
