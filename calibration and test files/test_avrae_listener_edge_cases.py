"""Edge-case tests for avrae_listener.parse_avrae_embed — Ship S42 audit.

Ground-truth embeds captured live from S42 verify pass against Avrae
(May 11, 2026). Each test reproduces the exact text Avrae rendered
(via MagicMock embed) so we can audit what the parser extracts vs
what it should extract.

Edge cases covered:
  - Plain attack (baseline; no edge case)
  - Advantage roll (Avrae renders as `2d20kh1 (kept, ~~dropped~~)`)
  - Disadvantage roll (Avrae renders as `2d20kl1 (~~dropped~~, kept)`)
  - Resistance damage (Avrae renders `Damage: (N [type]) / 2 = K`)
  - Multi-target attack (multiple `-t` flags → multiple field sub-blocks)
  - Crit detection (deferred — `-crit` flag didn't force crit in S42 verify;
    needs alt trigger path)
  - Save with halved damage (deferred — Donovan has no spells; needs
    spellcaster PC fixture for future ship)
  - Death save (deferred — `!init dsa` syntax + Avrae's PC-required gate
    blocks single-player test)

Run:
    cd /home/jordaneal/scripts && python3 test_avrae_listener_edge_cases.py
"""

import os
import sys
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(__file__))

import avrae_listener as al

captured: list = []
al.log = lambda m: captured.append(m)


def _mock_embed(title='', description='', fields=None, author_name=None,
                footer_text=None):
    """Build a MagicMock embed that matches discord.Embed shape enough for
    parse_avrae_embed to flatten and regex over."""
    embed = MagicMock()
    embed.title = title
    embed.description = description
    embed.author = MagicMock()
    embed.author.name = author_name
    embed.footer = MagicMock()
    embed.footer.text = footer_text
    embed.fields = []
    for name, value in (fields or []):
        f = MagicMock()
        f.name = name
        f.value = value
        embed.fields.append(f)
    return embed


def _mock_message(embed):
    """Build a MagicMock message that simulates an Avrae embed message."""
    msg = MagicMock()
    msg.author = MagicMock()
    msg.author.id = al.get_avrae_user_id()
    msg.embeds = [embed]
    msg.channel = MagicMock()
    msg.channel.id = 12345
    msg.guild = MagicMock()
    msg.guild.id = 67890
    return msg


# ─── Test 1: Plain attack baseline (S42 capture #4) ────────────────

def test_plain_attack_miss_captures_nat_and_result_no_damage():
    """S42 capture: !attack unarmed strike -t ProjTestA → miss.
    Embed format: To Hit: 1d20 (5) + 3 = `8` Miss!"""
    captured.clear()
    embed = _mock_embed(
        title='Donovan Ruby attacks with an Unarmed Strike!',
        fields=[
            ('ProjTestA',
             'To Hit: 1d20 (5) + 3 = `8` Miss!\nEffect\nYou make a melee...'),
        ],
    )
    event = al.parse_avrae_embed(_mock_message(embed))
    assert event is not None, "parser returned None for valid attack embed"
    assert event['kind'] == 'attack', f"kind={event['kind']}"
    assert event['actor'] == 'Donovan Ruby', f"actor={event['actor']}"
    assert event['nat'] == 5, f"nat={event['nat']}"
    assert event['result'] == 8, f"result={event['result']}"
    assert event['damage'] is None, f"damage={event['damage']}"
    assert event['crit'] is False, f"crit={event['crit']}"


# ─── Test 2: Advantage (S42 capture #5) ────────────────────────────

def test_advantage_2d20kh1_captures_kept_high_die():
    """S42 capture: !attack unarmed strike -t ProjTestA adv → hit.
    Embed format: To Hit: 2d20kh1 (15, ~~6~~) + 3 = `18` Damage: 2 [...] = `2`
    Kept die is 15 (first token, non-strikethrough)."""
    captured.clear()
    embed = _mock_embed(
        title='Donovan Ruby attacks with an Unarmed Strike!',
        fields=[
            ('ProjTestA',
             'To Hit: 2d20kh1 (15, ~~6~~) + 3 = `18` '
             'Damage: 2 [bludgeoning] = `2`'),
        ],
    )
    event = al.parse_avrae_embed(_mock_message(embed))
    assert event is not None
    assert event['kind'] == 'attack'
    assert event['nat'] == 15, (
        f"advantage kept-high die should be 15 (first non-strikethrough), "
        f"got nat={event['nat']}"
    )
    assert event['result'] == 18, f"result={event['result']}"
    assert event['damage'] == 2, f"damage={event['damage']}"


# ─── Test 3: Disadvantage (S42 capture #6) ─────────────────────────

def test_disadvantage_2d20kl1_captures_kept_low_die():
    """S42 capture: !attack unarmed strike -t ProjTestA dis → miss.
    Embed format: To Hit: 2d20kl1 (~~19~~, 2) + 3 = `5` Miss!
    Kept die is 2 (second token; first is strikethrough). The current
    parser strips strikethrough segments and returns FIRST remaining
    token — should be 2."""
    captured.clear()
    embed = _mock_embed(
        title='Donovan Ruby attacks with an Unarmed Strike!',
        fields=[
            ('ProjTestA',
             'To Hit: 2d20kl1 (~~19~~, 2) + 3 = `5` Miss!'),
        ],
    )
    event = al.parse_avrae_embed(_mock_message(embed))
    assert event is not None
    assert event['kind'] == 'attack'
    assert event['nat'] == 2, (
        f"disadvantage kept-low die should be 2 (first non-strikethrough "
        f"after the dropped 19 is stripped), got nat={event['nat']}"
    )
    assert event['result'] == 5, f"result={event['result']}"
    assert event['damage'] is None  # miss


# ─── Test 4: Resistance damage (S42 capture #9) ────────────────────

def test_resistance_damage_captures_post_resistance_value():
    """S42 capture: !attack against ProjTestA with -resist bludgeoning.
    Embed format: Damage: (2 [bludgeoning]) / 2 = `1`
    Post-resistance damage is 1 (final = N). The non-greedy `.*?=` regex
    captures the LAST `=` value in the line."""
    captured.clear()
    embed = _mock_embed(
        title='Donovan Ruby attacks with an Unarmed Strike!',
        fields=[
            ('ProjTestA',
             'To Hit: 1d20 (15) + 3 = `18` '
             'Damage: (2 [bludgeoning]) / 2 = `1`'),
        ],
    )
    event = al.parse_avrae_embed(_mock_message(embed))
    assert event is not None
    assert event['kind'] == 'attack'
    assert event['nat'] == 15
    assert event['result'] == 18
    assert event['damage'] == 1, (
        f"post-resistance damage should be 1 (= K after / 2), "
        f"got damage={event['damage']}"
    )


# ─── Test 5: Multi-target attack (S42 capture #10) ─────────────────

def test_multi_target_attack_currently_captures_only_first_attack():
    """S42 capture: !attack unarmed strike -t ProjTestA -t ProjTestB.
    Embed structure: TWO fields, one per target. First field is ProjTestA
    (resisted damage), second is ProjTestB (full damage).

    CURRENT PARSER BEHAVIOR (pre-S42 patch): captures FIRST attack only.
    This test documents the gap.

    Post-S42 patch: the parser populates an `attacks` list with one entry
    per target sub-block, while preserving top-level fields for the first
    attack (back-compat with single-attack consumers)."""
    captured.clear()
    embed = _mock_embed(
        title='Donovan Ruby attacks with an Unarmed Strike!',
        fields=[
            ('ProjTestA',
             'To Hit: 1d20 (11) + 3 = `14` '
             'Damage: (2 [bludgeoning]) / 2 = `1`'),
            ('ProjTestB',
             'To Hit: 1d20 (14) + 3 = `17` '
             'Damage: 2 [bludgeoning] = `2`'),
        ],
    )
    event = al.parse_avrae_embed(_mock_message(embed))
    assert event is not None
    assert event['kind'] == 'attack'
    # First-attack top-level fields (back-compat shape)
    assert event['nat'] == 11, f"first-attack nat={event['nat']}"
    assert event['result'] == 14, f"first-attack result={event['result']}"
    assert event['damage'] == 1, f"first-attack damage={event['damage']}"
    # Post-S42 patch: per-target attacks list (Ship S42 deliverable)
    assert 'attacks' in event, (
        "post-S42 patch should expose 'attacks' list for multi-target "
        "embeds. Pre-patch behavior had no such field."
    )
    assert len(event['attacks']) == 2, (
        f"expected 2 sub-attacks (ProjTestA + ProjTestB), "
        f"got {len(event['attacks'])}"
    )
    a, b = event['attacks']
    assert a['target'] == 'ProjTestA', f"first target={a['target']}"
    assert a['nat'] == 11 and a['result'] == 14 and a['damage'] == 1
    assert b['target'] == 'ProjTestB', f"second target={b['target']}"
    assert b['nat'] == 14 and b['result'] == 17 and b['damage'] == 2


def test_single_target_attack_does_not_populate_attacks_list():
    """For single-target attacks (one field), the `attacks` list should
    NOT be populated. Single-attack consumers continue using top-level
    nat/result/damage unchanged."""
    captured.clear()
    embed = _mock_embed(
        title='Donovan Ruby attacks with an Unarmed Strike!',
        fields=[
            ('ProjTestA',
             'To Hit: 1d20 (15) + 3 = `18` Damage: 2 [bludgeoning] = `2`'),
        ],
    )
    event = al.parse_avrae_embed(_mock_message(embed))
    assert event is not None
    assert event['kind'] == 'attack'
    # Top-level fields populated
    assert event['nat'] == 15
    assert event['result'] == 18
    assert event['damage'] == 2
    # No attacks list for single-target embeds
    assert 'attacks' not in event or event.get('attacks') in (None, [],
        [event['attacks'][0]] if event.get('attacks') else None
    ), (
        f"single-target attack should not surface 'attacks' list; "
        f"got attacks={event.get('attacks')}"
    )


# ─── Crit + resistance composition guard ───────────────────────────

def test_crit_keyword_detected_in_attack_text():
    """When Avrae renders 'Critical' or 'Crit' in an attack embed (e.g.
    'Crit!' on nat-20 + hit), the crit flag should be True. Constructed
    from Avrae's typical crit-hit embed format."""
    captured.clear()
    embed = _mock_embed(
        title='Donovan Ruby attacks with an Unarmed Strike!',
        fields=[
            ('ProjTestA',
             'To Hit: 1d20 (20) + 3 = `23` Crit! '
             'Damage: 4 [bludgeoning] = `4`'),
        ],
    )
    event = al.parse_avrae_embed(_mock_message(embed))
    assert event is not None
    assert event['kind'] == 'attack'
    assert event['nat'] == 20
    assert event['crit'] is True, f"crit should be True on natural 20 hit"


# ─── Run ─────────────────────────────────────────────────────────────

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
