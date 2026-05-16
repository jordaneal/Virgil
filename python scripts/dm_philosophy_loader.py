"""DM philosophy loader — Track 3, Session 14.

Reads an authored DM philosophy markdown file and surfaces it as a top-
priority directive in the system prompt. Companion to skeleton_loader,
but global (not per-campaign) and content-only (not parsed for
entities — the file is consumed verbatim by the LLM).

Architectural intent:
  Phase 1/12 directives are *imperative state interpreters* (roll
  discipline, capability grounding, pacing, central thread). They tell
  the DM what move to make given current state. The philosophy block
  defines *how those moves should be interpreted* — what good escalation
  looks like, when to break the fourth wall, what kind of pressure
  feels alive vs flat. It frames the operating policy that the other
  directives compose against.

Priority placement:
  Above pacing/central-thread directives in the prompt template, but
  BELOW canonical state blocks (skeleton, scene state, mode). Reason:
  state defines what's true; philosophy defines how to respond to it.
  State outranks policy as input.

File layout:
  /home/jordaneal/virgil-docs/DM_PHILOSOPHY.md
  (Moved from ~/scripts/ at S73.5 — canonical now lives with the other
  canon docs in ~/virgil-docs/, allowing PC push-docs to roundtrip
  natively without symlinks or special-case routing.)

Format:
  Free-form markdown. The whole file body is injected verbatim into the
  prompt under === DM PHILOSOPHY === (after stripping leading/trailing
  whitespace). No structured sections, no parser strictness — this is a
  living artifact Jordan tunes between sessions.

Caching:
  In-memory mtime cache. Reload is automatic on file change; no
  service restart required. Same pattern as skeleton_loader but global
  (single file, no campaign keying).
"""

import os
import threading
from pathlib import Path

from dnd_engine import log


PHILOSOPHY_PATH = Path("/home/jordaneal/virgil-docs/DM_PHILOSOPHY.md")

# Cap injection size — large philosophy docs would crowd out scene state
# and history. 6000 chars matches skeleton's max_chars default. The doc
# is meant to be tight: principles, not prose.
PHILOSOPHY_MAX_CHARS = 6000


# In-memory mtime cache. Single global entry: (mtime, content).
_cache: tuple | None = None
_cache_lock = threading.Lock()


def _read_philosophy_file() -> str | None:
    """Read PHILOSOPHY_PATH, return text body or None when missing/empty.

    mtime-gated: re-reads only when the file has changed since last read.
    Concurrent calls share the lock briefly during the file stat + read.
    """
    global _cache

    if not PHILOSOPHY_PATH.exists():
        return None

    try:
        mtime = PHILOSOPHY_PATH.stat().st_mtime
    except OSError as e:
        log(f"dm_philosophy_loader: stat failed: {e}")
        return None

    with _cache_lock:
        if _cache is not None and _cache[0] == mtime:
            return _cache[1]

        try:
            text = PHILOSOPHY_PATH.read_text(encoding='utf-8')
        except (OSError, UnicodeDecodeError) as e:
            log(f"dm_philosophy_loader: read failed: {e}")
            return None

        text = text.strip()
        if len(text) > PHILOSOPHY_MAX_CHARS:
            log(f"dm_philosophy_loader: doc truncated "
                f"{len(text)} -> {PHILOSOPHY_MAX_CHARS} chars")
            text = text[:PHILOSOPHY_MAX_CHARS] + "\n\n[truncated]"

        _cache = (mtime, text)
        log(f"dm_philosophy_loader: loaded {len(text)} chars "
            f"from {PHILOSOPHY_PATH}")
        return text


def get_philosophy_block() -> str:
    """Return the philosophy directive text or '' when no doc exists.

    Called per-turn from dm_respond. Empty string suppresses the prompt
    block entirely. Same advisory shape as compute_pacing_directive
    and compute_central_thread_directive.
    """
    text = _read_philosophy_file()
    if not text:
        return ''
    return text


def reload() -> bool:
    """Force a re-read on next call by clearing the mtime cache.

    Useful for debugging or for a future /philosophy reload command.
    Returns True if a doc exists, False otherwise.
    """
    global _cache
    with _cache_lock:
        _cache = None
    return PHILOSOPHY_PATH.exists()
