"""Tests for ``skl.compile.copilot_studio``."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from textwrap import dedent

import pytest

from skl.compile import build_ir, compile_skill
from skl.compile.budget import BudgetExceededError
from skl.compile.copilot_studio import (
    compile_copilot_studio,
    compose_copilot_studio_instructions,
)

_FIXED_DATE = date(2026, 5, 22)


def _make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "skill-repo.yaml").write_text("schema_version: 1\nname: host\nvisibility: internal\n")
    return repo


def _full_skill_md(
    *,
    name: str = "demo",
    with_tone: bool = False,
    with_knowledge_ref: bool = False,
    with_tools_ref: bool = False,
    body_extra: str = "",
) -> str:
    tone = "## Tone\nBe concise.\n\n" if with_tone else ""
    knowledge_section = (
        "## Knowledge Sources\nUse {{knowledge.case-study-library}} for past work.\n\n"
        if with_knowledge_ref
        else ""
    )
    tools_section = "## Tools\nCall {{tools.web_fetch}} when needed.\n\n" if with_tools_ref else ""
    return (
        "---\n"
        f"name: {name}\n"
        "description: Demo skill for Copilot Studio tests.\n"
        "skl:\n"
        "  schema_version: 1\n"
        "  display_name: Demo\n"
        "  status: active\n"
        "  enabled_platforms: [copilot-studio]\n"
        "---\n"
        "\n"
        "# Demo\n"
        "\n"
        "## Identity\n"
        "You are Demo, a demo persona.\n"
        "\n"
        f"{tone}"
        "## Capabilities\n"
        "- Demo capability.\n"
        "\n"
        f"{knowledge_section}"
        f"{tools_section}"
        "## Workflow\n"
        "1. Do.\n"
        "\n"
        "## Edge Cases\n"
        "- None.\n"
        "\n"
        "## Examples\n"
        "Example.\n"
        f"{body_extra}"
    )


def _make_skill(repo: Path, name: str, content: str, *, sidecar: str | None = None) -> Path:
    skill_root = repo / "skills" / name
    skill_root.mkdir(parents=True)
    (skill_root / "SKILL.md").write_text(content)
    if sidecar is not None:
        platforms_dir = skill_root / "skl" / "platforms"
        platforms_dir.mkdir(parents=True)
        (platforms_dir / "copilot-studio.yaml").write_text(dedent(sidecar))
    return skill_root


# ---------------------------------------------------------------------------
# Output path + provenance
# ---------------------------------------------------------------------------


def test_compile_writes_instructions_md(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _make_skill(repo, "demo", _full_skill_md())
    ir = build_ir(repo / "skills" / "demo", repo)
    result = compile_copilot_studio(ir, now=_FIXED_DATE)
    assert result.output_root == repo / "platforms" / "copilot-studio"
    out = repo / "platforms" / "copilot-studio" / "instructions.md"
    assert out.is_file()
    assert result.files_written == [out]


def test_provenance_comment_on_first_line(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _make_skill(repo, "demo", _full_skill_md())
    ir = build_ir(repo / "skills" / "demo", repo)
    compile_copilot_studio(ir, now=_FIXED_DATE)
    text = (repo / "platforms" / "copilot-studio" / "instructions.md").read_text()
    assert text.splitlines()[0].startswith("# Compiled by skl ")
    assert "on 2026-05-22" in text.splitlines()[0]


# ---------------------------------------------------------------------------
# Section order + Identity surfacing
# ---------------------------------------------------------------------------


def test_identity_surfaces_as_preamble(tmp_path: Path) -> None:
    """SKL-008: Identity stays for Copilot Studio. Inlined without H2 header."""
    repo = _make_repo(tmp_path)
    _make_skill(repo, "demo", _full_skill_md())
    ir = build_ir(repo / "skills" / "demo", repo)
    instructions = compose_copilot_studio_instructions(ir)
    # The Identity text appears before any ## section header.
    first_h2 = instructions.find("## Capabilities")
    identity_idx = instructions.find("You are Demo, a demo persona.")
    assert 0 <= identity_idx < first_h2
    # The literal "## Identity" header is NOT in the output - it was inlined.
    assert "## Identity" not in instructions


def test_tone_inlined_after_identity(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _make_skill(repo, "demo", _full_skill_md(with_tone=True))
    ir = build_ir(repo / "skills" / "demo", repo)
    instructions = compose_copilot_studio_instructions(ir)
    identity_idx = instructions.find("You are Demo, a demo persona.")
    tone_idx = instructions.find("Be concise.")
    capabilities_idx = instructions.find("## Capabilities")
    assert 0 <= identity_idx < tone_idx < capabilities_idx
    assert "## Tone" not in instructions


def test_section_order_canonical(tmp_path: Path) -> None:
    """Sections appear in: Capabilities, Knowledge Sources, Tools, Workflow, Edge Cases, Examples."""
    repo = _make_repo(tmp_path)
    _make_skill(
        repo,
        "demo",
        _full_skill_md(with_knowledge_ref=True, with_tools_ref=True),
    )
    ir = build_ir(repo / "skills" / "demo", repo)
    instructions = compose_copilot_studio_instructions(ir)
    expected_order = [
        "## Capabilities",
        "## Knowledge Sources",
        "## Tools",
        "## Workflow",
        "## Edge Cases",
        "## Examples",
    ]
    indices = [instructions.index(s) for s in expected_order]
    assert indices == sorted(indices)


def test_missing_sections_are_skipped(tmp_path: Path) -> None:
    """No empty headers for sections not present in source."""
    repo = _make_repo(tmp_path)
    _make_skill(repo, "demo", _full_skill_md())  # no Output Format, Response Templates
    ir = build_ir(repo / "skills" / "demo", repo)
    instructions = compose_copilot_studio_instructions(ir)
    assert "## Output Format" not in instructions
    assert "## Response Templates" not in instructions


# ---------------------------------------------------------------------------
# Token rewrites
# ---------------------------------------------------------------------------


def test_knowledge_token_rewritten_to_slash_binding(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _make_skill(
        repo,
        "demo",
        _full_skill_md(with_knowledge_ref=True),
        sidecar=dedent(
            """\
            bindings:
              knowledge:
                case-study-library: "Case Studies Library"
            """
        ),
    )
    ir = build_ir(repo / "skills" / "demo", repo)
    instructions = compose_copilot_studio_instructions(ir)
    assert "/Case Studies Library" in instructions
    assert "{{knowledge.case-study-library}}" not in instructions


def test_tools_token_rewritten_to_slash_binding(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _make_skill(
        repo,
        "demo",
        _full_skill_md(with_tools_ref=True),
        sidecar=dedent(
            """\
            bindings:
              tools:
                web_fetch: "Web Fetch"
            """
        ),
    )
    ir = build_ir(repo / "skills" / "demo", repo)
    instructions = compose_copilot_studio_instructions(ir)
    assert "/Web Fetch" in instructions
    assert "{{tools.web_fetch}}" not in instructions


def test_unbound_knowledge_token_left_intact(tmp_path: Path) -> None:
    """If no binding declared, the token stays as-is (validate catches it)."""
    repo = _make_repo(tmp_path)
    _make_skill(repo, "demo", _full_skill_md(with_knowledge_ref=True))
    ir = build_ir(repo / "skills" / "demo", repo)
    instructions = compose_copilot_studio_instructions(ir)
    assert "{{knowledge.case-study-library}}" in instructions


def test_variable_tokens_not_rewritten(tmp_path: Path) -> None:
    """Variables are deploy-time per D-007; compile leaves them as tokens."""
    repo = _make_repo(tmp_path)
    _make_skill(
        repo,
        "demo",
        _full_skill_md(body_extra="\n\nWorks for {{variables.company}}.\n"),
    )
    ir = build_ir(repo / "skills" / "demo", repo)
    instructions = compose_copilot_studio_instructions(ir)
    assert "{{variables.company}}" in instructions


# ---------------------------------------------------------------------------
# Budget enforcement
# ---------------------------------------------------------------------------


def test_default_budget_is_8000(tmp_path: Path) -> None:
    """An over-budget skill raises BudgetExceededError on compile."""
    repo = _make_repo(tmp_path)
    huge = "x " * 5000  # 10,000 chars
    _make_skill(repo, "huge", _full_skill_md(body_extra=f"\n\n{huge}\n"))
    ir = build_ir(repo / "skills" / "huge", repo)
    with pytest.raises(BudgetExceededError, match="copilot-studio"):
        compile_copilot_studio(ir, now=_FIXED_DATE)


def test_sidecar_budget_override(tmp_path: Path) -> None:
    """A lower budget in the sidecar fails sooner."""
    repo = _make_repo(tmp_path)
    medium = "x " * 200  # 400 chars
    _make_skill(
        repo,
        "demo",
        _full_skill_md(body_extra=f"\n\n{medium}\n"),
        sidecar="budget: 100\n",
    )
    ir = build_ir(repo / "skills" / "demo", repo)
    with pytest.raises(BudgetExceededError):
        compile_copilot_studio(ir, now=_FIXED_DATE)


def test_within_budget_compiles(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _make_skill(repo, "small", _full_skill_md())
    ir = build_ir(repo / "skills" / "small", repo)
    result = compile_copilot_studio(ir, now=_FIXED_DATE)
    assert (result.output_root / "instructions.md").is_file()


# ---------------------------------------------------------------------------
# Dispatcher + CLI
# ---------------------------------------------------------------------------


def test_dispatcher_routes_copilot_studio(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _make_skill(repo, "demo", _full_skill_md())
    ir = build_ir(repo / "skills" / "demo", repo)
    result = compile_skill(ir, "copilot-studio")
    assert result.platform_id == "copilot-studio"


def test_cli_compile_copilot_studio(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from click.testing import CliRunner

    from skl import __version__
    from skl.cli import main

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "skill-repo.yaml").write_text(
        f"""\
schema_version: 1
name: host
visibility: internal
skl_version: ">={__version__},<99.0"
shared_kit:
  source: github.com/example/kit
  version: "1.0.0"
enabled_platforms: []
"""
    )
    _make_skill(repo, "demo", _full_skill_md())
    monkeypatch.chdir(repo)
    runner = CliRunner()
    result = runner.invoke(main, ["compile", "--platform", "copilot-studio"])
    assert result.exit_code == 0, result.output
    assert (repo / "platforms" / "copilot-studio" / "instructions.md").is_file()
    assert "1 ok" in result.output


def test_cli_compile_copilot_studio_budget_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An over-budget compile surfaces as a CLI FAIL line + exit 1."""
    from click.testing import CliRunner

    from skl import __version__
    from skl.cli import main

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "skill-repo.yaml").write_text(
        f"""\
schema_version: 1
name: host
visibility: internal
skl_version: ">={__version__},<99.0"
shared_kit:
  source: github.com/example/kit
  version: "1.0.0"
enabled_platforms: []
"""
    )
    huge = "x " * 5000
    _make_skill(repo, "huge", _full_skill_md(body_extra=f"\n\n{huge}\n"))
    monkeypatch.chdir(repo)
    runner = CliRunner()
    result = runner.invoke(main, ["compile", "--platform", "copilot-studio"])
    assert result.exit_code == 1, result.output
    assert "FAIL" in result.output
    assert "8,000" in result.output or "8000" in result.output
