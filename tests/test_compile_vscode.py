"""Tests for ``skl.compile.vscode`` and its dispatcher routing."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from textwrap import dedent

import pytest

from skl.compile import build_ir, compile_skill
from skl.compile.skills_native import compile_skills_native
from skl.compile.vscode import (
    _compose_custom_agent_frontmatter,
    _compose_tools_list,
    compile_vscode,
)

_FIXED_DATE = date(2026, 5, 22)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "skill-repo.yaml").write_text("schema_version: 1\nname: host\nvisibility: internal\n")
    return repo


def _full_skill_md(*, name: str = "demo") -> str:
    return (
        "---\n"
        f"name: {name}\n"
        "description: Demo skill for VS Code compile tests.\n"
        "skl:\n"
        "  schema_version: 1\n"
        "  display_name: Demo\n"
        "  status: active\n"
        "  enabled_platforms: [vscode]\n"
        "  tools:\n"
        "    - { id: web_fetch }\n"
        "    - { id: file_search }\n"
        "---\n"
        "\n"
        "# Demo\n"
        "\n"
        "## Identity\n"
        "You are Demo, a demo persona.\n"
        "\n"
        "## Capabilities\n"
        "- Do things.\n"
        "\n"
        "## Workflow\n"
        "1. Do.\n"
        "\n"
        "## Edge Cases\n"
        "- None.\n"
        "\n"
        "## Examples\n"
        "Example.\n"
    )


def _make_skill(
    repo: Path,
    name: str,
    *,
    sidecar: str | None = None,
) -> Path:
    skill_root = repo / "skills" / name
    skill_root.mkdir(parents=True)
    (skill_root / "SKILL.md").write_text(_full_skill_md(name=name))
    if sidecar is not None:
        platforms_dir = skill_root / "skl" / "platforms"
        platforms_dir.mkdir(parents=True)
        (platforms_dir / "vscode.yaml").write_text(dedent(sidecar))
    return skill_root


# ---------------------------------------------------------------------------
# Sidecar absent: Skill variant only
# ---------------------------------------------------------------------------


def test_no_sidecar_emits_only_skill_variant(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _make_skill(repo, "demo")
    ir = build_ir(repo / "skills" / "demo", repo)
    result = compile_vscode(ir, now=_FIXED_DATE)
    assert (repo / "platforms" / "vscode" / "skill" / "demo" / "SKILL.md").is_file()
    assert not (repo / "platforms" / "vscode" / "agent").exists()
    assert result.platform_id == "vscode"
    # output_root is the platforms/vscode/ parent, not a per-variant path.
    assert result.output_root == repo / "platforms" / "vscode"


def test_skill_variant_bytes_match_claude_code(tmp_path: Path) -> None:
    """The Skill variant is the same byte-stream as the claude-code output."""
    repo = _make_repo(tmp_path)
    _make_skill(repo, "demo")
    ir = build_ir(repo / "skills" / "demo", repo)
    compile_vscode(ir, now=_FIXED_DATE)
    compile_skills_native(ir, "claude-code", now=_FIXED_DATE)
    vscode_skill = (repo / "platforms" / "vscode" / "skill" / "demo" / "SKILL.md").read_text()
    claude_code = (repo / "platforms" / "claude-code" / "demo" / "SKILL.md").read_text()
    assert vscode_skill == claude_code


# ---------------------------------------------------------------------------
# Sidecar present: both variants by default
# ---------------------------------------------------------------------------


def test_sidecar_present_emits_both_variants(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _make_skill(
        repo,
        "demo",
        sidecar="""\
target: vscode
model: claude-opus-4-7
""",
    )
    ir = build_ir(repo / "skills" / "demo", repo)
    compile_vscode(ir, now=_FIXED_DATE)
    assert (repo / "platforms" / "vscode" / "skill" / "demo" / "SKILL.md").is_file()
    assert (repo / "platforms" / "vscode" / "agent" / "demo.agent.md").is_file()


def test_emit_skill_false_suppresses_skill_variant(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _make_skill(repo, "demo", sidecar="emit_skill: false\ntarget: vscode\n")
    ir = build_ir(repo / "skills" / "demo", repo)
    compile_vscode(ir, now=_FIXED_DATE)
    assert not (repo / "platforms" / "vscode" / "skill").exists()
    assert (repo / "platforms" / "vscode" / "agent" / "demo.agent.md").is_file()


def test_chatmode_md_never_emitted(tmp_path: Path) -> None:
    """SKL-007: `.chatmode.md` is not produced under any setting."""
    repo = _make_repo(tmp_path)
    _make_skill(repo, "demo", sidecar="target: vscode\n")
    ir = build_ir(repo / "skills" / "demo", repo)
    compile_vscode(ir, now=_FIXED_DATE)
    chatmodes = list((repo / "platforms" / "vscode").rglob("*.chatmode.md"))
    assert not chatmodes


# ---------------------------------------------------------------------------
# Custom Agent variant: body, frontmatter, provenance
# ---------------------------------------------------------------------------


def test_custom_agent_retains_identity_section(tmp_path: Path) -> None:
    """SKL-008: Custom Agent variant surfaces persona; Identity stays."""
    repo = _make_repo(tmp_path)
    _make_skill(repo, "demo", sidecar="target: vscode\n")
    ir = build_ir(repo / "skills" / "demo", repo)
    compile_vscode(ir, now=_FIXED_DATE)
    text = (repo / "platforms" / "vscode" / "agent" / "demo.agent.md").read_text()
    assert "## Identity" in text
    assert "You are Demo, a demo persona." in text


def test_skill_variant_strips_identity_section(tmp_path: Path) -> None:
    """SKL-008: Skill variant strips Identity (matches claude-code)."""
    repo = _make_repo(tmp_path)
    _make_skill(repo, "demo", sidecar="target: vscode\n")
    ir = build_ir(repo / "skills" / "demo", repo)
    compile_vscode(ir, now=_FIXED_DATE)
    text = (repo / "platforms" / "vscode" / "skill" / "demo" / "SKILL.md").read_text()
    assert "## Identity" not in text


def test_custom_agent_provenance_above_fence(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _make_skill(repo, "demo", sidecar="target: vscode\n")
    ir = build_ir(repo / "skills" / "demo", repo)
    compile_vscode(ir, now=_FIXED_DATE)
    text = (repo / "platforms" / "vscode" / "agent" / "demo.agent.md").read_text()
    lines = text.splitlines()
    assert lines[0].startswith("# Compiled by skl ")
    assert "on 2026-05-22" in lines[0]
    assert lines[1] == "---"


def test_custom_agent_frontmatter_includes_master_fields(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _make_skill(repo, "demo", sidecar="target: vscode\nmodel: claude-opus-4-7\n")
    ir = build_ir(repo / "skills" / "demo", repo)
    compile_vscode(ir, now=_FIXED_DATE)
    text = (repo / "platforms" / "vscode" / "agent" / "demo.agent.md").read_text()
    assert "name: demo" in text
    assert "description: Demo skill for VS Code compile tests." in text
    assert "target: vscode" in text
    assert "model: claude-opus-4-7" in text


def test_custom_agent_frontmatter_does_not_include_skl_block(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _make_skill(repo, "demo", sidecar="target: vscode\n")
    ir = build_ir(repo / "skills" / "demo", repo)
    compile_vscode(ir, now=_FIXED_DATE)
    text = (repo / "platforms" / "vscode" / "agent" / "demo.agent.md").read_text()
    # Pull just the frontmatter region (between first two ---).
    fm_start = text.index("\n---\n") + len("\n---\n")
    fm_end = text.index("\n---\n", fm_start)
    fm = text[fm_start:fm_end]
    assert "skl:" not in fm
    assert "schema_version" not in fm
    assert "enabled_platforms" not in fm


# ---------------------------------------------------------------------------
# Frontmatter composition (unit-level)
# ---------------------------------------------------------------------------


def test_compose_custom_agent_frontmatter_minimal(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _make_skill(repo, "demo")
    ir = build_ir(repo / "skills" / "demo", repo)
    fm = _compose_custom_agent_frontmatter(ir, {})
    assert fm == {"name": "demo", "description": "Demo skill for VS Code compile tests."}


def test_compose_custom_agent_frontmatter_passthroughs(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _make_skill(repo, "demo")
    ir = build_ir(repo / "skills" / "demo", repo)
    sidecar = {
        "target": "vscode",
        "model": ["claude-opus-4-7", "claude-sonnet-4-6"],
        "agents": ["*"],
        "handoffs": [{"label": "x", "agent": "y"}],
        "hooks": {"on_start": "echo hi"},
        "mcp-servers": [{"name": "foo"}],
        "argument-hint": "an arg",
        "user-invocable": True,
        "disable-model-invocation": False,
    }
    fm = _compose_custom_agent_frontmatter(ir, sidecar)
    for key, value in sidecar.items():
        assert fm[key] == value


def test_compose_tools_list_bindings_only() -> None:
    sidecar = {
        "bindings": {
            "tools": {
                "web_fetch": "VS Code Web Fetch",
                "file_search": "VS Code File Search",
            }
        }
    }
    # Sorted by skill tool ID for determinism: file_search < web_fetch.
    assert _compose_tools_list(sidecar) == [
        "VS Code File Search",
        "VS Code Web Fetch",
    ]


def test_compose_tools_list_explicit_only() -> None:
    sidecar = {"tools": ["Search", "Run"]}
    assert _compose_tools_list(sidecar) == ["Search", "Run"]


def test_compose_tools_list_merges_with_dedup() -> None:
    sidecar = {
        "bindings": {"tools": {"a": "Alpha", "b": "Bravo"}},
        "tools": ["Bravo", "Charlie"],  # Bravo is a duplicate of bindings.b
    }
    assert _compose_tools_list(sidecar) == ["Alpha", "Bravo", "Charlie"]


def test_compose_tools_list_empty_when_neither_declared() -> None:
    assert _compose_tools_list({}) == []


def test_custom_agent_tools_array_in_output(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _make_skill(
        repo,
        "demo",
        sidecar=dedent(
            """\
            target: vscode
            bindings:
              tools:
                web_fetch: "VS Code Web Fetch"
                file_search: "VS Code File Search"
            """
        ),
    )
    ir = build_ir(repo / "skills" / "demo", repo)
    compile_vscode(ir, now=_FIXED_DATE)
    text = (repo / "platforms" / "vscode" / "agent" / "demo.agent.md").read_text()
    # Both binding values appear; sorted by skill tool ID alphabetically.
    assert "VS Code File Search" in text
    assert "VS Code Web Fetch" in text


# ---------------------------------------------------------------------------
# Sibling folders (Skill variant only - Custom Agent is a single file)
# ---------------------------------------------------------------------------


def test_sibling_folders_copied_to_skill_variant_path(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    skill_root = _make_skill(repo, "demo", sidecar="target: vscode\n")
    refs = skill_root / "references"
    refs.mkdir()
    (refs / "note.md").write_text("ref\n")
    ir = build_ir(skill_root, repo)
    compile_vscode(ir, now=_FIXED_DATE)
    assert (repo / "platforms" / "vscode" / "skill" / "demo" / "references" / "note.md").is_file()
    # Custom Agent is a single file; no sibling folders under its parent.
    assert not (repo / "platforms" / "vscode" / "agent" / "references").exists()


# ---------------------------------------------------------------------------
# Dispatcher routing
# ---------------------------------------------------------------------------


def test_dispatcher_routes_vscode(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _make_skill(repo, "demo")
    ir = build_ir(repo / "skills" / "demo", repo)
    result = compile_skill(ir, "vscode")
    assert result.platform_id == "vscode"
    assert (repo / "platforms" / "vscode" / "skill" / "demo" / "SKILL.md").is_file()


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------


def test_cli_compile_vscode_emits_both_variants(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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
    _make_skill(repo, "demo", sidecar="target: vscode\nmodel: claude-opus-4-7\n")
    monkeypatch.chdir(repo)
    runner = CliRunner()
    result = runner.invoke(main, ["compile", "--platform", "vscode"])
    assert result.exit_code == 0, result.output
    assert (repo / "platforms" / "vscode" / "skill" / "demo" / "SKILL.md").is_file()
    assert (repo / "platforms" / "vscode" / "agent" / "demo.agent.md").is_file()
    assert "1 ok" in result.output  # one CompileResult for vscode, regardless of variant count
