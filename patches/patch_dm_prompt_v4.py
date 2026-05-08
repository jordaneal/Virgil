#!/usr/bin/env python3
"""
patch_dm_prompt_v4.py
─────────────────────────────────────────────────────────
Triage patch addressing the cyberpunk-Tamriel tone bleed +
long-winded responses.

  1. dm_guidance (FIREBALL+CRD3 knowledge retrieval) is now
     CONTROLLED BY A FLAG. Default OFF. The knowledge base is
     polluting the tone — disable until we can verify clean.
     Re-enable later by setting USE_KNOWLEDGE_GUIDANCE = True.

  2. dm_respond() now passes max_tokens=600 to cap rambling.

  3. build_dm_context()'s SETTING & TONE block is duplicated:
     once at the TOP of the prompt and once at the BOTTOM as
     the final reminder before output. LLMs weight recency.

  4. Adds a hard length rule: "Max 2 paragraphs, 6 sentences
     total. Brevity is mandatory."

Idempotent. Backs up + syntax checks before writing.
"""

import re
import ast
import datetime
from pathlib import Path

ENGINE = Path('/home/jordaneal/scripts/dnd_engine.py')
engine_orig = ENGINE.read_text()
src = engine_orig


# ─────────────────────────────────────────────────────────
# 1. Add USE_KNOWLEDGE_GUIDANCE flag near the top
# ─────────────────────────────────────────────────────────

FLAG_MARKER = "USE_KNOWLEDGE_GUIDANCE"
FLAG_BLOCK = '''# ─────────────────────────────────────────────────────────
# Feature flags
# ─────────────────────────────────────────────────────────

# When True, retrieves narrative exemplars from the 740k FIREBALL+CRD3
# corpus and injects them into the DM prompt. When False, the DM relies
# on the prompt + chroma_search (per-campaign history) only.
#
# Disabled because the corpus pollutes the tone — exemplars from
# unrelated game settings bleed into our scenes (e.g. Elder Scrolls /
# cyberpunk language appearing in a high-fantasy game). Re-enable once
# the corpus is curated or filtered properly.
USE_KNOWLEDGE_GUIDANCE = False


'''

if FLAG_MARKER not in src:
    # Insert right after the LOG_PATH constant block (top of file)
    anchor = "LOG_PATH = Path('/mnt/virgil_storage/digest/dnd_engine.log')\n"
    if anchor not in src:
        raise SystemExit("[FAIL] LOG_PATH anchor not found")
    src = src.replace(anchor, anchor + "\n" + FLAG_BLOCK, 1)
    print("[ok] inserted USE_KNOWLEDGE_GUIDANCE flag")
else:
    print("[skip] flag already present")


# ─────────────────────────────────────────────────────────
# 2. Replace dm_respond() to honor the flag and pass max_tokens
# ─────────────────────────────────────────────────────────

OLD_DM_RESPOND_RE = re.compile(
    r"def dm_respond\(campaign, characters, player_action, avrae_events=None\):.*?"
    r"return f\"DM error: \{e\}\"",
    re.DOTALL
)

NEW_DM_RESPOND = '''def dm_respond(campaign, characters, player_action, avrae_events=None):
    """Run one DM turn. avrae_events is a list of structured roll events from
    avrae_listener, possibly empty. Returns response string."""
    action_type = classify_action_type(player_action)
    scene_blurb = (campaign.get('current_scene') or '')[:200]

    # Summarise Avrae events for the secondary knowledge query so retrieval
    # picks up "DM reacting to a crit" style exemplars when relevant.
    avrae_summary = ""
    if avrae_events:
        bits = []
        for ev in avrae_events:
            if ev.get('nat') == 20:
                bits.append("critical success")
            elif ev.get('nat') == 1:
                bits.append("catastrophic failure")
            elif ev.get('crit'):
                bits.append("critical hit")
            kind = ev.get('kind')
            if kind:
                bits.append(kind)
        avrae_summary = " ".join(bits)

    relevant = chroma_search(campaign['id'], player_action)

    # Knowledge guidance is gated — see USE_KNOWLEDGE_GUIDANCE at top of file
    if USE_KNOWLEDGE_GUIDANCE:
        guidance = multi_query_knowledge_search(
            player_action, action_type, scene_blurb, avrae_summary
        )
    else:
        guidance = ""

    system = build_dm_context(
        campaign, characters,
        relevant_history=relevant,
        dm_guidance=guidance,
        action_type=action_type,
        avrae_events=avrae_events,
    )
    try:
        response, _ = route(
            messages=[{"role": "user", "content": player_action}],
            task_type="dnd",
            system_prompt=system,
            max_tokens=600,
        )
        return response
    except Exception as e:
        log(f"dm_respond error: {e}")
        return f"DM error: {e}"'''

m = OLD_DM_RESPOND_RE.search(src)
if not m:
    if "if USE_KNOWLEDGE_GUIDANCE:" in src:
        print("[skip] dm_respond already gated")
    else:
        raise SystemExit("[FAIL] dm_respond block not matched")
else:
    src = src[:m.start()] + NEW_DM_RESPOND + src[m.end():]
    print("[ok] dm_respond: gated + max_tokens=600")


# ─────────────────────────────────────────────────────────
# 3. Tighten build_dm_context — duplicate SETTING block, add length rule
# ─────────────────────────────────────────────────────────

BUILD_DM_RE = re.compile(
    r"def build_dm_context\([^)]*\):.*?(?=\ndef dm_respond\()",
    re.DOTALL
)

NEW_BUILD_DM = '''def build_dm_context(campaign, characters, relevant_history="", dm_guidance="",
                     action_type="", avrae_events=None):
    """Compose the system prompt that drives the DM LLM call."""
    if characters:
        char_summaries = "\\n".join(
            f"- {c['name']}: Level {c.get('level', 1)} "
            f"{(c.get('race') or '?').title()} {(c.get('class') or '?').title()}"
            for c in characters
        )
    else:
        char_summaries = "- (no bound characters yet — narrate broadly)"

    DEFAULT_TONE = (
        "Classic high fantasy D&D — medieval, magical, swords and spells. "
        "Taverns, dungeons, ancient ruins, gods, monsters, beasts. "
        "STRICTLY NO firearms, NO modern technology, NO neon, NO grav-cars, "
        "NO LED lights, NO holograms, NO cyberpunk elements, NO science fiction. "
        "STRICTLY NO Elder Scrolls / Tamriel / Cyrodiil / Dwemer references. "
        "STRICTLY NO Marvel, Pokemon, Star Wars, or other fictional-universe content. "
        "If the previous turn drifted into another genre, IGNORE it and stay in classic fantasy."
    )
    tone = (campaign.get('tone') or '').strip() or DEFAULT_TONE

    history_section = (
        f"\\n\\n=== RELEVANT PAST EVENTS ===\\n{relevant_history}"
        if relevant_history else ""
    )

    guidance_section = (
        f"\\n\\n=== HOW EXPERIENCED DMS HANDLE SIMILAR MOMENTS ===\\n"
        f"These excerpts are for ENERGY and PACING only. NEVER copy their "
        f"settings, character names, places, or specific details — only the "
        f"shape of how they advance a beat.\\n\\n"
        f"{dm_guidance}"
        if dm_guidance else ""
    )

    avrae_block = _format_avrae_events(avrae_events) if avrae_events else ""
    avrae_section = (
        f"\\n\\n=== MECHANICAL EVENTS (from Avrae, just rolled) ===\\n"
        f"{avrae_block}\\n"
        f"These rolls already happened. Narrate the OUTCOME in prose. "
        f"Do NOT re-ask for the roll. Do NOT quote the number."
        if avrae_block else ""
    )

    action_hint = (
        f"\\n\\nThe player's action looks like a **{action_type}**."
        if action_type and action_type != "general roleplay" else ""
    )

    return f"""You are the Dungeon Master for a D&D 5th Edition campaign called "{campaign['name']}".

=== SETTING & TONE (HARD CONSTRAINT — DO NOT VIOLATE) ===
{tone}

=== PARTY ===
{char_summaries}

=== CURRENT SCENE ===
{campaign.get('current_scene') or 'The adventure is just beginning.'}{history_section}{guidance_section}{avrae_section}

=== HOW THIS GAME WORKS ===

You and Avrae split the work cleanly:
- AVRAE handles ALL dice, sheets, HP, attacks, spells, saves, checks, initiative.
- YOU handle scene description, NPC dialogue, world reactions, pacing, story.

=== WHEN TO CALL FOR ROLLS ===

If the player declares an action whose outcome is uncertain (sneak, persuade, attack, perceive, climb, lie, intimidate, recall lore, pick a lock, etc.), CALL FOR THE APPROPRIATE ROLL and STOP. End your message with the call.

Examples:
  "Roll a Stealth check — `!check stealth`."
  "Make a Persuasion check — `!check persuasion`."
  "Roll initiative — `!init join`."
  "Make a Dexterity save — `!save dex`."

After calling for a roll, STOP. Do NOT narrate the outcome. Avrae will roll, the result will appear in the next turn's MECHANICAL EVENTS block, and THEN you narrate the consequence.

If the action does NOT need a roll, narrate normally without one.

=== READING MECHANICAL EVENTS ===

When MECHANICAL EVENTS are present, those rolls already happened. Narrate the OUTCOME — never re-ask for the roll, never quote the number.

- Total 17+ on a check = solid success. 25+ = exceptional. 5 or below = failure with consequence.
- Nat 20 = spectacular. Nat 1 = catastrophic.
- Damage in flesh: 1–3 a scratch, 4–9 a solid hit, 10–19 staggering, 20+ grievous.

=== OUT-OF-CHARACTER REQUESTS ===

If the player asks a meta-question ("how do I roll", "what should I check", "OOC:..."), DROP CHARACTER. Answer in *italics* with a short, helpful note. Then return to scene.

=== LENGTH (MANDATORY) ===

Maximum 2 paragraphs. Maximum 6 sentences total per response. Brevity is mandatory. If you can say it in one paragraph, do.

=== STRICT AVOID ===

Forbidden phrases: "the air clings", "silence is oppressive", "shadows seem to writhe", "shadows seem to twist", "the very [X]", "as if [X] itself was [Y]", "darkness seems to swallow", "your every move", "with calculated silence", "luminescent orbs", "neon-drenched", "grav-cars", "holographic", "kaleidoscope", "cacophony of", "swirling vortex".

Do NOT mix genres. Do NOT restate what the player said. Do NOT invent roll results. Do NOT pad atmosphere when story should advance.

=== OUTPUT FORMAT ===

Plain prose. **bold** for key names. *italics* for thought, whisper, or OOC asides.{action_hint}

=== FINAL TONE REMINDER (HARD CONSTRAINT) ===
{tone}
Stay in this register. If you are tempted to write neon, grav-cars, Tamriel, Dwemer, holograms, augmented anything — STOP and pick a fantasy alternative. Stone, candle, steel, leather, parchment, lantern."""


'''

m2 = BUILD_DM_RE.search(src)
if not m2:
    raise SystemExit("[FAIL] build_dm_context block not matched")
src = src[:m2.start()] + NEW_BUILD_DM + src[m2.end():]
print("[ok] build_dm_context: tightened, double-anchored tone, length rule")


# ─────────────────────────────────────────────────────────
# Syntax check
# ─────────────────────────────────────────────────────────

try:
    ast.parse(src)
    print("[ok] dnd_engine.py syntax check passed")
except SyntaxError as e:
    raise SystemExit(f"[FAIL] dnd_engine.py syntax error: {e}")


# ─────────────────────────────────────────────────────────
# Backup + write
# ─────────────────────────────────────────────────────────

stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
backup = ENGINE.with_suffix(f'.py.bak.{stamp}')
backup.write_text(engine_orig)
ENGINE.write_text(src)
print(f"[ok] wrote {ENGINE}")
print(f"[ok] backup {backup}")
print()
print("Next:")
print("  systemctl --user restart virgil-discord")
print("  journalctl --user -u virgil-discord -n 10 --no-pager")
