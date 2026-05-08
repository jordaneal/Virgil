"""Unit tests for parse_avrae_sheet_embed — Session 15.

Guards against the !coin / !item false-positive bug (Session 14 surface,
fixed Session 15) and the related class of "embed shape match but no
real character data" cases. Avrae's !coin and !item embeds share the
author.name + description structure of !sheet/!beyond embeds; the
parser must distinguish by SHAPE of the description (Race/Class/Level
line + character fields), not by author.

Pure unit tests — no live Discord, no real Avrae traffic. Fakes the
discord.py Embed shape with minimal stubs.

Run: python3 test_parse_avrae_sheet_embed.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dnd_orchestration import parse_avrae_sheet_embed  # noqa: E402


# ── Fake embed shape ──

class _FakeAuthor:
    def __init__(self, name):
        self.name = name


class _FakeField:
    def __init__(self, name, value):
        self.name = name
        self.value = value


class _FakeEmbed:
    """Mimics discord.Embed minimally enough for parse_avrae_sheet_embed."""
    def __init__(self, author_name='', title='', description='', fields=None):
        self.author = _FakeAuthor(author_name) if author_name else None
        self.title = title
        self.description = description
        self.fields = fields or []


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


def check_falsy(label, got):
    global PASS, FAIL
    if not got:
        PASS += 1
    else:
        FAIL += 1
        FAILURES.append(f"  {label}: expected falsy/None, got={got!r}")


# ── Real character sheet embeds — must parse ──

real_sheet = _FakeEmbed(
    author_name='Donovan Ruby',
    description=(
        'Dwarf Rogue 1\n'
        '**HP**: 8 / 8\n'
        '**AC**: 13\n'
        '**Initiative**: +2\n'
        '**Senses**: passive Perception 12, darkvision 60ft\n'
        '**Save Proficiencies**: dexterity +4, intelligence +2\n'
        '**Skill Proficiencies**: stealth +6, perception +4'
    ),
    fields=[_FakeField('Attacks', '**Unarmed Strike** +3 (1d4)')]
)
ctx = parse_avrae_sheet_embed(real_sheet)
check_truthy('real sheet: parsed', ctx is not None)
if ctx:
    check('real sheet: name',     ctx.name,       'Donovan Ruby')
    check('real sheet: race',     ctx.race,       'Dwarf')
    check('real sheet: class',    ctx.char_class, 'Rogue')
    check('real sheet: level',    ctx.level,      1)
    check('real sheet: ac',       ctx.ac,         13)
    check('real sheet: hp_max',   ctx.hp_max,     8)
    check('real sheet: init',     ctx.initiative, 2)
    check('real sheet: passive',  ctx.passive_perception, 12)
    check_truthy('real sheet: darkvision tag',
                 'darkvision' in ctx.narrative_tags)


# Multi-token race ("Hill Dwarf") — head joins all but last
hill_dwarf = _FakeEmbed(
    author_name='Hilda',
    description='Hill Dwarf Rogue 1\n**HP**: 8 / 8\n**AC**: 13'
)
ctx = parse_avrae_sheet_embed(hill_dwarf)
check_truthy('hill dwarf: parsed', ctx is not None)
if ctx:
    check('hill dwarf: race',  ctx.race,       'Hill Dwarf')
    check('hill dwarf: class', ctx.char_class, 'Rogue')
    check('hill dwarf: level', ctx.level,      1)


# Class-only sheet (no race token) — race='' is OK
class_only = _FakeEmbed(
    author_name='Mage',
    description='Wizard 3\n**HP**: 18 / 18\n**AC**: 12'
)
ctx = parse_avrae_sheet_embed(class_only)
check_truthy('class-only: parsed',  ctx is not None)
if ctx:
    check('class-only: race',  ctx.race,       '')
    check('class-only: class', ctx.char_class, 'Wizard')
    check('class-only: level', ctx.level,      3)


# Higher-level character — level parsing through 2-digit levels
mid_level = _FakeEmbed(
    author_name='Veteran',
    description='Half-Elf Bard 12\n**HP**: 78 / 78\n**AC**: 16'
)
ctx = parse_avrae_sheet_embed(mid_level)
check_truthy('mid-level: parsed', ctx is not None)
if ctx:
    check('mid-level: level',   ctx.level,      12)
    check('mid-level: race',    ctx.race,       'Half-Elf')
    check('mid-level: class',   ctx.char_class, 'Bard')


# ── !coin / !item / non-sheet embeds — must REFUSE ──

# !coin embed — first line "**Platinum**: 0" used to extract garbage
coin = _FakeEmbed(
    author_name="Donovan Ruby's Coinpurse",
    description=(
        '**Platinum**: 0\n'
        '**Gold**: 47\n'
        '**Electrum**: 0\n'
        '**Silver**: 12\n'
        '**Copper**: 8\n\n'
        '**Total**: 4.78 gp'
    )
)
check_falsy('!coin embed: refused', parse_avrae_sheet_embed(coin))


# !item embed — also markdown-headed, no character data
item = _FakeEmbed(
    author_name='Healing Potion',
    description='**Type**: Potion\n**Rarity**: Common\n**Description**: Heals 2d4+2 HP'
)
check_falsy('!item embed: refused', parse_avrae_sheet_embed(item))


# Empty description — no parseable content
empty_desc = _FakeEmbed(author_name='Empty', description='')
check_falsy('empty desc: refused', parse_avrae_sheet_embed(empty_desc))


# Empty author + empty title — no name, can't anchor
no_name = _FakeEmbed(description='Dwarf Rogue 1\n**HP**: 8 / 8')
check_falsy('no name: refused', parse_avrae_sheet_embed(no_name))


# Title-only fallback (some Avrae embeds use title not author)
title_anchored = _FakeEmbed(
    title='Borin',
    description='Dwarf Cleric 2\n**HP**: 16 / 16\n**AC**: 18'
)
ctx = parse_avrae_sheet_embed(title_anchored)
check_truthy('title-anchored: parsed', ctx is not None)
if ctx:
    check('title-anchored: name', ctx.name, 'Borin')


# Zero-level edge case — D&D characters start at 1, level 0 is bogus
zero_level = _FakeEmbed(
    author_name='Pretender',
    description='Fighter 0\n'
)
check_falsy('zero level: refused', parse_avrae_sheet_embed(zero_level))


# Negative-look-alike — token ending in digit but level out of range
overlevel = _FakeEmbed(
    author_name='Cheater',
    description='Fighter 99'
)
check_falsy('over level (>20): refused', parse_avrae_sheet_embed(overlevel))


# Level 20 boundary — must accept (legal D&D max)
max_level = _FakeEmbed(
    author_name='Epic',
    description='Human Fighter 20\n**HP**: 200 / 200\n**AC**: 20'
)
ctx = parse_avrae_sheet_embed(max_level)
check_truthy('level 20: parsed', ctx is not None)
if ctx:
    check('level 20: level', ctx.level, 20)


# Level 1 with race+class — must NOT trip the all-defaults sentinel
# (level=1 matches default, but race/class set so sentinel passes)
level_1 = _FakeEmbed(
    author_name='Newbie',
    description='Human Fighter 1\n**HP**: 12 / 12\n**AC**: 16'
)
ctx = parse_avrae_sheet_embed(level_1)
check_truthy('level 1 with race/class: parsed', ctx is not None)
if ctx:
    check('level 1: level', ctx.level, 1)
    check('level 1: race',  ctx.race,  'Human')


# ── Edge cases — all defaults, level can't be parsed ──

# First line is purely descriptive prose (no digit at end)
prose_first = _FakeEmbed(
    author_name='Storyteller',
    description='A tale of three heroes\nMore prose here'
)
check_falsy('prose first line: refused', parse_avrae_sheet_embed(prose_first))


# Asterisks in head — "**Dwarf** Rogue 1" should NOT extract garbage
asterisk_race = _FakeEmbed(
    author_name='BoldName',
    description='**Dwarf** Rogue 1\n**HP**: 8 / 8'
)
ctx = parse_avrae_sheet_embed(asterisk_race)
# The first-line guard sees '*' in the head → refuses to extract Race/Class/Level.
# But HP IS parsed (8), so the all-defaults sentinel passes.
# Result: ctx exists but with race='', class='', level=1 (defaults).
# This is acceptable — partial parse, sentinel only catches all-defaults.
if ctx is not None:
    check('asterisks in head: race default', ctx.race, '')
    check('asterisks in head: class default', ctx.char_class, '')
    check('asterisks in head: hp parsed',     ctx.hp_max,    8)


# ── Report ──

print(f"\n{'=' * 50}")
print(f"PASS: {PASS}  FAIL: {FAIL}")
if FAIL:
    print("\nFAILURES:")
    for line in FAILURES:
        print(line)
    sys.exit(1)
print("ALL GREEN")
