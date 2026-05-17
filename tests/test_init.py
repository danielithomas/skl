"""Tests for `skl init` global form.

Covers the layout produced on disk, manifest contents, flag handling, and
the safety rails (rejecting bad names, existing targets, and invocation
from inside an existing skill-host repo).
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
)


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


def test_cli_init_refuses_inside_existing_repo(runner: CliRunner, tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path("skill-repo.yaml").write_text("schema_version: 1\n")
        result = runner.invoke(main, ["init", "another-repo", "--no-git"])
        assert result.exit_code != 0
        assert "inside an existing skill-host repo" in result.output


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
