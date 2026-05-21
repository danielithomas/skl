"""Tests for ``skl init`` (global + repo-scoped forms).

Global form covers disk layout, manifest contents, flag handling, and the
safety rails (rejecting bad names / existing targets). Repo-scoped form
covers SKILL.md scaffolding, sidecar emission per ``--platform``, the M365
schema-version pin (per SKL-009), and validation of the scaffolded output.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from skl import __version__
from skl.cli import main
from skl.init import (
    DEFAULT_SHARED_KIT_SOURCE,
    DEFAULT_SHARED_KIT_VERSION,
    compatible_version_range,
    find_skill_repo_root,
    init_repo,
    init_skill,
    kebab_to_display_name,
)
from skl.skill_md import parse_skill_md
from skl.validate import validate_repo


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture(autouse=True)
def _stub_shared_sync(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace shared.sync_repo_scoped with a no-op so init tests do not clone.

    Tests that want to exercise the real sync path opt in by overriding this
    again on a per-test basis.
    """
    monkeypatch.setattr(
        "skl.init.shared.sync_repo_scoped",
        lambda _repo_root, version=None: ("stub-version", "0000000000ab"),
    )


# ---------------------------------------------------------------------------
# init_repo: direct function tests
# ---------------------------------------------------------------------------


def test_init_repo_creates_expected_layout(tmp_path: Path) -> None:
    target = tmp_path / "my-skills"
    init_repo(target, no_git=True)

    assert (target / "skill-repo.yaml").is_file()
    assert (target / "README.md").is_file()
    assert (target / "LICENSE").is_file()
    assert (target / ".gitignore").is_file()
    assert (target / "skills").is_dir()
    assert not (target / ".git").exists()


def test_init_repo_manifest_has_required_fields(tmp_path: Path) -> None:
    target = tmp_path / "my-skills"
    init_repo(target, no_git=True)

    manifest = (target / "skill-repo.yaml").read_text()
    assert "schema_version: 1" in manifest
    assert "name: my-skills" in manifest
    assert "visibility: internal" in manifest
    assert f'skl_version: "{compatible_version_range()}"' in manifest
    assert f"source: {DEFAULT_SHARED_KIT_SOURCE}" in manifest
    assert f'version: "{DEFAULT_SHARED_KIT_VERSION}"' in manifest
    assert "enabled_platforms: []" in manifest
    assert "output_language: en-AU" in manifest
    # pinned_sha must NOT be present; it is written by `skl shared sync`.
    assert "pinned_sha:" not in manifest


def test_init_repo_respects_shared_kit_flags(tmp_path: Path) -> None:
    target = tmp_path / "my-skills"
    init_repo(
        target,
        shared_kit_source="github.com/example/custom-kit",
        shared_kit_version="2.1.0",
        no_git=True,
    )

    manifest = (target / "skill-repo.yaml").read_text()
    assert "source: github.com/example/custom-kit" in manifest
    assert 'version: "2.1.0"' in manifest


def test_init_repo_runs_git_init_by_default(tmp_path: Path) -> None:
    target = tmp_path / "my-skills"
    init_repo(target)

    assert (target / ".git").is_dir()


def test_init_repo_rejects_invalid_name(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="must match"):
        init_repo(tmp_path / "Invalid_Name", no_git=True)


def test_init_repo_rejects_existing_target(tmp_path: Path) -> None:
    target = tmp_path / "existing"
    target.mkdir()
    with pytest.raises(FileExistsError):
        init_repo(target, no_git=True)


def test_init_repo_reports_successful_shared_sync(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    init_repo(tmp_path / "my-skills", no_git=True)
    captured = capsys.readouterr()
    assert "fetched shared kit @ stub-version" in captured.err


def test_init_repo_warns_when_shared_sync_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def _boom(_repo_root: Path, version: str | None = None) -> tuple[str, str]:
        raise RuntimeError("upstream unreachable")

    monkeypatch.setattr("skl.init.shared.sync_repo_scoped", _boom)

    init_repo(tmp_path / "my-skills", no_git=True)

    captured = capsys.readouterr()
    assert "shared sync failed" in captured.err
    assert "upstream unreachable" in captured.err
    # Repo still scaffolded despite the sync failure.
    assert (tmp_path / "my-skills" / "skill-repo.yaml").is_file()


# ---------------------------------------------------------------------------
# compatible_version_range
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        ("0.0.1", ">=0.0.1,<0.1"),
        ("0.4.2", ">=0.4.2,<0.5"),
        ("1.0.0", ">=1.0,<2.0"),
        ("2.3.4", ">=2.0,<3.0"),
    ],
)
def test_compatible_version_range(version: str, expected: str) -> None:
    assert compatible_version_range(version) == expected


def test_compatible_version_range_uses_package_version_by_default() -> None:
    range_ = compatible_version_range()
    assert __version__ in range_


# ---------------------------------------------------------------------------
# find_skill_repo_root
# ---------------------------------------------------------------------------


def test_find_skill_repo_root_walks_up(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "nested" / "deeply").mkdir(parents=True)
    (repo / "skill-repo.yaml").write_text("schema_version: 1\n")

    assert find_skill_repo_root(repo / "nested" / "deeply") == repo


def test_find_skill_repo_root_returns_none_outside_repo(tmp_path: Path) -> None:
    assert find_skill_repo_root(tmp_path) is None


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------


def test_cli_init_scaffolds_repo(runner: CliRunner, tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(main, ["init", "my-skills", "--no-git"])
        assert result.exit_code == 0, result.output
        assert "scaffolded skill-host repo" in result.output
        assert Path("my-skills/skill-repo.yaml").is_file()


def test_cli_init_inside_repo_scaffolds_a_skill(runner: CliRunner, tmp_path: Path) -> None:
    """Inside an existing skill-host repo, `skl init <name>` scaffolds a skill."""
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path("skill-repo.yaml").write_text("schema_version: 1\n")
        result = runner.invoke(main, ["init", "my-skill"])
        assert result.exit_code == 0, result.output
        assert "scaffolded skill" in result.output
        assert Path("skills/my-skill/SKILL.md").is_file()


def test_cli_init_inside_repo_rejects_platform_flag_for_global_form(
    runner: CliRunner, tmp_path: Path
) -> None:
    """`--platform` outside a repo is a misuse - it's a repo-scoped flag."""
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(main, ["init", "my-skills", "--platform", "claude-code"])
        assert result.exit_code != 0
        assert "--platform is only valid in the repo-scoped form" in result.output


def test_cli_init_rejects_bad_name(runner: CliRunner, tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(main, ["init", "Bad_Name", "--no-git"])
        assert result.exit_code != 0
        assert "must match" in result.output


def test_cli_init_no_git_flag(runner: CliRunner, tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(main, ["init", "my-skills", "--no-git"])
        assert result.exit_code == 0, result.output
        assert not Path("my-skills/.git").exists()


def test_cli_init_default_runs_git_init(runner: CliRunner, tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        # Skip if git is not available on the runner.
        if subprocess.run(["git", "--version"], capture_output=True).returncode != 0:
            pytest.skip("git not available")
        result = runner.invoke(main, ["init", "my-skills"])
        assert result.exit_code == 0, result.output
        assert Path("my-skills/.git").is_dir()


# ---------------------------------------------------------------------------
# init_skill: repo-scoped form (direct function)
# ---------------------------------------------------------------------------


def _minimal_repo(tmp_path: Path) -> Path:
    """Set up a minimal skill-host repo (just enough that find_skill_repo_root finds it)."""
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


def test_init_skill_creates_skill_folder(tmp_path: Path) -> None:
    repo = _minimal_repo(tmp_path)
    skill_root = init_skill(repo, "my-skill")
    assert skill_root == repo / "skills" / "my-skill"
    assert (skill_root / "SKILL.md").is_file()
    # No platforms requested -> no sidecars
    assert not (skill_root / "skl").exists()


def test_init_skill_substitutes_name_and_display_name(tmp_path: Path) -> None:
    repo = _minimal_repo(tmp_path)
    init_skill(repo, "casey-case-studies")
    skill = parse_skill_md(repo / "skills" / "casey-case-studies" / "SKILL.md")
    assert skill.name == "casey-case-studies"
    assert skill.display_name == "Casey Case Studies"


def test_init_skill_writes_enabled_platforms(tmp_path: Path) -> None:
    repo = _minimal_repo(tmp_path)
    init_skill(repo, "demo", platforms=("claude-code", "m365"))
    skill = parse_skill_md(repo / "skills" / "demo" / "SKILL.md")
    assert skill.enabled_platforms == ["claude-code", "m365"]


def test_init_skill_scaffolds_m365_sidecar_with_default_schema(tmp_path: Path) -> None:
    repo = _minimal_repo(tmp_path)
    init_skill(repo, "demo", platforms=("m365",))
    m365 = repo / "skills" / "demo" / "skl" / "platforms" / "m365.yaml"
    assert m365.is_file()
    # The bundled kit default is "1.7" per SKL-009; the template substitutes it
    # into `schema_version: "<default>"`.
    assert 'schema_version: "1.7"' in m365.read_text()


def test_init_skill_scaffolds_copilot_studio_and_vscode_sidecars(tmp_path: Path) -> None:
    repo = _minimal_repo(tmp_path)
    init_skill(repo, "demo", platforms=("copilot-studio", "vscode"))
    sidecars_dir = repo / "skills" / "demo" / "skl" / "platforms"
    assert (sidecars_dir / "copilot-studio.yaml").is_file()
    assert (sidecars_dir / "vscode.yaml").is_file()
    assert not (sidecars_dir / "m365.yaml").exists()


def test_init_skill_skips_sidecars_for_skills_native_platforms(tmp_path: Path) -> None:
    """claude-code / claude-cowork / ms-cowork need no sidecar (compile is a copy)."""
    repo = _minimal_repo(tmp_path)
    init_skill(repo, "demo", platforms=("claude-code", "claude-cowork", "ms-cowork"))
    assert not (repo / "skills" / "demo" / "skl").exists()


def test_init_skill_rejects_existing_folder(tmp_path: Path) -> None:
    repo = _minimal_repo(tmp_path)
    init_skill(repo, "demo")
    with pytest.raises(FileExistsError):
        init_skill(repo, "demo")


def test_init_skill_rejects_bad_name(tmp_path: Path) -> None:
    repo = _minimal_repo(tmp_path)
    with pytest.raises(ValueError, match="must match"):
        init_skill(repo, "Bad_Name")


def test_init_skill_rejects_unknown_platform(tmp_path: Path) -> None:
    repo = _minimal_repo(tmp_path)
    with pytest.raises(ValueError, match="unknown platform"):
        init_skill(repo, "demo", platforms=("imaginary-platform",))


def test_scaffolded_skill_passes_skl_validate(tmp_path: Path) -> None:
    """The bundled scaffold produces a SKILL.md that `skl validate` accepts."""
    repo = _minimal_repo(tmp_path)
    init_skill(repo, "demo", platforms=("claude-code",))
    report = validate_repo(repo)
    assert not report.has_errors, (
        f"validate errors: {[r.errors for r in report.results if r.errors]}"
    )


@pytest.mark.parametrize(
    "kebab,expected",
    [
        ("casey", "Casey"),
        ("casey-case-studies", "Casey Case Studies"),
        ("ea-assessment", "Ea Assessment"),
    ],
)
def test_kebab_to_display_name(kebab: str, expected: str) -> None:
    assert kebab_to_display_name(kebab) == expected


# ---------------------------------------------------------------------------
# CLI integration: repo-scoped form
# ---------------------------------------------------------------------------


def test_cli_init_repo_scoped_with_platform(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _minimal_repo(tmp_path)
    monkeypatch.chdir(repo)
    result = runner.invoke(main, ["init", "demo", "--platform", "copilot-studio"])
    assert result.exit_code == 0, result.output
    assert (repo / "skills" / "demo" / "SKILL.md").is_file()
    assert (repo / "skills" / "demo" / "skl" / "platforms" / "copilot-studio.yaml").is_file()


def test_cli_init_repo_scoped_warns_on_global_flags(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Global-form flags inside a repo emit a warning but do not block the scaffold."""
    repo = _minimal_repo(tmp_path)
    monkeypatch.chdir(repo)
    result = runner.invoke(main, ["init", "demo", "--no-git"])
    assert result.exit_code == 0, result.output
    assert "global-form flags" in result.output
    assert (repo / "skills" / "demo" / "SKILL.md").is_file()


def test_cli_init_repo_scoped_rejects_bad_skill_name(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _minimal_repo(tmp_path)
    monkeypatch.chdir(repo)
    result = runner.invoke(main, ["init", "Bad_Name"])
    assert result.exit_code != 0
    assert "must match" in result.output
