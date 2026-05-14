"""
x_utils.py — Shared utility module for CRD3 cross-extractor analysis scripts.
All paths relative to /home/jordaneal/corpus_builder/cross_extractor/.
"""

import json
import os
from collections import defaultdict

_BASE = os.path.dirname(os.path.abspath(__file__))
_UNIFIED = os.path.join(_BASE, "all_records_unified.jsonl")
_STREAMS = os.path.join(_BASE, "streams")

# ---------------------------------------------------------------------------
# Module-level cache: loaded once at import time
# _eps_by_source[source] -> set of episode_combined strings
# _src_by_episode[episode_combined] -> set of source strings
# ---------------------------------------------------------------------------
_eps_by_source: dict[str, set] = defaultdict(set)
_src_by_episode: dict[str, set] = defaultdict(set)

def _build_episode_index() -> None:
    with open(_UNIFIED) as f:
        for line in f:
            r = json.loads(line)
            ep = r["episode_combined"]
            src = r["source"]
            _eps_by_source[src].add(ep)
            _src_by_episode[ep].add(src)

_build_episode_index()


# ---------------------------------------------------------------------------
# Core loaders
# ---------------------------------------------------------------------------

def load_unified_records(
    sources_filter: list[str] | None = None,
    episodes_filter: set[str] | None = None,
) -> list[dict]:
    """
    Read all_records_unified.jsonl, apply optional filters, and normalize:
      - category == None  ->  "TM_UNKNOWN"
    Returns list of record dicts.
    """
    records = []
    with open(_UNIFIED) as f:
        for line in f:
            r = json.loads(line)
            if sources_filter and r["source"] not in sources_filter:
                continue
            if episodes_filter and r["episode_combined"] not in episodes_filter:
                continue
            if r.get("category") is None:
                r["category"] = "TM_UNKNOWN"
            records.append(r)
    return records


def load_episode_stream(episode_combined: str) -> dict:
    """Read streams/{episode_combined}.json and return the dict."""
    path = os.path.join(_STREAMS, f"{episode_combined}.json")
    with open(path) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Scene-fence helpers
# ---------------------------------------------------------------------------

def get_scene_fence_turns(episode_stream: dict) -> list[int]:
    """
    Return sorted list of turn_numbers where source=="TM" and
    category=="scene_transition".
    """
    fences = []
    for ev in episode_stream.get("events", []):
        if ev["source"] == "TM" and ev.get("category") == "scene_transition":
            fences.append(ev["turn_number"])
    return sorted(fences)


def is_combat_state_via_ec_reinforcement(
    episode_stream: dict,
    turn_number: int,
    window: int = 25,
) -> bool:
    """
    §13.4 expanded combat-state signal.
    True if:
      - any EC record fires within ±window turns of turn_number in the stream, OR
      - any TM record at turn_number has payload.is_combat_state == True.
    """
    for ev in episode_stream.get("events", []):
        if ev["source"] == "EC":
            if abs(ev["turn_number"] - turn_number) <= window:
                return True
        if ev["source"] == "TM" and ev["turn_number"] == turn_number:
            if ev.get("payload", {}).get("is_combat_state", False):
                return True
    return False


def same_scene_within_window(
    fence_turns: list[int],
    t1: int,
    t2: int,
    window: int,
) -> bool:
    """
    Returns False if abs(t2 - t1) > window.
    Returns False if any fence_turn strictly between min(t1, t2) and max(t1, t2).
    Returns True otherwise.
    """
    if abs(t2 - t1) > window:
        return False
    lo = min(t1, t2)
    hi = max(t1, t2)
    for ft in fence_turns:
        if lo < ft < hi:
            return False
    return True


# ---------------------------------------------------------------------------
# Episode-level aggregates
# ---------------------------------------------------------------------------

def episode_late_fraction(episode_stream: dict, threshold: float = 0.75) -> float:
    """
    Fraction of events with episode_position_pct >= threshold.
    Events missing episode_position_pct are excluded from numerator and
    denominator.
    """
    events = episode_stream.get("events", [])
    valid = [
        ev for ev in events
        if ev.get("episode_position_pct") is not None
    ]
    if not valid:
        return 0.0
    return sum(1 for ev in valid if ev["episode_position_pct"] >= threshold) / len(valid)


# ---------------------------------------------------------------------------
# Intersection helpers
# ---------------------------------------------------------------------------

def get_all_four_intersection() -> set[str]:
    """
    Return set of episode_combined strings present in all 4 sources
    (EC, TM, LR, CC). Computed from the module-level index.
    """
    all_four = None
    for src in ("EC", "TM", "LR", "CC"):
        eps = _eps_by_source.get(src, set())
        if all_four is None:
            all_four = set(eps)
        else:
            all_four &= eps
    return all_four or set()


def get_pair_intersection(source_a: str, source_b: str) -> set[str]:
    """
    Return set of episode_combined strings present in both source_a and
    source_b. Computed from the module-level index.
    """
    return _eps_by_source.get(source_a, set()) & _eps_by_source.get(source_b, set())
