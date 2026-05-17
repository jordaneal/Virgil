"""S77 — §1b.1 Layer B handshake + reply parsing + listener filter.

Tests build_layer_b_question, parse_layer_b_reply, await_layer_b_reply
listener filter correctness (channel + author + post-timestamp + !bot).

Run: python3 test_clarification_layer_b.py
"""
import asyncio
import sys
import time
from dataclasses import dataclass

sys.path.insert(0, '/home/jordaneal/scripts')

import clarification_handshake as ch

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


def check_in(label, haystack, needle):
    global PASS, FAIL
    if needle in haystack:
        PASS += 1
    else:
        FAIL += 1
        FAILURES.append(f"  {label}: {needle!r} not in {haystack!r}")


# ── Card rendering ──

# T1 — question lists each candidate domain with numbered options + DM-voice copy
q = ch.build_layer_b_question([
    {'domain': 'quest_accept'}, {'domain': 'transaction_completion'},
    {'domain': 'loot_drop_player'},
])
check_in('T1: DM-voice header', q, 'A quick check')
check_in('T1: numbered prompt', q, 'Reply with a number')
check_in('T1: option 1 humanized quest_accept', q, '**1.** accepting an offered quest')
check_in('T1: option 2 humanized transaction', q, '**2.** paying or completing a trade')
check_in('T1: option 3 humanized loot', q, '**3.** claiming loot')
check_in('T1: skip option as last number', q, '**4.** none of those')
check_in('T1: DM-voice timeout copy', q, "I'll move on")

# T2 — recursion card (binary forced-choice at iteration 1) — DM-voice
card = ch.build_layer_b_recursion_card(
    [{'domain': 'transaction_completion'}, {'domain': 'loot_drop_player'}],
    iteration=1,
)
check_in('T2: narrowing header', card, 'Let me narrow it down')
check_in('T2: humanized transaction', card, 'paying or completing a trade')
check_in('T2: humanized loot', card, 'claiming loot')

# T3 — recursion at LAYER_B_RECURSION_MAX escalates to manual
card = ch.build_layer_b_recursion_card(
    [{'domain': 'transaction_completion'}, {'domain': 'loot_drop_player'}],
    iteration=ch.LAYER_B_RECURSION_MAX,
)
check_in('T3: DM-voice manual decision card', card, 'One more try')


# ── Reply parser ──

# T4 — explicit skip
r = ch.parse_layer_b_reply('skip', [{'domain': 'transaction'}])
check('T4: explicit_skip', r['intent'], 'EXPLICIT_SKIP')

# T5 — domain match commits
r = ch.parse_layer_b_reply('transaction',
                            [{'domain': 'transaction'}, {'domain': 'loot_drop'}])
check('T5: commit_transaction', r['intent'], 'COMMIT_transaction')
check('T5: matched_domain', r['matched_domain'], 'transaction')

# T6 — case-insensitive match
r = ch.parse_layer_b_reply('TRANSACTION',
                            [{'domain': 'transaction'}, {'domain': 'loot_drop'}])
check('T6: case-insensitive commit', r['intent'], 'COMMIT_transaction')

# T7 — non-matching reply is AMBIGUOUS
r = ch.parse_layer_b_reply('huh what now',
                            [{'domain': 'transaction'}, {'domain': 'loot_drop'}])
check('T7: AMBIGUOUS', r['intent'], 'AMBIGUOUS')

# T8 — empty reply
r = ch.parse_layer_b_reply('', [{'domain': 'transaction'}])
check('T8: empty AMBIGUOUS', r['intent'], 'AMBIGUOUS')

# T9 — "none" treated as skip
r = ch.parse_layer_b_reply('none', [{'domain': 'transaction'}])
check('T9: none → skip', r['intent'], 'EXPLICIT_SKIP')

# T9a — numeric reply "1" matches first candidate (post-S78 UX fix)
r = ch.parse_layer_b_reply('1', [{'domain': 'transaction'}, {'domain': 'loot_drop'}])
check('T9a: numeric 1 commits first candidate', r['intent'], 'COMMIT_transaction')
check('T9a: matched domain', r['matched_domain'], 'transaction')

# T9b — numeric reply "2" matches second candidate
r = ch.parse_layer_b_reply('2', [{'domain': 'transaction'}, {'domain': 'loot_drop'}])
check('T9b: numeric 2 commits second candidate', r['intent'], 'COMMIT_loot_drop')

# T9c — numeric reply "3" with 2 candidates = skip slot
r = ch.parse_layer_b_reply('3', [{'domain': 'transaction'}, {'domain': 'loot_drop'}])
check('T9c: numeric skip-slot is EXPLICIT_SKIP', r['intent'], 'EXPLICIT_SKIP')

# T9d — out-of-range numeric is AMBIGUOUS
r = ch.parse_layer_b_reply('99', [{'domain': 'transaction'}, {'domain': 'loot_drop'}])
check('T9d: out-of-range AMBIGUOUS', r['intent'], 'AMBIGUOUS')


# ── Listener filter correctness ──
#
# Stub Bot + Message to exercise the check function. We extract the check
# function via monkeypatching await_layer_b_reply's bot.wait_for call,
# capturing the predicate, then exercising it directly across boundary cases.

@dataclass
class StubAuthor:
    id: str
    bot: bool = False


@dataclass
class StubChannel:
    id: int


@dataclass
class StubMessage:
    channel: StubChannel
    author: StubAuthor
    created_at: object  # datetime-like with .timestamp()
    content: str = ''


class StubTs:
    """Mimics discord.Message.created_at — has .timestamp() method."""
    def __init__(self, t):
        self._t = t

    def timestamp(self):
        return self._t


captured_check = [None]


class FakeBot:
    async def wait_for(self, evt, check=None, timeout=None):
        captured_check[0] = check
        raise asyncio.TimeoutError()


async def _run_filter_test():
    bot = FakeBot()
    await ch.await_layer_b_reply(
        bot, channel_id=42, controller_id='user-1',
        trigger_timestamp=100.0, timeout=1,
    )


asyncio.run(_run_filter_test())
ck = captured_check[0]
check('T10: check fn captured', ck is not None, True)

# Right channel + author + timestamp + not bot → True
m = StubMessage(StubChannel(42), StubAuthor('user-1', False), StubTs(200.0))
check('T11: accept valid', ck(m), True)

# Wrong channel
m = StubMessage(StubChannel(99), StubAuthor('user-1', False), StubTs(200.0))
check('T12: reject wrong channel', ck(m), False)

# Wrong author
m = StubMessage(StubChannel(42), StubAuthor('user-99', False), StubTs(200.0))
check('T13: reject wrong author', ck(m), False)

# Bot author
m = StubMessage(StubChannel(42), StubAuthor('user-1', True), StubTs(200.0))
check('T14: reject bot author', ck(m), False)

# Before trigger timestamp
m = StubMessage(StubChannel(42), StubAuthor('user-1', False), StubTs(50.0))
check('T15: reject pre-trigger', ck(m), False)


# ── Summary ──
total = PASS + FAIL
print(f"\nclarification_layer_b: {PASS}/{total} passed")
if FAIL:
    print("\nFAILURES:")
    for f in FAILURES:
        print(f)
    sys.exit(1)
