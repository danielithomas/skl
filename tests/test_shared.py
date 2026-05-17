"""Tests for ``skl shared sync`` against local git fixture repos.

No network: a tmp_path-hosted git repo plays the role of ``ai-skills-shared``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from skl import shared
from skl.cli import main
from skl.init import init_repo


def _git(*args: str, cwd: Path | None = None) -> None:
    subprocess.run(
        ["git", *args],
        check=True,
        cwd=cwd,
        stdout=subprocess.DEVNULL,
    )


def _make_kit_repo(tmp_path: Path, *, tags: tuple[str, ...] = ("1.0.0",)) -> Path:
    """Create a local git repo that plays the role of a shared-kit source."""
    kit = tmp_path / "kit-source"
    kit.mkdir()
    (kit / "skill.config.yaml").write_text("style:\n  language: en-AU\n")
    (kit / "schemas").mkdir()
    (kit / "schemas" / "skill.frontmatter.schema.json").write_text('{"type": "object"}\n')

    _git("init", "--quiet", "--initial-branch=main", str(kit))
    _git("config", "user.email", "test@example.com", cwd=kit)
    _git("config", "user.name", "Test", cwd=kit)
    _git("add", ".", cwd=kit)
    _git("commit", "--quiet", "-m", "initial kit", cwd=kit)
    for tag in tags:
        _git("tag", tag, cwd=kit)
    return kit


def _scaffold_host(tmp_path: Path, *, kit_source: Path, version: str = "1.0.0") -> Path:
    """Scaffold a skill-host repo wired to a local kit source."""
    host = tmp_path / "host"
    init_repo(
        host,
        shared_kit_source=str(kit_source),
        shared_kit_version=version,
        no_git=True,
    )
    return host


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


# ---------------------------------------------------------------------------
# Library-level: sync_global
# ---------------------------------------------------------------------------


def test_sync_global_copies_files_and_returns_sha(tmp_path: Path) -> None:
    kit = _make_kit_repo(tmp_path)
    target = tmp_path / "out"

    version, sha = shared.sync_global(source=str(kit), version="1.0.0", target=target)

    assert version == "1.0.0"
    assert len(sha) == shared.SHORT_SHA_LENGTH
    assert (target / "skill.config.yaml").is_file()
    assert (target / "schemas" / "skill.frontmatter.schema.json").is_file()
    assert not (target / ".git").exists()
    assert (target / ".kit_version").read_text().strip() == "1.0.0"


def test_sync_global_latest_picks_highest_semver_tag(tmp_path: Path) -> None:
    kit = _make_kit_repo(tmp_path, tags=("1.0.0", "1.1.0", "2.0.0"))
    target = tmp_path / "out"

    version, _sha = shared.sync_global(source=str(kit), version="latest", target=target)

    assert version == "2.0.0"


def test_sync_global_raises_when_latest_but_no_tags(tmp_path: Path) -> None:
    kit = _make_kit_repo(tmp_path, tags=())
    target = tmp_path / "out"

    with pytest.raises(RuntimeError, match="has no tags"):
        shared.sync_global(source=str(kit), version="latest", target=target)


# ---------------------------------------------------------------------------
# Library-level: sync_repo_scoped
# ---------------------------------------------------------------------------


def test_sync_repo_scoped_populates_shared_and_updates_manifest(tmp_path: Path) -> None:
    kit = _make_kit_repo(tmp_path)
    host = _scaffold_host(tmp_path, kit_source=kit)

    version, sha = shared.sync_repo_scoped(host)

    assert version == "1.0.0"
    assert (host / "_shared" / "skill.config.yaml").is_file()
    assert (host / "_shared" / ".kit_version").read_text().strip() == "1.0.0"

    manifest_text = (host / "skill-repo.yaml").read_text()
    assert f"pinned_sha: {sha}" in manifest_text
    assert 'version: "1.0.0"' in manifest_text


def test_sync_repo_scoped_resolves_latest_sentinel(tmp_path: Path) -> None:
    kit = _make_kit_repo(tmp_path, tags=("1.0.0", "1.1.0"))
    host = _scaffold_host(tmp_path, kit_source=kit, version="latest")

    version, _sha = shared.sync_repo_scoped(host)

    assert version == "1.1.0"
    manifest_text = (host / "skill-repo.yaml").read_text()
    assert 'version: "1.1.0"' in manifest_text


def test_sync_repo_scoped_version_arg_overrides_manifest(tmp_path: Path) -> None:
    kit = _make_kit_repo(tmp_path, tags=("1.0.0", "1.1.0"))
    host = _scaffold_host(tmp_path, kit_source=kit, version="1.0.0")

    version, _sha = shared.sync_repo_scoped(host, version="1.1.0")

    assert version == "1.1.0"
    manifest_text = (host / "skill-repo.yaml").read_text()
    assert 'version: "1.1.0"' in manifest_text


def test_sync_repo_scoped_preserves_local_overlay(tmp_path: Path) -> None:
    kit = _make_kit_repo(tmp_path)
    host = _scaffold_host(tmp_path, kit_source=kit)

    overlay = host / "_shared" / "local"
    overlay.mkdir(parents=True)
    (overlay / "skill.config.yaml").write_text("override: true\n")

    shared.sync_repo_scoped(host)

    assert (host / "_shared" / "local" / "skill.config.yaml").read_text() == "override: true\n"
    assert (host / "_shared" / "skill.config.yaml").is_file()


def test_sync_repo_scoped_missing_source_errors(tmp_path: Path) -> None:
    host = tmp_path / "host"
    host.mkdir()
    (host / "skill-repo.yaml").write_text("schema_version: 1\nname: x\n")

    with pytest.raises(ValueError, match=r"shared_kit\.source"):
        shared.sync_repo_scoped(host)


# ---------------------------------------------------------------------------
# Source URL normalisation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("input_source", "expected"),
    [
        ("github.com/org/repo", "https://github.com/org/repo.git"),
        ("https://github.com/org/repo.git", "https://github.com/org/repo.git"),
        ("git@github.com:org/repo.git", "git@github.com:org/repo.git"),
        ("/local/path", "/local/path"),
    ],
)
def test_normalise_source(input_source: str, expected: str) -> None:
    assert shared._normalise_source(input_source) == expected


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------


def test_cli_shared_sync_outside_repo_errors(runner: CliRunner, tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(main, ["shared", "sync"])
        assert result.exit_code != 0
        assert "not inside a skill-host repo" in result.output


def test_cli_shared_sync_repo_scoped(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    kit = _make_kit_repo(tmp_path)
    host = _scaffold_host(tmp_path, kit_source=kit)
    monkeypatch.chdir(host)

    result = runner.invoke(main, ["shared", "sync"])

    assert result.exit_code == 0, result.output
    assert "synced shared kit @ 1.0.0" in result.output
    assert (host / "_shared" / "skill.config.yaml").is_file()


def test_cli_shared_sync_global_requires_source_and_version(
    runner: CliRunner, tmp_path: Path
) -> None:
    result = runner.invoke(main, ["shared", "sync", "--to", str(tmp_path / "out")])
    assert result.exit_code != 0
    assert "requires both --source and --version" in result.output


def test_cli_shared_sync_global_writes_to_target(runner: CliRunner, tmp_path: Path) -> None:
    kit = _make_kit_repo(tmp_path)
    target = tmp_path / "out"

    result = runner.invoke(
        main,
        [
            "shared",
            "sync",
            "--to",
            str(target),
            "--source",
            str(kit),
            "--version",
            "1.0.0",
        ],
    )

    assert result.exit_code == 0, result.output
    assert (target / "skill.config.yaml").is_file()
    assert (target / ".kit_version").read_text().strip() == "1.0.0"
