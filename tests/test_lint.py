"""Tests for ``skl.lint``."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest
from click.testing import CliRunner

from skl import __version__
from skl.cli import main
from skl.lint import (
    LintFinding,
    LintReport,
    apply_fixes,
    lint_repo,
    lint_skill,
)


def _make_skill_md(name: str = "demo", body: str = "") -> str:
    return dedent(
        f"""\
        ---
        name: {name}
        description: An example skill for lint tests.
        skl:
          schema_version: 1
          display_name: Demo
          status: draft
          enabled_platforms: []
        ---

        # Demo

        ## Capabilities
        - Do things.

        ## Workflow
        1. Do.

        ## Edge Cases
        - None.

        ## Examples
        Example use.
        {body}
        """
    )


def _make_skill(repo: Path, name: str, skill_md: str) -> Path:
    skill_root = repo / "skills" / name
    skill_root.mkdir(parents=True)
    (skill_root / "SKILL.md").write_text(skill_md)
    return skill_root


# ---------------------------------------------------------------------------
# em-dash / en-dash
# ---------------------------------------------------------------------------


def test_em_dash_is_an_error_with_fix(tmp_path: Path) -> None:
    skill_root = _make_skill(tmp_path, "dashy", _make_skill_md(body="Some — text.\n"))
    report = lint_skill(skill_root)
    em_findings = [f for f in report.findings if f.rule == "em-dash"]
    assert em_findings
    finding = em_findings[0]
    assert finding.severity == "error"
    assert finding.fix == ("—", " - ")


def test_en_dash_also_flagged(tmp_path: Path) -> None:
    skill_root = _make_skill(tmp_path, "dashy", _make_skill_md(body="Range 1–10.\n"))
    report = lint_skill(skill_root)
    assert any(f.rule == "em-dash" for f in report.findings)


# ---------------------------------------------------------------------------
# AU spelling
# ---------------------------------------------------------------------------


def test_us_spelling_warned_with_fix(tmp_path: Path) -> None:
    """Each US word produces its own finding with a per-word substring fix."""
    skill_root = _make_skill(
        tmp_path,
        "spelly",
        _make_skill_md(body="We organize and optimize the color palette.\n"),
    )
    report = lint_skill(skill_root)
    findings = [f for f in report.findings if f.rule == "au-spelling"]
    assert len(findings) >= 3
    assert all(f.severity == "warning" for f in findings)
    fixes = {f.fix for f in findings}
    assert ("organize", "organise") in fixes
    assert ("optimize", "optimise") in fixes
    assert ("color", "colour") in fixes


def test_au_spelling_preserves_case(tmp_path: Path) -> None:
    """Title-case and uppercase US words rewrite to matching case AU forms."""
    skill_root = _make_skill(
        tmp_path,
        "casey",
        _make_skill_md(body="Optimize the COLOR. Organize widely.\n"),
    )
    report = lint_skill(skill_root)
    fixes = {f.fix for f in report.findings if f.rule == "au-spelling"}
    assert ("Optimize", "Optimise") in fixes
    assert ("COLOR", "COLOUR") in fixes
    assert ("Organize", "Organise") in fixes


def test_au_spelling_does_not_flag_correct_au(tmp_path: Path) -> None:
    skill_root = _make_skill(
        tmp_path,
        "fine",
        _make_skill_md(body="We organise and optimise the colour.\n"),
    )
    report = lint_skill(skill_root)
    assert not any(f.rule == "au-spelling" for f in report.findings)


# ---------------------------------------------------------------------------
# credentials
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "token,rule_suffix",
    [
        ("AKIAIOSFODNN7EXAMPLE", "aws-access-key"),
        ("sk-ant-api03-abcdefghijklmnopqrstuvwxyz1234567890", "anthropic-api-key"),
        ("ghp_" + "A" * 36, "github-pat"),
        ("xoxb-1234567890-abcdefghijkl", "slack-token"),
    ],
)
def test_credential_patterns_flag_known_tokens(
    tmp_path: Path, token: str, rule_suffix: str
) -> None:
    skill_root = _make_skill(
        tmp_path,
        "leaky",
        _make_skill_md(body=f"Token leaked: {token}\n"),
    )
    report = lint_skill(skill_root)
    findings = [f for f in report.findings if f.rule.startswith("credentials/")]
    assert findings
    finding = findings[0]
    assert finding.severity == "error"
    assert rule_suffix in finding.rule


def test_private_key_block_flagged(tmp_path: Path) -> None:
    body = "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA...\n-----END RSA PRIVATE KEY-----\n"
    skill_root = _make_skill(tmp_path, "keys", _make_skill_md(body=body))
    report = lint_skill(skill_root)
    assert any(f.rule == "credentials/private-key-block" for f in report.findings)


def test_credentials_not_auto_fixable(tmp_path: Path) -> None:
    skill_root = _make_skill(
        tmp_path,
        "leaky",
        _make_skill_md(body="Leak: AKIAIOSFODNN7EXAMPLE\n"),
    )
    report = lint_skill(skill_root)
    cred = next(f for f in report.findings if f.rule.startswith("credentials/"))
    assert cred.fix is None


# ---------------------------------------------------------------------------
# banned phrases
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("phrase", ["as an AI", "I cannot fulfill", "in order to"])
def test_banned_phrases_flagged(tmp_path: Path, phrase: str) -> None:
    skill_root = _make_skill(
        tmp_path,
        "phrased",
        _make_skill_md(body=f"Note: {phrase} this.\n"),
    )
    report = lint_skill(skill_root)
    assert any(f.rule == "banned-phrase" for f in report.findings)


# ---------------------------------------------------------------------------
# unresolved tokens
# ---------------------------------------------------------------------------


def test_unresolved_token_warns(tmp_path: Path) -> None:
    skill_root = _make_skill(
        tmp_path,
        "vars",
        _make_skill_md(body="Refers to {{variables.ghost}}.\n"),
    )
    report = lint_skill(skill_root)
    tokens = [f for f in report.findings if f.rule == "unresolved-token"]
    assert tokens
    assert tokens[0].severity == "warning"


def test_declared_variable_not_flagged(tmp_path: Path) -> None:
    md = dedent(
        """\
        ---
        name: vars
        description: A skill with declared variables.
        skl:
          schema_version: 1
          display_name: Vars
          status: draft
          enabled_platforms: []
          variables:
            - { name: company, description: Company name }
        ---

        # Vars
        ## Capabilities
        Refers to {{variables.company}}.
        ## Workflow
        1. Do.
        ## Edge Cases
        - None.
        ## Examples
        Example.
        """
    )
    skill_root = _make_skill(tmp_path, "ok-vars", md)
    report = lint_skill(skill_root)
    assert not any(f.rule == "unresolved-token" for f in report.findings)


# ---------------------------------------------------------------------------
# file selection
# ---------------------------------------------------------------------------


def test_compiled_platforms_skipped(tmp_path: Path) -> None:
    """Files under `platforms/` are not linted (derived from source)."""
    skill_root = _make_skill(tmp_path, "demo", _make_skill_md())
    compiled = skill_root / "platforms" / "claude-code" / "demo" / "SKILL.md"
    compiled.parent.mkdir(parents=True)
    compiled.write_text("body with em-dash —\n")
    report = lint_skill(skill_root)
    # The compiled artefact would normally trigger em-dash; assert it does not.
    assert not any(f.rule == "em-dash" and "platforms" in str(f.file) for f in report.findings)


def test_lints_sidecars_too(tmp_path: Path) -> None:
    skill_root = _make_skill(tmp_path, "demo", _make_skill_md())
    sidecars_dir = skill_root / "skl" / "platforms"
    sidecars_dir.mkdir(parents=True)
    (sidecars_dir / "vscode.yaml").write_text("note: em — dash leak\n")
    report = lint_skill(skill_root)
    assert any(f.rule == "em-dash" and "vscode.yaml" in str(f.file) for f in report.findings)


# ---------------------------------------------------------------------------
# apply_fixes
# ---------------------------------------------------------------------------


def test_apply_fixes_modifies_file(tmp_path: Path) -> None:
    skill_root = _make_skill(
        tmp_path,
        "fixy",
        _make_skill_md(body="Some — text. We optimize it.\n"),
    )
    report = lint_skill(skill_root)
    modified = apply_fixes(report.findings)
    assert modified
    final = (skill_root / "SKILL.md").read_text()
    assert "—" not in final
    assert "optimize" not in final
    assert "optimise" in final


def test_apply_fixes_no_change_for_unfixable(tmp_path: Path) -> None:
    skill_root = _make_skill(
        tmp_path,
        "leaky",
        _make_skill_md(body="Leak: AKIAIOSFODNN7EXAMPLE\n"),
    )
    report = lint_skill(skill_root)
    modified = apply_fixes(report.findings)
    assert not modified


# ---------------------------------------------------------------------------
# lint_repo + CLI
# ---------------------------------------------------------------------------


def test_lint_repo_with_no_skills_dir_returns_empty(tmp_path: Path) -> None:
    report = lint_repo(tmp_path)
    assert isinstance(report, LintReport)
    assert report.findings == []


def _minimal_repo(tmp_path: Path) -> Path:
    """Set up a manifest so the CLI can find the repo root."""
    repo = tmp_path / "host-repo"
    repo.mkdir()
    (repo / "skill-repo.yaml").write_text(
        f"""\
schema_version: 1
name: host-repo
visibility: internal
skl_version: ">={__version__},<99.0"
shared_kit:
  source: github.com/example/kit
  version: "1.0.0"
enabled_platforms: []
"""
    )
    return repo


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_cli_lint_exits_zero_on_clean_repo(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _minimal_repo(tmp_path)
    _make_skill(repo, "clean", _make_skill_md())
    monkeypatch.chdir(repo)
    result = runner.invoke(main, ["lint"])
    assert result.exit_code == 0, result.output
    assert "lint ok" in result.output


def test_cli_lint_exits_one_on_errors(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _minimal_repo(tmp_path)
    _make_skill(repo, "leaky", _make_skill_md(body="Leak — AKIAIOSFODNN7EXAMPLE\n"))
    monkeypatch.chdir(repo)
    result = runner.invoke(main, ["lint"])
    assert result.exit_code == 1, result.output
    assert "lint failed" in result.output


def test_cli_lint_exits_zero_with_warnings(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Warnings (US spellings, banned phrases) keep exit code 0."""
    repo = _minimal_repo(tmp_path)
    _make_skill(repo, "spelly", _make_skill_md(body="We organize stuff.\n"))
    monkeypatch.chdir(repo)
    result = runner.invoke(main, ["lint"])
    assert result.exit_code == 0, result.output
    assert "lint ok" in result.output
    assert "warning" in result.output


def test_cli_lint_fix_applies_changes(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _minimal_repo(tmp_path)
    skill_root = _make_skill(repo, "fixy", _make_skill_md(body="Em — dash and organize.\n"))
    monkeypatch.chdir(repo)
    result = runner.invoke(main, ["lint", "--fix"])
    final = (skill_root / "SKILL.md").read_text()
    assert "—" not in final
    assert "organise" in final
    assert "fixed" in result.output
    assert result.exit_code == 0, result.output


def test_cli_lint_outside_repo_errors(runner: CliRunner, tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(main, ["lint"])
        assert result.exit_code != 0
        assert "not inside a skill-host repo" in result.output


def test_lint_finding_dataclass_carries_all_fields(tmp_path: Path) -> None:
    skill_root = _make_skill(tmp_path, "demo", _make_skill_md(body="Em — dash.\n"))
    report = lint_skill(skill_root)
    em = next(f for f in report.findings if f.rule == "em-dash")
    assert isinstance(em, LintFinding)
    assert em.severity == "error"
    assert em.file.name == "SKILL.md"
    assert em.line > 0
    assert em.fix == ("—", " - ")
