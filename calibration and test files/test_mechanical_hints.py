"""Deterministic unit tests for mechanical_hints.

No network. Mocks cloud_router.route. Tests validator + JSON parser
+ parse_mechanical_hints end-to-end with mocked responses.

Run: python3 test_mechanical_hints.py
"""

import sys
import types

# ── Mock cloud_router + dnd_engine BEFORE importing mechanical_hints ──

_mock_route_responses = []  # populated per-test by expect()

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

de = types.ModuleType('dnd_engine')
de.log = lambda m: None
sys.modules['dnd_engine'] = de

from mechanical_hints import _validate, _extract_json_array, parse_mechanical_hints  # noqa: E402

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

# ── Validator: currency (valid) ──
for cmd in ['!game coin -1gp', '!game coin +5gp', '!game coin -100sp',
            '!game coin +12cp', '!game coin -1ep', '!game coin +2pp']:
    check(f'currency_valid {cmd!r}', _validate(cmd), (True, None))

# ── Validator: currency (malformed) ──
for cmd in ['!game coin -3xx', '!game coin -gp', '!game coin 1gp',
            '!game coin -1.5gp', '!game coin --1gp', '!game coin gp1',
            '!game coin -gp1']:
    check(f'currency_malformed {cmd!r}', _validate(cmd), (False, 'malformed_currency'))

# ── Validator: rests (valid) ──
for cmd in ['!game longrest', '!game shortrest', '!game lr', '!game sr']:
    check(f'rest_valid {cmd!r}', _validate(cmd), (True, None))

# ── Validator: rests (malformed) ──
for cmd, reason in [('!game longrest now', 'not_in_whitelist'),
                    ('!game lr 8h',        'not_in_whitelist'),
                    ('!game lrlong',       'not_in_whitelist'),
                    ('!game rest',         'not_in_whitelist')]:
    check(f'rest_malformed {cmd!r}', _validate(cmd), (False, reason))

# ── Validator: items / inventory (REMOVED — Avrae has no inventory mgmt) ──
# All previously-allowed item commands must now be rejected.
for cmd in ['!item add "Healing Potion"', '!item remove "Sword"',
            '!bag', '!bag list',
            '!coin -1gp', '!sr', '!lr']:  # bare forms also invalid now
    check(f'old_syntax_rejected {cmd!r}',
          _validate(cmd), (False, 'not_in_whitelist'))

# ── Validator: whitelist rejection ──
for cmd in ['!cast fireball', '!attack', '!hp +5', '!init',
            '!level', '!character delete', 'random text', '/sr',
            '!game hp 10', '!game spellslot', '!game deathsave',
            '!game', '!gameXX coin']:
    check(f'not_whitelist {cmd!r}', _validate(cmd), (False, 'not_in_whitelist'))

# ── Validator: empty / non-string ──
for x in ['', '   ', '\n', None, 42, [], {}]:
    check(f'empty/nonstr {x!r}', _validate(x), (False, 'not_in_whitelist'))

# ── Validator: length cap ──
check('length_cap', _validate('!game coin -' + '1' * 250 + 'gp'), (False, 'length_exceeded'))

# ── Validator: shell metachars / control chars ──
for cmd in ['!game coin -1gp; rm -rf /', '!game lr && bad',
            '!game coin -1gp | nc', '!game lr `evil`',
            '!game coin -1gp > out', '!game coin -$(echo)gp',
            '!game coin -1gp\\extra']:
    check(f'metachar {cmd!r}', _validate(cmd), (False, 'invalid_chars'))

# ── Validator: embedded newlines ──
check('newline_lf', _validate('!game coin -1gp\nrm'), (False, 'invalid_chars'))
check('newline_cr', _validate('!game coin -1gp\rrm'), (False, 'invalid_chars'))

# ── Validator: whitespace tolerance ──
check('strip_pad', _validate('  !game coin -1gp  '), (True, None))

# ── JSON extractor ──
check('json_plain',      _extract_json_array('["!coin -1gp"]'),         ['!coin -1gp'])
check('json_empty',      _extract_json_array('[]'),                     [])
check('json_fence_lang', _extract_json_array('```json\n["!sr"]\n```'),  ['!sr'])
check('json_fence_bare', _extract_json_array('```\n[]\n```'),           [])
check('json_with_prose', _extract_json_array('Sure! ["!sr"] for you.'), ['!sr'])
check('json_malformed',  _extract_json_array('not json'),                None)
check('json_object',     _extract_json_array('{"x": 1}'),                None)
check('json_truncated',  _extract_json_array('["!coin'),                 None)
check('json_empty_str',  _extract_json_array(''),                        None)
check('json_none',       _extract_json_array(None),                      None)

# ── parse_mechanical_hints (mocked LLM) ──

def with_response(response):
    global _mock_route_responses
    _mock_route_responses = [response]
    return parse_mechanical_hints('A thing happens in the dungeon.')

check('e2e_single',       with_response('["!game coin -1gp"]'),                          ['!game coin -1gp'])
check('e2e_empty_array',  with_response('[]'),                                            [])
check('e2e_drop_invalid', with_response('["!game coin -1gp", "!cast fireball"]'),       ['!game coin -1gp'])
check('e2e_all_invalid',  with_response('["!cast fireball", "!hp +5"]'),                 [])
check('e2e_old_syntax',   with_response('["!coin -1gp", "!item add \\"X\\""]'),         [])
check('e2e_malformed',    with_response('not json at all'),                              [])
check('e2e_object',       with_response('{"hint": "!game coin -1gp"}'),                  [])
check('e2e_fence',        with_response('```json\n["!game lr"]\n```'),                   ['!game lr'])
check('e2e_nonstring',    with_response('[1, 2, "!game coin -1gp"]'),                   ['!game coin -1gp'])
check('e2e_multi_curr',   with_response('["!game coin -5gp", "!game coin -2sp"]'),
                                                                ['!game coin -5gp', '!game coin -2sp'])

# Empty / None narration short-circuits without consulting route
_mock_route_responses = []
check('e2e_empty_narr', parse_mechanical_hints(''),   [])
check('e2e_none_narr',  parse_mechanical_hints(None), [])

# Route raises → empty list
_mock_route_responses = [RuntimeError("provider exhausted")]
check('e2e_route_raises', parse_mechanical_hints('something happens'), [])

# ── Report ──
print(f"\n{'=' * 50}")
print(f"PASS: {PASS}  FAIL: {FAIL}")
if FAIL:
    print("\nFAILURES:")
    for line in FAILURES:
        print(line)
    sys.exit(1)
print("ALL GREEN")
