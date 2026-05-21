"""Tests for ``skl validate``.

Covers all implemented check families: manifest, compatibility,
shared-kit drift, frontmatter, body, sidecars, knowledge-contracts,
values-declarations. Cross-repo dependencies remains deferred and is
only verified at the orchestrator level (single ``skipped`` entry).
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


def _make_skill(
    repo_root: Path,
    name: str,
    skill_md: str,
    sidecars: dict[str, str] | None = None,
) -> Path:
    """Scaffold a skill folder under ``<repo_root>/skills/<name>/``."""
    skill_root = repo_root / "skills" / name
    skill_root.mkdir(parents=True)
    (skill_root / "SKILL.md").write_text(dedent(skill_md))
    if sidecars:
        platforms_dir = skill_root / "skl" / "platforms"
        platforms_dir.mkdir(parents=True)
        for platform_id, content in sidecars.items():
            (platforms_dir / f"{platform_id}.yaml").write_text(dedent(content))
    return skill_root


def _valid_skill_md(
    *,
    name: str = "example-skill",
    platforms: tuple[str, ...] = ("claude-code",),
    knowledge: bool = False,
    tools: bool = False,
    extra_body: str = "",
) -> str:
    """A SKILL.md that passes every check family by default.

    Built as a plain string without leading indentation so it is safe to
    write directly to disk (no ``dedent`` needed).
    """
    platforms_yaml = ", ".join(platforms)
    lines = [
        "---",
        f"name: {name}",
        "description: An example skill for testing.",
        "skl:",
        "  schema_version: 1",
        "  display_name: Example Skill",
        "  status: active",
        f"  enabled_platforms: [{platforms_yaml}]",
    ]
    if knowledge:
        lines.append("  knowledge:")
        lines.append("    - { id: kb, contract: kb.md }")
    if tools:
        lines.append("  tools:")
        lines.append("    - { id: web_fetch }")
    lines.extend(
        [
            "---",
            "",
            "# Example Skill",
            "",
            "## Capabilities",
            "- Do things",
            "",
        ]
    )
    if knowledge:
        lines.extend(["## Knowledge Sources", "- The kb knowledge base.", ""])
    if tools:
        lines.extend(["## Tools", "- web_fetch", ""])
    lines.extend(
        [
            "## Workflow",
            "1. Do.",
            "",
            "## Edge Cases",
            "- Nothing to do.",
            "",
            "## Examples",
            "Example use.",
        ]
    )
    if extra_body:
        lines.append("")
        lines.append(extra_body)
    return "\n".join(lines) + "\n"


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


def test_per_skill_checks_skip_when_no_skills_present(tmp_path: Path) -> None:
    """With no `skills/` directory the per-skill check families skip with a clear reason."""
    _write_manifest(tmp_path / "skill-repo.yaml", _minimal_valid_manifest())
    report = validate_repo(tmp_path)
    for name in ("frontmatter", "body", "sidecars", "knowledge-contracts", "values-declarations"):
        check = _result(report, name)
        assert check.skipped, f"{name} should skip when no skills/ directory present"
        assert check.skip_reason and "no skills" in check.skip_reason.lower()


def test_only_cross_repo_dependencies_remains_deferred(tmp_path: Path) -> None:
    """Cross-repo dependency verification is the only check flagged as not-yet-implemented."""
    _write_manifest(tmp_path / "skill-repo.yaml", _minimal_valid_manifest())
    _make_skill(tmp_path, "example-skill", _valid_skill_md())
    report = validate_repo(tmp_path)
    deferred = {
        r.name
        for r in report.results
        if r.skipped and r.skip_reason and "not yet implemented" in r.skip_reason
    }
    assert deferred == {"cross-repo-dependencies"}


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


# ---------------------------------------------------------------------------
# frontmatter check (Check 2)
# ---------------------------------------------------------------------------


def test_frontmatter_passes_on_valid_skill(tmp_path: Path) -> None:
    _write_manifest(tmp_path / "skill-repo.yaml", _minimal_valid_manifest())
    _make_skill(tmp_path, "example-skill", _valid_skill_md())
    report = validate_repo(tmp_path)
    assert _result(report, "frontmatter").passed


def test_frontmatter_rejects_unknown_status(tmp_path: Path) -> None:
    _write_manifest(tmp_path / "skill-repo.yaml", _minimal_valid_manifest())
    bad = _valid_skill_md().replace("status: active", "status: shipping")
    _make_skill(tmp_path, "bad-skill", bad)
    report = validate_repo(tmp_path)
    errors = _result(report, "frontmatter").errors
    assert any("bad-skill" in e and "status" in e.lower() for e in errors)


def test_frontmatter_surfaces_skill_md_parse_error(tmp_path: Path) -> None:
    """A SKILL.md without frontmatter fenced block surfaces in the frontmatter check."""
    _write_manifest(tmp_path / "skill-repo.yaml", _minimal_valid_manifest())
    _make_skill(tmp_path, "no-frontmatter", "Just body, no YAML fence\n")
    report = validate_repo(tmp_path)
    errors = _result(report, "frontmatter").errors
    assert any("no-frontmatter" in e and "missing a YAML frontmatter" in e for e in errors)


# ---------------------------------------------------------------------------
# body check (Check 3)
# ---------------------------------------------------------------------------


def test_body_passes_when_all_required_sections_present(tmp_path: Path) -> None:
    _write_manifest(tmp_path / "skill-repo.yaml", _minimal_valid_manifest())
    _make_skill(tmp_path, "example-skill", _valid_skill_md())
    report = validate_repo(tmp_path)
    assert _result(report, "body").passed


def test_body_errors_on_missing_required_section(tmp_path: Path) -> None:
    _write_manifest(tmp_path / "skill-repo.yaml", _minimal_valid_manifest())
    md = _valid_skill_md().replace("## Workflow\n1. Do.\n", "")
    _make_skill(tmp_path, "missing-workflow", md)
    report = validate_repo(tmp_path)
    errors = _result(report, "body").errors
    assert any("missing-workflow" in e and "Workflow" in e for e in errors)


def test_body_requires_identity_for_copilot_studio(tmp_path: Path) -> None:
    """Per SKL-008, Copilot Studio surfaces persona - Identity section required."""
    _write_manifest(tmp_path / "skill-repo.yaml", _minimal_valid_manifest())
    md = _valid_skill_md(platforms=("copilot-studio",))
    _make_skill(
        tmp_path,
        "no-identity",
        md,
        sidecars={"copilot-studio": "bindings:\n  knowledge: {}\n"},
    )
    report = validate_repo(tmp_path)
    errors = _result(report, "body").errors
    assert any("no-identity" in e and "Identity" in e for e in errors)


def test_body_does_not_require_identity_for_claude_code_only(tmp_path: Path) -> None:
    """Claude-family targets strip Identity (SKL-008); body check does not require it."""
    _write_manifest(tmp_path / "skill-repo.yaml", _minimal_valid_manifest())
    _make_skill(tmp_path, "claude-only", _valid_skill_md(platforms=("claude-code",)))
    report = validate_repo(tmp_path)
    body_errors = _result(report, "body").errors
    assert not any("Identity" in e for e in body_errors)


def test_body_warns_when_h1_does_not_match_display_name(tmp_path: Path) -> None:
    _write_manifest(tmp_path / "skill-repo.yaml", _minimal_valid_manifest())
    md = _valid_skill_md().replace("# Example Skill", "# Something Else")
    _make_skill(tmp_path, "h1-mismatch", md)
    report = validate_repo(tmp_path)
    warnings = _result(report, "body").warnings
    assert any("h1-mismatch" in w and "display_name" in w for w in warnings)


def test_body_requires_knowledge_sources_when_knowledge_declared(tmp_path: Path) -> None:
    _write_manifest(tmp_path / "skill-repo.yaml", _minimal_valid_manifest())
    # knowledge=True declares an ID but extra_body omits the section
    md = _valid_skill_md(knowledge=True)
    # Remove the Knowledge Sources section to trigger the error
    md = md.replace("## Knowledge Sources\n- The kb knowledge base.\n", "")
    skill_root = _make_skill(tmp_path, "no-knowledge-section", md)
    (skill_root / "kb.md").write_text("# kb\n")
    report = validate_repo(tmp_path)
    errors = _result(report, "body").errors
    assert any("no-knowledge-section" in e and "Knowledge Sources" in e for e in errors)


# ---------------------------------------------------------------------------
# sidecars check
# ---------------------------------------------------------------------------


def test_sidecar_schema_violation_is_an_error(tmp_path: Path) -> None:
    _write_manifest(tmp_path / "skill-repo.yaml", _minimal_valid_manifest())
    _make_skill(
        tmp_path,
        "bad-sidecar",
        _valid_skill_md(platforms=("copilot-studio",), extra_body="\n## Identity\nYou are X.\n"),
        sidecars={"copilot-studio": "budget: 99999\n"},  # over the 8K cap
    )
    report = validate_repo(tmp_path)
    errors = _result(report, "sidecars").errors
    assert any("bad-sidecar" in e and "copilot-studio.yaml" in e for e in errors)


def test_sidecar_binding_references_undeclared_id(tmp_path: Path) -> None:
    _write_manifest(tmp_path / "skill-repo.yaml", _minimal_valid_manifest())
    _make_skill(
        tmp_path,
        "bad-binding",
        _valid_skill_md(platforms=("copilot-studio",), extra_body="\n## Identity\nYou are X.\n"),
        sidecars={
            "copilot-studio": dedent(
                """\
                bindings:
                  knowledge: { ghost: "Ghost Knowledge" }
                """
            )
        },
    )
    report = validate_repo(tmp_path)
    errors = _result(report, "sidecars").errors
    assert any("bad-binding" in e and "ghost" in e and "skl.knowledge" in e for e in errors)


def test_sidecar_unparseable_yaml_is_an_error(tmp_path: Path) -> None:
    _write_manifest(tmp_path / "skill-repo.yaml", _minimal_valid_manifest())
    _make_skill(
        tmp_path,
        "bad-yaml",
        _valid_skill_md(platforms=("copilot-studio",), extra_body="\n## Identity\nYou are X.\n"),
        sidecars={"copilot-studio": "budget: [unclosed\n"},
    )
    report = validate_repo(tmp_path)
    errors = _result(report, "sidecars").errors
    assert any("bad-yaml" in e and "could not be parsed" in e for e in errors)


def test_sidecar_warns_when_bindings_declared_but_sidecar_missing(tmp_path: Path) -> None:
    """SKL-004: warn if enabled_platforms includes a non-Skills-native target with no sidecar."""
    _write_manifest(tmp_path / "skill-repo.yaml", _minimal_valid_manifest())
    md = _valid_skill_md(platforms=("copilot-studio",), knowledge=True)
    skill_root = _make_skill(tmp_path, "no-sidecar", md)
    (skill_root / "kb.md").write_text("# kb\n")
    # Also need Identity for copilot-studio
    skill_md_path = skill_root / "SKILL.md"
    skill_md_path.write_text(skill_md_path.read_text() + "\n## Identity\nYou are X.\n")
    report = validate_repo(tmp_path)
    warnings = _result(report, "sidecars").warnings
    assert any("no-sidecar" in w and "copilot-studio" in w for w in warnings)


# ---------------------------------------------------------------------------
# knowledge-contracts check (Check 4)
# ---------------------------------------------------------------------------


def test_knowledge_contracts_passes_when_files_exist(tmp_path: Path) -> None:
    _write_manifest(tmp_path / "skill-repo.yaml", _minimal_valid_manifest())
    skill_root = _make_skill(tmp_path, "has-kb", _valid_skill_md(knowledge=True))
    (skill_root / "kb.md").write_text("# kb\n")
    report = validate_repo(tmp_path)
    assert _result(report, "knowledge-contracts").passed


def test_knowledge_contracts_errors_when_file_missing(tmp_path: Path) -> None:
    _write_manifest(tmp_path / "skill-repo.yaml", _minimal_valid_manifest())
    _make_skill(tmp_path, "missing-kb", _valid_skill_md(knowledge=True))
    report = validate_repo(tmp_path)
    errors = _result(report, "knowledge-contracts").errors
    assert any("missing-kb" in e and "kb.md" in e for e in errors)


# ---------------------------------------------------------------------------
# values-declarations check (Check 7)
# ---------------------------------------------------------------------------


def test_values_declarations_passes_when_all_tokens_declared(tmp_path: Path) -> None:
    _write_manifest(tmp_path / "skill-repo.yaml", _minimal_valid_manifest())
    md = dedent(
        """\
        ---
        name: vars-skill
        description: A skill that uses variables.
        skl:
          schema_version: 1
          display_name: Vars Skill
          status: active
          enabled_platforms: [claude-code]
          variables:
            - { name: company, description: The company, required: true }
        ---

        # Vars Skill

        ## Capabilities
        Operates for {{variables.company}}.

        ## Workflow
        1. Use {{ variables.company }}.

        ## Edge Cases
        - None.

        ## Examples
        For {{variables.company}}.
        """
    )
    _make_skill(tmp_path, "vars-skill", md)
    report = validate_repo(tmp_path)
    assert _result(report, "values-declarations").passed


def test_values_declarations_errors_on_undeclared_body_token(tmp_path: Path) -> None:
    _write_manifest(tmp_path / "skill-repo.yaml", _minimal_valid_manifest())
    md = _valid_skill_md(extra_body="\n\nReferences {{variables.ghost}}.\n")
    _make_skill(tmp_path, "undeclared", md)
    report = validate_repo(tmp_path)
    errors = _result(report, "values-declarations").errors
    assert any("undeclared" in e and "ghost" in e for e in errors)


def test_values_declarations_errors_on_undeclared_sidecar_token(tmp_path: Path) -> None:
    _write_manifest(tmp_path / "skill-repo.yaml", _minimal_valid_manifest())
    _make_skill(
        tmp_path,
        "sidecar-tokens",
        _valid_skill_md(platforms=("copilot-studio",), extra_body="\n## Identity\nYou are X.\n"),
        sidecars={
            "copilot-studio": dedent(
                """\
                bindings:
                  knowledge: { x: "Path {{variables.unknown_var}}" }
                """
            )
        },
    )
    report = validate_repo(tmp_path)
    errors = _result(report, "values-declarations").errors
    assert any("sidecar-tokens" in e and "unknown_var" in e for e in errors)
