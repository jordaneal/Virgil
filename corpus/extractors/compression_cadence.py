#!/usr/bin/env python3
"""
Compression Cadence Extractor v1.

Reads CRD3 (`c=2` alignment dir) and emits one JSON record per detected
compression-decision event. A compression event is one of six categories:
SCENE_CUT, OVERNIGHT_REST, TEMPORAL_MONTAGE, NPC_DEPARTURE,
INVESTIGATIVE_CLOSURE, LOCATION_DEPARTURE.

Also emits STALE_HOLD_CANDIDATE records (Q6 partial single-extractor
coverage): stale-signal clusters (>=3 in a 30-turn window) not followed
by a compression event within 20 turns.

Per CORPUS_BUILDER.md: deterministic regex only, read-only on the corpus,
fail-open on unknown formats, idempotent on event content.

Spec: findings/track5_compression_cadence_phase1_spec.md (S13 decisions locked).
Lessons: docs/corpus_builder_lessons_v2.md -- Lesson 9 (phrase-span Stage 0)
operative from line one.

Locked S13 decisions applied:
  S13.1 Taxonomy: all six categories (LOCATION_DEPARTURE tentative).
  S13.2 Stage 0: phrase-span per S6 recommendation.
  S13.3 Q6: in-scope single-extractor partial -- STALE_SIGNAL cluster >=3
        in 30-turn window, no compression follow-through within 20 turns.
  S13.4 TM overlap: emit with time_mention_overlap=True (don't suppress).
  S13.5 Hand-sample: 10 episodes (seed 2222).
  S13.6 Player-driven compressions: Matt-voice only; player intent
        captured as buildup_signal=player_intent on the Matt-turn record.
  S13.7 compression_scope: included as sketch field; best-effort only.

Phrase-span Stage 0 (Lesson 9): each candidate phrase is classified as
EVENT or DISCOURSE based on the phrase's position inside the turn.
Compression-decision triggers are almost exclusively in Matt's in-fiction
narrative voice. NPC dialogue preceding a trigger is NOT a turn-level
reject -- the trigger phrase must be located outside NPC quoted speech
(D2 rule).

Four D-rules:
  D1: OOC scheduling language (position-agnostic; break announcements)
  D2: Trigger phrase inside NPC quoted speech (not Matt narration)
  D3: In-scene micro-motion (LOCATION_DEPARTURE family only)
  D4: Recap-state episode opening (turn-level skip; position <=3%)

STATE flags (not rejects):
  is_recap_state: always False on emitted records (recap turns are skipped)
  is_combat_state: initiative staleness window (25 + 30 turns)

Usage:
    python3 compression_cadence.py --sample
        Runs on the 10 hand-sample episodes. Writes per-episode files at
        ../output/compression_cadence/{episode_id}.json.

    python3 compression_cadence.py --full
        Runs on all CRD3. NOT to be invoked at Phase 2 -- hand-sample only.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

EXTRACTOR_VERSION = "compression_cadence_v1"

CORPUS_BUILDER = Path(__file__).resolve().parent.parent
SOURCE_BASE = Path("/mnt/virgil_storage/dnd_datasets/crd3/data/aligned data/c=2")
OUTPUT_DIR = CORPUS_BUILDER / "output" / "compression_cadence"
TM_OUTPUT_DIR = CORPUS_BUILDER / "output" / "time_mention"

PRECEDING_CONTEXT_BUDGET = 800
BUILDUP_LOOKBACK_TURNS = 15
COMBAT_STATE_LOOKBACK_TURNS = 25
COMBAT_STATE_STALENESS_TURNS = 30
RECAP_EPISODE_POSITION_THRESHOLD = 0.03   # S6 D4: 3%
STALE_SIGNAL_WINDOW = 30                   # S13.3: Q6 cluster window
STALE_FOLLOW_THROUGH_WINDOW = 20           # S13.3: turns after last stale to check
STALE_CLUSTER_THRESHOLD = 3               # S13.3: min stale signals per cluster

# S13.5 locked hand-sample. seed=2222; stratified across C1 phases.
#
# Available pool after removing 107 prior-eval-set episodes and 7 recon
# episodes: 22 C1 + 4 C2 = 26 episodes. C1-only stratified selection:
# one per phase bucket (C1_early/mid/late) then top-up to 10 from remainder.
# C2 available (C2E008, C2E009, C2E023, C2E039) not selected -- C1 pool
# sufficient for stratified fill.
# All 10 confirmed disjoint from prior 107 eval-set episodes + 7 recon.
SAMPLE_EPISODES = [
    "C1E004", "C1E013", "C1E025", "C1E036", "C1E050",
    "C1E056", "C1E088", "C1E090", "C1E093", "C1E097",
]

EPISODE_ID_RE = re.compile(r"^(C\d+)E(\d{3,4})$")


# ---------------------------------------------------------------------------
# Stage 1 -- trigger families
# ---------------------------------------------------------------------------
#
# Six per-category trigger families. Priority order for same-span dedup:
# OVERNIGHT_REST > SCENE_CUT > NPC_DEPARTURE > INVESTIGATIVE_CLOSURE >
# LOCATION_DEPARTURE > TEMPORAL_MONTAGE. Higher-specificity wins.

# 1. SCENE_CUT -- Matt announces an explicit cut or uses direct editorial
# framing to end a scene's continuity.
SCENE_CUT_TRIGGER = re.compile(
    r"\bcut\s+to\s+black\b"
    r"|\bwe\s+cut\s+to\b"
    r"|\bcut\s+away\s+to\b"
    r"|\bsome\s+time\s+(?:later|has\s+passed)\b"
    r"|\btime\s+(?:has\s+(?:now\s+)?passed|passes\s+by)\b"
    r"|\bskip\s+(?:ahead|forward)\s+(?:to|in\s+time)\b"
    r"|\bfast[-\s]forward\s+(?:to|in\s+time)\b"
    r"|\bas\s+(?:this|that)\s+time\s+has\s+passed\b"
    r"|\bthat(?:'s|\s+is)\s+where\s+(?:we(?:'re|'ll)\s+)?(?:leave|end|cut)\b",
    re.I,
)

# 2. OVERNIGHT_REST -- Matt compresses overnight to the next morning.
# Highest-TM-overlap category; emitted with time_mention_overlap flag.
OVERNIGHT_REST_TRIGGER = re.compile(
    r"\byou\s+(?:all\s+)?awaken\b"
    r"|\bawaking\s+in\s+the\s+(?:early\s+)?morning\b"
    r"|\bawakening\s+in\s+the\b"
    r"|\bas\s+the\s+morning\s+(?:comes?|arrives?|breaks?|light)\b"
    r"|\bfind\s+yourselves?\s+to\s+rest\s+for\s+the\s+evening\b"
    r"|\bthe\s+following\s+morning\b"
    r"|\byou\s+(?:all\s+)?come\s+to\s+(?:consciousness|awareness|your\s+senses)\b"
    r"|\bcome\s+to\s+consciousness\b"
    r"|\bby\s+(?:the\s+time\s+)?(?:morning|dawn|sunrise)\b"
    r"|\bthe\s+morning\s+(?:sun|light|air|arrives?|comes?|breaks?)\b"
    r"|\byou\s+(?:all\s+)?(?:wake\s+up|wake\s+to|awaken\s+to)\b"
    r"|\bshooting\s+up\s+with\s+a\s+gasp\b"
    r"|\bin\s+the\s+(?:early\s+)?(?:pre[-\s])?dawn\s+hour\b"
    r"|\bchilled\s+morning\s+air\b",
    re.I,
)

# 3. TEMPORAL_MONTAGE -- Matt narrates compressed in-fiction time (hours to
# months) with a summary of activity during that period.
TEMPORAL_MONTAGE_TRIGGER = re.compile(
    r"\bover\s+the\s+(?:next|course\s+of\s+the|following)\s+"
    r"(?:\d+\s+)?(?:hour|day|week|month|year|minute)s?\b"
    r"|\bover\s+the\s+(?:course\s+of\s+the\s+)?(?:evening|day|night|week|month|year)\b"
    r"|\bas\s+the\s+(?:days?|weeks?|months?|years?)\s+(?:go\s+by|pass|pass\s+by)\b"
    r"|\bspend\s+the\s+next\s+(?:\d+\s+)?(?:hour|day|week|month|minute)s?\b"
    r"|\bthroughout\s+the\s+(?:day|night|week|month|morning|afternoon|evening)\b"
    r"|\bas\s+you\s+continue\s+your\s+trek\b"
    r"|\bfor\s+the\s+next\s+(?:\d+\s+)?(?:hour|day|week|month|minute)s?\b"
    r"|\bin\s+the\s+(?:days?|weeks?|months?|years?)\s+(?:that\s+)?(?:follow|pass)\b"
    r"|\bthe\s+next\s+(?:\d+\s+)?(?:hours?|days?|weeks?|months?)\s+(?:pass|are|see|bring)\b"
    r"|\bmonths?\s+(?:of\s+(?:preparation|training|travel)|go\s+by|pass)\b",
    re.I,
)

# 4. NPC_DEPARTURE -- an NPC ends their active presence in the scene.
# Trigger phrases are in Matt's narration; NPC farewell dialogue preceding
# the trigger is allowed (phrase-span D2 handles the distinction).
NPC_DEPARTURE_TRIGGER = re.compile(
    r"\b(?:exit|exits)\s+(?:the\s+)?(?:room|building|tavern|inn|hall|area|shop|chamber|tent)\b"
    r"|\btakes?\s+(?:his|her|their|its)\s+leave\b"
    r"|\bbids?\s+(?:you|them|us)\s+(?:farewell|adieu|goodbye|good\s+night)\b"
    r"|\b(?:head|heads)\s+back\s+to\s+(?:his|her|their|the|a|an)\s+"
    r"(?:work|seat|table|post|duties|shop|corner)\b"
    r"|\b(?:makes?|making)\s+(?:his|her|their|its)\s+way\s+out\s+of\s+the\b"
    r"|\bturns?\s+(?:around\s+)?and\s+(?:exit|exits|departs?|leaves?)\s+the\b"
    r"|\b(?:says?|bade?)\s+(?:his|her|their)\s+(?:goodbyes?|farewell)\b"
    r"|\bsteps?\s+out\s+of\s+(?:the\s+)?(?:room|building|tavern|inn|hall|space)\b"
    r"|\bgathers?\s+(?:his|her|their|its)\s+(?:things|belongings|stuff)\s+"
    r"and\s+(?:leave|leaves?|depart|exits?)\b"
    r"|\bslowly\s+(?:exits?|departs?|leaves?)\b"
    r"|\b(?:the\s+)?(?:other|rest|remaining)\s+(?:few\s+)?(?:exit|leave|depart)\s+the\b"
    r"|\btake\s+a\s+different\s+table\b"
    r"|\b(?:over|in)\s+the\s+next\s+(?:\d+\s+or\s+so\s+)?(?:minute|moment)s?\s*[,.]?\s+"
    r"(?:the\s+)?(?:other|rest|remaining|three|four|five)\s+(?:exit|leave|depart)\b",
    re.I,
)

# 5. INVESTIGATIVE_CLOSURE -- Matt closes a search or investigation beat by
# declaring nothing more remains. Zero TM overlap; clean new signal.
INVESTIGATIVE_CLOSURE_TRIGGER = re.compile(
    r"\bnothing\s+else\s+to\s+find\b"
    r"|\bnothing\s+to\s+find\s+purchase\s+for\b"
    r"|\byou\s+come\s+to\s+the\s+conclusion\s+that\s+there\s+is\s+nothing\b"
    r"|\bnothing\s+more\s+of\s+(?:note|interest|value)\b"
    r"|\byou'?(?:ve)?\s+(?:searched|exhausted|covered)\s+(?:the|this|every)\s+"
    r"(?:area|room|floor|space|hall|chamber)\b"
    r"|\bthere\s+is\s+nothing\s+(?:here|left|more|else)\b"
    r"|\bnothing\s+(?:of\s+(?:value|note|interest)\s+)?(?:remains?|left|here)\b"
    r"|\bjust\s+a\s+pit\b"
    r"|\bnothing\s+(?:useful|worthwhile|significant|catches\s+your\s+eye)\s*"
    r"(?:here|in\s+(?:this|the))?\b"
    r"|\bthe\s+(?:room|area|space)\s+(?:has\s+been\s+)?(?:cleared|emptied|searched)\b"
    r"|\bno\s+(?:other|more|additional)\s+(?:clues?|items?|secrets?)\s+(?:here|to\s+find)\b"
    r"|\bnothing\s+of\s+interest\s+(?:here|in\s+(?:this|the))\b",
    re.I,
)

# 6. LOCATION_DEPARTURE (TENTATIVE) -- party departs a scene-level named
# location. Highest FP risk; destination-scope check applied at Stage 0.
LOCATION_DEPARTURE_TRIGGER = re.compile(
    r"\bgather\s+(?:the\s+last\s+of\s+your|your)\s+(?:things|belongings|stuff|gear|horses?)"
    r"\s*[,.]?\s*(?:retrieve\s+(?:the\s+)?horses?\s*[,.]?\s*)?and\s+(?:head\s+out|depart|leave|exit)\b"
    r"|\byou\s+set\s+out\s+for\b"
    r"|\byou\s+(?:head|make)\s+(?:your\s+way\s+)?out\s+of\s+(?:the\s+)?"
    r"(?:city|town|village|fortress|dungeon|keep|temple|forest|region|capital)\b"
    r"|\byou\s+charter\s+a\s+ship\b"
    r"|\byou\s+board\s+(?:a|the)\s+(?:ship|vessel|boat)\b"
    r"|\bsetting\s+(?:sail|out)\s+(?:from|across|toward|for)\b"
    r"|\byou\s+make\s+your\s+way\s+to\s+(?:the\s+)?(?:continent\s+of\s+|[A-Z][a-z]+)\b"
    r"|\byou\s+leave\s+[A-Z][a-z]+\s+behind\b"
    r"|\bdepart(?:ing|ed)?\s+from\s+(?:the\s+)?(?:city|town|[A-Z][a-z]+)\b"
    r"|\bleaving\s+(?:[A-Z][a-z]+|the\s+city|the\s+town|the\s+fortress)\s+behind\b",
    re.I,
)

TRIGGER_FAMILIES = [
    ("SCENE_CUT", SCENE_CUT_TRIGGER),
    ("OVERNIGHT_REST", OVERNIGHT_REST_TRIGGER),
    ("TEMPORAL_MONTAGE", TEMPORAL_MONTAGE_TRIGGER),
    ("NPC_DEPARTURE", NPC_DEPARTURE_TRIGGER),
    ("INVESTIGATIVE_CLOSURE", INVESTIGATIVE_CLOSURE_TRIGGER),
    ("LOCATION_DEPARTURE", LOCATION_DEPARTURE_TRIGGER),
]

# Priority for same-span dedup: lower number = higher priority.
CATEGORY_PRIORITY = {
    "OVERNIGHT_REST": 1,
    "SCENE_CUT": 2,
    "NPC_DEPARTURE": 3,
    "INVESTIGATIVE_CLOSURE": 4,
    "LOCATION_DEPARTURE": 5,
    "TEMPORAL_MONTAGE": 6,
}


# ---------------------------------------------------------------------------
# Stage 0 -- DISCOURSE / EVENT classifier (phrase-span)
# ---------------------------------------------------------------------------
#
# Per spec S6 + Lesson 9. Operates at phrase-span level.
# D1: OOC scheduling / production language.
# D2: Trigger phrase inside NPC quoted speech.
# D3: In-scene micro-motion (LOCATION_DEPARTURE only).
# D4: Recap-state episode opening -- handled at turn level (whole-turn skip).

# D1: Production OOC + scheduling. Comprehensive per spec S7 FP1.
DISCOURSE_OOC = re.compile(
    r"\bwelcome\s+(?:to|back)\b"
    r"|\btonight'?s\s+episode\b"
    r"|\bnext\s+week'?s?\s+(?:episode|stream|show|game)\b"
    r"|\bsee\s+you\s+(?:guys\s+)?next\s+(?:week|time|month)\b"
    r"|\bwe'?ll\s+(?:be\s+(?:right\s+)?back|come\s+back)\b"
    r"|\bquick\s+break\b"
    r"|\btake\s+(?:a\s+)?(?:short|quick)\s+(?:bathroom\s+)?break\b"
    r"|\b(?:sponsor|patreon|wyrmwood|d&d\s+beyond|critmas|stream\s+of\s+many\s+eyes)\b"
    r"|\bnext\s+week\s+we\b"
    r"|\bpick\s+(?:this\s+)?up\s+next\s+(?:week|time|session)\b"
    r"|\bwe'?ll\s+pick\s+up\s+(?:from|where)\b"
    r"|\bwe'?ll\s+(?:see\s+you|leave\s+you)\s+(?:guys\s+)?(?:next|in|here|there)\b"
    r"|\bjoin\s+us\s+next\s+(?:week|time|session)\b"
    r"|\bwe'?re\s+going\s+to\s+take\s+a\s+break\b"
    r"|\bgoing\s+to\s+take\s+a\s+(?:short|quick)?\s*break\b"
    r"|\bthat'?s\s+where\s+we'?re\s+going\s+to\s+take\s+a\s+break\b"
    r"|\bcomic\s+con\b|\bGenCon\b|\bPAX\b"
    r"|\bpre[-\s]?order\b"
    r"|\b\[break\]\b|\b\[BREAK\]\b"
    r"|\bdiscuss\s+(?:this\s+)?over\s+the\s+next\s+(?:week|few)\b"
    r"|\bcomic\s+(?:available|out\s+now)\b",
    re.I,
)

# D3: In-scene micro-motion -- sub-location navigation within the current
# scene. Applied only to LOCATION_DEPARTURE candidates. Recon: 16 of 22
# LOCATION_DEPART hits in C2E027 were this FP shape (S12 risk 3).
MICRO_MOTION_RE = re.compile(
    r"\bmake\s+your\s+way\s+(?:across|up\s+to\s+the|over\s+to|"
    r"to\s+the\s+(?:other\s+side|far\s+corner|back|center|entrance))\b"
    r"|\bhead\s+(?:down|up|over|across)\s+(?:the|a|to)\s+"
    r"(?:stairs?|hallway|corridor|passage|ladder|steps?|ramp|tunnel)\b"
    r"|\byou\s+(?:move|step)\s+(?:across|over|through|to|toward)\s+the\s+"
    r"(?:door|window|shelf|chest|table|corner|wall|bar|counter|other)\b"
    r"|\bmake\s+(?:it|your\s+way)\s+to\s+the\s+secondary\b"
    r"|\bslip\s+(?:through|past|into)\s+the\s+(?:door|window|passage|crack)\b"
    r"|\bclimb\s+(?:the|a)\s+(?:stairs?|ladder|rope|cliff)\b"
    r"|\byou\s+approach\s+the\s+(?:door|gate|entrance|bar|desk|counter)\b"
    r"|\bhead\s+to\s+the\s+(?:cargo\s+hold|lower\s+deck|next\s+room|back\s+room)\b",
    re.I,
)

# NPC voice detection -- identical to loot_reward.py.
_SENT_BOUNDARY_RE = re.compile(r"[.!?](?:\s+|$)")

NPC_VOICING_TAG = re.compile(
    r"\b(?:he|she|it|they|the\s+\w+)\s+"
    r"(?:says?|said|goes|growls?|hisses?|whispers?|shouts?|yells?|barks?|"
    r"roars?|chuckles?|laughs?|sneers?|scoffs?|smiles?\s+and\s+says?|"
    r"replies|reply|replied|continues|continued|states|stated|answers|"
    r"answered|nods?\s+and\s+says?|adds?|asks?|asked|tells?|told)\b"
    r"|\b(?:says?|whispers?|growls?|hisses?|roars?|shouts?|yells?)\s*[:,]",
    re.I,
)
NPC_NAMED_SPEECH = re.compile(
    r"\b[A-Z][a-zA-Z'\-]{2,}\s+(?:says?|said|goes|growls?|hisses?|whispers?|"
    r"shouts?|sneers?|scoffs?|smiles?\s+and\s+says?|chuckles?|laughs?|"
    r"replies|continues|tells?|told)\b"
)

# Recap-state vocabulary -- for D4 turn-level filter (bounded lookback).
RECAP_VOCAB = re.compile(
    r"\blast\s+(?:week|episode|time|game)\b"
    r"|\bpreviously\s+on\b"
    r"|\bwe\s+(?:left\s+off|last\s+(?:left|saw|met))\b"
    r"|\bas\s+we\s+begin\s+tonight\b"
    r"|\bpicking\s+up\s+(?:where|from)\b"
    r"|\bto\s+(?:recap|summarize|bring\s+you\s+up\s+to\s+speed)\b"
    r"|\brejoining\s+our\s+(?:heroes|adventurers|group|party)\b",
    re.I,
)


def get_sentence_span(turn_text, phrase_start, phrase_end):
    """Return (sent_start, sent_end) for the sentence containing the phrase."""
    sent_start = 0
    for m in _SENT_BOUNDARY_RE.finditer(turn_text[:phrase_start]):
        sent_start = m.end()
    rest = turn_text[phrase_end:]
    m = _SENT_BOUNDARY_RE.search(rest)
    sent_end = phrase_end + m.start() + 1 if m else len(turn_text)
    return sent_start, sent_end


def is_phrase_in_npc_speech(turn_text, phrase_start, phrase_end):
    """True if phrase falls inside NPC dialogue (quoted or voiced).

    Compression triggers must be in Matt's narrative voice. NPC dialogue
    *preceding* a trigger is allowed (e.g., NPC farewell + Matt narrating
    the departure), but the trigger phrase itself inside NPC speech is D2.
    """
    quote_count = sum(1 for c in turn_text[:phrase_start] if c in '"“”')
    if quote_count % 2 == 1:
        return True
    sent_start, _ = get_sentence_span(turn_text, phrase_start, phrase_end)
    same_sentence_pre = turn_text[sent_start:phrase_start]
    if NPC_VOICING_TAG.search(same_sentence_pre):
        return True
    if NPC_NAMED_SPEECH.search(same_sentence_pre):
        return True
    return False


def stage_0_phrase(turn_text, phrase_start, phrase_end, family):
    """Classify a single candidate phrase as EVENT or DISCOURSE.

    Returns (label, reason). Label is 'EVENT' or 'DISCOURSE'.
    """
    sent_start, sent_end = get_sentence_span(turn_text, phrase_start, phrase_end)
    sentence = turn_text[sent_start:sent_end]

    # D1: OOC scheduling / production language.
    if DISCOURSE_OOC.search(sentence):
        return "DISCOURSE", "D1_ooc"

    # D2: Trigger phrase inside NPC quoted speech. Compression triggers
    # must be in Matt's narration voice, not in NPC dialogue.
    if is_phrase_in_npc_speech(turn_text, phrase_start, phrase_end):
        return "DISCOURSE", "D2_npc_voice"

    # D3: In-scene micro-motion (LOCATION_DEPARTURE only).
    if family == "LOCATION_DEPARTURE":
        if MICRO_MOTION_RE.search(sentence):
            return "DISCOURSE", "D3_micro_motion"

    return "EVENT", None


# ---------------------------------------------------------------------------
# Combat / recap state
# ---------------------------------------------------------------------------

COPIED_POSITIVE_INIT = re.compile(
    r"\b(?:re)?roll(?:s|ing|ed)?\s+(?:for\s+|some\s+)?initiative\b"
    r"|\binitiative\s+(?:has\s+(?:now\s+)?|now\s+)?kicked\s+in\b"
    r"|\b(?:now|we'?re)\s+in\s+initiative\b"
    r"|\binitiative\s+is\s+being\s+rolled\b"
    r"|\bfor\s+initiative\b",
    re.I,
)
COPIED_END_OF_COMBAT = re.compile(
    r"\bcombat\s+ends?\b"
    r"|\bthat'?s\s+the\s+end\s+of\s+(?:combat|the\s+(?:fight|encounter|battle))\b"
    r"|\bend\s+of\s+the\s+encounter\b"
    r"|\bcombat\s+is\s+over\b"
    r"|\byou'?ve\s+defeated\b"
    r"|\bthe\s+(?:fight|battle|encounter)\s+is\s+(?:over|done|finished)\b",
    re.I,
)
INIT_VOCABULARY = re.compile(r"\binitiative\b", re.I)


def derive_combat_state(turns, candidate_idx):
    """True if episode appears to be in active combat at candidate_idx.
    Copied from loot_reward.py -- same staleness-window logic.
    """
    init_seen_idx = None
    end_seen_after_init = False
    start = max(0, candidate_idx - COMBAT_STATE_LOOKBACK_TURNS)
    for j in range(start, candidate_idx):
        t = turns[j]
        if t["speaker"] != "MATT":
            continue
        if COPIED_POSITIVE_INIT.search(t["text"]):
            init_seen_idx = j
            end_seen_after_init = False
        elif init_seen_idx is not None and COPIED_END_OF_COMBAT.search(t["text"]):
            end_seen_after_init = True
    if init_seen_idx is None:
        return False
    if end_seen_after_init:
        return False
    stale_start = max(0, candidate_idx - COMBAT_STATE_STALENESS_TURNS)
    return any(
        INIT_VOCABULARY.search(turns[j]["text"])
        for j in range(stale_start, candidate_idx)
    )


def derive_recap_state(turns, candidate_idx, total_turns):
    """True if turn is inside an episode-opening recap (position <= 3%).

    Bounded 15-turn lookback per Loot/Reward Phase 3.6 fix. Whole-episode
    scan caused over-firing; lookback keeps the check tight.
    """
    if total_turns == 0:
        return False
    pos = candidate_idx / total_turns
    if pos > RECAP_EPISODE_POSITION_THRESHOLD:
        return False
    lookback_start = max(0, candidate_idx - 15)
    for j in range(lookback_start, candidate_idx + 1):
        if RECAP_VOCAB.search(turns[j]["text"]):
            return True
    return False


# ---------------------------------------------------------------------------
# Buildup signal detection (Q3 -- 15-turn lookback)
# ---------------------------------------------------------------------------

PLAYER_INTENT_RE = re.compile(
    r"\blet'?s\s+(?:head\s+out|leave|get\s+out|move\s+on|go)\b"
    r"|\bi\s+think\s+we'?re\s+done\s+here\b"
    r"|\bwe\s+should\s+(?:move\s+on|leave|go|get\s+going)\b"
    r"|\bi\s+(?:want|think\s+we\s+should)\s+(?:to\s+)?(?:leave|go|head\s+out)\b"
    r"|\bthere'?s\s+nothing\s+(?:more|else)\s+(?:here|for\s+us)\b",
    re.I,
)

NPC_RESOLUTION_RE = re.compile(
    r"\byou\s+have\s+my\s+(?:thanks|gratitude)\b"
    r"|\bi\s+(?:owe|will\s+owe)\s+you\b"
    r"|\b(?:job|task|quest|mission)\s+(?:is\s+)?(?:done|complete|finished|fulfilled)\b"
    r"|\b(?:purpose|mission|objective)\s+(?:has\s+been\s+)?(?:fulfilled|completed|achieved)\b",
    re.I,
)

OBJECTIVE_COMPLETION_RE = re.compile(
    r"\byou(?:'?ve|ve)?\s+(?:got|found|retrieved|recovered|completed)\s+"
    r"(?:what|it|all|everything)\b"
    r"|\byou\s+have\s+(?:what\s+you\s+came\s+for|succeeded|accomplished)\b"
    r"|\b(?:we|you)\s+have\s+what\s+(?:we|you)\s+came\s+for\b"
    r"|\bsuccessfully\s+(?:retrieved|obtained|acquired|secured)\b",
    re.I,
)

STALE_SIGNAL_RE = re.compile(
    r"\bwhat\s+(?:do\s+you|would\s+you\s+like\s+to)\s+(?:want\s+to\s+)?do\b"
    r"|\bis\s+there\s+anything\s+else\s*\?"
    r"|\banything\s+else\s+(?:here|you\s+(?:want|need)\s+to\s+do|you\s+wish\s+to\s+do)?\b"
    r"|\banything\s+you\s+(?:want|wish)\s+to\s+do\s+(?:here|while)\b"
    r"|\bwhat\s+else\s+(?:do\s+you\s+(?:want\s+to\s+do|have)|would\s+you\s+like)?\s*\?",
    re.I,
)


def detect_buildup_signal(turns, trigger_idx):
    """Return (buildup_signal_str, buildup_window_turns) from preceding context.

    Priority: player_intent > npc_resolution > objective_completion >
    repeated_stale_signal > matt_initiated.
    """
    trigger_turn_number = turns[trigger_idx]["number"]
    start = max(0, trigger_idx - BUILDUP_LOOKBACK_TURNS)
    stale_count = 0

    for j in range(trigger_idx - 1, start - 1, -1):
        t = turns[j]
        distance = trigger_turn_number - t["number"]
        if t["speaker"] != "MATT":
            if PLAYER_INTENT_RE.search(t["text"]):
                return "player_intent", distance
        else:
            if NPC_RESOLUTION_RE.search(t["text"]):
                return "npc_resolution", distance
            if OBJECTIVE_COMPLETION_RE.search(t["text"]):
                return "objective_completion", distance
            if STALE_SIGNAL_RE.search(t["text"]):
                stale_count += 1

    if stale_count >= 2:
        return "repeated_stale_signal", BUILDUP_LOOKBACK_TURNS
    return "matt_initiated", None


def count_stale_signals_preceding(turns, trigger_idx):
    """Count STALE_SIGNAL hits in the preceding STALE_SIGNAL_WINDOW turns."""
    start = max(0, trigger_idx - STALE_SIGNAL_WINDOW)
    count = 0
    for j in range(start, trigger_idx):
        if turns[j]["speaker"] == "MATT" and STALE_SIGNAL_RE.search(turns[j]["text"]):
            count += 1
    return count


# ---------------------------------------------------------------------------
# Compression scope (S13.7 sketch field)
# ---------------------------------------------------------------------------

_SHORT_DURATION_RE = re.compile(r"\b(?:minute|hour)s?\b", re.I)
_LONG_DURATION_RE = re.compile(r"\b(?:day|week|month|year)s?\b", re.I)


def derive_compression_scope(category, trigger_phrase):
    """Best-effort compression_scope: in_scene | scene_exit | UNKNOWN."""
    if category in ("SCENE_CUT", "OVERNIGHT_REST", "LOCATION_DEPARTURE"):
        return "scene_exit"
    if category in ("INVESTIGATIVE_CLOSURE", "NPC_DEPARTURE"):
        return "in_scene"
    if category == "TEMPORAL_MONTAGE":
        if _SHORT_DURATION_RE.search(trigger_phrase):
            return "in_scene"
        if _LONG_DURATION_RE.search(trigger_phrase):
            return "scene_exit"
        return "UNKNOWN"
    return "UNKNOWN"


def derive_surface_form(category):
    """Map category to surface_form label."""
    mapping = {
        "SCENE_CUT": "explicit_cut",
        "OVERNIGHT_REST": "diurnal_transition",
        "TEMPORAL_MONTAGE": "montage",
        "NPC_DEPARTURE": "npc_exit",
        "INVESTIGATIVE_CLOSURE": "investigation_closed",
        "LOCATION_DEPARTURE": "location_exit",
        "STALE_HOLD_CANDIDATE": "stale_hold",
        "UNKNOWN_SHAPE": "unknown",
    }
    return mapping.get(category, "unknown")


# ---------------------------------------------------------------------------
# Time-Mention overlap check (S13.4)
# ---------------------------------------------------------------------------

def check_time_mention_overlap(episode_id, trigger_turn_number):
    """True if the trigger turn also has a Time-Mention record.

    Checks per-episode TM JSON output at output/time_mention/{episode_id}.json.
    Returns False if the file doesn't exist -- TM may not have run yet.
    """
    tm_path = TM_OUTPUT_DIR / f"{episode_id}.json"
    if not tm_path.exists():
        return False
    try:
        with open(tm_path, "r", encoding="utf-8") as f:
            records = json.load(f)
        for r in records:
            if r.get("trigger_turn_number") == trigger_turn_number:
                return True
    except (OSError, json.JSONDecodeError):
        pass
    return False


# ---------------------------------------------------------------------------
# Episode loading (copied from loot_reward.py -- same source format)
# ---------------------------------------------------------------------------

def parse_episode_id(episode_id):
    m = EPISODE_ID_RE.match(episode_id)
    if not m:
        return None
    return m.group(1), int(m.group(2))


def list_all_episodes():
    seen = set()
    for fn in os.listdir(SOURCE_BASE):
        if not fn.endswith(".json"):
            continue
        ep = fn.split("_")[0]
        seen.add(ep)
    return sorted(seen)


def load_episode_turns(episode_id):
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
_filtered_discourse_log = []
_unknown_shape_log = []


def log_unknown(msg):
    line = f"[EXTRACTOR_UNKNOWN] {msg}"
    _unknown_log.append(line)
    print(line, file=sys.stderr)


def log_filtered_discourse(text, reason, ep, turn_number):
    snippet = (text or "")[:200].replace("\n", " ")
    line = f"[FILTERED_DISCOURSE] {ep}_t{turn_number} :: {reason} :: {snippet}"
    _filtered_discourse_log.append(line)


def log_unknown_shape(text, ep, turn_number, phrase):
    snippet = (text or "")[:200].replace("\n", " ")
    line = f"[UNKNOWN_SHAPE] {ep}_t{turn_number} :: phrase={phrase!r} :: {snippet}"
    _unknown_shape_log.append(line)


# ---------------------------------------------------------------------------
# Preceding context
# ---------------------------------------------------------------------------

def gather_preceding_context(turns, trigger_idx, char_budget):
    pre_reversed = []
    used = 0
    for j in range(trigger_idx - 1, -1, -1):
        t = turns[j]
        text_len = len(t["text"])
        if used + text_len > char_budget:
            break
        entry = {
            "speaker": t["speaker"],
            "text": t["text"],
            "turn_number": t["number"],
        }
        pre_reversed.append(entry)
        used += text_len
    return list(reversed(pre_reversed)), used


# ---------------------------------------------------------------------------
# Candidate collection and same-span dedup
# ---------------------------------------------------------------------------

def collect_phrase_candidates(turn_text):
    """Return sorted list of (family, start, end, phrase_text)."""
    out = []
    for family, pattern in TRIGGER_FAMILIES:
        for m in pattern.finditer(turn_text):
            out.append((family, m.start(), m.end(), m.group(0)))
    out.sort(key=lambda x: (x[1], x[2]))
    return out


def dedup_phrase_candidates(candidates):
    """Resolve overlapping spans by category priority.

    When two candidates share overlapping spans, the higher-priority
    category (lower CATEGORY_PRIORITY value) survives. Non-overlapping
    candidates from different families are kept as separate records.
    """
    if not candidates:
        return candidates
    survivors = []
    for c in candidates:
        family, s, e, phrase = c
        collide_idx = None
        for i, kept in enumerate(survivors):
            kf, ks, ke, _ = kept
            if s < ke and e > ks:
                collide_idx = i
                break
        if collide_idx is None:
            survivors.append(c)
        else:
            kept_family = survivors[collide_idx][0]
            if CATEGORY_PRIORITY.get(family, 99) < CATEGORY_PRIORITY.get(kept_family, 99):
                survivors[collide_idx] = c
    return survivors


# ---------------------------------------------------------------------------
# Q6 -- STALE_HOLD_CANDIDATE detection (post-episode pass)
# ---------------------------------------------------------------------------

def detect_stale_hold_candidates(turns, compression_turn_numbers, episode_id,
                                  campaign, episode_num, extracted_at):
    """Emit STALE_HOLD_CANDIDATE records for Q6 coverage.

    A stale-hold candidate is a STALE_SIGNAL cluster (>=3 occurrences in a
    30-turn window) that is NOT followed by a compression event within 20
    turns. Single-extractor partial Q6 shape -- spec S8 and S13.3.
    """
    stale_positions = []
    for idx, t in enumerate(turns):
        if t["speaker"] == "MATT" and STALE_SIGNAL_RE.search(t["text"]):
            stale_positions.append(idx)

    if not stale_positions:
        return []

    total_turns = len(turns)
    records = []
    emitted_windows = set()

    for anchor_idx in stale_positions:
        window = [idx for idx in stale_positions
                  if anchor_idx - STALE_SIGNAL_WINDOW <= idx <= anchor_idx]
        if len(window) < STALE_CLUSTER_THRESHOLD:
            continue

        last_in_window = max(window)
        last_turn_number = turns[last_in_window]["number"]
        follow_end = min(len(turns), last_in_window + STALE_FOLLOW_THROUGH_WINDOW + 1)
        has_compression = any(
            turns[j]["number"] in compression_turn_numbers
            for j in range(last_in_window + 1, follow_end)
        )
        if has_compression:
            continue

        window_key = (turns[window[0]]["number"], last_turn_number)
        if window_key in emitted_windows:
            continue
        emitted_windows.add(window_key)

        t = turns[last_in_window]
        ep_pos = round(last_in_window / total_turns, 4) if total_turns else 0.0
        preceding_turns_ctx, preceding_chars = gather_preceding_context(
            turns, last_in_window, PRECEDING_CONTEXT_BUDGET
        )
        m = STALE_SIGNAL_RE.search(t["text"])
        trigger_phrase = m.group(0) if m else t["text"][:60]

        records.append({
            "campaign": campaign,
            "episode": episode_num,
            "episode_position_pct": ep_pos,
            "speaker": t["speaker"],
            "event_type": "compression_cadence",
            "raw_text": t["text"],
            "preceding_context_chars": preceding_chars,
            "extractor_version": EXTRACTOR_VERSION,
            "extracted_at": extracted_at,

            "trigger_turn_number": t["number"],
            "trigger_phrase": trigger_phrase,
            "compression_category": "STALE_HOLD_CANDIDATE",
            "surface_form": "stale_hold",
            "compression_scope": "UNKNOWN",
            "buildup_signal": "repeated_stale_signal",
            "buildup_window_turns": None,
            "is_recap_state": False,
            "is_combat_state": False,
            "time_mention_overlap": False,
            "stale_signal_count_preceding": len(window),
            "stale_cluster_first_turn": turns[window[0]]["number"],
            "stale_cluster_last_turn": last_turn_number,
            "same_turn_record_index": 0,
            "preceding_turns": preceding_turns_ctx,
        })

    return records


# ---------------------------------------------------------------------------
# Episode processing
# ---------------------------------------------------------------------------

def process_episode(episode_id, extracted_at):
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
    compression_turn_numbers = set()

    for idx, t in enumerate(turns):
        # MATT-only. Phrase-span Stage 0 handles NPC dialogue within turns.
        if t["speaker"] != "MATT":
            continue

        # D4 turn-level filter: recap-state opening. Bounded 15-turn lookback.
        # Whole-turn skip -- recap vocabulary in opening framing describes past
        # compressions, not new compression decisions.
        if derive_recap_state(turns, idx, total_turns):
            continue

        # Stage 1 -- find candidate phrases.
        candidates = collect_phrase_candidates(t["text"])
        if not candidates:
            continue

        candidates = dedup_phrase_candidates(candidates)

        # State flags (computed once per trigger turn).
        is_combat_state = derive_combat_state(turns, idx)
        episode_position_pct = round(idx / total_turns, 4) if total_turns else 0.0

        # Preceding context (computed once per trigger turn).
        preceding_turns_ctx, preceding_chars = gather_preceding_context(
            turns, idx, PRECEDING_CONTEXT_BUDGET
        )

        same_turn_idx = 0
        turn_records = []

        for family, s, e, phrase in candidates:
            # Phrase-span Stage 0.
            stage_0, reason = stage_0_phrase(t["text"], s, e, family)
            if stage_0 == "DISCOURSE":
                log_filtered_discourse(t["text"], reason, episode_id, t["number"])
                continue

            category = family
            compression_scope = derive_compression_scope(category, phrase)
            surface_form = derive_surface_form(category)

            buildup_signal, buildup_window_turns = detect_buildup_signal(turns, idx)
            stale_count = count_stale_signals_preceding(turns, idx)
            tm_overlap = check_time_mention_overlap(episode_id, t["number"])

            record = {
                # Required CORPUS_BUILDER.md fields.
                "campaign": campaign,
                "episode": episode_num,
                "episode_position_pct": episode_position_pct,
                "speaker": t["speaker"],
                "event_type": "compression_cadence",
                "raw_text": t["text"],
                "preceding_context_chars": preceding_chars,
                "extractor_version": EXTRACTOR_VERSION,
                "extracted_at": extracted_at,

                # Per-extractor fields.
                "trigger_turn_number": t["number"],
                "trigger_phrase": phrase,
                "compression_category": category,
                "surface_form": surface_form,
                "compression_scope": compression_scope,
                "buildup_signal": buildup_signal,
                "buildup_window_turns": buildup_window_turns,
                "is_recap_state": False,
                "is_combat_state": is_combat_state,
                "time_mention_overlap": tm_overlap,
                "stale_signal_count_preceding": stale_count,
                "same_turn_record_index": same_turn_idx,
                "preceding_turns": preceding_turns_ctx,
            }
            turn_records.append(record)
            compression_turn_numbers.add(t["number"])
            same_turn_idx += 1

        records.extend(turn_records)

    # Q6 post-pass: stale-hold candidates.
    stale_hold = detect_stale_hold_candidates(
        turns, compression_turn_numbers, episode_id, campaign, episode_num, extracted_at
    )
    records.extend(stale_hold)

    return records


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def utc_now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def run_sample():
    extracted_at = utc_now_iso()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    total = 0
    total_by_category = {}

    for ep in SAMPLE_EPISODES:
        records = process_episode(ep, extracted_at)
        out_path = OUTPUT_DIR / f"{ep}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, ensure_ascii=False)
        cat_counts = {}
        for r in records:
            c = r.get("compression_category", "?")
            cat_counts[c] = cat_counts.get(c, 0) + 1
            total_by_category[c] = total_by_category.get(c, 0) + 1
        total += len(records)
        cat_str = "  ".join(f"{k}={v}" for k, v in sorted(cat_counts.items()))
        print(f"  {ep}: {len(records)} record(s)  [{cat_str}]  -> {out_path}")

    print(f"\nSAMPLE_COMPLETE: episodes={len(SAMPLE_EPISODES)} records={total}")
    print("Category breakdown:")
    for cat, n in sorted(total_by_category.items()):
        print(f"  {cat}: {n}")
    print(f"output dir: {OUTPUT_DIR}")
    print(f"[FILTERED_DISCOURSE] count: {len(_filtered_discourse_log)}")
    print(f"[UNKNOWN_SHAPE] count: {len(_unknown_shape_log)}")
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
            print(f"  [{i}/{len(episodes)}] processed, running total: {total}")
    print(f"\nEXTRACTOR_COMPLETE: episodes_processed={len(episodes)} records={total}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--sample", action="store_true",
                       help="Run on the 10 hand-sample episodes only.")
    group.add_argument("--full", action="store_true",
                       help="Run on all CRD3 episodes.")
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
