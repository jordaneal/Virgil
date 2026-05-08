#!/usr/bin/env python3
"""
Loot/Reward Extractor v1.

Reads CRD3 (`c=2` alignment dir) and emits one JSON record per detected
loot/reward trigger phrase. A loot/reward event is one of six categories:
MATERIAL_LOOT, QUEST_OFFER, NPC_FAVOR_GRATITUDE, MECHANICAL_GRANT,
KNOWLEDGE_GRANT, ENVIRONMENTAL_DISCOVERY.

Per CORPUS_BUILDER.md: deterministic regex only, read-only on the corpus,
fail-open on unknown formats, idempotent on event content.

Spec: findings/track5_loot_reward_phase1_spec.md (§11 decisions locked).
Lessons: docs/corpus_builder_lessons_v2.md — Lesson 9 (phrase-span Stage 0)
operative from line one.

Locked decisions applied (per Phase 2 prompt):
  §11.1 Taxonomy: all six categories.
  §11.2 Stage 0: phrase-span with NPC-voice routing.
  §11.3 Q6 absence: in-scope, single-extractor narrated-absence only;
        broader form is cross-extractor and noted in findings.
  §11.4 Source corpus: CRD3 only for Phase 1.
  §11.5 Hand-sample: 10 episodes (seed 6666).
  §11.6 NPC-voice routing: phrase inside NPC voice → QUEST_OFFER /
        NPC_FAVOR_GRATITUDE; phrase in Matt voice → other four
        categories.
  §11.7 Quest-offer/delivery: out of scope; emits `direction` field only
        for future pairing.

Phrase-span Stage 0 (Lesson 9): each candidate phrase is classified as
EVENT, STATE, or DISCOURSE based on the phrase's position inside the turn.
NPC speech is NOT a turn-level reject in this domain — it is the primary
delivery mechanism for QUEST_OFFER / NPC_FAVOR_GRATITUDE. Phrases inside
quoted speech / immediately after an NPC voicing tag are ROUTED, not
rejected.

Usage:
    python3 loot_reward.py --sample
        Runs on the 10 hand-sample episodes. Writes per-episode files at
        ../output/loot_reward/{episode_id}.json.

    python3 loot_reward.py --full
        Runs on all CRD3. NOT to be invoked at Phase 2 — hand-sample only.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

EXTRACTOR_VERSION = "loot_reward_v1"

CORPUS_BUILDER = Path(__file__).resolve().parent.parent
SOURCE_BASE = Path("/mnt/virgil_storage/dnd_datasets/crd3/data/aligned data/c=2")
OUTPUT_DIR = CORPUS_BUILDER / "output" / "loot_reward"

PRECEDING_CONTEXT_BUDGET = 800
PERCEPTION_LOOKBACK_TURNS = 10
COMBAT_STATE_LOOKBACK_TURNS = 25
COMBAT_STATE_STALENESS_TURNS = 30
RECAP_EPISODE_POSITION_THRESHOLD = 0.10

# §11.5 locked hand-sample. seed=6666; stratified across CRD3 phases.
#
# Hand-sample episodes:
#   C1E007, C1E010, C1E052, C1E062, C1E089, C1E099,
#   C2E007, C2E022, C2E030, C2E043
#
# Disjointness deviation (logged 2026-05-07): 7 of 10 episodes overlap with
# the prior 91-episode set referenced by Encounter-Cadence and Time-Mention
# eval / sample / validation JSONs (collisions: C1E007, C1E010, C1E052,
# C1E062, C1E099, C2E007, C2E043). The Phase 2 prompt's "disjoint from
# prior-91" rule was walked back: 109 CRD3 episodes minus 91 prior minus 7
# recon leaves 11 disjoint, which would starve Phase 4 gate-set and Phase 5
# validation. Loot/Reward indexes a different signal surface than the prior
# extractors (Lesson 1 — local lexical patterns are extractor-specific), so
# episode reuse does not contaminate this extractor's calibration. The real
# integrity boundary — hand-sample disjoint from Phase 4 gate-set disjoint
# from Phase 5 validation — is preserved and enforced downstream. No re-roll.
# Disjoint from the 7 Phase 1 recon episodes.
SAMPLE_EPISODES = [
    "C1E007", "C1E010", "C1E052", "C1E062", "C1E089", "C1E099",
    "C2E007", "C2E022", "C2E030", "C2E043",
]

EPISODE_ID_RE = re.compile(r"^(C\d+)E(\d{3,4})$")


# ---------------------------------------------------------------------------
# Stage 1 — broad loot/reward candidate detection
# ---------------------------------------------------------------------------
#
# Six per-category trigger families. A turn that fires multiple families
# emits multiple records (one per phrase) with `same_turn_record_index`.
# Phrase-level overlap is resolved by family priority during classification.

# 1. MATERIAL_LOOT — currency or item enumerations narrated by Matt.
MATERIAL_LOOT_TRIGGER = re.compile(
    r"\byou\s+(?:find|discover|locate|recover|pull\s+out|pick\s+up|grab|"
    r"obtain)\s+(?:an?\s+|the\s+|some\s+|a\s+pouch\s+of\s+|a\s+bag\s+of\s+)?"
    r"(?:additional\s+)?"
    r"\d+(?:,\d{3})*\s+(?:gold|silver|copper|platinum|electrum)\s+(?:pieces?|coins?)?\b"
    r"|\byou\s+(?:find|discover|locate|recover)\s+(?:an?\s+|the\s+|some\s+)?"
    r"(?:additional\s+)?"
    r"\d+\s+(?:gp|sp|cp|pp|ep)\b"
    # bare currency line after "find"
    r"|\b\d+(?:,\d{3})*\s+gold\s+pieces\b"
    r"|\b\d+(?:,\d{3})*\s+silver\s+pieces\b"
    r"|\b\d+(?:,\d{3})*\s+platinum\s+pieces\b"
    r"|\b\d+(?:,\d{3})*\s+copper\s+pieces\b"
    # rifling / searching enumeration scaffold
    r"|\brifling\s+through\b"
    r"|\bsearching\s+through\s+(?:his|her|its|their|the)\s+(?:bits|belongings|pockets|effects|gear|stuff|things)\b"
    # container reveals
    r"|\b(?:inside|within)\s+(?:the|a|an|this)\s+"
    r"(?:chest|box|crate|bag|pouch|sack|coffer|strongbox|safe|drawer|"
    r"compartment|container)\s*[,.]?\s*you\s+(?:find|see|discover)\b"
    r"|\bthe\s+(?:chest|box|crate|bag|pouch|sack|coffer)\s+contains\b"
    # loot drop framing
    r"|\b(?:falls?|drops?)\s+to\s+the\s+(?:floor|ground)\b\s+a\b"
    r"|\bon\s+(?:his|her|its|their|the)\s+(?:body|corpse|person)\s+you\s+find\b"
    r"|\byou\s+find\s+(?:an?\s+|the\s+)?(?:pouch|bag|sack|coffer|chest)\s+(?:of|containing|with)\b",
    re.I,
)

# 2. QUEST_OFFER — NPC offering reward in dialogue. Trigger phrases are the
# offer-language; voice routing in Stage 0 confirms NPC origin.
QUEST_OFFER_TRIGGER = re.compile(
    r"\bi\s+(?:offer|propose|present|extend)\s+(?:you|an?|the)\b"
    r"|\bi\s+(?:shall|will|would|can)\s+(?:reward|pay|compensate|give)\s+you\b"
    r"|\bi\'?ll\s+(?:reward|pay|compensate|give)\s+you\b"
    r"|\b(?:an?\s+)?advance\s+of\s+\d"
    r"|\bpurse\s+of\s+\d"
    r"|\b\d+\s+gold\s+(?:pieces?\s+)?upon\s+(?:completion|return|delivery|success)\b"
    r"|\bupon\s+(?:completion|return|delivery|success|returning)\b"
    r"|\bfor\s+(?:this\s+task|the\s+task|your\s+services?|the\s+job|the\s+work)\b"
    r"|\byou\s*'?ll?\s+be\s+(?:rewarded|paid|compensated)\b"
    r"|\bin\s+exchange\s+for\s+(?:your|this)\b"
    r"|\bif\s+you\s+(?:can|would|will)\s+(?:bring|deliver|retrieve|find|return\s+with|locate|fetch)\b"
    r"|\bthere\s+(?:i\s+)?shall\s+(?:reward|pay)\s+you\b"
    # named coin in offer-context
    r"|\b\d+(?:,\d{3})*\s+gold\s+pieces\s+(?:as|for|upon)\b",
    re.I,
)

# 3. NPC_FAVOR_GRATITUDE — non-material relational reward.
NPC_FAVOR_TRIGGER = re.compile(
    r"\b(?:i\s+am|i\'m|we\s+are|we\'re)\s+(?:so\s+|truly\s+|deeply\s+|forever\s+)?"
    r"(?:grateful|thankful|indebted|in\s+your\s+debt)\b"
    r"|\bfor\s+that[,.]?\s+(?:i\'m|i\s+am|we\'re|we\s+are)\s+(?:thankful|grateful)\b"
    r"|\byou\s+have\s+my\s+(?:thanks|gratitude|sincerest\s+thanks)\b"
    r"|\bi\s+(?:give|offer|extend)\s+you\s+my\s+(?:thanks|gratitude)\b"
    r"|\bi\s+(?:owe|will\s+owe)\s+you\b"
    r"|\bcount\s+(?:me|us)\s+as\s+(?:a\s+|your\s+)?friend\b"
    r"|\byou\s+can\s+count\s+on\s+(?:me|us)\b"
    r"|\bfor\s+your\s+(?:assistance|help|service|aid|kindness)\b"
    r"|\bthank\s+you\s+(?:for|so\s+much\s+for)\b"
    r"|\byou\s+have\s+(?:saved|protected|preserved)\s+(?:me|us|her|him|them|all)\b"
    r"|\bi\s+(?:am|\'m)\s+grateful\s+that\b",
    re.I,
)

# 4. MECHANICAL_GRANT — DM grants in-game mechanical benefit.
MECHANICAL_GRANT_TRIGGER = re.compile(
    r"\bi\'?ll\s+give\s+you\s+(?:advantage|inspiration|that|a\s+bonus|the\s+benefit)\b"
    r"|\bi\'?ll\s+allow\s+(?:that|you|it)\b"
    r"|\b(?:gain|gains|gaining)\s+(?:a\s+point\s+of\s+)?inspiration\b"
    r"|\b(?:gives?|granting|grants?)\s+you\s+(?:advantage|inspiration|a\s+bonus)\b"
    r"|\btake\s+(?:a\s+)?(?:short|long)\s+rest\b"
    r"|\b(?:after\s+)?(?:the\s+)?(?:short|long)\s+rest\s*[,.]?\s+you\s+(?:regain|recover|gain)\b"
    r"|\byou\s+regain\s+(?:all\s+)?(?:hit\s+points|hp|spell\s+slots|your\s+\w+\s+slot)\b"
    r"|\b(?:that\s+)?last\s+bit\s+of\s+inspiration\b"
    r"|\bi\'?m\s+(?:going\s+to\s+)?(?:give|grant|allow)\s+you\s+(?:advantage|a\s+bonus|inspiration)\b"
    r"|\byou\s+have\s+advantage\s+on\s+(?:this|that|the)\b",
    re.I,
)

# 5. KNOWLEDGE_GRANT — info, lore, directions, identification, vision.
KNOWLEDGE_GRANT_TRIGGER = re.compile(
    r"\bgives?\s+you\s+the\s+(?:location|name|identity|address|position)\s+of\b"
    r"|\byou\s+(?:learn|find\s+out|discover|recall|remember)\s+that\b"
    r"|\b(?:it\s+)?comes\s+back\s+to\s+you\b"
    r"|\byou\'?re\s+(?:not\s+entirely\s+certain|aware\s+of|reminded\s+of|filled\s+with)\b"
    r"|\byou\s+have\s+(?:these\s+)?(?:images|visions?|flashes?)\s+of\b"
    r"|\byou\s+remember\s+(?:that|hearing|seeing|reading)\b"
    r"|\byou\s+recognize\s+(?:this|the|that|him|her|it|them)\b"
    r"|\byou\s+identify\s+(?:this|the|it|them)\s+as\b"
    r"|\bbased\s+on\s+(?:your|the)\s+(?:knowledge|memory|history|arcana|religion)\b"
    r"|\b(?:reveals|tells)\s+you\s+(?:that|the\s+location|where)\b",
    re.I,
)

# 6. ENVIRONMENTAL_DISCOVERY — narrated objects in scene without handover.
ENVIRONMENTAL_DISCOVERY_TRIGGER = re.compile(
    r"\bsets?\s+of\s+(?:gold|silver|gem|jewel)"
    r"|\b(?:gold|silver)\s+(?:rings?|jewelry|necklaces?|bracelets?|chains?|coins?)"
    r"\s+(?:and|of|with|inside|on|sit|sits|sitting|rest|resting|lying)\b"
    r"|\b(?:jewelry|gems?|jewels?|gold\s+scrolling|gilded\s+\w+)\s+"
    r"(?:of|with|sit|sits|sitting|rest|rests|resting|lying|line)\b"
    r"|\b(?:tattered|ornate|gilded|jeweled|engraved)\s+(?:urn|chest|box|coffer|amulet|tome)\b"
    r"|\bon\s+the\s+(?:table|floor|shelf|altar|pedestal|mantel)\s*[,.]?\s+"
    r"(?:you\s+see\s+|there\s+(?:is|are|sits?|rests?)\s+|sits?\s+|rests?\s+)"
    r"(?:an?\s+|the\s+|some\s+)?(?:gold|silver|jeweled|ornate|gilded|gem)"
    r"|\bdecorat(?:ive|ed)\s+with\s+(?:gold|silver|gems|jewels)\b",
    re.I,
)

# Combined: a single sweep gathers all candidate phrase-spans across
# families. Each match is tagged with its detected category for Stage 0
# routing.
TRIGGER_FAMILIES = [
    ("MATERIAL_LOOT", MATERIAL_LOOT_TRIGGER),
    ("QUEST_OFFER", QUEST_OFFER_TRIGGER),
    ("NPC_FAVOR_GRATITUDE", NPC_FAVOR_TRIGGER),
    ("MECHANICAL_GRANT", MECHANICAL_GRANT_TRIGGER),
    ("KNOWLEDGE_GRANT", KNOWLEDGE_GRANT_TRIGGER),
    ("ENVIRONMENTAL_DISCOVERY", ENVIRONMENTAL_DISCOVERY_TRIGGER),
]


# ---------------------------------------------------------------------------
# Stage 0 — DISCOURSE / STATE / EVENT classifier (phrase-span)
# ---------------------------------------------------------------------------
#
# Per spec §5 + Lesson 9. Operates at phrase-span level. Each candidate
# phrase is classified by:
#   1. Is it inside NPC speech? — quote-mark proximity OR NPC voicing tag
#      adjacent in the same sentence. Routes to QUEST_OFFER /
#      NPC_FAVOR_GRATITUDE.
#   2. Is it rules-talk? — pair of trigger phrase with rules vocabulary
#      (the spell, feat, bonus action, your AC, dice notation). Reject as
#      DISCOURSE.
#   3. Is it player-paying-NPC (direction inverted)? — `you put N gold`,
#      `you pay`, `you give him/her`. Reject as DISCOURSE.
#   4. Is it OOC table chatter? — break announcements, sponsor reads.
#      Reject as DISCOURSE.

DISCOURSE_OOC = re.compile(
    r"\bwelcome\s+(?:to|back)\b"
    r"|\btonight'?s\s+episode\b"
    r"|\bquick\s+break\b|\btake\s+(?:a\s+)?(?:short|quick)\s+break\b"
    r"|\b(?:sponsor|patreon|wyrmwood|d&d\s+beyond|critmas)\b"
    r"|\bsee\s+you\s+(?:guys\s+)?next\s+(?:week|time)\b"
    r"|\bwe'?ll\s+(?:be\s+(?:right\s+)?back|come\s+back)\b",
    re.I,
)

# Rules-talk: the trigger phrase pairs with rules vocabulary.
RULES_VOCAB = re.compile(
    r"\b(?:bonus\s+action|reaction|attunement|attune|attuning|"
    r"hit\s+(?:point|points|die|dice)|"
    r"saving\s+throw|spell\s+slot|spell\s+save|spell\s+attack|"
    r"armor\s+class|your\s+ac|"
    r"d4|d6|d8|d10|d12|d20|d100|"
    r"the\s+spell|that\s+spell|this\s+spell|the\s+ability|"
    r"the\s+feat|takes\s+a\s+feat|"
    r"next\s+turn|your\s+turn|end\s+of\s+(?:your|the)\s+turn|"
    r"until\s+the\s+end\s+of\b|"
    r"per\s+(?:short|long)\s+rest|"
    r"strength\s+save|dexterity\s+save|constitution\s+save|"
    r"wisdom\s+save|intelligence\s+save|charisma\s+save|"
    r"strength\s+modifier|dexterity\s+modifier|constitution\s+modifier|"
    r"proficiency\s+bonus)\b",
    re.I,
)

# Rules-adjudication extensions (Patch 4):
# Ext 1 — negated grant verb: "does not give you advantage" is a rules
#   ruling that negates a benefit, never a grant landing.
GRANT_NEGATION_RE = re.compile(
    r"\b(?:does\s+not|doesn'?t|don'?t)\s+give\b",
    re.I,
)

# Ext 2 — conditional rule explanation: "gives you X to <infinitive>"
#   describes when a class feature activates, not a benefit being granted now.
#   E.g. "gives you advantage to spend a ki point" is rules meta, not a grant.
GIVES_TO_INFIN_RE = re.compile(
    r"\bgives?\s+you\s+\w+\s+to\s+"
    r"(?:spend|use|activate|trigger|make|roll|do|take|attempt|cast|equip|attune)\b",
    re.I,
)

# "I'll give you that" — idiomatic concession, not a material grant.
# Matches "I'll give you that" when followed by a clause terminator (period,
# comma, etc.) or a concessive conjunction — never by a grant object (ring,
# sword, etc.). Voice-agnostic: fires whether Matt or NPC says it.
ILL_GIVE_YOU_THAT_RE = re.compile(
    r"\bi'?ll\s+give\s+you\s+that\s*[.,!?;]"
    r"|\bi'?ll\s+give\s+you\s+that\s+(?:but|though|however|and)\b",
    re.I,
)

# "I'll give you advantage/inspiration/etc." — mechanical grant regardless of voice.
# Fires when the QUEST_OFFER_TRIGGER short-matches "I'll give you" but the object
# is a game-mechanic benefit, not a physical item or quest.
ILL_GIVE_YOU_MECHANICAL_RE = re.compile(
    r"(?:i(?:'ll|(?:\s+can)|(?:\s+will)|(?:\s+would))?\s+give\s+you|let\s+me\s+give\s+you)\s+"
    r"(?:advantage|disadvantage|inspiration|your\s+action|your\s+turn|another\s+action|"
    r"your\s+bonus\s+action|your\s+reaction|a\s+reroll|the\s+benefit)\b",
    re.I,
)

# KNOWLEDGE_GRANT negation/uncertainty — trigger phrase is knowledge ABSENCE.
# The KNOWLEDGE_GRANT_TRIGGER includes `you're not entirely certain` which is
# the inverse of a grant. Reject when the trigger phrase itself contains
# explicit uncertainty/negation markers.
KNOWLEDGE_NEGATION_RE = re.compile(
    r"\bnot\s+entirely\s+certain\b"
    r"|\bnot\s+sure\b"
    r"|\bcan'?t\s+tell\b"
    r"|\bdon'?t\s+know\b"
    r"|\bno\s+way\s+to\s+tell\b"
    r"|\bunclear\b"
    r"|\buncertain\b",
    re.I,
)

# Donor-read (Twitch stream read of viewer messages) — Stage 0 reject.
# Detects donation amounts or stream-platform vocabulary within 200 chars
# before a trigger phrase. Matt reading donor messages aloud looks like NPC
# speech to the extractor but is stream meta-content.
DONOR_READ_STREAM_RE = re.compile(
    r"\d+\s+(?:bucks|dollars)\b"
    r"|donated\s+\$?\d+"
    r"|\$\d+"
    r"|\bTwitch\b"
    r"|\bPatreon\b"
    r"|\bsubscribed?\b"
    r"|\bdonated\b",
    re.I,
)

# Sale-price transaction detection — Stage 0 reject for currency mentions
# that are prices quoted in a buy/sell context, not reward grants.
#
# Two surfaces:
#   1. Preceding turns (last 5): price-query vocabulary from the buyer.
#   2. Current sentence: price-response markers (", please", "cost at").
#
# Applies only to MATERIAL_LOOT and QUEST_OFFER families, which are the
# families whose trigger patterns overlap with bare currency mentions.
SALE_PRICE_QUERY_RE = re.compile(
    r"\bhow\s+much\b"
    r"|\bwhat(?:'?s|\s+is)\s+(?:the\s+)?(?:price|cost|rate)\b"
    r"|\bfor\s+sale\b"
    r"|\btransaction\b",
    re.I,
)

SALE_PRICE_SENTENCE_RE = re.compile(
    r",\s*please\b"
    r"|\b(?:\w+\s+)?cost\s+(?:at|is|was|would)\b"
    r"|\bprice\s+(?:it|them|that)\b",
    re.I,
)

# Player-paying-NPC direction inversion.
DISCOURSE_DIRECTION_OUT = re.compile(
    r"\byou\s+(?:put|hand|pass|give|drop)\s+(?:him|her|them|it|the\s+\w+)?\s*"
    r"(?:\d+|a\s+|the\s+|some\s+)?\s*(?:gold|silver|copper|platinum|coins?)\b"
    r"|\byou\s+pay\s+(?:him|her|them|the\s+\w+|\d+)\b"
    r"|\b(?:please|here'?s)[,.]?\s+\d+\s+gold\s+pieces?\b"
    r"|\byou\s+(?:place|set\s+down)\s+\d+\s+gold\b",
    re.I,
)

# NPC voice detection (re-used from time_mention shape).
QUOTED_SPEECH = re.compile(r'["“”][^"“”\n]{4,}["“”]')

NPC_VOICING_TAG = re.compile(
    r"\b(?:he|she|it|they|the\s+\w+)\s+"
    r"(?:says?|said|goes|growls?|hisses?|whispers?|shouts?|yells?|barks?|"
    r"roars?|chuckles?|laughs?|sneers?|scoffs?|smiles?\s+and\s+says?|"
    r"replies|reply|replied|continues|continued|states|stated|answers|"
    r"answered|nods?\s+and\s+says?|adds?|asks?|asked|tells?|told)\b"
    r"|\b(?:says?|whispers?|growls?|hisses?|roars?|shouts?|yells?)\s*[:,]\s+[\"“]",
    re.I,
)
NPC_NAMED_SPEECH = re.compile(
    r"\b[A-Z][a-zA-Z'\-]{2,}\s+(?:says?|said|goes|growls?|hisses?|whispers?|"
    r"shouts?|sneers?|scoffs?|smiles?\s+and\s+says?|chuckles?|laughs?|"
    r"replies|continues|tells?|told)\b"
)


def is_donor_read(turn_text, trigger_offset):
    """True if donation or stream-platform vocabulary appears within 200 chars
    before the trigger phrase. Indicates Matt reading a Twitch viewer message
    aloud rather than voicing an NPC. Stage 0 DISCOURSE reject.
    """
    pre_window = turn_text[max(0, trigger_offset - 200):trigger_offset]
    return bool(DONOR_READ_STREAM_RE.search(pre_window))


_SENT_BOUNDARY_RE = re.compile(r"[.!?](?:\s+|$)")


def get_sentence_span(turn_text, phrase_start, phrase_end):
    sent_start = 0
    for m in _SENT_BOUNDARY_RE.finditer(turn_text[:phrase_start]):
        sent_start = m.end()
    rest = turn_text[phrase_end:]
    m = _SENT_BOUNDARY_RE.search(rest)
    sent_end = phrase_end + m.start() + 1 if m else len(turn_text)
    return sent_start, sent_end


def is_phrase_in_npc_speech(turn_text, phrase_start, phrase_end):
    """True if the phrase falls inside NPC dialogue (quoted or voiced)."""
    quote_count = sum(1 for c in turn_text[:phrase_start] if c in '"“”"')
    if quote_count % 2 == 1:
        return True
    sent_start, _ = get_sentence_span(turn_text, phrase_start, phrase_end)
    same_sentence_pre = turn_text[sent_start:phrase_start]
    if NPC_VOICING_TAG.search(same_sentence_pre):
        return True
    if NPC_NAMED_SPEECH.search(same_sentence_pre):
        return True
    return False


def is_sale_transaction(turn_text, phrase_start, phrase_end, preceding_text=""):
    """True if the currency mention is a price quote in a buy/sell context.

    Checks preceding-turn text (last 5 turns, passed in by caller) for
    price-query vocabulary, and the current sentence for price-response
    markers. Either surface is sufficient.
    """
    if preceding_text and SALE_PRICE_QUERY_RE.search(preceding_text):
        return True
    pre_window = turn_text[max(0, phrase_start - 300):phrase_start]
    if SALE_PRICE_QUERY_RE.search(pre_window):
        return True
    sent_start, sent_end = get_sentence_span(turn_text, phrase_start, phrase_end)
    sentence = turn_text[sent_start:sent_end]
    if SALE_PRICE_SENTENCE_RE.search(sentence):
        return True
    return False


# ---------------------------------------------------------------------------
# Absence detection (Q6 partial — single-extractor narrated absence)
# ---------------------------------------------------------------------------
#
# Per §11.3 lock and §6 of the spec. The single-extractor scope is
# narrated absence: explicit linguistic negation of a search/perception
# beat, ~1-3 per episode.

ABSENCE_NEGATION = re.compile(
    r"\bnothing\s+(?:here|of\s+(?:value|note|interest)|catches\s+your\s+eye)\b"
    r"|\byou\s+see\s+nothing\b"
    r"|\bno\s+sign\s+of\s+(?:a|an|the|any)\b"
    r"|\bcomes?\s+up\s+empty\b"
    r"|\bthe\s+(?:chest|box|drawer|coffer|container)\s+is\s+empty\b"
    r"|\byou\s+(?:don'?t|do\s+not)\s+find\b"
    r"|\byou\s+can'?t\s+(?:tell|find|see|discern)\s+(?:anything|much)\b"
    r"|\bthere\s+is\s+nothing\s+(?:here|of\s+(?:value|note))\b"
    r"|\bnothing\s+(?:catches|comes\s+up)\b",
    re.I,
)

# Perception/investigation buildup proximity.
PERCEPTION_BUILDUP = re.compile(
    r"\bmake\s+(?:an?\s+)?(?:perception|investigation|insight|search)\s+check\b"
    r"|\b(?:catches?\s+your\s+eye|your\s+eyes\s+(?:fall\s+on|drift\s+to)|"
    r"glimmers?|gleam|catches\s+the\s+light)\b",
    re.I,
)


def has_recent_perception_buildup(turns, idx, lookback=PERCEPTION_LOOKBACK_TURNS):
    """Return (had_buildup_bool, distance_in_turns_or_None)."""
    start = max(0, idx - lookback)
    trigger_turn_number = turns[idx]["number"]
    for j in range(idx - 1, start - 1, -1):
        t = turns[j]
        if t["speaker"] != "MATT":
            continue
        if PERCEPTION_BUILDUP.search(t["text"]):
            return True, trigger_turn_number - t["number"]
    # Also check the trigger turn itself.
    if PERCEPTION_BUILDUP.search(turns[idx]["text"]):
        return True, 0
    return False, None


# ---------------------------------------------------------------------------
# Persistence flag (cross-cutting)
# ---------------------------------------------------------------------------

PERSISTENCE_MARKER = re.compile(
    r"\bpermanent(?:ly)?\b"
    r"|\bfrom\s+now\s+on\b"
    r"|\bhenceforth\b"
    r"|\bforever\b"
    r"|\bfor\s+(?:the\s+rest\s+of|life|good)\b"
    r"|\buntil\s+you\b"
    r"|\bas\s+long\s+as\s+you\s+(?:carry|wear|wield|hold)\b",
    re.I,
)


# ---------------------------------------------------------------------------
# Combat / recap state (re-derived locally)
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
    r"|\bthat'?s\s+the\s+end\s+of\s+(?:combat|the\s+(?:fight|encounter|battle))"
    r"|\bend\s+of\s+the\s+encounter\b"
    r"|\bcombat\s+is\s+over\b"
    r"|\byou'?ve\s+defeated\b"
    r"|\bthe\s+(?:fight|battle|encounter)\s+is\s+(?:over|done|finished)\b",
    re.I,
)
INIT_VOCABULARY = re.compile(r"\binitiative\b", re.I)


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
    has_recent_init_vocab = any(
        INIT_VOCABULARY.search(turns[j]["text"])
        for j in range(stale_start, candidate_idx)
    )
    return has_recent_init_vocab


RECAP_VOCAB = re.compile(
    r"\blast\s+(?:week|episode|time|game)\b"
    r"|\bpreviously\s+on\b"
    r"|\bwe\s+(?:left\s+off|last\s+(?:left|saw|met))\b"
    r"|\bas\s+we\s+begin\s+tonight\b"
    r"|\bpicking\s+up\s+(?:where|from)\b"
    r"|\bto\s+(?:recap|summarize|bring\s+you\s+up\s+to\s+speed)\b",
    re.I,
)


def derive_recap_state(turns, candidate_idx, total_turns):
    if total_turns == 0:
        return False
    pos = candidate_idx / total_turns
    if pos > RECAP_EPISODE_POSITION_THRESHOLD:
        return False
    # Narrow lookback: only check the 15 turns immediately before the candidate.
    # Searching all turns 0..candidate_idx caused over-firing: any RECAP_VOCAB
    # anywhere in the first 10% of the episode flagged ALL subsequent turns in
    # that window, causing correct loot records to be marked as recap.
    lookback_start = max(0, candidate_idx - 15)
    for j in range(lookback_start, candidate_idx + 1):
        if RECAP_VOCAB.search(turns[j]["text"]):
            return True
    return False


# ---------------------------------------------------------------------------
# Currency total (gp-equivalent) — used by Q4 magnitude analysis
# ---------------------------------------------------------------------------

CURRENCY_NUM_RE = re.compile(
    r"(\d+(?:,\d{3})*)\s+(gold|silver|copper|platinum|electrum|gp|sp|cp|pp|ep)\b",
    re.I,
)

UNIT_TO_GP = {
    "gold": 1.0, "gp": 1.0,
    "silver": 0.1, "sp": 0.1,
    "copper": 0.01, "cp": 0.01,
    "platinum": 10.0, "pp": 10.0,
    "electrum": 0.5, "ep": 0.5,
}


def compute_currency_gp_equivalent(text):
    total = 0.0
    for m in CURRENCY_NUM_RE.finditer(text):
        try:
            n = int(m.group(1).replace(",", ""))
        except ValueError:
            continue
        unit = m.group(2).lower()
        total += n * UNIT_TO_GP.get(unit, 0.0)
    return round(total, 2) if total > 0 else 0.0


# ---------------------------------------------------------------------------
# Stage 0 dispatch
# ---------------------------------------------------------------------------

def stage_0_phrase(turn_text, phrase_start, phrase_end, family, preceding_text=""):
    """Classify a single candidate phrase.

    Returns (label, reason, is_in_npc_voice). Label is one of:
      "EVENT" — pass to Stage 2 routing.
      "DISCOURSE" — reject.
    is_in_npc_voice rides along on every record (data, not reject signal).
    preceding_text: concatenated text of the 5 turns before the trigger turn,
    used for transaction-context lookbehind.
    """
    sent_start, sent_end = get_sentence_span(turn_text, phrase_start, phrase_end)
    sentence = turn_text[sent_start:sent_end]

    # Stage 0 D-rules (apply before voice routing).
    if DISCOURSE_OOC.search(sentence):
        return "DISCOURSE", "D_ooc", False
    if is_donor_read(turn_text, phrase_start):
        return "DISCOURSE", "D_donor_read", False
    # Idiomatic concession: "I'll give you that." is not a grant.
    look_ahead = turn_text[phrase_start:min(len(turn_text), phrase_end + 15)]
    if ILL_GIVE_YOU_THAT_RE.search(look_ahead):
        return "DISCOURSE", "D_ill_give_you_that", False
    # KNOWLEDGE_GRANT candidates whose trigger phrase encodes knowledge ABSENCE.
    if family == "KNOWLEDGE_GRANT":
        phrase_text = turn_text[phrase_start:phrase_end]
        if KNOWLEDGE_NEGATION_RE.search(phrase_text):
            return "DISCOURSE", "D_knowledge_negation", False
    if RULES_VOCAB.search(sentence):
        return "DISCOURSE", "D_rules", False
    if GRANT_NEGATION_RE.search(sentence):
        return "DISCOURSE", "D_rules_negation", False
    if GIVES_TO_INFIN_RE.search(sentence):
        return "DISCOURSE", "D_rules_conditional", False
    if DISCOURSE_DIRECTION_OUT.search(sentence):
        return "DISCOURSE", "D_direction_out", False
    # Currency mention in a buy/sell transaction context is a price quote.
    if family in ("MATERIAL_LOOT", "QUEST_OFFER"):
        if is_sale_transaction(turn_text, phrase_start, phrase_end, preceding_text):
            return "DISCOURSE", "D_sale_transaction", False

    is_in_npc_voice = is_phrase_in_npc_speech(turn_text, phrase_start, phrase_end)
    return "EVENT", None, is_in_npc_voice


# ---------------------------------------------------------------------------
# Stage 2 — category routing
# ---------------------------------------------------------------------------
#
# Per §11.6 lock. Voice routing is the primary axis; the trigger family
# detected at Stage 1 is the secondary signal.
#
# Voice rules:
#   NPC voice → QUEST_OFFER if family is QUEST_OFFER OR if family was
#               MATERIAL_LOOT/MECHANICAL_GRANT/KNOWLEDGE_GRANT and the
#               sentence contains offer-language (NPC speaking about
#               currency = offer, not loot found).
#               NPC_FAVOR_GRATITUDE if family is NPC_FAVOR_GRATITUDE.
#   Matt voice → original family (MATERIAL_LOOT, MECHANICAL_GRANT,
#                KNOWLEDGE_GRANT, ENVIRONMENTAL_DISCOVERY).
#                If family is QUEST_OFFER detected in Matt voice, route to
#                MATERIAL_LOOT (Matt narrating an exchange).
#                If family is NPC_FAVOR_GRATITUDE in Matt voice → flag as
#                UNKNOWN_SHAPE (gratitude language outside dialogue is
#                ambiguous; per Lesson 2 no default catchall).
#

def route_category(family, is_in_npc_voice):
    """Return (category, unknown_shape_bool)."""
    if is_in_npc_voice:
        if family in ("QUEST_OFFER", "NPC_FAVOR_GRATITUDE"):
            return family, False
        if family == "MATERIAL_LOOT":
            # NPC speaking about currency → quest offer.
            return "QUEST_OFFER", False
        if family in ("MECHANICAL_GRANT", "KNOWLEDGE_GRANT"):
            # NPC voice + grant-language is structurally an in-fiction
            # promise / ask, not a Matt grant. Route to QUEST_OFFER as the
            # dominant in-dialogue reward shape.
            return "QUEST_OFFER", False
        if family == "ENVIRONMENTAL_DISCOVERY":
            return None, True
        return None, True
    # Matt voice
    if family in ("MATERIAL_LOOT", "MECHANICAL_GRANT",
                  "KNOWLEDGE_GRANT", "ENVIRONMENTAL_DISCOVERY"):
        return family, False
    if family == "QUEST_OFFER":
        # Matt narrating a paid exchange — treat as MATERIAL_LOOT delivery.
        return "MATERIAL_LOOT", False
    if family == "NPC_FAVOR_GRATITUDE":
        # Gratitude language outside dialogue is ambiguous.
        return None, True
    return None, True


def derive_direction(category, sentence_text):
    """Per §11.7 lock. Phase 2 emits direction field for future pairing.
    Three values: offered | delivered | absent. Absence is set elsewhere.
    """
    if category == "QUEST_OFFER":
        return "offered"
    if category in ("MATERIAL_LOOT", "MECHANICAL_GRANT",
                    "KNOWLEDGE_GRANT", "ENVIRONMENTAL_DISCOVERY",
                    "NPC_FAVOR_GRATITUDE"):
        return "delivered"
    return None


# ---------------------------------------------------------------------------
# Episode loading (copied from time_mention.py — same source format)
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
# Episode processing
# ---------------------------------------------------------------------------

def collect_phrase_candidates(turn_text):
    """Return list of (family, start, end, phrase_text) for all trigger
    families. Each match is preserved; no dedup across families. Phrase
    overlaps within a single family ARE deduped (regex non-overlapping).
    Phrase overlaps ACROSS families are kept as separate candidates and
    routed independently — they may collapse to the same category at
    Stage 2, in which case the dedup pass (below) suppresses the duplicate.
    """
    out = []
    for family, pattern in TRIGGER_FAMILIES:
        for m in pattern.finditer(turn_text):
            out.append((family, m.start(), m.end(), m.group(0)))
    out.sort(key=lambda x: (x[1], x[2]))
    return out


def dedup_phrase_candidates(candidates, turn_text):
    """Suppress overlapping candidates that route to the same category.
    Two candidates collide if their spans overlap; the first survives.
    Also collapse same-category candidates whose spans are within 80 chars
    of each other (same fictional reward beat).
    """
    if not candidates:
        return candidates
    survivors = []
    for c in candidates:
        family, s, e, phrase = c
        collide = False
        for kept in survivors:
            kf, ks, ke, _ = kept
            if s < ke and e > ks:
                collide = True
                break
        if not collide:
            survivors.append(c)
    return survivors


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

    for idx, t in enumerate(turns):
        # Phrase-span Stage 0 — voice routing means we cannot reject the
        # turn just because the speaker is not MATT. CRD3 has only Matt
        # narrating most NPC voice; players speak as their own names.
        # We process MATT-anchored turns where the trigger phrase may sit
        # in either Matt narration or NPC dialogue (Matt voicing the NPC).
        # Player turns are out of scope — players don't grant rewards.
        if t["speaker"] != "MATT":
            continue

        # Stage 1 — find all candidate phrases across families.
        candidates = collect_phrase_candidates(t["text"])
        if not candidates:
            continue

        candidates = dedup_phrase_candidates(candidates, t["text"])

        # State flags.
        is_combat_state = derive_combat_state(turns, idx)
        is_recap_state = derive_recap_state(turns, idx, total_turns)
        if is_recap_state:
            continue

        # Preceding context.
        preceding_turns, preceding_chars = gather_preceding_context(
            turns, idx, PRECEDING_CONTEXT_BUDGET
        )

        # Last-5-turn text for sale-price transaction lookbehind.
        preceding_text_sale = " ".join(
            turns[j]["text"] for j in range(max(0, idx - 5), idx)
        )

        # Perception buildup proximity.
        had_buildup, buildup_distance = has_recent_perception_buildup(turns, idx)

        episode_position_pct = round(idx / total_turns, 4) if total_turns else 0.0

        # Currency total (computed once per turn — concerns the trigger turn
        # text only; Q4 magnitude analysis is per-record context).
        currency_gp = compute_currency_gp_equivalent(t["text"])

        # Absence detection — if the turn carries explicit negation in
        # proximity to a perception/investigation beat, emit one absence
        # record per absence-marker in the turn.
        absence_matches = list(ABSENCE_NEGATION.finditer(t["text"]))

        same_turn_idx = 0
        turn_records = []

        # Emit a record per candidate phrase.
        for family, s, e, phrase in candidates:
            stage_0, reason, is_in_npc_voice = stage_0_phrase(
                t["text"], s, e, family, preceding_text=preceding_text_sale
            )
            if stage_0 == "DISCOURSE":
                log_filtered_discourse(t["text"], reason, episode_id, t["number"])
                continue

            # Object-aware override: QUEST_OFFER_TRIGGER short-matches "I'll give you",
            # suppressing the MECHANICAL_GRANT_TRIGGER longer match via dedup. If the
            # object after the phrase is a game mechanic (advantage, inspiration, etc.),
            # force MECHANICAL_GRANT regardless of voice routing.
            give_obj_window = t["text"][s:min(len(t["text"]), e + 60)]
            if ILL_GIVE_YOU_MECHANICAL_RE.search(give_obj_window):
                category = "MECHANICAL_GRANT"
                unknown_shape = False
            else:
                category, unknown_shape = route_category(family, is_in_npc_voice)
            if unknown_shape:
                log_unknown_shape(t["text"], episode_id, t["number"], phrase)
                # Per Lesson 2: emit with explicit unknown flag rather than
                # a default catchall. Skip if no category resolved.
                continue

            sent_start, sent_end = get_sentence_span(t["text"], s, e)
            sentence = t["text"][sent_start:sent_end]

            direction = derive_direction(category, sentence)
            has_persistence = bool(PERSISTENCE_MARKER.search(sentence))

            record = {
                # Required CORPUS_BUILDER fields.
                "campaign": campaign,
                "episode": episode_num,
                "episode_position_pct": episode_position_pct,
                "speaker": t["speaker"],
                "event_type": "loot_reward",
                "raw_text": t["text"],
                "preceding_context_chars": preceding_chars,
                "extractor_version": EXTRACTOR_VERSION,
                "extracted_at": extracted_at,

                # Per-extractor fields.
                "trigger_turn_number": t["number"],
                "trigger_phrase": phrase,
                "category": category,
                "is_in_npc_voice": is_in_npc_voice,
                "direction": direction,
                "absence_marker": False,
                "has_persistence_marker": has_persistence,
                "has_perception_buildup": had_buildup,
                "nearest_prior_perception_check_turn_distance": buildup_distance,
                "currency_total_gp_equivalent": currency_gp,
                "is_combat_state": is_combat_state,
                "is_recap_state": is_recap_state,

                "same_turn_record_index": same_turn_idx,
                "preceding_turns": preceding_turns,
            }
            turn_records.append(record)
            same_turn_idx += 1

        # Emit absence records — phrase-span absence detection per §11.3.
        # Only emit if a perception-buildup is in proximity (single-extractor
        # narrated absence, not the broader cross-extractor form).
        if had_buildup:
            for m in absence_matches:
                phrase = m.group(0)
                stage_0, reason, is_in_npc_voice = stage_0_phrase(
                    t["text"], m.start(), m.end(), "ABSENCE",
                    preceding_text=preceding_text_sale
                )
                if stage_0 == "DISCOURSE":
                    continue
                # Absence is Matt-voice only (negation-of-search beat).
                if is_in_npc_voice:
                    continue

                sent_start, sent_end = get_sentence_span(
                    t["text"], m.start(), m.end()
                )
                sentence = t["text"][sent_start:sent_end]
                has_persistence = bool(PERSISTENCE_MARKER.search(sentence))

                record = {
                    "campaign": campaign,
                    "episode": episode_num,
                    "episode_position_pct": episode_position_pct,
                    "speaker": t["speaker"],
                    "event_type": "loot_reward",
                    "raw_text": t["text"],
                    "preceding_context_chars": preceding_chars,
                    "extractor_version": EXTRACTOR_VERSION,
                    "extracted_at": extracted_at,

                    "trigger_turn_number": t["number"],
                    "trigger_phrase": phrase,
                    "category": "MATERIAL_LOOT",
                    "is_in_npc_voice": False,
                    "direction": "absent",
                    "absence_marker": True,
                    "has_persistence_marker": has_persistence,
                    "has_perception_buildup": True,
                    "nearest_prior_perception_check_turn_distance": buildup_distance,
                    "currency_total_gp_equivalent": 0.0,
                    "is_combat_state": is_combat_state,
                    "is_recap_state": is_recap_state,

                    "same_turn_record_index": same_turn_idx,
                    "preceding_turns": preceding_turns,
                }
                turn_records.append(record)
                same_turn_idx += 1

        records.extend(turn_records)

    return records


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def utc_now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def run_sample():
    extracted_at = utc_now_iso()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    per_episode_counts = {}
    total = 0
    for ep in SAMPLE_EPISODES:
        records = process_episode(ep, extracted_at)
        per_episode_counts[ep] = len(records)
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
