"""skeleton_writer.py — N-10 Canon Bootstrap Bot v0 single writer for
skeleton.md file appends.

Per CANON_BOOTSTRAP_BOT_V0_SPEC.md §1.G + §11.7 (LOCKED).

This is a NEW first-of-its-kind writer for the skeleton.md file. §17 narrow-
exception not invoked because no prior writer existed for this file (it was
hand-authored only before N-10).

Public API:
    skeleton_md_append_element(campaign_id, element_type, element_data)
        → tuple[bool, str]   # (success, status_message)

Element types: 'faction', 'npc', 'quest', 'quest_act', 'location'.

Behavior:
    - Soft-fail: file errors do NOT raise; return (False, error_msg).
    - Idempotent on (element_type, element_name): re-append updates the
      existing H3 entry's prose in place rather than duplicating.
    - Creates the parent H2 section if not present (e.g., first faction
      card creates `## Factions`).
    - Output shape compatible with skeleton_loader's `_parse_skeleton_text`
      parser (R2 recon evidence): H2 from recognized vocabulary, H3 entries
      with `### Name (kind, parent_hint)` format, free-form prose under each.

Hard invariants:
    - Single writer for skeleton.md file (the operator hand-edited it before
      N-10; that's now operator-driven external edits, not engine writes).
    - File-write failure NEVER blocks bootstrap session state; the canonical-
      table write is the authoritative side per §1.G.
"""

import re
from pathlib import Path

from dnd_engine import log

SKELETON_ROOT = Path("/home/jordaneal/scripts/campaigns")


# H2 section vocabulary — per skeleton_loader's _NPC_SECTIONS / etc.
# Bot writes to the CANONICAL section name (first in each set):
_H2_NAME_BY_ELEMENT_TYPE = {
    'faction':   '## Factions',
    'npc':       '## Primary NPCs',
    'quest':     '## Major hooks',
    'quest_act': '## Major hooks',   # acts live under quest H3 inside hooks
    'location':  '## Key locations',
}


def _skeleton_path(campaign_id: int) -> Path:
    return SKELETON_ROOT / str(campaign_id) / "skeleton.md"


def _ensure_skeleton_exists(campaign_id: int, campaign_name: str = '',
                             premise: str = '') -> Path:
    """Ensure skeleton.md exists for this campaign. Creates parent dir and
    a minimal H1+premise scaffold if file is missing. Idempotent."""
    path = _skeleton_path(campaign_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        title = (campaign_name or f"Campaign {campaign_id}").strip()
        scaffold_lines = [f"# Campaign: {title}", ""]
        if premise.strip():
            scaffold_lines += ["## Central conflict", premise.strip(), ""]
        path.write_text("\n".join(scaffold_lines), encoding="utf-8")
        log(f"skeleton_md_append: campaign={campaign_id} created_scaffold path={path}")
    return path


def _render_element(element_type: str, data: dict) -> str:
    """Render a single H3 element block as structured markdown per
    skeleton_loader parser expectations.

    Returns the multi-line block including the H3 header and prose body.
    Caller is responsible for placement (which H2 section to append under).
    """
    name = (data.get('name') or data.get('canonical_name')
            or data.get('title') or data.get('act_title') or '').strip()
    if not name:
        return ''

    if element_type == 'faction':
        kind = (data.get('type') or 'faction').strip()
        h3 = f"### {name} ({kind})"
        # Render structured fields as labeled prose lines (parser-permissive)
        body_lines = []
        if data.get('description'):
            body_lines.append(data['description'].strip())
        if data.get('goal'):
            body_lines.append(f"Goal: {data['goal'].strip()}")
        if data.get('pressure_shape'):
            body_lines.append(f"Pressure: {data['pressure_shape'].strip()}")
        if data.get('engagement_signals'):
            body_lines.append(f"Engagement signals: {data['engagement_signals'].strip()}")
        body = "\n".join(body_lines)
        return f"{h3}\n{body}\n"

    if element_type == 'npc':
        role = (data.get('role') or '').strip()
        location_hint = (data.get('location_name') or data.get('location_hint') or '').strip()
        # Parser expects "### Name (kind, parent_hint)" or "### Name (kind)"
        if role and location_hint:
            h3 = f"### {name} ({role}, {location_hint})"
        elif role:
            h3 = f"### {name} ({role})"
        else:
            h3 = f"### {name}"
        # Description must include pronouns in first sentence per §11.9 lock —
        # bot-side discipline; we just render whatever the bot produced.
        body = (data.get('description') or '').strip()
        return f"{h3}\n{body}\n"

    if element_type == 'quest':
        # Quest H3 inside ## Major hooks per Composition Layer §6 + R2.
        h3 = f"### {name}"
        body_lines = []
        if data.get('summary'):
            body_lines.append(data['summary'].strip())
        if data.get('offer_npc_name'):
            body_lines.append(f"Voicer: {data['offer_npc_name'].strip()}")
        if data.get('reward_summary'):
            body_lines.append(f"Reward: {data['reward_summary'].strip()}")
        if data.get('associated_faction_name'):
            body_lines.append(f"Faction: {data['associated_faction_name'].strip()}")
        body = "\n".join(body_lines)
        return f"{h3}\n{body}\n"

    if element_type == 'quest_act':
        # Acts render under the parent quest's H3 inside a `#### Acts`
        # subsection. The append logic (below) handles placement.
        # Here we render just the act line + body per the parser's
        # "N. <Act title>" pattern + indented description.
        act_index = data.get('act_index') or 1
        act_title = (data.get('act_title') or '').strip()
        body_lines = [f"{act_index}. {act_title}"]
        if data.get('act_description'):
            for line in data['act_description'].strip().splitlines():
                body_lines.append(f"   {line}")
        pred = data.get('transition_predicate') or {}
        if pred.get('scene_count_threshold'):
            body_lines.append(f"   Scene count threshold: {pred['scene_count_threshold']}")
        if pred.get('location_name'):
            body_lines.append(f"   Location: {pred['location_name']}")
        return "\n".join(body_lines) + "\n"

    if element_type == 'location':
        loc_type = (data.get('type') or '').strip()
        parent = (data.get('parent_location_name') or data.get('parent_hint') or '').strip()
        if loc_type and parent:
            h3 = f"### {name} ({loc_type} in {parent})"
        elif loc_type:
            h3 = f"### {name} ({loc_type})"
        else:
            h3 = f"### {name}"
        body_lines = []
        if data.get('description'):
            body_lines.append(data['description'].strip())
        if data.get('starting_location'):
            body_lines.append("Starting location for the party.")
        body = "\n".join(body_lines)
        return f"{h3}\n{body}\n"

    return ''


_RE_H2 = re.compile(r"^##\s+(.*?)\s*$")
_RE_H3 = re.compile(r"^###\s+(.*?)\s*$")
_RE_H4 = re.compile(r"^####\s+(.*?)\s*$")


def _replace_or_append_h3(text: str, h2_section: str, element_block: str,
                           element_name: str) -> str:
    """Place an H3 element block under a named H2 section.

    Idempotency:
      - If an H3 with the same canonical name already exists under the H2,
        replace its body in place (preserving order).
      - If the H2 section doesn't exist, append it at end-of-file with the
        new H3 entry.
      - If the H2 exists but no matching H3, append the new H3 entry to the
        end of that H2 section (before the next H2).

    `h2_section` is the full H2 header line (e.g., '## Factions').
    `element_block` is the rendered H3 + body (multi-line, ends with \\n).
    `element_name` is the canonical name to match against existing H3s.
    """
    lines = text.splitlines()
    h2_target = h2_section.strip().lower()
    name_target = element_name.strip().lower()

    # Find the H2 section's line range
    h2_start = None
    h2_end = None  # exclusive: first line after this section (next H2 or EOF)
    for i, ln in enumerate(lines):
        m_h2 = _RE_H2.match(ln)
        if m_h2:
            header = ln.strip().lower()
            if h2_start is None and header == h2_target:
                h2_start = i
            elif h2_start is not None and h2_end is None:
                h2_end = i
                break
    if h2_start is not None and h2_end is None:
        h2_end = len(lines)

    # H2 doesn't exist → append section + entry at EOF
    if h2_start is None:
        prefix = "\n" if text and not text.endswith("\n") else ""
        sep = "" if text.endswith("\n\n") or not text else "\n"
        return text + prefix + sep + h2_section + "\n" + element_block + "\n"

    # H2 exists → look for matching H3 inside the section
    h3_match_start = None
    h3_match_end = None
    for j in range(h2_start + 1, h2_end):
        m_h3 = _RE_H3.match(lines[j])
        if m_h3:
            h3_name = m_h3.group(1).split("(", 1)[0].strip().lower()
            if h3_match_start is not None and h3_match_end is None:
                h3_match_end = j
            if h3_name == name_target and h3_match_start is None:
                h3_match_start = j
    if h3_match_start is not None and h3_match_end is None:
        # The match extends to the H2 boundary
        h3_match_end = h2_end

    # H3 exists → replace in place
    if h3_match_start is not None:
        block_lines = element_block.rstrip("\n").splitlines()
        new_lines = (lines[:h3_match_start]
                     + block_lines
                     + lines[h3_match_end:])
        return "\n".join(new_lines) + ("\n" if text.endswith("\n") else "")

    # H3 doesn't exist → insert at end of H2 section
    # Trim trailing blank lines inside the section
    insert_at = h2_end
    while insert_at > h2_start + 1 and not lines[insert_at - 1].strip():
        insert_at -= 1
    block_lines = element_block.rstrip("\n").splitlines()
    new_lines = (lines[:insert_at]
                 + [""]  # one blank line before new entry
                 + block_lines
                 + ([""] if insert_at < len(lines) else [])
                 + lines[insert_at:])
    return "\n".join(new_lines) + ("\n" if text.endswith("\n") else "\n")


def _append_act_under_quest(text: str, quest_title: str,
                             act_block: str, act_index: int) -> str:
    """Place an act under the parent quest's H3 inside `## Major hooks`,
    creating the `#### Acts` subsection if not present.

    Idempotency: if an act with the same `act_index` exists under the quest,
    replace it in place.
    """
    lines = text.splitlines()
    h2_target = "## major hooks"
    quest_target = quest_title.strip().lower()

    # Find Major hooks section
    h2_start = None
    h2_end = None
    for i, ln in enumerate(lines):
        m_h2 = _RE_H2.match(ln)
        if m_h2:
            header = ln.strip().lower()
            if h2_start is None and header == h2_target:
                h2_start = i
            elif h2_start is not None and h2_end is None:
                h2_end = i
                break
    if h2_start is None:
        # No Major hooks section — caller's quest was never approved.
        # Soft-fail; engine-side state stays authoritative.
        log(f"skeleton_md_append: no Major hooks section for act_index={act_index}")
        return text
    if h2_end is None:
        h2_end = len(lines)

    # Find the quest H3 within the section
    quest_h3_start = None
    quest_h3_end = None
    for j in range(h2_start + 1, h2_end):
        m_h3 = _RE_H3.match(lines[j])
        if m_h3:
            qname = m_h3.group(1).split("(", 1)[0].strip().lower()
            if qname == quest_target:
                quest_h3_start = j
                # Find next H3 OR next H2 OR EOF
                for k in range(j + 1, h2_end):
                    if _RE_H3.match(lines[k]):
                        quest_h3_end = k
                        break
                if quest_h3_end is None:
                    quest_h3_end = h2_end
                break

    if quest_h3_start is None:
        log(f"skeleton_md_append: quest {quest_title!r} not found "
            f"for act_index={act_index}")
        return text

    # Find or create `#### Acts` subsection within quest's H3 range
    acts_h4_start = None
    acts_h4_end = None
    for k in range(quest_h3_start + 1, quest_h3_end):
        m_h4 = _RE_H4.match(lines[k])
        if m_h4 and m_h4.group(1).strip().lower() == 'acts':
            acts_h4_start = k
            acts_h4_end = quest_h3_end
            break

    block_lines = act_block.rstrip("\n").splitlines()
    if acts_h4_start is None:
        # Insert "#### Acts" + block at end of quest's H3 range
        insert_at = quest_h3_end
        while insert_at > quest_h3_start + 1 and not lines[insert_at - 1].strip():
            insert_at -= 1
        new_lines = (lines[:insert_at]
                     + [""]
                     + ["#### Acts"]
                     + block_lines
                     + ([""] if insert_at < len(lines) else [])
                     + lines[insert_at:])
        return "\n".join(new_lines) + ("\n" if text.endswith("\n") else "\n")

    # Acts subsection exists — check for matching act_index
    act_re = re.compile(rf"^\s*{act_index}\.\s+")
    match_start = None
    match_end = None
    for k in range(acts_h4_start + 1, acts_h4_end):
        if act_re.match(lines[k]):
            match_start = k
            # Match extends to next "N. " line or end of Acts section
            for m in range(k + 1, acts_h4_end):
                if re.match(r"^\s*\d+\.\s+", lines[m]):
                    match_end = m
                    break
            if match_end is None:
                match_end = acts_h4_end
            break

    if match_start is not None:
        # Replace in place
        new_lines = (lines[:match_start] + block_lines + lines[match_end:])
        return "\n".join(new_lines) + ("\n" if text.endswith("\n") else "")

    # Append to end of Acts subsection
    insert_at = acts_h4_end
    while insert_at > acts_h4_start + 1 and not lines[insert_at - 1].strip():
        insert_at -= 1
    new_lines = (lines[:insert_at]
                 + block_lines
                 + ([""] if insert_at < len(lines) else [])
                 + lines[insert_at:])
    return "\n".join(new_lines) + ("\n" if text.endswith("\n") else "\n")


def skeleton_md_append_element(campaign_id: int, element_type: str,
                                 element_data: dict,
                                 campaign_name: str = '',
                                 premise: str = '') -> tuple[bool, str]:
    """N-10 single-writer for skeleton.md appends.

    Returns (success, status_message). Soft-fail: file errors NEVER raise;
    returns (False, error_msg). Canonical-table writes are authoritative
    per §1.G; skeleton.md is the secondary side-effect.

    Idempotent on (element_type, element_name): re-append updates the H3
    body in place.
    """
    if element_type not in _H2_NAME_BY_ELEMENT_TYPE:
        msg = f"unknown_element_type={element_type!r}"
        log(f"skeleton_md_append: campaign={campaign_id} {msg}")
        return False, msg

    name = (element_data.get('name')
            or element_data.get('canonical_name')
            or element_data.get('title')
            or element_data.get('act_title') or '').strip()
    if not name:
        msg = "empty_element_name"
        log(f"skeleton_md_append: campaign={campaign_id} element_type={element_type} {msg}")
        return False, msg

    try:
        path = _ensure_skeleton_exists(campaign_id, campaign_name, premise)
        existing = path.read_text(encoding="utf-8")

        block = _render_element(element_type, element_data)
        if not block:
            msg = f"render_failed element_type={element_type}"
            log(f"skeleton_md_append: campaign={campaign_id} {msg}")
            return False, msg

        if element_type == 'quest_act':
            quest_title = (element_data.get('quest_title') or '').strip()
            if not quest_title:
                msg = "act_missing_quest_title"
                log(f"skeleton_md_append: campaign={campaign_id} {msg}")
                return False, msg
            act_index = element_data.get('act_index') or 1
            new_text = _append_act_under_quest(existing, quest_title, block, act_index)
        else:
            h2 = _H2_NAME_BY_ELEMENT_TYPE[element_type]
            new_text = _replace_or_append_h3(existing, h2, block, name)

        path.write_text(new_text, encoding="utf-8")
        log(f"skeleton_md_append: campaign={campaign_id} "
            f"element_type={element_type} name={name!r} chars={len(new_text)}")
        return True, 'appended'
    except Exception as e:
        msg = f"file_io_error={e!r}"
        log(f"skeleton_md_append: campaign={campaign_id} "
            f"element_type={element_type} name={name!r} {msg}")
        return False, msg
