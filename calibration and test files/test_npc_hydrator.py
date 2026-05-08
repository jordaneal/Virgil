"""Pure-function tests for npc_hydrator.py — Track 6 #4.

No DB, no Discord. All 16 CR bands + normalize_cr + fallback_stats.

Run:
    cd /home/jordaneal/scripts && python3 test_npc_hydrator.py
"""

import sys
sys.path.insert(0, '/home/jordaneal/scripts')

from npc_hydrator import hydrate_npc_stats, fallback_stats, normalize_cr, _CR_BANDS, _CR_KEYS


def test_cr_1_4_returns_correct_band():
    s = hydrate_npc_stats('1/4')
    assert s == {'hp_max': 13, 'ac': 13, 'attack_bonus': 3,
                 'damage_dice': '1d8', 'save_bonus': 2, 'init_mod': 1}, s


def test_all_16_cr_bands_return_six_key_dicts():
    for cr in _CR_BANDS:
        s = hydrate_npc_stats(cr)
        assert set(s.keys()) == set(_CR_KEYS), f"bad keys for CR={cr}: {s.keys()}"
        assert s is not None


def test_unrecognized_cr_raises_value_error():
    try:
        hydrate_npc_stats('99')
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_unrecognized_string_raises_value_error():
    try:
        hydrate_npc_stats('cr5')
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_fallback_stats_returns_cr_1_4():
    assert fallback_stats() == hydrate_npc_stats('1/4')


def test_normalize_decimal_0_25():
    assert normalize_cr('0.25') == '1/4'


def test_normalize_half():
    assert normalize_cr('half') == '1/2'


def test_normalize_fraction_1_8():
    assert normalize_cr('1/8') == '1/8'


def test_normalize_integer_12():
    assert normalize_cr('12') == '12'


def test_normalize_unknown_returns_none():
    assert normalize_cr('99') is None


def test_normalize_quarter():
    assert normalize_cr('quarter') == '1/4'


def test_normalize_decimal_0_5():
    assert normalize_cr('0.5') == '1/2'


def test_normalize_unicode_one_half():
    assert normalize_cr('½') == '1/2'


def test_normalize_unicode_one_quarter():
    assert normalize_cr('¼') == '1/4'


def test_normalize_unicode_one_eighth():
    assert normalize_cr('⅛') == '1/8'


def test_normalize_strips_whitespace():
    assert normalize_cr('  1/4  ') == '1/4'


def test_hydrate_npc_stats_deterministic():
    a = hydrate_npc_stats('2')
    b = hydrate_npc_stats('2')
    assert a == b


def test_hydrate_npc_stats_does_not_mutate_module_state():
    s1 = hydrate_npc_stats('3')
    s2 = hydrate_npc_stats('3')
    s1['hp_max'] = 9999
    s3 = hydrate_npc_stats('3')
    assert s3['hp_max'] == 70, "mutation leaked into module state"


def test_cr_0_band():
    s = hydrate_npc_stats('0')
    assert s['hp_max'] == 3
    assert s['ac'] == 10


def test_cr_1_2_band():
    s = hydrate_npc_stats('1/2')
    assert s['hp_max'] == 22
    assert s['attack_bonus'] == 4
    assert s['damage_dice'] == '1d8+2'


def test_cr_12_band():
    s = hydrate_npc_stats('12')
    assert s['hp_max'] == 240
    assert s['ac'] == 17


def test_normalize_0_125():
    assert normalize_cr('0.125') == '1/8'


def test_normalize_eighth():
    assert normalize_cr('eighth') == '1/8'


def test_normalize_case_insensitive():
    assert normalize_cr('HALF') == '1/2'
    assert normalize_cr('Quarter') == '1/4'


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
