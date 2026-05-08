"""Deterministic unit tests for location_extractor — Phase 12B.2.

No network. Mocks cloud_router.route. Tests _normalize_location,
_validate_location, _extract_raw_candidates, and parse_locations
end-to-end with mocked responses.

Run: python3 test_location_extractor.py
"""

import sys
import types

# ── Mock cloud_router + dnd_engine BEFORE importing location_extractor ──

_mock_route_responses = []


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

# Stub dnd_engine — duplicate canonicalize_location_name semantics here so
# we don't pull in sqlite3/chromadb/orchestration.
de = types.ModuleType('dnd_engine')
de.log = lambda m: None

_LEADING_ARTICLES = frozenset({"the", "a", "an"})


def _stub_canon_loc(s):
    if not s:
        return ''
    s = s.replace('\u2018', "'").replace('\u2019', "'")
    s = s.replace('\u201C', '"').replace('\u201D', '"')
    s = ' '.join(s.split())
    parts = s.split()
    while len(parts) > 1 and parts[0].lower() in _LEADING_ARTICLES:
        parts = parts[1:]
    return ' '.join(parts)


de.canonicalize_location_name = _stub_canon_loc
sys.modules['dnd_engine'] = de

from location_extractor import (  # noqa: E402
    _normalize_location, _validate_location, _extract_raw_candidates,
    parse_locations,
    _NAME_WHOLE_STOPLIST,
)

# ── Tiny harness ──

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


# ── Validator: name format (post-canonicalization) ──

# Valid names (already in canonical form — article stripped)
for name in ['Redhaven', 'Stoneforge', 'Whispering Woods', 'Crystal Caves',
             'Old Mill', 'Iron Tankard', 'Rusty Anchor',
             'Stoneforge Guild Hall', 'Aldric\'s Keep']:
    check(f'valid {name!r}',
          _validate_location({'name': name, 'type': '', 'parent_hint': '',
                              'description_fragment': ''}),
          (True, None))

# 4-word max (locations get one more word than NPCs)
check('valid_four_word',
      _validate_location({'name': 'East Wing of Castle', 'type': '',
                          'parent_hint': '', 'description_fragment': ''}),
      (False, 'bad_name_format'))  # "of" lowercase — fails regex

check('valid_four_caps',
      _validate_location({'name': 'East Wing Castle Annex', 'type': '',
                          'parent_hint': '', 'description_fragment': ''}),
      (True, None))

# Five+ words rejected
check('five_word',
      _validate_location({'name': 'East Wing Castle Annex Tower',
                          'type': '', 'parent_hint': '',
                          'description_fragment': ''}),
      (False, 'bad_name_format'))

# Lowercase first letter
for name in ['redhaven', 'stoneforge', 'crystal caves']:
    check(f'lowercase {name!r}',
          _validate_location({'name': name, 'type': '', 'parent_hint': '',
                              'description_fragment': ''}),
          (False, 'bad_name_format'))

# Empty / non-dict
check('empty_name',
      _validate_location({'name': '', 'type': '', 'parent_hint': '',
                          'description_fragment': ''}),
      (False, 'bad_shape'))
check('non_dict', _validate_location(['Redhaven']), (False, 'bad_shape'))
check('none',     _validate_location(None),         (False, 'bad_shape'))


# ── Validator: whole-name stoplist (pure-generic locations) ──

for name in ['Forest', 'Woods', 'Mountain', 'River', 'Lake', 'Sea',
             'Cave', 'Caves', 'Castle', 'Tower', 'Inn', 'Tavern',
             'Temple', 'Shrine', 'Market', 'Square', 'Gate', 'Bridge',
             'Hall', 'Room', 'Corridor', 'Dungeon', 'Lair',
             'Road', 'Path', 'Trail', 'Highway',
             'North', 'South', 'East', 'West',
             'Realm', 'Lands', 'Kingdom', 'Empire', 'Region',
             'Outside', 'Underground']:
    check(f'stoplist_drop {name!r}',
          _validate_location({'name': name, 'type': '', 'parent_hint': '',
                              'description_fragment': ''}),
          (False, 'name_in_stoplist'))


# ── Validator: distinctive-token prefixes pass even if they include type words ──

for name in ['Whispering Forest', 'Crystal Caves', 'Iron Tower',
             'Rusty Anchor', 'Old Mill', 'Stoneforge Hall']:
    check(f'distinctive_keep {name!r}',
          _validate_location({'name': name, 'type': '', 'parent_hint': '',
                              'description_fragment': ''}),
          (True, None))


# ── Validator: length caps ──

check('name_too_long',
      _validate_location({'name': 'A' + 'a' * 80, 'type': '',
                          'parent_hint': '', 'description_fragment': ''}),
      (False, 'length_exceeded'))

check('description_too_long',
      _validate_location({'name': 'Redhaven', 'type': '', 'parent_hint': '',
                          'description_fragment': 'x' * 101}),
      (False, 'length_exceeded'))

check('type_too_long',
      _validate_location({'name': 'Redhaven', 'type': 't' * 31,
                          'parent_hint': '', 'description_fragment': ''}),
      (False, 'length_exceeded'))

check('parent_hint_too_long',
      _validate_location({'name': 'Redhaven', 'type': '',
                          'parent_hint': 'p' * 81,
                          'description_fragment': ''}),
      (False, 'length_exceeded'))


# ── Validator: bad characters ──

for field, payload in [('type', 'tavern; rm -rf /'),
                       ('parent_hint', 'Redhaven | nc evil.com'),
                       ('description_fragment', 'smoky `evil` ceilings'),
                       ('description_fragment', 'has\nbreaklines'),
                       ('type', 'tavern\rrm'),
                       ('description_fragment', 'detail $(echo)'),
                       ('description_fragment', 'detail > out')]:
    loc = {'name': 'Redhaven', 'type': '', 'parent_hint': '',
           'description_fragment': ''}
    loc[field] = payload
    check(f'bad_chars {field}={payload[:30]!r}',
          _validate_location(loc), (False, 'bad_chars'))


# ── Normalizer: shape coercion ──

check('norm_basic',
      _normalize_location({'name': '  Redhaven  ', 'type': ' town ',
                           'parent_hint': '', 'description_fragment': ''}),
      {'name': 'Redhaven', 'type': 'town', 'parent_hint': '',
       'description_fragment': ''})

check('norm_missing_keys',
      _normalize_location({'name': 'Stoneforge'}),
      {'name': 'Stoneforge', 'type': '', 'parent_hint': '',
       'description_fragment': ''})

check('norm_curly',
      _normalize_location({'name': 'Aldric\u2019s Keep'}),
      {'name': "Aldric's Keep", 'type': '', 'parent_hint': '',
       'description_fragment': ''})

check('norm_collapse_ws',
      _normalize_location({'name': 'Stoneforge   Hall'}),
      {'name': 'Stoneforge Hall', 'type': '', 'parent_hint': '',
       'description_fragment': ''})

# Article-stripping integrated into normalize
check('norm_strips_the',
      _normalize_location({'name': 'The Rusty Anchor', 'type': 'tavern'}),
      {'name': 'Rusty Anchor', 'type': 'tavern', 'parent_hint': '',
       'description_fragment': ''})

check('norm_strips_a',
      _normalize_location({'name': 'A Hidden Cave'}),
      {'name': 'Hidden Cave', 'type': '', 'parent_hint': '',
       'description_fragment': ''})

check('norm_strips_an',
      _normalize_location({'name': 'An Old Shrine'}),
      {'name': 'Old Shrine', 'type': '', 'parent_hint': '',
       'description_fragment': ''})

check('norm_keeps_theramore',
      _normalize_location({'name': 'Theramore'}),
      {'name': 'Theramore', 'type': '', 'parent_hint': '',
       'description_fragment': ''})

# parent_hint also gets canonicalized
check('norm_parent_hint_canonicalized',
      _normalize_location({'name': 'Rusty Anchor',
                           'parent_hint': 'The Redhaven'}),
      {'name': 'Rusty Anchor', 'type': '', 'parent_hint': 'Redhaven',
       'description_fragment': ''})

check('norm_non_string_field',
      _normalize_location({'name': 'Redhaven', 'type': 42}),
      {'name': 'Redhaven', 'type': '', 'parent_hint': '',
       'description_fragment': ''})

check('norm_non_string_name',
      _normalize_location({'name': 42}),
      {'name': '', 'type': '', 'parent_hint': '',
       'description_fragment': ''})

check('norm_non_dict',  _normalize_location('Redhaven'), None)
check('norm_none',      _normalize_location(None), None)


# ── JSON extractor ──

check('json_plain',
      _extract_raw_candidates('[{"name":"Redhaven"}]'),
      [{'name': 'Redhaven'}])
check('json_empty',  _extract_raw_candidates('[]'),                 [])
check('json_fence',
      _extract_raw_candidates('```json\n[{"name":"Stoneforge"}]\n```'),
      [{'name': 'Stoneforge'}])
check('json_with_prose',
      _extract_raw_candidates('Sure! [{"name":"Redhaven"}] for you.'),
      [{'name': 'Redhaven'}])
check('json_malformed', _extract_raw_candidates('not json'),        None)
check('json_object',    _extract_raw_candidates('{"name":"X"}'),    None)
check('json_truncated', _extract_raw_candidates('[{"name"'),        None)
check('json_empty_str', _extract_raw_candidates(''),                 None)
check('json_none',      _extract_raw_candidates(None),               None)


# ── parse_locations end-to-end (mocked LLM) ──

def with_response(response):
    global _mock_route_responses
    _mock_route_responses = [response]
    return parse_locations('A scene happens.')


def loc(name, type='', parent_hint='', description_fragment=''):
    return {'name': name, 'type': type, 'parent_hint': parent_hint,
            'description_fragment': description_fragment}


check('e2e_single',
      with_response('[{"name":"Redhaven","type":"town","parent_hint":"","description_fragment":""}]'),
      [loc('Redhaven', type='town')])

check('e2e_empty', with_response('[]'), [])

check('e2e_drops_pure_type',
      with_response('[{"name":"Forest"},{"name":"Whispering Woods"}]'),
      [loc('Whispering Woods')])

check('e2e_strips_article',
      with_response('[{"name":"The Rusty Anchor","type":"tavern","parent_hint":"Redhaven"}]'),
      [loc('Rusty Anchor', type='tavern', parent_hint='Redhaven')])

check('e2e_dedupe_after_article_strip',
      with_response('[{"name":"The Rusty Anchor"},{"name":"Rusty Anchor"}]'),
      [loc('Rusty Anchor')])

check('e2e_drops_road',
      with_response('[{"name":"the road"},{"name":"Whispering Woods"}]'),
      [loc('Whispering Woods')])  # "the road" → "road" → stoplist drop

check('e2e_keeps_theramore',
      with_response('[{"name":"Theramore"}]'),
      [loc('Theramore')])

check('e2e_multi_loc',
      with_response('[{"name":"Redhaven"},{"name":"Stoneforge"},{"name":"Whispering Woods"}]'),
      [loc('Redhaven'), loc('Stoneforge'), loc('Whispering Woods')])

check('e2e_drops_kingdom',
      with_response('[{"name":"the Kingdom"},{"name":"the Empire"},{"name":"Redhaven"}]'),
      [loc('Redhaven')])

check('e2e_malformed', with_response('not json'),    [])
check('e2e_object',    with_response('{"name":"X"}'), [])

check('e2e_drop_nondict',
      with_response('[1, "redhaven", {"name":"Stoneforge"}]'),
      [loc('Stoneforge')])

check('e2e_drop_bad_chars',
      with_response('[{"name":"Redhaven","type":"town;rm -rf /"},{"name":"Stoneforge"}]'),
      [loc('Stoneforge')])

check('e2e_normalizes_input',
      with_response('[{"name":"  The   Rusty   Anchor  ","type":"  tavern  "}]'),
      [loc('Rusty Anchor', type='tavern')])

# Empty / None / int narration
_mock_route_responses = []
check('e2e_empty_narr', parse_locations(''),   [])
check('e2e_none_narr',  parse_locations(None), [])
check('e2e_int_narr',   parse_locations(42),   [])

_mock_route_responses = [RuntimeError("provider exhausted")]
check('e2e_route_raises', parse_locations('something'), [])

_mock_route_responses = ['']
check('e2e_route_empty', parse_locations('something'), [])

_mock_route_responses = [None]
check('e2e_route_none', parse_locations('something'), [])


# ── Stoplist sanity ──

for word in ['Forest', 'Road', 'Inn', 'Tavern', 'Castle', 'Dungeon',
             'Kingdom', 'Region', 'North', 'Outside']:
    check_truthy(f'stoplist contains {word!r}',
                 word in _NAME_WHOLE_STOPLIST)


# ── Report ──

print(f"\n{'=' * 50}")
print(f"PASS: {PASS}  FAIL: {FAIL}")
if FAIL:
    print("\nFAILURES:")
    for line in FAILURES:
        print(line)
    sys.exit(1)
print("ALL GREEN")
