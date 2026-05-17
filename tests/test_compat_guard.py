"""Tests for the global ``skl_version`` compatibility guard at the CLI entry.

The guard fires before any subcommand dispatches when ``skl`` is invoked from
inside a skill-host repo, except for subcommands in
:data:`skl.cli.COMPAT_GUARD_SKIP`. See SKL-003 in ``docs/decisions/``.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest
from click.testing import CliRunner

from skl import __version__
from skl.cli import COMPAT_GUARD_SKIP, main


def _write_manifest(path: Path, content: str) -> None:
    path.write_text(dedent(content))


def _manifest_with_range(skl_range: str) -> str:
    return f"""\
        schema_version: 1
        name: example-host
        visibility: internal
        skl_version: "{skl_range}"
        shared_kit:
          source: github.com/example/kit
          version: "1.0.0"
        enabled_platforms: []
    """


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_guard_fires_for_non_exempt_command(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`skl shared sync` from an incompatible manifest exits 4 before sync runs."""
    _write_manifest(tmp_path / "skill-repo.yaml", _manifest_with_range(">=99.0,<100.0"))
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(main, ["shared", "sync"])

    assert result.exit_code == 4, result.output
    assert "compatibility check failed" in result.output
    assert "outside the manifest's skl_version range" in result.output


def test_guard_skipped_for_init(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`skl init` is exempt; the existing-repo refusal surfaces instead of the guard."""
    _write_manifest(tmp_path / "skill-repo.yaml", _manifest_with_range(">=99.0,<100.0"))
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(main, ["init", "another-repo", "--no-git"])

    assert result.exit_code != 0
    assert "inside an existing skill-host repo" in result.output
    # Specifically not the guard error:
    assert "compatibility check failed" not in result.output


def test_guard_skipped_for_validate(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`skl validate` is exempt; full report runs and compat surfaces via check 8."""
    _write_manifest(tmp_path / "skill-repo.yaml", _manifest_with_range(">=99.0,<100.0"))
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(main, ["validate"])

    assert result.exit_code == 4, result.output
    assert "skl_version incompatible" in result.output
    # The guard's specific message must NOT appear; the full report should.
    assert "compatibility check failed" not in result.output


def test_guard_silent_outside_skill_host_repo(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No manifest present -> guard is a no-op; commands fail with their own messages."""
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(main, ["shared", "sync"])

    assert "compatibility check failed" not in result.output
    assert "not inside a skill-host repo" in result.output


def test_guard_tolerates_unparseable_manifest(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unparseable manifest defers to `skl validate`; the guard does not fail."""
    (tmp_path / "skill-repo.yaml").write_text("schema_version: 1\nname: [unclosed\n")
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(main, ["shared", "sync"])

    # The guard should not surface its own compat error against a manifest it
    # could not parse - let `skl validate` report the parse error instead.
    assert "compatibility check failed" not in result.output


def test_guard_silent_when_manifest_has_no_skl_version(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Missing `skl_version` field is a schema error, not a guard concern."""
    (tmp_path / "skill-repo.yaml").write_text(
        "schema_version: 1\nname: example-host\nvisibility: internal\n"
    )
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(main, ["shared", "sync"])

    assert "compatibility check failed" not in result.output


def test_guard_passes_for_compatible_version(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Compatible manifest -> guard returns silently; downstream command runs as usual."""
    _write_manifest(
        tmp_path / "skill-repo.yaml",
        _manifest_with_range(f">={__version__},<99.0"),
    )
    monkeypatch.chdir(tmp_path)

    # `shared sync` will fail on the unreachable kit source, but the guard
    # must not be the cause of the failure.
    result = runner.invoke(main, ["shared", "sync"])

    assert "compatibility check failed" not in result.output


def test_compat_guard_skip_contents() -> None:
    """The skip list must include `init` and `validate` per SKL-003."""
    assert "init" in COMPAT_GUARD_SKIP
    assert "validate" in COMPAT_GUARD_SKIP
