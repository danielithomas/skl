"""Implementation of ``skl validate``.

Runs the eight named check families against the active skill-host repo
(spec: ``docs/spec/cli.md`` ``skl validate``) and returns a
:class:`ValidationReport`. The CLI layer translates the report into stderr
output and an exit code.

Check families:

1. ``manifest`` - ``skill-repo.yaml`` against its bundled schema.
2. ``frontmatter`` - each SKILL.md frontmatter against
   ``skill.frontmatter.schema.json`` (SKL-004).
3. ``body`` - required H2 sections per the platforms the skill targets
   (per SKL-008 and the body structure in the skills-spec analysis §7.4).
4. ``knowledge-contracts`` - declared knowledge contracts exist.
5. ``cross-repo-dependencies`` - deferred (needs git access for pinned-SHA
   verification; entries report as ``skipped`` with a clear reason).
6. ``shared-kit-drift`` - ``_shared/.kit_version`` matches the manifest
   pin.
7. ``values-declarations`` - every ``{{variables.X}}`` token in a skill's
   body or sidecars is declared in ``skl.variables[]``.
8. ``compatibility`` - the installed ``skl`` is in the manifest's range.

The ``sidecars`` check (new in v0.1 per SKL-004) is run as part of family
3 / 4 / 7 conceptually; it lands as its own ``CheckResult`` because the
errors it surfaces are not bound to any single original spec family.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import jsonschema
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

from skl import __version__, manifest
from skl.schemas import load_schema
from skl.sidecars import SidecarParseError, Sidecars, parse_sidecars
from skl.skill_md import Skill, SkillParseError, parse_skill_md

LATEST_VERSION_SENTINEL = "latest"

GuardKind = Literal["ok", "mismatch", "parse_error"]

# Body sections required for every skill regardless of platform targets
# (per skills-spec analysis §7.4). Identity is required conditionally - see
# ``_check_body``.
_ALWAYS_REQUIRED_SECTIONS: tuple[str, ...] = (
    "Capabilities",
    "Workflow",
    "Edge Cases",
    "Examples",
)

# Platforms whose default-surface persona setup (per SKL-008) requires
# the body to carry a ``## Identity`` section. ``vscode`` qualifies when
# the Custom Agent sidecar is present (handled at the call site).
_PERSONA_SURFACE_PLATFORMS: frozenset[str] = frozenset({"copilot-studio"})

# Pattern for `{{variables.X}}` tokens. Whitespace inside the braces is
# tolerated so authors can use either `{{variables.x}}` or `{{ variables.x }}`.
_VARIABLE_TOKEN_RE = re.compile(r"\{\{\s*variables\.([a-z][a-z0-9_]*)\s*\}\}")


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


# Cross-repo dependency verification needs git access to resolve pinned
# SHAs against the depended-on repo. Deferred until that scaffolding lands;
# reported as ``skipped`` so the report does not pretend it passed.
_DEFERRED_CHECKS: tuple[tuple[str, str], ...] = (
    (
        "cross-repo-dependencies",
        "needs git access to verify pinned SHAs against the depended-on repo; not yet implemented",
    ),
)


@dataclass
class _SkillRecord:
    """Per-skill state used by the per-skill check families.

    Parse errors are split by source: ``skill_parse_error`` blocks the
    frontmatter / body / knowledge-contracts / values-declarations checks
    for that skill; ``sidecar_parse_error`` blocks the sidecars check.
    """

    root: Path
    skill: Skill | None = None
    sidecars: Sidecars | None = None
    skill_parse_error: str | None = None
    sidecar_parse_error: str | None = None

    @property
    def name(self) -> str:
        """Best-effort skill name for error messages (kebab folder name)."""
        return self.root.name


def validate_repo(repo_root: Path) -> ValidationReport:
    """Run every implemented check against ``repo_root``.

    The compatibility check is tagged separately on the report so the CLI
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

    plain = manifest.to_plain(data)

    # Family 1
    report.results.append(_check_manifest_schema(plain))

    # Family 8 (tagged for exit code 4)
    compat = _check_compatibility(plain)
    report.results.append(compat)
    if compat.errors:
        report.compatibility_failed = True

    # Family 6
    report.results.append(_check_shared_kit_drift(repo_root, plain))

    # Per-skill discovery + checks
    records = _discover_and_parse_skills(repo_root)
    report.results.append(_check_frontmatter(records))
    report.results.append(_check_body(records))
    report.results.append(_check_sidecars(records))
    report.results.append(_check_knowledge_contracts(records))
    report.results.append(_check_values_declarations(records))

    # Family 5 (still deferred)
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
    plain = manifest.to_plain(data)
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


def _discover_and_parse_skills(repo_root: Path) -> list[_SkillRecord]:
    """Find every ``skills/<name>/SKILL.md`` and parse it + its sidecars."""
    records: list[_SkillRecord] = []
    skills_dir = repo_root / "skills"
    if not skills_dir.is_dir():
        return records
    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        skill_root = skill_md.parent
        record = _SkillRecord(root=skill_root)
        try:
            record.skill = parse_skill_md(skill_md)
        except SkillParseError as exc:
            record.skill_parse_error = str(exc)
        try:
            record.sidecars = parse_sidecars(skill_root)
        except SidecarParseError as exc:
            record.sidecar_parse_error = str(exc)
        records.append(record)
    return records


def _check_frontmatter(records: list[_SkillRecord]) -> CheckResult:
    """Validate each SKILL.md frontmatter against the bundled schema."""
    result = CheckResult(name="frontmatter")
    if not records:
        result.skipped = True
        result.skip_reason = "no skills/ directory or no SKILL.md files found"
        return result
    schema = load_schema("skill.frontmatter.schema.json")
    validator = jsonschema.Draft202012Validator(schema)
    for record in records:
        if record.skill_parse_error is not None:
            result.errors.append(f"{record.name}: {record.skill_parse_error}")
            continue
        assert record.skill is not None
        for error in sorted(
            validator.iter_errors(record.skill.frontmatter),
            key=lambda e: list(e.absolute_path),
        ):
            location = ".".join(str(p) for p in error.absolute_path) or "(root)"
            result.errors.append(f"{record.name} ({location}): {error.message}")
    return result


def _check_body(records: list[_SkillRecord]) -> CheckResult:
    """Verify each SKILL.md has the body sections compilers require."""
    result = CheckResult(name="body")
    if not records:
        result.skipped = True
        result.skip_reason = "no skills/ directory or no SKILL.md files found"
        return result
    for record in records:
        if record.skill is None:
            # Already surfaced by the frontmatter check; do not double-report.
            continue
        skill = record.skill
        for section in _ALWAYS_REQUIRED_SECTIONS:
            if not skill.has_section(section):
                result.errors.append(f"{record.name}: missing required body section ## {section}")
        if skill.knowledge_ids and not skill.has_section("Knowledge Sources"):
            result.errors.append(
                f"{record.name}: declares `skl.knowledge[]` but lacks "
                "## Knowledge Sources body section"
            )
        if skill.tool_ids and not skill.has_section("Tools"):
            result.errors.append(
                f"{record.name}: declares `skl.tools[]` but lacks ## Tools body section"
            )
        if _needs_identity_section(skill, record.sidecars):
            if not skill.has_section("Identity"):
                result.errors.append(
                    f"{record.name}: targets a persona-surface platform but lacks "
                    "## Identity body section (per SKL-008)"
                )
        # H1 should mirror display_name (warn, not error).
        if skill.display_name is not None:
            expected_h1 = f"# {skill.display_name}"
            if expected_h1 not in skill.intro.splitlines():
                result.warnings.append(
                    f"{record.name}: H1 line does not match `skl.display_name` "
                    f"({skill.display_name!r}); compilers use display_name for the title"
                )
    return result


def _needs_identity_section(skill: Skill, sidecars: Sidecars | None) -> bool:
    """An ``## Identity`` section is required for any persona-surface target.

    SKL-008's per-target table maps to: Copilot Studio surfaces by default;
    M365 strips; ms-cowork / claude-code / claude-cowork / vscode-skill strip;
    vscode Custom Agent variant surfaces (so the section is required when a
    vscode sidecar is present, regardless of what other platforms target).
    """
    targets = set(skill.enabled_platforms)
    if targets & _PERSONA_SURFACE_PLATFORMS:
        return True
    if "vscode" in targets and sidecars is not None and sidecars.has("vscode"):
        return True
    return False


def _check_sidecars(records: list[_SkillRecord]) -> CheckResult:
    """Validate each sidecar against its schema and cross-reference IDs."""
    result = CheckResult(name="sidecars")
    if not records:
        result.skipped = True
        result.skip_reason = "no skills/ directory or no SKILL.md files found"
        return result

    for record in records:
        if record.sidecar_parse_error is not None:
            result.errors.append(f"{record.name}: {record.sidecar_parse_error}")
            continue
        if record.sidecars is None:
            continue
        skill = record.skill  # may be None - schema check still runs
        for platform_id in record.sidecars.platform_ids:
            sidecar = record.sidecars.get(platform_id)
            assert sidecar is not None
            schema_name = f"platforms/{platform_id}.schema.json"
            try:
                schema = load_schema(schema_name)
            except FileNotFoundError:
                result.warnings.append(
                    f"{record.name}: no bundled schema for sidecar "
                    f"`{platform_id}.yaml`; skipping shape check"
                )
                continue
            validator = jsonschema.Draft202012Validator(schema)
            for error in sorted(
                validator.iter_errors(sidecar.data),
                key=lambda e: list(e.absolute_path),
            ):
                location = ".".join(str(p) for p in error.absolute_path) or "(root)"
                result.errors.append(
                    f"{record.name} ({platform_id}.yaml: {location}): {error.message}"
                )
            if skill is not None:
                _cross_reference_bindings(record.name, skill, platform_id, sidecar.data, result)

        # Sidecar coverage vs enabled_platforms (per SKL-004).
        if skill is not None:
            _check_sidecar_coverage(record.name, skill, record.sidecars, result)
    return result


def _cross_reference_bindings(
    skill_name: str,
    skill: Skill,
    platform_id: str,
    sidecar_data: dict[str, Any],
    result: CheckResult,
) -> None:
    """Every binding ID must be declared in the master `skl.knowledge[]` / `skl.tools[]`."""
    bindings = sidecar_data.get("bindings", {})
    if not isinstance(bindings, dict):
        return
    declared_knowledge = set(skill.knowledge_ids)
    declared_tools = set(skill.tool_ids)
    for binding_id in bindings.get("knowledge") or {}:
        if binding_id not in declared_knowledge:
            result.errors.append(
                f"{skill_name} ({platform_id}.yaml: bindings.knowledge.{binding_id}): "
                f"id not declared in `skl.knowledge[]` of SKILL.md"
            )
    for binding_id in bindings.get("tools") or {}:
        if binding_id not in declared_tools:
            result.errors.append(
                f"{skill_name} ({platform_id}.yaml: bindings.tools.{binding_id}): "
                f"id not declared in `skl.tools[]` of SKILL.md"
            )


def _check_sidecar_coverage(
    skill_name: str,
    skill: Skill,
    sidecars: Sidecars,
    result: CheckResult,
) -> None:
    """Warn when `enabled_platforms` includes a platform with no sidecar and bindings are declared."""
    if not skill.knowledge_ids and not skill.tool_ids:
        return  # no bindings to declare; sidecar absence is fine
    for platform_id in skill.enabled_platforms:
        if platform_id in {"claude-code", "claude-cowork", "ms-cowork"}:
            continue  # Skills-native targets need no bindings
        if not sidecars.has(platform_id):
            result.warnings.append(
                f"{skill_name}: `enabled_platforms` includes {platform_id!r} but no "
                f"`skl/platforms/{platform_id}.yaml` sidecar exists; bindings will not "
                "land in the compiled artefact"
            )


def _check_knowledge_contracts(records: list[_SkillRecord]) -> CheckResult:
    """Each `skl.knowledge[i].contract` must point at an existing file."""
    result = CheckResult(name="knowledge-contracts")
    if not records:
        result.skipped = True
        result.skip_reason = "no skills/ directory or no SKILL.md files found"
        return result
    for record in records:
        if record.skill is None:
            continue
        for item in record.skill.skl.get("knowledge", []):
            if not isinstance(item, dict):
                continue
            contract = item.get("contract")
            if contract is None:
                continue
            contract_path = record.root / contract
            if not contract_path.is_file():
                result.errors.append(
                    f"{record.name}: knowledge contract not found at "
                    f"{contract_path.relative_to(record.root)}"
                )
    return result


def _check_values_declarations(records: list[_SkillRecord]) -> CheckResult:
    """Every `{{variables.X}}` token in body or sidecars must be declared."""
    result = CheckResult(name="values-declarations")
    if not records:
        result.skipped = True
        result.skip_reason = "no skills/ directory or no SKILL.md files found"
        return result
    for record in records:
        if record.skill is None:
            continue
        declared = set(record.skill.variable_names)
        # Body
        for var_name in _find_variable_tokens(record.skill.raw_text):
            if var_name not in declared:
                result.errors.append(
                    f"{record.name}: body references `{{{{variables.{var_name}}}}}` "
                    "but the variable is not declared in `skl.variables[]`"
                )
        # Sidecars
        if record.sidecars is not None:
            for platform_id in record.sidecars.platform_ids:
                sidecar = record.sidecars.get(platform_id)
                assert sidecar is not None
                for var_name in _find_variable_tokens_in_obj(sidecar.data):
                    if var_name not in declared:
                        result.errors.append(
                            f"{record.name} ({platform_id}.yaml): references "
                            f"`{{{{variables.{var_name}}}}}` but the variable is not "
                            "declared in `skl.variables[]`"
                        )
    return result


def _find_variable_tokens(text: str) -> list[str]:
    """Return every `{{variables.X}}` X in the given text (duplicates preserved)."""
    return _VARIABLE_TOKEN_RE.findall(text)


def _find_variable_tokens_in_obj(obj: Any) -> list[str]:
    """Walk a parsed YAML object collecting `{{variables.X}}` tokens from any string."""
    found: list[str] = []
    if isinstance(obj, str):
        found.extend(_find_variable_tokens(obj))
    elif isinstance(obj, dict):
        for value in obj.values():
            found.extend(_find_variable_tokens_in_obj(value))
    elif isinstance(obj, list):
        for item in obj:
            found.extend(_find_variable_tokens_in_obj(item))
    return found


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
