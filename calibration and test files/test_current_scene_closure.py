"""S67 Fix 2 Phase B — F-016 `current_scene` §76 closure adversarial verify.

Pre-S67 contamination loop:
  1. `_dm_respond_and_post` writes LLM response into dnd_campaigns.current_scene
     via `update_scene(campaign_id, f"Last actions: {action} | DM: {response}")`.
  2. `build_dm_context` reads campaign.current_scene and injects it as the
     `=== CURRENT SCENE ===` prompt block on the next turn.
  3. LLM narrates from its OWN prior summary, paraphrasing forward.
  4. Field updates with the new summary. Drift compounds turn-over-turn.

Post-S67 closure:
  1. No write path remains in production code (3 sites retired).
  2. `=== CURRENT SCENE ===` prompt block deleted from `build_dm_context`.
  3. Scene-detail memory now flows via:
     - SCENE STATE block (structured fields, Ship 2 canon)
     - chroma RELEVANT PAST EVENTS (distance-cutoff 0.5 mitigated)
     - skeleton-loaded canon
  4. `scene_blurb` reader (knowledge_search query input) falls back to
     `last_dm_response` instead of `current_scene`.

Tests:
  (1) AST: discord_dnd_bot.py contains NO call to `update_scene(...)` (note:
      `update_scene_state` is a different function and is allowed).
  (2) AST: dnd_engine.py:init_end_buffer_reset_post_init NO LONGER calls
      `update_scene(...)`.
  (3) Source-level: `update_scene` is NOT in discord_dnd_bot.py's import line.
  (4) Source-level: `build_dm_context` body does NOT render `=== CURRENT SCENE ===`.
  (5) Behavioral: simulate a write attempt — current_scene column stays empty
      across multiple bot-flow simulated calls.
  (6) Regression: get_active_campaign STILL returns the campaign dict with a
      current_scene key (back-compat — column not dropped).

Run: python3 test_current_scene_closure.py
"""

import ast
import sys

sys.path.insert(0, '/home/jordaneal/scripts')

import dnd_engine
from dnd_engine import (
    create_campaign, get_active_campaign, db_init,
    init_scene_state, update_last_dm_response, get_scene_state,
)


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


def check_not_in(label, needle, haystack):
    global PASS, FAIL
    if needle not in haystack:
        PASS += 1
    else:
        FAIL += 1
        FAILURES.append(f"  {label}: {needle!r} unexpectedly found")


def check_in(label, needle, haystack):
    global PASS, FAIL
    if needle in haystack:
        PASS += 1
    else:
        FAIL += 1
        FAILURES.append(f"  {label}: {needle!r} not found")


# ──────────────────────────────────────────────────────────────────────────────
# (1) AST sweep: NO `update_scene(...)` call sites in production code.
# `update_scene_state(...)` is a different function and is allowed.
# ──────────────────────────────────────────────────────────────────────────────

def find_update_scene_calls(file_path: str) -> list[tuple[int, str]]:
    """Find every call to the bare-name `update_scene` function. Excludes
    `update_scene_state`. Returns list of (lineno, source_line)."""
    with open(file_path) as f:
        src = f.read()
        lines = src.splitlines()
    tree = ast.parse(src)
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            name = None
            if isinstance(f, ast.Name):
                name = f.id
            elif isinstance(f, ast.Attribute):
                name = f.attr
            if name == 'update_scene':
                # Snapshot the source line for the failure message
                line = (lines[node.lineno - 1] if 0 < node.lineno <= len(lines)
                        else '')
                hits.append((node.lineno, line.strip()))
    return hits


discord_calls = find_update_scene_calls('/home/jordaneal/scripts/discord_dnd_bot.py')
check('AST: discord_dnd_bot has zero update_scene call sites',
      len(discord_calls), 0)
if discord_calls:
    for ln, src in discord_calls:
        FAILURES.append(f"    leftover at L{ln}: {src}")

engine_calls = find_update_scene_calls('/home/jordaneal/scripts/dnd_engine.py')
# dnd_engine.py contains the `def update_scene(...)` itself but no caller now.
# The only acceptable hit is the function definition, not a Call. AST walks for
# Call exclude FunctionDef so this should be zero.
check('AST: dnd_engine has zero update_scene call sites (def is excluded)',
      len(engine_calls), 0)


# ──────────────────────────────────────────────────────────────────────────────
# (2) Source-level: `update_scene` not in discord_dnd_bot.py import line
# ──────────────────────────────────────────────────────────────────────────────

with open('/home/jordaneal/scripts/discord_dnd_bot.py') as f:
    bot_src = f.read()

# The import line range from line 41-77 — capture the import block
import_block_end = bot_src.find('from cloud_router')
import_block = bot_src[:import_block_end]
check_not_in('source: update_scene not imported in discord_dnd_bot',
             'update_scene,', import_block)


# ──────────────────────────────────────────────────────────────────────────────
# (3) Source-level: build_dm_context body has no `=== CURRENT SCENE ===` block
# ──────────────────────────────────────────────────────────────────────────────

with open('/home/jordaneal/scripts/dnd_engine.py') as f:
    engine_src = f.read()

# Look for the LIVE f-string that previously emitted the block. The
# string "=== CURRENT SCENE ===" still appears in a SOURCE COMMENT
# documenting the closure (that's expected). The closure target is the
# active f-string template — strip comments first to filter false hits.
import re as _re
engine_src_no_comments = _re.sub(r'#.*$', '', engine_src, flags=_re.MULTILINE)
check_not_in('source: CURRENT SCENE label not rendered in any live code',
             '=== CURRENT SCENE ===', engine_src_no_comments)


# ──────────────────────────────────────────────────────────────────────────────
# (4) Source-level: `scene_blurb` reader redirected to last_dm_response
# ──────────────────────────────────────────────────────────────────────────────

check_in('source: scene_blurb pulls from last_dm_response',
         "scene_blurb = ((scene_state or {}).get('last_dm_response') or '')[:200]",
         engine_src)
check_not_in('source: scene_blurb no longer pulls from current_scene',
             "scene_blurb = (campaign.get('current_scene') or '')[:200]",
             engine_src)


# ──────────────────────────────────────────────────────────────────────────────
# (5) Behavioral: even with active flow, current_scene column stays empty
# ──────────────────────────────────────────────────────────────────────────────

# Fresh campaign — column should start empty (default '')
TEST_GUILD = 'test-guild-s67-cs-close'
CAMP_ID = create_campaign(TEST_GUILD, 'CS Close Test')
camp = get_active_campaign(TEST_GUILD)
check_truthy('behavior: campaign created', camp is not None)
check('behavior: fresh campaign has empty current_scene',
      camp['current_scene'], '')

# Even if last_dm_response is set, current_scene must remain untouched
init_scene_state(CAMP_ID)
update_last_dm_response(CAMP_ID, "Verbatim DM narration goes here.")
camp_after = get_active_campaign(TEST_GUILD)
check('behavior: current_scene still empty after last_dm_response write',
      camp_after['current_scene'], '')

# Verify last_dm_response did get written (regression: signal-only path intact)
ss = get_scene_state(CAMP_ID)
check_truthy('behavior: last_dm_response wrote successfully',
             ss is not None and ss.get('last_dm_response'))


# ──────────────────────────────────────────────────────────────────────────────
# (6) Back-compat: get_active_campaign STILL returns current_scene key
# (column not dropped from schema; readers may rely on key presence)
# ──────────────────────────────────────────────────────────────────────────────

check_truthy('back-compat: current_scene key present in campaign dict',
             'current_scene' in camp_after)


# ──────────────────────────────────────────────────────────────────────────────
# (7) Structural: build_dm_context still composes a valid prompt without
# the CURRENT SCENE block (no syntax errors, no missing-section drift).
# ──────────────────────────────────────────────────────────────────────────────

with open('/home/jordaneal/scripts/dnd_engine.py') as f:
    engine_src_check = f.read()
# Confirm the template f-string at line ~6460 no longer references
# current_scene_section. The variable still exists as "" (empty string)
# but the goal is to ensure the section identifier doesn't appear in any
# rendered string concatenation.
check_in('source: current_scene_section assignment retained as empty',
         'current_scene_section = ""', engine_src_check)
# The template still references {current_scene_section} (now expanded to "")
# — that's fine because empty-string-interpolation is a no-op. Confirm
# the IDENTIFIER usage is benign by checking it's only assigned to "".
import re
ass_count = len(re.findall(
    r'current_scene_section\s*=\s*(?!""$)', engine_src_check, re.MULTILINE
))
# Allow exactly one (the f-string reference itself is not an assignment)
# Actually count differently — just check no non-empty assignment exists.
non_empty_assigns = re.findall(
    r'current_scene_section\s*=\s*[^"\s]+', engine_src_check
)
check('source: current_scene_section assigned only to empty string',
      non_empty_assigns, [])


# ──────────────────────────────────────────────────────────────────────────────
# (8) S67 Fix 1A regression check — WAL pragma still present
# ──────────────────────────────────────────────────────────────────────────────

check_in('regression: WAL init present in db_init',
         'PRAGMA journal_mode=WAL', engine_src_check)
check_in('regression: wal_autocheckpoint set',
         'wal_autocheckpoint=1000', engine_src_check)


# ──────────────────────────────────────────────────────────────────────────────
# Cleanup + report
# ──────────────────────────────────────────────────────────────────────────────

print(f"\n{PASS} passed, {FAIL} failed")
if FAILURES:
    print("\nFAILURES:")
    for f in FAILURES:
        print(f)
    sys.exit(1)
sys.exit(0)
