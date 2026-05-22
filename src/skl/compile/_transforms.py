"""Text-transformation helpers shared across the per-platform compilers.

These were originally inlined in :mod:`skl.compile.skills_native`. Both the
Microsoft compilers (Copilot Studio, M365) and the existing Skills-native +
VS Code compilers need the same primitives:

- ``FENCE_RE`` - matches the leading ``---`` frontmatter fence so the
  compiler can split source SKILL.md text into frontmatter + body without
  going through ruamel (faster, preserves author formatting).
- ``split_frontmatter_and_body(raw)`` - convenience that returns the open
  fence, frontmatter text, close fence, and body, raising ``ValueError`` on
  a missing fence.
- ``remove_top_level_yaml_block(text, key)`` - drops a top-level YAML
  mapping by key (and its indented children). Used to strip the ``skl:``
  block per SKL-006.
- ``remove_h2_section(body, name)`` - drops an H2 section from the body,
  honouring fenced-code-block boundaries. Used for SKL-008's Identity
  strip and the H1/persona reorderings the Microsoft compilers do.
- ``rewrite_binding_tokens(text, kind, bindings, *, prefix='')`` -
  generic substitution of ``{{kind.<id>}}`` tokens with the matching value
  from a bindings map (with an optional prefix like ``/`` for Copilot
  Studio's UI-bound references).

This module is package-private: nothing outside ``skl.compile`` should
depend on it.
"""

from __future__ import annotations

import re
from typing import Any

FENCE_RE = re.compile(r"\A(---\s*\n)(.*?\n)(---\s*\n?)", re.DOTALL)
H2_LINE_RE = re.compile(r"^## (.+?)\s*$")


def split_frontmatter_and_body(raw: str) -> tuple[str, str, str, str]:
    """Split SKILL.md text into ``(open_fence, frontmatter, close_fence, body)``.

    Raises :class:`ValueError` if the source has no YAML frontmatter fence.
    Callers should rely on ``skl validate`` catching this before compile;
    the exception is a safety net.
    """
    match = FENCE_RE.match(raw)
    if match is None:
        raise ValueError(
            "source SKILL.md has no YAML frontmatter fence; "
            "this should have been caught by `skl validate` before compile"
        )
    return match.group(1), match.group(2), match.group(3), raw[match.end() :]


def remove_top_level_yaml_block(fm_text: str, key: str) -> str:
    """Remove a top-level YAML mapping by its key (and all indented children).

    Detects the key as a line at column 0 matching ``<key>:``. Children are
    consecutive indented or blank lines; the block ends at the next column-0
    non-blank line (the next top-level key) or end-of-frontmatter. If the
    key is not found, the text is returned unchanged.
    """
    lines = fm_text.splitlines(keepends=True)
    key_re = re.compile(rf"^{re.escape(key)}\s*:")
    start: int | None = None
    end = len(lines)
    for i, line in enumerate(lines):
        if key_re.match(line):
            start = i
            break
    if start is None:
        return fm_text
    for i in range(start + 1, len(lines)):
        line = lines[i]
        if line.strip() == "":
            continue
        if not line.startswith((" ", "\t")):
            end = i
            break
    return "".join(lines[:start] + lines[end:])


def remove_h2_section(body: str, name: str) -> str:
    """Remove an H2 section by heading (case-insensitive).

    The section is removed from the ``## Name`` line through (but not
    including) the next H2 line, or end-of-body. H2 lines inside fenced
    code blocks are not treated as section starts. If the section is not
    found, the body is returned unchanged.
    """
    target = name.lower().strip()
    lines = body.splitlines(keepends=True)
    in_code = False
    start: int | None = None
    end: int | None = None
    for i, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        match = H2_LINE_RE.match(line)
        if not match:
            continue
        heading = match.group(1).strip().lower()
        if start is None and heading == target:
            start = i
        elif start is not None:
            end = i
            break
    if start is None:
        return body
    if end is None:
        end = len(lines)
    return "".join(lines[:start] + lines[end:])


def rewrite_binding_tokens(
    text: str,
    kind: str,
    bindings: dict[str, Any],
    *,
    prefix: str = "",
) -> str:
    """Replace every ``{{<kind>.<id>}}`` token with its binding value.

    ``kind`` is the namespace (``"knowledge"`` or ``"tools"``).
    ``bindings`` maps the skill's ID to the platform-specific binding value.
    Only string bindings rewrite; dict/list bindings (e.g. M365's
    capability objects) are skipped and the token stays as-is.
    ``prefix`` is prepended to the rewritten value - Copilot Studio passes
    ``"/"`` to produce ``/Case Studies Library`` references.

    Whitespace inside the braces is tolerated (``{{ kind.x }}``).
    """
    pattern = re.compile(rf"\{{\{{\s*{re.escape(kind)}\.([a-z][a-z0-9_-]*)\s*\}}\}}")

    def _replace(match: re.Match[str]) -> str:
        binding_id = match.group(1)
        value = bindings.get(binding_id) if isinstance(bindings, dict) else None
        if isinstance(value, str):
            return f"{prefix}{value}"
        return match.group(0)

    return pattern.sub(_replace, text)
