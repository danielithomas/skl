"""Parse SKILL.md - frontmatter + body sections.

A SKILL.md file is the source-of-truth authoring artefact (per SKL-004). It
has a YAML frontmatter block fenced by ``---`` lines, followed by a markdown
body whose H2 sections (``## Identity``, ``## Capabilities``, ...) are the
anchors compilers and validators care about.

The Anthropic-Skills base fields live at the top of the frontmatter
(``name``, ``description``); the ``skl:`` block carries the cross-cutting
superset metadata. This module returns the whole frontmatter as a plain
``dict`` (via :func:`skl.manifest.to_plain`) and the body split into the
intro paragraph plus an ordered map of H2 sections.

The module is parsing only - schema validation is done by ``skl validate``
(Check 2) against ``skl.schemas.skill.frontmatter.schema.json``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from skl import manifest

_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?\n)---\s*\n?", re.DOTALL)
_H2_RE = re.compile(r"^## (.+?)\s*$")


class SkillParseError(ValueError):
    """SKILL.md could not be parsed.

    Raised for missing or malformed YAML frontmatter, or a frontmatter block
    that does not parse to a top-level mapping. Body parse errors do not
    raise - section splitting is best-effort - so a malformed body still
    yields a ``Skill`` whose sections are whatever was recoverable.
    """


@dataclass
class Skill:
    """Parsed SKILL.md.

    ``frontmatter`` is the whole frontmatter (Anthropic base + ``skl:`` block)
    as a plain dict. ``sections`` keys preserve the H2 heading text from the
    source verbatim (case included); use :meth:`section` for case-insensitive
    lookup.
    """

    path: Path | None
    raw_text: str
    frontmatter: dict[str, Any]
    intro: str
    sections: dict[str, str] = field(default_factory=dict)

    @property
    def name(self) -> str | None:
        return self.frontmatter.get("name")

    @property
    def description(self) -> str | None:
        return self.frontmatter.get("description")

    @property
    def skl(self) -> dict[str, Any]:
        """The ``skl:`` namespaced block. Empty dict if missing."""
        block = self.frontmatter.get("skl")
        return block if isinstance(block, dict) else {}

    @property
    def display_name(self) -> str | None:
        return self.skl.get("display_name")

    @property
    def status(self) -> str | None:
        return self.skl.get("status")

    @property
    def enabled_platforms(self) -> list[str]:
        return list(self.skl.get("enabled_platforms", []))

    @property
    def variables(self) -> list[dict[str, Any]]:
        return list(self.skl.get("variables", []))

    @property
    def variable_names(self) -> list[str]:
        return [v["name"] for v in self.variables if isinstance(v, dict) and "name" in v]

    @property
    def knowledge_ids(self) -> list[str]:
        items = self.skl.get("knowledge", [])
        return [item["id"] for item in items if isinstance(item, dict) and "id" in item]

    @property
    def tool_ids(self) -> list[str]:
        items = self.skl.get("tools", [])
        return [item["id"] for item in items if isinstance(item, dict) and "id" in item]

    def section(self, name: str) -> str | None:
        """Look up a section's body by its H2 heading (case-insensitive)."""
        target = name.lower().strip()
        for heading, body in self.sections.items():
            if heading.lower().strip() == target:
                return body
        return None

    def has_section(self, name: str) -> bool:
        return self.section(name) is not None


def parse_skill_md(path: Path) -> Skill:
    """Read and parse a SKILL.md file."""
    text = path.read_text()
    return parse_skill_md_text(text, path=path)


def parse_skill_md_text(text: str, path: Path | None = None) -> Skill:
    """Parse SKILL.md content from a string.

    Raises :class:`SkillParseError` if the frontmatter block is missing,
    malformed, or does not parse to a top-level mapping.
    """
    match = _FRONTMATTER_RE.match(text)
    if match is None:
        location = f" at {path}" if path else ""
        raise SkillParseError(
            f"SKILL.md{location} is missing a YAML frontmatter block "
            "(expected '---' fences at the top of the file)"
        )
    frontmatter_text = match.group(1)
    try:
        raw_frontmatter = manifest.loads(frontmatter_text)
    except Exception as exc:
        location = f" at {path}" if path else ""
        raise SkillParseError(
            f"SKILL.md frontmatter{location} could not be parsed as YAML: {exc}"
        ) from exc

    if raw_frontmatter is None:
        raw_frontmatter = {}
    if not isinstance(raw_frontmatter, dict):
        location = f" at {path}" if path else ""
        raise SkillParseError(
            f"SKILL.md frontmatter{location} must be a YAML mapping; "
            f"got {type(raw_frontmatter).__name__}"
        )

    frontmatter = manifest.to_plain(raw_frontmatter)
    body = text[match.end() :]
    intro, sections = _split_body(body)
    return Skill(
        path=path,
        raw_text=text,
        frontmatter=frontmatter,
        intro=intro,
        sections=sections,
    )


def _split_body(body: str) -> tuple[str, dict[str, str]]:
    """Split the body into intro (pre-first-H2) + a dict of H2 sections.

    H2 lines (``## Heading``) inside fenced code blocks are not treated as
    section starts. Section bodies are stripped of leading and trailing
    whitespace.
    """
    lines = body.splitlines(keepends=True)
    in_code_fence = False
    headings: list[tuple[int, str]] = []
    for idx, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            in_code_fence = not in_code_fence
            continue
        if in_code_fence:
            continue
        match = _H2_RE.match(line)
        if match:
            headings.append((idx, match.group(1).strip()))

    if not headings:
        return body.strip(), {}

    first_idx = headings[0][0]
    intro = "".join(lines[:first_idx]).strip()
    sections: dict[str, str] = {}
    for j, (idx, name) in enumerate(headings):
        start = idx + 1
        end = headings[j + 1][0] if j + 1 < len(headings) else len(lines)
        sections[name] = "".join(lines[start:end]).strip()
    return intro, sections
