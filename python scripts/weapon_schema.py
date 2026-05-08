"""Weapon-family taxonomy used by the capability-grounding subsystem.

Extracted from `dnd_orchestration` in Session 15 (post Session 13's
"weapon_schema.py extraction" filing) so that future capability sources
(DDB ingestion, skeleton-deny-list extensions) can depend on a neutral
schema module rather than reaching back into the orchestration layer.

The schema is the single source of truth for what counts as a "weapon
claim" the system can ground against. Adding a new family is one edit
here; consumers (`dnd_orchestration.check_action_capability`,
`skeleton_loader.get_player_capabilities`) pick it up automatically
because they iterate WEAPON_CAPABILITIES.

Locked spec (Session 13):
  - Matching is exact full-string equality, lowercased on both sides.
  - Player generic noun (a key in WEAPON_CAPABILITIES) → expand to
    alias list, exact-equality against attacks/skeleton.
  - Player specific noun → match only that exact noun.
  - "If anything doesn't match cleanly, the fix is data (aliases),
    not logic." Add aliases here, do NOT add normalization passes
    (substring, token, regex inference) — those collapse the
    partial-projections principle.

This module is import-cheap (no side effects, no I/O, no network).
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class WeaponCapability:
    """One weapon family the system can ground against.

    `aliases` is the lowercased token list that satisfies the family
    on a strict-equality match. Membership in `aliases` is what makes
    a specific weapon name (Avrae attack entry, skeleton-declared
    item) "count as" the family claim.

    `exact_matches` is reserved for future per-weapon grounding
    (thrown properties, reach, versatile distinctions) — unused in v1.
    """
    category:      str
    aliases:       tuple[str, ...]
    exact_matches: tuple[str, ...] = ()


# v1: 10 common weapon families. Add families when friction surfaces.
# Each `category` is the prompt-facing label. `aliases` is the strict-
# equality match set (lowercased on lookup).
WEAPON_CAPABILITIES: tuple[WeaponCapability, ...] = (
    WeaponCapability('sword',
        ('sword', 'longsword', 'shortsword', 'rapier', 'scimitar',
         'greatsword', 'katana')),
    WeaponCapability('axe',
        ('axe', 'handaxe', 'battleaxe', 'greataxe')),
    WeaponCapability('dagger',
        ('dagger',)),
    WeaponCapability('mace',
        ('mace', 'morningstar')),
    WeaponCapability('hammer',
        ('hammer', 'warhammer', 'maul')),
    WeaponCapability('bow',
        ('bow', 'shortbow', 'longbow')),
    WeaponCapability('crossbow',
        ('crossbow',)),
    WeaponCapability('spear',
        ('spear', 'javelin', 'pike', 'halberd', 'glaive', 'lance')),
    WeaponCapability('staff',
        ('staff', 'quarterstaff')),
    WeaponCapability('whip',
        ('whip',)),
)
