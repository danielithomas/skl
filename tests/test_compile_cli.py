"""CLI integration tests for ``skl compile``."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from skl import __version__
from skl.cli import main


def _make_repo(tmp_path: Path) -> Path:
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
    return repo


def _scaffold_skill(
    repo: Path,
    name: str,
    *,
    platforms: tuple[str, ...] = ("claude-code",),
) -> Path:
    skill_root = repo / "skills" / name
    skill_root.mkdir(parents=True)
    platforms_yaml = ", ".join(platforms)
    (skill_root / "SKILL.md").write_text(
        f"""---
name: {name}
description: Skill for compile-cli tests.
skl:
  schema_version: 1
  display_name: {name.title()}
  status: draft
  enabled_platforms: [{platforms_yaml}]
---

# {name.title()}

## Capabilities
- Things.

## Workflow
1. Do.

## Edge Cases
- None.

## Examples
Example.
"""
    )
    return skill_root


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_cli_compile_outside_repo_errors(runner: CliRunner, tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(main, ["compile"])
        assert result.exit_code != 0
        assert "not inside a skill-host repo" in result.output


def test_cli_compile_with_no_skills_returns_zero(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _make_repo(tmp_path)
    monkeypatch.chdir(repo)
    result = runner.invoke(main, ["compile"])
    assert result.exit_code == 0, result.output
    assert "no skills/ directory" in result.output


def test_cli_compile_default_compiles_every_skill_x_platform(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _make_repo(tmp_path)
    _scaffold_skill(repo, "alpha", platforms=("claude-code", "ms-cowork"))
    _scaffold_skill(repo, "beta", platforms=("claude-code",))
    monkeypatch.chdir(repo)
    result = runner.invoke(main, ["compile"])
    assert result.exit_code == 0, result.output
    # All three (skill, platform) pairs compiled.
    assert (repo / "platforms" / "claude-code" / "alpha" / "SKILL.md").is_file()
    assert (repo / "platforms" / "ms-cowork" / "alpha" / "SKILL.md").is_file()
    assert (repo / "platforms" / "claude-code" / "beta" / "SKILL.md").is_file()
    assert "3 ok" in result.output


def test_cli_compile_skill_filter(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _make_repo(tmp_path)
    _scaffold_skill(repo, "alpha")
    _scaffold_skill(repo, "beta")
    monkeypatch.chdir(repo)
    result = runner.invoke(main, ["compile", "--skill", "alpha"])
    assert result.exit_code == 0, result.output
    assert (repo / "platforms" / "claude-code" / "alpha" / "SKILL.md").is_file()
    assert not (repo / "platforms" / "claude-code" / "beta").exists()


def test_cli_compile_platform_filter(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _make_repo(tmp_path)
    _scaffold_skill(repo, "alpha", platforms=("claude-code", "ms-cowork"))
    monkeypatch.chdir(repo)
    result = runner.invoke(main, ["compile", "--platform", "claude-code"])
    assert result.exit_code == 0, result.output
    assert (repo / "platforms" / "claude-code" / "alpha" / "SKILL.md").is_file()
    assert not (repo / "platforms" / "ms-cowork").exists()


def test_cli_compile_unknown_platform_errors(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _make_repo(tmp_path)
    _scaffold_skill(repo, "alpha")
    monkeypatch.chdir(repo)
    result = runner.invoke(main, ["compile", "--platform", "atari-jaguar"])
    assert result.exit_code != 0
    assert "unknown platform" in result.output


def test_cli_compile_unknown_skill_errors(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _make_repo(tmp_path)
    _scaffold_skill(repo, "alpha")
    monkeypatch.chdir(repo)
    result = runner.invoke(main, ["compile", "--skill", "nonexistent"])
    assert result.exit_code != 0
    assert "no skill named" in result.output


def test_cli_compile_unimplemented_platform_skips(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Targeting m365 / copilot-studio / vscode reports skipped, exit 0."""
    repo = _make_repo(tmp_path)
    _scaffold_skill(repo, "alpha", platforms=("m365",))
    monkeypatch.chdir(repo)
    result = runner.invoke(main, ["compile", "--platform", "m365"])
    assert result.exit_code == 0, result.output
    assert "skip" in result.output
    assert "1 skipped" in result.output


def test_cli_compile_skill_with_no_platforms_warns(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _make_repo(tmp_path)
    _scaffold_skill(repo, "alpha", platforms=())
    monkeypatch.chdir(repo)
    result = runner.invoke(main, ["compile"])
    assert result.exit_code == 0, result.output
    assert "no enabled_platforms" in result.output


def test_cli_compile_end_to_end_via_init(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Scaffold a skill via `skl init`, then compile it - exercises both modules."""
    repo = _make_repo(tmp_path)
    monkeypatch.chdir(repo)
    init_result = runner.invoke(main, ["init", "demo-skill", "--platform", "claude-code"])
    assert init_result.exit_code == 0, init_result.output
    compile_result = runner.invoke(main, ["compile"])
    assert compile_result.exit_code == 0, compile_result.output
    compiled = repo / "platforms" / "claude-code" / "demo-skill" / "SKILL.md"
    assert compiled.is_file()
    text = compiled.read_text()
    assert text.startswith("# Compiled by skl ")
    assert "skl:" not in text
    assert "## Identity" not in text
