#!/usr/bin/env python3
"""
Encounter Cadence Extractor v1.

Reads CRD3 (`c=2` alignment dir, MATT-anchored) and emits one JSON record per
init-anchored event. Both fresh-start encounters and mid-fight wave/phase
events emit; `is_fresh_encounter` distinguishes them.

Per CORPUS_BUILDER.md: deterministic regex only, read-only on the corpus,
fail-open on unknown formats, idempotent on event content.

Spec: ENCOUNTER_CADENCE_V1_SPEC.md (Phase 1 doc) + chat-locked decisions
applied in this implementation. Schema is locked per Phase 2 prompt.

Usage:
    python3 encounter_cadence.py --sample
        Runs on 10 hand-sample episodes. Writes one combined file at
        ../samples/encounter_cadence_sample.json.

    python3 encounter_cadence.py --full
        Runs on all CRD3. Writes one file per episode to
        ../output/encounter_cadence/{episode_id}.json.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

EXTRACTOR_VERSION = "encounter_cadence_v1_3"

CORPUS_BUILDER = Path(__file__).resolve().parent.parent
SOURCE_BASE = Path("/mnt/virgil_storage/dnd_datasets/crd3/data/aligned data/c=2")
OUTPUT_DIR = CORPUS_BUILDER / "output" / "encounter_cadence"
SAMPLE_PATH = CORPUS_BUILDER / "samples" / "encounter_cadence_sample_v1_3.json"

PRECEDING_CONTEXT_BUDGET = 1500
NARRATION_BUILDUP_THRESHOLD_CHARS = 500
CAUSALITY_WINDOW_TURNS = 15

SAMPLE_EPISODES = [
    "C1E001", "C1E020", "C1E030", "C1E049", "C1E060",
    "C1E095", "C2E001", "C2E020", "C2E030", "C2E045",
]

EPISODE_ID_RE = re.compile(r"^(C\d+)E(\d{3,4})$")


# ---------------------------------------------------------------------------
# Stage 0 — discourse-context classification (v1.3)
# ---------------------------------------------------------------------------
#
# Before Stage 1 fires, classify the trigger turn + surrounding context as
# one of {DISCOURSE, STATE, EVENT}.
#
#   DISCOURSE — meta-narration ABOUT initiative rather than triggering it
#     (episode-break recap/promo, mid-combat init-count narration, summon
#     init-roll for ordering). Reject the candidate; log [FILTERED_DISCOURSE].
#
#   STATE — narration of mid-combat state without new init being established
#     (damage rolls / turn-order narration in last 5 turns). Continue to
#     Stage 1 with `force_combat_active=True`, so the wave classification
#     gate is reliably triggered even if the existing combat_active heuristic
#     misses it.
#
#   EVENT — actual mechanical initiative event. Default. Continue to Stage 1
#     with normal combat_active calculation.

# Episode-break / recap / promo markers — when a candidate fires inside an
# ad break or cold-open recap, it isn't an init event.
DISCOURSE_EPISODE_BREAK = re.compile(
    r"\bwelcome\s+back\b"
    r"|\blast\s+we\s+left\s+off\b"
    r"|\bpreviously\s+on\b"
    r"|\bthat\s+does\s+it\s+for\s+(?:us|tonight)\b"
    r"|\bsee\s+you\s+(?:here\s+)?(?:shortly|next\s+(?:week|time)|in\s+a\s+(?:bit|moment))"
    r"|\bwe'?ll\s+(?:be\s+right\s+back|come\s+back)\b"
    r"|\[break\]|\[BREAK\]|\[dramatic\s+music\]"
    r"|\bquick\s+break\b|\btake\s+(?:a\s+)?(?:short\s+|quick\s+)?break\b"
    r"|\b\d+[kK]\s+(?:arrival|figure|figurine)\b"
    r"|\bavailable\s+for\s+one\s+more\s+day\b"
    r"|\blast\s+week'?s?\s+(?:episode|stream|show|game)\b"
    r"|\bnext\s+week'?s?\s+(?:episode|stream|show|game)\b"
    r"|\bcomic\s+(?:available|out|now\s+available)\b"
    r"|\bif\s+you\s+want\s+to\s+get\s+(?:that|it)\b"
    r"|\bcheck\s+(?:that\s+out|it\s+out)\s+at\b"
    r"|\bonce\s+it'?s\s+gone\s+it'?s\s+gone\b"
    r"|\bgo\s+to\s+(?:our|the)\s+(?:store|website)\b"
    r"|\bvisit\s+(?:our|the)\s+(?:store|website|merch)\b",
    re.I,
)

# Init-order recount / reroll discussion in the trigger turn — meta-narrative
# about initiative slots, not establishing init.
DISCOURSE_INIT_RECOUNT = re.compile(
    r"\bwhat\s+did\s+(?:you|they|he|she|\w+)\s+roll\s+for\s+initiative\b"
    r"|\bwhat'?s?\s+(?:your|his|her|their|\w+'?s)\s+initiative\b"
    r"|\bpre[\- ]rolled?\s+(?:an?\s+|the\s+)?initiative\b"
    r"|\b(?:can|may)\s+(?:I|you|we)\s+(?:use|reroll|reroll(?:ing)?)\s+\w+\s+(?:for|on)\s+initiative\b"
    r"|\bcan\s+I\s+reroll\s+(?:initiative|that\s+initiative)\b"
    r"|\byou\s+can\s+reroll\s+initiative\s+if\s+you\s+want\b"
    r"|\binitiative\s+count\s+\d+\b"
    r"|\bwho'?s?\s+next\s+in\s+(?:the\s+)?(?:initiative|order)\b"
    r"|\b(?:I|I'?ll|I\s+will)\s+(?:have\s+to\s+)?roll\s+initiative\s+for\s+(?:it|him|her|them|the\s+\w+)\s+(?:separately|as\s+part)"
    r"|\bremind\s+me\s+(?:of\s+|what\s+)(?:your|the)\s+initiative",
    re.I,
)

# Init-order narration in surrounding context (mid-combat re-statement of
# whose turn it is, who's up next). When trigger is in this context AND
# trigger is itself a discourse-shape "What did you roll for initiative?"-
# style question rather than an init-rolling phrase, treat as DISCOURSE.
DISCOURSE_SURROUNDING_TURN_ORDER = re.compile(
    r"\bthat\s+brings\s+us\s+to\b"
    r"|\bnow\s+it'?s\s+\w+'?s\s+turn\b"
    r"|\bback\s+to\s+(?:you|\w+)\b"
    r"|\b(?:end|top)\s+of\s+(?:your|the|his|her)\s+(?:round|turn|initiative)"
    r"|\bnext\s+(?:up|in\s+(?:the\s+)?initiative)\b",
    re.I,
)

# Damage / turn-order / combat-action signals — when present in the last
# few turns, a new init-shaped trigger is occurring inside ongoing combat.
# Set force_combat_active=True so Stage 2 wave detection gets the boost.
STATE_DAMAGE = re.compile(
    r"\b\d+\s+points?\s+of\s+(?:slashing|piercing|bludgeoning|fire|cold|"
    r"acid|psychic|necrotic|radiant|thunder|lightning|force|poison)\s+damage\b",
    re.I,
)

STATE_TURN_ORDER = re.compile(
    r"\byour\s+turn\b"
    r"|\b(?:end|top|start)\s+of\s+(?:your|the|his|her|this)\s+(?:round|turn)"
    r"|\bthat\s+ends\s+(?:your|his|her|\w+'?s)\s+turn\b"
    r"|\bnow\s+it'?s\s+\w+'?s\s+turn\b"
    r"|\bback\s+to\s+you\b",
    re.I,
)

STATE_COMBAT_ROLLS = re.compile(
    r"\b\d{1,2}\s+to\s+hit\b"
    r"|\bthat\s+hits\b|\bthat\s+misses\b"
    r"|\bmake\s+a\s+saving\s+throw\b"
    r"|\broll\s+(?:for\s+)?damage\b",
    re.I,
)


def stage_0_classify(trigger_text, preceding_turns, last_n_turns_for_state=5,
                     last_n_turns_for_break=3):
    """Classify a Stage-1 candidate as DISCOURSE, STATE, or EVENT.

    Returns (label, reason). label in {"DISCOURSE", "STATE", "EVENT"}.
    """
    # DISCOURSE — episode break / recap / promo. Check trigger and the last
    # `last_n_turns_for_break` turns regardless of speaker.
    if DISCOURSE_EPISODE_BREAK.search(trigger_text):
        m = DISCOURSE_EPISODE_BREAK.search(trigger_text)
        return "DISCOURSE", f"episode_break in trigger: {m.group()!r}"
    seen = 0
    for p in reversed(preceding_turns):
        seen += 1
        if seen > last_n_turns_for_break:
            break
        if DISCOURSE_EPISODE_BREAK.search(p["text"]):
            m = DISCOURSE_EPISODE_BREAK.search(p["text"])
            return "DISCOURSE", f"episode_break in preceding: {m.group()!r}"

    # DISCOURSE — init-order recount / reroll discussion in trigger.
    if DISCOURSE_INIT_RECOUNT.search(trigger_text):
        m = DISCOURSE_INIT_RECOUNT.search(trigger_text)
        return "DISCOURSE", f"init_recount in trigger: {m.group()!r}"

    # STATE — damage / turn-order / combat rolls in last N turns. Doesn't
    # reject; just flags for combat_active boost.
    seen = 0
    state_reason = None
    for p in reversed(preceding_turns):
        seen += 1
        if seen > last_n_turns_for_state:
            break
        if STATE_DAMAGE.search(p["text"]):
            state_reason = f"damage_resolution in preceding: turn {p['turn_number']}"
            break
        if STATE_TURN_ORDER.search(p["text"]):
            state_reason = f"turn_order in preceding: turn {p['turn_number']}"
            break
        if STATE_COMBAT_ROLLS.search(p["text"]):
            state_reason = f"combat_rolls in preceding: turn {p['turn_number']}"
            break
    if state_reason:
        return "STATE", state_reason

    return "EVENT", None


# ---------------------------------------------------------------------------
# Stage 1 — candidate detection
# ---------------------------------------------------------------------------

# Patch 7: every alternative requires the literal word `initiative` adjacent to
# the roll/init verb. v1.1's `need\s+(?:you|...)\s+to\s+roll` branch matched
# turns like "I need you to roll a wisdom save" — those are mid-combat reaction
# rolls, not init events. Stage 1 must reject them.
POSITIVE_INIT = re.compile(
    # Core: any conjugation of "roll initiative" (covers "roll", "rolls",
    # "rolling", "rolled", "reroll[ing|s|ed]", with optional "for"/"some").
    r"\b(?:re)?roll(?:s|ing|ed)?\s+(?:for\s+|some\s+)?initiative\b"
    # "initiative has now kicked in", "initiative kicked in"
    r"|\binitiative\s+(?:has\s+(?:now\s+)?|now\s+)?kicked\s+in\b"
    # "now in initiative", "we're in initiative"
    r"|\b(?:now|we'?re)\s+in\s+initiative\b"
    # "initiative is being rolled"
    r"|\binitiative\s+is\s+being\s+rolled\b"
    # "for initiative" used as adverbial phrase ("a roll for initiative",
    # "going to be a roll for initiative")
    r"|\bfor\s+initiative\b",
    re.I,
)

# Patch 7: explicit FP-reject list. If the trigger turn ONLY matches this
# pattern (i.e., POSITIVE_INIT doesn't fire but a generic dice-roll instruction
# does), the turn isn't an init event. In practice the new POSITIVE_INIT
# already filters these because it requires the word `initiative`. The reject
# list stays as a defense-in-depth: if a future regex extension accidentally
# loosens POSITIVE_INIT, this catches the well-known FP shapes seen in the
# eval-set construction notes.
NON_INIT_ROLL = re.compile(
    # "roll a wisdom save", "roll a constitution saving throw", "roll a check"
    r"\broll\s+a(?:n)?\s+(?:[a-z][a-z\-\s]{1,40}?)?(?:save|saving\s+throw|check)\b"
    # "make a [stat] save"
    r"|\bmake\s+a(?:n)?\s+(?:[a-z][a-z\-\s]{1,40}?)?(?:save|saving\s+throw|check)\b"
    # "roll a d20", "roll a d12 minus one"
    r"|\broll\s+a\s+d\d+\b"
    # "roll a [skill] check"
    r"|\broll\s+(?:a(?:n)?\s+)?(?:concentration|acrobatics|athletics|insight|"
    r"perception|investigation|survival|stealth|persuasion|deception|"
    r"intimidation|history|arcana|nature|religion|medicine|sleight\s+of\s+hand|"
    r"animal\s+handling|performance)\s+(?:check|save|saving\s+throw)\b",
    re.I,
)

# Mid-combat noise — these do NOT count as init-rolling events even if
# `initiative` appears.
NEGATIVE_INIT_NOISE = re.compile(
    r"(?:initiative\s+order"
    r"|(?:next|top)\s+(?:up\s+)?(?:in\s+)?(?:the\s+)?initiative"
    r"|(?:currently|still)\s+in\s+initiative"
    r"|(?:not\s+)?out\s+of\s+initiative"
    r"|chang(?:e[ds]?|ing)\s+(?:his|her|their)\s+initiative"
    r"|keeping\s+(?:the\s+)?(?:same\s+)?initiative"
    r"|same\s+initiative\s+(?:order|round)"
    r"|initiative\s+(?:is|was|of)\s+\d"
    r"|your\s+initiative\s+(?:is|was|of|goes)"
    r"|already\s+rolled\s+initiative"
    r"|already\s+(?:in|on)\s+(?:the\s+)?initiative"
    r"|in\s+the\s+initiative\s+order"
    r"|on\s+the\s+initiative\s+(?:order|round)"
    r"|holds?\s+(?:his|her|their)\s+initiative)",
    re.I,
)


def is_init_candidate(text):
    """True if a MATT turn is announcing an init roll (fresh or wave).

    Patch 7 hardens Stage 1: a candidate fires only if the trigger turn
    contains an explicit `initiative` reference (POSITIVE_INIT) AND it doesn't
    match the mid-combat noise filter (NEGATIVE_INIT_NOISE).
    """
    if not POSITIVE_INIT.search(text):
        # Not an init event — log a `[FILTERED_NON_INIT]` line if it nonetheless
        # contains the high-noise dice-roll pattern, useful when diagnosing
        # extractor recall in future calibration cycles.
        if NON_INIT_ROLL.search(text):
            log_filtered_non_init(text)
        return False
    if NEGATIVE_INIT_NOISE.search(text):
        return False
    return True


# ---------------------------------------------------------------------------
# Wave/phase detection (priority 1 in classification)
# ---------------------------------------------------------------------------

WAVE_PARTY_JOIN = re.compile(
    r"(?:the\s+(?:people|three|both|two|few|other(?:s)?)|those|"
    r"(?:both|all|the\s+\d+)\s+of\s+you)"
    r"\s+(?:who\s+)?(?:just\s+|are\s+|now\s+)?"
    r"(?:woke|landed|fell|joined|appeared|came\s+in|came\s+down|dropped\s+in|"
    r"now\s+roll|entering\s+(?:the\s+)?(?:fray|fight|combat)|"
    r"joining\s+(?:in|the\s+(?:fight|combat|fray)))"
    r"|both\s+of\s+you\s+roll\s+initiative\s+to\s+see"
    r"|the\s+rest\s+of\s+you\s+(?:guys\s+)?roll\s+initiative"
    # Patch 8 widening: "anyone who cares to get involved" — open invitation
    # for new combatants to join existing fight.
    r"|\banyone\s+who\s+(?:cares\s+to\s+)?(?:get\s+involved|join(?:s|ing)?)"
    r"|\bdo\s+you\s+want\s+to\s+roll\s+to\s+get\s+involved"
    r"|\bcares?\s+to\s+get\s+involved\b",
    re.I,
)

WAVE_REINFORCEMENT = re.compile(
    r"\b(?:reinforcements?|backup|new\s+wave|second\s+wave|fresh\s+wave|more\s+(?:enemies|guards|figures|creatures))\b",
    re.I,
)

WAVE_PHASE_SHIFT = re.compile(
    r"\breroll(?:ing)?\s+(?:for\s+)?initiative"
    r"|reroll\s+(?:your\s+)?initiative"
    r"|new\s+phase"
    r"|phase\s+(?:two|three|change|shift)"
    r"|round\s+resets"
    r"|time\s+flux"
    r"|time\s+seems\s+to\s+(?:shift|move|warp)",
    re.I,
)

# Patch 2: semantic-wave detection. Active when init is already in progress
# this episode and the trigger has new-combatant shape — even without literal
# wave phrasing.
WAVE_NEW_COMBATANT_SHAPE = re.compile(
    r"\broll\s+initiative\s+for\s+(?:the\s+|an?\s+|its?\s+|her\s+|his\s+|their\s+)?[a-z]"
    r"|\bboth\s+of\s+you\s+(?:roll|now\s+roll)\s+initiative"
    r"|\bthe\s+(?:two|three|four|few|rest)\s+of\s+you\s+(?:roll|now\s+roll)\s+initiative"
    r"|\byou\s+who\s+just\s+(?:landed|woke|fell|dropped|joined|arrived)",
    re.I,
)

# Summon-language for reinforcement subtype (patch 2): a creature/elemental/etc.
# entering an existing fight as a player-summoned ally or DM-introduced
# reinforcement.
WAVE_SUMMON_LANGUAGE = re.compile(
    r"\b(?:elemental|familiar|companion|ally|the\s+\w+\s+you\s+summoned|"
    r"summoned\s+\w+|summon\s+\w+|conjured\s+\w+|the\s+\w+\s+(?:joins|enters)\s+(?:the\s+)?(?:fight|combat|fray))"
    r"|\broll\s+initiative\s+for\s+(?:the\s+)?(?:elemental|fire\s+elemental|water\s+elemental|"
    r"earth\s+elemental|air\s+elemental|familiar|companion|spirit|guardian|conjured|"
    r"summoned|spell|creature)",
    re.I,
)


# Patch 8: scene-transition markers — when present in the trigger or recent
# MATT context, a new init call is treated as a fresh start even when prior
# init has been seen this episode.
#
# Tight patterns only — bare "you reach" / "as you approach" over-fired on
# combat narration ("you reach forward and grab", "as you approach the
# dragon"). Keep markers that clearly delimit a scene change.
SCENE_TRANSITION_MARKERS = re.compile(
    r"\b(?:as\s+you\s+(?:enter\s+the|step\s+into\s+the|walk\s+into\s+the|"
    r"come\s+upon\s+the|arrive\s+at\s+the)"
    r"|you\s+arrive\s+at\s+the"
    r"|you\s+come\s+upon\s+(?:a|an|the)"
    r"|(?:that|one)\s+(?:night|morning|evening)"
    r"|the\s+next\s+(?:morning|day|evening|night)"
    r"|after\s+(?:several|a\s+few|some|many)\s+(?:days|hours|minutes|miles|weeks)"
    r"|(?:hours|days|weeks|miles)\s+(?:later|of\s+travel|of\s+walking|pass)"
    r"|traveling\s+for\s+(?:several|a\s+few|some|many)?\s*(?:days|hours|miles)"
    r"|new\s+(?:combat|encounter|fight|battle|scene|location)"
    r"|another\s+(?:combat|encounter|fight|battle|scene)"
    r"|the\s+next\s+(?:fight|combat|encounter|battle|scene|day|morning)"
    r"|the\s+scene\s+(?:shifts?|changes?|transitions?)"
    r"|welcome\s+back\s+to"
    r"|we'?ll\s+come\s+back"
    r"|short\s+(?:rest|break)"
    r"|long\s+(?:rest|break))",
    re.I,
)


# Patch 8: damage-resolution / active-combat indicators — when present in the
# IMMEDIATELY-preceding MATT turns, the trigger is treated as occurring
# inside ongoing combat (i.e., a wave/phase event), not a fresh start.
#
# Conservative pattern: requires explicit damage/hit/miss/turn-end vocab.
# Bare numbers and ambient combat references (perception checks, etc.) do
# NOT match — they over-fired on records like C2E045_t2014 (trap teeth bite
# pre-init) and C1E031_t686 (volley pre-init), where pre-init damage is
# part of the encounter STARTUP rather than ongoing combat.
DAMAGE_RESOLUTION = re.compile(
    r"\b\d{1,3}\s+points?\s+of\s+\w+\s+damage\b"
    r"|\bpoints?\s+of\s+(?:slashing|piercing|bludgeoning|fire|cold|acid|"
    r"psychic|necrotic|radiant|thunder|lightning|force|poison)\s+damage\b"
    r"|\byou\s+(?:take|both\s+take)\s+\w+\s+(?:points?\s+of\s+)?\w*\s*damage\b"
    r"|\b(?:end|top|start)\s+of\s+(?:your|his|her|the|this)\s+(?:turn|round)"
    r"|\bcrit(?:ical)?\s+hit\b"
    r"|\battack\s+of\s+opportunity\b"
    r"|\bversus\s+(?:armor\s+class|AC)\b"
    r"|\bAC\s+(?:of\s+)?\d+\b"
    r"|\b\d{1,3}\s+(?:does\s+)?(?:not\s+)?hits?\b"
    r"|\bthat\s+(?:hits?|misses)\b"
    r"|\bjust\s+(?:hits?|misses)\b"
    r"|\bdoes\s+(?:hit|miss|not\s+hit)\b"
    r"|\bnatural\s+\d+\b"
    r"|\bboth\s+(?:hit|miss|hits|misses)\b"
    r"|\bdamage\s+(?:roll|dice)\b",
    re.I,
)


def has_recent_damage_resolution(preceding_turns, trigger_text, k=3):
    """Patch 8: True if damage-resolution vocab appears in the trigger text or
    in the last `k` MATT turns of the preceding window.

    Why MATT-only and bounded to last `k`: a damage check that triggers on
    *any* preceding turn over a 1500-char window over-fires on encounters
    where the trigger turn IS the first attack of a fresh fight (trap-bite,
    volley-then-init). Limiting to the last few MATT turns means "actively
    being narrated as combat right now" not "combat happened somewhere in
    recent memory."
    """
    if DAMAGE_RESOLUTION.search(trigger_text):
        return True
    matt_seen = 0
    for p in reversed(preceding_turns):
        if p["speaker"] != "MATT":
            continue
        matt_seen += 1
        if DAMAGE_RESOLUTION.search(p["text"]):
            return True
        if matt_seen >= k:
            break
    return False


def has_scene_transition(preceding_turns, trigger_text, char_window=1500):
    """Return True if a scene-transition marker appears in the trigger or
    the preceding window. Indicates a fresh start regardless of prior init.
    """
    if SCENE_TRANSITION_MARKERS.search(trigger_text):
        return True
    used = 0
    for p in reversed(preceding_turns):
        if used >= char_window:
            break
        if SCENE_TRANSITION_MARKERS.search(p["text"]):
            return True
        used += len(p["text"])
    return False


def classify_wave(trigger_text, init_active, combat_active, scene_transition):
    """Return wave_subtype or None.

    Patch 8 (final):
      - Literal wave phrases (PARTY_JOIN/REINFORCEMENT/PHASE_SHIFT) fire
        regardless of state — they're explicit textual signals.
      - New-combatant shape (WAVE_NEW_COMBATANT_SHAPE/SUMMON) requires
        `init_active=True` per v1.1 caution: a first-of-episode init that
        happens to mention "Both of you" or similar shouldn't be tagged as
        wave from text alone.
      - Phase_shift fallback fires only when `combat_active=True`
        (= init_active AND recent damage-resolution narration). This is the
        strongest signal that combat is mid-stream and a new init call is a
        wave/phase event rather than a fresh start.
      - `scene_transition=True` short-circuits to None — even if init_active
        is set, an explicit scene-transition marker means a new fight is
        starting fresh.

    Sub-classification (priority order):
      1. reinforcement — summon-language or explicit reinforcement vocab
      2. party_join — party-member shape or matching literal patterns
      3. phase_shift — reroll/phase/time-flux phrases OR combat_active fallback
      4. None — not a wave
    """
    if scene_transition:
        return None

    has_literal_wave = (
        WAVE_PARTY_JOIN.search(trigger_text) is not None
        or WAVE_REINFORCEMENT.search(trigger_text) is not None
        or WAVE_PHASE_SHIFT.search(trigger_text) is not None
    )
    has_new_combatant_shape = (
        WAVE_NEW_COMBATANT_SHAPE.search(trigger_text) is not None
        or WAVE_SUMMON_LANGUAGE.search(trigger_text) is not None
    )

    if not has_literal_wave and not has_new_combatant_shape and not combat_active:
        return None
    if has_new_combatant_shape and not has_literal_wave and not init_active:
        return None

    # Sub-type assignment.
    if WAVE_SUMMON_LANGUAGE.search(trigger_text):
        return "reinforcement"
    if WAVE_REINFORCEMENT.search(trigger_text):
        return "reinforcement"
    if WAVE_PARTY_JOIN.search(trigger_text):
        return "party_join"
    if WAVE_NEW_COMBATANT_SHAPE.search(trigger_text):
        if re.search(r"\b(?:both\s+of\s+you|the\s+(?:two|three|four|few|rest)\s+of\s+you|you\s+who\s+just)", trigger_text, re.I):
            return "party_join"
        return "phase_shift"
    if WAVE_PHASE_SHIFT.search(trigger_text):
        return "phase_shift"
    if combat_active:
        return "phase_shift"
    return None


# ---------------------------------------------------------------------------
# Trap activation (priority 2)
# ---------------------------------------------------------------------------

PLAYER_TRAP_INTERACTION = re.compile(
    r"\bI\s+(?:open|reach|touch|stick|press|push|pull|grab|grasp|step|put|insert|"
    r"place|lift|unlock|pry|examine|investigate|inspect|search|probe|tug|prod|"
    r"shake|nudge|peer)\b"
    r"|\bwe(?:'re|'d| are| will)?\s+(?:going\s+to\s+)?(?:open|reach|touch|stick|"
    r"press|push|pull|grab|step|put|insert|place|examine|investigate|search|"
    r"probe|peer)\b"
    r"|(?:open(?:ing)?|stick(?:ing)?|reach(?:ing)?|touch(?:ing)?|press(?:ing)?)\s+"
    r"(?:the|our|my|its)\s+(?:hand|hands|chest|cabinet|door|lid|drawer|book|"
    r"body|corpse|lock|button|lever|handle|rope|chain|altar|coffin|sarcophagus|tome|page)",
    re.I,
)

TRIGGER_MECHANISM_VOCAB = re.compile(
    r"\b(?:teeth\s+emerge|teeth\s+suddenly\s+emerge|teeth\s+(?:emerge|burst|spring)"
    r"|pressure\s+plate|spring(?:s)?\s+(?:up|forth|out|loose|shut|closed)"
    r"|releases?\b|slams?\s+shut|trap(?:s|ped)?\b"
    r"|snaps?\s+shut|trigger(?:ed|s)?\b"
    r"|emerges?\s+from\s+the\s+(?:sides?|edges?|walls?|floor|ceiling)"
    r"|closes?\s+on\s+(?:your|his|her|their|each)"
    r"|locks?\s+(?:onto|around|shut)"
    r"|(?:a|the)\s+(?:dart|arrow|bolt|spike|blade|gas|cloud)\s+(?:fire|spring|emerge|release|shoot)"
    r"|the\s+floor\s+(?:gives|opens|drops))",
    re.I,
)


# ---------------------------------------------------------------------------
# Player action escalation (priority 3)
# ---------------------------------------------------------------------------

PLAYER_ACTION_VERBS = re.compile(
    r"\b(?:I|I'm|I'll|I\s+will|I\s+want\s+to|I\s+try\s+to|I\s+attempt\s+to|"
    r"I'm\s+going\s+to|I'm\s+gonna|"
    r"we|we're|we'll|we\s+will|we\s+want\s+to|we're\s+going\s+to|we're\s+gonna)\b"
    r"\s+(?:[a-z']+\s+){0,4}"
    r"(?:attack|cast|swing|stab|strike|fire|shoot|hit|throw|leap|jump|charge|"
    r"tackle|punch|kick|grab|sneak|stealth|tip[- ]?toe|approach|run|sing|"
    r"shout|yell|scream|insult|threaten|intimidate|deceive|lie|persuade|"
    r"sing|step\s+(?:in|forward|toward)|move\s+(?:in|toward|up)|engage|"
    r"start\s+singing|rush|bolt|sprint|slash|smash|bash|stomp|trample|"
    r"draw\s+(?:my|our|the)\s+(?:sword|weapon|bow|dagger|knife|blade)|"
    r"pull\s+out\s+(?:my|our|the)\s+(?:sword|weapon|bow|dagger|knife)|"
    r"unsheath|nock|aim|loose|let\s+(?:loose|fly)|spell|invoke|summon)",
    re.I,
)

PLAYER_CHECK_DECLARATIONS = re.compile(
    r"\b(?:stealth|persuasion|deception|intimidation|insight|investigation|"
    r"perception|sleight\s+of\s+hand|acrobatics|athletics)\s+check\b"
    r"|\bI\s+(?:rolled?|got)\s+(?:a\s+|an\s+)?\d{1,2}\b",
    re.I,
)

# Patch 1: NPC-reaction-to-player vocabulary in MATT narration. Used to gate
# `player_action_escalation` instead of the v1 trigger-references-player phrase
# list (which was too narrow).
MATT_REACTION_VERBS = re.compile(
    r"\b(?:continues?\s+to\s+(?:run|flee|move)"
    r"|looks?\s+over"
    r"|look(?:s|ing|ed)?\s+(?:up|toward|at\s+you|around|over\s+(?:his|her|their)\s+shoulder)"
    r"|notices?\b|noticed\b|noticing\b"
    r"|respond(?:s|ing|ed)?\b"
    r"|react(?:s|ing|ed)?\b"
    r"|frustrated\b"
    r"|nothing\s+happens"
    r"|stupid\b"
    r"|sees?\s+you\b|saw\s+you\b"
    r"|spots?\s+(?:you|the|a)\b"
    r"|spins?\s+(?:around|toward)"
    r"|whirls?\s+(?:around|toward)"
    r"|turns?\s+(?:to|toward|on)\s+you"
    r"|shifts?\s+(?:his|her|their)\s+attention"
    r"|catches?\s+sight"
    r"|kicked\s+in"
    r"|aware\s+of\s+(?:you|your)"
    r"|alerted"
    r"|takes?\s+(?:notice|note))",
    re.I,
)

STRONG_KICKED_IN = re.compile(r"\bkicked\s+in\b", re.I)


# Patch 9: additional strong-positive trigger phrases for
# player_action_escalation. Conservative list — over-broad phrases like
# "let's go ahead and roll initiative" or "as you {verb}" caused the gate to
# fire on non-player-caused inits (banshee scene, environmental ambush).
# Kept only patterns that strongly signal player causality.
PLAYER_ACTION_STRONG_PHRASES = re.compile(
    r"\bkicked\s+in\b"
    r"|\bnow\s+we'?re\s+rolling\b"
    # "with that, [matt narrates consequence]" — tight causal
    r"|\bwith\s+that[,.]\s+"
    # "because of (your|these|this) [action]"
    r"|\bbecause\s+of\s+(?:your|these|this)\b",
    re.I,
)


# Patch 9: physical-consequence narration that marks the moment a player
# action's effect lands. When a player action verb fires in the last 10
# turns AND a MATT turn after it contains a tight consequence vocab match,
# classify as player_action_escalation.
#
# Patterns require a clear destructive/impact context — bare "cracks" /
# "shatters" / "strikes" over-fired on ambient narration (creature mouths
# cracking open, etc.). Each alternative requires either a directional
# preposition or an explicit (impact_noise)-style cue.
MATT_PHYSICAL_CONSEQUENCE = re.compile(
    r"\b(?:slamming|slams?)\s+(?:into|against|down|on)"
    r"|smash(?:es|ing|ed)?\s+(?:into|through|against|to)"
    r"|crash(?:es|ing|ed)?\s+(?:into|through|against)"
    r"|strikes?\s+(?:at|toward|into|down)"
    r"|the\s+door\s+(?:swings?|flies|crashes)\s+(?:open|wide|in)"
    r"|swings?\s+open\s+(?:and|with|wide)"
    r"|reels?\s+(?:back|backwards)"
    r"|stagger(?:s|ing|ed)?\s+back"
    r"|hurled\s+(?:back|backward|across|through)"
    r"|sends?\s+(?:them|him|her|it)\s+(?:flying|tumbling|sprawling)"
    r"|explodes?\s+(?:into|outward|in\s+a)"
    r"|bursts?\s+(?:open|forth|out\s+of|from)"
    r"|gives\s+way\b|caves?\s+in\b"
    r"|blasting\s+through|crashing\s+through"
    r"|\(impact[\s_]*noise\)|\(crash\)|\(boom\)|\(shoosh\)|\(thunk\)|\(slam\)",
    re.I,
)


def looks_like_player_action(text):
    """True if a non-MATT turn appears to declare an action."""
    if not text or len(text.strip()) < 6:
        return False
    if PLAYER_ACTION_VERBS.search(text):
        return True
    if PLAYER_CHECK_DECLARATIONS.search(text):
        return True
    return False


def looks_like_trap_interaction(text):
    """True if a non-MATT turn declares physical interaction with a mechanism (patch 3)."""
    if not text or len(text.strip()) < 6:
        return False
    return PLAYER_TRAP_INTERACTION.search(text) is not None


def turn_window(turns, trigger_idx, span):
    """Return turns[max(0, trigger_idx-span):trigger_idx] — the `span` turns
    immediately preceding the trigger (excluding trigger itself).
    """
    return turns[max(0, trigger_idx - span):trigger_idx]


# ---------------------------------------------------------------------------
# NPC dialogue / hostile pivot (priority 4)
# ---------------------------------------------------------------------------

QUOTED_SPEECH = re.compile(r'["“”][^"“”\n]{6,}["“”]')

# Patch 4: dropped bare "goes" from NPC_VOICING (over-fired on physical-motion
# narration like "he goes and he does like a hand motion"). "Goes" in true
# speech-act usage is followed by a quoted clause and gets caught by
# QUOTED_SPEECH directly.
NPC_VOICING = re.compile(
    r"\b(?:he|she|it|they)\s+(?:say|says|said|growls?|hisses?|whispers?|"
    r"shouts?|yells?|barks?|roars?|chuckles?|laughs?|sneers?|scoffs?|smiles?\s+and\s+says?)\b"
    r"|\b(?:says?|whispers?|growls?|hisses?|roars?|shouts?|yells?)\s*[:,]\s+[\"“]",
    re.I,
)

NPC_NAMED_SPEECH = re.compile(
    # Heuristic: a Capitalized NPC name followed by a speech-act verb.
    r"\b[A-Z][a-zA-Z'\-]{2,}\s+(?:says?|said|growls?|hisses?|whispers?|"
    r"shouts?|sneers?|scoffs?|smiles?\s+and\s+says?|chuckles?|laughs?)\b",
)

# Patch 6: physical-transformation narration as a hostility-commitment signal
# that doesn't require dialogue. The old man transforming, eyes turning red,
# flesh changing color/texture etc. — the NPC reveals hostility through
# physical change rather than speech.
TRANSFORMATION_VOCAB = re.compile(
    r"\b(?:flesh\s+now\b"
    r"|eyes\s+(?:blood[- ]red|glow(?:ing)?|burn(?:ing)?|red\s+and\s+bulging)"
    r"|body\s+(?:stops?\s+quaking|begins?\s+to\s+(?:change|shift|warp|contort)|changes?|shifts?|warps?|contorts?|twists?|melts?)"
    r"|lips\s+curled"
    r"|turns?\s+into\b"
    r"|morphs?\b"
    r"|shifts?\s+into\b"
    r"|becomes?\s+(?:something|a\s+(?:creature|monster|hostile|terrible)|grotesque|monstrous|distorted)"
    r"|reveals?\s+(?:itself|its\s+(?:true\s+form|nature))"
    r"|unfolds?\s+into\b"
    r"|skin\s+(?:tears?|splits?|peels?|cracks?)"
    r"|fangs?\s+(?:emerge|elongate|grow)"
    r"|claws?\s+(?:emerge|extend|grow)"
    r"|features?\s+(?:contort|distort|warp|twist))",
    re.I,
)


def has_npc_dialogue(matt_text):
    """True if a MATT turn contains NPC dialogue (quoted or voiced)."""
    if QUOTED_SPEECH.search(matt_text):
        return True
    if NPC_VOICING.search(matt_text):
        return True
    if NPC_NAMED_SPEECH.search(matt_text):
        return True
    return False


def has_transformation_reveal(text):
    """True if text contains transformation/reveal vocab (patch 6)."""
    return TRANSFORMATION_VOCAB.search(text) is not None


# Patch 10 — NPC turns hostile widening.

# Ambush staging vocabulary: NPCs in waiting position with weapons drawn,
# expecting the party. Combined with attack narration in trigger or recent
# context, classifies as npc_turns_hostile.
AMBUSH_VOCAB = re.compile(
    r"\bcrossbows?\s+(?:pulled|nocked|ready|drawn|loaded)"
    r"|\bweapons?\s+(?:drawn|at\s+the\s+ready|raised|at\s+attention)"
    r"|\bwaiting\s+pattern"
    r"|\barranged\s+(?:in\s+(?:formation|ranks|a\s+(?:waiting|defensive)\s+pattern)|to\s+strike)"
    r"|\barmed\s+and\s+waiting"
    r"|\bprepared\s+(?:to\s+strike|for\s+(?:battle|combat|your\s+arrival))"
    r"|\bexpecting\s+your\s+arrival"
    r"|\b(?:bows|arrows|spears|swords)\s+(?:nocked|ready|drawn|raised)"
    r"|\balready\s+(?:arrayed|arranged|positioned)\b"
    r"|\bambush(?:ed|ing)?\b",
    re.I,
)

# NPC command words ("Loose!", "Attack!", "Now!") followed by attack narration
# within a few turns.
NPC_COMMAND = re.compile(
    r"""['"“”]\s*(?:Loose|Attack|Kill\s+(?:them|him|her|it)|"""
    r"""Now|Charge|Open\s+fire|Fire|Get\s+them|Take\s+(?:them|him|her))\s*[!.]*\s*['"“”]""",
    re.I,
)

ATTACK_NARRATION = re.compile(
    r"\b(?:loose|volley|barrage|arrows?\s+(?:fly|flies|loose|land)|bolts?\s+\w+"
    r"|strikes?\s+(?:at|toward|down)|attacks?\s+(?:you|him|her|it)"
    r"|\(fshh?\)|\(thwip\)|\(swish\)|\(shoosh\)"
    r"|shoots?\s+at|fires?\s+at|(?:dives|lunges|charges)\s+at\s+you"
    r"|let\s+loose|loose\s+(?:a\s+|the\s+)?(?:volley|barrage|arrow))",
    re.I,
)

# NPC physical reveal — describes the moment an NPC presence becomes
# threateningly evident. Tight patterns only — bare "snarling" / "blocking
# the passage" / "teeth bared" over-fired on environmental-creature
# narration (giant blue-scaled reptile coming down a cliff). Reserved for
# clear humanoid-NPC reveal shapes.
NPC_HOSTILE_REVEAL = re.compile(
    r"\byou\s+(?:see|recognize|spot)\s+(?:\w+\s+){0,8}"
    r"(?:step(?:s|ping)?\s+(?:out|from|forward)|stepping\s+(?:from|out|forward))"
    r"|\bfigures?\s+step(?:s|ping)?\s+(?:out|from|into\s+view)"
    r"|\beyes?\s+(?:fall|falls|fell|land(?:s)?)\s+(?:on|upon)\s+(?:you|the\s+(?:party|group))"
    r"|\bdrift(?:s|ing|ed)?\s+(?:in|toward)\s+(?:from|the|toward)"
    r"|\b(?:hooded|robed|armored|cloaked|skeletal)\s+(?:figures?|forms?|frame)"
    r"|\bhe\s+dives\s+at\s+you"
    r"|\bcrackling\s+energy\s+(?:bursting|surrounding)"
    r"|\bflesh\s+(?:is\s+)?pulled\s+tight",
    re.I,
)


def has_ambush_setup(preceding_turns, trigger_text):
    """Patch 10: ambush vocab in preceding MATT context AND attack narration
    in trigger or recent MATT."""
    has_ambush = False
    has_attack = ATTACK_NARRATION.search(trigger_text) is not None
    for p in reversed(preceding_turns):
        if p["speaker"] != "MATT":
            continue
        if AMBUSH_VOCAB.search(p["text"]):
            has_ambush = True
        if ATTACK_NARRATION.search(p["text"]):
            has_attack = True
        if has_ambush and has_attack:
            return True
    return has_ambush and has_attack


def has_npc_command_then_attack(preceding_turns, trigger_text):
    """Patch 10: NPC command (single-word imperative in quotes) within ~3 MATT
    turns followed by attack narration in trigger or subsequent MATT context.
    """
    has_command = NPC_COMMAND.search(trigger_text) is not None
    has_attack = ATTACK_NARRATION.search(trigger_text) is not None
    matt_seen = 0
    for p in reversed(preceding_turns):
        if p["speaker"] != "MATT":
            continue
        matt_seen += 1
        if NPC_COMMAND.search(p["text"]):
            has_command = True
        if ATTACK_NARRATION.search(p["text"]):
            has_attack = True
        if matt_seen >= 4:
            break
    return has_command and has_attack


def has_npc_hostile_reveal(preceding_turns, trigger_text):
    """Patch 10: NPC physical-reveal narration in trigger or recent MATT
    turns. Catches scenes like 'figures step out from behind the spire',
    'banshee drifts in', 'crackling energy bursting around his form'.
    """
    if NPC_HOSTILE_REVEAL.search(trigger_text):
        return True
    matt_seen = 0
    for p in reversed(preceding_turns):
        if p["speaker"] != "MATT":
            continue
        matt_seen += 1
        if NPC_HOSTILE_REVEAL.search(p["text"]):
            return True
        if matt_seen >= 3:
            break
    return False


# ---------------------------------------------------------------------------
# Environmental scene change (priority 5)
# ---------------------------------------------------------------------------

SCENE_CHANGE_VOCAB = re.compile(
    r"\b(?:form(?:s|ing|ed)?\s+(?:into|a\s+|themselves)"
    r"|emerge[sd]?\b"
    r"|materialize[sd]?\b"
    r"|coalesc(?:e|es|ing|ed)\b"
    r"|rise[sd]?\s+(?:from|up\s+from)"
    r"|take[sd]?\s+shape\b"
    r"|crystalliz(?:e|es|ing|ed)\b"
    r"|begins?\s+to\s+(?:form|emerge|materialize|rise|coalesce|take\s+shape|protrude|grow)"
    r"|protrud(?:e|es|ing|ed)\b"
    r"|grows?\s+from\b"
    r"|reaches?\s+out\s+for\s+you"
    r"|lunges?\s+(?:toward|at|out\s+toward)"
    r"|swoop(?:s|ing|ed)?\s+(?:in|down)"
    r"|burst(?:s|ing)?\s+(?:from|forth|out\s+of)"
    r"|crash(?:es|ing)?\s+through"
    r"|slither(?:s|ing)?\s+(?:into|out|forth)"
    r"|appear(?:s|ed)?\s+(?:before|in\s+front\s+of|behind|above|to\s+the)\b"
    r"|step(?:s|ped|ping)?\s+out\s+of\s+the\s+shadow"
    r"|(?:descends?|drops?|falls?)\s+from\s+(?:above|the\s+ceiling))",
    re.I,
)


# ---------------------------------------------------------------------------
# Context window
# ---------------------------------------------------------------------------

def gather_preceding_context(turns, trigger_idx, char_budget):
    """
    Walk back from trigger_idx-1 accumulating turns until char_budget exceeded.
    All speakers retained — no filtering at extraction.
    Returns:
      preceding_turns: list of {speaker, text, turn_number} oldest-first
      total_chars: sum of len(text) across preceding_turns
      narration_buildup_chars: sum of MATT len(text) only
      most_recent_non_matt_text: text of the closest non-MATT turn (or None)
    """
    pre_reversed = []
    used = 0
    for j in range(trigger_idx - 1, -1, -1):
        t = turns[j]
        text_len = len(t["text"])
        if used + text_len > char_budget:
            break
        pre_reversed.append({
            "speaker": t["speaker"],
            "text": t["text"],
            "turn_number": t["number"],
        })
        used += text_len

    preceding_turns = list(reversed(pre_reversed))
    total_chars = used
    narration_buildup_chars = sum(
        len(p["text"]) for p in preceding_turns if p["speaker"] == "MATT"
    )
    most_recent_non_matt_text = None
    for p in pre_reversed:  # walk from closest backward
        if p["speaker"] != "MATT":
            most_recent_non_matt_text = p["text"]
            break

    return (
        preceding_turns,
        total_chars,
        narration_buildup_chars,
        most_recent_non_matt_text,
    )


# ---------------------------------------------------------------------------
# Classification (locked priority order)
# ---------------------------------------------------------------------------

def classify_trigger(trigger_idx, trigger_text, turns, preceding_turns,
                     narration_buildup_chars, most_recent_non_matt_text,
                     init_active, force_combat_active=False):
    """
    Apply locked priority rules (v1_1 patches applied). Return:
        (trigger_category, is_fresh, wave_subtype, player_action_caused)

    Priority order:
      1. wave/phase (patch 2 — semantic when init_active, literal always)
      2. trap_activation (patch 3 — full preceding_turns window for both
         interaction signal and mechanism signal)
      3. player_action_escalation (patch 1 — strong-positive on "kicked in";
         else action-in-last-15 + reaction-verb gate)
      4. patch 5 immediate-predecessor override (NPC dialogue in immediate-prev
         MATT, or action in immediate-prev non-MATT)
      5. npc_turns_hostile (patch 6 — dialogue in closest-3 MATT, or
         transformation vocab anywhere in recent context)
      6. environmental_materialization (>=500 char buildup + scene-change vocab)
      7. interruption (default)

    Patch 5 fires AFTER patch 1 / patch 3 because the strong/clear positive
    signals in patches 1 and 3 ought to win over a generic immediate-predecessor
    rule. Patch 5 captures cases where patches 1/2/3/6 didn't fire but the
    immediate predecessor establishes either category cleanly.
    """
    # Default player_action_caused — used unless overridden by classification.
    pac_default = looks_like_player_action(most_recent_non_matt_text or "")

    # Recent MATT text concatenated (within preceding_turns budget) for vocab checks.
    recent_matt_text = " ".join(
        p["text"] for p in preceding_turns if p["speaker"] == "MATT"
    )

    # ---- Priority 1: wave/phase (patch 8 — multi-signal) ----
    # combat_active = init_active state AND damage-resolution narration in the
    # immediately-preceding MATT turns. Both signals required for the
    # phase_shift fallback to fire — init_active alone over-fires on
    # back-to-back-but-distinct encounters (e.g., C1E020_t993), and damage
    # alone over-fires on encounter-startup pre-init damage (e.g., C2E045_t2014
    # cabinet trap, C1E031_t686 crossbow volley, C2E042_t251 boxing-to-combat).
    recent_damage = has_recent_damage_resolution(preceding_turns, trigger_text)
    scene_transition = has_scene_transition(preceding_turns, trigger_text)
    # v1.3 Stage 0 STATE detection forces combat_active=True so the wave
    # classification gate fires reliably even when init_active or
    # damage-resolution heuristics would have missed it.
    combat_active = (init_active and recent_damage) or force_combat_active
    wave = classify_wave(trigger_text, init_active or force_combat_active,
                         combat_active, scene_transition)
    if wave is not None:
        return "wave_or_phase_shift", False, wave, pac_default

    # ---- Priority 2: trap_activation (patch 3) ----
    # Search the full preceding_turns window — `preceding_turns` typically spans
    # 15-25 turns at the 1500-char budget, exceeding the patch's 15-turn floor.
    interaction_in_window = any(
        p["speaker"] != "MATT" and looks_like_trap_interaction(p["text"])
        for p in preceding_turns
    )
    mechanism_in_window = (
        TRIGGER_MECHANISM_VOCAB.search(trigger_text) is not None
        or any(
            p["speaker"] == "MATT" and TRIGGER_MECHANISM_VOCAB.search(p["text"])
            for p in preceding_turns
        )
    )
    if interaction_in_window and mechanism_in_window:
        return "trap_activation", True, None, True

    # ---- Priority 3: player_action_escalation (patch 1) ----
    # Search a 15-turn pure-index window for player-action signals.
    causality_window = turn_window(turns, trigger_idx, CAUSALITY_WINDOW_TURNS)
    player_action_in_window = any(
        t["speaker"] != "MATT" and looks_like_player_action(t["text"])
        for t in causality_window
    )

    # Strong-positive: trigger contains "kicked in" or any patch-9 phrase
    # AND a player action is in the last CAUSALITY_WINDOW_TURNS turns.
    if player_action_in_window and (
        STRONG_KICKED_IN.search(trigger_text)
        or PLAYER_ACTION_STRONG_PHRASES.search(trigger_text)
    ):
        return "player_action_escalation", True, None, True

    # Closest preceding MATT turn (within causality window).
    closest_matt_text = ""
    for t in reversed(causality_window):
        if t["speaker"] == "MATT":
            closest_matt_text = t["text"]
            break

    has_reaction = (
        MATT_REACTION_VERBS.search(trigger_text) is not None
        or (closest_matt_text and MATT_REACTION_VERBS.search(closest_matt_text) is not None)
    )
    if player_action_in_window and has_reaction:
        return "player_action_escalation", True, None, True

    # Patch 9: player-action-then-MATT-physical-consequence pattern. Look at
    # the last 10 turns: if a player action fires in a non-MATT turn AND the
    # nearest subsequent MATT turn has physical-consequence narration, it's
    # a player_action_escalation. Catches cases like Liam kicking the door
    # (player) then "the door swings open / impact noise" (MATT) then init.
    # Window=10 because the gap between player declaration and MATT
    # narration may include OOC banter from other players.
    short_window = turn_window(turns, trigger_idx, 10)
    has_short_action = False
    has_short_consequence = False
    last_action_idx = -1
    for i, t in enumerate(short_window):
        if t["speaker"] != "MATT" and looks_like_player_action(t["text"]):
            has_short_action = True
            last_action_idx = i
        elif t["speaker"] == "MATT" and i > last_action_idx and last_action_idx >= 0:
            if MATT_PHYSICAL_CONSEQUENCE.search(t["text"]):
                has_short_consequence = True
                break
    if has_short_action and has_short_consequence:
        return "player_action_escalation", True, None, True

    # ---- Priority 4: patch 5 immediate-predecessor override ----
    immediate_prev = turns[trigger_idx - 1] if trigger_idx > 0 else None
    if immediate_prev is not None:
        if immediate_prev["speaker"] == "MATT" and has_npc_dialogue(immediate_prev["text"]):
            return "npc_turns_hostile", True, None, False
        if immediate_prev["speaker"] != "MATT" and looks_like_player_action(immediate_prev["text"]):
            return "player_action_escalation", True, None, True

    # ---- Priority 5: npc_turns_hostile widened (patch 6) ----
    # Closest 3 MATT turns concatenated, plus the trigger itself for
    # transformation vocab.
    closest_matt_turns = []
    for p in reversed(preceding_turns):
        if p["speaker"] == "MATT":
            closest_matt_turns.append(p["text"])
            if len(closest_matt_turns) >= 3:
                break
    closest_matt_concat = " ".join(closest_matt_turns)

    if closest_matt_concat and has_npc_dialogue(closest_matt_concat):
        return "npc_turns_hostile", True, None, pac_default

    # Patch 6: transformation/reveal narration in trigger or recent MATT.
    if has_transformation_reveal(trigger_text) or (
        closest_matt_concat and has_transformation_reveal(closest_matt_concat)
    ):
        return "npc_turns_hostile", True, None, pac_default

    # Patch 10: also check trigger text itself for NPC dialogue (v1.1 only
    # checked preceding window).
    if has_npc_dialogue(trigger_text):
        return "npc_turns_hostile", True, None, pac_default

    # Patch 10: ambush staging + attack narration in preceding/trigger.
    if has_ambush_setup(preceding_turns, trigger_text):
        return "npc_turns_hostile", True, None, pac_default

    # Patch 10: NPC command + attack narration.
    if has_npc_command_then_attack(preceding_turns, trigger_text):
        return "npc_turns_hostile", True, None, pac_default

    # Patch 10: NPC physical-reveal narration.
    if has_npc_hostile_reveal(preceding_turns, trigger_text):
        return "npc_turns_hostile", True, None, pac_default

    # ---- Priority 6: environmental_materialization ----
    if narration_buildup_chars >= NARRATION_BUILDUP_THRESHOLD_CHARS:
        if SCENE_CHANGE_VOCAB.search(trigger_text) or SCENE_CHANGE_VOCAB.search(recent_matt_text):
            return "environmental_materialization", True, None, pac_default

    # ---- Priority 7: default ----
    return "interruption", True, None, pac_default


# ---------------------------------------------------------------------------
# Episode loading
# ---------------------------------------------------------------------------

def parse_episode_id(episode_id):
    """C1E030 -> ('C1', 30). Returns None on parse failure."""
    m = EPISODE_ID_RE.match(episode_id)
    if not m:
        return None
    return m.group(1), int(m.group(2))


def list_all_episodes():
    """Return sorted list of unique episode IDs in the c=2 dir."""
    seen = set()
    for fn in os.listdir(SOURCE_BASE):
        if not fn.endswith(".json"):
            continue
        ep = fn.split("_")[0]
        seen.add(ep)
    return sorted(seen)


def load_episode_turns(episode_id):
    """
    Load all turns for an episode from the c=2 dir, deduplicated by NUMBER.
    Returns sorted list of {speaker, text, number} dicts.
    Fail-open on parse errors — log and return what we got.
    """
    files = sorted(
        f for f in os.listdir(SOURCE_BASE)
        if f.startswith(episode_id + "_") and f.endswith(".json")
    )
    if not files:
        log_unknown(f"no files for episode {episode_id}")
        return []

    turns_by_num = {}
    for fn in files:
        path = SOURCE_BASE / fn
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            log_unknown(f"failed to read {fn}: {e}")
            continue

        if not isinstance(data, list):
            log_unknown(f"{fn}: top-level is not a list")
            continue

        for rec in data:
            try:
                rec_turns = rec.get("TURNS", [])
            except AttributeError:
                log_unknown(f"{fn}: record is not a dict")
                continue

            for turn in rec_turns:
                try:
                    n = turn["NUMBER"]
                    names = turn.get("NAMES", [])
                    utterances = turn.get("UTTERANCES", [])
                except (KeyError, TypeError) as e:
                    log_unknown(f"{fn}: malformed turn ({e})")
                    continue

                if n in turns_by_num:
                    continue
                speaker = names[0].upper() if names else "UNKNOWN"
                if isinstance(utterances, list):
                    text = " ".join(str(u) for u in utterances)
                else:
                    text = str(utterances)
                turns_by_num[n] = {
                    "speaker": speaker,
                    "text": text,
                    "number": n,
                }

    return [turns_by_num[n] for n in sorted(turns_by_num)]


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

_unknown_log = []
_filtered_non_init_log = []
_filtered_discourse_log = []


def log_unknown(msg):
    """Capture [EXTRACTOR_UNKNOWN] events to stderr and to the run summary."""
    line = f"[EXTRACTOR_UNKNOWN] {msg}"
    _unknown_log.append(line)
    print(line, file=sys.stderr)


def log_filtered_non_init(text):
    """Patch 7: log Stage-1 rejections that match a non-init dice-roll pattern."""
    snippet = (text or "")[:200].replace("\n", " ")
    line = f"[FILTERED_NON_INIT] {snippet}"
    _filtered_non_init_log.append(line)


def log_filtered_discourse(text, reason):
    """v1.3 Stage 0: log candidates rejected as DISCOURSE."""
    snippet = (text or "")[:200].replace("\n", " ")
    line = f"[FILTERED_DISCOURSE] {reason} :: {snippet}"
    _filtered_discourse_log.append(line)


# ---------------------------------------------------------------------------
# Episode processing
# ---------------------------------------------------------------------------

def process_episode(episode_id, extracted_at):
    """Process one episode. Return list of records (possibly empty).

    Tracks per-episode `init_active` state for patch 2 semantic-wave detection.
    Once a fresh-start init has been seen this episode, init_active stays True
    for the rest of the episode (no end-of-combat detection in v1.1; over-marking
    as wave is a smaller error than under-marking, per the patch).
    """
    parsed = parse_episode_id(episode_id)
    if parsed is None:
        log_unknown(f"unparseable episode id {episode_id}")
        return []
    campaign, episode_num = parsed

    turns = load_episode_turns(episode_id)
    if not turns:
        return []

    total_turns = len(turns)
    records = []
    init_active = False
    last_emitted_turn_number = None
    for idx, t in enumerate(turns):
        if t["speaker"] != "MATT":
            continue
        if not is_init_candidate(t["text"]):
            continue

        (preceding_turns, preceding_chars,
         narration_buildup_chars, recent_non_matt) = gather_preceding_context(
            turns, idx, PRECEDING_CONTEXT_BUDGET
        )

        # Stage 0 (v1.3): EVENT / STATE / DISCOURSE.
        stage_0, stage_0_reason = stage_0_classify(t["text"], preceding_turns)
        if stage_0 == "DISCOURSE":
            log_filtered_discourse(t["text"], stage_0_reason)
            continue
        force_combat_active = (stage_0 == "STATE")

        category, is_fresh, wave_subtype, player_action_caused = classify_trigger(
            idx, t["text"], turns, preceding_turns,
            narration_buildup_chars, recent_non_matt, init_active,
            force_combat_active=force_combat_active,
        )

        # Update init_active state. A fresh start sets it; a wave does not
        # change it (already True by definition). Important: this is set AFTER
        # classification, so the first init in an episode is always evaluated
        # with init_active=False (and therefore can't be a wave by patch 2).
        if is_fresh:
            init_active = True

        # Position: index of this turn divided by episode-turn count (locked
        # decision §6.5 — no OOC strip in v1).
        episode_position_pct = round(idx / total_turns, 4) if total_turns else 0.0

        # Patch 11: distance (in turn numbers) to the previous emitted record
        # in this episode. None if this is the first record. Lets the
        # analysis layer dedup adjacent records (cf. C1E031_t144 / t152
        # where two init calls fire 8 turns apart and the second is a
        # restated request, not a separate encounter).
        nearest_prior_distance = (
            t["number"] - last_emitted_turn_number
            if last_emitted_turn_number is not None
            else None
        )

        record = {
            "campaign": campaign,
            "episode": episode_num,
            "episode_position_pct": episode_position_pct,
            "speaker": "MATT",
            "event_type": "init_event",
            "raw_text": t["text"],
            "preceding_context_chars": preceding_chars,
            "extractor_version": EXTRACTOR_VERSION,
            "extracted_at": extracted_at,

            "trigger_turn_number": t["number"],
            "trigger_category": category,
            "is_fresh_encounter": is_fresh,
            "wave_subtype": wave_subtype,
            "player_action_caused": player_action_caused,
            "narration_buildup_chars": narration_buildup_chars,
            "nearest_prior_trigger_turn_distance": nearest_prior_distance,
            "preceding_turns": preceding_turns,
        }
        records.append(record)
        last_emitted_turn_number = t["number"]

    return records


# ---------------------------------------------------------------------------
# CLI modes
# ---------------------------------------------------------------------------

def utc_now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def run_sample():
    extracted_at = utc_now_iso()
    all_records = []
    per_episode_counts = {}
    for ep in SAMPLE_EPISODES:
        records = process_episode(ep, extracted_at)
        per_episode_counts[ep] = len(records)
        all_records.extend(records)
        print(f"  {ep}: {len(records)} record(s)")

    SAMPLE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SAMPLE_PATH, "w", encoding="utf-8") as f:
        json.dump(all_records, f, indent=2, ensure_ascii=False)

    total = sum(per_episode_counts.values())
    print(f"\nSAMPLE_COMPLETE: episodes={len(SAMPLE_EPISODES)} records={total}")
    print(f"output: {SAMPLE_PATH}")
    if _unknown_log:
        print(f"[EXTRACTOR_UNKNOWN] count: {len(_unknown_log)}")


def run_full():
    extracted_at = utc_now_iso()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    episodes = list_all_episodes()
    print(f"Full parse: {len(episodes)} episodes")
    total = 0
    for i, ep in enumerate(episodes, 1):
        records = process_episode(ep, extracted_at)
        out_path = OUTPUT_DIR / f"{ep}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, ensure_ascii=False)
        total += len(records)
        if i % 10 == 0 or i == len(episodes):
            print(f"  [{i}/{len(episodes)}] processed, running record total: {total}")
    print(f"\nEXTRACTOR_COMPLETE: episodes_processed={len(episodes)} records={total}")
    if _unknown_log:
        print(f"[EXTRACTOR_UNKNOWN] count: {len(_unknown_log)}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--sample", action="store_true",
                       help="Run on the 10 hand-sample episodes only.")
    group.add_argument("--full", action="store_true",
                       help="Run on all CRD3 episodes (per-episode output files).")
    args = parser.parse_args()

    if not SOURCE_BASE.is_dir():
        print(f"FATAL: source dir not found: {SOURCE_BASE}", file=sys.stderr)
        sys.exit(2)

    if args.sample:
        run_sample()
    elif args.full:
        run_full()


if __name__ == "__main__":
    main()
