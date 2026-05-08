"""Deterministic tests for loot_tables module (Track 4 #2, Session 22).

Pure functions, no DB. Coin rolls seeded for reproducibility.

Run:
    cd /home/jordaneal/scripts && python3 test_loot_tables.py
"""

import sys
import random

sys.path.insert(0, '/home/jordaneal/scripts')

import loot_tables as lt


# ─── Substring matching ─────────────────────────────────────────────

def test_exact_key_match_goblin():
    out = lt.generate_loot('goblin')
    assert out['table_key'] == 'goblin'
    assert 'rusty shortsword' in out['items']


def test_substring_match_goblin_patrol():
    out = lt.generate_loot('Goblin Patrol')
    assert out['table_key'] == 'goblin'


def test_case_insensitive_match():
    out = lt.generate_loot('GOBLIN')
    assert out['table_key'] == 'goblin'


def test_substring_match_bandit_chieftain():
    out = lt.generate_loot('Bandit Chieftain')
    assert out['table_key'] == 'bandit'


def test_unknown_creature_falls_through_to_default():
    out = lt.generate_loot('unknown_creature')
    assert out['table_key'] == '_default'
    assert out['items'] == ['common gear']


def test_empty_creature_name_returns_default():
    out = lt.generate_loot('')
    assert out['table_key'] == '_default'


def test_none_creature_name_returns_default():
    # generate_loot guards against None via `creature_name or ''`
    out = lt.generate_loot(None)  # type: ignore[arg-type]
    assert out['table_key'] == '_default'
    assert out['creature'] == ''


# ─── Coin rolling ───────────────────────────────────────────────────

def test_roll_coin_2d6_sp_in_range():
    random.seed(42)
    table = lt.LOOT_TABLES['goblin']
    coin = lt._roll_coin(table['coin'])
    assert coin is not None
    assert coin['denom'] == 'sp'
    assert 2 <= coin['amount'] <= 12


def test_roll_coin_none_passes_through():
    coin = lt._roll_coin(None)
    assert coin is None


def test_roll_coin_empty_string_passes_through():
    coin = lt._roll_coin('')
    assert coin is None


def test_roll_coin_unparseable_returns_none():
    coin = lt._roll_coin('not a dice expr')
    assert coin is None


def test_roll_coin_zero_dice_returns_none():
    # 0d6 is a degenerate input — handled by the n <= 0 guard.
    coin = lt._roll_coin('0d6 sp')
    assert coin is None


def test_roll_coin_gp_denom():
    random.seed(0)
    coin = lt._roll_coin('2d4 gp')
    assert coin['denom'] == 'gp'
    assert 2 <= coin['amount'] <= 8


def test_roll_coin_uppercase_denom_normalized():
    coin = lt._roll_coin('1d4 SP')
    assert coin is not None
    assert coin['denom'] == 'sp'


# ─── generate_loot integration ──────────────────────────────────────

def test_wolf_has_no_coin():
    out = lt.generate_loot('wolf')
    assert out['coin'] is None
    assert 'wolf pelt' in out['items']


def test_skeleton_drops_bone_fragments():
    out = lt.generate_loot('skeleton')
    assert out['table_key'] == 'skeleton'
    assert 'bone fragments' in out['items']


def test_cultist_drops_gp():
    random.seed(123)
    out = lt.generate_loot('cultist')
    assert out['table_key'] == 'cultist'
    assert out['coin']['denom'] == 'gp'


def test_creature_field_preserves_input_casing():
    # generate_loot reports the original creature name back, so logs read
    # naturally even when the matched key is lowercase.
    out = lt.generate_loot('Goblin Patrol')
    assert out['creature'] == 'Goblin Patrol'


def test_items_returned_as_independent_copy():
    out1 = lt.generate_loot('goblin')
    out1['items'].append('mutation')
    out2 = lt.generate_loot('goblin')
    assert 'mutation' not in out2['items']


def test_deterministic_with_seed():
    random.seed(7)
    a = lt.generate_loot('goblin')
    random.seed(7)
    b = lt.generate_loot('goblin')
    assert a['coin'] == b['coin']


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
