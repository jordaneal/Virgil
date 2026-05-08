#!/usr/bin/env python3
"""
patch_phase1_3_scene_state.py
─────────────────────────────────────────────────────────
Phase 1.3 — Scene State.

Adds:

  1. dnd_scene_state SQLite table.
     Columns: campaign_id (PK), location, mode, focus,
     established_details (JSON), active_npcs (JSON),
     active_threats (JSON), open_questions (JSON), tension,
     last_player_action, last_scene_change, updated_at.

  2. dnd_engine.py:
     - get_scene_state(campaign_id) → dict | None
     - update_scene_state(campaign_id, **kwargs) → merges JSON fields
     - init_scene_state(campaign_id, seed) → seeds the table
     - extract_scene_updates(player_action, dm_response, prev_state) →
       lightweight LLM call that returns a structured update dict
     - dm_respond reads scene state, passes it to build_dm_context,
       and triggers extract_scene_updates after the DM response (in
       a thread so it doesn't block).
     - build_dm_context renders SCENE STATE as a block and adds the
       two key rules: "do not re-describe established details" and
       "narrate FORWARD from last_player_action".

  3. discord_dnd_bot.py:
     - /play seeds the scene state with the opening scene.

Idempotent. Backs up + syntax checks both files.
"""

import re
import ast
import datetime
from pathlib import Path

ENGINE = Path('/home/jordaneal/scripts/dnd_engine.py')
BOT = Path('/home/jordaneal/scripts/discord_dnd_bot.py')

engine_orig = ENGINE.read_text()
bot_orig = BOT.read_text()
engine_src = engine_orig
bot_src = bot_orig


# ─────────────────────────────────────────────────────────
# 1. dnd_engine.py — add scene state table to db_init
# ─────────────────────────────────────────────────────────

OLD_DB_INIT_END = '''    if 'tone' not in cols:
        conn.execute("ALTER TABLE dnd_campaigns ADD COLUMN tone TEXT DEFAULT ''")
    conn.commit()
    conn.close()'''

NEW_DB_INIT_END = '''    if 'tone' not in cols:
        conn.execute("ALTER TABLE dnd_campaigns ADD COLUMN tone TEXT DEFAULT ''")

    # Scene state (Phase 1.3)
    conn.execute("""CREATE TABLE IF NOT EXISTS dnd_scene_state (
        campaign_id INTEGER PRIMARY KEY,
        location TEXT DEFAULT '',
        mode TEXT DEFAULT 'exploration',
        focus TEXT DEFAULT '',
        established_details TEXT DEFAULT '[]',
        active_npcs TEXT DEFAULT '[]',
        active_threats TEXT DEFAULT '[]',
        open_questions TEXT DEFAULT '[]',
        tension TEXT DEFAULT 'low',
        last_player_action TEXT DEFAULT '',
        last_scene_change TEXT DEFAULT '',
        updated_at TEXT DEFAULT ''
    )""")
    conn.commit()
    conn.close()'''

if NEW_DB_INIT_END in engine_src:
    print("[skip] dnd_scene_state table already in db_init")
elif OLD_DB_INIT_END in engine_src:
    engine_src = engine_src.replace(OLD_DB_INIT_END, NEW_DB_INIT_END)
    print("[ok] db_init: dnd_scene_state table added")
else:
    raise SystemExit("[FAIL] db_init end block not matched")


# ─────────────────────────────────────────────────────────
# 2. dnd_engine.py — add scene state helpers BEFORE classify_action_type
# ─────────────────────────────────────────────────────────

SCENE_HELPERS_MARKER = "def get_scene_state"
SCENE_HELPERS = '''def get_scene_state(campaign_id: int):
    """Return scene state dict for the campaign, or None."""
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT location, mode, focus, established_details, active_npcs, "
        "active_threats, open_questions, tension, last_player_action, "
        "last_scene_change, updated_at FROM dnd_scene_state WHERE campaign_id=?",
        (campaign_id,)
    ).fetchone()
    conn.close()
    if not row:
        return None
    import json
    return {
        'campaign_id': campaign_id,
        'location': row[0] or '',
        'mode': row[1] or 'exploration',
        'focus': row[2] or '',
        'established_details': json.loads(row[3] or '[]'),
        'active_npcs': json.loads(row[4] or '[]'),
        'active_threats': json.loads(row[5] or '[]'),
        'open_questions': json.loads(row[6] or '[]'),
        'tension': row[7] or 'low',
        'last_player_action': row[8] or '',
        'last_scene_change': row[9] or '',
        'updated_at': row[10] or '',
    }


def init_scene_state(campaign_id: int, seed: str = ''):
    """Create or replace the scene state for a campaign with a seed."""
    import json
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT OR REPLACE INTO dnd_scene_state "
        "(campaign_id, location, mode, focus, established_details, active_npcs, "
        "active_threats, open_questions, tension, last_player_action, "
        "last_scene_change, updated_at) "
        "VALUES (?, '', 'exploration', '', '[]', '[]', '[]', '[]', 'low', '', ?, ?)",
        (campaign_id, seed[:500], datetime.datetime.now().isoformat())
    )
    conn.commit()
    conn.close()
    log(f"scene state initialized for campaign {campaign_id}")


def update_scene_state(campaign_id: int, **kwargs):
    """Update one or more scene state fields. JSON list fields (established_details,
    active_npcs, active_threats, open_questions) get MERGED with existing values
    (deduped, order preserved). Scalar fields (location, mode, focus, tension,
    last_player_action, last_scene_change) get REPLACED."""
    import json
    JSON_LIST_FIELDS = {'established_details', 'active_npcs', 'active_threats', 'open_questions'}
    SCALAR_FIELDS = {'location', 'mode', 'focus', 'tension', 'last_player_action', 'last_scene_change'}

    current = get_scene_state(campaign_id)
    if current is None:
        # No row yet — auto-seed empty
        init_scene_state(campaign_id, seed='')
        current = get_scene_state(campaign_id)

    sets = []
    values = []
    for key, val in kwargs.items():
        if key in JSON_LIST_FIELDS:
            existing = current.get(key, [])
            if isinstance(val, str):
                val = [val]
            for item in val:
                if item and item not in existing:
                    existing.append(item)
            # Cap each list at 20 items so it doesn't bloat
            existing = existing[-20:]
            sets.append(f"{key}=?")
            values.append(json.dumps(existing))
        elif key in SCALAR_FIELDS:
            sets.append(f"{key}=?")
            values.append(str(val)[:1000])
        else:
            log(f"update_scene_state: ignoring unknown field {key}")
    if not sets:
        return

    sets.append("updated_at=?")
    values.append(datetime.datetime.now().isoformat())
    values.append(campaign_id)

    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        f"UPDATE dnd_scene_state SET {', '.join(sets)} WHERE campaign_id=?",
        values
    )
    conn.commit()
    conn.close()


def extract_scene_updates(campaign_id: int, player_action: str, dm_response: str):
    """After a DM turn, run a lightweight LLM call to extract structured
    updates from the (player_action, dm_response) pair and merge them into
    scene state. Runs in a thread so it doesn't block the next turn."""
    import json
    current = get_scene_state(campaign_id) or {}
    extraction_prompt = f"""You extract structured scene-state updates from a D&D play exchange.

Current scene state:
- Location: {current.get('location') or '(unknown)'}
- Focus: {current.get('focus') or '(unknown)'}
- Tension: {current.get('tension') or 'low'}
- Mode: {current.get('mode') or 'exploration'}
- Already-established details: {', '.join(current.get('established_details') or []) or '(none)'}
- Active NPCs: {', '.join(current.get('active_npcs') or []) or '(none)'}

Player just said: "{player_action}"

The DM just replied:
\"\"\"
{dm_response[:1500]}
\"\"\"

Output ONLY valid JSON, no commentary. Use this exact schema (omit fields that did NOT change):
{{
  "location": "<short label of current location, only if it changed>",
  "focus": "<what the scene currently centers on, only if it changed>",
  "tension": "<low|rising|high|combat, only if it changed>",
  "new_established_details": ["<short detail 1>", "..."],
  "new_npcs": ["<NPC name 1>", "..."],
  "new_threats": ["<threat 1>", "..."],
  "new_open_questions": ["<question 1>", "..."],
  "last_scene_change": "<one short sentence: what materially changed this turn>"
}}

Rules:
- Be terse. Each list item should be 1-6 words.
- Only include details the DM EXPLICITLY mentioned. Do not infer.
- Do not repeat already-established details.
- If nothing meaningful changed, return {{}}.
"""
    try:
        response, _ = route(
            messages=[{"role": "user", "content": extraction_prompt}],
            task_type="dnd",
            system_prompt="You output structured JSON only. No prose.",
        )
        # Attempt to strip code fences if present
        body = response.strip()
        if body.startswith("```"):
            body = re.sub(r"^```(?:json)?\\s*", "", body)
            body = re.sub(r"\\s*```$", "", body)
        # Find the first { ... } block
        m = re.search(r"\\{.*\\}", body, re.DOTALL)
        if not m:
            log("extract_scene_updates: no JSON in response")
            return
        data = json.loads(m.group(0))
    except Exception as e:
        log(f"extract_scene_updates parse error: {e}")
        return

    if not data:
        return

    update_kwargs = {'last_player_action': player_action[:500]}
    if 'location' in data and data['location']:
        update_kwargs['location'] = data['location']
    if 'focus' in data and data['focus']:
        update_kwargs['focus'] = data['focus']
    if 'tension' in data and data['tension'] in ('low', 'rising', 'high', 'combat'):
        update_kwargs['tension'] = data['tension']
    if 'last_scene_change' in data and data['last_scene_change']:
        update_kwargs['last_scene_change'] = data['last_scene_change']
    if data.get('new_established_details'):
        update_kwargs['established_details'] = data['new_established_details']
    if data.get('new_npcs'):
        update_kwargs['active_npcs'] = data['new_npcs']
    if data.get('new_threats'):
        update_kwargs['active_threats'] = data['new_threats']
    if data.get('new_open_questions'):
        update_kwargs['open_questions'] = data['new_open_questions']

    update_scene_state(campaign_id, **update_kwargs)
    log(f"scene state updated: {list(update_kwargs.keys())}")


'''

if SCENE_HELPERS_MARKER not in engine_src:
    anchor = "def classify_action_type"
    if anchor not in engine_src:
        raise SystemExit("[FAIL] classify_action_type anchor missing")
    engine_src = engine_src.replace(anchor, SCENE_HELPERS + anchor, 1)
    print("[ok] scene state helpers added")
else:
    print("[skip] scene state helpers already present")


# ─────────────────────────────────────────────────────────
# 3. dnd_engine.py — wire scene state into dm_respond
# ─────────────────────────────────────────────────────────

OLD_DM_RESPOND_HEAD = '''def dm_respond(campaign, characters, player_action, avrae_events=None,
                acting_character_name: str = ""):
    """Run one DM turn. Returns response string. Roll-or-not decided by
    the orchestration engine, not the prompt."""
    character_ctx = None'''

NEW_DM_RESPOND_HEAD = '''def dm_respond(campaign, characters, player_action, avrae_events=None,
                acting_character_name: str = ""):
    """Run one DM turn. Returns response string. Roll-or-not decided by
    the orchestration engine, not the prompt."""
    scene_state = get_scene_state(campaign['id'])
    character_ctx = None'''

if NEW_DM_RESPOND_HEAD in engine_src:
    print("[skip] dm_respond already loads scene state")
elif OLD_DM_RESPOND_HEAD in engine_src:
    engine_src = engine_src.replace(OLD_DM_RESPOND_HEAD, NEW_DM_RESPOND_HEAD)
    print("[ok] dm_respond: loads scene state")
else:
    raise SystemExit("[FAIL] dm_respond head not matched")


# Pass scene_state into build_dm_context
OLD_BUILD_CALL = '''    system = build_dm_context(
        campaign, characters,
        relevant_history=relevant,
        dm_guidance=guidance,
        action_type=intent,
        avrae_events=avrae_events,
        character_context=character_ctx,
        roll_decision=roll_decision,
        mode=mode,
    )'''

NEW_BUILD_CALL = '''    system = build_dm_context(
        campaign, characters,
        relevant_history=relevant,
        dm_guidance=guidance,
        action_type=intent,
        avrae_events=avrae_events,
        character_context=character_ctx,
        roll_decision=roll_decision,
        mode=mode,
        scene_state=scene_state,
    )'''

if NEW_BUILD_CALL in engine_src:
    print("[skip] build_dm_context call already passes scene_state")
elif OLD_BUILD_CALL in engine_src:
    engine_src = engine_src.replace(OLD_BUILD_CALL, NEW_BUILD_CALL)
    print("[ok] build_dm_context call: scene_state passed")
else:
    raise SystemExit("[FAIL] build_dm_context call not matched")


# After the DM response succeeds, kick off the scene update extraction in a thread
OLD_RETURN = '''        response, _ = route(
            messages=[{"role": "user", "content": player_action}],
            task_type="dnd",
            system_prompt=system,
        )
        return response
    except Exception as e:
        log(f"dm_respond error: {e}")
        return f"DM error: {e}"'''

NEW_RETURN = '''        response, _ = route(
            messages=[{"role": "user", "content": player_action}],
            task_type="dnd",
            system_prompt=system,
        )
        # Fire-and-forget scene state update (don't block the next turn)
        try:
            threading.Thread(
                target=extract_scene_updates,
                args=(campaign['id'], player_action, response),
                daemon=True,
            ).start()
        except Exception as e:
            log(f"scene update thread launch failed: {e}")
        return response
    except Exception as e:
        log(f"dm_respond error: {e}")
        return f"DM error: {e}"'''

if NEW_RETURN in engine_src:
    print("[skip] dm_respond already triggers scene updates")
elif OLD_RETURN in engine_src:
    engine_src = engine_src.replace(OLD_RETURN, NEW_RETURN)
    print("[ok] dm_respond: triggers scene update extraction")
else:
    raise SystemExit("[FAIL] dm_respond return block not matched")


# ─────────────────────────────────────────────────────────
# 4. dnd_engine.py — build_dm_context accepts and renders scene_state
# ─────────────────────────────────────────────────────────

OLD_BUILD_SIG = '''def build_dm_context(campaign, characters, relevant_history="", dm_guidance="",
                     action_type="", avrae_events=None,
                     character_context=None, roll_decision=None, mode="exploration"):'''

NEW_BUILD_SIG = '''def build_dm_context(campaign, characters, relevant_history="", dm_guidance="",
                     action_type="", avrae_events=None,
                     character_context=None, roll_decision=None, mode="exploration",
                     scene_state=None):'''

if NEW_BUILD_SIG in engine_src:
    print("[skip] build_dm_context already takes scene_state")
elif OLD_BUILD_SIG in engine_src:
    engine_src = engine_src.replace(OLD_BUILD_SIG, NEW_BUILD_SIG)
    print("[ok] build_dm_context: signature accepts scene_state")
else:
    raise SystemExit("[FAIL] build_dm_context signature not matched")


# Inject the scene_state rendering and the new prompt rules
OLD_MODE_BLOCK = '''    mode_block = f"\\n\\n=== CURRENT MODE ===\\n{mode}"'''

NEW_MODE_BLOCK = '''    mode_block = f"\\n\\n=== CURRENT MODE ===\\n{mode}"

    scene_state_section = ""
    if scene_state:
        details = scene_state.get('established_details') or []
        npcs = scene_state.get('active_npcs') or []
        threats = scene_state.get('active_threats') or []
        questions = scene_state.get('open_questions') or []
        scene_state_section = (
            "\\n\\n=== SCENE STATE (authoritative — do not contradict) ===\\n"
            f"Location: {scene_state.get('location') or '(not yet set)'}\\n"
            f"Focus: {scene_state.get('focus') or '(not yet set)'}\\n"
            f"Tension: {scene_state.get('tension') or 'low'}\\n"
            f"Established details: {', '.join(details) if details else '(none yet)'}\\n"
            f"Active NPCs: {', '.join(npcs) if npcs else '(none)'}\\n"
            f"Active threats: {', '.join(threats) if threats else '(none)'}\\n"
            f"Open questions: {', '.join(questions) if questions else '(none)'}\\n"
            f"Last player action: {scene_state.get('last_player_action') or '(this is the first turn)'}\\n"
            f"Last scene change: {scene_state.get('last_scene_change') or '(scene just opened)'}"
        )'''

if NEW_MODE_BLOCK in engine_src:
    print("[skip] scene_state_section already rendered")
elif OLD_MODE_BLOCK in engine_src:
    engine_src = engine_src.replace(OLD_MODE_BLOCK, NEW_MODE_BLOCK)
    print("[ok] scene_state_section rendered")
else:
    raise SystemExit("[FAIL] mode_block not matched in build_dm_context")


# Add scene_state_section to the prompt body and add the new rules
OLD_BODY_HEAD = '''=== CURRENT SCENE ===
{campaign.get('current_scene') or 'The adventure is just beginning.'}{mode_block}{char_ctx_section}{history_section}{guidance_section}{avrae_section}{roll_directive}'''

NEW_BODY_HEAD = '''=== CURRENT SCENE ===
{campaign.get('current_scene') or 'The adventure is just beginning.'}{mode_block}{scene_state_section}{char_ctx_section}{history_section}{guidance_section}{avrae_section}{roll_directive}'''

if NEW_BODY_HEAD in engine_src:
    print("[skip] prompt body already includes scene_state_section")
elif OLD_BODY_HEAD in engine_src:
    engine_src = engine_src.replace(OLD_BODY_HEAD, NEW_BODY_HEAD)
    print("[ok] prompt body: scene_state_section inserted")
else:
    raise SystemExit("[FAIL] prompt body head not matched")


# Add the two key rules about scene state usage
OLD_LENGTH_RULE = '''=== LENGTH (MANDATORY) ===

Maximum 2 short paragraphs. Maximum 6 sentences total. Brevity is mandatory.'''

NEW_LENGTH_RULE = '''=== SCENE STATE RULES (MANDATORY) ===

The SCENE STATE block above is authoritative. Use it to keep continuity:
- Do NOT re-describe established details unless the player specifically examines them, they materially change, or they become relevant again.
- Do NOT re-establish atmosphere every turn. The cave was described once. Move forward.
- Do NOT contradict the location, focus, NPCs, or threats listed there.
- Narrate FORWARD from "Last player action". Advance the moment. Reveal something new, or apply a consequence, or push for a decision.

=== LENGTH (MANDATORY) ===

Maximum 2 short paragraphs. Maximum 6 sentences total. Brevity is mandatory.
After the first turn in a scene, prefer 1 short paragraph. The reader already knows where they are.'''

if NEW_LENGTH_RULE in engine_src:
    print("[skip] scene state rules already added")
elif OLD_LENGTH_RULE in engine_src:
    engine_src = engine_src.replace(OLD_LENGTH_RULE, NEW_LENGTH_RULE)
    print("[ok] scene state rules added before length rule")
else:
    raise SystemExit("[FAIL] length rule block not matched")


# ─────────────────────────────────────────────────────────
# 5. discord_dnd_bot.py — /play seeds scene state
# ─────────────────────────────────────────────────────────

# Update the import to include init_scene_state
OLD_IMPORT = '''from dnd_engine import (
    db_init, chroma_init, chroma_store, dm_respond,
    get_active_campaign, get_characters, get_character_by_controller,
    create_campaign, bind_character, update_scene, list_campaigns,
    log,
)'''

NEW_IMPORT = '''from dnd_engine import (
    db_init, chroma_init, chroma_store, dm_respond,
    get_active_campaign, get_characters, get_character_by_controller,
    create_campaign, bind_character, update_scene, list_campaigns,
    init_scene_state,
    log,
)'''

if NEW_IMPORT in bot_src:
    print("[skip] init_scene_state already imported")
elif OLD_IMPORT in bot_src:
    bot_src = bot_src.replace(OLD_IMPORT, NEW_IMPORT)
    print("[ok] init_scene_state imported")
else:
    raise SystemExit("[FAIL] dnd_engine import block not matched")


# In /play, call init_scene_state(campaign['id'], seed) right before
# update_scene(...). Find the unique signature.
OLD_PLAY_SEED = '''    seed = scene or f"The party gathers, ready to begin {campaign['name']}."'''

NEW_PLAY_SEED = '''    seed = scene or f"The party gathers, ready to begin {campaign['name']}."
    init_scene_state(campaign['id'], seed)'''

if NEW_PLAY_SEED in bot_src:
    print("[skip] /play already seeds scene state")
elif OLD_PLAY_SEED in bot_src:
    bot_src = bot_src.replace(OLD_PLAY_SEED, NEW_PLAY_SEED)
    print("[ok] /play seeds scene state")
else:
    raise SystemExit("[FAIL] /play seed line not matched")


# ─────────────────────────────────────────────────────────
# Syntax check both files
# ─────────────────────────────────────────────────────────

try:
    ast.parse(engine_src)
    print("[ok] dnd_engine.py syntax check passed")
except SyntaxError as e:
    raise SystemExit(f"[FAIL] dnd_engine.py syntax error: {e}")

try:
    ast.parse(bot_src)
    print("[ok] discord_dnd_bot.py syntax check passed")
except SyntaxError as e:
    raise SystemExit(f"[FAIL] discord_dnd_bot.py syntax error: {e}")


# ─────────────────────────────────────────────────────────
# Backup + write
# ─────────────────────────────────────────────────────────

stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')

ENGINE.with_suffix(f'.py.bak.{stamp}').write_text(engine_orig)
ENGINE.write_text(engine_src)
print(f"[ok] wrote {ENGINE}")

BOT.with_suffix(f'.py.bak.{stamp}').write_text(bot_orig)
BOT.write_text(bot_src)
print(f"[ok] wrote {BOT}")

print()
print("Next:")
print("  systemctl --user restart virgil-discord")
print("  journalctl --user -u virgil-discord -n 10 --no-pager")
print()
print("Then in Discord, restart your client and run a fresh test:")
print("  /newcampaign name:Phase 1.3 Test tone:classic high fantasy, dwarven hold")
print("  /bindchar  (Donovan)")
print("  /play scene:Donovan stands in a dim mountain cave at dusk. A heavy iron chest sits in the corner.")
print("Then in #dm-narration, repeat the four tests. Notice that 'I look around the cave'")
print("now does NOT re-describe the cave — it advances to what's NEW.")
