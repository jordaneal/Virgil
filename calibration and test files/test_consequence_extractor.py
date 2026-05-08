"""Deterministic unit tests for consequence_extractor.py.

Covers shape validation only — _normalize_proposal, _validate_proposal,
and _extract_raw_array. The LLM-call paths (parse_consequences_player /
parse_consequences_dm) are integration-tested separately at the bot level
and live-verified after deploy.

Run:
    cd /home/jordaneal/scripts && python3 test_consequence_extractor.py
"""

import sys
sys.path.insert(0, '/home/jordaneal/scripts')

# Suppress engine log spam.
import dnd_engine
dnd_engine.log = lambda m: None

import consequence_extractor
from consequence_extractor import (
    _normalize_proposal, _validate_proposal, _extract_raw_array,
    _check_ooc_marker, _OOC_MARKER_PATTERNS,
    parse_consequences_player, parse_consequences_dm,
    PLAYER_SYSTEM_PROMPT, DM_SYSTEM_PROMPT, KIND_DEFINITIONS_BLOCK,
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


# ─── _normalize_proposal ─────────────────────────────────────────────────────
n = _normalize_proposal({
    "target": "  Reginald  ",
    "kind": "Threat",
    "severity": 2,
    "summary": "  player threatened the inn  ",
})
check('normalize: target stripped', n['target'], 'Reginald')
check('normalize: kind lowered',    n['kind'],   'threat')
check('normalize: severity int',    n['severity'], 2)
check('normalize: summary stripped', n['summary'], 'player threatened the inn')

# Severity coerced from string.
nstr = _normalize_proposal({"target": "X", "kind": "mercy",
                             "severity": "3", "summary": "ok"})
check('normalize: sev str->int', nstr['severity'], 3)

# Severity garbage -> None.
nbad = _normalize_proposal({"target": "X", "kind": "mercy",
                             "severity": "lots", "summary": "ok"})
check('normalize: sev garbage', nbad['severity'], None)

# Non-string target / kind / summary coerced to ''.
ntype = _normalize_proposal({"target": 42, "kind": None,
                              "severity": 1, "summary": ["nope"]})
check('normalize: target coerced',  ntype['target'],  '')
check('normalize: kind coerced',    ntype['kind'],    '')
check('normalize: summary coerced', ntype['summary'], '')

# Missing fields default to empty.
nmiss = _normalize_proposal({})
check('normalize: missing target',   nmiss['target'],   '')
check('normalize: missing kind',     nmiss['kind'],     '')
check('normalize: missing severity', nmiss['severity'], None)
check('normalize: missing summary',  nmiss['summary'],  '')

# Bad input shape returns None.
check('normalize: not a dict (list)',   _normalize_proposal([1, 2, 3]), None)
check('normalize: not a dict (str)',    _normalize_proposal('hello'),    None)
check('normalize: not a dict (None)',   _normalize_proposal(None),       None)


# ─── _validate_proposal: happy path ──────────────────────────────────────────
ok_p = {"target": "Reginald", "kind": "threat",
        "severity": 2, "summary": "player threatened him"}
ok, reason = _validate_proposal(ok_p)
check('valid: ok',     ok, True)
check('valid: reason', reason, None)


# ─── _validate_proposal: reject paths ────────────────────────────────────────
def expect_reject(label, prop, want_reason):
    ok, reason = _validate_proposal(prop)
    check(f'{label}: rejected', ok, False)
    check(f'{label}: reason',   reason, want_reason)


expect_reject('not a dict', "string here", 'bad_shape')
expect_reject('missing target', {"kind": "mercy", "severity": 1, "summary": "x"},
              'bad_shape')
expect_reject('missing kind',
              {"target": "X", "severity": 1, "summary": "x"},
              'bad_shape')
expect_reject('missing severity',
              {"target": "X", "kind": "mercy", "summary": "x"},
              'bad_shape')
expect_reject('missing summary',
              {"target": "X", "kind": "mercy", "severity": 1},
              'bad_shape')

expect_reject('empty target',
              {"target": "", "kind": "mercy", "severity": 1, "summary": "x"},
              'empty_target')

expect_reject('shell meta in target',
              {"target": "Reginald;rm", "kind": "mercy",
               "severity": 1, "summary": "x"},
              'bad_chars')

expect_reject('control char in summary',
              {"target": "Reginald", "kind": "mercy", "severity": 1,
               "summary": "x\nrm"},
              'bad_chars')

expect_reject('invalid kind (love)',
              {"target": "X", "kind": "love",
               "severity": 1, "summary": "x"},
              'invalid_kind')

expect_reject('invalid kind (THREAT uppercase)',
              {"target": "X", "kind": "THREAT",
               "severity": 1, "summary": "x"},
              'invalid_kind')

expect_reject('severity missing (None)',
              {"target": "X", "kind": "mercy",
               "severity": None, "summary": "x"},
              'severity_missing')

expect_reject('severity oob (0)',
              {"target": "X", "kind": "mercy",
               "severity": 0, "summary": "x"},
              'severity_oob')

expect_reject('severity oob (4)',
              {"target": "X", "kind": "mercy",
               "severity": 4, "summary": "x"},
              'severity_oob')

expect_reject('summary empty',
              {"target": "X", "kind": "mercy",
               "severity": 1, "summary": ""},
              'summary_empty')

# 121 chars (cap is 120).
long_summary = 'a' * 121
expect_reject('summary too long',
              {"target": "X", "kind": "mercy",
               "severity": 1, "summary": long_summary},
              'summary_too_long')

# Summary at exactly 120 chars passes.
ok_120, _ = _validate_proposal(
    {"target": "X", "kind": "mercy", "severity": 1,
     "summary": 'a' * 120}
)
check('summary at cap valid', ok_120, True)


# ─── _extract_raw_array ──────────────────────────────────────────────────────
check('extract: simple',
      _extract_raw_array('[]'), [])
check('extract: with content',
      _extract_raw_array('[{"target": "X", "kind": "mercy"}]'),
      [{"target": "X", "kind": "mercy"}])

# Markdown-fenced response.
fenced = '```json\n[{"target":"R","kind":"threat"}]\n```'
parsed = _extract_raw_array(fenced)
check('extract: fenced', parsed, [{"target": "R", "kind": "threat"}])

fenced_plain = '```\n[]\n```'
check('extract: fenced plain', _extract_raw_array(fenced_plain), [])

# With prose wrapper before/after.
chatty = 'Sure, here you go: [{"target":"X","kind":"mercy"}]\nLet me know if I can help further.'
check('extract: chatty wrapper',
      _extract_raw_array(chatty),
      [{"target": "X", "kind": "mercy"}])

# Bad JSON returns None.
check('extract: not JSON', _extract_raw_array('hello world'), None)
check('extract: malformed array',
      _extract_raw_array('[oops]'), None)
check('extract: object not array',
      _extract_raw_array('{"target": "X"}'), None)
check('extract: empty input',
      _extract_raw_array(''), None)
check('extract: None input',
      _extract_raw_array(None), None)


# ─── Prompts contain locked verbatim taxonomy (§1.3 / §5.2) ──────────────────
for prompt_name, prompt in [('player', PLAYER_SYSTEM_PROMPT),
                             ('dm', DM_SYSTEM_PROMPT)]:
    for kind, definition in [
        ('threat',   'credible future harm or pressure (not executed action)'),
        ('mercy',    'restraint when harm was available'),
        ('cruelty',  'harm exceeding necessity'),
        ('betrayal', 'violation of trust/expectation'),
        ('promise',  'explicit commitment affecting future state'),
        ('alliance', 'mutual alignment / shared objective formation'),
    ]:
        check(f'{prompt_name} prompt has {kind} definition verbatim',
              definition in prompt, True)

# DM prompt explicitly forbids re-capture of player commitments.
check_truthy('DM prompt: re-capture warning',
              'DO NOT RE-CAPTURE PLAYER COMMITMENTS' in DM_SYSTEM_PROMPT)


# ─── _check_ooc_marker (S21) ─────────────────────────────────────────────────
# Pure-function tests on the marker matcher. No LLM, no monkey-patching.

# Each leading-marker shape returns its named tag.
check('ooc: ((',                _check_ooc_marker('((wait BRB))'),         'paren')
check('ooc: (( with ws',        _check_ooc_marker('   ((brb))'),           'paren')
check('ooc: [OOC]',              _check_ooc_marker('[OOC] real quick'),    'bracket')
check('ooc: [OOC] with ws',     _check_ooc_marker('  [OOC] hi'),          'bracket')
check('ooc: OOC:',                _check_ooc_marker('OOC: question'),       'colon')
check('ooc: OOC: with ws',      _check_ooc_marker('   OOC: question'),    'colon')
check('ooc: //',                  _check_ooc_marker('// just chatting'),    'slash')
check('ooc: // with ws',         _check_ooc_marker('   // chatting'),      'slash')

# Case-insensitivity for [OOC] and OOC:
check('ooc: [ooc] lower',       _check_ooc_marker('[ooc] hi'),            'bracket')
check('ooc: [Ooc] mixed',       _check_ooc_marker('[Ooc] hi'),            'bracket')
check('ooc: [OoC] mixed',       _check_ooc_marker('[OoC] hi'),            'bracket')
check('ooc: ooc: lower',         _check_ooc_marker('ooc: hi'),             'colon')
check('ooc: Ooc: mixed',         _check_ooc_marker('Ooc: hi'),             'colon')
check('ooc: oOc: mixed',         _check_ooc_marker('oOc: hi'),             'colon')

# Unmarked text returns None — must let parser run normally.
check('ooc: plain IC',           _check_ooc_marker('I attack the goblin'),     None)
check('ooc: I (',                _check_ooc_marker('I (try to) sneak past'),   None)
check('ooc: empty',              _check_ooc_marker(''),                          None)
check('ooc: whitespace only',    _check_ooc_marker('     '),                     None)
check('ooc: None',                _check_ooc_marker(None),                        None)

# Mid-message OOC NOT detected — leading-position-only filter (out of scope v1).
check('ooc: mid (( not detected',
      _check_ooc_marker('I swing the sword ((wait, brb))'),
      None)
check('ooc: mid OOC: not detected',
      _check_ooc_marker('I attack OOC: actually wait'),
      None)

# `OOC` without colon should NOT trigger the colon matcher.
check('ooc: OOC alone (no colon)',
      _check_ooc_marker('OOC about something'),
      None)
# `[OOC` without closing bracket should NOT trigger.
check('ooc: [OOC partial',
      _check_ooc_marker('[OOC unclosed'),
      None)

# A single `(` is NOT enough — two parens required.
check('ooc: single ( not detected',
      _check_ooc_marker('(my character is unsure)'),
      None)
# A single `/` is NOT enough — two slashes required.
check('ooc: single / not detected',
      _check_ooc_marker('/me waves'),
      None)


# ─── parse_consequences_player short-circuits on marker (S21) ────────────────
# Confirms (a) marker text returns [] without invoking the LLM, (b) emits the
# diagnostic log line, (c) the DM parser does NOT have the filter applied.

class _LogCapture:
    def __init__(self):
        self.lines = []
    def __call__(self, msg):
        self.lines.append(str(msg))

class _RouteCallTracker:
    def __init__(self, response='[]'):
        self.calls = 0
        self.response = response
    def __call__(self, *args, **kwargs):
        self.calls += 1
        return (self.response, 'mock_provider')


# Player parser: marker text → no route call, returns [], logs filter line.
log_cap = _LogCapture()
route_mock = _RouteCallTracker()
saved_log = consequence_extractor.log
saved_route = consequence_extractor.route
consequence_extractor.log = log_cap
consequence_extractor.route = route_mock

result = parse_consequences_player('OOC: real quick — bio break', campaign_id=42)
check('player short-circuit: returns []',     result, [])
check('player short-circuit: no route call',  route_mock.calls, 0)
filter_lines = [ln for ln in log_cap.lines if 'consequence_ooc_filtered' in ln]
check('player short-circuit: 1 filter log',   len(filter_lines), 1)
check_truthy('player short-circuit: has campaign tag', 'campaign=42' in filter_lines[0])
check_truthy('player short-circuit: has reason tag',   'reason=colon' in filter_lines[0])
check_truthy('player short-circuit: has text snippet', 'real quick' in filter_lines[0])

# Each marker shape produces the right reason tag.
for marker_text, expected_reason in [
    ('((brb))',         'paren'),
    ('[OOC] hi',        'bracket'),
    ('OOC: ping',       'colon'),
    ('// chatting',     'slash'),
]:
    log_cap = _LogCapture()
    route_mock = _RouteCallTracker()
    consequence_extractor.log = log_cap
    consequence_extractor.route = route_mock
    parse_consequences_player(marker_text, campaign_id=99)
    filter_lines = [ln for ln in log_cap.lines if 'consequence_ooc_filtered' in ln]
    check(f'player marker {expected_reason}: 1 log',   len(filter_lines), 1)
    check_truthy(f'player marker {expected_reason}: reason tag',
                 f'reason={expected_reason}' in filter_lines[0])
    check(f'player marker {expected_reason}: no route', route_mock.calls, 0)

# Player parser WITHOUT marker → does call route (filter does not short-circuit).
log_cap = _LogCapture()
route_mock = _RouteCallTracker(response='[]')
consequence_extractor.log = log_cap
consequence_extractor.route = route_mock
parse_consequences_player('I attack the goblin', campaign_id=42)
check('player unmarked: route called', route_mock.calls, 1)
filter_lines = [ln for ln in log_cap.lines if 'consequence_ooc_filtered' in ln]
check('player unmarked: no filter log', len(filter_lines), 0)

# DM parser: filter does NOT apply — marker text still calls route.
log_cap = _LogCapture()
route_mock = _RouteCallTracker(response='[]')
consequence_extractor.log = log_cap
consequence_extractor.route = route_mock
parse_consequences_dm('OOC: this would be filtered on the player side')
check('dm parser: marker text still calls route', route_mock.calls, 1)
filter_lines = [ln for ln in log_cap.lines if 'consequence_ooc_filtered' in ln]
check('dm parser: no filter log', len(filter_lines), 0)

# DM parser with [OOC] marker — also still calls route (defense in depth).
log_cap = _LogCapture()
route_mock = _RouteCallTracker(response='[]')
consequence_extractor.log = log_cap
consequence_extractor.route = route_mock
parse_consequences_dm('[OOC] meta-content from LLM')
check('dm parser: [OOC] still calls route', route_mock.calls, 1)

# Optional campaign_id: missing/None doesn't crash, log uses '?' placeholder.
log_cap = _LogCapture()
route_mock = _RouteCallTracker()
consequence_extractor.log = log_cap
consequence_extractor.route = route_mock
parse_consequences_player('// no campaign id supplied')
filter_lines = [ln for ln in log_cap.lines if 'consequence_ooc_filtered' in ln]
check('no campaign_id: 1 log', len(filter_lines), 1)
check_truthy('no campaign_id: ? placeholder', 'campaign=?' in filter_lines[0])

# Restore real log + route for any downstream code in this process.
consequence_extractor.log = saved_log
consequence_extractor.route = saved_route


# ─── final report ────────────────────────────────────────────────────────────
print(f"PASS: {PASS}  FAIL: {FAIL}")
if FAIL:
    print("\nFailures:")
    for f in FAILURES:
        print(f)

sys.exit(0 if FAIL == 0 else 1)
