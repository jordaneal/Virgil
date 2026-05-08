"""Engine helper tests for npc_hydrate_stats() — Track 6 #4.

In-memory DB. Tests source-based fill rule, idempotency, explicit overwrite,
generic_fallback hp_max exclusion, cr_str propagation.

Run:
    cd /home/jordaneal/scripts && python3 test_npc_hydrate_stats.py
"""

import sys
import sqlite3
import tempfile
from pathlib import Path

sys.path.insert(0, '/home/jordaneal/scripts')

import dnd_engine
_tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_tmp.close()
TEST_DB = Path(_tmp.name)
dnd_engine.DB_PATH = TEST_DB

captured = []
dnd_engine.log = lambda m: captured.append(m)
dnd_engine.db_init()

from dnd_engine import (
    npc_upsert, npc_get_by_name, stat_incomplete,
    npc_hydrate_stats, create_campaign,
)

GUILD = 'test-guild-hydrate'


def _campaign():
    return create_campaign(GUILD, 'TestCampaign')


def _fresh_npc(campaign_id, name='Garrik'):
    npc_upsert(campaign_id, name, skeleton_origin=False)
    return npc_get_by_name(campaign_id, name)


# ─── stat_incomplete predicate ───────────────────────────────────────

def test_stat_incomplete_null_npc():
    cid = _campaign()
    npc = _fresh_npc(cid, 'Dummy1')
    assert stat_incomplete(npc) is True


def test_stat_incomplete_fully_hydrated():
    cid = _campaign()
    npc_upsert(cid, 'Dummy2')
    npc_hydrate_stats(cid, 'Dummy2', cr_str='1/4', source='hook')
    npc = npc_get_by_name(cid, 'Dummy2')
    assert stat_incomplete(npc) is False


# ─── hook source: idempotent NULL-fill ───────────────────────────────

def test_hook_fills_all_null_cols():
    cid = _campaign()
    npc_upsert(cid, 'Orc1')
    wrote, sigs = npc_hydrate_stats(cid, 'Orc1', cr_str='1/4', source='hook')
    assert wrote is True
    npc = npc_get_by_name(cid, 'Orc1')
    assert npc['hp_max'] == 13
    assert npc['ac'] == 13
    assert npc['attack_bonus'] == 3
    assert npc['damage_dice'] == '1d8'
    assert npc['cr_str'] == '1/4'


def test_hook_does_not_overwrite_populated_hp_max():
    cid = _campaign()
    npc_upsert(cid, 'Orc2')
    # Manually write hp_max.
    conn = sqlite3.connect(TEST_DB)
    conn.execute("UPDATE dnd_npcs SET hp_max=99 WHERE campaign_id=? AND canonical_name='Orc2'", (cid,))
    conn.commit(); conn.close()
    npc_hydrate_stats(cid, 'Orc2', cr_str='1/4', source='hook')
    npc = npc_get_by_name(cid, 'Orc2')
    assert npc['hp_max'] == 99, "hook must not overwrite DM-authored hp_max"


def test_hook_fills_only_null_atk_when_others_present():
    cid = _campaign()
    npc_upsert(cid, 'Orc3')
    conn = sqlite3.connect(TEST_DB)
    conn.execute(
        "UPDATE dnd_npcs SET hp_max=99, ac=18 WHERE campaign_id=? AND canonical_name='Orc3'",
        (cid,)
    )
    conn.commit(); conn.close()
    npc_hydrate_stats(cid, 'Orc3', cr_str='1/4', source='hook')
    npc = npc_get_by_name(cid, 'Orc3')
    assert npc['hp_max'] == 99
    assert npc['ac'] == 18
    assert npc['attack_bonus'] == 3


def test_hook_fully_hydrated_returns_miss():
    cid = _campaign()
    npc_upsert(cid, 'Orc4')
    npc_hydrate_stats(cid, 'Orc4', cr_str='1/4', source='hook')
    wrote, sigs = npc_hydrate_stats(cid, 'Orc4', cr_str='1/4', source='hook')
    assert wrote is False
    assert sigs['source'] == 'miss'


def test_two_consecutive_calls_idempotent():
    cid = _campaign()
    npc_upsert(cid, 'Orc5')
    npc_hydrate_stats(cid, 'Orc5', cr_str='2', source='hook')
    wrote, _ = npc_hydrate_stats(cid, 'Orc5', cr_str='2', source='hook')
    assert wrote is False


def test_cr_1_2_values_correct():
    cid = _campaign()
    npc_upsert(cid, 'Bandit1')
    npc_hydrate_stats(cid, 'Bandit1', cr_str='1/2', source='hook')
    npc = npc_get_by_name(cid, 'Bandit1')
    assert npc['hp_max'] == 22
    assert npc['ac'] == 13
    assert npc['attack_bonus'] == 4
    assert npc['damage_dice'] == '1d8+2'


def test_cr_str_written_after_hook():
    cid = _campaign()
    npc_upsert(cid, 'Troll1')
    npc_hydrate_stats(cid, 'Troll1', cr_str='5', source='hook')
    npc = npc_get_by_name(cid, 'Troll1')
    assert npc['cr_str'] == '5'


# ─── adhoc source ────────────────────────────────────────────────────

def test_adhoc_creates_row_and_hydrates():
    cid = _campaign()
    assert npc_get_by_name(cid, 'Adhoc1') is None
    wrote, _ = npc_hydrate_stats(cid, 'Adhoc1', cr_str='1', source='adhoc')
    assert wrote is True
    npc = npc_get_by_name(cid, 'Adhoc1')
    assert npc is not None
    assert npc['hp_max'] == 35


# ─── generic_fallback source ─────────────────────────────────────────

def test_generic_fallback_writes_all_except_hp_max():
    cid = _campaign()
    npc_upsert(cid, 'Gfb1')
    npc_hydrate_stats(cid, 'Gfb1', cr_str=None, source='generic_fallback')
    npc = npc_get_by_name(cid, 'Gfb1')
    assert npc['hp_max'] is None, "generic_fallback must NOT write hp_max"
    assert npc['ac'] == 13
    assert npc['attack_bonus'] == 3
    assert npc['damage_dice'] == '1d8'
    assert npc['save_bonus'] == 2
    assert npc['init_mod'] == 1


def test_generic_fallback_writes_cr_str_1_4():
    cid = _campaign()
    npc_upsert(cid, 'Gfb2')
    npc_hydrate_stats(cid, 'Gfb2', cr_str=None, source='generic_fallback')
    npc = npc_get_by_name(cid, 'Gfb2')
    assert npc['cr_str'] == '1/4'


# ─── explicit_hydrate source (§11.H always-overwrite) ────────────────

def test_explicit_hydrate_overwrites_all_populated_fields():
    cid = _campaign()
    npc_upsert(cid, 'ExH1')
    npc_hydrate_stats(cid, 'ExH1', cr_str='1/4', source='hook')
    # Now overwrite with CR 5
    wrote, _ = npc_hydrate_stats(cid, 'ExH1', cr_str='5', source='explicit_hydrate')
    npc = npc_get_by_name(cid, 'ExH1')
    assert npc['hp_max'] == 115
    assert npc['ac'] == 15
    assert npc['attack_bonus'] == 7
    assert npc['cr_str'] == '5'


def test_explicit_hydrate_on_generic_fallback_replaces_all():
    cid = _campaign()
    npc_upsert(cid, 'ExH2')
    npc_hydrate_stats(cid, 'ExH2', cr_str=None, source='generic_fallback')
    # generic_fallback left hp_max NULL; explicit should fill it
    npc_hydrate_stats(cid, 'ExH2', cr_str='2', source='explicit_hydrate')
    npc = npc_get_by_name(cid, 'ExH2')
    assert npc['hp_max'] == 52
    assert npc['ac'] == 13
    assert npc['attack_bonus'] == 5
    assert npc['cr_str'] == '2'


def test_explicit_hydrate_same_values_returns_no_change():
    cid = _campaign()
    npc_upsert(cid, 'ExH3')
    npc_hydrate_stats(cid, 'ExH3', cr_str='1/4', source='explicit_hydrate')
    wrote, _ = npc_hydrate_stats(cid, 'ExH3', cr_str='1/4', source='explicit_hydrate')
    assert wrote is False


# ─── §11.L regression: engine does NOT resolve None for non-gfb sources ──

def test_engine_does_not_resolve_none_cr_for_hook():
    cid = _campaign()
    npc_upsert(cid, 'CrNone1')
    try:
        npc_hydrate_stats(cid, 'CrNone1', cr_str=None, source='hook')
        npc = npc_get_by_name(cid, 'CrNone1')
        # If engine silently filled stats from None (forbidden), this fails.
        assert stat_incomplete(npc), (
            "Engine must NOT resolve cr_str=None to fallback for source='hook' (§11.L)"
        )
    except (ValueError, TypeError):
        pass  # Raising is also acceptable — engine should not silently fill.


# ─── multi-word names ────────────────────────────────────────────────

def test_multi_word_name_handled():
    cid = _campaign()
    npc_upsert(cid, 'Garrik the Smith')
    wrote, _ = npc_hydrate_stats(cid, 'Garrik the Smith', cr_str='1/2', source='hook')
    assert wrote is True
    npc = npc_get_by_name(cid, 'Garrik the Smith')
    assert npc is not None
    assert npc['hp_max'] == 22


def test_generic_fallback_creates_row_when_none_exists():
    """Regression: generic_fallback on a brand-new NPC must create the row.

    Bug: npc_upsert was only called for source='adhoc', so a first-time
    generic_fallback call returned (False, error=row_not_found) and the NPC
    never landed in dnd_npcs — invisible to autocomplete and /hydrate.
    """
    cid = _campaign()
    assert npc_get_by_name(cid, 'BrandNewGfb') is None
    wrote, signals = npc_hydrate_stats(cid, 'BrandNewGfb', cr_str=None, source='generic_fallback')
    npc = npc_get_by_name(cid, 'BrandNewGfb')
    assert npc is not None, "generic_fallback must create the row even when no prior row exists"
    assert npc['ac'] == 13       # CR-1/4 fallback default
    assert npc['hp_max'] is None # hp_max always NULL for generic_fallback
    assert signals.get('error') != 'row_not_found'


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
