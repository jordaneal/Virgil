"""Deterministic tests for parse_init_list_embed (Session 21).

Combat Persistence Directive v1 — `!init list` snapshot parser. Pure regex,
no LLM. The user-confirmed sample (only `<None>` HP rendering) is the
load-bearing fixture; HP / private / defeated / conditions / fenced cases
exercise hypothetical Avrae formats based on cog convention. Real-combat
samples will let us lock those formats post-ship.

Run:
    cd /home/jordaneal/scripts && python3 test_init_list_parser.py
"""

import sys
sys.path.insert(0, '/home/jordaneal/scripts')

import avrae_listener as al
captured = []
al.log = lambda m: captured.append(m)


# ─── Confirmed format (user-supplied sample) ────────────────────────

CONFIRMED_SAMPLE = """Current initiative: 25 (round 1)
================================
  29: Garrick <None>
# 25: throx <None>
  13: Donovan <None>"""


def test_user_supplied_sample_parses():
    r = al.parse_init_list_embed(CONFIRMED_SAMPLE)
    assert r is not None
    assert r['round'] == 1
    assert r['current_init'] == 25
    assert len(r['combatants']) == 3


def test_user_supplied_sample_active_marker():
    r = al.parse_init_list_embed(CONFIRMED_SAMPLE)
    actives = [c for c in r['combatants'] if c['active']]
    assert len(actives) == 1
    assert actives[0]['name'] == 'throx'


def test_user_supplied_sample_none_status_decodes_clean():
    r = al.parse_init_list_embed(CONFIRMED_SAMPLE)
    for c in r['combatants']:
        assert c['hp_current'] is None
        assert c['hp_max'] is None
        assert c['conditions'] == ''
        assert c['alive'] == 1


def test_user_supplied_sample_init_values():
    r = al.parse_init_list_embed(CONFIRMED_SAMPLE)
    inits = [c['init'] for c in r['combatants']]
    assert inits == [29, 25, 13]


def test_user_supplied_sample_names_preserved():
    r = al.parse_init_list_embed(CONFIRMED_SAMPLE)
    names = [c['name'] for c in r['combatants']]
    # Avrae preserves case as-given to !init add
    assert names == ['Garrick', 'throx', 'Donovan']


# ─── Real-combat sample (locked 2026-05-04) ─────────────────────────

REAL_COMBAT_SAMPLE = """Current initiative: 0 (round 0)
===============================
  18: Garrick <None>
  14: Donovan Ruby <11/11 HP> (AC 13)"""


def test_real_combat_ac_suffix_does_not_break_row_match():
    """Sheet-bound combatants (added via !init join) render with a trailing
    `(AC N)` suffix after the HP slot. Captured live 2026-05-04. Permissive
    trailer in _INIT_LIST_ROW_RE absorbs this without dropping the row."""
    r = al.parse_init_list_embed(REAL_COMBAT_SAMPLE)
    assert r is not None
    assert len(r['combatants']) == 2, (
        f"both rows must parse despite (AC 13) suffix; got {r['combatants']}"
    )


def test_real_combat_garrick_decodes_to_unknown_hp():
    r = al.parse_init_list_embed(REAL_COMBAT_SAMPLE)
    g = next(c for c in r['combatants'] if c['name'] == 'Garrick')
    assert g['hp_current'] is None and g['hp_max'] is None
    assert g['alive'] == 1


def test_real_combat_donovan_decodes_full_hp():
    r = al.parse_init_list_embed(REAL_COMBAT_SAMPLE)
    d = next(c for c in r['combatants'] if c['name'] == 'Donovan Ruby')
    assert d['hp_current'] == 11
    assert d['hp_max'] == 11
    assert d['alive'] == 1


def test_real_combat_multi_word_name_preserved():
    r = al.parse_init_list_embed(REAL_COMBAT_SAMPLE)
    names = [c['name'] for c in r['combatants']]
    assert 'Donovan Ruby' in names


# ─── Code fence handling ────────────────────────────────────────────

def test_code_fenced_md():
    fenced = '```md\n' + CONFIRMED_SAMPLE + '\n```'
    r = al.parse_init_list_embed(fenced)
    assert r is not None
    assert len(r['combatants']) == 3


def test_code_fenced_plain():
    fenced = '```\n' + CONFIRMED_SAMPLE + '\n```'
    r = al.parse_init_list_embed(fenced)
    assert r is not None and len(r['combatants']) == 3


# ─── Negative cases ─────────────────────────────────────────────────

def test_empty_string_returns_none():
    assert al.parse_init_list_embed('') is None


def test_none_input_returns_none():
    assert al.parse_init_list_embed(None) is None


def test_narrative_text_returns_none():
    text = "The bandits scatter into the night, leaving you alone."
    assert al.parse_init_list_embed(text) is None


def test_header_without_separator_returns_none():
    text = "Current initiative: 25 (round 1)\nblah blah"
    assert al.parse_init_list_embed(text) is None


def test_separator_without_header_returns_none():
    text = "================================\n  29: Garrick <None>"
    assert al.parse_init_list_embed(text) is None


def test_header_and_separator_with_no_combatants_returns_empty_list():
    text = "Current initiative: 0 (round 1)\n================"
    r = al.parse_init_list_embed(text)
    assert r is not None and r['combatants'] == []


# ─── Hypothetical HP rendering (UNCONFIRMED format) ─────────────────

def test_hp_rendering_n_over_m_HP_decodes():
    sample = """Current initiative: 25 (round 1)
================
# 25: Goblin <22/22 HP>
  20: Hero <15/30 HP>"""
    r = al.parse_init_list_embed(sample)
    assert r is not None
    g = r['combatants'][0]
    assert g['hp_current'] == 22 and g['hp_max'] == 22 and g['alive'] == 1
    h = r['combatants'][1]
    assert h['hp_current'] == 15 and h['hp_max'] == 30 and h['alive'] == 1


def test_hp_rendering_n_over_m_no_HP_suffix_decodes():
    sample = """Current initiative: 10 (round 1)
================
# 10: Hero <12/12>"""
    r = al.parse_init_list_embed(sample)
    assert r['combatants'][0]['hp_current'] == 12
    assert r['combatants'][0]['hp_max'] == 12


def test_zero_hp_marks_alive_zero():
    sample = """Current initiative: 5 (round 1)
================
# 5: Down <0/22 HP>"""
    r = al.parse_init_list_embed(sample)
    assert r['combatants'][0]['hp_current'] == 0
    assert r['combatants'][0]['alive'] == 0


# ─── Defeated marker ────────────────────────────────────────────────

def test_defeated_status_marks_alive_zero():
    sample = """Current initiative: 10 (round 1)
================
# 10: Down <Defeated>"""
    r = al.parse_init_list_embed(sample)
    c = r['combatants'][0]
    assert c['alive'] == 0
    assert c['hp_current'] == 0


# ─── Private mode (Healthy / Bloodied / Wounded) ────────────────────

def test_private_status_keeps_hp_unknown_alive_true():
    sample = """Current initiative: 5 (round 1)
================
# 5: Mystery <Healthy>"""
    r = al.parse_init_list_embed(sample)
    c = r['combatants'][0]
    assert c['hp_current'] is None
    assert c['hp_max'] is None
    assert c['alive'] == 1


# ─── Condition continuation lines ───────────────────────────────────

def test_dash_continuation_attaches_conditions():
    sample = """Current initiative: 25 (round 1)
================
# 25: Hero <22/22 HP>
        - Frightened
        - Concentrating"""
    r = al.parse_init_list_embed(sample)
    c = r['combatants'][0]
    assert 'Frightened' in c['conditions']
    assert 'Concentrating' in c['conditions']


def test_star_continuation_also_attaches():
    sample = """Current initiative: 25 (round 1)
================
# 25: Hero <22/22 HP>
        * Prone"""
    r = al.parse_init_list_embed(sample)
    assert r['combatants'][0]['conditions'] == 'Prone'


def test_continuation_only_attaches_to_most_recent():
    sample = """Current initiative: 25 (round 1)
================
  25: A <22/22 HP>
        - CondA
  20: B <15/15 HP>
        - CondB"""
    r = al.parse_init_list_embed(sample)
    a = next(c for c in r['combatants'] if c['name'] == 'A')
    b = next(c for c in r['combatants'] if c['name'] == 'B')
    assert a['conditions'] == 'CondA'
    assert b['conditions'] == 'CondB'


# ─── Robustness ─────────────────────────────────────────────────────

def test_round_and_init_extracted_correctly():
    sample = """Current initiative: 17 (round 4)
================
# 17: X <None>"""
    r = al.parse_init_list_embed(sample)
    assert r['round'] == 4 and r['current_init'] == 17


def test_negative_init_value_parses():
    sample = """Current initiative: -2 (round 1)
================
# -2: Slow <None>"""
    r = al.parse_init_list_embed(sample)
    assert r['current_init'] == -2
    assert r['combatants'][0]['init'] == -2


def test_separator_can_be_short():
    sample = """Current initiative: 10 (round 1)
===
# 10: X <None>"""
    r = al.parse_init_list_embed(sample)
    assert r is not None and len(r['combatants']) == 1


def test_unknown_status_falls_open_and_logs():
    captured.clear()
    sample = """Current initiative: 10 (round 1)
================
# 10: Weird <some-novel-format-X>"""
    r = al.parse_init_list_embed(sample)
    # parse-unknown is hit because the format isn't None/numeric/defeated.
    # Actually a non-numeric, non-defeated, non-None status gets classified
    # as 'private' (alive, HP unknown), not 'unknown'. Verify graceful decode.
    assert r is not None
    c = r['combatants'][0]
    assert c['hp_current'] is None
    assert c['hp_max'] is None
    assert c['alive'] == 1


# ─── Run ────────────────────────────────────────────────────────────

if __name__ == '__main__':
    failures = []
    funcs = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for fn in funcs:
        try:
            fn()
            print(f"  ok   {fn.__name__}")
        except AssertionError as e:
            failures.append((fn.__name__, str(e)))
            print(f"  FAIL {fn.__name__}: {e}")
        except Exception as e:
            failures.append((fn.__name__, repr(e)))
            print(f"  ERR  {fn.__name__}: {e!r}")
    if failures:
        print(f"\n{len(failures)} failure(s)")
        sys.exit(1)
    print(f"\n{len(funcs)} tests passed.")
