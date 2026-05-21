"""Implementation of ``skl validate``.

Runs a sequence of named checks against the active skill-host repo and
returns a :class:`ValidationReport` summarising errors, warnings and
skipped checks. The CLI layer is responsible for translating the report
into stderr output and exit codes.

The spec (docs/spec/cli.md ``skl validate``) defines eight check families.
This v1 implementation covers three of them - manifest schema (Check 1),
compatibility (Check 8) and shared-kit drift (Check 6). The remaining
checks depend on SKILL.md / knowledge contract / cross-repo scaffolding
that does not yet exist and are reported as skipped with a clear reason.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import jsonschema
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

from skl import __version__, manifest
from skl.schemas import load_schema

LATEST_VERSION_SENTINEL = "latest"

GuardKind = Literal["ok", "mismatch", "parse_error"]


@dataclass
class CheckResult:
    """Outcome of a single named validation check."""

    name: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    skipped: bool = False
    skip_reason: str | None = None

    @property
    def passed(self) -> bool:
        return not self.skipped and not self.errors


@dataclass
class ValidationReport:
    """Aggregate result of every check in a validate run."""

    results: list[CheckResult] = field(default_factory=list)
    compatibility_failed: bool = False

    @property
    def has_errors(self) -> bool:
        return any(r.errors for r in self.results)

    @property
    def has_warnings(self) -> bool:
        return any(r.warnings for r in self.results)


# Checks that require SKILL.md / contract / cross-repo scaffolding that does
# not yet exist in this codebase. Listed here so the report still surfaces
# them as known-pending, instead of pretending they passed.
_DEFERRED_CHECKS: tuple[tuple[str, str], ...] = (
    ("frontmatter", "depends on SKILL.md frontmatter parsing; not yet implemented"),
    ("body", "depends on SKILL.md body parsing; not yet implemented"),
    ("knowledge-contracts", "depends on SKILL.md knowledge contracts; not yet implemented"),
    ("cross-repo-dependencies", "depends on cross-repo SHA resolution; not yet implemented"),
    ("values-declarations", "depends on SKILL.md variable declarations; not yet implemented"),
)


def validate_repo(repo_root: Path) -> ValidationReport:
    """Run every implemented check against the manifest at ``repo_root``.

    The compatibility check is marked separately on the report so the CLI
    can map a compatibility failure to exit code 4 per the spec, while
    other validation failures map to exit code 1.
    """
    report = ValidationReport()
    manifest_path = repo_root / "skill-repo.yaml"

    if not manifest_path.is_file():
        result = CheckResult(name="manifest")
        result.errors.append(f"no skill-repo.yaml at {repo_root}")
        report.results.append(result)
        return report

    try:
        data = manifest.load(manifest_path)
    except Exception as exc:  # ruamel raises a few different parse errors
        result = CheckResult(name="manifest")
        result.errors.append(f"failed to parse {manifest_path}: {exc}")
        report.results.append(result)
        return report

    plain = _to_plain(data)

    report.results.append(_check_manifest_schema(plain))

    compat = _check_compatibility(plain)
    report.results.append(compat)
    if compat.errors:
        report.compatibility_failed = True

    report.results.append(_check_shared_kit_drift(repo_root, plain))

    for name, reason in _DEFERRED_CHECKS:
        report.results.append(CheckResult(name=name, skipped=True, skip_reason=reason))

    return report


def exit_code(report: ValidationReport) -> int:
    """Map a :class:`ValidationReport` to a process exit code per the spec."""
    if report.compatibility_failed:
        return 4
    if report.has_errors:
        return 1
    return 0


@dataclass
class GuardCheck:
    """Outcome of the CLI guard's pre-flight check.

    Three states (SKL-003, SKL-010):

    - ``ok``: no manifest, manifest lacks ``skl_version``, manifest is the wrong
      top-level shape, or the installed ``skl`` is inside the pinned range.
      The CLI lets the subcommand run.
    - ``mismatch``: manifest is parseable and the installed ``skl`` is outside
      its ``skl_version`` range. The CLI exits 4 unless ``SKL_IGNORE_COMPAT``
      is set, in which case it emits a loud bypass warning and continues.
    - ``parse_error``: manifest is present but cannot be parsed as YAML. The
      CLI always exits 4 with a message pointing at ``skl validate``; the
      ``SKL_IGNORE_COMPAT`` escape hatch does **not** apply.
    """

    kind: GuardKind
    message: str = ""


def check_compatibility_status(repo_root: Path) -> GuardCheck:
    """Run the guard's pre-flight check against the manifest at ``repo_root``.

    Used by the CLI's global compatibility guard (see SKL-003, SKL-010).
    The three return states are documented on :class:`GuardCheck`.
    """
    manifest_path = repo_root / "skill-repo.yaml"
    if not manifest_path.is_file():
        return GuardCheck(kind="ok")
    try:
        data = manifest.load(manifest_path)
    except Exception as exc:
        return GuardCheck(
            kind="parse_error",
            message=f"skill-repo.yaml could not be parsed ({exc}); "
            "run `skl validate` to see the parse error.",
        )
    if not isinstance(data, dict):
        return GuardCheck(kind="ok")
    plain = _to_plain(data)
    result = _check_compatibility(plain)
    if result.errors:
        return GuardCheck(kind="mismatch", message=result.errors[0])
    return GuardCheck(kind="ok")


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------


def _check_manifest_schema(data: dict[str, Any]) -> CheckResult:
    """Validate the manifest against the bundled JSON Schema."""
    result = CheckResult(name="manifest")
    schema = load_schema("skill-repo.schema.json")
    validator = jsonschema.Draft202012Validator(schema)
    for error in sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path)):
        location = ".".join(str(p) for p in error.absolute_path) or "(root)"
        result.errors.append(f"{location}: {error.message}")
    return result


def _check_compatibility(data: dict[str, Any]) -> CheckResult:
    """Verify the installed ``skl`` version is within the manifest's range."""
    result = CheckResult(name="compatibility")
    range_text = data.get("skl_version")
    if not range_text:
        # Missing field is a schema error; do not duplicate it here.
        return result

    try:
        specifier = SpecifierSet(range_text)
    except InvalidSpecifier as exc:
        result.errors.append(f"skl_version {range_text!r} is not a valid specifier: {exc}")
        return result

    try:
        installed = Version(__version__)
    except InvalidVersion as exc:
        result.errors.append(f"installed skl version {__version__!r} is not parseable: {exc}")
        return result

    if installed not in specifier:
        result.errors.append(
            f"installed skl {installed} is outside the manifest's skl_version range "
            f"{range_text!r}; upgrade or downgrade skl, or widen the range"
        )
    return result


def _check_shared_kit_drift(repo_root: Path, data: dict[str, Any]) -> CheckResult:
    """Compare ``_shared/.kit_version`` to ``shared_kit.version`` in the manifest."""
    result = CheckResult(name="shared-kit-drift")
    shared_kit = data.get("shared_kit") or {}
    manifest_version = shared_kit.get("version")

    if manifest_version == LATEST_VERSION_SENTINEL:
        result.warnings.append(
            "shared_kit.version is the 'latest' sentinel; run `skl shared sync` to pin"
        )
        return result

    kit_version_file = repo_root / "_shared" / ".kit_version"
    if not kit_version_file.exists():
        result.warnings.append(
            "_shared/.kit_version is missing; run `skl shared sync` to populate it"
        )
        return result

    on_disk = kit_version_file.read_text().strip()
    if on_disk != manifest_version:
        result.warnings.append(
            f"shared-kit drift: manifest pins {manifest_version!r} but "
            f"_shared/.kit_version is {on_disk!r}; run `skl shared sync`"
        )
    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_plain(obj: Any) -> Any:
    """Convert ruamel CommentedMap / CommentedSeq trees to plain dict / list.

    Ruamel's mapping and sequence types subclass ``dict`` and ``list``, so a
    straight ``isinstance`` walk suffices. Conversion keeps the schema code
    dialect-agnostic and prevents subtle behaviour differences from leaking
    into downstream callers.
    """
    if isinstance(obj, dict):
        return {str(k): _to_plain(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_plain(v) for v in obj]
    return obj
