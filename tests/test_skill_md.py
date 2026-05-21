"""Tests for ``skl.skill_md`` - SKILL.md parsing."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from skl.skill_md import Skill, SkillParseError, parse_skill_md, parse_skill_md_text


def _full_skill_md() -> str:
    return dedent(
        """\
        ---
        name: casey-case-studies
        description: |
          Retrieve and synthesise consulting case studies from the firm's library.
        skl:
          schema_version: 1
          display_name: Casey - Case Studies
          status: active
          enabled_platforms: [claude-code, m365]
          variables:
            - { name: consulting_company, description: The firm, required: true }
          knowledge:
            - id: case-study-library
              contract: knowledge/case-studies.contract.md
          tools:
            - id: web_fetch
        ---

        # Casey - Case Studies

        Intro paragraph for the H1 area.

        ## Identity

        You are Casey, a Case Studies Specialist.

        ## Capabilities

        - Search the case study library
        - Summarise findings

        ## Workflow

        1. Find candidates.
        2. Filter by relevance.

        ## Edge Cases

        - No results -> ask for broader criteria.
        """
    )


def test_parse_text_minimal() -> None:
    text = dedent(
        """\
        ---
        name: simple
        description: A simple skill.
        ---

        Just an intro.
        """
    )
    skill = parse_skill_md_text(text)
    assert skill.name == "simple"
    assert skill.description == "A simple skill."
    assert skill.intro == "Just an intro."
    assert skill.sections == {}


def test_parse_full_worked_example() -> None:
    skill = parse_skill_md_text(_full_skill_md())
    assert skill.name == "casey-case-studies"
    assert skill.display_name == "Casey - Case Studies"
    assert skill.status == "active"
    assert skill.enabled_platforms == ["claude-code", "m365"]
    assert skill.knowledge_ids == ["case-study-library"]
    assert skill.tool_ids == ["web_fetch"]
    assert skill.variable_names == ["consulting_company"]


def test_sections_preserve_order_and_case() -> None:
    skill = parse_skill_md_text(_full_skill_md())
    assert list(skill.sections.keys()) == ["Identity", "Capabilities", "Workflow", "Edge Cases"]
    assert "You are Casey" in skill.sections["Identity"]
    assert "Search the case study library" in skill.sections["Capabilities"]


def test_section_lookup_is_case_insensitive() -> None:
    skill = parse_skill_md_text(_full_skill_md())
    assert skill.section("identity") is not None
    assert skill.section("IDENTITY") is not None
    assert skill.has_section("Edge Cases")
    assert skill.section("nonexistent") is None
    assert not skill.has_section("References")


def test_intro_includes_h1() -> None:
    skill = parse_skill_md_text(_full_skill_md())
    assert skill.intro.startswith("# Casey - Case Studies")
    assert "Intro paragraph" in skill.intro


def test_missing_frontmatter_raises() -> None:
    with pytest.raises(SkillParseError, match="missing a YAML frontmatter"):
        parse_skill_md_text("just a body, no frontmatter\n")


def test_unparseable_frontmatter_raises() -> None:
    bad = "---\nname: [unclosed\n---\n\nbody\n"
    with pytest.raises(SkillParseError, match="could not be parsed"):
        parse_skill_md_text(bad)


def test_non_mapping_frontmatter_raises() -> None:
    bad = "---\n- just a list\n---\n\nbody\n"
    with pytest.raises(SkillParseError, match="must be a YAML mapping"):
        parse_skill_md_text(bad)


def test_h2_inside_code_fence_is_ignored() -> None:
    text = dedent(
        """\
        ---
        name: codey
        description: codey
        ---

        # Heading

        ## Real Section

        Some prose.

        ```
        ## not a section
        more code
        ```

        ## Another Real Section

        More prose.
        """
    )
    skill = parse_skill_md_text(text)
    assert list(skill.sections.keys()) == ["Real Section", "Another Real Section"]
    # The pseudo-section in the code fence ends up in the preceding section's body.
    assert "## not a section" in skill.sections["Real Section"]


def test_skl_block_missing_returns_empty_dict() -> None:
    text = dedent(
        """\
        ---
        name: anthropic-only
        description: A plain Anthropic skill with no `skl:` block.
        ---

        # Anthropic Only
        """
    )
    skill = parse_skill_md_text(text)
    assert skill.skl == {}
    assert skill.enabled_platforms == []
    assert skill.knowledge_ids == []
    assert skill.tool_ids == []


def test_parse_skill_md_reads_from_disk(tmp_path: Path) -> None:
    path = tmp_path / "SKILL.md"
    path.write_text(_full_skill_md())
    skill = parse_skill_md(path)
    assert skill.path == path
    assert skill.name == "casey-case-studies"


def test_skill_dataclass_carries_raw_text() -> None:
    text = _full_skill_md()
    skill = parse_skill_md_text(text)
    assert skill.raw_text == text
    assert isinstance(skill, Skill)
