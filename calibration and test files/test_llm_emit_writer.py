"""Deterministic tests for Ship A (S36) — LLM-emit directive parser.

Tests `_parse_llm_emit_directive` regex + composition with shipped
`parse_skill_and_dc` + `pending_directive_upsert` end-to-end. Covers
LLM_EMIT_RESOLUTION_BINDING_SPEC.md §7.

Run:
    cd /home/jordaneal/scripts && python3 test_llm_emit_writer.py
"""

import sys
import sqlite3
import tempfile
from pathlib import Path

sys.path.insert(0, '/home/jordaneal/scripts')


# Set up an in-memory test DB before importing the discord bot module
# (which loads dnd_engine and triggers schema init).
import dnd_engine
_tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_tmp.close()
TEST_DB = Path(_tmp.name)
dnd_engine.DB_PATH = TEST_DB

captured = []
dnd_engine.log = lambda m: captured.append(m)
dnd_engine.db_init()

from dnd_engine import (
    pending_directive_upsert, pending_directive_get_active,
    init_scene_state,
)
import dnd_orchestration as orch

# Import after DB setup so import-time side effects don't blow up.
import discord_dnd_bot as bot


def _reset_logs():
    captured.clear()


# ─── Parser-only tests ───────────────────────────────────────────────

def test_parser_single_emit_with_dc():
    r = bot._parse_llm_emit_directive(
        "Donovan leans closer.\n!check perception 15"
    )
    assert r is not None
    assert r['kind'] == 'check'
    assert r['skill_raw'] == 'perception 15'
    assert r['multi_count'] == 1


def test_parser_no_directive_returns_none():
    assert bot._parse_llm_emit_directive("Some narration without a roll.") is None
    assert bot._parse_llm_emit_directive("") is None
    assert bot._parse_llm_emit_directive(None) is None


def test_parser_no_dc_returns_skill_only():
    r = bot._parse_llm_emit_directive("Body text.\n!check perception")
    assert r is not None
    assert r['kind'] == 'check'
    assert r['skill_raw'] == 'perception'


def test_parser_multi_emit_last_match_wins():
    # Spec §11.B.1 — last match is the operative one
    r = bot._parse_llm_emit_directive(
        "First emit !check perception 10\nThen save !save dex 14"
    )
    assert r is not None
    assert r['kind'] == 'save'
    assert r['skill_raw'] == 'dex 14'
    assert r['multi_count'] == 2


def test_parser_multi_word_skill():
    r = bot._parse_llm_emit_directive(
        "Donovan tries !check sleight of hand 12"
    )
    assert r is not None
    assert r['skill_raw'] == 'sleight of hand 12'
    # parse_skill_and_dc handles the multi-word split
    skill, dc = orch.parse_skill_and_dc(r['skill_raw'])
    assert skill == 'sleight of hand'
    assert dc == 12


def test_parser_punctuated_emission_degrades_to_no_dc():
    # `!check perception 15.` — punctuated DC is not pure \d+\s*$
    r = bot._parse_llm_emit_directive("Donovan tries it. !check perception 15.")
    assert r is not None
    assert r['kind'] == 'check'
    # parse_skill_and_dc falls through to no-DC for trailing period
    skill, dc = orch.parse_skill_and_dc(r['skill_raw'])
    assert dc is None, f"expected no-DC degrade, got dc={dc}"


def test_parser_cast_directive():
    r = bot._parse_llm_emit_directive("Cast it. !cast fireball 14")
    assert r is not None
    assert r['kind'] == 'cast'
    assert r['skill_raw'] == 'fireball 14'


def test_parse_skill_and_dc_simple_regression():
    # Regression — Ship 1 helper still works
    assert orch.parse_skill_and_dc('perception 15') == ('perception', 15)
    assert orch.parse_skill_and_dc('perception') == ('perception', None)


def test_parse_skill_and_dc_multi_word_regression():
    assert orch.parse_skill_and_dc('sleight of hand 12') == ('sleight of hand', 12)


# ─── End-to-end composition tests ────────────────────────────────────

def test_end_to_end_parse_then_upsert_writes_row_with_dc():
    init_scene_state(401, 'seed')
    _reset_logs()
    response = (
        "Donovan leans closer and squints at the runes.\n"
        "!check perception 15"
    )
    r = bot._parse_llm_emit_directive(response)
    assert r is not None
    skill, dc = orch.parse_skill_and_dc(r['skill_raw'])
    pending_directive_upsert(
        campaign_id=401,
        actor_name='Donovan Ruby',
        check_type=skill,
        source_message_id='bot-msg-1',
        ttl_seconds=300,
        dc=dc,
    )
    row = pending_directive_get_active(401)
    assert row is not None
    assert row['actor_name'] == 'Donovan Ruby'
    assert row['check_type'] == 'perception'
    assert row['dc'] == 15
    assert row['source_message_id'] == 'bot-msg-1'


def test_disjoint_writers_share_pending_directive_upsert():
    # Two upserts simulating disjoint triggers (DM-typed + LLM-emitted)
    # both calling the same helper. Second upsert replaces the first per
    # pending_directive_replaced semantics; the row reflects the latest.
    init_scene_state(402, 'seed')
    _reset_logs()
    # Surface A: simulated DM-typed directive
    pending_directive_upsert(
        campaign_id=402,
        actor_name='Donovan Ruby',
        check_type='perception',
        source_message_id='human-msg-id',
        ttl_seconds=300,
        dc=10,
    )
    # Surface B: simulated LLM-emit a moment later
    pending_directive_upsert(
        campaign_id=402,
        actor_name='Donovan Ruby',
        check_type='perception',
        source_message_id='bot-msg-id',
        ttl_seconds=300,
        dc=15,
    )
    row = pending_directive_get_active(402)
    assert row is not None
    assert row['dc'] == 15, f"second upsert should win: {row}"
    assert row['source_message_id'] == 'bot-msg-id'


# ─── Wrong-skill aside helper ────────────────────────────────────────

def test_wrong_skill_aside_copy_template():
    aside = bot._wrong_skill_aside('perception', 'insight')
    assert 'perception' in aside
    assert 'insight' in aside
    assert 'not consumed' in aside
    assert 'Wait for' in aside


# ─── Ship A live-verify patch (S36 #3 + #5) — DC strip ──────────────

def test_dc_strip_check_with_dc():
    out = bot._strip_dc_from_llm_emit(
        "Donovan leans closer.\n!check perception 15"
    )
    assert out == "Donovan leans closer.\n!check perception"


def test_dc_strip_operator_locked_bold_format():
    """S36 #5 — operator-locked `**!check skill DC : Name**` format.
    Strip preserves bold markers and the colon+name suffix."""
    out = bot._strip_dc_from_llm_emit(
        "Donovan leans closer.\n\n**!check perception 15 : Donovan**"
    )
    assert out == "Donovan leans closer.\n\n**!check perception : Donovan**"


def test_dc_strip_bold_multi_word_skill():
    out = bot._strip_dc_from_llm_emit("**!check sleight of hand 12 : Donovan**")
    assert out == "**!check sleight of hand : Donovan**"


def test_parser_handles_bold_colon_name_format():
    r = bot._parse_llm_emit_directive(
        "Donovan moves.\n\n**!check perception 15 : Donovan**"
    )
    assert r is not None
    assert r['kind'] == 'check'
    # skill_raw stops at colon/bold-close — doesn't include `: Donovan`
    assert r['skill_raw'] == 'perception 15'


def test_dc_strip_multi_word_skill():
    out = bot._strip_dc_from_llm_emit(
        "Try it. !check sleight of hand 12"
    )
    assert out == "Try it. !check sleight of hand"


def test_dc_strip_save():
    out = bot._strip_dc_from_llm_emit("Save it!\n!save dex 14")
    assert out == "Save it!\n!save dex"


def test_dc_strip_no_dc_unchanged():
    text = "!check perception"
    assert bot._strip_dc_from_llm_emit(text) == text


def test_dc_strip_cast_unchanged():
    # !cast accepts trailing integer as spell level override; don't strip
    text = "Body. !cast fireball 14"
    assert bot._strip_dc_from_llm_emit(text) == text


def test_dc_strip_idempotent():
    once = bot._strip_dc_from_llm_emit("!check perception 15")
    twice = bot._strip_dc_from_llm_emit(once)
    assert once == twice == "!check perception"


def test_dc_strip_handles_multi_emit():
    out = bot._strip_dc_from_llm_emit(
        "Multi: !check perception 10\nand !save dex 14"
    )
    assert out == "Multi: !check perception\nand !save dex"


def test_dc_strip_empty_input():
    assert bot._strip_dc_from_llm_emit("") == ""
    assert bot._strip_dc_from_llm_emit(None) is None


# ─── Runner ──────────────────────────────────────────────────────────

if __name__ == '__main__':
    import traceback
    funcs = [v for k, v in sorted(globals().items())
             if k.startswith('test_') and callable(v)]
    failures = []
    for fn in funcs:
        try:
            fn()
            print(f"  ok   {fn.__name__}")
        except AssertionError as e:
            failures.append((fn.__name__, repr(e)))
            print(f"  FAIL {fn.__name__}: {e!r}")
        except Exception as e:
            failures.append((fn.__name__, repr(e)))
            print(f"  ERR  {fn.__name__}: {e!r}")
            traceback.print_exc()
    if failures:
        print(f"\n{len(failures)} failure(s)")
        sys.exit(1)
    print(f"\n{len(funcs)} tests passed.")
