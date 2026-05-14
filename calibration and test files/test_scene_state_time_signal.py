"""Tests for Ship S51 — every-turn time signal in SCENE STATE block.

S50 verify surfaced body/footer divergence: state_footer (Discord embed)
shows correct day/phase from DB; narration body defaults to "morning
light" framing on non-advance turns because the LLM has no current-time
signal between time-advance moments. compute_time_directive only fires
on just_advanced=True; SCENE STATE (authoritative) block carried
Location/Tension/Recent NPCs/Last player action but not campaign_day or
day_phase.

Surgical fix: add `Day: {N}` and `Time of day: {phase}` lines to
scene_state_section at dnd_engine.py:5407, between Location and Tension.
LLM gets ground-truth time signal on every turn. §76 read-side analogue
closed at prompt-input layer; verifier candidate stays filed as safety
net per spec.

Run:
    cd /home/jordaneal/scripts && python3 test_scene_state_time_signal.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))


# ---------------------------------------------------------------------------
# Source-text regression guards on the production wiring.
# build_dm_context is too parameter-heavy to call directly without
# fixtures; source-text scanning verifies the wiring without DB setup.
# ---------------------------------------------------------------------------
engine_path = os.path.join(os.path.dirname(__file__), 'dnd_engine.py')
with open(engine_path) as f:
    engine_src = f.read()

# Locate the scene_state_section assignment (the f-string assembly).
# Bound by a unique post-assembly anchor — the `clocks = scene_state.get(...)`
# line that immediately follows the closing paren of the section assignment.
section_start = engine_src.find('scene_state_section = (\n            "\\n\\n=== SCENE STATE (authoritative)')
assert section_start != -1, \
    "could not locate scene_state_section assignment"
section_stop = engine_src.find("clocks = scene_state.get('progress_clocks')", section_start)
assert section_stop != -1, \
    "could not locate post-section anchor (clocks = scene_state.get(...))"
section_text = engine_src[section_start:section_stop]


# ---------------------------------------------------------------------------
# Assertion 1 — Day line is in the SCENE STATE block
# ---------------------------------------------------------------------------
assert '"Day: {_day_render}\\n"' in section_text or \
    'f"Day: {_day_render}\\n"' in section_text or \
    "Day: {_day_render}" in section_text, \
    f"'Day: {{_day_render}}' line missing from scene_state_section:\n{section_text}"
print("  ✓ 1. SCENE STATE block carries 'Day:' line")

# ---------------------------------------------------------------------------
# Assertion 2 — Time of day line is in the SCENE STATE block
# ---------------------------------------------------------------------------
assert "Time of day: {_phase_render}" in section_text, \
    f"'Time of day: {{_phase_render}}' line missing from scene_state_section:\n{section_text}"
print("  ✓ 2. SCENE STATE block carries 'Time of day:' line")

# ---------------------------------------------------------------------------
# Assertion 3 — both lines source from canonical scene_state keys
# (campaign_day + day_phase per dnd_engine.py:1208-1209)
# ---------------------------------------------------------------------------
# Verify the preceding lines extract from the right keys.
preamble_start = engine_src.rfind("_day = scene_state.get(", 0, section_start)
assert preamble_start != -1, \
    "could not locate _day extraction preamble before scene_state_section"
preamble_text = engine_src[preamble_start:section_start]
assert "_day = scene_state.get('campaign_day')" in preamble_text, \
    "must extract _day from scene_state['campaign_day']"
assert "_phase = scene_state.get('day_phase')" in preamble_text, \
    "must extract _phase from scene_state['day_phase']"
print("  ✓ 3. extraction uses canonical campaign_day + day_phase keys")

# ---------------------------------------------------------------------------
# Assertion 4 — None/missing handling renders '?' (no crash, no None render)
# ---------------------------------------------------------------------------
# Simulate the production logic locally (the assignments are simple
# truthy-fallback patterns identical to what's in the engine):
def _simulate_day_render(scene_state):
    day = scene_state.get('campaign_day')
    return day if day else '?'

def _simulate_phase_render(scene_state):
    phase = scene_state.get('day_phase')
    return phase if phase else '?'

# Missing key
assert _simulate_day_render({}) == '?', "missing campaign_day must render '?'"
assert _simulate_phase_render({}) == '?', "missing day_phase must render '?'"
# Explicit None
assert _simulate_day_render({'campaign_day': None}) == '?', \
    "None campaign_day must render '?'"
assert _simulate_phase_render({'day_phase': None}) == '?', \
    "None day_phase must render '?'"
# Explicit 0 (falsy int) — render '?' (day 0 isn't a real campaign day)
assert _simulate_day_render({'campaign_day': 0}) == '?', \
    "0 campaign_day must render '?'"
# Explicit empty string phase — render '?'
assert _simulate_phase_render({'day_phase': ''}) == '?', \
    "empty-string day_phase must render '?'"
print("  ✓ 4. None/missing/0/empty handled gracefully (renders '?')")

# ---------------------------------------------------------------------------
# Assertion 5 — Verify production preamble matches the simulated logic
# (preamble uses truthy fallback to '?' for both day and phase)
# ---------------------------------------------------------------------------
assert "_day_render = _day if _day else '?'" in preamble_text, \
    "production _day_render must use truthy fallback to '?'"
assert "_phase_render = _phase if _phase else '?'" in preamble_text, \
    "production _phase_render must use truthy fallback to '?'"
print("  ✓ 5. production fallback logic matches simulated truthy-'?' pattern")

# ---------------------------------------------------------------------------
# Assertion 6 — typical values render as expected
# ---------------------------------------------------------------------------
assert _simulate_day_render({'campaign_day': 10}) == 10
assert _simulate_phase_render({'day_phase': 'Midday'}) == 'Midday'
assert _simulate_phase_render({'day_phase': 'Late Night'}) == 'Late Night'
print("  ✓ 6. typical values render correctly (Day: 10 / Time of day: Midday)")

# ---------------------------------------------------------------------------
# Assertion 7 — Day + Time of day appear AFTER Location and BEFORE Tension
# (positioning consistent with spec — adjacent to Location as scene grounding)
# ---------------------------------------------------------------------------
location_idx = section_text.find("Location:")
day_idx = section_text.find("Day:")
phase_idx = section_text.find("Time of day:")
tension_idx = section_text.find("Tension:")
assert location_idx < day_idx < phase_idx < tension_idx, \
    f"expected ordering Location < Day < Time of day < Tension; got " \
    f"location={location_idx} day={day_idx} phase={phase_idx} tension={tension_idx}"
print("  ✓ 7. ordering: Location → Day → Time of day → Tension")

# ---------------------------------------------------------------------------
# Assertion 8 — module imports cleanly (catches any syntax break the edit
# might have introduced)
# ---------------------------------------------------------------------------
import dnd_engine
assert hasattr(dnd_engine, 'build_dm_context'), \
    "dnd_engine.build_dm_context must be importable"
print("  ✓ 8. dnd_engine module imports cleanly post-edit")

# ---------------------------------------------------------------------------
# Assertion 9 — compute_time_directive still untouched (separate
# responsibility: passive signal vs active beat). Verifies the just_advanced
# gate is intact — fix shape A explicitly does NOT touch this function.
# ---------------------------------------------------------------------------
orch_path = os.path.join(os.path.dirname(__file__), 'dnd_orchestration.py')
with open(orch_path) as f:
    orch_src = f.read()
ctd_start = orch_src.find("def compute_time_directive(")
assert ctd_start != -1
ctd_end = orch_src.find("\ndef ", ctd_start + 1)
assert ctd_end != -1, "could not locate end of compute_time_directive"
ctd_section = orch_src[ctd_start:ctd_end]
assert "if not scene_state or not just_advanced:" in ctd_section, \
    "compute_time_directive's just_advanced gate must remain intact " \
    "(S51 explicitly does not touch this; separate responsibility)"
print("  ✓ 9. compute_time_directive's just_advanced gate intact (untouched)")

# ---------------------------------------------------------------------------
# Assertion 10 — only ONE Day: + ONE Time of day: in the scene_state_section
# (no duplicate accidental wiring)
# ---------------------------------------------------------------------------
assert section_text.count("Day:") == 1, \
    f"expected exactly one Day: line; got {section_text.count('Day:')}"
assert section_text.count("Time of day:") == 1, \
    f"expected exactly one Time of day: line; got {section_text.count('Time of day:')}"
print("  ✓ 10. no duplicate Day:/Time of day: lines in section")

print()
print("All 10 S51 assertions pass.")
