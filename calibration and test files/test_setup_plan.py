"""Deterministic tests for compute_setup_plan (Session 23 #3 — channel cleanup).

Pure function — takes a guild snapshot (text_channels, voice_channels,
categories) and returns the actions /setup must take to converge to the
canonical structure. No Discord API mocks required.

Run:
    cd /home/jordaneal/scripts && python3 test_setup_plan.py
"""

import sys

sys.path.insert(0, '/home/jordaneal/scripts')

import discord_dnd_bot as bot


# ─── Module-level constants under test ──────────────────────────────

def test_canonical_channel_names_shape():
    assert bot.CHANNEL_NAMES == {
        'narration': 'dm-narration',
        'aside':     'dm-aside',
        'lore':      'lore-notes',
        'welcome':   'welcome',
        'commands':  'commands',
        'ooc':       'party-chat',
    }


def test_welcome_inserted_before_ooc_in_dict():
    # Insertion order matters — Discord positions channels by creation
    # order within a category. Putting 'welcome' before 'commands'/'ooc'
    # means a fresh /setup run creates #welcome first inside the OOC
    # category, so it lands at the top by default. /setup additionally
    # pins this via channel.edit(position=0) for idempotent placement.
    keys = list(bot.CHANNEL_NAMES.keys())
    assert keys.index('welcome') < keys.index('commands') < keys.index('ooc'), (
        f"OOC channel order must be welcome → commands → ooc in "
        f"CHANNEL_NAMES insertion order; got {keys}"
    )


def test_commands_channel_routes_to_ooc_category():
    assert bot.CHANNEL_CATEGORY['commands'] == 'ooc'


def test_avrae_read_only_set_includes_lore():
    # Avrae gets read but no send on #lore-notes (DM-only write surface).
    assert 'lore' in bot.AVRAE_READ_ONLY


def test_avrae_read_only_set_excludes_open_channels():
    # Open channels keep Avrae's full perms.
    for k in ('narration', 'aside', 'welcome', 'commands', 'ooc'):
        assert k not in bot.AVRAE_READ_ONLY, (
            f"channel key {k!r} should NOT be in AVRAE_READ_ONLY"
        )


def test_welcome_routes_to_ooc_category():
    assert bot.CHANNEL_CATEGORY['welcome'] == 'ooc'


def test_canonical_categories_shape():
    assert bot.CATEGORY_NAMES == {
        'dm':    '🎲 VIRGIL DM',
        'ooc':   '💬 OUT OF CHARACTER',
        'voice': '🔊 VOICE',
    }


def test_channel_to_category_mapping_complete():
    # Every text-channel key must have a category mapping.
    for key in bot.CHANNEL_NAMES:
        assert key in bot.CHANNEL_CATEGORY, f"missing category mapping for {key!r}"


def test_category_keys_resolve_to_real_categories():
    for chan_key, cat_key in bot.CHANNEL_CATEGORY.items():
        assert cat_key in bot.CATEGORY_NAMES, (
            f"channel {chan_key!r} maps to unknown category key {cat_key!r}"
        )


def test_voice_channel_specs_resolve():
    for vc_name, cat_key in bot.VOICE_CHANNELS:
        assert cat_key in bot.CATEGORY_NAMES, (
            f"voice {vc_name!r} maps to unknown category key {cat_key!r}"
        )


def test_legacy_dropped_keys_are_gone():
    # rolls / sheets / loot are no longer canonical (S23 #3). NOTE:
    # 'commands' was re-introduced (Phase 3 of S25 housekeeping) as a
    # separate OOC channel #commands — distinct from the old #commands
    # under 🎲 D&D, which was retired in S23 #3.
    for dropped in ('rolls', 'sheets', 'loot'):
        assert dropped not in bot.CHANNEL_NAMES


# ─── Empty guild ────────────────────────────────────────────────────

def test_empty_guild_creates_everything():
    plan = bot.compute_setup_plan(
        text_channels={},
        voice_channels={},
        categories=set(),
    )
    # All 3 canonical categories must be created
    assert sorted(plan['categories_to_create']) == sorted([
        '🎲 VIRGIL DM', '💬 OUT OF CHARACTER', '🔊 VOICE',
    ])
    # All 6 canonical text channels (S25 added 'commands')
    text_names = sorted(n for n, _ in plan['text_channels_to_create'])
    assert text_names == [
        'commands', 'dm-aside', 'dm-narration',
        'lore-notes', 'party-chat', 'welcome'
    ]
    # 2 voice channels (S25 added 'AFK')
    assert sorted(plan['voice_channels_to_create']) == sorted([
        ('General', '🔊 VOICE'),
        ('AFK', '🔊 VOICE'),
    ])
    # No moves, no existing
    assert plan['text_channels_to_move'] == []
    assert plan['voice_channels_to_move'] == []
    assert plan['text_channels_existing'] == []
    assert plan['voice_channels_existing'] == []
    assert plan['categories_existing'] == []
    assert plan['legacy_category_to_delete'] is None


def test_empty_guild_assigns_canonical_categories():
    plan = bot.compute_setup_plan(
        text_channels={},
        voice_channels={},
        categories=set(),
    )
    # narration / aside / lore → 🎲 VIRGIL DM
    # welcome / commands / party-chat → 💬 OUT OF CHARACTER
    cat_by_chan = {n: c for n, c in plan['text_channels_to_create']}
    assert cat_by_chan['dm-narration']   == '🎲 VIRGIL DM'
    assert cat_by_chan['dm-aside']       == '🎲 VIRGIL DM'
    assert cat_by_chan['lore-notes']     == '🎲 VIRGIL DM'
    assert cat_by_chan['welcome']        == '💬 OUT OF CHARACTER'
    assert cat_by_chan['commands']   == '💬 OUT OF CHARACTER'
    assert cat_by_chan['party-chat']     == '💬 OUT OF CHARACTER'


def test_welcome_appears_before_commands_and_party_chat_in_create_list():
    # Plan create-list order matches CHANNEL_NAMES dict order. Fresh /setup
    # creates welcome → commands → party-chat in that order so Discord's
    # default within-category positioning lands them in the right places.
    plan = bot.compute_setup_plan(
        text_channels={},
        voice_channels={},
        categories=set(),
    )
    create_names = [n for n, _ in plan['text_channels_to_create']]
    assert create_names.index('welcome') < create_names.index('commands')
    assert create_names.index('commands') < create_names.index('party-chat')


def test_afk_voice_in_create_list():
    # AFK voice channel must be planned alongside General when guild is empty.
    plan = bot.compute_setup_plan(
        text_channels={},
        voice_channels={},
        categories=set(),
    )
    voice_names = [n for n, _ in plan['voice_channels_to_create']]
    assert 'AFK' in voice_names
    assert 'General' in voice_names


# ─── Already canonical ──────────────────────────────────────────────

def test_already_canonical_is_no_op():
    plan = bot.compute_setup_plan(
        text_channels={
            'dm-narration': '🎲 VIRGIL DM',
            'dm-aside':     '🎲 VIRGIL DM',
            'lore-notes':   '🎲 VIRGIL DM',
            'welcome':      '💬 OUT OF CHARACTER',
            'commands': '💬 OUT OF CHARACTER',
            'party-chat':   '💬 OUT OF CHARACTER',
        },
        voice_channels={'General': '🔊 VOICE', 'AFK': '🔊 VOICE'},
        categories={'🎲 VIRGIL DM', '💬 OUT OF CHARACTER', '🔊 VOICE'},
    )
    assert plan['categories_to_create'] == []
    assert plan['text_channels_to_create'] == []
    assert plan['voice_channels_to_create'] == []
    assert plan['text_channels_to_move'] == []
    assert plan['voice_channels_to_move'] == []
    assert sorted(plan['text_channels_existing']) == [
        'commands', 'dm-aside', 'dm-narration',
        'lore-notes', 'party-chat', 'welcome'
    ]
    assert sorted(plan['voice_channels_existing']) == ['AFK', 'General']
    assert sorted(plan['categories_existing']) == sorted([
        '🎲 VIRGIL DM', '💬 OUT OF CHARACTER', '🔊 VOICE',
    ])
    assert plan['legacy_category_to_delete'] is None


def test_commands_missing_creates_only_commands():
    # Post-S23-#4 server has welcome + party-chat in OOC but no commands
    # channel yet — re-running /setup should plan only that addition.
    plan = bot.compute_setup_plan(
        text_channels={
            'dm-narration': '🎲 VIRGIL DM',
            'dm-aside':     '🎲 VIRGIL DM',
            'lore-notes':   '🎲 VIRGIL DM',
            'welcome':      '💬 OUT OF CHARACTER',
            'party-chat':   '💬 OUT OF CHARACTER',
        },
        voice_channels={'General': '🔊 VOICE', 'AFK': '🔊 VOICE'},
        categories={'🎲 VIRGIL DM', '💬 OUT OF CHARACTER', '🔊 VOICE'},
    )
    assert plan['text_channels_to_create'] == [
        ('commands', '💬 OUT OF CHARACTER'),
    ]
    assert plan['voice_channels_to_create'] == []


def test_afk_voice_missing_creates_only_afk():
    # Pre-S25 server has General voice but no AFK channel yet.
    plan = bot.compute_setup_plan(
        text_channels={
            'dm-narration': '🎲 VIRGIL DM',
            'dm-aside':     '🎲 VIRGIL DM',
            'lore-notes':   '🎲 VIRGIL DM',
            'welcome':      '💬 OUT OF CHARACTER',
            'commands': '💬 OUT OF CHARACTER',
            'party-chat':   '💬 OUT OF CHARACTER',
        },
        voice_channels={'General': '🔊 VOICE'},
        categories={'🎲 VIRGIL DM', '💬 OUT OF CHARACTER', '🔊 VOICE'},
    )
    assert plan['voice_channels_to_create'] == [('AFK', '🔊 VOICE')]
    assert plan['text_channels_to_create'] == []


def test_welcome_missing_creates_only_welcome():
    # Post-S23-#3 server (4 canonical channels exist) gets upgraded —
    # plan should add 'welcome' AND 'commands' (S25 #2). AFK voice
    # is also added since pre-S25 servers don't have it.
    plan = bot.compute_setup_plan(
        text_channels={
            'dm-narration': '🎲 VIRGIL DM',
            'dm-aside':     '🎲 VIRGIL DM',
            'lore-notes':   '🎲 VIRGIL DM',
            'party-chat':   '💬 OUT OF CHARACTER',
        },
        voice_channels={'General': '🔊 VOICE'},
        categories={'🎲 VIRGIL DM', '💬 OUT OF CHARACTER', '🔊 VOICE'},
    )
    text_names_to_create = sorted(n for n, _ in plan['text_channels_to_create'])
    assert text_names_to_create == ['commands', 'welcome']
    assert plan['text_channels_to_move'] == []
    voice_to_create = [n for n, _ in plan['voice_channels_to_create']]
    assert voice_to_create == ['AFK']
    assert sorted(plan['text_channels_existing']) == [
        'dm-aside', 'dm-narration', 'lore-notes', 'party-chat'
    ]


def test_welcome_in_wrong_category_gets_moved():
    # If #welcome was somehow created at top-level or in legacy, move it
    # into 💬 OUT OF CHARACTER.
    plan = bot.compute_setup_plan(
        text_channels={'welcome': '🎲 D&D'},
        voice_channels={},
        categories={'🎲 D&D'},
    )
    moves = {n: c for n, c in plan['text_channels_to_move']}
    assert moves.get('welcome') == '💬 OUT OF CHARACTER'


# ─── Mixed state — some canonical, some legacy ──────────────────────

def test_mixed_state_creates_missing_only():
    # Pretend dm-narration / lore-notes already exist in legacy 🎲 D&D
    # category (pre-S23-#3 setup), and the rest don't exist. None of
    # the canonical categories exist yet.
    plan = bot.compute_setup_plan(
        text_channels={
            'dm-narration': '🎲 D&D',
            'lore-notes':   '🎲 D&D',
            'dice-rolls':   '🎲 D&D',  # legacy, unknown
            'general':      None,
        },
        voice_channels={},
        categories={'🎲 D&D'},
    )
    # All 3 canonical categories need creation
    assert sorted(plan['categories_to_create']) == sorted([
        '🎲 VIRGIL DM', '💬 OUT OF CHARACTER', '🔊 VOICE',
    ])
    # Missing canonical channels: dm-aside, welcome, commands, party-chat
    text_names_to_create = sorted(n for n, _ in plan['text_channels_to_create'])
    assert text_names_to_create == [
        'commands', 'dm-aside', 'party-chat', 'welcome'
    ]
    # Existing canonical channels in WRONG category → moves
    text_names_to_move = sorted(n for n, _ in plan['text_channels_to_move'])
    assert text_names_to_move == ['dm-narration', 'lore-notes']
    # Both should target 🎲 VIRGIL DM
    move_cats = {n: c for n, c in plan['text_channels_to_move']}
    assert move_cats['dm-narration'] == '🎲 VIRGIL DM'
    assert move_cats['lore-notes']   == '🎲 VIRGIL DM'


def test_legacy_category_marked_for_deletion_when_emptied():
    # Legacy 🎲 D&D contains ONLY canonical channels we'll move out.
    plan = bot.compute_setup_plan(
        text_channels={
            'dm-narration': '🎲 D&D',
            'lore-notes':   '🎲 D&D',
        },
        voice_channels={},
        categories={'🎲 D&D'},
    )
    # Both channels move out → legacy will be empty → mark for deletion
    assert plan['legacy_category_to_delete'] == '🎲 D&D'


def test_legacy_category_not_deleted_when_non_canonical_remains():
    # Legacy 🎲 D&D has dm-narration AND a non-canonical leftover.
    plan = bot.compute_setup_plan(
        text_channels={
            'dm-narration': '🎲 D&D',
            'dice-rolls':   '🎲 D&D',  # legacy, won't be touched
        },
        voice_channels={},
        categories={'🎲 D&D'},
    )
    # dm-narration moves, dice-rolls stays → legacy NOT empty → keep
    assert plan['legacy_category_to_delete'] is None


def test_legacy_category_with_voice_remnant_not_deleted():
    plan = bot.compute_setup_plan(
        text_channels={'dm-narration': '🎲 D&D'},
        voice_channels={'OldRoom': '🎲 D&D'},  # leftover voice
        categories={'🎲 D&D'},
    )
    # dm-narration moves out but OldRoom voice stays → keep legacy
    assert plan['legacy_category_to_delete'] is None


def test_legacy_category_absent_no_op():
    # No legacy category exists → never marked for deletion.
    plan = bot.compute_setup_plan(
        text_channels={},
        voice_channels={},
        categories=set(),
    )
    assert plan['legacy_category_to_delete'] is None


# ─── Idempotency ────────────────────────────────────────────────────

def test_re_running_after_setup_is_no_op():
    state_text = {
        'dm-narration': '🎲 VIRGIL DM',
        'dm-aside':     '🎲 VIRGIL DM',
        'lore-notes':   '🎲 VIRGIL DM',
        'welcome':      '💬 OUT OF CHARACTER',
        'commands': '💬 OUT OF CHARACTER',
        'party-chat':   '💬 OUT OF CHARACTER',
    }
    state_voice = {'General': '🔊 VOICE', 'AFK': '🔊 VOICE'}
    state_cats = {'🎲 VIRGIL DM', '💬 OUT OF CHARACTER', '🔊 VOICE'}

    p1 = bot.compute_setup_plan(state_text, state_voice, state_cats)
    p2 = bot.compute_setup_plan(state_text, state_voice, state_cats)
    assert p1 == p2
    # No work to do
    assert p1['categories_to_create'] == []
    assert p1['text_channels_to_create'] == []
    assert p1['text_channels_to_move'] == []
    assert p1['voice_channels_to_create'] == []
    assert p1['voice_channels_to_move'] == []


# ─── Channel in correct category but other legacy still around ──────

def test_canonical_channel_in_correct_category_with_legacy_present():
    plan = bot.compute_setup_plan(
        text_channels={
            'dm-narration': '🎲 VIRGIL DM',
            'dice-rolls':   '🎲 D&D',  # leftover
        },
        voice_channels={},
        categories={'🎲 VIRGIL DM', '🎲 D&D'},
    )
    # dm-narration is correctly placed → existing
    assert 'dm-narration' in plan['text_channels_existing']
    # No moves
    assert plan['text_channels_to_move'] == []
    # Legacy not deleted (dice-rolls still in it)
    assert plan['legacy_category_to_delete'] is None


# ─── Channel exists at top level (no category) ──────────────────────

def test_canonical_channel_at_top_level_gets_moved():
    plan = bot.compute_setup_plan(
        text_channels={'dm-narration': None},  # no category
        voice_channels={},
        categories=set(),
    )
    # Must be moved to 🎲 VIRGIL DM
    moves = {n: c for n, c in plan['text_channels_to_move']}
    assert moves.get('dm-narration') == '🎲 VIRGIL DM'


# ─── Voice channel moves ────────────────────────────────────────────

def test_voice_channel_in_wrong_category_gets_moved():
    plan = bot.compute_setup_plan(
        text_channels={},
        voice_channels={'General': '🎲 D&D'},  # wrong category
        categories={'🎲 D&D'},
    )
    moves = {n: c for n, c in plan['voice_channels_to_move']}
    assert moves.get('General') == '🔊 VOICE'


def test_voice_channel_at_top_level_gets_moved():
    plan = bot.compute_setup_plan(
        text_channels={},
        voice_channels={'General': None},
        categories=set(),
    )
    moves = {n: c for n, c in plan['voice_channels_to_move']}
    assert moves.get('General') == '🔊 VOICE'


def test_voice_channel_correctly_placed_is_existing():
    plan = bot.compute_setup_plan(
        text_channels={},
        voice_channels={'General': '🔊 VOICE', 'AFK': '🔊 VOICE'},
        categories={'🔊 VOICE'},
    )
    assert sorted(plan['voice_channels_existing']) == ['AFK', 'General']
    assert plan['voice_channels_to_create'] == []
    assert plan['voice_channels_to_move'] == []


# ─── Determinism ────────────────────────────────────────────────────

def test_pure_function_deterministic():
    args = (
        {'dm-narration': '🎲 D&D'},
        {},
        {'🎲 D&D'},
    )
    p1 = bot.compute_setup_plan(*args)
    p2 = bot.compute_setup_plan(*args)
    assert p1 == p2


def test_no_input_mutation():
    text = {'dm-narration': '🎲 D&D'}
    voice = {}
    cats = {'🎲 D&D'}
    text_copy = dict(text)
    voice_copy = dict(voice)
    cats_copy = set(cats)
    bot.compute_setup_plan(text, voice, cats)
    assert text == text_copy
    assert voice == voice_copy
    assert cats == cats_copy


# ─── Telemetry helper ───────────────────────────────────────────────

def test_log_summary_empty_guild():
    plan = bot.compute_setup_plan({}, {}, set())
    out = bot.setup_plan_log_summary(plan)
    # S25: 6 text (added 'commands') + 2 voice (added 'AFK') = 8
    assert 'channels_created=8' in out
    assert 'categories_created=3' in out
    assert 'channels_moved=0' in out
    assert 'channels_existing=0' in out
    assert 'legacy_deleted=0' in out


def test_log_summary_already_canonical():
    plan = bot.compute_setup_plan(
        {
            'dm-narration': '🎲 VIRGIL DM',
            'dm-aside':     '🎲 VIRGIL DM',
            'lore-notes':   '🎲 VIRGIL DM',
            'welcome':      '💬 OUT OF CHARACTER',
            'commands': '💬 OUT OF CHARACTER',
            'party-chat':   '💬 OUT OF CHARACTER',
        },
        {'General': '🔊 VOICE', 'AFK': '🔊 VOICE'},
        {'🎲 VIRGIL DM', '💬 OUT OF CHARACTER', '🔊 VOICE'},
    )
    out = bot.setup_plan_log_summary(plan)
    assert 'channels_created=0' in out
    assert 'channels_moved=0' in out
    # 6 text + 2 voice = 8
    assert 'channels_existing=8' in out
    assert 'categories_existing=3' in out


# ─── Welcome channel content contracts (S23 #4) ─────────────────────

def test_welcome_pin_body_mentions_site():
    assert 'virgildm.com' in bot.WELCOME_PIN_BODY


def test_welcome_pin_body_mentions_codex_anchor():
    # The "played before" path links to https://virgildm.com#codex
    assert '#codex' in bot.WELCOME_PIN_BODY


def test_welcome_pin_body_mentions_dm_narration_handoff():
    assert '#dm-narration' in bot.WELCOME_PIN_BODY


def test_welcome_pin_body_has_two_paths():
    # New / experienced players each get a labeled entry point
    assert 'New to D&D' in bot.WELCOME_PIN_BODY
    assert 'Played before' in bot.WELCOME_PIN_BODY


def test_welcome_channel_topic_is_short_and_points_at_site():
    assert 'virgildm.com' in bot.WELCOME_CHANNEL_TOPIC
    # Discord channel topics have a 1024-char limit; ours is way under
    assert len(bot.WELCOME_CHANNEL_TOPIC) < 200


def test_log_summary_with_moves():
    plan = bot.compute_setup_plan(
        {'dm-narration': '🎲 D&D', 'lore-notes': '🎲 D&D'},
        {},
        {'🎲 D&D'},
    )
    out = bot.setup_plan_log_summary(plan)
    assert 'channels_moved=2' in out
    assert 'legacy_deleted=1' in out  # both move out → legacy will empty


def test_log_summary_empty_signals_safe():
    assert bot.setup_plan_log_summary({}) != ''
    assert bot.setup_plan_log_summary(None) != ''


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
