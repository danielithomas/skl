"""Tests for ``skl.budget`` and the ``skl budget`` CLI verb."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest
from click.testing import CliRunner

from skl import __version__
from skl.budget import BudgetReport, BudgetRow, budget_report, render_report
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


def _make_skill(
    repo: Path,
    name: str,
    *,
    platforms: tuple[str, ...],
    sidecars: dict[str, str] | None = None,
    body_size: int = 0,
) -> Path:
    skill_root = repo / "skills" / name
    skill_root.mkdir(parents=True)
    extra = ("x " * body_size) if body_size else ""
    platforms_yaml = ", ".join(platforms)
    (skill_root / "SKILL.md").write_text(
        f"""---
name: {name}
description: Demo skill for budget tests.
skl:
  schema_version: 1
  display_name: {name.title()}
  status: active
  enabled_platforms: [{platforms_yaml}]
---

# {name.title()}

## Identity
Persona block.

## Capabilities
- Things.{extra}

## Workflow
1. Do.

## Edge Cases
- None.

## Examples
Example.
"""
    )
    if sidecars:
        platforms_dir = skill_root / "skl" / "platforms"
        platforms_dir.mkdir(parents=True)
        for platform_id, content in sidecars.items():
            (platforms_dir / f"{platform_id}.yaml").write_text(dedent(content))
    return skill_root


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


# ---------------------------------------------------------------------------
# budget_report
# ---------------------------------------------------------------------------


def test_no_skills_dir_returns_empty_report(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    report = budget_report(repo)
    assert isinstance(report, BudgetReport)
    assert report.rows == []
    assert report.skipped == []


def test_skills_native_skill_not_in_report(tmp_path: Path) -> None:
    """Uncapped platforms (claude-code etc.) aren't measured."""
    repo = _make_repo(tmp_path)
    _make_skill(repo, "demo", platforms=("claude-code",))
    report = budget_report(repo)
    assert report.rows == []


def test_copilot_studio_skill_measured(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _make_skill(repo, "demo", platforms=("copilot-studio",))
    report = budget_report(repo)
    assert len(report.rows) == 1
    row = report.rows[0]
    assert row.skill_name == "demo"
    assert row.platform_id == "copilot-studio"
    assert row.cap == 8000
    assert 0 < row.used < 8000
    assert not row.over_budget


def test_m365_skill_measured(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _make_skill(
        repo,
        "demo",
        platforms=("m365",),
        sidecars={"m365": 'schema_version: "1.7"\n'},
    )
    report = budget_report(repo)
    row = next(r for r in report.rows if r.platform_id == "m365")
    assert row.cap == 8000
    assert row.used > 0


def test_overage_flagged(tmp_path: Path) -> None:
    """A skill larger than the cap is reported as over_budget."""
    repo = _make_repo(tmp_path)
    _make_skill(repo, "huge", platforms=("copilot-studio",), body_size=5000)
    report = budget_report(repo)
    row = report.rows[0]
    assert row.over_budget
    assert row.used > row.cap
    assert report.has_overages


def test_sidecar_budget_override_for_copilot_studio(tmp_path: Path) -> None:
    """Lowering `budget:` in the sidecar lowers the reported cap."""
    repo = _make_repo(tmp_path)
    _make_skill(
        repo,
        "demo",
        platforms=("copilot-studio",),
        sidecars={"copilot-studio": "budget: 100\n"},
    )
    report = budget_report(repo)
    row = report.rows[0]
    assert row.cap == 100
    assert row.over_budget  # the skill body is > 100 chars


def test_multiple_skills_x_platforms(tmp_path: Path) -> None:
    """Each (skill, capped platform) combination produces one row."""
    repo = _make_repo(tmp_path)
    _make_skill(repo, "alpha", platforms=("copilot-studio",))
    _make_skill(
        repo,
        "beta",
        platforms=("copilot-studio", "m365"),
        sidecars={"m365": 'schema_version: "1.7"\n'},
    )
    report = budget_report(repo)
    keys = {(r.skill_name, r.platform_id) for r in report.rows}
    assert keys == {
        ("alpha", "copilot-studio"),
        ("beta", "copilot-studio"),
        ("beta", "m365"),
    }


def test_unparseable_skill_skipped(tmp_path: Path) -> None:
    """A skill whose SKILL.md doesn't parse appears in `skipped`, not `rows`."""
    repo = _make_repo(tmp_path)
    skill_root = repo / "skills" / "broken"
    skill_root.mkdir(parents=True)
    (skill_root / "SKILL.md").write_text("Just body, no frontmatter.\n")
    report = budget_report(repo)
    assert "broken" in report.skipped
    assert report.rows == []


# ---------------------------------------------------------------------------
# render_report
# ---------------------------------------------------------------------------


def test_render_report_includes_header() -> None:
    report = BudgetReport(
        rows=[BudgetRow(skill_name="demo", platform_id="copilot-studio", used=4000, cap=8000)]
    )
    out = render_report(report)
    assert "Skill" in out
    assert "Platform" in out
    assert "Cap" in out
    assert "demo" in out
    assert "copilot-studio" in out
    assert "4,000" in out
    assert "8,000" in out
    assert "ok" in out


def test_render_report_flags_overage() -> None:
    report = BudgetReport(
        rows=[BudgetRow(skill_name="huge", platform_id="m365", used=9000, cap=8000)]
    )
    out = render_report(report)
    assert "OVER" in out


def test_render_report_empty() -> None:
    out = render_report(BudgetReport())
    assert "no skills" in out


def test_render_report_lists_skipped() -> None:
    report = BudgetReport(skipped=["broken"])
    out = render_report(report)
    assert "skipped" in out
    assert "broken" in out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_cli_budget_outside_repo_errors(runner: CliRunner, tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(main, ["budget"])
        assert result.exit_code != 0
        assert "not inside a skill-host repo" in result.output


def test_cli_budget_exits_zero_when_in_budget(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _make_repo(tmp_path)
    _make_skill(repo, "demo", platforms=("copilot-studio",))
    monkeypatch.chdir(repo)
    result = runner.invoke(main, ["budget"])
    assert result.exit_code == 0, result.output
    assert "demo" in result.output
    assert "ok" in result.output


def test_cli_budget_exits_one_on_overage(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _make_repo(tmp_path)
    _make_skill(repo, "huge", platforms=("copilot-studio",), body_size=5000)
    monkeypatch.chdir(repo)
    result = runner.invoke(main, ["budget"])
    assert result.exit_code == 1, result.output
    assert "OVER" in result.output


def test_cli_budget_with_no_capped_skills_returns_zero(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Skills targeting only uncapped platforms produce an empty report, exit 0."""
    repo = _make_repo(tmp_path)
    _make_skill(repo, "claude-only", platforms=("claude-code",))
    monkeypatch.chdir(repo)
    result = runner.invoke(main, ["budget"])
    assert result.exit_code == 0, result.output
    assert "no skills with budget-enforced platforms" in result.output
