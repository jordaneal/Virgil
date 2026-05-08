#!/usr/bin/env python3
"""
Time-Mention Extractor v1.

Reads CRD3 (`c=2` alignment dir, MATT-anchored) and emits one JSON record per
detected time-mention phrase. A time-mention is Matt narrating a quantity of
in-fiction time elapsing (in_scene_compression, travel_duration), a discrete
scene break (scene_transition), or an anchor-establishing assertion of how
much time has passed or what time-of-day it currently is (cumulative_anchor).

Per CORPUS_BUILDER.md: deterministic regex only, read-only on the corpus,
fail-open on unknown formats, idempotent on event content.

Spec: TIME_MENTION_V1_SPEC.md (Phase 1 doc) + chat-locked decisions applied
in this implementation. See `corpus_builder_lessons_v1.md` for the cross-
extractor architectural rules baked into the pipeline below (Stage 0 layer,
no-default-catchall, FP-family taxonomy, dual held-out methodology).

Locked decisions applied (per Phase 2 prompt):
  §11.1  Granularity scope is minutes-and-up only. The seconds band is
         dropped from Stage 1 candidate detection entirely. T20-style
         sub-minute beats are accepted as a known v1 miss. Combat
         round-tokens still detect (round != second).
  §11.2  Anchor resolution: explicit field, null on fail (15-turn back-walk).
  §11.3  Player time-mentions hard-rejected (MATT-only trigger).
  §11.4  Aggressive OOC reject.
  §11.5  Episode-break framing rejected entire-turn.
  §11.6  Multi-mention turns emit one record per phrase.
  §11.7  cumulative_anchor is its own category; boundary-stability reported
         in the validation doc.
  OQ1    NPC-dialogue D6 hard-reject; precision reported in validation.
  OQ5    Combat-state re-derived in this extractor (no import from
         encounter_cadence). Init regex copied below — deliberate single-
         extractor-isolation choice.

Usage:
    python3 time_mention.py --sample
        Runs on the 10 hand-sample episodes locked at OQ7 (disjoint from
        Encounter Cadence's review and from Phase 1 recon). Writes one
        combined file at ../samples/time_mention_sample.json.

    python3 time_mention.py --full
        Runs on all CRD3. Writes one file per episode to
        ../output/time_mention/{episode_id}.json.
        DO NOT RUN until gate-set (Phase 3) passes.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

EXTRACTOR_VERSION = "time_mention_v1_3"

CORPUS_BUILDER = Path(__file__).resolve().parent.parent
SOURCE_BASE = Path("/mnt/virgil_storage/dnd_datasets/crd3/data/aligned data/c=2")
OUTPUT_DIR = CORPUS_BUILDER / "output" / "time_mention"
SAMPLE_PATH = CORPUS_BUILDER / "samples" / "time_mention_sample_v1_3.json"

# Per spec §6: 800-char preceding context budget; 15-turn back-walk for anchor.
PRECEDING_CONTEXT_BUDGET = 800
ANCHOR_WALK_BACK_TURNS = 15
COMBAT_STATE_LOOKBACK_TURNS = 25  # OQ5 lock — prior 25 turns
COMBAT_STATE_STALENESS_TURNS = 30  # OQ5 lock — staleness fallback window
RECAP_EPISODE_POSITION_THRESHOLD = 0.10
DM_QA_SHORT_TURN_CHARS = 60

# OQ7 locked hand-sample episode list. Disjoint from Encounter Cadence's
# review set AND from Phase 1 recon's seven episodes.
SAMPLE_EPISODES = [
    "C1E003", "C1E024", "C1E047", "C1E057", "C1E085", "C1E101",
    "C2E002", "C2E018", "C2E024", "C2E031",
]

EPISODE_ID_RE = re.compile(r"^(C\d+)E(\d{3,4})$")


# ---------------------------------------------------------------------------
# Stage 1 — broad time-mention candidate detection (minutes-and-up only)
# ---------------------------------------------------------------------------
#
# Per §11.1 lock: seconds band excluded entirely. The unit alternation below
# is `minute|hour|day|night|week|month|year|round` (round retained for
# combat-state detection per the lock; nights/morning/evening retained
# because they imply day-scale time-of-day shifts). Each match is a
# candidate phrase. Multi-mention turns emit one record per phrase
# per §11.6.

_DURATION_NUM = (
    r"(?:an?|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    r"thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|"
    r"twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|"
    r"several|a\s+few|a\s+couple|a\s+number\s+of|many|some|few|\d+)"
)
_DURATION_UNIT = r"(?:minute|hour|day|night|week|month|year|round)s?"

TIME_TRIGGER = re.compile(
    # Numeric duration: "two weeks", "a few minutes", "six rounds"
    r"\b" + _DURATION_NUM + r"\s+" + _DURATION_UNIT + r"\b"
    # Relative-time anchored phrases
    r"|\bthe\s+(?:next|following|previous|last)\s+"
    r"(?:morning|day|night|week|month|year|evening|afternoon|hour|moment)\b"
    r"|\bby\s+the\s+time\s+you\b"
    # "moments later", "X minutes later", etc.
    r"|\b(?:moments?|hours?|days?|weeks?|months?|years?|minutes?)\s+"
    r"(?:later|pass|passed|go\s+by|have\s+passed)\b"
    r"|\blater\s+(?:that|on|in)\b"
    r"|\bsome\s+time\s+later\b|\bshortly\s+(?:after|later)\b|\bafter\s+a\s+while\b"
    # Time-of-day
    r"|\b(?:at|around|by|until|towards?)\s+"
    r"(?:dawn|dusk|noon|midnight|sunrise|sunset|nightfall|daybreak|sundown)\b"
    r"|\bthe\s+sun\s+(?:rises|sets|begins|dips|sinks|comes\s+up|hits)\b"
    # Tightened: "as night/day/etc" must be followed by a transition verb,
    # otherwise it's an idiom ("black as night"). The verb-bearing branch
    # below covers the real cases.
    r"|\bas\s+(?:the\s+sun)\b"
    r"|\b(?:as|when)\s+(?:night|morning|day|evening|dawn|dusk)\s+"
    r"(?:falls|takes|breaks|comes|arrives|begins|has\s+taken)\b"
    r"|\btime\s+(?:passes|has\s+passed|goes\s+by)\b"
    r"|\b(?:moments?|minutes?|hours?|days?|weeks?)\s+pass(?:es)?\b"
    r"|\ba\s+lot\s+of\s+time\s+passes\b"
    # Rest references (long/short rest)
    r"|\b(?:after\s+)?(?:a\s+)?(?:long|short)\s+rest\b"
    r"|\byou\s+(?:wake|come\s+to\s+consciousness)\b"
    # Travel verbs + duration framing
    r"|\b(?:you|you\s+all|you\s+guys)\s+"
    r"(?:travel|journey|ride|sail|march|fly|walk|trek|run|sprint)\s+(?:for|the|on)\b"
    r"|\bthe\s+(?:journey|trip|voyage|march)\s+(?:takes|lasts|will)\b"
    # Compression scaffolds
    r"|\bover\s+the\s+(?:course\s+of|next)\b"
    r"|\bin\s+the\s+(?:morning|evening|afternoon)\b"
    r"|\bthat\s+(?:morning|evening|night|afternoon)\b"
    # Cumulative-anchor scaffolds
    r"|\bit'?s\s+(?:been|now|getting|early|late|mid[-\s]?(?:morning|afternoon|evening|night))\b"
    r"|\bit\s+(?:has\s+been|is\s+now|is\s+(?:early|late|mid[-\s]?))\b"
    r"|\bsince\s+(?:you|last|the)\b"
    r"|\bpushing\s+(?:past|close\s+to)\b",
    re.I,
)


# ---------------------------------------------------------------------------
# Stage 0 — DISCOURSE / STATE / EVENT classifier
# ---------------------------------------------------------------------------
#
# Per spec §5 + Lesson 5. Runs AFTER Stage 1 candidate match, BEFORE Stage 2
# category classification. Each candidate-bearing turn is classified once;
# all phrases from a DISCOURSE turn are dropped together. STATE flags ride
# along on the EVENT records.
#
# With the §11.1 minutes-and-up lock, several D-patterns from the Phase 1
# spec became unnecessary: D3 (table-talk `hold on a second`), D4 (combat
# micro-beat `for a second`), and D5 (idiomatic `a second time/floor`)
# almost exclusively keyed on the seconds band. The remaining D3/D5
# patterns target minutes/hours that survive the lock — kept narrow.

# D1. Production OOC + episode breaks. Aggressive per §11.4 lock.
DISCOURSE_OOC = re.compile(
    r"\bwelcome\s+(?:to|back)\b"
    r"|\btonight'?s\s+episode\b"
    r"|\b(?:back\s+here|see\s+you\s+(?:guys\s+)?)\s*in\s+a\s+(?:few|couple)\s+(?:minutes?|seconds?)"
    r"|\bback\s+here\s+in\s+a\s+minute\b"
    r"|\bsee\s+you\s+(?:guys\s+)?(?:next\s+(?:week|time|month)|in\s+(?:a\s+(?:few|couple)\s+)?minutes?)"
    r"|\bwe'?ll\s+(?:be\s+(?:right\s+)?back|come\s+back|see\s+you)\b"
    r"|\bquick\s+break\b|\btake\s+(?:a\s+)?(?:short\s+|quick\s+)?(?:bathroom\s+)?break\b"
    r"|\b\[break\]|\[BREAK\]|\[dramatic\s+music\]"
    r"|\b(?:stream\s+of\s+many\s+eyes|wyrmwood|patreon|d&d\s+beyond|sponsor|critmas|critical\s+role\s+merch)"
    r"|\bgive\s+you\s+guys\s+some\s+character\s+backstory\b"
    r"|\bnext\s+week'?s?\s+(?:episode|stream|show|game)\b"
    r"|\blast\s+week'?s?\s+(?:episode|stream|show|game)\b"
    r"|\bcomic\s+(?:available|out|now\s+available)\b"
    r"|\bgo\s+to\s+(?:our|the)\s+(?:store|website)\b"
    r"|\bvisit\s+(?:our|the)\s+(?:store|website|merch)\b"
    r"|\bdaylight\s+savings?\b|\bgain(?:ing)?\s+an\s+hour\b"
    r"|\bmiss\s+you\s+then\b"
    r"|\bcliffhanger\b"
    # In-fiction-adjacent OOC at session boundaries — per §11.5 lock,
    # whole turn rejected even if a fiction-time phrase rides along.
    r"|\bwe'?ll\s+pick\s+up\s+(?:from|where)\b"
    r"|\bwe'?ll\s+leave\s+(?:you|it)\s+(?:on|here|there)\b"
    r"|\bwe'?ll\s+see\s+you\s+(?:guys\s+)?in\s+(?:a\s+)?(?:few|couple)\s+(?:weeks?|minutes?)"
    # Production / sponsor / event announcements
    r"|\bwe\s+will\s+continue\s+this\s+in\s+(?:just\s+)?a\s+moment\b"
    r"|\bplay\s+our\s+character\s+(?:backgrounds?|backstor(?:y|ies))\b"
    r"|\bin\s+the\s+meantime[,.]?\s+take\s+(?:a\s+)?(?:rest|breather|break)\b"
    r"|\bguests?\s+(?:at|next\s+week(?:end)?)\b"
    r"|\bpre[-\s]?order(?:ed|ing|s)?\b"
    r"|\bGilmore'?s\s+Glorious\s+Goods\b"
    r"|\b(?:critmas|Tekko|Wonderfest|Wizard\s+World|GenCon|PAX|D&D\s+Live|Origins)\b"
    r"|\bour\s+official\s+CritRole\b"
    r"|\bthrough\s+the\s+\d+(?:st|nd|rd|th)\b"  # event date framing
    r"|\bavailable\s+for\s+(?:one\s+more\s+)?day\b"
    r"|\bsale\s+ends\b"
    r"|\bGenCon\s+Indianapolis\b"
    r"|\bduring\s+the\s+convention\b"
    # Podcast / streaming / cross-show schedule
    r"|\bepisode\s+one\s+of\s+this\s+campaign\b"
    r"|\bin\s+podcast\s+form\b"
    r"|\bbetween\s+seasons\b"
    r"|\bback\s+for\s+(?:a\s+few\s+)?(?:episode|month|week)s?\b"
    r"|\b(?:Blindspot|Yellowstone|Brave\s+New\s+World)\b"
    r"|\bFor\s+Honor\s+streams?\b"
    r"|\bWoobox\b|\bcut[-\s]off\s+date\b"
    r"|\buntil\s+\w+\s+\d+(?:st|nd|rd|th)?\s+at\s+(?:midnight|noon|\d)"
    r"|\bin\s+the\s+chat\s+room\b"
    r"|\bof\s+these\s+upcoming\b"
    r"|\bpicking\s+up\s+a\s+shipment\b"  # NPC backstory dressed in OOC framing — but generic
    # Patch 4 (v1.2): break-announcement extensions
    r"|\bstrict\s+(?:five|ten|fifteen|twenty|thirty|\d+)\s+minutes?\b"
    r"|\b(?:we'?re|we\s+are|let'?s|let\s+us)\s+(?:going\s+to|gonna)\s+take\s+"
    r"(?:a|our|the)\s*(?:quick|short)?\s*(?:\d+|\w+)?\s*(?:minute|moment|second)?\s*break\b"
    r"|\b(?:we'?re|we\s+are|let'?s)\s+(?:going\s+to|gonna)\s+(?:come|be)\s+back\s+"
    r"(?:in|after)\s+(?:the|a)?\s*(?:morning|moment|minute|hour|few|short)\b"
    # Matt asking players (table-talk question form, not narration)
    r"|\bdid\s+you\s+(?:guys\s+)?(?:take|do|finish|complete|cast|use)\s+(?:a\s+)?"
    r"(?:long\s+rest|short\s+rest)\b\s*\?"
    r"|\bare\s+you\s+(?:guys\s+)?(?:taking|going\s+to\s+take)\s+(?:a\s+)?"
    r"(?:long\s+rest|short\s+rest)\b\s*\?"
    r"|\bback\s+(?:here\s+)?(?:in|after)\s+(?:a|\d+|\w+)?\s*"
    r"(?:few|couple|bunch\s+of)?\s*(?:minute|second|hour|moment)s?\b"
    r"|\b(?:see|catch)\s+you\s+(?:guys\s+)?(?:next|in|back)\s+"
    r"(?:week|episode|time|tonight|here|shortly)\b"
    # Meta-procedural addressed-to-players framing
    r"|\bdiscuss\s+this\s+over\s+the\s+next\s+(?:week|few|couple)\b"
    r"|\byou\s+don'?t\s+(?:need|have)\s+to\s+decide\s+(?:this\s+)?right\s+now\b"
    r"|\bif\s+you\s+want\s+to\s+(?:discuss|think|decide)\b"
    # Patch 4: cast banter / production references with time-phrase
    r"|\b(?:next\s+week|tonight|tomorrow)\s+we'?re\s+(?:gonna|going\s+to)\s+(?:try|do|run|stream|host)\b"
    r"|\bwe'?re\s+(?:gonna|going\s+to)\s+(?:try\s+and\s+)?do\s+a\s+(?:Q\s*&\s*A|Q&A|stream|panel)\b"
    r"|\bstay\s+for\s+an\s+hour\s+or\s+more\s+after\b"
    r"|\b(?:first|second|third|fourth|fifth)\s+(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+of\s+"
    r"(?:January|February|March|April|May|June|July|August|September|October|November|December)\b"
    # Cast biographical: "ten years ago" near photo/headshot/shoot context
    r"|\b(?:headshot|photo|shoot|that\s+shot|back\s+in\s+the\s+day)\b.{0,100}?\b\d+\s+years?\s+ago\b"
    r"|\b\d+\s+years?\s+ago\b.{0,100}?\b(?:headshot|photo|shoot|that\s+shot)\b"
    ,
    re.I,
)

# D2. Spell/rules duration. Targets `lasts for X` mechanic-talk and
# spell-name co-occurrence with duration phrases.
DISCOURSE_SPELL_DURATION = re.compile(
    r"\blasts?\s+for\s+(?:a|an|the\s+next|up\s+to|\d+)\s+(?:round|minute|hour)"
    r"|\bonly\s+lasts?\s+for?\s+(?:a|an|\d+)\s+(?:round|minute|hour)"
    r"|\b(?:the\s+)?spell\s+(?:has\s+)?(?:faded|ended|expires?|drops?|fades?)\b"
    r"|\bconcentration\s+(?:broken|drops?|ends|breaks)\b"
    r"|\beach\s+of\s+your\s+turns?\b"
    r"|\bend\s+of\s+(?:each\s+of\s+)?your\s+turns?\b"
    r"|\bat\s+the\s+end\s+of\s+your\s+turn\b"
    # named D&D spells next to a duration phrase
    r"|\b(?:Haste|Bigby'?s|Modify\s+Memory|Hold\s+Person|Hex|Detect\s+Magic|"
    r"Plane\s+Shift|Stoneskin|Mage\s+Armor|Polymorph|Banishment|Counterspell|"
    r"Dispel\s+Magic|Hunter'?s\s+Mark|Bless|Bane|Faerie\s+Fire|Fog\s+Cloud|"
    r"Misty\s+Step|Levitate|Invisibility|Silence|Sanctuary|Hypnotic\s+Pattern|"
    r"Wall\s+of\s+\w+|Bigby|Bigby's\s+Hand)\s+(?:lasts?|spell|by\s+the\s+way)"
    r"|\bup\s+to\s+ten\s+minutes\s+(?:of|that)\b"  # Modify Memory rule-text
    r"|\bspell\s+(?:level|slot|saves?)\b"
    r"|\b(?:a|an)\s+(?:second|third|fourth|fifth|sixth|seventh|eighth|ninth)[-\s]?level\s+spell\b"
    # Generic ability/potion/effect duration framings
    r"|\b(?:potion|ability|effect|disguise|charm|spell)('?s)?\s+(?:effect|duration|lasts)\b"
    r"|\bDisguise\s+Self\s+lasts\b|\bWild\s+Shape\b|\bBeast\s+Shape\b|\bRage\b\s+(?:lasts|for)"
    r"|\bequal\s+to\s+(?:half\s+)?your\s+(?:druid|wizard|cleric|barbarian|fighter|sorcerer|warlock|rogue|monk|ranger|paladin|bard)?\s*level\b"
    r"|\bfor\s+a\s+number\s+of\s+(?:hour|minute|round)s?\s+equal\s+to\b"
    r"|\bcan\s+(?:transform|stay|maintain|hold|keep|use)\s+for\s+(?:about\s+)?(?:a|an|\d+)\s+(?:minute|hour)s?\b"
    r"|\bfor\s+the\s+potion'?s?\s+(?:effect|duration)\b"
    r"|\banywhere\s+from\s+\w+\s+to\s+\w+\s+hours\b"
    r"|\b\w+\s+lasts\s+for[,.]?\s+is\s+it\s+(?:a|an)\b"
    # "stays unconscious for the duration"
    r"|\b(?:stays?|remains?)\s+unconscious\s+for\s+the\s+duration\b"
    r"|\bfor\s+the\s+duration\b"
    # "For the next X hours, not concentration" — Foresight-shaped rules text
    r"|\bfor\s+the\s+next\s+\d+\s+hours?,?\s+(?:not\s+)?concentration\b"
    r"|\b(?:not\s+)?concentration[,.]?\s+you\s+can'?t\s+be\s+surprised\b"
    # "the first 12 hours are completed" — long-rest mechanic
    r"|\bthe\s+first\s+\d+\s+hours?\s+(?:are\s+completed|of\s+(?:rest|long\s+rest))\b"
    # Healing potion / downtime craft
    r"|\bhealing\s+potion\s+for\s+\d+\s+gold\b"
    r"|\bone\s+day\s+of\s+downtime\b",
    re.I,
)

# D3 (minutes-band only). DM table-talk pacing: "give me a minute", "hold on
# a minute". Rare with seconds excluded but kept narrow.
DISCOURSE_TABLE_TALK = re.compile(
    r"\b(?:give|hold)\s+(?:me|on)\s+(?:just\s+)?a\s+minute\b"
    r"|\bone\s+minute\s+please\b"
    r"|\b(?:let\s+me|let'?s)\s+(?:see|figure|look|think)\s+for\s+a\s+(?:minute|moment)\b"
    r"|\bjust\s+a\s+minute\s+there\b"
    # Matt's self-narration: joking about narrative pacing.
    r"|\b(?:about\s+)?an?\s+hour\s+and\s+a\s+half\s+of\s+me\b"
    r"|\bof\s+me\s+(?:telling|talking|going\s+through|narrating|explaining)\s+you\b",
    re.I,
)

# D5 (minutes-band only). Idiom `a minute is up` (mechanic-flavored), the
# "minute" inside "in another minute" rules-talk, etc. Kept short.
DISCOURSE_MINUTE_IDIOM = re.compile(
    r"\bnever\s+mind\b\s+(?:so|then)\b\s+take\s+half"  # rules clarification
    r"|\bfor\s+the\s+next\s+round\s+or\s+so\s+there'?s\s+partial\s+cover"
    # Patch 5 (v1.2): non-temporal idioms
    # "it's been [emotion/state]" — not time
    r"|\bit'?s\s+been\s+(?:a\s+|an\s+|very\s+)?"
    r"(?:pleasure|honor|frustrating|tough|hard|difficult|wonderful|amazing|"
    r"crazy|wild|tense|long|interesting|fun|good|great|bad|awful|terrible|"
    r"rough|stressful|busy|quiet|fine|nice)\b"
    r"|\bit\s+has\s+been\s+(?:a\s+|an\s+|very\s+)?"
    r"(?:pleasure|honor|frustrating|tough|hard|difficult|wonderful|amazing|"
    r"crazy|wild|tense|long|interesting|fun|good|great|bad|awful|terrible|"
    r"rough|stressful|busy|quiet|fine|nice)\b"
    # "wait a minute" NPC idiom
    r"|\bwait\s+a\s+(?:minute|second|sec)(?:[\s,.!?]|$)"
    # "give me/us a minute" idiom
    r"|\bgive\s+(?:me|us|him|her|them)\s+(?:a|another)\s+(?:minute|second|moment)\b"
    # drinks idioms
    r"|\b(?:i|you|i'?ll|you'?ll)\s+owe\s+(?:you|me|him|her|them)?\s*a\s+round\b"
    r"|\bi\s+owe\s+you\s+a\s+round\b"
    # "as bright/fine/cold/warm a day as"
    r"|\bas\s+(?:bright|fine|cold|warm|long|good|nice|dark|gloomy|cloudy)\s+a\s+day\s+as\b"
    # Item-state perfect (has been used/crafted/etc.)
    r"|\b(?:it'?s|it\s+has)\s+been\s+"
    r"(?:used|crafted|completed|broken|destroyed|finished|made|built|left|put|placed|set|stored|sitting|standing)"
    r"(?!\s+for\s+(?:\d+|a|an|the\s+\w+|several|a\s+few|a\s+couple|many|some)\s+"
    r"(?:year|month|week|day|hour|minute)s?\b)"
    # "through the ringer/wringer/works/paces" idioms
    r"|\b(?:it'?s|it\s+has)\s+(?:been|gone)\s+(?:through|past)\s+(?:the\s+)?"
    r"(?:ringer|wringer|works|paces|gauntlet)\b"
    # "for a minute there" NPC pause idiom
    r"|\bfor\s+a\s+(?:minute|hour)\s+there[\s,.!?]"
    # "it's getting [non-temporal]" — only filter when followed by non-time adjective
    r"|\bit'?s\s+getting\s+"
    r"(?:pretty|really|kind\s+of|sort\s+of|very|quite)?\s*"
    r"(?:thick|frustrated|frustrating|annoying|hot|cold|crowded|loud|quiet|"
    r"weird|strange|interesting|boring|tough|hard|difficult|messy|"
    r"complicated|out\s+of\s+hand|ridiculous|tense|heated|awkward|silly)\b"
    # "a [non-temporal]-noun day" — "a day of work" idiom
    r"|\ba\s+day(?:'?s)?\s+(?:of|work|wages|labor|pay)\b"
    # "give it a few minutes" task idiom — let real fiction-time still match this
    # but block "give it a minute" as NPC idiom by checking quote context separately
    # NPC pause idiom variants
    r"|\blet\s+me\s+get\s+(?:loose|comfortable|settled|going)\s+(?:here\s+)?for\s+a\s+(?:minute|second|moment)\b"
    # "since you mention it" / "since you brought it up"
    r"|\bsince\s+you\s+mention(?:ed)?\s+it\b"
    r"|\bsince\s+you\s+brought\s+(?:it|that)\s+up\b"
    # Drinks-contest "round" idioms
    r"|\bgaining\s+a\s+round\b"
    r"|\bthese\s+last\s+(?:two|three|four|few|\d+)\s+rounds\b"
    r"|\b(?:that'?s|wins?)\s+(?:two|three|\d+)\s+for\s+(?:two|three|\d+)\b"
    # "it's been turned/transformed/changed [past participle]" — state change, not time
    r"|\b(?:it'?s|it\s+has)\s+been\s+(?:turned|transformed|changed|become|"
    r"made|rendered|reduced|reshaped|modified|altered|moved|shifted|"
    r"converted|covered|filled|cleaned|cleared)\s+\w+"
    # "it's been a while since" — meta-comment about real-world player action
    r"|\bit'?s\s+been\s+a\s+while\s+since\s+(?:you|we|i)\s+(?:wrestled|"
    r"played|ran|did|tried|saw|attempted|talked|met|fought)\b"
    # "slammed/dragged across [duration] of [thing]" — simile imagery
    r"|\b(?:slammed|dragged|carried|stretched)\s+across\s+(?:\w+\s+){0,2}"
    r"(?:hundred|thousand|\d+)\s+years?\s+of\b"
    # "Hour of [proper noun]" event-name idiom
    r"|\bHour\s+of\s+(?:Honor|Devotion|Reckoning|Truth|Glory|Reverence|Judgment)\b"
    # Bare 2-word "It has been" answer (player Q&A confirmation) — handled by D7
    # but tightened by Patch 3 D7 exception below.
    ,
    re.I,
)

# D6. NPC dialogue. Default per OQ1: hard reject when trigger phrase
# appears inside or adjacent to in-character speech. Phase 2 hand-sample
# reports D6 reject precision; if <85%, switch to flag-rather-than-reject.
QUOTED_SPEECH = re.compile(r'["“”][^"“”\n]{4,}["“”]')
NPC_VOICING = re.compile(
    r"\b(?:he|she|it|they|the\s+\w+)\s+"
    r"(?:says?|said|goes|growls?|hisses?|whispers?|shouts?|yells?|barks?|"
    r"roars?|chuckles?|laughs?|sneers?|scoffs?|smiles?\s+and\s+says?|"
    r"replies|reply|replied|continues|continued|states|stated|answers|"
    r"answered|nods?\s+and\s+says?|adds?|asks?|asked)\b"
    r"|\b(?:says?|whispers?|growls?|hisses?|roars?|shouts?|yells?)\s*[:,]\s+[\"“]",
    re.I,
)
NPC_NAMED_SPEECH = re.compile(
    r"\b[A-Z][a-zA-Z'\-]{2,}\s+(?:says?|said|goes|growls?|hisses?|whispers?|"
    r"shouts?|sneers?|scoffs?|smiles?\s+and\s+says?|chuckles?|laughs?|"
    r"replies|continues)\b"
)

# D7 (player-question pass-back). Computed at process_episode level — needs
# previous non-MATT turn context. Single-line answer ≤60 chars containing
# only a duration, immediately following a `?`-terminated non-MATT turn.
# Exception: if the answer matches a §3.4 cumulative_anchor pattern, allow
# through (it establishes a current-clock anchor).

# D8 (Patch 3, v1.2). Causal `since` filter — `since` used as a reason
# conjunction, not a temporal one. Fires per-phrase (when the trigger
# phrase itself contains `since`). Filters NOT_TIME_MENTION before Stage 2.
DISCOURSE_CAUSAL_SINCE = re.compile(
    # "since you're/I'm [verb]ing" — present participle reason
    r"\bsince\s+(?:you'?re|i'?m|we'?re|they'?re|he'?s|she'?s|it'?s)\s+\w+ing\b"
    # "since I am/you are [doing X]" — present indicative reason
    r"|\bsince\s+(?:i\s+am|you\s+are|we\s+are|they\s+are|he\s+is|she\s+is|it\s+is)\s+"
    r"(?:in|at|on|here|there|the|a|an|looking|trying|doing|going|coming|making|"
    r"taking|using|holding|carrying|wearing|sitting|standing|walking|stunned|"
    r"prone|grappled|invisible|hidden)\b"
    # "since the [noun] has been [state]" — state perfect, not event
    r"|\bsince\s+(?:the|a|an|that|this|my|your|our|their)\s+\w+(?:\s+\w+)?\s+"
    r"(?:has\s+been|have\s+been|is|was|were|are|'?s|'?re)\s+"
    r"(?:broken|completed|destroyed|damaged|finished|here|gone|sold|bought|"
    r"stolen|missing|present|ready|available|stunned|prone|grappled|invisible|"
    r"hidden|set\s+up|put\s+together)\b"
    # "since the [reason-noun]" — non-temporal reason noun
    r"|\bsince\s+(?:the|a|an)\s+"
    r"(?:war|issue|matter|incident|deal|trade|problem|concern|case|fact|"
    r"reason|thing|business|deck|name)\b"
    # "since [you/the X] are/were stunned/prone/etc." — combat condition
    r"|\bsince\s+(?:you|he|she|they|the\s+\w+)\s+(?:are|is|were|was)\s+"
    r"(?:stunned|prone|grappled|invisible|hidden|unconscious|charmed|frightened)\b",
    re.I,
)


# ---------------------------------------------------------------------------
# OQ5 — Combat-state detection (init regex copied from encounter_cadence.py).
# ---------------------------------------------------------------------------
#
# Deliberate single-extractor-isolation choice: rather than `import
# encounter_cadence`, copy the POSITIVE_INIT pattern below. Two extractors
# share a regex shape; neither depends on the other's module. If either
# evolves, the divergence is local and visible in version-control history.

# Copied from corpus_builder/extractors/encounter_cadence.py POSITIVE_INIT
# (encounter_cadence_v1_3, post-Patch-7 hardening). Source-of-truth for init
# detection is encounter_cadence.py; this copy is for combat-state heuristic
# only and may drift behind upstream over time.
COPIED_POSITIVE_INIT = re.compile(
    r"\b(?:re)?roll(?:s|ing|ed)?\s+(?:for\s+|some\s+)?initiative\b"
    r"|\binitiative\s+(?:has\s+(?:now\s+)?|now\s+)?kicked\s+in\b"
    r"|\b(?:now|we'?re)\s+in\s+initiative\b"
    r"|\binitiative\s+is\s+being\s+rolled\b"
    r"|\bfor\s+initiative\b",
    re.I,
)

# End-of-combat signals.
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
    """Per OQ5 lock. True if any MATT turn in [idx-25, idx) matched
    COPIED_POSITIVE_INIT AND no COPIED_END_OF_COMBAT signal appears between
    that init and the candidate AND no staleness (no init vocabulary in
    last COMBAT_STATE_STALENESS_TURNS turns) is detected.
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

    # Staleness fallback — no init vocabulary in last STALENESS_TURNS turns.
    stale_start = max(0, candidate_idx - COMBAT_STATE_STALENESS_TURNS)
    has_recent_init_vocab = any(
        INIT_VOCABULARY.search(turns[j]["text"])
        for j in range(stale_start, candidate_idx)
    )
    if not has_recent_init_vocab:
        return False
    return True


# ---------------------------------------------------------------------------
# Recap-state detection
# ---------------------------------------------------------------------------

RECAP_VOCAB = re.compile(
    r"\blast\s+(?:week|episode|time|game)\b"
    r"|\bpreviously\s+on\b"
    r"|\bwe\s+(?:left\s+off|last\s+(?:left|saw|met))\b"
    r"|\bas\s+we\s+begin\s+tonight\b"
    r"|\bpicking\s+up\s+(?:where|from)\b"
    r"|\blet'?s\s+pick\s+up\s+(?:where|from)\b"
    r"|\bgoing\s+back\s+over\s+what\b"
    r"|\bwhat\s+(?:had\s+)?transpired\b"
    r"|\bto\s+(?:recap|summarize|bring\s+you\s+up\s+to\s+speed)\b"
    r"|\bin\s+(?:our\s+)?last\s+episode\b",
    re.I,
)


def derive_recap_state(turns, candidate_idx, total_turns):
    """True if candidate sits within first RECAP_EPISODE_POSITION_THRESHOLD
    of the episode AND any preceding turn within the same prefix matched
    RECAP_VOCAB.
    """
    if total_turns == 0:
        return False
    pos = candidate_idx / total_turns
    if pos > RECAP_EPISODE_POSITION_THRESHOLD:
        return False
    for j in range(0, candidate_idx):
        if RECAP_VOCAB.search(turns[j]["text"]):
            return True
    # Trigger turn itself counts as a recap-prefix occurrence.
    return RECAP_VOCAB.search(turns[candidate_idx]["text"]) is not None


# ---------------------------------------------------------------------------
# Stage 0 dispatch
# ---------------------------------------------------------------------------


def stage_0_classify(trigger_text, preceding_turns, prev_non_matt_turn):
    """Return (label, reason). label in {"DISCOURSE", "EVENT"}.

    STATE flags (is_combat_state, is_recap_state) are computed elsewhere
    and ride along on the emitted record; Stage 0 here decides only
    DISCOURSE-reject vs continue-to-Stage-2.
    """
    if DISCOURSE_OOC.search(trigger_text):
        m = DISCOURSE_OOC.search(trigger_text)
        return "DISCOURSE", f"D1_ooc :: {m.group()!r}"

    if DISCOURSE_SPELL_DURATION.search(trigger_text):
        m = DISCOURSE_SPELL_DURATION.search(trigger_text)
        return "DISCOURSE", f"D2_spell_duration :: {m.group()!r}"

    if DISCOURSE_TABLE_TALK.search(trigger_text):
        m = DISCOURSE_TABLE_TALK.search(trigger_text)
        return "DISCOURSE", f"D3_table_talk :: {m.group()!r}"

    if DISCOURSE_MINUTE_IDIOM.search(trigger_text):
        m = DISCOURSE_MINUTE_IDIOM.search(trigger_text)
        return "DISCOURSE", f"D5_minute_idiom :: {m.group()!r}"

    # D6. NPC dialogue — DOWNGRADED from reject to flag in v1.
    # Phase 2 spot-check (n=25) of D6 rejects produced ~56-64% precision —
    # well below the OQ1 lock's 85% threshold. NPC-dialogue detection is
    # too lossy at the turn level (Matt routinely narrates real fiction-time
    # in the same turn as quoting an NPC). Per the OQ1 fallback, D6 is now
    # a `is_npc_dialogue_present` flag set at the record schema level. The
    # has_npc_dialogue() check still runs but no longer rejects.

    # D7. Player-question pass-back. Short MATT turn (≤ DM_QA_SHORT_TURN_CHARS)
    # immediately following a `?`-terminated non-MATT turn. Exception: if the
    # short answer matches a §3.4 cumulative_anchor pattern AND carries
    # explicit temporal context (Patch 3 tightening). Bare "It has been" with
    # no temporal vocab no longer escapes D7.
    if (
        prev_non_matt_turn is not None
        and prev_non_matt_turn["text"].rstrip().endswith("?")
        and len(trigger_text) <= DM_QA_SHORT_TURN_CHARS
    ):
        anchor_pattern_present = is_cumulative_anchor_phrase(trigger_text)
        has_temporal = (
            CUMULATIVE_TIME_VOCAB.search(trigger_text) is not None
            or CUMULATIVE_BACKWARD_TEMPORAL.search(trigger_text) is not None
        )
        if not (anchor_pattern_present and has_temporal):
            return "DISCOURSE", "D7_qa_passback"

    return "EVENT", None


def has_npc_dialogue(text):
    """True if a MATT turn contains NPC dialogue (quoted or voiced)."""
    if QUOTED_SPEECH.search(text):
        return True
    if NPC_VOICING.search(text):
        return True
    if NPC_NAMED_SPEECH.search(text):
        return True
    return False


# ---------------------------------------------------------------------------
# Patch 2 (v1.2) — phrase-span NPC routing
# ---------------------------------------------------------------------------
#
# When the turn carries `is_npc_dialogue_present: true`, route the phrase to
# UNKNOWN_SHAPE UNLESS the phrase falls in Matt-narration. Detection:
#   1. If unmatched quote-mark count BEFORE phrase is odd → phrase is INSIDE
#      a quoted span (NPC speech). Route to UNKNOWN_SHAPE.
#   2. If an NPC voicing tag (`he says`, `she goes`, `[name] replies`)
#      appears in the SAME sentence preceding the phrase → NPC speech.
#      Route to UNKNOWN_SHAPE.
#   3. Otherwise, phrase is in Matt narration. Classify normally.

_SENT_BOUNDARY_RE = re.compile(r"[.!?](?:\s+|$)")


def get_sentence_span(turn_text, phrase_start, phrase_end):
    """Return (sent_start, sent_end) for the sentence containing the phrase."""
    # Walk back to last sentence boundary before phrase_start
    sent_start = 0
    for m in _SENT_BOUNDARY_RE.finditer(turn_text[:phrase_start]):
        sent_start = m.end()
    # Walk forward to next sentence boundary after phrase_end
    rest = turn_text[phrase_end:]
    m = _SENT_BOUNDARY_RE.search(rest)
    sent_end = phrase_end + m.start() + 1 if m else len(turn_text)
    return sent_start, sent_end


def is_phrase_in_npc_speech(turn_text, phrase_start, phrase_end):
    """True if the phrase falls inside NPC dialogue (quoted or voiced)."""
    # Check 1: odd number of quote chars before phrase → inside open quote.
    quote_count = sum(1 for c in turn_text[:phrase_start] if c in '"“”')
    if quote_count % 2 == 1:
        return True
    # Check 2: NPC voicing tag in same sentence before phrase.
    sent_start, _ = get_sentence_span(turn_text, phrase_start, phrase_end)
    same_sentence_pre = turn_text[sent_start:phrase_start]
    if NPC_VOICING.search(same_sentence_pre):
        return True
    if NPC_NAMED_SPEECH.search(same_sentence_pre):
        return True
    return False


# ---------------------------------------------------------------------------
# Patch 3 (v1.2) — cumulative_anchor temporal-context check
# ---------------------------------------------------------------------------
#
# `cumulative_anchor` overfires on phrases like "it's been there for a while"
# (about a wall symbol). Require that the phrase's sentence carry at least
# one of: explicit time vocabulary, time-state vocabulary, backward-pointing
# temporal anchor, or campaign-clock state declaration paired with time
# vocabulary.

CUMULATIVE_TIME_VOCAB = re.compile(
    r"\b(?:morning|afternoon|evening|night|dusk|dawn|noon|midnight|"
    r"hour|hours|minute|minutes|day|days|week|weeks|month|months|"
    r"year|years|sundown|sunrise|sunset|daybreak|nightfall|"
    r"midday|midnight|midmorning|midafternoon)\b",
    re.I,
)

CUMULATIVE_TIME_STATE = re.compile(
    r"\b(?:early|late|mid[-\s]?)\s*"
    r"(?:morning|afternoon|evening|night|dusk|dawn|noon|midnight)"
    r"|\bpushing\s+(?:past|close\s+to|towards?)\b"
    r"|\bgetting\s+close\s+to\b"
    r"|\bclosing\s+on\b",
    re.I,
)

CUMULATIVE_BACKWARD_TEMPORAL = re.compile(
    # "X (hours|days|...) ago" — explicit duration backward
    r"\b(?:hours?|days?|weeks?|months?|years?|minutes?)\s+ago\b"
    # Patch 6 (v1.3): explicit time-context "since" — tightened.
    # `since (you|we|they|the party|he|she|it) (last|first)? <event-verb>`
    r"|\bsince\s+(?:you|we|they|the\s+(?:party|group)|he|she|it)\s+"
    r"(?:last\s+|first\s+)?"
    r"(?:left|arrived|came|woke|met|saw|encountered|departed|returned|started|"
    r"began|crossed|entered|exited|spoke|talked|finished|got|went)\b"
    # `since (you've|we've|they've) <participle>`
    r"|\bsince\s+(?:you'?ve|we'?ve|they'?ve|he'?s|she'?s)\s+"
    r"(?:been|seen|met|left|arrived|come|gone|spoken|talked|encountered)\b"
    # `since [the last|that] <time-noun>`
    r"|\bsince\s+(?:the\s+last|that)\s+"
    r"(?:morning|afternoon|evening|night|day|week|month|year|hour|minute|"
    r"moment|battle|encounter|fight|rest|meal|conversation|meeting|visit)\b"
    # `since N (hour|day|...)`
    r"|\bsince\s+\d+\s+(?:hour|minute|day|week|month|year)s?\b"
    # `since (yesterday|earlier|previously|the start|the beginning|breakfast|...)`
    r"|\bsince\s+(?:yesterday|earlier|previously|the\s+start|the\s+beginning|"
    r"breakfast|lunch|dinner|sundown|sunup|sunrise|sunset|nightfall|daybreak)\b"
    # bare "ago" — duration ago references
    r"|\bago\b",
    re.I,
)

CUMULATIVE_CAMPAIGN_CLOCK = re.compile(
    r"\bat\s+this\s+point(?:\s+in\s+time)?\b"
    r"|\bcurrently\b"
    r"|\bright\s+now\b"
    r"|\bso\s+far\b",
    re.I,
)


def cumulative_anchor_has_temporal_context(turn_text, phrase_start, phrase_end):
    """True if the phrase's sentence carries enough temporal context to
    support cumulative_anchor classification."""
    sent_start, sent_end = get_sentence_span(turn_text, phrase_start, phrase_end)
    sentence = turn_text[sent_start:sent_end]
    if CUMULATIVE_TIME_VOCAB.search(sentence):
        return True
    if CUMULATIVE_TIME_STATE.search(sentence):
        return True
    if CUMULATIVE_BACKWARD_TEMPORAL.search(sentence):
        return True
    if CUMULATIVE_CAMPAIGN_CLOCK.search(sentence) and CUMULATIVE_TIME_VOCAB.search(sentence):
        return True
    return False


# ---------------------------------------------------------------------------
# Stage 2 — category classification (priority order per spec §3)
# ---------------------------------------------------------------------------
#
# Priority: scene_transition > travel_duration > cumulative_anchor >
# in_scene_compression. Phrases unclassifiable but Stage-0-passed emit with
# `unknown_shape: true` per Lesson 2 (no default catchall).

SCENE_TRANSITION_PHRASE = re.compile(
    r"\bthe\s+(?:next|following)\s+(?:morning|day|night|evening|afternoon|week|month|year)\b"
    r"|\b(?:as|when)\s+(?:morning|night|day|evening|dawn|dusk)\s+"
    r"(?:falls|takes|breaks|comes|arrives|begins|has\s+taken)\b"
    r"|\bas\s+the\s+sun\s+(?:rises|sets|begins|hits|dips|sinks|comes\s+up)\b"
    r"|\bthe\s+sun\s+(?:rises|sets|begins\s+to|dips|sinks|comes\s+up|hits)\b"
    r"|\b(?:after\s+)?(?:a\s+)?(?:long|short)\s+rest\b"
    r"|\byou\s+(?:wake|come\s+to\s+consciousness|emerge\s+from\s+(?:your\s+)?(?:slumber|sleep))\b"
    r"|\b(?:moments?|minutes?|hours?|days?|weeks?)\s+later\b"
    r"|\bsome\s+time\s+later\b|\bshortly\s+(?:after|later)\b"
    r"|\b\d+\s+(?:or\s+so\s+)?(?:minute|hour|day|week|month|year)s?\s+later\b"
    r"|\b(?:months?|years?)\s+later\b"
    # X passes / X go by — passive scene-bridging compression
    r"|\b(?:a|an|\d+|few|several|a\s+few|a\s+couple|the\s+next\s+few)\s+"
    r"(?:minute|hour|day|week|month|year)s?\s+"
    r"(?:pass|passes|go\s+by|elapse|elapses|fly\s+by|tick\s+by)\b"
    r"|\bthe\s+(?:morning|day|night|evening)\s+(?:has\s+come|comes\s+to\s+(?:fruition|an\s+end))\b"
    r"|\bthe\s+next\s+(?:few|couple\s+of)\s+(?:minute|hour|day|week)s?\b"
    # "coming to consciousness in your respective rooms"
    r"|\bcoming\s+to\s+consciousness\b"
    r"|\bcold\s+(?:morning|evening)\s+air\b"
    # "X passes/pass" / "moments pass" / "time passes"
    r"|\b(?:moments?|minutes?|hours?|days?|weeks?|months?|years?)\s+pass(?:es)?\b"
    r"|\ba\s+lot\s+of\s+time\s+passes\b"
    r"|\btime\s+(?:passes|has\s+passed|goes\s+by)\b"
    # Foreshortening
    r"|\bby\s+the\s+time\s+you\b"
    # X (days|weeks|months) of downtime
    r"|\b(?:" + _DURATION_NUM + r"|roughly\s+" + _DURATION_NUM + r")\s+"
    r"(?:day|week|month|year)s?\s+of\s+downtime\b"
    # spent these N weeks/days handling/at — montage compression
    r"|\bspent\s+(?:these\s+|the\s+majority\s+of\s+(?:these\s+)?)?(?:" + _DURATION_NUM + r")\s+"
    r"(?:day|week|month|year)s?\s+(?:handling|at|in|wandering|exploring)"
    # "in N days/weeks" future scene cue
    r"|\bin\s+(?:" + _DURATION_NUM + r")\s+(?:day|week|month|year)s?\b",
    re.I,
)

TRAVEL_VERB = re.compile(
    r"\b(?:travel|travels|traveled|traveling|travelling|"
    r"journey|journeys|journeyed|journeying|"
    r"ride|rides|rode|riding|"
    r"sail|sails|sailed|sailing|"
    r"march|marches|marched|marching|"
    r"walk|walks|walked|walking|"
    r"run|runs|ran|running|"
    r"sprint|sprints|sprinted|sprinting|"
    r"fly|flies|flew|flying|"
    r"trek|treks|trekked|trekking|"
    r"hike|hikes|hiked|hiking|"
    r"coast|coasts|coasted|coasting)\b",
    re.I,
)

TRAVEL_PHRASE = re.compile(
    r"\b(?:you|you\s+all|you\s+guys)\s+"
    r"(?:travel|journey|ride|sail|march|fly|walk|trek|run|sprint|hike)"
    r"(?:s|ed|ing|led|ling|ked|king)?\s+(?:for|the|on|across|through)\b"
    r"|\bthe\s+(?:journey|trip|voyage|march)\s+(?:takes|lasts|will\s+take)\b"
    r"|\bmulti[-\s]day\s+travel\b"
    r"|\byou'?ve\s+(?:gone|been\s+(?:running|walking|riding|traveling|"
    r"travelling|sprinting|sailing))\b"
    r"|\b(?:running|sprinting|walking|riding|sailing|marching|trekking|hiking)"
    r"\s+(?:for|the)\s+(?:about\s+)?(?:the\s+)?(?:better\s+part\s+of\s+)?"
    r"(?:a|an|\d+|several|a\s+few|a\s+couple)\b"
    r"|\bover\s+the\s+next\s+(?:couple\s+of\s+)?days?\b",
    re.I,
)

CUMULATIVE_ANCHOR_PHRASE = re.compile(
    r"\bit'?s\s+been\b|\bit\s+has\s+been\b"
    r"|\bit'?s\s+now\b|\bit\s+is\s+now\b"
    r"|\bit'?s\s+(?:early|late|mid[-\s]?|past)?\s*(?:morning|afternoon|evening|"
    r"night|dawn|dusk|noon|midnight)\b"
    r"|\bit\s+is\s+(?:early|late|mid[-\s]?|past)?\s*(?:morning|afternoon|evening|"
    r"night|dawn|dusk|noon|midnight)\b"
    r"|\bit'?s\s+(?:past|getting)\s+(?:dusk|dawn|night|morning|evening|noon|midnight)\b"
    r"|\bnow\s+(?:getting|pushing)\s+(?:to|past|close\s+to)\b"
    r"|\bpushing\s+(?:past|close\s+to)\b"
    r"|\bsince\s+(?:you|last|that|the\s+\w+(?:\s+\w+)?)\b"
    r"|\b(?:hours?|days?|weeks?|months?|years?)\s+ago\b"
    r"|\btotal,?\s+all\s+the\s+nights\b"
    r"|\b(?:in|so\s+far|total)\s+(?:in\s+the\s+\w+\s+)?total\b"
    r"|\bgetting\s+(?:to|towards?|close\s+to)\s+"
    r"(?:dusk|dawn|night|morning|evening|noon|midnight|sunset|sunrise)\b"
    r"|\bclose\s+to\s+a\s+(?:week|month|year|day)\s+(?:in|of)\b"
    # Time-of-day with offset: "a few hours into the evening"
    r"|\b(?:a\s+few|several|\d+|a)\s+(?:hours?|minutes?)\s+into\s+(?:the\s+)?"
    r"(?:morning|evening|afternoon|night|day)\b"
    # "around noon" / "around dawn"
    r"|\baround\s+(?:noon|dawn|dusk|midnight|midday|sunrise|sunset)\b"
    # "later in the morning/evening/afternoon"
    r"|\blater\s+in\s+(?:the\s+)?(?:morning|evening|afternoon|night|day)\b"
    # "in the morning" / "in the evening" / "in the afternoon" anchored
    r"|\bin\s+the\s+(?:morning|evening|afternoon)\b"
    # explicit clock reading
    r"|\b\w+\s+o'?clock\b"
    r"|\b(?:about\s+)?(?:nine|ten|eleven|twelve|one|two|three|four|five|six|seven|eight|\d{1,2})\s+(?:in\s+the\s+)?(?:morning|evening|afternoon|night)\b"
    # "It's about three in the afternoon now"
    r"|\b(?:about|around)\s+\w+\s+in\s+the\s+(?:morning|evening|afternoon)\b"
    # Past-cumulative reference like "for more than a week or two"
    r"|\bfor\s+more\s+than\s+a?\s*(?:week|month|year|day)s?\b"
    r"|\bfor\s+the\s+(?:past|last)\s+(?:few\s+)?(?:hour|day|week|month|year)s?\b"
    # "X has/have been (out|asleep|gone|here) for [duration]"
    r"|\b(?:has|have|'?ve|'?s)\s+been\s+"
    r"(?:out|asleep|gone|here|there|away|in|down|underground|missing|"
    r"resting|sleeping|knocked\s+out|unconscious)\s+for\b"
    # "X hours/minutes after/before/past [time-of-day]"
    r"|\b(?:" + _DURATION_NUM + r")\s+(?:hour|minute|day)s?\s+"
    r"(?:after|before|past|since)\s+"
    r"(?:sundown|sunrise|noon|midnight|dawn|dusk|sunset|daybreak|"
    r"breakfast|lunch|dinner|supper)\b"
    # "for almost a day" / "for almost X" cumulative duration
    r"|\bfor\s+almost\s+(?:a|an|" + _DURATION_NUM + r")\s+(?:hour|day|week|month|year)s?\b",
    re.I,
)

IN_SCENE_COMPRESSION_PHRASE = re.compile(
    # task-verb + duration
    r"\b(?:take|takes|took|taking|"
    r"spend|spends|spent|spending|"
    r"wait|waits|waited|waiting|"
    r"finish|finishes|finished|finishing|"
    r"work|works|worked|working|"
    r"scan|scans|scanned|scanning|"
    r"hammer|hammers|hammered|hammering|"
    r"sit|sits|sat|sitting|"
    r"rest|rests|rested|resting|"
    r"give|gives|gave|giving)"
    r"\s+(?:it\s+|him\s+|her\s+|them\s+|about\s+|for\s+|the\s+next\s+|the\s+better\s+part\s+of\s+)?"
    r"(?:" + _DURATION_NUM + r")?\s*"
    r"(?:minute|hour|day)s?\b"
    # "It takes (you) about X minutes/hours"
    r"|\bit\s+(?:does\s+)?takes?\s+(?:you\s+)?"
    r"(?:about\s+|the\s+better\s+part\s+of\s+|a\s+|an\s+)?"
    r"(?:" + _DURATION_NUM + r")?\s*(?:or\s+so\s+)?(?:minute|hour|day)s?\b"
    r"|\bit\s+will\s+take\s+(?:you\s+)?about\b"
    # "over the next X minutes/hours/days" (in-scene montage)
    r"|\bover\s+the\s+next\s+(?:" + _DURATION_NUM + r")?\s*(?:or\s+so\s+)?"
    r"(?:minute|hour|day)s?\b"
    # "spend the next X" / "spend N hours/minutes"
    r"|\bspend\s+(?:the\s+next\s+)?(?:" + _DURATION_NUM + r")?\s*(?:minute|hour|day)s?\b"
    # "after about X minutes you finish"
    r"|\bafter\s+(?:about\s+)?(?:" + _DURATION_NUM + r")\s+(?:minute|hour)s?\b"
    # "for about X minutes" weak-fallback
    r"|\bfor\s+(?:about\s+)?(?:" + _DURATION_NUM + r")\s+(?:minute|hour)s?\b"
    # "within an hour" / "within X minutes"
    r"|\bwithin\s+(?:about\s+)?(?:" + _DURATION_NUM + r")\s+(?:minute|hour|day)s?\b"
    # "X minutes/hours before [event]"
    r"|\b(?:" + _DURATION_NUM + r")\s+(?:minute|hour|day)s?\s+(?:before|until)\b"
    # "you emerge a little over an hour or so of doing this"
    r"|\b(?:emerge|complete|conclude|wrap\s+up|move\s+on)\s+(?:a\s+little\s+)?"
    r"(?:over\s+|after\s+)?"
    r"(?:" + _DURATION_NUM + r")\s+(?:minute|hour|day)s?\b"
    ,
    re.I,
)


def is_cumulative_anchor_phrase(text):
    """Used for the D7 exception in Stage 0."""
    return CUMULATIVE_ANCHOR_PHRASE.search(text) is not None


def classify_phrase(turn_text, phrase_text, phrase_span,
                    is_npc_dialogue_present=False):
    """Return (category, unknown_shape).

    Each phrase classifies independently. The phrase + surrounding ±200 char
    window is the search surface. Priority order: scene_transition >
    travel_duration > cumulative_anchor > in_scene_compression. Falls
    through to (None, True) if none match — per Lesson 2, no default
    catchall.

    Patch 2 (v1.2): if the turn carries `is_npc_dialogue_present`, route the
    phrase to UNKNOWN_SHAPE unless the phrase falls in Matt-narration.
    """
    start, end = phrase_span

    # Patch 2: NPC routing. If the turn has NPC dialogue AND the phrase
    # itself falls inside an NPC quote / voicing span → route to
    # UNKNOWN_SHAPE.
    if is_npc_dialogue_present and is_phrase_in_npc_speech(turn_text, start, end):
        return None, True

    win_start = max(0, start - 200)
    win_end = min(len(turn_text), end + 200)
    window = turn_text[win_start:win_end]

    # Priority 1: scene_transition. The phrase itself or the window contains
    # transition vocabulary.
    if SCENE_TRANSITION_PHRASE.search(phrase_text) or SCENE_TRANSITION_PHRASE.search(window):
        return "scene_transition", False

    # Priority 2: travel_duration. Either the phrase is a travel phrase, or
    # the phrase is a numeric duration AND a travel verb appears in the
    # window.
    if TRAVEL_PHRASE.search(window):
        return "travel_duration", False
    if _is_numeric_duration(phrase_text) and TRAVEL_VERB.search(window):
        return "travel_duration", False

    # Priority 3: cumulative_anchor — patch 3 temporal-context check.
    if CUMULATIVE_ANCHOR_PHRASE.search(phrase_text) or CUMULATIVE_ANCHOR_PHRASE.search(window):
        if cumulative_anchor_has_temporal_context(turn_text, start, end):
            return "cumulative_anchor", False
        # Pattern fired but no temporal context in same sentence — route to
        # UNKNOWN_SHAPE per Patch 3.

    # Priority 4: in_scene_compression.
    if IN_SCENE_COMPRESSION_PHRASE.search(phrase_text) or IN_SCENE_COMPRESSION_PHRASE.search(window):
        return "in_scene_compression", False

    # No match — emit with unknown_shape=true per Lesson 2.
    return None, True


_NUMERIC_DURATION_RE = re.compile(
    r"^" + _DURATION_NUM + r"\s+" + _DURATION_UNIT + r"$",
    re.I,
)


def _is_numeric_duration(phrase_text):
    return bool(_NUMERIC_DURATION_RE.match(phrase_text.strip()))


# ---------------------------------------------------------------------------
# Stage 3 — anchor resolution (15-turn back-walk)
# ---------------------------------------------------------------------------
#
# Per §6 + §11.2 lock. Triggers containing relative-time phrases set
# is_anchored=True; the extractor walks back ANCHOR_WALK_BACK_TURNS turns
# for the most-recent prior time-mention or rest declaration.

ANCHORED_PHRASE = re.compile(
    r"\bthe\s+(?:next|following)\s+(?:morning|day|night|evening|afternoon)\b"
    r"|\b(?:moments?|minutes?|hours?|days?)\s+later\b"
    r"|\b\d+\s+(?:or\s+so\s+)?(?:minute|hour|day)s?\s+later\b"
    r"|\blater\s+(?:that|on|in)\b"
    r"|\bsome\s+time\s+later\b|\bshortly\s+(?:after|later)\b"
    r"|\bafter\s+(?:that|a\s+while)\b"
    r"|\bby\s+the\s+time\s+you\b",
    re.I,
)

ANCHOR_CANDIDATE_VOCAB = re.compile(
    # Prior time-mention or rest declaration that could serve as anchor.
    r"\b(?:long|short)\s+rest\b"
    r"|\byou\s+(?:bed|rest|sleep|settle|camp)\b"
    r"|\bmake\s+camp\b"
    r"|\bfor\s+the\s+night\b"
    r"|\bgo\s+to\s+sleep\b"
    r"|\b(?:in|during)\s+the\s+(?:morning|evening|afternoon)\b"
    r"|\bit'?s\s+(?:morning|evening|night|afternoon|dawn|dusk|noon|midnight)\b"
    r"|\b(?:we\s+left|left)\s+off\s+(?:with|at)\b",
    re.I,
)


def is_anchored_phrase(phrase_text):
    return ANCHORED_PHRASE.search(phrase_text) is not None


def resolve_anchor(turns, trigger_idx, walk_back=ANCHOR_WALK_BACK_TURNS):
    """Walk back up to `walk_back` turns for the most-recent prior anchor
    candidate. Return (anchor_turn_number, anchor_distance_turns) or
    (None, None) if no anchor found within window.
    """
    start = max(0, trigger_idx - walk_back)
    trigger_turn_number = turns[trigger_idx]["number"]
    for j in range(trigger_idx - 1, start - 1, -1):
        t = turns[j]
        if ANCHOR_CANDIDATE_VOCAB.search(t["text"]):
            return t["number"], trigger_turn_number - t["number"]
        # An earlier time-mention phrase also serves as anchor.
        if t["speaker"] == "MATT" and TIME_TRIGGER.search(t["text"]):
            return t["number"], trigger_turn_number - t["number"]
    return None, None


# ---------------------------------------------------------------------------
# Stage 4 — granularity bucket
# ---------------------------------------------------------------------------

GRANULARITY_PATTERNS = [
    ("years", re.compile(r"\byears?\b", re.I)),
    ("months", re.compile(r"\bmonths?\b", re.I)),
    ("weeks", re.compile(r"\bweeks?\b", re.I)),
    ("days", re.compile(r"\b(?:days?|nights?|morning|evening|afternoon|"
                        r"noon|midnight|dawn|dusk|sunset|sunrise|nightfall|"
                        r"daybreak|sundown)\b", re.I)),
    ("hours", re.compile(r"\bhours?\b", re.I)),
    ("minutes", re.compile(r"\bminutes?\b", re.I)),
    ("rounds", re.compile(r"\brounds?\b", re.I)),
]


def derive_granularity(phrase_text, window_text):
    """Largest unit wins. Search phrase first, then surrounding window.
    Returns a granularity bucket name or 'unspecified'.
    """
    for bucket, pattern in GRANULARITY_PATTERNS:
        if pattern.search(phrase_text):
            return bucket
    for bucket, pattern in GRANULARITY_PATTERNS:
        if pattern.search(window_text):
            return bucket
    return "unspecified"


# ---------------------------------------------------------------------------
# Episode loading (copied from encounter_cadence.py — same source format)
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
    """Walk back from trigger_idx-1 accumulating turns until char_budget
    exceeded. Returns:
      preceding_turns: list of {speaker, text, turn_number} oldest-first
      total_chars
      most_recent_non_matt_turn: dict or None
    """
    pre_reversed = []
    used = 0
    most_recent_non_matt = None
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
        if most_recent_non_matt is None and t["speaker"] != "MATT":
            most_recent_non_matt = entry
        used += text_len

    return list(reversed(pre_reversed)), used, most_recent_non_matt


# ---------------------------------------------------------------------------
# Episode processing
# ---------------------------------------------------------------------------

def dedup_turn_records(turn_records, turn_text):
    """Patch 1 (v1.2). Suppress duplicate records emitted from the same turn
    when phrases describe the same fictional moment.

    Two grouping rules. A later record is suppressed if it shares a group
    with any earlier (kept) record:
      A. Same-sentence proximity: both phrases are inside the SAME sentence
         AND their spans are within 80 chars of each other.
      B. Same-category-and-anchor: same `category` (including null for
         unknown_shape), same `time_anchor_turn_number` (or both null),
         AND span-gap within 200 chars.

    Different categories always survive (e.g., scene_transition +
    cumulative_anchor in same turn). After suppression, surviving records'
    `same_turn_record_index` is renumbered contiguously 0..N-1.
    """
    if len(turn_records) <= 1:
        return turn_records

    # Annotate each with its sentence span.
    annotated = []
    for r in turn_records:
        s = r["_phrase_start"]
        e = r["_phrase_end"]
        sent_start, sent_end = get_sentence_span(turn_text, s, e)
        annotated.append((r, sent_start, sent_end))

    suppressed = set()
    for i in range(len(annotated)):
        if i in suppressed:
            continue
        ri, sent_si, sent_ei = annotated[i]
        for j in range(i + 1, len(annotated)):
            if j in suppressed:
                continue
            rj, sent_sj, sent_ej = annotated[j]
            gap = rj["_phrase_start"] - ri["_phrase_end"]

            # Rule A: same sentence + within 80 chars.
            if sent_si == sent_sj and 0 <= gap <= 80:
                suppressed.add(j)
                continue
            # Rule B: same category + same anchor + within 200 chars.
            if (
                ri["category"] == rj["category"]
                and ri["time_anchor_turn_number"] == rj["time_anchor_turn_number"]
                and 0 <= gap <= 200
            ):
                suppressed.add(j)

    surviving = [annotated[i][0] for i in range(len(annotated)) if i not in suppressed]
    # Renumber same_turn_record_index.
    for new_idx, r in enumerate(surviving):
        r["same_turn_record_index"] = new_idx
    return surviving


def process_episode(episode_id, extracted_at):
    """Process one episode. Return list of records."""
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
        # §11.3 lock — MATT-only triggers.
        if t["speaker"] != "MATT":
            continue

        # Stage 1 — find all candidate phrases in this turn.
        matches = list(TIME_TRIGGER.finditer(t["text"]))
        if not matches:
            continue

        # Find immediately-prior non-MATT turn (for D7).
        prev_non_matt = None
        for j in range(idx - 1, -1, -1):
            if turns[j]["speaker"] != "MATT":
                prev_non_matt = turns[j]
                break

        # Stage 0 turn-level — runs once per turn; all phrases share outcome.
        stage_0, stage_0_reason = stage_0_classify(t["text"], None, prev_non_matt)
        if stage_0 == "DISCOURSE":
            log_filtered_discourse(t["text"], stage_0_reason, episode_id, t["number"])
            continue

        # STATE flags (turn-level).
        is_combat_state = derive_combat_state(turns, idx)
        is_recap_state = derive_recap_state(turns, idx, total_turns)
        is_npc_dialogue_present = has_npc_dialogue(t["text"])

        # Preceding context (per spec §6: 800-char budget).
        preceding_turns, preceding_chars, _ = gather_preceding_context(
            turns, idx, PRECEDING_CONTEXT_BUDGET
        )

        # Anchor resolution (computed once per turn — all phrases in the same
        # turn share the same anchor).
        anchor_turn_num = None
        anchor_distance = None
        any_anchored = any(is_anchored_phrase(m.group(0)) for m in matches)
        if any_anchored:
            anchor_turn_num, anchor_distance = resolve_anchor(turns, idx)

        episode_position_pct = round(idx / total_turns, 4) if total_turns else 0.0

        # Emit one record per phrase. Per-phrase D8 causal-since filter
        # runs first; suppressed phrases never enter the dedup pool.
        turn_records = []
        same_turn_idx = 0
        for m in matches:
            phrase = m.group(0)
            phrase_span = (m.start(), m.end())

            # Patch 3 (D8): per-phrase causal-since filter. When the phrase
            # contains "since" AND the trigger sentence matches the
            # causal-since pattern, drop the phrase as DISCOURSE-equivalent.
            if "since" in phrase.lower():
                sent_start, sent_end = get_sentence_span(
                    t["text"], m.start(), m.end()
                )
                if DISCOURSE_CAUSAL_SINCE.search(t["text"][sent_start:sent_end]):
                    log_filtered_discourse(
                        t["text"], f"D8_causal_since :: {phrase!r}",
                        episode_id, t["number"]
                    )
                    continue

            category, unknown_shape = classify_phrase(
                t["text"], phrase, phrase_span,
                is_npc_dialogue_present=is_npc_dialogue_present,
            )
            if unknown_shape:
                log_unknown_shape(t["text"], episode_id, t["number"], phrase)

            # Granularity: phrase + ±200 char window.
            win_start = max(0, m.start() - 200)
            win_end = min(len(t["text"]), m.end() + 200)
            window_text = t["text"][win_start:win_end]
            granularity = derive_granularity(phrase, window_text)

            phrase_anchored = is_anchored_phrase(phrase)

            record = {
                "campaign": campaign,
                "episode": episode_num,
                "episode_position_pct": episode_position_pct,
                "speaker": "MATT",
                "event_type": "time_mention",
                "raw_text": t["text"],
                "preceding_context_chars": preceding_chars,
                "extractor_version": EXTRACTOR_VERSION,
                "extracted_at": extracted_at,

                "trigger_turn_number": t["number"],
                "trigger_phrase": phrase,
                "category": category,
                "granularity_bucket": granularity,
                "is_anchored": phrase_anchored,
                "time_anchor_turn_number": (
                    anchor_turn_num if phrase_anchored else None
                ),
                "anchor_distance_turns": (
                    anchor_distance if phrase_anchored else None
                ),
                "is_combat_state": is_combat_state,
                "is_recap_state": is_recap_state,
                "is_npc_dialogue_present": is_npc_dialogue_present,
                "unknown_shape": unknown_shape,
                "same_turn_record_index": same_turn_idx,
                "preceding_turns": preceding_turns,
                # Internal fields used by the dedup pass; stripped before emit.
                "_phrase_start": m.start(),
                "_phrase_end": m.end(),
            }
            turn_records.append(record)
            same_turn_idx += 1

        # Patch 1 dedup pass.
        turn_records = dedup_turn_records(turn_records, t["text"])
        # Strip internal fields and append.
        for r in turn_records:
            r.pop("_phrase_start", None)
            r.pop("_phrase_end", None)
            records.append(r)

    return records


# ---------------------------------------------------------------------------
# CLI
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
