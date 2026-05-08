"""Deterministic unit tests for the consequence ledger (Session 16).

Covers: schema migration, consequence_upsert (insert + update + reject),
get_active_consequences (filter + ordering + cross-campaign), surface
emit telemetry, promotion thresholds + distribution check + age check,
notable_traits/description trait append, idempotency, list-for-command
debug query, _resolve_npc_id_for_consequence canonical+alias lookup,
apply_consequence_proposals end-to-end, turn counter helpers.

No network. Tempfile DB only.

Run:
    cd /home/jordaneal/scripts && python3 test_dnd_consequences.py
"""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, '/home/jordaneal/scripts')

_tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_tmp.close()
TEST_DB = Path(_tmp.name)

import dnd_engine                 # noqa: E402
dnd_engine.DB_PATH = TEST_DB
dnd_engine.log = lambda m: None

dnd_engine.db_init()

from dnd_engine import (           # noqa: E402
    npc_upsert, npc_set_aliases,
    consequence_upsert, get_active_consequences,
    consequence_emit_surface, maybe_promote_consequences,
    consequence_list_for_command, apply_consequence_proposals,
    _resolve_npc_id_for_consequence, _merge_sources,
    get_turn_counter, increment_turn_counter,
    CONSEQUENCE_KINDS, CONSEQUENCE_SEVERITIES, CONSEQUENCE_SOURCES,
    CONSEQUENCE_SUMMARY_MAX,
    PROMOTION_SURFACE_COUNT, PROMOTION_DISTINCT_TURNS, PROMOTION_AGE_TURNS,
)

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

def check_in(label, got, container):
    global PASS, FAIL
    if got in container:
        PASS += 1
    else:
        FAIL += 1
        FAILURES.append(f"  {label}: {got!r} not in {container!r}")


CAMP = 9100
OTHER_CAMP = 9101


# ─── module constants ────────────────────────────────────────────────────────
check('kinds locked count',    len(CONSEQUENCE_KINDS), 6)
check_in('kind: threat',       'threat', CONSEQUENCE_KINDS)
check_in('kind: mercy',        'mercy', CONSEQUENCE_KINDS)
check_in('kind: cruelty',      'cruelty', CONSEQUENCE_KINDS)
check_in('kind: betrayal',     'betrayal', CONSEQUENCE_KINDS)
check_in('kind: promise',      'promise', CONSEQUENCE_KINDS)
check_in('kind: alliance',     'alliance', CONSEQUENCE_KINDS)
check('severities',            CONSEQUENCE_SEVERITIES, frozenset({1, 2, 3}))
check('sources',               CONSEQUENCE_SOURCES, frozenset({'player', 'dm'}))
check('summary cap',           CONSEQUENCE_SUMMARY_MAX, 120)
check('promotion surf threshold',  PROMOTION_SURFACE_COUNT, 3)
check('promotion distinct turns',   PROMOTION_DISTINCT_TURNS, 2)
check('promotion age turns',        PROMOTION_AGE_TURNS, 10)


# ─── _merge_sources ──────────────────────────────────────────────────────────
check('merge: empty + player', _merge_sources('', 'player'), 'player')
check('merge: existing + new', _merge_sources('player', 'dm'), 'dm,player')
check('merge: idempotent',     _merge_sources('dm,player', 'player'), 'dm,player')
check('merge: sorted',         _merge_sources('player', 'dm'), 'dm,player')


# ─── turn counter ────────────────────────────────────────────────────────────
check('turn counter start (no scene)', get_turn_counter(CAMP), 0)
check('increment to 1', increment_turn_counter(CAMP), 1)
check('increment to 2', increment_turn_counter(CAMP), 2)
check('read after increments', get_turn_counter(CAMP), 2)
check('other campaign isolated', get_turn_counter(OTHER_CAMP), 0)
check('other increment', increment_turn_counter(OTHER_CAMP), 1)
check('original unaffected', get_turn_counter(CAMP), 2)


# ─── set up NPCs ─────────────────────────────────────────────────────────────
reginald_id = npc_upsert(CAMP, 'Reginald the Innkeeper', role='innkeeper')
lira_id     = npc_upsert(CAMP, 'Lira', role='ranger')
thorne_id   = npc_upsert(CAMP, 'Thorne', role='fence')
kael_id     = npc_upsert(CAMP, 'Kael', role='captain')
# NPC in a different campaign for isolation testing
other_npc   = npc_upsert(OTHER_CAMP, 'Garrick', role='smith')

check_truthy('reginald inserted', reginald_id)
check_truthy('lira inserted', lira_id)
check_truthy('thorne inserted', thorne_id)
check_truthy('kael inserted', kael_id)


# ─── consequence_upsert: insert path ─────────────────────────────────────────
r = consequence_upsert(CAMP, reginald_id, 'threat',
                        'player threatened to burn the inn down', 2,
                        'player', current_turn=5)
check('insert: status',         r['status'], 'inserted')
check_truthy('insert: id returned', r['id'])
reg_threat_id = r['id']

active = get_active_consequences(CAMP)
check('after insert: 1 active', len(active), 1)
check('insert: kind',           active[0]['kind'], 'threat')
check('insert: severity',       active[0]['severity'], 2)
check('insert: sources',        active[0]['sources'], 'player')
check('insert: summary',        active[0]['summary'],
      'player threatened to burn the inn down')
check('insert: first_seen_turn', active[0]['first_seen_turn'], 5)
check('insert: captured_turn',  active[0]['captured_turn'], 5)
check('insert: last_seen_turn', active[0]['last_seen_turn'], 5)
check('insert: surface_count',  active[0]['surface_count'], 0)
check('insert: distinct_surf_turns', active[0]['distinct_surface_turns'], 0)
check('insert: status active',  active[0]['status'], 'active')
check('insert: canonical_name', active[0]['canonical_name'],
      'Reginald the Innkeeper')


# ─── consequence_upsert: update path (last-write-wins) ───────────────────────
r2 = consequence_upsert(CAMP, reginald_id, 'threat',
                         'player threatened to set the cellar on fire', 1,
                         'dm', current_turn=8)
check('update: status',          r2['status'], 'updated')
check('update: same id',         r2['id'], reg_threat_id)

after_update = [c for c in get_active_consequences(CAMP)
                if c['id'] == reg_threat_id][0]
check('update: summary changed', after_update['summary'],
      'player threatened to set the cellar on fire')
check('update: severity MAX (kept higher)', after_update['severity'], 2)
check('update: sources merged', after_update['sources'], 'dm,player')
check('update: captured_turn advanced', after_update['captured_turn'], 8)
check('update: first_seen_turn IMMUTABLE', after_update['first_seen_turn'], 5)
check('update: last_seen_turn = max', after_update['last_seen_turn'], 8)


# ─── consequence_upsert: severity MAX (lower-then-higher) ────────────────────
r3 = consequence_upsert(CAMP, reginald_id, 'threat', 'still a threat', 3,
                         'player', current_turn=9)
check('update sev3: status', r3['status'], 'updated')
sev_check = [c for c in get_active_consequences(CAMP)
             if c['id'] == reg_threat_id][0]
check('severity rose to 3', sev_check['severity'], 3)

# Now lower severity comes in — MAX semantics keep 3.
r4 = consequence_upsert(CAMP, reginald_id, 'threat', 'low again', 1,
                         'dm', current_turn=10)
check('update lower sev: status', r4['status'], 'updated')
sev_kept = [c for c in get_active_consequences(CAMP)
            if c['id'] == reg_threat_id][0]
check('severity stays 3 (MAX)', sev_kept['severity'], 3)


# ─── consequence_upsert: validation rejects ──────────────────────────────────
bad = consequence_upsert(CAMP, lira_id, 'love', 'odd kind', 2,
                          'player', current_turn=5)
check('bad kind rejected', bad['status'], 'rejected_invalid')
check_truthy('bad kind reason', 'invalid_kind' in (bad['reason'] or ''))

bad_sev = consequence_upsert(CAMP, lira_id, 'mercy', 'sev oob', 5,
                              'player', current_turn=5)
check('bad severity rejected', bad_sev['status'], 'rejected_invalid')
check_truthy('bad sev reason', 'severity_out_of_range' in (bad_sev['reason'] or ''))

bad_src = consequence_upsert(CAMP, lira_id, 'mercy', 'odd source', 2,
                              'system', current_turn=5)
check('bad source rejected', bad_src['status'], 'rejected_invalid')

bad_summary_empty = consequence_upsert(CAMP, lira_id, 'mercy', '   ', 2,
                                        'player', current_turn=5)
check('empty summary rejected', bad_summary_empty['status'], 'rejected_invalid')
check('empty summary reason', bad_summary_empty['reason'], 'summary_empty')

long_summary = 'x' * 121
bad_long = consequence_upsert(CAMP, lira_id, 'mercy', long_summary, 2,
                               'player', current_turn=5)
check('long summary rejected', bad_long['status'], 'rejected_invalid')
check_truthy('long reason', 'summary_too_long' in (bad_long['reason'] or ''))

bad_npc = consequence_upsert(CAMP, 99999, 'mercy', 'no such npc', 2,
                              'player', current_turn=5)
check('npc not found rejected', bad_npc['status'], 'rejected_invalid')
check('npc not found reason', bad_npc['reason'], 'npc_not_found')


# ─── consequence_upsert: cross-kind, same NPC ────────────────────────────────
mercy_r = consequence_upsert(CAMP, reginald_id, 'mercy',
                              'player let him keep the till', 1,
                              'player', current_turn=6)
check('different kind: insert', mercy_r['status'], 'inserted')
all_active = get_active_consequences(CAMP)
check('reginald has 2 rows', sum(1 for c in all_active
                                  if c['npc_id'] == reginald_id), 2)


# ─── get_active_consequences: filter + ordering ──────────────────────────────
# Add consequences for two more NPCs.
consequence_upsert(CAMP, lira_id, 'betrayal', 'lira betrayed the party', 2,
                    'dm', current_turn=7)
consequence_upsert(CAMP, thorne_id, 'promise', 'promised to deliver', 1,
                    'player', current_turn=7)

all_a = get_active_consequences(CAMP)
check('total active count', len(all_a), 4)

filtered = get_active_consequences(CAMP, npc_ids=[lira_id, thorne_id])
check('filter: 2 npcs', len(filtered), 2)
filtered_kinds = sorted(c['kind'] for c in filtered)
check('filter: kinds', filtered_kinds, ['betrayal', 'promise'])

# Order: severity desc, then last_surfaced_turn desc (nulls last), then id.
# Nothing surfaced yet — all last_surfaced_turn are NULL.
# Reginald threat is sev 3; others are sev 1 or 2.
ordering = [(c['severity'], c['kind']) for c in all_a]
check('first row is highest severity', ordering[0][0], 3)


# ─── cross-campaign isolation ────────────────────────────────────────────────
other_active = get_active_consequences(OTHER_CAMP)
check('other campaign empty', len(other_active), 0)

consequence_upsert(OTHER_CAMP, other_npc, 'threat', 'across campaigns', 1,
                    'player', current_turn=2)
other_active2 = get_active_consequences(OTHER_CAMP)
check('other campaign 1 row', len(other_active2), 1)
camp1_count = len(get_active_consequences(CAMP))
check('campaign 1 untouched', camp1_count, 4)


# ─── consequence_emit_surface ────────────────────────────────────────────────
emit_ok = consequence_emit_surface(reg_threat_id, current_turn=12)
check('first surface emit', emit_ok, True)

after_surf = [c for c in get_active_consequences(CAMP)
              if c['id'] == reg_threat_id][0]
check('after surf: surface_count=1',         after_surf['surface_count'], 1)
check('after surf: distinct_turns=1',        after_surf['distinct_surface_turns'], 1)
check('after surf: last_surfaced_turn=12',   after_surf['last_surfaced_turn'], 12)
check('after surf: last_seen_turn=12',       after_surf['last_seen_turn'], 12)

# Same-turn re-emit: surface_count++ but distinct_surface_turns unchanged.
consequence_emit_surface(reg_threat_id, current_turn=12)
same_turn = [c for c in get_active_consequences(CAMP)
             if c['id'] == reg_threat_id][0]
check('same turn: surface_count=2',  same_turn['surface_count'], 2)
check('same turn: distinct stays 1', same_turn['distinct_surface_turns'], 1)

# Different-turn re-emit: both increment.
consequence_emit_surface(reg_threat_id, current_turn=15)
later = [c for c in get_active_consequences(CAMP)
         if c['id'] == reg_threat_id][0]
check('later turn: surface_count=3',  later['surface_count'], 3)
check('later turn: distinct=2',       later['distinct_surface_turns'], 2)
check('later turn: last_surf=15',     later['last_surfaced_turn'], 15)

# Bad id returns False, doesn't crash.
check('bad consequence id', consequence_emit_surface(99999, 1), False)


# ─── promotion thresholds ────────────────────────────────────────────────────
# reg_threat: surface_count=3, distinct_turns=2, age_turns=15-5=10. Eligible.
# Run promotion at current_turn=15.
promoted = maybe_promote_consequences(CAMP, current_turn=15)
check('promotion fires', promoted, 1)

after_promo = consequence_list_for_command(CAMP)
reg_after = [c for c in after_promo if c['id'] == reg_threat_id][0]
check('promoted: status', reg_after['status'], 'promoted')
check_truthy('promoted: timestamp set', reg_after['promoted_at'])

# Promoted rows excluded from active query.
active_after = get_active_consequences(CAMP)
check('promoted excluded from active',
      sum(1 for c in active_after if c['id'] == reg_threat_id), 0)

# Promotion appended to NPC description.
import sqlite3
conn = sqlite3.connect(TEST_DB)
desc = conn.execute("SELECT description FROM dnd_npcs WHERE id=?",
                     (reginald_id,)).fetchone()[0]
conn.close()
check_truthy('reginald desc has promoted prefix',
              '[promoted: threat]' in desc)


# ─── promotion: idempotency ─────────────────────────────────────────────────
promoted_again = maybe_promote_consequences(CAMP, current_turn=20)
check('promotion idempotent (no rows eligible after first)',
      promoted_again, 0)


# ─── promotion: distribution check (3 surfaces, 1 turn) ─────────────────────
# Lira betrayal: insert at turn=7. Surface 3 times all on turn=20.
# distinct_surface_turns=1 → should NOT promote at turn=25 (age 18, surfaces 3,
# but distinct only 1).
consequence_emit_surface([c for c in active_after if c['npc_id'] == lira_id
                          and c['kind'] == 'betrayal'][0]['id'], current_turn=20)
consequence_emit_surface([c for c in active_after if c['npc_id'] == lira_id
                          and c['kind'] == 'betrayal'][0]['id'], current_turn=20)
consequence_emit_surface([c for c in active_after if c['npc_id'] == lira_id
                          and c['kind'] == 'betrayal'][0]['id'], current_turn=20)
no_promote = maybe_promote_consequences(CAMP, current_turn=25)
check('distribution check blocks 1-turn-only', no_promote, 0)
lira_b = [c for c in get_active_consequences(CAMP)
          if c['npc_id'] == lira_id and c['kind'] == 'betrayal'][0]
check('lira betrayal still active',  lira_b['status'], 'active')
check('lira betrayal: surface 3',     lira_b['surface_count'], 3)
check('lira betrayal: distinct 1',    lira_b['distinct_surface_turns'], 1)


# ─── promotion: age check ────────────────────────────────────────────────────
# Thorne promise: insert at turn=7, surface 3 times on turn=8, 9, 10.
# At turn=12 (age=5) → not eligible (age < 10).
thorne_p = [c for c in get_active_consequences(CAMP)
            if c['npc_id'] == thorne_id][0]
consequence_emit_surface(thorne_p['id'], current_turn=8)
consequence_emit_surface(thorne_p['id'], current_turn=9)
consequence_emit_surface(thorne_p['id'], current_turn=10)
not_yet = maybe_promote_consequences(CAMP, current_turn=12)
check('age check blocks promotion', not_yet, 0)
# Now at turn=17 (age=10), eligible.
yes_now = maybe_promote_consequences(CAMP, current_turn=17)
check('age check passes when met', yes_now, 1)


# ─── consequence_upsert: rejects re-capture of promoted ──────────────────────
re_capture = consequence_upsert(CAMP, reginald_id, 'threat',
                                 'a fresh threat reading', 3,
                                 'player', current_turn=22)
check('promoted re-capture rejected', re_capture['status'], 'rejected_promoted')
check('promoted re-capture reason', re_capture['reason'], 'already_promoted')


# ─── consequence_list_for_command ────────────────────────────────────────────
all_camp = consequence_list_for_command(CAMP)
check_truthy('list returns rows', len(all_camp) >= 4)
# Ordered by first_seen_turn ASC.
turns = [c['first_seen_turn'] for c in all_camp]
check('list ordered by first_seen_turn ASC', turns, sorted(turns))

# Filter by canonical name.
filtered_list = consequence_list_for_command(CAMP, npc_canonical='Lira')
check('list filtered to lira', all(c['canonical_name'] == 'Lira'
                                    for c in filtered_list), True)
check('lira has at least 1 row',
      sum(1 for c in filtered_list) >= 1, True)


# ─── _resolve_npc_id_for_consequence ─────────────────────────────────────────
nid, reason = _resolve_npc_id_for_consequence(CAMP, 'Lira', pc_names=[])
check('resolve canonical', nid, lira_id)
check('resolve reason None', reason, None)

# Alias resolution.
npc_set_aliases(CAMP, lira_id, ['lira shadowfoot'])
nid2, _ = _resolve_npc_id_for_consequence(CAMP, 'Lira Shadowfoot', pc_names=[])
check('resolve via alias', nid2, lira_id)

unresolved_id, unresolved_reason = _resolve_npc_id_for_consequence(
    CAMP, 'NobodyHere', pc_names=[]
)
check('unresolved: id None', unresolved_id, None)
check('unresolved: reason', unresolved_reason, 'unresolved_target')

empty_id, empty_reason = _resolve_npc_id_for_consequence(
    CAMP, '', pc_names=[]
)
check('empty target: reason', empty_reason, 'unresolved_target')

# PC contamination guard.
pc_id, pc_reason = _resolve_npc_id_for_consequence(
    CAMP, 'Donovan Ruby', pc_names=['Donovan Ruby']
)
check('pc match: id None', pc_id, None)
check('pc match: reason', pc_reason, 'pc_match')


# ─── apply_consequence_proposals: end-to-end ─────────────────────────────────
proposals = [
    {'target': 'Kael', 'kind': 'cruelty', 'severity': 3,
     'summary': 'player cut him down before he surrendered'},
    {'target': 'NobodyHere', 'kind': 'threat', 'severity': 2,
     'summary': 'should be rejected — unresolved'},
    {'target': 'Kael', 'kind': 'invalid_kind', 'severity': 1,
     'summary': 'should be rejected — bad kind'},
    {'target': 'Kael', 'kind': 'mercy', 'severity': 7,
     'summary': 'should be rejected — sev OOB'},
]
result = apply_consequence_proposals(CAMP, proposals, source='player',
                                      current_turn=30)
check('apply: inserted', result['inserted'], 1)
check('apply: rejected', result['rejected'], 3)
check_truthy('apply: reasons',
              result['reasons'].get('unresolved_target') or
              result['reasons'].get('exception') or
              len(result['reasons']) > 0)


# ─── apply_consequence_proposals: empty / bad source ─────────────────────────
empty = apply_consequence_proposals(CAMP, [], 'player', current_turn=1)
check('empty proposals',  empty['inserted'], 0)

bad_src = apply_consequence_proposals(CAMP, [{'target': 'Kael',
                                               'kind': 'mercy',
                                               'severity': 1,
                                               'summary': 'x'}],
                                       'system', current_turn=1)
check('bad source: nothing written', bad_src['inserted'], 0)


# ─── apply_consequence_proposals: dual-pass merge ────────────────────────────
# Player pass writes; DM pass writes same kind+npc → sources merge to 'dm,player'
apply_consequence_proposals(
    CAMP, [{'target': 'Lira', 'kind': 'mercy', 'severity': 2,
             'summary': 'spared at the bridge'}],
    source='player', current_turn=40,
)
apply_consequence_proposals(
    CAMP, [{'target': 'Lira', 'kind': 'mercy', 'severity': 2,
             'summary': 'spared at the bridge'}],
    source='dm', current_turn=40,
)
lira_mercy = [c for c in get_active_consequences(CAMP)
              if c['npc_id'] == lira_id and c['kind'] == 'mercy'][0]
check('dual-pass merge: sources', lira_mercy['sources'], 'dm,player')


# ─── promotion: write to description is idempotent (no double-append) ───────
# Reginald already has [promoted: threat] in description from earlier.
# Run promotion again — even though no NEW rows are eligible, the existing
# promoted row should not double-append.
import sqlite3
conn = sqlite3.connect(TEST_DB)
desc_before = conn.execute("SELECT description FROM dnd_npcs WHERE id=?",
                            (reginald_id,)).fetchone()[0]
conn.close()
maybe_promote_consequences(CAMP, current_turn=100)
conn = sqlite3.connect(TEST_DB)
desc_after = conn.execute("SELECT description FROM dnd_npcs WHERE id=?",
                          (reginald_id,)).fetchone()[0]
conn.close()
check('description not double-appended', desc_before, desc_after)


# ─── _name_appears_in_text helper ────────────────────────────────────────────
from dnd_engine import _name_appears_in_text  # noqa: E402

check('helper: name in text',     _name_appears_in_text('Mira', 'Mira tends bar'), True)
check('helper: word boundary',    _name_appears_in_text('Mira', 'the miracle came'), False)
check('helper: case-insensitive', _name_appears_in_text('Mira', 'MIRA glares'), True)
check('helper: empty name',       _name_appears_in_text('', 'anything'), False)
check('helper: empty text',       _name_appears_in_text('Mira', ''), False)
check('helper: compound name',    _name_appears_in_text('Reginald the Innkeeper',
                                                          'You meet Reginald the Innkeeper at dawn.'), True)
check('helper: partial mismatch', _name_appears_in_text('Reginald the Innkeeper',
                                                          'Reginald nods.'), False)
check('helper: name with space inside text',
      _name_appears_in_text('Lira Shadowfoot', 'Behind you, Lira Shadowfoot vanishes.'), True)


# ─── consequence_race diagnostic ─────────────────────────────────────────────
# Tests use a fresh campaign id with NO NPCs (so all proposals reject as
# unresolved_target), capturing log emissions via a list-collector.

class _LogCapture:
    def __init__(self):
        self.lines = []
    def __call__(self, msg):
        self.lines.append(str(msg))

RACE_CAMP = 9200
_silent_log = dnd_engine.log  # the test-file's noop log; restore at end


# 1. Introduction-race: target unresolved AND in narration → race log fires.
log_cap = _LogCapture()
dnd_engine.log = log_cap
apply_consequence_proposals(
    RACE_CAMP,
    [{'target': 'Mira', 'kind': 'alliance', 'severity': 2,
      'summary': 'Mira swore to help'}],
    source='dm', current_turn=5,
    narration_text='You meet Mira at the well; she nods her thanks.',
)
race_lines = [ln for ln in log_cap.lines if 'consequence_race' in ln]
generic_lines = [ln for ln in log_cap.lines
                  if 'consequence_rejected reason=unresolved_target' in ln]
check('race fires: 1 race log',           len(race_lines), 1)
check('race fires: 1 generic unresolved', len(generic_lines), 1)
check_truthy('race log: target name',     "'Mira'" in race_lines[0])
check_truthy('race log: race reason',     'reason=npc_introduction_race' in race_lines[0])
check_truthy('race log: source tag',      'source=dm' in race_lines[0])
check_truthy('race log: campaign tag',    f"campaign={RACE_CAMP}" in race_lines[0])


# 2. Generic unresolved-target (target NOT in narration) → only generic log.
log_cap = _LogCapture()
dnd_engine.log = log_cap
apply_consequence_proposals(
    RACE_CAMP,
    [{'target': 'Garrick', 'kind': 'threat', 'severity': 1,
      'summary': 'a threat'}],
    source='player', current_turn=5,
    narration_text='You walk through an empty hall, untouched.',
)
race_lines = [ln for ln in log_cap.lines if 'consequence_race' in ln]
generic_lines = [ln for ln in log_cap.lines
                  if 'consequence_rejected reason=unresolved_target' in ln]
check('off-canon: zero race lines',     len(race_lines), 0)
check('off-canon: 1 generic unresolved', len(generic_lines), 1)


# 3. Word-boundary guard — 'Mira' must NOT match 'miracle'.
log_cap = _LogCapture()
dnd_engine.log = log_cap
apply_consequence_proposals(
    RACE_CAMP,
    [{'target': 'Mira', 'kind': 'mercy', 'severity': 1,
      'summary': 'mercy shown'}],
    source='dm', current_turn=5,
    narration_text='The miracle was witnessed by all who stood there.',
)
race_lines = [ln for ln in log_cap.lines if 'consequence_race' in ln]
check('word boundary: no race for substring-only match', len(race_lines), 0)


# 4. Empty narration_text → race check skipped, no race log.
log_cap = _LogCapture()
dnd_engine.log = log_cap
apply_consequence_proposals(
    RACE_CAMP,
    [{'target': 'Mira', 'kind': 'mercy', 'severity': 1,
      'summary': 'mercy shown'}],
    source='dm', current_turn=5,
    narration_text='',
)
race_lines = [ln for ln in log_cap.lines if 'consequence_race' in ln]
check('empty narration: no race log', len(race_lines), 0)


# 5. PC contamination reject is NOT mistaken for race even if name in narration.
# Bind a PC into the race campaign so names_overlap fires.
import sqlite3 as _sq
_conn = _sq.connect(TEST_DB)
_conn.execute(
    "INSERT INTO dnd_characters (campaign_id, name, controller, alive) "
    "VALUES (?, ?, ?, 1)",
    (RACE_CAMP, 'Donovan Ruby', 'discord_user_x')
)
_conn.commit()
_conn.close()

log_cap = _LogCapture()
dnd_engine.log = log_cap
apply_consequence_proposals(
    RACE_CAMP,
    [{'target': 'Donovan Ruby', 'kind': 'cruelty', 'severity': 3,
      'summary': 'targeting the PC by mistake'}],
    source='player', current_turn=5,
    narration_text='Donovan Ruby looks around the bar.',  # name DOES appear
)
race_lines = [ln for ln in log_cap.lines if 'consequence_race' in ln]
pc_lines = [ln for ln in log_cap.lines
             if 'consequence_rejected reason=pc_match' in ln]
check('pc match: no race log',              len(race_lines), 0)
check('pc match: pc_match generic emitted', len(pc_lines), 1)


# 6. Multiple proposals — only the unresolved-AND-in-narration ones trigger race.
# Set up: one proposal whose target is in narration (race), one whose target
# is in narration but is the bound PC (pc_match — no race), one whose target
# is unresolved AND off-canon (generic unresolved — no race).
log_cap = _LogCapture()
dnd_engine.log = log_cap
apply_consequence_proposals(
    RACE_CAMP,
    [
        {'target': 'Mira',          'kind': 'alliance', 'severity': 2,
         'summary': 'swore loyalty'},
        {'target': 'Donovan Ruby',  'kind': 'cruelty',  'severity': 3,
         'summary': 'pc target'},
        {'target': 'NobodyHere',    'kind': 'threat',   'severity': 1,
         'summary': 'off-canon'},
    ],
    source='dm', current_turn=5,
    narration_text='Mira and Donovan Ruby exchange a glance in the doorway.',
)
race_lines = [ln for ln in log_cap.lines if 'consequence_race' in ln]
check('mixed: exactly one race log (Mira only)', len(race_lines), 1)
check_truthy('mixed: race targets Mira', "'Mira'" in race_lines[0])
check_truthy('mixed: race not Donovan',  'Donovan' not in race_lines[0])
check_truthy('mixed: race not Nobody',   'Nobody' not in race_lines[0])


# Restore the test-file's silent log.
dnd_engine.log = _silent_log


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
