"""Deterministic unit tests for npc_extractor — Phase 12A.2.

No network. Mocks cloud_router.route. Tests _normalize_npc, _validate_npc,
_extract_raw_candidates, and parse_npcs end-to-end with mocked responses.

Run: python3 test_npc_extractor.py
"""

import sys
import types

# ── Mock cloud_router + dnd_engine BEFORE importing npc_extractor ──

_mock_route_responses = []  # populated per-test by with_response()


def _mock_route(messages, task_type=None, system_prompt=None, force_local=False):
    if not _mock_route_responses:
        raise RuntimeError("test forgot to set _mock_route_responses")
    item = _mock_route_responses.pop(0)
    if isinstance(item, Exception):
        raise item
    return item, "mock"


cr = types.ModuleType('cloud_router')
cr.route = _mock_route
sys.modules['cloud_router'] = cr

# Stub dnd_engine — we only need log + canonicalize_name. canonicalize_name
# is small and pure, so we duplicate its semantics here rather than pulling
# in the real engine (and its sqlite3 / chromadb / orchestration imports).
de = types.ModuleType('dnd_engine')
de.log = lambda m: None


def _stub_canon(s):
    if not s:
        return ''
    s = s.replace('\u2018', "'").replace('\u2019', "'")
    s = s.replace('\u201C', '"').replace('\u201D', '"')
    return ' '.join(s.split())


de.canonicalize_name = _stub_canon


def _stub_is_token_prefix(short_name, long_name):
    short_tokens = short_name.split()
    long_tokens = long_name.split()
    if len(short_tokens) >= len(long_tokens):
        return False
    return long_tokens[:len(short_tokens)] == short_tokens


def _stub_names_overlap(a, b):
    a_norm = _stub_canon(a or '')
    b_norm = _stub_canon(b or '')
    if not a_norm or not b_norm:
        return False
    if a_norm == b_norm:
        return True
    if _stub_is_token_prefix(a_norm, b_norm) or _stub_is_token_prefix(b_norm, a_norm):
        return True
    a_tokens = a_norm.split()
    b_tokens = b_norm.split()
    if len(a_tokens) == 1 and a_tokens[0] in b_tokens:
        return True
    if len(b_tokens) == 1 and b_tokens[0] in a_tokens:
        return True
    return False


de.names_overlap = _stub_names_overlap
sys.modules['dnd_engine'] = de

from npc_extractor import (  # noqa: E402
    _normalize_npc, _validate_npc, _extract_raw_candidates,
    _strip_honorific,
    parse_npcs,
    _NAME_FIRST_WORD_STOPLIST, _NAME_WHOLE_STOPLIST, _HONORIFIC_PREFIXES,
)

# ── Tiny test harness ──

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


# ── Validator: name format ──

# Valid single-word names
for name in ['Garrick', 'Mira', 'Po', 'Cassius', 'Tobin']:
    check(f'valid_single {name!r}',
          _validate_npc({'name': name, 'role': '', 'location_hint': '', 'description_fragment': ''}),
          (True, None))

# Valid two-word names (incl. honorific + name)
for name in ['Sir Aldric', 'Captain Smith', 'Father Tomas', 'Mary-Jane Clark',
             "O'Brien Patrick"]:
    check(f'valid_two {name!r}',
          _validate_npc({'name': name, 'role': '', 'location_hint': '', 'description_fragment': ''}),
          (True, None))

# Valid three-word
check('valid_three',
      _validate_npc({'name': "John D'Artagnan Smith", 'role': '', 'location_hint': '',
                     'description_fragment': ''}),
      (True, None))

# Apostrophe + hyphen forms
for name in ["O'Brien", "D'Artagnan", "Mary-Jane", "Sir Mary-Jane"]:
    check(f'valid_punct {name!r}',
          _validate_npc({'name': name, 'role': '', 'location_hint': '', 'description_fragment': ''}),
          (True, None))


# ── Validator: name format failures ──

# Lowercase first letter
for name in ['garrick', 'mira', 'sir aldric']:
    check(f'lowercase {name!r}',
          _validate_npc({'name': name, 'role': '', 'location_hint': '', 'description_fragment': ''}),
          (False, 'bad_name_format'))

# Single letter — regex requires at least 2 chars in first word
check('single_letter',
      _validate_npc({'name': 'X', 'role': '', 'location_hint': '', 'description_fragment': ''}),
      (False, 'bad_name_format'))

# Mixed-case mid-word breaks regex (lowercase "the" between caps)
check('mid_lowercase',
      _validate_npc({'name': 'Garrick the Smith', 'role': '', 'location_hint': '',
                     'description_fragment': ''}),
      (False, 'bad_name_format'))

# Numeric or symbolic
for name in ['12-Year-Old', '#Garrick', '!Mira', 'Garrick!']:
    check(f'bad_format {name!r}',
          _validate_npc({'name': name, 'role': '', 'location_hint': '', 'description_fragment': ''}),
          (False, 'bad_name_format'))

# Four-word names exceed the 3-word cap
check('four_word',
      _validate_npc({'name': 'John James Robert Smith', 'role': '', 'location_hint': '',
                     'description_fragment': ''}),
      (False, 'bad_name_format'))

# Empty name
check('empty_name',
      _validate_npc({'name': '', 'role': '', 'location_hint': '', 'description_fragment': ''}),
      (False, 'bad_shape'))

# Non-dict
check('non_dict_list', _validate_npc(['Garrick']), (False, 'bad_shape'))
check('non_dict_str',  _validate_npc('Garrick'),    (False, 'bad_shape'))
check('non_dict_none', _validate_npc(None),         (False, 'bad_shape'))


# ── Validator: first-word stoplist ──

for name in ['The Guard', 'An Innkeeper', 'He Smiles',
             'She Glares', 'They Wait', 'You See', 'My Companion',
             'This Person', 'That Bandit', 'Some Figure', 'Every Soul',
             'One Man', 'Three Soldiers']:
    check(f'first_word_drop {name!r}',
          _validate_npc({'name': name, 'role': '', 'location_hint': '',
                         'description_fragment': ''}),
          (False, 'name_in_stoplist'))

# Single-letter first words ("A Stranger", "I See") fail the regex before
# the stoplist check ever runs. Document that explicitly.
for name in ['A Stranger', 'I See']:
    check(f'first_word_via_regex {name!r}',
          _validate_npc({'name': name, 'role': '', 'location_hint': '',
                         'description_fragment': ''}),
          (False, 'bad_name_format'))


# ── Validator: whole-name stoplist ──

# Honorifics alone
for name in ['Sir', 'Lord', 'Lady', 'Captain', 'Father', 'Mother',
             'Brother', 'Sister', 'King', 'Queen']:
    check(f'whole_drop_honorific {name!r}',
          _validate_npc({'name': name, 'role': '', 'location_hint': '',
                         'description_fragment': ''}),
          (False, 'name_in_stoplist'))

# Generic role-as-name
for name in ['Guard', 'Soldier', 'Bandit', 'Blacksmith', 'Innkeeper',
             'Merchant', 'Stranger', 'Figure', 'Man', 'Woman', 'Child',
             'Traveler']:
    check(f'whole_drop_role {name!r}',
          _validate_npc({'name': name, 'role': '', 'location_hint': '',
                         'description_fragment': ''}),
          (False, 'name_in_stoplist'))

# Race/species alone
for name in ['Elf', 'Dwarf', 'Halfling', 'Goblin', 'Orc', 'Tiefling']:
    check(f'whole_drop_race {name!r}',
          _validate_npc({'name': name, 'role': '', 'location_hint': '',
                         'description_fragment': ''}),
          (False, 'name_in_stoplist'))

# Supernatural archetypes alone
for name in ['Dragon', 'Demon', 'Ghost', 'Vampire', 'Skeleton', 'Lich']:
    check(f'whole_drop_supernatural {name!r}',
          _validate_npc({'name': name, 'role': '', 'location_hint': '',
                         'description_fragment': ''}),
          (False, 'name_in_stoplist'))


# ── Validator: stoplist combinations that should still PASS ──

# Honorific + proper name → keep
for name in ['Sir Aldric', 'Lord Bardus', 'Captain Smith', 'Father Tomas',
             'Lady Mira', 'King Harold']:
    check(f'whole_keep_honorific_name {name!r}',
          _validate_npc({'name': name, 'role': '', 'location_hint': '',
                         'description_fragment': ''}),
          (True, None))


# ── Validator: length caps ──

check('name_long_passes_regex',
      _validate_npc({'name': 'A' + 'a' * 60, 'role': '', 'location_hint': '',
                     'description_fragment': ''}),
      (False, 'length_exceeded'))

check('description_too_long',
      _validate_npc({'name': 'Garrick', 'role': '', 'location_hint': '',
                     'description_fragment': 'x' * 101}),
      (False, 'length_exceeded'))

check('role_too_long',
      _validate_npc({'name': 'Garrick', 'role': 'r' * 61, 'location_hint': '',
                     'description_fragment': ''}),
      (False, 'length_exceeded'))

check('location_hint_too_long',
      _validate_npc({'name': 'Garrick', 'role': '', 'location_hint': 'l' * 81,
                     'description_fragment': ''}),
      (False, 'length_exceeded'))


# ── Validator: bad characters in fields ──

for field, payload in [('role', 'smith; rm -rf /'),
                       ('location_hint', 'Redhaven | nc evil.com'),
                       ('description_fragment', 'gruff `evil` smith'),
                       ('description_fragment', 'has\nbreaklines'),
                       ('role', 'smith\rrm'),
                       ('description_fragment', 'detail $(echo)'),
                       ('description_fragment', 'detail > out')]:
    npc = {'name': 'Garrick', 'role': '', 'location_hint': '',
           'description_fragment': ''}
    npc[field] = payload
    check(f'bad_chars {field}={payload[:30]!r}',
          _validate_npc(npc), (False, 'bad_chars'))


# ── _strip_honorific (deterministic identity normalization) ──

# Stripped: honorific prefix + at least one following token
check('strip_sir',          _strip_honorific('Sir Aldric'),         'Aldric')
check('strip_lord',         _strip_honorific('Lord Bardus'),        'Bardus')
check('strip_lady',         _strip_honorific('Lady Mira'),          'Mira')
check('strip_captain',      _strip_honorific('Captain Mira'),       'Mira')
check('strip_father',       _strip_honorific('Father Tomas'),       'Tomas')
check('strip_doctor',       _strip_honorific('Doctor Strange'),     'Strange')
check('strip_king',         _strip_honorific('King Harold'),        'Harold')
check('strip_dame',         _strip_honorific('Dame Cara'),          'Cara')

# Stacked honorifics: iterative strip
check('strip_stacked',      _strip_honorific('Sir Doctor Bardus'),  'Bardus')
check('strip_stacked_pair', _strip_honorific('Lord King Aldric'),   'Aldric')

# NEVER strips the last token — bare honorifics survive (caught by stoplist)
check('strip_alone_sir',    _strip_honorific('Sir'),                'Sir')
check('strip_alone_lord',   _strip_honorific('Lord'),               'Lord')
check('strip_alone_capt',   _strip_honorific('Captain'),            'Captain')

# Whole-word match only — embedded prefixes do NOT strip
check('strip_lordran',      _strip_honorific('Lordran'),            'Lordran')
check('strip_princewick',   _strip_honorific('Princewick'),         'Princewick')
check('strip_kingdom',      _strip_honorific('Kingdom'),            'Kingdom')
check('strip_master_bait',  _strip_honorific('Masterson'),          'Masterson')

# Non-honorific first word: passthrough
check('strip_passthrough',     _strip_honorific('Garrick'),                'Garrick')
check('strip_passthrough_two', _strip_honorific('Garrick Stoneborn'),     'Garrick Stoneborn')
check('strip_preserves_punct', _strip_honorific('Sir Mary-Jane'),         'Mary-Jane')
check('strip_preserves_apos',  _strip_honorific("Lord O'Brien"),          "O'Brien")

# Edge: empty / falsy
check('strip_empty',        _strip_honorific(''),                   '')
check('strip_none_safe',    _strip_honorific(None),                 None)


# ── Normalizer: shape coercion ──

check('norm_basic',
      _normalize_npc({'name': '  Garrick  ', 'role': ' blacksmith ',
                      'location_hint': '', 'description_fragment': ''}),
      {'name': 'Garrick', 'role': 'blacksmith', 'location_hint': '',
       'description_fragment': ''})

check('norm_missing_keys',
      _normalize_npc({'name': 'Mira'}),
      {'name': 'Mira', 'role': '', 'location_hint': '', 'description_fragment': ''})

check('norm_curly_quotes',
      _normalize_npc({'name': 'O\u2019Brien'}),
      {'name': "O'Brien", 'role': '', 'location_hint': '', 'description_fragment': ''})

check('norm_collapse_internal_ws',
      _normalize_npc({'name': 'Sir   Aldric'}),
      {'name': 'Aldric', 'role': '', 'location_hint': '', 'description_fragment': ''})

# Honorific stripping integrated into normalize
check('norm_strips_honorific_sir',
      _normalize_npc({'name': 'Sir Aldric'}),
      {'name': 'Aldric', 'role': '', 'location_hint': '', 'description_fragment': ''})
check('norm_strips_honorific_captain',
      _normalize_npc({'name': 'Captain Mira'}),
      {'name': 'Mira', 'role': '', 'location_hint': '', 'description_fragment': ''})
check('norm_strips_stacked',
      _normalize_npc({'name': 'Sir Doctor Bardus'}),
      {'name': 'Bardus', 'role': '', 'location_hint': '', 'description_fragment': ''})
check('norm_keeps_lordran',
      _normalize_npc({'name': 'Lordran'}),
      {'name': 'Lordran', 'role': '', 'location_hint': '', 'description_fragment': ''})
check('norm_canonicalizes_then_strips',
      _normalize_npc({'name': '  Sir   Aldric  '}),
      {'name': 'Aldric', 'role': '', 'location_hint': '', 'description_fragment': ''})

check('norm_non_string_field',
      _normalize_npc({'name': 'Garrick', 'role': 42}),
      {'name': 'Garrick', 'role': '', 'location_hint': '', 'description_fragment': ''})

check('norm_non_string_name',
      _normalize_npc({'name': 42}),
      {'name': '', 'role': '', 'location_hint': '', 'description_fragment': ''})

check('norm_non_dict',          _normalize_npc('Garrick'), None)
check('norm_non_dict_list',     _normalize_npc(['Garrick']), None)
check('norm_non_dict_none',     _normalize_npc(None), None)


# ── JSON extractor ──

check('json_plain',
      _extract_raw_candidates('[{"name":"Garrick"}]'),
      [{'name': 'Garrick'}])
check('json_empty', _extract_raw_candidates('[]'), [])
check('json_fence_lang',
      _extract_raw_candidates('```json\n[{"name":"Mira"}]\n```'),
      [{'name': 'Mira'}])
check('json_fence_bare',
      _extract_raw_candidates('```\n[]\n```'),
      [])
check('json_with_prose',
      _extract_raw_candidates('Sure! [{"name":"Cassius"}] for you.'),
      [{'name': 'Cassius'}])
check('json_malformed', _extract_raw_candidates('not json'),       None)
check('json_object',    _extract_raw_candidates('{"name":"X"}'),   None)
check('json_truncated', _extract_raw_candidates('[{"name"'),       None)
check('json_empty_str', _extract_raw_candidates(''),                None)
check('json_none',      _extract_raw_candidates(None),              None)


# ── parse_npcs end-to-end (mocked LLM) ──

def with_response(response):
    global _mock_route_responses
    _mock_route_responses = [response]
    return parse_npcs('A thing happens in the dungeon.')


# Helper for cleaner expected dicts in tests
def npc(name, role='', location_hint='', description_fragment=''):
    return {'name': name, 'role': role, 'location_hint': location_hint,
            'description_fragment': description_fragment}


check('e2e_single_named',
      with_response('[{"name":"Garrick","role":"blacksmith","location_hint":"","description_fragment":""}]'),
      [npc('Garrick', role='blacksmith')])

check('e2e_empty_array',
      with_response('[]'),
      [])

check('e2e_drop_invalid_name',
      with_response('[{"name":"Garrick"},{"name":"the guard"}]'),
      [npc('Garrick')])

check('e2e_drop_first_word_stoplist',
      with_response('[{"name":"The Guard"},{"name":"Mira"}]'),
      [npc('Mira')])

check('e2e_drop_whole_stoplist',
      with_response('[{"name":"Sir"},{"name":"Captain"},{"name":"Sir Aldric"}]'),
      [npc('Aldric')])

check('e2e_drop_pronoun_name',
      with_response('[{"name":"He"},{"name":"She"},{"name":"They"}]'),
      [])

check('e2e_multi_npc',
      with_response('[{"name":"Aldric"},{"name":"Bardus"},{"name":"Cara"}]'),
      [npc('Aldric'), npc('Bardus'), npc('Cara')])

check('e2e_dedupe_within_turn',
      with_response('[{"name":"Garrick"},{"name":"Garrick","role":"smith"}]'),
      [npc('Garrick')])

check('e2e_malformed_json', with_response('not json at all'), [])
check('e2e_object_root',    with_response('{"name":"X"}'),    [])

check('e2e_fence_wrap',
      with_response('```json\n[{"name":"Mira","role":"innkeeper","location_hint":"Redhaven","description_fragment":""}]\n```'),
      [npc('Mira', role='innkeeper', location_hint='Redhaven')])

check('e2e_drop_nondict_in_array',
      with_response('[1, "garrick", {"name":"Tobin"}]'),
      [npc('Tobin')])

check('e2e_drop_bad_chars_in_role',
      with_response('[{"name":"Garrick","role":"smith;rm -rf /"},{"name":"Mira"}]'),
      [npc('Mira')])

check('e2e_truncate_input_normalized',
      with_response('[{"name":"  Garrick  ","role":"  blacksmith  "}]'),
      [npc('Garrick', role='blacksmith')])

check('e2e_whitespace_collapse',
      with_response('[{"name":"Sir   Aldric"}]'),
      [npc('Aldric')])

# End-to-end honorific stripping (the doctrine — Session 12 review)
check('e2e_strips_sir',
      with_response('[{"name":"Sir Aldric","role":"knight"}]'),
      [npc('Aldric', role='knight')])
check('e2e_strips_captain_drops_lone',
      with_response('[{"name":"Captain Mira"},{"name":"Captain"}]'),
      [npc('Mira')])
check('e2e_strips_stacked',
      with_response('[{"name":"Sir Father Bardus"}]'),
      [npc('Bardus')])
check('e2e_dedupe_after_strip',
      with_response('[{"name":"Sir Aldric"},{"name":"Aldric"}]'),
      [npc('Aldric')])
check('e2e_keeps_embedded_prefix',
      with_response('[{"name":"Lordran"}]'),
      [npc('Lordran')])

# Empty / None narration short-circuits without consulting route
_mock_route_responses = []
check('e2e_empty_narr', parse_npcs(''),   [])
check('e2e_none_narr',  parse_npcs(None), [])
check('e2e_int_narr',   parse_npcs(42),   [])

# Route raises → empty list
_mock_route_responses = [RuntimeError("provider exhausted")]
check('e2e_route_raises', parse_npcs('something happens'), [])

# Route returns empty string → empty list (raw_response='' → no array)
_mock_route_responses = ['']
check('e2e_route_empty_str', parse_npcs('something happens'), [])

# Route returns None → empty list
_mock_route_responses = [None]
check('e2e_route_none', parse_npcs('something happens'), [])


# ── Stoplist sanity (catches accidental edits) ──

# A few stoplist entries we rely on as load-bearing
for word in ['The', 'A', 'He', 'She', 'They', 'You']:
    check_truthy(f'first_word_stoplist contains {word!r}',
                 word in _NAME_FIRST_WORD_STOPLIST)

for word in ['Sir', 'Lord', 'Lady', 'Captain', 'Guard', 'Stranger',
             'Elf', 'Dragon']:
    check_truthy(f'whole_stoplist contains {word!r}',
                 word in _NAME_WHOLE_STOPLIST)

# _HONORIFIC_PREFIXES is a strict subset of _NAME_WHOLE_STOPLIST (so that
# bare honorifics like 'Sir' alone — which _strip_honorific won't touch —
# get rejected by the whole-name pass).
check_truthy('honorific_prefixes_nonempty',
             len(_HONORIFIC_PREFIXES) > 10)
check_truthy('honorifics_subset_of_whole_stoplist',
             _HONORIFIC_PREFIXES.issubset(_NAME_WHOLE_STOPLIST))


# ── PC contamination filter (Session 15) ──

# _validate_npc with pc_names — only drops on overlap, otherwise behaves as before.
_NPC_TEMPLATE = lambda name: {
    'name': name, 'role': '', 'location_hint': '', 'description_fragment': ''
}

# pc_names=None → no filter at all
check('pc_filter: None pc_names',
      _validate_npc(_NPC_TEMPLATE('Donovan Ruby'), pc_names=None),
      (True, None))

# pc_names=[] → no filter
check('pc_filter: empty pc_names',
      _validate_npc(_NPC_TEMPLATE('Donovan Ruby'), pc_names=[]),
      (True, None))

# Exact match → pc_match
check('pc_filter: exact match',
      _validate_npc(_NPC_TEMPLATE('Donovan Ruby'), pc_names=['Donovan Ruby']),
      (False, 'pc_match'))

# First-token match (PC's first name in narration → drop)
check('pc_filter: first-token match',
      _validate_npc(_NPC_TEMPLATE('Donovan'), pc_names=['Donovan Ruby']),
      (False, 'pc_match'))

# Last-name-only address form (the original Donovan/Ruby failure mode)
check('pc_filter: last-name only',
      _validate_npc(_NPC_TEMPLATE('Ruby'), pc_names=['Donovan Ruby']),
      (False, 'pc_match'))

# Multi-token candidate sharing only first token = different identity, NOT
# blocked. The data model treats "Donovan James" and "Donovan Ruby" as
# distinct people. (Same as the fragmentation_report semantics.)
check('pc_filter: multi-token shared first NOT blocked',
      _validate_npc(_NPC_TEMPLATE('Donovan James'), pc_names=['Donovan Ruby']),
      (True, None))

# Non-overlapping name passes
check('pc_filter: non-overlap passes',
      _validate_npc(_NPC_TEMPLATE('Borin'), pc_names=['Donovan Ruby']),
      (True, None))

# Multiple PCs — match against any
check('pc_filter: match second PC',
      _validate_npc(_NPC_TEMPLATE('Sera'), pc_names=['Donovan Ruby', 'Sera Wynd']),
      (False, 'pc_match'))

check('pc_filter: match first PC of two',
      _validate_npc(_NPC_TEMPLATE('Donovan'), pc_names=['Donovan Ruby', 'Sera Wynd']),
      (False, 'pc_match'))

# Substring of token doesn't match (Don is not a whole-token prefix of Donovan)
check('pc_filter: substring not whole-token',
      _validate_npc(_NPC_TEMPLATE('Don'), pc_names=['Donovan Ruby']),
      (True, None))

# Stoplist still wins over PC filter (drop earlier)
check('pc_filter: stoplist still drops first',
      _validate_npc(_NPC_TEMPLATE('The Donovan'), pc_names=['Donovan Ruby']),
      (False, 'name_in_stoplist'))

# Bad name format still wins over PC filter
check('pc_filter: bad name format wins',
      _validate_npc(_NPC_TEMPLATE('lowercase name'), pc_names=['Donovan Ruby']),
      (False, 'bad_name_format'))


# ── parse_npcs end-to-end with PC filter ──

# parser emits PC + real NPC; PC dropped, real NPC kept
_mock_route_responses = ['[{"name":"Donovan Ruby","role":"rogue","location_hint":"","description_fragment":""},'
                         '{"name":"Garrick","role":"barkeep","location_hint":"","description_fragment":""}]']
result = parse_npcs("The barkeep slides a mug to Donovan Ruby. Garrick wipes the counter.",
                    pc_names=['Donovan Ruby'])
result_names = [n['name'] for n in result]
check('parse_npcs: PC filter drops PC, keeps NPC',
      result_names, ['Garrick'])

# parser emits PC short form (Donovan only); also dropped
_mock_route_responses = ['[{"name":"Donovan","role":"","location_hint":"","description_fragment":""},'
                         '{"name":"Lira","role":"bard","location_hint":"","description_fragment":""}]']
result = parse_npcs("Donovan nods. Lira hums a ditty.",
                    pc_names=['Donovan Ruby'])
result_names = [n['name'] for n in result]
check('parse_npcs: short-form PC also dropped',
      result_names, ['Lira'])

# pc_names=None preserves backward-compat (no filtering)
_mock_route_responses = ['[{"name":"Donovan Ruby","role":"rogue","location_hint":"","description_fragment":""}]']
result = parse_npcs("Donovan Ruby waves.", pc_names=None)
result_names = [n['name'] for n in result]
check('parse_npcs: pc_names=None no filter',
      result_names, ['Donovan Ruby'])

# pc_names=[] also no filter
_mock_route_responses = ['[{"name":"Donovan Ruby","role":"rogue","location_hint":"","description_fragment":""}]']
result = parse_npcs("Donovan Ruby waves.", pc_names=[])
result_names = [n['name'] for n in result]
check('parse_npcs: empty pc_names no filter',
      result_names, ['Donovan Ruby'])


# ── Report ──

print(f"\n{'=' * 50}")
print(f"PASS: {PASS}  FAIL: {FAIL}")
if FAIL:
    print("\nFAILURES:")
    for line in FAILURES:
        print(line)
    sys.exit(1)
print("ALL GREEN")
