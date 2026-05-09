#!/usr/bin/env python3
"""
Compression Cadence Extractor v1.

Reads CRD3 (c=2 alignment dir) and emits one JSON record per detected
compression-decision event. A compression event is one of six categories:
SCENE_CUT, OVERNIGHT_REST, TEMPORAL_MONTAGE, NPC_DEPARTURE,
INVESTIGATIVE_CLOSURE, LOCATION_DEPARTURE.

Spec: findings/track5_compression_cadence_phase1_spec.md (§13 decisions locked).
Lessons: docs/corpus_builder_lessons_v2.md — Lesson 9 (phrase-span Stage 0)
operative from line one.

Locked §13 decisions:
  §13.1 Taxonomy: all six categories (LOCATION_DEPARTURE tentative).
  §13.2 Stage 0: phrase-span per §6 recommendation.
  §13.3 Q6: in-scope single-extractor partial (STALE_SIGNAL cluster ≥3
        in 30-turn window, no compression follow-through within 20 turns;
        emitted as compression_category=STALE_HOLD_CANDIDATE).
  §13.4 TM overlap: emit with time_mention_overlap=True flag (don't suppress).
  §13.5 Hand-sample: 10 episodes (seed 2222).
  §13.6 Player-driven compressions: Matt-voice only; player intent captured
        as buildup_signal=player_intent on the Matt-narration record.
  §13.7 compression_scope: include as sketch field (best-effort rule-based).

Usage:
    python3 compression_cadence.py --sample
        Runs on the 10 hand-sample episodes. Writes per-episode files at
        ../output/compression_cadence/{episode_id}.json.

    python3 compression_cadence.py --full
        Runs on all CRD3. NOT to be invoked at Phase 2 — hand-sample only.
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
RECAP_EPISODE_POSITION_THRESHOLD = 0.03   # D4: ≤3% of episode
STALE_SIGNAL_WINDOW = 30
STALE_FOLLOW_THROUGH_WINDOW = 20
STALE_CLUSTER_THRESHOLD = 3

# §13.5 locked hand-sample. seed=2222; stratified across C1 phases.
# Available pool after removing 107 prior-eval-set episodes and 7 recon
# episodes: 22 C1 + 4 C2 = 26 episodes. C1-only stratified selection
# (3 phase buckets + 7 top-up from remaining pool). C2 available but not
# drawn (C2E008, C2E009, C2E023, C2E039). All 10 disjoint from prior 107
# + 7 recon episodes. No deviation.
SAMPLE_EPISODES = [
    "C1E004", "C1E013", "C1E025", "C1E036", "C1E050",
    "C1E056", "C1E088", "C1E090", "C1E093", "C1E097",
]

EPISODE_ID_RE = re.compile(r"^(C\d+)E(\d{3,4})$")


# ---------------------------------------------------------------------------
# Stage 1 — trigger families
# ---------------------------------------------------------------------------

# 1. SCENE_CUT — explicit editorial cuts and time-transition announcements.
SCENE_CUT_TRIGGER = re.compile(
    r"\bcut\s+to\s+black\b"
    r"|\bwe\s+cut\s+to\b"
    r"|\bcut\s+away\s+to\b"
    r"|\bsome\s+time\s+(?:later|has\s+passed)\b"
    r"|\btime\s+(?:has\s+(?:now\s+)?passed|passes)\b"
    r"|\bskip\s+(?:ahead|forward)\s+(?:to|in\s+time)\b"
    r"|\bfast[-\s]forward\s+(?:to|in\s+time)\b"
    r"|\bas\s+(?:this|that)\s+time\s+has\s+passed\b"
    r"|\bthat(?:'s|\s+is)\s+where\s+(?:we(?:'re|'ll)\s+)?(?:leave|end|cut)\b",
    re.I,
)

# 2. OVERNIGHT_REST — diurnal-boundary compression to next morning.
OVERNIGHT_REST_TRIGGER = re.compile(
    r"\byou\s+(?:all\s+)?awaken\b"
    r"|\bawaking\s+in\s+the\s+(?:early\s+)?morning\b"
    r"|\bawakening\s+in\s+the\b"
    r"|\bas\s+the\s+morning\s+(?:comes?|arrives?|breaks?)\b"
    r"|\bfind\s+yourselves?\s+to\s+rest\s+for\s+the\s+evening\b"
    r"|\bthe\s+following\s+morning\b"
    r"|\byou\s+(?:all\s+)?come\s+to\s+(?:consciousness|awareness|your\s+senses)\b"
    r"|\bcome\s+to\s+consciousness\b"
    r"|\bby\s+(?:the\s+time\s+)?(?:morning|dawn|sunrise)\b"
    r"|\bthe\s+morning\s+(?:sun|light|air|arrives?|comes?|breaks?)\b"
    r"|\byou\s+(?:all\s+)?(?:wake\s+up|wake\s+to|awaken\s+to)\b"
    r"|\bshooting\s+up\s+with\s+a\s+gasp\b"
    r"|\bin\s+the\s+(?:early\s+)?(?:pre[-\s])?dawn\s+hour\b",
    re.I,
)

# 3. TEMPORAL_MONTAGE — compressed in-fiction time (hours to months).
TEMPORAL_MONTAGE_TRIGGER = re.compile(
    r"\bover\s+the\s+(?:next|course\s+of\s+the|following)\s+"
    r"(?:\d+\s+)?(?:hour|day|week|month|year|minute)s?\b"
    r"|\bover\s+the\s+(?:course\s+of\s+the\s+)?(?:evening|day|night|week|month|year)\b"
    r"|\bas\s+the\s+(?:days?|weeks?|months?|years?)\s+(?:go\s+by|pass(?:\s+by)?)\b"
    r"|\bspend\s+the\s+next\s+(?:\d+\s+)?(?:hour|day|week|month|minute)s?\b"
    r"|\bthroughout\s+the\s+(?:day|night|week|month|morning|afternoon|evening)\b"
    r"|\bas\s+you\s+continue\s+your\s+trek\b"
    r"|\bfor\s+the\s+next\s+(?:\d+\s+)?(?:hour|day|week|month|minute)s?\b"
    r"|\bin\s+the\s+(?:days?|weeks?|months?|years?)\s+(?:that\s+)?(?:follow|pass)\b"
    r"|\bthe\s+next\s+(?:\d+\s+)?(?:hours?|days?|weeks?|months?)\s+(?:pass|are|see|bring)\b"
    r"|\bmonths?\s+(?:of\s+(?:preparation|training|travel)|go\s+by|pass)\b",
    re.I,
)

# 4. NPC_DEPARTURE — NPC ends active scene presence.
# Trigger phrases are Matt-narrated departures; phrases inside NPC quoted
# speech are rejected by Stage 0 D2. is_phrase_in_npc_speech() correctly
# handles mixed turns (NPC dialogue followed by Matt narration of departure).
NPC_DEPARTURE_TRIGGER = re.compile(
    r"\b(?:exit|exits)\s+(?:the\s+)?(?:room|building|tavern|inn|hall|area|shop|chamber|tent)\b"
    r"|\btakes?\s+(?:his|her|their|its)\s+leave\b"
    r"|\bbids?\s+(?:you|them|us)\s+(?:farewell|adieu|goodbye|good\s+night)\b"
    r"|\b(?:head|heads)\s+back\s+to\s+(?:his|her|their|the|a|an)\s+(?:work|seat|table|post|duties|shop)\b"
    r"|\b(?:makes?|making)\s+(?:his|her|their|its)\s+way\s+out\s+of\s+the\b"
    r"|\bturns?\s+(?:around\s+)?and\s+(?:exit|exits|departs?|leaves?)\s+the\b"
    r"|\b(?:says?|bid|bade)\s+(?:his|her|their)\s+(?:goodbyes?|farewell)\b"
    r"|\bsteps?\s+out\s+of\s+(?:the\s+)?(?:room|building|tavern|inn|hall|space)\b"
    r"|\bgathers?\s+(?:his|her|their|its)\s+(?:things|belongings|stuff)\s+and\s+(?:leave|leaves?|depart|exits?)\b"
    r"|\bslowly\s+(?:exits?|departs?|leaves?)\b"
    r"|\b(?:the\s+)?(?:other|rest|remaining)\s+(?:few\s+)?(?:exit|leave|depart)\s+the\b"
    r"|\btake\s+a\s+different\s+table\b",
    re.I,
)

# 5. INVESTIGATIVE_CLOSURE — search/investigation beat declared closed.
INVESTIGATIVE_CLOSURE_TRIGGER = re.compile(
    r"\bnothing\s+else\s+to\s+find\b"
    r"|\bnothing\s+to\s+find\s+purchase\s+for\b"
    r"|\byou\s+come\s+to\s+the\s+conclusion\s+that\s+there\s+is\s+nothing\b"
    r"|\bnothing\s+more\s+of\s+(?:note|interest|value)\b"
    r"|\byou'?ve\s+(?:searched|exhausted|covered)\s+(?:the|this|every)\s+(?:area|room|floor|space)\b"
    r"|\bthere\s+is\s+nothing\s+(?:here|left|more|else)\b"
    r"|\bnothing\s+(?:of\s+(?:value|note)\s+)?(?:remains?|left|here)\b"
    r"|\bjust\s+a\s+pit\b"
    r"|\bnothing\s+(?:useful|worthwhile|significant)\s*(?:here|in\s+(?:this|the))?\b"
    r"|\bthe\s+(?:room|area|space)\s+(?:has\s+been\s+)?(?:cleared|emptied|searched)\b"
    r"|\bno\s+(?:other|more|additional)\s+(?:clues?|items?|secrets?)\s+(?:here|to\s+find)\b"
    r"|\bnothing\s+of\s+interest\s+(?:here|in\s+(?:this|the))\b",
    re.I,
)

# 6. LOCATION_DEPARTURE — party departs a scene-level named location.
# Trigger patterns require named-location indicators or specific travel
# vocabulary to distinguish from in-scene micro-motion (FP2).
LOCATION_DEPARTURE_TRIGGER = re.compile(
    r"\bgather\s+(?:the\s+last\s+of\s+your|your)\s+(?:things|belongings|stuff|gear|horses?)\s*[,.]?\s*"
    r"(?:retrieve\s+(?:the\s+)?horses?\s*[,.]?\s*)?and\s+(?:head\s+out|depart|leave|exit)\b"
    r"|\byou\s+set\s+out\s+for\b"
    r"|\byou\s+(?:head|make)\s+(?:your\s+way\s+)?out\s+of\s+(?:the\s+)?(?:city|town|village|fortress|dungeon|keep|temple|forest|region|capital)\b"
    r"|\byou\s+charter\s+a\s+ship\b"
    r"|\byou\s+board\s+(?:a|the)\s+(?:ship|vessel|boat)\b"
    r"|\bsetting\s+(?:sail|out)\s+(?:from|across|toward|for)\b"
    r"|\byou\s+make\s+your\s+way\s+to\s+(?:the\s+)?(?:continent\s+of\s+|[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b"
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

# Higher priority wins when trigger spans overlap on the same turn.
CATEGORY_PRIORITY = {
    "OVERNIGHT_REST": 1,
    "SCENE_CUT": 2,
    "NPC_DEPARTURE": 3,
    "INVESTIGATIVE_CLOSURE": 4,
    "LOCATION_DEPARTURE": 5,
    "TEMPORAL_MONTAGE": 6,
}

CATEGORY_TO_SURFACE_FORM = {
    "SCENE_CUT": "explicit_cut",
    "OVERNIGHT_REST": "diurnal_transition",
    "TEMPORAL_MONTAGE": "montage",
    "NPC_DEPARTURE": "npc_exit",
    "INVESTIGATIVE_CLOSURE": "investigation_closed",
    "LOCATION_DEPARTURE": "location_exit",
    "STALE_HOLD_CANDIDATE": "stale_hold",
    "UNKNOWN_SHAPE": "unknown",
}


# ---------------------------------------------------------------------------
# Stage 0 — DISCOURSE / EVENT classifier (phrase-span)
# ---------------------------------------------------------------------------

# D1: Production OOC + scheduling language. Highest-volume FP family (§7 FP1).
DISCOURSE_OOC = re.compile(
    r"\bwelcome\s+(?:to|back)\b"
    r"|\btonight'?s\s+episode\b"
    r"|\bnext\s+week'?s?\s+(?:episode|stream|show|game)\b"
    r"|\bsee\s+you\s+(?:guys\s+)?next\s+(?:week|time|month)\b"
    r"|\bwe'?ll\s+(?:be\s+(?:right\s+)?back|come\s+back)\b"
    r"|\bquick\s+break\b|\btake\s+(?:a\s+)?(?:short|quick)\s+(?:bathroom\s+)?break\b"
    r"|\b(?:sponsor|patreon|wyrmwood|d&d\s+beyond|critmas|stream\s+of\s+many\s+eyes)\b"
    r"|\bnext\s+week\s+we\b"
    r"|\bpick\s+(?:this\s+up|things\s+up|up\s+from\s+here)\s+next\s+(?:week|time|session)\b"
    r"|\bwe'?ll\s+pick\s+up\s+(?:from|where)\b"
    r"|\bwe'?ll\s+(?:see\s+you|leave\s+you)\s+(?:guys\s+)?(?:next|here|there)\b"
    r"|\bjoin\s+us\s+next\s+(?:week|time|session)\b"
    r"|\bair\s+(?:the\s+)?(?:panel|episode)\s+next\s+(?:week|time)\b"
    r"|\bcomic\s+(?:available|out|now)\b"
    r"|\bpre[-\s]?order\b"
    r"|\bdiscuss\s+(?:this\s+)?over\s+the\s+next\s+(?:week|few)\b"
    r"|\b\[break\]\b|\b\[BREAK\]\b"
    r"|\btake\s+a\s+break\b"
    r"|\bcomic\s+con\b"
    r"|\bGenCon\b|\bPAX\b",
    re.I,
)

# D3: In-scene micro-motion — sub-location navigation within the current
# scene. Applied only to LOCATION_DEPARTURE candidates (§6 D3).
MICRO_MOTION_RE = re.compile(
    r"\bmake\s+your\s+way\s+(?:across|to\s+the\s+(?:other\s+side|far\s+corner|back\s+of|center)|up\s+to\s+the|over\s+to)\b"
    r"|\bhead\s+(?:down|up|over|across)\s+(?:the|a|to)\s+(?:stairs?|hallway|corridor|passage|ladder|steps?|ramp)\b"
    r"|\byou\s+(?:move|step)\s+(?:across|over|through|to|toward)\s+the\s+(?:door|window|shelf|chest|table|corner|wall|bar|counter)\b"
    r"|\bmake\s+(?:it|your\s+way)\s+to\s+the\s+secondary\b"
    r"|\bslip\s+(?:through|past|into)\s+the\s+(?:door|window|passage|crack)\b"
    r"|\bclimb\s+(?:the|a)\s+(?:stairs?|ladder|rope|cliff)\b"
    r"|\byou\s+approach\s+the\s+(?:door|gate|entrance|bar|desk|counter)\b",
    re.I,
)

# D4: Recap-state opening — compression vocabulary describing past events.
RECAP_VOCAB = re.compile(
    r"\blast\s+(?:week|episode|time|game|we\s+(?:left|saw))\b"
    r"|\bpreviously\s+on\b"
    r"|\bwe\s+(?:left\s+off|last\s+(?:left|saw|met))\b"
    r"|\bas\s+we\s+begin\s+tonight\b"
    r"|\bpicking\s+up\s+(?:where|from)\b"
    r"|\bto\s+(?:recap|summarize|bring\s+you\s+up\s+to\s+speed)\b"
    r"|\brejoining\s+our\s+(?:heroes|adventurers|group|party)\b",
    re.I,
)

# NPC voice detection (same pattern as loot_reward.py).
_SENT_BOUNDARY_RE = re.compile(r"[.!?](?:\s+|$)")

NPC_VOICING_TAG = re.compile(
    r"\b(?:he|she|it|they|the\s+\w+)\s+"
    r"(?:says?|said|goes|growls?|hisses?|whispers?|shouts?|yells?|barks?|"
    r"roars?|chuckles?|laughs?|sneers?|scoffs?|smiles?\s+and\s+says?|"
    r"replies|reply|replied|continues|continued|states|stated|answers|"
    r"answered|nods?\s+and\s+says?|adds?|asks?|asked|tells?|told)\b"
    r'|\b(?:says?|whispers?|growls?|hisses?|roars?|shouts?|yells?)\s*[:,]\s+["""]',
    re.I,
)
NPC_NAMED_SPEECH = re.compile(
    r"\b[A-Z][a-zA-Z'\-]{2,}\s+(?:says?|said|goes|growls?|hisses?|whispers?|"
    r"shouts?|sneers?|scoffs?|smiles?\s+and\s+says?|chuckles?|laughs?|"
    r"replies|continues|tells?|told)\b"
)


def get_sentence_span(turn_text, phrase_start, phrase_end):
    sent_start = 0
    for m in _SENT_BOUNDARY_RE.finditer(turn_text[:phrase_start]):
        sent_start = m.end()
    rest = turn_text[phrase_end:]
    m = _SENT_BOUNDARY_RE.search(rest)
    sent_end = phrase_end + m.start() + 1 if m else len(turn_text)
    return sent_start, sent_end


def is_phrase_in_npc_speech(turn_text, phrase_start, phrase_end):
    """True if the trigger phrase falls inside quoted NPC speech."""
    quote_count = sum(1 for c in turn_text[:phrase_start] if c in '""""')
    if quote_count % 2 == 1:
        return True
    sent_start, _ = get_sentence_span(turn_text, phrase_start, phrase_end)
    same_sentence_pre = turn_text[sent_start:phrase_start]
    if NPC_VOICING_TAG.search(same_sentence_pre):
        return True
    if NPC_NAMED_SPEECH.search(same_sentence_pre):
        return True
    return False


def stage_0_phrase(turn_text, phrase_start, phrase_end, family,
                   episode_position_pct, turns, idx):
    """Classify a single candidate phrase.

    Returns (label, reason). label is "EVENT" (pass to Stage 1) or
    "DISCOURSE" (reject).
    """
    sent_start, sent_end = get_sentence_span(turn_text, phrase_start, phrase_end)
    sentence = turn_text[sent_start:sent_end]

    # D1: OOC scheduling / production talk.
    if DISCOURSE_OOC.search(sentence):
        return "DISCOURSE", "D1_ooc"

    # D4: Recap-state opening (position ≤ 3%, RECAP_VOCAB in preceding 15 turns).
    if episode_position_pct <= RECAP_EPISODE_POSITION_THRESHOLD:
        lookback_start = max(0, idx - 15)
        for j in range(lookback_start, idx + 1):
            if RECAP_VOCAB.search(turns[j]["text"]):
                return "DISCOURSE", "D4_recap_state"

    # D2: Trigger phrase inside NPC quoted speech — all families.
    # Compression triggers must be in Matt's narration voice. NPC_DEPARTURE
    # uses Matt's narration of the departure, not the NPC's farewell line.
    if is_phrase_in_npc_speech(turn_text, phrase_start, phrase_end):
        return "DISCOURSE", "D2_npc_voice"

    # D3: In-scene micro-motion (LOCATION_DEPARTURE only).
    if family == "LOCATION_DEPARTURE":
        if MICRO_MOTION_RE.search(sentence):
            return "DISCOURSE", "D3_micro_motion"

    return "EVENT", None


# ---------------------------------------------------------------------------
# State flags
# ---------------------------------------------------------------------------

COPIED_POSITIVE_INIT = re.compile(
    r"\b(?:re)?roll(?:s|ing|ed)?\s+(?:for\s+|some\s+)?initiative\b"
    r"|\binitiative\s+(?:has\s+(?:now\s+)?|now\s+)?kicked\s+in\b"
    r"|\b(?:now|we'?re)\s+in\s+initiative\b"
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

RECAP_POSITION_THRESHOLD_STATE = 0.10


def derive_combat_state(turns, candidate_idx):
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
    """Bounded ±15-turn lookback (Loot/Reward Phase 3.6 fix — not whole episode)."""
    if total_turns == 0:
        return False
    pos = candidate_idx / total_turns
    if pos > RECAP_POSITION_THRESHOLD_STATE:
        return False
    lookback_start = max(0, candidate_idx - 15)
    for j in range(lookback_start, candidate_idx + 1):
        if RECAP_VOCAB.search(turns[j]["text"]):
            return True
    return False


# ---------------------------------------------------------------------------
# Buildup signal detection
# ---------------------------------------------------------------------------

PLAYER_INTENT_RE = re.compile(
    r"\blet'?s\s+(?:head\s+out|leave|get\s+out|move\s+on|go\s+(?:now|then))\b"
    r"|\bi\s+think\s+we'?re\s+done\s+here\b"
    r"|\bwe\s+should\s+(?:move\s+on|leave|go)\b"
    r"|\bi\s+want\s+to\s+(?:leave|go|head\s+out)\b"
    r"|\bthere'?s\s+nothing\s+(?:more|else)\s+(?:here|for\s+us)\b",
    re.I,
)
NPC_RESOLUTION_RE = re.compile(
    r"\byou\s+have\s+my\s+(?:thanks|gratitude)\b"
    r"|\bi\s+(?:owe|will\s+owe)\s+you\b"
    r"|\bjob\s+(?:is\s+)?done\b"
    r"|\btask\s+(?:is\s+)?(?:done|complete|completed)\b"
    r"|\b(?:purpose|mission|objective)\s+(?:has\s+been\s+)?(?:fulfilled|completed|achieved)\b",
    re.I,
)
OBJECTIVE_COMPLETION_RE = re.compile(
    r"\byou(?:'?ve|ve)?\s+(?:got|found|retrieved|recovered|completed)\s+(?:what|it|all|everything)\b"
    r"|\byou\s+have\s+what\s+you\s+came\s+for\b"
    r"|\b(?:we|you)\s+have\s+what\s+(?:we|you)\s+came\s+for\b"
    r"|\byou'?ve\s+succeeded\b",
    re.I,
)
STALE_SIGNAL_RE = re.compile(
    r"\bwhat\s+(?:do\s+you|would\s+you\s+like\s+to)\s+(?:do|want\s+to\s+do)\b"
    r"|\bis\s+there\s+anything\s+else\s*\?"
    r"|\banything\s+else\s+(?:here|you\s+(?:want|need)\s+to\s+do)\b"
    r"|\banything\s+you\s+(?:want|wish)\s+to\s+do\s+(?:here|while)\b"
    r"|\bwhat\s+else\s+(?:do\s+you\s+(?:want\s+to\s+do|have)\s*)?\?",
    re.I,
)


def derive_buildup_signal(turns, trigger_idx, lookback=BUILDUP_LOOKBACK_TURNS):
    """Check preceding turns for buildup signal. Returns (signal, window_turns)."""
    start = max(0, trigger_idx - lookback)
    trigger_turn_number = turns[trigger_idx]["number"]
    stale_count = 0
    for j in range(trigger_idx - 1, start - 1, -1):
        t = turns[j]
        if t["speaker"] != "MATT" and PLAYER_INTENT_RE.search(t["text"]):
            dist = trigger_turn_number - t["number"]
            return "player_intent", dist
        if t["speaker"] == "MATT":
            if NPC_RESOLUTION_RE.search(t["text"]):
                dist = trigger_turn_number - t["number"]
                return "npc_resolution", dist
            if OBJECTIVE_COMPLETION_RE.search(t["text"]):
                dist = trigger_turn_number - t["number"]
                return "objective_completion", dist
            if STALE_SIGNAL_RE.search(t["text"]):
                stale_count += 1
    if stale_count >= 2:
        return "repeated_stale_signal", lookback
    return "matt_initiated", 0


def count_stale_signals_preceding(turns, trigger_idx, window=STALE_SIGNAL_WINDOW):
    """Count STALE_SIGNAL hits in the preceding window turns (Matt turns only)."""
    start = max(0, trigger_idx - window)
    return sum(
        1 for j in range(start, trigger_idx)
        if turns[j]["speaker"] == "MATT" and STALE_SIGNAL_RE.search(turns[j]["text"])
    )


# ---------------------------------------------------------------------------
# Compression scope (sketch — §13.7)
# ---------------------------------------------------------------------------

_SHORT_DURATION_RE = re.compile(r"\b(?:minute|hour)s?\b", re.I)
_LONG_DURATION_RE = re.compile(r"\b(?:day|week|month|year)s?\b", re.I)


def derive_compression_scope(category, trigger_phrase):
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


# ---------------------------------------------------------------------------
# Time-Mention overlap check (§13.4)
# ---------------------------------------------------------------------------

def load_tm_turn_numbers(episode_id):
    """Return set of trigger_turn_numbers from the TM output file, or empty."""
    path = TM_OUTPUT_DIR / f"{episode_id}.json"
    if not path.exists():
        return set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            records = json.load(f)
        return {r["trigger_turn_number"] for r in records if "trigger_turn_number" in r}
    except (OSError, json.JSONDecodeError, KeyError):
        return set()


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
        pre_reversed.append({
            "speaker": t["speaker"],
            "text": t["text"],
            "turn_number": t["number"],
        })
        used += text_len
    return list(reversed(pre_reversed)), used


# ---------------------------------------------------------------------------
# Episode loading (same source format as loot_reward.py)
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
                text = " ".join(str(u) for u in utterances) if isinstance(utterances, list) else str(utterances)
                turns_by_num[n] = {"speaker": speaker, "text": text, "number": n}

    return [turns_by_num[n] for n in sorted(turns_by_num)]


# ---------------------------------------------------------------------------
# Candidate phrase collection and dedup
# ---------------------------------------------------------------------------

def collect_phrase_candidates(turn_text):
    """Return list of (family, start, end, phrase_text), sorted by start."""
    out = []
    for family, pattern in TRIGGER_FAMILIES:
        for m in pattern.finditer(turn_text):
            out.append((family, m.start(), m.end(), m.group(0)))
    out.sort(key=lambda x: (x[1], x[2]))
    return out


def dedup_phrase_candidates(candidates):
    """Suppress overlapping candidates; highest-priority family wins on overlap."""
    if not candidates:
        return candidates
    survivors = []
    for c in candidates:
        family, s, e, phrase = c
        collide = False
        for kept in survivors:
            kf, ks, ke, _ = kept
            if s < ke and e > ks:
                # Overlap — keep higher priority (lower number wins).
                if CATEGORY_PRIORITY.get(family, 99) < CATEGORY_PRIORITY.get(kf, 99):
                    survivors.remove(kept)
                    survivors.append(c)
                collide = True
                break
        if not collide:
            survivors.append(c)
    survivors.sort(key=lambda x: x[1])
    return survivors


# ---------------------------------------------------------------------------
# Q6: STALE_HOLD_CANDIDATE detection (post-turn-processing pass)
# ---------------------------------------------------------------------------

def find_stale_hold_candidates(turns, compression_turn_numbers):
    """Find stale signal clusters (≥3 in 30-turn window) with no compression
    follow-through within 20 turns. Returns list of (cluster_end_idx, count)."""
    stale_indices = [
        i for i, t in enumerate(turns)
        if t["speaker"] == "MATT" and STALE_SIGNAL_RE.search(t["text"])
    ]
    candidates = []
    for i, end_idx in enumerate(stale_indices):
        window_start_num = turns[end_idx]["number"] - STALE_SIGNAL_WINDOW
        cluster = [
            j for j in stale_indices
            if turns[j]["number"] >= window_start_num
            and turns[j]["number"] <= turns[end_idx]["number"]
        ]
        if len(cluster) < STALE_CLUSTER_THRESHOLD:
            continue
        # Check for compression follow-through within 20 turns.
        follow_end_num = turns[end_idx]["number"] + STALE_FOLLOW_THROUGH_WINDOW
        has_follow_through = any(
            n >= turns[end_idx]["number"] and n <= follow_end_num
            for n in compression_turn_numbers
        )
        if not has_follow_through:
            candidates.append((end_idx, len(cluster)))
    # Dedup: suppress candidates whose cluster overlaps a prior candidate's window.
    seen_end = set()
    deduped = []
    for end_idx, count in candidates:
        if end_idx not in seen_end:
            deduped.append((end_idx, count))
            for j in range(
                max(0, end_idx - STALE_SIGNAL_WINDOW), end_idx + 1
            ):
                seen_end.add(j)
    return deduped


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
    tm_turn_numbers = load_tm_turn_numbers(episode_id)
    records = []
    compression_turn_numbers = set()

    for idx, t in enumerate(turns):
        if t["speaker"] != "MATT":
            continue

        candidates = collect_phrase_candidates(t["text"])
        if not candidates:
            continue

        candidates = dedup_phrase_candidates(candidates)

        is_combat_state = derive_combat_state(turns, idx)
        is_recap_state = derive_recap_state(turns, idx, total_turns)
        if is_recap_state:
            continue

        preceding_turns, preceding_chars = gather_preceding_context(
            turns, idx, PRECEDING_CONTEXT_BUDGET
        )
        episode_position_pct = round(idx / total_turns, 4) if total_turns else 0.0
        time_mention_overlap = t["number"] in tm_turn_numbers

        stale_count = count_stale_signals_preceding(turns, idx)
        buildup_signal, buildup_window_turns = derive_buildup_signal(turns, idx)

        same_turn_idx = 0
        for family, s, e, phrase in candidates:
            stage_0, reason = stage_0_phrase(
                t["text"], s, e, family, episode_position_pct, turns, idx
            )
            if stage_0 == "DISCOURSE":
                log_filtered_discourse(t["text"], reason, episode_id, t["number"])
                continue

            compression_scope = derive_compression_scope(family, phrase)
            surface_form = CATEGORY_TO_SURFACE_FORM.get(family, "unknown")

            record = {
                # Required CORPUS_BUILDER fields.
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
                "compression_category": family,
                "surface_form": surface_form,
                "compression_scope": compression_scope,
                "buildup_signal": buildup_signal,
                "buildup_window_turns": buildup_window_turns,
                "is_recap_state": False,
                "is_combat_state": is_combat_state,
                "time_mention_overlap": time_mention_overlap,
                "stale_signal_count_preceding": stale_count,
                "same_turn_record_index": same_turn_idx,
                "preceding_turns": preceding_turns,
            }
            records.append(record)
            compression_turn_numbers.add(t["number"])
            same_turn_idx += 1

    # Q6 pass: emit STALE_HOLD_CANDIDATE records for stale clusters without
    # compression follow-through.
    stale_hold_candidates = find_stale_hold_candidates(turns, compression_turn_numbers)
    for end_idx, cluster_count in stale_hold_candidates:
        t = turns[end_idx]
        episode_position_pct = round(end_idx / total_turns, 4) if total_turns else 0.0
        preceding_turns, preceding_chars = gather_preceding_context(
            turns, end_idx, PRECEDING_CONTEXT_BUDGET
        )
        records.append({
            "campaign": campaign,
            "episode": episode_num,
            "episode_position_pct": episode_position_pct,
            "speaker": t["speaker"],
            "event_type": "compression_cadence",
            "raw_text": t["text"],
            "preceding_context_chars": preceding_chars,
            "extractor_version": EXTRACTOR_VERSION,
            "extracted_at": extracted_at,
            "trigger_turn_number": t["number"],
            "trigger_phrase": STALE_SIGNAL_RE.search(t["text"]).group(0),
            "compression_category": "STALE_HOLD_CANDIDATE",
            "surface_form": "stale_hold",
            "compression_scope": "UNKNOWN",
            "buildup_signal": "repeated_stale_signal",
            "buildup_window_turns": STALE_SIGNAL_WINDOW,
            "is_recap_state": False,
            "is_combat_state": derive_combat_state(turns, end_idx),
            "time_mention_overlap": t["number"] in tm_turn_numbers,
            "stale_signal_count_preceding": cluster_count,
            "same_turn_record_index": 0,
            "preceding_turns": preceding_turns,
        })

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
    for ep in SAMPLE_EPISODES:
        records = process_episode(ep, extracted_at)
        out_path = OUTPUT_DIR / f"{ep}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, ensure_ascii=False)
        total += len(records)
        print(f"  {ep}: {len(records)} record(s) → {out_path}")

    print(f"\nSAMPLE_COMPLETE: episodes={len(SAMPLE_EPISODES)} records={total}")
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
            print(f"  [{i}/{len(episodes)}] processed, running record total: {total}")
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
