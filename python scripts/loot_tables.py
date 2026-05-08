#!/usr/bin/env python3
"""
Hardcoded loot tables for Track 4 #2 v1.

Pattern-matched by substring (case-insensitive) against creature name from
defeat events. Falls through to _default when no match found.

v1 is small on purpose. Expanding the table list is filed as v1.x — observe
which creatures Jordan actually fights, then expand from real combat data.
"""

import random
import re
from typing import Optional, Dict, Any


LOOT_TABLES: Dict[str, Dict[str, Any]] = {
    'goblin':   {'coin': '2d6 sp',  'items': ['rusty shortsword', 'crude bow', 'tattered map']},
    'wolf':     {'coin': None,       'items': ['wolf pelt', 'wolf fang']},
    'bandit':   {'coin': '3d6 sp',  'items': ['leather armor', 'shortsword', 'coin pouch']},
    'skeleton': {'coin': '1d6 sp',  'items': ['rusted weapon', 'bone fragments']},
    'cultist':  {'coin': '2d4 gp',  'items': ['ritual dagger', 'dark robes', 'unholy symbol']},
    '_default': {'coin': '1d4 sp',  'items': ['common gear']},
}

_DICE_RE = re.compile(r'^\s*(\d+)d(\d+)\s*(sp|gp|cp|ep|pp)\s*$', re.IGNORECASE)


def _match_table_key(creature_name: str) -> str:
    """Substring match (case-insensitive) against table keys.
    'Goblin Patrol' -> 'goblin'. Falls through to '_default'."""
    if not creature_name:
        return '_default'
    name_lower = creature_name.lower()
    for key in LOOT_TABLES:
        if key == '_default':
            continue
        if key in name_lower:
            return key
    return '_default'


def _roll_coin(coin_expr: Optional[str]) -> Optional[Dict[str, Any]]:
    """Roll '2d6 sp' style expressions. Returns {amount: int, denom: str}
    or None when no expression / unparseable."""
    if not coin_expr:
        return None
    m = _DICE_RE.match(coin_expr)
    if not m:
        return None
    n, d, denom = int(m.group(1)), int(m.group(2)), m.group(3).lower()
    if n <= 0 or d <= 0:
        return None
    amount = sum(random.randint(1, d) for _ in range(n))
    return {'amount': amount, 'denom': denom}


def generate_loot(creature_name: str) -> Dict[str, Any]:
    """Pure function. Returns:
        {
            'creature':  str,                # original input
            'table_key': str,                # matched key or '_default'
            'coin':      {amount, denom} | None,
            'items':     list[str],          # copy of the table's item list
        }
    """
    key = _match_table_key(creature_name or '')
    table = LOOT_TABLES[key]
    coin = _roll_coin(table.get('coin'))
    items = list(table.get('items') or [])
    return {
        'creature':  creature_name or '',
        'table_key': key,
        'coin':      coin,
        'items':     items,
    }
