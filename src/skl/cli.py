"""Top-level CLI for skl.

The CLI surface is specified in docs/spec/cli.md. Implemented verbs dispatch
to the corresponding module under ``src/skl/``; verbs that have not yet been
built raise ``NotImplementedError`` with a pointer back to the spec.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import click

from skl import __version__
from skl.budget import budget_report, render_report
from skl.compile import (
    CompilerNotImplementedError,
    build_ir,
    compile_skill,
)
from skl.index import regenerate_index
from skl.init import (
    DEFAULT_SHARED_KIT_SOURCE,
    DEFAULT_SHARED_KIT_VERSION,
    find_skill_repo_root,
    init_repo,
    init_skill,
)
from skl.lint import apply_fixes, lint_repo
from skl.shared import sync_global, sync_repo_scoped
from skl.validate import (
    CheckResult,
    ValidationReport,
    check_compatibility_status,
    exit_code,
    validate_repo,
)

SPEC_REFERENCE = "See docs/spec/cli.md for the planned behaviour."

# Subcommands exempt from the global `skl_version` compatibility guard. See
# SKL-003 (original guard) and SKL-010 (edge cases) in docs/decisions/.
# `--version` and `--help` are also exempt because click handles them as eager
# options that exit before the group callback fires; this is documented rather
# than coded around (SKL-010 §4).
COMPAT_GUARD_SKIP: frozenset[str] = frozenset({"init", "validate"})

# Env-var escape hatch (SKL-010). Any value in this set, case-insensitive,
# bypasses the version-range check with a loud stderr warning. It does NOT
# bypass parse failure.
_COMPAT_BYPASS_TRUTHY: frozenset[str] = frozenset({"1", "true", "yes", "on"})


def _compat_bypass_enabled() -> bool:
    """Return True when SKL_IGNORE_COMPAT is set to a truthy value."""
    raw = os.environ.get("SKL_IGNORE_COMPAT", "")
    return raw.strip().lower() in _COMPAT_BYPASS_TRUTHY


@click.group(
    context_settings={"help_option_names": ["-h", "--help"]},
    help="Skill build and multi-platform deployment tool.",
)
@click.version_option(version=__version__, prog_name="skl")
@click.pass_context
def main(ctx: click.Context) -> None:
    """skl CLI entry point.

    Runs the global compatibility guard (per docs/spec/infrastructure.md
    §Versioning) before any subcommand dispatches, unless that subcommand
    is in :data:`COMPAT_GUARD_SKIP`. Behaviour is governed by SKL-003 (the
    guard itself) and SKL-010 (env-var escape hatch, fail-fast on parse
    failure).

    ``skl --version`` and ``skl --help`` bypass this callback entirely
    because click handles them as eager options that exit before the group
    callback fires.
    """
    if ctx.invoked_subcommand is None or ctx.invoked_subcommand in COMPAT_GUARD_SKIP:
        return
    repo_root = find_skill_repo_root(Path.cwd())
    if repo_root is None:
        return
    status = check_compatibility_status(repo_root)

    # Parse failure is non-bypassable. SKL_IGNORE_COMPAT exists for "I know
    # my version is wrong but I'll fix it later"; a broken manifest is a
    # different problem - fix the file.
    if status.kind == "parse_error":
        click.echo(f"compatibility check failed: {status.message}", err=True)
        ctx.exit(4)
        return

    bypass = _compat_bypass_enabled()
    if status.kind == "mismatch" and not bypass:
        click.echo(
            f"compatibility check failed: {status.message}\n"
            "(set SKL_IGNORE_COMPAT=1 to override for one session, or "
            "run `skl validate` to see the full report).",
            err=True,
        )
        ctx.exit(4)
        return

    if bypass:
        detail = f" ({status.message})" if status.kind == "mismatch" else ""
        click.echo(
            f"warning: compatibility guard bypassed via SKL_IGNORE_COMPAT{detail}",
            err=True,
        )


@main.command()
@click.argument("name")
@click.option(
    "--shared-kit-source",
    default=DEFAULT_SHARED_KIT_SOURCE,
    show_default=True,
    help="(global form) Written into shared_kit.source in the new manifest.",
)
@click.option(
    "--shared-kit-version",
    default=DEFAULT_SHARED_KIT_VERSION,
    show_default=True,
    help="(global form) Written into shared_kit.version. Resolved by `skl shared sync`.",
)
@click.option("--no-git", is_flag=True, help="(global form) Skip `git init` on the new directory.")
@click.option(
    "--platform",
    "platforms",
    multiple=True,
    help="(repo-scoped form) Target platform; repeatable. Sidecars are scaffolded "
    "for non-Skills-native targets.",
)
def init(
    name: str,
    shared_kit_source: str,
    shared_kit_version: str,
    no_git: bool,
    platforms: tuple[str, ...],
) -> None:
    """Scaffold a new skill-host repo (global form) or a new skill (repo-scoped form).

    Dispatch is based on the working directory:

    \b
    - **Outside** a skill-host repo: global form. Creates `./<name>/` with a
      manifest, README, LICENSE, `.gitignore`, empty `skills/`, and an
      attempted `skl shared sync`.
    - **Inside** a skill-host repo: repo-scoped form. Creates
      `<repo>/skills/<name>/SKILL.md` from the bundled template plus
      sidecar stubs for any `--platform` targets in {copilot-studio, m365,
      vscode}.
    """
    cwd = Path.cwd()
    repo_root = find_skill_repo_root(cwd)

    if repo_root is None:
        # Global form
        if platforms:
            raise click.ClickException(
                "--platform is only valid in the repo-scoped form (inside an "
                "existing skill-host repo). For a new repo, omit --platform; "
                "enable platforms via skills' frontmatter after scaffolding."
            )
        target = cwd / name
        try:
            init_repo(
                target,
                shared_kit_source=shared_kit_source,
                shared_kit_version=shared_kit_version,
                no_git=no_git,
            )
        except (ValueError, FileExistsError) as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo(f"scaffolded skill-host repo at {target}")
        return

    # Repo-scoped form
    if (
        shared_kit_source != DEFAULT_SHARED_KIT_SOURCE
        or shared_kit_version != DEFAULT_SHARED_KIT_VERSION
        or no_git
    ):
        click.echo(
            "warning: --shared-kit-source / --shared-kit-version / --no-git "
            "are global-form flags and are ignored when scaffolding a skill",
            err=True,
        )
    try:
        skill_root = init_skill(repo_root, name, platforms=platforms)
    except (ValueError, FileExistsError) as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"scaffolded skill at {skill_root}")


@main.command()
@click.option("--skill", help="(deferred) Validate a specific skill by kebab name.")
@click.option(
    "--all",
    "all_",
    is_flag=True,
    help="(deferred) Validate every skill in the repo.",
)
def validate(skill: str | None, all_: bool) -> None:
    """Run every implemented validate check family against the repo.

    Cross-repo dependency verification is still listed as ``skipped``
    because it needs git access to resolve pinned SHAs; landing that is
    its own work. The ``--skill`` and ``--all`` flags are accepted but
    raise ``NotImplementedError`` per SKL-002 until per-skill targeting
    is wired in.
    """
    if skill or all_:
        raise NotImplementedError(
            "per-skill validation flags (`--skill`, `--all`) are not yet implemented. "
            f"{SPEC_REFERENCE}"
        )

    repo_root = find_skill_repo_root(Path.cwd())
    if repo_root is None:
        raise click.ClickException("not inside a skill-host repo")

    report = validate_repo(repo_root)
    _print_validation_report(report)
    code = exit_code(report)
    if code:
        raise SystemExit(code)


def _print_validation_report(report: ValidationReport) -> None:
    """Render a ValidationReport to stderr in a stable, scannable format."""
    for result in report.results:
        _print_check_result(result)
    summary = _validation_summary(report)
    click.echo(summary, err=True)


def _print_check_result(result: CheckResult) -> None:
    if result.skipped:
        click.echo(f"  skip   {result.name}: {result.skip_reason}", err=True)
        return
    if result.errors:
        click.echo(f"  FAIL   {result.name}", err=True)
        for err in result.errors:
            click.echo(f"           error: {err}", err=True)
        for warn in result.warnings:
            click.echo(f"           warn:  {warn}", err=True)
        return
    if result.warnings:
        click.echo(f"  warn   {result.name}", err=True)
        for warn in result.warnings:
            click.echo(f"           warn:  {warn}", err=True)
        return
    click.echo(f"  ok     {result.name}", err=True)


def _validation_summary(report: ValidationReport) -> str:
    if report.compatibility_failed:
        return "validation failed: skl_version incompatible (exit 4)"
    if report.has_errors:
        return "validation failed (exit 1)"
    if report.has_warnings:
        return "validation ok (with warnings)"
    return "validation ok"


_KNOWN_PLATFORMS: frozenset[str] = frozenset(
    {"copilot-studio", "m365", "ms-cowork", "claude-code", "claude-cowork", "vscode"}
)


@main.command()
@click.option("--skill", "skill_name", help="Compile a specific skill (by kebab name).")
@click.option(
    "--platform",
    "platform_id",
    help="Compile for a specific platform. Defaults to every platform in each skill's `enabled_platforms`.",
)
@click.option(
    "--all",
    "all_",
    is_flag=True,
    help="Accepted for spec compatibility; the default is already to compile every skill x enabled-platform combination.",
)
def compile(
    skill_name: str | None,
    platform_id: str | None,
    all_: bool,
) -> None:
    """Compile SKILL.md to enabled platform artefacts under platforms/.

    Without flags: compiles every skill for every platform in its
    `enabled_platforms`. With `--skill` / `--platform`: filters to that
    skill / platform. Stages 3 (VS Code) and 4 (Copilot Studio / M365)
    add compilers for the remaining targets; until then, `skl compile`
    against those platforms reports them as skipped.
    """
    repo_root = find_skill_repo_root(Path.cwd())
    if repo_root is None:
        raise click.ClickException("not inside a skill-host repo")

    if platform_id is not None and platform_id not in _KNOWN_PLATFORMS:
        raise click.ClickException(
            f"unknown platform {platform_id!r}; known: {', '.join(sorted(_KNOWN_PLATFORMS))}"
        )

    skills_dir = repo_root / "skills"
    if not skills_dir.is_dir():
        click.echo("no skills/ directory found - nothing to compile", err=True)
        return

    skill_roots = sorted(p for p in skills_dir.glob("*/") if (p / "SKILL.md").is_file())
    if skill_name is not None:
        skill_roots = [p for p in skill_roots if p.name == skill_name]
        if not skill_roots:
            raise click.ClickException(f"no skill named {skill_name!r} under skills/")

    compiled = 0
    skipped = 0
    errors = 0

    for skill_root in skill_roots:
        try:
            ir = build_ir(skill_root, repo_root)
        except Exception as exc:
            click.echo(
                f"  FAIL    {skill_root.name}: could not parse SKILL.md: {exc}",
                err=True,
            )
            errors += 1
            continue

        targets = [platform_id] if platform_id is not None else list(ir.skill.enabled_platforms)
        if not targets:
            click.echo(
                f"  warn    {ir.name}: no enabled_platforms; nothing to compile",
                err=True,
            )
            continue

        for plat in targets:
            try:
                result = compile_skill(ir, plat)
            except CompilerNotImplementedError as exc:
                click.echo(f"  skip    {plat:<15} {ir.name}: {exc}", err=True)
                skipped += 1
                continue
            except Exception as exc:
                click.echo(f"  FAIL    {plat:<15} {ir.name}: {exc}", err=True)
                errors += 1
                continue
            relative_out = result.output_root.relative_to(repo_root)
            click.echo(
                f"  ok      {plat:<15} {ir.name} -> {relative_out}/ "
                f"({len(result.files_written)} files)",
                err=True,
            )
            compiled += 1

    summary = f"compile complete: {compiled} ok, {skipped} skipped, {errors} errors"
    click.echo(summary, err=True)
    if errors:
        raise SystemExit(1)


@main.command()
@click.option(
    "--all",
    "all_",
    is_flag=True,
    help="Accepted for spec compatibility; the default already reports every skill.",
)
def budget(all_: bool) -> None:
    """Report character usage versus per-platform budget (8K for Copilot Studio + M365).

    Walks every skill in the repo and computes the would-be compiled
    instructions length for each enabled budget-capped platform
    (Copilot Studio + M365). Skills-native and VS Code targets are
    uncapped and are not shown.

    Exit codes: 0 if no overages; 1 if any (skill, platform) pair
    exceeds its cap.
    """
    repo_root = find_skill_repo_root(Path.cwd())
    if repo_root is None:
        raise click.ClickException("not inside a skill-host repo")
    report = budget_report(repo_root)
    click.echo(render_report(report), err=True, nl=False)
    if report.has_overages:
        raise SystemExit(1)


@main.command()
@click.option("--all", "all_", is_flag=True, help="Test every skill.")
@click.option("--mock", is_flag=True, help="Use mocked platform responses.")
def test(all_: bool, mock: bool) -> None:
    """Run fixtures against compiled artefacts."""
    raise NotImplementedError(f"skl test is not implemented yet. {SPEC_REFERENCE}")


@main.command()
def index() -> None:
    """Regenerate skills/SKILLS_INDEX.md from the current skill set.

    Walks every ``skills/<name>/SKILL.md`` and writes a deterministic
    markdown table to ``skills/SKILLS_INDEX.md``. Same input set produces
    byte-identical output; re-run from CI to detect divergence.
    """
    repo_root = find_skill_repo_root(Path.cwd())
    if repo_root is None:
        raise click.ClickException("not inside a skill-host repo")
    try:
        path = regenerate_index(repo_root)
    except FileNotFoundError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"wrote {path.relative_to(repo_root)}", err=True)


@main.command()
@click.option(
    "--all",
    "all_",
    is_flag=True,
    help="Accepted for spec compatibility; current behaviour always lints every skill.",
)
@click.option("--fix", is_flag=True, help="Apply auto-fixable findings in place.")
def lint(all_: bool, fix: bool) -> None:
    """Style enforcement: em-dashes, AU spellings, unresolved tokens, credentials.

    Lints every skill folder under ``skills/`` in the active repo. Exits 0
    when no errors are present (warnings allowed); exits 1 when any
    error-severity finding is reported. With ``--fix``, auto-fixable
    findings (em-dashes, AU spellings) are applied in place before
    re-evaluating exit status.
    """
    repo_root = find_skill_repo_root(Path.cwd())
    if repo_root is None:
        raise click.ClickException("not inside a skill-host repo")

    report = lint_repo(repo_root)

    if fix and report.findings:
        modified = apply_fixes(report.findings)
        for path in sorted(modified):
            click.echo(f"  fixed   {path.relative_to(repo_root)}", err=True)
        report = lint_repo(repo_root)

    for finding in report.findings:
        prefix = "ERROR " if finding.severity == "error" else "warn  "
        location = f"{finding.file.relative_to(repo_root)}:{finding.line}"
        click.echo(f"  {prefix} [{finding.rule}] {location}: {finding.message}", err=True)

    if not report.findings:
        click.echo("lint ok", err=True)
    elif report.has_errors:
        click.echo(f"lint failed: {len(report.errors)} error(s)", err=True)
        raise SystemExit(1)
    else:
        click.echo(f"lint ok (with {len(report.warnings)} warning(s))", err=True)


@main.command()
@click.option("--skill", required=True, help="Skill kebab name.")
@click.option("--platform", "platform_", required=True, help="Target platform identifier.")
def deploy(skill: str, platform_: str) -> None:
    """Substitute values and copy the compiled artefact to its install location."""
    raise NotImplementedError(f"skl deploy is not implemented yet. {SPEC_REFERENCE}")


@main.command()
@click.argument("name")
@click.option("--in-favour-of", "in_favour_of", help="Replacement skill.")
def deprecate(name: str, in_favour_of: str | None) -> None:
    """Mark a skill as deprecated."""
    raise NotImplementedError(f"skl deprecate is not implemented yet. {SPEC_REFERENCE}")


@main.command()
@click.argument("legacy_path", type=click.Path(exists=True))
def migrate(legacy_path: str) -> None:
    """Scaffold a SKILL.md draft from a legacy agent file (in-repo only)."""
    raise NotImplementedError(f"skl migrate is not implemented yet. {SPEC_REFERENCE}")


@main.group()
def shared() -> None:
    """Shared-kit operations."""


@shared.command("sync")
@click.option(
    "--version",
    "version_",
    help="Pin or override the shared-kit version. In repo-scoped form, defaults to the manifest value.",
)
@click.option(
    "--source",
    "source_",
    help="(global form) Shared-kit source URL or `github.com/<org>/<repo>` shorthand.",
)
@click.option(
    "--to",
    "to_",
    type=click.Path(path_type=Path),
    help="(global form) Write the kit to this path instead of ./_shared/.",
)
def shared_sync(version_: str | None, source_: str | None, to_: Path | None) -> None:
    """Fetch the shared kit and write it into ./_shared/ (or to --to)."""
    if to_ is not None:
        if source_ is None or version_ is None:
            raise click.ClickException("global form (--to) requires both --source and --version")
        try:
            resolved_version, sha = sync_global(source=source_, version=version_, target=to_)
        except (subprocess.CalledProcessError, RuntimeError, ValueError) as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo(f"synced {source_}@{resolved_version} ({sha}) to {to_}")
        return

    repo_root = find_skill_repo_root(Path.cwd())
    if repo_root is None:
        raise click.ClickException("not inside a skill-host repo")
    try:
        resolved_version, sha = sync_repo_scoped(repo_root, version=version_)
    except (subprocess.CalledProcessError, RuntimeError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"synced shared kit @ {resolved_version} ({sha}) into {repo_root}/_shared/")


@main.group()
def values() -> None:
    """Values-file operations."""


@values.command("check")
@click.option("--values-file", "values_file", type=click.Path(), help="Values file to check.")
def values_check(values_file: str | None) -> None:
    """Verify all required vars are supplied and reject secret-like keys."""
    raise NotImplementedError(f"skl values check is not implemented yet. {SPEC_REFERENCE}")


@values.command("sync")
@click.option("--from", "from_", required=True, help="Source path or git URL.")
@click.option("--profile", help="Named profile within the source.")
def values_sync(from_: str, profile: str | None) -> None:
    """Sync a values profile from the sibling private values repo into ./.values/."""
    raise NotImplementedError(f"skl values sync is not implemented yet. {SPEC_REFERENCE}")


@values.command("schema")
@click.option("--output", type=click.Path(), help="Where to write the generated schema.")
def values_schema(output: str | None) -> None:
    """Generate a JSON Schema from the union of all enabled skills' variables."""
    raise NotImplementedError(f"skl values schema is not implemented yet. {SPEC_REFERENCE}")


@main.group()
def secrets() -> None:
    """Secrets-backend operations."""


@secrets.command("get")
@click.argument("key")
def secrets_get(key: str) -> None:
    """Resolve a secret via the configured backend."""
    raise NotImplementedError(f"skl secrets get is not implemented yet. {SPEC_REFERENCE}")


@secrets.command("set")
@click.argument("key")
def secrets_set(key: str) -> None:
    """Write a secret to the configured backend (where supported)."""
    raise NotImplementedError(f"skl secrets set is not implemented yet. {SPEC_REFERENCE}")


@secrets.command("list")
def secrets_list() -> None:
    """Enumerate known secret keys without revealing values."""
    raise NotImplementedError(f"skl secrets list is not implemented yet. {SPEC_REFERENCE}")


if __name__ == "__main__":
    main()
