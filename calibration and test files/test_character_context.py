"""Unit tests for CharacterContext (dnd_orchestration) — Session 15.

Covers the primary_name property + to_prompt_block / to_compact_line
render behavior added by the Donovan/Ruby address-name fix. Also
covers the existing rendering structure so future edits don't silently
drop fields.

Run: python3 test_character_context.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dnd_orchestration import CharacterContext  # noqa: E402


# ── Tiny harness ──

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


def check_in(label, needle, haystack):
    global PASS, FAIL
    if needle in haystack:
        PASS += 1
    else:
        FAIL += 1
        FAILURES.append(f"  {label}: {needle!r} not in {haystack!r}")


def check_not_in(label, needle, haystack):
    global PASS, FAIL
    if needle not in haystack:
        PASS += 1
    else:
        FAIL += 1
        FAILURES.append(f"  {label}: {needle!r} unexpectedly in {haystack!r}")


# ── primary_name property ──

# Multi-token names → first whitespace token
ctx = CharacterContext(name='Donovan Ruby')
check('primary_name: two tokens', ctx.primary_name, 'Donovan')

ctx = CharacterContext(name='Donovan James Ruby')
check('primary_name: three tokens', ctx.primary_name, 'Donovan')

# Single-token names → returned unchanged
ctx = CharacterContext(name='Throx')
check('primary_name: single token', ctx.primary_name, 'Throx')

# Empty / whitespace
ctx = CharacterContext(name='')
check('primary_name: empty', ctx.primary_name, '')

# Lowercase preserved (canonicalize_name preserves case; primary_name does too)
ctx = CharacterContext(name='donovan ruby')
check('primary_name: lowercase preserved', ctx.primary_name, 'donovan')

# Internal whitespace runs collapse only via .split() default behavior
ctx = CharacterContext(name='Donovan  Ruby')  # double space
check('primary_name: internal ws split', ctx.primary_name, 'Donovan')

# Leading whitespace doesn't break .split()
ctx = CharacterContext(name='  Donovan Ruby')
check('primary_name: leading ws', ctx.primary_name, 'Donovan')


# ── to_prompt_block renders "(address as X)" for multi-token names ──

ctx = CharacterContext(
    name='Donovan Ruby',
    race='Dwarf',
    char_class='Rogue',
    level=1,
    ac=13,
    hp_max=8,
    initiative=2,
    passive_perception=12,
)
block = ctx.to_prompt_block()

# Identity line should mention both forms
check_in('to_prompt_block: full name in identity',
         'Donovan Ruby', block)
check_in('to_prompt_block: address-as parenthetical',
         '(address as Donovan)', block)

# Single-token name → no parenthetical (would be redundant)
ctx_single = CharacterContext(
    name='Throx',
    race='Goblin',
    char_class='Rogue',
    level=1,
)
block_single = ctx_single.to_prompt_block()
check_in('to_prompt_block: single-token name present',
         'Throx', block_single)
check_not_in('to_prompt_block: no parenthetical for single-token',
             '(address as', block_single)

# Empty name → no parenthetical (defensive)
ctx_empty = CharacterContext(name='')
block_empty = ctx_empty.to_prompt_block()
check_not_in('to_prompt_block: no parenthetical for empty name',
             '(address as', block_empty)


# ── to_compact_line same parenthetical behavior ──

ctx = CharacterContext(name='Donovan Ruby', char_class='Rogue', level=1)
line = ctx.to_compact_line()
check_in('to_compact_line: full name', 'Donovan Ruby', line)
check_in('to_compact_line: address-as parenthetical',
         '(address as Donovan)', line)

ctx_single = CharacterContext(name='Throx', char_class='Rogue', level=1)
line_single = ctx_single.to_compact_line()
check_in('to_compact_line: single-token name', 'Throx', line_single)
check_not_in('to_compact_line: no parenthetical for single-token',
             '(address as', line_single)


# ── to_prompt_block renders all expected fields ──

ctx = CharacterContext(
    name='Donovan Ruby',
    race='Dwarf',
    char_class='Rogue',
    level=1,
    ac=13,
    hp_max=8,
    initiative=2,
    passive_perception=12,
    saves={'dex': 4},
    skills={'stealth': 6, 'perception': 4},
    attacks=['Unarmed Strike', 'Longsword'],
    narrative_tags={'darkvision', 'lockpicker'},
)
block = ctx.to_prompt_block()

check_in('to_prompt_block: race rendered',     'Dwarf',           block)
check_in('to_prompt_block: class rendered',    'Rogue',           block)
check_in('to_prompt_block: level rendered',    'Level 1',         block)
check_in('to_prompt_block: ac rendered',       'AC 13',           block)
check_in('to_prompt_block: hp rendered',       'HP 8',            block)
check_in('to_prompt_block: init signed',       'Initiative +2',   block)
check_in('to_prompt_block: passive rendered',  'Passive Perception 12', block)
check_in('to_prompt_block: skills rendered',   'stealth',         block)
check_in('to_prompt_block: attacks rendered',  'Longsword',       block)
check_in('to_prompt_block: tags rendered',     'darkvision',      block)
check_in('to_prompt_block: tags rendered 2',   'lockpicker',      block)


# Empty narrative_tags → "—" placeholder
ctx_no_tags = CharacterContext(name='Bare', char_class='Wizard', level=1)
block_no_tags = ctx_no_tags.to_prompt_block()
check_in('to_prompt_block: empty tags → em-dash',
         'Tags: —', block_no_tags)


# Skills rendering — top 5 by bonus, descending
ctx_many_skills = CharacterContext(
    name='Master',
    char_class='Bard',
    level=10,
    skills={
        'stealth': 8,
        'perception': 5,
        'persuasion': 10,
        'deception': 7,
        'arcana': 6,
        'history': 3,    # should NOT appear (top 5 only)
    },
)
block_skills = ctx_many_skills.to_prompt_block()
check_in('to_prompt_block: top skill', 'persuasion +10', block_skills)
check_in('to_prompt_block: high skill', 'stealth +8',    block_skills)
check_not_in('to_prompt_block: low skill excluded (top-5)',
             'history',                                    block_skills)


# ── to_compact_line shape ──

ctx = CharacterContext(
    name='Donovan Ruby',
    char_class='Rogue',
    level=1,
    narrative_tags={'darkvision', 'lockpicker', 'stealth_specialist'},
)
line = ctx.to_compact_line()
check_in('to_compact_line: class', 'Rogue', line)
check_in('to_compact_line: level', '1',     line)
check_in('to_compact_line: tags label', 'tags:', line)
check_in('to_compact_line: tag value', 'darkvision', line)


# ── set_cached_context / get_cached_context round-trip ──

from dnd_orchestration import (  # noqa: E402
    set_cached_context, get_cached_context, invalidate_cache,
)

invalidate_cache()  # clean slate

ctx = CharacterContext(name='Donovan Ruby', race='Dwarf', char_class='Rogue', level=1)
set_cached_context(ctx)

retrieved = get_cached_context('Donovan Ruby')
check_truthy('cache: round-trip retrieval', retrieved is not None)
if retrieved:
    check('cache: name preserved', retrieved.name, 'Donovan Ruby')
    check('cache: class preserved', retrieved.char_class, 'Rogue')

# Invalidate by name
invalidate_cache('Donovan Ruby')
check('cache: invalidate one', get_cached_context('Donovan Ruby'), None)

# Repopulate, then invalidate ALL
set_cached_context(CharacterContext(name='A'))
set_cached_context(CharacterContext(name='B'))
invalidate_cache()  # all
check('cache: invalidate all (A)', get_cached_context('A'), None)
check('cache: invalidate all (B)', get_cached_context('B'), None)


# ── Report ──

print(f"\n{'=' * 50}")
print(f"PASS: {PASS}  FAIL: {FAIL}")
if FAIL:
    print("\nFAILURES:")
    for line in FAILURES:
        print(line)
    sys.exit(1)
print("ALL GREEN")
