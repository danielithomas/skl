"""Smoke tests for the skl CLI."""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from skl import __version__
from skl.cli import main


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_version_flag(runner: CliRunner) -> None:
    """`skl --version` prints the package version and exits cleanly."""
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_help_flag(runner: CliRunner) -> None:
    """`skl --help` lists the documented top-level verbs."""
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    for verb in ("init", "validate", "compile", "budget", "test", "deploy"):
        assert verb in result.output


@pytest.mark.parametrize(
    "command",
    [
        ["budget"],
        ["test"],
        ["deploy", "--skill", "casey", "--platform", "claude-code"],
        ["values", "check"],
        ["secrets", "list"],
    ],
)
def test_unimplemented_verbs_raise(runner: CliRunner, command: list[str]) -> None:
    """Documented but unimplemented verbs raise NotImplementedError pointing to the spec."""
    result = runner.invoke(main, command, standalone_mode=False)
    assert isinstance(result.exception, NotImplementedError)
    assert "docs/spec/cli.md" in str(result.exception)
