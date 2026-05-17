"""Tests for ``skl validate`` (manifest schema, compatibility, shared-kit drift).

Other check families (frontmatter, body, knowledge contracts, cross-repo deps,
values declarations) are framed as skipped in the v1 implementation and only
verified at the orchestrator level here.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest
from click.testing import CliRunner

from skl import __version__
from skl.cli import main
from skl.validate import (
    CheckResult,
    ValidationReport,
    exit_code,
    validate_repo,
)


def _write_manifest(path: Path, content: str) -> None:
    path.write_text(dedent(content))


def _minimal_valid_manifest(skl_range: str | None = None) -> str:
    """Produce a manifest body that passes schema + compatibility checks."""
    skl_range = skl_range or f">={__version__},<99.0"
    return f"""\
        schema_version: 1
        name: example-host
        visibility: internal
        skl_version: "{skl_range}"
        shared_kit:
          source: github.com/example/kit
          version: "1.0.0"
        enabled_platforms:
          - claude-code
    """


def _result(report: ValidationReport, name: str) -> CheckResult:
    for result in report.results:
        if result.name == name:
            return result
    raise AssertionError(f"no check named {name!r} in report: {[r.name for r in report.results]}")


# ---------------------------------------------------------------------------
# validate_repo: end-to-end behaviour
# ---------------------------------------------------------------------------


def test_validate_repo_passes_on_minimal_valid_manifest(tmp_path: Path) -> None:
    _write_manifest(tmp_path / "skill-repo.yaml", _minimal_valid_manifest())
    report = validate_repo(tmp_path)
    assert not report.has_errors
    assert _result(report, "manifest").passed
    assert _result(report, "compatibility").passed


def test_validate_repo_errors_when_manifest_missing(tmp_path: Path) -> None:
    report = validate_repo(tmp_path)
    assert report.has_errors
    assert "no skill-repo.yaml" in _result(report, "manifest").errors[0]


def test_validate_repo_errors_on_unparseable_yaml(tmp_path: Path) -> None:
    (tmp_path / "skill-repo.yaml").write_text("schema_version: 1\nname: [unclosed\n")
    report = validate_repo(tmp_path)
    assert report.has_errors
    assert "failed to parse" in _result(report, "manifest").errors[0]


def test_validate_repo_includes_deferred_check_stubs(tmp_path: Path) -> None:
    _write_manifest(tmp_path / "skill-repo.yaml", _minimal_valid_manifest())
    report = validate_repo(tmp_path)
    skipped_names = {r.name for r in report.results if r.skipped}
    assert "frontmatter" in skipped_names
    assert "body" in skipped_names
    assert "knowledge-contracts" in skipped_names
    assert "values-declarations" in skipped_names


# ---------------------------------------------------------------------------
# manifest schema check
# ---------------------------------------------------------------------------


def test_manifest_schema_flags_missing_required_field(tmp_path: Path) -> None:
    _write_manifest(
        tmp_path / "skill-repo.yaml",
        """\
        schema_version: 1
        visibility: internal
        skl_version: ">=0.0,<99.0"
        shared_kit:
          source: github.com/example/kit
          version: "1.0.0"
        enabled_platforms: []
        """,
    )
    report = validate_repo(tmp_path)
    errors = _result(report, "manifest").errors
    assert any("'name' is a required property" in e for e in errors)


def test_manifest_schema_rejects_bad_name_pattern(tmp_path: Path) -> None:
    _write_manifest(
        tmp_path / "skill-repo.yaml",
        """\
        schema_version: 1
        name: NotKebab_Name
        visibility: internal
        skl_version: ">=0.0,<99.0"
        shared_kit:
          source: github.com/example/kit
          version: "1.0.0"
        enabled_platforms: []
        """,
    )
    report = validate_repo(tmp_path)
    errors = _result(report, "manifest").errors
    assert any("name" in e and "does not match" in e for e in errors)


def test_manifest_schema_rejects_unknown_platform(tmp_path: Path) -> None:
    _write_manifest(
        tmp_path / "skill-repo.yaml",
        """\
        schema_version: 1
        name: example-host
        visibility: internal
        skl_version: ">=0.0,<99.0"
        shared_kit:
          source: github.com/example/kit
          version: "1.0.0"
        enabled_platforms:
          - nope-not-a-platform
        """,
    )
    report = validate_repo(tmp_path)
    errors = _result(report, "manifest").errors
    assert any("nope-not-a-platform" in e for e in errors)


def test_manifest_schema_rejects_bad_visibility(tmp_path: Path) -> None:
    _write_manifest(
        tmp_path / "skill-repo.yaml",
        """\
        schema_version: 1
        name: example-host
        visibility: private
        skl_version: ">=0.0,<99.0"
        shared_kit:
          source: github.com/example/kit
          version: "1.0.0"
        enabled_platforms: []
        """,
    )
    report = validate_repo(tmp_path)
    errors = _result(report, "manifest").errors
    assert any("'private'" in e for e in errors)


def test_manifest_schema_rejects_unknown_top_level_key(tmp_path: Path) -> None:
    _write_manifest(
        tmp_path / "skill-repo.yaml",
        """\
        schema_version: 1
        name: example-host
        visibility: internal
        skl_version: ">=0.0,<99.0"
        shared_kit:
          source: github.com/example/kit
          version: "1.0.0"
        enabled_platforms: []
        what_is_this: surprise
        """,
    )
    report = validate_repo(tmp_path)
    errors = _result(report, "manifest").errors
    assert any("what_is_this" in e for e in errors)


# ---------------------------------------------------------------------------
# compatibility check
# ---------------------------------------------------------------------------


def test_compatibility_passes_for_in_range_version(tmp_path: Path) -> None:
    _write_manifest(tmp_path / "skill-repo.yaml", _minimal_valid_manifest(">=0.0,<99.0"))
    report = validate_repo(tmp_path)
    assert _result(report, "compatibility").passed


def test_compatibility_fails_for_out_of_range_version(tmp_path: Path) -> None:
    _write_manifest(tmp_path / "skill-repo.yaml", _minimal_valid_manifest(">=99.0,<100.0"))
    report = validate_repo(tmp_path)
    compat = _result(report, "compatibility")
    assert compat.errors
    assert report.compatibility_failed
    assert exit_code(report) == 4


def test_compatibility_flags_invalid_specifier(tmp_path: Path) -> None:
    _write_manifest(tmp_path / "skill-repo.yaml", _minimal_valid_manifest("not-a-specifier"))
    report = validate_repo(tmp_path)
    errors = _result(report, "compatibility").errors
    assert any("not a valid specifier" in e for e in errors)


# ---------------------------------------------------------------------------
# shared-kit drift check
# ---------------------------------------------------------------------------


def test_drift_warns_on_latest_sentinel(tmp_path: Path) -> None:
    _write_manifest(
        tmp_path / "skill-repo.yaml",
        """\
        schema_version: 1
        name: example-host
        visibility: internal
        skl_version: ">=0.0,<99.0"
        shared_kit:
          source: github.com/example/kit
          version: "latest"
        enabled_platforms: []
        """,
    )
    report = validate_repo(tmp_path)
    warnings = _result(report, "shared-kit-drift").warnings
    assert any("'latest' sentinel" in w for w in warnings)


def test_drift_warns_when_kit_version_file_missing(tmp_path: Path) -> None:
    _write_manifest(tmp_path / "skill-repo.yaml", _minimal_valid_manifest())
    report = validate_repo(tmp_path)
    warnings = _result(report, "shared-kit-drift").warnings
    assert any(".kit_version is missing" in w for w in warnings)


def test_drift_warns_when_versions_diverge(tmp_path: Path) -> None:
    _write_manifest(tmp_path / "skill-repo.yaml", _minimal_valid_manifest())
    (tmp_path / "_shared").mkdir()
    (tmp_path / "_shared" / ".kit_version").write_text("0.9.0\n")
    report = validate_repo(tmp_path)
    warnings = _result(report, "shared-kit-drift").warnings
    assert any("drift" in w and "'1.0.0'" in w and "'0.9.0'" in w for w in warnings)


def test_drift_silent_when_versions_match(tmp_path: Path) -> None:
    _write_manifest(tmp_path / "skill-repo.yaml", _minimal_valid_manifest())
    (tmp_path / "_shared").mkdir()
    (tmp_path / "_shared" / ".kit_version").write_text("1.0.0\n")
    report = validate_repo(tmp_path)
    drift = _result(report, "shared-kit-drift")
    assert not drift.errors
    assert not drift.warnings


# ---------------------------------------------------------------------------
# exit_code mapping
# ---------------------------------------------------------------------------


def test_exit_code_zero_on_clean_report() -> None:
    report = ValidationReport(results=[CheckResult(name="manifest")])
    assert exit_code(report) == 0


def test_exit_code_one_on_general_error() -> None:
    report = ValidationReport(results=[CheckResult(name="manifest", errors=["bad"])])
    assert exit_code(report) == 1


def test_exit_code_four_on_compatibility_failure() -> None:
    report = ValidationReport(
        results=[CheckResult(name="compatibility", errors=["mismatch"])],
        compatibility_failed=True,
    )
    assert exit_code(report) == 4


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_cli_validate_outside_repo_errors(runner: CliRunner, tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(main, ["validate"])
        assert result.exit_code != 0
        assert "not inside a skill-host repo" in result.output


def test_cli_validate_passes_on_valid_manifest(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_manifest(tmp_path / "skill-repo.yaml", _minimal_valid_manifest())
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(main, ["validate"])

    assert result.exit_code == 0, result.output
    assert "validation ok" in result.output


def test_cli_validate_exit_one_on_schema_failure(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_manifest(
        tmp_path / "skill-repo.yaml",
        """\
        schema_version: 1
        name: Not-Kebab
        visibility: internal
        skl_version: ">=0.0,<99.0"
        shared_kit:
          source: github.com/example/kit
          version: "1.0.0"
        enabled_platforms: []
        """,
    )
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(main, ["validate"])

    assert result.exit_code == 1, result.output
    assert "validation failed" in result.output


def test_cli_validate_exit_four_on_compat_failure(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_manifest(tmp_path / "skill-repo.yaml", _minimal_valid_manifest(">=99.0,<100.0"))
    monkeypatch.chdir(tmp_path)

    # `validate` is in COMPAT_GUARD_SKIP per SKL-003, so the global guard
    # does not short-circuit here - the compat failure surfaces via check 8.
    result = runner.invoke(main, ["validate"])

    assert result.exit_code == 4, result.output
    assert "skl_version incompatible" in result.output


def test_cli_validate_skill_flag_raises_not_implemented(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_manifest(tmp_path / "skill-repo.yaml", _minimal_valid_manifest())
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(main, ["validate", "--skill", "casey"], standalone_mode=False)

    assert isinstance(result.exception, NotImplementedError)
    assert "not yet implemented" in str(result.exception)


def test_cli_validate_all_flag_raises_not_implemented(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_manifest(tmp_path / "skill-repo.yaml", _minimal_valid_manifest())
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(main, ["validate", "--all"], standalone_mode=False)

    assert isinstance(result.exception, NotImplementedError)
    assert "not yet implemented" in str(result.exception)
