"""Sanity checks for the COMMANDS.md canonical reference doc.

Lightweight: does the file exist at the expected path, does it have the
expected top-level sections, is it non-trivially populated. This is the
operator-discipline backstop for the maintenance protocol — if a session
deletes or breaks COMMANDS.md, this suite catches it.

Run:
    cd /home/jordaneal/scripts && python3 test_commands_doc.py
"""

import sys
from pathlib import Path

sys.path.insert(0, '/home/jordaneal/scripts')

import dnd_orchestration as orch


def test_commands_doc_exists_at_canonical_path():
    assert orch.COMMANDS_DOC_PATH.is_file(), (
        f"COMMANDS.md missing at {orch.COMMANDS_DOC_PATH}. "
        f"Advisory mode degrades gracefully but loses its command-grounding."
    )


def test_commands_doc_has_virgil_slash_commands_section():
    content = orch.COMMANDS_DOC_PATH.read_text(encoding='utf-8')
    assert '## Virgil Slash Commands' in content


def test_commands_doc_has_avrae_commands_section():
    content = orch.COMMANDS_DOC_PATH.read_text(encoding='utf-8')
    assert '## Avrae Commands' in content


def test_commands_doc_has_advisory_notes_section():
    # Lower-priority but explicitly part of the spec — guidance for the LLM
    # is in this section.
    content = orch.COMMANDS_DOC_PATH.read_text(encoding='utf-8')
    assert 'Notes for Advisory Mode' in content


def test_commands_doc_non_empty():
    content = orch.COMMANDS_DOC_PATH.read_text(encoding='utf-8')
    assert len(content) >= 500, (
        f"COMMANDS.md is suspiciously short ({len(content)} chars). "
        f"Should be at least 500 chars with realistic content."
    )


def test_commands_doc_lists_setup_and_play():
    # Two commands so load-bearing they must appear: /setup (channel
    # provisioning) and /play (scene opening). Cheap detection of
    # accidental wholesale truncation.
    content = orch.COMMANDS_DOC_PATH.read_text(encoding='utf-8')
    assert '/setup' in content
    assert '/play' in content


def test_commands_doc_lists_avrae_init_attack_check():
    # Three Avrae commands the live flow uses every session — same
    # truncation-detection role as /setup / /play above.
    content = orch.COMMANDS_DOC_PATH.read_text(encoding='utf-8')
    assert '!init' in content
    assert '!attack' in content
    assert '!check' in content


def test_commands_doc_loadable_via_orchestration_loader():
    # The loader is the production read path; confirm it returns the
    # same content as a direct read. Catches encoding / path-resolution
    # drift that direct test reads would mask.
    direct = orch.COMMANDS_DOC_PATH.read_text(encoding='utf-8')
    via_loader = orch._load_commands_reference()
    assert via_loader == direct


if __name__ == '__main__':
    failures = []
    funcs = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for fn in funcs:
        try:
            fn()
            print(f"  ok   {fn.__name__}")
        except AssertionError as e:
            failures.append((fn.__name__, str(e)))
            print(f"  FAIL {fn.__name__}: {e}")
        except Exception as e:
            failures.append((fn.__name__, repr(e)))
            print(f"  ERR  {fn.__name__}: {e!r}")
    if failures:
        print(f"\n{len(failures)} failure(s)")
        sys.exit(1)
    print(f"\n{len(funcs)} tests passed.")
