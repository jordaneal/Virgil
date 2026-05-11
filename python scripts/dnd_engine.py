#!/usr/bin/env python3
"""
Virgil DnD Engine — narrative core only.

Replaces dnd_bot.py. Avrae handles all mechanics (rolls, sheets, HP, attacks,
spells, initiative). This module owns:
  - ChromaDB session memory + knowledge base retrieval
  - DM prompt construction with Avrae roll awareness
  - Campaign/character DB helpers (narrative-only)
  - Scene state management

NOT a bot. Imported by discord_dnd_bot.py.
"""

import os
import sys
import sqlite3
import json

def _now():
    import datetime
    return datetime.datetime.utcnow().isoformat()
import datetime
import threading
import requests
import re
from pathlib import Path
from dotenv import load_dotenv

load_dotenv('/home/jordaneal/scripts/.env')

sys.path.insert(0, '/home/jordaneal/scripts')
from cloud_router import route
import dnd_orchestration as orch
import npc_hydrator

DB_PATH = Path('/mnt/virgil_storage/virgil.db')
CHROMA_PATH = Path('/mnt/virgil_storage/chroma_dnd')
LOG_PATH = Path('/mnt/virgil_storage/digest/dnd_engine.log')

# ─────────────────────────────────────────────────────────
# Feature flags
# ─────────────────────────────────────────────────────────

# When True, retrieves narrative exemplars from the 740k FIREBALL+CRD3
# corpus and injects them into the DM prompt. Set to False if tone bleed
# returns — the flag is your kill switch. Currently enabled.
USE_KNOWLEDGE_GUIDANCE = True  # Corpus integration is a load-bearing design
                                # choice — we want the DM to draw on the 740k
                                # CRD3+FIREBALL exemplars even when semantic
                                # match is loose. Tonal bleed managed via prompt.


# ─────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────

def log(msg):
    timestamp = datetime.datetime.now().isoformat(timespec='seconds')
    line = f"[{timestamp}] {msg}"
    print(line, flush=True)
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_PATH, 'a') as f:
            f.write(line + '\n')
    except Exception:
        pass


# ─────────────────────────────────────────────────────────
# ChromaDB — sessions + knowledge base
# ─────────────────────────────────────────────────────────

_chroma_client = None
_chroma_collection = None
_knowledge_collection = None

# Track 6 #4: cross-call flag — set True by npc_hydrate_stats() when any
# stat write occurs; read+reset by dm_respond() for directive_emit telemetry.
_hydration_wrote_this_turn = False


def chroma_init():
    """Initialise both the session collection (writable) and the knowledge
    collection (read-only, 740k FIREBALL+CRD3 docs).

    BUGFIX: previous version forgot `global _knowledge_collection`, so the
    knowledge base was never actually wired up. knowledge_search() was
    returning empty for the entire history of the bot.
    """
    global _chroma_client, _chroma_collection, _knowledge_collection
    try:
        import chromadb
        CHROMA_PATH.mkdir(parents=True, exist_ok=True)
        _chroma_client = chromadb.PersistentClient(path=str(CHROMA_PATH))
        _chroma_collection = _chroma_client.get_or_create_collection(
            name="dnd_sessions",
            metadata={"hnsw:space": "cosine"}
        )
        try:
            _knowledge_collection = _chroma_client.get_collection('dnd_knowledge')
            log(f"chroma_init: sessions={_chroma_collection.count()} knowledge={_knowledge_collection.count()}")
        except Exception as e:
            _knowledge_collection = None
            log(f"chroma_init: sessions={_chroma_collection.count()} knowledge=NOT FOUND ({e})")
    except Exception as e:
        log(f"chroma_init error: {e}")


def chroma_embed(text):
    try:
        resp = requests.post(
            "http://localhost:11434/api/embed",
            json={"model": "nomic-embed-text", "input": text},
            timeout=15
        )
        if resp.status_code == 200:
            return resp.json().get("embeddings", [None])[0]
    except Exception as e:
        log(f"chroma_embed error: {e}")
    return None


def _chroma_store_async(campaign_id, role, text, ts):
    if _chroma_collection is None or len(text.strip()) < 10:
        return
    try:
        embedding = chroma_embed(text)
        if embedding is None:
            return
        doc_id = f"dnd_{campaign_id}_{ts}_{role}"
        _chroma_collection.upsert(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[text],
            metadatas=[{"campaign_id": str(campaign_id), "role": role, "ts": ts}]
        )
    except Exception as e:
        log(f"_chroma_store_async error: {e}")


def chroma_store(campaign_id, role, text):
    """Fire-and-forget store. role is 'user' or 'dm'."""
    if _chroma_collection is None:
        return
    ts = datetime.datetime.now().isoformat(timespec='seconds')
    threading.Thread(
        target=_chroma_store_async,
        args=(campaign_id, role, text, ts),
        daemon=True
    ).start()


def chroma_search(campaign_id, query, n=4):
    """Pull recent relevant campaign turns. Empty string if no hits or no DB."""
    if _chroma_collection is None or _chroma_collection.count() < 3:
        return ""
    try:
        embedding = chroma_embed(query)
        if embedding is None:
            return ""
        results = _chroma_collection.query(
            query_embeddings=[embedding],
            n_results=min(n, _chroma_collection.count()),
            where={"campaign_id": str(campaign_id)},
            include=["documents", "metadatas", "distances"]
        )
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]
        lines = []
        for doc, meta, dist in zip(docs, metas, distances):
            if dist > 0.5:
                continue
            role = meta.get("role", "")
            ts = meta.get("ts", "")[:10]
            prefix = "Player" if role == "user" else "DM"
            lines.append(f"[{ts}] {prefix}: {doc[:200]}")
        return "Relevant past events:\n" + "\n".join(lines) if lines else ""
    except Exception as e:
        log(f"chroma_search error: {e}")
        return ""


def knowledge_search(query, n=5, distance_cutoff=0.55):
    """Pull narrative exemplars from CRD3 (Matt Mercer DM turns) and FIREBALL.

    Returns up to n labeled exemplars, formatted for prompt injection.
    """
    if _knowledge_collection is None:
        return ""
    try:
        kc = _knowledge_collection
        if kc.count() < 10:
            return ""
        embedding = chroma_embed(query)
        if embedding is None:
            return ""
        results = kc.query(
            query_embeddings=[embedding],
            n_results=min(n * 3, kc.count()),
            include=["documents", "metadatas", "distances"]
        )
        docs = results.get("documents", [[]])[0]
        distances = results.get("distances", [[]])[0]
        metas = results.get("metadatas", [[]])[0]

        examples = []
        seen_prefixes = set()  # crude dedupe
        for doc, dist, meta in zip(docs, distances, metas):
            if dist > distance_cutoff:
                continue
            source = meta.get("source", "unknown")
            speaker = meta.get("speaker", "")
            text = doc
            if speaker and text.upper().startswith(speaker.upper() + ":"):
                text = text[len(speaker) + 1:].strip()
            # Dedupe by first 60 chars to avoid near-duplicates
            prefix = text[:60].lower()
            if prefix in seen_prefixes:
                continue
            seen_prefixes.add(prefix)
            label = "Matt Mercer (CR)" if source == "crd3" and speaker.upper() == "MATT" else source.upper()
            examples.append(f"— {label}: {text[:400]}")
            if len(examples) >= n:
                break
        return "\n\n".join(examples) if examples else ""
    except Exception as e:
        log(f"knowledge_search error: {e}")
        return ""


def multi_query_knowledge_search(action, action_type, scene_blurb, avrae_summary=""):
    """Run two complementary searches and merge — pulls more diverse exemplars
    than a single query. Bounded to ~6 total."""
    primary = f"{action_type}: {action}. Scene: {scene_blurb}".strip()
    secondary_bits = []
    if avrae_summary:
        secondary_bits.append(avrae_summary)
    if action_type and action_type != "general roleplay":
        secondary_bits.append(f"DM narrating {action_type}")
    secondary = " ".join(secondary_bits).strip()

    out = knowledge_search(primary, n=4)
    if secondary:
        extra = knowledge_search(secondary, n=3)
        if extra:
            out = (out + "\n\n" + extra) if out else extra
    return out


# ─────────────────────────────────────────────────────────
# Database — narrative-only schema
# ─────────────────────────────────────────────────────────

def db_init():
    """Ensures the DnD tables exist. Mechanical columns on dnd_characters
    are kept for back-compat but no longer populated by us — Avrae owns those."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS dnd_campaigns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        created_at TEXT,
        status TEXT DEFAULT 'active',
        world_notes TEXT DEFAULT '',
        current_scene TEXT DEFAULT '',
        guild_id TEXT DEFAULT '',
        tone TEXT DEFAULT ''
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS dnd_characters (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        campaign_id INTEGER,
        name TEXT NOT NULL,
        race TEXT DEFAULT '',
        class TEXT DEFAULT '',
        level INTEGER DEFAULT 1,
        background TEXT DEFAULT '',
        controller TEXT DEFAULT '',
        alive INTEGER DEFAULT 1,
        hp_current INTEGER DEFAULT 0,
        hp_max INTEGER DEFAULT 0,
        ac INTEGER DEFAULT 0,
        speed INTEGER DEFAULT 30,
        str_score INTEGER DEFAULT 10,
        dex_score INTEGER DEFAULT 10,
        con_score INTEGER DEFAULT 10,
        int_score INTEGER DEFAULT 10,
        wis_score INTEGER DEFAULT 10,
        cha_score INTEGER DEFAULT 10,
        proficiency_bonus INTEGER DEFAULT 2,
        hit_dice TEXT DEFAULT 'd8',
        inspiration INTEGER DEFAULT 0,
        xp INTEGER DEFAULT 0
    )''')
    # Migration: add columns if pre-existing schema
    cols = [row[1] for row in conn.execute("PRAGMA table_info(dnd_campaigns)").fetchall()]
    if 'guild_id' not in cols:
        conn.execute("ALTER TABLE dnd_campaigns ADD COLUMN guild_id TEXT DEFAULT ''")
    if 'tone' not in cols:
        conn.execute("ALTER TABLE dnd_campaigns ADD COLUMN tone TEXT DEFAULT ''")
    if 'created_by_user_id' not in cols:
        # Session 10: campaign creator stamp. Lets the campaign owner run
        # structural commands (/quest, /clock, /encounter, /companion, /mode)
        # without needing manage_guild — solves the solo-as-DM friction.
        conn.execute("ALTER TABLE dnd_campaigns ADD COLUMN created_by_user_id TEXT DEFAULT ''")

    # Phase 6 (Session 15): identity reconciliation columns on dnd_characters.
    # canonical_name = canonicalize_actor_name(name) for cross-system matching.
    # aliases = JSON list of additional canonical-form strings observed for this
    # character (Avrae nicknames, init labels, etc.) — durably stored equivalences.
    char_cols = [row[1] for row in conn.execute("PRAGMA table_info(dnd_characters)").fetchall()]
    if 'canonical_name' not in char_cols:
        conn.execute("ALTER TABLE dnd_characters ADD COLUMN canonical_name TEXT DEFAULT ''")
    if 'aliases' not in char_cols:
        conn.execute("ALTER TABLE dnd_characters ADD COLUMN aliases TEXT DEFAULT '[]'")
    # Backfill canonical_name from existing name. Idempotent — only fills
    # rows that don't already have a value.
    conn.execute(
        "UPDATE dnd_characters SET canonical_name=lower(trim(name)) "
        "WHERE canonical_name IS NULL OR canonical_name=''"
    )

    conn.execute('''CREATE TABLE IF NOT EXISTS dnd_scene_state (
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
    )''')
    # Combat coordination state — who holds the active turn per campaign.
    # Intentionally separate from dnd_scene_state (narrative scope).
    # Only deterministic systems write here. LLM extraction never touches this table.
    conn.execute('''CREATE TABLE IF NOT EXISTS dnd_combat_state (
        campaign_id     INTEGER PRIMARY KEY,
        controller_id   TEXT    NOT NULL,
        character_name  TEXT    NOT NULL,
        round           INTEGER NOT NULL,
        updated_at      TEXT    NOT NULL
    )''')
    # Per-combatant snapshot — populated from `!init list` Avrae plaintext via
    # the avrae_listener parser branch. Replace-in-place per snapshot. Read by
    # compute_persistence_directive, written only by update_combatants_from_init_list
    # / clear_combatants. LLM extraction never touches this table.
    # See COMBAT_PERSISTENCE_DIRECTIVE_SPEC.md §4.2 / §11.A.
    conn.execute('''CREATE TABLE IF NOT EXISTS dnd_combatant_state (
        campaign_id   INTEGER NOT NULL,
        name          TEXT    NOT NULL,
        init          INTEGER NOT NULL,
        hp_current    INTEGER,
        hp_max        INTEGER,
        conditions    TEXT    DEFAULT '',
        alive         INTEGER NOT NULL DEFAULT 1,
        side          TEXT    NOT NULL DEFAULT 'unknown',
        updated_at    TEXT    NOT NULL,
        PRIMARY KEY (campaign_id, name)
    )''')
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_combatant_campaign "
        "ON dnd_combatant_state(campaign_id)"
    )
    # Narrative inventory (Track 4 ship #1, Session 21) — per-character
    # narrative items: loot, quest objects, story items, found gear.
    # Distinct from Avrae sheet-bound combat gear (weapons / armor / equipment
    # that affects rolls); Avrae owns those. Single write path: add_item /
    # remove_item / clear_inventory. Read by get_inventory / has_item plus
    # build_dm_context's per-turn render. LLM extraction never touches this
    # table — DM hands items out via /giveitem; players claim through
    # narration. Item names stored lowercase; lookup case-insensitive.
    # Composite uniqueness via (campaign_id, character_name, item_name)
    # logical key — enforced by add_item (increments existing row rather
    # than inserting duplicate).
    conn.execute('''CREATE TABLE IF NOT EXISTS dnd_inventory (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        campaign_id     INTEGER NOT NULL,
        character_name  TEXT    NOT NULL,
        item_name       TEXT    NOT NULL,
        quantity        INTEGER NOT NULL DEFAULT 1,
        metadata        TEXT,
        created_at      TEXT    NOT NULL
    )''')
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_inventory_lookup "
        "ON dnd_inventory(campaign_id, character_name, item_name)"
    )
    # Pending loot queue (Track 4 #2, Session 22) — generated when a
    # combatant transitions alive=1 -> alive=0 in update_combatants_from_init_list.
    # Each row is one creature's drop, awaiting surface in the next narration
    # turn. Single writers: enqueue_loot (insert) / mark_loot_surfaced (flag).
    # Read by compute_loot_directive via get_pending_loot. Surface-and-clear
    # cycle: directive renders pending rows, then dm_respond marks them
    # surfaced AFTER the LLM call succeeds (so a failed LLM call leaves loot
    # pending for next turn).
    conn.execute('''CREATE TABLE IF NOT EXISTS dnd_loot_pending (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        campaign_id   INTEGER NOT NULL,
        creature      TEXT    NOT NULL,
        table_key     TEXT    NOT NULL,
        coin_amount   INTEGER,
        coin_denom    TEXT,
        items         TEXT    NOT NULL,
        surfaced      INTEGER NOT NULL DEFAULT 0,
        surfaced_at   TEXT,
        created_at    TEXT    NOT NULL
    )''')
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_loot_pending_lookup "
        "ON dnd_loot_pending(campaign_id, surfaced)"
    )
    # Quest log — DM-managed, slash-command driven. Status lifecycle:
    # active → completed | failed. Active quests inject into the DM prompt;
    # completed/failed remain queryable via /quest list but stay out of the
    # system prompt to keep focus tight (2C.2).
    conn.execute('''CREATE TABLE IF NOT EXISTS dnd_quests (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        campaign_id  INTEGER NOT NULL,
        title        TEXT    NOT NULL,
        summary      TEXT    DEFAULT '',
        status       TEXT    DEFAULT 'active',
        priority     TEXT    DEFAULT 'normal',
        given_by     TEXT    DEFAULT '',
        created_at   TEXT    NOT NULL,
        updated_at   TEXT    NOT NULL
    )''')
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_quests_campaign_status "
        "ON dnd_quests(campaign_id, status)"
    )
    # Companions — DM-managed NPCs that travel with the party (2C.3).
    # Pure prompt content. No mechanical state. No autonomous logic.
    # Hard cap of 3 per campaign enforced at the engine layer.
    conn.execute('''CREATE TABLE IF NOT EXISTS dnd_companions (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        campaign_id  INTEGER NOT NULL,
        name         TEXT    NOT NULL,
        persona      TEXT    DEFAULT '',
        created_at   TEXT    NOT NULL,
        updated_at   TEXT    NOT NULL
    )''')
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_companions_campaign "
        "ON dnd_companions(campaign_id)"
    )
    # Persistent NPCs (Phase 12A) — canonical narrative entities.
    # Authoritative storage for "who exists in this world." Distinct from
    # dnd_companions (party-bound NPCs). Single write path: npc_upsert().
    # skeleton_origin=1 rows are authored canon (skeleton.md) and are NEVER
    # overwritten by parser-detected hits — see npc_upsert() for the rule.
    conn.execute('''CREATE TABLE IF NOT EXISTS dnd_npcs (
        id                INTEGER PRIMARY KEY AUTOINCREMENT,
        campaign_id       INTEGER NOT NULL,
        canonical_name    TEXT    NOT NULL,
        aliases           TEXT    DEFAULT '[]',
        role              TEXT    DEFAULT '',
        location_id       INTEGER,
        description       TEXT    DEFAULT '',
        skeleton_origin   INTEGER DEFAULT 0,
        mention_count     INTEGER DEFAULT 1,
        origin_excerpt    TEXT    DEFAULT '',
        first_mentioned   TEXT    NOT NULL,
        last_mentioned    TEXT    NOT NULL,
        UNIQUE (campaign_id, canonical_name)
    )''')
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_npcs_campaign ON dnd_npcs(campaign_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_npcs_location ON dnd_npcs(location_id)"
    )
    # Persistent locations (Phase 12B) — canonical world geography.
    # Authoritative storage for "what places exist in this world."
    # Hierarchical: parent_location_id is a self-FK (e.g. "The Rusty Anchor"
    # parent → "Redhaven"). Single write path: location_upsert().
    # Identity is canonicalize_location_name(): strict literal AFTER leading
    # article strip. "The Rusty Anchor" and "Rusty Anchor" collapse to one
    # canonical "Rusty Anchor". See canonicalize_location_name().
    conn.execute('''CREATE TABLE IF NOT EXISTS dnd_locations (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        campaign_id         INTEGER NOT NULL,
        canonical_name      TEXT    NOT NULL,
        aliases             TEXT    DEFAULT '[]',
        type                TEXT    DEFAULT '',
        parent_location_id  INTEGER,
        description         TEXT    DEFAULT '',
        skeleton_origin     INTEGER DEFAULT 0,
        mention_count       INTEGER DEFAULT 1,
        origin_excerpt      TEXT    DEFAULT '',
        first_mentioned     TEXT    NOT NULL,
        last_mentioned      TEXT    NOT NULL,
        UNIQUE (campaign_id, canonical_name)
    )''')
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_locations_campaign ON dnd_locations(campaign_id)"
    )
    # Consequence ledger (Session 16) — captures and surfaces deferred
    # consequences against canonical NPCs. Single write path:
    # consequence_upsert() / consequence_emit_surface() / consequence_promote().
    # See CONSEQUENCE_SURFACING_SPEC.md §4 for field rationale.
    conn.execute('''CREATE TABLE IF NOT EXISTS dnd_consequences (
        id                       INTEGER PRIMARY KEY AUTOINCREMENT,
        campaign_id              INTEGER NOT NULL,
        npc_id                   INTEGER NOT NULL,
        kind                     TEXT    NOT NULL,
        summary                  TEXT    NOT NULL,
        severity                 INTEGER NOT NULL,
        sources                  TEXT    NOT NULL,
        captured_at              TEXT    NOT NULL,
        captured_turn            INTEGER NOT NULL,
        first_seen_turn          INTEGER NOT NULL,
        last_seen_turn           INTEGER NOT NULL,
        last_surfaced_at         TEXT,
        last_surfaced_turn       INTEGER,
        surface_count            INTEGER NOT NULL DEFAULT 0,
        distinct_surface_turns   INTEGER NOT NULL DEFAULT 0,
        status                   TEXT    NOT NULL DEFAULT 'active',
        promoted_at              TEXT,
        UNIQUE(campaign_id, npc_id, kind)
    )''')
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_consequences_campaign "
        "ON dnd_consequences(campaign_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_consequences_active "
        "ON dnd_consequences(campaign_id, status)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_consequences_npc "
        "ON dnd_consequences(campaign_id, npc_id)"
    )
    conn.commit()
    # Track 6 #4: add nullable stat columns to dnd_npcs for hydration.
    npc_cols = {row[1] for row in conn.execute("PRAGMA table_info(dnd_npcs)").fetchall()}
    for col, ctype in [
        ('hp_max',       'INTEGER'),
        ('ac',           'INTEGER'),
        ('attack_bonus', 'INTEGER'),
        ('damage_dice',  'TEXT'),
        ('save_bonus',   'INTEGER'),
        ('init_mod',     'INTEGER'),
        ('cr_str',       'TEXT'),
        ('avrae_source', 'TEXT'),
    ]:
        if col not in npc_cols:
            conn.execute(f"ALTER TABLE dnd_npcs ADD COLUMN {col} {ctype}")
    conn.commit()
    conn2 = sqlite3.connect(DB_PATH)
    existing = {row[1] for row in conn2.execute("PRAGMA table_info(dnd_scene_state)")}
    if 'tension_int' not in existing:
        conn2.execute("ALTER TABLE dnd_scene_state ADD COLUMN tension_int INTEGER DEFAULT 0")
        conn2.commit()
    if 'progress_clocks' not in existing:
        conn2.execute("ALTER TABLE dnd_scene_state ADD COLUMN progress_clocks TEXT DEFAULT '[]'")
        conn2.commit()
    if 'current_location_id' not in existing:
        # Phase 12B §9.9: semi-authoritative pointer. Single writer is
        # set_current_location(). Default NULL = "between locations" /
        # wilderness / not yet placed.
        conn2.execute("ALTER TABLE dnd_scene_state ADD COLUMN current_location_id INTEGER DEFAULT NULL")
        conn2.commit()
    if 'turn_counter' not in existing:
        # Session 16 (consequence surfacing): per-campaign monotonic turn
        # axis. Single writer is increment_turn_counter(). Used by the
        # consequence layer for promotion thresholds and for capture/surface
        # turn tagging. Default 0 = "no turns played yet".
        conn2.execute("ALTER TABLE dnd_scene_state ADD COLUMN turn_counter INTEGER DEFAULT 0")
        conn2.commit()
    if 'last_dm_response' not in existing:
        # Session 19 (committed-action resolution): the prior turn's DM
        # narration. Read by compute_commitment_directive's reaction-verb
        # heuristic to decide whether the prior commitment was narratively
        # resolved. Single writer is update_last_dm_response(). Default ''
        # = "no prior turn".
        conn2.execute("ALTER TABLE dnd_scene_state ADD COLUMN last_dm_response TEXT DEFAULT ''")
        conn2.commit()
    if 'last_active_actor' not in existing:
        # Session 32 (Bug 1 Phase 1) — footer-actor source of truth. The
        # name of the PC the DM most recently addressed (exploration mode)
        # or whose turn is active (combat mode). Read by the roll-directive
        # matcher to snapshot the active actor at directive-emit time.
        # Mode-disjoint single-writer discipline: update_last_active_actor()
        # is the sole writer; called from _dm_respond_and_post (exploration),
        # set_active_turn / clear_active_turn (combat), and /play (clear).
        # Default '' = no active actor in footer yet.
        conn2.execute("ALTER TABLE dnd_scene_state ADD COLUMN last_active_actor TEXT DEFAULT ''")
        conn2.commit()
    # Track 4 #3 (Session 27) — Time Progression v1. Two new scene_state
    # columns and one new audit-log table. Single write path is
    # advance_time(); skeleton loader seed-write is the narrow §17
    # exception (initialization only, fresh-row gated).
    if 'campaign_day' not in existing:
        conn2.execute("ALTER TABLE dnd_scene_state ADD COLUMN campaign_day INTEGER DEFAULT 1")
        conn2.commit()
    if 'day_phase' not in existing:
        conn2.execute("ALTER TABLE dnd_scene_state ADD COLUMN day_phase TEXT DEFAULT 'Morning'")
        conn2.commit()
    conn2.execute('''CREATE TABLE IF NOT EXISTS dnd_time_advancements (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        campaign_id     INTEGER NOT NULL,
        before_day      INTEGER NOT NULL,
        before_phase    TEXT    NOT NULL,
        after_day       INTEGER NOT NULL,
        after_phase     TEXT    NOT NULL,
        days_delta      INTEGER NOT NULL,
        phase_delta     INTEGER NOT NULL,
        resolved_phase_delta INTEGER NOT NULL,
        set_phase       TEXT    DEFAULT NULL,
        source          TEXT    NOT NULL,
        source_detail   TEXT    DEFAULT '',
        created_at      TEXT    NOT NULL
    )''')
    conn2.execute(
        "CREATE INDEX IF NOT EXISTS idx_time_adv_campaign "
        "ON dnd_time_advancements(campaign_id)"
    )
    conn2.execute(
        "CREATE INDEX IF NOT EXISTS idx_time_adv_created "
        "ON dnd_time_advancements(campaign_id, created_at)"
    )
    conn2.commit()
    # Bug 1 Phase 1 (Session 32) — pending DM roll directives.
    # When the DM emits `!check stealth` / `!save dex` / `!cast guidance`
    # in #dm-narration, a row is created snapshotting the current
    # last_active_actor + skill at directive-emit time. The Avrae roll
    # arrival path consumes the row when actor + skill match. TTL-expired
    # rows are swept on access. Single writer is the matcher logic in
    # discord_dnd_bot.py via the engine helpers below.
    # One pending row per campaign max (UNIQUE constraint on campaign_id);
    # later directives REPLACE prior unresolved ones (telemetry logs the
    # replacement before the swap).
    conn2.execute('''CREATE TABLE IF NOT EXISTS dnd_pending_roll_directives (
        campaign_id        INTEGER PRIMARY KEY,
        actor_name         TEXT    NOT NULL,
        check_type         TEXT    NOT NULL,
        source_message_id  TEXT    NOT NULL,
        created_at         TEXT    NOT NULL,
        expires_at         TEXT    NOT NULL,
        dc                 INTEGER
    )''')
    # Ship 1 (S34) idempotent migration — add dc column when older schema lacks it.
    pdr_cols = {
        row[1] for row in
        conn2.execute("PRAGMA table_info(dnd_pending_roll_directives)").fetchall()
    }
    if 'dc' not in pdr_cols:
        conn2.execute("ALTER TABLE dnd_pending_roll_directives ADD COLUMN dc INTEGER")
        conn2.commit()
    conn2.execute(
        "CREATE INDEX IF NOT EXISTS idx_pending_directive_msg "
        "ON dnd_pending_roll_directives(source_message_id)"
    )
    conn2.commit()
    conn2.close()
    conn.close()


def get_active_campaign(guild_id: str):
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT id, name, current_scene, world_notes, tone FROM dnd_campaigns "
        "WHERE status='active' AND guild_id=? ORDER BY id DESC LIMIT 1",
        (guild_id,)
    ).fetchone()
    conn.close()
    if row:
        return {
            'id': row[0], 'name': row[1],
            'current_scene': row[2], 'world_notes': row[3],
            'tone': row[4] or '',
            'guild_id': guild_id
        }
    return None


def get_characters(campaign_id: int):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT id, name, race, class, level, controller "
        "FROM dnd_characters WHERE campaign_id=? AND alive=1",
        (campaign_id,)
    ).fetchall()
    conn.close()
    return [
        {'id': r[0], 'name': r[1], 'race': r[2], 'class': r[3],
         'level': r[4], 'controller': r[5]}
        for r in rows
    ]


def get_bound_character_names(campaign_id: int) -> list:
    # Names of alive bound PCs in this campaign. Used by parsers and
    # npc_upsert to filter out the player character — PCs are not NPCs.
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT name FROM dnd_characters WHERE campaign_id=? AND alive=1",
        (campaign_id,)
    ).fetchall()
    conn.close()
    return [r[0] for r in rows if r[0]]


def get_character_by_canonical(campaign_id: int, canonical: str) -> dict | None:
    # Phase 6 identity resolution. Returns the alive bound character row whose
    # canonical_name matches `canonical` exactly (lowercased on both sides).
    # If multiple rows match, returns None (ambiguous — caller should log).
    # Empty/None canonical returns None.
    if not canonical:
        return None
    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute(
            "SELECT id, campaign_id, name, race, class, level, controller, alive, "
            "canonical_name, aliases "
            "FROM dnd_characters WHERE campaign_id=? AND alive=1 "
            "AND canonical_name=?",
            (campaign_id, canonical)
        ).fetchall()
    finally:
        conn.close()
    if not rows or len(rows) > 1:
        return None
    r = rows[0]
    try:
        aliases = json.loads(r[9]) if r[9] else []
        if not isinstance(aliases, list):
            aliases = []
    except (json.JSONDecodeError, TypeError):
        aliases = []
    return {
        'id': r[0], 'campaign_id': r[1], 'name': r[2], 'race': r[3],
        'class': r[4], 'level': r[5], 'controller': r[6], 'alive': r[7],
        'canonical_name': r[8], 'aliases': aliases,
    }


def get_character_by_alias(campaign_id: int, alias_canonical: str) -> dict | None:
    # Phase 6 identity resolution. Returns the alive bound character row whose
    # `aliases` JSON list contains an exact-equality match for `alias_canonical`.
    # If multiple rows match, returns None (ambiguous). Empty/None returns None.
    if not alias_canonical:
        return None
    conn = sqlite3.connect(DB_PATH)
    try:
        # JSON1 extension is available in modern SQLite. Use json_each to expand.
        rows = conn.execute(
            "SELECT c.id, c.campaign_id, c.name, c.race, c.class, c.level, "
            "c.controller, c.alive, c.canonical_name, c.aliases "
            "FROM dnd_characters c, json_each(c.aliases) j "
            "WHERE c.campaign_id=? AND c.alive=1 AND j.value=?",
            (campaign_id, alias_canonical)
        ).fetchall()
    finally:
        conn.close()
    if not rows or len(rows) > 1:
        return None
    r = rows[0]
    try:
        aliases = json.loads(r[9]) if r[9] else []
        if not isinstance(aliases, list):
            aliases = []
    except (json.JSONDecodeError, TypeError):
        aliases = []
    return {
        'id': r[0], 'campaign_id': r[1], 'name': r[2], 'race': r[3],
        'class': r[4], 'level': r[5], 'controller': r[6], 'alive': r[7],
        'canonical_name': r[8], 'aliases': aliases,
    }


def set_character_canonical_name(character_id: int, canonical: str) -> bool:
    # Phase 6: single-write-path for canonical_name updates. Returns True if a
    # row was updated. Used by refresh_canonical_name (orchestration) when a
    # sheet embed is parsed for a known controller.
    if not canonical:
        return False
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.execute(
            "UPDATE dnd_characters SET canonical_name=? WHERE id=?",
            (canonical, character_id)
        )
        updated = cur.rowcount > 0
        conn.commit()
        return updated
    finally:
        conn.close()


def append_character_alias(character_id: int, alias_canonical: str) -> bool:
    # Phase 6: single-write-path for aliases. Idempotent — no-op if alias is
    # already in the list. Returns True if the alias was appended (new entry).
    # Stored as JSON list of canonicalized strings.
    if not alias_canonical:
        return False
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute(
            "SELECT aliases FROM dnd_characters WHERE id=?",
            (character_id,)
        ).fetchone()
        if not row:
            return False
        try:
            current = json.loads(row[0]) if row[0] else []
            if not isinstance(current, list):
                current = []
        except (json.JSONDecodeError, TypeError):
            current = []
        if alias_canonical in current:
            return False  # already there
        current.append(alias_canonical)
        conn.execute(
            "UPDATE dnd_characters SET aliases=? WHERE id=?",
            (json.dumps(current), character_id)
        )
        conn.commit()
        return True
    finally:
        conn.close()


def get_character_by_controller(campaign_id: int, controller_id: str):
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT id, name, race, class, level, controller, "
        "canonical_name, aliases "
        "FROM dnd_characters WHERE campaign_id=? AND controller=? AND alive=1",
        (campaign_id, controller_id)
    ).fetchone()
    conn.close()
    if not row:
        return None
    try:
        aliases = json.loads(row[7]) if row[7] else []
        if not isinstance(aliases, list):
            aliases = []
    except (json.JSONDecodeError, TypeError):
        aliases = []
    return {'id': row[0], 'name': row[1], 'race': row[2], 'class': row[3],
            'level': row[4], 'controller': row[5],
            'canonical_name': row[6] or '', 'aliases': aliases}


def create_campaign(guild_id: str, name: str, tone: str = '', creator_user_id: str = '') -> int:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE dnd_campaigns SET status='inactive' WHERE status='active' AND guild_id=?",
        (guild_id,)
    )
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO dnd_campaigns (name, created_at, status, guild_id, tone, created_by_user_id) "
        "VALUES (?,?,?,?,?,?)",
        (name, datetime.datetime.now().isoformat(), 'active', guild_id, tone, creator_user_id)
    )
    campaign_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return campaign_id


def bind_character(campaign_id: int, controller_id: str, name: str,
                   race: str = '', char_class: str = '', level: int = 1) -> int:
    """Narrative-only binding. Avrae owns the actual sheet — we just need
    to know who's at the table for prompt context."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Soft-retire any prior character for this controller in this campaign
    cursor.execute(
        "UPDATE dnd_characters SET alive=0 WHERE campaign_id=? AND controller=?",
        (campaign_id, controller_id)
    )
    cursor.execute(
        "INSERT INTO dnd_characters (campaign_id, name, race, class, level, controller, alive) "
        "VALUES (?, ?, ?, ?, ?, ?, 1)",
        (campaign_id, name, race, char_class, level, controller_id)
    )
    char_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return char_id


def update_scene(campaign_id: int, scene_text: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE dnd_campaigns SET current_scene=? WHERE id=?",
        (scene_text[:2000], campaign_id)
    )
    conn.commit()
    conn.close()


def list_campaigns(guild_id: str):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT id, name, status, created_at FROM dnd_campaigns "
        "WHERE guild_id=? ORDER BY id DESC",
        (guild_id,)
    ).fetchall()
    conn.close()
    return [{'id': r[0], 'name': r[1], 'status': r[2], 'created_at': r[3]} for r in rows]


# Tables that hold per-campaign data via campaign_id. Order chosen for
# clarity (children before parent), though SQLite does not enforce FK
# constraints without PRAGMA foreign_keys=ON, and even with it on, deleting
# all rows for a campaign in one transaction is safe regardless of order.
# When new per-campaign tables are added, append them here.
_CAMPAIGN_SCOPED_TABLES = (
    'dnd_consequences',  # Session 16 — child of dnd_npcs.npc_id; delete first
    'dnd_npcs',
    'dnd_locations',
    'dnd_quests',
    'dnd_companions',
    'dnd_combat_state',
    'dnd_combatant_state',  # Session 21 — combat persistence directive snapshot
    'dnd_inventory',        # Track 4 #1 — narrative inventory per character
    'dnd_loot_pending',     # Track 4 #2 — pending loot queue (Session 22)
    'dnd_time_advancements', # Track 4 #3 — time progression audit log (Session 27)
    'dnd_pending_roll_directives',  # Bug 1 Phase 1 — pending DM roll directives (Session 32)
    'dnd_scene_state',
    'dnd_characters',
)


def campaign_delete_cascade(campaign_id: int) -> dict:
    """Hard-delete a campaign and all its dependent rows.

    Removes rows from every per-campaign table (see _CAMPAIGN_SCOPED_TABLES)
    plus the dnd_campaigns row itself. Single transaction — either everything
    deletes or nothing does.

    REFUSES to delete an active campaign. Caller (slash command layer) must
    archive or switch first. Engine defends this invariant rather than
    trusting the caller, mirroring the set_current_location FK-validation
    pattern from §9.9.

    Returns:
      {
        'campaign_id':  int,
        'deleted':      bool,                 # False if refused/missing
        'reason':       str | None,           # populated when deleted=False
        'rows_deleted': {table_name: int},    # per-table counts; campaign row
                                              # appears as 'dnd_campaigns'
      }
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute(
            "SELECT id, status, name FROM dnd_campaigns WHERE id=?",
            (campaign_id,)
        ).fetchone()
        if row is None:
            log(f"campaign_delete_cascade: refused — campaign={campaign_id} "
                f"not found")
            return {
                'campaign_id': campaign_id,
                'deleted':     False,
                'reason':      'not_found',
                'rows_deleted': {},
            }
        if row[1] == 'active':
            log(f"campaign_delete_cascade: refused — campaign={campaign_id} "
                f"is active (must archive or switch away first)")
            return {
                'campaign_id': campaign_id,
                'deleted':     False,
                'reason':      'campaign_is_active',
                'rows_deleted': {},
            }
        rows_deleted = {}
        try:
            conn.execute("BEGIN")
            for tbl in _CAMPAIGN_SCOPED_TABLES:
                cur = conn.execute(
                    f"DELETE FROM {tbl} WHERE campaign_id=?",
                    (campaign_id,)
                )
                rows_deleted[tbl] = cur.rowcount
            cur = conn.execute(
                "DELETE FROM dnd_campaigns WHERE id=?",
                (campaign_id,)
            )
            rows_deleted['dnd_campaigns'] = cur.rowcount
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        log(f"campaign_delete_cascade: campaign={campaign_id} name={row[2]!r} "
            f"deleted; rows_deleted={rows_deleted}")
        return {
            'campaign_id':  campaign_id,
            'deleted':      True,
            'reason':       None,
            'rows_deleted': rows_deleted,
        }
    finally:
        conn.close()


# Allowed campaign statuses. The active-flip rule lives in code, not in
# a CHECK constraint, because the existing dnd_campaigns table predates
# this enumeration and there are pre-existing rows with status='active'
# / 'inactive'. Adding 'archived' as a legal value is purely additive.
_VALID_CAMPAIGN_STATUSES = ('active', 'inactive', 'archived')


def campaign_set_status(campaign_id: int, status: str) -> dict:
    """Change a campaign's status. Single write path for the dnd_campaigns
    status column outside of create_campaign.

    Status semantics:
      - 'active'   — the campaign currently in play. Exactly ONE per
                     guild at a time. Setting a campaign active flips
                     any other active campaign in the same guild to
                     inactive in the same transaction.
      - 'inactive' — created or formerly active. Visible in /campaigns
                     by default. Eligible for delete.
      - 'archived' — soft-deleted. Hidden from /campaigns by default.
                     Eligible for delete (including bulk purge).

    Switching to 'active' un-archives if the row was archived. This is
    intentional — switching IS the act of un-archiving (per design
    review). Caller does not need to two-step it.

    Refuses on:
      - unknown campaign_id          (reason='not_found')
      - status not in _VALID_CAMPAIGN_STATUSES  (reason='invalid_status')

    Returns:
      {
        'campaign_id':       int,
        'updated':           bool,
        'reason':            str | None,
        'previous_status':   str | None,
        'new_status':        str | None,
        'previous_active_id': int | None,  # set if a sibling was demoted
      }
    """
    if status not in _VALID_CAMPAIGN_STATUSES:
        log(f"campaign_set_status: refused — invalid status={status!r} "
            f"for campaign={campaign_id}")
        return {
            'campaign_id':        campaign_id,
            'updated':            False,
            'reason':             'invalid_status',
            'previous_status':    None,
            'new_status':         None,
            'previous_active_id': None,
        }
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute(
            "SELECT id, name, status, guild_id FROM dnd_campaigns WHERE id=?",
            (campaign_id,)
        ).fetchone()
        if row is None:
            log(f"campaign_set_status: refused — campaign={campaign_id} "
                f"not found")
            return {
                'campaign_id':        campaign_id,
                'updated':            False,
                'reason':             'not_found',
                'previous_status':    None,
                'new_status':         None,
                'previous_active_id': None,
            }
        prev_status   = row[2]
        guild_id      = row[3]
        prev_active   = None

        try:
            conn.execute("BEGIN")
            if status == 'active':
                # Demote any sibling active campaign in the same guild.
                sib = conn.execute(
                    "SELECT id FROM dnd_campaigns "
                    "WHERE guild_id=? AND status='active' AND id!=?",
                    (guild_id, campaign_id)
                ).fetchone()
                if sib is not None:
                    prev_active = sib[0]
                    conn.execute(
                        "UPDATE dnd_campaigns SET status='inactive' WHERE id=?",
                        (prev_active,)
                    )
            conn.execute(
                "UPDATE dnd_campaigns SET status=? WHERE id=?",
                (status, campaign_id)
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        log(f"campaign_set_status: campaign={campaign_id} name={row[1]!r} "
            f"{prev_status!r}→{status!r}"
            + (f" (demoted sibling={prev_active})" if prev_active else ""))
        return {
            'campaign_id':        campaign_id,
            'updated':            True,
            'reason':             None,
            'previous_status':    prev_status,
            'new_status':         status,
            'previous_active_id': prev_active,
        }
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────
# Scene state
# ─────────────────────────────────────────────────────────

def get_scene_state(campaign_id: int):
    """Return scene state dict for the campaign, or None."""
    import json
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT location, mode, focus, established_details, active_npcs, "
        "active_threats, open_questions, tension, last_player_action, "
        "last_scene_change, updated_at, tension_int, progress_clocks, "
        "last_dm_response, current_location_id, campaign_day, day_phase, "
        "last_active_actor "
        "FROM dnd_scene_state "
        "WHERE campaign_id=?",
        (campaign_id,)
    ).fetchone()
    conn.close()
    if not row:
        return None
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
        'tension_int': int(row[11]) if row[11] is not None else 0,
        'progress_clocks': json.loads(row[12] or '[]') if len(row) > 12 else [],
        'last_player_action': row[8] or '',
        'last_scene_change': row[9] or '',
        'last_dm_response': row[13] if len(row) > 13 and row[13] is not None else '',
        'current_location_id': row[14] if len(row) > 14 else None,
        # Track 4 #3 — time progression v1.
        'campaign_day': int(row[15]) if len(row) > 15 and row[15] is not None else 1,
        'day_phase': (row[16] if len(row) > 16 and row[16] else 'Morning'),
        # Bug 1 Phase 1 (S32) — footer-actor source of truth.
        'last_active_actor': row[17] if len(row) > 17 and row[17] is not None else '',
        'updated_at': row[10] or '',
    }


def init_scene_state(campaign_id: int, seed: str = ''):
    """Ensure a scene_state row exists for this campaign and stamp the latest
    scene-change seed. New rows get schema defaults across the board; existing
    rows preserve everything (mode, location, day/phase, clocks, NPCs, etc.)
    and only refresh `last_scene_change` + `updated_at`. /play is reopening
    a scene, not resetting it — gameplay-advanced state must survive."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO dnd_scene_state "
        "(campaign_id, location, mode, focus, established_details, active_npcs, "
        "active_threats, open_questions, tension, last_player_action, "
        "last_scene_change, updated_at) "
        "VALUES (?, '', 'exploration', '', '[]', '[]', '[]', '[]', 'low', '', ?, ?) "
        "ON CONFLICT(campaign_id) DO UPDATE SET "
        "last_scene_change=excluded.last_scene_change, "
        "updated_at=excluded.updated_at",
        (campaign_id, seed[:500], datetime.datetime.now().isoformat())
    )
    conn.commit()
    conn.close()
    log(f"scene state initialized for campaign {campaign_id}")


# ─────────────────────────────────────────────────────────
# Progress clocks
# ─────────────────────────────────────────────────────────
# Clocks are stored as a JSON list on dnd_scene_state:
#   [{"name": "Alarm Level", "capacity": 6, "ticks": 2}, ...]
# All writes go through set_clocks() so the column stays consistent.

def get_clocks(campaign_id: int) -> list:
    """Return the progress clocks for a campaign, or []."""
    state = get_scene_state(campaign_id)
    return list(state.get('progress_clocks') or []) if state else []


def set_clocks(campaign_id: int, clocks: list):
    """Persist the full clocks list for a campaign."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE dnd_scene_state SET progress_clocks=?, updated_at=? WHERE campaign_id=?",
        (json.dumps(clocks), _now(), campaign_id)
    )
    conn.commit()
    conn.close()


def clock_create(campaign_id: int, name: str, capacity: int) -> str:
    """Add a new clock. Returns error string or None on success."""
    clocks = get_clocks(campaign_id)
    if any(c['name'].lower() == name.lower() for c in clocks):
        return f"A clock named '{name}' already exists."
    if not 2 <= capacity <= 12:
        return "Capacity must be between 2 and 12."
    clocks.append({'name': name, 'capacity': capacity, 'ticks': 0})
    set_clocks(campaign_id, clocks)
    return None


def clock_tick(campaign_id: int, name: str, n: int = 1) -> tuple:
    """Advance a clock by n ticks. Returns (clock_dict, filled, error)."""
    clocks = get_clocks(campaign_id)
    for c in clocks:
        if c['name'].lower() == name.lower():
            c['ticks'] = min(c['ticks'] + n, c['capacity'])
            filled = c['ticks'] >= c['capacity']
            set_clocks(campaign_id, clocks)
            return c, filled, None
    return None, False, f"No clock named '{name}'."


def clock_untick(campaign_id: int, name: str, n: int = 1) -> tuple:
    """Walk back a clock by n ticks. Returns (clock_dict, error)."""
    clocks = get_clocks(campaign_id)
    for c in clocks:
        if c['name'].lower() == name.lower():
            c['ticks'] = max(c['ticks'] - n, 0)
            set_clocks(campaign_id, clocks)
            return c, None
    return None, f"No clock named '{name}'."


def clock_reset(campaign_id: int, name: str) -> str:
    """Reset a clock to 0 ticks. Returns error string or None."""
    clocks = get_clocks(campaign_id)
    for c in clocks:
        if c['name'].lower() == name.lower():
            c['ticks'] = 0
            set_clocks(campaign_id, clocks)
            return None
    return f"No clock named '{name}'."


def clock_delete(campaign_id: int, name: str) -> str:
    """Remove a clock entirely. Returns error string or None."""
    clocks = get_clocks(campaign_id)
    new_clocks = [c for c in clocks if c['name'].lower() != name.lower()]
    if len(new_clocks) == len(clocks):
        return f"No clock named '{name}'."
    set_clocks(campaign_id, new_clocks)
    return None


def clocks_to_prompt_block(clocks: list) -> str:
    """Render the active clocks as a compact prompt block."""
    if not clocks:
        return ""
    lines = []
    for c in clocks:
        ticks = c.get('ticks', 0)
        cap = c.get('capacity', 6)
        bar = "█" * ticks + "░" * (cap - ticks)
        pct = int(100 * ticks / cap) if cap else 0
        lines.append(f"  {c['name']}: [{bar}] {ticks}/{cap} ({pct}%)")
    return "=== PROGRESS CLOCKS ===\n" + "\n".join(lines)


def tension_label(tension_int: int) -> str:
    if tension_int <= 25:
        return "Calm"
    elif tension_int <= 60:
        return "Mounting"
    elif tension_int <= 85:
        return "Dangerous"
    else:
        return "Climax"


def calculate_tension_shift(current: int, avrae_events: list, no_damage_turn: bool = False) -> int:
    delta = 0
    for ev in (avrae_events or []):
        kind = ev.get('kind', '')
        damage = ev.get('damage')
        nat = ev.get('nat')
        if kind == 'rest':
            detail = ev.get('detail', '')
            if 'long' in str(detail).lower():
                return 0
            else:
                delta -= 40
        if damage is not None:
            try:
                delta += min(int(damage), 25)
            except (ValueError, TypeError):
                pass
        if nat == 1:
            delta += 10
    if no_damage_turn:
        delta -= 3
    return max(0, min(100, current + delta))


def update_tension(campaign_id: int, tension_int: int):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE dnd_scene_state SET tension_int=?, updated_at=? WHERE campaign_id=?",
        (tension_int, _now(), campaign_id)
    )
    conn.commit()
    conn.close()


def update_last_dm_response(campaign_id: int, text: str):
    """Persist the most recent DM narration for the campaign.

    Single writer of dnd_scene_state.last_dm_response. Called by dm_respond
    after the cleaned narration is finalized but before the turn counter
    increments, so the value is available to the next turn's
    compute_commitment_directive reaction-verb heuristic.

    Capped at 4000 chars — long enough to hold a full DM response, short
    enough to bound row growth. Truncation tail-wins because the latest
    paragraph (which is what reaction-verb heuristics are most likely to
    match against the player's prior commitment) is the load-bearing part.
    """
    if text is None:
        text = ''
    # Tail-keep the last 4000 chars so the most recent narrative beat
    # always survives truncation.
    text = text[-4000:]
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE dnd_scene_state SET last_dm_response=?, updated_at=? "
        "WHERE campaign_id=?",
        (text, _now(), campaign_id)
    )
    conn.commit()
    conn.close()


def update_last_active_actor(campaign_id: int, new_actor: str, trigger: str) -> None:
    """Persist the footer-actor and emit footer_actor_changed on transitions.

    Sole writer of dnd_scene_state.last_active_actor. Mode-disjoint:
      - exploration: called by _dm_respond_and_post after actor canonicalization
      - combat:      called by set_active_turn / clear_active_turn
      - session:     called by /play (clear path)

    No-op when the new actor matches the prior one (no log, no UPDATE).
    Otherwise emits `footer_actor_changed: campaign={N} from={old|none}
    to={new|none} trigger={trigger}` and writes the new value.

    Phase 2 reads this column to decide whether to auto-fire dm_respond on
    matched roll arrivals; Phase 1 ships read-only telemetry against it.

    `trigger` must be one of: dm_respond, play, combat_turn_set,
    combat_turn_clear. Other values are accepted (logged verbatim) so future
    write sites don't have to wait for a code change here, but the four-value
    enum is the locked spec set.
    """
    new_val = (new_actor or '').strip()
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute(
            "SELECT last_active_actor FROM dnd_scene_state WHERE campaign_id=?",
            (campaign_id,)
        ).fetchone()
        prior = (row[0] if row and row[0] is not None else '').strip()
        if prior == new_val:
            return
        conn.execute(
            "UPDATE dnd_scene_state SET last_active_actor=?, updated_at=? "
            "WHERE campaign_id=?",
            (new_val, _now(), campaign_id)
        )
        conn.commit()
        from_label = prior if prior else 'none'
        to_label = new_val if new_val else 'none'
        log(f"footer_actor_changed: campaign={campaign_id} "
            f"from={from_label} to={to_label} trigger={trigger}")
    finally:
        conn.close()


def set_scene_mode(campaign_id: int, mode: str):
    """Explicitly set the mode field. Called by combat detection or /mode command.
    Valid values: exploration, combat, social, travel, downtime."""
    valid = {'exploration', 'combat', 'social', 'travel', 'downtime'}
    if mode not in valid:
        log(f"set_scene_mode: invalid mode '{mode}', ignoring")
        return
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE dnd_scene_state SET mode=?, updated_at=? WHERE campaign_id=?",
        (mode, datetime.datetime.now().isoformat(), campaign_id)
    )
    conn.commit()
    conn.close()
    log(f"scene mode set to '{mode}' for campaign {campaign_id}")


# ─────────────────────────────────────────────────────────
# Time progression (Track 4 #3, Session 27)
# ─────────────────────────────────────────────────────────
# Single write path for campaign clock state — `advance_time()`. Six-phase
# enum + integer day counter. Skeleton-loader seed is the narrow §17
# exception (initialization-only, fresh-row gated). LLM never decides
# when time advances (Doctrine §1a). See TRACK_4_3_SPEC.md v1.2.

PHASES = ('Morning', 'Midday', 'Afternoon', 'Evening', 'Night', 'Late Night')
_PHASE_INDEX = {p: i for i, p in enumerate(PHASES)}
_VALID_TIME_SOURCES = ('travel', 'rest_long', 'rest_short', 'advance')
# Just-advanced recency window in seconds. §11.E sub-(iii)α — tunable
# from telemetry. Initial 60s; widen if `directive_emit:.*time=1`
# correlations against `time_advance:` show >5% missed-fires after
# tuning to 120s, then re-decide to (iii)β process-memory flag.
_JUST_ADVANCED_WINDOW_SEC = 60


class TimeAdvancement:
    """Result of a single advance_time() call. Carries before/after state,
    deltas, and the resolved-vs-requested distinction when set_phase wins
    over phase_delta (§11.I precedence invariant).
    """
    __slots__ = (
        'before_day', 'before_phase', 'after_day', 'after_phase',
        'days_delta', 'phase_delta', 'resolved_phase_delta',
        'source', 'source_detail', 'set_phase',
    )

    def __init__(self, before_day, before_phase, after_day, after_phase,
                 days_delta, phase_delta, resolved_phase_delta,
                 source, source_detail, set_phase):
        self.before_day = before_day
        self.before_phase = before_phase
        self.after_day = after_day
        self.after_phase = after_phase
        self.days_delta = days_delta
        self.phase_delta = phase_delta
        self.resolved_phase_delta = resolved_phase_delta
        self.source = source
        self.source_detail = source_detail
        self.set_phase = set_phase

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in self.__slots__}


def parse_elapsed(elapsed_str):
    """Map a free-text duration string to (days_delta, phase_delta) or None.
    Deterministic — no LLM. Always-fire telemetry per call.

    Per Appendix A of TRACK_4_3_SPEC.md v1.2. The parser is intentionally
    narrow; unhandled inputs return None and emit a `parse_elapsed:` log
    line so the keyword/regex table can be tuned from observed strings.

    Returns:
      (int, int)  — (days_delta, phase_delta), both >= 0
      None        — unparseable input
    """
    raw = (elapsed_str or '').strip().lower()
    # Always-fire log line (success or failure). Helper-local so the
    # caller doesn't need to remember to log.
    def _emit(result):
        if result is None:
            log(f"parse_elapsed: input={raw!r} result=none")
        else:
            log(f"parse_elapsed: input={raw!r} result={result[0]},{result[1]}")
        return result

    if not raw:
        return _emit(None)

    # Strip leading articles / hedges that don't change the unit math.
    cleaned = raw
    for prefix in ('about ', 'around ', 'roughly ', 'approximately '):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):]
            break

    EXACT = {
        'a day': (1, 0), 'one day': (1, 0), '1 day': (1, 0),
        'the day': (1, 0), 'next day': (1, 0),
        'overnight': (1, 0),
        'a week': (7, 0), 'one week': (7, 0), '1 week': (7, 0),
        'a few hours': (0, 1),
        'a couple hours': (0, 1), 'a couple of hours': (0, 1),
        'an hour': (0, 1), 'one hour': (0, 1), '1 hour': (0, 1),
        'half a day': (0, 3),
        'a half day': (0, 3),
        'a few minutes': (0, 0),
        'a couple minutes': (0, 0),
        'a moment': (0, 0),
        'a few seconds': (0, 0),
    }
    if cleaned in EXACT:
        return _emit(EXACT[cleaned])

    NUMBER_WORDS = {
        'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
        'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
        'eleven': 11, 'twelve': 12,
        'a couple': 2, 'a couple of': 2,
        'a few': 3, 'several': 4, 'a handful of': 4,
    }

    def _to_int(token: str):
        t = token.strip()
        if not t:
            return None
        if t.isdigit():
            try:
                return int(t)
            except ValueError:
                return None
        return NUMBER_WORDS.get(t)

    # Number-then-unit patterns in priority order. Days > weeks > hours
    # > minutes/seconds.
    PATTERNS = [
        (re.compile(r'^([a-z0-9 ]+?)\s+days?$'),
         lambda n: (n, 0)),
        (re.compile(r'^([a-z0-9 ]+?)\s+weeks?$'),
         lambda n: (n * 7, 0)),
        (re.compile(r'^([a-z0-9 ]+?)\s+months?$'),
         lambda n: (n * 30, 0)),
        # Hours: ~6h per phase per §11.A=a 6-phase mapping. ceil(n/6) so
        # 1h still bumps a phase.
        (re.compile(r'^([a-z0-9 ]+?)\s+hours?$'),
         lambda n: (n // 24, _hours_to_phases(n % 24))),
        (re.compile(r'^([a-z0-9 ]+?)\s+minutes?$'),
         lambda n: (0, 0)),
        (re.compile(r'^([a-z0-9 ]+?)\s+seconds?$'),
         lambda n: (0, 0)),
    ]
    for rx, fn in PATTERNS:
        m = rx.match(cleaned)
        if not m:
            continue
        token = m.group(1).strip()
        n = _to_int(token)
        if n is None:
            return _emit(None)
        if n < 0:
            return _emit(None)
        result = fn(n)
        if result[0] < 0 or result[1] < 0:
            return _emit(None)
        return _emit(result)

    return _emit(None)


def _hours_to_phases(hours: int) -> int:
    """Map an hours-remainder (0..23) to phase steps. ~6h per phase, but
    never less than 1 phase for any positive hour count (so 'an hour'
    still moves the clock)."""
    if hours <= 0:
        return 0
    # Ceiling-ish: 1..6h → 1 phase; 7..12h → 2 phases; etc.
    return max(1, (hours + 5) // 6)


def advance_time(
    campaign_id: int,
    days_delta: int,
    phase_delta: int,
    source: str,
    source_detail: str = '',
    set_phase=None,
):
    """Single write path for campaign time. Updates dnd_scene_state and
    appends to dnd_time_advancements atomically.

    Pure-internally over (current_day, current_phase, deltas, set_phase)
    → (new_day, new_phase). Validates inputs; returns None on failure
    (with a logged diagnostic). Soft-fail at the call site per §59.

    set_phase precedence (§11.I): when set_phase is not None, the writer
    ignores the caller's phase_delta and computes
    `resolved_phase_delta = (target_idx - current_idx) mod 6`. The audit
    log row records all three values for diagnostic clarity.

    Missing-campaign no-op (§8): if no scene_state row exists for
    campaign_id, returns None and emits
    `time_advance: campaign={N} source={...} err='no scene_state row'`
    without writing the audit log.

    Returns TimeAdvancement on success, None otherwise.
    """
    # ── Input validation ────────────────────────────────────
    if source not in _VALID_TIME_SOURCES:
        log(f"time_advance: campaign={campaign_id} source={source!r} "
            f"err='unknown source'")
        return None
    try:
        days_delta = int(days_delta)
        phase_delta = int(phase_delta)
    except (TypeError, ValueError):
        log(f"time_advance: campaign={campaign_id} source={source} "
            f"err='non-integer delta days={days_delta!r} phases={phase_delta!r}'")
        return None
    if days_delta < 0 or phase_delta < 0:
        log(f"time_advance: campaign={campaign_id} source={source} "
            f"err='negative delta days={days_delta} phases={phase_delta}' "
            f"(no rewind in v1)")
        return None
    if set_phase is not None and set_phase not in _PHASE_INDEX:
        log(f"time_advance: campaign={campaign_id} source={source} "
            f"err='invalid set_phase={set_phase!r}'")
        return None
    # No-op-zero rejection (§9 test 10) — only applies when set_phase is
    # also unset, since set_phase='Morning' from Morning is a legal
    # idempotent jump that the writer treats as zero-resolved-delta.
    if days_delta == 0 and phase_delta == 0 and set_phase is None:
        log(f"time_advance: campaign={campaign_id} source={source} "
            f"err='zero advance'")
        return None

    # ── Read current state (missing-row no-op contract) ─────
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute(
            "SELECT campaign_day, day_phase FROM dnd_scene_state "
            "WHERE campaign_id=?",
            (campaign_id,)
        ).fetchone()
        if row is None:
            log(f"time_advance: campaign={campaign_id} source={source} "
                f"err='no scene_state row'")
            return None
        before_day = int(row[0]) if row[0] is not None else 1
        before_phase = (row[1] if row[1] in _PHASE_INDEX else 'Morning')
        before_idx = _PHASE_INDEX[before_phase]

        # ── Compute new state ───────────────────────────────
        if set_phase is not None:
            # set_phase wins over phase_delta. Compute the resolved
            # delta as the modular distance from current to target.
            target_idx = _PHASE_INDEX[set_phase]
            resolved_phase_delta = (target_idx - before_idx) % 6
        else:
            resolved_phase_delta = phase_delta

        total_steps = before_idx + resolved_phase_delta + (days_delta * 6)
        new_day = before_day + (total_steps // 6)
        new_idx = total_steps % 6
        new_phase = PHASES[new_idx]

        # ── Single-transaction write ───────────────────────
        try:
            conn.execute("BEGIN")
            conn.execute(
                "UPDATE dnd_scene_state SET campaign_day=?, day_phase=?, "
                "updated_at=? WHERE campaign_id=?",
                (new_day, new_phase, _now(), campaign_id)
            )
            conn.execute(
                "INSERT INTO dnd_time_advancements "
                "(campaign_id, before_day, before_phase, after_day, after_phase, "
                "days_delta, phase_delta, resolved_phase_delta, set_phase, "
                "source, source_detail, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (campaign_id, before_day, before_phase, new_day, new_phase,
                 days_delta, phase_delta, resolved_phase_delta,
                 set_phase, source, source_detail or '', _now())
            )
            conn.commit()
        except Exception as e:
            conn.rollback()
            log(f"time_advance: campaign={campaign_id} source={source} "
                f"err={e!r}")
            return None
    finally:
        conn.close()

    # ── Always-fire telemetry ──────────────────────────────
    set_phase_log = (f" set_phase={set_phase}" if set_phase else '')
    resolved_log = (f" resolved_phase_delta={resolved_phase_delta}"
                    if set_phase else '')
    log(f"time_advance: campaign={campaign_id} source={source} "
        f"before={before_day},{before_phase} "
        f"after={new_day},{new_phase} "
        f"days_delta={days_delta} phase_delta={phase_delta}"
        f"{resolved_log}{set_phase_log} "
        f"detail={source_detail!r}")

    return TimeAdvancement(
        before_day=before_day,
        before_phase=before_phase,
        after_day=new_day,
        after_phase=new_phase,
        days_delta=days_delta,
        phase_delta=phase_delta,
        resolved_phase_delta=resolved_phase_delta,
        source=source,
        source_detail=source_detail or '',
        set_phase=set_phase,
    )


def time_just_advanced(campaign_id: int,
                       window_seconds: int = _JUST_ADVANCED_WINDOW_SEC) -> bool:
    """Recency check on dnd_time_advancements per §11.E sub-(iii)α.

    Returns True if there is at least one advancement row for the given
    campaign with `created_at` within `window_seconds` of now. Used by
    compute_time_directive's caller to decide whether the directive
    fires this turn.

    Pure-read; no writes. Soft-fails to False on DB error so missing
    just-advanced never crashes a turn.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        try:
            row = conn.execute(
                "SELECT created_at FROM dnd_time_advancements "
                "WHERE campaign_id=? ORDER BY id DESC LIMIT 1",
                (campaign_id,)
            ).fetchone()
        finally:
            conn.close()
        if not row or not row[0]:
            return False
        try:
            ts = datetime.datetime.fromisoformat(row[0])
        except (TypeError, ValueError):
            return False
        # _now() writes UTC isoformat without tz; compare in same wall.
        now = datetime.datetime.utcnow()
        delta = (now - ts).total_seconds()
        return 0 <= delta <= window_seconds
    except Exception as e:
        log(f"time_just_advanced: campaign={campaign_id} err={e!r}")
        return False


# ─── Combat Runtime State ─────────────────────────────────────────────────────
# Coordination state — who is the active turn controller per campaign.
# Separate from dnd_scene_state (narrative scope). Single write path per
# invariant: set_active_turn / clear_active_turn only. Never called from
# the LLM extraction thread.

def set_active_turn(campaign_id: int, controller_id: str, character_name: str, round_num: int) -> None:
    """Record the active turn controller. Called from _handle_init_event on 'turn' events."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT OR REPLACE INTO dnd_combat_state "
        "(campaign_id, controller_id, character_name, round, updated_at) VALUES (?,?,?,?,?)",
        (campaign_id, str(controller_id), character_name, round_num, _now())
    )
    conn.commit()
    conn.close()
    log(f"set_active_turn: campaign={campaign_id} name='{character_name}' controller={controller_id} round={round_num}")
    # Bug 1 Phase 1 (S32) — combat-mode footer-actor write. Mirrors the
    # exploration writer in _dm_respond_and_post; emits footer_actor_changed
    # via update_last_active_actor only when the actor actually transitions.
    try:
        update_last_active_actor(campaign_id, character_name or '', 'combat_turn_set')
    except Exception as e:
        log(f"update_last_active_actor failed (set_active_turn): {e!r}")


def get_active_turn(campaign_id: int) -> dict | None:
    """Return current turn state or None if no active combat turn recorded."""
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT controller_id, character_name, round, updated_at "
        "FROM dnd_combat_state WHERE campaign_id=?",
        (campaign_id,)
    ).fetchone()
    conn.close()
    if not row:
        log(f"get_active_turn: campaign={campaign_id} — no active turn")
        return None
    result = {
        'controller_id': row[0],
        'character_name': row[1],
        'round': row[2],
        'updated_at': row[3],
    }
    log(f"get_active_turn: campaign={campaign_id} name='{result['character_name']}' controller={result['controller_id']} round={result['round']}")
    return result


def clear_active_turn(campaign_id: int) -> None:
    """Clear combat turn state when combat ends. Prevents stale state leaking into the next combat."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM dnd_combat_state WHERE campaign_id=?", (campaign_id,))
    conn.commit()
    conn.close()
    log(f"clear_active_turn: campaign={campaign_id} — combat state cleared")
    # Bug 1 Phase 1 (S32) — combat-mode footer-actor clear. Mirrors the
    # set path; emits footer_actor_changed only on transition.
    try:
        update_last_active_actor(campaign_id, '', 'combat_turn_clear')
    except Exception as e:
        log(f"update_last_active_actor failed (clear_active_turn): {e!r}")


# ─── Per-Combatant Snapshot State (Session 21 — combat persistence directive) ─
# Populated by the avrae_listener parser branch on `!init list` plaintext.
# Replace-in-place per snapshot. Read by compute_persistence_directive.
# Single-writer invariant: only update_combatants_from_init_list and
# clear_combatants write here.

def update_combatants_from_init_list(campaign_id: int, parsed: dict) -> int:
    """Replace per-campaign rows with the parsed `!init list` snapshot.

    DELETE-then-INSERT in one transaction so the table is always consistent
    with the most recent snapshot. Combatants removed from Avrae since the
    last snapshot are dropped here automatically.

    parsed shape (from avrae_listener.parse_init_list_embed):
      {'round': int, 'current_init': int, 'combatants': [
         {'init', 'name', 'active', 'hp_current', 'hp_max',
          'conditions', 'alive'}, ...]}

    Death-edge detection (Track 4 #2): combatants whose alive flag transitioned
    1 -> 0 since the prior snapshot are passed to enqueue_loot_for_defeats.
    Player characters (bound via /bindchar) are filtered out — only NPC
    defeats trigger loot. Names that disappear entirely from the snapshot
    are NOT counted as defeats (could be `!init remove`, ambiguous in v1).

    Returns the count of inserted rows.
    """
    rows = (parsed or {}).get('combatants') or []
    now = _now()
    conn = sqlite3.connect(DB_PATH)
    try:
        # Capture prior alive state BEFORE the snapshot wipe — the diff is the
        # only deterministic defeat signal Avrae gives us in v1.
        prior_alive = {}
        try:
            prior_rows = conn.execute(
                "SELECT name, alive FROM dnd_combatant_state WHERE campaign_id=?",
                (campaign_id,)
            ).fetchall()
            for pr in prior_rows:
                pname = (pr[0] or '').strip()
                if pname:
                    prior_alive[pname] = 1 if pr[1] else 0
        except sqlite3.Error:
            prior_alive = {}

        conn.execute(
            "DELETE FROM dnd_combatant_state WHERE campaign_id=?",
            (campaign_id,)
        )
        inserted = 0
        new_alive: dict[str, int] = {}
        for c in rows:
            name = (c.get('name') or '').strip()
            if not name:
                continue
            try:
                init_val = int(c.get('init', 0))
            except (TypeError, ValueError):
                init_val = 0
            hp_cur = c.get('hp_current')
            hp_max = c.get('hp_max')
            conditions = (c.get('conditions') or '').strip()
            alive = 1 if c.get('alive', 1) else 0
            conn.execute(
                "INSERT INTO dnd_combatant_state "
                "(campaign_id, name, init, hp_current, hp_max, conditions, "
                "alive, side, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (campaign_id, name, init_val,
                 hp_cur if hp_cur is not None else None,
                 hp_max if hp_max is not None else None,
                 conditions, alive, 'unknown', now)
            )
            new_alive[name] = alive
            inserted += 1
        conn.commit()
    finally:
        conn.close()
    log(f"update_combatants_from_init_list: campaign={campaign_id} "
        f"rows={inserted}")

    # Death-edge: alive=1 in prior snapshot, alive=0 in new snapshot.
    newly_defeated: list[str] = [
        name for name, was_alive in prior_alive.items()
        if was_alive == 1 and new_alive.get(name) == 0
    ]
    if newly_defeated:
        try:
            pc_names = {n.strip() for n in get_bound_character_names(campaign_id) if n}
            pc_names_lower = {n.lower() for n in pc_names}
            npc_defeats = [
                n for n in newly_defeated
                if n not in pc_names and n.lower() not in pc_names_lower
            ]
            if npc_defeats:
                enqueue_loot_for_defeats(campaign_id, npc_defeats)
        except Exception as e:
            log(f"enqueue_loot_for_defeats error: {e}")
    return inserted


def clear_combatants(campaign_id: int) -> None:
    """Drop all combatant snapshot rows for this campaign.

    Called from _handle_init_event on init_event=='end' and from
    _handle_rest_event when current mode == 'combat', alongside
    clear_active_turn.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "DELETE FROM dnd_combatant_state WHERE campaign_id=?",
        (campaign_id,)
    )
    conn.commit()
    conn.close()
    log(f"clear_combatants: campaign={campaign_id} — combatants cleared")


def get_combatants(campaign_id: int) -> dict:
    """Return the latest combatant snapshot for this campaign.

    Returns {
        'combatants': [{name, init, hp_current, hp_max, conditions, alive, side}, ...]
                       ordered by init DESC, then name ASC for ties,
        'snapshot_age_s': float | None,
    }

    snapshot_age_s is None when no rows exist; otherwise it's the seconds
    since the most recent updated_at (max across rows for this campaign,
    though all rows from one snapshot share the same updated_at).
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT name, init, hp_current, hp_max, conditions, alive, side, updated_at "
        "FROM dnd_combatant_state WHERE campaign_id=? "
        "ORDER BY init DESC, name ASC",
        (campaign_id,)
    ).fetchall()
    conn.close()

    if not rows:
        return {'combatants': [], 'snapshot_age_s': None}

    combatants = []
    latest_iso = None
    for r in rows:
        combatants.append({
            'name': r['name'],
            'init': r['init'],
            'hp_current': r['hp_current'],
            'hp_max': r['hp_max'],
            'conditions': r['conditions'] or '',
            'alive': r['alive'],
            'side': r['side'],
        })
        if latest_iso is None or (r['updated_at'] or '') > latest_iso:
            latest_iso = r['updated_at']

    snapshot_age_s = None
    if latest_iso:
        try:
            from datetime import datetime, timezone
            dt = datetime.fromisoformat(latest_iso)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            snapshot_age_s = (datetime.now(timezone.utc) - dt).total_seconds()
        except Exception:
            snapshot_age_s = None
    return {'combatants': combatants, 'snapshot_age_s': snapshot_age_s}


# ─── Pending DM Roll Directives (Bug 1 Phase 1, Session 32) ──────────────────
# Per-campaign pending row representing the most recent DM `!check` / `!save`
# / `!cast` directive that hasn't yet matched an Avrae roll. Single-writer
# invariant: only the matcher (in discord_dnd_bot.py) writes via these
# helpers. UNIQUE(campaign_id) means at most one pending directive per
# campaign — later directives REPLACE prior unresolved ones (the matcher
# logs `pending_directive_replaced` before swapping).
#
# TTL-expiry is lazy: pending_directive_get_active() sweeps and logs
# `pending_directive_expired` whenever it finds a row past expires_at.

def pending_directive_upsert(campaign_id: int, actor_name: str,
                             check_type: str, source_message_id: str,
                             ttl_seconds: int,
                             dc: int | None = None) -> dict:
    """Insert or replace the pending roll directive for this campaign.

    Returns a dict {'replaced': bool, 'prior': {actor_name, check_type,
    created_at} | None}. Caller logs `pending_directive_replaced` if
    `replaced` is True.

    `dc` is the DM-set difficulty class parsed at directive-emit time per
    RESOLUTION_BINDING_SPEC.md §6. None means the DM did not include a DC
    in the directive; resolution binding falls through to free-narration
    (§11.2 lock).
    """
    import datetime as _dt
    now_dt = _dt.datetime.utcnow()
    expires_dt = now_dt + _dt.timedelta(seconds=int(ttl_seconds))
    now_iso = now_dt.isoformat()
    expires_iso = expires_dt.isoformat()
    conn = sqlite3.connect(DB_PATH)
    try:
        prior_row = conn.execute(
            "SELECT actor_name, check_type, created_at "
            "FROM dnd_pending_roll_directives WHERE campaign_id=?",
            (campaign_id,)
        ).fetchone()
        prior = None
        replaced = False
        if prior_row:
            prior = {
                'actor_name':  prior_row[0] or '',
                'check_type':  prior_row[1] or '',
                'created_at':  prior_row[2] or '',
            }
            replaced = True
        conn.execute(
            "INSERT OR REPLACE INTO dnd_pending_roll_directives "
            "(campaign_id, actor_name, check_type, source_message_id, "
            " created_at, expires_at, dc) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (campaign_id, actor_name, check_type,
             str(source_message_id), now_iso, expires_iso,
             int(dc) if isinstance(dc, int) else None)
        )
        conn.commit()
    finally:
        conn.close()
    return {'replaced': replaced, 'prior': prior}


def pending_directive_get_active(campaign_id: int) -> dict | None:
    """Return the active (non-expired) pending directive for this campaign,
    sweeping any expired row and logging `pending_directive_expired`.

    Returns None when no row exists OR when the row was just-expired.
    """
    import datetime as _dt
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute(
            "SELECT actor_name, check_type, source_message_id, "
            "       created_at, expires_at, dc "
            "FROM dnd_pending_roll_directives WHERE campaign_id=?",
            (campaign_id,)
        ).fetchone()
        if not row:
            return None
        actor_name, check_type, source_message_id, created_at, expires_at, dc = row
        now_dt = _dt.datetime.utcnow()
        try:
            exp_dt = _dt.datetime.fromisoformat(expires_at)
        except Exception:
            # Malformed expires_at — treat as expired and sweep.
            exp_dt = now_dt - _dt.timedelta(seconds=1)
        if now_dt >= exp_dt:
            try:
                created_dt = _dt.datetime.fromisoformat(created_at)
                age_s = int((now_dt - created_dt).total_seconds())
            except Exception:
                age_s = -1
            conn.execute(
                "DELETE FROM dnd_pending_roll_directives WHERE campaign_id=?",
                (campaign_id,)
            )
            conn.commit()
            log(f"pending_directive_expired: campaign={campaign_id} "
                f"actor={actor_name} skill={check_type} age_s={age_s}")
            return None
        return {
            'actor_name':         actor_name or '',
            'check_type':         check_type or '',
            'source_message_id':  source_message_id or '',
            'created_at':         created_at or '',
            'expires_at':         expires_at or '',
            'dc':                 (int(dc) if isinstance(dc, int) else None),
            'campaign_id':        campaign_id,
        }
    finally:
        conn.close()


def pending_directive_age_seconds(created_at: str) -> int:
    """Helper: seconds since a directive was created. Returns -1 on parse failure."""
    import datetime as _dt
    try:
        created_dt = _dt.datetime.fromisoformat(created_at)
        return int((_dt.datetime.utcnow() - created_dt).total_seconds())
    except Exception:
        return -1


def pending_directive_consume(campaign_id: int) -> bool:
    """Delete the pending directive for this campaign. Returns True if a
    row was deleted, False otherwise. Used after a successful match."""
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.execute(
            "DELETE FROM dnd_pending_roll_directives WHERE campaign_id=?",
            (campaign_id,)
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def pending_directive_delete_by_message(campaign_id: int,
                                        source_message_id: str) -> dict | None:
    """Delete the pending directive iff it was created by this source
    message. Returns the deleted row dict (for cancel-edit logging) or None
    if nothing matched.
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute(
            "SELECT actor_name, check_type, created_at "
            "FROM dnd_pending_roll_directives "
            "WHERE campaign_id=? AND source_message_id=?",
            (campaign_id, str(source_message_id))
        ).fetchone()
        if not row:
            return None
        conn.execute(
            "DELETE FROM dnd_pending_roll_directives "
            "WHERE campaign_id=? AND source_message_id=?",
            (campaign_id, str(source_message_id))
        )
        conn.commit()
        return {
            'actor_name':  row[0] or '',
            'check_type':  row[1] or '',
            'created_at':  row[2] or '',
        }
    finally:
        conn.close()


# ─── Narrative Inventory (Track 4 #1) ────────────────────────────────────────
# Per-character narrative items: loot, quest objects, story items, found gear.
# Distinct from Avrae sheet-bound combat gear — Avrae owns weapons / armor /
# equipment that affect rolls; Virgil inventory holds the narrative layer.
# Naming convention: item_name stored LOWERCASE; lookup case-insensitive.
# (`silver key` / `Silver Key` / `SILVER KEY` all collapse to the same row.)
# Single-writer invariant: add_item / remove_item only. clear_inventory exists
# for the cascade-delete path; LLM extraction never writes here.


def _normalize_item_name(item_name: str) -> str:
    """Lowercase + collapse whitespace. Storage key + lookup key.
    Empty / None input returns ''."""
    if not item_name:
        return ''
    return ' '.join(item_name.lower().split())


def add_item(campaign_id: int, character_name: str, item_name: str,
             quantity: int = 1, metadata: str | None = None) -> dict:
    """Add `quantity` of `item_name` to (campaign, character)'s inventory.

    If a row already exists for (campaign_id, character_name, normalized
    item_name): increment its quantity, return action='incremented'.
    Else INSERT a new row, return action='inserted'.

    Item names are stored lowercase (collapse-whitespace normalized).
    metadata is opaque text; v1 doesn't consume it but the column is
    reserved for future v1.x enrichment (rarity, source, weight, etc.).

    Returns {item_name, quantity_now, action}. quantity_now is the post-
    add total for this row.

    Single writer for inventory inserts + quantity-up. Refuses non-positive
    quantities (returns action='invalid' with quantity_now=None).
    """
    if quantity is None or quantity <= 0:
        return {'item_name': _normalize_item_name(item_name),
                'quantity_now': None, 'action': 'invalid'}
    norm = _normalize_item_name(item_name)
    if not norm or not character_name:
        return {'item_name': norm, 'quantity_now': None, 'action': 'invalid'}

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        existing = conn.execute(
            "SELECT id, quantity FROM dnd_inventory "
            "WHERE campaign_id=? AND character_name=? AND item_name=?",
            (campaign_id, character_name, norm)
        ).fetchone()
        if existing:
            new_q = (existing['quantity'] or 0) + quantity
            conn.execute(
                "UPDATE dnd_inventory SET quantity=? WHERE id=?",
                (new_q, existing['id'])
            )
            conn.commit()
            log(f"inventory_add: campaign={campaign_id} character={character_name!r} "
                f"item={norm!r} qty={quantity} action=incremented")
            return {'item_name': norm, 'quantity_now': new_q, 'action': 'incremented'}
        conn.execute(
            "INSERT INTO dnd_inventory "
            "(campaign_id, character_name, item_name, quantity, metadata, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (campaign_id, character_name, norm, quantity, metadata, _now())
        )
        conn.commit()
        log(f"inventory_add: campaign={campaign_id} character={character_name!r} "
            f"item={norm!r} qty={quantity} action=inserted")
        return {'item_name': norm, 'quantity_now': quantity, 'action': 'inserted'}
    finally:
        conn.close()


def remove_item(campaign_id: int, character_name: str, item_name: str,
                quantity: int = 1) -> dict:
    """Decrement `quantity` from (campaign, character)'s inventory row.

    If the post-decrement quantity would be <= 0: DELETE the row,
    return action='removed' with quantity_now=None.
    If the post-decrement quantity is > 0: UPDATE in place,
    return action='decremented' with quantity_now=new total.
    If the row doesn't exist: return action='not_found'.
    If the requested quantity exceeds what's in stock: REFUSE the
    decrement (no mutation), return action='insufficient' with
    quantity_now=current quantity unchanged.

    Single writer for inventory decrements/deletes. Refuses non-positive
    quantities (returns action='invalid').
    """
    if quantity is None or quantity <= 0:
        return {'item_name': _normalize_item_name(item_name),
                'quantity_now': None, 'action': 'invalid'}
    norm = _normalize_item_name(item_name)
    if not norm or not character_name:
        return {'item_name': norm, 'quantity_now': None, 'action': 'invalid'}

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        existing = conn.execute(
            "SELECT id, quantity FROM dnd_inventory "
            "WHERE campaign_id=? AND character_name=? AND item_name=?",
            (campaign_id, character_name, norm)
        ).fetchone()
        if not existing:
            log(f"inventory_remove: campaign={campaign_id} character={character_name!r} "
                f"item={norm!r} qty={quantity} action=not_found")
            return {'item_name': norm, 'quantity_now': None, 'action': 'not_found'}
        cur_q = existing['quantity'] or 0
        if quantity > cur_q:
            log(f"inventory_remove: campaign={campaign_id} character={character_name!r} "
                f"item={norm!r} qty={quantity} action=insufficient (have {cur_q})")
            return {'item_name': norm, 'quantity_now': cur_q, 'action': 'insufficient'}
        new_q = cur_q - quantity
        if new_q <= 0:
            conn.execute("DELETE FROM dnd_inventory WHERE id=?", (existing['id'],))
            conn.commit()
            log(f"inventory_remove: campaign={campaign_id} character={character_name!r} "
                f"item={norm!r} qty={quantity} action=removed")
            return {'item_name': norm, 'quantity_now': None, 'action': 'removed'}
        conn.execute(
            "UPDATE dnd_inventory SET quantity=? WHERE id=?", (new_q, existing['id'])
        )
        conn.commit()
        log(f"inventory_remove: campaign={campaign_id} character={character_name!r} "
            f"item={norm!r} qty={quantity} action=decremented")
        return {'item_name': norm, 'quantity_now': new_q, 'action': 'decremented'}
    finally:
        conn.close()


def get_inventory(campaign_id: int, character_name: str) -> list[dict]:
    """Return [{item_name, quantity, metadata, created_at}, ...] for the
    given (campaign, character), ordered by item_name ASC. Pure read, no
    side effects. Empty list when no rows exist."""
    if not character_name:
        return []
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT item_name, quantity, metadata, created_at FROM dnd_inventory "
            "WHERE campaign_id=? AND character_name=? ORDER BY item_name ASC",
            (campaign_id, character_name)
        ).fetchall()
        return [
            {'item_name': r['item_name'], 'quantity': r['quantity'],
             'metadata': r['metadata'], 'created_at': r['created_at']}
            for r in rows
        ]
    finally:
        conn.close()


def has_item(campaign_id: int, character_name: str, item_name: str,
             min_quantity: int = 1) -> bool:
    """Pure read. Case-insensitive (whitespace-collapse) name match against
    the normalized stored form. Returns True iff a row exists for
    (campaign_id, character_name, normalized item_name) with quantity
    >= min_quantity. v1 uses exact-after-normalize match — no substring,
    no fuzzy. Reserved for future enrichment if the (deferred) item-claim
    capability layer wants softer matching."""
    if not character_name or min_quantity <= 0:
        return False
    norm = _normalize_item_name(item_name)
    if not norm:
        return False
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute(
            "SELECT quantity FROM dnd_inventory "
            "WHERE campaign_id=? AND character_name=? AND item_name=?",
            (campaign_id, character_name, norm)
        ).fetchone()
        return bool(row and (row[0] or 0) >= min_quantity)
    finally:
        conn.close()


# ─── Pending Loot Queue (Track 4 #2) ─────────────────────────────────────────
# Populated by update_combatants_from_init_list when a combatant transitions
# alive=1 -> alive=0. Surfaced by compute_loot_directive on the next narration
# turn. Surface-and-clear: rows are marked surfaced=1 in dm_respond AFTER the
# LLM call succeeds. v1 contract: loot is mechanically generated but NOT auto-
# added to inventory — the player claims via /giveitem or DM-mediated narration.


def enqueue_loot(campaign_id: int, creature: str, table_key: str,
                 coin: dict | None, items: list[str]) -> dict:
    """INSERT a pending loot row. Single writer for dnd_loot_pending inserts.

    coin shape: {'amount': int, 'denom': str} | None.
    items: list of item-name strings (stored as JSON).

    Returns {id, creature, table_key, coin, items}.
    """
    creature = (creature or '').strip()
    if not creature or not table_key:
        return {'id': None, 'creature': creature, 'table_key': table_key,
                'coin': coin, 'items': list(items or [])}
    items_json = json.dumps(list(items or []))
    coin_amount = coin['amount'] if (coin and 'amount' in coin) else None
    coin_denom = coin['denom'] if (coin and 'denom' in coin) else None
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.execute(
            "INSERT INTO dnd_loot_pending "
            "(campaign_id, creature, table_key, coin_amount, coin_denom, "
            " items, surfaced, surfaced_at, created_at) "
            "VALUES (?,?,?,?,?,?,0,NULL,?)",
            (campaign_id, creature, table_key,
             coin_amount, coin_denom, items_json, _now())
        )
        new_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    log(f"loot_generated: campaign={campaign_id} "
        f"creature={creature!r} "
        f"coin_amt={coin_amount if coin_amount is not None else 'none'} "
        f"coin_denom={coin_denom if coin_denom else 'none'} "
        f"items={len(items or [])}")
    return {'id': new_id, 'creature': creature, 'table_key': table_key,
            'coin': coin, 'items': list(items or [])}


def mark_loot_surfaced(loot_id: int) -> None:
    """Flip a row's surfaced flag to 1 with surfaced_at=now.
    Single writer for the surface counter."""
    if loot_id is None:
        return
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "UPDATE dnd_loot_pending SET surfaced=1, surfaced_at=? "
            "WHERE id=?",
            (_now(), loot_id)
        )
        conn.commit()
    finally:
        conn.close()


def get_pending_loot(campaign_id: int) -> list[dict]:
    """Return pending (surfaced=0) loot rows for this campaign, ordered by
    created_at ASC. Items decoded from JSON. coin folded back into a dict.
    Pure read."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT id, creature, table_key, coin_amount, coin_denom, "
            "items, created_at "
            "FROM dnd_loot_pending "
            "WHERE campaign_id=? AND surfaced=0 "
            "ORDER BY created_at ASC, id ASC",
            (campaign_id,)
        ).fetchall()
    finally:
        conn.close()
    out = []
    for r in rows:
        try:
            items = json.loads(r['items']) if r['items'] else []
            if not isinstance(items, list):
                items = []
        except (json.JSONDecodeError, TypeError):
            items = []
        coin = None
        if r['coin_amount'] is not None and r['coin_denom']:
            coin = {'amount': r['coin_amount'], 'denom': r['coin_denom']}
        out.append({
            'id':         r['id'],
            'creature':   r['creature'],
            'table_key':  r['table_key'],
            'coin':       coin,
            'coin_amount': r['coin_amount'],
            'coin_denom': r['coin_denom'],
            'items':      items,
            'created_at': r['created_at'],
        })
    return out


def enqueue_loot_for_defeats(campaign_id: int, creature_names: list[str]) -> int:
    """For each newly-defeated creature, generate and enqueue a loot row.

    Composition helper around generate_loot + enqueue_loot. Used by
    update_combatants_from_init_list when alive=1 -> alive=0 transitions
    are detected. Returns the count of rows enqueued. Empty input -> 0.
    """
    if not creature_names:
        return 0
    import loot_tables as _lt
    n = 0
    for name in creature_names:
        if not name or not name.strip():
            continue
        loot = _lt.generate_loot(name)
        log(f"defeat_parsed: campaign={campaign_id} "
            f"creature={loot['creature']!r} table={loot['table_key']} "
            f"coin={loot['coin']['amount'] if loot['coin'] else 'none'}")
        enqueue_loot(
            campaign_id,
            loot['creature'],
            loot['table_key'],
            loot['coin'],
            loot['items'],
        )
        n += 1
    return n


# ─── Quest Log (2C.2) ─────────────────────────────────────────────────────────
# DM-only via slash commands. No LLM extraction — quest lifecycle is structural,
# managed by deterministic write paths. Active quests inject into the DM prompt.

VALID_QUEST_STATUSES = {'active', 'completed', 'failed'}
VALID_QUEST_PRIORITIES = {'low', 'normal', 'urgent'}


def quest_add(campaign_id: int, title: str, summary: str = '',
              priority: str = 'normal', given_by: str = '') -> int:
    """Create a new active quest. Returns the new quest id."""
    if priority not in VALID_QUEST_PRIORITIES:
        priority = 'normal'
    ts = _now()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(
        "INSERT INTO dnd_quests "
        "(campaign_id, title, summary, status, priority, given_by, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (campaign_id, title, summary, 'active', priority, given_by, ts, ts)
    )
    quest_id = cur.lastrowid
    conn.commit()
    conn.close()
    log(f"quest_add: campaign={campaign_id} id={quest_id} title='{title}' priority={priority}")
    return quest_id


def quest_set_status(campaign_id: int, quest_id: int, status: str) -> bool:
    """Update a quest's status. Returns True if a row was updated."""
    if status not in VALID_QUEST_STATUSES:
        log(f"quest_set_status: invalid status '{status}'")
        return False
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(
        "UPDATE dnd_quests SET status=?, updated_at=? WHERE id=? AND campaign_id=?",
        (status, _now(), quest_id, campaign_id)
    )
    updated = cur.rowcount > 0
    conn.commit()
    conn.close()
    if updated:
        log(f"quest_set_status: campaign={campaign_id} id={quest_id} → {status}")
    return updated


def quest_delete(campaign_id: int, quest_id: int) -> bool:
    """Permanently delete a quest. Returns True if a row was removed."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(
        "DELETE FROM dnd_quests WHERE id=? AND campaign_id=?",
        (quest_id, campaign_id)
    )
    deleted = cur.rowcount > 0
    conn.commit()
    conn.close()
    if deleted:
        log(f"quest_delete: campaign={campaign_id} id={quest_id}")
    return deleted


def get_active_quests(campaign_id: int) -> list:
    """Return all active quests for the campaign, oldest first."""
    return get_all_quests(campaign_id, status_filter='active')


def get_all_quests(campaign_id: int, status_filter: str = None) -> list:
    """Return quests for the campaign, optionally filtered by status."""
    conn = sqlite3.connect(DB_PATH)
    if status_filter and status_filter in VALID_QUEST_STATUSES:
        rows = conn.execute(
            "SELECT id, title, summary, status, priority, given_by, created_at, updated_at "
            "FROM dnd_quests WHERE campaign_id=? AND status=? ORDER BY id ASC",
            (campaign_id, status_filter)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, title, summary, status, priority, given_by, created_at, updated_at "
            "FROM dnd_quests WHERE campaign_id=? ORDER BY id ASC",
            (campaign_id,)
        ).fetchall()
    conn.close()
    return [
        {
            'id': r[0], 'title': r[1], 'summary': r[2], 'status': r[3],
            'priority': r[4], 'given_by': r[5],
            'created_at': r[6], 'updated_at': r[7],
        }
        for r in rows
    ]


def quests_to_prompt_block(quests: list, max_shown: int = 5) -> str:
    """Format active quests as a prompt block. Returns empty string if no
    quests. Active-only — completed/failed never inject into the system prompt."""
    active = [q for q in quests if q.get('status') == 'active']
    if not active:
        return ""
    # Priority order: urgent > normal > low. Within priority, oldest first.
    priority_rank = {'urgent': 0, 'normal': 1, 'low': 2}
    active.sort(key=lambda q: (priority_rank.get(q.get('priority', 'normal'), 1), q['id']))

    shown = active[:max_shown]
    overflow = len(active) - len(shown)

    lines = ["=== ACTIVE QUESTS ==="]
    for q in shown:
        annotations = []
        given_by = (q.get('given_by') or '').strip()
        if given_by:
            annotations.append(f"given by {given_by}")
        priority = q.get('priority', 'normal')
        if priority != 'normal':
            annotations.append(priority)
        annotation_str = f" ({', '.join(annotations)})" if annotations else ""
        summary = (q.get('summary') or '').strip()
        if summary:
            lines.append(f"- {q['title']}{annotation_str}: {summary}")
        else:
            lines.append(f"- {q['title']}{annotation_str}")
    if overflow > 0:
        lines.append(f"({overflow} more — use /quest list to see all)")
    return "\n".join(lines)


# ─── Companions (2C.3) ────────────────────────────────────────────────────────
# DM-managed NPCs that travel with the party. Pure prompt content — no
# mechanical state, no autonomous logic. The DM (LLM) gives them voice when
# their persona is naturally relevant to the scene.

COMPANION_CAP = 3


def companion_add(campaign_id: int, name: str, persona: str = '') -> int | None:
    """Create a new companion. Returns the new id, or None if at cap."""
    existing = get_companions(campaign_id)
    if len(existing) >= COMPANION_CAP:
        log(f"companion_add: campaign={campaign_id} at cap ({COMPANION_CAP}), refused '{name}'")
        return None
    ts = _now()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(
        "INSERT INTO dnd_companions "
        "(campaign_id, name, persona, created_at, updated_at) VALUES (?,?,?,?,?)",
        (campaign_id, name, persona, ts, ts)
    )
    cid = cur.lastrowid
    conn.commit()
    conn.close()
    log(f"companion_add: campaign={campaign_id} id={cid} name='{name}'")
    return cid


def companion_remove(campaign_id: int, companion_id: int) -> bool:
    """Delete a companion. Returns True if a row was removed."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(
        "DELETE FROM dnd_companions WHERE id=? AND campaign_id=?",
        (companion_id, campaign_id)
    )
    removed = cur.rowcount > 0
    conn.commit()
    conn.close()
    if removed:
        log(f"companion_remove: campaign={campaign_id} id={companion_id}")
    return removed


def companion_edit(campaign_id: int, companion_id: int,
                   name: str = None, persona: str = None) -> bool:
    """Update a companion's name and/or persona. Returns True if updated."""
    sets = []
    values = []
    if name is not None:
        sets.append("name=?")
        values.append(name)
    if persona is not None:
        sets.append("persona=?")
        values.append(persona)
    if not sets:
        return False
    sets.append("updated_at=?")
    values.append(_now())
    values.extend([companion_id, campaign_id])
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(
        f"UPDATE dnd_companions SET {', '.join(sets)} WHERE id=? AND campaign_id=?",
        values
    )
    updated = cur.rowcount > 0
    conn.commit()
    conn.close()
    if updated:
        log(f"companion_edit: campaign={campaign_id} id={companion_id}")
    return updated


def get_companions(campaign_id: int) -> list:
    """Return all companions for the campaign, oldest first."""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT id, name, persona, created_at, updated_at "
        "FROM dnd_companions WHERE campaign_id=? ORDER BY id ASC",
        (campaign_id,)
    ).fetchall()
    conn.close()
    return [
        {
            'id': r[0], 'name': r[1], 'persona': r[2],
            'created_at': r[3], 'updated_at': r[4],
        }
        for r in rows
    ]


def companions_to_prompt_block(companions: list) -> str:
    """Format companions as a prompt block. Returns empty string if no
    companions. Includes the directive that keeps the DM from over-using
    them — companions are background presence, not co-protagonists."""
    if not companions:
        return ""
    lines = ["=== TRAVELING COMPANIONS ==="]
    for c in companions:
        persona = (c.get('persona') or '').strip()
        if persona:
            lines.append(f"{c['name']} — {persona}")
        else:
            lines.append(f"{c['name']}")
    lines.append(
        "These NPCs travel with the party. Have them speak occasionally — "
        "when their persona is naturally relevant, NOT every turn. They are "
        "background presence, not co-protagonists."
    )
    return "\n".join(lines)


# ─── Persistent NPCs (Phase 12A) ──────────────────────────────────────────────
# Canonical narrative entities. Authoritative — the table answers "who exists
# in this world." Distinct from dnd_companions (party-bound).
#
# Hard rules (PHASE_12_SPEC §4, §9.1, §9.10):
#   - npc_upsert() is the ONLY write path. Parsers and the skeleton loader
#     both go through it.
#   - Lookup is strict literal match on canonicalize_name(). No fuzzy matching.
#   - skeleton_origin=1 rows are authored canon. Parser hits NEVER overwrite
#     their fields. They DO bump mention_count/last_mentioned for recency.
#   - Auto-promotion (parser→skeleton) does NOT happen. Only an explicit
#     skeleton_origin=True call (the skeleton loader, 12C.2) sets the flag.

def canonicalize_name(s: str) -> str:
    """Normalize a name for canonical lookup. PURE normalization — not fuzzy:
      - strip leading/trailing whitespace
      - collapse internal whitespace runs to single space
      - normalize curly quotes/apostrophes to ASCII
      - PRESERVE capitalization (distinguishes proper from common nouns)

    See PHASE_12_SPEC §9.1. This is intentionally not lowercasing — "Garrick"
    and "garrick" should NOT collapse, because the parser only emits proper
    nouns and lowercase variants are likely a different entity or a miss.
    """
    if not s:
        return ''
    # Curly quotes/apostrophes → ASCII
    s = s.replace('\u2018', "'").replace('\u2019', "'")
    s = s.replace('\u201C', '"').replace('\u201D', '"')
    # Strip + collapse whitespace runs
    s = ' '.join(s.split())
    return s


def canonicalize_actor_name(s: str) -> str:
    """Normalize a player-character name for cross-system identity matching.
    See PHASE_6_IDENTITY_SPEC \u00A73 (6A).

    Differs from canonicalize_name in TWO ways:
      - LOWERCASES (so sheet "Donovan Ruby" and roll-embed "donovan ruby"
        canonicalize to the same string).
      - Does NOT strip honorifics. Different strings = different identities;
        explicit aliases via register_actor_alias are how operators record
        equivalence.

    Pure normalization. No fuzzy matching, no substring inference. Empty
    or None returns ''. Idempotent.
    """
    if not s:
        return ''
    s = s.replace('\u2018', "'").replace('\u2019', "'")
    s = s.replace('\u201C', '"').replace('\u201D', '"')
    s = ' '.join(s.split()).lower()
    return s


def levenshtein_distance(a: str, b: str) -> int:
    """Edit distance between two strings (insertions, deletions, substitutions).

    Used for near-match logging on canonical writes (S23 observability batch).
    O(len(a) * len(b)) time, O(len(b)) space. NPC/location names are short so
    this is instant in practice.

    Pure function — no side effects, no DB access.
    """
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            curr[j] = min(
                curr[j - 1] + 1,                        # insert into a
                prev[j] + 1,                            # delete from a
                prev[j - 1] + (0 if ca == cb else 1),  # substitute
            )
        prev = curr
    return prev[len(b)]


def _npc_row_to_dict(row) -> dict:
    """Convert a SELECT * row to a dict. Parses aliases JSON back to a list."""
    if row is None:
        return None
    try:
        aliases = json.loads(row[3]) if row[3] else []
        if not isinstance(aliases, list):
            aliases = []
    except (json.JSONDecodeError, TypeError):
        aliases = []
    return {
        'id':              row[0],
        'campaign_id':     row[1],
        'canonical_name':  row[2],
        'aliases':         aliases,
        'role':            row[4],
        'location_id':     row[5],
        'description':     row[6],
        'skeleton_origin': row[7],
        'mention_count':   row[8],
        'origin_excerpt':  row[9],
        'first_mentioned': row[10],
        'last_mentioned':  row[11],
        'hp_max':          row[12] if len(row) > 12 else None,
        'ac':              row[13] if len(row) > 13 else None,
        'attack_bonus':    row[14] if len(row) > 14 else None,
        'damage_dice':     row[15] if len(row) > 15 else None,
        'save_bonus':      row[16] if len(row) > 16 else None,
        'init_mod':        row[17] if len(row) > 17 else None,
        'cr_str':          row[18] if len(row) > 18 else None,
        'avrae_source':    row[19] if len(row) > 19 else None,
    }


_NPC_COLS = ("id, campaign_id, canonical_name, aliases, role, location_id, "
             "description, skeleton_origin, mention_count, origin_excerpt, "
             "first_mentioned, last_mentioned, "
             "hp_max, ac, attack_bonus, damage_dice, save_bonus, init_mod, cr_str, avrae_source")


def npc_upsert(campaign_id: int, name: str, role: str = '',
               location_id: int = None, description: str = '',
               origin_excerpt: str = '',
               skeleton_origin: bool = False) -> tuple[int, bool] | None:
    """Insert or update an NPC by (campaign_id, canonicalize_name(name)).
    Returns (row_id, was_new: bool), or None on empty/invalid name or refusal.
    was_new=True on INSERT, was_new=False on UPDATE. Callers that only need
    success/failure can check `if result:` — None is falsy, tuple is truthy.

    Behaviour matrix (existing × incoming):
      - missing × any         → INSERT, mention_count=1
      - skeleton × parser     → bump mention_count + last_mentioned ONLY
                                (authored fields locked, §4)
      - parser × skeleton     → promote to skeleton_origin=1, authored fields
                                win (12C.2 skeleton loader uses this path)
      - skeleton × skeleton   → re-load: update fields, no mention bump
      - parser × parser       → fill empty fields, bump mention_count + ts;
                                non-empty conflicts log and keep existing
    """
    canonical = canonicalize_name(name)
    if not canonical:
        log(f"npc_upsert: empty canonical name for campaign={campaign_id}, refused")
        return None

    # PC contamination guard. Refuse names that share token-prefix relationship
    # with any bound PC for this campaign (Donovan Ruby ↔ Donovan ↔ Donovan
    # Ruby's Coinpurse, etc.). Engine defends the invariant: PCs are not NPCs.
    # Skeleton-authored canon (skeleton_origin=True) is exempt — authors are
    # responsible for naming their canonical NPCs distinctly from their PCs.
    if not skeleton_origin:
        for pc_name in get_bound_character_names(campaign_id):
            if names_overlap(canonical, pc_name):
                log(f"npc_upsert: refused PC contamination campaign={campaign_id} "
                    f"name='{canonical}' matches PC='{pc_name}'")
                return None

    ts = _now()
    conn = sqlite3.connect(DB_PATH)
    try:
        existing = conn.execute(
            "SELECT id, role, location_id, description, skeleton_origin, "
            "origin_excerpt FROM dnd_npcs "
            "WHERE campaign_id=? AND canonical_name=?",
            (campaign_id, canonical)
        ).fetchone()

        if existing is None:
            # Near-match diagnostic (S23): surface potential name fragments
            # before writing the new canonical row. Pure observability — does
            # NOT alter matching behavior or the strict-equality identity rule.
            _ex_rows = conn.execute(
                "SELECT canonical_name FROM dnd_npcs WHERE campaign_id=?",
                (campaign_id,)
            ).fetchall()
            for (_ex_name,) in _ex_rows:
                _d = levenshtein_distance(canonical, _ex_name)
                if _d <= 2:
                    log(f"npc_near_match: new='{canonical}' "
                        f"existing='{_ex_name}' distance={_d}")
                # Token-prefix diagnostic (S30 Ship 4): surface bare-name vs
                # full-name fragmentation (e.g. "Lira" + "Lira Songheart").
                # Levenshtein distance between these is high (>> 2) so
                # npc_near_match misses them. Pure observability — no merge.
                _tp_new = canonical.lower()
                _tp_ex = _ex_name.lower()
                if _tp_new != _tp_ex:
                    _tp_new_first = canonical.split()[0].lower()
                    _tp_ex_first = _ex_name.split()[0].lower()
                    if _tp_new == _tp_ex_first:
                        log(f"npc_token_prefix_match: campaign={campaign_id} "
                            f"new='{canonical}' existing='{_ex_name}' "
                            f"relation=prefix_to_full")
                    elif _tp_ex == _tp_new_first:
                        log(f"npc_token_prefix_match: campaign={campaign_id} "
                            f"new='{canonical}' existing='{_ex_name}' "
                            f"relation=full_to_prefix")

            cur = conn.execute(
                "INSERT INTO dnd_npcs "
                "(campaign_id, canonical_name, role, location_id, description, "
                " skeleton_origin, mention_count, origin_excerpt, "
                " first_mentioned, last_mentioned) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (campaign_id, canonical, role or '', location_id,
                 description or '', 1 if skeleton_origin else 0,
                 1, (origin_excerpt or '')[:100], ts, ts)
            )
            npc_id = cur.lastrowid
            conn.commit()
            log(f"npc_upsert: insert campaign={campaign_id} id={npc_id} "
                f"name='{canonical}' skeleton_origin={1 if skeleton_origin else 0}")
            return (npc_id, True)

        (npc_id, ex_role, ex_location_id, ex_description,
         ex_skeleton_origin, ex_origin_excerpt) = existing

        sets = []
        values = []

        if ex_skeleton_origin == 1 and not skeleton_origin:
            # Skeleton lock: parser hit on authored canon. Recency only.
            sets.append("mention_count = mention_count + 1")
            sets.append("last_mentioned = ?")
            values.append(ts)
        elif skeleton_origin and ex_skeleton_origin == 0:
            # Promotion: skeleton.md now claims this NPC. Authored fields win.
            sets.append("skeleton_origin = 1")
            if role:
                sets.append("role = ?"); values.append(role)
            if location_id is not None:
                sets.append("location_id = ?"); values.append(location_id)
            if description:
                sets.append("description = ?"); values.append(description)
            if origin_excerpt:
                sets.append("origin_excerpt = ?"); values.append(origin_excerpt[:100])
            log(f"npc_upsert: promote campaign={campaign_id} id={npc_id} "
                f"name='{canonical}' (parser→skeleton)")
        elif skeleton_origin and ex_skeleton_origin == 1:
            # Skeleton re-load. Update fields if provided. No mention bump.
            if role:
                if ex_role and ex_role != role:
                    log(f"npc_upsert: skeleton role change campaign={campaign_id} "
                        f"id={npc_id} '{ex_role}'→'{role}'")
                sets.append("role = ?"); values.append(role)
            if location_id is not None:
                sets.append("location_id = ?"); values.append(location_id)
            if description:
                sets.append("description = ?"); values.append(description)
            if origin_excerpt:
                sets.append("origin_excerpt = ?"); values.append(origin_excerpt[:100])
        else:
            # Parser × parser. Fill empties. Conflicts logged, existing kept.
            if role and not ex_role:
                sets.append("role = ?"); values.append(role)
            elif role and ex_role and role != ex_role:
                log(f"npc_upsert: conflict campaign={campaign_id} id={npc_id} "
                    f"role: existing='{ex_role}' new='{role}' (kept existing)")
            if location_id is not None and ex_location_id is None:
                sets.append("location_id = ?"); values.append(location_id)
            elif (location_id is not None and ex_location_id is not None
                  and location_id != ex_location_id):
                log(f"npc_upsert: conflict campaign={campaign_id} id={npc_id} "
                    f"location_id: existing={ex_location_id} new={location_id} (kept existing)")
            if description and not ex_description:
                sets.append("description = ?"); values.append(description)
            if origin_excerpt and not ex_origin_excerpt:
                sets.append("origin_excerpt = ?"); values.append(origin_excerpt[:100])
            sets.append("mention_count = mention_count + 1")
            sets.append("last_mentioned = ?")
            values.append(ts)

        if sets:
            values.extend([campaign_id, canonical])
            conn.execute(
                f"UPDATE dnd_npcs SET {', '.join(sets)} "
                f"WHERE campaign_id=? AND canonical_name=?",
                values
            )
            conn.commit()
        return (npc_id, False)
    finally:
        conn.close()


def npc_get(campaign_id: int, npc_id: int) -> dict | None:
    """Fetch a single NPC by row id, scoped to campaign."""
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute(
            f"SELECT {_NPC_COLS} FROM dnd_npcs WHERE id=? AND campaign_id=?",
            (npc_id, campaign_id)
        ).fetchone()
        return _npc_row_to_dict(row)
    finally:
        conn.close()


def npc_get_by_name(campaign_id: int, name: str) -> dict | None:
    """Fetch a single NPC by canonical name (input is canonicalized first)."""
    canonical = canonicalize_name(name)
    if not canonical:
        return None
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute(
            f"SELECT {_NPC_COLS} FROM dnd_npcs "
            f"WHERE campaign_id=? AND canonical_name=?",
            (campaign_id, canonical)
        ).fetchone()
        return _npc_row_to_dict(row)
    finally:
        conn.close()


def npc_list(campaign_id: int, location_id: int = None) -> list:
    """List all NPCs for a campaign, optionally filtered by location_id.
    Stable order: id ASC."""
    conn = sqlite3.connect(DB_PATH)
    try:
        if location_id is None:
            rows = conn.execute(
                f"SELECT {_NPC_COLS} FROM dnd_npcs "
                f"WHERE campaign_id=? ORDER BY id ASC",
                (campaign_id,)
            ).fetchall()
        else:
            rows = conn.execute(
                f"SELECT {_NPC_COLS} FROM dnd_npcs "
                f"WHERE campaign_id=? AND location_id=? ORDER BY id ASC",
                (campaign_id, location_id)
            ).fetchall()
        return [_npc_row_to_dict(r) for r in rows]
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────
# Track 6 #4 — NPC stat hydration helpers
# ─────────────────────────────────────────────────────────

def stat_incomplete(npc: dict) -> bool:
    """True if the NPC is missing the minimum viable combat stat trio.

    Gate is hp_max + ac + attack_bonus. Returns True if ANY is NULL.
    The explicit_hydrate path (/hydrate slash command) bypasses this check
    and writes unconditionally.
    """
    return any(npc.get(k) is None for k in ('hp_max', 'ac', 'attack_bonus'))


def npc_hydrate_stats(campaign_id: int,
                      name: str,
                      cr_str: str | None,
                      source: str) -> tuple[bool, dict]:
    """Hydrate stat fields on a dnd_npcs row.

    source: 'skeleton' | 'hook' | 'adhoc' | 'generic_fallback'
            | 'explicit_hydrate'

    Returns (wrote_anything: bool, signals: dict).

    Fill rule depends on source (§11.H lock):
    - Hook sources ('skeleton', 'hook', 'adhoc', 'generic_fallback'):
        idempotent NULL-fill. DM-authored values are preserved.
    - Explicit source ('explicit_hydrate'): always-overwrite. No NULL guard.

    For source='generic_fallback': NULL-fill, but hp_max excluded.
    For source='adhoc' or 'generic_fallback': creates a minimal dnd_npcs row
    first if none exists (both encounter brand-new NPCs from init-list events).
    Engine NEVER resolves cr_str=None for non-generic_fallback sources (§11.L).
    """
    signals: dict = {'source': source, 'cr': cr_str, 'stats_filled': 'none'}

    if source in ('adhoc', 'generic_fallback'):
        npc_upsert(campaign_id, name, skeleton_origin=False)

    npc = npc_get_by_name(campaign_id, name)
    if npc is None:
        signals['error'] = 'row_not_found'
        log(f"hydration: campaign={campaign_id} npc='{name}' source={source} "
            f"stats_filled=none cr={cr_str or 'none'} error=row_not_found")
        return (False, signals)

    if source != 'explicit_hydrate' and not stat_incomplete(npc):
        signals['source'] = 'miss'
        log(f"hydration: campaign={campaign_id} npc='{name}' source=miss "
            f"stats_filled=none cr={cr_str or 'none'} status_token=n/a")
        return (False, signals)

    if source == 'generic_fallback':
        stats = npc_hydrator.fallback_stats()
    else:
        stats = npc_hydrator.hydrate_npc_stats(cr_str)

    ts = _now()
    conn = sqlite3.connect(DB_PATH)
    try:
        npc_id = npc['id']
        filled_cols = []

        if source == 'explicit_hydrate':
            # Track which cols actually changed (for "no fields updated" UX).
            col_map = [
                ('hp_max',       'hp',   stats['hp_max']),
                ('ac',           'ac',   stats['ac']),
                ('attack_bonus', 'atk',  stats['attack_bonus']),
                ('damage_dice',  'dmg',  stats['damage_dice']),
                ('save_bonus',   'save', stats['save_bonus']),
                ('init_mod',     'init', stats['init_mod']),
            ]
            for col, short, val in col_map:
                if npc.get(col) != val:
                    filled_cols.append(short)
            conn.execute(
                "UPDATE dnd_npcs SET hp_max=?, ac=?, attack_bonus=?, "
                "damage_dice=?, save_bonus=?, init_mod=?, cr_str=?, last_mentioned=? "
                "WHERE id=?",
                (stats['hp_max'], stats['ac'], stats['attack_bonus'],
                 stats['damage_dice'], stats['save_bonus'], stats['init_mod'],
                 cr_str, ts, npc_id)
            )
        elif source == 'generic_fallback':
            # Write all stat cols EXCEPT hp_max (§1 decision 7). WHERE col IS NULL.
            for col, short, val in [
                ('ac',           'ac',   stats['ac']),
                ('attack_bonus', 'atk',  stats['attack_bonus']),
                ('damage_dice',  'dmg',  stats['damage_dice']),
                ('save_bonus',   'save', stats['save_bonus']),
                ('init_mod',     'init', stats['init_mod']),
            ]:
                r = conn.execute(
                    f"UPDATE dnd_npcs SET {col}=? WHERE id=? AND {col} IS NULL",
                    (val, npc_id)
                )
                if r.rowcount:
                    filled_cols.append(short)
            # Write cr_str if NULL (generic_fallback uses 1/4)
            conn.execute(
                "UPDATE dnd_npcs SET cr_str=? WHERE id=? AND cr_str IS NULL",
                (npc_hydrator._FALLBACK_CR, npc_id)
            )
        else:
            # Hook sources: NULL-fill all six stat cols
            for col, short, val in [
                ('hp_max',       'hp',   stats['hp_max']),
                ('ac',           'ac',   stats['ac']),
                ('attack_bonus', 'atk',  stats['attack_bonus']),
                ('damage_dice',  'dmg',  stats['damage_dice']),
                ('save_bonus',   'save', stats['save_bonus']),
                ('init_mod',     'init', stats['init_mod']),
            ]:
                r = conn.execute(
                    f"UPDATE dnd_npcs SET {col}=? WHERE id=? AND {col} IS NULL",
                    (val, npc_id)
                )
                if r.rowcount:
                    filled_cols.append(short)
            conn.execute(
                "UPDATE dnd_npcs SET cr_str=? WHERE id=? AND cr_str IS NULL",
                (cr_str, npc_id)
            )

        conn.commit()
    finally:
        conn.close()

    stats_filled_str = ','.join(filled_cols) if filled_cols else 'none'
    signals['stats_filled'] = stats_filled_str
    log(f"hydration: campaign={campaign_id} npc='{name}' source={source} "
        f"stats_filled={stats_filled_str} cr={cr_str or 'none'} status_token=n/a")
    if filled_cols:
        global _hydration_wrote_this_turn
        _hydration_wrote_this_turn = True
    return (bool(filled_cols), signals)


def npc_register_avrae_madd(campaign_id: int, name: str,
                             status_token: str = '<Healthy>') -> tuple[bool, dict]:
    """Register an !init madd creature in dnd_npcs without hydrating it.

    Creates a minimal dnd_npcs row (if none exists) with avrae_source='avrae_madd'.
    Leaves all stat columns NULL — Avrae owns the mechanics for these creatures.
    Returns (wrote_anything, signals). Idempotent.
    """
    npc_upsert(campaign_id, name, skeleton_origin=False)
    conn = sqlite3.connect(DB_PATH)
    wrote = False
    try:
        r = conn.execute(
            "UPDATE dnd_npcs SET avrae_source='avrae_madd' "
            "WHERE campaign_id=? AND canonical_name=? AND avrae_source IS NULL",
            (campaign_id, name)
        )
        if r.rowcount:
            wrote = True
        conn.commit()
    finally:
        conn.close()
    log(f"hydration: campaign={campaign_id} npc='{name}' source=avrae_madd "
        f"stats_filled=none cr=none status_token={status_token}")
    return (wrote, {'source': 'avrae_madd', 'stats_filled': 'none'})


def get_recently_active_npcs(campaign_id: int, limit: int = 6,
                              location_id: int = None) -> list:
    """Return up to `limit` NPCs ordered by most-recent `last_mentioned`.

    Used by build_dm_context to populate the "Recently active NPCs" prompt
    block (S3, Session 15). Replaces the legacy `dnd_scene_state.active_npcs`
    field which never had a deterministic writer.

    When `location_id` is provided, strict filter: only NPCs whose
    `location_id` matches. NPCs with NULL `location_id` are silent — the
    parser leaves location_id NULL by default for any NPC it can't ground,
    so an "include NULL" rule grows the always-present set with every
    fabricated NPC and re-injects them post-/travel (S25 live test).
    Default (None) preserves prior campaign-wide behavior — no filter.

    Empty list when the campaign has no NPCs yet — caller MUST omit the
    prompt section entirely rather than rendering a placeholder.
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        if location_id is None:
            rows = conn.execute(
                "SELECT canonical_name FROM dnd_npcs "
                "WHERE campaign_id=? "
                "ORDER BY last_mentioned DESC, id DESC "
                "LIMIT ?",
                (campaign_id, max(1, int(limit)))
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT canonical_name FROM dnd_npcs "
                "WHERE campaign_id=? AND location_id=? "
                "ORDER BY last_mentioned DESC, id DESC "
                "LIMIT ?",
                (campaign_id, int(location_id), max(1, int(limit)))
            ).fetchall()
        return [r[0] for r in rows if r and r[0]]
    finally:
        conn.close()


def get_recently_active_npc_ids(campaign_id: int, limit: int = 6) -> list:
    """Return up to `limit` NPC ids ordered by most-recent `last_mentioned`.

    Sibling of get_recently_active_npcs (which returns canonical names).
    Used by the consequence directive (Session 16) to assemble the in-scope
    npc set without a name→id round trip. Empty list when no NPCs exist.
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute(
            "SELECT id FROM dnd_npcs "
            "WHERE campaign_id=? "
            "ORDER BY last_mentioned DESC, id DESC "
            "LIMIT ?",
            (campaign_id, max(1, int(limit)))
        ).fetchall()
        return [int(r[0]) for r in rows if r and r[0] is not None]
    finally:
        conn.close()


def get_npc_ids_at_location(campaign_id: int, location_id) -> list:
    """Return NPC ids whose location_id matches. Empty list when location_id
    is None or no NPCs are placed there.

    Used by the consequence directive (Session 16) to extend the in-scope
    npc set with characters present at the current scene's location.
    """
    if location_id is None:
        return []
    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute(
            "SELECT id FROM dnd_npcs "
            "WHERE campaign_id=? AND location_id=?",
            (campaign_id, location_id)
        ).fetchall()
        return [int(r[0]) for r in rows if r and r[0] is not None]
    finally:
        conn.close()


def get_npc_names_at_location(campaign_id: int, location_id) -> list:
    """Return NPC canonical names whose location_id matches. Empty list
    when location_id is None or no NPCs are placed there.

    Sibling of get_npc_ids_at_location. Used by compute_commitment_directive
    (Session 19) to assemble target hints for the reaction-verb proximity
    check.
    """
    if location_id is None:
        return []
    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute(
            "SELECT canonical_name FROM dnd_npcs "
            "WHERE campaign_id=? AND location_id=?",
            (campaign_id, location_id)
        ).fetchall()
        return [r[0] for r in rows if r and r[0]]
    finally:
        conn.close()


def npc_set_aliases(campaign_id: int, npc_id: int, aliases: list) -> bool:
    """Replace the aliases list for an NPC. Returns True if a row was updated."""
    if not isinstance(aliases, list) or any(not isinstance(a, str) for a in aliases):
        log(f"npc_set_aliases: bad aliases payload, refused (campaign={campaign_id} id={npc_id})")
        return False
    payload = json.dumps(aliases)
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.execute(
            "UPDATE dnd_npcs SET aliases=? WHERE id=? AND campaign_id=?",
            (payload, npc_id, campaign_id)
        )
        updated = cur.rowcount > 0
        conn.commit()
        if updated:
            log(f"npc_set_aliases: campaign={campaign_id} id={npc_id} count={len(aliases)}")
        return updated
    finally:
        conn.close()


def npc_delete(campaign_id: int, npc_id: int) -> bool:
    """Permanently delete an NPC row. Returns True if a row was removed.
    Manual cleanup only — parsers and the skeleton loader never call this."""
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.execute(
            "DELETE FROM dnd_npcs WHERE id=? AND campaign_id=?",
            (npc_id, campaign_id)
        )
        removed = cur.rowcount > 0
        conn.commit()
        if removed:
            log(f"npc_delete: campaign={campaign_id} id={npc_id}")
        return removed
    finally:
        conn.close()


def _is_token_prefix(short_name: str, long_name: str) -> bool:
    """True if short_name is a whole-token prefix of long_name. Token boundary
    is required: 'Mira' is NOT a prefix of 'Miranda', but IS a prefix of
    'Mira Wells'. Equal-length names never qualify (no self-prefix)."""
    short_tokens = short_name.split()
    long_tokens = long_name.split()
    if len(short_tokens) >= len(long_tokens):
        return False
    return long_tokens[:len(short_tokens)] == short_tokens


def names_overlap(a: str, b: str) -> bool:
    # Symmetric same-identity check used to detect PC/NPC contamination.
    # True iff (after canonicalization) ANY of:
    #   - a == b
    #   - one is a whole-token prefix of the other ("Donovan" of "Donovan Ruby")
    #   - one is a single token that appears anywhere in the other's token list
    #     ("Ruby" matching "Donovan Ruby" — last-name address form)
    # Empty inputs return False. Two multi-token names that share only a first
    # name (e.g. "Donovan James" vs "Donovan Ruby") do NOT overlap — they are
    # treated as distinct identities.
    a_norm = canonicalize_name(a or '')
    b_norm = canonicalize_name(b or '')
    if not a_norm or not b_norm:
        return False
    if a_norm == b_norm:
        return True
    if _is_token_prefix(a_norm, b_norm) or _is_token_prefix(b_norm, a_norm):
        return True
    a_tokens = a_norm.split()
    b_tokens = b_norm.split()
    if len(a_tokens) == 1 and a_tokens[0] in b_tokens:
        return True
    if len(b_tokens) == 1 and b_tokens[0] in a_tokens:
        return True
    return False


def npc_fragmentation_report(campaign_id: int) -> dict:
    """Compute alias-fragmentation metrics for a campaign.

    Under strict literal matching (PHASE_12_SPEC §9.1), narration that
    introduces "Eldrin Stormbow" once and then re-mentions as "Eldrin"
    creates two rows for one person. This function reports the rate of
    that drift WITHOUT mutating anything — it's a measurement primitive,
    not a merge tool.

    A row is a "fragment" of another row if its canonical_name is a
    whole-token prefix of the other's canonical_name. See _is_token_prefix.

    Greedy clustering: longest-name rows become primaries first, shorter
    rows attach to the first primary they prefix.

    Returns:
      {
        'total_rows':         int,    # all rows for the campaign
        'distinct_entities':  int,    # cluster count (≤ total_rows)
        'fragment_rows':      int,    # rows attached to a longer primary
        'fragmentation_rate': float,  # fragment_rows / total_rows, or 0.0
        'clusters':           list[dict],  # multi-row clusters only:
            [{'primary':                 'Eldrin Stormbow',
              'fragments':               ['Eldrin'],
              'combined_mention_count':  N}, ...]
      }
    """
    rows = npc_list(campaign_id)
    if not rows:
        return {
            'total_rows':         0,
            'distinct_entities':  0,
            'fragment_rows':      0,
            'fragmentation_rate': 0.0,
            'clusters':           [],
        }

    # Longest first, then by name length (chars), then by id for stable ties.
    rows_sorted = sorted(
        rows,
        key=lambda r: (-len(r['canonical_name'].split()),
                       -len(r['canonical_name']),
                       r['id']),
    )

    # Greedy: each row joins the first existing cluster whose primary it
    # prefixes; otherwise it starts its own cluster.
    clusters = []
    for row in rows_sorted:
        attached = False
        for cluster in clusters:
            primary_name = cluster['primary']['canonical_name']
            if _is_token_prefix(row['canonical_name'], primary_name):
                cluster['fragments'].append(row)
                attached = True
                break
        if not attached:
            clusters.append({'primary': row, 'fragments': []})

    fragment_rows = sum(len(c['fragments']) for c in clusters)
    multi = [c for c in clusters if c['fragments']]
    return {
        'total_rows':         len(rows),
        'distinct_entities':  len(clusters),
        'fragment_rows':      fragment_rows,
        'fragmentation_rate': fragment_rows / len(rows),
        'clusters': [
            {
                'primary':                c['primary']['canonical_name'],
                'fragments':              [f['canonical_name'] for f in c['fragments']],
                'combined_mention_count': c['primary']['mention_count'] +
                                          sum(f['mention_count'] for f in c['fragments']),
            }
            for c in multi
        ],
    }


# ─── Persistent Locations (Phase 12B) ─────────────────────────────────────────
# Canonical world geography. Authoritative — the table answers "what places
# exist in this world." Hierarchical via parent_location_id (self-FK).
#
# Hard rules (PHASE_12_SPEC §4, §6, §9.1, §9.9):
#   - location_upsert() is the ONLY write path for the locations table.
#     set_current_location() is the ONLY writer of dnd_scene_state.
#     current_location_id (§9.9 single mutation path).
#   - Identity is canonicalize_location_name(): strict literal AFTER
#     deterministic normalization (whitespace, quotes, leading article).
#   - skeleton_origin=1 rows are authored canon. Parser hits NEVER overwrite
#     authored fields — they bump mention_count + last_mentioned only.
#   - Auto-promotion (parser→skeleton) does NOT happen. Only an explicit
#     skeleton_origin=True call (the skeleton loader, 12C.2) sets the flag.
#   - set_current_location validates campaign-scoped FK existence before
#     writing. None is a valid value (clears current location for wilderness /
#     transitional scenes / invalidated locations). See §9.9.

# Articles to strip from the head of canonical location names. Whole-token
# match against a leading token, case-insensitive. "The Rusty Anchor" →
# "Rusty Anchor". "Theramore" stays "Theramore" (article must be a separate
# whitespace-separated token). Keep it purely syntactic.
_LEADING_ARTICLES = frozenset({"the", "a", "an"})


def canonicalize_location_name(s: str) -> str:
    """Normalize a location name for canonical lookup. PURE normalization:
      - strip leading/trailing whitespace
      - collapse internal whitespace runs to single space
      - normalize curly quotes/apostrophes to ASCII
      - strip leading article ("the", "a", "an") case-insensitively, but
        ONLY if it is a separate token followed by more tokens
      - PRESERVE capitalization on all surviving tokens

    See PHASE_12_SPEC §9.1 + Session 12 review. Leading-article stripping is
    the same family of rule as honorific stripping for NPCs: deterministic
    identity normalization, not fuzzy match. "Rusty Anchor" survives both
    "The Rusty Anchor" and "Rusty Anchor" inputs as one canonical row.
    """
    if not s:
        return ''
    # Curly → ASCII
    s = s.replace('\u2018', "'").replace('\u2019', "'")
    s = s.replace('\u201C', '"').replace('\u201D', '"')
    # Strip + collapse whitespace
    s = ' '.join(s.split())
    # Strip leading article (token + space + more tokens). NEVER strips the
    # last remaining token, so a bare "The" stays "The" (then fails validation
    # at the parser layer). "Theramore" stays "Theramore" because the article
    # must be a whitespace-separated token.
    parts = s.split()
    while len(parts) > 1 and parts[0].lower() in _LEADING_ARTICLES:
        parts = parts[1:]
    return ' '.join(parts)


def _location_row_to_dict(row) -> dict:
    """Convert a SELECT * row to a dict. Parses aliases JSON back to list."""
    if row is None:
        return None
    try:
        aliases = json.loads(row[3]) if row[3] else []
        if not isinstance(aliases, list):
            aliases = []
    except (json.JSONDecodeError, TypeError):
        aliases = []
    return {
        'id':                  row[0],
        'campaign_id':         row[1],
        'canonical_name':      row[2],
        'aliases':             aliases,
        'type':                row[4],
        'parent_location_id':  row[5],
        'description':         row[6],
        'skeleton_origin':     row[7],
        'mention_count':       row[8],
        'origin_excerpt':      row[9],
        'first_mentioned':     row[10],
        'last_mentioned':      row[11],
    }


_LOCATION_COLS = ("id, campaign_id, canonical_name, aliases, type, "
                  "parent_location_id, description, skeleton_origin, "
                  "mention_count, origin_excerpt, first_mentioned, last_mentioned")


def location_upsert(campaign_id: int, name: str, type: str = '',
                    parent_location_id: int = None, description: str = '',
                    origin_excerpt: str = '',
                    skeleton_origin: bool = False) -> int | None:
    """Insert or update a location by (campaign_id, canonicalize_location_name(name)).
    Returns the row id, or None on an empty/invalid name.

    Behaviour matrix (existing × incoming):
      - missing × any         → INSERT, mention_count=1
      - skeleton × parser     → bump mention_count + last_mentioned ONLY
                                (authored fields locked, §4)
      - parser × skeleton     → promote to skeleton_origin=1, authored fields win
      - skeleton × skeleton   → re-load: update fields, no mention bump
      - parser × parser       → fill empty fields, bump mention_count + ts;
                                non-empty conflicts log and keep existing

    parent_location_id is treated like a normal field — fillable if empty,
    locked once the row is skeleton_origin=1. The caller is responsible for
    passing a valid FK (parent must exist in the same campaign); this layer
    does not enforce that beyond storage.
    """
    canonical = canonicalize_location_name(name)
    if not canonical:
        log(f"location_upsert: empty canonical name for campaign={campaign_id}, refused")
        return None

    ts = _now()
    conn = sqlite3.connect(DB_PATH)
    try:
        existing = conn.execute(
            "SELECT id, type, parent_location_id, description, skeleton_origin, "
            "origin_excerpt FROM dnd_locations "
            "WHERE campaign_id=? AND canonical_name=?",
            (campaign_id, canonical)
        ).fetchone()

        if existing is None:
            # Near-match diagnostic (S23): same shape as npc_upsert near-match.
            # Pure observability — does NOT alter the strict-equality identity rule.
            _ex_rows = conn.execute(
                "SELECT canonical_name FROM dnd_locations WHERE campaign_id=?",
                (campaign_id,)
            ).fetchall()
            for (_ex_name,) in _ex_rows:
                _d = levenshtein_distance(canonical, _ex_name)
                if _d <= 2:
                    log(f"location_near_match: new='{canonical}' "
                        f"existing='{_ex_name}' distance={_d}")

            cur = conn.execute(
                "INSERT INTO dnd_locations "
                "(campaign_id, canonical_name, type, parent_location_id, "
                " description, skeleton_origin, mention_count, origin_excerpt, "
                " first_mentioned, last_mentioned) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (campaign_id, canonical, type or '', parent_location_id,
                 description or '', 1 if skeleton_origin else 0,
                 1, (origin_excerpt or '')[:100], ts, ts)
            )
            loc_id = cur.lastrowid
            conn.commit()
            log(f"location_upsert: insert campaign={campaign_id} id={loc_id} "
                f"name='{canonical}' skeleton_origin={1 if skeleton_origin else 0}")
            return loc_id

        (loc_id, ex_type, ex_parent, ex_description,
         ex_skeleton_origin, ex_origin_excerpt) = existing

        sets = []
        values = []

        if ex_skeleton_origin == 1 and not skeleton_origin:
            # Skeleton lock: parser hit on authored canon. Recency only.
            sets.append("mention_count = mention_count + 1")
            sets.append("last_mentioned = ?")
            values.append(ts)
        elif skeleton_origin and ex_skeleton_origin == 0:
            # Promotion: skeleton.md now claims this location. Authored wins.
            sets.append("skeleton_origin = 1")
            if type:
                sets.append("type = ?"); values.append(type)
            if parent_location_id is not None:
                sets.append("parent_location_id = ?"); values.append(parent_location_id)
            if description:
                sets.append("description = ?"); values.append(description)
            if origin_excerpt:
                sets.append("origin_excerpt = ?"); values.append(origin_excerpt[:100])
            log(f"location_upsert: promote campaign={campaign_id} id={loc_id} "
                f"name='{canonical}' (parser→skeleton)")
        elif skeleton_origin and ex_skeleton_origin == 1:
            # Skeleton re-load. Fields update if provided. No mention bump.
            if type:
                if ex_type and ex_type != type:
                    log(f"location_upsert: skeleton type change campaign={campaign_id} "
                        f"id={loc_id} '{ex_type}'→'{type}'")
                sets.append("type = ?"); values.append(type)
            if parent_location_id is not None:
                sets.append("parent_location_id = ?"); values.append(parent_location_id)
            if description:
                sets.append("description = ?"); values.append(description)
            if origin_excerpt:
                sets.append("origin_excerpt = ?"); values.append(origin_excerpt[:100])
        else:
            # Parser × parser. Fill empties. Conflicts logged, existing kept.
            if type and not ex_type:
                sets.append("type = ?"); values.append(type)
            elif type and ex_type and type != ex_type:
                log(f"location_upsert: conflict campaign={campaign_id} id={loc_id} "
                    f"type: existing='{ex_type}' new='{type}' (kept existing)")
            if parent_location_id is not None and ex_parent is None:
                sets.append("parent_location_id = ?"); values.append(parent_location_id)
            elif (parent_location_id is not None and ex_parent is not None
                  and parent_location_id != ex_parent):
                log(f"location_upsert: conflict campaign={campaign_id} id={loc_id} "
                    f"parent_location_id: existing={ex_parent} new={parent_location_id} "
                    f"(kept existing)")
            if description and not ex_description:
                sets.append("description = ?"); values.append(description)
            if origin_excerpt and not ex_origin_excerpt:
                sets.append("origin_excerpt = ?"); values.append(origin_excerpt[:100])
            sets.append("mention_count = mention_count + 1")
            sets.append("last_mentioned = ?")
            values.append(ts)

        if sets:
            values.extend([campaign_id, canonical])
            conn.execute(
                f"UPDATE dnd_locations SET {', '.join(sets)} "
                f"WHERE campaign_id=? AND canonical_name=?",
                values
            )
            conn.commit()
        return loc_id
    finally:
        conn.close()


def location_get(campaign_id: int, location_id: int) -> dict | None:
    """Fetch a single location by row id, scoped to campaign."""
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute(
            f"SELECT {_LOCATION_COLS} FROM dnd_locations "
            f"WHERE id=? AND campaign_id=?",
            (location_id, campaign_id)
        ).fetchone()
        return _location_row_to_dict(row)
    finally:
        conn.close()


def location_get_by_name(campaign_id: int, name: str) -> dict | None:
    """Fetch a single location by canonical name (input is canonicalized first)."""
    canonical = canonicalize_location_name(name)
    if not canonical:
        return None
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute(
            f"SELECT {_LOCATION_COLS} FROM dnd_locations "
            f"WHERE campaign_id=? AND canonical_name=?",
            (campaign_id, canonical)
        ).fetchone()
        return _location_row_to_dict(row)
    finally:
        conn.close()


def location_list(campaign_id: int, parent_location_id: int = None) -> list:
    """List locations for a campaign. If parent_location_id is provided,
    return only direct children of that parent. Stable order: id ASC."""
    conn = sqlite3.connect(DB_PATH)
    try:
        if parent_location_id is None:
            rows = conn.execute(
                f"SELECT {_LOCATION_COLS} FROM dnd_locations "
                f"WHERE campaign_id=? ORDER BY id ASC",
                (campaign_id,)
            ).fetchall()
        else:
            rows = conn.execute(
                f"SELECT {_LOCATION_COLS} FROM dnd_locations "
                f"WHERE campaign_id=? AND parent_location_id=? ORDER BY id ASC",
                (campaign_id, parent_location_id)
            ).fetchall()
        return [_location_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def location_set_aliases(campaign_id: int, location_id: int,
                         aliases: list) -> bool:
    """Replace the aliases list for a location. Returns True if a row was updated."""
    if not isinstance(aliases, list) or any(not isinstance(a, str) for a in aliases):
        log(f"location_set_aliases: bad aliases payload, refused "
            f"(campaign={campaign_id} id={location_id})")
        return False
    payload = json.dumps(aliases)
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.execute(
            "UPDATE dnd_locations SET aliases=? WHERE id=? AND campaign_id=?",
            (payload, location_id, campaign_id)
        )
        updated = cur.rowcount > 0
        conn.commit()
        if updated:
            log(f"location_set_aliases: campaign={campaign_id} id={location_id} "
                f"count={len(aliases)}")
        return updated
    finally:
        conn.close()


def location_delete(campaign_id: int, location_id: int) -> bool:
    """Permanently delete a location row. Returns True if a row was removed.
    Manual cleanup only — parsers and the skeleton loader never call this.

    Cleanup behavior (referential integrity, keep deterministic):
      - Any direct children pointing to this row via parent_location_id are
        re-parented to NULL (orphaned, not deleted — they may still be valid
        places, just no longer parented).
      - Any NPCs with location_id pointing here are likewise re-parented to
        NULL.
      - If dnd_scene_state.current_location_id == this row, it is cleared
        to NULL (engine no longer thinks party is in a non-existent place).
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        # First check the row exists in this campaign — otherwise the
        # cascading clears can't safely fire.
        existed = conn.execute(
            "SELECT 1 FROM dnd_locations WHERE id=? AND campaign_id=?",
            (location_id, campaign_id)
        ).fetchone() is not None
        if not existed:
            return False
        # Clear inbound FKs first.
        conn.execute(
            "UPDATE dnd_locations SET parent_location_id=NULL "
            "WHERE campaign_id=? AND parent_location_id=?",
            (campaign_id, location_id)
        )
        conn.execute(
            "UPDATE dnd_npcs SET location_id=NULL "
            "WHERE campaign_id=? AND location_id=?",
            (campaign_id, location_id)
        )
        conn.execute(
            "UPDATE dnd_scene_state SET current_location_id=NULL "
            "WHERE campaign_id=? AND current_location_id=?",
            (campaign_id, location_id)
        )
        conn.execute(
            "DELETE FROM dnd_locations WHERE id=? AND campaign_id=?",
            (location_id, campaign_id)
        )
        conn.commit()
        log(f"location_delete: campaign={campaign_id} id={location_id} "
            f"(inbound FKs cleared)")
        return True
    finally:
        conn.close()


def set_current_location(campaign_id: int, location_id) -> bool:
    """Set the party's current location. SINGLE WRITE PATH per §9.9.

    Callers: /travel command, scene-transition detector, skeleton loader.
    Returns True on successful write, False if the FK is invalid for this
    campaign or scene_state is missing.

    location_id semantics:
      - integer → must reference an existing dnd_locations.id in this campaign
      - None    → clear current location ("between locations" / wilderness /
                  invalidated). Always permitted.

    Refuses cross-campaign and stale IDs at the engine boundary. Spec §9.9
    rationale: this is authoritative cross-system state — the engine defends
    its own invariants rather than trusting callers.
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        if location_id is not None:
            ok = conn.execute(
                "SELECT 1 FROM dnd_locations WHERE id=? AND campaign_id=?",
                (location_id, campaign_id)
            ).fetchone() is not None
            if not ok:
                log(f"set_current_location: refused — location_id={location_id} "
                    f"not found in campaign={campaign_id}")
                return False

        cur = conn.execute(
            "UPDATE dnd_scene_state SET current_location_id=?, updated_at=? "
            "WHERE campaign_id=?",
            (location_id, _now(), campaign_id)
        )
        if cur.rowcount == 0:
            log(f"set_current_location: refused — no scene_state row for "
                f"campaign={campaign_id}")
            return False
        conn.commit()
        log(f"set_current_location: campaign={campaign_id} "
            f"current_location_id={location_id}")
        return True
    finally:
        conn.close()


def get_current_location(campaign_id: int) -> dict | None:
    """Return the location dict for the party's current location, or None
    if unset / invalid / scene_state missing. Convenience reader."""
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute(
            "SELECT current_location_id FROM dnd_scene_state WHERE campaign_id=?",
            (campaign_id,)
        ).fetchone()
        if row is None or row[0] is None:
            return None
        location_id = row[0]
    finally:
        conn.close()
    return location_get(campaign_id, location_id)


def phantom_location_candidates(campaign_id: int, threshold: int = 3) -> dict:
    """Surface parser-origin locations that look like potential phantoms.

    A "phantom" is a row written by the location extractor that doesn't
    correspond to durable world geography — e.g. a typo ("Stormbridge"
    for "Stonebridge"), one-off scenery treated as a place, or a transient
    reference the LLM never returned to. This function is telemetry only:
    it does NOT delete, merge, or mutate anything. The LLM proposes; the
    validator disposes; the human distinguishes phantom from emergent.

    Candidate definition (all three must hold):
      - skeleton_origin = 0   (parser-origin only; authored canon never flags)
      - mention_count   = 1   (still a hapax — never re-referenced)
      - turns_since_first_mention >= threshold

    Turn proxy (no per-campaign turn counter on the schema today):
      Count of OTHER dnd_locations rows in the same campaign whose
      last_mentioned > this row's first_mentioned. Each row is one
      distinct location (the table is one-row-per-location with
      last_mentioned updated in place on re-mention), so this counts
      breadth of new geography mentioned since the candidate appeared,
      not chattiness on already-known places. A heavily re-mentioned
      town counts as ONE other location, not many.

    Phantom vs emergent indistinguishability is intentional:
      "Stormbridge" (typo) and "River Wynd" (real geography) both have
      skeleton_origin=0, mention_count=1. The metric surfaces both as
      candidates by design — separating them requires human judgment
      that no SQL query can supply. Tuning the threshold higher trades
      false positives on slow-emerging real geography for slower
      phantom detection.

    Returns:
      {
        'threshold':  int,
        'count':      int,
        'candidates': [
            {'id':              int,
             'name':             str,
             'first_mentioned':  str,
             'turns_since':      int}, ...
        ],   # sorted by id ascending
      }
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute(
            "SELECT id, canonical_name, first_mentioned, turns_since FROM ("
            " SELECT c.id, c.canonical_name, c.first_mentioned, "
            "        (SELECT COUNT(*) FROM dnd_locations o "
            "         WHERE o.campaign_id = c.campaign_id "
            "           AND o.id != c.id "
            "           AND o.last_mentioned > c.first_mentioned) AS turns_since "
            " FROM dnd_locations c "
            " WHERE c.campaign_id = ? "
            "   AND c.skeleton_origin = 0 "
            "   AND c.mention_count = 1"
            ") WHERE turns_since >= ? ORDER BY id",
            (campaign_id, threshold)
        ).fetchall()
    finally:
        conn.close()
    return {
        'threshold':  threshold,
        'count':      len(rows),
        'candidates': [
            {'id':              r[0],
             'name':            r[1],
             'first_mentioned': r[2],
             'turns_since':     r[3]}
            for r in rows
        ],
    }


def world_health_report(campaign_id: int, phantom_threshold: int = 3) -> dict:
    """Aggregate canonical-world-state health metrics for a campaign.

    Composes existing telemetry primitives — npc_fragmentation_report()
    and phantom_location_candidates() — with a small skeleton-coverage
    count, into a single greppable line. Pure read, no mutations.

    Deliberately NOT a composite "score." Weighting NPC fragmentation
    against location skeleton coverage against phantom count is
    unjustified speculation, and a single number hides the underlying
    signal. The aggregate surfaces all four numbers; the human reads
    them as components, not as a verdict.

    Component sources:
      - NPC fragmentation: npc_fragmentation_report() (Phase 12A telemetry).
      - Location skeleton coverage: skeleton_origin=1 rows / total rows.
        High coverage means most known geography is authored canon;
        low coverage means the parser is doing most of the work.
      - Phantom locations: phantom_location_candidates() count at
        the given threshold. See that function's docstring for the
        candidate definition and turn-proxy reasoning.

    Returns:
      {
        'campaign_id':            int,
        'npc_total':              int,    # total NPC rows
        'npc_distinct':           int,    # cluster count after fragmentation analysis
        'npc_fragmentation_rate': float,  # 0.0–1.0
        'loc_total':              int,    # total location rows
        'loc_skeleton':           int,    # skeleton_origin=1 row count
        'loc_skeleton_coverage':  float,  # skeleton / total, or 0.0 when total=0
        'loc_phantoms':           int,    # phantom_location_candidates count
        'phantom_threshold':      int,    # echoed for log clarity
      }
    """
    npc = npc_fragmentation_report(campaign_id)
    phantoms = phantom_location_candidates(campaign_id, threshold=phantom_threshold)

    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute(
            "SELECT COUNT(*), "
            "       COALESCE(SUM(CASE WHEN skeleton_origin=1 THEN 1 ELSE 0 END), 0) "
            "FROM dnd_locations WHERE campaign_id=?",
            (campaign_id,)
        ).fetchone()
    finally:
        conn.close()
    loc_total    = row[0] or 0
    loc_skeleton = row[1] or 0
    loc_coverage = (loc_skeleton / loc_total) if loc_total else 0.0

    cons = consequence_health_report(campaign_id)
    return {
        'campaign_id':            campaign_id,
        'npc_total':              npc['total_rows'],
        'npc_distinct':           npc['distinct_entities'],
        'npc_fragmentation_rate': npc['fragmentation_rate'],
        'loc_total':              loc_total,
        'loc_skeleton':           loc_skeleton,
        'loc_skeleton_coverage':  loc_coverage,
        'loc_phantoms':           phantoms['count'],
        'phantom_threshold':      phantom_threshold,
        # Session 16: consequence layer telemetry composed into the aggregate.
        'cons_active':            cons['active'],
        'cons_promoted':          cons['promoted'],
        'cons_never_surfaced':    cons['never_surfaced'],
    }


def consequence_health_report(campaign_id: int) -> dict:
    """Aggregate consequence-layer health metrics for a campaign.

    Pure read; no mutations. Used by world_health_report and as a
    standalone telemetry primitive for the consequence parser tuning
    pass (Session 16).

    Returns:
      {
        'campaign_id':     int,
        'active':          int,    # status='active' row count
        'promoted':        int,    # status='promoted' row count
        'never_surfaced':  int,    # active rows with surface_count=0
        'by_kind':         dict,   # {kind: count} for ACTIVE rows
        'by_source':       dict,   # {sources_str: count} for ACTIVE rows
      }
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        active_rows = conn.execute(
            "SELECT kind, sources, surface_count FROM dnd_consequences "
            "WHERE campaign_id=? AND status='active'",
            (campaign_id,)
        ).fetchall()
        promoted_count = conn.execute(
            "SELECT COUNT(*) FROM dnd_consequences "
            "WHERE campaign_id=? AND status='promoted'",
            (campaign_id,)
        ).fetchone()[0]
    finally:
        conn.close()

    by_kind = {}
    by_source = {}
    never_surfaced = 0
    for kind, sources, surf_count in active_rows:
        by_kind[kind] = by_kind.get(kind, 0) + 1
        by_source[sources] = by_source.get(sources, 0) + 1
        if (surf_count or 0) == 0:
            never_surfaced += 1

    return {
        'campaign_id':    campaign_id,
        'active':         len(active_rows),
        'promoted':       int(promoted_count or 0),
        'never_surfaced': never_surfaced,
        'by_kind':        by_kind,
        'by_source':      by_source,
    }


# ─────────────────────────────────────────────────────────────────────
# Consequence ledger (Session 16)
# ─────────────────────────────────────────────────────────────────────
# See CONSEQUENCE_SURFACING_SPEC.md. NPCs the player wronged (or showed
# mercy to, or made promises to) carry that weight forward across turns
# via this table. Captured by the dual-pass advisory parser
# (consequence_extractor.py); surfaced by the directive layer
# (orch.compute_consequence_directive); graduated into NPC notable_traits
# by maybe_promote_consequences once thresholds are met.
#
# Single write paths:
#   - consequence_upsert        — capture (insert or last-write-wins update)
#   - consequence_emit_surface  — directive emit (counters)
#   - maybe_promote_consequences — graduation to notable_traits
# No other code path mutates dnd_consequences.

CONSEQUENCE_KINDS = frozenset({
    'threat', 'mercy', 'cruelty', 'betrayal', 'promise', 'alliance',
})

CONSEQUENCE_SEVERITIES = frozenset({1, 2, 3})

CONSEQUENCE_SUMMARY_MAX = 120

CONSEQUENCE_SOURCES = frozenset({'player', 'dm'})

# Promotion thresholds (CONSEQUENCE_SURFACING_SPEC §1.7, §7.1).
# All three AND-ed. Tunable from log emissions; v1 calibration is
# intuition-based same as pacing tier thresholds.
PROMOTION_SURFACE_COUNT = 3
PROMOTION_DISTINCT_TURNS = 2
PROMOTION_AGE_TURNS = 10

# Directive cap on simultaneous emits (§1.6, §6.3).
CONSEQUENCE_DIRECTIVE_CAP = 3


def _consequence_row_to_dict(row) -> dict:
    """Adapter: dnd_consequences row tuple → dict with all fields named."""
    return {
        'id':                     row[0],
        'campaign_id':            row[1],
        'npc_id':                 row[2],
        'kind':                   row[3],
        'summary':                row[4],
        'severity':               row[5],
        'sources':                row[6],
        'captured_at':            row[7],
        'captured_turn':          row[8],
        'first_seen_turn':        row[9],
        'last_seen_turn':         row[10],
        'last_surfaced_at':       row[11],
        'last_surfaced_turn':     row[12],
        'surface_count':          row[13],
        'distinct_surface_turns': row[14],
        'status':                 row[15],
        'promoted_at':            row[16],
    }


_CONSEQUENCE_COLS = (
    "c.id, c.campaign_id, c.npc_id, c.kind, c.summary, c.severity, "
    "c.sources, c.captured_at, c.captured_turn, c.first_seen_turn, "
    "c.last_seen_turn, c.last_surfaced_at, c.last_surfaced_turn, "
    "c.surface_count, c.distinct_surface_turns, c.status, c.promoted_at"
)


def get_turn_counter(campaign_id: int) -> int:
    """Return the campaign's monotonic turn counter, or 0 if no scene state."""
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute(
            "SELECT turn_counter FROM dnd_scene_state WHERE campaign_id=?",
            (campaign_id,)
        ).fetchone()
    finally:
        conn.close()
    return int(row[0]) if row and row[0] is not None else 0


def increment_turn_counter(campaign_id: int) -> int:
    """Advance the campaign's turn counter by 1. Returns the new value.

    If no dnd_scene_state row exists yet, creates one at turn=1. The
    increment is atomic per-call. Single writer is _dm_respond_and_post
    (or dm_respond's tail) — do not call from extraction threads.
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        with conn:
            existing = conn.execute(
                "SELECT turn_counter FROM dnd_scene_state WHERE campaign_id=?",
                (campaign_id,)
            ).fetchone()
            if existing is None:
                # Initialize scene_state row with turn_counter=1.
                now_iso = _now()
                conn.execute(
                    "INSERT INTO dnd_scene_state "
                    "(campaign_id, turn_counter, updated_at) VALUES (?, 1, ?)",
                    (campaign_id, now_iso)
                )
                return 1
            new_val = int(existing[0] or 0) + 1
            conn.execute(
                "UPDATE dnd_scene_state SET turn_counter=? WHERE campaign_id=?",
                (new_val, campaign_id)
            )
            return new_val
    finally:
        conn.close()


def _merge_sources(existing: str, new_source: str) -> str:
    """Add new_source to existing comma-list if absent. Returns sorted comma-list."""
    parts = set(s.strip() for s in (existing or '').split(',') if s.strip())
    parts.add(new_source)
    return ','.join(sorted(parts))


def consequence_upsert(campaign_id: int, npc_id: int, kind: str,
                       summary: str, severity: int, source: str,
                       current_turn: int) -> dict:
    """Single write path for consequence captures.

    Returns a dict: {
      'status':       'inserted' | 'updated' | 'rejected_promoted' | 'rejected_invalid',
      'id':           int | None,
      'reason':       str | None,
    }

    Last-write-wins per (campaign_id, npc_id, kind) for active rows.
    Promoted rows reject re-capture (logged, no write). Severity uses
    MAX semantics on update; sources accumulates the new channel.
    first_seen_turn is immutable after insert.

    Validation enforced HERE (defense-in-depth — apply_consequence_proposals
    also validates earlier):
      - kind must be in CONSEQUENCE_KINDS
      - severity must be in {1, 2, 3}
      - source must be in {'player', 'dm'}
      - summary must be non-empty after strip and ≤ CONSEQUENCE_SUMMARY_MAX
      - npc_id must reference an existing dnd_npcs row in this campaign
    """
    if kind not in CONSEQUENCE_KINDS:
        return {'status': 'rejected_invalid', 'id': None,
                'reason': f'invalid_kind:{kind}'}
    if severity not in CONSEQUENCE_SEVERITIES:
        return {'status': 'rejected_invalid', 'id': None,
                'reason': f'severity_out_of_range:{severity}'}
    if source not in CONSEQUENCE_SOURCES:
        return {'status': 'rejected_invalid', 'id': None,
                'reason': f'invalid_source:{source}'}
    s = (summary or '').strip()
    if not s:
        return {'status': 'rejected_invalid', 'id': None, 'reason': 'summary_empty'}
    if len(s) > CONSEQUENCE_SUMMARY_MAX:
        return {'status': 'rejected_invalid', 'id': None,
                'reason': f'summary_too_long:{len(s)}'}

    conn = sqlite3.connect(DB_PATH)
    try:
        with conn:
            npc_check = conn.execute(
                "SELECT 1 FROM dnd_npcs WHERE id=? AND campaign_id=?",
                (npc_id, campaign_id)
            ).fetchone()
            if not npc_check:
                return {'status': 'rejected_invalid', 'id': None,
                        'reason': 'npc_not_found'}

            existing = conn.execute(
                "SELECT id, severity, sources, status, last_surfaced_turn "
                "FROM dnd_consequences "
                "WHERE campaign_id=? AND npc_id=? AND kind=?",
                (campaign_id, npc_id, kind)
            ).fetchone()

            now_iso = _now()
            if existing is None:
                conn.execute(
                    "INSERT INTO dnd_consequences "
                    "(campaign_id, npc_id, kind, summary, severity, sources, "
                    " captured_at, captured_turn, first_seen_turn, "
                    " last_seen_turn, surface_count, distinct_surface_turns, "
                    " status) VALUES "
                    "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 'active')",
                    (campaign_id, npc_id, kind, s, severity, source,
                     now_iso, current_turn, current_turn, current_turn)
                )
                new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                return {'status': 'inserted', 'id': new_id, 'reason': None}

            ex_id, ex_sev, ex_sources, ex_status, ex_lst_turn = existing
            if ex_status == 'promoted':
                return {'status': 'rejected_promoted', 'id': ex_id,
                        'reason': 'already_promoted'}

            new_severity = max(int(ex_sev or 1), severity)
            new_sources = _merge_sources(ex_sources, source)
            last_seen = max(current_turn, int(ex_lst_turn or 0))
            conn.execute(
                "UPDATE dnd_consequences SET "
                "summary=?, severity=?, sources=?, captured_at=?, "
                "captured_turn=?, last_seen_turn=? "
                "WHERE id=?",
                (s, new_severity, new_sources, now_iso,
                 current_turn, last_seen, ex_id)
            )
            return {'status': 'updated', 'id': ex_id, 'reason': None}
    finally:
        conn.close()


def get_active_consequences(campaign_id: int,
                             npc_ids: list = None) -> list:
    """Return active consequences for the campaign, optionally filtered to npc_ids.

    LEFT JOINs dnd_npcs and skips rows whose NPC has been deleted (defensive
    against orphan rows even though there's no explicit cascade in v1).

    Returns a list of dicts in _consequence_row_to_dict shape, plus a
    'canonical_name' field joined from dnd_npcs.
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        params = [campaign_id]
        sql = (
            f"SELECT {_CONSEQUENCE_COLS}, n.canonical_name "
            "FROM dnd_consequences c "
            "INNER JOIN dnd_npcs n ON n.id = c.npc_id "
            "WHERE c.campaign_id=? AND c.status='active'"
        )
        if npc_ids:
            placeholders = ','.join('?' * len(npc_ids))
            sql += f" AND c.npc_id IN ({placeholders})"
            params.extend(npc_ids)
        sql += " ORDER BY c.severity DESC, c.last_surfaced_turn DESC NULLS LAST, c.id ASC"
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()

    out = []
    for row in rows:
        d = _consequence_row_to_dict(row[:17])
        d['canonical_name'] = row[17]
        out.append(d)
    return out


def consequence_emit_surface(consequence_id: int, current_turn: int) -> bool:
    """Record a surfacing emit on the given consequence. Returns True if
    the row was updated (active, exists), False otherwise.

    Called by the directive layer when a consequence appears in the
    composed prompt block. Increments surface_count, advances
    last_surfaced_at/last_surfaced_turn, advances last_seen_turn, and
    increments distinct_surface_turns ONLY when current_turn differs from
    the previous last_surfaced_turn.

    Single write path for surfacing telemetry.
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        with conn:
            row = conn.execute(
                "SELECT last_surfaced_turn, surface_count, "
                "distinct_surface_turns, captured_turn, status "
                "FROM dnd_consequences WHERE id=?",
                (consequence_id,)
            ).fetchone()
            if not row:
                return False
            prev_turn, surf_count, distinct_turns, captured_turn, status = row
            if status != 'active':
                return False

            now_iso = _now()
            new_surf_count = int(surf_count or 0) + 1
            if prev_turn is None or int(prev_turn) != int(current_turn):
                new_distinct = int(distinct_turns or 0) + 1
            else:
                new_distinct = int(distinct_turns or 0)
            new_last_seen = max(int(captured_turn or 0), int(current_turn))

            conn.execute(
                "UPDATE dnd_consequences SET "
                "last_surfaced_at=?, last_surfaced_turn=?, "
                "surface_count=?, distinct_surface_turns=?, "
                "last_seen_turn=? "
                "WHERE id=?",
                (now_iso, current_turn, new_surf_count, new_distinct,
                 new_last_seen, consequence_id)
            )
            return True
    finally:
        conn.close()


def maybe_promote_consequences(campaign_id: int, current_turn: int) -> int:
    """Promote eligible active consequences to status='promoted'. Returns
    the number of rows promoted.

    A row is eligible when ALL three thresholds hold:
      - surface_count >= PROMOTION_SURFACE_COUNT
      - distinct_surface_turns >= PROMOTION_DISTINCT_TURNS
      - (current_turn - first_seen_turn) >= PROMOTION_AGE_TURNS

    For each promoted row, appends '[promoted: kind] summary' to the
    target NPC's notable_traits-equivalent field (description). v1 lacks
    a dedicated notable_traits column; the description field is the
    practical place for the prose memory to land. This is the
    double-encoding acknowledged in §7.5.

    Idempotent — running twice on already-promoted rows is a no-op.
    """
    conn = sqlite3.connect(DB_PATH)
    promoted = 0
    try:
        with conn:
            eligible = conn.execute(
                "SELECT id, npc_id, kind, summary FROM dnd_consequences "
                "WHERE campaign_id=? AND status='active' "
                "AND surface_count >= ? AND distinct_surface_turns >= ? "
                "AND (? - first_seen_turn) >= ?",
                (campaign_id,
                 PROMOTION_SURFACE_COUNT,
                 PROMOTION_DISTINCT_TURNS,
                 current_turn,
                 PROMOTION_AGE_TURNS)
            ).fetchall()

            now_iso = _now()
            for cid, npc_id, kind, summary in eligible:
                conn.execute(
                    "UPDATE dnd_consequences SET status='promoted', promoted_at=? "
                    "WHERE id=? AND status='active'",
                    (now_iso, cid)
                )
                # Append to dnd_npcs.description with bracketed prefix.
                # Description is the closest-to-notable_traits field in v1
                # (no dedicated column exists). Future schema may split.
                npc_row = conn.execute(
                    "SELECT description FROM dnd_npcs "
                    "WHERE id=? AND campaign_id=?",
                    (npc_id, campaign_id)
                ).fetchone()
                if npc_row:
                    existing_desc = (npc_row[0] or '').rstrip()
                    addition = f"[promoted: {kind}] {summary}"
                    if existing_desc and addition not in existing_desc:
                        new_desc = existing_desc + ' ' + addition
                    elif not existing_desc:
                        new_desc = addition
                    else:
                        new_desc = existing_desc  # already present, idempotent
                    conn.execute(
                        "UPDATE dnd_npcs SET description=? "
                        "WHERE id=? AND campaign_id=?",
                        (new_desc, npc_id, campaign_id)
                    )
                promoted += 1
                log(f"consequence_promoted campaign={campaign_id} "
                    f"npc_id={npc_id} kind={kind} consequence_id={cid}")
    finally:
        conn.close()
    return promoted


def consequence_list_for_command(campaign_id: int,
                                  npc_canonical: str = None) -> list:
    """Read-only query backing /consequence list [npc].

    Returns ALL rows (active + promoted), oldest-first by first_seen_turn,
    each as a dict that joins canonical_name from dnd_npcs.

    npc_canonical: optional canonical-name filter (case-insensitive,
    canonicalized via canonicalize_name before query).
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        params = [campaign_id]
        sql = (
            f"SELECT {_CONSEQUENCE_COLS}, n.canonical_name "
            "FROM dnd_consequences c "
            "INNER JOIN dnd_npcs n ON n.id = c.npc_id "
            "WHERE c.campaign_id=?"
        )
        if npc_canonical:
            sql += " AND n.canonical_name=?"
            params.append(canonicalize_name(npc_canonical))
        sql += " ORDER BY c.first_seen_turn ASC, c.id ASC"
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()
    out = []
    for row in rows:
        d = _consequence_row_to_dict(row[:17])
        d['canonical_name'] = row[17]
        out.append(d)
    return out


def _resolve_npc_id_for_consequence(campaign_id: int,
                                     target_name: str,
                                     pc_names: list) -> tuple:
    """Resolve a parser-emitted target name to an NPC id. Strict canonical
    + alias lookup — no substring fallback. Returns (npc_id, reject_reason).
    npc_id is None when unresolved or PC-overlapping; reject_reason is None
    when resolved successfully.

    Reject reasons:
      'unresolved_target' — name doesn't match any canonical NPC name or alias
      'pc_match'          — name overlaps a bound PC (PCs are not NPCs)
    """
    if not target_name or not isinstance(target_name, str):
        return None, 'unresolved_target'
    canonical = canonicalize_name(target_name)
    if not canonical:
        return None, 'unresolved_target'

    if pc_names:
        for pc in pc_names:
            if names_overlap(canonical, pc):
                return None, 'pc_match'

    conn = sqlite3.connect(DB_PATH)
    try:
        # Direct canonical match.
        row = conn.execute(
            "SELECT id FROM dnd_npcs WHERE campaign_id=? AND canonical_name=?",
            (campaign_id, canonical)
        ).fetchone()
        if row:
            return int(row[0]), None
        # Alias match — aliases is a JSON list of canonical-form strings.
        rows = conn.execute(
            "SELECT id, aliases FROM dnd_npcs WHERE campaign_id=?",
            (campaign_id,)
        ).fetchall()
    finally:
        conn.close()

    import json
    canonical_lower = canonical.strip().lower()
    for npc_id, aliases_json in rows:
        try:
            aliases = json.loads(aliases_json or '[]')
        except (json.JSONDecodeError, TypeError):
            continue
        alias_set = {a.strip().lower() for a in aliases if isinstance(a, str)}
        if canonical_lower in alias_set:
            return int(npc_id), None
    return None, 'unresolved_target'


def _name_appears_in_text(name: str, text: str) -> bool:
    """Whole-word, case-insensitive match of `name` in `text`.

    Used by the consequence-race diagnostic to distinguish "target NPC
    is being INTRODUCED this same turn (race against npc_extractor)"
    from "target NPC is genuinely off-canon." False on empty inputs.

    Word-boundary regex keeps 'Mira' from matching 'miracle' and
    'Aldric' from matching 'baldric'. Case-insensitive because the DM
    narration may use different capitalization than the parser-emitted
    target string.
    """
    if not name or not text:
        return False
    pattern = r'\b' + re.escape(name.strip()) + r'\b'
    return bool(re.search(pattern, text, re.IGNORECASE))


def apply_consequence_proposals(campaign_id: int, proposals: list,
                                 source: str, current_turn: int,
                                 narration_text: str = '') -> dict:
    """Validate a list of parser-emitted consequence proposals and write
    valid ones via consequence_upsert. Returns a summary dict.

    proposals: list of {'target': str, 'kind': str, 'severity': int,
                        'summary': str} dicts
    source: 'player' or 'dm'
    current_turn: campaign turn counter at capture time
    narration_text: optional same-turn DM narration. When provided, a
        proposal that rejects with 'unresolved_target' is checked against
        narration_text — if the target name appears as a whole word, an
        additional `consequence_race: ... reason=npc_introduction_race`
        log line is emitted alongside the generic rejection. Distinguishes
        the introduction-race case (NPC being introduced this turn,
        racing against npc_extractor) from genuinely off-canon mentions.
        Pure observation; no behavior change. Default '' skips the check.

    Each proposal is independently validated; failures log a structured
    consequence_rejected line. No-op if proposals is empty. Never raises —
    individual errors are caught and logged.

    Returns {'inserted': N, 'updated': N, 'rejected': N, 'reasons': {...}}
    """
    summary = {'inserted': 0, 'updated': 0, 'rejected': 0,
               'reasons': {}}
    if not proposals:
        return summary
    if source not in CONSEQUENCE_SOURCES:
        log(f"consequence_apply: invalid source={source!r} campaign={campaign_id}")
        return summary

    try:
        pc_names = get_bound_character_names(campaign_id)
    except Exception as e:
        log(f"consequence_apply: pc_names lookup error={e!r} campaign={campaign_id}")
        pc_names = []

    for prop in proposals:
        if not isinstance(prop, dict):
            summary['rejected'] += 1
            summary['reasons']['bad_shape'] = summary['reasons'].get('bad_shape', 0) + 1
            log(f"consequence_rejected reason=bad_shape source={source} "
                f"campaign={campaign_id}")
            continue
        target = prop.get('target', '')
        kind = prop.get('kind', '')
        severity = prop.get('severity')
        prop_summary = prop.get('summary', '')

        npc_id, reject_reason = _resolve_npc_id_for_consequence(
            campaign_id, target, pc_names
        )
        if npc_id is None:
            summary['rejected'] += 1
            summary['reasons'][reject_reason] = (
                summary['reasons'].get(reject_reason, 0) + 1
            )
            log(f"consequence_rejected reason={reject_reason} "
                f"source={source} campaign={campaign_id} "
                f"target={target!r} kind={kind!r}")
            # Introduction-race diagnostic. When the rejection is
            # 'unresolved_target' AND the target name appears in
            # narration_text (the same-turn DM response), the NPC was
            # being introduced this turn — npc_extractor will write the
            # row to dnd_npcs but consequence resolution ran first and
            # missed it. The consequence is silently lost. Emit a
            # SECOND log line so this case is greppable independently
            # of the generic unresolved-target rejection.
            if reject_reason == 'unresolved_target' and narration_text:
                if _name_appears_in_text(target, narration_text):
                    log(f"consequence_race: campaign={campaign_id} "
                        f"target={target!r} reason=npc_introduction_race "
                        f"source={source}")
            continue

        try:
            sev_int = int(severity) if severity is not None else None
        except (TypeError, ValueError):
            sev_int = None
        if sev_int is None:
            summary['rejected'] += 1
            summary['reasons']['severity_missing'] = (
                summary['reasons'].get('severity_missing', 0) + 1
            )
            log(f"consequence_rejected reason=severity_missing "
                f"source={source} campaign={campaign_id} "
                f"target={target!r} kind={kind!r}")
            continue

        try:
            result = consequence_upsert(
                campaign_id=campaign_id,
                npc_id=npc_id,
                kind=kind,
                summary=prop_summary,
                severity=sev_int,
                source=source,
                current_turn=current_turn,
            )
        except Exception as e:
            summary['rejected'] += 1
            summary['reasons']['exception'] = (
                summary['reasons'].get('exception', 0) + 1
            )
            log(f"consequence_apply: exception={e!r} "
                f"campaign={campaign_id} target={target!r} kind={kind!r}")
            continue

        status = result['status']
        if status == 'inserted':
            summary['inserted'] += 1
            log(f"consequence_captured campaign={campaign_id} "
                f"npc_id={npc_id} kind={kind} severity={sev_int} "
                f"source={source} summary_len={len(prop_summary or '')} "
                f"id={result['id']}")
        elif status == 'updated':
            summary['updated'] += 1
            log(f"consequence_captured campaign={campaign_id} "
                f"npc_id={npc_id} kind={kind} severity={sev_int} "
                f"source={source} summary_len={len(prop_summary or '')} "
                f"id={result['id']} (updated)")
        else:
            summary['rejected'] += 1
            reason = result.get('reason') or 'unknown'
            summary['reasons'][reason] = summary['reasons'].get(reason, 0) + 1
            log(f"consequence_rejected reason={reason} "
                f"source={source} campaign={campaign_id} "
                f"target={target!r} kind={kind!r}")
    return summary


def update_scene_state(campaign_id: int, **kwargs):
    """Merge updates into scene state. List fields append (deduped).

    IMPORTANT: 'mode', 'tension', 'active_npcs', and 'active_threats' are
    NOT accepted here — those are owned by deterministic systems, not the
    LLM extraction thread. Use set_scene_mode() for mode changes.
    """
    import json
    # These fields may only be written by deterministic code paths, not the
    # LLM extraction thread. Silently drop them if passed.
    LOCKED_FIELDS = {'mode', 'tension', 'active_npcs', 'active_threats'}

    JSON_LIST_FIELDS = {'established_details', 'open_questions'}
    SCALAR_FIELDS = {'location', 'focus', 'last_player_action', 'last_scene_change'}

    current = get_scene_state(campaign_id)
    if current is None:
        init_scene_state(campaign_id, seed='')
        current = get_scene_state(campaign_id)

    sets = []
    values = []
    for key, val in kwargs.items():
        if key in LOCKED_FIELDS:
            log(f"update_scene_state: '{key}' is locked — only deterministic systems may write this field, skipping")
            continue
        if key in JSON_LIST_FIELDS:
            existing = current.get(key, [])
            if isinstance(val, str):
                val = [val]
            for item in val:
                if item and item not in existing:
                    existing.append(item)
            existing = existing[-20:]
            sets.append(f"{key}=?")
            values.append(json.dumps(existing))
        elif key in SCALAR_FIELDS:
            sets.append(f"{key}=?")
            values.append(str(val)[:1000])
        else:
            log(f"update_scene_state: ignoring unknown field '{key}'")
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
    """Lightweight LLM call to extract narrative scene updates from a DM turn.

    SCOPE: This thread may ONLY update established_details, open_questions,
    location, focus, and last_scene_change. It must NOT set mode, tension,
    active_npcs, or active_threats — those are owned by deterministic systems.
    The update_scene_state() function enforces this at the write layer, but
    the extraction prompt also intentionally omits those fields so the LLM
    doesn't waste tokens on them.
    """
    import json
    current = get_scene_state(campaign_id) or {}
    extraction_prompt = (
        "You extract structured scene-state updates from a D&D play exchange.\n\n"
        f"Current scene state:\n"
        f"- Location: {current.get('location') or '(unknown)'}\n"
        f"- Focus: {current.get('focus') or '(unknown)'}\n"
        f"- Already-established details: {', '.join(current.get('established_details') or []) or '(none)'}\n\n"
        f"Player just said: \"{player_action}\"\n\n"
        f"The DM just replied:\n\"\"\"\n{dm_response[:1500]}\n\"\"\"\n\n"
        "Output ONLY valid JSON. Use this schema (omit fields that did NOT change):\n"
        "{\"location\": \"...\", \"focus\": \"...\", "
        "\"new_established_details\": [\"...\"], "
        "\"new_open_questions\": [\"...\"], "
        "\"last_scene_change\": \"one short sentence\"}\n\n"
        "Rules: each list item 1-6 words. Only details the DM EXPLICITLY mentioned. "
        "Do not repeat already-established details. If nothing meaningful changed, return {}."
    )
    try:
        # task_type='extraction' routes to cerebras/groq, skipping groq_heavy
        # which is reserved for DnD narration. Pre-Session-16 this was set to
        # 'dnd' by mistake — the JSON-extraction call competed with the actual
        # narration call for groq_heavy each turn, doubled DND_PRIORITY_OVERRIDE
        # log noise, and burned the heavy model on bounded structured output.
        response, _ = route(
            messages=[{"role": "user", "content": extraction_prompt}],
            task_type="extraction",
            system_prompt="You output structured JSON only. No prose.",
        )
        body = response.strip()
        if body.startswith("```"):
            body = re.sub(r"^```(?:json)?\s*", "", body)
            body = re.sub(r"\s*```$", "", body)
        m = re.search(r"\{.*\}", body, re.DOTALL)
        if not m:
            log("extract_scene_updates: no JSON in response")
            return
        data = json.loads(m.group(0))
    except Exception as e:
        log(f"extract_scene_updates parse error: {e}")
        return

    if not data:
        return

    # Only write the fields this thread is allowed to touch.
    update_kwargs = {'last_player_action': player_action[:500]}
    if data.get('location'):
        update_kwargs['location'] = data['location']
    if data.get('focus'):
        update_kwargs['focus'] = data['focus']
    if data.get('last_scene_change'):
        update_kwargs['last_scene_change'] = data['last_scene_change']
    if data.get('new_established_details'):
        update_kwargs['established_details'] = data['new_established_details']
    if data.get('new_open_questions'):
        update_kwargs['open_questions'] = data['new_open_questions']

    update_scene_state(campaign_id, **update_kwargs)
    log(f"scene state updated: {list(update_kwargs.keys())}")


# ─────────────────────────────────────────────────────────
# DM prompt + response
# ─────────────────────────────────────────────────────────

def _format_avrae_events(events):
    """Turn structured Avrae events into a compact mechanics block for the DM."""
    if not events:
        return ""
    lines = []
    for ev in events:
        actor = ev.get('actor') or 'Someone'
        kind = ev.get('kind', 'roll')
        detail = ev.get('detail', '')
        result = ev.get('result')
        nat = ev.get('nat')
        damage = ev.get('damage')
        crit = ev.get('crit')
        bits = [f"{actor}"]
        if kind == 'attack':
            bits.append(f"attacks with {detail}" if detail else "attacks")
            if result is not None:
                bits.append(f"— hits AC {result}")
            if damage is not None:
                bits.append(f"for {damage} damage")
            if crit:
                bits.append("(CRITICAL HIT)")
        elif kind == 'check':
            bits.append(f"rolls {detail}" if detail else "rolls a check")
            if result is not None:
                bits.append(f"= {result}")
        elif kind == 'save':
            bits.append(f"makes a {detail} save" if detail else "makes a save")
            if result is not None:
                bits.append(f"= {result}")
        elif kind == 'cast':
            bits.append(f"casts {detail}" if detail else "casts a spell")
            if damage is not None:
                bits.append(f"({damage} damage)")
        elif kind == 'damage':
            bits.append(f"takes {damage} damage" if damage is not None else "takes damage")
        elif kind == 'rest':
            bits.append(f"takes a {detail}" if detail else "rests")
        else:
            bits.append(f"{kind}: {detail}")
            if result is not None:
                bits.append(f"= {result}")
        if nat == 20 and kind in ('attack', 'check', 'save'):
            bits.append("[NAT 20]")
        elif nat == 1 and kind in ('attack', 'check', 'save'):
            bits.append("[NAT 1]")
        lines.append("- " + " ".join(bits))
    return "\n".join(lines)


def build_dm_context(campaign, characters, relevant_history="", dm_guidance="",
                     action_type="", avrae_events=None,
                     character_contexts=None, roll_decision=None, mode="exploration",
                     scene_state=None, capability_decision=None,
                     pacing_directive="", central_thread_directive="",
                     philosophy_block="", consequence_directive="",
                     commitment_directive="", init_directive="",
                     persistence_directive="", loot_directive="",
                     combat_redirect="",
                     time_directive="",
                     arbitration_block="", arbitration_hardstop_echo="",
                     resolution_block="", resolution_hardstop_echo="",
                     acting_character_names=None):
    """Compose the system prompt. Tone, pacing, voice — narration ONLY.
    Roll decisions come pre-made via roll_decision.
    Capability claims pre-validated via capability_decision (S9) — when
    a player claim isn't supported by Avrae or skeleton, surfaces a
    soft annotation. Skeleton declarations CONFIRM but never block."""
    if characters:
        char_summaries = "\n".join(
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
        "STRICTLY NO Marvel, Pokemon, Star Wars, or other fictional-universe content."
    )
    tone = (campaign.get('tone') or '').strip() or DEFAULT_TONE

    history_section = (
        f"\n\n=== RELEVANT PAST EVENTS ===\n{relevant_history}"
        if relevant_history else ""
    )

    guidance_section = (
        f"\n\n=== DM PACING EXAMPLES ===\n"
        f"For ENERGY and PACING only. NEVER copy settings, names, places, or specific details.\n\n"
        f"{dm_guidance}"
        if dm_guidance else ""
    )

    avrae_block = _format_avrae_events(avrae_events) if avrae_events else ""
    avrae_section = (
        f"\n\n=== MECHANICAL EVENTS (from Avrae, just rolled) ===\n"
        f"{avrae_block}\n"
        f"These rolls already happened. Narrate the OUTCOME. Do NOT re-ask. Do NOT quote the number."
        if avrae_block else ""
    )

    # Acting character block. Three shapes:
    #   0 contexts → no block (no resolved sheet data)
    #   1 context  → full verbose block (solo play, preserves existing behavior)
    #   2+ contexts → compact one-line-per-actor block (multiplayer)
    # Per 2C.1: full per-actor sheets are NOT re-injected for multi-actor batches.
    if character_contexts and len(character_contexts) == 1:
        char_ctx_section = f"\n\n=== ACTING CHARACTER ===\n{character_contexts[0].to_prompt_block()}"
    elif character_contexts and len(character_contexts) > 1:
        compact_lines = "\n".join(c.to_compact_line() for c in character_contexts)
        char_ctx_section = f"\n\n=== ACTING CHARACTERS ===\n{compact_lines}"
    else:
        char_ctx_section = ""

    # Inventory line (Track 4 #1) — narrative items the active character
    # is carrying. Loot, quest objects, story items. Distinct from Avrae
    # sheet-bound combat gear. Pure read, no directive layer — just gives
    # the LLM the inventory list so narration can honor "I unlock the
    # cellar with my silver key" without needing the (deferred) item-claim
    # capability layer. Cap at 8 items shown; ... +N more when truncated.
    # Omitted entirely when empty. Single-actor only — multi-actor batches
    # don't render to keep the prompt compact (revisit if multiplayer
    # friction shows it). Sources actor identity from `acting_character_names`
    # (always populated when an actor typed) rather than `character_contexts`
    # (only populated when Avrae sheet is cached) so render works when sheet
    # data is missing.
    _INVENTORY_RENDER_CAP = 8
    inventory_section = ""
    _inv_char = None
    if acting_character_names and len(acting_character_names) == 1:
        _inv_char = acting_character_names[0]
    elif character_contexts and len(character_contexts) == 1:
        _inv_char = character_contexts[0].name
    if _inv_char:
        try:
            _inv_rows = get_inventory(campaign['id'], _inv_char)
            log(f"inventory_render: campaign={campaign['id']} "
                f"character={_inv_char!r} count={len(_inv_rows)}")
            if _inv_rows:
                shown = _inv_rows[:_INVENTORY_RENDER_CAP]
                rendered = []
                for r in shown:
                    name = r['item_name']
                    qty = r['quantity']
                    rendered.append(f"{name} ({qty})" if qty and qty > 1 else name)
                line = ", ".join(rendered)
                if len(_inv_rows) > _INVENTORY_RENDER_CAP:
                    line += f", ... (+{len(_inv_rows) - _INVENTORY_RENDER_CAP} more)"
                inventory_section = (
                    f"\n\n=== {_inv_char.upper()}'S NOTABLE ITEMS ===\n{line}"
                )
        except Exception as _e:
            log(f"inventory render skipped: {_e!r}")

    roll_directive = (
        f"\n\n=== ROLL DIRECTIVE ===\n{roll_decision.to_prompt_directive(init_directive_body=init_directive)}"
        if roll_decision else ""
    )

    # Capability directive (S9) — silent on no-claim AND on CONFIRMED
    # outcomes. Only VALID_BUT_UNCONFIGURED (soft annotation) and
    # future INVALID (anti-fabrication, no producer in v1) emit text.
    capability_directive = (
        f"\n\n=== CAPABILITY CHECK ===\n{capability_decision.to_prompt_directive()}"
        if capability_decision and capability_decision.to_prompt_directive()
        else ""
    )

    # Pacing directive (Track 3, Session 14) — converts existing
    # tension/clocks state into imperative narrative-move constraints.
    # Silent at low tension + no urgent clocks; otherwise tier directive
    # plus optional urgent-clock callout. Computed advisor-side
    # (orch.compute_pacing_directive); engine just renders.
    pacing_directive_block = (
        f"\n\n=== PACING DIRECTIVE ===\n{pacing_directive}"
        if pacing_directive else ""
    )

    # Central thread directive (Track 3, Session 14) — converts the
    # campaign's first authored skeleton hook into directional pressure
    # on every turn. Phrasing explicitly forbids literal restatement to
    # avoid keyword-spamming the hook. Composes with pacing directive
    # (pacing = how hard, central thread = which direction).
    central_thread_block = (
        f"\n\n=== CENTRAL THREAD ===\n{central_thread_directive}"
        if central_thread_directive else ""
    )

    # Consequence directive (Track 3, Session 16) — surfaces accumulated
    # consequences (threats, mercy, cruelty, betrayal, promise, alliance)
    # against NPCs in scene as imperative pressure on what the world
    # remembers. Composed by orch.compute_consequence_directive; engine
    # just renders. Cap-at-3, severity-then-recency ordered. Empty when
    # nothing relevant is in scope.
    consequence_block = (
        f"\n\n=== PENDING CONSEQUENCES ===\n{consequence_directive}"
        if consequence_directive else ""
    )

    # Committed-action resolution directive (Track 3, Session 19) —
    # surfaces the godmode-escape failure mode (player commits to combat,
    # next turn tries to scene-shift without resolving the prior commitment).
    # Computed advisor-side (orch.compute_commitment_directive); engine
    # just renders. Last block in the tactical band, per locked §11.8 —
    # commitment is the most immediate-stakes constraint and matches the
    # `commitment=` slot reserved in the directive_emit log shape.
    commitment_block = (
        f"\n\n=== UNRESOLVED COMMITMENT ===\n{commitment_directive}"
        if commitment_directive else ""
    )

    # Combat persistence directive (Track 3, Session 21) — three composed
    # sub-pressures (enemy persistence, condition awareness, initiative-order
    # confirm) rendered from dnd_combatant_state snapshot + active_turn.
    # Master gate: mode == 'combat'; otherwise empty. Last block in tactical
    # band per locked §11.E (most-immediate-stakes ordering).
    persistence_block = (
        f"\n\n=== COMBAT PERSISTENCE ===\n{persistence_directive}"
        if persistence_directive else ""
    )

    # Loot directive (Track 4 #2, Session 22) — surfaces creatures that
    # transitioned alive=1 -> alive=0 since the last narration turn. Renders
    # AFTER persistence so combat resolution beats appear before the loot
    # discovery beat in the tactical band. Empty when no pending loot.
    loot_block = (
        f"\n\n=== LOOT TO SURFACE ===\n{loot_directive}"
        if loot_directive else ""
    )

    # Combat redirect directive (Track 6 #2, Session 23) — informs the LLM
    # about active threats when player on-turn narration in combat may
    # attempt to bypass combat reality. Companion to S19's commitment
    # directive (escape-intent only); broader scope here — fires on every
    # PC on-turn narration in active combat with alive enemies. Renders
    # AFTER loot so any loot-discovery beat from a just-defeated foe has
    # already cleared before the redirect block restates the remaining
    # threats. Empty when gate fails (mode != combat, no alive enemies,
    # or NPC turn).
    combat_redirect_block = (
        f"\n\n=== COMBAT REDIRECT ===\n{combat_redirect}"
        if combat_redirect else ""
    )

    # Time directive (Track 4 #3, Session 27) — fires only on the turn
    # immediately following an advancement (recency check via
    # time_just_advanced(); §11.E sub-(iii)α). One in-fiction beat per
    # advancement, then hand agency back. Pure function in orchestration.
    # Renders AFTER combat_redirect because combat-band beats outrank
    # time-of-day texture in the tactical ordering, and time texture is
    # an opener-shape directive that doesn't compete with mid-fight pressure.
    time_directive_block = (
        f"\n\n=== TIME ADVANCE ===\n{time_directive}"
        if time_directive else ""
    )

    # Arbitration block (Track 7 #2) — multi-actor binding verdicts for the
    # current turn. Renders FIRST in the prompt (top placement for response
    # framing per concrete-in-prompt §48); the hardstop echo restates the
    # verdict at the END of HARD STOP RULES (last constraint before
    # generation per §2). Both placements required: one for framing, one
    # for the moment of generation. Empty when all verdicts are FREE/FALLBACK
    # with no constraint. Single-actor degenerate case is byte-identical to
    # Track 7 #1's adjudication block (per §11.N rename lock).
    arbitration_section = (
        f"\n\n=== ARBITRATION RESULT ===\n{arbitration_block}"
        if arbitration_block else ""
    )
    arbitration_hardstop_section = (
        f"\n7. {arbitration_hardstop_echo}"
        if arbitration_hardstop_echo else ""
    )

    # Ship 1 (S34) — AUTHORITATIVE ROLL RESOLUTION block. Renders the
    # engine-computed DC-vs-roll verdict when the matcher auto-fired
    # _dm_respond_and_post via resolve_directive (RESOLUTION_BINDING_SPEC.md
    # §7). Mutually exclusive with arbitration_section by flow (§2.3) —
    # arbitration fires on player-typed input through dm_respond's normal
    # path; resolution fires on DM-typed-directive consume. Both kwargs are
    # rendered if both are populated (defensive §11.9); the warning log
    # below surfaces any unexpected co-occurrence.
    resolution_section = (
        f"\n\n═══ AUTHORITATIVE ROLL RESOLUTION ═══\n{resolution_block}\n═══"
        if resolution_block else ""
    )
    resolution_hardstop_section = (
        f"\n8. {resolution_hardstop_echo}"
        if resolution_hardstop_echo else ""
    )
    if arbitration_block and resolution_block:
        try:
            log(f"unexpected_binding_co_occurrence: campaign={campaign.get('id')} "
                f"has_arbitration=1 has_resolution=1")
        except Exception:
            pass

    # DM philosophy block (Track 3, Session 14) — operating policy for
    # how all subsequent directives are interpreted. Authored by Jordan,
    # mtime-cached, reloads on file change. Sits HIGH in the prompt
    # (after canonical state, before tactical directives) because it
    # frames how pacing/central-thread/etc. should be applied. State
    # outranks policy; policy outranks individual move directives.
    philosophy_block_rendered = (
        f"\n\n=== DM PHILOSOPHY ===\n{philosophy_block}"
        if philosophy_block else ""
    )

    _MODE_DIRECTIVES = {
        'combat': (
            "COMBAT MODE. Be terse and kinetic. "
            "One sentence of action per beat — no atmospheric padding. "
            "Describe what happens mechanically and viscerally: blows land, positions shift, enemies react. "
            "Every response should end with immediate pressure: what does the enemy do, what opens up, what closes down. "
            "Do NOT describe the room. The players know where they are. Move the fight forward."
        ),
        'exploration': (
            "EXPLORATION MODE. Descriptive and sensory. "
            "Ground the player in place — light, smell, sound, texture. "
            "Reward curiosity: examining something yields a real detail, not a brush-off. "
            "Pace forward without urgency. Let the world breathe. "
            "Hint at what might be here without over-explaining."
        ),
        'social': (
            "SOCIAL MODE. Dialogue-forward. "
            "NPCs have a voice, a posture, a tell — write them as people with wants, not exposition dispensers. "
            "Do not summarize what an NPC says. Give them actual lines. "
            "Read the player approach (intimidation, charm, deception) and let the NPC react accordingly — "
            "with suspicion, warmth, deflection. Social scenes should feel like a negotiation, not a cutscene."
        ),
        'travel': (
            "TRAVEL MODE. Montage and pace. "
            "Compress time. Describe the journey in broad strokes — terrain, weather, mood of the road. "
            "One or two sharp details, not a travel log. "
            "Use travel to plant seeds: a smoke plume on the horizon, a grave marker with no name, "
            "merchants moving fast in the other direction. Something to notice. Then arrive."
        ),
        'downtime': (
            "DOWNTIME MODE. Low-stakes, character-forward. "
            "This is time to breathe, spend coin, train, recover, or pursue personal threads. "
            "Do NOT call for rolls unless the player is doing something genuinely risky. "
            "Let the world feel mundane and alive. NPCs have opinions about the party by now. "
            "Reward roleplaying over optimization."
        ),
    }
    _directive = _MODE_DIRECTIVES.get(mode, _MODE_DIRECTIVES['exploration'])
    mode_block = f"\n\n=== CURRENT MODE: {mode.upper()} ===\n{_directive}"

    scene_state_section = ""
    if scene_state:
        details = scene_state.get('established_details') or []
        questions = scene_state.get('open_questions') or []
        # S3 (Session 15): active_npcs is now derived from dnd_npcs.last_mentioned
        # at prompt-render rather than read from a never-written field. Section
        # is OMITTED entirely when empty (no "(none)" lie). active_threats
        # prompt block dropped — schema column kept; defer until threat model
        # exists.
        # Bug 3 fix: scope to NPCs at current location ∪ unattributed NPCs so
        # tavern NPCs don't surface after /travel. Falls back to campaign-wide
        # when current_location_id is unset.
        _scope_loc = scene_state.get('current_location_id')
        recent_npcs = get_recently_active_npcs(
            campaign['id'], limit=6, location_id=_scope_loc
        )
        log(f"npcs_in_context: campaign={campaign['id']} "
            f"count={len(recent_npcs)} "
            f"location_filtered={1 if _scope_loc else 0}")
        recent_npcs_line = (
            f"Recently active NPCs: {', '.join(recent_npcs)}\n"
            if recent_npcs else ""
        )
        scene_state_section = (
            "\n\n=== SCENE STATE (authoritative) ===\n"
            f"Location: {scene_state.get('location') or '(not yet set)'}\n"
            f"Focus: {scene_state.get('focus') or '(not yet set)'}\n"
            f"Tension: {tension_label(scene_state.get('tension_int') or 0)} ({scene_state.get('tension_int') or 0}/100)\n"
            f"Established details: {', '.join(details) if details else '(none yet)'}\n"
            f"{recent_npcs_line}"
            f"Open questions: {', '.join(questions) if questions else '(none)'}\n"
            f"Last player action: {scene_state.get('last_player_action') or '(this is the first turn)'}\n"
            f"Last scene change: {scene_state.get('last_scene_change') or '(scene just opened)'}"
        )
        clocks = scene_state.get('progress_clocks') or []
        clock_block = clocks_to_prompt_block(clocks)
        if clock_block:
            scene_state_section += "\n\n" + clock_block

    # Quest block — pulled fresh per turn. Active quests only.
    quests_section = ""
    quest_block = quests_to_prompt_block(get_active_quests(campaign['id']))
    if quest_block:
        quests_section = f"\n\n{quest_block}"

    # Companions block — pulled fresh per turn. Slots between PARTY and the
    # scene description so the DM has the full party (PCs + NPCs) in mind
    # before reading current state.
    companions_section = ""
    companions_block = companions_to_prompt_block(get_companions(campaign['id']))
    if companions_block:
        companions_section = f"\n\n{companions_block}"

    return f"""You are the Dungeon Master for a D&D 5th Edition campaign called "{campaign['name']}".{arbitration_section}{resolution_section}

=== SETTING & TONE (HARD CONSTRAINT — DO NOT VIOLATE) ===
{tone}

=== PARTY ===
{char_summaries}{companions_section}

=== CURRENT SCENE ===
{campaign.get('current_scene') or 'The adventure is just beginning.'}{mode_block}{scene_state_section}{quests_section}{char_ctx_section}{inventory_section}{history_section}{philosophy_block_rendered}{guidance_section}{avrae_section}{roll_directive}{capability_directive}{pacing_directive_block}{central_thread_block}{consequence_block}{commitment_block}{persistence_block}{loot_block}{combat_redirect_block}{time_directive_block}

=== HOW THIS GAME WORKS ===

You and Avrae split work cleanly:
- AVRAE handles ALL dice, sheets, HP, attacks, spells, saves, checks.
- YOU handle scene description, NPC dialogue, world reactions, pacing.

You DO NOT decide whether to call for a roll. That decision is made FOR you and given as a ROLL DIRECTIVE above. Follow it exactly:
- If NO ROLL: narrate the outcome based on character ability + tags. Do not invent a roll.
- If a specific roll is required: end your message asking for that exact roll, then STOP. Do not narrate the outcome until the roll comes back as a MECHANICAL EVENT next turn.

=== READING MECHANICAL EVENTS ===

When MECHANICAL EVENTS are present, those rolls already happened. Narrate the OUTCOME — never re-ask, never quote the number.
- Total 5 or below = clear failure with a consequence (alarm, broken tool, attention drawn).
- Total 6-9 = failure, but a small one (no progress, but no penalty either).
- Total 10-14 = partial success or success at a cost (chest opens but the lock is now broken; door opens but it creaks loudly).
- Total 15-19 = solid success.
- Total 20+ = exceptional success, narrate flair.
- Nat 20 = spectacular. Nat 1 = catastrophic, something memorable goes wrong.

=== CHARACTER AWARENESS ===

The ACTING CHARACTER block (if present) is PRIVATE DM REFERENCE — character stats, skills, tags. NEVER reproduce, summarize, list, or read it back to the player. The player has their own sheet via Avrae; they do not need a copy from you. Use the data SILENTLY to inform narration:
- Reference tags naturally in prose, woven into description ("with darkvision, the dim alley reads clearly" / "the rogue's hand is already drifting toward the lock").
- Match difficulty and tone to their level.
- Don't ignore their proficiencies.
- NEVER write a stat readout, AC/HP line, "Notable skills:" line, "Attacks:" line, or "Tags:" line in your response. NEVER repeat the structure or labels of the ACTING CHARACTER block. If you find yourself writing "Donovan Ruby — Level 1 Dwarf Rogue" or anything resembling a sheet, stop and rewrite the response as pure narration.
- Address the acting character by the parenthesized name in their identity line ("Donovan Ruby (address as Donovan)" → call him Donovan, never Ruby) unless the player uses a different form first. NPCs, narration, and direct address all follow this rule. If no parenthetical is present, the full name IS the address form.

=== OUT-OF-CHARACTER REQUESTS ===

If the ROLL DIRECTIVE says "Out-of-character question", DROP CHARACTER. Answer in italics — that means wrap your reply in single asterisks like *this is in italics* — with a short, helpful note. Never write the literal word "italics" in your response.

=== SCENE STATE RULES (MANDATORY) ===

The SCENE STATE block above is authoritative. Use it to keep continuity:
- Do NOT re-describe established details unless the player specifically examines them, they materially change, or they become relevant again.
- Do NOT re-establish atmosphere every turn. Move forward.
- Do NOT contradict the location, focus, NPCs, or threats listed there.
- Narrate FORWARD from "Last player action". Advance the moment. Reveal something new, apply a consequence, or push for a decision.

=== LENGTH (MANDATORY) ===

Maximum 2 short paragraphs. Maximum 6 sentences total. Brevity is mandatory.
After the first turn in a scene, prefer 1 short paragraph. The reader already knows where they are.

=== STRICT AVOID ===

Forbidden phrases: "the air clings", "silence is oppressive", "shadows seem to writhe", "shadows seem to twist", "the very [X]", "as if [X] itself was [Y]", "darkness seems to swallow", "with calculated silence", "luminescent orbs", "neon-drenched", "grav-cars", "holographic", "kaleidoscope", "swirling vortex".

Do NOT mix genres. Do NOT restate what the player said. Do NOT pad atmosphere when story should advance.

=== OUTPUT FORMAT ===

Plain prose. **bold** for key names. *italics* for thought, whisper, or OOC asides.

=== AUTO-EXECUTE (TIER 1 STRUCTURAL CHANGES) ===

This is the AUTHORITATIVE state-write layer. If this turn explicitly enacted a Tier 1 structural change, append a machine-readable tail. The tail is stripped before the player sees it — it exists ONLY to commit state. This decision is made BEFORE any UI suggestions; commit state first, present second.

Tier 1 commands (these belong ONLY here, never in Player UI Suggestions):
- QUEST_ADD|<title>         — a quest the party just committed to in this narration
- CLOCK_TICK|<name>|<n>     — a clock explicitly advanced (n = integer segments ticked)
- MODE|<mode>               — scene mode shift (combat/exploration/social/travel/downtime)

MODE rule: emit ONLY on a clear action-state transition — blade drawn, chase begins, fight starts, ambush lands. Atmosphere alone ("tension builds", "feels dangerous", "something stirs") does NOT qualify. Borderline fires you do emit should be honest transitions, not atmospheric hedges.

Tail format — exact, no variation:
AUTO_EXECUTE_BEGIN
QUEST_ADD|Investigate the Crystal Cave
CLOCK_TICK|Detection|1
MODE|combat
AUTO_EXECUTE_END

Rules:
- Tail is ALWAYS the very last content in the response. Nothing follows AUTO_EXECUTE_END.
- Omit the entire tail if no Tier 1 changes occurred. Most turns: no tail.
- One line per change. No duplicates. Titles must be plain text — no pipe characters.
- Do not emit QUEST_ADD for quests already in the quest log.
- Do not emit CLOCK_TICK for clocks that don't exist yet — that goes in Player UI Suggestions as /clock create.

=== PLAYER UI SUGGESTIONS (DERIVED ONLY, OPTIONAL) ===

This is a REFLECTIVE UI layer, not a decision layer. It surfaces ambiguous or higher-impact actions the player may want to run manually — actions the engine deliberately does NOT auto-execute. It is purely derivative: it cannot mutate state, and it must never overlap with the AUTO-EXECUTE tail above.

If this turn surfaced a Tier 2/3 action worth offering, you MAY append a "Suggested Actions" block immediately before the AUTO-EXECUTE tail (or at the end of the response if no tail).

Allowed commands ONLY:
- /encounter stealth|social|trap   — start an encounter preset (mode + clocks + tension)
- /clock create <name> <capacity>  — create a new progress clock
- /companion add|remove|edit       — manage NPC companions

DO NOT include /quest, /clock tick, or /mode in this block. Those are Tier 1 and belong in the AUTO-EXECUTE tail. If you find yourself wanting to suggest one of them here, emit it as AUTO-EXECUTE instead.

Format exactly (bullets required, no trailing commas):

  Suggested Actions:
  - /encounter stealth
  - /clock create Detection 4

INVALID examples (do NOT do this):
  Suggested Actions:
  /encounter stealth,            ← missing bullet, trailing comma
  - Suggest: /encounter stealth  ← extra prefix
  /companion Frank interact      ← invented subcommand

Rules:
- 1 to 3 suggestions, never more.
- Use only the three allowed commands above. Do NOT invent commands or subcommands.
- Suggest only what the narration just established. No speculation.
- If nothing in this turn warrants a Tier 2/3 suggestion, OMIT the block entirely. Silence is correct.
- If HARD STOP RULE 1 (roll required) applies, OMIT this block.

This block reflects state that already exists; it does not create it.

=== FINAL TONE REMINDER ===
{tone}

=== HARD STOP RULES (READ LAST, OBEY ABSOLUTELY) ===
1. If the ROLL DIRECTIVE above said a specific roll is required, your reply MUST end with the roll request and NOTHING ELSE. Do not narrate the outcome. Do not describe the chest opening. Do not invent loot. STOP after the roll request.
2. The SCENE STATE "Established details" list is what the player ALREADY KNOWS. Do NOT mention any of those items again, EVEN AS BACKGROUND. No "rough-hewn walls" if walls are established. No "iron chest" if chest is established. No "musty air" if it's listed. Use pronouns ("the chest", "it", "the lock") instead of re-introducing nouns. The player remembers. If you cannot write a sentence WITHOUT referencing an established detail, write a shorter response or just a question.
3. If you cannot think of anything new to add, write a short response (one or two sentences) that simply asks the player what they want to do next.
4. NPC COMMITMENT. If the player asserted a decision, demand, threat, refusal, or commitment (this turn or unresolved from a prior turn), an involved NPC MUST take a position before this response ends: agree, refuse, counter-offer, walk away, or attack. Do not re-ask a question the player already answered. Do not end the turn with the negotiation in the same state it started. Exception: if rule 1 fires (roll required), the NPC reaction resolves AFTER the roll — STOP at the roll request. Otherwise, NPC commitment is mandatory and overrides rule 3: "what do you want to do next?" is NOT a valid response to a player commitment. If no NPC is in the scene, narrate the consequence of the commitment directly — do not stall on it.
5. NO UNAUTHORIZED MECHANICAL COMMANDS. The ONLY Avrae command (`!check`, `!save`, `!roll`, `!attack`, `!cast`, etc.) that may appear in your response is the exact command quoted in the ROLL DIRECTIVE's "End your message asking the player to roll: `<cmd>`" line, and only when ROLL DIRECTIVE actually requires a roll. If ROLL DIRECTIVE says "NO ROLL", you emit ZERO `!`-prefixed commands — not for atmosphere, not for tension, not for flavor, not because the scene "feels like" it should have a roll. Mechanical commands are not decoration. They are state writes. If you find yourself typing `!` for any reason other than copying a directive-quoted command verbatim, stop and rewrite without it. EXCEPTION FOR ATTACKS: when ROLL DIRECTIVE is an attack roll, the quoted command is a TEMPLATE with `<weapon-name>`, `<spell-name>`, and `<target>` placeholders. Replace EVERY `<...>` placeholder with the appropriate value from character context and scene NPCs — do NOT emit the literal `<weapon-name>` or `<target>` text, and do NOT wrap multi-word names in quotes (Avrae uses positional parsing — `!attack unarmed strike -t Garrick` is correct). The `-t <target>` portion is mandatory; bare `!attack` makes Avrae roll against `<No Target>` and the attack vanishes. The attack response must ALSO contain narration of the player's attempt before the command — the command alone with no narrative body is insufficient.
6. PLAYER ATTEMPTS, NOT OUTCOMES. Players declare what they try; the world decides what happens. The player CANNOT author scene physics, NPC reactions, or success conditions through declaration alone.
   (a) OUTCOME DICTATION — If the player narrates the result of an uncertain action ("I take the steering wheel off and leave", "I pick the lock easily", "I convince him to help me"), treat the verbs as ATTEMPTS, not facts. The action's outcome is decided by the ROLL DIRECTIVE and the world, not by the player's wording. Never echo "you manage to" or "the action feels easy" or any phrase that grants success the directive did not authorize. If the directive says NO ROLL but the action is non-trivial, describe the friction (mechanical complexity, time required, who notices) rather than narrating a clean success.
   (b) IMPOSSIBLE ACTIONS — If the player declares a capability the character does not have ("I fly", "I teleport", "I cast a spell I don't know", "I one-shot the dragon"), do NOT silently rewrite the action into something plausible. Interrupt in narration: state directly that the character cannot do this, briefly explain why ("you have no means of flight"), and ask what they want to do instead. Do not invent a workaround for them.
   (c) CONTRADICTING ESTABLISHED SCENE — If the player's declaration contradicts a fact already in scene state (door position, NPC location, object placement, environmental constraint), the SCENE WINS. Describe the friction the contradiction creates ("the door is on the rear-passenger side, not the driver's — you'd have to climb over the console") and let the player adapt. Do not rewrite the scene to match the player's assumption.{arbitration_hardstop_section}{resolution_hardstop_section}"""


def parse_auto_execute(response: str):
    """Strip the AUTO_EXECUTE tail from response and parse Tier 1 actions.

    Returns (cleaned_response, actions) where actions is a list of dicts:
      {'cmd': 'QUEST_ADD'|'CLOCK_TICK'|'MODE', 'args': [...]}
    Invalid lines are dropped silently to the player but logged to engine.
    """
    if 'AUTO_EXECUTE_BEGIN' not in response:
        return response, []

    VALID_MODES = {'exploration', 'combat', 'social', 'travel', 'downtime'}
    actions = []

    try:
        before, tail = response.split('AUTO_EXECUTE_BEGIN', 1)
        # Strip everything from BEGIN onward — including any trailing newlines
        cleaned = before.rstrip()
        # Pull just the lines between BEGIN and END
        if 'AUTO_EXECUTE_END' in tail:
            body = tail.split('AUTO_EXECUTE_END', 1)[0]
        else:
            body = tail  # malformed but try anyway

        for raw_line in body.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            parts = line.split('|')
            cmd = parts[0].upper()

            if cmd == 'QUEST_ADD':
                if len(parts) < 2 or not parts[1].strip():
                    log(f"auto_execute_rejected reason=bad_format target={line!r}")
                    continue
                actions.append({'cmd': 'QUEST_ADD', 'args': [parts[1].strip()]})

            elif cmd == 'CLOCK_TICK':
                if len(parts) < 2 or not parts[1].strip():
                    log(f"auto_execute_rejected reason=bad_format target={line!r}")
                    continue
                name = parts[1].strip()
                try:
                    n = int(parts[2].strip()) if len(parts) >= 3 else 1
                except ValueError:
                    log(f"auto_execute_rejected reason=bad_format target={line!r}")
                    continue
                actions.append({'cmd': 'CLOCK_TICK', 'args': [name, n]})

            elif cmd == 'MODE':
                if len(parts) < 2 or parts[1].strip().lower() not in VALID_MODES:
                    log(f"auto_execute_rejected reason=invalid_mode target={line!r}")
                    continue
                actions.append({'cmd': 'MODE', 'args': [parts[1].strip().lower()]})

            else:
                log(f"auto_execute_rejected reason=unknown_command target={line!r}")

    except Exception as e:
        log(f"parse_auto_execute error: {e}")
        return response, []

    return cleaned, actions


def execute_auto_actions(campaign_id: int, actions: list):
    """Execute validated Tier 1 actions. Returns list of (success, undo_line) tuples.

    Never raises — all errors are caught and logged with structured reasons.
    """
    results = []
    for action in actions:
        cmd = action['cmd']
        args = action['args']
        try:
            if cmd == 'QUEST_ADD':
                title = args[0]
                # S7: dedup against existing active quests. Title comparison is
                # case-insensitive + whitespace-normalized. Defense-in-depth —
                # the prompt rule against re-emitting QUEST_ADD for known
                # quests can be broken by the LLM; this catches it
                # deterministically. Auto-execute scope only; manual /quest add
                # remains unrestricted (DM may deliberately re-add).
                existing_active = get_active_quests(campaign_id)
                norm_new = ' '.join(title.split()).lower()
                duplicate = next(
                    (q for q in existing_active
                     if ' '.join((q.get('title') or '').split()).lower() == norm_new),
                    None
                )
                if duplicate:
                    log(f"auto_execute_rejected reason=duplicate_quest "
                        f"campaign_id={campaign_id} title={title!r} "
                        f"existing_id={duplicate.get('id')}")
                    continue
                quest_id = quest_add(campaign_id, title)
                undo = f"*Quest added: **{title}** (id: {quest_id}) — undo: /quest delete {quest_id}*"
                results.append((True, undo))
                log(f"auto_execute_success cmd=QUEST_ADD campaign_id={campaign_id} quest_id={quest_id} title={title!r}")

            elif cmd == 'CLOCK_TICK':
                name, n = args[0], args[1]
                # Verify clock exists before ticking
                clocks = get_clocks(campaign_id)
                match = next((c for c in clocks if c['name'].lower() == name.lower()), None)
                if match is None:
                    log(f"auto_execute_rejected reason=unknown_clock campaign_id={campaign_id} target={name!r}")
                    continue
                clock_dict, filled, error = clock_tick(campaign_id, match['name'], n)
                if error:
                    log(f"auto_execute_rejected reason=clock_tick_error campaign_id={campaign_id} target={name!r} error={error}")
                    continue
                filled_note = " — **clock filled!**" if filled else ""
                undo = f"*Clock ticked: **{match['name']}** +{n}{filled_note} — undo: /clock tick {match['name']} -{n}*"
                results.append((True, undo))
                log(f"auto_execute_success cmd=CLOCK_TICK campaign_id={campaign_id} name={match['name']!r} n={n}")

            elif cmd == 'MODE':
                mode = args[0]
                # Capture prior mode BEFORE flipping so the undo line names the
                # actual previous state instead of a literal placeholder. The
                # `/mode <choice>` slash command takes the target mode as its
                # arg, so `/mode {prior_mode}` is the exact undo invocation.
                prior_state = get_scene_state(campaign_id)
                prior_mode = (prior_state.get('mode') if prior_state else None) or 'exploration'
                set_scene_mode(campaign_id, mode)
                undo = f"*Mode set: **{mode}** — undo: /mode {prior_mode}*"
                results.append((True, undo))
                log(f"auto_execute_success cmd=MODE campaign_id={campaign_id} "
                    f"mode={mode} prior_mode={prior_mode}")

        except Exception as e:
            log(f"auto_execute_error cmd={cmd} campaign_id={campaign_id} args={args} error={e}")

    return results


def dm_respond(campaign, characters, player_action, avrae_events=None,
                acting_character_names=None, transition_context=None,
                typing_user_id=None, actions: list = None,
                resolution_result=None):
    """Run one DM turn. Returns response string. Roll-or-not decided by
    the orchestration engine, not the prompt.

    actions: structured list of (actor_name, text[, user_id]) tuples from
    ActionBatcher. When provided, arbitrate() is called per-actor. When
    omitted, degrades to single-actor Track 7 #1 behavior using
    player_action (backwards-compatible). Per §1.2 lock.

    acting_character_names: list of character names (deduped, in batch order).
    All resolvable contexts are passed to build_dm_context — single actor
    gets the verbose block, multi-actor gets a compact list (2C.1).

    transition_context: optional structured directive from a transition-
    issuing command (/travel today; /rest, /camp, /downtime later). When
    set, it is injected as a top-priority block in the system prompt,
    overriding normal narration cadence. Treated as authoritative for one
    turn only — not persisted, not retrieved on subsequent turns. The
    durable consequence (e.g. current_location_id) is written by the
    issuing command before dm_respond is called.

    Format expected:
        TRAVEL_TRANSITION:
        origin=...
        destination=...
        elapsed=...
        instruction=...
    """
    scene_state = get_scene_state(campaign['id'])

    # Normalize input. Default to first bound character if no actors specified
    # (preserves prior behavior for the open-scene seed call).
    if acting_character_names is None:
        acting_character_names = []
    if not acting_character_names and characters:
        acting_character_names = [characters[0]['name']]

    # Resolve cached contexts for every acting actor. Misses logged per-actor
    # so the diagnostic reads cleanly for multi-actor batches.
    character_contexts = []
    for name in acting_character_names:
        ctx = orch.get_cached_context(name)
        if ctx is None:
            log(f"dm_respond: no cached context for '{name}' — narrating without sheet data")
        else:
            character_contexts.append(ctx)

    # Roll decision is per-action, not per-actor. Use the primary (first
    # resolved) context. None if nobody resolved.
    primary_ctx = character_contexts[0] if character_contexts else None

    # Mode is authoritative from scene_state. Fall back to 'exploration' only
    # if there is no scene state yet (first turn before /play was called).
    # Do NOT recompute mode from Avrae events — that was the bug.
    mode = (scene_state or {}).get('mode') or 'exploration'

    # Track 7 #2 — Multi-actor arbitration. First orchestration step.
    # Wraps per-actor adjudicate() calls with priority sort + all-pairs
    # conflict detection → ArbitrationResult. Single-actor degenerate case
    # is byte-identical to Track 7 #1. Soft-fails to first-actor-only
    # single adjudicate() on any exception — never blocks narration
    # (Doctrine §59).
    import adjudicator
    import narration_verifier as _nv
    try:
        _adj_skeleton = None
        try:
            from skeleton_loader import get_player_capabilities as _adj_gpc
            _adj_skeleton = _adj_gpc(campaign['id'])
        except Exception:
            _adj_skeleton = {}
        _adj_combatants_payload = get_combatants(campaign['id']) or {}
        _adj_combatants = _adj_combatants_payload.get('combatants') or []
        _adj_active_turn = get_active_turn(campaign['id'])

        # Build the actions list for arbitrate(). When caller passed the
        # structured list, use it. When only combined_action (legacy path),
        # synthesize a single-actor tuple.
        _arb_actions = list(actions) if actions else None
        if not _arb_actions:
            _primary_name = primary_ctx.name if primary_ctx else (
                acting_character_names[0] if acting_character_names else '?'
            )
            _arb_actions = [(_primary_name, player_action or '')]

        arbitration_result = adjudicator.arbitrate(
            actions=_arb_actions,
            scene_state=scene_state,
            characters=characters,
            combatants=_adj_combatants,
            active_turn=_adj_active_turn,
            avrae_events=avrae_events,
            skeleton_capabilities=_adj_skeleton,
            character_cache=orch.get_cached_context,
        )
    except Exception as _arb_e:
        log(f"[ARBITRATION_FALLBACK]: campaign={campaign['id']} error={_arb_e!r}")
        # Fall back to first-actor-only Track 7 #1 single adjudicate()
        try:
            _fallback_verdict = adjudicator.adjudicate(
                player_input=player_action,
                scene_state=scene_state,
                character=primary_ctx,
                combatants=_adj_combatants if '_adj_combatants' in dir() else [],
                active_turn=_adj_active_turn if '_adj_active_turn' in dir() else None,
                avrae_events=avrae_events,
                skeleton_capabilities=_adj_skeleton if '_adj_skeleton' in dir() else {},
            )
        except Exception:
            _fallback_verdict = adjudicator.AdjudicationResult(
                category=adjudicator.FALLBACK,
                allowed=True,
                narration_constraint='',
                signals={'category': 'fallback', 'allowed': 1,
                         'input_preview': (player_action or '')[:140]},
            )
        _fb_actor = primary_ctx.name if primary_ctx else (
            acting_character_names[0] if acting_character_names else '?'
        )
        arbitration_result = adjudicator.ArbitrationResult(
            verdicts=[_fallback_verdict],
            actor_order=[_fb_actor],
            merge_plan='sequence',
            primary_actor=_fb_actor,
            combined_constraint=_fallback_verdict.narration_constraint or '',
            overridden_actors=[],
            signals={'actors': 1, 'verdicts': _fallback_verdict.category,
                     'merge_plan': 'sequence', 'primary_actor': _fb_actor,
                     'overridden_actors': '-', 'priority_order': _fb_actor,
                     'input_total_chars': len(player_action or ''),
                     'input_per_actor': f"{_fb_actor}:{len(player_action or '')}"},
        )

    arbitration_block_text = adjudicator.render_arbitration_block(arbitration_result)
    arbitration_hardstop_text = adjudicator.render_arbitration_hardstop_echo(
        arbitration_result
    )
    log(adjudicator.arbitration_log_summary(arbitration_result, campaign['id']))

    intent = orch.classify_action_intent(player_action, mode=mode)
    roll_decision = orch.should_call_roll(intent, mode, player_action, primary_ctx)

    # Godmode-gap diagnostic (Session 16): when player intent classifies as
    # COMBAT but scene mode isn't combat, the player has narratively committed
    # to a violent action without the system constraining the next move.
    # Log the event so the gap is observable without mutating mode (mode
    # changes are an architecture decision deferred to user review). Used to
    # build the case for "deterministic mode flip on COMBAT intent" or for a
    # committed-action-resolution layer (separate spec).
    if intent == orch.INTENT_COMBAT and mode != 'combat':
        log(f"godmode_gap: campaign={campaign['id']} mode={mode} "
            f"intent={intent} player_action={player_action[:140]!r}")

    # S9 — capability grounding. Specific-item exact-equality matching
    # against (Avrae attacks, skeleton declarations). Skeleton hints
    # are POSITIVE-only — they CONFIRM, never CONTRADICT or block.
    # Mode-independent. Silent on no-claim turns and CONFIRMED outcomes
    # (directive renders empty); soft-annotation directive on
    # VALID_BUT_UNCONFIGURED. INVALID is reserved for future authoritative
    # contradiction sources (DDB, DM override) — unreachable in v1.
    try:
        from skeleton_loader import get_player_capabilities
        skeleton_capabilities = get_player_capabilities(campaign['id'])
    except Exception as e:
        log(f"dm_respond: get_player_capabilities failed: {e}")
        skeleton_capabilities = {}
    capability_decision = orch.check_action_capability(
        player_action, primary_ctx,
        skeleton_capabilities=skeleton_capabilities,
    )
    # Logging policy per spec (locked Session 13): log all non-no-claim
    # outcomes — CONFIRMED via avrae, CONFIRMED via skeleton, and
    # VALID_BUT_UNCONFIGURED. NO_MATCH is the silent no-claim case
    # (needs_check=False) and is not logged.
    if capability_decision.needs_check:
        actor_name = primary_ctx.name if primary_ctx else '?'
        verdict_name = capability_decision.verdict.name
        if capability_decision.verdict is orch.CapabilityVerdict.CONFIRMED:
            source = ('skeleton'
                      if capability_decision.matched_attack.startswith('skeleton-declared:')
                      else 'avrae')
            log(f"capability_check: actor={actor_name} "
                f"claim={capability_decision.capability!r} "
                f"verdict={verdict_name} source={source} "
                f"matched={capability_decision.matched_attack!r}")
        else:
            log(f"capability_check: actor={actor_name} "
                f"claim={capability_decision.capability!r} "
                f"verdict={verdict_name} "
                f"avrae_attacks={primary_ctx.attacks if primary_ctx else []} "
                f"skeleton_keys={list(skeleton_capabilities.keys())}")

    # Pacing directive (Track 3, Session 14). Computes from existing
    # tension_int + progress_clocks. Silent at low tension + no urgent
    # clocks; tier-imperative otherwise. Logged on every non-silent
    # emission so threshold tuning has data.
    pacing_directive_text = orch.compute_pacing_directive(scene_state)
    if pacing_directive_text:
        log(f"pacing_directive: {orch.pacing_log_summary(scene_state)}")

    # Central thread directive (Track 3, Session 14). Reads first
    # authored skeleton hook as the campaign's gravitational pull.
    # Phrasing forbids literal restatement — guards against keyword-
    # spamming. Logged when emitted so we can verify hook-presence
    # across sessions.
    central_thread_text = ""
    try:
        from skeleton_loader import parse_skeleton_file
        parsed_skel = parse_skeleton_file(campaign['id'])
        skeleton_hooks = (parsed_skel or {}).get('hooks') or []
        central_thread_text = orch.compute_central_thread_directive(skeleton_hooks)
        if central_thread_text:
            log(f"central_thread: hook={skeleton_hooks[0]!r} "
                f"(1 of {len(skeleton_hooks)})")
    except Exception as e:
        log(f"dm_respond: central thread directive failed: {e}")

    # DM philosophy (Track 3, Session 14). Global authored doc, mtime-
    # cached. Sits high in prompt (frames how all directives are
    # interpreted). Returns empty string when no doc exists, in which
    # case the prompt block is suppressed entirely.
    philosophy_text = ""
    try:
        from dm_philosophy_loader import get_philosophy_block
        philosophy_text = get_philosophy_block()
        if philosophy_text:
            log(f"dm_philosophy: loaded ({len(philosophy_text)} chars)")
    except Exception as e:
        log(f"dm_respond: philosophy loader failed: {e}")

    # Consequence directive (Track 3, Session 16). Reads active
    # dnd_consequences rows scoped to this turn's NPCs and renders
    # imperative pressure surfacing what the world remembers. Promotion
    # to NPC notable_traits is run BEFORE the directive so promoted rows
    # never re-fire here.
    current_turn = get_turn_counter(campaign['id'])
    consequence_text = ""
    surfaced_consequences = []
    try:
        promoted_count = maybe_promote_consequences(campaign['id'], current_turn)
        if promoted_count:
            log(f"consequence_promotion: campaign={campaign['id']} "
                f"promoted={promoted_count} current_turn={current_turn}")

        # Build the in-scope NPC id set: recently active NPCs ∪ NPCs at
        # the current location. Off-screen NPCs accumulate consequences
        # silently; relevance filter prevents directive spam.
        in_scope_ids = set(
            get_recently_active_npc_ids(campaign['id'], limit=6)
        )
        current_loc = (scene_state or {}).get('current_location_id')
        if current_loc:
            in_scope_ids.update(get_npc_ids_at_location(campaign['id'], current_loc))

        if in_scope_ids:
            active_cons = get_active_consequences(
                campaign['id'], npc_ids=list(in_scope_ids)
            )
            consequence_text, surfaced_consequences = (
                orch.compute_consequence_directive(active_cons, in_scope_ids)
            )
            if surfaced_consequences:
                log(f"consequence_directive: campaign={campaign['id']} "
                    f"current_turn={current_turn} "
                    f"{orch.consequence_log_summary(surfaced_consequences)}")
                # Single-write-path on directive emit: increment surface
                # counters for each row that actually appeared in the
                # composed block. Done here (sync) so promotion thresholds
                # advance in lockstep with what the LLM saw.
                for c in surfaced_consequences:
                    consequence_emit_surface(c['id'], current_turn)
    except Exception as e:
        log(f"dm_respond: consequence directive failed: {e}")

    # Committed-action resolution directive (Track 3, Session 19). Detects
    # the godmode-escape failure mode: COMBAT-intent prior turn + scene-shift
    # current turn + no Avrae mechanical resolution + no narrative reaction-
    # verb resolution + no explicit retraction → fire imperative directive
    # demanding the LLM resolve, refuse, or charge for the new action.
    # Per locked §11.1 (COMBAT-only), §11.2 (regex resolution), §11.3
    # (recompute prior intent), §11.7 (read prior DM response from
    # scene_state), §11.B (target hints from recently_active ∪ at_location),
    # §11.D (retraction grammar in v1).
    commitment_text = ""
    commitment_signals = {}
    try:
        prior_action_text = (scene_state or {}).get('last_player_action') or ''
        intent_prior = (
            orch.classify_action_intent(prior_action_text, mode=mode)
            if prior_action_text else 'unknown'
        )
        avrae_kinds_resolved = {'attack', 'cast', 'damage'}
        avrae_resolved = any(
            ev.get('kind') in avrae_kinds_resolved
            for ev in (avrae_events or [])
        )
        prior_dm_response = (scene_state or {}).get('last_dm_response') or ''
        # Target hints: recently active NPCs ∪ NPCs at current location.
        # Same scoping rule as the consequence directive (§11.B).
        target_hint_set = set(
            get_recently_active_npcs(campaign['id'], limit=6)
        )
        if current_loc:
            target_hint_set.update(
                get_npc_names_at_location(campaign['id'], current_loc)
            )
        commitment_text, commitment_signals = orch.compute_commitment_directive(
            intent_prior=intent_prior,
            intent_current=intent,
            current_action_text=player_action,
            prior_action_text=prior_action_text,
            avrae_resolved_since_prior=avrae_resolved,
            prior_dm_response=prior_dm_response,
            prior_target_hints=list(target_hint_set),
        )
    except Exception as e:
        log(f"dm_respond: commitment directive failed: {e}")

    # Init directive (Track 3 / Combat Initiation Orchestration v1, Session 20).
    # Detects COMBAT intent in non-combat mode with no active init tracker.
    # When all three gates pass, extends the ROLL DIRECTIVE block with a
    # three-command emission sequence: !init begin, !init add <target>,
    # !attack -t <target>. Pure function — no state mutation. Mode flip
    # stays on the existing reactive _handle_init_event path (§11.2 locked).
    init_body = ""
    init_signals = {}
    try:
        _init_loc = (scene_state or {}).get('current_location_id')
        _init_hint_set = set(get_recently_active_npcs(campaign['id'], limit=6))
        if _init_loc:
            _init_hint_set.update(
                get_npc_names_at_location(campaign['id'], _init_loc)
            )
        init_body, init_signals = orch.compute_init_directive(
            intent_current=intent,
            mode=mode,
            has_active_turn=(get_active_turn(campaign['id']) is not None),
            target_hints=sorted(_init_hint_set),
        )
    except Exception as e:
        log(f"dm_respond: init directive failed: {e}")

    # Persistence directive (Track 3 / Combat Persistence Directive v1, Session 21).
    # Three composed sub-pressures (enemy persistence, condition awareness,
    # initiative-order confirm) rendered from the !init list snapshot.
    # Master gate: mode == 'combat'. Per §11.B retroactive lock, OFF-turn
    # rendering is dropped — Phase 2A.3 catches off-turn messages upstream.
    persistence_text = ""
    persistence_signals = {}
    try:
        _active_turn = get_active_turn(campaign['id'])
        _combatants_snapshot = get_combatants(campaign['id'])
        _typing_char = (
            acting_character_names[0] if acting_character_names else None
        )
        persistence_text, persistence_signals = orch.compute_persistence_directive(
            mode=mode,
            active_turn=_active_turn,
            combatants_snapshot=_combatants_snapshot,
            typing_user_id=str(typing_user_id) if typing_user_id else None,
            typing_character_name=_typing_char,
        )
    except Exception as e:
        log(f"dm_respond: persistence directive failed: {e}")

    # Loot directive (Track 4 #2, Session 22) — surfaces creatures defeated
    # since the last narration turn (detected via alive=1 -> alive=0 transition
    # in update_combatants_from_init_list). Pure read here; surface-and-clear
    # happens AFTER the LLM call succeeds so a failed call leaves loot pending.
    loot_text = ""
    loot_signals = {}
    pending_loot_rows: list[dict] = []
    try:
        pending_loot_rows = get_pending_loot(campaign['id'])
        loot_text, loot_signals = orch.compute_loot_directive(pending_loot_rows)
    except Exception as e:
        log(f"dm_respond: loot directive failed: {e}")
        pending_loot_rows = []
        loot_text = ""
        loot_signals = {}

    # Combat redirect directive (Track 6 #2, Session 23) — informational
    # pressure when on-turn player narration in active combat may attempt
    # to bypass combat reality. Companion to S19's commitment directive
    # (escape-intent only); fires on every PC on-turn narration in
    # combat with alive enemies. Hard refusal lives in 2A.3 off-turn
    # gate; this is explanatory. Pure orch call; on exception the
    # directive is dropped and narration still posts. Re-reads active
    # turn + combatants snapshot directly — cheap SQLite reads, avoids
    # state-leak from the persistence-directive scope above.
    redirect_text = ""
    redirect_signals = {}
    try:
        _redirect_active_turn = get_active_turn(campaign['id'])
        _redirect_snapshot = get_combatants(campaign['id'])
        _redirect_typing_char = (
            acting_character_names[0] if acting_character_names else None
        )
        _redirect_combatants_list = (
            (_redirect_snapshot or {}).get('combatants') or []
        )
        redirect_text, redirect_signals = orch.compute_combat_redirect_directive(
            scene_state=scene_state,
            active_turn=_redirect_active_turn,
            combatants=_redirect_combatants_list,
            bound_character_name=_redirect_typing_char,
        )
    except Exception as e:
        log(f"dm_respond: redirect directive failed: {e}")
        import traceback
        log(f"[REDIRECT_FAILED] {traceback.format_exc()}")
        redirect_text = ""
        redirect_signals = {}

    # Time directive (Track 4 #3, Session 27) — recency-gated on
    # dnd_time_advancements per §11.E sub-(iii)α. Fires only on the
    # turn immediately following an advancement; '' on every other
    # turn. Soft-fail: directive is dropped silently on exception so
    # narration still posts.
    time_text = ""
    try:
        _just_advanced = time_just_advanced(campaign['id'])
        time_text = orch.compute_time_directive(scene_state, _just_advanced)
    except Exception as e:
        log(f"dm_respond: time directive failed: {e}")
        time_text = ""

    scene_blurb = (campaign.get('current_scene') or '')[:200]
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

    current_tension = (scene_state or {}).get('tension_int', 0)
    has_damage = any(ev.get('damage') is not None for ev in (avrae_events or []))
    new_tension = calculate_tension_shift(
        current_tension, avrae_events or [], no_damage_turn=not has_damage
    )
    if new_tension != current_tension and scene_state:
        update_tension(campaign['id'], new_tension)
        scene_state = dict(scene_state)
        scene_state['tension_int'] = new_tension

    # §11.L deduplication — silence sibling directives whose surface is
    # already covered by arbitration's primary verdict. Capability surface:
    # when the primary verdict is CAPABILITY_ACTION (allowed or refused),
    # its narration_constraint subsumes the S9 advisory. Combat surface:
    # when primary verdict is COMBAT_ACTION, combat_redirect is silent.
    _primary_verdict = (arbitration_result.verdicts[0]
                        if arbitration_result.verdicts else None)
    if _primary_verdict and _primary_verdict.category == adjudicator.CAPABILITY_ACTION:
        capability_decision = None
    if _primary_verdict and _primary_verdict.category == adjudicator.COMBAT_ACTION:
        redirect_text = ""

    relevant = chroma_search(campaign['id'], player_action)
    if USE_KNOWLEDGE_GUIDANCE:
        guidance = multi_query_knowledge_search(
            player_action, intent, scene_blurb, avrae_summary
        )
    else:
        guidance = ""

    # Ship 1 (S34) — render the AUTHORITATIVE-CANON resolution block when
    # the matcher auto-fired with a resolved directive. Both helpers return
    # '' on None; build_dm_context section-assembly handles the empty case.
    resolution_block_text = orch.render_resolution_block(resolution_result)
    resolution_hardstop_text = orch.render_resolution_hardstop_echo(resolution_result)

    system = build_dm_context(
        campaign, characters,
        relevant_history=relevant,
        dm_guidance=guidance,
        action_type=intent,
        avrae_events=avrae_events,
        character_contexts=character_contexts,
        roll_decision=roll_decision,
        capability_decision=capability_decision,
        mode=mode,
        scene_state=scene_state,
        pacing_directive=pacing_directive_text,
        central_thread_directive=central_thread_text,
        philosophy_block=philosophy_text,
        consequence_directive=consequence_text,
        commitment_directive=commitment_text,
        init_directive=init_body,
        persistence_directive=persistence_text,
        loot_directive=loot_text,
        combat_redirect=redirect_text,
        time_directive=time_text,
        arbitration_block=arbitration_block_text,
        arbitration_hardstop_echo=arbitration_hardstop_text,
        resolution_block=resolution_block_text,
        resolution_hardstop_echo=resolution_hardstop_text,
        acting_character_names=acting_character_names,
    )
    # S24: save build_dm_context output size before skeleton/transition prepends.
    _build_chars = len(system)

    # Authored canon (Phase 12C.3) — prepend the skeleton block. This is
    # the highest-priority world-grounding context. Authoritative over
    # parser-detected entities (skeleton_origin=1 always wins). Cached by
    # mtime in skeleton_loader so per-turn cost is sub-millisecond when
    # the file hasn't changed.
    try:
        from skeleton_loader import get_skeleton_prompt_block
        skeleton_block = get_skeleton_prompt_block(campaign['id'])
    except Exception as e:
        log(f"dm_respond: skeleton block build failed: {e}")
        skeleton_block = ""
    if skeleton_block:
        system = skeleton_block + "\n\n" + system

    # Transition directive (if any) takes priority over normal narration
    # cadence. Prepended to the system prompt with explicit framing so the
    # LLM treats it as an authoritative scene-transition instruction, not
    # retrievable context. Only applies to this turn — caller is responsible
    # for any persistent state changes (e.g. current_location_id).
    if transition_context:
        system = (
            "═══════════════════════════════════════════════════════════════\n"
            "AUTHORITATIVE SCENE TRANSITION — HIGHEST PRIORITY\n"
            "═══════════════════════════════════════════════════════════════\n"
            "The following transition has ALREADY OCCURRED. Do NOT narrate\n"
            "the journey, the road, intervening events, or anything between\n"
            "origin and destination. Begin your narration AT ARRIVAL with a\n"
            "single, atmospheric scene-setting beat at the destination, then\n"
            "hand agency back to the player.\n\n"
            f"{transition_context.strip()}\n"
            "═══════════════════════════════════════════════════════════════\n\n"
            + system
        )

    # DIAG: knowledge corpus + prompt size visibility (Session 10).
    # Tells us whether the 740k CRD3+FIREBALL corpus is contributing
    # exemplars in this campaign's tone, and how big the assembled prompt
    # is (relevant for whether HARD STOP RULES at the end are getting
    # buried in attention). Remove once we've decided on USE_KNOWLEDGE_GUIDANCE.
    _exemplars = [e for e in (guidance or "").split("\n\n") if e.strip()]
    log(f"dnd guidance: {len(guidance or '')} chars, {len(_exemplars)} exemplars")
    log(f"dnd prompt total: {len(system)} chars")

    # S24: per-turn prompt size telemetry — section breakdown so over-sized
    # sections are identifiable before they start burying the HARD STOP RULES.
    # 'system' = build_dm_context output (before skeleton/transition prepend).
    # 'total'  = final prompt size (after all prepends).
    # Section sizes are computed from the input variables that feed each block.
    _retrieval_chars = len(relevant or '') + len(guidance or '')
    _party_chars = (
        sum(len(c.to_prompt_block()) for c in character_contexts)
        if character_contexts else 0
    )
    _scene_chars = 0
    if scene_state:
        for _k in ('location', 'focus', 'last_player_action', 'last_scene_change'):
            _scene_chars += len(str(scene_state.get(_k) or ''))
        for _lst in (
            scene_state.get('established_details') or [],
            scene_state.get('open_questions') or [],
            scene_state.get('progress_clocks') or [],
        ):
            if isinstance(_lst, list):
                _scene_chars += sum(len(str(x)) for x in _lst)
    _directive_chars = (
        len(pacing_directive_text) +
        len(central_thread_text) +
        len(consequence_text) +
        len(philosophy_text) +
        len(commitment_text) +
        len(init_body) +
        len(persistence_text) +
        len(loot_text) +
        len(redirect_text)
    )
    log(f"prompt_size: campaign={campaign['id']} "
        f"system={_build_chars} retrieval={_retrieval_chars} "
        f"party={_party_chars} scene={_scene_chars} "
        f"directives={_directive_chars} total={len(system)}")

    # S25: per-turn directive emission summary. Aggregates which directives
    # fired with non-empty content so threshold calibration has a single
    # per-turn signal alongside the existing per-directive log lines.
    # pacing={tier} — tier name (mounting/dangerous/climax) when fired, 'none' when silent.
    # central_thread={1|0} — 1 when a skeleton hook exists and text was emitted.
    # philosophy={chars} — byte count of the loaded philosophy block (0 when unloaded).
    # consequence={count} — number of consequences that appeared in the directive.
    # capability={verdict|none} — verdict name when a claim was checked, 'none' on no-claim turns.
    # commitment={1|0} — 1 when commitment directive fired (godmode-escape detected).
    # init={1|0} — 1 when init directive fired (COMBAT intent, non-combat mode, no active turn).
    if pacing_directive_text:
        _pacing_tension = int((scene_state or {}).get('tension_int') or 0)
        _pacing_tier_log = orch._pacing_tier(_pacing_tension)
    else:
        _pacing_tier_log = 'none'
    _cap_log = (
        capability_decision.verdict.name
        if (capability_decision and capability_decision.needs_check)
        else 'none'
    )
    _commitment_fired = int(bool(commitment_signals.get('fired')))
    _init_fired = int(bool(init_signals.get('fired')))
    _persistence_fired = int(bool(persistence_signals.get('fired')))
    _loot_fired = int(bool(loot_signals.get('fired')))
    _redirect_fired = int(bool(redirect_signals.get('fired')))
    _time_fired = 1 if time_text else 0
    global _hydration_wrote_this_turn
    _hydration_write_fired = int(_hydration_wrote_this_turn)
    _hydration_wrote_this_turn = False
    log(f"directive_emit: campaign={campaign['id']} "
        f"pacing={_pacing_tier_log} "
        f"central_thread={1 if central_thread_text else 0} "
        f"philosophy={len(philosophy_text)} "
        f"consequence={len(surfaced_consequences)} "
        f"capability={_cap_log} "
        f"commitment={_commitment_fired} "
        f"init={_init_fired} "
        f"persistence={_persistence_fired} "
        f"loot={_loot_fired} "
        f"redirect={_redirect_fired} "
        f"time={_time_fired} "
        f"hydration_write_fired={_hydration_write_fired}")

    # Per-turn commitment_directive: log line. Fires every turn (not just
    # when the directive emits) so the empirical baseline of gate hit
    # rates is observable. See `Why godmode_gap ships before any
    # constraint layer` for the diagnostic-baseline doctrine.
    log(f"commitment_directive: campaign={campaign['id']} "
        f"{orch.commitment_log_summary(commitment_signals)}")
    # Retraction-filter diagnostic: fires only when retraction grammar
    # suppressed an otherwise-firing directive. Per §11.D doctrine
    # (`Why this ship is fix+diagnostic together`) — measure how often
    # the retraction filter fires vs. expected so future tuning has data.
    if commitment_signals.get('retraction_filtered'):
        log(f"commitment_retraction_filtered: campaign={campaign['id']} "
            f"text={(player_action or '')[:80]!r}")

    # Per-turn init_directive: log line. Fires every turn (not just when
    # the directive emits) so the empirical baseline of gate hit rates is
    # observable. Mirrors commitment_directive: shape. See §6.3 / §11.11.
    log(f"init_directive: campaign={campaign['id']} "
        f"{orch.init_log_summary(init_signals)}")

    # Per-turn persistence_directive: log line. Fires every turn — surfaces
    # snapshot freshness (snapshot_age_s), data-layer signals (hp_known,
    # conditions_known, combatants), and active-turn controller. See
    # COMBAT_PERSISTENCE_DIRECTIVE_SPEC.md §6.3.
    log(f"persistence_directive: campaign={campaign['id']} "
        f"{orch.persistence_log_summary(persistence_signals)}")

    # Per-turn loot_directive: log line (Track 4 #2). Fires every turn so the
    # empirical baseline of pending-queue depth is observable.
    log(f"loot_directive: campaign={campaign['id']} "
        f"{orch.loot_log_summary(loot_signals)}")

    # Per-turn combat_redirect: log line (Track 6 #2). Fires every turn so
    # the empirical baseline of gate hit rates is observable — answers
    # "how often does the redirect actually fire vs. gate out at
    # gate_mode/gate_no_enemies/gate_npc_turn?" Pre-friends visibility
    # for whether this directive is doing real work.
    log(f"combat_redirect: campaign={campaign['id']} "
        f"{orch.combat_redirect_log_summary(redirect_signals)}")

    try:
        response, _ = route(
            messages=[{"role": "user", "content": player_action}],
            task_type="dnd",
            system_prompt=system,
        )
        # Empty-narration diagnostic (Session 16). Jordan flagged a turn
        # where the bot posted only a footer with no narration text. If
        # the LLM returned empty/whitespace OR everything was AUTO_EXECUTE
        # tail (which gets stripped by parse_auto_execute), surface that
        # explicitly so the failure mode is observable instead of silent.
        # Pre-clean check; the post-clean check fires below after parse_auto_execute.
        if not response or not response.strip():
            log(f"dm_respond: EMPTY response from LLM "
                f"campaign={campaign['id']} mode={mode} intent={intent} "
                f"prompt_chars={len(system)}")
            # S26 follow-up: measure how often commitment directive + empty
            # response co-occur. High rate → commitment prompt bloat implicated.
            # Low rate → empty narration has a different root. Fires ONLY when
            # both conditions hold; silent on non-empty turns (§39 baseline).
            if _commitment_fired:
                log(f"commitment_empty_response: campaign={campaign['id']} "
                    f"prompt_chars={len(system)} fired=1 "
                    f"directive_chars={len(commitment_text)}")

        # Track 7 #2 — Post-LLM verification pass. verify_narration checks
        # the response against the bound ArbitrationResult and canonical
        # state sources. On violation: one retry with === VERIFICATION FAILED
        # === prepended (same system prompt). On second violation: deterministic
        # escalation placeholder. Soft-fail at every boundary (Doctrine §59).
        _vfy_result = None
        _retry_result = None
        _vfy_escalated = False
        try:
            _adj_combatants_for_vfy = (
                getattr(arbitration_result, '_combatants_snapshot', None)
                or _adj_combatants if '_adj_combatants' in dir() else []
            )
            # Pull canonical NPC names for fabrication detection
            try:
                _canonical_npc_names = []
                _vfy_npc_rows = npc_list(campaign['id'])
                _canonical_npc_names = [
                    r.get('canonical_name') or r.get('name') or ''
                    for r in (_vfy_npc_rows or [])
                    if r.get('canonical_name') or r.get('name')
                ]
            except Exception:
                _canonical_npc_names = []

            _vfy_result = _nv.verify_narration(
                narration_text=response or '',
                arbitration_result=arbitration_result,
                scene_state=scene_state,
                combatants=_adj_combatants if '_adj_combatants' in dir() else [],
                npcs_canonical=_canonical_npc_names,
                resolution_result=resolution_result,
            )

            if not _vfy_result.passed:
                # One retry: prepend === VERIFICATION FAILED === to system prompt
                _retry_prefix = _nv.build_verification_retry_prefix(_vfy_result)
                _retry_system = _retry_prefix + system
                try:
                    _retry_response, _ = route(
                        messages=[{"role": "user", "content": player_action}],
                        task_type="dnd",
                        system_prompt=_retry_system,
                    )
                    _retry_result = _nv.verify_narration(
                        narration_text=_retry_response or '',
                        arbitration_result=arbitration_result,
                        scene_state=scene_state,
                        combatants=_adj_combatants if '_adj_combatants' in dir() else [],
                        npcs_canonical=_canonical_npc_names,
                        resolution_result=resolution_result,
                    )
                    if _retry_result.passed and _retry_response and _retry_response.strip():
                        response = _retry_response
                    else:
                        # Both passes failed — escalation placeholder
                        _vfy_escalated = True
                        _escalation = _nv.build_escalation_placeholder(
                            arbitration_result,
                            failed_violation_class=(
                                (_retry_result.violation_class
                                 if _retry_result else _vfy_result.violation_class)
                                or ''
                            ),
                            resolution_result=resolution_result,
                        )
                        if _escalation and _escalation.strip():
                            response = _escalation
                        log(f"[VERIFICATION_ESCALATED]: campaign={campaign['id']} "
                            f"initial_class={_vfy_result.violation_class} "
                            f"retry_class={(_retry_result.violation_class if _retry_result else '?')}")
                except Exception as _retry_e:
                    log(f"verification_retry error: campaign={campaign['id']} "
                        f"error={_retry_e!r}")
                    _vfy_escalated = True

            log(_nv.verification_log_summary(
                campaign_id=campaign['id'],
                result=_vfy_result,
                retry_fired=(_vfy_result is not None and not _vfy_result.passed),
                retry_result=_retry_result,
                escalated=_vfy_escalated,
            ))
        except Exception as _vfy_e:
            # Fail-open: verification error → treat as passed, post original
            log(f"[VERIFICATION_FALLBACK]: campaign={campaign['id']} error={_vfy_e!r}")
            # Emit a minimal verification log line even on fallback
            log(f"verification: campaign={campaign['id']} "
                f"passed=1 violation_class=none detected='' "
                f"retry_fired=0 retry_passed=- escalated=0 "
                f"narration_chars={len(response or '')} "
                f"canonical_combatants_count=0")

        # Loot surface-and-clear (Track 4 #2). Mark pending rows surfaced
        # ONLY after the LLM call returned a meaningful response. A failed
        # or empty call leaves loot pending for next turn so the directive
        # re-fires. Marks happen regardless of whether the LLM actually
        # narrated the loot — it had the directive in the prompt; we don't
        # second-guess the narrative outcome.
        if (loot_signals.get('fired')
                and response and response.strip()
                and pending_loot_rows):
            try:
                surfaced_n = 0
                for _row in pending_loot_rows:
                    rid = _row.get('id')
                    if rid is not None:
                        mark_loot_surfaced(rid)
                        surfaced_n += 1
                log(f"loot_surfaced: campaign={campaign['id']} count={surfaced_n}")
            except Exception as ex:
                log(f"loot surface-and-clear error: {ex}")
        try:
            threading.Thread(
                target=extract_scene_updates,
                args=(campaign['id'], player_action, response),
                daemon=True,
            ).start()
        except Exception as e:
            log(f"scene update thread launch failed: {e}")

        # Consequence capture (Session 16) — dual-pass advisory parser.
        # Player pass reads player_text; DM pass reads response. Both
        # write through apply_consequence_proposals at the engine layer.
        # Capture turn is the CURRENT turn (pre-increment), so first_seen_turn
        # for new rows aligns with the turn the player just played.
        def _capture_player_consequences():
            try:
                from consequence_extractor import parse_consequences_player
                proposals = parse_consequences_player(
                    player_action, campaign_id=campaign['id'],
                )
                if proposals:
                    # narration_text=response feeds the introduction-race
                    # diagnostic — distinguishes NPC-being-introduced-this-turn
                    # from genuinely off-canon target.
                    result = apply_consequence_proposals(
                        campaign['id'], proposals,
                        source='player', current_turn=current_turn,
                        narration_text=response,
                    )
                    log(f"consequence_apply: campaign={campaign['id']} "
                        f"source=player inserted={result['inserted']} "
                        f"updated={result['updated']} "
                        f"rejected={result['rejected']} "
                        f"reasons={result['reasons']}")
            except Exception as ex:
                log(f"consequence_capture player error: {ex}")

        def _capture_dm_consequences():
            try:
                from consequence_extractor import parse_consequences_dm
                proposals = parse_consequences_dm(response)
                if proposals:
                    result = apply_consequence_proposals(
                        campaign['id'], proposals,
                        source='dm', current_turn=current_turn,
                        narration_text=response,
                    )
                    log(f"consequence_apply: campaign={campaign['id']} "
                        f"source=dm inserted={result['inserted']} "
                        f"updated={result['updated']} "
                        f"rejected={result['rejected']} "
                        f"reasons={result['reasons']}")
            except Exception as ex:
                log(f"consequence_capture dm error: {ex}")

        try:
            threading.Thread(
                target=_capture_player_consequences, daemon=True,
            ).start()
            threading.Thread(
                target=_capture_dm_consequences, daemon=True,
            ).start()
        except Exception as e:
            log(f"consequence capture thread launch failed: {e}")
        try:
            if response and "Suggested Actions:" in response:
                lines = response.split("Suggested Actions:", 1)[1].splitlines()
                count = sum(1 for ln in lines if ln.strip().startswith("- /"))
                log(f"suggestion_emitted campaign_id={campaign['id']} count={count}")
        except Exception as e:
            log(f"suggestion log failed: {e}")

        # Phase 3.1 — auto-execute Tier 1 structural changes
        try:
            cleaned, actions = parse_auto_execute(response)
            if actions:
                log(f"auto_execute_attempted campaign_id={campaign['id']} count={len(actions)}")
                results = execute_auto_actions(campaign['id'], actions)
                undo_lines = [undo for success, undo in results if success]
                if undo_lines:
                    # Insert undo lines between prose and Suggested Actions block
                    undo_block = "\n".join(undo_lines)
                    if "Suggested Actions:" in cleaned:
                        parts = cleaned.split("Suggested Actions:", 1)
                        cleaned = parts[0].rstrip() + "\n" + undo_block + "\n\nSuggested Actions:" + parts[1]
                    else:
                        cleaned = cleaned + "\n" + undo_block
            response = cleaned
        except Exception as e:
            log(f"auto_execute pipeline error: {e}")

        # Post-clean empty-narration diagnostic. If the LLM emitted
        # primarily AUTO_EXECUTE / Suggested-Actions content with no real
        # narration, parse_auto_execute strips the tail, leaving empty or
        # near-empty text. Discord still posts the embed with footer, but
        # the player sees no narration. Surface this explicitly.
        if response is None or len(response.strip()) < 10:
            log(f"dm_respond: cleaned response too short to narrate "
                f"campaign={campaign['id']} cleaned_len={len(response or '')!r} "
                f"mode={mode} intent={intent}")

        # Persist the cleaned narration as last_dm_response so the next
        # turn's compute_commitment_directive can read it for the
        # reaction-verb resolution check (Session 19). Single writer is
        # update_last_dm_response. Written AFTER auto_execute cleanup
        # because that's the form the player actually sees, and BEFORE
        # the turn counter increments so the row reflects "the prior
        # turn's DM response" relative to the next turn.
        try:
            update_last_dm_response(campaign['id'], response or '')
        except Exception as e:
            log(f"last_dm_response write failed: {e}")

        # Advance turn counter at the END of a successful turn. Capture
        # threads spawned above already hold `current_turn` via closure,
        # so their writes target the turn that just finished, not the
        # next turn that this increment is preparing for.
        try:
            increment_turn_counter(campaign['id'])
        except Exception as e:
            log(f"turn_counter increment failed: {e}")

        return response
    except Exception as e:
        log(f"dm_respond error: {e}")
        return f"DM error: {e}"
