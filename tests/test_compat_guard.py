"""Tests for the global ``skl_version`` compatibility guard at the CLI entry.

The guard fires before any subcommand dispatches when ``skl`` is invoked from
inside a skill-host repo, except for subcommands in
:data:`skl.cli.COMPAT_GUARD_SKIP`. See SKL-003 (original guard) and SKL-010
(escape hatch, fail-fast on parse failure) in ``docs/decisions/``.
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
    """`skl init` is exempt - scaffolds a skill even when the manifest pins out-of-range."""
    _write_manifest(tmp_path / "skill-repo.yaml", _manifest_with_range(">=99.0,<100.0"))
    monkeypatch.chdir(tmp_path)

    # Inside a repo with an incompatible pin, `skl init <skill>` should still
    # run the repo-scoped scaffold because init is in COMPAT_GUARD_SKIP.
    result = runner.invoke(main, ["init", "new-skill"])

    assert result.exit_code == 0, result.output
    assert "compatibility check failed" not in result.output
    assert (tmp_path / "skills" / "new-skill" / "SKILL.md").is_file()


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


def test_guard_fails_fast_on_unparseable_manifest(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unparseable manifest exits 4 with a parse-failure message (SKL-010)."""
    (tmp_path / "skill-repo.yaml").write_text("schema_version: 1\nname: [unclosed\n")
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(main, ["shared", "sync"])

    assert result.exit_code == 4, result.output
    assert "compatibility check failed" in result.output
    assert "could not be parsed" in result.output
    assert "skl validate" in result.output


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


# ---------------------------------------------------------------------------
# SKL-010: SKL_IGNORE_COMPAT env var escape hatch
# ---------------------------------------------------------------------------


def test_env_var_bypasses_mismatch(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SKL_IGNORE_COMPAT lets an out-of-range invocation proceed with a warning."""
    _write_manifest(tmp_path / "skill-repo.yaml", _manifest_with_range(">=99.0,<100.0"))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SKL_IGNORE_COMPAT", "1")

    result = runner.invoke(main, ["shared", "sync"])

    # The guard must not exit 4 - the bypass converts the failure into a warning.
    assert "compatibility check failed" not in result.output
    assert "compatibility guard bypassed via SKL_IGNORE_COMPAT" in result.output
    # Detail is included so the user sees what they bypassed.
    assert "outside the manifest's skl_version range" in result.output
    # The downstream command runs (and fails on its own concerns - not our problem here).
    assert result.exit_code != 4, result.output


def test_env_var_warns_even_when_compatible(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Loud bypass: warning fires even when the version is in range."""
    _write_manifest(
        tmp_path / "skill-repo.yaml",
        _manifest_with_range(f">={__version__},<99.0"),
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SKL_IGNORE_COMPAT", "1")

    result = runner.invoke(main, ["shared", "sync"])

    assert "compatibility guard bypassed via SKL_IGNORE_COMPAT" in result.output
    # No detail to surface when the version is actually compatible.
    assert "outside the manifest's skl_version range" not in result.output


def test_env_var_does_not_bypass_parse_failure(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Parse failure is non-bypassable; the env var has no effect on it."""
    (tmp_path / "skill-repo.yaml").write_text("schema_version: 1\nname: [unclosed\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SKL_IGNORE_COMPAT", "1")

    result = runner.invoke(main, ["shared", "sync"])

    assert result.exit_code == 4, result.output
    assert "could not be parsed" in result.output
    # The bypass warning must not appear; the parse error is the only output.
    assert "compatibility guard bypassed" not in result.output


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "Yes", "on", " 1 "])
def test_env_var_truthy_values(
    runner: CliRunner,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    """All documented truthy spellings (case-insensitive, whitespace-tolerant) bypass."""
    _write_manifest(tmp_path / "skill-repo.yaml", _manifest_with_range(">=99.0,<100.0"))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SKL_IGNORE_COMPAT", value)

    result = runner.invoke(main, ["shared", "sync"])

    assert "compatibility guard bypassed" in result.output, f"value={value!r}"
    assert result.exit_code != 4


@pytest.mark.parametrize("value", ["0", "false", "no", "off", "", "foo"])
def test_env_var_falsy_values_do_not_bypass(
    runner: CliRunner,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    """Non-truthy values leave the guard intact."""
    _write_manifest(tmp_path / "skill-repo.yaml", _manifest_with_range(">=99.0,<100.0"))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SKL_IGNORE_COMPAT", value)

    result = runner.invoke(main, ["shared", "sync"])

    assert result.exit_code == 4, f"value={value!r}: {result.output}"
    assert "compatibility check failed" in result.output
    assert "compatibility guard bypassed" not in result.output
