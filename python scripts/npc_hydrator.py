"""NPC stat hydration — Track 6 #4.

Pure-function core. No DB access, no Discord, no dnd_engine imports.
Single consumer: npc_hydrate_stats() in dnd_engine.py.

Doctrine §1 anchor: LLM is not in the CR estimation path. All stat
derivation is deterministic lookup against the embedded CR-band table.
"""

# 5e SRD CR-band defaults (DMG Table 5 — Monster Statistics by Challenge
# Rating). Values: (hp_max, ac, attack_bonus, damage_dice, save_bonus, init_mod).
# Damage dice are representative midpoint expressions per CR band.
_CR_BANDS: dict[str, tuple] = {
    '0':   (3,   10, 2, '1d4',    0, 0),
    '1/8': (9,   12, 3, '1d6',    2, 1),
    '1/4': (13,  13, 3, '1d8',    2, 1),
    '1/2': (22,  13, 4, '1d8+2',  2, 1),
    '1':   (35,  13, 5, '2d6+3',  2, 2),
    '2':   (52,  13, 5, '2d8+3',  2, 2),
    '3':   (70,  13, 5, '2d8+4',  3, 2),
    '4':   (85,  14, 6, '2d10+4', 3, 2),
    '5':   (115, 15, 7, '3d8+5',  3, 3),
    '6':   (140, 15, 7, '3d10+5', 3, 3),
    '7':   (155, 15, 7, '4d8+5',  3, 3),
    '8':   (180, 16, 7, '4d10+5', 3, 3),
    '9':   (195, 16, 8, '4d10+6', 4, 3),
    '10':  (200, 17, 8, '4d12+6', 4, 4),
    '11':  (225, 17, 8, '4d12+7', 4, 4),
    '12':  (240, 17, 8, '5d10+7', 4, 4),
}

_CR_KEYS = ('hp_max', 'ac', 'attack_bonus', 'damage_dice', 'save_bonus', 'init_mod')
_FALLBACK_CR = '1/4'


def hydrate_npc_stats(cr_str: str) -> dict:
    """Return a stat dict for the given CR band.

    Raises ValueError for unrecognized CR strings. Callers validate
    before calling (via normalize_cr). Pure: no side effects.
    """
    row = _CR_BANDS.get(cr_str)
    if row is None:
        raise ValueError(f"unrecognized CR band: {cr_str!r}")
    return dict(zip(_CR_KEYS, row))


def fallback_stats() -> dict:
    """Return CR-1/4 defaults for use when CR is unknown.

    Note: the fallback path deliberately omits hp_max from the write
    (see npc_hydrate_stats source='generic_fallback' branch). This
    function returns the full dict; the write-path caller selects which
    fields to apply.
    """
    return hydrate_npc_stats(_FALLBACK_CR)


def normalize_cr(raw: str) -> str | None:
    """Normalize a user-supplied CR string to a _CR_BANDS key.

    Returns None if the input is unrecognized. Handles common
    alternate forms (decimals, spelled-out fractions, unicode glyphs).
    """
    s = raw.strip().lower()
    _aliases = {
        '0.125': '1/8', '.125': '1/8', 'eighth': '1/8', '⅛': '1/8',
        '0.25':  '1/4', '.25':  '1/4', 'quarter': '1/4', '¼': '1/4',
        '0.5':   '1/2', '.5':   '1/2', 'half': '1/2', '½': '1/2',
    }
    s = _aliases.get(s, s)
    return s if s in _CR_BANDS else None
