"""Tests for the /consequence list debug surface — formatter + engine
list query end-to-end (no Discord mocks; the slash command body is a
thin wrapper around format_consequence_list + consequence_list_for_command).

Run:
    cd /home/jordaneal/scripts && python3 test_consequence_command.py
"""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, '/home/jordaneal/scripts')

_tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_tmp.close()
TEST_DB = Path(_tmp.name)

import dnd_engine
dnd_engine.DB_PATH = TEST_DB
dnd_engine.log = lambda m: None

dnd_engine.db_init()

from dnd_engine import (
    npc_upsert,
    apply_consequence_proposals,
    consequence_list_for_command,
)
from discord_dnd_bot import format_consequence_list

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


CAMP = 9300


# ─── format_consequence_list: empty input ────────────────────────────────────
empty_msg = format_consequence_list([])
check_truthy('empty: has guidance text', '_No consequences' in empty_msg)


# ─── set up canonical NPCs ───────────────────────────────────────────────────
reginald = npc_upsert(CAMP, 'Reginald the Innkeeper', role='innkeeper')
lira     = npc_upsert(CAMP, 'Lira', role='ranger')
thorne   = npc_upsert(CAMP, 'Thorne', role='fence')


# ─── apply proposals (light integration: capture → list) ─────────────────────
proposals = [
    {'target': 'Reginald the Innkeeper', 'kind': 'threat',
     'severity': 2, 'summary': 'player threatened to torch the inn'},
    {'target': 'Lira', 'kind': 'mercy',
     'severity': 3, 'summary': 'player spared her at the bridge'},
    {'target': 'Thorne', 'kind': 'promise',
     'severity': 1, 'summary': 'player promised to deliver the package'},
]
result = apply_consequence_proposals(CAMP, proposals,
                                      source='player', current_turn=5)
check('apply: 3 inserted', result['inserted'], 3)
check('apply: 0 rejected', result['rejected'], 0)


# ─── consequence_list_for_command: full + filtered ──────────────────────────
all_rows = consequence_list_for_command(CAMP)
check('list: 3 rows', len(all_rows), 3)

just_lira = consequence_list_for_command(CAMP, npc_canonical='Lira')
check('list filtered to lira: 1 row', len(just_lira), 1)
check('list filtered: matches lira', just_lira[0]['canonical_name'], 'Lira')

no_match = consequence_list_for_command(CAMP, npc_canonical='Garrick')
check('list filter no match: 0 rows', len(no_match), 0)


# ─── format_consequence_list: full output ────────────────────────────────────
formatted = format_consequence_list(all_rows)
check_truthy('format: includes Reginald',  'Reginald the Innkeeper' in formatted)
check_truthy('format: includes Lira',      'Lira' in formatted)
check_truthy('format: includes Thorne',    'Thorne' in formatted)
check_truthy('format: shows kind threat',  'threat' in formatted)
check_truthy('format: shows kind mercy',   'mercy' in formatted)
check_truthy('format: shows kind promise', 'promise' in formatted)
check_truthy('format: shows turn tag',     'T5' in formatted)
check_truthy('format: shows sources',      '[player]' in formatted)
check_truthy('format: shows status active', 'active' in formatted)
check_truthy('format: shows surface count', 'surf 0' in formatted)
check_truthy('format: shows summary line',
              'player threatened to torch the inn' in formatted)
check_truthy('format: header counts',
              '3 active · 0 promoted' in formatted)
check_truthy('format: NPC name in bold',   '**Lira**' in formatted)
check_truthy('format: status in backticks', '`active`' in formatted)


# ─── format_consequence_list: with promoted row in mix ──────────────────────
# Promote Reginald's threat by hand for the formatter test.
import sqlite3
conn = sqlite3.connect(TEST_DB)
conn.execute("UPDATE dnd_consequences SET status='promoted', "
             "promoted_at=? WHERE npc_id=? AND kind='threat'",
             ('2026-05-03T00:00:00', reginald))
conn.commit()
conn.close()

mixed = consequence_list_for_command(CAMP)
formatted_mixed = format_consequence_list(mixed)
check_truthy('mixed: shows promoted',  'promoted' in formatted_mixed)
check_truthy('mixed: counts split',    '2 active · 1 promoted' in formatted_mixed)
check_truthy('mixed: promoted in backticks', '`promoted`' in formatted_mixed)


# ─── format_consequence_list: truncation guard for long input ───────────────
# Build a synthetic large list of 50 fake rows that all want to render.
big_list = []
for i in range(50):
    big_list.append({
        'first_seen_turn':   i,
        'kind':              'threat',
        'canonical_name':    f'NPC{i:02d} the Whatever Of Some Long Place',
        'severity':          2,
        'status':            'active',
        'sources':           'player',
        'surface_count':     i,
        'distinct_surface_turns': 1,
        'summary':           ('long summary about something specific ' * 4)[:110],
    })
big_format = format_consequence_list(big_list)
check_truthy('truncation: produced under 2000 chars', len(big_format) <= 1980)
check_truthy('truncation: has truncation note', 'truncated' in big_format)


# ─── final report ────────────────────────────────────────────────────────────
print(f"PASS: {PASS}  FAIL: {FAIL}")
if FAIL:
    print("\nFailures:")
    for f in FAILURES:
        print(f)

try:
    os.unlink(TEST_DB)
except OSError:
    pass

sys.exit(0 if FAIL == 0 else 1)
