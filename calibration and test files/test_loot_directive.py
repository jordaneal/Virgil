"""Deterministic tests for compute_loot_directive (Track 4 #2, Session 22).

Pure function — takes pending_loot row dicts (as returned by get_pending_loot)
and produces (body, signals). No DB, no side effects.

Run:
    cd /home/jordaneal/scripts && python3 test_loot_directive.py
"""

import sys

sys.path.insert(0, '/home/jordaneal/scripts')

import dnd_orchestration as orch


def _row(creature, coin_amount=None, coin_denom=None, items=None, id_=1):
    return {
        'id':          id_,
        'creature':    creature,
        'table_key':   'test',
        'coin_amount': coin_amount,
        'coin_denom':  coin_denom,
        'coin':        ({'amount': coin_amount, 'denom': coin_denom}
                        if coin_amount is not None and coin_denom else None),
        'items':       items or [],
        'created_at':  '2026-05-05T00:00:00',
    }


# ─── Empty input ────────────────────────────────────────────────────

def test_empty_pending_returns_empty_body_fired_false():
    body, signals = orch.compute_loot_directive([])
    assert body == ''
    assert signals['fired'] is False
    assert signals['pending_count'] == 0


def test_none_pending_returns_empty_body():
    body, signals = orch.compute_loot_directive(None)  # type: ignore[arg-type]
    assert body == ''
    assert signals['fired'] is False


# ─── Single creature ────────────────────────────────────────────────

def test_single_creature_fires_directive():
    rows = [_row('Goblin', 3, 'sp', ['rusty shortsword'])]
    body, signals = orch.compute_loot_directive(rows)
    assert signals['fired'] is True
    assert signals['pending_count'] == 1
    assert 'The party has defeated:' in body
    assert '- Goblin' in body
    assert '3 sp' in body
    assert 'rusty shortsword' in body


def test_single_creature_no_coin_renders_items_only():
    rows = [_row('Wolf', None, None, ['wolf pelt', 'wolf fang'])]
    body, signals = orch.compute_loot_directive(rows)
    assert '- Wolf (wolf pelt, wolf fang)' in body
    # No coin section in the bullet
    assert 'sp' not in body.split('Narrate')[0]
    assert 'gp' not in body.split('Narrate')[0]


def test_single_creature_no_items_renders_coin_only():
    rows = [_row('Goblin', 5, 'sp', [])]
    body, _ = orch.compute_loot_directive(rows)
    assert '- Goblin (5 sp)' in body


# ─── Multiple creatures ─────────────────────────────────────────────

def test_multiple_creatures_render_all_bullets():
    rows = [
        _row('Goblin Patrol', 3, 'sp', ['rusty shortsword'], id_=1),
        _row('Wolf', None, None, ['wolf pelt'], id_=2),
        _row('Bandit', 6, 'sp', ['leather armor'], id_=3),
    ]
    body, signals = orch.compute_loot_directive(rows)
    assert signals['pending_count'] == 3
    assert '- Goblin Patrol' in body
    assert '- Wolf' in body
    assert '- Bandit' in body


# ─── Coin formatting ────────────────────────────────────────────────

def test_coin_uses_space_separator_not_concatenated():
    rows = [_row('X', 5, 'sp', [])]
    body, _ = orch.compute_loot_directive(rows)
    # Bullet body should contain '5 sp' — never '5sp'.
    bullet_line = next(l for l in body.split('\n') if l.startswith('- X'))
    assert '5 sp' in bullet_line
    assert '5sp' not in bullet_line


def test_invalid_coin_denom_drops_coin_silently():
    rows = [_row('X', 5, 'XX', ['a'])]
    body, _ = orch.compute_loot_directive(rows)
    # 'XX' is not a valid denom — should render items only.
    bullet_line = next(l for l in body.split('\n') if l.startswith('- X'))
    assert '5' not in bullet_line
    assert 'a' in bullet_line


def test_coin_amount_zero_still_renders():
    rows = [_row('X', 0, 'sp', [])]
    body, _ = orch.compute_loot_directive(rows)
    assert '0 sp' in body


def test_total_coin_summary_aggregates_by_denom():
    rows = [
        _row('A', 5, 'sp', [], id_=1),
        _row('B', 3, 'sp', [], id_=2),
        _row('C', 2, 'gp', [], id_=3),
    ]
    _, signals = orch.compute_loot_directive(rows)
    assert signals['total_coin_summary'] == '8 sp, 2 gp'


def test_total_coin_summary_none_when_no_coin():
    rows = [_row('A', None, None, ['x'])]
    _, signals = orch.compute_loot_directive(rows)
    assert signals['total_coin_summary'] == 'none'


# ─── Items formatting ───────────────────────────────────────────────

def test_items_joined_with_comma_space():
    rows = [_row('X', None, None, ['a', 'b', 'c'])]
    body, _ = orch.compute_loot_directive(rows)
    assert '(a, b, c)' in body


def test_creature_with_unnamed_creature_renders_placeholder():
    rows = [_row('', None, None, ['gear'])]
    body, signals = orch.compute_loot_directive(rows)
    assert '- (unnamed)' in body
    assert signals['fired'] is True


# ─── Directive content invariants ───────────────────────────────────

def test_directive_includes_no_auto_inventory_clause():
    rows = [_row('Goblin', 1, 'sp', ['x'])]
    body, _ = orch.compute_loot_directive(rows)
    assert 'Do NOT auto-add' in body
    assert '/giveitem' in body


def test_coin_hint_example_uses_actual_amount_not_static():
    # Live S22 test (10:24 May 5) showed the LLM treated a static '+3sp'
    # placeholder as data and emitted '+3cp' for a 12-sp drop. The example
    # must reflect the directive's own coin total, not a fixed template.
    rows = [_row('Goblin', 12, 'sp', ['rusty shortsword'])]
    body, _ = orch.compute_loot_directive(rows)
    assert '!game coin +12sp' in body
    # The pre-fix static placeholder must be gone:
    assert '!game coin +3sp' not in body


def test_coin_hint_example_singular_denomination_summary():
    rows = [_row('Goblin', 3, 'sp', [])]
    body, _ = orch.compute_loot_directive(rows)
    assert '!game coin +3sp' in body
    assert 'for the 3 sp listed above' in body


def test_coin_hint_uses_first_denomination_when_multiple():
    rows = [
        _row('A', 5, 'sp', [], id_=1),
        _row('B', 2, 'gp', [], id_=2),
    ]
    body, _ = orch.compute_loot_directive(rows)
    # _total_coin_summary orders by canonical D&D denom (cp, sp, ep, gp, pp),
    # so 'sp' surfaces first; example anchors to the first total.
    assert '!game coin +5sp' in body


def test_no_coin_drop_renders_explicit_no_coin_line():
    # Without an explicit "no coin" framing, the LLM hallucinates coin
    # (S22 live test: invented "three copper coins" for a Wolf drop). v1.1
    # closes the gap with a positive instruction.
    rows = [_row('Wolf', None, None, ['wolf pelt'])]
    body, _ = orch.compute_loot_directive(rows)
    assert 'no coin' in body.lower()
    assert '!game coin' not in body  # no example when there's no coin
    # Authoritative framing still present
    assert 'AUTHORITATIVE' in body


def test_directive_includes_authoritative_and_exhaustive_framing():
    # The framing addresses BOTH failure modes from the live test:
    # (1) substitution (LLM swapped iron ring for shortsword)
    # (2) addition (LLM added parchment + ring on top of the listed items).
    # 'AUTHORITATIVE' covers (1); 'EXHAUSTIVE' + 'nothing more' covers (2).
    rows = [_row('Goblin', 1, 'sp', ['x'])]
    body, _ = orch.compute_loot_directive(rows)
    assert 'AUTHORITATIVE' in body
    assert 'EXHAUSTIVE' in body
    assert 'do NOT invent additional items' in body.lower() \
        or 'Do NOT invent additional items' in body
    assert 'nothing more' in body.lower()


def test_directive_forbids_substitution_explicitly():
    rows = [_row('Goblin', 1, 'sp', ['x'])]
    body, _ = orch.compute_loot_directive(rows)
    # 'substitute thematic alternatives' is the load-bearing phrase that
    # blocks "iron ring with wolf rune" style flavor swaps.
    assert 'substitute' in body.lower()


def test_directive_overrides_retrieval():
    # Live S22 test (10:34 May 5) showed the LLM blending retrieved past
    # events ("RELEVANT PAST EVENTS" block) with the loot directive — the
    # past narration's invalid loot description anchored attention because
    # retrieval sits earlier in the prompt than tactical directives.
    # Explicit override clause closes the structural attention bias.
    rows = [_row('Goblin', 12, 'sp', ['rusty shortsword'])]
    body, _ = orch.compute_loot_directive(rows)
    assert 'RELEVANT PAST EVENTS' in body
    assert 'ignore those descriptions' in body
    assert 'supersedes any prior narration' in body
    assert 'current ground truth' in body
    # No epistemic hedge — direct authority language only.
    assert 'may have been' not in body.lower()
    assert 'might have been' not in body.lower()


# ─── log summary ────────────────────────────────────────────────────

def test_log_summary_when_fired():
    s = orch.loot_log_summary({'fired': True, 'pending_count': 2})
    assert s == 'fired=1 pending_count=2'


def test_log_summary_when_silent():
    s = orch.loot_log_summary({'fired': False, 'pending_count': 0})
    assert s == 'fired=0 pending_count=0'


def test_log_summary_with_empty_signals():
    assert orch.loot_log_summary({}) == 'fired=0 pending_count=0'


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
